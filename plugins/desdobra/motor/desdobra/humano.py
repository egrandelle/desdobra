# -*- coding: utf-8 -*-
"""Disparo humano: o que so uma pessoa faz (render, confirmacoes, aprovacao e entrega) passa por aqui.

Regra (decisoes-v1.md, arquitetura n. 2 e n. 142): render, aprovacao, entrega e confirmacoes so partem do DA, pela
tela (M7) ou por um terminal interativo. O Claude nunca dispara. Este modulo:
  - confere o console do processo (console_interativo): nada de modo envelope; nada de variavel de ambiente que o
    Claude Code poe nos processos que ele abre; nada das marcas do painel de terminal do app do Claude (decisoes-v1.md,
    160: TERM_PROGRAM=claude-desktop, CLAUDE_AGENT_SDK_VERSION e, depois da conferencia do console, processo pai
    claude.exe na cadeia de pais, lida por uma foto dos processos do sistema; cadeia ilegivel recusa); no Windows, a entrada e a saida padrao tem de ser um console de
    verdade (GetFileType de caractere e GetConsoleMode que responde nos dois: o dispositivo nulo NUL e um arquivo de
    caractere sem modo de console, e por isso e recusado) e o processo tem de ter janela de console; fora do
    Windows, isatty nos dois;
  - emite um Disparo so depois dessa conferencia (exigir). O Disparo leva um selo aleatorio guardado neste processo,
    e quem grava o que so o DA pode gravar (o render, os linkados confirmados, as confirmacoes de spec, a aprovacao)
    confere o selo (conferir), e os parametros de entrega tambem. Nao ha parametro que pule a conferencia;
  - le as respostas do DA so pelo console (ler);
  - emite o Disparo da tela (exigir_tela, meio 'tela'; decisoes-v1.md, 159; proposta do M7, 159b): so o servidor da
    tela chama, no processo de fundo, depois do clique do DA na janela confirmado no dialogo da propria janela, sem
    opcao marcada, com o pedido de uso unico gasto. A sessao da tela (abrir_sessao_tela) so abre num processo sem o
    modo envelope e sem as marcas do Claude e do painel (o processo de fundo nasce com o ambiente por lista de
    permissao, desdobra.tela.ambiente_do_fundo). A prova do clique e o conjunto do servidor: cookie HttpOnly
    SameSite=Strict, entrada de uso unico, cabecalho X-Desdobra-CSRF com o token da pagina, Origin e Sec-Fetch-Site da
    propria origem e a confirmacao explicita; o selo do Disparo fica neste processo, como o do terminal;
  - no modo de teste da tela (proposta do M7, 159c), o Disparo sai com meio 'medicao' e origem 'fixture_de_teste', que
    o portao de entrega recusa.

Risco residual declarado: um processo do mesmo usuario, fora do Claude, com acesso ao console (por exemplo um
programa que abre um console novo e escreve teclas nele com WriteConsoleInputW) ainda passa por aqui. O gancho
PreToolUse do plugin (scripts/gancho_confirmacoes.py) cobre o caminho do Claude; um processo malicioso local fica
fora do que o motor consegue impedir. O processo pai que ja terminou some da foto, e a cadeia para nele: um processo
do Claude que abre um intermediario e o encerra antes do comando passa pela conferencia dos pais (as marcas de
ambiente continuam valendo se ele as herdar). Isso nao pede corrida: um comando comum (explorer.exe abrindo um .bat)
abre um console de verdade filho do explorer.exe, com o ambiente limpo dele, e a conferencia inteira passa; o que
segura esse caminho e o gancho (o painel negado sempre, decisoes-v1.md, 160) e as regras de permissao, nao o motor.
A cadeia para tambem no pai que nasceu depois do filho (PID reaproveitado pelo Windows, plataforma.cadeia_de_pais).
No Mac a cadeia de pais nao e lida (plataforma base), so as marcas.
Riscos residuais da tela (declarados na decisoes-v1.md, 159): outro processo local do mesmo usuario, e uma ferramenta
que controle a tela da maquina e clique no botao; os cookies do perfil cifrados pela DPAPI do Windows se leem por
qualquer processo do mesmo usuario. A protecao contra o Claude e o gancho e as regras de permissao, nao uma prova
tecnica.
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
# os mesmos do gancho PreToolUse (scripts/gancho_confirmacoes.py, SUBCOMANDOS_HUMANOS), com teste: aprovar e entregar
# so partem do DA (decisoes-v1.md, 138 e 142); briefing confirmar entra com a tela (M7); parametros-entrega grava as
# decisoes do DA por formato ate a tela (139)
COMANDOS = ('render', 'linkado confirmar', 'spec confirmar', 'briefing confirmar', 'aprovar', 'entregar',
            'parametros-entrega')
# atos que so existem como botao da tela, sem comando de terminal (decisoes-v1.md, 159 e 170): o Disparo deles sai so
# por exigir_tela. Ficam fora de COMANDOS e do gancho, que so conhece os comandos de terminal
ATOS_DA_TELA = ('modo dados escolher', 'familia confirmar')
# marcas do painel de terminal do app do Claude (decisoes-v1.md, 160), medidas no shell do painel em 04/11: o painel
# nao poe as VARIAVEIS_DO_CLAUDE, mas poe TERM_PROGRAM=claude-desktop e CLAUDE_AGENT_SDK_VERSION, e o shell dele e
# filho de claude.exe (powershell.exe -> claude.exe -> claude.exe -> sihost.exe). Cada marca recusa sozinha
MARCAS_DO_PAINEL = {'TERM_PROGRAM': 'claude-desktop'}
VARIAVEIS_DO_PAINEL = ('CLAUDE_AGENT_SDK_VERSION',)
PROCESSOS_DO_CLAUDE = ('claude.exe',)
O_QUE_FAZER = ('Isto é do DA: abra um terminal próprio (Prompt de Comando, PowerShell ou Terminal), fora do Claude, e '
               'rode o comando lá. O desdobra recusa rodar com --envelope, com a entrada ou a saída redirecionada, '
               'sem console interativo, em processo aberto pelo Claude ou no painel de terminal do app do Claude.')
TEXTO_MOTIVO = {
    'terminal_do_claude': ('O comando veio do painel de terminal do app do Claude ou de um processo aberto pelo '
                           'Claude, e o que só o DA faz não parte de lá.'),
    'cadeia_de_processos_ilegivel': ('O sistema não deixou ler os processos pais deste terminal, e sem isso o '
                                     'desdobra não confirma que o comando não veio do Claude.'),
}
MEIO_TERMINAL = 'terminal'
MEIO_TELA = 'tela'
MEIO_MEDICAO = 'medicao'
ORIGEM_DA = 'da'
ORIGEM_FIXTURE = 'fixture_de_teste'
_SELOS = {}
# sessoes da tela abertas neste processo: chave -> modo de teste (so o servidor da tela abre e fecha)
_SESSOES_TELA = {}


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
    origem: str = ORIGEM_DA

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


def _ancestrais():
    """Nomes dos processos pais deste processo (None quando o sistema nao deixou ler), ate o teto registrado."""
    from desdobra import limites, plataforma
    return plataforma.obter().processos_ancestrais(int(limites.valor('humano.profundidade_max_ancestrais')))


def _marca_do_painel():
    """O ambiente tem marca do painel de terminal do app do Claude (MARCAS_DO_PAINEL, VARIAVEIS_DO_PAINEL)."""
    if any((os.environ.get(v) or '').strip().lower() == valor for v, valor in MARCAS_DO_PAINEL.items()):
        return True
    return any(os.environ.get(v) for v in VARIAVEIS_DO_PAINEL)


def console_interativo():
    """(ok, motivo). Recusa o modo envelope, o ambiente aberto pelo Claude, o painel de terminal do app do Claude
    (marca de ambiente ou processo pai claude.exe), o console que nao e interativo e a cadeia de pais ilegivel."""
    if _modo_envelope():
        return False, 'modo_envelope'
    if any(os.environ.get(v) for v in VARIAVEIS_DO_CLAUDE):
        return False, 'processo_aberto_pelo_claude'
    if _marca_do_painel():
        return False, 'terminal_do_claude'
    ok, motivo = _console_do_sistema()
    if not ok:
        return ok, motivo
    try:
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            return False, 'sem_terminal'
    except (AttributeError, ValueError):
        return False, 'sem_terminal'
    pais = _ancestrais()
    if pais is None:
        return False, 'cadeia_de_processos_ilegivel'
    if any(str(n).strip().lower() in PROCESSOS_DO_CLAUDE for n in pais):
        return False, 'terminal_do_claude'
    return True, None


def exigir(comando):
    """Confere o console e emite o Disparo do comando. ErroHumano quando nao e uma pessoa num terminal."""
    if comando not in COMANDOS:
        raise ValueError('comando sem disparo humano: %r' % comando)
    ok, motivo = console_interativo()
    if not ok:
        raise ErroHumano(motivo)
    return _emitir(comando, MEIO_TERMINAL, ORIGEM_DA)


def _emitir(comando, meio, origem):
    try:
        usuario = getpass.getuser()
    except Exception:  # noqa: BLE001
        usuario = None
    selo = secrets.token_hex(16)  # numero-neutro: bytes de entropia do selo
    d = Disparo(comando=comando, meio=meio, usuario=usuario, maquina=_platform.node() or None,
                quando=datetime.now().astimezone().isoformat(timespec='seconds'), selo=selo, origem=origem)
    _SELOS[selo] = comando
    return d


@dataclass(frozen=True)
class SessaoTela:
    """A sessao do servidor da tela neste processo. So abrir_sessao_tela registra a chave; uma sessao montada a mao
    nao vale."""
    chave: str = field(repr=False)
    teste: bool = False


def ambiente_da_tela():
    """(ok, motivo) do processo do servidor da tela: nada de modo envelope, de variavel do Claude nem de marca do
    painel. Nao confere console: o processo de fundo da tela nao tem console, e a prova do clique e a do servidor."""
    if _modo_envelope():
        return False, 'modo_envelope'
    if any(os.environ.get(v) for v in VARIAVEIS_DO_CLAUDE):
        return False, 'processo_aberto_pelo_claude'
    if _marca_do_painel():
        return False, 'terminal_do_claude'
    return True, None


def abrir_sessao_tela(teste=False):
    """Abre a sessao do servidor da tela. ErroHumano quando o processo nao pode emitir o Disparo da tela (fora do modo
    de teste)."""
    if not teste:
        ok, motivo = ambiente_da_tela()
        if not ok:
            raise ErroHumano(motivo)
    chave = secrets.token_hex(16)  # numero-neutro: bytes de entropia da chave
    _SESSOES_TELA[chave] = bool(teste)
    return SessaoTela(chave=chave, teste=bool(teste))


def fechar_sessao_tela(sessao):
    if isinstance(sessao, SessaoTela):
        _SESSOES_TELA.pop(sessao.chave, None)


def exigir_tela(comando, sessao, confirmado):
    """O Disparo de um clique do DA na janela, confirmado no dialogo da propria janela. So o servidor da tela chama,
    depois de gastar o pedido de uso unico (confirmado=True). ErroHumano sem a confirmacao, com sessao que este
    processo nao abriu ou, fora do modo de teste, num processo com as marcas do Claude."""
    if comando not in COMANDOS + ATOS_DA_TELA:
        raise ValueError('comando sem disparo humano: %r' % comando)
    if confirmado is not True:
        raise ErroHumano('sem_confirmacao_na_tela')
    if not isinstance(sessao, SessaoTela) or _SESSOES_TELA.get(sessao.chave) is not sessao.teste:
        raise ErroHumano('sessao_da_tela_invalida')
    if sessao.teste:
        return _emitir(comando, MEIO_MEDICAO, ORIGEM_FIXTURE)
    ok, motivo = ambiente_da_tela()
    if not ok:
        raise ErroHumano(motivo)
    return _emitir(comando, MEIO_TELA, ORIGEM_DA)


def conferir(disparo, comando, consumir=False):
    """ErroHumano quando o disparo nao foi emitido por exigir(comando) neste processo."""
    if not isinstance(disparo, Disparo) or _SELOS.get(disparo.selo) != comando or disparo.comando != comando:
        raise ErroHumano('disparo_sem_conferencia')
    if consumir:
        del _SELOS[disparo.selo]
    return disparo


def gastar(disparo):
    """Gasta o disparo, se ainda vale (o de uso unico que nao chegou a gravar nada)."""
    if isinstance(disparo, Disparo):
        _SELOS.pop(disparo.selo, None)


def ler(pergunta):
    """Uma resposta do DA, pelo console."""
    return input(pergunta)
