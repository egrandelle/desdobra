# -*- coding: utf-8 -*-
"""M7b, D4: o elemento, ou o grupo, que o DA mexeu no palco pode passar da borda do quadro (sangria por decisao do
DA; decisoes-v1.md, 167; pergunta 5 do plano do M7b, respondida pelo Duda em 10/11: "So o DA ajusta"), escrito antes
do codigo.

Criterios de pronto cobertos aqui:
  - o lado em que a caixa que o DA mexeu ou escalou passa da borda do formato vira sangria por decisao do DA
    (sangria_do_da), em qualquer lado; o texto e a marca nunca sangram (continuam dentro do quadro, como antes);
  - a derivacao da familia confirmada honra a caixa do DA: o encaixe refeito pelo solver nao puxa o elemento de volta
    para dentro nem separa o grupo, e a validacao obrigatoria (enquadramento) e a conferencia (fora do quadro) nao
    marcam a sangria do DA como defeito;
  - o caso do packshot (Duda, 10/11): o grupo (circulo, garrafa, copo e lata) escalado a 85% e movido para os tres
    produtos ficarem inteiros na largura, sangrando na base; o circulo pode sangrar na direita;
  - a previa da tela leva o mesmo layout, sem "Pede ajuste";
  - o render corta no quadro o que passa dele, exatamente na caixa da derivacao;
  - revisao 1 da fase D: o elemento cortado na borda do KV que o DA tira dela fica onde o DA o pos, com o mesmo
    tamanho em todo membro e o grupo junto, e pede ajuste pelo corte a vista; o grupo alinhado na base vai pela linha
    dos produtos, e o circulo continua passando da borda.
Tudo sintetico: laudo montado a mao, PSD sintetico gerado na hora e a fonte de autoteste do motor."""
import json
import sys

import pytest

import test_derivacao_apoio as ap
from desdobra import contratos, humano, limites
from desdobra.briefing import modelo as mb
from desdobra.derivacao import nucleo as nd
from desdobra.tela import edicao as ed

CONF = {'origem': 'fixture_de_teste', 'meio': 'medicao', 'em': '2026-11-11T10:00:00-03:00'}
ROT0 = {'graus': 0, 'sentido': None}
# o packshot sintetico do KV 400 x 200: o circulo de fundo (grafismo, sangra na base do KV) e, na frente dele, a
# garrafa, o copo e a lata (sujeito), inteiros no KV
LOGO, CIRCULO, GARRAFA, COPO, LATA = 30, 40, 41, 42, 43
CAIXAS_KV = {LOGO: [20, 20, 70, 55], CIRCULO: [250, 70, 380, 200], GARRAFA: [270, 75, 300, 190],
             COPO: [305, 125, 330, 190], LATA: [335, 115, 360, 190]}
FUN = {1: 'fundo', LOGO: 'logo_principal', CIRCULO: 'grafismo', GARRAFA: 'sujeito', COPO: 'sujeito', LATA: 'sujeito'}
PRODUTOS = ['el%d' % k for k in (GARRAFA, COPO, LATA)]
GRUPO = PRODUTOS + ['el%d' % CIRCULO]
HORIZONTAIS = [('h1', 800, 400), ('h2', 840, 400), ('h3', 880, 400)]
TOL = 0.5  # numero-neutro: px de folga do arredondamento da derivacao
# o "antes" do Duda: o grupo grande, a lata cortada pela borda direita e o packshot sangrando na base
ANTES = [{'elemento': GRUPO[0], 'elementos': GRUPO, 'acao': 'mover', 'dx': 0.12, 'dy': 0.06}]
# o "depois": o grupo a 85% em volta do meio da base e para a esquerda, ate a lata caber inteira
DEPOIS = ANTES + [{'elemento': GRUPO[0], 'elementos': GRUPO, 'acao': 'escalar', 'fator': 0.85, 'fx': 0.5, 'fy': 1.0},
                  {'elemento': GRUPO[0], 'elementos': GRUPO, 'acao': 'mover', 'dx': -0.04, 'dy': 0.0}]


