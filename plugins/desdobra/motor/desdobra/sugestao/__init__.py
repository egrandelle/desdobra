# -*- coding: utf-8 -*-
"""Fronteira com o modelo (arquitetura-v1.md, 4.9): a unica porta por onde conteudo do job chega ao Claude.

  - segredos.py:   detector de segredos (padroes do registro, segredos.padroes) sobre nomes e textos;
  - envelope.py:   o envelope de saida que o motor imprime com --envelope, filtrado pelo modo de dados;
  - miniaturas.py: as miniaturas que o Claude pode ver no modo (a), copiadas para sugestoes/miniaturas/ (M7c, S1);
  - pacote.py:     sugestoes/pacote-modelo.json (pacote-modelo/2) por modo, refeito quando o modo ou o PSD muda
                   (M7c, S2);
  - specs.py:      sugestoes/pacote-specs.json e a volta das propostas de trecho para campo.

Achado de segredo vira bloqueio: a camada sai do envelope e do pacote, e o detalhe (layer_id e nome do
padrao, nunca o trecho achado) vai so para sugestoes/segredos-bloqueados.json, que so o DA ve.

Subcomando "desdobra sugestao pacote --job <pasta>" (M7c, S2): nao e ato do DA (nao esta em humano.COMANDOS). Refaz os
dois pacotes no modo efetivo de agora, com o teto da linha de comando, e devolve so contagens; o modo vai no proprio
envelope.
"""
import time
from pathlib import Path

from desdobra.resultado import Codigo, Resultado

COMANDO_PACOTE = 'sugestao pacote'


def registrar(subparsers):
    p = subparsers.add_parser('sugestao', help='Fronteira com o Claude: pacotes para a sugestão de função')
    sub = p.add_subparsers(dest='acao_sugestao', metavar='ACAO', required=True)
    pc = sub.add_parser('pacote', help='Refaz o pacote do modelo e o das specs no modo de dados de agora')
    pc.add_argument('--job', required=True, help='Pasta do job')
    pc.set_defaults(executar=_pacote, nome_comando=COMANDO_PACOTE)


def _pacote(args):
    from desdobra.job import nucleo
    from desdobra.sugestao import pacote
    pasta = Path(args.job).resolve()
    if not (pasta / nucleo.ARQUIVO_ESTADO).is_file():
        return Resultado(comando=COMANDO_PACOTE, codigo=int(Codigo.USO), situacao='erro',
                         o_que_fazer='Passe a pasta de um job do desdobra.', linhas_humanas=['A pasta não é um job.'])
    inicio = time.monotonic()
    try:
        r = pacote.refazer_pacotes(pasta, teto=getattr(args, 'teto_modo_dados', None))
    except Exception:  # noqa: BLE001 - na falha, o Claude fica sem nada para ler
        pacote.fechar(pasta)
        return Resultado(comando=COMANDO_PACOTE, codigo=int(Codigo.ERRO_INTERNO), situacao='erro', pasta_job=pasta,
                         o_que_fazer='Os pacotes do job não puderam ser refeitos e foram apagados. Rode "desdobra '
                                     'job proxima" e depois este comando de novo.',
                         linhas_humanas=['Os pacotes não puderam ser refeitos.'])
    contagens = {k: v for k, v in r.items() if k != 'modo'}
    return Resultado(comando=COMANDO_PACOTE, situacao='ok', pasta_job=pasta, contagens=contagens,
                     numeros={'tempo_s': round(time.monotonic() - inicio, 3)},  # numero-neutro: milissegundos
                     linhas_humanas=['Pacotes refeitos: %d camadas, %d miniaturas.' % (r['camadas'],
                                                                                       r['miniaturas'])])
