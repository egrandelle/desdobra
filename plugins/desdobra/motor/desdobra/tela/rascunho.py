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
  - cada familia guarda os formatos que a tela mostrava quando o DA mexeu nela pela ultima vez (revisao do M7b, fase
    A; so o servidor grava, _com_os_formatos): a tela casa o id com o grupo que divide mais formatos com eles
    (desdobra.tela.estado.abas), e a familia que a tela nao mostra mais fica aqui com as edicoes dela;
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
    return dados, False


def origem_gravada(pasta):
    """A origem do rascunho que esta no job, sem conferir o esquema (None sem arquivo ou ilegivel)."""
    try:
        dados = arquivos.ler_json(Path(pasta) / ARQUIVO)
    except (OSError, ValueError):
        return None
    return dados.get('origem') if isinstance(dados, dict) else None


def gravar(pasta, recebido, *, job_id, laudo_atual, origem, familias_da_tela=None):
    """Confere o rascunho mandado pela pagina e grava de forma atomica. ErroRascunho quando ele e de outro job, de
    outro laudo ou nao segue o esquema. familias_da_tela: {id: [formatos]} das familias que a tela mostra agora (o
    servidor da tela); com elas, cada familia guarda os formatos de quando o DA mexeu nela (_com_os_formatos).
    Devolve o que foi gravado."""
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


def _familias_com_a_confirmacao(pasta, familias, laudo_atual):
    """As familias da pagina com a confirmacao que so o ato da janela grava (decisoes-v1.md, 167): a pagina nunca manda
    a confirmacao (o que ela manda e jogado fora); uma familia marcada confirmada so passa quando ja estava confirmada
    no rascunho gravado, com a mesma versao e as mesmas edicoes, e leva a confirmacao gravada. Mexer depois da
    confirmacao pede confirmada falsa. ErroRascunho('confirmacao') no resto."""
    if not isinstance(familias, dict):
        raise ErroRascunho('esquema')
    anterior, _de_outro = ler(pasta, laudo_atual)
    gravadas = (anterior or {}).get('familias') or {}
    saida = {}
    for gid, f in familias.items():
        if not isinstance(f, dict):
            raise ErroRascunho('esquema')
        f = {k: v for k, v in f.items() if k not in ('confirmacao', 'formatos', 'cedidos')}
        if f.get('confirmada') is True:
            g = gravadas.get(gid) or {}
            if not g.get('confirmada') or g.get('versao') != f.get('versao') or g.get('edicoes') != f.get('edicoes'):
                raise ErroRascunho('confirmacao')
            f['confirmacao'] = g['confirmacao']
        saida[gid] = f
    return saida


def _com_os_formatos(familias, gravadas, tela):
    """As familias da pagina com os formatos de cada uma (revisao do M7b, fase A), que so o servidor grava: a pagina
    nunca os manda (o que ela manda ja saiu em _familias_com_a_confirmacao). A familia que o DA mexeu agora (versao ou
    edicoes diferentes das gravadas, ou nova no rascunho) leva os formatos que a tela mostra para ela; a que nao mudou
    guarda os de antes, e assim a tela continua avisando que ela ganhou ou perdeu formatos ate o DA mexer nela ou
    confirma-la. A familia que a tela nao mostra mais guarda os formatos gravados, com as edicoes. Os formatos que a
    familia mexida agora leva de outra familia ficam marcados nesta (cedidos, _ceder)."""
    saida, mexidas = {}, []
    for gid, f in familias.items():
        g = gravadas.get(gid) or {}
        mudou = not g or (g.get('versao'), g.get('edicoes') or []) != (f.get('versao'), f.get('edicoes') or [])
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


def edicoes_gravadas(pasta, familia):
    """As edicoes da familia no rascunho gravado agora ([] sem a familia ou sem rascunho valido)."""
    dados, _de_outro = ler(pasta, laudo_sha256(pasta))
    return ((((dados or {}).get('familias') or {}).get(familia)) or {}).get('edicoes') or []


def versao_gravada(pasta, familia):
    """A versao da galeria que o DA escolheu para a familia no rascunho gravado agora (None sem escolha)."""
    dados, _de_outro = ler(pasta, laudo_sha256(pasta))
    return ((((dados or {}).get('familias') or {}).get(familia)) or {}).get('versao')


