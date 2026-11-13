# -*- coding: utf-8 -*-
"""Validacao final da entrega e roteamento para entrega/aprovados e entrega/reprovados (M6, fatias 4 e 6 da proposta;
arquitetura-v1.md, 5.9 e 9.7; decisoes-v1.md, 136, 137, 140, 141, 142 e 143).

validar(final, nome, ctx) confere o arquivo final de um formato (desdobra.entrega.codificar) antes de ele ir para o
veiculo. Cada verificacao tem nome, situacao (ok, reprova, avisa ou registra), regra (o codigo, quando nao passa), fonte
e medidas:
  - peso: os bytes contra o teto estrito da folha confirmada (leitura decimal, nº 136); sem a condicao escolhida pelo DA,
    o teto mais estrito, com a regra condicao_nao_decidida (nº 137). Sem peso confirmado, reprova: a entrega nao confere
    teto que nao existe;
  - dimensao: a do cabecalho contra a do formato no briefing e a da folha confirmada;
  - tipo: o MIME pela assinatura contra os tipos aceitos confirmados, e a extensao do nome contra o MIME;
  - alfa e perfil: o arquivo decodificado e RGB, sem transparencia e sem perfil embutido (nº 140);
  - caminho de cor (conferencia sRGB): os parametros de cor do render (render.json) e a conversao que ele fez sao os
    do job agora, e o job nao pede perfil embutido (nº 140);
  - parametros do arquivo: a rotacao, o achatamento e a borda gravados pelo encoder sao os que o briefing e o DA
    decidiram agora (parametros/entrega.json);
  - arquivo do master (conferencia sRGB): o arquivo e transformar(master) com os parametros gravados (achatamento, giro
    e borda). PNG: os pixels decodificados sao exatamente os esperados. JPEG: codificar de novo, com os parametros
    gravados, da os mesmos bytes;
  - borda de 1 px: so com a condicao declarada pelo DA para o formato; o anel do arquivo e exatamente a cor da folha (no
    JPEG, conferido nos pixels antes do encoder, que o reencode liga ao arquivo);
  - area segura, area util e faixas: a tinta medida de cada texto (render.json) e a caixa do logo no layout
    (derivacao/<formato>.json, a unica caixa de logo que o motor tem: fica registrado) ficam inteiras dentro da area
    segura e da area util e fora das faixas, com entrega.tolerancia_area_px (0 px, nº 141);
  - so registro ou aviso, sem mudar o roteamento: a escolha entre PNG e JPEG, a qualidade do JPEG contra o piso de aviso
    (a calibrar) e a comparacao com a peca aprovada, que ainda nao existe no motor.
Arquivo com alguma verificacao que reprova vai para entrega/reprovados, com a regra e a sugestao; os outros vao para
entrega/aprovados (destino()). O formato que o encoder recusou por decisao ou folha que falta (RECUSAS_ROTEADAS) entra
no relatorio em reprovados com a regra e a sugestao, sem arquivo (item_sem_arquivo; sha256 nulo). Dois formatos com o
mesmo nome de arquivo (casefold) saem com o id do formato, com aviso (nomes_dos_arquivos).

invalidar() tira a entrega atual de cena quando uma entrada do job muda: ela vai inteira para
entrega/anteriores/<carimbo>-invalidada/, nunca e apagada.

gravar() monta a entrega inteira numa pasta temporaria dentro de entrega/ (os arquivos e o relatorio-entrega.json),
confere essa pasta como o conferir-entrega confere (hashes, roteamento e nenhum arquivo de fonte, nº 143) e troca: a
entrega anterior vai para entrega/anteriores/<carimbo>/ (o relatorio primeiro, entao ela deixa de valer antes de sair) e
a nova entra (o relatorio por ultimo, e ele que fecha a troca). Cada passo e um os.replace; se um falha, os passos feitos
voltam. Depois da troca, o manifesto-licenca.json fecha na raiz do job (desdobra.entrega.relatorio), e o relatorio guarda
o selo dele. entrega/previa/ (a aprovacao) e entrega/anteriores/ ficam fora da troca. So grava com o Disparo do "entregar"
(desdobra.humano) e com a trava do job (quem chama e o "desdobra entregar").

conferir_entrega() so le (nunca grava, nem a trava do job): confere o relatorio pelo selo, cada arquivo listado pelo
sha256 e pelos bytes, que nada sobra em aprovados/ e reprovados/, que nenhum arquivo com verificacao que reprova esta em
aprovados/ e que nao ha arquivo de fonte em entrega/; conferir_entrega() tambem confere o manifesto da raiz do job
contra o selo do relatorio.
"""
import hashlib
import io
import json
import os
import re
from datetime import datetime
from pathlib import Path

from desdobra import arquivos, contratos, humano, limites
from desdobra.entrega import codificar
from desdobra.entrega import relatorio as mod_relatorio

ESQUEMA = 'relatorio-entrega/1'
PASTA_ENTREGA = Path('entrega')
PASTA_ANTERIORES = 'anteriores'
ARQUIVO_RELATORIO = 'relatorio-entrega.json'
APROVADOS, REPROVADOS = 'aprovados', 'reprovados'
# a entrega velha sai nesta ordem (o relatorio primeiro); a nova entra na ordem inversa (o relatorio por ultimo)
ITENS_DA_ENTREGA = (ARQUIVO_RELATORIO, APROVADOS, REPROVADOS)
SUFIXO_VALIDO = re.compile(r'^[A-Za-z0-9._-]*$')
CARIMBO = re.compile(r'^[0-9]{8}T[0-9]{6}[+-][0-9]{4}$')
CAMPOS_DE_COR = ('intent', 'compensacao_ponto_preto', 'perfil_embutido_na_saida')
CAMPOS_DA_CONVERSAO = ('intent', 'compensacao_ponto_preto')

FONTE_140 = {'tipo': 'decisao', 'arquivo': 'decisoes-v1.md', 'secao': '04/11/2026: decisões do M6, 140'}
FONTE_COR = {'tipo': 'arquitetura', 'arquivo': 'arquitetura-v1.md', 'secao': '4.6 e 9.7 (saída sRGB conferida)'}
FONTE_DECISOES = {'tipo': 'parametro_do_job', 'arquivo': 'parametros/entrega.json',
                  'secao': 'decisoes-v1.md, 04/11/2026: decisões do M6, 138 e 139'}
