# -*- coding: utf-8 -*-
"""Briefing confirmado (briefing/1, arquitetura-v1.md, 5.3): leitura, conferencia, heranca de funcoes e a marca da
origem que o entregar le.

O briefing guarda as decisoes do DA. Todo campo de decisao tem valor, situacao e origem, sem valor inicial. A funcao
resolvida de cada camada sai da heranca (resolver): a funcao dada a uma camada vale sobre a do grupo mais proximo
(decisoes-v1.md, 29/10, rotular por grupo); a camada coberta no KV recebe a funcao da regra da decisao 10 aceita ou
invertida pelo DA (decisao 10). Layout, validacao e teste leem so a funcao resolvida (defeito 1 do predecessor).

Quem grava o briefing como confirmado pelo DA e a tela (M7) ou o "briefing confirmar" no terminal. O "briefing
importar --teste" grava um briefing escrito a mao com a origem fixture_de_teste: o motor deriva e renderiza a partir
dele, mas o entregar (M6) recusa (conferir_para_entrega).

Funcao pura dos arquivos do job: nao abre PSD, fonte nem imagem.
"""
import getpass
import platform as _platform
from datetime import datetime
from pathlib import Path

from desdobra import arquivos, contratos

ESQUEMA = 'briefing/1'
ARQUIVO = Path('briefing') / 'briefing-confirmado.json'
PASTA_HISTORICO = Path('briefing') / 'historico'
ARQUIVO_RASCUNHO = Path('rotulagem') / 'briefing-rascunho.json'
PASTA_RASCUNHO_NO_JOB = 'rotulagem'
ORIGEM_FIXTURE = 'fixture_de_teste'
ORIGEM_DA = 'da'
ORIGEM_RASCUNHO = 'rascunho'
# ids que o motor ou o Windows ja usam: derivacao/devolucoes.json, render/origem/ e os nomes de dispositivo
IDS_DO_MOTOR = ('devolucoes', 'origem')
IDS_DO_WINDOWS = tuple(['con', 'prn', 'aux', 'nul'] + ['com%d' % k for k in range(1, 10)] +  # numero-neutro: com1 a com9
                       ['lpt%d' % k for k in range(1, 10)])  # numero-neutro: lpt1 a lpt9
FUNCAO_FORA = 'fora_da_peca'
FUNCAO_ESTRUTURA = 'estrutura'
FUNCAO_INDETERMINADO = 'indeterminado'
FUNCAO_AJUSTE = 'ajuste_global'
TIPOS_SEM_DESENHO = ('grupo', 'prancheta')
# funcoes sem geometria propria: nao pedem regra de escala nem ancora
SEM_GEOMETRIA = (FUNCAO_FORA, FUNCAO_ESTRUTURA, FUNCAO_AJUSTE)
# classe de cada funcao (taxonomia-funcoes.md): decide as restricoes e as validacoes que valem para o elemento
CLASSES = {
    'fundo': 'base', 'imagem': 'base', 'sujeito': 'base', 'veu_de_legibilidade': 'base', 'grafismo': 'base',
    'titulo': 'texto', 'texto_de_apoio': 'texto', 'cta': 'texto', 'url_ou_contato': 'texto', 'texto_legal': 'texto',
    'informacao_de_evento': 'texto', 'destaque_numerico': 'texto', 'icone_de_cta': 'marca',
    'logo_principal': 'marca', 'assinatura_institucional': 'marca', 'selo': 'marca', 'logo_de_parceiro': 'marca',
    'ajuste_global': 'global', 'estrutura': 'global', 'fora_da_peca': 'fora', 'indeterminado': 'indeterminado',
}
INVERSA_DECISAO_10 = {FUNCAO_ESTRUTURA: FUNCAO_FORA, FUNCAO_FORA: FUNCAO_ESTRUTURA}
ARQUIVO_FORMATOS = Path('specs') / 'formatos-do-job.json'
ARQUIVO_RASCUNHO_SPECS = Path('specs') / 'rascunho.json'
ARQUIVO_DS = Path('ds') / 'design-system.json'
ARQUIVO_CONFERENCIA = Path('fontes') / 'conferencia.json'
ARQUIVO_LAUDO = Path('laudo') / 'laudo.json'

