# -*- coding: utf-8 -*-
"""M7a, fatia 1: o caminho de escrita da tela, a prova humana pela janela, o rascunho e o gancho.

Criterios de pronto cobertos aqui (decisoes-v1.md, 159, 164, 167 e 170; proposta do M7, secao 2, 159b, 159c, 160b,
160c e 164; secao 3, linhas Escritas, Teto do corpo da requisicao e Gravacao do rascunho; secao 4, fatia a4):
  - so POST, e so nas rotas da tabela de escrita; cada recusa (sem CSRF, Origin errado ou ausente, Sec-Fetch-Site de
    fora, Host errado, formulario, tipo errado, corpo acima do teto, corpo sem tamanho, JSON quebrado, campo fora do
    esquema, rota fora da tabela, sem cookie) e 404 ou 403, sem corpo, e nada e gravado;
  - o token CSRF vai so na pagina servida (meta), por sessao, e nunca no estado;
  - o rascunho (briefing/rascunho.json): ida e volta, gravacao atomica, a espera da gravacao vem do registro de
    limites, a chave e o hash do laudo (rascunho de outro laudo nunca volta calado) e o preparar e o portao de entrega
    so leem o briefing confirmado;
  - o Disparo da tela (meio tela) nasce so de um pedido de uso unico confirmado na janela; cancelar nao grava nada;
    o modo de teste grava origem fixture_de_teste e meio medicao, nunca num job com briefing ou rascunho do DA;
  - o servidor de verdade nao abre a escrita num processo com as marcas do Claude, e o processo de fundo cai para so
    leitura nesse caso;
  - no Chromium sem janela: a gravacao do rascunho espera o DA parar de clicar, a escolha volta ao reabrir, e a
    confirmacao na janela abre sem opcao marcada, com Cancelar sem efeito;
  - o gancho nega ao Claude escrever em briefing/** (rascunho e historico inclusive), derivacao/** e estado.json, e
    pedir as rotas de escrita; o codigo-fonte do motor continua editavel.
Tudo sintetico: laudo de mentira para as rotas e o job de test_tela_galeria para o navegador.
"""
import json
import time

import pytest

import test_derivacao_apoio as ap
import test_tela_servidor as tts
from test_tela_galeria import job_galeria  # noqa: F401 - fixture do job sintetico com galeria
from desdobra import humano, limites
from desdobra.briefing import modelo as mb
from desdobra.tela import rascunho as tr
from desdobra.tela import servidor as ts

COMANDO = 'briefing confirmar'


@pytest.fixture
def job(tmp_path):
    j = tmp_path / 'job'
    (j / 'laudo').mkdir(parents=True)
    (j / 'laudo' / 'laudo.json').write_text('{"laudo": "sintetico"}', encoding='utf-8')
    return j


def _atos(chamadas):
    def executar(disparo, dados):
        humano.conferir(disparo, COMANDO, consumir=True)
        chamadas.append((disparo, dados))
        return {'feito': True}
    return {'teste': ts.Ato(comando=COMANDO, titulo='Confirmar o teste', texto='Este é um ato de teste.',
                            sim='Confirmar', nao='Cancelar', executar=executar)}


@pytest.fixture
def chamadas():
    return []


@pytest.fixture
def srv(job, chamadas):
    s = ts.ServidorTela(tts._conteudo(), pasta=job, modo_teste=True, atos=_atos(chamadas)).iniciar()
    yield s
    s.parar()


def _escrever(s, rota, dados=None, *, cookie, csrf=True, origem=True, site='same-origin', tipo='application/json',
              corpo=None, host=None, extra=()):
    corpo = corpo if corpo is not None else json.dumps(dados if dados is not None else {}).encode('utf-8')
    cab = []
    if origem:
        cab.append(('Origin', s.origem if origem is True else origem))
    if site:
        cab.append(('Sec-Fetch-Site', site))
    if tipo:
        cab.append(('Content-Type', tipo))
    if csrf:
        cab.append(('X-Desdobra-CSRF', s.csrf if csrf is True else csrf))
    cab += list(extra)
    return tts._pedir(s, rota, metodo='POST', cookie=cookie, extra=cab, corpo=corpo, host=host)


def _rascunho(s, **familias):
    return {'job_id': ap.JOB, 'laudo_sha256': s.laudo_sha256,
            'familias': familias or {'vertical-1': {'versao': 'espelhado', 'confirmada': False, 'edicoes': []}}}


# ------------------------------------------------------------------ o token da pagina
def test_csrf_vai_so_na_pagina_e_e_por_sessao(srv, job, chamadas):
    biscoito = tts._entrar(srv)
    pagina = tts._pedir(srv, '/', cookie=biscoito)[2].decode('utf-8')
    assert '<meta name="dsd-csrf" content="%s">' % srv.csrf in pagina
    assert srv.csrf not in tts._pedir(srv, '/api/estado', cookie=biscoito)[2].decode('utf-8')
    assert len({srv.csrf, srv.token, srv.sessao}) == 3  # numero-neutro: tres segredos diferentes
    outro = ts.ServidorTela(tts._conteudo(), pasta=job, modo_teste=True, atos=_atos(chamadas))
    assert outro.csrf != srv.csrf