FONTE_FOLHA = {'tipo': 'folha', 'arquivo': 'specs/formatos-do-job.json'}
FONTE_BORDA = {'tipo': 'folha', 'arquivo': 'specs/formatos-do-job.json', 'campo': 'borda_1px',
               'condicao': 'declarada pelo DA em parametros/entrega.json'}

DESCRICOES = {
    'formato_sem_spec_confirmada': codificar.DESCRICOES['formato_sem_spec_confirmada'],
    'peso_sem_valor_confirmado': 'A folha confirmada não tem o peso do formato: a entrega não confere um teto que não '
                                 'existe.',
    'acima_do_teto_estrito': 'O arquivo passou do teto estrito da folha (leitura decimal, decisão 136).',
    'condicao_nao_decidida': 'O teto depende da condição (hospedado ou por tag), o DA não escolheu a condição, e o '
                             'arquivo passou do teto mais estrito (decisão 137).',
    'dimensao_ilegivel': 'O cabeçalho do arquivo não diz a dimensão.',
    'dimensao_diferente': 'O arquivo não tem a dimensão do formato.',
    'girado': 'O arquivo tem a dimensão do formato trocada (largura e altura).',
    'tipo_nao_aceito': 'O tipo do arquivo (pela assinatura) não está nos tipos aceitos da folha confirmada.',
    'extensao_nao_bate_com_o_tipo': 'A extensão do nome do arquivo não é a do tipo dele.',
    'arquivo_ilegivel': 'O arquivo não abre como imagem.',
    'arquivo_com_alfa': 'O arquivo tem transparência: a v1 não entrega alfa.',
    'modo_de_cor_inesperado': 'O arquivo não é RGB de 8 bits.',
    'perfil_embutido_no_arquivo': 'O arquivo tem perfil de cor embutido, e a entrega sai sem perfil (decisão 140).',
    'job_pede_perfil_embutido': 'Os parâmetros de cor do job pedem perfil embutido, e a entrega sai sem perfil '
                                '(decisão 140).',
    'master_com_perfil_embutido': 'O master tem perfil embutido, e o job pede saída sem perfil.',
    'conversao_cor_diferente_do_job': 'O render usou parâmetros de cor (intent, ponto preto ou perfil) que não são os '
                                      'do job agora.',
    'parametros_diferentes_das_decisoes': 'O encoder gravou rotação, achatamento, borda ou perfil diferentes do que o '
                                          'briefing e o DA decidiram agora.',
    'transformacao_impossivel': 'O master não passa pela transformação gravada (achatamento, giro e borda).',
    'pixels_diferentes_do_master': 'Os pixels do arquivo não são o master transformado (achatamento, giro e borda).',
    'bytes_diferentes_do_reencode': 'Codificar o master de novo, com os parâmetros gravados, não dá os bytes do arquivo.',
    'tipo_do_encoder_desconhecido': 'Os parâmetros do encoder não dizem se o arquivo é JPEG ou PNG.',
    'borda_ausente': 'A borda que o DA declarou para o formato não está no arquivo (anel com a cor da folha).',
    'borda_nao_conferida': 'O arquivo não liga aos pixels esperados, e a borda não pôde ser conferida.',
    'borda_sem_condicao_declarada': 'A folha tem borda condicional e o DA não declarou a condição do formato: nada foi '
                                    'desenhado (o motor não detecta sozinho o fundo da página).',
    'fora_da_area_segura': 'Texto (tinta medida) ou logo (caixa do layout) entra na área segura da folha.',
    'fora_da_area_util': 'Texto (tinta medida) ou logo (caixa do layout) sai da área útil da folha.',
    'dentro_da_faixa': 'Texto (tinta medida) ou logo (caixa do layout) entra numa faixa reservada da folha.',
    'logo_pela_caixa_do_layout': 'O logo é conferido pela caixa dele no layout: o motor não tem a caixa do logo no '
                                 'pixel.',
    'logo_sem_caixa_de_layout': 'O formato não tem derivação: o logo não tem caixa de layout para conferir.',
    'png_sem_perda': 'O arquivo saiu em PNG sem perda: a folha aceita PNG e ele cabe no teto estrito.',
    'jpeg': 'O arquivo saiu em JPEG: a folha não aceita PNG.',
    'jpeg_png_nao_cabe': 'O arquivo saiu em JPEG: o PNG sem perda não cabe no teto estrito.',
    'png_fora_do_teto_sem_jpeg_aceito': 'O arquivo saiu em PNG fora do teto: a folha não aceita JPEG.',
    'qualidade_abaixo_do_piso': 'A qualidade do JPEG ficou abaixo do piso de aviso (entrega.jpeg_qualidade_piso_aviso): '
                                'confira o arquivo antes de entregar.',
    'piso_de_qualidade_a_calibrar': 'O piso de aviso da qualidade do JPEG ainda não tem valor: a qualidade escolhida fica '
                                    'só como registro.',
    'comparacao_com_aprovada_pendente': 'A comparação com a peça aprovada pela tolerância de borda por camada ainda não '
                                        'existe no motor: fica só como registro.',
    'sufixo_nome_arquivo_invalido': 'O sufixo do nome confirmado na folha tem caractere que não vai em nome de arquivo: '
                                    'o arquivo sai com o id do formato.',
    'nome_de_arquivo_repetido': 'Com o sufixo da folha, o nome do arquivo seria o de outro formato (no Windows, a caixa '
                                'não distingue): o arquivo sai com o id do formato.',
}
SUGESTOES = {
    'formato_sem_spec_confirmada': 'O DA confirma a folha do formato na tela do desdobra e aprova o formato '
                                   'de novo.',
    'peso_sem_valor_confirmado': 'O DA confirma o peso do formato na folha, na tela do desdobra, e aprova o '
                                 'formato de novo.',
    'teto_da_condicao_sem_valor': 'Confirme o teto da condição na folha ou escolha outra condição.',
    'acima_do_teto_estrito': 'Simplifique a arte do formato (menos ruído e degradê) ou confirme com o veículo um teto '
                             'maior; as medidas dizem a qualidade e os bytes de cada tentativa.',
    'condicao_nao_decidida': 'Escolha a condição do teto do formato (hospedado ou por tag) em parametros/entrega.json, '
                             'que é decisão do DA; o botão dela chega no próximo marco do desdobra.',
    'cor_de_achatamento_nao_definida': 'A cor de achatamento do formato, em parametros/entrega.json, é decisão '
                                       'do DA; o botão dela chega no próximo marco do desdobra.',
    'borda_ausente': 'O DA aprova o formato de novo na tela: o arquivo final desenha a borda declarada.',
    'parametros_diferentes_das_decisoes': 'O DA aprova o formato de novo na tela, com as decisões de agora.',
    'conversao_cor_diferente_do_job': 'O DA renderiza o formato de novo na tela, com os parâmetros de cor do '
                                      'job.',
    'job_pede_perfil_embutido': 'Tire o perfil embutido dos parâmetros de cor do job (decisão 140).',
    'fora_da_area_segura': 'O DA ajusta o briefing do formato na tela para tirar texto e logo da área segura (o '
                           '"Salvar e seguir" deriva de novo) e renderiza o formato de novo.',
    'fora_da_area_util': 'O DA ajusta o briefing do formato na tela para trazer texto e logo para a área útil (o '
                         '"Salvar e seguir" deriva de novo) e renderiza o formato de novo.',
    'dentro_da_faixa': 'O DA ajusta o briefing do formato na tela para tirar texto e logo da faixa (o "Salvar e '
                       'seguir" deriva de novo) e renderiza o formato de novo.',
}
SUGESTAO_PADRAO = ('O DA renderiza e aprova o formato de novo, com cliques na tela do desdobra; se repetir, é bug '
                   'do motor.')
