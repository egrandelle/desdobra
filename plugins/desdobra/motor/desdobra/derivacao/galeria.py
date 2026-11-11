# -*- coding: utf-8 -*-
"""Galeria de variantes para o formato sem familia (decisoes-v1.md, 164 e as notas de 05/11).

Nenhum formato volta ao DA sem sugestao, e o desdobra parte de um KV so: na troca de orientacao e na proporcao fora
da faixa de familia, o motor monta de 3 a derivacao.galeria_variantes_max variantes de fato diferentes, so com os
blocos do proprio KV (sem modelo pronto e sem nada aprendido de outras pecas); o DA escolhe uma e ajusta no palco. Sem
regra fixa de rediagramacao: cada eixo de variacao e uma opcao da galeria.

Os blocos: o conteudo da mestre cortado em atomos na ordem de leitura (as linhas da mestre vertical; os itens da
horizontal, coluna por coluna); o legal fino perto da borda fica colado a ela; a cena e a arte que sangram ficam de
fundo. Os eixos de variacao:
  - estrutura: a melhor particao dos atomos em trilhas (colunas ou linhas) no formato, ou a melhor do outro tipo
    (lado a lado no lugar de empilhado, ou o contrario);
  - ordem: a da mestre, ou espelhada ao longo do lado maior do quadro;
  - imagem: a cena de fundo inteiro, ou o conteudo reunido numa parte do lado maior (derivacao.galeria_conteudo_fracao)
    e a imagem livre no resto, dos dois lados; a arte do KV que sangra em parte dos lados vira um bloco nessa faixa.
Nas faixas (derivacao.galeria_faixa_razao_min), a galeria abre com o conteudo no inicio e a imagem no fim, e com o
inverso, como opcoes entre as outras (a tendencia de leitura que o Duda citou, nunca regra).

Cada variante passa pelo solver do repositorio como uma mestre sintetica do tamanho do formato: as caixas do fluxo sao
a mestre, e a regra de cada elemento vai dividida pela escala que o fluxo ja deu, para o piso da 133 continuar relativo
a regra verdadeira. Depois a variante e conferida contra a mestre verdadeira (quadro, area segura, sobreposicao nova,
piso da 133, distancia da 135 e a validacao do motor) e ganha avisos, que nunca bloqueiam.

O layout editado pelo DA no palco passa pela mesma conferencia. O piso da 133 ou da 135 que o elemento mexido ou
escalado pelo DA fura e decisao dele (decisoes_do_da; M7b, D5, pergunta 10 do plano): sai das falhas ("Pede ajuste")
com o valor a vista. O elemento que o solver mexeu continua falha, e a validacao do motor continua devolvendo o formato.

So previa, em memoria: nada aqui grava arquivo, e o que o "desdobra derivar" grava nao muda (como o motor guarda a
proposta ainda esta em aberto com o Duda). Origem: o prototipo da galeria de 05/11 (revisado) sobre o fluxo B do
prototipo aprender-referencias, sem os priors aprendidos.
"""
import copy
import itertools
import math
import statistics

from desdobra import limites
from desdobra.derivacao import escala as mod_escala
from desdobra.derivacao import formatos as mod_formatos
from desdobra.derivacao import nucleo as mod_nucleo
from desdobra.derivacao import solver as mod_solver
from desdobra.derivacao import validacao as mod_validacao

DESEMPATE = 1e-12  # numero-neutro: folga numerica ao comparar a pontuacao de duas particoes
FOLGA_COTA = 1e-9  # numero-neutro: folga numerica da cota de cima da pontuacao (so corta o que certamente perde)
MESMA_ESCALA = 1e-6  # numero-neutro: a escala do fluxo igual a provisoria (a reserva do legal nao muda mais)
FOLGA_PISO = 1e-9  # numero-neutro: folga numerica do piso da 133
# id: (estrutura, espelhar, lado da imagem livre). "melhor": a melhor particao; "outra": a melhor do outro tipo
VARIANTES = {'reorganizado': ('melhor', False, None), 'espelhado': ('melhor', True, None),
             'outra_estrutura': ('outra', False, None), 'imagem_livre_fim': ('melhor', False, 'fim'),
             'imagem_livre_inicio': ('melhor', False, 'inicio')}
ORDEM = ('reorganizado', 'espelhado', 'outra_estrutura', 'imagem_livre_fim', 'imagem_livre_inicio')
ORDEM_FAIXA = ('imagem_livre_fim', 'imagem_livre_inicio', 'reorganizado', 'outra_estrutura', 'espelhado')
ROTULO = {'titulo': 'o título', 'texto_de_apoio': 'o texto', 'cta': 'a chamada', 'url_ou_contato': 'o contato',
          'texto_legal': 'o legal', 'informacao_de_evento': 'a informação', 'destaque_numerico': 'o destaque',
          'icone_de_cta': 'o ícone', 'logo_principal': 'a marca', 'assinatura_institucional': 'a assinatura',
          'selo': 'o selo', 'logo_de_parceiro': 'os logos', 'grafismo': 'o grafismo', 'sujeito': 'o produto',
          'imagem': 'a imagem', 'fundo': 'o fundo'}
ROTULO_GERAL = 'o elemento'
# M7b, D5: os pisos que a decisao do DA fura sem pedir ajuste (133 e 135); o resto das falhas continua falha
PISOS_DO_DA = ('abaixo_do_piso_da_regra', 'distancia_menor_que_na_mestre')
# revisao 1 da fase D do M7b: a borda do KV em que o asset acaba, na frase do corte a vista (corte_a_mostra)
BORDAS_DO_KV = {'esq': 'na borda esquerda', 'topo': 'no topo', 'dir': 'na borda direita', 'base': 'na base'}


# ------------------------------------------------------------------ apoio
def _uniao(caixas):
    return [min(c[0] for c in caixas), min(c[1] for c in caixas), max(c[2] for c in caixas), max(c[3] for c in caixas)]


def _sobra(a0, a1, b0, b1):
    """Comprimento da sobreposicao de dois intervalos (negativo: a distancia entre eles)."""
    return min(a1, b1) - max(a0, b0)


def _eixo_longo(largura, altura):
    return 'x' if largura >= altura else 'y'


def _rotulo(e):
    return ROTULO.get(e['funcao'], ROTULO_GERAL)


def _maiuscula(texto):
    return texto[0].upper() + texto[1:]


def _numero(v):
    """Numero da tela: uma casa, com virgula, sem ",0"."""
    t = ('%.1f' % v).replace('.', ',')
    return t[:-2] if t.endswith(',0') else t


def _juntar(rotulos):
    if len(rotulos) == 1:
        return rotulos[0]
    return ', '.join(rotulos[:-1]) + ' e ' + rotulos[-1]


def em_fluxo(e):
    """Elemento que a galeria reposiciona: conteudo ou objeto solto que nao sangra."""
    return (mod_solver.conteudo(e) or mod_solver.objeto_solto(e)) and not any(e['sangra'].values())


