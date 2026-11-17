# -*- coding: utf-8 -*-
"""M7b, C4: o controle da quebra de linha no palco e a aprovacao da quebra proposta (decisoes-v1.md, 167 e 171;
arquitetura-v1.md, item 9 e 9.8).

Criterios de pronto cobertos aqui:
  - a previa da familia leva, para cada texto que o DA pode quebrar, o texto de agora (o do KV ou o editado na
    familia) com as posicoes das quebras gravadas e dos espacos: a pagina monta o controle a partir dela;
  - o texto editado no palco sai nas linhas da quebra da familia (as juntadas e as inseridas), como o render o desenha;
  - a quebra que o desdobra propos e o DA ainda nao aprovou impede "Confirmar familia", na janela e no motor (a do
    rascunho de antes da 0.9.4 num texto que nao foi editado);
  - a quebra mudada conta como edicao da familia: a frase da familia que mudou de formatos diz que ela tinha edicao;
  - na pagina: o DA clica entre duas palavras para pôr ou tirar a quebra e ve a previa nos membros (a previa espera
    300 ms sem clique); mover, mudar a quebra, confirmar, "Salvar e seguir", fechar e reabrir mostram tudo igual, e a
    derivacao gravada traz a quebra do DA.
  - Linhas do DA (0.9.4): o texto editado nunca quebra sozinho na largura da caixa. O desdobra nao propoe quebra nele,
    a pagina nao tem "Aprovar quebra", e "Confirmar familia" so espera a previa (antes: a proposta e a aprovacao).
Tudo sintetico: o PSD de test_tela_palco (o texto de apoio 'VOX AH', o titulo 'HOAX') e a fonte de autoteste."""
import json
import sys
import time

import pytest

import test_tela_salvar as tsv
import test_tela_servidor as tts
from desdobra import contratos, humano
from desdobra.briefing import modelo as mb
from desdobra.derivacao import quebras as mq
from desdobra.tela import estado as te
from desdobra.tela import rascunho as tr

modelo = tsv.modelo
job = tsv.job
APOIO = 'VOX AH'
TITULO = 'HOAX HOAX HOAX'  # o titulo editado: mais largo que a caixa do KV, fica numa linha so (0.9.4)


def _quebra(el, lid, inseridas=(3,), manter=(), origem='da', aprovada=True):
    return {'elemento': el, 'layer_id': lid, 'manter': list(manter), 'inseridas': list(inseridas), 'origem': origem,
            'aprovada': aprovada}


def _linhas(palco, eid):
    p = next(x for x in palco['pecas'] if x.get('elemento') == eid and x.get('tipo') == 'texto' and x.get('linhas'))
    return [''.join(t['texto'] for t in ln['trechos']) for ln in p['linhas']]


# ------------------------------------------------------------------ funcoes puras
def test_linhas_do_texto_editado_com_a_quebra_da_familia():
    assert mq.linhas_do_editado('VOX\nAH VOX', [], [6]) == ['VOX AH', 'VOX']
    assert mq.linhas_do_editado('VOX\nAH VOX', [0], [6]) == ['VOX', 'AH', 'VOX']
    assert mq.linhas_do_editado('VOX AH', [], []) == ['VOX AH']
    # CR LF e CR contam como LF, como o render desenha o texto editado
    assert mq.linhas_do_editado('VOX\r\nAH VOX', [], [6]) == ['VOX AH', 'VOX']
    assert mq.linhas_do_editado('VOX\rAH', [0], []) == ['VOX', 'AH']


def test_texto_para_quebrar_da_as_posicoes_do_texto_de_agora():
    camada = {'tipo': 'texto', 'texto': {'conteudo': 'HH\rHHH\r'}}
    # a quebra do fim do texto nao abre linha e nao entra
    assert mq.texto_para_quebrar(camada) == {'texto': 'HH\rHHH', 'gravadas': [2], 'espacos': []}
    assert mq.texto_para_quebrar(camada, 'VOX AH\r\nX') == {'texto': 'VOX AH\nX', 'gravadas': [6], 'espacos': [3]}


def test_quebra_por_aprovar_so_na_proposta_sem_aprovacao():
    da = _quebra('el1', 1)
    proposta = _quebra('el2', 2, origem='proposta', aprovada=False)
    aprovada = _quebra('el3', 3, origem='proposta', aprovada=True)
    assert tr.por_aprovar({'quebras': [da, proposta, aprovada]}) == [proposta]
    assert tr.por_aprovar({'quebras': [da, aprovada]}) == []
    assert tr.por_aprovar({}) == [] and tr.por_aprovar(None) == []
    # Linhas do DA (0.9.4): a proposta de antes num texto editado nunca espera aprovacao
    editado = [{'elemento': 'el2', 'acao': 'texto', 'texto': 'VOX AH'}]
    assert tr.por_aprovar({'quebras': [da, proposta, aprovada], 'edicoes': editado}) == []


