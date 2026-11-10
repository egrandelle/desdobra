# -*- coding: utf-8 -*-
"""M7b, C3: a medida da quebra de linha ao vivo, com cache (derivacao.medida_quebras; decisoes-v1.md, 167 e 171).

Criterios de pronto cobertos aqui:
  - a segunda medida igual nao abre o Chromium: a medida de cada texto com as suas quebras fica guardada no processo;
  - so o texto cuja quebra mudou vai ao Chromium; a medida que falhou nao fica guardada;
  - a chave da medida muda com o texto, com as quebras e com as faces servidas;
  - a previa da familia leva a quebra do rascunho (o campo quebras do pedido): mede uma vez, desenha as linhas juntadas
    em cada membro e recusa a posicao fora de um espaco do texto;
  - a previa e a derivacao gravada usam a mesma medida: depois de gravar o briefing com a mesma quebra, a derivacao
    nao abre o Chromium e a caixa do texto e a da previa;
  - a pagina manda a quebra do rascunho com a previa e espera 300 ms sem clique antes de pedir a previa da quebra.
Tudo sintetico: o PSD de duas linhas de test_tela_palco e a fonte de autoteste do motor."""
import copy
import json
import re

import pytest

import test_derivacao_apoio as ap
import test_render_texto_editado as rte
import test_tela_palco as tp
from desdobra import contratos
from desdobra.briefing import modelo as mb
from desdobra.chromium import navegador
from desdobra.derivacao import medida_quebras as mm
from desdobra.derivacao import nucleo as nd
from desdobra.derivacao import quebras as mq
from desdobra.fontes import medicao
from desdobra.job import nucleo
from desdobra.tela import estado as te

modelo = rte.modelo
job = rte.job
CONF = rte.CONF


@pytest.fixture
def espiao(monkeypatch):
    """Conta as aberturas do Chromium da medida e os textos de cada pagina de medida (o real continua medindo)."""
    real_conferir, real_montar = navegador.conferir, medicao.montar
    visto = {'chromium': 0, 'textos': []}

    def conferir(*a, **k):
        visto['chromium'] += 1
        return real_conferir(*a, **k)

    def montar(textos, *a, **k):
        visto['textos'].append(len(textos))
        return real_montar(textos, *a, **k)
    monkeypatch.setattr(mm.navegador, 'conferir', conferir)
    monkeypatch.setattr(mm.medicao, 'montar', montar)
    mm.limpar_cache()
    yield visto
    mm.limpar_cache()


def _briefing(job_, layer_id, *pedidos):
    """O briefing gravado com uma entrada de familia por pedido (manter, inseridas) no texto layer_id."""
    b = contratos.ler(job_ / mb.ARQUIVO, 'briefing/1')
    b['quebras_por_familia'] = [{'layer_id': layer_id, 'familia': 'g%d' % n, 'formatos': ['mesma'],
                                 'quebras': ap.decisao(list(manter)), 'inseridas': list(ins), 'origem': 'da',
                                 'aprovada': True} for n, (manter, ins) in enumerate(pedidos)]
    return b


def _medir(job_, b):
    laudo = contratos.ler(job_ / mb.ARQUIVO_LAUDO, 'laudo/1')
    return mm.medir(job_, laudo, b, nucleo.ler_estado(job_))


# ------------------------------------------------------------------ o cache da medida
def test_segunda_medida_igual_nao_abre_o_chromium(job, modelo, espiao):
    lid = modelo['layer_id']
    b = _briefing(job, lid, ((), ()))
    primeira = _medir(job, b)
    ch = mq.chave(lid, (), ())
    assert 'largura_texto' in primeira[ch], primeira
    assert espiao['chromium'] == 1
    segunda = _medir(job, b)
    assert segunda == primeira
    assert espiao['chromium'] == 1
    # quem recebe a medida pode mexer nela sem mexer no que ficou guardado
    segunda[ch]['largura_texto'] = -1.0
    assert _medir(job, b) == primeira and espiao['chromium'] == 1


def test_so_o_texto_que_mudou_vai_ao_chromium(job, modelo, espiao):
    lid = modelo['layer_id']
    juntar, manter = ((), ()), ((0,), ())
    antes = _medir(job, _briefing(job, lid, juntar))
    assert espiao['chromium'] == 1 and espiao['textos'] == [2]  # numero-neutro: o texto da mestre e o juntado
    depois = _medir(job, _briefing(job, lid, juntar, manter))
    # o pedido novo vai ao Chromium sozinho; o guardado volta igual
    assert espiao['chromium'] == 2 and espiao['textos'] == [2, 2]  # numero-neutro: um pedido por pagina
    assert depois[mq.chave(lid, (), ())] == antes[mq.chave(lid, (), ())]
    assert 'largura_texto' in depois[mq.chave(lid, (0,), ())]


