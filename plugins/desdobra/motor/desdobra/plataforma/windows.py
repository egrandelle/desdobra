# -*- coding: utf-8 -*-
"""Isolador do Windows: roda o processo filho dentro de um Job Object, so com a biblioteca padrao (ctypes).

Vem de p04_isolamento.py e p04_filho.py da pesquisa (pesquisa/render-local-pesquisa.md, 2), ja testados em
PSD sintetico. Este e o unico arquivo do motor que importa ctypes.wintypes.

Como o filho roda:
  1. o pai cria um Job Object com teto de memoria por processo (orcamento_bytes), no maximo 1 processo ativo,
     KILL_ON_JOB_CLOSE (o filho morre junto com o pai) e DIE_ON_UNHANDLED_EXCEPTION (excecao nativa mata o
     filho sem janela de erro), mais as restricoes de interface (RESTRICOES_UI: sem area de transferencia, sem
     janelas de outros processos, sem atomos globais). Uma porta de conclusao ligada ao job recebe o aviso de teto de memoria;
  2. o filho nasce SUSPENSO (CREATE_SUSPENDED), sem shell, sem janela, com cwd na pasta de trabalho vazia e
     stdin, stdout e stderr em pipe. Enquanto esta suspenso, nenhuma instrucao dele roda;
  3. o pai coloca o processo no job e so entao retoma a thread principal. Nao ha janela de corrida: o filho
     ja comeca confinado. Se a atribuicao falhar, o pai mata o filho e devolve 'recusado';
  4. depois disso o pai escreve LINHA_LIBERAR na entrada padrao e fecha a entrada (segunda trava, a do
     protocolo do filho: ele nao faz nada arriscado antes de ler essa linha);
  5. timeout de relogio no pai; ao estourar, TerminateJobObject e situacao 'tempo';
  6. ao fim, o pai le o pico de memoria do processo (PeakProcessMemoryUsed) e os avisos da porta de conclusao.

Python de venv: no Windows, o python.exe de um venv e um lancador que cria outro processo (o Python base).
Com o limite de 1 processo ativo, o lancador nao consegue criar o Python base e sai com 101. Por isso, quando
o comando comeca pelo Python deste ambiente e ele e um venv, o isolador troca o lancador pelo Python base e
passa __PYVENV_LAUNCHER__ com o caminho do lancador, do mesmo jeito que a biblioteca padrao faz em
multiprocessing/popen_spawn_win32.py (bpo-35797). O filho enxerga o mesmo sys.prefix e os mesmos pacotes.
"""
import collections
import ctypes
import enum
import math
import os
import subprocess
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

from desdobra import limites
from desdobra.plataforma import LINHA_LIBERAR, Plataforma, ResultadoFilho


class Limite(enum.IntFlag):
    """LimitFlags de JOBOBJECT_BASIC_LIMIT_INFORMATION (winnt.h)."""
    ACTIVE_PROCESS = 0x00000008
    PROCESS_MEMORY = 0x00000100
    DIE_ON_UNHANDLED_EXCEPTION = 0x00000400
    KILL_ON_JOB_CLOSE = 0x00002000


class RestricaoUI(enum.IntFlag):
    """UIRestrictionsClass de JOBOBJECT_BASIC_UI_RESTRICTIONS (winnt.h, JOB_OBJECT_UILIMIT_*)."""
    HANDLES = 0x00000001
    READCLIPBOARD = 0x00000002
    WRITECLIPBOARD = 0x00000004
    SYSTEMPARAMETERS = 0x00000008
    DISPLAYSETTINGS = 0x00000010
    GLOBALATOMS = 0x00000020
    DESKTOP = 0x00000040
    EXITWINDOWS = 0x00000080


