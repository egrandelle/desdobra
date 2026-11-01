# -*- coding: utf-8 -*-
"""Mistura do texto com gama, como o Photoshop faz com "Blend Text Colors Using Gamma" (decisoes-v1.md, 29/10, 9).

Formula da pesquisa (pesquisa/render-local-pesquisa.md, 3; render/r06_formula_referencia.py da pesquisa, levada
como esta). Por canal, com os valores do documento v em 0..1 e a = cobertura x opacidade x preenchimento:
    L = TRC_doc(v)                         (decodifica para luz linear com a curva do perfil do documento)
    y = a * L_f ** (1/G) + (1 - a) * L_b ** (1/G)
    v_saida = TRC_doc^-1(y ** G)
G vem do registro (render.gama, 1,45). Um unico G, de 1,444 a 1,452, serviu a todas as camadas testadas. Para curva
de gama pura g (Adobe RGB: 563/256), o modelo vira potencia nos valores do documento com k = g / G.

So numpy: roda no processo filho do render (desdobra.render.filho) e nos testes.
"""
import numpy as np


def srgb_dec(v):
    v = np.asarray(v, dtype=np.float64)
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)  # numero-neutro: curva sRGB (IEC 61966-2-1)


def srgb_enc(x):
    x = np.clip(np.asarray(x, dtype=np.float64), 0, 1)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * x ** (1 / 2.4) - 0.055)  # numero-neutro: curva sRGB (IEC 61966-2-1)


def curva_gama(g):
    """(decodifica, codifica) de uma curva de gama pura."""
    g = float(g)
    return (lambda v: np.clip(np.asarray(v, dtype=np.float64), 0, 1) ** g,
            lambda x: np.clip(np.asarray(x, dtype=np.float64), 0, 1) ** (1 / g))


CURVA_SRGB = (srgb_dec, srgb_enc)


def mistura_texto_photoshop(fg, bg, a, G, curva_doc):
    """fg, bg: valores do documento em 0..1 (broadcast por canal); a: cobertura 0..1 (com eixo de canal);
    curva_doc: (decodifica, codifica) da curva do perfil do documento. G=None devolve a mistura linear nos valores
    do documento (opcao desligada no Photoshop)."""
    fg = np.asarray(fg, dtype=np.float64)
    bg = np.asarray(bg, dtype=np.float64)
    a = np.asarray(a, dtype=np.float64)
    if G is None:
        return a * fg + (1 - a) * bg
    dec, enc = curva_doc
    y = a * dec(fg) ** (1 / G) + (1 - a) * dec(bg) ** (1 / G)
    return enc(y ** G)