def test_medida_que_falhou_nao_fica_guardada(job, modelo, espiao, monkeypatch):
    lid = modelo['layer_id']
    b = _briefing(job, lid, ((), ()))
    real = mm.navegador.conferir

    def falhar(*_a, **_k):
        raise navegador.ErroNavegador('teste')
    monkeypatch.setattr(mm.navegador, 'conferir', falhar)
    assert _medir(job, b)[mq.chave(lid, (), ())] == {'erro': 'chromium_nao_mediu'}
    monkeypatch.setattr(mm.navegador, 'conferir', real)
    assert 'largura_texto' in _medir(job, b)[mq.chave(lid, (), ())]
    assert espiao['chromium'] == 1
    # a medida boa fica guardada
    assert 'largura_texto' in _medir(job, b)[mq.chave(lid, (), ())] and espiao['chromium'] == 1


def test_chave_da_medida_muda_com_o_texto_as_quebras_e_as_faces():
    camada = {'tipo': 'texto', 'texto': {'conteudo': 'AB\rab', 'runs': [{'inicio': 0, 'texto': 'AB\rab',
                                                                         'fonte_ps': 'Teste-Regular'}]}}
    faces = [('f1', 'a' * 64)]  # numero-neutro: sha256 em hexadecimal
    base = mm.chave_da_medida(camada, (), (), faces)
    assert base == mm.chave_da_medida(copy.deepcopy(camada), (), (), list(faces))
    outra = copy.deepcopy(camada)
    outra['texto']['runs'][0]['corpo'] = 30.0
    assert mm.chave_da_medida(outra, (), (), faces) != base
    assert mm.chave_da_medida(camada, (0,), (), faces) != base
    assert mm.chave_da_medida(camada, (), (1,), faces) != base
    assert mm.chave_da_medida(camada, (), (), [('f1', 'b' * 64)]) != base  # numero-neutro: outra face


# ------------------------------------------------------------------ a previa da familia com a quebra do rascunho
def _quebra(conteudo, gid, modelo, manter=(), inseridas=()):
    el = rte._titulo(conteudo, gid)
    return el, {'elemento': el, 'layer_id': modelo['layer_id'], 'manter': list(manter),
                'inseridas': list(inseridas), 'origem': 'da', 'aprovada': True}


def _linhas_do_texto(palco, layer_id):
    p = next(x for x in palco['pecas'] if x.get('camada') == layer_id and x.get('linhas'))
    return [''.join(t['texto'] for t in ln['trechos']) for ln in p['linhas']]


def test_previa_mede_a_quebra_do_rascunho_uma_vez_e_junta_as_linhas(job, modelo, espiao):
    conteudo = te.montar(job)
    gid = rte._familia_de(conteudo, 'mesma')
    sem = conteudo['editar']({'familia': gid, 'versao': None, 'edicoes': []})
    assert all(_linhas_do_texto(m['palco'], modelo['layer_id']) == list(tp.LINHAS_DUAS) for m in sem['membros'])
    espiao['chromium'] = 0
    _el, q = _quebra(conteudo, gid, modelo)
    dados = {'familia': gid, 'versao': None, 'edicoes': [], 'quebras': [q]}
    r = conteudo['editar'](dados)
    assert r is not None and r['membros']
    for m in r['membros']:
        assert _linhas_do_texto(m['palco'], modelo['layer_id']) == [' '.join(tp.LINHAS_DUAS)], m['formato']
    assert espiao['chromium'] == 1
    # a pagina pede de novo (outra edicao, a mesma quebra): a medida guardada vale
    assert conteudo['editar'](copy.deepcopy(dados))['membros'] and espiao['chromium'] == 1
    # tirar a quebra no rascunho volta as linhas do KV, sem medir
    r0 = conteudo['editar'](dict(dados, quebras=[]))
    assert all(_linhas_do_texto(m['palco'], modelo['layer_id']) == list(tp.LINHAS_DUAS) for m in r0['membros'])
    assert espiao['chromium'] == 1


