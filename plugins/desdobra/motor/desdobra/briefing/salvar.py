# -*- coding: utf-8 -*-
"""O gravador do briefing confirmado pelo DA (M7a, fatia 5; decisoes-v1.md, 159, 164, 167, 169, 170 e 171).

"Salvar e seguir" e um ato da janela da tela (desdobra.tela.atos, com a confirmacao do DA na propria janela e o
Disparo da tela) e o "desdobra briefing confirmar" do terminal fica so para os testes e para a Trezion (decisoes-v1.md,
159; o Disparo do console). Os dois chamam este gravador, que:
  - so grava quando todas as familias da tela estao confirmadas no rascunho (briefing/rascunho.json, pelo ato
    "Confirmar familia"), com a confirmacao de mesma origem do Disparo, quando o DA escolheu o modo de dados na tela e
    quando o briefing montado passa na conferencia do motor (pendencias). Nada tem valor inicial: as funcoes, as
    cobertas, as regras e as ancoras sao as do rascunho (desdobra.tela.funcoes.briefing_parcial), o modo e o de
    briefing/modo-dados.json, e as familias levam a versao e as edicoes que o DA confirmou;
  - a prancheta da peca (quadro) e o giro de cada formato sao escolhas do passo 1, no rascunho (escolhas_do_passo_1;
    revisao do M7a); sem o giro de todos os formatos, nada e gravado;
  - o que a tela ainda nao decide (formatos, mestres, parametros das familias, quebras e regras de bloco) vem do
    briefing gravado, com a origem que cada decisao ja tinha; no job novo, sem briefing gravado, vem do briefing de
    partida (desdobra.briefing.modelo.partida: os formatos das specs do job, a mestre do KV e o quadro pendente), e o
    primeiro briefing confirmado nasce aqui; com o gravado de outra versao dos arquivos do job, vem da retomada
    (desdobra.briefing.modelo.retomada: o de partida com o que ainda vale do gravado);
  - o texto editado tem de ter todos os caracteres na fonte do job (a mesma conferencia da previa da tela);
  - grava briefing/briefing-confirmado.json com a origem e o meio do Disparo (da e tela; da e terminal; no modo de
    teste da tela, fixture_de_teste e medicao, que o entregar recusa), guarda a versao anterior em
    briefing/historico/ e roda a derivacao, que parte das familias confirmadas (desdobra.derivacao.proposta).
"""
import copy
from pathlib import Path

from desdobra import contratos

COMANDO = 'briefing confirmar'
ORIGEM_DA = 'da'
ORIGEM_FIXTURE = 'fixture_de_teste'
REF_RASCUNHO = 'rascunho da tela'
REF_MODO = 'briefing/modo-dados.json'
CAMPOS_DO_RASCUNHO = ('funcoes', 'cobertas', 'regras_escala', 'regras_indeterminado', 'ancoras')


class ErroSalvar(Exception):
    """O briefing nao foi gravado. pendencias: [{'codigo', ...}] (codigos fixos do motor)."""

    def __init__(self, mensagem, pendencias=()):
        super().__init__(mensagem)
        self.pendencias = list(pendencias)


def _rascunho(pasta):
    from desdobra.tela import rascunho
    return rascunho.ler(pasta, rascunho.laudo_sha256(pasta))


def _modo(pasta, origem):
    """O modo escolhido na tela para a origem pedida (da: so a escolha do DA, limitada pelo teto do job; fixture: a do
    modo de teste tambem; None: qualquer escolha gravada), ou None."""
    from desdobra.job import modo_dados
    reg = modo_dados.ler(pasta)
    if reg is None:
        return None
    if origem == ORIGEM_DA:
        if reg['origem'] != ORIGEM_DA:
            return None
        return modo_dados.efetivo(pasta, modo_dados.teto_do_job(pasta))
    return reg['valor']


