# -*- coding: utf-8 -*-
"""Laudo do PSD (laudo/1): funcao pura da estrutura bruta (estrutura/1) lida pelo processo filho.

Diz camada por camada o que foi lido e com que perda (arquitetura-v1.md, 4.4 e 5.2):
  - identidade (sha256 do arquivo, layer_id), tipo, aparencia, geometria, texto por trecho, smart object;
  - situacao lida, degradada ou bloqueante, com regra, medida, limite citado e fonte (desdobra.laudo.regras);
  - "coberta no KV" (decisoes-v1.md, 29/10, 10): fracao coberta, marca "ocupa o canvas" e a funcao que a
    regra da decisao da, so como sugestao citada. O campo de funcao do briefing fica para o DA;
  - quadros e variantes ocultas como entidades (desdobra.laudo.quadros);
  - prova de pixel com o limiar citado do registro;
  - quem gravou o arquivo e os casos de smart object que a pesquisa achou, como alertas.

Nao le PSD nem disco: recebe dicionarios e devolve um dicionario. Quem grava e valida e desdobra.leitor.
"""
import collections
from fractions import Fraction

from desdobra import limites
from desdobra.laudo import efeitos_1260, quadros as mod_quadros, regras

FONTE_DECISAO_10 = {'arquivo': 'decisoes-v1.md', 'secao': '29/10, respostas ao teste do corpus, 10'}
FONTE_SMART = {'arquivo': 'pesquisa/corpus-testes.md', 'secao': '4, item 4'}
FONTE_FONTES = {'arquivo': 'pesquisa/corpus-testes.md', 'secao': '4, itens 6 e 8'}
FONTE_PROFUNDIDADE = {'arquivo': 'pesquisa/render-local-pesquisa.md', 'secao': '2'}
MOTIVO_PROFUNDIDADE = 'profundidade máxima'  # o mesmo texto que desdobra.leitor grava em aninhadas
# motivo da prova de pixel nao feita -> tipo do bloqueio de composicao no laudo
MOTIVOS_COMPOSICAO_ESTOURADA = {'orcamento': 'memoria', 'tempo': 'tempo'}

TIPOS = {'type': 'texto', 'shape': 'forma', 'pixel': 'pixel', 'solidcolorfill': 'cor_solida',
         'gradientfill': 'preenchimento', 'patternfill': 'preenchimento', 'group': 'grupo', 'artboard': 'prancheta'}


def tipo_da_camada(reg):
    k = reg.get('kind')
    if k == 'smartobject':
        so = reg.get('smart_object') or {}
        return 'smart_embutido' if so.get('embutido') else 'smart_linkado'
    if reg.get('ajuste'):
        return 'ajuste'
    return TIPOS.get(k, 'outro')


def _atinge(parte, todo, fracao_medida, limite):
    """parte/todo >= limite, com as contagens inteiras quando existem (sem arredondamento escondido); sem elas,
    com a fracao gravada. O limite entra como a fracao decimal escrita no registro (0,07 vale exatamente 7/100),
    e a conta e exata."""
    if isinstance(parte, int) and isinstance(todo, int) and todo > 0:
        return Fraction(parte, todo) >= Fraction(str(limite))
    return fracao_medida is not None and fracao_medida >= limite


def _coberta(reg, lim_cob, lim_ocupa):
    px = reg.get('pixels') or {}
    fc, fcan = px.get('fracao_coberta'), px.get('fracao_canvas')
    if fc is None:
        return None
    coberta = bool(reg.get('visivel_efetiva')) and _atinge(px.get('px_cobertos'), px.get('px_visiveis'), fc,
                                                          lim_cob.valor)
    ocupa = _atinge(px.get('px_visiveis'), px.get('px_area_ref'), fcan, lim_ocupa.valor)
    sugestao = None
    if coberta:
        sugestao = {'funcao': 'estrutura' if ocupa else 'fora_da_peca', 'regra': 'decisao-10', 'fonte': FONTE_DECISAO_10}
    return {'coberta': coberta, 'fracao_coberta': fc, 'ocupa_canvas': ocupa, 'fracao_canvas': fcan,
            'sugestao_da_regra': sugestao, 'limites': [lim_cob.citacao(), lim_ocupa.citacao()]}


