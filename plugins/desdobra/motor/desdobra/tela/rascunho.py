# -*- coding: utf-8 -*-
"""Rascunho da tela de briefing (M7a, fatia 1): briefing/rascunho.json (decisoes-v1.md, 164 e 167; proposta do M7,
164, revisa a 82 so para a tela).

O que o DA escolhe e edita na tela (a versao da galeria e as edicoes de cada familia; no passo 2 e no Design system, a
funcao de cada grupo ou camada, a decisao das cobertas e a regra e a ancora de cada funcao, desdobra.tela.funcoes)
fica salvo sozinho, a cada mudanca, neste arquivo. Regras:
  - so o servidor da tela grava (desdobra.tela.servidor, rota POST /api/rascunho); o gancho nega ao Claude escrever
    em briefing/** (scripts/gancho_confirmacoes.py);
  - o rascunho nunca e o briefing confirmado: o preparar da derivacao e o portao de entrega leem so
    briefing/briefing-confirmado.json (desdobra.briefing.modelo.ARQUIVO). "Salvar e seguir" grava o confirmado;
  - a chave e o hash do laudo: o rascunho gravado com outro laudo (o PSD relido muda os ids das camadas) nunca volta
    calado; ler devolve (None, True) e a tela avisa o DA;
  - o passo 2 e conferido contra o laudo antes da gravacao: indeterminado sem observacao, camada que o laudo nao tem e
    decisao de coberta numa camada que nao e coberta sao recusados (desdobra.tela.funcoes.conferir);
  - a familia confirmada (decisoes-v1.md, 167) so nasce do ato "Confirmar familia" da janela (confirmar_familia, com
    o Disparo da tela); a pagina nunca manda a confirmacao, e a familia que muda depois dela volta a confirmada falsa;
  - a quebra de linha que o DA poe ou tira na familia (M7b, C1; decisoes-v1.md, 167 e 171) e edicao da familia: muda a
    familia como a versao e as edicoes, e a posicao inserida tem de cair num espaco do texto de agora (o do KV ou o
    editado na familia; _conferir_quebras). A quebra que o DA poe ou tira vale aprovada pelo proprio ato (origem da);
    a que o desdobra propos (origem proposta, M7b, C4) espera o clique "Aprovar quebra" da pagina, e a familia com
    quebra por aprovar nunca e confirmada (por_aprovar). Linhas do DA (0.9.4): o texto editado nunca quebra sozinho e
    o desdobra nao propoe quebra nele; a proposta de antes num texto editado sai na leitura da familia que nao esta
    confirmada (sem_proposta_velha);
  - cada familia guarda os formatos que a tela mostrava quando o DA mexeu nela pela ultima vez (revisao do M7b, fase
    A; so o servidor grava, _com_os_formatos): a tela casa o id com o grupo que divide mais formatos com eles
    (desdobra.tela.estado.abas), e a familia que a tela nao mostra mais fica aqui com as edicoes dela;
  - cada familia guarda o arquivo de edicao dela (decisao 199, 1; 0.10.0; so o servidor grava): na primeira gravacao,
    o que a tela mostra pela regra (_com_a_estrutura), e ele fica enquanto o arquivo estiver na familia. So os atos da
    janela o trocam (trocar_arquivo, na familia sem edicao) e separam um arquivo em familia propria (separar e
    juntar, com a lista separados). A confirmacao guarda o arquivo de edicao e o hash do layout de cada arquivo
    (decisao 199, 5); a confirmacao de antes da 0.10.0, sem eles, cai uma vez (confirmada_para), e a tela diz por que
    (desdobra.tela.estado.RECONFIRMAR_0100);
  - gravacao atomica, com o esquema rascunho-tela/1 conferido antes. A origem e 'rascunho', ou 'fixture_de_teste' no
    modo de teste da tela (proposta do M7, 159c).
"""
from pathlib import Path

from desdobra import arquivos, contratos

ESQUEMA = 'rascunho-tela/1'
ARQUIVO = Path('briefing') / 'rascunho.json'
ARQUIVO_LAUDO = Path('laudo') / 'laudo.json'
# o que a pagina manda; o resto (esquema, origem, atualizado_em) e do servidor. Os campos do passo 2 e do Design
# system (desdobra.tela.funcoes) sao opcionais: o rascunho so com as familias continua valendo
CAMPOS_DA_PAGINA = ('job_id', 'laudo_sha256', 'familias')
CAMPOS_DO_PASSO_2 = ('funcoes', 'cobertas', 'design', 'design_camadas')
# as escolhas do passo 1 que mudam o layout (revisao do M7a): a prancheta de onde a peca sai (quadro, id do laudo) e o
# giro de cada formato (rotacoes, pela chave da folha). Vao ao briefing por desdobra.briefing.salvar.escolhas_do_passo_1
CAMPOS_DO_PASSO_1 = ('quadro', 'rotacoes')
# tudo o que, mudado, muda o layout de todas as familias
CAMPOS_DAS_ESCOLHAS = CAMPOS_DO_PASSO_1 + CAMPOS_DO_PASSO_2
# o ato da janela que confirma uma familia (humano.ATOS_DA_TELA)
COMANDO_FAMILIA = 'familia confirmar'
# decisao 199 (0.10.0): os atos da janela que trocam o arquivo de edicao e separam um arquivo em familia propria (e o
# juntam de volta). So o servidor grava estes campos da familia; o que a pagina manda e jogado fora
COMANDO_TROCAR_ARQUIVO = 'familia trocar arquivo'
COMANDO_SEPARAR = 'familia separar'
COMANDO_JUNTAR = 'familia juntar'
CAMPOS_DO_SERVIDOR = ('confirmacao', 'formatos', 'cedidos', 'arquivo_de_edicao', 'separados', 'layout_mudou',
                      'arquivo_trocado')