# recusas do encoder que sao decisao ou folha que faltam no formato (nao arquivo velho ou trocado): na entrega, o formato
# vai para reprovados com a regra e a sugestao, sem arquivo, e os outros formatos seguem (bloco de parametros do M6:
# "master com transparencia vai para reprovados ate o DA definir a cor de achatamento"). No aprovar, recusam.
RECUSAS_ROTEADAS = ('cor_de_achatamento_nao_definida', 'teto_da_condicao_sem_valor', 'borda_sem_valor_confirmado',
                    'borda_com_valor_desconhecido', 'formato_sem_spec_confirmada', 'sem_tipos_aceitos_confirmados',
                    'sem_tipo_com_encoder')
SUGESTOES.update({
    'borda_sem_valor_confirmado': 'O DA confirma o valor da borda na folha, na tela do desdobra, ou tira a '
                                  'declaração da borda do formato em parametros/entrega.json (o botão dessa decisão '
                                  'chega no próximo marco do desdobra).',
    'borda_com_valor_desconhecido': 'Confira o valor da borda na folha: a v1 desenha a borda preta de espessura inteira.',
    'sem_tipos_aceitos_confirmados': 'O DA confirma os tipos de arquivo aceitos na folha, na tela do '
                                     'desdobra.',
    'sem_tipo_com_encoder': 'A folha só aceita tipos que a v1 não entrega: confirme com o veículo JPEG ou PNG.',
})
FONTE_ENCODER = {'tipo': 'decisao', 'arquivo': 'decisoes-v1.md',
                 'secao': '04/11/2026: decisões do M6, bloco de parâmetros (transparência, teto e borda)'}
SUFIXO_INVALIDADA = '-invalidada'


class ErroEntrega(Exception):
    """A entrega montada nao confere. codigo: texto fixo; medidas: o resultado da conferencia."""

    def __init__(self, codigo, medidas=None):
        super().__init__(codigo)
        self.codigo, self.medidas = codigo, dict(medidas or {})


def _item(nome, regra, fonte, situacao=None, **medidas):
    """Uma verificacao. regra None: passou. situacao: a do limite (efeito efetivo); sem ela, reprova."""
    it = {'nome': nome, 'situacao': 'ok' if regra is None else (situacao or 'reprova'), 'regra': regra, 'fonte': fonte}
    if regra is not None:
        it['descricao'] = DESCRICOES.get(regra) or codificar.DESCRICOES.get(regra, regra)
        if it['situacao'] == 'reprova':
            it['sugestao'] = SUGESTOES.get(regra, SUGESTAO_PADRAO)
    if medidas:
        it['medidas'] = medidas
    return it


def _normal(dados):
    return json.loads(json.dumps(dados, sort_keys=True))


def _campo(spec, nome):
    v = ((spec or {}).get('campos') or {}).get(nome)
    return v if v is not None and v.get('situacao') == 'confirmado' and v.get('valor') is not None else None


def destino(verificacoes):
    """aprovados ou reprovados: um reprova manda o arquivo para reprovados."""
    return REPROVADOS if any(v['situacao'] == 'reprova' for v in verificacoes) else APROVADOS


# ------------------------------------------------------------------ contexto do formato
def contexto(pasta, formato):
    """O que a validacao le do job para o formato: o do briefing, a folha confirmada, os parametros de entrega do
    formato, o master aberto, o render.json, os parametros de cor do job e a derivacao (None sem ela)."""
    from PIL import Image
    from desdobra.briefing import modelo as mb
    from desdobra.derivacao import nucleo as nd
    from desdobra.entrega import portao
    from desdobra.render import execucao
    pasta = Path(pasta).resolve()
    fmt = next(f for f in mb.ler(pasta)['formatos'] if f['id'] == formato)
    base = pasta / 'render' / formato
    with Image.open(io.BytesIO((base / 'master.png').read_bytes())) as img:
        img.load()
        master = img.copy()
    arq_der = pasta / nd.PASTA / ('%s.json' % formato)
    return {'formato': fmt, 'spec': codificar.spec_confirmada(pasta, fmt.get('chave')),
            'parametros': portao.parametros_de_entrega(pasta).get(formato) or {}, 'master': master,
            'render': contratos.ler(base / 'render.json', execucao.ESQUEMA_RENDER),
            'cor': codificar.parametros_de_cor(pasta),
            'derivacao': contratos.ler(arq_der, nd.ESQUEMA) if arq_der.is_file() else None,
            'arquivo_specs': mb.ARQUIVO_FORMATOS.as_posix()}


def nome_do_arquivo(formato, spec, extensao):
    """(nome, verificacao ou None): o id do formato, o sufixo literal confirmado na folha e a extensao."""
    v = _campo(spec, 'sufixo_nome_arquivo')
    sufixo = v['valor'] if v is not None and isinstance(v['valor'], str) else ''
    if not SUFIXO_VALIDO.match(sufixo):
        return '%s.%s' % (formato, extensao), _item('nome_do_arquivo', 'sufixo_nome_arquivo_invalido', FONTE_FOLHA,
                                                    situacao='avisa')
    return '%s%s.%s' % (formato, sufixo, extensao), None


