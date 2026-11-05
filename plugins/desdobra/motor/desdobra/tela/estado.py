# -*- coding: utf-8 -*-
"""O que a tela so de leitura mostra (M7a2 e M7a3): os passos, as abas, o palco de cada composicao, as faces e os
assets do job.

  - lido (passo 1, "O que eu li"): bloqueios das fases e das camadas, linkados, valores de spec por situacao, modo de
    dados e fontes (decisoes-v1.md n 161);
  - funcoes (passo 2, "Funcoes"): a arvore dos grupos do laudo com a funcao resolvida de cada camada e de onde ela vem
    (da propria camada, herdada do grupo ou pela regra da decisao 10; briefing.modelo.resolver), o resumo das regras e
    das ancoras por funcao e o palco do KV, no centro;
  - abas: orientacao da composicao (escala.orientacao, banda derivacao.quadrado_ln_max) e, dentro dela, os grupos
    de composicoes de proporcao parecida (revisao da 163 em 05/11: lado longo sobre lado curto, amplitude ate
    derivacao.grupo_proporcao_dif_max, por ligacao completa), qualquer que seja a familia da derivacao (a mestre que
    ela escolheu, ou SEM_FAMILIA para o formato que volta ao DA, fica como dado da composicao). Cada composicao
    (largura x altura depois do giro) lista os formatos que ela gera, com o giro, e marca a escala pura (o caminho
    transform da derivacao: mesma proporcao da mestre);
  - previas: o palco de cada formato (palco), montado da derivacao do motor em memoria (derivacao.nucleo.preparar e
    derivar_em_memoria), nada gravado. Cada camada do elemento vira uma peca, na transformacao do elemento
    (destino + (caixa - origem) * s) e no recorte dele: a imagem da camada pelo asset por id, ou o texto com a face do
    job (casamento.casar do nome PostScript do trecho). A tinta do texto e medida no Chromium (tela.js), nunca aqui;
  - fantasmas (n 162, opcao A): elemento sem regra, e todo elemento do KV num formato devolvido, aparece hachurado na
    escala pura da mestre (contain, centrado), com o selo "apoio de desenho, nao gravado". O fantasma e so desenho:
    nao tem regra nem ancora inventada e nunca vai a arquivo nenhum;
  - galeria (n 164 e notas de 05/11): o formato devolvido (troca de orientacao ou proporcao fora da faixa) chega com
    as variantes da galeria do motor (derivacao.galeria.variantes), cada uma com o palco dela no mesmo modelo das
    pecas; no grupo de proporcao com mais de um devolvido, cada variante leva a mesma estrutura a todos os membros
    (variante_para_grupo). So previa: nada gravado, e o que o derivar grava nao muda;
  - faltam: a lista unica do que falta, cada item com o lugar da tela que leva a ele (so leitura no M7a0);
  - fontes: as faces do job (fontes/bruto/<sha>/leitura.json e entrada/fontes/), com os bytes como a conferencia as
    serve ao Chromium (a face de um .ttc emendada, conferencia.bytes_para_servir). O processo nunca abre a fonte: so
    copia bytes;
  - assets: o PNG dos pixels proprios de cada camada (laudo/bruto/<sha>/estrutura.json, pixels.asset_sha256, em
    laudo/assets/), com id a001, a002... por sha256, lidos como bytes e nunca decodificados.

Nada daqui vai ao Claude: o conteudo so sai pelo servidor da tela (desdobra.tela.servidor) para o Chromium que o
motor abre. Texto do cliente (nome de camada, texto do PSD, nome de fonte) vai como dado; a pagina o poe so por
textContent.
"""
import math
import re
from pathlib import Path

from desdobra import limites
from desdobra.derivacao import escala
from desdobra.resultado import Codigo

ESQUEMA = 'tela-estado/1'
SEM_FAMILIA = 'sem_familia'
ORIENTACOES = ('horizontal', 'quadrado', 'vertical')
ROTULOS = {'horizontal': 'Horizontal', 'quadrado': 'Quadrado', 'vertical': 'Vertical', SEM_FAMILIA: 'Sem proposta ainda',
           'kv': 'Mestre do KV'}
ASSINATURA_PNG = bytes([137, 80, 78, 71, 13, 10, 26, 10])  # numero-neutro: assinatura do PNG
COR = re.compile(r'^#[0-9A-Fa-f]{6}$')
SEPARADOR_DE_LINHA = re.compile('[\r\n\x03]')  # fim de paragrafo (\r) e quebra manual (\x03) do texto do PSD
ALINHAMENTOS = {'LEFT': 'esquerda', 'CENTER': 'centro', 'RIGHT': 'direita'}
POR = {'camada': 'camada', 'grupo': 'grupo', 'decisao_10': 'decisao_10'}
# O que a tela diz do formato que a derivacao devolve, em lugar do o_que_fazer do motor: o DA nunca e chamado a
# desenhar uma mestre por orientacao (n 164 e comentarios de 05/11), e o texto da tela nao leva identificador do motor.
PROPOSTA_DEPOIS = 'A proposta do motor para esta composição chega com a galeria de variantes, na próxima versão.'
SEM_VERSOES = 'O motor não conseguiu montar versões para esta composição.'
SELO_VARIANTE = 'variante'
MOTIVOS_TELA = {
    'troca_forte_de_orientacao': 'A orientação muda em relação ao KV.',
    'troca_de_orientacao_quadrado': 'A peça passa para o quadrado, ou sai dele, em relação ao KV.',
    'fora_da_faixa_de_familia': 'A proporção fica longe da proporção do KV.',
}
MOTIVO_GERAL = 'O motor ainda não chegou a uma proposta para este formato.'


