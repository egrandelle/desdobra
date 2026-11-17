# -*- coding: utf-8 -*-
"""Revisao da tela 0.9.3: o relato do KV A na 0.9.2, cada defeito com a prova no Chromium ou nas rotas.

Relato do Duda: com as funcoes e o Design system feitos, "Salvar e seguir" nao dava retorno, o selo dizia que a tela
nao conseguiu registrar a acao, e as Familias mostravam a lista toda feita com o botao "Ir para Funções".
Criterios cobertos aqui:
  - o Design system escolhido depois das funcoes faz a pagina pedir o estado de novo: as familias aparecem, ou o motivo
    concreto do servidor;
  - a lista da espera, o "Faltam" e a frase ao lado de "Salvar e seguir" seguem o servidor: nunca a lista toda feita
    junto com a espera, nunca "Tudo confirmado. Pode salvar." sem familia;
  - todo codigo da conferencia do motor tem motivo para o DA, com o passo onde ele se resolve;
  - a recusa do ato e a falha do rascunho aparecem no rodape, perto do botao, com o motivo que o servidor deu, e o
    botao mostra que esta trabalhando;
  - o servidor devolve o motivo da recusa do "Salvar e seguir" em portugues, sem codigo nem caminho.
Tudo sintetico: o job de testes/sinteticos/kv_relato e o KV A de testes/sinteticos/kv_a_b.
"""
import json
import re
import shutil
import time

import pytest

import test_tela_escrita as tte
import test_tela_palco as tp
import test_tela_partida as tpa
import test_tela_revisao_092 as rv
import test_tela_servidor as tts
from desdobra.briefing import modelo as mb
from desdobra.tela import estado as te
from desdobra.tela import rascunho as tr
from sinteticos import kv_a_b as kv
from sinteticos import kv_relato as kr

DICA_PRONTA = 'Tudo confirmado. Pode salvar.'
PAGINA = '''() => {
  const t = id => (document.getElementById(id) || {}).textContent || "";
  const vis = id => { const n = document.getElementById(id); return !!n && !n.hidden && n.getClientRects().length > 0; };
  return {
    selo: t("selo"), rascunho: document.documentElement.dataset.rascunho,
    salvar: { texto: t("salvar-seguir"), desligado: document.getElementById("salvar-seguir").disabled,
              dica: t("dica-acoes") },
    aviso: vis("aviso-acoes") ? t("aviso-acoes") : "",
    espera: { visivel: vis("espera-familias"), texto: t("espera-texto"),
              feitos: document.querySelectorAll("#espera-checklist .espera-item.feito").length,
              faltando: Array.from(document.querySelectorAll("#espera-checklist .espera-item.falta")).map(n => n.innerText),
              botao: vis("espera-ir") ? t("espera-ir") : null },
    familias: document.querySelectorAll("#orientacoes [role=tab]").length,
    faltam: t("faltam")
  };
}'''


@pytest.fixture(scope='module')
def base(tmp_path_factory):
    from desdobra.chromium import navegador
    navegador.apontar_playwright()
    raiz = tmp_path_factory.mktemp('revisao-093')
    (raiz / 'relato').mkdir()
    job, ids, _laudo = kr.criar(raiz / 'relato')
    _antes(job)
    a = kv.criar_job(raiz, 'a')
    _antes(a['job'])
    return {'relato': (job, ids), 'kva': (a['job'], a['funcoes'])}


@pytest.fixture
def pw():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        yield p


def _copia(base, nome, tmp_path):
    job, extra = base[nome]
    destino = tmp_path / nome
    shutil.copytree(job.parent, destino)
    return destino / job.name, extra


def _antes(job):
    """O modo de dados e os valores de spec pelas rotas da tela, num servidor que fecha antes de a pagina abrir."""
    _conteudo, s = tpa._servidor(job)
    try:
        b = tts._entrar(s)
        assert tpa._ato(s, b, 'modo_dados', {'modo': 'c'}) == (200, 200)
        for _ in range(50):
            pend = [x for x in te.specs_pendentes(job) if not x['leituras']]
            if not pend:
                break
            assert tpa._ato(s, b, 'spec_valor', {'valor_id': pend[0]['valor_id']}) == (200, 200)
    finally:
        s.parar()


def _clicar(pg, seletor):
    assert pg.evaluate('s => { const b = document.querySelector(s); if (!b) return false; b.click(); return true; }',
                       seletor), seletor


