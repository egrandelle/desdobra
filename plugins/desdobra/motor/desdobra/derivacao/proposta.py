# -*- coding: utf-8 -*-
"""A proposta confirmada pelo DA na tela, por familia (M7a, fatia 5; decisoes-v1.md, 164, 166, 167, 168, 169 e 171).

O briefing confirmado por "Salvar e seguir" (desdobra.briefing.salvar) traz em composicoes cada familia da tela: os
formatos dela, a versao da galeria escolhida e as edicoes do DA no palco. A derivacao parte delas:
  - o formato que o motor devolve por troca de orientacao ou proporcao fora da faixa (MOTIVOS_DA_GALERIA) sai da
    versao da galeria escolhida para a familia (sem escolha, a primeira sem falha, como a tela mostra), com as edicoes
    do DA; o caminho e 'galeria' e o formato deixa de ser devolvido;
  - o formato que o motor deriva sozinho (transform ou solver) recebe as edicoes do DA por cima da proposta dele;
  - as edicoes vao a cada membro em proporcao ao formato dele, com a intencao de alinhamento (168), e o encaixe e
    refeito pelo solver do repositorio: a mesma conta da previa da tela (desdobra.tela.edicao.Editor), pelas mesmas
    funcoes daqui, para a derivacao gravada ser o que o DA viu;
  - cada elemento leva a origem da geometria (origem_geometria): 'da' (mexido, alinhado pela intencao ou com texto
    editado pelo DA), 'galeria' (a versao sem edicao), 'transformacao' (escala pura), 'regra' (solver);
  - o elemento apagado sai do formato e fica em apagados_pelo_da, com a origem de quem confirmou a familia; ele deixa
    de contar no inventario igual entre formatos;
  - o texto editado vale so na familia onde o DA mexeu (171) e vai em texto_editado, com as quebras dele (as linhas
    do DA e as que a medida do render da na largura da caixa, M7b, A7): nunca as quebras da proposta (quebras
    'do_texto_editado');
  - a validacao obrigatoria do motor continua valendo: o layout confirmado que reprova volta ao DA com o nome da
    validacao, como na derivacao sem tela.
A galeria e a mesma da tela (galeria_da_familia, com os formatos devolvidos da familia na ordem da tela). So le
arquivos do job pelo contexto da derivacao: nao abre PSD, fonte nem imagem.
"""
import copy

# os motivos da devolucao que a galeria resolve (decisoes-v1.md, 164): os outros (folha, dimensao, indeterminado,
# bloco partido) sao guardas do motor que a escolha do DA nao pula
MOTIVOS_DA_GALERIA = ('troca_forte_de_orientacao', 'troca_de_orientacao_quadrado', 'fora_da_faixa_de_familia')
ORIGEM_POR_CAMINHO = {'galeria': 'galeria', 'transform': 'transformacao', 'solver': 'regra', 'mestre_propria': 'da'}
ORIGEM_DA = 'da'
ORIGENS_DO_APAGADO = ('da', 'fixture_de_teste')
QUEBRAS_DO_TEXTO_EDITADO = 'do_texto_editado'
TEXTO_SOLVER = 'As restrições da folha e do KV não fecham nesta versão.'


