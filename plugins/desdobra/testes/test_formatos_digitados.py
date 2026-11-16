# -*- coding: utf-8 -*-
"""0.9.2, formatos digitados na tela: o job chega sem folha de spec, e o DA escreve os formatos no passo 1.

Pedido do dono do produto: "quero que a tela ganhe um jeito de digitar formatos sem folha de spec". Sem folha, o job
nao tem formato, e o passo 3 nunca monta familia. Criterios cobertos aqui:
  - o campo aceita uma lista colada (virgula, ponto e virgula ou uma por linha, com ou sem px) e recusa na hora, com o
    codigo e o trecho, o que nao entende, o numero quebrado, o lado fora dos limites, o repetido e o texto longo; a
    pagina usa o mesmo parser do motor (o espelho em tela.js), conferido no Chromium;
  - o ato e da tela, com a confirmacao na janela e a rota generica (token, cookie, CSRF): o arquivo
    briefing/formatos-digitados.json guarda cada formato com quem e quando, e o rascunho das specs ganha o formato com
    a dimensao confirmada (origem digitado_pelo_da_na_tela, meio tela); a fase specs fica em dia;
  - do job sem folha ao primeiro briefing salvo so por cliques: o passo 3 mostra as familias dos formatos digitados;
  - o Claude nao digita formatos: o motor recusa sem o Disparo da tela, e o gancho nega a escrita e o codigo;
  - a folha que traz a mesma medida vale, e o formato digitado volta quando a folha sai;
  - nenhuma proposta do Claude alcanca o formato digitado, e o pacote das specs nao o oferece.
Tudo sintetico: o PSD de test_tela_palco, a fonte de autoteste do motor e as fichas HTML de test_specs_apoio.
"""
import json
import os
import shutil

import pytest

import test_specs_apoio as sap
import test_tela_escrita as tte
import test_tela_palco as tp
import test_tela_partida as tpa
import test_tela_servidor as tts
from desdobra import contratos, humano, limites
from desdobra.briefing import modelo as mb
from desdobra.job import nucleo
from desdobra.specs import digitados as dg
from desdobra.specs import importar
from desdobra.specs import modelo as sm
from desdobra.tela import atos as ta
from desdobra.tela import estado as te
from desdobra.tela import servidor as ts

ATO = 'formatos_digitados'
PROIBIDOS = ('\u2014', '\u2013', 'desdobra job', 'desdobra spec', '--job', 'terminal', 'digite', 'Digite')


# ------------------------------------------------------------------ apoio
def _limpar_ambiente(mp):
    for v in humano.VARIAVEIS_DO_CLAUDE + humano.VARIAVEIS_DO_PAINEL + tuple(humano.MARCAS_DO_PAINEL):
        mp.delenv(v, raising=False)
    from desdobra import cli
    mp.setattr(cli._Analisador, 'modo_envelope', False, raising=False)


def _ato(job, dados, teste=True):
    """Pede o ato pela rota generica da tela e confirma. (codigo do pedido, codigo da confirmacao, pedido)."""
    s = ts.ServidorTela(tts._conteudo(), pasta=job, modo_teste=teste, atos=ta.atos_do_job(job)).iniciar()
    try:
        biscoito = tts._entrar(s)
        codigo, p = tte._pedir_ato(s, biscoito, nome=ATO, dados=dados)
        if codigo != 200:
            return codigo, None, None
        c2 = tte._escrever(s, '/api/ato/confirmar', {'pedido': p['pedido'], 'resposta': 'confirmar'},
                           cookie=biscoito)[0]
        return codigo, c2, p
    finally:
        s.parar()


def _ato_do_da(job, dados):
    with pytest.MonkeyPatch.context() as mp:
        _limpar_ambiente(mp)
        return _ato(job, dados, teste=False)


def _acrescentar(texto):
    return {'acao': 'acrescentar', 'texto': texto}


def _remover(largura, altura):
    return {'acao': 'remover', 'largura': largura, 'altura': altura}


def _confirmar_spec(job, valor_id):
    """O DA confirma o valor de spec da folha na tela (ato spec_valor, rota generica)."""
    with pytest.MonkeyPatch.context() as mp:
        _limpar_ambiente(mp)
        s = ts.ServidorTela(tts._conteudo(), pasta=job, modo_teste=False, atos=ta.atos_do_job(job)).iniciar()
        try:
            biscoito = tts._entrar(s)
            codigo, p = tte._pedir_ato(s, biscoito, nome='spec_valor', dados={'valor_id': valor_id})
            assert codigo == 200, p
            assert tte._escrever(s, '/api/ato/confirmar', {'pedido': p['pedido'], 'resposta': 'confirmar'},
                                 cookie=biscoito)[0] == 200
        finally:
            s.parar()


def _rascunho(job):
    return contratos.ler(job / importar.ARQUIVO_RASCUNHO, 'spec/1')


def _digitados_no_rascunho(job):
    return {f['chave']: f for f in _rascunho(job)['formatos'] if sm.eh_digitado_na_tela(f)}