class ErroRascunho(Exception):
    """O rascunho mandado pela pagina foi recusado. O motivo e um codigo fixo, que nao vai a pagina."""

    def __init__(self, motivo):
        super().__init__(motivo)
        self.motivo = motivo


def laudo_sha256(pasta):
    """Hash do laudo do job agora, ou None quando o job ainda nao tem laudo."""
    arq = Path(pasta) / ARQUIVO_LAUDO
    return arquivos.sha256_arquivo(arq) if arq.is_file() else None


def ler(pasta, laudo_atual):
    """(rascunho, de_outro_laudo). (None, False) sem arquivo; (None, True) quando o arquivo e de outro laudo, nao segue
    o esquema ou nao se le: o rascunho velho nunca volta calado."""
    arq = Path(pasta) / ARQUIVO
    if not arq.is_file():
        return None, False
    try:
        dados = contratos.ler(arq, ESQUEMA)
    except contratos.ErroContrato:
        return None, True
    if laudo_atual is None or dados['laudo_sha256'] != laudo_atual:
        return None, True
    return sem_proposta_velha(dados), False


def _proposta_no_editado(f, q):
    """A quebra q da familia f e a proposta do desdobra (aprovada ou nao) num texto editado pelo DA na familia."""
    from desdobra.derivacao import quebras as mq
    return q.get('origem') == 'proposta' and mq.texto_editado(f.get('edicoes'), q.get('elemento')) is not None


def sem_proposta_velha(dados):
    """Linhas do DA (0.9.4): o desdobra nao propoe mais quebra no texto editado. Na familia que nao esta confirmada, a
    quebra proposta de antes num texto editado (aprovada ou nao) sai na leitura, e as linhas voltam a ser as do DA: o
    rascunho velho nunca trava a confirmacao (por_aprovar) nem a previa. A familia confirmada fica como o DA a
    confirmou (a proposta aprovada e decisao dele). Devolve os dados, no lugar."""
    for f in (dados.get('familias') or {}).values():
        if not isinstance(f, dict) or f.get('confirmada') or not f.get('quebras'):
            continue
        f['quebras'] = [q for q in f['quebras'] if not _proposta_no_editado(f, q)]
    return dados


def origem_gravada(pasta):
    """A origem do rascunho que esta no job, sem conferir o esquema (None sem arquivo ou ilegivel)."""
    try:
        dados = arquivos.ler_json(Path(pasta) / ARQUIVO)
    except (OSError, ValueError):
        return None
    return dados.get('origem') if isinstance(dados, dict) else None