def galeria_da_familia(ctx, kv, formatos, *, specs, arquivo_specs, params):
    """{id do formato: [(ordem, variante do motor)]} dos formatos devolvidos de uma familia (formatos: os do briefing,
    na ordem da tela). As variantes vem da galeria no primeiro formato; com mais de um, cada variante vai a todos pela
    estrutura que deixa o pior membro melhor (desdobra.derivacao.galeria.variante_para_grupo). Quando nenhuma estrutura
    serve a todos, cada membro fica com a variante de mesmo id dele. O membro sem nenhuma variante ganha a galeria dele
    sozinho. So previa, em memoria."""
    from desdobra.derivacao import galeria as mg
    kw = {'specs': specs, 'arquivo_specs': arquivo_specs, 'params': params}
    if not formatos:
        return {}
    por_id = {f['id']: f for f in formatos}
    fids = [f['id'] for f in formatos]
    por_formato = {fid: [] for fid in fids}
    proprias = {}

    def propria(fid, vid):
        if fid not in proprias:
            proprias[fid] = {x['id']: x for x in mg.variantes(ctx, kv, por_id[fid], **kw)}
        return proprias[fid].get(vid)
    for n, v in enumerate(mg.variantes(ctx, kv, por_id[fids[0]], **kw), 1):
        membros = {fids[0]: v}
        if len(fids) > 1:
            try:
                membros = mg.variante_para_grupo(ctx, kv, formatos, v['id'], **kw)['membros']
            except ValueError:  # nenhuma estrutura da variante serve a todos: cada um com a dele, de mesmo id
                for fid in fids[1:]:
                    mv = propria(fid, v['id'])
                    if mv is not None:
                        membros[fid] = mv
        for fid, mv in membros.items():
            por_formato[fid].append((n, mv))
    return {fid: por_formato[fid] or list(enumerate(mg.variantes(ctx, kv, por_id[fid], **kw), 1)) for fid in fids}


def partida(derivado, versoes, versao):
    """Os elementos de onde o membro parte: a proposta derivada (formato derivado), a versao escolhida, a primeira sem
    falha ou a primeira da galeria. versoes: {id da versao: variante do motor}. None sem nenhuma."""
    if (derivado or {}).get('situacao') == 'derivado':
        return derivado['elementos']
    versoes = versoes or {}
    if versao in versoes:
        return versoes[versao]['elementos']
    ordem = list(versoes.values())
    v = next((x for x in ordem if not x['falhas_obrigatorias']), ordem[0] if ordem else None)
    return v['elementos'] if v else None


def layout_do_membro(cf, elementos, edicoes, *, kv_por_id, conteudo, kv_caixas, kv_tamanho):
    """O layout de um membro da familia com as edicoes do DA: as edicoes em proporcao ao formato, a intencao de
    alinhamento entre os elementos de conteudo, o encaixe refeito pelo solver (so quando o DA mexeu ou apagou) e a
    conferencia contra a mestre verdadeira. cf: o contexto da galeria do formato (galeria.contexto_do_formato).
    Devolve {'caixas', 'sangra', 'apagados', 'textos', 'mexidos', 'alinhados', 'falha_solver', 'falhas', 'avisos',
    'reprovadas', 'elementos'}."""
    from desdobra.derivacao import galeria as mg
    from desdobra.tela import edicao
    W, H = cf['W'], cf['H']
    caixas = {e['id']: e['caixa'] for e in elementos}
    sangra = {e['id']: dict(e['transformacao']['sangra']) for e in elementos
              if e['transformacao'].get('sangra') != kv_por_id[e['id']]['sangra']}
    caixas, apagados, textos, mexidos = edicao.aplicar(caixas, edicoes, W, H)
    so_conteudo = {k: v for k, v in caixas.items() if k in conteudo}
    norm, alinhados = edicao.normalizar(so_conteudo, mexidos, W, H, kv_caixas, kv_tamanho)
    caixas.update(norm)
    for k in apagados:
        sangra.pop(k, None)
    falha = None
    if mexidos or apagados:
        caixas, falha = mg.reencaixar(cf, caixas, sangra, apagados)
    falhas, avisos, reprovadas = mg.conferir_edicao(cf, caixas, sangra, apagados)
    if falha:
        falhas.append({'codigo': 'solver_nao_fecha', 'texto': TEXTO_SOLVER, 'elementos': []})
    return {'caixas': caixas, 'sangra': sangra, 'apagados': apagados, 'textos': textos, 'mexidos': mexidos,
            'alinhados': alinhados, 'falha_solver': falha, 'falhas': falhas, 'avisos': avisos, 'reprovadas': reprovadas,
            'elementos': mg.elementos_do_layout(cf, caixas, sangra, apagados)}


