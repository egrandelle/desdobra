# -*- coding: utf-8 -*-
"""M7a3: o palco so de leitura da tela de briefing.

Criterios de pronto cobertos aqui (proposta do M7, secao 4, fatia a3; secao 3, linhas Texto do cliente na pagina,
@font-face, Caixa de tinta do texto, Palco, Agrupamento por orientacao; decisoes-v1.md n 157, 161 e 162):
  - passo 1 "O que eu li" (bloqueios, linkados, valores de spec, modo de dados) e passo 2 "Funcoes" (arvore dos
    grupos com a funcao e a heranca, KV no centro), so de leitura;
  - abas por orientacao e, dentro dela, uma miniatura por grupo de composicoes de proporcao parecida (revisao da 163 em
    05/11), desenhada do mesmo modelo do palco, com os arquivos de saida como fichas; a escala pura e o formato
    devolvido levam o selo deles, e o devolvido aparece com o motivo em portugues, sem pedir mestre propria (n 164);
  - nenhum identificador do motor no texto da moldura (redesenho de 05/11); os botoes do M7a ("Confirmar composicao",
    "Salvar e seguir") aparecem desligados, com a dica de que chegam na proxima versao;
  - o palco desenha a derivacao do motor em pixel real: cada camada pelo asset por id ou pelo texto com a fonte do job
    (@font-face pela rota da fonte, sem local()), com a tinta medida no Chromium; a primeira tentativa do solver leva
    "proposta, nao aprovada"; elemento sem regra e o formato devolvido aparecem hachurados como "apoio de desenho, nao
    gravado";
  - um contador unico "faltam N";
  - nome de camada hostil ("<form action=/api/aprovar>", "<img onerror=...>") aparece como texto;
  - o palco desenha a fonte de autoteste do motor e o CDP confirma isCustomFont, com o nome de familia dela;
  - nenhum pedido sai de 127.0.0.1; nada e gravado no job.

Tudo e sintetico: o PSD montado aqui com o psd-tools, a fonte de autoteste do motor (gerada pelo fontTools num
processo filho) e briefings de teste. Os testes do modelo rodam sem navegador; o do palco roda no Chromium sem janela
(o modo de teste: a propriedade testada nao pede janela); o ultimo abre a janela de verdade e fecha pelo CDP.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

import test_derivacao_apoio as ap
import test_fontes_apoio as fap
import test_render_apoio as rap
from conftest import RAIZ_PLUGIN
from desdobra import limites
from desdobra.derivacao import escala
from desdobra.derivacao import nucleo as nd
from desdobra.tela import estado as te
from desdobra.tela import estatico
from desdobra.tela import servidor as ts

NOME_FORM = '<form action=/api/aprovar>'
NOME_IMG = '<img src=x onerror="document.title=1">'
NOME_APOIO = 'texto <b>apoio</b>'
SELO_APOIO = 'apoio de desenho, não gravado'
SELO_PROPOSTA = 'proposta, não aprovada'
PASTA_TELA = RAIZ_PLUGIN / 'tela'


# ------------------------------------------------------------------ geradores
def _psd_hostil(destino, ps):
    """PSD 320 x 160: fundo, grupo de titulo com nome de formulario (texto com nome de imagem e uma linha), logo,
    texto de apoio com nome de HTML e um quadrado solto. Os textos usam so os glifos da fonte de autoteste."""
    from PIL import Image
    from psd_tools import PSDImage
    p = PSDImage.new('RGB', (320, 160), color=(255, 255, 255))
    p.create_pixel_layer(Image.new('RGBA', (320, 160), (240, 236, 220, 255)), name='fundo-sintetico')
    g = p.create_group(name=NOME_FORM)
    t1 = g.create_pixel_layer(Image.new('RGBA', (200, 30), (20, 20, 20, 255)), name=NOME_IMG, top=20, left=10)
    fap._virar_texto(t1, [('HOAX', 0, 28.0, 0)], [ps], fap.largura('HOAX', 28.0, avancos=AVANCOS), x=12.0, y=44.0)
    g.create_pixel_layer(Image.new('RGBA', (100, 4), (30, 30, 120, 255)), name='linha-sintetica', top=56, left=12)
    p.create_pixel_layer(Image.new('RGBA', (40, 40), (0, 120, 60, 255)), name='quadrado-sintetico', top=100, left=260)
    t2 = p.create_pixel_layer(Image.new('RGBA', (200, 30), (20, 20, 20, 255)), name=NOME_APOIO, top=110, left=10)
    fap._virar_texto(t2, [('VOX AH', 0, 20.0, 0)], [ps], fap.largura('VOX AH', 20.0, avancos=AVANCOS), x=20.0, y=130.0)
    p.create_pixel_layer(Image.new('RGBA', (20, 20), (220, 0, 0, 255)), name='solto-sintetico', top=70, left=200)
    return rap._salvar(p, destino)


# avancos dos glifos da fonte de autoteste (desdobra.render.autoteste.FILHO_FONTE): a caixa TySh confere com o Chromium
AVANCOS = {'H': 680, 'O': 760, 'A': 700, 'V': 700, 'X': 680, ' ': 500}
# largo: o 2048x720 dos KV do corpus (proposta do M7, secao 5; decisoes-v1.md, 157: o palco legivel no 2048x720)
FORMATOS = [('mesma', 640, 320), ('perto', 400, 240), ('vertical', 160, 320), ('largo', 2048, 720)]


def _fotografia(pasta):
    return {str(p.relative_to(pasta)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path(pasta).rglob('*') if p.is_file()}


@pytest.fixture(scope='module')
def job_palco(tmp_path_factory):
    """Job sintetico com a fonte de autoteste do motor, nomes de camada hostis e o briefing de teste."""
    from desdobra import contratos
    from desdobra.briefing import modelo as mb
    from desdobra.job import nucleo
    from desdobra.render import autoteste
    base = tmp_path_factory.mktemp('palco')
    fontes = base / 'origem-fontes'
    fap.gravar(fontes, 'autoteste.ttf', autoteste.gerar_fonte())
    job = base / 'job'
    nucleo.criar(job, _psd_hostil(base / 'origem' / 'kv.psd', autoteste.NOME_PS), 'c', fontes=[fontes])
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    ids = {c['nome']: c['identidade']['layer_id'] for c in laudo['camadas']}
    funcoes = {ids['fundo-sintetico']: 'fundo', ids[NOME_FORM]: 'titulo', ids['quadrado-sintetico']: 'logo_principal',
               ids[NOME_APOIO]: 'texto_de_apoio', ids['solto-sintetico']: 'fora_da_peca'}
    b = ap.briefing(funcoes=funcoes, formatos=[ap.formato(i, w, h) for i, w, h in FORMATOS])
    b.pop('cabecalho')
    b.pop('job_id')
    arq = base / 'fixture.json'
    arq.write_text(json.dumps(b), encoding='utf-8')
    mb.importar_teste(job, arq)
    return job


# ------------------------------------------------------------------ modelo do palco, sem navegador
def test_resumo_aceita_ancora_por_elemento():
    # achado ao abrir a tela nos jobs do corpus: a ancora pode ser por funcao ou por elemento (layer_id, sem funcao)
    def decisao(v):
        return {'valor': v, 'situacao': 'confirmado', 'origem': 'da'}
    b = ap.briefing()
    b['ancoras'] = [{'funcao': 'titulo', 'x': decisao('esquerda'), 'y': decisao('topo')},
                    {'layer_id': 7, 'x': decisao('centro'), 'y': decisao('base')}]
    resolvidas = {3: {'funcao': 'titulo'}, 7: {'funcao': 'logo'}, 8: {'funcao': 'logo'}}
    r = {x['funcao']: x for x in te.resumo_das_funcoes(b, resolvidas)}
    assert r['titulo']['ancora'] == ['esquerda', 'topo'] and r['titulo']['ancoras_por_elemento'] == 0
    assert r['logo']['ancora'] is None and r['logo']['ancoras_por_elemento'] == 1


def test_palco_compoe_cada_camada_pela_transformacao_do_motor():
    b, laudo = ap.briefing(), ap.laudo()
    r = nd.derivar_em_memoria(nd.contexto(laudo, b))
    base = te.pecas_base(laudo, {}, lambda ps: None)
    d = r['formatos']['perto']
    p = te.palco(d, r['kv'], laudo, base)
    assert (p['largura'], p['altura'], p['caminho'], p['selo']) == (480, 300, 'solver', 'proposta')
    assert not p['devolucao']
    por_el = {e['id']: e for e in d['elementos']}
    assert {e['id'] for e in p['elementos']} == set(por_el)
    assert all(not e['fantasma'] for e in p['elementos'])
    # cada peca: destino + (caixa da camada - origem) * s, no recorte do elemento
    for peca in p['pecas']:
        tr = por_el[peca['elemento']]['transformacao']
        cx = laudo['camadas'][[c['identidade']['layer_id'] for c in laudo['camadas']].index(peca['camada'])]
        caixa = cx['geometria']['caixa']
        s, (ox, oy), (dx, dy) = tr['s'], tr['origem_doc'], tr['destino']
        esperado = [dx + (caixa[0] - ox) * s, dy + (caixa[1] - oy) * s, dx + (caixa[2] - ox) * s,
                    dy + (caixa[3] - oy) * s]
        assert peca['caixa'] == pytest.approx(esperado, abs=1e-3), peca
        rec = tr['recorte_doc']
        assert peca['recorte'] == pytest.approx([dx + (rec[0] - ox) * s, dy + (rec[1] - oy) * s,
                                                 dx + (rec[2] - ox) * s, dy + (rec[3] - oy) * s], abs=1e-3)
    # o fundo cover sangra: o mundo desenhado passa do quadro (extensao da foto alem do quadro)
    assert p['mundo'][0] < 0 and p['fora_do_quadro'] is True
    # as pecas vem na ordem do laudo (de baixo para cima)
    ordem = [c['identidade']['layer_id'] for c in laudo['camadas']]
    assert [ordem.index(x['camada']) for x in p['pecas']] == sorted(ordem.index(x['camada']) for x in p['pecas'])
    json.dumps(p)


def test_escala_pura_e_devolvido_com_fantasmas_na_escala_pura_da_mestre():
    b, laudo = ap.briefing(), ap.laudo()
    r = nd.derivar_em_memoria(nd.contexto(laudo, b))
    base = te.pecas_base(laudo, {}, lambda ps: None)
    mesmo = te.palco(r['formatos']['mesmo'], r['kv'], laudo, base)
    assert mesmo['selo'] == 'escala_pura' and mesmo['caminho'] == 'transform'
    vert = te.palco(r['formatos']['vertical'], r['kv'], laudo, base)
    assert vert['selo'] == 'devolvido' and vert['devolucao']['motivo'] == 'troca_forte_de_orientacao'
    assert vert['devolucao']['o_que_fazer']
    # devolvido: os elementos do KV como apoio de desenho, na escala pura da mestre (contain e centrado)
    assert vert['elementos'] and all(e['fantasma'] for e in vert['elementos'])
    W, H, Wm, Hm = 300, 600, 400, 200
    s = min(W / Wm, H / Hm)
    fundo = next(e for e in vert['elementos'] if e['funcao'] == 'fundo')
    assert fundo['caixa'] == pytest.approx([0, (H - Hm * s) / 2, W, (H + Hm * s) / 2], abs=1e-3)


def test_elemento_sem_regra_e_fantasma_e_nada_vira_valor():
    regras = dict(ap.REGRAS)
    del regras['titulo']
    b, laudo = ap.briefing(regras=regras), ap.laudo()
    r = nd.derivar_em_memoria(nd.contexto(laudo, b))
    base = te.pecas_base(laudo, {}, lambda ps: None)
    p = te.palco(r['formatos']['perto'], r['kv'], laudo, base)
    titulo = next(e for e in p['elementos'] if e['funcao'] == 'titulo')
    assert titulo['fantasma'] is True and titulo['regra'] is None
    # o modelo do palco nao inventa regra nem ancora para quem nao tem
    assert all(e['regra'] is None for e in p['elementos'] if e['fantasma'] and e['funcao'] == 'titulo')


def test_abas_com_escala_pura_e_rotulos_das_familias():
    formatos = [ap.formato('mesmo', 800, 400), ap.formato('perto', 480, 300), ap.formato('vertical', 300, 600)]
    b = ap.briefing(formatos=formatos)
    laudo = ap.laudo()
    r = nd.derivar_em_memoria(nd.contexto(laudo, b))
    abas = te.abas(laudo, b, r['formatos'])
    grupos = abas[0]['grupos']
    assert [g['escala_pura'] for g in grupos] == [True, False]
    assert {c['rotulo_familia'] for g in grupos for c in g['composicoes']} == {'Mestre do KV'}
    assert abas[-1]['grupos'][0]['composicoes'][0]['rotulo_familia'] == 'Sem proposta ainda'
    # a mestre propria nao mostra o id dela
    assert te._rotulo_familia('m2', {'tipo': 'propria'}) == 'Mestre própria'


def test_devolvido_na_tela_nao_pede_mestre_propria_nem_mostra_identificador():
    for motivo in list(te.MOTIVOS_TELA) + ['restricao_obrigatoria_nao_fecha', None]:
        t = te.texto_da_devolucao(motivo)
        assert t and 'mestre própria' not in t and not re.search(r'[a-z]+_[a-z]+', t), (motivo, t)
    b, laudo = ap.briefing(formatos=[ap.formato('vertical', 300, 600)]), ap.laudo()
    r = nd.derivar_em_memoria(nd.contexto(laudo, b))
    vert = te.palco(r['formatos']['vertical'], r['kv'], laudo, te.pecas_base(laudo, {}, lambda ps: None))
    assert vert['devolucao']['texto'] == te.texto_da_devolucao('troca_forte_de_orientacao')


def test_tela_nao_diz_volta_ao_da_e_da_nome_a_toda_funcao():
    # decisao 164: nenhum formato volta ao DA; a tela nunca diz isso ao designer
    js = (PASTA_TELA / 'tela.js').read_text(encoding='utf-8')
    textos = [js, (PASTA_TELA / 'tela.html').read_text(encoding='utf-8')] + [str(v) for v in te.ROTULOS.values()]
    assert not any(re.search(r'volta ao DA', t, re.IGNORECASE) for t in textos)
    # toda funcao do briefing tem nome com acento na tela, nunca o id cru com o sublinhado trocado
    from desdobra.briefing import modelo as mb
    bloco = re.search(r'const FUNCOES = \{(.*?)\};', js, re.DOTALL).group(1)
    chaves = set(re.findall(r'([a-z_]+):', bloco))
    assert set(mb.CLASSES) <= chaves, sorted(set(mb.CLASSES) - chaves)
    assert "titulo: 'título'" in bloco


def test_textos_da_tela_sem_travessao_e_sem_html_de_cliente():
    arqs = {n: (PASTA_TELA / n).read_text(encoding='utf-8') for n in ('tela.html', 'tela.css', 'tela.js')}
    servidos = estatico.arquivos()
    assert servidos['/'][0].decode('utf-8') == arqs['tela.html']
    assert servidos['/tela.js'][0].decode('utf-8') == arqs['tela.js']
    assert servidos['/tela.css'][0].decode('utf-8') == arqs['tela.css']
    for nome, texto in arqs.items():
        assert '—' not in texto and '–' not in texto, nome
        assert not re.search(r'não é [^,.]{1,40}, é ', texto), nome
        # nada externo: sem CDN, sem URL absoluta, sem local()
        assert not re.search(r'https?://|//[a-z0-9]', texto.replace('http://www.w3.org', '')), nome
        assert 'local(' not in texto, nome
    js = arqs['tela.js']
    for proibido in ('innerHTML', 'outerHTML', 'insertAdjacentHTML', 'document.write', 'eval(', 'new Function',
                     'setAttribute(\'on', 'srcdoc', 'method: \'POST\'', 'method:\'POST\''):
        assert proibido not in js, proibido
    html = arqs['tela.html']
    assert '<script src="/tela.js"' in html and '<style' not in html
    assert not re.search(r'<[^>]+\son[a-z]+=', html)
    for t in (te.ROTULOS.values()):
        assert '—' not in t and '–' not in t


def test_montar_no_job_sintetico_sem_gravar_nada(job_palco):
    antes = _fotografia(job_palco)
    c = te.montar(job_palco)
    assert _fotografia(job_palco) == antes
    e = c['estado']
    assert e['somente_leitura'] is True
    # passo 1: o que o motor leu
    lido = e['lido']
    assert lido['modo_dados'] == {'job': 'c', 'teto': None, 'briefing': 'c'}
    assert isinstance(lido['bloqueios'], list) and lido['linkados'] == []
    assert set(lido['specs']) >= {'confirmados', 'rascunhos', 'divergentes', 'registros', 'formatos'}
    assert [f['id'] for f in lido['fontes']] == ['f01'] and lido['fontes_que_faltam'] == []
    # passo 2: a arvore de funcoes, com a heranca do grupo
    arvore = e['funcoes']['arvore']
    nos = {}

    def andar(lista):
        for n in lista:
            nos[n['nome']] = n
            andar(n['filhos'])
    andar(arvore)
    assert nos[NOME_FORM]['funcao'] == 'titulo' and nos[NOME_FORM]['por'] == 'camada'
    assert nos[NOME_IMG]['funcao'] == 'titulo' and nos[NOME_IMG]['por'] == 'grupo'
    assert nos[NOME_IMG]['raiz'] == nos[NOME_FORM]['camada']
    assert nos['solto-sintetico']['funcao'] == 'fora_da_peca'
    resumo = {x['funcao']: x for x in e['funcoes']['resumo']}
    assert resumo['titulo']['regra'] == 'raiz_area' and resumo['titulo']['ancora'] == ['esquerda', 'topo']
    assert e['funcoes']['palco_kv']['selo'] == 'kv'
    # as abas e as previas
    assert [o['id'] for o in e['orientacoes']] == ['horizontal', 'vertical']
    assert set(c['previas']) == {'mesma', 'perto', 'vertical', 'largo'}
    perto = c['previas']['perto']
    textos = [p for p in perto['pecas'] if p['tipo'] == 'texto']
    assert len(textos) == 2 and all(p['modo'] == 'texto' for p in textos)
    hoax = next(p for p in textos if p['nome'] == NOME_IMG)
    assert [[t['texto'] for t in ln['trechos']] for ln in hoax['linhas']] == [['HOAX']]
    assert hoax['linhas'][0]['trechos'][0]['face'] == 'f01'
    s = next(x for x in perto['elementos'] if x['id'] == hoax['elemento'])['escala']
    assert hoax['linhas'][0]['trechos'][0]['corpo'] == pytest.approx(28.0 * s, abs=1e-3)
    imagens = [p for p in perto['pecas'] if p['tipo'] == 'imagem']
    assert imagens and all(ts.ID_ASSET.match(p['asset']) and p['asset'] in c['assets'] for p in imagens)
    assert all(dados.startswith(te.ASSINATURA_PNG) for dados, _t in c['assets'].values())
    # faltam N: o formato devolvido conta e leva a aba dele
    faltam = e['faltam']
    assert any(f['ir'].get('formato') == 'vertical' for f in faltam)
    json.dumps(e)


# ------------------------------------------------------------------ palco no Chromium sem janela (modo de teste)
JS_PRONTO = '() => document.documentElement.dataset.pronto || ""'


def _esperar(pg, expressao, valor='1', teto_s=60):
    fim = time.monotonic() + teto_s
    while True:
        v = pg.evaluate(expressao)
        if v == valor:
            return
        if v == 'erro' or time.monotonic() > fim:
            raise AssertionError('a pagina nao ficou pronta: %r %r' % (v, pg.evaluate('() => document.body.innerText')))
        time.sleep(0.1)  # numero-neutro: intervalo do teste


def _textos(pg, seletor):
    return pg.evaluate('s => Array.from(document.querySelectorAll(s)).map(e => e.textContent)', seletor)


def _clicar_aba(pg, nivel, inicio):
    pg.evaluate('([n, t]) => Array.from(document.querySelectorAll("#" + n + " [role=tab]"))'
                '.find(b => b.textContent.startsWith(t)).click()', [nivel, inicio])
    _esperar(pg, '() => document.getElementById("palco").dataset.pronto || ""')


def _clicar_grupo(pg, gid):
    pg.evaluate('g => document.querySelector(\'#composicoes [data-grupo="\' + g + \'"]\').click()', gid)
    _esperar(pg, '() => document.getElementById("palco").dataset.pronto || ""')


def _medidas_das_abas(pg):
    return _textos(pg, '#composicoes [role=tab] .mini-medidas')


def _no_palco(pg):
    return pg.evaluate('() => document.getElementById("palco").dataset.formato || ""')


def _onde(estado, fid):
    """(orientacao, grupo, composicao) do formato `fid` no modelo das abas."""
    for o in estado['orientacoes']:
        for g in o['grupos']:
            for co in g['composicoes']:
                if any(x['id'] == fid for x in co['formatos']):
                    return o, g, co
    raise AssertionError(fid)


# texto da moldura que o DA le: textContent, aria-label e title, fora o texto do cliente (nomes de camada, nome de
# arquivo e de fonte, o texto do PSD no palco), que e dado
JS_TEXTO_DA_MOLDURA = """() => {
  const fora = new Set(['nome', 'trecho', 'etiqueta', 'ficha-nome', 'nome-palco', 'nome-formato', 'rotulo-fonte',
                        'nome-fonte', 'detalhe-item']);
  const partes = [];
  const andar = (no) => {
    if (no.nodeType === 3) { partes.push(no.nodeValue); return; }
    if (no.nodeType !== 1) return;
    if (Array.from(no.classList).some(c => fora.has(c))) return;
    if (no.tagName === 'SCRIPT') return;
    for (const a of ['aria-label', 'title']) if (no.getAttribute(a)) partes.push(no.getAttribute(a));
    no.childNodes.forEach(andar);
  };
  andar(document.body);
  return partes.join(' ');
}"""
IDENTIFICADOR = re.compile(r'[a-z]+_[a-z]+|layer|\bel\d+\b|\bf\d\d\b|\b(?:contain|cover)\b', re.IGNORECASE)


def _cdp_fontes(ctx, pg, seletor):
    cdp = ctx.new_cdp_session(pg)
    cdp.send('DOM.enable')
    cdp.send('CSS.enable')
    raiz = cdp.send('DOM.getDocument', {'depth': -1})['root']['nodeId']
    no = cdp.send('DOM.querySelector', {'nodeId': raiz, 'selector': seletor})['nodeId']
    assert no, seletor
    return cdp.send('CSS.getPlatformFontsForNode', {'nodeId': no})['fonts']


def test_palco_no_chromium_sem_janela(job_palco):
    from playwright.sync_api import sync_playwright

    from desdobra.chromium import navegador
    from desdobra.render import autoteste
    antes = _fotografia(job_palco)
    conteudo = te.montar(job_palco)
    navegador.apontar_playwright()
    pedidos = []
    with ts.ServidorTela(conteudo) as srv, sync_playwright() as pw:
        nav = pw.chromium.launch(headless=True, args=list(navegador.ARGUMENTOS))
        try:
            ctx = nav.new_context(viewport={'width': 2048, 'height': 720}, device_scale_factor=1)  # numero-neutro: janela de 2048x720, a medida do formato da decisao 157 (a janela de verdade abre maximizada)
            pg = ctx.new_page()
            pg.on('request', lambda r: pedidos.append(r.url))
            try:
                pg.goto(srv.url_entrada, wait_until='commit')
            except Exception:  # noqa: BLE001 - o 204 nao completa a navegacao
                pass
            pg.goto(srv.url_pagina, wait_until='load')
            _esperar(pg, JS_PRONTO)
            # contador unico
            n = len(conteudo['estado']['faltam'])
            assert pg.evaluate('() => document.getElementById("faltam").textContent') == \
                ('Falta 1' if n == 1 else 'Faltam %d' % n)
            # passo 2: os nomes hostis aparecem como texto, sem virar elemento
            pg.evaluate('() => document.querySelector("#passos [data-passo=funcoes]").click()')
            corpo = pg.evaluate('() => document.body.innerText')
            assert NOME_FORM in corpo and NOME_IMG in corpo and NOME_APOIO in corpo
            assert 'do grupo' in corpo
            assert pg.evaluate('() => document.querySelectorAll("form, b, [onerror]").length') == 0
            assert pg.evaluate('() => document.title') != '1'
            assert pg.evaluate('() => document.querySelectorAll("#palco-kv .peca").length') > 0
            # nada de identificador cru do motor na regra e no tipo (revisao do M7a0)
            pg.evaluate('() => document.querySelector("#arvore button").click()')
            corpo = pg.evaluate('() => document.body.innerText')
            assert not [r for r in escala.REGRAS if re.search(r'(?<![\w-])%s(?![\w-])' % r, corpo)], corpo
            assert not re.search(r'smart_|cor_solida', corpo)
            # o passo Design system: o resumo so de leitura das regras e ancoras (decisoes-v1.md, 161)
            pg.evaluate('() => document.querySelector("#passos [data-passo=design]").click()')
            assert pg.evaluate('() => document.querySelectorAll("#resumo-design tr").length') == \
                len(conteudo['estado']['funcoes']['resumo']) + 1
            assert not pg.evaluate('() => document.getElementById("passo-design").hidden')
            # as abas: orientacao e uma miniatura por grupo de proporcao, do mais largo ao mais perto do quadrado
            pg.evaluate('() => document.querySelector("#passos [data-passo=pecas]").click()')
            _esperar(pg, '() => document.getElementById("palco").dataset.pronto || ""')
            assert [t.split(' ')[0] for t in _textos(pg, '#orientacoes [role=tab]')] == ['Horizontal', 'Vertical']
            assert _medidas_das_abas(pg) == ['2048x720', '640x320', '400x240']
            # cada miniatura desenha o quadro do mesmo modelo do palco
            _esperar(pg, '() => Array.from(document.querySelectorAll("#composicoes .mini-palco"))'
                         '.every(m => m.querySelector(".peca")) ? "1" : ""')
            selos = _textos(pg, '#composicoes .mini-selo')
            assert selos == ['Proposta', 'Escala pura', 'Proposta'], selos
            _o, g, _co = _onde(conteudo['estado'], 'mesma')
            _clicar_grupo(pg, g['id'])
            assert _no_palco(pg) == 'mesma'
            assert 'Escala pura' in pg.evaluate('() => document.getElementById("selo-palco").textContent')
            assert pg.evaluate('() => document.querySelectorAll("#composicoes [aria-selected=true]").length') == 1
            _o, g, _co = _onde(conteudo['estado'], 'perto')
            _clicar_grupo(pg, g['id'])
            assert 'perto' in ' '.join(_textos(pg, '#fichas .ficha'))
            assert _no_palco(pg) == 'perto'
            assert SELO_PROPOSTA in pg.evaluate('() => document.getElementById("selo-palco").textContent')
            # o texto do palco: fonte de autoteste do motor, propria (CDP), e tinta medida
            faces = _cdp_fontes(ctx, pg, '#palco .texto .trecho')
            assert faces and all(f.get('isCustomFont') for f in faces), faces
            assert {f.get('familyName') for f in faces} == {autoteste.FAMILIA}
            tintas = pg.evaluate('() => Array.from(document.querySelectorAll("#palco .texto"))'
                                 '.map(t => t.dataset.tinta || "")')
            assert len(tintas) == 2 and all(t for t in tintas), tintas
            for t in tintas:
                largura, altura = (float(x) for x in t.split(','))
                assert largura > 0 and altura > 0
            assert pg.evaluate('() => document.querySelectorAll("#palco img.peca").length') > 0
            # o palco cabe na area em 2048 x 720, sem rolagem lateral da pagina
            assert pg.evaluate('() => document.documentElement.scrollWidth') <= 2048  # numero-neutro: largura da tela
            caixa = pg.evaluate('() => { const r = document.querySelector("#palco .moldura").getBoundingClientRect();'
                                ' return [r.left, r.top, r.right, r.bottom]; }')
            assert caixa[2] <= 2048 and caixa[3] <= 720, caixa  # numero-neutro: a tela do Duda
            # o 2048x720: a peca inteira cabe na janela de 2048 x 720, sem rolagem
            o, g, _co = _onde(conteudo['estado'], 'largo')
            _clicar_aba(pg, 'orientacoes', o['rotulo'])
            _clicar_grupo(pg, g['id'])
            pg.evaluate('() => document.querySelector(\'.ficha[data-formato="largo"]\').click()')
            _esperar(pg, '() => document.getElementById("palco").dataset.pronto || ""')
            assert _no_palco(pg) == 'largo'
            assert pg.evaluate('() => document.getElementById("nome-palco").textContent') == 'largo'
            caixa = pg.evaluate('() => { const r = document.querySelector("#palco .moldura").getBoundingClientRect();'
                                ' return [r.left, r.top, r.right, r.bottom]; }')
            assert caixa[0] >= 0 and caixa[2] <= 2048 and caixa[3] <= 720, caixa  # numero-neutro: a tela 2048x720
            assert pg.evaluate('() => document.documentElement.scrollWidth') <= 2048  # numero-neutro: largura da tela
            assert caixa[2] - caixa[0] > 0, caixa
            # o devolvido: o motivo e a galeria de variantes do motor, a primeira ja no palco (decisao 164: nenhum
            # formato volta sem sugestao); os fantasmas e o aviso uma vez por palco ficam em test_tela_galeria
            _clicar_aba(pg, 'orientacoes', 'Vertical')
            assert _medidas_das_abas(pg) == ['160x320']
            assert _textos(pg, '#composicoes .mini-selo') == ['Versões para escolher']
            dv = pg.evaluate('() => document.getElementById("devolucao").textContent')
            assert dv and 'mestre própria' not in dv
            assert pg.evaluate('() => document.querySelectorAll("#variantes [role=tab]").length') >= 3
            assert pg.evaluate('() => document.querySelectorAll("#palco .fantasma").length') == 0
            assert SELO_PROPOSTA in pg.evaluate('() => document.getElementById("selo-palco").textContent')
            assert SELO_APOIO not in pg.evaluate('() => document.getElementById("palco").textContent')
            # ver limpo esconde rotulos e fantasmas
            pg.evaluate('() => document.getElementById("ver-limpo").click()')
            assert pg.evaluate('() => getComputedStyle(document.querySelector("#palco .rotulo")).display') == 'none'
            assert pg.evaluate('() => document.querySelectorAll("form, [onerror]").length') == 0
            # nenhum identificador do motor no texto da moldura, em nenhum passo (redesenho de 05/11)
            for passo in ('lido', 'funcoes', 'pecas', 'design'):
                pg.evaluate('p => document.querySelector("#passos [data-passo=" + p + "]").click()', passo)
                pg.evaluate('() => { const b = document.querySelector("#arvore button"); if (b) b.click(); }')
                texto = pg.evaluate(JS_TEXTO_DA_MOLDURA)
                assert not IDENTIFICADOR.findall(texto), (passo, IDENTIFICADOR.findall(texto))
            pg.evaluate('() => document.getElementById("faltam").click()')
            assert not IDENTIFICADOR.findall(pg.evaluate(JS_TEXTO_DA_MOLDURA))
            # os botoes do M7a: presentes, desligados, com a dica; a tela continua so de leitura
            for bid in ('confirmar-composicao', 'salvar-seguir'):
                assert pg.evaluate('i => document.getElementById(i).disabled', bid) is True, bid
            assert pg.evaluate('() => document.getElementById("dica-acoes").textContent').lower() == \
                'disponível na próxima versão'
            pg.evaluate('() => { document.getElementById("salvar-seguir").click();'
                        ' document.getElementById("confirmar-composicao").click(); }')
        finally:
            nav.close()
        contagem, origem = dict(srv.contagem), srv.origem
    # nenhum pedido sai de 127.0.0.1, e nada foi pedido fora da tabela
    assert pedidos and all(u.startswith(origem + '/') for u in pedidos), pedidos
    assert not [u for u in pedidos if 'aprovar' in u]
    assert contagem['nao_encontrado'] == 0 and contagem['proibido'] == 0 and contagem['sem_cookie'] == 0
    assert contagem['fonte'] == 1 and contagem['asset'] > 0 and contagem['previa'] >= 2
    assert _fotografia(job_palco) == antes


# ------------------------------------------------------------------ entrelinha do texto e Ajustar (revisao do M7a0)
# Texto de duas linhas com entrelinha fixa diferente da automatica e matriz com escala 2: no 2048x720 do corpus a
# caixa de linha do CSS (o strut na fonte da pagina mais a meia entrelinha do trecho) passava da entrelinha do PSD e
# a segunda linha saia cortada na base do recorte do elemento.
CORPO_DUAS, ENTRELINHA_DUAS, ESCALA_DUAS, ORIGEM_DUAS = 25.0, 32.0, 2.0, (20.0, 60.0)  # numero-neutro: texto do teste
LINHAS_DUAS = ('HH', 'HHH')
# o H da fonte de autoteste: tinta de 60 a 620 no avanco de 680, de 0 a 700 na altura (unidades por em: 1000)
H_ESQ, H_DIR, H_AVANCO, H_ALTURA = 0.06, 0.62, 0.68, 0.7  # numero-neutro: glifo H da fonte de autoteste em em
FORMATOS_DUAS = [('mesma', 640, 320), ('perto', 400, 240), ('largo', 2048, 720)]


def _tinta_duas_no_doc():
    """A tinta do texto pelas regras do render (render/texto.py): primeira linha de base na origem da matriz, a
    segunda uma entrelinha abaixo, tudo na escala da matriz."""
    c = CORPO_DUAS * ESCALA_DUAS
    x, y = ORIGEM_DUAS
    larga = max(len(t) for t in LINHAS_DUAS)
    return [x + H_ESQ * c, y - H_ALTURA * c, x + ((larga - 1) * H_AVANCO + H_DIR) * c,
            y + ENTRELINHA_DUAS * ESCALA_DUAS * (len(LINHAS_DUAS) - 1)]


def _psd_duas_linhas(destino, ps):
    """PSD 320 x 160: fundo, o texto de duas linhas (camada de pixels do tamanho da tinta dele) e um quadrado."""
    from PIL import Image
    from psd_tools import PSDImage
    p = PSDImage.new('RGB', (320, 160), color=(255, 255, 255))
    p.create_pixel_layer(Image.new('RGBA', (320, 160), (240, 236, 220, 255)), name='fundo-sintetico')
    x0, y0, x1, y1 = (int(round(v)) for v in _tinta_duas_no_doc())
    t = p.create_pixel_layer(Image.new('RGBA', (x1 - x0, y1 - y0), (20, 20, 20, 255)), name='duas-linhas',
                             top=y0, left=x0)
    texto = '\r'.join(LINHAS_DUAS)
    ed = fap.EngineData.frombytes(fap._engine([(texto, 0, CORPO_DUAS, 0)], [ps]).replace(
        b'/AutoLeading true', b'/AutoLeading false\n/Leading ' + str(ENTRELINHA_DUAS).encode()))
    bounds = fap.Descriptor(name='', classID=b'bounds', items=[
        (b'Left', fap.Double(0.0)), (b'Top ', fap.Double(-20.0)), (b'Rght', fap.Double(60.0)),
        (b'Btom', fap.Double(40.0))])
    td = fap.DescriptorBlock(name='', classID=b'TxLr', items=[
        (b'Txt ', fap.String(value=texto + '\r')), (b'AntA', fap.Enumerated(typeID=b'Annt', enum=b'antiAliasSharp')),
        (b'bounds', bounds), (b'EngineData', fap.RawData(value=ed))])
    warp = fap.DescriptorBlock(name='', classID=b'warp', items=[
        (b'warpStyle', fap.Enumerated(typeID=b'warpStyle', enum=b'warpNone')), (b'warpValue', fap.Double(0.0)),
        (b'warpPerspective', fap.Double(0.0)), (b'warpPerspectiveOther', fap.Double(0.0)),
        (b'warpRotate', fap.Enumerated(typeID=b'Ornt', enum=b'Hrzn'))])
    tysh = fap.TypeToolObjectSetting(version=1, transform=(ESCALA_DUAS, 0.0, 0.0, ESCALA_DUAS) + ORIGEM_DUAS,
                                     text_version=50, text_data=td, warp_version=1, warp=warp, left=0, top=0,
                                     right=t.width, bottom=t.height)
    t._record.tagged_blocks[fap.Tag.TYPE_TOOL_OBJECT_SETTING] = fap.TaggedBlock(
        key=fap.Tag.TYPE_TOOL_OBJECT_SETTING, data=tysh)
    p.create_pixel_layer(Image.new('RGBA', (40, 40), (0, 120, 60, 255)), name='quadrado-sintetico', top=100, left=260)
    return rap._salvar(p, destino)


@pytest.fixture(scope='module')
def job_duas_linhas(tmp_path_factory):
    from desdobra import contratos
    from desdobra.briefing import modelo as mb
    from desdobra.job import nucleo
    from desdobra.render import autoteste
    base = tmp_path_factory.mktemp('duas')
    fontes = base / 'origem-fontes'
    fap.gravar(fontes, 'autoteste.ttf', autoteste.gerar_fonte())
    job = base / 'job'
    nucleo.criar(job, _psd_duas_linhas(base / 'origem' / 'kv.psd', autoteste.NOME_PS), 'c', fontes=[fontes])
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    ids = {c['nome']: c['identidade']['layer_id'] for c in laudo['camadas']}
    funcoes = {ids['fundo-sintetico']: 'fundo', ids['duas-linhas']: 'titulo', ids['quadrado-sintetico']: 'logo_principal'}
    b = ap.briefing(funcoes=funcoes, formatos=[ap.formato(i, w, h) for i, w, h in FORMATOS_DUAS])
    b.pop('cabecalho')
    b.pop('job_id')
    arq = base / 'fixture.json'
    arq.write_text(json.dumps(b), encoding='utf-8')
    mb.importar_teste(job, arq)
    return job


def _abrir_formato(pg, estado, fid):
    o, g, _co = _onde(estado, fid)
    _clicar_aba(pg, 'orientacoes', o['rotulo'])
    _clicar_grupo(pg, g['id'])
    pg.evaluate('f => document.querySelector(\'.ficha[data-formato="\' + f + \'"]\').click()', fid)
    _esperar(pg, '() => document.getElementById("palco").dataset.pronto || ""')
    assert _no_palco(pg) == fid


def _pagina_da_tela(pw, srv, largura, altura):
    from desdobra.chromium import navegador
    nav = pw.chromium.launch(headless=True, args=list(navegador.ARGUMENTOS))
    pg = nav.new_context(viewport={'width': largura, 'height': altura}, device_scale_factor=1).new_page()
    try:
        pg.goto(srv.url_entrada, wait_until='commit')
    except Exception:  # noqa: BLE001 - o 204 nao completa a navegacao
        pass
    pg.goto(srv.url_pagina, wait_until='load')
    _esperar(pg, JS_PRONTO)
    pg.evaluate('() => document.querySelector("#passos [data-passo=pecas]").click()')
    _esperar(pg, '() => document.getElementById("palco").dataset.pronto || ""')
    return nav, pg


def test_modelo_do_texto_leva_a_entrelinha_do_psd_vezes_as_escalas(job_duas_linhas):
    c = te.montar(job_duas_linhas)
    assert ENTRELINHA_DUAS != CORPO_DUAS * 1.2  # numero-neutro: a entrelinha automatica do Photoshop (120%)
    for fid, _w, _h in FORMATOS_DUAS:
        m = c['previas'][fid]
        texto = next(p for p in m['pecas'] if p['tipo'] == 'texto')
        s = next(e for e in m['elementos'] if e['id'] == texto['elemento'])['escala']
        assert [''.join(t['texto'] for t in ln['trechos']) for ln in texto['linhas']] == list(LINHAS_DUAS)
        # a entrelinha fixa do PSD vezes a escala da matriz vezes a do elemento, em px da composicao
        for ln in texto['linhas']:
            assert ln['entrelinha'] == pytest.approx(ENTRELINHA_DUAS * ESCALA_DUAS * s, abs=1e-3)
            assert ln['trechos'][0]['corpo'] == pytest.approx(CORPO_DUAS * ESCALA_DUAS * s, abs=1e-3)


def test_tinta_do_texto_no_palco_e_a_do_render_sem_corte(job_duas_linhas):
    from playwright.sync_api import sync_playwright

    from desdobra.chromium import navegador
    conteudo = te.montar(job_duas_linhas)
    navegador.apontar_playwright()
    doc = _tinta_duas_no_doc()
    with ts.ServidorTela(conteudo) as srv, sync_playwright() as pw:
        nav, pg = _pagina_da_tela(pw, srv, 1600, 900)  # numero-neutro: janela do teste
        try:
            for fid, _w, _h in FORMATOS_DUAS:
                _abrir_formato(pg, conteudo['estado'], fid)
                m = conteudo['previas'][fid]
                texto = next(p for p in m['pecas'] if p['tipo'] == 'texto')
                el = next(e for e in m['elementos'] if e['id'] == texto['elemento'])
                s = el['escala']
                # a caixa de tinta do contrato do render (a validada pela derivacao, render/derivado.py) e a tinta
                # que o render desenha: a do texto pelas regras do render, levada pelo elemento
                esperada = texto['caixa_validada']
                # a caixa de tinta do canvas do Chromium vem em pixel inteiro do glifo no corpo da exibicao
                tol = 1.0 + 0.01 * (esperada[2] - esperada[0])  # numero-neutro: um pixel mais 1% da largura
                assert esperada[3] - esperada[1] == pytest.approx((doc[3] - doc[1]) * s, abs=tol), (fid, esperada)
                no = pg.evaluate('() => (document.querySelector("#palco .texto") || {dataset: {}}).dataset.caixaTinta'
                                 ' || ""')
                assert no, fid
                medida = [float(x) for x in no.split(',')]
                assert medida == pytest.approx(esperada, abs=tol), (fid, medida, esperada)
                # nada da tinta fica fora do recorte da peca nem da caixa do elemento
                rec = texto['recorte']
                assert rec[0] - tol <= medida[0] and rec[1] - tol <= medida[1], (fid, rec, medida)
                assert medida[2] <= rec[2] + tol and medida[3] <= rec[3] + tol, (fid, rec, medida)
                cx = el['caixa']
                assert cx[1] - tol <= medida[1] and medida[3] <= cx[3] + tol, (fid, cx, medida)
        finally:
            nav.close()


def _escala_do_palco(pg):
    return pg.evaluate('() => { const m = document.querySelector("#palco .mundo");'
                       ' const t = /scale\\(([0-9.e-]+)\\)/.exec(m.style.transform);'
                       ' return t ? parseFloat(t[1]) : 1; }')


def _escala_de_ajustar(pg):
    return pg.evaluate('() => { const a = document.getElementById("palco");'
                       ' const m = a.querySelector(".mundo");'
                       ' return Math.min((a.clientWidth - 40) / parseFloat(m.style.width),'
                       ' (a.clientHeight - 40) / parseFloat(m.style.height)); }')


def test_cada_palco_abre_em_ajustar(job_duas_linhas):
    from playwright.sync_api import sync_playwright

    from desdobra.chromium import navegador
    conteudo = te.montar(job_duas_linhas)
    navegador.apontar_playwright()
    with ts.ServidorTela(conteudo) as srv, sync_playwright() as pw:
        nav, pg = _pagina_da_tela(pw, srv, 1600, 900)  # numero-neutro: janela do teste
        try:
            vistos = []
            for fid, _w, _h in FORMATOS_DUAS:
                _abrir_formato(pg, conteudo['estado'], fid)
                assert pg.evaluate('() => document.getElementById("palco").dataset.vista') == 'ajustar', fid
                k = _escala_do_palco(pg)
                assert k == pytest.approx(_escala_de_ajustar(pg), rel=1e-3), fid
                vistos.append(k)
                assert 'ajustada' in pg.evaluate('() => document.getElementById("medida-palco").textContent')
                # a composicao inteira na area, sem rolagem
                assert pg.evaluate('() => { const a = document.getElementById("palco");'
                                   ' return a.scrollWidth <= a.clientWidth && a.scrollHeight <= a.clientHeight; }'), fid
                # 1:1, Aproximar, Afastar e Ajustar seguem valendo no palco aberto
                pg.evaluate('() => document.getElementById("um-por-um").click()')
                assert _escala_do_palco(pg) == pytest.approx(1.0)
                assert pg.evaluate('() => document.getElementById("palco").dataset.vista') == 'zoom'
                pg.evaluate('() => document.getElementById("aproximar").click()')
                assert _escala_do_palco(pg) == pytest.approx(1.25)  # numero-neutro: passo do zoom da tela
                pg.evaluate('() => document.getElementById("afastar").click()')
                assert _escala_do_palco(pg) == pytest.approx(1.0)
                pg.evaluate('() => document.getElementById("ajustar").click()')
                assert _escala_do_palco(pg) == pytest.approx(k, rel=1e-3)
                pg.evaluate('() => document.getElementById("um-por-um").click()')
            # a composicao pequena cresce ate a area (Ajustar nao para em 1:1), a grande diminui
            assert max(vistos) > 1 and min(vistos) < 1, vistos
            # o 1:1 de um palco nao passa ao proximo: o formato aberto de novo volta em Ajustar
            _abrir_formato(pg, conteudo['estado'], FORMATOS_DUAS[0][0])
            assert pg.evaluate('() => document.getElementById("palco").dataset.vista') == 'ajustar'
            assert _escala_do_palco(pg) == pytest.approx(vistos[0], rel=1e-3)
        finally:
            nav.close()


# ------------------------------------------------------------------ janela de verdade
FILHO_JANELA = r'''
import json, sys, time
saida = open(sys.argv[1], 'a', encoding='utf-8')
def gravar(**k):
    saida.write(json.dumps(k) + '\n'); saida.flush()
from desdobra.tela import processo
def ao_abrir(janela, srv):
    try:
        pg = janela.pagina()
        def esperar(expr):
            fim = time.monotonic() + 60
            while pg.evaluate(expr) != '1':
                if time.monotonic() > fim:
                    raise RuntimeError('pagina nao ficou pronta')
                time.sleep(0.1)
        esperar('() => document.documentElement.dataset.pronto || ""')
        pg.evaluate('() => document.querySelector("#passos [data-passo=pecas]").click()')
        esperar('() => document.getElementById("palco").dataset.pronto || ""')
        cdp = janela.ctx.new_cdp_session(pg)
        cdp.send('DOM.enable'); cdp.send('CSS.enable')
        raiz = cdp.send('DOM.getDocument', {'depth': -1})['root']['nodeId']
        no = cdp.send('DOM.querySelector', {'nodeId': raiz, 'selector': '#palco .texto .trecho'})['nodeId']
        faces = cdp.send('CSS.getPlatformFontsForNode', {'nodeId': no})['fonts'] if no else []
        recursos = pg.evaluate('() => [location.href].concat(performance.getEntriesByType("resource").map(e => e.name))')
        gravar(aberta=True, origem=srv.origem, recursos=recursos, contagem=dict(srv.contagem),
               faces=[[f.get('familyName'), bool(f.get('isCustomFont'))] for f in faces],
               hostis=pg.evaluate('() => document.querySelectorAll("form, [onerror]").length'),
               orientacoes=pg.evaluate('() => Array.from(document.querySelectorAll("#orientacoes [role=tab]")).map(b => b.textContent)'),
               tinta=pg.evaluate('() => (document.querySelector("#palco .texto") || {dataset: {}}).dataset.tinta || ""'),
               perfil=str(janela.perfil))
    except BaseException:
        import traceback
        gravar(erro=traceback.format_exc()[-3000:])
    cdp2 = janela.ctx.new_cdp_session(janela.pagina())
    cdp2.send('Browser.close')
codigo = processo.principal(sys.argv[2:], ao_abrir=ao_abrir)
gravar(fim=True, codigo=codigo)
'''


def test_palco_na_janela_de_verdade(job_palco, tmp_path, monkeypatch):
    if sys.platform != 'win32':
        pytest.skip('a amarra do Chromium da tela roda no Windows')
    import test_tela_servidor as tts
    from desdobra import chromium
    from desdobra.render import autoteste
    navegadores = tts._pasta_com_janela()
    if navegadores is None:
        pytest.skip('Chromium com janela fixado ausente nesta maquina')
    monkeypatch.setenv(chromium.VARIAVEL_NAVEGADORES, str(navegadores))
    registro = tmp_path / 'janela.jsonl'
    teto = float(limites.valor('chromium.tempo_max_s')) * 3  # numero-neutro: teto do teste
    proc = subprocess.run([sys.executable, '-c', FILHO_JANELA, str(registro), '--job', str(job_palco)],
                          capture_output=True, timeout=teto, stdin=subprocess.DEVNULL, env=dict(os.environ))
    linhas = [json.loads(x) for x in registro.read_text(encoding='utf-8').splitlines()]
    assert not [x for x in linhas if 'erro' in x], linhas
    aberta = next(x for x in linhas if x.get('aberta'))
    assert next(x for x in linhas if x.get('fim'))['codigo'] == 0 and proc.returncode == 0
    assert proc.stdout.decode('utf-8', 'replace').strip() == 'pronto'
    assert aberta['faces'] and all(propria for _f, propria in aberta['faces'])
    assert {f for f, _p in aberta['faces']} == {autoteste.FAMILIA}
    assert aberta['hostis'] == 0 and [o.split(' ')[0] for o in aberta['orientacoes']] == ['Horizontal', 'Vertical']
    assert aberta['tinta'] and all(float(x) > 0 for x in aberta['tinta'].split(','))
    assert all(u.startswith(aberta['origem'] + '/') for u in aberta['recursos']), aberta['recursos']
    c = aberta['contagem']
    assert c['nao_encontrado'] == 0 and c['proibido'] == 0 and c['sem_cookie'] == 0 and c['fonte'] == 1
    assert not Path(aberta['perfil']).exists()