def test_previa_recusa_quebra_fora_de_espaco_ou_de_outro_elemento(job, modelo, espiao):
    conteudo = te.montar(job)
    gid = rte._familia_de(conteudo, 'mesma')
    _el, q = _quebra(conteudo, gid, modelo)
    base = {'familia': gid, 'versao': None, 'edicoes': []}
    # o texto do KV nao tem espaco: nenhuma posicao inserida cabe nele
    assert conteudo['editar'](dict(base, quebras=[dict(q, inseridas=[0])])) is None
    assert conteudo['editar'](dict(base, quebras=[dict(q, manter=[3])])) is None
    outro = next(e['id'] for e in conteudo['editar'](base)['membros'][0]['palco']['elementos']
                 if e['id'] != q['elemento'])
    assert conteudo['editar'](dict(base, quebras=[dict(q, elemento=outro)])) is None
    assert conteudo['editar'](dict(base, quebras=[q, q])) is None
    assert conteudo['editar'](dict(base, quebras=[dict(q, origem='da', aprovada=False)])) is None
    assert espiao['chromium'] == 0
    # a quebra que junta as linhas do KV passa, e a proposta do desdobra ainda sem aprovacao tambem (C4 pede aprovar)
    assert conteudo['editar'](dict(base, quebras=[q])) is not None
    assert conteudo['editar'](dict(base, quebras=[dict(q, origem='proposta', aprovada=False)])) is not None
    assert espiao['chromium'] == 1


def test_previa_e_derivacao_gravada_usam_a_mesma_medida(job, modelo, espiao):
    conteudo = te.montar(job)
    gid = rte._familia_de(conteudo, 'mesma')
    el, q = _quebra(conteudo, gid, modelo)
    r = conteudo['editar']({'familia': gid, 'versao': None, 'edicoes': [], 'quebras': [q]})
    assert espiao['chromium'] == 1
    caixas = {m['formato']: next(e['caixa'] for e in m['palco']['elementos'] if e['id'] == el) for m in r['membros']}
    # "Salvar e seguir" grava a mesma quebra: a derivacao pega a medida guardada, sem abrir o Chromium
    _el, membros = rte._com_quebra(job, modelo, None, manter=())
    assert espiao['chromium'] == 1
    assert set(membros) == set(caixas)
    for fid in membros:
        d = rte._deriv(job, fid)
        x = next(e for e in d['elementos'] if e['id'] == el)
        assert x['quebras']['familia'][0]['aprovadas'] == []
        assert x['caixa'] == pytest.approx(caixas[fid], abs=0.01), fid  # numero-neutro: o arredondamento do palco


# ------------------------------------------------------------------ a pagina
def test_pagina_manda_a_quebra_e_espera_300_ms_sem_clique():
    """A pagina leva a quebra do rascunho da familia em cada previa e, quando so a quebra muda, espera 300 ms sem
    clique antes de pedir (o controle da quebra no palco, C4, chama pedirPreviaDaQuebra)."""
    from desdobra.tela import estatico
    js = (estatico.PASTA_TELA / 'tela.js').read_text(encoding='utf-8')
    assert re.search(r'const ESPERA_QUEBRA_MS = 300;', js)
    corpo = js[js.index('function pedirPrevia()'):js.index('function tirarRecusadas')]
    assert 'quebras' in corpo and 'clearTimeout(ed.esperaQuebra)' in corpo
    espera = js[js.index('function pedirPreviaDaQuebra()'):]
    espera = espera[:espera.index('\n  }\n') + 4]
    assert 'setTimeout(pedirPrevia, ESPERA_QUEBRA_MS)' in espera
    # um clique durante a espera recomeca a espera
    assert re.search(r"addEventListener\('pointerdown', function \(\) \{\s*"
                     r"if \(ed\.esperaQuebra\) pedirPreviaDaQuebra\(\);", js)


@pytest.mark.skipif(__import__('sys').platform != 'win32', reason='o isolador dos filhos roda no Windows')
def test_pagina_leva_a_quebra_do_rascunho_ao_palco(job, modelo, espiao):
    from playwright.sync_api import sync_playwright

    import test_tela_galeria as tg
    from desdobra.tela import atos as ta
    from desdobra.tela import rascunho as tr
    from desdobra.tela import servidor as ts
    conteudo = te.montar(job)
    gid = rte._familia_de(conteudo, 'mesma')
    _el, q = _quebra(conteudo, gid, modelo)
    laudo_sha = tr.laudo_sha256(job)
    familias = {g: {'versao': None, 'confirmada': False, 'edicoes': []} for g in conteudo['familias']}
    familias[gid]['quebras'] = [q]
    tr.gravar(job, {'job_id': conteudo['estado']['job_id'], 'laudo_sha256': laudo_sha, 'familias': familias},
              job_id=conteudo['estado']['job_id'], laudo_atual=laudo_sha, origem=mb.ORIGEM_FIXTURE)
    navegador.apontar_playwright()
    with ts.ServidorTela(conteudo, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo)) as srv, sync_playwright() as pw:
        nav, pg = tp._pagina_da_tela(pw, srv, 1600, 900)  # numero-neutro: janela do teste
        try:
            tg._abrir(pg, conteudo['estado'], 'mesma')
            tp._esperar(pg, '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""')
            linhas = pg.evaluate('() => Array.from(document.querySelectorAll("#palco .texto .linha"))'
                                 '.map(l => l.textContent)')
        finally:
            nav.close()
    assert ' '.join(tp.LINHAS_DUAS) in linhas, linhas
    assert espiao['chromium'] == 1
    assert json.loads((job / tr.ARQUIVO).read_text(encoding='utf-8'))['familias'][gid]['quebras'] == [q]


