# -*- coding: utf-8 -*-
"""M7a, fatia 2: o passo 1 da tela, "O que eu li", com as decisoes do DA em botoes.

Criterios de pronto cobertos aqui (decisoes-v1.md, 159 e 170; proposta do M7, secao 2, 163 e 166, com a 159 vencendo
onde a proposta mandava o DA ao terminal; secao 4, fatia a6b):
  - o modo de dados e escolhido pelo DA na tela, como fonte unica (briefing/modo-dados.json): sem escolha, o envelope,
    o pacote e as sugestoes tratam o job como c, mesmo com o estado.json de um job antigo dizendo a ou b; a escolha de
    teste nunca abre o modo; o modo acima do teto da agencia nao e oferecido e e recusado pelo motor;
  - a tela mostra o modo sem valor marcado e so as opcoes dentro do teto;
  - o linkado e o valor de spec viram botoes do passo 1, com a confirmacao na janela: o Disparo da tela (meio tela) ou o
    de teste (meio medicao, origem fixture_de_teste) e o que fica gravado; dado fora da lista de candidatos ou de
    pendencias e recusado antes do dialogo;
  - os esquemas aceitam meio tela (e medicao) nos linkados e nas acoes de spec;
  - a divergencia de largura, a mesclagem e as paradas do isolador aparecem como bloqueio em texto simples, sem
    comando nem identificador do motor;
  - o gancho nega ao Claude escrever a escolha do modo;
  - no Chromium sem janela: os tres modos aparecem sem nada marcado, o clique pede a confirmacao na janela, e a
    escolha confirmada aparece marcada e fica depois de recarregar.
Tudo sintetico.
"""
import json

import pytest

import test_render_apoio as rap
import test_render_revisao as trr
import test_specs as tsp
import test_specs_apoio as sap
import test_tela_escrita as tte
import test_tela_servidor as tts
from conftest import psd_minimo
from desdobra import cli, contratos, humano
from desdobra.job import modo_dados as md
from desdobra.job import nucleo
from desdobra.render import contrato as mc
from desdobra.resultado import Resultado
from desdobra.sugestao import pacote
from desdobra.tela import atos as ta
from desdobra.tela import estado as te
from desdobra.tela import servidor as ts

ambiente_limpo = tte.ambiente_limpo
UID = 'uuid-linkado-sintetico'
ARTE = 'entrada/campanha/arte-linkada.png'
PROIBIDOS = ('"desdobra', 'desdobra job', 'Rode', 'terminal', '--job', '\u2014', '\u2013', 'grupo')


def _laudo_de_mentira(job):
    arq = job / 'laudo' / 'laudo.json'
    if not arq.is_file():
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text('{"laudo": "sintetico"}', encoding='utf-8')


@pytest.fixture
def job_c(tmp_path):
    (tmp_path / 'kv.psd').write_bytes(psd_minimo())
    nucleo.criar(tmp_path / 'job', tmp_path / 'kv.psd', 'a')  # o pedido do job criar fica so como registro
    _laudo_de_mentira(tmp_path / 'job')
    return tmp_path / 'job'


def _disparo(comando=md.ESCOLHER, teste=True):
    sessao = humano.abrir_sessao_tela(teste=teste)
    return humano.exigir_tela(comando, sessao, confirmado=True)


def _servidor(job, teste=True, teto=None):
    return ts.ServidorTela(tts._conteudo(), pasta=job, modo_teste=teste, atos=ta.atos_do_job(job, teto=teto)).iniciar()


def _ato(s, nome, dados):
    """Pede o ato e confirma. (codigo do pedido, codigo da confirmacao, texto do dialogo)."""
    if not hasattr(s, 'biscoito_do_teste'):
        s.biscoito_do_teste = tts._entrar(s)  # a entrada vale uma vez
    biscoito = s.biscoito_do_teste
    codigo, p = tte._pedir_ato(s, biscoito, nome=nome, dados=dados)
    if codigo != 200:
        return codigo, None, None
    c2 = tte._escrever(s, '/api/ato/confirmar', {'pedido': p['pedido'], 'resposta': 'confirmar'}, cookie=biscoito)[0]
    return codigo, c2, p


# ------------------------------------------------------------------ o modo de dados como fonte unica
def test_sem_escolha_o_job_e_c_mesmo_com_o_estado_dizendo_a(job_c):
    estado = json.loads((job_c / 'estado.json').read_text(encoding='utf-8'))
    assert estado['modo_dados'] == 'a'
    assert md.escolhido(job_c) is None and md.efetivo(job_c) == 'c'
    assert cli._modo_do_resultado(Resultado(comando='x', pasta_job=job_c), None) == 'c'
    assert pacote.modo_do_job(job_c, estado) == 'c'