DESCRICOES = {
    'pendente_obrigatorio': 'Há decisão obrigatória pendente ou sem valor no briefing.',
    'indeterminado_sem_observacao': 'Camada ou grupo com função "indeterminado" sem a observação do DA.',
    'camada_inexistente': 'O briefing cita uma camada que o laudo não tem.',
    'quadro_invalido': 'O quadro escolhido não é um dos quadros do laudo.',
    'quadro_sem_escolha': 'O laudo tem quadros, e o briefing não diz de qual quadro a peça sai (decisão 1).',
    'camada_sem_funcao': 'Há camada visível no quadro escolhido sem função, nem por grupo nem por exceção.',
    'coberta_sem_decisao': 'Há camada coberta no KV sem a decisão do DA sobre a função da regra da decisão 10.',
    'regra_de_escala_faltando': 'Há função usada no quadro escolhido sem regra de escala escolhida pelo DA.',
    'ancora_faltando': 'Há elemento sem âncora confirmada em algum eixo.',
    'formato_repetido': 'Dois formatos do briefing têm o mesmo id.',
    'mestre_invalida': 'Uma mestre própria cita formato que o briefing não tem, ou falta a mestre do KV.',
    'job_diferente': 'O briefing é de outro job.',
    'camada_sem_tinta_sem_bloco': 'Há camada sem tinta (ajuste) que não cobre nenhum elemento de cena embaixo: ela não '
                                  'teria onde atuar no formato (decisão 95).',
    'mestre_sem_elemento': 'Nenhuma camada com tinta no canvas da mestre tem função com geometria: não há o que derivar.',
    'bloco_com_regras_diferentes': 'Há camadas que andam juntas num bloco rígido (cena sobreposta) com funções de regras de '
                                   'escala diferentes. Escolha uma regra para o bloco inteiro (regras_bloco; decisão 100).',
    'regra_de_bloco_conflitante': 'O briefing dá regras diferentes para camadas do mesmo bloco rígido (regras_bloco).',
    'regra_de_bloco_sem_bloco': 'O briefing dá regra de bloco (regras_bloco) para uma camada que não está num bloco '
                                'rígido.',
    'quebra_em_caixa_de_paragrafo': 'Quebra aprovada por família em texto de caixa de parágrafo: o render refaz a quebra '
                                    'automática na largura da caixa, e o número de linhas não seria o validado.',
    'quebra_para_formato_inexistente': 'A quebra aprovada por família cita formato que o briefing não tem.',
    'quebra_com_faixa_invertida': 'A quebra aprovada por família tem razao_min maior que razao_max.',
    'quebras_conflitantes': 'Duas quebras aprovadas do mesmo texto valem para a mesma proporção com valores diferentes '
                            '(faixas que se sobrepõem, ou o mesmo formato duas vezes).',
    'quebras_da_mestre_propria_ambiguas': 'A mestre própria dá uma lista de quebras para um elemento com mais de um '
                                          'texto: não há como saber de qual texto são as posições.',
    'quebra_aprovada_invalida': 'A quebra aprovada por família (quebras_por_familia) cita camada que não é texto com '
                                'quebra gravada, ou índice de quebra que o texto não tem.',
    'composicao_com_formato_inexistente': 'Uma família confirmada na tela (composicoes) cita formato que o briefing não '
                                          'tem.',
    'formato_em_duas_composicoes': 'Um formato está em duas famílias confirmadas na tela (composicoes).',
    'formato_id_reservado': 'O id do formato é um nome que o motor ou o Windows já usam (devolucoes, origem, con, prn, '
                            'aux, nul, com1 a com9, lpt1 a lpt9).',
}


class ErroBriefing(Exception):
    """O briefing foi recusado. erros: [{'codigo', 'descricao', 'onde', ...}]."""

    def __init__(self, mensagem, erros=(), codigo='recusado'):
        super().__init__(mensagem)
        self.erros, self.codigo = list(erros), codigo


def agora():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def _erro(codigo, onde=None, **medidas):
    e = {'codigo': codigo, 'descricao': DESCRICOES[codigo]}
    if onde is not None:
        e['onde'] = onde
    if medidas:
        e['medidas'] = medidas
    return e


def _sha(pasta, rel):
    arq = Path(pasta) / rel
    return arquivos.sha256_arquivo(arq) if arq.is_file() else None


def arquivo_de_specs(pasta):
    """O arquivo de specs que vale para o briefing: os formatos do job (confirmados pelo DA) quando houver formato
    confirmado, senao o rascunho."""
    pasta = Path(pasta)
    arq = pasta / ARQUIVO_FORMATOS
    if arq.is_file():
        try:
            dados = arquivos.ler_json(arq)
            if dados.get('formatos'):
                return ARQUIVO_FORMATOS
        except (OSError, ValueError):
            pass
    return ARQUIVO_RASCUNHO_SPECS


def hashes_atuais(pasta):
    """Os hashes que o cabecalho guarda, dos arquivos que estao no job agora."""
    return {'laudo_sha256': _sha(pasta, ARQUIVO_LAUDO), 'specs_sha256': _sha(pasta, arquivo_de_specs(pasta)),
            'ds_sha256': _sha(pasta, ARQUIVO_DS), 'conferencia_sha256': _sha(pasta, ARQUIVO_CONFERENCIA)}


def ler(pasta):
    """O briefing gravado, validado pelo esquema; None quando nao ha."""
    arq = Path(pasta) / ARQUIVO
    return contratos.ler(arq, ESQUEMA) if arq.is_file() else None


def desatualizado(pasta, briefing):
    """Campos do cabecalho que nao batem com os arquivos do job (lista vazia quando o briefing vale)."""
    atuais = hashes_atuais(pasta)
    return sorted(k for k, v in atuais.items() if briefing['cabecalho'].get(k) != v)


# ------------------------------------------------------------------ heranca
def _decisao_valida(d):
    return isinstance(d, dict) and d.get('situacao') == 'confirmado' and d.get('valor') is not None


def camadas_do_laudo(laudo):
    return {c['identidade']['layer_id']: c for c in laudo['camadas']}