# ------------------------------------------------------------------ a previa da familia
def test_previa_leva_os_textos_que_o_da_pode_quebrar(job, modelo):
    conteudo = te.montar(job)
    gm = tsv._familia_de(conteudo, 'mesma')
    el, lid = tsv._apoio(modelo)
    r = conteudo['editar']({'familia': gm, 'versao': None, 'edicoes': []})
    textos = {t['elemento']: t for t in r['textos_da_quebra']}
    assert textos[el] == {'elemento': el, 'layer_id': lid, 'texto': APOIO, 'gravadas': [], 'espacos': [3],
                          'editado': False}
    # o titulo e um texto de uma linha so, sem espaco: entra, sem onde quebrar
    titulo = tsv._titulo(conteudo, gm)
    assert textos[titulo]['espacos'] == [] and textos[titulo]['gravadas'] == []
    # o texto editado na familia vale no lugar do texto do KV; o elemento apagado sai
    ed = [{'elemento': el, 'acao': 'texto', 'texto': 'VOX AH\r\nVOX'}, {'elemento': titulo, 'acao': 'apagar'}]
    r = conteudo['editar']({'familia': gm, 'versao': None, 'edicoes': ed})
    textos = {t['elemento']: t for t in r['textos_da_quebra']}
    assert textos[el] == {'elemento': el, 'layer_id': lid, 'texto': 'VOX AH\nVOX', 'gravadas': [6], 'espacos': [3],
                          'editado': True}
    assert titulo not in textos


def test_previa_desenha_o_texto_editado_com_a_quebra_da_familia(job, modelo):
    conteudo = te.montar(job)
    gm = tsv._familia_de(conteudo, 'mesma')
    el, lid = tsv._apoio(modelo)
    ed = [{'elemento': el, 'acao': 'texto', 'texto': 'VOX\nAH VOX'}]
    sem = conteudo['editar']({'familia': gm, 'versao': None, 'edicoes': ed})
    assert all(_linhas(m['palco'], el) == ['VOX', 'AH VOX'] for m in sem['membros'])
    q = _quebra(el, lid, inseridas=(6,), origem='proposta', aprovada=False)
    com = conteudo['editar']({'familia': gm, 'versao': None, 'edicoes': ed, 'quebras': [q]})
    assert com['membros'] and all(_linhas(m['palco'], el) == ['VOX AH', 'VOX'] for m in com['membros'])


# ------------------------------------------------------------------ "Confirmar familia" com a quebra proposta
def test_confirmar_familia_recusa_quebra_proposta_sem_aprovacao(job, modelo):
    conteudo = te.montar(job)
    gm = tsv._familia_de(conteudo, 'mesma')
    el, lid = tsv._apoio(modelo)
    s = tsv._servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        escolhas = tsv._escolhas(conteudo)
        p2 = tsv._passo_2(modelo['funcoes'])
        f = escolhas[gm]
        escolhas[gm]['quebras'] = [_quebra(el, lid, origem='proposta', aprovada=False)]
        assert tsv._gravar_rascunho(s, biscoito, escolhas, p2) == 200
        # a janela recusa antes do dialogo, e o motor recusa mesmo com o Disparo da janela
        assert tsv._ato(s, biscoito, 'familia', {'familia': gm, 'versao': f['versao'], 'edicoes': f['edicoes'],
                                                 'quebras': f['quebras']})[0] != 200
        d = humano.exigir_tela(tr.COMANDO_FAMILIA, s._sessao_humana, confirmado=True)
        with pytest.raises(tr.ErroRascunho) as erro:
            tr.confirmar_familia(job, gm, f['versao'], disparo=d, job_id=s.job_id, laudo_atual=s.laudo_sha256,
                                 edicoes=f['edicoes'], formatos=conteudo['familias'][gm]['formatos'])
        assert erro.value.motivo == 'quebra_proposta'
        assert tr.ler(job, s.laudo_sha256)[0]['familias'][gm]['confirmada'] is False
        # aprovada com um clique, a familia confirma
        escolhas[gm]['quebras'] = [_quebra(el, lid, origem='proposta', aprovada=True)]
        assert tsv._gravar_rascunho(s, biscoito, escolhas, p2) == 200
        assert tsv._ato(s, biscoito, 'familia', {'familia': gm, 'versao': f['versao'], 'edicoes': f['edicoes'],
                                                 'quebras': f['quebras']})[1] == 200
        assert tr.ler(job, s.laudo_sha256)[0]['familias'][gm]['confirmada'] is True
    finally:
        s.parar()


def test_confirmar_familia_confere_as_quebras_que_a_janela_mostra(job, modelo):
    """Revisao do C: a quebra de linha e edicao da familia (decisoes-v1.md, 171). O ato "Confirmar familia" leva as
    quebras que a janela mostra, como leva as edicoes, e o servidor confere contra o rascunho gravado: a quebra que
    nao foi gravada (a gravacao falhou) nunca e confirmada as cegas. Sem o campo, a janela nao mostra quebra."""
    conteudo = te.montar(job)
    gm = tsv._familia_de(conteudo, 'mesma')
    el, lid = tsv._apoio(modelo)
    q = _quebra(el, lid)
    s = tsv._servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        escolhas = tsv._escolhas(conteudo)
        p2 = tsv._passo_2(modelo['funcoes'])
        f = escolhas[gm]
        assert tsv._gravar_rascunho(s, biscoito, escolhas, p2) == 200
        pedido = {'familia': gm, 'versao': f['versao'], 'edicoes': f['edicoes']}
        # a janela mostra a quebra que o rascunho gravado nao tem: recusado antes do dialogo
        assert tsv._ato(s, biscoito, 'familia', dict(pedido, quebras=[q]))[0] != 200
        assert tsv._ato(s, biscoito, 'familia', dict(pedido, quebras='x'))[0] != 200
        # o motor tambem recusa, mesmo com o Disparo da janela
        d = humano.exigir_tela(tr.COMANDO_FAMILIA, s._sessao_humana, confirmado=True)
        with pytest.raises(tr.ErroRascunho) as erro:
            tr.confirmar_familia(job, gm, f['versao'], disparo=d, job_id=s.job_id, laudo_atual=s.laudo_sha256,
                                 edicoes=f['edicoes'], quebras=[q], formatos=conteudo['familias'][gm]['formatos'])
        assert erro.value.motivo == 'mudou'
        assert tr.ler(job, s.laudo_sha256)[0]['familias'][gm]['confirmada'] is False
        # com a quebra gravada, o pedido sem ela (a janela que nao a mostra) e recusado, e o pedido com ela confirma
        escolhas[gm]['quebras'] = [q]
        assert tsv._gravar_rascunho(s, biscoito, escolhas, p2) == 200
        assert tsv._ato(s, biscoito, 'familia', pedido)[0] != 200
        assert tsv._ato(s, biscoito, 'familia', dict(pedido, quebras=[]))[0] != 200
        assert tsv._ato(s, biscoito, 'familia', dict(pedido, quebras=[q]))[1] == 200
        assert tr.ler(job, s.laudo_sha256)[0]['familias'][gm]['confirmada'] is True
    finally:
        s.parar()