def _fontes_nao_conferidas(reg, fontes_status):
    """Fontes de trechos com tinta que o laudo nao conferiu (no M1, todas: a conferencia das faces entra no M2)."""
    tx = reg.get('texto') or {}
    return sorted({r['fonte_ps'] for r in tx.get('runs') or [] if r.get('tem_tinta') and r.get('fonte_ps')
                   and (fontes_status or {}).get(r['fonte_ps']) not in ('presente', 'ausente')})


def _alertas(reg, aninhadas, fontes_status=None):
    out = [{'codigo': 'leitura', 'descricao': a} for a in reg.get('alertas') or []]
    nao_conferidas = _fontes_nao_conferidas(reg, fontes_status)
    if nao_conferidas:
        # "lida" nao quer dizer que a fonte foi conferida: sem a conferencia, a B3 nao tem como disparar
        out.append({'codigo': 'fonte_nao_conferida', 'fonte': FONTE_FONTES,
                    'descricao': 'Texto com tinta em fonte que o laudo não conferiu nas faces instaladas. A conferência '
                                 'entra no M2; até lá, uma fonte ausente não aparece como bloqueante.',
                    'medida': {'n_fontes': len(nao_conferidas)}})
    so = reg.get('smart_object')
    if not so:
        return out
    dims = so.get('dims') or {}
    if so.get('tipo_detectado') == 'pdf' and dims.get('n_imagens_raster'):
        q = so.get('quad_colocado') or {}
        out.append({'codigo': 'pdf_com_imagem_raster', 'fonte': FONTE_SMART,
                    'descricao': 'PDF dito vetorial com imagem raster dentro: conferir a resolução efetiva antes de ampliar.',
                    'medida': {'maior_imagem_px': dims.get('maior_imagem_px'), 'n_imagens_raster': dims['n_imagens_raster'],
                               'colocado_px': [q.get('largura'), q.get('altura')] if q else None}})
    if so.get('tipo_detectado') == 'pdf' and any(e.get('ativo') and e.get('tipo') == 'ColorOverlay' for e in reg.get('efeitos') or []):
        out.append({'codigo': 'pdf_perde_color_overlay', 'fonte': FONTE_SMART,
                    'descricao': 'Re-rasterizar este PDF perde o ColorOverlay da camada.'})
    ab = aninhadas.get(so.get('sha256')) if so.get('sha256') else None
    est = (ab or {}).get('estrutura')
    if ab and est is None and ab.get('recusa') is None and ab.get('motivo') == MOTIVO_PROFUNDIDADE:
        out.append({'codigo': 'smart_object_nao_aberto', 'fonte': FONTE_PROFUNDIDADE,
                    'descricao': 'Smart object embutido mais fundo que a profundidade máxima de leitura: o conteúdo '
                                 'dele não foi lido nem conferido.',
                    'medida': {'profundidade_max': limites.valor('leitor.profundidade_max_smart')}})
    if est:
        tem_texto = any(c.get('kind') == 'type' and c.get('visivel_efetiva') for c in est.get('camadas') or [])
        if est['documento'].get('previa_uniforme') and tem_texto:
            out.append({'codigo': 'composto_uniforme_com_texto', 'fonte': FONTE_SMART,
                        'descricao': 'PSB ou PSD embutido com o composto gravado de uma cor só e camadas de texto visíveis: '
                                     'o composto pode esconder fonte ausente.'})
        elif not est['documento'].get('tem_previa') and tem_texto:
            # sem "maximizar compatibilidade", o Photoshop grava um composto em branco (VERSION_INFO.has_composite
            # falso): e o caso dos cartoes da pesquisa, em que a fonte ausente fica escondida
            out.append({'codigo': 'composto_ausente_com_texto', 'fonte': FONTE_SMART,
                        'descricao': 'PSB ou PSD embutido salvo sem composto real (o arquivo diz que o composto '
                                     'gravado não vale) e com camadas de texto visíveis: o composto em branco pode '
                                     'esconder fonte ausente. O motor não compõe este objeto.'})
    return out


