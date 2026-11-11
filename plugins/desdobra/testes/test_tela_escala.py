# -*- coding: utf-8 -*-
"""M7b, D3: a escala por numero (decisoes-v1.md, 167; secao 9.8 da arquitetura), escrita antes do codigo.

Criterios de pronto cobertos aqui:
  - o tamanho de cada elemento e a conta dos fatores das edicoes de escalar que o levam, sozinho ou no grupo
    (escalas): 100% e o tamanho antes das edicoes do DA;
  - o tamanho fica entre tela.escala_min e tela.escala_max (0,25 e 4, o fator livre do plano), com a folga do
    arredondamento das fracoes; a previa e o rascunho recusam a edicao que passa disso;
  - a tela manda os dois limites a pagina (estado.edicao);
  - na derivacao da fixture com a estrutura do KV A e na previa do job sintetico, a assinatura escalada a 155% fica com
    1,55 vez a largura e a altura que tinha em cada membro da familia;
  - na tela (Chromium sem janela): o DA digita 155 no campo Tamanho e a assinatura fica com 1,55x (uma edicao de
    escalar so); o campo mostra o tamanho de agora, recusa o numero fora dos limites e vale para o grupo; Aumentar
    para no limite;
  - revisao 1 da fase D: o rascunho com tamanho fora dos limites gravado pela tela de antes nunca trava o job (so o
    tamanho novo mais longe do limite e recusado), e o rascunho recusa o grupo que a previa recusa.
Tudo sintetico: laudo montado a mao, PSD sintetico gerado na hora e a fonte de autoteste do motor."""
import json

import pytest

import test_tela_alinhar as tal
import test_tela_grupo as tgr
from desdobra import contratos
from desdobra import limites
from desdobra.tela import edicao as ed
from desdobra.tela import rascunho as tr

TOL = 0.5  # numero-neutro: px de folga do arredondamento da derivacao
ALVO = 1.55  # numero-neutro: os 155% do criterio de pronto


def _escalar(fator, *ids, **kw):
    e = {'elemento': ids[0], 'acao': 'escalar', 'fator': fator}
    if len(ids) > 1:
        e['elementos'] = list(ids)
    e.update(kw)
    return e


# ------------------------------------------------------------------ o fator e os limites, sem job
def test_limites_da_escala_vem_do_registro():
    assert ed.limites_da_escala() == (limites.valor('tela.escala_min'), limites.valor('tela.escala_max'))
    assert ed.limites_da_escala() == (0.25, 4.0)


def test_escalas_multiplicam_os_fatores_de_cada_elemento():
    eds = [_escalar(1.5, 'a'),
           {'elemento': 'a', 'acao': 'mover', 'dx': 0.1, 'dy': 0.0},
           _escalar(0.5, 'b', 'a', 'c'),
           {'elemento': 'c', 'acao': 'texto', 'texto': 'X'},
           {'elemento': 'b', 'acao': 'alinhar', 'alvo': 'topo', 'referencia': 'margem'}]
    assert ed.escalas(eds) == pytest.approx({'a': 0.75, 'b': 0.5, 'c': 0.5})
    # o elemento sem escalar fica de fora (100%); o apagado sai
    assert ed.escalas(eds + [{'elemento': 'c', 'acao': 'apagar'}]) == pytest.approx({'a': 0.75, 'b': 0.5})
    assert ed.escalas([]) == {}


@pytest.mark.parametrize('edicoes, fora', [
    ([_escalar(ALVO, 'a')], []),
    ([_escalar(4.0, 'a')], []),
    ([_escalar(0.25, 'a')], []),
    ([_escalar(4.01, 'a')], ['a']),
    ([_escalar(0.2, 'a')], ['a']),
    ([_escalar(2.0, 'a'), _escalar(2.0, 'a')], []),
    ([_escalar(2.0, 'a'), _escalar(2.1, 'a', 'b')], ['a']),
    ([_escalar(0.5, 'a', 'b'), _escalar(0.5, 'a')], []),
    ([_escalar(0.5, 'a', 'b'), _escalar(0.4, 'b', 'a')], ['a', 'b']),
    # a conta da pagina com o fator arredondado em 6 casas: 0,3 x 0,833333 fica dentro pela folga
    ([_escalar(0.3, 'a'), _escalar(0.833333, 'a')], []),
    ([_escalar(4.0, 'a'), _escalar(1.000001, 'a')], []),
])
def test_escala_fora_dos_limites(edicoes, fora):
    assert ed.escala_fora(edicoes) == fora


