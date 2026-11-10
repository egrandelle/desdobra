# -*- coding: utf-8 -*-
"""Medida das linhas juntadas das quebras aprovadas por familia (revisao 3 do M5).

O mesmo caminho da conferencia de fontes (fontes.conferencia e fontes.medicao): a pagina de medida com uma linha por
quebra que fica, cada trecho com a face do job servida pelo motor (o processo principal so copia os bytes que o filho
leu; nunca abre a fonte), medida no Chromium fixado. Para cada texto e cada conjunto de quebras aprovado, a pagina leva
o texto da mestre e o texto juntado; a medida e a linha mais larga dos dois, no espaco de texto, sem o espacamento do
ultimo caractere (como o Photoshop). A quebra da familia da tela (M7b, C2) tambem insere quebra nos espacos: o texto
juntado leva as duas. A quebra da familia cujas posicoes nao cabem no texto do KV (a do texto editado pelo DA na
familia, que o render quebra sem medida) fica sem medir.

Medida ao vivo, com cache (M7b, C3): a medida de cada texto com as suas quebras fica guardada no processo, pela
chave da medida (chave_da_medida: a camada do laudo, as quebras que ficam, as inseridas e as faces servidas, que sao
tudo o que a pagina de medida le). A segunda medida igual nao abre o Chromium, e so o texto cuja quebra mudou vai a
pagina. A previa da tela (desdobra.tela.edicao) e a derivacao gravada passam por medir, entao usam a mesma medida. A
medida que falhou (Chromium que nao abriu, face ausente, sem largura) nao fica guardada: o proximo pedido tenta de
novo. O cache guarda ate CACHE_MAX medidas; a mais antiga sai primeiro.

Chromium aberto da tela (M7b, C3): com a tela aberta, o processo dela liga um desdobra.chromium.aberto.NavegadorAberto
(usar_aberto), e a medida sem cache vai a ele: o Chromium fica aberto entre as medidas, e cada medida roda num
contexto sem perfil, com as mesmas linhas de medida do caminho frio. Quando o aberto nao mede (fechado, sem amarra,
caiu ou passou do teto), o pedido sai pelo caminho frio, o de sempre: o Chromium fixado abre com um perfil novo,
mede e fecha. Fora da tela (a CLI e a derivacao), nada fica ligado e toda medida e a do caminho frio.

Devolve {chave: {'largura_texto', 'largura_texto_mestre', 'linhas'}} ou, quando nao mede, {chave: {'erro': motivo}}.
"""
import copy
import hashlib
import json
import threading
from collections import OrderedDict
from pathlib import Path

from desdobra import arquivos, contratos
from desdobra.briefing import modelo as mb
from desdobra.chromium import navegador, servidor
from desdobra.derivacao import quebras as mq
from desdobra.fontes import casamento, conferencia, medicao

PERFIL = 'medida-quebras'
CACHE_MAX = 512  # numero-neutro: medidas guardadas no processo (cada uma e um dicionario pequeno)
INTERVALO_SERVIDOR_ABERTO_S = 0.01  # numero-neutro: intervalo de consulta do servidor da pagina, so com o aberto

_cache = OrderedDict()
_trava = threading.Lock()
_aberto = None  # o Chromium aberto da tela (desdobra.chromium.aberto), ligado so pelo processo da tela


def usar_aberto(aberto):
    """Liga o Chromium aberto da tela na medida sem cache, ou desliga com None (o fecho da tela)."""
    global _aberto
    with _trava:
        _aberto = aberto


def limpar_cache():
    """Esquece as medidas guardadas (os testes e a medicao de latencia sem cache)."""
    with _trava:
        _cache.clear()


def chave_da_medida(camada, manter, inseridas, faces):
    """A chave do cache: o sha256 do texto canonico da camada do laudo, das quebras que ficam, das inseridas e das
    faces servidas [(id, sha256)]. Mudar qualquer um muda a chave."""
    dados = {'camada': camada, 'manter': sorted(int(x) for x in manter),
             'inseridas': sorted(int(x) for x in inseridas), 'faces': sorted([str(i), str(s)] for i, s in faces)}
    texto = json.dumps(dados, sort_keys=True, ensure_ascii=False, separators=(',', ':'), default=str)
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()


