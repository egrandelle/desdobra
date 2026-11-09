# -*- coding: utf-8 -*-
"""Render de um formato (M4: a origem), do contrato ao render/<formato>/master.png e ao render.json.

Passos (arquitetura-v1.md, 4.11 e 9.5):
  1. monta o contrato (desdobra.render.contrato) e grava render/<formato>/contrato.json; com bloqueio, para;
  2. pilhas: cada pilha do contrato tem um asset render/assets/<sha256>.png, indexado em render/pilhas.json pelo
     hash da pilha (sha256 do KV e camadas). Se o indice ja tem o asset (cache por hash, ideia do renderizar.py do
     predecessor), o PSD nao e aberto de novo; senao, o filho das pilhas (desdobra.render.filho_pilhas) compoe as que faltam;
  3. texto: cada camada de texto vira uma pagina por cor (desdobra.render.texto). O servidor local serve as paginas e
     as faces do job pela rota propria, com Cache-Control: no-store; o Chromium fixado (escala 1, --disable-lcd-text,
     --disable-gpu, sRGB forcado, perfil temporario curto) carrega cada pagina, o CDP confere em cada trecho que a
     face usada e a do arquivo do job, e o PDF de cada pagina volta em bytes, so na memoria;
  4. o perfil do Chromium e varrido (copia de fonte, assinatura de PDF e o controle positivo do cache) e apagado;
  5. o filho do render (desdobra.render.filho) recebe os PDFs pela entrada padrao, rasteriza com o PDFium e compoe
     com a gama; o master.png vai para render/<formato>/ e o render.json registra versoes, G, tempos, sha256 de cada
     fonte e asset, o resultado do CDP, o teste de cache e a varredura da pasta do job.

O render so parte de uma pessoa (decisoes-v1.md, arquitetura n. 2): quem chama aqui e o comando "desdobra render",
que exige terminal interativo e confirmacao (desdobra.render, disparo), ou o autoteste do doctor, que nao usa job.
"""
import getpass
import json
import os
import platform as _platform
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

from desdobra import __version__, arquivos, contratos, limites, plataforma
from desdobra.chromium import navegador, servidor
from desdobra.fontes import conferencia, medicao
from desdobra.render import contrato as mod_contrato
from desdobra.render import texto as mod_texto
from desdobra.render.filho import CodigoFilho
from desdobra.resultado import Codigo

ESQUEMA_RENDER = 'render/1'
MODULO_FILHO = 'desdobra.render.filho'
MODULO_PILHAS = 'desdobra.render.filho_pilhas'
ARQUIVO_PILHAS = Path('render') / 'pilhas.json'
PASTA_ASSETS = Path('render') / 'assets'
PASTA_TRABALHO = Path('render') / '.trabalho'
PASTA_ENTRADA = 'entrada/'
CODIGOS_FILHO = {CodigoFilho.ARGUMENTOS: 'argumentos', CodigoFilho.RECUSADO: 'recusado', CodigoFilho.MEMORIA: 'memoria',
                 CodigoFilho.AUDITORIA: 'auditoria', CodigoFilho.BUG: 'bug'}


class ErroRender(Exception):
    """O render parou. codigo: um dos de desdobra.resultado.Codigo; motivo: codigo curto; texto fixo do motor."""

    def __init__(self, mensagem, motivo, codigo=Codigo.RECUSADO, o_que_fazer=None, medidas=None):
        super().__init__(mensagem)
        self.motivo, self.codigo, self.o_que_fazer, self.medidas = motivo, codigo, o_que_fazer, medidas or {}


def agora():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def quem():
    try:
        usuario = getpass.getuser()
    except Exception:  # noqa: BLE001
        usuario = None
    return {'usuario': usuario, 'maquina': _platform.node() or None}


def _versao(pacote):
    try:
        from importlib.metadata import version
        return version(pacote)
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------------ filhos
def orcamento_composicao(largura, altura, bytes_pdfs, px_linkados=0):
    """Orcamento do filho do render: o canvas, a faixa do PDFium, os PDFs e os linkados decodificados."""
    base = limites.valor('isolador.base_python_bytes')
    por_px = limites.valor('render.bytes_por_px_canvas')
    banda = limites.valor('render.bytes_banda_pdfium')
    margem = limites.valor('isolador.margem_orcamento')
    return int((base + por_px * (int(largura) * int(altura) + int(px_linkados)) + banda + int(bytes_pdfs)) * margem)