def gravar(pasta, recebido, *, job_id, laudo_atual, origem, familias_da_tela=None, elementos_da_tela=None,
           arquivos_da_tela=None):
    """Confere o rascunho mandado pela pagina e grava de forma atomica. ErroRascunho quando ele e de outro job, de
    outro laudo, nao segue o esquema, cita um elemento que a mestre da tela nao tem ou um grupo que nao comeca pelo
    elemento da edicao (desdobra.tela.edicao.ids_conferem, 'edicao') ou leva um elemento a um tamanho fora dos limites
    da escala (desdobra.tela.edicao.escala_fora, M7b, D3). Essas duas conferencias valem so para a familia com edicao
    nova, e o tamanho que o rascunho gravado ja tinha fora dos limites passa enquanto nao for para mais longe deles
    (revisao 1 da fase D): o que ja estava gravado nunca trava o job.
    familias_da_tela: {id: [formatos]} das familias que a tela mostra
    agora (o servidor da tela); com elas, cada familia guarda os formatos de quando o DA mexeu nela (_com_os_formatos).
    elementos_da_tela: {id do elemento: [layer_ids]} da mestre que a tela mostra agora; com eles, a quebra de linha
    so cita o elemento que existe e uma camada dele (_conferir_quebras). arquivos_da_tela: {id: arquivo de edicao}
    que a tela mostra agora (decisao 199, 1); com eles, a familia sem arquivo de edicao gravado (ou com um que saiu
    dela) grava o da tela (_com_a_estrutura). Devolve o que foi gravado."""
    from desdobra.briefing import modelo
    from desdobra.tela import funcoes
    if not isinstance(recebido, dict) or not set(CAMPOS_DA_PAGINA) <= set(recebido) or             not set(recebido) <= set(CAMPOS_DA_PAGINA + CAMPOS_DAS_ESCOLHAS):
        raise ErroRascunho('campos')
    if recebido['job_id'] != job_id:
        raise ErroRascunho('outro_job')
    if laudo_atual is None or recebido['laudo_sha256'] != laudo_atual:
        raise ErroRascunho('outro_laudo')
    familias = _familias_com_a_confirmacao(pasta, recebido['familias'], laudo_atual)
    anterior, _de_outro = ler(pasta, laudo_atual)
    familias = _com_os_formatos(familias, (anterior or {}).get('familias') or {}, familias_da_tela or {})
    familias = _com_a_estrutura(familias, (anterior or {}).get('familias') or {}, familias_da_tela or {},
                                arquivos_da_tela or {})
    if any((recebido.get(k) or {}) != ((anterior or {}).get(k) or {}) for k in CAMPOS_DAS_ESCOLHAS):
        # a prancheta, o giro, o passo 2 e o Design system mudam o layout de todas as familias: nenhuma confirmacao
        # fica (revisao do M7a)
        familias = {g: dict({k: v for k, v in f.items() if k != 'confirmacao'}, confirmada=False)
                    for g, f in familias.items()}
    dados = {'esquema': ESQUEMA, 'job_id': job_id, 'laudo_sha256': laudo_atual, 'origem': origem,
             'atualizado_em': modelo.agora(), 'familias': familias}
    dados.update({k: recebido[k] for k in CAMPOS_DAS_ESCOLHAS if k in recebido})
    try:
        contratos.validar(dados, ESQUEMA)
    except contratos.ErroContrato:
        raise ErroRascunho('esquema') from None
    from desdobra.tela import edicao
    gravadas = {g: (f.get('edicoes') or []) for g, f in ((anterior or {}).get('familias') or {}).items()}
    # so a familia com edicao nova passa pela conferencia das edicoes (revisao 1 da fase D): o que ja estava gravado
    # nunca trava o rascunho inteiro
    novas = {g: f.get('edicoes') or [] for g, f in familias.items() if (f.get('edicoes') or []) != gravadas.get(g, [])}
    if not all(edicao.ids_conferem(eds, elementos_da_tela) for eds in novas.values()):
        # os elementos que existem na mestre da tela, e o grupo (M7b, D1) com o elemento da edicao primeiro, como a
        # previa confere
        raise ErroRascunho('edicao')
    if any(edicao.escala_fora(eds, gravadas.get(g)) for g, eds in novas.items()):
        # o tamanho de cada elemento entre os limites da escala (M7b, D3), como a previa confere; o tamanho que o
        # rascunho gravado ja tinha fora deles passa, enquanto nao for para mais longe
        raise ErroRascunho('escala')
    if any(f.get('quebras') for f in familias.values()):
        # a quebra cita a camada de texto e a posicao no texto de agora: confere contra o laudo
        laudo = _laudo(pasta)
        if laudo is None:
            raise ErroRascunho('laudo')
        _conferir_quebras(familias, laudo, elementos_da_tela)
    if any(k in dados for k in CAMPOS_DO_PASSO_2):
        # o passo 2 cita camadas: confere contra o laudo (indeterminado sem observacao, camada que nao existe)
        laudo = _laudo(pasta)
        if laudo is None:
            raise ErroRascunho('laudo')
        erros = funcoes.conferir(dados, laudo)
        if erros:
            raise ErroRascunho(erros[0])
    if dados.get('quadro') is not None:
        # a prancheta so entre as do laudo (decisao 1): o PSD sem prancheta nao tem o que escolher
        laudo = _laudo(pasta)
        quadros = {q.get('id') for q in ((laudo or {}).get('documento') or {}).get('quadros') or []}
        if dados['quadro'] not in quadros:
            raise ErroRascunho('quadro')
    try:
        contratos.gravar(Path(pasta) / ARQUIVO, dados, ESQUEMA)
    except contratos.ErroContrato:
        raise ErroRascunho('esquema') from None
    return dados


def _escolhas_da_familia(f):
    """O que o DA escolheu e editou na familia: a versao, as edicoes e as quebras de linha (M7b, C1). Mudar qualquer
    uma tira a confirmacao."""
    return (f.get('versao'), f.get('edicoes') or [], f.get('quebras') or [])


def por_aprovar(f):
    """As quebras de linha da familia f (do rascunho) que o desdobra propos e o DA ainda nao aprovou (M7b, C4). A
    proposta num texto editado nunca espera (Linhas do DA, 0.9.4: sem_proposta_velha)."""
    return [q for q in (f or {}).get('quebras') or [] if q.get('origem') == 'proposta' and not q.get('aprovada')
            and not _proposta_no_editado(f, q)]


