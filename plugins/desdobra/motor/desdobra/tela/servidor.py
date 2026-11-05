# -*- coding: utf-8 -*-
"""Servidor local da tela de briefing, so de leitura (M7a2; proposta do M7, secao 3 e fatia a2; arquitetura-v1.md, 3.4).

Regras (cada uma com teste em testes/test_tela_servidor.py):
  - escuta so em ('127.0.0.1', 0), nunca ::1 nem 0.0.0.0; sem allow_reuse_address e, no Windows, com
    SO_EXCLUSIVEADDRUSE: outro socket local nao toma a porta;
  - so GET (METODOS). O M7a0 nao tem rota de escrita: todo outro metodo da 404;
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
  - nada e impresso nem gravado: o token e a sessao ficam so na memoria deste processo e vao so ao Chromium que ele
    abre (url_entrada). O servidor so conta as respostas por rota (contagem).
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
from urllib.parse import unquote

from desdobra.chromium.servidor import CACHE_CONTROLE, _iguais

COOKIE = 'dsd_tela'
METODOS = ('GET',)
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
ROTAS = ('entrar', 'pagina', 'estatico', 'controle', 'estado', 'saude', 'previa', 'asset', 'fonte')
RECUSAS = ('proibido', 'nao_encontrado', 'sem_cookie', 'extensao_recusada', 'metodo_recusado', 'entrada_reusada')
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


class ServidorTela:
    """Uso:
        with ServidorTela(conteudo) as s:
            janela.ir(s.url_entrada)        # so para o Chromium da tela, nunca impresso

    conteudo: {'estado': dict, 'previas': {id: dict}, 'assets': {id: (bytes, mime)}, 'fontes': {id: (bytes, mime)},
               'estaticos': {caminho: (bytes, mime)} (opcional; padrao: desdobra.tela.estatico)}."""

    def __init__(self, conteudo):
        from desdobra.tela import estatico
        self.estado = conteudo['estado']
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
        self.token = secrets.token_hex(16)  # numero-neutro: bytes de entropia do token
        self.sessao = secrets.token_hex(16)  # numero-neutro: idem
        self.marcador_controle = secrets.token_hex(32).encode('ascii')  # numero-neutro: bytes de entropia do marcador
        self.contagem = {k: 0 for k in ROTAS + RECUSAS}
        self._entrada_usada = False
        self._trava = threading.Lock()
        self._srv = None
        self._fio = None

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
            return 'estado', (json.dumps(self.estado, ensure_ascii=False, default=str).encode('utf-8'), MIME_JSON)
        if caminho == '/api/saude':
            return 'saude', (json.dumps({'ok': True, 'somente_leitura': True}).encode('utf-8'), MIME_JSON)
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

            def _tratar(self):
                # o alvo como chegou na linha do pedido: o http.server junta // no inicio de self.path, e o
                # servidor recusa em vez de consertar
                partes_linha = (self.requestline or '').split(' ')
                alvo = partes_linha[1] if len(partes_linha) == 3 else self.path  # numero-neutro: metodo, alvo e versao
                # 1. extensao de fonte ou de PSD em qualquer forma: 404 antes de tudo
                if extensao_recusada(alvo):
                    return self._negar(404, 'extensao_recusada')  # numero-neutro: codigo HTTP
                # 2. so GET
                if self.command not in METODOS:
                    return self._negar(404, 'metodo_recusado')  # numero-neutro: codigo HTTP
                # 3. de onde vem o pedido
                if not self._origem_ok():
                    return self._negar(403, 'proibido')  # numero-neutro: codigo HTTP
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
                chave, (corpo, tipo) = achado
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
        if self._srv is not None:
            self._srv.shutdown()
            self._srv.server_close()
            self._srv = None

    def __enter__(self):
        return self.iniciar()

    def __exit__(self, *exc):
        self.parar()
        return False
