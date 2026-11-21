# -*- coding: utf-8 -*-
"""Galeria de variantes para o formato sem familia (decisoes-v1.md, 164 e 166; as notas de 05/11 e a calibracao de
19/11 contra as metas do Duda no KV do cartaz).

Nenhum formato volta ao DA sem sugestao, e o desdobra parte de um KV so: na troca de orientacao e na proporcao fora
da faixa de familia, o motor monta de derivacao.galeria_variantes_min a derivacao.galeria_variantes_max versoes de
fato diferentes, so com os blocos do proprio KV (sem modelo pronto e sem nada aprendido de outras pecas); o DA escolhe
uma e ajusta no palco. A familia na faixa copia o KV e nao passa por aqui.

Sem molde fixo por proporcao (166): cada arquetipo so gera candidatas, e a escolha e pela nota. Os blocos: o conteudo
da mestre cortado em atomos na ordem de leitura (as linhas da mestre vertical; os itens da horizontal, coluna por
coluna); o legal fino perto da borda fica colado a ela; a cena e a arte que sangram ficam de fundo. Cada candidata
combina:
  - a figura (o sujeito recortado que cobre derivacao.galeria_figura_area_min do KV): numa banda de um dos quatro
    lados, presa a borda que ela toca no KV, ou de fundo como no KV. O conteudo vai para o espaco livre e cresce para
    ocupa-lo (19/11: o sujeito fica do lado em que esta no KV, e a nota pune o outro lado). No KV deitado, no formato
    em pe ou quadrado, a figura de fundo fica atras do conteudo (figura_de_fundo; decisoes-v1.md, n 202, revendo a 96
    so neste caso): o conteudo sobre ela nao e falha, e ela fica no formato nos lados que nao sangram ou centrada e
    sangrando nos dois lados do eixo em que e maior que ele;
  - sem figura, a imagem livre: o conteudo reunido numa parte do lado maior (derivacao.galeria_conteudo_fracao) e a
    arte do KV que sangra em parte dos lados (ou so a cena) livre no resto, dos dois lados;
  - a faixa de borda (o bloco fino e largo que abre ou fecha a leitura colado ao topo ou a base): presa a essa borda
    de ponta a ponta, so sobre o conteudo, ou no fluxo;
  - os itens iguais em sequencia (a lista): como no KV ou girados para o outro eixo;
  - a melhor particao dos atomos em trilhas (colunas ou linhas) ou a melhor do outro tipo, na ordem do KV ou
    espelhada ao longo do lado maior do quadro.
Cada bloco do conteudo cresce sobre a regra verdadeira dele (regras_relativas: o legal de regra constante nao cresce
com o titulo) ate derivacao.galeria_teto_sobre_regra, com hierarquia: o titulo cresce mais
(derivacao.galeria_expoente_titulo, ate derivacao.galeria_titulo_sobre_outros_max dos outros textos; 19/11) e as
marcas, o contato e o legal crescem menos (derivacao.galeria_expoente_secundario). Nenhum bloco de conteudo fica abaixo
do piso da 133 no fluxo: quando nao cabe, a figura cede primeiro (encolhe por derivacao.galeria_figura_reducao_passo ate
derivacao.galeria_figura_reducao_min); se ainda nao couber, o conteudo fica no piso e a conferencia diz o que falhou.

Cada candidata passa pelo solver do repositorio como uma mestre sintetica do tamanho do formato: as caixas do fluxo sao
a mestre e a regra de cada bloco do fluxo e a escala que o fluxo deu (o solver so resolve o que o fluxo deixou em
conflito). Depois a candidata e conferida contra a mestre verdadeira (quadro, area segura, sobreposicao nova, piso da
133 contra a regra verdadeira, distancia da 135 e a validacao do motor) e ganha avisos, que nunca bloqueiam. A nota
(derivacao.galeria_nota_pesos) soma a escala do conteudo (saturada em derivacao.galeria_nota_satura), o menor corpo,
a razao entre os blocos (97), a figura, o conteudo sobre a figura, o espaco vazio, a ordem do KV e as falhas (a prevista
antes do solver e, depois dele, a da conferencia e o bloco que o solver esmagou, que tambem e falha da versao). Vao a
galeria as limpas primeiro, da melhor nota para a pior; a versao com falha so entra para chegar ao minimo de versoes, e
mais candidatas vao ao solver enquanto faltar versao limpa para o minimo.

O layout editado pelo DA no palco passa pela mesma conferencia. O piso da 133 ou da 135 que o elemento mexido ou
escalado pelo DA fura e decisao dele (decisoes_do_da; M7b, D5, pergunta 10 do plano): sai das falhas ("Pede ajuste")
com o valor a vista. O elemento que o solver mexeu continua falha, e a validacao do motor continua devolvendo o formato.

So previa, em memoria: nada aqui grava arquivo, e o que o "desdobra derivar" grava nao muda. Origem: o prototipo da
galeria de 05/11 (revisado) e o prototipo "fluxo" de 19/11, escolhido pelo juiz, com os enxertos dos prototipos "zonas"
(piso por bloco, saturacao da nota, teto do titulo, limpas primeiro) e "busca" (menor corpo, bloco esmagado, falhas
previstas, legal do lado do conteudo).
"""
import copy
import itertools
import math
import statistics

from desdobra import limites
from desdobra.derivacao import elementos as mod_elementos
from desdobra.derivacao import escala as mod_escala
from desdobra.derivacao import familia as mod_familia
from desdobra.derivacao import formatos as mod_formatos
from desdobra.derivacao import nucleo as mod_nucleo
from desdobra.derivacao import silhueta as mod_silhueta
from desdobra.derivacao import solver as mod_solver
from desdobra.derivacao import validacao as mod_validacao

DESEMPATE = 1e-12  # numero-neutro: folga numerica ao comparar a pontuacao de duas particoes
FOLGA_COTA = 1e-9  # numero-neutro: folga numerica da cota de cima da pontuacao (so corta o que certamente perde)
MESMA_ESCALA = 1e-6  # numero-neutro: a escala do fluxo igual a provisoria (a reserva do legal nao muda mais)
FOLGA_PISO = 1e-9  # numero-neutro: folga numerica do piso da 133
FOLGA_RELATIVA = 1e-6  # numero-neutro: folga numerica relativa (a escala colocada um fio acima do piso)
# o arredondamento das caixas a nucleo.CASAS_PX casas (_elementos) muda a largura em ate uma casa (meia casa em cada
# borda); a escala colocada no piso leva o dobro disso de folga, sobre a largura em px
ERRO_DO_ARREDONDAMENTO = 2.0  # numero-neutro: o dobro do erro do arredondamento
FOLGA_PONTO_FIXO = 1e-3  # numero-neutro: folga numerica do ponto fixo (peso da hierarquia, vao da 135)
MINUSCULO = 1e-6  # numero-neutro: piso numerico do log (escala zero)
VOLTAS_HIERARQUIA = 4  # numero-neutro: ponto fixo do peso da hierarquia (converge em duas ou tres no tipico)
# o vao da 135 depende da escala do fluxo e a escala do vao; tres voltas cercam o ponto fixo dos dois lados (a primeira,
# na regra, acima ou abaixo dele; a segunda do outro lado; a terceira de novo do lado que cumpre)
VOLTAS_135 = 3  # numero-neutro: voltas do ponto fixo do vao da 135
# os blocos que crescem menos que o conteudo (derivacao.galeria_expoente_secundario)
FUNCOES_SECUNDARIAS = ('logo_principal', 'logo_de_parceiro', 'assinatura_institucional', 'selo', 'url_ou_contato',
                       'texto_legal')
ROTULO = {'titulo': 'o título', 'texto_de_apoio': 'o texto', 'cta': 'a chamada', 'url_ou_contato': 'o contato',
          'texto_legal': 'o legal', 'informacao_de_evento': 'a informação', 'destaque_numerico': 'o destaque',
          'icone_de_cta': 'o ícone', 'logo_principal': 'a marca', 'assinatura_institucional': 'a assinatura',
          'selo': 'o selo', 'logo_de_parceiro': 'os logos', 'grafismo': 'o grafismo', 'sujeito': 'a foto',
          'imagem': 'a imagem', 'fundo': 'o fundo'}
ROTULO_GERAL = 'o elemento'
# a concordancia de "inteiro" com o artigo do rotulo (a frase da relacao de fundo quebrada, decisao 199, 3)
INTEIRO = {'o': 'inteiro', 'a': 'inteira', 'os': 'inteiros', 'as': 'inteiras'}
# M7b, D5: os pisos que a decisao do DA fura sem pedir ajuste (133 e 135); o resto das falhas continua falha
PISOS_DO_DA = ('abaixo_do_piso_da_regra', 'distancia_menor_que_na_mestre')
# n 202: a validacao do motor da foto de fundo acima de um conteudo na pilha; na conferencia, a falha com o mesmo nome
# e a frase da causa (_conferir)
FUNDO_ACIMA = 'figura_de_fundo_acima_do_conteudo'
# revisao 1 da fase D do M7b: a borda do KV em que o asset acaba, na frase do corte a vista (corte_a_mostra)
BORDAS_DO_KV = {'esq': 'na borda esquerda', 'topo': 'no topo', 'dir': 'na borda direita', 'base': 'na base'}
# o lado da figura e o lado oposto, na frase do DA
LADO_NA_FRASE = {'esq': 'à esquerda', 'dir': 'à direita', 'topo': 'em cima', 'base': 'embaixo'}
OPOSTO = {'esq': 'dir', 'dir': 'esq', 'topo': 'base', 'base': 'topo'}


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


def _piso_com_folga(cf, e, regra=None):
    """A menor escala de e que continua no piso da 133 da regra verdadeira (ou de regra) depois que _elementos
    arredonda a caixa a nucleo.CASAS_PX casas: a folga cobre o erro do arredondamento sobre o lado que da a escala em
    _escalas (a largura; a altura quando a largura no KV e zero)."""
    r = cf['regras'][e['id']] if regra is None else regra
    piso = limites.valor('derivacao.escala_conteudo_min_da_regra')
    m = e['caixa']
    lado = (m[2] - m[0]) if m[2] > m[0] else (m[3] - m[1])
    px = piso * r * lado
    folga = FOLGA_RELATIVA
    if px > 0:
        folga = max(folga, ERRO_DO_ARREDONDAMENTO * 10.0 ** -mod_nucleo.CASAS_PX / px)
    return piso * r * (1.0 + folga)


def _porcento_da_regra(fr, piso):
    """A fracao da regra em porcentagem inteira, para a frase do DA: abaixo do piso, nunca o proprio piso (o
    arredondamento nao diz "50%, abaixo do minimo de 50%")."""
    pct = round(fr * 100)  # numero-neutro: porcentagem
    if fr < piso:
        pct = min(pct, math.ceil(piso * 100) - 1)  # numero-neutro: porcentagem, um ponto abaixo do piso
    return pct


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
    # o conteudo pequeno no meio do KV nao e margem: sem o teto, o quadro do formato encolhe ate o tamanho dele
    margem_max = limites.valor('derivacao.galeria_margem_max_lado_curto')
    return {'atomos': atomos, 'colados': colados, 'estrutura': estrutura, 'vao': vao,
            'bbox': _uniao([a['caixa'] for a in atomos]) if atomos else [0.0, 0.0, Wm, Hm],
            'margem_rel': min(max(margem_min, margem / curto), max(margem_min, margem_max)), 'Wm': Wm, 'Hm': Hm}


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


# ------------------------------------------------------------------ a figura, a faixa de borda e a lista
def _area(c):
    return max(0.0, c[2] - c[0]) * max(0.0, c[3] - c[1])


def _inter(a, b):
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def figura(kv):
    """O sujeito recortado que vira banda: funcao sujeito, fora do fluxo (sangra em algum lado, mas nao em todos) e com
    ao menos derivacao.galeria_figura_area_min do canvas. O maior; None sem nenhum."""
    A = float(kv['largura']) * float(kv['altura'])
    minimo = limites.valor('derivacao.galeria_figura_area_min')
    melhor = None
    for e in kv['elementos']:
        sg = e['sangra']
        if e['funcao'] != 'sujeito' or all(sg.values()) or em_fluxo(e):
            continue
        a = _area(e['caixa'])
        if a >= minimo * A and (melhor is None or a > melhor[0]):
            melhor = (a, e)
    return melhor[1] if melhor else None


def faixas_de_borda(an):
    """[(indice do atomo, 'topo' | 'base')] do atomo que abre ou fecha a leitura colado a essa borda do KV, fino e
    largo (derivacao.galeria_faixa_distancia_max, _espessura_max e _largura_min, em fracao do KV)."""
    at, Wm, Hm = an['atomos'], an['Wm'], an['Hm']
    saida = []
    if len(at) < 3:  # numero-neutro: com menos de tres atomos, a faixa e o proprio conteudo
        return saida
    dist_max = limites.valor('derivacao.galeria_faixa_distancia_max')
    esp_max = limites.valor('derivacao.galeria_faixa_espessura_max')
    larg_min = limites.valor('derivacao.galeria_faixa_largura_min')
    for i, lado in ((0, 'topo'), (len(at) - 1, 'base')):
        c = at[i]['caixa']
        dist = c[1] / Hm if lado == 'topo' else (Hm - c[3]) / Hm
        if dist <= dist_max and (c[3] - c[1]) / Hm <= esp_max and (c[2] - c[0]) / Wm >= larg_min:
            saida.append((i, lado))
    return saida


