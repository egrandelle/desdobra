# -*- coding: utf-8 -*-
"""Elementos da mestre: o que a derivacao move junto, montado da funcao resolvida e da medida de cada camada.

Um elemento e o conjunto das camadas desenhaveis que herdam a funcao do mesmo lugar (o grupo ou a camada onde o DA
deu a funcao, a raiz). O nome da camada nunca entra. A caixa do elemento e a uniao das caixas de tinta das camadas,
cortada no canvas da mestre: e o que o asset da pilha tem (o render compoe dentro do canvas). Os lados onde a caixa
encosta na borda do canvas da mestre (ou passa dela) sangram: no formato, o corte tem de continuar fora do canvas.

Cena sobreposta vira bloco rigido (decisoes-v1.md, 95): elementos de cena que se sobrepoem, com a mesclagem e os
ajustes acima deles, andam com uma escala so e sao compostos numa pilha so, como no render da origem. A camada clipada
anda com a base do clip (o compositor so a desenha sobre a base), e o ajuste e a mesclagem atuam so onde atuam no KV:
na base do clip, dentro do grupo isolado (grupo com mesclagem propria) ou, em grupo em passagem, em tudo embaixo.

Funcao pura do laudo, do design system e da funcao resolvida.
"""
from desdobra import limites
from desdobra.briefing import modelo as mb

LADOS = ('esq', 'topo', 'dir', 'base')
CLASSES_SEM_SANGRIA = ('texto', 'marca')
TIPOS_QUE_ATUAM = ('ajuste',)  # camada sem tinta propria que muda o que esta embaixo
TIPOS_SEPARADOS_NO_RENDER = ('texto', 'smart_linkado')  # o render da origem desenha estas fora da pilha
TIPOS_DE_COR = ('cor_solida', 'preenchimento')  # tinta de cor (luz, sombra, tom): nao e objeto que corta


def canvas_da_mestre(laudo, quadro):
    """[x0, y0, x1, y1] do canvas da mestre no espaco do documento: a prancheta escolhida, ou o documento inteiro
    (quadro por grupo de topo, ou sem quadro)."""
    doc = laudo['documento']
    for q in doc.get('quadros') or []:
        if q['id'] == quadro and q.get('regra') == 'pranchetas':
            return [float(v) for v in q['caixa']]
    return [0.0, 0.0, float(doc['largura']), float(doc['altura'])]


def _uniao(a, b):
    if a is None:
        return list(b)
    return [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]


def _folgas_de_resolucao(ds):
    """{layer_id: folga de resolucao} das medidas do design system (quanto o raster ainda pode ampliar)."""
    saida = {}
    for m in ((ds or {}).get('tokens') or {}).get('medidas') or []:
        f = (m.get('folga_resolucao') or {}).get('folga')
        if f is not None:
            saida[m['camada']] = float(f)
    return saida


def _area(c):
    return max(0.0, c[2] - c[0]) * max(0.0, c[3] - c[1])


def _corte(a, b):
    return [max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])]


def _inter(a, b):
    return _area(_corte(a, b))


def mesclagem(camada):
    return (camada.get('aparencia') or {}).get('blend') not in (None, 'NORMAL', 'PASS_THROUGH')


def mascara_raster(camada):
    mk = (camada.get('aparencia') or {}).get('mascara') or {}
    return mk if mk.get('raster') and not mk.get('desativada') else None


def _caixa_de_tinta(camada):
    geo = camada.get('geometria') or {}
    cx = geo.get('caixa_tinta') or geo.get('caixa')
    if cx and cx[2] > cx[0] and cx[3] > cx[1]:
        return [float(v) for v in cx]
    return None


def influencia(camada, canvas, caixa=None):
    """Onde uma camada que atua embaixo (ajuste, ou ajuste global com tinta) atua: a caixa de tinta dela, quando tem;
    cortada pela caixa da mascara quando fora dela a mascara e preta; sem tinta e sem mascara, o canvas inteiro."""
    base = list(caixa) if caixa else list(canvas)
    mk = mascara_raster(camada)
    if mk and mk.get('cor_fundo') == 0 and mk.get('caixa') and _area(mk['caixa']) > 0:
        return _corte(base, [float(v) for v in mk['caixa']])
    return base


