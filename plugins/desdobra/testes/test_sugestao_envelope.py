# -*- coding: utf-8 -*-
"""Envelope de saida: filtro por modo de dados e detector de segredos, pela funcao unica de impressao.

O teste principal roda a impressao sobre um laudo sintetico cheio de nomes e textos e confere, por varredura
da linha impressa, que no modo c nada disso aparece, e que segredo nao aparece em modo nenhum.
"""
import hashlib
import io
import json

import pytest

from desdobra import cli, contratos
from desdobra.resultado import Codigo, Resultado
from desdobra.sugestao import envelope, pacote, segredos
from test_sugestao_apoio import CAMINHO_CLIENTE, laudo_cheio_de_conteudo


def _resultado(laudo, pasta_job=None, **extra):
    return Resultado(comando='ler', fase='ler', o_que_fazer='Leitura concluída. Confira o laudo na tela.',
                     contagens={'camadas': len(laudo['camadas'])}, ids={'arquivo_sha256': laudo['origem']['sha256']},
                     numeros={'tempo_s': 1.5}, conteudo=pacote.conteudo_para_resultado(laudo), pasta_job=pasta_job,
                     linhas_humanas=['Arquivo: ' + CAMINHO_CLIENTE], **extra)


def _imprimir(resultado, modo):
    fluxo = io.StringIO()
    env = envelope.imprimir(resultado, modo, fluxo=fluxo)
    linha = fluxo.getvalue()
    assert linha.endswith('\n') and linha.count('\n') == 1
    dados = json.loads(linha)
    contratos.validar(dados, 'envelope/1')
    assert dados == env
    return linha, dados


def _variantes(texto):
    """O texto e o jeito como ele sairia escapado no JSON."""
    return {texto, json.dumps(texto, ensure_ascii=False)[1:-1], json.dumps(texto)[1:-1]}


def test_modo_c_nao_imprime_nome_texto_nem_caminho(tmp_path):
    laudo, textos, falsos = laudo_cheio_de_conteudo()
    linha, env = _imprimir(_resultado(laudo, pasta_job=tmp_path), 'c')
    assert env['modo_dados'] == 'c' and 'conteudo' not in env
    for texto in textos + falsos:
        for v in _variantes(texto):
            assert v not in linha, 'vazou no modo c: %r' % texto
    assert env['segredos_bloqueados'] == 2 * len(falsos)
    assert env['contagens'] == {'camadas': len(laudo['camadas'])}


@pytest.mark.parametrize('modo', ['a', 'b', 'c'])
def test_segredo_nunca_sai_e_vai_so_para_o_arquivo_do_da(tmp_path, modo):
    laudo, _, falsos = laudo_cheio_de_conteudo()
    linha, env = _imprimir(_resultado(laudo, pasta_job=tmp_path), modo)
    for s in falsos:
        for v in _variantes(s):
            assert v not in linha
    assert env['segredos_bloqueados'] == 2 * len(falsos)
    arquivo = tmp_path / 'sugestoes' / 'segredos-bloqueados.json'
    dados = contratos.ler(arquivo, 'segredos-bloqueados/1')
    assert dados['total'] == 2 * len(falsos)
    bruto = arquivo.read_text(encoding='utf-8')
    for s in falsos:
        assert s not in bruto
    # nada foi para o log do job
    assert not (tmp_path / 'log').exists()


def test_modo_b_leva_camadas_limpas_e_sem_miniaturas(tmp_path):
    laudo, _, _ = laudo_cheio_de_conteudo()
    resultado = _resultado(laudo, pasta_job=tmp_path)
    resultado.conteudo['miniaturas'] = ['sugestoes/miniaturas/1.png']
    _, env = _imprimir(resultado, 'b')
    camadas = {c['layer_id']: c for c in env['conteudo']['camadas']}
    assert set(camadas) == {1, 2, 3, 4, 5, 6}
    assert camadas[2]['textos'] == ['Promoção Fictícia Lilás']
    assert camadas[4]['situacao'] == 'degradada'
    assert 'miniaturas' not in env['conteudo']


