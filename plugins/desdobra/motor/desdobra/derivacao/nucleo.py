# -*- coding: utf-8 -*-
"""Derivacao deterministica por familia (arquitetura-v1.md, 4.10 e 9.6).

A partir do briefing confirmado, cada formato do briefing vai para uma familia e segue um de tres caminhos, por
calculo:
  - mesma proporcao da mestre: transform de saida (so a escala da peca inteira muda), quando satisfaz as obrigatorias
    da folha; senao, o solver;
  - proporcao diferente dentro da familia: solver de restricoes (as forcas do Cassowary, em ordem estrita, pelo HiGHS);
  - restricao obrigatoria que nao fecha: o formato volta ao DA com o nome e a fonte da restricao.
O formato que e a propria mestre propria do DA sai das caixas que o DA desenhou. Troca de orientacao contra a mestre
nunca deriva sozinha: pede mestre propria. Camada "fora da peca" nao entra em formato nenhum; camada "indeterminado"
sem regra de escala escolhida devolve o formato ao DA.

Com as familias confirmadas pelo DA na tela (briefing composicoes, M7a), o formato devolvido por troca de orientacao ou
proporcao fora da faixa sai da versao da galeria que o DA escolheu, com as edicoes dele, e o derivado recebe as edicoes
por cima (desdobra.derivacao.proposta); cada elemento leva a origem da geometria.

Grava derivacao/<formato>.json (derivacao/1) e derivacao/devolucoes.json. So le arquivos do job: nao abre PSD, fonte
nem imagem.
"""
import math
from datetime import datetime
from pathlib import Path

from desdobra import __version__, arquivos, contratos, limites
from desdobra.briefing import modelo as mb
from desdobra.derivacao import elementos as mod_elementos
from desdobra.derivacao import escala as mod_escala
from desdobra.derivacao import formatos as mod_formatos
from desdobra.derivacao import quebras as mod_quebras
from desdobra.derivacao import solver as mod_solver
from desdobra.derivacao import validacao as mod_validacao

ESQUEMA = 'derivacao/1'
CASAS_PX = 4  # numero-neutro: casas decimais das caixas em px; tira o ruido de ponto flutuante
CASAS_ESCALA = 6  # numero-neutro: casas decimais das escalas
# origem da caixa de cada elemento, pelo caminho do formato (a galeria e as edicoes do DA: desdobra.derivacao.proposta)
ORIGEM_GEOMETRIA = {'transform': 'transformacao', 'solver': 'regra', 'mestre_propria': 'da'}
ESQUEMA_DEVOLUCOES = 'devolucoes/1'
# o formato da folha com um valor que a derivacao le (formatos.CAMPOS_DO_LAYOUT) a espera da confirmacao do DA
# (revisao dos becos, A1): sem galeria nem proposta
MOTIVO_SPEC_POR_CONFIRMAR = 'spec_por_confirmar'
# o formato que deriva de uma mestre propria cujo formato tem valor de spec a espera do DA (revisao dos becos, D3): a
# base da mestre sairia do valor sem confirmacao, e o formato espera com ela, sem galeria nem proposta
MOTIVO_MESTRE_POR_CONFIRMAR = 'mestre_por_confirmar'
MOTIVOS_POR_CONFIRMAR = (MOTIVO_SPEC_POR_CONFIRMAR, MOTIVO_MESTRE_POR_CONFIRMAR)
PASTA = Path('derivacao')
ARQUIVO_DEVOLUCOES = PASTA / 'devolucoes.json'
FASES_DA_DERIVACAO = ('ler', 'fontes', 'laudo-fontes', 'ds', 'specs')
O_QUE_FAZER = {
    'troca_forte_de_orientacao': 'A orientação do formato é a oposta à da mestre. Troca forte de orientação não deriva '
                                 'sozinha: desenhe uma mestre própria para este formato no briefing.',
    'troca_de_orientacao_quadrado': 'O formato é quadrado e a mestre não (ou o contrário). Desenhe uma mestre própria '
                                    'para este formato no briefing.',
    'fora_da_faixa_de_familia': 'A proporção do formato fica fora da faixa de família de todas as mestres. Desenhe uma '
                                'mestre própria para este formato ou revise a faixa da família.',
    'acima_do_numero_de_mestres': 'O job já tem o número de mestres do parâmetro do job. Revise o parâmetro ou junte os '
                                  'formatos numa família.',
    'restricao_obrigatoria_nao_fecha': 'Uma restrição obrigatória não fecha neste formato. Veja o nome e a fonte da '
                                       'restrição e ajuste a mestre ou o formato.',
    'validacao_obrigatoria_reprovou': 'O layout derivado reprovou numa validação obrigatória. Veja o nome e a fonte e '
                                      'ajuste a mestre ou desenhe uma mestre própria.',
    'indeterminado_sem_regra': 'Há camada "indeterminado" sem regra de escala escolhida pelo DA. Escolha a regra dela no '
                               'briefing (regras_indeterminado).',
    'mestre_propria_incompleta': 'A mestre própria não traz caixa para todos os elementos da mestre do KV.',
    'formato_sem_folha': 'O formato não tem folha de spec no job (a chave não está nas specs). Confira a chave ou '
                         'acrescente a folha; um formato só de medição é marcado sem_folha no briefing.',
    'spec_por_confirmar': 'Um valor de spec deste formato (a medida, a faixa, a área útil ou a área segura) ainda '
                          'espera a sua confirmação. Confirme os valores dele em Valores de spec, no passo 1, e o '
                          'desdobra monta a peça com os valores confirmados.',
    'mestre_por_confirmar': 'O formato da mestre desta família ainda espera a confirmação de um valor de spec (a '
                            'medida, a faixa, a área útil ou a área segura). Confirme os valores dele em Valores de '
                            'spec, no passo 1, e o desdobra monta as peças da família com os valores confirmados.',
    'dimensao_diferente_da_folha': 'A largura e a altura do formato no briefing não são as da folha de spec da chave.',
    'ajuste_global_sem_aplicar': 'Há ajuste global que atua também sobre conteúdo (texto, marca ou sujeito) embaixo dele. '
                                 'O render ainda não aplica ajuste ao formato inteiro; prepare o PSD (decisão 99).',
    'bloco_partido_na_pilha': 'Na pilha do KV, outro elemento (ou um texto, ou um linkado) fica entre um efeito do bloco '
                              '(ajuste, mesclagem ou camada clipada) e o que o efeito pega: o render não compõe o bloco '
                              'numa pilha só sem levar o elemento do meio. Prepare o PSD (junte a cena num smart object '
                              'ou num grupo) ou reveja as funções.',
    'bloco_com_regras_diferentes': 'Um bloco rígido tem membros com regras de escala diferentes e o briefing não dá a '
                                   'regra do bloco (decisão 100).',
    'quebra_sem_medida': 'Há quebra aprovada para a família deste formato, e a largura das linhas juntadas não foi '
                         'medida (a medida roda no Chromium com a fonte do job). Rode o "desdobra derivar" de novo ou '
                         'confira o doctor.',
    'erro_no_formato': 'A derivação deste formato parou com um erro do motor; os outros formatos seguiram. Mande o '
                       'derivacao/<formato>.json para a Trezion.',
}


