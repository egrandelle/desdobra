# -*- coding: utf-8 -*-
"""Derivacao deterministica por familia (M5, arquitetura-v1.md, 4.10 e 9.6), com laudos e briefings sinteticos.

Criterios de pronto cobertos aqui: a origem passa (a mestre satisfaz todas as obrigatorias); teste de mutacao do
defeito 1 (trocar a funcao de uma camada no briefing muda a regra aplicada no layout e na validacao em todos os casos
gerados); troca forte de orientacao devolvida pedindo mestre propria em todos os casos, nenhum derivado sozinho;
obrigatoria sintetica que nao fecha devolvida com o nome e a fonte em todos os casos; "fora da peca" em nenhum
formato; "indeterminado" sem regra devolve o formato em todos os casos.
"""
import itertools
import math
import random

import pytest
from pathlib import Path

import test_derivacao_apoio as ap
from desdobra import contratos, limites
from desdobra.briefing import modelo as mb
from desdobra.derivacao import elementos as mel
from desdobra.derivacao import escala as mesc
from desdobra.derivacao import formatos as mfmt
from desdobra.derivacao import nucleo as nd
from desdobra.derivacao import solver as msol
from desdobra.derivacao import validacao as mval

FUNCOES_COM_GEOMETRIA = sorted(f for f, c in mb.CLASSES.items() if c in ('base', 'texto', 'marca'))


def _derivar(laudo=None, briefing=None, specs=None):
    laudo = laudo or ap.laudo()
    briefing = briefing or ap.briefing()
    ctx = nd.contexto(laudo, briefing)
    return nd.derivar_em_memoria(ctx, specs=specs or {}, arquivo_specs='specs/rascunho.json')


def _el(d, ident):
    return next(e for e in d['elementos'] if e['id'] == ident)


# ------------------------------------------------------------------ regras e orientacao
def test_regras_de_escala_seguem_a_pesquisa():
    m, f = (400, 200), (800, 300)
    assert mesc.escala('largura', m, f) == 2.0 and mesc.escala('altura', m, f) == 1.5
    assert mesc.escala('lado_curto', m, f) == 1.5 and mesc.escala('lado_longo', m, f) == 2.0
    assert math.isclose(mesc.escala('raiz_area', m, f), math.sqrt(3.0))
    assert mesc.escala('constante', m, f) == 1.0
    assert mesc.escala('contain', m, f) == 1.5 and mesc.escala('cover', m, f) == 2.0
    with pytest.raises(ValueError):
        mesc.escala('pelo_nome_da_camada', m, f)
    assert set(mesc.REGRAS) == set(contratos.carregar_esquema('briefing/1')['$defs']['regra']['enum'])


def test_orientacao_e_troca_forte():
    assert mesc.orientacao(1920, 1080) == 'horizontal' and mesc.orientacao(1080, 1920) == 'vertical'
    assert mesc.orientacao(400, 400) == 'quadrado' and mesc.orientacao(404, 400) == 'quadrado'
    assert mesc.troca_de_orientacao((1920, 1080), (300, 600)) == 'forte'
    assert mesc.troca_de_orientacao((1080, 1920), (3584, 960)) == 'forte'
    assert mesc.troca_de_orientacao((1920, 1080), (300, 300)) == 'quadrado'
    assert mesc.troca_de_orientacao((1920, 1080), (1200, 637)) is None


# ------------------------------------------------------------------ heranca e elementos
def test_heranca_grupo_passa_e_excecao_vale_sobre_o_grupo():
    laudo = ap.laudo()
    b = ap.briefing(funcoes={**ap.FUNCOES, 12: 'grafismo'})
    res, erros, info = mb.resolver(laudo, b)
    assert not erros
    assert res[11]['funcao'] == 'titulo' and res[11]['por'] == 'grupo' and res[11]['raiz'] == 10
    assert res[12]['funcao'] == 'grafismo' and res[12]['por'] == 'camada' and res[12]['raiz'] == 12
    assert 60 not in res and info['invisiveis'] == 1


