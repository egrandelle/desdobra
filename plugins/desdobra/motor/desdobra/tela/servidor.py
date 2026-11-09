# -*- coding: utf-8 -*-
"""Servidor local da tela de briefing (M7a2 so de leitura; M7a, fatia 1, com o caminho de escrita; proposta do M7,
secao 3 e fatias a2 e a4; arquitetura-v1.md, 3.4).

Regras (cada uma com teste em testes/test_tela_servidor.py e testes/test_tela_escrita.py):
  - escuta so em ('127.0.0.1', 0), nunca ::1 nem 0.0.0.0; sem allow_reuse_address e, no Windows, com
    SO_EXCLUSIVEADDRUSE: outro socket local nao toma a porta;
  - so GET e POST (METODOS); todo outro metodo da 404. POST so nas rotas da tabela de escrita (ESCRITAS) e so no
    servidor aberto com a pasta do job; fora disso, 404. Toda escrita pede, nesta ordem: o cookie da sessao (sem ele,
    404), Origin presente e igual a propria origem, Sec-Fetch-Site same-origin, Content-Type application/json, o
    cabecalho X-Desdobra-CSRF com o token da sessao (entregue so na pagina, na meta dsd-csrf; um formulario comum nao
    manda cabecalho), Content-Length presente e ate tela.corpo_max_bytes (sem Transfer-Encoding; acima do teto, a
    recusa sai sem ler o corpo), JSON em UTF-8 e o esquema da rota conferido antes da gravacao atomica. Toda recusa e
    403 ou 404, sem corpo e sem dizer o motivo;
  - rascunho (POST e GET /api/rascunho): briefing/rascunho.json (desdobra.tela.rascunho), com a chave do hash do
    laudo; o rascunho de outro laudo e recusado na gravacao e nunca volta calado na leitura;
  - atos humanos (/api/ato/pedir, /api/ato/confirmar, /api/ato/cancelar; decisoes-v1.md, 159; proposta do M7, 159b):
    o clique do DA pede um ato da tabela do servidor (Ato); o servidor devolve um pedido de uso unico e o texto do
    dialogo, que a janela mostra sem opcao marcada. So o confirmar com o pedido vivo e a resposta "confirmar" emite o
    Disparo da tela (humano.exigir_tela, meio tela), e o pedido morre nele; cancelar, um pedido novo ou o pedido
    errado nao executam nada. No modo de teste (proposta do M7, 159c) o Disparo sai com meio medicao e origem
    fixture_de_teste, e o rascunho com origem fixture_de_teste; o modo de teste recusa o job com briefing ou rascunho
    do DA, e nenhum comando da CLI o abre;
  - antes do roteamento, 404 para o caminho cru e o decodificado que citam .ttf .otf .ttc .woff .woff2 .psd .psb, sem
    diferenca de maiuscula, com ponto e espaco no fim e ::$DATA normalizados (decisoes-v1.md, proposta 167);
  - depois, Host igual a 127.0.0.1:<porta>, cliente 127.0.0.1, Origin ausente ou a propria, Sec-Fetch-Site ausente ou
    da mesma origem (contra pagina de outro site e DNS rebinding): fora disso, 403;
  - rotas explicitas (tabela em _rota): /entrar/<token>, /, /tela.js, /tela.css, /fontes.css, /controle,
    /api/estado, /api/saude, /api/previa/<id>, /asset/<id> e /fonte/<id ou sha256>. Caminho fora da tabela, com
    query, com % ou com barra a mais da 404;
  - /entrar/<token> vale uma vez so: vira o cookie HttpOnly SameSite=Strict e depois da 404. A resposta e 204, sem
    pagina: a navegacao nao se completa e a URL com o token nao entra no historico do perfil (proposta do M7, secao 3,
    linha Entrada); quem abre segue para / (desdobra.tela.processo). Toda outra rota, saude inclusive, exige o cookie,
    e sem ele da 404 (nao diz se a rota existe);
  - a fonte vai por id (f01) ou pelo sha256 dos bytes servidos, da memoria, com no-store e sem CORS; a folha
    /fontes.css so cita /fonte/<id>, sem local() nem nome de arquivo;
  - toda resposta: no-store (menos o controle positivo /controle, como na conferencia de fontes), nosniff,
    Cross-Origin-Resource-Policy same-origin, Referrer-Policy no-referrer, a CSP estrita e X-Frame-Options DENY;
  - nada e impresso, e so o rascunho e o que os atos gravam vai ao disco: o token, a sessao e o CSRF ficam so na
    memoria deste processo e vao so ao Chromium que ele abre (url_entrada e a pagina). O servidor so conta as respostas
    por rota (contagem).
Risco residual declarado (o mesmo da desdobra.humano): o token, a sessao e os bytes das fontes ficam em claro na
memoria do processo de fundo, que roda na conta do DA enquanto a janela esta aberta. Um despejo de memoria desse
processo (ferramentas do proprio Windows, sem elevacao) os tira dali; o gancho nega os despejos conhecidos pelo
terminal do Claude (DESPEJO_DE_MEMORIA em scripts/gancho_confirmacoes.py), e o resto fica nas regras de permissao.
"""
import hashlib
import http.server
import json
import re
import secrets
import socket
import socketserver
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import unquote