# ------------------------------------------------------------------ a derivacao da fixture com a estrutura do KV A
ASSINATURA = 'el%d' % tal.ASSINATURA


def test_derivacao_escala_a_assinatura_a_155_em_cada_membro():
    _ctx, antes = tal._derivar([])
    _ctx, depois = tal._derivar([_escalar(ALVO, ASSINATURA)])
    for fs in tal.FAMILIAS.values():
        for fid, _w, _h in fs:
            a, d = tal._caixas(antes[fid])[ASSINATURA], tal._caixas(depois[fid])[ASSINATURA]
            assert depois[fid]['situacao'] == 'derivado', (fid, depois[fid].get('devolucao'))
            assert d[2] - d[0] == pytest.approx(ALVO * (a[2] - a[0]), abs=TOL), (fid, a, d)
            assert d[3] - d[1] == pytest.approx(ALVO * (a[3] - a[1]), abs=TOL), (fid, a, d)


# ------------------------------------------------------------------ o job sintetico com a assinatura
NOMES = dict(tgr.NOMES, assinatura='assinatura-sintetica')
CAIXA_ASSINATURA = [20, 150, 70, 180]


def _psd_com_assinatura(destino, ps):
    """O PSD do packshot (test_tela_grupo) com a assinatura no canto de baixo a esquerda, uma camada de pixels."""
    from PIL import Image
    from psd_tools import PSDImage

    import test_render_apoio as rap
    tgr._psd_packshot(destino, ps)
    p = PSDImage.open(destino)
    c = CAIXA_ASSINATURA
    p.create_pixel_layer(Image.new('RGBA', (c[2] - c[0], c[3] - c[1]), (40, 40, 120, 255)), name=NOMES['assinatura'],
                         top=c[1], left=c[0])
    return rap._salvar(p, destino)


@pytest.fixture(scope='module')
def job_escala(tmp_path_factory):
    import test_derivacao_apoio as ap
    import test_fontes_apoio as fap
    from desdobra.briefing import modelo as mb
    from desdobra.job import nucleo
    from desdobra.render import autoteste
    base = tmp_path_factory.mktemp('escala')
    fontes = base / 'origem-fontes'
    fap.gravar(fontes, 'autoteste.ttf', autoteste.gerar_fonte())
    job = base / 'job'
    nucleo.criar(job, _psd_com_assinatura(base / 'origem' / 'kv.psd', autoteste.NOME_PS), 'c', fontes=[fontes])
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    ids = {c['nome']: c['identidade']['layer_id'] for c in laudo['camadas']}
    funcoes = {ids[NOMES['fundo']]: 'fundo', ids[NOMES['titulo']]: 'titulo', ids[NOMES['circulo']]: 'grafismo',
               ids[NOMES['garrafa']]: 'sujeito', ids[NOMES['copo']]: 'sujeito',
               ids[NOMES['assinatura']]: 'logo_principal'}
    b = ap.briefing(funcoes=funcoes, formatos=[ap.formato(i, w, h) for i, w, h in tgr.HORIZONTAIS])
    b.pop('cabecalho')
    b.pop('job_id')
    arq = base / 'fixture.json'
    arq.write_text(json.dumps(b), encoding='utf-8')
    mb.importar_teste(job, arq)
    return {'job': job, 'assinatura': 'el%d' % ids[NOMES['assinatura']],
            'grupo': ['el%d' % ids[NOMES[k]] for k in ('garrafa', 'copo', 'circulo')]}


@pytest.fixture(scope='module')
def conteudo_escala(job_escala):
    from desdobra.tela import estado as te
    return te.montar(job_escala['job'])


def _familia(conteudo):
    return next(g for g, f in conteudo['familias'].items() if 'h1' in f['formatos'])


def _caixa(r, fid, eid):
    m = next(x for x in r['membros'] if x['formato'] == fid)
    return next([float(v) for v in e['caixa']] for e in m['palco']['elementos'] if e['id'] == eid)


