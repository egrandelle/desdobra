# -*- coding: utf-8 -*-
"""Efeitos de camada e ajustes que o compositor do psd-tools 1.26.0 desenha, conferidos no codigo instalado.

Conferencia (M1, refaz a lista que pesquisa/v1-estatico-sintese.md, 3 mediu na 1.17.4):
  - efeitos: psd_tools/composite/composite.py desenha os tres overlays da tabela _OVERLAY_DRAWS
    (coloroverlay, patternoverlay, gradientoverlay) e o traco (stroke, _add_stroke_effects). O proprio modulo
    diz que sombra projetada, sombra interna, os dois brilhos, cetim e chanfro nao sao desenhados
    (Compositor._compose_effects, TODO; _stroke_reach). Os 10 tipos que a API le estao em
    psd_tools/api/effects.py;
  - pacotes: gradiente (paint.draw_gradient_fill, @require_scipy) e traco de efeito (effects.py, scipy.ndimage)
    pedem scipy; o padrao (paint.draw_pattern_fill) usa so numpy e PIL; o traco vetorial de forma pede aggdraw
    (composite/_compat.py, require_aggdraw); preencher um caminho vetorial nao pede aggdraw (scanline.py);
  - ajustes: entram no composto os 8 tipos de ADJUSTMENT_FUNC (composite/adjustments.py), e so nos modos
    RGB, CMYK e tons de cinza (Compositor._apply_adjustment). brightnesscontrast, curves e huesaturation pedem
    scipy. Os outros 8 tipos sao lidos pela API (api/adjustments.py) e ficam fora do composto;
  - mesclagem dissolve: blend.py troca por normal ('Dissolve blend is not implemented');
  - pass-through com mascara ou opacidade: corrigido desde a 1.19 (pesquisa/render-local-pesquisa.md, 9), por
    isso a regra D9 da sonda foi aposentada.

O teste test_laudo_efeitos.py confere estas listas contra o psd-tools instalado.
"""
VERSAO_CONFERIDA = '1.26.0'
FONTE = 'psd-tools 1.26.0: composite/composite.py, composite/adjustments.py, composite/paint.py, api/effects.py'

# nome da classe na API (api/effects.py) -> pacote opcional de que o desenho depende (None = nenhum)
EFEITOS_DESENHADOS = {
    'ColorOverlay': None,
    'GradientOverlay': 'scipy',
    'PatternOverlay': None,
    'Stroke': 'scipy',
}
EFEITOS_NAO_DESENHADOS = ('DropShadow', 'InnerShadow', 'OuterGlow', 'InnerGlow', 'Satin', 'BevelEmboss')
EFEITOS_LIDOS = tuple(sorted(list(EFEITOS_DESENHADOS) + list(EFEITOS_NAO_DESENHADOS)))

# kind do psd-tools -> pacote opcional de que o ajuste depende
AJUSTES_NO_COMPOSTO = {
    'brightnesscontrast': 'scipy',
    'curves': 'scipy',
    'exposure': None,
    'huesaturation': 'scipy',
    'invert': None,
    'levels': None,
    'posterize': None,
    'threshold': None,
}
AJUSTES_FORA_DO_COMPOSTO = ('blackandwhite', 'channelmixer', 'colorbalance', 'colorlookup', 'gradientmap',
                            'photofilter', 'selectivecolor', 'vibrance')
MODOS_COM_AJUSTE = ('RGB', 'CMYK', 'GRAYSCALE')

# preenchimentos sem pixel guardado que o compositor desenha, e o pacote de que dependem
PREENCHIMENTOS = {'solidcolorfill': None, 'gradientfill': 'scipy', 'patternfill': None}
PACOTE_TRACO_VETORIAL = 'aggdraw'


def efeito_desenhado(tipo, pacotes):
    """(desenhado, pacote_ausente) para um efeito pelo nome da classe."""
    if tipo not in EFEITOS_DESENHADOS:
        return False, None
    pacote = EFEITOS_DESENHADOS[tipo]
    if pacote and not pacotes.get(pacote, False):
        return False, pacote
    return True, None


def ajuste_no_composto(kind, modo, pacotes):
    """(entra, motivo) para um ajuste pelo kind do psd-tools e o modo de cor do documento."""
    if kind not in AJUSTES_NO_COMPOSTO:
        return False, 'tipo fora dos que o compositor aplica'
    if modo not in MODOS_COM_AJUSTE:
        return False, 'modo de cor sem ajuste no compositor'
    pacote = AJUSTES_NO_COMPOSTO[kind]
    if pacote and not pacotes.get(pacote, False):
        return False, 'exige %s, ausente' % pacote
    return True, None


def descricao():
    """O que o laudo grava em efeitos_suportados."""
    return {'efeitos': sorted(EFEITOS_DESENHADOS), 'ajustes': sorted(AJUSTES_NO_COMPOSTO), 'fonte': FONTE}