@pytest.fixture(scope='module')
def base_sem_folha(tmp_path_factory):
    """O job sintetico novo, sem folha de spec: laudo e fontes lidos, sem formato nenhum."""
    return tpa._criar(tmp_path_factory.mktemp('digitados-sem-folha'), folhas=None)


@pytest.fixture
def sem_folha(base_sem_folha, tmp_path):
    job, funcoes = base_sem_folha
    destino = tmp_path / 'job'
    shutil.copytree(job, destino)
    return destino, funcoes


# ------------------------------------------------------------------ o parser (motor)
@pytest.mark.parametrize('texto,esperado', [
    ('1080x1920, 300x600', [(1080, 1920), (300, 600)]),
    ('1080 x 1920; 300\u00d7600', [(1080, 1920), (300, 600)]),
    ('1080X1920\n300*600', [(1080, 1920), (300, 600)]),
    ('1080x1920px', [(1080, 1920)]),
    ('  1080 px x 1920 px ,\r\n', [(1080, 1920)]),
    ('640x320, , 300x600;', [(640, 320), (300, 600)]),
])
def test_interpretar_aceita_lista_colada(texto, esperado):
    assert dg.interpretar(texto) == (esperado, [])


CASOS_DE_ERRO = [
    ('', [], ['vazio']),
    (' , ;\n', [], ['vazio']),
    ('1080', [], ['nao_entendido']),
    ('abc', [], ['nao_entendido']),
    ('1080.5x1920', [], ['nao_inteiro']),
    ('0x600', [], ['pequeno']),
    ('8x8', [], ['pequeno']),
    ('20000x100', [], ['grande']),
    ('1080x1920, 1080 x 1920', [(1080, 1920)], ['repetido_no_texto']),
    ('1080x1920, abc', [(1080, 1920)], ['nao_entendido']),
    ('x' * 2001, [], ['texto_longo']),
    ('\u0661\u0660x20', [], ['nao_entendido']),
]


@pytest.mark.parametrize('texto,medidas,codigos', CASOS_DE_ERRO)
def test_interpretar_recusa_com_o_codigo_e_o_trecho(texto, medidas, codigos):
    achadas, erros = dg.interpretar(texto)
    assert achadas == medidas and [e['codigo'] for e in erros] == codigos
    for e in erros:
        texto_erro = dg.mensagem(e)
        assert texto_erro and '{' not in texto_erro and not any(x in texto_erro for x in PROIBIDOS)
    if codigos == ['nao_entendido'] and texto == 'abc':
        assert erros[0]['trecho'] == 'abc' and 'abc' in dg.mensagem(erros[0])


def test_limites_do_parser_vem_do_registro():
    assert dg.interpretar('%dx%d' % ((limites.valor('specs.digitado_lado_min_px'),) * 2))[1] == []
    assert dg.interpretar('%dx16' % (limites.valor('specs.digitado_lado_max_px') + 1))[1][0]['codigo'] == 'grande'
    assert set(dg.MENSAGENS) >= {'vazio', 'nao_entendido', 'nao_inteiro', 'pequeno', 'grande', 'repetido_no_texto',
                                 'ja_na_lista', 'ja_na_folha', 'demais', 'texto_longo', 'recusado'}
    for codigo, texto in dg.MENSAGENS.items():
        assert not any(x in texto for x in PROIBIDOS), codigo


# ------------------------------------------------------------------ o ato da tela
def test_ato_pela_tela_grava_confirmado_com_quem_e_quando(sem_folha):
    job, _funcoes = sem_folha
    assert nucleo.fases_invalidas(job) == set()
    assert te.montar(job)['estado']['passo_3']['texto'] == te.SEM_FORMATOS
    codigo, c2, p = _ato_do_da(job, _acrescentar('1080x1920, 300 x 600'))
    assert (codigo, c2) == (200, 200)
    assert '1080 x 1920 e 300 x 600' in p['texto'] and not any(x in p['texto'] for x in PROIBIDOS)
    dados = contratos.ler(job / dg.ARQUIVO, dg.ESQUEMA)
    assert [(f['largura'], f['altura']) for f in dados['formatos']] == [(1080, 1920), (300, 600)]
    assert all(f['origem'] == 'da' and f['decidido_por']['meio'] == 'tela' and f['decidido_por']['quando']
               for f in dados['formatos'])
    assert [h['acao'] for h in dados['historico']] == ['acrescentar', 'acrescentar']
    # o rascunho das specs: o formato digitado com a dimensao confirmada pelo DA, na tela
    fmts = _digitados_no_rascunho(job)
    assert set(fmts) == {'digitado|tela|1080x1920', 'digitado|tela|300x600'}
    dim = fmts['digitado|tela|1080x1920']['campos']['dimensao']
    assert dim['origem'] == sm.ORIGEM_DIGITADO_NA_TELA and dim['situacao'] == 'confirmado'
    assert dim['confirmacao']['meio'] == 'tela' and dim['confirmacao']['por'] == 'da' and dim['fonte'] is None
    assert _rascunho(job)['resumo']['formatos_digitados'] == 2
    # os formatos do job (so o confirmado) e nada a espera em Valores de spec
    fj = contratos.ler(job / importar.ARQUIVO_FORMATOS, 'spec/1')
    assert {f['chave'] for f in fj['formatos']} == set(fmts)
    assert te.specs_pendentes(job) == []
    # a fase specs fica em dia, sem passo nenhum fora da tela
    assert nucleo.fases_invalidas(job) == set()
    e = te.montar(job)['estado']
    assert {f['id'] for f in e['lido']['specs']['formatos']} == {'digitado-tela-1080x1920', 'digitado-tela-300x600'}
    assert all(f['digitado'] for f in e['lido']['specs']['formatos'])
    assert e['lido']['specs']['sem_formatos'] == ''
    assert te.SEM_FORMATOS_FALTA not in [x['texto'] for x in e['faltam']]
    lista = e['lido']['specs']['digitados']['lista']
    assert [x['medida'] for x in lista] == ['1080 x 1920', '300 x 600'] and not any(x['na_folha'] for x in lista)
    assert ts._job_do_da(job)  # a decisao do DA conta: o modo de teste da tela recusa o job


