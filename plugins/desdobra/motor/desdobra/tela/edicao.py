# -*- coding: utf-8 -*-
"""Edicao da composicao no palco, por familia (M7a, fatia 4; decisoes-v1.md, 164, 166, 167, 168, 169, 171 e 185).

A familia (as composicoes de proporcao parecida de uma orientacao, desdobra.tela.estado.agrupar_por_proporcao) recebe
as decisoes do DA de uma vez so, nunca peca a peca:
  - o ponto de partida de cada membro e a versao da galeria que o DA escolheu (o formato devolvido) ou a proposta da
    derivacao (o formato derivado); sem escolha, a primeira versao sem falha, como a tela mostra;
  - cada edicao (mover, escalar, texto, apagar) e gravada em fracao do lado da peca e vai a cada membro em proporcao
    ao formato dele (aplicar);
  - o grupo (M7b, D1): mover e escalar podem levar a lista dos elementos escolhidos juntos no palco (elementos, o
    elemento da edicao e o primeiro dela). O grupo anda junto, e o escalar usa o ponto fixo em fracao da caixa que
    junta o grupo no formato: cada membro da familia escala o grupo em volta do mesmo ponto dele, e as distancias
    entre os elementos do grupo mudam na razao do tamanho. O grupo que fica (grupos) e o dos elementos que andaram
    juntos na ultima edicao de cada um; a intencao de alinhamento nunca o separa;
  - alinhar no quadro (M7b, D2): o elemento, ou o grupo, encosta na margem esquerda, na direita, no topo ou na base,
    ou fica no centro da largura ou da altura do quadro de cada membro (a margem dele ou a area segura dele). A
    intencao fica ate o DA mexer naquele eixo (intencoes): o alinhamento entre elementos nao a desfaz, e ela e firmada
    de novo depois do encaixe refeito pelo solver (firmar);
  - a escala por numero (M7b, D3): o tamanho de cada elemento e a conta dos fatores das edicoes de escalar que o
    levam, sozinho ou no grupo (escalas); 100% e o tamanho antes das edicoes do DA, a versao de onde o membro parte. O
    campo Tamanho da pagina grava o escalar que leva do tamanho de agora ao digitado. O tamanho fica entre
    tela.escala_min e tela.escala_max (limites_da_escala): a previa e o rascunho recusam a edicao que passa disso
    (escala_fora). O tamanho que o rascunho gravado ja tinha fora dos limites (a tela de antes do D3) passa enquanto
    nao for para mais longe deles: o job nunca trava (revisao 1 da fase D). Em nenhum passo o tamanho sai do teto
    numerico, nem com o rascunho gravado (revisao 2 da fase D);
  - a sangria do DA (M7b, D4; pergunta 5 do plano, "So o DA ajusta"): o elemento, ou o grupo, que o DA mexeu ou
    escalou pode passar da borda do quadro em qualquer lado; o quadro corta o que fica fora (sangria_do_da). O lado
    vira sangria do elemento naquele membro: o encaixe refeito nao o puxa de volta e a conferencia nao o marca como
    defeito. O texto e a marca nunca sangram. O elemento que o DA tira da borda em que o asset dele acaba no KV fica
    onde o DA o pos, com o tamanho dele, e a conferencia pede ajuste porque o corte aparece (corte_a_mostra, revisao 1
    da fase D). No alinhamento no quadro, o elemento preso a borda daquele lado fica fora da linha do grupo e anda
    junto (caixa_da_linha). O elemento levado inteiro para fora da peca nao sangra: pede ajuste (fora_da_peca,
    revisao 2 da fase D);
  - o piso diante da intencao do DA (M7b, D5; pergunta 10 do plano): a escala abaixo do piso da 133 ou a distancia
    menor que a da 135 com um elemento que o DA mexeu ou escalou e decisao dele. A previa a leva em decisoes_do_da, com
    o valor no texto, e nao em falhas; a tela a mostra como "Decisão do DA", nunca como "Pede ajuste". O elemento que
    o encaixe refeito tirou do lugar continua falha, e a validacao do motor continua devolvendo o formato. O piso que
    a versao de partida ja furava, e a distancia de caixas que se sobrepoem, continuam falha (revisao 1 da fase D);
  - depois de cada edicao, a intencao de alinhamento (168, revista pela 185): so o elemento que o DA acabou de mexer
    (ou o grupo dele) anda. A borda ou o centro dele que fica a menos de derivacao.alinhamento_intencao_tolerancia do
    lado maior da peca da linha de um vizinho encaixa nela (normalizar); com o vizinho com quem ja se alinhava no KV,
    volta para a linha do KV. Nenhum outro elemento sai do lugar, nem o que o DA mexeu antes: o produto alinhado com o
    bloco de texto no KV nao acompanha o bloco. O mexido preso a uma linha do quadro nao anda naquele eixo. Acima da
    tolerancia, a diferenca e intencao do DA. A previa e o "Salvar e seguir" refazem as edicoes uma a uma, cada uma
    com o alinhamento na hora dela (editar), cada uma a partir do que a tela mostrou. O vizinho de cuja linha a edicao
    tirou o mexido nao o puxa de volta, e o eixo em que ele nao andou nao encaixa (o alinhar na largura nao muda a
    altura). O mexido que divide agora uma linha que ja dividia no KV com um terceiro fica nela, e a linha mais perto
    vem primeiro, sem depender da ordem dos cliques (revisao 2 da fase D);
  - o encaixe de cada membro e refeito pelo solver do repositorio, com as caixas editadas como mestre sintetica (como a
    galeria faz com a variante), e o layout e conferido contra a mestre verdadeira (desdobra.derivacao.galeria);
  - o texto editado precisa de todos os caracteres na face do job que o desenha (a cobertura do cmap lida pelo filho
    das fontes; o processo principal nunca abre a fonte); a previa leva o texto novo com a face real, e as quebras
    sao refeitas pela pagina na largura da caixa, com a fonte carregada. O texto vale so na familia editada (171);
  - o elemento apagado sai de todos os membros, fica registrado com a origem do rascunho ('da', ou fixture_de_teste no
    modo de teste da tela) e deixa de reprovar o inventario (desdobra.derivacao.validacao, apagados);
  - a quebra de linha da familia (M7b, C3; decisoes-v1.md, 167 e 171): o pedido pode levar as quebras do rascunho da
    familia (quebras, o mesmo formato do rascunho); sem o campo, a familia nao tem quebra no rascunho, como a lista
    vazia (revisao do C). Quando elas diferem das do briefing, a previa mede o texto com a
    quebra nova (desdobra.derivacao.medida_quebras.medir, com o cache: so o texto que mudou vai ao Chromium) e deriva
    de novo os membros da familia com ela, como a derivacao vai fazer depois de "Salvar e seguir"; a previa e a
    derivacao gravada usam a mesma medida. A quebra fora de um espaco do texto de agora e recusada (como o rascunho).
    A previa leva os textos que o DA pode quebrar, com as posicoes (textos_da_quebra, o controle da quebra no palco,
    M7b, C4), e o texto editado sai no palco nas linhas da quebra da familia.
So previa, em memoria: nada aqui grava arquivo. As edicoes ficam no rascunho que a pagina grava (desdobra.tela.rascunho),
e "Confirmar familia" e um ato da janela (desdobra.tela.atos).
"""
import math
import time

from desdobra import limites

