# -*- coding: utf-8 -*-
"""M7b, C3: o Chromium fixado aberto enquanto a tela esta aberta, para a medida da quebra de linha ao vivo
(desdobra.chromium.aberto e derivacao.medida_quebras.usar_aberto).

Criterios de pronto cobertos aqui:
  - a medida no Chromium aberto e a mesma do caminho frio (larguras, tintas e numero de linhas), nos dois jobs
    sinteticos: o de duas linhas (juntar e manter) e o do texto de apoio com espaco (quebra inserida);
  - o Chromium aberto so abre na primeira medida sem cache e mede as seguintes sem abrir de novo; cada medida roda num
    contexto sem perfil (o cache dele fica na memoria);
  - higiene da fonte: o perfil do Chromium aberto e um dsd-tela- com dono (a varredura de orfas o acha depois de uma
    queda), grava o controle positivo e, no fecho, a varredura do perfil inteiro nao acha copia de fonte; o perfil some;
  - o Chromium que caiu: a medida daquele pedido sai pelo caminho frio e a proxima abre o Chromium de novo;
  - o Chromium que travou: o pedido espera no maximo o teto (chromium.aberto_espera_max_s) e sai pelo caminho frio;
    enquanto o travado nao volta, as medidas vao pelo caminho frio, sem abrir outro;
  - sem a amarra do Job Object o aberto nao abre, e a medida sai pelo caminho frio;
  - fora da tela nada fica aberto: so o processo da tela liga o aberto; a CLI e a derivacao fora da tela medem pelo
    caminho frio como antes;
  - no processo da tela (filho, com a janela de verdade): o aberto e o mesmo para a previa e para a derivacao, o
    Chromium dele fica amarrado ao Job Object, morre junto com o Python morto, e o fecho da tela apaga o perfil e
    registra a varredura em tela_fechada.
Tudo sintetico: os PSDs de test_tela_palco e de test_derivacao_apoio, com a fonte de autoteste do motor e a fonte
inventada dos testes."""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

import test_derivacao_apoio as ap
import test_fontes_apoio as fap
import test_medida_quebras_cache as tmc
import test_render_apoio as rap
import test_render_texto_editado as rte
from desdobra import contratos, limites
from desdobra.briefing import modelo as mb
from desdobra.chromium import aberto as ab
from desdobra.chromium import navegador, processos, servidor
from desdobra.derivacao import medida_quebras as mm
from desdobra.derivacao import quebras as mq
from desdobra.job import nucleo

modelo = rte.modelo
job = rte.job
espiao = tmc.espiao

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')

ESPERA_MORTE_S = 30  # numero-neutro: teto do teste para o Chromium morrer depois do Python


@pytest.fixture
def temp_curta():
    """Pasta curta na pasta temporaria do sistema para o perfil do aberto (a do pytest passa de 220 caracteres)."""
    pasta = Path(tempfile.mkdtemp(prefix='dsdt-'))
    yield pasta
    shutil.rmtree(pasta, ignore_errors=True)


@pytest.fixture
def aberto(temp_curta):
    """O Chromium aberto da tela, ligado na medida das quebras, sem a amarra do Job Object (o pytest nao fica
    amarrado: o teste do processo da tela, com a amarra de verdade, roda num filho)."""
    a = ab.NavegadorAberto(amarrar=lambda: True, pasta_temp=temp_curta)
    mm.usar_aberto(a)
    yield a
    mm.usar_aberto(None)
    a.fechar()