def _lados(c, W, H, tol):
    return [lado for lado, fora in (('esq', c[0] < -tol), ('topo', c[1] < -tol), ('dir', c[2] > W + tol),
                                    ('base', c[3] > H + tol)) if fora]


# ------------------------------------------------------------------ a sangria do DA, sem job
def test_sangria_do_da_marca_os_lados_que_passam_do_quadro():
    caixas = {'a': [-30.0, 10.0, 50.0, 90.0], 'b': [700.0, 300.0, 830.0, 420.0], 'c': [-30.0, 0.0, 10.0, 10.0],
              'd': [-0.2, 0.0, 10.0, 400.2], 't': [-40.0, 10.0, 60.0, 30.0]}
    sangra = ed.sangria_do_da(caixas, ['a', 'b', 'd', 't'], 800, 400, 0.5, sem_sangria=('t',))
    # c passa da borda, mas o DA nao o mexeu; d fica dentro da tolerancia; o texto t nunca sangra
    assert sangra == {'a': ['esq'], 'b': ['dir', 'base']}
    assert ed.sangria_do_da(caixas, [], 800, 400, 0.5) == {}


# ------------------------------------------------------------------ a derivacao da familia confirmada
def _laudo():
    camadas = [ap.camada(1, 'pixel', [0, 0, 400, 200]), ap.camada(LOGO, 'smart_embutido', CAIXAS_KV[LOGO])]
    camadas += [ap.camada(k, 'pixel', CAIXAS_KV[k]) for k in (CIRCULO, GARRAFA, COPO, LATA)]
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


@pytest.mark.parametrize('edicoes', [ANTES, DEPOIS], ids=['lata_cortada', 'packshot_menor'])
def test_derivacao_honra_a_caixa_que_o_da_deixou_sangrar(edicoes):
    tol = limites.valor('derivacao.enquadramento_tolerancia_px')
    antes = _derivar([])
    depois = _derivar(edicoes)
    for fid, w, h in HORIZONTAIS:
        d = depois[fid]
        assert d['situacao'] == 'derivado', (fid, d.get('devolucao'))
        assert [v['nome'] for v in d['validacoes'] if v['situacao'] == 'reprova'] == []
        assert not [r for r in d['registros'] if r['codigo'] == 'proposta_com_falha'], d['registros']
        # a caixa de cada elemento do grupo e a que o DA deu: o solver nao puxa nada para dentro nem separa o grupo
        esperado = ed.aplicar(_caixas(antes[fid]), edicoes, w, h)[0]
        caixas = _caixas(d)
        por_id = {e['id']: e for e in d['elementos']}
        for i in GRUPO:
            assert caixas[i] == pytest.approx(esperado[i], abs=TOL), (fid, i, caixas[i], esperado[i])
            e = por_id[i]
            assert e['origem_geometria'] == 'da'
            lados = _lados(esperado[i], w, h, tol)
            # o lado que passa da borda sangra por decisao do DA; o lado que ja sangrava no KV continua sangrando
            # (sem entrar na sangria do DA)
            do_kv = next(x for x in antes[fid]['elementos'] if x['id'] == i)['transformacao']['sangra']
            assert e.get('sangria_do_da', []) == [x for x in lados if not do_kv[x]], (fid, i, e.get('sangria_do_da'))
            assert all(e['transformacao']['sangra'][x] for x in lados), (fid, i, e['transformacao']['sangra'], lados)
        contratos.validar(d, nd.ESQUEMA)


