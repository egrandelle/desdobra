# -*- coding: utf-8 -*-
"""Passo 2 da tela, "Funcoes", e o passo "Design system" (M7a, fatia 3; decisoes-v1.md, 10, rotular por grupo de
29/10, 161 e 162; proposta do M7, secao 4, fatia a6a).

O DA da a funcao a um grupo do PSD (ela passa para as camadas de dentro) ou a uma camada (vale sobre a do grupo), aceita
ou inverte a sugestao da regra da decisao 10 nas camadas cobertas e, no Design system, escolhe a regra de escala e a
ancora de cada funcao usada (e de cada elemento indeterminado). Tudo fica no rascunho da tela (briefing/rascunho.json,
desdobra.tela.rascunho), salvo sozinho; nada disto e o briefing confirmado.

Regras:
  - nenhum campo tem valor inicial: as opcoes saem do esquema briefing/1 (opcoes), e a tela abre sem nada marcado;
  - a heranca e a do motor: o rascunho vira um briefing parcial (briefing_parcial) e a funcao de cada camada sai de
    desdobra.briefing.modelo.resolver, a mesma que layout, validacao e teste leem;
  - indeterminado pede a observacao do DA: o rascunho sem ela e recusado (conferir), e a tela nao o manda;
  - pendencias: o que ainda falta no passo 2 e no Design system, a lista que o "Faltam N" da tela mostra, uma por
    camada sem funcao, por coberta sem decisao e por funcao sem regra ou sem ancora;
  - decisoes_minimas: o menor conjunto de escolhas por grupo e por camada que reproduz uma rotulagem camada a camada
    (a conta da rotulagem por grupo, taxonomia-funcoes.md: de 112 para 82 decisoes no gabarito).

Funcao pura dos dados do laudo e do rascunho: nao abre PSD, fonte nem imagem.
"""
from desdobra import contratos
from desdobra.briefing import modelo as mb

ESQUEMA_BRIEFING = 'briefing/1'
CHAVES_DO_PASSO = ('funcoes', 'cobertas', 'design', 'design_camadas')
ORIGEM = {'tipo': 'da', 'ref': 'rascunho da tela'}


def _sem_nulo(valores):
    return [v for v in valores if v is not None]


def opcoes():
    """As opcoes de cada campo do passo 2 e do Design system, lidas do esquema briefing/1 (a tela nunca inventa
    opcao nem valor padrao): funcoes (com a classe e se pede geometria), regras de escala, ancora x, ancora y e a
    decisao das cobertas."""
    esq = contratos.carregar_esquema(ESQUEMA_BRIEFING)
    props = esq['properties']

    def valores(no):
        return _sem_nulo(no['allOf'][1]['properties']['valor']['enum'])
    ancora = props['ancoras']['items']['properties']
    return {'funcoes': [{'id': f, 'classe': mb.CLASSES.get(f), 'geometria': f not in mb.SEM_GEOMETRIA}
                        for f in esq['$defs']['funcao']['enum']],
            'regras': list(esq['$defs']['regra']['enum']),
            'ancora_x': valores(ancora['x']), 'ancora_y': valores(ancora['y']),
            'cobertas': valores(props['cobertas']['items']['properties']['decisao'])}


def nos(laudo, quadro=None):
    """Os grupos e as camadas do passo 2, na ordem do painel do Photoshop (de cima para baixo): [{'camada', 'nome',
    'tipo', 'pai', 'nivel', 'folha', 'coberta'}]. folha: camada desenhavel (precisa de funcao); grupo: so passa a
    funcao. coberta: a sugestao da regra da decisao 10 ({'sugestao': funcao ou None}) na camada coberta no KV, que
    nunca herda a funcao do grupo."""
    camadas = mb.camadas_do_laudo(laudo)
    usados = set()
    for lid, c in camadas.items():
        if mb.desenhavel(c) and mb.no_escopo(c, quadro):
            usados.add(lid)
            usados.update(x for x in c.get('caminho_ids') or [] if x in camadas)
    por_pai = {}
    for c in reversed(laudo['camadas']):  # o painel: de cima para baixo, o grupo antes das camadas de dentro
        lid = c['identidade']['layer_id']
        if lid not in usados:
            continue
        folha = c.get('tipo') not in mb.TIPOS_SEM_DESENHO
        cob = (c.get('geometria') or {}).get('coberta_no_kv') or {}
        coberta = None
        if folha and cob.get('coberta'):
            coberta = {'sugestao': (cob.get('sugestao_da_regra') or {}).get('funcao')}
        pai = c.get('pai_id') if c.get('pai_id') in usados else None
        por_pai.setdefault(pai, []).append({'camada': lid, 'nome': c.get('nome') or '', 'tipo': c.get('tipo'),
                                            'pai': pai, 'nivel': 0, 'folha': folha, 'coberta': coberta})
    saida = []

    def descer(pai, nivel):
        for n in por_pai.get(pai, []):
            n['nivel'] = nivel
            saida.append(n)
            descer(n['camada'], nivel + 1)
    descer(None, 0)
    return saida