def _escolhas_do_relato(pg, ids, design):
    """As escolhas do Duda por cliques: a prancheta e o giro (passo 1), a funcao de cada camada (passo 2) e, depois, a
    regra e a ancora de cada funcao (Design system). Nenhuma funcao muda depois do Design system."""
    rv._passo(pg, 'lido')
    _clicar(pg, '[data-quadro=q1]')
    time.sleep(0.6)
    for g in pg.evaluate('() => Array.from(document.querySelectorAll("button[data-giro]")).map(b => b.dataset.giro)'
                         '.filter(g => g.endsWith("|0|"))'):
        pg.evaluate('g => Array.from(document.querySelectorAll("button[data-giro]")).find(b => b.dataset.giro === g)'
                    '.click()', g)
        time.sleep(0.2)
    rv._passo(pg, 'funcoes')
    for papel, f in kr.FUNCOES.items():
        if papel not in ids:
            continue
        _clicar(pg, '#arvore button[data-camada="%d"]' % ids[papel])
        time.sleep(0.15)
        _clicar(pg, '#detalhe button[data-funcao="%s"]' % f)
        time.sleep(0.2)
    rv._passo(pg, 'design')
    for f, (r, x, y) in design.items():
        art = "article[data-chave='f%s']" % f
        _clicar(pg, art + ' .funcao-ds-topo')
        time.sleep(0.15)
        _clicar(pg, art + " button[data-regra='%s']" % r)
        time.sleep(0.15)
        _clicar(pg, art + " button[data-x='%s'][data-y='%s']" % (x, y))
        time.sleep(0.15)


def _esperar_gravado(pg):
    tp._esperar(pg, '() => document.documentElement.dataset.rascunho === "salvo" ? "1" : ""', teto_s=30)
    time.sleep(1.5)


def _confirmar_dialogo(pg):
    pg.wait_for_selector('#confirmacao[open]', timeout=60000)
    pg.evaluate('() => document.querySelector("#confirmacao [data-resposta=sim]").click()')


def _confirmar_familias(pg, teto=8):
    """Cada familia que falta pelo "Ir até lá" do rodape, com o "Confirmar família" e a janela."""
    for _ in range(teto):
        if not pg.evaluate('() => document.getElementById("salvar-seguir").disabled'):
            return
        if pg.evaluate('() => !document.getElementById("dica-ir").hidden'):
            _clicar(pg, '#dica-ir')
            time.sleep(0.5)
        # a familia com versoes do desdobra pede a escolha de uma antes da confirmacao
        if pg.evaluate('() => !document.getElementById("galeria").hidden && '
                       '!document.querySelector("#variantes .variante[aria-selected=true]")'):
            _clicar(pg, '#variantes .variante')
            time.sleep(0.5)
        tp._esperar(pg, '() => document.getElementById("confirmar-familia").disabled ? "" : "1"', teto_s=60)
        _clicar(pg, '#confirmar-familia')
        _confirmar_dialogo(pg)
        tp._esperar(pg, '() => document.documentElement.dataset.estadoAto === "feito" ? "1" : ""', teto_s=60)
        time.sleep(0.6)
    assert not pg.evaluate('() => document.getElementById("salvar-seguir").disabled'), pg.evaluate(PAGINA)


def _legivel_perto_do_salvar(pg):
    """O aviso do rodape: visivel na janela, em letra de 12 px ou mais, sem corte, e na mesma faixa do botao."""
    return pg.evaluate('''() => { const n = document.getElementById("aviso-acoes"), b = document.getElementById("salvar-seguir");
      if (!n || n.hidden) return "escondido";
      const s = getComputedStyle(n), r = n.getBoundingClientRect(), rb = b.getBoundingClientRect();
      if (parseFloat(s.fontSize) < 12) return "letra " + s.fontSize;
      if (r.width < 120 || r.height < 12) return "pequeno " + r.width + "x" + r.height;
      if (r.left < 0 || r.right > innerWidth + 1 || r.top < 0 || r.bottom > innerHeight + 1) return "fora da janela";
      if (n.scrollWidth > n.clientWidth + 2) return "cortado";
      if (s.visibility === "hidden" || s.display === "none" || parseFloat(s.opacity) < 0.5) return "invisivel";
      if (Math.abs((r.top + r.bottom) / 2 - (rb.top + rb.bottom) / 2) > 90) return "longe do botao";
      return "ok"; }''')


# ------------------------------------------------------------------ causa 1: o Design system pede o estado de novo
def test_design_depois_das_funcoes_faz_as_familias_aparecerem(base, pw, tmp_path):
    """O cenario do Duda com a mesma regra no bloco: funcoes primeiro, Design system depois, nenhuma escolha a mais.
    As familias aparecem sem recarregar a pagina, e "Salvar e seguir" diz que falta confirmar as familias, com o "Ir
    até lá" que abre a primeira delas."""
    job, ids = _copia(base, 'relato', tmp_path)
    with rv._Tela(pw, job, 1600, 900) as pg:
        _escolhas_do_relato(pg, ids, kr.DESIGN_MESMA_REGRA)
        _esperar_gravado(pg)
        rv._passo(pg, 'pecas')
        tp._esperar(pg, '() => document.querySelectorAll("#orientacoes [role=tab]").length ? "1" : ""', teto_s=40)
        p = pg.evaluate(PAGINA)
        rv._passo(pg, 'design')
        _clicar(pg, '#dica-ir')
        time.sleep(0.8)
        abriu = pg.evaluate('() => !document.getElementById("passo-pecas").hidden && '
                            '!!document.querySelector("#composicoes [aria-selected=true]")')
    assert not p['espera']['visivel'] and p['familias'] >= 1, p
    assert p['salvar']['desligado'] and re.search(r'Falta confirmar \d+ famílias? para salvar', p['salvar']['dica']), p
    assert p['salvar']['dica'] != DICA_PRONTA, p
    assert abriu


