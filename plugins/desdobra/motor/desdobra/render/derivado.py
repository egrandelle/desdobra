# -*- coding: utf-8 -*-
"""Contrato da composicao (composicao/1) de um formato derivado (M5), a partir de derivacao/<formato>.json.

O contrato da origem (desdobra.render.contrato) da as entradas de baixo para cima; aqui cada entrada recebe a
transformacao do elemento a que a camada pertence (escala uniforme e deslocamento, arquitetura-v1.md, 4.10):
  - pilha: as camadas da pilha da origem sao separadas pelo elemento de cada uma (as vizinhas do mesmo elemento ficam
    juntas) e cada pedaco vira uma pilha com a transformacao do elemento e o recorte da caixa da mestre (o asset sai do
    canvas da mestre e acaba na borda dele);
  - texto: a matriz da camada recebe a escala e o deslocamento do elemento (as quebras e o tracking ficam os da
    mestre, so o tamanho muda); a regiao da pagina e a da origem transformada, com a margem do render;
  - texto editado pelo DA no palco (decisoes-v1.md, 169 e 171; M7b, A7): o texto novo num trecho so, com o estilo do
    primeiro trecho com tinta, as linhas do DA e a quebra no espaco na largura da caixa de tinta da camada (a mesma
    da previa da tela), medida no Chromium pelo render; o cmap da face do job e conferido como na edicao, e a tinta
    e conferida na borda do formato (a pagina cobre o formato inteiro: nada e cortado calado);
  - linkado: o quadrilatero de colocacao e a caixa recebem a transformacao.
Camada "fora da peca" nao entra em entrada nenhuma. Camada sem elemento (estrutura, fora do quadro ou fora do
canvas) sai do formato com registro. O ajuste global entra no bloco da cena que ele cobre; o que cobre conteudo, e o
bloco que a pilha parte (outro elemento entre um efeito e o que ele pega), devolvem o formato na derivacao
(decisoes-v1.md, 95 e 99). Se ainda assim um efeito de um elemento abrir um pedaco de pilha separado do que ele pega,
o render recusa (elemento_partido_no_render): pedaco de efeito sozinho nunca sai em silencio. Formato com rotacao
renderiza a composicao (largura e altura trocadas nos 90 e 270 graus); a entrega gira o master para o arquivo.

Funcao pura dos arquivos do job.
"""
import hashlib
import json
import math
from pathlib import Path

from desdobra import contratos, limites
from desdobra.briefing import modelo as mb
from desdobra.derivacao import impressao as mi
from desdobra.derivacao import nucleo as nd
from desdobra.render import contrato as mc

DESCRICOES = {
    'formato_sem_derivacao': 'O formato não tem derivacao/<formato>.json. Rode "desdobra derivar --job <pasta>".',
    'formato_devolvido': 'A derivação devolveu este formato ao DA (veja derivacao/devolucoes.json): não há layout '
                         'para renderizar.',
    'texto_editado_fora_da_fonte': 'O texto editado na tela tem caractere que a fonte do job não tem, e o render não '
                                   'desenha o texto sem ele. Troque o caractere na tela ou envie a fonte que o tenha.',
    'derivacao_desatualizada': 'A derivação gravada não é a que o briefing, as specs, os parâmetros e os limites de agora '
                               'dão (arquivo mexido ou entrada mudada). Rode "desdobra derivar" de novo.',
    'briefing_desatualizado': 'O briefing é de outra versão do laudo, das specs, do design system ou das fontes.',
    'elemento_partido_no_render': 'Um efeito de um elemento (ajuste, mesclagem ou camada clipada) ficaria num pedaço de '
                                  'pilha separado do que ele pega. A derivação devia ter devolvido o formato: rode o '
                                  '"desdobra derivar" de novo e mande o caso para a Trezion.',
    'mesclagem_sem_o_fundo_de_outro_elemento': 'Há camada com mesclagem diferente da normal. No formato derivado, cada '
                                               'elemento é composto sozinho: a mesclagem não pega os elementos de '
                                               'baixo. É decisão do DA aceitar.',
}


def _bloqueio(codigo, **medidas):
    return {'codigo': codigo, 'descricao': DESCRICOES[codigo], 'medidas': medidas}


