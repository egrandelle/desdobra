# -*- coding: utf-8 -*-
"""Pagina de medicao da conferencia de fontes e leitura do que o Chromium respondeu (funcoes puras).

A ideia vem da medicao da pesquisa (pesquisa/corpus-testes.md, 4, itens 8 e 9; pesquisa/wf_9612ef10-419-
resultado.json): cada camada de texto de ponto vira uma linha por quebra (U+000D, U+000A e U+0003), cada trecho
um span com o corpo do espaco de texto, letter-spacing = tracking / 1000 x corpo, kerning conforme o AutoKerning
cru, ligaduras do trecho, caixa alta (com a feature cpsp) quando o trecho pede e font-synthesis: none. Trechos
vizinhos que so mudam de cor viram um span so, para nao perder o kerning na fronteira. A largura da camada e a
maior largura de linha, medida em duas variantes (com e sem o letter-spacing do ultimo caractere, que o CSS
aplica e o Photoshop nao), e comparada com a largura de layout gravada na caixa TySh (bounds, Rght - Left).

Cada face entra com um nome de familia proprio do job e o peso declarado, entao uma face instalada no sistema
com o mesmo nome nunca entra no lugar (arquitetura-v1.md, 4.5).

O HTML existe so na memoria do processo principal e do servidor local; nunca vai para disco nem para log.
"""
import html

from desdobra import limites
from desdobra.fontes import casamento

AMOSTRA_SONDA = 24  # numero-neutro: caracteres da sonda de cada face (so para o Chromium carregar e o CDP responder)


def familia_css(prefixo, face_id):
    return '%s-%s' % (prefixo, face_id)


def _css_texto(t):
    return '"%s"' % str(t).replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')


def largura_tysh(texto):
    b = ((texto or {}).get('caixa_tysh') or {}).get('bounds') or {}
    esq, dir_ = b.get('Left'), b.get('Rght')
    if isinstance(esq, (int, float)) and isinstance(dir_, (int, float)) and dir_ > esq:
        return float(dir_) - float(esq)
    return None


def motivo_sem_largura(texto, pares):
    """Por que a largura da camada nao pode ser comparada com a caixa TySh, ou None quando pode."""
    if not texto or texto.get('tipo_caixa') != 'ponto':
        return 'largura_nao_medida_caixa_paragrafo'
    if largura_tysh(texto) is None:
        return 'largura_nao_medida_sem_caixa'
    tol = limites.valor('laudo.tolerancia_escala_texto')
    for r in texto.get('runs') or []:
        visivel = any(ch not in casamento.CONTROLES_DE_QUEBRA for ch in (r.get('texto') or ''))
        if not visivel:
            continue
        if pares.get(r.get('fonte_ps')) is None:
            return 'largura_nao_medida_face_ausente'
        if r.get('tem_tinta') and r.get('faux_bold'):
            return 'largura_nao_medida_faux_bold'
        for k in ('escala_h', 'escala_v'):
            if r.get(k) is not None and abs(float(r[k]) - 1.0) > tol:
                return 'largura_nao_medida_escala'
    w = texto.get('warp') or {}
    if w.get('estilo') not in (None, 'warpNone'):
        return 'largura_nao_medida_warp'
    return None


def _estilo(face, prefixo, corpo, ls, run):
    kerning = 'normal' if run.get('autokerning', True) else 'none'
    lig = 'common-ligatures' if run.get('ligaduras', True) else 'none'
    caps = run.get('font_caps') in ('ALL_CAPS', 'SMALL_CAPS')
    return ("font-family:'%s';font-weight:%d;font-style:normal;font-size:%.4fpx;letter-spacing:%.4fpx;"
            "font-kerning:%s;font-variant-ligatures:%s;font-synthesis:none;%s" % (
                familia_css(prefixo, face['id']), int(face['peso_declarado'] or 400), corpo, ls, kerning, lig,  # numero-neutro: peso normal do CSS
                'font-feature-settings:"cpsp" 1;' if caps else ''))


