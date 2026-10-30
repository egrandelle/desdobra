# -*- coding: utf-8 -*-
"""Quadros e variantes ocultas como entidades do laudo (pesquisa/corpus-testes.md, 4, itens 1 e 2).

Regra dos quadros, portada do instrumento de teste da pesquisa:
  - pranchetas: cada prancheta e um quadro;
  - grupos de topo: grupos filhos do documento que contem uma camada (nao grupo) cuja caixa cobre ao menos
    quadros.fracao_canvas_grupo_topo do canvas, com no maximo um deles visivel ao salvar. Precisa de ao
    menos quadros.min_candidatos grupos assim.
Com mais de um quadro, a peca sai do quadro que o DA escolher (decisoes-v1.md, 29/10, 1).

Variante oculta: o no oculto mais alto de um ramo (camada ou grupo com visibilidade propria desligada e todos
os grupos acima visiveis) que tem conteudo. Pode ser variante em uso, como o modelo oculto que a arte final
usa numa pagina (pesquisa/corpus-testes.md, 4, item 2). Quadros ocultos nao entram, porque ja sao quadros.
"""
from desdobra import limites

KINDS_FUNDO = ('gradientfill', 'solidcolorfill', 'patternfill', 'pixel', 'smartobject', 'shape')


def _fracao_canvas(caixa, largura, altura):
    x0, y0, x1, y1 = caixa
    ix = max(0, min(largura, x1) - max(0, x0))
    iy = max(0, min(altura, y1) - max(0, y0))
    return ix * iy / float(largura * altura)


def detectar(estrutura):
    doc = estrutura['documento']
    W, H = doc['largura'], doc['altura']
    regs = estrutura['camadas']
    quadros = []
    if doc.get('pranchetas'):
        for k, a in enumerate(sorted(doc['pranchetas'], key=lambda p: (p['caixa'][0], p['caixa'][1])), 1):
            quadros.append({'id': 'q%d' % k, 'regra': 'pranchetas', 'layer_id': a['layer_id'], 'nome': a.get('nome', ''),
                            'caixa': a['caixa'], 'visivel_ao_salvar': bool(a.get('visivel_propria'))})
        return quadros
    lim = limites.obter('quadros.fracao_canvas_grupo_topo')
    fracao_min = limites.valor('quadros.fracao_canvas_grupo_topo')
    minimo = limites.valor('quadros.min_candidatos')
    topo = [r for r in regs if r.get('pai_id') is None and r.get('kind') == 'group']
    cand = []
    for g in topo:
        filhos = [r for r in regs if g['layer_id'] in (r.get('caminho_ids') or []) and r.get('kind') not in ('group', 'artboard')]
        if any(r.get('kind') in KINDS_FUNDO and _fracao_canvas(r['caixa'], W, H) >= fracao_min for r in filhos):
            cand.append(g)
    if len(cand) >= minimo and sum(1 for g in cand if g.get('visivel_propria')) <= 1:
        for k, g in enumerate(cand, 1):
            quadros.append({'id': 'q%d' % k, 'regra': 'grupos_de_topo', 'layer_id': g['layer_id'], 'nome': g.get('nome', ''),
                            'caixa': _caixa_do_grupo(g, regs), 'visivel_ao_salvar': bool(g.get('visivel_propria')),
                            'limite': lim.citacao()})
    return quadros


def _caixa_do_grupo(g, regs):
    """A caixa do grupo; se vazia (o psd-tools zera a de grupo oculto), a uniao das caixas de dentro."""
    if _area(g.get('caixa')):
        return g['caixa']
    caixas = [r['caixa'] for r in regs if g['layer_id'] in (r.get('caminho_ids') or []) and _area(r.get('caixa'))]
    if not caixas:
        return g.get('caixa') or [0, 0, 0, 0]
    return [min(c[0] for c in caixas), min(c[1] for c in caixas), max(c[2] for c in caixas), max(c[3] for c in caixas)]


def quadro_da_camada(reg, quadros):
    for q in quadros:
        if reg['layer_id'] == q['layer_id'] or q['layer_id'] in (reg.get('caminho_ids') or []):
            return q['id']
    return None


def variantes_ocultas(estrutura, quadros):
    regs = estrutura['camadas']
    por_id = {r['layer_id']: r for r in regs}
    ids_quadro = {q['layer_id'] for q in quadros}
    out = []
    for r in regs:
        if r.get('visivel_propria') or r['layer_id'] in ids_quadro:
            continue
        anc = [por_id.get(i) for i in (r.get('caminho_ids') or [])]
        if any(a is None or (not a.get('visivel_propria') and a['layer_id'] not in ids_quadro) for a in anc):
            continue
        if r.get('kind') in ('group', 'artboard'):
            conteudo = [x for x in regs if r['layer_id'] in (x.get('caminho_ids') or []) and x.get('kind') not in ('group', 'artboard')
                        and _area(x.get('caixa_tinta') or x.get('caixa'))]
            if not conteudo:
                continue
            motivo = 'grupo oculto com %d camadas com conteúdo' % len(conteudo)
        else:
            if not _area(r.get('caixa_tinta') or r.get('caixa')):
                continue
            motivo = 'camada oculta com conteúdo'
        out.append({'layer_id': r['layer_id'], 'motivo': motivo, 'quadro': quadro_da_camada(r, quadros)})
    return out


def _area(b):
    return 0 if not b else max(0, b[2] - b[0]) * max(0, b[3] - b[1])
