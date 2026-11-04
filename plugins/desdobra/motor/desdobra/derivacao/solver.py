# -*- coding: utf-8 -*-
"""Restricoes por funcao e por medida, com forcas (a hierarquia do Cassowary), resolvidas por programacao linear.

Cada elemento tem tres variaveis no formato: x e y (canto da caixa) e s (escala sobre a caixa da mestre); a caixa e
[x, y, x + s.w0, y + s.h0], linear nas variaveis. As restricoes saem da funcao resolvida e da medida, nunca do nome
da camada (arquitetura-v1.md, 4.10; pesquisa/v1-estatico-sintese.md, 6). Forcas:
  - obrigatorias, so com fonte: a folha (area util, faixas, area segura) e as relacoes que a mestre ja satisfaz
    (elemento dentro do canvas continua dentro, e o membro inteiro de um bloco tambem; o lado que sangra continua
    sangrando; caixas que nao se tocam continuam sem se tocar, pelo eixo em que a mestre as separa);
  - fortes: razoes de corpo (elementos com a mesma funcao e a mesma regra mantem a razao entre si) e alinhamentos
    da mestre (bordas e centros iguais);
  - medias: posicao relativa, pela ancora de cada eixo confirmada pelo DA, e a margem da mestre ate cada borda
    (decisoes-v1.md, 101);
  - fracas: a regra de escala da funcao escolhida pelo DA.
As obrigatorias sao duras; as outras em ordem estrita (lexicografica): o menor erro das fortes fica preso, depois o
das medias, depois o das fracas. O Cassowary aproxima essa ordem com pesos (1e6, 1e3, 1); aqui ela e exata, e uma
fraca nunca vence uma media, qualquer que seja o tamanho do elemento ou do formato. A obrigatoria que nao fecha com as anteriores, na ordem acima, e a que
volta ao DA, com o nome e a fonte.

O problema e o do Cassowary, resolvido pelo HiGHS (scipy.optimize.linprog), e nao pelo kiwisolver: no corpus do M5 o
kiwisolver 1.5.1 (e o 1.4.9) abortou o processo inteiro em parte das solucoes (um erro interno que a biblioteca nao
converte em excecao, sem como recuperar), e o resultado dele variava de um processo para outro conforme o endereco
das variaveis na memoria. Cuidados numericos: posicoes em unidades do maior lado do formato; peso unico por restricao
dentro da forca (perturbacao), para o otimo ser unico; o vertice e refeito pelas restricoes ativas (minimos
quadrados) e arredondado no nucleo, para o resultado ser o mesmo em todo processo.
"""
import itertools

from desdobra import limites

FONTE_MESTRE = {'tipo': 'mestre', 'ref': 'arquitetura-v1.md, 4.10: relação que a mestre já satisfaz'}
FONTE_SINTESE = {'tipo': 'pesquisa', 'ref': 'pesquisa/v1-estatico-sintese.md, 6'}
FONTE_DA = {'tipo': 'briefing', 'ref': 'briefing/briefing-confirmado.json'}
CLASSES_AREA_SEGURA = ('texto', 'marca')
FORCAS = ('strong', 'medium', 'weak')
NOMES_FORCA = {'strong': 'forte', 'medium': 'media', 'weak': 'fraca'}
FOLGA_DO_OTIMO = 1e-6  # numero-neutro: folga numerica ao prender o otimo de uma forca antes da seguinte
PERTURBACAO = 1e-4  # numero-neutro: so desempata restricoes de mesma forca (o peso fica entre 1 e 1,1); nao decide forca
ATIVA = 1e-5  # numero-neutro: folga (em unidades do maior lado do formato, um centesimo de px em 1920) abaixo da qual a restricao conta como ativa no vertice
CONFERE = 1e-9  # numero-neutro: folga numerica do vertice refeito contra as obrigatorias


def conteudo(e):
    """Conteudo da peca: texto, marca e sujeito (decisoes-v1.md, 96), e o indeterminado com tinta (o DA nao disse o
    que e: pode ser um logo; revisao 2 do M5, B4)."""
    return e.get('classe') in ('texto', 'marca') or e.get('funcao') in ('sujeito', 'indeterminado')


def objeto_solto(e):
    """Elemento de base que e objeto na peca (rodada 3 do M5): opaco, nao sangra em lado nenhum e nao e veu. Ele nao
    e conteudo (decisoes-v1.md, 96), mas o conteudo nao pode passar a cobri-lo nem ser coberto por ele: entra no "nao
    sobrepor" e na colisao contra o conteudo (os icones de grafismo do KV de produto)."""
    return e.get('classe') == 'base' and e.get('funcao') not in ('veu_de_legibilidade', 'sujeito') and \
        bool(e.get('opaco')) and not any((e.get('sangra') or {}).values())


