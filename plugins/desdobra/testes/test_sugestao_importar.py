# -*- coding: utf-8 -*-
"""M7c, S3: sugestoes/1 e o importador validado (desdobra.sugestao.importar e "desdobra sugestao importar").

O Claude escreve sugestoes/sugestoes.json; o motor confere e grava sugestoes/sugestoes-validadas.json. A conferencia:
  - so funcoes do $defs.funcao do briefing-1.json, na sugestao e na alternativa;
  - o alvo e um layer_id ou um grupo do laudo; uma sugestao e uma alternativa por alvo;
  - nenhum numero alem dos ids (sem geometria, escala ou ancora), nenhum texto livre, campo extra recusado;
  - o modo efetivo na hora da importacao e (a) ou (b), com o teto do processo;
  - o arquivo cita o sha256 do pacote que o Claude leu, e pacote velho e recusado.
O envelope de volta traz so contagens e recusas por codigo, sem nome nem texto.

O gancho do plugin nega ao Claude a escrita em sugestoes/miniaturas/**, sugestoes/pacote-modelo.json,
sugestoes/pacote-specs.json e sugestoes/sugestoes-validadas.json, pelas ferramentas de arquivo, pelo terminal e pelo
codigo do motor que grava esses arquivos.

Tudo sintetico: laudo, estado e miniaturas inventados na hora; nenhum PSD ou fonte e aberto.
"""
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import time
from contextlib import redirect_stdout

import pytest

from conftest import RAIZ_PLUGIN, escolher_modo_do_da
from desdobra import cli, contratos, humano
from desdobra.sugestao import importar, pacote
from test_sugestao_apoio import camada, laudo, segredos_falsos

SCRIPT_GANCHO = RAIZ_PLUGIN / 'scripts' / 'gancho_confirmacoes.py'
OFERTA = 'Oferta Ficticia Coral'
NOME_GRUPO = 'Grupo Ficticio Marfim'


def _estado(teto=None):
    return {'esquema': 'estado/1', 'job_id': '0' * 32, 'criado_em': '2026-10-29T10:00:00-03:00',
            'atualizado_em': '2026-10-29T10:00:00-03:00', 'motor_versao': '0.1.0', 'modo_dados': None,
            'teto_modo_dados': teto, 'entradas': {}, 'fases': {},
            'proxima': {'tipo': 'concluido', 'fase': None, 'o_que_fazer': 'nada'}}


def _laudo(segredo=None):
    nome_logo = 'Logo Ficticio' if segredo is None else 'Logo %s' % segredo
    return laudo([camada(10, NOME_GRUPO, tipo='grupo'),
                  camada(11, 'Fundo Ficticio', pai_id=10),
                  camada(12, 'Titulo Ficticio', tipo='texto', texto=OFERTA, pai_id=10),
                  camada(13, nome_logo)])


def _job(tmp_path, modo='a', teto=None, segredo=None):
    job = tmp_path / 'job'
    la = _laudo(segredo)
    estado = _estado(teto)
    estado['entradas'] = {'entrada/kv.psd': {'sha256': la['origem']['sha256'], 'bytes': 1234,
                                             'congelada_em': '2026-10-29T10:00:00-03:00'}}
    contratos.gravar(job / 'estado.json', estado, 'estado/1')
    contratos.gravar(job / 'laudo' / 'laudo.json', la, 'laudo/1')
    if modo is not None:
        escolher_modo_do_da(job, modo)
    pacote.refazer_pacotes(job)
    return job


def _sha_pacote(job):
    return hashlib.sha256((job / 'sugestoes' / 'pacote-modelo.json').read_bytes()).hexdigest()


def _sugestoes(job, itens, **extra):
    dados = {'esquema': 'sugestoes/1', 'pacote_sha256': _sha_pacote(job), 'sugestoes': itens}
    dados.update(extra)
    return dados


def _escrever(job, dados):
    arq = job / 'sugestoes' / 'sugestoes.json'
    arq.parent.mkdir(parents=True, exist_ok=True)
    texto = dados if isinstance(dados, str) else json.dumps(dados, ensure_ascii=False)
    arq.write_text(texto, encoding='utf-8')
    return arq


VALIDAS = [{'layer_id': 10, 'funcao': 'grafismo', 'alternativa': 'estrutura'},
           {'layer_id': 12, 'funcao': 'titulo', 'alternativa': 'texto_de_apoio'},
           {'layer_id': 13, 'funcao': 'logo_principal', 'alternativa': 'selo'}]

ARQ_VALIDADAS = ('sugestoes', 'sugestoes-validadas.json')


def _validadas(job):
    return job.joinpath(*ARQ_VALIDADAS)


def _numeros(valor, chave=None):
    """Todos os numeros (fora bool) do valor, com a chave de onde vieram."""
    if isinstance(valor, dict):
        for k, v in valor.items():
            yield from _numeros(v, k)
    elif isinstance(valor, list):
        for v in valor:
            yield from _numeros(v, chave)
    elif isinstance(valor, (int, float)) and not isinstance(valor, bool):
        yield chave, valor


# ------------------------------------------------------------------ esquema
def test_esquema_usa_as_funcoes_do_briefing():
    briefing = contratos.carregar_esquema('briefing/1')['$defs']['funcao']['enum']
    esq = contratos.carregar_esquema('sugestoes/1')
    item = esq['$defs']['sugestao']['properties']
    assert item['funcao']['enum'] == briefing and item['alternativa']['enum'] == briefing
    assert importar.funcoes_da_taxonomia() == tuple(briefing)
    assert esq['$defs']['sugestao']['additionalProperties'] is False and esq['additionalProperties'] is False


