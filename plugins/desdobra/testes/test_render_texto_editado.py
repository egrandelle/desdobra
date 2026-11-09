# -*- coding: utf-8 -*-
"""M7b, A7: o render do texto editado pelo DA no palco (decisoes-v1.md, 169 e 171).

Criterios de pronto cobertos aqui:
  - a derivacao nunca junta as quebras da proposta com o texto editado: o texto do DA leva so as quebras dele (o \\n)
    e as da medida na largura da caixa;
  - o contrato do render leva o texto editado num trecho so, com o estilo do primeiro trecho com tinta, e confere o
    cmap da face do job como a edicao na tela: caractere que a fonte nao tem e recusado com motivo claro;
  - no Chromium, o texto com \\n sai exatamente nas linhas pedidas, e a linha que passa da largura da caixa quebra no
    espaco, como na previa;
  - a tinta do render bate com a previa da tela dentro da tolerancia da tinta do texto (render.tolerancia_tinta_texto).
Tudo sintetico: o PSD de duas linhas de test_tela_palco e a fonte de autoteste do motor."""
import json
import shutil
import sys

import pytest

import test_derivacao_apoio as ap
import test_fontes_apoio as fap
import test_tela_palco as tp
from desdobra import contratos, humano
from desdobra.briefing import modelo as mb
from desdobra.derivacao import nucleo as nd
from desdobra.render import derivado as rd
from desdobra.render import execucao
from desdobra.render import texto as rt
from desdobra.tela import estado as te

ROT0 = {'graus': 0, 'sentido': None}
CONF = {'origem': 'da', 'meio': 'tela', 'em': '2026-11-06T10:00:00'}
# os glifos da fonte de autoteste em unidades por em (1000): avanco e tinta de cada um (desdobra.render.autoteste)
AVANCOS = tp.AVANCOS
EM = 1000.0  # numero-neutro: unidades por em da fonte de autoteste
DUAS_LINHAS = 'HAH\nHOX'
REFLOW = 'H H H'


@pytest.fixture(scope='module')
def modelo(tmp_path_factory):
    """O job de duas linhas (a camada de pixels do tamanho da tinta do texto, a previa e o render no mesmo lugar)."""
    from desdobra.job import nucleo
    from desdobra.render import autoteste
    base = tmp_path_factory.mktemp('texto-editado')
    fontes = base / 'origem-fontes'
    fap.gravar(fontes, 'autoteste.ttf', autoteste.gerar_fonte())
    job = base / 'job'
    nucleo.criar(job, tp._psd_duas_linhas(base / 'origem' / 'kv.psd', autoteste.NOME_PS), 'c', fontes=[fontes])
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    laudo = contratos.ler(job / mb.ARQUIVO_LAUDO, 'laudo/1')
    ids = {c['nome']: c['identidade']['layer_id'] for c in laudo['camadas']}
    funcoes = {ids['fundo-sintetico']: 'fundo', ids['duas-linhas']: 'titulo', ids['quadrado-sintetico']: 'logo_principal'}
    b = ap.briefing(funcoes=funcoes, formatos=[ap.formato(i, w, h, rotacao=ROT0) for i, w, h in tp.FORMATOS_DUAS])
    b.pop('cabecalho')
    b.pop('job_id')
    arq = base / 'fixture.json'
    arq.write_text(json.dumps(b), encoding='utf-8')
    mb.importar_teste(job, arq)
    return {'job': job, 'layer_id': ids['duas-linhas']}


@pytest.fixture
def job(modelo, tmp_path):
    destino = tmp_path / 'job'
    shutil.copytree(modelo['job'], destino)
    return destino


def _familia_de(conteudo, fid):
    return next(g for g, f in conteudo['familias'].items() if fid in f['formatos'])


def _titulo(conteudo, gid):
    base = conteudo['editar']({'familia': gid, 'versao': None, 'edicoes': []})
    return next(e['id'] for e in base['membros'][0]['palco']['elementos'] if e['funcao'] == 'titulo')


def _editar(job, texto, fid='mesma', versao=None, edicoes=None):
    """Grava o briefing do DA com o texto editado na familia de fid (as outras confirmadas sem edicao) e deriva."""
    conteudo = te.montar(job)
    gid = _familia_de(conteudo, fid)
    el = _titulo(conteudo, gid)
    comps = []
    for g, f in conteudo['familias'].items():
        ed = (edicoes if edicoes is not None else [{'elemento': el, 'acao': 'texto', 'texto': texto}]) if g == gid else []
        comps.append({'familia': g, 'formatos': f['formatos'], 'versao': versao if g == gid else None, 'edicoes': ed,
                      'confirmada': True, 'confirmacao': dict(CONF)})
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    b['cabecalho'].update(origem='da', meio='terminal')
    b['composicoes'] = comps
    contratos.gravar(job / mb.ARQUIVO, b, 'briefing/1')
    nd.derivar(job)
    return el


def _deriv(job, fid):
    return contratos.ler(job / nd.PASTA / ('%s.json' % fid), nd.ESQUEMA)