def _sha_texto(dados):
    return hashlib.sha256(json.dumps(dados, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def _ponto(tr, x, y):
    s = tr['s']
    return s * (x - tr['origem_doc'][0]) + tr['destino'][0], s * (y - tr['origem_doc'][1]) + tr['destino'][1]


def _caixa(tr, c):
    x0, y0 = _ponto(tr, c[0], c[1])
    x1, y1 = _ponto(tr, c[2], c[3])
    return [x0, y0, x1, y1]


def _regiao(tr, regiao, W, H):
    m = int(limites.valor('render.margem_regiao_px'))
    c = _caixa(tr, regiao)
    r = [int(math.floor(c[0])) - m, int(math.floor(c[1])) - m, int(math.ceil(c[2])) + m, int(math.ceil(c[3])) + m]
    r = [max(r[0], 0), max(r[1], 0), min(r[2], W), min(r[3], H)]
    return r if r[2] > r[0] and r[3] > r[1] else None


def _sem_carimbo(d):
    # o sha do briefing e so registro de quando o formato foi derivado: a impressao_formato (comparada aqui) e que diz
    # se o que alimenta o formato mudou (M7b, A2). Da proposta sai o que a impressao tambem deixa fora (o carimbo da
    # confirmacao e o id da familia): o salvar seletivo (A6) guarda o arquivo do formato que so ganhou um destes
    d = {k: v for k, v in d.items() if k not in ('gerado_em', 'inventario_entre_formatos', 'briefing_sha256')}
    if 'proposta' in d:
        d['proposta'] = mi.sem_carimbo(d['proposta'])
    return d


def _derivacao_confere(pasta, formato, gravada):
    """A derivacao e deterministica: o render refaz a do formato com o briefing, as specs, os parametros e os limites
    de agora e so segue se sai igual ao arquivo gravado (arquivo mexido, parametro ou limite mudado: rode o derivar)."""
    from desdobra.derivacao import formatos as mod_formatos
    try:
        ctx = nd.preparar(pasta)
        specs, arq = mod_formatos.specs_do_job(pasta)
        r = nd.derivar_em_memoria(ctx, specs=specs, arquivo_specs=arq,
                                  params=mod_formatos.parametros(pasta, ctx['briefing']), so=[formato])
    except (nd.ErroDerivacao, contratos.ErroContrato, mod_formatos.ErroFormatos):
        return False
    novo = json.loads(json.dumps(r['formatos'][formato]))
    return _sem_carimbo(novo) == _sem_carimbo(gravada)


def ler_derivacao(pasta, formato):
    arq = Path(pasta) / nd.PASTA / ('%s.json' % formato)
    return contratos.ler(arq, nd.ESQUEMA) if arq.is_file() else None


def mesclas_sem_fundo(pedacos, regs, ja_tem_embaixo=False):
    """Camadas em mesclagem diferente da normal que ficam sem o fundo no formato derivado: cada pedaco de pilha e
    composto sozinho, entao so perde o fundo a camada que abre um pedaco com algo desenhado embaixo dela. Dentro de um
    bloco (decisoes-v1.md, 95), a luz e o ajuste ficam no mesmo pedaco do que eles pegam, como no KV."""
    saida = []
    for k, (el, indices, lids) in enumerate(pedacos):
        i, lid = indices[0], lids[0]
        blend = regs[i].get('blend')
        if blend not in ('NORMAL', 'PASS_THROUGH', None) and (k > 0 or ja_tem_embaixo):
            saida.append({'layer_id': lid, 'blend': blend, 'elemento': el['id'] if isinstance(el, dict) else el})
    return saida


def quebras_da_entrada(el, entrada):
    """Quebras aprovadas que o render aplica no texto da entrada (revisao 3, A3 e M5): as da familia (indices das
    quebras que ficam; o render calcula as posicoes que viram espaco) e a lista de posicoes da mestre propria (espacos
    que viram quebra). Cada texto do elemento com a sua."""
    from desdobra.derivacao import quebras as mq
    q = el.get('quebras')
    if isinstance(q, dict):
        item = next((x for x in q.get('familia') or [] if x['layer_id'] == entrada['layer_id']), None)
        if item is not None:
            return {'quebras_juntadas': mq.juntadas({'texto': entrada['texto']}, item['aprovadas'])}
    if isinstance(q, list) and el.get('quebras_camada') == entrada['layer_id']:
        return {'quebras_inseridas': list(q)}
    return {}


def _tolerancia_tinta(caixa):
    lado = max(caixa[2] - caixa[0], caixa[3] - caixa[1])
    return max(float(limites.valor('render.tolerancia_tinta_texto_min_px')),
               float(limites.valor('render.tolerancia_tinta_texto')) * lado)


def caixa_validada_do_texto(el, layer_id, caixa_doc):
    """A caixa que a derivacao validou para o texto layer_id do elemento, no formato: a medida da quebra por familia,
    a caixa do DA na mestre propria (elemento de um texto so), ou caixa_doc (a tinta da camada no KV) transformada."""
    tr = el['transformacao']
    fam = next((x for x in ((el.get('quebras') or {}).get('familia') or []) if x['layer_id'] == layer_id),
               None) if isinstance(el.get('quebras'), dict) else None
    if fam is not None:
        return _caixa(tr, fam['caixa_doc'])
    if el.get('quebras_camada') == layer_id and isinstance(el.get('quebras'), list):
        return list(el['caixa'])
    return _caixa(tr, caixa_doc)


def regiao_da_pagina_de_texto(tr, regiao, cv, W, H):
    """Regiao da pagina de um texto no formato: a caixa validada cv com folga, unida a regiao da origem
    transformada, dentro do formato. O texto nunca e cortado no recorte do elemento (a tela de briefing usa esta
    mesma regiao como recorte do texto)."""
    reg = _regiao(tr, regiao, W, H)
    folga = int(limites.valor('render.margem_regiao_px')) + int(math.ceil(_tolerancia_tinta(cv)))
    alvo = [int(math.floor(cv[0])) - folga, int(math.floor(cv[1])) - folga, int(math.ceil(cv[2])) + folga,
            int(math.ceil(cv[3])) + folga]
    alvo = [max(alvo[0], 0), max(alvo[1], 0), min(alvo[2], W), min(alvo[3], H)]
    if reg is not None:
        alvo = [min(alvo[0], reg[0]), min(alvo[1], reg[1]), max(alvo[2], reg[2]), max(alvo[3], reg[3])]
    return alvo


def tinta_fora_da_caixa(entradas, estatisticas, W, H):
    """Textos cuja tinta real (medida no filho) passa da caixa validada pela derivacao alem da tolerancia, ou encosta
    na borda da regiao da pagina (cortada) sem que a caixa validada chegue ali (revisao 3, C1 e A1)."""
    por_id = {s['id']: s for s in estatisticas if s.get('tipo') == 'texto'}
    saida = []
    for e in entradas:
        cv = e.get('caixa_validada')
        st = por_id.get(e['id'])
        if e['tipo'] != 'texto' or cv is None or st is None or not st.get('tinta'):
            continue
        tol = _tolerancia_tinta(cv)
        t = st['tinta']
        excesso = max(cv[0] - t[0], cv[1] - t[1], t[2] - cv[2], t[3] - cv[3])
        reg = e['regiao']
        cortes = [lado for lado in st.get('toca_regiao') or []
                  if not ({'esq': reg[0] <= 0 and cv[0] <= tol, 'topo': reg[1] <= 0 and cv[1] <= tol,
                           'dir': reg[2] >= W and cv[2] >= W - tol, 'base': reg[3] >= H and cv[3] >= H - tol}[lado])]
        if e.get('texto_editado'):
            # o texto editado nao tem caixa validada pela derivacao: a pagina e o formato, e tinta na borda e corte
            cortes = list(st.get('toca_regiao') or [])
        if excesso > tol or cortes:
            saida.append({'layer_id': e['layer_id'], 'excesso_px': round(excesso, 2), 'tolerancia_px': round(tol, 2),
                          'cortada_na_regiao': cortes})
    return saida


def texto_editado_na_entrada(entrada, texto, caixa_tinta):
    """A entrada de texto do contrato com o texto editado pelo DA (M7b, A7): um trecho so, com o estilo, a cor e a
    face do primeiro trecho com tinta (como a previa da tela, desdobra.tela.edicao.trocar_texto), o paragrafo dele e
    largura_quebra: a largura da caixa de tinta da camada no formato (caixa_tinta), levada ao espaco do texto, onde o
    render quebra a linha no espaco (desdobra.render.texto.quebras_da_caixa), como a previa quebra na largura da
    caixa. A matriz e a da entrada (ja no formato)."""
    from desdobra.render import texto as rt
    texto = texto.replace('\r\n', '\n').replace('\r', '\n')
    t = entrada['texto']
    r0 = next(r for r in t['runs'] if r.get('tem_tinta'))
    par = rt._paragrafo_de(t.get('paragrafos') or [], r0['inicio'])
    cor = entrada['cores_por_trecho'][str(r0['inicio'])]
    novo = json.loads(json.dumps(entrada))
    # o kerning manual era de um par do texto antigo
    novo['texto']['runs'] = [dict(r0, inicio=0, fim=len(texto), texto=texto, kerning=None, tem_tinta=True)]
    novo['texto']['paragrafos'] = [dict(par, inicio=0, fim=len(texto) + 1)] if par else []
    novo['cores'] = [cor]
    novo['cores_por_trecho'] = {'0': cor}
    novo['valores_cor'] = {cor: entrada['valores_cor'][cor]}
    novo['faces'] = {k: v for k, v in entrada['faces'].items() if k == r0.get('fonte_ps')}
    xx, xy = (float(v) for v in t['matriz'][:2])
    largura = (float(caixa_tinta[2]) - float(caixa_tinta[0])) / math.hypot(xx, xy)
    novo['largura_quebra'] = round(largura, 4)  # numero-neutro: casas do px
    novo['texto_editado'] = True
    return novo


def caracteres_fora_da_face(entrada, faces_do_job):
    """Os caracteres do texto editado da entrada que a face do job nao cobre (a conferencia da edicao na tela,
    desdobra.tela.edicao.caracteres_que_faltam, pelo cmap lido pelo filho das fontes)."""
    from desdobra.tela import edicao
    r = entrada['texto']['runs'][0]
    face = next((f for f in faces_do_job if f['id'] == entrada['faces'].get(r.get('fonte_ps'))), None)
    if face is None:
        return []
    return edicao.caracteres_que_faltam(r['texto'], face, r.get('font_caps') in ('ALL_CAPS', 'SMALL_CAPS'))


def _efeitos_partidos(entradas, regs):
    """Camadas que abrem um pedaco de pilha de um elemento que ja tem outro pedaco embaixo e que so atuam sobre o que
    esta embaixo (ajuste, mesclagem diferente da normal, camada clipada) e tocam o que o elemento tem nos pedacos de
    baixo: compostas sozinhas, sairiam sem efeito. E a mesma conta da derivacao (elementos._partido), pelo render."""
    embaixo, saida = {}, []
    for e in entradas:
        el = e.get('elemento')
        if e['tipo'] != 'pilha':
            continue
        i, lid = e['indices'][0], e['layer_ids'][0]
        r = regs[i]
        mescla = r.get('blend') not in ('NORMAL', 'PASS_THROUGH', None)
        caixas = embaixo.setdefault(el, [])
        if caixas and r.get('ajuste'):
            saida.append({'layer_id': lid, 'elemento': el})
        elif caixas and (mescla or r.get('clipping')):
            c = r.get('caixa') or [0, 0, 0, 0]
            if any(min(c[2], b[2]) > max(c[0], b[0]) and min(c[3], b[3]) > max(c[1], b[1]) for b in caixas):
                saida.append({'layer_id': lid, 'elemento': el})
        caixas.extend(regs[k].get('caixa') or [0, 0, 0, 0] for k in e['indices'])
    return saida


def montar(pasta_job, formato):
    """(contrato, bloqueios, pede_confirmacao) do formato derivado, como desdobra.render.contrato.montar."""
    pasta = Path(pasta_job).resolve()
    d = ler_derivacao(pasta, formato)
    if d is None:
        return None, [_bloqueio('formato_sem_derivacao')], []
    if d['situacao'] != 'derivado':
        return None, [_bloqueio('formato_devolvido', motivo=d['devolucao']['motivo'])], []
    briefing = mb.ler(pasta)
    bloqueios, confirmar = [], []
    if briefing is None or mb.desatualizado(pasta, briefing):
        bloqueios.append(_bloqueio('briefing_desatualizado'))
    elif d.get('impressao_formato') is None or nd.impressao_de_agora(pasta, d, briefing) != d['impressao_formato']:
        # a impressao do formato (M7b, A2): a mudanca do briefing que nao alimenta este formato nao trava o render dele
        bloqueios.append(_bloqueio('derivacao_desatualizada'))
    if not bloqueios and not _derivacao_confere(pasta, formato, d):
        bloqueios.append(_bloqueio('derivacao_desatualizada'))
    if bloqueios:
        return None, bloqueios, confirmar
    laudo = contratos.ler(pasta / mb.ARQUIVO_LAUDO, 'laudo/1')
    camadas_laudo = mb.camadas_do_laudo(laudo)
    resolvidas, _e, _i = mb.resolver(laudo, briefing)
    elemento_de = {}
    for e in d['elementos']:
        for lid in e['layer_ids']:
            elemento_de[lid] = e
    # a funcao que o contrato da origem usa: fora da peca para tudo que nao tem elemento neste formato
    funcoes = {}
    for c in laudo['camadas']:
        lid = c['identidade']['layer_id']
        r = resolvidas.get(lid)
        if r is not None and r['funcao'] == mb.FUNCAO_FORA:
            funcoes[lid] = mb.FUNCAO_FORA
        elif lid not in elemento_de and c.get('tipo') not in mb.TIPOS_SEM_DESENHO:
            funcoes[lid] = mb.FUNCAO_FORA
    origem, bloqueios, confirmar = mc.montar(pasta, funcoes=funcoes, formato=formato)
    if origem is None:
        return None, bloqueios, confirmar
    # o master e a composicao, como o publico ve (girada nos 90 e 270 graus): o giro para o arquivo e da entrega,
    # sem reamostrar (decisoes-v1.md, 139; desdobra.entrega.codificar)
    W, H = (int(v) for v in d['formato']['composicao'])
    estrutura, _arq = mc.estrutura_do_documento(pasta, laudo)
    regs = estrutura['camadas']
    por_lid = {}
    for r in regs:
        por_lid.setdefault(r['layer_id'], r)
    # camada clipada vai com o elemento da base (o psd-tools so desenha a camada clipada junto da base)
    registros = list(origem['registros'])
    for lid, r in por_lid.items():
        base = r.get('base_do_clip') if r.get('clipping') else None
        if base is not None and lid in elemento_de and base in elemento_de and \
                elemento_de[lid]['id'] != elemento_de[base]['id']:
            registros.append({'codigo': 'camada_clipada_vai_com_o_elemento_da_base', 'layer_id': lid,
                              'medidas': {'elemento': elemento_de[lid]['id'], 'elemento_da_base': elemento_de[base]['id']}})
            elemento_de[lid] = elemento_de[base]
    entradas, mesclas = [], []
    kv = origem['origem']['kv_sha256']
    faces_do_job, fora_da_fonte = None, {}

    def nova_id():
        return 'e%02d' % (len(entradas) + 1)

    for e in origem['entradas']:
        if e['tipo'] == 'pilha':
            pedacos = []
            for i, lid in zip(e['indices'], e['layer_ids']):
                el = elemento_de.get(lid)
                if el is None:
                    continue
                if pedacos and pedacos[-1][0]['id'] == el['id']:
                    pedacos[-1][1].append(i)
                    pedacos[-1][2].append(lid)
                else:
                    pedacos.append((el, [i], [lid]))
            mesclas.extend(mesclas_sem_fundo(pedacos, regs, ja_tem_embaixo=bool(entradas)))
            for el, indices, lids in pedacos:
                entradas.append({'id': nova_id(), 'tipo': 'pilha', 'indices': indices, 'layer_ids': lids,
                                 'chave': mc._sha_texto({'kv': kv, 'indices': indices}),
                                 'elemento': el['id'], 'transformacao': el['transformacao']})
        elif e['tipo'] == 'texto':
            el = elemento_de.get(e['layer_id'])
            if el is None:
                continue
            tr = el['transformacao']
            s = float(tr['s'])
            xx, xy, yx, yy, tx, ty = e['texto']['matriz']
            nx, ny = _ponto(tr, tx, ty)
            novo = json.loads(json.dumps(e))
            novo['id'] = nova_id()
            novo['texto']['matriz'] = [xx * s, xy * s, yx * s, yy * s, nx, ny]
            ct = (camadas_laudo.get(e['layer_id']) or {}).get('geometria') or {}
            if el.get('texto_editado') is not None:
                tinta_no_formato = _caixa(tr, ct.get('caixa_tinta') or e['regiao'])
                novo = texto_editado_na_entrada(novo, el['texto_editado'], tinta_no_formato)
                if faces_do_job is None:
                    faces_do_job = mc.faces_do_job(pasta, contratos.ler(pasta / 'estado.json', 'estado/1'))
                for ch in caracteres_fora_da_face(novo, faces_do_job):
                    if ch not in fora_da_fonte.setdefault(el['id'], []):
                        fora_da_fonte[el['id']].append(ch)
                # sem caixa validada para o texto novo: a pagina e o formato inteiro, e a tinta e conferida na borda
                # dele depois de compor (tinta_fora_da_caixa)
                cv = alvo = [0, 0, W, H]
                registros.append({'codigo': 'texto_editado_desenhado', 'layer_id': e['layer_id'],
                                  'medidas': {'elemento': el['id']}})
            else:
                novo.update(quebras_da_entrada(el, e))
                # a caixa que a derivacao validou para este texto, no formato: a medida da quebra por familia, a caixa
                # do DA na mestre propria (elemento de um texto so), ou a tinta da camada no KV transformada
                cv = caixa_validada_do_texto(el, e['layer_id'], ct.get('caixa_tinta') or e['regiao'])
                alvo = regiao_da_pagina_de_texto(tr, e['regiao'], cv, W, H)
            if alvo[2] <= alvo[0] or alvo[3] <= alvo[1]:
                registros.append({'codigo': 'texto_fora_do_formato', 'layer_id': e['layer_id']})
                continue
            # a regiao da pagina cobre a caixa validada com folga: a tinta alem dela e conferida depois de compor
            # (tinta_fora_da_caixa), nunca cortada em silencio
            novo['regiao'] = alvo
            novo['caixa_validada'] = [round(v, 2) for v in cv]
            novo['corpo_dispositivo_px'] = round(float(e['corpo_dispositivo_px']) * s, 4)
            novo['sharp_pequeno'] = bool(e['antialiasing'] == 'antiAliasSharp' and
                                         novo['corpo_dispositivo_px'] <= limites.valor('render.corpo_sharp_pequeno_px'))
            novo['elemento'] = el['id']
            novo['transformacao'] = tr
            entradas.append(novo)
        elif e['tipo'] == 'linkado':
            el = elemento_de.get(e['layer_id'])
            if el is None:
                continue
            tr = el['transformacao']
            novo = dict(e, id=nova_id(), elemento=el['id'], transformacao=tr)
            if e.get('colocacao'):
                q = e['colocacao']
                pts = [_ponto(tr, q[k], q[k + 1]) for k in range(0, len(q), 2)]  # numero-neutro: pares x, y
                novo['colocacao'] = [v for p in pts for v in p]
            if e.get('caixa'):
                novo['caixa'] = [int(round(v)) for v in _caixa(tr, e['caixa'])]
            entradas.append(novo)
    if fora_da_fonte:
        return None, [_bloqueio('texto_editado_fora_da_fonte', elementos=sorted(fora_da_fonte),
                                caracteres=[c for k in sorted(fora_da_fonte) for c in fora_da_fonte[k]])], []
    partidos = _efeitos_partidos(entradas, regs)
    if partidos:
        return None, [_bloqueio('elemento_partido_no_render', camadas=partidos)], []
    if mesclas:
        confirmar.append(_bloqueio('mesclagem_sem_o_fundo_de_outro_elemento', camadas=mesclas))
    for lid in d['sem_geometria']:
        registros.append({'codigo': 'estrutura_sem_desenho_no_formato', 'layer_id': lid})
    fora = sorted(set(d['fora_da_peca']))
    contrato = dict(origem)
    contrato['formato'] = {'chave': formato, 'largura': W, 'altura': H,
                           'escala': round(W / float((d.get('mestre') or {}).get('largura') or W), 6)}
    # a impressao, e nao o sha do arquivo (que leva o carimbo): derivar de novo sem mudar o formato deixa o contrato igual
    contrato['origem'] = dict(origem['origem'], funcoes='derivacao', derivacao_impressao=d['impressao_formato'])
    contrato['entradas'] = entradas
    contrato['fora_da_peca'] = fora
    contrato['registros'] = registros
    return contrato, [], confirmar
