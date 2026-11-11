# -*- coding: utf-8 -*-
"""Revisao 1 da fase D do M7b: os defeitos da tela e do rascunho que a revisao achou, escritos antes do codigo.

Criterios cobertos aqui:
  - a gravacao atomica tenta de novo quando o Windows recusa a troca do arquivo que alguem le naquele instante (o
    laco de espera de um teste, um antivirus); a pagina que nao conseguiu gravar o rascunho tenta de novo sozinha, e
    "Confirmar família" fica desligado enquanto a ultima escolha nao esta gravada;
  - Tamanho, Diminuir e Aumentar mudam o tamanho em volta do meio, menos no lado em que o escolhido chega a borda da
    peca: ali ele fica preso a borda (o circulo que sangra na base continua na base);
  - "Escolher vários" ligado: arrastar um escolhido leva o grupo, e o clique sem arrastar tira o elemento do grupo;
  - o retangulo de selecao comeca tambem em cima da etiqueta de um elemento que nao esta escolhido;
  - no grupo com tamanhos diferentes, o campo Tamanho mostra o tamanho do grupo desde que ele foi escolhido (100
    no comeco), e digitar o mesmo numero de novo nao grava nada;
  - os botoes de alinhar dizem "Centro da largura" e "Meio da altura";
  - depois de Diminuir, Aumentar ou Alinhar, o foco volta ao escolhido (as setas e Esc seguem valendo);
  - Delete com o grupo escolhido diz por que nao apaga;
  - a barra de edicao cabe em duas linhas na tela larga, e o resumo do grupo nunca e cortado.
Tudo sintetico: PSD sintetico gerado na hora e a fonte de autoteste do motor."""
import contextlib
import sys
import threading
import time

import pytest

import test_tela_grupo as tgr
from desdobra import arquivos
from desdobra.tela import rascunho as tr
from test_tela_escala import conteudo_escala, job_escala  # noqa: F401 - o packshot com a assinatura
from test_tela_sangria import job_sangria  # noqa: F401 - o circulo que sangra na base do KV

SALVO = '() => (document.documentElement.dataset.rascunho === "salvo" && ' \
        'document.documentElement.dataset.previa === "pronta") ? "1" : ""'
MSG = '() => document.getElementById("ed-mensagem").textContent'
FOCO = '() => { const a = document.activeElement; return a && a.closest(".rotulo") ? a.closest(".rotulo")' \
       '.dataset.elemento : (a ? a.id : null); }'


@contextlib.contextmanager
def _tela(conteudo, job, largura, altura):
    """O servidor da tela no modo de teste e a pagina aberta no h1, com o rascunho limpo; devolve (srv, pg, gid)."""
    from playwright.sync_api import sync_playwright

    import test_tela_galeria as tg
    import test_tela_palco as tp
    from desdobra.chromium import navegador
    from desdobra.tela import atos as ta
    from desdobra.tela import servidor as ts
    tgr._limpar_rascunho(job)
    gid = next(g for g, f in conteudo['familias'].items() if 'h1' in f['formatos'])
    navegador.apontar_playwright()
    with ts.ServidorTela(conteudo, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo)) as srv, sync_playwright() as pw:
        nav, pg = tp._pagina_da_tela(pw, srv, largura, altura)
        try:
            tg._abrir(pg, conteudo['estado'], 'h1')
            tp._esperar(pg, '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""')
            yield srv, pg, gid
        finally:
            nav.close()
        c = srv.contagem
        assert c['proibido'] == 0 and c['csrf_recusado'] == 0 and c['dado_recusado'] == 0, dict(c)
    tgr._limpar_rascunho(job)


def _esperar_edicoes(pg, job, gid, n):
    import test_tela_palco as tp
    fim = time.monotonic() + 30  # numero-neutro: segundos de teto do teste
    while len(tgr._edicoes(job, gid)) < n:
        assert time.monotonic() < fim, tgr._edicoes(job, gid)
        pg.wait_for_timeout(100)  # numero-neutro: ms, intervalo do teste
    tp._esperar(pg, SALVO)
    return tgr._edicoes(job, gid)


def _arrastar(pg, x, y, dx, dy):
    pg.mouse.move(x, y)
    pg.mouse.down()
    pg.mouse.move(x + dx, y + dy, steps=6)  # numero-neutro: passos do arrasto
    pg.mouse.up()