def test_remover_tira_o_formato_e_guarda_o_historico(sem_folha):
    job, _funcoes = sem_folha
    assert _ato(job, _acrescentar('640x320, 300x600'))[:2] == (200, 200)
    codigo, c2, p = _ato(job, _remover(300, 600))
    assert (codigo, c2) == (200, 200) and 'sai do job' in p['texto']
    dados = dg.ler(job)
    assert dg.lista(job) == [(640, 320)]
    assert [(h['acao'], h['largura'], h['altura']) for h in dados['historico']] == [
        ('acrescentar', 640, 320), ('acrescentar', 300, 600), ('remover', 300, 600)]
    assert set(_digitados_no_rascunho(job)) == {'digitado|tela|640x320'}
    assert nucleo.fases_invalidas(job) == set()


def test_sem_disparo_da_tela_o_motor_recusa(sem_folha):
    job, _funcoes = sem_folha
    with pytest.raises(humano.ErroHumano):
        dg.gravar(job, _acrescentar('640x320'), disparo=None)
    sessao = humano.abrir_sessao_tela(teste=True)
    outro = humano.exigir_tela('modo dados escolher', sessao, confirmado=True)
    with pytest.raises(humano.ErroHumano):
        dg.gravar(job, _acrescentar('640x320'), disparo=outro)
    assert dg.ler(job) is None and not (job / dg.ARQUIVO).exists()


def _muitos(n):
    lado = limites.valor('specs.digitado_lado_min_px')
    return ', '.join('%dx%d' % (lado + i, lado) for i in range(n))


@pytest.mark.parametrize('dados', [
    {'acao': 'acrescentar', 'texto': '640x320', 'extra': 1},
    {'acao': 'acrescentar'},
    {'acao': 'acrescentar', 'texto': 640},
    {'acao': 'acrescentar', 'texto': 'abc'},
    {'acao': 'acrescentar', 'texto': '1080.5x1920'},
    {'acao': 'apagar', 'texto': '640x320'},
    {'acao': 'remover', 'largura': True, 'altura': 600},
    {'acao': 'remover', 'largura': '300', 'altura': 600},
    {'acao': 'remover', 'largura': 300, 'altura': 600},
    'demais',
])
def test_ato_recusa_antes_da_janela(sem_folha, dados):
    job, _funcoes = sem_folha
    if dados == 'demais':
        dados = _acrescentar(_muitos(limites.valor('specs.digitados_max') + 1))
    assert _ato(job, dados)[0] == 403
    assert dg.ler(job) is None


def test_ato_recusa_o_que_ja_esta_na_lista(sem_folha):
    job, _funcoes = sem_folha
    assert _ato(job, _acrescentar('640x320'))[:2] == (200, 200)
    assert _ato(job, _acrescentar('300x600, 640 x 320'))[0] == 403
    assert dg.conferir(job, _acrescentar('640x320')) == 'ja_na_lista'
    assert dg.lista(job) == [(640, 320)]


def test_job_de_antes_sem_o_arquivo_nao_fica_desatualizado(sem_folha):
    """O estado.json de um job da 0.9.1 nao tem a entrada nova da fase specs: sem o arquivo, o hash e None dos dois
    lados, e a fase continua em dia."""
    job, _funcoes = sem_folha
    estado = contratos.ler(job / 'estado.json', 'estado/1')
    rel = dg.ARQUIVO.as_posix()
    assert rel in estado['fases']['specs']['hash_entradas']
    del estado['fases']['specs']['hash_entradas'][rel]
    contratos.gravar(job / 'estado.json', estado, 'estado/1')
    assert nucleo.fases_invalidas(job) == set()


