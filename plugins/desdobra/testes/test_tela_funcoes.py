# -*- coding: utf-8 -*-
"""M7a, fatia 3: o passo 2 da tela, "Funcoes", e o passo "Design system", com as escolhas do DA no rascunho.

Criterios de pronto cobertos aqui (decisoes-v1.md, 10, rotular por grupo de 29/10, 161, 162 e 167; proposta do M7,
secao 4, fatia a6a; secao 5, criterio 9):
  - nenhum campo tem valor inicial: as opcoes de funcao, regra de escala, ancora e decisao das cobertas saem do esquema
    briefing/1, e o esquema do rascunho aceita exatamente as mesmas; com o rascunho vazio, tudo falta;
  - heranca do motor: a funcao do grupo passa para as camadas de dentro, a da camada vale sobre a do grupo, a camada
    coberta no KV nao herda e pede a decisao do DA (aceitar ou inverter a sugestao da regra da decisao 10);
  - o Design system pede regra e ancora por funcao usada com geometria, e por elemento no indeterminado;
  - indeterminado sem observacao: recusado pelo motor (o rascunho nao grava, a conferencia do briefing recusa) e pela
    tela (a escolha nao vai ao rascunho ate a observacao);
  - o rascunho grava e devolve as escolhas do passo 2; camada que o laudo nao tem e recusada;
  - a reducao da rotulagem por grupo (112 para 82 decisoes no gabarito; taxonomia-funcoes.md) refeita em dados
    sinteticos com a mesma forma dos tres KVs (plano, agrupado por elemento, grupos misturados): 8, 16 e 58 decisoes
    para 8, 43 e 61 camadas, e as funcoes resolvidas pela heranca do motor iguais as do rotulo camada a camada;
  - no Chromium sem janela: nada marcado no comeco, o grupo passa a funcao e a camada troca, o indeterminado pede a
    observacao, o Design system grava regra e ancora e marca os elementos no KV, o "Faltam N" acompanha e leva ao item,
    a escolha volta ao recarregar, e a rotulagem minima refeita por cliques bate com a do motor.
Tudo sintetico.
"""
import json

import pytest

import test_tela_escrita as tte
import test_tela_servidor as tts
from desdobra import contratos
from desdobra.briefing import modelo as mb
from desdobra.derivacao import escala
from desdobra.tela import funcoes as tf
from desdobra.tela import rascunho as tr
from desdobra.tela import servidor as ts

PROIBIDOS = ('—', '–', 'grupo', 'Grupo', 'decisão 10', '_')


# ------------------------------------------------------------------ laudo sintetico
def _camada(lid, nome, tipo='pixel', pai=None, caminho=(), coberta=None):
    c = {'identidade': {'layer_id': lid}, 'nome': nome, 'tipo': tipo, 'pai_id': pai, 'caminho_ids': list(caminho),
         'aparencia': {'visivel_efetiva': True}, 'geometria': {'caixa': [0, 0, 10, 10]}}
    if coberta is not None:
        c['geometria']['coberta_no_kv'] = {'coberta': True, 'sugestao_da_regra': {'funcao': coberta}}
    return c


def _laudo(camadas):
    return {'documento': {'largura': 100, 'altura': 100, 'quadros': []}, 'camadas': camadas}  # numero-neutro: medida sintetica


def laudo_pequeno():
    """fundo; grupo do titulo com texto, linha e uma camada coberta (sugestao estrutura); logo; texto solto."""
    return _laudo([_camada(1, 'fundo'), _camada(10, 'titulo', 'grupo'),
                   _camada(11, 'texto do titulo', 'texto', 10, [10]), _camada(12, 'linha', 'pixel', 10, [10]),
                   _camada(13, 'coberta', 'pixel', 10, [10], coberta='estrutura'), _camada(20, 'logo'),
                   _camada(40, 'apoio', 'texto')])


def _f(funcao, obs=None):
    return {'funcao': funcao, 'observacao': obs}