def test_servidor_so_de_leitura_nao_tem_csrf_nem_escrita():
    s = ts.ServidorTela(tts._conteudo()).iniciar()
    try:
        biscoito = tts._entrar(s)
        pagina = tts._pedir(s, '/', cookie=biscoito)[2].decode('utf-8')
        assert '<meta name="dsd-csrf" content="">' in pagina and s.csrf is None
        assert _escrever(s, '/api/rascunho', {}, cookie=biscoito, csrf='x')[0] == 404
        assert tts._pedir(s, '/api/rascunho', cookie=biscoito)[0] == 404
    finally:
        s.parar()


# ------------------------------------------------------------------ recusas da escrita
RECUSAS = {
    'sem_csrf': dict(csrf=False),
    'csrf_errado': dict(csrf='0' * 32),
    'origin_errado': dict(origem='http://127.0.0.1:1'),
    'origin_de_fora': dict(origem='https://exemplo.test'),
    'sem_origin': dict(origem=False),
    'site_de_fora': dict(site='cross-site'),
    'site_irmao': dict(site='same-site'),
    'sem_site': dict(site=False),
    'host_errado': dict(host='localhost:1'),
    'formulario': dict(tipo='application/x-www-form-urlencoded', corpo=b'a=b', csrf=False),
    'formulario_com_csrf': dict(tipo='application/x-www-form-urlencoded', corpo=b'a=b'),
    'multipart': dict(tipo='multipart/form-data; boundary=x', corpo=b'--x--'),
    'texto': dict(tipo='text/plain', corpo=b'{}'),
    'sem_tipo': dict(tipo=False),
    'json_quebrado': dict(corpo=b'{"job_id": '),
    'nao_utf8': dict(corpo=bytes([255, 254, 0])),
    'sem_tamanho': dict(corpo=b''),
    'em_pedacos': dict(corpo=b'', extra=[('Transfer-Encoding', 'chunked')]),
}


@pytest.mark.parametrize('caso', sorted(RECUSAS))
def test_cada_recusa_da_escrita_e_403_ou_404_sem_corpo_e_nada_gravado(srv, job, caso):
    biscoito = tts._entrar(srv)
    kw = dict(RECUSAS[caso])
    corpo = kw.pop('corpo', None)
    dados = None if corpo is not None else _rascunho(srv)
    codigo, cab, resto = _escrever(srv, '/api/rascunho', dados, cookie=biscoito, corpo=corpo, **kw)
    assert codigo in (403, 404), (caso, codigo)
    assert resto == b'' and cab['content-length'] == ['0']
    assert not (job / tr.ARQUIVO).exists()


def test_corpo_acima_do_teto_e_recusado_sem_ler(srv, job):
    biscoito = tts._entrar(srv)
    teto = int(limites.valor('tela.corpo_max_bytes'))
    assert srv.corpo_max == teto
    codigo, _cab, resto = _escrever(srv, '/api/rascunho', cookie=biscoito, corpo=b'',
                                    extra=[('Content-Length', str(teto + 1))])
    assert codigo == 403 and resto == b''
    assert srv.contagem['corpo_recusado'] == 1 and not (job / tr.ARQUIVO).exists()


def test_teto_do_corpo_tem_fonte_e_e_a_calibrar():
    lim = limites.obter('tela.corpo_max_bytes')
    assert lim.valor == 2 * 1024 * 1024 and lim.fonte is not None and lim.situacao == 'a_calibrar'
    assert lim.efeito == 'registra' and 'Origem:' in lim.nota
    esp = limites.obter('tela.rascunho_espera_ms')
    assert esp.valor == 500 and esp.fonte is not None and esp.situacao == 'a_calibrar' and esp.efeito == 'registra'


@pytest.mark.parametrize('rota', ['/api/outra', '/api/rascunho/x', '/api/ato', '/api/estado', '/fonte/f01', '/'])
def test_post_fora_da_tabela_de_escrita_da_404(srv, rota):
    biscoito = tts._entrar(srv)
    assert _escrever(srv, rota, {}, cookie=biscoito)[0] == 404


@pytest.mark.parametrize('metodo', ['PUT', 'DELETE', 'PATCH', 'OPTIONS'])
def test_outro_metodo_na_rota_de_escrita_da_404(srv, metodo):
    biscoito = tts._entrar(srv)
    codigo = tts._pedir(srv, '/api/rascunho', metodo=metodo, cookie=biscoito,
                        extra=[('Content-Type', 'application/json'), ('Origin', srv.origem),
                               ('Sec-Fetch-Site', 'same-origin'), ('X-Desdobra-CSRF', srv.csrf)],
                        corpo=b'{}')[0]
    assert codigo == 404
    assert set(ts.METODOS) == {'GET', 'POST'}


def test_escrita_sem_cookie_da_404(srv, job):
    codigo, _c, resto = _escrever(srv, '/api/rascunho', _rascunho(srv), cookie=None)
    assert codigo == 404 and resto == b'' and not (job / tr.ARQUIVO).exists()