def _versoes(n):
    return '%d versão' % n if n == 1 else '%d versões' % n


def texto_da_devolucao(motivo, variantes=None):
    """A frase da tela para o formato devolvido, sem identificador do motor e sem pedir mestre propria. variantes:
    quantas a galeria montou (None: a galeria nao foi montada)."""
    if variantes:
        depois = 'O motor montou %s com os blocos do próprio KV.' % _versoes(variantes)  # a nota da galeria pede a escolha
    elif variantes is None:
        depois = PROPOSTA_DEPOIS
    else:
        depois = SEM_VERSOES
    if motivo in MOTIVOS_TELA:
        return MOTIVOS_TELA[motivo] + ' ' + depois
    return MOTIVO_GERAL if variantes is None else MOTIVO_GERAL + ' ' + depois


class ErroTela(Exception):
    def __init__(self, mensagem, motivo):
        super().__init__(mensagem)
        self.motivo = motivo


# ------------------------------------------------------------------ abas
def _rotulo_familia(fam, mestre):
    if fam in ROTULOS:
        return ROTULOS[fam]
    if (mestre or {}).get('tipo') == 'propria':
        return 'Mestre própria'
    return fam


def proporcao(largura, altura):
    """Lado longo sobre lado curto: a mesma medida nas duas orientacoes (decisoes-v1.md, revisao da 163 em 05/11)."""
    return max(largura, altura) / float(min(largura, altura))


def agrupar_por_proporcao(composicoes):
    """Grupos de composicoes de proporcao parecida, dentro de uma orientacao (revisao da 163 em 05/11): ligacao
    completa, a diferenca entre a maior e a menor proporcao do grupo ate derivacao.grupo_proporcao_dif_max. Em uma
    dimensao a ligacao completa so junta vizinhos: as composicoes vao em ordem de proporcao (e de id, no empate) e, a
    cada passo, junta-se o par vizinho de menor amplitude (o primeiro, no empate) enquanto ela couber no limite. A
    cadeia nao passa: 2,0 e 2,2 juntam, 2,2 e 2,4 tambem cabem, mas os tres nao. Devolve listas na ordem da entrada
    ordenada; a amplitude vai nas casas do estado da tela (_arred), para o empate nao depender do float."""
    limite = float(limites.valor('derivacao.grupo_proporcao_dif_max'))
    itens = sorted(composicoes, key=lambda c: (proporcao(c['largura'], c['altura']), c['id']))
    grupos = [[c] for c in itens]

    def amplitude(g):
        ps = [proporcao(c['largura'], c['altura']) for c in g]
        return _arred(max(ps) - min(ps))
    while len(grupos) > 1:
        melhor = min(range(len(grupos) - 1), key=lambda i: (amplitude(grupos[i] + grupos[i + 1]), i))
        if amplitude(grupos[melhor] + grupos[melhor + 1]) > limite:
            break
        grupos[melhor:melhor + 2] = [grupos[melhor] + grupos[melhor + 1]]
    return grupos


def abas(laudo, briefing, formatos, variantes=None):
    """[{'id', 'rotulo', 'grupos': [{'id', 'proporcao': [menor, maior], 'escala_pura', 'composicoes': [{'id',
    'largura', 'altura', 'proporcao', 'escala_pura', 'familia', 'rotulo_familia', 'formatos': [...]}]}]}] na ordem
    horizontal, quadrado, vertical. Dentro da orientacao, as composicoes de proporcao parecida formam um grupo (uma aba
    da tela; agrupar_por_proporcao), qualquer que seja a familia da derivacao: a faixa de familia deixa de separar o
    que a tela agrupa (n 163). formatos: {id: derivacao/1}; variantes: {id: quantas variantes a galeria montou}."""
    variantes = variantes or {}
    ordem_briefing = [f['id'] for f in briefing['formatos']]
    por_ori = {}
    for fid in ordem_briefing:
        d = formatos.get(fid)
        if d is None:
            continue
        W, H = d['formato']['composicao']
        ori = escala.orientacao(W, H)
        fam = (d.get('mestre') or {}).get('id') if d['situacao'] == 'derivado' else None
        fam = fam or SEM_FAMILIA
        comp_id = 'c%dx%d-%s' % (W, H, fam)
        mestre = d.get('mestre') if fam != SEM_FAMILIA else None
        comps = por_ori.setdefault(ori, {})
        c = comps.setdefault(comp_id, {'id': comp_id, 'largura': int(W), 'altura': int(H),
                                       'proporcao': _arred(proporcao(W, H)), 'escala_pura': False, 'familia': fam,
                                       'rotulo_familia': _rotulo_familia(fam, mestre), 'formatos': []})
        if d.get('caminho') == 'transform':
            c['escala_pura'] = True
        c['formatos'].append({'id': fid, 'largura': d['formato']['largura'], 'altura': d['formato']['altura'],
                              'rotacao_graus': ((d['formato'].get('rotacao') or {}).get('graus')) or 0,
                              'situacao': d['situacao'], 'caminho': d.get('caminho'),
                              'motivo': (d.get('devolucao') or {}).get('motivo'),
                              'variantes': int(variantes.get(fid, 0))})
    saida = []
    for ori in ORIENTACOES:
        if ori not in por_ori:
            continue
        grupos = []
        for membros in agrupar_por_proporcao(list(por_ori[ori].values())):
            membros = sorted(membros, key=lambda c: (-c['largura'] / c['altura'], c['id']))
            ps = [c['proporcao'] for c in membros]
            grupos.append({'proporcao': [min(ps), max(ps)], 'escala_pura': all(c['escala_pura'] for c in membros),
                           'composicoes': membros})
        grupos.sort(key=lambda g: (-g['composicoes'][0]['largura'] / g['composicoes'][0]['altura'],
                                   g['composicoes'][0]['id']))
        for n, g in enumerate(grupos, 1):
            g['id'] = '%s-%d' % (ori, n)
        saida.append({'id': ori, 'rotulo': ROTULOS[ori], 'grupos': [dict({'id': g.pop('id')}, **g) for g in grupos]})
    return saida


