# -*- coding: utf-8 -*-
"""Material sintetico dos testes de fontes: fontes geradas na hora pelo fontTools (fontBuilder) e PSD com camadas
de texto que pedem essas fontes, com a caixa TySh (bounds) gravada. Nada fica no repositorio; nomes e textos sao
inventados. Este arquivo nao tem teste: so geradores."""
import io
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.ttCollection import TTCollection
from PIL import Image
from psd_tools import PSDImage
from psd_tools.constants import Tag
from psd_tools.psd.descriptor import Descriptor, DescriptorBlock, Double, Enumerated, RawData, String
from psd_tools.psd.engine_data import EngineData
from psd_tools.psd.tagged_blocks import TaggedBlock, TypeToolObjectSetting

CARACTERES = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,'
OFL = 'This Font Software is licensed under the SIL Open Font License, Version 1.1.'
UPM = 1000


def fonte(ps='Inventada-Bold', familia='Inventada', estilo='Bold', avanco=500, peso=700, caracteres=CARACTERES,
          formato='ttf', licenca=OFL, ps_mac=None, versao='Version 1.000', variavel=False, fs_type=0, id_unico=None,
          avancos=None):
    """Bytes de uma fonte TrueType sintetica: um retangulo por glifo, avanco fixo (ou por caractere em avancos)."""
    fb = FontBuilder(UPM, isTTF=True)
    nomes = ['.notdef'] + ['g%04x' % ord(c) for c in caracteres]
    fb.setupGlyphOrder(nomes)
    fb.setupCharacterMap({ord(c): 'g%04x' % ord(c) for c in caracteres})
    glifos, metricas = {}, {}
    for n, c in zip(nomes, [None] + list(caracteres)):
        av = (avancos or {}).get(c, avanco)
        pen = TTGlyphPen(None)
        if c not in (None, ' '):
            pen.moveTo((50, 0))
            pen.lineTo((50, 700))
            pen.lineTo((max(av - 50, 60), 700))
            pen.lineTo((max(av - 50, 60), 0))
            pen.closePath()
        glifos[n] = pen.glyph()
        metricas[n] = (av, 50)
    fb.setupGlyf(glifos)
    fb.setupHorizontalMetrics(metricas)
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    nomes_tab = {'familyName': familia, 'styleName': estilo, 'psName': ps, 'version': versao,
                 'uniqueFontIdentifier': id_unico or ('1.000;TESTE;' + ps)}
    if licenca:
        nomes_tab['licenseDescription'] = licenca
    fb.setupNameTable(nomes_tab, mac=bool(ps_mac))
    fb.setupOS2(usWeightClass=peso, sTypoAscender=800, sTypoDescender=-200, sTypoLineGap=0, usWinAscent=800,
                usWinDescent=200, sCapHeight=700, sxHeight=500, fsType=fs_type)
    fb.setupPost()
    if variavel:
        fb.setupFvar([('wght', 100, peso, 900, 'Weight')], [])
    fonte_tt = fb.font
    if ps_mac:
        for r in fonte_tt['name'].names:
            if r.nameID == 6 and r.platformID == 1:
                r.string = ps_mac
    b = io.BytesIO()
    fonte_tt.save(b)
    if formato in ('woff', 'woff2'):
        f = TTFont(io.BytesIO(b.getvalue()))
        f.flavor = formato
        b = io.BytesIO()
        f.save(b)
    return b.getvalue()


def colecao(*dados_fontes):
    c = TTCollection()
    c.fonts = [TTFont(io.BytesIO(d)) for d in dados_fontes]
    b = io.BytesIO()
    c.save(b)
    return b.getvalue()


def largura(texto, corpo, avanco=500, tracking=0, avancos=None):
    """Largura esperada de uma linha no espaco de texto (sem kerning; sem o tracking do ultimo caractere)."""
    soma = sum((avancos or {}).get(c, avanco) for c in texto) * corpo / UPM
    return soma + tracking / 1000.0 * corpo * max(len(texto) - 1, 0)


# ------------------------------------------------------------------ PSD com texto
def _pstr(t):
    b = b'\xfe\xff' + t.encode('utf-16-be')
    b = b.replace(b'\\', b'\\\\').replace(b'(', b'\\(').replace(b')', b'\\)')
    return b'(' + b + b')'


