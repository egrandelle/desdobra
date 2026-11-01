# -*- coding: utf-8 -*-
"""Lado do processo principal da leitura da folha de spec: chama o filho isolado e le o que ele gravou.

O processo principal nunca abre a folha com o PDFium, o html.parser ou o csv. Ele so reconhece o formato pela
extensao e pela assinatura (%PDF-), calcula o orcamento, chama o filho (desdobra.specs.filho) pela interface de
plataforma, com o mesmo isolador do leitor de PSD, e le e valida leitura.json (leitura-folha/1). Queda, memoria,
tempo e bug do filho viram recusa tipada; nada disso derruba o processo principal.

A leitura fica em specs/bruto/<sha256>/ e e reaproveitada enquanto o sha256 da folha e a versao do motor forem os
mesmos (a confirmacao do DA refaz o rascunho sem ler a folha de novo).
"""
import shutil
from pathlib import Path

from desdobra import __version__, contratos, limites, plataforma
from desdobra.arquivos import sha256_arquivo

MODULO_FILHO = 'desdobra.specs.filho'
ESQUEMA = 'leitura-folha/1'
EXTENSOES = {'.pdf': 'pdf', '.html': 'html', '.htm': 'html', '.csv': 'csv', '.txt': 'texto', '.eml': 'texto'}
ASSINATURA_PDF = b'%PDF-'


def formato_da_folha(caminho):
    """'pdf', 'html', 'csv', 'texto' ou None (formato fora da v1: planilha .xlsx, imagem solta, Word)."""
    caminho = Path(caminho)
    formato = EXTENSOES.get(caminho.suffix.lower())
    try:
        with open(caminho, 'rb') as f:
            inicio = f.read(len(ASSINATURA_PDF))
    except OSError:
        return None
    if inicio == ASSINATURA_PDF:
        return 'pdf'
    if formato == 'pdf':
        return None
    return formato


def orcamento_bytes(n_bytes):
    """(isolador.base_python_bytes + specs.fator_abertura_max x bytes) x isolador.margem_orcamento."""
    base = limites.valor('isolador.base_python_bytes')
    fator = limites.valor('specs.fator_abertura_max')
    margem = limites.valor('isolador.margem_orcamento')
    return int((base + fator * int(n_bytes)) * margem)


def _recusa(tipo, motivo):
    return {'situacao': 'recusada', 'leitura': None, 'recusa': {'tipo': tipo, 'motivo': motivo}}


def _reaproveitavel(arq, sha, formato):
    if not arq.is_file():
        return None
    try:
        leitura = contratos.ler(arq, ESQUEMA)
    except contratos.ErroContrato:
        return None
    if leitura['origem']['sha256'] != sha or leitura['leitor']['motor'] != __version__ or leitura['situacao'] != 'lida':
        return None
    # a leitura so vale para o mesmo formato e a mesma escala de recorte (os mesmos bytes como .txt e como .csv
    # sao duas leituras)
    if leitura['formato'] != formato or leitura.get('escala_recorte') != float(limites.valor('specs.recorte_escala')):
        return None
    for p in leitura['paginas']:
        if p['recorte'] and not (arq.parent / p['recorte']).is_file():
            return None
    return leitura


def ler(caminho, pasta_saida, pasta_trabalho, *, plat=None, reaproveitar=True):
    """Le uma folha no filho isolado. Devolve {'situacao': 'lida'|'recusada', 'leitura', 'recusa'}."""
    caminho, pasta_saida, pasta_trabalho = Path(caminho).resolve(), Path(pasta_saida).resolve(), Path(pasta_trabalho).resolve()
    formato = formato_da_folha(caminho)
    if formato is None:
        return _recusa('formato', 'A folha não é PDF, HTML salvo, CSV nem texto.')
    sha = sha256_arquivo(caminho)
    if reaproveitar:
        anterior = _reaproveitavel(pasta_saida / 'leitura.json', sha, formato)
        if anterior is not None:
            return {'situacao': 'lida', 'leitura': anterior, 'recusa': None}
    plat = plat or plataforma.obter()
    for p in (pasta_saida, pasta_trabalho):
        if p.exists():
            shutil.rmtree(p)
        p.mkdir(parents=True)
    orc = orcamento_bytes(caminho.stat().st_size)
    cmd = [str(plat.interpretador()), '-I', '-B', '-m', MODULO_FILHO, str(caminho), str(pasta_saida),
           '--formato', formato, '--orcamento-bytes', str(orc),
           '--escala-recorte', str(limites.valor('specs.recorte_escala'))]
    r = plat.executar_isolado(cmd, orc, float(limites.valor('specs.tempo_max_s')), pasta_trabalho)
    shutil.rmtree(pasta_trabalho, ignore_errors=True)
    arq = pasta_saida / 'leitura.json'
    if r.situacao == 'recusado':
        return _recusa('plataforma', r.motivo or 'isolador indisponível')
    if arq.is_file():
        try:
            leitura = contratos.ler(arq, ESQUEMA)
        except contratos.ErroContrato:
            leitura = None
        if leitura is not None:
            if leitura['situacao'] == 'lida' and r.situacao == 'ok' and r.codigo == 0:
                return {'situacao': 'lida', 'leitura': leitura, 'recusa': None}
            if leitura['situacao'] == 'recusada':
                return {'situacao': 'recusada', 'leitura': leitura,
                        'recusa': {'tipo': leitura['recusa']['tipo'], 'motivo': leitura['recusa']['motivo']}}
    if r.situacao == 'memoria':  # o filho morto pelo teto nao chega a gravar a recusa
        return _recusa('memoria', 'A leitura da folha passou do orçamento de memória.')
    if r.situacao == 'tempo':
        return _recusa('tempo', 'A leitura da folha passou do tempo máximo.')
    if r.situacao == 'queda':
        return _recusa('queda', 'O processo de leitura da folha caiu.')
    return _recusa('bug', 'O processo de leitura da folha terminou com erro interno.')
