# -*- coding: utf-8 -*-
"""M7b, D1: varios elementos escolhidos juntos no palco andam e mudam de tamanho como um grupo (decisoes-v1.md, 167 e
168; secao 9.8 da arquitetura), escrito antes do codigo.

Criterios de pronto cobertos aqui:
  - mover e escalar aceitam a lista dos elementos do grupo (elementos), com o ponto fixo do escalar em fracao da caixa
    que junta o grupo no formato: cada membro da familia escala o grupo em volta do mesmo ponto dele, e as distancias
    entre os elementos do grupo mudam na mesma razao do tamanho (nada se afasta);
  - a intencao de alinhamento (168) nunca separa o grupo: os elementos do mesmo grupo nao se alinham entre si, e o
    grupo que encosta na linha de outro elemento anda inteiro, tambem o elemento do grupo que nao e de conteudo;
  - o esquema do rascunho e o do briefing aceitam a lista so em mover e escalar, com dois elementos ou mais e sem
    repetir; a previa recusa o elemento que o KV nao tem;
  - a derivacao da familia confirmada e a previa da tela levam o grupo do mesmo jeito: a garrafa, o copo e o circulo
    do packshot sintetico escalam juntos em volta do mesmo ponto em todos os formatos da familia;
  - na tela (Chromium sem janela): Shift+clique, o botao "Escolher vários" e o retangulo de selecao escolhem o grupo;
    arrastar, as setas, Diminuir e Aumentar e o canto da caixa do grupo gravam uma edicao so, com a lista.
Tudo sintetico: laudo montado a mao, PSD sintetico gerado na hora e a fonte de autoteste do motor."""
import copy
import json

import pytest

import test_derivacao_apoio as ap
from desdobra import contratos
from desdobra.briefing import modelo as mb
from desdobra.derivacao import nucleo as nd
from desdobra.tela import edicao as ed
from desdobra.tela import rascunho as tr

CONF = {'origem': 'fixture_de_teste', 'meio': 'medicao', 'em': '2026-11-11T10:00:00-03:00'}
# o packshot sintetico: o circulo de fundo (grafismo), a garrafa e o copo (sujeito), no canto direito do KV 400 x 200
CIRCULO, GARRAFA, COPO = 40, 41, 42
CAIXAS_KV = {CIRCULO: [250, 50, 370, 170], GARRAFA: [275, 60, 305, 165], COPO: [315, 110, 345, 165]}
GRUPO = ['el%d' % GARRAFA, 'el%d' % COPO, 'el%d' % CIRCULO]
FUN = {1: 'fundo', 30: 'logo_principal', CIRCULO: 'grafismo', GARRAFA: 'sujeito', COPO: 'sujeito'}
# uma familia horizontal de tres arquivos (derivacao.grupo_proporcao_dif_max)
HORIZONTAIS = [('h1', 800, 400), ('h2', 840, 400), ('h3', 880, 400)]
TOL = 0.5  # numero-neutro: px de folga do arredondamento da derivacao


def _uniao(cs):
    return [min(c[0] for c in cs), min(c[1] for c in cs), max(c[2] for c in cs), max(c[3] for c in cs)]


def _centro(c):
    return ((c[0] + c[2]) / 2.0, (c[1] + c[3]) / 2.0)


def _confere_grupo(antes, depois, k, fx, fy, ids, tol=TOL, ponto=True):
    """Cada caixa do grupo depois e a de antes escalada por k em volta do mesmo ponto (fx, fy da caixa que junta o
    grupo antes); as distancias entre os centros mudam na razao k. ponto=False: so as distancias e os tamanhos (o grupo
    pode ter andado inteiro pelo alinhamento)."""
    u = _uniao([antes[i] for i in ids])
    px, py = u[0] + fx * (u[2] - u[0]), u[1] + fy * (u[3] - u[1])
    for i in ids:
        a, d = antes[i], depois[i]
        assert d[2] - d[0] == pytest.approx(k * (a[2] - a[0]), abs=tol), (i, a, d)
        assert d[3] - d[1] == pytest.approx(k * (a[3] - a[1]), abs=tol), (i, a, d)
        if ponto:
            esperado = [px + k * (a[0] - px), py + k * (a[1] - py), px + k * (a[2] - px), py + k * (a[3] - py)]
            assert d == pytest.approx(esperado, abs=tol), (i, d, esperado)
    for i in ids:
        for j in ids:
            if i < j:
                (ax, ay), (bx, by) = _centro(antes[i]), _centro(antes[j])
                (cx, cy), (dx, dy) = _centro(depois[i]), _centro(depois[j])
                assert cx - dx == pytest.approx(k * (ax - bx), abs=tol), (i, j)
                assert cy - dy == pytest.approx(k * (ay - by), abs=tol), (i, j)


