# -*- coding: utf-8 -*-
"""O modo de dados do job, escolhido pelo DA na tela (decisoes-v1.md, 170; proposta do M7, 163).

Fonte unica: briefing/modo-dados.json (modo-dados/1), gravado so pelo servidor da tela, com o Disparo do clique do DA
confirmado na janela (comando ESCOLHER, humano.ATOS_DA_TELA). Regras:
  - o estado.json deixa de ser fonte do modo: o modo_dados que o job criar grava la fica so como registro do pedido,
    e o job antigo, sem escolha na tela, e lido como modo c;
  - ate existir uma escolha com origem da, o envelope, o pacote e as sugestoes tratam o job como modo c (efetivo);
  - a escolha de teste (origem fixture_de_teste, o modo de teste da tela) nunca abre o modo: conta como sem escolha;
  - a escolha nunca passa do teto da agencia (opcoes): o teto do estado.json e o da linha de comando, o mais fechado;
    e o efetivo limita de novo pelo teto de agora, mesmo que o teto tenha fechado depois da escolha.
Risco declarado (o da proposta, 163): o teto chega pela opcao que a skill passa; um teto imposto por configuracao
gerenciada fica para o M8.
"""
from pathlib import Path

from desdobra import arquivos, contratos
from desdobra.resultado import MODOS_DADOS, modo_mais_fechado, modo_permitido

ARQUIVO = Path('briefing') / 'modo-dados.json'
ESQUEMA = 'modo-dados/1'
ESCOLHER = 'modo dados escolher'
ORIGEM_DA = 'da'


class ErroModo(Exception):
    pass


def teto(*tetos):
    """O teto mais fechado entre os dados (None e ignorado); None quando nenhum."""
    validos = [t for t in tetos if t is not None]
    return modo_mais_fechado(*validos) if validos else None


def teto_do_job(pasta, teto_cli=None):
    """O teto do estado.json do job junto com o da linha de comando."""
    try:
        estado = arquivos.ler_json(Path(pasta) / 'estado.json')
    except (OSError, ValueError):
        estado = {}
    t = estado.get('teto_modo_dados') if isinstance(estado, dict) else None
    return teto(t if t in MODOS_DADOS else None, teto_cli)


def opcoes(teto_):
    """Os modos que a tela pode oferecer sob o teto, do mais aberto ao mais fechado."""
    return [m for m in MODOS_DADOS if teto_ is None or modo_permitido(m, teto_)]


def ler(pasta):
    """O registro da escolha, ou None (sem arquivo ou arquivo fora do contrato)."""
    arq = Path(pasta) / ARQUIVO
    if not arq.is_file():
        return None
    try:
        return contratos.ler(arq, ESQUEMA)
    except (contratos.ErroContrato, OSError, ValueError):
        return None


def escolhido(pasta):
    """O modo escolhido pelo DA na tela, ou None (sem escolha, escolha de teste ou arquivo ilegivel)."""
    reg = ler(pasta)
    if reg is None or reg['origem'] != ORIGEM_DA:
        return None
    return reg['valor']


def efetivo(pasta, *tetos):
    """O modo que vale para o job: o escolhido pelo DA limitado pelos tetos; sem escolha, c."""
    m = escolhido(pasta) if pasta is not None else None
    if m is None:
        return 'c'
    return modo_mais_fechado(m, *[t for t in tetos if t is not None])


def gravar(pasta, valor, *, disparo, teto_=None):
    """Grava a escolha do DA. disparo: o da tela (humano.exigir_tela(ESCOLHER, ...)); ErroModo para modo fora das
    opcoes do teto."""
    from desdobra import humano
    from desdobra.job import nucleo
    humano.conferir(disparo, ESCOLHER, consumir=True)
    pasta = Path(pasta).resolve()
    if valor not in opcoes(teto_):
        raise ErroModo('modo acima do teto da agencia')
    with nucleo.Trava(pasta):
        estado = contratos.ler(pasta / 'estado.json', 'estado/1')
        reg = disparo.registro()
        dados = {'esquema': ESQUEMA, 'job_id': estado['job_id'], 'valor': valor, 'teto': teto_,
                 'origem': disparo.origem,
                 'escolhido_por': {'usuario': reg['usuario'], 'maquina': reg['maquina'], 'meio': reg['meio'],
                                   'quando': reg['quando']}}
        contratos.gravar(pasta / ARQUIVO, dados, ESQUEMA)
        nucleo.registrar_evento(pasta, 'modo_dados_escolhido', valor=valor, origem=disparo.origem)
    return dados
