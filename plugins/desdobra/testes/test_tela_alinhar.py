# -*- coding: utf-8 -*-
"""M7b, D2: alinhar no quadro com a intencao do DA (decisoes-v1.md, 167 e 168; secao 9.8 da arquitetura), escrito
antes do codigo.

Criterios de pronto cobertos aqui:
  - a edicao alinhar leva o elemento, ou o grupo (elementos), a margem esquerda, a direita, ao topo, a base, ao centro
    na largura ou ao centro na altura do quadro de cada membro da familia, pela margem dele ou pela area segura dele;
  - a intencao fica valendo depois da edicao: a intencao de alinhamento entre elementos (168) e o encaixe refeito pelo
    solver nao tiram o bloco da margem. Mexer no bloco depois, naquele eixo, troca a intencao pela edicao nova;
  - os esquemas do rascunho e do briefing aceitam a edicao com alvo e referencia, tambem com o grupo;
  - na derivacao da fixture com a estrutura do KV A (titulo, linha, apoio, icones, packshot e assinatura), nas
    familias do 2048x720 e do 1008x432, o bloco de texto fica com a borda esquerda na margem e o centro na metade da
    altura em cada membro, dentro de 1 px;
  - na tela (Chromium sem janela): os botoes de alinhar gravam uma edicao so, para o elemento ou para o grupo, e a
    previa mostra cada membro com o bloco no lugar pedido.
Tudo sintetico: laudo montado a mao, PSD sintetico gerado na hora e a fonte de autoteste do motor."""
import pytest

import test_derivacao_apoio as ap
from desdobra import contratos
from desdobra.briefing import modelo as mb
from desdobra.derivacao import galeria as mg
from desdobra.derivacao import nucleo as nd
from desdobra.derivacao import proposta
from desdobra.derivacao import solver as mod_solver
from desdobra.tela import edicao as ed
from desdobra.tela import rascunho as tr
from test_tela_grupo import conteudo_grupo, job_grupo  # noqa: F401 - as fixtures do job sintetico com o packshot

CONF = {'origem': 'fixture_de_teste', 'meio': 'medicao', 'em': '2026-11-11T10:00:00-03:00'}
TOL = 1.0  # numero-neutro: px de folga do criterio de pronto do D2


def _uniao(cs):
    return [min(c[0] for c in cs), min(c[1] for c in cs), max(c[2] for c in cs), max(c[3] for c in cs)]


# ------------------------------------------------------------------ a conta, sem job
QUADROS = {'margem': [40.0, 20.0, 360.0, 180.0], 'area_segura': [10.0, 10.0, 390.0, 190.0]}


@pytest.mark.parametrize('alvo, referencia, esperado', [
    ('margem_esquerda', 'margem', ('x', 0, 40.0)),
    ('margem_direita', 'margem', ('x', 2, 360.0)),
    ('topo', 'margem', ('y', 1, 20.0)),
    ('base', 'margem', ('y', 3, 180.0)),
    ('centro_horizontal', 'margem', ('x', None, 200.0)),
    ('centro_vertical', 'margem', ('y', None, 100.0)),
    ('margem_esquerda', 'area_segura', ('x', 0, 10.0)),
    ('base', 'area_segura', ('y', 3, 190.0)),
])
def test_alinhar_um_elemento_no_quadro(alvo, referencia, esperado):
    caixas = {'a': [100.0, 50.0, 160.0, 80.0], 'b': [0.0, 0.0, 5.0, 5.0]}
    e = {'elemento': 'a', 'acao': 'alinhar', 'alvo': alvo, 'referencia': referencia}
    depois, apagados, _t, mexidos = ed.aplicar(caixas, [e], 400, 200, QUADROS)
    eixo, i, valor = esperado
    c = depois['a']
    if i is None:
        k0, k1 = (0, 2) if eixo == 'x' else (1, 3)
        assert (c[k0] + c[k1]) / 2.0 == pytest.approx(valor)
    else:
        assert c[i] == pytest.approx(valor)
    # so desloca, no eixo do alvo: o tamanho e o outro eixo ficam
    assert c[2] - c[0] == pytest.approx(60.0) and c[3] - c[1] == pytest.approx(30.0)
    if eixo == 'x':
        assert (c[1], c[3]) == (50.0, 80.0)
    else:
        assert (c[0], c[2]) == (100.0, 160.0)
    assert depois['b'] == caixas['b'] and apagados == [] and mexidos == ['a']