# ------------------------------------------------------------------ as edicoes do grupo, sem job
def test_escalar_o_grupo_em_volta_do_mesmo_ponto_em_cada_formato():
    caixas = {'a': [100.0, 40.0, 130.0, 145.0], 'b': [140.0, 90.0, 170.0, 145.0], 'c': [75.0, 30.0, 195.0, 150.0]}
    edicoes = [{'elemento': 'a', 'elementos': ['a', 'b', 'c'], 'acao': 'escalar', 'fator': 0.8, 'fx': 0.5, 'fy': 1.0}]
    for W, H in ((400, 200), (840, 400)):
        depois, apagados, _t, mexidos = ed.aplicar(caixas, edicoes, W, H)
        assert apagados == [] and sorted(mexidos) == ['a', 'b', 'c']
        _confere_grupo(caixas, depois, 0.8, 0.5, 1.0, ['a', 'b', 'c'], tol=1e-9)


def test_escalar_o_grupo_sem_ponto_fixo_usa_o_meio_da_caixa_do_grupo():
    caixas = {'a': [0.0, 0.0, 10.0, 10.0], 'b': [90.0, 40.0, 100.0, 50.0]}
    edicoes = [{'elemento': 'a', 'elementos': ['a', 'b'], 'acao': 'escalar', 'fator': 2.0}]
    depois = ed.aplicar(caixas, edicoes, 100, 50)[0]
    _confere_grupo(caixas, depois, 2.0, 0.5, 0.5, ['a', 'b'], tol=1e-9)
    # o elemento so continua escalando em volta do meio dele, como antes
    so = ed.aplicar(caixas, [{'elemento': 'a', 'acao': 'escalar', 'fator': 2.0}], 100, 50)[0]
    assert so['a'] == pytest.approx([-5.0, -5.0, 15.0, 15.0]) and so['b'] == caixas['b']


def test_mover_o_grupo_anda_todos_igual_em_proporcao_ao_formato():
    caixas = {'a': [10.0, 20.0, 30.0, 40.0], 'b': [50.0, 60.0, 70.0, 80.0], 'c': [0.0, 0.0, 5.0, 5.0]}
    edicoes = [{'elemento': 'a', 'elementos': ['a', 'b'], 'acao': 'mover', 'dx': 0.1, 'dy': -0.05}]
    depois, _ap, _t, mexidos = ed.aplicar(caixas, edicoes, 200, 400)
    assert depois['a'] == pytest.approx([30.0, 0.0, 50.0, 20.0])
    assert depois['b'] == pytest.approx([70.0, 40.0, 90.0, 60.0])
    assert depois['c'] == caixas['c'] and mexidos == ['a', 'b']


def test_grupo_sem_o_elemento_apagado_escala_o_resto():
    caixas = {'a': [0.0, 0.0, 10.0, 10.0], 'b': [20.0, 0.0, 30.0, 10.0], 'c': [200.0, 200.0, 210.0, 210.0]}
    edicoes = [{'elemento': 'c', 'acao': 'apagar'},
               {'elemento': 'a', 'elementos': ['a', 'b', 'c'], 'acao': 'escalar', 'fator': 2.0, 'fx': 0.0, 'fy': 0.0}]
    depois, apagados, _t, mexidos = ed.aplicar(caixas, edicoes, 400, 400)
    assert apagados == ['c'] and 'c' not in depois and mexidos == ['a', 'b']
    _confere_grupo(caixas, depois, 2.0, 0.0, 0.0, ['a', 'b'], tol=1e-9)


