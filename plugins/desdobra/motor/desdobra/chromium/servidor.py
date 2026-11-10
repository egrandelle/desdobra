# -*- coding: utf-8 -*-
"""Servidor local da conferencia de fontes: a rota propria da fonte do job (arquitetura-v1.md, 3.4).

Regras:
  - escuta so em 127.0.0.1, numa porta livre escolhida pelo sistema;
  - rotas explicitas, sem listar diretorio: /entrar/<token>, /pagina (ou /pagina/<id>, quando o servidor recebe
    varias paginas, como no render), /fonte/<id> e /controle. Qualquer outro caminho, inclusive outra fonte, outro id
    ou caminho de arquivo, responde 404;
  - o token de sessao vai so na primeira URL e vira um cookie HttpOnly (SameSite=Strict); as outras rotas
    exigem o cookie, o Host 127.0.0.1:<porta> e, quando vem, o Origin da propria pagina (contra pagina de
    outro site e DNS rebinding);
  - a fonte e servida pelo id da face, a partir de bytes que o processo principal leu de entrada/fontes/ (ou
    da emenda da colecao feita com os deslocamentos que o filho mediu). O caminho nunca entra na URL;
  - toda resposta proibe cache (Cache-Control: no-store) e nao libera outra origem (sem CORS). A unica excecao e
    /controle, o controle positivo do teste de cache: uma folha de estilo so com um comentario de marcador
    aleatorio, nunca fonte, servida com cache liberado para provar que o perfil do Chromium grava cache;
  - token e cookie sao comparados como bytes: valor fora do ASCII da 404 ou 403, sem excecao nem traceback;
  - nada e impresso nem gravado: o servidor so conta as respostas por rota, para o teste e o relatorio.
"""
import http.server
import secrets
import threading
from http.cookies import SimpleCookie

COOKIE = 'dsd_sessao'
ROTA_CONTROLE = '/controle'
CACHE_CONTROLE = 'max-age=3600'  # numero-neutro: cache liberado so no controle positivo (segundos)
CABECALHOS_FIXOS = (('Cache-Control', 'no-store'), ('Pragma', 'no-cache'), ('X-Content-Type-Options', 'nosniff'),
                    ('Cross-Origin-Resource-Policy', 'same-origin'), ('Referrer-Policy', 'no-referrer'))
MIME_POR_FORMATO = {'ttf': 'font/ttf', 'otf': 'font/otf', 'ttc': 'font/collection', 'woff': 'font/woff',
                    'woff2': 'font/woff2'}


def _iguais(recebido, esperado):
    """Comparacao em tempo constante, em bytes: valor fora do ASCII nunca levanta excecao (so nao confere)."""
    return secrets.compare_digest(str(recebido).encode('utf-8', 'surrogateescape'), str(esperado).encode('utf-8'))


