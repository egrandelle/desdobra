# -*- coding: utf-8 -*-
"""Material sintetico dos testes do render (M4): PSD com fundo, texto de duas cores, camada por cima do texto e
texto com opacidade, e o PSD com smart object linkado e o arquivo casado da campanha. Tudo gerado na hora numa pasta
temporaria; nomes, textos e cores sao inventados. Este arquivo nao tem teste: so geradores."""
import io
from pathlib import Path

from PIL import Image
from psd_tools import PSDImage
from psd_tools.constants import Tag
from psd_tools.psd.descriptor import Descriptor, DescriptorBlock, Double, Enumerated, RawData, String
from psd_tools.psd.engine_data import EngineData
from psd_tools.psd.tagged_blocks import TaggedBlock, TypeToolObjectSetting

import sinteticos
import test_fontes_apoio as ap

FONTE = 'Inventada-Bold'
COR_1 = (0.1, 0.2, 0.3)
COR_2 = (0.8, 0.1, 0.1)


def _engine_cores(trechos):
    """Engine data com um trecho por item [(texto, corpo, (r, g, b))], todos na fonte FONTE."""
    base = ap._engine([(t, 0, corpo, 0) for t, corpo, _c in trechos], [FONTE])
    partes = base.split(b'/Values [ 1.0 0.1 0.2 0.3 ]')
    saida = partes[0]
    for (_t, _c, cor), resto in zip(trechos, partes[1:]):
        saida += b'/Values [ 1.0 %s ]' % b' '.join(b'%.3f' % x for x in cor) + resto
    return saida


def _virar_texto(camada, trechos, x, y, largura_caixa):
    texto = ''.join(t for t, *_ in trechos)
    ed = EngineData.frombytes(_engine_cores(trechos))
    bounds = Descriptor(name='', classID=b'bounds', items=[
        (b'Left', Double(0.0)), (b'Top ', Double(-20.0)), (b'Rght', Double(float(largura_caixa))), (b'Btom', Double(5.0))])
    td = DescriptorBlock(name='', classID=b'TxLr', items=[
        (b'Txt ', String(value=texto + '\r')), (b'AntA', Enumerated(typeID=b'Annt', enum=b'antiAliasSmooth')),
        (b'bounds', bounds), (b'EngineData', RawData(value=ed))])
    warp = DescriptorBlock(name='', classID=b'warp', items=[
        (b'warpStyle', Enumerated(typeID=b'warpStyle', enum=b'warpNone')), (b'warpValue', Double(0.0)),
        (b'warpPerspective', Double(0.0)), (b'warpPerspectiveOther', Double(0.0)),
        (b'warpRotate', Enumerated(typeID=b'Ornt', enum=b'Hrzn'))])
    tysh = TypeToolObjectSetting(version=1, transform=(1.0, 0.0, 0.0, 1.0, x, y), text_version=50, text_data=td,
                                 warp_version=1, warp=warp, left=0, top=0, right=camada.width, bottom=camada.height)
    camada._record.tagged_blocks[Tag.TYPE_TOOL_OBJECT_SETTING] = TaggedBlock(key=Tag.TYPE_TOOL_OBJECT_SETTING, data=tysh)


def psd_render(destino):
    """Fundo, texto de duas cores, quadrado por cima do texto e um segundo texto com opacidade 50%."""
    p = PSDImage.new('RGB', (320, 160), color=(255, 255, 255))
    p.create_pixel_layer(Image.new('RGBA', (320, 160), (240, 236, 220, 255)), name='fundo-sintetico')
    t1 = p.create_pixel_layer(Image.new('RGBA', (200, 30), (20, 20, 20, 255)), name='texto-cores', top=20, left=10)
    _virar_texto(t1, [('ABC', 28.0, COR_1), ('abc', 28.0, COR_2)], 12.0, 44.0, ap.largura('ABCabc', 28.0))
    p.create_pixel_layer(Image.new('RGBA', (40, 40), (0, 120, 60, 255)), name='quadrado-acima', top=30, left=150)
    t2 = p.create_pixel_layer(Image.new('RGBA', (200, 30), (20, 20, 20, 255)), name='texto-meio', top=90, left=10)
    t2.opacity = 128
    _virar_texto(t2, [('AB ab', 40.0, COR_1)], 20.0, 130.0, ap.largura('AB ab', 40.0))
    for i, camada in enumerate(p.descendants(), 1):
        if camada.layer_id < 1:
            camada.tagged_blocks.set_data(Tag.LAYER_ID, i)
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    p.save(str(destino))
    return destino