# ------------------------------------------------------------------ do job sem folha ao briefing salvo
def test_familias_aparecem_no_passo_3_depois_do_ato(sem_folha):
    job, funcoes = sem_folha
    e = te.montar(job)['estado']
    assert e['passo_3']['texto'] == te.SEM_FORMATOS and e['orientacoes'] == []
    item = next(x for x in e['faltam'] if x['texto'] == te.SEM_FORMATOS_FALTA)
    assert item['detalhe'] == te.SEM_FOLHA_DE_SPEC and 'Valores de spec' in te.SEM_FOLHA_DE_SPEC
    _conteudo, s = tpa._servidor(job)
    try:
        biscoito = tts._entrar(s)
        assert tpa._ato(s, biscoito, ATO, _acrescentar('640x320, 300x600')) == (200, 200)
        e = tpa._estado(s, biscoito)
        assert {f['id'] for f in e['lido']['specs']['formatos']} == {'digitado-tela-640x320', 'digitado-tela-300x600'}
        assert te.SEM_FORMATOS_FALTA not in [x['texto'] for x in e['faltam']]
        assert e['passo_3']['texto'] != te.SEM_FORMATOS  # agora so falta o passo 2
        # o mesmo caminho do job com folha: o passo 2 pelo rascunho, as familias, a versao e o Salvar e seguir
        familias = tpa._ate_salvar(s, biscoito, job, funcoes)
    finally:
        s.parar()
    tpa._depois_do_primeiro_salvar(job, funcoes, familias)
    b = mb.ler(job)
    assert {f['id'] for f in b['formatos']} == {'digitado-tela-640x320', 'digitado-tela-300x600'}
    assert 'specs' not in nucleo.fases_invalidas(job)


# ------------------------------------------------------------------ a folha vale
def test_folha_com_a_mesma_medida_vale_a_folha_e_o_digitado_volta_sem_ela(sem_folha, tmp_path):
    job, _funcoes = sem_folha
    assert _ato(job, _acrescentar('640x320, 300x600'))[:2] == (200, 200)
    folha = tmp_path / 'origem-folha' / 'mesma.html'
    folha.parent.mkdir(parents=True)
    folha.write_text(sap.html_ficha('Mesma Exemplo', [('dimensão', '640x320')]), encoding='utf-8')
    nucleo.trocar_entrada(job, 'entrada/specs/veic/mesma.html', folha)
    assert nucleo.proxima(job, todas=True).codigo == 0
    # revisao do 0.9.2: a folha em rascunho nao cobre o digitado; so a medida confirmada da folha cobre
    assert set(_digitados_no_rascunho(job)) == {'digitado|tela|640x320', 'digitado|tela|300x600'}
    da_folha = next(f for f in _rascunho(job)['formatos'] if not sm.eh_digitado_na_tela(f) and f.get('chave'))
    _confirmar_spec(job, da_folha['campos']['dimensao']['id'])
    doc = _rascunho(job)
    em_px = [sm.medida_em_px(f) for f in doc['formatos']]
    assert em_px.count((640, 320)) == 1  # um formato so, o da folha
    assert set(_digitados_no_rascunho(job)) == {'digitado|tela|300x600'}
    assert dg.lista(job) == [(640, 320), (300, 600)]  # o arquivo do DA fica intacto
    na = {x['medida']: x for x in dg.na_tela(job)['lista']}
    assert na['640 x 320']['na_folha'] is True and na['300 x 600']['na_folha'] is False
    assert dg.conferir(job, _acrescentar('640x320')) in ('ja_na_lista', 'ja_na_folha')
    # o texto do remover do formato coberto diz que nada muda nas pecas
    ato = ta.atos_do_job(job)[ATO]
    assert ato.validar(_remover(640, 320)) and 'folha de spec já traz' in ato.texto(_remover(640, 320))
    assert 'sai do job' in ato.texto(_remover(300, 600))
    # a folha deixa de trazer a medida (outra versao da folha): o formato digitado volta
    folha.write_text(sap.html_ficha('Mesma Exemplo', [('dimensão', '728x90')]), encoding='utf-8')
    nucleo.trocar_entrada(job, 'entrada/specs/veic/mesma.html', folha)
    assert nucleo.proxima(job, todas=True).codigo == 0
    assert set(_digitados_no_rascunho(job)) == {'digitado|tela|640x320', 'digitado|tela|300x600'}
    assert not any(x['na_folha'] for x in dg.na_tela(job)['lista'])


def test_medida_da_folha_recusa_o_digitado_igual(tmp_path):
    job, _funcoes = tpa._criar(tmp_path)
    # revisao do 0.9.2: a medida da folha em rascunho nao recusa (ela ainda nao esta em Formatos e giro)
    assert dg.conferir(job, _acrescentar('640x320')) is None
    da_folha = next(f for f in _rascunho(job)['formatos']
                    if sm.medida_em_px(f) == (640, 320) and not sm.eh_digitado_na_tela(f))
    _confirmar_spec(job, da_folha['campos']['dimensao']['id'])
    assert dg.conferir(job, _acrescentar('640x320')) == 'ja_na_folha'
    assert [640, 320] in dg.na_tela(job)['da_folha']
    assert _ato_do_da(job, _acrescentar('640x320'))[0] == 403