def _origem_do_apagado(ctx, comp):
    conf = comp.get('confirmacao') or {}
    if conf.get('origem') in ORIGENS_DO_APAGADO:
        return conf['origem']
    o = ctx['briefing']['cabecalho']['origem']
    return o if o in ORIGENS_DO_APAGADO else ORIGEM_DA


def _derivacao(ctx, kv, cf, d, lay, caminho, proposta, origem_apagado):
    """A derivacao/1 do membro a partir do layout com as edicoes (layout_do_membro)."""
    from desdobra.derivacao import galeria as mg
    from desdobra.derivacao import nucleo as nd
    from desdobra.derivacao import validacao as mv
    novo = copy.deepcopy(d)
    kv_por_id = {e['id']: e for e in kv['elementos']}
    do_da = set(lay['mexidos']) | {a['elementos'][0] for a in lay['alinhados']} | set(lay['textos'])
    antes = {e['id']: e for e in d['elementos']} if d['situacao'] == 'derivado' else {}
    base = ORIGEM_POR_CAMINHO[caminho]
    refeito = bool(lay['mexidos'] or lay['apagados'])
    elementos = []
    for e in lay['elementos']:
        x = dict(e)
        o = antes.get(e['id'])
        if e['id'] in lay['textos']:
            # o texto editado leva so as quebras do DA, nunca as da proposta junto com as linhas dele (M7b, A7)
            x['quebras'] = QUEBRAS_DO_TEXTO_EDITADO
            x.pop('quebras_camada', None)
        elif o is not None:
            # as quebras aprovadas da familia ficam as da proposta derivada (o render as aplica)
            for k in ('quebras', 'quebras_camada'):
                if k in o:
                    x[k] = o[k]
        x['regra_aplicada'] = {'funcao': e['funcao'], 'regra': e['regra'], 'caminho': caminho, 'classe': e['classe']}
        if e['id'] in do_da:
            x['origem_geometria'] = ORIGEM_DA
        elif refeito and o is not None and [float(v) for v in o['caixa']] != [float(v) for v in e['caixa']]:
            # o encaixe refeito pelo solver depois da edicao do DA mudou esta caixa: nao e mais escala pura, e a regra
            # aplicada diz o caminho do solver
            x['origem_geometria'] = ORIGEM_POR_CAMINHO['solver']
            x['regra_aplicada']['caminho'] = 'solver'
        else:
            x['origem_geometria'] = base
        if e['id'] in lay['textos']:
            x['texto_editado'] = lay['textos'][e['id']]
        elementos.append(x)
    registros = list(d['registros'])
    if d['situacao'] == 'devolvido':
        registros.append({'codigo': 'proposta_da_galeria', 'medidas': {'motivo_da_devolucao': d['devolucao']['motivo']}})
        novo['mestre'] = {'id': kv['id'], 'tipo': 'kv', 'largura': kv['largura'], 'altura': kv['altura']}
        novo['restricoes'] = []
    else:
        registros.append({'codigo': 'editado_pelo_da', 'medidas': {'edicoes': proposta['edicoes']}})
    if lay['falhas']:
        registros.append({'codigo': 'proposta_com_falha',
                          'medidas': {'falhas': sorted({f['codigo'] for f in lay['falhas']})}})
    validacoes = mg.validacoes_do_layout(cf, lay['caixas'], lay['sangra'], lay['apagados'])
    novo.update(elementos=elementos, validacoes=validacoes, caminho=caminho, situacao='derivado', devolucao=None,
                registros=registros, proposta=dict(proposta),
                apagados_pelo_da=[{'elemento': k, 'layer_ids': list(kv_por_id[k]['layer_ids']), 'origem': origem_apagado}
                                  for k in lay['apagados']])
    ruins = mv.reprovadas(validacoes)
    if ruins:
        v = ruins[0]
        return nd._devolver(novo, nd._devolucao('validacao_obrigatoria_reprovou',
                                                restricao={'nome': v['nome'], 'forca': 'obrigatoria',
                                                           'fonte': v['fonte'], 'elementos': v['elementos'],
                                                           'medidas': v.get('medidas')},
                                                elementos=v['elementos'], validacoes=[x['nome'] for x in ruins]))
    return novo