# ------------------------------------------------------------------ os blocos da mestre
def analisar(kv):
    """Atomos de conteudo da mestre na ordem de leitura, os colados a borda, a estrutura da mestre (colunas, k), o vao
    tipico entre atomos, a caixa do conteudo e a margem da mestre em fracao do lado curto."""
    Wm, Hm = float(kv['largura']), float(kv['altura'])
    curto = min(Wm, Hm)
    margem_cola = limites.valor('derivacao.galeria_colado_margem_max')
    espessura_cola = limites.valor('derivacao.galeria_colado_espessura_max')
    colados, itens = [], []
    for e in kv['elementos']:
        if not em_fluxo(e):
            continue
        c = e['caixa']
        lado = None
        if e['funcao'] == 'texto_legal':
            for nome, marg, esp in (('esq', c[0] / Wm, (c[2] - c[0]) / Wm), ('dir', (Wm - c[2]) / Wm, (c[2] - c[0]) / Wm),
                                    ('topo', c[1] / Hm, (c[3] - c[1]) / Hm), ('base', (Hm - c[3]) / Hm, (c[3] - c[1]) / Hm)):
                if marg < margem_cola and esp < espessura_cola:
                    lado = nome
        if lado:
            colados.append((e, lado))
        else:
            itens.append(e)
    vertical = Hm > Wm
    atomos = _atomos(itens, vertical, curto)
    if vertical:
        atomos.sort(key=lambda a: (a['caixa'][1], a['caixa'][0]))
        estrutura = ('colunas', 1)
    else:
        colunas = []
        for a in sorted(atomos, key=lambda a: a['caixa'][0]):
            for col in colunas:
                cc = _uniao([x['caixa'] for x in col])
                if _sobra(cc[0], cc[2], a['caixa'][0], a['caixa'][2]) > 0:
                    col.append(a)
                    break
            else:
                colunas.append([a])
        atomos = [a for col in colunas for a in sorted(col, key=lambda a: a['caixa'][1])]
        for k, col in enumerate(colunas):
            for a in col:
                a['col_mestre'] = k
        estrutura = ('colunas', len(colunas))
    vaos = []
    for a, b in zip(atomos, atomos[1:]):
        ca, cb = a['caixa'], b['caixa']
        g = max(cb[1] - ca[3], cb[0] - ca[2], ca[1] - cb[3], ca[0] - cb[2])
        if g > 0:
            vaos.append(g)
    margem_min = limites.valor('derivacao.galeria_margem_min_lado_curto')
    vao = statistics.median(vaos) if vaos else limites.valor('derivacao.galeria_vao_padrao_lado_curto') * curto
    margem = min([min(e['caixa'][0], e['caixa'][1], Wm - e['caixa'][2], Hm - e['caixa'][3]) for e in itens]
                 or [margem_min * curto])
    return {'atomos': atomos, 'colados': colados, 'estrutura': estrutura, 'vao': vao,
            'bbox': _uniao([a['caixa'] for a in atomos]) if atomos else [0.0, 0.0, Wm, Hm],
            'margem_rel': max(margem_min, margem / curto), 'Wm': Wm, 'Hm': Hm}


def _atomos(itens, vertical, curto):
    """Itens que se sobrepoem (ou, na mestre vertical, lado a lado na mesma linha) formam um atomo; atomo fino demais
    junta ao vizinho mais perto."""
    vao_linha = limites.valor('derivacao.galeria_linha_vao_lado_curto') * curto
    minimo = limites.valor('derivacao.galeria_atomo_min_lado_curto') * curto
    pai = list(range(len(itens)))

    def raiz(k):
        while pai[k] != k:
            k = pai[k]
        return k

    for i, j in itertools.combinations(range(len(itens)), 2):
        a, b = itens[i]['caixa'], itens[j]['caixa']
        ox, oy = _sobra(a[0], a[2], b[0], b[2]), _sobra(a[1], a[3], b[1], b[3])
        if (ox > 0 and oy > 0) or (vertical and oy > 0 and -ox < vao_linha):
            ri, rj = raiz(i), raiz(j)
            pai[max(ri, rj)] = min(ri, rj)
    grupos = {}
    for k in range(len(itens)):
        grupos.setdefault(raiz(k), []).append(itens[k])
    atomos = [{'els': g, 'caixa': _uniao([e['caixa'] for e in g])} for g in grupos.values()]
    mudou = True
    while mudou and len(atomos) > 1:
        mudou = False
        for a in atomos:
            c = a['caixa']
            if min(c[2] - c[0], c[3] - c[1]) >= minimo:
                continue

            def distancia(b, c=c):
                d = b['caixa']
                return max(0, max(d[0] - c[2], c[0] - d[2])) + max(0, max(d[1] - c[3], c[1] - d[3]))
            b = min((x for x in atomos if x is not a), key=distancia)
            b['els'] += a['els']
            b['caixa'] = _uniao([e['caixa'] for e in b['els']])
            atomos.remove(a)
            mudou = True
            break
    return atomos


# ------------------------------------------------------------------ particoes e fluxo
def particoes(n):
    """Toda divisao de n itens em ordem em trilhas contiguas."""
    for k in range(1, n + 1):
        for cortes in itertools.combinations(range(1, n), k - 1):
            b = (0,) + cortes + (n,)
            yield [list(range(b[i], b[i + 1])) for i in range(k)]


def _dims(an):
    return [(a['caixa'][2] - a['caixa'][0], a['caixa'][3] - a['caixa'][1]) for a in an['atomos']]


def avaliar_particao(an, quadro, s_cap, tipo, part):
    """(pontuacao, escala, escala que cabe, espessura de cada trilha). A pontuacao e a escala com uma penalidade pela
    distancia a estrutura da mestre (desempata para o que a mestre ja faz)."""
    dims, g = _dims(an), an['vao']
    FW, FH = quadro[2] - quadro[0], quadro[3] - quadro[1]
    ke, kc = (0, 1) if tipo == 'colunas' else (1, 0)
    esp = [max(dims[i][ke] for i in t) for t in part]
    comp = [sum(dims[i][kc] for i in t) + g * (len(t) - 1) for t in part]
    tot_e, tot_c = (FW, FH) if tipo == 'colunas' else (FH, FW)
    s_fit = min(tot_e / (sum(esp) + g * (len(part) - 1)), tot_c / max(comp))
    s = min(s_fit, s_cap)
    tipo_m, k_m = an['estrutura']
    dist = abs(len(part) - k_m) + (0 if tipo == tipo_m else 1)
    if tipo_m == 'colunas' and k_m > 1 and tipo == 'colunas' and len(part) == k_m:
        # as mesmas colunas da mestre: nenhuma mudanca de estrutura
        if all(len({an['atomos'][i].get('col_mestre') for i in t}) == 1 for t in part):
            dist = 0
    return s * (1 - limites.valor('derivacao.galeria_penalidade_estrutura') * dist), s, s_fit, esp


def melhor_particao(an, quadro, s_cap, tipos=('colunas', 'linhas'), excluir=()):
    """(pontuacao, escala, escala que cabe, tipo, particao, espessuras) de maior pontuacao, ou None. Percorre as
    particoes na ordem de particoes() e corta o ramo cuja cota de cima da pontuacao nao passa da melhor ate ali: devolve
    a mesma particao da busca em todas, com o mesmo desempate, sem o custo dobrar a cada atomo."""
    dims, g = _dims(an), an['vao']
    n = len(dims)
    FW, FH = quadro[2] - quadro[0], quadro[3] - quadro[1]
    pen = limites.valor('derivacao.galeria_penalidade_estrutura')
    tipo_m, k_m = an['estrutura']
    melhor = None

    def nao_passa(cota):
        return melhor is not None and cota * (1 + FOLGA_COTA) + FOLGA_COTA <= melhor[0] + DESEMPATE

    for tipo in tipos:
        ke, kc = (0, 1) if tipo == 'colunas' else (1, 0)
        tot_e, tot_c = (FW, FH) if tipo == 'colunas' else (FH, FW)
        esp_a, comp_a = [d[ke] for d in dims], [d[kc] for d in dims]
        for k in range(1, n + 1):
            fator = 1 - pen * (abs(k - k_m) + (0 if tipo == tipo_m else 1))

            def cota(i, j, soma_e, maior_c):
                """A pontuacao maxima de qualquer particao em k trilhas que fecha j trilhas ate o atomo i (soma das
                espessuras e maior comprimento delas): o resto leva ao menos o atomo mais espesso numa trilha e o mais
                fino em cada outra, e o maior comprimento nunca fica abaixo da media do que falta."""
                r = k - j  # de 1 a k: a ultima trilha e sempre o resto
                resto_e, resto_c = esp_a[i:], comp_a[i:]
                e = soma_e + max(resto_e) + (r - 1) * min(resto_e)
                c = max(maior_c, max(resto_c), (sum(resto_c) + g * (n - i - r)) / r)
                den_e = e + g * (k - 1)
                s_ub = min(tot_e / den_e if den_e > 0 else math.inf, tot_c / c if c > 0 else math.inf, s_cap)
                return s_ub * fator if fator > 0 else 0.0

            def descer(i, j, cortes, soma_e, maior_c):
                nonlocal melhor
                if nao_passa(cota(i, j, soma_e, maior_c)):
                    return
                if j == k - 1:
                    b = [0] + cortes + [n]
                    part = [list(range(b[x], b[x + 1])) for x in range(k)]
                    if (tipo, tuple(len(t) for t in part)) in excluir:
                        return
                    score, s, s_fit, esp = avaliar_particao(an, quadro, s_cap, tipo, part)
                    if melhor is None or score > melhor[0] + DESEMPATE:
                        melhor = (score, s, s_fit, tipo, part, esp)
                    return
                for fim in range(i + 1, n - (k - 1 - j) + 1):
                    e_t = max(esp_a[i:fim])
                    c_t = sum(comp_a[i:fim]) + g * (fim - i - 1)
                    descer(fim, j + 1, cortes + [fim], soma_e + e_t, max(maior_c, c_t))

            descer(0, 0, [], 0.0, 0.0)
    return melhor


