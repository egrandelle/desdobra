# -*- coding: utf-8 -*-
"""Arquivo final de um formato: os bytes que vao para o veiculo (arquitetura-v1.md, 4.12 e 9.7; decisoes-v1.md, 136 a
140).

Interface que a aprovacao e o entregar usam:

    final = codificar.arquivo_final(pasta, formato)   # ArquivoFinal ou ErroCodificar

  - dados: os bytes do arquivo entregue, ja com tudo que muda pixel depois do master (qualidade de JPEG, achatamento da
    transparencia, rotacao e borda);
  - extensao: 'jpg' ou 'png';
  - parametros: tudo que decide os bytes (tipo, qualidade, subamostragem, progressivo, optimize, nivel do PNG, teto,
    rotacao, achatamento, borda, perfil, versoes do encoder). A aprovacao guarda o sha256 dos dados e estes parametros; mudar
    qualquer um derruba a aprovacao do formato;
  - medidas: o que foi medido na escolha (bytes de cada tentativa, se coube no teto, a sugestao de qualidade), para o
    relatorio e o roteamento da entrega. Nao entra na aprovacao: o sha256 dos dados ja cobre o resultado.

Regras (parametros aprovados no bloco do M6, com o limite de cada numero em fontes-de-limites.json):
  - teto estrito (nº 136): a leitura decimal do peso (alvo_bytes do valor confirmado em specs/formatos-do-job.json). Com
    teto condicional (hospedado, por tag) e sem a condicao escolhida pelo DA em parametros/entrega.json, vale o teto mais
    estrito de todos, com a regra condicao_nao_decidida (nº 137). O motor nunca escolhe a condicao;
  - PNG sem perda (nivel 9) quando a folha aceita PNG e ele cabe no teto; senao, JPEG baseline 4:4:4 com optimize (com o
    buffer de entrega.jpeg_buffer_bytes) e sem EXIF. A escolha fica em medidas;
  - busca da qualidade do JPEG entre entrega.jpeg_qualidade_min e entrega.jpeg_qualidade_max, sempre pelos bytes finais
    de cada tentativa: o peso nao cai sempre com a qualidade, entao a busca guarda como "cabe" so o que mediu e devolve
    uma qualidade que cabe com a seguinte acima sem caber (nunca supoe que o vizinho cabe). Quando nem a minima cabe, o
    arquivo sai na minima, marcado fora do teto (vai para reprovados na entrega);
  - sem perfil embutido (nº 140): o arquivo sai sem ICC. Com perfil pedido nos parametros de cor do job, recusa: o motor
    nao tem um perfil fixo conferido por hash (o gerado na hora grava a data e mudaria os bytes a cada execucao);
  - transparencia: master opaco nao muda. Master com transparencia recusa com cor_de_achatamento_nao_definida ate o DA
    definir a cor em parametros/entrega.json; com a cor, e achatado sobre ela. A v1 nao entrega alfa;
  - rotacao (nº 139): o master e a composicao (como o publico ve); o giro para o arquivo e uma transposicao sem perda, no
    sentido confirmado pelo DA nos 90 e 270 graus. Rotacao sem decisao ou sem o sentido recusa (desdobra.entrega.portao);
  - borda de 1 px (folha da Globo, valor condicional): so quando o DA declara a condicao do formato em
    parametros/entrega.json (borda_1px sim) e a folha confirmada tem o valor (espessura e cor). O anel e desenhado por
    cima dos pixels de fora do arquivo ja girado, sem encolher a arte. Sem a declaracao, nada e desenhado: o motor nao
    detecta sozinho se o fundo da peca e o da pagina.

Funcao deterministica: os mesmos arquivos do job dao os mesmos bytes, em toda execucao (sem carimbo de hora, sem
perfil gerado na hora, sem metadado herdado do master).
"""
import io
from dataclasses import dataclass, field
from pathlib import Path

from desdobra import arquivos, contratos, limites