def no_escopo(camada, quadro):
    """A camada pertence a peca: e do quadro escolhido ou de nenhum quadro (camada comum)."""
    return quadro is None or camada.get('quadro') in (None, quadro)


def desenhavel(camada):
    return camada.get('tipo') not in TIPOS_SEM_DESENHO and bool((camada.get('aparencia') or {}).get('visivel_efetiva'))


def resolver(laudo, briefing):
    """Funcao resolvida de cada camada desenhavel do quadro escolhido.

    Devolve (resolvidas, erros, info): resolvidas = {layer_id: {'funcao', 'raiz', 'por', 'observacao'}}, em que raiz
    e o layer_id onde a funcao foi dada (o grupo ou a propria camada; o elemento da derivacao) e por diz de onde a
    funcao veio ('camada', 'grupo', 'decisao_10'); erros = lista de erros (camada sem funcao, coberta sem decisao,
    pendente, indeterminado sem observacao); info = contagens (fora do quadro, invisiveis)."""
    camadas = camadas_do_laudo(laudo)
    erros = []
    quadros = {q['id'] for q in (laudo['documento'].get('quadros') or [])}
    quadro = None
    if quadros:
        d = briefing['quadro']
        if not _decisao_valida(d):
            erros.append(_erro('quadro_sem_escolha', '/quadro'))
        elif d['valor'] not in quadros:
            erros.append(_erro('quadro_invalido', '/quadro'))
        else:
            quadro = d['valor']
    dadas = {}
    for k, item in enumerate(briefing['funcoes']):
        onde = '/funcoes/%d' % k
        lid = item['layer_id']
        if lid not in camadas:
            erros.append(_erro('camada_inexistente', onde, layer_id=lid))
            continue
        if not _decisao_valida(item['funcao']):
            # excecao pendente nao vale: a camada fica com a funcao do grupo (e sem ela, camada_sem_funcao)
            continue
        if item['funcao']['valor'] == FUNCAO_INDETERMINADO and not (item.get('observacao') or '').strip():
            erros.append(_erro('indeterminado_sem_observacao', onde, layer_id=lid))
            continue
        dadas[lid] = item
    cobertas = {}
    for k, item in enumerate(briefing['cobertas']):
        onde = '/cobertas/%d' % k
        if item['layer_id'] not in camadas:
            erros.append(_erro('camada_inexistente', onde, layer_id=item['layer_id']))
        elif _decisao_valida(item['decisao']):
            cobertas[item['layer_id']] = item['decisao']['valor']
    resolvidas, info = {}, {'fora_do_quadro': 0, 'invisiveis': 0, 'quadro': quadro}
    for lid, c in camadas.items():
        if not desenhavel(c):
            info['invisiveis'] += int(c.get('tipo') not in TIPOS_SEM_DESENHO)
            continue
        if not no_escopo(c, quadro):
            info['fora_do_quadro'] += 1
            continue
        cob = (c.get('geometria') or {}).get('coberta_no_kv') or {}
        if cob.get('coberta') and lid not in dadas:
            # a funcao da regra da decisao 10 e so sugestao: vale quando o DA aceita ou inverte
            sug = (cob.get('sugestao_da_regra') or {}).get('funcao')
            if lid not in cobertas or sug not in INVERSA_DECISAO_10:
                erros.append(_erro('coberta_sem_decisao', layer_id=lid))
                continue
            funcao = sug if cobertas[lid] == 'aceita' else INVERSA_DECISAO_10[sug]
            resolvidas[lid] = {'funcao': funcao, 'raiz': lid, 'por': 'decisao_10', 'observacao': None}
            continue
        cadeia = [lid] + list(reversed(c.get('caminho_ids') or []))
        achou = next((x for x in cadeia if x in dadas), None)
        if achou is None:
            erros.append(_erro('camada_sem_funcao', layer_id=lid))
            continue
        item = dadas[achou]
        resolvidas[lid] = {'funcao': item['funcao']['valor'], 'raiz': achou,
                           'por': 'camada' if achou == lid else 'grupo', 'observacao': item.get('observacao')}
    return resolvidas, erros, info


def regras_por_funcao(briefing):
    return {r['funcao']: r['regra']['valor'] for r in briefing['regras_escala'] if _decisao_valida(r['regra'])}


def regras_indeterminado(briefing):
    return {r['layer_id']: r['regra']['valor'] for r in briefing['regras_indeterminado'] if _decisao_valida(r['regra'])}


def regras_bloco(briefing):
    """{layer_id: regra} das regras de bloco confirmadas (decisoes-v1.md, 100)."""
    return {r['layer_id']: r['regra']['valor'] for r in briefing.get('regras_bloco') or [] if _decisao_valida(r['regra'])}


