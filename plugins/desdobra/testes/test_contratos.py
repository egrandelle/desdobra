# -*- coding: utf-8 -*-
import json

import pytest
from jsonschema.validators import validator_for

from desdobra import contratos
from desdobra.contratos import ErroContrato


def test_todos_os_esquemas_sao_validos_e_batem_com_o_nome():
    nomes = contratos.listar_esquemas()
    assert {'estado/1', 'estrutura/1', 'laudo/1', 'envelope/1', 'fontes-de-limites/1', 'recusa/1'} <= set(nomes)
    for nome in nomes:
        esquema = contratos.carregar_esquema(nome)
        validator_for(esquema).check_schema(esquema)
        assert esquema['properties']['esquema'] == {'const': nome}
        assert esquema['$id'] == 'urn:desdobra:schema:%s' % nome.replace('/', ':')


def test_nome_de_contrato_invalido():
    with pytest.raises(ValueError):
        contratos.arquivo_do_esquema('estado')
    with pytest.raises(ErroContrato, match='esquema não encontrado'):
        contratos.carregar_esquema('naoexiste/1')


def _estado_valido():
    return {'esquema': 'estado/1', 'job_id': '0' * 32, 'criado_em': '2026-10-29T10:00:00-03:00',
            'atualizado_em': '2026-10-29T10:00:00-03:00', 'motor_versao': '0.1.0', 'modo_dados': 'c',
            'teto_modo_dados': None, 'entradas': {}, 'fases': {},
            'proxima': {'tipo': 'concluido', 'fase': None, 'o_que_fazer': 'nada'}}


def test_erro_claro_com_campo():
    estado = _estado_valido()
    estado['modo_dados'] = 'z'
    with pytest.raises(ErroContrato) as e:
        contratos.validar(estado, 'estado/1', origem='estado.json')
    texto = str(e.value)
    assert 'estado.json' in texto and 'estado/1' in texto and '/modo_dados' in texto
    assert e.value.onde == '/modo_dados'


def test_campo_esquema_tem_de_bater():
    estado = _estado_valido()
    contratos.validar(estado, 'estado/1')
    estado['esquema'] = 'estado/2'
    with pytest.raises(ErroContrato):
        contratos.validar(estado, 'estado/1')


def test_gravar_e_atomico_e_valida_antes(tmp_path):
    destino = tmp_path / 'estado.json'
    contratos.gravar(destino, _estado_valido(), 'estado/1')
    original = destino.read_bytes()
    ruim = _estado_valido()
    ruim['job_id'] = 'x'
    with pytest.raises(ErroContrato):
        contratos.gravar(destino, ruim, 'estado/1')
    assert destino.read_bytes() == original
    assert [p.name for p in tmp_path.iterdir()] == ['estado.json']
    assert contratos.ler(destino, 'estado/1')['job_id'] == '0' * 32


def test_ler_arquivo_ausente_ou_quebrado(tmp_path):
    with pytest.raises(ErroContrato, match='arquivo não encontrado'):
        contratos.ler(tmp_path / 'nada.json', 'estado/1')
    (tmp_path / 'quebrado.json').write_text('{', encoding='utf-8')
    with pytest.raises(ErroContrato, match='JSON inválido'):
        contratos.ler(tmp_path / 'quebrado.json', 'estado/1')


def _envelope(modo, **extra):
    base = {'esquema': 'envelope/1', 'modo_dados': modo, 'comando': 'ler', 'fase': None, 'situacao': 'ok',
            'codigo': 0, 'o_que_fazer': None, 'contagens': {'camadas': 3}, 'ids': {'job_id': 'ab' * 16},
            'numeros': {'tempo_s': 1.5}, 'segredos_bloqueados': 0}
    base.update(extra)
    return base


def test_envelope_respeita_o_modo():
    contratos.validar(_envelope('c'), 'envelope/1')
    with pytest.raises(ErroContrato):
        contratos.validar(_envelope('c', conteudo={'camadas': []}), 'envelope/1')
    contratos.validar(_envelope('b', conteudo={'camadas': [{'layer_id': 4, 'nome': 'x', 'textos': ['y']}]}), 'envelope/1')
    with pytest.raises(ErroContrato):
        contratos.validar(_envelope('b', conteudo={'miniaturas': ['sugestoes/miniaturas/4.png']}), 'envelope/1')
    contratos.validar(_envelope('a', conteudo={'miniaturas': ['sugestoes/miniaturas/4.png']}), 'envelope/1')
    with pytest.raises(ErroContrato):
        contratos.validar(_envelope('a', conteudo={'miniaturas': ['laudo/miniaturas/4.png']}), 'envelope/1')


