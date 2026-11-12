# -*- coding: utf-8 -*-
"""Pacote das specs para o modelo (sugestoes/pacote-specs.json, contrato pacote-specs/1) e a volta das propostas
(sugestoes/mapeamento-specs.json, contrato mapeamento-specs/1).

arquitetura-v1.md, 4.8, 4.9 e 6: o Claude pode dizer que trecho da folha vai para que campo; o motor extrai o
numero do trecho; o DA confirma. Por isso:
  - o pacote leva os trechos da folha (texto, pagina, rotulo, secao) e os alvos possiveis (ids de formato,
    circuito e veiculador, com a chave do formato), so nos modos a e b e depois do detector de segredos. No modo c
    leva so contagens, e o Claude nao propoe nada;
  - a proposta volta so com ids e o nome do campo (o esquema nao tem lugar para numero). O pedaco literal
    opcional (recorte_texto) tem de existir no trecho, e o motor extrai dele; a proposta nunca preenche valor e
    nunca confirma.
"""
from pathlib import Path

from desdobra import contratos
from desdobra.sugestao import segredos

CONTRATO = 'pacote-specs/1'
ARQUIVO_PACOTE = Path('sugestoes') / 'pacote-specs.json'


def montar_pacote(rascunho, modo, *, job_id=None, detector=None):
    """Devolve (pacote, achados). O pacote vale contra pacote-specs/1."""
    from desdobra.specs import modelo
    detector = detector or segredos.detector_padrao()
    abre = modo in ('a', 'b')
    mapeados = set()
    for _r, _c, v in modelo.todos_os_valores(rascunho):
        fon = v.get('fonte') or {}
        if fon.get('trecho') and v.get('origem') == 'extraido_do_trecho':
            mapeados.add((fon['folha'], fon['trecho']))
            if fon.get('rotulo_trecho'):
                mapeados.add((fon['folha'], fon['rotulo_trecho']))
    achados, trechos, secoes_vistas = [], [], {}
    n_trechos = 0
    for f in rascunho['folhas']:
        for t in f['trechos']:
            n_trechos += 1
            # texto e rotulo passam pelo detector: com achado, o trecho sai inteiro
            achado = detector.achado_em('trecho_spec', None, {'textos': [t['texto'], t.get('rotulo') or '']})
            if achado is not None:
                achados.append(achado)
                continue
            # a secao (o titulo do HTML acima do trecho) tambem: com achado, so a secao sai, contada uma vez
            secao = t.get('secao')
            if secao and secao not in secoes_vistas:
                secoes_vistas[secao] = detector.achado_em('trecho_spec', None, {'textos': [secao]})
                if secoes_vistas[secao] is not None:
                    achados.append(secoes_vistas[secao])
            if secao and secoes_vistas[secao] is not None:
                secao = None
            if abre:
                trechos.append({'folha': f['id'], 'trecho': t['id'], 'pagina': t['pagina'], 'texto': t['texto'],
                                'rotulo': t.get('rotulo'), 'secao': secao,
                                'mapeado': (f['id'], t['id']) in mapeados})
    pacote = {'esquema': CONTRATO, 'modo_dados': modo, 'job_id': job_id, 'exposto': {'textos': abre},
              'campos': sorted(c for c in modelo.CAMPOS),
              'contagens': {'folhas': len(rascunho['folhas']), 'trechos': n_trechos,
                            'trechos_mapeados': len(mapeados), 'formatos': len(rascunho['formatos'])},
              'folhas': [], 'alvos': [], 'trechos': trechos}
    if abre:
        for f in rascunho['folhas']:
            # o id do veiculador vem do nome da pasta: tambem passa pelo detector
            achado = detector.achado_em('trecho_spec', None, {'textos': [f['veiculador']]})
            if achado is not None:
                achados.append(achado)
                continue
            pacote['folhas'].append({'id': f['id'], 'formato': f['formato'], 'n_paginas': f['n_paginas'],
                                     'camada_texto': f['camada_texto'], 'veiculador': f['veiculador']})
        candidatos = ([{'id': x['id'], 'nivel': 'formato', 'chave': x.get('chave'), 'pagina': x['entrada']['pagina'],
                        'folha': x['entrada']['folha']} for x in rascunho['formatos']] +
                      [{'id': x['id'], 'nivel': 'circuito', 'chave': None, 'pagina': None, 'folha': None}
                       for x in rascunho['circuitos']] +
                      [{'id': x['id'], 'nivel': 'veiculador', 'chave': None, 'pagina': None, 'folha': None}
                       for x in rascunho['veiculadores']])
        for alvo in candidatos:
            # os ids e as chaves levam texto da folha (o circuito, o veiculador): alvo com achado fica de fora
            achado = detector.achado_em('trecho_spec', None, {'textos': [alvo['id'], alvo['chave'] or '']})
            if achado is not None:
                achados.append(achado)
                continue
            pacote['alvos'].append(alvo)
    pacote['contagens']['segredos_bloqueados'] = len(achados)
    contratos.validar(pacote, CONTRATO)
    return pacote, achados


def gravar_pacote(pasta_job, rascunho, modo, *, job_id=None, detector=None, comando='spec importar'):
    pacote, achados = montar_pacote(rascunho, modo, job_id=job_id, detector=detector)
    destino = Path(pasta_job) / ARQUIVO_PACOTE
    contratos.gravar(destino, pacote, CONTRATO)
    segredos.gravar_bloqueios(pasta_job, achados, comando=comando)
    return destino, len(achados)


def refazer_pacote(pasta_job, modo, *, job_id=None, detector=None):
    """Refaz sugestoes/pacote-specs.json no modo dado a partir do rascunho gravado (specs/rascunho.json), sem ler as
    folhas de novo (M7c, S2: o ato do modo e o "sugestao pacote" refazem os dois pacotes). Sem rascunho, o pacote das
    specs nao existe: o que sobrou e apagado. Devolve (caminho ou None, numero de achados)."""
    from desdobra.specs import importar
    pasta_job = Path(pasta_job)
    arq = pasta_job / importar.ARQUIVO_RASCUNHO
    if not arq.is_file():
        try:
            (pasta_job / ARQUIVO_PACOTE).unlink()
        except FileNotFoundError:
            pass
        return None, 0
    rascunho = contratos.ler(arq, importar.ESQUEMA)
    return gravar_pacote(pasta_job, rascunho, modo, job_id=job_id, detector=detector, comando='sugestao pacote')
