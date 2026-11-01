# -*- coding: utf-8 -*-
"""Autoteste do caminho PDF + PDFium do render, para o doctor (decisoes-v1.md, 01/11, 36; arquitetura-v1.md, 4.15).

A fonte do autoteste e gerada pelo proprio motor num processo filho (fontBuilder do fontTools), com retas, diagonais
e curvas: nada e baixado, o DA nao poe arquivo em pasta nenhuma e o pacote continua sem arquivo de fonte. A fonte
vive so na memoria e numa pasta temporaria do doctor, apagada logo depois de lida.

A pagina de referencia e desenhada pelo mesmo caminho do job: @font-face servido pela rota local, Chromium fixado,
PDF em memoria, PDFium com supersample, composicao com a gama do Photoshop (desdobra.render.execucao). O resultado
e comparado com a imagem gravada no pacote (motor/referencias/autoteste-render.png), gerada com a mesma fonte na
maquina de desenvolvimento. Os limiares (render.autoteste_media_max e render.autoteste_max_abs) estao a calibrar:
acima deles o doctor avisa.

Para gravar a imagem de referencia de novo (so desenvolvimento, depois de mudar o caminho do render de proposito):
    python -m desdobra.render.autoteste --gravar-referencia
"""
import io
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from desdobra import PASTA_MOTOR, arquivos, contratos, limites, plataforma

REFERENCIA = PASTA_MOTOR / 'referencias' / 'autoteste-render.png'
NOME_PS = 'DesdobraAutoteste-Regular'
FAMILIA = 'DesdobraAutoteste'
LARGURA, ALTURA = 480, 260  # numero-neutro: tamanho da pagina de referencia
# Filho que grava a fonte do autoteste: so o fontBuilder, com datas fixas (a fonte sai igual byte a byte).
FILHO_FONTE = (
    'import sys\n'
    'from fontTools.fontBuilder import FontBuilder\n'
    'from fontTools.pens.ttGlyphPen import TTGlyphPen\n'
    'def caminho(pen, pts):\n'
    '    pen.moveTo(pts[0])\n'
    '    for p in pts[1:]:\n'
    '        pen.lineTo(p)\n'
    '    pen.closePath()\n'
    'def oval(pen, cx, cy, rx, ry, horario):\n'
    '    k = 0.4142\n'
    '    pts = [(cx + rx, cy), (cx + rx, cy + k * ry), (cx + k * rx, cy + ry), (cx, cy + ry), (cx - k * rx, cy + ry),\n'
    '           (cx - rx, cy + k * ry), (cx - rx, cy), (cx - rx, cy - k * ry), (cx - k * rx, cy - ry), (cx, cy - ry),\n'
    '           (cx + k * rx, cy - ry), (cx + rx, cy - k * ry)]\n'
    '    pts = [(round(x), round(y)) for x, y in pts]\n'
    '    if horario:\n'
    '        pts = [pts[0]] + pts[1:][::-1]\n'
    '    pen.moveTo(pts[0])\n'
    '    for i in range(1, 12, 3):\n'
    '        pen.qCurveTo(pts[i], pts[i + 1], pts[(i + 2) % 12])\n'
    '    pen.closePath()\n'
    'glifos_def = {\n'
    '    "H": (680, lambda pen: (caminho(pen, [(60, 0), (60, 700), (180, 700), (180, 410), (500, 410), (500, 700), (620, 700), (620, 0), (500, 0), (500, 300), (180, 300), (180, 0)]))),\n'
    '    "O": (760, lambda pen: (oval(pen, 380, 350, 330, 360, True), oval(pen, 380, 350, 210, 250, False))),\n'
    '    "A": (700, lambda pen: (caminho(pen, [(10, 0), (290, 700), (410, 700), (690, 0), (560, 0), (490, 190), (210, 190), (140, 0)]), caminho(pen, [(250, 300), (450, 300), (350, 570)]))),\n'
    '    "V": (700, lambda pen: caminho(pen, [(10, 700), (140, 700), (350, 140), (560, 700), (690, 700), (410, 0), (290, 0)])),\n'
    '    "X": (680, lambda pen: caminho(pen, [(20, 0), (270, 350), (20, 700), (160, 700), (340, 440), (520, 700), (660, 700), (410, 350), (660, 0), (520, 0), (340, 260), (160, 0)])),\n'
    '}\n'
    'fb = FontBuilder(1000, isTTF=True)\n'
    'cars = sorted(glifos_def) + [" "]\n'
    'nomes = [".notdef"] + ["g%04x" % ord(c) for c in cars]\n'
    'fb.setupGlyphOrder(nomes)\n'
    'fb.setupCharacterMap({ord(c): "g%04x" % ord(c) for c in cars})\n'
    'glifos, metricas = {}, {}\n'
    'for n, c in zip(nomes, [None] + cars):\n'
    '    pen = TTGlyphPen(None)\n'
    '    av = 500\n'
    '    if c in glifos_def:\n'
    '        av, desenho = glifos_def[c]\n'
    '        desenho(pen)\n'
    '    glifos[n] = pen.glyph()\n'
    '    metricas[n] = (av, 0)\n'
    'fb.setupGlyf(glifos)\n'
    'fb.setupHorizontalMetrics(metricas)\n'
    'fb.setupHorizontalHeader(ascent=800, descent=-200)\n'
    'fb.setupNameTable({"familyName": "DesdobraAutoteste", "styleName": "Regular", "psName": sys.argv[2], "version": "Version 1.000"})\n'
    'fb.setupOS2(usWeightClass=400, sTypoAscender=800, sTypoDescender=-200, sTypoLineGap=0, usWinAscent=800, usWinDescent=200, sCapHeight=700, sxHeight=500)\n'
    'fb.setupPost()\n'
    'fb.font["head"].created = 3600000000\n'
    'fb.font["head"].modified = 3600000000\n'
    'fb.save(sys.argv[1])\n'
)