def test_rascunho_recusa_a_quebra_no_elemento_de_outro_texto(job, modelo):
    """Revisao 2 do C: a quebra cita o elemento do palco que tem o texto e a camada dele. O rascunho recusa o par que a
    previa e o briefing recusam (o elemento que nao existe, ou que nao tem a camada), como recusa a posicao fora de
    espaco: senao a familia ficaria com a previa recusada a cada abertura, sem clique que tire a quebra."""
    conteudo = te.montar(job)
    gv = tsv._familia_de(conteudo, 'v1')
    el, lid = tsv._apoio(modelo)
    titulo = tsv._titulo(conteudo, gv)
    s = tsv._servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        p2 = tsv._passo_2(modelo['funcoes'])
        escolhas = tsv._escolhas(conteudo)
        # o titulo editado tem um espaco na posicao 9: so o par errado faria a posicao passar
        escolhas[gv]['edicoes'] = escolhas[gv]['edicoes'] + [{'elemento': titulo, 'acao': 'texto', 'texto': TITULO}]
        for forjada in (_quebra(titulo, lid, inseridas=(9,)), _quebra('el999999', lid)):
            escolhas[gv]['quebras'] = [forjada]
            assert tsv._gravar_rascunho(s, biscoito, escolhas, p2) == 403, forjada
        escolhas[gv]['quebras'] = [_quebra(el, lid)]
        assert tsv._gravar_rascunho(s, biscoito, escolhas, p2) == 200
        assert tr.ler(job, s.laudo_sha256)[0]['familias'][gv]['quebras'] == [_quebra(el, lid)]
    finally:
        s.parar()
    # o motor recusa direto, com os elementos que a tela mostra ({id: camadas})
    escolhas[gv]['quebras'] = [_quebra(titulo, lid, inseridas=(9,))]
    corpo = {'job_id': s.job_id, 'laudo_sha256': s.laudo_sha256, 'familias': escolhas}
    with pytest.raises(tr.ErroRascunho) as erro:
        tr.gravar(job, corpo, job_id=s.job_id, laudo_atual=s.laudo_sha256, origem=s.origem_rascunho,
                  elementos_da_tela={el: [lid], titulo: [lid + 1000]})  # numero-neutro: uma camada que nao e a dele
    assert erro.value.motivo == 'quebras'


# ------------------------------------------------------------------ a quebra e edicao da familia
def test_quebra_conta_como_edicao_da_familia(job, modelo):
    conteudo = te.montar(job)
    gm = tsv._familia_de(conteudo, 'mesma')
    el, lid = tsv._apoio(modelo)
    laudo = tr.laudo_sha256(job)
    familias = {g: {'versao': None, 'confirmada': False, 'edicoes': []} for g in conteudo['familias']}
    familias[gm]['quebras'] = [_quebra(el, lid)]
    tr.gravar(job, {'job_id': conteudo['estado']['job_id'], 'laudo_sha256': laudo, 'familias': familias},
              job_id=conteudo['estado']['job_id'], laudo_atual=laudo, origem=mb.ORIGEM_FIXTURE)
    editadas, _cedidos = te.marcas_das_familias(job)
    assert gm in editadas
    familias[gm]['quebras'] = []
    tr.gravar(job, {'job_id': conteudo['estado']['job_id'], 'laudo_sha256': laudo, 'familias': familias},
              job_id=conteudo['estado']['job_id'], laudo_atual=laudo, origem=mb.ORIGEM_FIXTURE)
    assert gm not in te.marcas_das_familias(job)[0]


# ------------------------------------------------------------------ a pagina
JS_LINHAS = ('i => Array.from(document.querySelectorAll(\'#palco .recorte[data-elemento="\' + i + \'"]'
             ' .texto .linha\')).map(l => l.textContent.trim())')
JS_LINHAS_DO_CONTROLE = ('() => Array.from(document.querySelectorAll("#quebra-linhas .quebra-linha")).map(l => '
                         'Array.from(l.querySelectorAll(".quebra-palavra")).map(p => p.textContent).join(" "))')


def _escolher(pg, eid):
    pg.evaluate('i => { const r = document.querySelector(\'#palco .rotulo[data-elemento="\' + i + \'"]\');'
                ' r.focus(); r.dispatchEvent(new KeyboardEvent("keydown", {key: "Enter", bubbles: true})); }', eid)


