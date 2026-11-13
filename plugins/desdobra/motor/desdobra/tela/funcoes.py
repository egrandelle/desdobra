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
import re

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


def _decisao(valor, origem=None):
    return {'valor': valor, 'situacao': 'confirmado', 'origem': dict(origem or ORIGEM)}


def _origem_do_campo(d, campo):
    """M7c, M4: a origem padrao_marca que o clique em "Usar o padrao" deixou no campo (regra ou ancora) da entrada do
    Design system, ou None (a escolha e do DA)."""
    o = (d.get('origem') or {}).get(campo)
    return {'tipo': o['tipo'], 'ref': o['ref']} if isinstance(o, dict) and o.get('tipo') == TIPO_PADRAO else None


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
        # M7c, M4: o valor posto pelo clique em "Usar o padrao" leva a origem padrao_marca com o ref
        if d.get('regra') is not None:
            regras.append({'funcao': f, 'regra': _decisao(d['regra'], _origem_do_campo(d, 'regra'))})
        if d.get('x') is not None and d.get('y') is not None:
            o = _origem_do_campo(d, 'ancora')
            ancoras.append({'funcao': f, 'x': _decisao(d['x'], o), 'y': _decisao(d['y'], o)})
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


FRASE_PEDIR_SUGESTOES = 'Para ver sugestões de função, escreva ao Claude: quero sugestões'


def _sem_sugestao(modo):
    return {'modo': modo, 'sha256': None, 'sugestoes': []}


# revisao do S4: o laudo nao muda com a tela aberta, e a rota leve e consultada a cada poucos segundos. O que ela usa do
# laudo (o sha256 do KV e os layer_id) fica guardado por arquivo e so e lido e validado de novo quando o arquivo muda
# (data de modificacao ou tamanho).
_LAUDO_DAS_SUGESTOES = {}
_LAUDOS_GUARDADOS = 16  # numero-neutro: so limita a memoria do processo; uma tela usa um laudo


def _laudo_das_sugestoes(pasta):
    """(sha256 do KV, frozenset dos layer_id) do laudo do job, lidos e validados uma vez por versao do arquivo."""
    arq = pasta / 'laudo' / 'laudo.json'
    st = arq.stat()
    chave = (st.st_mtime_ns, st.st_size)
    guardado = _LAUDO_DAS_SUGESTOES.get(str(arq))
    if guardado is not None and guardado[0] == chave:
        return guardado[1], guardado[2]
    laudo = contratos.ler(arq, 'laudo/1')
    sha, ids = (laudo.get('origem') or {}).get('sha256'), frozenset(mb.camadas_do_laudo(laudo))
    if len(_LAUDO_DAS_SUGESTOES) >= _LAUDOS_GUARDADOS:
        _LAUDO_DAS_SUGESTOES.clear()
    _LAUDO_DAS_SUGESTOES[str(arq)] = (chave, sha, ids)
    return sha, ids


def sugestoes_na_tela(pasta, teto=None):
    """M7c, S4 (decisoes-v1.md, 162 e 190, Q4): o que a tela mostra ao lado de cada funcao, lido de
    sugestoes/sugestoes-validadas.json (o arquivo que o motor gravou depois de conferir o do Claude;
    desdobra.sugestao.importar). {'modo': o modo efetivo de agora, 'sha256': o do arquivo mostrado ou None,
    'sugestoes': [{'layer_id', 'funcao', 'alternativa'}] pela ordem do layer_id}. Nada aparece quando o modo efetivo
    (escolha do DA limitada pelo teto do job, o da linha de comando e o do processo) e c, quando o arquivo e de outro
    modo, de outro job ou de outro KV, ou quando nao se le; o alvo que o laudo nao tem mais sai. So ids e o enum de
    funcoes: nenhum nome nem texto. Le e nunca grava: a sugestao so vira valor com o clique do DA. O arquivo validado
    acima de LIMITE_BYTES da importacao nao se le, e o laudo so e lido de novo quando muda (_laudo_das_sugestoes)."""
    import hashlib
    import json
    from pathlib import Path

    from desdobra.sugestao import importar, pacote
    pasta = Path(pasta)
    try:
        estado = contratos.ler(pasta / 'estado.json', 'estado/1')
    except (contratos.ErroContrato, OSError, ValueError):
        return _sem_sugestao('c')
    modo = pacote.modo_do_job(pasta, estado, teto)
    if modo not in ('a', 'b'):
        return _sem_sugestao('c')
    arq = pasta / importar.ARQUIVO_VALIDADAS
    try:
        if arq.is_symlink() or not arq.is_file() or arq.stat().st_size > importar.LIMITE_BYTES:
            return _sem_sugestao(modo)
        bruto = arq.read_bytes()
        if len(bruto) > importar.LIMITE_BYTES:
            return _sem_sugestao(modo)
        dados = contratos.validar(json.loads(bruto.decode('utf-8')), importar.CONTRATO)
        kv_sha256, ids = _laudo_das_sugestoes(pasta)
    except (contratos.ErroContrato, OSError, ValueError, UnicodeDecodeError):
        return _sem_sugestao(modo)
    if dados.get('modo_dados') != modo or dados.get('job_id') != estado.get('job_id') or \
            dados.get('arquivo_sha256') != kv_sha256:
        return _sem_sugestao(modo)
    itens = sorted(({'layer_id': x['layer_id'], 'funcao': x['funcao'], 'alternativa': x['alternativa']}
                    for x in dados['sugestoes'] if x['layer_id'] in ids), key=lambda x: x['layer_id'])
    return {'modo': modo, 'sha256': hashlib.sha256(bruto).hexdigest(), 'sugestoes': itens}


