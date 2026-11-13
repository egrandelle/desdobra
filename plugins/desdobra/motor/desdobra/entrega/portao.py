# -*- coding: utf-8 -*-
"""Portao da entrega e da aprovacao (arquitetura-v1.md, 9.7; decisoes-v1.md, 93, 86, 138 e 139).

conferir() devolve, por formato do briefing, as falhas que impedem entregar (ou aprovar) e os hashes medidos agora:
  - briefing (so o entregar): a conferencia inteira de desdobra.briefing.modelo.conferir_para_entrega. Origem
    fixture_de_teste, rascunho ou outra que nao seja 'da' recusa todo formato (nº 93);
  - rotacao (nº 139): sem decisao, recusa; em 90 e 270 graus, exige o sentido confirmado pelo DA nos parametros do
    job (parametros/entrega.json); em 0 e 180 graus, o sentido nao importa;
  - master e render: render/<formato>/master.png, render.json e contrato.json do mesmo formato e do mesmo job; o sha256
    do master e o do render.json, o do contrato e o do render.json;
  - KV e impressao: o contrato e do KV que esta em entrada/ agora e o render.json leva a impressao do formato de agora
    (impressao_do_formato; M7b, A2): a mudanca do briefing que nao alimenta o formato nao derruba o render dele;
  - contrato refeito (nº 86): o contrato do formato e montado de novo, como o render faz (no derivado, a derivacao
    tambem e refeita), e tem de sair sem bloqueio, igual ao gravado e com as mesmas decisoes que o DA aceitou;
  - familia e proposta (so o entregar; decisoes-v1.md, 167): no briefing com as familias da tela (composicoes), o
    formato fora de uma familia confirmada recusa; a proposta da galeria (derivacao/<formato>.json com o caminho
    galeria) sem a confirmacao da familia recusa;
  - aprovacao (so o entregar, nº 138): o registro do formato em briefing/aprovacao.json, com os hashes de agora e o
    arquivo final que o encoder da agora. A aprovacao do modo de teste da tela (meio medicao ou origem
    fixture_de_teste; M7b, B4) e recusada (aprovacao_de_teste), com o meio e a origem gravados nas medidas; o sentido
    do giro do modo de teste conta como confirmacao de teste (confirmacao_de_teste).

Funcao pura dos arquivos do job: nao grava nada.
"""
import json
from pathlib import Path

from desdobra import arquivos, contratos, humano
from desdobra.briefing import modelo as mb
from desdobra.entrega import aprovacao as mod_aprovacao
from desdobra.entrega import codificar

ARQUIVO_PARAMETROS = Path('parametros') / 'entrega.json'
ESQUEMA_PARAMETROS = 'parametros-entrega/1'
GRAUS_QUARTO_DE_VOLTA = (90, 270)  # numero-neutro: graus do giro de um quarto de volta (a dimensao troca)