DESCRICOES = {
    'formato_inexistente': 'O briefing não tem este formato.',
    'sem_master': 'O formato não tem render/<formato>/master.png: o render dele é um clique do DA na tela.',
    'master_ilegivel': 'O master.png do formato não abre como PNG.',
    'master_em_modo_inesperado': 'O master.png não é RGB nem RGBA de 8 bits.',
    'master_com_dimensao_errada': 'O master.png não tem a dimensão da composição do formato.',
    'formato_sem_spec_confirmada': 'O formato não está em specs/formatos-do-job.json (valores confirmados pelo DA): sem '
                                   'a folha confirmada, a entrega não sabe o tipo nem o teto.',
    'sem_tipos_aceitos_confirmados': 'A folha confirmada do formato não diz os tipos de arquivo aceitos.',
    'sem_tipo_com_encoder': 'A folha só aceita tipos que a v1 não entrega (a v1 entrega JPEG e PNG).',
    'teto_da_condicao_sem_valor': 'O DA escolheu a condição do teto, mas a folha confirmada não tem o teto dessa '
                                  'condição.',
    'perfil_embutido_sem_perfil_fixo': 'Os parâmetros de cor do job pedem perfil embutido no arquivo, e o motor não tem '
                                       'um perfil fixo conferido por hash (decisão 140): a entrega sai sem perfil.',
    'cor_de_achatamento_nao_definida': 'O master tem transparência e o DA não definiu a cor de achatamento em '
                                       'parametros/entrega.json: a v1 não entrega alfa.',
    'jpeg_buffer_insuficiente': 'O JPEG passou do buffer do encoder (entrega.jpeg_buffer_bytes).',
    'parametros_de_entrega_invalidos': 'parametros/entrega.json não segue o contrato parametros-entrega/1.',
    'parametros_de_cor_invalidos': 'parametros/cor.json não segue o contrato ds-parametros-cor/1.',
    'borda_sem_valor_confirmado': 'O DA declarou a borda de 1 px do formato, mas a folha confirmada não tem o valor da '
                                  'borda (espessura e cor).',
    'borda_com_valor_desconhecido': 'O valor confirmado da borda tem espessura ou cor que o motor não sabe desenhar.',
}
MIME_PNG, MIME_JPEG = 'image/png', 'image/jpeg'
SUBAMOSTRAGEM_PILLOW = {'4:4:4': 0}  # valor do subsampling do Pillow para cada subamostragem
# transposicao do Pillow (ROTATE_90 gira no sentido anti-horario) para cada (graus, sentido) do giro de entrega
TRANSPOSICAO = {(90, 'horario'): 'ROTATE_270', (90, 'anti_horario'): 'ROTATE_90',  # numero-neutro: graus do giro
                (270, 'horario'): 'ROTATE_90', (270, 'anti_horario'): 'ROTATE_270',  # numero-neutro: graus do giro
                (180, None): 'ROTATE_180'}  # numero-neutro: meia volta
MEIA_VOLTA = 180  # numero-neutro: graus da meia volta (o sentido nao importa)
OPACO = 255  # numero-neutro: alfa opaco em 8 bits
CORES_DA_BORDA = {'preta': '#000000'}  # numero-neutro: o nome da cor na folha e o hexadecimal dela


class ErroCodificar(Exception):
    """O arquivo final nao saiu. codigo: chave de DESCRICOES; medidas: o que foi medido."""

    def __init__(self, codigo, medidas=None):
        super().__init__(DESCRICOES.get(codigo, codigo))
        self.codigo, self.medidas = codigo, dict(medidas or {})


@dataclass(frozen=True)
class ArquivoFinal:
    dados: bytes = field(repr=False)
    extensao: str
    parametros: dict
    medidas: dict = field(default_factory=dict, compare=False)

    @property
    def sha256(self):
        return arquivos.sha256_bytes(self.dados)


# ------------------------------------------------------------------ teto estrito (nº 136 e 137)
def teto_estrito(spec, condicao=None):
    """{'alvo_bytes', 'campo', 'regra', 'condicao'} do teto que o arquivo tem de respeitar, ou None quando a folha
    confirmada nao tem peso. spec: o formato de specs/formatos-do-job.json; condicao: a escolhida pelo DA (None: nao
    decidida). ErroCodificar('teto_da_condicao_sem_valor') quando a condicao escolhida nao tem teto confirmado."""
    from desdobra.specs import validar
    candidatos = []
    for campo in validar.PESOS:
        v = (spec.get('campos') or {}).get(campo)
        if v is None or v.get('situacao') != 'confirmado' or not isinstance(v.get('valor'), dict):
            continue
        candidatos.append((int(v['valor']['alvo_bytes']), campo, v.get('condicao')))
    if not candidatos:
        return None
    condicionais = [c for c in candidatos if c[2] is not None]
    if condicao is None:
        valem, regra = candidatos, ('condicao_nao_decidida' if condicionais else 'leitura_decimal')
    else:
        valem = [c for c in candidatos if c[2] is None or c[2] == condicao]
        if condicionais and not any(c[2] == condicao for c in condicionais):
            raise ErroCodificar('teto_da_condicao_sem_valor', {'condicao': condicao})
        regra = 'leitura_decimal'
    alvo, campo, cond = min(valem)
    # a leitura decimal e o alvo_bytes do valor (a leitura estrita; 250 KB = 250.000 bytes)
    return {'alvo_bytes': alvo, 'campo': campo, 'regra': regra, 'condicao': condicao if condicao else cond,
            'leitura': limites.valor('entrega.peso_reprova_acima_da_leitura_decimal')}


