# -*- coding: utf-8 -*-
"""Fronteira com o modelo (arquitetura-v1.md, 4.9): a unica porta por onde conteudo do job chega ao Claude.

  - segredos.py:   detector de segredos (padroes do registro, segredos.padroes) sobre nomes e textos;
  - envelope.py:   o envelope de saida que o motor imprime com --envelope, filtrado pelo modo de dados;
  - miniaturas.py: as miniaturas que o Claude pode ver no modo (a), copiadas para sugestoes/miniaturas/ (M7c, S1);
  - pacote.py:     sugestoes/pacote-modelo.json (pacote-modelo/2) por modo, refeito quando o modo ou o PSD muda
                   (M7c, S2);
  - specs.py:      sugestoes/pacote-specs.json e a volta das propostas de trecho para campo;
  - importar.py:   a conferencia de sugestoes/sugestoes.json, que o Claude escreve, e a gravacao de
                   sugestoes/sugestoes-validadas.json (contrato sugestoes/1; M7c, S3).

Achado de segredo vira bloqueio: a camada sai do envelope e do pacote, e o detalhe (layer_id e nome do
padrao, nunca o trecho achado) vai so para sugestoes/segredos-bloqueados.json, que so o DA ve.

Subcomando "desdobra sugestao pacote --job <pasta>" (M7c, S2): nao e ato do DA (nao esta em humano.COMANDOS). Refaz os
dois pacotes no modo efetivo de agora, com o teto da linha de comando, e devolve so contagens; o modo vai no proprio
envelope, e o sha256 do pacote-modelo.json gravado vai em ids.pacote_sha256 (o Claude o cita no sugestoes.json; M7c, S3).

Subcomando "desdobra sugestao importar --job <pasta>" (M7c, S3): tambem nao e ato do DA. Confere sugestoes/sugestoes.json
pelo desdobra.sugestao.importar, com o teto da linha de comando, e devolve so contagens (aceitas, recusadas e
recusa_<codigo>) e numeros.tempo_s; nunca nome, texto ou caminho.
"""
import hashlib
import time
from pathlib import Path

from desdobra.resultado import Codigo, Resultado

COMANDO_PACOTE = 'sugestao pacote'
COMANDO_IMPORTAR = 'sugestao importar'
# o que o Claude faz com cada recusa do arquivo inteiro (o texto vai no envelope; nunca cita nome nem texto do job)
O_QUE_FAZER_IMPORTAR = {
    'modo_c': 'O modo de dados do job é (c): não há sugestão. A tela segue sem sugestão; nada a fazer.',
    'sem_sugestoes': 'Escreva sugestoes/sugestoes.json no job (contrato sugestoes/1) e rode este comando de novo.',
    'grande_demais': 'O sugestoes.json passou do limite. Escreva uma sugestão por alvo, sem outros campos.',
    'json_invalido': 'O sugestoes.json não é JSON válido (ou tem chave repetida, NaN ou Infinity). Escreva de novo.',
    'esquema': 'O sugestoes.json não segue o contrato sugestoes/1 (esquema, pacote_sha256 e a lista sugestoes).',
    'campo_extra': 'O sugestoes.json tem campo fora do contrato sugestoes/1. Deixe só esquema, pacote_sha256 e '
                   'sugestoes, e em cada sugestão só layer_id, funcao e alternativa.',
    'numero': 'O sugestoes.json tem número fora dos ids (geometria, escala ou outro). Deixe só os campos do contrato.',
    'sem_pacote': 'O job não tem pacote para o modelo. Rode "desdobra sugestao pacote" com o teto e leia o pacote.',
    'pacote_velho': 'O pacote mudou depois da leitura. Rode "desdobra sugestao pacote" com o teto, leia o pacote de '
                    'novo e escreva o sugestoes.json com o pacote_sha256 que o comando devolve.',
}


def registrar(subparsers):
    p = subparsers.add_parser('sugestao', help='Fronteira com o Claude: pacotes para a sugestão de função')
    sub = p.add_subparsers(dest='acao_sugestao', metavar='ACAO', required=True)
    pc = sub.add_parser('pacote', help='Refaz o pacote do modelo e o das specs no modo de dados de agora')
    pc.add_argument('--job', required=True, help='Pasta do job')
    pc.set_defaults(executar=_pacote, nome_comando=COMANDO_PACOTE)
    im = sub.add_parser('importar', help='Confere o sugestoes.json do Claude e grava as sugestões validadas')
    im.add_argument('--job', required=True, help='Pasta do job')
    im.set_defaults(executar=_importar, nome_comando=COMANDO_IMPORTAR)


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
    # M7c, S3: o sha256 do pacote gravado, que o Claude cita no sugestoes.json (pacote velho e recusado na importacao)
    ids = {}
    arq = pasta / pacote.ARQUIVO_PACOTE
    if arq.is_file() and not arq.is_symlink():
        ids['pacote_sha256'] = hashlib.sha256(arq.read_bytes()).hexdigest()
    return Resultado(comando=COMANDO_PACOTE, situacao='ok', pasta_job=pasta, contagens=contagens, ids=ids,
                     numeros={'tempo_s': round(time.monotonic() - inicio, 3)},  # numero-neutro: milissegundos
                     linhas_humanas=['Pacotes refeitos: %d camadas, %d miniaturas.' % (r['camadas'],
                                                                                       r['miniaturas'])])


def _importar(args):
    from desdobra.job import nucleo
    from desdobra.sugestao import importar
    pasta = Path(args.job).resolve()
    if not (pasta / nucleo.ARQUIVO_ESTADO).is_file():
        return Resultado(comando=COMANDO_IMPORTAR, codigo=int(Codigo.USO), situacao='erro',
                         o_que_fazer='Passe a pasta de um job do desdobra.', linhas_humanas=['A pasta não é um job.'])
    inicio = time.monotonic()
    r = importar.importar(pasta, teto=getattr(args, 'teto_modo_dados', None))
    tempo = {'tempo_s': round(time.monotonic() - inicio, 3)}  # numero-neutro: milissegundos
    contagens = {'aceitas': r['aceitas'], 'recusadas': sum(r['recusadas'].values())}
    contagens.update({'recusa_%s' % c: n for c, n in sorted(r['recusadas'].items())})
    if r['recusa'] is not None:
        contagens['recusa_%s' % r['recusa']] = 1
        return Resultado(comando=COMANDO_IMPORTAR, codigo=int(Codigo.RECUSADO), situacao='recusado', pasta_job=pasta,
                         contagens=contagens, numeros=tempo, o_que_fazer=O_QUE_FAZER_IMPORTAR[r['recusa']],
                         linhas_humanas=['Sugestões recusadas (%s).' % r['recusa']])
    if not r['aceitas']:
        return Resultado(comando=COMANDO_IMPORTAR, codigo=int(Codigo.RECUSADO), situacao='recusado', pasta_job=pasta,
                         contagens=contagens, numeros=tempo,
                         o_que_fazer='Nenhuma sugestão passou. Veja os códigos de recusa nas contagens, escreva o '
                                     'sugestoes.json de novo e rode este comando.',
                         linhas_humanas=['Nenhuma sugestão passou.'])
    return Resultado(comando=COMANDO_IMPORTAR, situacao='ok', pasta_job=pasta, contagens=contagens, numeros=tempo,
                     o_que_fazer='As sugestões conferidas aparecem na tela, ao lado de cada função, e só viram valor '
                                 'com o clique do DA.',
                     linhas_humanas=['Sugestões conferidas: %d aceitas, %d recusadas.' % (contagens['aceitas'],
                                                                                        contagens['recusadas'])])