def test_escolha_do_da_vale_e_o_teto_limita(job_c, ambiente_limpo):
    dados = md.gravar(job_c, 'a', disparo=_disparo(teste=False))
    assert dados['origem'] == 'da' and dados['escolhido_por']['meio'] == 'tela'
    contratos.ler(job_c / md.ARQUIVO, md.ESQUEMA)
    r = Resultado(comando='x', pasta_job=job_c)
    assert md.efetivo(job_c) == 'a' and cli._modo_do_resultado(r, None) == 'a'
    assert cli._modo_do_resultado(r, 'b') == 'b'
    estado = json.loads((job_c / 'estado.json').read_text(encoding='utf-8'))
    assert pacote.modo_do_job(job_c, estado) == 'a'
    estado['teto_modo_dados'] = 'c'
    assert pacote.modo_do_job(job_c, estado) == 'c'


def test_escolha_de_teste_nunca_abre_o_modo(job_c):
    dados = md.gravar(job_c, 'a', disparo=_disparo())
    assert dados['origem'] == 'fixture_de_teste' and dados['escolhido_por']['meio'] == 'medicao'
    assert md.ler(job_c)['valor'] == 'a' and md.escolhido(job_c) is None and md.efetivo(job_c) == 'c'


def test_escolha_acima_do_teto_e_recusada_e_nada_e_gravado(job_c):
    assert md.opcoes(None) == ['a', 'b', 'c'] and md.opcoes('b') == ['b', 'c'] and md.opcoes('c') == ['c']
    with pytest.raises(md.ErroModo):
        md.gravar(job_c, 'a', disparo=_disparo(), teto_='b')
    with pytest.raises(md.ErroModo):
        md.gravar(job_c, 'z', disparo=_disparo())
    assert not (job_c / md.ARQUIVO).exists()


def test_escolha_pede_o_disparo_do_proprio_ato(job_c):
    with pytest.raises(humano.ErroHumano):
        md.gravar(job_c, 'b', disparo=_disparo('linkado confirmar'))
    with pytest.raises(humano.ErroHumano):
        md.gravar(job_c, 'b', disparo=None)
    assert not (job_c / md.ARQUIVO).exists()


def test_arquivo_fora_do_contrato_vale_c(job_c):
    (job_c / md.ARQUIVO).parent.mkdir(exist_ok=True)
    (job_c / md.ARQUIVO).write_text('{"valor": "a", "origem": "da"}', encoding='utf-8')
    assert md.escolhido(job_c) is None and md.efetivo(job_c) == 'c'


def test_teto_do_job_junta_estado_e_linha_de_comando(job_c):
    assert md.teto_do_job(job_c) is None and md.teto_do_job(job_c, 'b') == 'b'
    estado = json.loads((job_c / 'estado.json').read_text(encoding='utf-8'))
    estado['teto_modo_dados'] = 'b'
    (job_c / 'estado.json').write_text(json.dumps(estado), encoding='utf-8')
    assert md.teto_do_job(job_c) == 'b' and md.teto_do_job(job_c, 'c') == 'c' and md.teto_do_job(job_c, 'a') == 'b'


def test_tela_mostra_o_modo_sem_valor_marcado_e_so_dentro_do_teto(job_c):
    m = te.modo_na_tela(job_c, None)
    assert m == {'escolhido': None, 'teto': None, 'opcoes': ['a', 'b', 'c']}
    assert te.modo_na_tela(job_c, 'b')['opcoes'] == ['b', 'c']


# ------------------------------------------------------------------ o ato do modo pela janela
def test_ato_do_modo_na_janela_de_teste(job_c):
    s = _servidor(job_c)
    try:
        c1, c2, p = _ato(s, 'modo_dados', {'modo': 'b'})
        assert (c1, c2) == (200, 200)
        assert p['sim'] == 'Confirmar' and p['nao'] == 'Cancelar' and 'Sem imagens' in p['texto']
        assert not any(x in p['texto'] + p['titulo'] for x in PROIBIDOS)
        reg = md.ler(job_c)
        assert reg['valor'] == 'b' and reg['origem'] == 'fixture_de_teste' and reg['escolhido_por']['meio'] == 'medicao'
        assert md.efetivo(job_c) == 'c'
    finally:
        s.parar()