class ErroDerivacao(Exception):
    def __init__(self, mensagem, motivo, medidas=None):
        super().__init__(mensagem)
        self.motivo, self.medidas = motivo, medidas or {}


def agora():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def _devolucao(motivo, restricao=None, elementos=(), **medidas):
    d = {'motivo': motivo, 'o_que_fazer': O_QUE_FAZER[motivo], 'restricao': restricao, 'elementos': list(elementos)}
    if medidas:
        d['medidas'] = medidas
    return d


def _portao_fontes(pasta):
    """Situacao do portao de fontes para o texto do formato: passa, decisao_do_da (divergencia de largura) ou
    bloqueado. A derivacao segue; quem para e o render."""
    arq = Path(pasta) / mb.ARQUIVO_CONFERENCIA
    if not arq.is_file():
        return 'nao_conferido'
    conf = arquivos.ler_json(arq)
    codigos = {m['codigo'] for c in conf.get('camadas') or [] for m in c.get('motivos') or []
               if m.get('situacao') == 'bloqueante'}
    if codigos - {'largura_divergente'}:
        return 'bloqueado'
    return 'decisao_do_da' if codigos else 'passa'


def preparar(pasta, partida=False):
    """Le e confere o que a derivacao precisa. Devolve o contexto, ou ErroDerivacao.
    partida: so para a tela (desdobra.tela.estado.montar). No job sem briefing confirmado (ou com o rascunho do motor
    no lugar dele), o contexto sai do briefing de partida em memoria (briefing.modelo.partida), sem conferencia: a tela
    mostra o que falta, e a derivacao gravada (derivar) continua pedindo o briefing confirmado. Com o briefing gravado
    de outra versao dos arquivos do job, o contexto sai da retomada (briefing.modelo.retomada)."""
    from desdobra.job import fases as mod_fases
    from desdobra.job import nucleo
    pasta = Path(pasta).resolve()
    estado = contratos.ler(pasta / 'estado.json', 'estado/1')
    if nucleo.conferir_entradas(pasta, estado):
        raise ErroDerivacao('Uma entrada congelada do job mudou fora do motor.', 'entrada_alterada_fora_do_motor')
    avaliacao, _d = nucleo.avaliar(pasta, estado, mod_fases.ESTEIRA)
    invalidas = sorted(f for f in FASES_DA_DERIVACAO if f in avaliacao and not avaliacao[f][0])
    if invalidas:
        raise ErroDerivacao('Fases desatualizadas: %s.' % ', '.join(invalidas), 'fases_desatualizadas',
                            {'fases': invalidas})
    try:
        briefing = mb.ler(pasta)
    except contratos.ErroContrato as e:
        raise ErroDerivacao('O briefing não segue o contrato: %s' % e, 'briefing_invalido') from None
    if partida and (briefing is None or briefing['cabecalho']['origem'] == mb.ORIGEM_RASCUNHO or
                    mb.desatualizado(pasta, briefing)):
        # o gravado de outra versao dos arquivos do job: a tela parte da retomada (mb.base_da_tela), com o aviso do que
        # mudou, e nunca do gravado velho (revisao do M7a)
        laudo = contratos.ler(pasta / mb.ARQUIVO_LAUDO, 'laudo/1')
        ds_arq = pasta / mb.ARQUIVO_DS
        return contexto(laudo, mb.base_da_tela(pasta), ds=arquivos.ler_json(ds_arq) if ds_arq.is_file() else None,
                        job_id=estado['job_id'], pasta=pasta, portao_fontes=_portao_fontes(pasta), da_tela=True)
    if briefing is None:
        raise ErroDerivacao('O job não tem briefing.', 'sem_briefing')
    if briefing['cabecalho']['origem'] == mb.ORIGEM_RASCUNHO:
        raise ErroDerivacao('O briefing gravado é um rascunho, sem as decisões do DA.', 'briefing_rascunho')
    velhos = mb.desatualizado(pasta, briefing)
    if velhos:
        raise ErroDerivacao('O briefing é de outra versão do laudo, das specs, do design system ou das fontes.',
                            'briefing_desatualizado', {'campos': velhos})
    laudo = contratos.ler(pasta / mb.ARQUIVO_LAUDO, 'laudo/1')
    erros = mb.conferir(laudo, briefing, estado['job_id'])
    if erros:
        raise ErroDerivacao('O briefing tem problema: %s.' % ', '.join(sorted({e['codigo'] for e in erros})),
                            'briefing_com_problema', {'erros': erros})
    ds_arq = pasta / mb.ARQUIVO_DS
    ds = arquivos.ler_json(ds_arq) if ds_arq.is_file() else None
    medidas = None
    if mod_quebras.entradas_validas(briefing):
        from desdobra.derivacao import medida_quebras
        medidas = medida_quebras.medir(pasta, laudo, briefing, estado)
    return contexto(laudo, briefing, ds=ds, job_id=estado['job_id'], pasta=pasta,
                    briefing_sha256=arquivos.sha256_arquivo(pasta / mb.ARQUIVO), portao_fontes=_portao_fontes(pasta),
                    medidas_quebras=medidas, da_tela=partida)