class ErroAutoteste(Exception):
    pass


def gerar_fonte():
    """Bytes da fonte do autoteste, gerada num processo filho (o processo principal nunca importa o fontTools)."""
    tempo = float(limites.valor('chromium.tempo_max_s'))
    with tempfile.TemporaryDirectory(prefix='desdobra-autoteste-') as pasta:
        arq = Path(pasta) / 'autoteste.ttf'
        proc = subprocess.run([sys.executable, '-I', '-B', '-c', FILHO_FONTE, str(arq), NOME_PS],
                              capture_output=True, timeout=tempo, stdin=subprocess.DEVNULL)
        if proc.returncode != 0 or not arq.is_file():
            raise ErroAutoteste('O fontTools não gerou a fonte do autoteste.')
        dados = arq.read_bytes()
        arq.unlink()
    return dados


def _run(inicio, fim, texto, corpo, tracking=0):
    return {'inicio': inicio, 'fim': fim, 'texto': texto, 'fonte_ps': NOME_PS, 'corpo_espaco_texto': corpo,
            'tracking': tracking, 'entrelinha': corpo * 1.2, 'autoleading': True, 'font_caps': 'NORMAL',  # numero-neutro: entrelinha da pagina de teste
            'autokerning': True, 'kerning': 0, 'ligaduras': True, 'tem_tinta': True, 'faux_bold': False}


def _texto(ident, regiao, matriz, trechos, cores):
    """trechos: [(texto, corpo, cor)], na mesma linha; cores: {cor: [r, g, b]}."""
    runs, por_trecho, pos = [], {}, 0
    for t, corpo, cor in trechos:
        runs.append(_run(pos, pos + len(t), t, corpo))
        por_trecho[str(pos)] = cor
        pos += len(t)
    return {'id': ident, 'tipo': 'texto', 'layer_id': int(ident[1:]), 'indice': int(ident[1:]), 'regiao': regiao,
            'opacidade': 1.0, 'blend': 'NORMAL',
            'texto': {'matriz': matriz, 'runs': runs, 'paragrafos': [], 'tipo_caixa': 'ponto', 'box_bounds': None},
            'faces': {NOME_PS: 'f01'}, 'cores': sorted(cores),
            'valores_cor': {c: {'rgb': v, 'alfa': 1.0} for c, v in cores.items()},
            'cores_por_trecho': por_trecho, 'antialiasing': 'AnSm', 'corpo_dispositivo_px': max(c for _t, c, _k in trechos),
            'sharp_pequeno': False}


