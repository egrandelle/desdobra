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
  - cronometro da mestre (POST /api/medicao; M7b, C5): o sinal de clique ou tecla da pagina, com a familia aberta e as
    edicoes e as quebras feitas, vai ao cronometro da janela (desdobra.tela.cronometro), que grava so
    medicoes/tela.json; o ato "Confirmar familia" feito para o cronometro da familia. Se a familia esta confirmada, o
    cronometro pergunta ao servidor, que le o rascunho sob a trava de escrita e com a regra da confirmacao velha da
    tela (_confirmada_na_tela). A resposta e 204, sem corpo;
  - atos humanos (/api/ato/pedir, /api/ato/confirmar, /api/ato/cancelar; decisoes-v1.md, 159; proposta do M7, 159b):
    o clique do DA pede um ato da tabela do servidor (Ato); o servidor devolve um pedido de uso unico e o texto do
    dialogo, que a janela mostra sem opcao marcada. So o confirmar com o pedido vivo e a resposta "confirmar" emite o
    Disparo da tela (humano.exigir_tela, meio tela), e o pedido morre nele; cancelar, um pedido novo ou o pedido
    errado nao executam nada. No modo de teste (proposta do M7, 159c) o Disparo sai com meio medicao e origem
    fixture_de_teste, e o rascunho com origem fixture_de_teste; o modo de teste recusa o job com briefing ou rascunho
    do DA, e nenhum comando da CLI o abre;
  - ato longo (Ato.longo; M7b, B1): o Confirmar emite o Disparo, pega a trava do job e responde 202 com o id da tarefa
    (desdobra.tela.tarefas), que roda no fio de trabalho unico do servidor. A pagina acompanha por GET
    /api/tarefa/<id> (etapa, formato, prontos, texto do motor) e cancela por POST /api/tarefa/cancelar, com as
    mesmas conferencias da escrita. Enquanto a tarefa roda, /api/estado e o rascunho respondem sem montar a tela de
    novo (o estado leva a tarefa e edicao_bloqueada), e a previa da edicao e os atos sao recusados (403,
    tarefa_em_andamento). Na saida, parar() pede a parada da tarefa e espera no maximo tela.parar_max_s;
  - ato com preparo (Ato.preparar; M7b, B2): o pedir responde 202 com a tarefa do preparo, que confere o que o ato vai
    fazer fora da trava de escrita; o pedido de uso unico e o texto do dialogo saem na resposta da tarefa. Com
    Ato.selo_por_formato, a confirmacao do DA emite um Disparo por formato, preso a ele (o render da tela). O aprovar da
    tela (M7b, B4) usa o preparo para gerar o arquivo final de cada formato, que o servidor mostra por /final antes do
    dialogo, e Ato.outros_comandos para gravar o sentido do giro com a mesma confirmacao (um Disparo do
    parametros-entrega ao lado do Disparo do aprovar);
  - antes do roteamento, 404 para o caminho cru e o decodificado que citam .ttf .otf .ttc .woff .woff2 .psd .psb, sem
    diferenca de maiuscula, com ponto e espaco no fim e ::$DATA normalizados (decisoes-v1.md, proposta 167);
  - depois, Host igual a 127.0.0.1:<porta>, cliente 127.0.0.1, Origin ausente ou a propria, Sec-Fetch-Site ausente ou
    da mesma origem (contra pagina de outro site e DNS rebinding): fora disso, 403;
  - rotas explicitas (tabela em _rota): /entrar/<token>, /, /tela.js, /tela.css, /fontes.css, /controle,
    /api/estado, /api/saude, /api/previa/<id>, /api/tarefa/<id> (so no servidor que grava, so JSON), /asset/<id>,
    /fonte/<id ou sha256> e, so no servidor que grava, /render/<formato> e /final/<formato>. Caminho fora da tabela,
    com query, com % ou com barra a mais da 404;
  - rotas de imagem (M7b, B3): o id segue ID_PREVIA e e formato do briefing confirmado, e tudo e lido do disco so
    depois do cookie. /render/<formato> serve render/<formato>/master.png quando o sha256 dos bytes lidos e o do
    render.json do formato e do job; /final/<formato> serve entrega/previa/<formato>.<png ou jpg> quando o sha256 e o do
    arquivo final que o portao gerou nesta janela (mostrar_final). So image/png e image/jpeg, conferidos pelos primeiros
    bytes, e o caminho real nao pode sair do lugar dele no job (juncao ou link): fora disso, 404. Nunca servem
    .trabalho, PDF, fonte nem pagina de texto;
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
import os
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
# /api/medicao nao decide nada: e o sinal do cronometro da mestre (desdobra.tela.cronometro; M7b, C5), que grava so
# medicoes/tela.json, fora do briefing, e passa pelas mesmas conferencias da escrita
ESCRITAS = {'/api/rascunho': 'rascunho', '/api/ato/pedir': 'ato_pedir', '/api/ato/confirmar': 'ato_confirmar',
            '/api/ato/cancelar': 'ato_cancelar', '/api/familia/previa': 'familia_previa',
            '/api/tarefa/cancelar': 'tarefa_cancelar', '/api/medicao': 'medicao'}