def mestre_do_kv(ctx):
    """Elementos da mestre do KV com a regra, a ancora e a escala na mestre (1)."""
    b = ctx['briefing']
    m = mod_elementos.montar(ctx['laudo'], ctx['resolvidas'], ctx['info']['quadro'], ctx['ds'])
    regras_ind = mb.regras_indeterminado(b)
    sem_regra, regras_diferentes = [], []
    for e in m['elementos']:
        if e['funcao'] == mb.FUNCAO_INDETERMINADO and not e.get('bloco'):
            e['regra'] = regras_ind.get(e['raiz']) or next((regras_ind[x] for x in e['layer_ids'] if x in regras_ind), None)
            if e['regra'] is None:
                sem_regra.append(e['id'])
        else:
            # a regra do elemento, ou a do bloco (decisoes-v1.md, 100)
            e['regra'], _dos, conflito = mb.regra_do_elemento(b, e)
            if conflito:
                regras_diferentes.append(e['id'])
        e['ancora'] = mb.ancora_do_elemento(b, e['raiz'], e['funcao'])
        e['ancora_explicita'] = mb.ancora_explicita(b, e['raiz'])
        e['escala_na_mestre'] = 1.0
    m['indeterminado_sem_regra'] = sem_regra
    m['blocos_com_regras_diferentes'] = regras_diferentes
    m['id'], m['tipo'] = next(x['id'] for x in b['mestres'] if x['tipo'] == 'kv'), 'kv'
    return m


def _encaixar(caixa_mestre, alvo, ancora, cobrir=False):
    """Escala uniforme e caixa do elemento na caixa desenhada pelo DA, pela ancora: cabe na caixa (contain), ou cobre a
    caixa (cover) no elemento que sangra no KV, para o corte continuar fora."""
    w0, h0 = caixa_mestre[2] - caixa_mestre[0], caixa_mestre[3] - caixa_mestre[1]
    bw, bh = alvo[2] - alvo[0], alvo[3] - alvo[1]
    s = max(bw / w0, bh / h0) if cobrir else min(bw / w0, bh / h0)
    w, h = w0 * s, h0 * s
    ax, ay = ancora
    x = alvo[0] if ax == 'esquerda' else (alvo[2] - w if ax == 'direita' else (alvo[0] + alvo[2] - w) / 2.0)  # numero-neutro: centro
    y = alvo[1] if ay == 'topo' else (alvo[3] - h if ay == 'base' else (alvo[1] + alvo[3] - h) / 2.0)  # numero-neutro: centro
    return s, [x, y, x + w, y + h]


def mestre_propria(kv, mp, formato, camadas=None):
    """Mestre propria do DA: cada elemento da mestre do KV vai para a caixa que o DA desenhou. Devolve a mestre (com
    os elementos no espaco do formato, escala_na_mestre e caixa) e a lista dos elementos sem caixa."""
    por_raiz = {x['layer_id']: x for x in mp.get('elementos') or []}
    W, H = mod_formatos.composicao(formato)
    elementos, faltando = [], []
    for e in kv['elementos']:
        alvo = por_raiz.get(e['raiz'])
        if alvo is None:
            faltando.append(e['id'])
            continue
        s, caixa = _encaixar(e['caixa'], [float(v) for v in alvo['caixa']], e['ancora'], cobrir=any(e['sangra'].values()))
        # o lado que sangra no KV continua sangrando: o asset acaba na borda do canvas do KV, e o corte nunca aparece
        am, cm = e.get('caixa_asset') or e['caixa'], e['caixa']
        asset = [caixa[0] + s * (am[0] - cm[0]), caixa[1] + s * (am[1] - cm[1]), caixa[2] + s * (am[2] - cm[2]),
                 caixa[3] + s * (am[3] - cm[3])]
        novo = dict(e, caixa=caixa, caixa_asset=asset, escala_na_mestre=s, quebras=alvo.get('quebras'),
                    sangra=dict(e['sangra']))
        # a lista de posicoes que viram quebra e do texto do elemento (revisao 3: o render aplica); o conferir recusa
        # a lista num elemento com mais de um texto
        textos = [x for x in e['layer_ids'] if ((camadas or {}).get(x) or {}).get('tipo') == 'texto']
        if isinstance(alvo.get('quebras'), list) and len(textos) == 1:
            novo['quebras_camada'] = textos[0]
        elementos.append(novo)
    m = dict(kv, elementos=elementos, largura=float(W), altura=float(H), id=mp['id'], tipo='propria',
             formato=mp['formato'])
    return m, faltando


def _com_quebras(ctx, m, formato, W, H):
    """A mestre do KV com a caixa de cada texto que tem quebras aprovadas para a familia deste formato
    (decisoes-v1.md, 77, estendida na rodada 3; revisao 3): a caixa medida das linhas que ficam (derivacao.quebras e
    derivacao.medida_quebras), unida as outras camadas do elemento, sem corte no canvas da mestre (a linha juntada pode
    passar da mestre; o solver e a validacao veem a caixa inteira). Devolve (mestre, chaves sem medida). A mestre propria
    traz as quebras dela: as aprovadas por familia nao valem nela (registro)."""
    if not mod_quebras.entradas_validas(ctx['briefing']):
        return m, []
    cam = mb.camadas_do_laudo(ctx['laudo'])
    if m['tipo'] != 'kv':
        return m, []
    medidas = ctx.get('medidas_quebras') or {}
    novos, mudou, sem_medida = [], False, []
    for e in m['elementos']:
        textos = []
        for lid in e['layer_ids']:
            c = cam.get(lid) or {}
            if c.get('tipo') == 'texto' and mod_quebras.posicoes_de_quebra(c):
                manter = mod_quebras.aprovadas_para(ctx['briefing'], lid, formato, W, H)
                if manter is not None:
                    textos.append((lid, sorted(manter)))
        if not textos:
            novos.append(e)
            continue
        caixa, familia = None, []
        for lid, manter in textos:
            medida = medidas.get(mod_quebras.chave(lid, manter)) or {}
            if 'largura_texto' not in medida:
                sem_medida.append({'layer_id': lid, 'motivo': medida.get('erro') or 'sem_medida'})
                continue
            geo = cam[lid]['geometria']
            ct = mod_quebras.caixa_medida(cam[lid], geo.get('caixa_tinta') or geo['caixa'], manter, medida)
            ct = [_q(v, CASAS_PX) for v in ct]
            familia.append({'layer_id': lid, 'aprovadas': manter, 'caixa_doc': ct})
            caixa = ct if caixa is None else [min(caixa[0], ct[0]), min(caixa[1], ct[1]), max(caixa[2], ct[2]),
                                               max(caixa[3], ct[3])]
        if caixa is None:
            novos.append(e)
            continue
        com_quebra = {x['layer_id'] for x in familia}
        for outra in e['layer_ids']:
            g = (cam.get(outra) or {}).get('geometria') or {}
            if outra not in com_quebra and g.get('caixa_tinta') and cam[outra].get('tipo') != 'ajuste':
                ct = g['caixa_tinta']
                caixa = [min(caixa[0], ct[0]), min(caixa[1], ct[1]), max(caixa[2], ct[2]), max(caixa[3], ct[3])]
        ox, oy = m['canvas_doc'][0], m['canvas_doc'][1]
        local = [caixa[0] - ox, caixa[1] - oy, caixa[2] - ox, caixa[3] - oy]
        novos.append(dict(e, caixa_doc=list(caixa), caixa=local, caixa_kv=list(local), caixa_asset_doc=list(caixa),
                          caixa_asset=list(local), quebras={'familia': familia}))
        mudou = True
    return (dict(m, elementos=novos) if mudou else m), sem_medida