def test_elementos_juntam_o_grupo_e_cortam_no_canvas():
    laudo = ap.laudo()
    laudo['camadas'][0]['geometria']['caixa_tinta'] = [-50, -10, 450, 210]
    res, _e, _i = mb.resolver(laudo, ap.briefing())
    m = mel.montar(laudo, res, None)
    ids = {e['id']: e for e in m['elementos']}
    assert set(ids) == {'el1', 'el10', 'el20', 'el30', 'el40'}
    assert ids['el10']['layer_ids'] == [11, 12] and ids['el10']['texto'] and ids['el10']['caixa'] == [20, 20, 220, 80]
    assert ids['el1']['caixa'] == [0, 0, 400, 200] and all(ids['el1']['sangra'].values())
    assert not any(ids['el20']['sangra'].values())
    assert m['fora_da_peca'] == [50]


def test_camada_sem_funcao_indeterminado_sem_observacao_e_pendente_sao_recusados():
    laudo = ap.laudo()
    sem = dict(ap.FUNCOES)
    sem.pop(30)
    assert any(e['codigo'] == 'camada_sem_funcao' for e in mb.conferir(laudo, ap.briefing(funcoes=sem)))
    b = ap.briefing(funcoes={**ap.FUNCOES, 30: 'indeterminado'})
    b['funcoes'][[f['layer_id'] for f in b['funcoes']].index(30)]['observacao'] = '  '
    assert any(e['codigo'] == 'indeterminado_sem_observacao' for e in mb.conferir(laudo, b))
    b = ap.briefing()
    b['modo_dados'] = ap.pendente()
    assert any(e['codigo'] == 'pendente_obrigatorio' for e in mb.conferir(laudo, b))
    b = ap.briefing(regras={k: v for k, v in ap.REGRAS.items() if k != 'titulo'})
    assert any(e['codigo'] == 'regra_de_escala_faltando' for e in mb.conferir(laudo, b))
    b = ap.briefing(ancoras={k: v for k, v in ap.ANCORAS.items() if k != 'logo_principal'})
    assert any(e['codigo'] == 'ancora_faltando' for e in mb.conferir(laudo, b))
    assert mb.conferir(laudo, ap.briefing()) == []


def test_coberta_pede_decisao_e_aceita_ou_inverte_a_regra_da_decisao_10():
    cob = {'coberta': True, 'sugestao_da_regra': {'funcao': 'fora_da_peca', 'regra': 'decisao-10'}}
    laudo = ap.laudo()
    laudo['camadas'].append(ap.camada(70, 'pixel', [60, 60, 80, 80], coberta=cob))
    assert any(e['codigo'] == 'coberta_sem_decisao' for e in mb.conferir(laudo, ap.briefing()))
    res, erros, _i = mb.resolver(laudo, ap.briefing(cobertas=[(70, 'aceita')]))
    assert not erros and res[70]['funcao'] == 'fora_da_peca' and res[70]['por'] == 'decisao_10'
    res, erros, _i = mb.resolver(laudo, ap.briefing(cobertas=[(70, 'inverte')]))
    assert not erros and res[70]['funcao'] == 'estrutura'


def test_quadro_escolhido_tira_as_camadas_dos_outros_quadros():
    quadros = [{'id': 'q1', 'regra': 'pranchetas', 'caixa': [0, 0, 400, 200]},
               {'id': 'q2', 'regra': 'pranchetas', 'caixa': [500, 0, 900, 200]}]
    camadas = ap.laudo()['camadas']
    for c in camadas:
        c['quadro'] = 'q1'
    camadas.append(ap.camada(90, 'pixel', [520, 20, 560, 60], quadro='q2'))
    laudo = ap.laudo(largura=900, camadas=camadas, quadros=quadros)
    assert any(e['codigo'] == 'quadro_sem_escolha' for e in mb.conferir(laudo, ap.briefing()))
    b = ap.briefing(quadro='q9')
    assert any(e['codigo'] == 'quadro_invalido' for e in mb.conferir(laudo, b))
    b = ap.briefing(quadro='q2', funcoes={90: 'grafismo'})
    res, erros, info = mb.resolver(laudo, b)
    assert not erros and set(res) == {90} and info['fora_do_quadro'] == 7
    m = mel.montar(laudo, res, 'q2')
    assert m['canvas_doc'] == [500, 0, 900, 200] and m['elementos'][0]['caixa'] == [20, 20, 60, 60]