def _com_origem(itens, tipo):
    saida = copy.deepcopy(itens)
    for item in saida:
        for v in item.values():
            if isinstance(v, dict) and 'situacao' in v:
                v['origem'] = {'tipo': tipo, 'ref': REF_RASCUNHO}
    return saida


def escolhas_do_passo_1(briefing, dados, laudo, tipo):
    """O briefing (copia) com as escolhas do passo 1 do rascunho da tela por cima (revisao do M7a): a prancheta de onde
    a peca sai (quadro, so entre os quadros do laudo; decisao 1) e o giro de cada formato (rotacoes, pela chave da
    folha; decisao 139). O que o rascunho nao tem fica como estava no briefing. tipo: a origem das decisoes (da ou
    fixture_de_teste)."""
    novo = copy.deepcopy(briefing)
    dados = dados or {}
    quadros = {q['id'] for q in (laudo.get('documento') or {}).get('quadros') or []}
    if dados.get('quadro') in quadros:
        novo['quadro'] = {'valor': dados['quadro'], 'situacao': 'confirmado', 'origem': {'tipo': tipo, 'ref': REF_RASCUNHO}}
    giro = dados.get('rotacoes') or {}
    for f in novo['formatos']:
        if f['chave'] in giro:
            f['rotacao'] = {'graus': giro[f['chave']]['graus'], 'sentido': giro[f['chave']]['sentido']}
    return novo


def montar(pasta, conteudo, dados, *, origem, meio, por, quando, modo):
    """O briefing/1 que o gravador grava: o rascunho da tela (passo 1, prancheta e giro; passo 2, Design system e
    familias), o modo da tela e o resto do briefing gravado. Nao grava nada."""
    from desdobra.briefing import modelo as mb
    from desdobra.tela import funcoes
    # no job novo, o briefing de partida (os formatos das specs, o quadro e o resto pendentes): o primeiro briefing
    # confirmado nasce aqui; com o gravado de outra versao dos arquivos do job, a retomada (mb.base_da_tela)
    base = mb.base_da_tela(pasta)
    tipo = ORIGEM_DA if origem == ORIGEM_DA else ORIGEM_FIXTURE
    laudo = contratos.ler(Path(pasta) / mb.ARQUIVO_LAUDO, 'laudo/1')
    novo = escolhas_do_passo_1(base, dados, laudo, tipo)
    quadro = novo['quadro']['valor'] if mb._decisao_valida(novo['quadro']) else None
    parcial = funcoes.briefing_parcial(dados, quadro)
    for k in CAMPOS_DO_RASCUNHO:
        novo[k] = _com_origem(parcial[k], tipo)
    novo['modo_dados'] = {'valor': modo, 'situacao': 'confirmado' if modo else 'pendente',
                          'origem': {'tipo': tipo, 'ref': REF_MODO}}
    novo['composicoes'] = []
    for gid, fam in conteudo['familias'].items():
        f = dados['familias'].get(gid) or {}
        conf = f.get('confirmacao')
        novo['composicoes'].append({'familia': gid, 'formatos': list(fam['formatos']), 'versao': f.get('versao'),
                                    'edicoes': copy.deepcopy(f.get('edicoes') or []),
                                    'confirmada': bool(f.get('confirmada')),
                                    'confirmacao': None if conf is None else
                                    {k: v for k, v in conf.items() if k not in ('formatos', 'pecas')}})
    novo['cabecalho'] = dict(mb.hashes_atuais(pasta), origem=origem, meio=meio, por=dict(por), quando=quando)
    return novo


