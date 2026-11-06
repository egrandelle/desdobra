# -*- coding: utf-8 -*-
"""M7a2: servidor so de leitura da tela, o comando "desdobra tela abrir" e o gancho.

Criterios de pronto cobertos aqui (proposta do M7, secao 4, fatia a2; secao 3, linhas Endereco do servidor, Porta no
Windows, /api/saude, Entrada, Recusa 404, Rota de fonte, CSP da tela; decisoes-v1.md n 159, 167):
  - matriz de 404 antes do roteamento (caminho cru e decodificado, maiuscula, ponto e espaco no fim, ::$DATA);
  - rota de fonte sem cookie: recusada; no-store; so por id ou sha256;
  - entrada reutilizada: recusada; saude sem cookie: 404; Host errado: recusado;
  - so GET: nenhuma rota de escrita no M7a0;
  - o modelo das abas (orientacao e grupo de proporcao, revisao da 163 em 05/11) a partir da derivacao em memoria;
  - o gancho deixa o Claude rodar "desdobra tela abrir" e nega pedir as rotas do servidor e tocar no perfil dsd-;
  - com a janela aberta (Chromium com janela de verdade, pelo comando da CLI que o Claude roda): 0 arquivo de fonte no
    perfil e no cache, pedidos a rota da fonte so da janela (contadores), token ausente da saida, do envelope, do log,
    dos eventos e de todo arquivo fora do perfil; a janela fecha, o processo de fundo sai e o perfil some.

Tudo e sintetico: fontes do fontTools geradas na hora, laudos montados a mao e o PSD sintetico de psd_derivacao.
Os testes do servidor rodam no processo do pytest, sem navegador; so o ultimo abre a janela.
"""
import hashlib
import importlib.util
import io
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

import test_derivacao_apoio as ap
import test_fontes_apoio as fap
from conftest import RAIZ_PLUGIN
from desdobra import limites
from desdobra.derivacao import nucleo as nd
from desdobra.tela import estado as te
from desdobra.tela import servidor as ts

CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' blob:; font-src 'self'; "
       "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
PNG = bytes([137, 80, 78, 71, 13, 10, 26, 10]) + b'png-sintetico'


def _conteudo(fonte=None):
    fonte = fonte if fonte is not None else fap.fonte(ps='Inventada-Tela')
    return {'estado': {'esquema': te.ESQUEMA, 'job_id': ap.JOB, 'somente_leitura': True, 'orientacoes': []},
            'previas': {'mesmo': {'formato': {'id': 'mesmo'}, 'elementos': []}},
            'assets': {'a001': (PNG, 'image/png')},
            'fontes': {'f01': (fonte, 'font/ttf')}}


@pytest.fixture
def srv():
    s = ts.ServidorTela(_conteudo()).iniciar()
    yield s
    s.parar()


def _pedir(s, caminho, metodo='GET', host=None, extra=(), cookie=None, corpo=b''):
    """Pedido HTTP cru por socket (o http.client recusa alguns caminhos da matriz). Devolve (codigo, cabecalhos,
    corpo)."""
    linhas = ['%s %s HTTP/1.1' % (metodo, caminho)]
    if host is not False:
        linhas.append('Host: %s' % (host or '127.0.0.1:%d' % s.porta))
    if cookie:
        linhas.append('Cookie: %s' % cookie)
    linhas += ['%s: %s' % kv for kv in extra]
    if corpo:
        linhas.append('Content-Length: %d' % len(corpo))
    linhas.append('Connection: close')
    bruto = ('\r\n'.join(linhas) + '\r\n\r\n').encode('latin-1') + corpo
    with socket.create_connection(('127.0.0.1', s.porta), timeout=10) as c:
        c.sendall(bruto)
        resposta = b''
        while True:
            parte = c.recv(65536)
            if not parte:
                break
            resposta += parte
    cabeca, _, resto = resposta.partition(b'\r\n\r\n')
    linhas_c = cabeca.decode('latin-1').split('\r\n')
    codigo = int(linhas_c[0].split()[1])
    cab = {}
    for ln in linhas_c[1:]:
        k, _, v = ln.partition(':')
        cab.setdefault(k.strip().lower(), []).append(v.strip())
    return codigo, cab, resto


def _entrar(s):
    codigo, cab, _ = _pedir(s, '/entrar/%s' % s.token)
    assert codigo == 204, codigo
    biscoito = cab['set-cookie'][0]
    return biscoito.split(';', 1)[0]