# ------------------------------------------------------------------ opcoes do esquema, sem valor inicial
def test_opcoes_saem_do_esquema_do_briefing():
    esq = contratos.carregar_esquema('briefing/1')
    o = tf.opcoes()
    assert [f['id'] for f in o['funcoes']] == esq['$defs']['funcao']['enum']
    assert o['regras'] == esq['$defs']['regra']['enum'] and set(o['regras']) == set(escala.REGRAS)
    assert o['ancora_x'] == ['esquerda', 'centro', 'direita'] and o['ancora_y'] == ['topo', 'meio', 'base']
    assert o['cobertas'] == ['aceita', 'inverte']
    sem = {f['id'] for f in o['funcoes'] if not f['geometria']}
    assert sem == set(mb.SEM_GEOMETRIA)


def test_esquema_do_rascunho_aceita_exatamente_as_opcoes_do_briefing():
    o = tf.opcoes()
    r = contratos.carregar_esquema(tr.ESQUEMA)
    defs = r['$defs']
    assert defs['funcao']['enum'] == [f['id'] for f in o['funcoes']]
    assert defs['regra']['enum'] == o['regras']
    assert defs['ancora_x']['enum'] == o['ancora_x'] and defs['ancora_y']['enum'] == o['ancora_y']
    assert r['properties']['cobertas']['additionalProperties']['enum'] == o['cobertas']
    # nenhum campo do passo 2 tem valor padrao no esquema
    assert 'default' not in json.dumps(r)


def test_rascunho_vazio_nada_tem_valor_e_tudo_falta():
    laudo = laudo_pequeno()
    p = tf.pendencias(laudo, {})
    assert p == [{'tipo': 'funcao', 'camada': 40}, {'tipo': 'funcao', 'camada': 20},
                 {'tipo': 'coberta', 'camada': 13}, {'tipo': 'funcao', 'camada': 12},
                 {'tipo': 'funcao', 'camada': 11}, {'tipo': 'funcao', 'camada': 1}]
    nos = tf.nos(laudo)
    assert [n['camada'] for n in nos] == [40, 20, 10, 13, 12, 11, 1]
    assert {n['camada'] for n in nos if not n['folha']} == {10}
    assert next(n for n in nos if n['camada'] == 13)['coberta'] == {'sugestao': 'estrutura'}
    assert all(set(n) == {'camada', 'nome', 'tipo', 'pai', 'nivel', 'folha', 'coberta'} for n in nos)


# ------------------------------------------------------------------ heranca
def test_funcao_do_grupo_passa_para_dentro_e_a_camada_troca():
    laudo = laudo_pequeno()
    dados = {'funcoes': {'10': _f('titulo'), '12': _f('grafismo')}}
    res, _e = tf.resolver(laudo, dados)
    assert res[11]['funcao'] == 'titulo' and res[11]['por'] == 'grupo' and res[11]['raiz'] == 10
    assert res[12]['funcao'] == 'grafismo' and res[12]['por'] == 'camada'
    assert 13 not in res  # a coberta nao herda do grupo
    tipos = [(x['tipo'], x.get('camada')) for x in tf.pendencias(laudo, dados) if x['tipo'] in ('funcao', 'coberta')]
    assert tipos == [('funcao', 40), ('funcao', 20), ('coberta', 13), ('funcao', 1)]


@pytest.mark.parametrize('decisao, funcao', [('aceita', 'estrutura'), ('inverte', 'fora_da_peca')])
def test_coberta_aceita_ou_inverte_a_sugestao(decisao, funcao):
    laudo = laudo_pequeno()
    res, _e = tf.resolver(laudo, {'cobertas': {'13': decisao}})
    assert res[13]['funcao'] == funcao and res[13]['por'] == 'decisao_10'


def test_design_pede_regra_e_ancora_por_funcao_e_por_elemento_indeterminado():
    laudo = laudo_pequeno()
    dados = {'funcoes': {'1': _f('fundo'), '10': _f('titulo'), '20': _f('indeterminado', 'selo da campanha'),
                         '40': _f('fora_da_peca')},
             'cobertas': {'13': 'aceita'}}
    faltam = [x for x in tf.pendencias(laudo, dados)]
    assert faltam == [{'tipo': 'regra', 'camada': 20}, {'tipo': 'ancora', 'camada': 20},
                      {'tipo': 'regra', 'funcao': 'titulo'}, {'tipo': 'ancora', 'funcao': 'titulo'},
                      {'tipo': 'regra', 'funcao': 'fundo'}, {'tipo': 'ancora', 'funcao': 'fundo'}]
    dados['design'] = {'titulo': {'regra': 'largura', 'x': 'esquerda', 'y': 'topo'},
                       'fundo': {'regra': 'cover', 'x': 'centro', 'y': None}}
    dados['design_camadas'] = {'20': {'regra': 'constante', 'x': 'direita', 'y': 'base'}}
    assert tf.pendencias(laudo, dados) == [{'tipo': 'ancora', 'funcao': 'fundo'}]
    b = tf.briefing_parcial(dados)
    assert mb.regras_por_funcao(b) == {'titulo': 'largura', 'fundo': 'cover'}
    assert mb.regras_indeterminado(b) == {20: 'constante'}
    assert mb.ancora_do_elemento(b, 20, 'indeterminado') == ('direita', 'base')
    assert mb.ancora_do_elemento(b, 10, 'titulo') == ('esquerda', 'topo')