def _isotonica(v):
    """Ajuste nao decrescente de minimos quadrados (juntar vizinhos que violam a ordem)."""
    blocos = []
    for x in v:
        blocos.append([x, 1])
        while len(blocos) > 1 and blocos[-2][0] > blocos[-1][0]:
            a, b = blocos.pop(), blocos.pop()
            blocos.append([(a[0] * a[1] + b[0] * b[1]) / (a[1] + b[1]), a[1] + b[1]])
    saida = []
    for m, n in blocos:
        saida += [m] * n
    return saida


def _empilhar(tam, alvo, lo, hi, vao):
    """Inicio de cada item empilhado em ordem num eixo, com o vao entre eles, dentro de [lo, hi], com o centro o mais
    perto possivel (minimos quadrados) do alvo."""
    off, acc = [], 0.0
    for t in tam:
        off.append(acc)
        acc += t + vao
    q = _isotonica([a - t / 2.0 - o for a, t, o in zip(alvo, tam, off)])  # numero-neutro: centro do item
    topo = max(hi - off[-1] - tam[-1], lo)
    return [min(max(x, lo), topo) + o for x, o in zip(q, off)]


def _cruz(c0, c1, b0, b1, trilha, a):
    """Deslocamento do atomo atraves da trilha: o centro dele fica no lugar relativo que tinha na caixa do conteudo."""
    cr = ((c0 + c1) / 2.0 - b0) / (b1 - b0) if b1 > b0 else 0.5  # numero-neutro: centro
    return min(max(cr * trilha - a / 2.0, 0.0), max(trilha - a, 0.0))  # numero-neutro: centro


def colocar(an, quadro, s, tipo, part, esp, espelhar, distrib):
    """Caixas dos elementos dos atomos para (tipo, particao) na escala s. espelhar: inverte ao longo do lado maior do
    quadro (a ordem das trilhas, quando elas correm nele; a ordem dentro de cada trilha, senao). distrib: 'espalhada'
    (as trilhas com o mesmo espaco entre si e as bordas), 'inicio' ou 'fim' (juntas contra aquele lado)."""
    at, g = an['atomos'], an['vao']
    fx0, fy0, fx1, fy1 = quadro
    FW, FH = fx1 - fx0, fy1 - fy0
    dims = _dims(an)
    colunas = tipo == 'colunas'
    trilhas_no_longo = colunas == (_eixo_longo(FW, FH) == 'x')
    ordem_t = list(range(len(part)))
    inverte_dentro = espelhar and not trilhas_no_longo
    if espelhar and trilhas_no_longo:
        ordem_t = ordem_t[::-1]
    main0, main_tot = (fx0, FW) if colunas else (fy0, FH)
    esp_s = [v * s for v in esp]
    sobra = main_tot - sum(esp_s)
    if distrib == 'espalhada':
        passo = sobra / (len(part) + 1) if len(part) > 1 else sobra / 2.0  # numero-neutro: centro
        pos = main0 + passo
    else:
        passo = g * s
        tot = sum(esp_s) + passo * (len(part) - 1)
        pos = main0 if distrib == 'inicio' else main0 + main_tot - tot
    un = len(part) > 1 or distrib != 'espalhada'
    bb = an['bbox']
    lo_c, hi_c = (fy0, fy1) if colunas else (fx0, fx1)
    Dm = an['Hm'] if colunas else an['Wm']
    k0 = 1 if colunas else 0
    caixas = {}
    for k in ordem_t:
        seq = list(part[k])
        larg = [dims[i][k0] * s for i in seq]
        alvo = [lo_c + (at[i]['caixa'][k0] + at[i]['caixa'][k0 + 2]) / 2.0 / Dm * (hi_c - lo_c) for i in seq]  # numero-neutro: centro
        # a marca que fecha a pilha vai para o fim dela (o fluxo B sem priors)
        if len(seq) > 1 and any(el['classe'] == 'marca' for el in at[seq[-1]]['els']):
            alvo[-1] = hi_c - larg[-1] / 2.0  # numero-neutro: centro
        if inverte_dentro:
            seq, larg = seq[::-1], larg[::-1]
            alvo = [lo_c + hi_c - a for a in alvo[::-1]]
        for i, ini in zip(seq, _empilhar(larg, alvo, lo_c, hi_c, g * s)):
            c = at[i]['caixa']
            aw, ah = dims[i][0] * s, dims[i][1] * s
            if colunas:
                trilha = esp_s[k] if un else FW
                x = (pos if un else fx0) + _cruz(c[0], c[2], bb[0], bb[2], trilha, aw)
                y = ini
            else:
                trilha = esp_s[k] if un else FH
                y = (pos if un else fy0) + _cruz(c[1], c[3], bb[1], bb[3], trilha, ah)
                x = ini
            for el in at[i]['els']:
                m = el['caixa']
                caixas[el['id']] = [x + s * (m[0] - c[0]), y + s * (m[1] - c[1]), x + s * (m[2] - c[0]),
                                    y + s * (m[3] - c[1])]
        pos += esp_s[k] + passo
    return caixas


# ------------------------------------------------------------------ cena e arte
def _fundo(e, bm, bf, W, H):
    """Elemento fora do fluxo (cena, arte que sangra): a escala da regra, crescida para cada lado que sangra continuar
    sangrando; posicao proporcional a da mestre, presa aos lados que sangram."""
    Wm, Hm = bm
    c, a = e['caixa'], e.get('caixa_asset') or e['caixa']
    s = mod_escala.escala(e['regra'], bm, bf) or 1.0
    sg = e['sangra']
    if sg['esq'] and sg['dir']:
        s = max(s, W / (a[2] - a[0]))
    if sg['topo'] and sg['base']:
        s = max(s, H / (a[3] - a[1]))
    w, h = (c[2] - c[0]) * s, (c[3] - c[1]) * s
    x0 = (c[0] + c[2]) / 2.0 / Wm * W - w / 2.0  # numero-neutro: centro
    y0 = (c[1] + c[3]) / 2.0 / Hm * H - h / 2.0  # numero-neutro: centro
    dl, dt, dr, db = (a[0] - c[0]) * s, (a[1] - c[1]) * s, (a[2] - c[2]) * s, (a[3] - c[3]) * s
    if sg['esq'] and sg['dir']:
        x0 = min(-dl, max(x0, W - w - dr))
    elif sg['esq']:
        x0 = -dl
    elif sg['dir']:
        x0 = W - w - dr
    if sg['topo'] and sg['base']:
        y0 = min(-dt, max(y0, H - h - db))
    elif sg['topo']:
        y0 = -dt
    elif sg['base']:
        y0 = H - h - db
    return [x0, y0, x0 + w, y0 + h]


def arte_parcial(kv):
    """A maior base que sangra em parte dos lados (nao em todos) e cobre derivacao.galeria_arte_area_min do canvas:
    a arte que vira bloco na faixa da imagem livre."""
    A = float(kv['largura']) * float(kv['altura'])
    minimo = limites.valor('derivacao.galeria_arte_area_min')
    melhor = None
    for e in kv['elementos']:
        sg = e['sangra']
        if mod_solver.conteudo(e) or e['classe'] != 'base' or not any(sg.values()) or all(sg.values()):
            continue
        c = e['caixa']
        area = (c[2] - c[0]) * (c[3] - c[1])
        if area >= minimo * A and (melhor is None or area > melhor[0]):
            melhor = (area, e)
    return melhor[1] if melhor else None