# ------------------------------------------------------------------ endereco e porta
def test_escuta_so_em_127_numa_porta_exclusiva(srv):
    assert srv._srv.server_address[0] == '127.0.0.1' and srv.porta
    assert srv._srv.allow_reuse_address is False
    if sys.platform == 'win32':
        assert srv._srv.socket.getsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE) == 1
        assert srv._srv.socket.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR) == 0
        # outro socket local, mesmo com SO_REUSEADDR, nao toma a porta
        intruso = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            intruso.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            with pytest.raises(OSError):
                intruso.bind(('127.0.0.1', srv.porta))
        finally:
            intruso.close()


# ------------------------------------------------------------------ entrada de uso unico
def test_entrada_de_uso_unico_vira_cookie_httponly_strict(srv):
    codigo, cab, _ = _pedir(srv, '/entrar/%s' % srv.token)
    assert codigo == 204 and 'location' not in cab
    biscoito = cab['set-cookie'][0]
    for marca in ('HttpOnly', 'SameSite=Strict', 'Path=/'):
        assert marca in biscoito
    assert srv.token not in biscoito
    # a mesma entrada de novo: recusada, e o cookie ja dado continua valendo
    codigo2, cab2, _ = _pedir(srv, '/entrar/%s' % srv.token)
    assert codigo2 == 404 and 'set-cookie' not in cab2
    assert srv.contagem['entrar'] == 1 and srv.contagem['entrada_reusada'] == 1
    assert _pedir(srv, '/api/saude', cookie=biscoito.split(';', 1)[0])[0] == 200


def test_entrada_com_token_errado_nao_gasta_a_entrada(srv):
    assert _pedir(srv, '/entrar/%s' % ('0' * 32))[0] == 404
    assert _pedir(srv, '/entrar/%s' % (srv.token + 'x'))[0] == 404
    assert _pedir(srv, '/entrar/\xe9\xe9')[0] == 404
    assert _pedir(srv, '/entrar/%s' % srv.token)[0] == 204


# ------------------------------------------------------------------ cookie
ROTAS_COM_COOKIE = ['/', '/tela.js', '/tela.css', '/fontes.css', '/controle', '/api/estado', '/api/saude',
                    '/api/previa/mesmo', '/asset/a001', '/fonte/f01']


@pytest.mark.parametrize('rota', ROTAS_COM_COOKIE)
def test_sem_cookie_toda_rota_da_404_e_com_cookie_200(srv, rota):
    assert _pedir(srv, rota)[0] == 404
    assert _pedir(srv, rota, cookie='dsd_tela=%s' % ('0' * 32))[0] == 404
    assert _pedir(srv, rota, cookie='dsd_tela=\xe9')[0] == 404
    assert _pedir(srv, rota, cookie=_entrar(srv))[0] == 200


def test_saude_sem_cookie_404(srv):
    codigo, _c, corpo = _pedir(srv, '/api/saude')
    assert codigo == 404 and b'ok' not in corpo
    assert srv.contagem['saude'] == 0 and srv.contagem['sem_cookie'] == 1


# ------------------------------------------------------------------ fonte
def test_fonte_so_por_id_ou_sha256_sem_cache_e_sem_cors(srv):
    biscoito = _entrar(srv)
    dados = srv.fontes['f01'][0]
    sha = hashlib.sha256(dados).hexdigest()
    for rota in ('/fonte/f01', '/fonte/%s' % sha):
        codigo, cab, corpo = _pedir(srv, rota, cookie=biscoito)
        assert codigo == 200 and corpo == dados
        assert cab['cache-control'] == ['no-store'] and cab['content-type'] == ['font/ttf']
        assert 'access-control-allow-origin' not in cab
        assert cab['cross-origin-resource-policy'] == ['same-origin']
    for rota in ('/fonte/f02', '/fonte/F01', '/fonte/f1', '/fonte/f001', '/fonte/%s' % sha.upper(),
                 '/fonte/%s' % sha[:-1], '/fonte/Inventada-Tela', '/fonte/f01/', '/fonte/../fonte/f01', '/fonte/',
                 '/fonte'):
        assert _pedir(srv, rota, cookie=biscoito)[0] == 404, rota
    assert srv.contagem['fonte'] == 2


def test_fonte_e_ids_fora_do_padrao_sao_recusados_na_montagem():
    with pytest.raises(ValueError):
        ts.ServidorTela(dict(_conteudo(), fontes={'inventada': (b'x', 'font/ttf')}))
    with pytest.raises(ValueError):
        ts.ServidorTela(dict(_conteudo(), assets={'kv.psd': (PNG, 'image/png')}))