def test_packshot_menor_fica_inteiro_na_largura_e_sangra_na_base():
    antes = _derivar(ANTES)
    depois = _derivar(DEPOIS)
    for fid, w, h in HORIZONTAIS:
        a, d = _caixas(antes[fid]), _caixas(depois[fid])
        por_id = {e['id']: e for e in depois[fid]['elementos']}
        # no "antes", a lata e cortada pela borda direita
        assert a[PRODUTOS[-1]][2] > w + 1, (fid, a[PRODUTOS[-1]])
        for i in PRODUTOS:
            # os tres produtos inteiros na largura, sangrando na base
            assert d[i][0] >= 0 and d[i][2] <= w, (fid, i, d[i])
            assert d[i][3] > h + 1, (fid, i, d[i])
            assert 'base' in por_id[i]['sangria_do_da'] and 'dir' not in por_id[i].get('sangria_do_da', [])
            # 85% do tamanho do "antes", o enquadramento interno da imagem igual (so escala)
            assert d[i][2] - d[i][0] == pytest.approx(0.85 * (a[i][2] - a[i][0]), abs=TOL)
            assert d[i][3] - d[i][1] == pytest.approx(0.85 * (a[i][3] - a[i][1]), abs=TOL)
            assert por_id[i]['transformacao']['recorte_doc'] == [CAIXAS_KV[int(i[2:])][k] for k in range(4)]
        # o circulo continua sangrando na base (do KV) e pode sangrar na direita (do DA)
        c = d['el%d' % CIRCULO]
        assert c[3] > h and por_id['el%d' % CIRCULO]['transformacao']['sangra']['base'] is True
        if c[2] > w + 1:
            assert por_id['el%d' % CIRCULO]['sangria_do_da'] == ['dir']


def test_texto_e_marca_nunca_sangram():
    # a marca que o DA arrasta para fora volta para dentro do quadro, como antes do D4
    antes = _derivar([])
    depois = _derivar([{'elemento': 'el%d' % LOGO, 'acao': 'mover', 'dx': -0.1, 'dy': 0.0}])
    for fid, w, h in HORIZONTAIS:
        e = next(x for x in depois[fid]['elementos'] if x['id'] == 'el%d' % LOGO)
        assert e['caixa'][0] >= -TOL and 'sangria_do_da' not in e and not any(e['transformacao']['sangra'].values())
        assert e['caixa'][0] < next(x for x in antes[fid]['elementos'] if x['id'] == e['id'])['caixa'][0]


def test_derivacao_com_sangria_do_da_e_deterministica():
    um, dois = _derivar(DEPOIS), _derivar(json.loads(json.dumps(DEPOIS)))
    sem = lambda x: json.dumps({k: v for k, v in x.items() if k != 'gerado_em'}, sort_keys=True)  # noqa: E731
    assert all(sem(um[f]) == sem(dois[f]) for f, _w, _h in HORIZONTAIS)


# ------------------------------------------------------------------ o elemento cortado na borda do KV, mexido pelo DA
# (revisao 1 da fase D): o circulo encosta na base do KV, entao o asset dele acaba ali (o compositor corta na borda do
# documento). O DA que o tira da base deixa esse corte a vista: o desdobra nunca o puxa de volta nem muda o tamanho
# dele (o grupo nao se separa, e o tamanho vale igual em todo membro), e pede ajuste com uma frase que diz o que houve
C = 'el%d' % CIRCULO


def _layout(edicoes, fid):
    """O layout do membro fid com as edicoes, como a previa e a derivacao o montam (proposta.layout_do_membro)."""
    from desdobra.derivacao import galeria as mg
    from desdobra.derivacao import proposta
    from desdobra.derivacao import solver as mod_solver
    b = _briefing([])
    ctx = nd.contexto(_laudo(), b)
    antes = nd.derivar_em_memoria(ctx, specs={})['formatos']
    kv = nd.mestre_do_kv(ctx)
    f = next(x for x in ctx['briefing']['formatos'] if x['id'] == fid)
    cf = mg.contexto_do_formato(ctx, proposta.mestre_do_membro(ctx, kv, f, antes[fid]), f, specs={})
    extra = {'kv_por_id': {e['id']: e for e in kv['elementos']},
             'conteudo': [e['id'] for e in kv['elementos'] if mod_solver.conteudo(e)],
             'kv_caixas': {e['id']: [float(x) for x in e['caixa']] for e in kv['elementos']},
             'kv_tamanho': (float(kv['largura']), float(kv['altura']))}
    return proposta.layout_do_membro(cf, antes[fid]['elementos'], edicoes, **extra)


