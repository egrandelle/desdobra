# -*- coding: utf-8 -*-
"""Pagina de texto do render: uma camada de texto do contrato vira um SVG dentro de uma pagina HTML do tamanho da
regiao da camada, que o Chromium fixado grava em PDF (funcoes puras, sem disco).

Mapeamento do texto (montar_svg de gama/g_comum.py:162-234 da pesquisa, adaptado aos campos do laudo):
  - uma linha <text> por quebra (U+000D, U+000A e U+0003), um <tspan> por trecho, com o corpo do espaco de texto,
    letter-spacing = tracking / 1000 x corpo e a matriz da camada no <g>;
  - linha de base pela entrelinha (a automatica e o fator do paragrafo vezes o corpo; a fixa e a do trecho), e a
    primeira linha na origem da matriz (texto de ponto);
  - ancora pela justificacao do paragrafo, com a compensacao do letter-spacing do ultimo caractere (o CSS aplica,
    o Photoshop nao);
  - kerning automatico do trecho (font-kerning), kerning manual como dx, ligaduras do trecho, caixa alta com a
    feature cpsp;
  - trechos vizinhos que so mudam de cor viram um tspan so, para nao perder o kerning na fronteira. Cada cor do
    texto e uma passada com o mesmo layout: numa linha de varias cores, um gradiente de paradas duras nas fronteiras
    entre os caracteres (medidas pelo Chromium numa pagina base) deixa preta so a cor da passada (pesquisa,
    fronteiras_de_cor). A soma das coberturas das passadas da a cobertura da camada.

A fonte entra pelo @font-face com url('/fonte/<id>'), a rota propria do servidor local (desdobra.chromium.servidor):
nunca base64 no HTML, nunca local(), nunca CDN. Cada face tem um nome de familia proprio do job e o peso declarado,
entao uma face instalada no sistema com o mesmo nome nunca entra no lugar (arquitetura-v1.md, 4.5 e 4.11).

O HTML existe so na memoria do processo principal e do servidor local; nunca vai para disco nem para log.
"""
import html

from desdobra import limites
from desdobra.fontes import casamento

ANCORA = {'LEFT': 'start', 'RIGHT': 'end', 'CENTER': 'middle'}
TRANSPARENTE = 'transparent'
PRETO = '#000000'
MILESIMOS = 1000.0  # numero-neutro: tracking e kerning do Photoshop em milesimos de em
ENTRELINHA_AUTOMATICA = 1.2  # numero-neutro: entrelinha automatica padrao do Photoshop (120% do corpo), como no leitor


def familia_css(prefixo, face_id):
    return '%s-%s' % (prefixo, face_id)


