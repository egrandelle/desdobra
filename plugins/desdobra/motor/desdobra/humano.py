# -*- coding: utf-8 -*-
"""Disparo humano: o que so uma pessoa faz (render, confirmacao de linkado, confirmacao de spec) passa por aqui.

Regra (decisoes-v1.md, arquitetura n. 2): render, aprovacao e confirmacoes so partem do DA, pela tela (M7) ou por um
terminal interativo. O Claude nunca dispara. Este modulo:
  - confere o console do processo (console_interativo): nada de modo envelope; nada de variavel de ambiente que o
    Claude Code poe nos processos que ele abre; no Windows, a entrada e a saida padrao tem de ser um console de
    verdade (GetFileType de caractere e GetConsoleMode que responde nos dois: o dispositivo nulo NUL e um arquivo de
    caractere sem modo de console, e por isso e recusado) e o processo tem de ter janela de console; fora do
    Windows, isatty nos dois;
  - emite um Disparo so depois dessa conferencia (exigir). O Disparo leva um selo aleatorio guardado neste processo,
    e quem grava o que so o DA pode gravar (o render, os linkados confirmados, as confirmacoes de spec) confere o selo
    (conferir). Nao ha parametro que pule a conferencia;
  - le as respostas do DA so pelo console (ler).

Risco residual declarado: um processo do mesmo usuario, fora do Claude, com acesso ao console (por exemplo um
programa que abre um console novo e escreve teclas nele com WriteConsoleInputW) ainda passa por aqui. O gancho
PreToolUse do plugin (scripts/gancho_confirmacoes.py) cobre o caminho do Claude; um processo malicioso local fica
fora do que o motor consegue impedir.
"""
import getpass
import os
import platform as _platform
import secrets
import sys
from dataclasses import dataclass, field
from datetime import datetime

# variaveis que o Claude Code poe no ambiente dos processos que ele abre (ferramentas Bash e PowerShell)
VARIAVEIS_DO_CLAUDE = ('CLAUDECODE', 'CLAUDE_CODE_ENTRYPOINT', 'CLAUDE_CODE_SESSION_ID', 'CLAUDE_PID', 'AI_AGENT')
COMANDOS = ('render', 'linkado confirmar', 'spec confirmar')
O_QUE_FAZER = ('Isto é do DA: abra um terminal próprio (Prompt de Comando, PowerShell ou Terminal), fora do Claude, e '
               'rode o comando lá. O desdobra recusa rodar com --envelope, com a entrada ou a saída redirecionada, '
               'sem console interativo ou em processo aberto pelo Claude.')
_SELOS = {}


class ErroHumano(Exception):
    """A conferencia do disparo humano recusou. A mensagem e texto fixo do motor."""


@dataclass(frozen=True)
class Disparo:
    comando: str
    meio: str
    usuario: str | None
    maquina: str | None
    quando: str
    selo: str = field(repr=False, default='')

    def registro(self):
        """O que vai para o render.json e para os arquivos de confirmacao (sem o selo)."""
        return {'meio': self.meio, 'usuario': self.usuario, 'maquina': self.maquina, 'quando': self.quando}


def _modo_envelope():
    try:
        from desdobra import cli
        return bool(getattr(cli._Analisador, 'modo_envelope', False))
    except ImportError:
        return False


def _console_do_sistema():
    """(ok, motivo) do console do processo, pela interface de plataforma (no Windows, o modo de console)."""
    from desdobra import plataforma
    return plataforma.obter().console_interativo()


def console_interativo():
    """(ok, motivo). Recusa o modo envelope, o ambiente aberto pelo Claude e o console que nao e interativo."""
    if _modo_envelope():
        return False, 'modo_envelope'
    if any(os.environ.get(v) for v in VARIAVEIS_DO_CLAUDE):
        return False, 'processo_aberto_pelo_claude'
    ok, motivo = _console_do_sistema()
    if not ok:
        return ok, motivo
    try:
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            return False, 'sem_terminal'
    except (AttributeError, ValueError):
        return False, 'sem_terminal'
    return True, None


def exigir(comando):
    """Confere o console e emite o Disparo do comando. ErroHumano quando nao e uma pessoa num terminal."""
    if comando not in COMANDOS:
        raise ValueError('comando sem disparo humano: %r' % comando)
    ok, motivo = console_interativo()
    if not ok:
        raise ErroHumano(motivo)
    try:
        usuario = getpass.getuser()
    except Exception:  # noqa: BLE001
        usuario = None
    selo = secrets.token_hex(16)  # numero-neutro: bytes de entropia do selo
    d = Disparo(comando=comando, meio='terminal', usuario=usuario, maquina=_platform.node() or None,
                quando=datetime.now().astimezone().isoformat(timespec='seconds'), selo=selo)
    _SELOS[selo] = comando
    return d


def conferir(disparo, comando, consumir=False):
    """ErroHumano quando o disparo nao foi emitido por exigir(comando) neste processo."""
    if not isinstance(disparo, Disparo) or _SELOS.get(disparo.selo) != comando or disparo.comando != comando:
        raise ErroHumano('disparo_sem_conferencia')
    if consumir:
        del _SELOS[disparo.selo]
    return disparo


def ler(pergunta):
    """Uma resposta do DA, pelo console."""
    return input(pergunta)