def test_salvar_e_seguir_com_as_familias_confirmadas_salva_com_retorno_visivel(base, pw, tmp_path):
    """Com as familias confirmadas, "Salvar e seguir" mostra que confere, abre a janela e, confirmado, o rodape diz que
    o briefing esta salvo."""
    job, funcoes = _copia(base, 'kva', tmp_path)
    with rv._Tela(pw, job, 1600, 900, rascunho_kv=funcoes) as pg:
        rv._passo(pg, 'pecas')
        _confirmar_familias(pg)
        assert pg.evaluate(PAGINA)['salvar']['dica'] == DICA_PRONTA
        _clicar(pg, '#salvar-seguir')
        _confirmar_dialogo(pg)
        tp._esperar(pg, '() => document.getElementById("salvo").hidden ? "" : "1"', teto_s=180)
        p = pg.evaluate(PAGINA)
        salvo = pg.evaluate('() => document.getElementById("salvo").textContent')
    assert p['salvar']['texto'] == 'Briefing salvo' and p['aviso'] == '', p
    assert 'O briefing está salvo' in salvo
    assert (job / mb.ARQUIVO).exists()


def test_relato_mostra_o_motivo_do_bloco_em_todo_lugar(base, pw, tmp_path):
    """O relato como foi: Grafismo pela altura e Fundo pela area num bloco. A espera diz o motivo concreto com o nome
    das camadas, a lista marca o que falta, o botao leva ao Design system, o "Faltam" conta o motivo e "Salvar e
    seguir" fica desligado com o motivo ao lado."""
    job, ids = _copia(base, 'relato', tmp_path)
    motivo = te.MOTIVOS_DA_CONFERENCIA['bloco_com_regras_diferentes'].split('{camadas}')[1][:30]
    with rv._Tela(pw, job, 1600, 900) as pg:
        _escolhas_do_relato(pg, ids, kr.DESIGN)
        _esperar_gravado(pg)
        rv._passo(pg, 'pecas')
        tp._esperar(pg, '() => document.getElementById("espera-texto").textContent.includes(%s) ? "1" : ""'
                    % json.dumps(motivo), teto_s=30)
        p = pg.evaluate(PAGINA)
        titulo_da_dica = pg.evaluate('() => document.getElementById("dica-acoes").title')
        rv._passo(pg, 'design')
        no_design = pg.evaluate('() => { const n = document.getElementById("aviso-design"); '
                                'return n && !n.hidden ? n.textContent : ""; }')
        rv._passo(pg, 'pecas')
        _clicar(pg, '#espera-ir')
        time.sleep(0.5)
        foi = pg.evaluate('() => !document.getElementById("passo-design").hidden')
    assert p['espera']['visivel'] and kr.NOMES['retangulo'] in p['espera']['texto'], p
    assert kr.NOMES['grafismo'] in p['espera']['texto'], p
    assert p['espera']['faltando'], 'a lista ficou toda feita junto com a espera: %r' % p
    assert p['espera']['botao'] == 'Ir para o Design system', p
    assert p['faltam'] != 'Faltam 0', p
    # ao lado do botao, o nome curto do motivo (cabe no rodape); a frase inteira no title
    assert p['salvar']['desligado'] and p['salvar']['dica'] != DICA_PRONTA, p
    assert te.CURTO_DO_MOTIVO['bloco_com_regras_diferentes'] in p['salvar']['dica'], p
    assert motivo in titulo_da_dica, titulo_da_dica
    assert motivo in no_design
    assert foi


# ------------------------------------------------------------------ causa 2 e o pedido C: a recusa e a falha no rodape
@pytest.mark.parametrize('largura,altura', [(1600, 900), (1024, 768)])
def test_recusa_do_salvar_aparece_no_rodape_e_o_botao_mostra_que_trabalha(base, pw, tmp_path, largura, altura):
    """O servidor recusa o "Salvar e seguir" com um motivo: o motivo aparece no rodape, legivel, ao lado do botao; o
    botao diz que esta conferindo enquanto espera e volta depois. O selo nunca manda tentar de novo."""
    job, funcoes = _copia(base, 'kva', tmp_path)
    presos = []
    with rv._Tela(pw, job, largura, altura, rascunho_kv=funcoes) as pg:
        rv._passo(pg, 'pecas')
        _confirmar_familias(pg)
        motivo = 'Falta confirmar 1 família para salvar.'
        pg.route(re.compile(r'.*/api/ato/pedir$'), lambda r: presos.append(r))
        _clicar(pg, '#salvar-seguir')
        tp._esperar(pg, '() => document.getElementById("salvar-seguir").getAttribute("aria-busy") === "true" ? "1" : ""',
                    teto_s=10)
        trabalhando = pg.evaluate('() => [document.getElementById("salvar-seguir").textContent, '
                                  'document.getElementById("salvar-seguir").disabled]')
        for _ in range(100):
            if presos:
                break
            time.sleep(0.05)
        presos[0].fulfill(status=403, content_type='application/json; charset=utf-8',
                          body=json.dumps({'motivo': motivo}, ensure_ascii=False))
        tp._esperar(pg, '() => document.getElementById("salvar-seguir").getAttribute("aria-busy") === "true" ? "" : "1"',
                    teto_s=10)
        time.sleep(0.3)
        p = pg.evaluate(PAGINA)
        legivel = _legivel_perto_do_salvar(pg)
    assert trabalhando == ['Conferindo', True], trabalhando
    assert motivo in p['aviso'], p
    assert legivel == 'ok', legivel
    assert 'Tente de novo' not in p['selo'] and p['salvar']['texto'] == 'Salvar e seguir', p