def multiplo(x, passo):
    """x arredondado para cima no multiplo de passo (pagina do PDF, como na pesquisa)."""
    return int(-(-int(x) // int(passo)) * int(passo))


def _paragrafo_de(paragrafos, pos):
    for p in paragrafos:
        if p['inicio'] <= pos < p['fim']:
            return p
    return paragrafos[-1] if paragrafos else {}


def _entrelinha(run, paragrafo):
    corpo = float(run.get('corpo_espaco_texto') or 0)
    if run.get('autoleading'):
        fator = paragrafo.get('auto_leading_fator') or ENTRELINHA_AUTOMATICA
        return corpo * float(fator)
    return float(run.get('entrelinha') or 0)


def linhas_da_camada(texto, quebras=()):
    """Divide os trechos em linhas pelas quebras gravadas e, na caixa de paragrafo, pelas quebras automaticas medidas
    (quebras: posicoes de espaco no texto que viram fim de linha). Cada linha: {'pedacos': [(texto, run)],
    'indices': [posicao de cada caractere no texto], 'entrelinha', 'just'}."""
    quebras = set(quebras or ())
    runs = [r for r in texto.get('runs') or [] if r.get('texto')]
    paragrafos = texto.get('paragrafos') or []
    linhas = [{'pedacos': [], 'runs': [], 'indices': [], 'inicio': runs[0]['inicio'] if runs else 0}]
    for r in runs:
        atual = ''
        pos = r['inicio']
        for ch in r['texto']:
            if ch in casamento.CONTROLES_DE_QUEBRA or pos in quebras:
                if atual:
                    linhas[-1]['pedacos'].append((atual, r))
                linhas[-1]['runs'].append(r)
                atual = ''
                linhas.append({'pedacos': [], 'runs': [], 'indices': [], 'inicio': pos + 1})
            else:
                atual += ch
                linhas[-1]['indices'].append(pos)
            pos += 1
        if atual:
            linhas[-1]['pedacos'].append((atual, r))
            linhas[-1]['runs'].append(r)
    saida = []
    for ln in linhas:
        par = _paragrafo_de(paragrafos, ln['inicio'])
        rs = ln['runs'] or [p[1] for p in ln['pedacos']]
        lead = max((_entrelinha(r, par) for r in rs), default=0.0)
        saida.append({'pedacos': ln['pedacos'], 'indices': ln['indices'], 'entrelinha': lead,
                      'just': par.get('justificacao') or 'LEFT'})
    # a ultima quebra (o Photoshop grava o texto terminado em U+000D) nao abre linha nova
    while len(saida) > 1 and not saida[-1]['pedacos']:
        saida.pop()
    return saida


def caixa_alta(s):
    """Caixa alta caractere a caractere, sem mudar o tamanho do texto (o mapa de posicoes depende disso)."""
    return ''.join(c.upper() if len(c.upper()) == 1 else c for c in s)


def unidades_utf16(s):
    """Quantas unidades UTF-16 cada caractere ocupa (o Chromium conta posicoes de caractere em UTF-16)."""
    return [2 if ord(c) > 0xFFFF else 1 for c in s]  # numero-neutro: plano basico do Unicode


def _x_dos_caracteres(texto_linha, pos):
    """[(x inicio, x fim)] por caractere do texto da linha, a partir das posicoes por unidade UTF-16 do Chromium."""
    unidades = unidades_utf16(texto_linha)
    if not pos or len(pos) != sum(unidades):
        raise ValueError('posicoes dos caracteres com outro tamanho')
    out, u = [], 0
    for n in unidades:
        out.append((float(pos[u][0]), float(pos[u + n - 1][2])))
        u += n
    return out


def eh_caixa_de_paragrafo(t):
    caixa = t.get('box_bounds')
    return t.get('tipo_caixa') == 'paragrafo' and bool(caixa) and len(caixa) == 4  # numero-neutro: [esquerda, topo, direita, base]


def quebras_da_caixa(entrada, posicoes, faces_por_ps):
    """Quebras automaticas da caixa de paragrafo: em cada linha medida, a ultima posicao de espaco antes de o texto
    passar da largura da caixa vira fim de linha (como o Photoshop quebra, pela palavra). posicoes: as do Chromium na
    pagina de medida, com as quebras que ja havia. Devolve a lista ordenada de posicoes no texto."""
    t = entrada['texto']
    esq, _topo, dir_, _base = (float(x) for x in t['box_bounds'])
    largura = dir_ - esq
    quebras = set(entrada.get('quebras_automaticas') or ())
    for n, ln in enumerate(linhas_da_camada(t, quebras)):
        if not ln['pedacos']:
            continue
        texto_linha = ''.join(caixa_alta(s) if r.get('font_caps') in ('ALL_CAPS', 'SMALL_CAPS') else s
                              for s, r in ln['pedacos'] if faces_por_ps.get(r.get('fonte_ps')) is not None)
        if len(texto_linha) != len(ln['indices']):
            raise ValueError('linha com trecho sem face')
        xs = _x_dos_caracteres(texto_linha, (posicoes or {}).get('L%d' % n))
        inicio, ultimo_espaco = 0, None
        for k, ch in enumerate(texto_linha):
            if ch == ' ':
                ultimo_espaco = k
                continue
            if xs[k][1] - xs[inicio][0] > largura and ultimo_espaco is not None and ultimo_espaco > inicio:
                quebras.add(ln['indices'][ultimo_espaco])
                inicio, ultimo_espaco = ultimo_espaco + 1, None
    return sorted(quebras)


def _chave_estilo(r, face):
    return (face['id'] if face else None, r.get('corpo_espaco_texto'), r.get('tracking'), r.get('kerning'),
            r.get('autokerning', True), r.get('font_caps'), r.get('faux_bold'), r.get('ligaduras', True))


def _estilo(r, face, prefixo):
    corpo = float(r.get('corpo_espaco_texto') or 0)
    ls = float(r.get('tracking') or 0) / MILESIMOS * corpo
    caps = r.get('font_caps') in ('ALL_CAPS', 'SMALL_CAPS')
    return ("font-family:'%s';font-weight:%d;font-style:normal;font-size:%.5fpx;letter-spacing:%.5fpx;"
            "font-kerning:%s;font-variant-ligatures:%s;font-synthesis:none;white-space:pre;%s" % (
                familia_css(prefixo, face['id']), int(face.get('peso_declarado') or 400), corpo, ls,  # numero-neutro: peso normal do CSS
                'normal' if r.get('autokerning', True) else 'none',
                'common-ligatures' if r.get('ligaduras', True) else 'none',
                "font-feature-settings:'cpsp' 1;" if caps else '')), ls


def origem_das_linhas(t, linhas, faces_por_ps):
    """(x por ancora, y da primeira linha de base) no espaco de texto. Texto de ponto: a origem da matriz. Caixa de
    paragrafo: a primeira linha de base fica no topo da caixa mais a ascendente da face do primeiro trecho (o padrao
    do Photoshop), e a ancora nas bordas ou no meio da caixa. A quebra automatica da caixa nao e refeita: so as quebras
    gravadas no texto (o contrato registra isso)."""
    caixa = t.get('box_bounds')
    if not eh_caixa_de_paragrafo(t):
        return {'start': 0.0, 'middle': 0.0, 'end': 0.0}, 0.0
    esq, topo, dir_ = float(caixa[0]), float(caixa[1]), float(caixa[2])
    y = topo
    primeira = next((ln for ln in linhas if ln['pedacos']), None)
    if primeira is not None:
        alturas = []
        for _s, r in primeira['pedacos']:
            m = (faces_por_ps.get(r.get('fonte_ps')) or {}).get('metricas') or {}
            if m.get('ascender') and m.get('unidades_por_em'):
                alturas.append(float(m['ascender']) / float(m['unidades_por_em']) * float(r.get('corpo_espaco_texto') or 0))
        y = topo + max(alturas, default=0.0)
    return {'start': esq, 'middle': (esq + dir_) / 2.0, 'end': dir_}, y  # numero-neutro: meio da caixa


def _gradiente(gid, fronteiras, cor_esq, cor_dir_final):
    """linearGradient de paradas duras ao longo da linha de base (pesquisa, gama/g_comum.py, fronteiras_de_cor).
    fronteiras: [(x, opacidade a esquerda, opacidade a direita)] no espaco do texto, em ordem."""
    xa, xb = fronteiras[0][0] - 1.0, fronteiras[-1][0] + 1.0
    paradas = ['<stop offset="0" stop-color="#000000" stop-opacity="%d"/>' % cor_esq]
    for xf, esq, dir_ in fronteiras:
        o = (xf - xa) / (xb - xa)
        paradas.append('<stop offset="%.8f" stop-color="#000000" stop-opacity="%d"/>' % (o, esq))
        paradas.append('<stop offset="%.8f" stop-color="#000000" stop-opacity="%d"/>' % (o, dir_))
    paradas.append('<stop offset="1" stop-color="#000000" stop-opacity="%d"/>' % cor_dir_final)
    return ('<linearGradient id="%s" gradientUnits="userSpaceOnUse" x1="%.6f" y1="0" x2="%.6f" y2="0">%s'
            '</linearGradient>' % (gid, xa, xb, ''.join(paradas)))


def montar_svg(entrada, faces_por_ps, prefixo, cor_da_passada=None, posicoes=None):
    """SVG da camada de texto do contrato na regiao dela.

    Trechos vizinhos com o mesmo estilo viram um tspan so, mesmo quando a cor muda: assim o Chromium desenha a linha
    inteira de uma vez, com o kerning da fronteira (separar a cor em tspans internos muda o avanco depois da
    fronteira). Sem cor_da_passada, tudo sai preto (cobertura total). Com cor_da_passada, a linha de uma cor so sai
    preta ou transparente; a linha de varias cores recebe um gradiente de paradas duras nas fronteiras entre os
    caracteres, medidas pelo proprio Chromium (posicoes: {id da linha: [[x inicio, y, x fim], ...]}).

    Devolve (svg, spans, linhas) com spans = [{'id', 'fonte_ps', 'face_id', 'cdp'}] para o CDP e linhas =
    {id da linha: [cor de cada caractere]}."""
    t = entrada['texto']
    x0, y0, x1, y1 = entrada['regiao']
    rw, rh = x1 - x0, y1 - y0
    xx, xy, yx, yy, tx, ty = t['matriz']
    linhas = linhas_da_camada(t, entrada.get('quebras_automaticas'))
    corpo, spans, defs, cores_linhas = [], [], [], {}
    ancoras_x, y = origem_das_linhas(t, linhas, faces_por_ps)
    for n, ln in enumerate(linhas):
        if n > 0:
            y += ln['entrelinha']
        if not ln['pedacos']:
            continue
        ancora = ANCORA.get(ln['just'], 'start')
        ultimo = ln['pedacos'][-1][1]
        ls_ultimo = float(ultimo.get('tracking') or 0) / MILESIMOS * float(ultimo.get('corpo_espaco_texto') or 0)
        xdesl = ancoras_x[ancora] + {'middle': ls_ultimo / 2.0, 'end': ls_ultimo}.get(ancora, 0.0)  # numero-neutro: metade do espaco do ultimo caractere no centro
        fundidos = []
        for s, r in ln['pedacos']:
            face = faces_por_ps.get(r.get('fonte_ps'))
            if face is None:
                continue
            k = _chave_estilo(r, face)
            if fundidos and fundidos[-1]['chave'] == k and not r.get('kerning'):
                fundidos[-1]['partes'].append((s, r))
            else:
                fundidos.append({'chave': k, 'face': face, 'run': r, 'partes': [(s, r)]})
        lid = 'L%d' % n
        cores_chars = []
        textos = []
        for f in fundidos:
            texto_f = ''
            for s, rr in f['partes']:
                if rr.get('font_caps') in ('ALL_CAPS', 'SMALL_CAPS'):
                    s = caixa_alta(s)
                texto_f += s
                cores_chars += [entrada['cores_por_trecho'][str(rr['inicio'])]] * len(s)
            textos.append(texto_f)
        cores_linhas[lid] = cores_chars
        if cor_da_passada is None or set(cores_chars) == {cor_da_passada}:
            fill = PRETO
        elif cor_da_passada not in cores_chars:
            fill = TRANSPARENTE
        else:
            xs = _x_dos_caracteres(''.join(textos), (posicoes or {}).get(lid))
            fronteiras = []
            for k in range(1, len(cores_chars)):
                if cores_chars[k] != cores_chars[k - 1]:
                    xf = (xs[k - 1][1] + xs[k][0]) / 2.0  # numero-neutro: meio entre os caracteres
                    fronteiras.append((xf, int(cores_chars[k - 1] == cor_da_passada), int(cores_chars[k] == cor_da_passada)))
            gid = 'g%s' % lid
            defs.append(_gradiente(gid, fronteiras, int(cores_chars[0] == cor_da_passada),
                                   int(cores_chars[-1] == cor_da_passada)))
            fill = 'url(#%s)' % gid
        tspans = []
        for f, texto_f in zip(fundidos, textos):
            r, face = f['run'], f['face']
            estilo, _ls = _estilo(r, face, prefixo)
            dx = ''
            if not r.get('autokerning', True) and r.get('kerning'):
                dx = ' dx="%.5f"' % (float(r['kerning']) / MILESIMOS * float(r.get('corpo_espaco_texto') or 0))
            sid = 's%d_%d' % (n, len(spans))
            spans.append({'id': sid, 'fonte_ps': r.get('fonte_ps'), 'face_id': face['id'],
                          'cdp': any(casamento.tem_tinta(ch) for ch in texto_f)})
            tspans.append('<tspan id="%s" style="%sfill:%s"%s>%s</tspan>' % (
                sid, estilo, fill, dx, html.escape(texto_f, quote=False)))
        corpo.append('<text id="%s" x="%.5f" y="%.5f" text-anchor="%s" style="white-space:pre">%s</text>' % (
            lid, xdesl, y, ancora, ''.join(tspans)))
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="%d %d %d %d" '
           'style="display:block;position:absolute;left:0;top:0">'
           '<g transform="matrix(%.10f %.10f %.10f %.10f %.6f %.6f)"><defs>%s</defs>%s</g></svg>') % (
        rw, rh, x0, y0, rw, rh, xx, xy, yx, yy, tx, ty, ''.join(defs), ''.join(corpo))
    return svg, spans, cores_linhas


def css_faces(faces, prefixo):
    """@font-face de cada face pela rota local, com familia propria do job e o peso declarado."""
    return '\n'.join("@font-face{font-family:'%s';src:url('/fonte/%s');font-weight:%d;font-style:normal;"
                     "font-display:block}" % (familia_css(prefixo, f['id']), f['id'], int(f.get('peso_declarado') or 400))  # numero-neutro: peso normal do CSS
                     for f in faces)


def pagina(svg, largura, altura, css):
    """Pagina HTML do tamanho da pagina do PDF, fundo transparente, sem margem."""
    return ('<!doctype html><html><head><meta charset="utf-8"><style>%s\n@page{size:%dpx %dpx;margin:0}'
            'html,body{margin:0;padding:0;background:transparent;width:%dpx;height:%dpx;overflow:hidden;'
            '-webkit-print-color-adjust:exact;print-color-adjust:exact}</style></head><body>%s</body></html>') % (
        css, largura, altura, largura, altura, svg)


def _tamanho_da_pagina(entrada):
    passo = int(limites.valor('render.pagina_multiplo_px'))
    x0, y0, x1, y1 = entrada['regiao']
    return multiplo(x1 - x0, passo), multiplo(y1 - y0, passo)


def _css_da_entrada(faces_por_ps, faces, prefixo):
    usadas = {f['id'] for f in faces_por_ps.values() if f is not None}
    return css_faces([f for f in faces if f['id'] in usadas], prefixo)


def paginas_da_entrada(entrada, faces_por_ps, faces, prefixo):
    """As paginas de uma camada de texto. Uma cor: uma pagina preta, que da a cobertura. Varias cores: primeiro uma
    pagina preta so para medir a posicao dos caracteres no Chromium ('posicoes': True, sem PDF); as paginas de cada cor
    saem de paginas_de_cor depois da medida. Devolve [{'id', 'cor', 'html', 'largura', 'altura', 'spans', 'pdf',
    'posicoes', 'entrada'}]."""
    largura, altura = _tamanho_da_pagina(entrada)
    css = _css_da_entrada(faces_por_ps, faces, prefixo)
    svg, spans, _linhas = montar_svg(entrada, faces_por_ps, prefixo)
    if eh_caixa_de_paragrafo(entrada['texto']) and entrada.get('quebras_automaticas') is None:
        # caixa de paragrafo: primeiro mede as linhas sem a quebra automatica; as quebras saem de quebras_da_caixa
        return [{'id': '%s_quebra' % entrada['id'], 'cor': None, 'largura': largura, 'altura': altura,
                 'html': pagina(svg, largura, altura, css), 'spans': spans, 'pdf': False, 'posicoes': True,
                 'quebra': True, 'entrada': entrada['id']}]
    varias = len(entrada['cores']) > 1
    return [{'id': '%s_%s' % (entrada['id'], 'base' if varias else 'c0'), 'cor': None if varias else entrada['cores'][0],
             'largura': largura, 'altura': altura, 'html': pagina(svg, largura, altura, css), 'spans': spans,
             'pdf': not varias, 'posicoes': varias, 'entrada': entrada['id']}]


def paginas_de_cor(entrada, faces_por_ps, faces, prefixo, posicoes):
    """As paginas de cada cor de uma camada de varias cores, com as posicoes medidas na pagina base."""
    largura, altura = _tamanho_da_pagina(entrada)
    css = _css_da_entrada(faces_por_ps, faces, prefixo)
    saida = []
    for k, cor in enumerate(entrada['cores']):
        svg, spans, _linhas = montar_svg(entrada, faces_por_ps, prefixo, cor, posicoes)
        saida.append({'id': '%s_c%d' % (entrada['id'], k), 'cor': cor, 'largura': largura, 'altura': altura,
                      'html': pagina(svg, largura, altura, css), 'spans': spans, 'pdf': True, 'posicoes': False,
                      'entrada': entrada['id']})
    return saida