# ------------------------------------------------------------------ pixels: achatamento e giro
def _rgb(img, cor_de_achatamento):
    """(imagem RGB nova, sem metadado herdado, achatamento). ErroCodificar sem a cor num master com transparencia."""
    from PIL import Image
    if img.mode not in ('RGB', 'RGBA'):
        raise ErroCodificar('master_em_modo_inesperado', {'modo': img.mode})
    achatamento = None
    if img.mode == 'RGBA':
        alfa_min, _alfa_max = img.getchannel('A').getextrema()
        if alfa_min < OPACO:
            if cor_de_achatamento is None:
                raise ErroCodificar('cor_de_achatamento_nao_definida', {'alfa_min': alfa_min})
            fundo = Image.new('RGBA', img.size, _cor(cor_de_achatamento) + (OPACO,))
            img = Image.alpha_composite(fundo, img)
            achatamento = {'cor': cor_de_achatamento}
    # imagem nova a partir dos bytes crus: nenhum info (icc_profile, exif, dpi) do master passa para o arquivo
    return Image.frombytes('RGB', img.size, img.convert('RGB').tobytes()), achatamento


def _sim(limite_id):
    return limites.valor(limite_id) == 'sim'


def _cor(hexa):
    return tuple(int(hexa[k:k + 2], 16) for k in (1, 3, 5))  # numero-neutro: posicoes de #rrggbb


def girar(img, graus, sentido):
    """A imagem girada para o arquivo, sem reamostrar (transposicao). graus 0: a mesma imagem."""
    from PIL import Image
    if not graus:
        return img
    chave = (graus, None) if graus == MEIA_VOLTA else (graus, sentido)
    if chave not in TRANSPOSICAO:
        raise ErroCodificar('rotacao_sem_sentido_confirmado', {'graus': graus})
    return img.transpose(getattr(Image.Transpose, TRANSPOSICAO[chave]))


def desenhar_borda(img, borda):
    """Uma copia da imagem com o anel da borda ({'espessura_px', 'cor'}) por cima dos pixels de fora. borda None: a
    mesma imagem."""
    if not borda:
        return img
    e, cor = int(borda['espessura_px']), _cor(borda['cor'])
    w, h = img.size
    saida = img.copy()
    for caixa in ((0, 0, w, e), (0, h - e, w, h), (0, 0, e, h), (w - e, 0, w, h)):
        saida.paste(cor, caixa)
    return saida


def borda_declarada(spec, parametros):
    """{'espessura_px', 'cor'} da borda do formato, ou None. So vale com a condicao declarada pelo DA (parametros do
    formato em parametros/entrega.json, borda_1px sim) e com o valor confirmado na folha. ErroCodificar quando o DA
    declarou e a folha nao tem um valor que o motor sabe desenhar."""
    if not ((parametros or {}).get('borda_1px') or {}).get('valor'):
        return None
    v = ((spec or {}).get('campos') or {}).get('borda_1px')
    if v is None or v.get('situacao') != 'confirmado' or not isinstance(v.get('valor'), dict):
        raise ErroCodificar('borda_sem_valor_confirmado')
    esp, cor = v['valor'].get('espessura_px'), CORES_DA_BORDA.get(v['valor'].get('cor'))
    if cor is None or not isinstance(esp, int) or isinstance(esp, bool) or esp < 1:
        raise ErroCodificar('borda_com_valor_desconhecido', {'espessura_px': esp, 'cor': v['valor'].get('cor')})
    return {'espessura_px': esp, 'cor': cor}


# ------------------------------------------------------------------ encoders
def _png(img):
    buf = io.BytesIO()
    img.save(buf, format='PNG', compress_level=int(limites.valor('entrega.png_nivel_compressao')))
    return buf.getvalue()