def test_grupos_saem_da_ultima_edicao_de_cada_elemento():
    g = [{'elemento': 'a', 'elementos': ['a', 'b', 'c'], 'acao': 'mover', 'dx': 0.0, 'dy': 0.1}]
    assert ed.grupos(g) == [['a', 'b', 'c']]
    # escalar o mesmo grupo depois: continua um grupo so
    assert ed.grupos(g + [dict(g[0], acao='escalar', fator=0.9)]) == [['a', 'b', 'c']]
    # mexer num elemento sozinho tira ele do grupo; o resto continua junto
    assert ed.grupos(g + [{'elemento': 'a', 'acao': 'mover', 'dx': 0.1, 'dy': 0.0}]) == [['b', 'c']]
    # o elemento apagado sai do grupo, e o grupo de um elemento so nao e grupo
    assert ed.grupos(g + [{'elemento': 'b', 'acao': 'apagar'}, {'elemento': 'c', 'acao': 'apagar'}]) == []
    # o texto editado nao mexe no grupo
    assert ed.grupos(g + [{'elemento': 'a', 'acao': 'texto', 'texto': 'X'}]) == [['a', 'b', 'c']]
    assert ed.grupos([{'elemento': 'a', 'acao': 'mover', 'dx': 0.0, 'dy': 0.0}]) == []


def test_alinhamento_nao_separa_o_grupo():
    # a e b sao do mesmo grupo: as esquerdas a 3 px (abaixo da tolerancia de 19 px em 1920) ficam como estao
    caixas = {'a': [100.0, 100.0, 200.0, 150.0], 'b': [103.0, 300.0, 180.0, 350.0]}
    novas, alinhados = ed.normalizar(caixas, ['a', 'b'], 1920, 1080, grupos=[['a', 'b']])
    assert novas == caixas and alinhados == []


def test_grupo_que_encosta_na_linha_de_outro_elemento_anda_inteiro():
    # o grupo, mexido por ultimo, para com b a 4 px da esquerda do titulo t: o grupo inteiro anda os mesmos 4 px ate a
    # linha de t, tambem o circulo c, que nao e de conteudo e vai junto (acompanham); t fica (decisao 185)
    caixas = {'a': [500.0, 600.0, 560.0, 700.0], 'b': [104.0, 400.0, 180.0, 450.0], 't': [100.0, 50.0, 400.0, 90.0]}
    circulo = {'c': [450.0, 380.0, 700.0, 720.0]}
    novas, alinhados = ed.normalizar(caixas, ['a', 'b', 'c'], 1920, 1080, grupos=[['a', 'b', 'c']],
                                     acompanham=circulo)
    assert novas['t'] == caixas['t']
    assert novas['b'][0] == pytest.approx(100.0)
    for k, c in list(caixas.items()) + list(circulo.items()):
        if k != 't':
            assert novas[k] == pytest.approx([c[0] - 4.0, c[1], c[2] - 4.0, c[3]]), k
    assert [(a['elementos'], a['eixo']) for a in alinhados] == [(['b', 't'], 'x')]


def test_grupo_volta_inteiro_para_a_linha_do_kv():
    # no KV, b e t dividiam a esquerda: o grupo mexido volta inteiro para a linha do titulo (a primeira passada)
    caixas = {'a': [500.0, 600.0, 560.0, 700.0], 'b': [104.0, 400.0, 180.0, 450.0], 't': [100.0, 50.0, 400.0, 90.0]}
    kv = {'a': [250.0, 300.0, 280.0, 350.0], 'b': [50.0, 200.0, 90.0, 225.0], 't': [50.0, 25.0, 200.0, 45.0]}
    novas, _a = ed.normalizar(caixas, ['a', 'b'], 1920, 1080, kv_caixas=kv, kv_tamanho=(960, 540),
                              grupos=[['a', 'b']])
    assert novas['t'] == caixas['t']
    assert novas['b'][0] == pytest.approx(100.0) and novas['a'][0] == pytest.approx(496.0)


# ------------------------------------------------------------------ os esquemas
def _rascunho(edicoes):
    return {'esquema': tr.ESQUEMA, 'job_id': '0' * 32, 'laudo_sha256': '0' * 64, 'origem': 'rascunho',
            'atualizado_em': '2026-11-11T10:00:00', 'familias': {'h-1': {'versao': None, 'confirmada': False,
                                                                       'edicoes': edicoes}}}