def _conferir_quebras(familias, laudo, elementos=None):
    """As quebras de linha de cada familia contra o laudo (M7b, C1): uma por texto na familia, camada de texto do
    laudo, e os indices e as posicoes no texto de agora (o do KV, ou o editado pelo DA na familia, decisoes-v1.md, 171;
    desdobra.derivacao.quebras.conferir_da_familia). Com os elementos da tela ({id: [layer_ids]}), o elemento citado
    existe e tem a camada, como a previa confere (desdobra.tela.edicao.Editor._quebras_conferem; revisao 2 do C): o
    texto editado que conta e o desse elemento. ErroRascunho('quebras') no resto. O briefing confere de novo, com o
    elemento resolvido pelas funcoes (desdobra.briefing.modelo.conferir)."""
    from desdobra.derivacao import quebras as mq
    camadas = {c['identidade']['layer_id']: c for c in laudo['camadas']}
    for f in familias.values():
        vistos = set()
        for q in f.get('quebras') or []:
            c = camadas.get(q['layer_id'])
            if q['layer_id'] in vistos or c is None or c.get('tipo') != 'texto':
                raise ErroRascunho('quebras')
            if elementos is not None and q['layer_id'] not in (elementos.get(q['elemento']) or ()):
                raise ErroRascunho('quebras')
            vistos.add(q['layer_id'])
            editado = mq.texto_editado(f.get('edicoes'), q['elemento'])
            if mq.conferir_da_familia(c, q['manter'], q['inseridas'], editado) is not None:
                raise ErroRascunho('quebras')


def _familias_com_a_confirmacao(pasta, familias, laudo_atual):
    """As familias da pagina com a confirmacao que so o ato da janela grava (decisoes-v1.md, 167): a pagina nunca manda
    a confirmacao (o que ela manda e jogado fora); uma familia marcada confirmada so passa quando ja estava confirmada
    no rascunho gravado, com a mesma versao, as mesmas edicoes e as mesmas quebras, e leva a confirmacao gravada.
    Mexer depois da confirmacao pede confirmada falsa. ErroRascunho('confirmacao') no resto."""
    if not isinstance(familias, dict):
        raise ErroRascunho('esquema')
    anterior, _de_outro = ler(pasta, laudo_atual)
    gravadas = (anterior or {}).get('familias') or {}
    saida = {}
    for gid, f in familias.items():
        if not isinstance(f, dict):
            raise ErroRascunho('esquema')
        f = {k: v for k, v in f.items() if k not in CAMPOS_DO_SERVIDOR}
        if f.get('confirmada') is True:
            g = gravadas.get(gid) or {}
            if not g.get('confirmada') or _escolhas_da_familia(g) != _escolhas_da_familia(f):
                raise ErroRascunho('confirmacao')
            f['confirmacao'] = g['confirmacao']
        saida[gid] = f
    return saida


def _com_os_formatos(familias, gravadas, tela):
    """As familias da pagina com os formatos de cada uma (revisao do M7b, fase A), que so o servidor grava: a pagina
    nunca os manda (o que ela manda ja saiu em _familias_com_a_confirmacao). A familia que o DA mexeu agora (versao,
    edicoes ou quebras diferentes das gravadas, ou nova no rascunho) leva os formatos que a tela mostra para ela; a que
    nao mudou guarda os de antes, e assim a tela continua avisando que ela ganhou ou perdeu formatos ate o DA mexer
    nela ou confirma-la. A familia que a tela nao mostra mais guarda os formatos gravados, com as edicoes. Os formatos
    que a familia mexida agora leva de outra familia ficam marcados nesta (cedidos, _ceder)."""
    saida, mexidas = {}, []
    for gid, f in familias.items():
        g = gravadas.get(gid) or {}
        mudou = not g or _escolhas_da_familia(g) != _escolhas_da_familia(f)
        if mudou and gid in tela:
            saida[gid] = dict(f, formatos=list(tela[gid]))
            mexidas.append(gid)
            continue
        # o rascunho de antes desta revisao: os formatos da confirmacao, quando houver
        fids = g.get('formatos', (g.get('confirmacao') or {}).get('formatos'))
        if fids is None and gid in tela:
            fids = tela[gid]
        saida[gid] = dict(f, formatos=list(fids)) if fids is not None else dict(f)
        if g.get('cedidos'):
            saida[gid]['cedidos'] = list(g['cedidos'])
    for gid in mexidas:
        _ceder(saida, gid, tela[gid])
    return saida


def _ceder(familias, gid, formatos):
    """A familia gid acabou de ser mexida (ou confirmada) com estes formatos: cada outra familia que ainda os tem na
    lista dela (a lista de quando o DA mexeu nela, revisao do M7b, fase A) guarda em cedidos os que gid levou. A
    lista fica, e a tela continua dizendo que o formato saiu; quando ele volta, ele entrou de novo (o DA mexeu nele
    em outra familia no meio tempo), e a confirmacao velha nao vale (confirmada_para). Muda familias no lugar."""
    levados = set(formatos)
    for g, f in familias.items():
        comum = levados & set(f.get('formatos') or ()) if g != gid else set()
        if comum:
            f['cedidos'] = sorted(comum | set(f.get('cedidos') or ()))