@pytest.fixture(scope='module')
def job_apoio(tmp_path_factory):
    """O job do texto de apoio 'AB ab' (o espaco na posicao 2) e do texto de duas cores, com a fonte inventada."""
    base = tmp_path_factory.mktemp('aberto')
    fontes = base / 'origem-fontes'
    fap.gravar(fontes, 'inventada.ttf', fap.fonte(ps=rap.FONTE))
    pasta = base / 'job'
    nucleo.criar(pasta, ap.psd_derivacao(base / 'origem' / 'kv.psd'), 'c', fontes=[fontes])
    r = nucleo.proxima(pasta, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    return pasta


def _ids(pasta):
    laudo = contratos.ler(pasta / mb.ARQUIVO_LAUDO, 'laudo/1')
    return {c['nome']: c['identidade']['layer_id'] for c in laudo['camadas']}


def _pedido(layer_id, manter=(), inseridas=(), n=0):
    return {'layer_id': layer_id, 'familia': 'g%d' % n, 'formatos': ['f%d' % n], 'quebras': ap.decisao(list(manter)),
            'inseridas': list(inseridas), 'origem': 'da', 'aprovada': True}


def _medir(pasta, briefing):
    laudo = contratos.ler(pasta / mb.ARQUIVO_LAUDO, 'laudo/1')
    return mm.medir(pasta, laudo, briefing, nucleo.ler_estado(pasta))


def _frio(pasta, briefing):
    """A medida pelo caminho frio, sem cache e sem o aberto ligado."""
    antes = mm._aberto
    mm.usar_aberto(None)
    mm.limpar_cache()
    try:
        return _medir(pasta, briefing)
    finally:
        mm.limpar_cache()
        mm.usar_aberto(antes)


def _briefings(job_, modelo_, job_apoio_):
    """(pasta, briefing) dos dois jobs, com as quebras que cada um aceita."""
    lid = modelo_['layer_id']
    duas = {'quebras_por_familia': [_pedido(lid, (), (), 0), _pedido(lid, (0,), (), 1)]}
    ids = _ids(job_apoio_)
    apoio = {'quebras_por_familia': [_pedido(ids['texto-apoio'], (), (2,), 0),  # numero-neutro: o espaco de 'AB ab'
                                     _pedido(ids['texto-cores'], (), (), 1)]}
    return [(job_, duas), (job_apoio_, apoio)]


def _chrome_novos(antes):
    return sorted(p for p, nome in processos.descendentes(os.getpid())
                  if nome.lower().startswith('chrome') and p not in antes)


def _chrome_agora():
    return {p for p, nome in processos.descendentes(os.getpid()) if nome.lower().startswith('chrome')}


def _morreram(pids, teto_s):
    fim = time.monotonic() + teto_s
    while time.monotonic() < fim:
        if all(processos.identidade(p) is None for p in pids):
            return True
        time.sleep(0.2)  # numero-neutro: intervalo do teste
    return False


# ------------------------------------------------------------------ a mesma medida do caminho frio
def test_aberto_mede_igual_ao_caminho_frio(job, modelo, job_apoio, aberto, espiao):
    for pasta, b in _briefings(job, modelo, job_apoio):
        frio = _frio(pasta, b)
        assert frio and all('largura_texto' in v and 'tinta' in v for v in frio.values()), frio
        espiao['chromium'] = 0
        mm.limpar_cache()
        quente = _medir(pasta, b)
        # o caminho frio nao abriu: a medida veio do aberto
        assert espiao['chromium'] == 0
        assert quente == frio
    # as linhas de cada pedido: juntar (1), manter (2), inserir no espaco (2) e o texto de uma linha (1)
    ids = _ids(job_apoio)
    assert [v['linhas'] for v in _frio(job, _briefings(job, modelo, job_apoio)[0][1]).values()] == [1, 2]
    apoio = _frio(job_apoio, _briefings(job, modelo, job_apoio)[1][1])
    assert apoio[mq.chave(ids['texto-apoio'], (), (2,))]['linhas'] == 2  # numero-neutro: 'AB' / 'ab'
    assert apoio[mq.chave(ids['texto-cores'], (), ())]['linhas'] == 1
    rel = aberto.relatorio()
    assert rel['aberturas'] == 1 and rel['medidas'] == 2 and rel['quedas'] == 0, rel


def test_aberto_so_abre_na_primeira_medida_e_nao_abre_de_novo(job, modelo, aberto, espiao, temp_curta):
    assert aberto.relatorio()['aberturas'] == 0 and aberto.perfil is None
    assert list(temp_curta.iterdir()) == []
    b = {'quebras_por_familia': [_pedido(modelo['layer_id'])]}
    for _ in range(3):  # numero-neutro: tres medidas sem cache
        mm.limpar_cache()
        assert 'largura_texto' in _medir(job, b)[mq.chave(modelo['layer_id'], (), ())]
    rel = aberto.relatorio()
    assert rel['aberturas'] == 1 and rel['medidas'] == 3 and espiao['chromium'] == 0, rel
    # com cache, nem o aberto mede
    assert _medir(job, b) and aberto.relatorio()['medidas'] == 3


def test_servidor_da_medida_no_aberto_para_sem_esperar_meio_segundo(job, modelo, aberto, monkeypatch):
    """O servidor da pagina de medida para sem a espera de meio segundo do serve_forever quando o aberto esta ligado
    (essa espera era quase toda a remedicao no aberto). Sem o aberto, o servidor e o de antes."""
    real = servidor.ServidorFontes
    vistos = []

    def espiar(*a, **k):
        if a[0] != ab.PAGINA_CONTROLE:  # o controle positivo da abertura do aberto nao e a pagina de medida
            vistos.append(k.get('intervalo_s'))
        return real(*a, **k)
    monkeypatch.setattr(mm.servidor, 'ServidorFontes', espiar)
    b = {'quebras_por_familia': [_pedido(modelo['layer_id'])]}
    mm.limpar_cache()
    assert 'largura_texto' in _medir(job, b)[mq.chave(modelo['layer_id'], (), ())]
    mm.usar_aberto(None)
    mm.limpar_cache()
    try:
        assert 'largura_texto' in _medir(job, b)[mq.chave(modelo['layer_id'], (), ())]
    finally:
        mm.usar_aberto(aberto)
    assert vistos == [mm.INTERVALO_SERVIDOR_ABERTO_S, None], vistos
    s = real('<p>x</p>', {}, intervalo_s=mm.INTERVALO_SERVIDOR_ABERTO_S).iniciar()
    t = time.perf_counter()
    s.parar()
    assert time.perf_counter() - t < 0.25  # numero-neutro: teto do teste (a espera de antes era 0,5 s)


# ------------------------------------------------------------------ higiene da fonte
def test_perfil_do_aberto_tem_dono_nao_guarda_fonte_e_some_no_fecho(job, modelo, job_apoio, temp_curta, espiao):
    a = ab.NavegadorAberto(amarrar=lambda: True, pasta_temp=temp_curta)
    mm.usar_aberto(a)
    try:
        for pasta, b in _briefings(job, modelo, job_apoio):
            mm.limpar_cache()
            assert all('largura_texto' in v for v in _medir(pasta, b).values())
        perfil = a.perfil
        assert perfil is not None and perfil.parent == temp_curta
        assert perfil.name.startswith(navegador.PREFIXO_PERFIL_TELA)
        # o perfil tem dono vivo: a varredura de orfas da tela aberta o deixa
        assert navegador.dono_do_perfil(perfil)['pid'] == os.getpid() and not navegador.perfil_orfao(perfil)
        assert navegador.varrer_orfaos(temp_curta)['mantidas'] == 1
    finally:
        mm.usar_aberto(None)
        rel = a.fechar()
    assert espiao['chromium'] == 0
    assert not perfil.exists() and list(temp_curta.iterdir()) == []
    # a varredura do perfil inteiro no fecho, com o Chromium fechado: o controle positivo prova que o perfil grava
    # cache, e nenhuma fonte servida as duas medidas ficou nele
    assert rel['varreduras'] == 1 and rel['varreduras_limpas'] == 1, rel
    assert rel['copias'] == 0 and rel['ilegiveis'] == 0 and rel['controle'] is True, rel
    assert rel['fontes_servidas'] == 2 and rel['perfis_apagados'] == 1 and rel['perfis_que_ficaram'] == 0, rel
    assert rel['limpo'] is True
    # depois do fecho, a medida sai pelo caminho frio sem abrir nada
    with pytest.raises(navegador.ErroNavegador):
        a.conferir('http://127.0.0.1:1/entrar/x', [], [])


def test_varredura_do_aberto_acha_a_fonte_que_ficasse_no_perfil(temp_curta):
    """O metodo da varredura vale no perfil do aberto: a fonte servida com cache liberado no contexto persistente
    (o que as medidas nunca usam) aparece na varredura do fecho, e o fecho diz que o perfil nao estava limpo."""
    fonte = fap.fonte(ps=rap.FONTE)
    a = ab.NavegadorAberto(amarrar=lambda: True, pasta_temp=temp_curta)
    pagina = ('<!doctype html><html><head><style>@font-face{font-family:"x";src:url(/fonte/f01)}'
              'p{font-family:"x"}</style></head><body><p>AB</p></body></html>')
    with servidor.ServidorFontes(pagina, {'f01': (fonte, 'font/ttf')}, cache_control='max-age=3600') as srv:
        a.conferir(srv.url_entrada, ['x'], [], servidos=[fonte])


        def no_persistente(fio):  # so este teste usa o contexto persistente, no fio do aberto
            pg = fio.ctx.pages[0]
            pg.goto(srv.url_entrada, wait_until='load')
            pg.evaluate(navegador.JS_CARREGAR, ['x'])
        a._no_fio(no_persistente)
    rel = a.fechar()
    assert rel['copias'] >= 1 and rel['limpo'] is False, rel
    assert rel['perfis_apagados'] == 1 and list(temp_curta.iterdir()) == []


# ------------------------------------------------------------------ queda, trava e recusa
def test_chromium_do_aberto_que_caiu_volta_na_proxima_medida(job, modelo, aberto, espiao):
    lid = modelo['layer_id']
    b = {'quebras_por_familia': [_pedido(lid)]}
    frio = _frio(job, b)
    espiao['chromium'] = 0
    antes = _chrome_agora()
    mm.limpar_cache()
    assert _medir(job, b) == frio
    chrome = _chrome_novos(antes)
    assert chrome and aberto.relatorio()['aberturas'] == 1
    for p in chrome:  # o Chromium do aberto cai (processos que este teste abriu pelo aberto)
        try:
            os.kill(p, signal.SIGTERM)
        except OSError:
            pass
    assert _morreram(chrome, ESPERA_MORTE_S)
    # o pedido seguinte sai certo: pelo caminho frio, ou pelo aberto que ja abriu de novo
    mm.limpar_cache()
    assert _medir(job, b) == frio
    mm.limpar_cache()
    assert _medir(job, b) == frio
    rel = aberto.relatorio()
    assert rel['aberturas'] == 2 and rel['quedas'] == 1, rel  # numero-neutro: abriu de novo depois da queda
    # a ultima medida veio do aberto de novo
    frios = espiao['chromium']
    mm.limpar_cache()
    assert _medir(job, b) == frio and espiao['chromium'] == frios
    # o perfil do Chromium que caiu (o fio dele fecha depois de responder)
    assert _esperar(lambda: aberto.relatorio()['perfis_apagados'] == 1, ESPERA_MORTE_S), aberto.relatorio()


def test_aberto_travado_sai_pelo_caminho_frio_no_teto(job, modelo, temp_curta, espiao, monkeypatch):
    lid = modelo['layer_id']
    b = {'quebras_por_familia': [_pedido(lid)]}
    frio = _frio(job, b)
    espiao['chromium'] = 0
    real = navegador.medir_na_pagina
    solta = threading.Event()
    preso = {'n': 0, 'ativo': False}

    def travar(*a, **k):
        if threading.current_thread().name.startswith(ab.NOME_FIO) and preso['ativo'] and not preso['n']:
            preso['n'] += 1
            solta.wait(60)  # numero-neutro: teto do teste
        return real(*a, **k)
    monkeypatch.setattr(navegador, 'medir_na_pagina', travar)
    a = ab.NavegadorAberto(amarrar=lambda: True, pasta_temp=temp_curta)
    mm.usar_aberto(a)
    try:
        # o aberto ja aberto (a abertura conta no teto; aqui so a medida trava)
        mm.limpar_cache()
        assert _medir(job, b) == frio and a.relatorio()['aberturas'] == 1 and espiao['chromium'] == 0
        espera = a.espera_s
        a.espera_s = 2.0  # numero-neutro: teto do teste
        preso['ativo'] = True
        mm.limpar_cache()
        t = time.monotonic()
        assert _medir(job, b) == frio
        # o teto do aberto, mais o caminho frio (que abre o Chromium de novo)
        assert time.monotonic() - t < 2.0 + float(limites.valor('chromium.tempo_max_s'))  # numero-neutro: idem
        assert preso['n'] == 1 and espiao['chromium'] == 1
        rel = a.relatorio()
        assert rel['travadas'] == 1 and rel['presos'] == 1, rel
        # com o travado ainda preso, a medida vai pelo caminho frio, sem abrir outro aberto
        mm.limpar_cache()
        assert _medir(job, b) == frio and espiao['chromium'] == 2 and a.relatorio()['aberturas'] == 1
        solta.set()
        # o travado volta, fecha o Chromium dele e apaga o perfil; a proxima medida abre um aberto novo
        fim = time.monotonic() + ESPERA_MORTE_S
        while a.relatorio()['presos'] and time.monotonic() < fim:
            time.sleep(0.1)  # numero-neutro: intervalo do teste
        assert a.relatorio()['presos'] == 0
        a.espera_s = espera
        mm.limpar_cache()
        assert _medir(job, b) == frio and espiao['chromium'] == 2 and a.relatorio()['aberturas'] == 2
    finally:
        solta.set()
        mm.usar_aberto(None)
        rel = a.fechar()
    assert rel['perfis_apagados'] == 2 and rel['perfis_que_ficaram'] == 0 and rel['copias'] == 0, rel
    assert list(temp_curta.iterdir()) == []


def test_aberto_sem_amarra_nao_abre_e_a_medida_sai_fria(job, modelo, temp_curta, espiao):
    a = ab.NavegadorAberto(amarrar=lambda: False, pasta_temp=temp_curta)
    mm.usar_aberto(a)
    try:
        b = {'quebras_por_familia': [_pedido(modelo['layer_id'])]}
        mm.limpar_cache()
        assert 'largura_texto' in _medir(job, b)[mq.chave(modelo['layer_id'], (), ())]
        mm.limpar_cache()
        assert 'largura_texto' in _medir(job, b)[mq.chave(modelo['layer_id'], (), ())]
    finally:
        mm.usar_aberto(None)
        rel = a.fechar()
    assert espiao['chromium'] == 2 and rel['aberturas'] == 0 and rel['recusas'] == 1, rel
    assert list(temp_curta.iterdir()) == []


def test_fora_da_tela_nada_fica_aberto(job, modelo, espiao):
    """Sem a tela, a medida e a de antes: o caminho frio, que abre e fecha o Chromium a cada medida sem cache."""
    from conftest import PASTA_PACOTE
    assert mm._aberto is None
    b = {'quebras_por_familia': [_pedido(modelo['layer_id'])]}
    assert 'largura_texto' in _medir(job, b)[mq.chave(modelo['layer_id'], (), ())] and espiao['chromium'] == 1
    # so o processo da tela liga o aberto (as chamadas de usar_aberto e os NavegadorAberto criados no pacote)
    import ast

    def chama(p, nome):
        arvore = ast.parse(p.read_text(encoding='utf-8'))
        return any(isinstance(n, ast.Call) and getattr(n.func, 'attr', getattr(n.func, 'id', None)) == nome
                   for n in ast.walk(arvore))
    for nome in ('usar_aberto', 'NavegadorAberto'):
        quem = sorted(str(p.relative_to(PASTA_PACOTE)).replace(os.sep, '/') for p in PASTA_PACOTE.rglob('*.py')
                      if chama(p, nome))
        assert quem == ['tela/processo.py'], (nome, quem)


# ------------------------------------------------------------------ o processo da tela de verdade (filho)
FILHO_TELA = r'''
import json, os, sys, time
saida = open(sys.argv[1], 'a', encoding='utf-8')
def gravar(**k):
    saida.write(json.dumps(k) + '\n'); saida.flush()
from desdobra import contratos
from desdobra.briefing import modelo as mb
from desdobra.chromium import processos
from desdobra.derivacao import medida_quebras as mm
from desdobra.job import nucleo
from desdobra.tela import processo
def chrome():
    return {p for p, n in processos.descendentes(os.getpid()) if n.lower().startswith('chrome')}
def ao_abrir(janela, srv):
    try:
        job = srv.pasta or __import__('pathlib').Path(sys.argv[3]).resolve()
        antes = chrome()
        aberto = mm._aberto
        conteudo = srv._conteudo
        gid = next(g for g, f in conteudo['familias'].items() if 'mesma' in f['formatos'])
        base = srv.editar({'familia': gid, 'versao': None, 'edicoes': []})
        el = next(e for e in base['membros'][0]['palco']['elementos'] if e['funcao'] == 'titulo')
        lid = el['layer_ids'][0] if el.get('layer_ids') else None
        laudo = contratos.ler(job / mb.ARQUIVO_LAUDO, 'laudo/1')
        lid = lid or next(c['identidade']['layer_id'] for c in laudo['camadas'] if c['nome'] == 'duas-linhas')
        q = {'elemento': el['id'], 'layer_id': lid, 'manter': [], 'inseridas': [], 'origem': 'da', 'aprovada': True}
        mm.limpar_cache()
        previa = srv.editar({'familia': gid, 'versao': None, 'edicoes': [], 'quebras': [q]})
        depois_previa = aberto.relatorio()
        perfil = str(aberto.perfil)
        novos = sorted(chrome() - antes)
        # a derivacao no mesmo processo (o "Salvar e seguir" roda nele) mede no mesmo aberto
        mm.limpar_cache()
        b = {'quebras_por_familia': [{'layer_id': lid, 'familia': gid, 'formatos': ['mesma'],
                                      'quebras': {'valor': [], 'situacao': 'confirmado',
                                                  'origem': {'tipo': 'fixture_de_teste', 'ref': 'teste'}},
                                      'inseridas': [], 'origem': 'da',
                                      'aprovada': True}]}
        medida = mm.medir(job, laudo, b, nucleo.ler_estado(job))
        gravar(aberta=True, previa=previa is not None, depois_previa=depois_previa, relatorio=aberto.relatorio(),
               perfil=perfil, existe=os.path.isdir(perfil), chrome=novos, no_job=[processos.amarrado(p) for p in novos],
               medida=sorted(medida.values(), key=json.dumps)[0] if medida else None, pid=os.getpid())
        if sys.argv[2] == 'matar':
            time.sleep(3600)  # o teste mata este processo
    except BaseException:
        import traceback
        gravar(erro=traceback.format_exc()[-3000:])
    cdp = janela.ctx.new_cdp_session(janela.pagina())
    cdp.send('Browser.close')
codigo = processo.principal(sys.argv[4:], ao_abrir=ao_abrir)
gravar(fim=True, codigo=codigo)
'''


def _filho_tela(job_, registro, modo):
    import test_tela_servidor as tts
    from desdobra import chromium
    navegadores = tts._pasta_com_janela()
    if navegadores is None:
        pytest.skip('Chromium com janela fixado ausente nesta maquina')
    env = dict(os.environ, **{chromium.VARIAVEL_NAVEGADORES: str(navegadores)})
    return subprocess.Popen([sys.executable, '-c', FILHO_TELA, str(registro), modo, str(job_), '--job', str(job_)],
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)


def _registros(registro):
    return [json.loads(x) for x in registro.read_text(encoding='utf-8').splitlines()] if registro.exists() else []


def test_processo_da_tela_mede_no_aberto_amarrado_e_apaga_o_perfil_no_fecho(job, tmp_path):
    registro = tmp_path / 'tela.jsonl'
    proc = _filho_tela(job, registro, 'fechar')
    try:
        _saida, erro = proc.communicate(timeout=float(limites.valor('chromium.tempo_max_s')) * 3)  # numero-neutro: teto
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    linhas = _registros(registro)
    assert not [x for x in linhas if 'erro' in x], linhas
    aberta = next(x for x in linhas if x.get('aberta'))
    assert next(x for x in linhas if x.get('fim'))['codigo'] == 0, erro.decode('utf-8', 'replace')[-2000:]
    # a previa abriu o aberto, e a derivacao do mesmo processo mediu nele sem abrir de novo
    assert aberta['previa'] and aberta['depois_previa']['aberturas'] == 1 and aberta['depois_previa']['medidas'] == 1
    assert aberta['relatorio']['aberturas'] == 1 and aberta['relatorio']['medidas'] == 2, aberta['relatorio']
    assert aberta['medida'] and 'largura_texto' in aberta['medida']
    # o Chromium do aberto nasceu dentro do Job Object da tela
    assert aberta['chrome'] and all(aberta['no_job']), aberta
    assert aberta['existe'] and Path(aberta['perfil']).name.startswith(navegador.PREFIXO_PERFIL_TELA)
    assert not Path(aberta['perfil']).exists()
    assert _morreram(aberta['chrome'], ESPERA_MORTE_S)
    eventos = [json.loads(x) for x in (job / 'log' / 'eventos.jsonl').read_text(encoding='utf-8').splitlines()]
    fechada = [e for e in eventos if e['evento'] == 'tela_fechada'][-1]
    assert fechada['aberto_aberturas'] == 1 and fechada['aberto_medidas'] == 2, fechada
    assert fechada['aberto_copias'] == 0 and fechada['aberto_ilegiveis'] == 0, fechada
    assert fechada['aberto_controle'] is True and fechada['aberto_limpo'] is True, fechada
    assert fechada['aberto_perfis_apagados'] == 1 and fechada['aberto_perfis_que_ficaram'] == 0, fechada


def test_chromium_do_aberto_morre_com_o_python_e_a_varredura_apaga_a_orfa(job, tmp_path):
    registro = tmp_path / 'tela.jsonl'
    proc = _filho_tela(job, registro, 'matar')
    try:
        fim = time.monotonic() + float(limites.valor('chromium.tempo_max_s')) * 2  # numero-neutro: teto do teste
        aberta = None
        while aberta is None and time.monotonic() < fim and proc.poll() is None:
            aberta = next((x for x in _registros(registro) if x.get('aberta') or x.get('erro')), None)
            time.sleep(0.2)  # numero-neutro: intervalo do teste
        assert aberta and 'erro' not in aberta, (aberta, proc.poll())
        assert aberta['chrome'] and all(aberta['no_job'])
        perfil = Path(aberta['perfil'])
        assert perfil.is_dir() and not navegador.perfil_orfao(perfil)
        # mata o Python da tela de verdade (TerminateProcess: o Python nao fecha nada)
        os.kill(aberta['pid'], signal.SIGTERM)
        proc.wait(timeout=ESPERA_MORTE_S)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    assert _morreram(aberta['chrome'], ESPERA_MORTE_S), 'o Chromium do aberto sobreviveu ao Python morto'
    assert navegador.perfil_orfao(perfil)
    r = navegador.varrer_orfaos(perfil.parent)
    assert r['nao_removidas'] == 0 and r['removidas'] >= 1 and not perfil.exists()


# ------------------------------------------------------------------ revisao 1 do aberto
def _esperar(condicao, teto_s):
    fim = time.monotonic() + teto_s
    while time.monotonic() < fim:
        if condicao():
            return True
        time.sleep(0.1)  # numero-neutro: intervalo do teste
    return condicao()


def _driver_do_aberto(antes):
    """O driver do Playwright (node) que o aberto abriu: o novo filho deste processo com o Chromium embaixo dele."""
    return [p for p, nome in processos.descendentes(os.getpid())
            if nome.lower().startswith('node') and p not in antes
            and any(n.lower().startswith('chrome') for _q, n in processos.descendentes(p))]


def test_driver_do_aberto_que_morreu_volta_na_proxima_medida_sem_travar(job, modelo, temp_curta, espiao):
    """O driver do Playwright do aberto morre com a tela aberta: a medida seguinte nao espera o teto, a outra mede no
    aberto aberto de novo, o perfil do driver morto e varrido e apagado, e o fecho da tela nao fica preso."""
    lid = modelo['layer_id']
    b = {'quebras_por_familia': [_pedido(lid)]}
    frio = _frio(job, b)
    espiao['chromium'] = 0
    a = ab.NavegadorAberto(amarrar=lambda: True, pasta_temp=temp_curta, espera_s=5)  # numero-neutro: teto do teste
    mm.usar_aberto(a)
    antes = {p for p, _n in processos.descendentes(os.getpid())}
    chrome_antes = _chrome_agora()
    try:
        mm.limpar_cache()
        assert _medir(job, b) == frio and a.relatorio()['aberturas'] == 1
        driver = _driver_do_aberto(antes)
        chrome = _chrome_novos(chrome_antes)
        assert len(driver) == 1 and chrome, (driver, chrome)
        primeiro = a.perfil
        os.kill(driver[0], signal.SIGTERM)  # o driver que este teste abriu pelo aberto
        assert _morreram(driver, ESPERA_MORTE_S)
        mm.limpar_cache()
        t = time.monotonic()
        assert _medir(job, b) == frio
        assert time.monotonic() - t < a.espera_s, time.monotonic() - t
        frios = espiao['chromium']
        mm.limpar_cache()
        assert _medir(job, b) == frio and espiao['chromium'] == frios
        rel = a.relatorio()
        assert rel['aberturas'] == 2 and rel['travadas'] == 0 and rel['presos'] == 0 and rel['quedas'] == 1, rel
        assert _esperar(lambda: not primeiro.exists(), ESPERA_MORTE_S)
        assert _morreram(chrome, ESPERA_MORTE_S)
    finally:
        mm.usar_aberto(None)
        t = time.monotonic()
        rel = a.fechar()
    assert time.monotonic() - t < float(limites.valor('tela.parar_max_s'))
    assert rel['presos'] == 0 and rel['perfis_apagados'] == 2 and rel['perfis_que_ficaram'] == 0, rel
    assert rel['varreduras'] == 2 and rel['copias'] == 0 and rel['limpo'] is True, rel
    assert list(temp_curta.iterdir()) == []


def test_fechar_duas_vezes_espera_o_preso_uma_vez_so(monkeypatch):
    """O processo da tela fecha o aberto no fecho em ordem e de novo no fim: o segundo fecho nao espera o preso de
    novo."""
    real = limites.valor
    monkeypatch.setattr(ab.limites, 'valor', lambda chave: 1.0 if chave == 'tela.parar_max_s' else real(chave))
    a = ab.NavegadorAberto(amarrar=lambda: True, espera_s=0.3)  # numero-neutro: teto do teste
    solta = threading.Event()
    try:
        with pytest.raises(navegador.ErroNavegador):
            a._no_fio(lambda fio: solta.wait(60))  # numero-neutro: teto do teste
        t = time.monotonic()
        assert a.fechar()['presos'] == 1
        assert time.monotonic() - t >= 0.9  # numero-neutro: o primeiro fecho espera o teto (1 s)
        t = time.monotonic()
        rel = a.fechar()
        assert time.monotonic() - t < 0.2, time.monotonic() - t  # numero-neutro: teto do teste
        assert rel['presos'] == 1 and rel['limpo'] is False, rel
    finally:
        solta.set()


@pytest.fixture
def tela_no_pytest(temp_curta, monkeypatch):
    """O processo da tela no proprio pytest: os perfis (o da janela e o do aberto) na pasta curta do teste, sem a
    varredura de orfas da pasta temporaria do sistema e sem a amarra do Job Object."""
    real = navegador.perfil_tela
    monkeypatch.setattr(navegador, 'perfil_tela', lambda pasta_temp=None: real(temp_curta))
    monkeypatch.setattr(navegador, 'varrer_orfaos',
                        lambda pasta_temp=None: {'removidas': 0, 'nao_removidas': 0, 'mantidas': 0})
    monkeypatch.setattr(processos, 'amarrar_ao_processo', lambda: True)
    return temp_curta


def _eventos(pasta):
    return [json.loads(x) for x in (pasta / 'log' / 'eventos.jsonl').read_text(encoding='utf-8').splitlines()]


def test_tela_que_termina_em_erro_registra_o_relatorio_do_aberto(job, tela_no_pytest, monkeypatch):
    """A tela que termina em erro depois de medir no aberto: o tela_recusou leva o relatorio do aberto (aqui sujo, com
    a fonte posta no perfil persistente), como o tela_fechada."""
    from desdobra.resultado import Codigo
    from desdobra.tela import processo
    fonte = fap.fonte(ps=rap.FONTE)
    pagina = ('<!doctype html><html><head><style>@font-face{font-family:"x";src:url(/fonte/f01)}'
              'p{font-family:"x"}</style></head><body><p>AB</p></body></html>')

    class JanelaQueFalha:
        def __init__(self, perfil, antes_de_apagar=None):
            self.perfil, self.perfil_apagado, self.versao = perfil, None, None

        def __enter__(self):
            a = mm._aberto
            with servidor.ServidorFontes(pagina, {'f01': (fonte, 'font/ttf')}, cache_control='max-age=3600') as srv:
                a.conferir(srv.url_entrada, ['x'], [], servidos=[fonte])

                def no_persistente(fio):
                    pg = fio.ctx.pages[0]
                    pg.goto(srv.url_entrada, wait_until='load')
                    pg.evaluate(navegador.JS_CARREGAR, ['x'])
                a._no_fio(no_persistente)
            raise RuntimeError('a tela caiu depois de medir')

        def __exit__(self, *exc):
            return False
    monkeypatch.setattr(navegador, 'Janela', JanelaQueFalha)
    avisos = []
    assert processo.executar(job, avisar=avisos.append) == int(Codigo.ERRO_INTERNO)
    assert avisos == ['recusado erro_interno']
    ev = _eventos(job)[-1]
    assert ev['evento'] == 'tela_recusou' and ev['motivo'] == 'erro_interno', ev
    assert ev['aberto_aberturas'] == 1 and ev['aberto_copias'] >= 1 and ev['aberto_limpo'] is False, ev
    assert ev['aberto_perfis_apagados'] == 1 and ev['aberto_perfis_que_ficaram'] == 0, ev
    assert list(tela_no_pytest.iterdir()) == []


def test_montagem_da_tela_nao_abre_o_aberto(job, modelo, tela_no_pytest, espiao, monkeypatch):
    """A montagem do job com a quebra gravada mede antes do "pronto" pelo caminho frio, como antes do aberto: abrir o
    aberto ali atrasaria a abertura da tela. Depois do "pronto", a previa mede no aberto."""
    from desdobra.tela import processo
    rte._com_quebra(job, modelo, None, manter=())
    mm.limpar_cache()
    espiao['chromium'] = 0
    visto = {}

    class JanelaQueOlha:
        def __init__(self, perfil, antes_de_apagar=None):
            self.perfil, self.perfil_apagado, self.versao = perfil, None, None

        def __enter__(self):
            a = mm._aberto
            visto['ligado'] = a is not None
            visto['montagem'] = (a.relatorio()['aberturas'], espiao['chromium'])
            # a previa de uma quebra nova mede no aberto
            mm.limpar_cache()
            _medir(job, {'quebras_por_familia': [_pedido(modelo['layer_id'], (0,))]})
            visto['previa'] = (a.relatorio()['aberturas'], espiao['chromium'])
            raise RuntimeError('fim do teste')

        def __exit__(self, *exc):
            return False
    monkeypatch.setattr(navegador, 'Janela', JanelaQueOlha)
    processo.executar(job, avisar=lambda linha: None)
    assert visto['ligado'] is True, visto
    assert visto['montagem'] == (0, 1), visto  # numero-neutro: nenhuma abertura do aberto, uma medida fria
    assert visto['previa'] == (1, 1), visto  # numero-neutro: o aberto abriu na previa
    assert list(tela_no_pytest.iterdir()) == []


def test_queda_do_aberto_nao_atrasa_o_caminho_frio_com_o_fecho(job, modelo, aberto, espiao, monkeypatch):
    """O pedido que acha o Chromium do aberto caido sai pelo caminho frio sem esperar o fecho do Chromium caido (a
    varredura e o apagar do perfil): o fecho corre no fio do aberto, e a medida seguinte ja abre outro Chromium."""
    lid = modelo['layer_id']
    b = {'quebras_por_familia': [_pedido(lid)]}
    frio = _frio(job, b)
    espiao['chromium'] = 0
    real = ab._varrer
    solta = threading.Event()

    def varrer_preso(*a, **k):
        solta.wait(60)  # numero-neutro: teto do teste
        return real(*a, **k)
    monkeypatch.setattr(ab, '_varrer', varrer_preso)
    aberto.espera_s = 5.0  # numero-neutro: teto do teste
    antes = _chrome_agora()
    try:
        mm.limpar_cache()
        assert _medir(job, b) == frio
        chrome = _chrome_novos(antes)
        primeiro = aberto.perfil
        for p in chrome:  # o Chromium do aberto cai (processos que este teste abriu pelo aberto)
            try:
                os.kill(p, signal.SIGTERM)
            except OSError:
                pass
        assert _morreram(chrome, ESPERA_MORTE_S)
        mm.limpar_cache()
        t = time.monotonic()
        assert _medir(job, b) == frio and espiao['chromium'] == 1
        assert time.monotonic() - t < aberto.espera_s, time.monotonic() - t
        # o fecho do Chromium caido ainda corre (a varredura presa), e a proxima medida ja abre outro
        assert primeiro.exists()
        mm.limpar_cache()
        assert _medir(job, b) == frio and espiao['chromium'] == 1
        rel = aberto.relatorio()
        assert rel['aberturas'] == 2 and rel['quedas'] == 1 and rel['travadas'] == 0, rel
    finally:
        solta.set()
    assert _esperar(lambda: aberto.relatorio()['perfis_apagados'] == 1, ESPERA_MORTE_S), aberto.relatorio()
    assert not primeiro.exists()


def test_artefatos_do_playwright_do_aberto_ficam_no_perfil(job, modelo, aberto, monkeypatch):
    """O Playwright cria uma pasta de artefatos (downloads e afins) para cada Chromium que abre. A do aberto fica
    dentro do perfil dele, nunca solta na pasta temporaria do driver: a varredura do fecho e a de orfas a acham."""
    pasta = Path(tempfile.mkdtemp(prefix='dsdt-'))
    try:
        monkeypatch.setenv('TEMP', str(pasta))  # a pasta temporaria do driver que o aberto abre
        monkeypatch.setenv('TMP', str(pasta))
        b = {'quebras_por_familia': [_pedido(modelo['layer_id'])]}
        mm.limpar_cache()
        assert 'largura_texto' in _medir(job, b)[mq.chave(modelo['layer_id'], (), ())]
        assert aberto.relatorio()['aberturas'] == 1
        assert not list(pasta.glob('playwright-artifacts-*')), list(pasta.iterdir())
        assert aberto.perfil is not None and aberto.perfil.is_dir()
        aberto.fechar()
        assert list(pasta.iterdir()) == []
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


# ------------------------------------------------------------------ revisao 2 do aberto
@pytest.fixture
def queda_na_abertura(monkeypatch):
    """Derruba o Chromium que o aberto acabou de abrir, antes da pagina do controle positivo: so os processos do
    Chromium embaixo do driver que o proprio aberto abriu, lidos no fio dele. vezes: quantas aberturas derrubar;
    derrubadas: quantas foram derrubadas (as tentativas de abrir)."""
    real = processos.descendentes
    estado = {'vezes': 0, 'derrubadas': 0}

    def descendentes(pid):
        r = real(pid)
        if estado['vezes'] and threading.current_thread().name == ab.NOME_FIO:
            estado['vezes'] -= 1
            estado['derrubadas'] += 1
            chrome = [p for p, nome in r if nome.lower().startswith('chrome')]
            for p in chrome:
                try:
                    os.kill(p, signal.SIGTERM)
                except OSError:
                    pass
            _morreram(chrome, ESPERA_MORTE_S)
        return r
    monkeypatch.setattr(processos, 'descendentes', descendentes)
    return estado


def test_chromium_do_aberto_que_cai_na_abertura_volta_na_proxima_medida(job, modelo, aberto, espiao, temp_curta,
                                                                        queda_na_abertura):
    """O Chromium do aberto cai logo depois de abrir, na primeira abertura da tela e na reabertura depois de uma queda:
    o pedido sai pelo caminho frio, e a medida seguinte abre o aberto de novo, em vez de desligar o aberto ate a tela
    fechar. O relatorio conta as aberturas que falharam."""
    lid = modelo['layer_id']
    b = {'quebras_por_familia': [_pedido(lid)]}
    frio = _frio(job, b)
    espiao['chromium'] = 0
    # a primeira abertura da tela cai: caminho frio
    queda_na_abertura['vezes'] = 1
    mm.limpar_cache()
    assert _medir(job, b) == frio and espiao['chromium'] == 1 and queda_na_abertura['derrubadas'] == 1
    # a seguinte abre o aberto e mede nele
    mm.limpar_cache()
    assert _medir(job, b) == frio and espiao['chromium'] == 1, aberto.relatorio()
    # o Chromium do aberto cai entre duas medidas (os processos que o proprio aberto guardou)
    chrome = [p for p, _i in aberto._fio.chromium]
    for p in chrome:
        try:
            os.kill(p, signal.SIGTERM)
        except OSError:
            pass
    assert _morreram(chrome, ESPERA_MORTE_S)
    mm.limpar_cache()
    assert _medir(job, b) == frio and espiao['chromium'] == 2  # numero-neutro: a queda sai pelo caminho frio
    # a reabertura cai tambem: caminho frio, e a seguinte mede no aberto aberto de novo
    queda_na_abertura['vezes'] = 1
    mm.limpar_cache()
    assert _medir(job, b) == frio and espiao['chromium'] == 3  # numero-neutro: a reabertura que caiu
    assert queda_na_abertura['derrubadas'] == 2  # numero-neutro: duas aberturas derrubadas
    mm.limpar_cache()
    assert _medir(job, b) == frio and espiao['chromium'] == 3, aberto.relatorio()  # numero-neutro: idem
    rel = aberto.relatorio()
    assert rel['aberturas'] == 2 and rel['quedas'] == 1 and rel['falhas_abertura'] == 2, rel  # numero-neutro: idem
    assert rel['desligado'] is False and rel['recusas'] == 0, rel
    # o perfil do Chromium que caiu entre as medidas apaga depois de responder; os das aberturas que cairam, na hora
    assert _esperar(lambda: aberto.relatorio()['perfis_apagados'] == 3, ESPERA_MORTE_S), aberto.relatorio()
    mm.usar_aberto(None)
    rel = aberto.fechar()
    assert rel['perfis_apagados'] == 4 and rel['perfis_que_ficaram'] == 0 and rel['limpo'] is True, rel
    assert list(temp_curta.iterdir()) == []


def test_aberto_que_cai_em_toda_abertura_desliga_no_teto_de_falhas_seguidas(job, modelo, aberto, espiao, temp_curta,
                                                                           queda_na_abertura):
    """O Chromium do aberto que cai em toda abertura: o aberto tenta de novo ate chromium.aberto_falhas_abertura_max
    aberturas seguidas que falham e entao fica desligado ate a tela fechar (o DA nao paga uma abertura que falha em
    cada previa). Toda medida sai certa, pelo caminho frio, e o relatorio diz que o aberto ficou desligado."""
    lid = modelo['layer_id']
    b = {'quebras_por_familia': [_pedido(lid)]}
    frio = _frio(job, b)
    espiao['chromium'] = 0
    queda_na_abertura['vezes'] = 100  # numero-neutro: toda abertura cai
    medidas = 6  # numero-neutro: mais medidas do que o teto
    for _ in range(medidas):
        mm.limpar_cache()
        assert _medir(job, b) == frio
    assert espiao['chromium'] == medidas
    # a abertura que caiu nao desliga o aberto na primeira vez
    assert queda_na_abertura['derrubadas'] > 1, aberto.relatorio()
    teto = int(limites.valor('chromium.aberto_falhas_abertura_max'))
    assert 1 < teto < medidas
    assert queda_na_abertura['derrubadas'] == teto, aberto.relatorio()
    mm.usar_aberto(None)
    rel = aberto.fechar()
    assert rel['aberturas'] == 0 and rel['falhas_abertura'] == teto and rel['desligado'] is True, rel
    assert rel['recusas'] == 0 and rel['perfis_apagados'] == teto and rel['limpo'] is True, rel
    assert list(temp_curta.iterdir()) == []


def test_servidor_do_controle_na_abertura_do_aberto_para_sem_esperar_meio_segundo(job, modelo, aberto,
                                                                                    monkeypatch):
    """O servidor da pagina do controle positivo, na abertura do aberto (a primeira quebra sem cache de cada tela e a
    reabertura depois de uma queda), para sem a espera de meio segundo do serve_forever, como o da pagina de medida."""
    real = servidor.ServidorFontes
    vistos = []

    class Espiao(real):
        def parar(self):
            t = time.perf_counter()
            super().parar()
            if self.pagina == ab.PAGINA_CONTROLE.encode('utf-8'):
                vistos.append((self.intervalo_s, time.perf_counter() - t))
    monkeypatch.setattr(servidor, 'ServidorFontes', Espiao)
    b = {'quebras_por_familia': [_pedido(modelo['layer_id'])]}
    mm.limpar_cache()
    assert 'largura_texto' in _medir(job, b)[mq.chave(modelo['layer_id'], (), ())]
    assert aberto.relatorio()['aberturas'] == 1 and len(vistos) == 1, vistos
    intervalo, parar_s = vistos[0]
    assert intervalo is not None and intervalo <= mm.INTERVALO_SERVIDOR_ABERTO_S, vistos
    assert parar_s < 0.25, vistos  # numero-neutro: teto do teste (a espera de antes era 0,5 s)