def _confere_155(antes, depois, eid, k=ALVO):
    for fid, _w, _h in tgr.HORIZONTAIS:
        a, d = _caixa(antes, fid, eid), _caixa(depois, fid, eid)
        assert d[2] - d[0] == pytest.approx(k * (a[2] - a[0]), abs=TOL), (fid, a, d)
        assert d[3] - d[1] == pytest.approx(k * (a[3] - a[1]), abs=TOL), (fid, a, d)


def test_estado_manda_os_limites_da_escala_a_pagina(conteudo_escala):
    assert conteudo_escala['estado']['edicao']['escala_min'] == 0.25
    assert conteudo_escala['estado']['edicao']['escala_max'] == 4.0


def test_previa_escala_a_assinatura_a_155_em_cada_arquivo(job_escala, conteudo_escala):
    gid = _familia(conteudo_escala)
    eid = job_escala['assinatura']
    antes = conteudo_escala['editar']({'familia': gid, 'versao': None, 'edicoes': []})
    depois = conteudo_escala['editar']({'familia': gid, 'versao': None, 'edicoes': [_escalar(ALVO, eid)]})
    assert depois is not None and len(depois['membros']) == len(tgr.HORIZONTAIS)
    _confere_155(antes, depois, eid)


@pytest.mark.parametrize('edicoes', [
    lambda a, g: [_escalar(4.5, a)],
    lambda a, g: [_escalar(0.2, a)],
    lambda a, g: [_escalar(3.0, a), _escalar(1.5, a)],
    lambda a, g: [_escalar(0.5, *g), _escalar(0.4, g[1])],
])
def test_previa_recusa_escala_fora_dos_limites(job_escala, conteudo_escala, edicoes):
    gid = _familia(conteudo_escala)
    eds = edicoes(job_escala['assinatura'], job_escala['grupo'])
    assert conteudo_escala['editar']({'familia': gid, 'versao': None, 'edicoes': eds}) is None


def test_rascunho_recusa_escala_fora_dos_limites(job_escala, conteudo_escala):
    job = job_escala['job']
    gid = _familia(conteudo_escala)
    laudo = tr.laudo_sha256(job)
    job_id = conteudo_escala['estado']['job_id']

    def mandar(edicoes):
        return {'job_id': job_id, 'laudo_sha256': laudo,
                'familias': {gid: {'versao': None, 'confirmada': False, 'edicoes': edicoes}}}
    try:
        with pytest.raises(tr.ErroRascunho) as erro:
            tr.gravar(job, mandar([_escalar(5.0, job_escala['assinatura'])]), job_id=job_id, laudo_atual=laudo,
                      origem='rascunho')
        assert erro.value.motivo == 'escala'
        assert not (job / tr.ARQUIVO).exists()
        gravado = tr.gravar(job, mandar([_escalar(4.0, job_escala['assinatura'])]), job_id=job_id, laudo_atual=laudo,
                            origem='rascunho')
        assert gravado['familias'][gid]['edicoes'][0]['fator'] == 4.0
    finally:
        tgr._limpar_rascunho(job)


# ------------------------------------------------------------------ revisao 1 da fase D: o rascunho de antes do D3
# A tela de antes do D3 nao tinha o limite do tamanho acumulado: o canto so parava cada edicao em 0,05. O rascunho
# gravado por ela continua valendo (rascunho-tela/1). O tamanho que ele ja tinha fora dos limites nunca trava o job: a
# familia abre, as outras gravam, e o DA conserta pela tela. So a edicao nova que leva o tamanho para mais longe dos
# limites e recusada
ORIGEM = 'fixture_de_teste'  # o modo de teste da tela so abre o job sintetico


def _velhas(a):
    return [_escalar(0.45, a, fx=0, fy=1), _escalar(0.45, a, fx=0, fy=1)]  # numero-neutro: dois cantos de antes, 20%


