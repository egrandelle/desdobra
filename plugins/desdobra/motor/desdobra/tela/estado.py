# -*- coding: utf-8 -*-
"""O que a tela so de leitura mostra (M7a2 e M7a3): os passos, as abas, o palco de cada composicao, as faces e os
assets do job.

  - lido (passo 1, "O que eu li"): bloqueios das fases e das camadas, linkados, valores de spec por situacao, modo de
    dados e fontes (decisoes-v1.md n 161); e, desde a revisao do M7a, os formatos com o giro escolhido pelo DA (e o que
    a folha diz do giro, como dica) e as pranchetas do PSD com a previa de cada uma, para o DA escolher de qual a peca
    sai. As duas escolhas ficam no rascunho da tela (desdobra.tela.rascunho.CAMPOS_DO_PASSO_1);
  - funcoes (passo 2, "Funcoes"): a arvore dos grupos do laudo com a funcao resolvida de cada camada e de onde ela vem
    (da propria camada, herdada do grupo ou pela regra da decisao 10; briefing.modelo.resolver), o resumo das regras e
    das ancoras por funcao e o palco do KV, no centro; e, desde a fatia 3 do M7a, as decisoes que o DA toma na tela
    (decisoes_do_passo_2: os nos e as opcoes do esquema, sem valor; as escolhas vao ao rascunho da tela);
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
PROPOSTA_DEPOIS = 'A proposta do desdobra para este arquivo chega com a galeria de variantes, na próxima versão.'
SEM_VERSOES = 'O desdobra não conseguiu montar versões para este arquivo.'
SELO_VARIANTE = 'variante'
MOTIVOS_TELA = {
    'troca_forte_de_orientacao': 'A orientação muda em relação ao KV.',
    'troca_de_orientacao_quadrado': 'A peça passa para o quadrado, ou sai dele, em relação ao KV.',
    'fora_da_faixa_de_familia': 'A proporção fica longe da proporção do KV.',
}
MOTIVO_GERAL = 'O desdobra ainda não chegou a uma proposta para este formato.'
# o formato com um valor de spec que espera a confirmacao do DA (revisao dos becos, A1): a previa e a lista do que
# falta levam ao passo 1, sem galeria (o desdobra so monta a peca com os valores confirmados), e a familia dele so e
# confirmada depois (o DA nunca confirma uma familia sem ver a galeria de cada formato)
SPEC_POR_CONFIRMAR = ('Um valor de spec deste formato ainda espera a sua confirmação. Confirme os valores dele em '
                      'Valores de spec, no passo 1, e o desdobra monta a peça com os valores confirmados.')
SPEC_POR_CONFIRMAR_FALTA = 'Confirme os valores deste formato em Valores de spec, no passo 1.'
# o formato que deriva da mestre propria do DA cujo formato espera um valor de spec (revisao dos becos, D3): espera
# com ela, como o formato da mestre, sem galeria e com a familia sem confirmacao
MESTRE_POR_CONFIRMAR = ('O formato da mestre desta família ainda espera a confirmação de um valor de spec. Confirme os '
                        'valores dele em Valores de spec, no passo 1, e o desdobra monta as peças da família com os '
                        'valores confirmados.')
# o formato da folha com duas medidas, sem a escolha do DA (revisao dos becos, D2): sem medida nao ha chave nem peca, e
# ele aparece pelo que a folha diz, nunca pelo identificador interno
ONDE_SEM_MEDIDA = 'Formato da folha com duas medidas: %s'
# o mesmo formato na frase da janela de confirmacao ("No formato da folha com duas medidas (...), o campo ...")
FRASE_SEM_MEDIDA = 'formato da folha com duas medidas (%s)'
MEDIDA_A_ESCOLHER_FALTA = ('Um formato da folha traz duas medidas. Escolha a medida dele em Valores de spec, no '
                           'passo 1, e ele entra nos formatos do job.')
MESTRE_POR_CONFIRMAR_FALTA = 'Confirme os valores do formato da mestre desta família em Valores de spec, no passo 1.'


def _versoes(n):
    return '%d versão' % n if n == 1 else '%d versões' % n


def texto_da_devolucao(motivo, variantes=None):
    """A frase da tela para o formato devolvido, sem identificador do motor e sem pedir mestre propria. variantes:
    quantas a galeria montou (None: a galeria nao foi montada)."""
    from desdobra.derivacao import nucleo as nd
    if motivo == nd.MOTIVO_SPEC_POR_CONFIRMAR:
        return SPEC_POR_CONFIRMAR
    if motivo == nd.MOTIVO_MESTRE_POR_CONFIRMAR:
        return MESTRE_POR_CONFIRMAR
    if variantes:
        depois = 'O desdobra montou %s com os blocos do próprio KV.' % _versoes(variantes)  # a nota da galeria pede a escolha
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


def galerias(ctx, kv, laudo, base, derivados, orientacoes, *, specs, arquivo_specs, params, brutos=None):
    """{id do formato devolvido: {'grupo': [ids], 'variantes': [...]}} para cada grupo de proporcao da tela
    (orientacoes, de abas) com formato devolvido. As variantes vem da galeria do motor no primeiro devolvido do grupo
    (derivacao.galeria.variantes); com mais de um devolvido no grupo, cada variante vai a todos pela estrutura que
    deixa o pior membro melhor (variante_para_grupo). Quando nenhuma estrutura serve ao grupo, cada membro fica com a
    variante em todo o grupo. O membro sem nenhuma variante ganha a galeria dele sozinho. So previa, em memoria.
    brutos: {id do formato: {id da variante: variante do motor}} preenchido aqui, para a edicao no palco partir da
    variante escolhida (desdobra.tela.edicao)."""
    from desdobra.derivacao import proposta
    por_id = {f['id']: f for f in ctx['briefing']['formatos']}
    kw = {'specs': specs, 'arquivo_specs': arquivo_specs, 'params': params}
    saida = {}
    for o in orientacoes:
        for g in o['grupos']:
            # o formato com a medida por confirmar fica fora: a galeria so sai da medida confirmada
            fids = [x['id'] for c in g['composicoes'] for x in c['formatos'] if x['situacao'] == 'devolvido' and
                    x['id'] not in por_confirmar(derivados)]
            if not fids:
                continue
            # a mesma galeria que a derivacao usa quando o DA confirma a familia (desdobra.derivacao.proposta)
            por_formato = proposta.galeria_da_familia(ctx, kv, [por_id[f] for f in fids], **kw)
            for fid in fids:
                pares = por_formato[fid]
                W, H = derivados[fid]['formato']['composicao']
                if brutos is not None:
                    brutos[fid] = {v['id']: v for _n, v in pares}
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


def decisoes_do_passo_2(laudo, quadro):
    """O que o passo 2 e o Design system pedem ao DA (desdobra.tela.funcoes): os grupos e as camadas na ordem do
    painel e as opcoes de cada campo, lidas do esquema briefing/1. Nenhum valor: as escolhas do DA vem so do rascunho
    da tela, e a funcao do briefing de teste nunca aparece como escolha."""
    from desdobra.tela import funcoes as tf
    return {'nos': tf.nos(laudo, quadro), 'opcoes': tf.opcoes(), 'quadro': quadro}


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


def modo_na_tela(pasta, teto_cli=None):
    """O modo de dados do passo 1 (decisoes-v1.md, 170): o escolhido na tela (o valor gravado, sem nada marcado antes
    da escolha), o teto da agencia e so as opcoes dentro dele. O estado.json nao e fonte do modo."""
    from desdobra.job import modo_dados
    teto = modo_dados.teto_do_job(pasta, teto_cli)
    reg = modo_dados.ler(pasta)
    return {'escolhido': reg['valor'] if reg is not None else None, 'teto': teto, 'opcoes': modo_dados.opcoes(teto)}


def linkados_na_tela(pasta, laudo):
    """Os linkados do laudo para o passo 1: camada, nome, se ja tem arquivo confirmado (e qual) e os candidatos da
    proposta do leitor (caminho do job em entrada/campanha/, bytes e se o tamanho bate com o registro do PSD)."""
    from desdobra.render import contrato as mod_contrato
    try:
        confirmados = mod_contrato.linkados_confirmados(pasta, None, laudo['origem']['sha256']) or {}
    except Exception:  # noqa: BLE001 - arquivo fora do contrato conta como sem confirmacao
        confirmados = {}
    out = []
    for c in laudo['camadas']:
        so = c.get('smart_object') or {}
        if c.get('tipo') != 'smart_linkado' or not so.get('unique_id'):
            continue
        conf = confirmados.get(so['unique_id'])
        cands = [{'arquivo': 'entrada/' + x['arquivo'], 'nome': Path(x['arquivo']).name, 'bytes': x.get('bytes'),
                  'mesmo_tamanho': bool(x.get('mesmo_tamanho'))}
                 for x in (so.get('casamento') or {}).get('candidatos') or [] if isinstance(x.get('arquivo'), str)]
        out.append({'camada': c['identidade']['layer_id'], 'nome': c.get('nome') or '', 'unique_id': so['unique_id'],
                    'confirmado': conf is not None, 'arquivo': conf['arquivo'] if conf else None, 'candidatos': cands})
    return out


# os campos de spec (specs.modelo.CAMPOS) com nome para o DA; o id cru nunca vai a tela
NOMES_CAMPO = {
    'versao_impressa': 'versão impressa', 'data_impressa': 'data impressa', 'nome': 'nome do veículo',
    'apelidos': 'outros nomes', 'concessionaria': 'concessionária', 'prazo_envio': 'prazo de envio',
    'ambiente': 'ambiente', 'praca': 'praça', 'modelo_tela': 'modelo da tela', 'faixas_reservadas': 'faixas reservadas',
    'restricao': 'restrição', 'dimensao': 'dimensão', 'orientacao_painel': 'orientação do painel', 'rotacao': 'rotação',
    'area_util': 'área útil', 'faixas': 'faixas', 'area_segura': 'área segura', 'borda_1px': 'borda de 1 px',
    'peso_max': 'peso máximo', 'peso_max_hospedado': 'peso máximo hospedado', 'peso_max_tag': 'peso máximo por tag',
    'peso_max_tag_carga_inicial': 'peso máximo da carga inicial',
    'peso_max_tag_carga_posterior': 'peso máximo da carga posterior', 'tipos_aceitos': 'tipos de arquivo aceitos',
    'qualidade_jpg_recomendada': 'qualidade de JPG recomendada', 'area_visivel': 'área visível', 'sangria': 'sangria',
    'margem_seguranca': 'margem de segurança', 'sufixo_nome_arquivo': 'final do nome do arquivo',
}


def nome_do_campo(campo):
    return NOMES_CAMPO.get(campo) or str(campo).replace('_', ' ')


def descricao_do_valor(v):
    """O valor de spec em texto para o DA: a dimensao, o texto como esta na folha ou o valor."""
    x = v.get('valor')
    if isinstance(x, dict) and 'largura' in x and 'altura' in x:
        return ('%s x %s %s' % (x['largura'], x['altura'], v.get('unidade') or '')).strip()
    if v.get('texto_original'):
        return str(v['texto_original'])
    if isinstance(x, list):
        return ', '.join(str(i) for i in x)
    return '' if x is None else str(x)


def formatos_sem_medida(pasta):
    """Os formatos do rascunho das specs com a medida divergente, sem a escolha do DA e por isso sem chave (revisao
    dos becos, D2): [{'valor_id', 'leituras': [texto de cada medida], 'texto'}], na ordem da folha. Vazio sem rascunho
    legivel."""
    doc = _ler(Path(pasta) / 'specs' / 'rascunho.json', 'spec/1')
    saida = []
    for f in (doc or {}).get('formatos') or []:
        dim = (f.get('campos') or {}).get('dimensao') or {}
        if f.get('chave') or dim.get('valor') is not None or not dim.get('leituras'):
            continue
        leituras = [descricao_do_valor(lei) for lei in dim['leituras']]
        saida.append({'formato': f['id'], 'valor_id': dim['id'], 'leituras': leituras, 'texto': ' ou '.join(leituras)})
    return saida


def specs_pendentes(pasta):
    """Os valores de spec que esperam o DA no passo 1, na ordem da confirmacao do terminal (divergentes primeiro):
    {'valor_id', 'onde', 'campo' (nome para o DA), 'descricao', 'trecho', 'leituras': [{'indice', 'descricao',
    'trecho'}]}. A leitura so aparece no campo com fontes divergentes."""
    from desdobra.specs import confirmar as mod_confirmar
    out = []
    sem_medida = {x['formato']: x['texto'] for x in formatos_sem_medida(pasta)}
    for r, campo, v in mod_confirmar.pendencias_gravadas(pasta):
        divergente = bool(v.get('leituras')) and v['valor'] is None
        leituras = [{'indice': i, 'descricao': descricao_do_valor(lei), 'trecho': lei.get('texto_original') or ''}
                    for i, lei in enumerate(v.get('leituras') or [])] if divergente else []
        # o formato sem chave (a medida espera a escolha) aparece pelas medidas da folha, em todos os valores dele
        if not r.get('chave') and r['id'] in sem_medida:
            onde, na_frase = ONDE_SEM_MEDIDA % sem_medida[r['id']], FRASE_SEM_MEDIDA % sem_medida[r['id']]
        else:
            onde = r.get('chave') or r['id']
            na_frase = 'formato %s' % onde
        out.append({'valor_id': v['id'], 'onde': onde, 'na_frase': na_frase, 'campo': nome_do_campo(campo),
                    'descricao': descricao_do_valor(v) if not divergente else 'as folhas trazem valores diferentes',
                    'trecho': v.get('texto_original') or '', 'leituras': leituras})
    return out


# as paradas que ainda nao tem botao na tela, em texto para o DA (decisoes-v1.md, 24, 41, 57 e 79; a 159 manda que o
# DA nunca rode nada no terminal: a tela so mostra o bloqueio, sem comando)
PARADA_DEPOIS = 'Esta decisão ainda não tem botão na tela; o job fica parado neste ponto até a próxima versão.'
TEXTOS_PARADA = {
    'largura': 'A largura de uma linha de texto ficou diferente da largura medida no Photoshop. ' + PARADA_DEPOIS,
    'mesclagem': ('Uma camada usa mesclagem ou ajuste sobre outras camadas, e as peças novas podem sair com outra '
                  'aparência nesse ponto. ' + PARADA_DEPOIS),
    'isolador': ('O arquivo passou do limite de memória ou de tempo na leitura, e a composição do KV não foi '
                 'conferida. ' + PARADA_DEPOIS),
}
CODIGOS_PARADA = {'largura_divergente': 'largura', 'efeito_sobre_texto_sem_aplicar': 'mesclagem',
                  'clipping_dividido_por_texto': 'mesclagem', 'composicao_acima_do_orcamento': 'isolador'}
RECUSAS_DO_ISOLADOR = ('memoria', 'tempo', 'orcamento')


def _ids_das_medidas(medidas):
    out = []
    for x in (medidas or {}).get('camadas') or []:
        lid = x.get('layer_id') if isinstance(x, dict) else x
        if isinstance(lid, int) and not isinstance(lid, bool):
            out.append(lid)
    return out


def paradas(pasta, laudo):
    """Bloqueios do passo 1 em texto simples: a divergencia de largura, a mesclagem (no KV, pelo contrato do render, e
    nas pecas derivadas, pelas camadas visiveis do laudo com mesclagem) e as paradas do isolador (recusa de memoria ou
    tempo do laudo). [{'tipo', 'texto', 'camadas': [nome]}], um por tipo."""
    from desdobra.derivacao import elementos
    from desdobra.render import contrato as mod_contrato
    nomes = {c['identidade']['layer_id']: c.get('nome') or '' for c in laudo.get('camadas') or []}
    por_tipo = {}

    def juntar(tipo, ids=()):
        item = por_tipo.setdefault(tipo, {'tipo': tipo, 'texto': TEXTOS_PARADA[tipo], 'camadas': []})
        for lid in ids:
            nome = nomes.get(lid)
            if nome and nome not in item['camadas']:
                item['camadas'].append(nome)

    try:
        _c, bloqueios, confirmar = mod_contrato.montar(pasta)
    except Exception:  # noqa: BLE001 - sem contrato legivel a tela segue; o render recusa do jeito dele
        bloqueios, confirmar = [], []
    for b in list(bloqueios or []) + list(confirmar or []):
        tipo = CODIGOS_PARADA.get(b.get('codigo'))
        if tipo:
            juntar(tipo, _ids_das_medidas(b.get('medidas')))
    mesclas = [c['identidade']['layer_id'] for c in laudo.get('camadas') or []
               if elementos.mesclagem(c) and (c.get('aparencia') or {}).get('visivel_efetiva', True)]
    if mesclas:
        juntar('mesclagem', mesclas)
    if any(r.get('tipo') in RECUSAS_DO_ISOLADOR for r in laudo.get('recusas') or []):
        juntar('isolador')
    return [por_tipo[t] for t in ('largura', 'mesclagem', 'isolador') if t in por_tipo]


BLOQUEIO_DE_FASE = 'O desdobra parou nesta etapa, e a próxima versão da tela traz o que fazer aqui.'


def bloqueio_na_tela(fid, bloqueio):
    """O bloqueio de uma fase em texto para o DA: o nome da etapa e uma frase fixa, nunca o o_que_fazer do motor, que
    cita comando de terminal."""
    return {'fase': fid, 'descricao': descricao_da_fase(fid), 'texto': BLOQUEIO_DE_FASE}


def giro_da_folha(doc, chave):
    """O que a folha de spec diz do giro do formato (o campo rotacao, so registro), no texto da folha, ou None quando
    ela nao diz nada. So dica para o DA: o giro do briefing e escolha dele."""
    for f in (doc or {}).get('formatos') or []:
        if f.get('chave') == chave:
            v = (f.get('campos') or {}).get('rotacao') or {}
            texto = v.get('texto_original')
            return texto if isinstance(texto, str) and texto.strip() else None
    return None


def quadros_na_tela(laudo, briefing):
    """As pranchetas do PSD para o passo 1 (decisao 1; revisao do M7a): [{'id', 'nome', 'largura', 'altura',
    'visivel', 'escolhido'}], na ordem do laudo, sem nada escolhido antes do DA. O PSD sem prancheta da lista vazia. A
    previa de cada uma (palco) entra em montar."""
    from desdobra.briefing import modelo as mb
    d = briefing.get('quadro')
    escolhido = d['valor'] if mb._decisao_valida(d) else None
    saida = []
    for q in (laudo.get('documento') or {}).get('quadros') or []:
        x0, y0, x1, y1 = q['caixa']
        saida.append({'id': q['id'], 'nome': q.get('nome') or '', 'largura': int(round(x1 - x0)),
                      'altura': int(round(y1 - y0)), 'visivel': bool(q.get('visivel_ao_salvar')),
                      'escolhido': q['id'] == escolhido})
    return saida


def lido(pasta, estado_job, laudo, briefing, formatos, faces_servidas, teto=None):
    """Passo 1: o que o motor leu do job, com as decisoes do DA que ja tem botao (modo de dados, linkados e valores de
    spec; decisoes-v1.md, 159 e 170) e as paradas em texto simples."""
    from desdobra.job import fases as mod_fases
    from desdobra.job import nucleo
    from desdobra.specs import confirmar as mod_confirmar
    from desdobra.specs import modelo as mod_specs
    pasta = Path(pasta)
    avaliacao, _d = nucleo.avaliar(pasta, estado_job, mod_fases.ESTEIRA)
    bloqueios = [bloqueio_na_tela(fid, b) for fid, b in nucleo.bloqueios_pendentes(estado_job, avaliacao,
                                                                                 mod_fases.ESTEIRA)]
    camadas_bloqueadas = [{'camada': c['identidade']['layer_id'], 'nome': c.get('nome') or '',
                           'motivos': [m.get('descricao') or m.get('regra') for m in c.get('motivos') or []]}
                          for c in laudo['camadas'] if c.get('situacao') == 'bloqueante']
    linkados = linkados_na_tela(pasta, laudo)
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
    specs['lista'] = specs_pendentes(pasta) if doc is not None else []
    specs['recortes'] = sum(len(f.get('recortes') or []) for f in (doc or {}).get('folhas') or [])
    specs['folhas'] = len((doc or {}).get('folhas') or [])
    specs['sem_medida'] = formatos_sem_medida(pasta) if doc is not None else []
    # o giro de cada formato e escolha do DA (revisao do M7a): o que a folha diz do giro vai como dica, nunca marcado
    specs['formatos'] = [{'id': f['id'], 'chave': f.get('chave'), 'sem_folha': bool(f.get('sem_folha')),
                          'tem_spec': bool(((formatos.get(f['id']) or {}).get('formato') or {}).get('tem_spec')),
                          'largura': f['largura'], 'altura': f['altura'], 'rotacao': f.get('rotacao'),
                          'giro_da_folha': giro_da_folha(doc, f.get('chave'))}
                         for f in briefing['formatos']]
    # sem formato em pixels: o que o DA faz, no lugar da lista (revisao do M7a)
    specs['sem_formatos'] = '' if specs['formatos'] else \
        (SEM_MEDIDA_EM_PIXELS if specs['folhas'] else SEM_FOLHA_DE_SPEC)
    lf = _ler(pasta / 'laudo' / 'laudo-fontes.json', 'laudo/1')
    usadas = (lf or laudo).get('fontes_usadas') or []
    return {'bloqueios': bloqueios, 'camadas_bloqueadas': camadas_bloqueadas, 'linkados': linkados, 'specs': specs,
            'quadros': quadros_na_tela(laudo, briefing),
            'modo_dados': modo_na_tela(pasta, teto), 'paradas': paradas(pasta, laudo),
            'fontes': faces_servidas,
            'fontes_que_faltam': [{'fonte_ps': u['fonte_ps'], 'situacao': u['situacao'], 'camadas': len(u['camadas'])}
                                  for u in usadas if u.get('situacao') in ('ausente', 'divergente')]}


FAMILIA_SEM_CONFIRMACAO = 'Confirme a família quando ela estiver como você quer.'


def por_confirmar(formatos):
    """Os ids dos formatos devolvidos com um valor de spec a espera do DA, na derivacao em memoria ({id: derivacao}):
    o do proprio formato (spec_por_confirmar) e o do formato da mestre propria de que ele deriva (mestre_por_confirmar;
    revisao dos becos, D3)."""
    from desdobra.derivacao import nucleo as nd
    return {fid for fid, d in (formatos or {}).items()
            if (d.get('devolucao') or {}).get('motivo') in nd.MOTIVOS_POR_CONFIRMAR}


def familias_confirmadas(pasta, familias, pendentes=(), pecas=None):
    """Os ids das familias confirmadas no rascunho da tela agora (decisoes-v1.md, 167), so para os formatos que cada
    uma tem hoje (familias: {id: [formatos]}; desdobra.tela.rascunho.confirmada_para). A familia com formato em
    pendentes (por_confirmar) nunca conta como confirmada: o DA nao viu a galeria dele. pecas: {id: impressao}
    (impressao_das_pecas); com ela, a confirmacao feita sobre outras pecas nao conta."""
    from desdobra.tela import rascunho
    dados, _de_outro = rascunho.ler(pasta, rascunho.laudo_sha256(pasta))
    return {g for g, f in ((dados or {}).get('familias') or {}).items()
            if rascunho.confirmada_para(f, familias.get(g, ()), None if pecas is None else pecas.get(g, ''))
            and not set(familias.get(g, ())) & set(pendentes)}


def impressao_das_pecas(fids, formatos, versoes):
    """A impressao do que a tela mostra da familia (revisao 3 da regra spec_por_confirmar): de cada formato, a
    composicao, a situacao, o motivo da devolucao e as areas que vem da spec (a area util, as faixas e a area segura),
    e as versoes da galeria. A folha trocada (outra area segura) ou a galeria que aparece depois da confirmacao mudam
    a impressao, e a confirmacao de antes deixa de valer (desdobra.tela.rascunho.confirmada_para).
    formatos: {id: derivacao}."""
    import hashlib
    import json
    itens = []
    for fid in fids:
        d = formatos.get(fid) or {}
        a = d.get('areas') or {}
        au, seg = a.get('area_util'), a.get('area_segura')
        itens.append([fid, (d.get('formato') or {}).get('composicao'), d.get('situacao'),
                      (d.get('devolucao') or {}).get('motivo'), au and au.get('caixa'),
                      [[x.get('lado'), x.get('px'), x.get('caixa')] for x in a.get('faixas') or []],
                      seg and [seg.get('caixa'), seg.get('lados')]])
    texto = json.dumps({'formatos': itens, 'versoes': sorted(versoes)}, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()


def faltam(lido_, formatos, variantes=None, familias=None, confirmadas=()):
    """A lista unica do que falta, cada item com o lugar da tela que leva a ele. variantes: {id do formato: quantas
    variantes a galeria montou}; o formato devolvido com versoes pede a escolha de uma. familias: {id: [formatos]}; a
    familia sem confirmacao no rascunho pede a confirmacao, e a confirmada deixa de pedir a escolha da versao."""
    variantes = variantes or {}
    familias = familias or {}
    resolvidos = {f for g in confirmadas for f in familias.get(g, ())}
    itens = []
    if lido_['modo_dados']['escolhido'] is None:
        itens.append({'texto': 'Escolha o modo de dados do job.', 'detalhe': '', 'ir': {'passo': 'lido'}})
    for b in lido_['bloqueios']:
        itens.append({'texto': b['texto'], 'detalhe': b['descricao'], 'ir': {'passo': 'lido'}})
    for p in lido_['paradas']:
        itens.append({'texto': p['texto'], 'detalhe': ', '.join(p['camadas']), 'ir': {'passo': 'lido'}})
    for c in lido_['camadas_bloqueadas']:
        itens.append({'texto': 'Uma camada do PSD não pôde ser lida.', 'detalhe': c['nome'], 'ir': {'passo': 'lido'}})
    for x in lido_['linkados']:
        if not x['confirmado']:
            itens.append({'texto': 'Um linkado espera a confirmação do arquivo.', 'detalhe': x['nome'],
                          'ir': {'passo': 'lido'}})
    if lido_['specs'].get('recortes'):
        itens.append({'texto': 'Uma folha de spec tem página sem texto, e os valores dela ainda não têm botão na tela.',
                      'detalhe': str(lido_['specs']['recortes']), 'ir': {'passo': 'lido'}})
    if lido_['specs']['pendentes']:
        itens.append({'texto': 'Há valores de spec que esperam a sua confirmação.',
                      'detalhe': str(lido_['specs']['pendentes']), 'ir': {'passo': 'lido'}})
    # o formato da folha com duas medidas espera a escolha do DA, e nunca some do job em silencio (revisao dos becos, D2)
    for x in lido_['specs'].get('sem_medida') or []:
        itens.append({'texto': MEDIDA_A_ESCOLHER_FALTA, 'detalhe': x['texto'], 'ir': {'passo': 'lido'}})
    # o passo 1 da revisao do M7a: specs sem formato em pixels, a prancheta e o giro de cada formato
    if not lido_['specs']['formatos']:
        itens.append({'texto': SEM_FORMATOS_FALTA, 'ir': {'passo': 'lido'},
                      'detalhe': SEM_MEDIDA_EM_PIXELS if lido_['specs'].get('folhas') else SEM_FOLHA_DE_SPEC})
    if lido_.get('quadros') and not any(q['escolhido'] for q in lido_['quadros']):
        itens.append({'texto': QUADRO_SEM_ESCOLHA, 'detalhe': '', 'ir': {'passo': 'lido'}})
    sem_giro = [f['id'] for f in lido_['specs']['formatos'] if f.get('rotacao') is None]
    if sem_giro:
        itens.append({'texto': GIRO_SEM_ESCOLHA, 'detalhe': ', '.join(sem_giro), 'ir': {'passo': 'lido'}})
    for f in lido_['fontes_que_faltam']:
        itens.append({'texto': 'Uma fonte do PSD falta ou não confere com o arquivo enviado.', 'detalhe': f['fonte_ps'],
                      'ir': {'passo': 'lido'}})
    pendentes = por_confirmar(formatos)
    for gid, fids in familias.items():
        # a familia com formato por confirmar espera o passo 1: o item do formato, logo abaixo, leva a ele
        if gid not in confirmadas and fids and not set(fids) & pendentes:
            itens.append({'texto': FAMILIA_SEM_CONFIRMACAO, 'detalhe': ', '.join(fids),
                          'ir': {'passo': 'pecas', 'formato': fids[0]}})
    for fid, d in formatos.items():
        if d['situacao'] == 'devolvido' and not (fid in resolvidos and variantes.get(fid)):
            motivo = (d.get('devolucao') or {}).get('motivo')
            if fid in pendentes and motivo == 'mestre_por_confirmar':
                # o formato espera a spec do formato da mestre, que tem o item dele com a chave da folha
                itens.append({'texto': MESTRE_POR_CONFIRMAR_FALTA, 'detalhe': fid, 'ir': {'passo': 'lido'}})
                continue
            if fid in pendentes:
                # a chave da folha, como a lista de Valores de spec mostra o formato
                itens.append({'texto': SPEC_POR_CONFIRMAR_FALTA, 'detalhe': d['formato'].get('chave') or fid,
                              'ir': {'passo': 'lido'}})
                continue
            inicio = 'Escolha uma das versões do desdobra. ' if variantes.get(fid) else 'Sem proposta do desdobra. '
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
def com_o_passo_2_do_rascunho(pasta, ctx):
    """O contexto da derivacao com as funcoes, as cobertas e o Design system do rascunho da tela por cima do briefing
    gravado, ou do de partida no job novo (revisao do M7a): as familias do passo 3 partem do que "Salvar e seguir" vai
    gravar (desdobra.briefing.salvar.montar). Sem passo 2 no rascunho, ou com ele ainda incompleto (a conferencia do
    motor acha problema), fica o contexto de antes. O passo 2 mudado com a tela aberta vale no proximo GET do estado
    (montar, atualizar); as confirmacoes das familias caem na gravacao (desdobra.tela.rascunho.gravar)."""
    import copy

    from desdobra.briefing import modelo as mb
    from desdobra.briefing import salvar
    from desdobra.derivacao import nucleo as nd
    from desdobra.tela import funcoes, rascunho
    dados, _de_outro = rascunho.ler(pasta, rascunho.laudo_sha256(pasta))
    if not dados or not dados.get('funcoes'):
        return ctx
    base = ctx['briefing']
    novo = copy.deepcopy(base)
    quadro = base['quadro']['valor'] if mb._decisao_valida(base['quadro']) else None
    parcial = funcoes.briefing_parcial(dados, quadro)
    tipo = mb.ORIGEM_FIXTURE if dados.get('origem') == mb.ORIGEM_FIXTURE else mb.ORIGEM_DA
    for k in salvar.CAMPOS_DO_RASCUNHO:
        novo[k] = salvar._com_origem(parcial[k], tipo)
    if novo['cabecalho']['origem'] == mb.ORIGEM_RASCUNHO:
        # o de partida (job novo): a previa leva a origem que "Salvar e seguir" vai gravar; so em memoria
        novo['cabecalho'] = dict(novo['cabecalho'], origem=tipo)
    erros = [e for e in mb.conferir(ctx['laudo'], novo, ctx['estado']['job_id'])
             if not (e['codigo'] == 'pendente_obrigatorio' and e.get('onde') == '/modo_dados')]
    if erros:
        return ctx
    return nd.contexto(ctx['laudo'], novo, ds=ctx['ds'], job_id=ctx['estado']['job_id'], pasta=ctx['pasta'],
                       briefing_sha256=ctx['briefing_sha256'], portao_fontes=ctx['portao_fontes'],
                       medidas_quebras=ctx['medidas_quebras'], da_tela=True)




# o passo 3 que espera o passo 2 (job novo, sem briefing confirmado): o aviso da tela, sem identificador do motor
AGUARDA_PASSO_2 = ('As famílias aparecem aqui quando todas as camadas tiverem função, no passo 2, e cada função tiver '
                   'regra de escala e âncora, no Design system.')
AGUARDA_CONFERENCIA = ('As funções e o Design system estão preenchidos, mas o desdobra ainda não consegue montar as '
                       'famílias com essas escolhas. Confira as funções das camadas no passo 2.')
AGUARDA_QUADRO = 'O PSD tem pranchetas. Escolha no passo 1 de qual prancheta a peça sai, e as famílias aparecem aqui.'
# specs sem nenhum formato em pixels (revisao do M7a): o passo 3 e a lista do que falta dizem o que falta e o que fazer
SEM_FORMATOS = ('As famílias saem dos formatos das specs, e o job ainda não tem nenhum formato com medida em pixels. '
                'Veja no passo 1 o que falta.')
SEM_FORMATOS_FALTA = 'As specs do job ainda não têm nenhum formato com medida em pixels.'
SEM_FOLHA_DE_SPEC = ('O job ainda não tem folha de spec. Consiga com o veículo a folha com as medidas em pixels e peça '
                     'para incluí-la no job. Os formatos aparecem aqui assim que ela for lida.')
SEM_MEDIDA_EM_PIXELS = ('As folhas de spec do job não trazem uma medida em pixels que o desdobra consiga usar. Se as '
                        'folhas trazem medidas diferentes para o mesmo formato, escolha a certa em Valores de spec. Se a '
                        'medida está em outra unidade, consiga com o veículo a folha em pixels e peça para incluí-la no '
                        'job.')
# as escolhas do passo 1 que ainda faltam (revisao do M7a)
QUADRO_SEM_ESCOLHA = 'Escolha de qual prancheta do PSD a peça sai.'
GIRO_SEM_ESCOLHA = 'Escolha o giro de cada formato.'
# o briefing salvo de outra versao dos arquivos do job: a tela parte do briefing de partida e do rascunho
# (desdobra.briefing.modelo.retomada) e diz o que mudou e o que pede a confirmacao de novo (revisao do M7a)
AVISO_PSD_MUDOU = ('O PSD foi lido de novo depois que o briefing foi salvo. A prancheta, as funções, o design system e '
                   'as famílias precisam ser escolhidos e confirmados de novo. O giro de cada formato continua como '
                   'estava.')
AVISO_SPECS_MUDARAM = ('As specs do job mudaram depois que o briefing foi salvo. Confira os formatos e o giro de cada um '
                       'no passo 1, confirme de novo as famílias que mudaram e salve o briefing outra vez.')
AVISO_FONTES_MUDARAM = ('As fontes ou o design system do PSD mudaram depois que o briefing foi salvo. Confira as '
                        'famílias e salve o briefing outra vez.')


def avisos_de_retomada(pasta, gravado):
    """Os avisos da tela quando o briefing gravado e de outra versao dos arquivos do job ([] quando ele vale ou nao
    ha briefing confirmado)."""
    from desdobra.briefing import modelo as mb
    if gravado is None or gravado['cabecalho']['origem'] == mb.ORIGEM_RASCUNHO:
        return []
    velhos = set(mb.desatualizado(pasta, gravado))
    saida = []
    if 'laudo_sha256' in velhos:
        saida.append(AVISO_PSD_MUDOU)
    if 'specs_sha256' in velhos:
        saida.append(AVISO_SPECS_MUDARAM)
    if velhos & {'ds_sha256', 'conferencia_sha256'}:
        saida.append(AVISO_FONTES_MUDARAM)
    return saida


def _avisos_do_job(pasta):
    from desdobra import contratos
    from desdobra.briefing import historico
    from desdobra.briefing import modelo as mb
    try:
        retomada = avisos_de_retomada(pasta, mb.ler(pasta))
    except contratos.ErroContrato:
        retomada = []
    # o indice do historico mexido fora do desdobra (M7b, A4): so a adulteracao ingenua, risco 177 continua
    return retomada + historico.avisos(pasta)


def com_o_passo_1_do_rascunho(pasta, ctx):
    """O contexto da derivacao com as escolhas do passo 1 do rascunho da tela (a prancheta e o giro de cada formato;
    desdobra.briefing.salvar.escolhas_do_passo_1) por cima do briefing, como "Salvar e seguir" vai gravar. Vale mesmo
    com o passo 2 incompleto: a prancheta escolhe as camadas que o passo 2 mostra. Sem escolha nova, o contexto de
    antes."""
    from desdobra.briefing import modelo as mb
    from desdobra.briefing import salvar
    from desdobra.derivacao import nucleo as nd
    from desdobra.tela import rascunho
    dados, _de_outro = rascunho.ler(pasta, rascunho.laudo_sha256(pasta))
    if not dados or not any(dados.get(k) for k in rascunho.CAMPOS_DO_PASSO_1):
        return ctx
    tipo = mb.ORIGEM_FIXTURE if dados.get('origem') == mb.ORIGEM_FIXTURE else mb.ORIGEM_DA
    novo = salvar.escolhas_do_passo_1(ctx['briefing'], dados, ctx['laudo'], tipo)
    if novo['quadro'] == ctx['briefing']['quadro'] and novo['formatos'] == ctx['briefing']['formatos']:
        return ctx
    return nd.contexto(ctx['laudo'], novo, ds=ctx['ds'], job_id=ctx['estado']['job_id'], pasta=ctx['pasta'],
                       briefing_sha256=ctx['briefing_sha256'], portao_fontes=ctx['portao_fontes'],
                       medidas_quebras=ctx['medidas_quebras'], da_tela=True)


def _sem_passo_2(pasta):
    """O rascunho da tela ainda nao tem nada do passo 2 nem do Design system."""
    from desdobra.tela import rascunho
    dados = rascunho.ler(pasta, rascunho.laudo_sha256(pasta))[0] or {}
    return not any(dados.get(k) for k in rascunho.CAMPOS_DO_PASSO_2)


def _escolhas_do_passo_1(pasta):
    import json

    from desdobra.tela import rascunho
    dados = rascunho.ler(pasta, rascunho.laudo_sha256(pasta))[0] or {}
    return json.dumps({k: dados.get(k) for k in rascunho.CAMPOS_DO_PASSO_1}, sort_keys=True)


def assinatura_do_passo_2(pasta):
    """A prancheta, o giro (passo 1), o passo 2 e o Design system do rascunho da tela agora, em texto canonico (as
    familias ficam de fora): quando muda, o passo 3 e montado de novo (montar, atualizar). pasta None: a assinatura do
    rascunho sem escolha nenhuma."""
    import json

    from desdobra.tela import rascunho
    dados = None if pasta is None else rascunho.ler(pasta, rascunho.laudo_sha256(pasta))[0]
    return json.dumps({k: (dados or {}).get(k) or {} for k in rascunho.CAMPOS_DAS_ESCOLHAS}, sort_keys=True)


def espera_do_passo_3(pasta, ctx):
    """None quando o briefing do contexto passa na conferencia do motor (o modo de dados fica para o passo 1), senao o
    aviso do passo 3 que espera: as specs sem formato em pixels, a prancheta sem escolha, o passo 2 com escolha
    faltando, ou o passo 2 completo que a conferencia ainda recusa."""
    from desdobra.briefing import modelo as mb
    from desdobra.tela import funcoes, rascunho
    if not ctx['briefing']['formatos']:
        return SEM_FORMATOS
    erros = [e for e in mb.conferir(ctx['laudo'], ctx['briefing'], ctx['estado']['job_id'])
             if not (e['codigo'] == 'pendente_obrigatorio' and e.get('onde') == '/modo_dados')]
    if not erros:
        return None
    if any(e['codigo'] in ('quadro_sem_escolha', 'quadro_invalido') for e in erros):
        return AGUARDA_QUADRO
    dados, _de_outro = rascunho.ler(pasta, rascunho.laudo_sha256(pasta))
    if funcoes.pendencias(ctx['laudo'], dados or {}, ctx['info'].get('quadro')):
        return AGUARDA_PASSO_2
    return AGUARDA_CONFERENCIA


def palco_do_documento(laudo, base, resolvidas, quadro):
    """O palco do passo 2 antes de as funcoes fecharem: cada camada desenhavel da peca como ela esta no KV (sem
    transformacao, sem fantasma), com a funcao que a heranca ja da (ou nenhuma). So desenho: nenhuma regra nem ancora."""
    from desdobra.briefing import modelo as mb
    doc = laudo.get('documento') or {}
    canvas = [0.0, 0.0, float(doc.get('largura') or 1), float(doc.get('altura') or 1)]
    q = next((x for x in doc.get('quadros') or [] if x.get('id') == quadro), None)
    if q is not None and q.get('caixa'):
        canvas = [float(v) for v in q['caixa']]
    tr = {'s': 1.0, 'origem_doc': canvas[:2], 'destino': [0.0, 0.0], 'recorte_doc': canvas}
    itens = []
    for c in laudo['camadas']:
        lid = c['identidade']['layer_id']
        if lid not in base or not mb.no_escopo(c, quadro):
            continue
        r = resolvidas.get(lid) or {}
        el = {'id': 'c%d' % lid, 'raiz': lid, 'layer_ids': [lid], 'funcao': r.get('funcao'), 'regra': None,
              'origem_funcao': r.get('por')}
        itens.append((el, tr, _mapear(base[lid]['caixa'], tr), False))
    return _montar_palco(None, canvas[2] - canvas[0], canvas[3] - canvas[1], itens, base, 'kv', None, 'mestre', None,
                         _nomes(laudo))


def _sem_previa(_dados, origem=None):
    """A previa da edicao enquanto o passo 3 espera: nenhuma familia para editar."""
    return None


def montar(pasta, teto=None):
    """Conteudo do servidor da tela para o job: {'estado', 'previas', 'assets', 'fontes', 'recarregar', 'editar',
    'familias', 'atualizar'}. editar(dados, origem) e a previa da edicao por familia (desdobra.tela.edicao.Editor.previa);
    familias: {id: {'formatos', 'versoes'}} para o ato de confirmar a familia. ErroTela com o motivo (texto fixo do
    motor) quando o job nao tem o que mostrar. teto: o teto do modo de dados da linha de comando (o do estado.json entra
    sozinho). recarregar() refaz o passo 1 e a lista do que falta depois de um ato da tela, sem derivar de novo: as
    composicoes seguem as specs da abertura. atualizar() monta tudo de novo quando o passo 2 do rascunho mudou desde
    esta montagem (None quando nao mudou): o GET do estado leva o passo 3 novo a pagina, sem abrir a tela de novo.

    No job novo, sem briefing confirmado, a tela parte do briefing de partida (desdobra.briefing.modelo.partida: os
    formatos das specs do job e tudo o mais pendente), e nada e gravado na abertura. Enquanto o passo 2 nao passa na
    conferencia do motor, o passo 3 espera (estado passo_3), sem familia nem previa."""
    from desdobra.derivacao import formatos as mf
    from desdobra.derivacao import nucleo as nd
    from desdobra.fontes import casamento
    from desdobra.job import nucleo
    pasta = Path(pasta).resolve()
    from desdobra.briefing import modelo as mb
    assinatura = assinatura_do_passo_2(pasta)
    passo_1 = _escolhas_do_passo_1(pasta)
    try:
        with nucleo.Trava(pasta):
            estado_job = nucleo.ler_estado(pasta)
            # os arquivos do job desta montagem: o ato de spec da tela (ou outro que mude o laudo, as specs, o design
            # system ou as fontes) pede a tela montada de novo no proximo GET do estado (atualizar)
            arquivos_feitos = mb.hashes_atuais(pasta)
            ctx_gravado = nd.preparar(pasta, partida=True)
            # a prancheta e o giro do passo 1 valem antes do passo 2: a prancheta escolhe as camadas que ele mostra
            ctx_base = com_o_passo_1_do_rascunho(pasta, ctx_gravado)
            ctx = com_o_passo_2_do_rascunho(pasta, ctx_base)
            # o passo 3 mostra o passo 2 do rascunho (ou o rascunho nao tem passo 2): a pagina tira o aviso de que as
            # familias ainda sao as de antes
            aplicado = ctx is not ctx_base or _sem_passo_2(pasta)
            espera = espera_do_passo_3(pasta, ctx)
            specs, arquivo_specs = mf.specs_do_job(pasta)
            params = mf.parametros(pasta, ctx['briefing'])
            if espera is None:
                # sem as familias ja confirmadas: a tela parte da proposta do motor e leva as edicoes do rascunho por
                # cima, como a derivacao faz depois de "Salvar e seguir" (desdobra.derivacao.proposta)
                r = nd.derivar_em_memoria(ctx, specs=specs, arquivo_specs=arquivo_specs, params=params,
                                          composicoes=False)
            else:
                r = {'formatos': {}, 'devolucoes': [], 'kv': None}
            fontes, lista_fontes, faces = fontes_do_job(pasta, estado_job)
            assets, asset_por_camada = assets_das_camadas(pasta, ctx['laudo'])
            lido_ = lido(pasta, estado_job, ctx['laudo'], ctx['briefing'], r['formatos'], lista_fontes, teto)
    except nd.ErroDerivacao as e:
        raise ErroTela(str(e), e.motivo) from None
    except nucleo.ErroJob as e:
        raise ErroTela(str(e), 'job_ocupado' if int(e.codigo) == int(Codigo.OCUPADO) else 'nao_e_job') from None

    def face_de(ps):
        if not ps:
            return None
        f, _metodo, _n = casamento.casar(ps, faces)
        return f['id'] if f is not None and f['id'] in fontes else None

    from desdobra.tela import edicao
    b, laudo = ctx['briefing'], ctx['laudo']
    base = pecas_base(laudo, asset_por_camada, face_de)

    def com_previas_dos_quadros(l):
        # a previa de cada prancheta no passo 1: as camadas dela como estao no KV, so desenho
        for q in l['quadros']:
            q['palco'] = palco_do_documento(laudo, base, ctx['resolvidas'], q['id'])
        return l
    com_previas_dos_quadros(lido_)
    previas = {fid: palco(d, r['kv'], laudo, base) for fid, d in r['formatos'].items()}
    brutos = {}
    gals = {}
    if espera is None:
        gals = galerias(ctx, r['kv'], laudo, base, r['formatos'], abas(laudo, b, r['formatos']), specs=specs,
                        arquivo_specs=arquivo_specs, params=params, brutos=brutos)
    for fid, gal in gals.items():
        previas[fid]['galeria'] = gal
        dv = previas[fid]['devolucao']
        dv['texto'] = texto_da_devolucao(dv['motivo'], len(gal['variantes']))
    n_variantes = {fid: len(gal['variantes']) for fid, gal in gals.items()}
    quadro = ctx['info'].get('quadro')
    kv_palco = palco_kv(r['kv'], laudo, base) if espera is None else \
        palco_do_documento(laudo, base, ctx['resolvidas'], quadro)
    estado = {'esquema': ESQUEMA, 'job_id': estado_job['job_id'], 'somente_leitura': True,
              'briefing_origem': b['cabecalho']['origem'],
              'mestre': {'largura': laudo['documento']['largura'], 'altura': laudo['documento']['altura']},
              'orientacoes': abas(laudo, b, r['formatos'], n_variantes), 'fontes': lista_fontes,
              'assets': [{'id': i} for i in sorted(assets)], 'devolucoes': len(r['devolucoes']),
              'lido': lido_,
              'funcoes': {'arvore': arvore(laudo, b, ctx['resolvidas'], quadro),
                          'resumo': resumo_das_funcoes(b, ctx['resolvidas']), 'palco_kv': kv_palco,
                          'decisoes': decisoes_do_passo_2(laudo, quadro)},
              'passo_3': {'aguarda_passo_2': espera is not None, 'texto': espera or '', 'passo_2_aplicado': aplicado},
              'faltam': [],
              'edicao': {'tolerancia_alinhamento': limites.valor('derivacao.alinhamento_intencao_tolerancia')}}
    familias = {g['id']: [x['id'] for co in g['composicoes'] for x in co['formatos']]
                for o in estado['orientacoes'] for g in o['grupos']}
    from desdobra.briefing import salvar
    estado['briefing'] = dict(salvar.situacao_na_tela(pasta, familias), avisos=_avisos_do_job(pasta))
    if espera is not None:
        editor = None
    else:
        editor = edicao.Editor(ctx, r['kv'], laudo, base, r['formatos'], brutos, familias,
                               [f for f in faces if f['id'] in fontes], specs=specs, arquivo_specs=arquivo_specs,
                               params=params)
    versoes = {gid: sorted(editor.versoes(gid)) if editor else [] for gid in familias}
    pecas = {gid: impressao_das_pecas(fids, r['formatos'], versoes[gid]) for gid, fids in familias.items()}
    estado['faltam'] = faltam(lido_, r['formatos'], n_variantes, familias,
                              familias_confirmadas(pasta, familias, por_confirmar(r['formatos']), pecas))

    def recarregar():
        novo_job = nucleo.ler_estado(pasta)
        novo_lido = com_previas_dos_quadros(lido(pasta, novo_job, laudo, b, r['formatos'], lista_fontes, teto))
        return dict(estado, lido=novo_lido,
                    faltam=faltam(novo_lido, r['formatos'], n_variantes, familias,
                                  familias_confirmadas(pasta, familias, por_confirmar(r['formatos']), pecas)),
                    briefing=dict(salvar.situacao_na_tela(pasta, familias), avisos=_avisos_do_job(pasta)))

    conteudo = {'estado': estado, 'previas': previas, 'assets': assets, 'fontes': fontes, 'recarregar': recarregar,
                'editar': editor.previa if editor is not None else _sem_previa,
                'familias': {gid: {'formatos': fids, 'versoes': versoes[gid], 'pecas': pecas[gid],
                                   'por_confirmar': sorted(set(fids) & por_confirmar(r['formatos']))}
                             for gid, fids in familias.items()}}

    def atualizador(feita, atual):
        def atualizar():
            if mb.hashes_atuais(pasta) != arquivos_feitos:
                # o laudo, as specs, o design system ou as fontes mudaram com a tela aberta (o ato de spec do passo
                # 1): os formatos e o briefing de onde a tela parte sao outros
                return montar(pasta, teto)
            nova = assinatura_do_passo_2(pasta)
            if nova == feita:
                return None
            if ctx is ctx_base and _escolhas_do_passo_1(pasta) == passo_1 and                     com_o_passo_2_do_rascunho(pasta, ctx_base) is ctx_base:
                # o passo 2 mudou e ainda nao fecha, como antes: as familias e as previas sao as mesmas, e so o aviso
                # do passo 3 muda (sem derivar de novo a cada clique do DA)
                p3 = dict(atual['estado']['passo_3'], texto=espera_do_passo_3(pasta, ctx_base) or '',
                          passo_2_aplicado=_sem_passo_2(pasta))
                novo = dict(atual, estado=dict(atual['estado'], passo_3=p3),
                            recarregar=lambda: dict(recarregar(), passo_3=p3))
                novo['atualizar'] = atualizador(nova, novo)
                return novo
            return montar(pasta, teto)
        return atualizar
    conteudo['atualizar'] = atualizador(assinatura, conteudo)
    return conteudo