def _rodar(plat, cmd, orc, tempo, trabalho, entrada=b''):
    trabalho.mkdir(parents=True, exist_ok=True)
    return plat.executar_isolado(cmd, orc, tempo, trabalho, entrada=entrada)


def _falha_filho(r, etapa):
    if r.situacao == 'recusado':
        return ErroRender('O isolador não executou o processo do render.', 'isolador_indisponivel',
                          codigo=Codigo.NAO_DISPONIVEL, o_que_fazer='Rode "desdobra doctor".')
    if r.situacao in ('memoria', 'tempo'):
        return ErroRender('O processo do render (%s) passou do teto de %s.' % (etapa, 'memória' if r.situacao == 'memoria'
                                                                              else 'tempo'),
                          '%s_%s' % (etapa, r.situacao), codigo=Codigo.ORCAMENTO,
                          o_que_fazer='O teto do render ainda é um valor a calibrar. Feche outros programas e rode de '
                                      'novo; se repetir, mande o render.json do job para a Trezion.',
                          medidas={'pico_bytes': r.pico_bytes})
    if r.codigo == CodigoFilho.AUDITORIA:
        return ErroRender('O processo do render tentou uma ação que o desdobra não permite e foi parado.',
                          '%s_auditoria' % etapa, codigo=Codigo.AUDITORIA)
    return ErroRender('O processo do render (%s) terminou com erro (%s).' % (etapa, CODIGOS_FILHO.get(r.codigo, r.situacao)),
                      '%s_%s' % (etapa, CODIGOS_FILHO.get(r.codigo, r.situacao)), codigo=Codigo.ERRO_INTERNO)


def resolver_pilhas(pasta, contrato, plat):
    """{id da entrada: {'arquivo', 'caixa', 'sha256'}} das pilhas, com o cache por hash. Devolve (mapa, n_do_cache)."""
    pilhas = [e for e in contrato['entradas'] if e['tipo'] == 'pilha']
    indice_arq = pasta / ARQUIVO_PILHAS
    indice = arquivos.ler_json(indice_arq) if indice_arq.is_file() else {'pilhas': {}}
    versao_psd = _versao('psd-tools')

    def valido(chave):
        it = indice['pilhas'].get(chave)
        if not it or it.get('psd_tools') != versao_psd or it.get('motor') != __version__:
            return False
        if it['sha256'] is None:
            return True
        arq = pasta / PASTA_ASSETS / ('%s.png' % it['sha256'])
        # o asset no disco tem de ser o que o indice diz (um asset mexido ou trocado e refeito)
        return arq.is_file() and arquivos.sha256_arquivo(arq) == it['sha256']

    faltam = [e for e in pilhas if not valido(e['chave'])]
    do_cache = len(pilhas) - len(faltam)
    if faltam:
        kv = next((pasta / rel for rel in sorted(contratos.ler(pasta / 'estado.json', 'estado/1')['entradas'])
                   if rel.startswith('entrada/kv')), None)
        if kv is None or not kv.is_file():
            raise ErroRender('O KV do job não está mais na pasta do job, e as pilhas não estão no cache.',
                             'kv_ausente', o_que_fazer='Restaure entrada/kv do job para o render compor as pilhas.')
        saida = pasta / PASTA_TRABALHO / 'pilhas'
        shutil.rmtree(saida, ignore_errors=True)
        saida.mkdir(parents=True)
        try:
            _compor_pilhas(pasta, contrato, plat, kv, saida, faltam, indice, indice_arq, versao_psd)
        finally:
            shutil.rmtree(pasta / PASTA_TRABALHO, ignore_errors=True)
    mapa = {}
    for e in pilhas:
        it = indice['pilhas'][e['chave']]
        mapa[e['id']] = {'sha256': it['sha256'], 'caixa': it['caixa'],
                         'arquivo': str(pasta / PASTA_ASSETS / ('%s.png' % it['sha256'])) if it['sha256'] else None}
    return mapa, do_cache