def test_esquema_recusa_geometria_campo_extra_e_texto():
    base = {'esquema': 'sugestoes/1', 'pacote_sha256': 'a' * 64, 'sugestoes': [dict(VALIDAS[0])]}
    contratos.validar(base, 'sugestoes/1')
    for ruim in ({'caixa': [0, 0, 10, 10]}, {'escala': 1.5}, {'motivo': 'texto livre'}, {'funcao': 'Titulo'},
                 {'layer_id': 1.5}, {'layer_id': True}):
        item = dict(VALIDAS[0], **ruim)
        with pytest.raises(contratos.ErroContrato):
            contratos.validar(dict(base, sugestoes=[item]), 'sugestoes/1')
    with pytest.raises(contratos.ErroContrato):
        contratos.validar(dict(base, nota='texto'), 'sugestoes/1')
    with pytest.raises(contratos.ErroContrato):
        contratos.validar(dict(base, pacote_sha256='velho'), 'sugestoes/1')


# ------------------------------------------------------------------ importador
@pytest.mark.parametrize('modo', ['a', 'b'])
def test_sugestao_valida_grava_o_arquivo_validado(tmp_path, modo):
    job = _job(tmp_path, modo)
    _escrever(job, _sugestoes(job, VALIDAS))
    r = importar.importar(job)
    assert r['situacao'] == 'ok' and r['recusa'] is None and r['modo'] == modo
    assert r['aceitas'] == 3 and r['recusadas'] == {}
    v = contratos.ler(_validadas(job), 'sugestoes/1')
    assert v['modo_dados'] == modo and v['pacote_sha256'] == _sha_pacote(job)
    assert v['arquivo_sha256'] == _laudo()['origem']['sha256'] and v['job_id'] == '0' * 32
    assert v['sugestoes'] == sorted(VALIDAS, key=lambda i: i['layer_id'])
    # nenhum numero alem dos ids
    assert {k for k, _ in _numeros(v)} == {'layer_id'}


@pytest.mark.parametrize('ruim, codigo', [
    ({'layer_id': 13, 'funcao': 'logo_principal', 'alternativa': 'selo', 'caixa': [0, 0, 10, 10]}, 'numero'),
    ({'layer_id': 13, 'funcao': 'logo_principal', 'alternativa': 'selo', 'escala': 0.5}, 'numero'),
    ({'layer_id': 13, 'funcao': 'logo_principal', 'alternativa': 'selo', 'ancora': {'x': 1, 'y': 0}}, 'numero'),
    ({'layer_id': 13, 'funcao': 'logo_principal', 'alternativa': 'selo', 'motivo': 'texto livre'}, 'campo_extra'),
    ({'layer_id': 13, 'funcao': 'logo_da_marca', 'alternativa': 'selo'}, 'funcao_fora'),
    ({'layer_id': 13, 'funcao': 'logo_principal', 'alternativa': 'Selo bonito'}, 'funcao_fora'),
    ({'layer_id': 99, 'funcao': 'logo_principal', 'alternativa': 'selo'}, 'alvo_inexistente'),
    ({'layer_id': 13.0, 'funcao': 'logo_principal', 'alternativa': 'selo'}, 'numero'),
    ({'layer_id': '13', 'funcao': 'logo_principal', 'alternativa': 'selo'}, 'alvo_invalido'),
    ({'layer_id': True, 'funcao': 'logo_principal', 'alternativa': 'selo'}, 'alvo_invalido'),
    ({'layer_id': 13, 'funcao': 'logo_principal'}, 'item_incompleto'),
    ({'layer_id': 13, 'funcao': 'logo_principal', 'alternativa': 'logo_principal'}, 'alternativa_igual'),
    ('logo_principal', 'item_invalido'),
])
def test_sugestao_ruim_e_recusada_e_as_outras_seguem(tmp_path, ruim, codigo):
    job = _job(tmp_path)
    _escrever(job, _sugestoes(job, VALIDAS[:2] + [ruim]))
    r = importar.importar(job)
    assert r['situacao'] == 'ok' and r['aceitas'] == 2 and r['recusadas'] == {codigo: 1}, r
    v = contratos.ler(_validadas(job), 'sugestoes/1')
    assert [i['layer_id'] for i in v['sugestoes']] == [10, 12]


def test_duas_sugestoes_no_mesmo_alvo_recusam_as_duas(tmp_path):
    job = _job(tmp_path)
    _escrever(job, _sugestoes(job, VALIDAS + [{'layer_id': 12, 'funcao': 'cta', 'alternativa': 'titulo'}]))
    r = importar.importar(job)
    assert r['aceitas'] == 2 and r['recusadas'] == {'alvo_repetido': 2}
    assert [i['layer_id'] for i in contratos.ler(_validadas(job), 'sugestoes/1')['sugestoes']] == [10, 13]


def test_grupo_do_laudo_e_alvo_valido(tmp_path):
    job = _job(tmp_path)
    _escrever(job, _sugestoes(job, [{'layer_id': 10, 'funcao': 'estrutura', 'alternativa': 'grafismo'}]))
    assert importar.importar(job)['aceitas'] == 1