@pytest.mark.parametrize('largura,altura', [(1600, 900), (1024, 768)])
def test_falha_de_gravar_aparece_no_rodape(base, pw, tmp_path, largura, altura):
    """O rascunho que nao grava: o rodape diz que a escolha nao foi salva, com o motivo do servidor quando ele vem, e
    o aviso sai quando a gravacao volta."""
    job, funcoes = _copia(base, 'kva', tmp_path)
    estado = {'falhar': True, 'motivo': None}

    def rota(r):
        if r.request.method == 'GET' or not estado['falhar']:
            return r.continue_()
        if estado['motivo']:
            return r.fulfill(status=403, content_type='application/json; charset=utf-8',
                             body=json.dumps({'motivo': estado['motivo']}, ensure_ascii=False))
        return r.fulfill(status=500, body='')
    with rv._Tela(pw, job, largura, altura, rascunho_kv=funcoes) as pg:
        pg.route(re.compile(r'.*/api/rascunho$'), rota)
        rv._passo(pg, 'funcoes')
        _clicar(pg, '#arvore button[data-camada]')
        time.sleep(0.2)
        _clicar(pg, '#detalhe button[data-funcao=imagem]')
        tp._esperar(pg, '() => document.documentElement.dataset.rascunho === "erro" ? "1" : ""', teto_s=15)
        time.sleep(0.2)
        sem_motivo = pg.evaluate(PAGINA)['aviso']
        legivel = _legivel_perto_do_salvar(pg)
        estado['motivo'] = 'O PSD foi lido de novo com a tela aberta.'
        _clicar(pg, '#detalhe button[data-funcao=grafismo]')
        for _ in range(100):
            if estado['motivo'] in pg.evaluate(PAGINA)['aviso']:
                break
            time.sleep(0.1)
        com_motivo = pg.evaluate(PAGINA)['aviso']
        estado['falhar'] = False
        _clicar(pg, '#detalhe button[data-funcao=imagem]')
        tp._esperar(pg, '() => document.documentElement.dataset.rascunho === "salvo" ? "1" : ""', teto_s=15)
        depois = pg.evaluate(PAGINA)['aviso']
    assert 'não foi salva' in sem_motivo, sem_motivo
    assert legivel == 'ok', legivel
    assert estado['motivo'] in com_motivo, com_motivo
    assert depois == '', depois


# ------------------------------------------------------------------ o servidor: o motivo da recusa e do estado
def _rascunho_do_relato(job, s, ids, design):
    corpo = {'job_id': s.job_id, 'laudo_sha256': s.laudo_sha256, 'familias': {}, 'quadro': 'q1'}
    corpo.update(kr.passo_2(ids, design))
    e = te.montar(job)['estado']
    corpo['rotacoes'] = {f['chave']: tpa.ROT0 for f in e['lido']['specs']['formatos']}
    tr.gravar(job, corpo, job_id=s.job_id, laudo_atual=s.laudo_sha256, origem=s.origem_rascunho)


def _motivo_da_recusa(corpo):
    d = json.loads(corpo.decode('utf-8'))
    assert set(d) == {'motivo'}, d
    m = d['motivo']
    assert m and '\\' not in m and '/' not in m and '_' not in m, m
    assert chr(0x2014) not in m and chr(0x2013) not in m and 'Tente de novo' not in m, m
    return m