def test_alinhar_o_grupo_leva_a_caixa_que_junta_o_grupo_e_cada_membro_usa_a_margem_dele():
    caixas = {'t': [100.0, 30.0, 300.0, 60.0], 'l': [100.0, 66.0, 180.0, 70.0], 'p': [104.0, 76.0, 260.0, 96.0]}
    grupo = ['t', 'l', 'p']
    eds = [{'elemento': 't', 'elementos': grupo, 'acao': 'alinhar', 'alvo': 'margem_esquerda', 'referencia': 'margem'},
           {'elemento': 't', 'elementos': grupo, 'acao': 'alinhar', 'alvo': 'centro_vertical', 'referencia': 'margem'}]
    for W, H, q in ((400, 200, [20.0, 10.0, 380.0, 190.0]), (1000, 300, [50.0, 30.0, 950.0, 270.0])):
        depois, _a, _t, mexidos = ed.aplicar(caixas, eds, W, H, {'margem': q, 'area_segura': [0, 0, W, H]})
        u = _uniao([depois[k] for k in grupo])
        assert u[0] == pytest.approx(q[0]) and (u[1] + u[3]) / 2.0 == pytest.approx((q[1] + q[3]) / 2.0)
        # o grupo anda inteiro: as distancias entre os membros ficam
        for k in grupo:
            assert depois[k][0] - depois['t'][0] == pytest.approx(caixas[k][0] - caixas['t'][0])
            assert depois[k][1] - depois['t'][1] == pytest.approx(caixas[k][1] - caixas['t'][1])
        assert sorted(mexidos) == sorted(grupo)
    # sem quadros, o quadro e a peca inteira
    depois = ed.aplicar(caixas, eds[:1], 400, 200)[0]
    assert _uniao([depois[k] for k in grupo])[0] == pytest.approx(0.0)


def test_o_grupo_alinhado_vira_grupo():
    eds = [{'elemento': 'a', 'elementos': ['a', 'b'], 'acao': 'alinhar', 'alvo': 'topo', 'referencia': 'margem'}]
    assert ed.grupos(eds) == [['a', 'b']]
    # alinhar um so tira ele do grupo, como mover um so
    assert ed.grupos(eds + [{'elemento': 'a', 'acao': 'alinhar', 'alvo': 'base', 'referencia': 'margem'}]) == []


def test_intencoes_que_ficam_depois_das_edicoes():
    esq = {'elemento': 'a', 'elementos': ['a', 'b'], 'acao': 'alinhar', 'alvo': 'margem_esquerda',
           'referencia': 'margem'}
    meio = {'elemento': 'a', 'elementos': ['a', 'b'], 'acao': 'alinhar', 'alvo': 'centro_vertical',
            'referencia': 'area_segura'}
    assert ed.intencoes([esq, meio]) == [
        {'elementos': ['a', 'b'], 'eixo': 'x', 'alvo': 'margem_esquerda', 'referencia': 'margem'},
        {'elementos': ['a', 'b'], 'eixo': 'y', 'alvo': 'centro_vertical', 'referencia': 'area_segura'}]
    # mover o grupo so na altura tira a intencao da altura e deixa a da largura
    mover_y = {'elemento': 'a', 'elementos': ['a', 'b'], 'acao': 'mover', 'dx': 0.0, 'dy': 0.02}
    assert [i['alvo'] for i in ed.intencoes([esq, meio, mover_y])] == ['margem_esquerda']
    # mover um so na largura tira so ele da intencao da largura
    mover_x = {'elemento': 'b', 'acao': 'mover', 'dx': 0.01, 'dy': 0.0}
    assert ed.intencoes([esq, mover_x])[0]['elementos'] == ['a']
    # escalar troca a intencao pela edicao nova nos dois eixos; apagar tira o elemento
    escalar = {'elemento': 'a', 'elementos': ['a', 'b'], 'acao': 'escalar', 'fator': 1.2}
    assert ed.intencoes([esq, meio, escalar]) == []
    assert ed.intencoes([esq, {'elemento': 'a', 'acao': 'apagar'}])[0]['elementos'] == ['b']
    # o alinhamento novo no mesmo eixo vale sobre o de antes; o texto nao mexe
    dir_ = dict(esq, alvo='margem_direita')
    assert [i['alvo'] for i in ed.intencoes([esq, dir_, {'elemento': 'a', 'acao': 'texto', 'texto': 'X'}])] == \
        ['margem_direita']