def nomes_dos_arquivos(pedidos):
    """[(nome, verificacao ou None)] de [(formato, spec, extensao)], na mesma ordem (nome_do_arquivo). Nomes que
    colidem (comparados com casefold: no Windows a caixa nao distingue) caem para o id do formato, com o aviso
    nome_de_arquivo_repetido; os ids sao unicos, entao a troca termina."""
    saida = [nome_do_arquivo(f, s, e) for f, s, e in pedidos]
    while True:
        por_nome = {}
        for k, (nome, _x) in enumerate(saida):
            por_nome.setdefault(nome.casefold(), []).append(k)
        repetidos = [k for ks in por_nome.values() if len(ks) > 1 for k in ks
                     if saida[k][0] != '%s.%s' % (pedidos[k][0], pedidos[k][2])]
        if not repetidos:
            return saida
        for k in repetidos:
            formato, _spec, extensao = pedidos[k]
            saida[k] = ('%s.%s' % (formato, extensao),
                        _item('nome_do_arquivo', 'nome_de_arquivo_repetido', FONTE_FOLHA, situacao='avisa'))


# ------------------------------------------------------------------ verificacoes
def _peso(n_bytes, spec, params, final):
    lim = limites.obter('entrega.peso_reprova_acima_da_leitura_decimal')
    fonte = {'tipo': 'limite', 'limite': lim.citacao(), 'folha': FONTE_FOLHA}
    if spec is None:
        return _item('peso', 'peso_sem_valor_confirmado', fonte, bytes=n_bytes)
    try:
        teto = codificar.teto_estrito(spec, (params.get('condicao') or {}).get('valor'))
    except codificar.ErroCodificar as e:
        return _item('peso', e.codigo, fonte, bytes=n_bytes, **e.medidas)
    if teto is None:
        return _item('peso', 'peso_sem_valor_confirmado', fonte, bytes=n_bytes)
    medidas = {'bytes': n_bytes, 'alvo_bytes': teto['alvo_bytes'], 'campo': teto['campo'], 'condicao': teto['condicao'],
               'qualidade': final.parametros.get('qualidade'), 'escolha': final.medidas.get('escolha'),
               'sugestao_qualidade': final.medidas.get('sugestao_qualidade')}
    if n_bytes <= teto['alvo_bytes']:
        return _item('peso', None, fonte, **medidas)
    regra = 'condicao_nao_decidida' if teto['regra'] == 'condicao_nao_decidida' else 'acima_do_teto_estrito'
    return _item('peso', regra, fonte, situacao=lim.efeito_efetivo, **medidas)


def _escolha_e_qualidade(final):
    """A escolha entre PNG e JPEG (so registra) e, no JPEG, a qualidade contra o piso de aviso (a calibrar: so avisa)."""
    m, p = final.medidas, final.parametros
    nivel = limites.obter('entrega.png_nivel_compressao')
    itens = [_item('escolha_do_tipo', m.get('escolha') or 'escolha_desconhecida',
                   {'tipo': 'limite', 'limite': nivel.citacao(), 'regra': 'proposta-m6, seção 3 (format choice)'},
                   situacao='registra', tipo=p.get('tipo'), png_bytes=m.get('png_bytes'), alvo_bytes=m.get('alvo_bytes'))]
    if p.get('tipo') == 'jpg':
        piso = limites.obter('entrega.jpeg_qualidade_piso_aviso')
        fonte = {'tipo': 'limite', 'limite': piso.citacao(),
                 'busca': [limites.obter('entrega.jpeg_qualidade_min').citacao(),
                           limites.obter('entrega.jpeg_qualidade_max').citacao()]}
        q = p.get('qualidade')
        if piso.valor is None:
            itens.append(_item('qualidade_jpeg', 'piso_de_qualidade_a_calibrar', fonte, situacao='registra', qualidade=q))
        else:
            itens.append(_item('qualidade_jpeg', 'qualidade_abaixo_do_piso' if q < piso.valor else None, fonte,
                               situacao=piso.efeito_efetivo, qualidade=q, piso=piso.valor))
    return itens


def _dimensao(largura, altura, fmt, spec):
    esperado = [int(fmt['largura']), int(fmt['altura'])]
    dim = _campo(spec, 'dimensao')
    folha = [dim['valor'].get('largura'), dim['valor'].get('altura')] if dim and isinstance(dim['valor'], dict) else None
    fonte = {'tipo': 'briefing', 'campo': 'formatos[].largura e altura', 'folha': FONTE_FOLHA}
    medida = [largura, altura]
    if largura is None:
        return _item('dimensao', 'dimensao_ilegivel', fonte)
    if medida == esperado and folha in (None, esperado):
        return _item('dimensao', None, fonte, medida=medida, esperado=esperado)
    regra = 'girado' if medida == esperado[::-1] else 'dimensao_diferente'
    return _item('dimensao', regra, fonte, medida=medida, esperado=esperado, folha=folha)


def _tipo(mime, nome, spec):
    from desdobra.specs import validar as vs
    tipos = _campo(spec, 'tipos_aceitos')
    fonte = dict(FONTE_FOLHA, campo='tipos_aceitos')
    if tipos is None:
        itens = [_item('tipo', 'sem_tipos_aceitos_confirmados', fonte, medida=mime)]
    else:
        itens = [_item('tipo', None if mime in tipos['valor'] else 'tipo_nao_aceito', fonte, medida=mime,
                       esperado=list(tipos['valor']))]
    ok = mime in vs.EXTENSOES and nome.lower().endswith(vs.EXTENSOES[mime])
    itens.append(_item('extensao', None if ok else 'extensao_nao_bate_com_o_tipo', fonte, medida=Path(nome).suffix))
    return itens


def _alfa_e_perfil(img):
    if img is None:
        return [_item('decodificacao', 'arquivo_ilegivel', FONTE_COR)]
    com_alfa = 'A' in img.getbands() or 'transparency' in img.info
    regra = 'arquivo_com_alfa' if com_alfa else (None if img.mode == 'RGB' else 'modo_de_cor_inesperado')
    return [_item('alfa', regra, FONTE_COR, modo=img.mode),
            _item('perfil_do_arquivo', 'perfil_embutido_no_arquivo' if img.info.get('icc_profile') else None, FONTE_140)]