@pytest.mark.parametrize('mexer, codigo', [
    (lambda d: d.update(nota='texto livre'), 'campo_extra'),
    (lambda d: d.update(modo_dados='a'), 'campo_extra'),
    (lambda d: d.update(confianca=0.9), 'numero'),
    (lambda d: d.update(esquema='sugestoes/2'), 'esquema'),
    (lambda d: d.pop('pacote_sha256'), 'esquema'),
    (lambda d: d.update(sugestoes={'10': 'grafismo'}), 'esquema'),
    (lambda d: d.update(pacote_sha256='0' * 64), 'pacote_velho'),
])
def test_arquivo_ruim_e_recusado_inteiro(tmp_path, mexer, codigo):
    job = _job(tmp_path)
    dados = _sugestoes(job, VALIDAS)
    mexer(dados)
    _escrever(job, dados)
    r = importar.importar(job)
    assert r['situacao'] == 'recusado' and r['recusa'] == codigo and r['aceitas'] == 0, r
    assert not _validadas(job).exists()


@pytest.mark.parametrize('texto', ['{"esquema": "sugestoes/1", "sugestoes": [', '{"a": NaN}',
                                   '{"esquema": "sugestoes/1", "esquema": "sugestoes/1"}', '[]'])
def test_json_ruim_e_recusado(tmp_path, texto):
    job = _job(tmp_path)
    _escrever(job, texto)
    r = importar.importar(job)
    assert r['situacao'] == 'recusado' and r['recusa'] in ('json_invalido', 'esquema')
    assert not _validadas(job).exists()


def test_sem_arquivo_do_claude(tmp_path):
    job = _job(tmp_path)
    r = importar.importar(job)
    assert r['situacao'] == 'recusado' and r['recusa'] == 'sem_sugestoes'


def test_pacote_velho_depois_da_troca_de_modo_e_recusado(tmp_path):
    job = _job(tmp_path, 'a')
    dados = _sugestoes(job, VALIDAS)  # cita o pacote do modo (a)
    escolher_modo_do_da(job, 'b')
    pacote.refazer_pacotes(job)
    assert _sha_pacote(job) != dados['pacote_sha256']
    _escrever(job, dados)
    r = importar.importar(job)
    assert r['recusa'] == 'pacote_velho' and not _validadas(job).exists()


def test_pacote_de_outro_kv_e_recusado(tmp_path):
    job = _job(tmp_path, 'a')
    _escrever(job, _sugestoes(job, VALIDAS))
    estado = json.loads((job / 'estado.json').read_text(encoding='utf-8'))
    estado['entradas']['entrada/kv.psd']['sha256'] = 'cd' * 32  # o KV foi trocado e o laudo ainda e do antigo
    contratos.gravar(job / 'estado.json', estado, 'estado/1')
    assert importar.importar(job)['recusa'] == 'pacote_velho'


def test_sem_pacote_e_recusado(tmp_path):
    job = _job(tmp_path, 'a')
    _escrever(job, _sugestoes(job, VALIDAS))
    (job / 'sugestoes' / 'pacote-modelo.json').unlink()
    assert importar.importar(job)['recusa'] == 'sem_pacote'


def test_modo_c_e_recusado(tmp_path):
    job = _job(tmp_path, None)  # sem escolha do DA: o job e (c)
    _escrever(job, {'esquema': 'sugestoes/1', 'pacote_sha256': _sha_pacote(job), 'sugestoes': VALIDAS})
    r = importar.importar(job)
    assert r['situacao'] == 'recusado' and r['recusa'] == 'modo_c' and r['modo'] == 'c'
    assert not _validadas(job).exists()


def test_escolha_de_teste_continua_c(tmp_path):
    job = _job(tmp_path, None)
    from desdobra.job import modo_dados
    estado = json.loads((job / 'estado.json').read_text(encoding='utf-8'))
    contratos.gravar(job / modo_dados.ARQUIVO,
                     {'esquema': modo_dados.ESQUEMA, 'job_id': estado['job_id'], 'valor': 'a', 'teto': None,
                      'origem': 'fixture_de_teste', 'escolhido_por': {'usuario': None, 'maquina': None,
                                                                      'meio': 'tela',
                                                                      'quando': '2026-11-05T10:00:00-03:00'}},
                     modo_dados.ESQUEMA)
    _escrever(job, {'esquema': 'sugestoes/1', 'pacote_sha256': _sha_pacote(job), 'sugestoes': VALIDAS})
    assert importar.importar(job)['recusa'] == 'modo_c'


@pytest.mark.parametrize('teto_estado, teto_cli', [('c', None), (None, 'c')])
def test_teto_c_recusa_mesmo_com_a_escolha_a(tmp_path, teto_estado, teto_cli):
    job = _job(tmp_path, 'a')
    _escrever(job, _sugestoes(job, VALIDAS))
    if teto_estado:
        estado = json.loads((job / 'estado.json').read_text(encoding='utf-8'))
        estado['teto_modo_dados'] = teto_estado
        contratos.gravar(job / 'estado.json', estado, 'estado/1')
    assert importar.importar(job, teto=teto_cli)['recusa'] == 'modo_c'
    assert not _validadas(job).exists()


def test_teto_do_processo_vale_na_importacao(tmp_path):
    job = _job(tmp_path, 'a')
    _escrever(job, _sugestoes(job, VALIDAS))
    pacote.definir_teto_do_processo('c')
    try:
        assert importar.importar(job)['recusa'] == 'modo_c'
    finally:
        pacote.definir_teto_do_processo(None)


def test_arquivo_grande_demais_e_recusado(tmp_path):
    job = _job(tmp_path, 'a')
    _escrever(job, ' ' * (importar.LIMITE_BYTES + 1))
    assert importar.importar(job)['recusa'] == 'grande_demais'


def test_atalho_no_lugar_do_arquivo_e_recusado(tmp_path):
    job = _job(tmp_path, 'a')
    alvo = tmp_path / 'fora.json'
    alvo.write_text(json.dumps(_sugestoes(job, VALIDAS)), encoding='utf-8')
    try:
        os.symlink(alvo, job / 'sugestoes' / 'sugestoes.json')
    except (OSError, NotImplementedError):
        pytest.skip('sem permissao para criar ligacao simbolica neste sistema')
    assert importar.importar(job)['recusa'] == 'sem_sugestoes'