def regra_do_elemento(briefing, elemento):
    """(regra, regras dos membros, conflito) de um elemento da mestre (um so, ou um bloco). A regra de cada membro e a
    da funcao dele (a do indeterminado, a da camada); no bloco com regras diferentes vale a regra do bloco que o DA
    escolheu (regras_bloco). conflito: None, 'diferentes' (sem regra de bloco) ou 'conflitante' (duas regras de bloco)."""
    regras = regras_por_funcao(briefing)
    ind = regras_indeterminado(briefing)
    funcoes = elemento.get('membros_funcoes') or {elemento['raiz']: elemento['funcao']}
    camadas = elemento.get('membros_camadas') or {elemento['raiz']: elemento['layer_ids']}
    dos = set()
    for raiz, f in funcoes.items():
        if f in SEM_GEOMETRIA:
            continue
        if f == FUNCAO_INDETERMINADO:
            r = ind.get(raiz) or next((ind[x] for x in camadas.get(raiz) or [] if x in ind), None)
        else:
            r = regras.get(f)
        if r is not None:
            dos.add(r)
    rb = regras_bloco(briefing)
    do_bloco = {rb[x] for x in elemento['layer_ids'] if x in rb}
    if len(do_bloco) > 1:
        return None, sorted(dos), 'conflitante'
    if do_bloco:
        return do_bloco.pop(), sorted(dos), None
    if len(dos) > 1:
        return None, sorted(dos), 'diferentes'
    return (next(iter(dos)) if dos else None), sorted(dos), None


def ancora_explicita(briefing, raiz):
    """(x, y): True no eixo em que o DA deu a ancora do proprio elemento (e nao a da funcao)."""
    a = next((a for a in briefing['ancoras'] if a.get('layer_id') == raiz), None)
    return tuple(bool(a) and _decisao_valida(a[eixo]) for eixo in ('x', 'y'))


def ancora_do_elemento(briefing, raiz, funcao):
    """(x, y) confirmados para o elemento: a ancora do elemento vale sobre a da funcao; None no eixo sem ancora."""
    por_elemento = {a['layer_id']: a for a in briefing['ancoras'] if a.get('layer_id') is not None}
    por_funcao = {a['funcao']: a for a in briefing['ancoras'] if a.get('funcao') and a.get('layer_id') is None}
    saida = []
    for eixo in ('x', 'y'):
        valor = None
        for a in (por_elemento.get(raiz), por_funcao.get(funcao)):
            if a is not None and _decisao_valida(a[eixo]):
                valor = a[eixo]['valor']
                break
        saida.append(valor)
    return tuple(saida)