def _vista_das_familias(familias):
    return {g: (f.get('versao'), f.get('edicoes') or [], bool(f.get('confirmada')))
            for g, f in familias.items() if isinstance(f, dict)}


def mesma_vista(pasta, vista):
    """A vista da pagina (o rascunho como a janela o mostra, no formato que a pagina grava) e igual ao rascunho
    gravado agora: as familias (versao, edicoes e confirmada) e o passo 2 e o Design system. O ato "Salvar e seguir"
    so vale para o que o DA viu (revisao do M7a)."""
    dados, _de_outro = ler(pasta, laudo_sha256(pasta))
    if dados is None or not isinstance(vista, dict) or not isinstance(vista.get('familias'), dict):
        return False
    if vista.get('laudo_sha256') != dados['laudo_sha256']:
        return False
    if _vista_das_familias(vista['familias']) != _vista_das_familias(dados['familias']):
        return False
    return all((vista.get(k) or {}) == (dados.get(k) or {}) for k in CAMPOS_DAS_ESCOLHAS)


def confirmada_para(familia, formatos, pecas=None):
    """A familia do rascunho esta confirmada para estes formatos: a confirmacao guarda os formatos que o DA viu
    (revisao do M7a), e a familia de mesmo id que ganhou ou perdeu formatos (desdobra.tela.estado.abas) pede a
    confirmacao de novo. pecas: a impressao do que a tela mostra hoje da familia
    (desdobra.tela.estado.impressao_das_pecas); com ela, a confirmacao vale so se foi feita sobre as mesmas pecas (a
    area de spec e a galeria de cada formato), e a confirmacao sem impressao nao vale (revisao 3 da regra
    spec_por_confirmar). O formato que outra familia levou depois da confirmacao (cedidos) e voltou tambem pede a
    confirmacao de novo: no meio tempo o DA mexeu nele la (revisao do M7b, fase A)."""
    f = familia or {}
    conf = f.get('confirmacao') or {}
    if pecas is not None and conf.get('pecas') != pecas:
        return False
    if set(f.get('cedidos') or ()) & set(formatos):
        return False
    return bool(f.get('confirmada')) and conf.get('formatos') == list(formatos)


def sem_confirmacao_velha(dados, familias, pecas=None):
    """O rascunho com a confirmacao tirada da familia que hoje tem outros formatos ou outras pecas (ou que a tela nao
    tem mais). familias: {id: [formatos]}; pecas: {id: impressao} (confirmada_para). Nao grava."""
    if dados is None:
        return None
    saida = dict(dados, familias={})
    for g, f in (dados.get('familias') or {}).items():
        if f.get('confirmada') and not confirmada_para(f, familias.get(g, ()), (pecas or {}).get(g)):
            f = {k: v for k, v in f.items() if k != 'confirmacao'}
            f['confirmada'] = False
        saida['familias'][g] = f
    return saida


def confirmar_familia(pasta, familia, versao, *, disparo, job_id, laudo_atual, edicoes=None, formatos=None,
                      pecas=None):
    """O ato "Confirmar familia" da janela (decisoes-v1.md, 167): a familia fica confirmada no rascunho, com a versao
    mostrada e as edicoes gravadas, e a confirmacao leva a origem e o meio do Disparo da tela e os formatos da familia.
    edicoes: as que a janela mostrou; diferentes das gravadas, ErroRascunho('mudou') e nada e gravado. O Disparo vale
    um ato so. Devolve a familia gravada."""
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
    if f.get('versao') != versao:
        # a versao confirmada e a que o DA clicou na galeria, gravada no rascunho (revisao do M7a)
        raise ErroRascunho('mudou')
    conf = {'origem': disparo.origem, 'meio': disparo.meio, 'em': modelo.agora()}
    if formatos is not None:
        conf['formatos'] = list(formatos)
        # a familia passa a ser destes formatos (revisao do M7b, fase A): o aviso de que ela mudou sai com a confirmacao
        f['formatos'] = list(formatos)
        f.pop('cedidos', None)
    if pecas is not None:
        conf['pecas'] = pecas
    f.update(versao=versao, confirmada=True, confirmacao=conf)
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
