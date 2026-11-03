# -*- coding: utf-8 -*-
"""Rodada 3 da fatia vertical do M5, escrita antes do codigo.

1a objeto solto (base que nao sangra, opaco) entra no "nao sobrepor" e na colisao contra conteudo; 1b proximidade da
mestre (elementos perto um do outro mantem a distancia na escala); 2 quebras aprovadas por familia no briefing (a caixa
do texto e a das linhas que ficam, o render junta as linhas, e o texto de muitas linhas sem quebra aprovada numa
proporcao muito diferente avisa).
"""
import test_derivacao_apoio as ap
from desdobra import limites
from desdobra.briefing import modelo as mb
from desdobra.derivacao import nucleo as nd
from desdobra.derivacao import validacao as mval
from desdobra.render import texto as mtexto
from test_derivacao_blocos import camada

SG = {'esq': False, 'topo': False, 'dir': False, 'base': False}


def _d(laudo, funcoes, formato, ancoras=None, **k):
    b = ap.briefing(funcoes=funcoes, formatos=[formato], ancoras=ancoras or ap.ANCORAS,
                    familias={'faixa': ap.decisao(3.0)}, **k)
    return nd.derivar_em_memoria(nd.contexto(ap.laudo(400, 200, laudo), b), specs={})['formatos'][formato['id']], b


def _icones():
    """Titulo grande em cima de dois icones (grafismo, sem sangrar), fundo e logo."""
    return [camada(1, 'pixel', [0, 0, 400, 200]), camada(10, 'texto', [20, 40, 260, 110], corpo=60),
            camada(5, 'smart_embutido', [20, 118, 140, 146]), camada(30, 'smart_embutido', [330, 150, 380, 185])]


FUNCOES_ICONES = {1: 'fundo', 10: 'titulo', 5: 'grafismo', 30: 'logo_principal'}
ANCORAS_ICONES = {**ap.ANCORAS, 'titulo': ('esquerda', 'base'), 'grafismo': ('esquerda', 'base')}


# ------------------------------------------------------------------ 1a
def test_objeto_solto_entra_no_nao_sobrepor_com_o_conteudo():
    d, _b = _d(_icones(), FUNCOES_ICONES, ap.formato('largo', 760, 240), ancoras=ANCORAS_ICONES)
    assert d['situacao'] == 'derivado', d['devolucao']
    pares = [set(x['elementos']) for x in d['restricoes'] if x['nome'].startswith('nao_sobrepor')]
    assert {'el10', 'el5'} in pares
    el = {e['id']: e for e in d['elementos']}
    t, i = el['el10']['caixa'], el['el5']['caixa']
    assert t[3] <= i[1] + limites.valor('derivacao.colisao_tolerancia_px')
    # o fundo, que sangra, continua fora do "nao sobrepor"
    assert not any('el1' in p for p in pares)


def test_colisao_conta_objeto_solto_contra_conteudo_e_nao_cena_que_sangra():
    els = [{'id': 'el1', 'funcao': 'titulo', 'regra': 'x', 'classe': 'texto', 'sangra': SG},
           {'id': 'el2', 'funcao': 'grafismo', 'regra': 'x', 'classe': 'base', 'sangra': SG, 'opaco': True}]
    kv = {'el1': {'caixa': [0, 0, 10, 10]}, 'el2': {'caixa': [20, 0, 30, 10]}}
    esperado = {'el1': ('titulo', 'x'), 'el2': ('grafismo', 'x')}
    caixas = [[0, 0, 25, 10], [20, 0, 30, 10]]
    val = mval.validar((100, 100), {}, els, caixas, [1.0, 1.0], kv, esperado)
    assert next(v for v in val if v['nome'] == 'colisao_nova_contra_a_origem')['situacao'] == 'reprova'
    els[1]['sangra'] = dict(SG, esq=True)
    val = mval.validar((100, 100), {}, els, caixas, [1.0, 1.0], kv, esperado)
    assert next(v for v in val if v['nome'] == 'colisao_nova_contra_a_origem')['situacao'] == 'ok'


# ------------------------------------------------------------------ 1b
def test_proximidade_da_mestre_mantem_a_distancia_na_escala():
    d, _b = _d(_icones(), FUNCOES_ICONES, ap.formato('quase', 400, 300), ancoras=ANCORAS_ICONES)
    assert d['situacao'] == 'derivado', d['devolucao']
    nomes = [x for x in d['restricoes'] if x['nome'].startswith('proximidade')]
    assert nomes and {x['forca'] for x in nomes} == {'forte'}
    el = {e['id']: e for e in d['elementos']}
    t, i = el['el10'], el['el5']
    gap = i['caixa'][1] - t['caixa'][3]
    s = (t['escala'] + i['escala']) / 2.0
    assert abs(gap - 8 * s) <= 0.5, (gap, s)
    lim = limites.obter('derivacao.proximidade_max')
    assert lim.fonte and lim.situacao == 'a_calibrar'