# ------------------------------------------------------------------ matriz de 404
MATRIZ = ['/fonte/f01.ttf', '/x.ttf', '/x.TTF', '/x.otf', '/x.OtF', '/x.ttc', '/x.woff', '/x.woff2', '/x.WOFF2',
          '/kv.psd', '/kv.PSB', '/x.ttf.', '/x.ttf..', '/x.ttf%20', '/x.ttf%20.%20', '/x.ttf::$DATA', '/x.ttf::$data',
          '/x%2Ettf', '/x%2etTf', '/x%252Ettf', '/entrada/fontes/a.otf', '/entrada%2Ffontes%2Fa.otf',
          '/api/estado?f=a.ttf', '/api/estado?f=a%2Ewoff2', '/x.ttf/', '/x.psd/y', '/api/previa/kv.psd',
          '/asset/a001.psd', '/x.ttf;a', '/x.ttf%3B', '\\x.ttf', '/x\\a.ttf',
          '/fonte%2Ff01', '/nao-existe', '/api', '/api/', '/api/previa/', '/api/previa/nao', '/asset/', '/asset/a002',
          '//api/estado', '/./api/estado', '/API/ESTADO', '/api/estado/', '/api/estado?x=1', '/fonte/f01%00',
          '/%2e%2e/estado.json', '/../estado.json', '/estado.json', '/entrar', '/entrar/', 'api/estado',
          'http://127.0.0.1/api/estado', '/pagina', '/index.html']
EXTENSOES = [c for c in MATRIZ if re.search(r'(?i)(ttf|otf|ttc|woff|psd|psb)', c)]


@pytest.mark.parametrize('caminho', MATRIZ)
def test_matriz_de_404_com_cookie(srv, caminho):
    biscoito = _entrar(srv)
    antes = dict(srv.contagem)
    codigo, cab, _ = _pedir(srv, caminho, cookie=biscoito)
    assert codigo == 404, caminho
    assert cab['cache-control'] == ['no-store']
    # nenhuma rota respondeu: so as contagens de recusa mudam
    for rota in ts.ROTAS:
        assert srv.contagem[rota] == antes[rota], (caminho, rota)
    if caminho in EXTENSOES:
        assert srv.contagem['extensao_recusada'] == antes['extensao_recusada'] + 1, caminho


@pytest.mark.parametrize('caminho', ['/x.ttf', '/x%2Ettf', '/x.ttf::$DATA', '/x.PSB.', '/fonte/f01.woff2'])
def test_extensao_recusada_antes_do_cookie_e_do_host(srv, caminho):
    assert _pedir(srv, caminho)[0] == 404
    assert srv.contagem['extensao_recusada'] == 1 and srv.contagem['sem_cookie'] == 0


def test_caminho_normalizado_pega_os_disfarces():
    for c in ('/a.TTF', '/a.ttf. . ', '/a.otf::$DATA', '/a%2Ettc', '/a%252Ewoff', '/a.psd/', '\\a.psb'):
        assert ts.extensao_recusada(c), c
    for c in ('/api/estado', '/fonte/f01', '/tela.js', '/attfx', '/a.ttfx'):
        assert not ts.extensao_recusada(c), c


# ------------------------------------------------------------------ host, origem e metodos
@pytest.mark.parametrize('host', ['localhost:%d', '127.0.0.1', '127.0.0.1:1', 'exemplo.test', '[::1]:%d',
                                  '127.0.0.1:%d.', 'exemplo.test:%d'])
def test_host_errado_e_recusado(srv, host):
    biscoito = _entrar(srv)
    h = host % srv.porta if '%d' in host else host
    assert _pedir(srv, '/api/estado', host=h, cookie=biscoito)[0] == 403
    assert _pedir(srv, '/entrar/%s' % srv.token, host=h)[0] == 403


def test_sem_host_e_com_origem_de_fora_e_recusado(srv):
    biscoito = _entrar(srv)
    assert _pedir(srv, '/api/estado', host=False, cookie=biscoito)[0] in (400, 403)
    for origem in ('http://exemplo.test', 'null', 'http://localhost:%d' % srv.porta):
        assert _pedir(srv, '/api/estado', cookie=biscoito, extra=[('Origin', origem)])[0] == 403
    assert _pedir(srv, '/api/estado', cookie=biscoito, extra=[('Origin', srv.origem)])[0] == 200
    assert _pedir(srv, '/api/estado', cookie=biscoito, extra=[('Sec-Fetch-Site', 'cross-site')])[0] == 403


@pytest.mark.parametrize('metodo', ['POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD'])
def test_servidor_so_de_leitura_nao_tem_rota_de_escrita(srv, metodo):
    # sem a pasta do job o servidor e so de leitura: POST tambem da 404 (a escrita: testes/test_tela_escrita.py)
    biscoito = _entrar(srv)
    for rota in ('/api/estado', '/api/aprovar', '/api/briefing', '/api/rascunho', '/fonte/f01'):
        codigo = _pedir(srv, rota, metodo=metodo, cookie=biscoito,
                        extra=[('Content-Type', 'application/json'), ('Origin', srv.origem)],
                        corpo=b'{}' if metodo in ('POST', 'PUT', 'PATCH') else b'')[0]
        assert codigo == 404, (metodo, rota)
    assert srv.contagem['metodo_recusado'] == 5
    assert set(ts.METODOS) == {'GET', 'POST'} and not srv.escreve and srv.csrf is None


