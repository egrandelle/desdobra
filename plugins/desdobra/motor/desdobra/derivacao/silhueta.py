# -*- coding: utf-8 -*-
"""A tinta das bases na derivacao: a silhueta que o preparo gravou, ou a caixa, com o aviso (decisao 199, 3).

O preparo (desdobra.ds.silhueta) grava em ds/silhuetas/<sha256>.json a grade do alfa de cada camada que sangra. Aqui
a derivacao so le esses JSON (carregar; nunca a imagem) e leva a tinta de cada elemento de base para o layout:
  - partes_do_elemento: as camadas com tinta do elemento, cada uma com a caixa do asset na mestre do KV e a silhueta
    dela, ou sem silhueta (base sem asset, camada de preenchimento, job lido antes desta versao): a caixa da tinta;
  - tinta_do_elemento: a tinta no espaco da mestre do KV ({'poligonos', 'caixas'}, como desdobra.derivacao.familia),
    cortada na caixa do elemento (o asset da pilha acaba na borda do canvas da mestre) e no canvas;
  - tinta_no_layout: a mesma tinta levada da caixa do elemento na mestre para a caixa dele no formato (a conta do
    render: a pilha escala e anda com a caixa), cortada no formato;
  - relacao / quebrada: a relacao do conteudo com a tinta na mestre (dentro dela, ou livre dela com folga) e se ela se
    perde no formato, com a folga do pixel (derivacao.enquadramento_tolerancia_px).
A base que entra na conta sem silhueta nenhuma e conferida pela caixa, com o aviso forma_conferida_pela_caixa (199, 3;
desenho final, 5). Funcoes puras, menos carregar, que le os JSON do job.
"""
import math
from pathlib import Path

from desdobra import contratos
from desdobra.derivacao import familia as mod_familia

ESQUEMA = 'silhueta/1'
PASTA = Path('ds') / 'silhuetas'
AVISO_CAIXA = 'forma_conferida_pela_caixa'
DENTRO, LIVRE = 'dentro_da_tinta', 'livre_da_tinta'


def carregar(pasta, laudo=None):
    """{layer_id: {'sha256', 'caixa_asset' (px do documento), 'grade'}} das silhuetas gravadas no job. O arquivo de
    outro KV (arquivo_sha256 diferente do laudo) ou fora do contrato fica de fora: a camada cai na caixa. Sem a pasta
    (job lido antes desta versao), {}."""
    if pasta is None:
        return {}
    raiz = Path(pasta) / PASTA
    if not raiz.is_dir():
        return {}
    sha_kv = ((laudo or {}).get('origem') or {}).get('sha256')
    saida = {}
    for arq in sorted(raiz.glob('*.json')):
        try:
            d = contratos.ler(arq, ESQUEMA)
        except contratos.ErroContrato:
            continue
        if d['arquivo_sha256'] is None or (sha_kv is not None and d['arquivo_sha256'] != sha_kv):
            continue
        for c in d['camadas']:
            saida[int(c['layer_id'])] = {'sha256': d['sha256'], 'caixa_asset': [float(v) for v in c['caixa_asset']],
                                         'grade': d['grade']}
    return saida


def _camadas(ctx):
    """{layer_id: camada do laudo}, guardado no contexto (o laudo do contexto nao muda)."""
    por_id = ctx.get('_camadas_por_id')
    if por_id is None:
        por_id = {c['identidade']['layer_id']: c for c in ctx['laudo']['camadas']}
        ctx['_camadas_por_id'] = por_id
    return por_id


def partes_do_elemento(ctx, e, canvas_doc):
    """[(caixa do asset em px da mestre do KV, silhueta {'grade'} ou None)] das camadas visiveis com tinta do
    elemento, na ordem de layer_ids. Sem silhueta, a caixa da tinta da camada."""
    sil = ctx.get('silhuetas') or {}
    cam = _camadas(ctx)
    ox, oy = float(canvas_doc[0]), float(canvas_doc[1])
    partes = []
    for lid in e.get('layer_ids') or ():
        c = cam.get(lid)
        if c is None or not (c.get('aparencia') or {}).get('visivel_efetiva'):
            continue
        s = sil.get(lid)
        if s is not None:
            a = s['caixa_asset']
            partes.append(([a[0] - ox, a[1] - oy, a[2] - ox, a[3] - oy], {'grade': s['grade']}))
            continue
        t = (c.get('geometria') or {}).get('caixa_tinta')
        if t and t[2] > t[0] and t[3] > t[1]:
            partes.append(([float(t[0]) - ox, float(t[1]) - oy, float(t[2]) - ox, float(t[3]) - oy], None))
    return partes