def _abrir_controle(pg, eid):
    _escolher(pg, eid)
    pg.evaluate('() => document.getElementById("ed-quebra").click()')
    import test_tela_palco as tp
    tp._esperar(pg, '() => document.getElementById("editor-quebra").hidden ? "" : "1"')


def _do_elemento(dados, gid, eid):
    return [q for q in dados['familias'][gid].get('quebras') or [] if q['elemento'] == eid]


@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
def test_quebra_na_tela_do_clique_a_reabertura(job, modelo):
    from playwright.sync_api import sync_playwright

    import test_tela_edicao as ted
    import test_tela_familia_estavel as tfe
    import test_tela_galeria as tg
    import test_tela_palco as tp
    from desdobra.chromium import navegador
    from desdobra.derivacao import nucleo as nd
    from desdobra.job import modo_dados
    from desdobra.tela import atos as ta
    from desdobra.tela import servidor as ts
    conteudo = te.montar(job)
    gm = tsv._familia_de(conteudo, 'mesma')
    apoio, lid = tsv._apoio(modelo)
    titulo = tsv._titulo(conteudo, gm)
    navegador.apontar_playwright()
    with ts.ServidorTela(conteudo, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo)) as srv, sync_playwright() as pw:
        # as outras familias confirmadas e o modo escolhido antes de abrir a pagina; a familia de 'mesma' fica com o DA
        escolhas = tsv._escolhas(conteudo)
        escolhas[gm] = {'versao': escolhas[gm]['versao'], 'confirmada': False, 'edicoes': []}
        corpo = dict({'job_id': srv.job_id, 'laudo_sha256': srv.laudo_sha256, 'familias': escolhas},
                     **tsv._passo_2(modelo['funcoes']))
        tr.gravar(job, corpo, job_id=srv.job_id, laudo_atual=srv.laudo_sha256, origem=srv.origem_rascunho)
        for gid, f in escolhas.items():
            if gid != gm:
                d = humano.exigir_tela(tr.COMANDO_FAMILIA, srv._sessao_humana, confirmado=True)
                tr.confirmar_familia(job, gid, f['versao'], disparo=d, job_id=srv.job_id,
                                     laudo_atual=srv.laudo_sha256, edicoes=f['edicoes'],
                                     formatos=conteudo['familias'][gid]['formatos'],
                                     pecas=conteudo['familias'][gid]['pecas'])
        modo_dados.gravar(job, 'c', disparo=humano.exigir_tela(modo_dados.ESCOLHER, srv._sessao_humana,
                                                               confirmado=True))
        srv.estado = conteudo['recarregar']()
        nav, pg = tp._pagina_da_tela(pw, srv, 1600, 900)  # numero-neutro: janela do teste
        previas = []
        pg.on('request', lambda r: previas.append(r.url) if '/api/familia/previa' in r.url else None)
        try:
            tg._abrir(pg, conteudo['estado'], 'mesma')
            tp._esperar(pg, '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""')
            # mover: o titulo desce pela seta
            ted._focar(pg, titulo)
            pg.keyboard.press('ArrowDown')
            ted._esperar_salvo(pg)
            # a quebra do DA: com o apoio escolhido, um clique entre as duas palavras; tres cliques seguidos pedem uma
            # previa so, 300 ms depois do ultimo
            _abrir_controle(pg, apoio)
            assert pg.evaluate(JS_LINHAS_DO_CONTROLE) == [APOIO]
            antes = len(previas)
            pg.evaluate('''() => {
                const clicar = () => document.querySelector('#quebra-linhas button[data-pos="3"]').click();
                clicar(); clicar(); clicar(); }''')
            assert pg.evaluate(JS_LINHAS_DO_CONTROLE) == ['VOX', 'AH']
            pg.wait_for_timeout(150)  # numero-neutro: ms, dentro da espera de 300 ms
            assert len(previas) == antes
            # espera o pedido, e nao o "pedindo": com a medida da quebra no cache do processo (um teste anterior), a
            # previa volta antes de uma leitura do estado da pagina (revisao do C)
            fim = time.monotonic() + 60  # numero-neutro: segundos de teto do teste
            while len(previas) == antes and time.monotonic() < fim:
                pg.wait_for_timeout(50)  # numero-neutro: ms, intervalo do teste
            tp._esperar(pg, PREVIA_PRONTA)
            ted._esperar_salvo(pg)
            assert len(previas) == antes + 1
            assert pg.evaluate(JS_LINHAS, apoio) == ['VOX', 'AH']
            assert _do_elemento(ted._rascunho_gravado(job), gm, apoio) == [_quebra(apoio, lid)]
            # Linhas do DA (0.9.4; antes o desdobra propunha a quebra na largura da caixa e pedia "Aprovar quebra"): o
            # titulo editado mais largo que a caixa do KV fica numa linha so, sem proposta nem aprovacao
            _escolher(pg, titulo)
            pg.evaluate('() => document.getElementById("ed-texto").click()')
            pg.fill('#ed-campo-texto', TITULO)
            pg.evaluate('() => document.getElementById("ed-texto-aplicar").click()')
            tp._esperar(pg, '() => document.getElementById("editor-texto").hidden ? "1" : ""')
            tp._esperar(pg, PREVIA_PRONTA)
            ted._esperar_salvo(pg)
            assert _do_elemento(ted._rascunho_gravado(job), gm, titulo) == []
            assert pg.evaluate(JS_LINHAS, titulo) == [TITULO]
            assert pg.evaluate('() => !document.getElementById("quebra-proposta") && '
                               '!document.getElementById("aprovar-quebra") && '
                               '!document.getElementById("ed-quebra-aprovar")') is True
            assert pg.evaluate('() => document.getElementById("texto-borda").hidden') is True
            assert pg.evaluate('() => document.getElementById("confirmar-familia").disabled') is False
            # confirmar e "Salvar e seguir"
            tfe._confirmar_na_pagina(pg, '#confirmar-familia')
            tp._esperar(pg, tfe.SALVAR_DESABILITADO + ' ? "" : "1"')
            tfe._confirmar_na_pagina(pg, '#salvar-seguir')
            tp._esperar(pg, '() => document.getElementById("salvo").hidden ? "" : "1"')
            gravado = ted._rascunho_gravado(job)['familias'][gm]
            linhas = {e: pg.evaluate(JS_LINHAS, e) for e in (apoio, titulo)}
            texto = pg.evaluate(tp.JS_TEXTO_DA_MOLDURA)
            assert not tp.IDENTIFICADOR.findall(texto), tp.IDENTIFICADOR.findall(texto)
            # fechar e reabrir: tudo igual
            pg.reload(wait_until='load')
            tp._esperar(pg, tp.JS_PRONTO)
            pg.evaluate('() => document.querySelector("#passos [data-passo=pecas]").click()')
            tg._abrir(pg, conteudo['estado'], 'mesma')
            tp._esperar(pg, '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""')
            assert ted._rascunho_gravado(job)['familias'][gm] == gravado
            assert {e: pg.evaluate(JS_LINHAS, e) for e in (apoio, titulo)} == linhas
            assert pg.evaluate('() => document.getElementById("texto-borda").hidden') is True
            assert pg.evaluate('() => document.getElementById("confirmar-familia").textContent') == 'Família confirmada'
            assert pg.evaluate('() => document.getElementById("salvo").hidden') is False
            _abrir_controle(pg, apoio)
            assert pg.evaluate(JS_LINHAS_DO_CONTROLE) == ['VOX', 'AH']
        finally:
            nav.close()
    assert gravado['confirmada'] is True and len(gravado['edicoes']) == 2  # numero-neutro: mover e o texto
    # a derivacao gravada traz a quebra do DA no apoio; o titulo editado leva so as linhas do DA e a caixa medida
    d = contratos.ler(job / nd.PASTA / 'mesma.json', nd.ESQUEMA)
    por_id = {e['id']: e for e in d['elementos']}
    assert por_id[apoio]['quebras_origem'] == 'da' and por_id[apoio]['origem_geometria'] == 'da'
    assert por_id[apoio]['quebras']['familia'][0]['inseridas'] == [3]
    assert por_id[titulo]['texto_editado'] == TITULO and 'quebras_origem' not in por_id[titulo]
    assert por_id[titulo]['origem_geometria'] == 'da' and por_id[titulo]['quebras'] == 'do_texto_editado'
    assert len(por_id[titulo]['caixa_texto_editado']) == 4
    b = mb.ler(job)
    assert sorted((q['layer_id'], q['origem'], q['aprovada']) for q in b['quebras_por_familia']
                  if q.get('familia') == gm) == [(lid, 'da', True)]
    assert json.loads(json.dumps(b)) == mb.ler(job)