# ------------------------------------------------------------------ cabecalhos e conteudo
def test_pagina_com_csp_estrita_e_sem_moldura(srv):
    codigo, cab, corpo = _pedir(srv, '/', cookie=_entrar(srv))
    assert codigo == 200 and cab['content-type'] == ['text/html; charset=utf-8']
    assert cab['content-security-policy'] == [CSP] and cab['x-frame-options'] == ['DENY']
    assert cab['x-content-type-options'] == ['nosniff'] and cab['cache-control'] == ['no-store']
    assert cab['referrer-policy'] == ['no-referrer']
    texto = corpo.decode('utf-8')
    assert '<script src="/tela.js"' in texto and 'onerror' not in texto and '<style' not in texto
    assert srv.token not in texto and srv.sessao not in texto


def test_estado_previa_asset_e_folha_das_fontes(srv):
    biscoito = _entrar(srv)
    codigo, cab, corpo = _pedir(srv, '/api/estado', cookie=biscoito)
    assert codigo == 200 and cab['content-type'] == ['application/json; charset=utf-8']
    assert json.loads(corpo) == srv.estado
    assert json.loads(_pedir(srv, '/api/previa/mesmo', cookie=biscoito)[2]) == {'formato': {'id': 'mesmo'},
                                                                                  'elementos': []}
    codigo, cab, corpo = _pedir(srv, '/asset/a001', cookie=biscoito)
    assert codigo == 200 and corpo == PNG and cab['content-type'] == ['image/png']
    css = _pedir(srv, '/fontes.css', cookie=biscoito)[2].decode('utf-8')
    assert 'url(/fonte/f01)' in css and 'font-display:block' in css and 'local(' not in css
    assert '.ttf' not in css
    codigo, cab, corpo = _pedir(srv, '/controle', cookie=biscoito)
    assert codigo == 200 and srv.marcador_controle in corpo and cab['cache-control'] != ['no-store']


def test_contadores_por_rota(srv):
    biscoito = _entrar(srv)
    for rota in ('/', '/tela.js', '/api/estado', '/api/estado', '/fonte/f01', '/x.ttf', '/nada'):
        _pedir(srv, rota, cookie=biscoito)
    c = srv.contagem
    assert (c['entrar'], c['pagina'], c['estatico'], c['estado'], c['fonte']) == (1, 1, 1, 2, 1)
    assert c['extensao_recusada'] == 1 and c['nao_encontrado'] == 1


def test_o_servidor_nada_imprime(srv, capfd):
    biscoito = _entrar(srv)
    for rota in ('/', '/api/estado', '/x.ttf', '/entrar/%s' % srv.token, '/api/saude'):
        _pedir(srv, rota, cookie=biscoito)
    _pedir(srv, '/api/estado', metodo='POST', cookie=biscoito, corpo=b'x' * 64)
    saida, erro = capfd.readouterr()
    assert saida == '' and erro == ''


# ------------------------------------------------------------------ modelo das abas
def _comps(*medidas):
    return [{'id': 'c%dx%d' % (w, h), 'largura': w, 'altura': h} for w, h in medidas]


def _medidas(grupos):
    return [sorted((c['largura'], c['altura']) for c in g) for g in grupos]


def test_limite_do_agrupamento_tem_fonte_na_revisao_da_163():
    lim = limites.obter('derivacao.grupo_proporcao_dif_max')
    assert lim.valor == 0.3 and lim.situacao == 'a_calibrar' and lim.efeito == 'registra'
    assert lim.fonte['arquivo'] == 'decisoes-v1.md' and '163' in lim.fonte['secao'] and '05/11' in lim.fonte['secao']


def test_agrupamento_junta_as_proporcoes_parecidas_do_duda():
    # 960x192 (5,00) com 1248x250 (4,99); 1280x720 (1,778) com 960x576 (1,667): os exemplos da revisao da 163
    g = te.agrupar_por_proporcao(_comps((960, 192), (1280, 720), (1248, 250), (960, 576)))
    assert _medidas(g) == [[(960, 576), (1280, 720)], [(960, 192), (1248, 250)]]
    # a proporcao e lado longo sobre lado curto: vale igual no vertical
    g = te.agrupar_por_proporcao(_comps((720, 1280), (576, 960)))
    assert _medidas(g) == [[(576, 960), (720, 1280)]]
    # acima do limite, composicao nova
    assert len(te.agrupar_por_proporcao(_comps((800, 400), (480, 300)))) == 2  # 2,0 e 1,6


