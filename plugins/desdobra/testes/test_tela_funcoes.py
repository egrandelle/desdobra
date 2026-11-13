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


# ------------------------------------------------------------------ M7c, S4: a sugestao do Claude na tela, sem gravar
# decisoes-v1.md, 162 e 190 (Q4): a tela mostra a sugestao e a alternativa ao lado da funcao, com a fonte; so o clique
# do DA em "Usar" poe a funcao no rascunho. A rota leve /api/sugestoes leva o sha256 do arquivo validado; quando ele
# muda, a pagina avisa e espera o "Mostrar". No modo c, nada aparece.
import hashlib  # noqa: E402

import test_sugestao_importar as tsi  # noqa: E402
from conftest import RAIZ_PLUGIN, escolher_modo_do_da  # noqa: E402
from desdobra.sugestao import importar as si  # noqa: E402
from desdobra.sugestao import pacote as sp  # noqa: E402

SEM_SUGESTAO = {'modo': 'c', 'sha256': None, 'sugestoes': []}


def _job_com_sugestoes(tmp_path, modo='a', itens=None):
    job = tsi._job(tmp_path, modo=modo)
    tsi._escrever(job, tsi._sugestoes(job, itens or tsi.VALIDAS))
    assert si.importar(job)['gravou']
    return job


def _sha_validadas(job):
    return hashlib.sha256(job.joinpath(*tsi.ARQ_VALIDADAS).read_bytes()).hexdigest()


@pytest.mark.parametrize('modo', ['a', 'b'])
def test_sugestoes_na_tela_trazem_so_ids_e_funcoes_do_arquivo_validado(tmp_path, modo):
    job = _job_com_sugestoes(tmp_path, modo)
    s = tf.sugestoes_na_tela(job)
    assert set(s) == {'modo', 'sha256', 'sugestoes'}
    assert s['modo'] == modo and s['sha256'] == _sha_validadas(job)
    assert s['sugestoes'] == sorted(tsi.VALIDAS, key=lambda x: x['layer_id'])
    texto = json.dumps(s, ensure_ascii=False)
    assert tsi.OFERTA not in texto and tsi.NOME_GRUPO not in texto
    # ler a sugestao nunca grava nada: nem rascunho, nem briefing
    assert not (job / tr.ARQUIVO).exists() and not (job / mb.ARQUIVO).exists()


def test_sem_sugestao_na_tela_quando_o_modo_cai_para_c(tmp_path):
    job = _job_com_sugestoes(tmp_path)
    # o DA trocou para o modo c e o arquivo validado ainda nao saiu: a tela ja deixa de mostrar
    escolher_modo_do_da(job, 'c')
    assert job.joinpath(*tsi.ARQ_VALIDADAS).is_file()
    assert tf.sugestoes_na_tela(job) == SEM_SUGESTAO
    # a agencia fechou o teto sem clique do DA
    job2 = _job_com_sugestoes(tmp_path / 'outro')
    assert tf.sugestoes_na_tela(job2, teto='c') == SEM_SUGESTAO
    assert tf.sugestoes_na_tela(job2, teto='b')['sugestoes'] == []
    # sem arquivo validado
    job2.joinpath(*tsi.ARQ_VALIDADAS).unlink()
    assert tf.sugestoes_na_tela(job2) == {'modo': 'a', 'sha256': None, 'sugestoes': []}


def test_sugestao_de_outro_modo_de_outro_kv_ou_de_alvo_que_saiu_nao_aparece(tmp_path):
    job = _job_com_sugestoes(tmp_path, 'a')
    escolher_modo_do_da(job, 'b')  # o arquivo foi validado no modo a
    assert tf.sugestoes_na_tela(job) == {'modo': 'b', 'sha256': None, 'sugestoes': []}
    escolher_modo_do_da(job, 'a')
    arq = job.joinpath(*tsi.ARQ_VALIDADAS)
    dados = contratos.ler(arq, 'sugestoes/1')
    contratos.gravar(arq, dict(dados, arquivo_sha256='cd' * 32), 'sugestoes/1')
    assert tf.sugestoes_na_tela(job)['sugestoes'] == []
    contratos.gravar(arq, dict(dados, job_id='f' * 32), 'sugestoes/1')
    assert tf.sugestoes_na_tela(job)['sugestoes'] == []
    # o alvo que o laudo nao tem mais sai; os outros ficam
    contratos.gravar(arq, dict(dados, sugestoes=dados['sugestoes'] + [
        {'layer_id': 999, 'funcao': 'cta', 'alternativa': 'selo'}]), 'sugestoes/1')
    assert [x['layer_id'] for x in tf.sugestoes_na_tela(job)['sugestoes']] == [10, 12, 13]
    arq.write_text('{"esquema": "sugestoes/1"', encoding='utf-8')
    assert tf.sugestoes_na_tela(job)['sugestoes'] == []


def test_sugestao_nunca_vira_valor_nem_pendencia_resolvida(tmp_path):
    job = _job_com_sugestoes(tmp_path)
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    antes = tf.pendencias(laudo, {})
    assert tf.sugestoes_na_tela(job)['sugestoes']
    assert tf.pendencias(laudo, {}) == antes and any(p['tipo'] == 'funcao' for p in antes)