# ------------------------------------------------------------------ indeterminado pede observacao
@pytest.mark.parametrize('obs', [None, '', '   '])
def test_indeterminado_sem_observacao_e_recusado_pelo_motor(obs):
    laudo = laudo_pequeno()
    dados = {'funcoes': {'20': _f('indeterminado', obs)}}
    assert tf.conferir(dados, laudo) == ['indeterminado_sem_observacao']
    # e a conferencia do briefing tambem recusa
    b = tf.briefing_parcial(dados)
    _r, erros, _i = mb.resolver(laudo, b)
    assert 'indeterminado_sem_observacao' in [e['codigo'] for e in erros]


def test_conferir_recusa_camada_que_o_laudo_nao_tem_e_coberta_sem_cobertura():
    laudo = laudo_pequeno()
    assert tf.conferir({'funcoes': {'999': _f('fundo')}}, laudo) == ['camada_inexistente']
    assert tf.conferir({'cobertas': {'11': 'aceita'}}, laudo) == ['coberta_sem_cobertura']
    assert tf.conferir({'funcoes': {'20': _f('indeterminado', 'explicado')}, 'cobertas': {'13': 'inverte'}},
                       laudo) == []


# ------------------------------------------------------------------ o rascunho grava o passo 2
@pytest.fixture
def job_funcoes(tmp_path):
    j = tmp_path / 'job'
    (j / 'laudo').mkdir(parents=True)
    (j / 'laudo' / 'laudo.json').write_text(json.dumps(laudo_pequeno()), encoding='utf-8')
    return j


@pytest.fixture
def srv_funcoes(job_funcoes):
    s = ts.ServidorTela(tts._conteudo(), pasta=job_funcoes, modo_teste=True).iniciar()
    yield s
    s.parar()


def _passo2(s, **campos):
    d = tte._rascunho(s)
    d.update(campos)
    return d


def test_rascunho_grava_e_devolve_as_escolhas_do_passo_2(srv_funcoes, job_funcoes):
    biscoito = tts._entrar(srv_funcoes)
    d = _passo2(srv_funcoes, funcoes={'10': _f('titulo'), '20': _f('indeterminado', 'selo da campanha')},
                cobertas={'13': 'inverte'}, design={'titulo': {'regra': 'largura', 'x': None, 'y': None}},
                design_camadas={'20': {'regra': None, 'x': 'direita', 'y': 'base'}})
    assert tte._escrever(srv_funcoes, '/api/rascunho', d, cookie=biscoito)[0] == 200
    gravado = contratos.ler(job_funcoes / tr.ARQUIVO, tr.ESQUEMA)
    for k in tf.CHAVES_DO_PASSO:
        assert gravado[k] == d[k]
    lido = json.loads(tts._pedir(srv_funcoes, '/api/rascunho', cookie=biscoito)[2])['rascunho']
    assert lido['funcoes'] == d['funcoes'] and lido['cobertas'] == d['cobertas']
    # o rascunho antigo, so com as familias, continua valendo
    assert tte._escrever(srv_funcoes, '/api/rascunho', tte._rascunho(srv_funcoes), cookie=biscoito)[0] == 200