def _quebras_sem_aprovacao(ctx, m, aplicados, W, H):
    """Aviso (rodada 3): texto de mais de uma linha, sem quebra aprovada para a familia, num formato de proporcao muito
    diferente da mestre (derivacao.quebra_razao_aviso)."""
    lim = limites.valor('derivacao.quebra_razao_aviso')
    dif = abs(math.log((float(W) / float(H)) / (float(m['largura']) / float(m['altura']))))
    if dif <= lim:
        return []
    cam = mb.camadas_do_laudo(ctx['laudo'])
    saida = []
    for e in aplicados:
        aprovadas = {x['layer_id'] for x in ((e.get('quebras') or {}).get('familia') or [])} \
            if isinstance(e.get('quebras'), dict) else set()
        if e.get('quebras_camada') is not None:
            aprovadas.add(e['quebras_camada'])
        linhas = [mod_quebras.linhas_do_texto(cam[x]) for x in e['layer_ids']
                  if (cam.get(x) or {}).get('tipo') == 'texto' and x not in aprovadas]
        if linhas and max(linhas) > 1:
            saida.append({'nome': 'quebras_sem_aprovacao', 'situacao': 'avisa',
                          'fonte': {'tipo': 'limite', 'ref': 'derivacao.quebra_razao_aviso'}, 'elementos': [e['id']],
                          'medidas': {'linhas': max(linhas), 'diferenca_de_proporcao': round(dif, 6)}})
    return saida


def _layout_transform(mestre, W, H):
    s = W / mestre['largura']
    return [[c * s for c in e['caixa']] for e in mestre['elementos']], [s] * len(mestre['elementos'])


