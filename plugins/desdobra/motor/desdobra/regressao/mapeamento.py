# -*- coding: utf-8 -*-
"""Mapeamento entre o laudo da sonda da pesquisa (formato antigo, psd-tools 1.26.0) e o laudo/1.

Os dois formatos viram a mesma forma normalizada, e so ela e comparada (comparar.py):

    {'formato': 'sonda' | 'laudo/1',
     'psd_tools': '1.26.0' | None,
     'tem_laudo': bool (False quando a leitura nao deixou laudo legivel),
     'execucao': {'situacao': ok | erro | tempo | recusado | orcamento | auditoria | sem_laudo | laudo_invalido,
                  'motivo': texto fixo ou None},
     'prova_pixel': {'feita': bool, 'pct': float | None, 'motivo': texto ou None,
                     'px_acima': int | None, 'px_total': int | None (so no laudo/1)},
     'tempo_s': {'interno': float | None, 'externo': float | None},
     'camadas': {layer_id: {'situacao', 'tipo', 'caixa', 'visivel', 'texto', 'texto_runs', 'regras'}}}

Toda diferenca de nome entre os formatos fica aqui, em funcoes pequenas, para que o comparador nunca
precise saber de onde veio cada lado:
  - situacao: lido/degradado/bloqueante (sonda) para lida/degradada/bloqueante (laudo/1);
  - tipo: kind e classe do psd-tools (sonda) para o tipo do laudo/1;
  - caixa: bbox (sonda) e geometria.caixa (laudo/1);
  - visibilidade: visivel_efetiva (sonda) e aparencia.visivel_efetiva (laudo/1);
  - texto: texto.conteudo e os trechos (inicio, fim, fonte_ps) nos dois;
  - regras: prefixo "D7:" dos motivos em texto (sonda) e motivos[].regra (laudo/1);
  - prova de pixel: fidelidade.pct_px_acima_de_24_qualquer_canal (sonda) e
    prova_pixel.pct_px_acima_qualquer_canal (laudo/1), os dois em porcentagem dos pixels do canvas.
"""
import re

SITUACAO_DA_SONDA = {'lido': 'lida', 'degradado': 'degradada', 'bloqueante': 'bloqueante'}

# kind do psd-tools (como a sonda grava) -> tipo do laudo/1
TIPO_POR_KIND = {
    'type': 'texto',
    'shape': 'forma',
    'pixel': 'pixel',
    'solidcolorfill': 'cor_solida',
    'gradientfill': 'preenchimento',
    'patternfill': 'preenchimento',
    'group': 'grupo',
    'artboard': 'prancheta',
}
KINDS_DE_AJUSTE = frozenset({
    'brightnesscontrast', 'levels', 'curves', 'exposure', 'vibrance', 'huesaturation', 'colorbalance',
    'blackandwhite', 'photofilter', 'channelmixer', 'colorlookup', 'invert', 'posterize', 'threshold',
    'selectivecolor', 'gradientmap',
})
TIPOS_SMART_EMBUTIDO = frozenset({'embedded', 'liFD'})

# situacao da execucao da sonda (status_execucao.status de rodar_corpus_126.py) -> situacao normalizada
EXECUCAO_DA_SONDA = {'ok': 'ok', 'timeout': 'tempo', 'erro': 'erro', 'pulado': 'erro'}

_REGRA_NO_MOTIVO = re.compile(r'^\s*([BD][0-9]+)\s*:')


# ------------------------------------------------------------------ sonda
def situacao_da_sonda(camada):
    laudo = camada.get('laudo') if isinstance(camada.get('laudo'), dict) else {}
    return SITUACAO_DA_SONDA.get(laudo.get('status') or camada.get('status_laudo'))


def regras_da_sonda(camada):
    laudo = camada.get('laudo') if isinstance(camada.get('laudo'), dict) else {}
    regras = set()
    for motivo in laudo.get('motivos') or []:
        if isinstance(motivo, str):
            m = _REGRA_NO_MOTIVO.match(motivo)
            if m:
                regras.add(m.group(1))
        elif isinstance(motivo, dict) and motivo.get('regra'):
            regras.add(motivo['regra'])
    return sorted(regras)