def test_rota_leve_das_sugestoes_le_o_sha_e_segue_a_importacao(tmp_path):
    job = _job_com_sugestoes(tmp_path)
    conteudo = dict(tts._conteudo(), sugestoes=lambda: tf.sugestoes_na_tela(job))
    s = ts.ServidorTela(conteudo).iniciar()
    try:
        assert tts._pedir(s, '/api/sugestoes')[0] == 404  # sem o cookie
        biscoito = tts._entrar(s)
        codigo, cab, corpo = tts._pedir(s, '/api/sugestoes', cookie=biscoito)
        assert codigo == 200 and cab['cache-control'] == ['no-store']
        lido = json.loads(corpo)
        assert lido['sha256'] == _sha_validadas(job) and len(lido['sugestoes']) == len(tsi.VALIDAS)
        # o Claude escreveu de novo e o motor conferiu: o sha256 muda
        tsi._escrever(job, tsi._sugestoes(job, tsi.VALIDAS[:1]))
        assert si.importar(job)['gravou']
        novo = json.loads(tts._pedir(s, '/api/sugestoes', cookie=biscoito)[2])
        assert novo['sha256'] == _sha_validadas(job) != lido['sha256'] and len(novo['sugestoes']) == 1
        assert tts._pedir(s, '/api/sugestoes', metodo='POST', cookie=biscoito)[0] == 404
        assert s.contagem['sugestoes'] == 2  # numero-neutro: as duas leituras com o cookie
    finally:
        s.parar()
    assert not (job / tr.ARQUIVO).exists()


def test_montar_da_tela_leva_a_rota_das_sugestoes(job_palco):  # noqa: F811
    from desdobra.tela import estado as te
    c = te.montar(job_palco)
    assert callable(c['sugestoes']) and c['sugestoes']() == SEM_SUGESTAO
    with ts.ServidorTela(c) as s:
        biscoito = tts._entrar(s)
        assert json.loads(tts._pedir(s, '/api/sugestoes', cookie=biscoito)[2]) == SEM_SUGESTAO


def test_texto_do_modo_a_declara_letra_desenhada_na_imagem_e_a_pagina_usa_o_mesmo():
    from desdobra.tela import atos as ta
    _nome, texto = ta.MODOS['a']
    assert 'pixel' in texto and 'vetorial' in texto and 'imagem' in texto
    js = (RAIZ_PLUGIN / 'tela' / 'tela.js').read_text(encoding='utf-8')
    for nome, texto in ta.MODOS.values():
        assert "['%s', '%s']" % (nome, texto) in js
        assert not any(x in texto for x in ('—', '–'))
    # a frase da decisao 190 (Q4), mostrada quando o modo a ou b esta gravado
    assert tf.FRASE_PEDIR_SUGESTOES == 'Para ver sugestões de função, escreva ao Claude: quero sugestões'
    assert tf.FRASE_PEDIR_SUGESTOES in js


def test_ref_das_sugestoes_e_o_sha_do_arquivo_validado(tmp_path):
    from desdobra.briefing import salvar as bs
    job = _job_com_sugestoes(tmp_path)
    assert bs.sugestoes_ref(job) == _sha_validadas(job)
    escolher_modo_do_da(job, 'c')
    assert bs.sugestoes_ref(job) is None


from test_tela_salvar import job as job_salvar, modelo  # noqa: E402,F401 - o job sintetico do salvar


def test_briefing_montado_leva_sugestoes_ref(job_salvar, modelo):  # noqa: F811
    from desdobra.briefing import salvar as bs
    from desdobra.tela import estado as te
    job = job_salvar
    conteudo = te.montar(job)
    kw = dict(origem='fixture_de_teste', meio='medicao', por={'usuario': None, 'maquina': None},
              quando='2026-11-13T10:00:00-03:00', modo=None)
    assert bs.montar(job, conteudo, {'familias': {}}, **kw)['sugestoes_ref'] is None
    escolher_modo_do_da(job, 'a')
    sp.refazer_pacotes(job)
    lid = next(iter(modelo['funcoes']))
    tsi._escrever(job, tsi._sugestoes(job, [{'layer_id': lid, 'funcao': 'titulo', 'alternativa': 'cta'}]))
    assert si.importar(job)['gravou']
    b = bs.montar(job, conteudo, {'familias': {}}, **kw)
    assert b['sugestoes_ref'] == _sha_validadas(job)
    contratos.validar(b, mb.ESQUEMA)


def _sugestao(lid, funcao, alternativa):
    return {'layer_id': lid, 'funcao': funcao, 'alternativa': alternativa}


def _rascunho_do_disco(job):
    arq = job / tr.ARQUIVO
    return contratos.ler(arq, tr.ESQUEMA) if arq.is_file() else None