def series(an):
    """Listas de indices de atomos consecutivos iguais: um elemento so cada, mesma funcao, largura e altura a menos de
    derivacao.galeria_serie_tolerancia da maior."""
    at = an['atomos']
    tol = limites.valor('derivacao.galeria_serie_tolerancia')
    saida, atual = [], []

    def igual(a, b):
        if len(a['els']) != 1 or len(b['els']) != 1 or a['els'][0]['funcao'] != b['els'][0]['funcao']:
            return False
        ca, cb = a['caixa'], b['caixa']
        for k0, k1 in ((0, 2), (1, 3)):
            la, lb = ca[k1] - ca[k0], cb[k1] - cb[k0]
            if abs(la - lb) > tol * max(la, lb):
                return False
        return True
    for i in range(len(at)):
        if atual and igual(at[atual[-1]], at[i]):
            atual.append(i)
            continue
        if len(atual) >= 2:  # numero-neutro: uma serie tem ao menos dois itens
            saida.append(atual)
        atual = [i]
    if len(atual) >= 2:  # numero-neutro: idem
        saida.append(atual)
    return saida


def _peso(atomo, g, rel=1.0):
    """O peso do atomo no fluxo quando o conteudo cresce g vezes sobre a regra: rel (a regra verdadeira do atomo sobre
    a regra de referencia, regras_relativas: cada bloco cresce sobre a regra dele, e o legal de regra constante nao
    cresce com o titulo) vezes o peso da hierarquia (g > 1): g^(expoente - 1), com o titulo ate
    derivacao.galeria_titulo_sobre_outros_max dos outros textos, sem nenhum passar do teto sobre a regra."""
    if g <= 1.0:
        return rel
    fs = {e['funcao'] for e in atomo['els']}
    teto = limites.valor('derivacao.galeria_teto_sobre_regra') / g
    if 'titulo' in fs:
        return rel * min(g ** (limites.valor('derivacao.galeria_expoente_titulo') - 1.0),
                         limites.valor('derivacao.galeria_titulo_sobre_outros_max'), teto)
    if fs and fs <= set(FUNCOES_SECUNDARIAS):
        return rel * min(g ** (limites.valor('derivacao.galeria_expoente_secundario') - 1.0), teto)
    return rel * min(1.0, teto)


def regras_relativas(an, regras, regra_ref):
    """A regra verdadeira de cada atomo (a maior dos elementos de conteudo dele; a de referencia sem nenhuma) sobre a
    regra de referencia do formato: o fluxo poe uma escala so, e sem isso o bloco de regra menor que a de referencia
    (o legal de regra constante) crescia muitas vezes a regra dele e prendia o titulo."""
    saida = []
    for a in an['atomos']:
        rs = [regras[el['id']] for el in a['els'] if mod_solver.conteudo(el) and regras.get(el['id'])]
        saida.append(max(rs) / regra_ref if rs and regra_ref else 1.0)
    return saida


def atomos_efetivos(an, idx, g, serie_girada):
    """Atomos (do conjunto idx, na ordem) com o tamanho efetivo: cada um com o peso da hierarquia (_peso) e, com
    serie_girada, cada serie de itens iguais vira um atomo so, com os itens no outro eixo. Cada atomo leva 'membros': a
    caixa de cada elemento em unidades do KV ja pesadas, relativa ao canto do atomo."""
    at, vao = an['atomos'], an['vao']
    rels = an.get('rel_regra') or [1.0] * len(at)
    sers = [s for s in series(an) if all(i in idx for i in s)] if serie_girada else []
    em_serie = {i: s for s in sers for i in s}
    saida, feitos = [], set()
    for i in idx:
        if i in feitos:
            continue
        grupo = em_serie.get(i, [i])
        feitos.update(grupo)
        membros = {}
        peso = _peso(at[i], g, rels[i])
        if len(grupo) == 1:
            c = at[i]['caixa']
            for el in at[i]['els']:
                m = el['caixa']
                membros[el['id']] = [(m[0] - c[0]) * peso, (m[1] - c[1]) * peso, (m[2] - c[0]) * peso,
                                     (m[3] - c[1]) * peso]
            w, h = (c[2] - c[0]) * peso, (c[3] - c[1]) * peso
            caixa_kv = c
        else:
            caixa_kv = _uniao([at[j]['caixa'] for j in grupo])
            empilhada = (caixa_kv[3] - caixa_kv[1]) >= (caixa_kv[2] - caixa_kv[0])
            pos, maior = 0.0, 0.0
            for j in grupo:
                c = at[j]['caixa']
                cw, ch = (c[2] - c[0]) * peso, (c[3] - c[1]) * peso
                el = at[j]['els'][0]
                if empilhada:  # vira linha
                    membros[el['id']] = [pos, 0.0, pos + cw, ch]
                    maior = max(maior, ch)
                    pos += cw + vao * peso
                else:  # vira coluna
                    membros[el['id']] = [0.0, pos, cw, pos + ch]
                    maior = max(maior, cw)
                    pos += ch + vao * peso
            pos -= vao * peso
            w, h = (pos, maior) if empilhada else (maior, pos)
            for k, b in membros.items():  # os itens centrados atraves do bloco
                if empilhada:
                    d = (h - (b[3] - b[1])) / 2.0  # numero-neutro: centro
                    membros[k] = [b[0], d, b[2], d + b[3] - b[1]]
                else:
                    d = (w - (b[2] - b[0])) / 2.0  # numero-neutro: centro
                    membros[k] = [d, b[1], d + b[2] - b[0], b[3]]
        cx, cy = (caixa_kv[0] + caixa_kv[2]) / 2.0, (caixa_kv[1] + caixa_kv[3]) / 2.0  # numero-neutro: centro
        a = {'els': [el for j in grupo for el in at[j]['els']],
             'caixa': [cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0],  # numero-neutro: centro
             'caixa_kv': caixa_kv, 'membros': membros, 'peso': peso, 'serie': len(grupo) > 1}
        if 'col_mestre' in at[grupo[0]]:
            a['col_mestre'] = at[grupo[0]]['col_mestre']
        saida.append(a)
    return saida


def _an_efetivo(an, atomos):
    bb = _uniao([a['caixa_kv'] for a in atomos]) if atomos else an['bbox']
    return dict(an, atomos=atomos, bbox=bb, rel_regra=None)  # o peso ja esta nos atomos efetivos


# ------------------------------------------------------------------ o piso da 135 dentro do fluxo
def vizinhos_135(cf, fundo=()):
    """[(id a, id b, distancia no KV)]: os pares que a conferencia da 135 mede (o vizinho de conteudo mais perto em
    cada eixo, na mestre do KV, sem o legal colado), como em _conferir. Guardado no contexto do formato. fundo: os ids
    da figura de fundo da versao (n 202), que nao e vizinha de ninguem (guardado a parte)."""
    if fundo:
        cache = cf.setdefault('_viz_sem', {})
        if tuple(fundo) not in cache:
            cache[tuple(fundo)] = _vizinhos(cf, set(fundo))
        return cache[tuple(fundo)]
    if '_viz' not in cf:
        cf['_viz'] = _vizinhos(cf, set())
    return cf['_viz']


def _vizinhos(cf, fundo):
    colados = {e['id'] for e, _l in cf['an']['colados']}
    cont = [e for e in cf['kv']['elementos'] if mod_solver.conteudo(e) and e['id'] not in colados and
            e['id'] not in fundo]
    saida = []
    for a in cont:
        ca = a['caixa']
        for (k0, k1), (o0, o1) in (((0, 2), (1, 3)), ((1, 3), (0, 2))):
            melhor = None
            for b in cont:
                cb = b['caixa']
                if b is a or _sobra(ca[o0], ca[o1], cb[o0], cb[o1]) <= 0:
                    continue
                gap = cb[k0] - ca[k1]
                if gap > 0 and (melhor is None or gap < melhor[0]):
                    melhor = (gap, b)
            if melhor is not None:
                saida.append((a['id'], melhor[1]['id'], melhor[0]))
    return saida


def _piso_135(cf):
    """O piso da 135 que o fluxo cumpre, com a folga derivacao.galeria_folga_135 sobre o da conferencia."""
    return limites.valor('derivacao.distancia_entre_linhas_min') * (1.0 + limites.valor('derivacao.galeria_folga_135'))


def _precisa(cf, at):
    """Matriz do vao minimo (em unidades efetivas, a multiplicar pela escala do fluxo) entre o fim do atomo i e o
    comeco do atomo j ao longo de uma trilha, para o par vizinho no KV nao ficar abaixo do piso da 135."""
    piso_d = _piso_135(cf)
    onde = {}
    for k, a in enumerate(at):
        for el in a['els']:
            onde[el['id']] = k
    n = len(at)
    m = [[0.0] * n for _ in range(n)]
    for ia, ib, gap in vizinhos_135(cf):
        if ia not in onde or ib not in onde or onde[ia] == onde[ib]:
            continue
        i, j = onde[ia], onde[ib]
        v = piso_d * gap * (at[i]['peso'] + at[j]['peso']) / 2.0  # numero-neutro: media das duas escalas
        m[i][j] = max(m[i][j], v)
        m[j][i] = max(m[j][i], v)
    return m


def _offsets(dims, kc, prec, vao, seq):
    """Inicio de cada atomo de seq ao longo da trilha (unidades efetivas), com o vao vao e o vao minimo da 135 (prec,
    ou nenhum) entre qualquer par da trilha. Devolve (inicios, comprimento)."""
    offs, fim = [], 0.0
    for p, k in enumerate(seq):
        ini = 0.0
        if p:
            ini = offs[-1] + dims[seq[p - 1]][kc] + vao
            if prec is not None:
                for q, m in enumerate(seq[:p]):
                    ini = max(ini, offs[q] + dims[m][kc] + prec[m][k])
        offs.append(ini)
        fim = max(fim, ini + dims[k][kc])
    return offs, fim


def _trilhas(prec, part, esp, vao):
    """(inicio de cada trilha, espessura total) atraves das trilhas, em unidades efetivas: o vao entre trilhas e o
    vao minimo da 135 entre blocos de trilhas diferentes."""
    n = len(part)
    tp = None
    if prec is not None:
        tp = [[max([prec[i][j] for i in part[a] for j in part[b]] or [0.0]) for b in range(n)] for a in range(n)]
    return _offsets([(e, e) for e in esp], 0, tp, vao, list(range(n)))


# ------------------------------------------------------------------ particoes
def particoes(n):
    """Toda divisao de n itens em ordem em trilhas contiguas."""
    for k in range(1, n + 1):
        for cortes in itertools.combinations(range(1, n), k - 1):
            b = (0,) + cortes + (n,)
            yield [list(range(b[i], b[i + 1])) for i in range(k)]


def _dims(an):
    return [(a['caixa'][2] - a['caixa'][0], a['caixa'][3] - a['caixa'][1]) for a in an['atomos']]


def _dist_estrutura(an, tipo, part):
    """Passos de distancia a estrutura da mestre: trilhas a mais ou a menos e a troca de colunas por linhas; as mesmas
    colunas da mestre ficam a zero."""
    tipo_m, k_m = an['estrutura']
    dist = abs(len(part) - k_m) + (0 if tipo == tipo_m else 1)
    if tipo_m == 'colunas' and k_m > 1 and tipo == 'colunas' and len(part) == k_m:
        if all(len({an['atomos'][i].get('col_mestre') for i in t}) == 1 for t in part):
            dist = 0
    return dist


def _comprimentos(dims, kc, prec, g):
    """{(i, j): comprimento da trilha com os atomos de i ate j - 1} (_offsets de cada trecho contiguo), num passe por
    inicio: o trecho de i ate j acrescenta o atomo j - 1 ao de i ate j - 1, com os mesmos inicios."""
    n = len(dims)
    compr = {}
    for i in range(n):
        offs, fim = [], 0.0
        for j in range(i, n):
            ini = 0.0
            if offs:
                ini = offs[-1] + dims[j - 1][kc] + g
                if prec is not None:
                    for q, m in enumerate(range(i, j)):
                        ini = max(ini, offs[q] + dims[m][kc] + prec[m][j])
            offs.append(ini)
            fim = max(fim, ini + dims[j][kc])
            compr[(i, j + 1)] = fim
    return compr


def avaliar_particao(an, quadro, s_cap, tipo, part, prec=None, compr=None):
    """(pontuacao, escala, escala que cabe, espessura de cada trilha). A pontuacao e a escala com uma penalidade pela
    distancia a estrutura da mestre (desempata para o que a mestre ja faz). prec: os vaos minimos da 135 (_precisa).
    compr: os comprimentos dos trechos contiguos ja medidos (_comprimentos) no eixo da trilha, quando houver."""
    dims, g = _dims(an), an['vao']
    FW, FH = quadro[2] - quadro[0], quadro[3] - quadro[1]
    ke, kc = (0, 1) if tipo == 'colunas' else (1, 0)
    esp = [max(dims[i][ke] for i in t) for t in part]
    comp = [compr[(t[0], t[-1] + 1)] if compr is not None else _offsets(dims, kc, prec, g, t)[1] for t in part]
    tot_e, tot_c = (FW, FH) if tipo == 'colunas' else (FH, FW)
    s_fit = min(tot_e / _trilhas(prec, part, esp, g)[1], tot_c / max(comp))
    s = min(s_fit, s_cap)
    dist = _dist_estrutura(an, tipo, part)
    return s * (1 - limites.valor('derivacao.galeria_penalidade_estrutura') * dist), s, s_fit, esp