# escritas recusadas enquanto uma tarefa longa roda (a edicao fica bloqueada; M7b, B1): a previa disputaria o fio do
# HiGHS com o render (decisoes-v1.md, 172), e todo ato pega a trava do job, que fica com a tarefa
BLOQUEADAS_NA_TAREFA = ('familia_previa', 'ato_pedir', 'ato_confirmar')
CABECALHO_CSRF = 'X-Desdobra-CSRF'
TIPOS_JSON = ('application/json', 'application/json;charset=utf-8')
META_CSRF = '<meta name="dsd-csrf" content="%s">'
RESPOSTA_CONFIRMAR = 'confirmar'
# as chaves do dialogo de confirmacao, que so o servidor poe (o preparo de um ato nao as troca)
CHAVES_DO_DIALOGO = ('pedido', 'titulo', 'texto', 'sim', 'nao')
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
# as rotas de imagem do servidor que grava (M7b, B3): /render/<formato> (o master) e /final/<formato> (o arquivo final
# que o portao gerou para a aprovacao). So estes dois tipos saem, e o conteudo e conferido pelos primeiros bytes
ROTAS_DE_IMAGEM = ('render', 'final')
MIME_IMAGEM = {'png': 'image/png', 'jpg': 'image/jpeg'}
ASSINATURAS_IMAGEM = {'png': b'\x89PNG\r\n\x1a\n', 'jpg': b'\xff\xd8\xff'}  # numero-neutro: assinaturas dos formatos
# contagem por rota servida; as recusas tem contagem propria
ROTAS = ('entrar', 'pagina', 'estatico', 'controle', 'estado', 'saude', 'previa', 'asset', 'fonte', 'rascunho_lido',
         'tarefa') + ROTAS_DE_IMAGEM + tuple(ESCRITAS.values())