def test_escala_fora_so_conta_o_tamanho_novo_mais_longe_dos_limites():
    velhas = _velhas('a')
    assert ed.escala_fora(velhas) == ['a']
    # o que ja estava gravado fora dos limites passa, e o conserto tambem
    assert ed.escala_fora(velhas, antes=velhas) == []
    assert ed.escala_fora(velhas + [{'elemento': 'a', 'acao': 'mover', 'dx': 0.01, 'dy': 0}], antes=velhas) == []
    assert ed.escala_fora(velhas + [_escalar(0.3 / 0.2025, 'a')], antes=velhas) == []
    assert ed.escala_fora(velhas + [_escalar(1.1, 'a')], antes=velhas) == []
    # o tamanho que vai mais longe do limite, ou passa do outro lado, e recusado
    assert ed.escala_fora(velhas + [_escalar(0.9, 'a')], antes=velhas) == ['a']
    assert ed.escala_fora(velhas + [_escalar(0.9, 'b')], antes=velhas) == []
    assert ed.escala_fora(velhas + [_escalar(0.2, 'b')], antes=velhas) == ['b']
    # so o tamanho final conta: o conserto que passa pelo meio do caminho fica dentro
    assert ed.escala_fora([_escalar(0.2, 'a'), _escalar(2.0, 'a')]) == []


def test_rascunho_de_antes_dos_limites_nunca_trava_o_job(job_escala, conteudo_escala, monkeypatch):
    from desdobra.tela import atos as ta
    from desdobra.tela import servidor as ts
    job, a = job_escala['job'], job_escala['assinatura']
    gid = _familia(conteudo_escala)
    laudo = tr.laudo_sha256(job)
    job_id = conteudo_escala['estado']['job_id']
    velhas = _velhas(a)

    def mandar(edicoes):
        return {'job_id': job_id, 'laudo_sha256': laudo,
                'familias': {gid: {'versao': None, 'confirmada': False, 'edicoes': edicoes}}}
    try:
        # o arquivo como a tela de antes o gravou (sem a conferencia do tamanho)
        with monkeypatch.context() as m:
            m.setattr(ed, 'escala_fora', lambda edicoes, antes=None: [])
            tr.gravar(job, mandar(velhas), job_id=job_id, laudo_atual=laudo, origem=ORIGEM)
        # o DA anda o titulo: o rascunho grava
        andar = velhas + [{'elemento': job_escala['grupo'][0], 'acao': 'mover', 'dx': 0.01, 'dy': 0}]
        tr.gravar(job, mandar(andar), job_id=job_id, laudo_atual=laudo, origem=ORIGEM)
        # o conserto pela tela (Tamanho 30%) grava tambem
        conserto = andar + [_escalar(round(0.3 / 0.2025, 6), a)]
        tr.gravar(job, mandar(conserto), job_id=job_id, laudo_atual=laudo, origem=ORIGEM)
        assert tgr._edicoes(job, gid) == conserto
        # e a que leva a assinatura para mais longe do limite continua recusada
        with pytest.raises(tr.ErroRascunho) as erro:
            tr.gravar(job, mandar(velhas + [_escalar(0.9, a)]), job_id=job_id, laudo_atual=laudo, origem=ORIGEM)
        assert erro.value.motivo == 'escala'
        # a previa pela rota do servidor confere contra o rascunho gravado: a familia de antes abre
        with monkeypatch.context() as m:
            m.setattr(ed, 'escala_fora', lambda edicoes, antes=None: [])
            tr.gravar(job, mandar(velhas), job_id=job_id, laudo_atual=laudo, origem=ORIGEM)
        with ts.ServidorTela(conteudo_escala, pasta=job, modo_teste=True,
                             atos=ta.atos_do_job(job, conteudo=conteudo_escala)) as srv:
            for eds in (velhas, conserto[:2] + conserto[-1:]):
                r = srv._previa_da_familia({'familia': gid, 'versao': None, 'edicoes': eds})
                assert r is not None and r[0] == 200 and r[1]['membros'], eds  # numero-neutro: codigo HTTP
            assert srv._previa_da_familia({'familia': gid, 'versao': None,
                                           'edicoes': velhas + [_escalar(0.9, a)]}) is None
    finally:
        tgr._limpar_rascunho(job)