# ------------------------------------------------------------------ pecas do palco
def _arred(v):
    return round(float(v), 4)  # numero-neutro: casas decimais do pixel no estado da tela


def _mapear(caixa, tr):
    """Caixa do documento para a composicao: destino + (caixa - origem) * s."""
    s, (ox, oy), (dx, dy) = float(tr['s']), tr['origem_doc'], tr['destino']
    return [_arred(dx + (caixa[0] - ox) * s), _arred(dy + (caixa[1] - oy) * s), _arred(dx + (caixa[2] - ox) * s),
            _arred(dy + (caixa[3] - oy) * s)]


def _linhas(texto, face_de, juntar=(), inserir=()):
    """Linhas do texto do PSD como o render as monta (render.texto.linhas_da_camada: quebras gravadas, as juntadas
    pela familia do formato e as inseridas na mestre propria), cada uma com os trechos de estilo dela (texto, face,
    cor, corpo, tracking) e a entrelinha da linha no documento (a distancia da linha de base da anterior, a mesma do
    render: o fator do paragrafo vezes o corpo na automatica, a do trecho na fixa, vezes a escala da matriz). None
    quando o laudo nao traz o texto dos trechos."""
    from desdobra.render import texto as rt
    texto = texto or {}
    runs = texto.get('runs') or []
    if not runs or any(not isinstance(r.get('texto'), str) or not isinstance(r.get('inicio'), int) for r in runs):
        return None
    m = texto.get('matriz') or [1.0, 0.0, 0.0, 1.0]
    sy = math.hypot(float(m[2]), float(m[3]))
    linhas = []
    for ln in rt.linhas_da_camada(texto, quebras=inserir, juntar=juntar):
        trechos = []
        for parte, r in ln['pedacos']:
            cor = r.get('cor_hex') if isinstance(r.get('cor_hex'), str) and COR.match(r.get('cor_hex')) else None
            trechos.append({'texto': parte, 'fonte_ps': r.get('fonte_ps'), 'face': face_de(r.get('fonte_ps')),
                            'cor': cor, 'corpo': r.get('corpo_efetivo'), 'tracking': r.get('tracking') or 0})
        linhas.append({'trechos': trechos, 'entrelinha': _arred(ln['entrelinha'] * sy) if ln['entrelinha'] else None})
    while linhas and not linhas[-1]['trechos']:
        linhas.pop()
    return linhas or None


def pecas_base(laudo, asset_por_camada, face_de):
    """{layer_id: peca no documento} de cada camada desenhavel: 'imagem' (asset por id), 'texto' (linhas com a face
    de cada trecho; sem face para algum trecho, a peca usa a imagem da camada e lista o que falta) ou 'sem_imagem'
    (a caixa so, quando o laudo nao tem pixels da camada)."""
    from desdobra.briefing import modelo as mb
    from desdobra.render import contrato as mc
    doc = laudo.get('documento') or {}
    base = {}
    for ordem, c in enumerate(laudo['camadas']):
        if not mb.desenhavel(c):
            continue
        lid = c['identidade']['layer_id']
        geo = c.get('geometria') or {}
        caixa = geo.get('caixa')
        if not caixa:
            continue
        ap = c.get('aparencia') or {}
        opacidade = ap.get('opacidade')
        peca = {'camada': lid, 'nome': c.get('nome') or '', 'ordem': ordem, 'caixa': [float(x) for x in caixa],
                'opacidade': None if opacidade is None else _arred(opacidade / 255.0),  # numero-neutro: opacidade de 8 bits
                'asset': asset_por_camada.get(lid), 'faltando': []}
        linhas = _linhas(c.get('texto'), face_de) if c.get('tipo') == 'texto' else None
        if linhas is not None:
            faltando = sorted({t['fonte_ps'] or '' for ln in linhas for t in ln['trechos'] if t['face'] is None})
            par = ((c.get('texto') or {}).get('paragrafos') or [{}])[0]
            tinta = [float(x) for x in (geo.get('caixa_tinta') or caixa)]
            regiao = None
            if doc.get('largura') and doc.get('altura'):
                regiao = mc.regiao_do_texto(geo, int(doc['largura']), int(doc['altura']))
            peca.update(linhas=linhas, faltando=faltando, alinhamento=ALINHAMENTOS.get(par.get('justificacao'), 'esquerda'),
                        caixa_tinta=tinta, _texto=c.get('texto'), _regiao=regiao or tinta,
                        _faces={t['fonte_ps']: t['face'] for ln in linhas for t in ln['trechos']})
            peca['tipo'] = 'texto'
            peca['modo'] = 'texto' if not faltando else ('imagem' if peca['asset'] else 'texto')
        else:
            peca['tipo'] = 'imagem' if peca['asset'] else 'sem_imagem'
        base[lid] = peca
    return base