# ------------------------------------------------------------------ a gravacao atomica com o arquivo aberto por outro
@pytest.mark.skipif(sys.platform != 'win32', reason='so o Windows recusa trocar o arquivo aberto')
def test_gravacao_atomica_espera_o_leitor_soltar_o_arquivo(tmp_path):
    arq = tmp_path / 'rascunho.json'
    arq.write_bytes(b'antes')
    leitor = open(arq, 'rb')

    def soltar():
        time.sleep(0.15)  # numero-neutro: o leitor solta o arquivo depois de um instante
        leitor.close()
    t = threading.Thread(target=soltar)
    t.start()
    try:
        arquivos.gravar_bytes_atomico(arq, b'depois')
    finally:
        t.join()
        leitor.close()
    assert arq.read_bytes() == b'depois'
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(arquivos.PREFIXO_TEMPORARIO)]


# ------------------------------------------------------------------ Tamanho preso a borda (o circulo na base)
def test_tamanho_no_elemento_na_borda_fica_preso_a_ela(job_sangria):  # noqa: F811
    from desdobra.tela import estado as te
    job, el = job_sangria['job'], job_sangria['el']
    conteudo = te.montar(job)
    with _tela(conteudo, job, 1600, 900) as (_srv, pg, gid):  # numero-neutro: janela do teste
        x, y = tgr._ponto(pg, el['circulo'])
        pg.mouse.click(x, y)
        pg.fill('#ed-tamanho', '70')
        pg.press('#ed-tamanho', 'Enter')
        eds = _esperar_edicoes(pg, job, gid, 1)
        # o circulo chega a base da peca: o ponto fixo e o meio da base, e o corte do KV fica fora do quadro
        assert eds == [{'elemento': el['circulo'], 'acao': 'escalar', 'fator': 0.7, 'fx': 0.5, 'fy': 1}], eds
        r = conteudo['editar']({'familia': gid, 'versao': None, 'edicoes': eds})
        for m in r['membros']:
            assert not [f for f in m['falhas'] if f['codigo'] == 'corte_a_mostra'], (m['formato'], m['falhas'])
        # a garrafa, longe das bordas, muda em volta do meio (a edicao sem ponto fixo)
        pg.keyboard.press('Escape')
        x, y = tgr._ponto(pg, el['garrafa'])
        pg.mouse.click(x, y)
        pg.evaluate('() => document.getElementById("ed-diminuir").click()')
        eds = _esperar_edicoes(pg, job, gid, 2)
        assert set(eds[1]) == {'elemento', 'acao', 'fator'}, eds[1]


# ------------------------------------------------------------------ "Escolher vários" e o arraste do grupo
def test_escolher_varios_ligado_deixa_arrastar_o_grupo(job_escala, conteudo_escala):  # noqa: F811
    job, grupo = job_escala['job'], job_escala['grupo']
    with _tela(conteudo_escala, job, 1600, 900) as (_srv, pg, gid):  # numero-neutro: janela do teste
        pg.click('#ed-varios')
        for eid in grupo:
            x, y = tgr._ponto(pg, eid)
            pg.mouse.click(x, y)
        assert pg.evaluate(tgr.JS_ESCOLHIDOS) == sorted(grupo)
        # o DA arrasta a garrafa para mover o packshot: o grupo anda inteiro e continua escolhido
        x, y = tgr._ponto(pg, grupo[0])
        _arrastar(pg, x, y, 0, 20)  # numero-neutro: px de tela
        eds = _esperar_edicoes(pg, job, gid, 1)
        assert len(eds) == 1 and eds[0]['acao'] == 'mover' and eds[0]['elementos'] == grupo, eds
        assert pg.evaluate(tgr.JS_ESCOLHIDOS) == sorted(grupo)
        # o clique sem arrastar, com o modo ligado, tira o copo do grupo
        x, y = tgr._ponto(pg, grupo[1])
        pg.mouse.click(x, y)
        assert pg.evaluate(tgr.JS_ESCOLHIDOS) == sorted([grupo[0], grupo[2]])
        assert len(tgr._edicoes(job, gid)) == 1


# ------------------------------------------------------------------ o retangulo comeca na etiqueta
JS_NA_ETIQUETA = """i => {
  const rot = document.querySelector('#palco .rotulo[data-elemento="' + i + '"]');
  const caixa = rot.getBoundingClientRect();
  const e = rot.querySelector('.etiqueta').getBoundingClientRect();
  for (let fy = 0.5; fy < 1; fy += 0.2) {
    for (let fx = 0.1; fx < 1; fx += 0.1) {
      const x = e.left + fx * e.width, y = e.top + fy * e.height;
      const dentro = x >= caixa.left && x <= caixa.right && y >= caixa.top && y <= caixa.bottom;
      const no = document.elementFromPoint(x, y);
      if (!dentro && no && no.closest('.etiqueta') && no.closest('.rotulo') === rot) return [x, y];
    }
  }
  return null;
}"""
JS_INTEIROS_NO_RETANGULO = """r => Array.from(document.querySelectorAll('#palco .rotulo.editavel')).filter(n => {
  const b = n.getBoundingClientRect();
  return b.left >= r[0] && b.top >= r[1] && b.right <= r[2] && b.bottom <= r[3];
}).map(n => n.dataset.elemento).sort()"""


