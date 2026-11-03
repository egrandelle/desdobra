# -*- coding: utf-8 -*-
"""Correcoes da fatia vertical do M5 (decisoes-v1.md, 95 a 99), escritas antes do codigo.

95 cena sobreposta e bloco rigido (e nada some em silencio); 96 "nao sobrepor" so entre conteudo; 97 razao de corpo
entre todas as funcoes de texto; 98 margem da mestre forte, com minimo obrigatorio para texto e marca; 99 ajuste
global aplicado ao formato inteiro ou devolvido, e as contagens de preparo do PSD no laudo e na esteira.
"""
import math

import test_derivacao_apoio as ap
from desdobra import limites
from desdobra.briefing import modelo as mb
from desdobra.derivacao import elementos as mel
from desdobra.derivacao import nucleo as nd
from desdobra.derivacao import validacao as mval


def camada(lid, tipo, caixa, blend='NORMAL', mascara=None, ajuste=None, pais=(), corpo=None):
    c = ap.camada(lid, tipo, caixa if caixa else [0, 0, 0, 0], pais=pais, corpo=corpo)
    if not caixa:
        c['geometria']['caixa_tinta'] = None
    c['aparencia'].update(blend=blend, mascara=mascara or {'raster': False}, ajuste=ajuste, clipping=False)
    return c


def mascara(caixa, fundo=0):
    return {'raster': True, 'desativada': False, 'caixa': caixa, 'cor_fundo': fundo}


def cena():
    """KV 400x200 de baixo para cima: fundo, duas imagens que se sobrepoem (garrafa e liquido), uma luz em tela sobre
    elas, um ajuste com mascara sobre a garrafa, titulo, texto de apoio e logo."""
    camadas = [camada(1, 'pixel', [0, 0, 400, 200]),
               camada(2, 'smart_embutido', [250, 40, 330, 190]),
               camada(3, 'pixel', [260, 100, 320, 180]),
               camada(4, 'smart_embutido', [200, 0, 400, 120], blend='SCREEN'),
               camada(5, 'ajuste', None, mascara=mascara([255, 60, 325, 170]), ajuste={'tipo': 'curves'}),
               camada(10, 'texto', [20, 20, 220, 60], corpo=40),
               camada(20, 'texto', [20, 100, 200, 120], corpo=16),
               camada(30, 'smart_embutido', [340, 150, 390, 190])]
    funcoes = {1: 'fundo', 2: 'imagem', 3: 'imagem', 4: 'imagem', 5: 'imagem', 10: 'titulo', 20: 'texto_de_apoio',
               30: 'logo_principal'}
    return ap.laudo(400, 200, camadas), funcoes


def _ctx(laudo, funcoes, formatos=None, regras_bloco=None, **k):
    # a cena tem fundo (cover) e imagens (contain) no mesmo bloco: o DA da a regra do bloco (decisoes-v1.md, 100)
    b = ap.briefing(funcoes=funcoes, formatos=formatos or [ap.formato('perto', 480, 300)],
                    ancoras={**ap.ANCORAS, 'imagem': ('direita', 'meio')}, **k)
    regras_bloco = regras_bloco or {1: 'cover'}
    b['regras_bloco'] = [{'layer_id': lid, 'regra': ap.decisao(r)} for lid, r in sorted(regras_bloco.items())]
    return nd.contexto(laudo, b)


def _el(d, ident):
    return next(e for e in d['elementos'] if e['id'] == ident)


# ------------------------------------------------------------------ 95
def test_95_cena_sobreposta_vira_bloco_com_o_ajuste_e_a_luz():
    laudo, funcoes = cena()
    res, _e, info = mb.resolver(laudo, ap.briefing(funcoes=funcoes))
    m = mel.montar(laudo, res, None)
    blocos = [e for e in m['elementos'] if len(e['layer_ids']) > 1]
    assert len(blocos) == 1
    # a luz em tela pega o que esta embaixo dela, inclusive o fundo: tudo vai junto, como no KV
    assert set(blocos[0]['layer_ids']) == {1, 2, 3, 4, 5}
    assert m['fora_do_canvas'] == [] and m.get('sem_bloco') == []
    assert blocos[0]['membros'] and blocos[0]['bloco'] is True