ACOES = ('mover', 'escalar', 'texto', 'apagar', 'alinhar')
ACOES_DO_GRUPO = ('mover', 'escalar', 'alinhar')  # M7b, D1 e D2: as acoes que levam a lista do grupo
# M7b, D2: o alinhamento no quadro do membro. alvo: (eixo, linha da caixa que encosta na mesma linha do quadro)
ALVOS = {'margem_esquerda': ('x', 'esquerda'), 'centro_horizontal': ('x', 'centro'), 'margem_direita': ('x', 'direita'),
         'topo': ('y', 'topo'), 'centro_vertical': ('y', 'meio'), 'base': ('y', 'base')}
REFERENCIAS = ('margem', 'area_segura')  # o quadro de cada membro: a margem dele ou a area segura dele
CAMPOS =('familia', 'versao', 'edicoes')
CAMPOS_OPCIONAIS = ('quebras',)  # M7b, C3: as quebras de linha do rascunho da familia
VIVAS_MAX = 8  # numero-neutro: familias com quebra nova guardadas na previa (a ultima mexida fica)
# as linhas de alinhamento de uma caixa [x0, y0, x1, y1]: (nome para o DA, indice, indice do outro lado para o centro)
LINHAS = {'x': (('esquerda', 0, None), ('centro', 0, 2), ('direita', 2, None)),  # numero-neutro: indices da caixa
          'y': (('topo', 1, None), ('meio', 1, 3), ('base', 3, None))}  # numero-neutro: indices da caixa
METADE = 0.5  # numero-neutro: o meio da caixa
IGUAL = 1e-6  # numero-neutro: folga numerica de duas linhas que ja estao no mesmo valor
# a folga relativa do tamanho nos limites: a pagina grava o fator em 6 casas (fracao), e a conta de varios fatores
# arredondados pode passar do limite por menos que isto
FOLGA_ESCALA = 1e-4  # numero-neutro: arredondamento das 6 casas da fracao do fator
POR_MS = 1000.0  # numero-neutro: segundos para milissegundos
CASAS_MS = 1  # numero-neutro: casas do tempo gasto
# o membro devolvido porque a quebra de linha da familia ficou sem medida (previa igual ao Salvar, M7b): o DA pode
# tirar a quebra no palco
TEXTO_QUEBRA_SEM_MEDIDA = ('A quebra de linha desta família ficou sem medida. Sem a medida, o desdobra não monta as '
                           'versões deste arquivo. Tire a quebra ou fale com a Trezion.')


def tolerancia(W, H):
    """A tolerancia da intencao de alinhamento, em px da peca W x H (proporcional ao lado maior)."""
    return float(limites.valor('derivacao.alinhamento_intencao_tolerancia')) * max(float(W), float(H))


def _linha(c, eixo, nome):
    for n, i, j in LINHAS[eixo]:
        if n == nome:
            return c[i] if j is None else (c[i] + c[j]) * METADE
    raise KeyError(nome)


def _deslocar(c, eixo, d):
    if eixo == 'x':
        return [c[0] + d, c[1], c[2] + d, c[3]]
    return [c[0], c[1] + d, c[2], c[3] + d]


# ------------------------------------------------------------------ as edicoes em proporcao
def membros(ed):
    """Os elementos que a edicao mexe: a lista do grupo (elementos, M7b, D1) ou o elemento so."""
    if ed['acao'] in ACOES_DO_GRUPO and ed.get('elementos'):
        return list(ed['elementos'])
    return [ed['elemento']]


def grupos(edicoes):
    """Os grupos que ficam depois das edicoes (M7b, D1): os elementos que andaram juntos na ultima edicao de mover ou
    escalar de cada um, na ordem da lista dela. O elemento mexido sozinho depois sai do grupo, o apagado tambem, e o
    grupo de um elemento so deixa de ser grupo. Vale igual em todo formato (so le as edicoes)."""
    ultima, apagados = {}, set()
    for n, ed in enumerate(edicoes):
        if ed['acao'] == 'apagar':
            apagados.add(ed['elemento'])
            ultima.pop(ed['elemento'], None)
        elif ed['acao'] in ACOES_DO_GRUPO:
            for eid in membros(ed):
                if eid not in apagados:
                    ultima[eid] = (n, membros(ed).index(eid))
    por_edicao = {}
    for eid, (n, i) in ultima.items():
        por_edicao.setdefault(n, []).append((i, eid))
    return [[eid for _i, eid in sorted(v)] for _n, v in sorted(por_edicao.items()) if len(v) > 1]


def limites_da_escala():
    """(menor, maior) tamanho que o DA da a um elemento (M7b, D3), em fator sobre o tamanho antes das edicoes."""
    return float(limites.valor('tela.escala_min')), float(limites.valor('tela.escala_max'))


def escalas(edicoes):
    """O tamanho de cada elemento escalado pelo DA (M7b, D3): {id: produto dos fatores das edicoes de escalar que o
    levam, sozinho ou no grupo}, sobre o tamanho antes das edicoes. O elemento sem escalar fica de fora (1, 100%), e o
    apagado sai. Vale igual em todo formato (so le as edicoes)."""
    tamanho = {}
    for ed in edicoes:
        if ed['acao'] == 'apagar':
            tamanho.pop(ed['elemento'], None)
        elif ed['acao'] == 'escalar':
            for eid in membros(ed):
                tamanho[eid] = tamanho.get(eid, 1.0) * float(ed['fator'])
    return tamanho


def _passos(edicoes):
    """{id: [tamanho depois de cada edicao de escalar que o leva]} (escalas, passo a passo); o apagado recomeca."""
    passos, tamanho = {}, {}
    for ed in edicoes:
        if ed['acao'] == 'apagar':
            tamanho.pop(ed['elemento'], None)
        elif ed['acao'] == 'escalar':
            for eid in membros(ed):
                tamanho[eid] = tamanho.get(eid, 1.0) * float(ed['fator'])
                passos.setdefault(eid, []).append(tamanho[eid])
    return passos


def escala_fora(edicoes, antes=None):
    """Os elementos, ordenados pelo id, cujo tamanho depois das edicoes passa dos limites da escala (M7b, D3), com a
    folga do arredondamento (FOLGA_ESCALA). antes: as edicoes gravadas da mesma familia (revisao 1 da fase D). O
    tamanho que elas ja tinham fora dos limites (o rascunho da tela de antes do D3, sem o limite acumulado) passa,
    enquanto o novo nao for para mais longe do mesmo limite: o job nunca trava, e o DA conserta pela tela. Conta o
    tamanho final, para o conserto que sai de fora dos limites passar. Revisao 2 da fase D: em nenhum passo o tamanho
    sai do teto, os limites esticados pela razao entre eles (de escala_min ao quadrado sobre escala_max a escala_max ao
    quadrado sobre escala_min), nem com o rascunho gravado: o par forjado que se cancela no fim (1e308 e 1e-308) levaria
    a caixa a infinito ou a um ponto, e a previa e a derivacao quebrariam."""
    menor, maior = limites_da_escala()
    baixo, alto = menor * (1 - FOLGA_ESCALA), maior * (1 + FOLGA_ESCALA)
    piso, teto = baixo * menor / maior, alto * maior / menor
    velho = escalas(antes or [])
    passos = _passos(edicoes)
    fora = []
    for eid, s in escalas(edicoes).items():
        if not all(math.isfinite(p) and piso <= p <= teto for p in passos.get(eid, ())):
            fora.append(eid)
            continue
        if baixo <= s <= alto:
            continue
        v = velho.get(eid)
        if v is not None and ((s < baixo and v < baixo and s >= v * (1 - FOLGA_ESCALA)) or
                              (s > alto and v > alto and s <= v * (1 + FOLGA_ESCALA))):
            continue  # ja estava gravado fora do limite, e nao foi para mais longe
        fora.append(eid)
    return sorted(fora)