def melhor_particao(an, quadro, s_cap, tipos=('colunas', 'linhas'), excluir=(), prec=None):
    """(pontuacao, escala, escala que cabe, tipo, particao, espessuras) de maior pontuacao, ou None. Percorre as
    particoes na ordem de particoes() e corta o ramo cuja cota de cima da pontuacao nao passa da melhor ate ali: devolve
    a mesma particao da busca em todas, com o mesmo desempate, sem o custo dobrar a cada atomo. A cota usa o vao
    simples, que nunca passa do vao com a 135 (prec)."""
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
        compr = _comprimentos(dims, kc, prec, g)
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
                    score, s, s_fit, esp = avaliar_particao(an, quadro, s_cap, tipo, part, prec, compr)
                    if melhor is None or score > melhor[0] + DESEMPATE:
                        melhor = (score, s, s_fit, tipo, part, esp)
                    return
                for fim in range(i + 1, n - (k - 1 - j) + 1):
                    e_t = max(esp_a[i:fim])
                    descer(fim, j + 1, cortes + [fim], soma_e + e_t, max(maior_c, compr[(i, fim)]))

            descer(0, 0, [], 0.0, 0.0)
    return melhor


def _mesma_geometria(a, b):
    """Uma trilha so de um tipo e a mesma coisa que cada atomo numa trilha do outro tipo."""
    la, lb = [len(t) for t in a[4]], [len(t) for t in b[4]]
    n = sum(la)
    return (la == [n] and lb == [1] * n) or (lb == [n] and la == [1] * n)


# ------------------------------------------------------------------ colocar
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


def _empilhar(offs, tam, alvo, lo, hi):
    """Inicio de cada item empilhado em ordem num eixo, com os inicios relativos offs (os vaos e a 135), dentro de
    [lo, hi], com o centro o mais perto possivel (minimos quadrados) do alvo."""
    q = _isotonica([a - t / 2.0 - o for a, t, o in zip(alvo, tam, offs)])  # numero-neutro: centro do item
    topo = max(hi - offs[-1] - tam[-1], lo)
    return [min(max(x, lo), topo) + o for x, o in zip(q, offs)]


def _cruz(c0, c1, b0, b1, trilha, a):
    """Deslocamento do atomo atraves da trilha: o centro dele fica no lugar relativo que tinha na caixa do conteudo."""
    cr = ((c0 + c1) / 2.0 - b0) / (b1 - b0) if b1 > b0 else 0.5  # numero-neutro: centro
    return min(max(cr * trilha - a / 2.0, 0.0), max(trilha - a, 0.0))  # numero-neutro: centro


def _inicio_cruz(u0, b0, b1, trilha, a):
    """Deslocamento do atomo atraves da trilha quando ele comeca onde a uniao do grupo dele comecava na caixa do
    conteudo (_lado_a_lado)."""
    cr = (u0 - b0) / (b1 - b0) if b1 > b0 else 0.0
    return min(max(cr * trilha, 0.0), max(trilha - a, 0.0))


def _lado_a_lado(at, seq, k0):
    """{indice do atomo: caixa no KV do grupo dele, ou None quando ele esta sozinho} dos atomos da trilha seq: os itens
    da mesma funcao que ficavam lado a lado no KV (a fileira de icones, a grade de informacoes: sobrepostos ao longo
    da trilha, eixo k0) e agora vao um depois do outro formam um grupo, e todos comecam onde a uniao deles comecava,
    alinhados atraves da trilha. Sem isso, cada um guardava o lugar que tinha na fileira e a fileira virava escada. Os
    blocos de funcoes diferentes guardam o lugar de cada um, como antes."""
    pai = {i: i for i in seq}

    def raiz(k):
        while pai[k] != k:
            k = pai[k]
        return k
    for i, j in itertools.combinations(seq, 2):
        a, b = at[i]['caixa_kv'], at[j]['caixa_kv']
        mesma = {el['funcao'] for el in at[i]['els']} == {el['funcao'] for el in at[j]['els']}
        if mesma and _sobra(a[k0], a[k0 + 2], b[k0], b[k0 + 2]) > 0:
            pai[raiz(j)] = raiz(i)
    grupos = {}
    for i in seq:
        grupos.setdefault(raiz(i), []).append(i)
    return {i: _uniao([at[j]['caixa_kv'] for j in grupos[raiz(i)]]) if len(grupos[raiz(i)]) > 1 else None for i in seq}


def colocar(an2, prec, quadro, s, tipo, part, esp, espelhar, distrib):
    """Caixas dos elementos dos atomos efetivos para (tipo, particao) na escala s. espelhar: inverte ao longo do lado
    maior do quadro (a ordem das trilhas, quando elas correm nele; a ordem dentro de cada trilha, senao). distrib:
    'espalhada' (as trilhas com o mesmo espaco entre si e as bordas, quando esse espaco cumpre a 135; senao juntas pelo
    vao minimo, no centro), 'inicio' ou 'fim' (juntas contra aquele lado)."""
    at, g = an2['atomos'], an2['vao']
    fx0, fy0, fx1, fy1 = quadro
    FW, FH = fx1 - fx0, fy1 - fy0
    dims = _dims(an2)
    colunas = tipo == 'colunas'
    trilhas_no_longo = colunas == (_eixo_longo(FW, FH) == 'x')
    ordem_t = list(range(len(part)))
    inverte_dentro = espelhar and not trilhas_no_longo
    if espelhar and trilhas_no_longo:
        ordem_t = ordem_t[::-1]
    main0, main_tot = (fx0, FW) if colunas else (fy0, FH)
    esp_s = [v * s for v in esp]
    sobra = main_tot - sum(esp_s)
    offs, tot_t = _trilhas(prec, [part[k] for k in ordem_t], [esp[k] for k in ordem_t], g)
    offs = [o * s for o in offs]
    tot_t *= s
    esp_o = [esp_s[k] for k in ordem_t]
    if distrib == 'espalhada':
        passo = sobra / (len(part) + 1) if len(part) > 1 else sobra / 2.0  # numero-neutro: centro
        iguais, p0 = [], main0 + passo
        for e_ in esp_o:
            iguais.append(p0)
            p0 += e_ + passo
        if all(iguais[k] - iguais[0] >= offs[k] - FOLGA_COTA for k in range(len(iguais))):
            inicio = {k: iguais[n_] for n_, k in enumerate(ordem_t)}
        else:
            base = main0 + max(0.0, (main_tot - tot_t) / 2.0)  # numero-neutro: centro
            inicio = {k: base + offs[n_] for n_, k in enumerate(ordem_t)}
    else:
        base = main0 if distrib == 'inicio' else main0 + main_tot - tot_t
        inicio = {k: base + offs[n_] for n_, k in enumerate(ordem_t)}
    un = len(part) > 1 or distrib != 'espalhada'
    bb = an2['bbox']
    lo_c, hi_c = (fy0, fy1) if colunas else (fx0, fx1)
    Dm = an2['Hm'] if colunas else an2['Wm']
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
        offs_t = [o * s for o in _offsets(dims, k0, prec, g, seq)[0]]
        grupo = _lado_a_lado(at, seq, k0)
        for i, ini in zip(seq, _empilhar(offs_t, larg, alvo, lo_c, hi_c)):
            c, u = at[i]['caixa'], grupo[i]
            aw, ah = dims[i][0] * s, dims[i][1] * s
            if colunas:
                trilha = esp_s[k] if un else FW
                x = (inicio[k] if un else fx0) + (_cruz(c[0], c[2], bb[0], bb[2], trilha, aw) if u is None else
                                                  _inicio_cruz(u[0], bb[0], bb[2], trilha, aw))
                y = ini
            else:
                trilha = esp_s[k] if un else FH
                y = (inicio[k] if un else fy0) + (_cruz(c[1], c[3], bb[1], bb[3], trilha, ah) if u is None else
                                                  _inicio_cruz(u[1], bb[1], bb[3], trilha, ah))
                x = ini
            for eid, m in at[i]['membros'].items():
                caixas[eid] = [x + s * m[0], y + s * m[1], x + s * m[2], y + s * m[3]]
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


def _fundo_da_figura(e, bm, bf, W, H):
    """(caixa, lados que sangram) da figura de fundo (figura_de_fundo; decisoes-v1.md, n 202): a escala da regra e a
    posicao de _fundo, sem passar da borda que nao sangra quando cabe. No eixo em que a figura e maior que o formato,
    ela fica centrada pelo centro dela e sangra dos dois lados desse eixo: o corte dela nunca fica a vista nem fora do
    quadro. O lado que ela passa a cruzar para continuar presa a borda que sangra tambem passa a sangrar."""
    c = _fundo(e, bm, bf, W, H)
    sg = dict(e['sangra'])
    for (k0, k1), D, ini, fim in (((0, 2), W, 'esq', 'dir'), ((1, 3), H, 'topo', 'base')):
        t = c[k1] - c[k0]
        if t > D:
            o = (D - t) / 2.0  # numero-neutro: centro
            sg[ini] = sg[fim] = True
        else:
            o = c[k0]
            if not sg[ini] and not sg[fim]:
                o = min(max(o, 0.0), D - t)
            elif not sg[ini] and o < 0.0:
                sg[ini] = True
            elif not sg[fim] and o + t > D:
                sg[fim] = True
        c[k0], c[k1] = o, o + t
    return c, sg


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
    """A arte cobrindo a faixa livre, presa a borda de dentro (a que encosta no conteudo) e centrada atraves; sangra
    no lado de fora e nos dois lados atraves (o lado de dentro fica no canvas). Quando a arte precisa passar do
    comprimento da faixa para cobrir atraves, o que sobra sai pelo lado de fora da peca, nunca por baixo do conteudo."""
    c = e['caixa']
    w0, h0 = c[2] - c[0], c[3] - c[1]
    b0, b1, lado = banda
    if longo == 'x':
        s = max((b1 - b0) / w0, H / h0)
        w, h = w0 * s, h0 * s
        x0, y0 = (b0 if lado == 'fim' else b1 - w), (H - h) / 2.0  # numero-neutro: centro
        sg = {'esq': lado == 'inicio', 'dir': lado == 'fim', 'topo': True, 'base': True}
    else:
        s = max((b1 - b0) / h0, W / w0)
        w, h = w0 * s, h0 * s
        x0, y0 = (W - w) / 2.0, (b0 if lado == 'fim' else b1 - h)  # numero-neutro: centro
        sg = {'esq': True, 'dir': True, 'topo': lado == 'inicio', 'base': lado == 'fim'}
    return [x0, y0, x0 + w, y0 + h], sg


# ------------------------------------------------------------------ contexto do formato
def _contexto(ctx, kv, formato, specs=None, arquivo_specs=None, params=None):
    """O que a galeria precisa de um formato: composicao, areas da folha, base do calculo, regra de cada elemento,
    escala de referencia do conteudo, os blocos da mestre, a figura e as faixas de borda."""
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
    an['rel_regra'] = regras_relativas(an, regras, statistics.median(rc) if rc else 1.0)
    base_q = (areas.get('area_segura') or areas.get('area_util') or {}).get('caixa') or [0.0, 0.0, W, H]
    ins = an['margem_rel'] * min(W, H)
    quadro = [max(base_q[0], ins), max(base_q[1], ins), min(base_q[2], W - ins), min(base_q[3], H - ins)]
    # o formato na familia do KV (na faixa, ou na mesma proporcao, como derivacao.nucleo decide): o layout dele copia o
    # do KV, e as relacoes de fundo do KV valem nele (_relacoes_de_fundo). Na troca de orientacao e fora da faixa, a
    # galeria reorganiza o conteudo sobre a cena de proposito (a imagem livre), e as relacoes do KV nao se aplicam
    fam = mod_formatos.familia(bm, bf, params['faixa']['valor'])
    copia = fam['na_faixa'] or abs(bm[1] * W / bm[0] - H) <= limites.valor('derivacao.mesma_proporcao_px')
    return {'ctx': ctx, 'kv': kv, 'formato': formato, 'W': W, 'H': H, 'areas': areas, 'bf': bf, 'bm': bm,
            'regras': regras, 'regra_ref': statistics.median(rc) if rc else 1.0, 'an': an, 'quadro': quadro,
            'copia_do_kv': bool(copia), '_figura': figura(kv), '_faixas': faixas_de_borda(an)}


# ------------------------------------------------------------------ uma candidata
def _particao(cf, an_base, idx, q, cap, modo, serie_girada, forcada):
    """(an efetivo, escolha, vaos da 135) com a hierarquia resolvida por ponto fixo (a escala do fluxo decide o peso).
    Guardada no contexto do formato pelo tamanho da area (a particao so depende dos lados dela, nunca da posicao): a
    versao espelhada e a banda do outro lado usam a mesma particao."""
    cache = cf.setdefault('_particoes', {})
    lados = (round(q[2] - q[0], 6), round(q[3] - q[1], 6))  # numero-neutro: casas da chave
    chave = (lados, tuple(idx), cap, modo, serie_girada, forcada)
    if chave not in cache:
        cache[chave] = _particao_calc(cf, an_base, idx, q, cap, modo, serie_girada, forcada)
    return cache[chave]


def _particao_calc(cf, an_base, idx, q, cap, modo, serie_girada, forcada):
    r = cf['regra_ref']
    g, escolha, an2, prec = 1.0, None, None, None
    for _volta in range(VOLTAS_HIERARQUIA):
        an2 = _an_efetivo(an_base, atomos_efetivos(an_base, idx, g, serie_girada))
        prec = _precisa(cf, an2['atomos'])
        if forcada is not None:
            tipo, tamanhos = forcada
            if sum(tamanhos) != len(an2['atomos']):
                return an2, None, prec
            cortes = list(itertools.accumulate(tamanhos))
            part = [list(range(a, b)) for a, b in zip([0] + cortes[:-1], cortes)]
            score, s, s_fit, esp = avaliar_particao(an2, q, cap, tipo, part, prec)
            escolha = (score, s, s_fit, tipo, part, esp)
        else:
            melhor = melhor_particao(an2, q, cap, prec=prec)
            if melhor is None:
                return an2, None, prec
            escolha = melhor
            if modo != 'melhor':
                outro = 'linhas' if melhor[3] == 'colunas' else 'colunas'
                escolha = melhor_particao(an2, q, cap, tipos=(outro,), prec=prec)
                if escolha is not None and _mesma_geometria(melhor, escolha):
                    escolha = melhor_particao(an2, q, cap, tipos=(outro,), prec=prec,
                                              excluir={(outro, tuple(len(t) for t in escolha[4]))})
                    if escolha is not None and _mesma_geometria(melhor, escolha):
                        escolha = None
                if escolha is None:
                    return an2, None, prec
        g_novo = max(escolha[1] / r, 1.0) if r else 1.0
        if abs(g_novo - g) < FOLGA_PONTO_FIXO * g:
            break
        g = g_novo
    return an2, escolha, prec