from desdobra.chromium.servidor import CACHE_CONTROLE, _iguais

COOKIE = 'dsd_tela'
METODOS = ('GET', 'POST')
# rotas de escrita: caminho exato -> chave da contagem (so POST, so com a pasta do job)
# /api/familia/previa nao grava: e a previa da edicao por familia (desdobra.tela.edicao), que passa pelas mesmas
# conferencias da escrita porque leva as edicoes do DA no corpo
ESCRITAS = {'/api/rascunho': 'rascunho', '/api/ato/pedir': 'ato_pedir', '/api/ato/confirmar': 'ato_confirmar',
            '/api/ato/cancelar': 'ato_cancelar', '/api/familia/previa': 'familia_previa'}
CABECALHO_CSRF = 'X-Desdobra-CSRF'
TIPOS_JSON = ('application/json', 'application/json;charset=utf-8')
META_CSRF = '<meta name="dsd-csrf" content="%s">'
RESPOSTA_CONFIRMAR = 'confirmar'
# a tela que nao conseguiu se montar de novo (_atualizar) avisa o DA no estado, e o aviso sai na proxima atualizacao
# que der certo (revisao do M7a): nunca segue calada com o que tinha
AVISO_JOB_OCUPADO = ('O job está ocupado com outra tarefa agora, e a tela ainda mostra o que tinha antes da sua última '
                     'escolha. Ela tenta de novo sozinha na próxima vez que você mexer em alguma coisa.')
AVISO_SEM_ATUALIZAR = ('A tela não conseguiu se atualizar com a sua última escolha, e o que aparece aqui pode estar '
                       'desatualizado. Feche esta janela e abra a tela de novo. Se o aviso voltar, chame a Trezion.')
ID_ATO = re.compile(r'^[a-z][a-z0-9_]*$')
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' blob:; font-src 'self'; "
       "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
CABECALHOS_FIXOS = (('X-Content-Type-Options', 'nosniff'), ('Cross-Origin-Resource-Policy', 'same-origin'),
                    ('Referrer-Policy', 'no-referrer'), ('Content-Security-Policy', CSP), ('X-Frame-Options', 'DENY'))
EXTENSOES_RECUSADAS = ('ttf', 'otf', 'ttc', 'woff', 'woff2', 'psd', 'psb')
_EXTENSAO = re.compile(r'\.(?:%s)(?![a-z0-9])' % '|'.join(sorted(EXTENSOES_RECUSADAS, key=len, reverse=True)))
_FLUXO_NTFS = re.compile(r'::\$data', re.IGNORECASE)
ID_FONTE = re.compile(r'^(?:f\d{2}|[0-9a-f]{64})$')
ID_ASSET = re.compile(r'^a\d{3,4}$')
ID_PREVIA = re.compile(r'^[a-z0-9][a-z0-9_-]*$')  # o id do formato do briefing (briefing-1.json, formatos.id)
_TOKEN = re.compile(r'^[0-9a-f]+$')
# contagem por rota servida; as recusas tem contagem propria
ROTAS = ('entrar', 'pagina', 'estatico', 'controle', 'estado', 'saude', 'previa', 'asset', 'fonte', 'rascunho_lido') + \
    tuple(ESCRITAS.values())
RECUSAS = ('proibido', 'nao_encontrado', 'sem_cookie', 'extensao_recusada', 'metodo_recusado', 'entrada_reusada',
           'tipo_recusado', 'csrf_recusado', 'corpo_recusado', 'dado_recusado', 'erro_do_ato')
MIME_JSON = 'application/json; charset=utf-8'
DECODIFICACOES = 3  # numero-neutro: camadas de %-codificacao desfeitas na recusa por extensao (%252E e afins)


def _normalizar(caminho):
    """Caminho como o Windows o leria: barras para /, sem ::$DATA e sem ponto ou espaco no fim de cada segmento."""
    s = _FLUXO_NTFS.sub('', caminho.replace('\\', '/').lower())
    return '/'.join(seg.rstrip('. ') for seg in s.split('/'))


def extensao_recusada(alvo):
    """O alvo do pedido (caminho e query, cru) cita uma extensao de fonte ou de PSD, cru ou decodificado."""
    vistos = [alvo]
    for _ in range(DECODIFICACOES):
        vistos.append(unquote(vistos[-1]))
    return any(_EXTENSAO.search(_normalizar(v)) or _EXTENSAO.search(_normalizar(v) + '/') for v in vistos)