@pytest.mark.parametrize('dados', [{'modo': 'z'}, {'modo': 'a', 'x': 1}, {}, {'modo': None}, {'modo': ['a']}])
def test_ato_do_modo_recusa_dado_fora_do_formato(job_c, dados):
    s = _servidor(job_c)
    try:
        assert _ato(s, 'modo_dados', dados)[0] == 403
        assert not (job_c / md.ARQUIVO).exists()
    finally:
        s.parar()


def test_ato_do_modo_recusa_acima_do_teto_antes_do_dialogo(job_c):
    s = _servidor(job_c, teto='b')
    try:
        assert _ato(s, 'modo_dados', {'modo': 'a'})[0] == 403
        assert _ato(s, 'modo_dados', {'modo': 'b'})[:2] == (200, 200)
    finally:
        s.parar()


def test_ato_do_modo_de_verdade_grava_meio_tela_e_abre_o_modo(job_c, ambiente_limpo):
    s = _servidor(job_c, teste=False)
    try:
        assert _ato(s, 'modo_dados', {'modo': 'b'})[:2] == (200, 200)
    finally:
        s.parar()
    reg = md.ler(job_c)
    assert reg['origem'] == 'da' and reg['escolhido_por']['meio'] == 'tela' and md.efetivo(job_c) == 'b'


def test_ato_recarrega_o_estado_da_tela(job_c):
    vistos = []
    c = tts._conteudo()

    def recarregar():
        vistos.append(1)
        return dict(c['estado'], recarregado=len(vistos))
    c['recarregar'] = recarregar
    s = ts.ServidorTela(c, pasta=job_c, modo_teste=True, atos=ta.atos_do_job(job_c)).iniciar()
    try:
        assert _ato(s, 'modo_dados', {'modo': 'c'})[:2] == (200, 200)
        assert vistos == [1] and s.estado['recarregado'] == 1
        # um ato recusado nao recarrega
        assert _ato(s, 'modo_dados', {'modo': 'z'})[0] == 403 and vistos == [1]
    finally:
        s.parar()


# ------------------------------------------------------------------ linkado na tela
@pytest.fixture
def job_linkado(tmp_path):
    psd, campanha, _dados = rap.linkado_com_campanha(tmp_path / 'origem')
    return trr._job(tmp_path, psd, campanha=campanha, fontes=False)


def test_linkado_na_tela_lista_os_candidatos(job_linkado):
    laudo = contratos.ler(job_linkado / 'laudo' / 'laudo.json', 'laudo/1')
    lks = te.linkados_na_tela(job_linkado, laudo)
    assert len(lks) == 1 and lks[0]['unique_id'] == UID and not lks[0]['confirmado'] and lks[0]['arquivo'] is None
    assert [c['arquivo'] for c in lks[0]['candidatos']] == [ARTE]


def test_ato_do_linkado_confirma_o_arquivo_na_janela(job_linkado):
    s = _servidor(job_linkado)
    try:
        assert _ato(s, 'linkado', {'unique_id': UID, 'arquivo': 'entrada/campanha/outro.png'})[0] == 403
        assert _ato(s, 'linkado', {'unique_id': 'outro', 'arquivo': ARTE})[0] == 403
        assert _ato(s, 'linkado', {'unique_id': UID})[0] == 403
        c1, c2, p = _ato(s, 'linkado', {'unique_id': UID, 'arquivo': ARTE})
        assert (c1, c2) == (200, 200) and 'arte-linkada.png' in p['texto']
        assert not any(x in p['texto'] + p['titulo'] for x in PROIBIDOS)
    finally:
        s.parar()
    d = contratos.ler(job_linkado / mc.ARQUIVO_LINKADOS, mc.ESQUEMA_LINKADOS)
    quem = d['linkados'][0]['confirmado_por']
    assert d['linkados'][0]['arquivo'] == ARTE and quem['meio'] == 'medicao' and quem['origem'] == 'fixture_de_teste'
    # revisao do M7a: a entrega recusa o job com confirmacao do modo de teste
    from desdobra.entrega import portao
    assert portao.confirmacao_de_teste(job_linkado) == 'confirmacao_de_fixture_de_teste'
    laudo = contratos.ler(job_linkado / 'laudo' / 'laudo.json', 'laudo/1')
    lk = te.linkados_na_tela(job_linkado, laudo)[0]
    assert lk['confirmado'] and lk['arquivo'] == ARTE