def test_intencao_de_alinhamento_nao_tira_o_bloco_da_margem():
    # t foi alinhado a margem (preso na largura); o, mexido depois, para a 5 px da esquerda dele: o vem para a linha
    # de t, e t fica na margem
    caixas = {'t': [40.0, 100.0, 300.0, 140.0], 'o': [45.0, 400.0, 200.0, 450.0]}
    novas, alinhados = ed.normalizar(caixas, ['o'], 1920, 1080, presos={('t', 'x')})
    assert novas['t'] == caixas['t'] and novas['o'][0] == pytest.approx(40.0)
    assert [(a['elementos'], a['eixo']) for a in alinhados] == [(['o', 't'], 'x')]
    # o mexido preso: nada anda naquele eixo (decisao 185); antes, o outro vinha para a linha dele
    novas, alinhados = ed.normalizar(caixas, ['t'], 1920, 1080, presos={('t', 'x')})
    assert novas == caixas and alinhados == []
    # os dois presos: nenhum anda
    novas, alinhados = ed.normalizar(caixas, ['o'], 1920, 1080, presos={('t', 'x'), ('o', 'x')})
    assert novas == caixas and alinhados == []


def test_quadros_do_membro_pela_margem_e_pela_area_segura():
    cf = {'W': 1000.0, 'H': 500.0, 'quadro': [50.0, 40.0, 950.0, 460.0],
          'areas': {'area_segura': {'caixa': [20.0, 20.0, 980.0, 480.0]}}}
    assert proposta.quadros_do_membro(cf) == {'margem': [50.0, 40.0, 950.0, 460.0],
                                              'area_segura': [20.0, 20.0, 980.0, 480.0]}
    # revisao 2 da fase D: sem area segura na folha, a area segura do membro e a margem dele (como a pagina diz)
    sem = dict(cf, areas={})
    assert proposta.quadros_do_membro(sem)['area_segura'] == [50.0, 40.0, 950.0, 460.0]


# ------------------------------------------------------------------ os esquemas
def _rascunho(edicoes):
    return {'esquema': tr.ESQUEMA, 'job_id': '0' * 32, 'laudo_sha256': '0' * 64, 'origem': 'rascunho',
            'atualizado_em': '2026-11-11T10:00:00', 'familias': {'h-1': {'versao': None, 'confirmada': False,
                                                                       'edicoes': edicoes}}}


@pytest.mark.parametrize('edicao, vale', [
    ({'elemento': 'el11', 'acao': 'alinhar', 'alvo': 'margem_esquerda', 'referencia': 'margem'}, True),
    ({'elemento': 'el11', 'elementos': ['el11', 'el20'], 'acao': 'alinhar', 'alvo': 'centro_vertical',
      'referencia': 'area_segura'}, True),
    ({'elemento': 'el11', 'acao': 'alinhar', 'referencia': 'margem'}, False),
    ({'elemento': 'el11', 'acao': 'alinhar', 'alvo': 'margem_esquerda'}, False),
    ({'elemento': 'el11', 'acao': 'alinhar', 'alvo': 'meio', 'referencia': 'margem'}, False),
    ({'elemento': 'el11', 'acao': 'alinhar', 'alvo': 'topo', 'referencia': 'folha'}, False),
    ({'elemento': 'el11', 'acao': 'mover', 'dx': 0.0, 'dy': 0.0, 'alvo': 'topo', 'referencia': 'margem'}, False),
])
def test_esquemas_aceitam_alinhar_com_alvo_e_referencia(edicao, vale):
    def passa(dado, esquema):
        try:
            contratos.validar(dado, esquema)
            return True
        except contratos.ErroContrato:
            return False
    assert passa(_rascunho([edicao]), tr.ESQUEMA) is vale
    assert passa(_briefing([edicao]), mb.ESQUEMA) is vale