def test_sugestao_na_tela_no_chromium(job_palco, tmp_path):  # noqa: F811
    """A pagina, com a rota das sugestoes trocada por uma lista sintetica (o modo de teste da tela deixa o job em c,
    e a rota de verdade tem os testes de cima): a sugestao aparece sem nada marcado, a chegada de outra espera o
    "Mostrar" sem mexer no rascunho, o "Usar" grava a funcao como qualquer escolha, o modo c tira tudo, a escolha do
    modo a ou b mostra a frase do pedido, e o cronometro do passo 2 recebe os sinais com a marca da sugestao."""
    import shutil

    from playwright.sync_api import sync_playwright

    import test_tela_palco as tp
    from desdobra.chromium import navegador
    from desdobra.tela import atos as ta
    from desdobra.tela import cronometro as tc
    from desdobra.tela import estado as te
    job = tmp_path / 'job'
    shutil.copytree(job_palco, job)
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    ids = {c['nome']: c['identidade']['layer_id'] for c in laudo['camadas']}
    pasta, filho = ids[tp.NOME_FORM], ids[tp.NOME_IMG]
    c = te.montar(job)
    vez = {'v': {'modo': 'a', 'sha256': '1' * 64, 'sugestoes': [_sugestao(pasta, 'titulo', 'texto_de_apoio')]}}
    c['sugestoes'] = lambda: vez['v']
    no_detalhe = '() => Array.from(document.querySelectorAll("#detalhe [data-usar]")).map(b => b.dataset.usar).join(",")'
    navegador.apontar_playwright()
    with ts.ServidorTela(c, pasta=job, modo_teste=True, atos=ta.atos_do_job(job, conteudo=c)) as srv, \
            sync_playwright() as pw:
        nav, pg = tp._pagina_da_tela(pw, srv, 1600, 900)  # numero-neutro: janela do teste
        try:
            _esperar(pg, '() => document.documentElement.dataset.sugestoes === "mostradas" ? "1" : ""')
            _clicar(pg, '#passos [data-passo=funcoes]')
            marca = '#arvore button[data-camada="%d"] .sugestao-arvore' % pasta
            assert pg.evaluate('(s) => document.querySelector(s).textContent', marca) == 'Sugestão: título'
            assert 'quero sugestões' not in pg.evaluate('() => document.getElementById("detalhe").innerText')
            _clicar(pg, '#arvore button[data-camada="%d"]' % pasta)
            texto = pg.evaluate('() => document.querySelector("#detalhe [data-sugestao]").innerText')
            assert 'Sugestão do Claude, modo (a)' in texto and 'Título' in texto and 'Texto de apoio' in texto
            assert not any(x in texto for x in ('—', '–')), texto
            assert pg.evaluate(no_detalhe) == 'titulo,texto_de_apoio'
            assert _pressionados(pg, '#passo-funcoes') == 0  # a sugestao nunca aparece como escolhida
            assert not (_rascunho_do_disco(job) or {}).get('funcoes')
            # chegam outras: a faixa avisa, e o que esta na tela e no rascunho nao muda ate o "Mostrar"
            vez['v'] = {'modo': 'a', 'sha256': '2' * 64,
                        'sugestoes': [_sugestao(pasta, 'cta', 'titulo'), _sugestao(filho, 'imagem', 'grafismo')]}
            _esperar(pg, '() => document.documentElement.dataset.sugestoes === "chegaram" ? "1" : ""')
            assert pg.evaluate('() => document.getElementById("sugestoes-chegaram").hidden') is False
            assert 'Chegaram as sugestões' in pg.evaluate(
                '() => document.getElementById("sugestoes-chegaram").innerText')
            assert pg.evaluate(no_detalhe) == 'titulo,texto_de_apoio'
            assert not (_rascunho_do_disco(job) or {}).get('funcoes')
            _clicar(pg, '#mostrar-sugestoes')
            assert pg.evaluate(no_detalhe) == 'cta,titulo'
            assert pg.evaluate('() => document.getElementById("sugestoes-chegaram").hidden') is True
            assert _pressionados(pg, '#passo-funcoes') == 0
            # so o clique em "Usar" poe a funcao no rascunho, como qualquer escolha do DA
            _clicar(pg, '#detalhe button[data-usar="cta"]')
            r = _salvo(pg, job)
            assert r['funcoes'] == {str(pasta): {'funcao': 'cta', 'observacao': None}}
            assert r['origem'] == 'fixture_de_teste'
            assert 'Em uso' in pg.evaluate('() => document.querySelector("#detalhe [data-sugestao]").innerText')
            assert pg.evaluate('(s) => document.querySelector(s).hidden', marca) is True  # o DA ja escolheu
            pg.wait_for_timeout(1200)  # numero-neutro: ms, um sinal por segundo
            _clicar(pg, '#arvore button[data-camada="%d"]' % filho)
            _esperar(pg, '() => document.documentElement.dataset.sinal === "enviado" ? "1" : ""')
            # o modo caiu para c: a sugestao some na hora, sem "Mostrar", e o rascunho fica
            vez['v'] = SEM_SUGESTAO
            _esperar(pg, '() => document.documentElement.dataset.sugestoes === "nenhuma" ? "1" : ""')
            assert pg.evaluate('() => document.querySelectorAll("[data-sugestao]").length') == 0
            assert pg.evaluate('() => Array.from(document.querySelectorAll(".sugestao-arvore"))'
                               '.filter(x => !x.hidden).length') == 0
            assert _rascunho_do_disco(job)['funcoes'] == r['funcoes']
            # a frase do pedido (decisao 190, Q4) aparece quando o modo a ou b fica gravado e vale
            _clicar(pg, '#passos [data-passo=lido]')
            assert 'quero sugestões' not in pg.evaluate('() => document.getElementById("lido-modo").innerText')
            import test_tela_familia_estavel as tfe
            # revisao do S4: a escolha gravada e a, mas o modo que vale continua c (teto da agencia, escolha de
            # teste): a importacao recusaria, e a frase nao aparece
            tfe._confirmar_na_pagina(pg, '#lido-modo button[data-modo=a]')
            pg.wait_for_timeout(800)  # numero-neutro: ms, a leitura das sugestoes depois do ato
            assert 'quero sugestões' not in pg.evaluate('() => document.getElementById("lido-modo").innerText')
            # o modo b gravado e valendo: a frase aparece
            vez['v'] = {'modo': 'b', 'sha256': None, 'sugestoes': []}
            tfe._confirmar_na_pagina(pg, '#lido-modo button[data-modo=b]')
            _esperar(pg, '() => document.getElementById("lido-modo").innerText.includes("quero sugestões") ? "1" : ""')
            assert tf.FRASE_PEDIR_SUGESTOES in pg.evaluate('() => document.getElementById("lido-modo").innerText')
        finally:
            nav.close()
    sessao = contratos.ler(job / tc.ARQUIVO, tc.ESQUEMA)['sessoes'][-1]
    assert sessao['passo_2']['sugestao_na_tela'] is True and sessao['passo_2']['total_s'] >= 0


