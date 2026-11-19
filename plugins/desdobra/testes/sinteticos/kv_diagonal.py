# -*- coding: utf-8 -*-
"""O KV sintetico da diagonal (decisao 199; etapa E3 do desenho da familia), gerado na hora numa pasta temporaria.

A geometria do caso de aceitacao de 18/11 (testes/familia_geometria.py), so numeros, sem nada do arquivo do Duda: o
KV vertical 1080 x 1920 e o proprio arquivo de edicao da familia. Camadas, do fundo para a frente:
  - o fundo branco, do canvas inteiro;
  - o azul, camada de pixels com o alfa cortado pela diagonal de (1080, 1286) a (130, 1900): o asset passa do canvas
    no topo e a direita ([0, -100, 1180, 1900]), e a area branca fica no canto de baixo a direita;
  - a faixa verde a esquerda (12% da largura), que sangra no topo, na base e a esquerda;
  - o titulo 'HOAX VA' em 2 linhas no alto a esquerda e o texto em 4 linhas abaixo, os dois sobre o azul (camadas de
    texto na fonte de autoteste do motor: so os glifos H, O, A, V, X e o espaco);
  - a assinatura [525, 1651, 1025, 1801] no triangulo branco, a 5,3 px da diagonal (camada de pixels, embutida no
    arquivo; nada linkado).
Nomes, textos e cores sao inventados aqui.

Geradores:
  psd(destino, ps)                o PSD 1080 x 1920, com os textos na fonte ps
  criar_job(base, formatos=None)  o job com o laudo, as fontes, o design system (com as silhuetas) e o briefing de teste
"""
import json
from pathlib import Path

import familia_geometria as G

LARGURA, ALTURA = int(G.W_REF), int(G.H_REF)
NOMES = {'fundo': 'fundo-branco-sintetico', 'azul': 'azul-diagonal-sintetico', 'verde': 'faixa-verde-sintetica',
         'titulo': 'titulo-sintetico', 'texto': 'texto-sintetico', 'assinatura': 'assinatura-sintetica'}
FUNCOES = {'fundo': 'fundo', 'azul': 'grafismo', 'verde': 'grafismo', 'titulo': 'titulo', 'texto': 'texto_de_apoio',
           'assinatura': 'assinatura_institucional'}
# a regra e a ancora de cada funcao usada (o Design system do passo 2)
USADAS = {'fundo': ('cover', 'centro', 'meio'), 'grafismo': ('cover', 'centro', 'meio'),
          'titulo': ('raiz_area', 'esquerda', 'topo'), 'texto_de_apoio': ('raiz_area', 'esquerda', 'topo'),
          'assinatura_institucional': ('raiz_area', 'direita', 'base')}
CAIXAS = {'titulo': [190, 150, 800, 450], 'texto': [190, 520, 760, 900], 'assinatura': [int(v) for v in G.ASSINATURA]}
AZUL_ASSET = [int(v) for v in G.AZUL_ASSET]
VERDE_ASSET = [-20, -20, 130, ALTURA + 20]
TITULO = 'HOAX\rVA'  # 'HOAX VA' em duas linhas
TEXTO = 'VOX AH\rHOAX VA\rAH VOX\rHOAX'  # quatro linhas
CORPO_TITULO, CORPO_TEXTO = 120.0, 80.0
CORES = {'fundo': (255, 255, 255, 255), 'azul': (20, 60, 170, 255), 'verde': (0, 150, 70, 255),
         'assinatura': (250, 200, 0, 255), 'texto': (250, 250, 250, 255)}
# os formatos do caso: o arquivo de edicao (a proporcao do KV) e o 300x600, na familia vertical
FORMATOS = [('f1080x1920', 1080, 1920), ('f300x600', 300, 600)]


def alfa_do_azul():
    """O alfa do azul (uint8, altura x largura do asset): 255 dentro do poligono do caso, 0 fora, sem suavizar."""
    import numpy as np
    from PIL import Image, ImageDraw
    a = AZUL_ASSET
    img = Image.new('L', (a[2] - a[0], a[3] - a[1]), 0)
    ImageDraw.Draw(img).polygon([(x - a[0], y - a[1]) for x, y in G.AZUL_PONTOS], fill=255)
    return np.asarray(img, dtype=np.uint8)