@pytest.mark.parametrize('edicao, vale', [
    ({'elemento': 'el41', 'elementos': GRUPO, 'acao': 'escalar', 'fator': 0.8, 'fx': 0.5, 'fy': 1.0}, True),
    ({'elemento': 'el41', 'elementos': GRUPO, 'acao': 'mover', 'dx': 0.1, 'dy': 0.0}, True),
    ({'elemento': 'el41', 'elementos': ['el41'], 'acao': 'mover', 'dx': 0.1, 'dy': 0.0}, False),
    ({'elemento': 'el41', 'elementos': ['el41', 'el41'], 'acao': 'mover', 'dx': 0.1, 'dy': 0.0}, False),
    ({'elemento': 'el41', 'elementos': GRUPO, 'acao': 'apagar'}, False),
    ({'elemento': 'el41', 'elementos': GRUPO, 'acao': 'texto', 'texto': 'X'}, False),
    ({'elemento': 'el41', 'elementos': ['el41', 7], 'acao': 'mover', 'dx': 0.1, 'dy': 0.0}, False),
])
def test_esquemas_aceitam_a_lista_do_grupo_so_em_mover_e_escalar(edicao, vale):
    def passa(dado, esquema):
        try:
            contratos.validar(dado, esquema)
            return True
        except contratos.ErroContrato:
            return False
    assert passa(_rascunho([edicao]), tr.ESQUEMA) is vale
    b = _briefing([edicao])
    assert passa(b, mb.ESQUEMA) is vale


# ------------------------------------------------------------------ a derivacao da familia confirmada
def _laudo():
    camadas = [ap.camada(1, 'pixel', [0, 0, 400, 200]), ap.camada(30, 'smart_embutido', [20, 150, 70, 185])]
    camadas += [ap.camada(k, 'pixel', CAIXAS_KV[k]) for k in (CIRCULO, GARRAFA, COPO)]
    return ap.laudo(400, 200, camadas)


def _briefing(edicoes):
    b = ap.briefing(funcoes=FUN, formatos=[ap.formato(i, w, h) for i, w, h in HORIZONTAIS])
    b['composicoes'] = [{'familia': 'horizontal-1', 'formatos': [i for i, _w, _h in HORIZONTAIS], 'versao': None,
                         'edicoes': list(edicoes), 'confirmada': True, 'confirmacao': dict(CONF)}]
    return b


def _derivar(edicoes):
    b = _briefing(edicoes)
    contratos.validar(b, mb.ESQUEMA)
    assert mb.conferir(_laudo(), b) == []
    return nd.derivar_em_memoria(nd.contexto(_laudo(), b), specs={})['formatos']


def _caixas(d):
    return {e['id']: [float(x) for x in e['caixa']] for e in d['elementos']}


@pytest.mark.parametrize('fator, fx, fy', [(0.8, 0.5, 1.0), (1.25, 0.0, 1.0), (0.9, 0.5, 0.5)])
def test_derivacao_escala_o_packshot_junto_em_todos_os_membros(fator, fx, fy):
    antes = _derivar([])
    grupo = [{'elemento': GRUPO[0], 'elementos': GRUPO, 'acao': 'escalar', 'fator': fator, 'fx': fx, 'fy': fy}]
    depois = _derivar(grupo)
    for fid, _w, _h in HORIZONTAIS:
        a, d = antes[fid], depois[fid]
        assert a['situacao'] == 'derivado' and d['situacao'] == 'derivado', (fid, d.get('devolucao'))
        _confere_grupo(_caixas(a), _caixas(d), fator, fx, fy, GRUPO)
        origem = {e['id']: e['origem_geometria'] for e in d['elementos']}
        assert all(origem[i] == 'da' for i in GRUPO), origem


def test_encaixe_refeito_nao_desfaz_o_tamanho_que_o_da_deu():
    # o solver refaz o encaixe depois da edicao: a regra de escala da funcao nao puxa de volta o tamanho que o DA deu
    # ao elemento que ele mexeu (a garrafa, de conteudo, encolhida sozinha)
    antes = _derivar([])
    depois = _derivar([{'elemento': GRUPO[0], 'acao': 'escalar', 'fator': 0.8, 'fx': 0.5, 'fy': 1.0}])
    for fid, _w, _h in HORIZONTAIS:
        _confere_grupo(_caixas(antes[fid]), _caixas(depois[fid]), 0.8, 0.5, 1.0, [GRUPO[0]])