FRASE_CORTE = 'O grafismo acaba na base do KV, onde a imagem foi cortada. Nesta posição, esse corte aparece na peça.'


@pytest.mark.parametrize('fator', [0.7, 0.5])
def test_tamanho_no_elemento_cortado_no_kv_vale_igual_em_todo_membro(fator):
    # o campo Tamanho sem ponto fixo (o meio): o circulo sobe da base, com o mesmo tamanho em todo membro
    eds = [{'elemento': C, 'acao': 'escalar', 'fator': fator}]
    antes, depois = _derivar([]), _derivar(eds)
    situacoes = set()
    for fid, w, h in HORIZONTAIS:
        esperado = ed.aplicar(_caixas(antes[fid]), eds, w, h)[0][C]
        assert _caixas(depois[fid])[C] == pytest.approx(esperado, abs=TOL), fid
        situacoes.add((depois[fid]['situacao'], (depois[fid].get('devolucao') or {}).get('motivo')))
        lay = _layout(eds, fid)
        corte = [f for f in lay['falhas'] if f['codigo'] == 'corte_a_mostra']
        assert [(f['elementos'], f['texto']) for f in corte] == [([C], FRASE_CORTE)], (fid, lay['falhas'])
        # a frase do corte fica no lugar da conferencia generica do motor
        assert not [f for f in lay['falhas'] if f['codigo'] == 'validacao_reprova' and f['elementos'] == [C]]
    # o mesmo resultado em todo membro: o corte a vista devolve o formato pela validacao obrigatoria
    assert situacoes == {('devolvido', 'validacao_obrigatoria_reprovou')}, situacoes


@pytest.mark.parametrize('eds', [
    [{'elemento': GRUPO[0], 'elementos': GRUPO, 'acao': 'escalar', 'fator': 0.85}],
    [{'elemento': GRUPO[0], 'elementos': GRUPO, 'acao': 'mover', 'dx': 0.0, 'dy': -0.05}],
], ids=['diminuir_85_no_meio', 'subir_o_grupo'])
def test_grupo_com_o_elemento_cortado_no_kv_fica_junto(eds):
    antes, depois = _derivar([]), _derivar(eds)
    for fid, w, h in HORIZONTAIS:
        esperado = ed.aplicar(_caixas(antes[fid]), eds, w, h)[0]
        caixas = _caixas(depois[fid])
        for i in GRUPO:
            assert caixas[i] == pytest.approx(esperado[i], abs=TOL), (fid, i, caixas[i], esperado[i])
        lay = _layout(eds, fid)
        assert [f['elementos'] for f in lay['falhas'] if f['codigo'] == 'corte_a_mostra'] == [[C]], lay['falhas']


def test_grupo_alinhado_na_base_fica_na_margem_e_o_cortado_continua_na_borda():
    # o grupo sobe (o corte do circulo aparece) e o DA o poe de volta na base pela margem: a linha do grupo e a dos
    # produtos, que acabam dentro do quadro; o circulo anda junto e continua passando da base
    eds =[{'elemento': GRUPO[0], 'elementos': GRUPO, 'acao': 'mover', 'dx': 0.0, 'dy': -0.05},
           {'elemento': GRUPO[0], 'elementos': GRUPO, 'acao': 'alinhar', 'alvo': 'base', 'referencia': 'margem'}]
    depois = _derivar(eds)
    for fid, w, h in HORIZONTAIS:
        d = depois[fid]
        assert d['situacao'] == 'derivado', (fid, d.get('devolucao'))
        assert not [r for r in d['registros'] if r['codigo'] == 'proposta_com_falha'], d['registros']
        caixas = _caixas(d)
        lay = _layout(eds, fid)
        margem = lay['quadros']['margem']
        assert max(caixas[i][3] for i in PRODUTOS) == pytest.approx(margem[3], abs=TOL), (fid, caixas, margem)
        assert caixas[C][3] >= h - TOL, (fid, caixas[C])