def derivar_formato(ctx, kv, mestres, formato, specs, arquivo_specs, params):
    """Deriva um formato. Devolve o dicionario derivacao/1."""
    W, H = mod_formatos.composicao(formato)
    spec = specs.get(formato['chave'])
    # a folha tem o formato, e um valor que a derivacao le espera o DA (revisao dos becos, A1): a spec nao vale, nem
    # com o valor do rascunho nem sem ele (os formatos do job deixam de fora o campo sem confirmacao)
    por_confirmar = not formato.get('sem_folha') and         formato['chave'] in mod_formatos.chaves_por_confirmar(ctx.get('pasta'))
    if por_confirmar:
        spec = None
    areas = mod_formatos.areas(formato, spec, arquivo_specs)
    base = params['base']['valor']
    saida = {'esquema': ESQUEMA, 'job_id': ctx['estado']['job_id'], 'gerado_em': agora(), 'motor_versao': __version__,
             'formato': {'id': formato['id'], 'chave': formato['chave'], 'largura': int(formato['largura']),
                         'altura': int(formato['altura']), 'rotacao': formato.get('rotacao'),
                         'composicao': [W, H], 'tem_spec': spec is not None,
                         'base': {'tipo': base, 'dimensoes': list(mod_formatos.base_do_formato(formato, areas, base))}},
             'areas': areas, 'parametros': params,
             'briefing_sha256': ctx['briefing_sha256'],
             'briefing_origem': ctx['briefing']['cabecalho']['origem'],
             'laudo_sha256': ctx['briefing']['cabecalho']['laudo_sha256'],
             'portao_fontes': ctx['portao_fontes'],
             'fora_da_peca': kv['fora_da_peca'], 'sem_geometria': kv['sem_geometria'],
             'fora_do_canvas': kv['fora_do_canvas'], 'fora_do_quadro': ctx['info']['fora_do_quadro'],
             'mestre': None, 'familia': None, 'caminho': None, 'situacao': None, 'elementos': [], 'restricoes': [],
             'validacoes': [], 'devolucao': None, 'registros': list(areas['registros'])}
    if kv['indeterminado_sem_regra']:
        return _devolver(saida, _devolucao('indeterminado_sem_regra', elementos=kv['indeterminado_sem_regra']))
    if kv.get('ajuste_global_sobre_conteudo'):
        return _devolver(saida, _devolucao('ajuste_global_sem_aplicar', camadas=kv['ajuste_global_sobre_conteudo']))
    if kv.get('blocos_com_regras_diferentes'):
        return _devolver(saida, _devolucao('bloco_com_regras_diferentes', elementos=kv['blocos_com_regras_diferentes']))
    if kv.get('blocos_partidos'):
        return _devolver(saida, _devolucao('bloco_partido_na_pilha', elementos=[p['elemento'] for p in kv['blocos_partidos']],
                                           blocos=kv['blocos_partidos']))
    # sem folha, o formato nunca deriva em silencio: so o formato marcado sem_folha (medicao, teste) segue, com registro
    if spec is None:
        if por_confirmar:
            return _devolver(saida, _devolucao(MOTIVO_SPEC_POR_CONFIRMAR))
        if not formato.get('sem_folha'):
            return _devolver(saida, _devolucao('formato_sem_folha'))
        saida['registros'].append({'codigo': 'formato_sem_folha'})
    else:
        dim = (spec.get('campos') or {}).get('dimensao') or {}
        v = dim.get('valor') or {}
        if dim.get('unidade') in (None, 'px') and v.get('largura') and v.get('altura') and                 (round(float(v['largura'])) != int(formato['largura']) or round(float(v['altura'])) != int(formato['altura'])):
            return _devolver(saida, _devolucao('dimensao_diferente_da_folha', folha=[v['largura'], v['altura']],
                                               formato=[int(formato['largura']), int(formato['altura'])]))
    au = areas.get('area_util')
    if au is not None and (au['caixa'][2] <= au['caixa'][0] or au['caixa'][3] <= au['caixa'][1]):
        # a folha deixa a area util sem area (faixas maiores que o formato): obrigatoria da folha que nao fecha
        return _devolver(saida, _devolucao('restricao_obrigatoria_nao_fecha',
                                           restricao={'nome': 'area_util_sem_area', 'forca': 'obrigatoria',
                                                      'fonte': au['fonte'], 'elementos': []}))
    # o formato que e a propria mestre propria do DA
    propria = next((m for m in ctx['briefing']['mestres'] if m['tipo'] == 'propria' and m.get('formato') == formato['id']),
                   None)
    if propria is not None and propria['id'] not in ctx['proprias_permitidas']:
        saida['caminho'] = 'mestre_propria'
        return _devolver(saida, _devolucao('acima_do_numero_de_mestres', mestres_max=params['mestres_max']['valor']))
    if propria is not None:
        m, faltando = mestre_propria(kv, propria, formato, mb.camadas_do_laudo(ctx['laudo']))
        saida['mestre'] = {'id': m['id'], 'tipo': 'propria', 'largura': W, 'altura': H}
        saida['caminho'] = 'mestre_propria'
        if faltando:
            return _devolver(saida, _devolucao('mestre_propria_incompleta', elementos=faltando))
        caixas = [e['caixa'] for e in m['elementos']]
        escalas = [1.0] * len(caixas)
        return _fechar(ctx, saida, kv, m, (W, H), areas, caixas, escalas, base, propria_do_formato=True)
    # familia: a mestre de mesma orientacao e proporcao mais perto, dentro da faixa
    faixa = params['faixa']['valor']
    candidatas = []
    for m in mestres:
        bm = (m['largura'], m['altura']) if m['tipo'] == 'kv' else m['base']
        bf = mod_formatos.base_do_formato(formato, areas, base)
        fam = mod_formatos.familia(bm, bf, faixa)
        if abs(m['altura'] * W / m['largura'] - H) <= limites.valor('derivacao.mesma_proporcao_px'):
            # mesma proporcao da mestre (dentro do pixel): a banda do quadrado nao separa os dois
            fam = dict(fam, troca=None, na_faixa=True, mesma_proporcao=True)
        candidatas.append((m, fam, bm, bf))
    na_faixa = [c for c in candidatas if c[1]['na_faixa']]
    if not na_faixa:
        m, fam, _bm, _bf = candidatas[0]
        saida['mestre'] = {'id': m['id'], 'tipo': m['tipo'], 'largura': m['largura'], 'altura': m['altura']}
        saida['familia'] = fam
        if any(c[1]['troca'] is None for c in candidatas):
            motivo = 'fora_da_faixa_de_familia'
        else:
            motivo = 'troca_forte_de_orientacao' if fam['troca'] == 'forte' else 'troca_de_orientacao_quadrado'
        return _devolver(saida, _devolucao(motivo, fator=fam['fator'], orientacao_mestre=fam['orientacao_mestre'],
                                           orientacao_formato=fam['orientacao_formato']))
    m, fam, bm, bf = min(na_faixa, key=lambda c: (c[1]['fator'], c[0]['id']))
    if m.get('por_confirmar'):
        # a mestre propria cujo formato espera um valor de spec: a familia espera com ela (revisao dos becos, D3)
        saida['mestre'] = {'id': m['id'], 'tipo': m['tipo'], 'largura': m['largura'], 'altura': m['altura']}
        saida['familia'] = fam
        return _devolver(saida, _devolucao(MOTIVO_MESTRE_POR_CONFIRMAR, mestre=m['id'],
                                           formato_da_mestre=m['por_confirmar']['formato'],
                                           chave_da_mestre=m['por_confirmar']['chave']))
    m, sem_medida = _com_quebras(ctx, m, formato, W, H)
    if sem_medida:
        return _devolver(saida, _devolucao('quebra_sem_medida', camadas=sem_medida))
    saida['mestre'] = {'id': m['id'], 'tipo': m['tipo'], 'largura': m['largura'], 'altura': m['altura']}
    saida['familia'] = fam
    regras = []
    for e in m['elementos']:
        regras.append(mod_escala.escala(e['regra'], bm, bf))
    # mesma proporcao: transform de saida, se satisfaz as obrigatorias
    s_w = W / m['largura']
    if abs(m['altura'] * s_w - H) <= limites.valor('derivacao.mesma_proporcao_px'):
        caixas, escalas = _layout_transform(m, W, H)
        val = mod_validacao.validar((W, H), areas, _aplicados(m, regras), caixas, escalas, _kv_por_id(kv),
                                    _esperado(ctx, kv))
        if not mod_validacao.reprovadas(val):
            saida['caminho'] = 'transform'
            # na mesma proporcao o formato e a mestre escalada: as ancoras nao entram (revisao 3, M1: registro)
            saida['registros'].append({'codigo': 'transform_sem_ancoras', 'medidas': {
                'ancoras': [[e['id'], e['ancora'][0], e['ancora'][1]] for e in m['elementos']]}})
            return _fechar(ctx, saida, kv, m, (W, H), areas, caixas, escalas, base, regras=regras, validacoes=val)
        saida['registros'].append({'codigo': 'transform_reprovou_obrigatoria_vai_ao_solver',
                                   'medidas': {'validacoes': [v['nome'] for v in mod_validacao.reprovadas(val)]}})
    saida['caminho'] = 'solver'
    try:
        caixas, escalas, restricoes = mod_solver.resolver(m['elementos'], (m['largura'], m['altura']), (W, H), areas,
                                                          regras)
    except mod_solver.NaoFecha as e:
        return _devolver(saida, _devolucao('restricao_obrigatoria_nao_fecha', restricao=e.restricao,
                                           elementos=e.restricao['elementos']))
    saida['restricoes'] = restricoes
    return _fechar(ctx, saida, kv, m, (W, H), areas, caixas, escalas, base, regras=regras)


def _q(v, casas):
    """Valor arredondado e sem -0.0: o Cassowary chega ao mesmo otimo por caminhos diferentes conforme a ordem interna,
    com diferenca no ultimo bit; arredondado, o resultado e o mesmo em todo processo."""
    return round(float(v), casas) + 0.0


