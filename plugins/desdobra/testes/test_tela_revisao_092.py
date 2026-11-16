# -*- coding: utf-8 -*-
"""Revisao de design da tela 0.9.2: os defeitos achados na revisao adversarial, cada um com a prova no Chromium.

Pedido do dono do produto: o DA testou o KV A sem bloqueio e mesmo assim nao viu as Familias, e quer a tela rapida,
facil e precisa. Criterios cobertos aqui:
  - a espera das Familias acompanha o ato (os formatos escritos na tela) e, quando tudo esta feito e o motor ainda
    recusa, diz o motivo concreto e tem botao;
  - o erro do rascunho aparece em frase abaixo de 1280 px, e o selo e uma regiao viva;
  - o formato escrito na tela aparece pela medida, sem o id do motor;
  - a janela de confirmacao destaca a acao (e o remover em cor de aviso);
  - os botoes desligados do passo 5 dizem por que;
  - as etiquetas do palco nao se encavalam;
  - a camada com mascara chega a tela com a transparencia;
  - o foco do campo Tamanho aparece, a marca de chegada aparece com movimento reduzido e os alvos tem 24 px;
  - o texto do bloqueio de fase nao contradiz o botao nem a frase de baixo.
Tudo sintetico: os KV A e B de testes/sinteticos, o PSD de test_tela_palco e as fichas de test_specs_apoio.
"""
import re
import shutil
import time

import pytest

import test_tela_palco as tp
import test_tela_partida as tpa
from desdobra.tela import atos as ta
from desdobra.tela import estado as te
from desdobra.tela import rascunho as tr
from desdobra.tela import servidor as ts
from sinteticos import kv_a_b as kv


@pytest.fixture(scope='module')
def base(tmp_path_factory):
    from desdobra.chromium import navegador
    navegador.apontar_playwright()
    raiz = tmp_path_factory.mktemp('revisao-092')
    a = kv.criar_job(raiz, 'a')
    (raiz / 'novo').mkdir()
    novo, f_novo = tpa._criar(raiz / 'novo')
    (raiz / 'sem-folha').mkdir()
    sf, f_sf = tpa._criar(raiz / 'sem-folha', folhas=None)
    return {'kva': (a['job'], a['funcoes']), 'novo': (novo, f_novo), 'sem-folha': (sf, f_sf)}


@pytest.fixture
def pw():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        yield p


def _copia(base, nome, tmp_path):
    job, funcoes = base[nome]
    destino = tmp_path / nome
    shutil.copytree(job.parent, destino)
    return destino / job.name, funcoes


class _Tela:
    """O servidor da tela em modo de teste e a pagina no Chromium. rascunho_kv: as funcoes do KV sintetico com o passo
    2 e o Design system ja feitos."""

    def __init__(self, pw, job, largura=1366, altura=768, rascunho_kv=None, movimento=None):
        from desdobra.chromium import navegador
        conteudo = te.montar(job)
        self.srv = ts.ServidorTela(conteudo, pasta=job, modo_teste=True, atos=ta.atos_do_job(job, conteudo=conteudo))
        self.srv.__enter__()
        if rascunho_kv:
            fams = {gid: {'versao': None, 'confirmada': False, 'edicoes': []} for gid in conteudo['familias']}
            corpo = dict({'job_id': self.srv.job_id, 'laudo_sha256': self.srv.laudo_sha256, 'familias': fams},
                         **kv.passo_2(rascunho_kv))
            tr.gravar(job, corpo, job_id=self.srv.job_id, laudo_atual=self.srv.laudo_sha256,
                      origem=self.srv.origem_rascunho)
            self.srv.estado = conteudo['recarregar']()
        self.nav = pw.chromium.launch(headless=True, args=list(navegador.ARGUMENTOS))
        opc = {'viewport': {'width': largura, 'height': altura}, 'device_scale_factor': 1}
        if movimento:
            opc['reduced_motion'] = movimento
        self.pg = self.nav.new_context(**opc).new_page()
        try:
            self.pg.goto(self.srv.url_entrada, wait_until='commit')
        except Exception:  # noqa: BLE001 - o 204 nao completa a navegacao
            pass
        self.pg.goto(self.srv.url_pagina, wait_until='load')
        tp._esperar(self.pg, tp.JS_PRONTO)
        time.sleep(0.6)

    def __enter__(self):
        return self.pg

    def __exit__(self, *exc):
        self.nav.close()
        self.srv.__exit__(None, None, None)