class _Servidor(http.server.ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        """Nada e impresso: um erro numa requisicao so fecha a conexao dela."""


class ServidorFontes:
    """Uso:
        with ServidorFontes(html, {'f01': (bytes, 'font/ttf')}) as s:
            navegador.abrir(s.url_entrada) ...
    """

    def __init__(self, pagina_html, fontes, *, cache_control='no-store', intervalo_s=None):
        # intervalo_s: o intervalo de consulta do serve_forever, que o parar() espera no pior caso (padrao o do
        # socketserver, meio segundo). So o Chromium aberto da tela pede um curto, na pagina de medida da quebra e na do
        # controle positivo da abertura dele (M7b, C3)
        # uma pagina (str, servida em /pagina) ou varias ({id: str}, servidas em /pagina/<id>; o render usa uma por
        # camada de texto e cor)
        if isinstance(pagina_html, dict):
            self.paginas = {k: v.encode('utf-8') for k, v in pagina_html.items()}
            self.pagina = None
        else:
            self.paginas = {}
            self.pagina = pagina_html.encode('utf-8')
        self.fontes = dict(fontes)
        self.token = secrets.token_hex(16)  # numero-neutro: bytes de entropia do token
        self.sessao = secrets.token_hex(16)  # numero-neutro: idem
        self.cache_control = cache_control  # so o teste do metodo de varredura troca isto
        self.marcador_controle = secrets.token_hex(32).encode('ascii')  # numero-neutro: bytes de entropia do marcador
        self.contagem = {'entrar': 0, 'pagina': 0, 'fonte': 0, 'controle': 0, 'nao_encontrado': 0, 'proibido': 0}
        self.intervalo_s = intervalo_s
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
        return '%s/entrar/%s' % (self.origem, self.token)

    def url_pagina(self, ident):
        return '%s/pagina/%s' % (self.origem, ident)

    @property
    def primeira_pagina(self):
        return '/pagina' if self.pagina is not None else '/pagina/%s' % next(iter(self.paginas))

    def iniciar(self):
        dono = self

        class Tratador(http.server.BaseHTTPRequestHandler):
            server_version = 'desdobra'
            sys_version = ''

            def log_message(self, *a):  # nada no terminal nem em arquivo
                pass

            def _responder(self, codigo, corpo=b'', tipo='text/plain; charset=utf-8', extra=(), cache=None):
                self.send_response(codigo)
                for k, v in CABECALHOS_FIXOS:
                    if k == 'Cache-Control':
                        v = cache or dono.cache_control
                    elif k == 'Pragma' and cache:
                        continue
                    self.send_header(k, v)
                self.send_header('Content-Type', tipo)
                self.send_header('Content-Length', str(len(corpo)))
                for k, v in extra:
                    self.send_header(k, v)
                self.end_headers()
                if corpo and self.command != 'HEAD':
                    self.wfile.write(corpo)

            def _negar(self, codigo):
                dono.contagem['proibido' if codigo == 403 else 'nao_encontrado'] += 1  # numero-neutro: codigo HTTP
                self._responder(codigo)

            def _cookie_ok(self):
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
                if self.headers.get('Host') != '127.0.0.1:%d' % dono.porta:
                    return False
                origem = self.headers.get('Origin')
                return origem in (None, dono.origem)

            def do_GET(self):
                if not self._origem_ok():
                    return self._negar(403)  # numero-neutro: codigo HTTP
                caminho = self.path.split('?', 1)[0]
                partes = caminho.split('/')
                if len(partes) == 3 and partes[1] == 'entrar':  # numero-neutro: /entrar/<token>
                    if not _iguais(partes[2], dono.token):
                        return self._negar(404)  # numero-neutro: codigo HTTP
                    dono.contagem['entrar'] += 1
                    return self._responder(303, extra=(  # numero-neutro: codigo HTTP
                        ('Location', dono.primeira_pagina),
                        ('Set-Cookie', '%s=%s; HttpOnly; SameSite=Strict; Path=/' % (COOKIE, dono.sessao))))
                if (caminho == '/pagina' and dono.pagina is not None) or (
                        len(partes) == 3 and partes[1] == 'pagina' and partes[2] in dono.paginas):  # numero-neutro: /pagina/<id>
                    if not self._cookie_ok():
                        return self._negar(403)  # numero-neutro: codigo HTTP
                    dono.contagem['pagina'] += 1
                    corpo = dono.pagina if caminho == '/pagina' else dono.paginas[partes[2]]
                    return self._responder(200, corpo, 'text/html; charset=utf-8', extra=(  # numero-neutro: codigo HTTP
                        ('Content-Security-Policy', "default-src 'none'; font-src 'self'; style-src 'self' "
                                                    "'unsafe-inline'; script-src 'none'"),))
                if caminho == ROTA_CONTROLE:
                    if not self._cookie_ok():
                        return self._negar(403)  # numero-neutro: codigo HTTP
                    dono.contagem['controle'] += 1
                    corpo = b'/* ' + dono.marcador_controle + b' */' + bytes([10])
                    return self._responder(200, corpo, 'text/css; charset=utf-8', cache=CACHE_CONTROLE)  # numero-neutro: codigo HTTP
                if len(partes) == 3 and partes[1] == 'fonte' and partes[2] in dono.fontes:  # numero-neutro: /fonte/<id>
                    if not self._cookie_ok():
                        return self._negar(403)  # numero-neutro: codigo HTTP
                    dados, tipo = dono.fontes[partes[2]]
                    dono.contagem['fonte'] += 1
                    return self._responder(200, dados, tipo)  # numero-neutro: codigo HTTP
                return self._negar(404)  # numero-neutro: codigo HTTP

            def do_HEAD(self):
                self._negar(404)  # numero-neutro: codigo HTTP

            def do_POST(self):
                self._negar(404)  # numero-neutro: codigo HTTP

            do_PUT = do_DELETE = do_OPTIONS = do_PATCH = do_POST

        self._srv = _Servidor(('127.0.0.1', 0), Tratador)
        self._srv.daemon_threads = True
        kw = {} if self.intervalo_s is None else {'poll_interval': float(self.intervalo_s)}
        self._fio = threading.Thread(target=self._srv.serve_forever, kwargs=kw, daemon=True)
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
