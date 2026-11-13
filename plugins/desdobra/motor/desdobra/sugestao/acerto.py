# -*- coding: utf-8 -*-
"""Acerto da sugestao de funcao (comparar_gabarito; M7c, S5; arquitetura-v1.md, 9.8; decisoes-v1.md, 162 e 189).

Mede a sugestao do Claude que a tela mostrou (sugestoes/sugestoes-validadas.json, lida como a tela le:
desdobra.tela.funcoes.sugestoes_na_tela) contra uma referencia:
  - ao salvar o briefing (desdobra.briefing.salvar), a funcao que o DA confirmou, resolvida pela heranca do motor;
  - pelo comando nao humano "desdobra sugestao acerto --gabarito CAMINHO", um gabarito fora do repositorio, no padrao
    de "desdobra regressao --corpus": o caminho entra so por argumento e nunca e gravado nem impresso.

A conta (comparar_gabarito):
  - a sugestao passa pelo desdobra.briefing.modelo.resolver, com a heranca de grupo, antes da contagem por camada,
    igual a funcao confirmada pelo DA (a camada coberta no KV so recebe funcao propria, como no motor). O alvo que o
    motor nao resolve (um grupo do gabarito) conta pela sugestao dada a ele mesmo;
  - por_camada: camadas da referencia com a sugestao certa sobre o total (para comparar com 60,7% e 50,0%,
    pesquisa/gabarito-resultado.md, 4);
  - por_decisao: as decisoes minimas da referencia (desdobra.tela.funcoes.decisoes_minimas, por grupo e por camada);
    a decisao conta como certa quando a sugestao resolvida da a funcao dela a todas as camadas que ela decide;
  - alternativa: camadas em que a alternativa resolvida e a funcao da referencia; cobertura: camadas com sugestao
    sobre o total. Nenhuma meta reprova: e so registro.

Do gabarito (forma da ficha de rotulagem: kvs[].respostas[] com layer_id e funcao) valem so layer_id e funcao, pela
tabela FUNCOES_DO_GABARITO; respondente, arquivo, chave, nome e obs nunca vao para o envelope, o log ou
medicoes/sugestao.json. O KV e escolhido pelo sha256 do PSD do job (o do laudo): pelo campo sha256 do KV no gabarito
ou, sem ele, pelo sha256 do arquivo do KV dentro da pasta passada em --corpus (o nome do arquivo so localiza o
arquivo, na memoria).

medicoes/sugestao.json (contrato medicoes-sugestao/1) fica fora do briefing, como medicoes/tela.json: a medicao mais
recente por referencia e por modo, so com ids, o enum de funcoes e numeros.
"""
import hashlib
import json
import os
from pathlib import Path

from desdobra import contratos

ESQUEMA = 'medicoes-sugestao/1'
ARQUIVO = Path('medicoes') / 'sugestao.json'
COMANDO = 'sugestao acerto'
EVENTO = 'acerto_da_sugestao'
REFERENCIAS = ('briefing', 'gabarito')
# so para a heranca do motor aceitar a sugestao "indeterminado" (que pede observacao); nunca sai daqui
_OBSERVACAO = 'sugestao do Claude'
LIMITE_GABARITO = 1 << 22  # numero-neutro: so limita a leitura; o gabarito da ficha tem poucas centenas de camadas
_BLOCO = 1 << 20  # numero-neutro: tamanho do pedaco lido para o sha256

# A ficha de rotulagem (as funcoes que o gabarito usa) para os ids do $defs.funcao do briefing/1, uma a uma. O "nao
# sei" fica sem par: nem acerto nem erro. Funcao fora desta tabela tambem fica sem par.
FUNCOES_DO_GABARITO = {
    'fundo': 'fundo',
    'imagem': 'imagem',
    'sujeito': 'sujeito',
    'veu-legibilidade': 'veu_de_legibilidade',
    'grafismo': 'grafismo',
    'titulo': 'titulo',
    'texto-apoio': 'texto_de_apoio',
    'cta': 'cta',
    'icone-cta': 'icone_de_cta',
    'url-contato': 'url_ou_contato',
    'texto-legal': 'texto_legal',
    'info-evento': 'informacao_de_evento',
    'destaque-numerico': 'destaque_numerico',
    'logo-principal': 'logo_principal',
    'assinatura-institucional': 'assinatura_institucional',
    'selo': 'selo',
    'logo-parceiro': 'logo_de_parceiro',
    'estrutura': 'estrutura',
    'fora-da-peca': 'fora_da_peca',
    'indeterminado': 'indeterminado',
    'nao-sei': None,
}


