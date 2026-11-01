# -*- coding: utf-8 -*-
"""PSD sinteticos para os testes do leitor e do laudo, gerados na hora numa pasta temporaria.

Nenhum material de cliente: nomes, textos e cores sao inventados aqui. Nada disto fica gravado no
repositorio. Os geradores usam a API de escrita do psd-tools no processo de teste (o arquivo e nosso).

Geradores:
  simples(pasta)      fundo, quadrado, grupo com camada, camada oculta e camada de texto com dois trechos
  coberta(pasta)      fundo do canvas inteiro e elemento solto, os dois cobertos por uma camada opaca
  embutido(pasta)     smart object embutido (kind data) com um PSB interno
  linkado(pasta)      smart object linkado cujo fullPath aponta para um arquivo-isca e o relPath tenta escapar
  bomba(pasta)        PSD cujo cabecalho declara 29999 x 29999 x 3 canais, com poucos bytes
  quadros(pasta)      tres grupos de topo, cada um com fundo do canvas, so um visivel
"""
import io
import struct
from pathlib import Path

from PIL import Image
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer
from psd_tools.constants import LinkedLayerType, Tag
from psd_tools.psd.descriptor import DescriptorBlock, Double, Enumerated, RawData, String
from psd_tools.psd.engine_data import EngineData
from psd_tools.psd.linked_layer import LinkedLayer
from psd_tools.psd.tagged_blocks import TaggedBlock, TaggedBlocks, TypeToolObjectSetting

TEXTO_SINTETICO = 'Oferta sintetica'
FONTE_SINTETICA = 'FonteInventada-Bold'
FONTE_SINTETICA_2 = 'FonteInventada-Regular'
FONTE_SO_ESPACO = 'FonteInventada-SoEspaco'


def _pstr(t):
    b = b'\xfe\xff' + t.encode('utf-16-be')
    b = b.replace(b'\\', b'\\\\').replace(b'(', b'\\(').replace(b')', b'\\)')
    return b'(' + b + b')'


def _engine(trechos, corpo):
    """Engine data minima com um trecho de estilo por item de `trechos` [(texto, indice_da_fonte, faux_bold)]."""
    texto = ''.join(t for t, _f, _b in trechos) + '\r'
    n = len(texto)
    runs = b''
    comprimentos = []
    for i, (t, fonte, faux) in enumerate(trechos):
        k = len(t) + (1 if i == len(trechos) - 1 else 0)
        comprimentos.append(str(k).encode())
        runs += (b'<<\n/StyleSheet\n<<\n/StyleSheetData\n<<\n/Font ' + str(fonte).encode() + b'\n/FontSize '
                 + str(float(corpo)).encode() + b'\n/AutoLeading true\n/FauxBold ' + (b'true' if faux else b'false')
                 + b'\n/FillColor\n<<\n/Type 1\n/Values [ 1.0 0.1 0.2 0.3 ]\n>>\n>>\n>>\n>>\n')
    return (b'\n\n<<\n/EngineDict\n<<\n/Editor\n<<\n/Text ' + _pstr(texto) + b'\n>>\n'
            b'/ParagraphRun\n<<\n/RunArray [\n<<\n/ParagraphSheet\n<<\n/DefaultStyleSheet 0\n/Properties\n<<\n'
            b'/Justification 2\n>>\n>>\n>>\n]\n/RunLengthArray [ ' + str(n).encode() + b' ]\n>>\n'
            b'/StyleRun\n<<\n/RunArray [\n' + runs + b']\n/RunLengthArray [ ' + b' '.join(comprimentos) + b' ]\n>>\n'
            b'/Rendered\n<<\n/Shapes\n<<\n/Children [\n<<\n/ShapeType 0\n/Cookie\n<<\n/Photoshop\n<<\n/ShapeType 0\n'
            b'/PointBase [ 0.0 0.0 ]\n>>\n>>\n>>\n]\n>>\n>>\n'
            b'>>\n/ResourceDict\n<<\n/FontSet [\n<<\n/Name ' + _pstr(FONTE_SINTETICA) + b'\n/Script 0\n/FontType 1\n'
            b'/Synthetic 0\n>>\n<<\n/Name ' + _pstr(FONTE_SINTETICA_2) + b'\n/Script 0\n/FontType 1\n/Synthetic 0\n>>\n'
            b'<<\n/Name ' + _pstr(FONTE_SO_ESPACO) + b'\n/Script 0\n/FontType 1\n/Synthetic 0\n>>\n]\n'
            b'/StyleSheetSet [\n<<\n/Name ' + _pstr('Normal RGB') + b'\n/StyleSheetData\n<<\n/Font 0\n/FontSize 12.0\n>>\n>>\n]\n'
            b'/TheNormalStyleSheet 0\n>>\n>>\n')