def _compor_pilhas(pasta, contrato, plat, kv, saida, faltam, indice, indice_arq, versao_psd):
    """Roda o filho das pilhas que faltam e poe os assets e o indice no lugar."""
    arquivos.gravar_json_atomico(saida / 'pedido.json', {
        'kv_sha256': contrato['origem']['kv_sha256'],
        'pilhas': [{'chave': e['chave'], 'indices': e['indices']} for e in faltam]})
    from desdobra import leitor
    # as pilhas sao compostas no tamanho do documento, qualquer que seja o formato (decisoes-v1.md, 131: o 300x600 do
    # KV C parou no teto calculado pela area do formato)
    doc = contrato.get('documento') or contrato['formato']
    orc = leitor.orcamento_bytes(kv.stat().st_size, doc['largura'] * doc['altura'])
    cmd = [str(plat.interpretador()), '-I', '-B', '-m', MODULO_PILHAS, str(kv), str(saida),
           '--orcamento-bytes', str(orc)]
    r = _rodar(plat, cmd, orc, float(limites.valor('isolador.tempo_max_s')), pasta / PASTA_TRABALHO / 'pt')
    if r.situacao != 'ok' or r.codigo != 0:
        raise _falha_filho(r, 'pilhas')
    res = arquivos.ler_json(saida / 'pilhas.json')
    (pasta / PASTA_ASSETS).mkdir(parents=True, exist_ok=True)
    for chave, it in res['pilhas'].items():
        if it['sha256']:
            dados = (saida / ('%s.png' % it['sha256'])).read_bytes()
            if arquivos.sha256_bytes(dados) != it['sha256']:
                raise ErroRender('O asset de uma pilha não bate com o hash.', 'pilha_hash', codigo=Codigo.ERRO_INTERNO)
            destino = pasta / PASTA_ASSETS / ('%s.png' % it['sha256'])
            if not destino.is_file() or arquivos.sha256_arquivo(destino) != it['sha256']:
                if destino.exists():
                    arquivos.tornar_gravavel(destino)
                arquivos.gravar_bytes_atomico(destino, dados)
        indice['pilhas'][chave] = dict(it, psd_tools=res.get('psd_tools') or versao_psd, motor=__version__)
    arquivos.gravar_json_atomico(indice_arq, indice)


# ------------------------------------------------------------------ texto no Chromium
def bytes_das_faces(pasta, contrato, estado):
    """{face_id: (bytes servidos, mime)}; os bytes vem de entrada/fontes/ (colecao: emenda do diretorio)."""
    por_sha = {reg['sha256']: rel for rel, reg in estado['entradas'].items() if rel.startswith(conferencia.PASTA_ENTRADA)}
    servidos = {}
    for f in contrato['faces']:
        rel = por_sha.get(f['sha256'])
        if rel is None:
            raise ErroRender('Um arquivo de fonte do contrato não está em entrada/fontes/.', 'fonte_ausente')
        dados = conferencia.bytes_para_servir((pasta / rel).read_bytes(), f)
        if dados is None or arquivos.sha256_bytes((pasta / rel).read_bytes()) != f['sha256']:
            raise ErroRender('Um arquivo de fonte do contrato não pode ser servido ao Chromium.', 'fonte_nao_servivel')
        servidos[f['id']] = (dados, servidor.MIME_POR_FORMATO[f['formato']])
    return servidos


def _faces_por_ps(contrato, e):
    por_id = {f['id']: f for f in contrato['faces']}
    return {ps: por_id.get(fid) for ps, fid in e['faces'].items()}


def paginas_do_contrato(contrato, prefixo):
    """As paginas iniciais do texto (uma por camada; a de varias cores so mede as posicoes)."""
    paginas = []
    for e in contrato['entradas']:
        if e['tipo'] == 'texto':
            paginas.extend(mod_texto.paginas_da_entrada(e, _faces_por_ps(contrato, e), contrato['faces'], prefixo))
    return paginas