def _caminho_de_cor(ctx):
    par, rr = ctx['cor'], ctx['render']
    itens = [_item('perfil_do_job', 'job_pede_perfil_embutido' if par.perfil_embutido_na_saida else None, FONTE_140)]
    gravado = (rr.get('parametros') or {}).get('cor') or {}
    campos = [c for c in CAMPOS_DE_COR if (gravado.get(c) or {}).get('valor') != getattr(par, c)]
    conv = rr.get('conversao_cor')
    if not isinstance(conv, dict):
        campos.append('conversao_cor')
    elif conv.get('feita'):
        campos += ['conversao_cor.%s' % c for c in CAMPOS_DA_CONVERSAO if conv.get(c) != getattr(par, c)]
    feita = isinstance(conv, dict) and bool(conv.get('feita'))
    itens.append(_item('caminho_de_cor', 'conversao_cor_diferente_do_job' if campos else None, FONTE_COR, campos=campos,
                       conversao='feita' if feita else (conv or {}).get('motivo'), intent=par.intent))
    com_perfil = bool(ctx['master'].info.get('icc_profile'))
    itens.append(_item('perfil_do_master', 'master_com_perfil_embutido' if com_perfil and not par.perfil_embutido_na_saida
                       else None, FONTE_140))
    return itens


def _decisoes(final, ctx):
    """Os parametros que o encoder gravou contra o que o briefing e o DA decidiram agora. Devolve (itens, borda de
    agora ou None)."""
    from desdobra.entrega import portao
    fmt, params, p = ctx['formato'], ctx['parametros'], final.parametros
    graus = int(((fmt.get('rotacao') or {}).get('graus')) or 0)
    sentido = (params.get('rotacao_sentido') or {}).get('valor') if graus in portao.GRAUS_QUARTO_DE_VOLTA else None
    esperados = {'rotacao': {'graus': graus, 'sentido': sentido}, 'perfil_embutido': False}
    master = ctx['master']
    if master.mode == 'RGBA' and master.getchannel('A').getextrema()[0] < codificar.OPACO:
        cor = (params.get('cor_de_achatamento') or {}).get('valor')
        esperados['achatamento'] = {'cor': cor} if cor else 'cor_de_achatamento_nao_definida'
    else:
        esperados['achatamento'] = None
    itens, borda = [], None
    try:
        borda = codificar.borda_declarada(ctx['spec'], params)
        esperados['borda'] = borda
    except codificar.ErroCodificar as e:
        itens.append(_item('borda_1px', e.codigo, FONTE_BORDA, **e.medidas))
    campos = sorted(k for k, v in esperados.items() if _normal(p.get(k)) != _normal(v))
    itens.append(_item('parametros_do_arquivo', 'parametros_diferentes_das_decisoes' if campos else None, FONTE_DECISOES,
                       campos=campos))
    return itens, borda


def transformar(master, parametros):
    """O master como vai para o encoder, pelos parametros gravados: achatamento, giro e borda. ErroCodificar quando
    nao passa."""
    rgb, _achatamento = codificar._rgb(master, (parametros.get('achatamento') or {}).get('cor'))
    rot = parametros.get('rotacao') or {}
    return codificar.desenhar_borda(codificar.girar(rgb, rot.get('graus') or 0, rot.get('sentido')),
                                    parametros.get('borda'))


def _arquivo_do_master(final, img, ctx):
    """(itens, pixels que o arquivo prova ter ou None): o arquivo e transformar(master)?"""
    p = final.parametros
    try:
        esperado = transformar(ctx['master'], p)
    except (codificar.ErroCodificar, KeyError, TypeError) as e:
        return [_item('arquivo_do_master', 'transformacao_impossivel', FONTE_COR,
                      motivo=getattr(e, 'codigo', type(e).__name__))], None
    if p.get('tipo') == 'png':
        ok = img is not None and img.mode == 'RGB' and img.size == esperado.size and img.tobytes() == esperado.tobytes()
        return [_item('arquivo_do_master', None if ok else 'pixels_diferentes_do_master', FONTE_COR,
                      comparacao='pixels_exatos')], (img if ok else None)
    if p.get('tipo') == 'jpg':
        try:
            refeito = codificar._jpeg(esperado, p['qualidade'], gravados=p)
        except (codificar.ErroCodificar, KeyError, TypeError, ValueError):
            refeito = None
        ok = refeito == final.dados
        return [_item('arquivo_do_master', None if ok else 'bytes_diferentes_do_reencode', FONTE_COR,
                      comparacao='bytes_do_reencode', versoes_iguais=p.get('versoes') == codificar.versoes())], \
            (esperado if ok else None)
    return [_item('arquivo_do_master', 'tipo_do_encoder_desconhecido', FONTE_COR)], None


def tem_borda(img, borda):
    """O anel de fora da imagem e exatamente a cor da borda?"""
    import numpy as np
    a = np.asarray(img.convert('RGB'))
    e, cor = int(borda['espessura_px']), np.asarray(codificar._cor(borda['cor']), np.uint8)
    return all(bool((faixa == cor).all()) for faixa in (a[:e], a[-e:], a[:, :e], a[:, -e:]))


def _borda(borda, provado, ctx):
    if borda is None:
        if _campo(ctx['spec'], 'borda_1px') is not None:
            return [_item('borda_1px', 'borda_sem_condicao_declarada', FONTE_BORDA, situacao='registra')]
        return []
    if provado is None:
        return [_item('borda_1px', 'borda_nao_conferida', FONTE_BORDA, **borda)]
    return [_item('borda_1px', None if tem_borda(provado, borda) else 'borda_ausente', FONTE_BORDA, **borda)]


def _fora(c, zona, tol, sangra):
    return [lado for lado, ok in (('esq', c[0] >= zona[0] - tol), ('topo', c[1] >= zona[1] - tol),
                                  ('dir', c[2] <= zona[2] + tol), ('base', c[3] <= zona[3] + tol))
            if not ok and not sangra.get(lado)]


def caixas_de_conteudo(ctx):
    """[(id, caixa na composicao, lados que sangram)]: a tinta medida de cada texto (render.json) e a caixa do logo no
    layout (derivacao/<formato>.json, classe marca)."""
    caixas = [('texto:%s' % e['id'], [float(v) for v in e['tinta']], {})
              for e in ctx['render'].get('entradas') or [] if e.get('tipo') == 'texto' and e.get('tinta')]
    for e in (ctx['derivacao'] or {}).get('elementos') or []:
        if e.get('classe') == 'marca':
            caixas.append(('marca:%s' % e['id'], [float(v) for v in e['caixa']],
                           (e.get('transformacao') or {}).get('sangra') or {}))
    return caixas