def _virar_texto(camada, trechos, corpo=24.0, x=10.0, y=30.0):
    texto = ''.join(t for t, _f, _b in trechos)
    ed = EngineData.frombytes(_engine(trechos, corpo))
    td = DescriptorBlock(name='', classID=b'TxLr', items=[
        (b'Txt ', String(value=texto + '\r')), (b'AntA', Enumerated(typeID=b'Annt', enum=b'antiAliasSharp')),
        (b'EngineData', RawData(value=ed))])
    warp = DescriptorBlock(name='', classID=b'warp', items=[
        (b'warpStyle', Enumerated(typeID=b'warpStyle', enum=b'warpNone')), (b'warpValue', Double(0.0)),
        (b'warpPerspective', Double(0.0)), (b'warpPerspectiveOther', Double(0.0)),
        (b'warpRotate', Enumerated(typeID=b'Ornt', enum=b'Hrzn'))])
    tysh = TypeToolObjectSetting(version=1, transform=(1.0, 0.0, 0.0, 1.0, x, y), text_version=50, text_data=td,
                                 warp_version=1, warp=warp, left=0, top=0, right=camada.width, bottom=camada.height)
    camada._record.tagged_blocks[Tag.TYPE_TOOL_OBJECT_SETTING] = TaggedBlock(key=Tag.TYPE_TOOL_OBJECT_SETTING, data=tysh)


def _salvar(psd, destino):
    """Grava dando layer_id 1, 2, 3... na ordem de descendants() (o psd-tools nao numera camada nova)."""
    for i, camada in enumerate(psd.descendants(), 1):
        if camada.layer_id < 1:
            camada.tagged_blocks.set_data(Tag.LAYER_ID, i)
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    psd.save(str(destino))
    return destino


def simples(pasta, nome='simples.psd'):
    p = PSDImage.new('RGB', (200, 100), color=(255, 255, 255))
    p.create_pixel_layer(Image.new('RGBA', (200, 100), (240, 240, 230, 255)), name='fundo-sintetico')
    p.create_pixel_layer(Image.new('RGBA', (40, 30), (200, 0, 0, 255)), name='quadrado', top=10, left=10)
    g = p.create_group(name='grupo-sintetico')
    g.create_pixel_layer(Image.new('RGBA', (30, 30), (0, 0, 200, 255)), name='dentro-do-grupo', top=50, left=150)
    oculta = p.create_pixel_layer(Image.new('RGBA', (20, 20), (0, 200, 0, 255)), name='oculta', top=70, left=20)
    oculta.visible = False
    t = p.create_pixel_layer(Image.new('RGBA', (120, 24), (20, 20, 20, 255)), name='texto-sintetico', top=40, left=60)
    _virar_texto(t, [(TEXTO_SINTETICO[:7], 0, False), (TEXTO_SINTETICO[7:], 1, True), (' ', 2, False)])
    return _salvar(p, Path(pasta) / nome)


def coberta(pasta, nome='coberta.psd'):
    p = PSDImage.new('RGB', (120, 80), color=(255, 255, 255))
    p.create_pixel_layer(Image.new('RGBA', (120, 80), (10, 120, 200, 255)), name='fundo-coberto')
    p.create_pixel_layer(Image.new('RGBA', (20, 10), (250, 200, 0, 255)), name='elemento-coberto', top=30, left=40)
    p.create_pixel_layer(Image.new('RGBA', (120, 80), (30, 30, 30, 255)), name='tampa-opaca')
    p.create_pixel_layer(Image.new('RGBA', (30, 20), (255, 255, 255, 128)), name='veu-acima', top=5, left=5)
    return _salvar(p, Path(pasta) / nome)