def _com_a_estrutura(familias, gravadas, tela, arquivos):
    """As familias da pagina com o arquivo de edicao e os separados (decisao 199; 0.10.0), que so o servidor grava: a
    pagina nunca os manda (o que ela manda ja saiu em _familias_com_a_confirmacao). Cada familia guarda os gravados.
    A familia que a tela mostra (tela: {id: [formatos]}) sem arquivo de edicao gravado, ou com um que nao esta mais
    nela, grava o que a tela mostra (arquivos: {id: arquivo}, a regra de desdobra.derivacao.proposta.arquivo_de_edicao):
    a escolha fica estavel dali em diante, e o arquivo maior que entra depois nao troca. Este e o caminho da migracao do
    rascunho de antes da 0.10.0: ele recebe o arquivo de edicao pela regra na primeira gravacao."""
    saida = {}
    for gid, f in familias.items():
        g = gravadas.get(gid) or {}
        f = dict(f)
        for k in ('arquivo_de_edicao', 'separados', 'layout_mudou', 'arquivo_trocado'):
            if g.get(k):
                f[k] = list(g[k]) if isinstance(g[k], list) else g[k]
        if gid in tela and arquivos.get(gid) and f.get('arquivo_de_edicao') not in tela[gid]:
            if f.get('arquivo_de_edicao') and (f.get('edicoes') or f.get('quebras')):
                # o arquivo em que o DA editou saiu da familia, e as edicoes dele (fracoes do arquivo de edicao)
                # passam a valer no arquivo da regra: a tela diz isso ate o DA confirmar de novo (revisao da 0.10.0;
                # nada calado)
                f['arquivo_trocado'] = {'de': f['arquivo_de_edicao'], 'para': arquivos[gid]}
            f['arquivo_de_edicao'] = arquivos[gid]
        saida[gid] = f
    return saida


def _familia_gravada(pasta, familia, laudo_atual, job_id):
    """(dados do rascunho, familia) gravados agora para os atos da estrutura (trocar_arquivo, separar e juntar)."""
    if laudo_atual is None or laudo_sha256(pasta) != laudo_atual:
        raise ErroRascunho('outro_laudo')
    dados, _de_outro = ler(pasta, laudo_atual)
    if dados is None:
        dados = {'esquema': ESQUEMA, 'job_id': job_id, 'laudo_sha256': laudo_atual, 'familias': {}}
    return dados, dict(dados['familias'].get(familia) or {'versao': None, 'confirmada': False, 'edicoes': []})


def _gravar_estrutura(pasta, dados, mudadas, disparo):
    """Grava o rascunho com as familias mudadas por um ato da estrutura: cada uma perde a confirmacao (a familia
    mudou de arquivos ou de arquivo de edicao, e o DA confere de novo)."""
    from desdobra.briefing import modelo
    familias = dict(dados['familias'])
    for gid, f in mudadas.items():
        f = {k: v for k, v in f.items() if k != 'confirmacao'}
        f['confirmada'] = False
        familias[gid] = f
    teste = disparo.origem == modelo.ORIGEM_FIXTURE
    dados = dict(dados, familias=familias, origem=modelo.ORIGEM_FIXTURE if teste else modelo.ORIGEM_RASCUNHO,
                 atualizado_em=modelo.agora())
    contratos.gravar(Path(pasta) / ARQUIVO, dados, ESQUEMA)
    return dados


def trocar_arquivo(pasta, familia, arquivo, *, disparo, job_id, laudo_atual, formatos):
    """O ato "Trocar arquivo de edicao" da janela (decisao 199, 1; resposta 2 do Duda em 18/11): a familia sem edicao
    nem quebra de linha passa a ser editada em outro arquivo dela (formatos: os da familia na tela agora). A versao da
    galeria sai (a galeria e do arquivo de edicao) e a confirmacao cai. ErroRascunho('com_edicao') na familia com
    edicao; ErroRascunho('arquivo') no arquivo que nao e da familia. O Disparo vale um ato so."""
    from desdobra import humano
    humano.conferir(disparo, COMANDO_TROCAR_ARQUIVO, consumir=True)
    dados, f = _familia_gravada(pasta, familia, laudo_atual, job_id)
    if f.get('edicoes') or f.get('quebras'):
        raise ErroRascunho('com_edicao')
    if arquivo not in formatos:
        raise ErroRascunho('arquivo')
    f.update(arquivo_de_edicao=arquivo, versao=None, formatos=list(formatos))
    f.pop('cedidos', None)
    f.pop('arquivo_trocado', None)
    return _gravar_estrutura(pasta, dados, {familia: f}, disparo)['familias'][familia]


def separar(pasta, familia, arquivo, *, disparo, job_id, laudo_atual, formatos, arquivo_de_edicao):
    """O ato "Separar em familia propria" da janela (decisao 199, 3): o arquivo (nunca o de edicao) sai da familia e
    vira uma familia com ele de arquivo de edicao. A familia de onde ele saiu guarda o arquivo em separados e perde a
    confirmacao; os formatos dela passam a ser os que ficam (a tela nao diz que ele "saiu": foi o DA que o tirou).
    ErroRascunho('arquivo') no arquivo de edicao, no que nao e da familia ou na familia de um arquivo so."""
    from desdobra import humano
    humano.conferir(disparo, COMANDO_SEPARAR, consumir=True)
    dados, f = _familia_gravada(pasta, familia, laudo_atual, job_id)
    if arquivo not in formatos or arquivo == arquivo_de_edicao or len(formatos) < 2:  # numero-neutro: familia de um so
        raise ErroRascunho('arquivo')
    f['separados'] = sorted(set(f.get('separados') or ()) | {arquivo})
    f['formatos'] = [x for x in formatos if x != arquivo]
    f.setdefault('arquivo_de_edicao', arquivo_de_edicao)
    f.pop('cedidos', None)
    return _gravar_estrutura(pasta, dados, {familia: f}, disparo)['familias'][familia]