def par_que_nao_sobrepoe(a, b):
    """Par que entra no "nao sobrepor" e na colisao: conteudo com conteudo, ou conteudo com objeto solto."""
    return (conteudo(a) or objeto_solto(a)) and (conteudo(b) or objeto_solto(b)) and (conteudo(a) or conteudo(b))


def membro_no_formato(e, m, x0, y0, s, U):
    """Caixa (formas lineares) do membro m do bloco e no formato: o bloco anda com uma escala e um deslocamento so; o
    membro esta na caixa do KV (caixa_kv), e a caixa do elemento na mestre pode ser a da mestre propria."""
    c, ckv, mc = e['caixa'], e.get('caixa_kv') or e['caixa'], m['caixa']
    f = (c[2] - c[0]) / (ckv[2] - ckv[0]) if ckv[2] > ckv[0] else 1.0
    return [x0 + s * ((mc[0] - ckv[0]) * f / U), y0 + s * ((mc[1] - ckv[1]) * f / U),
            x0 + s * ((mc[2] - ckv[0]) * f / U), y0 + s * ((mc[3] - ckv[1]) * f / U)]


class NaoFecha(Exception):
    """Uma restricao obrigatoria nao fecha com as anteriores."""

    def __init__(self, restricao):
        super().__init__(restricao['nome'])
        self.restricao = restricao


class Lin:
    """Forma linear sobre as variaveis do layout: {indice: coeficiente} + constante."""

    def __init__(self, termos=None, const=0.0):
        self.termos, self.const = dict(termos or {}), float(const)

    def _mais(self, outro, sinal):
        if not isinstance(outro, Lin):
            return Lin(self.termos, self.const + sinal * float(outro))
        t = dict(self.termos)
        for k, v in outro.termos.items():
            t[k] = t.get(k, 0.0) + sinal * v
        return Lin(t, self.const + sinal * outro.const)

    def __add__(self, outro):
        return self._mais(outro, 1.0)

    def __sub__(self, outro):
        return self._mais(outro, -1.0)

    def __mul__(self, k):
        return Lin({i: v * float(k) for i, v in self.termos.items()}, self.const * float(k))

    def valor(self, v):
        return sum(c * v[i] for i, c in self.termos.items()) + self.const


def _disjuntas(a, b, tol):
    """Eixo e sentido em que a mestre separa as caixas a e b ('x', a antes de b, folga normalizada), ou None."""
    opcoes = []
    for eixo, (i0, i1) in (('x', (0, 2)), ('y', (1, 3))):
        if a[i1] <= b[i0] + tol:
            opcoes.append((eixo, True, b[i0] - a[i1]))
        elif b[i1] <= a[i0] + tol:
            opcoes.append((eixo, False, a[i0] - b[i1]))
    return opcoes


def alinhamentos(elementos, tol):
    """Pares alinhados na mestre: (eixo, tipo, i, j) com tipo em inicio, centro, fim.

    Ficam de fora o eixo em que um dos dois sangra (a borda ja esta presa ao canvas por obrigatoria) e o centro
    quando inicio e fim ja estao alinhados (redundante)."""
    saida = []
    lados = {'x': ('esq', 'dir'), 'y': ('topo', 'base')}
    for (i, a), (j, b) in itertools.combinations(enumerate(elementos), 2):
        for eixo, (k0, k1) in (('x', (0, 2)), ('y', (1, 3))):
            if any((a.get('sangra') or {}).get(l) or (b.get('sangra') or {}).get(l) for l in lados[eixo]):
                continue
            ca, cb = a['caixa'], b['caixa']
            inicio = abs(ca[k0] - cb[k0]) <= tol
            fim = abs(ca[k1] - cb[k1]) <= tol
            if inicio:
                saida.append((eixo, 'inicio', i, j))
            if not (inicio and fim) and abs((ca[k0] + ca[k1]) - (cb[k0] + cb[k1])) <= 2 * tol:  # numero-neutro: soma das bordas e o dobro do centro
                saida.append((eixo, 'centro', i, j))
            if fim:
                saida.append((eixo, 'fim', i, j))
    return saida


