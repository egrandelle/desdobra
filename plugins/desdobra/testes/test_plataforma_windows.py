# -*- coding: utf-8 -*-
"""Isolador do Windows (Job Object), so com filhos sinteticos escritos aqui. Nenhum PSD de cliente."""
import ctypes
import os
import json
import subprocess
import sys
import textwrap
import time

import pytest

from desdobra import limites, plataforma

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='isolador do Windows')

MB = 2 ** 20


@pytest.fixture
def win():
    from desdobra.plataforma.windows import PlataformaWindows
    p = plataforma.obter()
    assert isinstance(p, PlataformaWindows)
    return p


@pytest.fixture
def trabalho(tmp_path):
    pasta = tmp_path / 'trabalho'
    pasta.mkdir()
    return pasta


def filho(codigo):
    """Comando de um filho sintetico que segue o protocolo: espera a linha de liberar e so entao age."""
    corpo = 'import sys\nliberacao = sys.stdin.buffer.readline()\n' + textwrap.dedent(codigo)
    return [sys.executable, '-c', corpo]


def test_caso_normal_devolve_ok_com_stdout_e_ambiente_do_contrato(win, trabalho):
    r = win.executar_isolado(filho('''
        import json, os
        print(json.dumps({"liberacao": liberacao.decode(), "cwd": os.getcwd(), "prefixo": sys.prefix,
                          "isolado": sys.flags.isolated, "sem_pyc": sys.flags.dont_write_bytecode,
                          "fios": [os.environ.get(n) for n in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS",
                                                                "MKL_NUM_THREADS")],
                          "extra": os.environ.get("DESDOBRA_TESTE")}))
    '''), 256 * MB, 60, trabalho, ambiente={'DESDOBRA_TESTE': 'sim'})
    assert r.situacao == 'ok' and r.codigo == 0, r
    dados = json.loads(r.stdout_bytes)
    assert dados['liberacao'] == plataforma.LINHA_LIBERAR.decode()
    assert dados['cwd'].lower() == str(trabalho).lower()
    assert dados['prefixo'].lower() == sys.prefix.lower()  # o mesmo ambiente, mesmo sem o lancador do venv
    assert dados['isolado'] == 1 and dados["sem_pyc"] == 1
    assert dados['fios'] == ['1', '1', '1'] and dados['extra'] == 'sim'
    assert r.pico_bytes and 0 < r.pico_bytes < 256 * MB
    assert r.motivo is None and r.tempo_s > 0
    assert not any(trabalho.iterdir())


def test_o_filho_importa_o_motor_dentro_do_job(win, trabalho):
    r = win.executar_isolado([sys.executable, '-I', '-B', '-c',
                              'import sys; sys.stdin.readline(); import desdobra, numpy, psd_tools; print("ok")'],
                             1024 * MB, 120, trabalho)
    assert r.situacao == 'ok' and r.codigo == 0 and r.stdout_bytes.strip() == b'ok', r.stderr_resumo


def test_estouro_de_memoria_aos_poucos_vira_memoria_sem_derrubar_o_pai(win, trabalho):
    teto = 256 * MB
    r = win.executar_isolado(filho('''
        blocos = []
        while True:
            blocos.append(bytearray(4 * 2 ** 20))
    '''), teto, 60, trabalho)
    assert r.situacao == 'memoria', r
    assert r.codigo not in (None, 0)
    assert r.pico_bytes <= teto
    assert str(teto) in r.motivo
    assert 'MemoryError' in r.stderr_resumo


def test_alocacao_unica_acima_do_teto_vira_memoria_pelo_aviso_do_job(win, trabalho):
    # O pico fica baixo (a alocacao inteira falha), entao quem acusa e o aviso da porta de conclusao.
    teto = 256 * MB
    r = win.executar_isolado(filho('''
        dados = bytearray(4 * 2 ** 30)
    '''), teto, 60, trabalho)
    assert r.situacao == 'memoria', r
    assert r.pico_bytes < limites.valor('isolador.fracao_pico_memoria') * teto