def psd(destino, ps):
    """O PSD 1080 x 1920 do caso, uma camada por papel, na ordem do fundo para a frente."""
    from PIL import Image

    import test_fontes_apoio as fap
    import test_render_apoio as rap
    import test_tela_palco as tp
    p = PSDImage_new(LARGURA, ALTURA)
    p.create_pixel_layer(Image.new('RGBA', (LARGURA, ALTURA), CORES['fundo']), name=NOMES['fundo'])
    a = AZUL_ASSET
    azul = Image.new('RGBA', (a[2] - a[0], a[3] - a[1]), CORES['azul'])
    azul.putalpha(Image.fromarray(alfa_do_azul(), 'L'))
    p.create_pixel_layer(azul, name=NOMES['azul'], top=a[1], left=a[0])
    v = VERDE_ASSET
    p.create_pixel_layer(Image.new('RGBA', (v[2] - v[0], v[3] - v[1]), CORES['verde']), name=NOMES['verde'], top=v[1],
                         left=v[0])
    for papel, texto, corpo in (('titulo', TITULO, CORPO_TITULO), ('texto', TEXTO, CORPO_TEXTO)):
        x0, y0, x1, y1 = CAIXAS[papel]
        t = p.create_pixel_layer(Image.new('RGBA', (x1 - x0, y1 - y0), CORES['texto']), name=NOMES[papel], top=y0,
                                 left=x0)
        maior = max(texto.split('\r'), key=len)
        fap._virar_texto(t, [(texto, 0, corpo, 0)], [ps], fap.largura(maior, corpo, avancos=tp.AVANCOS),
                         x=float(x0 + 4), y=float(y0 + corpo))
    x0, y0, x1, y1 = CAIXAS['assinatura']
    p.create_pixel_layer(Image.new('RGBA', (x1 - x0, y1 - y0), CORES['assinatura']), name=NOMES['assinatura'],
                         top=y0, left=x0)
    return rap._salvar(p, destino)


def PSDImage_new(largura, altura):
    from psd_tools import PSDImage
    return PSDImage.new('RGB', (largura, altura), color=(255, 255, 255))


def criar_job(base, formatos=None):
    """O job do KV da diagonal em base/kv-diagonal: o PSD, a fonte de autoteste, o laudo, o design system com as
    silhuetas e o briefing de teste (as funcoes, as regras e os formatos). Devolve {'job', 'ids': papel -> layer_id,
    'funcoes': layer_id -> funcao}."""
    import test_derivacao_apoio as ap
    import test_fontes_apoio as fap
    from desdobra import contratos
    from desdobra.briefing import modelo as mb
    from desdobra.job import nucleo
    from desdobra.render import autoteste
    base = Path(base) / 'kv-diagonal'
    fontes = base / 'origem-fontes'
    fap.gravar(fontes, 'autoteste.ttf', autoteste.gerar_fonte())
    job = base / 'job'
    nucleo.criar(job, psd(base / 'origem' / 'kv-diagonal.psd', autoteste.NOME_PS), 'c', fontes=[fontes])
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    por_nome = {c['nome']: c['identidade']['layer_id'] for c in laudo['camadas']}
    ids = {papel: por_nome[nome] for papel, nome in NOMES.items()}
    funcoes = {ids[papel]: f for papel, f in FUNCOES.items()}
    regras = dict(ap.REGRAS, **{f: r for f, (r, _x, _y) in USADAS.items()})
    ancoras = dict(ap.ANCORAS, **{f: (x, y) for f, (_r, x, y) in USADAS.items()})
    # cada formato e (id, largura, altura) ou (id, largura, altura, graus do giro); o giro de um quarto de volta vai
    # no sentido horario (etapa E4: os girados da familia vertical)
    fmts = []
    for f in formatos or FORMATOS:
        i, w, h = f[:3]
        g = f[3] if len(f) > 3 else 0
        fmts.append(ap.formato(i, w, h, rotacao={'graus': g, 'sentido': 'horario' if g else None}))
    b = ap.briefing(funcoes=funcoes, regras=regras, ancoras=ancoras, formatos=fmts)
    b.pop('cabecalho')
    b.pop('job_id')
    arq = base / 'fixture.json'
    arq.write_text(json.dumps(b), encoding='utf-8')
    mb.importar_teste(job, arq)
    return {'job': job, 'ids': ids, 'funcoes': funcoes}