def test_95_luz_do_canvas_inteiro_so_puxa_o_que_esta_embaixo():
    """No KV B, uma luz em tela do canvas inteiro puxava para o bloco os icones que ficam acima dela."""
    laudo, funcoes = cena()
    laudo['camadas'].insert(1, camada(8, 'smart_embutido', [0, 0, 400, 200], blend='SCREEN'))
    laudo['camadas'].insert(6, camada(9, 'smart_embutido', [20, 150, 60, 190]))
    funcoes = {**funcoes, 8: 'imagem', 9: 'grafismo'}
    res, _e, _i = mb.resolver(laudo, ap.briefing(funcoes=funcoes))
    m = mel.montar(laudo, res, None)
    bloco = next(e for e in m['elementos'] if 2 in e['layer_ids'])
    assert 8 in bloco['layer_ids'] and 9 not in bloco['layer_ids']


def test_95_bloco_anda_com_uma_escala_e_um_deslocamento():
    laudo, funcoes = cena()
    r = nd.derivar_em_memoria(_ctx(laudo, funcoes), specs={})
    d = r['formatos']['perto']
    assert d['situacao'] == 'derivado', d['devolucao']
    bl = next(e for e in d['elementos'] if 2 in e['layer_ids'])
    assert {1, 2, 3, 4, 5} == set(bl['layer_ids'])
    # o bloco e um elemento so no solver: nenhuma restricao fala de um membro como elemento proprio (sem variavel
    # propria, os membros nao tem como andar separados), e o render recebe uma transformacao so para todas as camadas
    ids_membros = {'el%d' % k for k in (2, 3, 4, 5)}
    assert not any(ids_membros & set(x['elementos']) for x in d['restricoes'])
    assert [e['id'] for e in d['elementos']].count(bl['id']) == 1
    # a garrafa (inteira no canvas da mestre) tem as restricoes de membro inteiro, pela caixa dela no formato
    assert any(x['nome'].startswith('membro_dentro_do_canvas') and x['nome'].endswith(':2') for x in d['restricoes'])
    tr = bl['transformacao']
    g = [250, 40, 330, 190]
    gx0, gy0 = tr['s'] * (g[0] - tr['origem_doc'][0]) + tr['destino'][0], tr['s'] * (g[1] - tr['origem_doc'][1]) + tr['destino'][1]
    gx1, gy1 = tr['s'] * (g[2] - tr['origem_doc'][0]) + tr['destino'][0], tr['s'] * (g[3] - tr['origem_doc'][1]) + tr['destino'][1]
    assert -1 <= gx0 and -1 <= gy0 and gx1 <= 481 and gy1 <= 301


def test_95_camada_sem_tinta_que_nao_cobre_bloco_e_erro_no_conferir():
    laudo, funcoes = cena()
    # ajuste abaixo de tudo: nao ha elemento de cena embaixo dele para atuar
    laudo['camadas'].insert(0, camada(6, 'ajuste', None, mascara=mascara([20, 20, 60, 40]), ajuste={'tipo': 'curves'}))
    funcoes = {**funcoes, 6: 'imagem'}
    b = ap.briefing(funcoes=funcoes, ancoras={**ap.ANCORAS, 'imagem': ('direita', 'meio')})
    res, _e, _i = mb.resolver(laudo, b)
    m = mel.montar(laudo, res, None)
    assert m['sem_bloco'] == [6] and 6 not in m['fora_do_canvas']
    assert any(e['codigo'] == 'camada_sem_tinta_sem_bloco' for e in mb.conferir(laudo, b))


def test_95_mesclagem_dentro_do_bloco_fica_na_pilha_do_bloco_e_partida_devolve():
    # a luz em tela logo acima da cena fica no bloco, sem outro elemento entre ela e o que ela pega: deriva
    laudo, funcoes = cena()
    d = nd.derivar_em_memoria(_ctx(laudo, funcoes), specs={})['formatos']['perto']
    assert d['situacao'] == 'derivado', d['devolucao']
    # o logo entre a cena e a luz na pilha: o render nao compoe o bloco numa pilha so, e o formato volta ao DA
    laudo, funcoes = cena()
    logo = next(c for c in laudo['camadas'] if c['identidade']['layer_id'] == 30)
    laudo['camadas'].remove(logo)
    laudo['camadas'].insert(3, logo)
    d = nd.derivar_em_memoria(_ctx(laudo, funcoes), specs={})['formatos']['perto']
    assert d['devolucao']['motivo'] == 'bloco_partido_na_pilha', d['devolucao']
    assert d['devolucao']['medidas']['blocos'][0]['separadores'] == [30]


