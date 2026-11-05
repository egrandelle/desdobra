# -*- coding: utf-8 -*-
"""Processos do Chromium com janela da tela (M7a1; decisoes-v1.md n 20, 156 e 158; proposta do M7, secao 3).

  - identidade(pid): o instante de criacao do processo vivo, ou None quando ele nao existe mais. O dono do perfil
    dsd-tela- guarda PID e identidade: um PID que o Windows reaproveitou para outro processo tem outra identidade, e
    a pasta conta como orfa;
  - descendentes(pid): os processos que nasceram dele (o driver do Playwright e o Chromium), pela foto de processos
    do sistema;
  - amarrar_ao_processo(): poe o proprio processo num Job Object com KILL_ON_JOB_CLOSE. O driver do Playwright e o
    Chromium nascem depois e herdam o job; quando este processo morre, mesmo morto a forca, o ultimo handle do job
    fecha e o Windows mata tudo o que estiver dentro. A amarra vale para o processo inteiro ate ele sair: so o
    processo da tela a pede (os testes rodam a janela num filho).

As chamadas ao Windows ficam em desdobra.plataforma.windows (o unico modulo do pacote com ctypes do Windows). Fora do
Windows, identidade so diz se o PID existe, e a amarra nao existe (a tela recusa abrir).
"""
import os
import sys

_JOB = None  # handle do job da amarra, guardado ate o processo sair (fechar o handle mataria a tela)


def identidade(pid):
    """Instante de criacao do processo `pid` enquanto ele roda, ou None quando ele nao existe ou ja saiu. Fora do
    Windows: o proprio pid quando ele existe."""
    if pid is None or int(pid) <= 0:
        return None
    if sys.platform == 'win32':
        from desdobra.plataforma import windows
        return windows.identidade_do_processo(int(pid))
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return None
    except PermissionError:
        return int(pid)
    return int(pid)


def vivo(pid, inicio):
    """O processo que gravou (pid, inicio) ainda roda: mesmo PID e mesma identidade."""
    atual = identidade(pid)
    return atual is not None and (inicio is None or atual == inicio)


def descendentes(pid):
    """[(pid, nome do executavel)] dos processos que descendem de `pid`, nascidos depois dele. So no Windows."""
    if sys.platform != 'win32':
        return []
    from desdobra.plataforma import windows
    tabela = windows.tabela_de_processos() or {}
    filhos = {}
    for filho, (nome, pai) in tabela.items():
        filhos.setdefault(pai, []).append((filho, nome))
    saida, fila, vistos = [], [(int(pid), identidade(pid))], {int(pid)}
    while fila:
        pai, inicio_pai = fila.pop()
        for filho, nome in filhos.get(pai, []):
            if filho in vistos:
                continue
            inicio = identidade(filho)
            # PID de pai reaproveitado: o filho de verdade nasce depois do pai
            if inicio is None or (inicio_pai is not None and inicio < inicio_pai):
                continue
            vistos.add(filho)
            saida.append((filho, nome))
            fila.append((filho, inicio))
    return saida


def amarrado(pid=None):
    """A amarra vale para este processo; com `pid`, o processo `pid` esta dentro do job da amarra."""
    if _JOB is None:
        return False
    if pid is None:
        return True
    from desdobra.plataforma import windows
    return windows.processo_no_job(_JOB, pid)


def amarrar_ao_processo():
    """Poe este processo num Job Object com KILL_ON_JOB_CLOSE (Windows). Devolve True quando a amarra vale (ja
    estava ou passou a valer) e False quando o sistema nao tem ou recusou."""
    global _JOB
    if _JOB is not None:
        return True
    if sys.platform != 'win32':
        return False
    from desdobra.plataforma import windows
    _JOB = windows.amarrar_este_processo()
    return _JOB is not None