class ErroGabarito(Exception):
    """O gabarito nao serve para este job. codigo: gabarito_invalido, kv_fora_do_gabarito ou kv_repetido."""

    def __init__(self, codigo):
        super().__init__(codigo)
        self.codigo = codigo


def traduzir(funcao):
    """O id do esquema da funcao do gabarito, ou None (sem par)."""
    return FUNCOES_DO_GABARITO.get(funcao) if isinstance(funcao, str) else None


# ------------------------------------------------------------------ a conta
def _fracao(certas, total):
    return round(certas / total, 3) if total else None  # numero-neutro: tres casas, como a pesquisa


def _resolver_sugestoes(laudo, sugestoes, campo, quadro):
    """{layer_id: funcao} da sugestao (campo 'funcao' ou 'alternativa') resolvida pela heranca do motor, mais o alvo
    que o motor nao resolve (grupo), pela sugestao dada a ele mesmo."""
    from desdobra.briefing import modelo as mb
    from desdobra.tela import funcoes
    dados = {'funcoes': {str(s['layer_id']): {'funcao': s[campo], 'observacao': _OBSERVACAO} for s in sugestoes}}
    resolvidas, _erros, _info = mb.resolver(laudo, funcoes.briefing_parcial(dados, quadro))
    saida = {s['layer_id']: s[campo] for s in sugestoes}
    saida.update({lid: r['funcao'] for lid, r in resolvidas.items()})
    return saida


def _decisoes(laudo, referencia, quadro):
    """[(alvo, funcao, camadas que a decisao decide)] das decisoes minimas da referencia."""
    from desdobra.briefing import modelo as mb
    from desdobra.tela import funcoes
    minimas = {lid: f for lid, f in funcoes.decisoes_minimas(laudo, referencia, quadro).items() if f is not None}
    dados = {'funcoes': {str(lid): {'funcao': f, 'observacao': _OBSERVACAO} for lid, f in minimas.items()}}
    resolvidas, _erros, _info = mb.resolver(laudo, funcoes.briefing_parcial(dados, quadro))
    por_raiz = {}
    for lid, r in resolvidas.items():
        if lid in referencia:
            por_raiz.setdefault(r['raiz'], []).append(lid)
    return [(alvo, f, sorted(por_raiz.get(alvo, []))) for alvo, f in sorted(minimas.items())]


def comparar_gabarito(laudo, referencia, sugestoes, quadro=None):
    """Compara as sugestoes ([{'layer_id', 'funcao', 'alternativa'}]) com a referencia ({layer_id: funcao do
    esquema}). Devolve {'por_camada', 'por_decisao', 'alternativa', 'cobertura', 'camadas'}; so ids, funcoes e
    numeros. Funcao pura: nao le nem grava nada."""
    from desdobra.briefing import modelo as mb
    camadas_laudo = mb.camadas_do_laudo(laudo)
    ref = {lid: f for lid, f in referencia.items() if lid in camadas_laudo and f is not None}
    sugestoes = [s for s in sugestoes if s['layer_id'] in camadas_laudo]
    sug = _resolver_sugestoes(laudo, sugestoes, 'funcao', quadro)
    alt = _resolver_sugestoes(laudo, sugestoes, 'alternativa', quadro)
    camadas = [{'layer_id': lid, 'funcao': f, 'sugestao': sug.get(lid), 'alternativa': alt.get(lid)}
               for lid, f in sorted(ref.items())]
    total = len(camadas)
    certas = sum(c['sugestao'] == c['funcao'] for c in camadas)
    certas_alt = sum(c['alternativa'] == c['funcao'] for c in camadas)
    com = sum(c['sugestao'] is not None for c in camadas)
    decisoes = _decisoes(laudo, ref, quadro)
    certas_dec = sum(bool(lids) and all(sug.get(x) == f for x in lids) for _alvo, f, lids in decisoes)
    return {'por_camada': {'certas': certas, 'total': total, 'acerto': _fracao(certas, total)},
            'por_decisao': {'certas': certas_dec, 'total': len(decisoes), 'acerto': _fracao(certas_dec, len(decisoes))},
            'alternativa': {'certas': certas_alt, 'total': total, 'acerto': _fracao(certas_alt, total)},
            'cobertura': {'com_sugestao': com, 'total': total, 'cobertura': _fracao(com, total)},
            'camadas': camadas}


