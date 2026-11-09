# -*- coding: utf-8 -*-
"""Historico do briefing com indice encadeado (M7b, A4; desdobra.briefing.historico).

Cada gravacao do briefing (briefing.modelo.gravar_com_historico) deixa uma entrada em briefing/historico/indice.json:
numero em sequencia, sha anterior e novo do briefing, carimbo, origem e meio, formatos afetados e o sha da entrada
anterior (a cadeia). Apagar, trocar ou reordenar uma entrada e detectado na leitura e vira aviso na tela. A cadeia so
pega a adulteracao ingenua (risco 177 continua: quem reescreve o indice inteiro passa). Material sintetico
(test_derivacao_apoio), sem PSD."""
import json

import pytest

import test_derivacao_apoio as ap
from desdobra import arquivos, contratos
from desdobra.briefing import historico as bh
from desdobra.briefing import modelo as mb


def _gravar(pasta, quando, afetados=None, **mudar):
    b = ap.briefing()
    b['cabecalho'] = dict(b['cabecalho'], quando=quando)
    b.update(mudar)
    return mb.gravar_com_historico(pasta, b, afetados=afetados)


@pytest.fixture
def tres(tmp_path):
    """Tres gravacoes seguidas, cada uma com um briefing diferente."""
    shas = []
    for k, quando in enumerate(('2026-11-06T10:00:00-03:00', '2026-11-06T10:05:00-03:00',
                                '2026-11-06T10:10:00-03:00')):
        _gravar(tmp_path, quando, afetados=None if k == 0 else ['f%d' % k])
        shas.append(arquivos.sha256_arquivo(tmp_path / mb.ARQUIVO))
    return tmp_path, shas


def _indice(pasta):
    return json.loads((pasta / bh.ARQUIVO).read_text(encoding='utf-8'))


def _regravar(pasta, dados):
    (pasta / bh.ARQUIVO).write_text(json.dumps(dados), encoding='utf-8')


def test_tres_gravacoes_deixam_tres_entradas_em_ordem_e_encadeadas(tres):
    pasta, shas = tres
    dados = contratos.ler(pasta / bh.ARQUIVO, bh.ESQUEMA)
    e = dados['entradas']
    assert [x['seq'] for x in e] == [1, 2, 3]
    assert [x['sha_anterior'] for x in e] == [None, shas[0], shas[1]]
    assert [x['sha_novo'] for x in e] == shas
    assert [x['formatos_afetados'] for x in e] == [None, ['f1'], ['f2']]
    assert {(x['origem'], x['meio']) for x in e} == {(mb.ORIGEM_FIXTURE, 'importar_teste')}
    assert all(x['quando'] for x in e)
    assert e[0]['sha_entrada_anterior'] is None
    assert e[1]['sha_entrada_anterior'] == bh.sha_da_entrada(e[0])
    assert e[2]['sha_entrada_anterior'] == bh.sha_da_entrada(e[1])
    assert bh.conferir(pasta) == []
    assert bh.avisos(pasta) == []
    # a versao anterior continua guardada em briefing/historico/<sha>.json, como antes do indice
    assert all((pasta / mb.PASTA_HISTORICO / ('%s.json' % s)).is_file() for s in shas[:2])


def test_primeira_gravacao_sem_versao_anterior(tmp_path):
    assert _gravar(tmp_path, '2026-11-06T10:00:00-03:00') is None
    e = _indice(tmp_path)['entradas']
    assert len(e) == 1 and e[0]['seq'] == 1 and e[0]['sha_anterior'] is None
    assert bh.conferir(tmp_path) == []


def test_sem_indice_nao_avisa(tmp_path):
    # job gravado antes do indice (ou sem briefing): nada a conferir; a proxima gravacao abre o indice
    assert bh.conferir(tmp_path) == [] and bh.avisos(tmp_path) == []


def test_apagar_uma_entrada_no_meio_e_detectado(tres):
    pasta, _shas = tres
    dados = _indice(pasta)
    del dados['entradas'][1]
    _regravar(pasta, dados)
    codigos = {p['codigo'] for p in bh.conferir(pasta)}
    assert {'sequencia_quebrada', 'cadeia_quebrada', 'versoes_desencadeadas'} <= codigos
    assert bh.avisos(pasta) == [bh.AVISO_HISTORICO_MEXIDO]