# ------------------------------------------------------------------ os tres caminhos
def test_a_origem_passa_a_mestre_satisfaz_todas_as_obrigatorias():
    b = ap.briefing(formatos=[ap.formato('origem', 400, 200)])
    d = _derivar(briefing=b)['formatos']['origem']
    assert d['situacao'] == 'derivado' and d['caminho'] == 'transform'
    assert not mval.reprovadas(d['validacoes'])
    for e in d['elementos']:
        assert e['caixa'] == e['caixa_mestre'] and e['escala'] == 1.0
    # e pelo solver tambem: as obrigatorias geradas da propria mestre fecham na mestre
    kv = nd.mestre_do_kv(nd.contexto(ap.laudo(), b))
    regras = [1.0] * len(kv['elementos'])
    caixas, escalas, rest = msol.resolver(kv['elementos'], (400, 200), (400, 200), {}, regras)
    assert all(r['forca'] != 'obrigatoria' or r['fonte'] for r in rest)
    for e, c in zip(kv['elementos'], caixas):
        assert all(abs(a - b) < 1e-6 for a, b in zip(c, e['caixa']))


def test_mesma_proporcao_vira_transform_de_saida():
    d = _derivar()['formatos']['mesmo']
    assert d['caminho'] == 'transform' and d['situacao'] == 'derivado'
    assert {e['escala'] for e in d['elementos']} == {2.0}
    assert _el(d, 'el20')['caixa'] == [40, 200, 400, 240]


def test_proporcao_diferente_na_familia_vai_ao_solver_e_fecha():
    d = _derivar()['formatos']['perto']
    assert d['caminho'] == 'solver' and d['situacao'] == 'derivado', d['devolucao']
    assert d['familia']['na_faixa'] and d['familia']['troca'] is None
    assert not mval.reprovadas(d['validacoes'])
    forcas = {r['forca'] for r in d['restricoes']}
    assert {'obrigatoria', 'forte', 'media', 'fraca'} <= forcas
    fundo = _el(d, 'el1')
    assert fundo['caixa'][0] <= 0 and fundo['caixa'][1] <= 0 and fundo['caixa'][2] >= 480 and fundo['caixa'][3] >= 300
    for e in d['elementos']:
        if e['id'] != 'el1':
            assert e['caixa'][0] >= -1 and e['caixa'][2] <= 481 and e['caixa'][3] <= 301
    # o texto anda junto (razao de corpo)
    # as funcoes de texto mantem a razao de corpo da mestre entre si (decisoes-v1.md, 97)
    assert math.isclose(_el(d, 'el10')['escala'], _el(d, 'el20')['escala'], rel_tol=1e-4)
    assert math.isclose(_el(d, 'el10')['escala'], _el(d, 'el40')['escala'], rel_tol=1e-4)


def test_troca_forte_de_orientacao_e_sempre_devolvida_e_nunca_derivada():
    rng = random.Random(5)
    formatos = []
    for k in range(40):
        a = rng.randint(300, 2000)
        formatos.append(ap.formato('v%02d' % k, int(a / rng.uniform(1.2, 6.0)), a))
    r = _derivar(briefing=ap.briefing(formatos=formatos))
    assert len(r['formatos']) == 40
    for d in r['formatos'].values():
        assert d['situacao'] == 'devolvido' and d['devolucao']['motivo'] == 'troca_forte_de_orientacao'
        assert d['elementos'] == []
    # o mesmo do vertical para o horizontal
    camadas = [ap.camada(1, 'pixel', [0, 0, 200, 400]), ap.camada(2, 'texto', [20, 20, 180, 60], corpo=30)]
    b = ap.briefing(funcoes={1: 'fundo', 2: 'titulo'}, formatos=[ap.formato('h', 1200, 400), ap.formato('q', 400, 400)])
    r = _derivar(laudo=ap.laudo(200, 400, camadas), briefing=b)
    assert r['formatos']['h']['devolucao']['motivo'] == 'troca_forte_de_orientacao'
    assert r['formatos']['q']['devolucao']['motivo'] == 'troca_de_orientacao_quadrado'