def ids_conferem(edicoes, ids):
    """As edicoes citam so elementos que existem (ids, os do KV que a tela mostra), e o grupo (M7b, D1) comeca pelo
    elemento da edicao. A previa e o rascunho conferem igual (revisao 1 da fase D): o rascunho nunca guarda a edicao
    que a previa recusa. ids None: so a ordem do grupo."""
    for e in edicoes:
        lista = e.get('elementos')
        if lista is not None and lista[0] != e['elemento']:
            return False
        if ids is not None and not ({e['elemento']} | set(lista or ())) <= set(ids):
            return False
    return True


def intencoes(edicoes):
    """Os alinhamentos no quadro que ficam valendo depois das edicoes (M7b, D2), na ordem delas: [{'elementos',
    'eixo', 'alvo', 'referencia'}]. A ultima edicao vence: o elemento movido naquele eixo, escalado ou apagado depois
    sai da intencao, e o alinhamento novo no mesmo eixo vale sobre o de antes. Vale igual em todo formato (so le as
    edicoes); a derivacao a segura contra a intencao de alinhamento (168) e o encaixe refeito (firmar)."""
    vale = {}
    for n, ed in enumerate(edicoes):
        acao = ed['acao']
        if acao == 'alinhar':
            eixo = ALVOS[ed['alvo']][0]
            for eid in membros(ed):
                vale[(eid, eixo)] = n
        elif acao == 'mover':
            for eid in membros(ed):
                for eixo, d in (('x', ed['dx']), ('y', ed['dy'])):
                    if float(d):
                        vale.pop((eid, eixo), None)
        elif acao in ('escalar', 'apagar'):
            for eid in membros(ed):
                for eixo in ('x', 'y'):
                    vale.pop((eid, eixo), None)
    por_edicao = {}
    for (eid, _eixo), n in vale.items():
        por_edicao.setdefault(n, set()).add(eid)
    saida = []
    for n in sorted(por_edicao):
        ed = edicoes[n]
        saida.append({'elementos': [k for k in membros(ed) if k in por_edicao[n]], 'eixo': ALVOS[ed['alvo']][0],
                      'alvo': ed['alvo'], 'referencia': ed['referencia']})
    return saida


def firmar(caixas, intencoes_, quadros, W, H, borda=()):
    """Os alinhamentos no quadro (intencoes) de novo, depois do encaixe refeito pelo solver (M7b, D2): cada intencao
    leva os elementos dela que o formato tem, juntos, ate a linha do quadro do membro; o solver nunca tira o bloco do
    lugar que o DA pediu. A linha do grupo e a de caixa_da_linha (borda: {(id, lado)} do asset cortado na borda do
    KV). Devolve (caixas, no_quadro [{'elementos', 'eixo', 'alvo', 'referencia', 'valor'}])."""
    caixas = {k: list(v) for k, v in caixas.items()}
    feitos = []
    for i in intencoes_:
        ids = [k for k in i['elementos'] if k in caixas]
        if not ids:
            continue
        q = quadro_da_referencia(quadros, i['referencia'], W, H)
        eixo, d, valor = no_quadro(caixa_da_linha(caixas, ids, i['alvo'], W, H, borda), i['alvo'], q)
        if abs(d) > IGUAL:
            for k in ids:
                caixas[k] = _deslocar(caixas[k], eixo, d)
        feitos.append({'elementos': ids, 'eixo': eixo, 'alvo': i['alvo'], 'referencia': i['referencia'],
                       'valor': round(valor, 4)})  # numero-neutro: casas do px
    return caixas, feitos


def _uniao(cs):
    return [min(c[0] for c in cs), min(c[1] for c in cs), max(c[2] for c in cs), max(c[3] for c in cs)]


LADO_DO_ALVO = {'esquerda': 'esq', 'topo': 'topo', 'direita': 'dir', 'base': 'base'}


def caixa_da_linha(caixas, ids, alvo, W, H, borda=()):
    """A caixa que da a linha do grupo no alinhamento no quadro (revisao 1 da fase D do M7b). No alvo de borda (as
    margens, o topo e a base), o elemento preso a borda da peca daquele lado fica fora da conta e anda junto: o que
    passa da borda agora (o que sangra) e o que tem o asset cortado naquela borda do KV (borda: {(id, lado)}). Assim o
    packshot vai para a base pela linha dos produtos, e o circulo de tras continua passando da borda. Com todos presos
    a borda, e no centro, conta o grupo inteiro. Revisao 2 da fase D: o elemento que so encosta na borda (o que o
    alinhamento acabou de levar ate ela, quando a linha do quadro e a propria borda da peca) continua na conta; senao
    o segundo clique, ou o alinhamento firmado depois do solver, levaria o grupo para fora da peca."""
    _eixo, nome = ALVOS[alvo]
    lado = LADO_DO_ALVO.get(nome)
    cs = [caixas[k] for k in ids]
    if lado is None:
        return _uniao(cs)
    passa = {'esq': lambda c: c[0] < -IGUAL, 'topo': lambda c: c[1] < -IGUAL, 'dir': lambda c: c[2] > float(W) + IGUAL,
             'base': lambda c: c[3] > float(H) + IGUAL}[lado]
    dentro = [caixas[k] for k in ids if not passa(caixas[k]) and (k, lado) not in borda]
    return _uniao(dentro or cs)


def quadro_da_referencia(quadros, referencia, W, H):
    """O quadro do membro para o alinhamento (M7b, D2): a margem ou a area segura dele; sem quadros, a peca inteira."""
    q = (quadros or {}).get(referencia)
    return [float(v) for v in q] if q else [0.0, 0.0, float(W), float(H)]


def no_quadro(u, alvo, quadro):
    """(eixo, deslocamento, valor) que leva a linha do alvo da caixa u a mesma linha do quadro (M7b, D2)."""
    eixo, nome = ALVOS[alvo]
    valor = _linha(quadro, eixo, nome)
    return eixo, valor - _linha(u, eixo, nome), valor


