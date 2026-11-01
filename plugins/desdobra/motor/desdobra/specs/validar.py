# -*- coding: utf-8 -*-
"""desdobra validar: confere qualquer arquivo (inclusive export humano) contra um formato de spec.

Confere, com o valor e a fonte de cada regra:
  - dimensao do arquivo contra a dimensao do formato (arquivo girado reprova: a rotacao e decisao do DA);
  - peso em bytes nas duas leituras de KB e MB (arquitetura-v1.md, 4.8 e 5.5): acima da leitura folgada reprova
    (specs.peso_reprova_acima_da_leitura_binaria), entre a estrita e a folgada avisa
    (specs.peso_avisa_acima_da_leitura_decimal). Peso condicional (hospedado, por tag) vale inteiro so com a
    condicao escolhida em --condicao; sem ela, fica em aviso, porque depende de como a peca vai ser servida;
  - tipo do arquivo pela assinatura (MIME) contra os tipos aceitos; extensao que nao bate com o tipo avisa.
Area util, faixas, area segura e borda de 1 px pedem o pixel e entram na validacao final da entrega (M6): aqui
ficam como nao verificadas, com o valor da folha ao lado.

Contra o job (--job), so valem os valores que o DA confirmou (specs/formatos-do-job.json). Contra um perfil da
biblioteca ou um rascunho (--perfil), os valores ainda nao foram confirmados: serve de diagnostico, e o resultado
diz isso.

O arquivo nunca e decodificado: o motor le so o cabecalho (PNG IHDR, marcador SOF do JPEG, tela logica do GIF)
para a dimensao, e os primeiros bytes para o tipo.
"""
import struct
from pathlib import Path

from desdobra import contratos, limites
from desdobra.arquivos import sha256_arquivo
from desdobra.specs import modelo

ESQUEMA = 'validacao-arquivo/1'
ASSINATURAS = ((b'\x89PNG\r\n\x1a\n', 'image/png'), (b'\xff\xd8\xff', 'image/jpeg'), (b'GIF87a', 'image/gif'),
               (b'GIF89a', 'image/gif'), (b'%PDF-', 'application/pdf'))
EXTENSOES = {'image/png': ('.png',), 'image/jpeg': ('.jpg', '.jpeg'), 'image/gif': ('.gif',),
             'application/pdf': ('.pdf',), 'image/webp': ('.webp',)}
CAMPOS_DE_PIXEL = ('area_util', 'faixas', 'area_segura', 'borda_1px')
PESOS = ('peso_max', 'peso_max_hospedado', 'peso_max_tag', 'peso_max_tag_carga_inicial', 'peso_max_tag_carga_posterior')
CONDICOES = ('hospedado', 'por_tag', 'tag_carga_inicial', 'tag_carga_posterior')
BYTES_CABECALHO = 1 << 16  # numero-neutro: bytes lidos do inicio do arquivo para achar o cabecalho
# marcadores SOF do JPEG que trazem a dimensao (C4, C8 e CC nao sao SOF) e os sem tamanho: fato do formato
MARCADORES_SOF = frozenset(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}  # numero-neutro: especificacao JPEG (ITU T.81)
MARCADORES_SEM_TAMANHO = frozenset(range(0xD0, 0xDA)) | {0x01}  # numero-neutro: RSTn, SOI, EOI e TEM do JPEG
MARCADOR_APP1 = 0xE1  # numero-neutro: segmento APP1 (Exif) do JPEG
TAG_ORIENTACAO = 0x0112  # numero-neutro: tag Orientation do Exif
ORIENTACAO_NORMAL = 1  # numero-neutro: valor Exif de imagem sem giro


class ErroValidar(Exception):
    pass


def mime_do_arquivo(inicio):
    for assinatura, mime in ASSINATURAS:
        if inicio.startswith(assinatura):
            return mime
    if inicio[:4] == b'RIFF' and inicio[8:12] == b'WEBP':  # numero-neutro: cabecalho RIFF do WebP
        return 'image/webp'
    return None


def _orientacao_exif(dados):
    """Valor da tag Orientation (0x0112) do IFD0 de um bloco Exif (TIFF), ou None."""
    try:
        if dados[:6] != b'Exif\x00\x00':
            return None
        tiff = dados[6:]
        ordem = '<' if tiff[:2] == b'II' else '>'
        desl = struct.unpack(ordem + 'I', tiff[4:8])[0]  # numero-neutro: cabecalho TIFF
        n = struct.unpack(ordem + 'H', tiff[desl:desl + 2])[0]
        for k in range(n):
            e = desl + 2 + 12 * k  # numero-neutro: entrada do IFD tem 12 bytes
            tag, _tipo, _cont = struct.unpack(ordem + 'HHI', tiff[e:e + 8])  # numero-neutro: campos da entrada
            if tag == TAG_ORIENTACAO:
                return struct.unpack(ordem + 'H', tiff[e + 8:e + 10])[0]  # numero-neutro: valor SHORT da entrada
    except struct.error:
        return None
    return None