def _arte_em_banda(e, banda, longo, W, H):
    """A arte cobrindo a faixa livre, presa a borda de fora e centrada atraves; sangra no lado de fora e nos dois
    lados atraves (o lado de dentro fica no canvas)."""
    c = e['caixa']
    w0, h0 = c[2] - c[0], c[3] - c[1]
    b0, b1, lado = banda
    if longo == 'x':
        s = max((b1 - b0) / w0, H / h0)
        w, h = w0 * s, h0 * s
        x0, y0 = (W - w if lado == 'fim' else 0.0), (H - h) / 2.0  # numero-neutro: centro
        sg = {'esq': lado == 'inicio', 'dir': lado == 'fim', 'topo': True, 'base': True}
    else:
        s = max((b1 - b0) / h0, W / w0)
        w, h = w0 * s, h0 * s
        x0, y0 = (W - w) / 2.0, (H - h if lado == 'fim' else 0.0)  # numero-neutro: centro
        sg = {'esq': True, 'dir': True, 'topo': lado == 'inicio', 'base': lado == 'fim'}
    return [x0, y0, x0 + w, y0 + h], sg


# ------------------------------------------------------------------ contexto do formato
def _contexto(ctx, kv, formato, specs=None, arquivo_specs=None, params=None):
    """O que a galeria precisa de um formato: composicao, areas da folha, base do calculo, regra de cada elemento,
    escala de referencia do conteudo e os blocos da mestre."""
    if specs is None:
        specs, arquivo_specs = mod_formatos.specs_do_job(ctx['pasta']) if ctx.get('pasta') else ({}, None)
    params = params or mod_formatos.parametros(ctx.get('pasta'), ctx['briefing'])
    W, H = (float(v) for v in mod_formatos.composicao(formato))
    areas = mod_formatos.areas(formato, specs.get(formato['chave']), arquivo_specs)
    bf = mod_formatos.base_do_formato(formato, areas, params['base']['valor'])
    bm = (float(kv['largura']), float(kv['altura']))
    regras = {e['id']: mod_escala.escala(e['regra'], bm, bf) for e in kv['elementos']}
    rc = [regras[e['id']] for e in kv['elementos'] if mod_solver.conteudo(e) and regras[e['id']]]
    an = analisar(kv)
    base_q = (areas.get('area_segura') or areas.get('area_util') or {}).get('caixa') or [0.0, 0.0, W, H]
    ins = an['margem_rel'] * min(W, H)
    quadro = [max(base_q[0], ins), max(base_q[1], ins), min(base_q[2], W - ins), min(base_q[3], H - ins)]
    return {'ctx': ctx, 'kv': kv, 'formato': formato, 'W': W, 'H': H, 'areas': areas, 'bf': bf, 'bm': bm,
            'regras': regras, 'regra_ref': statistics.median(rc) if rc else 1.0, 'an': an, 'quadro': quadro}


def _ordem(cf):
    W, H = cf['W'], cf['H']
    faixa = max(W, H) / min(W, H) >= limites.valor('derivacao.galeria_faixa_razao_min')
    return ORDEM_FAIXA if faixa else ORDEM


# ------------------------------------------------------------------ uma variante
def _reservar(cf, q_cont, s):
    """O quadro do fluxo sem a faixa de cada legal colado, na escala s."""
    an, quadro = cf['an'], cf['quadro']
    q = list(q_cont)
    for e, lado in an['colados']:
        c = e['caixa']
        t = ((c[2] - c[0]) if lado in ('esq', 'dir') else (c[3] - c[1])) * s + an['vao'] * s
        if lado == 'esq':
            q[0] = max(q[0], quadro[0] + t)
        elif lado == 'dir':
            q[2] = min(q[2], quadro[2] - t)
        elif lado == 'topo':
            q[1] = max(q[1], quadro[1] + t)
        else:
            q[3] = min(q[3], quadro[3] - t)
    return q


def _mesma_geometria(a, b):
    """Uma trilha so de um tipo e a mesma coisa que cada atomo numa trilha do outro tipo."""
    la, lb = [len(t) for t in a[4]], [len(t) for t in b[4]]
    n = sum(la)
    return (la == [n] and lb == [1] * n) or (lb == [n] and la == [1] * n)


def _escolher(cf, q, modo, forcada):
    """A particao da variante no quadro q, ou None quando a estrutura nao existe neste KV."""
    an, s_cap = cf['an'], cf['regra_ref']
    melhor = melhor_particao(an, q, s_cap)
    if forcada is not None:
        tipo, tamanhos = forcada
        if sum(tamanhos) != len(an['atomos']):
            return None
        cortes = list(itertools.accumulate(tamanhos))
        part = [list(range(a, b)) for a, b in zip([0] + cortes[:-1], cortes)]
        score, s, s_fit, esp = avaliar_particao(an, q, s_cap, tipo, part)
        return score, s, s_fit, tipo, part, esp
    if modo == 'melhor':
        return melhor
    outro = 'linhas' if melhor[3] == 'colunas' else 'colunas'
    escolha = melhor_particao(an, q, s_cap, tipos=(outro,))
    if escolha is not None and _mesma_geometria(melhor, escolha):
        escolha = melhor_particao(an, q, s_cap, tipos=(outro,), excluir={(outro, tuple(len(t) for t in escolha[4]))})
        if escolha is not None and _mesma_geometria(melhor, escolha):
            escolha = None
    return escolha


def _gerar(cf, vid, forcada=None):
    """A variante vid (VARIANTES) do formato: caixas depois do solver, a estrutura e o que a conferencia precisa. None
    quando a estrutura nao existe neste KV (a outra estrutura com um atomo so). forcada: (tipo, tamanhos das trilhas)
    tirada de outro membro do grupo."""
    modo, espelhar, lado_img = VARIANTES[vid]
    an, kv, W, H, quadro = cf['an'], cf['kv'], cf['W'], cf['H'], cf['quadro']
    longo = _eixo_longo(W, H)
    q_cont, banda = list(quadro), None
    if lado_img is not None:
        k0, k1 = (0, 2) if longo == 'x' else (1, 3)
        L, D = quadro[k1] - quadro[k0], (W if longo == 'x' else H)
        fr = limites.valor('derivacao.galeria_conteudo_fracao')
        if lado_img == 'fim':
            q_cont[k1] = quadro[k0] + fr * L
            banda = (q_cont[k1], D, 'fim')
        else:
            q_cont[k0] = quadro[k1] - fr * L
            banda = (0.0, q_cont[k0], 'inicio')
    s_prov, escolha, q = cf['regra_ref'], None, q_cont
    for _volta in range(2):  # numero-neutro: reserva o legal com a escala provisoria e refaz uma vez com a do fluxo
        q = _reservar(cf, q_cont, s_prov)
        if not an['atomos']:
            escolha = (s_prov, s_prov, s_prov, None, [], [])
            break
        escolha = _escolher(cf, q, modo, forcada)
        if escolha is None:
            return None
        if abs(escolha[1] - s_prov) < MESMA_ESCALA:
            break
        s_prov = escolha[1]
    _score, s, s_fit, tipo, part, esp = escolha
    distrib = 'espalhada'
    if lado_img is not None and (tipo == 'colunas') == (longo == 'x'):
        # as trilhas correm no lado maior: juntas do lado do conteudo, longe da imagem
        distrib = 'inicio' if lado_img == 'fim' else 'fim'
    caixas = colocar(an, q, s, tipo, part, esp, espelhar, distrib) if part else {}
    bm = cf['bm']
    for e, lado in an['colados']:
        c = e['caixa']
        w, h = (c[2] - c[0]) * s, (c[3] - c[1]) * s
        cx, cy = (c[0] + c[2]) / 2.0 / bm[0] * W, (c[1] + c[3]) / 2.0 / bm[1] * H  # numero-neutro: centro
        if lado in ('esq', 'dir'):
            x0 = quadro[0] if lado == 'esq' else quadro[2] - w
            y0 = min(max(cy - h / 2.0, quadro[1]), quadro[3] - h)  # numero-neutro: centro
        else:
            y0 = quadro[1] if lado == 'topo' else quadro[3] - h
            x0 = min(max(cx - w / 2.0, quadro[0]), quadro[2] - w)  # numero-neutro: centro
        caixas[e['id']] = [x0, y0, x0 + w, y0 + h]
    arte = arte_parcial(kv) if banda is not None else None
    sangra = {}
    for e in kv['elementos']:
        if e['id'] in caixas:
            continue
        if arte is not None and e['id'] == arte['id']:
            caixas[e['id']], sangra[e['id']] = _arte_em_banda(e, banda, longo, W, H)
        else:
            caixas[e['id']] = _fundo(e, bm, cf['bf'], W, H)
    caixas, falha = _resolver(cf, caixas, sangra)
    return {'id': vid, 'caixas': caixas, 'sangra': sangra, 'falha_solver': falha, 'arte': arte,
            'tipo': tipo, 'part': part, 'espelhar': espelhar, 'lado_img': lado_img, 's': s, 's_fit': s_fit,
            'eixo_quadro': _eixo_longo(q[2] - q[0], q[3] - q[1])}