def texto_no_chromium(contrato, servidos, prefixo, cache_control='no-store'):
    """Imprime as paginas do texto. Devolve (pdfs {pagina: bytes}, paginas impressas em PDF, cdp, cache, versao do
    Chromium). As passadas de cor de uma camada de varias cores entram na fila depois da pagina base, com as posicoes
    dos caracteres medidas nela."""
    try:
        paginas = paginas_do_contrato(contrato, prefixo)
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise ErroRender('O layout do texto não fechou (%s).' % type(e).__name__, 'texto_layout',
                         codigo=Codigo.ERRO_INTERNO) from None
    todas = list(paginas)
    entradas = {e['id']: e for e in contrato['entradas']}
    cdp_res = {'trechos': 0, 'confere': 0, 'diverge': 0, 'sem_resposta': 0, 'faces_carregadas': 0,
               'faces_nao_carregadas': 0}
    cache = {'feito': False, 'copias_encontradas': None, 'pdfs_encontrados': None, 'arquivos_varridos': 0,
             'controle_encontrado': None, 'perfil_apagado': None, 'cache_control': cache_control,
             'metodo': navegador.METODO_VARREDURA}
    if not paginas:
        return {}, paginas, cdp_res, cache, None
    htmls = {p['id']: p['html'] for p in paginas}
    primeira = paginas[0]['id']
    htmls[primeira] = htmls[primeira].replace('</head>', conferencia.LINK_CONTROLE + '</head>', 1)
    familias = [mod_texto.familia_css(prefixo, fid) for fid in servidos]
    perfil = navegador.perfil_curto()
    marcador = None
    resposta = None
    try:
        with servidor.ServidorFontes(htmls, servidos, cache_control=cache_control) as srv:
            marcador = srv.marcador_controle
            def depois(p, posicoes):
                e = entradas[p['entrada']]
                fp = _faces_por_ps(contrato, e)
                if p.get('quebra'):
                    # caixa de paragrafo: as quebras automaticas saem das posicoes medidas, e a camada volta para a fila
                    e['quebras_automaticas'] = mod_texto.quebras_da_caixa(e, posicoes, fp)
                    novas = mod_texto.paginas_da_entrada(e, fp, contrato['faces'], prefixo)
                else:
                    novas = mod_texto.paginas_de_cor(e, fp, contrato['faces'], prefixo, posicoes)
                for n in novas:
                    srv.paginas[n['id']] = n['html'].encode('utf-8')
                todas.extend(novas)
                return novas
            resposta = navegador.imprimir(srv.url_entrada, srv.url_pagina, perfil, familias, paginas, depois=depois)
    except navegador.ErroNavegador as e:
        raise ErroRender(str(e), 'chromium', codigo=Codigo.ERRO_INTERNO,
                         o_que_fazer='Rode "desdobra doctor" para conferir o Chromium fixado.') from None
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise ErroRender('O layout do texto não fechou (%s).' % type(e).__name__, 'texto_layout',
                         codigo=Codigo.ERRO_INTERNO,
                         o_que_fazer='Mande o render.json e o código para a Trezion.') from None
    finally:
        cache.update(navegador.varrer_perfil(perfil, [d for d, _t in servidos.values()], marcador))
        cache['feito'] = bool(cache['controle_encontrado'])
        cache['perfil_apagado'] = navegador.apagar_perfil(perfil)
    faces = {f['id']: f for f in contrato['faces']}
    pdfs = {}
    for p in todas:
        r = resposta['paginas'][p['id']]
        if r['pdf'] is not None:
            pdfs[p['id']] = r['pdf']
        for familia, st in r['status'].items():
            cdp_res['faces_carregadas' if st == 'loaded' else 'faces_nao_carregadas'] += 1
        for s in p['spans']:
            if not s['cdp']:
                continue
            cdp_res['trechos'] += 1
            ok = medicao.face_confere(r['cdp'].get(s['id']), faces[s['face_id']])
            cdp_res['confere' if ok else ('sem_resposta' if ok is None else 'diverge')] += 1
    return pdfs, [p for p in todas if p['id'] in pdfs], cdp_res, cache, resposta['chromium']