def _passo(pg, passo):
    pg.evaluate('p => document.querySelector("#passos [data-passo=" + p + "]").click()', passo)
    time.sleep(0.6)


def _valor(pg, seletor, texto):
    pg.evaluate('([s, t]) => { const c = document.querySelector(s); c.value = t; '
                'c.dispatchEvent(new Event("input", {bubbles: true})); }', [seletor, texto])


def _digitar(pg, texto):
    _passo(pg, 'lido')
    _valor(pg, '#digitados-campo', texto)
    pg.evaluate('() => document.getElementById("digitados-acrescentar").click()')
    pg.wait_for_selector('#confirmacao[open]')
    pg.evaluate('() => document.querySelector("#confirmacao [data-resposta=sim]").click()')
    tp._esperar(pg, '() => document.documentElement.dataset.estadoAto === "feito" ? "1" : ""')
    time.sleep(0.8)


# ------------------------------------------------------------------ altos
def test_espera_das_familias_acompanha_os_formatos_escritos(base, pw, tmp_path):
    """D1: depois do ato dos formatos escritos, o texto da espera nas Familias deixa de dizer que o job nao tem
    formato (a lista ja dizia "Feito. 3 formatos no job")."""
    job, _f = _copia(base, 'sem-folha', tmp_path)
    with _Tela(pw, job) as pg:
        _digitar(pg, '640x320, 300x600, 1080x1920')
        _passo(pg, 'pecas')
        texto = pg.evaluate('() => document.getElementById("espera-texto").textContent')
        lista = pg.evaluate('() => document.getElementById("espera-checklist").innerText')
    assert 'Feito. 3 formatos no job' in lista
    assert texto != te.SEM_FORMATOS and 'nenhum formato' not in texto, texto


def test_espera_diz_o_motivo_e_tem_botao_quando_o_motor_recusa(base, pw, tmp_path):
    """D2, o caso do KV A: tudo feito na lista e o motor ainda recusa (aqui, todas as camadas fora da peca). O texto diz
    o motivo concreto, e o botao leva ao lugar dele."""
    job, funcoes = _copia(base, 'novo', tmp_path)
    with _Tela(pw, job) as pg:
        _passo(pg, 'funcoes')
        for lid in funcoes:
            pg.evaluate('s => document.querySelector(s).click()', '#arvore button[data-camada="%d"]' % lid)
            time.sleep(0.15)
            pg.evaluate('s => document.querySelector(s).click()', '#detalhe button[data-funcao="fora_da_peca"]')
            time.sleep(0.25)
        time.sleep(2.5)
        _passo(pg, 'pecas')
        time.sleep(1.0)
        visivel = pg.evaluate('() => !document.getElementById("espera-familias").hidden')
        texto = pg.evaluate('() => document.getElementById("espera-texto").textContent')
        faltando = pg.evaluate('() => document.querySelectorAll("#espera-checklist .espera-item.falta").length')
        botao = pg.evaluate('() => { const b = document.getElementById("espera-ir"); '
                            'return !b.hidden && b.getClientRects().length > 0 ? b.textContent : ""; }')
    assert visivel
    assert botao, 'a espera ficou sem botao'
    assert faltando > 0 or texto != te.AGUARDA_CONFERENCIA, texto
    if not faltando:
        assert te.MOTIVOS_DA_CONFERENCIA['mestre_sem_elemento'] in texto, texto
        assert botao == 'Ir para Funções'


def test_motivo_da_conferencia_sem_comando_nem_codigo():
    for codigo, texto in te.MOTIVOS_DA_CONFERENCIA.items():
        assert codigo not in texto and chr(0x2014) not in texto and chr(0x2013) not in texto
    assert te.motivo_da_conferencia([{'codigo': 'desconhecido'}], {'camadas': []}) is None


