# -*- coding: utf-8 -*-
"""Curva de tom (TRC) do perfil ICC do documento, lida dos bytes do perfil (especificacao ICC.1, tags rTRC, gTRC,
bTRC e kTRC, tipos 'curv' e 'para').

O perfil do documento e dado de cliente: este modulo so roda no processo filho do render (desdobra.render.filho),
como o modulo de cor (arquitetura-v1.md, 4.6 e 7.1). Devolve a curva como (decodifica, codifica) para a mistura com
gama (desdobra.render.gama). Documento sem perfil usa a curva sRGB (mesma regra de desdobra.cor).

Sem curva legivel (perfil sem TRC, como perfil so de tabela LUT), o filho cai para a curva sRGB e registra o motivo.
"""
import struct

import numpy as np

TAMANHO_CABECALHO = 128  # numero-neutro: cabecalho do perfil ICC (especificacao ICC.1)
BYTES_CONTAGEM = 4  # numero-neutro: contagem de tags depois do cabecalho (ICC.1)
BYTES_ENTRADA_TAG = 12  # numero-neutro: cada entrada da tabela de tags (ICC.1)
TAGS_TRC = (b'rTRC', b'gTRC', b'bTRC')
TAG_TRC_CINZA = b'kTRC'
PONTOS_INVERSA = 4096  # numero-neutro: amostras da tabela que inverte a curva; nao e regra
# parametros de cada funcao 'para' (ICC.1, 10.18): tipo -> quantidade de numeros s15Fixed16
PARAMETROS_PARA = {0: 1, 1: 3, 2: 4, 3: 5, 4: 7}  # numero-neutro: fato do formato ICC
ESCALA_S15 = 65536.0  # numero-neutro: ponto fixo s15Fixed16
ESCALA_U8F8 = 256.0  # numero-neutro: ponto fixo u8Fixed8
ESCALA_U16 = 65535.0  # numero-neutro: tabela de 16 bits da tag curv


class ErroCurva(Exception):
    pass


def _s15(b):
    return struct.unpack('>i', b)[0] / ESCALA_S15


def _tags(dados):
    inicio = TAMANHO_CABECALHO + BYTES_CONTAGEM
    if len(dados) < inicio:
        raise ErroCurva('perfil curto demais')
    n = struct.unpack('>I', dados[TAMANHO_CABECALHO:inicio])[0]
    out = {}
    for i in range(n):
        p = inicio + BYTES_ENTRADA_TAG * i
        if p + BYTES_ENTRADA_TAG > len(dados):
            raise ErroCurva('tabela de tags truncada')
        sig, desl, tam = struct.unpack('>4sII', dados[p:p + BYTES_ENTRADA_TAG])
        if desl + tam > len(dados):
            raise ErroCurva('tag fora do perfil')
        out[sig] = (desl, tam)
    return out


def _clip(v):
    return np.clip(np.asarray(v, dtype=np.float64), 0, 1)


def _curv(corpo):
    n = struct.unpack('>I', corpo[8:12])[0]  # numero-neutro: layout da tag curv
    if n == 0:
        return _clip, {'tipo': 'curv', 'pontos': 0}
    if n == 1:
        g = struct.unpack('>H', corpo[12:14])[0] / ESCALA_U8F8  # numero-neutro: layout da tag curv
        if not g > 0:
            raise ErroCurva('curva de gama zero')
        return (lambda v: _clip(v) ** g), {'tipo': 'curv', 'gama': g}
    tab = np.frombuffer(corpo[12:12 + 2 * n], dtype='>u2').astype(np.float64) / ESCALA_U16  # numero-neutro: idem
    if len(tab) != n:
        raise ErroCurva('tabela da curva truncada')
    xs = np.linspace(0, 1, n)
    return (lambda v: np.interp(_clip(v), xs, tab)), {'tipo': 'curv', 'pontos': int(n)}