def _peca_no_formato(peca, tr, el, W, H):
    """A peca no formato: caixa e recorte pela transformacao do elemento. O texto leva as quebras do elemento no
    formato e o recorte e a regiao da pagina do texto no render (a caixa validada com folga), nunca o recorte do
    elemento: o render nao corta o texto ali."""
    from desdobra.derivacao import quebras as mq
    from desdobra.render import derivado as rd
    s = float(tr['s'])
    p = {k: v for k, v in peca.items() if k not in ('caixa', 'caixa_tinta', 'linhas') and not k.startswith('_')}
    p['elemento'] = el['id']
    p['caixa'] = _mapear(peca['caixa'], tr)
    p['recorte'] = _mapear(tr['recorte_doc'], tr)
    if 'linhas' in peca:
        lid = peca['camada']
        alvo = dict(el, transformacao=tr)
        q = el.get('quebras')
        linhas = peca['linhas']

        def face_de(ps):
            return peca['_faces'].get(ps)
        fam = next((x for x in (q.get('familia') or []) if x['layer_id'] == lid), None) if isinstance(q, dict) else None
        if fam is not None:
            linhas = _linhas(peca['_texto'], face_de, juntar=mq.juntadas({'texto': peca['_texto']}, fam['aprovadas']))
        elif isinstance(q, list) and el.get('quebras_camada') == lid:
            linhas = _linhas(peca['_texto'], face_de, inserir=q)
        cv = rd.caixa_validada_do_texto(alvo, lid, peca['caixa_tinta'])
        p['caixa_tinta'] = _mapear(peca['caixa_tinta'], tr)
        p['caixa_validada'] = [_arred(x) for x in cv]
        regiao = rd.regiao_da_pagina_de_texto(tr, peca['_regiao'], cv, int(W), int(H))
        if regiao[2] > regiao[0] and regiao[3] > regiao[1]:  # fora do formato, o texto fica no recorte do elemento
            p['recorte'] = [float(x) for x in regiao]
        p['linhas'] = [{'trechos': [dict(t, corpo=None if t['corpo'] is None else _arred(t['corpo'] * s)) for t in ln['trechos']],
                        'entrelinha': None if ln['entrelinha'] is None else _arred(ln['entrelinha'] * s)}
                       for ln in linhas or []]
    return p


def escala_pura(kv, W, H):
    """Transformacao da escala pura da mestre na composicao W x H: contain, centrado (n 162: onde o fantasma fica)."""
    x0, y0, x1, y1 = kv['canvas_doc']
    Wm, Hm = x1 - x0, y1 - y0
    s = min(W / Wm, H / Hm)
    return {'s': s, 'origem_doc': [x0, y0], 'destino': [(W - Wm * s) / 2.0, (H - Hm * s) / 2.0],  # numero-neutro: centro
            'recorte_doc': [x0, y0, x1, y1]}


def _identidade(kv):
    x0, y0, x1, y1 = kv['canvas_doc']
    return {'s': 1.0, 'origem_doc': [x0, y0], 'destino': [0.0, 0.0], 'recorte_doc': [x0, y0, x1, y1]}


def _montar_palco(formato, W, H, itens, base, selo, caminho, situacao, devolucao, nomes):
    """itens: [(elemento, transformacao, caixa na composicao, fantasma)]."""
    elementos, pecas = [], []
    for el, tr, caixa, fantasma in itens:
        elementos.append({'id': el['id'], 'raiz': el.get('raiz'), 'nome': nomes.get(el.get('raiz'), ''),
                          'funcao': el.get('funcao'), 'regra': el.get('regra'),
                          'ancora': list(el['ancora']) if el.get('ancora') and el.get('regra') is not None else None,
                          'origem_funcao': el.get('origem_funcao'), 'fantasma': bool(fantasma),
                          'escala': _arred(tr['s']), 'caixa': [_arred(x) for x in caixa],
                          'recorte': _mapear(tr['recorte_doc'], tr)})
        for lid in el.get('layer_ids') or []:
            if lid in base:
                p = _peca_no_formato(base[lid], tr, {'id': el['id']} if fantasma else el, W, H)  # fantasma: as quebras da mestre
                p['fantasma'] = bool(fantasma)
                pecas.append(p)
    pecas.sort(key=lambda p: p['ordem'])
    mundo = [0.0, 0.0, float(W), float(H)]
    for p in pecas:
        c, r = p['caixa'], p['recorte']
        vis = [max(c[0], r[0]), max(c[1], r[1]), min(c[2], r[2]), min(c[3], r[3])]
        if vis[2] > vis[0] and vis[3] > vis[1]:
            mundo = [min(mundo[0], vis[0]), min(mundo[1], vis[1]), max(mundo[2], vis[2]), max(mundo[3], vis[3])]
    return {'formato': formato, 'largura': int(W), 'altura': int(H), 'caminho': caminho, 'situacao': situacao,
            'selo': selo, 'devolucao': devolucao, 'elementos': elementos, 'pecas': pecas,
            'mundo': [_arred(x) for x in mundo], 'fora_do_quadro': mundo != [0.0, 0.0, float(W), float(H)]}