def test_agrupamento_por_ligacao_completa_quebra_a_cadeia():
    # 2,0, 2,2 e 2,4: cada vizinho cabe no limite, os tres juntos nao (amplitude 0,4)
    g = te.agrupar_por_proporcao(_comps((1000, 500), (1100, 500), (1200, 500)))
    assert _medidas(g) == [[(1000, 500), (1100, 500)], [(1200, 500)]]
    # deterministico: a ordem da entrada nao muda o resultado
    g2 = te.agrupar_por_proporcao(_comps((1200, 500), (1000, 500), (1100, 500)))
    assert _medidas(g2) == _medidas(g)
    # a amplitude do grupo inteiro, nunca a do vizinho: 2,0 2,15 2,3 2,45 vira dois pares
    g = te.agrupar_por_proporcao(_comps((800, 400), (860, 400), (920, 400), (980, 400)))
    assert _medidas(g) == [[(800, 400), (860, 400)], [(920, 400), (980, 400)]]


def test_abas_por_orientacao_e_grupo_de_proporcao():
    formatos = [ap.formato('mesmo', 800, 400), ap.formato('perto', 480, 300), ap.formato('quadrado', 400, 400),
                ap.formato('vertical', 300, 600), ap.formato('faixa', 960, 192), ap.formato('faixa-larga', 1248, 250),
                ap.formato('tv', 1280, 720), ap.formato('tv-menor', 960, 576),
                ap.formato('deitado', 300, 480, rotacao={'graus': 90, 'sentido': 'horario'})]
    b = ap.briefing(formatos=formatos)
    laudo = ap.laudo()
    ctx = nd.contexto(laudo, b)
    r = nd.derivar_em_memoria(ctx)
    abas = te.abas(laudo, b, r['formatos'])
    assert [o['id'] for o in abas] == ['horizontal', 'quadrado', 'vertical']
    horiz = abas[0]
    assert 'familias' not in horiz

    def ids(g):
        return sorted(x['id'] for c in g['composicoes'] for x in c['formatos'])
    grupos = [ids(g) for g in horiz['grupos']]
    # do mais largo para o mais perto do quadrado; as faixas juntam mesmo voltando ao DA sem familia
    # 1,6 (perto e deitado), 1,667 e 1,778 cabem juntos (amplitude 0,178); o 2,0 da escala pura passaria de 0,3
    assert grupos == [['faixa', 'faixa-larga'], ['mesmo'], ['deitado', 'perto', 'tv', 'tv-menor']], grupos
    for g in horiz['grupos']:
        assert g['proporcao'][1] - g['proporcao'][0] <= 0.3
    perto = next(c for g in horiz['grupos'] for c in g['composicoes'] if [c['largura'], c['altura']] == [480, 300])
    # perto (480 x 300) e deitado (300 x 480 girado: composicao 480 x 300) dividem a composicao
    assert sorted(x['id'] for x in perto['formatos']) == ['deitado', 'perto']
    assert next(x for x in perto['formatos'] if x['id'] == 'deitado')['rotacao_graus'] == 90
    mesmo = next(g for g in horiz['grupos'] if ids(g) == ['mesmo'])
    assert mesmo['escala_pura'] is True and mesmo['composicoes'][0]['rotulo_familia'] == 'Mestre do KV'
    assert perto['escala_pura'] is False
    faixa = horiz['grupos'][0]['composicoes']
    assert {c['familia'] for c in faixa} == {te.SEM_FAMILIA}
    # o vertical troca de orientacao: volta ao DA e aparece na aba dele
    vert = abas[2]['grupos']
    assert len(vert) == 1 and vert[0]['composicoes'][0]['formatos'][0]['situacao'] == 'devolvido'
    assert vert[0]['composicoes'][0]['formatos'][0]['motivo'] == 'troca_forte_de_orientacao'
    assert len({g['id'] for o in abas for g in o['grupos']}) == sum(len(o['grupos']) for o in abas)
    json.dumps(abas)


