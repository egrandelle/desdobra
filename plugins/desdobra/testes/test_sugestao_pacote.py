# -*- coding: utf-8 -*-
"""Rascunho do pacote para o modelo (pacote-modelo/1) por modo de dados."""
import json

import pytest

from desdobra import contratos
from desdobra.sugestao import pacote
from test_sugestao_apoio import ARQUIVO_CLIENTE, CAMINHO_CLIENTE, camada, laudo, laudo_cheio_de_conteudo


def _estado(modo, teto=None):
    return {'esquema': 'estado/1', 'job_id': '0' * 32, 'criado_em': '2026-10-29T10:00:00-03:00',
            'atualizado_em': '2026-10-29T10:00:00-03:00', 'motor_versao': '0.1.0', 'modo_dados': modo,
            'teto_modo_dados': teto, 'entradas': {}, 'fases': {},
            'proxima': {'tipo': 'concluido', 'fase': None, 'o_que_fazer': 'nada'}}


@pytest.mark.parametrize('modo', ['a', 'b', 'c'])
def test_pacote_valida_e_nunca_leva_segredo(modo):
    la, _, falsos = laudo_cheio_de_conteudo()
    p, achados = pacote.montar_pacote(la, modo, job_id='0' * 32)
    contratos.validar(p, 'pacote-modelo/1')
    bruto = json.dumps(p, ensure_ascii=False)
    for s in falsos:
        assert s not in bruto
    assert len(achados) == 2 * len(falsos) == p['contagens']['segredos_bloqueados']
    bloqueadas = [c for c in p['camadas'] if c.get('segredo_bloqueado')]
    assert len(bloqueadas) == 2 * len(falsos)
    assert all('nome' not in c and 'textos' not in c for c in bloqueadas)
    assert p['miniaturas'] == [] and p['exposto']['miniaturas'] is False
    assert ARQUIVO_CLIENTE not in bruto and CAMINHO_CLIENTE not in bruto


def test_modo_c_so_contagens_estados_e_ids():
    la, textos, _ = laudo_cheio_de_conteudo()
    p, _ = pacote.montar_pacote(la, 'c')
    bruto = json.dumps(p, ensure_ascii=False)
    for t in textos:
        assert t not in bruto
    assert 'fontes_usadas' not in p and p['exposto'] == {'metadados': False, 'textos': False, 'miniaturas': False}
    assert set(p['camadas'][0]) <= {'layer_id', 'pai_id', 'tipo', 'situacao', 'regras', 'segredo_bloqueado'}


def test_modo_b_leva_metadados_e_textos():
    la, _, _ = laudo_cheio_de_conteudo()
    p, _ = pacote.montar_pacote(la, 'b')
    por_id = {c['layer_id']: c for c in p['camadas']}
    assert por_id[2]['textos'] == ['Promoção Fictícia Lilás'] and por_id[2]['nome']
    assert por_id[4]['regras'] == ['D8'] and por_id[6]['pai_id'] == 5
    assert p['fontes_usadas'][0]['fonte_ps']


def test_esquema_recusa_nome_no_modo_c():
    la = laudo([camada(1, 'Fundo Ficticio')])
    p, _ = pacote.montar_pacote(la, 'c')
    p['camadas'][0]['nome'] = 'Fundo Ficticio'
    with pytest.raises(contratos.ErroContrato):
        contratos.validar(p, 'pacote-modelo/1')


def test_coberta_no_kv_leva_so_a_sugestao_citada():
    cob = {'coberta': True, 'fracao_coberta': 1.0, 'ocupa_canvas': True, 'fracao_canvas': 1.0, 'limites': [],
           'sugestao_da_regra': {'funcao': 'estrutura', 'regra': 'decisao-10',
                                 'fonte': {'arquivo': 'decisoes-v1.md', 'secao': '29/10, 10'}}}
    p, _ = pacote.montar_pacote(laudo([camada(1, 'Fundo', tipo='cor_solida', coberta=cob)]), 'b')
    assert p['camadas'][0]['coberta_no_kv'] == {'coberta': True, 'ocupa_canvas': True,
                                                 'sugestao_da_regra': {'funcao': 'estrutura', 'regra': 'decisao-10'}}


def test_gravar_pacote_respeita_o_teto_do_job(tmp_path):
    la, textos, falsos = laudo_cheio_de_conteudo()
    try:
        contratos.validar(la, 'laudo/1')
    except contratos.ErroContrato as e:
        pytest.fail('o laudo sintetico deixou de valer contra laudo/1: %s' % e)
    contratos.gravar(tmp_path / 'estado.json', _estado('a', teto='c'), 'estado/1')
    contratos.gravar(tmp_path / 'laudo' / 'laudo.json', la, 'laudo/1')
    destino, n = pacote.gravar_pacote(tmp_path)
    p = contratos.ler(destino, 'pacote-modelo/1')
    assert p['modo_dados'] == 'c' and n == 2 * len(falsos)
    bruto = destino.read_text(encoding='utf-8')
    for t in textos + falsos:
        assert t not in bruto
    assert (tmp_path / 'sugestoes' / 'segredos-bloqueados.json').is_file()


def test_conteudo_para_resultado():
    la = laudo([camada(1, 'A'), camada(2, 'B', tipo='texto', texto='Olá')])
    assert pacote.conteudo_para_resultado(la) == {'camadas': [
        {'layer_id': 1, 'nome': 'A', 'tipo': 'pixel', 'situacao': 'lida', 'textos': []},
        {'layer_id': 2, 'nome': 'B', 'tipo': 'texto', 'situacao': 'lida', 'textos': ['Olá']}]}