def _areas(ctx):
    from desdobra.derivacao import formatos as mf
    areas = mf.areas(ctx['formato'], ctx['spec'], ctx['arquivo_specs'])
    lim = limites.obter('entrega.tolerancia_area_px')
    tol = float(lim.valor)
    caixas = caixas_de_conteudo(ctx)
    itens = []
    for nome, regra, zona in (('area_segura', 'fora_da_area_segura', areas['area_segura']),
                              ('area_util', 'fora_da_area_util', areas['area_util'])):
        if zona is None:
            continue
        fora = [{'elemento': cid, 'lados': lados, 'caixa': c} for cid, c, sg in caixas
                for lados in [_fora(c, zona['caixa'], tol, sg)] if lados]
        itens.append(_item(nome, regra if fora else None, {'tipo': 'folha', 'folha': zona['fonte'],
                                                           'tolerancia': lim.citacao()},
                           situacao=lim.efeito_efetivo, caixa=zona['caixa'], elementos=len(caixas), fora=fora))
    for fx in areas['faixas']:
        f = fx['caixa']
        dentro = [cid for cid, c, _sg in caixas
                  if min(c[2], f[2]) - max(c[0], f[0]) > tol and min(c[3], f[3]) - max(c[1], f[1]) > tol]
        itens.append(_item('faixa_%s' % fx['lado'], 'dentro_da_faixa' if dentro else None,
                           {'tipo': 'folha', 'folha': fx['fonte'], 'tolerancia': lim.citacao()},
                           situacao=lim.efeito_efetivo, caixa=f, dentro=dentro))
    if itens:
        n_logos = sum(1 for cid, _c, _s in caixas if cid.startswith('marca:'))
        regra = 'logo_pela_caixa_do_layout' if ctx['derivacao'] is not None else 'logo_sem_caixa_de_layout'
        itens.append(_item('logo', regra, {'tipo': 'proposta', 'arquivo': 'proposta-m6, seção 3 (logo check)'},
                           situacao='registra', logos=n_logos))
    return itens


def validar(final, nome, ctx):
    """Verificacoes do arquivo final de um formato (ver o cabecalho). final: ArquivoFinal; nome: o nome do arquivo na
    entrega; ctx: de contexto()."""
    from PIL import Image
    from desdobra.specs import validar as vs
    fmt, spec, params, dados = ctx['formato'], ctx['spec'], ctx['parametros'], final.dados
    itens = [] if spec is not None else [_item('folha', 'formato_sem_spec_confirmada', FONTE_FOLHA)]
    itens.append(_peso(len(dados), spec, params, final))
    itens += _escolha_e_qualidade(final)
    mime = vs.mime_do_arquivo(dados[:vs.BYTES_CABECALHO])
    largura, altura = vs.dimensao_do_cabecalho(dados, mime)
    itens.append(_dimensao(largura, altura, fmt, spec))
    itens += _tipo(mime, nome, spec)
    try:
        with Image.open(io.BytesIO(dados)) as im:
            im.load()
            img = im.copy()
    except (OSError, ValueError, SyntaxError):
        img = None
    itens += _alfa_e_perfil(img)
    itens += _caminho_de_cor(ctx)
    i_decisoes, borda = _decisoes(final, ctx)
    itens += i_decisoes
    i_master, provado = _arquivo_do_master(final, img, ctx)
    itens += i_master
    itens += _borda(borda, provado, ctx)
    itens += _areas(ctx)
    # a comparacao com a peca aprovada (entrada/aprovadas/, tolerancia de borda do M4) ainda nao foi portada
    itens.append(_item('comparacao_com_aprovada', 'comparacao_com_aprovada_pendente',
                       {'tipo': 'limite', 'limites': [limites.obter('render.tolerancia_borda_smooth').citacao(),
                                                      limites.obter('render.tolerancia_borda_sharp_pequeno').citacao()]},
                       situacao='registra'))
    return itens


def montar(pasta, conferencia):
    """[{'formato', 'nome', 'final', 'verificacoes', 'origem', 'aprovacao', 'render'}] dos formatos que passaram no
    portao (desdobra.entrega.portao): origem = os hashes medidos agora; aprovacao = o registro do formato em
    briefing/aprovacao.json; render = as versoes e os sha256 das fontes do render.json."""
    from desdobra.entrega import aprovacao as mod_aprovacao
    aprov = mod_aprovacao.ler(pasta)
    com_arquivo = [(fid, item, contexto(pasta, fid)) for fid, item in conferencia['formatos'].items()
                   if item.get('recusa_do_encoder') is None]
    nomes = dict(zip((fid for fid, _i, _c in com_arquivo),
                     nomes_dos_arquivos([(fid, ctx['spec'], item['final'].extensao) for fid, item, ctx in com_arquivo])))
    ctxs = {fid: ctx for fid, _i, ctx in com_arquivo}
    itens = []
    for fid, item in conferencia['formatos'].items():
        if item.get('recusa_do_encoder') is not None:
            itens.append(item_sem_arquivo(fid, item['recusa_do_encoder'], item['atual']))
            continue
        ctx = ctxs[fid]
        nome, extra = nomes[fid]
        itens.append({'formato': fid, 'nome': nome, 'final': item['final'],
                      'verificacoes': ([extra] if extra else []) + validar(item['final'], nome, ctx),
                      'origem': dict(item['atual']), 'aprovacao': ((aprov or {}).get('formatos') or {}).get(fid),
                      'render': {'versoes': ctx['render'].get('versoes'),
                                 'fontes_sha256': sorted(f['sha256'] for f in ctx['render'].get('fontes') or [])}})
    return itens


def item_sem_arquivo(formato, erro, atual):
    """O item de montar() de um formato que o encoder recusou com uma de RECUSAS_ROTEADAS: vai para reprovados com a
    regra e a sugestao, sem arquivo (final None) e sem aprovacao (nao houve arquivo para aprovar)."""
    return {'formato': formato, 'nome': formato, 'final': None,
            'verificacoes': [_item('arquivo_final', erro.codigo, FONTE_ENCODER, **erro.medidas)],
            'origem': dict(atual or {}), 'aprovacao': None, 'render': None}


