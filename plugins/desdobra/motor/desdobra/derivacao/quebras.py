# -*- coding: utf-8 -*-
"""Quebras aprovadas por familia (decisoes-v1.md, 77, estendida as familias na rodada 3 do M5).

O briefing diz, para um texto de ponto e uma familia de formatos (lista de formatos, ou faixa de proporcao largura /
altura; o formato vence a faixa), quais quebras gravadas do texto ficam; as outras viram espaco. Nada de texto no
briefing nem no envelope: so os indices das quebras (0 e a primeira quebra gravada, sem contar a do fim do texto).

A largura das linhas juntadas vem de medida (revisao 3 do M5): a pagina da conferencia de fontes (fontes.medicao), com
as linhas juntadas, no Chromium, com a fonte servida pelo motor (derivacao.medida_quebras). O processo principal nao
le a fonte. A caixa nova e a da tinta da mestre, com a largura na proporcao medida (linha juntada mais larga contra a
linha mais larga da mestre) e a altura menos uma entrelinha por quebra tirada; a posicao segue a justificacao (o
ponto de ancora do texto nao muda). A caixa nunca e cortada no canvas da mestre.

Funcao pura do laudo, do briefing e da medida.
"""
from desdobra.briefing import modelo as mb
from desdobra.fontes import casamento


def _conteudo(camada):
    """O texto inteiro (o do laudo, ou o dos trechos na ordem, como o contrato do render leva)."""
    t = camada.get('texto') or {}
    if t.get('conteudo'):
        return t['conteudo']
    runs = sorted(t.get('runs') or [], key=lambda r: r.get('inicio', 0))
    s = ''
    for r in runs:
        s = s.ljust(int(r.get('inicio', len(s)))) + (r.get('texto') or '')
    return s


def posicoes_de_quebra(camada):
    """Posicoes das quebras gravadas do texto, sem as do fim: a quebra seguida so de outras quebras ate o fim nao abre
    linha (a mesma regra do render, render.texto.linhas_da_camada)."""
    s = _conteudo(camada)
    pos = [k for k, ch in enumerate(s) if ch in casamento.CONTROLES_DE_QUEBRA]
    while pos and all(ch in casamento.CONTROLES_DE_QUEBRA for ch in s[pos[-1] + 1:]):
        pos.pop()
    return pos


def juntadas(camada, manter):
    """Posicoes das quebras que viram espaco (as que nao estao em manter)."""
    manter = set(manter)
    return [p for k, p in enumerate(posicoes_de_quebra(camada)) if k not in manter]


def chave(layer_id, manter):
    return '%d:%s' % (int(layer_id), ','.join(str(int(x)) for x in sorted(manter)))


def entradas_validas(briefing):
    return [i for i in briefing.get('quebras_por_familia') or [] if mb._decisao_valida(i['quebras'])]


def aprovadas_para(briefing, layer_id, formato, largura, altura):
    """Indices das quebras que ficam neste formato, ou None sem quebra aprovada para a familia dele. A entrada por
    formato vence a faixa de proporcao."""
    razao = float(largura) / float(altura)
    itens = [i for i in entradas_validas(briefing) if i['layer_id'] == layer_id]
    for item in itens:
        if item.get('formatos') and formato['id'] in item['formatos']:
            return list(item['quebras']['valor'])
    for item in itens:
        if item.get('formatos'):
            continue
        rmin, rmax = item.get('razao_min'), item.get('razao_max')
        if (rmin is None or razao >= rmin) and (rmax is None or razao <= rmax):
            return list(item['quebras']['valor'])
    return None


def pedidos(briefing):
    """[(layer_id, manter)] de todas as quebras aprovadas do briefing (o que a medida tem de medir)."""
    vistos = []
    for item in entradas_validas(briefing):
        p = (item['layer_id'], tuple(sorted(item['quebras']['valor'])))
        if p not in vistos:
            vistos.append(p)
    return vistos


def com_juntadas(camada, manter):
    """Copia da camada de texto com as quebras juntadas trocadas por espaco (para a pagina de medida)."""
    import copy
    c = copy.deepcopy(camada)
    pos = set(juntadas(camada, manter))
    t = c.get('texto') or {}
    if t.get('conteudo'):
        t['conteudo'] = ''.join(' ' if k in pos else ch for k, ch in enumerate(t['conteudo']))
    for r in t.get('runs') or []:
        s = r.get('texto') or ''
        r['texto'] = ''.join(' ' if r['inicio'] + k in pos else ch for k, ch in enumerate(s))
    return c


def entrelinha_px(camada):
    rs = (camada.get('texto') or {}).get('runs') or []
    v = [float(r.get('entrelinha_efetiva_px') or 0) for r in rs]
    return max(v) if v else 0.0


def caixa_medida(camada, caixa, manter, medida):
    """Caixa da tinta do texto (espaco do documento) com so as quebras de indice em manter, pela medida
    {'largura_texto', 'largura_texto_mestre'} (no espaco de texto da pagina de medida)."""
    x0, y0, x1, y1 = (float(v) for v in caixa)
    fator = (x1 - x0) / float(medida['largura_texto_mestre'])
    w = float(medida['largura_texto']) * fator
    tiradas = len(juntadas(camada, manter))
    h = max((y1 - y0) - tiradas * entrelinha_px(camada), 1.0)  # numero-neutro: altura minima de um px
    just = ((camada.get('texto') or {}).get('justificacao') or 'LEFT').upper()
    if just.startswith('CENTER'):
        cx = (x0 + x1) / 2.0  # numero-neutro: centro
        nx0, nx1 = cx - w / 2.0, cx + w / 2.0  # numero-neutro: metade para cada lado
    elif just.startswith('RIGHT'):
        nx0, nx1 = x1 - w, x1
    else:
        nx0, nx1 = x0, x0 + w
    return [nx0, y0, nx1, y0 + h]


def linhas_do_texto(camada):
    return len(posicoes_de_quebra(camada)) + 1