class _ServidorExclusivo(http.server.ThreadingHTTPServer):
    """ThreadingHTTPServer sem reuso de porta: no Windows o reuso deixa outro socket local tomar a mesma porta."""
    allow_reuse_address = False
    allow_reuse_port = False
    daemon_threads = True

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        socketserver.TCPServer.server_bind(self)
        # sem getfqdn: o nome do servidor e o endereco, sem consulta de nome
        self.server_name, self.server_port = self.server_address[:2]

    def handle_error(self, request, client_address):
        """Nada e impresso: um erro numa requisicao so fecha a conexao dela."""


@dataclass(frozen=True)
class Ato:
    """Um ato humano da tela: o comando humano (humano.COMANDOS ou humano.ATOS_DA_TELA) do Disparo, o texto do dialogo
    de confirmacao (do motor, nunca da pagina) e quem executa. executar(disparo, dados) -> dict da resposta;
    validar(dados) -> bool (sem ele, o ato nao aceita dados). texto pode ser uma funcao dos dados ja validados
    (texto(dados) -> str), para o dialogo dizer o que sera gravado."""
    comando: str
    titulo: str
    texto: str
    sim: str
    nao: str
    executar: Callable
    validar: Callable | None = None


def _job_do_da(pasta):
    """O job tem decisao do DA (ou arquivo de decisao que nao se le): o modo de teste recusa. Conta o briefing
    confirmado que nao e de teste, o rascunho do DA e, desde a revisao do M7a, o linkado confirmado sem a origem de
    teste (o de antes da origem gravada conta como do DA), a acao de spec do DA e o modo de dados escolhido pelo DA."""
    from desdobra import arquivos
    from desdobra.briefing import modelo
    from desdobra.job import modo_dados
    from desdobra.render import contrato as mod_contrato
    from desdobra.specs import importar
    from desdobra.tela import rascunho

    def ler(rel):
        arq = Path(pasta) / rel
        if not arq.is_file():
            return {}
        try:
            d = arquivos.ler_json(arq)
        except (OSError, ValueError):
            return None
        return d if isinstance(d, dict) else None

    b = ler(modelo.ARQUIVO)
    if b is None or (b and (b.get('cabecalho') or {}).get('origem') != modelo.ORIGEM_FIXTURE):
        return True
    lk, sp, md = ler(mod_contrato.ARQUIVO_LINKADOS), ler(importar.ARQUIVO_CONFIRMACOES), ler(modo_dados.ARQUIVO)
    if lk is None or sp is None or md is None:
        return True
    if any(not isinstance(x, dict) or (x.get('confirmado_por') or {}).get('origem') != modelo.ORIGEM_FIXTURE
           for x in lk.get('linkados') or []):
        return True
    if any(not isinstance(a, dict) or a.get('por') != modelo.ORIGEM_FIXTURE for a in sp.get('acoes') or []):
        return True
    if md and md.get('origem') != modelo.ORIGEM_FIXTURE:
        return True
    return rascunho.origem_gravada(pasta) == modelo.ORIGEM_RASCUNHO