# ------------------------------------------------------------------ composicao
def compor(pasta_job, contrato, arq_contrato, mapa_pilhas, pdfs, paginas, plat, *, trabalho, leitura=(),
           guardar_coberturas=False, parametros_cor=None):
    """Roda o filho do render. Devolve (bytes do master, saida.json, coberturas.npz ou None)."""
    from desdobra import cor
    par = parametros_cor or cor.parametros()
    ordem = [p for p in paginas]
    cab = {'pasta_job': str(pasta_job), 'G': float(limites.valor('cor.gama_mistura_texto')),
           'supersample': int(limites.valor('render.supersample')),
           'parametros_cor': {'intent': par.intent, 'compensacao_ponto_preto': par.compensacao_ponto_preto,
                              'perfil_embutido_na_saida': par.perfil_embutido_na_saida},
           'pilhas': mapa_pilhas,
           'pdfs': [{'pagina': p['id'], 'entrada': p['entrada'], 'cor': p['cor'], 'bytes': len(pdfs[p['id']]),
                     'largura': p['largura'], 'altura': p['altura']} for p in ordem],
           'leitura': [str(x) for x in leitura], 'guardar_coberturas': bool(guardar_coberturas)}
    corpo = json.dumps(cab, ensure_ascii=False).encode('utf-8') + b'\n' + b''.join(pdfs[p['id']] for p in ordem)
    saida = Path(trabalho) / 'composicao'
    shutil.rmtree(saida, ignore_errors=True)
    saida.mkdir(parents=True)
    W, H = contrato['formato']['largura'], contrato['formato']['altura']
    px_linkados = sum(int(e['dims'][0]) * int(e['dims'][1]) for e in contrato['entradas']
                      if e['tipo'] == 'linkado' and e.get('dims'))
    orc = orcamento_composicao(W, H, len(corpo), px_linkados)
    cmd = [str(plat.interpretador()), '-I', '-B', '-m', MODULO_FILHO, str(arq_contrato), str(saida),
           '--orcamento-bytes', str(orc)]
    r = _rodar(plat, cmd, orc, float(limites.valor('render.tempo_max_s')), Path(trabalho) / 'ct', entrada=corpo)
    del corpo
    if r.situacao != 'ok' or r.codigo != 0:
        raise _falha_filho(r, 'composicao')
    res = arquivos.ler_json(saida / 'saida.json')
    master = (saida / 'master.png').read_bytes()
    cob = (saida / 'coberturas.npz') if (saida / 'coberturas.npz').is_file() else None
    return master, res, cob, r.pico_bytes


# ------------------------------------------------------------------ varredura
def varrer_pdfs_no_job(pasta_job):
    """Arquivos com assinatura de PDF na pasta do job fora de entrada/ (as entradas sao do DA, congeladas)."""
    n, varridos = 0, 0
    for p in Path(pasta_job).rglob('*'):
        if not p.is_file() or p.relative_to(pasta_job).as_posix().startswith(PASTA_ENTRADA):
            continue
        varridos += 1
        try:
            if navegador.ASSINATURA_PDF in p.read_bytes():
                n += 1
        except OSError:
            continue
    return n, varridos


# ------------------------------------------------------------------ render do job
def montar_contrato(pasta, formato=mod_contrato.FORMATO_ORIGEM, funcoes=None):
    """(contrato, bloqueios, pede_confirmacao) do formato: o da origem (M4) ou o de um formato derivado (M5)."""
    if formato == mod_contrato.FORMATO_ORIGEM:
        return mod_contrato.montar(pasta, funcoes=funcoes)
    from desdobra.render import derivado
    return derivado.montar(pasta, formato)


def _gravar_parada(pasta, formato, e):
    """render/<formato>/parada.json com o motivo, o codigo e as medidas de toda parada (decisoes-v1.md, 131)."""
    try:
        destino = Path(pasta).resolve() / 'render' / str(formato)
        destino.mkdir(parents=True, exist_ok=True)
        arquivos.gravar_json_atomico(destino / 'parada.json', {
            'formato': str(formato), 'quando': agora(), 'motivo': e.motivo, 'codigo': int(e.codigo),
            'mensagem': str(e), 'o_que_fazer': e.o_que_fazer, 'medidas': e.medidas})
    except OSError:
        pass


def renderizar(pasta_job, *, disparo, aceites=(), plat=None, funcoes=None, guardar_coberturas=None,
               formato=mod_contrato.FORMATO_ORIGEM, progresso=None, parar=None):
    """Renderiza um formato do job (veja _renderizar). Toda parada depois do disparo humano grava
    render/<formato>/parada.json; o render que termina apaga a parada velha."""
    from desdobra import humano
    try:
        humano.conferir(disparo, 'render', consumir=False, alvo=formato)
    except humano.ErroHumano:
        return _renderizar(pasta_job, disparo=disparo, aceites=aceites, plat=plat, funcoes=funcoes,
                           guardar_coberturas=guardar_coberturas, formato=formato, progresso=progresso, parar=parar)
    try:
        rel = _renderizar(pasta_job, disparo=disparo, aceites=aceites, plat=plat, funcoes=funcoes,
                          guardar_coberturas=guardar_coberturas, formato=formato, progresso=progresso, parar=parar)
    except ErroRender as e:
        _gravar_parada(pasta_job, formato, e)
        raise
    velha = Path(pasta_job).resolve() / 'render' / str(formato) / 'parada.json'
    if velha.is_file():
        arquivos.tornar_gravavel(velha)
        velha.unlink()
    return rel