# O filho le arquivo de cliente e nao precisa de nada da sessao do usuario: sem area de transferencia, sem janelas
# de outros processos, sem atomos globais, sem trocar desktop, configuracao do sistema ou da tela, sem encerrar o
# Windows (decisoes-v1.md, arquitetura n 25).
RESTRICOES_UI = (RestricaoUI.HANDLES | RestricaoUI.READCLIPBOARD | RestricaoUI.WRITECLIPBOARD
                 | RestricaoUI.SYSTEMPARAMETERS | RestricaoUI.DISPLAYSETTINGS | RestricaoUI.GLOBALATOMS
                 | RestricaoUI.DESKTOP | RestricaoUI.EXITWINDOWS)


class Criacao(enum.IntFlag):
    """dwCreationFlags de CreateProcess (processthreadsapi.h)."""
    CREATE_SUSPENDED = 0x00000004
    CREATE_NO_WINDOW = 0x08000000


class Acesso(enum.IntFlag):
    """Direitos de acesso pedidos ao abrir o processo e a thread do filho."""
    PROCESS_TERMINATE = 0x0001
    PROCESS_SET_QUOTA = 0x0100
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    THREAD_SUSPEND_RESUME = 0x0002


class Classe(enum.IntEnum):
    """JOBOBJECTINFOCLASS usadas aqui."""
    BASIC_UI_RESTRICTIONS = 4
    ASSOCIATE_COMPLETION_PORT = 7
    EXTENDED_LIMIT_INFORMATION = 9


class Mensagem(enum.IntEnum):
    """Mensagens do job na porta de conclusao (winnt.h, JOB_OBJECT_MSG_*)."""
    ACTIVE_PROCESS_LIMIT = 3
    EXIT_PROCESS = 7
    ABNORMAL_EXIT_PROCESS = 8
    PROCESS_MEMORY_LIMIT = 9


class Constante(enum.IntEnum):
    """Valores de protocolo do Windows e do isolador."""
    TH32CS_SNAPTHREAD = 0x00000004
    RESUME_FALHOU = 0xFFFFFFFF          # ResumeThread devolve (DWORD)-1 em erro
    SEVERIDADE_ERRO_NTSTATUS = 0x80000000  # codigo de saida com o bit alto ligado: NTSTATUS de aviso ou erro
    ENCERRADO_POR_TEMPO = 0xDE5D0001     # codigo de saida que o pai da ao filho no TerminateJobObject
    ENCERRADO_PELO_PAI = 0xDE5D0002      # idem, quando o pai desiste antes de liberar o filho


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [(n, ctypes.c_ulonglong) for n in ('ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
                                                 'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [('PerProcessUserTimeLimit', ctypes.c_longlong), ('PerJobUserTimeLimit', ctypes.c_longlong),
                ('LimitFlags', wintypes.DWORD), ('MinimumWorkingSetSize', ctypes.c_size_t),
                ('MaximumWorkingSetSize', ctypes.c_size_t), ('ActiveProcessLimit', wintypes.DWORD),
                ('Affinity', ctypes.c_size_t), ('PriorityClass', wintypes.DWORD), ('SchedulingClass', wintypes.DWORD)]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [('BasicLimitInformation', JOBOBJECT_BASIC_LIMIT_INFORMATION), ('IoInfo', IO_COUNTERS),
                ('ProcessMemoryLimit', ctypes.c_size_t), ('JobMemoryLimit', ctypes.c_size_t),
                ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]


class JOBOBJECT_BASIC_UI_RESTRICTIONS(ctypes.Structure):
    _fields_ = [('UIRestrictionsClass', wintypes.DWORD)]


class JOBOBJECT_ASSOCIATE_COMPLETION_PORT(ctypes.Structure):
    _fields_ = [('CompletionKey', wintypes.LPVOID), ('CompletionPort', wintypes.HANDLE)]


class THREADENTRY32(ctypes.Structure):
    _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD), ('th32ThreadID', wintypes.DWORD),
                ('th32OwnerProcessID', wintypes.DWORD), ('tpBasePri', wintypes.LONG), ('tpDeltaPri', wintypes.LONG),
                ('dwFlags', wintypes.DWORD)]