class ServidorTela:
    """Uso:
        with ServidorTela(conteudo, pasta=job) as s:
            janela.ir(s.url_entrada)        # so para o Chromium da tela, nunca impresso

    conteudo: {'estado': dict, 'previas': {id: dict}, 'assets': {id: (bytes, mime)}, 'fontes': {id: (bytes, mime)},
               'estaticos': {caminho: (bytes, mime)} (opcional; padrao: desdobra.tela.estatico)}.
    pasta: a pasta do job; sem ela o servidor e so de leitura (sem POST). Com ela, a sessao humana da tela abre aqui
    (humano.abrir_sessao_tela), e o job precisa ter laudo.
    modo_teste: o modo de teste da tela (proposta do M7, 159c), so para os testes com job sintetico.
    atos: {nome: Ato} dos botoes que pedem confirmacao na janela."""

    def __init__(self, conteudo, pasta=None, modo_teste=False, atos=None):
        from desdobra import humano, limites
        from desdobra.briefing import modelo
        from desdobra.tela import estatico, rascunho
        self.estado = conteudo['estado']
        # o conteudo da montagem, o mesmo dicionario que os atos da tela leem (desdobra.tela.atos.atos_do_job): o passo 3
        # montado de novo (_atualizar) entra nele no lugar, e os atos passam a ver as familias novas
        self._conteudo = conteudo
        # recarregar() -> estado novo da tela, chamado depois de cada ato feito (a pagina pede /api/estado de novo)
        self.recarregar = conteudo.get('recarregar')
        # editar(dados, origem) -> previa da edicao por familia, ou None quando os dados nao seguem o formato
        self.editar = conteudo.get('editar')
        # {id: [formatos]} das familias da tela: o rascunho lido pela pagina perde a confirmacao de outros formatos
        self.familias_da_tela = {g: list(f.get('formatos') or ())
                                 for g, f in (conteudo.get('familias') or {}).items()}
        self.pecas_da_tela = {g: f.get('pecas') for g, f in (conteudo.get('familias') or {}).items()}
        self.previas = dict(conteudo.get('previas') or {})
        self.assets = dict(conteudo.get('assets') or {})
        self.fontes = dict(conteudo.get('fontes') or {})
        for ident in self.fontes:
            if not re.match(r'^f\d{2}$', ident):
                raise ValueError('id de fonte fora do padrao')
        for ident in self.assets:
            if not ID_ASSET.match(ident):
                raise ValueError('id de asset fora do padrao')
        for ident in self.previas:
            if not ID_PREVIA.match(ident) or extensao_recusada('/' + ident):
                raise ValueError('id de previa fora do padrao')
        # a fonte tambem pelo sha256 dos bytes servidos
        self._fonte_por_rota = dict(self.fontes)
        for dados, tipo in list(self.fontes.values()):
            self._fonte_por_rota[hashlib.sha256(dados).hexdigest()] = (dados, tipo)
        self.estaticos = dict(conteudo.get('estaticos') or estatico.arquivos())
        self.estaticos['/fontes.css'] = (estatico.folha_das_fontes(sorted(self.fontes)), 'text/css; charset=utf-8')
        self.atos = dict(atos or {})
        for nome, ato in self.atos.items():
            humanos = humano.COMANDOS + humano.ATOS_DA_TELA
            if not ID_ATO.match(nome) or not isinstance(ato, Ato) or ato.comando not in humanos:
                raise ValueError('ato fora do padrao')
        self.pasta = Path(pasta).resolve() if pasta is not None else None
        self.modo_teste = bool(modo_teste)
        self.laudo_sha256 = None
        self.job_id = None
        self.csrf = None
        self.origem_rascunho = modelo.ORIGEM_FIXTURE if self.modo_teste else modelo.ORIGEM_RASCUNHO
        self.corpo_max = int(limites.valor('tela.corpo_max_bytes'))
        self.espera_rascunho_ms = limites.valor('tela.rascunho_espera_ms')
        self._sessao_humana = None
        if self.pasta is not None:
            self.laudo_sha256 = rascunho.laudo_sha256(self.pasta)
            self.job_id = (conteudo.get('estado') or {}).get('job_id')
            if self.laudo_sha256 is None or not self.job_id:
                raise ValueError('a escrita da tela pede o laudo e o job')
            if self.modo_teste and _job_do_da(self.pasta):
                raise ValueError('o modo de teste da tela so roda em job sintetico')
            self.csrf = secrets.token_hex(16)  # numero-neutro: bytes de entropia do token CSRF
            self._sessao_humana = humano.abrir_sessao_tela(teste=self.modo_teste)
        if '/' in self.estaticos:
            # o token CSRF vai so na pagina, na meta dsd-csrf (vazia no servidor so de leitura)
            pagina, tipo = self.estaticos['/']
            meta_vazia = (META_CSRF % '').encode('ascii')
            self.estaticos['/'] = (pagina.replace(meta_vazia, (META_CSRF % (self.csrf or '')).encode('ascii'), 1), tipo)
        self.token = secrets.token_hex(16)  # numero-neutro: bytes de entropia do token
        self.sessao = secrets.token_hex(16)  # numero-neutro: idem
        self.marcador_controle = secrets.token_hex(32).encode('ascii')  # numero-neutro: bytes de entropia do marcador
        self.contagem = {k: 0 for k in ROTAS + RECUSAS}
        self._entrada_usada = False
        self._pendente = None  # (pedido, nome do ato, dados) do unico ato a confirmar
        self._trava = threading.Lock()
        self._trava_escrita = threading.Lock()
        self._trava_previa = threading.Lock()
        self._srv = None
        self._fio = None

    @property
    def escreve(self):
        return self.pasta is not None

    # --------------------------------------------------------------
    @property
    def porta(self):
        return self._srv.server_address[1]

    @property
    def origem(self):
        return 'http://127.0.0.1:%d' % self.porta

    @property
    def url_entrada(self):
        """A URL de entrada com o token: so para o Chromium da tela (Janela.ir), nunca impressa nem gravada."""
        return '%s/entrar/%s' % (self.origem, self.token)

    @property
    def url_pagina(self):
        return self.origem + '/'

    @property
    def entrada_usada(self):
        return self._entrada_usada

    def _contar(self, chave):
        with self._trava:
            self.contagem[chave] += 1

    def _gastar_entrada(self, recebido):
        """True uma vez so, para o token certo."""
        with self._trava:
            if not _iguais(recebido, self.token):
                return False
            if self._entrada_usada:
                self.contagem['entrada_reusada'] += 1
                return False
            self._entrada_usada = True
            return True

    def _rota(self, caminho):
        """(chave da contagem, (corpo, tipo) ou None quando so a entrada) ou None quando fora da tabela."""
        partes = caminho.split('/')
        if caminho == '/':
            return 'pagina', self.estaticos['/']
        if caminho in self.estaticos:
            return 'estatico', self.estaticos[caminho]
        if caminho == '/controle':
            return 'controle', (b'/* ' + self.marcador_controle + b' */' + bytes([10]), 'text/css; charset=utf-8')
        if caminho == '/api/estado':
            return 'estado', self._estado_servido  # montado de novo, se o passo 2 mudou, so depois do cookie
        if caminho == '/api/saude':
            return 'saude', (json.dumps({'ok': True, 'somente_leitura': not self.escreve}).encode('utf-8'), MIME_JSON)
        if caminho == '/api/rascunho' and self.escreve:
            return 'rascunho_lido', self._rascunho_lido  # lido so depois do cookie
        if len(partes) != 3:  # numero-neutro: /<rota>/<id>
            return None
        _vazio, nome, ident = partes
        if nome == 'api' or not ident:
            return None
        if nome == 'fonte' and ID_FONTE.match(ident) and ident in self._fonte_por_rota:
            return 'fonte', self._fonte_por_rota[ident]
        if nome == 'asset' and ID_ASSET.match(ident) and ident in self.assets:
            return 'asset', self.assets[ident]
        return None

    def _previa(self, caminho):
        partes = caminho.split('/')
        if len(partes) == 4 and partes[1] == 'api' and partes[2] == 'previa' and partes[3] in self.previas:  # numero-neutro: /api/previa/<id>
            d = self.previas[partes[3]]
            return 'previa', (json.dumps(d, ensure_ascii=False, default=str).encode('utf-8'), MIME_JSON)
        return None

    def _estado_servido(self):
        if self.escreve:
            with self._trava_escrita:
                self._atualizar()
        return json.dumps(self.estado, ensure_ascii=False, default=str).encode('utf-8'), MIME_JSON

    def _atualizar(self):
        """O passo 2 do rascunho mudou desde a montagem (conteudo atualizar): o conteudo e montado de novo e entra no
        lugar do velho (estado, previas, familias, previa da edicao e o recarregar). Assets e fontes sao do laudo e do
        job, e ficam. Qualquer erro deixa o conteudo de antes, com o aviso no estado (aviso_atualizacao, texto fixo em
        portugues para o DA): a pagina mostra que o que ela tem pode estar velho (revisao do M7a)."""
        atualizar = self._conteudo.get('atualizar')
        if not callable(atualizar):
            return
        try:
            novo = atualizar()
        except Exception as e:  # noqa: BLE001 - job ocupado ou lido no meio de uma gravacao: fica o conteudo de antes
            self._avisar(AVISO_JOB_OCUPADO if getattr(e, 'motivo', None) == 'job_ocupado' else AVISO_SEM_ATUALIZAR)
            return
        if not novo:
            self._avisar(None)
            return
        previas = dict(novo.get('previas') or {})
        if any(not ID_PREVIA.match(i) or extensao_recusada('/' + i) for i in previas):
            self._avisar(AVISO_SEM_ATUALIZAR)
            return
        if set(novo.get('assets') or {}) != set(self.assets) or set(novo.get('fontes') or {}) != set(self.fontes):
            # o PSD ou as fontes mudaram com a tela aberta: so uma tela nova serve os arquivos novos
            self._avisar(AVISO_SEM_ATUALIZAR)
            return
        for k in ('assets', 'fontes'):
            novo[k] = self._conteudo.get(k)
        self._conteudo.update(novo)
        self.estado = novo['estado']
        self.previas = previas
        self.recarregar = novo.get('recarregar')
        self.editar = novo.get('editar')
        self.familias_da_tela = {g: list(f.get('formatos') or ()) for g, f in (novo.get('familias') or {}).items()}
        self.pecas_da_tela = {g: f.get('pecas') for g, f in (novo.get('familias') or {}).items()}
        self._pendente = None  # o pedido de ato aberto e de antes do passo 3 novo

    def _avisar(self, texto):
        """Poe (ou tira, com None) o aviso de que a tela nao se atualizou no estado servido."""
        estado = {k: v for k, v in self.estado.items() if k != 'aviso_atualizacao'}
        if texto:
            estado['aviso_atualizacao'] = texto
        self.estado = estado

    # -------------------------------------------------------------- escrita
    def _rascunho_lido(self):
        from desdobra.tela import rascunho
        with self._trava_escrita:
            dados, de_outro = rascunho.ler(self.pasta, rascunho.laudo_sha256(self.pasta))
        if dados is not None and dados['laudo_sha256'] != self.laudo_sha256:
            dados, de_outro = None, True
        if dados is not None and self.familias_da_tela:
            dados = rascunho.sem_confirmacao_velha(dados, self.familias_da_tela, self.pecas_da_tela)
        corpo = {'rascunho': dados, 'de_outro_laudo': de_outro, 'espera_ms': self.espera_rascunho_ms,
                 'job_id': self.job_id, 'laudo_sha256': self.laudo_sha256}
        return json.dumps(corpo, ensure_ascii=False).encode('utf-8'), MIME_JSON

    def _escrever(self, chave, dados):
        """(codigo, dict ou None) da escrita aceita, ou None quando recusada (403 sem detalhe)."""
        if chave == 'familia_previa':
            return self._previa_da_familia(dados)
        with self._trava_escrita:
            if chave == 'rascunho':
                return self._gravar_rascunho(dados)
            if chave == 'ato_pedir':
                return self._pedir_ato(dados)
            if chave == 'ato_cancelar':
                return self._cancelar_ato(dados)
            return self._confirmar_ato(dados)

    def _previa_da_familia(self, dados):
        from desdobra.briefing import modelo
        if not callable(self.editar):
            return None
        origem = modelo.ORIGEM_FIXTURE if self.modo_teste else 'da'
        with self._trava_previa:
            r = self.editar(dados, origem=origem)
        return None if r is None else (200, r)  # numero-neutro: codigo HTTP

    def _gravar_rascunho(self, dados):
        from desdobra.tela import rascunho
        laudo_agora = rascunho.laudo_sha256(self.pasta)
        if laudo_agora != self.laudo_sha256:
            return None  # o PSD foi relido com a tela aberta: o rascunho desta pagina e de outro laudo
        try:
            # cada familia mexida guarda os formatos que a tela mostra para ela agora (revisao do M7b, fase A)
            gravado = rascunho.gravar(self.pasta, dados, job_id=self.job_id, laudo_atual=laudo_agora,
                                      origem=self.origem_rascunho, familias_da_tela=self.familias_da_tela)
        except rascunho.ErroRascunho:
            return None
        return 200, {'atualizado_em': gravado['atualizado_em']}  # numero-neutro: codigo HTTP

    def _pedido_vivo(self, recebido):
        p = self._pendente
        return p is not None and isinstance(recebido, str) and _iguais(recebido, p[0])

    def _pedir_ato(self, dados):
        if not isinstance(dados, dict) or set(dados) != {'ato', 'dados'}:
            return None
        ato = self.atos.get(dados['ato']) if isinstance(dados['ato'], str) else None
        if ato is None:
            return None
        # o rascunho gravado (o giro, a prancheta, o passo 2) ou um ato de spec mudam as familias: o ato e conferido
        # contra a tela montada com eles, mesmo antes de a pagina pedir o estado de novo (revisao do M7a)
        self._atualizar()
        valido = ato.validar(dados['dados']) if ato.validar is not None else dados['dados'] == {}
        if valido is not True:
            return None
        pedido = secrets.token_hex(16)  # numero-neutro: bytes de entropia do pedido
        self._pendente = (pedido, dados['ato'], dados['dados'])  # um pedido novo derruba o anterior
        texto = ato.texto(dados['dados']) if callable(ato.texto) else ato.texto
        return 200, {'pedido': pedido, 'titulo': ato.titulo, 'texto': texto, 'sim': ato.sim,  # numero-neutro: codigo HTTP
                     'nao': ato.nao}

    def _cancelar_ato(self, dados):
        if not isinstance(dados, dict) or set(dados) != {'pedido'} or not self._pedido_vivo(dados['pedido']):
            return None
        self._pendente = None
        return 204, None  # numero-neutro: codigo HTTP

    def _confirmar_ato(self, dados):
        from desdobra import humano
        if not isinstance(dados, dict) or set(dados) != {'pedido', 'resposta'}:
            return None
        if dados['resposta'] != RESPOSTA_CONFIRMAR or not self._pedido_vivo(dados['pedido']):
            return None
        # a tela montada de novo depois do pedido (o rascunho mudou no meio) derruba o pedido: o DA confirma de novo
        # sobre o que a tela mostra agora (_atualizar zera o pedido)
        self._atualizar()
        if not self._pedido_vivo(dados['pedido']):
            return None
        _pedido, nome, dados_ato = self._pendente
        self._pendente = None  # o pedido morre antes do ato
        ato = self.atos[nome]
        # os dados valem de novo no Confirmar: o que mudou no disco depois do pedido nao ganha o clique do DA
        if ato.validar is not None and ato.validar(dados_ato) is not True:
            return None
        try:
            disparo = humano.exigir_tela(ato.comando, self._sessao_humana, confirmado=True)
        except humano.ErroHumano:
            return None
        resposta = ato.executar(disparo, dados_ato)
        if callable(self.recarregar):
            self.estado = self.recarregar()
        return 200, resposta if isinstance(resposta, dict) else {}  # numero-neutro: codigo HTTP

    def iniciar(self):
        dono = self

        class Tratador(http.server.BaseHTTPRequestHandler):
            server_version = 'desdobra'
            sys_version = ''
            protocol_version = 'HTTP/1.1'

            def log_message(self, *a):  # nada no terminal nem em arquivo
                pass

            def log_error(self, *a):
                pass

            def send_error(self, code, message=None, explain=None):
                # pedido malformado: resposta curta, sem eco do pedido
                self.close_connection = True
                self._responder(code)

            def _responder(self, codigo, corpo=b'', tipo='text/plain; charset=utf-8', extra=(), cache='no-store'):
                self.send_response(codigo)
                self.send_header('Cache-Control', cache)
                if cache == 'no-store':
                    self.send_header('Pragma', 'no-cache')
                for k, v in CABECALHOS_FIXOS:
                    self.send_header(k, v)
                self.send_header('Content-Type', tipo)
                self.send_header('Content-Length', str(len(corpo)))
                for k, v in extra:
                    self.send_header(k, v)
                self.end_headers()
                if corpo and self.command != 'HEAD':
                    self.wfile.write(corpo)

            def _negar(self, codigo, chave):
                dono._contar(chave)
                self.close_connection = True
                self._responder(codigo)

            def _cookie_ok(self):
                from http.cookies import SimpleCookie
                c = SimpleCookie()
                try:
                    c.load(self.headers.get('Cookie') or '')
                except Exception:  # noqa: BLE001 - cookie malformado conta como ausente
                    return False
                m = c.get(COOKIE)
                return m is not None and _iguais(m.value, dono.sessao)

            def _origem_ok(self):
                if self.client_address[0] != '127.0.0.1':
                    return False
                if self.headers.get_all('Host') != ['127.0.0.1:%d' % dono.porta]:
                    return False
                if self.headers.get('Origin') not in (None, dono.origem):
                    return False
                return self.headers.get('Sec-Fetch-Site') in (None, 'same-origin', 'none')

            def _um(self, nome):
                """O valor do cabecalho quando ele vem uma vez so, senao None."""
                valores = self.headers.get_all(nome) or []
                return valores[0] if len(valores) == 1 else None

            def _tamanho(self):
                """O Content-Length declarado, quando vem uma vez, so com digitos, sem Transfer-Encoding."""
                if self.headers.get_all('Transfer-Encoding'):
                    return None
                bruto = self._um('Content-Length')
                if bruto is None or not bruto.isdigit() or not bruto.isascii():
                    return None
                return int(bruto)

            def _tratar_escrita(self, alvo):
                chave = ESCRITAS[alvo]
                # o cookie primeiro: sem ele, a rota nao se revela
                if not self._cookie_ok():
                    return self._negar(404, 'sem_cookie')  # numero-neutro: codigo HTTP
                if self._um('Origin') != dono.origem or self._um('Sec-Fetch-Site') != 'same-origin':
                    return self._negar(403, 'proibido')  # numero-neutro: codigo HTTP
                tipo = (self._um('Content-Type') or '').replace(' ', '').lower()
                if tipo not in TIPOS_JSON:
                    return self._negar(403, 'tipo_recusado')  # numero-neutro: codigo HTTP
                csrf = self._um(CABECALHO_CSRF)
                if csrf is None or not _iguais(csrf, dono.csrf):
                    return self._negar(403, 'csrf_recusado')  # numero-neutro: codigo HTTP
                tamanho = self._tamanho()
                if tamanho is None or tamanho < 1 or tamanho > dono.corpo_max:
                    return self._negar(403, 'corpo_recusado')  # numero-neutro: codigo HTTP
                corpo = self.rfile.read(tamanho)
                if len(corpo) != tamanho:
                    return self._negar(403, 'corpo_recusado')  # numero-neutro: codigo HTTP
                try:
                    dados = json.loads(corpo.decode('utf-8'))
                except (UnicodeDecodeError, ValueError):
                    return self._negar(403, 'dado_recusado')  # numero-neutro: codigo HTTP
                try:
                    feito = dono._escrever(chave, dados)
                except Exception:  # noqa: BLE001 - erro do ato: 500 sem detalhe, nada impresso
                    return self._negar(500, 'erro_do_ato')  # numero-neutro: codigo HTTP
                if feito is None:
                    return self._negar(403, 'dado_recusado')  # numero-neutro: codigo HTTP
                codigo, resposta = feito
                dono._contar(chave)
                if resposta is None:
                    return self._responder(codigo)
                return self._responder(codigo, json.dumps(resposta, ensure_ascii=False).encode('utf-8'), MIME_JSON)

            def _tratar(self):
                # o alvo como chegou na linha do pedido: o http.server junta // no inicio de self.path, e o
                # servidor recusa em vez de consertar
                partes_linha = (self.requestline or '').split(' ')
                alvo = partes_linha[1] if len(partes_linha) == 3 else self.path  # numero-neutro: metodo, alvo e versao
                # 1. extensao de fonte ou de PSD em qualquer forma: 404 antes de tudo
                if extensao_recusada(alvo):
                    return self._negar(404, 'extensao_recusada')  # numero-neutro: codigo HTTP
                # 2. so GET, e POST so nas rotas de escrita do servidor com a pasta do job
                if self.command not in METODOS:
                    return self._negar(404, 'metodo_recusado')  # numero-neutro: codigo HTTP
                escrita = self.command == 'POST'
                if escrita and (not dono.escreve or alvo not in ESCRITAS):
                    return self._negar(404, 'metodo_recusado')  # numero-neutro: codigo HTTP
                # 3. de onde vem o pedido
                if not self._origem_ok():
                    return self._negar(403, 'proibido')  # numero-neutro: codigo HTTP
                if escrita:
                    return self._tratar_escrita(alvo)
                # 4. a tabela: caminho exato, sem query nem %-codificacao
                if not alvo.startswith('/') or '?' in alvo or '%' in alvo or '#' in alvo:
                    return self._negar(404, 'nao_encontrado')  # numero-neutro: codigo HTTP
                partes = alvo.split('/')
                if len(partes) == 3 and partes[1] == 'entrar' and partes[2]:  # numero-neutro: /entrar/<token>
                    if not _TOKEN.match(partes[2]) or not dono._gastar_entrada(partes[2]):
                        return self._negar(404, 'nao_encontrado')  # numero-neutro: codigo HTTP
                    dono._contar('entrar')
                    # 204: a navegacao nao se completa, e a URL com o token nao entra no historico do perfil; o cookie
                    # de sessao (sem Max-Age, nunca gravado no disco) vale mesmo assim
                    return self._responder(204, extra=(  # numero-neutro: codigo HTTP
                        ('Set-Cookie', '%s=%s; HttpOnly; SameSite=Strict; Path=/' % (COOKIE, dono.sessao)),))
                achado = dono._rota(alvo) or dono._previa(alvo)
                if achado is None:
                    return self._negar(404, 'nao_encontrado')  # numero-neutro: codigo HTTP
                # 5. o cookie da sessao: sem ele, 404 (a rota nao se revela)
                if not self._cookie_ok():
                    return self._negar(404, 'sem_cookie')  # numero-neutro: codigo HTTP
                chave, servido = achado
                corpo, tipo = servido() if callable(servido) else servido
                dono._contar(chave)
                cache = CACHE_CONTROLE if chave == 'controle' else 'no-store'
                return self._responder(200, corpo, tipo, cache=cache)  # numero-neutro: codigo HTTP

            def do_GET(self):
                self._tratar()

            do_HEAD = do_POST = do_PUT = do_DELETE = do_OPTIONS = do_PATCH = do_TRACE = do_CONNECT = do_GET

        self._srv = _ServidorExclusivo(('127.0.0.1', 0), Tratador)
        self._fio = threading.Thread(target=self._srv.serve_forever, daemon=True)
        self._fio.start()
        return self

    def parar(self):
        """Para o servidor com espera limitada (tela.parar_max_s): o shutdown() do socketserver espera sem teto o
        serve_forever, e um serve_forever preso (um Thread.start que nao volta) virava um processo parado para
        sempre; aqui vira erro."""
        from desdobra import humano, limites
        preso = False
        if self._srv is not None:
            srv, fio, self._srv = self._srv, self._fio, None
            srv._BaseServer__shutdown_request = True  # o mesmo que shutdown() faz, sem a espera sem teto
            if fio is not None:
                fio.join(float(limites.valor('tela.parar_max_s')))
                preso = fio.is_alive()
            srv.server_close()
        humano.fechar_sessao_tela(self._sessao_humana)
        self._pendente = None
        if preso:
            raise RuntimeError('o servidor da tela não parou em %s s (serve_forever preso)'
                               % limites.valor('tela.parar_max_s'))

    def __enter__(self):
        return self.iniciar()

    def __exit__(self, *exc):
        self.parar()
        return False