def tipo_da_sonda(camada):
    kind = (camada.get('kind') or '').lower()
    if kind == 'smartobject':
        so = camada.get('smart_object') or {}
        embutido = so.get('tipo') in TIPOS_SMART_EMBUTIDO or so.get('tipo_bruto') in TIPOS_SMART_EMBUTIDO
        return 'smart_embutido' if embutido else 'smart_linkado'
    if kind in KINDS_DE_AJUSTE:
        return 'ajuste'
    return TIPO_POR_KIND.get(kind, 'outro')


def caixa(valor):
    if isinstance(valor, (list, tuple)) and all(isinstance(v, (int, float)) for v in valor):
        return [int(v) for v in valor]
    return None


def texto_normalizado(texto):
    """(conteudo, trechos) de um texto no formato comum a sonda e a estrutura/1."""
    if not isinstance(texto, dict):
        return None, None
    runs = [[r.get('inicio'), r.get('fim'), r.get('fonte_ps')] for r in texto.get('runs') or [] if isinstance(r, dict)]
    return texto.get('conteudo'), runs


def camada_da_sonda(camada):
    conteudo, runs = texto_normalizado(camada.get('texto'))
    return {'situacao': situacao_da_sonda(camada), 'tipo': tipo_da_sonda(camada), 'caixa': caixa(camada.get('bbox')),
            'visivel': camada.get('visivel_efetiva'), 'texto': conteudo, 'texto_runs': runs,
            'regras': regras_da_sonda(camada)}


def prova_pixel_da_sonda(laudo):
    fid = laudo.get('fidelidade') if isinstance(laudo.get('fidelidade'), dict) else {}
    resumo = (laudo.get('resumo') or {}).get('fidelidade') or {}
    pct = fid.get('pct_px_acima_de_24_qualquer_canal', resumo.get('pct_px_acima_de_24_qualquer_canal'))
    feita = bool(fid.get('feita')) if fid else pct is not None
    return {'feita': feita and pct is not None, 'pct': pct if feita else None,
            'motivo': fid.get('motivo') or (laudo.get('resumo') or {}).get('fidelidade_motivo')}


def normalizar_sonda(laudo):
    execucao = laudo.get('status_execucao') or {}
    camadas = {}
    for c in laudo.get('camadas') or []:
        if isinstance(c.get('layer_id'), int):
            camadas[c['layer_id']] = camada_da_sonda(c)
    return {'formato': 'sonda', 'psd_tools': laudo.get('psd_tools'), 'tem_laudo': True,
            'execucao': {'situacao': EXECUCAO_DA_SONDA.get(execucao.get('status'), 'ok' if not execucao else 'erro'),
                         'motivo': execucao.get('motivo')},
            'prova_pixel': prova_pixel_da_sonda(laudo),
            'tempo_s': {'interno': laudo.get('tempo_s'), 'externo': execucao.get('tempo_s_externo')},
            'camadas': camadas}


# ------------------------------------------------------------------ laudo/1
def _sem_efeito(valores):
    return all(v in (0, 0.0, None) for v in valores or ())