def _decisao(valor):
    return {'valor': valor, 'situacao': 'confirmado', 'origem': dict(ORIGEM)}


def briefing_parcial(dados, quadro=None):
    """O rascunho do passo 2 e do Design system na forma do briefing/1 (so os campos de funcao, cobertas, regras e
    ancoras), para a heranca e a conferencia do motor."""
    dados = dados or {}
    funcoes = [{'layer_id': int(k), 'funcao': _decisao(v['funcao']), 'observacao': v.get('observacao')}
               for k, v in sorted((dados.get('funcoes') or {}).items(), key=lambda kv: int(kv[0]))]
    cobertas = [{'layer_id': int(k), 'decisao': _decisao(v)}
                for k, v in sorted((dados.get('cobertas') or {}).items(), key=lambda kv: int(kv[0]))]
    regras, ancoras, regras_ind = [], [], []
    for f, d in sorted((dados.get('design') or {}).items()):
        if d.get('regra') is not None:
            regras.append({'funcao': f, 'regra': _decisao(d['regra'])})
        if d.get('x') is not None and d.get('y') is not None:
            ancoras.append({'funcao': f, 'x': _decisao(d['x']), 'y': _decisao(d['y'])})
    for k, d in sorted((dados.get('design_camadas') or {}).items(), key=lambda kv: int(kv[0])):
        if d.get('regra') is not None:
            regras_ind.append({'layer_id': int(k), 'regra': _decisao(d['regra'])})
        if d.get('x') is not None and d.get('y') is not None:
            ancoras.append({'layer_id': int(k), 'x': _decisao(d['x']), 'y': _decisao(d['y'])})
    q = {'valor': quadro, 'situacao': 'confirmado' if quadro else 'pendente', 'origem': dict(ORIGEM)}
    return {'quadro': q, 'funcoes': funcoes, 'cobertas': cobertas, 'regras_escala': regras,
            'regras_indeterminado': regras_ind, 'ancoras': ancoras}


def resolver(laudo, dados, quadro=None):
    """(resolvidas, erros) da heranca do motor (desdobra.briefing.modelo.resolver) sobre o rascunho."""
    resolvidas, erros, _info = mb.resolver(laudo, briefing_parcial(dados, quadro))
    return resolvidas, erros


def pendencias(laudo, dados, quadro=None):
    """O que falta no passo 2 e no Design system, na ordem do painel: [{'tipo', 'camada' ou 'funcao'}], tipo
    'funcao' (camada sem funcao, nem propria nem do grupo), 'coberta' (camada coberta sem a decisao do DA), 'regra'
    e 'ancora' (por funcao usada com geometria; por camada, a raiz do elemento, no indeterminado)."""
    dados = dados or {}
    resolvidas, erros = resolver(laudo, dados, quadro)
    sem = {e['medidas']['layer_id']: e['codigo'] for e in erros
           if e['codigo'] in ('camada_sem_funcao', 'coberta_sem_decisao')}
    saida = []
    for n in nos(laudo, quadro):
        cod = sem.get(n['camada'])
        if cod == 'camada_sem_funcao':
            saida.append({'tipo': 'funcao', 'camada': n['camada']})
        elif cod == 'coberta_sem_decisao':
            saida.append({'tipo': 'coberta', 'camada': n['camada']})
    design = dados.get('design') or {}
    design_camadas = dados.get('design_camadas') or {}
    vistas = []
    for n in nos(laudo, quadro):
        r = resolvidas.get(n['camada'])
        if r is None or r['funcao'] in mb.SEM_GEOMETRIA:
            continue
        chave = ('camada', r['raiz']) if r['funcao'] == mb.FUNCAO_INDETERMINADO else ('funcao', r['funcao'])
        if chave not in vistas:
            vistas.append(chave)
    for tipo, alvo in vistas:
        d = (design_camadas.get(str(alvo)) if tipo == 'camada' else design.get(alvo)) or {}
        if d.get('regra') is None:
            saida.append({'tipo': 'regra', tipo: alvo})
        if d.get('x') is None or d.get('y') is None:
            saida.append({'tipo': 'ancora', tipo: alvo})
    return saida


