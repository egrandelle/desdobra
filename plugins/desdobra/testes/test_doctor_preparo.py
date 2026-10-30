# -*- coding: utf-8 -*-
"""Gancho SessionStart e script de preparo do ambiente (scripts/preparar_ambiente.py).

Nada aqui instala pacote: o executor de comandos e trocado por um falso, que so registra o pedido e cria o
arquivo do Python do venv. O teste pela linha de comando usa um registro que recusa a versao do Python, para o
script parar antes de criar qualquer coisa.
"""
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import RAIZ_PLUGIN
from test_doctor import LIMITES_PROPOSTOS

SCRIPT = RAIZ_PLUGIN / 'scripts' / 'preparar_ambiente.py'


def _carregar():
    spec = importlib.util.spec_from_file_location('preparar_ambiente_teste', SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


pa = _carregar()


def _raiz_falsa(pasta, lock='aggdraw==1.4.1 \\\n    --hash=sha256:aa\n', aceitas=None):
    """Pasta com a forma minima do plugin: motor/requirements.lock e motor/fontes-de-limites.json."""
    (pasta / 'motor').mkdir(parents=True)
    (pasta / 'motor' / 'requirements.lock').write_text(lock, encoding='utf-8')
    limites = [dict(x) for x in LIMITES_PROPOSTOS]
    if aceitas is not None:
        limites[0]['valor'] = aceitas
    (pasta / 'motor' / 'fontes-de-limites.json').write_text(
        json.dumps({'esquema': 'fontes-de-limites/1', 'limites': limites}), encoding='utf-8')
    return pasta


class Executor:
    """Executor falso: registra cada etapa pelo argv e simula o que o comando deixaria no disco."""

    def __init__(self, falhar_em=None):
        self.etapas = []
        self.falhar_em = falhar_em

    def __call__(self, argv, log):
        argv = [str(a) for a in argv]
        if argv[1:3] == ['-I', '-m'] and argv[3] == 'venv':
            etapa = 'venv'
            python = pa.python_do_venv(Path(argv[4]))
            python.parent.mkdir(parents=True, exist_ok=True)
            python.write_bytes(b'')
        elif 'pip' in argv and '-r' in argv:
            etapa = 'pip_lock'
            assert '--require-hashes' in argv and '--only-binary=:all:' in argv and '--no-deps' in argv
        elif 'pip' in argv and '-e' in argv:
            etapa = 'motor'
            assert '--no-build-isolation' in argv
        elif 'pip' in argv and 'check' in argv:
            etapa = 'pip_check'
        elif argv[-1] == '--version':
            etapa = 'conferir'
        else:
            raise AssertionError(argv)
        self.etapas.append(etapa)
        if etapa == self.falhar_em:
            return 1, 'erro simulado'
        return 0, 'desdobra 0.1.0\n' if etapa == 'conferir' else 'ok'


@pytest.fixture
def raiz(tmp_path):
    return _raiz_falsa(tmp_path / 'cache' / 'desdobra' / '0.1.0')


@pytest.fixture
def dados(tmp_path):
    return tmp_path / 'data' / 'desdobra-desdobra'


def test_primeira_sessao_cria_o_ambiente(raiz, dados):
    ex = Executor()
    linha = pa.preparar(raiz, dados, executar=ex, python_base='python-base')
    assert linha.startswith('ambiente Python criado em')
    assert ex.etapas == ['venv', 'pip_lock', 'motor', 'conferir', 'pip_check']
    interp = json.loads((dados / 'interpretador.json').read_text(encoding='utf-8'))
    assert interp['esquema'] == 'interpretador/1'
    assert pa.mesmo_caminho(interp['python'], pa.python_do_venv(dados / 'venv'))
    assert '\\' not in interp['python'] and pa.mesmo_caminho(interp['plugin_root'], raiz)
    assert (dados / 'requirements.lock').read_bytes() == (raiz / 'motor' / 'requirements.lock').read_bytes()
    preparo = json.loads((dados / 'preparo.json').read_text(encoding='utf-8'))
    assert preparo['situacao'] == 'ok' and preparo['acao'] == 'recriar'
    assert [e['etapa'] for e in preparo['etapas']] == ex.etapas and preparo['tempo_s'] is not None
    assert not (dados / '.preparo.trava').exists()


def test_sessao_seguinte_e_rapida_e_nao_roda_nada(raiz, dados):
    pa.preparar(raiz, dados, executar=Executor(), python_base='python-base')
    ex = Executor()
    inicio = time.perf_counter()
    linha = pa.preparar(raiz, dados, executar=ex, python_base='python-base')
    assert ex.etapas == [] and 'sem mudança' in linha
    assert time.perf_counter() - inicio < 1.0


def test_versao_nova_do_plugin_com_o_mesmo_lock_so_religa_o_motor(raiz, dados, tmp_path):
    pa.preparar(raiz, dados, executar=Executor(), python_base='python-base')
    raiz_nova = _raiz_falsa(tmp_path / 'cache' / 'desdobra' / '0.2.0')
    ex = Executor()
    linha = pa.preparar(raiz_nova, dados, executar=ex, python_base='python-base')
    assert ex.etapas == ['motor', 'conferir'] and 'religado' in linha
    interp = json.loads((dados / 'interpretador.json').read_text(encoding='utf-8'))
    assert pa.mesmo_caminho(interp['plugin_root'], raiz_nova)


def test_lock_mudado_recria_o_ambiente(raiz, dados):
    pa.preparar(raiz, dados, executar=Executor(), python_base='python-base')
    (raiz / 'motor' / 'requirements.lock').write_text('aggdraw==1.4.1 \\\n    --hash=sha256:bb\n', encoding='utf-8')
    ex = Executor()
    pa.preparar(raiz, dados, executar=ex, python_base='python-base')
    assert ex.etapas[0] == 'venv' and len(ex.etapas) == 5


def test_falha_no_pip_nao_grava_interpretador_e_a_proxima_sessao_tenta_de_novo(raiz, dados):
    ex = Executor(falhar_em='pip_lock')
    linha = pa.preparar(raiz, dados, executar=ex, python_base='python-base')
    assert 'falhou' in linha and '/desdobra:doctor' in linha
    assert not (dados / 'interpretador.json').exists() and not (dados / 'requirements.lock').exists()
    preparo = json.loads((dados / 'preparo.json').read_text(encoding='utf-8'))
    assert preparo['situacao'] == 'falhou' and preparo['etapa_que_falhou'] == 'pip_lock'
    ex = Executor()
    pa.preparar(raiz, dados, executar=ex, python_base='python-base')
    assert ex.etapas[0] == 'venv' and (dados / 'interpretador.json').exists()


def test_motor_que_nao_responde_e_falha(raiz, dados):
    class Mudo(Executor):
        def __call__(self, argv, log):
            codigo, texto = super().__call__(argv, log)
            return codigo, '' if self.etapas[-1] == 'conferir' else texto
    linha = pa.preparar(raiz, dados, executar=Mudo(), python_base='python-base')
    assert 'não respondeu' in linha and not (dados / 'interpretador.json').exists()


def test_python_fora_da_lista_nao_instala_nada(raiz, dados, monkeypatch):
    monkeypatch.setattr(sys, 'version_info', (3, 13, 9, 'final', 0))
    ex = Executor()
    linha = pa.preparar(raiz, dados, executar=ex, python_base='python-base')
    assert ex.etapas == [] and '3.13' in linha and '3.14' in linha and not dados.exists()


def test_registro_sem_os_limites_do_ambiente(tmp_path, dados):
    raiz = _raiz_falsa(tmp_path / 'r')
    (raiz / 'motor' / 'fontes-de-limites.json').write_text('{"limites": []}', encoding='utf-8')
    ex = Executor()
    assert 'registro de limites' in pa.preparar(raiz, dados, executar=ex) and ex.etapas == []


def test_trava_recente_de_outra_sessao_espera_e_trava_velha_e_retomada(raiz, dados):
    dados.mkdir(parents=True)
    trava = dados / '.preparo.trava'
    trava.write_text('123', encoding='utf-8')
    ex = Executor()
    assert 'outra sessão' in pa.preparar(raiz, dados, executar=ex, python_base='python-base') and ex.etapas == []
    velha = time.time() - pa.ler_limite(raiz, 'ambiente.trava_preparo_max_s') - 5
    os.utime(trava, (velha, velha))
    linha = pa.preparar(raiz, dados, executar=ex, python_base='python-base')
    assert linha.startswith('ambiente Python criado') and not trava.exists()


def test_venv_em_uso_nao_e_apagado(raiz, dados, monkeypatch):
    pa.preparar(raiz, dados, executar=Executor(), python_base='python-base')
    (raiz / 'motor' / 'requirements.lock').write_text('numpy==2.5.4\n', encoding='utf-8')

    def rename_recusado(self, alvo):
        raise PermissionError('em uso')
    monkeypatch.setattr(Path, 'rename', rename_recusado)
    linha = pa.preparar(raiz, dados, executar=Executor(), python_base='python-base')
    assert 'em uso' in linha and pa.python_do_venv(dados / 'venv').exists()


# ------------------------------------------------------------------ o script de verdade, sem instalar nada
def _rodar_script(ambiente):
    env = {k: val for k, val in os.environ.items() if not k.startswith('CLAUDE_PLUGIN_')}
    env.update(ambiente)
    proc = subprocess.run([sys.executable, '-I', '-B', str(SCRIPT)], capture_output=True, env=env,
                          stdin=subprocess.DEVNULL)
    return proc.returncode, proc.stdout.decode('utf-8'), proc.stderr.decode('utf-8')


def test_script_imprime_uma_linha_so_e_sai_com_zero(tmp_path):
    raiz = _raiz_falsa(tmp_path / 'raiz', aceitas=['0.0'])
    dados = tmp_path / 'dados'
    codigo, saida, erro = _rodar_script({'CLAUDE_PLUGIN_ROOT': str(raiz), 'CLAUDE_PLUGIN_DATA': str(dados)})
    assert codigo == 0 and erro == ''
    assert len(saida.splitlines()) == 1 and saida.startswith('desdobra: o Python do PATH')
    assert not dados.exists()
    codigo, saida, _ = _rodar_script({'CLAUDE_PLUGIN_ROOT': str(raiz)})
    assert codigo == 0 and len(saida.splitlines()) == 1 and 'pasta de dados' in saida


# ------------------------------------------------------------------ forma do plugin
def test_hooks_json_na_forma_exec_sem_shell():
    dados = json.loads((RAIZ_PLUGIN / 'hooks' / 'hooks.json').read_text(encoding='utf-8'))
    grupos = dados['hooks']['SessionStart']
    assert len(grupos) == 1 and len(grupos[0]['hooks']) == 1
    gancho = grupos[0]['hooks'][0]
    assert gancho['type'] == 'command' and gancho['command'] == 'python'
    assert gancho['args'] == ['-I', '-B', '${CLAUDE_PLUGIN_ROOT}/scripts/preparar_ambiente.py']
    assert gancho['timeout'] <= 600
    assert SCRIPT.is_file()


def test_plugin_sem_pasta_bin_de_topo():
    assert not (RAIZ_PLUGIN / 'bin').exists()


@pytest.mark.parametrize('skill', ['doctor', 'novo-job'])
def test_skills_curtas_leem_o_interpretador_e_seguem_as_regras(skill):
    texto = (RAIZ_PLUGIN / 'skills' / skill / 'SKILL.md').read_text(encoding='utf-8')
    assert texto.startswith('---\n') and '\ndescription: ' in texto.split('---')[1]
    assert len(texto.splitlines()) < 500
    assert '${CLAUDE_PLUGIN_DATA}/interpretador.json' in texto and '${CLAUDE_PLUGIN_ROOT}' in texto
    assert '--envelope' in texto and '${user_config.teto_modo_dados}' in texto
    for proibido in ('—', '–'):
        assert proibido not in texto
    for regra in ('geometria', 'render', 'fonte'):
        assert regra in texto
