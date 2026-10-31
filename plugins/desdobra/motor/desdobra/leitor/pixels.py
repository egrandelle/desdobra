# -*- coding: utf-8 -*-
"""Medidas de pixel no processo filho: caixa de tinta, miniatura, asset, cobertura e prova de pixel.

Cobertura ("coberta no KV", decisoes-v1.md, 29/10, 10): uma passada de cima para baixo pelas folhas da
arvore, mantendo a mascara do canvas ja coberto por pixel opaco. Para cada camada com tinta, mede a fracao
dos pixels visiveis dela que caem dentro dessa mascara antes de somar os pixels opacos dela. Conta como
cobridora so a camada que, com certeza, esconde o que esta embaixo: visivel, mesclagem normal, opacidade e
preenchimento cheios nela e nos grupos acima, sem clipping, sem mascara nos grupos acima e sem mascara
vetorial propria em camada de pixel. A medida e conservadora: pode dizer menos coberta, nunca mais.

Prova de pixel (pesquisa/corpus-testes.md, 2): o merged gravado pelo Photoshop contra a recomposicao do
psd-tools sem a previa, os dois achatados sobre branco, diferenca por canal em 0 a 255. A recomposicao e
feita em faixas horizontais: o resultado e identico ao composto inteiro, com menos memoria (verificado na
pesquisa).
"""
import hashlib
import io
import math

import numpy as np
from PIL import Image

from desdobra import arquivos
from desdobra.leitor import adaptador

PIXELS_POR_FAIXA = 2_000_000  # numero-neutro: tamanho da faixa de recomposicao; nao muda o resultado
FAIXAS_MAX = 8  # numero-neutro: idem (cada faixa redecodifica as camadas que a cruzam)
LINHAS_MIN_FAIXA = 32  # numero-neutro: idem
PIXELS_POR_BLOCO_COMPARACAO = 1_000_000  # numero-neutro: bloco de linhas da comparacao; nao muda o resultado
PIXELS_GRADE_REGIOES = 4_000_000  # numero-neutro: resolucao de trabalho dos componentes conexos (so registro)
AMPLIFICACAO_DIFERENCA = 4  # numero-neutro: so para enxergar o mapa de diferencas
FATOR_FUNDO_DIFERENCA = 0.3  # numero-neutro: idem
COMPRESSAO_PNG = 1  # numero-neutro: nivel de compressao do PNG; nao muda os pixels


def reduzir(img, lado):
    img = img.copy()
    img.thumbnail((lado, lado), Image.Resampling.LANCZOS, reducing_gap=3.0)  # numero-neutro: parametro do PIL
    return img


def png_bytes(img):
    buf = io.BytesIO()
    img.save(buf, format='PNG', compress_level=COMPRESSAO_PNG)
    return buf.getvalue()


def interseccao(a, b):
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    return [x0, y0, x1, y1] if x1 > x0 and y1 > y0 else None


# ------------------------------------------------------------------ passada por camada
class Cobertura:
    def __init__(self, largura, altura):
        self.w, self.h = largura, altura
        self.coberto = np.zeros((altura, largura), dtype=bool)