@pytest.mark.parametrize('design,trecho', [
    (kr.DESIGN, 'andam juntas num bloco'),
    (kr.DESIGN_MESMA_REGRA, 'Falta confirmar 3 famílias'),
])
def test_salvar_recusado_devolve_o_motivo_em_portugues(base, tmp_path, design, trecho):
    job, ids = _copia(base, 'relato', tmp_path)
    _conteudo, s = tpa._servidor(job)
    try:
        b = tts._entrar(s)
        _rascunho_do_relato(job, s, ids, design)
        e = tpa._estado(s, b)
        codigo, _cab, corpo = tte._escrever(s, '/api/ato/pedir', {'ato': 'salvar', 'dados': {'rascunho': tpa._vista(job)}},
                                            cookie=b)[:3]
        # a recusa de seguranca continua sem corpo
        sem_csrf = tte._escrever(s, '/api/ato/pedir', {'ato': 'salvar', 'dados': {}}, cookie=b, csrf=False)
    finally:
        s.parar()
    assert codigo == 403, (codigo, corpo)
    assert trecho in _motivo_da_recusa(corpo)
    assert sem_csrf[0] == 403 and sem_csrf[2] == b''
    if design is kr.DESIGN:
        m = e['passo_3']['motivo']
        assert e['passo_3']['aguarda_passo_2'] and e['passo_3']['ir'] == 'design' and m['passo'] == 'design', e['passo_3']
        assert m['codigo'] == 'bloco_com_regras_diferentes' and set(m['funcoes']) == {'fundo', 'grafismo'}, m
        assert kr.NOMES['retangulo'] in m['texto'] and kr.NOMES['grafismo'] in m['texto'], m


# ------------------------------------------------------------------ todo codigo da conferencia tem motivo
def _codigos_da_conferencia():
    from desdobra.briefing import modelo
    import inspect
    fonte = inspect.getsource(modelo)
    return set(mb.DESCRICOES) | set(re.findall(r"_erro\('([a-z_]+)'", fonte))


def test_todo_codigo_da_conferencia_tem_motivo_e_destino():
    codigos = _codigos_da_conferencia()
    assert len(codigos) >= 28
    sem = sorted(c for c in codigos if c not in te.MOTIVOS_DA_CONFERENCIA)
    assert sem == [], 'codigos da conferencia sem motivo para o DA: %s' % sem
    laudo = {'camadas': [{'identidade': {'layer_id': 7}, 'nome': 'camada-sete'}]}
    for c in sorted(codigos):
        # None: o motivo que a tela nao resolve (a regra de bloco), e a frase diz que o Claude ajuda
        assert te.DESTINO_DO_MOTIVO[c] in ('lido', 'funcoes', 'design', 'pecas', None), c
        assert te.CURTO_DO_MOTIVO[c], c
        m = te.motivo_da_conferencia([{'codigo': c, 'medidas': {'layer_id': 7, 'funcao': 'titulo'}}], laudo)
        assert m is not None and m['passo'] == te.DESTINO_DO_MOTIVO[c], c
        for texto in (m['texto'], m['curto']):
            assert c not in texto and '{' not in texto and chr(0x2014) not in texto and chr(0x2013) not in texto, c
            assert not re.search(r'\bdigit', texto, re.I) and 'Tente de novo' not in texto, c
            assert not re.search(r'\bnão é [^.;:]{1,60}, é\b', texto, re.I), c
        if '{camadas}' in te.MOTIVOS_DA_CONFERENCIA[c]:
            assert 'camada-sete' in m['texto'], c


def test_codigo_desconhecido_fica_sem_motivo():
    assert te.motivo_da_conferencia([{'codigo': 'codigo_que_nao_existe'}], {'camadas': []}) is None


# ================================================================== ajuste depois das revisoes adversariais da 0.9.3
MOTIVO_DE_TESTE = 'O PSD foi lido de novo com esta janela aberta.'
FOCO = '() => (document.activeElement || {}).id || document.activeElement.tagName'


def _recusar_rascunho(r, motivo=MOTIVO_DE_TESTE):
    return r.fulfill(status=403, content_type='application/json; charset=utf-8',
                     body=json.dumps({'motivo': motivo}, ensure_ascii=False))


def _recusar_salvar(pg, motivo, teclado=False):
    """O "Salvar e seguir" recusado pelo servidor com um motivo; devolve o foco durante a conferencia."""
    presos = []
    pg.route(re.compile(r'.*/api/ato/pedir$'), lambda r: presos.append(r))
    if teclado:
        pg.focus('#salvar-seguir')
        pg.keyboard.press('Enter')
    else:
        _clicar(pg, '#salvar-seguir')
    for _ in range(200):
        if presos:
            break
        time.sleep(0.05)
    durante = pg.evaluate(FOCO)
    presos[0].fulfill(status=403, content_type='application/json; charset=utf-8',
                      body=json.dumps({'motivo': motivo}, ensure_ascii=False))
    tp._esperar(pg, '() => document.getElementById("salvar-seguir").getAttribute("aria-busy") === "true" ? "" : "1"',
                teto_s=10)
    time.sleep(0.3)
    pg.unroute(re.compile(r'.*/api/ato/pedir$'))
    return durante


