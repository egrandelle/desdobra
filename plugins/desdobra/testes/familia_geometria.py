# -*- coding: utf-8 -*-
"""Geometrias sinteticas da familia (decisao 199; etapas E1 e E2), so numeros, nenhum PSD e nenhum job.

caso_diagonal(): a geometria do job de 18/11 que o Duda mediu, sem nada do arquivo dele. Arquivo de edicao 1080x1920
com margem de 55 px; fundo branco; faixa verde a esquerda (12% da largura, sangra no topo, na base e a esquerda);
forma azul por baixo da faixa, com a borda diagonal de (1080, 1286) a (130, 1900), formando a area branca no canto de
baixo a direita (o asset passa do canvas em cima e a direita); titulo de 2 linhas no alto a esquerda, texto de 4
linhas abaixo, os dois no azul; assinatura [525, 1651, 1025, 1801] no branco, 5,3 px da diagonal.
"""
import math

W_REF, H_REF = 1080.0, 1920.0
MARGEM_REF = 55.0
P1, P2 = (1080.0, 1286.0), (130.0, 1900.0)  # a diagonal medida
INCLINACAO = (P2[1] - P1[1]) / (P2[0] - P1[0])
ASSINATURA = [525.0, 1651.0, 1025.0, 1801.0]
TODOS = {'esq': True, 'topo': True, 'dir': True, 'base': True}


def y_da_diagonal(x):
    return P1[1] + (x - P1[0]) * INCLINACAO


def quadros(W, H, margem_rel=MARGEM_REF / W_REF, area_segura=None):
    """A margem como a galeria a faz (fracao do lado curto) e a area segura (sem folha, a propria margem)."""
    m = margem_rel * min(W, H)
    margem = [m, m, W - m, H - m]
    if area_segura is not None:
        margem = [max(margem[0], area_segura[0]), max(margem[1], area_segura[1]), min(margem[2], area_segura[2]),
                  min(margem[3], area_segura[3])]
    return {'margem': margem, 'area_segura': list(area_segura) if area_segura is not None else list(margem)}


def membro(fid, W, H, giro=0, **kw):
    return {'id': fid, 'W': float(W), 'H': float(H), 'giro': giro, 'quadros': quadros(float(W), float(H), **kw)}


def em_fracao(pontos, asset):
    a = asset
    return [[(x - a[0]) / (a[2] - a[0]), (y - a[1]) / (a[3] - a[1])] for x, y in pontos]


AZUL_ASSET = [0.0, -100.0, 1180.0, 1900.0]
AZUL_PONTOS = [(0.0, -100.0), (1180.0, -100.0), (1180.0, y_da_diagonal(1180.0)), P2, (0.0, 1900.0)]


def grade_do_poligono(pontos, asset, colunas, linhas):
    """A silhueta em grade de um poligono convexo por partes (amostra do centro de cada celula)."""
    def dentro(x, y):
        c = False
        n = len(pontos)
        for i in range(n):
            (x0, y0), (x1, y1) = pontos[i - 1], pontos[i]
            if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                c = not c
        return c
    a = asset
    cel = []
    for j in range(linhas):
        y = a[1] + (a[3] - a[1]) * (j + 0.5) / linhas
        cel.append(''.join('1' if dentro(a[0] + (a[2] - a[0]) * (i + 0.5) / colunas, y) else '0'
                           for i in range(colunas)))
    return {'grade': {'colunas': colunas, 'linhas': linhas, 'celulas': cel}}


def caso_diagonal(silhueta='poligono', com_ds=True):
    """(referencia, elementos, silhuetas) do caso de 18/11, so numeros."""
    ref = {'id': 'f1080x1920', 'W': W_REF, 'H': H_REF, 'quadros': quadros(W_REF, H_REF)}
    els = [
        {'id': 'fundo', 'classe': 'base', 'funcao': 'fundo', 'caixa': [0.0, 0.0, W_REF, H_REF], 'sangra': dict(TODOS)},
        {'id': 'azul', 'classe': 'base', 'funcao': 'grafismo', 'caixa': [0.0, 0.0, W_REF, 1900.0],
         'caixa_asset': list(AZUL_ASSET), 'sangra': {'esq': True, 'topo': True, 'dir': True, 'base': False}},
        {'id': 'verde', 'classe': 'base', 'funcao': 'grafismo', 'caixa': [0.0, 0.0, 130.0, H_REF],
         'caixa_asset': [-20.0, -20.0, 130.0, H_REF + 20.0],
         'sangra': {'esq': True, 'topo': True, 'dir': False, 'base': True}},
        {'id': 'titulo', 'classe': 'texto', 'funcao': 'titulo', 'caixa': [190.0, 150.0, 800.0, 450.0],
         'sangra': {}, 'ancora': ('esquerda', 'topo') if com_ds else None},
        {'id': 'texto', 'classe': 'texto', 'funcao': 'texto_de_apoio', 'caixa': [190.0, 520.0, 760.0, 900.0],
         'sangra': {}, 'ancora': ('esquerda', 'topo') if com_ds else None},
        {'id': 'assinatura', 'classe': 'marca', 'funcao': 'assinatura_institucional', 'caixa': list(ASSINATURA),
         'sangra': {}, 'ancora': ('direita', 'base') if com_ds else None},
    ]
    if silhueta == 'poligono':
        sil = {'azul': {'poligono': em_fracao(AZUL_PONTOS, AZUL_ASSET)}}
    elif silhueta == 'grade':
        sil = {'azul': grade_do_poligono(AZUL_PONTOS, AZUL_ASSET, 236, 400)}
    else:
        sil = {}
    return ref, els, sil


def membros_do_caso():
    """Os arquivos da familia do caso: o de edicao, o 300x600, os dois girados e as pontas da faixa de 0,3."""
    return [membro('f1080x1920', 1080, 1920), membro('f300x600', 300, 600),
            membro('g1920x1080r270', 1080, 1920, giro=270), membro('g640x360r90', 360, 640, giro=90),
            membro('f1080x1600', 1080, 1600), membro('f900x1870', 900, 1870)]


def distancia_a_reta(p, origem, inclinacao):
    """Distancia com sinal do ponto p a reta (positivo: abaixo dela, no y da tela)."""
    return (p[1] - (origem[1] + (p[0] - origem[0]) * inclinacao)) / math.sqrt(1 + inclinacao * inclinacao)