def test_derivacao_move_e_escala_o_grupo_e_continua_junto():
    antes = _derivar([])
    edicoes = [{'elemento': GRUPO[0], 'elementos': GRUPO, 'acao': 'mover', 'dx': -0.05, 'dy': 0.02},
               {'elemento': GRUPO[0], 'elementos': GRUPO, 'acao': 'escalar', 'fator': 0.85, 'fx': 0.5, 'fy': 1.0}]
    depois = _derivar(edicoes)
    for fid, w, h in HORIZONTAIS:
        a = _caixas(antes[fid])
        movido = {i: [a[i][0] - 0.05 * w, a[i][1] + 0.02 * h, a[i][2] - 0.05 * w, a[i][3] + 0.02 * h] for i in GRUPO}
        _confere_grupo(movido, _caixas(depois[fid]), 0.85, 0.5, 1.0, GRUPO)


def test_derivacao_com_o_grupo_e_deterministica():
    grupo = [{'elemento': GRUPO[0], 'elementos': GRUPO, 'acao': 'escalar', 'fator': 0.8, 'fx': 0.5, 'fy': 1.0}]
    um, dois = _derivar(grupo), _derivar(copy.deepcopy(grupo))
    sem = lambda x: json.dumps({k: v for k, v in x.items() if k != 'gerado_em'}, sort_keys=True)  # noqa: E731
    assert all(sem(um[f]) == sem(dois[f]) for f, _w, _h in HORIZONTAIS)


# ------------------------------------------------------------------ o job sintetico com o packshot
NOMES = {'fundo': 'fundo-sintetico', 'titulo': 'titulo-sintetico', 'circulo': 'circulo-sintetico',
         'garrafa': 'garrafa-sintetica', 'copo': 'copo-sintetico'}


def _psd_packshot(destino, ps):
    """PSD 400 x 200: fundo, titulo de texto em cima a esquerda e o packshot no canto direito: o circulo de fundo e,
    na frente dele, a garrafa e o copo (cada um uma camada). O titulo usa so os glifos da fonte de autoteste."""
    from PIL import Image, ImageDraw
    from psd_tools import PSDImage

    import test_fontes_apoio as fap
    import test_render_apoio as rap
    import test_tela_palco as tp
    p = PSDImage.new('RGB', (400, 200), color=(255, 255, 255))
    p.create_pixel_layer(Image.new('RGBA', (400, 200), (236, 232, 222, 255)), name=NOMES['fundo'])
    t = p.create_pixel_layer(Image.new('RGBA', (200, 30), (20, 20, 20, 255)), name=NOMES['titulo'], top=20, left=10)
    fap._virar_texto(t, [('HOAX', 0, 28.0, 0)], [ps], fap.largura('HOAX', 28.0, avancos=tp.AVANCOS), x=12.0, y=44.0)
    disco = Image.new('RGBA', (120, 120), (0, 0, 0, 0))
    ImageDraw.Draw(disco).ellipse([0, 0, 119, 119], fill=(200, 90, 40, 255))
    c = CAIXAS_KV
    p.create_pixel_layer(disco, name=NOMES['circulo'], top=c[CIRCULO][1], left=c[CIRCULO][0])
    p.create_pixel_layer(Image.new('RGBA', (30, 105), (30, 70, 40, 255)), name=NOMES['garrafa'],
                         top=c[GARRAFA][1], left=c[GARRAFA][0])
    p.create_pixel_layer(Image.new('RGBA', (30, 55), (60, 60, 90, 255)), name=NOMES['copo'],
                         top=c[COPO][1], left=c[COPO][0])
    return rap._salvar(p, destino)


@pytest.fixture(scope='module')
def job_grupo(tmp_path_factory):
    import test_fontes_apoio as fap
    from desdobra.job import nucleo
    from desdobra.render import autoteste
    base = tmp_path_factory.mktemp('grupo')
    fontes = base / 'origem-fontes'
    fap.gravar(fontes, 'autoteste.ttf', autoteste.gerar_fonte())
    job = base / 'job'
    nucleo.criar(job, _psd_packshot(base / 'origem' / 'kv.psd', autoteste.NOME_PS), 'c', fontes=[fontes])
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    ids = {c['nome']: c['identidade']['layer_id'] for c in laudo['camadas']}
    funcoes = {ids[NOMES['fundo']]: 'fundo', ids[NOMES['titulo']]: 'titulo', ids[NOMES['circulo']]: 'grafismo',
               ids[NOMES['garrafa']]: 'sujeito', ids[NOMES['copo']]: 'sujeito'}
    b = ap.briefing(funcoes=funcoes, formatos=[ap.formato(i, w, h) for i, w, h in HORIZONTAIS])
    b.pop('cabecalho')
    b.pop('job_id')
    arq = base / 'fixture.json'
    arq.write_text(json.dumps(b), encoding='utf-8')
    mb.importar_teste(job, arq)
    return {'job': job, 'grupo': ['el%d' % ids[NOMES[k]] for k in ('garrafa', 'copo', 'circulo')]}