def test_queda_para_c_apaga_as_validadas(tmp_path):
    job = _job(tmp_path, 'a')
    _escrever(job, _sugestoes(job, VALIDAS))
    importar.importar(job)
    assert _validadas(job).is_file()
    pacote.refazer_pacotes(job, teto='c')
    assert not _validadas(job).exists() and not (job / 'sugestoes' / 'sugestoes.json').exists()


def test_registro_no_log_so_com_contagens(tmp_path):
    job = _job(tmp_path, 'a')
    _escrever(job, _sugestoes(job, VALIDAS[:2] + [{'layer_id': 99, 'funcao': 'cta', 'alternativa': 'titulo'}]))
    importar.importar(job)
    eventos = [json.loads(x) for x in (job / 'log' / 'eventos.jsonl').read_text(encoding='utf-8').splitlines()]
    ev = [e for e in eventos if e['evento'] == importar.EVENTO][-1]
    assert ev['modo'] == 'a' and ev['aceitas'] == 2 and ev['recusadas'] == {'alvo_inexistente': 1}
    assert set(ev) <= {'quando', 'evento', 'modo', 'aceitas', 'recusadas', 'recusa'}


# ------------------------------------------------------------------ CLI e envelope
def _cli(*argv):
    saida = io.StringIO()
    with redirect_stdout(saida):
        codigo = cli.principal(list(argv))
    linhas = saida.getvalue().strip().splitlines()
    assert len(linhas) == 1, saida.getvalue()
    return codigo, json.loads(linhas[0])


def test_importar_nao_e_ato_do_da():
    assert 'sugestao importar' not in humano.COMANDOS
    assert cli.CONFEREM_O_MODO.get('sugestao importar') == ('job',)


def test_pacote_pela_cli_devolve_o_sha256_do_pacote(tmp_path):
    job = _job(tmp_path, 'a')
    codigo, env = _cli('--envelope', '--teto-modo-dados', 'a', 'sugestao', 'pacote', '--job', str(job))
    assert codigo == 0 and env['ids']['pacote_sha256'] == _sha_pacote(job)


def test_envelope_so_com_contagens_e_codigos(tmp_path):
    falsos = segredos_falsos()
    segredo = falsos['token do GitHub']
    job = _job(tmp_path, 'b', segredo=segredo)
    ruim = {'layer_id': 13, 'funcao': 'cta', 'alternativa': 'titulo', 'nome': 'Logo %s' % segredo,
            'texto': OFERTA}
    _escrever(job, _sugestoes(job, VALIDAS[:2] + [ruim]))
    codigo, env = _cli('--envelope', '--teto-modo-dados', 'a', 'sugestao', 'importar', '--job', str(job))
    assert codigo == 0 and env['comando'] == 'sugestao importar' and env['situacao'] == 'ok'
    assert env['contagens'] == {'aceitas': 2, 'recusadas': 1, 'recusa_campo_extra': 1}
    assert set(env['numeros']) == {'tempo_s'} and env['ids'] == {}
    assert env.get('conteudo') in (None, {'camadas': []})
    tudo = '\n'.join([json.dumps(env, ensure_ascii=False), _validadas(job).read_text(encoding='utf-8'),
                      (job / 'log' / 'eventos.jsonl').read_text(encoding='utf-8')])
    # medicao "Segredo e fonte" (plano, secao 4): 0 ocorrencia do segredo, do nome e do texto
    for proibido in (segredo, 'Logo', OFERTA, NOME_GRUPO, 'Titulo Ficticio'):
        assert proibido not in tudo, proibido


@pytest.mark.parametrize('modo', ['a', 'b'])
def test_medicao_segredo_em_todos_os_padroes(tmp_path, modo, capsys):
    """Medicao do plano (secao 4, Segredo e fonte): cada segredo falso do registro no nome de uma camada e copiado
    pelo Claude para o sugestoes.json (campo extra, valor de funcao e alvo de texto) da 0 ocorrencia no arquivo
    validado, no envelope e no log."""
    ocorrencias, casos = 0, 0
    for i, segredo in enumerate(segredos_falsos().values()):
        job = _job(tmp_path / str(i), modo, segredo=segredo)
        itens = VALIDAS[:2] + [{'layer_id': 13, 'funcao': 'cta', 'alternativa': 'titulo', 'obs': segredo},
                               {'layer_id': 11, 'funcao': segredo, 'alternativa': 'fundo'},
                               {'layer_id': segredo, 'funcao': 'fundo', 'alternativa': 'imagem'}]
        _escrever(job, _sugestoes(job, itens))
        codigo, env = _cli('--envelope', '--teto-modo-dados', 'a', 'sugestao', 'importar', '--job', str(job))
        assert codigo == 0 and env['contagens']['aceitas'] == 2 and env['contagens']['recusadas'] == 3
        tudo = '\n'.join([json.dumps(env, ensure_ascii=False), _validadas(job).read_text(encoding='utf-8'),
                          (job / 'log' / 'eventos.jsonl').read_text(encoding='utf-8')])
        ocorrencias += tudo.count(segredo)
        casos += 1
    assert ocorrencias == 0
    with capsys.disabled():
        print('\n[medicao S3] modo %s: %d segredos, %d ocorrencias em validadas, envelope e log'
              % (modo, casos, ocorrencias))