def test_memoria_tratada_pelo_filho_com_codigo_zero_fica_ok(win, trabalho):
    r = win.executar_isolado(filho('''
        try:
            dados = bytearray(4 * 2 ** 30)
        except MemoryError:
            print("tratado")
    '''), 256 * MB, 60, trabalho)
    assert r.situacao == 'ok' and r.codigo == 0 and r.stdout_bytes.strip() == b'tratado'


def test_laco_infinito_vira_tempo(win, trabalho):
    inicio = time.perf_counter()
    r = win.executar_isolado(filho('''
        while True:
            pass
    '''), 256 * MB, 2, trabalho)
    assert r.situacao == 'tempo', r
    assert '2 s' in r.motivo
    assert 1.9 <= r.tempo_s < 15 and time.perf_counter() - inicio < 20


def test_filho_que_nao_le_a_entrada_tambem_respeita_o_tempo(win, trabalho):
    r = win.executar_isolado([sys.executable, '-c', 'import time; time.sleep(60)'], 256 * MB, 1.5, trabalho)
    assert r.situacao == 'tempo'


@pytest.mark.parametrize('codigo, esperado', [
    ('import ctypes; ctypes.WinDLL("kernel32").DebugBreak()', 0x80000003),   # excecao de breakpoint nao tratada
    ('import faulthandler; faulthandler._read_null()', 0xC0000005),          # violacao de acesso no codigo nativo
    ('import os; os.abort()', 0xC0000409),                                    # abort do C (__fastfail)
])
def test_excecao_nativa_vira_queda_sem_janela_de_erro(win, trabalho, codigo, esperado):
    # Sem DIE_ON_UNHANDLED_EXCEPTION o Windows poderia abrir o relatorio de erro e o filho so sairia por tempo.
    r = win.executar_isolado(filho(codigo), 256 * MB, 60, trabalho)
    assert r.situacao == 'queda', r
    assert r.codigo == esperado
    assert '0x%08X' % esperado in r.motivo
    assert r.tempo_s < 30


def test_erro_fatal_do_python_sai_com_3_e_fica_ok(win, trabalho):
    # Py_FatalError sai com exit(3) no Windows, o mesmo numero do "recusado" do protocolo do filho. Por isso o
    # pai do leitor confere recusa.json no disco antes de tratar o codigo 3 como recusa (pendencia registrada).
    r = win.executar_isolado(filho('import faulthandler; faulthandler._fatal_error_c_thread()'), 256 * MB, 60,
                             trabalho)
    assert r.situacao == 'ok' and r.codigo == 3 and 'Fatal Python error' in r.stderr_resumo


def test_excecao_python_nao_tratada_fica_ok_com_o_codigo_do_filho(win, trabalho):
    # Contrato (docs/m1-interfaces.md, 10): o filho terminou sozinho; quem chamou interpreta o codigo 1 como bug.
    r = win.executar_isolado(filho('raise RuntimeError("falha sintetica")'), 256 * MB, 60, trabalho)
    assert r.situacao == 'ok' and r.codigo == 1
    assert 'RuntimeError' in r.stderr_resumo


def test_filho_nao_consegue_criar_outro_processo(win, trabalho):
    r = win.executar_isolado(filho('''
        import subprocess
        try:
            subprocess.run([sys.executable, "-c", "pass"], check=True)
            print("criou")
        except OSError as e:
            print("barrado", getattr(e, "winerror", None))
    '''), 256 * MB, 60, trabalho)
    assert r.situacao == 'ok', r
    assert r.stdout_bytes.split()[0] == b'barrado'


def test_stdout_e_cortado_no_teto_e_o_filho_nao_trava(win, trabalho):
    teto = limites.valor('isolador.stdout_max_bytes')
    r = win.executar_isolado(filho('''
        sys.stdout.buffer.write(b"x" * (3 * 2 ** 20))
        sys.stderr.buffer.write(b"y" * (3 * 2 ** 20) + b"FIM")
    '''), 256 * MB, 60, trabalho)
    assert r.situacao == 'ok' and r.codigo == 0
    assert len(r.stdout_bytes) == teto
    assert r.stderr_resumo.endswith('FIM') and len(r.stderr_resumo) < teto