_INVALIDO = wintypes.HANDLE(-1).value  # INVALID_HANDLE_VALUE


def _kernel32():
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    assinaturas = {
        'CreateJobObjectW': (wintypes.HANDLE, [wintypes.LPVOID, wintypes.LPCWSTR]),
        'SetInformationJobObject': (wintypes.BOOL, [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]),
        'QueryInformationJobObject': (wintypes.BOOL, [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
                                                      wintypes.LPVOID]),
        'AssignProcessToJobObject': (wintypes.BOOL, [wintypes.HANDLE, wintypes.HANDLE]),
        'TerminateJobObject': (wintypes.BOOL, [wintypes.HANDLE, wintypes.UINT]),
        'TerminateProcess': (wintypes.BOOL, [wintypes.HANDLE, wintypes.UINT]),
        'OpenProcess': (wintypes.HANDLE, [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]),
        'OpenThread': (wintypes.HANDLE, [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]),
        'ResumeThread': (wintypes.DWORD, [wintypes.HANDLE]),
        'CloseHandle': (wintypes.BOOL, [wintypes.HANDLE]),
        'CreateIoCompletionPort': (wintypes.HANDLE, [wintypes.HANDLE, wintypes.HANDLE, ctypes.c_size_t,
                                                     wintypes.DWORD]),
        'GetQueuedCompletionStatus': (wintypes.BOOL, [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD),
                                                      ctypes.POINTER(ctypes.c_size_t),
                                                      ctypes.POINTER(wintypes.LPVOID), wintypes.DWORD]),
        'CreateToolhelp32Snapshot': (wintypes.HANDLE, [wintypes.DWORD, wintypes.DWORD]),
        'Thread32First': (wintypes.BOOL, [wintypes.HANDLE, ctypes.POINTER(THREADENTRY32)]),
        'Thread32Next': (wintypes.BOOL, [wintypes.HANDLE, ctypes.POINTER(THREADENTRY32)]),
    }
    for nome, (retorno, argumentos) in assinaturas.items():
        funcao = getattr(k32, nome)
        funcao.restype = retorno
        funcao.argtypes = argumentos
    return k32


class _ErroIsolador(Exception):
    """Falha do proprio isolador (nao do filho). Vira situacao 'recusado' com o motivo fixo."""

    def __init__(self, motivo, erro_windows=None):
        super().__init__(motivo)
        self.motivo = motivo if erro_windows is None else '%s (erro do Windows %d)' % (motivo, erro_windows)


def _mesmo_caminho(a, b):
    try:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))
    except (TypeError, ValueError):
        return False


def _opcoes_do_interpretador(argumentos):
    """Letras das opcoes curtas do Python antes do script, de -m ou de -c (ex.: ['-I', '-B'] -> {'I', 'B'})."""
    letras = set()
    pular_valor = False
    for arg in argumentos:
        if pular_valor:
            pular_valor = False
            continue
        if not arg.startswith('-') or arg == '-' or arg.startswith('--'):
            break
        for posicao, letra in enumerate(arg[1:]):
            if letra in 'mc':
                return letras  # o resto e o modulo ou o codigo
            if letra in 'XW':
                pular_valor = not arg[posicao + 2:]  # '-X utf8': o valor vem no proximo argumento
                break
            letras.add(letra)
    return letras