# ------------------------------------------------------------------ a previa sem a quebra gravada (revisao do C)
def test_previa_sem_quebra_no_pedido_volta_as_linhas_do_kv(job, modelo, espiao):
    """O briefing gravado tem a quebra do DA que junta as linhas; o DA a tira no palco e o rascunho fica sem quebra
    nesta familia. A previa sem o campo quebras e a previa com a lista vazia desenham as linhas do KV, as que "Salvar
    e seguir" grava: a previa nunca volta a quebra do briefing de antes."""
    rte._com_quebra(job, modelo, None, manter=())
    conteudo = te.montar(job)
    gid = rte._familia_de(conteudo, 'mesma')
    sem_campo = conteudo['editar']({'familia': gid, 'versao': None, 'edicoes': []})
    vazia = conteudo['editar']({'familia': gid, 'versao': None, 'edicoes': [], 'quebras': []})
    for r in (sem_campo, vazia):
        assert r['membros']
        assert all(_linhas_do_texto(m['palco'], modelo['layer_id']) == list(tp.LINHAS_DUAS) for m in r['membros'])


def test_pagina_manda_a_lista_de_quebras_mesmo_vazia():
    """A pagina leva sempre as quebras do rascunho da familia na previa, a lista vazia quando o DA tirou a ultima."""
    from desdobra.tela import estatico
    js = (estatico.PASTA_TELA / 'tela.js').read_text(encoding='utf-8')
    corpo = js[js.index('function pedirPrevia()'):js.index('function pedirPreviaDaQuebra')]
    assert re.search(r"quebras: \(fam && fam\.quebras\) \|\| \[\]", corpo), corpo


@pytest.mark.skipif(__import__('sys').platform != 'win32', reason='o isolador dos filhos roda no Windows')
def test_pagina_sem_quebra_no_rascunho_mostra_as_linhas_do_kv(job, modelo):
    """Na pagina: o briefing gravado tem a quebra do DA na familia, e o rascunho nao tem quebra nela (o DA voltou as
    quebras do KV). O palco mostra as linhas do KV, as da derivacao que "Salvar e seguir" grava."""
    from playwright.sync_api import sync_playwright

    import test_tela_galeria as tg
    from desdobra.tela import atos as ta
    from desdobra.tela import rascunho as tr
    from desdobra.tela import servidor as ts
    conteudo = te.montar(job)
    gid = rte._familia_de(conteudo, 'mesma')
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    conf = {'origem': mb.ORIGEM_FIXTURE, 'meio': 'tela', 'em': '2026-11-06T10:00:00'}
    b['composicoes'] = [{'familia': g, 'formatos': f['formatos'], 'versao': None, 'edicoes': [], 'confirmada': True,
                         'confirmacao': dict(conf)} for g, f in conteudo['familias'].items()]
    b['quebras_por_familia'] = [{'layer_id': modelo['layer_id'], 'familia': gid,
                                 'formatos': list(conteudo['familias'][gid]['formatos']),
                                 'quebras': ap.decisao([]), 'inseridas': [], 'origem': 'da', 'aprovada': True}]
    contratos.gravar(job / mb.ARQUIVO, b, 'briefing/1')
    conteudo = te.montar(job)
    laudo_sha = tr.laudo_sha256(job)
    familias = {g: {'versao': None, 'confirmada': False, 'edicoes': []} for g in conteudo['familias']}
    tr.gravar(job, {'job_id': conteudo['estado']['job_id'], 'laudo_sha256': laudo_sha, 'familias': familias},
              job_id=conteudo['estado']['job_id'], laudo_atual=laudo_sha, origem=mb.ORIGEM_FIXTURE)
    navegador.apontar_playwright()
    mm.limpar_cache()
    with ts.ServidorTela(conteudo, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo)) as srv, sync_playwright() as pw:
        nav, pg = tp._pagina_da_tela(pw, srv, 1600, 900)  # numero-neutro: janela do teste
        try:
            tg._abrir(pg, conteudo['estado'], 'mesma')
            tp._esperar(pg, '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""')
            linhas = pg.evaluate('() => Array.from(document.querySelectorAll("#palco .texto .linha"))'
                                 '.map(l => l.textContent)')
        finally:
            nav.close()
            mm.limpar_cache()
    assert ' '.join(tp.LINHAS_DUAS) not in linhas, linhas
    assert all(x in linhas for x in tp.LINHAS_DUAS), linhas