def test_get_nas_rotas_so_de_escrita_da_404(srv):
    biscoito = tts._entrar(srv)
    for rota in ('/api/ato/pedir', '/api/ato/confirmar', '/api/ato/cancelar'):
        assert tts._pedir(srv, rota, cookie=biscoito)[0] == 404


@pytest.mark.parametrize('mexer', [
    lambda d: d.update(extra=1),
    lambda d: d.update(job_id='cd' * 16),
    lambda d: d.update(origem='da'),
    lambda d: d['familias'].update({'Fora Do Padrao': {'versao': None, 'confirmada': False, 'edicoes': []}}),
    lambda d: d['familias']['vertical-1'].update(confirmada='sim'),
    lambda d: d['familias']['vertical-1']['edicoes'].append({'elemento': 'el1', 'acao': 'pintar'}),
])
def test_rascunho_fora_do_esquema_e_recusado(srv, job, mexer):
    biscoito = tts._entrar(srv)
    d = _rascunho(srv)
    mexer(d)
    codigo, _c, resto = _escrever(srv, '/api/rascunho', d, cookie=biscoito)
    assert codigo == 403 and resto == b'' and not (job / tr.ARQUIVO).exists()


# ------------------------------------------------------------------ rascunho
def test_rascunho_ida_e_volta(srv, job):
    biscoito = tts._entrar(srv)
    d = _rascunho(srv, **{'vertical-1': {'versao': 'espelhado', 'confirmada': False,
                                         'edicoes': [{'elemento': 'el2', 'acao': 'mover', 'dx': 0.1, 'dy': -0.05}]},
                          'faixa-1': {'versao': None, 'confirmada': False, 'edicoes': []}})
    codigo, cab, corpo = _escrever(srv, '/api/rascunho', d, cookie=biscoito)
    assert codigo == 200, codigo
    gravado = json.loads((job / tr.ARQUIVO).read_text(encoding='utf-8'))
    assert gravado['esquema'] == tr.ESQUEMA and gravado['origem'] == mb.ORIGEM_FIXTURE
    assert gravado['laudo_sha256'] == srv.laudo_sha256 and gravado['familias'] == d['familias']
    assert json.loads(corpo)['atualizado_em'] == gravado['atualizado_em']
    # volta pela rota de leitura, com a espera da gravacao do registro de limites
    lido = json.loads(tts._pedir(srv, '/api/rascunho', cookie=biscoito)[2])
    assert lido['rascunho']['familias'] == d['familias'] and lido['de_outro_laudo'] is False
    assert lido['espera_ms'] == limites.valor('tela.rascunho_espera_ms')
    # gravacao atomica: nenhum temporario fica na pasta
    assert sorted(p.name for p in (job / 'briefing').iterdir()) == ['rascunho.json']
    assert srv.contagem['rascunho'] == 1 and srv.contagem['rascunho_lido'] == 1


def test_rascunho_de_outro_laudo_e_recusado_e_nunca_volta_calado(srv, job):
    biscoito = tts._entrar(srv)
    d = _rascunho(srv)
    d['laudo_sha256'] = '0' * 64
    assert _escrever(srv, '/api/rascunho', d, cookie=biscoito)[0] == 403
    assert not (job / tr.ARQUIVO).exists()
    # um rascunho valido, e depois o PSD relido (laudo novo): o rascunho velho nao volta
    assert _escrever(srv, '/api/rascunho', _rascunho(srv), cookie=biscoito)[0] == 200
    (job / 'laudo' / 'laudo.json').write_text('{"laudo": "relido"}', encoding='utf-8')
    novo = ts.ServidorTela(tts._conteudo(), pasta=job, modo_teste=True).iniciar()
    try:
        b2 = tts._entrar(novo)
        lido = json.loads(tts._pedir(novo, '/api/rascunho', cookie=b2)[2])
        assert lido['rascunho'] is None and lido['de_outro_laudo'] is True
        # e o servidor novo nao aceita o rascunho com o hash velho
        velho = _rascunho(srv)
        assert _escrever(novo, '/api/rascunho', velho, cookie=b2)[0] == 403
    finally:
        novo.parar()
    assert tr.ler(job, tr.laudo_sha256(job)) == (None, True)


def test_rascunho_corrompido_nao_volta(job):
    (job / 'briefing').mkdir()
    (job / tr.ARQUIVO).write_text('{"esquema": "rascunho-tela/1"', encoding='utf-8')
    assert tr.ler(job, tr.laudo_sha256(job)) == (None, True)
    assert tr.ler(job / 'nada', None) == (None, False)


def test_rascunho_solto_e_ignorado_pelo_briefing_e_pelo_portao(job):
    (job / 'briefing').mkdir()
    (job / tr.ARQUIVO).write_text(json.dumps({'esquema': tr.ESQUEMA}), encoding='utf-8')
    assert tr.ARQUIVO != mb.ARQUIVO
    assert mb.ler(job) is None
    assert mb.conferir_para_entrega(job) == (False, 'sem_briefing')