def _nomes(laudo):
    return {c['identidade']['layer_id']: c.get('nome') or '' for c in laudo['camadas']}


def palco(d, kv, laudo, base):
    """Palco de um formato (derivacao/1 em memoria): pecas, elementos, selo e devolucao."""
    W, H = d['formato']['composicao']
    por_kv = {e['id']: e for e in kv['elementos']}
    pura = escala_pura(kv, W, H)
    itens = []
    if d['situacao'] == 'derivado':
        for el in d['elementos']:
            if el.get('regra') is None:
                ek = por_kv.get(el['id'], el)
                itens.append((el, pura, _mapear(ek.get('caixa_doc') or el['caixa_mestre'], pura), True))
            else:
                itens.append((el, el['transformacao'], el['caixa'], False))
        selo = 'escala_pura' if d.get('caminho') == 'transform' else 'proposta'
        devolucao = None
    else:
        for ek in kv['elementos']:
            itens.append((ek, pura, _mapear(ek['caixa_doc'], pura), True))
        selo = 'devolvido'
        dv = d.get('devolucao') or {}
        devolucao = {'motivo': dv.get('motivo'), 'o_que_fazer': dv.get('o_que_fazer'),
                     'texto': texto_da_devolucao(dv.get('motivo'))}
    return _montar_palco(d['formato']['id'], W, H, itens, base, selo, d.get('caminho'), d['situacao'], devolucao,
                         _nomes(laudo))


def palco_kv(kv, laudo, base):
    """Palco da mestre do KV, como a derivacao a ve (o canvas da mestre, sem transformacao)."""
    tr = _identidade(kv)
    itens = [(ek, tr, _mapear(ek['caixa_doc'], tr), ek.get('regra') is None) for ek in kv['elementos']]
    return _montar_palco(None, kv['largura'], kv['altura'], itens, base, 'kv', None, 'mestre', None, _nomes(laudo))


# ------------------------------------------------------------------ galeria (so previa)
def palco_da_variante(formato, W, H, v, laudo, base):
    """O palco de uma variante da galeria: os elementos dela (na forma dos elementos da derivacao) no mesmo modelo de
    pecas do palco, sem fantasma (a variante posiciona todo elemento do KV)."""
    itens = [(el, el['transformacao'], el['caixa'], False) for el in v['elementos']]
    return _montar_palco(formato, W, H, itens, base, SELO_VARIANTE, None, 'variante', None, _nomes(laudo))


def _variante_da_tela(v, ordem, palco_):
    """A variante como a tela a mostra: a frase do DA, os avisos e as falhas (codigo e texto em portugues) e o palco.
    O codigo so serve a tela para escolher a marca; nunca vai ao texto da moldura."""
    est = v.get('estrutura') or {}
    return {'id': v['id'], 'ordem': ordem, 'descricao': v['descricao'],
            'avisos': [{'codigo': a['codigo'], 'texto': a['texto']} for a in v['avisos']],
            'falhas': [{'codigo': f['codigo'], 'texto': f['texto']} for f in v['falhas_obrigatorias']],
            'estrutura': {'tipo': est.get('tipo'), 'trilhas': list(est.get('trilhas') or [])},
            'palco': palco_}


def galerias(ctx, kv, laudo, base, derivados, orientacoes, *, specs, arquivo_specs, params):
    """{id do formato devolvido: {'grupo': [ids], 'variantes': [...]}} para cada grupo de proporcao da tela
    (orientacoes, de abas) com formato devolvido. As variantes vem da galeria do motor no primeiro devolvido do grupo
    (derivacao.galeria.variantes); com mais de um devolvido no grupo, cada variante vai a todos pela estrutura que
    deixa o pior membro melhor (variante_para_grupo). Quando nenhuma estrutura serve ao grupo, cada membro fica com a
    variante de mesmo id da galeria dele; o numero da versao e sempre o do primeiro membro, para Versao N ser a mesma
    variante em todo o grupo. O membro sem nenhuma variante ganha a galeria dele sozinho. So previa, em memoria."""
    from desdobra.derivacao import galeria as mg
    por_id = {f['id']: f for f in ctx['briefing']['formatos']}
    kw = {'specs': specs, 'arquivo_specs': arquivo_specs, 'params': params}
    saida = {}
    for o in orientacoes:
        for g in o['grupos']:
            fids = [x['id'] for c in g['composicoes'] for x in c['formatos'] if x['situacao'] == 'devolvido']
            if not fids:
                continue
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
                        membros = mg.variante_para_grupo(ctx, kv, [por_id[f] for f in fids], v['id'], **kw)['membros']
                    except ValueError:  # nenhuma estrutura da variante serve a todos: cada um com a dele, de mesmo id
                        for fid in fids[1:]:
                            mv = propria(fid, v['id'])
                            if mv is not None:
                                membros[fid] = mv
                for fid, mv in membros.items():
                    por_formato[fid].append((n, mv))
            for fid in fids:
                pares = por_formato[fid] or list(enumerate(mg.variantes(ctx, kv, por_id[fid], **kw), 1))
                W, H = derivados[fid]['formato']['composicao']
                saida[fid] = {'grupo': list(fids),
                              'variantes': [_variante_da_tela(v, n, palco_da_variante(fid, W, H, v, laudo, base))
                                            for n, v in pares]}
    return saida