def test_envelope_da_recusa_inteira(tmp_path):
    job = _job(tmp_path, 'a')
    _escrever(job, _sugestoes(job, VALIDAS, pacote_sha256='1' * 64))
    codigo, env = _cli('--envelope', '--teto-modo-dados', 'a', 'sugestao', 'importar', '--job', str(job))
    assert codigo == 3 and env['situacao'] == 'recusado'
    assert env['contagens'] == {'aceitas': 0, 'recusadas': 0, 'recusa_pacote_velho': 1}
    # M7c, ajuste terminal: o passo seguinte cita a skill, sem comando de terminal
    assert env['o_que_fazer'] and '/desdobra:sugerir-funcoes' in env['o_que_fazer']
    assert 'desdobra sugestao' not in env['o_que_fazer']


def test_cli_com_teto_c_refaz_o_pacote_e_recusa(tmp_path):
    job = _job(tmp_path, 'a')
    _escrever(job, _sugestoes(job, VALIDAS))
    codigo, env = _cli('--envelope', '--teto-modo-dados', 'c', 'sugestao', 'importar', '--job', str(job))
    assert codigo == 3 and env['modo_dados'] == 'c' and env['contagens'].get('recusa_modo_c') == 1
    assert not _validadas(job).exists() and not (job / 'sugestoes' / 'sugestoes.json').exists()


def test_cli_fora_de_um_job(tmp_path):
    codigo, env = _cli('--envelope', 'sugestao', 'importar', '--job', str(tmp_path))
    assert codigo == 2 and env['situacao'] == 'erro'


def test_tempo_do_sugestao_importar(tmp_path, capsys):
    """Medicao do plano (secao 4, Tempo): o sugestao importar pela linha de comando, com a partida do Python."""
    job = _job(tmp_path, 'a')
    _escrever(job, _sugestoes(job, VALIDAS))
    inicio = time.monotonic()
    proc = subprocess.run([sys.executable, '-I', '-B', '-m', 'desdobra', '--envelope', '--teto-modo-dados', 'a',
                           'sugestao', 'importar', '--job', str(job)], capture_output=True)
    total = time.monotonic() - inicio
    env = json.loads(proc.stdout.decode('utf-8'))
    assert proc.returncode == 0 and env['contagens']['aceitas'] == 3
    with capsys.disabled():
        print('\n[medicao S3] sugestao importar: %.2f s pela linha de comando, %.3f s no motor'
              % (total, env['numeros']['tempo_s']))


# ------------------------------------------------------------------ gancho
def _gancho():
    spec = importlib.util.spec_from_file_location('gancho_confirmacoes_s3', SCRIPT_GANCHO)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def g():
    return _gancho()


@pytest.fixture
def job_vazio(tmp_path):
    job = tmp_path / 'jobs' / 'campanha'
    for rel in ('sugestoes/pacote-modelo.json', 'sugestoes/pacote-specs.json', 'sugestoes/sugestoes.json',
                'sugestoes/sugestoes-validadas.json', 'sugestoes/mapeamento-specs.json',
                'sugestoes/miniaturas/13.png', 'sugestoes/miniaturas/indice.json'):
        p = job / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b'sintetico')
    (job / 'estado.json').write_text('{}', encoding='utf-8')
    return job


PROTEGIDOS = ('sugestoes/pacote-modelo.json', 'sugestoes/pacote-specs.json', 'sugestoes/sugestoes-validadas.json',
              'sugestoes/miniaturas/13.png', 'sugestoes/miniaturas/indice.json', 'sugestoes/miniaturas/novo.png',
              'sugestoes/Pacote-Modelo.json', 'sugestoes\\miniaturas\\14.png', 'sugestoes/miniaturas./15.png')


def _decidir(g, ferramenta, entrada, cwd):
    return g.decidir_com_motivo({'tool_name': ferramenta, 'tool_input': entrada, 'cwd': str(cwd)})


@pytest.mark.parametrize('ferramenta', ['Write', 'Edit', 'MultiEdit', 'NotebookEdit'])
@pytest.mark.parametrize('rel', PROTEGIDOS)
def test_gancho_nega_a_escrita_do_claude_no_que_o_motor_grava(g, job_vazio, tmp_path, ferramenta, rel):
    campo = 'notebook_path' if ferramenta == 'NotebookEdit' else 'file_path'
    decisao, motivo = _decidir(g, ferramenta, {campo: str(job_vazio) + '/' + rel, 'content': '{}'}, tmp_path)
    assert decisao == 'deny' and motivo == g.MOTIVO_SUGESTOES
    # relativo ao cwd do job e ao cwd da pasta sugestoes
    assert _decidir(g, ferramenta, {campo: rel}, job_vazio)[0] == 'deny'
    nome = rel.split('/', 1)[1] if '/' in rel else rel.split('\\', 1)[1]
    assert _decidir(g, ferramenta, {campo: nome}, job_vazio / 'sugestoes')[0] == 'deny'


@pytest.mark.parametrize('ferramenta', ['Write', 'Edit'])
@pytest.mark.parametrize('rel', ['sugestoes/sugestoes.json', 'sugestoes/mapeamento-specs.json'])
def test_gancho_deixa_o_claude_escrever_as_sugestoes_dele(g, job_vazio, tmp_path, ferramenta, rel):
    assert _decidir(g, ferramenta, {'file_path': str(job_vazio / rel), 'content': '{}'}, tmp_path) == (None, None)


def test_gancho_nega_escrita_por_ligacao_para_o_pacote(g, job_vazio, tmp_path):
    lig = tmp_path / 'inocente.json'
    try:
        os.symlink(job_vazio / 'sugestoes' / 'pacote-modelo.json', lig)
    except (OSError, NotImplementedError):
        pytest.skip('sem permissao para criar ligacao simbolica neste sistema')
    assert _decidir(g, 'Write', {'file_path': str(lig), 'content': '{}'}, tmp_path)[0] == 'deny'


