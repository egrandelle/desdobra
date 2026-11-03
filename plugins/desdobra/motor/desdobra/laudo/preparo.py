# -*- coding: utf-8 -*-
"""Preparo do PSD antes da rotulagem (decisoes-v1.md, 99): contagens do laudo que dizem quando vale o DA juntar a
cena (luz, cor e liquido) num smart object ou num grupo antes de enviar.

Conta, so com numeros:
  - ajustes com mascara;
  - camadas com mesclagem diferente da normal;
  - cores solidas com mascara sobre imagem (pixel, smart object ou forma desenhados embaixo, na mesma area);
  - aglomerados sobrepostos: grupos de tres ou mais camadas desenhaveis sem texto que se sobrepoem umas as outras (sem
    contar a que cobre quase toda a tela), e quantas camadas eles somam; com pranchetas, por prancheta.
Funcao pura do laudo: nao abre PSD, nao le nome nem texto.
"""
from desdobra import limites

TIPOS_IMAGEM = ('pixel', 'smart_embutido', 'smart_linkado', 'forma', 'cor_solida', 'preenchimento')
TAMANHO_AGLOMERADO = 3  # numero-neutro: um aglomerado e mais que um par (o par e so sobreposicao)


def _area(c):
    return max(0.0, c[2] - c[0]) * max(0.0, c[3] - c[1])


def _inter(a, b):
    return _area([max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])])


def _mascara(c):
    mk = (c.get('aparencia') or {}).get('mascara') or {}
    return mk.get('raster') and not mk.get('desativada')


def _caixa(c):
    g = c.get('geometria') or {}
    cx = g.get('caixa_tinta') or g.get('caixa')
    return [float(v) for v in cx] if cx and cx[2] > cx[0] and cx[3] > cx[1] else None


def _telas(laudo, camadas):
    """[(caixa da tela, camadas dela)]: cada prancheta quando o laudo tem quadros por prancheta (a camada comum, sem
    quadro, entra em todas), senao o documento inteiro."""
    quadros = [q for q in laudo['documento'].get('quadros') or [] if q.get('regra') == 'pranchetas' and q.get('caixa')]
    if not quadros:
        W, H = float(laudo['documento']['largura']), float(laudo['documento']['altura'])
        return [([0.0, 0.0, W, H], camadas)]
    return [([float(v) for v in q['caixa']], [c for c in camadas if c.get('quadro') in (None, q['id'])]) for q in quadros]


def _aglomerados(camadas, tela, frac_fundo):
    """Tamanhos dos componentes conexos por sobreposicao, sem texto e sem o que cobre quase toda a tela."""
    area_tela = _area(tela)
    nos = []
    for c in camadas:
        cx = _caixa(c)
        if c.get('tipo') == 'texto' or cx is None:
            continue
        cx = [max(cx[0], tela[0]), max(cx[1], tela[1]), min(cx[2], tela[2]), min(cx[3], tela[3])]
        if _area(cx) <= 0 or _area(cx) >= frac_fundo * area_tela:
            continue
        nos.append(cx)
    pai = list(range(len(nos)))

    def r(x):
        while pai[x] != x:
            pai[x] = pai[pai[x]]
            x = pai[x]
        return x
    for i in range(len(nos)):
        for j in range(i + 1, len(nos)):
            if _inter(nos[i], nos[j]) > 0:
                pai[r(i)] = r(j)
    tamanhos = {}
    for i in range(len(nos)):
        tamanhos[r(i)] = tamanhos.get(r(i), 0) + 1
    return [t for t in tamanhos.values() if t >= TAMANHO_AGLOMERADO]


def contar(laudo):
    camadas = [c for c in laudo['camadas'] if (c.get('aparencia') or {}).get('visivel_efetiva')
               and c.get('tipo') not in ('grupo', 'prancheta')]
    frac_fundo = limites.valor('derivacao.bloco_fundo_fracao')
    ajustes = sum(1 for c in camadas if c.get('tipo') == 'ajuste' and _mascara(c))
    mesclas = sum(1 for c in camadas if (c.get('aparencia') or {}).get('blend') not in (None, 'NORMAL', 'PASS_THROUGH'))
    cores = 0
    for k, c in enumerate(camadas):
        cx = _caixa(c)
        if c.get('tipo') != 'cor_solida' or not _mascara(c) or cx is None:
            continue
        if any(b.get('tipo') in TIPOS_IMAGEM and _caixa(b) and _inter(_caixa(b), cx) > 0 for b in camadas[:k]):
            cores += 1
    # aglomerados por tela (revisao 2 do M5, M3): numa peca de pranchetas, o fundo de cada prancheta e medido contra a
    # area dela, nao contra a do documento
    grandes = []
    for tela, das in _telas(laudo, camadas):
        grandes.extend(_aglomerados(das, tela, frac_fundo))
    return {'ajustes_com_mascara': ajustes, 'mesclagens': mesclas, 'cores_solidas_mascaradas_sobre_imagem': cores,
            'aglomerados_sobrepostos': len(grandes), 'camadas_em_aglomerados': sum(grandes)}


def recomendacao(contagens):
    """Texto fixo da recomendacao de preparo, ou None quando as contagens ficam abaixo do limite."""
    soma = contagens['ajustes_com_mascara'] + contagens['mesclagens'] + contagens['cores_solidas_mascaradas_sobre_imagem']
    if soma < limites.valor('laudo.preparo_minimo_camadas') and not contagens['aglomerados_sobrepostos']:
        return None
    return ('O PSD tem %d ajuste(s) com máscara, %d mesclagem(ns), %d cor(es) sólida(s) com máscara sobre imagem e %d '
            'aglomerado(s) de camadas sobrepostas (%d camadas). Antes da rotulagem, vale pedir à agência para juntar a '
            'cena (luz, cor e líquido) num smart object ou num grupo, com o blending resolvido lá dentro, e deixar '
            'título, textos, logos e ícones em camadas separadas. Na derivação, a cena sobreposta anda como um bloco '
            'rígido.' % (contagens['ajustes_com_mascara'], contagens['mesclagens'],
                         contagens['cores_solidas_mascaradas_sobre_imagem'], contagens['aglomerados_sobrepostos'],
                         contagens['camadas_em_aglomerados']))