# ------------------------------------------------------------------ referencias
def quadro_do_briefing(briefing):
    from desdobra.briefing import modelo as mb
    d = (briefing or {}).get('quadro')
    return d['valor'] if mb._decisao_valida(d) else None  # noqa: SLF001 - a mesma regra do motor


def referencia_do_briefing(laudo, briefing):
    """{layer_id: funcao} confirmada pelo DA, resolvida pela heranca do motor (a mesma que layout e validacao leem)."""
    from desdobra.briefing import modelo as mb
    resolvidas, _erros, _info = mb.resolver(laudo, briefing)
    return {lid: r['funcao'] for lid, r in resolvidas.items()}


def _e_inteiro(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _sha256_do_arquivo(caminho):
    h = hashlib.sha256()
    with open(caminho, 'rb') as f:
        for bloco in iter(lambda: f.read(_BLOCO), b''):
            h.update(bloco)
    return h.hexdigest()


def _dentro(caminho, pasta):
    c = os.path.normcase(str(caminho))
    p = os.path.normcase(str(pasta))
    return c != p and c.startswith(p.rstrip('\\/') + os.sep)


def _sha_do_kv(kv, corpus):
    """O sha256 do KV do gabarito: o campo sha256, ou o do arquivo dentro da pasta do corpus; None sem nenhum."""
    from desdobra.sugestao import importar
    sha = kv.get('sha256')
    if importar._hex64(sha):  # noqa: SLF001 - a mesma conferencia de sha256 do importador
        return sha
    rel = kv.get('arquivo')
    if corpus is None or not isinstance(rel, str) or not rel:
        return None
    try:
        raiz = Path(corpus).resolve()
        alvo = (raiz / rel).resolve()
        if not _dentro(alvo, raiz) or not alvo.is_file():
            return None
        return _sha256_do_arquivo(alvo)
    except (OSError, ValueError):
        return None


def _conferir_forma(dados):
    if not isinstance(dados, dict) or not isinstance(dados.get('kvs'), list):
        raise ErroGabarito('gabarito_invalido')
    for kv in dados['kvs']:
        if not isinstance(kv, dict) or not isinstance(kv.get('respostas'), list):
            raise ErroGabarito('gabarito_invalido')
        for r in kv['respostas']:
            if not isinstance(r, dict) or not _e_inteiro(r.get('layer_id')):
                raise ErroGabarito('gabarito_invalido')


def referencia_do_gabarito(dados, laudo, corpus=None):
    """({layer_id: funcao do esquema}, {'sem_par', 'fora_do_laudo'}) do KV do gabarito com o sha256 do PSD do job.
    Usa so layer_id e funcao de cada resposta. ErroGabarito sem o KV, com dois KVs do mesmo sha256 ou na forma
    errada. Nada do gabarito alem disso sai daqui."""
    from desdobra.briefing import modelo as mb
    _conferir_forma(dados)
    alvo = (laudo.get('origem') or {}).get('sha256')
    achados = [kv for kv in dados['kvs'] if alvo is not None and _sha_do_kv(kv, corpus) == alvo]
    if not achados:
        raise ErroGabarito('kv_fora_do_gabarito')
    if len(achados) > 1:
        raise ErroGabarito('kv_repetido')
    camadas = mb.camadas_do_laudo(laudo)
    # a ultima resposta da camada vale, como no comparador da pesquisa, mesmo quando ela fica sem par
    ultimas = {}
    for r in achados[0]['respostas']:
        ultimas[r['layer_id']] = traduzir(r.get('funcao'))
    ref, info = {}, {'sem_par': 0, 'fora_do_laudo': 0}
    for layer_id, funcao in ultimas.items():
        if funcao is None:
            info['sem_par'] += 1
        elif layer_id not in camadas:
            info['fora_do_laudo'] += 1
        else:
            ref[layer_id] = funcao
    return ref, info


def ler_gabarito(caminho):
    """O JSON do gabarito, ou ErroGabarito('gabarito_invalido'). O caminho nunca vai para mensagem nenhuma."""
    try:
        arq = Path(caminho)
        if not arq.is_file() or arq.stat().st_size > LIMITE_GABARITO:
            raise ErroGabarito('gabarito_invalido')
        return json.loads(arq.read_bytes().decode('utf-8'))
    except (OSError, ValueError, UnicodeDecodeError, RecursionError):
        raise ErroGabarito('gabarito_invalido') from None


# ------------------------------------------------------------------ medicao do job
def _sem_sugestao(modo, referencia, quando, info):
    return {'quando': quando, 'modo': modo, 'referencia': referencia, 'situacao': 'sem_sugestao',
            'sugestoes_ref': None, 'por_camada': None, 'por_decisao': None, 'alternativa': None, 'cobertura': None,
            'sem_par': info.get('sem_par', 0), 'fora_do_laudo': info.get('fora_do_laudo', 0), 'camadas': []}


def medir(pasta, laudo, referencia_funcoes, *, referencia, quando=None, teto=None, quadro=None, tela=None,
          info=None):
    """A medicao do job agora: as sugestoes que a tela mostra (tela: o dict de
    desdobra.tela.funcoes.sugestoes_na_tela; sem ele, lido aqui com o teto) contra referencia_funcoes. No modo c ou
    sem sugestao conferida, situacao sem_sugestao. Nao grava."""
    from desdobra.briefing import modelo as mb
    from desdobra.job import modo_dados
    from desdobra.tela import funcoes
    if referencia not in REFERENCIAS:
        raise ValueError('referencia invalida: %r' % referencia)
    quando = quando or mb.agora()
    info = dict(info or {})
    if tela is None:
        tela = funcoes.sugestoes_na_tela(pasta, modo_dados.teto_do_job(pasta, teto))
    modo = tela.get('modo') if tela.get('modo') in ('a', 'b') else 'c'
    if modo == 'c' or not tela.get('sugestoes') or not tela.get('sha256'):
        return _sem_sugestao(modo, referencia, quando, info)
    conta = comparar_gabarito(laudo, referencia_funcoes, tela['sugestoes'], quadro)
    return dict(conta, quando=quando, modo=modo, referencia=referencia, situacao='medido',
                sugestoes_ref=tela['sha256'], sem_par=info.get('sem_par', 0),
                fora_do_laudo=info.get('fora_do_laudo', 0))


def gravar(pasta, medicao):
    """Guarda a medicao em medicoes/sugestao.json, no lugar da anterior da mesma referencia e do mesmo modo. O arquivo
    que nao se le recomeca."""
    from desdobra.briefing import modelo as mb
    pasta = Path(pasta)
    job_id = contratos.ler(pasta / 'estado.json', 'estado/1')['job_id']
    arq = pasta / ARQUIVO
    dados = None
    if arq.is_file():
        try:
            dados = contratos.ler(arq, ESQUEMA)
        except contratos.ErroContrato:
            dados = None
    if dados is None or dados.get('job_id') != job_id:
        dados = {'esquema': ESQUEMA, 'job_id': job_id, 'atualizado_em': None, 'briefing': {}, 'gabarito': {}}
    dados[medicao['referencia']][medicao['modo']] = medicao
    dados['atualizado_em'] = mb.agora()
    arq.parent.mkdir(parents=True, exist_ok=True)
    contratos.gravar(arq, dados, ESQUEMA)
    return dados


def registrar(pasta, medicao):
    """A linha do log: so a referencia, o modo, a situacao e as contagens."""
    from desdobra.job import nucleo
    campos = {'referencia': medicao['referencia'], 'modo': medicao['modo'], 'situacao': medicao['situacao']}
    for chave in ('por_camada', 'por_decisao', 'alternativa'):
        if medicao.get(chave):
            campos['certas_' + chave] = medicao[chave]['certas']
            campos['total_' + chave] = medicao[chave]['total']
    try:
        nucleo.registrar_evento(pasta, EVENTO, **campos)
    except OSError:
        pass  # o registro nunca derruba a medicao


def ao_salvar(pasta, briefing, conteudo=None):
    """Chamado pelo gravador do briefing depois de gravar: mede a sugestao que a tela mostrava contra o briefing
    confirmado e guarda em medicoes/sugestao.json. Engole todo erro: a medicao nunca interrompe o salvar e nunca
    chega ao DA."""
    try:
        laudo = contratos.ler(Path(pasta) / 'laudo' / 'laudo.json', 'laudo/1')
        ler = (conteudo or {}).get('sugestoes')
        tela = ler() if callable(ler) else None
        m = medir(pasta, laudo, referencia_do_briefing(laudo, briefing), referencia='briefing',
                  quando=(briefing.get('cabecalho') or {}).get('quando'), quadro=quadro_do_briefing(briefing),
                  tela=tela)
        gravar(pasta, m)
        registrar(pasta, m)
    except Exception:  # noqa: BLE001 - a medicao e so registro; o briefing ja foi gravado
        return None
    return m
