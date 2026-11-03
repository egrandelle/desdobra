# -*- coding: utf-8 -*-
"""Regras de escala por funcao (pesquisa/corpus-testes.md, 4, item 17) e orientacao dos formatos.

A regra de escala e escolhida pelo DA, por funcao (e por camada no "indeterminado"), e entra no solver como
restricao fraca (arquitetura-v1.md, 4.10). Cada regra da a escala prevista de um elemento a partir das dimensoes
da base do calculo na mestre (wm, hm) e no formato (wf, hf):
  largura: wf/wm; altura: hf/hm; lado_curto e lado_longo: pelo menor e pelo maior lado; raiz_area: raiz da razao
  das areas; constante: 1; contain: o menor entre largura e altura; cover: o maior.
"""
import math

from desdobra import limites

REGRAS = ('largura', 'altura', 'lado_curto', 'lado_longo', 'raiz_area', 'constante', 'contain', 'cover')
ORIENTACOES = ('horizontal', 'quadrado', 'vertical')


def escala(regra, mestre, formato):
    """Escala prevista pela regra. mestre e formato: (largura, altura) da base do calculo."""
    wm, hm = (float(v) for v in mestre)
    wf, hf = (float(v) for v in formato)
    if regra == 'largura':
        return wf / wm
    if regra == 'altura':
        return hf / hm
    if regra == 'lado_curto':
        return min(wf, hf) / min(wm, hm)
    if regra == 'lado_longo':
        return max(wf, hf) / max(wm, hm)
    if regra == 'raiz_area':
        return math.sqrt(wf * hf / (wm * hm))
    if regra == 'constante':
        return 1.0
    if regra == 'contain':
        return min(wf / wm, hf / hm)
    if regra == 'cover':
        return max(wf / wm, hf / hm)
    raise ValueError('regra de escala desconhecida: %r' % regra)


def residuo(observada, prevista):
    """|ln(observada / prevista)|, a medida de residuo da pesquisa (corpus-testes.md, 4, item 15)."""
    return abs(math.log(float(observada) / float(prevista)))


def orientacao(largura, altura):
    """horizontal, quadrado ou vertical, pela banda derivacao.quadrado_ln_max em torno do quadrado."""
    ln = math.log(float(largura) / float(altura))
    if abs(ln) <= limites.valor('derivacao.quadrado_ln_max'):
        return 'quadrado'
    return 'horizontal' if ln > 0 else 'vertical'


def troca_de_orientacao(mestre, formato):
    """None (mesma orientacao), 'forte' (horizontal para vertical ou o contrario) ou 'quadrado' (para ou de
    quadrado). As duas pedem mestre propria (pesquisa/corpus-testes.md, 4, item 16)."""
    om, of = orientacao(*mestre), orientacao(*formato)
    if om == of:
        return None
    return 'quadrado' if 'quadrado' in (om, of) else 'forte'


def fator_de_proporcao(mestre, formato):
    """A maior sobre a menor das duas proporcoes (largura sobre altura): 1 quando iguais."""
    rm = float(mestre[0]) / float(mestre[1])
    rf = float(formato[0]) / float(formato[1])
    return max(rm, rf) / min(rm, rf)
