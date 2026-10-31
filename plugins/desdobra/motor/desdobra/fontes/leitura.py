# -*- coding: utf-8 -*-
"""Lado do processo principal da leitura de fonte: chama o filho isolado e le o que ele gravou.

O processo principal nunca abre o arquivo de fonte com o fontTools. Ele so calcula o orcamento, chama o filho
(desdobra.fontes.filho) pela interface de plataforma, com o mesmo isolador do leitor de PSD, e le e valida
leitura.json (leitura-fonte/1). Queda, memoria, tempo e bug do filho viram recusa tipada; nada disso derruba o
processo principal.
"""
import shutil
from pathlib import Path

from desdobra import contratos, limites, plataforma

MODULO_FILHO = 'desdobra.fontes.filho'
ESQUEMA = 'leitura-fonte/1'


def orcamento_bytes(n_bytes):
    """(isolador.base_python_bytes + fontes.fator_abertura_max x bytes) x isolador.margem_orcamento."""
    base = limites.valor('isolador.base_python_bytes')
    fator = limites.valor('fontes.fator_abertura_max')
    margem = limites.valor('isolador.margem_orcamento')
    return int((base + fator * int(n_bytes)) * margem)


def _limpar(pasta):
    pasta = Path(pasta)
    if pasta.exists():
        shutil.rmtree(pasta)
    pasta.mkdir(parents=True)


def _recusa(tipo, motivo, pico=None):
    return {'situacao': 'recusada', 'leitura': None, 'pico_bytes': pico,
            'recusa': {'tipo': tipo, 'motivo': motivo}}


def ler(caminho, pasta_saida, pasta_trabalho, *, plat=None):
    """Le um arquivo de fonte no filho isolado. Devolve {'situacao': 'lida'|'recusada', 'leitura', 'recusa',
    'pico_bytes'}; 'leitura' e o leitura-fonte/1 validado (tambem na recusa tipada que o filho gravou)."""
    plat = plat or plataforma.obter()
    caminho, pasta_saida, pasta_trabalho = Path(caminho).resolve(), Path(pasta_saida).resolve(), Path(pasta_trabalho).resolve()
    _limpar(pasta_saida)
    _limpar(pasta_trabalho)
    orc = orcamento_bytes(caminho.stat().st_size)
    cmd = [str(plat.interpretador()), '-I', '-B', '-m', MODULO_FILHO, str(caminho), str(pasta_saida),
           '--orcamento-bytes', str(orc)]
    r = plat.executar_isolado(cmd, orc, float(limites.valor('fontes.tempo_max_s')), pasta_trabalho)
    shutil.rmtree(pasta_trabalho, ignore_errors=True)
    arq = pasta_saida / 'leitura.json'
    if r.situacao == 'recusado':
        return _recusa('plataforma', r.motivo or 'isolador indisponível')
    if arq.is_file():
        try:
            leitura = contratos.ler(arq, ESQUEMA)
        except contratos.ErroContrato:
            leitura = None
        if leitura is not None and (r.situacao == 'ok' or leitura['situacao'] == 'recusada'):
            if leitura['situacao'] == 'lida' and r.codigo == 0 and r.situacao == 'ok':
                return {'situacao': 'lida', 'leitura': leitura, 'recusa': None, 'pico_bytes': r.pico_bytes}
            if leitura['situacao'] == 'recusada':
                rec = leitura['recusa']
                return {'situacao': 'recusada', 'leitura': leitura, 'pico_bytes': r.pico_bytes,
                        'recusa': {'tipo': rec['tipo'], 'motivo': rec['motivo']}}
    if r.situacao == 'memoria':
        return _recusa('memoria', 'A leitura da fonte passou do orçamento de memória.', r.pico_bytes)
    if r.situacao == 'tempo':
        return _recusa('tempo', 'A leitura da fonte passou do tempo máximo.', r.pico_bytes)
    if r.situacao == 'queda':
        return _recusa('queda', 'O processo de leitura da fonte caiu.', r.pico_bytes)
    return _recusa('bug', 'O processo de leitura da fonte terminou com erro interno.', r.pico_bytes)