@pytest.fixture(scope='module')
def conteudo_grupo(job_grupo):
    from desdobra.tela import estado as te
    return te.montar(job_grupo['job'])


def _familia(conteudo):
    return next(g for g, f in conteudo['familias'].items() if 'h1' in f['formatos'])


def _caixas_da_previa(r):
    return {m['formato']: {e['id']: [float(x) for x in e['caixa']] for e in m['palco']['elementos']}
            for m in r['membros']}


def test_previa_da_tela_escala_o_grupo_junto_em_cada_arquivo(job_grupo, conteudo_grupo):
    gid = _familia(conteudo_grupo)
    assert sorted(conteudo_grupo['familias'][gid]['formatos']) == [i for i, _w, _h in HORIZONTAIS]
    grupo = job_grupo['grupo']
    antes = _caixas_da_previa(conteudo_grupo['editar']({'familia': gid, 'versao': None, 'edicoes': []}))
    edicao = {'elemento': grupo[0], 'elementos': grupo, 'acao': 'escalar', 'fator': 0.8, 'fx': 0.5, 'fy': 1.0}
    r = conteudo_grupo['editar']({'familia': gid, 'versao': None, 'edicoes': [edicao]})
    assert r is not None and len(r['membros']) == len(HORIZONTAIS)
    # nenhum elemento do grupo encostou na linha de outro: o ponto fixo fica onde o DA o pos
    assert not [a for a in r['alinhados'] if set(a['elementos']) & set(grupo)], r['alinhados']
    depois = _caixas_da_previa(r)
    for fid, _w, _h in HORIZONTAIS:
        _confere_grupo(antes[fid], depois[fid], 0.8, 0.5, 1.0, grupo)


@pytest.mark.parametrize('mexe', [
    lambda g: [{'elemento': g[1], 'elementos': g, 'acao': 'mover', 'dx': 0.1, 'dy': 0.0}],  # o primeiro nao e o elemento
    lambda g: [{'elemento': g[0], 'elementos': g[:1] + ['el999'], 'acao': 'mover', 'dx': 0.1, 'dy': 0.0}],
    lambda g: [{'elemento': g[0], 'elementos': g, 'acao': 'apagar'}],
])
def test_previa_recusa_grupo_fora_do_formato(job_grupo, conteudo_grupo, mexe):
    gid = _familia(conteudo_grupo)
    assert conteudo_grupo['editar']({'familia': gid, 'versao': None, 'edicoes': mexe(job_grupo['grupo'])}) is None


# ------------------------------------------------------------------ a tela no Chromium sem janela (modo de teste)
JS_PONTO = """i => {
  const r = document.querySelector('#palco .rotulo[data-elemento="' + i + '"]').getBoundingClientRect();
  for (let fy = 0.1; fy < 1; fy += 0.1) {
    for (let fx = 0.1; fx < 1; fx += 0.1) {
      const x = r.left + fx * r.width, y = r.top + fy * r.height;
      const no = document.elementFromPoint(x, y);
      const rot = no && no.closest('.rotulo');
      if (rot && rot.dataset.elemento === i) return [x, y];
    }
  }
  return null;
}"""
JS_ESCOLHIDOS = """() => Array.from(document.querySelectorAll('#palco .rotulo.selecionado')).map(r => r.dataset.elemento)
  .sort()"""


def _ponto(pg, eid):
    p = pg.evaluate(JS_PONTO, eid)
    assert p, eid
    return p


def _shift_clique(pg, eid):
    x, y = _ponto(pg, eid)
    pg.keyboard.down('Shift')
    pg.mouse.click(x, y)
    pg.keyboard.up('Shift')


def _rascunho_gravado(job):
    arq = job / tr.ARQUIVO
    return json.loads(arq.read_text(encoding='utf-8')) if arq.exists() else None


def _edicoes(job, gid):
    return ((_rascunho_gravado(job) or {}).get('familias', {}).get(gid) or {}).get('edicoes') or []


def _limpar_rascunho(job):
    arq = job / tr.ARQUIVO
    if arq.exists():
        arq.unlink()