def _resolver(cf, caixas, sangra, do_da=()):
    """O fluxo vai ao solver do repositorio como mestre sintetica do tamanho do formato: as caixas do fluxo sao a
    mestre, e a regra de cada elemento vai dividida pela escala que o fluxo deu (o piso da 133 fica relativo a regra
    verdadeira). do_da: os elementos que o DA mexeu no palco (M7b, D1); a regra deles e o tamanho que o DA deu (escala 1
    sobre a mestre sintetica), para o encaixe refeito nunca puxar um elemento do grupo para um tamanho e o outro para
    outro; o piso da 133 contra a regra verdadeira continua na conferencia (conferir_edicao). Devolve (caixas, nome da
    obrigatoria que nao fecha ou None); sem fechar, ficam as caixas do fluxo."""
    W, H, kv = cf['W'], cf['H'], cf['kv']
    do_da = set(do_da)
    sint, regras = [], []
    for e in kv['elementos']:
        c, m = caixas[e['id']], e['caixa']
        k = (c[2] - c[0]) / (m[2] - m[0]) if m[2] > m[0] else 1.0
        x = copy.deepcopy(e)
        x['caixa'] = list(c)
        a = e.get('caixa_asset') or m
        x['caixa_asset'] = [c[0] + k * (a[0] - m[0]), c[1] + k * (a[1] - m[1]), c[0] + k * (a[2] - m[0]),
                            c[1] + k * (a[3] - m[1])]
        if e['id'] in sangra:
            x['sangra'] = sangra[e['id']]
        sint.append(x)
        r = cf['regras'][e['id']]
        regras.append(1.0 if e['id'] in do_da else ((r / k) if r and k else r))
    try:
        resolvidas, _esc, _r = mod_solver.resolver(sint, (W, H), (W, H), cf['areas'], regras)
    except mod_solver.NaoFecha as ex:
        return caixas, ex.restricao['nome']
    return {e['id']: c for e, c in zip(kv['elementos'], resolvidas)}, None


# ------------------------------------------------------------------ a frase do DA
def _rotulos_dos_atomos(an, idx):
    vistos = []
    for i in idx:
        for el in an['atomos'][i]['els']:
            r = _rotulo(el)
            if r not in vistos:
                vistos.append(r)
    return vistos


def _lugares(n, eixo):
    if eixo == 'x':
        nomes = {1: ['no centro'], 2: ['à esquerda', 'à direita'], 3: ['à esquerda', 'no centro', 'à direita']}  # numero-neutro: quantas trilhas
        return nomes.get(n, ['na coluna %d' % (k + 1) for k in range(n)])
    nomes = {1: ['no centro'], 2: ['em cima', 'embaixo'], 3: ['em cima', 'no meio', 'embaixo']}  # numero-neutro: quantas trilhas
    return nomes.get(n, ['na linha %d' % (k + 1) for k in range(n)])


def descrever(cf, v):
    """Uma linha em portugues para o DA. O espelho e descrito pelo mesmo lado maior que o desenhou (o do quadro do
    fluxo): no quadrado, o lado maior do formato e o do quadro podem ser outros (defeito da revisao do prototipo)."""
    an, part = cf['an'], v['part']
    if not part:
        return 'Só a imagem'
    nome_img = 'a arte' if v['arte'] is not None else 'a imagem'
    if v['lado_img'] is not None:
        longo = _eixo_longo(cf['W'], cf['H'])
        inicio, fim = ('à esquerda', 'à direita') if longo == 'x' else ('em cima', 'embaixo')
        lado_c, lado_i = (inicio, fim) if v['lado_img'] == 'fim' else (fim, inicio)
        todos = _juntar(_rotulos_dos_atomos(an, [i for t in part for i in t]))
        return '%s %s, %s livre %s' % (_maiuscula(todos), lado_c, nome_img, lado_i)
    eixo_t = 'x' if v['tipo'] == 'colunas' else 'y'
    trilhas_no_longo = eixo_t == v['eixo_quadro']
    inverte_dentro = v['espelhar'] and not trilhas_no_longo
    ordem = list(range(len(part)))[::-1] if v['espelhar'] and trilhas_no_longo else list(range(len(part)))
    if len(part) == 1:
        modo = 'em linha' if eixo_t == 'y' else 'empilhado'
        seq = part[0][::-1] if inverte_dentro else part[0]
        rot = _rotulos_dos_atomos(an, seq)
        lista = rot[0] if len(rot) == 1 else ', '.join(rot[:-1]) + ', depois ' + rot[-1]
        return 'Tudo %s (%s), %s de fundo' % (modo, lista, nome_img)
    lugares = _lugares(len(part), eixo_t)
    pedacos = ['%s %s' % (_juntar(_rotulos_dos_atomos(an, part[k][::-1] if inverte_dentro else part[k])), lugares[pos])
               for pos, k in enumerate(ordem)]
    return _maiuscula('; '.join(pedacos)) + ', %s de fundo' % nome_img


# ------------------------------------------------------------------ conferencia
def _escalas(kv, caixas):
    saida = {}
    for e in kv['elementos']:
        c, m = caixas[e['id']], e['caixa']
        if m[2] > m[0]:
            saida[e['id']] = (c[2] - c[0]) / (m[2] - m[0])
        else:
            saida[e['id']] = (c[3] - c[1]) / (m[3] - m[1]) if m[3] > m[1] else 1.0
    return saida


def _item(codigo, texto, elementos, **medidas):
    d = {'codigo': codigo, 'texto': texto, 'elementos': list(elementos)}
    if medidas:
        d['medidas'] = medidas
    return d


def sem_elementos(cf, apagados):
    """O contexto do formato sem os elementos que o DA apagou no palco (decisoes-v1.md, 169)."""
    if not apagados:
        return cf
    if 'esperado' not in cf:
        cf['esperado'] = mod_nucleo._esperado(cf['ctx'], cf['kv'])
    kv = dict(cf['kv'], elementos=[e for e in cf['kv']['elementos'] if e['id'] not in set(apagados)])
    return dict(cf, kv=kv, kv_inteiro=cf.get('kv_inteiro') or cf['kv'])


def reencaixar(cf, caixas, sangra, apagados=(), do_da=()):
    """O encaixe refeito pelo solver do repositorio depois de uma edicao do DA no palco (desdobra.tela.edicao): as
    caixas editadas sao a mestre sintetica do formato, como na variante (_resolver), e os elementos que o DA mexeu
    (do_da) ficam com o tamanho que ele deu. Devolve (caixas, nome da obrigatoria que nao fecha ou None)."""
    return _resolver(sem_elementos(cf, apagados), caixas, sangra, do_da)


def contexto_do_formato(ctx, kv, formato, *, specs=None, arquivo_specs=None, params=None):
    """O contexto que a galeria monta para um formato (para a edicao no palco reaproveitar entre as edicoes)."""
    cf = _contexto(ctx, kv, formato, specs, arquivo_specs, params)
    cf['esperado'] = mod_nucleo._esperado(ctx, kv)
    return cf


def conferir_edicao(cf, caixas, sangra, apagados=()):
    """(falhas, avisos, validacoes reprovadas) do layout editado pelo DA, contra a mestre verdadeira; o elemento
    apagado sai da conta e o inventario o registra."""
    return _conferir(sem_elementos(cf, apagados), caixas, sangra, apagados=apagados, com_validacoes=True)