def _formato(fid, chave, medida, folha):
    dim = None
    if medida is not None:
        dim = sm.valor_digitado_na_tela('%s/dimensao' % fid, medida[0], medida[1],
                                        {'por': 'da', 'meio': 'tela', 'em': 'x', 'leitura': None})
    return {'id': fid, 'chave': chave, 'veiculador': chave.split('|')[0] if chave else 'v', 'circuito': 'v:c',
            'entrada': {'folha': folha, 'pagina': None, 'ordem': 1}, 'campos': {'dimensao': dim} if dim else {}}


def test_leitura_divergente_escolhida_cobre_o_digitado():
    doc = {'formatos': [_formato('f1-e01', 'v|c|640x320', (640, 320), 'f12345678'),
                        _formato('digitado-640x320', 'digitado|tela|640x320', (640, 320), 'tela'),
                        _formato('digitado-300x600', 'digitado|tela|300x600', (300, 600), 'tela')],
           'circuitos': [{'id': 'v:c', 'veiculador': 'v'}, {'id': 'digitado:tela', 'veiculador': 'digitado'}],
           'veiculadores': [{'id': 'v', 'folhas': ['f12345678']}, {'id': 'digitado', 'folhas': []}]}
    doc['formatos'][2]['circuito'] = 'digitado:tela'
    doc['formatos'][1]['circuito'] = 'digitado:tela'
    assert sm.tirar_digitados_cobertos(doc) == 1
    assert [f['id'] for f in doc['formatos']] == ['f1-e01', 'digitado-300x600']
    assert {c['id'] for c in doc['circuitos']} == {'v:c', 'digitado:tela'}
    # sem nenhum digitado, o veiculador e o circuito digitado saem
    doc['formatos'] = doc['formatos'][:1]
    sm.tirar_digitados_cobertos(doc)
    assert [c['id'] for c in doc['circuitos']] == ['v:c'] and [v['id'] for v in doc['veiculadores']] == ['v']


# ------------------------------------------------------------------ o Claude nao alcanca o formato digitado
def test_proposta_do_claude_nunca_alcanca_o_digitado(sem_folha):
    from desdobra.sugestao import specs as pacote_specs
    job, _funcoes = sem_folha
    assert _ato(job, _acrescentar('640x320'))[:2] == (200, 200)
    m = sm.Montagem()
    m.adicionar_digitados([{'largura': 640, 'altura': 320,
                            'confirmacao': {'por': 'da', 'meio': 'tela', 'em': 'x', 'leitura': None}}])
    # a proposta com o formato digitado como alvo nao tem trecho: fica de fora
    m.aplicar_propostas([{'folha': 'tela', 'trecho': 'p1-t1', 'campo': 'dimensao', 'alvo': 'digitado-640x320'}],
                        'proposta_do_modelo')
    assert m.contagem['propostas_aplicadas'] == 0
    pacote, _achados = pacote_specs.montar_pacote(_rascunho(job), 'b', job_id='ab' * 16)
    assert not [a for a in pacote['alvos'] if a['id'].startswith('digitado') or a.get('folha') == 'tela']


def test_conferir_literais_aceita_o_digitado_e_recusa_o_numero_de_fora(sem_folha):
    job, _funcoes = sem_folha
    assert _ato(job, _acrescentar('640x320'))[:2] == (200, 200)
    doc = _rascunho(job)
    assert sm.conferir_literais(doc) == []
    dim = next(f for f in doc['formatos'] if sm.eh_digitado_na_tela(f))['campos']['dimensao']
    dim['numeros_literais'] = ['641', '320']
    assert sm.conferir_literais(doc) == [(dim['id'], '641')]


def test_resumo_conta_formatos_digitados_e_zero_nos_jobs_de_folha(tmp_path):
    job, _funcoes = tpa._criar(tmp_path)
    assert _rascunho(job)['resumo']['formatos_digitados'] == 0


def test_contrato_spec_aceita_a_origem_nova_e_recusa_sem_texto_ou_com_fonte():
    v = sm.valor_digitado_na_tela('digitado-640x320/dimensao', 640, 320,
                                  {'por': 'da', 'meio': 'tela', 'em': '2026-11-16T10:00:00-03:00', 'leitura': None})
    fmt = {'id': 'digitado-640x320', 'chave': 'digitado|tela|640x320', 'veiculador': 'digitado',
           'circuito': 'digitado:tela', 'entrada': {'folha': 'tela', 'pagina': None, 'ordem': 1},
           'campos': {'dimensao': v}}
    doc = {'esquema': 'spec/1', 'tipo': 'rascunho', 'gerado_em': None, 'motor_versao': '0.9.2', 'job_id': None,
           'perfis': [], 'folhas': [], 'veiculadores': [], 'circuitos': [], 'formatos': [fmt], 'resumo': {}}
    contratos.validar(doc, 'spec/1')
    for estrago in ({'texto_digitado': None}, {'fonte': {'folha': 'f12345678'}}, {'situacao': 'rascunho'}):
        ruim = json.loads(json.dumps(doc))
        dim = ruim['formatos'][0]['campos']['dimensao']
        for k, x in estrago.items():
            if x is None:
                del dim[k]
            else:
                dim[k] = x
        with pytest.raises(contratos.ErroContrato):
            contratos.validar(ruim, 'spec/1')