def evidencias_do_laudo(camada, fontes_conferidas):
    """Fatos medidos do laudo/1 que explicam uma regra que a sonda aplicava e o laudo nao aplica mais.

    - fonte_nao_conferida_com_tinta: a propria camada tem texto com tinta em fonte que o laudo nao conferiu
      (alerta fonte_nao_conferida), num laudo sem conferencia de faces instaladas (M1), entao a B3 nao pode
      disparar nela. Camada sem esse alerta (sem texto com tinta) nao tem a perda da B3 explicada;
    - malha_identidade: malha de deformacao com desvio ate laudo.tolerancia_malha_px, que nao deforma (D6);
    - warp_sem_efeito: warp com curvatura e perspectivas 0, que nao deforma (D6)."""
    from desdobra import limites
    ev = []
    if not fontes_conferidas and any(isinstance(a, dict) and a.get('codigo') == 'fonte_nao_conferida'
                                     for a in camada.get('alertas') or []):
        ev.append('fonte_nao_conferida_com_tinta')
    medidas = (camada.get('smart_object') or {}).get('medidas') or {}
    desvio = medidas.get('malha_desvio_max_px')
    if medidas.get('malha_custom') and desvio is not None and desvio <= limites.valor('laudo.tolerancia_malha_px'):
        ev.append('malha_identidade')
    warp = (camada.get('texto') or {}).get('warp') or {}
    estilo = medidas.get('warp_estilo') or warp.get('estilo')
    valores = medidas.get('warp_valores') if medidas.get('warp_estilo') else [warp.get(k) for k in
                                                                             ('valor', 'perspectiva', 'perspectiva_outra')]
    if estilo not in (None, 'warpNone', 'warpCustom') and _sem_efeito(valores):
        ev.append('warp_sem_efeito')
    return ev


def camada_do_laudo(camada, fontes_conferidas=False):
    conteudo, runs = texto_normalizado(camada.get('texto'))
    aparencia = camada.get('aparencia') or {}
    geometria = camada.get('geometria') or {}
    return {'situacao': camada.get('situacao'), 'tipo': camada.get('tipo'), 'caixa': caixa(geometria.get('caixa')),
            'visivel': aparencia.get('visivel_efetiva'), 'texto': conteudo, 'texto_runs': runs,
            'regras': sorted({m.get('regra') for m in camada.get('motivos') or [] if isinstance(m, dict)
                              and m.get('regra')}),
            'evidencias': evidencias_do_laudo(camada, fontes_conferidas)}


def prova_pixel_do_laudo(laudo):
    pp = laudo.get('prova_pixel') or {}
    pct = pp.get('pct_px_acima_qualquer_canal')
    feita = bool(pp.get('feita')) and pct is not None
    return {'feita': feita, 'pct': pct if feita else None, 'motivo': pp.get('motivo'),
            'px_acima': pp.get('px_acima_qualquer_canal') if feita else None,
            'px_total': pp.get('px_total') if feita else None}


def normalizar_laudo(laudo, execucao=None):
    """laudo/1 -> forma normalizada. `execucao` vem do executor ({'situacao', 'motivo', 'tempo_s'})."""
    execucao = dict(execucao or {})
    camadas = {}
    fontes_conferidas = any(f.get('situacao') not in (None, 'nao_conferida') for f in laudo.get('fontes_usadas') or [])
    for c in laudo.get('camadas') or []:
        lid = (c.get('identidade') or {}).get('layer_id')
        if isinstance(lid, int):
            camadas[lid] = camada_do_laudo(c, fontes_conferidas)
    return {'formato': 'laudo/1', 'psd_tools': (laudo.get('origem') or {}).get('psd_tools'), 'tem_laudo': True,
            'execucao': {'situacao': execucao.get('situacao', 'ok'), 'motivo': execucao.get('motivo')},
            'prova_pixel': prova_pixel_do_laudo(laudo),
            'tempo_s': {'interno': (laudo.get('recursos') or {}).get('tempo_s'), 'externo': execucao.get('tempo_s')},
            'camadas': camadas}


def normalizado_sem_laudo(execucao):
    """Forma normalizada de uma execucao que nao deixou laudo legivel."""
    return {'formato': 'laudo/1', 'psd_tools': None, 'tem_laudo': False,
            'execucao': {'situacao': execucao.get('situacao', 'sem_laudo'), 'motivo': execucao.get('motivo')},
            'prova_pixel': {'feita': False, 'pct': None, 'motivo': None},
            'tempo_s': {'interno': None, 'externo': execucao.get('tempo_s')}, 'camadas': {}}


def normalizar(laudo, execucao=None):
    """Reconhece o formato pelo campo esquema: laudo/1 tem esquema; a sonda, nao."""
    if isinstance(laudo, dict) and laudo.get('esquema') == 'laudo/1':
        return normalizar_laudo(laudo, execucao)
    return normalizar_sonda(laudo)