@pytest.mark.parametrize('comando', [
    'echo {{}} > {j}/sugestoes/pacote-modelo.json',
    'echo {{}} >> "{j}/sugestoes/sugestoes-validadas.json"',
    'cp {f}/x.png {j}/sugestoes/miniaturas/13.png',
    'cp {f}/x.png {j}/sugestoes/miniaturas/',
    'mv {f}/x.json {j}/sugestoes/pacote-specs.json',
    'tee {j}/sugestoes/pacote-modelo.json < {f}/x.json',
    'cat {f}/x.json | tee -a {j}/sugestoes/sugestoes-validadas.json',
    'mkdir -p {j}/sugestoes/miniaturas',
    'touch {j}/sugestoes/miniaturas/novo.png',
    'ln -s {j}/sugestoes/pacote-modelo.json {f}/inocente.json',
    'sed -i s/a/b/ {j}/sugestoes/pacote-specs.json',
    'Set-Content -Path "{w}\\sugestoes\\sugestoes-validadas.json" -Value x',
    '"x" | Out-File {w}\\sugestoes\\pacote-modelo.json',
    'Copy-Item {f}/x.png -Destination {j}/sugestoes/miniaturas/13.png',
    'Copy-Item -Path {f}/x.png {j}/sugestoes/miniaturas/13.png',
    'New-Item -ItemType File {j}/sugestoes/miniaturas/novo.png',
    'Move-Item {f}/x.json {j}/sugestoes/pacote-modelo.json',
    'python -c "open(\'{j}/sugestoes/pacote-modelo.json\', \'w\').write(\'x\')"',
    'python -c "import pathlib; pathlib.Path(\'{j}/sugestoes/sugestoes-validadas.json\').write_text(\'x\')"',
    'python -c "import shutil; shutil.copy(\'{f}/x.png\', \'{j}/sugestoes/miniaturas/13.png\')"',
    '[IO.File]::WriteAllText(\'{j}/sugestoes/pacote-specs.json\', \'x\')',
    'cd {j}/sugestoes && echo x > pacote-modelo.json',
    'cd {j}/sugestoes/miniaturas; cp {f}/x.png 13.png',
    'echo x > pacote-modelo.json',
])
def test_gancho_nega_a_escrita_pelo_terminal(g, job_vazio, tmp_path, comando):
    fora = tmp_path / 'fora'
    fora.mkdir(exist_ok=True)
    cmd = comando.format(j=job_vazio.as_posix(), w=str(job_vazio).replace('/', '\\'), f=fora.as_posix())
    cwd = job_vazio / 'sugestoes' if comando.startswith('echo x > pacote') else tmp_path
    for ferramenta in ('Bash', 'PowerShell'):
        decisao, motivo = _decidir(g, ferramenta, {'command': cmd}, cwd)
        assert decisao == 'deny', (ferramenta, cmd)


@pytest.mark.parametrize('comando', [
    'python -c "from desdobra.sugestao import pacote; pacote.gravar_pacote(\'{j}\')"',
    'python -c "import desdobra.sugestao.importar as i; i.importar(\'{j}\')"',
    'python -c "from desdobra.sugestao.miniaturas import gravar_miniaturas"',
    'python -c "from desdobra.sugestao import specs; specs.refazer_pacote(\'{j}\', \'a\')"',
    'python -c "from desdobra.sugestao import importar as i"',
    'python -c "import desdobra.sugestao.pacote"',
    'python -c "import importlib; importlib.import_module(\'desdobra.sugestao.importar\')"',
    'python -c "from desdobra.sugestao import envelope, pacote"',
])
def test_gancho_nega_o_codigo_do_motor_que_grava_esses_arquivos(g, job_vazio, tmp_path, comando):
    cmd = comando.format(j=job_vazio.as_posix())
    for ferramenta in ('Bash', 'PowerShell'):
        decisao, motivo = _decidir(g, ferramenta, {'command': cmd}, tmp_path)
        assert decisao == 'deny', (ferramenta, cmd)


@pytest.mark.parametrize('comando, onde', [
    ('python -m desdobra --envelope --teto-modo-dados a sugestao importar --job "{j}"', 'tmp'),
    ('python -m desdobra --envelope --teto-modo-dados a sugestao pacote --job "{j}"', 'tmp'),
    ('cp {j}/sugestoes/pacote-modelo.json {f}/copia.json', 'tmp'),
    ('ls {j}/sugestoes/miniaturas', 'tmp'),
    ('python -m pytest -p no:cacheprovider testes/test_sugestao_importar.py -q', 'plugin'),
    ('git diff -- motor/desdobra/sugestao/importar.py motor/schemas/sugestoes-1.json', 'plugin'),
    ('git status', 'plugin'),
    ('echo as sugestoes > {f}/notas.txt', 'tmp'),
])
def test_gancho_deixa_o_que_nao_grava_esses_arquivos(g, job_vazio, tmp_path, comando, onde):
    fora = tmp_path / 'fora'
    fora.mkdir(exist_ok=True)
    cmd = comando.format(j=job_vazio.as_posix(), f=fora.as_posix())
    cwd = RAIZ_PLUGIN if onde == 'plugin' else tmp_path
    for ferramenta in ('Bash', 'PowerShell'):
        assert _decidir(g, ferramenta, {'command': cmd}, cwd) == (None, None), (ferramenta, cmd)