# ------------------------------------------------------------------ 2
def _apoio(corpo=20):
    """Texto de apoio de quatro linhas (tres quebras gravadas), 160 x 80 na mestre."""
    c = camada(20, 'texto', [20, 100, 180, 180], corpo=corpo)
    linhas = ['aaaa bbbb', 'cccc dd', 'eeee ffff', 'gg hhhh']
    conteudo = '\r'.join(linhas) + '\r'
    c['texto'].update({'conteudo': conteudo, 'paragrafos': [], 'justificacao': 'LEFT'})
    c['texto']['runs'][0].update({'inicio': 0, 'fim': len(conteudo), 'texto': conteudo})
    return c


def _quebras(manter, razao_min=2.5, razao_max=None):
    return [{'layer_id': 20, 'razao_min': razao_min, 'razao_max': razao_max, 'quebras': ap.decisao(manter)}]


def _laudo_apoio():
    return [camada(1, 'pixel', [0, 0, 400, 200]), camada(10, 'texto', [20, 20, 220, 60], corpo=40), _apoio(),
            camada(30, 'smart_embutido', [330, 150, 380, 185])]


FUNCOES_APOIO = {1: 'fundo', 10: 'titulo', 20: 'texto_de_apoio', 30: 'logo_principal'}


def test_quebra_aprovada_por_familia_muda_a_caixa_do_texto_no_formato_da_familia():
    """Revisao 3: a largura vem da medida (injetada aqui; no job, o Chromium mede) e a altura perde uma entrelinha por
    quebra tirada."""
    from desdobra.derivacao import quebras as mq
    largo = ap.formato('largo', 760, 240)
    d0, _b = _d(_laudo_apoio(), FUNCOES_APOIO, largo)
    b = ap.briefing(funcoes=FUNCOES_APOIO, formatos=[largo], ancoras=ap.ANCORAS, familias={'faixa': ap.decisao(3.0)},
                    quebras_por_familia=_quebras([1]))
    assert not mb.conferir(ap.laudo(400, 200, _laudo_apoio()), b)
    medidas = {mq.chave(20, [1]): {'largura_texto_mestre': 90.0, 'largura_texto': 170.0, 'linhas': 2}}
    ctx = nd.contexto(ap.laudo(400, 200, _laudo_apoio()), b, medidas_quebras=medidas)
    d1 = nd.derivar_em_memoria(ctx, specs={})['formatos']['largo']
    assert d1['situacao'] == 'derivado', d1['devolucao']
    a0 = next(e for e in d0['elementos'] if e['id'] == 'el20')
    a1 = next(e for e in d1['elementos'] if e['id'] == 'el20')
    m0, m1 = a0['caixa_mestre'], a1['caixa_mestre']
    assert abs((m1[2] - m1[0]) - (m0[2] - m0[0]) * 170.0 / 90.0) <= 0.5
    assert a1['quebras']['familia'][0]['aprovadas'] == [1]
    # fora da familia, a quebra aprovada nao vale
    d2, _b = _d(_laudo_apoio(), FUNCOES_APOIO, ap.formato('perto', 480, 300), quebras_por_familia=_quebras([1]))
    a2 = next(e for e in d2['elementos'] if e['id'] == 'el20')
    assert a2['quebras'] == 'congeladas_da_mestre'


def test_texto_de_muitas_linhas_sem_quebra_aprovada_em_proporcao_muito_diferente_avisa():
    d, _b = _d(_laudo_apoio(), FUNCOES_APOIO, ap.formato('largo', 760, 240))
    v = [x for x in d['validacoes'] if x['nome'] == 'quebras_sem_aprovacao']
    assert v and v[0]['situacao'] == 'avisa' and v[0]['elementos'] == ['el20']
    d, _b = _d(_laudo_apoio(), FUNCOES_APOIO, ap.formato('perto', 480, 300))
    assert not [x for x in d['validacoes'] if x['nome'] == 'quebras_sem_aprovacao' and x['situacao'] == 'avisa']
    lim = limites.obter('derivacao.quebra_razao_aviso')
    assert lim.fonte and lim.situacao == 'a_calibrar'