def _faixa_de_borda(cf, an, i, lado, x0, x1, y_ref):
    """Caixas dos elementos da faixa de borda presa a borda (lado), na largura [x0, x1]: escala para a largura, com o
    teto sobre a regra; com dois ou mais elementos, o primeiro vai ao inicio e o ultimo ao fim. Devolve (caixas,
    espessura, escala); (None, 0, escala) quando a faixa so cabe abaixo do piso da 133 nesta largura."""
    a = an['atomos'][i]
    c = a['caixa']
    w0, h0 = c[2] - c[0], c[3] - c[1]
    s = min(limites.valor('derivacao.galeria_teto_sobre_regra') * cf['regra_ref'], (x1 - x0) / w0)
    if s < max(_piso_com_folga(cf, el, cf['regras'][el['id']] or cf['regra_ref']) for el in a['els']):
        return None, 0.0, s
    h = h0 * s
    y0 = y_ref if lado == 'topo' else y_ref - h
    caixas = {}
    els = sorted(a['els'], key=lambda e: e['caixa'][0])
    for k, el in enumerate(els):
        m = el['caixa']
        w = (m[2] - m[0]) * s
        if len(els) > 1 and k == len(els) - 1:
            ex = x1 - w
        elif len(els) > 1 and k == 0:
            ex = x0
        else:
            ex = x0 + (m[0] - c[0]) * s
        caixas[el['id']] = [ex, y0 + (m[1] - c[1]) * s, ex + w, y0 + (m[3] - c[1]) * s]
    return caixas, h, s


def _figura_na_banda(cf, e, eixo, lado, lim, fator):
    """Caixa da figura na banda: presa a borda que ela toca no KV, na altura cheia do espaco lim = [x0, y0, x1, y1] (ou
    na largura cheia, na banda de cima ou de baixo), sem passar de derivacao.galeria_figura_banda_max do lado em que a
    banda corre nem do teto sobre a regra dela. fator: quanto a figura ja cedeu ao conteudo (de 1 ate
    derivacao.galeria_figura_reducao_min); nunca abaixo do piso da 133. O lado que sangra passa da borda por
    derivacao.galeria_sujeito_sangria_extra do lado curto; a figura que sangra nos dois lados atraves da banda (em
    cima e embaixo, na banda de lado) cresce ate passar das duas bordas, como o fundo, para o corte nao ficar a vista.
    None na banda do lado oposto a um lado que sangra: o corte dele ficaria no meio da peca."""
    W, H = cf['W'], cf['H']
    c, a = e['caixa'], e.get('caixa_asset') or e['caixa']
    w0, h0 = c[2] - c[0], c[3] - c[1]
    sg = e['sangra']
    if sg[OPOSTO[lado]]:
        return None
    regra = cf['regras'][e['id']] or cf['regra_ref']
    banda_max = limites.valor('derivacao.galeria_figura_banda_max')
    teto = limites.valor('derivacao.galeria_figura_teto_sobre_regra') * regra
    extra = limites.valor('derivacao.galeria_sujeito_sangria_extra') * min(W, H)
    if eixo == 'x':
        s = min((lim[3] - lim[1]) / h0, banda_max * W / w0, teto)
    else:
        s = min((lim[2] - lim[0]) / w0, banda_max * H / h0, teto)
    s = max(s * fator, _piso_com_folga(cf, e, regra))
    # os dois lados atraves sangram: o asset passa das duas bordas (o teto e a banda maxima cedem; o corte a vista e
    # pior)
    cheia_x = eixo == 'x' and sg['topo'] and sg['base']
    cheia_y = eixo == 'y' and sg['esq'] and sg['dir']
    if cheia_x:
        s = max(s, (H + 2.0 * extra) / (a[3] - a[1]))  # numero-neutro: as duas bordas
    if cheia_y:
        s = max(s, (W + 2.0 * extra) / (a[2] - a[0]))  # numero-neutro: as duas bordas
    w, h = w0 * s, h0 * s
    dl, dt, dr, db = (a[0] - c[0]) * s, (a[1] - c[1]) * s, (a[2] - c[2]) * s, (a[3] - c[3]) * s
    Wm, Hm = cf['bm']
    if eixo == 'x':
        # atraves da banda: presa a borda que toca (sangra); senao, a distancia do KV a borda do lado dela
        x0 = (-dl - extra if sg['esq'] else min(c[0] * s, lim[0])) if lado == 'esq' else \
            (W - w - dr + extra if sg['dir'] else W - w - min((Wm - c[2]) * s, W - lim[2]))
        if cheia_x:
            y0 = (H - (a[3] - a[1]) * s) / 2.0 - dt  # numero-neutro: o asset centrado, passando das duas bordas
        elif sg['base']:
            y0 = max(H - h - db + extra, lim[1])
        elif sg['topo']:
            y0 = min(-dt - extra, lim[3] - h)
        else:
            y0 = (lim[1] + lim[3] - h) / 2.0  # numero-neutro: centro
    else:
        y0 = (-dt - extra if sg['topo'] else min(c[1] * s, lim[1])) if lado == 'topo' else \
            (H - h - db + extra if sg['base'] else H - h - min((Hm - c[3]) * s, H - lim[3]))
        cx = (c[0] + c[2]) / 2.0 / Wm  # numero-neutro: centro
        if cheia_y:
            x0 = (W - (a[2] - a[0]) * s) / 2.0 - dl  # numero-neutro: o asset centrado, passando das duas bordas
        elif sg['esq']:
            x0 = -dl - extra
        elif sg['dir']:
            x0 = W - w - dr + extra
        else:
            x0 = min(max(cx * W - w / 2.0, lim[0]), lim[2] - w)  # numero-neutro: centro
    return [x0, y0, x0 + w, y0 + h]


def _escala_colado(cf, e, s):
    """A escala do legal colado a borda: a do fluxo, sem ficar abaixo do piso da 133 da regra dele (o legal de regra
    constante nao encolhe com o conteudo)."""
    r = cf['regras'][e['id']]
    return max(s, _piso_com_folga(cf, e)) if r else s


def _reservar(cf, regiao, s):
    """A regiao do fluxo sem a faixa de cada legal colado, na escala s. O legal fica do lado do conteudo: na regiao
    que sobra depois da figura e da imagem livre (com a figura ao lado, ele corre so na largura do conteudo; com a
    figura na mesma borda, ele fica entre o conteudo e ela)."""
    an = cf['an']
    ins = an['margem_rel'] * min(cf['W'], cf['H'])
    q = list(regiao)
    for e, lado in an['colados']:
        c = e['caixa']
        sc = _escala_colado(cf, e, s)
        # o vao ate o fluxo: o vao tipico do KV na escala do fluxo, sem passar da margem (o legal colado fica fora da
        # 135, decisoes-v1.md, 165)
        t = ((c[2] - c[0]) if lado in ('esq', 'dir') else (c[3] - c[1])) * sc + min(an['vao'] * s, ins)
        if lado == 'esq':
            q[0] = max(q[0], regiao[0] + t)
        elif lado == 'dir':
            q[2] = min(q[2], regiao[2] - t)
        elif lado == 'topo':
            q[1] = max(q[1], regiao[1] + t)
        else:
            q[3] = min(q[3], regiao[3] - t)
    return q


def _vao_135(cf, colocados, s_a, s_b, minimo):
    """O vao entre um bloco ja colocado (colocados: {id: caixa}, na escala s_a) e o fluxo (escala ate s_b) para os
    pares vizinhos no KV nao ficarem abaixo do piso da 135; nunca abaixo de minimo (a margem)."""
    piso_d = _piso_135(cf)
    v = minimo
    for ia, ib, gap in vizinhos_135(cf):
        if (ia in colocados) != (ib in colocados):
            v = max(v, piso_d * gap * (s_a + s_b) / 2.0)  # numero-neutro: media das duas escalas
    return v


def gerar(cf, p, forcada=None):
    """Uma candidata, antes do solver. p: {'fig': None | (eixo, lado), 'arte': None | 'inicio' | 'fim', 'faixa': None |
    'inteira' | 'conteudo', 'serie': bool, 'modo': 'melhor' | 'outra', 'espelhar': bool}. forcada: (tipo, tamanhos
    das trilhas) tirada de outro membro do grupo. Devolve a variante ou None quando a estrutura nao existe neste KV.
    Piso por bloco: quando o conteudo so caberia abaixo do piso da 133, a figura cede primeiro (encolhe por
    derivacao.galeria_figura_reducao_passo ate derivacao.galeria_figura_reducao_min); se ainda nao couber, o conteudo
    fica no piso e a conferencia diz o que nao fecha."""
    passo = limites.valor('derivacao.galeria_figura_reducao_passo')
    minimo = limites.valor('derivacao.galeria_figura_reducao_min')
    fator = 1.0
    while True:
        v = _gerar_135(cf, p, fator, forcada)
        if v is None or not v['abaixo_do_piso'] or p['fig'] is None or fator <= minimo * (1.0 + FOLGA_RELATIVA):
            return v
        fator = max(minimo, fator * passo)


def _gerar_135(cf, p, fator, forcada):
    """_gerar com o vao da 135 entre a figura (ou a faixa) e o fluxo: o vao depende da escala do fluxo (s_viz) e a
    escala do fluxo do vao (mais vao, menos espaco). Comeca na regra e refaz com a maior escala que o fluxo deu, para
    cima ou para baixo: a estimada acima da do fluxo deixava o vao largo demais e o conteudo preso no piso com espaco
    vazio. Devolve a ultima candidata cujo vao cumpre a escala que o fluxo deu (a estimada nao fica abaixo dela); para
    quando a estimada e a do fluxo se encontram ou quando o ponto fixo fica cercado pelos dois lados."""
    s_viz = cf['regra_ref']
    v, cumpre, abaixo = None, None, None
    for _volta in range(VOLTAS_135):
        v = _gerar(cf, p, s_viz, fator, forcada)
        if v is None:
            return cumpre
        esc = _escalas(cf['kv'], v['caixas'])
        maior = max([esc[e['id']] for e in cf['kv']['elementos'] if em_fluxo(e)] or [s_viz])
        if maior <= s_viz * (1.0 + FOLGA_PONTO_FIXO):
            cumpre = v
            if maior >= s_viz * (1.0 - FOLGA_PONTO_FIXO) or abaixo is not None:
                break
        else:
            abaixo = s_viz
        s_viz = maior
    return cumpre or v