# ------------------------------------------------------------------ o job sintetico com o packshot
NOMES = {'fundo': 'fundo-sintetico', 'logo': 'logo-sintetico', 'circulo': 'circulo-sintetico',
         'garrafa': 'garrafa-sintetica', 'copo': 'copo-sintetico', 'lata': 'lata-sintetica'}
CORES = {'fundo': (236, 232, 222), 'logo': (20, 90, 160), 'circulo': (200, 90, 40), 'garrafa': (30, 150, 40),
         'copo': (240, 220, 30), 'lata': (150, 20, 160)}


def _psd_packshot(destino):
    """PSD 400 x 200: fundo, marca no canto de cima a esquerda e o packshot a direita: o circulo de fundo, que sangra na
    base, e na frente dele a garrafa, o copo e a lata, cada um uma camada de cor lisa."""
    from PIL import Image, ImageDraw
    from psd_tools import PSDImage

    import test_render_apoio as rap
    p = PSDImage.new('RGB', (400, 200), color=(255, 255, 255))
    p.create_pixel_layer(Image.new('RGBA', (400, 200), CORES['fundo'] + (255,)), name=NOMES['fundo'])
    c = CAIXAS_KV
    p.create_pixel_layer(Image.new('RGBA', (50, 35), CORES['logo'] + (255,)), name=NOMES['logo'],
                         top=c[LOGO][1], left=c[LOGO][0])
    disco = Image.new('RGBA', (130, 130), (0, 0, 0, 0))
    ImageDraw.Draw(disco).ellipse([0, 0, 129, 129], fill=CORES['circulo'] + (255,))
    p.create_pixel_layer(disco, name=NOMES['circulo'], top=c[CIRCULO][1], left=c[CIRCULO][0])
    for k, nome in ((GARRAFA, 'garrafa'), (COPO, 'copo'), (LATA, 'lata')):
        w, h = c[k][2] - c[k][0], c[k][3] - c[k][1]
        p.create_pixel_layer(Image.new('RGBA', (w, h), CORES[nome] + (255,)), name=NOMES[nome],
                             top=c[k][1], left=c[k][0])
    return rap._salvar(p, destino)


@pytest.fixture(scope='module')
def job_sangria(tmp_path_factory):
    import test_fontes_apoio as fap
    from desdobra.job import nucleo
    from desdobra.render import autoteste
    base = tmp_path_factory.mktemp('sangria')
    fontes = base / 'origem-fontes'
    fap.gravar(fontes, 'autoteste.ttf', autoteste.gerar_fonte())
    job = base / 'job'
    nucleo.criar(job, _psd_packshot(base / 'origem' / 'kv.psd'), 'c', fontes=[fontes])
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    ids = {c['nome']: c['identidade']['layer_id'] for c in laudo['camadas']}
    funcoes = {ids[NOMES['fundo']]: 'fundo', ids[NOMES['logo']]: 'logo_principal',
               ids[NOMES['circulo']]: 'grafismo', ids[NOMES['garrafa']]: 'sujeito', ids[NOMES['copo']]: 'sujeito',
               ids[NOMES['lata']]: 'sujeito'}
    b = ap.briefing(funcoes=funcoes, formatos=[ap.formato(i, w, h, rotacao=ROT0) for i, w, h in HORIZONTAIS])
    b.pop('cabecalho')
    b.pop('job_id')
    arq = base / 'fixture.json'
    arq.write_text(json.dumps(b), encoding='utf-8')
    mb.importar_teste(job, arq)
    el = {k: 'el%d' % ids[NOMES[k]] for k in NOMES}
    grupo = [el['garrafa'], el['copo'], el['lata'], el['circulo']]
    return {'job': job, 'el': el, 'grupo': grupo}


def _edicoes_do_job(grupo, edicoes):
    return [dict(e, elemento=grupo[0], elementos=list(grupo)) for e in edicoes]