def test_quebra_aprovada_invalida_e_recusada_no_conferir():
    laudo = ap.laudo(400, 200, _laudo_apoio())
    b = ap.briefing(funcoes=FUNCOES_APOIO, formatos=[ap.formato('largo', 760, 240)], quebras_por_familia=_quebras([5]))
    assert 'quebra_aprovada_invalida' in {e['codigo'] for e in mb.conferir(laudo, b)}
    b = ap.briefing(funcoes=FUNCOES_APOIO, formatos=[ap.formato('largo', 760, 240)],
                    quebras_por_familia=[dict(_quebras([1])[0], layer_id=30)])
    assert 'quebra_aprovada_invalida' in {e['codigo'] for e in mb.conferir(laudo, b)}


def test_render_junta_as_linhas_nas_quebras_juntadas():
    t = _apoio()['texto']
    assert len(mtexto.linhas_da_camada(t)) == 4
    linhas = mtexto.linhas_da_camada(t, juntar=[9, 27])
    assert len(linhas) == 2
    texto = [''.join(p[0] for p in ln['pedacos']) for ln in linhas]
    assert texto == ['aaaa bbbb cccc dd', 'eeee ffff gg hhhh']
    assert linhas[0]['indices'][9] == 9


def test_grupo_preso_anda_pela_ancora_do_maior():
    """Escrito depois da correcao (achado no diagnostico da rodada 3): com a distancia presa pela proximidade, as
    ancoras de cada membro do grupo (meio num, base no outro) prendiam a escala do grupo inteiro. O grupo anda pela
    ancora do maior membro, naquele eixo."""
    ancoras = {**ANCORAS_ICONES, 'titulo': ('esquerda', 'meio')}
    d, _b = _d(_icones(), FUNCOES_ICONES, ap.formato('largo', 760, 240), ancoras=ancoras)
    assert d['situacao'] == 'derivado', d['devolucao']
    ancoras_y = {x['elementos'][0] for x in d['restricoes'] if x['nome'].startswith('ancora_y')}
    assert 'el10' in ancoras_y and 'el5' not in ancoras_y


def test_alinhamento_com_diferenca_de_um_px_nao_prende_a_escala_na_largura_do_formato():
    """Rodada 3, diagnostico do 2048x720: dois textos alinhados nas duas bordas com 1 px de diferenca na mestre. A
    diferenca entrava na proporcao da largura do formato; com a mesma escala nos dois (razao de corpo), isso prendia a
    escala em largura do formato / largura da mestre, longe da regra."""
    camadas = [camada(1, 'pixel', [0, 0, 400, 200]), camada(10, 'texto', [20, 40, 220, 80], corpo=40),
               camada(11, 'texto', [21, 90, 222, 110], corpo=20), camada(30, 'smart_embutido', [330, 150, 380, 185])]
    funcoes = {1: 'fundo', 10: 'titulo', 11: 'texto_de_apoio', 30: 'logo_principal'}
    d, _b = _d(camadas, funcoes, ap.formato('largo', 1000, 240))
    assert d['situacao'] == 'derivado', d['devolucao']
    el = {e['id']: e for e in d['elementos']}
    assert any(x['nome'].startswith('alinhamento_x_fim') for x in d['restricoes'])
    assert abs(el['el10']['escala'] - 1000 / 400.0) > 0.1, el['el10']['escala']
    assert abs(el['el10']['escala'] - el['el10']['escala_regra']) < abs(1000 / 400.0 - el['el10']['escala_regra'])


def test_elementos_alinhados_andam_por_uma_ancora_so_no_eixo():
    """Escrito junto com a correcao (achado no diagnostico do 2048x720 do KV A): titulo ancorado a esquerda e apoio
    ancorado no centro, alinhados pela borda esquerda (forte): as duas ancoras (medias) prendiam a largura do apoio, e
    com ela a escala dos textos."""
    camadas = [camada(1, 'pixel', [0, 0, 400, 200]), camada(10, 'texto', [20, 20, 220, 60], corpo=40),
               camada(11, 'texto', [20, 100, 300, 140], corpo=20), camada(30, 'smart_embutido', [330, 150, 380, 185])]
    funcoes = {1: 'fundo', 10: 'titulo', 11: 'texto_de_apoio', 30: 'logo_principal'}
    ancoras = {**ap.ANCORAS, 'texto_de_apoio': ('centro', 'meio')}
    d, _b = _d(camadas, funcoes, ap.formato('largo', 1000, 240), ancoras=ancoras)
    assert d['situacao'] == 'derivado', d['devolucao']
    com_x = {x['elementos'][0] for x in d['restricoes'] if x['nome'].startswith('ancora_x')}
    assert ('el10' in com_x) != ('el11' in com_x)