def preparar_comando(comando, interpretador_do_ambiente=None, executavel_base=None):
    """Devolve (comando_final, ambiente_extra).

    Quando comando[0] e o Python deste ambiente:
      - garante as opcoes -I (isolado: sem PYTHON*, sem pasta do script, sem site do usuario) e -B (sem .pyc);
      - se o ambiente e um venv, troca o lancador do venv pelo Python base e devolve __PYVENV_LAUNCHER__ (ver o
        cabecalho deste modulo).
    Outros comandos passam como vieram.
    """
    interpretador_do_ambiente = interpretador_do_ambiente or sys.executable
    executavel_base = executavel_base or getattr(sys, '_base_executable', sys.executable)
    comando = [os.fspath(c) for c in comando]
    if not _mesmo_caminho(comando[0], interpretador_do_ambiente):
        return comando, {}
    letras = _opcoes_do_interpretador(comando[1:])
    faltando = ['-%s' % letra for letra in ('I', 'B') if letra not in letras]
    final = [comando[0]] + faltando + comando[1:]
    extra = {}
    if executavel_base and not _mesmo_caminho(executavel_base, interpretador_do_ambiente):
        final[0] = os.fspath(executavel_base)
        extra['__PYVENV_LAUNCHER__'] = os.fspath(interpretador_do_ambiente)
    return final, extra


# Variaveis do pai que o filho recebe. O resto (tokens da sessao, credenciais, configuracao do usuario) fica de
# fora: o filho parseia arquivo de cliente e nao precisa de nada disso.
VARIAVEIS_PERMITIDAS = ('SYSTEMROOT', 'SYSTEMDRIVE', 'WINDIR', 'TEMP', 'TMP', 'PATHEXT', 'COMSPEC',
                        'NUMBER_OF_PROCESSORS', 'PROCESSOR_ARCHITECTURE', 'PROCESSOR_IDENTIFIER', 'OS')


def _path_minimo(interpretadores=()):
    """PATH so com a pasta do Python (e do ambiente) e as pastas do sistema."""
    raiz = os.environ.get('SYSTEMROOT') or os.environ.get('WINDIR') or 'C:\\Windows'
    pastas = []
    for p in list(interpretadores) + [sys.executable, getattr(sys, '_base_executable', None)]:
        if p:
            pastas.append(os.path.dirname(os.fspath(p)))
    pastas += [os.path.join(raiz, 'System32'), raiz]
    vistos, saida = set(), []
    for p in pastas:
        chave = os.path.normcase(p)
        if p and chave not in vistos:
            vistos.add(chave)
            saida.append(p)
    return os.pathsep.join(saida)


def ambiente_do_filho(ambiente=None, extra_lancador=None, interpretadores=()):
    """Ambiente minimo por lista de permissao (VARIAVEIS_PERMITIDAS e um PATH minimo), mais `ambiente`, mais as
    variaveis obrigatorias (que prevalecem). Nunca copia o ambiente inteiro do pai."""
    env = {k: os.environ[k] for k in VARIAVEIS_PERMITIDAS if k in os.environ}
    env['PATH'] = _path_minimo(interpretadores)
    env.update(ambiente or {})
    env.update(extra_lancador or {})
    env.update({'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
                'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONIOENCODING': 'utf-8'})
    return env


class _Leitor(threading.Thread):
    """Esvazia um pipe do filho ate o fim. Guarda o comeco (ate `teto` bytes) ou so o fim (cauda)."""

    def __init__(self, fluxo, teto, cauda=False):
        super().__init__(daemon=True)
        self.fluxo, self.teto, self.cauda = fluxo, teto, cauda
        self.partes = collections.deque()
        self.guardados = 0
        self.total = 0

    def run(self):
        try:
            while True:
                bloco = self.fluxo.read1(1 << 16)  # numero-neutro: tamanho do bloco de leitura do pipe
                if not bloco:
                    break
                self.total += len(bloco)
                if self.cauda:
                    self.partes.append(bloco)
                    self.guardados += len(bloco)
                    while self.partes and self.guardados - len(self.partes[0]) >= self.teto:
                        self.guardados -= len(self.partes.popleft())
                elif self.guardados < self.teto:
                    pedaco = bloco[:self.teto - self.guardados]
                    self.partes.append(pedaco)
                    self.guardados += len(pedaco)
        except (OSError, ValueError):
            pass
        finally:
            try:
                self.fluxo.close()
            except OSError:
                pass

    def bytes(self):
        dados = b''.join(self.partes)
        return dados[-self.teto:] if self.cauda else dados