def _entrada_editada(contrato, layer_id):
    return next(e for e in contrato['entradas'] if e['tipo'] == 'texto' and e['layer_id'] == layer_id)


def _linhas(entrada):
    return [''.join(s for s, _r in ln['pedacos']) for ln in rt.linhas_da_camada(
        entrada['texto'], set(entrada.get('quebras_automaticas') or ()), entrada.get('quebras_juntadas'))]


# ------------------------------------------------------------------ derivacao e contrato
def test_derivacao_nao_junta_as_quebras_da_proposta_ao_texto_editado(job, modelo):
    # sem edicao, a familia leva as quebras aprovadas da proposta derivada (o titulo de duas linhas)
    el = _editar(job, None, edicoes=[])
    antes = next(e for e in _deriv(job, 'mesma')['elementos'] if e['id'] == el)
    _editar(job, DUAS_LINHAS)
    d = _deriv(job, 'mesma')
    x = next(e for e in d['elementos'] if e['id'] == el)
    assert x['texto_editado'] == DUAS_LINHAS and x['origem_geometria'] == 'da'
    # o texto do DA leva so as quebras dele: nenhuma quebra da proposta fica no elemento editado
    assert antes['quebras'] != 'do_texto_editado'
    assert x['quebras'] == 'do_texto_editado' and 'quebras_camada' not in x, x.get('quebras')


def test_contrato_leva_o_texto_editado_num_trecho_so(job, modelo):
    el = _editar(job, DUAS_LINHAS)
    contrato, bloqueios, _c = rd.montar(job, 'mesma')
    assert bloqueios == [], bloqueios
    e = _entrada_editada(contrato, modelo['layer_id'])
    assert e['texto_editado'] is True and e['elemento'] == el
    assert [r['texto'] for r in e['texto']['runs']] == [DUAS_LINHAS]
    assert e['texto']['runs'][0]['inicio'] == 0 and e['texto']['runs'][0]['fim'] == len(DUAS_LINHAS)
    assert list(e['cores_por_trecho']) == ['0'] and e['cores'] == [e['cores_por_trecho']['0']]
    assert 'quebras_juntadas' not in e and 'quebras_inseridas' not in e
    # a largura da quebra e a da caixa de tinta da camada no espaco do texto (a mesma largura da previa)
    laudo = contratos.ler(job / mb.ARQUIVO_LAUDO, 'laudo/1')
    ct = mb.camadas_do_laudo(laudo)[modelo['layer_id']]['geometria']['caixa_tinta']
    assert e['largura_quebra'] == pytest.approx((ct[2] - ct[0]) / tp.ESCALA_DUAS, abs=1e-6)
    # a tinta do texto novo e conferida na borda do formato: a pagina cobre o formato inteiro, sem corte calado
    W, H = contrato['formato']['largura'], contrato['formato']['altura']
    assert e['regiao'] == [0, 0, W, H] and e['caixa_validada'] == [0, 0, W, H]
    assert any(r['codigo'] == 'texto_editado_desenhado' and r['layer_id'] == modelo['layer_id']
               for r in contrato['registros'])
    contratos.validar(contrato, 'composicao/1')
    # o texto vale so na familia editada (171): o outro formato desenha o texto do KV
    outro, b2, _c2 = rd.montar(job, 'perto')
    assert b2 == [] and not _entrada_editada(outro, modelo['layer_id']).get('texto_editado')


def test_caractere_fora_do_cmap_e_recusado_no_contrato(job, modelo):
    # o briefing que chega sem passar pela tela (arquivo mexido) tambem e conferido: a fonte de autoteste nao tem o Ç
    el = _editar(job, 'HAÇ\nHOX')
    contrato, bloqueios, _c = rd.montar(job, 'mesma')
    assert contrato is None
    assert [b['codigo'] for b in bloqueios] == ['texto_editado_fora_da_fonte']
    assert bloqueios[0]['medidas'] == {'elementos': [el], 'caracteres': ['Ç']}
    texto = bloqueios[0]['descricao']
    assert 'fonte' in texto and '—' not in texto and '–' not in texto


def test_texto_editado_sem_bloqueio_antigo():
    assert 'texto_editado_sem_render' not in rd.DESCRICOES


def test_tinta_do_texto_editado_cortada_na_borda_do_formato_reprova():
    e = {'id': 'e01', 'tipo': 'texto', 'layer_id': 7, 'regiao': [0, 0, 100, 50], 'caixa_validada': [0, 0, 100, 50],
         'texto_editado': True}
    st = {'id': 'e01', 'tipo': 'texto', 'tinta': [10, 10, 100, 40], 'toca_regiao': ['dir']}
    assert [x['cortada_na_regiao'] for x in rd.tinta_fora_da_caixa([e], [st], 100, 50)] == [['dir']]
    assert rd.tinta_fora_da_caixa([e], [dict(st, toca_regiao=[])], 100, 50) == []


# ------------------------------------------------------------------ no Chromium: as linhas
def _texto_no_chromium(job, contrato):
    estado = contratos.ler(job / 'estado.json', 'estado/1')
    servidos = execucao.bytes_das_faces(job, contrato, estado)
    return execucao.texto_no_chromium(contrato, servidos, 'dsd-teste')


