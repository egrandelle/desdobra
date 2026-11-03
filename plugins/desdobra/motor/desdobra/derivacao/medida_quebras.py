# -*- coding: utf-8 -*-
"""Medida das linhas juntadas das quebras aprovadas por familia (revisao 3 do M5).

O mesmo caminho da conferencia de fontes (fontes.conferencia e fontes.medicao): a pagina de medida com uma linha por
quebra que fica, cada trecho com a face do job servida pelo motor (o processo principal so copia os bytes que o filho
leu; nunca abre a fonte), medida no Chromium fixado. Para cada texto e cada conjunto de quebras aprovado, a pagina leva
o texto da mestre e o texto juntado; a medida e a linha mais larga dos dois, no espaco de texto, sem o espacamento do
ultimo caractere (como o Photoshop).

Devolve {chave: {'largura_texto', 'largura_texto_mestre', 'linhas'}} ou, quando nao mede, {chave: {'erro': motivo}}.
"""
from pathlib import Path

from desdobra import arquivos, contratos
from desdobra.briefing import modelo as mb
from desdobra.chromium import navegador, servidor
from desdobra.derivacao import quebras as mq
from desdobra.fontes import casamento, conferencia, medicao

PERFIL = 'medida-quebras'


def _faces(pasta, estado):
    leituras, por_sha = [], {}
    for rel, reg in sorted(estado['entradas'].items()):
        if not rel.startswith(conferencia.PASTA_ENTRADA):
            continue
        arq = Path(pasta) / 'fontes' / 'bruto' / reg['sha256'] / 'leitura.json'
        if arq.is_file():
            leitura = contratos.ler(arq, 'leitura-fonte/1')
            if leitura.get('situacao') == 'lida':
                leituras.append((reg['sha256'], leitura))
                por_sha[reg['sha256']] = rel
    return casamento.montar_faces(leituras), por_sha


def medir(pasta, laudo, briefing, estado):
    pedidos = mq.pedidos(briefing)
    if not pedidos:
        return {}
    camadas = mb.camadas_do_laudo(laudo)
    saida = {}
    faces, por_sha = _faces(pasta, estado)
    servidos = {}
    for f in faces:
        rel = por_sha.get(f['sha256'])
        dados = (Path(pasta) / rel).read_bytes() if rel else None
        if dados is None or arquivos.sha256_bytes(dados) != f['sha256']:
            continue
        servir = conferencia.bytes_para_servir(dados, f)
        if servir is not None:
            servidos[f['id']] = (servir, servidor.MIME_POR_FORMATO[f['formato']])
    textos, ordem = [], []
    for lid, manter in pedidos:
        c = camadas.get(lid)
        if c is None or c.get('tipo') != 'texto':
            saida[mq.chave(lid, manter)] = {'erro': 'camada_sem_texto'}
            continue
        textos.extend([c, mq.com_juntadas(c, manter)])
        ordem.append((lid, manter))
    if not ordem:
        return saida
    pares = {}
    for c in textos:
        for r in c['texto'].get('runs') or []:
            ps = r.get('fonte_ps')
            if ps and ps not in pares:
                pares[ps] = casamento.casar(ps, faces)[0]
    prefixo = 'dsd-%s' % estado['job_id'][:8]  # numero-neutro: prefixo curto do job no nome da familia
    pagina, plano = medicao.montar(textos, pares, faces, prefixo)
    larguras, motivo = {}, None
    if not servidos:
        motivo = 'sem_face_servivel'
    else:
        perfil = navegador.perfil_curto() / PERFIL
        try:
            with servidor.ServidorFontes(pagina, servidos) as srv:
                resposta = navegador.conferir(srv.url_entrada, perfil, [medicao.familia_css(prefixo, i) for i in servidos],
                                              [])
            larguras = resposta.get('larguras') or {}
        except navegador.ErroNavegador:
            motivo = 'chromium_nao_mediu'
        finally:
            navegador.apagar_perfil(perfil)
    for k, (lid, manter) in enumerate(ordem):
        ch = mq.chave(lid, manter)
        if motivo:
            saida[ch] = {'erro': motivo}
            continue
        mestre, juntado = plano['camadas'][2 * k], plano['camadas'][2 * k + 1]  # numero-neutro: duas camadas por pedido
        if any(pares.get(r.get('fonte_ps')) is None for r in camadas[lid]['texto'].get('runs') or [] if r.get('fonte_ps')):
            saida[ch] = {'erro': 'face_ausente'}
            continue
        _cm, sm = medicao.ler_larguras(mestre, larguras)
        _cj, sj = medicao.ler_larguras(juntado, larguras)
        if not sm or not sj:
            saida[ch] = {'erro': 'sem_medida_do_chromium'}
            continue
        saida[ch] = {'largura_texto_mestre': round(sm, 4), 'largura_texto': round(sj, 4),
                     'linhas': len(juntado['linhas'])}
    return saida