def juntar(pasta, familia, arquivo, *, disparo, job_id, laudo_atual):
    """O ato "Juntar de volta" da janela (decisao 199, 3): o arquivo separado volta a familia de onde saiu (familia),
    que perde a confirmacao e volta a leva-lo nos formatos. ErroRascunho('arquivo') no arquivo que ela nao separou."""
    from desdobra import humano
    humano.conferir(disparo, COMANDO_JUNTAR, consumir=True)
    dados, f = _familia_gravada(pasta, familia, laudo_atual, job_id)
    if arquivo not in (f.get('separados') or ()):
        raise ErroRascunho('arquivo')
    resto = [x for x in f['separados'] if x != arquivo]
    if resto:
        f['separados'] = resto
    else:
        f.pop('separados')
    if f.get('formatos') is not None and arquivo not in f['formatos']:
        f['formatos'] = list(f['formatos']) + [arquivo]
    return _gravar_estrutura(pasta, dados, {familia: f}, disparo)['familias'][familia]


def derrubar_por_layout(pasta, laudo_atual, quedas):
    """A confirmacao das familias cujo layout saiu diferente do confirmado no "Salvar e seguir" cai (decisao 199, 5;
    revisao da 0.10.0): sem isto, a tela continuava com a familia confirmada, o rodape dizia "Tudo confirmado", e o DA
    nao tinha botao para confirmar de novo. quedas: {id da familia: [arquivos que mudaram]}. Cada familia guarda os
    arquivos em layout_mudou, para a tela dizer quais foram, ate o DA confirmar de novo. Nao precisa de Disparo: e a
    consequencia da conferencia do servidor, e a familia so perde a confirmacao. Devolve o rascunho gravado, ou None."""
    dados, _de_outro = ler(pasta, laudo_atual)
    if dados is None or not quedas:
        return None
    familias = dict(dados['familias'])
    for gid, fids in quedas.items():
        if gid not in familias:
            continue
        f = {k: v for k, v in familias[gid].items() if k != 'confirmacao'}
        f.update(confirmada=False, layout_mudou=sorted(set(fids)))
        familias[gid] = f
    dados = dict(dados, familias=familias)
    contratos.gravar(Path(pasta) / ARQUIVO, dados, ESQUEMA)
    return dados


def estrutura(pasta):
    """({id: arquivo de edicao gravado}, {id: [separados]}) do rascunho gravado agora (decisao 199; 0.10.0), vazios
    sem rascunho valido. A tela (desdobra.tela.estado.abas) e a previa (desdobra.tela.edicao.Editor) os leem."""
    dados, _de_outro = ler(pasta, laudo_sha256(pasta))
    arquivos, separados = {}, {}
    for gid, f in ((dados or {}).get('familias') or {}).items():
        if f.get('arquivo_de_edicao'):
            arquivos[gid] = f['arquivo_de_edicao']
        if f.get('separados'):
            separados[gid] = list(f['separados'])
    return arquivos, separados


def edicoes_gravadas(pasta, familia):
    """As edicoes da familia no rascunho gravado agora ([] sem a familia ou sem rascunho valido)."""
    dados, _de_outro = ler(pasta, laudo_sha256(pasta))
    return ((((dados or {}).get('familias') or {}).get(familia)) or {}).get('edicoes') or []


def versao_gravada(pasta, familia):
    """A versao da galeria que o DA escolheu para a familia no rascunho gravado agora (None sem escolha)."""
    dados, _de_outro = ler(pasta, laudo_sha256(pasta))
    return ((((dados or {}).get('familias') or {}).get(familia)) or {}).get('versao')


def versao_de_agora(versao, versoes):
    """A versao gravada, quando a galeria da familia ainda a tem (versoes: as da tela agora), ou None. A versao que a
    galeria nao tem mais (o rascunho da tela de antes da previa igual ao Salvar, M7b, que oferecia galeria a outros
    formatos devolvidos) nao e escolha do DA: a pagina mostra a familia sem versao e a confirma assim."""
    return versao if versao in (versoes or ()) else None


def quebras_gravadas(pasta, familia):
    """As quebras de linha da familia no rascunho gravado agora ([] sem a familia, sem quebra ou sem rascunho
    valido)."""
    dados, _de_outro = ler(pasta, laudo_sha256(pasta))
    return ((((dados or {}).get('familias') or {}).get(familia)) or {}).get('quebras') or []


def _vista_das_familias(familias):
    return {g: _escolhas_da_familia(f) + (bool(f.get('confirmada')),)
            for g, f in familias.items() if isinstance(f, dict)}