# ------------------------------------------------------------------ revisao do C, na pagina
JS_MEDIDAS = '''() => {
  const alto = id => {
    const n = document.getElementById(id);
    return n && !n.hidden ? n.getBoundingClientRect().height : 0;
  };
  const escala = document.querySelector('#palco .escala');
  // a miniatura a vista: desenhada, com o quadro inteiro dentro da janela
  const aVista = Array.from(document.querySelectorAll('#membros-lista .membro')).filter(b => {
    const q = b.querySelector('.membro-quadro');
    const r = q ? q.getBoundingClientRect() : null;
    return b.offsetParent !== null && r && r.width > 0 && r.height > 0 && r.top >= 0 && r.left >= 0 &&
      r.bottom <= window.innerHeight && r.right <= window.innerWidth;
  });
  return {palco: alto('palco'), faixa: alto('texto-borda'), controle: alto('editor-quebra'),
          barra: alto('barra-edicao'), membros: alto('membros'), variante: alto('variante-palco'),
          largura: escala ? escala.getBoundingClientRect().width : 0,
          miniaturas: document.querySelectorAll('#membros-lista .membro').length,
          miniaturas_a_vista: aVista.map(b => b.dataset.formato),
          rola_x: document.documentElement.scrollWidth > document.documentElement.clientWidth};
}'''
PREVIA_PRONTA = '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""'