@pytest.mark.parametrize('campos', [
    {'funcoes': {'20': _f('indeterminado')}},
    {'funcoes': {'20': _f('indeterminado', '  ')}},
    {'funcoes': {'999': _f('fundo')}},
    {'funcoes': {'20': _f('logotipo')}},
    {'funcoes': {'vinte': _f('fundo')}},
    {'funcoes': {'20': {'funcao': None, 'observacao': None}}},
    {'cobertas': {'13': 'talvez'}},
    {'cobertas': {'11': 'aceita'}},
    {'design': {'titulo': {'regra': 'width', 'x': None, 'y': None}}},
    {'design': {'titulo': {'regra': 'largura', 'x': 'topo', 'y': None}}},
    {'design': {'logotipo': {'regra': 'largura', 'x': None, 'y': None}}},
    {'design_camadas': {'999': {'regra': 'largura', 'x': None, 'y': None}}},
    {'outra_coisa': {}},
])
def test_rascunho_do_passo_2_fora_da_regra_e_recusado_e_nada_e_gravado(srv_funcoes, job_funcoes, campos):
    biscoito = tts._entrar(srv_funcoes)
    codigo, _c, resto = tte._escrever(srv_funcoes, '/api/rascunho', _passo2(srv_funcoes, **campos), cookie=biscoito)
    assert codigo == 403 and resto == b''
    assert not (job_funcoes / tr.ARQUIVO).exists()


def test_rascunho_do_passo_2_com_laudo_ilegivel_e_recusado(tmp_path):
    j = tmp_path / 'job'
    (j / 'laudo').mkdir(parents=True)
    (j / 'laudo' / 'laudo.json').write_text('{"laudo": "sintetico"}', encoding='utf-8')
    with ts.ServidorTela(tts._conteudo(), pasta=j, modo_teste=True) as s:
        biscoito = tts._entrar(s)
        assert tte._escrever(s, '/api/rascunho', _passo2(s, funcoes={'1': _f('fundo')}), cookie=biscoito)[0] == 403
        assert tte._escrever(s, '/api/rascunho', tte._rascunho(s), cookie=biscoito)[0] == 200


# ------------------------------------------------------------------ 112 para 82, em dados sinteticos
FUNCOES_CICLO = ('titulo', 'texto_de_apoio', 'cta', 'imagem', 'grafismo', 'logo_principal', 'selo', 'texto_legal')


def _kv_plano():
    """8 camadas soltas, uma funcao cada (a forma do KV sem grupos)."""
    fs = ('fundo', 'imagem', 'titulo', 'texto_de_apoio', 'cta', 'logo_principal', 'texto_legal', 'selo')
    camadas = [_camada(100 + k, 'c%d' % k) for k in range(len(fs))]
    return _laudo(camadas), {100 + k: f for k, f in enumerate(fs)}


def _kv_por_elemento():
    """43 camadas: 12 grupos de 3 camadas da mesma funcao, um grupo de 4 (2 camadas e um subgrupo de 2) e 3 soltas
    (a forma do KV organizado em grupos por elemento)."""
    camadas, alvo, lid = [], {}, 200
    for g in range(12):
        gid, lid = lid, lid + 1
        camadas.append(_camada(gid, 'g%d' % g, 'grupo'))
        for _k in range(3):
            camadas.append(_camada(lid, 'c%d' % lid, 'pixel', gid, [gid]))
            alvo[lid], lid = FUNCOES_CICLO[g % len(FUNCOES_CICLO)], lid + 1
    gid, sub = lid, lid + 1
    camadas += [_camada(gid, 'g-quatro', 'grupo'), _camada(sub, 'sub', 'grupo', gid, [gid])]
    lid += 2
    for pai, caminho in ((gid, [gid]), (gid, [gid]), (sub, [gid, sub]), (sub, [gid, sub])):
        camadas.append(_camada(lid, 'c%d' % lid, 'pixel', pai, caminho))
        alvo[lid], lid = 'fundo', lid + 1
    for f in ('cta', 'selo', 'texto_legal'):
        camadas.append(_camada(lid, 'c%d' % lid))
        alvo[lid], lid = f, lid + 1
    return _laudo(camadas), alvo