def test_erro_do_rascunho_aparece_em_frase_abaixo_de_1280(base, pw, tmp_path):
    """D3: a 1024 px, o rascunho que nao grava aparece em frase legivel, e o selo e uma regiao viva."""
    job, _f = _copia(base, 'kva', tmp_path)
    with _Tela(pw, job, 1024, 768) as pg:
        assert pg.evaluate('() => document.getElementById("selo").getAttribute("role")') == 'status'
        pg.route(re.compile(r'.*/api/rascunho.*'), lambda r: r.fulfill(status=500, body='{}')
                 if r.request.method != 'GET' else r.continue_())
        _passo(pg, 'funcoes')
        pg.evaluate('() => document.querySelector("#arvore button").click()')
        time.sleep(0.2)
        pg.evaluate('() => document.querySelector("#detalhe button[data-funcao=imagem]").click()')
        tp._esperar(pg, '() => document.getElementById("selo").dataset.estado === "erro" ? "1" : ""', teto_s=15)
        visto = pg.evaluate('''() => { const n = document.getElementById("selo"), s = getComputedStyle(n),
            r = n.getBoundingClientRect();
            return n.textContent.includes("Não foi possível salvar") && parseFloat(s.fontSize) >= 12 && r.width > 80 &&
                   r.height > 10 && s.visibility !== "hidden"; }''')
    assert visto


# ------------------------------------------------------------------ medios
def test_formato_escrito_aparece_pela_medida_sem_id_do_motor(base, pw, tmp_path):
    """D4: em Formatos e giro e no que falta, o formato escrito na tela aparece pela medida."""
    job, _f = _copia(base, 'sem-folha', tmp_path)
    with _Tela(pw, job) as pg:
        _digitar(pg, '1080x1920')
        texto = pg.evaluate('() => document.getElementById("lido-formatos").innerText')
    assert 'digitado-' not in texto and '1080x1920' in texto.replace(' ', ''), texto
    e = te.montar(job)['estado']
    giro = [i for i in e['faltam'] if i['texto'] == te.GIRO_SEM_ESCOLHA]
    assert giro and 'digitado-' not in giro[0]['detalhe'] and '1080 x 1920' in giro[0]['detalhe']


def test_janela_de_confirmacao_destaca_a_acao_e_o_remover(base, pw, tmp_path):
    """D5: Confirmar e a acao primaria da janela; o remover usa a cor de aviso."""
    job, _f = _copia(base, 'sem-folha', tmp_path)
    estilo = '''r => { const s = getComputedStyle(document.querySelector("#confirmacao [data-resposta=" + r + "]"));
        return s.backgroundColor + "|" + s.color + "|" + s.fontWeight; }'''
    with _Tela(pw, job) as pg:
        _valor(pg, '#digitados-campo', '640x320')
        pg.evaluate('() => document.getElementById("digitados-acrescentar").click()')
        pg.wait_for_selector('#confirmacao[open]')
        sim, nao = pg.evaluate(estilo, 'sim'), pg.evaluate(estilo, 'nao')
        pg.evaluate('() => document.querySelector("#confirmacao [data-resposta=sim]").click()')
        tp._esperar(pg, '() => document.documentElement.dataset.estadoAto === "feito" ? "1" : ""')
        pg.evaluate('() => document.querySelector("#digitados-lista button[aria-label^=\'Remover\']").click()')
        pg.wait_for_selector('#confirmacao[open]')
        remover = pg.evaluate(estilo, 'sim')
    assert sim != nao, (sim, nao)
    assert remover != sim, (remover, sim)


def test_botoes_desligados_do_passo_5_dizem_por_que(base, pw, tmp_path):
    """D6: Renderizar os afetados, Aprovar e as caixas de marcar desligados levam o motivo."""
    job, _f = _copia(base, 'kva', tmp_path)
    with _Tela(pw, job) as pg:
        _passo(pg, 'formatos')
        sem_motivo = pg.evaluate('''() => ["renderizar-afetados", "aprovar-marcados"].filter(id => {
            const b = document.getElementById(id);
            return b.disabled && !b.hidden && b.getClientRects().length && !b.title; })''')
        caixas = pg.evaluate('''() => Array.from(document.querySelectorAll("#lista-formatos input.linha-marca"))
            .filter(c => c.disabled && !c.title).length''')
    assert sem_motivo == [] and caixas == 0, (sem_motivo, caixas)