def test_trocar_uma_entrada_no_meio_e_detectado(tres):
    pasta, _shas = tres
    dados = _indice(pasta)
    dados['entradas'][1]['formatos_afetados'] = ['outro']
    _regravar(pasta, dados)
    problemas = bh.conferir(pasta)
    assert {'codigo': 'cadeia_quebrada', 'seq': 3} in problemas
    assert bh.avisos(pasta) == [bh.AVISO_HISTORICO_MEXIDO]


def test_reordenar_entradas_e_detectado(tres):
    pasta, _shas = tres
    dados = _indice(pasta)
    dados['entradas'][1], dados['entradas'][2] = dados['entradas'][2], dados['entradas'][1]
    _regravar(pasta, dados)
    assert 'sequencia_quebrada' in {p['codigo'] for p in bh.conferir(pasta)}


def test_briefing_trocado_fora_do_gravador_e_detectado(tres):
    pasta, _shas = tres
    b = contratos.ler(pasta / mb.ARQUIVO, mb.ESQUEMA)
    b['cabecalho']['quando'] = '2026-11-06T11:00:00-03:00'
    contratos.gravar(pasta / mb.ARQUIVO, b, mb.ESQUEMA)
    assert bh.conferir(pasta) == [{'codigo': 'briefing_fora_do_indice', 'seq': 3}]
    assert bh.avisos(pasta) == [bh.AVISO_BRIEFING_FORA]


def test_indice_ilegivel_e_detectado(tres):
    pasta, _shas = tres
    (pasta / bh.ARQUIVO).write_text('{"esquema": "historico-indice/1"', encoding='utf-8')
    assert [p['codigo'] for p in bh.conferir(pasta)] == ['indice_invalido']
    assert bh.avisos(pasta) == [bh.AVISO_INDICE_INVALIDO]


def test_gravar_por_cima_de_indice_mexido_segue_e_o_aviso_fica(tres):
    # o DA nao fica preso: a gravacao segue, encadeada na ultima entrada, e a quebra antiga continua no aviso
    pasta, _shas = tres
    dados = _indice(pasta)
    del dados['entradas'][1]
    _regravar(pasta, dados)
    _gravar(pasta, '2026-11-06T12:00:00-03:00')
    e = _indice(pasta)['entradas']
    assert [x['seq'] for x in e] == [1, 3, 4]
    assert e[-1]['sha_entrada_anterior'] == bh.sha_da_entrada(e[-2])
    assert e[-1]['sha_novo'] == arquivos.sha256_arquivo(pasta / mb.ARQUIVO)
    assert bh.avisos(pasta) == [bh.AVISO_HISTORICO_MEXIDO]


def test_gravar_por_cima_de_indice_ilegivel_guarda_o_velho_e_o_aviso_fica(tres):
    pasta, _shas = tres
    (pasta / bh.ARQUIVO).write_text('{', encoding='utf-8')
    _gravar(pasta, '2026-11-06T12:00:00-03:00')
    guardados = list((pasta / mb.PASTA_HISTORICO).glob('indice-invalido-*.json'))
    assert len(guardados) == 1 and guardados[0].read_text(encoding='utf-8') == '{'
    dados = contratos.ler(pasta / bh.ARQUIVO, bh.ESQUEMA)
    assert dados['reiniciado_de'] == guardados[0].name
    assert [x['seq'] for x in dados['entradas']] == [1]
    assert [p['codigo'] for p in bh.conferir(pasta)] == ['indice_reiniciado']
    assert bh.avisos(pasta) == [bh.AVISO_HISTORICO_MEXIDO]


def test_avisos_vao_para_a_faixa_da_tela(tres, monkeypatch):
    from desdobra.tela import estado as te
    pasta, _shas = tres
    monkeypatch.setattr(te, 'avisos_de_retomada', lambda p, g: [])
    assert te._avisos_do_job(pasta) == []
    dados = _indice(pasta)
    del dados['entradas'][0]
    _regravar(pasta, dados)
    assert te._avisos_do_job(pasta) == [bh.AVISO_HISTORICO_MEXIDO]


def test_avisos_em_portugues_sem_travessao():
    for t in (bh.AVISO_HISTORICO_MEXIDO, bh.AVISO_BRIEFING_FORA, bh.AVISO_INDICE_INVALIDO):
        assert '—' not in t and '–' not in t and t.endswith('.')