def _opacidade_efetiva(camada, camadas):
    """Opacidade x preenchimento da camada x opacidade dos grupos acima, de 0 a 1 (sem o campo, 255)."""
    ap = camada.get('aparencia') or {}
    v = (float(ap.get('opacidade', 255)) / 255.0) * (float(ap.get('preenchimento', 255)) / 255.0)  # numero-neutro: escala de 8 bits
    for gid in camada.get('caminho_ids') or []:
        g = (camadas.get(gid) or {}).get('aparencia') or {}
        v *= float(g.get('opacidade', 255)) / 255.0  # numero-neutro: escala de 8 bits
    return v


def de_cena(el):
    """Elemento que pode entrar num bloco de cena: classe base, menos o sujeito (que e conteudo)."""
    return el['classe'] == 'base' and el['funcao'] != 'sujeito'


def bases_de_clip(laudo):
    """{layer_id: layer_id da base} das camadas clipadas: a camada mais perto embaixo, no mesmo pai, sem clipping
    (a ordem do laudo e de baixo para cima, com o grupo antes dos filhos)."""
    cs = laudo['camadas']
    base = {}
    for k, c in enumerate(cs):
        if not (c.get('aparencia') or {}).get('clipping'):
            continue
        for q in range(k - 1, -1, -1):
            o = cs[q]
            if o.get('pai_id') == c.get('pai_id') and not (o.get('aparencia') or {}).get('clipping'):
                base[c['identidade']['layer_id']] = o['identidade']['layer_id']
                break
    return base


def _escopo(camada, camadas):
    """O grupo isolado mais perto acima da camada (grupo com mesclagem propria, que compoe os filhos sozinho), ou None
    quando todos os grupos acima dela estao em passagem."""
    for gid in reversed(camada.get('caminho_ids') or []):
        g = camadas.get(gid)
        if g is not None and (g.get('aparencia') or {}).get('blend') not in (None, 'PASS_THROUGH'):
            return gid
    return None