def test_chegada_das_primeiras_sugestoes_tira_a_frase_do_pedido(job_palco, tmp_path):  # noqa: F811
    """Revisao do S4, o fluxo da Q4: a tela abre sem sugestao e mostra a frase do pedido; as sugestoes chegam com o
    passo 2 aberto e a faixa "Chegaram" espera o "Mostrar". Enquanto isso, a frase sai: as duas mensagens nao podem
    pedir coisas contrarias ao DA."""
    import shutil

    from playwright.sync_api import sync_playwright

    import test_tela_palco as tp
    from desdobra.chromium import navegador
    from desdobra.tela import atos as ta
    from desdobra.tela import estado as te
    job = tmp_path / 'job'
    shutil.copytree(job_palco, job)
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    pasta = {c['nome']: c['identidade']['layer_id'] for c in laudo['camadas']}[tp.NOME_FORM]
    c = te.montar(job)
    vez = {'v': {'modo': 'a', 'sha256': None, 'sugestoes': []}}
    c['sugestoes'] = lambda: vez['v']
    detalhe = '() => document.getElementById("detalhe").innerText'
    navegador.apontar_playwright()
    with ts.ServidorTela(c, pasta=job, modo_teste=True, atos=ta.atos_do_job(job, conteudo=c)) as srv, \
            sync_playwright() as pw:
        nav, pg = tp._pagina_da_tela(pw, srv, 1600, 900)  # numero-neutro: janela do teste
        try:
            _esperar(pg, '() => document.documentElement.dataset.sugestoes === "nenhuma" ? "1" : ""')
            _clicar(pg, '#passos [data-passo=funcoes]')
            assert tf.FRASE_PEDIR_SUGESTOES in pg.evaluate(detalhe)
            vez['v'] = {'modo': 'a', 'sha256': '3' * 64, 'sugestoes': [_sugestao(pasta, 'titulo', 'cta')]}
            _esperar(pg, '() => document.documentElement.dataset.sugestoes === "chegaram" ? "1" : ""')
            assert 'Chegaram as sugestões' in pg.evaluate(
                '() => document.getElementById("sugestoes-chegaram").innerText')
            assert 'quero sugestões' not in pg.evaluate(detalhe)
            _clicar(pg, '#mostrar-sugestoes')
            assert 'quero sugestões' not in pg.evaluate(detalhe)
            assert 'sugestão do Claude' in pg.evaluate(detalhe)
            assert not (_rascunho_do_disco(job) or {}).get('funcoes')
        finally:
            nav.close()


def test_rota_leve_nao_valida_o_laudo_a_cada_consulta(tmp_path, monkeypatch):
    """Revisao do S4: o laudo nao muda com a tela aberta. A consulta a cada poucos segundos le o laudo uma vez e so
    volta a ler quando o arquivo muda; o arquivo validado grande demais nao se le."""
    import os
    job = _job_com_sugestoes(tmp_path)
    arq_laudo = job / 'laudo' / 'laudo.json'
    leituras = []
    ler = contratos.ler

    def contar(caminho, *a, **k):
        if os.path.basename(str(caminho)) == 'laudo.json':
            leituras.append(1)
        return ler(caminho, *a, **k)
    monkeypatch.setattr(contratos, 'ler', contar)
    primeira = tf.sugestoes_na_tela(job)
    for _ in range(5):  # numero-neutro: consultas seguidas
        assert tf.sugestoes_na_tela(job) == primeira
    assert primeira['sugestoes'] and len(leituras) == 1
    # o laudo mudou: le de novo
    st = arq_laudo.stat()
    os.utime(arq_laudo, ns=(st.st_atime_ns, st.st_mtime_ns + 10 ** 9))
    assert tf.sugestoes_na_tela(job) == primeira and len(leituras) == 2
    # o arquivo validado grande demais fica de fora, como na importacao
    arq = job.joinpath(*tsi.ARQ_VALIDADAS)
    arq.write_bytes(arq.read_bytes() + b' ' * (si.LIMITE_BYTES + 1))
    assert tf.sugestoes_na_tela(job) == {'modo': 'a', 'sha256': None, 'sugestoes': []}