TIPO_PADRAO = 'padrao_marca'
CAMPOS_DO_PADRAO = ('regra', 'ancora')
# o ref do padrao da marca no briefing e no rascunho (texto, sem mudar o briefing/1): o id do perfil, a versao atual e
# o job de origem da regra ou da ancora
FORMA_DO_REF = re.compile(r'^marca:([0-9a-f]{32})@v([1-9][0-9]*)#job:([0-9a-f]{8,64})$')


def ref_do_padrao(marca_id, versao, job):
    """O ref do padrao: marca:<id>@v<N>#job:<id>."""
    return 'marca:%s@v%d#job:%s' % (marca_id, int(versao), job)


def padrao_da_marca(pasta, biblioteca):
    """M7c, M4 (arquitetura-v1.md, 5.3 e 5.7; decisoes-v1.md, 162 e 190, Q1 e Q3): o padrao da marca escolhida no passo
    1 (briefing/marca.json) para o Design system, lido da versao atual do perfil na biblioteca da agencia:
    {'versao', 'funcoes': {funcao: {'regra': {'valor', 'job', 'job_nome', 'ref', 'desde'} ou None, 'ancora': {'x', 'y',
    'job', 'job_nome', 'ref', 'desde'} ou None}}}, com o job de origem de cada regra e ancora (desde: _desde; job_nome:
    o nome do job de origem que o perfil guarda, ou None no perfil gravado antes do ajuste nome). None sem biblioteca,
    sem marca escolhida, em "Sem marca", com a marca fora desta biblioteca, com o perfil que nao se le ou sem registro
    (versao 0). Le e nunca grava: o padrao e sugestao citada, e so o clique do DA em "Usar o padrao" poe o valor no
    rascunho. Ids, o enum, a versao e o nome do job de origem (so para a pagina da tela): o nome da marca nunca entra,
    e o ref continua pelo id."""
    from desdobra.marca import job as marca_job
    from desdobra.marca import perfil
    if biblioteca is None:
        return None
    reg = marca_job.ler(pasta)
    if reg is None or reg['escolha'] != 'marca' or not reg.get('marca_id'):
        return None
    try:
        dados = perfil.ler(biblioteca, reg['marca_id'])
    except (perfil.ErroPerfil, OSError, ValueError):
        return None
    atual = perfil.atual(dados)
    if atual is None:
        return None
    versao, id_ = dados['versao'], dados['id']
    # revisao do M4: as versoes da mais nova para a mais antiga (o historico guarda todas, nunca apagadas, Q3)
    versoes = [atual] + list(reversed(dados.get('historico') or []))
    # ajuste nome: o nome do job de origem, o que o item guarda ou o que uma campanha do mesmo job registrou
    nomes = perfil.nomes_dos_jobs(dados)
    funcoes = {}
    for r in atual['regras_escala']:
        funcoes.setdefault(r['funcao'], {'regra': None, 'ancora': None})['regra'] = {
            'valor': r['regra'], 'job': r['job_origem'], 'job_nome': _nome_do_job(r, nomes),
            'ref': ref_do_padrao(id_, versao, r['job_origem']),
            'desde': _desde(versoes, 'regras_escala', r, ('regra', 'job_origem'))}
    for a in atual['ancoras']:
        funcoes.setdefault(a['funcao'], {'regra': None, 'ancora': None})['ancora'] = {
            'x': a['x'], 'y': a['y'], 'job': a['job_origem'], 'job_nome': _nome_do_job(a, nomes),
            'ref': ref_do_padrao(id_, versao, a['job_origem']),
            'desde': _desde(versoes, 'ancoras', a, ('x', 'y', 'job_origem'))}
    return {'versao': versao, 'funcoes': funcoes}