DESCRICOES = {
    'formato_inexistente': 'O briefing não tem este formato.',
    'rotacao_nao_decidida': 'A rotação do formato não foi decidida no briefing (decisão 139): a entrega não supõe 0 grau.',
    'rotacao_sem_sentido_confirmado': 'O formato gira um quarto de volta e o sentido do giro não está confirmado pelo DA '
                                      'em parametros/entrega.json (decisão 139). O sentido (horário ou anti-horário) é '
                                      'decisão do DA, e o botão dela chega no próximo marco do desdobra.',
    'rotacao_sentido_divergente': 'O sentido do giro no briefing não é o que o DA confirmou em parametros/entrega.json.',
    'parametros_de_entrega_invalidos': 'parametros/entrega.json não segue o contrato parametros-entrega/1.',
    'sem_master': 'O formato não tem render/<formato>/master.png, render.json e contrato.json: o render dele é '
                  'um clique do DA na tela.',
    'render_json_invalido': 'O render.json do formato não segue o contrato render/1.',
    'render_de_outro_formato': 'O render.json da pasta é de outro formato (arquivo trocado).',
    'render_de_outro_job': 'O render.json é de outro job.',
    'master_diferente_do_render': 'O master.png não é o que o render gravou (sha256 diferente do render.json).',
    'contrato_diferente_do_render': 'O contrato.json não é o que o render usou (sha256 diferente do render.json).',
    'master_de_outro_kv': 'O master saiu de outro KV, e não do que está em entrada/ agora.',
    'master_de_outra_impressao': 'O master saiu de outra versão do que alimenta o formato (função, regra, âncora, '
                                 'quebra, família, spec ou mestre da derivação dele). O "Salvar e seguir" do DA, na '
                                 'tela, deriva de novo, e o render do formato é um clique dele.',
    'contrato_desatualizado': 'O contrato montado de novo, com os arquivos de agora, não é o que o render usou: o DA '
                              'renderiza o formato de novo, com um clique na tela.',
    'aceites_diferentes': 'As decisões que o contrato de agora pede ao DA não são as que ele aceitou no render.',
    'familia_sem_confirmacao': 'O formato não está numa família confirmada pelo DA na tela ("Confirmar família").',
    'proposta_sem_confirmacao': 'O formato sai de uma proposta do motor que o DA não confirmou na tela.',
    'sem_aprovacao': 'O formato não tem aprovação do DA (um clique dele na tela do desdobra).',
    'aprovacao_invalida': 'briefing/aprovacao.json não segue o contrato aprovacao/2.',
    'aprovacao_antiga': 'A aprovação do formato é de uma versão anterior do desdobra, que olhava o briefing inteiro, e '
                        'caiu: aprove o formato de novo.',
    'aprovacao_de_outro_job': 'briefing/aprovacao.json é de outro job.',
    'aprovacao_de_teste': 'A aprovação do formato saiu do modo de teste da tela (meio medicao ou origem '
                          'fixture_de_teste) e não vale para a entrega: o DA aprova o formato na tela.',
    'aprovacao_caiu': 'A aprovação do formato caiu: algo mudou depois dela (veja os campos).',
}


def _falha(codigo, **medidas):
    f = {'codigo': codigo, 'descricao': DESCRICOES.get(codigo) or codificar.DESCRICOES.get(codigo, codigo)}
    if medidas:
        f['medidas'] = medidas
    return f


def _normal(dados):
    return json.loads(json.dumps(dados, sort_keys=True))


def parametros_de_entrega(pasta):
    """{formato: {...}} de parametros/entrega.json ({} sem o arquivo). ErroContrato quando nao segue o contrato."""
    arq = Path(pasta) / ARQUIVO_PARAMETROS
    return contratos.ler(arq, ESQUEMA_PARAMETROS)['formatos'] if arq.is_file() else {}


def conferir_rotacao(formato, parametros):
    """Falhas da rotacao do formato do briefing (nº 139). parametros: os do formato em parametros/entrega.json."""
    rot = formato.get('rotacao')
    if rot is None or rot.get('graus') is None:
        return [_falha('rotacao_nao_decidida')]
    if rot['graus'] not in GRAUS_QUARTO_DE_VOLTA:
        return []
    confirmado = ((parametros or {}).get('rotacao_sentido') or {}).get('valor')
    if confirmado is None:
        return [_falha('rotacao_sem_sentido_confirmado', graus=rot['graus'])]
    if rot.get('sentido') is not None and rot['sentido'] != confirmado:
        return [_falha('rotacao_sentido_divergente', graus=rot['graus'])]
    return []


def conferir_familia(pasta, briefing, formato):
    """Falhas da familia do formato (decisoes-v1.md, 167): o formato tem de estar numa familia confirmada, e a proposta
    da galeria gravada tem de ser de familia confirmada. O gravador do briefing (desdobra.briefing.salvar, da tela e do
    terminal) sempre grava as composicoes: briefing sem elas nao passou pela confirmacao das familias e o formato
    falha (revisao do M7a)."""
    from desdobra.derivacao import nucleo as nd
    falhas = []
    comps = briefing.get('composicoes')
    if comps is None:
        falhas.append(_falha('familia_sem_confirmacao'))
    else:
        comp = next((c for c in comps if formato in c['formatos']), None)
        # so a confirmacao do DA na janela da tela vale (a do modo de teste, fixture_de_teste e medicao, nao)
        conf = (comp or {}).get('confirmacao') or {}
        if comp is None or not comp['confirmada'] or conf.get('origem') != 'da' or conf.get('meio') != 'tela':
            falhas.append(_falha('familia_sem_confirmacao'))
    arq = Path(pasta) / nd.PASTA / ('%s.json' % formato)
    try:
        d = contratos.ler(arq, nd.ESQUEMA) if arq.is_file() else None
    except contratos.ErroContrato:
        d = None
    if d is not None and d.get('caminho') == 'galeria' and not (d.get('proposta') or {}).get('confirmada'):
        falhas.append(_falha('proposta_sem_confirmacao'))
    return falhas