def _vertice(lineares, valores, n):
    """Refaz o vertice do otimo pelas restricoes ativas, sem o solver; None quando nao fecha."""
    import numpy as np
    linhas, lados = [], []
    for forma, op, obrigatoria in lineares:
        r = forma.valor(valores)
        if (op == 'eq' or abs(r) <= ATIVA) and (obrigatoria or abs(r) <= ATIVA):
            linha = np.zeros(n)
            for i, c in forma.termos.items():
                linha[i] = c
            linhas.append(linha)
            lados.append(-forma.const)
    if not linhas:
        return None
    A, b = np.array(linhas), np.array(lados)
    if np.linalg.matrix_rank(A) < n:
        return None
    v = np.linalg.lstsq(A, b, rcond=None)[0]
    for forma, op, obrigatoria in lineares:
        if not obrigatoria:
            continue
        r = forma.valor(v)
        if (op == 'eq' and abs(r) > CONFERE) or (op == 'ge' and r < -CONFERE) or (op == 'le' and r > CONFERE):
            return None
    return [float(x) for x in v]


def _matrizes(obrigatorias, n, extra=0):
    import numpy as np
    A_ub, b_ub, A_eq, b_eq = [], [], [], []
    for forma, op, _r in obrigatorias:
        linha = np.zeros(n + extra)
        for i, c in forma.termos.items():
            linha[i] = c
        if op == 'eq':
            A_eq.append(linha)
            b_eq.append(-forma.const)
        elif op == 'le':
            A_ub.append(linha)
            b_ub.append(-forma.const)
        else:
            A_ub.append(-linha)
            b_ub.append(forma.const)
    return A_ub, b_ub, A_eq, b_eq


def _linprog(c, A_ub, b_ub, A_eq, b_eq, limites_vars):
    import numpy as np
    from scipy.optimize import linprog
    return linprog(np.asarray(c, float), A_ub=np.asarray(A_ub) if A_ub else None, b_ub=b_ub or None,
                   A_eq=np.asarray(A_eq) if A_eq else None, b_eq=b_eq or None, bounds=limites_vars, method='highs')


def _cabe(obrigatorias, n):
    A_ub, b_ub, A_eq, b_eq = _matrizes(obrigatorias, n)
    r = _linprog([0.0] * n, A_ub, b_ub, A_eq, b_eq, [(None, None)] * n)
    return r.status == 0


def _resolver_lp(obrigatorias, suaves, n):
    """O otimo da soma ponderada dos erros das nao obrigatorias, com as obrigatorias duras (a hierarquia de forcas do
    Cassowary), pelo HiGHS. Sem solucao, a obrigatoria que nao fecha com as anteriores (na ordem em que entraram) e
    achada por bissecao e volta em NaoFecha."""
    if not _cabe(obrigatorias, n):
        baixo, alto = 0, len(obrigatorias)
        while alto - baixo > 1:
            meio = (baixo + alto) // 2  # numero-neutro: bissecao
            if _cabe(obrigatorias[:meio], n):
                baixo = meio
            else:
                alto = meio
        raise NaoFecha(obrigatorias[alto - 1][2])
    m = len(suaves)
    A_ub, b_ub, A_eq, b_eq = _matrizes(obrigatorias, n, 2 * m)  # numero-neutro: erro para mais e para menos
    import numpy as np
    for k, (forma, _forca, _peso, op) in enumerate(suaves):
        linha = np.zeros(n + 2 * m)  # numero-neutro: idem
        for i, c in forma.termos.items():
            linha[i] = c
        if op == 'ge':
            # forma >= 0 com o deficit (erro para menos) pago: -forma - e_menos <= const
            linha = -linha
            linha[n + m + k] = -1.0
            A_ub.append(linha)
            b_ub.append(forma.const)
            continue
        linha[n + k], linha[n + m + k] = 1.0, -1.0
        A_eq.append(linha)
        b_eq.append(-forma.const)
    limites_vars = [(None, None)] * n + [(0, None)] * (2 * m)  # numero-neutro: idem
    r = None
    # ordem estrita: o otimo de cada forca fica preso antes da seguinte (forte, depois media, depois fraca)
    for forca in FORCAS:
        pesos = [p if f == forca else 0.0 for _x, f, p, _op in suaves]
        if not any(pesos):
            continue
        c = [0.0] * n + pesos * 2  # numero-neutro: erro para mais e para menos
        novo = _linprog(c, A_ub, b_ub, A_eq, b_eq, limites_vars)
        if novo.status != 0:
            if r is None:
                raise NaoFecha({'nome': 'otimo_sem_solucao', 'forca': 'obrigatoria', 'fonte': FONTE_MESTRE,
                                'elementos': []})
            # a forca anterior ja tem solucao: a folga numerica do otimo preso nao deixou a seguinte andar; fica a
            # solucao da anterior (que cumpre todas as obrigatorias)
            break
        r = novo
        A_ub.append(np.asarray(c, float))
        b_ub.append(float(r.fun) + FOLGA_DO_OTIMO * (1.0 + abs(float(r.fun))))
    if r is None:
        r = _linprog([0.0] * (n + 2 * m), A_ub, b_ub, A_eq, b_eq, limites_vars)  # numero-neutro: idem
        if r.status != 0:
            raise NaoFecha({'nome': 'otimo_sem_solucao', 'forca': 'obrigatoria', 'fonte': FONTE_MESTRE, 'elementos': []})
    return [float(x) for x in r.x[:n]]