RECUSAS = ('proibido', 'nao_encontrado', 'sem_cookie', 'extensao_recusada', 'metodo_recusado', 'entrada_reusada',
           'tipo_recusado', 'csrf_recusado', 'corpo_recusado', 'dado_recusado', 'erro_do_ato', 'tarefa_em_andamento')
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
    (texto(dados) -> str), para o dialogo dizer o que sera gravado. longo: o ato roda como tarefa em segundo plano
    (desdobra.tela.tarefas), com executar(disparo, dados, tarefa); formatos(dados) -> [ids] diz os formatos dela.
    preparar(dados, tarefa) -> {'texto', 'vista', 'guardado'} (M7b, B2): o pedido nao monta o texto no fio do pedido
    HTTP; ele vira uma tarefa (fio de trabalho, com a trava do job e fora da trava de escrita) que confere o que o ato
    vai fazer e devolve o texto do dialogo, o que mais a pagina mostra nele (vista) e o que o servidor guarda no pedido
    pendente (guardado, nunca enviado a pagina). O executar recebe preparado=<guardado> no Confirmar.
    selo_por_formato: o Confirmar emite um Disparo por formato (humano.exigir_tela com alvo), e executar recebe
    {formato: Disparo} no lugar do Disparo unico. O preparo pode devolver tambem 'finais' ({formato: ArquivoFinal}, M7b,
    B4): o servidor os mostra na janela (/final/<formato>, mostrar_final) antes de abrir o dialogo.
    outros_comandos(dados) -> [comandos] (M7b, B4; so em ato longo): a mesma confirmacao do DA emite tambem um Disparo
    da tela de cada um desses comandos (o aprovar da tela grava o sentido do giro com o do parametros-entrega), e
    executar recebe outros={comando: Disparo}; todos sao gastos quando a tarefa acaba."""
    comando: str
    titulo: str
    texto: str
    sim: str
    nao: str
    executar: Callable
    validar: Callable | None = None
    longo: bool = False
    formatos: Callable | None = None
    preparar: Callable | None = None
    selo_por_formato: bool = False
    outros_comandos: Callable | None = None


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
    atos: {nome: Ato} dos botoes que pedem confirmacao na janela.
    relogio: o relogio do cronometro da mestre (desdobra.tela.cronometro; padrao time.time, o falso nos testes)."""

    def __init__(self, conteudo, pasta=None, modo_teste=False, atos=None, relogio=None):
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
        self.sem_edicao_da_tela = {g: f.get('pecas_sem_edicao') for g, f in (conteudo.get('familias') or {}).items()}
        # {id do elemento: [layer_ids]} da mestre da tela: a quebra de linha do rascunho cita um deles (revisao 2 do C)
        self.elementos_da_tela = conteudo.get('elementos')
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
            if (ato.preparar is not None or ato.selo_por_formato or ato.outros_comandos is not None) and \
                    not (ato.longo and callable(ato.formatos)):
                raise ValueError('ato fora do padrao')  # o preparo e os selos a mais sao de ato longo
        self.pasta = Path(pasta).resolve() if pasta is not None else None
        self.modo_teste = bool(modo_teste)
        self.laudo_sha256 = None
        self.job_id = None
        self.csrf = None
        self.origem_rascunho = modelo.ORIGEM_FIXTURE if self.modo_teste else modelo.ORIGEM_RASCUNHO
        self.corpo_max = int(limites.valor('tela.corpo_max_bytes'))
        self.espera_rascunho_ms = limites.valor('tela.rascunho_espera_ms')
        self._sessao_humana = None
        # as tarefas longas (desdobra.tela.tarefas), so no servidor que grava; o aviso do render que a janela anterior
        # deixou pela metade vem do processo de fundo (tarefas.recuperar, antes da montagem)
        self.tarefas = None
        self.render_inacabado = conteudo.get('render_inacabado')
        self._tarefas_do_aviso = set()  # as tarefas que ja mexeram no aviso (_aviso_depois_da_tarefa)
        self._recarregar_depois = False
        # {formato: (sha256, extensao)} dos arquivos finais que o portao gerou nesta janela (mostrar_final; M7b, B3)
        self._finais = {}
        # o cronometro da mestre desta janela (M7b, C5), so no servidor que grava
        self.cronometro = None
        if self.pasta is not None:
            self.laudo_sha256 = rascunho.laudo_sha256(self.pasta)
            self.job_id = (conteudo.get('estado') or {}).get('job_id')
            if self.laudo_sha256 is None or not self.job_id:
                raise ValueError('a escrita da tela pede o laudo e o job')
            if self.modo_teste and _job_do_da(self.pasta):
                raise ValueError('o modo de teste da tela so roda em job sintetico')
            self.csrf = secrets.token_hex(16)  # numero-neutro: bytes de entropia do token CSRF
            self._sessao_humana = humano.abrir_sessao_tela(teste=self.modo_teste)
            from desdobra.tela import cronometro, tarefas
            self.tarefas = tarefas.Tarefas(self.pasta)
            self.cronometro = cronometro.Cronometro(self.pasta, self.job_id, relogio=relogio,
                                                    origem=modelo.ORIGEM_FIXTURE if self.modo_teste else 'da',
                                                    confirmada=self._confirmada_na_tela)
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
        self._pendente = None  # (pedido, nome do ato, dados, preparado) do unico ato a confirmar
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
        if nome in ROTAS_DE_IMAGEM and self.escreve and ID_PREVIA.match(ident):
            return nome, lambda: self._imagem(nome, ident)  # o briefing e os bytes, so depois do cookie
        return None

    # -------------------------------------------------------------- imagens (M7b, B3)
    def mostrar_final(self, formato, final):
        """O portao gerou o arquivo final do formato (desdobra.entrega.codificar.ArquivoFinal) e o gravou na previa
        (entrega/previa/<formato>.<extensao>) para o DA conferir antes de aprovar: /final/<formato> passa a servir esse
        arquivo, e so enquanto o sha256 dos bytes lidos for o dele. final None tira o formato da janela. ValueError no
        servidor so de leitura, com id fora do padrao ou com extensao que nao e de imagem (so png e jpg)."""
        if not self.escreve or not isinstance(formato, str) or not ID_PREVIA.match(formato):
            raise ValueError('formato fora do padrao')
        if final is not None and final.extensao not in MIME_IMAGEM:
            raise ValueError('o arquivo final da tela e png ou jpg')
        with self._trava:
            if final is None:
                self._finais.pop(formato, None)
            else:
                self._finais[formato] = (final.sha256, final.extensao)

    def _ler_no_job(self, rel):
        """Os bytes de <pasta do job>/<rel>, ou None quando o arquivo falta ou o caminho real sai dele (juncao ou link
        de uma pasta para outra, dentro ou fora do job)."""
        caminho = self.pasta / rel
        try:
            real = caminho.resolve(strict=True)
            if os.path.normcase(str(real)) != os.path.normcase(str(caminho)) or not real.is_file():
                return None
            return real.read_bytes()
        except (OSError, RuntimeError):
            return None

    def _imagem(self, nome, formato):
        """(bytes, tipo) da rota de imagem, ou None (404). O formato tem de ser do briefing confirmado. /render: o
        render/<formato>/master.png, com o render.json do formato e do job no esquema e o sha256 dos bytes lidos igual ao
        do master dele. /final: o arquivo da previa que o portao mostrou nesta janela (mostrar_final), pelo sha256. Em
        todos, os primeiros bytes tem de ser os do tipo (png ou jpg): nunca sai PDF, fonte nem pagina de texto. O caminho
        nunca vem do arquivo lido: e montado do id conferido."""
        from desdobra import arquivos, contratos
        from desdobra.briefing import modelo
        from desdobra.entrega import aprovacao
        from desdobra.render import execucao
        try:
            b = modelo.ler(self.pasta)
        except (contratos.ErroContrato, OSError, ValueError):
            return None
        if not b or formato not in {f.get('id') for f in b.get('formatos') or []}:
            return None
        if nome == 'render':
            base = Path('render') / formato
            bruto = self._ler_no_job(base / 'render.json')
            if bruto is None:
                return None
            try:
                rel = contratos.validar(json.loads(bruto.decode('utf-8')), execucao.ESQUEMA_RENDER)
            except (UnicodeDecodeError, ValueError, contratos.ErroContrato):
                return None
            if rel.get('job_id') != self.job_id or (rel.get('formato') or {}).get('chave') != formato:
                return None
            esperado, extensao, arq = rel['master']['sha256'], 'png', base / 'master.png'
        else:
            with self._trava:
                mostrado = self._finais.get(formato)
            if mostrado is None:
                return None
            esperado, extensao = mostrado
            arq = aprovacao.PASTA_PREVIA / ('%s.%s' % (formato, extensao))
        dados = self._ler_no_job(arq)
        if dados is None or arquivos.sha256_bytes(dados) != esperado:
            return None
        if not dados.startswith(ASSINATURAS_IMAGEM[extensao]):
            return None
        return dados, MIME_IMAGEM[extensao]

    def _previa(self, caminho):
        partes = caminho.split('/')
        if len(partes) == 4 and partes[1] == 'api' and partes[2] == 'previa' and partes[3] in self.previas:  # numero-neutro: /api/previa/<id>
            d = self.previas[partes[3]]
            return 'previa', (json.dumps(d, ensure_ascii=False, default=str).encode('utf-8'), MIME_JSON)
        return None

    def _tarefa(self, caminho):
        """/api/tarefa/<id>: a vista da tarefa deste servidor, lida so depois do cookie."""
        from desdobra.tela import tarefas
        partes = caminho.split('/')
        if self.tarefas is None or len(partes) != 4 or partes[1] != 'api' or partes[2] != 'tarefa':  # numero-neutro: /api/tarefa/<id>
            return None
        t = self.tarefas.obter(partes[3]) if tarefas.ID_TAREFA.match(partes[3]) else None
        if t is None:
            return None
        return 'tarefa', lambda: (json.dumps(t.vista(), ensure_ascii=False, default=str).encode('utf-8'), MIME_JSON)

    def bloqueada(self, chave):
        """A escrita `chave` espera a tarefa longa acabar (a edicao fica bloqueada durante ela)."""
        return chave in BLOQUEADAS_NA_TAREFA and self.tarefas is not None and self.tarefas.ocupada

    def _estado_servido(self):
        if self.escreve:
            with self._trava_escrita:
                # com a tarefa rodando, a trava do job e dela: a tela nao tenta se montar de novo (o aviso de job
                # ocupado daria lugar ao trabalho em andamento) e responde ja com o que tem
                if not self.tarefas.ocupada:
                    self._aviso_depois_da_tarefa()
                    self._depois_da_tarefa()
                    self._atualizar()
        return json.dumps(self._estado_com_tarefa(), ensure_ascii=False, default=str).encode('utf-8'), MIME_JSON

    def _estado_com_tarefa(self):
        """O estado servido: o da montagem, com a ultima tarefa (ou None), edicao_bloqueada e o aviso do render que a
        janela anterior deixou pela metade (render_inacabado)."""
        extra = {}
        if self.tarefas is not None:
            t = self.tarefas.ultima
            extra['tarefa'] = t.vista() if t is not None else None
            extra['edicao_bloqueada'] = self.tarefas.ocupada
        if self.render_inacabado:
            extra['render_inacabado'] = self.render_inacabado
        return dict(self.estado, **extra) if extra else self.estado

    def _aviso_depois_da_tarefa(self):
        """O aviso da reabertura (render_inacabado) perde os formatos que as tarefas acabadas desde o ultimo pedido
        refizeram nesta janela, uma vez por tarefa e na ordem delas (tarefas.aviso_depois_da_tarefa; segunda revisao do
        M7b, fase B)."""
        from desdobra.tela import tarefas
        for t in self.tarefas.acabadas():
            if t.id in self._tarefas_do_aviso:
                continue
            self._tarefas_do_aviso.add(t.id)
            self.render_inacabado = tarefas.aviso_depois_da_tarefa(self.render_inacabado, t)

    def _depois_da_tarefa(self):
        """A primeira montagem depois de uma tarefa longa: o recarregar, como depois de todo ato. O erro deixa o aviso
        e tenta de novo no proximo pedido."""
        if not self._recarregar_depois or not callable(self.recarregar):
            self._recarregar_depois = False
            return
        try:
            self.estado = self.recarregar()
        except Exception as e:  # noqa: BLE001 - job ocupado por outro comando: fica o estado de antes, com o aviso
            self._avisar(AVISO_JOB_OCUPADO if getattr(e, 'motivo', None) == 'job_ocupado' else AVISO_SEM_ATUALIZAR)
            return
        self._recarregar_depois = False

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
        self.sem_edicao_da_tela = {g: f.get('pecas_sem_edicao') for g, f in (novo.get('familias') or {}).items()}
        self.elementos_da_tela = novo.get('elementos')
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
            dados = rascunho.sem_confirmacao_velha(dados, self.familias_da_tela, self.pecas_da_tela,
                                                   self.sem_edicao_da_tela)
        corpo = {'rascunho': dados, 'de_outro_laudo': de_outro, 'espera_ms': self.espera_rascunho_ms,
                 'job_id': self.job_id, 'laudo_sha256': self.laudo_sha256}
        return json.dumps(corpo, ensure_ascii=False).encode('utf-8'), MIME_JSON

    def _escrever(self, chave, dados):
        """(codigo, dict ou None) da escrita aceita, ou None quando recusada (403 sem detalhe)."""
        if chave == 'familia_previa':
            return self._previa_da_familia(dados)
        if chave == 'tarefa_cancelar':
            return self._cancelar_tarefa(dados)
        if chave == 'medicao':
            return self._sinal_do_cronometro(dados)
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
        # as edicoes que o rascunho ja tem da familia: o tamanho gravado fora dos limites (a tela de antes do D3) nunca
        # trava a previa (revisao 1 da fase D)
        antes = self._edicoes_gravadas(dados.get('familia') if isinstance(dados, dict) else None)
        with self._trava_previa:
            r = self.editar(dados, origem=origem, **({'antes': antes} if antes else {}))
        return None if r is None else (200, r)  # numero-neutro: codigo HTTP

    def _edicoes_gravadas(self, familia):
        """As edicoes da familia no rascunho gravado, lidas sob a trava de escrita (como _rascunho_lido); [] sem
        rascunho, de outro laudo ou que nao se le agora."""
        from desdobra.tela import rascunho
        if not isinstance(familia, str) or self.pasta is None or self.laudo_sha256 is None:
            return []
        try:
            with self._trava_escrita:
                dados, _de_outro = rascunho.ler(self.pasta, self.laudo_sha256)
        except (OSError, ValueError):
            return []
        return list((((dados or {}).get('familias') or {}).get(familia) or {}).get('edicoes') or [])

    def _sinal_do_cronometro(self, dados):
        """O clique ou a tecla da pagina para o cronometro da mestre (M7b, C5): a familia tem de ser uma das que a
        tela mostra agora (ou nenhuma, fora do passo 3). Fora da trava de escrita: o cronometro tem a dele. So o sinal
        sem edicao de uma familia le o rascunho, e essa leitura espera a trava (_confirmada_na_tela)."""
        from desdobra.tela import cronometro
        sinal = cronometro.conferir_sinal(dados, set(self.familias_da_tela))
        if sinal is None:
            return None
        self.cronometro.sinal(*sinal)
        return 204, None  # numero-neutro: codigo HTTP

    def _confirmada_na_tela(self, familia):
        """A familia esta confirmada como a tela a mostra agora, para o cronometro (revisao do C5): o rascunho e lido
        sob a trava de escrita, como _rascunho_lido (no Windows, o arquivo aberto para leitura faz a troca atomica do
        autosave falhar), e a confirmacao velha sai pela mesma regra da pagina (rascunho.sem_confirmacao_velha: a
        familia que ganhou ou perdeu formatos, ou mudou de pecas, pede a confirmacao de novo)."""
        from desdobra.tela import rascunho
        try:
            with self._trava_escrita:
                dados, _de_outro = rascunho.ler(self.pasta, rascunho.laudo_sha256(self.pasta))
        except (OSError, ValueError):
            return False  # o rascunho que nao se le agora: a familia conta como aberta
        if dados is None or dados['laudo_sha256'] != self.laudo_sha256:
            return False
        if self.familias_da_tela:
            dados = rascunho.sem_confirmacao_velha(dados, self.familias_da_tela, self.pecas_da_tela,
                                                   self.sem_edicao_da_tela)
        return bool(((dados.get('familias') or {}).get(familia) or {}).get('confirmada'))

    def _cronometro_depois_do_ato(self, ato, resposta):
        """O ato "Confirmar familia" feito para o cronometro da familia. A medicao nunca muda a resposta do ato."""
        from desdobra.tela import rascunho
        if ato.comando != rascunho.COMANDO_FAMILIA or not isinstance(resposta, dict) or not resposta.get('confirmada'):
            return
        try:
            self.cronometro.confirmar(resposta['familia'])
        except Exception:  # noqa: BLE001 - a medicao nunca atrapalha o ato: a familia ja esta confirmada
            pass

    def _gravar_rascunho(self, dados):
        from desdobra.tela import rascunho
        laudo_agora = rascunho.laudo_sha256(self.pasta)
        if laudo_agora != self.laudo_sha256:
            return None  # o PSD foi relido com a tela aberta: o rascunho desta pagina e de outro laudo
        try:
            # cada familia mexida guarda os formatos que a tela mostra para ela agora (revisao do M7b, fase A)
            gravado = rascunho.gravar(self.pasta, dados, job_id=self.job_id, laudo_atual=laudo_agora,
                                      origem=self.origem_rascunho, familias_da_tela=self.familias_da_tela,
                                      elementos_da_tela=self.elementos_da_tela)
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
        if ato.preparar is not None:
            return self._preparar_ato(dados['ato'], ato, dados['dados'])
        pedido = secrets.token_hex(16)  # numero-neutro: bytes de entropia do pedido
        self._pendente = (pedido, dados['ato'], dados['dados'], None)  # um pedido novo derruba o anterior
        texto = ato.texto(dados['dados']) if callable(ato.texto) else ato.texto
        return 200, {'pedido': pedido, 'titulo': ato.titulo, 'texto': texto, 'sim': ato.sim,  # numero-neutro: codigo HTTP
                     'nao': ato.nao}

    def _preparar_ato(self, nome, ato, dados):
        """O pedido do ato com preparo (M7b, B2): o preparo roda como tarefa sem marcador (desdobra.tela.tarefas), com a
        trava do job e fora da trava de escrita, e a resposta e 202 com o id dela. No fim, a tarefa leva na resposta o
        pedido de uso unico e o texto do dialogo, como o pedido comum; o que o preparo guardou fica so no pedido
        pendente. Job ocupado ou outra tarefa: recusa."""
        from desdobra.job import nucleo
        from desdobra.tela import tarefas
        self._pendente = None  # um pedido novo derruba o anterior, mesmo antes de o preparo acabar

        def rodar(tarefa):
            preparo = ato.preparar(dados, tarefa)
            if tarefa.parar():
                return None
            # o arquivo final de cada formato que o preparo gerou (o aprovar, M7b, B4): a janela o mostra por /final
            for fid, final in (preparo.get('finais') or {}).items():
                self.mostrar_final(fid, final)
            pedido = secrets.token_hex(16)  # numero-neutro: bytes de entropia do pedido
            with self._trava_escrita:
                self._pendente = (pedido, nome, dados, preparo['guardado'])
            vista = {k: v for k, v in (preparo.get('vista') or {}).items() if k not in CHAVES_DO_DIALOGO}
            return dict(vista, pedido=pedido, titulo=ato.titulo, texto=preparo['texto'], sim=ato.sim, nao=ato.nao)
        try:
            t = self.tarefas.iniciar(tarefas.TAREFA_PREPARO, rodar, marcador=False)
        except (tarefas.ErroTarefa, nucleo.ErroJob):
            return None
        return 202, {'tarefa': t.id}  # numero-neutro: codigo HTTP

    def _cancelar_ato(self, dados):
        if not isinstance(dados, dict) or set(dados) != {'pedido'} or not self._pedido_vivo(dados['pedido']):
            return None
        self._pendente = None
        return 204, None  # numero-neutro: codigo HTTP

    def _cancelar_tarefa(self, dados):
        """O DA cancelou a tarefa longa: a parada vale entre formatos e entre as etapas do render (o formato cortado
        pede render de novo, os prontos ficam)."""
        if not isinstance(dados, dict) or set(dados) != {'tarefa'} or not isinstance(dados['tarefa'], str):
            return None
        return (204, None) if self.tarefas.cancelar(dados['tarefa']) else None  # numero-neutro: codigo HTTP

    def _iniciar_tarefa(self, nome, ato, dados, preparado=None):
        """O ato longo confirmado: o Disparo e a trava do job vao para a tarefa, e a resposta e 202 com o id dela. Job
        ocupado (outro comando do desdobra ou outra tarefa): recusa, com o Disparo gasto. Com selo_por_formato (M7b,
        B2), a confirmacao do DA emite um Disparo por formato, preso a ele (humano.exigir_tela com alvo), e todos sao
        gastos quando a tarefa acaba, usados ou nao."""
        from desdobra import humano
        from desdobra.job import nucleo
        from desdobra.tela import tarefas
        formatos = list(ato.formatos(dados)) if callable(ato.formatos) else []
        outros_comandos = list(ato.outros_comandos(dados)) if callable(ato.outros_comandos) else []
        selos, outros = [], {}
        try:
            if ato.selo_por_formato:
                if not formatos or len(set(formatos)) != len(formatos):
                    return None
                for f in formatos:
                    selos.append(humano.exigir_tela(ato.comando, self._sessao_humana, confirmado=True, alvo=f))
                disparo = dict(zip(formatos, selos))
            else:
                selos.append(humano.exigir_tela(ato.comando, self._sessao_humana, confirmado=True))
                disparo = selos[0]
            # a mesma confirmacao do DA vale para os outros comandos do ato (M7b, B4: o sentido do giro no aprovar)
            for c in dict.fromkeys(outros_comandos):
                outros[c] = humano.exigir_tela(c, self._sessao_humana, confirmado=True)
                selos.append(outros[c])
        except (humano.ErroHumano, ValueError):
            for d in selos:
                humano.gastar(d)
            return None
        extra = {'preparado': preparado} if ato.preparar is not None else {}
        if ato.outros_comandos is not None:
            extra['outros'] = outros

        def rodar(tarefa):
            try:
                return ato.executar(disparo, dados, tarefa, **extra)
            finally:
                for d in selos:
                    humano.gastar(d)  # o selo de uso unico nunca passa da tarefa
        try:
            t = self.tarefas.iniciar(nome, rodar, formatos=formatos)
        except (tarefas.ErroTarefa, nucleo.ErroJob):
            for d in selos:
                humano.gastar(d)
            return None
        self._recarregar_depois = True
        return 202, {'tarefa': t.id}  # numero-neutro: codigo HTTP

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
        _pedido, nome, dados_ato, preparado = self._pendente
        self._pendente = None  # o pedido morre antes do ato
        ato = self.atos[nome]
        # os dados valem de novo no Confirmar: o que mudou no disco depois do pedido nao ganha o clique do DA. O ato
        # com preparo confere de novo, na tarefa, o que o preparo guardou (o contrato de cada formato, no render)
        if ato.validar is not None and ato.validar(dados_ato) is not True:
            return None
        if ato.longo:
            return self._iniciar_tarefa(nome, ato, dados_ato, preparado)
        try:
            disparo = humano.exigir_tela(ato.comando, self._sessao_humana, confirmado=True)
        except humano.ErroHumano:
            return None
        resposta = ato.executar(disparo, dados_ato)
        self._cronometro_depois_do_ato(ato, resposta)
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
                if dono.bloqueada(chave):
                    return self._negar(403, 'tarefa_em_andamento')  # numero-neutro: codigo HTTP
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
                achado = dono._rota(alvo) or dono._previa(alvo) or dono._tarefa(alvo)
                if achado is None:
                    return self._negar(404, 'nao_encontrado')  # numero-neutro: codigo HTTP
                # 5. o cookie da sessao: sem ele, 404 (a rota nao se revela)
                if not self._cookie_ok():
                    return self._negar(404, 'sem_cookie')  # numero-neutro: codigo HTTP
                chave, servido = achado
                servido = servido() if callable(servido) else servido
                if servido is None:  # a rota de imagem sem arquivo que confira (M7b, B3)
                    return self._negar(404, 'nao_encontrado')  # numero-neutro: codigo HTTP
                corpo, tipo = servido
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
        if self.tarefas is not None:
            # a janela fechou com a tarefa no meio: parada em ordem, com teto (desdobra.tela.tarefas, fechar)
            self.tarefas.fechar(float(limites.valor('tela.parar_max_s')))
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