def test_fora_da_faixa_volta_ao_da_e_a_faixa_e_parametro():
    b = ap.briefing(formatos=[ap.formato('largo', 1200, 200)])
    d = _derivar(briefing=b)['formatos']['largo']
    assert d['devolucao']['motivo'] == 'fora_da_faixa_de_familia'
    assert d['parametros']['faixa']['origem']['tipo'] == 'proposta'
    assert d['parametros']['faixa']['origem']['limite']['limite_id'] == 'derivacao.faixa_familia_razao_max'
    b['familias'] = {'faixa': ap.decisao(4.0)}
    d = _derivar(briefing=b)['formatos']['largo']
    assert d['parametros']['faixa']['origem']['tipo'] == 'briefing' and d['familia']['na_faixa']


def _colunas(n, rng):
    """KV com n colunas lado a lado, cada uma da altura toda (sangram em cima e embaixo)."""
    W, H = 100 * n, 300
    camadas = [ap.camada(k + 1, 'pixel', [100 * k + 10, 0, 100 * k + 90, 300]) for k in range(n)]
    # sujeito e conteudo: "nao sobrepor" vale entre eles (decisoes-v1.md, 96), e o que sangra continua sangrando
    return ap.laudo(W, H, camadas), {k + 1: 'sujeito' for k in range(n)}


def test_obrigatoria_sintetica_que_nao_fecha_volta_com_nome_e_fonte():
    rng = random.Random(9)
    casos = 0
    for _ in range(400):
        if casos >= 25:
            break
        n = rng.randint(4, 8)
        laudo, funcoes = _colunas(n, rng)
        W = 100 * n
        # bem mais estreito, ainda horizontal e dentro da faixa: as colunas tem de ir de cima a baixo e nao se tocar
        fmt = ap.formato('aperto', int(W * rng.uniform(0.55, 0.7)), int(300 * rng.uniform(1.1, 1.3)))
        if mesc.troca_de_orientacao((W, 300), (fmt['largura'], fmt['altura'])):
            continue
        b = ap.briefing(funcoes=funcoes, formatos=[fmt], familias={'faixa': ap.decisao(10.0)})
        d = _derivar(laudo=laudo, briefing=b)['formatos']['aperto']
        casos += 1
        assert d['situacao'] == 'devolvido', d['caminho']
        dv = d['devolucao']
        assert dv['motivo'] == 'restricao_obrigatoria_nao_fecha'
        assert dv['restricao']['nome'] and dv['restricao']['forca'] == 'obrigatoria' and dv['restricao']['fonte']
        assert dv['restricao']['nome'].split(':')[0].startswith(('nao_sobrepor', 'sangria'))
    assert casos >= 25


def test_area_util_e_faixa_da_folha_entram_como_obrigatoria_com_a_fonte():
    chave = 'teste|faixa|480x300'
    specs = {chave: ap.spec(chave, {'area_util': {'largura': 480, 'altura': 252},
                                    'faixas': [{'lado': 'inferior', 'px': 48}]})}
    b = ap.briefing(formatos=[ap.formato('faixa', 480, 300, chave=chave)])
    d = _derivar(briefing=b, specs=specs)['formatos']['faixa']
    assert d['situacao'] == 'derivado', d['devolucao']
    assert d['areas']['area_util']['caixa'] == [0.0, 0.0, 480.0, 252.0]
    legal = _el(d, 'el40')
    assert legal['caixa'][3] <= 252 + 1
    folha = [r for r in d['restricoes'] if r['fonte'].get('tipo') == 'folha']
    assert folha and all(r['forca'] == 'obrigatoria' and r['fonte']['trecho'] for r in folha)
    assert any(v['nome'] == 'area_util_e_faixa' and v['situacao'] == 'ok' for v in d['validacoes'])
    # o fundo sangra por baixo da faixa
    assert _el(d, 'el1')['caixa'][3] >= 300


