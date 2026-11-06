# -*- coding: utf-8 -*-
"""Validacoes de layout de um formato derivado (arquitetura-v1.md, 9.6), sobre as caixas finais.

  - enquadramento: o elemento que nao sangra na mestre fica dentro do canvas; o lado que sangra continua com o
    corte fora do canvas;
  - area util e faixa: o elemento que nao sangra fica dentro da area util (fora das faixas reservadas); texto e marca
    ficam dentro da area segura, quando a folha da uma;
  - colisao nova contra a origem: caixas que nao se tocam na mestre do KV continuam sem se tocar;
  - inventario: o formato tem os mesmos elementos da mestre (a conferencia entre formatos fica em nucleo);
  - regra por funcao: a funcao e a regra de cada elemento sao relidas do briefing (a funcao resolvida) e
    comparadas com as do layout; o residuo da escala contra a regra so e registrado;
  - folga de resolucao: ampliacao acima da folga do raster avisa;
  - membro do bloco: o que estava inteiro no canvas da mestre (e o texto e a marca) continua inteiro, dentro da area
    util e, texto e marca, da area segura (revisao 2 do M5, A3);
  - cena que passa a cobrir conteudo: cena opaca acima de texto, marca ou sujeito na pilha nao passa a cobrir mais
    que derivacao.cobertura_nova_cena_sobre_conteudo_max da caixa dele (revisao 2, M4);
  - corpo minimo do texto legal: abaixo de derivacao.corpo_minimo_legal_px avisa (revisao 2, B5).
A obrigatoria que reprova devolve o formato ao DA com o nome e a fonte.

Funcao pura das caixas.
"""
from desdobra import limites
from desdobra.derivacao import escala as mod_escala
from desdobra.derivacao.solver import CLASSES_AREA_SEGURA, FONTE_MESTRE, conteudo, par_que_nao_sobrepoe


def _area(c):
    return max(0.0, c[2] - c[0]) * max(0.0, c[3] - c[1])


def _inter(a, b):
    return _area([max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])])


def membros_no_formato(e, c):
    """[(raiz, classe, caixa no formato)] dos membros que tem de ficar inteiros, pela caixa do elemento no formato."""
    ckv = e.get('caixa_kv') or e.get('caixa')
    saida = []
    for m in e.get('membros_caixas') or []:
        k = (c[2] - c[0]) / (ckv[2] - ckv[0]) if ckv[2] > ckv[0] else 1.0
        mc = m['caixa']
        saida.append((m['raiz'], m['classe'], [c[0] + k * (mc[0] - ckv[0]), c[1] + k * (mc[1] - ckv[1]),
                                               c[0] + k * (mc[2] - ckv[0]), c[1] + k * (mc[3] - ckv[1])]))
    return saida


def _item(nome, situacao, fonte, elementos=(), **medidas):
    r = {'nome': nome, 'situacao': situacao, 'fonte': fonte, 'elementos': list(elementos)}
    if medidas:
        r['medidas'] = medidas
    return r


def _sobrepoe(a, b, tol):
    return min(a[2], b[2]) - max(a[0], b[0]) > tol and min(a[3], b[3]) - max(a[1], b[1]) > tol


