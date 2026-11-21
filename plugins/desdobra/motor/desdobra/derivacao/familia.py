# -*- coding: utf-8 -*-
"""A familia segue o arquivo de edicao (decisao 199, 18/11; etapas E1 e E2 do desenho final).

Cada familia tem um arquivo de edicao (arquivo_de_edicao): o de maior area na composicao, medida em pe; no empate, o
sem giro e depois o primeiro da lista. A escolha gravada no rascunho fica (como o id da nº178). So ele aceita edicao
no palco. O layout que o DA aprovou nele (L*) vira um modelo (extrair_modelo), e cada outro arquivo sai do modelo por
uma conta fechada (transferir), nunca da partida propria nem por deltas (199, 2):
  - escala unica s = min(Lq_m/Lq_ref, Aq_m/Aq_ref) entre os quadros de margem, a do lado que aperta, igual para todo
    o conteudo. O arquivo de edicao e o maior, entao s <= 1: nada amplia alem do que o DA viu;
  - blocos de conteudo por eixo (union-find): os grupos do DA e os elementos que se sobrepoem andam juntos nos dois
    eixos; os que dividem uma linha (borda ou centro, derivacao.alinhamento_tolerancia_px) andam juntos naquele eixo,
    e o alinhamento continua. O interior do bloco vai em offset x s;
  - ancora por bloco e por eixo: a intencao explicita de alinhar (185) vence; senao, a borda mais perto do quadro (a
    margem ou a area segura); margens quase iguais (derivacao.alinhamento_intencao_tolerancia) dao o centro, ou a
    ancora da funcao no Design system confirmado, quando o DA a deu;
  - a sobra do eixo solto fica entre os blocos e nunca aproxima dois conteudos: o bloco que vem depois nunca anda
    menos que o de antes;
  - a base que sangra cresce (g >= 1) so o necessario para continuar sangrando, em volta do ponto da borda de dentro
    dela mais perto do conteudo que se relaciona com ela (o hospede). O ponto anda com o hospede, entao a diagonal
    fica no mesmo angulo e no mesmo lugar em relacao a ele. A forma que precisa crescer alem de
    derivacao.familia_crescimento_max deixa o arquivo pedindo ajuste (resposta do Duda em 18/11). O fundo puro
    (derivacao.bloco_fundo_fracao) cresce em volta do centro, levado em proporcao, como galeria._fundo, sem limite;
  - protecao de fundo: o conteudo nunca muda de fundo. Quando a ancora leva um conteudo do branco para a forma, ou o
    tira de dentro dela, o bloco volta a posicao rigida em relacao aquela forma (ancora_desfeita_pelo_fundo).
As relacoes do aprovado (relacoes, cada uma com id estavel) sao conferidas pela tinta da forma: a silhueta (poligono
ou grade, em fracao da caixa do asset) ou, sem ela, a caixa, com o aviso forma_conferida_pela_caixa. A relacao que se
perde passa pela escada do menor ajuste (ajustar_minimo, 199, 3): F1 anda o bloco dentro da sobra; F2 recua a forma
na normal da borda, sem perder a sangria e sem tirar conteudo de dentro dela; F3 diminui o bloco em volta da ancora
ate derivacao.familia_ajuste_escala_min, nunca abaixo do piso da 133 (pisos). A magnitude de cada uma e a menor que
devolve a folga do aprovado x s, por bissecao com passos fixos. Vence o menor custo (o maior deslocamento visivel em
px sobre o lado menor do arquivo); no empate, F1, F2, F3 (resposta 1 do Duda em 18/11). O ajuste nunca cria relacao
quebrada nova. O que nada resolve fica "Pede ajuste" com o valor. Todo ajuste e toda relacao quebrada levam frase.
Tudo na composicao em pe (o giro fica na entrega, 139 e 180). Funcoes puras: nada aqui le ou grava arquivo, e a
mesma entrada da a mesma saida, sem depender da ordem dos membros nem do hash do processo.
"""
import copy
import itertools
import math

from desdobra import limites

LADOS = ('esq', 'topo', 'dir', 'base')
EIXOS = ('x', 'y')
INDICES = {'x': (0, 2), 'y': (1, 3)}  # numero-neutro: indices da caixa [x0, y0, x1, y1]
QUADROS = ('margem', 'area_segura')
LADOS_DA_ANCORA = ('inicio', 'centro', 'fim')
# a intencao explicita de alinhar no quadro (185; desdobra.tela.edicao.ALVOS) e a ancora do Design system
ANCORA_DO_ALVO = {'margem_esquerda': 'inicio', 'centro_horizontal': 'centro', 'margem_direita': 'fim',
                  'topo': 'inicio', 'centro_vertical': 'centro', 'base': 'fim'}
ANCORA_DO_DS = {'esquerda': 'inicio', 'centro': 'centro', 'direita': 'fim', 'topo': 'inicio', 'meio': 'centro',
                'base': 'fim'}
PAPEIS = ('movel', 'base', 'fundo')
TIPOS = ('livre_da_tinta', 'dentro_da_tinta', 'sem_sobreposicao', 'distancia', 'no_quadro', 'na_area_segura',
         'alinhados')
TIPOS_DE_FUNDO = ('livre_da_tinta', 'dentro_da_tinta')
AJUSTES = ('F1', 'F2', 'F3')  # a ordem do empate (resposta 1 do Duda em 18/11)
CLASSES_AREA_SEGURA = ('texto', 'marca')
SITUACOES = ('igual', 'ajustado', 'pede_ajuste')
TINTA = '1#'  # o caractere da celula com tinta na grade da silhueta
METADE = 0.5  # numero-neutro: o meio
QUARTO = 0.25  # numero-neutro: o encolhimento da caixa na conferencia de dentro nunca passa do meio dela
IGUAL = 1e-9  # numero-neutro: folga numerica de duas medidas iguais, em px
AREA_IGUAL = 1e-6  # numero-neutro: folga relativa da area coberta (arredondamento do recorte do poligono)
PASSOS = 60  # numero-neutro: passos da bissecao (a precisao do float de 64 bits)
CASAS_CUSTO = 9  # numero-neutro: casas do custo no desempate (o arredondamento da conta, nao uma regra)
VOLTA = 360  # numero-neutro: graus de uma volta
POR_CENTO = 100.0  # numero-neutro: fracao para porcentagem


# ------------------------------------------------------------------ apoio de geometria
def _f(c):
    return [float(v) for v in c]


def _uniao(cs):
    return [min(c[0] for c in cs), min(c[1] for c in cs), max(c[2] for c in cs), max(c[3] for c in cs)]


def _sobra(a0, a1, b0, b1):
    """Comprimento da sobreposicao de dois intervalos (negativo: a distancia entre eles)."""
    return min(a1, b1) - max(a0, b0)


def _area(c):
    return max(0.0, c[2] - c[0]) * max(0.0, c[3] - c[1])


def _inter(a, b):
    return [max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])]


def _lado(q, eixo):
    i0, i1 = INDICES[eixo]
    return q[i1] - q[i0]


def _ponto(p, origem, destino, k):
    """O ponto levado pela semelhanca que leva origem a destino com a escala k. Escrita para a identidade ser exata
    (origem = destino e k = 1 devolvem p sem erro de arredondamento): transferir para a propria referencia da 0 px."""
    return [p[0] + (destino[0] - origem[0]) + (p[0] - origem[0]) * (k - 1.0),
            p[1] + (destino[1] - origem[1]) + (p[1] - origem[1]) * (k - 1.0)]


def _caixa_por(c, origem, destino, k):
    a = _ponto([c[0], c[1]], origem, destino, k)
    b = _ponto([c[2], c[3]], origem, destino, k)
    return [a[0], a[1], b[0], b[1]]


def _grampo(p, c):
    return [min(max(p[0], c[0]), c[2]), min(max(p[1], c[1]), c[3])]


def _cantos(c):
    return ([c[0], c[1]], [c[2], c[1]], [c[2], c[3]], [c[0], c[3]])