def conferir(dados, laudo=None):
    """Codigos de recusa do rascunho do passo 2 (lista vazia quando vale): indeterminado sem observacao, camada que o
    laudo nao tem e decisao de coberta numa camada que nao e coberta. laudo None: so o que nao depende dele."""
    erros = []
    for k, v in (dados.get('funcoes') or {}).items():
        if v.get('funcao') == mb.FUNCAO_INDETERMINADO and not (v.get('observacao') or '').strip():
            erros.append('indeterminado_sem_observacao')
    if laudo is None:
        return sorted(set(erros))
    camadas = mb.camadas_do_laudo(laudo)
    for chave in ('funcoes', 'cobertas', 'design_camadas'):
        for k in dados.get(chave) or {}:
            if int(k) not in camadas:
                erros.append('camada_inexistente')
    for k in dados.get('cobertas') or {}:
        c = camadas.get(int(k)) or {}
        if not ((c.get('geometria') or {}).get('coberta_no_kv') or {}).get('coberta'):
            erros.append('coberta_sem_cobertura')
    return sorted(set(erros))


def decisoes_minimas(laudo, alvo, quadro=None):
    """O menor conjunto de escolhas {layer_id: funcao} (por grupo e por camada) que, pela heranca do motor, da a cada
    camada desenhavel a funcao de alvo ({layer_id: funcao}). A camada coberta no KV nao herda do grupo e conta sempre
    uma escolha. No empate, fica sem escolha no grupo (a heranca de cima vale)."""
    lista = nos(laudo, quadro)
    filhos = {}
    for n in lista:
        filhos.setdefault(n['pai'], []).append(n)
    memo = {}

    def candidatas(n):
        if n['folha']:
            return {alvo.get(n['camada'])}
        out = set()
        for f in filhos.get(n['camada'], []):
            out |= candidatas(f)
        return out

    def custo(n, herdada):
        chave = (n['camada'], herdada)
        if chave in memo:
            return memo[chave]
        if n['folha']:
            precisa = n['coberta'] is not None or herdada != alvo.get(n['camada'])
            res = (1, {n['camada']: alvo.get(n['camada'])}) if precisa else (0, {})
        else:
            sem_n, sem_e = 0, {}
            for f in filhos.get(n['camada'], []):
                c, e = custo(f, herdada)
                sem_n += c
                sem_e.update(e)
            res = (sem_n, sem_e)
            for g in sorted(x for x in candidatas(n) if x is not None):
                if g == herdada:
                    continue
                total, escolhas = 1, {n['camada']: g}
                for f in filhos.get(n['camada'], []):
                    c, e = custo(f, g)
                    total += c
                    escolhas.update(e)
                if total < res[0]:
                    res = (total, escolhas)
        memo[chave] = res
        return res
    escolhas = {}
    for n in filhos.get(None, []):
        escolhas.update(custo(n, None)[1])
    return escolhas


def rascunho_de_escolhas(escolhas, observacao='observacao do teste'):
    """{layer_id: funcao} na forma do rascunho da tela (as chaves em texto; indeterminado com observacao)."""
    return {str(k): {'funcao': f, 'observacao': observacao if f == mb.FUNCAO_INDETERMINADO else None}
            for k, f in escolhas.items()}