def test_grupo_na_tela_do_chromium(job_grupo, conteudo_grupo):
    from playwright.sync_api import sync_playwright

    import test_tela_galeria as tg
    import test_tela_palco as tp
    from desdobra.chromium import navegador
    from desdobra.tela import atos as ta
    from desdobra.tela import servidor as ts
    job, grupo = job_grupo['job'], job_grupo['grupo']
    _limpar_rascunho(job)
    estado = conteudo_grupo['estado']
    gid = _familia(conteudo_grupo)
    base = conteudo_grupo['editar']({'familia': gid, 'versao': None, 'edicoes': []})
    antes = _caixas_da_previa(base)
    fundo = next(e['id'] for e in base['membros'][0]['palco']['elementos'] if e['funcao'] == 'fundo')
    salvo = '() => (document.documentElement.dataset.rascunho === "salvo" && ' \
            'document.documentElement.dataset.previa === "pronta") ? "1" : ""'
    navegador.apontar_playwright()
    with ts.ServidorTela(conteudo_grupo, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo_grupo)) as srv, sync_playwright() as pw:
        nav, pg = tp._pagina_da_tela(pw, srv, 2048, 720)  # numero-neutro: a tela do Duda (decisao 157)
        try:
            tg._abrir(pg, estado, 'h1')
            tp._esperar(pg, '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""')
            # revisao 2 da fase D: os gestos ficam na lista de "Como editar"; a linha do nome manda para ela
            assert 'Como editar' in pg.evaluate('() => document.getElementById("elemento-escolhido").textContent')
            ajuda = pg.evaluate('() => document.getElementById("ed-ajuda-painel").textContent')
            assert 'Shift' in ajuda and 'Escolher vários' in ajuda and 'retângulo' in ajuda
            # Shift+clique na garrafa, no copo e no circulo: os tres escolhidos, uma caixa so em volta deles
            for eid in grupo:
                _shift_clique(pg, eid)
            assert pg.evaluate(JS_ESCOLHIDOS) == sorted(grupo)
            assert pg.evaluate('() => document.querySelectorAll("#palco .caixa-grupo").length') == 1
            assert pg.evaluate('() => document.querySelectorAll("#palco .caixa-grupo .alca").length') == 4  # numero-neutro: os cantos
            assert 'Escolhidos juntos: 3 elementos' in pg.evaluate(
                '() => document.getElementById("elemento-escolhido").textContent')
            # texto e apagar sao de um elemento so; Diminuir e Aumentar valem para o grupo
            assert pg.evaluate('() => document.getElementById("ed-apagar").disabled') is True
            assert pg.evaluate('() => document.getElementById("ed-diminuir").disabled') is False
            assert _edicoes(job, gid) == []  # escolher nao grava nada
            # Diminuir: uma edicao so, com a lista do grupo, em volta do meio da caixa do grupo
            pg.evaluate('() => document.getElementById("ed-diminuir").click()')
            tp._esperar(pg, salvo)
            eds = _edicoes(job, gid)
            assert len(eds) == 1 and eds[0]['acao'] == 'escalar' and eds[0]['elementos'] == grupo
            assert eds[0]['elemento'] == grupo[0] and 'fx' not in eds[0]
            k = eds[0]['fator']
            assert k == pytest.approx(1 / 1.05, abs=1e-5)
            depois = _caixas_da_previa(conteudo_grupo['editar']({'familia': gid, 'versao': None, 'edicoes': eds}))
            for fid, _w, _h in HORIZONTAIS:
                _confere_grupo(antes[fid], depois[fid], k, 0.5, 0.5, grupo)
            # o grupo continua escolhido depois da previa; arrastar um deles leva todos (uma edicao de mover)
            assert pg.evaluate(JS_ESCOLHIDOS) == sorted(grupo)
            x, y = _ponto(pg, grupo[0])
            pg.mouse.move(x, y)
            pg.mouse.down()
            pg.mouse.move(x - 40, y, steps=4)  # numero-neutro: 40 px de tela para a esquerda
            pg.mouse.up()
            tp._esperar(pg, salvo)
            eds = _edicoes(job, gid)
            assert [e['acao'] for e in eds] == ['escalar', 'mover'] and eds[1]['elementos'] == grupo
            assert eds[1]['dx'] < 0
            # o canto de baixo a direita da caixa do grupo: o ponto fixo e o canto de cima a esquerda do grupo
            alca = pg.evaluate('''() => { const r = document.querySelector('#palco .caixa-grupo .alca[data-canto="se"]')
                .getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }''')
            pg.mouse.move(alca[0], alca[1])
            pg.mouse.down()
            pg.mouse.move(alca[0] - 30, alca[1] - 30, steps=4)  # numero-neutro: px de tela, para dentro
            pg.mouse.up()
            tp._esperar(pg, salvo)
            eds = _edicoes(job, gid)
            assert eds[-1]['acao'] == 'escalar' and eds[-1]['elementos'] == grupo
            assert (eds[-1]['fx'], eds[-1]['fy']) == (0, 0) and eds[-1]['fator'] < 1
            # a seta com o foco num elemento do grupo move o grupo
            pg.keyboard.press('ArrowUp')
            tp._esperar(pg, salvo)
            eds = _edicoes(job, gid)
            assert eds[-1]['acao'] == 'mover' and eds[-1]['elementos'] == grupo and eds[-1]['dy'] < 0
            n = len(eds)
            # Shift+clique num escolhido tira ele do grupo; Esc solta a escolha
            _shift_clique(pg, grupo[2])
            assert pg.evaluate(JS_ESCOLHIDOS) == sorted(grupo[:2])
            pg.keyboard.press('Escape')
            assert pg.evaluate(JS_ESCOLHIDOS) == []
            assert pg.evaluate('() => document.querySelectorAll("#palco .caixa-grupo").length') == 0
            # o retangulo: arrastar a partir do fundo, em volta do packshot, escolhe so os elementos inteiros nele
            caixa = pg.evaluate('''ids => { const rs = ids.map(i => document.querySelector(
                '#palco .rotulo[data-elemento="' + i + '"]').getBoundingClientRect());
                return [Math.min(...rs.map(r => r.left)), Math.min(...rs.map(r => r.top)),
                        Math.max(...rs.map(r => r.right)), Math.max(...rs.map(r => r.bottom))]; }''', grupo)
            # (de baixo para cima: a etiqueta de cada elemento fica em cima, a esquerda da caixa dele)
            pg.mouse.move(caixa[2] + 6, caixa[3] + 6)
            pg.mouse.down()
            pg.mouse.move(caixa[0] - 6, caixa[1] - 6, steps=6)
            assert pg.evaluate('() => document.querySelectorAll("#palco .retangulo-selecao").length') == 1
            pg.mouse.up()
            assert pg.evaluate('() => document.querySelectorAll("#palco .retangulo-selecao").length') == 0
            assert pg.evaluate(JS_ESCOLHIDOS) == sorted(grupo)
            # escolher nao grava nada
            assert len(_edicoes(job, gid)) == n
            # o clique no fundo sem arrastar escolhe o fundo
            pg.mouse.click(caixa[2] + 6, caixa[3] + 6)
            assert pg.evaluate(JS_ESCOLHIDOS) == [fundo]
            # "Escolher vários": sem teclado, cada clique poe ou tira um elemento do grupo
            pg.keyboard.press('Escape')
            pg.evaluate('() => document.getElementById("ed-varios").click()')
            assert pg.evaluate('() => document.getElementById("ed-varios").getAttribute("aria-pressed")') == 'true'
            for eid in grupo[:2]:
                x, y = _ponto(pg, eid)
                pg.mouse.click(x, y)
            assert pg.evaluate(JS_ESCOLHIDOS) == sorted(grupo[:2])
            pg.evaluate('() => document.getElementById("ed-varios").click()')
            assert pg.evaluate('() => document.getElementById("ed-varios").getAttribute("aria-pressed")') == 'false'
            # sem o modo, o clique num elemento escolhe so ele
            x, y = _ponto(pg, grupo[1])
            pg.mouse.click(x, y)
            assert pg.evaluate(JS_ESCOLHIDOS) == [grupo[1]]
            texto = pg.evaluate(tp.JS_TEXTO_DA_MOLDURA)
            assert not tp.IDENTIFICADOR.findall(texto), tp.IDENTIFICADOR.findall(texto)
            assert '—' not in texto and '–' not in texto
        finally:
            nav.close()
        contagem = dict(srv.contagem)
    assert contagem['proibido'] == 0 and contagem['csrf_recusado'] == 0 and contagem['dado_recusado'] == 0
    _limpar_rascunho(job)