def _jpeg(img, qualidade, gravados=None):
    """Bytes do JPEG. gravados: os parametros de um ArquivoFinal (a conferencia da entrega codifica de novo com eles);
    sem eles, os do registro de limites."""
    from PIL import ImageFile
    g = gravados or {}
    buf = io.BytesIO()
    antes = ImageFile.MAXBLOCK
    ImageFile.MAXBLOCK = max(antes, int(g.get('buffer_bytes') or limites.valor('entrega.jpeg_buffer_bytes')))
    try:
        img.save(buf, format='JPEG', quality=int(qualidade),
                 subsampling=SUBAMOSTRAGEM_PILLOW[g.get('subamostragem') or limites.valor('entrega.jpeg_subamostragem')],
                 progressive=g['progressivo'] if 'progressivo' in g else _sim('entrega.jpeg_progressivo'),
                 optimize=g['optimize'] if 'optimize' in g else _sim('entrega.jpeg_optimize'))
    except OSError as e:
        raise ErroCodificar('jpeg_buffer_insuficiente', {'qualidade': int(qualidade), 'erro': type(e).__name__}) from None
    finally:
        ImageFile.MAXBLOCK = antes
    return buf.getvalue()


def buscar_qualidade(img, alvo_bytes):
    """(qualidade, bytes do JPEG, tentativas {qualidade: bytes}, cabe). Cada tentativa e medida nos bytes finais."""
    q_min = int(limites.valor('entrega.jpeg_qualidade_min'))
    q_max = int(limites.valor('entrega.jpeg_qualidade_max'))
    tentativas, feitos = {}, {}

    def medir(q):
        if q not in feitos:
            feitos[q] = _jpeg(img, q)
            tentativas[q] = len(feitos[q])
        return feitos[q]

    if alvo_bytes is None or len(medir(q_max)) <= alvo_bytes:
        return q_max, medir(q_max), tentativas, True
    if len(medir(q_min)) > alvo_bytes:
        return q_min, medir(q_min), tentativas, False
    # invariante: lo cabe e hi nao cabe, os dois medidos (nada e suposto entre eles)
    lo, hi = q_min, q_max
    while hi - lo > 1:
        meio = (lo + hi) // 2  # numero-neutro: metade do intervalo da busca binaria
        if len(medir(meio)) <= alvo_bytes:
            lo = meio
        else:
            hi = meio
    return lo, medir(lo), tentativas, True


def versoes():
    from PIL import Image, features
    return {'pillow': Image.__version__, 'libjpeg_turbo': features.version('libjpeg_turbo'),
            'zlib': features.version_codec('zlib')}


def build_de_referencia():
    """{biblioteca: versao} da build de referencia do encoder (entrega.encoder_build_referencia)."""
    return dict(x.split('=', 1) for x in limites.valor('entrega.encoder_build_referencia'))


def build_difere(atual=None):
    """Bibliotecas cuja versao nesta build (versoes()) nao e a da referencia."""
    atual = atual if atual is not None else versoes()
    return sorted(k for k, v in build_de_referencia().items() if atual.get(k) != v)


def _parametros_comuns(teto, graus, sentido, achatamento, borda):
    """Os parametros do encoder que nao dependem do tipo escolhido nem dos bytes (o teto, o giro, o achatamento, a borda,
    perfil, exif e as versoes)."""
    return {'teto': teto, 'rotacao': {'graus': int(graus or 0), 'sentido': sentido if graus and graus != MEIA_VOLTA else None},
            'achatamento': achatamento, 'borda': dict(borda) if borda else None, 'perfil_embutido': False, 'exif': False,
            'versoes': versoes()}


def _parametros_do_tipo(tipo):
    """Os parametros do encoder do tipo escolhido que vem dos limites do pacote e nao dependem dos bytes (o nivel do
    png; a subamostragem, o progressivo, o optimize e o buffer do jpg). A qualidade do jpg depende do master e fica de
    fora. {} para outro tipo."""
    if tipo == 'png':
        return {'nivel_png': int(limites.valor('entrega.png_nivel_compressao'))}
    if tipo == 'jpg':
        return {'subamostragem': limites.valor('entrega.jpeg_subamostragem'),
                'progressivo': _sim('entrega.jpeg_progressivo'), 'optimize': _sim('entrega.jpeg_optimize'),
                'buffer_bytes': int(limites.valor('entrega.jpeg_buffer_bytes'))}
    return {}