# ------------------------------------------------------------------ relatorio e gravacao
def selo(relatorio):
    """sha256 do relatorio sem o campo relatorio_sha256 (JSON com chaves ordenadas)."""
    sem = {k: v for k, v in relatorio.items() if k != 'relatorio_sha256'}
    return hashlib.sha256(json.dumps(sem, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def _registro(item, job_id, anterior):
    from desdobra.specs import validar as vs
    f = item['final']
    vers = _normal(item['verificacoes'])
    if f is None:  # recusa do encoder (item_sem_arquivo): a entrada fica no relatorio, sem arquivo
        arq = {'sha256': None, 'bytes': None, 'mime': None, 'largura': None, 'altura': None, 'extensao': None,
               'parametros_encoder': {}, 'medidas_encoder': {}}
    else:
        mime = vs.mime_do_arquivo(f.dados[:vs.BYTES_CABECALHO])
        largura, altura = vs.dimensao_do_cabecalho(f.dados, mime)
        arq = {'sha256': f.sha256, 'bytes': len(f.dados), 'mime': mime, 'largura': largura, 'altura': altura,
               'extensao': f.extensao, 'parametros_encoder': _normal(f.parametros), 'medidas_encoder': _normal(f.medidas)}
    return {'formato': item['formato'], 'nome': item['nome'], 'pasta': destino(vers), **arq, 'verificacoes': vers,
            'regras': [v['regra'] for v in vers if v['situacao'] == 'reprova'],
            'sugestoes': [v['sugestao'] for v in vers if v.get('sugestao')],
            'origem': item.get('origem'), 'aprovacao': mod_relatorio.aprovacao_do_arquivo(item, job_id),
            'mudou_desde_a_entrega_anterior': mod_relatorio.mudou(item, anterior)}


def relatorio(itens, job_id, disparo, quando=None, anterior=None, manifesto_sha256=None):
    """relatorio-entrega/1 dos itens de montar(). anterior: o relatorio da entrega que sai (None sem ela), para dizer o
    que mudou por formato; manifesto_sha256: o selo do manifesto de licenca desta entrega. ErroEntrega quando sobra
    numero sem fonte (desdobra.entrega.relatorio)."""
    from desdobra import __version__
    quando = quando or datetime.now().astimezone()
    regs = [_registro(i, job_id, anterior) for i in itens]
    rel = {'esquema': ESQUEMA, 'job_id': job_id, 'gerado_em': quando.isoformat(timespec='seconds'),
           'carimbo': quando.strftime('%Y%m%dT%H%M%S%z'), 'motor_versao': __version__,
           'entregue_por': disparo.registro(),
           'contagens': {'aprovados': sum(1 for r in regs if r['pasta'] == APROVADOS),
                         'reprovados': sum(1 for r in regs if r['pasta'] == REPROVADOS)},
           'arquivos': regs, 'ambiente': mod_relatorio.ambiente(itens),
           'limites': mod_relatorio.citacoes_da_entrega(), 'fontes_dos_campos': mod_relatorio.fontes_dos_campos(),
           'entrega_anterior': (anterior or {}).get('carimbo'), 'manifesto_sha256': manifesto_sha256}
    rel['resumo'] = mod_relatorio.resumo(rel)
    sem_fonte = mod_relatorio.numeros_sem_fonte(rel)
    if sem_fonte:
        raise ErroEntrega('relatorio_com_numero_sem_fonte', {'caminhos': sem_fonte})
    rel['relatorio_sha256'] = selo(rel)
    contratos.validar(rel, ESQUEMA)
    return rel


def _apagar(caminho):
    caminho = Path(caminho)
    if not caminho.exists():
        return
    for q in sorted(caminho.rglob('*'), reverse=True):
        if q.is_dir():
            q.rmdir()
        else:
            arquivos.tornar_gravavel(q)
            q.unlink()
    caminho.rmdir()


def _pasta_anterior(raiz, carimbo_novo, sufixo=''):
    """entrega/anteriores/<carimbo da entrega que sai><sufixo> (o do relatorio dela; sem relatorio legivel, o desta
    entrega com o sufixo -sem-relatorio), sem sobrescrever uma pasta que ja existe."""
    try:
        velho = arquivos.ler_json(raiz / ARQUIVO_RELATORIO).get('carimbo')
    except (OSError, ValueError, AttributeError):
        velho = None
    nome = (velho if isinstance(velho, str) and CARIMBO.match(velho) else '%s-sem-relatorio' % carimbo_novo) + sufixo
    base = raiz / PASTA_ANTERIORES / nome
    destino_, k = base, 1
    while destino_.exists():
        k += 1
        destino_ = base.with_name('%s-%d' % (nome, k))
    return destino_


def _trocar(raiz, nova, carimbo_novo):
    velhos = [n for n in ITENS_DA_ENTREGA if (raiz / n).exists()]
    anterior = _pasta_anterior(raiz, carimbo_novo) if velhos else None
    if anterior is not None:
        anterior.mkdir(parents=True)
    movidos, postos = [], []
    try:
        for n in velhos:
            os.replace(raiz / n, anterior / n)
            movidos.append(n)
        for n in reversed(ITENS_DA_ENTREGA):
            os.replace(nova / n, raiz / n)
            postos.append(n)
    except OSError:
        for n in reversed(postos):
            os.replace(raiz / n, nova / n)
        for n in reversed(movidos):
            os.replace(anterior / n, raiz / n)
        for d in ((anterior, anterior.parent) if anterior is not None else ()):
            if not any(d.iterdir()):
                d.rmdir()
        raise
    return anterior


def invalidar(pasta):
    """Tira a entrega atual de cena sem apagar nada (uma entrada do job mudou: nucleo.invalidar_render). O relatorio
    (primeiro, entao a entrega deixa de valer antes de sair), aprovados, reprovados e o manifesto-licenca.json da raiz
    vao para entrega/anteriores/<carimbo>-invalidada/, cada um com os.replace; se um falha (arquivo aberto no Windows),
    os passos feitos voltam e o OSError sobe. Devolve a pasta, ou None sem entrega."""
    pasta = Path(pasta)
    raiz = pasta / PASTA_ENTREGA
    itens = [(raiz / n, n) for n in ITENS_DA_ENTREGA if (raiz / n).exists()]
    man = pasta / mod_relatorio.ARQUIVO_MANIFESTO
    if man.exists():
        itens.append((man, man.name))
    if not itens:
        return None
    destino_ = _pasta_anterior(raiz, datetime.now().astimezone().strftime('%Y%m%dT%H%M%S%z'), SUFIXO_INVALIDADA)
    destino_.mkdir(parents=True)
    movidos = []
    try:
        for de, n in itens:
            os.replace(de, destino_ / n)
            movidos.append((de, n))
    except OSError:
        for de, n in reversed(movidos):
            os.replace(destino_ / n, de)
        for d in (destino_, destino_.parent):
            if not any(d.iterdir()):
                d.rmdir()
        raise
    return destino_


def gravar(pasta, itens, job_id, *, disparo):
    """Grava a entrega dos itens de montar() (ver o cabecalho). Devolve (relatorio, pasta da entrega anterior ou None).
    humano.ErroHumano sem o disparo do "entregar"; ErroEntrega quando a pasta montada nao confere."""
    humano.conferir(disparo, 'entregar', consumir=True)
    pasta = Path(pasta).resolve()
    raiz = pasta / PASTA_ENTREGA
    quando = datetime.now().astimezone()
    try:
        velho = arquivos.ler_json(raiz / ARQUIVO_RELATORIO) if (raiz / ARQUIVO_RELATORIO).is_file() else None
    except (OSError, ValueError):
        velho = None
    man = mod_relatorio.manifesto(pasta, job_id, quando)
    rel = relatorio(itens, job_id, disparo, quando, anterior=velho if isinstance(velho, dict) else None,
                    manifesto_sha256=mod_relatorio.selo_manifesto(man))
    nova = raiz / ('%sentrega-%d' % (arquivos.PREFIXO_TEMPORARIO, os.getpid()))
    _apagar(nova)
    try:
        for d in (APROVADOS, REPROVADOS):
            (nova / d).mkdir(parents=True)
        for reg, item in zip(rel['arquivos'], itens):
            if item['final'] is not None:
                arquivos.gravar_bytes_atomico(nova / reg['pasta'] / reg['nome'], item['final'].dados)
        contratos.gravar(nova / ARQUIVO_RELATORIO, rel, ESQUEMA)
        conf = conferir_pasta(nova)
        if not conf['ok']:
            raise ErroEntrega('entrega_montada_nao_confere', {k: v for k, v in conf.items() if k != 'ok'})
        anterior = _trocar(raiz, nova, rel['carimbo'])
    finally:
        _apagar(nova)
    # o manifesto fecha com a entrega, na raiz do job (nunca dentro de aprovados/); o relatorio guarda o selo dele. A
    # troca ja foi feita: se o manifesto nao grava (arquivo aberto), o conferir-entrega diz sem_manifesto ou
    # manifesto_diferente, e o OSError nao sobe como se a entrega nao tivesse sido trocada
    try:
        contratos.gravar(pasta / mod_relatorio.ARQUIVO_MANIFESTO, man, mod_relatorio.ESQUEMA_MANIFESTO)
    except OSError:
        pass
    return rel, anterior


# ------------------------------------------------------------------ conferir-entrega (so le)
def conferir_pasta(raiz):
    """Confere uma pasta de entrega contra o relatorio dela. So le. Devolve {'ok', 'relatorio' (motivo ou None),
    'arquivos', 'conferem', 'divergem', 'faltam', 'sobram', 'reprovado_em_aprovados', 'aprovado_em_reprovados',
    'arquivos_de_fonte'} (listas de caminhos relativos a raiz)."""
    raiz = Path(raiz)
    s = {'relatorio': None, 'arquivos': 0, 'conferem': 0, 'divergem': [], 'faltam': [], 'sobram': [],
         'reprovado_em_aprovados': [], 'aprovado_em_reprovados': [], 'arquivos_de_fonte': 0}
    if raiz.is_dir():
        s['arquivos_de_fonte'] = sum(1 for p in raiz.rglob('*') if p.is_file() and arquivos.eh_arquivo_de_fonte(p))
    arq = raiz / ARQUIVO_RELATORIO
    rel = None
    if not arq.is_file():
        s['relatorio'] = 'sem_relatorio'
    else:
        try:
            rel = contratos.ler(arq, ESQUEMA)
        except contratos.ErroContrato:
            s['relatorio'] = 'relatorio_invalido'
    if rel is not None and rel['relatorio_sha256'] != selo(rel):
        s['relatorio'] = 'relatorio_mexido'
    listados = set()
    for a in (rel or {}).get('arquivos') or []:
        rel_arq = '%s/%s' % (a['pasta'], a['nome'])
        s['arquivos'] += 1
        p = raiz / a['pasta'] / a['nome']
        sem_arquivo = a['sha256'] is None  # recusa do encoder: so a entrada, sempre em reprovados
        if not sem_arquivo:
            listados.add(rel_arq)
        if sem_arquivo:
            s['conferem'] += 1
        elif not p.is_file():
            s['faltam'].append(rel_arq)
        elif p.stat().st_size != a['bytes'] or arquivos.sha256_arquivo(p) != a['sha256']:
            s['divergem'].append(rel_arq)
        else:
            s['conferem'] += 1
        if (a['pasta'] != destino(a['verificacoes']) or bool(a['regras']) != (a['pasta'] == REPROVADOS) or
                (sem_arquivo and a['pasta'] != REPROVADOS)):
            s['reprovado_em_aprovados' if a['pasta'] == APROVADOS else 'aprovado_em_reprovados'].append(rel_arq)
    for d in (APROVADOS, REPROVADOS):
        if (raiz / d).is_dir():
            s['sobram'] += sorted(p.relative_to(raiz).as_posix() for p in (raiz / d).rglob('*')
                                  if p.is_file() and p.relative_to(raiz).as_posix() not in listados)
    s['ok'] = (s['relatorio'] is None and not s['arquivos_de_fonte'] and
               not any(s[k] for k in ('divergem', 'faltam', 'sobram', 'reprovado_em_aprovados', 'aprovado_em_reprovados')))
    return s


def conferir_entrega(pasta):
    """conferir_pasta() de entrega/ do job, mais o manifesto de licenca da raiz do job contra o selo que o relatorio
    guarda ('manifesto': motivo ou None). So le."""
    s = conferir_pasta(Path(pasta) / PASTA_ENTREGA)
    s['manifesto'] = None
    if s['relatorio'] is None:
        try:
            rel = arquivos.ler_json(Path(pasta) / PASTA_ENTREGA / ARQUIVO_RELATORIO)
        except (OSError, ValueError):
            rel = {}
        s['manifesto'] = mod_relatorio.conferir_manifesto(pasta, rel.get('manifesto_sha256'))
    s['ok'] = s['ok'] and s['manifesto'] is None
    return s