class _Job:
    """Um Job Object com os limites do isolador e a porta de conclusao. Fechar mata o que estiver dentro."""

    def __init__(self, k32, teto_bytes):
        self.k32 = k32
        self.handle = None
        self.porta = None
        self.teto_bytes = teto_bytes
        self.handle = k32.CreateJobObjectW(None, None)
        if not self.handle:
            raise _ErroIsolador('O Windows não criou o Job Object.', ctypes.get_last_error())
        try:
            info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            info.BasicLimitInformation.LimitFlags = (Limite.PROCESS_MEMORY | Limite.ACTIVE_PROCESS
                                                     | Limite.KILL_ON_JOB_CLOSE | Limite.DIE_ON_UNHANDLED_EXCEPTION)
            info.BasicLimitInformation.ActiveProcessLimit = 1
            info.ProcessMemoryLimit = teto_bytes
            if not k32.SetInformationJobObject(self.handle, Classe.EXTENDED_LIMIT_INFORMATION, ctypes.byref(info),
                                               ctypes.sizeof(info)):
                raise _ErroIsolador('O Windows recusou os limites do Job Object.', ctypes.get_last_error())
            ui = JOBOBJECT_BASIC_UI_RESTRICTIONS(RESTRICOES_UI)
            if not k32.SetInformationJobObject(self.handle, Classe.BASIC_UI_RESTRICTIONS, ctypes.byref(ui),
                                               ctypes.sizeof(ui)):
                raise _ErroIsolador('O Windows recusou as restrições de interface do Job Object.',
                                    ctypes.get_last_error())
            self.porta = k32.CreateIoCompletionPort(_INVALIDO, None, 0, 1)
            if not self.porta:
                raise _ErroIsolador('O Windows não criou a porta de avisos do Job Object.', ctypes.get_last_error())
            assoc = JOBOBJECT_ASSOCIATE_COMPLETION_PORT(None, self.porta)
            if not k32.SetInformationJobObject(self.handle, Classe.ASSOCIATE_COMPLETION_PORT, ctypes.byref(assoc),
                                               ctypes.sizeof(assoc)):
                raise _ErroIsolador('O Windows não ligou a porta de avisos ao Job Object.', ctypes.get_last_error())
        except BaseException:
            self.fechar()
            raise

    def atribuir(self, pid):
        """Coloca o processo `pid` no job. Devolve o handle do processo (para matar se preciso)."""
        hproc = self.k32.OpenProcess(Acesso.PROCESS_SET_QUOTA | Acesso.PROCESS_TERMINATE
                                     | Acesso.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not hproc:
            raise _ErroIsolador('O Windows não deixou abrir o processo filho.', ctypes.get_last_error())
        if not self.k32.AssignProcessToJobObject(self.handle, hproc):
            erro = ctypes.get_last_error()
            self.k32.TerminateProcess(hproc, Constante.ENCERRADO_PELO_PAI)
            self.k32.CloseHandle(hproc)
            raise _ErroIsolador('O Windows não colocou o processo filho no Job Object.', erro)
        return hproc

    def terminar(self, codigo):
        if self.handle:
            self.k32.TerminateJobObject(self.handle, codigo)

    def pico_bytes(self):
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        if not self.k32.QueryInformationJobObject(self.handle, Classe.EXTENDED_LIMIT_INFORMATION, ctypes.byref(info),
                                                  ctypes.sizeof(info), None):
            return None
        return int(info.PeakProcessMemoryUsed)

    def mensagens(self):
        """Mensagens que a porta de conclusao recebeu ate agora (sem esperar). A entrega nao e garantida pelo
        Windows: a falta de uma mensagem nao prova que o evento nao aconteceu."""
        vistas = set()
        mensagem, chave, sobreposto = wintypes.DWORD(), ctypes.c_size_t(), wintypes.LPVOID()
        while self.porta and self.k32.GetQueuedCompletionStatus(self.porta, ctypes.byref(mensagem), ctypes.byref(chave),
                                                                ctypes.byref(sobreposto), 0):
            vistas.add(int(mensagem.value))
        return vistas

    def fechar(self):
        for nome in ('handle', 'porta'):
            h = getattr(self, nome)
            if h:
                self.k32.CloseHandle(h)
                setattr(self, nome, None)


def _retomar(k32, pid):
    """Retoma as threads do processo criado suspenso. O subprocess fecha o handle da thread principal, entao a
    thread e achada pela lista de threads do sistema (Toolhelp32)."""
    foto = k32.CreateToolhelp32Snapshot(Constante.TH32CS_SNAPTHREAD, 0)
    if not foto or foto == _INVALIDO:
        raise _ErroIsolador('O Windows não listou as threads do processo filho.', ctypes.get_last_error())
    retomadas = 0
    try:
        entrada = THREADENTRY32()
        entrada.dwSize = ctypes.sizeof(THREADENTRY32)
        tem = k32.Thread32First(foto, ctypes.byref(entrada))
        while tem:
            if entrada.th32OwnerProcessID == pid:
                hthread = k32.OpenThread(Acesso.THREAD_SUSPEND_RESUME, False, entrada.th32ThreadID)
                if not hthread:
                    raise _ErroIsolador('O Windows não deixou abrir a thread do processo filho.',
                                        ctypes.get_last_error())
                try:
                    if k32.ResumeThread(hthread) == Constante.RESUME_FALHOU:
                        raise _ErroIsolador('O Windows não retomou o processo filho.', ctypes.get_last_error())
                    retomadas += 1
                finally:
                    k32.CloseHandle(hthread)
            entrada.dwSize = ctypes.sizeof(THREADENTRY32)
            tem = k32.Thread32Next(foto, ctypes.byref(entrada))
    finally:
        k32.CloseHandle(foto)
    if not retomadas:
        raise _ErroIsolador('O processo filho não tem thread para retomar.')


def _recusado(motivo, inicio=None):
    tempo = time.perf_counter() - inicio if inicio is not None else 0.0
    return ResultadoFilho(situacao='recusado', codigo=None, pico_bytes=None, stdout_bytes=b'', stderr_resumo='',
                          tempo_s=tempo, motivo=motivo)


def _conferir_pedido(comando, orcamento_bytes, tempo_s, pasta_trabalho):
    """Texto do motivo quando o pedido e invalido; None quando esta certo."""
    if not isinstance(comando, (list, tuple)) or not comando:
        return 'O comando do processo filho veio vazio ou fora do formato de lista.'
    if not all(isinstance(c, (str, os.PathLike)) for c in comando):
        return 'O comando do processo filho tem argumento que não é texto.'
    if isinstance(orcamento_bytes, bool) or not isinstance(orcamento_bytes, int) or orcamento_bytes <= 0:
        return 'O orçamento de memória do processo filho tem de ser um número inteiro de bytes maior que zero.'
    if orcamento_bytes > ctypes.c_size_t(-1).value:
        return 'O orçamento de memória do processo filho passa do que o Windows aceita.'
    if isinstance(tempo_s, bool) or not isinstance(tempo_s, (int, float)) or not math.isfinite(tempo_s)             or not tempo_s > 0:
        return 'O tempo máximo do processo filho tem de ser um número finito maior que zero.'
    pasta = Path(pasta_trabalho)
    if not pasta.is_dir():
        return 'A pasta de trabalho do processo filho não existe.'
    if any(pasta.iterdir()):
        return 'A pasta de trabalho do processo filho tem de estar vazia.'
    return None


class PlataformaWindows(Plataforma):
    """Isolador por Job Object. Porta livre e interpretador vem da classe base (pelo sistema operacional e pelo
    Python deste ambiente)."""

    nome = 'windows'

    def __init__(self):
        self._k32 = _kernel32()

    def console_interativo(self):
        return console_do_windows()

    def executar_isolado(self, comando, orcamento_bytes, tempo_s, pasta_trabalho, *, ambiente=None, entrada=b''):
        inicio = time.perf_counter()
        try:
            problema = _conferir_pedido(comando, orcamento_bytes, tempo_s, pasta_trabalho)
        except OSError:
            problema = 'A pasta de trabalho do processo filho não pode ser lida.'
        if problema:
            return _recusado(problema, inicio)
        teto_stdout = int(limites.valor('isolador.stdout_max_bytes'))
        fracao_pico = float(limites.valor('isolador.fracao_pico_memoria'))
        teto_stderr = 8192  # numero-neutro: tamanho do resumo de diagnostico do stderr, nao decide nada

        try:
            final, extra = preparar_comando(comando, str(self.interpretador()))
            env = ambiente_do_filho(ambiente, extra, interpretadores=(final[0], self.interpretador()))
        except (TypeError, ValueError) as e:
            return _recusado('O comando do processo filho é inválido (%s).' % type(e).__name__, inicio)

        job = proc = hproc = None
        leitores = []
        try:
            try:
                job = _Job(self._k32, orcamento_bytes)
            except _ErroIsolador as e:
                return _recusado(e.motivo, inicio)
            try:
                proc = subprocess.Popen(final, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        cwd=os.fspath(pasta_trabalho), env=env, shell=False, close_fds=True,
                                        creationflags=Criacao.CREATE_SUSPENDED | Criacao.CREATE_NO_WINDOW)
            except (OSError, ValueError) as e:
                return _recusado('O Windows não iniciou o processo filho (%s).' % type(e).__name__, inicio)
            try:
                hproc = job.atribuir(proc.pid)
                _retomar(self._k32, proc.pid)
            except _ErroIsolador as e:
                job.terminar(Constante.ENCERRADO_PELO_PAI)
                try:
                    proc.kill()
                except OSError:
                    pass
                proc.wait()
                return _recusado(e.motivo, inicio)

            leitores = [_Leitor(proc.stdout, teto_stdout), _Leitor(proc.stderr, teto_stderr, cauda=True)]
            for leitor in leitores:
                leitor.start()
            # a entrada vai numa thread: um filho que nao le a entrada padrao nao segura o pai, e o relogio
            # (tempo_s) conta desde aqui; ao estourar, o job mata o filho e a escrita termina com erro de pipe
            escritor = threading.Thread(target=_escrever_entrada, args=(proc.stdin, entrada), daemon=True)
            escritor.start()

            estourou = False
            restante = max(float(tempo_s) - (time.perf_counter() - inicio), 0.0)
            try:
                proc.wait(timeout=restante)
            except subprocess.TimeoutExpired:
                estourou = True
                job.terminar(Constante.ENCERRADO_POR_TEMPO)
                proc.wait()
            decorrido = time.perf_counter() - inicio
            escritor.join()
            for leitor in leitores:
                leitor.join()
            pico = job.pico_bytes()
            mensagens = job.mensagens()
            stdout = leitores[0].bytes()
            stderr = leitores[1].bytes().decode('utf-8', 'replace')
            return _classificar(proc.returncode, estourou, pico, mensagens, orcamento_bytes, fracao_pico, stdout,
                                stderr, decorrido, tempo_s)
        finally:
            if hproc:
                self._k32.CloseHandle(hproc)
            if job is not None:
                job.terminar(Constante.ENCERRADO_PELO_PAI)  # nada fica vivo depois do retorno
                job.fechar()
            if proc is not None:
                for fluxo in (proc.stdin, proc.stdout, proc.stderr):
                    try:
                        if fluxo and not fluxo.closed:
                            fluxo.close()
                    except OSError:
                        pass


STD_INPUT_HANDLE = -10  # numero-neutro: constante da API do Windows
STD_OUTPUT_HANDLE = -11  # numero-neutro: constante da API do Windows
FILE_TYPE_CHAR = 2  # numero-neutro: constante da API do Windows


def console_do_windows(k32=None):
    """(ok, motivo): entrada e saida padrao de caractere com modo de console (GetFileType e GetConsoleMode: o NUL e
    um arquivo de caractere sem modo de console) e processo com janela de console."""
    k32 = k32 or ctypes.WinDLL('kernel32', use_last_error=True)
    k32.GetStdHandle.restype = wintypes.HANDLE
    k32.GetStdHandle.argtypes = (wintypes.DWORD,)
    k32.GetFileType.argtypes = (wintypes.HANDLE,)
    k32.GetConsoleMode.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    k32.GetConsoleWindow.restype = wintypes.HWND
    for nome, ident in (('entrada', STD_INPUT_HANDLE), ('saida', STD_OUTPUT_HANDLE)):
        h = k32.GetStdHandle(wintypes.DWORD(ident & 0xFFFFFFFF))  # numero-neutro: DWORD do identificador
        if not h:
            return False, 'sem_%s_padrao' % nome
        if k32.GetFileType(h) != FILE_TYPE_CHAR:
            return False, '%s_redirecionada' % nome
        modo = wintypes.DWORD()
        if not k32.GetConsoleMode(h, ctypes.byref(modo)):
            return False, '%s_sem_console' % nome
    if not k32.GetConsoleWindow():
        return False, 'console_sem_janela'
    return True, None


def _escrever_entrada(fluxo, entrada):
    """Escreve a linha de liberacao e a entrada na entrada padrao do filho e fecha. Nunca levanta excecao."""
    try:
        fluxo.write(LINHA_LIBERAR)
        if entrada:
            fluxo.write(entrada)
        fluxo.flush()
    except (OSError, ValueError):
        pass  # o filho ja terminou ou foi morto; a situacao sai do codigo de saida
    finally:
        try:
            fluxo.close()
        except (OSError, ValueError):
            pass


def _classificar(codigo, estourou, pico, mensagens, teto, fracao_pico, stdout, stderr, decorrido, tempo_s):
    """Regra do contrato (docs/m1-interfaces.md, 10):
      tempo    o pai matou por tempo;
      ok       codigo 0, ou codigo diferente de zero sem sinal de memoria nem de queda (o protocolo do filho decide);
      memoria  codigo diferente de zero e (aviso de teto na porta do job, ou pico >= isolador.fracao_pico_memoria
               do teto);
      queda    codigo diferente de zero com o bit alto ligado (NTSTATUS: excecao nativa, abort, erro do sistema).
    """
    base = dict(codigo=codigo, pico_bytes=pico, stdout_bytes=stdout, stderr_resumo=stderr, tempo_s=decorrido)
    if estourou:
        return ResultadoFilho(situacao='tempo', motivo='O processo filho passou do tempo máximo de %g s e foi '
                                                       'encerrado.' % tempo_s, **base)
    if codigo == 0:
        return ResultadoFilho(situacao='ok', **base)
    bateu_no_teto = Mensagem.PROCESS_MEMORY_LIMIT in mensagens
    perto_do_teto = pico is not None and pico >= fracao_pico * teto
    if bateu_no_teto or perto_do_teto:
        return ResultadoFilho(situacao='memoria', motivo='O processo filho bateu no teto de memória de %d bytes.'
                                                         % teto, **base)
    if codigo is not None and (codigo & Constante.SEVERIDADE_ERRO_NTSTATUS):
        return ResultadoFilho(situacao='queda', motivo='O processo filho terminou de forma anormal, com o código '
                                                       'do sistema 0x%08X.' % codigo, **base)
    return ResultadoFilho(situacao='ok', **base)