# ------------------------------------------------------------------ modo de teste e o job do DA
def test_modo_de_teste_grava_fixture_e_nao_conta_como_decisao_do_da(sem_folha):
    job, _funcoes = sem_folha
    assert not ts._job_do_da(job)
    assert _ato(job, _acrescentar('640x320'))[:2] == (200, 200)
    dados = dg.ler(job)
    assert dados['formatos'][0]['origem'] == 'fixture_de_teste' and dados['formatos'][0]['decidido_por']['meio'] == \
        'medicao'
    dim = next(iter(_digitados_no_rascunho(job).values()))['campos']['dimensao']
    assert dim['confirmacao']['por'] == 'fixture_de_teste'
    assert not ts._job_do_da(job)
    (job / dg.ARQUIVO).write_text('{', encoding='utf-8')
    assert ts._job_do_da(job)  # o arquivo que nao se le conta como do DA


# ------------------------------------------------------------------ gancho e humano
@pytest.mark.parametrize('caminho', ['C:/jobs/kv/briefing/formatos-digitados.json',
                                     'briefing\\formatos-digitados.json', 'formatos-digitados.json'])
def test_gancho_nega_escrever_o_arquivo(caminho):
    g = tts._gancho()
    for ferramenta in ('Write', 'Edit'):
        assert g.decidir({'tool_name': ferramenta, 'tool_input': {'file_path': caminho}}) == 'deny'
    # o nome sozinho, no terminal, com o cwd do evento na pasta briefing do job
    evento = {'tool_name': 'Bash', 'tool_input': {'command': 'echo {} > %s' % caminho}}
    if '/' not in caminho and '\\' not in caminho:
        evento['cwd'] = 'C:/jobs/kv/briefing'
    assert g.decidir(evento) == 'deny'


@pytest.mark.parametrize('comando', [
    'python -c "from desdobra.specs import digitados; digitados.gravar(1, 2, disparo=None)"',
    'python -c "import desdobra.specs.digitados as d"',
    'python -c "from desdobra.specs.digitados import gravar"',
])
def test_gancho_nega_o_codigo_do_ato(comando):
    g = tts._gancho()
    assert g.decidir({'tool_name': 'Bash', 'tool_input': {'command': comando}}) == 'deny'


def test_ato_da_tela_registrado_no_humano():
    assert dg.COMANDO in humano.ATOS_DA_TELA and dg.COMANDO not in humano.COMANDOS
    with pytest.raises(ValueError):
        humano.exigir(dg.COMANDO)


# ------------------------------------------------------------------ a pagina no Chromium
def _valor(pg, seletor, texto):
    pg.evaluate('([s, t]) => { const c = document.querySelector(s); c.value = t; '
                'c.dispatchEvent(new Event("input", {bubbles: true})); }', [seletor, texto])


def _parse_da_pagina(pg):
    return pg.evaluate('() => { const d = document.getElementById("digitados"); '
                       'return [JSON.parse(d.dataset.medidas || "[]"), JSON.parse(d.dataset.codigos || "[]")]; }')