def _gerar(cf, p, s_viz, fator, forcada):
    an, kv, W, H, quadro = cf['an'], cf['kv'], cf['W'], cf['H'], cf['quadro']
    r = cf['regra_ref']
    cap = limites.valor('derivacao.galeria_teto_sobre_regra') * r
    ins = an['margem_rel'] * min(W, H)
    longo = _eixo_longo(W, H)
    caixas, sangra = {}, {}
    q = list(quadro)
    idx = list(range(len(an['atomos'])))
    fx = cf['_figura']
    faixas = list(cf['_faixas']) if p['faixa'] else []
    for i, _lado in faixas:
        idx.remove(i)

    def faixas_em(x0, x1, lim):
        """Coloca as faixas presas a borda delas na largura [x0, x1] e devolve lim sem elas (ou None)."""
        lim = list(lim)
        for i, lf in faixas:
            cx_f, h_f, s_f = _faixa_de_borda(cf, an, i, lf, x0, x1, lim[1] if lf == 'topo' else lim[3])
            if cx_f is None:
                return None
            caixas.update(cx_f)
            vao_f = _vao_135(cf, cx_f, s_f, s_viz, ins)
            if lf == 'topo':
                lim[1] += h_f + vao_f
            else:
                lim[3] -= h_f + vao_f
        return lim
    # 1. a figura na banda (com a faixa de ponta a ponta antes dela)
    fig_caixa = None
    if p['fig'] is not None:
        eixo, lado = p['fig']
        lim = list(quadro)
        if p['faixa'] == 'inteira':
            lim = faixas_em(quadro[0], quadro[2], quadro)
            if lim is None:
                return None
            q = list(lim)
        lim_f = lim if eixo == 'y' else [lim[0], lim[1] if p['faixa'] == 'inteira' else quadro[1], lim[2], lim[3]]
        fig_caixa = _figura_na_banda(cf, fx, eixo, lado, lim_f, fator)
        if fig_caixa is None:
            return None
        caixas[fx['id']] = fig_caixa
        s_fig = (fig_caixa[2] - fig_caixa[0]) / (fx['caixa'][2] - fx['caixa'][0])
        vao_g = _vao_135(cf, {fx['id']: fig_caixa}, s_fig, s_viz, ins)
        if lado == 'esq':
            q[0] = max(q[0], fig_caixa[2] + vao_g)
        elif lado == 'dir':
            q[2] = min(q[2], fig_caixa[0] - vao_g)
        elif lado == 'topo':
            q[1] = max(q[1], fig_caixa[3] + vao_g)
        else:
            q[3] = min(q[3], fig_caixa[1] - vao_g)
        if q[2] - q[0] <= 0 or q[3] - q[1] <= 0:
            return None
    # 2. a faixa de borda so sobre o conteudo (ou de ponta a ponta, sem figura)
    if faixas and (p['faixa'] == 'conteudo' or p['fig'] is None):
        q = faixas_em(q[0], q[2], q)
        if q is None or q[2] - q[0] <= 0 or q[3] - q[1] <= 0:
            return None
    # 3. a imagem livre (a arte que sangra em parte, ou a cena) num lado do lado maior
    banda = None
    if p['arte'] is not None:
        k0, k1 = (0, 2) if longo == 'x' else (1, 3)
        L, D = q[k1] - q[k0], (W if longo == 'x' else H)
        fr = limites.valor('derivacao.galeria_conteudo_fracao')
        if p['arte'] == 'fim':
            q[k1] = q[k0] + fr * L
            banda = (q[k1], D, 'fim')
        else:
            q[k0] = q[k1] - fr * L
            banda = (0.0, q[k0], 'inicio')
    # 4. o fluxo, com a reserva do legal colado do lado do conteudo
    regiao = list(q)
    s_prov, escolha, an2, prec = r, None, _an_efetivo(an, []), None
    for _volta in range(2):  # numero-neutro: reserva o legal com a escala provisoria e refaz uma vez com a do fluxo
        q = _reservar(cf, regiao, s_prov)
        if q[2] - q[0] <= 0 or q[3] - q[1] <= 0:
            return None
        if not idx:
            escolha = (s_prov, s_prov, s_prov, None, [], [])
            break
        an2, escolha, prec = _particao(cf, an, idx, q, cap, p['modo'], p['serie'], forcada)
        if escolha is None:
            return None
        if abs(escolha[1] - s_prov) < MESMA_ESCALA:
            break
        s_prov = escolha[1]
    _score, s, s_fit, tipo, part, esp = escolha
    # piso por bloco: nenhum bloco de conteudo do fluxo abaixo do piso da 133 da regra verdadeira dele (com a folga do
    # arredondamento das caixas)
    s_min = 0.0
    for a in an2['atomos']:
        for el in a['els']:
            if cf['regras'][el['id']] and mod_solver.conteudo(el):
                s_min = max(s_min, _piso_com_folga(cf, el) / a['peso'])
    abaixo = bool(part) and s < s_min
    if part:
        s = max(s, s_min)
    distrib = 'espalhada'
    if banda is not None and (tipo == 'colunas') == (longo == 'x'):
        # as trilhas correm no lado maior: juntas do lado do conteudo, longe da imagem
        distrib = 'inicio' if p['arte'] == 'fim' else 'fim'
    if part:
        caixas.update(colocar(an2, prec, q, s, tipo, part, esp, p['espelhar'], distrib))
    bm = cf['bm']
    for e, lado in an['colados']:
        c = e['caixa']
        sc = _escala_colado(cf, e, s)
        w, h = (c[2] - c[0]) * sc, (c[3] - c[1]) * sc
        cx, cy = (c[0] + c[2]) / 2.0 / bm[0] * W, (c[1] + c[3]) / 2.0 / bm[1] * H  # numero-neutro: centro
        if lado in ('esq', 'dir'):
            x0 = regiao[0] if lado == 'esq' else regiao[2] - w
            y0 = max(min(max(cy - h / 2.0, regiao[1]), regiao[3] - h), quadro[1])  # numero-neutro: centro
        else:
            y0 = regiao[1] if lado == 'topo' else regiao[3] - h
            x0 = max(min(max(cx - w / 2.0, regiao[0]), regiao[2] - w), quadro[0])  # numero-neutro: centro
        caixas[e['id']] = [x0, y0, x0 + w, y0 + h]
    arte = arte_parcial(kv) if banda is not None else None
    de_fundo = figura_de_fundo(cf, p)
    for e in kv['elementos']:
        if e['id'] in caixas:
            continue
        if arte is not None and e['id'] == arte['id']:
            caixas[e['id']], sangra[e['id']] = _arte_em_banda(e, banda, longo, W, H)
        elif e['id'] == de_fundo:
            caixas[e['id']], sg = _fundo_da_figura(e, bm, cf['bf'], W, H)
            if sg != e['sangra']:
                sangra[e['id']] = sg
        else:
            caixas[e['id']] = _fundo(e, bm, cf['bf'], W, H)
    return {'id': None, 'p': p, 'caixas': caixas, 'sangra': sangra, 'falha_solver': None, 'arte': arte,
            'tipo': tipo, 'part': part, 'an2': an2, 'espelhar': p['espelhar'], 'lado_img': p['arte'], 's': s,
            's_fit': s_fit, 'eixo_quadro': _eixo_longo(q[2] - q[0], q[3] - q[1]), 'q': q, 'fig_caixa': fig_caixa,
            'faixas': faixas, 'abaixo_do_piso': abaixo}


def _resolver(cf, caixas, sangra, fundo=()):
    """O fluxo vai ao solver do repositorio como mestre sintetica do tamanho do formato: as caixas do fluxo sao a
    mestre. A regra de cada bloco do fluxo (e da figura) e a escala que o fluxo deu: o solver so resolve o que o fluxo
    deixou em conflito (sobreposicao, margem, area). Sem isso, a regra fraca puxaria de volta a regra o que nenhuma
    relacao forte prende, e o piso forte da regra empurraria para cima o texto que o fluxo deixou abaixo dela. O resto
    leva a regra verdadeira dividida pela escala do fluxo. O piso obrigatorio da 133 continua contra a regra verdadeira
    (o maior entre ele e o da regra do fluxo): o solver nunca leva um bloco abaixo dele; quando o conteudo nao cabe
    sem isso, o solver nao fecha e a conferencia diz o que falha. So a variante da galeria passa por aqui: depois de
    uma edicao do DA no palco, nada refaz o encaixe (o que o DA nao mexeu fica parado, 0.9.5). fundo: os ids da figura
    de fundo da versao (figura_de_fundo, n 202): o conteudo pode ficar sobre ela, e o piso dela continua. Devolve
    (caixas, nome da obrigatoria que nao fecha ou None); sem fechar, ficam as caixas do fluxo."""
    W, H, kv = cf['W'], cf['H'], cf['kv']
    fx_id = (cf.get('_figura') or {}).get('id')
    piso = limites.valor('derivacao.escala_conteudo_min_da_regra')
    sint, regras, pisos = [], [], []
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
        if r and k and (em_fluxo(e) or e['id'] == fx_id):
            regras.append(1.0)  # a escala do fluxo sobre a mestre sintetica, que ja esta nessa escala
            # o piso da regra verdadeira com a folga do arredondamento das caixas (o solver deixa o bloco no piso)
            pisos.append(max(piso, _piso_com_folga(cf, e) / k))
        else:
            regras.append((r / k) if r and k else r)
            pisos.append(None)
    try:
        resolvidas, _esc, _r = mod_solver.resolver(sint, (W, H), (W, H), cf['areas'], regras, pisos, fundo=fundo)
    except mod_solver.NaoFecha as ex:
        return caixas, ex.restricao['nome']
    return {e['id']: c for e, c in zip(kv['elementos'], resolvidas)}, None


# ------------------------------------------------------------------ a nota
def ordem_invertida(cf, caixas, fundo=()):
    """Fracao dos pares (conteudo do fluxo, objeto solto e figura) que tinham uma ordem clara no KV num eixo (um
    inteiro antes do outro) e que, no formato, aparecem na ordem contraria naquele eixo (pelo centro, com a folga de
    derivacao.galeria_ordem_tolerancia do lado do formato). A figura de fundo (fundo, n 202) fica de fora: ela esta
    atras do conteudo, nunca antes ou depois dele."""
    fx = cf['_figura']
    tol = limites.valor('derivacao.galeria_ordem_tolerancia')
    els = [e for e in cf['kv']['elementos'] if e['id'] not in fundo and
           (em_fluxo(e) or (fx is not None and e['id'] == fx['id']))]
    tot = inv = 0
    for a, b in itertools.combinations(els, 2):
        ka, kb = a['caixa'], b['caixa']
        ca, cb = caixas[a['id']], caixas[b['id']]
        for k0, k1 in ((0, 2), (1, 3)):
            if ka[k1] <= kb[k0]:
                antes, depois = ca, cb
            elif kb[k1] <= ka[k0]:
                antes, depois = cb, ca
            else:
                continue
            tot += 1
            lado = cf['W'] if k0 == 0 else cf['H']
            if (antes[k0] + antes[k1]) - (depois[k0] + depois[k1]) > 2.0 * tol * lado:  # numero-neutro: soma das bordas e o dobro do centro
                inv += 1
    return inv / tot if tot else 0.0


def serie_partida(cf, v):
    """1 quando os itens de uma serie de itens iguais ficam em trilhas diferentes junto com outros blocos (a lista
    quebrada no meio do fluxo); 0 senao."""
    an2, part = v.get('an2'), v['part']
    if not part or an2 is None:
        return 0.0
    for s in series(cf['an']):
        ids = {el['id'] for i in s for el in cf['an']['atomos'][i]['els']}
        trilhas = [t for t in part if any(el['id'] in ids for i in t for el in an2['atomos'][i]['els'])]
        if len(trilhas) > 1 and any(el['id'] not in ids for t in trilhas for i in t for el in an2['atomos'][i]['els']):
            return 1.0
    return 0.0


def _pares_sobre(cf):
    """Os pares que a conferencia nao deixa passar a se sobrepor (e que nao se sobrepunham no KV). Guardado no
    contexto do formato."""
    if '_pares_sobre' not in cf:
        pares = []
        for a, b in itertools.combinations(cf['kv']['elementos'], 2):
            ka, kb = a['caixa'], b['caixa']
            if mod_solver.par_que_nao_sobrepoe(a, b) and not (
                    _sobra(ka[0], ka[2], kb[0], kb[2]) > 0 and _sobra(ka[1], ka[3], kb[1], kb[3]) > 0):
                pares.append((a['id'], b['id']))
        cf['_pares_sobre'] = pares
    return cf['_pares_sobre']


def falhas_previstas(cf, caixas, sangra=None, fundo=()):
    """Quantas falhas obrigatorias a candidata tem antes do solver, pela mesma conta barata da conferencia: conteudo
    fora do formato, abaixo do piso da 133, sobreposicao nova e distancia da 135 contra o KV (sem a validacao do motor).
    Escolhe melhor as candidatas que vao ao solver. fundo: os ids da figura de fundo da versao (n 202): fora dos pares
    de sobreposicao e da 135; o quadro e a sangria dela continuam contando."""
    kv, W, H = cf['kv'], cf['W'], cf['H']
    sangra = sangra or {}
    tol = limites.valor('derivacao.enquadramento_tolerancia_px')
    tol_col = limites.valor('derivacao.colisao_tolerancia_px')
    piso = limites.valor('derivacao.escala_conteudo_min_da_regra')
    piso_d = limites.valor('derivacao.distancia_entre_linhas_min')
    esc = _escalas(kv, caixas)
    n = 0
    for e in kv['elementos']:
        if not mod_solver.conteudo(e):
            continue
        c, sg = caixas[e['id']], sangra.get(e['id'], e['sangra'])
        r = cf['regras'][e['id']]
        n += bool(r and esc[e['id']] < piso * r - FOLGA_PISO)
        n += bool((c[0] < -tol and not sg['esq']) or (c[1] < -tol and not sg['topo']) or
                  (c[2] > W + tol and not sg['dir']) or (c[3] > H + tol and not sg['base']))
        # o lado que sangra continua com o corte fora da peca (o enquadramento da validacao do motor)
        m = e['caixa']
        am, s_e = e.get('caixa_asset') or m, esc[e['id']]
        a = [c[k] + s_e * (am[k] - m[k]) for k in range(4)]  # numero-neutro: os quatro lados
        n += bool((sg['esq'] and a[0] > tol) or (sg['topo'] and a[1] > tol) or
                  (sg['dir'] and a[2] < W - tol) or (sg['base'] and a[3] < H - tol))
    for a, b in _pares_sobre(cf):
        if a in fundo or b in fundo:
            continue
        ca, cb = caixas[a], caixas[b]
        n += bool(_sobra(ca[0], ca[2], cb[0], cb[2]) > tol_col and _sobra(ca[1], ca[3], cb[1], cb[3]) > tol_col)
    for a, b, gap in vizinhos_135(cf, fundo):
        va, vb = caixas[a], caixas[b]
        sep = max(vb[0] - va[2], va[0] - vb[2], vb[1] - va[3], va[1] - vb[3])
        n += bool(sep < piso_d * gap * (esc[a] + esc[b]) / 2.0 - tol)  # numero-neutro: media das duas escalas
    return n