def _cortar(tinta, corte):
    pols = [p for p in (mod_familia._recortar(pol, corte) for pol in tinta['poligonos'])
            if mod_familia._area_poligono(p) > 0]
    cxs = [c for c in (mod_familia._inter(c, corte) for c in tinta['caixas']) if mod_familia._area(c) > 0]
    return {'poligonos': pols, 'caixas': cxs}


def tinta_do_elemento(partes, caixa, W, H):
    """(tinta, sem silhueta) do elemento no espaco da mestre do KV, cortada na caixa dele (caixa_kv) e no canvas W x
    H. sem silhueta: nenhuma parte tem silhueta (a forma e conferida pela caixa)."""
    tinta = {'poligonos': [], 'caixas': []}
    com = False
    for caixa_asset, s in partes:
        t, _borda, sem = mod_familia._tinta([float(v) for v in caixa_asset], s, W, H)
        com = com or not sem
        tinta['poligonos'] += t['poligonos']
        tinta['caixas'] += t['caixas']
    corte = mod_familia._inter([float(v) for v in caixa], [0.0, 0.0, float(W), float(H)])
    return _cortar(tinta, corte), not com


def tinta_no_layout(tinta, de, para, W, H):
    """A tinta levada da caixa de (o elemento na mestre do KV) para a caixa para (o elemento no formato), eixo a eixo,
    e cortada em para e no formato W x H."""
    de, para = [float(v) for v in de], [float(v) for v in para]
    kx = (para[2] - para[0]) / (de[2] - de[0]) if de[2] > de[0] else 1.0
    ky = (para[3] - para[1]) / (de[3] - de[1]) if de[3] > de[1] else 1.0

    def leva(p):
        return [para[0] + (p[0] - de[0]) * kx, para[1] + (p[1] - de[1]) * ky]
    levada = {'poligonos': [[leva(p) for p in pol] for pol in tinta['poligonos']],
              'caixas': [leva(c[:2]) + leva(c[2:]) for c in tinta['caixas']]}
    return _cortar(levada, mod_familia._inter(para, [0.0, 0.0, float(W), float(H)]))


def cobertura(caixa, tinta):
    """Fracao de 0 a 1 da caixa sobre a tinta."""
    return mod_familia._cobertura([float(v) for v in caixa], tinta)


def relacao(caixa, tinta, tol):
    """A relacao do conteudo (caixa) com a tinta na mestre: {'tipo': dentro_da_tinta} quando a caixa inteira esta
    sobre ela (com a folga do pixel tol), {'tipo': livre_da_tinta, 'folga'} quando nao toca nela, ou None (sobre a borda
    da forma, ou sem tinta)."""
    caixa = [float(v) for v in caixa]
    if not tinta['poligonos'] and not tinta['caixas']:
        return None
    if mod_familia._dentro(caixa, tinta, tol):
        return {'tipo': DENTRO}
    d, invade, _pt, _pc = mod_familia._distancia(caixa, tinta)
    if invade or not math.isfinite(d):
        return None
    return {'tipo': LIVRE, 'folga': d}


def quebrada(rel, caixa, tinta, tol):
    """A relacao rel se perde com o conteudo em caixa sobre a tinta do formato: o conteudo que estava dentro sai em
    parte dela; o que estava livre passa a ficar sobre ela, alem da folga do pixel tol."""
    caixa = [float(v) for v in caixa]
    if rel['tipo'] == DENTRO:
        return not mod_familia._dentro(caixa, tinta, tol)
    return mod_familia._cobertura(mod_familia._encolhida(caixa, tol), tinta) > mod_familia.AREA_IGUAL