# ------------------------------------------------------------------ a derivacao da fixture com a estrutura do KV A
# KV A sintetico 400 x 200: fundo, bloco de texto a esquerda (titulo, linha, apoio), dois icones embaixo do bloco,
# packshot a direita (circulo de fundo, garrafa, copo e lata) e a assinatura no canto
FUNDO, TITULO, LINHA, APOIO, ICONE1, ICONE2, ASSINATURA = 1, 11, 12, 20, 21, 22, 30
CIRCULO, GARRAFA, COPO, LATA = 40, 41, 42, 43
CAIXAS_KV = {FUNDO: [0, 0, 400, 200], TITULO: [24, 40, 200, 72], LINHA: [24, 80, 120, 84], APOIO: [24, 92, 190, 112],
             ICONE1: [24, 124, 44, 144], ICONE2: [52, 124, 72, 144], ASSINATURA: [330, 166, 380, 186],
             CIRCULO: [250, 40, 370, 160], GARRAFA: [270, 50, 300, 160], COPO: [306, 100, 330, 160],
             LATA: [336, 96, 360, 160]}
TIPOS = {FUNDO: 'pixel', TITULO: 'texto', LINHA: 'forma', APOIO: 'texto', ICONE1: 'pixel', ICONE2: 'pixel',
         ASSINATURA: 'smart_embutido', CIRCULO: 'pixel', GARRAFA: 'pixel', COPO: 'pixel', LATA: 'pixel'}
CORPOS = {TITULO: 28, APOIO: 12}
FUN = {FUNDO: 'fundo', TITULO: 'titulo', LINHA: 'grafismo', APOIO: 'texto_de_apoio', ICONE1: 'icone_de_cta',
       ICONE2: 'icone_de_cta', ASSINATURA: 'logo_principal', CIRCULO: 'grafismo', GARRAFA: 'sujeito', COPO: 'sujeito',
       LATA: 'sujeito'}
# o bloco de texto: titulo, linha, apoio e os icones embaixo dele
BLOCO = ['el%d' % k for k in (TITULO, LINHA, APOIO, ICONE1, ICONE2)]
# as duas familias do criterio: o 2048x720 e o 1008x432, cada um com um irmao de proporcao parecida
FAMILIAS = {'horizontal-larga': [('a1', 2048, 720), ('a2', 1900, 700)],
            'horizontal-media': [('b1', 1008, 432), ('b2', 1100, 450)]}
NO_QUADRO = [{'elemento': BLOCO[0], 'elementos': BLOCO, 'acao': 'alinhar', 'alvo': 'margem_esquerda',
              'referencia': 'margem'},
             {'elemento': BLOCO[0], 'elementos': BLOCO, 'acao': 'alinhar', 'alvo': 'centro_vertical',
              'referencia': 'margem'}]


def _laudo():
    return ap.laudo(400, 200, [ap.camada(k, TIPOS[k], CAIXAS_KV[k], corpo=CORPOS.get(k)) for k in sorted(CAIXAS_KV)])


def _briefing(edicoes, familias=None):
    familias = FAMILIAS if familias is None else familias
    formatos = [ap.formato(i, w, h) for fs in familias.values() for i, w, h in fs]
    b = ap.briefing(funcoes=FUN, formatos=formatos or [ap.formato('a1', 2048, 720)],
                    regras=dict(ap.REGRAS, icone_de_cta='raiz_area'),
                    ancoras=dict(ap.ANCORAS, icone_de_cta=('esquerda', 'meio')))
    b['composicoes'] = [{'familia': g, 'formatos': [i for i, _w, _h in fs], 'versao': None, 'edicoes': list(edicoes),
                         'confirmada': True, 'confirmacao': dict(CONF)} for g, fs in familias.items()]
    return b