def test_passo_1_no_chromium_colar_confirmar_e_remover(sem_folha):
    """O DA cola a lista, ve a previa e o erro na hora, confirma na janela e remove um formato, tudo por clique. O
    parser da pagina da as mesmas medidas e os mesmos codigos que o do motor."""
    from playwright.sync_api import sync_playwright

    from desdobra.chromium import navegador
    job, _funcoes = sem_folha
    conteudo = te.montar(job)
    pasta = os.environ.get('DESDOBRA_CAPTURA_TELA')
    navegador.apontar_playwright()
    feito = '() => document.documentElement.dataset.estadoAto === "feito" ? "1" : ""'
    with ts.ServidorTela(conteudo, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo)) as srv, sync_playwright() as pw:
        nav = pw.chromium.launch(headless=True, args=list(navegador.ARGUMENTOS))
        pg = nav.new_context(viewport={'width': 1280, 'height': 800}, device_scale_factor=1).new_page()
        try:
            try:
                pg.goto(srv.url_entrada, wait_until='commit')
            except Exception:  # noqa: BLE001 - o 204 nao completa a navegacao
                pass
            pg.goto(srv.url_pagina, wait_until='load')
            tp._esperar(pg, tp.JS_PRONTO)
            # o parser da pagina e o do motor dao o mesmo resultado
            for texto, _m, _c in CASOS_DE_ERRO + [('1080x1920, 300x600', 0, 0), ('1080 x 1920; 300\u00d7600', 0, 0),
                                                  ('1080X1920\n300*600', 0, 0), ('  1080 px x 1920 px ,\r\n', 0, 0),
                                                  ('1.080 x 1.920', 0, 0), ('1.08x1920', 0, 0)]:
                _valor(pg, '#digitados-campo', texto)
                medidas, codigos = _parse_da_pagina(pg)
                m_motor, e_motor = dg.interpretar(texto)
                assert ([tuple(x) for x in medidas], codigos) == (m_motor, [e['codigo'] for e in e_motor]), texto
            # o erro na hora, ligado ao campo
            _valor(pg, '#digitados-campo', '640x320, abc')
            assert pg.evaluate('() => document.getElementById("digitados-acrescentar").disabled') is True
            erro = pg.evaluate('() => document.getElementById("digitados-erro").innerText')
            assert 'abc' in erro and not any(x in erro for x in PROIBIDOS)
            assert 'digitados-erro' in pg.evaluate(
                '() => document.getElementById("digitados-campo").getAttribute("aria-describedby")')
            if pasta:
                pg.locator('#digitados').screenshot(path=os.path.join(pasta, 'digitados-erro.png'))
            # a previa e o Acrescentar
            _valor(pg, '#digitados-campo', '640x320, 300x600')
            assert pg.evaluate('() => document.getElementById("digitados-previa").innerText') == \
                'Vão entrar: 640 x 320 e 300 x 600.'
            if pasta:
                pg.locator('#digitados').screenshot(path=os.path.join(pasta, 'digitados-previa.png'))
            pg.evaluate('() => document.getElementById("digitados-acrescentar").click()')
            pg.wait_for_selector('#confirmacao[open]')
            texto = pg.evaluate('() => document.getElementById("confirmacao-texto").innerText')
            assert '640 x 320 e 300 x 600' in texto
            if pasta:
                pg.screenshot(path=os.path.join(pasta, 'digitados-janela.png'))
            pg.evaluate('() => document.querySelector("#confirmacao [data-resposta=sim]").click()')
            tp._esperar(pg, feito)
            assert pg.evaluate('() => document.querySelectorAll("#digitados-lista li").length') == 2
            assert pg.evaluate('() => document.querySelectorAll("#lido-formatos article").length') == 2
            assert pg.evaluate('() => document.getElementById("digitados-campo").value') == ''
            assert pg.evaluate('() => document.activeElement && document.activeElement.id') == 'digitados-campo'
            nota = pg.evaluate('() => document.getElementById("lido-formatos").innerText')
            assert 'Formato escrito por você, sem folha de spec.' in nota
            assert pg.evaluate('() => document.documentElement.scrollWidth <= window.innerWidth')
            if pasta:
                pg.screenshot(path=os.path.join(pasta, 'digitados-lista.png'), full_page=True)
            # remover um formato, tambem com a janela
            pg.evaluate('() => document.querySelector("#digitados-lista button[aria-label=\'Remover o formato 300 x '
                        '600\']").click()')
            pg.wait_for_selector('#confirmacao[open]')
            assert 'sai do job' in pg.evaluate('() => document.getElementById("confirmacao-texto").innerText')
            pg.evaluate('() => document.querySelector("#confirmacao [data-resposta=sim]").click()')
            tp._esperar(pg, '() => document.querySelectorAll("#digitados-lista li").length === 1 ? "1" : ""')
            assert dg.lista(job) == [(640, 320)]
        finally:
            nav.close()


# ------------------------------------------------------------------ revisao do 0.9.2
def test_revisao_digitado_no_modo_de_teste_barra_entrega_render_e_marca(sem_folha):
    """D1: o formato digitado no modo de teste (origem fixture_de_teste) nunca chega ao master, a entrega nem ao
    registro da marca (que usa o mesmo portao da entrega), como a spec e o texto como imagem do modo de teste."""
    from desdobra.entrega import portao
    from desdobra.render import contrato as mc
    job, _funcoes = sem_folha
    assert portao.confirmacao_de_teste(job) is None
    assert _ato(job, _acrescentar('640x320'))[:2] == (200, 200)
    assert dg.ler(job)['formatos'][0]['origem'] == 'fixture_de_teste'
    assert portao.confirmacao_de_teste(job) == 'confirmacao_de_fixture_de_teste'
    assert 'formato_digitado_no_modo_de_teste' in {b['codigo'] for b in mc.montar(job)[1]}


def test_revisao_digitado_do_da_nao_barra_a_entrega(sem_folha):
    from desdobra.entrega import portao
    from desdobra.render import contrato as mc
    job, _funcoes = sem_folha
    assert _ato_do_da(job, _acrescentar('640x320'))[:2] == (200, 200)
    assert portao.confirmacao_de_teste(job) is None
    assert 'formato_digitado_no_modo_de_teste' not in {b['codigo'] for b in mc.montar(job)[1]}


def _medidas_do_job(job):
    fj = contratos.ler(job / importar.ARQUIVO_FORMATOS, 'spec/1')
    return {sm.medida_em_px(f) for f in fj['formatos']}


def _chega_folha(job, tmp_path, medida='640x320'):
    folha = tmp_path / 'origem-folha' / 'mesma.html'
    folha.parent.mkdir(parents=True, exist_ok=True)
    folha.write_text(sap.html_ficha('Mesma Exemplo', [('dimensão', medida)]), encoding='utf-8')
    nucleo.trocar_entrada(job, 'entrada/specs/veic/mesma.html', folha)
    assert nucleo.proxima(job, todas=True).codigo == 0