def test_etiquetas_do_palco_nao_se_encavalam(base, pw, tmp_path):
    """D7: nas Familias do KV A, as etiquetas visiveis do palco nao se cobrem."""
    job, funcoes = _copia(base, 'kva', tmp_path)
    with _Tela(pw, job, rascunho_kv=funcoes) as pg:
        _passo(pg, 'pecas')
        tp._esperar(pg, '() => document.getElementById("palco").dataset.pronto || ""', teto_s=20)
        time.sleep(0.8)
        pares = pg.evaluate('''() => { const e = Array.from(document.querySelectorAll("#palco .etiqueta"))
            .filter(n => n.getClientRects().length && getComputedStyle(n).visibility !== "hidden");
          const out = [];
          for (let i = 0; i < e.length; i++) for (let j = i + 1; j < e.length; j++) {
            const a = e[i].getBoundingClientRect(), b = e[j].getBoundingClientRect();
            const w = Math.min(a.right, b.right) - Math.max(a.left, b.left);
            const h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
            if (w > 4 && h > 4) out.push([e[i].textContent, e[j].textContent]); }
          return [out, e.length]; }''')
    assert pares[1] > 0 and pares[0] == [], pares


def test_camada_com_mascara_chega_transparente(base, pw, tmp_path):
    """D8: a camada cujo alfa esta na mascara (o circulo do KV A) chega a tela com o canto transparente."""
    job, funcoes = _copia(base, 'kva', tmp_path)
    with _Tela(pw, job, rascunho_kv=funcoes) as pg:
        _passo(pg, 'funcoes')
        time.sleep(1.0)
        cantos = pg.evaluate('''() => Array.from(document.querySelectorAll("#palco-kv img.peca"))
          .filter(i => i.naturalWidth).map(i => { const c = document.createElement("canvas");
            c.width = i.naturalWidth; c.height = i.naturalHeight; const x = c.getContext("2d"); x.drawImage(i, 0, 0);
            return [i.naturalWidth, i.naturalHeight, Array.from(x.getImageData(0, 0, 1, 1).data)]; })''')
    redondo = [c for c in cantos if c[0] == c[1] == 128]
    assert redondo and all(c[2][3] == 0 for c in redondo), cantos


# ------------------------------------------------------------------ baixos
def test_campo_tamanho_com_foco_visivel(base, pw, tmp_path):
    """D9: pelo Tab, o campo Tamanho mostra o anel de foco."""
    job, funcoes = _copia(base, 'kva', tmp_path)
    with _Tela(pw, job, rascunho_kv=funcoes) as pg:
        _passo(pg, 'pecas')
        tp._esperar(pg, '() => document.getElementById("palco").dataset.pronto || ""', teto_s=20)
        pg.query_selector('#palco .peca').click(force=True)
        pg.focus('#ed-tamanho')
        pg.keyboard.press('Shift+Tab')
        pg.keyboard.press('Tab')
        anel = pg.evaluate('''() => { const s = getComputedStyle(document.activeElement);
            return [document.activeElement.id, s.outlineStyle, s.boxShadow]; }''')
    assert anel[0] == 'ed-tamanho' and (anel[1] != 'none' or anel[2] != 'none'), anel


def test_movimento_reduzido_ainda_marca_onde_chegou(base, pw, tmp_path):
    """D10: com prefers-reduced-motion, o Ir ate la marca o bloco de destino sem animacao."""
    job, funcoes = _copia(base, 'kva', tmp_path)
    with _Tela(pw, job, rascunho_kv=None, movimento='reduce') as pg:
        _passo(pg, 'funcoes')
        pg.evaluate('() => document.getElementById("dica-ir").click()')
        time.sleep(0.3)
        marca = pg.evaluate('''() => { const n = document.querySelector(".chegou-aqui");
            if (!n) return null; const s = getComputedStyle(n); return [n.id, s.boxShadow, s.outlineStyle]; }''')
    assert marca is not None and (marca[1] != 'none' or marca[2] != 'none'), marca