def _derivar(edicoes):
    b = _briefing(edicoes)
    contratos.validar(b, mb.ESQUEMA)
    assert mb.conferir(_laudo(), b) == []
    ctx = nd.contexto(_laudo(), b)
    return ctx, nd.derivar_em_memoria(ctx, specs={})['formatos']


def _caixas(d):
    return {e['id']: [float(x) for x in e['caixa']] for e in d['elementos']}


def _quadro_do_membro(ctx, fid):
    f = next(x for x in ctx['briefing']['formatos'] if x['id'] == fid)
    kv = nd.mestre_do_kv(ctx)
    cf = mg.contexto_do_formato(ctx, proposta.mestre_do_membro(ctx, kv, f, {'situacao': 'derivado'}), f, specs={})
    return cf['quadro']


def test_derivacao_poe_o_bloco_de_texto_na_margem_e_no_meio_da_altura_em_cada_membro():
    ctx, antes = _derivar([])
    _ctx, depois = _derivar(NO_QUADRO)
    for fs in FAMILIAS.values():
        for fid, w, h in fs:
            a, d = antes[fid], depois[fid]
            assert d['situacao'] == 'derivado', (fid, d.get('devolucao'))
            q = _quadro_do_membro(ctx, fid)
            u = _uniao([_caixas(d)[k] for k in BLOCO])
            assert abs(u[0] - q[0]) <= TOL, (fid, u, q)
            assert abs((u[1] + u[3]) / 2.0 - h / 2.0) <= TOL, (fid, u, h)
            # o bloco so andou: o tamanho de cada elemento dele fica o da proposta
            ca, cd = _caixas(a), _caixas(d)
            for k in BLOCO:
                assert cd[k][2] - cd[k][0] == pytest.approx(ca[k][2] - ca[k][0], abs=TOL), (fid, k)
                assert cd[k][3] - cd[k][1] == pytest.approx(ca[k][3] - ca[k][1], abs=TOL), (fid, k)
            origem = {e['id']: e['origem_geometria'] for e in d['elementos']}
            assert all(origem[k] == 'da' for k in BLOCO), origem


def test_encaixe_refeito_nao_tira_o_bloco_da_margem(monkeypatch):
    # o solver que empurra o bloco (aqui de mentira, 7 px para a direita e para baixo) nao tira o bloco do lugar que o
    # DA pediu: o alinhamento no quadro e firmado de novo depois do encaixe refeito
    ctx, antes = _derivar([])
    kv = nd.mestre_do_kv(ctx)
    f = next(x for x in ctx['briefing']['formatos'] if x['id'] == 'a1')
    cf = mg.contexto_do_formato(ctx, proposta.mestre_do_membro(ctx, kv, f, antes['a1']), f, specs={})
    real = mg.reencaixar

    def empurra(cf_, caixas, sangra, apagados=(), do_da=()):
        cs, falha = real(cf_, caixas, sangra, apagados, do_da)
        return {k: ([v[0] + 7.0, v[1] + 7.0, v[2] + 7.0, v[3] + 7.0] if k in BLOCO else v) for k, v in cs.items()}, falha
    monkeypatch.setattr(mg, 'reencaixar', empurra)
    extra = {'kv_por_id': {e['id']: e for e in kv['elementos']},
             'conteudo': [e['id'] for e in kv['elementos'] if mod_solver.conteudo(e)],
             'kv_caixas': {e['id']: [float(x) for x in e['caixa']] for e in kv['elementos']},
             'kv_tamanho': (float(kv['largura']), float(kv['altura']))}
    lay = proposta.layout_do_membro(cf, antes['a1']['elementos'], NO_QUADRO, **extra)
    u = _uniao([lay['caixas'][k] for k in BLOCO])
    assert abs(u[0] - cf['quadro'][0]) <= TOL and abs((u[1] + u[3]) / 2.0 - cf['H'] / 2.0) <= TOL, (u, cf['quadro'])
    assert sorted(x['alvo'] for x in lay['no_quadro']) == ['centro_vertical', 'margem_esquerda']
    assert lay['quadros']['margem'] == pytest.approx(cf['quadro'])