def test_preparar_da_derivacao_le_so_o_briefing_confirmado():
    import inspect

    from desdobra.derivacao import nucleo as nd
    fonte = inspect.getsource(nd)
    assert 'rascunho.json' not in fonte and 'tela.rascunho' not in fonte


# ------------------------------------------------------------------ atos confirmados na janela
def _pedir_ato(s, biscoito, nome='teste', dados=None):
    codigo, _c, corpo = _escrever(s, '/api/ato/pedir', {'ato': nome, 'dados': dados or {}}, cookie=biscoito)
    return codigo, (json.loads(corpo) if codigo == 200 else None)


def test_pedir_devolve_o_texto_da_confirmacao_sem_resposta_marcada(srv, chamadas):
    biscoito = tts._entrar(srv)
    codigo, p = _pedir_ato(srv, biscoito)
    assert codigo == 200 and len(p['pedido']) == 32  # numero-neutro: 16 bytes em hexadecimal
    assert (p['titulo'], p['texto'], p['sim'], p['nao']) == ('Confirmar o teste', 'Este é um ato de teste.',
                                                            'Confirmar', 'Cancelar')
    assert 'padrao' not in p and 'marcada' not in p and chamadas == []


def test_cancelar_nao_grava_nada_e_gasta_o_pedido(srv, job, chamadas):
    biscoito = tts._entrar(srv)
    antes = sorted(p.name for p in job.rglob('*'))
    _c, p = _pedir_ato(srv, biscoito)
    codigo, _cab, resto = _escrever(srv, '/api/ato/cancelar', {'pedido': p['pedido']}, cookie=biscoito)
    assert codigo == 204 and resto == b''
    assert _escrever(srv, '/api/ato/confirmar', {'pedido': p['pedido'], 'resposta': 'confirmar'},
                     cookie=biscoito)[0] == 403
    assert chamadas == [] and sorted(p.name for p in job.rglob('*')) == antes


def test_confirmar_gera_um_disparo_de_teste_de_uso_unico(srv, chamadas):
    biscoito = tts._entrar(srv)
    _c, p = _pedir_ato(srv, biscoito)
    codigo, _cab, corpo = _escrever(srv, '/api/ato/confirmar', {'pedido': p['pedido'], 'resposta': 'confirmar'},
                                    cookie=biscoito)
    assert codigo == 200 and json.loads(corpo) == {'feito': True}
    assert len(chamadas) == 1
    d, dados = chamadas[0]
    assert d.meio == humano.MEIO_MEDICAO and d.origem == mb.ORIGEM_FIXTURE and d.comando == COMANDO
    assert dados == {}
    # o selo foi gasto pelo ato: o mesmo disparo nao serve de novo
    with pytest.raises(humano.ErroHumano):
        humano.conferir(d, COMANDO)
    # o pedido vale uma vez
    assert _escrever(srv, '/api/ato/confirmar', {'pedido': p['pedido'], 'resposta': 'confirmar'},
                     cookie=biscoito)[0] == 403
    assert len(chamadas) == 1


@pytest.mark.parametrize('corpo', [{'resposta': 'confirmar'}, {'pedido': 'x' * 32, 'resposta': 'confirmar'},
                                   'sem_resposta', 'resposta_outra'])
def test_confirmar_sem_pedido_valido_ou_sem_resposta_explicita_e_recusado(srv, chamadas, corpo):
    biscoito = tts._entrar(srv)
    _c, p = _pedir_ato(srv, biscoito)
    if corpo == 'sem_resposta':
        corpo = {'pedido': p['pedido']}
    elif corpo == 'resposta_outra':
        corpo = {'pedido': p['pedido'], 'resposta': 'sim'}
    assert _escrever(srv, '/api/ato/confirmar', corpo, cookie=biscoito)[0] == 403
    assert chamadas == []


def test_pedido_novo_derruba_o_anterior(srv, chamadas):
    biscoito = tts._entrar(srv)
    _c, p1 = _pedir_ato(srv, biscoito)
    _c, p2 = _pedir_ato(srv, biscoito)
    assert _escrever(srv, '/api/ato/confirmar', {'pedido': p1['pedido'], 'resposta': 'confirmar'},
                     cookie=biscoito)[0] == 403
    assert _escrever(srv, '/api/ato/confirmar', {'pedido': p2['pedido'], 'resposta': 'confirmar'},
                     cookie=biscoito)[0] == 200
    assert len(chamadas) == 1


def test_ato_desconhecido_ou_com_dados_e_recusado(srv, chamadas):
    biscoito = tts._entrar(srv)
    assert _pedir_ato(srv, biscoito, nome='aprovar')[0] == 403
    assert _pedir_ato(srv, biscoito, dados={'x': 1})[0] == 403
    assert chamadas == []