def test_ato_do_linkado_de_verdade_grava_meio_tela(job_linkado, ambiente_limpo):
    s = _servidor(job_linkado, teste=False)
    try:
        assert _ato(s, 'linkado', {'unique_id': UID, 'arquivo': ARTE})[:2] == (200, 200)
    finally:
        s.parar()
    quem = contratos.ler(job_linkado / mc.ARQUIVO_LINKADOS, mc.ESQUEMA_LINKADOS)['linkados'][0]['confirmado_por']
    assert quem['meio'] == 'tela' and quem['origem'] == 'da'
    from desdobra.entrega import portao
    assert portao.confirmacao_de_teste(job_linkado) is None


# ------------------------------------------------------------------ valores de spec na tela
def _sem_escolha_do_da(job):
    """O modo de teste da tela so abre em job sem decisao do DA (revisao do M7a): o modo de dados que o job de specs
    escolhe como o DA (conftest.escolher_modo_do_da) sai depois do importar."""
    from desdobra.job import modo_dados
    (job / modo_dados.ARQUIVO).unlink(missing_ok=True)


@pytest.fixture
def job_spec(tmp_path):
    from desdobra.specs import importar
    job = tsp._job(tmp_path, {'pme/folha.pdf': sap.folha_pme_sintetica()})
    importar.importar(job)
    _laudo_de_mentira(job)
    _sem_escolha_do_da(job)
    return job


def test_specs_na_tela_listam_as_pendencias_com_o_que_o_da_precisa(job_spec):
    lista = te.specs_pendentes(job_spec)
    assert lista and all(x['valor_id'] and x['campo'] and x['descricao'] for x in lista)
    divergentes = [x for x in lista if x['leituras']]
    assert all(len(x['leituras']) >= 2 for x in divergentes)  # numero-neutro: divergencia tem duas leituras ou mais


def test_ato_da_spec_confirma_um_valor_na_janela(job_spec):
    from desdobra.specs import importar, modelo
    alvo = next(x for x in te.specs_pendentes(job_spec) if not x['leituras'])
    s = _servidor(job_spec)
    try:
        assert _ato(s, 'spec_valor', {'valor_id': 'nao-existe'})[0] == 403
        assert _ato(s, 'spec_valor', {'valor_id': alvo['valor_id'], 'leitura': 0})[0] == 403
        c1, c2, p = _ato(s, 'spec_valor', {'valor_id': alvo['valor_id']})
        assert (c1, c2) == (200, 200)
        assert not any(x in p['texto'] + p['titulo'] for x in PROIBIDOS)
    finally:
        s.parar()
    acoes = importar.ler_confirmacoes(job_spec)['acoes']
    assert len(acoes) == 1 and acoes[0]['meio'] == 'medicao' and acoes[0]['por'] == 'fixture_de_teste'
    from desdobra.entrega import portao
    assert portao.confirmacao_de_teste(job_spec) == 'confirmacao_de_fixture_de_teste'
    doc = contratos.ler(job_spec / 'specs' / 'rascunho.json', 'spec/1')
    v = modelo.indice_de_valores(doc)[alvo['valor_id']][2]
    assert v['situacao'] == 'confirmado' and v['confirmacao']['meio'] == 'medicao'
    assert alvo['valor_id'] not in {x['valor_id'] for x in te.specs_pendentes(job_spec)}


@pytest.fixture
def job_divergente(tmp_path):
    from desdobra.specs import importar
    job = tsp._job(tmp_path, {'globo/meia.html': sap.html_meia_pagina(), 'globo/vertical.html': sap.html_vertical(),
                              'globo/orientacoes.html': sap.html_orientacoes()})
    importar.importar(job)
    _laudo_de_mentira(job)
    _sem_escolha_do_da(job)
    return job


def test_ato_da_spec_escolhe_a_leitura_de_um_divergente(job_divergente):
    from desdobra.specs import importar
    job_spec = job_divergente
    alvo = next(x for x in te.specs_pendentes(job_spec) if x['leituras'])
    assert all(lei['descricao'] for lei in alvo['leituras'])
    s = _servidor(job_spec)
    try:
        assert _ato(s, 'spec_valor', {'valor_id': alvo['valor_id']})[0] == 403  # divergente pede a leitura
        assert _ato(s, 'spec_valor', {'valor_id': alvo['valor_id'], 'leitura': len(alvo['leituras'])})[0] == 403
        assert _ato(s, 'spec_valor', {'valor_id': alvo['valor_id'], 'leitura': True})[0] == 403
        assert _ato(s, 'spec_valor', {'valor_id': alvo['valor_id'], 'leitura': 1})[:2] == (200, 200)
    finally:
        s.parar()
    acoes = importar.ler_confirmacoes(job_spec)['acoes']
    assert acoes[0]['acao'] == 'escolher_leitura' and acoes[0]['leitura'] == 1 and acoes[0]['meio'] == 'medicao'