def pendencias(pasta, conteudo, origem=None):
    """O que impede gravar: [{'codigo', ...}], vazio quando o briefing pode ser gravado. origem: a do Disparo (da ou
    fixture_de_teste); None antes do dialogo (vale qualquer uma das duas). conteudo: o da tela
    (desdobra.tela.estado.montar), com as familias e a previa da edicao."""
    from desdobra.briefing import modelo as mb
    from desdobra.tela import rascunho
    from desdobra.tela import estado as mod_estado
    pasta = Path(pasta).resolve()
    # o formato da folha com duas medidas, sem a escolha do DA, nao tem chave nem peca: o briefing sem ele deixaria um
    # formato da folha de fora em silencio (revisao dos becos, D2)
    sem_medida = mod_estado.formatos_sem_medida(pasta)
    antes = [{'codigo': 'formato_sem_medida', 'formatos': [x['texto'] for x in sem_medida]}] if sem_medida else []
    dados, de_outro = _rascunho(pasta)
    if dados is None:
        return antes + [{'codigo': 'rascunho_de_outro_laudo' if de_outro else 'sem_rascunho'}]
    origens = (origem,) if origem else (ORIGEM_DA, ORIGEM_FIXTURE)
    saida = list(antes)
    editar = conteudo.get('editar')
    for gid, fam in conteudo['familias'].items():
        f = dados['familias'].get(gid)
        if fam.get('por_confirmar'):
            # um formato da familia tem valor de spec a espera do DA, sem galeria: nenhuma confirmacao vale para ela
            # (revisao da correcao dos becos)
            saida.append({'codigo': 'formato_com_spec_por_confirmar', 'familia': gid,
                          'formatos': list(fam['por_confirmar'])})
            continue
        # a confirmacao vale so para os formatos que a familia tinha quando o DA confirmou (revisao do M7a)
        if not f or not rascunho.confirmada_para(f, fam['formatos'], fam.get('pecas')) or \
                (f.get('confirmacao') or {}).get('origem') not in origens:
            saida.append({'codigo': 'familia_sem_confirmacao', 'familia': gid})
            continue
        if f['versao'] is not None and f['versao'] not in fam['versoes']:
            saida.append({'codigo': 'versao_que_a_familia_nao_tem', 'familia': gid})
            continue
        if callable(editar):
            r = editar({'familia': gid, 'versao': f['versao'], 'edicoes': f['edicoes']})
            if r is None:
                saida.append({'codigo': 'edicao_invalida', 'familia': gid})
            elif r['recusas']:
                saida.append({'codigo': 'texto_sem_caractere', 'familia': gid})
    modo = _modo(pasta, origem)
    if modo is None:
        saida.append({'codigo': 'modo_dados_sem_escolha'})
    # o gravado de outra versao do laudo, das specs, do design system ou das fontes nao entra aqui: montar parte da
    # retomada (mb.base_da_tela), com os formatos das specs de agora, e nunca carimba os formatos velhos como atuais
    try:
        b = montar(pasta, conteudo, dados, origem=origem or ORIGEM_DA, meio='tela', por={'usuario': None, 'maquina': None},
                   quando=mb.agora(), modo=modo)
        contratos.validar(b, mb.ESQUEMA)
    except (contratos.ErroContrato, KeyError, TypeError, ValueError):
        return saida + [{'codigo': 'briefing_invalido'}]
    if not b['formatos']:
        saida.append({'codigo': 'sem_formatos'})
    # o giro de cada formato e decisao do DA no passo 1 (decisoes-v1.md, 139): sem ele a derivacao suporia 0 grau
    for f in b['formatos']:
        if f.get('rotacao') is None:
            saida.append({'codigo': 'rotacao_sem_escolha', 'formato': f['id']})
    laudo = contratos.ler(pasta / mb.ARQUIVO_LAUDO, 'laudo/1')
    estado = contratos.ler(pasta / 'estado.json', 'estado/1')
    erros = [e for e in mb.conferir(laudo, b, estado['job_id'])
             if not (e['codigo'] == 'pendente_obrigatorio' and e.get('onde') == '/modo_dados')]
    if erros:
        saida.append({'codigo': 'briefing_com_problema', 'erros': sorted({e['codigo'] for e in erros})})
    return saida