def _engine(trechos, fontes):
    """trechos: [(texto, indice_da_fonte, corpo, tracking)]; fontes: nomes PostScript do FontSet."""
    texto = ''.join(t for t, *_ in trechos) + '\r'
    runs, comprimentos = b'', []
    for i, (t, fonte_i, corpo, tracking) in enumerate(trechos):
        comprimentos.append(str(len(t) + (1 if i == len(trechos) - 1 else 0)).encode())
        runs += (b'<<\n/StyleSheet\n<<\n/StyleSheetData\n<<\n/Font ' + str(fonte_i).encode() + b'\n/FontSize '
                 + str(float(corpo)).encode() + b'\n/Tracking ' + str(int(tracking)).encode()
                 + b'\n/AutoKerning true\n/AutoLeading true\n/FauxBold false\n/FillColor\n<<\n/Type 1\n'
                 b'/Values [ 1.0 0.1 0.2 0.3 ]\n>>\n>>\n>>\n>>\n')
    fontset = b''.join(b'<<\n/Name ' + _pstr(f) + b'\n/Script 0\n/FontType 1\n/Synthetic 0\n>>\n' for f in fontes)
    return (b'\n\n<<\n/EngineDict\n<<\n/Editor\n<<\n/Text ' + _pstr(texto) + b'\n>>\n'
            b'/ParagraphRun\n<<\n/RunArray [\n<<\n/ParagraphSheet\n<<\n/DefaultStyleSheet 0\n/Properties\n<<\n'
            b'/Justification 0\n>>\n>>\n>>\n]\n/RunLengthArray [ ' + str(len(texto)).encode() + b' ]\n>>\n'
            b'/StyleRun\n<<\n/RunArray [\n' + runs + b']\n/RunLengthArray [ ' + b' '.join(comprimentos) + b' ]\n>>\n'
            b'/Rendered\n<<\n/Shapes\n<<\n/Children [\n<<\n/ShapeType 0\n/Cookie\n<<\n/Photoshop\n<<\n/ShapeType 0\n'
            b'/PointBase [ 0.0 0.0 ]\n>>\n>>\n>>\n]\n>>\n>>\n'
            b'>>\n/ResourceDict\n<<\n/FontSet [\n' + fontset + b']\n'
            b'/StyleSheetSet [\n<<\n/Name ' + _pstr('Normal RGB') + b'\n/StyleSheetData\n<<\n/Font 0\n/FontSize 12.0\n>>\n>>\n]\n'
            b'/TheNormalStyleSheet 0\n>>\n>>\n')


def _virar_texto(camada, trechos, fontes, largura_caixa, x=10.0, y=30.0):
    texto = ''.join(t for t, *_ in trechos)
    ed = EngineData.frombytes(_engine(trechos, fontes))
    bounds = Descriptor(name='', classID=b'bounds', items=[
        (b'Left', Double(0.0)), (b'Top ', Double(-20.0)), (b'Rght', Double(float(largura_caixa))), (b'Btom', Double(5.0))])
    td = DescriptorBlock(name='', classID=b'TxLr', items=[
        (b'Txt ', String(value=texto + '\r')), (b'AntA', Enumerated(typeID=b'Annt', enum=b'antiAliasSharp')),
        (b'bounds', bounds), (b'EngineData', RawData(value=ed))])
    warp = DescriptorBlock(name='', classID=b'warp', items=[
        (b'warpStyle', Enumerated(typeID=b'warpStyle', enum=b'warpNone')), (b'warpValue', Double(0.0)),
        (b'warpPerspective', Double(0.0)), (b'warpPerspectiveOther', Double(0.0)),
        (b'warpRotate', Enumerated(typeID=b'Ornt', enum=b'Hrzn'))])
    tysh = TypeToolObjectSetting(version=1, transform=(1.0, 0.0, 0.0, 1.0, x, y), text_version=50, text_data=td,
                                 warp_version=1, warp=warp, left=0, top=0, right=camada.width, bottom=camada.height)
    camada._record.tagged_blocks[Tag.TYPE_TOOL_OBJECT_SETTING] = TaggedBlock(key=Tag.TYPE_TOOL_OBJECT_SETTING, data=tysh)


def psd_textos(destino, camadas):
    """PSD com uma camada de texto por item de `camadas`: (trechos [(texto, fonte_ps, corpo, tracking)], largura
    da caixa TySh). Devolve o caminho."""
    p = PSDImage.new('RGB', (300, 200), color=(255, 255, 255))
    p.create_pixel_layer(Image.new('RGBA', (300, 200), (240, 240, 230, 255)), name='fundo-sintetico')
    for k, (trechos, larg) in enumerate(camadas):
        fontes = []
        for _t, ps, *_ in trechos:
            if ps not in fontes:
                fontes.append(ps)
        t = p.create_pixel_layer(Image.new('RGBA', (120, 24), (20, 20, 20, 255)), name='texto-%d' % k, top=20 + 30 * k,
                                 left=20)
        _virar_texto(t, [(tx, fontes.index(ps), corpo, tr) for tx, ps, corpo, tr in trechos], fontes, larg)
    for i, camada in enumerate(p.descendants(), 1):
        if camada.layer_id < 1:
            camada.tagged_blocks.set_data(Tag.LAYER_ID, i)
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    p.save(str(destino))
    return destino


def gravar(pasta, nome, dados):
    caminho = Path(pasta) / nome
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(dados)
    return caminho