def validar(formato, areas, elementos, caixas, escalas, kv_elementos, esperado, apagados=()):
    """Lista de validacoes. formato: (largura, altura) da composicao; areas: de formatos.areas; elementos: os do
    layout (com funcao, regra e classe aplicadas); caixas e escalas: do layout; kv_elementos: os da mestre do KV
    (caixa na mestre do KV), por id; esperado: {id do elemento: (funcao resolvida, regra do briefing)} relido do
    briefing; apagados: ids dos elementos que o DA tirou da familia no palco (decisoes-v1.md, 169): saem da conta do
    inventario, que os registra."""
    W, H = (float(v) for v in formato)
    tol = limites.valor('derivacao.enquadramento_tolerancia_px')
    tol_col = limites.valor('derivacao.colisao_tolerancia_px')
    tol_regra = limites.valor('derivacao.tolerancia_regra_escala')
    util = (areas.get('area_util') or {}).get('caixa')
    fonte_util = (areas.get('area_util') or {}).get('fonte')
    segura = areas.get('area_segura')
    saida = []
    for e, c, s in zip(elementos, caixas, escalas):
        sg = e['sangra']
        fora = []
        # a borda do asset no formato (alem da caixa visivel quando a camada passa da prancheta)
        cm = e.get('caixa')
        am = e.get('caixa_asset') or cm
        a = list(c) if cm is None else [c[0] + s * (am[0] - cm[0]), c[1] + s * (am[1] - cm[1]),
                                         c[2] + s * (am[2] - cm[2]), c[3] + s * (am[3] - cm[3])]
        for lado, dentro, corte in (('esq', c[0] >= -tol, a[0] <= tol), ('topo', c[1] >= -tol, a[1] <= tol),
                                    ('dir', c[2] <= W + tol, a[2] >= W - tol), ('base', c[3] <= H + tol, a[3] >= H - tol)):
            if (not sg[lado] and not dentro) or (sg[lado] and not corte):
                fora.append(lado)
        saida.append(_item('enquadramento', 'reprova' if fora else 'ok', FONTE_MESTRE, [e['id']], lados=fora))
        if util is not None:
            fora_u = [lado for lado, k, ok in (('esq', 0, c[0] >= util[0] - tol), ('topo', 1, c[1] >= util[1] - tol),
                                               ('dir', 2, c[2] <= util[2] + tol), ('base', 3, c[3] <= util[3] + tol))
                      if not sg[lado] and not ok]
            saida.append(_item('area_util_e_faixa', 'reprova' if fora_u else 'ok', fonte_util, [e['id']], lados=fora_u))
        if segura is not None and e['classe'] in CLASSES_AREA_SEGURA:
            sc = segura['caixa']
            fora_s = [lado for lado, ok in (('esq', c[0] >= sc[0] - tol), ('topo', c[1] >= sc[1] - tol),
                                            ('dir', c[2] <= sc[2] + tol), ('base', c[3] <= sc[3] + tol))
                      if not sg[lado] and not ok]
            saida.append(_item('area_segura', 'reprova' if fora_s else 'ok', segura['fonte'], [e['id']], lados=fora_s))
        if e.get('membros_caixas'):
            membros = membros_no_formato(e, c)
            for nome, caixa_lim, fonte_lim, so in (('membro_dentro_do_canvas', [0.0, 0.0, W, H], FONTE_MESTRE, None),
                                                   ('membro_dentro_da_area_util', util, fonte_util, None),
                                                   ('membro_dentro_da_area_segura', (segura or {}).get('caixa'),
                                                    (segura or {}).get('fonte'), CLASSES_AREA_SEGURA)):
                if caixa_lim is None:
                    continue
                fora_m = []
                for raiz, classe, mc in membros:
                    if so is not None and classe not in so:
                        continue
                    lados = [lado for lado, ok in (('esq', mc[0] >= caixa_lim[0] - tol), ('topo', mc[1] >= caixa_lim[1] - tol),
                                                   ('dir', mc[2] <= caixa_lim[2] + tol), ('base', mc[3] <= caixa_lim[3] + tol))
                             if not ok]
                    if lados:
                        fora_m.append({'membro': raiz, 'lados': lados})
                saida.append(_item(nome, 'reprova' if fora_m else 'ok', fonte_lim, [e['id']], membros=fora_m))
        esp = esperado.get(e['id'], (None, None))
        funcao, regra = esp[0], esp[1]
        mesma = funcao == e['funcao'] and regra == e['regra']
        medidas = {'funcao': funcao, 'regra': regra, 'funcao_do_layout': e['funcao'], 'regra_do_layout': e['regra'],
                   'classe': e['classe']}
        if len(esp) > 2:  # numero-neutro: o terceiro campo do esperado e o dos membros do bloco
            # bloco: a funcao de cada membro, relida do briefing, contra a do layout (decisoes-v1.md, 100)
            do_layout = e.get('membros_funcoes') or {}
            mesma = mesma and {int(k): v for k, v in do_layout.items()} == {int(k): v for k, v in esp[2].items()}
            medidas['funcoes_membros'] = sorted([int(k), v] for k, v in esp[2].items())
            medidas['funcoes_membros_do_layout'] = sorted([int(k), v] for k, v in do_layout.items())
        saida.append(_item('regra_por_funcao', 'ok' if mesma else 'reprova',
                           {'tipo': 'briefing', 'ref': 'função resolvida pela herança (arquitetura-v1.md, 5.3)'},
                           [e['id']], **medidas))
        if e.get('funcao') == 'texto_legal' and e.get('corpo_px'):
            corpo = float(e['corpo_px']) * s * float(e.get('escala_na_mestre') or 1.0)
            minimo = limites.valor('derivacao.corpo_minimo_legal_px')
            saida.append(_item('corpo_minimo_do_legal', 'avisa' if corpo < minimo else 'ok',
                               {'tipo': 'limite', 'ref': 'derivacao.corpo_minimo_legal_px'}, [e['id']],
                               corpo_px=round(corpo, 4), minimo_px=minimo))
        if e.get('escala_regra'):
            res = mod_escala.residuo(s, e['escala_regra'])
            saida.append(_item('residuo_da_regra', 'registra' if res > tol_regra else 'ok',
                               {'tipo': 'limite', 'ref': 'derivacao.tolerancia_regra_escala'}, [e['id']],
                               residuo=round(res, 6), escala=round(s, 6), escala_regra=round(e['escala_regra'], 6)))
            if res > limites.valor('derivacao.residuo_regra_aviso'):
                saida.append(_item('escala_longe_da_regra', 'avisa',
                                   {'tipo': 'limite', 'ref': 'derivacao.residuo_regra_aviso'}, [e['id']],
                                   residuo=round(res, 6)))
        folga = e.get('folga_resolucao')
        ampl = s * float(e.get('escala_na_mestre') or 1.0)
        if folga is not None and ampl > folga:
            saida.append(_item('folga_de_resolucao', 'avisa', {'tipo': 'limite', 'ref': 'ds.ampliacao_raster_max'},
                               [e['id']], ampliacao=round(ampl, 6), folga=round(folga, 6)))
    # colisao nova: pares de conteudo que nao se tocam na mestre do KV nao se tocam no formato (luz, veu e grafismo de
    # cena podem passar por cima do conteudo, como no KV; decisoes-v1.md, 96)
    por_id = {e['id']: (e, c) for e, c in zip(elementos, caixas)}
    ids = sorted(por_id)
    novas = []
    for k, a in enumerate(ids):
        for b in ids[k + 1:]:
            ka, kb = kv_elementos.get(a), kv_elementos.get(b)
            if not par_que_nao_sobrepoe(por_id[a][0], por_id[b][0]):
                continue
            if ka is None or kb is None or _sobrepoe(ka['caixa'], kb['caixa'], 0.0):
                continue
            if _sobrepoe(por_id[a][1], por_id[b][1], tol_col):
                novas.append([a, b])
    saida.append(_item('colisao_nova_contra_a_origem', 'reprova' if novas else 'ok', FONTE_MESTRE,
                       sorted({x for par in novas for x in par}), pares=novas))
    # cena opaca acima do conteudo na pilha que passa a cobri-lo (revisao 2 do M5, M4): a luz e o veu (mesclagem) podem
    # passar por cima, como no KV (decisoes-v1.md, 96); a cena normal acima do texto, nao
    lim_cob = limites.valor('derivacao.cobertura_nova_cena_sobre_conteudo_max')
    cobre = []
    for a in ids:
        ea, ca = por_id[a]
        ka = kv_elementos.get(a)
        if not (ea.get('opaco') and ea.get('z') and ka is not None) or conteudo(ea):
            continue
        for b in ids:
            eb, cb = por_id[b]
            kb = kv_elementos.get(b)
            if b == a or not conteudo(eb) or not eb.get('z') or kb is None or not ea['z'][0] > eb['z'][1]:
                continue
            area_f, area_k = _area(cb), _area(kb['caixa'])
            if area_f <= 0 or area_k <= 0:
                continue
            novo = _inter(ca, cb) / area_f - _inter(ka['caixa'], kb['caixa']) / area_k
            if novo > lim_cob:
                cobre.append([a, b])
    saida.append(_item('cena_cobre_conteudo', 'reprova' if cobre else 'ok',
                       {'tipo': 'limite', 'ref': 'derivacao.cobertura_nova_cena_sobre_conteudo_max'},
                       sorted({x for par in cobre for x in par}), pares=cobre))
    tirados = sorted(set(apagados) & set(kv_elementos))
    inv_kv, inv = sorted(set(kv_elementos) - set(tirados)), sorted(por_id)
    medidas_inv = {'faltando': sorted(set(inv_kv) - set(inv)), 'sobrando': sorted(set(inv) - set(inv_kv))}
    if tirados:
        medidas_inv['apagados_pelo_da'] = tirados
    saida.append(_item('inventario', 'ok' if inv == inv_kv else 'reprova', FONTE_MESTRE,
                       sorted(set(inv_kv) ^ set(inv)), **medidas_inv))
    return saida


def reprovadas(validacoes):
    return [v for v in validacoes if v['situacao'] == 'reprova']