def aplicar(caixas, edicoes, W, H, quadros=None, borda=()):
    """As edicoes do DA no formato W x H. caixas: {id: [x0, y0, x1, y1]}. Mover anda dx x W e dy x H; escalar multiplica
    a caixa pelo fator em volta do ponto fixo (fx, fy, fracoes da caixa; o meio sem eles). No grupo (elementos, M7b,
    D1), todos andam igual, e o ponto fixo e a fracao da caixa que junta o grupo no formato (sem o elemento apagado nem
    o que o formato nao tem). Alinhar (M7b, D2) desloca o elemento, ou o grupo inteiro, no eixo do alvo, ate a linha da
    caixa que junta o grupo encostar na mesma linha do quadro do membro (quadros: {'margem', 'area_segura'}: caixas do
    formato; sem ele, a peca inteira); o tamanho nao muda. No alvo de borda, o elemento preso a borda da peca daquele
    lado fica fora da linha e anda junto (caixa_da_linha; borda: {(id, lado)} do asset cortado na borda do KV, revisao
    1 da fase D). Devolve (caixas, apagados, textos {id: texto}, mexidos na
    ordem, o ultimo por ultimo)."""
    caixas = {k: [float(x) for x in v] for k, v in caixas.items()}
    apagados, textos, mexidos = [], {}, []
    for ed in edicoes:
        eid, acao = ed['elemento'], ed['acao']
        if acao in ('apagar', 'texto'):
            if eid not in caixas or eid in apagados:
                continue
            if acao == 'apagar':
                apagados.append(eid)
            else:
                textos[eid] = ed['texto']
            continue
        ids = [k for k in membros(ed) if k in caixas and k not in apagados]
        if not ids:
            continue
        if acao == 'mover':
            dx, dy = float(ed['dx']) * W, float(ed['dy']) * H
            for k in ids:
                c = caixas[k]
                caixas[k] = [c[0] + dx, c[1] + dy, c[2] + dx, c[3] + dy]
        elif acao == 'alinhar':
            q = quadro_da_referencia(quadros, ed['referencia'], W, H)
            eixo, d, _v = no_quadro(caixa_da_linha(caixas, ids, ed['alvo'], W, H, borda), ed['alvo'], q)
            for k in ids:
                caixas[k] = _deslocar(caixas[k], eixo, d)
        else:
            f = float(ed['fator'])
            u = _uniao([caixas[k] for k in ids])
            px = u[0] + float(ed.get('fx', METADE)) * (u[2] - u[0])
            py = u[1] + float(ed.get('fy', METADE)) * (u[3] - u[1])
            for k in ids:
                c = caixas[k]
                caixas[k] = [px + (c[0] - px) * f, py + (c[1] - py) * f, px + (c[2] - px) * f, py + (c[3] - py) * f]
        for k in ids:
            if k in mexidos:
                mexidos.remove(k)
            mexidos.append(k)
    for eid in apagados:
        caixas.pop(eid, None)
        textos.pop(eid, None)
        if eid in mexidos:
            mexidos.remove(eid)
    return caixas, apagados, textos, mexidos


def sangria_do_da(caixas, mexidos, W, H, tol, sem_sangria=()):
    """Os lados em que o DA deixou o elemento passar da borda da peca W x H (M7b, D4): {id: [lados, na ordem esq,
    topo, dir, base]} de cada elemento mexido (mover, escalar ou alinhar, sozinho ou no grupo) cuja caixa passa da
    borda por mais que tol. O quadro corta o que fica fora, e o lado vira sangria por decisao do DA. O texto e a marca
    (sem_sangria: os ids deles) nunca sangram: continuam dentro do quadro, como no KV. Revisao 2 da fase D: o elemento
    que fica inteiro fora da peca nao sangra (fora_da_peca): sangrar e passar uma parte pela borda, e o que some da
    peca pede ajuste. A derivacao passa tol pequeno (a folga numerica): o solver prende sem folga o lado que nao
    sangra, e o elemento que passa da borda por menos que a tolerancia do enquadramento tambem fica onde o DA o pos."""
    saida = {}
    fora = set(fora_da_peca(caixas, mexidos, W, H, tol))
    for k in mexidos:
        if k not in caixas or k in sem_sangria or k in fora:
            continue
        c = caixas[k]
        lados = [lado for lado, fora in (('esq', c[0] < -tol), ('topo', c[1] < -tol), ('dir', c[2] > W + tol),
                                         ('base', c[3] > H + tol)) if fora]
        if lados:
            saida[k] = lados
    return saida


def fora_da_peca(caixas, mexidos, W, H, tol):
    """Os elementos mexidos pelo DA, na ordem, que ficam inteiros fora da peca W x H (revisao 2 da fase D): nada da
    caixa aparece no quadro, a menos de tol. Nao e sangria: a conferencia pede ajuste e diz que, para tirar o elemento,
    o caminho e Apagar."""
    return [k for k in mexidos if k in caixas and (
        caixas[k][2] <= tol or caixas[k][3] <= tol or caixas[k][0] >= W - tol or caixas[k][1] >= H - tol)]