def contrato_de_referencia(sha_fonte):
    """A pagina de referencia: retas, diagonais e curvas em corpos pequeno, medio e grande, duas cores numa linha e
    uma linha girada, preto e cor sobre fundo branco e cor sobre cor."""
    import math
    ang = math.radians(-9.0)  # numero-neutro: giro da linha de teste
    c, s = math.cos(ang), math.sin(ang)
    preto, azul, vermelho = [0.0, 0.0, 0.0], [0.05, 0.2, 0.6], [0.85, 0.1, 0.1]
    entradas = [
        _texto('e01', [0, 0, LARGURA, 40], [1, 0, 0, 1, 10.3, 24.6], [('HOAVX HOAVX XVAOH', 13.0, 'c0')], {'c0': preto}),  # numero-neutro: pagina de teste
        _texto('e02', [0, 30, LARGURA, 100], [1, 0, 0, 1, 10.0, 80.4], [('HOAV', 40.0, 'c0'), ('X OHA', 40.0, 'c1')],  # numero-neutro: idem
               {'c0': preto, 'c1': vermelho}),
        _texto('e03', [0, 100, LARGURA, ALTURA], [1, 0, 0, 1, 12.7, 225.2], [('HOAVX', 118.0, 'c0')], {'c0': azul}),  # numero-neutro: idem
        _texto('e04', [250, 90, LARGURA, ALTURA], [c, s, -s, c, 262.0, 160.0], [('AVOX', 30.0, 'c0')], {'c0': vermelho}),  # numero-neutro: idem
    ]
    return {'esquema': 'composicao/1', 'job_id': 'autoteste',
            'formato': {'chave': 'autoteste', 'largura': LARGURA, 'altura': ALTURA, 'escala': 1.0},
            'documento': {'largura': LARGURA, 'altura': ALTURA, 'modo': 'RGB', 'bits': 8, 'perfil': None,  # numero-neutro: 8 bits
                          'fundo': [1.0, 1.0, 0.92]},  # numero-neutro: fundo creme da pagina de teste
            'origem': {'kv_sha256': None, 'laudo_sha256': None, 'funcoes': 'autoteste'},
            'faces': [{'id': 'f01', 'sha256': sha_fonte, 'nome_ps': NOME_PS, 'nomes_ps': [NOME_PS], 'formato': 'ttf',
                       'indice': 0, 'peso_declarado': 400, 'colecao': None, 'metricas': None}],  # numero-neutro: peso normal
            'entradas': entradas, 'fora_da_peca': [], 'registros': []}


def desenhar(plat=None):
    """Desenha a pagina de referencia pelo caminho do job. Devolve (bytes do PNG, cdp, cache, versao do Chromium)."""
    from desdobra.chromium import servidor
    from desdobra.render import execucao
    plat = plat or plataforma.obter()
    dados = gerar_fonte()
    contrato = contrato_de_referencia(arquivos.sha256_bytes(dados))
    servidos = {'f01': (dados, servidor.MIME_POR_FORMATO['ttf'])}
    pasta = Path(tempfile.mkdtemp(prefix='desdobra-autoteste-'))
    try:
        arq = pasta / 'contrato.json'
        contratos.gravar(arq, contrato, 'composicao/1')
        pdfs, paginas, cdp, cache, versao = execucao.texto_no_chromium(contrato, servidos, 'dsd-autoteste')
        master, _saida, _cob, _pico = execucao.compor(pasta, contrato, arq, {}, pdfs, paginas, plat,
                                                      trabalho=pasta / 'trabalho')
    finally:
        shutil.rmtree(pasta, ignore_errors=True)
    return master, cdp, cache, versao


def comparar(png, referencia=REFERENCIA):
    """(media da diferenca absoluta, maior diferenca) por canal, em 0..255, contra a imagem gravada."""
    import numpy as np
    from PIL import Image
    a = np.asarray(Image.open(io.BytesIO(png)).convert('RGB')).astype(np.int16)
    b = np.asarray(Image.open(referencia).convert('RGB')).astype(np.int16)
    if a.shape != b.shape:
        raise ErroAutoteste('A imagem do autoteste não tem o tamanho da referência.')
    d = np.abs(a - b)
    return float(d.mean()), int(d.max())


def rodar(plat=None):
    """Roda o autoteste. Devolve {'media', 'maximo', 'cdp', 'cache', 'chromium', 'passou'}."""
    if not REFERENCIA.is_file():
        raise ErroAutoteste('A imagem de referência do autoteste não está no pacote.')
    png, cdp, cache, versao = desenhar(plat)
    media, maximo = comparar(png)
    passou = (media <= limites.valor('render.autoteste_media_max') and maximo <= limites.valor('render.autoteste_max_abs'))
    return {'media': round(media, 4), 'maximo': maximo, 'cdp': cdp, 'cache': cache, 'chromium': versao,
            'passou': bool(passou)}


def gravar_referencia():
    png, cdp, _cache, versao = desenhar()
    if cdp['confere'] != cdp['trechos'] or not cdp['trechos']:
        raise ErroAutoteste('O CDP não confirmou a face do autoteste: a referência não foi gravada.')
    REFERENCIA.parent.mkdir(parents=True, exist_ok=True)
    arquivos.gravar_bytes_atomico(REFERENCIA, png)
    return versao


if __name__ == '__main__':
    if sys.argv[1:] == ['--gravar-referencia']:
        print('Referência gravada com o Chromium %s.' % gravar_referencia())
    else:
        sys.stderr.write('uso: python -m desdobra.render.autoteste --gravar-referencia\n')
        sys.exit(2)  # numero-neutro: codigo de uso