def _kv_por_id(kv):
    return {e['id']: e for e in kv['elementos']}


def _esperado(ctx, kv):
    """{id do elemento: (funcao resolvida, regra)} relido do briefing gravado no disco (quando ha job), nunca do
    layout nem da heranca que o layout usou. O contexto da tela (da_tela) confere contra o briefing em memoria de onde o
    layout saiu (o de partida, a retomada ou o gravado com o rascunho da tela por cima): o gravado no disco e outro
    (o rascunho do motor, ou o de antes da regra que o DA mudou no Design system) e reprovaria a regra nova do DA."""
    briefing = ctx['briefing']
    if not ctx.get('da_tela') and ctx.get('pasta') is not None and (Path(ctx['pasta']) / mb.ARQUIVO).is_file():
        briefing = mb.ler(ctx['pasta'])
    return esperado_do_briefing(ctx['laudo'], briefing, kv['elementos'])


def esperado_do_briefing(laudo, briefing, elementos):
    """{id do elemento: (funcao, regra)} relido do briefing; no bloco, (funcao, regra, {raiz do membro: funcao}): a
    validacao confere a funcao de cada membro (decisoes-v1.md, 100)."""
    resolvidas, _e, _i = mb.resolver(laudo, briefing)
    saida = {}
    for e in elementos:
        # a funcao do elemento (ou do bloco) e a da raiz dele; a de cada membro, a da primeira camada dele
        r = next((resolvidas[x] for x in e['layer_ids'] if x in resolvidas and resolvidas[x]['raiz'] == e['raiz']),
                 resolvidas.get(e['layer_ids'][0]))
        if r is None:
            saida[e['id']] = (None, None)
            continue
        camadas = e.get('membros_camadas') or {e['raiz']: e['layer_ids']}
        membros = {}
        for raiz, lids in camadas.items():
            rm = next((resolvidas[x] for x in lids if x in resolvidas), None)
            membros[raiz] = rm['funcao'] if rm else None
        relido = dict(e, funcao=r['funcao'], membros_funcoes=membros)
        if r['funcao'] == mb.FUNCAO_INDETERMINADO and not e.get('bloco'):
            ind = mb.regras_indeterminado(briefing)
            regra = ind.get(e['raiz']) or next((ind[x] for x in e['layer_ids'] if x in ind), None)
        else:
            regra, _dos, _c = mb.regra_do_elemento(briefing, relido)
        saida[e['id']] = (r['funcao'], regra, membros) if e.get('bloco') else (r['funcao'], regra)
    return saida


def _aplicados(m, regras):
    return [dict(e, escala_regra=r) for e, r in zip(m['elementos'], regras)]


def _devolver(saida, devolucao):
    saida['situacao'] = 'devolvido'
    saida['caminho'] = saida['caminho'] or 'devolvido'
    saida['devolucao'] = devolucao
    return saida


def _fechar(ctx, saida, kv, m, formato, areas, caixas, escalas, base, regras=None, validacoes=None,
            propria_do_formato=False):
    W, H = formato
    # arredondado antes de validar: a validacao e o arquivo veem os mesmos numeros em todo processo
    caixas = [[_q(v, CASAS_PX) for v in c] for c in caixas]
    escalas = [_q(v, CASAS_ESCALA) for v in escalas]
    aplicados = _aplicados(m, regras or [None] * len(m['elementos']))
    if validacoes is None:
        validacoes = mod_validacao.validar(formato, areas, aplicados, caixas, escalas, _kv_por_id(kv),
                                           _esperado(ctx, kv))
    if kv.get('fundo_ambiguo'):
        # fundo logo abaixo do limiar do fundo de cena: juntou a cena num bloco, e o DA confere (revisao 2, M2)
        validacoes = list(validacoes) + [{'nome': 'fundo_de_cena_ambiguo', 'situacao': 'avisa',
                                          'fonte': {'tipo': 'limite', 'ref': 'derivacao.bloco_fundo_faixa_ambigua'},
                                          'elementos': [x['elemento'] for x in kv['fundo_ambiguo']],
                                          'medidas': {'fundos': kv['fundo_ambiguo']}}]
    if not propria_do_formato:
        validacoes = list(validacoes) + _quebras_sem_aprovacao(ctx, m, aplicados, W, H)
    saida['validacoes'] = validacoes
    for e, c, s in zip(aplicados, caixas, escalas):
        s_total = s * float(e.get('escala_na_mestre') or 1.0)
        doc = e['caixa_doc']
        item = {'id': e['id'], 'raiz': e['raiz'], 'funcao': e['funcao'], 'classe': e['classe'],
                'layer_ids': e['layer_ids'], 'texto': e['texto'], 'regra': e['regra'],
                'escala_regra': None if e.get('escala_regra') is None else round(e['escala_regra'], 6),
                'ancora': list(e['ancora']), 'caixa_mestre': [_q(v, CASAS_PX) for v in e['caixa']],
                'caixa': [_q(v, CASAS_PX) for v in c], 'escala': _q(s_total, CASAS_ESCALA),
                'regra_aplicada': {'funcao': e['funcao'], 'regra': e['regra'], 'caminho': saida['caminho'],
                                   'classe': e['classe']},
                # arredondado: o solver pode variar no ultimo bit conforme a ordem interna, e o resultado tem de ser
                # o mesmo em todo processo
                'transformacao': {'s': _q(s_total, CASAS_ESCALA), 'origem_doc': [doc[0], doc[1]],
                                  'destino': [_q(c[0], CASAS_PX), _q(c[1], CASAS_PX)],
                                  'recorte_doc': e.get('caixa_asset_doc') or doc,
                                  'sangra': dict(e['sangra'])},
                'corpo_px': None if e.get('corpo_px') is None else round(e['corpo_px'] * s_total, 4),
                'quebras': e.get('quebras') or ('congeladas_da_mestre' if e['texto'] else None),
                # de onde veio a funcao do elemento: a da raiz dele (no bloco, a do maior membro)
                'origem_funcao': next((ctx['resolvidas'][x]['por'] for x in e['layer_ids']
                                       if x in ctx['resolvidas'] and ctx['resolvidas'][x]['raiz'] == e['raiz']),
                                      ctx['resolvidas'][e['layer_ids'][0]]['por']),
                # de onde veio a caixa (proposta do M7, parametros): escala pura, solver ou a mestre desenhada pelo DA
                'origem_geometria': ORIGEM_GEOMETRIA[saida['caminho']]}
        if e.get('quebras_camada') is not None:
            item['quebras_camada'] = e['quebras_camada']
        if e['texto'] and m['tipo'] == 'propria' and propria_do_formato and e.get('quebras') is None:
            saida['registros'].append({'codigo': 'quebras_da_origem_sem_requebra_aprovada', 'medidas': {'elemento': e['id']}})
        saida['elementos'].append(item)
    ruins = mod_validacao.reprovadas(validacoes)
    if ruins:
        v = ruins[0]
        return _devolver(saida, _devolucao('validacao_obrigatoria_reprovou',
                                           restricao={'nome': v['nome'], 'forca': 'obrigatoria', 'fonte': v['fonte'],
                                                      'elementos': v['elementos'], 'medidas': v.get('medidas')},
                                           elementos=v['elementos'], validacoes=[x['nome'] for x in ruins]))
    if propria_do_formato and any(r['codigo'] == 'quebras_da_origem_sem_requebra_aprovada' for r in saida['registros']):
        # as quebras da mestre nunca sao congeladas entre orientacoes (arquitetura-v1.md, 4.10)
        if mod_escala.troca_de_orientacao((kv['largura'], kv['altura']), (W, H)) is not None:
            return _devolver(saida, _devolucao('mestre_propria_incompleta',
                                               elementos=[e['id'] for e in aplicados if e['texto'] and e.get('quebras') is None],
                                               falta='quebras_aprovadas_pelo_da'))
    saida['situacao'] = 'derivado'
    return saida


