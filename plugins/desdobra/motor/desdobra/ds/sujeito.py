# -*- coding: utf-8 -*-
"""Caixa do sujeito pelo alfa (pesquisa/corpus-testes.md, 4, item 19).

  - com recorte em alfa, o limiar no maior componente conexo da a caixa certa (limite ds.sujeito_limiar_alfa);
  - com o sujeito fundido a foto, nao ha metodo confiavel: o motor pede a caixa ao DA.

A camada nao tem recorte quando nenhum pixel fica abaixo do limiar (o alfa nao separa nada da foto). Um recorte que
encosta nas quatro bordas da camada (uma foto recortada em elipse, por exemplo) continua sendo recorte: a caixa
sai do maior componente. A funcao "sujeito" continua sendo confirmada pelo DA no
briefing: aqui so se mede a caixa de cada candidata.
"""
import numpy as np

from desdobra import limites

METODO_ALFA = 'alfa'
METODO_PEDIR_AO_DA = 'pedir_ao_da'
METODO_SEM_TINTA = 'sem_tinta'
VIZINHANCA_8 = np.ones((3, 3), bool)  # numero-neutro: vizinhanca de 8 pixels dos componentes conexos

MOTIVO_FUNDIDO = ('o alfa da camada não separa o sujeito da foto (sem recorte): o sujeito está fundido à foto, e o '
                  'DA marca a caixa do sujeito')


def caixa_por_alfa(alfa, origem_xy=(0, 0)):
    """alfa: matriz uint8 (altura x largura) da camada; origem_xy: canto da camada no documento.

    Devolve {'metodo', 'caixa', 'medidas', 'limiar', 'motivo'}; caixa em pixels do documento, x1 e y1 exclusivos."""
    from scipy import ndimage
    lim = limites.obter('ds.sujeito_limiar_alfa')
    alfa = np.asarray(alfa)
    h, w = alfa.shape[:2]
    mascara = alfa >= lim.valor
    n_opacos = int(mascara.sum())
    medidas = {'px_camada': int(h * w), 'px_acima_do_limiar': n_opacos, 'n_componentes': 0, 'px_maior_componente': 0}
    base = {'metodo': None, 'caixa': None, 'medidas': medidas, 'limiar': lim.citacao(), 'motivo': None}
    if n_opacos == 0:
        return dict(base, metodo=METODO_SEM_TINTA, motivo='nenhum pixel da camada chega ao limiar de alfa')
    if n_opacos == h * w:
        return dict(base, metodo=METODO_PEDIR_AO_DA, motivo=MOTIVO_FUNDIDO)
    rotulos, n = ndimage.label(mascara, structure=VIZINHANCA_8)
    tamanhos = np.bincount(rotulos.ravel())
    tamanhos[0] = 0
    maior = int(tamanhos.argmax())
    medidas.update(n_componentes=int(n), px_maior_componente=int(tamanhos[maior]))
    fatia = ndimage.find_objects((rotulos == maior).astype(np.int32))[0]
    y0, y1, x0, x1 = fatia[0].start, fatia[0].stop, fatia[1].start, fatia[1].stop
    ox, oy = origem_xy
    return dict(base, metodo=METODO_ALFA, caixa=[int(x0 + ox), int(y0 + oy), int(x1 + ox), int(y1 + oy)])
