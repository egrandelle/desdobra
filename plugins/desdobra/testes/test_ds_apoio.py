# -*- coding: utf-8 -*-
"""Material sintetico dos testes de cor e de design system (test_cor*, test_ds*), gerado na hora.

  - perfis ICC: o sRGB vem do ImageCms.createProfile; o Adobe RGB (1998) e um perfil de matriz v2 escrito aqui a
    partir dos primarios publicados (colorantes adaptados a D50 e gama 563/256), lido pelo ImageCms;
  - PSD sintetico com perfil, fundo chapado, preenchimento de cor solida, texto com escala vertical na matriz,
    camada recortada em alfa, foto sem recorte e efeito de overlay;
  - conferencia de fontes sintetica com os campos do contrato conferencia-fontes/1.
Nada de material de cliente: nomes, cores e fontes sao inventados.
"""
import io
import struct
from pathlib import Path

from PIL import Image, ImageCms
from psd_tools import PSDImage
from psd_tools.constants import Resource, Tag
from psd_tools.psd.descriptor import Bool, Descriptor, DescriptorBlock, Double, Enumerated, UnitFloat
from psd_tools.psd.image_resources import ImageResource

import sinteticos

# primarios do Adobe RGB (1998) adaptados a D50 (Bradford), como no perfil publicado pela Adobe
ADOBE_D50 = ((0.60974, 0.31111, 0.01947), (0.20528, 0.62567, 0.06087), (0.14919, 0.06322, 0.74457))
BRANCO_D50 = (0.96420, 1.0, 0.82491)
GAMA_ADOBE = 563 / 256


def _s15(v):
    return struct.pack('>i', int(round(v * 65536)))


def _xyz(x, y, z):
    return b'XYZ ' + b'\0' * 4 + _s15(x) + _s15(y) + _s15(z)


def _desc(texto):
    t = texto.encode('ascii') + b'\0'
    return b'desc' + b'\0' * 4 + struct.pack('>I', len(t)) + t + b'\0' * 4 + b'\0' * 4 + b'\0' * 67


def _curva(gama):
    return b'curv' + b'\0' * 4 + struct.pack('>I', 1) + struct.pack('>H', int(round(gama * 256))) + b'\0\0'


def perfil_matriz(nome, colorantes, gama):
    """Perfil ICC v2 de matriz e curva (classe mntr, RGB para XYZ)."""
    tags = [(b'desc', _desc(nome)), (b'wtpt', _xyz(*BRANCO_D50)), (b'rXYZ', _xyz(*colorantes[0])),
            (b'gXYZ', _xyz(*colorantes[1])), (b'bXYZ', _xyz(*colorantes[2])), (b'rTRC', _curva(gama)),
            (b'gTRC', _curva(gama)), (b'bTRC', _curva(gama)), (b'cprt', b'text\0\0\0\0sintetico\0\0\0')]
    deslocamento = 128 + 4 + 12 * len(tags)
    tabela, corpo = b'', b''
    for assinatura, dados in tags:
        while (deslocamento + len(corpo)) % 4:
            corpo += b'\0'
        tabela += assinatura + struct.pack('>II', deslocamento + len(corpo), len(dados))
        corpo += dados
    tamanho = deslocamento + len(corpo)
    cab = (struct.pack('>I', tamanho) + b'lcms' + bytes([2, 0x10, 0, 0]) + b'mntr' + b'RGB ' + b'XYZ '
           + b'\0' * 12 + b'acsp' + b'MSFT' + b'\0' * 4 + b'\0' * 4 + b'\0' * 4 + b'\0' * 8 + b'\0' * 4
           + _s15(BRANCO_D50[0]) + _s15(BRANCO_D50[1]) + _s15(BRANCO_D50[2]) + b'\0' * 4 + b'\0' * 16 + b'\0' * 28)
    assert len(cab) == 128
    return cab + struct.pack('>I', len(tags)) + tabela + corpo


def icc_adobe_rgb():
    return perfil_matriz('Adobe RGB sintetico', ADOBE_D50, GAMA_ADOBE)