def test_ref_das_sugestoes_segue_o_teto_da_tela(job_salvar, modelo):  # noqa: F811
    """Revisao do S4: a tela aberta com o teto da agencia na linha de comando (b) nao mostra as sugestoes validadas
    no modo a; o briefing tambem nao leva a referencia delas."""
    from desdobra.briefing import salvar as bs
    from desdobra.tela import estado as te
    job = job_salvar
    # as duas telas abrem antes (a rota das sugestoes le de novo a cada pedido)
    com_b, sem_teto = te.montar(job, teto='b'), te.montar(job)
    escolher_modo_do_da(job, 'a')
    sp.refazer_pacotes(job)
    lid = next(iter(modelo['funcoes']))
    tsi._escrever(job, tsi._sugestoes(job, [{'layer_id': lid, 'funcao': 'titulo', 'alternativa': 'cta'}]))
    assert si.importar(job)['gravou']
    kw = dict(origem='fixture_de_teste', meio='medicao', por={'usuario': None, 'maquina': None},
              quando='2026-11-13T10:00:00-03:00', modo=None)
    assert com_b['sugestoes']()['sha256'] is None
    assert bs.montar(job, com_b, {'familias': {}}, **kw)['sugestoes_ref'] is None
    assert bs.montar(job, sem_teto, {'familias': {}}, **kw)['sugestoes_ref'] == _sha_validadas(job)


# ------------------------------------------------------------------ M7c, M4: o padrao da marca como sugestao citada
# arquitetura-v1.md, 5.3 e 5.7; decisoes-v1.md, 162 e 190 (Q1 e Q3): para cada funcao com regra no perfil atual da
# marca escolhida no passo 1, a tela mostra a regra de escala e a ancora com a fonte ("padrao da marca, versao N, do job
# X"), sem gravar nada. So o clique do DA em "Usar o padrao" poe o valor no rascunho, com a origem padrao_marca e o ref
# "marca:<id>@v<N>#job:<id>". Biblioteca e perfis sinteticos, em pasta temporaria (pelo modulo do perfil, M2).
import copy  # noqa: E402

JOB_P1 = 'a1' * 16
JOB_P2 = 'b2' * 16


def _campanha_m4(job_id):
    return {'job': job_id, 'data': '2026-11-12', 'formatos': [{'formato': 'f300x250', 'aprovacao_sha256': 'd4' * 32}],
            'confirmado_por': {'usuario': 'da', 'maquina': 'estacao'}, 'origem': 'da', 'meio': 'tela'}


def perfil_m4(bib, nome='Marca Sintetica M4', versoes=2, regra_titulo='raiz_area'):
    """Um perfil sintetico: na versao 1 (job 1), titulo e estrutura; na 2 (job 2) o logo entra, e o titulo e a
    estrutura mantem o job 1 de origem. Devolve o id."""
    from desdobra.marca import perfil
    id_ = perfil.criar(bib, nome)['id']
    v1 = {'regras_escala': [{'funcao': 'titulo', 'regra': regra_titulo, 'job_origem': JOB_P1},
                            {'funcao': 'estrutura', 'regra': 'cover', 'job_origem': JOB_P1}],
          'ancoras': [{'funcao': 'titulo', 'x': 'esquerda', 'y': 'topo', 'job_origem': JOB_P1},
                      {'funcao': 'estrutura', 'x': 'centro', 'y': 'meio', 'job_origem': JOB_P1}],
          'faces': [{'postscript': 'Sintetica-Bold'}]}
    perfil.nova_versao(bib, id_, campanha=_campanha_m4(JOB_P1), quando='2026-11-12T10:00:00-03:00', **v1)
    if versoes >= 2:
        registrar_m4(bib, id_, v1)
    return id_


def registrar_m4(bib, id_, v1, regra_titulo=None):
    """A versao seguinte do perfil (job 2): o logo entra; regra_titulo troca a regra do titulo (origem job 2)."""
    from desdobra.marca import perfil
    v2 = copy.deepcopy(v1)
    v2['regras_escala'].append({'funcao': 'logo_principal', 'regra': 'raiz_area', 'job_origem': JOB_P2})
    v2['ancoras'].append({'funcao': 'logo_principal', 'x': 'direita', 'y': 'base', 'job_origem': JOB_P2})
    if regra_titulo:
        v2['regras_escala'][0] = {'funcao': 'titulo', 'regra': regra_titulo, 'job_origem': JOB_P2}
    return perfil.nova_versao(bib, id_, campanha=_campanha_m4(JOB_P2), quando='2026-11-13T10:00:00-03:00', **v2)[0]


