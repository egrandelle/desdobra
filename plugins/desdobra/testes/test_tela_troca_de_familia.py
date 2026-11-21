# -*- coding: utf-8 -*-
"""A edicao continua depois de trocar de familia (relato do Duda em 19/11: ao mudar de familia, o palco deixava de
aceitar edicao ate recarregar a pagina). No Chromium sem janela, com o KV sintetico da diagonal: edita uma familia,
abre outra, edita nela pelo clique e pela seta, e volta a primeira."""
import json

import pytest

import test_tela_edicao as tte
import test_tela_familia_0100 as tf
import test_tela_palco as tp
from desdobra.tela import atos as ta
from desdobra.tela import rascunho as tr
from desdobra.tela import servidor as ts


def _edicoes(job, gid):
    arq = job / tr.ARQUIVO
    dados = json.loads(arq.read_text(encoding='utf-8')) if arq.exists() else {}
    return json.dumps(((dados.get('familias') or {}).get(gid) or {}).get('edicoes') or [], sort_keys=True)


def _um_de_conteudo(pg):
    return pg.evaluate('() => (document.querySelector("#palco .rotulo.editavel.de-conteudo") || {}).dataset.elemento')


# um ponto do elemento em que o clique chega nele: o meio, ou outro ponto da caixa quando a etiqueta de nome cobre o
# meio (no elemento pequeno na tela, o arraste na etiqueta de quem nao esta escolhido desenha o retangulo de selecao)
PONTO_NO_ELEMENTO = '''i => { const r = document.querySelector('#palco .rotulo[data-elemento="' + i + '"]');
    const c = r.getBoundingClientRect();
    for (const [fx, fy] of [[0.5, 0.5], [0.5, 0.8], [0.25, 0.8], [0.75, 0.8], [0.25, 0.5], [0.75, 0.5], [0.5, 0.2]]) {
        const x = c.left + c.width * fx, y = c.top + c.height * fy;
        const t = document.elementFromPoint(x, y);
        if (t && t.closest('#palco .rotulo') === r && !t.closest('.etiqueta')) return [x, y];
    }
    return [c.left + c.width / 2, c.top + c.height / 2]; }'''


def _clicar_no_meio(pg, eid):
    caixa = pg.evaluate(PONTO_NO_ELEMENTO, eid)
    pg.mouse.click(caixa[0], caixa[1])


def _arrastar(pg, eid):
    x, y = pg.evaluate(PONTO_NO_ELEMENTO, eid)
    pg.mouse.move(x, y)
    pg.mouse.down()
    for k in range(1, 6):
        pg.mouse.move(x + 4 * k, y + 2 * k)
    pg.mouse.up()


def _editar(pg, job, gid, arrastando=False):
    antes = _edicoes(job, gid)
    eid = _um_de_conteudo(pg)
    assert eid, 'o palco da familia %s nao tem elemento editavel' % gid
    if arrastando:
        _arrastar(pg, eid)
    else:
        _clicar_no_meio(pg, eid)
        tp._esperar(pg, '() => document.querySelector("#palco .rotulo.selecionado") ? "1" : ""', teto_s=10)
        pg.keyboard.press('ArrowRight')
    tte._esperar_salvo(pg)
    # o mover seguido do mesmo elemento se junta numa edicao so: vale que as edicoes da familia mudaram
    assert _edicoes(job, gid) != antes, (gid, antes)


@pytest.fixture
def novo(tmp_path):
    return tf._job(tmp_path)


def test_editar_depois_de_trocar_de_familia(novo):
    from playwright.sync_api import sync_playwright

    from desdobra.chromium import navegador
    job, conteudo = novo['job'], novo['conteudo']
    estado = conteudo['estado']
    gids = [g['id'] for o in estado['orientacoes'] for g in o['grupos']]
    assert len(gids) >= 2, gids
    navegador.apontar_playwright()
    with ts.ServidorTela(conteudo, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo)) as srv, sync_playwright() as pw:
        nav, pg = tf._pagina(pw, srv)
        try:
            # todas as familias, de aba em aba, pelo clique e pelo arraste; depois a primeira de novo
            for arrastando in (False, True):
                for gid in gids + gids[:1]:
                    tf._abrir_familia(pg, estado, gid)
                    _editar(pg, job, gid, arrastando)
        finally:
            nav.close()


def test_editar_depois_de_trocar_de_familia_com_a_previa_lenta(novo):
    """O job real leva segundos na previa: o DA mexe numa familia e troca de familia antes de a previa voltar."""
    import time

    from playwright.sync_api import sync_playwright

    from desdobra.chromium import navegador
    job, conteudo = novo['job'], novo['conteudo']
    estado = conteudo['estado']
    gids = [g['id'] for o in estado['orientacoes'] for g in o['grupos']]
    editar = conteudo['editar']

    def lento(dados, *a, **k):
        time.sleep(1.5)  # numero-neutro: segundos, a previa de um job real
        return editar(dados, *a, **k)
    conteudo = dict(conteudo, editar=lento)
    navegador.apontar_playwright()
    with ts.ServidorTela(conteudo, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo)) as srv, sync_playwright() as pw:
        nav, pg = tf._pagina(pw, srv)
        try:
            a, b = gids[0], gids[-1]
            tf._abrir_familia(pg, estado, a)
            eid = _um_de_conteudo(pg)
            _clicar_no_meio(pg, eid)
            pg.keyboard.press('ArrowRight')
            # sem esperar a previa: troca de familia ja
            o = next(o for o in estado['orientacoes'] if any(g['id'] == b for g in o['grupos']))
            tp._clicar_aba(pg, 'orientacoes', o['rotulo'])
            tp._clicar_grupo(pg, b)
            tp._esperar(pg, '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""')
            pg.wait_for_timeout(3000)  # numero-neutro: ms, as previas atrasadas chegam
            _editar(pg, job, b)
            _editar(pg, job, b, arrastando=True)
        finally:
            nav.close()