def png_azul():
    buf = io.BytesIO()
    Image.new('RGBA', (20, 10), (0, 0, 220, 255)).save(buf, format='PNG')
    return buf.getvalue()


def linkado_com_campanha(pasta):
    """PSD com um smart object linkado (camada de 80 x 60 com pixels verdes gravados) e a pasta de campanha com o
    arquivo do mesmo nome e tamanho (PNG azul). Devolve (psd, pasta da campanha, bytes do PNG)."""
    pasta = Path(pasta)
    dados = png_azul()
    campanha = pasta / 'campanha'
    campanha.mkdir(parents=True, exist_ok=True)
    (campanha / 'arte-linkada.png').write_bytes(dados)
    fora = pasta / 'fora-da-entrada'
    fora.mkdir(parents=True, exist_ok=True)
    isca = fora / 'arte-linkada.png'
    isca.write_bytes(b'isca sintetica, nunca aberta')
    psd = sinteticos.linkado(pasta / 'psd', isca, tamanho=len(dados))
    return psd, campanha, dados


def _salvar(p, destino):
    for i, camada in enumerate(p.descendants(), 1):
        if camada.layer_id < 1:
            camada.tagged_blocks.set_data(Tag.LAYER_ID, i)
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    p.save(str(destino))
    return destino


def psd_ajuste_sobre_texto(destino, mesclagem=None):
    """Fundo, texto e, por cima do texto, uma camada de ajuste (inversao) ou, com mesclagem, um quadrado nesse modo."""
    from psd_tools.constants import BlendMode
    p = PSDImage.new('RGB', (200, 80), color=(255, 255, 255))
    p.create_pixel_layer(Image.new('RGBA', (200, 80), (200, 210, 230, 255)), name='fundo-sintetico')
    t = p.create_pixel_layer(Image.new('RGBA', (120, 30), (20, 20, 20, 255)), name='texto', top=20, left=10)
    _virar_texto(t, [('ABC', 28.0, COR_1)], 12.0, 44.0, ap.largura('ABC', 28.0))
    if mesclagem is None:
        a = p.create_pixel_layer(Image.new('RGBA', (200, 80), (0, 0, 0, 0)), name='ajuste-global')
        a._record.tagged_blocks.set_data(Tag.INVERT)
    else:
        q = p.create_pixel_layer(Image.new('RGBA', (60, 60), (250, 120, 0, 255)), name='quadrado', top=10, left=20)
        q.blend_mode = getattr(BlendMode, mesclagem)
    return _salvar(p, destino)


def psd_clip_dividido(destino):
    """Base, texto clipado na base e um quadrado clipado na mesma base, acima do texto."""
    p = PSDImage.new('RGB', (200, 80), color=(255, 255, 255))
    p.create_pixel_layer(Image.new('RGBA', (200, 80), (240, 240, 230, 255)), name='fundo-sintetico')
    p.create_pixel_layer(Image.new('RGBA', (150, 60), (30, 90, 160, 255)), name='base', top=10, left=10)
    t = p.create_pixel_layer(Image.new('RGBA', (120, 30), (20, 20, 20, 255)), name='texto', top=20, left=10)
    _virar_texto(t, [('ABC', 28.0, COR_2)], 12.0, 44.0, ap.largura('ABC', 28.0))
    t.clipping = True
    q = p.create_pixel_layer(Image.new('RGBA', (40, 40), (250, 200, 0, 255)), name='clipado-acima', top=20, left=120)
    q.clipping = True
    return _salvar(p, destino)


def jpeg_cmyk_com_icc():
    """JPEG CMYK sem perfil embutido (o Pillow nao cria perfil CMYK): o render converte de forma simples e registra."""
    buf = io.BytesIO()
    Image.new('CMYK', (20, 10), (200, 0, 0, 0)).save(buf, format='JPEG', quality=95)
    return buf.getvalue()