# ------------------------------------------------------------------ 96
def test_96_nao_sobrepor_so_entre_conteudo():
    laudo, funcoes = cena()
    r = nd.derivar_em_memoria(_ctx(laudo, funcoes), specs={})
    d = r['formatos']['perto']
    pares = [x['elementos'] for x in d['restricoes'] if x['nome'].startswith('nao_sobrepor')]
    classes = {e['id']: e['classe'] for e in d['elementos']}
    assert pares and all(classes[a] in ('texto', 'marca') and classes[b] in ('texto', 'marca') for a, b in pares)


# ------------------------------------------------------------------ 97
def test_97_razao_de_corpo_entre_todas_as_funcoes_de_texto():
    regras = {**ap.REGRAS, 'titulo': 'raiz_area', 'texto_de_apoio': 'altura'}
    b = ap.briefing(formatos=[ap.formato('largo', 640, 240)], regras=regras)
    d = nd.derivar_em_memoria(nd.contexto(ap.laudo(), b), specs={})['formatos']['largo']
    assert d['situacao'] == 'derivado', d['devolucao']
    assert math.isclose(_el(d, 'el10')['escala'], _el(d, 'el20')['escala'], rel_tol=1e-4)
    assert any(x['nome'] == 'razao_de_corpo:el10:el20' or x['nome'] == 'razao_de_corpo:el20:el10'
               for x in d['restricoes'])


# ------------------------------------------------------------------ 98
def test_98_margem_da_mestre_e_minimo_obrigatorio_para_texto_e_marca():
    # texto de apoio grande, perto da base; formato largo e baixo
    camadas = [ap.camada(1, 'pixel', [0, 0, 400, 200]), ap.camada(10, 'texto', [40, 20, 200, 60], corpo=40),
               ap.camada(20, 'texto', [40, 80, 260, 180], corpo=60), ap.camada(30, 'smart_embutido', [330, 150, 380, 185])]
    funcoes = {1: 'fundo', 10: 'titulo', 20: 'texto_de_apoio', 30: 'logo_principal'}
    ancoras = {**ap.ANCORAS, 'texto_de_apoio': ('centro', 'meio')}
    b = ap.briefing(funcoes=funcoes, ancoras=ancoras, formatos=[ap.formato('baixo', 760, 240)],
                    familias={'faixa': ap.decisao(3.0)})
    d = nd.derivar_em_memoria(nd.contexto(ap.laudo(400, 200, camadas), b), specs={})['formatos']['baixo']
    assert d['situacao'] == 'derivado', d['devolucao']
    # o minimo e a fracao do lado curto do formato, ou a margem da mestre na escala de contain, a menor das duas
    r_min = limites.valor('derivacao.margem_minima_lado_curto')
    contain = min(760 / 400, 240 / 200)
    mestre = {'el10': [40, 20, 200, 140], 'el20': [40, 80, 140, 20], 'el30': [330, 150, 20, 15]}
    for ident in ('el10', 'el20', 'el30'):
        c = _el(d, ident)['caixa']
        margens = [c[0], c[1], 760 - c[2], 240 - c[3]]
        for lado, m, na_mestre in zip(('esq', 'topo', 'dir', 'base'), margens, mestre[ident]):
            assert m >= min(r_min * 240, na_mestre * contain) - 0.01, (ident, lado, m)
    # o logo esta a 15 px da base na mestre: o teto (15 x 1,2 = 18) passa o minimo do lado curto (12), vale o 12
    assert any(x['nome'] == 'margem_minima_base:el30' for x in d['restricoes'])
    # com a margem da mestre de 5 px, o minimo e o da mestre escalada (6 px), abaixo dos 12 do lado curto
    camadas2 = [ap.camada(1, 'pixel', [0, 0, 400, 200]), ap.camada(10, 'texto', [5, 20, 200, 60], corpo=40),
                ap.camada(30, 'smart_embutido', [330, 150, 380, 185])]
    b2 = ap.briefing(funcoes={1: 'fundo', 10: 'titulo', 30: 'logo_principal'}, formatos=[ap.formato('baixo', 760, 240)],
                     familias={'faixa': ap.decisao(3.0)})
    d2 = nd.derivar_em_memoria(nd.contexto(ap.laudo(400, 200, camadas2), b2), specs={})['formatos']['baixo']
    assert d2['situacao'] == 'derivado', d2['devolucao']
    assert _el(d2, 'el10')['caixa'][0] >= 5 * contain - 0.01
    nomes = {x['nome'].split(':')[0] for x in d['restricoes']}
    assert any(n.startswith('margem_minima') for n in nomes) and any(n.startswith('margem_da_mestre') for n in nomes)
    lim = limites.obter('derivacao.margem_minima_lado_curto')
    assert lim.fonte and lim.situacao == 'a_calibrar'