def test_mover_o_bloco_depois_de_alinhar_vale_a_edicao_nova():
    # alinhar na margem e depois mover para a direita: o bloco fica onde o DA o deixou, nao volta para a margem
    _ctx, so_alinhado = _derivar(NO_QUADRO[:1])
    mover = {'elemento': BLOCO[0], 'elementos': BLOCO, 'acao': 'mover', 'dx': 0.03, 'dy': 0.0}
    _ctx, movido = _derivar(NO_QUADRO[:1] + [mover])
    for fs in FAMILIAS.values():
        for fid, w, _h in fs:
            u0 = _uniao([_caixas(so_alinhado[fid])[k] for k in BLOCO])
            u1 = _uniao([_caixas(movido[fid])[k] for k in BLOCO])
            assert u1[0] - u0[0] == pytest.approx(0.03 * w, abs=TOL), fid


# ------------------------------------------------------------------ a previa da tela
def _familia(conteudo):
    return next(g for g, f in conteudo['familias'].items() if 'h1' in f['formatos'])


def test_previa_alinha_o_grupo_em_cada_arquivo_com_a_margem_dele(job_grupo, conteudo_grupo):  # noqa: F811
    gid = _familia(conteudo_grupo)
    grupo = job_grupo['grupo']
    eds = [{'elemento': grupo[0], 'elementos': grupo, 'acao': 'alinhar', 'alvo': 'margem_direita',
            'referencia': 'margem'},
           {'elemento': grupo[0], 'elementos': grupo, 'acao': 'alinhar', 'alvo': 'centro_vertical',
            'referencia': 'margem'}]
    r = conteudo_grupo['editar']({'familia': gid, 'versao': None, 'edicoes': eds})
    assert r is not None and len(r['membros']) == 3  # numero-neutro: os tres arquivos da familia
    for m in r['membros']:
        q = m['quadro']['margem']
        cs = {e['id']: [float(x) for x in e['caixa']] for e in m['palco']['elementos']}
        u = _uniao([cs[k] for k in grupo])
        assert abs(u[2] - q[2]) <= TOL and abs((u[1] + u[3]) / 2.0 - (q[1] + q[3]) / 2.0) <= TOL, (m['formato'], u, q)
    # a previa diz onde cada alinhamento ficou, para a linha no palco
    feitos = [(x['formato'], x['alvo']) for x in r['no_quadro']]
    assert sorted(feitos) == sorted((m['formato'], a) for m in r['membros']
                                    for a in ('margem_direita', 'centro_vertical'))