def decisoes_do_da(cf, falhas, do_da, do_solver=(), da_partida=()):
    """(falhas que ficam, decisoes do DA) do layout editado no palco (M7b, D5; pergunta 10 do plano). A falha de piso
    (PISOS_DO_DA: a escala abaixo do piso da 133, a distancia menor que a da 135) com um elemento que o DA mexeu ou
    escalou (do_da) e decisao dele, quando nenhum elemento dela foi mexido pelo solver (do_solver): sai das falhas e
    ganha o texto com o valor a vista. O resto (fora do quadro, area segura, sobreposicao, validacao do motor, solver
    que nao fecha) continua falha. Revisao 1 da fase D: o piso que a versao de partida ja furava (da_partida: os pares
    (codigo, elementos ordenados) das falhas dela) continua falha, porque o DA nao o furou; a distancia de duas caixas
    que se sobrepoem (zero ou menos) tambem, porque a sobreposicao ja pede ajuste e px negativo nao diz nada ao DA. A
    ordem das listas e a das falhas."""
    do_da, do_solver = set(do_da), set(do_solver)
    da_partida = set(da_partida)
    por_id = {e['id']: e for e in cf['kv']['elementos']}
    ficam, decisoes = [], []
    for f in falhas:
        els = set(f['elementos'])
        m = f.get('medidas') or {}
        if f['codigo'] not in PISOS_DO_DA or not els & do_da or els & do_solver or \
                (f['codigo'], tuple(sorted(els))) in da_partida or \
                (f['codigo'] == 'distancia_menor_que_na_mestre' and float(m.get('distancia_px', 1)) <= 0):
            ficam.append(f)
            continue
        nomes = [_rotulo(por_id[k]) if k in por_id else ROTULO_GERAL for k in f['elementos']]
        if f['codigo'] == 'abaixo_do_piso_da_regra':
            piso = m.get('minimo_da_regra', limites.valor('derivacao.escala_conteudo_min_da_regra'))
            texto = '%s fica com %d%% da escala prevista. O mínimo é %d%%.' % (
                _maiuscula(nomes[0]), round(m['fracao_da_regra'] * 100), round(piso * 100))  # numero-neutro: porcentagem
        else:
            texto = '%s ficam a %s px um do outro. O KV pede pelo menos %s px.' % (
                _maiuscula(_juntar(nomes)), _numero(m['distancia_px']), _numero(m['minimo_px']))
        decisoes.append(dict(f, texto=texto))
    return ficam, decisoes


def corte_a_mostra(cf, falhas, cortes):
    """As falhas do layout editado no palco com o corte do KV a vista (revisao 1 da fase D do M7b). cortes: {id:
    [lados]} dos elementos que o DA tirou da borda em que o asset deles acaba no KV (o compositor corta na borda do
    documento). Cada um ganha a falha corte_a_mostra, com a frase que diz onde estava o corte, no lugar da conferencia
    generica do motor (validacao_reprova do enquadramento so dele); a validacao obrigatoria continua devolvendo o
    formato. As outras falhas ficam na ordem delas."""
    por_id = {e['id']: e for e in cf['kv']['elementos']}
    ficam = [f for f in falhas if not (f['codigo'] == 'validacao_reprova' and
                                       (f.get('medidas') or {}).get('validacao') == 'enquadramento' and
                                       len(f['elementos']) == 1 and f['elementos'][0] in cortes)]
    for k in sorted(cortes):
        nome = _rotulo(por_id[k]) if k in por_id else ROTULO_GERAL
        onde = _juntar([BORDAS_DO_KV[lado] for lado in cortes[k]])
        ficam.append(_item('corte_a_mostra', '%s acaba %s do KV, onde a imagem foi cortada. Nesta posição, esse corte '
                           'aparece na peça.' % (_maiuscula(nome), onde), [k], lados=list(cortes[k])))
    return ficam


def fora_da_peca(cf, falhas, ids):
    """As falhas do layout editado no palco com os elementos que o DA levou inteiros para fora da peca (revisao 2 da
    fase D do M7b; desdobra.tela.edicao.fora_da_peca). Cada um ganha a falha fora_do_quadro com a frase que diz o que
    fazer, no lugar da conferencia generica (fora_do_quadro e validacao_reprova do enquadramento so dele); a validacao
    obrigatoria continua devolvendo o formato. As outras falhas ficam na ordem delas."""
    if not ids:
        return falhas
    por_id = {e['id']: e for e in cf['kv']['elementos']}
    ids = set(ids)
    ficam = [f for f in falhas if not (len(f['elementos']) == 1 and f['elementos'][0] in ids and (
        f['codigo'] == 'fora_do_quadro' or (f['codigo'] == 'validacao_reprova' and
                                            (f.get('medidas') or {}).get('validacao') == 'enquadramento')))]
    for k in sorted(ids):
        nome = _rotulo(por_id[k]) if k in por_id else ROTULO_GERAL
        varios = nome.split(' ', 1)[0] in ('os', 'as')
        ficam.append(_item('fora_do_quadro', '%s %s fora do formato e não %s nele. Arraste de volta ou use Apagar.' % (
            _maiuscula(nome), 'ficaram' if varios else 'ficou', 'aparecem' if varios else 'aparece'), [k]))
    return ficam


def elementos_do_layout(cf, caixas, sangra, apagados=()):
    """Os elementos do layout editado, na forma dos elementos de derivacao/<formato>.json."""
    return _elementos(sem_elementos(cf, apagados), {'caixas': caixas, 'sangra': sangra})