def salvar(pasta, conteudo, disparo):
    """Grava o briefing confirmado e deriva. disparo: o do ato "Salvar e seguir" da tela ou o do "briefing confirmar"
    do terminal (comando COMANDO), de uso unico. ErroSalvar com as pendencias quando nao pode gravar; humano.ErroHumano
    com disparo de outro comando. Devolve {'briefing', 'historico', 'derivado', 'motivo', 'devolucoes'}."""
    from desdobra import humano
    humano.conferir(disparo, COMANDO)
    try:
        return _salvar(pasta, conteudo, disparo)
    finally:
        # de uso unico: gasto na gravacao (mb.gravar_com_historico) ou aqui, quando nada foi gravado
        humano.gastar(disparo)


def _salvar(pasta, conteudo, disparo):
    from desdobra.briefing import modelo as mb
    from desdobra.derivacao import nucleo as nd
    from desdobra.job import nucleo
    pasta = Path(pasta).resolve()
    pend = pendencias(pasta, conteudo, disparo.origem)
    if pend:
        raise ErroSalvar('O briefing não foi gravado.', pend)
    dados, _de_outro = _rascunho(pasta)
    reg = disparo.registro()
    b = montar(pasta, conteudo, dados, origem=disparo.origem, meio=disparo.meio,
               por={'usuario': reg['usuario'], 'maquina': reg['maquina']}, quando=reg['quando'],
               modo=_modo(pasta, disparo.origem))
    contratos.validar(b, mb.ESQUEMA)
    derivado, motivo, devolucoes = True, None, None
    with nucleo.Trava(pasta):
        guardada = mb.gravar_com_historico(pasta, b, disparo=disparo)
        try:
            r = nd.derivar(pasta)
            devolucoes = len(r['devolucoes'])
        except nd.ErroDerivacao as e:
            derivado, motivo = False, e.motivo
    nucleo.registrar_evento(pasta, 'briefing_confirmado', origem=disparo.origem, meio=disparo.meio,
                            familias=len(b['composicoes']), derivado=derivado, motivo=motivo)
    return {'briefing': b, 'historico': guardada, 'derivado': derivado, 'motivo': motivo, 'devolucoes': devolucoes}


def situacao_na_tela(pasta, familias):
    """{'salvo', 'em'} para a tela: salvo quando o briefing gravado traz as familias da tela como o rascunho as tem
    confirmadas agora (mesma versao, mesmas edicoes) e vale para os arquivos do job. familias: {id: [formatos]}."""
    from desdobra.briefing import modelo as mb
    nao = {'salvo': False, 'em': None}
    try:
        b = mb.ler(pasta)
    except contratos.ErroContrato:
        return nao
    if b is None or not b.get('composicoes') or b['cabecalho']['origem'] not in (ORIGEM_DA, ORIGEM_FIXTURE):
        return nao
    if mb.desatualizado(pasta, b):
        return nao
    dados, _de_outro = _rascunho(pasta)
    if dados is None:
        return nao
    comps = {c['familia']: c for c in b['composicoes']}
    if set(comps) != set(familias):
        return nao
    for gid, fids in familias.items():
        c, f = comps[gid], dados['familias'].get(gid) or {}
        if c['formatos'] != list(fids) or not f.get('confirmada') or not c['confirmada'] or \
                (c['versao'], c['edicoes']) != (f.get('versao'), f.get('edicoes')):
            return nao
    # a prancheta e o giro do passo 1 tambem: escolhidos de novo depois de salvar, pedem outro "Salvar e seguir"
    giro = dados.get('rotacoes') or {}
    if any(f['chave'] in giro and f.get('rotacao') != giro[f['chave']] for f in b['formatos']):
        return nao
    if dados.get('quadro') is not None and dados['quadro'] != b['quadro'].get('valor'):
        return nao
    return {'salvo': True, 'em': b['cabecalho']['quando']}