def test_envelope_nao_aceita_nome_de_arquivo_em_ids():
    with pytest.raises(ErroContrato):
        contratos.validar(_envelope('c', ids={'arquivo': 'kv final.psd'}), 'envelope/1')


def test_laudo_minimo_valido_e_d9_aposentada():
    laudo = {
        'esquema': 'laudo/1',
        'origem': {'arquivo': 'teste.psd', 'sha256': 'a' * 64, 'bytes': 10, 'gravado_por': {'programa': None, 'versao': None},
                   'psd_tools': '1.26.0', 'motor': '0.1.0'},
        'documento': {'largura': 1, 'altura': 1, 'modo': 'RGB', 'bits': 8, 'icc': None, 'pranchetas': [],
                      'layer_comps': [], 'tem_previa': True, 'quadros': [], 'variantes_ocultas': []},
        'camadas': [], 'fontes_usadas': [],
        'prova_pixel': {'feita': False, 'motivo': 'sem_merged',
                        'limiar': {'limite_id': 'prova_pixel.limiar_diferenca', 'valor': 24, 'situacao': 'medido',
                                   'efeito': 'registra'}},
        'regras': {'B1': {'descricao': 'x', 'situacao': 'bloqueante', 'fonte': {'arquivo': 'pesquisa/corpus-testes.md'}}},
        'recusas': [], 'recursos': {'tempo_s': 0.1, 'orcamento_bytes': 1},
        'resumo': {'n_camadas': 0, 'por_situacao': {'lida': 0, 'degradada': 0, 'bloqueante': 0},
                   'por_situacao_visiveis': {'lida': 0, 'degradada': 0, 'bloqueante': 0}, 'por_regra': {}, 'n_quadros': 0},
    }
    contratos.validar(laudo, 'laudo/1')
    laudo['regras']['D9'] = {'descricao': 'x', 'situacao': 'degradada', 'fonte': {'arquivo': 'pesquisa/x.md'}}
    with pytest.raises(ErroContrato):
        contratos.validar(laudo, 'laudo/1')


def test_coberta_no_kv_e_sugestao_nunca_valor():
    esquema = contratos.carregar_esquema('laudo/1')
    coberta = esquema['$defs']['coberta']
    assert 'funcao' not in coberta['properties']
    assert coberta['properties']['sugestao_da_regra']['oneOf'][1]['properties']['regra'] == {'const': 'decisao-10'}


def test_registro_de_limites_segue_o_contrato():
    from desdobra.limites import ARQUIVO_REGISTRO
    contratos.ler(ARQUIVO_REGISTRO, 'fontes-de-limites/1')
    dados = json.loads(ARQUIVO_REGISTRO.read_text(encoding='utf-8'))
    ruim = dict(dados['limites'][0], id='teste.ruim', situacao='a_calibrar', efeito='reprova')
    with pytest.raises(ErroContrato):
        contratos.validar({'esquema': 'fontes-de-limites/1', 'limites': [ruim]}, 'fontes-de-limites/1')


def test_estrutura_declara_as_contagens_inteiras_de_pixel():
    from test_laudo_regras import camada, estrutura
    px = {'erro': None, 'pulado': None, 'fracao_coberta': 0.5, 'fracao_canvas': 0.5, 'px_visiveis': 10,
          'px_cobertos': 5, 'px_area_ref': 20}
    est = estrutura([camada(1, pixels=px)])
    est['prova_pixel'] = {'feita': True, 'motivo': None, 'px_acima_qualquer_canal': 3, 'px_total': 5000}
    contratos.validar(est, 'estrutura/1')
    for campo, valor in (('px_visiveis', 10.5), ('px_cobertos', '5'), ('px_area_ref', -1), ('pulado', 3)):
        ruim = estrutura([camada(1, pixels=dict(px, **{campo: valor}))])
        with pytest.raises(ErroContrato):
            contratos.validar(ruim, 'estrutura/1')
    for campo, valor in (('px_acima_qualquer_canal', 2.5), ('px_total', '5000')):
        ruim = estrutura([camada(1, pixels=px)])
        ruim['prova_pixel'] = dict(est['prova_pixel'], **{campo: valor})
        with pytest.raises(ErroContrato):
            contratos.validar(ruim, 'estrutura/1')