def conferir(laudo, briefing, job_id=None):
    """Erros de conteudo do briefing (lista vazia quando vale). O motor recusa o briefing com pendente obrigatorio e
    a funcao indeterminado sem observacao (arquitetura-v1.md, 5.3)."""
    erros = []
    if job_id is not None and briefing['job_id'] != job_id:
        erros.append(_erro('job_diferente', '/job_id'))
    resolvidas, e_res, _info = resolver(laudo, briefing)
    erros += e_res
    if not _decisao_valida(briefing['modo_dados']):
        erros.append(_erro('pendente_obrigatorio', '/modo_dados'))
    # regra, ancora e excecao pendentes nao valem; a falta delas e conferida abaixo (regra_de_escala_faltando,
    # ancora_faltando) e na heranca (camada_sem_funcao, coberta_sem_decisao)
    for nome in ('faixa', 'base', 'mestres_max'):
        d = (briefing.get('familias') or {}).get(nome)
        if d is not None and not _decisao_valida(d):
            erros.append(_erro('pendente_obrigatorio', '/familias/%s' % nome))
    regras = regras_por_funcao(briefing)
    usadas = sorted({r['funcao'] for r in resolvidas.values()
                     if r['funcao'] not in SEM_GEOMETRIA and r['funcao'] != FUNCAO_INDETERMINADO})
    for f in usadas:
        if f not in regras:
            erros.append(_erro('regra_de_escala_faltando', funcao=f))
    # ancora so dos elementos que a derivacao move: os que tem tinta dentro do canvas da mestre
    from desdobra.derivacao import elementos as mod_elementos
    mestre = mod_elementos.montar(laudo, resolvidas, _info['quadro'])
    raizes = {e['raiz']: e['funcao'] for e in mestre['elementos']}
    for lid in mestre.get('sem_bloco') or []:
        erros.append(_erro('camada_sem_tinta_sem_bloco', layer_id=lid))
    # regra do bloco (decisoes-v1.md, 100): membros com regras diferentes pedem uma regra so para o bloco
    for k, item in enumerate(briefing.get('regras_bloco') or []):
        if not _decisao_valida(item['regra']):
            erros.append(_erro('pendente_obrigatorio', '/regras_bloco/%d' % k))
    em_bloco = set()
    for e in mestre['elementos']:
        if e.get('bloco'):
            em_bloco.update(e['layer_ids'])
        _r, dos, conflito = regra_do_elemento(briefing, e)
        if conflito == 'diferentes':
            erros.append(_erro('bloco_com_regras_diferentes', camadas=e['layer_ids'], membros=e['membros'], regras=dos))
        elif conflito == 'conflitante':
            erros.append(_erro('regra_de_bloco_conflitante', camadas=e['layer_ids']))
    for lid in sorted(regras_bloco(briefing)):
        if lid not in em_bloco:
            erros.append(_erro('regra_de_bloco_sem_bloco', layer_id=lid))
    # quebras aprovadas por familia (decisoes-v1.md, 77, estendida na rodada 3): texto com quebra gravada e indices
    # que existem
    from desdobra.derivacao import quebras as mod_quebras
    camadas = camadas_do_laudo(laudo)
    ids = [f['id'] for f in briefing['formatos']]
    for k, item in enumerate(briefing.get('quebras_por_familia') or []):
        onde = '/quebras_por_familia/%d' % k
        if not _decisao_valida(item['quebras']):
            erros.append(_erro('pendente_obrigatorio', onde))
            continue
        c = camadas.get(item['layer_id'])
        n = len(mod_quebras.posicoes_de_quebra(c)) if c is not None and c.get('tipo') == 'texto' else 0
        valor = item['quebras']['valor']
        if not n or any(x >= n for x in valor) or len(set(valor)) != len(valor):
            erros.append(_erro('quebra_aprovada_invalida', onde, layer_id=item['layer_id']))
            continue
        # caixa de paragrafo: o render refaz a quebra automatica na largura da caixa (revisao 3, A2)
        if (c.get('texto') or {}).get('tipo_caixa') == 'paragrafo':
            erros.append(_erro('quebra_em_caixa_de_paragrafo', onde, layer_id=item['layer_id']))
        rmin, rmax = item.get('razao_min'), item.get('razao_max')
        if item.get('formatos'):
            if any(f not in ids for f in item['formatos']):
                erros.append(_erro('quebra_para_formato_inexistente', onde, layer_id=item['layer_id']))
        elif rmin is not None and rmax is not None and rmin > rmax:
            erros.append(_erro('quebra_com_faixa_invertida', onde, layer_id=item['layer_id']))
    validas = [i for i in briefing.get('quebras_por_familia') or [] if _decisao_valida(i['quebras'])]
    for a_k, a in enumerate(validas):
        for b in validas[a_k + 1:]:
            if a['layer_id'] != b['layer_id'] or sorted(a['quebras']['valor']) == sorted(b['quebras']['valor']):
                continue
            if a.get('formatos') or b.get('formatos'):
                junto = set(a.get('formatos') or ()) & set(b.get('formatos') or ())
            else:
                lo = max(a.get('razao_min') or 0.0, b.get('razao_min') or 0.0)
                hi = min(x for x in (a.get('razao_max'), b.get('razao_max'), float('inf')) if x is not None)
                junto = lo <= hi
            if junto:
                erros.append(_erro('quebras_conflitantes', '/quebras_por_familia', layer_id=a['layer_id']))
    for k, mp in enumerate(briefing['mestres']):
        for el in mp.get('elementos') or []:
            if isinstance(el.get('quebras'), list):
                textos = [x for x in camadas.values() if x.get('tipo') == 'texto' and
                          (x['identidade']['layer_id'] == el['layer_id'] or el['layer_id'] in (x.get('caminho_ids') or []))]
                if len(textos) > 1:
                    erros.append(_erro('quebras_da_mestre_propria_ambiguas', '/mestres/%d' % k, layer_id=el['layer_id']))
    if not raizes and not any(e['codigo'] in ('camada_sem_funcao', 'coberta_sem_decisao', 'quadro_sem_escolha',
                                              'quadro_invalido') for e in erros):
        erros.append(_erro('mestre_sem_elemento'))
    for raiz, funcao in sorted(raizes.items()):
        x, y = ancora_do_elemento(briefing, raiz, funcao)
        if x is None or y is None:
            erros.append(_erro('ancora_faltando', layer_id=raiz, funcao=funcao))
    ids = [f['id'] for f in briefing['formatos']]
    if len(ids) != len(set(i.lower() for i in ids)):
        erros.append(_erro('formato_repetido', '/formatos'))
    for k, ident in enumerate(ids):
        if ident.lower() in IDS_DO_MOTOR + IDS_DO_WINDOWS:
            erros.append(_erro('formato_id_reservado', '/formatos/%d/id' % k))
    # as familias da tela (decisoes-v1.md, 167): cada formato numa familia so, e so formatos do briefing
    vistos = set()
    for k, comp in enumerate(briefing.get('composicoes') or []):
        onde = '/composicoes/%d' % k
        if any(f not in ids for f in comp['formatos']):
            erros.append(_erro('composicao_com_formato_inexistente', onde))
        if vistos & set(comp['formatos']) or len(set(comp['formatos'])) != len(comp['formatos']):
            erros.append(_erro('formato_em_duas_composicoes', onde))
        vistos.update(comp['formatos'])
    if sum(1 for m in briefing['mestres'] if m['tipo'] == 'kv') != 1:
        erros.append(_erro('mestre_invalida', '/mestres'))
    for k, m in enumerate(briefing['mestres']):
        if m['tipo'] == 'propria' and m.get('formato') not in ids:
            erros.append(_erro('mestre_invalida', '/mestres/%d' % k))
    return erros


# ------------------------------------------------------------------ gravacao
def _quem():
    try:
        usuario = getpass.getuser()
    except Exception:  # noqa: BLE001
        usuario = None
    return {'usuario': usuario, 'maquina': _platform.node() or None}