def test_folha_que_deixa_a_area_util_sem_area_ou_apertada_volta_com_nome_e_fonte():
    chave = 'teste|faixa|480x300'
    for px, nome in ((300, 'area_util_sem_area'), (299.9, 'dentro_da_area_util')):
        specs = {chave: ap.spec(chave, {'faixas': [{'lado': 'inferior', 'px': px}]})}
        # base pela composicao: pela area util, a faixa tiraria o formato da familia antes do solver
        b = ap.briefing(formatos=[ap.formato('f', 480, 300, chave=chave)], familias={'base': ap.decisao('composicao')})
        d = _derivar(briefing=b, specs=specs)['formatos']['f']
        dv = d['devolucao']
        assert d['situacao'] == 'devolvido' and dv['motivo'] == 'restricao_obrigatoria_nao_fecha'
        assert dv['restricao']['nome'].startswith(nome)
        assert dv['restricao']['fonte']['tipo'] == 'folha' and dv['restricao']['fonte']['trecho'] == 'p01-t001'


def test_area_segura_vale_para_texto_e_marca():
    chave = 'teste|segura|480x300'
    specs = {chave: ap.spec(chave, {'area_segura': {'pct': 20, 'px': None, 'lados': ['superior', 'inferior']}})}
    b = ap.briefing(formatos=[ap.formato('segura', 480, 300, chave=chave)])
    d = _derivar(briefing=b, specs=specs)['formatos']['segura']
    assert d['situacao'] == 'derivado', d['devolucao']
    for e in d['elementos']:
        if e['classe'] in ('texto', 'marca'):
            assert e['caixa'][1] >= 60 - 1 and e['caixa'][3] <= 240 + 1, e['id']
    assert any(v['nome'] == 'area_segura' for v in d['validacoes'])


def test_fora_da_peca_nunca_aparece_em_formato_derivado():
    rng = random.Random(3)
    formatos = [ap.formato('h%02d' % k, int(400 * f), int(200 * f * rng.uniform(0.8, 1.2)))
                for k, f in enumerate(rng.uniform(0.5, 3.0) for _ in range(20))]
    r = _derivar(briefing=ap.briefing(formatos=formatos))
    for d in r['formatos'].values():
        assert 50 in d['fora_da_peca']
        assert all(50 not in e['layer_ids'] for e in d['elementos'])
        assert all(e['funcao'] != 'fora_da_peca' for e in d['elementos'])


def test_indeterminado_sem_regra_devolve_todo_formato_e_com_regra_deriva():
    funcoes = {**ap.FUNCOES, 30: 'indeterminado'}
    formatos = [ap.formato('a', 800, 400), ap.formato('b', 480, 300), ap.formato('c', 300, 600)]
    r = _derivar(briefing=ap.briefing(funcoes=funcoes, formatos=formatos))
    assert all(d['devolucao']['motivo'] == 'indeterminado_sem_regra' for d in r['formatos'].values())
    r = _derivar(briefing=ap.briefing(funcoes=funcoes, formatos=formatos, indeterminado={30: 'constante'}))
    assert r['formatos']['b']['situacao'] == 'derivado'
    assert _el(r['formatos']['b'], 'el30')['regra'] == 'constante'


# ------------------------------------------------------------------ mutacao (defeito 1)
def test_mutacao_trocar_a_funcao_muda_a_regra_aplicada_no_layout_e_na_validacao():
    base = ap.briefing(formatos=[ap.formato('perto', 480, 300), ap.formato('mesmo', 800, 400)])
    ref = _derivar(briefing=base)
    casos = mudou_layout = mudou_validacao = mudou_geometria = com_regra_diferente = 0
    for lid in (10, 20, 30, 40):
        for nova in FUNCOES_COM_GEOMETRIA:
            if nova == ap.FUNCOES[lid]:
                continue
            funcoes = {**ap.FUNCOES, lid: nova}
            b = ap.briefing(funcoes=funcoes, formatos=base['formatos'],
                            regras={**ap.REGRAS, nova: ap.REGRAS.get(nova, 'largura')},
                            ancoras={**ap.ANCORAS, nova: ap.ANCORAS.get(nova, ('centro', 'meio'))})
            r = _derivar(briefing=b)
            for k in ('perto', 'mesmo'):
                d0, d1 = ref['formatos'][k], r['formatos'][k]
                if d1['situacao'] != 'derivado':
                    continue
                casos += 1
                e0, e1 = _el(d0, 'el%d' % lid), _el(d1, 'el%d' % lid)
                mudou_layout += e1['regra_aplicada'] != e0['regra_aplicada'] and e1['regra_aplicada']['funcao'] == nova
                v1 = next(v for v in d1['validacoes'] if v['nome'] == 'regra_por_funcao' and v['elementos'] == [e1['id']])
                mudou_validacao += v1['medidas']['funcao'] == nova and v1['situacao'] == 'ok'
                if b['regras_escala'] and dict((x['funcao'], x['regra']['valor']) for x in b['regras_escala'])[nova] != \
                        ap.REGRAS[ap.FUNCOES[lid]] and k == 'perto':
                    com_regra_diferente += 1
                    mudou_geometria += e1['caixa'] != e0['caixa'] or e1['escala'] != e0['escala']
    assert casos >= 60
    assert mudou_layout == casos and mudou_validacao == casos
    # a geometria muda quando a regra muda, salvo quando uma obrigatoria prende o elemento
    # a razao de corpo forte entre todas as funcoes de texto (decisoes-v1.md, 97) prende a escala do texto: a regra
    # fraca so muda a geometria quando a classe muda
    assert mudou_geometria > 0