def marca_do_job_m4(job, marca_id):
    """briefing/marca.json sintetico (o ato da tela tem os testes dele em test_tela_salvar.py)."""
    from desdobra.marca import job as mj
    (job / 'briefing').mkdir(exist_ok=True)
    contratos.gravar(job / mj.ARQUIVO, {
        'esquema': mj.ESQUEMA, 'job_id': 'f0' * 16, 'escolha': 'sem_marca' if marca_id is None else 'marca',
        'marca_id': marca_id, 'origem': 'fixture_de_teste',
        'escolhido_por': {'usuario': None, 'maquina': None, 'meio': 'medicao', 'quando': '2026-11-13T10:00:00-03:00'}},
        mj.ESQUEMA)


@pytest.fixture
def bib_m4(tmp_path):
    bib = tmp_path / 'biblioteca-da-agencia'
    bib.mkdir()
    return bib


def test_padrao_da_marca_cita_versao_e_job_de_cada_regra(job_funcoes, bib_m4):
    id_ = perfil_m4(bib_m4)
    marca_do_job_m4(job_funcoes, id_)
    p = tf.padrao_da_marca(job_funcoes, bib_m4)
    assert p['versao'] == 2 and set(p['funcoes']) == {'titulo', 'estrutura', 'logo_principal'}
    t = p['funcoes']['titulo']
    # desde: a primeira versao, na sequencia que chega a atual, com o mesmo valor e o mesmo job de origem
    assert t['regra'] == {'valor': 'raiz_area', 'job': JOB_P1, 'ref': 'marca:%s@v2#job:%s' % (id_, JOB_P1),
                          'desde': 1}
    assert t['ancora'] == {'x': 'esquerda', 'y': 'topo', 'job': JOB_P1, 'ref': 'marca:%s@v2#job:%s' % (id_, JOB_P1),
                           'desde': 1}
    assert p['funcoes']['logo_principal']['regra']['ref'] == 'marca:%s@v2#job:%s' % (id_, JOB_P2)
    assert tf.ref_do_padrao(id_, 2, JOB_P1) == t['regra']['ref']
    # so ids, o enum e a versao: o nome da marca nunca entra
    assert 'Marca Sintetica' not in json.dumps(p)
    # nada foi gravado no job
    assert not (job_funcoes / tr.ARQUIVO).exists()


def test_sem_marca_sem_biblioteca_ou_perfil_sem_registro_nada_aparece(job_funcoes, bib_m4):
    assert tf.padrao_da_marca(job_funcoes, bib_m4) is None  # nenhuma marca escolhida
    id_ = perfil_m4(bib_m4)
    marca_do_job_m4(job_funcoes, None)
    assert tf.padrao_da_marca(job_funcoes, bib_m4) is None  # "Sem marca"
    marca_do_job_m4(job_funcoes, id_)
    assert tf.padrao_da_marca(job_funcoes, None) is None  # biblioteca nao configurada
    vazia = bib_m4.parent / 'outra-biblioteca'
    vazia.mkdir()
    assert tf.padrao_da_marca(job_funcoes, vazia) is None  # a marca nao esta nesta biblioteca
    from desdobra.marca import perfil
    nova = perfil.criar(bib_m4, 'Marca Sintetica Sem Registro')['id']
    marca_do_job_m4(job_funcoes, nova)
    assert tf.padrao_da_marca(job_funcoes, bib_m4) is None  # versao 0: nada registrado


def design_do_padrao(p, *funcoes):
    """O que o clique em "Usar o padrao" poe no rascunho, por funcao."""
    d = {}
    for f in funcoes:
        x = p['funcoes'][f]
        d[f] = {'regra': x['regra']['valor'], 'x': x['ancora']['x'], 'y': x['ancora']['y'],
                'origem': {'regra': {'tipo': 'padrao_marca', 'ref': x['regra']['ref']},
                           'ancora': {'tipo': 'padrao_marca', 'ref': x['ancora']['ref']}}}
    return d


def _rascunho_minimo():
    return {'esquema': tr.ESQUEMA, 'job_id': 'f0' * 16, 'laudo_sha256': 'c' * 64, 'origem': 'rascunho',
            'atualizado_em': '2026-11-13T10:00:00-03:00', 'familias': {}}


def test_padrao_nao_e_valor_e_o_clique_leva_a_origem_ao_briefing_parcial(job_funcoes, bib_m4):
    laudo = laudo_pequeno()
    id_ = perfil_m4(bib_m4)
    marca_do_job_m4(job_funcoes, id_)
    p = tf.padrao_da_marca(job_funcoes, bib_m4)
    dados = {'funcoes': {'10': _f('titulo')}}
    # com o padrao citado, a regra e a ancora do titulo continuam faltando: 0 campo preenchido sem o clique
    assert {'tipo': 'regra', 'funcao': 'titulo'} in tf.pendencias(laudo, dados)
    dados['design'] = design_do_padrao(p, 'titulo')
    contratos.validar(dict(_rascunho_minimo(), **dados), tr.ESQUEMA)
    assert {'tipo': 'regra', 'funcao': 'titulo'} not in tf.pendencias(laudo, dados)
    parcial = tf.briefing_parcial(dados)
    regra = next(r for r in parcial['regras_escala'] if r['funcao'] == 'titulo')['regra']
    assert regra['origem'] == {'tipo': 'padrao_marca', 'ref': p['funcoes']['titulo']['regra']['ref']}
    ancora = next(a for a in parcial['ancoras'] if a.get('funcao') == 'titulo')
    assert ancora['x']['origem']['tipo'] == ancora['y']['origem']['tipo'] == 'padrao_marca'
    assert tf.padrao_invalido(dados, p) == []
    # sem o clique, a origem e a do DA, como antes
    sem = tf.briefing_parcial({'design': {'titulo': {'regra': 'largura', 'x': None, 'y': None}}})
    assert sem['regras_escala'][0]['regra']['origem'] == tf.ORIGEM