def importar_teste(pasta, arquivo):
    """Grava em briefing/briefing-confirmado.json o briefing escrito a mao, com a origem fixture_de_teste e o
    cabecalho dos arquivos do job de agora. Recusa (ErroBriefing) o briefing que nao passa no esquema ou na
    conferencia, e nunca grava por cima de um briefing confirmado pelo DA."""
    pasta = Path(pasta).resolve()
    estado = contratos.ler(pasta / 'estado.json', 'estado/1')
    laudo = contratos.ler(pasta / ARQUIVO_LAUDO, 'laudo/1')
    dados = arquivos.ler_json(arquivo)
    if not isinstance(dados, dict):
        raise ErroBriefing('O arquivo do briefing não é um objeto JSON.', codigo='uso')
    dados = dict(dados)
    dados.setdefault('esquema', ESQUEMA)
    dados['job_id'] = dados.get('job_id') or estado['job_id']
    dados['cabecalho'] = dict(hashes_atuais(pasta), origem=ORIGEM_FIXTURE, meio='importar_teste', por=_quem(),
                              quando=agora(), importado_sha256=arquivos.sha256_arquivo(arquivo))
    try:
        contratos.validar(dados, ESQUEMA, origem=str(arquivo))
    except contratos.ErroContrato as e:
        raise ErroBriefing('O briefing não segue o contrato briefing/1: %s' % e,
                           [{'codigo': 'contrato', 'descricao': str(e), 'onde': e.onde}]) from None
    erros = conferir(laudo, dados, estado['job_id'])
    if erros:
        raise ErroBriefing('O briefing tem %d problema(s).' % len(erros), erros)
    atual = Path(pasta) / ARQUIVO
    if atual.is_file():
        try:
            velho = contratos.ler(atual, ESQUEMA)
        except contratos.ErroContrato:
            raise ErroBriefing('O briefing gravado no job não segue o contrato briefing/1. O importar --teste não grava '
                               'por cima dele: confira o arquivo briefing/briefing-confirmado.json.',
                               codigo='recusado') from None
        if velho['cabecalho']['origem'] == ORIGEM_DA:
            raise ErroBriefing('O job já tem briefing confirmado pelo DA. O importar --teste nunca grava por cima dele.',
                               codigo='recusado')
    gravar_com_historico(pasta, dados)
    return dados


def gravar_com_historico(pasta, dados, *, disparo=None):
    """Grava o briefing confirmado; a versao anterior, quando ha, fica em briefing/historico/<sha256>.json (proposta do
    M7, parametros: toda gravacao guarda a anterior). Devolve o caminho da versao guardada, ou None.
    disparo: o do "briefing confirmar" (da tela ou do terminal), de uso unico, gasto aqui; a origem do cabecalho tem
    de ser a dele. Sem disparo, so o briefing de teste (origem fixture_de_teste, o importar --teste) e gravado
    (revisao do M7a): ErroBriefing para o resto, humano.ErroHumano com disparo sem conferencia."""
    origem = (dados.get('cabecalho') or {}).get('origem')
    if disparo is None:
        if origem != ORIGEM_FIXTURE:
            raise ErroBriefing('O briefing confirmado só é gravado com a confirmação do DA.', codigo='recusado')
    else:
        from desdobra import humano
        if getattr(disparo, 'origem', None) != origem:
            raise humano.ErroHumano('disparo_de_outra_origem')
        humano.conferir(disparo, 'briefing confirmar', consumir=True)
    atual = Path(pasta) / ARQUIVO
    guardada = None
    if atual.is_file():
        hist = Path(pasta) / PASTA_HISTORICO
        hist.mkdir(parents=True, exist_ok=True)
        guardada = hist / ('%s.json' % arquivos.sha256_arquivo(atual))
        arquivos.gravar_bytes_atomico(guardada, atual.read_bytes())
    contratos.gravar(atual, dados, ESQUEMA)
    return guardada


def conferir_para_entrega(pasta):
    """(pode, motivo). O entregar (M6) recusa todo job cujo briefing seja fixture de teste (arquitetura-v1.md, 5.3) ou
    rascunho, sem briefing, com briefing desatualizado ou com briefing que nao passa na conferencia (pendente
    obrigatorio, camada sem funcao e o resto de conferir). O arquivo nao carrega prova de quem o gravou (o cabecalho e
    dado sem segredo): o portao confere origem, hashes e conteudo, e a familia so vale com a confirmacao do DA na
    janela (desdobra.entrega.portao.conferir_familia). O que impede o Claude de gravar o arquivo e o gancho
    (scripts/gancho_confirmacoes.py); o arquivo escrito a mao por outro caminho e risco residual declarado (revisao do
    M7a)."""
    try:
        b = ler(pasta)
    except contratos.ErroContrato:
        return False, 'briefing_invalido'
    if b is None:
        return False, 'sem_briefing'
    if b['cabecalho']['origem'] == ORIGEM_FIXTURE:
        return False, 'briefing_de_fixture_de_teste'
    if b['cabecalho']['origem'] == ORIGEM_RASCUNHO:
        return False, 'briefing_rascunho'
    if b['cabecalho']['origem'] != ORIGEM_DA:
        return False, 'briefing_sem_origem_do_da'
    if desatualizado(pasta, b):
        return False, 'briefing_desatualizado'
    try:
        estado = contratos.ler(Path(pasta) / 'estado.json', 'estado/1')
        laudo = contratos.ler(Path(pasta) / ARQUIVO_LAUDO, 'laudo/1')
    except (contratos.ErroContrato, OSError):
        return False, 'briefing_desatualizado'
    if conferir(laudo, b, estado['job_id']):
        return False, 'briefing_com_problema'
    return True, None


