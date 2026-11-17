# -*- coding: utf-8 -*-
"""Quebras aprovadas por familia (decisoes-v1.md, 77, estendida as familias na rodada 3 do M5).

O briefing diz, para um texto de ponto e uma familia de formatos (lista de formatos, ou faixa de proporcao largura /
altura; o formato vence a faixa), quais quebras gravadas do texto ficam; as outras viram espaco. Nada de texto no
briefing nem no envelope: so os indices das quebras (0 e a primeira quebra gravada, sem contar a do fim do texto).

A largura das linhas juntadas vem de medida (revisao 3 do M5): a pagina da conferencia de fontes (fontes.medicao), com
as linhas juntadas, no Chromium, com a fonte servida pelo motor (derivacao.medida_quebras). O processo principal nao
le a fonte. A caixa nova e a da tinta da mestre, com a largura na proporcao medida (linha juntada mais larga contra a
linha mais larga da mestre) e a altura menos uma entrelinha por quebra tirada; a posicao segue a justificacao (o
ponto de ancora do texto nao muda). Com a tinta de cada linha medida no Chromium (M7a, fatia 4), as bordas seguem a
tinta, como o render a desenha. A caixa nunca e cortada no canvas da mestre.

A quebra da familia da tela (M7b, C1; decisoes-v1.md, 167 e 171) usa o mesmo campo, com familia: vale para os formatos
da familia, juntando quebras gravadas (os indices que ficam) e inserindo quebra num espaco (inseridas, as posicoes,
como a mestre propria). As posicoes contam no texto de agora: o do KV, ou o editado pelo DA na familia
(texto_editado). Na derivacao (M7b, C2), a quebra da familia vence a da faixa nos formatos da familia, e a caixa do
texto do KV e medida como a da faixa, com as linhas juntadas e as inseridas (com_juntadas, caixa_medida: uma entrelinha
a mais por quebra inserida). No texto editado, a quebra vale sobre o texto novo (render.derivado.
quebras_do_texto_editado).

Linhas do DA (0.9.4): o texto editado nunca quebra sozinho na largura da caixa. As linhas sao as do DA (Enter no texto
e a quebra da familia), com o mesmo corpo, e a caixa cresce em volta da ancora do texto ate a linha mais longa. A
tinta do texto editado e medida no Chromium pela mesma pagina de medida (pedidos_editados, camada_do_editado,
caixa_do_editado; derivacao.medida_quebras.medir_editados), e a caixa medida vai a derivacao (caixa_texto_editado) e
ao render (a caixa validada do texto).

O controle da quebra no palco (M7b, C4) le o texto de agora com as posicoes que pode quebrar (texto_para_quebrar), e a
previa desenha o texto editado nas linhas da quebra da familia (linhas_do_editado).

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


def chave(layer_id, manter, inseridas=()):
    """A chave da medida de um texto com as quebras que ficam e as inseridas. Sem inseridas, a chave de antes do C2 (a
    medida da faixa do M5 e a da familia que so junta sao a mesma)."""
    base = '%d:%s' % (int(layer_id), ','.join(str(int(x)) for x in sorted(manter)))
    if not inseridas:
        return base
    return '%s+%s' % (base, ','.join(str(int(x)) for x in sorted(inseridas)))


def entradas_validas(briefing):
    """As quebras aprovadas por faixa ou por lista de formatos (M5). A quebra da familia da tela (com familia, M7b, C1)
    fica de fora: ela vale por cima destas nos formatos da familia (da_familia)."""
    return [i for i in briefing.get('quebras_por_familia') or []
            if mb._decisao_valida(i['quebras']) and i.get('familia') is None]


# ------------------------------------------------------------------ a quebra da familia da tela (M7b, C1)
def da_familia(briefing, layer_id, formato_id):
    """A quebra da familia da tela que vale para o texto no formato (a entrada com familia que lista o formato), ou
    None. Com duas, a conferencia do briefing recusa (quebras_conflitantes); aqui vale a primeira."""
    for item in briefing.get('quebras_por_familia') or []:
        if item.get('familia') is not None and item['layer_id'] == layer_id and \
                formato_id in (item.get('formatos') or ()) and mb._decisao_valida(item['quebras']):
            return item
    return None


def normalizar_editado(texto):
    """O texto editado como o render o desenha (desdobra.render.derivado.texto_editado_na_entrada): CR LF e CR viram
    LF. As posicoes da quebra da familia contam neste texto."""
    return texto.replace('\r\n', '\n').replace('\r', '\n')


def texto_editado(edicoes, elemento):
    """O texto editado pelo DA no elemento, nas edicoes da familia (desdobra.tela.edicao.aplicar: vale a ultima edicao
    de texto, e o elemento apagado nao tem texto), normalizado (normalizar_editado); None sem edicao de texto."""
    if elemento is None:
        return None
    texto = None
    for ed in edicoes or ():
        if ed.get('elemento') != elemento:
            continue
        if ed.get('acao') == 'apagar':
            return None
        if ed.get('acao') == 'texto' and isinstance(ed.get('texto'), str):
            texto = ed['texto']
    return None if texto is None else normalizar_editado(texto)


def da_familia_no_formato(briefing, layer_ids, formato_id):
    """[(layer_id, entrada)] das quebras da familia da tela que valem nos textos layer_ids no formato."""
    saida = []
    for lid in layer_ids:
        item = da_familia(briefing, lid, formato_id)
        if item is not None:
            saida.append((lid, item))
    return saida


def item_da_familia(layer_id, entrada):
    """O item de quebras.familia do elemento na derivacao/1 (M7b, C2): os indices que ficam e as posicoes inseridas.
    A caixa medida (caixa_doc) entra so no texto do KV; o texto editado nao tem medida."""
    return {'layer_id': layer_id, 'aprovadas': sorted(entrada['quebras']['valor']),
            'inseridas': sorted(entrada.get('inseridas') or ())}


def origem_das(entradas):
    """quebras_origem do elemento: 'da' quando alguma das quebras da familia dele e do DA, senao 'proposta'."""
    return 'da' if any(x.get('origem') == 'da' for x in entradas) else 'proposta'


def do_da(entradas):
    """A quebra e decisao do DA (a dele, ou a proposta que ele aprovou): a caixa que ela da tem origem 'da'."""
    return bool(entradas) and all(x.get('origem') == 'da' or x.get('aprovada') for x in entradas)


def editado_no_formato(briefing, elemento, formato_id):
    """O texto editado pelo DA no elemento, na familia do formato (as edicoes da composicao dele, 171), ou None."""
    comp = next((c for c in briefing.get('composicoes') or [] if formato_id in c['formatos']), None)
    return texto_editado((comp or {}).get('edicoes'), elemento)


def texto_de_agora(camada, editado=None):
    """A camada de texto como a quebra da familia a le: a do laudo, ou so o conteudo editado pelo DA na familia."""
    return {'texto': {'conteudo': editado}} if editado is not None else camada


def espacos(camada):
    """Posicoes dos espacos (U+0020) do texto, onde a quebra pode entrar."""
    return [k for k, ch in enumerate(_conteudo(camada)) if ch == ' ']


def texto_para_quebrar(camada, editado=None):
    """O texto de agora como o controle da quebra no palco o le (M7b, C4): {'texto', 'gravadas', 'espacos'}, o texto
    (o do KV, ou o editado pelo DA na familia, normalizado), as posicoes das quebras gravadas que abrem linha e as dos
    espacos. As quebras do fim do texto saem do texto: elas nao abrem linha, e as posicoes de antes nao mudam."""
    alvo = texto_de_agora(camada, None if editado is None else normalizar_editado(editado))
    texto = _conteudo(alvo)
    while texto and texto[-1] in casamento.CONTROLES_DE_QUEBRA:
        texto = texto[:-1]
    return {'texto': texto, 'gravadas': posicoes_de_quebra(alvo), 'espacos': espacos(alvo)}


def linhas_do_editado(texto, manter, inseridas):
    """As linhas do texto editado pelo DA com a quebra da familia (M7b, C4), como o render as desenha
    (render.derivado.quebras_do_texto_editado): a quebra gravada fora de manter vira espaco, e o espaco inserido vira
    quebra. As linhas sao so estas: o texto editado nunca quebra sozinho (Linhas do DA, 0.9.4)."""
    t = normalizar_editado(texto)
    juntar = set(juntadas({'texto': {'conteudo': t}}, manter))
    novas = set(inseridas or ())

    def trocar(k, ch):
        if k in juntar:
            return ' '
        return '\n' if k in novas and ch == ' ' else ch
    return ''.join(trocar(k, ch) for k, ch in enumerate(t)).split('\n')


def conferir_da_familia(camada, manter, inseridas, editado=None):
    """O codigo do erro da quebra da familia no texto de agora (a camada, ou o texto editado na familia), ou None.
    quebra_aprovada_invalida: indice de quebra gravada que o texto nao tem, ou repetido; quebra_fora_de_espaco: posicao
    inserida que nao e espaco do texto, ou repetida."""
    alvo = texto_de_agora(camada, editado)
    n = len(posicoes_de_quebra(alvo))
    manter, inseridas = list(manter or ()), list(inseridas or ())
    if any(x >= n for x in manter) or len(set(manter)) != len(manter):
        return 'quebra_aprovada_invalida'
    livres = set(espacos(alvo))
    if any(p not in livres for p in inseridas) or len(set(inseridas)) != len(inseridas):
        return 'quebra_fora_de_espaco'
    return None


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
    """[(layer_id, manter, inseridas)] de todas as quebras aprovadas do briefing, as da faixa (sem inseridas) e as da
    familia da tela (o que a medida tem de medir)."""
    vistos = []
    for item in briefing.get('quebras_por_familia') or []:
        if not mb._decisao_valida(item['quebras']):
            continue
        p = (item['layer_id'], tuple(sorted(item['quebras']['valor'])), tuple(sorted(item.get('inseridas') or ())))
        if p not in vistos:
            vistos.append(p)
    return vistos


def com_juntadas(camada, manter, inseridas=()):
    """Copia da camada de texto com as quebras juntadas trocadas por espaco e os espacos inseridos trocados por quebra
    (para a pagina de medida)."""
    import copy
    c = copy.deepcopy(camada)
    pos = set(juntadas(camada, manter))
    novas = set(inseridas or ())
    q = '\r'  # a quebra de paragrafo, como o Photoshop a grava

    def trocar(k, ch):
        if k in pos:
            return ' '
        return q if k in novas and ch == ' ' else ch
    t = c.get('texto') or {}
    if t.get('conteudo'):
        t['conteudo'] = ''.join(trocar(k, ch) for k, ch in enumerate(t['conteudo']))
    for r in t.get('runs') or []:
        s = r.get('texto') or ''
        r['texto'] = ''.join(trocar(r['inicio'] + k, ch) for k, ch in enumerate(s))
    return c


def entrelinha_px(camada):
    rs = (camada.get('texto') or {}).get('runs') or []
    v = [float(r.get('entrelinha_efetiva_px') or 0) for r in rs]
    return max(v) if v else 0.0


def escala_x(camada):
    """Escala do espaco de texto para o documento no eixo x (a matriz do texto), ou None sem matriz."""
    import math
    m = (camada.get('texto') or {}).get('matriz')
    if not isinstance(m, (list, tuple)) or len(m) < 2:  # numero-neutro: a e b da matriz
        return None
    sx = math.hypot(float(m[0]), float(m[1]))
    return sx if sx > 0 else None


def escala_y(camada):
    """Escala do espaco de texto para o documento no eixo y (c e d da matriz do texto), ou None sem matriz. Difere da
    escala x na camada transformada com escala diferente em x e y (revisao do M7a)."""
    import math
    m = (camada.get('texto') or {}).get('matriz')
    if not isinstance(m, (list, tuple)) or len(m) < 4:  # numero-neutro: c e d da matriz
        return None
    sy = math.hypot(float(m[2]), float(m[3]))
    return sy if sy > 0 else None


def caixa_medida(camada, caixa, manter, medida, inseridas=()):
    """Caixa da tinta do texto (espaco do documento) com so as quebras de indice em manter e as inseridas nos espacos
    (a quebra da familia da tela, M7b, C2), pela medida {'largura_texto', 'largura_texto_mestre'} (no espaco de texto
    da pagina de medida). Cada quebra inserida soma uma entrelinha, como cada quebra tirada subtrai uma.

    Com a tinta medida no Chromium (medida['tinta_mestre'] e medida['tinta']: {'esq', 'dir', 'sobe', 'desce'} do
    bloco, no espaco de texto) e a matriz do texto, a caixa segue a tinta como o render a desenha: as bordas da tinta
    da mestre andam o quanto a tinta medida anda, na escala da matriz (topo pela subida da primeira linha, base pela
    descida da ultima, menos uma entrelinha por quebra tirada). Sem ela, a conta de antes: a largura na proporcao
    medida e a altura menos as entrelinhas, o que deixava a caixa menor que a tinta do render quando a linha juntada
    ganha acento, descendente ou o espaco lateral dos glifos (uns 21 px num titulo do corpus, revisao do M7a0)."""
    x0, y0, x1, y1 = (float(v) for v in caixa)
    tiradas = len(juntadas(camada, manter)) - len(set(inseridas or ()))
    h = max((y1 - y0) - tiradas * entrelinha_px(camada), 1.0)  # numero-neutro: altura minima de um px
    just = ((camada.get('texto') or {}).get('justificacao') or 'LEFT').upper()
    tm, tj, sx, sy = medida.get('tinta_mestre'), medida.get('tinta'), escala_x(camada), escala_y(camada)
    if isinstance(tm, dict) and isinstance(tj, dict) and sx is not None and sy is not None:
        nx0 = x0 + (float(tj['esq']) - float(tm['esq'])) * sx
        nx1 = x1 + (float(tj['dir']) - float(tm['dir'])) * sx
        ny0 = y0 + (float(tm['sobe']) - float(tj['sobe'])) * sy
        ny1 = y0 + h + (float(tj['desce']) - float(tm['desce'])) * sy
        return [nx0, ny0, nx1, max(ny1, ny0 + 1.0)]  # numero-neutro: altura minima de um px
    fator = (x1 - x0) / float(medida['largura_texto_mestre'])
    w = float(medida['largura_texto']) * fator
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


# ------------------------------------------------------------------ Linhas do DA no texto editado (0.9.4)
def linhas_editadas(texto, item=None):
    """As linhas do texto editado pelo DA como o render as desenha: as do texto (Enter) ou, com a quebra da familia
    (item: {'aprovadas', 'inseridas'}, o item de quebras.familia do elemento), as de linhas_do_editado. Nunca ha
    quebra na largura da caixa."""
    if item is not None:
        return linhas_do_editado(texto, item.get('aprovadas') or (), item.get('inseridas') or ())
    return normalizar_editado(texto).split('\n')


def chave_editado(layer_id, linhas):
    """A chave da medida do texto editado (as linhas do DA na camada), separada das chaves de chave()."""
    import hashlib
    sha = hashlib.sha256('\n'.join(linhas).encode('utf-8')).hexdigest()
    return 'ed:%d:%s' % (int(layer_id), sha)


def _trecho_e_paragrafo(camada):
    from desdobra.render import texto as rt
    t = camada.get('texto') or {}
    r0 = next((r for r in t.get('runs') or [] if r.get('tem_tinta')), None)
    if r0 is None:
        return None, None
    return r0, rt._paragrafo_de(t.get('paragrafos') or [], r0['inicio'])


def camada_do_editado(camada, linhas):
    """Copia da camada de texto do laudo com o texto editado num trecho so: o estilo do primeiro trecho com tinta, sem
    kerning manual, o paragrafo dele e as linhas do DA (como desdobra.render.derivado.texto_editado_na_entrada). Para a
    pagina de medida e para a conta da caixa (caixa_do_editado). None sem trecho com tinta."""
    import copy
    r0, par = _trecho_e_paragrafo(camada)
    if r0 is None:
        return None
    c = copy.deepcopy(camada)
    s = '\r'.join(linhas)
    t = c.setdefault('texto', {})
    t['conteudo'] = s
    t['runs'] = [dict(r0, inicio=0, fim=len(s), texto=s, kerning=None, tem_tinta=True)]
    t['paragrafos'] = [dict(par, inicio=0, fim=len(s) + 1)] if par else []
    return c


def caixa_do_editado(camada_editada, tinta, faces_por_ps):
    """A caixa da tinta do texto editado no espaco do documento (a da camada no KV), com as linhas do DA e o mesmo
    corpo, ou None. tinta: {'esq', 'dir', 'sobe', 'desce'} do bloco medido no Chromium (fontes.medicao.tinta_do_bloco:
    x a partir da ancora da linha, subida da primeira linha e descida da ultima). A ancora e a do render
    (render.texto.origem_das_linhas): a origem da matriz no texto de ponto, a borda ou o meio da caixa de paragrafo,
    com a primeira linha de base no topo dela mais a ascendente. As linhas de base descem uma entrelinha por linha
    (render.texto._entrelinha). Os quatro cantos passam pela matriz do texto."""
    from desdobra.render import texto as rt
    t = camada_editada.get('texto') or {}
    if not isinstance(tinta, dict) or not t.get('runs') or not t.get('matriz'):
        return None
    linhas = rt.linhas_da_camada(t)
    cheias = [n for n, ln in enumerate(linhas) if ln['pedacos']]
    if not cheias:
        return None
    ancoras, y0 = rt.origem_das_linhas(t, linhas, faces_por_ps or {})
    just = linhas[cheias[0]]['just']
    x = ancoras[rt.ANCORA.get(just, 'start')]
    bases = [y0]
    for ln in linhas[1:]:
        bases.append(bases[-1] + ln['entrelinha'])
    u0, u1 = x + float(tinta['esq']), x + float(tinta['dir'])
    v0, v1 = bases[cheias[0]] - float(tinta['sobe']), bases[cheias[-1]] + float(tinta['desce'])
    xx, xy, yx, yy, tx, ty = (float(v) for v in t['matriz'][:6])  # numero-neutro: os seis termos da matriz
    pts = [(xx * u + yx * v + tx, xy * u + yy * v + ty) for u in (u0, u1) for v in (v0, v1)]
    return [min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)]