def _jpeg(f):
    """(largura, altura, orientacao Exif) de um JPEG, andando pelos segmentos e lendo so o cabecalho de cada um
    (o export do Photoshop pode ter mais de 64 KiB de metadados antes do SOF)."""
    orientacao = None
    f.seek(2)  # numero-neutro: depois do SOI
    while True:
        cab = f.read(2)  # numero-neutro: marcador
        if len(cab) < 2 or cab[0] != 0xFF:  # numero-neutro: prefixo de marcador do JPEG
            return None, None, orientacao
        marcador = cab[1]
        if marcador == 0xFF:  # numero-neutro: preenchimento do JPEG
            f.seek(-1, 1)
            continue
        if marcador in MARCADORES_SEM_TAMANHO:
            continue
        bruto = f.read(2)  # numero-neutro: tamanho do segmento
        if len(bruto) < 2:  # numero-neutro: tamanho do segmento
            return None, None, orientacao
        tamanho = struct.unpack('>H', bruto)[0]
        if marcador in MARCADORES_SOF:
            campos = f.read(5)  # numero-neutro: precisao, altura e largura do SOF
            if len(campos) < 5:  # numero-neutro: precisao, altura e largura do SOF
                return None, None, orientacao
            altura, largura = struct.unpack('>HH', campos[1:5])  # numero-neutro: campos do SOF
            return largura, altura, orientacao
        if marcador == MARCADOR_APP1 and orientacao is None:
            orientacao = _orientacao_exif(f.read(tamanho - 2))  # numero-neutro: o tamanho conta os 2 bytes dele
            continue
        f.seek(tamanho - 2, 1)  # numero-neutro: o tamanho conta os 2 bytes dele


def dimensao_do_cabecalho(inicio, mime):
    """(largura, altura) lidas do cabecalho, ou (None, None)."""
    import io
    largura, altura, _o = _medir(io.BytesIO(inicio), mime)
    return largura, altura


def _medir(f, mime):
    try:
        if mime == 'image/jpeg':
            return _jpeg(f)
        f.seek(0)
        inicio = f.read(BYTES_CABECALHO)
        if mime == 'image/png':
            return struct.unpack('>II', inicio[16:24]) + (None,)  # numero-neutro: posicao do IHDR no PNG
        if mime == 'image/gif':
            return struct.unpack('<HH', inicio[6:10]) + (None,)  # numero-neutro: tela logica do GIF
    except (struct.error, OSError, ValueError):
        return None, None, None
    return None, None, None


def ler_arquivo(caminho):
    caminho = Path(caminho)
    with open(caminho, 'rb') as f:
        mime = mime_do_arquivo(f.read(BYTES_CABECALHO))
        largura, altura, orientacao = _medir(f, mime)
    return {'sha256': sha256_arquivo(caminho), 'bytes': caminho.stat().st_size, 'mime': mime,
            'largura': largura, 'altura': altura, 'orientacao_exif': orientacao}


def achar_formato(doc, chave):
    """O formato pela chave (veiculador|circuito|LxA) ou pelo id."""
    for f in doc['formatos']:
        if f.get('chave') == chave or f['id'] == chave:
            return f
    return None


def _item(campo, situacao, medida=None, esperado=None, motivo=None, v=None, limite=None):
    return {'campo': campo, 'situacao': situacao, 'medida': medida, 'esperado': esperado, 'motivo': motivo,
            'valor_id': v['id'] if v else None, 'valor_situacao': v['situacao'] if v else None,
            'fonte': v['fonte'] if v else None, 'limite': limite}


def _valer(v, contra):
    """O valor vale na validacao? Contra o job, so confirmado (o formatos-do-job so tem confirmado)."""
    return v is not None and v.get('valor') is not None and (contra != 'formatos_do_job' or v['situacao'] == 'confirmado')


def conferir_peso(campo, v, n_bytes, condicao):
    lim_reprova = limites.obter('specs.peso_reprova_acima_da_leitura_binaria')
    lim_avisa = limites.obter('specs.peso_avisa_acima_da_leitura_decimal')
    alvo, teto = v['valor']['alvo_bytes'], v['valor']['reprova_acima_bytes']
    esperado = {'alvo_bytes': alvo, 'reprova_acima_bytes': teto, 'condicao': v.get('condicao')}
    condicional = v.get('condicao') is not None
    vale_inteiro = not condicional or v['condicao'] == condicao
    if n_bytes > teto:
        sit = lim_reprova.efeito_efetivo if vale_inteiro else 'aviso'
        motivo = 'acima_da_leitura_folgada' if vale_inteiro else 'acima_da_leitura_folgada_se_%s' % v['condicao']
        return _item(campo, 'reprova' if sit == 'reprova' else 'aviso', n_bytes, esperado, motivo, v, lim_reprova.citacao())
    if n_bytes > alvo:
        return _item(campo, 'aviso', n_bytes, esperado, 'entre_as_duas_leituras', v, lim_avisa.citacao())
    return _item(campo, 'ok', n_bytes, esperado, None, v)