@pytest.mark.parametrize('rel', ['motor/desdobra/sugestao/importar.py', 'motor/desdobra/sugestao/pacote.py',
                                 'motor/schemas/sugestoes-1.json', 'testes/test_sugestao_importar.py'])
def test_gancho_deixa_editar_o_codigo_fonte(g, rel):
    assert _decidir(g, 'Edit', {'file_path': str(RAIZ_PLUGIN / rel)}, RAIZ_PLUGIN) == (None, None)


# ------------------------------------------------------------------ revisao do S3
# defeito 4: arquivo pequeno e muito aninhado vira recusa, nunca erro interno
def _aninhado(niveis, folha='x'):
    return '[' * niveis + json.dumps(folha) + ']' * niveis


def _arquivo_cru(sha, sugestoes='[]', extra=None):
    texto = '{"esquema": "sugestoes/1", "pacote_sha256": "%s", "sugestoes": %s' % (sha, sugestoes)
    return texto + (', "extra": %s}' % extra if extra is not None else '}')


@pytest.mark.parametrize('sugestoes, extra', [
    ('[' * 100000 + ']' * 100000, None),
    ('[]', _aninhado(5000)),
    ('[]', _aninhado(900)),
])
def test_arquivo_muito_aninhado_e_recusado_inteiro(tmp_path, sugestoes, extra):
    job = _job(tmp_path, 'a')
    _escrever(job, _arquivo_cru(_sha_pacote(job), sugestoes, extra))
    r = importar.importar(job)
    assert r['situacao'] == 'recusado' and r['recusa'] in ('json_invalido', 'campo_extra'), r
    assert not _validadas(job).exists()
    assert importar.EVENTO in (job / 'log' / 'eventos.jsonl').read_text(encoding='utf-8')


@pytest.mark.parametrize('niveis', [900, 5000])
def test_item_muito_aninhado_nunca_derruba_o_importador(tmp_path, niveis):
    job = _job(tmp_path, 'a')
    itens = json.dumps(VALIDAS[:2])[:-1] + \
        ', {"layer_id": 13, "funcao": "cta", "alternativa": "titulo", "obs": %s}]' % _aninhado(niveis)
    _escrever(job, _arquivo_cru(_sha_pacote(job), itens))
    r = importar.importar(job)
    if r['recusa'] is None:
        assert r['aceitas'] == 2 and r['recusadas'] == {'campo_extra': 1}, r
    else:
        assert r['recusa'] == 'json_invalido' and not _validadas(job).exists(), r


def test_cli_com_arquivo_muito_aninhado_sai_como_recusa(tmp_path):
    job = _job(tmp_path, 'a')
    _escrever(job, _arquivo_cru(_sha_pacote(job), '[' * 100000 + ']' * 100000))
    codigo, env = _cli('--envelope', '--teto-modo-dados', 'a', 'sugestao', 'importar', '--job', str(job))
    assert codigo == 3 and env['situacao'] == 'recusado', env
    assert env['contagens'] == {'aceitas': 0, 'recusadas': 0, 'recusa_json_invalido': 1}


# defeito 1: o nome montado pelo shell (aspas no meio, escape, chaves, variavel), com o cwd do evento ja na pasta
# sugestoes ou com um cd que o gancho nao acompanha
@pytest.mark.parametrize('comando, onde', [
    ('cp ../../fora.json sugestoes-"validadas".json', 'sugestoes'),
    ('cp ../../fora.json pacote-"modelo".json', 'sugestoes'),
    ("cp ../../fora.json 'pacote-'\"specs\".json", 'sugestoes'),
    ('cp ../../fora.json "pacote-"modelo.json', 'sugestoes'),
    ('echo x > sugestoes-"validadas".json', 'sugestoes'),
    ('echo x > "pacote-"modelo.json', 'sugestoes'),
    ('Copy-Item ../../fora.json pacote-`modelo.json', 'sugestoes'),
    ('cp ../../fora.json pacote-mod\\elo.json', 'sugestoes'),
    ('tee pacote-{{modelo,outro}}.json < ../../fora.json', 'sugestoes'),
    ('cp ../../fora.json pacote-modelo$VAZIO.json', 'sugestoes'),
    ('cp ../../fora.json "$ALVO"', 'sugestoes'),
    ('echo x > miniatura"s"/13.png', 'sugestoes'),
    ('cd {j}/sugestoes && cp {f}/x.json pacote-"modelo".json', 'tmp'),
    ('cd {j}/sugestoes; echo x > sugestoes-"validadas".json', 'tmp'),
    ('ALVO={j}/sugestoes/pacote-modelo.json; cp {f}/x.json "$ALVO"', 'tmp'),
    ('tee {f}/a.json {j}/sugestoes/pacote-{{modelo,specs}}.json < {f}/x.json', 'tmp'),
    ('cp {f}/x.json {{{f}/a.json,{j}/sugestoes/pacote-modelo.json}}', 'tmp'),
    ('cd $PASTA_DO_JOB && cp {f}/x.json pacote-modelo.json', 'tmp'),
])
def test_gancho_nega_o_nome_montado_pelo_shell(g, job_vazio, tmp_path, comando, onde):
    fora = tmp_path / 'fora'
    fora.mkdir(exist_ok=True)
    cmd = comando.format(j=job_vazio.as_posix(), f=fora.as_posix())
    cwd = job_vazio / 'sugestoes' if onde == 'sugestoes' else tmp_path
    for ferramenta in ('Bash', 'PowerShell'):
        decisao, motivo = _decidir(g, ferramenta, {'command': cmd}, cwd)
        assert decisao == 'deny', (ferramenta, cmd)