def _alfa_visivel(L, img):
    """Alfa da camada multiplicado pela mascara raster ativa (real quando existe). uint8, tamanho da camada."""
    alfa = np.asarray(img.getchannel('A'), dtype=np.uint8) if 'A' in img.mode else np.full((img.height, img.width), 255, np.uint8)
    mk = L.mask if L.has_mask() else None
    if mk is not None and not mk.disabled:
        try:
            m_img = adaptador.pixels_de_mascara(mk)
        except Exception:
            m_img = None
        if m_img is not None:
            if m_img.mode != 'L':
                m_img = m_img.convert('L')
            m = np.asarray(m_img, dtype=np.uint16)
            if m.shape == alfa.shape:
                alfa = (alfa.astype(np.uint16) * m // 255).astype(np.uint8)  # numero-neutro: escala de 8 bits
    return alfa


def pode_cobrir(reg, por_id):
    if not reg.get('visivel_efetiva') or reg.get('clipping') or reg.get('blend') != 'NORMAL':
        return False
    if reg.get('opacidade') != 255 or reg.get('preenchimento') != 255:  # numero-neutro: opacidade cheia em 8 bits
        return False
    mk = reg.get('mascara') or {}
    if mk.get('vetorial') and not mk.get('vetorial_desativada') and reg.get('kind') == 'pixel':
        return False
    for gid in reg.get('caminho_ids') or []:
        g = por_id.get(gid)
        if g is None or g.get('opacidade') != 255 or g.get('blend') not in ('NORMAL', 'PASS_THROUGH'):  # numero-neutro: idem
            return False
        gm = g.get('mascara') or {}
        if (gm.get('raster') and not gm.get('desativada')) or (gm.get('vetorial') and not gm.get('vetorial_desativada')):
            return False
    return True


def medir_camada(L, reg, psd, pasta_saida, cobertura, por_id, parametros, contexto):
    """Decodifica os pixels proprios uma vez e mede tudo. Preenche reg['pixels'] e reg['caixa_tinta']."""
    W, H = psd.width, psd.height
    px = {'erro': None, 'pulado': None, 'miniatura': None, 'asset_sha256': None, 'fracao_coberta': None,
          'fracao_canvas': None, 'px_visiveis': None, 'px_cobertos': None, 'px_area_ref': None, 'origem': None}
    reg['pixels'] = px
    reg['caixa_tinta'] = None
    img = None
    try:
        if L.has_pixels():
            img = L.topil()
            px['origem'] = 'pixels_proprios'
        elif cobertura is not None and reg['medidas_regras'].get('preenchimento_sem_pixel') and reg.get('visivel_efetiva'):
            img = L.composite(viewport=(0, 0, W, H))
            if img is not None:
                px['origem'] = 'preenchimento_desenhado'
                img = img.convert('RGBA')
    except Exception as e:
        if adaptador.eh_estouro_de_orcamento(e):
            px['pulado'] = 'orcamento'
        else:
            px['erro'] = type(e).__name__
        return
    if img is None:
        return
    if img.mode not in ('RGB', 'RGBA', 'L', 'LA'):
        img = img.convert('RGBA')
    if px['origem'] == 'preenchimento_desenhado':
        esq, topo = 0, 0
        alfa = np.asarray(img.getchannel('A'), dtype=np.uint8)
    else:
        esq, topo = L.left, L.top
        alfa = _alfa_visivel(L, img)
    nz = np.nonzero(alfa)
    if len(nz[0]):
        reg['caixa_tinta'] = [int(nz[1].min()) + esq, int(nz[0].min()) + topo, int(nz[1].max()) + 1 + esq,
                              int(nz[0].max()) + 1 + topo]
    # area de referencia: o canvas ou, dentro de prancheta, a prancheta (o Photoshop corta o conteudo nela)
    ref = [0, 0, W, H]
    art = por_id.get(reg.get('prancheta_id')) if reg.get('prancheta_id') is not None else None
    if art is not None:
        ref = interseccao(ref, art['caixa']) or [0, 0, 0, 0]
    rc = interseccao(ref, [esq, topo, esq + img.width, topo + img.height]) if ref[2] > ref[0] else None
    mini_rc = rc or interseccao([0, 0, W, H], [esq, topo, esq + img.width, topo + img.height])
    if rc is not None:
        loc = (rc[0] - esq, rc[1] - topo, rc[2] - esq, rc[3] - topo)
        a_canvas = alfa[loc[1]:loc[3], loc[0]:loc[2]]
        visivel = a_canvas > 0
        n_vis = int(visivel.sum())
        px['px_visiveis'] = n_vis
        area_ref = max(1, (ref[2] - ref[0]) * (ref[3] - ref[1]))
        # as contagens inteiras decidem (desdobra.laudo); a fracao arredondada e so para leitura
        px['px_area_ref'] = int(area_ref)
        px['fracao_canvas'] = round(n_vis / area_ref, 6)
        if cobertura is not None and reg.get('visivel_efetiva') and n_vis and reg.get('kind') not in ('group', 'artboard'):
            janela = cobertura.coberto[rc[1]:rc[3], rc[0]:rc[2]]
            px['px_cobertos'] = int((janela & visivel).sum())
            px['fracao_coberta'] = round(px['px_cobertos'] / n_vis, 6)
            if pode_cobrir(reg, por_id):
                janela |= a_canvas == 255  # numero-neutro: alfa cheio em 8 bits
    if mini_rc is not None:
        loc = (mini_rc[0] - esq, mini_rc[1] - topo, mini_rc[2] - esq, mini_rc[3] - topo)
        mini = reduzir(img.crop(loc), parametros['miniatura_lado_px'])
        nome = 'miniaturas/%s.png' % contexto['nome_arquivo_camada'](reg)
        arquivos.gravar_bytes_atomico(pasta_saida / nome, png_bytes(mini))
        px['miniatura'] = nome
    if px['origem'] == 'pixels_proprios' and contexto.get('extrair_assets'):
        dados = png_bytes(img)
        sha = hashlib.sha256(dados).hexdigest()
        destino = pasta_saida / 'assets' / ('%s.png' % sha)
        if not destino.exists():
            arquivos.gravar_bytes_atomico(destino, dados)
        px['asset_sha256'] = sha
        px['asset_dims'] = [img.width, img.height]
        del dados
        # com mascara raster ativa, o alfa visivel (alfa da camada vezes a mascara) vai junto: o design system
        # (desdobra.ds) mede a caixa do sujeito por ele, porque o asset guarda so os pixels proprios
        alfa_proprio = np.asarray(img.getchannel('A'), dtype=np.uint8) if 'A' in img.mode else None
        if alfa_proprio is None:
            alfa_proprio = np.full(alfa.shape, 255, np.uint8)  # numero-neutro: alfa cheio em 8 bits
        if not np.array_equal(alfa_proprio, alfa):
            dados_alfa = png_bytes(Image.fromarray(alfa, 'L'))
            sha_alfa = hashlib.sha256(dados_alfa).hexdigest()
            destino_alfa = pasta_saida / 'assets' / ('%s.png' % sha_alfa)
            if not destino_alfa.exists():
                arquivos.gravar_bytes_atomico(destino_alfa, dados_alfa)
            px['alfa_visivel_sha256'] = sha_alfa
            del dados_alfa
        del alfa_proprio
    del img, alfa


# ------------------------------------------------------------------ prova de pixel
def _achatar(a):
    a = a.astype(np.int32)
    return (a[..., :3] * a[..., 3:4] + 255 * (255 - a[..., 3:4]) + 127) // 255  # numero-neutro: sobre branco, 8 bits


def para_rgba(img):
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    return np.asarray(img)


def recompor_e_comparar(psd, merged, limiar):
    """Recompoe em faixas e compara com o merged. Devolve (rec_rgba, dmax, histogramas, faixas)."""
    W, H = psd.width, psd.height
    n_alvo = min(FAIXAS_MAX, max(1, int(math.ceil(W * H / PIXELS_POR_FAIXA))))
    passo = max(LINHAS_MIN_FAIXA, int(math.ceil(H / n_alvo)))
    A = para_rgba(merged)
    rec = np.zeros((H, W, 4), np.uint8)
    dmax = np.zeros((H, W), np.uint8)
    hist = [np.zeros(256, np.int64) for _ in range(4)]  # numero-neutro: 256 niveis, 4 canais
    n_faixas = 0
    for y0 in range(0, H, passo):
        y1 = min(H, y0 + passo)
        im = psd.composite(viewport=(0, y0, W, y1), ignore_preview=True)
        rec[y0:y1] = np.asarray(im.convert('RGBA'))
        del im
        n_faixas += 1
        sub = max(1, PIXELS_POR_BLOCO_COMPARACAO // max(W, 1))
        for z0 in range(y0, y1, sub):
            z1 = min(y1, z0 + sub)
            a, b = A[z0:z1], rec[z0:z1]
            d = np.abs(_achatar(a) - _achatar(b)).astype(np.uint8)
            for c in range(3):  # numero-neutro: canais R, G, B
                hist[c] += np.bincount(d[..., c].ravel(), minlength=256)  # numero-neutro: 256 niveis
            hist[3] += np.bincount(np.abs(a[..., 3].astype(np.int32) - b[..., 3]).astype(np.uint8).ravel(), minlength=256)  # numero-neutro: idem
            dmax[z0:z1] = d.max(axis=2)
    return rec, dmax, hist, {'n_faixas': n_faixas, 'altura_faixa_px': passo}


def stats_hist(hist, n, limiar):
    cum = np.cumsum(hist)
    p99 = int(np.searchsorted(cum, 0.99 * n))  # numero-neutro: percentil 99 descritivo
    nz = np.nonzero(hist)[0]
    return {'media_abs': round(float((hist * np.arange(len(hist))).sum()) / n, 4), 'p99': p99,
            'max': int(nz[-1]) if len(nz) else 0,
            'pct_px_acima': round(float(hist[int(limiar) + 1:].sum()) / n * 100, 4)}  # numero-neutro: porcentagem


def pool_max(arr, f):
    H, W = arr.shape
    H2, W2 = -(-H // f), -(-W // f)
    pad = np.zeros((H2 * f, W2 * f), arr.dtype)
    pad[:H, :W] = arr
    return pad.reshape(H2, f, W2, f).max(axis=(1, 3))


def mapa_diferenca(dmax, merged, lado):
    H, W = dmax.shape
    f = max(1, -(-max(H, W) // lado))
    amp = np.clip(pool_max(dmax, f).astype(np.int32) * AMPLIFICACAO_DIFERENCA, 0, 255).astype(np.uint8)  # numero-neutro: 8 bits
    fundo = merged.convert('L').resize((amp.shape[1], amp.shape[0]), Image.Resampling.BOX)
    g = (np.asarray(fundo, dtype=np.float32) * FATOR_FUNDO_DIFERENCA).astype(np.uint8)
    return Image.fromarray(np.stack([np.maximum(g, amp), g, g], axis=2), 'RGB'), f


def regioes(dmax, limiar, min_px, max_regioes):
    """Componentes conexos dos pixels acima do limiar, numa grade reduzida (so registro)."""
    from scipy import ndimage
    mask = dmax > limiar
    tot = int(mask.sum())
    H, W = dmax.shape
    meta = {'n_componentes': 0, 'n_reportadas': 0, 'n_omitidas_por_limite': 0, 'n_pequenas': 0, 'px_acima_total': tot,
            'fator_reducao': 1}
    if tot == 0:
        return [], meta
    f = max(1, int(math.ceil(math.sqrt(W * H / PIXELS_GRADE_REGIOES))))
    red = ndimage.binary_dilation(pool_max(mask.astype(np.uint8), f).astype(bool), iterations=1)
    lab, _n = ndimage.label(red, structure=np.ones((3, 3), bool))  # numero-neutro: vizinhanca 8
    cand = []
    for sl in ndimage.find_objects(lab):
        if sl is None:
            continue
        y0, y1 = sl[0].start * f, min(H, sl[0].stop * f)
        x0, x1 = sl[1].start * f, min(W, sl[1].stop * f)
        cand.append(([x0, y0, x1, y1], int(mask[y0:y1, x0:x1].sum())))
    cand.sort(key=lambda t: (-t[1], t[0]))
    grandes = [c for c in cand if c[1] >= min_px]
    meta.update({'n_componentes': len(cand), 'n_reportadas': min(len(grandes), max_regioes),
                 'n_omitidas_por_limite': max(0, len(grandes) - max_regioes), 'n_pequenas': len(cand) - len(grandes),
                 'px_acima_nas_pequenas': int(sum(c[1] for c in cand if c[1] < min_px)), 'fator_reducao': f})
    return [{'caixa': bb, 'px_acima': n} for bb, n in grandes[:max_regioes]], meta


def por_camada(dmax, limiar, regs):
    out = []
    for r in regs:
        if not r.get('visivel_efetiva') or r.get('kind') in ('group', 'artboard'):
            continue
        b = r.get('caixa_tinta')
        if not b:
            continue
        H, W = dmax.shape
        bb = interseccao(b, [0, 0, W, H])
        if not bb:
            continue
        sub = dmax[bb[1]:bb[3], bb[0]:bb[2]]
        n = int((sub > limiar).sum())
        out.append({'layer_id': r['layer_id'], 'px_acima': n, 'pct_da_camada': round(n / max(1, sub.size) * 100, 4)})  # numero-neutro: porcentagem
    return out