def test_ato_com_comando_que_nao_e_humano_e_recusado_na_montagem(job):
    with pytest.raises(ValueError):
        ts.ServidorTela(tts._conteudo(), pasta=job, modo_teste=True,
                        atos={'x': ts.Ato(comando='tela abrir', titulo='t', texto='t', sim='s', nao='n',
                                          executar=lambda d, x: {})})
    with pytest.raises(ValueError):
        ts.ServidorTela(tts._conteudo(), pasta=job, modo_teste=True,
                        atos={'Fora Do Padrao': ts.Ato(comando=COMANDO, titulo='t', texto='t', sim='s', nao='n',
                                                       executar=lambda d, x: {})})


# ------------------------------------------------------------------ o Disparo da tela no humano
def test_disparo_da_tela_pede_a_confirmacao_e_uma_sessao_registrada():
    sessao = humano.abrir_sessao_tela(teste=True)
    try:
        with pytest.raises(humano.ErroHumano):
            humano.exigir_tela(COMANDO, sessao, confirmado=False)
        forjada = humano.SessaoTela(chave='0' * 32, teste=True)
        with pytest.raises(humano.ErroHumano):
            humano.exigir_tela(COMANDO, forjada, confirmado=True)
        with pytest.raises(ValueError):
            humano.exigir_tela('tela abrir', sessao, confirmado=True)
        d = humano.exigir_tela(COMANDO, sessao, confirmado=True)
        assert humano.conferir(d, COMANDO) is d and d.meio == humano.MEIO_MEDICAO
    finally:
        humano.fechar_sessao_tela(sessao)
    with pytest.raises(humano.ErroHumano):
        humano.exigir_tela(COMANDO, sessao, confirmado=True)


@pytest.fixture
def ambiente_limpo(monkeypatch):
    for v in humano.VARIAVEIS_DO_CLAUDE + humano.VARIAVEIS_DO_PAINEL + tuple(humano.MARCAS_DO_PAINEL):
        monkeypatch.delenv(v, raising=False)
    from desdobra import cli
    monkeypatch.setattr(cli._Analisador, 'modo_envelope', False, raising=False)


def test_sessao_de_verdade_recusa_o_processo_com_as_marcas_do_claude(ambiente_limpo, monkeypatch, job):
    monkeypatch.setenv('CLAUDECODE', '1')
    with pytest.raises(humano.ErroHumano) as e:
        humano.abrir_sessao_tela()
    assert str(e.value) == 'processo_aberto_pelo_claude'
    with pytest.raises(humano.ErroHumano):
        ts.ServidorTela(tts._conteudo(), pasta=job)
    monkeypatch.delenv('CLAUDECODE')
    monkeypatch.setenv('TERM_PROGRAM', 'claude-desktop')
    with pytest.raises(humano.ErroHumano):
        humano.abrir_sessao_tela()


def test_sessao_de_verdade_no_ambiente_limpo_da_meio_tela(ambiente_limpo, job, chamadas):
    s = ts.ServidorTela(tts._conteudo(), pasta=job, atos=_atos(chamadas)).iniciar()
    try:
        biscoito = tts._entrar(s)
        assert _escrever(s, '/api/rascunho', _rascunho(s), cookie=biscoito)[0] == 200
        assert json.loads((job / tr.ARQUIVO).read_text(encoding='utf-8'))['origem'] == mb.ORIGEM_RASCUNHO
        _c, p = _pedir_ato(s, biscoito)
        assert _escrever(s, '/api/ato/confirmar', {'pedido': p['pedido'], 'resposta': 'confirmar'},
                         cookie=biscoito)[0] == 200
        d = chamadas[0][0]
        assert d.meio == humano.MEIO_TELA and d.origem == mb.ORIGEM_DA
        assert d.registro()['meio'] == 'tela' and 'selo' not in d.registro()
    finally:
        s.parar()


def test_exigir_do_terminal_nunca_da_meio_tela(pessoa):
    d = pessoa.exigir(COMANDO)
    assert d.meio == 'terminal' and d.origem == mb.ORIGEM_DA


# ------------------------------------------------------------------ modo de teste so em job sintetico
def test_modo_de_teste_recusa_job_com_briefing_do_da(job):
    (job / 'briefing').mkdir()
    (job / mb.ARQUIVO).write_text(json.dumps({'cabecalho': {'origem': mb.ORIGEM_DA}}), encoding='utf-8')
    with pytest.raises(ValueError):
        ts.ServidorTela(tts._conteudo(), pasta=job, modo_teste=True)


def test_modo_de_teste_recusa_job_com_rascunho_do_da(job):
    (job / 'briefing').mkdir()
    (job / tr.ARQUIVO).write_text(json.dumps({'origem': mb.ORIGEM_RASCUNHO}), encoding='utf-8')
    with pytest.raises(ValueError):
        ts.ServidorTela(tts._conteudo(), pasta=job, modo_teste=True)