# defeito 2: o codigo do motor importado por nome montado em pedacos, sem caminho do job no comando
@pytest.mark.parametrize('comando, onde', [
    ("python -c \"import importlib as l; m=l.import_module('.'.join(['desdobra','sugestao','pacote'])); import os; "
     "getattr(m, '_'.join(['gravar','pacote']))(os.path.dirname(os.getcwd()))\"", 'sugestoes'),
    ("python -c \"import importlib as l; m=l.import_module('.'.join(['desdobra','sugestao','pacote'])); import os; "
     "getattr(m, '_'.join(['gravar','pacote']))(os.environ['J'])\"", 'tmp'),
    ("python -c \"m=__import__('desdobra.sug'+'estao.pac'+'ote', fromlist=['x']); m.refazer_pacotes('.')\"", 'tmp'),
    ("python -c \"import runpy; runpy.run_module('desdobra.' + 'sugestao' + '.importar')\"", 'tmp'),
    ("python - <<'EOF'\nimport importlib\nm = importlib.import_module('desdobra' + '.sugestao' + '.miniaturas')\nEOF",
     'tmp'),
    ("python -c \"import importlib as l; l.import_module('desdobra.' + 'sugestao.' + 'specs')\"", 'tmp'),
])
def test_gancho_nega_o_codigo_do_motor_com_nome_em_pedacos(g, job_vazio, tmp_path, comando, onde):
    cwd = job_vazio / 'sugestoes' if onde == 'sugestoes' else tmp_path
    for ferramenta in ('Bash', 'PowerShell'):
        decisao, motivo = _decidir(g, ferramenta, {'command': comando}, cwd)
        assert decisao == 'deny', (ferramenta, comando)


# defeito 3: ligacao fisica e comando dentro de outro (cmd /c, bash -c, Start-Process)
@pytest.mark.parametrize('comando', [
    'fsutil hardlink create {fw}\\h.json {w}\\sugestoes\\pacote-modelo.json',
    'cmd /c mklink /H {fw}\\h2.json {w}\\sugestoes\\pacote-modelo.json',
    'cmd.exe /c "mklink /H {fw}\\h2.json {w}\\sugestoes\\sugestoes-validadas.json"',
    'cp -l {j}/sugestoes/pacote-modelo.json {f}/h.json',
    'cp -al {j}/sugestoes/sugestoes-validadas.json {f}/h.json',
    'cp --link {j}/sugestoes/pacote-specs.json {f}/h.json',
    'cp -s {j}/sugestoes/pacote-modelo.json {f}/h.json',
    'link {j}/sugestoes/sugestoes-validadas.json {f}/h.json',
    'bash -c "cp {f}/x.json {j}/sugestoes/pacote-modelo.json"',
    'sh -c \'echo x > {j}/sugestoes/sugestoes-validadas.json\'',
    'powershell -Command "Set-Content {j}/sugestoes/pacote-modelo.json x"',
    'Start-Process cmd -ArgumentList \'/c mklink /H {fw}\\h3.json {w}\\sugestoes\\pacote-modelo.json\'',
    'xargs -I{{}} cp {{}} {j}/sugestoes/pacote-modelo.json',
    'python -c "from desdobra import arquivos as a; a.gravar_texto_atomico(\'{j}/sugestoes/pacote-modelo.json\', \'x\')"',
])
def test_gancho_nega_ligacao_e_comando_embrulhado(g, job_vazio, tmp_path, comando):
    fora = tmp_path / 'fora'
    fora.mkdir(exist_ok=True)
    cmd = comando.format(j=job_vazio.as_posix(), w=str(job_vazio).replace('/', '\\'), f=fora.as_posix(),
                         fw=str(fora).replace('/', '\\'))
    for ferramenta in ('Bash', 'PowerShell'):
        decisao, motivo = _decidir(g, ferramenta, {'command': cmd}, tmp_path)
        assert decisao == 'deny', (ferramenta, cmd)


# defeito 5: buscar no fonte e copiar dali para fora com o mesmo nome seguem
@pytest.mark.parametrize('comando, onde', [
    ('grep -rn refazer_pacotes motor/desdobra', 'plugin'),
    ('grep -n gravar_pacote motor/desdobra/sugestao/pacote.py', 'plugin'),
    ('rg "desdobra.sugestao.importar" testes', 'plugin'),
    ('git log -S gravar_validadas --oneline', 'plugin'),
    ('Select-String -Path motor/desdobra/sugestao/*.py -Pattern gravar_miniaturas', 'plugin'),
    ('cp {j}/sugestoes/pacote-modelo.json {f}/pacote-modelo.json', 'tmp'),
    ('cp {j}/sugestoes/pacote-specs.json {f}/pacote-specs.json', 'tmp'),
    ('Copy-Item {j}/sugestoes/pacote-specs.json -Destination {f}/pacote-specs.json', 'tmp'),
    ('cd {f} && cp {j}/sugestoes/pacote-modelo.json pacote-modelo.json', 'tmp'),
    ('cp {j}/sugestoes/pacote-modelo.json "{f}/pacote-modelo.json"', 'tmp'),
])
def test_gancho_deixa_buscar_no_fonte_e_copiar_para_fora(g, job_vazio, tmp_path, comando, onde):
    fora = tmp_path / 'fora'
    fora.mkdir(exist_ok=True)
    cmd = comando.format(j=job_vazio.as_posix(), f=fora.as_posix())
    cwd = RAIZ_PLUGIN if onde == 'plugin' else tmp_path
    for ferramenta in ('Bash', 'PowerShell'):
        assert _decidir(g, ferramenta, {'command': cmd}, cwd) == (None, None), (ferramenta, cmd)