def codificar(img, *, tipos_aceitos, teto=None, graus=0, sentido=None, cor_de_achatamento=None, borda=None):
    """ArquivoFinal de uma imagem (o master aberto). tipos_aceitos: MIMEs da folha confirmada; teto: o de
    teto_estrito (None sem peso na folha); graus e sentido: o giro de entrega ja conferido; borda: a de
    borda_declarada (None sem a condicao declarada)."""
    if MIME_PNG not in tipos_aceitos and MIME_JPEG not in tipos_aceitos:
        raise ErroCodificar('sem_tipo_com_encoder', {'tipos_aceitos': sorted(tipos_aceitos)})
    rgb, achatamento = _rgb(img, cor_de_achatamento)
    rgb = desenhar_borda(girar(rgb, graus, sentido), borda)
    alvo = teto['alvo_bytes'] if teto else None
    comum = _parametros_comuns(teto, graus, sentido, achatamento, borda)
    medidas = {'largura': rgb.width, 'altura': rgb.height, 'alvo_bytes': alvo,
               'piso_qualidade': limites.obter('entrega.jpeg_qualidade_piso_aviso').citacao()}
    png = None
    if MIME_PNG in tipos_aceitos:
        png = _png(rgb)
        medidas['png_bytes'] = len(png)
        if alvo is None or len(png) <= alvo or MIME_JPEG not in tipos_aceitos:
            cabe = alvo is None or len(png) <= alvo
            medidas.update(escolha='png_sem_perda' if cabe else 'png_fora_do_teto_sem_jpeg_aceito', cabe_no_teto=cabe,
                           bytes=len(png))
            parametros = dict(comum, tipo='png', **_parametros_do_tipo('png'))
            return ArquivoFinal(dados=png, extensao='png', parametros=parametros, medidas=medidas)
    q, dados, tentativas, cabe = buscar_qualidade(rgb, alvo)
    piso = limites.obter('entrega.jpeg_qualidade_piso_aviso').valor
    medidas.update(escolha='jpeg' if png is None else 'jpeg_png_nao_cabe', cabe_no_teto=cabe, bytes=len(dados),
                   tentativas={str(k): v for k, v in sorted(tentativas.items())},
                   abaixo_do_piso_de_qualidade=(piso is not None and q < piso),
                   sugestao_qualidade=(q if cabe else None))
    parametros = dict(comum, tipo='jpg', qualidade=q, **_parametros_do_tipo('jpg'))
    return ArquivoFinal(dados=dados, extensao='jpg', parametros=parametros, medidas=medidas)


# ------------------------------------------------------------------ o formato do job
def spec_confirmada(pasta, chave):
    """O formato de specs/formatos-do-job.json (so valores confirmados pelo DA) pela chave, ou None."""
    from desdobra.briefing import modelo as mb
    arq = Path(pasta) / mb.ARQUIVO_FORMATOS
    if not chave or not arq.is_file():
        return None
    dados = arquivos.ler_json(arq)
    if dados.get('tipo') != 'formatos_do_job':
        return None
    return next((f for f in dados.get('formatos') or [] if f.get('chave') == chave), None)


def parametros_de_cor(pasta):
    """Os parametros de cor do job (desdobra.cor.Parametros), de parametros/cor.json ou do registro."""
    from desdobra import ds
    arq = Path(pasta) / ds.ARQUIVO_PARAMETROS
    try:
        dados = contratos.ler(arq, ds.ESQUEMA_PARAMETROS) if arq.is_file() else None
    except contratos.ErroContrato:
        raise ErroCodificar('parametros_de_cor_invalidos') from None
    return ds.parametros_do_job(dados)