def contexto(laudo, briefing, *, ds=None, job_id=None, pasta=None, briefing_sha256=None, portao_fontes='passa',
             medidas_quebras=None, da_tela=False):
    """Contexto da derivacao em memoria (o mesmo que preparar monta do job; os testes e a medicao usam direto).
    medidas_quebras: a medida das linhas juntadas (derivacao.medida_quebras.medir); sem ela, o formato com quebra
    aprovada volta ao DA. da_tela: o briefing e o da previa da tela (preparar com partida, desdobra.tela.estado), e a
    validacao confere contra ele (_esperado)."""
    resolvidas, _e, info = mb.resolver(laudo, briefing)
    return {'pasta': Path(pasta) if pasta else None, 'estado': {'job_id': job_id or briefing['job_id']},
            'briefing': briefing, 'laudo': laudo, 'ds': ds, 'resolvidas': resolvidas, 'info': info,
            'briefing_sha256': briefing_sha256 or '0' * 64, 'portao_fontes': portao_fontes,  # numero-neutro: hash vazio so em memoria
            'medidas_quebras': dict(medidas_quebras or {}), 'da_tela': bool(da_tela)}


def derivar_em_memoria(ctx, *, specs=None, arquivo_specs=None, params=None, so=None, composicoes=True):
    """Deriva os formatos do briefing sem gravar. Devolve {'formatos', 'devolucoes', 'inventario', 'kv'}.
    composicoes: aplica as familias confirmadas na tela (briefing composicoes; desdobra.derivacao.proposta); a tela
    deriva sem elas, para a previa partir da proposta do motor e levar as edicoes do rascunho por cima."""
    b = ctx['briefing']
    specs = specs or {}
    params = params or mod_formatos.parametros(ctx['pasta'], b)
    kv = mestre_do_kv(ctx)
    formatos = [f for f in b['formatos'] if so is None or f['id'] in so]
    if so is not None and len(formatos) != len(set(so)):
        raise ErroDerivacao('Formato fora do briefing.', 'formato_desconhecido',
                            {'pedidos': sorted(set(so) - {f['id'] for f in formatos})})
    # mestres: a do KV e as proprias (cada propria vira mestre da familia dela, na base do formato)
    mestres = [kv]
    proprias = {}
    pendentes = mod_formatos.chaves_por_confirmar(ctx.get('pasta'))
    for mp in b['mestres']:
        if mp['tipo'] != 'propria':
            continue
        fmt = next(f for f in b['formatos'] if f['id'] == mp['formato'])
        m, faltando = mestre_propria(kv, mp, fmt, mb.camadas_do_laudo(ctx['laudo']))
        # o formato da mestre com valor de spec a espera do DA: a base nunca sai do valor sem confirmacao, e os formatos
        # que derivam desta mestre esperam com ela (mestre_por_confirmar; revisao dos becos, D3)
        espera = not fmt.get('sem_folha') and fmt['chave'] in pendentes
        areas = mod_formatos.areas(fmt, None if espera else specs.get(fmt['chave']), arquivo_specs)
        m['base'] = mod_formatos.base_do_formato(fmt, areas, params['base']['valor'])
        if espera:
            m['por_confirmar'] = {'formato': fmt['id'], 'chave': fmt['chave']}
        if not faltando:
            proprias[mp['id']] = m
    n_mestres = 1 + len(proprias)
    maximo = int(params['mestres_max']['valor'])
    # acima do numero de mestres do job, as proprias que sobram (pela ordem do id) nao viram mestre
    for k in sorted(proprias)[max(maximo - 1, 0):]:
        proprias.pop(k)
    ctx['proprias_permitidas'] = set(proprias) | {mp['id'] for mp in b['mestres'] if mp['tipo'] == 'propria'
                                                  and mp['id'] not in proprias and n_mestres <= maximo}
    mestres += [proprias[k] for k in sorted(proprias)]
    resultados = {}
    for f in formatos:
        try:
            d = derivar_formato(ctx, kv, mestres, f, specs, arquivo_specs, params)
        except Exception as e:  # noqa: BLE001 - um formato que quebra volta ao DA sozinho, os outros seguem
            d = _formato_com_erro(ctx, kv, f, params, e)
        if d['situacao'] == 'devolvido' and d['devolucao']['motivo'] in ('troca_forte_de_orientacao',
                                                                         'troca_de_orientacao_quadrado',
                                                                         'fora_da_faixa_de_familia')                 and n_mestres > maximo:
            # o motivo da orientacao fica; o registro diz que o job ja passou do numero de mestres
            d['devolucao'].setdefault('medidas', {})['mestres_max_atingido'] = True
        resultados[f['id']] = d
    if composicoes and b.get('composicoes'):
        from desdobra.derivacao import proposta as mod_proposta

        def derivar_um(f):
            try:
                return derivar_formato(ctx, kv, mestres, f, specs, arquivo_specs, params)
            except Exception as e:  # noqa: BLE001 - como no laco acima
                return _formato_com_erro(ctx, kv, f, params, e)
        mod_proposta.aplicar(ctx, kv, resultados, derivar_um, specs=specs, arquivo_specs=arquivo_specs, params=params)
    inventario = _inventario(kv, resultados)
    for d in resultados.values():
        d['inventario_entre_formatos'] = 'igual' if inventario['iguais_entre_formatos'] else 'diferente'
        contratos.validar(d, ESQUEMA)
    return {'formatos': resultados, 'devolucoes': _devolucoes(resultados), 'inventario': inventario, 'kv': kv}