# ------------------------------------------------------------------ D1: o rascunho recusado nunca vira "Salvando"
def test_rascunho_recusado_com_motivo_mostra_a_falha_e_nao_salvando(base, pw, tmp_path):
    """Revisao adversarial (corretude D1, regressao 1): a gravacao recusada com motivo para de tentar sozinha. O
    rodape e a espera das Familias dizem que a ultima escolha nao foi salva, nunca "Salvando" nem "Tudo pronto"."""
    job, ids = _copia(base, 'relato', tmp_path)
    estado = {'falhar': False}

    def rota(r):
        if r.request.method == 'GET' or not estado['falhar']:
            return r.continue_()
        return _recusar_rascunho(r)
    with rv._Tela(pw, job, 1600, 900) as pg:
        pg.route(re.compile(r'.*/api/rascunho$'), rota)
        _escolhas_do_relato(pg, ids, kr.DESIGN)
        _esperar_gravado(pg)
        estado['falhar'] = True
        rv._passo(pg, 'design')
        art = "article[data-chave='fgrafismo']"
        _clicar(pg, art + ' .funcao-ds-topo')
        time.sleep(0.2)
        _clicar(pg, art + " button[data-regra='raiz_area']")
        tp._esperar(pg, '() => document.documentElement.dataset.rascunho === "erro" ? "1" : ""', teto_s=20)
        time.sleep(3)
        p = pg.evaluate(PAGINA)
        rv._passo(pg, 'pecas')
        time.sleep(0.8)
        q = pg.evaluate(PAGINA)
    assert MOTIVO_DE_TESTE in p['aviso'], p
    assert 'Salvando' not in p['salvar']['dica'] and 'não foi salva' in p['salvar']['dica'], p
    assert p['salvar']['desligado'], p
    assert 'Tudo pronto' not in q['espera']['texto'] and 'não foi salva' in q['espera']['texto'], q
    assert MOTIVO_DE_TESTE in q['espera']['texto'], q
    # o aviso do rascunho continua depois de trocar de passo: a escolha continua sem gravar
    assert MOTIVO_DE_TESTE in q['aviso'], q


def test_rascunho_que_falhou_todas_as_vezes_nao_fica_dizendo_que_salva(base, pw, tmp_path):
    """As tentativas sozinhas acabam (500): o rodape diz que a escolha nao foi salva, sem "Salvando"."""
    job, ids = _copia(base, 'relato', tmp_path)
    with rv._Tela(pw, job, 1600, 900) as pg:
        pg.route(re.compile(r'.*/api/rascunho$'),
                 lambda r: r.continue_() if r.request.method == 'GET' else r.fulfill(status=500, body=''))
        _escolhas_do_relato(pg, ids, kr.DESIGN_MESMA_REGRA)
        tp._esperar(pg, '() => document.getElementById("aviso-acoes").textContent.includes("Faça uma mudança") ? "1" : ""',
                    teto_s=60)
        time.sleep(0.5)
        p = pg.evaluate(PAGINA)
    assert 'Salvando' not in p['salvar']['dica'] and 'não foi salva' in p['salvar']['dica'], p


# ------------------------------------------------------------------ UX 1: o aviso de ato velho sai
def test_aviso_da_recusa_sai_quando_o_da_muda_alguma_coisa(base, pw, tmp_path):
    job, funcoes = _copia(base, 'kva', tmp_path)
    motivo = 'Falta confirmar 1 família para salvar.'
    with rv._Tela(pw, job, 1024, 768, rascunho_kv=funcoes) as pg:
        rv._passo(pg, 'pecas')
        _confirmar_familias(pg)
        _recusar_salvar(pg, motivo)
        logo = pg.evaluate(PAGINA)['aviso']
        rv._passo(pg, 'design')
        pg.evaluate('''() => { const a = document.querySelector("#resumo-design article.funcao-ds");
            const b = Array.from(a.querySelectorAll("button[data-regra]")).find(x => x.getAttribute("aria-pressed") !== "true");
            b.click(); }''')
        _esperar_gravado(pg)
        depois = pg.evaluate(PAGINA)['aviso']
    assert motivo in logo
    assert depois == '', depois


def test_aviso_da_recusa_sai_ao_trocar_de_passo(base, pw, tmp_path):
    job, funcoes = _copia(base, 'kva', tmp_path)
    with rv._Tela(pw, job, 1600, 900, rascunho_kv=funcoes) as pg:
        rv._passo(pg, 'pecas')
        _confirmar_familias(pg)
        _recusar_salvar(pg, 'Motivo de teste.')
        logo = pg.evaluate(PAGINA)['aviso']
        rv._passo(pg, 'lido')
        depois = pg.evaluate(PAGINA)['aviso']
    assert 'Motivo de teste.' in logo and depois == '', (logo, depois)


# ------------------------------------------------------------------ UX 2 e 3: o foco e uma regiao viva so
def test_foco_volta_ao_botao_depois_da_recusa_pelo_teclado(base, pw, tmp_path):
    job, funcoes = _copia(base, 'kva', tmp_path)
    with rv._Tela(pw, job, 1600, 900, rascunho_kv=funcoes) as pg:
        rv._passo(pg, 'pecas')
        _confirmar_familias(pg)
        _recusar_salvar(pg, 'Motivo de teste.', teclado=True)
        depois = pg.evaluate(FOCO)
    assert depois in ('salvar-seguir', 'aviso-acoes'), depois