def montar(laudo, resolvidas, quadro, ds=None):
    """Mestre do KV: {'canvas_doc', 'largura', 'altura', 'elementos', 'sem_geometria', 'fora_da_peca',
    'fora_do_canvas', 'sem_bloco', 'ajuste_global_sobre_conteudo', 'blocos_partidos', 'fundo_ambiguo'}. Cada
    elemento: id, raiz, funcao, classe, layer_ids, texto, caixa (no canvas da mestre, origem no canto), caixa_doc,
    sangra (por lado), corpo_px, folga_resolucao, bloco, membros, membros_funcoes, membros_camadas, membros_caixas
    (os membros que tem de ficar inteiros no formato), z (a primeira e a ultima posicao na pilha) e opaco.

    Bloco rigido (decisoes-v1.md, 95): entram no mesmo bloco os elementos de cena que se sobrepoem na mestre (pelo
    menos derivacao.bloco_sobreposicao_min da menor caixa), a camada em mesclagem diferente da normal com os de cena
    que ela pega embaixo, a camada que atua embaixo (ajuste, ajuste global) com os de cena que ela cobre embaixo, e a
    camada clipada com a base do clip. O bloco anda com uma escala e um deslocamento so; a funcao e a ancora sao as do
    maior membro (desempate pela ordem da pilha: o de baixo), e a regra e a do bloco (decisoes-v1.md, 100). O elemento
    de cena que cobre quase todo o canvas (derivacao.bloco_fundo_fracao) e fundo de cena: nao junta os outros so por
    sobreposicao; logo abaixo do limiar (derivacao.bloco_fundo_faixa_ambigua) ele junta e vai para fundo_ambiguo.
    Camada que atua embaixo sem elemento de cena embaixo vai para sem_bloco (erro no conferir). Ajuste global que
    tambem cobre conteudo embaixo vai para ajuste_global_sobre_conteudo (o formato volta ao DA). Elemento cuja pilha
    tem outro elemento (ou um texto, ou um linkado, que o render desenha a parte) entre um efeito e o que ele pega vai
    para blocos_partidos (o formato volta ao DA: o render nao compoe o bloco numa pilha so sem levar o do meio)."""
    canvas = canvas_da_mestre(laudo, quadro)
    ox, oy, cx1, cy1 = canvas
    W, H = cx1 - ox, cy1 - oy
    tol = limites.valor('derivacao.enquadramento_tolerancia_px')
    frac = limites.valor('derivacao.bloco_sobreposicao_min')
    frac_fundo = limites.valor('derivacao.bloco_fundo_fracao')
    faixa_fundo = limites.valor('derivacao.bloco_fundo_faixa_ambigua')
    camadas = mb.camadas_do_laudo(laudo)
    folgas = _folgas_de_resolucao(ds)
    ordem = {c['identidade']['layer_id']: k for k, c in enumerate(laudo['camadas'])}
    base_clip = bases_de_clip(laudo)
    op_min = limites.valor('derivacao.objeto_solto_opacidade_min')

    def raiz_da(lid):
        """A raiz do elemento a que a camada (ou o grupo) pertence, ou None."""
        if lid in resolvidas:
            return resolvidas[lid]['raiz']
        for x in sorted(resolvidas, key=lambda y: ordem.get(y, 0)):
            if lid in (camadas[x].get('caminho_ids') or []):
                return resolvidas[x]['raiz']
        return None

    por_raiz, sem_geo, fora, fora_canvas = {}, [], [], []
    camadas_el = {}  # layer_id -> registro da camada no elemento
    for lid in sorted(resolvidas, key=lambda x: ordem.get(x, 0)):
        r = resolvidas[lid]
        f = r['funcao']
        if f == mb.FUNCAO_FORA:
            fora.append(lid)
            continue
        if f == mb.FUNCAO_ESTRUTURA:
            sem_geo.append(lid)
            continue
        c = camadas[lid]
        z = ordem.get(lid, 0)
        caixa = _caixa_de_tinta(c)
        clip = base_clip.get(lid)
        if clip is not None and caixa is not None and clip in camadas:
            cb = _caixa_de_tinta(camadas[clip])
            if cb is not None:
                caixa = _corte(caixa, cb) if _inter(caixa, cb) > 0 else None
        el = por_raiz.setdefault(r['raiz'], {'id': 'el%d' % r['raiz'], 'raiz': r['raiz'], 'funcao': f,
                                             'classe': mb.CLASSES[f], 'layer_ids': [], 'texto': False,
                                             '_caixa': None, 'corpo_px': None, 'folga_resolucao': None,
                                             '_zs': [], '_nao_clipado': False, '_opaco': False, '_objeto': False})
        el['layer_ids'].append(lid)
        el['_zs'].append(z)
        atua = c.get('tipo') in TIPOS_QUE_ATUAM or f == mb.FUNCAO_AJUSTE
        reg = {'lid': lid, 'z': z, 'raiz': r['raiz'], 'tipo': c.get('tipo'), 'clip': clip, 'atua': atua,
               'global': f == mb.FUNCAO_AJUSTE, 'mescla': mesclagem(c), 'escopo': _escopo(c, camadas),
               'caminho': list(c.get('caminho_ids') or []), 'caixa': None, 'influencia': None}
        camadas_el[lid] = reg
        if c.get('tipo') == 'texto':
            el['texto'] = True
            corpo = _corpo(c)
            if corpo is not None:
                el['corpo_px'] = max(el['corpo_px'] or 0.0, corpo)
        if lid in folgas:
            el['folga_resolucao'] = min(el['folga_resolucao'], folgas[lid]) if el['folga_resolucao'] else folgas[lid]
        if atua:
            # o ajuste global nunca e elemento proprio, com tinta ou sem (decisoes-v1.md, 99)
            reg['influencia'] = influencia(c, canvas, caixa)
        elif caixa is not None:
            reg['caixa'] = caixa
            el['_caixa'] = _uniao(el['_caixa'], caixa)
            el['_nao_clipado'] = el['_nao_clipado'] or clip is None
            # opaco: alguma camada em mesclagem normal com opacidade efetiva (camada e grupos acima) de pelo menos
            # derivacao.objeto_solto_opacidade_min (revisao 3, M3: um brilho em NORMAL com opacidade baixa e luz)
            el['_opaco'] = el['_opaco'] or (not reg['mescla'] and _opacidade_efetiva(c, camadas) >= op_min)
            el['_objeto'] = el['_objeto'] or c.get('tipo') not in TIPOS_DE_COR
        else:
            reg['influencia'] = influencia(c, canvas)
    com_tinta, sem_tinta = [], []
    for el in por_raiz.values():
        bruta = el.pop('_caixa')
        if bruta is None:
            atuam = any(camadas_el[x]['atua'] for x in el['layer_ids'])
            if el['classe'] in CLASSES_SEM_SANGRIA and not atuam:
                fora_canvas.extend(el['layer_ids'])
            else:
                sem_tinta.append(el)
            continue
        corte = _corte(bruta, canvas)
        if corte[2] <= corte[0] or corte[3] <= corte[1]:
            fora_canvas.extend(el['layer_ids'])
            continue
        el['caixa_doc'] = corte
        el['_bruta'] = bruta
        com_tinta.append(el)
    tinta = {el['raiz']: el for el in com_tinta}
    pai = {r: r for r in tinta}

    def raiz_de(x):
        while pai[x] != x:
            pai[x] = pai[pai[x]]
            x = pai[x]
        return x

    def unir(a, b):
        ra, rb = raiz_de(a), raiz_de(b)
        if ra != rb:
            pai[max(ra, rb)] = min(ra, rb)

    area_canvas = W * H
    fundo_ambiguo = []

    def fundo_de_cena(el):
        # o que cobre quase todo o canvas nao junta os outros so por sobreposicao
        return _area(el['caixa_doc']) >= frac_fundo * area_canvas

    cena = [el for el in com_tinta if de_cena(el)]
    for el in cena:
        fr = _area(el['caixa_doc']) / area_canvas
        if frac_fundo - faixa_fundo <= fr < frac_fundo:
            fundo_ambiguo.append({'elemento': el['id'], 'fracao': round(fr, 4)})
    for i, a in enumerate(cena):
        for b in cena[i + 1:]:
            inter = _inter(a['caixa_doc'], b['caixa_doc'])
            if inter > 0 and not fundo_de_cena(a) and not fundo_de_cena(b) and \
                    inter >= frac * min(_area(a['caixa_doc']), _area(b['caixa_doc'])):
                unir(a['raiz'], b['raiz'])

    def no_escopo(reg, alvo):
        return reg['escopo'] is None or reg['escopo'] in alvo['caminho']

    def embaixo(reg, area, so_cena=True):
        """Elementos com tinta que tem camada embaixo de reg, no escopo dele, tocando a area."""
        saida = []
        for alvo in camadas_el.values():
            el = tinta.get(alvo['raiz'])
            if el is None or alvo['caixa'] is None or alvo['z'] >= reg['z'] or not no_escopo(reg, alvo):
                continue
            if (de_cena(el) if so_cena else not de_cena(el)) and _inter(alvo['caixa'], area) > 0 and el not in saida:
                saida.append(el)
        return saida

    # a camada clipada anda com a base do clip
    anexos, sem_bloco, global_sobre_conteudo = {}, [], []
    for reg in camadas_el.values():
        if reg['clip'] is None:
            continue
        rb = raiz_da(reg['clip'])
        if rb is None or rb not in tinta:
            continue
        if reg['raiz'] in tinta:
            unir(reg['raiz'], rb)
    # mesclagem: pega os de cena embaixo, no escopo, onde a tinta dela toca
    for reg in camadas_el.values():
        if not reg['mescla'] or reg['caixa'] is None or reg['clip'] is not None:
            continue
        el = tinta.get(reg['raiz'])
        if el is None or not de_cena(el):
            continue
        for alvo in embaixo(reg, reg['caixa']):
            unir(el['raiz'], alvo['raiz'])
    # camadas que atuam embaixo (e o elemento inteiro sem tinta): o que elas cobrem embaixo
    anexado = set()
    sem_tinta_raizes = {el['raiz'] for el in sem_tinta}
    for reg in sorted(camadas_el.values(), key=lambda x: x['z']):
        if reg['influencia'] is None or (reg['raiz'] not in tinta and reg['raiz'] not in sem_tinta_raizes):
            # sem efeito, ou de elemento que ja saiu (texto vazio, tinta fora do canvas)
            continue
        dono = por_raiz[reg['raiz']]
        if reg['clip'] is not None:
            rb = raiz_da(reg['clip'])
            if rb in tinta:
                if reg['raiz'] in tinta:
                    unir(reg['raiz'], rb)
                elif reg['raiz'] not in anexado:
                    anexos.setdefault(rb, []).append(dono)
                    anexado.add(reg['raiz'])
                continue
        if reg['raiz'] in tinta and not reg['atua']:
            continue
        alvos = embaixo(reg, reg['influencia'])
        if reg['global'] and embaixo(reg, reg['influencia'], so_cena=False):
            global_sobre_conteudo.append(reg['lid'])
        if reg['raiz'] in tinta:
            if de_cena(tinta[reg['raiz']]):
                for alvo in alvos:
                    unir(reg['raiz'], alvo['raiz'])
            continue
        if not alvos:
            continue
        for alvo in alvos[1:]:
            unir(alvos[0]['raiz'], alvo['raiz'])
        if reg['raiz'] not in anexado:
            anexos.setdefault(alvos[0]['raiz'], []).append(dono)
            anexado.add(reg['raiz'])
    for el in sem_tinta:
        if el['raiz'] not in anexado:
            sem_bloco.extend(el['layer_ids'])
    grupos = {}
    for el in com_tinta:
        grupos.setdefault(raiz_de(el['raiz']), []).append(el)
    for chave, lista in anexos.items():
        grupos[raiz_de(chave)].extend(lista)
    elementos, partidos = [], []
    for membros in grupos.values():
        elementos.append(_juntar(membros, canvas, tol))
    for el in elementos:
        p = _partido(el, camadas_el, elementos)
        if p is not None:
            partidos.append(p)
    elementos.sort(key=lambda e: e['raiz'])
    return {'canvas_doc': canvas, 'largura': W, 'altura': H, 'elementos': elementos, 'sem_geometria': sorted(sem_geo),
            'fora_da_peca': sorted(fora), 'fora_do_canvas': sorted(fora_canvas), 'sem_bloco': sorted(sem_bloco),
            'ajuste_global_sobre_conteudo': sorted(set(global_sobre_conteudo)), 'blocos_partidos': partidos,
            'fundo_ambiguo': fundo_ambiguo}