def confirmacao_de_teste(pasta):
    """'confirmacao_de_fixture_de_teste' quando o job tem confirmacao de linkado ou de spec do modo de teste da tela
    (origem fixture_de_teste, proposta do M7, 159c), ou None. O modo de teste roda tambem em job com briefing de
    fixture, e a confirmacao dele nunca chega a entrega (revisao do M7a)."""
    from desdobra.render import contrato as mod_contrato
    from desdobra.specs import importar
    try:
        linkados = mod_contrato.linkados_confirmados(pasta)
    except contratos.ErroContrato:
        linkados = {}
    # a confirmacao de linkado sem origem gravada (a de antes da revisao do M7a) tambem nao conta como do DA
    if any((x.get('confirmado_por') or {}).get('origem') != mb.ORIGEM_DA for x in linkados.values()):
        return 'confirmacao_de_fixture_de_teste'
    try:
        acoes = importar.ler_confirmacoes(pasta)['acoes']
    except (contratos.ErroContrato, OSError, ValueError):
        acoes = []
    if any(a.get('por') == mb.ORIGEM_FIXTURE for a in acoes):
        return 'confirmacao_de_fixture_de_teste'
    # o sentido do giro gravado pela janela de aprovar do modo de teste (M7b, B4)
    try:
        params = parametros_de_entrega(pasta)
    except contratos.ErroContrato:
        params = {}
    if any((c.get('confirmado_por') or {}).get('origem') == mb.ORIGEM_FIXTURE
           for campos in params.values() for c in campos.values()):
        return 'confirmacao_de_fixture_de_teste'
    return None


def kv_atual(pasta):
    estado = contratos.ler(Path(pasta) / 'estado.json', 'estado/1')
    rel_kv = next((r for r in sorted(estado['entradas']) if r.startswith('entrada/kv')), None)
    return estado['job_id'], (estado['entradas'][rel_kv]['sha256'] if rel_kv else None)


def impressao_do_formato(pasta, briefing, formato):
    """A impressao do formato agora (M7b, A2): a de derivacao/<formato>.json com o briefing, o laudo e as folhas de
    spec de agora (desdobra.derivacao.nucleo.impressao_de_agora). None sem derivacao legivel. A derivacao mexida ou a
    entrada do formato mudada dao outra impressao; a mudanca do briefing fora do formato, nao."""
    from desdobra.derivacao import nucleo as nd
    arq = Path(pasta) / nd.PASTA / ('%s.json' % formato)
    try:
        d = contratos.ler(arq, nd.ESQUEMA) if arq.is_file() else None
    except contratos.ErroContrato:
        d = None
    return nd.impressao_de_agora(pasta, d, briefing) if d is not None else None


def hashes_do_formato(pasta, formato, impressao):
    """Os HASHES da aprovacao medidos agora (desdobra.entrega.aprovacao), sem refazer contrato nem arquivo final: a
    impressao dada e o sha256 do master, do render.json e do contrato (None quando falta). A tela mede com eles a
    aprovacao que caiu (desdobra.entrega.nucleo_aprovar.situacao; M7b, B4)."""
    base = Path(pasta) / 'render' / formato
    arq_master, arq_rel, arq_contrato = base / 'master.png', base / 'render.json', base / 'contrato.json'
    return {'impressao_formato': impressao,
            'master_sha256': arquivos.sha256_arquivo(arq_master) if arq_master.is_file() else None,
            'render_json_sha256': arquivos.sha256_arquivo(arq_rel) if arq_rel.is_file() else None,
            'contrato_sha256': arquivos.sha256_arquivo(arq_contrato) if arq_contrato.is_file() else None}