def test_revisao_folha_em_rascunho_nao_tira_o_digitado_confirmado(sem_folha, tmp_path):
    """D2: a folha que chega depois com a mesma medida, ainda sem confirmar, nao tira do job o formato que o DA ja
    confirmou; so a folha confirmada cobre o digitado. A recusa ja_na_folha vale so para a medida confirmada."""
    job, _funcoes = sem_folha
    assert _ato_do_da(job, _acrescentar('640x320, 300x600'))[:2] == (200, 200)
    _chega_folha(job, tmp_path)
    assert _medidas_do_job(job) == {(640, 320), (300, 600)}
    assert set(_digitados_no_rascunho(job)) == {'digitado|tela|640x320', 'digitado|tela|300x600'}
    assert not any(x['na_folha'] for x in dg.na_tela(job)['lista'])
    giro = {(f['largura'], f['altura']) for f in te.montar(job)['estado']['lido']['specs']['formatos']}
    assert (640, 320) in giro
    assert dg.medidas_da_folha(dg.rascunho_gravado(job)) == set()


def test_revisao_arquivo_de_outro_job_nao_vale_e_nao_e_sobrescrito(sem_folha):
    """D3: o arquivo de outro job (uma copia) nao entra no job, e o ato recusa em vez de gravar por cima."""
    job, _funcoes = sem_folha
    assert _ato_do_da(job, _acrescentar('640x320'))[:2] == (200, 200)
    dados = dg.ler(job)
    dados['job_id'] = 'ff' * 16
    contratos.gravar(job / dg.ARQUIVO, dados, dg.ESQUEMA)
    importar.importar(job)
    assert dg.lista(job) == [] and not _digitados_no_rascunho(job)
    assert dg.ler_com_problema(job)[1] == 'outro_job'
    assert dg.conferir(job, _acrescentar('300x600')) == 'lista_ilegivel'
    assert dg.na_tela(job)['problema'] == dg.MENSAGENS['lista_ilegivel']


def test_revisao_arquivo_ilegivel_recusa_o_ato_e_guarda_o_historico(sem_folha):
    """D4: o arquivo fora do contrato nao some em silencio nem e gravado por cima, sem o historico."""
    job, _funcoes = sem_folha
    assert _ato_do_da(job, _acrescentar('640x320'))[:2] == (200, 200)
    bruto = json.loads((job / dg.ARQUIVO).read_text(encoding='utf-8'))
    bruto['formatos'][0]['largura'] = 'x'
    (job / dg.ARQUIVO).write_text(json.dumps(bruto), encoding='utf-8')
    assert dg.ler_com_problema(job)[1] == 'ilegivel'
    assert dg.conferir(job, _acrescentar('300x600')) == 'lista_ilegivel'
    assert dg.conferir(job, _remover(640, 320)) == 'lista_ilegivel'
    assert _ato_do_da(job, _acrescentar('300x600'))[0] == 403
    assert json.loads((job / dg.ARQUIVO).read_text(encoding='utf-8')) == bruto
    texto = dg.mensagem({'codigo': 'lista_ilegivel'})
    assert texto and not any(x in texto for x in PROIBIDOS)


@pytest.mark.parametrize('texto,esperado', [
    ('1.080 x 1.920', [(1080, 1920)]),
    ('1.080x1.920, 300x600', [(1080, 1920), (300, 600)]),
    ('10.000x1.000', [(10000, 1000)]),
])
def test_revisao_milhar_com_ponto(texto, esperado):
    """D6: o DA brasileiro escreve o milhar com ponto; o numero quebrado continua recusado."""
    assert dg.interpretar(texto) == (esperado, [])


@pytest.mark.parametrize('texto', ['1.08x1920', '1.0800x600', '1080.5x1920'])
def test_revisao_numero_quebrado_continua_recusado(texto):
    assert [e['codigo'] for e in dg.interpretar(texto)[1]] == ['nao_inteiro']


def test_revisao_folha_do_veiculador_digitado_nao_vira_formato_digitado(tmp_path):
    """D5: a pasta entrada/specs/digitado/ da a folha um veiculador proprio, sem colidir com o dos formatos escritos
    na tela."""
    folhas = {'digitado/ficha.html': sap.html_ficha('Mesma Exemplo', [('dimensão', '640x320')])}
    job, _f = tpa._criar(tmp_path, folhas=folhas)
    e = te.montar(job)['estado']
    assert e['lido']['specs']['formatos'] and not any(f['digitado'] for f in e['lido']['specs']['formatos'])
    assert sm.VEICULADOR_DIGITADO not in {v['id'] for v in _rascunho(job)['veiculadores']}


def test_revisao_gancho_nega_o_modulo_montado_em_partes():
    """D7: o nome do modulo montado em partes com importacao dinamica tambem e negado, como em sugestoes/."""
    g = tts._gancho()
    comando = ('python -c "import desdobra.specs as s, importlib; importlib.import_module(s.__name__ + '
               '\'.digitados\')"')
    assert g.decidir({'tool_name': 'Bash', 'tool_input': {'command': comando}, 'cwd': 'C:/jobs/kv'}) == 'deny'