def test_validacao_reprova_layout_com_funcao_que_nao_e_a_do_briefing():
    d = _derivar()['formatos']['perto']
    elementos = [dict(e, sangra={'esq': False, 'topo': False, 'dir': False, 'base': False}) for e in d['elementos']]
    esperado = {e['id']: (e['funcao'], e['regra']) for e in elementos}
    esperado['el20'] = ('texto_legal', 'constante')
    kv = {e['id']: {'caixa': e['caixa_mestre']} for e in elementos}
    val = mval.validar((480, 300), {}, elementos, [e['caixa'] for e in elementos], [e['escala'] for e in elementos],
                       kv, esperado)
    ruins = [v for v in mval.reprovadas(val) if v['nome'] == 'regra_por_funcao']
    assert [v['elementos'] for v in ruins] == [['el20']]


def test_escala_muito_longe_da_regra_avisa_sem_reprovar():
    sg = {'esq': False, 'topo': False, 'dir': False, 'base': False}
    el = {'id': 'el1', 'funcao': 'logo_principal', 'regra': 'raiz_area', 'classe': 'marca', 'sangra': sg,
          'escala_regra': 1.0}
    kv = {'el1': {'caixa': [0, 0, 10, 10]}}
    esperado = {'el1': ('logo_principal', 'raiz_area')}
    for s, aviso in ((0.6, False), (0.4, True), (2.1, True)):
        val = mval.validar((100, 100), {}, [el], [[0, 0, 10 * s, 10 * s]], [s], kv, esperado)
        assert any(v['nome'] == 'escala_longe_da_regra' and v['situacao'] == 'avisa' for v in val) == aviso
        assert not mval.reprovadas(val)


def test_colisao_nova_e_inventario_reprovam():
    sg = {'esq': False, 'topo': False, 'dir': False, 'base': False}
    els = [{'id': 'el1', 'funcao': 'titulo', 'regra': 'raiz_area', 'classe': 'texto', 'sangra': sg},
           {'id': 'el2', 'funcao': 'logo_principal', 'regra': 'raiz_area', 'classe': 'marca', 'sangra': sg}]
    kv = {'el1': {'caixa': [0, 0, 10, 10]}, 'el2': {'caixa': [20, 0, 30, 10]}, 'el3': {'caixa': [40, 0, 50, 10]}}
    esperado = {'el1': ('titulo', 'raiz_area'), 'el2': ('logo_principal', 'raiz_area')}
    val = mval.validar((100, 100), {}, els, [[0, 0, 25, 10], [20, 0, 30, 10]], [1.0, 1.0], kv, esperado)
    nomes = {v['nome'] for v in mval.reprovadas(val)}
    assert nomes == {'colisao_nova_contra_a_origem', 'inventario'}


# ------------------------------------------------------------------ mestre propria, mestres, base, rotacao
def _propria(caixas=None):
    caixas = caixas or {1: [0, 0, 300, 600], 10: [20, 40, 280, 140], 20: [20, 200, 280, 230], 30: [200, 500, 280, 580],
                        40: [20, 560, 180, 580]}
    return {'id': 'vertical', 'tipo': 'propria', 'formato': 'v300',
            'elementos': [{'layer_id': k, 'caixa': v, 'quebras': 'origem'} for k, v in sorted(caixas.items())]}


