# -*- coding: utf-8 -*-
"""Gancho de auditoria do processo filho (sys.addaudithook): um alarme, nao uma sandbox.

Todo caminho e conferido depois de resolvido (os.path.realpath), para que link simbolico ou juncao dentro da
pasta de saida nao leve para fora dela.

Permite:
  - abrir para leitura o arquivo de entrada, os arquivos do Python e do ambiente (sys.prefix, sys.base_prefix,
    sys.exec_prefix) e os do motor (pacote desdobra, motor/schemas, motor/fontes-de-limites.json), menos
    arquivo de fonte;
  - gravar, renomear, apagar, criar pasta, copiar e mudar data so dentro da pasta de saida do filho, e nunca
    num arquivo com mais de um nome (hardlink) dentro dela;
  - listar pasta so dentro da pasta de saida, das raizes de leitura e das pastas do sys.path.
Barra (levanta PermissionError e registra o evento):
  - abrir qualquer outro arquivo;
  - criar link (os.link, os.symlink, _winapi.CreateJunction) e pipe com nome;
  - _winapi.CreateFile fora da pasta de saida, a nao ser leitura de caminho permitido;
  - criar processo (subprocess, os.system, exec, spawn, fork, startfile), abrir ou matar outro processo;
  - rede (socket.connect, bind, sendto, getaddrinfo e afins);
  - carregar biblioteca nativa por ctypes (ctypes.dlopen) depois de instalado (as bibliotecas do leitor ja foram
    carregadas antes);
  - ler ou gravar o registro do Windows (winreg).

Risco residual declarado (arquitetura-v1.md, 7.1): codigo nativo passa por fora do gancho, e os.stat e
os.path.exists nao geram evento de auditoria, entao o filho consegue saber se um caminho existe. Um gancho de
auditoria nao pode ser removido depois de instalado.
"""
import os
import sys

from desdobra.arquivos import EXTENSOES_FONTE

EVENTOS_PROCESSO = ('subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn', 'os.spawn', 'os.startfile',
                    'os.fork', 'os.forkpty', '_winapi.CreateProcess', 'pty.spawn', 'os.kill', 'os.killpg',
                    '_winapi.OpenProcess', '_winapi.TerminateProcess', 'signal.pthread_kill')
EVENTOS_REDE = ('socket.connect', 'socket.bind', 'socket.sendto', 'socket.sendmsg', 'socket.getaddrinfo',
                'socket.gethostbyname', 'socket.gethostbyaddr', 'socket.getnameinfo', 'urllib.Request')
EVENTOS_LINK = ('os.link', 'os.symlink', '_winapi.CreateJunction', '_winapi.CreateNamedPipe', 'ctypes.dlopen')
# evento -> quantos dos primeiros argumentos sao caminhos que tem de ficar dentro da pasta de saida
EVENTOS_ARQUIVO_SAIDA = {'os.rename': 2, 'os.remove': 1, 'os.rmdir': 1, 'os.mkdir': 1, 'os.chmod': 1,  # numero-neutro: aridade do evento
                         'os.truncate': 1, 'os.utime': 1, 'shutil.rmtree': 1, 'shutil.move': 2,  # numero-neutro: aridade do evento
                         'shutil.copyfile': 2, 'shutil.copymode': 2, 'shutil.copystat': 2,  # numero-neutro: aridade do evento
                         '_winapi.CopyFile2': 2}  # numero-neutro: aridade do evento
EVENTOS_LISTAGEM = ('os.listdir', 'os.scandir')
# _winapi.CreateFile: so leitura (GENERIC_READ) de arquivo que ja existe (OPEN_EXISTING) passa por caminho permitido
GENERIC_READ = 0x80000000  # numero-neutro: constante da API do Windows
OPEN_EXISTING = 3  # numero-neutro: constante da API do Windows


def _norm(p):
    try:
        return os.path.normcase(os.path.realpath(os.fsdecode(p)))
    except (TypeError, ValueError, OSError):
        return None


def _dentro(p, raiz):
    return p == raiz or p.startswith(raiz.rstrip(os.sep) + os.sep)


def _tem_outro_nome(p):
    """True quando o arquivo existe e tem mais de um nome (hardlink): gravar nele muda um arquivo de fora."""
    try:
        return os.stat(p).st_nlink > 1
    except OSError:
        return False


