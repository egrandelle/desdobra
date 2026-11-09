# -*- coding: utf-8 -*-
"""Indice encadeado do historico do briefing (M7b, A4): briefing/historico/indice.json, esquema historico-indice/1.

Cada gravacao do briefing confirmado (briefing.modelo.gravar_com_historico) deixa uma entrada: o numero em sequencia,
o sha do briefing antes e depois, o carimbo, a origem e o meio do cabecalho, os formatos afetados (None quando quem
grava nao os calculou; o salvar seletivo do A6 os passa) e o sha256 da entrada anterior (a cadeia). A versao anterior
continua em briefing/historico/<sha>.json, como antes do indice.

A leitura confere a sequencia, a cadeia, o elo entre o sha novo de uma entrada e o anterior da seguinte e o briefing
gravado contra a ultima entrada; o que nao fecha vira aviso na tela (tela.estado._avisos_do_job). A gravacao nunca
para por causa de um indice mexido: ela encadeia na ultima entrada que ha (o indice ilegivel fica guardado ao lado e
o novo comeca com reiniciado_de), e o aviso continua.

O que a cadeia nao resolve (risco 177, revisao do M7a): ela mostra a ordem e pega a adulteracao ingenua (entrada
apagada, trocada ou fora de ordem). Ela nao prova quem gravou: o indice nao tem segredo, e quem reescreve o indice
inteiro com a cadeia refeita passa. Job gravado antes do indice nao tem o que conferir ate a proxima gravacao.
"""
import hashlib
import json
from pathlib import Path

from desdobra import arquivos, contratos

ESQUEMA = 'historico-indice/1'
ARQUIVO = Path('briefing') / 'historico' / 'indice.json'
PREFIXO_INVALIDO = 'indice-invalido-'

AVISO_HISTORICO_MEXIDO = ('O histórico de versões do briefing foi mexido fora do desdobra: falta, sobra ou foi '
                          'trocada uma versão. As versões novas continuam sendo guardadas, mas confira quem mexeu na '
                          'pasta do job.')
AVISO_BRIEFING_FORA = ('O briefing gravado no job não é a última versão do histórico. Ele pode ter sido trocado fora '
                       'da tela. Confira as famílias e salve o briefing outra vez pela tela.')
AVISO_INDICE_INVALIDO = ('O histórico de versões do briefing não pôde ser lido. A próxima vez que o briefing for salvo, '
                         'o desdobra guarda o arquivo antigo e começa um histórico novo.')
AVISOS = {'sequencia_quebrada': AVISO_HISTORICO_MEXIDO, 'cadeia_quebrada': AVISO_HISTORICO_MEXIDO,
          'versoes_desencadeadas': AVISO_HISTORICO_MEXIDO, 'indice_reiniciado': AVISO_HISTORICO_MEXIDO,
          'briefing_fora_do_indice': AVISO_BRIEFING_FORA, 'indice_invalido': AVISO_INDICE_INVALIDO}


def sha_da_entrada(entrada):
    """sha256 (hex) da entrada em JSON canonico (chaves em ordem, sem espaco): o elo da entrada seguinte."""
    texto = json.dumps(entrada, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()


def ler(pasta):
    """O indice lido e conferido pelo contrato; None sem indice. contratos.ErroContrato quando ilegivel."""
    caminho = Path(pasta) / ARQUIVO
    if not caminho.is_file():
        return None
    return contratos.ler(caminho, ESQUEMA)


def registrar(pasta, sha_anterior, sha_novo, cabecalho, afetados=None, quando=None):
    """Acrescenta a entrada da gravacao ao indice e devolve a entrada. Chamado por gravar_com_historico depois de
    gravar o briefing (o sha novo e o do arquivo gravado). O indice ilegivel fica guardado como
    indice-invalido-<sha>.json, e o novo comeca com reiniciado_de."""
    from desdobra.briefing import modelo as mb
    caminho = Path(pasta) / ARQUIVO
    try:
        dados = ler(pasta)
    except contratos.ErroContrato:
        guardado = caminho.with_name('%s%s.json' % (PREFIXO_INVALIDO, arquivos.sha256_arquivo(caminho)))
        arquivos.gravar_bytes_atomico(guardado, caminho.read_bytes())
        dados = {'esquema': ESQUEMA, 'reiniciado_de': guardado.name, 'entradas': []}
    if dados is None:
        dados = {'esquema': ESQUEMA, 'entradas': []}
    entradas = dados['entradas']
    ultima = entradas[-1] if entradas else None
    entrada = {'seq': ultima['seq'] + 1 if ultima else 1, 'quando': quando or mb.agora(),
               'origem': (cabecalho or {}).get('origem'), 'meio': (cabecalho or {}).get('meio'),
               'sha_anterior': sha_anterior, 'sha_novo': sha_novo,
               'formatos_afetados': None if afetados is None else sorted(afetados),
               'sha_entrada_anterior': sha_da_entrada(ultima) if ultima else None}
    entradas.append(entrada)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    contratos.gravar(caminho, dados, ESQUEMA)
    return entrada


def conferir(pasta):
    """Lista de problemas do indice ({'codigo', 'seq'}; [] quando fecha ou nao ha indice): indice_invalido,
    indice_reiniciado, sequencia_quebrada, cadeia_quebrada, versoes_desencadeadas e briefing_fora_do_indice."""
    from desdobra.briefing import modelo as mb
    try:
        dados = ler(pasta)
    except contratos.ErroContrato:
        return [{'codigo': 'indice_invalido', 'seq': None}]
    if dados is None:
        return []
    saida = []
    if dados.get('reiniciado_de'):
        saida.append({'codigo': 'indice_reiniciado', 'seq': None})
    anterior = None
    for e in dados['entradas']:
        if e['seq'] != (anterior['seq'] + 1 if anterior else 1):
            saida.append({'codigo': 'sequencia_quebrada', 'seq': e['seq']})
        if e['sha_entrada_anterior'] != (sha_da_entrada(anterior) if anterior else None):
            saida.append({'codigo': 'cadeia_quebrada', 'seq': e['seq']})
        if anterior is not None and e['sha_anterior'] != anterior['sha_novo']:
            saida.append({'codigo': 'versoes_desencadeadas', 'seq': e['seq']})
        anterior = e
    atual = Path(pasta) / mb.ARQUIVO
    if anterior is not None and atual.is_file() and arquivos.sha256_arquivo(atual) != anterior['sha_novo']:
        saida.append({'codigo': 'briefing_fora_do_indice', 'seq': anterior['seq']})
    return saida


def avisos(pasta):
    """Os avisos da tela (frases, sem repetir) para os problemas do indice."""
    saida = []
    for p in conferir(pasta):
        t = AVISOS[p['codigo']]
        if t not in saida:
            saida.append(t)
    return saida