def _preparar_pagina(job, modelo, srv, conteudo, gm, confirmar_gm=False, edicoes_gm=None):
    """O rascunho com as outras familias confirmadas e o modo escolhido antes de abrir a pagina; a familia gm fica
    com o DA (ou confirmada, com confirmar_gm), com edicoes_gm."""
    from desdobra.job import modo_dados
    escolhas = tsv._escolhas(conteudo)
    escolhas[gm] = {'versao': escolhas[gm]['versao'], 'confirmada': False, 'edicoes': list(edicoes_gm or [])}
    corpo = dict({'job_id': srv.job_id, 'laudo_sha256': srv.laudo_sha256, 'familias': escolhas},
                 **tsv._passo_2(modelo['funcoes']))
    tr.gravar(job, corpo, job_id=srv.job_id, laudo_atual=srv.laudo_sha256, origem=srv.origem_rascunho)
    for gid, f in escolhas.items():
        if gid != gm or confirmar_gm:
            d = humano.exigir_tela(tr.COMANDO_FAMILIA, srv._sessao_humana, confirmado=True)
            tr.confirmar_familia(job, gid, f['versao'], disparo=d, job_id=srv.job_id, laudo_atual=srv.laudo_sha256,
                                 edicoes=f['edicoes'], formatos=conteudo['familias'][gid]['formatos'],
                                 pecas=conteudo['familias'][gid]['pecas'])
    modo_dados.gravar(job, 'c', disparo=humano.exigir_tela(modo_dados.ESCOLHER, srv._sessao_humana,
                                                           confirmado=True))
    srv.estado = conteudo['recarregar']()


def _editar_titulo(pg, titulo):
    """O DA edita o titulo para um texto mais largo que a caixa do KV (0.9.4: fica numa linha so)."""
    import test_tela_edicao as ted
    import test_tela_palco as tp
    _escolher(pg, titulo)
    pg.evaluate('() => document.getElementById("ed-texto").click()')
    pg.fill('#ed-campo-texto', TITULO)
    pg.evaluate('() => document.getElementById("ed-texto-aplicar").click()')
    tp._esperar(pg, '() => document.getElementById("editor-texto").hidden ? "1" : ""')
    tp._esperar(pg, PREVIA_PRONTA)
    ted._esperar_salvo(pg)


def _na_pagina(job, modelo, janela, passos, fid='mesma', **preparo):
    """Abre a pagina da tela no job sintetico, com a familia de fid aberta, e roda passos(pg, conteudo, gm)."""
    from playwright.sync_api import sync_playwright

    import test_tela_galeria as tg
    import test_tela_palco as tp
    from desdobra.chromium import navegador
    from desdobra.derivacao import medida_quebras
    from desdobra.tela import atos as ta
    from desdobra.tela import servidor as ts
    medida_quebras.limpar_cache()
    conteudo = te.montar(job)
    gm = tsv._familia_de(conteudo, fid)
    navegador.apontar_playwright()
    with ts.ServidorTela(conteudo, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo)) as srv, sync_playwright() as pw:
        _preparar_pagina(job, modelo, srv, conteudo, gm, **preparo)
        nav, pg = tp._pagina_da_tela(pw, srv, *janela)
        try:
            tg._abrir(pg, conteudo['estado'], fid)
            tp._esperar(pg, PREVIA_PRONTA)
            return passos(pg, conteudo, gm)
        finally:
            nav.close()
            medida_quebras.limpar_cache()


@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
def test_quebra_nao_gravada_nao_e_confirmada_pela_janela(job, modelo):
    """A gravacao do rascunho falha depois do clique na quebra; o DA ve 'VOX' / 'AH' e clica "Confirmar familia". O
    servidor recusa, como recusa a edicao nao gravada: a familia fica sem confirmar."""
    import test_tela_edicao as ted
    import test_tela_palco as tp
    apoio, _lid = tsv._apoio(modelo)

    def passos(pg, conteudo, gm):
        pg.route('**/api/rascunho', lambda r: r.abort() if r.request.method == 'POST' else r.continue_())
        _abrir_controle(pg, apoio)
        pg.evaluate('() => document.querySelector(\'#quebra-linhas button[data-pos="3"]\').click()')
        assert pg.evaluate(JS_LINHAS_DO_CONTROLE) == ['VOX', 'AH']
        tp._esperar(pg, '() => document.documentElement.dataset.rascunho === "erro" ? "1" : ""')
        # a previa da quebra volta, e o botao continua desligado: a ultima escolha nao foi gravada (revisao 1 da fase
        # D do M7b). O clique forcado (uma pagina mexida) tenta gravar antes; sem gravar, o ato nao vai
        tp._esperar(pg, '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""')
        assert pg.evaluate('() => document.getElementById("confirmar-familia").disabled') is True
        pg.evaluate('() => { document.documentElement.dataset.estadoAto = ""; '
                    'const b = document.getElementById("confirmar-familia"); b.disabled = false; b.click(); }')
        # o dialogo aberto e o servidor aceitando o pedido do ato; "erro" e a recusa
        fim = time.monotonic() + 60  # numero-neutro: segundos de teto do teste
        while time.monotonic() < fim:
            v = pg.evaluate('() => document.getElementById("confirmacao").open ? "aberto" : '
                            '(document.documentElement.dataset.estadoAto === "erro" ? "erro" : "")')
            if v:
                return gm, v
            time.sleep(0.1)  # numero-neutro: intervalo do teste
        return gm, None
    gm, ato = _na_pagina(job, modelo, (1600, 900), passos)  # numero-neutro: janela do teste
    assert ato == 'erro'
    gravada = ted._rascunho_gravado(job)['familias'][gm]
    assert gravada['confirmada'] is False and not gravada.get('quebras')