@pytest.mark.parametrize('arquivo, dados', [
    # revisao do M7a: alem do briefing e do rascunho, qualquer decisao do DA ja gravada no job tira o modo de teste
    ('briefing/linkados-confirmados.json', {'linkados': [{'confirmado_por': {'meio': 'terminal', 'quando': 'x'}}]}),
    ('briefing/linkados-confirmados.json',
     {'linkados': [{'confirmado_por': {'meio': 'tela', 'quando': 'x', 'origem': 'da'}}]}),
    ('specs/confirmacoes.json', {'acoes': [{'por': 'da', 'meio': 'terminal'}]}),
    ('briefing/modo-dados.json', {'origem': 'da', 'valor': 'c'}),
    ('briefing/linkados-confirmados.json', 'nao e json'),
])
def test_modo_de_teste_recusa_job_com_decisao_do_da(job, arquivo, dados):
    arq = job / arquivo
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(dados if isinstance(dados, str) else json.dumps(dados), encoding='utf-8')
    with pytest.raises(ValueError):
        ts.ServidorTela(tts._conteudo(), pasta=job, modo_teste=True)


def test_modo_de_teste_aceita_job_so_com_decisoes_de_teste(job):
    (job / 'briefing').mkdir()
    (job / 'briefing' / 'linkados-confirmados.json').write_text(json.dumps(
        {'linkados': [{'confirmado_por': {'meio': 'medicao', 'quando': 'x', 'origem': 'fixture_de_teste'}}]}),
        encoding='utf-8')
    (job / 'briefing' / 'modo-dados.json').write_text(json.dumps({'origem': 'fixture_de_teste', 'valor': 'c'}),
                                                      encoding='utf-8')
    (job / 'specs').mkdir()
    (job / 'specs' / 'confirmacoes.json').write_text(json.dumps({'acoes': [{'por': 'fixture_de_teste'}]}),
                                                     encoding='utf-8')
    ts.ServidorTela(tts._conteudo(), pasta=job, modo_teste=True)


def test_servidor_com_escrita_pede_o_laudo(tmp_path):
    with pytest.raises(ValueError):
        ts.ServidorTela(tts._conteudo(), pasta=tmp_path, modo_teste=True)


def test_processo_de_fundo_cai_para_so_leitura_com_as_marcas_do_claude(ambiente_limpo, monkeypatch, job):
    from desdobra.tela import processo
    monkeypatch.setenv('CLAUDECODE', '1')
    assert processo.opcoes_do_servidor(job) == {}
    monkeypatch.delenv('CLAUDECODE')
    assert processo.opcoes_do_servidor(job) == {'pasta': job}


def test_varredura_do_fecho_procura_tambem_o_csrf(srv, tmp_path):
    from desdobra.tela import processo
    perfil = tmp_path / 'perfil'
    perfil.mkdir()
    (perfil / 'Sessao').write_bytes(b'x' + srv.csrf.encode('ascii') + b'y')
    assert processo.varrer_fechado(perfil, srv)['segredos'] == 1


# ------------------------------------------------------------------ gancho
@pytest.mark.parametrize('caminho', [
    'C:/jobs/kv/briefing/rascunho.json', 'C:\\jobs\\kv\\briefing\\rascunho.json',
    'C:/jobs/kv/briefing/historico/ab12.json', 'C:/jobs/kv/briefing/notas.txt',
    'C:/jobs/kv/derivacao/sub/x.json', 'C:/jobs/kv/derivacao/vertical.json', 'C:/jobs/kv/estado.json',
    'C:/jobs/kv/./briefing/../briefing/rascunho.json', 'briefing/rascunho.json', 'estado.json',
])
def test_gancho_nega_escrever_nos_arquivos_que_decidem_o_job(caminho):
    g = tts._gancho()
    for ferramenta in ('Write', 'Edit', 'MultiEdit'):
        assert g.decidir({'tool_name': ferramenta, 'tool_input': {'file_path': caminho}}) == 'deny', (ferramenta,
                                                                                                     caminho)


@pytest.mark.parametrize('caminho', [
    'C:/r/plugins/desdobra/motor/desdobra/briefing/modelo.py',
    'C:/r/plugins/desdobra/motor/desdobra/derivacao/galeria.py',
    'C:/r/plugins/desdobra/motor/desdobra/derivacao/__pycache__/galeria.cpython-314.pyc',
    'C:/r/plugins/desdobra/motor/desdobra/tela/estado.py', 'C:/r/plugins/desdobra/motor/desdobra/tela/rascunho.py',
    'C:/r/plugins/desdobra/motor/schemas/estado-1.json', 'C:/r/plugins/desdobra/motor/schemas/rascunho-tela-1.json',
    'C:/r/plugins/desdobra/testes/test_tela_escrita.py', 'C:/r/docs/estado-do-projeto.md',
    'C:/r/plugins/desdobra/skills/briefing/SKILL.md', 'C:/r/plugins/desdobra/skills/derivacao/references/x.md',
])
def test_gancho_deixa_editar_o_codigo_fonte(caminho):
    g = tts._gancho()
    assert g.decidir({'tool_name': 'Edit', 'tool_input': {'file_path': caminho}}) is None, caminho