def destino_do_rascunho(pasta, saida=None):
    """Caminho onde o rascunho pode ser gravado, ou None quando o destino e recusado. Dentro da pasta do job, so em
    rotulagem/ (nunca em briefing/, specs/, render/, derivacao/, entrada/, laudo/ nem em arquivo do DA). O caminho e
    resolvido de verdade (.., juncao e link simbolico) antes da conferencia."""
    import os
    destino = Path(saida) if saida else Path(pasta) / ARQUIVO_RASCUNHO
    real = Path(os.path.realpath(destino))
    job = Path(os.path.realpath(pasta))
    try:
        rel = real.relative_to(job)
    except ValueError:
        return real
    partes = rel.parts
    if len(partes) >= 2 and partes[0].lower() == PASTA_RASCUNHO_NO_JOB:  # numero-neutro: pasta e arquivo
        return real
    return None


def rascunho(pasta):
    """Rascunho do briefing para o DA preencher (instrumento da rotulagem): todos os campos de decisao sem valor
    (situacao pendente), um item por grupo do topo do quadro e por camada desenhavel, e a sugestao citada da regra da
    decisao 10 nas cobertas. Nao grava: devolve o dicionario e as contagens."""
    pasta = Path(pasta).resolve()
    estado = contratos.ler(pasta / 'estado.json', 'estado/1')
    laudo = contratos.ler(pasta / ARQUIVO_LAUDO, 'laudo/1')
    pend = {'valor': None, 'situacao': 'pendente', 'origem': {'tipo': 'da', 'ref': None}}
    funcoes, cobertas, grupos = [], [], set()
    for c in laudo['camadas']:
        if not desenhavel(c):
            continue
        for g in c.get('caminho_ids') or []:
            grupos.add(g)
    for c in laudo['camadas']:
        lid = c['identidade']['layer_id']
        if c.get('tipo') in TIPOS_SEM_DESENHO and lid not in grupos:
            continue
        if c.get('tipo') not in TIPOS_SEM_DESENHO and not desenhavel(c):
            continue
        funcoes.append({'layer_id': lid, 'funcao': dict(pend), 'observacao': None})
        cob = (c.get('geometria') or {}).get('coberta_no_kv') or {}
        if cob.get('coberta'):
            cobertas.append({'layer_id': lid, 'decisao': dict(pend)})
    dados = {'esquema': ESQUEMA, 'job_id': estado['job_id'],
             'cabecalho': dict(hashes_atuais(pasta), origem=ORIGEM_RASCUNHO, meio='rascunho', por=_quem(),
                                  quando=agora()),
             'quadro': dict(pend), 'funcoes': funcoes, 'cobertas': cobertas, 'regras_escala': [],
             'regras_indeterminado': [], 'ancoras': [], 'formatos': [], 'mestres': [{'id': 'kv', 'tipo': 'kv'}],
             'modo_dados': dict(pend)}
    contratos.validar(dados, ESQUEMA)
    return dados, {'decisoes_de_funcao': len(funcoes), 'grupos': len(grupos), 'cobertas': len(cobertas)}


def _id_do_formato(chave, vistos):
    """O id do formato na pasta do job a partir da chave da folha (veiculador|circuito|LxA): minusculas, letras e
    digitos, o resto vira hifen. O id repetido, ou um nome que o motor ou o Windows ja usam, ganha -2, -3..."""
    import re
    base = re.sub('-+', '-', re.sub('[^a-z0-9]+', '-', chave.lower())).strip('-') or 'formato'
    ident, n = base, 1
    while ident in vistos or ident in IDS_DO_MOTOR + IDS_DO_WINDOWS:
        n += 1
        ident = '%s-%d' % (base, n)
    vistos.add(ident)
    return ident