def nota(cf, v, falhas):
    """Nota geral da candidata (maior e melhor), com os pesos de derivacao.galeria_nota_pesos: a escala do conteudo
    sobre a regra (log, saturada em derivacao.galeria_nota_satura; o titulo ate derivacao.galeria_titulo_sobre_outros_max
    vezes isso), o menor corpo (log, sem corte no piso: o conteudo minusculo perde), a razao entre os blocos (97: o
    espalhamento das escalas, fora o titulo, o legal colado e a faixa de borda), a figura (escala, conteudo sobre ela,
    parte a vista e o lado do KV), o espaco vazio, a ordem do KV, a lista partida, o espelho e as falhas. Nada aqui olha
    um KV em particular. Na versao com a figura de fundo (figura_de_fundo, n 202), o conteudo sobre ela nao pesa, e
    ela fica fora da ordem do KV."""
    P = {x['termo']: x['peso'] for x in limites.valor('derivacao.galeria_nota_pesos')}
    kv, caixas = cf['kv'], v['caixas']
    fundo = _fundo_de(cf, v['p'])
    esc = _escalas(kv, caixas)
    fx = cf['_figura']
    satura = limites.valor('derivacao.galeria_nota_satura')
    tit = limites.valor('derivacao.galeria_titulo_sobre_outros_max')
    fluxo = [e for e in kv['elementos'] if em_fluxo(e) and mod_solver.conteudo(e)]
    fora_da_razao = {e['id'] for e, _l in cf['an']['colados']}
    fora_da_razao |= {el['id'] for i, _l in v.get('faixas') or () for el in cf['an']['atomos'][i]['els']}
    logs, rels, razoes = [], [], []
    for e in fluxo:
        rg = cf['regras'][e['id']]
        if not rg:
            continue
        rel = max(esc[e['id']] / rg, MINUSCULO)
        logs.append(math.log(min(rel, satura * (tit if e['funcao'] == 'titulo' else 1.0))))
        rels.append(rel)
        if e['funcao'] != 'titulo' and e['id'] not in fora_da_razao:
            razoes.append(math.log(rel))
    n = P['escala'] * (sum(logs) / len(logs) if logs else 0.0)
    if rels:
        n += P['menor'] * math.log(min(rels))
    if len(razoes) > 1:
        n -= P['razao'] * statistics.pstdev(razoes)
    if fx is not None:
        rg = cf['regras'][fx['id']]
        if rg:
            n += P['figura'] * math.log(min(max(esc[fx['id']] / rg, MINUSCULO),
                                            limites.valor('derivacao.galeria_figura_teto_sobre_regra')))
        fc = caixas[fx['id']]
        tot = sum(_area(caixas[e['id']]) for e in fluxo)
        if tot and fx['id'] not in fundo:
            # o conteudo sobre a figura de fundo nao e defeito (n 202)
            n -= P['cobre'] * sum(_inter(caixas[e['id']], fc) for e in fluxo) / tot
        if _area(fc):
            vis = _inter(fc, [0.0, 0.0, cf['W'], cf['H']]) / _area(fc)
            n -= P['cobre'] * max(0.0, limites.valor('derivacao.galeria_figura_visivel_min') - vis)
        if v['p']['fig'] is not None:
            Wm, Hm = cf['bm']
            c = fx['caixa']
            eixo, lado = v['p']['fig']
            # o centro da figura no KV, de -1/2 (encostada no comeco) a 1/2; no meio (com a folga da ordem), nenhum lado
            # e o do KV
            tol = limites.valor('derivacao.galeria_ordem_tolerancia')
            k0, k1, D = (0, 2, Wm) if eixo == 'x' else (1, 3, Hm)
            rel = (c[k0] + c[k1]) / 2.0 / D - 0.5  # numero-neutro: centro
            do_kv = None if abs(rel) <= tol else (('esq' if eixo == 'x' else 'topo') if rel < 0 else
                                                  ('dir' if eixo == 'x' else 'base'))
            if do_kv is not None and lado != do_kv:
                n -= P['lado']
    q = v['q']
    aq = _area(q)
    if fluxo and aq:
        u = _uniao([caixas[e['id']] for e in fluxo])
        n -= P['vazio'] * (1.0 - min(_inter(u, q) / aq, 1.0))
    n -= P['ordem'] * ordem_invertida(cf, caixas, fundo)
    n -= P['serie_partida'] * serie_partida(cf, v)
    if v['espelhar']:
        n -= P['espelho']
    return n - P['falha'] * falhas


# ------------------------------------------------------------------ a frase do DA
def _rotulos_dos_atomos(an, idx):
    vistos = []
    for i in idx:
        for el in an['atomos'][i]['els']:
            r = _rotulo(el)
            if r not in vistos:
                vistos.append(r)
    return vistos


def _plural(rotulo):
    """O rotulo no plural, com o artigo: o grafismo vira os grafismos, e o nome terminado em ao (com til) troca o fim
    por oes; o rotulo ja no plural fica como esta."""
    artigo, _, nome = rotulo.partition(' ')
    if artigo in ('os', 'as') or not nome:
        return rotulo
    if nome.endswith('ão'):
        nome = nome[:-2] + 'ões'
    elif nome.endswith('m'):
        nome = nome[:-1] + 'ns'
    elif nome.endswith('l'):
        nome = nome[:-1] + 'is'
    elif nome[-1] in 'aeiouáéíóúâêô':
        nome += 's'
    else:
        nome += 'es'
    return artigo + 's ' + nome


def descrever(cf, v):
    """Uma linha curta em portugues para o DA: onde fica a figura, a faixa de borda, como o conteudo se arruma (com a
    lista girada e a ordem invertida) e a imagem."""
    p, an2, part = v['p'], v['an2'], v['part']
    fx = cf['_figura']
    pedacos = []
    if p['fig'] is not None:
        pedacos.append('%s %s' % (_rotulo(fx), LADO_NA_FRASE[p['fig'][1]]))
    for i, lf in v['faixas']:
        nome = _juntar(_rotulos_dos_atomos(cf['an'], [i]))
        ponta = ' de ponta a ponta' if p['faixa'] == 'inteira' and p['fig'] is not None else ''
        pedacos.append('%s %s%s' % (nome, 'no topo' if lf == 'topo' else 'na base', ponta))
    if part:
        resto = 'o resto' if pedacos else None
        if len(part) == 1:
            modo = 'em linha' if v['tipo'] == 'linhas' else 'empilhado'
            txt = '%s %s' % (resto or 'tudo', modo)
        else:
            txt = '%s em %d %s' % (resto or 'o conteúdo', len(part), 'colunas' if v['tipo'] == 'colunas' else 'linhas')
        if p['fig'] is not None:
            txt += ' ' + LADO_NA_FRASE[OPOSTO[p['fig'][1]]]
        seri = [a for a in an2['atomos'] if a.get('serie')]
        if seri:
            c = seri[0]['caixa']
            plural = _plural(_rotulo(seri[0]['els'][0]))
            # a concordancia com o genero do rotulo: as informacoes uma embaixo da outra
            em_pilha = 'uma embaixo da outra' if plural.startswith('as ') else 'um embaixo do outro'
            txt += ', com %s %s' % (plural, 'lado a lado' if c[2] - c[0] >= c[3] - c[1] else em_pilha)
        if v['espelhar']:
            txt += ', na ordem invertida'
        pedacos.append(txt)
    if p['arte'] is not None:
        inicio, fim = ('à esquerda', 'à direita') if _eixo_longo(cf['W'], cf['H']) == 'x' else ('em cima', 'embaixo')
        pedacos.append('%s livre %s' % ('a arte' if v['arte'] is not None else 'a imagem',
                                        fim if p['arte'] == 'fim' else inicio))
    if figura_de_fundo(cf, p) is not None:
        # n 202: a foto do KV deitado fica de fundo no formato em pe ou quadrado, e o conteudo vai por cima dela
        pedacos.append('%s fica de fundo, atrás do conteúdo' % _rotulo(fx))
    elif p['arte'] is None and p['fig'] is None:
        pedacos.append('%s de fundo' % ('a imagem' if fx is None else _rotulo(fx)))
    if not pedacos:
        return 'Só a imagem'
    return _maiuscula('; '.join(pedacos))

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


def contexto_do_formato(ctx, kv, formato, *, specs=None, arquivo_specs=None, params=None):
    """O contexto que a galeria monta para um formato (para a edicao no palco reaproveitar entre as edicoes)."""
    cf = _contexto(ctx, kv, formato, specs, arquivo_specs, params)
    cf['esperado'] = mod_nucleo._esperado(ctx, kv)
    return cf


def conferir_edicao(cf, caixas, sangra, apagados=(), geometria=None, fundo=()):
    """(falhas, avisos, validacoes reprovadas) do layout editado pelo DA, contra a mestre verdadeira; o elemento
    apagado sai da conta e o inventario o registra. geometria (0.9.6): as caixas que dao a escala de cada elemento,
    quando caixas leva a caixa visivel do texto editado (as linhas do DA, decisao 196). Sem ela, as proprias caixas.
    fundo: os ids da figura de fundo da versao de partida neste formato (fundo_da_versao; n 202)."""
    return _conferir(sem_elementos(cf, apagados), caixas, sangra, apagados=apagados, com_validacoes=True,
                     geometria=geometria, fundo=fundo)


def decisoes_do_da(cf, falhas, do_da, da_partida=()):
    """(falhas que ficam, decisoes do DA) do layout editado no palco (M7b, D5; pergunta 10 do plano). A falha de piso
    (PISOS_DO_DA: a escala abaixo do piso da 133, a distancia menor que a da 135) com um elemento que o DA mexeu ou
    escalou (do_da) e decisao dele: sai das falhas e ganha o texto com o valor a vista. Depois da edicao, nada refaz o
    encaixe (0.9.5): o elemento que o DA nao mexeu fica parado, e so a edicao do DA muda o layout. O resto (fora do
    quadro, area segura, sobreposicao, validacao do motor) continua falha. Revisao 1 da fase D: o piso que a versao de
    partida ja furava (da_partida: os pares (codigo, elementos ordenados) das falhas dela) continua falha, porque o DA
    nao o furou; a distancia de duas caixas que se sobrepoem (zero ou menos) tambem, porque a sobreposicao ja pede
    ajuste e px negativo nao diz nada ao DA. A relacao de fundo quebrada (relacao_quebrada, decisao 199, 3) com um
    elemento que o DA mexeu tambem e decisao dele, com a mesma frase. A ordem das listas e a das falhas."""
    do_da = set(do_da)
    da_partida = set(da_partida)
    por_id = {e['id']: e for e in cf['kv']['elementos']}
    ficam, decisoes = [], []
    for f in falhas:
        els = set(f['elementos'])
        m = f.get('medidas') or {}
        if f['codigo'] == 'relacao_quebrada' and els & do_da and (f['codigo'], tuple(sorted(els))) not in da_partida:
            # a relacao de fundo que o proprio DA desfez no palco e o layout que ele aprova (199, 3): decisao dele,
            # com a frase a vista
            decisoes.append(dict(f))
            continue
        if f['codigo'] not in PISOS_DO_DA or not els & do_da or \
                (f['codigo'], tuple(sorted(els))) in da_partida or \
                (f['codigo'] == 'distancia_menor_que_na_mestre' and float(m.get('distancia_px', 1)) <= 0):
            ficam.append(f)
            continue
        nomes = [_rotulo(por_id[k]) if k in por_id else ROTULO_GERAL for k in f['elementos']]
        if f['codigo'] == 'abaixo_do_piso_da_regra':
            piso = m.get('minimo_da_regra', limites.valor('derivacao.escala_conteudo_min_da_regra'))
            texto = '%s fica com %d%% da escala prevista. O mínimo é %d%%.' % (
                # a falha so existe abaixo do piso, e a medida dela e arredondada
                _maiuscula(nomes[0]), _porcento_da_regra(min(m['fracao_da_regra'], piso - FOLGA_PISO), piso),
                round(piso * 100))  # numero-neutro: porcentagem
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


def _tinta_da_base(cf, e):
    """(tinta na mestre, tinta no espaco do KV, caixa de partida, sem silhueta) da base e (desdobra.derivacao.silhueta),
    guardada no contexto do formato: a mesma em todas as conferencias dele."""
    cache = cf.setdefault('_tintas', {})
    if e['id'] not in cache:
        kv = cf['kv']
        canvas = [float(v) for v in (kv.get('canvas_doc') or [0.0, 0.0, kv['largura'], kv['altura']])]
        de = [float(v) for v in (e.get('caixa_kv') or e['caixa'])]
        partes = mod_silhueta.partes_do_elemento(cf['ctx'], e, canvas)
        tinta, sem = mod_silhueta.tinta_do_elemento(partes, de, canvas[2] - canvas[0], canvas[3] - canvas[1])
        mestre = mod_silhueta.tinta_no_layout(tinta, de, e['caixa'], float(kv['largura']), float(kv['altura']))
        cache[e['id']] = (mestre, tinta, de, sem)
    return cache[e['id']]


def _relacoes_de_fundo(cf, caixas, cont, tol):
    """O ponto cego da conferencia (decisao 199, 3): o par conteudo x base que ja se sobrepunha na mestre fica fora do
    "nao sobrepor" acima, e a assinatura podia ir para cima do azul sem falha. Agora o par e conferido pela tinta da
    base (a silhueta que o preparo gravou; sem ela, a caixa): quando, na mestre, o conteudo estava dentro da tinta ou
    livre dela, a relacao tem de continuar no formato, com a folga do pixel (tol). O fundo puro (a tinta cobre ao
    menos derivacao.bloco_fundo_fracao do canvas da mestre) fica de fora: o conteudo nunca sai de cima dele. So no
    formato que copia o layout do KV (copia_do_kv, em _contexto); a variante da galeria reorganiza de proposito. Devolve
    ([(conteudo, base, relacao, fracao do conteudo sobre a tinta no formato)], [bases conferidas pela caixa])."""
    kv, W, H = cf['kv'], cf['W'], cf['H']
    Wm, Hm = float(kv['largura']), float(kv['altura'])
    fundo_min = limites.valor('derivacao.bloco_fundo_fracao')
    quebradas, pela_caixa = [], []
    for b in kv['elementos']:
        if mod_solver.conteudo(b) or b['classe'] != 'base' or b['id'] not in caixas:
            continue
        kb = b['caixa']
        pares = [c for c in cont if _sobra(c['caixa'][0], c['caixa'][2], kb[0], kb[2]) > 0 and
                 _sobra(c['caixa'][1], c['caixa'][3], kb[1], kb[3]) > 0]
        if not pares:
            continue
        mestre, tinta, de, sem = _tinta_da_base(cf, b)
        if mod_silhueta.cobertura([0.0, 0.0, Wm, Hm], mestre) >= fundo_min:
            continue
        no_formato = None
        for c in pares:
            rel = mod_silhueta.relacao(c['caixa'], mestre, tol)
            if rel is None:
                continue
            if sem and b not in pela_caixa:
                pela_caixa.append(b)
            if no_formato is None:
                no_formato = mod_silhueta.tinta_no_layout(tinta, de, caixas[b['id']], W, H)
            if mod_silhueta.quebrada(rel, caixas[c['id']], no_formato, tol):
                quebradas.append((c, b, rel, mod_silhueta.cobertura(caixas[c['id']], no_formato)))
    return quebradas, pela_caixa