def _kv_misturado():
    """61 camadas: 3 grupos de 3 camadas com uma funcao diferente em cada (um dentro de outro grupo) e 52 soltas
    (a forma do KV em que os grupos misturam funcoes)."""
    camadas, alvo, lid = [], {}, 400
    externo = lid
    camadas.append(_camada(externo, 'externo', 'grupo'))
    lid += 1
    for g in range(3):
        gid, lid = lid, lid + 1
        caminho = [externo, gid] if g == 0 else [gid]
        camadas.append(_camada(gid, 'g%d' % g, 'grupo', externo if g == 0 else None, caminho[:-1]))
        for f in ('titulo', 'titulo', 'grafismo'):
            camadas.append(_camada(lid, 'c%d' % lid, 'pixel', gid, caminho))
            alvo[lid], lid = f, lid + 1
    for k in range(52):
        camadas.append(_camada(lid, 'c%d' % lid))
        alvo[lid], lid = FUNCOES_CICLO[k % len(FUNCOES_CICLO)], lid + 1
    return _laudo(camadas), alvo


@pytest.mark.parametrize('montar, camadas, decisoes', [(_kv_plano, 8, 8), (_kv_por_elemento, 43, 16),
                                                       (_kv_misturado, 61, 58)])
def test_rotulagem_por_grupo_reduz_as_decisoes_e_resolve_igual(montar, camadas, decisoes):
    laudo, alvo = montar()
    assert len(alvo) == camadas
    escolhas = tf.decisoes_minimas(laudo, alvo)
    assert len(escolhas) == decisoes
    dados = {'funcoes': tf.rascunho_de_escolhas(escolhas)}
    assert tf.conferir(dados, laudo) == []
    res, erros = tf.resolver(laudo, dados)
    assert erros == []
    assert {k: v['funcao'] for k, v in res.items()} == alvo
    assert [p for p in tf.pendencias(laudo, dados) if p['tipo'] in ('funcao', 'coberta')] == []


def test_rotulagem_dos_tres_kvs_soma_82_de_112():
    total_c = total_d = 0
    for montar in (_kv_plano, _kv_por_elemento, _kv_misturado):
        laudo, alvo = montar()
        total_c += len(alvo)
        total_d += len(tf.decisoes_minimas(laudo, alvo))
    assert (total_c, total_d) == (112, 82)  # numero-neutro: a conta do gabarito, taxonomia-funcoes.md


def test_decisoes_minimas_contam_a_coberta_sempre():
    laudo = laudo_pequeno()
    alvo = {1: 'fundo', 11: 'titulo', 12: 'titulo', 13: 'titulo', 20: 'logo_principal', 40: 'texto_de_apoio'}
    escolhas = tf.decisoes_minimas(laudo, alvo)
    assert escolhas == {1: 'fundo', 10: 'titulo', 13: 'titulo', 20: 'logo_principal', 40: 'texto_de_apoio'}
    res, _e = tf.resolver(laudo, {'funcoes': tf.rascunho_de_escolhas(escolhas)})
    assert {k: v['funcao'] for k, v in res.items()} == alvo


# ------------------------------------------------------------------ estado da tela e Chromium sem janela
from test_tela_palco import job_palco  # noqa: E402,F401 - fixture do job sintetico com grupo, fonte e nomes hostis


def test_estado_da_tela_leva_os_nos_e_as_opcoes_sem_valor(job_palco):  # noqa: F811
    from desdobra.tela import estado as te
    c = te.montar(job_palco)
    d = c['estado']['funcoes']['decisoes']
    laudo = contratos.ler(job_palco / 'laudo' / 'laudo.json', 'laudo/1')
    assert d['nos'] == tf.nos(laudo, d['quadro']) and d['opcoes'] == tf.opcoes()
    assert not any('funcao' in n or 'valor' in n for n in d['nos'])
    assert not (job_palco / tr.ARQUIVO).exists()


SALVO = '() => document.documentElement.dataset.rascunho === "salvo" ? "1" : ""'
PARADO = ('() => ["pendente", "salvando"].includes(document.documentElement.dataset.rascunho) ? "" : "1"')
ACHAR_IR = ('() => Array.from(document.querySelectorAll("#itens-faltam li"))'
            '.find(li => li.textContent.includes("regra de escala")).querySelector("button").click()')


def _esperar(pg, expressao, teto_s=60):
    import test_tela_palco as tp
    tp._esperar(pg, expressao, teto_s=teto_s)


def _clicar(pg, seletor):
    pg.evaluate('(s) => { const b = document.querySelector(s); if (!b) throw new Error(s); b.click(); }', seletor)