def mesma_vista(pasta, vista):
    """A vista da pagina (o rascunho como a janela o mostra, no formato que a pagina grava) e igual ao rascunho
    gravado agora: as familias (versao, edicoes, quebras e confirmada) e o passo 2 e o Design system. O ato "Salvar e
    seguir" so vale para o que o DA viu (revisao do M7a)."""
    dados, _de_outro = ler(pasta, laudo_sha256(pasta))
    if dados is None or not isinstance(vista, dict) or not isinstance(vista.get('familias'), dict):
        return False
    if vista.get('laudo_sha256') != dados['laudo_sha256']:
        return False
    if _vista_das_familias(vista['familias']) != _vista_das_familias(dados['familias']):
        return False
    return all((vista.get(k) or {}) == (dados.get(k) or {}) for k in CAMPOS_DAS_ESCOLHAS)


def _vale_pela_regra_de_antes(f, conf, antes):
    """A confirmacao feita pela regra de uma previa de antes que mostra a mesma familia: a de antes da decisao 185
    para a familia sem edicao, e a de antes da 0.9.6 para a familia sem texto editado (a caixa do texto editado passou
    a ser a das linhas do DA, e a previa dele muda: a confirmacao cai uma vez)."""
    if antes is None:
        return False
    if not isinstance(antes, dict):
        antes = {'sem_edicao': antes}
    edicoes = f.get('edicoes') or []
    if not edicoes and antes.get('sem_edicao') is not None and conf.get('pecas') == antes['sem_edicao']:
        return True
    sem_texto = not any(isinstance(e, dict) and e.get('acao') == 'texto' for e in edicoes)
    return sem_texto and antes.get('sem_texto') is not None and conf.get('pecas') == antes['sem_texto']


def confirmacao_da_0100(conf):
    """A confirmacao foi feita na tela da 0.10.0 ou depois (decisao 199, 5): ela leva o arquivo de edicao."""
    return bool((conf or {}).get('arquivo_de_edicao'))


def confirmada_de_antes(familia):
    """A familia do rascunho estava confirmada por uma tela de antes da 0.10.0 (a confirmacao sem arquivo de edicao):
    a confirmacao cai uma vez, e a tela diz por que."""
    f = familia or {}
    return bool(f.get('confirmada')) and not confirmacao_da_0100(f.get('confirmacao'))


def confirmada_para(familia, formatos, pecas=None, sem_edicao=None):
    """A familia do rascunho esta confirmada para estes formatos: a confirmacao guarda os formatos que o DA viu
    (revisao do M7a), e a familia de mesmo id que ganhou ou perdeu formatos (desdobra.tela.estado.abas) pede a
    confirmacao de novo. pecas: a impressao do que a tela mostra hoje da familia
    (desdobra.tela.estado.impressao_das_pecas); com ela, a confirmacao vale so se foi feita sobre as mesmas pecas (a
    area de spec e a galeria de cada formato), e a confirmacao sem impressao nao vale (revisao 3 da regra
    spec_por_confirmar). O formato que outra familia levou depois da confirmacao (cedidos) e voltou tambem pede a
    confirmacao de novo: no meio tempo o DA mexeu nele la (revisao do M7b, fase A). sem_edicao: a impressao das
    mesmas pecas pela regra da previa de antes da decisao 185 (estado.REGRA_SEM_EDICAO); vale tambem, so para a
    familia sem edicao do DA, cuja previa e a mesma pelas duas regras. sem_edicao pode ser tambem {'sem_edicao',
    'sem_texto'} (0.9.6): 'sem_texto' e a impressao pela regra de antes das linhas do DA
    (estado.REGRA_SEM_TEXTO_EDITADO), que vale so para a familia sem texto editado, cuja previa nao muda."""
    f = familia or {}
    conf = f.get('confirmacao') or {}
    if pecas is not None and not confirmacao_da_0100(conf):
        # decisao 199 (5; resposta 3 do Duda em 18/11): a confirmacao de antes da 0.10.0 foi feita numa tela em que
        # cada arquivo partia da propria proposta. Agora os outros arquivos seguem o arquivo de edicao, e ela cai uma
        # vez, tambem na familia sem edicao (a tela diz por que, desdobra.tela.estado.RECONFIRMAR_0100). As regras de
        # antes (_vale_pela_regra_de_antes) deixam de salvar essa confirmacao
        return False
    if pecas is not None and conf.get('pecas') != pecas and not _vale_pela_regra_de_antes(f, conf, sem_edicao):
        return False
    if set(f.get('cedidos') or ()) & set(formatos):
        return False
    return bool(f.get('confirmada')) and conf.get('formatos') == list(formatos)


def sem_confirmacao_velha(dados, familias, pecas=None, sem_edicao=None):
    """O rascunho com a confirmacao tirada da familia que hoje tem outros formatos ou outras pecas (ou que a tela nao
    tem mais). familias: {id: [formatos]}; pecas e sem_edicao: {id: impressao} (confirmada_para). Nao grava."""
    if dados is None:
        return None
    saida = dict(dados, familias={})
    for g, f in (dados.get('familias') or {}).items():
        if f.get('confirmada') and not confirmada_para(f, familias.get(g, ()), (pecas or {}).get(g),
                                                       (sem_edicao or {}).get(g)):
            f = {k: v for k, v in f.items() if k != 'confirmacao'}
            f['confirmada'] = False
        saida['familias'][g] = f
    return saida