def aplicar(ctx, kv, resultados, derivar_um, *, specs, arquivo_specs, params):
    """Aplica as composicoes do briefing (as familias confirmadas na tela) aos formatos de resultados ({id:
    derivacao/1}), no lugar. derivar_um(formato) deriva um membro da familia que nao esta em resultados (a derivacao
    de um formato so precisa dos outros devolvidos da familia para montar a galeria como a tela)."""
    from desdobra.derivacao import galeria as mg
    from desdobra.derivacao import nucleo as nd
    from desdobra.derivacao import solver as mod_solver
    comps = ctx['briefing'].get('composicoes') or []
    if not comps:
        return resultados
    kw = {'specs': specs, 'arquivo_specs': arquivo_specs, 'params': params}
    por_id = {f['id']: f for f in ctx['briefing']['formatos']}
    kv_por_id = {e['id']: e for e in kv['elementos']}
    extra = {'kv_por_id': kv_por_id, 'conteudo': [e['id'] for e in kv['elementos'] if mod_solver.conteudo(e)],
             'kv_caixas': {e['id']: [float(x) for x in e['caixa']] for e in kv['elementos']},
             'kv_tamanho': (float(kv['largura']), float(kv['altura']))}
    for comp in comps:
        alvo = [f for f in comp['formatos'] if f in resultados]
        if not alvo:
            continue
        dos = {}
        for f in comp['formatos']:
            if f in resultados:
                dos[f] = resultados[f]
            elif f in por_id:
                dos[f] = derivar_um(por_id[f])
        # a mesma galeria da tela: o formato com a medida por confirmar fica fora (desdobra.tela.estado.galerias)
        devolvidos = [f for f in comp['formatos'] if f in dos and dos[f]['situacao'] == 'devolvido' and
                      (dos[f].get('devolucao') or {}).get('motivo') not in nd.MOTIVOS_POR_CONFIRMAR]
        proposta = {'familia': comp['familia'], 'versao': comp['versao'], 'edicoes': len(comp['edicoes']),
                    'confirmada': bool(comp['confirmada']), 'confirmacao': comp.get('confirmacao')}
        try:
            galeria = galeria_da_familia(ctx, kv, [por_id[f] for f in devolvidos], **kw) if devolvidos else {}
        except Exception:  # noqa: BLE001 - a galeria que quebra deixa os formatos como o motor os deixou
            galeria = None
        for fid in alvo:
            d = dos[fid]
            if d['situacao'] == 'devolvido':
                if galeria is None or (d.get('devolucao') or {}).get('motivo') not in MOTIVOS_DA_GALERIA:
                    continue
                elementos = partida(None, {v['id']: v for _n, v in galeria.get(fid) or []}, comp['versao'])
                caminho = 'galeria'
                if elementos is None:
                    continue
            elif not comp['edicoes']:
                d['proposta'] = dict(proposta)
                continue
            else:
                elementos, caminho = d['elementos'], d['caminho']
            try:
                cf = mg.contexto_do_formato(ctx, kv, por_id[fid], **kw)
                lay = layout_do_membro(cf, elementos, comp['edicoes'], **extra)
                resultados[fid] = _derivacao(ctx, kv, cf, d, lay, caminho, proposta, _origem_do_apagado(ctx, comp))
            except Exception as e:  # noqa: BLE001 - o formato fica como o motor o deixou, com o registro
                d['registros'].append({'codigo': 'erro_na_proposta', 'medidas': {'erro': type(e).__name__}})
    return resultados