def montar(camadas_texto, pares, faces, prefixo):
    """Monta a pagina. Devolve (html, plano).

    camadas_texto: camadas do laudo com tipo texto; pares: {fonte_ps: face ou None}; faces: as do job.
    plano: {'camadas': [{layer_id, escala, largura_tysh, motivo_sem_largura, linhas: [{id, ls_ultimo_px}],
    spans: [{id, fonte_ps, cdp}]}], 'sondas': {face_id: id}, 'diagnostico': {face_id: id}}."""
    alvo = float(limites.valor('chromium.corpo_medicao_px'))
    linhas_html, plano = [], {'camadas': [], 'sondas': {}, 'diagnostico': {}}
    for k, c in enumerate(camadas_texto):
        texto = c.get('texto') or {}
        runs = texto.get('runs') or []
        corpos = [float(r.get('corpo_espaco_texto') or 0) for r in runs if r.get('fonte_ps') in pares and pares[r['fonte_ps']]]
        maior = max(corpos) if corpos else 0.0
        escala = alvo / maior if maior > 0 else 1.0
        item = {'layer_id': c['identidade']['layer_id'], 'escala': escala, 'largura_tysh': largura_tysh(texto),
                'motivo_sem_largura': motivo_sem_largura(texto, pares), 'linhas': [], 'spans': []}
        # pedacos por linha: (fonte_ps, estilo, ls_px, texto, cdp)
        linhas = [[]]
        for r in runs:
            ps = r.get('fonte_ps')
            face = pares.get(ps)
            if face is None:
                continue
            corpo = float(r.get('corpo_espaco_texto') or 0) * escala
            ls = float(r.get('tracking') or 0) / 1000.0 * corpo  # numero-neutro: tracking em milesimos de em
            estilo = _estilo(face, prefixo, corpo, ls, r)
            atual = ''
            atual_cdp = None
            for ch in casamento.texto_do_trecho(r):
                if ch in casamento.CONTROLES_DE_QUEBRA:
                    if atual:
                        linhas[-1].append((ps, estilo, ls, atual, atual_cdp))
                    atual, atual_cdp = '', None
                    linhas.append([])
                    continue
                if not casamento.tem_tinta(ch) and ch != ' ' and not ch.isspace():
                    continue
                # caractere sem tinta que a face nao cobre fica num span proprio, fora do CDP: o fallback dele
                # nao deixa marca (pesquisa/corpus-testes.md, 4, item 6)
                cdp = casamento.tem_tinta(ch) or casamento.cobre(face, ord(ch))
                if atual and cdp != atual_cdp:
                    linhas[-1].append((ps, estilo, ls, atual, atual_cdp))
                    atual = ''
                atual += ch
                atual_cdp = cdp
            if atual:
                linhas[-1].append((ps, estilo, ls, atual, atual_cdp))
        for j, ln in enumerate(linhas):
            if not ln:
                continue
            # junta pedacos vizinhos com o mesmo estilo (trechos que so mudam de cor)
            juntos = []
            for p in ln:
                if juntos and juntos[-1][1] == p[1] and juntos[-1][4] == p[4]:
                    juntos[-1] = (p[0], p[1], p[2], juntos[-1][3] + p[3], p[4])
                else:
                    juntos.append(p)
            lid = 'l%d_%d' % (k, j)
            spans = []
            for i, (ps, estilo, ls, t, cdp) in enumerate(juntos):
                sid = 's%d_%d_%d' % (k, j, i)
                spans.append('<span id="%s" style="%s">%s</span>' % (sid, estilo, html.escape(t)))
                item['spans'].append({'id': sid, 'fonte_ps': ps, 'cdp': bool(cdp)})
            item['linhas'].append({'id': lid, 'ls_ultimo_px': juntos[-1][2]})
            linhas_html.append('<div class="l" id="%s">%s</div>' % (lid, ''.join(spans)))
        plano['camadas'].append(item)
    faces_css, sondas = [], []
    for f in faces:
        if not f.get('servivel', True):
            continue
        faces_css.append("@font-face{font-family:'%s';src:url('/fonte/%s');font-weight:%d;font-style:normal;"
                         "font-display:block}" % (familia_css(prefixo, f['id']), f['id'], int(f['peso_declarado'] or 400)))  # numero-neutro: peso normal do CSS
        amostra = casamento.amostra_da_face(f, AMOSTRA_SONDA)
        if not amostra:
            continue
        pid, did = 'p_%s' % f['id'], 'd_%s' % f['id']
        plano['sondas'][f['id']] = pid
        sondas.append('<div class="p" id="%s" style="font-family:\'%s\';font-weight:%d;font-synthesis:none">%s</div>' % (
            pid, familia_css(prefixo, f['id']), int(f['peso_declarado'] or 400), html.escape(amostra)))  # numero-neutro: peso normal do CSS
        if f.get('familia'):
            # diagnostico (arquitetura-v1.md, 4.2): a familia do arquivo pedida pelo nome, sem @font-face, mostra
            # se ha face instalada com o mesmo nome. So registra; nao entra no portao
            plano['diagnostico'][f['id']] = did
            estilo = 'font-family:%s;font-weight:%d' % (_css_texto(f['familia']), int(f['peso_declarado'] or 400))  # numero-neutro: peso normal do CSS
            sondas.append('<div class="p" id="%s" style="%s">%s</div>' % (did, html.escape(estilo, quote=True),
                                                                         html.escape(amostra)))
    doc = ('<!doctype html><html><head><meta charset="utf-8"><style>%s\n*{margin:0;padding:0}'
           'body{background:#fff}.l,.p{white-space:pre;display:block;width:max-content;line-height:1}</style></head>'
           '<body>%s</body></html>' % ('\n'.join(faces_css), '\n'.join(linhas_html + sondas)))
    return doc, plano


def ids_para_cdp(plano):
    ids = [s['id'] for c in plano['camadas'] for s in c['spans'] if s['cdp']]
    return ids + list(plano['sondas'].values()) + list(plano['diagnostico'].values())


def face_confere(fontes_cdp, face):
    """True quando todas as faces que desenharam o elemento sao a do arquivo do job (isCustomFont e um dos nomes
    PostScript do arquivo); False se entrou outra face (fallback); None sem resposta do CDP."""
    if fontes_cdp is None:
        return None
    if not fontes_cdp:
        return False
    nomes = {casamento.normalizar(n) for n in face['nomes_ps']}
    return all(f['propria'] and casamento.normalizar(f['nome_ps']) in nomes for f in fontes_cdp)


def ler_larguras(item, larguras):
    """(largura_com, largura_sem) da camada no espaco de texto, ou (None, None) sem resposta."""
    com, sem = [], []
    for ln in item['linhas']:
        w = larguras.get(ln['id'])
        if not isinstance(w, (int, float)):
            return None, None
        com.append(float(w))
        sem.append(float(w) - float(ln['ls_ultimo_px']))
    if not com:
        return None, None
    return max(com) / item['escala'], max(sem) / item['escala']


def erro_largura_pct(item, larguras):
    """Erro da largura em porcentagem contra a caixa TySh, na variante mais proxima; None sem medida."""
    if item['motivo_sem_largura'] or not item['largura_tysh']:
        return None
    com, sem = ler_larguras(item, larguras)
    if com is None:
        return None
    ref = item['largura_tysh']
    erros = [100.0 * (w / ref - 1.0) for w in (com, sem)]  # numero-neutro: porcentagem
    return min(erros, key=abs)