def _abertura(so, aninhadas):
    if not so or not so.get('embutido'):
        return None
    if so.get('tipo_detectado') not in ('psd', 'psb'):
        return {'situacao': 'nao_aberto', 'motivo': 'não é PSD nem PSB'}
    ab = aninhadas.get(so.get('sha256'))
    if ab is None:
        return {'situacao': 'nao_aberto', 'motivo': 'fora da profundidade máxima ou não pedido'}
    est, rec = ab.get('estrutura'), ab.get('recusa')
    if est is None and rec is None:
        return {'situacao': 'nao_aberto', 'motivo': ab.get('motivo') or 'não aberto'}
    if est:
        textos = [c for c in est.get('camadas') or [] if c.get('kind') == 'type']
        return {'situacao': 'aberto', 'profundidade': est['origem']['profundidade'], 'pasta': ab.get('pasta'),
                'resumo': {'n_camadas': len(est.get('camadas') or []), 'n_textos': len(textos),
                           'fontes_ps': sorted({f for c in textos for f in (c.get('texto') or {}).get('fontes_ps', [])}),
                           'dims': [est['documento']['largura'], est['documento']['altura']],
                           'previa_uniforme': est['documento'].get('previa_uniforme'),
                           'smart_objects': len(est.get('indice_smart') or [])}}
    return {'situacao': 'recusado', 'recusa': rec, 'motivo': ab.get('motivo')}


def _camada(reg, sha, contexto):
    mot = regras.avaliar(reg, contexto['pacotes'], contexto.get('fontes_status'))
    efs = [{'tipo': e['tipo'], 'ativo': bool(e.get('ativo')), 'suportado_pelo_render': bool(e.get('desenhado_pelo_render')),
            'requer_pacote_ausente': e.get('requer_pacote_ausente')} for e in reg.get('efeitos') or []]
    so = reg.get('smart_object')
    so_laudo = None
    if so is not None:
        so_laudo = {k: so.get(k) for k in ('tipo', 'embutido', 'unique_id', 'filetype', 'tipo_detectado', 'nome', 'bytes',
                                            'sha256', 'dims', 'transformacao', 'quad_colocado', 'escala_sobre_original',
                                            'resolucao_colocada', 'filtros_inteligentes', 'medidas')}
        if not so.get('embutido'):
            so_laudo = {'tipo': so.get('tipo'), 'embutido': False, 'unique_id': so.get('unique_id'),
                        'registro': so.get('linkado') or {'nome': so.get('nome'), 'tamanho': so.get('bytes'), 'data': None},
                        'casamento': contexto['casamentos'].get(so.get('unique_id'),
                                                               {'situacao': 'sem_candidato', 'candidatos': []})}
        else:
            so_laudo['abertura'] = _abertura(so, contexto['aninhadas'])
    return {
        'identidade': {'arquivo_sha256': sha, 'layer_id': reg['layer_id']},
        'nome': reg.get('nome', ''), 'tipo': tipo_da_camada(reg), 'pai_id': reg.get('pai_id'),
        'caminho_ids': reg.get('caminho_ids') or [], 'quadro': mod_quadros.quadro_da_camada(reg, contexto['quadros']),
        'aparencia': {'visivel_efetiva': bool(reg.get('visivel_efetiva')), 'visivel_propria': bool(reg.get('visivel_propria')),
                      'opacidade': reg.get('opacidade', 0), 'preenchimento': reg.get('preenchimento', 0),
                      'blend': reg.get('blend', ''), 'clipping': bool(reg.get('clipping')), 'mascara': reg.get('mascara'),
                      'efeitos': efs, 'ajuste': reg.get('ajuste')},
        'geometria': {'caixa': reg.get('caixa') or [0, 0, 0, 0], 'caixa_tinta': reg.get('caixa_tinta'),
                      'coberta_no_kv': _coberta(reg, contexto['lim_cob'], contexto['lim_ocupa'])},
        'texto': reg.get('texto'), 'smart_object': so_laudo,
        'situacao': regras.situacao(mot), 'motivos': mot,
        'alertas': _alertas(reg, contexto['aninhadas'], contexto.get('fontes_status')),
    }