def confirmar_familia(pasta, familia, versao, *, disparo, job_id, laudo_atual, edicoes=None, formatos=None,
                      pecas=None, quebras=None, versoes=None, arquivo_de_edicao=None, layouts=None):
    """O ato "Confirmar familia" da janela (decisoes-v1.md, 167): a familia fica confirmada no rascunho, com a versao
    mostrada e as edicoes gravadas, e a confirmacao leva a origem e o meio do Disparo da tela e os formatos da familia.
    edicoes e quebras: as edicoes e as quebras de linha que a janela mostrou (revisao do C: a quebra e edicao da
    familia); diferentes das gravadas, ErroRascunho('mudou') e nada e gravado. versoes: as da galeria da familia na
    tela agora; com elas, a versao gravada que a galeria nao tem mais conta como nenhuma (versao_de_agora), e a
    confirmacao grava a versao que a janela mostrou. arquivo_de_edicao e layouts (decisao 199, 5; 0.10.0): o arquivo
    de edicao e o hash do layout de cada arquivo como a janela mostrou; vao a confirmacao (a impressao da 175). A
    familia com
    quebra de linha proposta pelo desdobra e ainda sem a aprovacao do DA nao e confirmada:
    ErroRascunho('quebra_proposta') (M7b, C4). O Disparo vale um ato so. Devolve a familia gravada."""
    from desdobra import humano
    from desdobra.briefing import modelo
    humano.conferir(disparo, COMANDO_FAMILIA, consumir=True)
    if laudo_atual is None or laudo_sha256(pasta) != laudo_atual:
        raise ErroRascunho('outro_laudo')
    dados, _de_outro = ler(pasta, laudo_atual)
    if dados is None:
        dados = {'esquema': ESQUEMA, 'job_id': job_id, 'laudo_sha256': laudo_atual, 'familias': {}}
    f = dict(dados['familias'].get(familia) or {'edicoes': []})
    if edicoes is not None and (f.get('edicoes') or []) != edicoes:
        raise ErroRascunho('mudou')
    if quebras is not None and (f.get('quebras') or []) != quebras:
        raise ErroRascunho('mudou')
    if (f.get('versao') if versoes is None else versao_de_agora(f.get('versao'), versoes)) != versao:
        # a versao confirmada e a que o DA clicou na galeria, gravada no rascunho (revisao do M7a)
        raise ErroRascunho('mudou')
    if por_aprovar(f):
        # a quebra que o desdobra propos pede o clique do DA antes (arquitetura-v1.md, item 9)
        raise ErroRascunho('quebra_proposta')
    conf = {'origem': disparo.origem, 'meio': disparo.meio, 'em': modelo.agora()}
    if formatos is not None:
        conf['formatos'] = list(formatos)
        # a familia passa a ser destes formatos (revisao do M7b, fase A): o aviso de que ela mudou sai com a confirmacao
        f['formatos'] = list(formatos)
        f.pop('cedidos', None)
    if pecas is not None:
        conf['pecas'] = pecas
    if arquivo_de_edicao is not None:
        conf['arquivo_de_edicao'] = arquivo_de_edicao
        f['arquivo_de_edicao'] = arquivo_de_edicao
    if layouts is not None:
        conf['layouts'] = dict(sorted(layouts.items()))
    f.update(versao=versao, confirmada=True, confirmacao=conf)
    f.pop('layout_mudou', None)  # o DA conferiu os arquivos de novo (derrubar_por_layout)
    f.pop('arquivo_trocado', None)  # e viu as edicoes no arquivo de edicao de agora (_com_a_estrutura)
    dados['familias'] = dict(dados['familias'], **{familia: f})
    if formatos is not None:
        # as outras familias que ainda tinham estes formatos na lista guardam que esta os levou
        dados['familias'] = {g: dict(x) for g, x in dados['familias'].items()}
        _ceder(dados['familias'], familia, formatos)
    teste = disparo.origem == modelo.ORIGEM_FIXTURE
    dados.update(origem=modelo.ORIGEM_FIXTURE if teste else modelo.ORIGEM_RASCUNHO, atualizado_em=modelo.agora())
    contratos.gravar(Path(pasta) / ARQUIVO, dados, ESQUEMA)
    return f


def _laudo(pasta):
    """O laudo do job como dado (so as camadas, sem conferir o esquema inteiro), ou None quando nao se le."""
    try:
        laudo = arquivos.ler_json(Path(pasta) / ARQUIVO_LAUDO)
    except (OSError, ValueError):
        return None
    if not isinstance(laudo, dict) or not isinstance(laudo.get('camadas'), list):
        return None
    try:
        {c['identidade']['layer_id'] for c in laudo['camadas']}
    except (KeyError, TypeError):
        return None
    return laudo