def normalizar(caixas, mexidos, W, H, kv_caixas=None, kv_tamanho=None, grupos=(), acompanham=None, presos=(),
               antes=None):
    """A intencao de alinhamento (decisoes-v1.md, 168, revista pela 185) depois de uma edicao: so o elemento que o DA
    acabou de mexer anda (mexidos: os elementos daquela edicao, o elemento so ou o grupo dele). Em cada eixo, o par
    que ja divide uma linha fica; senao, o mexido encaixa na linha mais perto de um vizinho abaixo da tolerancia, so
    com deslocamento (o tamanho nao muda), um encaixe por elemento e eixo. Nenhum outro elemento sai do lugar: nem o
    que o DA nao mexeu, nem o que ele mexeu antes. Duas passadas: primeiro os vizinhos com quem o mexido ja estava
    alinhado no KV (o mexido volta para a linha do outro), depois os outros, ja com as posicoes da primeira; assim um
    encaixe do KV nunca e desfeito por outro e nao fica linha quase igual (revisao do M7a). O grupo (M7b, D1; grupos,
    as listas de ids) nunca se separa: os elementos do mesmo grupo nao se alinham entre si, e o elemento do grupo que
    encosta na linha de outro leva o grupo inteiro com ele, tambem os membros fora da conta do alinhamento
    (acompanham: {id: caixa}, os que nao sao de conteudo), num encaixe so por eixo. O mexido alinhado no quadro pelo
    DA (M7b, D2; presos: {(id, eixo)}, de intencoes) nunca sai da linha do quadro: naquele eixo nada anda. O mexido
    que divide agora, naquele eixo, uma linha que ja dividia no KV com um terceiro fica nela (revisao 2 da fase D),
    e os pares vao da linha mais perto para a mais longe, com o empate pelos ids, para o resultado nao depender da
    ordem dos cliques no grupo. antes ({id: caixa antes da edicao}, de editar): a linha do mexido so encaixa na do
    vizinho que fica a frente de onde a edicao o tirou, no sentido em que ela o levou; a linha que ele deixou para
    tras nao o puxa de volta (o toque da seta sai da linha) e o eixo em que ele nao andou nao encaixa (o arraste so na
    vertical nao muda o x, o alinhar na largura nao muda a altura). Sem antes, qualquer sentido. Devolve (caixas, com
    as de acompanham; alinhados [{'elementos': [o que andou, o que ficou], 'eixo', 'linha', 'valor'}])."""
    tol = tolerancia(W, H)
    presos = set(presos)
    tol_kv = tolerancia(*kv_tamanho) if kv_tamanho else None
    caixas = {k: list(v) for k, v in caixas.items()}
    junto = {k: list(v) for k, v in (acompanham or {}).items() if k not in caixas}
    grupo_de = {eid: tuple(g) for g in grupos for eid in g}
    # o que anda nesta edicao: o mexido e o grupo dele; o resto fica (decisao 185)
    andam = {x for m in mexidos for x in (grupo_de.get(m) or (m,))} | set(mexidos)
    feitos, alinhados = set(), []

    def a_frente(m, o, eixo, n):
        # a linha do vizinho fica a frente de onde a edicao tirou o mexido (antes): a linha que ele deixou para tras
        # nao o puxa de volta, e o eixo em que ele nao andou nao encaixa (decisao 185)
        if antes is None or m not in antes:
            return True
        v0 = _linha(antes[m], eixo, n)
        andou, falta = _linha(caixas[m], eixo, n) - v0, _linha(caixas[o], eixo, n) - v0
        return abs(andou) > IGUAL and abs(falta) > IGUAL and (andou > 0) == (falta > 0)

    def perto_de(m, o, eixo):
        nomes = [n for n, _i, _j in LINHAS[eixo]]
        difs = [(abs(_linha(caixas[m], eixo, n) - _linha(caixas[o], eixo, n)), n) for n in nomes]
        if any(d <= IGUAL for d, _n in difs):
            return []
        return [(d, n) for d, n in difs if d <= tol and a_frente(m, o, eixo, n)]

    def preso(k, eixo):
        return any((x, eixo) in presos for x in grupo_de.get(k) or (k,))

    def encaixar(anda, fica, eixo, nome):
        # o mexido alinhado no quadro fica na linha do quadro (M7b, D2): naquele eixo nada anda (decisao 185)
        if preso(anda, eixo) or (anda, eixo) in feitos:
            return
        valor = _linha(caixas[fica], eixo, nome)
        d = valor - _linha(caixas[anda], eixo, nome)
        # o grupo do elemento anda inteiro com ele (M7b, D1)
        for k in grupo_de.get(anda) or (anda,):
            for onde in (caixas, junto):
                if k in onde:
                    onde[k] = _deslocar(onde[k], eixo, d)
            feitos.add((k, eixo))
        alinhados.append({'elementos': [anda, fica], 'eixo': eixo, 'linha': nome, 'valor': round(valor, 4)})  # numero-neutro: casas do px

    def do_kv(m, o, eixo, perto):
        if not (kv_caixas and tol_kv is not None and m in kv_caixas and o in kv_caixas):
            return []
        return [(d, n) for d, n in perto
                if abs(_linha(kv_caixas[m], eixo, n) - _linha(kv_caixas[o], eixo, n)) <= tol_kv]

    def linha_do_kv(k, eixo, fica):
        # o mexido (ou o grupo dele) divide agora, naquele eixo, uma linha que ja dividia no KV com outro elemento
        # (revisao 2 da fase D): encaixar no vizinho o tiraria do alinhamento do KV, que vale (168)
        if not (kv_caixas and tol_kv is not None):
            return False
        meus = grupo_de.get(k) or (k,)
        for g in meus:
            if g not in caixas or g not in kv_caixas:
                continue
            for x in caixas:
                if x == fica or x in meus or x not in kv_caixas:
                    continue
                for n, _i, _j in LINHAS[eixo]:
                    if abs(_linha(caixas[g], eixo, n) - _linha(caixas[x], eixo, n)) <= IGUAL and \
                            abs(_linha(kv_caixas[g], eixo, n) - _linha(kv_caixas[x], eixo, n)) <= tol_kv:
                        return True
        return False

    def mais_perto_primeiro(lista):
        # a linha mais perto primeiro, e o empate pelos ids: o resultado nunca depende da ordem dos cliques no grupo
        # (revisao 2 da fase D)
        cands = []
        for m, o, eixo in pares:
            perto = lista(m, o, eixo)
            if perto:
                d, nome = min(perto)
                cands.append((d, eixo, nome, sorted((m, o)), m, o))
        return [(m, o, eixo) for _d, eixo, _n, _ids, m, o in sorted(cands)]

    # o mexido com cada vizinho que nao anda com ele; os do mesmo grupo ficam como o DA os deixou (M7b, D1)
    pares = [(m, o, eixo) for m in sorted(set(mexidos)) if m in caixas for o in sorted(caixas)
             if o not in andam for eixo in ('x', 'y')]
    # 1a passada: o alinhamento do KV vence, o mexido volta para a linha do outro
    for m, o, eixo in mais_perto_primeiro(lambda m, o, eixo: do_kv(m, o, eixo, perto_de(m, o, eixo))):
        no_kv = do_kv(m, o, eixo, perto_de(m, o, eixo))
        if no_kv:
            encaixar(m, o, eixo, min(no_kv)[1])
    # 2a passada: o resto, com as posicoes da primeira; o mexido encaixa na linha do vizinho. O mexido que dividia uma
    # linha do KV com um terceiro e continua nela nao anda
    for m, o, eixo in mais_perto_primeiro(
            lambda m, o, eixo: [] if do_kv(m, o, eixo, perto_de(m, o, eixo)) else perto_de(m, o, eixo)):
        perto = perto_de(m, o, eixo)
        if not perto or do_kv(m, o, eixo, perto) or linha_do_kv(m, eixo, o):
            continue
        encaixar(m, o, eixo, min(perto)[1])
    caixas.update(junto)
    return caixas, alinhados


def editar(caixas, edicoes, W, H, quadros=None, borda=(), conteudo=None, kv_caixas=None, kv_tamanho=None):
    """As edicoes do DA no formato W x H, uma a uma, cada uma com a intencao de alinhamento na hora dela (decisao
    185): aplicar a edicao e normalizar so o que ela mexeu (o elemento ou o grupo dele), com os grupos e os
    alinhamentos no quadro que valem ate ela. Cada edicao parte das caixas que a tela mostra depois da edicao de
    antes, ja com o encaixe dela, como tela.js mede o arraste, o Tamanho e o alinhar: o elemento solta onde o DA o
    soltou, o grupo anda inteiro como o DA o via e o canto fixo do Tamanho fica no lugar. A edicao depois nunca tira
    do lugar o que o DA mexeu antes nem o que ele nao mexeu, e o rascunho refeito inteiro (a previa e o "Salvar e
    seguir") da o mesmo layout que a tela mostrou edicao a edicao. O mexido so encaixa na linha que fica a frente de
    onde a edicao o tirou (normalizar, antes): o toque de 1 px da seta anda 1 px nos dois sentidos, e o eixo em que
    ele nao andou nao muda. A edicao de texto e a de apagar nao alinham nada. conteudo: os ids que entram na conta do
    alinhamento (os de conteudo; None: todos); o elemento do grupo fora dela anda junto com o grupo. Devolve (caixas,
    apagados, textos {id: texto}, mexidos na ordem, o ultimo por ultimo, alinhados da ultima edicao: vazio quando
    ela nao mexeu em caixa)."""
    atual = {k: [float(x) for x in v] for k, v in caixas.items()}
    apagados, textos, mexidos, alinhados = [], {}, [], []
    for n, uma in enumerate(edicoes):
        antes = atual
        atual, ap, tx, mx = aplicar(atual, [uma], W, H, quadros, borda)
        textos.update(tx)
        for k in ap:
            apagados.append(k)
            textos.pop(k, None)
            if k in mexidos:
                mexidos.remove(k)
        for k in mx:
            if k in mexidos:
                mexidos.remove(k)
            mexidos.append(k)
        alinhados = []
        if not mx:
            continue
        ate_aqui = edicoes[:n + 1]
        gs = grupos(ate_aqui)
        so = {k: v for k, v in atual.items() if conteudo is None or k in conteudo}
        junto = {k: atual[k] for g in gs for k in g if k in atual and k not in so}
        presos = {(k, i['eixo']) for i in intencoes(ate_aqui) for k in i['elementos']}
        norm, alinhados = normalizar(so, mx, W, H, kv_caixas, kv_tamanho, grupos=gs, acompanham=junto, presos=presos,
                                     antes={k: antes[k] for k in mx if k in antes})
        atual.update(norm)
    return atual, apagados, textos, mexidos, alinhados