@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
@pytest.mark.parametrize('janela', [(2048, 720), (1280, 800)])  # numero-neutro: a janela da decisao 157 e uma menor
def test_palco_continua_legivel_com_o_titulo_editado_e_o_controle(job, modelo, janela):
    """Com o titulo editado e o controle da quebra aberto no apoio, o palco guarda o espaco para o DA ler a quebra que
    fez: as miniaturas saem da frente, como no editor de texto, e o controle fica baixo. 0.9.4: sem a faixa da quebra
    proposta (o desdobra nao propoe mais quebra no texto editado)."""
    import test_tela_palco as tp
    apoio, _lid = tsv._apoio(modelo)

    def passos(pg, conteudo, gm):
        antes = pg.evaluate(JS_MEDIDAS)
        _editar_titulo(pg, tsv._titulo(conteudo, gm))
        _abrir_controle(pg, apoio)
        tp._esperar(pg, PREVIA_PRONTA)
        pg.wait_for_timeout(400)  # numero-neutro: ms, a animacao do controle
        return antes, pg.evaluate(JS_MEDIDAS)
    antes, depois = _na_pagina(job, modelo, janela, passos)
    assert depois['faixa'] == 0 and depois['controle'] > 0
    assert not depois['rola_x']
    medidas = json.dumps({'antes': antes, 'depois': depois})
    assert depois['palco'] >= 0.8 * antes['palco'], medidas  # numero-neutro: o palco perde no maximo 20%
    assert depois['largura'] >= 0.8 * antes['largura'], medidas  # numero-neutro: idem para a peca
    # o DA ve a quebra nos membros da familia enquanto clica (plano do M7b, C4; revisao 2 do C)
    assert depois['miniaturas'] > 0 and len(depois['miniaturas_a_vista']) == depois['miniaturas'], medidas


@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
def test_membros_da_galeria_ficam_a_vista_enquanto_o_da_quebra_a_linha(job, modelo):
    """Revisao 2 do C: a familia da galeria (v1, v2, v3) a 1280 x 800. O DA abre o controle, clica entre 'VOX' e 'AH',
    e a previa volta: as tres miniaturas continuam a vista, com a quebra nova, e o palco continua legivel."""
    import test_tela_palco as tp
    apoio, _lid = tsv._apoio(modelo)

    def passos(pg, conteudo, gm):
        antes = pg.evaluate(JS_MEDIDAS)
        _abrir_controle(pg, apoio)
        n = _esperar_pedido(pg, lambda: pg.evaluate('() => document.querySelector(\'#quebra-linhas '
                                                    'button[data-pos="3"]\').click()'))
        tp._esperar(pg, PREVIA_PRONTA)
        pg.wait_for_timeout(400)  # numero-neutro: ms, a animacao do controle
        linhas = pg.evaluate('() => Array.from(document.querySelectorAll("#membros-lista .membro")).map(b => '
                             'Array.from(b.querySelectorAll(".linha")).map(l => l.textContent.trim()))')
        return antes, pg.evaluate(JS_MEDIDAS), pg.evaluate(JS_LINHAS_DO_CONTROLE), linhas, n
    antes, depois, controle, linhas, n = _na_pagina(job, modelo, (1280, 800), passos, fid='v1')  # numero-neutro
    medidas = json.dumps({'antes': antes, 'depois': depois, 'linhas': linhas})
    assert n >= 1 and controle == ['VOX', 'AH']
    assert antes['miniaturas'] == depois['miniaturas'] == 3, medidas
    assert len(depois['miniaturas_a_vista']) == 3, medidas
    assert all(['VOX', 'AH'] == [x for x in ls if x in ('VOX', 'AH', 'VOX AH')] for ls in linhas), medidas
    assert depois['palco'] >= 0.7 * antes['palco'], medidas  # numero-neutro: a galeria perde no maximo 30%
    assert not depois['rola_x']


def _esperar_pedido(pg, acao):
    """Faz a acao e espera o pedido da previa da familia sair (o pedido, nao o dataset, que a previa rapida pula)."""
    pedidos = []
    pg.on('request', lambda r: pedidos.append(r.url) if '/api/familia/previa' in r.url else None)
    acao()
    fim = time.monotonic() + 60  # numero-neutro: segundos de teto do teste
    while not pedidos and time.monotonic() < fim:
        pg.wait_for_timeout(50)  # numero-neutro: ms entre olhadas
    return len(pedidos)


@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
def test_confirmar_familia_espera_a_previa_do_texto_editado(job, modelo):
    """Revisao 2 do C: a previa demora (a familia grande, ou a medida nova da quebra). O DA edita o titulo para um
    texto mais largo que a caixa do KV; enquanto a previa nao volta, "Confirmar familia" fica desligado, porque o DA
    ainda nao viu a familia. Quando ela volta, o botao liga (0.9.4: o texto fica nas linhas do DA, sem a quebra
    proposta que antes esperava "Aprovar quebra")."""
    import test_tela_edicao as ted
    import test_tela_palco as tp

    def passos(pg, conteudo, gm):
        titulo = tsv._titulo(conteudo, gm)
        # so o tempo muda: o pedido e a resposta sao os do servidor
        pg.evaluate('''() => { const f0 = window.fetch;
            window.fetch = (u, o) => String(u).includes('/api/familia/previa') && window.__atraso
              ? new Promise(r => setTimeout(r, window.__atraso)).then(() => f0(u, o)) : f0(u, o); }''')
        _escolher(pg, titulo)
        pg.evaluate('() => document.getElementById("ed-texto").click()')
        pg.fill('#ed-campo-texto', TITULO)
        pg.evaluate('() => { window.__atraso = 2000; document.getElementById("ed-texto-aplicar").click(); }')
        durante = pg.evaluate('() => [document.documentElement.dataset.previa, '
                              'document.getElementById("confirmar-familia").disabled, '
                              'document.getElementById("confirmar-familia").title]')
        tp._esperar(pg, PREVIA_PRONTA)
        pg.evaluate('() => { window.__atraso = 0; }')
        ted._esperar_salvo(pg)
        tp._esperar(pg, '() => document.getElementById("confirmar-familia").disabled ? "" : "1"')
        depois = pg.evaluate('() => document.getElementById("confirmar-familia").disabled')
        return gm, titulo, durante, depois, ted._rascunho_gravado(job)['familias'][gm]
    gm, titulo, durante, depois, gravada = _na_pagina(job, modelo, (1280, 800), passos)  # numero-neutro
    assert durante[0] == 'pedindo' and durante[1] is True and durante[2], durante
    assert depois is False
    assert gravada['confirmada'] is False and not gravada.get('quebras')