def _renderizar(pasta_job, *, disparo, aceites=(), plat=None, funcoes=None, guardar_coberturas=None,
                formato=mod_contrato.FORMATO_ORIGEM, progresso=None, parar=None):
    """Renderiza um formato do job: a origem (M4) ou um formato derivado (M5, de derivacao/<formato>.json). disparo:
    o Disparo que desdobra.humano.exigir('render') emitiu depois de conferir o console, ou o da tela preso a este
    formato (humano.exigir_tela com alvo; M7b, B2): nada mais vale, o disparo so serve uma vez e o selo de outro
    formato e recusado; aceites: decisoes do DA confirmadas no terminal ou na janela da tela (codigos de
    pede_confirmacao). Devolve o
    render.json gravado. ErroRender quando para; nesse caso nao fica master nem render.json novos, nem
    render/.trabalho.

    guardar_coberturas: pasta fora do job para as coberturas do texto (so a medicao do corpus usa).
    progresso(etapa) e parar() -> bool (M7b, B1; a tarefa da tela, desdobra.tela.tarefas): antes de cada etapa
    (ETAPAS), parar() verdadeiro corta o render com o motivo "parado" (o selo ja foi gasto, e nada e gravado alem da
    parada); senao, progresso diz a etapa que comeca. A ultima conferencia e depois da composicao, antes de gravar."""
    from desdobra import humano
    try:
        humano.conferir(disparo, 'render', consumir=True, alvo=formato)
    except humano.ErroHumano:
        raise ErroRender('O render só parte de uma pessoa num terminal interativo.', 'disparo_sem_conferencia',
                         o_que_fazer=humano.O_QUE_FAZER) from None

    def etapa(nome):
        if parar is not None and parar():
            raise ErroRender('O render foi parado antes de terminar.', 'parado', medidas={'etapa': nome})
        if progresso is not None:
            progresso(nome)
    etapa('contrato')
    t0 = time.perf_counter()
    tempos = {}
    pasta = Path(pasta_job).resolve()
    plat = plat or plataforma.obter()
    estado = contratos.ler(pasta / 'estado.json', 'estado/1')
    contrato, bloqueios, confirmar = montar_contrato(pasta, formato, funcoes)
    if bloqueios:
        raise ErroRender('O render tem bloqueio: %s.' % ', '.join(sorted({b['codigo'] for b in bloqueios})),
                         'bloqueio', o_que_fazer=' '.join(dict.fromkeys(b['descricao'] for b in bloqueios)),
                         medidas={'bloqueios': bloqueios})
    faltando = [c for c in confirmar if c['codigo'] not in set(aceites)]
    if faltando:
        raise ErroRender('O render pede decisão do DA: %s.' % ', '.join(c['codigo'] for c in faltando),
                         'pede_decisao_do_da', o_que_fazer=' '.join(c['descricao'] for c in faltando),
                         medidas={'pede_confirmacao': faltando})
    formato = contrato['formato']['chave']
    arq_contrato = mod_contrato.gravar(pasta, contrato)
    tempos['contrato'] = round(time.perf_counter() - t0, 3)

    etapa('pilhas')
    t1 = time.perf_counter()
    mapa_pilhas, do_cache = resolver_pilhas(pasta, contrato, plat)
    tempos['pilhas'] = round(time.perf_counter() - t1, 3)

    etapa('texto')
    t2 = time.perf_counter()
    servidos = bytes_das_faces(pasta, contrato, estado)
    prefixo = 'dsd-%s' % estado['job_id'][:8]  # numero-neutro: prefixo curto do job no nome da familia
    pdfs, paginas, cdp, cache, versao_chromium = texto_no_chromium(contrato, servidos, prefixo)
    tempos['chromium'] = round(time.perf_counter() - t2, 3)
    if cdp['diverge'] or cdp['sem_resposta'] or cdp['faces_nao_carregadas']:
        raise ErroRender('O CDP não confirmou a face do arquivo do job em todos os trechos.', 'face_cdp_nao_confere',
                         o_que_fazer='Rode "desdobra fontes conferir --job <pasta>" e "desdobra doctor".',
                         medidas={'cdp': cdp})
    if cache['copias_encontradas'] or cache['pdfs_encontrados']:
        raise ErroRender('A varredura achou cópia da fonte ou PDF no perfil do Chromium.', 'copia_no_perfil',
                         medidas={'cache': cache})
    # texto visivel tem de sair com trecho conferido: sem pagina ou sem trecho, o master sairia sem o texto
    textos = [e for e in contrato['entradas'] if e['tipo'] == 'texto']
    conferidas = {p['entrada'] for p in paginas if any(s['cdp'] for s in p['spans'])}
    if textos and (not cdp['trechos'] or any(e['id'] not in conferidas for e in textos)):
        raise ErroRender('Uma camada de texto visível ficou sem trecho conferido por CDP.', 'texto_sem_trecho_conferido',
                         o_que_fazer='Rode "desdobra job proxima --todas" e "desdobra doctor"; se repetir, mande o '
                                     'render.json para a Trezion.', medidas={'cdp': cdp})

    etapa('composicao')
    t3 = time.perf_counter()
    leitura = [pasta / PASTA_ASSETS, pasta / 'entrada' / 'campanha']
    if contrato['documento'].get('perfil'):
        leitura.append((pasta / contrato['documento']['perfil']['arquivo']).parent)
    from desdobra import ds
    par_cor = None
    arq_par = pasta / ds.ARQUIVO_PARAMETROS
    if arq_par.is_file():
        par_cor = ds.parametros_do_job(contratos.ler(arq_par, 'ds-parametros-cor/1'))
    trabalho = pasta / PASTA_TRABALHO
    try:
        master, saida, cob, pico = compor(pasta, contrato, arq_contrato, mapa_pilhas, pdfs, paginas, plat,
                                          trabalho=trabalho, leitura=leitura,
                                          guardar_coberturas=guardar_coberturas is not None, parametros_cor=par_cor)
        del pdfs
        if cob is not None and guardar_coberturas is not None:
            Path(guardar_coberturas).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(cob, Path(guardar_coberturas) / 'coberturas.npz')
    finally:
        shutil.rmtree(trabalho, ignore_errors=True)
    tempos['composicao'] = round(time.perf_counter() - t3, 3)
    if formato != mod_contrato.FORMATO_ORIGEM:
        from desdobra.render import derivado as mod_derivado
        fora_da_caixa = mod_derivado.tinta_fora_da_caixa(contrato['entradas'], saida.get('entradas') or [],
                                                         contrato['formato']['largura'], contrato['formato']['altura'])
        if fora_da_caixa:
            raise ErroRender('A tinta de um texto passou da caixa que a derivação validou (ou foi cortada na página).',
                             'tinta_fora_da_caixa_validada', medidas={'textos': fora_da_caixa},
                             o_que_fazer='Rode o "desdobra derivar" de novo; se continuar, mande o render.json para a Trezion.')
    etapa('gravacao')
    destino = pasta / 'render' / formato

    fora, varridos = conferencia.varrer_fontes_fora_da_entrada(pasta)
    pdfs_job, varridos_pdf = varrer_pdfs_no_job(pasta)
    por_id = {f['id']: f for f in contrato['faces']}
    usados = sorted({s['face_id'] for p in paginas for s in p['spans']})
    from desdobra import cor
    par = par_cor or cor.parametros()
    rel = {
        'esquema': ESQUEMA_RENDER, 'job_id': estado['job_id'], 'formato': dict(contrato['formato']),
        'gerado_em': agora(), 'motor_versao': __version__,
        'disparo': disparo.registro(),
        'versoes': {'chromium': versao_chromium, 'playwright': _versao('playwright'),
                    'pypdfium2': (saida.get('versoes') or {}).get('pypdfium2'),
                    'pdfium': (saida.get('versoes') or {}).get('pdfium'), 'psd_tools': _versao('psd-tools'),
                    'numpy': (saida.get('versoes') or {}).get('numpy'),
                    'pillow': (saida.get('versoes') or {}).get('pillow'), 'lcms': cor.versao_lcms(),
                    'python': _platform.python_version(), 'sistema': sys.platform},
        'parametros': {'gama': limites.obter('cor.gama_mistura_texto').citacao(),
                       'supersample': limites.obter('render.supersample').citacao(),
                       'corpo_sharp_pequeno': limites.obter('render.corpo_sharp_pequeno_px').citacao(),
                       'margem_regiao': limites.obter('render.margem_regiao_px').citacao(),
                       'cor': par.para_json()},
        'contrato_sha256': arquivos.sha256_arquivo(arq_contrato),
        'master': {'arquivo': 'render/%s/master.png' % formato, 'sha256': arquivos.sha256_bytes(master),
                   'largura': saida['master']['largura'], 'altura': saida['master']['altura'],
                   'modo': saida['master']['modo']},
        'fontes': [{'face_id': fid, 'sha256': por_id[fid]['sha256'], 'nome_ps': por_id[fid]['nome_ps'],
                    'formato': por_id[fid]['formato']} for fid in usados],
        'cdp': cdp, 'cache': cache,
        'varredura': {'arquivos_de_fonte_fora_da_entrada': fora, 'arquivos_varridos': varridos,
                      'pdfs_no_job': pdfs_job, 'arquivos_varridos_pdf': varridos_pdf},
        'assets': [{'tipo': 'pilha', 'entrada': eid, 'sha256': m['sha256'],
                    'arquivo': 'render/assets/%s.png' % m['sha256'] if m['sha256'] else None}
                   for eid, m in sorted(mapa_pilhas.items())] +
                  [{'tipo': 'linkado', 'entrada': e['id'], 'layer_id': e['layer_id'], 'sha256': e['sha256'],
                    'arquivo': e['arquivo']} for e in contrato['entradas'] if e['tipo'] == 'linkado'],
        'pilhas_do_cache': do_cache,
        'aceites': [{'codigo': c['codigo'], 'medidas': c['medidas'], 'meio': disparo.meio,
                     'quando': disparo.quando} for c in confirmar],
        'registros': list(contrato['registros']) + list(saida.get('registros') or []),
        'curva': saida.get('curva'), 'conversao_cor': saida.get('conversao'),
        'entradas': saida.get('entradas') or [],
        'textos': {'camadas': sum(1 for e in contrato['entradas'] if e['tipo'] == 'texto'),
                   'sharp_pequeno': sum(1 for e in contrato['entradas'] if e['tipo'] == 'texto' and e['sharp_pequeno']),
                   'paginas_pdf': len(paginas),
                   # o texto editado pelo DA (M7b, A7): as linhas que o render desenhou, com as quebras da medida
                   'editados': [{'entrada': e['id'], 'layer_id': e['layer_id'], 'elemento': e.get('elemento'),
                                 'linhas': mod_texto.linhas_desenhadas(e)}
                                for e in contrato['entradas'] if e['tipo'] == 'texto' and e.get('texto_editado')]},
        'recursos': {'pico_bytes_composicao': pico},
        'tempos': dict(tempos, filho=saida.get('tempos')), 'tempo_s': round(time.perf_counter() - t0, 3),
    }
    if formato != mod_contrato.FORMATO_ORIGEM:
        from desdobra.derivacao import nucleo as nd
        arq_d = pasta / nd.PASTA / ('%s.json' % formato)
        d = contratos.ler(arq_d, nd.ESQUEMA)
        # impressao_formato: a do contrato, que e o que o portao e a aprovacao comparam (M7b, A2); o sha do arquivo e o
        # do briefing ficam como registro
        rel['derivacao'] = {'arquivo': '%s/%s.json' % (nd.PASTA.as_posix(), formato),
                            'sha256': arquivos.sha256_arquivo(arq_d), 'caminho': d['caminho'],
                            'impressao_formato': contrato['origem'].get('derivacao_impressao'),
                            'briefing_sha256': d['briefing_sha256'], 'briefing_origem': d['briefing_origem'],
                            'mestre': (d.get('mestre') or {}).get('id')}
    if fora or pdfs_job:
        raise ErroRender('A varredura achou arquivo de fonte ou PDF na pasta do job depois do render.', 'varredura',
                         medidas={'varredura': rel['varredura']})
    contratos.validar(rel, ESQUEMA_RENDER)
    # grava em temporario e so promove depois da varredura: master e render.json saem juntos ou nao saem
    tmp_master, tmp_rel = destino / (arquivos.PREFIXO_TEMPORARIO + 'master.png'), destino / (arquivos.PREFIXO_TEMPORARIO + 'render.json')
    try:
        arquivos.gravar_bytes_atomico(tmp_master, master)
        arquivos.gravar_json_atomico(tmp_rel, rel)
        os.replace(tmp_master, destino / 'master.png')
        os.replace(tmp_rel, destino / 'render.json')
    finally:
        for t in (tmp_master, tmp_rel):
            if t.exists():
                t.unlink()
    return rel