@pytest.mark.parametrize('ferramenta', ['Bash', 'PowerShell'])
@pytest.mark.parametrize('comando', [
    'echo {} > C:/jobs/kv/briefing/rascunho.json',
    'Set-Content -Path C:\\jobs\\kv\\estado.json -Value x',
    'cp x.json C:/jobs/kv/derivacao/sub/x.json',
    'python -c "open(\'C:/jobs/kv/briefing/historico/a.json\', \'w\')"',
    'curl -X POST http://127.0.0.1:51234/api/rascunho -d {}',
    'Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/api/ato/confirmar',
    'curl -H "X-Desdobra-CSRF: x" http://localhost:8/api/ato/pedir',
])
def test_gancho_nega_escrever_pelo_terminal_e_as_rotas_de_escrita(ferramenta, comando):
    assert tts._gancho().decidir({'tool_name': ferramenta, 'tool_input': {'command': comando}}) == 'deny', comando


@pytest.mark.parametrize('ferramenta', ['Bash', 'PowerShell'])
@pytest.mark.parametrize('comando', [
    # revisao do M7a: os gravadores do M7 que nao pedem Disparo (briefing confirmado, rascunho e modo de dados)
    'python -c "from desdobra.briefing import modelo as mb, salvar; b=salvar.montar(j,c,d); mb.gravar_com_historico(j,b)"',
    'python -c "import desdobra.briefing.salvar as s"',
    'python -c "from desdobra.tela import rascunho as r; r.gravar(j, d, job_id=1, laudo_atual=2, origem=3)"',
    'python -c "from desdobra import contratos; import desdobra.tela.rascunho as r; contratos.gravar(p, d, r.ESQUEMA)"',
    'python -c "from desdobra.job import modo_dados as m; from desdobra import contratos; contratos.gravar(p, d, m.ESQUEMA)"',
    'python -c "import desdobra.job.modo_dados"',
    'python -c "from desdobra.tela import atos"',
    # revisao do M7a: os gravadores do motor por baixo (contratos.gravar, arquivos.gravar_*), as constantes de caminho
    # dos modulos e o caminho montado por partes
    'python -c "from desdobra import contratos; from desdobra.briefing import modelo as mb; '
    'contratos.gravar(Path(j)/mb.ARQUIVO, b, mb.ESQUEMA)"',
    'python -c "from desdobra import contratos; contratos.gravar(Path(j, \'briefing\', \'modo-dados.json\'), d, e)"',
    'python -c "from desdobra import contratos; contratos.gravar(Path(j)/\'briefing\'/\'rascunho.json\', d, \'r/1\')"',
    'python -c "from desdobra import arquivos; from desdobra.briefing import modelo as mb; '
    'arquivos.gravar_bytes_atomico(Path(j)/mb.ARQUIVO, x)"',
    'python -c "from desdobra import arquivos; arquivos.gravar_json_atomico(p, d)"',
    'python -c "from desdobra import job; print(job.modo_dados.ARQUIVO)"',
    'python -c "from desdobra.render import contrato as mc; import desdobra; open(Path(j)/mc.ARQUIVO_LINKADOS, \'w\')"',
    'python -c "import desdobra; p = Path(j, \'briefing\', \'x.json\'); p.write_text(t)"',
    # revisao do M7a: a fase gravada em dia no proprio processo (o ato de spec da tela) e o estado.json pelo codigo,
    # que carimbariam como em dia uma saida de fase escrita a mao (specs/formatos-do-job.json)
    'python -c "from desdobra.job import nucleo; nucleo.renovar_fase(j, \'specs\')"',
    'python -c "from desdobra.job import nucleo as n; e = n.ler_estado(j); n.gravar_estado(j, e)"',
])
def test_gancho_nega_os_gravadores_do_m7_pelo_codigo(ferramenta, comando):
    assert tts._gancho().decidir({'tool_name': ferramenta, 'tool_input': {'command': comando}}) == 'deny', comando


@pytest.mark.parametrize('ferramenta', ['Bash', 'PowerShell'])
@pytest.mark.parametrize('comando', [
    'type C:/jobs/kv/estado.json',
    'python -m pytest testes/test_tela_escrita.py -q',
    'git diff plugins/desdobra/motor/desdobra/briefing/modelo.py',
])
def test_gancho_deixa_ler(ferramenta, comando):
    assert tts._gancho().decidir({'tool_name': ferramenta, 'tool_input': {'command': comando}}) is None, comando


def test_gancho_nega_o_cabecalho_csrf_no_navegador_do_claude():
    g = tts._gancho()
    ev = {'tool_name': 'mcp__Claude_Browser__javascript_tool',
          'tool_input': {'text': 'fetch("/api/rascunho", {method: "POST", headers: {"X-Desdobra-CSRF": t}})'}}
    assert g.decidir(ev) == 'deny'


# ------------------------------------------------------------------ no Chromium sem janela
def _ler_rascunho(job):
    arq = job / tr.ARQUIVO
    return json.loads(arq.read_text(encoding='utf-8')) if arq.exists() else None