def test_ato_da_spec_de_verdade_grava_meio_tela(job_spec, ambiente_limpo):
    from desdobra.specs import importar
    alvo = next(x for x in te.specs_pendentes(job_spec) if not x['leituras'])
    s = _servidor(job_spec, teste=False)
    try:
        assert _ato(s, 'spec_valor', {'valor_id': alvo['valor_id']})[:2] == (200, 200)
    finally:
        s.parar()
    a = importar.ler_confirmacoes(job_spec)['acoes'][0]
    assert a['meio'] == 'tela' and a['por'] == 'da'
    from desdobra.entrega import portao
    assert portao.confirmacao_de_teste(job_spec) is None


def test_esquemas_aceitam_meio_tela():
    acao = {'n': 1, 'acao': 'confirmar', 'valor_id': 'x', 'impressao': '0' * 64, 'por': 'da', 'meio': 'tela',
            'em': '2026-11-05T10:00:00-03:00'}
    contratos.validar({'esquema': 'spec-confirmacoes/1', 'acoes': [acao]}, 'spec-confirmacoes/1')
    contratos.validar({'esquema': 'spec-confirmacoes/1', 'acoes': [dict(acao, por='fixture_de_teste', meio='medicao')]},
                      'spec-confirmacoes/1')
    with pytest.raises(contratos.ErroContrato):
        contratos.validar({'esquema': 'spec-confirmacoes/1', 'acoes': [dict(acao, meio='claude')]},
                          'spec-confirmacoes/1')


# ------------------------------------------------------------------ bloqueios em texto simples
def test_paradas_viram_texto_simples_sem_comando(job_c, monkeypatch):
    confirmar = [{'codigo': 'largura_divergente', 'medidas': {'camadas': [{'layer_id': 3}]}},
                 {'codigo': 'efeito_sobre_texto_sem_aplicar', 'medidas': {'camadas': [4]}},
                 {'codigo': 'clipping_dividido_por_texto', 'medidas': {'camadas': [5]}}]
    monkeypatch.setattr(mc, 'montar', lambda pasta: (None, [{'codigo': 'composicao_acima_do_orcamento'}], confirmar))
    laudo = {'camadas': [{'identidade': {'layer_id': 3}, 'nome': 'Titulo', 'aparencia': {}},
                         {'identidade': {'layer_id': 6}, 'nome': 'Brilho', 'aparencia': {'blend': 'SCREEN',
                                                                                         'visivel_efetiva': True}}],
             'recusas': [{'tipo': 'tempo', 'etapa': 'composicao'}]}
    ps = te.paradas(job_c, laudo)
    tipos = [p['tipo'] for p in ps]
    assert tipos.count('largura') == 1 and 'mesclagem' in tipos and 'isolador' in tipos
    assert next(p for p in ps if p['tipo'] == 'largura')['camadas'] == ['Titulo']
    assert any(p['tipo'] == 'mesclagem' and 'Brilho' in p['camadas'] for p in ps)
    for p in ps:
        assert p['texto'] and not any(x in p['texto'] for x in PROIBIDOS), p


def test_paradas_de_um_job_sem_problema_e_vazia(job_c, monkeypatch):
    monkeypatch.setattr(mc, 'montar', lambda pasta: (None, [], []))
    assert te.paradas(job_c, {'camadas': [], 'recusas': []}) == []


def test_paradas_com_contrato_ilegivel_nao_quebram_a_tela(job_c, monkeypatch):
    def quebra(pasta):
        raise ValueError('x')
    monkeypatch.setattr(mc, 'montar', quebra)
    assert te.paradas(job_c, {'camadas': [], 'recusas': []}) == []


def test_bloqueio_de_fase_na_tela_nao_leva_comando(job_c):
    estado = json.loads((job_c / 'estado.json').read_text(encoding='utf-8'))
    estado['fases']['fontes'] = {'situacao': 'ok', 'bloqueio': {'situacao': 'ok_com_bloqueio',
                                                                'o_que_fazer': 'Rode "desdobra job proxima".',
                                                                'contagens': {}}}
    b = te.bloqueio_na_tela('fontes', estado['fases']['fontes']['bloqueio'])
    assert b['descricao'] and b['texto'] and not any(x in b['texto'] for x in PROIBIDOS)