def _faltam(pg):
    return pg.evaluate('() => document.querySelectorAll("#itens-faltam li:not(.vazio)").length')


def _pressionados(pg, seletor):
    return pg.evaluate('(s) => document.querySelectorAll(s + " [aria-pressed=true]").length', seletor)


def _salvo(pg, job):
    """Espera a gravacao e devolve o rascunho do disco."""
    _esperar(pg, PARADO)
    _esperar(pg, SALVO)
    return contratos.ler(job / tr.ARQUIVO, tr.ESQUEMA)


def test_passo_2_e_design_system_no_chromium(job_palco):  # noqa: F811
    from playwright.sync_api import sync_playwright

    import test_tela_palco as tp
    from desdobra.chromium import navegador
    from desdobra.tela import estado as te
    laudo = contratos.ler(job_palco / 'laudo' / 'laudo.json', 'laudo/1')
    ids = {c['nome']: c['identidade']['layer_id'] for c in laudo['camadas']}
    alvo = {k: v['funcao'] for k, v in mb.resolver(laudo, mb.ler(job_palco))[0].items()}
    escolhas = tf.decisoes_minimas(laudo, alvo)
    assert ids[tp.NOME_FORM] in escolhas and ids[tp.NOME_IMG] not in escolhas  # o grupo leva o titulo para dentro
    c = te.montar(job_palco)
    servidor_faltam = len(c['estado']['faltam'])
    navegador.apontar_playwright()
    try:
        with ts.ServidorTela(c, pasta=job_palco, modo_teste=True) as srv, sync_playwright() as pw:
            nav = pw.chromium.launch(headless=True, args=list(navegador.ARGUMENTOS))
            pg = nav.new_context(viewport={'width': 2048, 'height': 720}).new_page()  # numero-neutro: a tela do Duda
            try:
                try:
                    pg.goto(srv.url_entrada, wait_until='commit')
                except Exception:  # noqa: BLE001 - o 204 nao completa a navegacao
                    pass
                pg.goto(srv.url_pagina, wait_until='load')
                _esperar(pg, tp.JS_PRONTO)
                # nada marcado no comeco, e tudo falta
                _clicar(pg, '#passos [data-passo=funcoes]')
                _clicar(pg, '#arvore button[data-camada="%d"]' % ids[tp.NOME_FORM])
                assert _pressionados(pg, '#passo-funcoes') == 0 and _pressionados(pg, '#passo-design') == 0
                assert pg.evaluate('() => document.querySelectorAll("#detalhe [data-funcao]").length') == \
                    len(tf.opcoes()['funcoes'])
                assert _faltam(pg) == servidor_faltam + len(tf.pendencias(laudo, {}))
                texto = pg.evaluate('() => document.getElementById("passo-funcoes").innerText')
                assert not any(x in texto for x in ('—', '–', 'grupo', 'Grupo')), texto
                assert tp.NOME_FORM in texto and tp.NOME_IMG in texto
                assert pg.evaluate('() => document.querySelectorAll("form, b, [onerror]").length') == 0
                aviso = '() => document.getElementById("aviso-passo-2").hidden'
                assert pg.evaluate(aviso) is True
                # a rotulagem minima do motor, refeita por cliques: uma escolha de funcao por decisao
                for lid, f in escolhas.items():
                    _clicar(pg, '#arvore button[data-camada="%d"]' % lid)
                    _clicar(pg, '#detalhe button[data-funcao="%s"]' % f)
                r = _salvo(pg, job_palco)
                # revisao do M7a: o passo 3 segue montado com o passo 2 de antes enquanto o novo nao fecha, e diz isso
                assert pg.evaluate(aviso) is False
                assert 'estiverem completos' in pg.evaluate(
                    '() => document.getElementById("aviso-passo-2").textContent')
                assert len(r['funcoes']) == len(escolhas)
                assert {k: v['funcao'] for k, v in tf.resolver(laudo, r)[0].items()} == alvo
                assert r['origem'] == 'fixture_de_teste'
                # a camada de dentro mostra a heranca e troca so ela
                filho = '#arvore button[data-camada="%d"]' % ids[tp.NOME_IMG]
                assert 'da pasta' in pg.evaluate('(s) => document.querySelector(s).innerText', filho)
                _clicar(pg, filho)
                _clicar(pg, '#detalhe button[data-funcao="cta"]')
                r = _salvo(pg, job_palco)
                res = tf.resolver(laudo, r)[0]
                assert res[ids[tp.NOME_IMG]]['funcao'] == 'cta' and res[ids['linha-sintetica']]['funcao'] == 'titulo'
                _clicar(pg, '#detalhe button.tirar')
                r = _salvo(pg, job_palco)
                assert str(ids[tp.NOME_IMG]) not in r['funcoes']
                # indeterminado sem observacao nao vai ao rascunho
                q = ids['quadrado-sintetico']
                _clicar(pg, '#arvore button[data-camada="%d"]' % q)
                _clicar(pg, '#detalhe button[data-funcao="indeterminado"]')
                r = _salvo(pg, job_palco)
                assert str(q) not in r['funcoes']
                assert not pg.evaluate('() => document.getElementById("observacao-erro").hidden')
                assert pg.evaluate('() => document.activeElement.id') == 'observacao'
                pg.keyboard.type('selo da campanha')
                r = _salvo(pg, job_palco)
                assert r['funcoes'][str(q)] == {'funcao': 'indeterminado', 'observacao': 'selo da campanha'}
                assert pg.evaluate('() => document.getElementById("observacao-erro").hidden')
                _clicar(pg, '#detalhe button[data-funcao="logo_principal"]')
                r = _salvo(pg, job_palco)
                assert r['funcoes'][str(q)] == {'funcao': 'logo_principal', 'observacao': None}
                # o Design system: regra e ancora por funcao, marcadas no KV
                antes = _faltam(pg)
                _clicar(pg, '#passos [data-passo=design]')
                vistas = [p for p in tf.pendencias(laudo, r) if p['tipo'] == 'regra']
                assert pg.evaluate('() => document.querySelectorAll("#resumo-design .funcao-ds").length') == len(vistas)
                assert _pressionados(pg, '#passo-design') == 1  # so a funcao aberta, nenhuma regra nem ancora
                _esperar(pg, '() => Number(document.getElementById("palco-ds").dataset.marcadas || 0) > 0 ? "1" : ""')
                primeira = '#resumo-design .funcao-ds:first-of-type'
                chave = pg.evaluate('(s) => document.querySelector(s).dataset.chave', primeira)
                _clicar(pg, primeira + ' button[data-regra="largura"]')
                _clicar(pg, primeira + ' button[data-x="esquerda"][data-y="topo"]')
                r = _salvo(pg, job_palco)
                assert r['design'][chave[1:]] == {'regra': 'largura', 'x': 'esquerda', 'y': 'topo'}
                assert _faltam(pg) == antes - 2
                assert pg.evaluate('() => document.getElementById("palco-ds").dataset.ancoras') != '0'
                assert _pressionados(pg, primeira) == 3
                texto = pg.evaluate('() => document.getElementById("passo-design").innerText')
                assert not any(x in texto for x in PROIBIDOS), texto
                # o "Faltam N" leva ao item
                _clicar(pg, '#faltam')
                pg.evaluate(ACHAR_IR)
                assert not pg.evaluate('() => document.getElementById("passo-design").hidden')
                assert pg.evaluate('() => document.activeElement.dataset.topo') == '1'
                # tudo volta ao recarregar, e o que falta na tela e o que o motor diz
                pg.reload(wait_until='load')
                _esperar(pg, tp.JS_PRONTO)
                assert _faltam(pg) == servidor_faltam + len(tf.pendencias(laudo, r))
                _clicar(pg, '#passos [data-passo=design]')
                assert _pressionados(pg, '#resumo-design [data-chave="%s"]' % chave) == 3
                _clicar(pg, '#passos [data-passo=funcoes]')
                _clicar(pg, '#arvore button[data-camada="%d"]' % ids[tp.NOME_FORM])
                assert pg.evaluate('() => document.querySelector("#detalhe [aria-pressed=true]").dataset.funcao') \
                    == 'titulo'
                _esperar(pg, '() => Number(document.getElementById("palco-kv").dataset.marcadas || 0) > 0 ? "1" : ""')
            finally:
                nav.close()
            assert srv.contagem['csrf_recusado'] == 0 and srv.contagem['dado_recusado'] == 0
    finally:
        (job_palco / tr.ARQUIVO).unlink(missing_ok=True)