def _avanco(s, corpo):
    return sum(AVANCOS[c] for c in s) / EM * corpo


def test_texto_com_quebra_sai_exatamente_nas_linhas_pedidas(job, modelo):
    _editar(job, DUAS_LINHAS)
    contrato, _b, _c = rd.montar(job, 'mesma')
    pdfs, paginas, cdp, _cache, _v = _texto_no_chromium(job, contrato)
    e = _entrada_editada(contrato, modelo['layer_id'])
    assert _linhas(e) == ['HAH', 'HOX']
    assert cdp['diverge'] == 0 and cdp['faces_nao_carregadas'] == 0
    assert any(p['entrada'] == e['id'] for p in paginas)


def test_linha_mais_larga_que_a_caixa_quebra_no_espaco(job, modelo):
    _editar(job, REFLOW)
    contrato, _b, _c = rd.montar(job, 'mesma')
    e = _entrada_editada(contrato, modelo['layer_id'])
    corpo = e['texto']['runs'][0]['corpo_espaco_texto']
    largura = e['largura_quebra']
    palavra = REFLOW.split(' ')[0]
    # duas palavras cabem na largura da caixa, tres nao: a terceira desce
    assert _avanco(palavra + ' ' + palavra, corpo) < largura < _avanco(REFLOW, corpo)
    _texto_no_chromium(job, contrato)
    assert _linhas(e) == [palavra + ' ' + palavra, palavra]


# ------------------------------------------------------------------ o render e a previa da tela
@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
def test_tinta_do_render_bate_com_a_previa_da_tela(job, modelo, monkeypatch):
    from playwright.sync_api import sync_playwright

    import test_tela_edicao as ted
    import test_tela_galeria as tg
    from desdobra.chromium import navegador
    from desdobra.tela import atos as ta
    from desdobra.tela import rascunho as tr
    from desdobra.tela import servidor as ts
    conteudo = te.montar(job)
    gid = _familia_de(conteudo, 'mesma')
    el = _titulo(conteudo, gid)
    navegador.apontar_playwright()
    with ts.ServidorTela(conteudo, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo)) as srv, sync_playwright() as pw:
        nav, pg = tp._pagina_da_tela(pw, srv, 1600, 900)  # numero-neutro: janela do teste
        try:
            tg._abrir(pg, conteudo['estado'], 'mesma')
            ted._focar(pg, el)
            pg.keyboard.press('Enter')
            pg.evaluate('() => document.getElementById("ed-texto").click()')
            pg.fill('#ed-campo-texto', DUAS_LINHAS)
            pg.evaluate('() => document.getElementById("ed-texto-aplicar").click()')
            tp._esperar(pg, '() => document.getElementById("editor-texto").hidden ? "1" : ""')
            ted._esperar_salvo(pg)
            tp._esperar(pg, '() => (document.querySelector("#palco .texto.editado") || {dataset: {}}).dataset'
                            '.caixaTinta ? "1" : ""')
            previa = [float(x) for x in pg.evaluate(
                '() => document.querySelector("#palco .texto.editado").dataset.caixaTinta').split(',')]
            linhas_previa = pg.evaluate('() => Array.from(document.querySelectorAll("#palco .texto.editado .linha"))'
                                        '.map(l => l.textContent)')
        finally:
            nav.close()
    assert linhas_previa == DUAS_LINHAS.split('\n')
    f = json.loads((job / tr.ARQUIVO).read_text(encoding='utf-8'))['familias'][gid]
    assert [x['texto'] for x in f['edicoes'] if x['acao'] == 'texto'] == [DUAS_LINHAS]
    _editar(job, None, versao=f['versao'], edicoes=f['edicoes'])
    monkeypatch.setattr(humano, 'console_interativo', lambda: (True, None))
    # a caixa TySh do PSD sintetico nao confere com a largura da fonte de autoteste: decisao do DA, aceita no teste
    rel = execucao.renderizar(job, disparo=humano.exigir('render'), formato='mesma', aceites=('largura_divergente',))
    contrato = contratos.ler(job / 'render' / 'mesma' / 'contrato.json', 'composicao/1')
    e = _entrada_editada(contrato, modelo['layer_id'])
    assert [x['linhas'] for x in rel['textos']['editados'] if x['entrada'] == e['id']] == [DUAS_LINHAS.split('\n')]
    tinta = next(s['tinta'] for s in rel['entradas'] if s['id'] == e['id'])
    # a tolerancia da tinta do texto do render (render.tolerancia_tinta_texto, com o piso em px): a mesma que confere
    # a tinta contra a caixa validada
    tol = rd._tolerancia_tinta(previa)
    assert tinta == pytest.approx(previa, abs=tol), (tinta, previa, tol)
    # o render nao tirou nada da pagina: a tinta nao encosta na borda do formato
    assert rel['textos']['camadas'] >= 1 and all(s['toca_regiao'] == [] for s in rel['entradas'] if s['id'] == e['id'])