# ------------------------------------------------------------------ gancho
@pytest.mark.parametrize('caminho', ['C:/jobs/kv/briefing/modo-dados.json', 'briefing\\modo-dados.json'])
def test_gancho_nega_escrever_a_escolha_do_modo(caminho):
    g = tts._gancho()
    for ferramenta in ('Write', 'Edit'):
        assert g.decidir({'tool_name': ferramenta, 'tool_input': {'file_path': caminho}}) == 'deny'
    assert g.decidir({'tool_name': 'Bash', 'tool_input': {'command': 'echo {} > C:/j/briefing/modo-dados.json'}}) \
        == 'deny'


# ------------------------------------------------------------------ no Chromium sem janela
def test_passo_1_no_chromium(job_galeria):  # noqa: F811
    from playwright.sync_api import sync_playwright

    import test_tela_palco as tp
    from desdobra.chromium import navegador
    c = te.montar(job_galeria)
    assert c['estado']['lido']['modo_dados'] == {'escolhido': None, 'teto': None, 'opcoes': ['a', 'b', 'c']}
    assert callable(c.get('recarregar'))
    navegador.apontar_playwright()
    try:
        with ts.ServidorTela(c, pasta=job_galeria, modo_teste=True, atos=ta.atos_do_job(job_galeria)) as srv, \
                sync_playwright() as pw:
            nav = pw.chromium.launch(headless=True, args=list(navegador.ARGUMENTOS))
            pg = nav.new_context(viewport={'width': 2048, 'height': 720}).new_page()  # numero-neutro: a tela do Duda
            try:
                try:
                    pg.goto(srv.url_entrada, wait_until='commit')
                except Exception:  # noqa: BLE001 - o 204 nao completa a navegacao
                    pass
                pg.goto(srv.url_pagina, wait_until='load')
                tp._esperar(pg, tp.JS_PRONTO)
                opcoes = pg.evaluate('''() => Array.from(document.querySelectorAll("#lido-modo [data-modo]"))
                    .map(b => [b.dataset.modo, b.getAttribute("aria-pressed"), b.dataset.ato])''')
                assert opcoes == [['a', 'false', 'modo_dados'], ['b', 'false', 'modo_dados'],
                                  ['c', 'false', 'modo_dados']]
                texto = pg.evaluate('() => document.getElementById("passo-lido").textContent')
                assert not any(x in texto for x in PROIBIDOS), texto
                assert 'Faltam' in pg.evaluate('() => document.getElementById("faltam").textContent')
                faltam_antes = pg.evaluate('() => document.querySelectorAll("#itens-faltam li").length')
                pg.evaluate('() => document.querySelector("#lido-modo [data-modo=b]").click()')
                tp._esperar(pg, '() => document.getElementById("confirmacao").open ? "1" : ""')
                assert 'Sem imagens' in pg.evaluate('() => document.getElementById("confirmacao-texto").textContent')
                pg.evaluate('''() => Array.from(document.querySelectorAll("#confirmacao button"))
                    .find(b => b.textContent === "Confirmar").click()''')
                tp._esperar(pg, '() => document.documentElement.dataset.estadoAto === "feito" ? "1" : ""')
                tp._esperar(pg, '''() => (document.querySelector("#lido-modo [data-modo=b]") || {}).getAttribute &&
                    document.querySelector("#lido-modo [data-modo=b]").getAttribute("aria-pressed") === "true" ? "1" : ""''')
                assert md.ler(job_galeria)['valor'] == 'b'
                assert pg.evaluate('() => document.querySelectorAll("#itens-faltam li").length') == faltam_antes - 1
                pg.reload(wait_until='load')
                tp._esperar(pg, tp.JS_PRONTO)
                assert pg.evaluate('''() => document.querySelector("#lido-modo [data-modo=b]")
                    .getAttribute("aria-pressed")''') == 'true'
                assert pg.evaluate('() => document.querySelectorAll("form, [onerror]").length') == 0
            finally:
                nav.close()
            assert srv.contagem['ato_confirmar'] == 1 and srv.contagem['csrf_recusado'] == 0
    finally:
        (job_galeria / md.ARQUIVO).unlink(missing_ok=True)


from test_tela_galeria import job_galeria  # noqa: E402,F401 - fixture do job sintetico com galeria