@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
def test_juntar_as_linhas_do_texto_editado_fica_numa_linha(job, modelo):
    """0.9.4 (Linhas do DA; antes a linha juntada que nao cabia voltava a ser quebra proposta): o DA escreve o titulo
    em duas linhas e junta as duas no controle. O texto fica numa linha so, com o mesmo corpo, no controle e no palco;
    a quebra e do DA, sem proposta, e "Confirmar familia" liga depois da previa."""
    import test_tela_edicao as ted
    import test_tela_palco as tp

    def passos(pg, conteudo, gm):
        titulo = tsv._titulo(conteudo, gm)
        _escolher(pg, titulo)
        pg.evaluate('() => document.getElementById("ed-texto").click()')
        pg.fill('#ed-campo-texto', 'HOAX\nHOAX HOAX')
        pg.evaluate('() => document.getElementById("ed-texto-aplicar").click()')
        tp._esperar(pg, '() => document.getElementById("editor-texto").hidden ? "1" : ""')
        tp._esperar(pg, PREVIA_PRONTA)
        ted._esperar_salvo(pg)
        antes = pg.evaluate(JS_LINHAS, titulo)
        _abrir_controle(pg, titulo)
        _esperar_pedido(pg, lambda: pg.evaluate('() => document.querySelector("#quebra-linhas .quebra-marca").click()'))
        tp._esperar(pg, PREVIA_PRONTA)
        ted._esperar_salvo(pg)
        tp._esperar(pg, '() => document.getElementById("confirmar-familia").disabled ? "" : "1"')
        return titulo, {'antes': antes, 'controle': pg.evaluate(JS_LINHAS_DO_CONTROLE),
                        'palco': pg.evaluate(JS_LINHAS, titulo),
                        'aprovar': pg.evaluate('() => !!document.getElementById("ed-quebra-aprovar")'),
                        'familia_off': pg.evaluate('() => document.getElementById("confirmar-familia").disabled'),
                        'rascunho': _do_elemento(ted._rascunho_gravado(job), gm, titulo)}
    titulo, vista = _na_pagina(job, modelo, (1600, 900), passos)  # numero-neutro: janela do teste
    assert vista['antes'] == ['HOAX', 'HOAX HOAX'], vista
    assert vista['controle'] == [TITULO] and vista['palco'] == [TITULO], vista
    assert vista['aprovar'] is False and vista['familia_off'] is False, vista
    [q] = vista['rascunho']
    assert (q['origem'], q['aprovada'], q['manter'], q['inseridas']) == ('da', True, [], []), vista


@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
def test_abrir_a_familia_confirmada_nao_tira_a_confirmacao(job, modelo):
    """A familia confirmada no rascunho, com o titulo editado mais largo que a caixa e sem quebra. So abrir a familia
    na tela nunca tira a confirmacao do DA. Quando o DA mexe na familia, a confirmacao cai pela edicao dele. 0.9.4:
    o desdobra nao propoe quebra no titulo editado (antes propunha), e nenhuma faixa aparece."""
    import test_tela_edicao as ted
    import test_tela_palco as tp
    titulo_de = {}

    def edicoes(conteudo, gm):
        titulo_de[gm] = tsv._titulo(conteudo, gm)
        return [{'elemento': titulo_de[gm], 'acao': 'texto', 'texto': TITULO}]

    def passos(pg, conteudo, gm):
        pg.wait_for_timeout(1500)  # numero-neutro: ms, mais que a espera do rascunho
        depois_de_abrir = ted._rascunho_gravado(job)['familias'][gm]
        faixa = pg.evaluate('() => document.getElementById("texto-borda").hidden')
        ted._focar(pg, titulo_de[gm])
        pg.keyboard.press('ArrowDown')
        tp._esperar(pg, '() => document.getElementById("confirmar-familia").textContent === "Família confirmada" '
                        '? "" : "1"')
        tp._esperar(pg, PREVIA_PRONTA)
        ted._esperar_salvo(pg)
        return gm, depois_de_abrir, faixa, ted._rascunho_gravado(job)['familias'][gm]
    conteudo = te.montar(job)
    gm0 = tsv._familia_de(conteudo, 'mesma')
    gm, aberta, faixa, mexida = _na_pagina(job, modelo, (1280, 800), passos, confirmar_gm=True,  # numero-neutro
                                           edicoes_gm=edicoes(conteudo, gm0))
    assert aberta['confirmada'] is True and aberta.get('confirmacao') and not aberta.get('quebras'), aberta
    assert faixa is True
    assert mexida['confirmada'] is False and not mexida.get('quebras'), mexida