def validar(arquivo, doc, chave, contra, *, condicao=None, nome_arquivo=None):
    fmt = achar_formato(doc, chave)
    if fmt is None:
        raise ErroValidar('formato não encontrado')
    arq = ler_arquivo(arquivo)
    itens = []
    dim = modelo.resolver(doc, fmt, 'dimensao')
    if not _valer(dim, contra) or not isinstance(dim['valor'], dict):
        itens.append(_item('dimensao', 'sem_regra', [arq['largura'], arq['altura']], None, 'sem_valor_confirmado', dim))
    elif arq['largura'] is None:
        itens.append(_item('dimensao', 'reprova', None, dim['valor'], 'dimensao_ilegivel', dim))
    else:
        esp = dim['valor']
        medida = [arq['largura'], arq['altura']]
        if (dim.get('unidade') or 'px') != 'px':
            itens.append(_item('dimensao', 'nao_verificado', medida, esp, 'unidade_fora_de_px', dim))
        elif medida == [esp['largura'], esp['altura']]:
            itens.append(_item('dimensao', 'ok', medida, esp, None, dim))
        elif medida == [esp['altura'], esp['largura']]:
            itens.append(_item('dimensao', 'reprova', medida, esp, 'girado', dim))
        else:
            itens.append(_item('dimensao', 'reprova', medida, esp, 'dimensao_diferente', dim))
    algum_peso = False
    for campo in PESOS:
        v = modelo.resolver(doc, fmt, campo) or fmt['campos'].get(campo)
        if _valer(v, contra) and isinstance(v['valor'], dict):
            algum_peso = True
            itens.append(conferir_peso(campo, v, arq['bytes'], condicao))
        elif v is not None and v.get('leituras'):
            algum_peso = True
            itens.append(_item(campo, 'aviso', arq['bytes'], [x['valor'] for x in v['leituras']],
                               'fontes_divergentes_o_da_decide', v))
    if not algum_peso:
        itens.append(_item('peso_max', 'sem_regra', arq['bytes'], None, 'sem_valor_confirmado'))
    tipos = modelo.resolver(doc, fmt, 'tipos_aceitos')
    if not _valer(tipos, contra):
        itens.append(_item('tipos_aceitos', 'sem_regra', arq['mime'], None, 'sem_valor_confirmado', tipos))
    elif arq['mime'] in tipos['valor']:
        itens.append(_item('tipos_aceitos', 'ok', arq['mime'], tipos['valor'], None, tipos))
    else:
        itens.append(_item('tipos_aceitos', 'reprova', arq['mime'], tipos['valor'], 'tipo_nao_aceito', tipos))
    orient = arq.pop('orientacao_exif')
    if orient is not None and orient != ORIENTACAO_NORMAL:
        # o visualizador gira a imagem pela tag: a dimensao do cabecalho pode nao ser a que aparece na tela
        itens.append(_item('orientacao_exif', 'aviso', orient, ORIENTACAO_NORMAL, 'imagem_com_giro_no_exif'))
    nome = (nome_arquivo or Path(arquivo).name).lower()
    if arq['mime'] in EXTENSOES and not nome.endswith(EXTENSOES[arq['mime']]):
        itens.append(_item('extensao', 'aviso', Path(nome).suffix, list(EXTENSOES[arq['mime']]), 'extensao_nao_bate_com_o_tipo'))
    for campo in CAMPOS_DE_PIXEL:
        v = modelo.resolver(doc, fmt, campo)
        if _valer(v, contra) and not (campo == 'faixas' and v['valor'] == []):
            itens.append(_item(campo, 'nao_verificado', None, v['valor'], 'conferido_no_pixel_na_entrega', v))
    situacoes = {i['situacao'] for i in itens}
    # sem regra confirmada para dimensao, peso ou tipo, o arquivo nunca sai aprovado: a validacao ficou incompleta
    incompleta = any(i['situacao'] == 'sem_regra' for i in itens if i['campo'] in ('dimensao', 'peso_max', 'tipos_aceitos'))
    resultado = 'reprovado' if 'reprova' in situacoes else ('aviso' if 'aviso' in situacoes or incompleta else 'aprovado')
    rel = {'esquema': ESQUEMA, 'arquivo': arq, 'formato': {'id': fmt['id'], 'chave': fmt.get('chave')},
           'contra': contra, 'condicao': condicao, 'resultado': resultado, 'verificacoes': itens}
    contratos.validar(rel, ESQUEMA)
    return rel