def test_filho_morre_quando_o_pai_morre(tmp_path):
    # Um pai intermediario roda o isolador; o filho grava o proprio pid e fica parado. Matar o pai fecha o
    # Job Object (KILL_ON_JOB_CLOSE) e o filho tem de morrer junto.
    trabalho = tmp_path / 'trabalho'
    trabalho.mkdir()
    arquivo_pid = tmp_path / 'pid.txt'
    codigo_filho = ('import os, sys, time; sys.stdin.readline(); '
                    'open(sys.argv[1], "w").write(str(os.getpid())); time.sleep(120)')
    codigo_pai = textwrap.dedent('''
        import sys
        from desdobra import plataforma
        plataforma.obter().executar_isolado([sys.executable, "-c", sys.argv[1], sys.argv[2]], 256 * 2 ** 20, 120,
                                            sys.argv[3])
    ''')
    pai = subprocess.Popen([sys.executable, '-I', '-c', codigo_pai, codigo_filho, str(arquivo_pid), str(trabalho)])
    try:
        limite = time.monotonic() + 60
        while not (arquivo_pid.exists() and arquivo_pid.read_text()) and time.monotonic() < limite:
            time.sleep(0.05)
        pid = int(arquivo_pid.read_text())
        k32 = ctypes.WinDLL('kernel32', use_last_error=True)
        k32.OpenProcess.restype = ctypes.c_void_p
        k32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        k32.WaitForSingleObject.restype = ctypes.c_uint32
        k32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        k32.CloseHandle.argtypes = [ctypes.c_void_p]
        sincronizar = 0x00100000  # SYNCHRONIZE
        h = k32.OpenProcess(sincronizar, 0, pid)
        assert h, 'o filho deveria estar vivo antes de matar o pai'
        try:
            assert k32.WaitForSingleObject(h, 0) != 0, 'o filho nao deveria ter terminado ainda'
            pai.kill()
            pai.wait(30)
            assert k32.WaitForSingleObject(h, 15000) == 0, 'o filho continuou vivo depois do pai morrer'
        finally:
            k32.CloseHandle(h)
    finally:
        if pai.poll() is None:
            pai.kill()


@pytest.mark.parametrize('comando, orcamento, tempo, motivo', [
    ([], 256 * MB, 10, 'vazio'),
    ([sys.executable, '-c', 'pass'], 0, 10, 'orçamento'),
    ([sys.executable, '-c', 'pass'], 256 * MB, 0, 'tempo máximo'),
    ([sys.executable, '-c', 'pass'], 256 * MB, float('inf'), 'tempo máximo'),
    ([sys.executable, '-c', 'pass'], 2 ** 70, 10, 'passa do que o Windows aceita'),
    ([sys.executable, 3], 256 * MB, 10, 'não é texto'),
    (['C:/nao/existe/programa.exe'], 256 * MB, 10, 'não iniciou'),
])
def test_pedido_invalido_vira_recusado(win, trabalho, comando, orcamento, tempo, motivo):
    r = win.executar_isolado(comando, orcamento, tempo, trabalho)
    assert r.situacao == 'recusado' and r.codigo is None and motivo in r.motivo


def test_pasta_de_trabalho_tem_de_existir_e_estar_vazia(win, tmp_path):
    r = win.executar_isolado([sys.executable, '-c', 'pass'], 256 * MB, 10, tmp_path / 'nao-existe')
    assert r.situacao == 'recusado' and 'não existe' in r.motivo
    (tmp_path / 'sobra.txt').write_text('x')
    r = win.executar_isolado([sys.executable, '-c', 'pass'], 256 * MB, 10, tmp_path)
    assert r.situacao == 'recusado' and 'vazia' in r.motivo


