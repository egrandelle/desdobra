# -*- coding: utf-8 -*-
"""Interface de plataforma: tudo o que muda entre Windows e Mac fica atras desta classe.

So a interface mora aqui. As implementacoes ficam em plataforma/windows.py (Job Object via ctypes) e
plataforma/mac.py (esqueleto que recusa rodar com mensagem clara). obter() devolve a do sistema atual.
O contrato completo esta em docs/m1-interfaces.md, secao "Interface de plataforma".
"""
import abc
import importlib
import socket
import sys
from dataclasses import dataclass
from pathlib import Path

SITUACOES_FILHO = ('ok', 'memoria', 'tempo', 'queda', 'recusado')
LINHA_LIBERAR = b'iniciar\n'


@dataclass(frozen=True)
class ResultadoFilho:
    """Como o processo filho terminou.

    situacao:
      ok        o filho terminou sozinho; o codigo dele esta em `codigo` (pode ser diferente de zero: quem chamou
                interpreta pelo protocolo do filho);
      memoria   o filho bateu no teto de memoria (morto pelo sistema, ou falhou com pico perto do teto);
      tempo     o pai matou o filho porque passou do tempo de relogio;
      queda     o filho terminou de forma anormal (excecao nativa, codigo de erro do sistema, sinal);
      recusado  a plataforma nao executou o filho (sistema sem suporte, isolamento indisponivel, comando invalido).
    codigo: codigo de retorno do filho; None quando ele nem rodou (recusado).
    pico_bytes: pico de memoria do filho medido pelo sistema; None se o sistema nao mede.
    stdout_bytes: os bytes que o filho escreveu na saida padrao, ate o teto isolador.stdout_max_bytes.
    stderr_resumo: fim da saida de erro, em texto, so para diagnostico humano (pode conter conteudo do
      arquivo; nunca vai para o envelope, para o log do job nem para o laudo).
    tempo_s: tempo de relogio do filho.
    motivo: texto fixo da plataforma explicando recusado, memoria, tempo ou queda (sem conteudo do arquivo).
    """
    situacao: str
    codigo: int | None
    pico_bytes: int | None
    stdout_bytes: bytes
    stderr_resumo: str
    tempo_s: float = 0.0
    motivo: str | None = None

    def __post_init__(self):
        if self.situacao not in SITUACOES_FILHO:
            raise ValueError('situacao invalida: %r' % self.situacao)


@dataclass(frozen=True)
class FaceInstalada:
    """Uma face de fonte instalada (M2). Nunca guarda o arquivo da fonte, so os nomes e a origem."""
    nome_postscript: str
    familia: str
    estilo: str
    origem: str  # 'cliente' ou 'sistema'


class Plataforma(abc.ABC):
    """Contrato que cada sistema implementa."""

    nome = 'abstrata'

    @abc.abstractmethod
    def executar_isolado(self, comando, orcamento_bytes, tempo_s, pasta_trabalho, *, ambiente=None):
        """Roda `comando` (lista de argumentos, sem shell) num processo filho isolado e devolve ResultadoFilho.

        Obrigacoes da implementacao:
          - teto de memoria do processo = orcamento_bytes; no maximo 1 processo ativo (o filho nao cria outro);
            o filho morre se o pai morrer; excecao nao tratada mata o filho sem janela de erro;
          - timeout de relogio no pai = tempo_s; ao estourar, mata o filho e devolve situacao 'tempo';
          - cwd = pasta_trabalho (o chamador entrega uma pasta vazia);
          - ambiente = o do pai, mais OPENBLAS_NUM_THREADS=1, OMP_NUM_THREADS=1, MKL_NUM_THREADS=1,
            PYTHONDONTWRITEBYTECODE=1, PYTHONIOENCODING=utf-8, mais `ambiente` se vier;
          - so depois de confinar o processo, escreve LINHA_LIBERAR na entrada padrao do filho e fecha a entrada.
            O filho nao faz nada arriscado antes de ler essa linha;
          - nunca levanta excecao por causa do filho: tudo vira ResultadoFilho.
        """

    def fontes_instaladas(self):
        """Lista de FaceInstalada, separando fonte de cliente de fonte do sistema. Entra no M2."""
        raise NotImplementedError('fontes_instaladas entra no M2')

    def porta_livre(self):
        """Uma porta TCP livre em 127.0.0.1, escolhida pelo sistema."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', 0))
            return s.getsockname()[1]

    def interpretador(self):
        """Caminho do Python do ambiente do motor (o que roda este processo)."""
        return Path(sys.executable)


class PlataformaSemSuporte(Plataforma):
    """Sistema sem implementacao: recusa executar, com mensagem clara."""

    nome = 'sem-suporte'

    def __init__(self, motivo):
        self.motivo = motivo

    def executar_isolado(self, comando, orcamento_bytes, tempo_s, pasta_trabalho, *, ambiente=None):
        return ResultadoFilho(situacao='recusado', codigo=None, pico_bytes=None, stdout_bytes=b'', stderr_resumo='',
                              motivo=self.motivo)


_IMPLEMENTACOES = {'win32': ('desdobra.plataforma.windows', 'PlataformaWindows'),
                   'darwin': ('desdobra.plataforma.mac', 'PlataformaMac')}


def obter(sistema=None):
    """Devolve a implementacao de Plataforma do sistema atual (ou de `sistema`, para teste)."""
    sistema = sistema or sys.platform
    if sistema not in _IMPLEMENTACOES:
        return PlataformaSemSuporte('O desdobra roda no Windows. O sistema %s não tem suporte.' % sistema)
    modulo, classe = _IMPLEMENTACOES[sistema]
    try:
        return getattr(importlib.import_module(modulo), classe)()
    except ModuleNotFoundError as e:
        if e.name != modulo:
            raise
        return PlataformaSemSuporte('A implementação de plataforma para %s ainda não está neste build.' % sistema)