def _guardada(chave):
    with _trava:
        medida = _cache.get(chave)
        if medida is None:
            return None
        _cache.move_to_end(chave)
        return copy.deepcopy(medida)


def _guardar(chave, medida):
    with _trava:
        _cache[chave] = copy.deepcopy(medida)
        _cache.move_to_end(chave)
        while len(_cache) > CACHE_MAX:
            _cache.popitem(last=False)


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


def _conferir(url_entrada, familias, servidos):
    """A pagina de medida no Chromium aberto da tela, quando ligado; senao, ou quando ele nao mede, no caminho frio
    (navegador.conferir com um perfil novo, apagado no fim)."""
    aberto = _aberto
    if aberto is not None:
        try:
            return aberto.conferir(url_entrada, familias, [], servidos=servidos)
        except navegador.ErroNavegador:
            pass  # este pedido sai pelo caminho frio; o aberto abre de novo no proximo (desdobra.chromium.aberto)
    perfil = navegador.perfil_curto() / PERFIL
    try:
        return navegador.conferir(url_entrada, perfil, familias, [])
    finally:
        navegador.apagar_perfil(perfil)


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
    servidas = [(f['id'], f['sha256']) for f in faces if f['id'] in servidos]
    textos, ordem = [], []
    for lid, manter, inseridas in pedidos:
        c = camadas.get(lid)
        if c is None or c.get('tipo') != 'texto':
            saida[mq.chave(lid, manter, inseridas)] = {'erro': 'camada_sem_texto'}
            continue
        if mq.conferir_da_familia(c, manter, inseridas) is not None:
            continue
        no_cache = chave_da_medida(c, manter, inseridas, servidas)
        guardada = _guardada(no_cache)
        if guardada is not None:
            # a mesma medida de antes, sem abrir o Chromium (M7b, C3)
            saida[mq.chave(lid, manter, inseridas)] = guardada
            continue
        textos.extend([c, mq.com_juntadas(c, manter, inseridas)])
        ordem.append((lid, manter, inseridas, no_cache))
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
    larguras, tintas, motivo = {}, {}, None
    if not servidos:
        motivo = 'sem_face_servivel'
    else:
        # com o aberto ligado, o servidor da pagina para sem a espera de meio segundo do serve_forever, que era quase
        # toda a remedicao no aberto; o caminho frio fica com o servidor de antes
        kw = {'intervalo_s': INTERVALO_SERVIDOR_ABERTO_S} if _aberto is not None else {}
        try:
            with servidor.ServidorFontes(pagina, servidos, **kw) as srv:
                resposta = _conferir(srv.url_entrada, [medicao.familia_css(prefixo, i) for i in servidos],
                                     [d for d, _mime in servidos.values()])
            larguras = resposta.get('larguras') or {}
            tintas = resposta.get('tintas') or {}
        except navegador.ErroNavegador:
            motivo = 'chromium_nao_mediu'
    for k, (lid, manter, inseridas, no_cache) in enumerate(ordem):
        ch = mq.chave(lid, manter, inseridas)
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
        just = (camadas[lid].get('texto') or {}).get('justificacao')
        tm = medicao.tinta_do_bloco(mestre, larguras, tintas, just)
        tj = medicao.tinta_do_bloco(juntado, larguras, tintas, just)
        if tm is not None and tj is not None:
            # a tinta de cada linha, para a caixa seguir a do render (derivacao.quebras.caixa_medida)
            saida[ch]['tinta_mestre'] = {k: round(v, 4) for k, v in tm.items()}
            saida[ch]['tinta'] = {k: round(v, 4) for k, v in tj.items()}
        _guardar(no_cache, saida[ch])
    return saida