# ------------------------------------------------------------------ passos 1 e 2
def arvore(laudo, briefing, resolvidas, quadro):
    """Arvore dos grupos e camadas da peca, do topo do painel para baixo: [{'camada', 'nome', 'tipo', 'funcao',
    'por', 'raiz', 'propria', 'observacao', 'filhos'}]."""
    from desdobra.briefing import modelo as mb
    camadas = mb.camadas_do_laudo(laudo)
    dadas = {i['layer_id']: i for i in briefing['funcoes'] if mb._decisao_valida(i['funcao'])}
    usados = set()
    for lid, c in camadas.items():
        if mb.desenhavel(c) and mb.no_escopo(c, quadro):
            usados.add(lid)
            usados.update(c.get('caminho_ids') or [])
    nos = {}
    for lid in usados:
        c = camadas.get(lid)
        if c is None:
            continue
        if lid in resolvidas:
            r = resolvidas[lid]
            funcao, por, raiz, obs = r['funcao'], POR.get(r['por']), r['raiz'], r.get('observacao')
        else:
            cadeia = [lid] + list(reversed(c.get('caminho_ids') or []))
            achou = next((x for x in cadeia if x in dadas), None)
            funcao = dadas[achou]['funcao']['valor'] if achou is not None else None
            por = None if achou is None else ('camada' if achou == lid else 'grupo')
            raiz, obs = achou, (dadas[achou].get('observacao') if achou is not None else None)
        nos[lid] = {'camada': lid, 'nome': c.get('nome') or '', 'tipo': c.get('tipo'), 'funcao': funcao, 'por': por,
                    'raiz': raiz, 'nome_raiz': (camadas.get(raiz) or {}).get('nome') or '' if raiz is not None else '',
                    'propria': dadas[lid]['funcao']['valor'] if lid in dadas else None, 'observacao': obs,
                    'visivel': bool((c.get('aparencia') or {}).get('visivel_efetiva')), 'filhos': []}
    raizes = []
    for c in reversed(laudo['camadas']):  # o painel do Photoshop: de cima para baixo
        lid = c['identidade']['layer_id']
        if lid not in nos:
            continue
        pai = c.get('pai_id')
        (nos[pai]['filhos'] if pai in nos else raizes).append(nos[lid])
    return raizes


def resumo_das_funcoes(briefing, resolvidas):
    """Regra e ancora de cada funcao usada (o resumo so de leitura do que o briefing decide; n 161)."""
    from desdobra.briefing import modelo as mb
    regras = mb.regras_por_funcao(briefing)
    ancoras, por_elemento = {}, {}
    for a in briefing.get('ancoras') or []:
        if not (mb._decisao_valida(a.get('x')) and mb._decisao_valida(a.get('y'))):
            continue
        if a.get('funcao'):
            ancoras[a['funcao']] = [a['x']['valor'], a['y']['valor']]
        elif a.get('layer_id') in resolvidas:  # ancora por elemento (layer_id da raiz), que vale sobre a da funcao
            f = resolvidas[a['layer_id']]['funcao']
            por_elemento[f] = por_elemento.get(f, 0) + 1
    contagem = {}
    for r in resolvidas.values():
        contagem[r['funcao']] = contagem.get(r['funcao'], 0) + 1
    return [{'funcao': f, 'regra': regras.get(f), 'ancora': ancoras.get(f), 'ancoras_por_elemento': por_elemento.get(f, 0),
             'camadas': n}
            for f, n in sorted(contagem.items())]


def _ler(arq, esquema):
    from desdobra import contratos
    try:
        return contratos.ler(arq, esquema) if Path(arq).is_file() else None
    except (contratos.ErroContrato, OSError, ValueError):
        return None


def descricao_da_fase(fid):
    """O nome da fase para a tela (a descricao da esteira), nunca o id cru do motor."""
    from desdobra.job import fases as mod_fases
    for f in mod_fases.ESTEIRA:
        if f.id == fid:
            return f.descricao
    return str(fid).replace('_', ' ')