@pytest.mark.parametrize('grupo', [
    lambda a, g: {'elemento': a, 'acao': 'mover', 'dx': 0.01, 'dy': 0, 'elementos': [g[0], g[1]]},
    lambda a, g: {'elemento': a, 'acao': 'escalar', 'fator': 0.9, 'elementos': [a, 'el999']},
    lambda a, g: {'elemento': 'el999', 'acao': 'mover', 'dx': 0.01, 'dy': 0},
], ids=['elemento_fora_da_lista', 'id_que_o_kv_nao_tem', 'elemento_que_o_kv_nao_tem'])
def test_rascunho_recusa_o_grupo_que_a_previa_recusa(job_escala, conteudo_escala, grupo):
    job = job_escala['job']
    gid = _familia(conteudo_escala)
    laudo = tr.laudo_sha256(job)
    job_id = conteudo_escala['estado']['job_id']
    eds = [grupo(job_escala['assinatura'], job_escala['grupo'])]
    try:
        assert conteudo_escala['editar']({'familia': gid, 'versao': None, 'edicoes': eds}) is None
        with pytest.raises(tr.ErroRascunho) as erro:
            tr.gravar(job, {'job_id': job_id, 'laudo_sha256': laudo,
                            'familias': {gid: {'versao': None, 'confirmada': False, 'edicoes': eds}}},
                      job_id=job_id, laudo_atual=laudo, origem='rascunho',
                      elementos_da_tela=conteudo_escala['elementos'])
        assert erro.value.motivo == 'edicao'
        assert not (job / tr.ARQUIVO).exists()
    finally:
        tgr._limpar_rascunho(job)


# ------------------------------------------------------------------ a tela no Chromium sem janela (modo de teste)
def _tamanho(pg):
    return pg.evaluate('() => document.getElementById("ed-tamanho").value')


def _digitar(pg, texto, enter=True):
    pg.fill('#ed-tamanho', texto)
    if enter:
        pg.press('#ed-tamanho', 'Enter')
    else:
        pg.evaluate('() => document.getElementById("ed-tamanho-aplicar").click()')