def test_preparar_comando_garante_isolado_e_troca_o_lancador_do_venv():
    from desdobra.plataforma.windows import preparar_comando
    venv, base = r'C:\amb\Scripts\python.exe', r'C:\Python\python.exe'
    final, extra = preparar_comando([venv, '-m', 'desdobra'], venv, base)
    assert final == [base, '-I', '-B', '-m', 'desdobra'] and extra == {'__PYVENV_LAUNCHER__': venv}
    final, _ = preparar_comando([venv, '-IB', '-X', 'utf8', '-m', 'x'], venv, base)
    assert final == [base, '-IB', '-X', 'utf8', '-m', 'x']
    final, _ = preparar_comando([venv, '-X', 'utf8', '-I', '-c', 'pass'], venv, base)
    assert final == [base, '-B', '-X', 'utf8', '-I', '-c', 'pass']
    final, extra = preparar_comando([base, '-c', 'pass'], base, base)  # Python fora de venv: sem troca
    assert final == [base, '-I', '-B', '-c', 'pass'] and extra == {}
    final, extra = preparar_comando(['C:/outro.exe', '-c'], venv, base)  # outro programa: passa como veio
    assert final == ['C:/outro.exe', '-c'] and extra == {}


def test_variaveis_obrigatorias_prevalecem_sobre_o_ambiente_pedido():
    from desdobra.plataforma.windows import ambiente_do_filho
    env = ambiente_do_filho({'OMP_NUM_THREADS': '8', 'OUTRA': 'x'})
    assert env['OMP_NUM_THREADS'] == '1' and env['OUTRA'] == 'x' and env['PYTHONIOENCODING'] == 'utf-8'


def test_filho_nao_herda_token_nem_variavel_do_usuario(monkeypatch):
    from desdobra.plataforma.windows import VARIAVEIS_PERMITIDAS, ambiente_do_filho
    monkeypatch.setenv('CLAUDE_CODE_TOKEN_FICTICIO', 'segredo-ficticio')
    monkeypatch.setenv('USE_LOCAL_OAUTH', '1')
    monkeypatch.setenv('USERPROFILE_FICTICIO', 'C:/Users/ficticio')
    env = ambiente_do_filho()
    permitidas = set(VARIAVEIS_PERMITIDAS) | {'PATH', 'OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS',
                                              'PYTHONDONTWRITEBYTECODE', 'PYTHONIOENCODING'}
    assert set(env) <= permitidas
    assert 'segredo-ficticio' not in ''.join(env.values())
    assert os.path.dirname(sys.executable).lower() in env['PATH'].lower()


def test_classificacao():
    from desdobra.plataforma.windows import Mensagem, _classificar
    fracao = limites.valor('isolador.fracao_pico_memoria')

    def c(codigo, estourou=False, pico=MB, mensagens=()):
        return _classificar(codigo, estourou, pico, set(mensagens), 100 * MB, fracao, b'', '', 1.0, 10).situacao
    assert c(0) == 'ok'
    assert c(0, mensagens=[Mensagem.PROCESS_MEMORY_LIMIT]) == 'ok'
    assert c(3) == 'ok' and c(1) == 'ok'
    assert c(1, mensagens=[Mensagem.PROCESS_MEMORY_LIMIT]) == 'memoria'
    assert c(1, pico=100 * MB) == 'memoria'
    assert c(1, pico=None) == 'ok'
    assert c(0xC0000005) == 'queda' and c(0xC0000409) == 'queda'
    assert c(0xC0000017, mensagens=[Mensagem.PROCESS_MEMORY_LIMIT]) == 'memoria'
    assert c(None, estourou=True) == 'tempo'


def test_porta_livre_e_interpretador(win):
    porta = win.porta_livre()
    assert isinstance(porta, int) and porta > 0
    assert win.interpretador().is_file()
    with pytest.raises(NotImplementedError):
        win.fontes_instaladas()


def test_wintypes_so_no_isolador():
    from conftest import PASTA_PACOTE
    usam = sorted(p.relative_to(PASTA_PACOTE).as_posix() for p in PASTA_PACOTE.rglob('*.py')
                  if 'wintypes' in p.read_text(encoding='utf-8'))
    assert usam == ['plataforma/windows.py']
