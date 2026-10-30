# -*- coding: utf-8 -*-
"""Adaptador: o unico modulo do leitor que toca partes internas do psd-tools (atributos com sublinhado,
tabelas do compositor, leitores de baixo nivel). Conferido contra o psd-tools 1.26.0 instalado.

Por que existe (arquitetura-v1.md, 4.3): a ida da 1.17.4 para a 1.26.0 exigiu dois ajustes na sonda da
pesquisa, ambos em partes internas. Concentrando tudo aqui, a proxima atualizacao mexe num arquivo so, e a
regressao (desdobra regressao) mostra o que mudou.

So o processo filho importa este modulo.
"""
import contextlib
import io

import psd_tools
from psd_tools.api.utils import MAX_DIMENSION_PSD
from psd_tools.composite import _compat
from psd_tools.composite import utils as comp_utils
from psd_tools.composite.adjustments import ADJUSTMENT_FUNC
from psd_tools.constants import ColorMode, Tag
from psd_tools.psd import bin_utils
from psd_tools.psd.descriptor import DescriptorBlock, Enumerated
from psd_tools.psd.parse_limits import ParseLimitError, ParseLimits, parse_context
from psd_tools.psd.tagged_blocks import TaggedBlock

VERSAO_ADAPTADOR = '1.26.0-1'
VERSAO_PSD_TOOLS_CONFERIDA = '1.26.0'

# Eixo maximo que o proprio psd-tools aceita (api/utils.py, check_pixel_size): vale para PSD e PSB.
EIXO_MAX_PSD_TOOLS = MAX_DIMENSION_PSD

CHAVES_SMART = (Tag.LINKED_LAYER1, Tag.LINKED_LAYER2, Tag.LINKED_LAYER3, Tag.LINKED_LAYER_EXTERNAL)
CHAVES_SMART_BYTES = tuple(k.value for k in CHAVES_SMART)

# Modos em que o compositor aplica ajuste (composite/composite.py, Compositor._apply_adjustment).
MODOS_COM_AJUSTE = (ColorMode.CMYK, ColorMode.GRAYSCALE, ColorMode.RGB)


def pacotes_opcionais():
    """Pacotes opcionais do composto, como o proprio psd-tools os enxerga (composite/_compat.py)."""
    return {'aggdraw': bool(_compat.HAS_AGGDRAW), 'scipy': bool(_compat.HAS_SCIPY)}


def versao_psd_tools():
    return psd_tools.__version__


def ajustes_do_compositor():
    """Tipos de ajuste que o compositor aplica: chaves de ADJUSTMENT_FUNC (composite/adjustments.py)."""
    return sorted(ADJUSTMENT_FUNC)


def overlays_do_compositor():
    """Overlays que o compositor desenha (composite/composite.py, _OVERLAY_DRAWS)."""
    return sorted(modulo_compositor()._OVERLAY_DRAWS)


def modulo_compositor():
    """O modulo psd_tools.composite.composite (o pacote exporta uma funcao com o mesmo nome)."""
    import importlib
    return importlib.import_module('psd_tools.composite.composite')


def limites_de_parse(orcamento_bytes):
    """ParseLimits do psd-tools 1.26.0. Os tetos de objetos e de aninhamento ficam no padrao da biblioteca; o
    total de bytes materializados fica no orcamento do filho."""
    padrao = ParseLimits()
    return ParseLimits(max_read_bytes=None, max_total_bytes=int(orcamento_bytes), max_objects=padrao.max_objects,
                       max_nesting_depth=padrao.max_nesting_depth)


def eh_estouro_de_orcamento(exc):
    """True quando a excecao e um limite de memoria do psd-tools, e nao arquivo corrompido.

    O psd-tools 1.26.0 levanta ValueError com 'over the configured budget' quando a estimativa passa de
    max_alloc_bytes (api/utils.py, check_pixel_size) e ParseLimitError com 'max_total_bytes' ou
    'max_read_bytes' quando o parse passa do teto de bytes (psd/parse_limits.py)."""
    if isinstance(exc, MemoryError):
        return True
    texto = str(exc)
    if isinstance(exc, ParseLimitError):
        return 'max_total_bytes' in texto or 'max_read_bytes' in texto
    return isinstance(exc, ValueError) and 'configured budget' in texto


def formato_do_comprimento(chave, versao):
    """'I' ou 'Q': o mesmo criterio que o psd-tools usa para ler o comprimento de um bloco marcado."""
    try:
        chave = Tag(chave)
    except ValueError:
        pass
    return TaggedBlock._length_format(chave, versao)


# ------------------------------------------------------------------ leitura de baixo nivel dos registros lnk*
@contextlib.contextmanager
def contexto_de_parse():
    with parse_context(ParseLimits()):
        yield


def ler_fmt(fmt, fp):
    return bin_utils.read_fmt(fmt, fp)


def ler_pascal(fp):
    return bin_utils.read_pascal_string(fp, 'macroman', padding=1)


def ler_unicode(fp):
    return bin_utils.read_unicode_string(fp)


def pular_descritor(fp):
    """Le um DescriptorBlock (padding 1) so para andar no arquivo. Devolve as chaves de primeiro nivel."""
    d = DescriptorBlock.read(fp, padding=1)
    return [k.decode('latin-1') if isinstance(k, bytes) else str(k) for k in d.keys()]


# ------------------------------------------------------------------ acesso a partes internas da API
def dados_texto(layer):
    """TypeToolObjectSetting da camada de texto (TypeLayer._data)."""
    return layer._data


def estilo_cru(estilo, chave):
    """Valor cru de uma chave do estilo de um trecho: o do trecho, senao o padrao da camada (psd-tools 1.26)."""
    dados = getattr(estilo, '_data', None)
    v = dados.get(chave) if dados else None
    if v is None:
        padrao = getattr(estilo, '_default', None)
        if padrao:
            v = padrao.get(chave)
    return v


def registro_smart(layer):
    """(config SoLd/SoLE, PlacedLayer) da camada de smart object, sem tocar nos dados ligados."""
    so = layer.smart_object
    return so._config, so._placed_layer


def tem_preenchimento(layer):
    return comp_utils.has_fill(layer)


def pixels_de_mascara(mascara):
    """PIL da mascara raster no tamanho da camada (real quando existe)."""
    return mascara.topil(real=True, layer_sized=True)


def enum_texto(v):
    if isinstance(v, Enumerated):
        e = v.enum
        return e.decode('latin-1') if isinstance(e, bytes) else str(e)
    return v


def bytes_io(dados):
    return io.BytesIO(dados)