def _conferir(cf, caixas, sangra, apagados=(), com_validacoes=False, geometria=None, fundo=()):
    """Falhas obrigatorias contra a mestre verdadeira e avisos de elemento. Devolve (falhas, avisos); com_validacoes,
    (falhas, avisos, nomes das validacoes do motor que reprovam). geometria: as caixas que dao a escala (0.9.6; sem
    ela, caixas); a posicao, a sobreposicao e o enquadramento usam caixas, a caixa que o DA ve. fundo: os ids da figura
    de fundo da versao (figura_de_fundo; decisoes-v1.md, n 202): o conteudo sobre ela nao e sobreposicao nova, e ela
    nao entra na distancia da 135; o quadro, a area segura e o piso dela continuam conferidos."""
    fundo = set(fundo)
    kv, W, H, areas = cf['kv'], cf['W'], cf['H'], cf['areas']
    els = kv['elementos']
    tol = limites.valor('derivacao.enquadramento_tolerancia_px')
    tol_col = limites.valor('derivacao.colisao_tolerancia_px')
    seg = (areas.get('area_segura') or {}).get('caixa')
    piso = limites.valor('derivacao.escala_conteudo_min_da_regra')
    piso_d = limites.valor('derivacao.distancia_entre_linhas_min')
    esc, regra = _escalas(kv, caixas if geometria is None else geometria), cf['regras']
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
        if not mod_solver.par_que_nao_sobrepoe(a, b) or a['id'] in fundo or b['id'] in fundo:
            continue
        ka, kb = a['caixa'], b['caixa']
        if _sobra(ka[0], ka[2], kb[0], kb[2]) > 0 and _sobra(ka[1], ka[3], kb[1], kb[3]) > 0:
            continue  # ja se sobrepoem na mestre
        ca, cb = caixas[a['id']], caixas[b['id']]
        if _sobra(ca[0], ca[2], cb[0], cb[2]) > tol_col and _sobra(ca[1], ca[3], cb[1], cb[3]) > tol_col:
            sobre.append((a, b))
    # a figura de fundo fica fora dos pares daqui para baixo (a relacao de fundo e a 135)
    cont = [e for e in cont if e['id'] not in fundo]
    quebradas, pela_caixa = _relacoes_de_fundo(cf, caixas, cont, tol) if cf.get('copia_do_kv') else ([], [])
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
    val = _validacoes(cf, caixas, sangra, esc, apagados, fundo)
    falhas = []
    for e in fora:
        falhas.append(_item('fora_do_quadro', '%s sai do formato.' % _maiuscula(_rotulo(e)), [e['id']]))
    for e in fora_seg:
        falhas.append(_item('fora_da_area_segura', '%s passa da área segura.' % _maiuscula(_rotulo(e)), [e['id']]))
    for e, fr in abaixo:
        falhas.append(_item('abaixo_do_piso_da_regra', '%s fica com %d%% da escala prevista, abaixo do mínimo de %d%%.'
                             % (_maiuscula(_rotulo(e)), _porcento_da_regra(fr, piso), round(piso * 100)), [e['id']],  # numero-neutro: porcentagem
                             fracao_da_regra=round(fr, 4), minimo_da_regra=piso))  # numero-neutro: casas da medida
    for a, b in sobre:
        falhas.append(_item('sobreposicao_nova', '%s e %s passam a se sobrepor.' % (_maiuscula(_rotulo(a)), _rotulo(b)),
                             [a['id'], b['id']]))
    for c, b, rel, cob in quebradas:
        base, nome = _rotulo(b), _rotulo(c)
        if rel['tipo'] == mod_silhueta.LIVRE:
            texto = '%s passa por cima %s, e no KV ficava fora %s.' % (
                _maiuscula(nome), mod_familia._contrair('de', base), mod_familia._dela(base))
        else:
            texto = '%s deixa de ficar %s sobre %s, como estava no KV.' % (
                _maiuscula(nome), INTEIRO.get(nome.partition(' ')[0], 'inteiro'), base)
        falhas.append(_item('relacao_quebrada', texto, [c['id'], b['id']], relacao=rel['tipo'],
                             fracao_sobre_a_forma=round(cob, 4)))  # numero-neutro: casas da medida
    for a, b, sep, minimo in perto:
        falhas.append(_item('distancia_menor_que_na_mestre', '%s e %s ficam mais perto do que o KV permite.'
                             % (_maiuscula(_rotulo(a)), _rotulo(b)), [a['id'], b['id']],
                             distancia_px=round(sep, 1), minimo_px=round(minimo, 1)))
    por_id = {e['id']: e for e in els}
    for v in mod_validacao.reprovadas(val):
        if v['nome'] == FUNDO_ACIMA:
            # a foto de fundo acima de um conteudo na pilha do PSD (n 202): a frase diz a causa, que mexer no palco nao
            # resolve; a validacao continua reprovando no "Salvar e seguir"
            for a, b in v['medidas']['pares']:
                foto, nome = _rotulo(por_id[a]), _rotulo(por_id[b])
                falhas.append(_item(FUNDO_ACIMA, '%s fica acima %s na ordem das camadas do PSD e sai por cima %s. '
                                    'Escolha uma versão com %s ao lado do conteúdo ou mude a ordem das camadas no PSD.'
                                    % (_maiuscula(foto), mod_familia._contrair('de', nome), mod_familia._dela(nome),
                                       foto), [a, b]))
            continue
        falhas.append(_item('validacao_reprova', 'A conferência do motor reprova esta versão.', v['elementos'],
                             validacao=v['nome']))
    avisos = _avisos_de_elemento(cf, caixas, sangra, esc)
    for b in pela_caixa:
        base = _rotulo(b)
        avisos.append(_item(mod_silhueta.AVISO_CAIXA, 'O desdobra conferiu %s pela caixa, porque não tem o desenho %s.'
                            % (base, mod_familia._dela(base)), [b['id']]))
    if com_validacoes:
        return falhas, avisos, sorted({v['nome'] for v in mod_validacao.reprovadas(val)})
    return falhas, avisos


def _validacoes(cf, caixas, sangra, esc, apagados=(), fundo=()):
    """As validacoes do motor (desdobra.derivacao.validacao) do layout, contra a mestre verdadeira; o elemento apagado
    pelo DA sai da conta do inventario. A origem da colisao e a do motor: os elementos do KV, tambem quando a mestre
    tem a caixa medida da quebra de linha (elementos_de_origem, desdobra.derivacao.nucleo._com_quebras). Assim a previa
    mostra a colisao que o "Salvar e seguir" acha (previa igual ao Salvar, M7b). fundo: os ids da figura de fundo da
    versao (n 202), na validacao do motor."""
    kv, W, H, areas = cf['kv'], cf['W'], cf['H'], cf['areas']
    els, regra = kv['elementos'], cf['regras']
    aplicados = mod_nucleo._aplicados(kv, [regra[e['id']] for e in els])
    for x in aplicados:
        if x['id'] in sangra:
            x['sangra'] = sangra[x['id']]
    if 'esperado' not in cf:
        cf['esperado'] = mod_nucleo._esperado(cf['ctx'], kv)
    inteiro = cf.get('kv_inteiro') or kv
    origem = {e['id']: e for e in inteiro.get('elementos_de_origem') or inteiro['elementos']}
    return mod_validacao.validar((W, H), areas, aplicados, [caixas[e['id']] for e in els], [esc[e['id']] for e in els],
                                 origem, cf['esperado'], apagados=apagados, fundo=fundo)


def validacoes_do_layout(cf, caixas, sangra, apagados=(), geometria=None, fundo=()):
    """As validacoes do motor do layout editado pelo DA, na forma de derivacao/<formato>.json (para a derivacao gravar
    a proposta confirmada; desdobra.derivacao.proposta). geometria: as caixas que dao a escala (0.9.6), como em
    conferir_edicao. fundo: os ids da figura de fundo (n 202), como em conferir_edicao."""
    cf = sem_elementos(cf, apagados)
    return _validacoes(cf, caixas, sangra, _escalas(cf['kv'], caixas if geometria is None else geometria), apagados,
                       fundo)


def _fundo_sem_desenho(cf, e):
    """O fundo cujo corte no formato nao tira nada do KV: o de cor chapada (so camadas de cor solida ou de
    preenchimento, desdobra.derivacao.elementos.TIPOS_DE_COR) ou o que cobre o canvas inteiro do KV (sangra nos quatro
    lados: a troca de proporcao sempre corta parte dele). Nele, o aviso de fundo pouco visivel nao diz nada ao DA; o
    fundo com imagem que nao cobre o canvas continua com o aviso."""
    if all(e['sangra'].get(lado) for lado in mod_elementos.LADOS):
        return True
    tipos = cf.get('_tipos_das_camadas')
    if tipos is None:
        laudo = cf['ctx'].get('laudo') or {}
        tipos = {c['identidade']['layer_id']: c.get('tipo') for c in laudo.get('camadas') or ()}
        cf['_tipos_das_camadas'] = tipos
    ids = e.get('layer_ids') or ()
    return bool(ids) and all(tipos.get(lid) in mod_elementos.TIPOS_DE_COR for lid in ids)


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
        if e['funcao'] == 'fundo' and area and vis / area < vis_min and not _fundo_sem_desenho(cf, e):
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
    # a figura de fundo que passa a sangrar (n 202) nao e a arte da parte livre: o aviso e so da arte
    arte = sorted(k for k in v['sangra'] if k not in _fundo_de(cf, v['p']))
    if arte:
        avisos.append(_item('sangria_da_arte_mudou', 'A arte vira um bloco na parte livre e muda os lados em que sangra.',
                             arte))
    q = v['s_fit'] / cf['regra_ref'] if cf['regra_ref'] else 1.0
    piso = limites.valor('derivacao.escala_conteudo_min_da_regra')
    # so o conteudo abaixo do piso da 133: o solver que nao fecha ja volta como falha solver_nao_fecha, com o nome dele.
    # O piso por bloco sobe o conteudo ao minimo (_gerar): a frase diz a escala que a versao mostra, nao a que cabia
    if q < piso:
        pct = round(piso * 100)  # numero-neutro: porcentagem
        avisos.append(_item('conteudo_nao_cabe', 'O conteúdo fica no mínimo de %d%% da escala prevista e passa do espaço '
                             'livre. Vale ver se algum texto secundário pode sair.' % pct, [],
                             fracao_que_cabe=round(q, 3)))  # numero-neutro: casas da medida
    return avisos


def distancia(cf, a, b):
    """Media do deslocamento do centro de cada elemento de conteudo entre duas variantes, sobre a diagonal. A figura
    de fundo das duas (n 202) fica no mesmo lugar nas duas e fica fora da media."""
    diag = math.hypot(cf['W'], cf['H'])
    fora = set(_fundo_de(cf, a['p'])) & set(_fundo_de(cf, b['p']))
    ds = []
    for e in cf['kv']['elementos']:
        if mod_solver.conteudo(e) and e['id'] not in fora:
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
        if e.get('texto_como_imagem'):
            saida[-1]['texto_como_imagem'] = list(e['texto_como_imagem'])  # 0.9.1, como em derivacao.nucleo
            saida[-1]['caixas_texto_como_imagem'] = mod_nucleo._caixas_como_imagem(ctx, e['texto_como_imagem'],
                                                                                  doc, c, s)
    return saida


def _saida(cf, v, ordem):
    # a conferencia ve as caixas que a variante leva (arredondadas em _elementos), as mesmas que a derivacao da familia
    # confirmada grava e confere (desdobra.derivacao.proposta.layout_do_membro): o par que o solver deixa a
    # exatamente a tolerancia da colisao nunca vira falha so na tela (previa igual ao Salvar, M7b)
    elementos = _elementos(cf, v)
    caixas = {e['id']: [float(x) for x in e['caixa']] for e in elementos}
    fundo = _fundo_de(cf, v['p'])
    falhas, avisos = _conferir(cf, caixas, v['sangra'], fundo=fundo)
    if v['falha_solver']:
        falhas.append(_item('solver_nao_fecha', 'As restrições da folha e do KV não fecham nesta versão.', [],
                             restricao=v['falha_solver']))
    if v.get('esmagados'):
        por_id = {e['id']: e for e in cf['kv']['elementos']}
        rotulos = [_rotulo(por_id[k]) for k in v['esmagados']]
        nomes = []
        for r in rotulos:
            nome = _plural(r) if rotulos.count(r) > 1 else r
            if nome not in nomes:
                nomes.append(nome)
        falhas.append(_item('bloco_esmagado', 'Nesta versão, o ajuste final encolhe demais %s.' % _juntar(nomes),
                             list(v['esmagados'])))
    p = v['p']
    return {'id': v['id'], 'ordem': ordem, 'descricao': descrever(cf, v), 'elementos': elementos,
            'avisos': avisos + _avisos_da_variante(cf, v), 'falhas_obrigatorias': falhas,
            'estrutura': {'tipo': v['tipo'], 'trilhas': [len(t) for t in v['part']], 'espelhada': v['espelhar'],
                          'imagem_livre': v['lado_img'], 'figura': p['fig'] and p['fig'][1],
                          'faixa_de_borda': p['faixa'], 'serie_girada': p['serie'],
                          # o id da figura que fica de fundo nesta versao (n 202), ou None: 'figura' None nao diz
                          # se a versao nao tem figura ou se a figura e o fundo
                          'figura_de_fundo': fundo[0] if fundo else None},
            'situacao': 'proposta' if not v['falha_solver'] else 'proposta_sem_solver',
            'escala_do_conteudo': round(v['s'], mod_nucleo.CASAS_ESCALA)}