def _render_do_formato(pasta, formato, job_id, kv, impressao):
    """(atual, rel, falhas) dos arquivos de render/<formato>/: atual = os hashes medidos agora (None quando falta)."""
    from desdobra.render import execucao
    base = Path(pasta) / 'render' / formato
    arq_rel, arq_contrato = base / 'render.json', base / 'contrato.json'
    atual = hashes_do_formato(pasta, formato, impressao)
    if None in (atual['master_sha256'], atual['render_json_sha256'], atual['contrato_sha256']):
        return atual, None, [_falha('sem_master')]
    try:
        rel = contratos.ler(arq_rel, execucao.ESQUEMA_RENDER)
    except contratos.ErroContrato:
        return atual, None, [_falha('render_json_invalido')]
    falhas = []
    if rel['formato']['chave'] != formato:
        falhas.append(_falha('render_de_outro_formato'))
    if rel['job_id'] != job_id:
        falhas.append(_falha('render_de_outro_job'))
    if rel['master']['sha256'] != atual['master_sha256']:
        falhas.append(_falha('master_diferente_do_render'))
    if rel['contrato_sha256'] != atual['contrato_sha256']:
        falhas.append(_falha('contrato_diferente_do_render'))
    try:
        gravado = contratos.ler(arq_contrato, 'composicao/1')
    except contratos.ErroContrato:
        gravado = None
    if gravado is None or gravado['origem'].get('kv_sha256') != kv:
        falhas.append(_falha('master_de_outro_kv'))
    if impressao is None or (rel.get('derivacao') or {}).get('impressao_formato') != impressao:
        falhas.append(_falha('master_de_outra_impressao'))
    if falhas:
        return atual, rel, falhas
    # o contrato de agora, montado como o render monta (nº 86; no derivado, com a derivacao refeita)
    novo, bloqueios, confirmar = execucao.montar_contrato(pasta, formato)
    if bloqueios:
        return atual, rel, [_falha('contrato_desatualizado', bloqueios=sorted({b['codigo'] for b in bloqueios}))]
    if _normal(novo) != _normal(gravado):
        return atual, rel, [_falha('contrato_desatualizado')]
    if sorted(c['codigo'] for c in confirmar) != sorted(a['codigo'] for a in rel.get('aceites') or []):
        return atual, rel, [_falha('aceites_diferentes')]
    return atual, rel, []