def _dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def _projecao(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = dx * dx + dy * dy
    if n <= 0:
        return list(a)
    t = min(1.0, max(0.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / n))
    return [a[0] + dx * t, a[1] + dy * t]


def _segmento_na_caixa(a, b, c):
    """O pedaco do segmento ab dentro da caixa c (Liang-Barsky), ou None."""
    t0, t1 = 0.0, 1.0
    dx, dy = b[0] - a[0], b[1] - a[1]
    for p, q in ((-dx, a[0] - c[0]), (dx, c[2] - a[0]), (-dy, a[1] - c[1]), (dy, c[3] - a[1])):
        if p == 0:
            if q < 0:
                return None
            continue
        t = q / p
        if p < 0:
            if t > t1:
                return None
            t0 = max(t0, t)
        else:
            if t < t0:
                return None
            t1 = min(t1, t)
    if t0 > t1:
        return None
    return [a[0] + dx * t0, a[1] + dy * t0], [a[0] + dx * t1, a[1] + dy * t1]


def _par_segmento_caixa(a, b, c):
    """(distancia, ponto no segmento, ponto na caixa) do par mais perto entre o segmento ab e a caixa c. Dois convexos
    disjuntos no plano: o par mais perto tem um vertice de um deles."""
    corte = _segmento_na_caixa(a, b, c)
    if corte is not None:
        p = [(corte[0][0] + corte[1][0]) * METADE, (corte[0][1] + corte[1][1]) * METADE]
        return 0.0, p, list(p)
    cands = [(_dist(p, _grampo(p, c)), list(p)) for p in (a, b)]
    cands += [(_dist(_projecao(q, a, b), q), _projecao(q, a, b)) for q in _cantos(c)]
    d = min(x[0] for x in cands)
    # a borda paralela ao lado do conteudo encosta num trecho inteiro: o ponto e o meio dele, e nao uma ponta
    perto = [p for dd, p in cands if dd <= d + IGUAL]
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = [(p[0] - a[0]) * dx + (p[1] - a[1]) * dy for p in perto]
    p0, p1 = perto[t.index(min(t))], perto[t.index(max(t))]
    p = [(p0[0] + p1[0]) * METADE, (p0[1] + p1[1]) * METADE]
    return d, p, _grampo(p, c)


def _intervalo_perto(a0, a1, b0, b1):
    """(ponto em a, ponto em b) mais perto num eixo."""
    if a1 < b0:
        return a1, b0
    if b1 < a0:
        return a0, b1
    m = (max(a0, b0) + min(a1, b1)) * METADE
    return m, m


def _par_caixas(t, c):
    """(distancia, ponto em t, ponto em c) do par mais perto entre duas caixas."""
    tx, cx = _intervalo_perto(t[0], t[2], c[0], c[2])
    ty, cy = _intervalo_perto(t[1], t[3], c[1], c[3])
    return math.hypot(tx - cx, ty - cy), [tx, ty], [cx, cy]


def _recortar(pts, c):
    """O poligono pts recortado pela caixa c (Sutherland-Hodgman)."""
    lados = ((0, c[0], True), (0, c[2], False), (1, c[1], True), (1, c[3], False))  # numero-neutro: eixos
    for eixo, lim, de_baixo in lados:
        if not pts:
            break
        saida = []
        for i in range(len(pts)):
            a, b = pts[i - 1], pts[i]
            da = a[eixo] >= lim if de_baixo else a[eixo] <= lim
            db = b[eixo] >= lim if de_baixo else b[eixo] <= lim
            if da != db:
                t = (lim - a[eixo]) / (b[eixo] - a[eixo])
                p = [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
                p[eixo] = lim
                saida.append(p)
            if db:
                saida.append(list(b))
        pts = saida
    return pts


def _area_poligono(pts):
    if len(pts) < 3:  # numero-neutro: um poligono tem pelo menos tres pontos
        return 0.0
    soma = 0.0
    for i in range(len(pts)):
        a, b = pts[i - 1], pts[i]
        soma += a[0] * b[1] - b[0] * a[1]
    return abs(soma) * METADE


def _no_contorno(a, b, W, H):
    """O segmento fica todo sobre a borda do canvas W x H (a borda do canvas nao e borda de dentro da forma)."""
    tol = IGUAL * max(W, H, 1.0)
    for i, lim in ((0, 0.0), (0, W), (1, 0.0), (1, H)):  # numero-neutro: eixos
        if abs(a[i] - lim) <= tol and abs(b[i] - lim) <= tol:
            return True
    return False


# ------------------------------------------------------------------ a tinta das bases
def _tinta(caixa_asset, silhueta, W, H, recorte=None):
    """(tinta, borda de dentro, sem silhueta) de uma base no espaco da referencia. A tinta e {'poligonos', 'caixas'};
    a silhueta vem em fracao da caixa do asset: {'poligono': [[u, v], ...]}, {'poligonos': [...]} ou {'grade':
    {'colunas', 'linhas', 'celulas': [texto por linha, de cima para baixo; '1' ou '#' e tinta]}}. Sem silhueta, a
    caixa do asset. A borda de dentro e o contorno da tinta dentro do canvas, sem o que fica sobre a borda dele.
    recorte (etapa E4): a caixa em que o render corta a pilha (o elemento acaba na borda do canvas da mestre,
    desdobra.derivacao.elementos): a tinta que passa dela nunca aparece, e sai daqui."""
    if recorte is not None:
        tinta, borda, sem = _tinta(caixa_asset, silhueta, W, H)
        r = _f(recorte)
        pols = [p for p in (_recortar(pol, r) for pol in tinta['poligonos']) if _area_poligono(p) > 0]
        cxs = [c for c in (_inter(c, r) for c in tinta['caixas']) if _area(c) > 0]
        cortada = []
        for p, q in borda:
            corte = _segmento_na_caixa(p, q, r)
            if corte is not None and _dist(*corte) > IGUAL:
                cortada.append([list(corte[0]), list(corte[1])])
        return {'poligonos': pols, 'caixas': cxs}, cortada, sem
    a = caixa_asset
    largura, altura = a[2] - a[0], a[3] - a[1]

    def em_px(u, v):
        return [a[0] + largura * float(u), a[1] + altura * float(v)]
    poligonos, caixas, segmentos = [], [], []
    sem = not silhueta
    if sem:
        caixas.append(list(a))
        segmentos += [(p, q) for p, q in zip(_cantos(a), _cantos(a)[1:] + _cantos(a)[:1])]
    elif silhueta.get('grade') is not None:
        g = silhueta['grade']
        n, m = int(g['colunas']), int(g['linhas'])
        cel = [[ch in TINTA for ch in str(linha)[:n].ljust(n, '0')] for linha in list(g['celulas'])[:m]]
        cel += [[False] * n for _ in range(m - len(cel))]

        def X(i):
            return a[0] + largura * i / n

        def Y(j):
            return a[1] + altura * j / m

        def tem(j, i):
            return 0 <= j < m and 0 <= i < n and cel[j][i]
        for j in range(m):
            i = 0
            while i < n:
                if not cel[j][i]:
                    i += 1
                    continue
                i0 = i
                while i < n and cel[j][i]:
                    i += 1
                caixas.append([X(i0), Y(j), X(i), Y(j + 1)])
        for i in range(n + 1):  # bordas verticais, juntas na coluna
            j = 0
            while j < m:
                if tem(j, i - 1) == tem(j, i):
                    j += 1
                    continue
                j0 = j
                while j < m and tem(j, i - 1) != tem(j, i):
                    j += 1
                segmentos.append(([X(i), Y(j0)], [X(i), Y(j)]))
        for j in range(m + 1):  # bordas horizontais, juntas na linha
            i = 0
            while i < n:
                if tem(j - 1, i) == tem(j, i):
                    i += 1
                    continue
                i0 = i
                while i < n and tem(j - 1, i) != tem(j, i):
                    i += 1
                segmentos.append(([X(i0), Y(j)], [X(i), Y(j)]))
    else:
        lista = silhueta.get('poligonos') or [silhueta['poligono']]
        for pol in lista:
            pts = [em_px(u, v) for u, v in pol]
            poligonos.append(pts)
            segmentos += [(pts[i - 1], pts[i]) for i in range(len(pts))]
    borda = []
    canvas = [0.0, 0.0, W, H]
    for p, q in segmentos:
        corte = _segmento_na_caixa(p, q, canvas)
        if corte is None or _dist(*corte) <= IGUAL or _no_contorno(corte[0], corte[1], W, H):
            continue
        borda.append([list(corte[0]), list(corte[1])])
    return {'poligonos': poligonos, 'caixas': caixas}, borda, sem


def _tinta_por(tinta, origem, destino, k):
    return {'poligonos': [[_ponto(p, origem, destino, k) for p in pol] for pol in tinta['poligonos']],
            'caixas': [_caixa_por(c, origem, destino, k) for c in tinta['caixas']]}


def _recortada(tinta, W, H):
    """A tinta que aparece: o render corta na borda do documento (131)."""
    canvas = [0.0, 0.0, W, H]
    pols = [p for p in (_recortar(pol, canvas) for pol in tinta['poligonos']) if _area_poligono(p) > 0]
    cxs = [c for c in (_inter(c, canvas) for c in tinta['caixas']) if _area(c) > 0]
    return {'poligonos': pols, 'caixas': cxs}


def _area_coberta(caixa, tinta):
    return sum(_area_poligono(_recortar(p, caixa)) for p in tinta['poligonos']) + \
        sum(_area(_inter(t, caixa)) for t in tinta['caixas'])


def _distancia(caixa, tinta):
    """(distancia, invade, ponto na tinta, ponto no conteudo) entre a caixa do conteudo e a tinta que aparece. invade:
    a caixa tem area sobre a tinta; a distancia e 0. Sem tinta, distancia infinita."""
    area = _area(caixa)
    if _area_coberta(caixa, tinta) > AREA_IGUAL * max(area, 1.0):
        return 0.0, True, None, None
    melhor = None
    for pol in tinta['poligonos']:
        for i in range(len(pol)):
            d, pt, pc = _par_segmento_caixa(pol[i - 1], pol[i], caixa)
            if melhor is None or d < melhor[0] - IGUAL:
                melhor = (d, pt, pc)
    for t in tinta['caixas']:
        d, pt, pc = _par_caixas(t, caixa)
        if melhor is None or d < melhor[0] - IGUAL:
            melhor = (d, pt, pc)
    if melhor is None:
        return math.inf, False, None, None
    return melhor[0], False, melhor[1], melhor[2]


def _encolhida(c, d):
    hx, hy = min(d, (c[2] - c[0]) * QUARTO), min(d, (c[3] - c[1]) * QUARTO)
    return [c[0] + hx, c[1] + hy, c[2] - hx, c[3] - hy]


def _cobertura(caixa, tinta):
    area = _area(caixa)
    if area <= 0:
        return 0.0
    return min(1.0, _area_coberta(caixa, tinta) / area)


def _dentro(caixa, tinta, tol):
    """A caixa inteira sobre a tinta, com a folga do pixel (tol) em cada lado."""
    return _cobertura(_encolhida(caixa, tol), tinta) >= 1.0 - AREA_IGUAL


# ------------------------------------------------------------------ o arquivo de edicao
def arquivo_de_edicao(membros, gravado=None):
    """O id do arquivo de edicao da familia (199, 1). membros: [{'id', 'W', 'H', 'giro'}], W x H na composicao (em
    pe, como o publico ve), na ordem da tela. A escolha gravada no rascunho (gravado) fica enquanto o arquivo esta na
    familia: o arquivo maior que entra depois nao troca. Senao, o de maior area; no empate, o sem giro, depois o
    primeiro da lista. None sem membros."""
    ids = [m['id'] for m in membros]
    if gravado is not None and gravado in ids:
        return gravado
    melhor = None
    for n, m in enumerate(membros):
        gira = 1 if int(m.get('giro') or 0) % VOLTA else 0
        chave = (-(float(m['W']) * float(m['H'])), gira, n)
        if melhor is None or chave < melhor[0]:
            melhor = (chave, m['id'])
    return melhor[1] if melhor else None


# ------------------------------------------------------------------ o modelo
class _Uniao:
    def __init__(self, ids):
        self.pai = {k: k for k in ids}
        self.ordem = {k: n for n, k in enumerate(ids)}

    def raiz(self, k):
        while self.pai[k] != k:
            k = self.pai[k]
        return k

    def juntar(self, a, b):
        ra, rb = self.raiz(a), self.raiz(b)
        if ra != rb:
            # a raiz e sempre a do elemento que vem antes: o resultado nao depende da ordem das unioes
            if self.ordem[rb] < self.ordem[ra]:
                ra, rb = rb, ra
            self.pai[rb] = ra

    def copia(self):
        u = _Uniao(list(self.ordem))
        u.pai = dict(self.pai)
        return u

    def grupos(self, ids):
        por = {}
        for k in ids:
            por.setdefault(self.raiz(k), []).append(k)
        return [por[r] for r in sorted(por, key=lambda r: self.ordem[r])]


def _quadros(alvo):
    q = alvo.get('quadros') or {}
    margem = _f(q.get('margem') or [0.0, 0.0, float(alvo['W']), float(alvo['H'])])
    return {'margem': margem, 'area_segura': _f(q.get('area_segura') or margem)}


def _mesma_linha(a, b, eixo, tol):
    i0, i1 = INDICES[eixo]
    return abs(a[i0] - b[i0]) <= tol or abs(a[i1] - b[i1]) <= tol or \
        abs((a[i0] + a[i1]) - (b[i0] + b[i1])) * METADE <= tol


def _linhas(c, eixo):
    i0, i1 = INDICES[eixo]
    return {'inicio': c[i0], 'centro': (c[i0] + c[i1]) * METADE, 'fim': c[i1]}


def _ancora(caixa, eixo, quadros, intencao, ds, tol):
    """A ancora de um bloco num eixo (199, 2): {'lado', 'quadro', 'origem'}."""
    if intencao is not None:
        return {'lado': ANCORA_DO_ALVO[intencao['alvo']], 'quadro': intencao.get('referencia') or 'margem',
                'origem': 'intencao'}
    i0, i1 = INDICES[eixo]
    melhor = None
    for qn in QUADROS:
        q = quadros[qn]
        for lado, d in (('inicio', abs(caixa[i0] - q[i0])), ('fim', abs(q[i1] - caixa[i1]))):
            if melhor is None or d < melhor[0] - IGUAL:
                melhor = (d, qn, lado)
    _d, qn, lado = melhor
    q = quadros[qn]
    if abs(abs(caixa[i0] - q[i0]) - abs(q[i1] - caixa[i1])) <= tol:
        # margens quase iguais: o centro, ou a ancora que o DA confirmou no Design system
        if ds is not None:
            return {'lado': ds, 'quadro': qn, 'origem': 'design_system'}
        return {'lado': 'centro', 'quadro': qn, 'origem': 'centro'}
    return {'lado': lado, 'quadro': qn, 'origem': 'borda'}


def extrair_modelo(referencia, elementos, *, intencoes=(), grupos=(), silhuetas=None):
    """O modelo da familia, tirado do layout aprovado L* no arquivo de edicao (199, 2). Puro.
    referencia: {'id', 'W', 'H', 'quadros': {'margem', 'area_segura'}} (sem area segura, a margem).
    elementos: os de L* na ordem z, de baixo para cima: {'id', 'classe', 'funcao', 'caixa' (a que o DA ve, em px da
    referencia), 'caixa_asset' (opcional: o asset inteiro, que pode passar do canvas), 'geometria' (opcional: a caixa
    de geometria do texto editado, 196), 'sangra' {lado: bool}, 'ancora' (x, y) do Design system, 'opaco',
    'de_fundo' (opcional: a figura de fundo da versao da galeria, decisoes-v1.md, n 202: vai como fundo, nunca como
    conteudo)}.
    intencoes: as de desdobra.tela.edicao.intencoes; grupos: listas de ids que o DA juntou; silhuetas: {id da base:
    silhueta} (ver _tinta).
    Devolve {'referencia', 'W', 'H', 'quadros', 'ordem', 'elementos', 'blocos', 'fortes', 'bases', 'relacoes',
    'avisos'}, so com listas, numeros e textos."""
    from desdobra.derivacao import solver as mod_solver
    W, H = float(referencia['W']), float(referencia['H'])
    quadros = _quadros(referencia)
    silhuetas = silhuetas or {}
    tol_px = float(limites.valor('derivacao.enquadramento_tolerancia_px'))
    tol_linha = float(limites.valor('derivacao.alinhamento_tolerancia_px'))
    tol_meio = float(limites.valor('derivacao.alinhamento_intencao_tolerancia')) * max(W, H)
    fundo_min = float(limites.valor('derivacao.bloco_fundo_fracao'))
    canvas = [0.0, 0.0, W, H]
    els, ordem, avisos = {}, [], []
    originais = {}
    # o elemento que o DA juntou num grupo com outros (M7b, D1) anda com o grupo, mesmo a base que sangra (o circulo do
    # packshot): o grupo do DA nunca se separa na copia (etapa E4)
    agrupados = {k for g in grupos if len(g) > 1 for k in g}
    for z, e in enumerate(elementos):
        k = e['id']
        sangra = {lado: bool((e.get('sangra') or {}).get(lado)) for lado in LADOS}
        ds = list(e.get('ancora') or (None, None))
        # a figura de fundo do aprovado (de_fundo; decisoes-v1.md, n 202) nao e conteudo aqui: o conteudo sobre ela ja
        # foi aprovado, e ela vai como fundo (cresce para continuar sangrando, sem relacao de tinta)
        de_fundo = bool(e.get('de_fundo')) and any(sangra.values())
        x = {'id': k, 'classe': e.get('classe'), 'funcao': e.get('funcao'), 'z': z, 'caixa': _f(e['caixa']),
             'caixa_asset': _f(e.get('caixa_asset') or e['caixa']), 'sangra': sangra,
             'ancora_ds': [ANCORA_DO_DS.get(v) for v in ds],
             'conteudo': bool(mod_solver.conteudo(e)) and not de_fundo}
        if e.get('geometria') is not None:
            x['geometria'] = _f(e['geometria'])
        if e.get('recorte') is not None:
            # a caixa em que o render corta a pilha (etapa E4): a tinta e a sangria contam so dentro dela
            x['recorte'] = _f(e['recorte'])
        if x['conteudo'] or not any(sangra.values()) or k in agrupados:
            # a cena que nao sangra (objeto solto, grafismo) anda como conteudo (desenho 4, 2.5); a do grupo do DA
            # tambem
            x['papel'] = 'movel'
        else:
            # o fundo puro e a tinta que cobre quase o canvas inteiro (95), medida pela silhueta: a caixa da forma com
            # a diagonal cobre o canvas, a tinta dela nao
            x['tinta'], x['borda'], sem = _tinta(x['caixa_asset'], silhuetas.get(k), W, H, x.get('recorte'))
            coberta = _area_coberta(canvas, _recortada(x['tinta'], W, H))
            x['papel'] = 'fundo' if de_fundo or coberta >= fundo_min * W * H else 'base'
            # sem silhueta, a forma e conferida pela caixa, com o aviso (199, 3; desenho final, 5). O fundo que cobre o
            # canvas inteiro nao tem borda para conferir e fica sem aviso; a figura de fundo tambem (n 202)
            if sem and not de_fundo and (x['papel'] == 'base' or coberta < (1.0 - AREA_IGUAL) * W * H):
                avisos.append({'codigo': 'forma_conferida_pela_caixa', 'elemento': k})
        els[k] = x
        ordem.append(k)
        originais[k] = dict(e, sangra=sangra)
    moveis = [k for k in ordem if els[k]['papel'] == 'movel']
    conteudos = [k for k in moveis if els[k]['conteudo']]
    bases = [k for k in ordem if els[k]['papel'] == 'base']
    fundos = [k for k in ordem if els[k]['papel'] == 'fundo']
    # os blocos: grupos do DA e elementos que se sobrepoem andam juntos nos dois eixos (os fortes); os que dividem uma
    # linha andam juntos naquele eixo
    forte = _Uniao(moveis)
    for g in grupos:
        dentro = [k for k in moveis if k in set(g)]
        for a, b in zip(dentro, dentro[1:]):
            forte.juntar(a, b)
    for a, b in itertools.combinations(moveis, 2):
        ca, cb = els[a]['caixa'], els[b]['caixa']
        if _sobra(ca[0], ca[2], cb[0], cb[2]) > 0 and _sobra(ca[1], ca[3], cb[1], cb[3]) > 0:
            forte.juntar(a, b)
    blocos = {}
    for eixo in EIXOS:
        u = forte.copia()
        for a, b in itertools.combinations(moveis, 2):
            if _mesma_linha(els[a]['caixa'], els[b]['caixa'], eixo, tol_linha):
                u.juntar(a, b)
        lista = []
        n_eixo = EIXOS.index(eixo)
        for membros in u.grupos(moveis):
            caixa = _uniao([els[k]['caixa'] for k in membros])
            # a ancora sai do que nao sangra no bloco (revisao da 0.10.0): a base que sangra e que o DA juntou ao grupo
            # (a faixa verde com a assinatura) tem a altura inteira do arquivo e levaria a ancora ao centro; ela segue
            # o conteudo do grupo e cresce depois so o necessario para continuar sangrando (_sangrar_movel)
            soltos = [k for k in membros if not any(els[k]['sangra'].values())]
            caixa_ancora = _uniao([els[k]['caixa'] for k in soltos]) if soltos else caixa
            intencao = next((i for i in intencoes if i.get('eixo') == eixo and
                             any(k in membros for k in i.get('elementos') or ())), None)
            valores = [els[k]['ancora_ds'][n_eixo] for k in (soltos or membros)
                       if els[k]['ancora_ds'][n_eixo] is not None]
            ds = valores[0] if valores and all(v == valores[0] for v in valores) else None
            lista.append({'id': '%s:%s' % (eixo, membros[0]), 'elementos': membros, 'caixa': caixa,
                          'caixa_ancora': caixa_ancora,
                          'ancora': _ancora(caixa_ancora, eixo, quadros, intencao, ds, tol_meio)})
        blocos[eixo] = lista
    fortes = forte.grupos(moveis)
    # as relacoes medidas em L*, cada uma com id estavel
    relacoes = []
    for c in conteudos:
        cc = els[c]['caixa']
        for k in bases:
            tin = _recortada(els[k]['tinta'], W, H)
            if _dentro(cc, tin, tol_px):
                relacoes.append({'id': 'dentro_da_tinta:%s:%s' % (c, k), 'tipo': 'dentro_da_tinta',
                                 'elementos': [c, k], 'conteudo': c, 'base': k})
                continue
            d, invade, pt, pc = _distancia(cc, tin)
            if invade or not math.isfinite(d):
                continue  # o conteudo que ja estava sobre a borda da forma nao tem relacao com ela
            normal = None
            if d > IGUAL:
                normal = [(pt[0] - pc[0]) / d, (pt[1] - pc[1]) / d]
            relacoes.append({'id': 'livre_da_tinta:%s:%s' % (c, k), 'tipo': 'livre_da_tinta', 'elementos': [c, k],
                             'conteudo': c, 'base': k, 'folga': d, 'normal': normal})
    for a, b in itertools.combinations(moveis, 2):
        if not mod_solver.par_que_nao_sobrepoe(originais[a], originais[b]):
            continue
        ca, cb = els[a]['caixa'], els[b]['caixa']
        if _sobra(ca[0], ca[2], cb[0], cb[2]) > 0 and _sobra(ca[1], ca[3], cb[1], cb[3]) > 0:
            continue  # ja se sobrepoem no aprovado
        relacoes.append({'id': 'sem_sobreposicao:%s:%s' % (a, b), 'tipo': 'sem_sobreposicao', 'elementos': [a, b]})
    for a, b in itertools.combinations(conteudos, 2):
        ca, cb = els[a]['caixa'], els[b]['caixa']
        for eixo in EIXOS:
            i0, i1 = INDICES[eixo]
            o0, o1 = INDICES['y' if eixo == 'x' else 'x']
            vao = max(cb[i0] - ca[i1], ca[i0] - cb[i1])
            if vao > 0 and _sobra(ca[o0], ca[o1], cb[o0], cb[o1]) > 0:
                relacoes.append({'id': 'distancia:%s:%s:%s' % (a, b, eixo), 'tipo': 'distancia', 'elementos': [a, b],
                                 'eixo': eixo, 'vao': vao})
    for c in conteudos:
        cc = els[c]['caixa']
        for tipo, qn in (('no_quadro', 'margem'), ('na_area_segura', 'area_segura')):
            if tipo == 'na_area_segura' and els[c]['classe'] not in CLASSES_AREA_SEGURA:
                continue
            q = quadros[qn]
            if cc[0] >= q[0] - tol_px and cc[1] >= q[1] - tol_px and cc[2] <= q[2] + tol_px and cc[3] <= q[3] + tol_px:
                relacoes.append({'id': '%s:%s' % (tipo, c), 'tipo': tipo, 'elementos': [c], 'quadro': qn})
    for a, b in itertools.combinations(conteudos, 2):
        for eixo in EIXOS:
            la, lb = _linhas(els[a]['caixa'], eixo), _linhas(els[b]['caixa'], eixo)
            for linha in LADOS_DA_ANCORA:
                if abs(la[linha] - lb[linha]) <= tol_linha:
                    relacoes.append({'id': 'alinhados:%s:%s:%s:%s' % (a, b, eixo, linha), 'tipo': 'alinhados',
                                     'elementos': [a, b], 'eixo': eixo, 'linha': linha})
    relacoes.sort(key=lambda r: (TIPOS.index(r['tipo']), r['id']))
    # o conteudo que fica sobre a caixa de uma forma sem desenho (revisao da 0.10.0): a caixa nao diz se ele esta no
    # branco ou na tinta, e a copia nunca sai "igual" sem conferir isso (o job sem silhueta deixava a assinatura 60 px
    # dentro do azul no 1080x1600 com o selo "Igual ao seu")
    sem_desenho = []
    for a in avisos:
        k = a['elemento']
        caixa_tinta = _recortada(els[k]['tinta'], W, H)
        sobre = [c for c in conteudos if _area_coberta(els[c]['caixa'], caixa_tinta) > 0]
        if sobre:
            sem_desenho.append({'base': k, 'conteudos': sobre})
    # o ponto fixo de cada base: o da borda de dentro mais perto do conteudo que se relaciona com ela (o hospede); o
    # fundo puro e a base sem relacao crescem em volta do centro, levado em proporcao (galeria._fundo)
    info = {}
    for k in fundos + bases:
        x = els[k]
        centro = [(x['caixa'][0] + x['caixa'][2]) * METADE, (x['caixa'][1] + x['caixa'][3]) * METADE]
        melhor = None
        if x['papel'] == 'base':
            ligados = [r['conteudo'] for r in relacoes if r.get('base') == k]
            for c in conteudos:
                if c not in ligados:
                    continue
                for a, b in x['borda']:
                    d, p, _q = _par_segmento_caixa(a, b, els[c]['caixa'])
                    if melhor is None or d < melhor[0] - IGUAL:
                        melhor = (d, c, p)
        if melhor is None:
            info[k] = {'modo': 'centro', 'ponto': centro, 'hospede': None}
        else:
            info[k] = {'modo': 'borda', 'ponto': melhor[2], 'hospede': melhor[1], 'distancia': melhor[0]}
    return {'referencia': referencia.get('id'), 'W': W, 'H': H, 'quadros': quadros, 'ordem': ordem,
            'elementos': els, 'blocos': blocos, 'fortes': fortes, 'bases': info, 'relacoes': relacoes,
            'avisos': avisos, 'sem_desenho': sem_desenho}


# ------------------------------------------------------------------ a copia para cada arquivo
def _no_eixo(v, b, s):
    """A coordenada v levada pelo bloco b no eixo dele: v + deslocamento + (v - ancora) x (s - 1)."""
    return v + b['deslocamento'] + (v - b['ancora']) * (s - 1.0)


def _bloco_de(est, eixo, k):
    return est['blocos'][eixo][est['bloco_do_elemento'][eixo][k]]


def _ponto_fixo(modelo, est, k):
    """(origem, destino) do ponto fixo da base k: o ponto da borda anda com o hospede, pela mesma conta do bloco dele
    (199, 2); no centro, levado em proporcao ao canvas."""
    b = modelo['bases'][k]
    p = list(b['ponto'])
    if b['modo'] == 'borda':
        h = b['hospede']
        return p, [_no_eixo(p[0], _bloco_de(est, 'x', h), est['s']), _no_eixo(p[1], _bloco_de(est, 'y', h), est['s'])]
    W0, H0 = modelo['W'], modelo['H']
    return p, [p[0] + p[0] * (est['W'] - W0) / W0, p[1] + p[1] * (est['H'] - H0) / H0]


def _crescimento(a, sangra, origem, destino, s, W, H):
    """A menor escala k >= s da base (asset a) em volta do ponto fixo para cada lado que sangrava continuar sangrando.
    None quando um lado nao volta a sangrar em volta deste ponto."""
    k = s
    for lado in LADOS:
        if not sangra[lado]:
            continue
        if lado == 'esq':
            falta, braco = destino[0], origem[0] - a[0]
        elif lado == 'dir':
            falta, braco = W - destino[0], a[2] - origem[0]
        elif lado == 'topo':
            falta, braco = destino[1], origem[1] - a[1]
        else:
            falta, braco = H - destino[1], a[3] - origem[1]
        if falta <= 0:
            continue
        if braco <= 0:
            return None
        k = max(k, falta / braco)
    return k


def _colocar_base(modelo, est, k):
    x = modelo['elementos'][k]
    origem, destino = _ponto_fixo(modelo, est, k)
    modo = modelo['bases'][k]['modo']
    # o lado que sangra e medido na caixa que o render mostra (o recorte, etapa E4), senao no asset
    corte = x.get('recorte') or x['caixa_asset']
    esc = _crescimento(corte, x['sangra'], origem, destino, est['s'], est['W'], est['H'])
    if esc is None:
        # o lado que sangrava nao volta a sangrar em volta do ponto da borda: o centro, com o aviso
        modo = 'centro_sem_ponto'
        origem = [(x['caixa'][0] + x['caixa'][2]) * METADE, (x['caixa'][1] + x['caixa'][3]) * METADE]
        W0, H0 = modelo['W'], modelo['H']
        destino = [origem[0] + origem[0] * (est['W'] - W0) / W0, origem[1] + origem[1] * (est['H'] - H0) / H0]
        esc = _crescimento(corte, x['sangra'], origem, destino, est['s'], est['W'], est['H']) or est['s']
        if not any(a.get('codigo') == 'base_sem_ponto_fixo' and a.get('elemento') == k for a in est['avisos']):
            est['avisos'].append({'codigo': 'base_sem_ponto_fixo', 'elemento': k})
    est['bases'][k] = {'origem': origem, 'destino': destino, 'escala': esc, 'crescimento': esc / est['s'],
                       'hospede': modelo['bases'][k].get('hospede'), 'modo': modo}
    est['caixas'][k] = _caixa_por(x['caixa'], origem, destino, esc)
    est['caixas_asset'][k] = _caixa_por(x['caixa_asset'], origem, destino, esc)
    if x.get('recorte') is not None:
        est.setdefault('recortes', {})[k] = _caixa_por(x['recorte'], origem, destino, esc)


def _sangrar_movel(modelo, est, k):
    """O elemento de cena que anda como conteudo (o do grupo do DA) e sangrava no aprovado continua sangrando (199,
    2): cresce em volta do centro dele so o necessario para voltar a chegar a borda (etapa E4: o circulo do packshot
    alinhado na base, cuja caixa ficaria 2 px acima dela na copia, com o corte do KV a vista)."""
    x = modelo['elementos'][k]
    if x['conteudo'] or not any(x['sangra'].values()):
        return
    c = est['caixas'][k]
    centro = [(c[0] + c[2]) * METADE, (c[1] + c[3]) * METADE]
    g = _crescimento(c, x['sangra'], centro, centro, 1.0, est['W'], est['H'])
    if g is None or g <= 1.0 + IGUAL:
        return
    for campo in ('caixas', 'geometrias'):
        if k in est[campo]:
            est[campo][k] = _caixa_por(est[campo][k], centro, centro, g)
    est['fatores'][k] *= g
    est['crescimento_movel'][k] = g


def _colocar_moveis(modelo, est, ids):
    s = est['s']
    for k in ids:
        bx, by = _bloco_de(est, 'x', k), _bloco_de(est, 'y', k)
        for campo, chave in (('caixas', 'caixa'), ('geometrias', 'geometria')):
            c = modelo['elementos'][k].get(chave)
            if c is not None:
                est[campo][k] = [_no_eixo(c[0], bx, s), _no_eixo(c[1], by, s), _no_eixo(c[2], bx, s),
                                 _no_eixo(c[3], by, s)]


def _deslocamento(b, eixo, qr, qm, s):
    """(coordenada da ancora na referencia, deslocamento dela no membro) do bloco b."""
    i0, i1 = INDICES[eixo]
    c = b.get('caixa_ancora') or b['caixa']
    r, m = qr[b['ancora']['quadro']], qm[b['ancora']['quadro']]
    lado = b['ancora']['lado']
    if lado == 'inicio':
        return c[i0], (m[i0] - r[i0]) + (c[i0] - r[i0]) * (s - 1.0)
    if lado == 'fim':
        return c[i1], (m[i1] - r[i1]) + (c[i1] - r[i1]) * (s - 1.0)
    cr, cm, cb = (r[i0] + r[i1]) * METADE, (m[i0] + m[i1]) * METADE, (c[i0] + c[i1]) * METADE
    return cb, (cm - cr) + (cb - cr) * (s - 1.0)


def transferir(modelo, membro):
    """O layout de um arquivo da familia, copiado do modelo (199, 2). Conta fechada, sem otimizador. Puro.
    membro: {'id', 'W', 'H', 'quadros': {'margem', 'area_segura'}} na composicao (em pe).
    Devolve {'membro', 'W', 'H', 'quadros', 's', 'sobra', 'caixas', 'caixas_asset', 'geometrias', 'fatores',
    'blocos', 'bloco_do_elemento', 'bases', 'ajustes', 'avisos'}: caixas em px do membro; o texto leva o corpo x s
    (fatores, 1 enquanto a escada nao diminui o bloco); bases[k]: a semelhanca da base {'origem', 'destino',
    'escala' (s x g), 'crescimento' (g), 'hospede', 'modo'}; ajustes: as ancoras desfeitas pelo fundo."""
    W, H = float(membro['W']), float(membro['H'])
    qm, qr = _quadros(membro), modelo['quadros']
    # s nunca passa de 1 (199, 1; revisao da 0.10.0): o arquivo de edicao e o maior em area, mas a area segura dele
    # pode apertar o quadro mais que a do membro, e a razao dos quadros passaria de 1. Nada amplia alem do que o DA
    # viu: a sobra fica nos eixos
    s = min(_lado(qm['margem'], 'x') / _lado(qr['margem'], 'x'), _lado(qm['margem'], 'y') / _lado(qr['margem'], 'y'),
            1.0)
    els = modelo['elementos']
    est = {'membro': membro.get('id'), 'W': W, 'H': H, 'quadros': qm, 's': s, 'sobra': {}, 'caixas': {},
           'caixas_asset': {}, 'recortes': {}, 'geometrias': {}, 'fatores': {}, 'blocos': {'x': {}, 'y': {}},
           'bloco_do_elemento': {'x': {}, 'y': {}}, 'bases': {}, 'crescimento_movel': {}, 'reducao': {}, 'ajustes': [],
           'avisos': copy.deepcopy(modelo['avisos'])}
    for eixo in EIXOS:
        i0, i1 = INDICES[eixo]
        est['sobra'][eixo] = _lado(qm['margem'], eixo) - s * _lado(qr['margem'], eixo)
        ref0, mem0 = qr['margem'][i0], qm['margem'][i0]
        itens = []
        for b in modelo['blocos'][eixo]:
            a_r, desl = _deslocamento(b, eixo, qr, qm, s)
            c0 = b['caixa'][i0]
            inicio = (mem0 - ref0) + (c0 - ref0) * (s - 1.0)  # o deslocamento de c0 preso ao inicio da margem
            delta = desl + (c0 - a_r) * (s - 1.0) - inicio
            q = b['ancora']['quadro']
            ini_q = (qm[q][i0] - qr[q][i0]) + (c0 - qr[q][i0]) * (s - 1.0) - inicio
            fim_q = ini_q + _lado(qm[q], eixo) - s * _lado(qr[q], eixo)
            itens.append({'b': b, 'ancora': a_r, 'deslocamento': desl, 'delta': delta,
                          'faixa': [min(ini_q, fim_q), max(ini_q, fim_q)], 'origem': b['ancora']['origem']})
        # a sobra nunca aproxima dois conteudos: o bloco que vem depois no eixo nunca anda menos que o de antes
        itens.sort(key=lambda it: (it['b']['caixa'][i0], it['b']['caixa'][i1], it['b']['id']))
        for j, it in enumerate(itens):
            antes = [o['delta'] for o in itens[:j] if o['b']['caixa'][i1] <= it['b']['caixa'][i0] + IGUAL]
            if antes and max(antes) > it['delta'] + IGUAL:
                novo = max(antes)
                it['deslocamento'] += novo - it['delta']
                it['delta'] = novo
                it['origem'] = 'ordem'
        for it in itens:
            b = it['b']
            est['blocos'][eixo][b['id']] = {'elementos': list(b['elementos']), 'ancora': it['ancora'],
                                            'deslocamento': it['deslocamento'], 'delta': it['delta'],
                                            'faixa': it['faixa'], 'lado': b['ancora']['lado'],
                                            'quadro': b['ancora']['quadro'], 'origem': it['origem']}
            for k in b['elementos']:
                est['bloco_do_elemento'][eixo][k] = b['id']
    moveis = [k for k in modelo['ordem'] if els[k]['papel'] == 'movel']
    for k in moveis:
        est['fatores'][k] = 1.0
        est['reducao'][k] = 1.0  # o produto dos F3 da escada, sobre o tamanho copiado
    _colocar_moveis(modelo, est, moveis)
    for k in moveis:
        _sangrar_movel(modelo, est, k)
    for k in modelo['ordem']:
        if els[k]['papel'] != 'movel':
            _colocar_base(modelo, est, k)
    _protecao(modelo, est)
    return est


def _mover_bloco(modelo, est, eixo, bid, d):
    i0, i1 = INDICES[eixo]
    b = est['blocos'][eixo][bid]
    b['deslocamento'] += d
    b['delta'] += d
    for k in b['elementos']:
        for campo in ('caixas', 'geometrias'):
            if k in est[campo]:
                c = est[campo][k]
                c[i0] += d
                c[i1] += d


def _seguir_hospedes(modelo, est, movidos):
    """A base cujo hospede andou anda com ele (o ponto fixo e do hospede)."""
    for k in modelo['ordem']:
        b = modelo['bases'].get(k)
        if b is not None and b.get('hospede') in movidos:
            _colocar_base(modelo, est, k)


def _protecao(modelo, est):
    """O conteudo nunca muda de fundo (desenho 4, 2.6): quando a ancora o leva para cima da tinta de uma forma de que
    estava livre, ou o tira de dentro dela, o bloco volta a posicao rigida em relacao aquela forma, se ali todas as
    relacoes de fundo dele valem e nada novo quebra. Registro ancora_desfeita_pelo_fundo."""
    tentados = []
    for _volta in range(len(modelo['relacoes']) + 1):
        antes = [r for r in relacoes(modelo, est) if not r['ok']]
        ids_antes = [r['id'] for r in antes]
        trocou = False
        for r in antes:
            if r['tipo'] not in TIPOS_DE_FUNDO or r['id'] in tentados:
                continue
            if r['tipo'] == 'livre_da_tinta' and not r['invade']:
                continue  # so a folga menor, no mesmo fundo: e a escada que resolve
            tentados.append(r['id'])
            c, k = r['conteudo'], r['base']
            base = est['bases'][k]
            rig = _ponto(modelo['elementos'][c]['caixa'][:2], base['origem'], base['destino'], est['s'])
            atual = est['caixas'][c]
            novo = copy.deepcopy(est)
            movidos = []
            for eixo, d in (('x', rig[0] - atual[0]), ('y', rig[1] - atual[1])):
                if abs(d) > IGUAL:
                    bid = novo['bloco_do_elemento'][eixo][c]
                    _mover_bloco(modelo, novo, eixo, bid, d)
                    novo['blocos'][eixo][bid]['origem'] = 'fundo:%s' % k
                    movidos += [m for m in novo['blocos'][eixo][bid]['elementos'] if m not in movidos]
            if not movidos:
                continue
            _seguir_hospedes(modelo, novo, movidos)
            depois = [q for q in relacoes(modelo, novo) if not q['ok']]
            de_fundo = [q for q in depois if q['tipo'] in TIPOS_DE_FUNDO and q['conteudo'] in movidos]
            if de_fundo or any(q['id'] not in ids_antes for q in depois):
                continue
            novo['ajustes'].append({'codigo': 'ancora_desfeita_pelo_fundo', 'relacao': r['id'], 'elemento': c,
                                    'base': k, 'deslocamento': [rig[0] - atual[0], rig[1] - atual[1]],
                                    'frase': _frase_fundo(modelo, c, k)})
            est.clear()
            est.update(novo)
            trocou = True
            break
        if not trocou:
            return


# ------------------------------------------------------------------ as relacoes no membro
def _tinta_no_membro(modelo, est, k, cache):
    b = est['bases'][k]
    chave = (k, tuple(b['origem']), tuple(b['destino']), b['escala'])
    if chave not in cache:
        cache[chave] = _recortada(_tinta_por(modelo['elementos'][k]['tinta'], b['origem'], b['destino'], b['escala']),
                                  est['W'], est['H'])
    return cache[chave]


def _avaliar(modelo, est, r, cache, estrito=False):
    """{'ok', 'medida', 'alvo', 'invade'} da relacao r no layout est. A relacao quebra quando a folga fica abaixo do
    alvo alem do arredondamento do pixel (derivacao.enquadramento_tolerancia_px); estrito: a escada busca o alvo
    inteiro, a folga do aprovado x s, sem o arredondamento (199, 3)."""
    s = est['s']
    tol = float(limites.valor('derivacao.enquadramento_tolerancia_px'))
    if estrito and r['tipo'] in ('livre_da_tinta', 'distancia'):
        tol = IGUAL
    cx = est['caixas']
    t = r['tipo']
    if t == 'livre_da_tinta':
        d, invade, _pt, _pc = _distancia(cx[r['conteudo']], _tinta_no_membro(modelo, est, r['base'], cache))
        alvo = r['folga'] * s
        return {'ok': not invade and d >= alvo - tol, 'medida': d, 'alvo': alvo, 'invade': invade}
    if t == 'dentro_da_tinta':
        tin = _tinta_no_membro(modelo, est, r['base'], cache)
        c = cx[r['conteudo']]
        return {'ok': _dentro(c, tin, tol), 'medida': _cobertura(c, tin), 'alvo': 1.0, 'invade': False}
    if t == 'sem_sobreposicao':
        ca, cb = cx[r['elementos'][0]], cx[r['elementos'][1]]
        tol_col = float(limites.valor('derivacao.colisao_tolerancia_px'))
        sx, sy = _sobra(ca[0], ca[2], cb[0], cb[2]), _sobra(ca[1], ca[3], cb[1], cb[3])
        return {'ok': not (sx > tol_col and sy > tol_col), 'medida': min(sx, sy), 'alvo': tol_col, 'invade': False}
    if t == 'distancia':
        i0, i1 = INDICES[r['eixo']]
        ca, cb = cx[r['elementos'][0]], cx[r['elementos'][1]]
        sep = max(cb[i0] - ca[i1], ca[i0] - cb[i1])
        alvo = float(limites.valor('derivacao.distancia_entre_linhas_min')) * r['vao'] * s
        return {'ok': sep >= alvo - tol, 'medida': sep, 'alvo': alvo, 'invade': False}
    if t in ('no_quadro', 'na_area_segura'):
        q, c = est['quadros'][r['quadro']], cx[r['elementos'][0]]
        fora = max(q[0] - c[0], q[1] - c[1], c[2] - q[2], c[3] - q[3], 0.0)
        return {'ok': fora <= tol, 'medida': fora, 'alvo': 0.0, 'invade': False}
    la, lb = (_linhas(cx[k], r['eixo'])[r['linha']] for k in r['elementos'])
    tol_linha = float(limites.valor('derivacao.alinhamento_tolerancia_px'))
    return {'ok': abs(la - lb) <= tol_linha, 'medida': abs(la - lb), 'alvo': 0.0, 'invade': False}


def relacoes(modelo, colocado):
    """As relacoes do aprovado conferidas no layout de um arquivo (colocado: o de transferir ou ajustar_minimo), na
    ordem do modelo: [{'id', 'tipo', 'elementos', 'conteudo', 'base', 'ok', 'medida', 'alvo', 'invade'}]. A forma e
    conferida pela tinta dela (a silhueta, ou a caixa sem silhueta)."""
    cache = {}
    saida = []
    for r in modelo['relacoes']:
        a = _avaliar(modelo, colocado, r, cache)
        saida.append(dict({'id': r['id'], 'tipo': r['tipo'], 'elementos': list(r['elementos']),
                           'conteudo': r.get('conteudo'), 'base': r.get('base')}, **a))
    return saida


def relacoes_furadas(modelo, colocado):
    """As relacoes do aprovado que se perdem no layout do arquivo."""
    return [r for r in relacoes(modelo, colocado) if not r['ok']]


# ------------------------------------------------------------------ a escada do menor ajuste
def _bissecao(ok, fim):
    """O menor t em [0, fim] com ok(t), sabendo ok(fim); passos fixos, a mesma resposta em todo processo."""
    if ok(0.0):
        return 0.0
    a, b = 0.0, fim
    for _ in range(PASSOS):
        m = (a + b) * METADE
        if ok(m):
            b = m
        else:
            a = m
    return b


def escolher(candidatos):
    """O candidato de menor custo; no empate (ao arredondamento da conta), F1, F2, F3 (resposta 1 do Duda)."""
    if not candidatos:
        return None
    return min(candidatos, key=lambda c: (round(c['custo'], CASAS_CUSTO), AJUSTES.index(c['tipo'])))


def _moveis_da_relacao(modelo, r):
    return [k for k in r['elementos'] if modelo['elementos'][k]['papel'] == 'movel']


def _escalar(modelo, est, ids, ponto, f):
    for k in ids:
        for campo in ('caixas', 'geometrias'):
            if k in est[campo]:
                est[campo][k] = _caixa_por(est[campo][k], ponto, ponto, f)
        est['fatores'][k] *= f
        est.setdefault('reducao', {})[k] = est['reducao'].get(k, 1.0) * f


def _ponto_da_ancora(modelo, est, k, caixa):
    """O ponto fixo do F3 em cada eixo: a linha em que o elemento se alinha com outro no aprovado (diminuir em volta
    dela mantem o alinhamento), senao a ancora do bloco dele."""
    p = []
    for eixo in EIXOS:
        i0, i1 = INDICES[eixo]
        linha = next((r['linha'] for r in modelo['relacoes'] if r['tipo'] == 'alinhados' and r['eixo'] == eixo and
                      k in r['elementos']), None)
        lado = linha or _bloco_de(est, eixo, k)['lado']
        p.append(caixa[i0] if lado == 'inicio' else caixa[i1] if lado == 'fim' else (caixa[i0] + caixa[i1]) * METADE)
    return p


def _recuo_max(modelo, est, k, n):
    """O maior recuo da base k na direcao n sem ela deixar de sangrar onde sangrava (ate a reserva fora do canvas)."""
    x = modelo['elementos'][k]
    a = (est.get('recortes') or {}).get(k) or est['caixas_asset'][k]
    W, H = est['W'], est['H']
    lim = max(W, H)
    for lado in LADOS:
        if not x['sangra'][lado]:
            continue
        if lado == 'esq' and n[0] > IGUAL:
            lim = min(lim, -a[0] / n[0])
        elif lado == 'dir' and n[0] < -IGUAL:
            lim = min(lim, (a[2] - W) / -n[0])
        elif lado == 'topo' and n[1] > IGUAL:
            lim = min(lim, -a[1] / n[1])
        elif lado == 'base' and n[1] < -IGUAL:
            lim = min(lim, (a[3] - H) / -n[1])
    return max(0.0, lim)


def _recuar(modelo, est, k, n, d):
    b = est['bases'][k]
    b['destino'] = [b['destino'][0] + n[0] * d, b['destino'][1] + n[1] * d]
    x = modelo['elementos'][k]
    est['caixas'][k] = _caixa_por(x['caixa'], b['origem'], b['destino'], b['escala'])
    est['caixas_asset'][k] = _caixa_por(x['caixa_asset'], b['origem'], b['destino'], b['escala'])
    if x.get('recorte') is not None:
        est['recortes'][k] = _caixa_por(x['recorte'], b['origem'], b['destino'], b['escala'])


def _candidatos(modelo, est, r, quebradas, pisos, escala_min):
    """Os candidatos de um parametro para a relacao r (199, 3), cada um com a menor magnitude que a devolve e sem
    quebrar relacao nova: [{'tipo', 'custo', 'estado', 'registro'}]."""
    lado_menor = min(est['W'], est['H'])
    spec = next(x for x in modelo['relacoes'] if x['id'] == r['id'])

    def vale(novo):
        return _avaliar(modelo, novo, spec, {}, estrito=True)['ok']

    def valido(novo):
        return all(q['ok'] or q['id'] in quebradas and q['id'] != r['id'] for q in relacoes(modelo, novo))
    saida = []
    for k in _moveis_da_relacao(modelo, r):
        # F1: andar o bloco dentro da sobra do eixo
        for eixo in EIXOS:
            bid = est['bloco_do_elemento'][eixo][k]
            b = est['blocos'][eixo][bid]
            for sinal, limite in ((1.0, b['faixa'][1] - b['delta']), (-1.0, b['delta'] - b['faixa'][0])):
                if limite <= IGUAL:
                    continue

                def andar(t, eixo=eixo, bid=bid, sinal=sinal):
                    novo = copy.deepcopy(est)
                    _mover_bloco(modelo, novo, eixo, bid, sinal * t)
                    return novo
                if not vale(andar(limite)):
                    continue
                t = _bissecao(lambda t: vale(andar(t)), limite)
                novo = andar(t)
                if valido(novo):
                    saida.append({'tipo': 'F1', 'custo': t / lado_menor, 'estado': novo,
                                  'registro': {'tipo': 'F1', 'relacao': r['id'], 'elemento': k, 'eixo': eixo,
                                               'px': sinal * t, 'frase': _frase_f1(modelo, spec, k, t)}})
        # F3: diminuir o bloco em volta da ancora, ate o piso
        forte = next(g for g in modelo['fortes'] if k in g)
        # o piso vale sobre o tamanho copiado, e nao sobre o atual (revisao da 0.10.0): o F3 que vem depois de outro
        # no mesmo bloco so diminui o que falta ate o piso, e o produto dos dois nunca fica abaixo de escala_min nem
        # do piso da 133
        red = est.get('reducao') or {}
        f_min = max(max(float(escala_min), float((pisos or {}).get(m, 0.0))) / red.get(m, 1.0) for m in forte)
        if f_min < 1.0 - IGUAL:
            caixa = _uniao([est['caixas'][m] for m in forte])
            ponto = _ponto_da_ancora(modelo, est, k, caixa)
            braco = max(_dist(ponto, c) for c in _cantos(caixa))

            def diminuir(t, forte=forte, ponto=ponto):
                novo = copy.deepcopy(est)
                _escalar(modelo, novo, forte, ponto, 1.0 - t)
                return novo
            if vale(diminuir(1.0 - f_min)):
                t = _bissecao(lambda t: vale(diminuir(t)), 1.0 - f_min)
                novo = diminuir(t)
                if valido(novo):
                    saida.append({'tipo': 'F3', 'custo': t * braco / lado_menor, 'estado': novo,
                                  'registro': {'tipo': 'F3', 'relacao': r['id'], 'elemento': k,
                                               'elementos': list(forte), 'fator': 1.0 - t, 'px': t * braco,
                                               'frase': _frase_f3(modelo, spec, k, 1.0 - t)}})
    # F2: recuar a forma na normal da borda, sem perder a sangria e sem tirar conteudo de dentro dela
    if spec['tipo'] == 'livre_da_tinta' and spec.get('normal'):
        k, n = spec['base'], spec['normal']
        limite = _recuo_max(modelo, est, k, n)

        def recuar(t):
            novo = copy.deepcopy(est)
            _recuar(modelo, novo, k, n, t)
            return novo
        if limite > IGUAL and vale(recuar(limite)):
            t = _bissecao(lambda t: vale(recuar(t)), limite)
            novo = recuar(t)
            if valido(novo):
                saida.append({'tipo': 'F2', 'custo': t / lado_menor, 'estado': novo,
                              'registro': {'tipo': 'F2', 'relacao': r['id'], 'elemento': k, 'px': t,
                                           'normal': list(n), 'frase': _frase_f2(modelo, spec, t)}})
    return saida


def _valor_pedido(modelo, est, r):
    """O valor do "Pede ajuste" em px: quanto falta para a relacao voltar."""
    spec = next(x for x in modelo['relacoes'] if x['id'] == r['id'])
    a = _avaliar(modelo, est, spec, {})
    t = r['tipo']
    if t == 'livre_da_tinta' and spec.get('normal'):
        # quanto o conteudo teria de sair da forma, na normal da borda, para a folga do aprovado voltar (quando ja
        # esta sobre a tinta, a distancia e 0 e nao diz quanto entrou)
        n, c, k = spec['normal'], est['caixas'][spec['conteudo']], spec['base']
        tin = _tinta_no_membro(modelo, est, k, {})

        def livre(d):
            fora = [c[0] - n[0] * d, c[1] - n[1] * d, c[2] - n[0] * d, c[3] - n[1] * d]
            dist, invade, _pt, _pc = _distancia(fora, tin)
            return not invade and dist >= a['alvo']
        teto = max(est['W'], est['H'])
        if livre(teto):
            return _bissecao(livre, teto)
    if t in ('livre_da_tinta', 'distancia'):
        return max(0.0, a['alvo'] - a['medida']) if math.isfinite(a['medida']) else 0.0
    if t == 'dentro_da_tinta':
        c = est['caixas'][r['conteudo']]
        tin = _tinta_no_membro(modelo, est, r['base'], {})
        meio = min(c[2] - c[0], c[3] - c[1]) * METADE
        return _bissecao(lambda d: _cobertura(_encolhida(c, d), tin) >= 1.0 - AREA_IGUAL, meio) \
            if _cobertura(_encolhida(c, meio), tin) >= 1.0 - AREA_IGUAL else meio
    return a['medida']


def ajustar_minimo(modelo, colocado, *, pisos=None, escala_min=None, crescimento_max=None):
    """A escada do menor ajuste (199, 3) no layout de um arquivo (o de transferir). Puro.
    Para cada relacao do aprovado que se perdeu, na ordem do modelo: os candidatos F1 (andar o bloco dentro da sobra),
    F2 (recuar a forma na normal da borda, sem perder a sangria nem tirar conteudo de dentro dela) e F3 (diminuir o
    bloco em volta da ancora ate escala_min, derivacao.familia_ajuste_escala_min, e nunca abaixo de pisos[id]: o
    fator do piso da 133 sobre o tamanho copiado), cada um com a menor magnitude que devolve a folga do aprovado x s.
    Vence o menor custo; no empate, F1, F2, F3. Nenhum candidato quebra relacao nova. O que nada resolve fica pedido.
    A forma que sangra e cresceu alem de crescimento_max (derivacao.familia_crescimento_max) tambem fica pedida, com
    o tipo 'crescimento' e o valor em 'crescimento'.
    Devolve o layout com 'ajustes' (as ancoras desfeitas e os F1/F2/F3, cada um com a frase), 'relacoes_quebradas'
    ([{'relacao', 'tipo', 'elementos', 'valor_px', 'frase'}]) e 'situacao' (igual, ajustado ou pede_ajuste)."""
    est = copy.deepcopy(colocado)
    escala_min = float(limites.valor('derivacao.familia_ajuste_escala_min') if escala_min is None else escala_min)
    pedidos = []
    for _volta in range(len(modelo['relacoes']) + 1):
        furadas = relacoes_furadas(modelo, est)
        abertas = [r for r in furadas if r['id'] not in pedidos]
        if not abertas:
            break
        r = abertas[0]
        melhor = escolher(_candidatos(modelo, est, r, [q['id'] for q in furadas], pisos, escala_min))
        if melhor is None:
            pedidos.append(r['id'])
            continue
        novo = melhor['estado']
        novo['ajustes'].append(dict(melhor['registro'], codigo='ajuste_da_familia', custo=melhor['custo']))
        est = novo
    quebradas = []
    for r in relacoes_furadas(modelo, est):
        valor = _valor_pedido(modelo, est, r)
        quebradas.append({'relacao': r['id'], 'tipo': r['tipo'], 'elementos': list(r['elementos']), 'valor_px': valor,
                          'frase': _frase_pedido(modelo, r, valor)})
    # a forma sem desenho com conteudo sobre a caixa dela: a relacao nao foi conferida, e o arquivo pede o olhar do DA
    # (revisao da 0.10.0; nada calado). Nada mudou de lugar por isso: o valor e 0 px
    for x in modelo.get('sem_desenho') or []:
        quebradas.append({'relacao': 'sem_desenho:%s' % x['base'], 'tipo': 'sem_desenho',
                          'elementos': list(x['conteudos']) + [x['base']], 'valor_px': 0.0,
                          'frase': _frase_sem_desenho(modelo, x['base'], x['conteudos'])})
    # a forma que precisou crescer alem de derivacao.familia_crescimento_max para continuar sangrando (resposta do
    # Duda em 18/11): o layout fica como a copia deu, e o arquivo pede o olhar do DA. Vale para a base e para a forma
    # que o DA juntou a um conteudo num grupo (ela anda como movel e cresce em _sangrar_movel). O fundo puro cresce o
    # quanto precisar para cobrir o arquivo e nunca entra
    cresc_max = float(limites.valor('derivacao.familia_crescimento_max') if crescimento_max is None
                      else crescimento_max)
    for k in modelo['ordem']:
        papel = modelo['elementos'][k]['papel']
        if papel == 'base' and k in est['bases']:
            g = est['bases'][k]['crescimento']
        elif papel == 'movel' and k in est['crescimento_movel']:
            g = est['crescimento_movel'][k]
        else:
            continue
        if g <= cresc_max + IGUAL:
            continue
        quebradas.append({'relacao': 'crescimento:%s' % k, 'tipo': 'crescimento', 'elementos': [k],
                          'valor_px': 0.0, 'crescimento': g, 'frase': _frase_crescimento(modelo, k, g, cresc_max)})
    est['relacoes_quebradas'] = quebradas
    est['situacao'] = 'pede_ajuste' if quebradas else ('ajustado' if est['ajustes'] else 'igual')
    return est


def copiar_familia(modelo, membros, *, pisos=None):
    """{id: layout} de cada membro da familia, pela copia e pela escada (transferir e ajustar_minimo). Cada membro
    depende so do modelo e dele: a ordem da lista nao muda nada. pisos: {id do membro: {id do elemento: fator}}."""
    return {m['id']: ajustar_minimo(modelo, transferir(modelo, m), pisos=(pisos or {}).get(m['id']))
            for m in sorted(membros, key=lambda m: m['id'])}


# ------------------------------------------------------------------ frases para o DA (sem jargao, com artigos)
def _rotulo(modelo, k):
    from desdobra.derivacao import galeria as mg
    e = modelo['elementos'][k]
    if e['papel'] == 'fundo':
        return 'o fundo'
    if e['papel'] == 'base':
        return 'a imagem' if e['funcao'] == 'imagem' else 'a forma'
    return mg.ROTULO.get(e['funcao'], mg.ROTULO_GERAL)


def _contrair(preposicao, rotulo):
    artigo, _, resto = rotulo.partition(' ')
    tabela = {'de': {'o': 'do', 'a': 'da', 'os': 'dos', 'as': 'das'},
              'a': {'o': 'ao', 'a': 'à', 'os': 'aos', 'as': 'às'}}[preposicao]
    if artigo in tabela and resto:
        return '%s %s' % (tabela[artigo], resto)
    return '%s %s' % (preposicao, rotulo)


def _dela(rotulo):
    return {'o': 'dele', 'a': 'dela', 'os': 'deles', 'as': 'delas'}.get(rotulo.partition(' ')[0], 'dele')


def _maiuscula(texto):
    return texto[0].upper() + texto[1:]


def _px(v):
    from desdobra.derivacao import galeria as mg
    return mg._numero(v)


def _motivo(modelo, r, k):
    """O que a relacao pede, dito para o elemento k."""
    t = r['tipo']
    outro = next((x for x in r['elementos'] if x != k), None)
    if t == 'livre_da_tinta':
        return 'ficar fora %s' % _contrair('de', _rotulo(modelo, r['base']))
    if t == 'dentro_da_tinta':
        return 'ficar dentro %s' % _contrair('de', _rotulo(modelo, r['base']))
    if t == 'sem_sobreposicao':
        return 'não passar por cima %s' % _contrair('de', _rotulo(modelo, outro))
    if t == 'distancia':
        return 'manter a distância %s' % _contrair('de', _rotulo(modelo, outro))
    if t == 'no_quadro':
        return 'ficar dentro da margem'
    if t == 'na_area_segura':
        return 'ficar dentro da área segura'
    return 'ficar na mesma linha %s' % _contrair('de', _rotulo(modelo, outro))


def _frase_f1(modelo, r, k, px):
    return '%s andou %s px para %s.' % (_maiuscula(_rotulo(modelo, k)), _px(px), _motivo(modelo, r, k))


def _frase_f2(modelo, r, px):
    base = _rotulo(modelo, r['base'])
    return '%s recuou %s px para %s continuar fora %s.' % (_maiuscula(base), _px(px), _rotulo(modelo, r['conteudo']),
                                                          _dela(base))


def _frase_f3(modelo, r, k, fator):
    return '%s ficou %s%% menor para %s.' % (_maiuscula(_rotulo(modelo, k)), _px((1.0 - fator) * POR_CENTO),
                                            _motivo(modelo, r, k))


def _frase_fundo(modelo, c, k):
    return '%s ficou no mesmo lugar em relação %s, como no seu arquivo, para não mudar de fundo.' % (
        _maiuscula(_rotulo(modelo, c)), _contrair('a', _rotulo(modelo, k)))


def _frase_sem_desenho(modelo, k, conteudos):
    rotulos = [_rotulo(modelo, c) for c in conteudos]
    lista = rotulos[0] if len(rotulos) == 1 else '%s e %s' % (', '.join(rotulos[:-1]), rotulos[-1])
    base = _rotulo(modelo, k)
    verbo = 'fica' if len(rotulos) == 1 else 'ficam'
    return ('O desdobra não tem o desenho %s e não conseguiu conferir se %s %s no mesmo fundo do seu arquivo. Confira '
            'este arquivo antes de confirmar.' % (_contrair('de', base), lista, verbo))


NOMES_DAS_BORDAS = {'esq': 'esquerda', 'topo': 'de cima', 'dir': 'direita', 'base': 'de baixo'}
DECIMO = 10.0  # numero-neutro: a casa decimal das frases (galeria._numero)


def _frase_crescimento(modelo, k, g, g_max):
    """A frase do crescimento acima do limite. As bordas sao as que a forma tocava no aprovado (a frase de
    proposta._base_passa_da_borda diz a borda nova). O valor mostrado nunca empata com o limite: o que passa dele por
    menos de uma casa sobe para a casa de cima."""
    base = _rotulo(modelo, k)
    lados = [NOMES_DAS_BORDAS[lado] for lado in LADOS if modelo['elementos'][k]['sangra'].get(lado)]
    if len(lados) == 1:
        bordas = 'à borda %s' % lados[0]
    else:
        bordas = 'às bordas %s e %s' % (', '.join(lados[:-1]), lados[-1])
    mostrado = round(g, 1)
    if _px(mostrado) == _px(g_max) or mostrado < g_max:
        mostrado = math.ceil(g * DECIMO) / DECIMO
    return ('%s precisou ficar %s vezes maior neste arquivo para continuar chegando %s, e o desdobra só aumenta até '
            '%s vezes sem pedir o seu olhar. Confira este arquivo antes de confirmar.' % (
                _maiuscula(base), _px(mostrado), bordas, _px(g_max)))


def _frase_pedido(modelo, r, valor):
    k = next((x for x in r['elementos'] if modelo['elementos'][x]['papel'] == 'movel'), r['elementos'][0])
    return '%s pede ajuste neste arquivo: faltam %s px para %s.' % (_maiuscula(_rotulo(modelo, k)), _px(valor),
                                                                    _motivo(modelo, r, k))