def _indice(job, ids, corromper=()):
    """sugestoes/miniaturas/ como gravar_miniaturas deixa (M7c, S1), com PNG sintetico."""
    pasta = job / 'sugestoes' / 'miniaturas'
    pasta.mkdir(parents=True, exist_ok=True)
    itens = []
    for lid in ids:
        dados = b'png-sintetico-%d' % lid
        (pasta / ('%d.png' % lid)).write_bytes(dados + (b'!' if lid in corromper else b''))
        itens.append({'layer_id': lid, 'sha256': hashlib.sha256(dados).hexdigest()})
    (pasta / 'indice.json').write_text(json.dumps({'miniaturas': itens}), encoding='utf-8')


def test_modo_a_so_miniaturas_de_camadas_sem_texto(tmp_path):
    laudo, _, _ = laudo_cheio_de_conteudo()
    _indice(tmp_path, [1, 2, 4, 6])
    resultado = _resultado(laudo, pasta_job=tmp_path)
    resultado.conteudo['miniaturas'] = ['sugestoes/miniaturas/1.png', 'sugestoes/miniaturas/2.png',
                                        {'layer_id': 4, 'arquivo': 'sugestoes/miniaturas/4.png'},
                                        'laudo/miniaturas/6.png', 'sugestoes/miniaturas/10.png',
                                        'sugestoes/miniaturas/../../kv.png']
    _, env = _imprimir(resultado, 'a')
    assert env['conteudo']['miniaturas'] == ['sugestoes/miniaturas/1.png', 'sugestoes/miniaturas/4.png']


def test_modo_a_sem_indice_nao_lista_miniatura(tmp_path):
    # M7c, S2: o envelope lista so o que esta no indice.json do job
    laudo, _, _ = laudo_cheio_de_conteudo()
    resultado = _resultado(laudo, pasta_job=tmp_path)
    resultado.conteudo['miniaturas'] = ['sugestoes/miniaturas/1.png', 'sugestoes/miniaturas/4.png']
    _, env = _imprimir(resultado, 'a')
    assert env['conteudo']['miniaturas'] == []
    _, env = _imprimir(_resultado(laudo), 'a')
    assert env['conteudo']['miniaturas'] == []


def test_modo_a_fora_do_indice_ou_com_sha_trocado_fica_de_fora(tmp_path):
    laudo, _, _ = laudo_cheio_de_conteudo()
    _indice(tmp_path, [1, 4], corromper={4})
    (tmp_path / 'sugestoes' / 'miniaturas' / '6.png').write_bytes(b'fora do indice')
    resultado = _resultado(laudo, pasta_job=tmp_path)
    resultado.conteudo['miniaturas'] = ['sugestoes/miniaturas/1.png', 'sugestoes/miniaturas/4.png',
                                        'sugestoes/miniaturas/6.png']
    _, env = _imprimir(resultado, 'a')
    assert env['conteudo']['miniaturas'] == ['sugestoes/miniaturas/1.png']


def test_modo_a_sem_lista_no_conteudo_usa_o_indice(tmp_path):
    # o conteudo do ler nao traz miniaturas: o envelope do modo (a) lista as do indice, so de camada sem texto
    laudo, _, _ = laudo_cheio_de_conteudo()
    _indice(tmp_path, [1, 2, 6])
    _, env = _imprimir(_resultado(laudo, pasta_job=tmp_path), 'a')
    assert env['conteudo']['miniaturas'] == ['sugestoes/miniaturas/1.png', 'sugestoes/miniaturas/6.png']
    for modo in ('b', 'c'):
        _, env = _imprimir(_resultado(laudo, pasta_job=tmp_path), modo)
        assert 'miniaturas' not in (env.get('conteudo') or {})