def resolver(elementos, mestre, formato, areas, regras):
    """Resolve o layout de um formato.

    elementos: os da mestre (caixa na mestre, sangra, classe, funcao, ancora (x, y)); mestre: (largura, altura) do
    canvas da mestre; formato: (largura, altura) da composicao; areas: de formatos.areas; regras: [escala da regra
    por elemento]. Devolve (caixas [[x0, y0, x1, y1]], escalas, restricoes) ou levanta NaoFecha com a obrigatoria."""
    Wm, Hm = (float(v) for v in mestre)
    W, H = (float(v) for v in formato)
    tol_al = limites.valor('derivacao.alinhamento_tolerancia_px')
    tol_col = limites.valor('derivacao.colisao_tolerancia_px')
    s_min = limites.valor('derivacao.escala_min')
    U = max(W, H)
    Wu, Hu = W / U, H / U
    n = 3 * len(elementos)  # numero-neutro: x, y e s por elemento
    restricoes, lineares = [], []
    obrigatorias, suaves = [], []

    def caixa(i):
        x, y, s = Lin({3 * i: 1.0}), Lin({3 * i + 1: 1.0}), Lin({3 * i + 2: 1.0})  # numero-neutro: posicoes das variaveis
        c = elementos[i]['caixa']
        w0, h0 = (c[2] - c[0]) / U, (c[3] - c[1]) / U
        return x, y, x + s * w0, y + s * h0

    def escala(i):
        return Lin({3 * i + 2: 1.0})  # numero-neutro: posicao da variavel s

    def obrigatoria(nome, forma, op, fonte, elems):
        r = {'nome': nome, 'forca': 'obrigatoria', 'fonte': fonte, 'elementos': elems}
        obrigatorias.append((forma, op, r))
        restricoes.append(r)
        lineares.append((forma, op, True))

    def outra(nome, forma, forca, fonte, elems, op='eq'):
        peso = 1.0 + len(restricoes) * PERTURBACAO
        suaves.append((forma, forca, peso, op))
        restricoes.append({'nome': nome, 'forca': NOMES_FORCA[forca], 'fonte': fonte, 'elementos': elems})
        lineares.append((forma, op, False))

    util = [v / U for v in ((areas.get('area_util') or {}).get('caixa') or [0.0, 0.0, W, H])]
    fonte_util = (areas.get('area_util') or {}).get('fonte') or FONTE_MESTRE
    segura = areas.get('area_segura')
    for i, e in enumerate(elementos):
        obrigatoria('escala_positiva:%s' % e['id'], escala(i) - s_min, 'ge', FONTE_MESTRE, [e['id']])
        x0, y0, x1, y1 = caixa(i)
        sg = e['sangra']
        # folha: o elemento que nao sangra fica dentro da area util (fora das faixas); o texto e a marca, dentro da
        # area segura
        lim = list(util)
        fonte_lado = [fonte_util] * 4
        if segura is not None and e['classe'] in CLASSES_AREA_SEGURA:
            sc = [v / U for v in segura['caixa']]
            for k, pega in ((0, max), (1, max), (2, min), (3, min)):
                novo = pega(lim[k], sc[k])
                if novo != lim[k]:
                    lim[k], fonte_lado[k] = novo, segura['fonte']
        for k, lado, forma, op in ((0, 'esq', x0 - lim[0], 'ge'), (1, 'topo', y0 - lim[1], 'ge'),
                                   (2, 'dir', x1 - lim[2], 'le'), (3, 'base', y1 - lim[3], 'le')):
            if sg[lado]:
                continue
            nome = 'dentro_da_area_util' if fonte_lado[k] is not FONTE_MESTRE else 'dentro_do_canvas'
            if segura is not None and fonte_lado[k] is segura['fonte']:
                nome = 'dentro_da_area_segura'
            obrigatoria('%s_%s:%s' % (nome, lado, e['id']), forma, op, fonte_lado[k], [e['id']])
    for i, e in enumerate(elementos):
        x0, y0, x1, y1 = caixa(i)
        sg = e['sangra']
        # mestre: o lado que sangra continua com o corte do asset fora do canvas (o asset acaba na borda do documento,
        # que numa prancheta fica alem da borda dela)
        c, a = e['caixa'], e.get('caixa_asset') or e['caixa']
        s = escala(i)
        a0, a1 = x0 + s * ((a[0] - c[0]) / U), y0 + s * ((a[1] - c[1]) / U)
        a2, a3 = x1 + s * ((a[2] - c[2]) / U), y1 + s * ((a[3] - c[3]) / U)
        for lado, forma, op in (('esq', a0, 'le'), ('topo', a1, 'le'), ('dir', a2 - Wu, 'ge'), ('base', a3 - Hu, 'ge')):
            if sg[lado]:
                obrigatoria('sangria_%s:%s' % (lado, e['id']), forma, op, FONTE_MESTRE, [e['id']])
        if segura is not None and e['classe'] in CLASSES_AREA_SEGURA and any(sg.values()):
            restricoes.append({'nome': 'area_segura_com_sangria:%s' % e['id'], 'forca': 'registro',
                               'fonte': segura['fonte'], 'elementos': [e['id']]})
    for i, e in enumerate(elementos):
        x0, y0, _x1, _y1 = caixa(i)
        # membro do bloco que estava inteiro no canvas (ou e texto ou marca) continua inteiro: dentro da area util, e
        # o texto e a marca dentro da area segura (revisao 2 do M5, A3). Entra depois da sangria: quando o bloco que
        # sangra nao deixa o membro inteiro, e esta a obrigatoria que volta ao DA
        for mb_ in e.get('membros_caixas') or []:
            mx0, my0, mx1, my1 = membro_no_formato(e, mb_, x0, y0, escala(i), U)
            lim_m, fonte_m = list(util), [fonte_util] * 4
            if segura is not None and mb_['classe'] in CLASSES_AREA_SEGURA:
                sc = [v / U for v in segura['caixa']]
                for k, pega in ((0, max), (1, max), (2, min), (3, min)):
                    novo = pega(lim_m[k], sc[k])
                    if novo != lim_m[k]:
                        lim_m[k], fonte_m[k] = novo, segura['fonte']
            for k, lado, forma, op in ((0, 'esq', mx0 - lim_m[0], 'ge'), (1, 'topo', my0 - lim_m[1], 'ge'),
                                       (2, 'dir', mx1 - lim_m[2], 'le'), (3, 'base', my1 - lim_m[3], 'le')):
                nome = 'membro_dentro_da_area_util' if fonte_m[k] is not FONTE_MESTRE else 'membro_dentro_do_canvas'
                if segura is not None and fonte_m[k] is segura['fonte']:
                    nome = 'membro_dentro_da_area_segura'
                obrigatoria('%s_%s:%s:%d' % (nome, lado, e['id'], mb_['raiz']), forma, op, fonte_m[k], [e['id']])
    for (i, a), (j, b) in itertools.combinations(enumerate(elementos), 2):
        # nao sobrepor entre conteudo, e entre conteudo e objeto solto: luz, veu e cena que sangra nao empurram conteudo
        # (decisoes-v1.md, 96; rodada 3)
        if not par_que_nao_sobrepoe(a, b):
            continue
        opcoes = _disjuntas(a['caixa'], b['caixa'], 0.0)
        if not opcoes:
            continue
        eixo, a_antes, _folga = max(opcoes, key=lambda o: o[2] / (Wm if o[0] == 'x' else Hm))
        ca, cb = caixa(i), caixa(j)
        k0, k1 = (0, 2) if eixo == 'x' else (1, 3)
        primeiro, segundo = (ca, cb) if a_antes else (cb, ca)
        obrigatoria('nao_sobrepor_%s:%s:%s' % (eixo, a['id'], b['id']), primeiro[k1] - segundo[k0] - tol_col / U,
                    'le', FONTE_MESTRE, [a['id'], b['id']])
    # fortes: razao de corpo e alinhamentos
    # razao de corpo: todas as funcoes de texto mantem a razao da mestre entre si (decisoes-v1.md, 97); fora do
    # texto, entre elementos da mesma funcao e da mesma regra
    por_regra = {}
    for i, e in enumerate(elementos):
        chave = ('texto', '') if e['classe'] == 'texto' else (e['funcao'], e['regra'])
        por_regra.setdefault(chave, []).append(i)
    for (_funcao, _regra), idx in sorted(por_regra.items()):
        for i, j in zip(idx, idx[1:]):
            outra('razao_de_corpo:%s:%s' % (elementos[i]['id'], elementos[j]['id']), escala(i) - escala(j), 'strong',
                  FONTE_SINTESE, [elementos[i]['id'], elementos[j]['id']])
    # grupos por eixo (rodada 3): elementos presos um ao outro por alinhamento ou proximidade andam por uma ancora so
    grupo = {'x': list(range(len(elementos))), 'y': list(range(len(elementos)))}

    def raiz_g(eixo, k):
        while grupo[eixo][k] != k:
            k = grupo[eixo][k]
        return k

    def juntar_g(eixo, a, b):
        ra, rb = raiz_g(eixo, a), raiz_g(eixo, b)
        grupo[eixo][max(ra, rb)] = min(ra, rb)
    for eixo, tipo, i, j in alinhamentos(elementos, tol_al):
        juntar_g(eixo, i, j)
        ci, cj = caixa(i), caixa(j)
        k0, k1 = (0, 2) if eixo == 'x' else (1, 3)
        mi, mj = elementos[i]['caixa'], elementos[j]['caixa']
        # a diferenca da mestre (dentro da tolerancia) vai na escala media dos dois: a mestre continua satisfazendo, e
        # dois elementos de mesma escala alinhados nas duas bordas com um px de diferenca nao prendem a escala na
        # proporcao do formato (rodada 3: no 2048x720 isso prendia os textos em largura do formato / largura da mestre)
        fator = (escala(i) + escala(j)) * (1.0 / U / 2.0)  # numero-neutro: media das duas escalas
        if tipo == 'inicio':
            forma = ci[k0] - cj[k0] - fator * (mi[k0] - mj[k0])
        elif tipo == 'fim':
            forma = ci[k1] - cj[k1] - fator * (mi[k1] - mj[k1])
        else:
            forma = ci[k0] + ci[k1] - cj[k0] - cj[k1] - fator * (mi[k0] + mi[k1] - mj[k0] - mj[k1])
        outra('alinhamento_%s_%s:%s:%s' % (eixo, tipo, elementos[i]['id'], elementos[j]['id']), forma, 'strong',
              FONTE_SINTESE, [elementos[i]['id'], elementos[j]['id']])
    # margem da mestre ate cada borda, proporcional ao eixo, como media (decisoes-v1.md, 101: abaixo da razao de
    # corpo e dos alinhamentos, para nao encolher o texto); texto e marca com um minimo obrigatorio: a fracao do lado
    # curto do formato, ou a margem da mestre na escala de contain, a menor das duas (decisoes-v1.md, 98)
    r_min = limites.valor('derivacao.margem_minima_lado_curto')
    contain = min(W / Wm, H / Hm)
    fonte_min = {'tipo': 'limite', 'ref': 'derivacao.margem_minima_lado_curto'}
    for i, e in enumerate(elementos):
        x0, y0, x1, y1 = caixa(i)
        c = e['caixa']
        margens = (('esq', x0, c[0] / Wm * Wu, c[0]), ('topo', y0, c[1] / Hm * Hu, c[1]),
                   ('dir', Lin({}, Wu) - x1, (Wm - c[2]) / Wm * Wu, Wm - c[2]),
                   ('base', Lin({}, Hu) - y1, (Hm - c[3]) / Hm * Hu, Hm - c[3]))
        for lado, dist, proporcional, na_mestre in margens:
            if e['sangra'][lado] or na_mestre <= 0:
                continue
            outra('margem_da_mestre_%s:%s' % (lado, e['id']), dist - proporcional, 'medium', FONTE_MESTRE, [e['id']],
                  op='ge')
            if e['classe'] in CLASSES_AREA_SEGURA:
                minimo = min(r_min * min(W, H), na_mestre * contain) / U
                obrigatoria('margem_minima_%s:%s' % (lado, e['id']), dist - minimo, 'ge', fonte_min, [e['id']])
    # proximidade da mestre (rodada 3): conteudo e objeto solto, empilhados e perto um do outro na mestre, mantem a
    # distancia da mestre, na escala media dos dois (forte)
    perto = limites.valor('derivacao.proximidade_max') * min(Wm, Hm)
    for (i, a), (j, b) in itertools.combinations(enumerate(elementos), 2):
        if any(a['sangra'].values()) or any(b['sangra'].values()):
            continue
        # so entre conteudo e objeto solto (o titulo e os icones): entre textos, a razao de corpo e as ancoras ja dao o
        # espaco, como nos formatos que o DA aprovou
        if not ((conteudo(a) and objeto_solto(b)) or (objeto_solto(a) and conteudo(b))):
            continue
        ca, cb = a['caixa'], b['caixa']
        for eixo, (k0, k1), (o0, o1) in (('x', (0, 2), (1, 3)), ('y', (1, 3), (0, 2))):
            if min(ca[o1], cb[o1]) - max(ca[o0], cb[o0]) <= 0:
                continue
            for (pi, p_), (qi, q_) in (((i, ca), (j, cb)), ((j, cb), (i, ca))):
                gap = q_[k0] - p_[k1]
                if 0 <= gap <= perto:
                    fp, fq = caixa(pi), caixa(qi)
                    forma = fq[k0] - fp[k1] - (escala(pi) + escala(qi)) * (gap / U / 2.0)  # numero-neutro: media das duas escalas
                    outra('proximidade_%s:%s:%s' % (eixo, elementos[pi]['id'], elementos[qi]['id']), forma, 'strong',
                          FONTE_MESTRE, [elementos[pi]['id'], elementos[qi]['id']])
                    juntar_g(eixo, pi, qi)

    def area(k):
        c = elementos[k]['caixa']
        return (c[2] - c[0]) * (c[3] - c[1])

    # o grupo de elementos presos (alinhados, ou conteudo e objeto solto proximos) anda por uma ancora so, naquele eixo:
    # com a borda ou a distancia presa, as ancoras dos outros so prenderiam a escala do grupo (rodada 3). Vale a do
    # maior membro
    principal = {}
    for eixo in ('x', 'y'):
        membros = {}
        for k in range(len(elementos)):
            membros.setdefault(raiz_g(eixo, k), []).append(k)
        for ks in membros.values():
            # a ancora que o DA deu ao proprio elemento vale sobre a da funcao (revisao 3, M1): entre os membros com
            # ancora propria naquele eixo, o maior; sem nenhum, o maior do grupo
            ex = 0 if eixo == 'x' else 1
            proprias = [k for k in ks if (elementos[k].get('ancora_explicita') or (False, False))[ex]]
            escolhido = max(proprias or ks, key=lambda k: (area(k), -k))
            for k in ks:
                principal[(eixo, k)] = k == escolhido
            if len(ks) > 1:
                caidas = [[elementos[k]['id'], elementos[k]['ancora'][ex]] for k in ks if k != escolhido]
                restricoes.append({'nome': 'ancora_do_grupo_%s:%s' % (eixo, elementos[escolhido]['id']), 'forca': 'registro',
                                   'fonte': FONTE_DA, 'elementos': [elementos[escolhido]['id']] + [c[0] for c in caidas],
                                   'medidas': {'ancora': elementos[escolhido]['ancora'][ex], 'ancoras_sem_efeito': caidas,
                                               'propria': bool(proprias)}})
    # conteudo nao encolhe para cumprir as outras relacoes (decisoes-v1.md, 132 e 133): forte, escala de pelo menos
    # derivacao.escala_conteudo_forte_da_regra da regra; obrigatoria, o piso derivacao.escala_conteudo_min_da_regra
    # (por ultimo entre as obrigatorias: quando nao fecha, e o piso que volta ao DA, com nome e fonte)
    forte_c = limites.valor('derivacao.escala_conteudo_forte_da_regra')
    piso_c = limites.valor('derivacao.escala_conteudo_min_da_regra')
    fonte_piso = {'tipo': 'limite', 'ref': 'derivacao.escala_conteudo_min_da_regra'}
    fonte_forte = {'tipo': 'limite', 'ref': 'derivacao.escala_conteudo_forte_da_regra'}
    for i, e in enumerate(elementos):
        if conteudo(e) and regras[i]:
            obrigatoria('escala_minima_de_conteudo:%s' % e['id'], escala(i) - piso_c * regras[i], 'ge', fonte_piso,
                        [e['id']])
            outra('escala_de_conteudo:%s' % e['id'], escala(i) - forte_c * regras[i], 'strong', fonte_forte, [e['id']],
                  op='ge')
    # distancia entre linhas (e colunas) de conteudo (decisoes-v1.md, 135): entre um elemento de conteudo e o vizinho de
    # conteudo mais perto naquele eixo (sem sobreposicao na mestre, com as projecoes no outro eixo se tocando), a
    # distancia da mestre na escala media dos dois, forte; e o piso obrigatorio de derivacao.distancia_entre_linhas_min
    # dela, por ultimo entre as obrigatorias (quando nao fecha, e ele que volta ao DA, com nome e fonte)
    piso_d = limites.valor('derivacao.distancia_entre_linhas_min')
    fonte_d = {'tipo': 'limite', 'ref': 'derivacao.distancia_entre_linhas_min'}
    vistos = set()
    for i, a in enumerate(elementos):
        if not conteudo(a):
            continue
        ca = a['caixa']
        for eixo, (k0, k1), (o0, o1) in (('x', (0, 2), (1, 3)), ('y', (1, 3), (0, 2))):
            melhor = None
            for j, b in enumerate(elementos):
                if j == i or not conteudo(b):
                    continue
                cb = b['caixa']
                if min(ca[o1], cb[o1]) - max(ca[o0], cb[o0]) <= 0:
                    continue
                gap = cb[k0] - ca[k1]
                if gap > 0 and (melhor is None or gap < melhor[0]):
                    melhor = (gap, j)
            if melhor is None or (eixo, i, melhor[1]) in vistos:
                continue
            vistos.add((eixo, i, melhor[1]))
            gap, j = melhor
            fa, fb = caixa(i), caixa(j)
            dist = fb[k0] - fa[k1]
            media = (escala(i) + escala(j)) * (gap / U / 2.0)  # numero-neutro: media das duas escalas
            ids = [elementos[i]['id'], elementos[j]['id']]
            obrigatoria('distancia_minima_entre_conteudo:%s:%s:%s' % (eixo, ids[0], ids[1]), dist - media * piso_d, 'ge',
                        fonte_d, ids)
            # em fracao da distancia da mestre, para pesar como a escala de conteudo (as duas sao fortes)
            outra('distancia_entre_conteudo:%s:%s:%s' % (eixo, ids[0], ids[1]), (dist - media) * (U / gap), 'strong',
                  FONTE_MESTRE, ids, op='ge')
    # medias: ancora por eixo, posicao proporcional ao canvas
    formas_ancora = []
    for i, e in enumerate(elementos):
        x0, y0, x1, y1 = caixa(i)
        c = e['caixa']
        ax, ay = e['ancora']
        if ax == 'esquerda':
            forma_x = x0 - c[0] / Wm * Wu
        elif ax == 'direita':
            forma_x = x1 - (Wu - (Wm - c[2]) / Wm * Wu)
        else:
            forma_x = x0 + x1 - (c[0] + c[2]) / Wm * Wu
        if ay == 'topo':
            forma_y = y0 - c[1] / Hm * Hu
        elif ay == 'base':
            forma_y = y1 - (Hu - (Hm - c[3]) / Hm * Hu)
        else:
            forma_y = y0 + y1 - (c[1] + c[3]) / Hm * Hu
        if principal[('x', i)]:
            outra('ancora_x_%s:%s' % (ax, e['id']), forma_x, 'medium', FONTE_DA, [e['id']])
            formas_ancora.append((restricoes[-1], forma_x))
        if principal[('y', i)]:
            outra('ancora_y_%s:%s' % (ay, e['id']), forma_y, 'medium', FONTE_DA, [e['id']])
            formas_ancora.append((restricoes[-1], forma_y))
    # fracas: a regra de escala
    for i, e in enumerate(elementos):
        outra('regra_de_escala_%s:%s' % (e['regra'], e['id']), escala(i) - regras[i], 'weak', FONTE_DA, [e['id']])
    if not elementos:
        return [], [], []
    valores = _resolver_lp(obrigatorias, suaves, n)
    refeito = _vertice(lineares, valores, n)
    if refeito is not None:
        valores = refeito
    # quanto cada ancora ficou de fora, em px do formato (revisao 3, M1): a ancora que uma forca maior venceu nao
    # some em silencio
    for r, forma in formas_ancora:
        r['medidas'] = {'desvio_px': round(abs(forma.valor(valores)) * U, 2) + 0.0}
    caixas, escalas = [], []
    for i, e in enumerate(elementos):
        x, y, s = valores[3 * i] * U, valores[3 * i + 1] * U, valores[3 * i + 2]  # numero-neutro: posicoes das variaveis
        c = e['caixa']
        caixas.append([x, y, x + s * (c[2] - c[0]), y + s * (c[3] - c[1])])
        escalas.append(s)
    return caixas, escalas, restricoes