def _conferir(cf, caixas, sangra, apagados=(), com_validacoes=False):
    """Falhas obrigatorias contra a mestre verdadeira e avisos de elemento. Devolve (falhas, avisos); com_validacoes,
    (falhas, avisos, nomes das validacoes do motor que reprovam)."""
    kv, W, H, areas = cf['kv'], cf['W'], cf['H'], cf['areas']
    els = kv['elementos']
    tol = limites.valor('derivacao.enquadramento_tolerancia_px')
    tol_col = limites.valor('derivacao.colisao_tolerancia_px')
    seg = (areas.get('area_segura') or {}).get('caixa')
    piso = limites.valor('derivacao.escala_conteudo_min_da_regra')
    piso_d = limites.valor('derivacao.distancia_entre_linhas_min')
    esc, regra = _escalas(kv, caixas), cf['regras']
    cont = [e for e in els if mod_solver.conteudo(e)]
    fora, fora_seg, abaixo, sobre, perto = [], [], [], [], []
    for e in cont:
        c = caixas[e['id']]
        # o lado que sangra (no KV, ou por decisao do DA no palco, M7b, D4) pode passar da borda: o quadro corta
        sg = sangra.get(e['id'], e['sangra'])
        if (c[0] < -tol and not sg['esq']) or (c[1] < -tol and not sg['topo']) or \
                (c[2] > W + tol and not sg['dir']) or (c[3] > H + tol and not sg['base']):
            fora.append(e)
        if seg is not None and e['classe'] in mod_solver.CLASSES_AREA_SEGURA and (
                c[0] < seg[0] - tol or c[1] < seg[1] - tol or c[2] > seg[2] + tol or c[3] > seg[3] + tol):
            fora_seg.append(e)
        if regra[e['id']] and esc[e['id']] < piso * regra[e['id']] - FOLGA_PISO:
            abaixo.append((e, esc[e['id']] / regra[e['id']]))
    for a, b in itertools.combinations(els, 2):
        if not mod_solver.par_que_nao_sobrepoe(a, b):
            continue
        ka, kb = a['caixa'], b['caixa']
        if _sobra(ka[0], ka[2], kb[0], kb[2]) > 0 and _sobra(ka[1], ka[3], kb[1], kb[3]) > 0:
            continue  # ja se sobrepoem na mestre
        ca, cb = caixas[a['id']], caixas[b['id']]
        if _sobra(ca[0], ca[2], cb[0], cb[2]) > tol_col and _sobra(ca[1], ca[3], cb[1], cb[3]) > tol_col:
            sobre.append((a, b))
    # 135 contra a mestre verdadeira: o vizinho de conteudo mais perto em cada eixo, na mestre do KV (como o solver o
    # escolhe); na variante, o par fica a pelo menos piso_d da distancia da mestre na escala media dos dois. O legal
    # colado a borda fica fora (decisoes-v1.md, 165): a distancia dele na mestre vem da largura do KV, e ele segue preso
    # a borda com a margem minima
    colados = {e['id'] for e, _lado in cf['an']['colados']}
    for a in cont:
        if a['id'] in colados:
            continue
        ca = a['caixa']
        for (k0, k1), (o0, o1) in (((0, 2), (1, 3)), ((1, 3), (0, 2))):
            melhor = None
            for b in cont:
                cb = b['caixa']
                if b is a or b['id'] in colados or _sobra(ca[o0], ca[o1], cb[o0], cb[o1]) <= 0:
                    continue
                gap = cb[k0] - ca[k1]
                if gap > 0 and (melhor is None or gap < melhor[0]):
                    melhor = (gap, b)
            if melhor is None:
                continue
            gap, b = melhor
            va, vb = caixas[a['id']], caixas[b['id']]
            sep = max(vb[0] - va[2], va[0] - vb[2], vb[1] - va[3], va[1] - vb[3])
            minimo = piso_d * gap * (esc[a['id']] + esc[b['id']]) / 2.0  # numero-neutro: media das duas escalas
            if sep < minimo - tol:
                perto.append((a, b, sep, minimo))
    val = _validacoes(cf, caixas, sangra, esc, apagados)
    falhas = []
    for e in fora:
        falhas.append(_item('fora_do_quadro', '%s sai do formato.' % _maiuscula(_rotulo(e)), [e['id']]))
    for e in fora_seg:
        falhas.append(_item('fora_da_area_segura', '%s passa da área segura.' % _maiuscula(_rotulo(e)), [e['id']]))
    for e, fr in abaixo:
        falhas.append(_item('abaixo_do_piso_da_regra', '%s fica com %d%% da escala prevista, abaixo do mínimo de %d%%.'
                             % (_maiuscula(_rotulo(e)), round(fr * 100), round(piso * 100)), [e['id']],  # numero-neutro: porcentagem
                             fracao_da_regra=round(fr, 4), minimo_da_regra=piso))  # numero-neutro: casas da medida
    for a, b in sobre:
        falhas.append(_item('sobreposicao_nova', '%s e %s passam a se sobrepor.' % (_maiuscula(_rotulo(a)), _rotulo(b)),
                             [a['id'], b['id']]))
    for a, b, sep, minimo in perto:
        falhas.append(_item('distancia_menor_que_na_mestre', '%s e %s ficam mais perto do que o KV permite.'
                             % (_maiuscula(_rotulo(a)), _rotulo(b)), [a['id'], b['id']],
                             distancia_px=round(sep, 1), minimo_px=round(minimo, 1)))
    for v in mod_validacao.reprovadas(val):
        falhas.append(_item('validacao_reprova', 'A conferência do motor reprova esta versão.', v['elementos'],
                             validacao=v['nome']))
    avisos = _avisos_de_elemento(cf, caixas, sangra, esc)
    if com_validacoes:
        return falhas, avisos, sorted({v['nome'] for v in mod_validacao.reprovadas(val)})
    return falhas, avisos


def _validacoes(cf, caixas, sangra, esc, apagados=()):
    """As validacoes do motor (desdobra.derivacao.validacao) do layout, contra a mestre verdadeira; o elemento apagado
    pelo DA sai da conta do inventario."""
    kv, W, H, areas = cf['kv'], cf['W'], cf['H'], cf['areas']
    els, regra = kv['elementos'], cf['regras']
    aplicados = mod_nucleo._aplicados(kv, [regra[e['id']] for e in els])
    for x in aplicados:
        if x['id'] in sangra:
            x['sangra'] = sangra[x['id']]
    if 'esperado' not in cf:
        cf['esperado'] = mod_nucleo._esperado(cf['ctx'], kv)
    return mod_validacao.validar((W, H), areas, aplicados, [caixas[e['id']] for e in els], [esc[e['id']] for e in els],
                                 mod_nucleo._kv_por_id(cf.get('kv_inteiro') or kv), cf['esperado'], apagados=apagados)


def validacoes_do_layout(cf, caixas, sangra, apagados=()):
    """As validacoes do motor do layout editado pelo DA, na forma de derivacao/<formato>.json (para a derivacao gravar
    a proposta confirmada; desdobra.derivacao.proposta)."""
    cf = sem_elementos(cf, apagados)
    return _validacoes(cf, caixas, sangra, _escalas(cf['kv'], caixas), apagados)


def _avisos_de_elemento(cf, caixas, sangra, esc):
    kv, W, H, regra = cf['kv'], cf['W'], cf['H'], cf['regras']
    corpo_min = limites.valor('derivacao.corpo_minimo_legal_px')
    vis_min = limites.valor('derivacao.galeria_fundo_visivel_min')
    graf_max = limites.valor('derivacao.galeria_grafismo_sobre_regra_max')
    pequenos, fundos, grafismos = [], [], []
    for e in kv['elementos']:
        if e['classe'] == 'texto' and e.get('corpo_px'):
            corpo = float(e['corpo_px']) * esc[e['id']] * float(e.get('escala_na_mestre') or 1.0)
            if corpo < corpo_min:
                pequenos.append((corpo, e))
        if mod_solver.conteudo(e) or not any(sangra.get(e['id'], e['sangra']).values()):
            continue
        c = caixas[e['id']]
        area = max(0.0, c[2] - c[0]) * max(0.0, c[3] - c[1])
        vis = max(0.0, min(c[2], W) - max(c[0], 0.0)) * max(0.0, min(c[3], H) - max(c[1], 0.0))
        if e['funcao'] == 'fundo' and area and vis / area < vis_min:
            fundos.append((vis / area, e))
        if e['funcao'] == 'grafismo' and regra[e['id']] and esc[e['id']] / regra[e['id']] > graf_max:
            grafismos.append((esc[e['id']] / regra[e['id']], e))
    avisos = []
    if pequenos:
        corpo, e = min(pequenos, key=lambda x: x[0])
        avisos.append(_item('texto_abaixo_de_8px', '%s fica com corpo de %s px, abaixo de %s px.'
                             % (_maiuscula(_rotulo(e)), _numero(corpo), _numero(corpo_min)),
                             [x[1]['id'] for x in pequenos], menor_corpo_px=round(corpo, 1)))
    if fundos:
        fr = min(x[0] for x in fundos)
        avisos.append(_item('fundo_pouco_visivel', 'Só %d%% do fundo aparece no formato, menos de %d%%.'
                             % (round(fr * 100), round(vis_min * 100)), [x[1]['id'] for x in fundos],  # numero-neutro: porcentagem
                             fracao_visivel=round(fr, 3)))  # numero-neutro: casas da medida
    if grafismos:
        r = max(x[0] for x in grafismos)
        avisos.append(_item('grafismo_acima_da_regra', 'O grafismo fica com %s vezes a escala da regra dele.' % _numero(r),
                             [x[1]['id'] for x in grafismos], vezes_a_regra=round(r, 2)))
    return avisos


def conferir(ctx, kv, formato, elementos, *, specs=None, arquivo_specs=None, params=None):
    """Confere um layout do formato (os elementos de uma variante, ajustados ou nao) contra a mestre verdadeira.
    Devolve {'falhas_obrigatorias', 'avisos'}; nao grava nada."""
    cf = _contexto(ctx, kv, formato, specs, arquivo_specs, params)
    caixas = {e['id']: [float(x) for x in e['caixa']] for e in elementos}
    por_id = {e['id']: e for e in kv['elementos']}
    sangra = {e['id']: dict(e['transformacao']['sangra']) for e in elementos
              if e.get('transformacao') and e['transformacao'].get('sangra') != por_id[e['id']]['sangra']}
    falhas, avisos = _conferir(cf, caixas, sangra)
    return {'falhas_obrigatorias': falhas, 'avisos': avisos}