# ------------------------------------------------------------------ a galeria
def _parametros(cf, so_imagem_livre=False):
    """Os arquetipos que geram candidatas (nenhum e escolhido pela proporcao: todos passam pela nota, decisao 166). A
    figura: cada um dos quatro lados, ou de fundo como no KV; sem figura, a imagem livre de cada lado do lado maior, ou
    de fundo; a faixa de borda presa a borda (de ponta a ponta ou so sobre o conteudo) ou no fluxo; a lista girada ou
    nao; a melhor particao ou a melhor do outro tipo; a ordem do KV ou espelhada. so_imagem_livre: so a imagem livre
    com a figura de fundo (para a figura que nao cabe em banda nenhuma, variantes)."""
    fx = cf['_figura']
    figs = [None] if fx is None or so_imagem_livre else [('x', 'esq'), ('x', 'dir'), ('y', 'topo'), ('y', 'base'), None]
    artes = ['inicio', 'fim'] if so_imagem_livre else [None, 'inicio', 'fim'] if fx is None else [None]
    faixas = [None, 'inteira', 'conteudo'] if cf['_faixas'] else [None]
    sers = [False, True] if series(cf['an']) else [False]
    saida = []
    for fig, arte, faixa, ser, modo, esp in itertools.product(figs, artes, faixas, sers, ('melhor', 'outra'),
                                                              (False, True)):
        if fig is None and faixa == 'conteudo':
            continue
        saida.append({'fig': fig, 'arte': arte, 'faixa': faixa, 'serie': ser, 'modo': modo, 'espelhar': esp})
    return saida


def _id(p):
    """O id da versao, feito dos parametros dela (parametros_do_id desfaz): a tela le a versao escolhida por ele."""
    partes = []
    if p['fig'] is not None:
        partes.append('figura_%s' % p['fig'][1])
    if p['arte'] is not None:
        partes.append('imagem_livre_%s' % p['arte'])
    if p['faixa']:
        partes.append('faixa_%s' % p['faixa'])
    if p['serie']:
        partes.append('serie_girada')
    if p['modo'] == 'outra':
        partes.append('outra_estrutura')
    if p['espelhar']:
        partes.append('espelhado')
    return '__'.join(partes) or 'reorganizado'


def parametros_do_id(vid):
    """O inverso de _id: os parametros da versao (para variante_para_grupo refazer a mesma versao nos membros do
    grupo). O pedaco que nao e desta galeria fica de fora."""
    partes = set(vid.split('__')) if vid != 'reorganizado' else set()
    fig = next(((('x' if x[7:] in ('esq', 'dir') else 'y'), x[7:]) for x in sorted(partes)
                if x.startswith('figura_') and x[7:] in OPOSTO), None)
    arte = next((x[13:] for x in sorted(partes) if x.startswith('imagem_livre_') and x[13:] in ('inicio', 'fim')), None)
    faixa = next((x[6:] for x in sorted(partes) if x.startswith('faixa_') and x[6:] in ('inteira', 'conteudo')), None)
    return {'fig': fig, 'arte': arte, 'faixa': faixa, 'serie': 'serie_girada' in partes,
            'modo': 'outra' if 'outra_estrutura' in partes else 'melhor', 'espelhar': 'espelhado' in partes}


def figura_de_fundo(cf, p):
    """O id da figura que fica de fundo nesta versao (decisoes-v1.md, n 202, revendo a 96 so neste caso), ou None: o
    KV deitado com a figura (figura(kv)), o formato em pe ou quadrado e a versao sem a figura numa banda (p['fig']
    None). Nela, o conteudo pode ficar sobre a foto, e isso nao e falha. A versao com banda, o KV em pe ou quadrado, o
    formato deitado e o KV sem figura ficam como antes. Os ids das versoes nao mudam."""
    fx = cf.get('_figura')
    if fx is None or p['fig'] is not None:
        return None
    if '_fundo_elegivel' not in cf:
        # guardado no contexto do formato: a nota e a distancia das candidatas perguntam muitas vezes
        cf['_fundo_elegivel'] = mod_escala.orientacao(*cf['bm']) == 'horizontal' and \
            mod_escala.orientacao(cf['W'], cf['H']) in ('vertical', 'quadrado')
    return fx['id'] if cf['_fundo_elegivel'] else None


def fundo_da_versao(cf, vid):
    """(id da figura de fundo,) da versao de id vid neste formato (figura_de_fundo), ou (): o conjunto que a
    conferencia, as validacoes e o solver recebem. vid None (sem versao): ()."""
    return _fundo_de(cf, parametros_do_id(vid)) if vid else ()


def _fundo_de(cf, p):
    fx = figura_de_fundo(cf, p)
    return () if fx is None else (fx,)


def _resolvida(cf, v):
    """A candidata depois do solver: as caixas resolvidas, o nome da restricao que nao fecha e os ids dos blocos que o
    solver esmagou (ficaram com menos que o piso da 133 da escala que o fluxo planejou). O bloco esmagado e falha
    (_saida): o solver nao segura o piso do objeto solto (o grafismo), e o icone de 2 px nao pode abrir a galeria como
    versao limpa."""
    kv = cf['kv']
    planejada = _escalas(kv, v['caixas'])
    fundo = _fundo_de(cf, v['p'])
    # sem figura de fundo, a chamada de antes (quem troca _resolver, como os testes, continua valendo)
    caixas, falha = _resolver(cf, v['caixas'], v['sangra'], fundo) if fundo else _resolver(cf, v['caixas'], v['sangra'])
    esc = _escalas(kv, caixas)
    fx_id = (cf.get('_figura') or {}).get('id')
    deformado = limites.valor('derivacao.escala_conteudo_min_da_regra')
    esmagados = [e['id'] for e in kv['elementos'] if (em_fluxo(e) or e['id'] == fx_id) and
                 esc[e['id']] < deformado * planejada[e['id']] - FOLGA_PISO]
    return dict(v, caixas=caixas, falha_solver=falha, esmagados=esmagados)


def _falhas_na_nota(r, out):
    """Quantas falhas a nota conta: as da conferencia, com cada bloco esmagado contado uma vez (a falha bloco_esmagado
    junta todos numa frase so)."""
    n = len(out['falhas_obrigatorias'])
    return n - 1 + len(r['esmagados']) if r.get('esmagados') else n


def _finais(cf, prontas, limite, minimo):
    """As versoes da galeria: as limpas primeiro, da melhor nota para a pior, ate limite; a versao com falha so entra
    para chegar ao minimo. Sai a quase igual a uma escolhida (derivacao.galeria_duplicada_distancia_max) e a de mesma
    frase. A versao com a figura de fundo (figura_de_fundo; decisoes-v1.md, n 202) e uma opcao a mais, nunca o lugar
    das versoes com a figura numa banda: em cada passada (as limpas, depois as com falha), a melhor sem a figura de
    fundo vem primeiro, e so derivacao.galeria_fundo_max versoes de fundo entram antes das outras com banda; as outras
    de fundo, so na vaga que sobra."""
    duplicada = limites.valor('derivacao.galeria_duplicada_distancia_max')
    fundo_max = int(limites.valor('derivacao.galeria_fundo_max'))
    ordem = sorted(prontas, key=lambda x: (bool(x[1]['falhas_obrigatorias']), -x[0]['nota']))
    final = []

    def repetida(v, out):
        return any(out['descricao'] == o['descricao'] or distancia(cf, v, k) < duplicada for k, o in final)
    for com_falha, teto in ((False, limite), (True, minimo)):
        da_vez = [x for x in ordem if bool(x[1]['falhas_obrigatorias']) == com_falha]
        # a melhor sem a figura de fundo abre a passada: a partida de quem nao escolheu versao fica como antes
        primeira = next((x for x in da_vez if not _fundo_de(cf, x[0]['p'])), None)
        if primeira is not None:
            da_vez = [primeira] + [x for x in da_vez if x is not primeira]
        adiadas = []
        for v, out in da_vez:
            if len(final) >= teto:
                break
            if repetida(v, out):
                continue
            if _fundo_de(cf, v['p']) and sum(1 for k, _o in final if _fundo_de(cf, k['p'])) >= fundo_max:
                adiadas.append((v, out))
                continue
            final.append((v, out))
        # a de fundo alem de derivacao.galeria_fundo_max so ocupa a vaga que as com banda deixam
        for v, out in adiadas:
            if len(final) >= teto:
                break
            if not repetida(v, out):
                final.append((v, out))
    return final


def variantes(ctx, kv, formato, limite=None, *, specs=None, arquivo_specs=None, params=None):
    """A galeria de um formato: [{'id', 'ordem', 'descricao', 'elementos', 'avisos', 'falhas_obrigatorias',
    'estrutura', 'situacao', 'escala_do_conteudo', 'nota'}], de derivacao.galeria_variantes_min a limite
    (derivacao.galeria_variantes_max) versoes diferentes (a quase igual a uma anterior, a menos de
    derivacao.galeria_duplicada_distancia_max, sai), as limpas primeiro e da melhor nota para a pior. Todas as
    candidatas ganham a nota antes do solver (com as falhas previstas); as derivacao.galeria_candidatas_ao_solver
    melhores e diferentes vao ao solver e a conferencia, e mais vao enquanto faltar versao limpa para o minimo. ctx e
    kv: o contexto da derivacao e a mestre do KV (derivacao.nucleo.contexto e mestre_do_kv); formato: o do briefing.
    Sem specs, le as do job (ctx['pasta']). So previa: nao grava nada."""
    limite = int(limites.valor('derivacao.galeria_variantes_max') if limite is None else limite)
    minimo = min(int(limites.valor('derivacao.galeria_variantes_min')), limite)
    lote = int(limites.valor('derivacao.galeria_candidatas_ao_solver'))
    duplicada = limites.valor('derivacao.galeria_duplicada_distancia_max')
    cf = _contexto(ctx, kv, formato, specs, arquivo_specs, params)
    cands = []
    for so_imagem_livre in (False, True):
        # a figura que nao cabe em banda nenhuma (a foto que cobre quase o KV todo, a que sangra dos dois lados de um
        # formato alongado) fica de fundo, e a imagem livre da as outras versoes ate o minimo
        if so_imagem_livre and (cf['_figura'] is None or any(v['p']['fig'] for v in cands)):
            break
        for p in _parametros(cf, so_imagem_livre):
            v = gerar(cf, p)
            if v is None:
                continue
            v['id'] = _id(p)
            v['nota_previa'] = nota(cf, v, falhas_previstas(cf, v['caixas'], v['sangra'], _fundo_de(cf, p)))
            cands.append(v)
    cands.sort(key=lambda v: -v['nota_previa'])
    fila, enviadas, prontas, final = iter(cands), [], [], []
    while True:
        novas = 0
        for v in fila:
            if any(distancia(cf, v, k) < duplicada for k in enviadas):
                continue
            enviadas.append(v)
            r = _resolvida(cf, v)
            out = _saida(cf, r, 0)
            r['nota'] = nota(cf, r, _falhas_na_nota(r, out))
            out['nota'] = round(r['nota'], 4)  # numero-neutro: casas da nota
            prontas.append((r, out))
            novas += 1
            if novas >= lote:
                break
        final = _finais(cf, prontas, limite, minimo)
        # mais um lote enquanto faltar versao limpa para o minimo: a versao com falha que completa o minimo nao segura
        # a limpa que ainda nao passou pelo solver. A limpa com a figura de fundo (n 202) nao conta: as versoes com a
        # figura numa banda vao ao solver como antes (_finais)
        if sum(1 for v, out in final if not out['falhas_obrigatorias'] and not _fundo_de(cf, v['p'])) >= minimo \
                or not novas:
            break
    for n, (_v, out) in enumerate(final, 1):
        out['ordem'] = n
    return [out for _v, out in final]


def variante_para_grupo(ctx, kv, formatos, escolha, *, specs=None, arquivo_specs=None, params=None):
    """Uma estrutura so para todos os membros de um grupo de proporcao (derivacao.grupo_proporcao_dif_max): a versao
    escolhida (id, refeita pelos parametros dele, parametros_do_id) com a estrutura (tipo e trilhas) de um dos membros,
    a que deixa o pior membro melhor (mais membros sem falha obrigatoria, depois a maior escala do pior membro relativa
    a mesma versao sozinha nele). Devolve {'variante', 'estrutura', 'membros': {id do formato: variante},
    'membros_sem_falha', 'pior_escala_relativa', 'candidatas'}; ValueError quando nenhuma estrutura serve a todos. So
    previa: nao grava nada."""
    p = parametros_do_id(escolha)
    cfs = [(f['id'], _contexto(ctx, kv, f, specs, arquivo_specs, params)) for f in formatos]
    proprias = {fid: gerar(cf, p) for fid, cf in cfs}
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
            v = gerar(cf, p, forcada=est) if est is not None else proprias[fid]
            if v is None:
                break
            saida = _saida(cf, _resolvida(cf, dict(v, id=escolha)), 1)
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