def _juntar(membros, canvas, tol):
    """O elemento de um grupo de membros (um so, ou um bloco)."""
    ox, oy, cx1, cy1 = canvas
    W, H = cx1 - ox, cy1 - oy
    com = [m for m in membros if m.get('caixa_doc')]
    # o maior membro desenhado por si (nao so clipado); empate: o de baixo na pilha
    maior = max(com, key=lambda m: (m['_nao_clipado'], _area(m['caixa_doc']), -min(m['_zs'])))
    el = {k: v for k, v in maior.items() if not k.startswith('_')}
    el['layer_ids'] = sorted({lid for m in membros for lid in m['layer_ids']})
    el['membros'] = sorted(m['raiz'] for m in membros)
    el['bloco'] = len(membros) > 1
    el['membros_funcoes'] = {m['raiz']: m['funcao'] for m in membros}
    el['membros_camadas'] = {m['raiz']: sorted(m['layer_ids']) for m in membros}
    corte = com[0]['caixa_doc']
    for m in com[1:]:
        corte = _uniao(corte, m['caixa_doc'])
    folgas_m = [m['folga_resolucao'] for m in membros if m.get('folga_resolucao')]
    el['folga_resolucao'] = min(folgas_m) if folgas_m else None
    corpos = [m['corpo_px'] for m in membros if m.get('corpo_px')]
    el['corpo_px'] = max(corpos) if corpos else None
    el['texto'] = any(m['texto'] for m in membros)
    zs = [z for m in membros for z in m['_zs']]
    el['z'] = [min(zs), max(zs)]
    el['opaco'] = de_cena(el) and any(m['_opaco'] for m in com)
    el['caixa_doc'] = corte
    el['caixa'] = [corte[0] - ox, corte[1] - oy, corte[2] - ox, corte[3] - oy]
    el['caixa_kv'] = list(el['caixa'])
    # o asset da pilha acaba na borda do canvas da mestre: o compositor corta na borda do documento, e a prancheta
    # corta o que passa dela. O corte do asset e o que nao pode aparecer no formato (solver e validacao usam esta
    # caixa; ela fica separada da caixa visivel para o dia em que o asset trouxer o que passa da prancheta)
    el['caixa_asset_doc'] = list(corte)
    el['caixa_asset'] = list(el['caixa'])
    x0, y0, x1, y1 = el['caixa']
    el['sangra'] = {'esq': x0 <= tol, 'topo': y0 <= tol, 'dir': x1 >= W - tol, 'base': y1 >= H - tol}
    if el['classe'] in CLASSES_SEM_SANGRIA:
        # texto e marca nunca ficam dispensados da area util, das faixas e da area segura da folha: o que encosta
        # na borda do KV conta como dentro do canvas
        el['sangra'] = {lado: False for lado in LADOS}
    # membros do bloco que tem de continuar inteiros no formato: o objeto (camada com desenho proprio, nao so cor
    # solida ou preenchimento, que sao luz e tom sobre a cena) que estava inteiro dentro do canvas da mestre, e o
    # texto e a marca (que nunca sangram)
    el['membros_caixas'] = []
    if el['bloco']:
        for m in com:
            c = [m['caixa_doc'][0] - ox, m['caixa_doc'][1] - oy, m['caixa_doc'][2] - ox, m['caixa_doc'][3] - oy]
            inteiro = c[0] > tol and c[1] > tol and c[2] < W - tol and c[3] < H - tol and \
                m['_bruta'] == m['caixa_doc']
            if (inteiro and m['_objeto']) or m['classe'] in CLASSES_SEM_SANGRIA:
                el['membros_caixas'].append({'raiz': m['raiz'], 'classe': m['classe'], 'caixa': c})
    return el


