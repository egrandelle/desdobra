# -*- coding: utf-8 -*-
"""O que todo comando da CLI devolve, e os codigos de retorno do motor.

Cada comando devolve um Resultado. A CLI decide como mostrar:
  - modo humano (padrao): imprime as linhas_humanas e o "O QUE FAZER";
  - modo envelope (--envelope, usado pelas skills): imprime so o envelope de saida filtrado pelo modo de
    dados (docs/m1-interfaces.md, secao Envelope). linhas_humanas nunca entram no envelope.

Regra para quem escreve um comando: o_que_fazer e as chaves de contagens, ids e numeros sao textos fixos do
motor. Nunca ponha nome de camada, texto de peca, nome de arquivo de cliente ou caminho neles. Conteudo do
job (nomes, textos, miniaturas) vai so em `conteudo`, que passa pelo filtro do modo e pelo detector de segredos.
"""
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path


class Codigo(IntEnum):
    """Codigos de retorno da CLI e das fases. Zero e sucesso; diferente de zero interrompe a fase."""
    OK = 0
    ERRO_INTERNO = 1      # excecao nao tratada: e bug do motor
    USO = 2               # argumentos invalidos
    RECUSADO = 3          # entrada recusada (arquivo invalido, contrato violado, entrada alterada fora do motor)
    ORCAMENTO = 4         # orcamento de memoria ou de tempo estourado de forma controlada
    AUDITORIA = 5         # o gancho de auditoria do filho barrou uma acao (alarme)
    NAO_DISPONIVEL = 9    # comando ainda nao existe neste build ou neste sistema
    PORTAO = 10           # parou num portao humano: ver o_que_fazer
    FASE_FALHOU = 20      # uma fase do job terminou com codigo diferente de zero
    OCUPADO = 21          # outro processo do desdobra esta usando o job
    REGRESSAO_PIOROU = 30  # a regressao achou piora contra a linha de base


SITUACOES = ('ok', 'ok_com_bloqueio', 'portao', 'concluido', 'erro', 'recusado', 'bloqueado', 'nao_disponivel')
MODOS_DADOS = ('a', 'b', 'c')  # do mais aberto ao mais fechado (arquitetura-v1.md, secao 7.4)


@dataclass
class Resultado:
    comando: str
    codigo: int = Codigo.OK
    situacao: str = 'ok'
    fase: str | None = None
    o_que_fazer: str | None = None
    contagens: dict = field(default_factory=dict)
    ids: dict = field(default_factory=dict)
    numeros: dict = field(default_factory=dict)
    conteudo: dict = field(default_factory=dict)
    pasta_job: Path | None = None
    linhas_humanas: list = field(default_factory=list)
    # camadas que um passo anterior (a fase rodada pelo job proxima) ja segurou no detector; somam no envelope
    segredos_ja_bloqueados: int = 0

    def __post_init__(self):
        if self.situacao not in SITUACOES:
            raise ValueError('situacao invalida: %r' % self.situacao)


def modo_mais_fechado(*modos):
    """Devolve o modo mais fechado entre os dados (None e ignorado). Sem nenhum modo, devolve 'c'."""
    validos = [m for m in modos if m is not None]
    for m in validos:
        if m not in MODOS_DADOS:
            raise ValueError('modo de dados invalido: %r' % m)
    if not validos:
        return 'c'
    return max(validos, key=MODOS_DADOS.index)


def modo_permitido(modo, teto):
    """True quando o modo escolhido e igual ou mais fechado que o teto da instalacao."""
    if modo not in MODOS_DADOS or teto not in MODOS_DADOS:
        return False
    return MODOS_DADOS.index(modo) >= MODOS_DADOS.index(teto)