# ------------------------------------------------------------------ 99
def test_99_ajuste_global_com_conteudo_embaixo_devolve_e_sobre_a_cena_entra_no_bloco():
    laudo, funcoes = cena()
    # ajuste global no topo, acima do texto: o render nao aplica sobre o formato inteiro -> devolve
    laudo['camadas'].append(camada(90, 'ajuste', None, mascara=mascara([0, 0, 0, 0], fundo=255), ajuste={'tipo': 'curves'}))
    r = nd.derivar_em_memoria(_ctx(laudo, {**funcoes, 90: 'ajuste_global'}), specs={})
    assert r['formatos']['perto']['devolucao']['motivo'] == 'ajuste_global_sem_aplicar'
    # o mesmo ajuste logo acima da cena (abaixo do texto) entra no bloco da cena
    laudo, funcoes = cena()
    laudo['camadas'].insert(5, camada(90, 'ajuste', None, mascara=mascara([0, 0, 0, 0], fundo=255), ajuste={'tipo': 'curves'}))
    r = nd.derivar_em_memoria(_ctx(laudo, {**funcoes, 90: 'ajuste_global'}), specs={})
    d = r['formatos']['perto']
    assert d['situacao'] == 'derivado', d['devolucao']
    assert any(90 in e['layer_ids'] for e in d['elementos'])


def test_99_preparo_conta_ajustes_mesclagens_cores_mascaradas_e_aglomerados():
    from desdobra.laudo import preparo
    laudo, _f = cena()
    laudo['camadas'].insert(4, camada(7, 'cor_solida', [255, 50, 300, 120], mascara=mascara([255, 50, 300, 120])))
    c = preparo.contar(laudo)
    assert c == {'ajustes_com_mascara': 1, 'mesclagens': 1, 'cores_solidas_mascaradas_sobre_imagem': 1,
                 'aglomerados_sobrepostos': 1, 'camadas_em_aglomerados': 4}
    rec = preparo.recomendacao(c)
    assert rec and 'smart object' in rec
    assert preparo.recomendacao({k: 0 for k in c}) is None


def test_99_esteira_mostra_as_contagens_do_preparo(job_der):
    from desdobra.job import nucleo
    r = nucleo.proxima(job_der['job'], todas=True)
    assert 'preparo_ajustes_com_mascara' in r.contagens and 'preparo_aglomerados_sobrepostos' in r.contagens


def test_validacao_de_colisao_so_entre_conteudo():
    sg = {'esq': False, 'topo': False, 'dir': False, 'base': False}
    els = [{'id': 'el1', 'funcao': 'imagem', 'regra': 'contain', 'classe': 'base', 'sangra': sg},
           {'id': 'el2', 'funcao': 'titulo', 'regra': 'raiz_area', 'classe': 'texto', 'sangra': sg}]
    kv = {'el1': {'caixa': [0, 0, 10, 10], 'classe': 'base'}, 'el2': {'caixa': [20, 0, 30, 10], 'classe': 'texto'}}
    esperado = {'el1': ('imagem', 'contain'), 'el2': ('titulo', 'raiz_area')}
    val = mval.validar((100, 100), {}, els, [[0, 0, 25, 10], [20, 0, 30, 10]], [1.0, 1.0], kv, esperado)
    assert not mval.reprovadas(val)


from test_derivacao_job import job_der  # noqa: E402,F401  (fixture do job sintetico)