def _entradas(pasta, formato, sentido=None):
    """O que decide o arquivo final do formato alem do master: {'fmt', 'params', 'sentido', 'tipos', 'teto', 'borda'}
    (o briefing, os parametros de entrega, a rotacao conferida, a cor do job e a folha confirmada). ErroCodificar."""
    from desdobra.briefing import modelo as mb
    from desdobra.entrega import portao
    b = mb.ler(pasta)
    fmt = next((f for f in (b or {}).get('formatos') or [] if f['id'] == formato), None)
    if fmt is None:
        raise ErroCodificar('formato_inexistente')
    try:
        params = portao.parametros_de_entrega(pasta).get(formato) or {}
    except contratos.ErroContrato:
        raise ErroCodificar('parametros_de_entrega_invalidos') from None
    if sentido is not None:
        params = dict(params, rotacao_sentido={'valor': sentido})
    falhas = portao.conferir_rotacao(fmt, params)
    if falhas:
        raise ErroCodificar(falhas[0]['codigo'], falhas[0].get('medidas'))
    if parametros_de_cor(pasta).perfil_embutido_na_saida:
        raise ErroCodificar('perfil_embutido_sem_perfil_fixo')
    spec = spec_confirmada(pasta, fmt.get('chave'))
    if spec is None:
        raise ErroCodificar('formato_sem_spec_confirmada')
    tipos = (spec.get('campos') or {}).get('tipos_aceitos')
    if tipos is None or tipos.get('situacao') != 'confirmado' or not tipos.get('valor'):
        raise ErroCodificar('sem_tipos_aceitos_confirmados')
    return {'fmt': fmt, 'params': params, 'sentido': (params.get('rotacao_sentido') or {}).get('valor'),
            'tipos': tipos, 'teto': teto_estrito(spec, (params.get('condicao') or {}).get('valor')),
            'borda': borda_declarada(spec, params)}


def parametros_sem_o_master(pasta, formato, achatado, tipo=None):
    """Os parametros do encoder que o arquivo final do formato teria agora e que nao dependem dos bytes do master (o
    teto, o giro, o achatamento, a borda, perfil, exif e as versoes e, com o tipo aprovado, os do tipo que vem dos
    limites do pacote), sem abrir o master nem codificar: o painel da tela os compara com os da aprovacao
    (desdobra.entrega.nucleo_aprovar.situacao; revisao do M7b, fase B). achatado: o master aprovado foi achatado (tem
    transparencia); com o mesmo master, so a cor de agora decide o achatamento. tipo: o tipo do arquivo aprovado (png ou
    jpg; a escolha depende dos bytes e fica de fora). ErroCodificar quando o arquivo final nao sai (o portao recusa com o
    mesmo codigo)."""
    e = _entradas(Path(pasta).resolve(), formato)
    achatamento = None
    if achatado:
        cor = (e['params'].get('cor_de_achatamento') or {}).get('valor')
        if cor is None:
            raise ErroCodificar('cor_de_achatamento_nao_definida')
        achatamento = {'cor': cor}
    return dict(_parametros_comuns(e['teto'], e['fmt']['rotacao']['graus'], e['sentido'], achatamento, e['borda']),
                **_parametros_do_tipo(tipo))


def arquivo_final(pasta, formato, sentido=None):
    """ArquivoFinal do formato, a partir de render/<formato>/master.png, do briefing, das specs confirmadas e dos
    parametros do job. ErroCodificar quando nao sai. sentido: o sentido do giro que o DA escolheu na janela de aprovar
    da tela e que ainda nao esta em parametros/entrega.json (M7b, B4: a janela mostra o arquivo ja girado; a mesma
    confirmacao grava o sentido e a aprovacao). Quem chama confere antes que o formato pede o sentido e nao tem um."""
    from PIL import Image
    from desdobra.derivacao import formatos as mod_formatos
    pasta = Path(pasta).resolve()
    e = _entradas(pasta, formato, sentido)
    fmt, tipos, teto, borda, params = e['fmt'], e['tipos'], e['teto'], e['borda'], e['params']
    rot, sentido = fmt['rotacao'], e['sentido']
    arq = pasta / 'render' / formato / 'master.png'
    if not arq.is_file():
        raise ErroCodificar('sem_master')
    try:
        with Image.open(io.BytesIO(arq.read_bytes())) as img:
            if img.format != 'PNG':
                raise ErroCodificar('master_ilegivel')
            img.load()
            master = img.copy()
    except (OSError, ValueError):
        raise ErroCodificar('master_ilegivel') from None
    esperado = list(mod_formatos.composicao(fmt))
    if [master.width, master.height] != esperado:
        raise ErroCodificar('master_com_dimensao_errada', {'medida': [master.width, master.height], 'esperado': esperado})
    final = codificar(master, tipos_aceitos=list(tipos['valor']), teto=teto, graus=rot['graus'], sentido=sentido,
                      cor_de_achatamento=(params.get('cor_de_achatamento') or {}).get('valor'), borda=borda)
    return final