def _fontes_usadas(regs, fontes_status):
    usos = collections.OrderedDict()
    for r in regs:
        tx = r.get('texto')
        if not tx:
            continue
        for run in tx['runs']:
            ps = run.get('fonte_ps')
            if not ps:
                continue
            u = usos.setdefault(ps, {'camadas': [], 'com_tinta': False})
            if r['layer_id'] not in u['camadas']:
                u['camadas'].append(r['layer_id'])
            u['com_tinta'] = u['com_tinta'] or bool(run.get('tem_tinta'))
    out = []
    for ps, u in usos.items():
        sit = (fontes_status or {}).get(ps, 'nao_conferida')
        out.append({'fonte_ps': ps, 'camadas': u['camadas'], 'situacao': sit, 'so_em_espaco': not u['com_tinta']})
    return out


def _gravado_por(gp):
    gp = gp or {}
    v = gp.get('file_version')
    return {'programa': gp.get('writer'), 'versao': str(v) if v is not None else None}


def _vazio_documento():
    return {'largura': 1, 'altura': 1, 'modo': 'desconhecido', 'bits': 0, 'icc': None, 'pranchetas': [], 'layer_comps': [],
            'tem_previa': False, 'quadros': [], 'variantes_ocultas': []}


def montar(estrutura, *, origem, recursos, aninhadas=None, recusa=None, casamentos=None, fontes_status=None):
    """Monta o laudo/1.

    estrutura: estrutura/1 do documento, ou None quando o arquivo foi recusado inteiro;
    origem: {'arquivo', 'sha256', 'bytes'} do arquivo lido (o nome e dado de cliente);
    recursos: {'tempo_s', 'pico_bytes', 'orcamento_bytes', 'filhos'};
    aninhadas: {sha256 do embutido: {'estrutura' | 'recusa', 'pasta', 'motivo'}};
    recusa: lista de recusas (tipo, etapa, motivo, layer_id, medidas) que entram no laudo;
    casamentos: {unique_id do linkado: proposta de casamento com arquivo da pasta do job};
    fontes_status: {fonte_ps: 'presente' | 'ausente'} quando houver conferencia de faces (M2)."""
    aninhadas = aninhadas or {}
    limiar = limites.obter('prova_pixel.limiar_diferenca')
    laudo = {'esquema': 'laudo/1',
             'origem': {'arquivo': origem['arquivo'], 'sha256': origem['sha256'], 'bytes': origem['bytes'],
                        'gravado_por': {'programa': None, 'versao': None}, 'psd_tools': '', 'motor': ''},
             'documento': _vazio_documento(), 'camadas': [], 'fontes_usadas': [],
             'prova_pixel': {'feita': False, 'motivo': 'recusado', 'limiar': limiar.citacao()},
             'regras': {k: dict(v) for k, v in regras.REGRAS.items()}, 'recusas': list(recusa or []),
             'recursos': dict(recursos), 'efeitos_suportados': efeitos_1260.descricao(),
             'resumo': {}}
    if estrutura is None:
        laudo['resumo'] = _resumo([], [], laudo['recusas'])
        return laudo
    doc = estrutura['documento']
    laudo['origem'].update({'gravado_por': _gravado_por(doc.get('gravado_por')),
                            'psd_tools': estrutura['leitor']['psd_tools'], 'motor': estrutura['leitor']['motor']})
    qd = mod_quadros.detectar(estrutura)
    icc = doc.get('icc') or {}
    laudo['documento'] = {
        'largura': doc['largura'], 'altura': doc['altura'], 'formato': doc.get('formato'), 'modo': doc['modo'],
        'bits': doc['bits'],
        'icc': {'nome': icc.get('descricao'), 'sha256': icc['sha256']} if icc.get('presente') and icc.get('sha256') else None,
        'pranchetas': doc.get('pranchetas') or [], 'layer_comps': doc.get('layer_comps') or [],
        'tem_previa': bool(doc.get('tem_previa')), 'quadros': qd,
        'variantes_ocultas': mod_quadros.variantes_ocultas(estrutura, qd)}
    contexto = {'pacotes': estrutura['leitor'].get('pacotes') or {}, 'fontes_status': fontes_status,
                'quadros': qd, 'aninhadas': aninhadas, 'casamentos': casamentos or {},
                'lim_cob': limites.obter('coberta_no_kv.fracao_coberta_min'),
                'lim_ocupa': limites.obter('coberta_no_kv.ocupa_canvas_fracao')}
    sha = estrutura['origem']['sha256']
    laudo['camadas'] = [_camada(r, sha, contexto) for r in estrutura['camadas']]
    laudo['fontes_usadas'] = _fontes_usadas(estrutura['camadas'], fontes_status)
    pp = estrutura.get('prova_pixel') or {}
    prova = {'feita': bool(pp.get('feita')), 'motivo': pp.get('motivo'), 'limiar': limiar.citacao()}
    for k in ('pct_px_acima_qualquer_canal', 'px_acima_qualquer_canal', 'px_total', 'por_canal', 'regioes',
              'por_camada'):
        if k in pp:
            prova[k] = pp[k]
    if 'regioes_meta' in pp:
        prova['por_canal'] = dict(prova.get('por_canal') or {}, alfa=pp.get('alfa'))
        prova['regioes'] = [dict(r) for r in pp.get('regioes') or []]
    laudo['prova_pixel'] = prova
    if prova['motivo'] in MOTIVOS_COMPOSICAO_ESTOURADA:
        # a leitura vale, mas a composicao do documento passou do orcamento: bloqueio tipado do documento inteiro,
        # que pede decisao do DA (arquitetura-v1.md, 9.2), sem derrubar o processo principal
        laudo['recusas'].append({'tipo': MOTIVOS_COMPOSICAO_ESTOURADA[prova['motivo']], 'etapa': 'composicao',
                                 'layer_id': None,
                                 'motivo': 'A composição do documento passou do orçamento; a prova de pixel não foi '
                                           'feita e a peça precisa de decisão do DA antes do render.',
                                 'medidas': {'orcamento_bytes': recursos.get('orcamento_bytes')}})
    laudo['resumo'] = _resumo(laudo['camadas'], qd, laudo['recusas'])
    return laudo


def _resumo(camadas, qd, recusas):
    st = collections.Counter(c['situacao'] for c in camadas)
    stv = collections.Counter(c['situacao'] for c in camadas if c['aparencia']['visivel_efetiva'])
    regra = collections.Counter(m['regra'] for c in camadas for m in c['motivos'])
    sit = ('lida', 'degradada', 'bloqueante')
    return {'n_camadas': len(camadas), 'por_situacao': {s: st.get(s, 0) for s in sit},
            'por_situacao_visiveis': {s: stv.get(s, 0) for s in sit}, 'por_regra': dict(sorted(regra.items())),
            'n_quadros': len(qd),
            'n_cobertas_no_kv': sum(1 for c in camadas if (c['geometria'].get('coberta_no_kv') or {}).get('coberta')),
            # bloqueio do documento inteiro (sem layer_id): arquivo recusado ou composicao acima do orcamento
            'bloqueios_documento': sum(1 for r in recusas or [] if r.get('layer_id') is None),
            'n_fonte_nao_conferida': sum(1 for c in camadas if any(a['codigo'] == 'fonte_nao_conferida'
                                                                   for a in c.get('alertas') or []))}