def _para(corpo):
    func = struct.unpack('>H', corpo[8:10])[0]  # numero-neutro: layout da tag para
    if func not in PARAMETROS_PARA:
        raise ErroCurva('funcao para desconhecida')
    k = PARAMETROS_PARA[func]
    if len(corpo) < 12 + 4 * k:  # numero-neutro: layout da tag para
        raise ErroCurva('parametros da curva truncados')
    ps = [_s15(corpo[12 + 4 * i:16 + 4 * i]) for i in range(k)]  # numero-neutro: layout da tag para
    g, a, b, c, d, e, f = (ps + [0.0] * 7)[:7]  # numero-neutro: g, a, b, c, d, e, f da ICC.1
    if not g > 0 or (k != PARAMETROS_PARA[0] and a == 0):
        raise ErroCurva('parametros da curva invalidos')

    def dec(v):
        v = _clip(v)
        if k == PARAMETROS_PARA[0]:
            return v ** g
        lin = np.maximum(a * v + b, 0) ** g
        if k == PARAMETROS_PARA[1]:
            return np.where(v >= -b / a, lin, 0.0)
        if k == PARAMETROS_PARA[2]:
            return np.where(v >= -b / a, lin + c, c)
        if k == PARAMETROS_PARA[3]:
            return np.where(v >= d, lin, c * v)
        return np.where(v >= d, lin + e, c * v + f)
    return dec, {'tipo': 'para', 'funcao': int(func), 'parametros': [round(x, 6) for x in ps]}


def _avaliar(dados, desl, tam):
    """Funcao decodifica (valor do documento -> luz linear) de uma tag curv ou para."""
    corpo = dados[desl:desl + tam]
    if corpo[:4] == b'curv':
        return _curv(corpo)
    if corpo[:4] == b'para':
        return _para(corpo)
    raise ErroCurva('tipo de curva sem suporte')


def _inversa(dec):
    xs = np.linspace(0, 1, PONTOS_INVERSA)
    ys = np.maximum.accumulate(dec(xs))
    return lambda y: np.interp(_clip(y), ys, xs)


def curva_do_perfil(dados):
    """(decodifica, codifica, descricao) da curva do perfil. Usa a curva do canal verde quando os tres canais tem
    curvas diferentes, e registra isso em descricao['canais_iguais']. ErroCurva quando nao ha curva legivel (perfil
    truncado, tag com tamanho errado, gama zero, parametro que divide por zero, curva que nao da numero finito)."""
    try:
        dec, enc, desc = _curva_do_perfil(dados)
        xs = np.linspace(0, 1, PONTOS_INVERSA)
        with np.errstate(all='ignore'):
            ys = dec(xs)
            volta = enc(ys)
        if not (np.all(np.isfinite(ys)) and np.all(np.isfinite(volta))):
            raise ErroCurva('curva sem valor finito')
    except (struct.error, ZeroDivisionError, ValueError, IndexError, OverflowError, TypeError) as e:
        raise ErroCurva('perfil ilegivel (%s)' % type(e).__name__) from None
    return dec, enc, desc


def _curva_do_perfil(dados):
    tags = _tags(dados)
    if all(t in tags for t in TAGS_TRC):
        brutos = [dados[tags[t][0]:tags[t][0] + tags[t][1]] for t in TAGS_TRC]
        dec, desc = _avaliar(dados, *tags[b'gTRC'])
        desc = dict(desc, canais_iguais=brutos[0] == brutos[1] == brutos[2])
    elif TAG_TRC_CINZA in tags:
        dec, desc = _avaliar(dados, *tags[TAG_TRC_CINZA])
        desc = dict(desc, canais_iguais=True)
    else:
        raise ErroCurva('perfil sem curva de tom')
    if 'gama' in desc:
        g = desc['gama']
        enc = lambda x: _clip(x) ** (1 / g)  # noqa: E731
    else:
        enc = _inversa(dec)
    return dec, enc, desc