def quadros(pasta, nome='quadros.psd'):
    p = PSDImage.new('RGB', (90, 60), color=(255, 255, 255))
    for i, cor in enumerate(((200, 0, 0), (0, 200, 0), (0, 0, 200))):
        g = p.create_group(name='quadro-%d' % (i + 1))
        g.create_pixel_layer(Image.new('RGBA', (90, 60), cor + (255,)), name='fundo-%d' % (i + 1))
        g.create_pixel_layer(Image.new('RGBA', (10, 10), (255, 255, 255, 255)), name='marca-%d' % (i + 1), top=5, left=5)
        g.visible = (i == 0)
    return _salvar(p, Path(pasta) / nome)


def _interno_psb():
    p = PSDImage.new('RGB', (64, 48), color=(255, 255, 255))
    p._record.header.version = 2
    p.append(PixelLayer.frompil(Image.new('RGBA', (64, 48), (200, 0, 0, 255)), p, 'fundo-interno', top=0, left=0))
    p.append(PixelLayer.frompil(Image.new('RGBA', (20, 20), (0, 0, 220, 255)), p, 'quadrado-interno', top=10, left=30))
    buf = io.BytesIO()
    p.save(buf)
    return buf.getvalue()


def png_pequeno():
    buf = io.BytesIO()
    Image.new('RGBA', (12, 8), (0, 120, 0, 255)).save(buf, format='PNG')
    return buf.getvalue()


def _documento_com_smart(linkado, uid, destino):
    p = PSDImage.new('RGB', (80, 60), color=(255, 255, 255))
    lay = PixelLayer.frompil(Image.new('RGBA', (80, 60), (0, 160, 0, 255)), p, 'so-sintetico', top=0, left=0)
    p.append(lay)
    sold = DescriptorBlock(name='', classID=b'null', items=[(b'Idnt', String(value=uid))])
    lay._record.tagged_blocks.set_data(Tag.SMART_OBJECT_LAYER_DATA1, b'soLD', 4, sold)
    lmi = p._record.layer_and_mask_information
    if lmi.tagged_blocks is None:
        lmi.tagged_blocks = TaggedBlocks()
    lmi.tagged_blocks.set_data(Tag.LINKED_LAYER2, [linkado])
    return _salvar(p, destino)


def embutido(pasta, nome='embutido.psd', dados=None):
    dados = dados if dados is not None else _interno_psb()
    eh_psd = dados[:4] == b'8BPS'
    reg = LinkedLayer(kind=LinkedLayerType.DATA, version=7, uuid='uuid-embutido-sintetico',
                      filename='interno.psb' if eh_psd else 'interno.png', filetype=b'8BPB' if eh_psd else b'png ', creator=b'8BIM', filesize=None, open_file=None, linked_file=None, timestamp=None,
                      data=dados, child_id='', mod_time=0.0, lock_state=0)
    return _documento_com_smart(reg, 'uuid-embutido-sintetico', Path(pasta) / nome), dados


def linkado(pasta, isca, nome='linkado.psd', tamanho=1234):
    """O fullPath aponta para `isca` (caminho absoluto) e o relPath tenta escapar com ../..; o registro grava o nome
    da isca e o tamanho dado."""
    lf = DescriptorBlock(name='', classID=b'ExtF', items=[
        (b'fullPath', String(value=str(isca))),
        (b'relPath', String(value='../../isca/' + Path(isca).name))])
    reg = LinkedLayer(kind=LinkedLayerType.EXTERNAL, version=7, uuid='uuid-linkado-sintetico', filename=Path(isca).name,
                      filetype=b'TEXT', creator=b'????', filesize=tamanho, open_file=None, linked_file=lf,
                      timestamp=(2026, 10, 29, 12, 30, 0.0), data=b'', child_id='', mod_time=0.0, lock_state=0)
    return _documento_com_smart(reg, 'uuid-linkado-sintetico', Path(pasta) / nome)


def bomba(pasta, nome='bomba.psd', largura=29999, altura=29999):
    """So cabecalho e secoes vazias: declara largura x altura x 3 canais a 8 bits (dentro do eixo do formato)."""
    cab = b'8BPS' + struct.pack('>H', 1) + b'\x00' * 6 + struct.pack('>HIIHH', 3, altura, largura, 8, 3)
    corpo = struct.pack('>I', 0) + struct.pack('>I', 0) + struct.pack('>I', 0) + struct.pack('>H', 0)
    destino = Path(pasta) / nome
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(cab + corpo)
    return destino