def test_previa_da_tela_deixa_o_grupo_sangrar_sem_pedir_ajuste(job_sangria):
    from desdobra.tela import estado as te
    conteudo = te.montar(job_sangria['job'])
    gid = next(g for g, f in conteudo['familias'].items() if 'h1' in f['formatos'])
    grupo, el = job_sangria['grupo'], job_sangria['el']
    r = conteudo['editar']({'familia': gid, 'versao': None, 'edicoes': _edicoes_do_job(grupo, DEPOIS)})
    assert r is not None and len(r['membros']) == len(HORIZONTAIS)
    for m in r['membros']:
        W, H = m['palco']['largura'], m['palco']['altura']
        assert m['falhas'] == [] and m['validacoes_reprovadas'] == [], (m['formato'], m['falhas'])
        caixas = {e['id']: e['caixa'] for e in m['palco']['elementos']}
        for k in ('garrafa', 'copo', 'lata'):
            c = caixas[el[k]]
            assert c[0] >= 0 and c[2] <= W and c[3] > H + 1, (m['formato'], k, c)
            assert 'base' in m['sangria_do_da'][el[k]]
        # o palco mostra o que passa do quadro (a parte de fora fica esmaecida na pagina)
        assert m['palco']['fora_do_quadro'] is True


@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
def test_render_corta_no_quadro_o_que_o_da_deixou_sangrar(job_sangria, monkeypatch):
    import numpy as np
    from PIL import Image

    from desdobra.render import execucao
    job, grupo, el = job_sangria['job'], job_sangria['grupo'], job_sangria['el']
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    b['composicoes'] = [{'familia': 'horizontal-1', 'formatos': [i for i, _w, _h in HORIZONTAIS], 'versao': None,
                         'edicoes': _edicoes_do_job(grupo, DEPOIS), 'confirmada': True, 'confirmacao': dict(CONF)}]
    contratos.gravar(job / mb.ARQUIVO, b, 'briefing/1')
    nd.derivar(job)
    d = contratos.ler(job / nd.PASTA / 'h1.json', nd.ESQUEMA)
    assert d['situacao'] == 'derivado', d.get('devolucao')
    caixas = {e['id']: [float(x) for x in e['caixa']] for e in d['elementos']}
    monkeypatch.setattr(humano, 'console_interativo', lambda: (True, None))
    execucao.renderizar(job, disparo=humano.exigir('render'), formato='h1')
    img = np.asarray(Image.open(job / 'render' / 'h1' / 'master.png').convert('RGB')).astype(int)
    H, W = img.shape[:2]
    assert (W, H) == (800, 400)

    # cada pixel fica com a cor lisa mais perto dele, quando esta perto dela (a borda reamostrada entre duas cores fica
    # de fora); a caixa da cor sao as colunas e as linhas com uma faixa dela
    nomes = sorted(CORES)
    dist = np.stack([np.abs(img - np.asarray(CORES[n])).sum(axis=2) for n in nomes])
    perto = np.where(dist.min(axis=0) <= 40, np.argmin(dist, axis=0), -1)  # numero-neutro: folga da cor reamostrada
    faixa = 8  # numero-neutro: pixels da cor numa coluna ou linha para ela contar

    def onde(nome):
        m = perto == nomes.index(nome)
        xs, ys = np.nonzero(m.sum(axis=0) >= faixa)[0], np.nonzero(m.sum(axis=1) >= faixa)[0]
        return [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
    for k in ('garrafa', 'copo', 'lata'):
        c = caixas[el[k]]
        assert c[3] > H + 1
        x0, y0, x1, y1 = onde(k)
        # a caixa da derivacao cortada no quadro: inteira na largura, ate a ultima linha da imagem
        assert (x0, y0, x1) == pytest.approx((c[0], c[1], c[2]), abs=1.5), (k, (x0, y0, x1), c)
        assert y1 == H
    # o circulo vai ate a borda de baixo (e a direita, quando o DA o deixou passar)
    c = caixas[el['circulo']]
    _x0, _y0, x1, y1 = onde("circulo")
    assert y1 == H and (x1 == W) is (c[2] > W)