def _partido(el, camadas_el, elementos):
    """O elemento cuja pilha tem, entre um efeito dele (camada que atua embaixo, mesclagem ou camada clipada) e o que
    o efeito pega, uma camada de outro elemento ou uma camada que o render desenha fora da pilha (texto, linkado).
    Devolve {'elemento', 'separadores', 'efeitos'} ou None."""
    meus = [camadas_el[x] for x in el['layer_ids'] if x in camadas_el]
    z0, z1 = el['z']
    de_quem = {}
    for e in elementos:
        for lid in e['layer_ids']:
            de_quem[lid] = e['id']
    separadores = [r for r in camadas_el.values()
                   if z0 < r['z'] < z1 and ((de_quem.get(r['lid']) not in (None, el['id'])) or
                                            (de_quem.get(r['lid']) == el['id'] and r['tipo'] in TIPOS_SEPARADOS_NO_RENDER))]
    if not separadores:
        return None
    seps, efeitos = set(), set()
    for x in meus:
        if not (x['atua'] or x['mescla'] or x['clip'] is not None or x['influencia'] is not None):
            continue
        area = x['influencia'] if x['influencia'] is not None else x['caixa']
        for s in separadores:
            if not (s['z'] < x['z']) or s['lid'] == x['lid']:
                continue
            pega = [y for y in meus if y['z'] < s['z'] and y['caixa'] is not None and
                    (x['clip'] == y['lid'] or (x['clip'] is None and area is not None and _inter(y['caixa'], area) > 0))]
            if pega:
                seps.add(s['lid'])
                efeitos.add(x['lid'])
    if not efeitos:
        return None
    return {'elemento': el['id'], 'separadores': sorted(seps), 'efeitos': sorted(efeitos)}


def _corpo(camada):
    """Maior corpo efetivo (no dispositivo) dos trechos com tinta, como o laudo mede."""
    t = camada.get('texto') or {}
    corpos = [float(r['corpo_efetivo']) for r in t.get('runs') or [] if r.get('tem_tinta') and r.get('corpo_efetivo')]
    return max(corpos) if corpos else None