def test_escala_por_numero_na_tela_do_chromium(job_escala, conteudo_escala):
    from playwright.sync_api import sync_playwright

    import test_tela_galeria as tg
    import test_tela_palco as tp
    from desdobra.chromium import navegador
    from desdobra.tela import atos as ta
    from desdobra.tela import servidor as ts
    job, eid, grupo = job_escala['job'], job_escala['assinatura'], job_escala['grupo']
    tgr._limpar_rascunho(job)
    estado = conteudo_escala['estado']
    gid = _familia(conteudo_escala)
    base = conteudo_escala['editar']({'familia': gid, 'versao': None, 'edicoes': []})
    salvo = '() => (document.documentElement.dataset.rascunho === "salvo" && ' \
            'document.documentElement.dataset.previa === "pronta") ? "1" : ""'
    msg = '() => document.getElementById("ed-mensagem").textContent'
    navegador.apontar_playwright()
    with ts.ServidorTela(conteudo_escala, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo_escala)) as srv, sync_playwright() as pw:
        nav, pg = tp._pagina_da_tela(pw, srv, 2048, 720)  # numero-neutro: a tela do Duda (decisao 157)
        try:
            tg._abrir(pg, estado, 'h1')
            tp._esperar(pg, '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""')
            # sem nada escolhido, o campo e o botao ficam desligados; o rotulo diz o que e
            assert pg.evaluate('() => document.getElementById("ed-tamanho").disabled') is True
            assert pg.evaluate('() => document.getElementById("ed-tamanho-aplicar").disabled') is True
            assert pg.evaluate('() => document.querySelector("label[for=ed-tamanho]").textContent.trim()') == 'Tamanho'
            assert pg.evaluate('() => document.getElementById("ed-tamanho-aplicar").textContent.trim()') == 'Aplicar'
            # a assinatura escolhida: o campo mostra 100 (o tamanho antes das edicoes)
            x, y = tgr._ponto(pg, eid)
            pg.mouse.click(x, y)
            assert pg.evaluate('() => document.getElementById("ed-tamanho").disabled') is False
            assert _tamanho(pg) == '100'
            # o criterio de pronto: o DA digita 155 e aperta Enter; uma edicao de escalar so, com 1,55
            _digitar(pg, '155')
            tp._esperar(pg, salvo)
            eds = tgr._edicoes(job, gid)
            assert eds == [{'elemento': eid, 'acao': 'escalar', 'fator': ALVO}]
            _confere_155(base, conteudo_escala['editar']({'familia': gid, 'versao': None, 'edicoes': eds}), eid)
            assert _tamanho(pg) == '155'
            assert '155%' in pg.evaluate(msg)
            # a assinatura no palco do Chromium (px da peca): 1,55 vez a largura e a altura de antes
            tam = pg.evaluate('''i => { const r = document.querySelector('#palco .rotulo[data-elemento="' + i + '"]');
                return [parseFloat(r.style.width), parseFloat(r.style.height)]; }''', eid)
            a = _caixa(base, 'h1', eid)
            assert tam == pytest.approx([ALVO * (a[2] - a[0]), ALVO * (a[3] - a[1])], abs=TOL)
            # digitar o mesmo numero de novo nao grava nada: o numero e o tamanho, nao um aumento
            _digitar(pg, '155 %')
            assert len(tgr._edicoes(job, gid)) == 1
            # com virgula e pelo botao Aplicar: 120,5% vira o fator que leva de 155% a 120,5%
            _digitar(pg, '120,5', enter=False)
            tp._esperar(pg, salvo)
            eds = tgr._edicoes(job, gid)
            assert len(eds) == 2 and eds[1]['fator'] == pytest.approx(1.205 / ALVO, abs=1e-6)
            assert _tamanho(pg) == '120,5'
            # fora dos limites ou sem numero: nada e gravado, e a tela diz o que fazer
            for texto in ('500', '10', 'abc', ''):
                _digitar(pg, texto)
                assert len(tgr._edicoes(job, gid)) == 2, texto
                assert pg.evaluate('() => document.getElementById("ed-tamanho").getAttribute("aria-invalid")') == 'true'
                assert '25%' in pg.evaluate(msg) and '400%' in pg.evaluate(msg), texto
            # 400% e o teto: Aumentar ali nao grava nada e diz que chegou ao limite
            _digitar(pg, '400')
            tp._esperar(pg, salvo)
            assert len(tgr._edicoes(job, gid)) == 3
            assert pg.evaluate('() => document.getElementById("ed-tamanho").getAttribute("aria-invalid")') is None
            assert _tamanho(pg) == '400'
            assert pg.evaluate('() => document.getElementById("ed-aumentar").disabled') is True
            pg.evaluate('() => document.getElementById("ed-diminuir").click()')
            tp._esperar(pg, salvo)
            assert len(tgr._edicoes(job, gid)) == 4 and _tamanho(pg) == '381'
            pg.evaluate('() => document.getElementById("ed-aumentar").click()')
            tp._esperar(pg, salvo)
            pg.evaluate('() => document.getElementById("ed-aumentar").click()')
            tp._esperar(pg, salvo)
            eds = tgr._edicoes(job, gid)
            assert ed.escala_fora(eds) == [] and _tamanho(pg) == '400'
            # o grupo do packshot: o campo mostra 100, e 80 grava uma edicao so, com a lista
            x, y = tgr._ponto(pg, grupo[0])
            pg.mouse.click(x, y)
            for g in grupo[1:]:
                tgr._shift_clique(pg, g)
            assert _tamanho(pg) == '100'
            n = len(eds)
            _digitar(pg, '80')
            tp._esperar(pg, salvo)
            eds = tgr._edicoes(job, gid)
            assert len(eds) == n + 1 and eds[-1] == {'elemento': grupo[0], 'elementos': grupo, 'acao': 'escalar',
                                                     'fator': 0.8}
            assert _tamanho(pg) == '80'
            # um do grupo com outro tamanho: o campo mostra 100, o tamanho do grupo desde que ele foi escolhido, e diz
            # que os tamanhos sao diferentes (revisao 1 da fase D: o campo vazio com "Vários" nao dizia o que valia)
            pg.keyboard.press('Escape')
            x, y = tgr._ponto(pg, grupo[0])
            pg.mouse.click(x, y)
            _digitar(pg, '100')
            tp._esperar(pg, salvo)
            for g in grupo[1:]:
                tgr._shift_clique(pg, g)
            assert _tamanho(pg) == '100'
            assert 'tamanhos diferentes' in pg.evaluate('() => document.getElementById("ed-tamanho").title')
            texto = pg.evaluate(tp.JS_TEXTO_DA_MOLDURA)
            assert not tp.IDENTIFICADOR.findall(texto), tp.IDENTIFICADOR.findall(texto)
            assert '—' not in texto and '–' not in texto
        finally:
            nav.close()
        contagem = dict(srv.contagem)
    assert contagem['proibido'] == 0 and contagem['csrf_recusado'] == 0 and contagem['dado_recusado'] == 0
    tgr._limpar_rascunho(job)