def lido(pasta, estado_job, laudo, briefing, formatos, faces_servidas):
    """Passo 1: o que o motor leu do job (so leitura)."""
    from desdobra.job import fases as mod_fases
    from desdobra.job import nucleo
    from desdobra.render import contrato as mod_contrato
    from desdobra.specs import confirmar as mod_confirmar
    from desdobra.specs import modelo as mod_specs
    pasta = Path(pasta)
    avaliacao, _d = nucleo.avaliar(pasta, estado_job, mod_fases.ESTEIRA)
    bloqueios = [{'fase': fid, 'descricao': descricao_da_fase(fid), 'o_que_fazer': b.get('o_que_fazer') or ''}
                 for fid, b in nucleo.bloqueios_pendentes(estado_job, avaliacao, mod_fases.ESTEIRA)]
    camadas_bloqueadas = [{'camada': c['identidade']['layer_id'], 'nome': c.get('nome') or '',
                           'motivos': [m.get('descricao') or m.get('regra') for m in c.get('motivos') or []]}
                          for c in laudo['camadas'] if c.get('situacao') == 'bloqueante']
    confirmados = _ler(pasta / mod_contrato.ARQUIVO_LINKADOS, mod_contrato.ESQUEMA_LINKADOS) or {'linkados': []}
    ids_confirmados = {x['unique_id'] for x in confirmados['linkados']}
    linkados = [{'camada': c['identidade']['layer_id'], 'nome': c.get('nome') or '',
                 'confirmado': (c.get('smart_object') or {}).get('unique_id') in ids_confirmados}
                for c in laudo['camadas'] if c.get('tipo') == 'smart_linkado']
    doc = _ler(pasta / 'specs' / 'rascunho.json', 'spec/1')
    specs = {'confirmados': 0, 'rascunhos': 0, 'divergentes': 0, 'registros': 0, 'pendentes': 0, 'tem_rascunho': doc
             is not None}
    if doc is not None:
        for _r, _campo, v in mod_specs.todos_os_valores(doc):
            if v['situacao'] == 'confirmado':
                specs['confirmados'] += 1
            elif v['situacao'] == 'registro':
                specs['registros'] += 1
            elif v.get('leituras') and v['valor'] is None:
                specs['divergentes'] += 1
            else:
                specs['rascunhos'] += 1
        specs['pendentes'] = len(mod_confirmar.pendencias(doc))
    specs['formatos'] = [{'id': f['id'], 'chave': f.get('chave'), 'sem_folha': bool(f.get('sem_folha')),
                          'tem_spec': bool(((formatos.get(f['id']) or {}).get('formato') or {}).get('tem_spec'))}
                         for f in briefing['formatos']]
    lf = _ler(pasta / 'laudo' / 'laudo-fontes.json', 'laudo/1')
    usadas = (lf or laudo).get('fontes_usadas') or []
    return {'bloqueios': bloqueios, 'camadas_bloqueadas': camadas_bloqueadas, 'linkados': linkados, 'specs': specs,
            'modo_dados': {'job': estado_job.get('modo_dados'), 'teto': estado_job.get('teto_modo_dados'),
                           'briefing': (briefing.get('modo_dados') or {}).get('valor')},
            'fontes': faces_servidas,
            'fontes_que_faltam': [{'fonte_ps': u['fonte_ps'], 'situacao': u['situacao'], 'camadas': len(u['camadas'])}
                                  for u in usadas if u.get('situacao') in ('ausente', 'divergente')]}


def faltam(lido_, formatos, variantes=None):
    """A lista unica do que falta, cada item com o lugar da tela que leva a ele. variantes: {id do formato: quantas
    variantes a galeria montou}; o formato devolvido com versoes pede a escolha de uma."""
    variantes = variantes or {}
    itens = []
    for b in lido_['bloqueios']:
        itens.append({'texto': b['o_que_fazer'] or 'Uma fase do job terminou com bloqueio.', 'detalhe': b['descricao'],
                      'ir': {'passo': 'lido'}})
    for c in lido_['camadas_bloqueadas']:
        itens.append({'texto': 'Uma camada do PSD não pôde ser lida.', 'detalhe': c['nome'], 'ir': {'passo': 'lido'}})
    for x in lido_['linkados']:
        if not x['confirmado']:
            itens.append({'texto': 'Um linkado espera a confirmação do arquivo.', 'detalhe': x['nome'],
                          'ir': {'passo': 'lido'}})
    if lido_['specs']['pendentes']:
        itens.append({'texto': 'Há valores de spec que esperam a sua confirmação.',
                      'detalhe': str(lido_['specs']['pendentes']), 'ir': {'passo': 'lido'}})
    for f in lido_['fontes_que_faltam']:
        itens.append({'texto': 'Uma fonte do PSD falta ou não confere com o arquivo enviado.', 'detalhe': f['fonte_ps'],
                      'ir': {'passo': 'lido'}})
    for fid, d in formatos.items():
        if d['situacao'] == 'devolvido':
            motivo = (d.get('devolucao') or {}).get('motivo')
            inicio = 'Escolha uma das versões do motor. ' if variantes.get(fid) else 'Sem proposta do motor. '
            itens.append({'texto': inicio + MOTIVOS_TELA.get(motivo, MOTIVO_GERAL),
                          'detalhe': fid, 'ir': {'passo': 'pecas', 'formato': fid}})
    return itens


# ------------------------------------------------------------------ fontes e assets
def fontes_do_job(pasta, estado_job):
    """({id: (bytes, mime)} das faces servidas, a lista para o estado [{'id', 'sha256', 'formato', 'familia_css',
    'familia', 'estilo', 'nome_ps'}], as faces de casamento.montar_faces que sao servidas)."""
    import hashlib

    from desdobra import arquivos, contratos
    from desdobra.chromium import servidor
    from desdobra.fontes import casamento, conferencia
    from desdobra.tela import estatico
    leituras, por_sha = [], {}
    for rel, reg in sorted((estado_job.get('entradas') or {}).items()):
        if not rel.startswith(conferencia.PASTA_ENTRADA):
            continue
        arq = Path(pasta) / 'fontes' / 'bruto' / reg['sha256'] / 'leitura.json'
        if arq.is_file():
            leitura = contratos.ler(arq, 'leitura-fonte/1')
            if leitura.get('situacao') == 'lida':
                leituras.append((reg['sha256'], leitura))
                por_sha[reg['sha256']] = rel
    servidos, lista, faces = {}, [], []
    for f in casamento.montar_faces(leituras):
        rel = por_sha.get(f['sha256'])
        dados = (Path(pasta) / rel).read_bytes() if rel else None
        if dados is None or arquivos.sha256_bytes(dados) != f['sha256']:
            continue
        servir = conferencia.bytes_para_servir(dados, f)
        if servir is None:
            continue
        servidos[f['id']] = (servir, servidor.MIME_POR_FORMATO[f['formato']])
        faces.append(f)
        lista.append({'id': f['id'], 'sha256': hashlib.sha256(servir).hexdigest(), 'formato': f['formato'],
                      'familia_css': estatico.familia_css(f['id']), 'familia': f.get('familia'),
                      'estilo': f.get('estilo'), 'nome_ps': f.get('nome_ps')})
    return servidos, lista, faces