def test_mestre_propria_sai_das_caixas_do_da_e_vira_familia_dos_verticais():
    formatos = [ap.formato('v300', 300, 600), ap.formato('v320', 320, 560)]
    b = ap.briefing(formatos=formatos, mestres=[{'id': 'kv', 'tipo': 'kv'}, _propria()])
    r = _derivar(briefing=b)
    d = r['formatos']['v300']
    assert d['caminho'] == 'mestre_propria' and d['situacao'] == 'derivado', d['devolucao']
    t = _el(d, 'el10')
    assert t['caixa'][0] == 20 and t['caixa'][2] <= 280 and t['caixa'][3] <= 140
    d2 = r['formatos']['v320']
    assert d2['mestre']['id'] == 'vertical' and d2['situacao'] == 'derivado', d2['devolucao']
    assert d2['caminho'] in ('solver', 'transform')
    assert r['inventario']['iguais_entre_formatos']


def test_mestre_propria_incompleta_e_acima_do_numero_de_mestres_voltam():
    caixas = {1: [0, 0, 300, 600], 10: [20, 40, 280, 140]}
    b = ap.briefing(formatos=[ap.formato('v300', 300, 600)], mestres=[{'id': 'kv', 'tipo': 'kv'}, _propria(caixas)])
    d = _derivar(briefing=b)['formatos']['v300']
    assert d['devolucao']['motivo'] == 'mestre_propria_incompleta' and set(d['devolucao']['elementos']) == {'el20', 'el30', 'el40'}
    b = ap.briefing(formatos=[ap.formato('v300', 300, 600), ap.formato('v320', 320, 560)],
                    mestres=[{'id': 'kv', 'tipo': 'kv'}, _propria()], familias={'mestres_max': ap.decisao(1)})
    r = _derivar(briefing=b)
    # a propria que passa do numero vira acima_do_numero_de_mestres; o formato sem familia guarda o motivo dele
    assert r['formatos']['v300']['devolucao']['motivo'] == 'acima_do_numero_de_mestres'
    assert r['formatos']['v320']['devolucao']['motivo'] == 'troca_forte_de_orientacao'


def test_base_do_calculo_muda_a_escala_da_regra():
    chave = 'teste|faixa|480x300'
    specs = {chave: ap.spec(chave, {'faixas': [{'lado': 'inferior', 'px': 60}]})}
    out = {}
    for base in ('arquivo', 'area_util'):
        b = ap.briefing(formatos=[ap.formato('f', 480, 300, chave=chave)], familias={'base': ap.decisao(base)})
        d = _derivar(briefing=b, specs=specs)['formatos']['f']
        out[base] = _el(d, 'el10')['escala_regra']
        assert d['formato']['base']['tipo'] == base
    assert math.isclose(out['arquivo'], math.sqrt(480 * 300 / 80000), rel_tol=1e-6)
    assert math.isclose(out['area_util'], math.sqrt(480 * 240 / 80000), rel_tol=1e-6)


def test_rotacao_gira_a_composicao():
    f = ap.formato('girado', 300, 480, rotacao={'graus': 90, 'sentido': 'horario'})
    assert mfmt.composicao(f) == (480, 300)
    d = _derivar(briefing=ap.briefing(formatos=[f]))['formatos']['girado']
    assert d['formato']['composicao'] == [480, 300] and d['situacao'] == 'derivado'


def test_derivacao_e_deterministica_e_segue_o_contrato():
    a, b = _derivar(), _derivar()
    for k in a['formatos']:
        x, y = dict(a['formatos'][k]), dict(b['formatos'][k])
        x.pop('gerado_em'), y.pop('gerado_em')
        assert x == y
        contratos.validar(a['formatos'][k], 'derivacao/1')