class Gancho:
    def __init__(self, entrada, pasta_saida, raizes_leitura):
        self.entrada = _norm(entrada)
        self.saida = _norm(pasta_saida)
        self.raizes = [r for r in (_norm(x) for x in raizes_leitura) if r]
        # o sistema de import lista as pastas do sys.path (que so tem codigo do ambiente e do motor)
        self.raizes_listagem = self.raizes + [r for r in (_norm(x) for x in sys.path if x) if r]
        self.bloqueios = []
        self.instalado = False

    def _barrar(self, evento, detalhe):
        self.bloqueios.append({'evento': evento, 'detalhe': detalhe})
        raise PermissionError('O gancho de auditoria do desdobra barrou %s.' % evento)

    def _na_saida(self, p):
        return bool(self.saida) and p is not None and _dentro(p, self.saida)

    def _leitura_permitida(self, p):
        if p == self.entrada or self._na_saida(p):
            return True
        if p.endswith(EXTENSOES_FONTE):
            return False
        return any(_dentro(p, r) for r in self.raizes)

    def _abrir(self, caminho, escrita, evento):
        p = _norm(caminho)
        if p is None:
            return
        if self._na_saida(p):
            if _tem_outro_nome(p):
                self._barrar(evento, 'arquivo com mais de um nome dentro da pasta de saida')
            return
        if escrita:
            self._barrar(evento, 'gravacao fora da pasta de saida')
        if self._leitura_permitida(p):
            return
        self._barrar(evento, 'leitura fora da entrada e do ambiente')

    def __call__(self, evento, args):
        if evento == 'open':
            caminho, modo, flags = (list(args) + [None, None, None])[:3]  # numero-neutro: o evento open tem 3 argumentos
            if caminho is None or isinstance(caminho, int):
                return
            escrita = (isinstance(modo, str) and any(c in modo for c in 'wax+')) or (
                isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND
                                                         | os.O_TRUNC)))
            self._abrir(caminho, escrita, 'open')
        elif evento == '_winapi.CreateFile':
            caminho, acesso, _comp, disposicao = (list(args) + [None] * 4)[:4]  # numero-neutro: argumentos do evento
            so_leitura = isinstance(acesso, int) and acesso & ~GENERIC_READ == 0 and disposicao == OPEN_EXISTING
            self._abrir(caminho, not so_leitura, evento)
        elif evento in EVENTOS_ARQUIVO_SAIDA:
            for a in args[:EVENTOS_ARQUIVO_SAIDA[evento]]:
                if isinstance(a, int) or a is None:
                    continue
                p = _norm(a)
                if not self._na_saida(p):
                    self._barrar(evento, 'alteracao de arquivo fora da pasta de saida')
                if _tem_outro_nome(p):
                    self._barrar(evento, 'arquivo com mais de um nome dentro da pasta de saida')
        elif evento in EVENTOS_LISTAGEM:
            alvo = args[0] if args else None
            p = _norm(alvo if alvo not in (None, b'', '') else '.')
            if p is None or not (self._na_saida(p) or any(_dentro(p, r) for r in self.raizes_listagem)):
                self._barrar(evento, 'listagem de pasta fora da saida e do ambiente')
        elif evento in EVENTOS_LINK:
            self._barrar(evento, 'link, pipe ou biblioteca nativa')
        elif evento.startswith('winreg.'):
            self._barrar(evento, 'registro do Windows')
        elif evento in EVENTOS_PROCESSO or evento.startswith('os.exec') or evento.startswith('os.spawn'):
            self._barrar(evento, 'processo')
        elif evento in EVENTOS_REDE:
            self._barrar(evento, 'rede')

    def instalar(self):
        sys.addaudithook(self)
        self.instalado = True


def raizes_do_ambiente(pasta_motor):
    raizes = {sys.prefix, sys.base_prefix, sys.exec_prefix, os.path.dirname(sys.executable)}
    raizes.add(os.path.join(os.fspath(pasta_motor), 'desdobra'))
    raizes.add(os.path.join(os.fspath(pasta_motor), 'schemas'))
    raizes.add(os.path.join(os.fspath(pasta_motor), 'fontes-de-limites.json'))
    return sorted(raizes)