def _avisos_da_variante(cf, v):
    avisos = []
    if v['sangra']:
        avisos.append(_item('sangria_da_arte_mudou', 'A arte vira um bloco na parte livre e muda os lados em que sangra.',
                             sorted(v['sangra'])))
    q = v['s_fit'] / cf['regra_ref'] if cf['regra_ref'] else 1.0
    # so o conteudo abaixo do piso da 133: o solver que nao fecha ja volta como falha solver_nao_fecha, com o nome dele
    if q < limites.valor('derivacao.escala_conteudo_min_da_regra'):
        avisos.append(_item('conteudo_nao_cabe', 'O conteúdo só cabe com %d%% da escala prevista. Vale ver se algum texto '
                             'secundário pode sair.' % round(min(q, 1.0) * 100), [], fracao_que_cabe=round(q, 3)))  # numero-neutro: porcentagem e casas
    return avisos


def distancia(cf, a, b):
    """Media do deslocamento do centro de cada elemento de conteudo entre duas variantes, sobre a diagonal."""
    diag = math.hypot(cf['W'], cf['H'])
    ds = []
    for e in cf['kv']['elementos']:
        if mod_solver.conteudo(e):
            ca, cb = a['caixas'][e['id']], b['caixas'][e['id']]
            ds.append(math.hypot((ca[0] + ca[2] - cb[0] - cb[2]) / 2.0, (ca[1] + ca[3] - cb[1] - cb[3]) / 2.0) / diag)  # numero-neutro: centro
    return statistics.mean(ds) if ds else 0.0


# ------------------------------------------------------------------ saida
def _elementos(cf, v):
    """Os elementos no formato, na forma dos elementos de derivacao/<formato>.json (caixa, escala, transformacao)."""
    ctx, q, casas_e = cf['ctx'], mod_nucleo.CASAS_PX, mod_nucleo.CASAS_ESCALA
    esc = _escalas(cf['kv'], v['caixas'])
    saida = []
    for e in cf['kv']['elementos']:
        c = [mod_nucleo._q(x, q) for x in v['caixas'][e['id']]]
        s = mod_nucleo._q(esc[e['id']] * float(e.get('escala_na_mestre') or 1.0), casas_e)
        doc = e['caixa_doc']
        r = cf['regras'][e['id']]
        origem = next((ctx['resolvidas'][x]['por'] for x in e['layer_ids']
                       if x in ctx['resolvidas'] and ctx['resolvidas'][x]['raiz'] == e['raiz']),
                      (ctx['resolvidas'].get(e['layer_ids'][0]) or {}).get('por'))
        saida.append({'id': e['id'], 'raiz': e['raiz'], 'funcao': e['funcao'], 'classe': e['classe'],
                      'layer_ids': e['layer_ids'], 'texto': e['texto'], 'regra': e['regra'],
                      'escala_regra': None if r is None else round(r, casas_e), 'ancora': list(e['ancora']),
                      'caixa_mestre': [mod_nucleo._q(x, q) for x in e['caixa']], 'caixa': c, 'escala': s,
                      'transformacao': {'s': s, 'origem_doc': [doc[0], doc[1]], 'destino': c[:2],
                                        'recorte_doc': e.get('caixa_asset_doc') or doc,
                                        'sangra': dict(v['sangra'].get(e['id'], e['sangra']))},
                      'corpo_px': None if e.get('corpo_px') is None else round(e['corpo_px'] * s, 4),  # numero-neutro: casas do corpo
                      'quebras': e.get('quebras') or ('congeladas_da_mestre' if e['texto'] else None),
                      'origem_funcao': origem})
    return saida


def _saida(cf, v, ordem):
    falhas, avisos = _conferir(cf, v['caixas'], v['sangra'])
    if v['falha_solver']:
        falhas.append(_item('solver_nao_fecha', 'As restrições da folha e do KV não fecham nesta versão.', [],
                             restricao=v['falha_solver']))
    return {'id': v['id'], 'ordem': ordem, 'descricao': descrever(cf, v), 'elementos': _elementos(cf, v),
            'avisos': avisos + _avisos_da_variante(cf, v), 'falhas_obrigatorias': falhas,
            'estrutura': {'tipo': v['tipo'], 'trilhas': [len(t) for t in v['part']], 'espelhada': v['espelhar'],
                          'imagem_livre': v['lado_img']},
            'situacao': 'proposta' if not v['falha_solver'] else 'proposta_sem_solver',
            'escala_do_conteudo': round(v['s'], mod_nucleo.CASAS_ESCALA)}


def _galeria(cf, limite):
    duplicada = limites.valor('derivacao.galeria_duplicada_distancia_max')
    mantidas = []
    for vid in _ordem(cf):
        if len(mantidas) >= limite:
            break
        v = _gerar(cf, vid)
        if v is None or any(distancia(cf, v, k) < duplicada for k in mantidas):
            continue
        mantidas.append(v)
    return mantidas


def variantes(ctx, kv, formato, limite=None, *, specs=None, arquivo_specs=None, params=None):
    """A galeria de um formato: [{'id', 'ordem', 'descricao', 'elementos', 'avisos', 'falhas_obrigatorias',
    'estrutura', 'situacao', 'escala_do_conteudo'}], de 3 a limite (derivacao.galeria_variantes_max) variantes
    diferentes (a quase igual a uma anterior, a menos de derivacao.galeria_duplicada_distancia_max, sai). ctx e kv: o
    contexto da derivacao e a mestre do KV (derivacao.nucleo.contexto e mestre_do_kv); formato: o do briefing. Sem
    specs, le as do job (ctx['pasta']). So previa: nao grava nada."""
    limite = int(limites.valor('derivacao.galeria_variantes_max') if limite is None else limite)
    cf = _contexto(ctx, kv, formato, specs, arquivo_specs, params)
    return [_saida(cf, v, n) for n, v in enumerate(_galeria(cf, limite), 1)]


def variante_para_grupo(ctx, kv, formatos, escolha, *, specs=None, arquivo_specs=None, params=None):
    """Uma estrutura so para todos os membros de um grupo de proporcao (derivacao.grupo_proporcao_dif_max): a variante
    escolhida (id) com a estrutura (tipo e trilhas) de um dos membros, a que deixa o pior membro melhor (mais membros
    sem falha obrigatoria, depois a maior escala do pior membro relativa a mesma variante sozinha nele). Devolve
    {'variante', 'estrutura', 'membros': {id do formato: variante}, 'membros_sem_falha', 'pior_escala_relativa',
    'candidatas'}. So previa: nao grava nada."""
    cfs = [(f['id'], _contexto(ctx, kv, f, specs, arquivo_specs, params)) for f in formatos]
    proprias = {fid: _gerar(cf, escolha) for fid, cf in cfs}
    estruturas = []
    for fid, _cf in cfs:
        v = proprias[fid]
        if v is not None and v['tipo'] is not None:
            e = (v['tipo'], tuple(len(t) for t in v['part']))
            if e not in estruturas:
                estruturas.append(e)
    candidatas = []
    for est in estruturas or [None]:
        membros, sem_falha, pior = {}, 0, None
        for fid, cf in cfs:
            v = _gerar(cf, escolha, forcada=est) if est is not None else proprias[fid]
            if v is None:
                break
            saida = _saida(cf, v, 1)
            membros[fid] = saida
            sem_falha += 0 if saida['falhas_obrigatorias'] else 1
            propria = proprias[fid]
            rel = v['s'] / propria['s'] if propria is not None and propria['s'] else 1.0
            pior = rel if pior is None else min(pior, rel)
        else:
            candidatas.append({'estrutura': None if est is None else {'tipo': est[0], 'trilhas': list(est[1])},
                               'membros_sem_falha': sem_falha, 'pior_escala_relativa': round(pior, 6),  # numero-neutro: casas da escala
                               'membros': membros})
    melhor = max(candidatas, key=lambda c: (c['membros_sem_falha'], c['pior_escala_relativa']))
    return {'variante': escolha, 'estrutura': next(iter(melhor['membros'].values()))['estrutura'],
            'membros': melhor['membros'], 'membros_sem_falha': melhor['membros_sem_falha'],
            'pior_escala_relativa': melhor['pior_escala_relativa'],
            'candidatas': [{k: c[k] for k in ('estrutura', 'membros_sem_falha', 'pior_escala_relativa')} for c in candidatas]}