def test_recusa_e_anunciada_uma_vez_so(base, pw, tmp_path):
    job, funcoes = _copia(base, 'kva', tmp_path)
    motivo = 'Motivo de teste para uma regiao viva so.'
    with rv._Tela(pw, job, 1600, 900, rascunho_kv=funcoes) as pg:
        rv._passo(pg, 'pecas')
        _confirmar_familias(pg)
        _recusar_salvar(pg, motivo)
        vivos = pg.evaluate('''() => Array.from(document.querySelectorAll("[role=alert],[role=status],[aria-live]"))
            .filter(n => !n.hidden && n.textContent.includes(%s)).map(n => n.id)''' % json.dumps(motivo))
        selo = pg.evaluate(PAGINA)['selo']
    assert vivos == ['aviso-acoes'], vivos
    assert selo and 'Tente de novo' not in selo, selo


# ------------------------------------------------------------------ UX 4: "Ir para o Design system" mostra o motivo
@pytest.mark.parametrize('largura,altura', [(1600, 900), (1024, 768)])
def test_ir_para_o_design_mostra_o_cartao_e_o_aviso(base, pw, tmp_path, largura, altura):
    job, ids = _copia(base, 'relato', tmp_path)
    with rv._Tela(pw, job, largura, altura) as pg:
        _escolhas_do_relato(pg, ids, kr.DESIGN)
        _esperar_gravado(pg)
        rv._passo(pg, 'pecas')
        tp._esperar(pg, '() => document.getElementById("espera-ir").hidden ? "" : "1"', teto_s=30)
        _clicar(pg, '#espera-ir')
        time.sleep(0.8)
        m = pg.evaluate('''() => { const vis = n => { if (!n || n.hidden) return false; const r = n.getBoundingClientRect();
                return r.height > 0 && r.top >= 40 && r.bottom <= innerHeight - 40; };
            const conf = Array.from(document.querySelectorAll("#resumo-design article.funcao-ds.em-conflito"));
            return {conflitos: conf.map(a => a.dataset.chave),
                    algum_visivel: conf.some(a => vis(a.querySelector(".funcao-ds-topo") || a)),
                    aviso_visivel: vis(document.getElementById("aviso-design"))}; }''')
    assert m['conflitos'], m
    assert m['algum_visivel'] and m['aviso_visivel'], m


# ------------------------------------------------------------------ UX 5 e 6, regressao 3 e 4: as frases do motivo
def test_lista_de_camadas_e_funcoes_do_motivo_usa_e_no_fim():
    laudo = {'camadas': [{'identidade': {'layer_id': 1}, 'nome': 'Rectangle 1'},
                         {'identidade': {'layer_id': 2}, 'nome': 'brasil'},
                         {'identidade': {'layer_id': 3}, 'nome': 'BG'}]}
    dois = te.motivo_da_conferencia([{'codigo': 'bloco_com_regras_diferentes', 'medidas': {'camadas': [1, 2]}}],
                                    laudo, {1: {'funcao': 'fundo'}, 2: {'funcao': 'grafismo'}})
    tres = te.motivo_da_conferencia([{'codigo': 'bloco_com_regras_diferentes', 'medidas': {'camadas': [1, 2, 3]}}],
                                    laudo, {1: {'funcao': 'fundo'}, 2: {'funcao': 'grafismo'}, 3: {'funcao': 'fundo'}})
    assert 'Rectangle 1 e brasil' in dois['texto'] and 'fundo e grafismo' in dois['texto'], dois['texto']
    assert 'Rectangle 1, brasil e BG' in tres['texto'], tres['texto']


def test_frase_curta_do_rodape_diz_o_que_fazer():
    verbos = re.compile(r'\b(escolha|dê|confira|confirme|tire|aprove|mude|resolva|escreva|decida|peça|fique|abra|feche)'
                        r'\b', re.I)
    curtos = dict(te.CURTO_DO_MOTIVO, passo_2_incompleto=te.CURTO_PASSO_2, sem_formatos=te.CURTO_SEM_FORMATOS)
    sem_acao = sorted(c for c, t in curtos.items() if not verbos.search(t))
    assert not sem_acao, sem_acao
    # cabe no rodape a 1024 px depois de "As famílias ainda não foram montadas."
    longos = sorted(c for c, t in curtos.items() if len(t) > 60)
    assert not longos, longos


def test_motivo_sem_nome_nao_mostra_id_interno():
    laudo = {'camadas': [{'identidade': {'layer_id': 4711}, 'nome': ''}]}
    m = te.motivo_da_conferencia([{'codigo': 'camada_sem_funcao', 'medidas': {'layer_id': 4711}}], laudo)
    assert '4711' not in m['texto'] and 'sem nome' in m['texto'], m['texto']