def test_retangulo_comeca_na_etiqueta_do_elemento_nao_escolhido(job_escala, conteudo_escala):  # noqa: F811
    job, grupo = job_escala['job'], job_escala['grupo']
    with _tela(conteudo_escala, job, 2048, 720) as (_srv, pg, gid):  # numero-neutro: a tela do Duda (decisao 157)
        p = pg.evaluate(JS_NA_ETIQUETA, grupo[0])
        assert p, 'a etiqueta da garrafa fica coberta'
        fim = pg.evaluate('() => { const r = document.getElementById("palco").getBoundingClientRect();'
                          ' return [r.right - 4, r.bottom - 4]; }')
        _arrastar(pg, p[0], p[1], fim[0] - p[0], fim[1] - p[1])
        # nada andou: o arraste a partir da etiqueta e o retangulo de selecao
        pg.wait_for_timeout(600)  # numero-neutro: ms, mais que a espera do rascunho
        assert tgr._edicoes(job, gid) == []
        esperado = pg.evaluate(JS_INTEIROS_NO_RETANGULO, [min(p[0], fim[0]), min(p[1], fim[1]),
                                                          max(p[0], fim[0]), max(p[1], fim[1])])
        assert esperado and pg.evaluate(tgr.JS_ESCOLHIDOS) == esperado
        # o clique sem arrastar na etiqueta escolhe o elemento dela (a linha fina so se pega pela etiqueta)
        pg.keyboard.press('Escape')
        p = pg.evaluate(JS_NA_ETIQUETA, grupo[1])
        pg.mouse.click(p[0], p[1])
        assert pg.evaluate(tgr.JS_ESCOLHIDOS) == [grupo[1]]
        # o escolhido anda tambem pela etiqueta
        _arrastar(pg, p[0], p[1], 0, 12)  # numero-neutro: px de tela
        eds = _esperar_edicoes(pg, job, gid, 1)
        assert eds[0]['elemento'] == grupo[1] and eds[0]['acao'] == 'mover', eds


# ------------------------------------------------------------------ o Tamanho do grupo com tamanhos diferentes
def test_tamanho_do_grupo_misto_e_o_numero_que_vale(job_escala, conteudo_escala):  # noqa: F811
    job, grupo = job_escala['job'], job_escala['grupo']
    copo, garrafa = grupo[1], grupo[0]
    with _tela(conteudo_escala, job, 1600, 900) as (_srv, pg, gid):  # numero-neutro: janela do teste
        x, y = tgr._ponto(pg, copo)
        pg.mouse.click(x, y)
        pg.fill('#ed-tamanho', '120')
        pg.press('#ed-tamanho', 'Enter')
        _esperar_edicoes(pg, job, gid, 1)
        tgr._shift_clique(pg, garrafa)
        # tamanhos diferentes: o campo mostra 100, o tamanho do grupo desde que ele foi escolhido, e a tela diz isso
        assert pg.evaluate('() => document.getElementById("ed-tamanho").value') == '100'
        assert 'tamanhos diferentes' in pg.evaluate(MSG)
        pg.fill('#ed-tamanho', '80')
        pg.press('#ed-tamanho', 'Enter')
        eds = _esperar_edicoes(pg, job, gid, 2)
        assert eds[1]['acao'] == 'escalar' and eds[1]['fator'] == 0.8 and sorted(eds[1]['elementos']) == \
            sorted([copo, garrafa]), eds
        assert pg.evaluate('() => document.getElementById("ed-tamanho").value') == '80'
        # o mesmo numero de novo nao grava nada: o numero e o tamanho do grupo, nunca mais uma reducao
        pg.fill('#ed-tamanho', '80')
        pg.press('#ed-tamanho', 'Enter')
        pg.wait_for_timeout(600)  # numero-neutro: ms, mais que a espera do rascunho
        assert len(tgr._edicoes(job, gid)) == 2
        assert pg.evaluate(MSG) == 'O tamanho já é este.'