def _trocar_versao(d, p):
    o = d['titulo']['origem']['regra']
    # revisao do M4: o titulo esta igual desde a versao 1, entao so a versao que nao existe (3) nao vale
    o['ref'] = o['ref'].replace('@v2', '@v3')


def _trocar_marca(d, p):
    d['titulo']['origem']['ancora']['ref'] = 'marca:%s@v2#job:%s' % ('e' * 32, JOB_P1)


def _trocar_job(d, p):
    o = d['titulo']['origem']['regra']
    o['ref'] = o['ref'].replace(JOB_P1, JOB_P2)


@pytest.mark.parametrize('mudar, esperado', [
    (lambda d, p: d['titulo'].update(regra='largura'), [{'funcao': 'titulo', 'campo': 'regra'}]),
    (lambda d, p: d['titulo'].update(x='direita'), [{'funcao': 'titulo', 'campo': 'ancora'}]),
    (_trocar_versao, [{'funcao': 'titulo', 'campo': 'regra'}]),
    (_trocar_marca, [{'funcao': 'titulo', 'campo': 'ancora'}]),
    (_trocar_job, [{'funcao': 'titulo', 'campo': 'regra'}]),
])
def test_origem_do_padrao_que_nao_bate_com_o_perfil_atual_e_invalida(job_funcoes, bib_m4, mudar, esperado):
    id_ = perfil_m4(bib_m4)
    marca_do_job_m4(job_funcoes, id_)
    p = tf.padrao_da_marca(job_funcoes, bib_m4)
    design = design_do_padrao(p, 'titulo')
    mudar(design, p)
    assert tf.padrao_invalido({'design': design}, p) == esperado
    # sem o perfil (sem marca, sem biblioteca), toda origem do padrao e invalida
    assert tf.padrao_invalido({'design': design_do_padrao(p, 'titulo')}, None) == \
        [{'funcao': 'titulo', 'campo': 'regra'}, {'funcao': 'titulo', 'campo': 'ancora'}]
    # sem_padrao_invalido tira so a origem que nao vale; o valor fica, como escolha do DA
    limpo = tf.sem_padrao_invalido({'design': design}, p)
    assert limpo['design']['titulo']['regra'] == design['titulo']['regra']
    campo = esperado[0]['campo']
    assert campo not in (limpo['design']['titulo'].get('origem') or {})


def test_versao_nova_do_perfil_invalida_o_clique_de_antes(job_funcoes, bib_m4):
    """O DA usou o padrao da versao 2; a marca ganha a versao 3 com outra regra de titulo: o clique de antes deixa de
    valer (o ref cita a versao 2), e o padrao citado agora e o da versao 3."""
    from desdobra.marca import perfil
    id_ = perfil_m4(bib_m4)
    marca_do_job_m4(job_funcoes, id_)
    p2 = tf.padrao_da_marca(job_funcoes, bib_m4)
    dados = {'design': design_do_padrao(p2, 'titulo')}
    atual = perfil.ler(bib_m4, id_)['atual']
    base = {k: atual[k] for k in ('regras_escala', 'ancoras', 'faces')}
    base['regras_escala'] = [r for r in base['regras_escala'] if r['funcao'] != 'logo_principal']
    base['ancoras'] = [a for a in base['ancoras'] if a['funcao'] != 'logo_principal']
    registrar_m4(bib_m4, id_, base, regra_titulo='lado_curto')
    p3 = tf.padrao_da_marca(job_funcoes, bib_m4)
    assert p3['versao'] == 3 and p3['funcoes']['titulo']['regra']['valor'] == 'lado_curto'
    assert {'funcao': 'titulo', 'campo': 'regra'} in tf.padrao_invalido(dados, p3)
    # revisao do M4: so o campo que mudou na versao nova cai; a ancora do titulo, igual desde a versao 1, continua
    assert tf.padrao_invalido(dados, p3) == [{'funcao': 'titulo', 'campo': 'regra'}]