def test_destino_pelo_texto_saiu():
    """destino_da_espera deduzia o passo pelo texto e errava com as frases novas; o passo vem do motivo."""
    assert not hasattr(te, 'destino_da_espera')


# ------------------------------------------------------------------ corretude D2: a regra de bloco sem controle na tela
def test_motivo_de_regra_de_bloco_pede_ajuda_ao_claude():
    """A tela nao edita regras_bloco (o briefing que as tem veio de fora da tela): o motivo nao manda a um passo sem o
    controle e diz que o Claude resolve."""
    laudo = {'camadas': [{'identidade': {'layer_id': 7}, 'nome': 'camada-sete'}]}
    for c in ('regra_de_bloco_sem_bloco', 'regra_de_bloco_conflitante'):
        m = te.motivo_da_conferencia([{'codigo': c, 'medidas': {'layer_id': 7, 'camadas': [7]}}], laudo)
        assert m['passo'] is None and te.DESTINO_DO_MOTIVO[c] is None, c
        assert 'Claude' in m['texto'] and 'Claude' in m['curto'], m
        assert 'Design system' not in m['texto'], m


def test_espera_sem_passo_nao_mostra_botao_que_leva_ao_lugar_errado(base, pw, tmp_path):
    """O motivo sem passo na tela (a regra de bloco): a espera diz o motivo, a lista marca o que falta, e nenhum botao
    leva a Funcoes ou ao Design system."""
    job, ids = _copia(base, 'relato', tmp_path)
    texto = te.MOTIVOS_DA_CONFERENCIA['regra_de_bloco_conflitante'].replace('{camadas}', 'a e b')

    def rota(r):
        resp = r.fetch()
        e = resp.json()
        if (e.get('passo_3') or {}).get('aguarda_passo_2') and e['passo_3'].get('motivo'):
            e['passo_3']['motivo'] = dict(e['passo_3']['motivo'], codigo='regra_de_bloco_conflitante', texto=texto,
                                          curto=te.CURTO_DO_MOTIVO['regra_de_bloco_conflitante'], passo=None,
                                          funcoes=[])
            e['passo_3']['ir'] = None
            e['passo_3']['texto'] = te.AGUARDA_CONFERENCIA_COM_MOTIVO % texto
        return r.fulfill(response=resp, json=e)
    with rv._Tela(pw, job, 1600, 900) as pg:
        pg.route(re.compile(r'.*/api/estado$'), rota)
        _escolhas_do_relato(pg, ids, kr.DESIGN)
        _esperar_gravado(pg)
        rv._passo(pg, 'pecas')
        tp._esperar(pg, '() => document.getElementById("espera-texto").textContent.includes("Claude") ? "1" : ""',
                    teto_s=30)
        p = pg.evaluate(PAGINA)
        ir = pg.evaluate('() => document.getElementById("dica-ir").hidden')
    assert p['espera']['botao'] is None, p
    assert p['espera']['faltando'], p
    assert 'Claude' in p['salvar']['dica'] and ir, (p, ir)


# ------------------------------------------------------------------ regressao 2: a tarefa em andamento e o esquema
def test_tarefa_em_andamento_da_motivo_so_ao_pedido_com_a_forma_da_rota(tmp_path):
    import test_tela_tarefas as tt
    from desdobra.tela import servidor as ts
    j = tmp_path / 'job'
    (j / 'laudo').mkdir(parents=True)
    (j / 'laudo' / 'laudo.json').write_text('{"laudo": "sintetico"}', encoding='utf-8')
    (j / 'estado.json').write_text('{}', encoding='utf-8')
    fake = tt.Fake()
    s = ts.ServidorTela(tt._conteudo(j, {'atualizar': 0, 'recarregar': 0}), pasta=j, modo_teste=True,
                        atos={'render': fake.ato()}).iniciar()
    try:
        b = tts._entrar(s)
        tt._iniciar(s, b)
        lixo = tte._escrever(s, '/api/ato/pedir', {'campo_que_nao_existe': [1, 2, 3]}, cookie=b)
        sem_ato = tte._escrever(s, '/api/ato/pedir', {'ato': 'ato_que_nao_existe', 'dados': {}}, cookie=b)
        previa = tte._escrever(s, '/api/familia/previa', {'qualquer': 'coisa'}, cookie=b)
        resposta_errada = tte._escrever(s, '/api/ato/confirmar', {'pedido': 'x', 'resposta': 'outra'}, cookie=b)
        certo = tte._escrever(s, '/api/ato/pedir', {'ato': 'render', 'dados': {}}, cookie=b)
        previa_certa = tte._escrever(s, '/api/familia/previa', {'familia': 'x'}, cookie=b)
    finally:
        for ev in fake.liberar.values():
            ev.set()
        s.parar()
    for r in (lixo, sem_ato, previa, resposta_errada):
        assert r[0] == 403 and r[2] == b'', r
    for r in (certo, previa_certa):
        assert r[0] == 403 and json.loads(r[2]) == {'motivo': ts.MOTIVO_TAREFA_EM_ANDAMENTO}, r