def test_rascunho_espera_e_confirmacao_no_chromium(job_galeria):  # noqa: F811
    from playwright.sync_api import sync_playwright

    import test_tela_galeria as tg
    import test_tela_palco as tp
    from desdobra.chromium import navegador
    from desdobra.tela import estado as te
    c = te.montar(job_galeria)
    chamadas = []
    espera = float(limites.valor('tela.rascunho_espera_ms')) / 1000
    navegador.apontar_playwright()
    with ts.ServidorTela(c, pasta=job_galeria, modo_teste=True, atos=_atos(chamadas)) as srv, \
            sync_playwright() as pw:
        nav, pg = tp._pagina_da_tela(pw, srv, 2048, 720)  # numero-neutro: a tela do Duda (decisao 157)
        try:
            assert pg.evaluate('() => document.querySelector("meta[name=dsd-csrf]").content') == srv.csrf
            tg._abrir(pg, c['estado'], 'vertical')
            familia = pg.evaluate('() => document.querySelector("#composicoes [aria-selected=true]").dataset.grupo')
            vs = c['previas']['vertical']['galeria']['variantes']
            # a primeira versao vem do motor sem clique: nada e gravado
            time.sleep(espera * 2)  # numero-neutro: o dobro da espera
            assert _ler_rascunho(job_galeria) is None and srv.contagem['rascunho'] == 0
            # tres cliques seguidos: uma gravacao so, com a ultima escolha
            for n in (2, 3, 2):
                pg.evaluate('n => document.querySelector("#variantes [role=tab]:nth-child(" + n + ")").click()', n)
            tp._esperar(pg, '() => document.documentElement.dataset.rascunho === "salvo" ? "1" : ""')
            time.sleep(espera * 2)  # numero-neutro: o dobro da espera
            assert srv.contagem['rascunho'] == 1
            r = _ler_rascunho(job_galeria)
            assert r['familias'][familia]['versao'] == vs[1]['id'] and r['origem'] == mb.ORIGEM_FIXTURE
            assert 'salvo' in pg.evaluate('() => document.getElementById("selo").textContent').lower()
            # reabrir a tela: a escolha volta
            pg.reload(wait_until='load')
            tp._esperar(pg, tp.JS_PRONTO)
            pg.evaluate('() => document.querySelector("#passos [data-passo=pecas]").click()')
            tp._esperar(pg, '() => document.getElementById("palco").dataset.pronto || ""')
            tg._abrir(pg, c['estado'], 'vertical')
            assert tg._variante_no_palco(pg) == vs[1]['id']
            # a confirmacao na janela: nenhuma opcao marcada, Cancelar nao faz nada
            pg.evaluate('''() => { const b = document.createElement("button"); b.type = "button";
                b.id = "ato-teste"; b.dataset.ato = "teste"; b.textContent = "Teste"; document.body.appendChild(b); }''')
            pg.evaluate('() => document.getElementById("ato-teste").click()')
            tp._esperar(pg, '() => document.getElementById("confirmacao").open ? "1" : ""')
            dialogo = pg.evaluate('''() => { const d = document.getElementById("confirmacao");
                return [d.querySelector("h2").textContent, d.querySelector(".confirmacao-texto").textContent,
                        Array.from(d.querySelectorAll("button")).map(b => b.textContent),
                        d.contains(document.activeElement) && document.activeElement.tagName,
                        d.querySelectorAll("[autofocus], input:checked, [aria-checked=true]").length]; }''')
            assert dialogo[0] == 'Confirmar o teste' and dialogo[1] == 'Este é um ato de teste.'
            assert sorted(dialogo[2]) == ['Cancelar', 'Confirmar']
            assert dialogo[3] != 'BUTTON' and dialogo[4] == 0, dialogo
            pg.keyboard.press('Enter')  # Enter sem opcao em foco nao confirma
            assert pg.evaluate('() => document.getElementById("confirmacao").open')
            pg.keyboard.press('Escape')
            tp._esperar(pg, '() => document.getElementById("confirmacao").open ? "" : "1"')
            time.sleep(espera)
            assert chamadas == [] and srv.contagem['ato_cancelar'] == 1
            assert pg.evaluate('() => document.documentElement.dataset.estadoAto') == 'cancelado'
            # de novo, agora confirmando
            pg.evaluate('() => document.getElementById("ato-teste").click()')
            tp._esperar(pg, '() => document.getElementById("confirmacao").open ? "1" : ""')
            pg.evaluate('''() => Array.from(document.querySelectorAll("#confirmacao button"))
                .find(b => b.textContent === "Confirmar").click()''')
            tp._esperar(pg, '() => document.getElementById("confirmacao").open ? "" : "1"')
            tp._esperar(pg, '() => document.documentElement.dataset.estadoAto === "feito" ? "1" : ""')
            assert len(chamadas) == 1 and chamadas[0][0].meio == humano.MEIO_MEDICAO
            assert 'conseguiu' not in pg.evaluate('() => document.getElementById("selo").textContent')
            assert pg.evaluate('() => document.querySelectorAll("form, [onerror]").length') == 0
        finally:
            nav.close()
        contagem = dict(srv.contagem)
    assert contagem['proibido'] == 0 and contagem['sem_cookie'] == 0 and contagem['csrf_recusado'] == 0