# ------------------------------------------------------------------ texto
def caracteres_que_faltam(texto, face, caixa_alta=False):
    """Os caracteres com tinta do texto que a face nao cobre, em ordem e sem repetir."""
    from desdobra.fontes import casamento
    alvo = texto.upper() if caixa_alta else texto
    vistos = []
    for ch in alvo:
        if casamento.tem_tinta(ch) and not casamento.cobre(face, ord(ch)) and ch not in vistos:
            vistos.append(ch)
    return vistos


def _texto_da_recusa(faltam):
    lista = ', '.join(faltam)
    if len(faltam) == 1:
        return 'A fonte deste texto não tem o caractere %s. Troque o caractere ou envie a fonte que o tenha.' % lista
    return 'A fonte deste texto não tem os caracteres %s. Troque esses caracteres ou envie a fonte que os tenha.' % lista


def trocar_texto(palco, elemento, texto, quebra=None):
    """As pecas de texto do elemento no palco levam o texto novo, linha a linha (as quebras do DA), com o estilo do
    primeiro trecho (face, cor, corpo e tracking ja na escala do formato); a pagina refaz as quebras na largura da
    caixa com a fonte real. quebra: a quebra de linha da familia no texto (o item do rascunho, M7b, C4): as linhas
    juntadas e as inseridas, como o render desenha (desdobra.derivacao.quebras.linhas_do_editado)."""
    from desdobra.derivacao import quebras as mq
    if quebra is not None:
        linhas = mq.linhas_do_editado(texto, quebra['manter'], quebra['inseridas'])
    else:
        linhas = texto.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    for p in palco['pecas']:
        if p.get('elemento') != elemento or p.get('tipo') != 'texto' or not p.get('linhas'):
            continue
        t0 = p['linhas'][0]['trechos'][0]
        ent = next((ln['entrelinha'] for ln in p['linhas'] if ln.get('entrelinha')), None)
        p['linhas'] = [{'trechos': [dict(t0, texto=ln)], 'entrelinha': ent} for ln in linhas]
        p['texto_editado'] = True
        p['modo'] = 'texto'
    return palco