# ------------------------------------------------------------------ a tela no Chromium sem janela (modo de teste)
def test_alinhar_na_tela_do_chromium(job_grupo, conteudo_grupo):  # noqa: F811
    from playwright.sync_api import sync_playwright

    import test_tela_galeria as tg
    import test_tela_grupo as tgr
    import test_tela_palco as tp
    from desdobra.chromium import navegador
    from desdobra.tela import atos as ta
    from desdobra.tela import servidor as ts
    job, grupo = job_grupo['job'], job_grupo['grupo']
    tgr._limpar_rascunho(job)
    estado = conteudo_grupo['estado']
    gid = _familia(conteudo_grupo)
    titulo = next(e['id'] for e in conteudo_grupo['editar']({'familia': gid, 'versao': None, 'edicoes': []})
                  ['membros'][0]['palco']['elementos'] if e['funcao'] == 'titulo')
    salvo = '() => (document.documentElement.dataset.rascunho === "salvo" && ' \
            'document.documentElement.dataset.previa === "pronta") ? "1" : ""'
    navegador.apontar_playwright()
    with ts.ServidorTela(conteudo_grupo, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo_grupo)) as srv, sync_playwright() as pw:
        nav, pg = tp._pagina_da_tela(pw, srv, 2048, 720)  # numero-neutro: a tela do Duda (decisao 157)
        try:
            tg._abrir(pg, estado, 'h1')
            tp._esperar(pg, '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""')
            botoes = ['ed-al-esquerda', 'ed-al-centro', 'ed-al-direita', 'ed-al-topo', 'ed-al-meio', 'ed-al-base']
            # sem nada escolhido, os botoes de alinhar ficam desligados; a area segura so liga com area segura
            assert all(pg.evaluate('i => document.getElementById(i).disabled', b) for b in botoes)
            assert pg.evaluate('() => document.getElementById("ed-ref-margem").getAttribute("aria-pressed")') == 'true'
            assert pg.evaluate('() => document.getElementById("ed-ref-segura").disabled') is True
            # um elemento: o titulo vai a margem esquerda, com um clique
            x, y = tgr._ponto(pg, titulo)
            pg.mouse.click(x, y)
            assert not any(pg.evaluate('i => document.getElementById(i).disabled', b) for b in botoes)
            rotulos = [pg.evaluate('i => document.getElementById(i).textContent.trim()', b) for b in botoes]
            # revisao 1 da fase D: os dois centros dizem de qual medida sao (no meio e no centro sao a mesma palavra)
            assert rotulos == ['À esquerda', 'Centro da largura', 'À direita', 'No topo', 'Meio da altura', 'Na base']
            pg.evaluate('() => document.getElementById("ed-al-esquerda").click()')
            tp._esperar(pg, salvo)
            eds = tgr._edicoes(job, gid)
            assert eds == [{'elemento': titulo, 'acao': 'alinhar', 'alvo': 'margem_esquerda', 'referencia': 'margem'}]
            assert 'margem' in pg.evaluate('() => document.getElementById("ed-mensagem").textContent')
            assert pg.evaluate('() => document.querySelectorAll("#palco .guia").length') >= 1
            # o grupo do packshot: clique no primeiro, Shift+clique nos outros, depois "Na base"; uma edicao so, com a
            # lista
            x, y = tgr._ponto(pg, grupo[0])
            pg.mouse.click(x, y)
            for eid in grupo[1:]:
                tgr._shift_clique(pg, eid)
            pg.evaluate('() => document.getElementById("ed-al-base").click()')
            tp._esperar(pg, salvo)
            eds = tgr._edicoes(job, gid)
            assert eds[-1] == {'elemento': grupo[0], 'elementos': grupo, 'acao': 'alinhar', 'alvo': 'base',
                               'referencia': 'margem'}
            r = conteudo_grupo['editar']({'familia': gid, 'versao': None, 'edicoes': eds})
            for m in r['membros']:
                q = m['quadro']['margem']
                cs = {e['id']: [float(v) for v in e['caixa']] for e in m['palco']['elementos']}
                assert abs(cs[titulo][0] - q[0]) <= TOL, m['formato']
                assert abs(_uniao([cs[k] for k in grupo])[3] - q[3]) <= TOL, m['formato']
            # o palco mostra o grupo no lugar que a previa devolveu
            grupo_no_palco = pg.evaluate('''ids => { const m = document.getElementById('palco');
                return ids.map(i => m.querySelector('.rotulo[data-elemento="' + i + '"]') ? 1 : 0); }''', grupo)
            assert grupo_no_palco == [1, 1, 1]
            texto = pg.evaluate(tp.JS_TEXTO_DA_MOLDURA)
            assert not tp.IDENTIFICADOR.findall(texto), tp.IDENTIFICADOR.findall(texto)
            assert '—' not in texto and '–' not in texto
        finally:
            nav.close()
        contagem = dict(srv.contagem)
    assert contagem['proibido'] == 0 and contagem['csrf_recusado'] == 0 and contagem['dado_recusado'] == 0
    tgr._limpar_rascunho(job)