def assets_das_camadas(pasta, laudo):
    """({id: (bytes, 'image/png')}, {layer_id: id}): o PNG dos pixels proprios de cada camada do KV, pelo
    pixels.asset_sha256 da estrutura/1 do leitor; um id por sha256, na ordem das camadas. Bytes conferidos pelo
    sha256 e pela assinatura do PNG, nunca decodificados."""
    from desdobra import arquivos
    sha_kv = laudo['origem']['sha256']
    estrutura = Path(pasta) / 'laudo' / 'bruto' / sha_kv / 'estrutura.json'
    try:
        regs = arquivos.ler_json(estrutura).get('camadas') or [] if estrutura.is_file() else []
    except (OSError, ValueError):
        regs = []
    por_id = {}
    for r in regs:
        sha = (r.get('pixels') or {}).get('asset_sha256')
        if isinstance(r.get('layer_id'), int) and isinstance(sha, str) and re.match(r'^[0-9a-f]{64}$', sha):
            por_id[r['layer_id']] = sha
    servidos, por_sha, por_camada = {}, {}, {}
    for c in laudo['camadas']:
        lid = c['identidade']['layer_id']
        sha = por_id.get(lid)
        if sha is None:
            continue
        if sha not in por_sha:
            arq = Path(pasta) / 'laudo' / 'assets' / ('%s.png' % sha)
            try:
                dados = arq.read_bytes()
            except OSError:
                continue
            if not dados.startswith(ASSINATURA_PNG) or arquivos.sha256_bytes(dados) != sha:
                continue
            ident = 'a%03d' % (len(por_sha) + 1)
            por_sha[sha] = ident
            servidos[ident] = (dados, 'image/png')
        por_camada[lid] = por_sha[sha]
    return servidos, por_camada


# ------------------------------------------------------------------ montagem
def montar(pasta):
    """Conteudo do servidor da tela para o job: {'estado', 'previas', 'assets', 'fontes'}. ErroTela com o motivo
    (texto fixo do motor) quando o job nao tem o que mostrar."""
    from desdobra.derivacao import formatos as mf
    from desdobra.derivacao import nucleo as nd
    from desdobra.fontes import casamento
    from desdobra.job import nucleo
    pasta = Path(pasta).resolve()
    try:
        with nucleo.Trava(pasta):
            estado_job = nucleo.ler_estado(pasta)
            ctx = nd.preparar(pasta)
            specs, arquivo_specs = mf.specs_do_job(pasta)
            params = mf.parametros(pasta, ctx['briefing'])
            r = nd.derivar_em_memoria(ctx, specs=specs, arquivo_specs=arquivo_specs, params=params)
            fontes, lista_fontes, faces = fontes_do_job(pasta, estado_job)
            assets, asset_por_camada = assets_das_camadas(pasta, ctx['laudo'])
            lido_ = lido(pasta, estado_job, ctx['laudo'], ctx['briefing'], r['formatos'], lista_fontes)
    except nd.ErroDerivacao as e:
        raise ErroTela(str(e), e.motivo) from None
    except nucleo.ErroJob as e:
        raise ErroTela(str(e), 'job_ocupado' if int(e.codigo) == int(Codigo.OCUPADO) else 'nao_e_job') from None

    def face_de(ps):
        if not ps:
            return None
        f, _metodo, _n = casamento.casar(ps, faces)
        return f['id'] if f is not None and f['id'] in fontes else None

    b, laudo = ctx['briefing'], ctx['laudo']
    base = pecas_base(laudo, asset_por_camada, face_de)
    previas = {fid: palco(d, r['kv'], laudo, base) for fid, d in r['formatos'].items()}
    gals = galerias(ctx, r['kv'], laudo, base, r['formatos'], abas(laudo, b, r['formatos']), specs=specs,
                    arquivo_specs=arquivo_specs, params=params)
    for fid, gal in gals.items():
        previas[fid]['galeria'] = gal
        dv = previas[fid]['devolucao']
        dv['texto'] = texto_da_devolucao(dv['motivo'], len(gal['variantes']))
    n_variantes = {fid: len(gal['variantes']) for fid, gal in gals.items()}
    estado = {'esquema': ESQUEMA, 'job_id': estado_job['job_id'], 'somente_leitura': True,
              'briefing_origem': b['cabecalho']['origem'],
              'mestre': {'largura': laudo['documento']['largura'], 'altura': laudo['documento']['altura']},
              'orientacoes': abas(laudo, b, r['formatos'], n_variantes), 'fontes': lista_fontes,
              'assets': [{'id': i} for i in sorted(assets)], 'devolucoes': len(r['devolucoes']),
              'lido': lido_,
              'funcoes': {'arvore': arvore(laudo, b, ctx['resolvidas'], ctx['info'].get('quadro')),
                          'resumo': resumo_das_funcoes(b, ctx['resolvidas']), 'palco_kv': palco_kv(r['kv'], laudo, base)},
              'faltam': faltam(lido_, r['formatos'], n_variantes)}
    return {'estado': estado, 'previas': previas, 'assets': assets, 'fontes': fontes}