def test_campos_fixos_fora_do_contrato_sao_descartados():
    r = Resultado(comando='Comando Estranho', fase='Fase/1', contagens={'ok': 2, 'Chave Ruim': 3, 'flag': True,
                                                                       'texto': 'x'},
                  ids={'arquivo_sha256': 'ab' * 32, 'caminho': CAMINHO_CLIENTE, 'layer_id': 4, 'lista': [1, 2],
                       'sujo': [1, 'a']},
                  numeros={'tempo_s': 1.25, 'nan': float('nan'), 'texto': 'x'})
    _, env = _imprimir(r, 'b')
    assert env['comando'] == 'desdobra' and env['fase'] is None
    assert env['contagens'] == {'ok': 2, 'flag': 1}
    assert env['ids'] == {'arquivo_sha256': 'ab' * 32, 'layer_id': 4, 'lista': [1, 2]}
    assert env['numeros'] == {'tempo_s': 1.25, 'nan': None}
    assert env['conteudo'] == {'camadas': []}


def test_o_que_fazer_com_segredo_e_retido():
    falso = laudo_cheio_de_conteudo()[2][0]
    r = Resultado(comando='teste', o_que_fazer='Use a chave ' + falso)
    _, env = _imprimir(r, 'c')
    assert falso not in json.dumps(env) and env['o_que_fazer'] == envelope.O_QUE_FAZER_RETIDO
    assert env['segredos_bloqueados'] == 1


def test_modo_invalido_vira_c():
    laudo, _, _ = laudo_cheio_de_conteudo()
    _, env = _imprimir(_resultado(laudo), 'z')
    assert env['modo_dados'] == 'c' and 'conteudo' not in env


def test_falha_interna_devolve_envelope_seguro(monkeypatch):
    laudo, textos, _ = laudo_cheio_de_conteudo()

    class Quebrado:
        def achado_em(self, *a, **k):
            raise RuntimeError('quebrou')

    env = envelope.montar(_resultado(laudo), 'a', detector=Quebrado())
    contratos.validar(env, 'envelope/1')
    assert env['modo_dados'] == 'c' and 'conteudo' not in env
    linha = json.dumps(env, ensure_ascii=False)
    for t in textos:
        assert t not in linha


def test_cli_usa_este_modulo():
    laudo, _, falsos = laudo_cheio_de_conteudo()
    env = cli.montar_envelope(_resultado(laudo), 'b')
    contratos.validar(env, 'envelope/1')
    assert env['segredos_bloqueados'] == 2 * len(falsos) and 'conteudo' in env


def test_cli_no_modo_envelope_sem_job_fica_no_modo_c(capsys, monkeypatch):
    laudo, textos, _ = laudo_cheio_de_conteudo()
    import desdobra.limites as modulo_limites

    def registrar(sub):
        p = sub.add_parser('teste-envelope')
        p.set_defaults(executar=lambda a: _resultado(laudo), nome_comando='teste-envelope')

    monkeypatch.setattr(modulo_limites, 'registrar', registrar)
    # so o componente do teste: os outros podem estar em construcao por outros agentes
    monkeypatch.setattr(cli, 'COMPONENTES', (('desdobra.limites', ('limites',)),))
    codigo = cli.principal(['--envelope', 'teste-envelope'])
    saida = capsys.readouterr().out
    assert codigo == int(Codigo.OK)
    env = json.loads(saida)
    contratos.validar(env, 'envelope/1')
    assert env['modo_dados'] == 'c'
    for t in textos:
        assert t not in saida


def test_detector_roda_mesmo_sem_pasta_do_job():
    laudo, _, falsos = laudo_cheio_de_conteudo()
    env = envelope.montar(_resultado(laudo), 'b', detector=segredos.Detector())
    assert env['segredos_bloqueados'] == 2 * len(falsos)


def test_avisos_de_segredo_para_o_terminal_do_da(tmp_path):
    laudo, _, falsos = laudo_cheio_de_conteudo()
    linhas = envelope.avisos_de_segredo(_resultado(laudo, pasta_job=tmp_path))
    assert len(linhas) == 2 * len(falsos)
    texto = '\n'.join(linhas)
    for s in falsos:
        assert s not in texto
    assert chr(0x2014) not in texto and chr(0x2013) not in texto
    assert (tmp_path / 'sugestoes' / 'segredos-bloqueados.json').is_file()
    assert envelope.avisos_de_segredo(Resultado(comando='x')) == []