# ------------------------------------------------------------------ o foco depois dos botoes e o Delete com o grupo
def test_foco_volta_ao_grupo_depois_dos_botoes_e_delete_diz_por_que(job_escala, conteudo_escala):  # noqa: F811
    job, grupo = job_escala['job'], job_escala['grupo']
    with _tela(conteudo_escala, job, 1600, 900) as (_srv, pg, gid):  # numero-neutro: janela do teste
        x, y = tgr._ponto(pg, grupo[0])
        pg.mouse.click(x, y)
        tgr._shift_clique(pg, grupo[1])
        pg.keyboard.press('Delete')
        assert pg.evaluate(MSG) == 'Para apagar, escolha um elemento só. Com vários escolhidos, nenhum é apagado.'
        assert tgr._edicoes(job, gid) == []
        pg.click('#ed-diminuir')
        _esperar_edicoes(pg, job, gid, 1)
        assert pg.evaluate(FOCO) in grupo[:2]
        pg.keyboard.press('ArrowLeft')
        eds = _esperar_edicoes(pg, job, gid, 2)
        assert eds[1]['acao'] == 'mover' and sorted(eds[1]['elementos']) == sorted(grupo[:2]), eds
        pg.click('#ed-al-esquerda')
        _esperar_edicoes(pg, job, gid, 3)
        assert pg.evaluate(FOCO) in grupo[:2]
        pg.keyboard.press('Escape')
        assert pg.evaluate(tgr.JS_ESCOLHIDOS) == []


# ------------------------------------------------------------------ a barra de edicao
JS_BARRA = """() => {
  const q = s => document.querySelector(s).getBoundingClientRect();
  const n = document.getElementById('elemento-escolhido');
  return {grupo: q('.barra-grupo').top, alinhar: q('.barra-alinhar').top, barra: q('#barra-edicao').height,
          cortado: n.scrollHeight > n.clientHeight + 1 || n.scrollWidth > n.clientWidth + 1, texto: n.textContent};
}"""


@pytest.mark.parametrize('janela', [(2048, 720), (1280, 800)], ids=['2048x720', '1280x800'])
def test_barra_em_duas_linhas_e_resumo_do_grupo_inteiro(job_escala, conteudo_escala, janela):  # noqa: F811
    job, grupo = job_escala['job'], job_escala['grupo']
    with _tela(conteudo_escala, job, *janela) as (_srv, pg, _gid):
        x, y = tgr._ponto(pg, grupo[0])
        pg.mouse.click(x, y)
        for eid in grupo[1:]:
            tgr._shift_clique(pg, eid)
        pg.evaluate('() => { document.getElementById("ed-mensagem").textContent = ""; }')
        b = pg.evaluate(JS_BARRA)
        assert not b['cortado'], b
        assert b['texto'].startswith('Escolhidos juntos: 3 elementos'), b
        if janela[0] == 2048:  # numero-neutro: a tela larga do Duda
            # os botoes do elemento e os de alinhar na mesma linha: o nome embaixo, duas linhas na barra
            assert b['grupo'] == b['alinhar'], b


# ------------------------------------------------------------------ o rascunho que nao gravou
@pytest.mark.skipif(sys.platform != 'win32', reason='so o Windows recusa trocar o arquivo aberto')
def test_rascunho_que_nao_gravou_tenta_de_novo_e_segura_a_familia(job_escala, conteudo_escala):  # noqa: F811
    import test_tela_palco as tp
    job, a = job_escala['job'], job_escala['assinatura']
    with _tela(conteudo_escala, job, 1600, 900) as (_srv, pg, gid):  # numero-neutro: janela do teste
        x, y = tgr._ponto(pg, a)
        pg.mouse.click(x, y)
        pg.click('#ed-diminuir')
        _esperar_edicoes(pg, job, gid, 1)
        leitor = open(job / tr.ARQUIVO, 'rb')  # um leitor que segura o arquivo (um antivirus, um indexador)
        try:
            pg.click('#ed-aumentar')
            tp._esperar(pg, '() => document.documentElement.dataset.rascunho === "erro" ? "ok" : ""', 'ok')
            # a ultima escolha nao esta gravada: o botao da familia fica desligado e diz por que
            assert pg.evaluate('() => document.getElementById("confirmar-familia").disabled') is True
            assert 'ainda não foi salva' in pg.evaluate('() => document.getElementById("confirmar-familia").title')
        finally:
            leitor.close()
        # o leitor soltou: a pagina tenta de novo sozinha, grava, e o botao volta
        tp._esperar(pg, SALVO, teto_s=20)  # numero-neutro: segundos, mais que as tres primeiras tentativas
        assert len(tgr._edicoes(job, gid)) == 2
        assert pg.evaluate('() => document.getElementById("confirmar-familia").disabled') is False