# ------------------------------------------------------------------ gancho
def _gancho():
    spec = importlib.util.spec_from_file_location('gancho_confirmacoes', RAIZ_PLUGIN / 'scripts' / 'gancho_confirmacoes.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.mark.parametrize('ferramenta', ['Bash', 'PowerShell'])
@pytest.mark.parametrize('comando', [
    'desdobra tela abrir --job "C:/jobs/kv"',
    'desdobra --envelope tela abrir --job C:/jobs/kv',
    '"C:/Users/x/.venv/Scripts/desdobra.exe" --envelope tela abrir --job "C:/a b/job"',
    'curl https://exemplo.test/api/estado',
    'python -m pytest testes/test_tela_servidor.py -q',
])
def test_gancho_deixa_o_claude_abrir_a_tela(ferramenta, comando):
    assert _gancho().decidir({'tool_name': ferramenta, 'tool_input': {'command': comando}}) is None, comando


@pytest.mark.parametrize('ferramenta', ['Bash', 'PowerShell'])
@pytest.mark.parametrize('comando', [
    'curl http://127.0.0.1:51234/entrar/abc',
    'curl -s "http://127.0.0.1:51234/api/estado"',
    'curl http://localhost:51234/fonte/f01 -o x',
    'Invoke-WebRequest -Uri http://127.0.0.1:5000/api/saude',
    'iwr http://[::1]:5000/api/previa/x',
    'python -c "import urllib.request as u; u.urlopen(\'http://127.0.0.1:%d/fonte/f01\' % p)"',
    'wget 127.0.0.1:8080/asset/a001',
    'curl http://127.0.0.1:8080/controle',
    'dir %TEMP%\\dsd-tela-abc123',
    'Get-ChildItem $env:TEMP -Filter dsd-tela-*',
    'ls /tmp/dsd-tela-x/Default/Cookies',
    'type C:\\Users\\x\\AppData\\Local\\Temp\\dsd-nasce-x\\dsd-dono.json',
    'python -m desdobra.tela.processo --job C:/jobs/kv',
    'python -c "from desdobra.tela import servidor"',
])
def test_gancho_nega_as_rotas_da_tela_e_o_perfil(ferramenta, comando):
    assert _gancho().decidir({'tool_name': ferramenta, 'tool_input': {'command': comando}}) == 'deny', comando


@pytest.mark.parametrize('caminho', ['C:/Users/x/AppData/Local/Temp/dsd-tela-abc/Default/Preferences',
                                     'C:\\Temp\\dsd-tela-1\\x.json', '/tmp/dsd-nasce-x/dsd-dono.json'])
def test_gancho_nega_escrever_no_perfil_da_tela(caminho):
    for ferramenta in ('Write', 'Edit'):
        assert _gancho().decidir({'tool_name': ferramenta, 'tool_input': {'file_path': caminho}}) == 'deny'


def test_tela_abrir_nao_e_comando_humano():
    from desdobra import humano
    g = _gancho()
    assert 'tela abrir' not in humano.COMANDOS and 'tela abrir' not in g.SUBCOMANDOS_HUMANOS
    assert 'tela' not in {c.split()[0] for c in g.SUBCOMANDOS_HUMANOS}


# ------------------------------------------------------------------ CLI sem janela
def test_tela_abrir_recusa_pasta_que_nao_e_job(tmp_path, capsys):
    from desdobra import cli
    codigo = cli.principal(['--envelope', 'tela', 'abrir', '--job', str(tmp_path)])
    env = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert codigo == 2 and env['comando'] == 'tela abrir' and env['situacao'] == 'erro'


def test_tela_abrir_le_a_recusa_do_processo_de_fundo(tmp_path, capsys, monkeypatch):
    """O processo de fundo avisa a recusa por um codigo fixo; a CLI devolve o envelope sem esperar a janela."""
    from desdobra import cli, tela
    (tmp_path / 'estado.json').write_text('{}', encoding='utf-8')
    monkeypatch.setattr(tela, '_janela_presente', lambda: True)
    monkeypatch.setattr(tela, 'comando_do_filho', lambda pasta: [sys.executable, '-I', '-c',
                                                                 'import sys; print("recusado sem_briefing")'])
    codigo = cli.principal(['--envelope', 'tela', 'abrir', '--job', str(tmp_path)])
    env = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert codigo == 3 and env['situacao'] == 'recusado' and env['contagens'] == {'recusa_sem_briefing': 1}
    assert 'briefing' in env['o_que_fazer']


def test_tela_abrir_sem_resposta_do_fundo_mata_e_avisa(tmp_path, capsys, monkeypatch):
    from desdobra import cli, tela
    (tmp_path / 'estado.json').write_text('{}', encoding='utf-8')
    monkeypatch.setattr(tela, '_janela_presente', lambda: True)
    monkeypatch.setattr(tela, '_espera_s', lambda: 1.0)
    monkeypatch.setattr(tela, 'comando_do_filho', lambda pasta: [sys.executable, '-I', '-c',
                                                                 'import time; time.sleep(60)'])
    inicio = time.monotonic()
    codigo = cli.principal(['--envelope', 'tela', 'abrir', '--job', str(tmp_path)])
    env = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert time.monotonic() - inicio < 30 and codigo == 4 and env['contagens'] == {'recusa_tela_nao_respondeu': 1}


def test_tela_abrir_sem_chromium_com_janela(tmp_path, capsys, monkeypatch):
    from desdobra import cli, tela
    (tmp_path / 'estado.json').write_text('{}', encoding='utf-8')
    monkeypatch.setattr(tela, '_janela_presente', lambda: False)
    codigo = cli.principal(['--envelope', 'tela', 'abrir', '--job', str(tmp_path)])
    env = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert codigo == 3 and env['contagens'] == {'recusa_sem_chromium_com_janela': 1}


# ------------------------------------------------------------------ janela de verdade, pela CLI
ESPIAO = r'''
import json, os, sys, secrets
saida = open(sys.argv[1], 'a', encoding='utf-8')
def gravar(**k):
    saida.write(json.dumps(k) + '\n'); saida.flush()
real_hex = secrets.token_hex
def espiao(n=None):
    v = real_hex(n)
    gravar(segredo=v)
    return v
secrets.token_hex = espiao
from desdobra.chromium import navegador
from desdobra.tela import processo
def ao_abrir(janela, srv):
    try:
        _ao_abrir(janela, srv)
    except BaseException as e:
        import traceback
        gravar(erro=traceback.format_exc()[-3000:])
        raise
def _ao_abrir(janela, srv):
    import time
    pg = janela.pagina()
    # sem wait_for_function: a CSP da tela (sem unsafe-eval) barra a funcao montada de texto
    fim = time.monotonic() + 60
    while pg.evaluate('() => document.documentElement.dataset.pronto || ""') != '1':
        if time.monotonic() > fim:
            raise RuntimeError('a pagina nao ficou pronta: %r' % pg.evaluate('() => document.body.innerText'))
        time.sleep(0.2)
    familias = pg.evaluate('Array.from(document.fonts).map(f => [f.family.replace(/^"|"$/g, ""), f.status])')
    servidos = [d for d, _t in srv.fontes.values()]
    r = navegador.varrer_perfil(janela.perfil, servidos, srv.marcador_controle)
    cdp = janela.ctx.new_cdp_session(pg)
    cdp.send('DOM.enable'); cdp.send('CSS.enable')
    raiz = cdp.send('DOM.getDocument', {'depth': -1})['root']['nodeId']
    no = cdp.send('DOM.querySelector', {'nodeId': raiz, 'selector': '#amostra-f01'})['nodeId']
    faces = cdp.send('CSS.getPlatformFontsForNode', {'nodeId': no})['fonts'] if no else []
    gravar(aberta=True, pid=os.getpid(), varredura=r, contagem=dict(srv.contagem), familias=familias,
           propria=[bool(f.get('isCustomFont')) for f in faces], perfil=str(janela.perfil))
    cdp.send('Browser.close')
codigo = processo.principal(sys.argv[2:], ao_abrir=ao_abrir)
gravar(fim=True, codigo=codigo)
'''


def _pasta_com_janela():
    from desdobra import chromium
    revisao, _v = chromium.revisao_fixada(navegador=chromium.NAVEGADOR_JANELA)
    for c in (chromium.pasta_navegadores(),
              Path.home() / '.claude' / 'plugins' / 'data' / 'desdobra-desdobra' / chromium.PASTA_NAVEGADORES,
              chromium.pasta_padrao_do_playwright()):
        if c is not None and chromium.executavel_fixado(c, revisao, navegador=chromium.NAVEGADOR_JANELA):
            return c
    return None


@pytest.fixture(scope='module')
def job_tela(tmp_path_factory):
    if sys.platform != 'win32':
        pytest.skip('o isolador dos filhos e a amarra do Chromium rodam no Windows')
    from desdobra import contratos
    from desdobra.briefing import modelo as mb
    from desdobra.job import nucleo
    import test_render_apoio as rap
    base = tmp_path_factory.mktemp('tela')
    fontes = base / 'origem-fontes'
    fap.gravar(fontes, 'inventada.ttf', fap.fonte(ps=rap.FONTE))
    job = base / 'job'
    nucleo.criar(job, ap.psd_derivacao(base / 'origem' / 'kv.psd'), 'c', fontes=[fontes])
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    b, _ids = ap.briefing_do_job(laudo, [ap.formato('mesma', 640, 320), ap.formato('perto', 400, 240),
                                         ap.formato('vertical', 160, 320)])
    arq = base / 'fixture.json'
    arq.write_text(json.dumps(b), encoding='utf-8')
    mb.importar_teste(job, arq)
    return job


def _arquivos_de_texto(pasta):
    for p in Path(pasta).rglob('*'):
        if p.is_file():
            try:
                yield p, p.read_bytes()
            except OSError:
                continue


def test_janela_de_verdade_pela_cli_sem_token_fora_da_janela(job_tela, tmp_path, monkeypatch, capfd):
    from desdobra import chromium, cli, tela
    navegadores = _pasta_com_janela()
    if navegadores is None:
        pytest.skip('Chromium com janela fixado ausente nesta maquina')
    monkeypatch.setenv(chromium.VARIAVEL_NAVEGADORES, str(navegadores))
    espiao = tmp_path / 'espiao.jsonl'
    monkeypatch.setattr(tela, 'comando_do_filho', lambda pasta: [sys.executable, '-c', ESPIAO, str(espiao), '--job',
                                                                 str(pasta)])
    temp = Path(tempfile.gettempdir())
    antes_temp = {p.name for p in temp.iterdir()}
    inicio = time.monotonic()
    codigo = cli.principal(['--envelope', 'tela', 'abrir', '--job', str(job_tela)])
    saida, erro = capfd.readouterr()
    assert codigo == 0, saida
    env = json.loads(saida.strip().splitlines()[-1])
    assert env['comando'] == 'tela abrir' and env['situacao'] == 'ok' and env['contagens'] == {'tela_aberta': 1}
    # o fundo sai sozinho quando a janela fecha (o espiao fecha pelo CDP, como o DA fechando a janela)
    fim = time.monotonic() + float(limites.valor('chromium.tempo_max_s'))
    registros = []
    while time.monotonic() < fim:
        registros = [json.loads(x) for x in espiao.read_text(encoding='utf-8').splitlines()] if espiao.exists() else []
        if any(r.get('fim') for r in registros):
            break
        time.sleep(0.5)  # numero-neutro: intervalo do teste
    aberta = next(r for r in registros if r.get('aberta'))
    assert next(r for r in registros if r.get('fim'))['codigo'] == 0
    segredos = [r['segredo'] for r in registros if 'segredo' in r]
    assert len(segredos) >= 2  # token da entrada e sessao do cookie
    # com a janela aberta: nenhuma copia de fonte nos arquivos do perfil e do cache que se leem (o Chromium prende
    # alguns arquivos enquanto roda; a varredura completa, sem ilegivel e com o controle positivo, e a do fecho)
    v = aberta['varredura']
    assert v['copias_encontradas'] == 0 and v['pdfs_encontrados'] == 0 and v['arquivos_varridos'] > 0, v
    assert v['arquivos_varridos'] > v['arquivos_ilegiveis']
    # a fonte foi pedida so pela janela (uma vez por face), desenhou o texto e e a propria
    assert aberta['contagem']['fonte'] == 1 and aberta['contagem']['entrar'] == 1
    assert aberta['contagem']['proibido'] == 0 and aberta['contagem']['sem_cookie'] == 0
    assert ['dsd-f01', 'loaded'] in aberta['familias'] and aberta['propria'] and all(aberta['propria'])
    # o perfil sumiu e nenhuma pasta dsd-tela- ficou
    assert not Path(aberta['perfil']).exists()
    depois_temp = {p.name for p in temp.iterdir()}
    assert not [n for n in depois_temp - antes_temp if n.startswith(('dsd-tela-', 'dsd-nasce-'))]
    # o token e a sessao nunca saem: nem na saida da CLI, nem no envelope, nem no log, nem em arquivo do job
    textos = [saida, erro, json.dumps(env)]
    for s in segredos:
        for t in textos:
            assert s not in t
        for p, dados in _arquivos_de_texto(job_tela):
            assert s.encode('ascii') not in dados, p
        assert b'/entrar/' not in (job_tela / 'log' / 'eventos.jsonl').read_bytes()
    eventos = [json.loads(x) for x in (job_tela / 'log' / 'eventos.jsonl').read_text(encoding='utf-8').splitlines()]
    nomes = [e['evento'] for e in eventos]
    assert 'tela_aberta' in nomes and 'tela_fechada' in nomes
    fechada = [e for e in eventos if e['evento'] == 'tela_fechada'][-1]
    assert fechada['perfil_apagado'] is True
    # no fecho, antes de apagar: o perfil inteiro sem copia de fonte, sem ilegivel, com o controle positivo, e sem o
    # token nem a sessao em arquivo nenhum (a entrada 204 nao entra no historico; o cookie de sessao nao vai ao disco)
    assert fechada['varredura_copias'] == 0 and fechada['varredura_ilegiveis'] == 0, fechada
    assert fechada['varredura_controle'] is True and fechada['varredura_segredos'] == 0, fechada
    assert fechada['varredura_limpa'] is True and fechada['varredura_arquivos'] > 0
    assert fechada['pedidos_fonte'] == 1 and fechada['pedidos_entrar'] == 1 and fechada['pedidos_proibido'] == 0
    assert time.monotonic() - inicio < float(limites.valor('chromium.tempo_max_s')) * 3  # numero-neutro: teto do teste