def icc_srgb():
    return ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()


def icc_monitor():
    """Perfil de monitor inventado: primarios proximos do sRGB e gama 2,0."""
    srgb_d50 = ((0.4361, 0.2225, 0.0139), (0.3851, 0.7169, 0.0971), (0.1431, 0.0606, 0.7141))
    return perfil_matriz('Monitor sintetico', srgb_d50, 2.0)


def adobe_para_srgb_referencia(rgb):
    """Referencia independente do LittleCMS: Adobe RGB -> XYZ D50 -> Bradford D65 -> sRGB com a curva da norma."""
    lin = [(c / 255.0) ** GAMA_ADOBE for c in rgb]
    xyz50 = [sum(ADOBE_D50[j][i] * lin[j] for j in range(3)) for i in range(3)]
    d50_d65 = ((0.9555766, -0.0230393, 0.0631636), (-0.0282895, 1.0099416, 0.0210077), (0.0122982, -0.0204830, 1.3299098))
    xyz65 = [sum(d50_d65[i][k] * xyz50[k] for k in range(3)) for i in range(3)]
    m = ((3.2404542, -1.5371385, -0.4985314), (-0.9692660, 1.8760108, 0.0415560), (0.0556434, -0.2040259, 1.0572252))
    out = []
    for i in range(3):
        v = max(0.0, min(1.0, sum(m[i][k] * xyz65[k] for k in range(3))))
        v = 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
        out.append(v * 255.0)
    return out


# ------------------------------------------------------------------ PSD
COR_FUNDO = (40, 160, 90)
COR_SOLIDA = (200, 30, 60)
COR_OVERLAY = (10, 20, 230)
CORPO_TEXTO = 24.0
ESCALA_H, ESCALA_V = 1.0, 2.0


def _rgbc(rgb):
    return Descriptor(name='', classID=b'RGBC', items=[(b'Rd  ', Double(float(rgb[0]))),
                                                             (b'Grn ', Double(float(rgb[1]))),
                                                             (b'Bl  ', Double(float(rgb[2])))])


def _com_icc(psd, icc):
    if icc is not None:
        psd._record.image_resources[Resource.ICC_PROFILE] = ImageResource(key=Resource.ICC_PROFILE, name='', data=icc)


def psd_de_cor(pasta, icc=None, nome='cor.psd', com_overlay=True):
    """PSD 120 x 80: fundo chapado, cor solida, texto (matriz com escala vertical 2), recorte em alfa, foto sem
    recorte e uma camada com overlay de cor. Devolve o caminho."""
    p = PSDImage.new('RGB', (120, 80), color=(255, 255, 255))
    _com_icc(p, icc)
    p.create_pixel_layer(Image.new('RGBA', (120, 80), COR_FUNDO + (255,)), name='fundo-chapado')
    solida = p.create_pixel_layer(Image.new('RGBA', (20, 20), COR_SOLIDA + (255,)), name='cor-solida', top=5, left=5)
    soco = DescriptorBlock(name='', classID=b'null', items=[(b'Clr ', _rgbc(COR_SOLIDA))])
    solida._record.tagged_blocks.set_data(Tag.SOLID_COLOR_SHEET_SETTING, soco)
    recorte = Image.new('RGBA', (40, 40), (0, 0, 0, 0))
    recorte.paste(Image.new('RGBA', (16, 22), (250, 200, 10, 255)), (10, 8))
    recorte.paste(Image.new('RGBA', (3, 3), (250, 200, 10, 255)), (35, 35))  # componente menor, fica de fora
    from psd_tools.api.layers import PixelLayer
    p.append(PixelLayer.frompil(recorte, p, 'recorte-alfa', top=30, left=70))
    p.create_pixel_layer(Image.new('RGBA', (30, 20), (90, 90, 90, 255)), name='foto-sem-recorte', top=50, left=5)
    t = p.create_pixel_layer(Image.new('RGBA', (60, 30), (20, 20, 20, 255)), name='texto-sintetico', top=40, left=30)
    sinteticos._virar_texto(t, [('Texto sintetico', 0, False)], corpo=CORPO_TEXTO)
    tysh = t._record.tagged_blocks.get_data(Tag.TYPE_TOOL_OBJECT_SETTING)
    tysh.transform = (ESCALA_H, 0.0, 0.0, ESCALA_V, 30.0, 60.0)
    if com_overlay:
        ov = p.create_pixel_layer(Image.new('RGBA', (10, 10), (0, 0, 0, 255)), name='com-overlay', top=2, left=100)
        _overlay(ov, COR_OVERLAY)
    return sinteticos._salvar(p, Path(pasta) / nome)


