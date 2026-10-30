# -*- coding: utf-8 -*-
"""Esteira de fases do job.

Uma Fase e um passo que o motor roda sozinho (tipo "fase") ou um portao humano (tipo "portao").
  - entradas: padroes glob relativos a pasta do job. O hash deles fica gravado quando a fase conclui; se um
    deles muda, a fase fica invalidada. As saidas das fases de que ela depende entram automaticamente.
  - depende_de: fases que precisam estar validas antes. Se uma delas fica invalida, esta tambem fica.
  - comando: devolve o argv que roda a fase num subprocesso. Codigo de retorno diferente de zero interrompe.
  - o_que_fazer: no portao, o que o humano precisa fazer; na fase, o que fazer quando ela falha.
  - cumprido: no portao, devolve True quando o humano ja fez a parte dele (por exemplo, gravou o briefing).
"""
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Fase:
    id: str
    tipo: str
    descricao: str
    entradas: tuple = ()
    depende_de: tuple = ()
    saidas: tuple = ()
    comando: Callable[[Path], list] | None = None
    o_que_fazer: str = ''
    cumprido: Callable[[Path], bool] | None = None

    def __post_init__(self):
        if self.tipo not in ('fase', 'portao'):
            raise ValueError('tipo de fase inválido: %r' % self.tipo)
        if self.tipo == 'fase' and self.comando is None:
            raise ValueError('a fase %s precisa de comando' % self.id)
        if self.tipo == 'portao' and self.cumprido is None:
            raise ValueError('o portão %s precisa da funcao cumprido' % self.id)


def comando_motor(*argumentos):
    """argv que roda um subcomando do proprio motor sobre a pasta do job, com o Python do ambiente.

    O subcomando roda com --envelope: o job proxima le a linha do envelope (ja filtrada pelo modo do job) e
    repassa contagens, ids, numeros e conteudo da fase no proprio Resultado."""
    def montar(pasta):
        return [sys.executable, '-I', '-B', '-m', 'desdobra', '--envelope', *argumentos, '--job', str(pasta)]
    return montar


FASES_M1 = (
    Fase(id='ler', tipo='fase', descricao='Leitura isolada do PSD e laudo',
         # entrada/campanha: o laudo propoe o casamento de cada smart object linkado com os arquivos dela
         entradas=('entrada/kv.*', 'entrada/campanha'), saidas=('laudo/laudo.json', 'sugestoes/pacote-modelo.json'),
         comando=comando_motor('ler'),
         o_que_fazer='A leitura do PSD falhou. Rode "desdobra job estado" para ver o código e "desdobra doctor" '
                     'para conferir o ambiente. Se o arquivo foi recusado, salve o PSD de novo no Photoshop e troque '
                     'a entrada com "desdobra job trocar-entrada".'),
)

FIM_M1 = ('O laudo está pronto em laudo/laudo.json. As próximas fases (fontes, specs, design system e briefing) '
          'entram nos marcos seguintes.')


def validar_esteira(fases):
    ids = [f.id for f in fases]
    if len(ids) != len(set(ids)):
        raise ValueError('ids de fase repetidos: %s' % ids)
    vistos = set()
    for f in fases:
        for d in f.depende_de:
            if d not in vistos:
                raise ValueError('a fase %s depende de %s, que não vem antes dela' % (f.id, d))
        vistos.add(f.id)
    return fases