def _inventario(kv, resultados):
    # o elemento que o DA apagou na familia conta como presente (decisoes-v1.md, 169): a decisao e dele
    conjuntos = {k: sorted([e['id'] for e in d['elementos']] + [a['elemento'] for a in d.get('apagados_pelo_da') or []])
                 for k, d in resultados.items() if d['situacao'] == 'derivado'}
    return {'mestre': sorted(e['id'] for e in kv['elementos']),
            'iguais_entre_formatos': len({tuple(v) for v in conjuntos.values()}) <= 1, 'formatos': len(conjuntos)}


def _devolucoes(resultados):
    return [{'formato': k, 'chave': d['formato']['chave'], **d['devolucao']}
            for k, d in sorted(resultados.items()) if d['situacao'] == 'devolvido']


def _formato_com_erro(ctx, kv, formato, params, erro):
    W, H = mod_formatos.composicao(formato)
    saida = {'esquema': ESQUEMA, 'job_id': ctx['estado']['job_id'], 'gerado_em': agora(), 'motor_versao': __version__,
             'formato': {'id': formato['id'], 'chave': formato['chave'], 'largura': int(formato['largura']),
                         'altura': int(formato['altura']), 'rotacao': formato.get('rotacao'), 'composicao': [W, H],
                         'tem_spec': None, 'base': {'tipo': params['base']['valor'], 'dimensoes': [W, H]}},
             'areas': {'area_util': None, 'faixas': [], 'area_segura': None, 'registros': []}, 'parametros': params,
             'briefing_sha256': ctx['briefing_sha256'], 'briefing_origem': ctx['briefing']['cabecalho']['origem'],
             'laudo_sha256': ctx['briefing']['cabecalho']['laudo_sha256'], 'portao_fontes': ctx['portao_fontes'],
             'fora_da_peca': kv['fora_da_peca'], 'sem_geometria': kv['sem_geometria'], 'mestre': None,
             'familia': None, 'caminho': 'devolvido', 'situacao': None, 'elementos': [], 'restricoes': [],
             'validacoes': [], 'devolucao': None, 'registros': []}
    return _devolver(saida, _devolucao('erro_no_formato', erro=type(erro).__name__))


def derivar(pasta, so=None):
    """Deriva os formatos do briefing (ou so os ids de so). Grava derivacao/<id>.json e atualiza
    derivacao/devolucoes.json: com so, so as entradas desses formatos mudam, e o inventario e refeito com todos os
    formatos do briefing que tem derivacao gravada deste briefing."""
    ctx = preparar(pasta)
    pasta = ctx['pasta']
    specs, arquivo_specs = mod_formatos.specs_do_job(pasta)
    r = derivar_em_memoria(ctx, specs=specs, arquivo_specs=arquivo_specs,
                           params=mod_formatos.parametros(pasta, ctx['briefing']), so=so)
    (pasta / PASTA).mkdir(parents=True, exist_ok=True)
    for k, d in r['formatos'].items():
        contratos.gravar(pasta / PASTA / ('%s.json' % k), d, ESQUEMA)
    todos = {}
    for f in ctx['briefing']['formatos']:
        arq = pasta / PASTA / ('%s.json' % f['id'])
        if f['id'] in r['formatos']:
            todos[f['id']] = r['formatos'][f['id']]
        elif arq.is_file():
            try:
                d = contratos.ler(arq, ESQUEMA)
            except contratos.ErroContrato:
                continue
            if d['briefing_sha256'] == ctx['briefing_sha256']:
                todos[f['id']] = d
    inventario = _inventario(r['kv'], todos)
    dev = {'esquema': ESQUEMA_DEVOLUCOES, 'job_id': ctx['estado']['job_id'], 'gerado_em': agora(),
           'briefing_sha256': ctx['briefing_sha256'], 'devolucoes': _devolucoes(todos), 'inventario': inventario}
    contratos.gravar(pasta / ARQUIVO_DEVOLUCOES, dev, ESQUEMA_DEVOLUCOES)
    return dict(r, devolucoes=dev['devolucoes'], inventario=inventario)


def conferir_layout(pasta, formato):
    """Releitura do layout gravado (derivacao/<formato>.json) contra o briefing gravado no disco agora: a funcao
    resolvida e a regra de cada elemento tem de ser as que o layout aplicou. Devolve as validacoes que reprovam."""
    pasta = Path(pasta).resolve()
    d = contratos.ler(pasta / PASTA / ('%s.json' % formato), ESQUEMA)
    briefing = mb.ler(pasta)
    laudo = contratos.ler(pasta / mb.ARQUIVO_LAUDO, 'laudo/1')
    esperado = esperado_do_briefing(laudo, briefing, d['elementos'])
    ruins = []
    for e in d['elementos']:
        funcao, regra = esperado.get(e['id'], (None, None))
        if (funcao, regra) != (e['regra_aplicada']['funcao'], e['regra_aplicada']['regra']):
            ruins.append({'nome': 'regra_por_funcao', 'situacao': 'reprova',
                          'fonte': {'tipo': 'briefing', 'ref': mb.ARQUIVO.as_posix()}, 'elementos': [e['id']],
                          'medidas': {'funcao': funcao, 'regra': regra, 'funcao_do_layout': e['regra_aplicada']['funcao'],
                                      'regra_do_layout': e['regra_aplicada']['regra']}})
    return ruins


def residuo(d, elemento_id):
    """|ln(escala / escala da regra)| de um elemento derivado (para a medicao contra a derivacao humana)."""
    e = next(x for x in d['elementos'] if x['id'] == elemento_id)
    return abs(math.log(e['escala'] / e['escala_regra'])) if e.get('escala_regra') else None