def _overlay(camada, rgb):
    from psd_tools.psd.descriptor import DescriptorBlock2
    from psd_tools.psd.tagged_blocks import TaggedBlock
    sofi = Descriptor(name='', classID=b'SoFi', items=[
        (b'enab', Bool(True)), (b'present', Bool(True)), (b'showInDialog', Bool(True)),
        (b'Md  ', Enumerated(typeID=b'BlnM', enum=b'Nrml')), (b'Clr ', _rgbc(rgb)),
        (b'Opct', UnitFloat(unit=b'#Prc', value=100.0))])
    raiz = DescriptorBlock2(name='', classID=b'null', version=0, items=[
        (b'Scl ', UnitFloat(unit=b'#Prc', value=100.0)), (b'masterFXSwitch', Bool(True)), (b'SoFi', sofi)])
    camada._record.tagged_blocks[Tag.OBJECT_BASED_EFFECTS_LAYER_INFO] = TaggedBlock(
        key=Tag.OBJECT_BASED_EFFECTS_LAYER_INFO, data=raiz)


def interno_com_perfil(icc):
    """PSB interno de um smart object embutido, com perfil proprio."""
    from psd_tools.api.layers import PixelLayer
    p = PSDImage.new('RGB', (64, 48), color=(255, 255, 255))
    p._record.header.version = 2
    _com_icc(p, icc)
    p.append(PixelLayer.frompil(Image.new('RGBA', (64, 48), (180, 40, 40, 255)), p, 'fundo-interno', top=0, left=0))
    buf = io.BytesIO()
    p.save(buf)
    return buf.getvalue()


# ------------------------------------------------------------------ conferencia de fontes
def conferencia(layer_id, job_id='0' * 32, arquivo_sha256='b' * 64, nome_ps=sinteticos.FONTE_SINTETICA, situacao='ok'):
    """fontes/conferencia.json sintetica, valida pelo contrato conferencia-fontes/1."""
    return {
        'esquema': 'conferencia-fontes/1', 'job_id': job_id, 'gerado_em': '2026-10-30T12:00:00',
        'laudo_sha256': 'c' * 64, 'arquivo_sha256': arquivo_sha256, 'licencas_sha256': None, 'limites': [],
        'chromium': {'feito': False, 'motivo': 'sintetico', 'versao': None, 'playwright': None},
        'faces': [{'id': 'f01', 'nome_ps': nome_ps, 'familia': 'Fonte Inventada', 'estilo': 'Bold',
                   'formato': 'otf', 'sha256': 'a' * 64, 'versao_name': 'Version 1.000', 'peso_declarado': 700,
                   'metricas': {'unidades_por_em': 1000, 'ascender': 800, 'descender': -200, 'cap_height': 700,
                                'x_height': 500, 'entrelinha_tipo': 1200},
                   'situacao': situacao, 'motivos': []}],
        'camadas': [{'layer_id': layer_id, 'nome_ps': nome_ps, 'face_id': 'f01', 'glifos_faltando': 0,
                     'largura_erro_max_pct': 0.01, 'face_cdp_confere': True, 'situacao': situacao, 'motivos': []}],
        'arquivos': [{'sha256': 'a' * 64, 'formato': 'otf', 'situacao': 'aceito', 'motivo': None}],
        'cache': {'feito': False, 'copias_encontradas': None, 'metodo': 'sintetico'},
        'varredura': {'arquivos_de_fonte_fora_da_entrada': 0, 'arquivos_varridos': 0},
        'resumo': {},
    }