def test_derivacao_e_a_mesma_em_processos_diferentes(tmp_path, python):
    import json
    import subprocess
    codigo = chr(10).join([
        'import sys, json; sys.path[:0] = [%r, %r]',
        'lixo = [object() for _ in range(int(sys.argv[1]))]',
        'import test_derivacao_apoio as ap',
        'from desdobra.derivacao import nucleo as nd',
        "saida = {}",
        "r = nd.derivar_em_memoria(nd.contexto(ap.laudo(), ap.briefing()), specs={})",
        "saida.update({k: d['elementos'] for k, d in r['formatos'].items()})",
        "laudo, funcoes = ap.laudo_degenerado()",
        "fmts = [ap.formato('d%%d' %% k, w, h, chave='teste|faixa|1080x1920') for k, (w, h) in "
        "enumerate([(1080, 1920), (360, 1080), (400, 600), (320, 448), (960, 1544)])]",
        "specs = {'teste|faixa|1080x1920': ap.spec('teste|faixa|1080x1920', {'area_util': {'largura': 1080, "
        "'altura': 1848}, 'faixas': [{'lado': 'inferior', 'px': 72}]})}",
        "r = nd.derivar_em_memoria(nd.contexto(laudo, ap.briefing(funcoes=funcoes, formatos=fmts)), specs=specs)",
        "saida.update({k: [d['situacao'], d['elementos']] for k, d in r['formatos'].items()})",
        "print(json.dumps(saida, sort_keys=True))",
    ]) % (str(Path(__file__).parent), str(Path(__file__).parent.parent / 'motor'))
    saidas = set()
    for n in (0, 777, 31337, 5, 4242, 123):
        r = subprocess.run([python, '-c', codigo, str(n)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-500:]
        saidas.add(r.stdout)
    assert len(saidas) == 1 and json.loads(saidas.pop())


def test_derivacao_nao_le_nome_de_camada():
    laudo = ap.laudo()
    outro = ap.copia(laudo)
    for c in outro['camadas']:
        c['nome'] = 'logo titulo fundo legal %d' % c['identidade']['layer_id']
    a, b = _derivar(laudo=laudo), _derivar(laudo=outro)
    for k in a['formatos']:
        assert a['formatos'][k]['elementos'] == b['formatos'][k]['elementos']


def test_limites_novos_da_derivacao_tem_fonte_e_nao_reprovam():
    for lid in ('derivacao.faixa_familia_razao_max', 'derivacao.base_calculo', 'derivacao.mestres_max',
                'derivacao.quadrado_ln_max', 'derivacao.mesma_proporcao_px', 'derivacao.alinhamento_tolerancia_px',
                'derivacao.colisao_tolerancia_px', 'derivacao.enquadramento_tolerancia_px', 'derivacao.escala_min',
                'derivacao.tolerancia_regra_escala'):
        lim = limites.obter(lid)
        assert lim.fonte and lim.situacao == 'a_calibrar' and limites.efeito(lid) != 'reprova'


def test_alinhamentos_da_mestre_viram_restricao_forte():
    els = [{'id': 'a', 'caixa': [10, 10, 50, 20]}, {'id': 'b', 'caixa': [10, 40, 90, 60]},
           {'id': 'c', 'caixa': [100, 10, 140, 20]}]
    al = msol.alinhamentos(els, 2.0)
    assert ('x', 'inicio', 0, 1) in al and ('y', 'inicio', 0, 2) in al and ('y', 'fim', 0, 2) in al
    assert not any(t == (0, 1) for *_x, i, j in al for t in [(i, j)] if _x == ['y', 'inicio'])


def test_pares_disjuntos_sao_separados_pelo_eixo_da_mestre():
    assert msol._disjuntas([0, 0, 10, 10], [20, 0, 30, 10], 0.0)[0][:2] == ('x', True)
    assert msol._disjuntas([0, 20, 10, 30], [0, 0, 10, 10], 0.0)[0][:2] == ('y', False)
    assert msol._disjuntas([0, 0, 10, 10], [5, 5, 15, 15], 0.0) == []


def test_familias_combinam_todos_os_pares():
    for (w1, h1), (w2, h2) in itertools.product([(400, 200), (200, 400), (300, 300)], repeat=2):
        f = mfmt.familia((w1, h1), (w2, h2), 2.0)
        assert f['na_faixa'] == (f['troca'] is None and f['fator'] <= 2.0)