def conferir(pasta, formatos=None, *, origem=True, aprovacao=True, final=True, sentidos=None):
    """Confere os formatos do job para a entrega (origem e aprovacao: o entregar) ou para a aprovacao (origem=False,
    aprovacao=False: o aprovar). formatos: ids a conferir (None: todos os formatos do briefing). final: gera o arquivo
    final dos formatos sem falha (desdobra.entrega.codificar). sentidos: {formato: sentido do giro} que o DA escolheu
    na janela de aprovar da tela e que ainda nao esta gravado (M7b, B4): vale para a rotacao e para o arquivo final
    deste conferir, sem gravar nada; quem chama confere o pedido (parametros.conferir) antes.

    Devolve {'briefing': motivo ou None, 'formatos': {id: {'falhas': [...], 'atual': {...}, 'final': ArquivoFinal ou
    None, 'recusa_do_encoder': ErroCodificar ou None}}}. Sem briefing legivel, 'formatos' so tem os ids pedidos.
    No entregar (aprovacao=True), uma recusa do encoder de validar.RECUSAS_ROTEADAS (decisao ou folha que falta no
    formato, como a cor de achatamento) nao e falha: fica em recusa_do_encoder, sem aprovacao a conferir, e a entrega
    manda o formato para reprovados com a regra e a sugestao. No aprovar, e falha (nao ha arquivo para aprovar)."""
    from desdobra.entrega import validar
    pasta = Path(pasta).resolve()
    saida = {'briefing': None, 'formatos': {}}
    try:
        b = mb.ler(pasta)
    except contratos.ErroContrato:
        b = None
        saida['briefing'] = 'briefing_invalido'
    if b is None and saida['briefing'] is None:
        saida['briefing'] = 'sem_briefing'
    do_briefing = {f['id']: f for f in (b or {}).get('formatos') or []}
    ids = list(do_briefing) if formatos is None else list(dict.fromkeys(formatos))
    if origem and saida['briefing'] is None:
        pode, motivo = mb.conferir_para_entrega(pasta)
        if not pode:
            saida['briefing'] = motivo
        else:
            saida['briefing'] = confirmacao_de_teste(pasta)
    if saida['briefing'] is not None:
        for fid in ids:
            saida['formatos'][fid] = {'falhas': [_falha(saida['briefing'])], 'atual': {}, 'final': None}
        return saida
    job_id, kv = kv_atual(pasta)
    try:
        params, erro_params = parametros_de_entrega(pasta), None
    except contratos.ErroContrato:
        params, erro_params = {}, _falha('parametros_de_entrega_invalidos')
    aprov, erro_aprov = None, None
    if aprovacao:
        try:
            aprov = mod_aprovacao.ler(pasta)
        except contratos.ErroContrato:
            erro_aprov = _falha('aprovacao_invalida')
    for fid in ids:
        if fid not in do_briefing:
            saida['formatos'][fid] = {'falhas': [_falha('formato_inexistente')], 'atual': {}, 'final': None}
            continue
        falhas = [erro_params] if erro_params else []
        sentido = (sentidos or {}).get(fid)
        params_f = params.get(fid) if sentido is None else dict(params.get(fid) or {}, rotacao_sentido={'valor': sentido})
        falhas += conferir_rotacao(do_briefing[fid], params_f)
        if origem:
            falhas += conferir_familia(pasta, b, fid)
        atual, _rel, f_render = _render_do_formato(pasta, fid, job_id, kv, impressao_do_formato(pasta, b, fid))
        falhas += f_render
        arq_final, recusa = None, None
        if final and not falhas:
            try:
                arq_final = codificar.arquivo_final(pasta, fid) if sentido is None else \
                    codificar.arquivo_final(pasta, fid, sentido=sentido)
            except codificar.ErroCodificar as e:
                if aprovacao and e.codigo in validar.RECUSAS_ROTEADAS:
                    recusa = e  # o entregar manda o formato para reprovados, com regra e sugestao, sem arquivo
                else:
                    falhas.append(_falha(e.codigo, **e.medidas))
        if aprovacao and recusa is None:
            falhas += _conferir_aprovacao(aprov, erro_aprov, fid, job_id, atual, arq_final)
        saida['formatos'][fid] = {'falhas': falhas, 'atual': atual, 'final': arq_final, 'recusa_do_encoder': recusa}
    return saida


def _conferir_aprovacao(aprov, erro, formato, job_id, atual, final):
    if erro is not None:
        return [erro]
    if aprov is None or formato not in aprov['formatos']:
        return [_falha('sem_aprovacao')]
    if aprov['job_id'] != job_id:
        return [_falha('aprovacao_de_outro_job')]
    if aprov['esquema'] != mod_aprovacao.ESQUEMA:
        return [_falha('aprovacao_antiga', esquema=aprov['esquema'])]
    reg = aprov['formatos'][formato]
    # a aprovacao do modo de teste da tela nunca vale para a entrega (M7b, B4; a critica do plano): o meio e a origem
    # gravados vao nas medidas. O registro de antes da origem gravada (o do terminal) conta como do DA
    por = reg.get('aprovado_por') or {}
    if por.get('meio') == humano.MEIO_MEDICAO or por.get('origem', humano.ORIGEM_DA) != humano.ORIGEM_DA:
        return [_falha('aprovacao_de_teste', meio=por.get('meio'), origem=por.get('origem'))]
    campos = mod_aprovacao.diferencas(reg, job_id, atual, final)
    return [_falha('aprovacao_caiu', campos=campos)] if campos else []


def falhas_por_codigo(conferencia):
    """{codigo: numero de formatos com essa falha}."""
    cont = {}
    for item in conferencia['formatos'].values():
        for codigo in sorted({f['codigo'] for f in item['falhas']}):
            cont[codigo] = cont.get(codigo, 0) + 1
    return cont
