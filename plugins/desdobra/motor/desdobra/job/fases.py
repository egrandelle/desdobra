# -*- coding: utf-8 -*-
"""Esteira de fases do job.

Uma Fase e um passo que o motor roda sozinho (tipo "fase") ou um portao humano (tipo "portao").
  - entradas: padroes glob relativos a pasta do job. O hash deles fica gravado quando a fase conclui; se um
    deles muda, a fase fica invalidada. As saidas das fases de que ela depende entram automaticamente.
  - depende_de: fases que precisam estar validas antes. Se uma delas fica invalida, esta tambem fica.
  - comando: devolve o argv que roda a fase num subprocesso. Codigo de retorno diferente de zero interrompe.
  - o_que_fazer: no portao, o que o humano precisa fazer; na fase, o que fazer quando ela falha.
  - cumprido: no portao, devolve True quando o humano ja fez a parte dele (por exemplo, gravou o briefing).
  - bloqueio_persiste: a fase que termina com bloqueio (envelope ok_com_bloqueio) grava o bloqueio no estado, e ele
    continua no job estado e em todo job proxima seguinte ate a fase rodar de novo sem bloqueio (o DA troca ou
    remove a entrada, ou libera pela entrada propria). Enquanto houver bloqueio, o job nao fica concluido.
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
    bloqueio_persiste: bool = False

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


def _fase_ds(anteriores):
    """Fase ds (M2): design system da peca e limites do job. Vem depois de ler e, quando a esteira tem, da
    conferencia de fontes; sem fontes/conferencia.json, sai com a pendencia "fontes nao conferidas"."""
    return Fase(id='ds', tipo='fase', descricao='Design system da peça e limites do job',
                entradas=('laudo/laudo.json', 'laudo/bruto/*/estrutura.json', 'fontes/conferencia.json',
                          'parametros/cor.json'),
                depende_de=tuple(f.id for f in anteriores if f.id in ('ler', 'fontes')),
                saidas=('ds/design-system.json', 'ds/limites.json'),
                comando=comando_motor('ds', 'montar'),
                o_que_fazer='A montagem do design system falhou. Rode "desdobra ds montar --job <pasta>" para ver '
                            'o motivo no terminal e "desdobra job estado" para ver o código.')


# M2, fontes (arquitetura-v1.md, 4.4 e 4.5): a conferencia contra o arquivo enviado em entrada/fontes/ e a
# segunda passada do laudo. A troca de um arquivo de fonte invalida so estas duas
# fases (e as que dependem delas); a leitura do PSD fica como esta.
FASE_FONTES = Fase(
    id='fontes', tipo='fase', descricao='Conferência das fontes contra os arquivos enviados',
    entradas=('entrada/fontes',), depende_de=('ler',),
    saidas=('fontes/conferencia.json',),
    comando=comando_motor('fontes', 'conferir'),
    # arquivo faltando, nome sem par, glifo faltando e fallback param o job (arquitetura-v1.md, 4.5); divergencia
    # de largura pede decisao do DA. Os dois casos ficam no estado ate a fase rodar sem bloqueio. Licenca nao entra
    # no portao (decisoes-v1.md, n. 19)
    bloqueio_persiste=True,
    o_que_fazer='A conferência de fontes falhou. Rode "desdobra fontes conferir --job <pasta>" para ver o motivo no '
                'terminal, "desdobra job estado" para ver o código e "desdobra doctor" para conferir o ambiente.')
FASE_LAUDO_FONTES = Fase(
    id='laudo-fontes', tipo='fase', descricao='Segunda passada do laudo com a conferência de fontes (regra B3)',
    depende_de=('ler', 'fontes'), saidas=('laudo/laudo-fontes.json',),
    comando=comando_motor('fontes', 'laudo'),
    o_que_fazer='A segunda passada do laudo falhou. Rode "desdobra fontes laudo --job <pasta>" para ver o motivo.')

_FASES_FONTES = FASES_M1 + (FASE_FONTES, FASE_LAUDO_FONTES)
FASES_M2 = _FASES_FONTES + (_fase_ds(_FASES_FONTES),)
# a esteira que job criar e job proxima usam
ESTEIRA = FASES_M2

FIM_M1 = ('O laudo está pronto em laudo/laudo.json. As próximas fases (fontes, specs, design system e briefing) '
          'entram nos marcos seguintes.')
FIM_M2 = ('O laudo, a conferência de fontes (fontes/conferencia.json e laudo/laudo-fontes.json) e o design system '
          'da peça estão prontos. As próximas fases (specs e briefing) entram nos marcos seguintes.')
FIM = FIM_M2


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