def test_versao_nova_sem_mudar_a_funcao_mantem_o_clique_de_antes(job_funcoes, bib_m4):
    """Revisao do M4: o DA usou o padrao da versao 2 no titulo e no logo; outra campanha registra a versao 3 mudando so
    a estrutura. O titulo e o logo tem o mesmo valor e o mesmo job de origem: o clique de antes continua valendo, e o
    ref novo do titulo diz desde que versao o valor esta igual. Um ref de versao em que o valor ainda nao estava no
    perfil (ou de versao que nao existe) nao vale."""
    from desdobra.marca import perfil
    id_ = perfil_m4(bib_m4)
    marca_do_job_m4(job_funcoes, id_)
    p2 = tf.padrao_da_marca(job_funcoes, bib_m4)
    assert p2['funcoes']['titulo']['regra']['desde'] == 1
    assert p2['funcoes']['logo_principal']['regra']['desde'] == 2
    dados = {'design': design_do_padrao(p2, 'titulo', 'logo_principal')}
    v = copy.deepcopy({k: perfil.ler(bib_m4, id_)['atual'][k] for k in ('regras_escala', 'ancoras', 'faces')})
    for r in v['regras_escala']:
        if r['funcao'] == 'estrutura':
            r.update(regra='largura', job_origem='c3' * 16)
    perfil.nova_versao(bib_m4, id_, campanha=_campanha_m4('c3' * 16), quando='2026-11-14T10:00:00-03:00', **v)
    p3 = tf.padrao_da_marca(job_funcoes, bib_m4)
    assert p3['versao'] == 3 and p3['funcoes']['estrutura']['regra']['desde'] == 3
    assert tf.padrao_invalido(dados, p3) == []
    # o ref da versao 1 no logo (o logo so entrou na versao 2) e o da versao 4 (que nao existe) nao valem
    velho = copy.deepcopy(dados)
    velho['design']['logo_principal']['origem']['regra']['ref'] = 'marca:%s@v1#job:%s' % (id_, JOB_P2)
    velho['design']['titulo']['origem']['ancora']['ref'] = 'marca:%s@v4#job:%s' % (id_, JOB_P1)
    assert tf.padrao_invalido(velho, p3) == [{'funcao': 'logo_principal', 'campo': 'regra'},
                                             {'funcao': 'titulo', 'campo': 'ancora'}]


def test_regra_da_decisao_10_e_padrao_da_marca_aparecem_cada_um_com_a_fonte(job_funcoes, bib_m4):
    """A camada coberta mostra a sugestao da regra da decisao 10 (estrutura) no passo 2, e o titulo mostra o padrao da
    marca no Design system: as duas aparecem, cada uma com a fonte (a da decisao 10 no no da arvore, a da marca com o
    ref), e nenhuma vira valor. A funcao que a regra da decisao 10 da (estrutura ou fora da peca) nao tem tamanho nem
    ancora: o padrao da marca para ela fica no perfil e o Design system nao a pede."""
    laudo = laudo_pequeno()
    id_ = perfil_m4(bib_m4)
    marca_do_job_m4(job_funcoes, id_)
    p = tf.padrao_da_marca(job_funcoes, bib_m4)
    coberta = next(n for n in tf.nos(laudo) if n['camada'] == 13)
    assert coberta['coberta'] == {'sugestao': 'estrutura'}
    assert p['funcoes']['titulo']['regra']['ref'].startswith('marca:%s@v2#' % id_)
    assert {'estrutura', 'fora_da_peca'} <= set(mb.SEM_GEOMETRIA)
    dados = {'funcoes': {'10': _f('titulo')}}
    pend = tf.pendencias(laudo, dados)
    # a coberta continua pedindo a decisao do DA, e o titulo continua pedindo regra e ancora: nada foi preenchido
    assert {'tipo': 'coberta', 'camada': 13} in pend
    assert {'tipo': 'regra', 'funcao': 'titulo'} in pend and {'tipo': 'ancora', 'funcao': 'titulo'} in pend
    pend = tf.pendencias(laudo, dict(dados, cobertas={'13': 'aceita'}))
    assert not any(x.get('funcao') == 'estrutura' for x in pend)


def test_esquema_do_rascunho_aceita_a_origem_do_padrao_so_no_formato_do_ref():
    base = _rascunho_minimo()
    ref = 'marca:%s@v3#job:%s' % ('a' * 32, JOB_P1)
    ok = {'titulo': {'regra': 'largura', 'x': None, 'y': None,
                     'origem': {'regra': {'tipo': 'padrao_marca', 'ref': ref}}}}
    contratos.validar(dict(base, design=ok), tr.ESQUEMA)
    for ruim in ({'regra': {'tipo': 'da', 'ref': ref}}, {'regra': {'tipo': 'padrao_marca', 'ref': 'marca:abc'}},
                 {'regra': {'tipo': 'padrao_marca', 'ref': 'marca:%s@v0#job:%s' % ('a' * 32, JOB_P1)}},
                 {'cor': {'tipo': 'padrao_marca', 'ref': ref}},
                 {'regra': {'tipo': 'padrao_marca', 'ref': ref, 'nome': 'x'}}):
        with pytest.raises(contratos.ErroContrato):
            contratos.validar(dict(base, design={'titulo': dict(ok['titulo'], origem=ruim)}), tr.ESQUEMA)
    # o elemento indeterminado nao tem padrao da marca (a regra dele e por camada, no job)
    with pytest.raises(contratos.ErroContrato):
        contratos.validar(dict(base, design_camadas={'20': dict(ok['titulo'])}), tr.ESQUEMA)