def test_alvos_de_clique_com_24px(base, pw, tmp_path):
    """D11: os resumos de Como configurar e as caixas de marcar do passo 5 tem pelo menos 24 px."""
    job, _f = _copia(base, 'kva', tmp_path)
    with _Tela(pw, job) as pg:
        _passo(pg, 'lido')
        pequenos = pg.evaluate('''() => Array.from(document.querySelectorAll("#lido-marca summary"))
            .filter(n => n.getClientRects().length && n.getBoundingClientRect().height < 24).length''')
        _passo(pg, 'formatos')
        pequenos += pg.evaluate('''() => Array.from(document.querySelectorAll("#lista-formatos input.linha-marca"))
            .filter(n => n.getBoundingClientRect().height < 24).length''')
    assert pequenos == 0


# ------------------------------------------------------------------ revisao de regressao e textos
@pytest.mark.parametrize('fase', ['ler', 'ds', 'specs', 'laudo-fontes'])
def test_bloqueio_de_fase_nao_contradiz_a_tela(fase):
    """D1 da revisao de regressao: o texto do bloqueio nunca diz que a tela ainda nao traz o caminho. A fase das specs
    e a do laudo das fontes levam ao lugar da tela; as outras dizem que se resolvem com o Claude, como a frase de
    baixo."""
    texto = te.bloqueio_na_tela(fase, {})['texto']
    assert 'próxima versão' not in texto
    if fase == 'specs':
        assert 'Valores de spec' in texto
    elif fase == 'laudo-fontes':
        assert 'Fontes do job' in texto
    else:
        assert 'Claude' in texto


def test_faixa_abas_e_busca_da_arvore(base, pw, tmp_path):
    """D2 da revisao de regressao (melhorias sem teste): a faixa do passo 1 leva ao campo dos formatos no job sem folha,
    as abas dizem o que falta, e a busca e o filtro "So as sem funcao" da arvore do passo 2 escondem e mostram camadas."""
    job, funcoes = _copia(base, 'sem-folha', tmp_path)
    with _Tela(pw, job) as pg:
        faixa = pg.evaluate('() => { const f = document.getElementById("faixa-lido"); '
                            'return f.hidden ? "" : f.innerText; }')
        assert 'Escrever os formatos' in faixa
        pg.evaluate('''() => Array.from(document.querySelectorAll("#faixa-lido button"))
            .find(b => b.textContent === "Escrever os formatos").click()''')
        time.sleep(0.6)
        assert pg.evaluate('() => document.activeElement && document.activeElement.id') == 'digitados-campo'
        assert pg.evaluate('() => document.querySelector("#passos [data-passo=funcoes]").dataset.estado') == 'falta'
        _passo(pg, 'funcoes')
        visiveis = ('() => Array.from(document.querySelectorAll("#arvore button[data-camada]"))'
                    '.filter(b => b.offsetParent).length')
        todas = pg.evaluate(visiveis)
        _valor(pg, '#arvore-busca', 'nenhuma-camada-com-este-nome')
        time.sleep(0.2)
        assert pg.evaluate(visiveis) == 0
        _valor(pg, '#arvore-busca', '')
        time.sleep(0.2)
        assert pg.evaluate(visiveis) == todas
        lid = next(iter(funcoes))
        pg.evaluate('s => document.querySelector(s).click()', '#arvore button[data-camada="%d"]' % lid)
        time.sleep(0.15)
        pg.evaluate('s => document.querySelector(s).click()', '#detalhe button[data-funcao="%s"]' % funcoes[lid])
        time.sleep(0.3)
        pg.evaluate('() => document.getElementById("arvore-so-falta").click()')
        time.sleep(0.2)
        assert pg.evaluate('() => document.getElementById("arvore-so-falta").getAttribute("aria-pressed")') == 'true'
        assert 0 < pg.evaluate(visiveis) < todas