def formatos_das_specs(pasta, ids_de_antes=None):
    """Os formatos do briefing que saem das specs do job, na ordem da folha: cada formato com chave e dimensao em px,
    com a largura e a altura da folha. ids_de_antes: {chave: id} do briefing gravado (a retomada): a chave que ele ja
    tem fica com o id dele, e o id de uma chave que saiu da folha nunca vai para outra (revisao da correcao dos
    becos: as mestres, as quebras e as familias seguem pelo id). A lista sai do rascunho das specs, que tem todos os formatos da folha: os
    formatos do job (formatos-do-job.json) so tem os confirmados, e confirmar a medida de um formato tiraria os outros
    do briefing (revisao do M7a). A rotacao fica de fora: a folha a traz em texto, e o giro e decisao do DA (o rascunho
    da tela, desdobra.briefing.salvar.escolhas_do_passo_1)."""
    arq = Path(pasta) / ARQUIVO_RASCUNHO_SPECS
    if not arq.is_file():
        arq = Path(pasta) / ARQUIVO_FORMATOS
    try:
        dados = arquivos.ler_json(arq) if arq.is_file() else {}
    except (OSError, ValueError):
        dados = {}
    saida, vistos = [], set()
    for f in (dados or {}).get('formatos') or []:
        chave = f.get('chave')
        dim = (f.get('campos') or {}).get('dimensao') or {}
        v = dim.get('valor') if isinstance(dim, dict) else None
        if not isinstance(chave, str) or not chave or (dim.get('unidade') or 'px') != 'px' or not isinstance(v, dict):
            continue
        try:
            largura, altura = int(round(float(v['largura']))), int(round(float(v['altura'])))
        except (KeyError, TypeError, ValueError):
            continue
        if largura < 1 or altura < 1:
            continue
        partes = chave.split('|')
        tem_nivel = len(partes) > 2  # numero-neutro: veiculador|circuito|LxA
        saida.append({'id': None, 'chave': chave,
                      'veiculador': partes[0] if tem_nivel else None, 'circuito': partes[1] if tem_nivel else None,
                      'largura': largura, 'altura': altura})
    # o id do briefing de antes vale primeiro; o resto sai na ordem da chave exata, e nunca na da folha: as chaves que
    # dao o mesmo id base (maiuscula ou pontuacao) ficam com o mesmo sufixo se a folha mudar de ordem (revisao dos
    # becos, A3)
    antes = {k: v for k, v in (ids_de_antes or {}).items() if isinstance(k, str) and isinstance(v, str) and v}
    vistos.update(v for v in antes.values() if v not in IDS_DO_MOTOR + IDS_DO_WINDOWS)
    for f in saida:
        if antes.get(f['chave']) in vistos:
            f['id'] = antes[f['chave']]
    for f in sorted(saida, key=lambda f: f['chave']):
        if f['id'] is None:
            f['id'] = _id_do_formato(f['chave'], vistos)
    return saida


def partida(pasta, ids_de_antes=None):
    """O briefing de partida da tela no job sem briefing confirmado (M7a): o rascunho do motor (tudo pendente, sem valor
    inicial; rascunho) com os formatos das specs do job (formatos_das_specs) e a mestre do KV. Nada e gravado: a tela
    parte dele, e "Salvar e seguir" grava o primeiro briefing confirmado por cima do que o DA escolheu. O quadro fica
    pendente: so o DA escolhe de qual prancheta a peca sai (decisao 1)."""
    dados, _contagem = rascunho(pasta)
    dados['formatos'] = formatos_das_specs(pasta, ids_de_antes)
    contratos.validar(dados, ESQUEMA)
    return dados


def retomada(pasta, gravado):
    """O briefing de partida com o que ainda vale do briefing gravado de outra versao do laudo, das specs, do design
    system ou das fontes (revisao do M7a): a tela abre dele e "Salvar e seguir" grava por cima, sem passo no terminal.
    Os formatos sao sempre os das specs de agora (formatos_das_specs), com o id que o gravado ja dava a cada chave, e o
    giro que o DA ja decidiu segue o formato pela chave da folha. Com o mesmo laudo, as decisoes das camadas (prancheta, funcoes, cobertas, regras, ancoras, blocos e
    quebras) e as mestres continuam, menos o que cita formato que as specs nao tem mais; com outro laudo, nenhuma
    decisao das camadas volta (os ids sao de outra leitura do PSD). As familias confirmadas ficam so no rascunho da
    tela. O cabecalho e o do rascunho do motor: o briefing gravado continua o de antes ate o DA salvar. Nao grava."""
    import copy
    dados = partida(pasta, {f['chave']: f['id'] for f in gravado.get('formatos') or [] if f.get('chave')})
    giro = {f['chave']: f['rotacao'] for f in gravado.get('formatos') or [] if f.get('rotacao') is not None}
    for f in dados['formatos']:
        if f['chave'] in giro:
            f['rotacao'] = copy.deepcopy(giro[f['chave']])
    if gravado['cabecalho'].get('laudo_sha256') == dados['cabecalho']['laudo_sha256']:
        ids = {f['id'] for f in dados['formatos']}
        for k in ('quadro', 'funcoes', 'cobertas', 'regras_escala', 'regras_indeterminado', 'ancoras', 'regras_bloco',
                  'familias'):
            if k in gravado:
                dados[k] = copy.deepcopy(gravado[k])
        dados['mestres'] = [copy.deepcopy(m) for m in gravado['mestres']
                            if m['tipo'] != 'propria' or m.get('formato') in ids]
        if 'quebras_por_familia' in gravado:
            dados['quebras_por_familia'] = [copy.deepcopy(q) for q in gravado['quebras_por_familia']
                                            if all(f in ids for f in q.get('formatos') or ())]
    contratos.validar(dados, ESQUEMA)
    return dados


def base_da_tela(pasta):
    """O briefing de onde a tela e o gravador partem: o gravado (confirmado pelo DA ou de teste); sem ele ou com o
    rascunho do motor gravado no lugar, o de partida; com o gravado de outra versao dos arquivos do job, a retomada
    (o de partida com o que ainda vale dele). ErroContrato quando o gravado nao segue o contrato."""
    b = ler(pasta)
    if b is None or b['cabecalho']['origem'] == ORIGEM_RASCUNHO:
        return partida(pasta)
    if desatualizado(pasta, b):
        return retomada(pasta, b)
    return b