def _nome_do_job(item, nomes):
    """Ajuste nome do M7c: o nome do job de origem para a tela, ou None no perfil sem nome (a pagina cai no id curto).
    Revisao do ajuste nome: vale o nome mais recente que o perfil tem para o job (perfil.nomes_dos_jobs), e o que o item
    guarda so na falta dele; o job com a pasta renomeada aparece com um nome so."""
    return nomes.get(item['job_origem']) or item.get('job_origem_nome')


def _desde(versoes, lista, item, chaves):
    """Revisao do M4: a primeira versao, na sequencia que chega a atual sem interrupcao, em que a regra ou a ancora da
    funcao tem o mesmo valor e o mesmo job de origem. O clique feito em qualquer versao desse intervalo continua
    valendo: a versao nova que nao muda a funcao nao derruba o clique de antes (decisoes-v1.md, 190, Q3)."""
    desde = versoes[0]['versao']
    for v in versoes[1:]:
        igual = next((x for x in v.get(lista) or () if x.get('funcao') == item['funcao']), None)
        if igual is None or any(igual.get(k) != item[k] for k in chaves):
            break
        desde = v['versao']
    return desde


def _ref_vale(ref, p, versao):
    """O ref do clique cita a mesma marca e o mesmo job de origem do padrao atual, numa versao entre p['desde'] e a
    versao atual (o valor nao mudou desde o clique)."""
    a, b = FORMA_DO_REF.match(ref or ''), FORMA_DO_REF.match(p['ref'])
    if a is None or b is None or a.group(1) != b.group(1) or a.group(3) != b.group(3):
        return False
    return p.get('desde', versao) <= int(a.group(2)) <= versao


def _vale_o_padrao(d, campo, f, padrao):
    """O campo da entrada d do Design system (funcao f) com a origem padrao_marca bate com o padrao atual: a marca
    escolhida, o job de origem, a versao entre a primeira com o valor de hoje e a atual (_ref_vale) e o mesmo valor."""
    o = _origem_do_campo(d, campo)
    p = ((padrao or {}).get('funcoes') or {}).get(f) or {}
    p = p.get(campo)
    if o is None or p is None or not _ref_vale(o['ref'], p, padrao['versao']):
        return False
    if campo == 'regra':
        return d.get('regra') == p['valor']
    return d.get('x') == p['x'] and d.get('y') == p['y']


def padrao_invalido(dados, padrao):
    """As origens padrao_marca do rascunho que nao valem contra o padrao atual (padrao_da_marca; None sem perfil):
    [{'funcao', 'campo'}], na ordem das funcoes. Vale so o ref da marca escolhida e do job de origem de agora, de uma
    versao em que o campo ja tinha o valor de hoje (revisao do M4: _desde), com o mesmo valor do perfil; o resto e
    recusado pelo gravador do briefing."""
    saida = []
    for f, d in sorted(((dados or {}).get('design') or {}).items()):
        for campo in CAMPOS_DO_PADRAO:
            if _origem_do_campo(d, campo) is not None and not _vale_o_padrao(d, campo, f, padrao):
                saida.append({'funcao': f, 'campo': campo})
    return saida


def sem_padrao_invalido(dados, padrao):
    """Copia do rascunho sem as origens padrao_marca que nao valem (padrao_invalido): o valor fica, como escolha do
    DA. Para o briefing montado so para comparar (a situacao da tela); o gravador recusa antes."""
    import copy
    ruins = {(x['funcao'], x['campo']) for x in padrao_invalido(dados, padrao)}
    if not ruins:
        return dados
    novo = copy.deepcopy(dados)
    for f, campo in ruins:
        d = novo['design'][f]
        d['origem'].pop(campo, None)
        if not d['origem']:
            del d['origem']
    return novo


def rascunho_de_escolhas(escolhas, observacao='observacao do teste'):
    """{layer_id: funcao} na forma do rascunho da tela (as chaves em texto; indeterminado com observacao)."""
    return {str(k): {'funcao': f, 'observacao': observacao if f == mb.FUNCAO_INDETERMINADO else None}
            for k, f in escolhas.items()}