# ------------------------------------------------------------------ a familia
class Editor:
    """A previa da edicao por familia, para a rota POST /api/familia/previa do servidor da tela.

    ctx, kv: o contexto e a mestre da derivacao; laudo e base: os do palco (desdobra.tela.estado.pecas_base);
    derivados: {id do formato: derivacao/1 em memoria}; brutos: {id do formato: {id da versao: variante do motor}};
    familias: {id da familia: [ids dos formatos membros]}; faces: as faces servidas do job (com o cmap)."""

    def __init__(self, ctx, kv, laudo, base, derivados, brutos, familias, faces, *, specs, arquivo_specs, params):
        from desdobra.derivacao import solver as mod_solver
        from desdobra.tela import estado
        self.ctx, self.kv, self.laudo, self.base = ctx, kv, laudo, base
        self.derivados, self.brutos, self.familias = derivados, brutos, familias
        self.faces = {f['id']: f for f in faces}
        self.kw = {'specs': specs, 'arquivo_specs': arquivo_specs, 'params': params}
        self.por_formato = {f['id']: f for f in ctx['briefing']['formatos']}
        self.kv_por_id = {e['id']: e for e in kv['elementos']}
        self.conteudo = [e['id'] for e in kv['elementos'] if mod_solver.conteudo(e)]
        self.kv_caixas = {e['id']: [float(x) for x in e['caixa']] for e in kv['elementos']}
        self.kv_tamanho = (float(kv['largura']), float(kv['altura']))
        self.nomes = estado._nomes(laudo)
        self._cf = {}
        # a familia com a quebra de linha do rascunho diferente da do briefing (M7b, C3): {chave: {'chave', 'ctx',
        # 'derivados', 'brutos'}}, a mais nova no fim
        self._vivas = {}

    def versoes(self, gid):
        return {vid for fid in self.familias.get(gid, ()) for vid in (self.brutos.get(fid) or {})}

    def _contexto(self, fid, viva=None):
        from desdobra.derivacao import galeria as mg
        from desdobra.derivacao import proposta
        ctx = viva['ctx'] if viva else self.ctx
        derivados = viva['derivados'] if viva else self.derivados
        chave = (fid, viva['chave'] if viva else None)
        if chave not in self._cf:
            # a mestre de onde o membro parte, com a quebra de linha da familia (a mesma da derivacao, M7b, C2)
            mestre = proposta.mestre_do_membro(ctx, self.kv, self.por_formato[fid], derivados.get(fid))
            self._cf[chave] = mg.contexto_do_formato(ctx, mestre, self.por_formato[fid], **self.kw)
        return self._cf[chave]

    def partida(self, fid, versao, viva=None):
        """Os elementos de onde o membro parte: a versao escolhida, a primeira sem falha ou a proposta derivada (a
        mesma regra da derivacao, desdobra.derivacao.proposta.partida). viva: a familia com a quebra nova (_viva)."""
        from desdobra.derivacao import proposta
        derivados, brutos = (viva['derivados'], viva['brutos']) if viva else (self.derivados, self.brutos)
        return proposta.partida(derivados.get(fid), brutos.get(fid), versao)

    def conferir(self, dados, antes=None):
        """True quando os dados da pagina seguem o formato da edicao (o mesmo esquema do rascunho), com o tamanho de
        cada elemento entre os limites da escala (escala_fora, M7b, D3; antes: as edicoes gravadas da familia no
        rascunho, revisao 1 da fase D). As quebras de linha, quando vem, seguem as regras do rascunho
        (desdobra.tela.rascunho._conferir_quebras)."""
        from desdobra import contratos
        from desdobra.tela import rascunho
        if not isinstance(dados, dict) or not set(CAMPOS) <= set(dados) <= set(CAMPOS + CAMPOS_OPCIONAIS):
            return False
        gid, versao, edicoes = dados['familia'], dados['versao'], dados['edicoes']
        if not isinstance(gid, str) or gid not in self.familias:
            return False
        if versao is not None and (not isinstance(versao, str) or versao not in self.versoes(gid)):
            return False
        familia = {'versao': versao, 'confirmada': False, 'edicoes': edicoes}
        if 'quebras' in dados:
            familia['quebras'] = dados['quebras']
        prova = {'esquema': rascunho.ESQUEMA, 'job_id': '0' * 32, 'laudo_sha256': '0' * 64,  # numero-neutro: tamanhos dos ids
                 'origem': 'rascunho', 'atualizado_em': '2026-01-01T00:00:00', 'familias': {gid: familia}}
        try:
            contratos.validar(prova, rascunho.ESQUEMA)
        except contratos.ErroContrato:
            return False
        # todos os elementos no KV, e o grupo (M7b, D1) com o elemento da edicao primeiro
        if not ids_conferem(edicoes, self.kv_por_id):
            return False
        # o tamanho de cada elemento entre os limites da escala (M7b, D3); o que o rascunho gravado ja tinha fora
        # deles passa (antes, revisao 1 da fase D)
        if escala_fora(edicoes, antes):
            return False
        return self._quebras_conferem(edicoes, dados.get('quebras') or [])

    def _quebras_conferem(self, edicoes, quebras):
        """Cada quebra num texto do elemento que ela cita, uma por texto, com os indices e as posicoes no texto de
        agora (o do KV, ou o editado pelo DA nas edicoes da familia, decisoes-v1.md, 171)."""
        from desdobra.briefing import modelo as mb
        from desdobra.derivacao import quebras as mq
        camadas = mb.camadas_do_laudo(self.ctx['laudo'])
        vistos = set()
        for q in quebras:
            el, c = self.kv_por_id.get(q['elemento']), camadas.get(q['layer_id'])
            if el is None or q['layer_id'] not in el['layer_ids'] or q['layer_id'] in vistos or c is None or \
                    c.get('tipo') != 'texto':
                return False
            vistos.add(q['layer_id'])
            if mq.conferir_da_familia(c, q['manter'], q['inseridas'], mq.texto_editado(edicoes, q['elemento'])):
                return False
        return True

    def _viva(self, gid, quebras, edicoes, origem):
        """A familia com as quebras de linha do rascunho (M7b, C3), ou None quando elas sao as do briefing (quebras
        None: as do briefing, sem conferir; a previa manda a lista, vazia sem quebra). O briefing em memoria troca as
        quebras da familia pelas do rascunho e leva as edicoes dela (a derivacao so le delas qual texto foi editado: o
        texto editado nao tem medida); a medida vem de
        desdobra.derivacao.medida_quebras.medir, com o cache, so dos textos do KV com quebra; os membros sao derivados
        de novo com ela, e os devolvidos que partem da galeria (desdobra.derivacao.proposta.usa_galeria) ganham a
        galeria de novo, como a tela monta na abertura (desdobra.tela.estado.galerias). Guardada pela chave das
        quebras: a proxima edicao na familia parte dela."""
        import json

        from desdobra.briefing import modelo as mb
        from desdobra.briefing import salvar
        from desdobra.derivacao import medida_quebras
        from desdobra.derivacao import nucleo as nd
        from desdobra.derivacao import proposta
        from desdobra.derivacao import quebras as mq
        from desdobra.job import nucleo
        if quebras is None:
            return None
        b = self.ctx['briefing']
        fids = list(self.familias[gid])
        antes = [q for q in b.get('quebras_por_familia') or []
                 if q.get('familia') is not None and set(q.get('formatos') or ()) & set(fids)]
        tipo = origem if origem in (mb.ORIGEM_DA, mb.ORIGEM_FIXTURE) else mb.ORIGEM_DA
        novas = salvar.quebras_da_familia(gid, fids, {'quebras': quebras}, tipo)
        editados = sorted({q['elemento'] for q in quebras if mq.texto_editado(edicoes, q['elemento']) is not None})
        if _assinatura(novas) == _assinatura(antes) and not editados:
            return None
        chave = json.dumps([gid, _assinatura(novas), editados])
        if chave in self._vivas:
            viva = self._vivas.pop(chave)
            self._vivas[chave] = viva
            return viva
        novo = dict(b, quebras_por_familia=[q for q in b.get('quebras_por_familia') or [] if q not in antes] + novas)
        novo['composicoes'] = [c for c in b.get('composicoes') or [] if not set(c['formatos']) & set(fids)] + [
            {'familia': gid, 'formatos': fids, 'versao': None, 'edicoes': list(edicoes), 'confirmada': False,
             'confirmacao': None}]
        a_medir = [n for n, q in zip(novas, quebras) if q['elemento'] not in editados]
        medidas = dict(self.ctx.get('medidas_quebras') or {})
        if a_medir and self.ctx.get('pasta') is not None:
            pasta = self.ctx['pasta']
            medidas.update(medida_quebras.medir(pasta, self.ctx['laudo'], {'quebras_por_familia': a_medir},
                                                nucleo.ler_estado(pasta)))
        # so as quebras e as composicoes mudam: as funcoes resolvidas do contexto continuam valendo
        ctx = dict(self.ctx, briefing=novo, medidas_quebras=medidas)
        derivados = dict(self.derivados)
        derivados.update(nd.derivar_em_memoria(ctx, so=fids, composicoes=False, **self.kw)['formatos'])
        # a galeria so dos membros que a derivacao tira dela, pela mesma regra (proposta.galeria_dos_devolvidos): o
        # membro que a quebra nova deixa sem galeria (tambem pela quebra sem medida) nao parte da versao de antes
        brutos = {f: v for f, v in self.brutos.items() if f not in fids}
        por, _mestre, sem_medida = proposta.galeria_dos_devolvidos(
            ctx, self.kv, derivados, [self.por_formato[f] for f in fids], **self.kw)
        brutos.update({f: {v['id']: v for _n, v in pares} for f, pares in por.items()})
        viva = {'chave': chave, 'ctx': ctx, 'derivados': derivados, 'brutos': brutos, 'sem_medida': sem_medida}
        self._vivas[chave] = viva
        while len(self._vivas) > VIVAS_MAX:
            velha = next(iter(self._vivas))
            del self._vivas[velha]
            self._cf = {k: v for k, v in self._cf.items() if k[1] != velha}
        return viva

    def _texto(self, eid, texto):
        """(texto aceito, recusa ou None) de uma edicao de texto no elemento."""
        el = self.kv_por_id[eid]
        textos = [lid for lid in el['layer_ids'] if (self.base.get(lid) or {}).get('linhas')]
        if len(textos) != 1:
            return None, 'Este elemento não tem um texto só para editar.'
        if not texto.strip():
            return None, 'O texto ficou vazio. Para tirar o elemento, use Apagar.'
        peca = self.base[textos[0]]
        face_id = next((t['face'] for ln in peca['linhas'] for t in ln['trechos'] if t['face']), None)
        face = self.faces.get(face_id)
        if face is None:
            return None, 'A fonte deste texto não está no job, e sem ela a tela não mostra o texto novo.'
        runs = (peca.get('_texto') or {}).get('runs') or [{}]
        faltam = caracteres_que_faltam(texto, face, runs[0].get('font_caps') in ('ALL_CAPS', 'SMALL_CAPS'))
        if faltam:
            return None, _texto_da_recusa(faltam)
        return texto, None

    def previa(self, dados, origem='da', antes=None):
        """{'familia', 'versao', 'membros': [{'formato', 'palco', 'falhas', 'decisoes_do_da', 'avisos',
        'validacoes_reprovadas', 'situacao', 'sangria_do_da': {id: [lados]}, 'quadro': {'margem', 'area_segura'}}],
        'apagados',
        'textos_editados', 'recusas', 'alinhados', 'no_quadro', 'textos_da_quebra', 'tempo_ms'}, ou None quando os
        dados nao seguem o formato. no_quadro: os alinhamentos no quadro que valem em cada membro, com o valor da linha
        (M7b, D2). sangria_do_da: os lados em que o DA deixou cada elemento passar da borda do membro (M7b, D4).
        decisoes_do_da: o piso de escala ou de distancia que o elemento mexido pelo DA fura, fora das falhas, com o
        valor no texto ({'codigo', 'texto', 'elementos', 'medidas'}; M7b, D5). antes: as edicoes gravadas da familia
        no rascunho (o servidor as le), para o tamanho que ja estava fora dos limites nunca travar a familia (revisao
        1 da fase D). O membro devolvido sem versao da galeria vem com situacao 'devolvido', o palco do formato
        devolvido e a falha que diz por que (_devolvido; previa igual ao Salvar, M7b). So previa: nada e gravado."""
        from desdobra.derivacao import proposta
        from desdobra.tela import estado
        if not self.conferir(dados, antes):
            return None
        inicio = time.perf_counter()
        gid, versao = dados['familia'], dados['versao']
        recusas, aceitas = [], []
        for e in dados['edicoes']:
            if e['acao'] == 'texto':
                texto, recusa = self._texto(e['elemento'], e['texto'])
                if recusa is not None:
                    recusas.append({'elemento': e['elemento'], 'texto': recusa})
                    continue
                e = dict(e, texto=texto)
            aceitas.append(e)
        # a quebra de linha do rascunho diferente da do briefing: os membros partem da derivacao com ela (M7b, C3). O
        # pedido sem o campo e o rascunho sem quebra na familia: a previa nunca volta a quebra do briefing de antes,
        # que "Salvar e seguir" tira (revisao do C)
        quebras = dados.get('quebras') or []
        viva = self._viva(gid, quebras, aceitas, origem)
        # o texto editado no palco sai nas linhas da quebra da familia (M7b, C4)
        quebras_por_elemento = {q['elemento']: q for q in quebras}
        membros, apagados_fam, textos_fam, alinhados_fam, no_quadro_fam = [], [], {}, [], []
        for fid in self.familias[gid]:
            elementos = self.partida(fid, versao, viva)
            if elementos is None:
                # o membro devolvido sem versao da galeria fica devolvido, como o "Salvar e seguir" o grava
                membros.append(self._devolvido(fid, viva))
                continue
            cf = self._contexto(fid, viva)
            W, H = cf['W'], cf['H']
            # a mesma conta da derivacao da familia confirmada (desdobra.derivacao.proposta)
            lay = proposta.layout_do_membro(cf, elementos, aceitas, kv_por_id=self.kv_por_id, conteudo=self.conteudo,
                                            kv_caixas=self.kv_caixas, kv_tamanho=self.kv_tamanho)
            apagados, textos, alinhados = lay['apagados'], lay['textos'], lay['alinhados']
            falhas, avisos, reprovadas, falha = lay['falhas'], lay['avisos'], lay['reprovadas'], lay['falha_solver']
            els = lay['elementos']
            palco = estado.palco_da_variante(fid, W, H, {'elementos': els}, self.laudo, self.base)
            for eid, texto in textos.items():
                trocar_texto(palco, eid, texto, quebras_por_elemento.get(eid))
            # os quadros do membro para alinhar (M7b, D2): a margem dele e a area segura da folha, None sem ela
            seg = ((cf.get('areas') or {}).get('area_segura') or {}).get('caixa')
            membros.append({'formato': fid, 'palco': palco,
                            'falhas': [{'codigo': f['codigo'], 'texto': f['texto']} for f in falhas],
                            # o piso que o DA furou com a edicao dele (M7b, D5), com o valor no texto
                            'decisoes_do_da': [{'codigo': d['codigo'], 'texto': d['texto'],
                                                'elementos': list(d['elementos']),
                                                'medidas': dict(d.get('medidas') or {})}
                                               for d in lay['decisoes_do_da']],
                            'avisos': [{'codigo': a['codigo'], 'texto': a['texto']} for a in avisos],
                            'validacoes_reprovadas': reprovadas,
                            'situacao': 'proposta' if not falha else 'proposta_sem_solver',
                            'sangria_do_da': {k: list(v) for k, v in lay['sangria_do_da'].items()},
                            'quadro': {'margem': [round(v, 4) for v in lay['quadros']['margem']],  # numero-neutro: casas do px
                                       'area_segura': [round(float(v), 4) for v in seg] if seg else None}})  # numero-neutro: casas do px
            for k in apagados:
                if k not in apagados_fam:
                    apagados_fam.append(k)
            textos_fam.update(textos)
            alinhados_fam.extend(dict(a, formato=fid) for a in alinhados)
            no_quadro_fam.extend(dict(a, formato=fid) for a in lay['no_quadro'])
        nome = self._nome
        return {'familia': gid, 'versao': versao, 'membros': membros,
                'apagados': [{'elemento': k, 'nome': nome(k), 'origem': origem} for k in apagados_fam],
                'textos_editados': [{'elemento': k, 'nome': nome(k)} for k in textos_fam],
                'recusas': recusas, 'alinhados': alinhados_fam, 'no_quadro': no_quadro_fam,
                'textos_da_quebra': self._textos_da_quebra(aceitas),
                'tempo_ms': round((time.perf_counter() - inicio) * POR_MS, CASAS_MS)}

    def _devolvido(self, fid, viva=None):
        """O membro devolvido sem versao da galeria, como a derivacao da familia confirmada o grava (previa igual ao
        Salvar, M7b): o palco do formato devolvido, sem layout do desdobra, e a falha que diz por que. A falha e a
        quebra de linha sem medida quando ela tirou a galeria do membro (desdobra.derivacao.proposta.
        galeria_dos_devolvidos), e a frase da devolucao no resto."""
        from desdobra.derivacao import proposta
        from desdobra.tela import estado
        d = (viva['derivados'] if viva else self.derivados)[fid]
        W, H = d['formato']['composicao']
        if viva and viva.get('sem_medida') and proposta.usa_galeria(d):
            falha = {'codigo': 'quebra_sem_medida', 'texto': TEXTO_QUEBRA_SEM_MEDIDA}
        else:
            falha = {'codigo': 'formato_devolvido',
                     'texto': estado.texto_da_devolucao((d.get('devolucao') or {}).get('motivo'), 0)}
        return {'formato': fid, 'palco': estado.palco(d, self.kv, self.laudo, self.base), 'falhas': [falha],
                'decisoes_do_da': [], 'avisos': [], 'validacoes_reprovadas': [], 'situacao': 'devolvido',
                'sangria_do_da': {}, 'quadro': {'margem': [float(v) for v in (0, 0, W, H)], 'area_segura': None}}

    def _textos_da_quebra(self, edicoes):
        """Os textos que o DA pode quebrar na familia (M7b, C4), na ordem do KV: o elemento com um texto de ponto so
        (a caixa de paragrafo o render refaz na largura dela; o elemento apagado sai), com o texto de agora e as
        posicoes das quebras gravadas e dos espacos (desdobra.derivacao.quebras.texto_para_quebrar). A pagina monta
        o controle da quebra com eles; o texto do cliente vai a ela so por textContent."""
        from desdobra.briefing import modelo as mb
        from desdobra.derivacao import quebras as mq
        camadas = mb.camadas_do_laudo(self.ctx['laudo'])
        apagados = {e['elemento'] for e in edicoes if e['acao'] == 'apagar'}
        saida = []
        for e in self.kv['elementos']:
            textos = [lid for lid in e['layer_ids'] if (camadas.get(lid) or {}).get('tipo') == 'texto']
            if e['id'] in apagados or len(textos) != 1 or \
                    (camadas[textos[0]].get('texto') or {}).get('tipo_caixa') == 'paragrafo':
                continue
            editado = mq.texto_editado(edicoes, e['id'])
            saida.append(dict(mq.texto_para_quebrar(camadas[textos[0]], editado), elemento=e['id'],
                              layer_id=textos[0], editado=editado is not None))
        return saida

    def _nome(self, eid):
        e = self.kv_por_id[eid]
        return self.nomes.get(e.get('raiz')) or ''


def _assinatura(entradas):
    """As quebras de linha de familia (entradas de quebras_por_familia) sem a origem da decisao, em ordem: o texto, os
    indices que ficam, as posicoes inseridas, quem fez e a aprovacao."""
    return sorted([int(q['layer_id']), sorted(q['quebras']['valor']), sorted(q.get('inseridas') or ()),
                   q.get('origem'), bool(q.get('aprovada'))] for q in entradas)
