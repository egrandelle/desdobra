# -*- coding: utf-8 -*-
"""M7b, B2: o ato de render na tela (desdobra.tela.ato_render; decisoes do Duda Q3, Q4 e Q14; a critica do plano).

Criterios de pronto cobertos aqui:
  - um clique e uma confirmacao renderizam os N formatos pedidos: o pedido monta o contrato de cada formato numa
    tarefa (fio de trabalho, fora da trava de escrita), e o texto da confirmacao diz os formatos e cada decisao que o
    contrato pede ao DA (pede_confirmacao), sem comando e sem nome de arquivo; os aceites ficam no pedido pendente;
  - o Confirmar emite um Disparo por formato (humano.exigir_tela, alvo do formato), cada um gasto por um render; o selo
    de um formato nunca serve a outro, nem pelo humano.conferir nem pelo render;
  - na tarefa, o contrato de cada formato e montado de novo e comparado com o que o DA confirmou: o formato que mudou
    nao vai para o render, fica "pede render" e o selo dele e gasto;
  - cancelar no meio do lote corta o formato em andamento; os prontos ficam renderizados;
  - o pedido que nao serve (formato fora do briefing, lista vazia ou repetida, formato bloqueado) nao abre dialogo;
  - a tarefa do pedido nao deixa marcador de render nem parada.json quando a janela fecha no meio;
  - o ato usa o comando 'render' de humano.COMANDOS: nada novo em ATOS_DA_TELA nem no gancho.
Tudo sintetico: o PSD de duas linhas de test_tela_palco, a fonte de autoteste do motor e o meio de teste da tela.
"""
import dataclasses
import json
import shutil
import sys
import threading

import pytest

import test_derivacao_apoio as ap
import test_fontes_apoio as fap
import test_tela_escrita as tte
import test_tela_palco as tp
import test_tela_servidor as tts
import test_tela_tarefas as ttt
from desdobra import arquivos, contratos, humano
from desdobra.briefing import modelo as mb
from desdobra.derivacao import nucleo as nd
from desdobra.job import nucleo
from desdobra.render import execucao
from desdobra.tela import ato_render as tar
from desdobra.tela import atos as ta
from desdobra.tela import estado as te
from desdobra.tela import servidor as ts
from desdobra.tela import tarefas as tt

ROT0 = {'graus': 0, 'sentido': None}
DOIS = ['mesma', 'perto']
RENDER = pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
# nada de comando para o DA (o nome do produto pode aparecer, o comando nao), de arquivo, de travessao nem de Trezion
PROIBIDOS = ('"desdobra', 'desdobra render', '--', 'Rode', 'rode ', 'terminal', 'comando', '.json', 'render/',
             chr(0x2013), chr(0x2014), 'Trezion')


@pytest.fixture(scope='module')
def modelo(tmp_path_factory):
    """O job de duas linhas com os tres formatos derivados (mesma, perto e largo), briefing de teste."""
    from desdobra.render import autoteste
    base = tmp_path_factory.mktemp('ato-render')
    fontes = base / 'origem-fontes'
    fap.gravar(fontes, 'autoteste.ttf', autoteste.gerar_fonte())
    job = base / 'job'
    nucleo.criar(job, tp._psd_duas_linhas(base / 'origem' / 'kv.psd', autoteste.NOME_PS), 'c', fontes=[fontes])
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    laudo = contratos.ler(job / mb.ARQUIVO_LAUDO, 'laudo/1')
    ids = {c['nome']: c['identidade']['layer_id'] for c in laudo['camadas']}
    funcoes = {ids['fundo-sintetico']: 'fundo', ids['duas-linhas']: 'titulo',
               ids['quadrado-sintetico']: 'logo_principal'}
    b = ap.briefing(funcoes=funcoes, formatos=[ap.formato(i, w, h, rotacao=ROT0) for i, w, h in tp.FORMATOS_DUAS])
    b.pop('cabecalho')
    b.pop('job_id')
    arq = base / 'fixture.json'
    arq.write_text(json.dumps(b), encoding='utf-8')
    mb.importar_teste(job, arq)
    nd.derivar(job)
    return job


@pytest.fixture
def job(modelo, tmp_path):
    destino = tmp_path / 'job'
    shutil.copytree(modelo, destino)
    return destino


@pytest.fixture
def selos(monkeypatch):
    """Os Disparos que a tela emitiu, na ordem (o caminho de verdade, so anotado)."""
    emitidos = []
    original = humano.exigir_tela

    def anotar(*a, **k):
        d = original(*a, **k)
        emitidos.append(d)
        return d
    monkeypatch.setattr(humano, 'exigir_tela', anotar)
    return emitidos


@pytest.fixture
def renders(monkeypatch):
    """Cada render que a tarefa chamou: (formato, alvo do selo, fio)."""
    feitos = []
    original = execucao.renderizar

    def anotar(pasta, **k):
        feitos.append((k.get('formato'), k['disparo'].alvo, threading.current_thread().name))
        return original(pasta, **k)
    monkeypatch.setattr(execucao, 'renderizar', anotar)
    return feitos


def _servidor(job):
    conteudo = te.montar(job)
    return ts.ServidorTela(conteudo, pasta=job, modo_teste=True, atos=ta.atos_do_job(job, conteudo=conteudo))


@pytest.fixture
def srv(job):
    s = _servidor(job).iniciar()
    yield s
    s.parar()


def _esperar_fim(s, biscoito, ident):
    return ttt._esperar(lambda: (lambda v: v if v and v['situacao'] not in ('na_fila', 'rodando') else None)(
        ttt._tarefa(s, biscoito, ident)), teto_s=600)  # numero-neutro: teto do teste para um lote de render


def _pedir(s, biscoito, formatos):
    """O pedido do ato de render: 202 com a tarefa do preparo; devolve (codigo, vista da tarefa no fim ou None)."""
    codigo, _c, corpo = tte._escrever(s, '/api/ato/pedir', {'ato': 'render', 'dados': {'formatos': formatos}},
                                      cookie=biscoito)
    if codigo != 202:  # numero-neutro: codigo HTTP
        return codigo, None
    return codigo, _esperar_fim(s, biscoito, json.loads(corpo)['tarefa'])


def _confirmar(s, biscoito, pedido):
    codigo, _c, corpo = tte._escrever(s, '/api/ato/confirmar', {'pedido': pedido, 'resposta': 'confirmar'},
                                      cookie=biscoito)
    if codigo != 202:  # numero-neutro: codigo HTTP
        return codigo, None
    return codigo, _esperar_fim(s, biscoito, json.loads(corpo)['tarefa'])


def _rel(job, fid):
    arq = job / 'render' / fid / 'render.json'
    return arquivos.ler_json(arq) if arq.is_file() else None


# ------------------------------------------------------------------ o selo preso ao formato
def test_selo_da_tela_preso_ao_formato_nao_serve_outro():
    sessao = humano.abrir_sessao_tela(teste=True)
    try:
        d = humano.exigir_tela('render', sessao, confirmado=True, alvo='perto')
        assert d.alvo == 'perto'
        with pytest.raises(humano.ErroHumano):
            humano.conferir(d, 'render', alvo='mesma')
        with pytest.raises(humano.ErroHumano):
            humano.conferir(d, 'render')  # sem dizer o formato, o selo preso nao serve
        # o Disparo copiado com outro alvo leva o mesmo selo, e o registro do selo e que vale
        with pytest.raises(humano.ErroHumano):
            humano.conferir(dataclasses.replace(d, alvo='mesma'), 'render', alvo='mesma')
        # a recusa nao gasta: o selo continua valendo para o formato dele, uma vez
        assert humano.conferir(d, 'render', consumir=True, alvo='perto') is d
        with pytest.raises(humano.ErroHumano):
            humano.conferir(d, 'render', alvo='perto')
    finally:
        humano.fechar_sessao_tela(sessao)


def test_selo_sem_formato_do_terminal_serve_o_formato_que_o_render_pedir(pessoa):
    d = pessoa.exigir('render')
    assert d.alvo is None
    assert humano.conferir(d, 'render', alvo='perto') is d


def test_render_recusa_o_selo_de_outro_formato_sem_gravar_nada(job):
    sessao = humano.abrir_sessao_tela(teste=True)
    try:
        d = humano.exigir_tela('render', sessao, confirmado=True, alvo='perto')
        with pytest.raises(execucao.ErroRender) as e:
            execucao.renderizar(job, disparo=d, formato='mesma', aceites=('largura_divergente',))
        assert e.value.motivo == 'disparo_sem_conferencia'
        assert not (job / 'render' / 'mesma').exists()
        # o selo de perto nao foi gasto pela tentativa em mesma
        assert humano.conferir(d, 'render', alvo='perto') is d
    finally:
        humano.fechar_sessao_tela(sessao)


def test_ato_de_render_usa_o_comando_render_sem_ato_novo_da_tela(job):
    ato = ta.atos_do_job(job)['render']
    assert ato.comando == 'render' and ato.longo and ato.selo_por_formato and callable(ato.preparar)
    # M7c, M3: a marca do job e o unico ato da tela novo depois do render
    assert 'render' in humano.COMANDOS and \
        humano.ATOS_DA_TELA == ('modo dados escolher', 'familia confirmar', 'marca escolher')


# ------------------------------------------------------------------ o pedido
@pytest.mark.parametrize('formatos', [[], ['mesma', 'mesma'], ['nao-existe'], ['mesma', 1], 'mesma', None])
def test_pedido_que_nao_serve_e_recusado_sem_tarefa(srv, formatos):
    biscoito = tts._entrar(srv)
    codigo, _v = _pedir(srv, biscoito, formatos)
    assert codigo == 403 and srv.tarefas.ultima is None  # numero-neutro: codigo HTTP


def test_pedido_com_chave_a_mais_e_recusado(srv):
    biscoito = tts._entrar(srv)
    codigo, _c, _corpo = tte._escrever(srv, '/api/ato/pedir', {'ato': 'render', 'dados': {'formatos': DOIS, 'x': 1}},
                                       cookie=biscoito)
    assert codigo == 403  # numero-neutro: codigo HTTP


def test_pedido_monta_os_contratos_na_tarefa_e_diz_formatos_e_decisoes(srv, job, monkeypatch):
    fios = []
    original = execucao.montar_contrato

    def anotar(pasta, formato='origem', funcoes=None):
        fios.append((formato, threading.current_thread().name))
        return original(pasta, formato, funcoes)
    monkeypatch.setattr(execucao, 'montar_contrato', anotar)
    biscoito = tts._entrar(srv)
    codigo, v = _pedir(srv, biscoito, DOIS)
    assert codigo == 202 and v['situacao'] == 'feita' and v['nome'] == tar.TAREFA_PEDIDO, v
    # o contrato de cada formato foi montado no fio de trabalho, nunca no fio do pedido HTTP
    assert [f for f, _n in fios] == DOIS and {n for _f, n in fios} == {'desdobra-tela-tarefas'}
    r = v['resposta']
    assert set(r) == {'pedido', 'titulo', 'texto', 'sim', 'nao', 'formatos', 'decisoes'}
    assert len(r['pedido']) == 32 and (r['sim'], r['nao']) == ('Confirmar', 'Cancelar')  # numero-neutro: 16 bytes
    assert r['formatos'] == [{'id': 'mesma', 'nome': '640x320'}, {'id': 'perto', 'nome': '400x240'}]
    assert r['decisoes'] == [{'codigo': 'largura_divergente', 'formatos': DOIS,
                              'texto': tar.DECISOES['largura_divergente']}]
    texto = r['texto']
    assert '640x320' in texto and '400x240' in texto and '2048x720' not in texto
    assert 'Nos formatos 640x320 e 400x240, a' + tar.DECISOES['largura_divergente'][1:] in texto
    for proibido in PROIBIDOS:
        assert proibido not in texto, (proibido, texto)
    # os aceites ficam no pedido pendente, do lado do servidor
    pedido, nome, dados, preparado = srv._pendente
    assert (pedido, nome, dados) == (r['pedido'], 'render', {'formatos': DOIS})
    assert [preparado[f]['aceites'] for f in DOIS] == [['largura_divergente'], ['largura_divergente']]
    # o pedido nao grava nada no job, nem marcador de render
    assert not (job / 'render').exists() and not (job / nucleo.ARQUIVO_TRAVA).exists()


def test_formato_bloqueado_para_o_pedido_sem_dialogo(srv, job, monkeypatch):
    original = execucao.montar_contrato

    def bloquear(pasta, formato='origem', funcoes=None):
        if formato == 'perto':
            return None, [{'codigo': 'derivacao_desatualizada', 'descricao': 'x', 'medidas': {}}], []
        return original(pasta, formato, funcoes)
    monkeypatch.setattr(execucao, 'montar_contrato', bloquear)
    biscoito = tts._entrar(srv)
    codigo, v = _pedir(srv, biscoito, DOIS)
    assert codigo == 202 and v['situacao'] == 'parou' and v['motivo'] == 'formato_bloqueado'
    assert v['resposta'] == {'bloqueados': [{'id': 'perto', 'nome': '400x240'}]}
    assert v['texto'] == tt.TEXTOS_POR_MOTIVO['formato_bloqueado'] and srv._pendente is None


def test_janela_fechada_no_meio_do_pedido_nao_deixa_marcador_nem_parada(job, monkeypatch):
    liberar, chegou = threading.Event(), threading.Event()
    original = execucao.montar_contrato

    def segurar(pasta, formato='origem', funcoes=None):
        chegou.set()
        liberar.wait(30)  # numero-neutro: teto do teste
        return original(pasta, formato, funcoes)
    monkeypatch.setattr(execucao, 'montar_contrato', segurar)
    s = _servidor(job).iniciar()
    try:
        biscoito = tts._entrar(s)
        codigo, _c, _corpo = tte._escrever(s, '/api/ato/pedir', {'ato': 'render', 'dados': {'formatos': DOIS}},
                                           cookie=biscoito)
        assert codigo == 202 and chegou.wait(30)  # numero-neutro: codigo HTTP e teto do teste
        assert not (job / tt.ARQUIVO_MARCADOR).exists()
        threading.Timer(0.2, liberar.set).start()  # numero-neutro: o preparo acaba durante a parada
    finally:
        s.parar()
    assert not (job / tt.ARQUIVO_MARCADOR).exists()
    assert not list((job / 'render').glob('*/parada.json')) if (job / 'render').exists() else True
    assert not (job / nucleo.ARQUIVO_TRAVA).exists()


# ------------------------------------------------------------------ a confirmacao e o lote
@RENDER
def test_um_clique_e_uma_confirmacao_renderizam_os_formatos_com_um_selo_cada(srv, job, selos, renders):
    biscoito = tts._entrar(srv)
    _c, v = _pedir(srv, biscoito, DOIS)
    codigo, fim = _confirmar(srv, biscoito, v['resposta']['pedido'])
    assert codigo == 202 and fim['situacao'] == 'feita', fim  # numero-neutro: codigo HTTP
    assert fim['nome'] == 'render' and fim['feitos'] == DOIS and fim['faltam'] == []
    # um Disparo por formato, preso a ele, e cada render recebeu o do proprio formato, no fio de trabalho
    assert [(d.comando, d.alvo, d.meio) for d in selos] == [('render', f, humano.MEIO_MEDICAO) for f in DOIS]
    assert [(f, alvo) for f, alvo, _n in renders] == [(f, f) for f in DOIS]
    assert {n for _f, _a, n in renders} == {'desdobra-tela-tarefas'}
    for d in selos:
        with pytest.raises(humano.ErroHumano):
            humano.conferir(d, 'render', alvo=d.alvo)  # todos gastos
    for f in DOIS:
        rel = _rel(job, f)
        assert rel is not None and (job / 'render' / f / 'master.png').is_file()
        assert rel['disparo']['meio'] == humano.MEIO_MEDICAO
        assert [a['codigo'] for a in rel['aceites']] == ['largura_divergente']
    assert _rel(job, 'largo') is None
    assert set(fim['resposta']['tempos_s']) == set(DOIS) and fim['resposta']['mudaram'] == []
    assert not (job / tt.ARQUIVO_MARCADOR).exists() and not (job / nucleo.ARQUIVO_TRAVA).exists()
    eventos = [json.loads(x) for x in (job / 'log' / 'eventos.jsonl').read_text(encoding='utf-8').splitlines()]
    assert [e['formato'] for e in eventos if e['evento'] == 'render_concluido'] == DOIS
    # o pedido morreu no Confirmar
    assert _confirmar(srv, biscoito, v['resposta']['pedido'])[0] == 403  # numero-neutro: codigo HTTP


@RENDER
def test_formato_que_mudou_depois_do_pedido_nao_vai_para_o_render(srv, job, selos, renders, monkeypatch):
    biscoito = tts._entrar(srv)
    _c, v = _pedir(srv, biscoito, DOIS)
    original = execucao.montar_contrato

    def mudar(pasta, formato='origem', funcoes=None):
        contrato, bloqueios, confirmar = original(pasta, formato, funcoes)
        if formato == 'mesma' and contrato is not None:
            contrato = dict(contrato, fora_da_peca=list(contrato['fora_da_peca']) + ['mudou-depois'])
        return contrato, bloqueios, confirmar
    monkeypatch.setattr(execucao, 'montar_contrato', mudar)
    codigo, fim = _confirmar(srv, biscoito, v['resposta']['pedido'])
    assert codigo == 202 and fim['situacao'] == 'parou' and fim['motivo'] == 'contrato_mudou', fim
    assert fim['feitos'] == ['perto'] and fim['faltam'] == ['mesma']
    assert fim['resposta']['mudaram'] == ['mesma'] and fim['texto'] == tt.TEXTOS_POR_MOTIVO['contrato_mudou']
    assert [f for f, _a, _n in renders] == ['perto'] and _rel(job, 'mesma') is None and _rel(job, 'perto')
    for d in selos:
        with pytest.raises(humano.ErroHumano):
            humano.conferir(d, 'render', alvo=d.alvo)  # o selo do formato que mudou tambem foi gasto


@RENDER
def test_decisao_nova_depois_do_pedido_tambem_conta_como_mudanca(srv, job, renders, monkeypatch):
    biscoito = tts._entrar(srv)
    _c, v = _pedir(srv, biscoito, ['perto'])
    original = execucao.montar_contrato

    def decidir(pasta, formato='origem', funcoes=None):
        contrato, bloqueios, confirmar = original(pasta, formato, funcoes)
        return contrato, bloqueios, list(confirmar) + [{'codigo': 'clipping_dividido_por_texto', 'medidas': {}}]
    monkeypatch.setattr(execucao, 'montar_contrato', decidir)
    _codigo, fim = _confirmar(srv, biscoito, v['resposta']['pedido'])
    assert fim['situacao'] == 'parou' and fim['resposta']['mudaram'] == ['perto'] and renders == []


@RENDER
def test_cancelar_no_meio_do_lote_corta_o_formato_em_andamento_e_os_prontos_ficam(srv, job, renders, monkeypatch):
    biscoito = tts._entrar(srv)
    _c, v = _pedir(srv, biscoito, DOIS)
    original = execucao.renderizar  # ja anotado pela fixture renders

    def cancelar_no_segundo(pasta, **k):
        if k['formato'] == DOIS[1]:
            srv.tarefas.cancelar(srv.tarefas.ultima.id)  # o DA clicou em cancelar quando o segundo comecou
        return original(pasta, **k)
    monkeypatch.setattr(execucao, 'renderizar', cancelar_no_segundo)
    _codigo, fim = _confirmar(srv, biscoito, v['resposta']['pedido'])
    assert fim['situacao'] == 'cancelada' and fim['feitos'] == [DOIS[0]] and fim['faltam'] == [DOIS[1]], fim
    assert _rel(job, DOIS[0]) is not None and _rel(job, DOIS[1]) is None
    assert arquivos.ler_json(job / 'render' / DOIS[1] / 'parada.json')['motivo'] == tt.MOTIVO_PARADO
    assert not (job / tt.ARQUIVO_MARCADOR).exists() and not (job / nucleo.ARQUIVO_TRAVA).exists()


@RENDER
def test_cancelar_depois_do_ultimo_render_nao_esconde_o_formato_que_mudou(srv, job, renders, monkeypatch):
    """Revisao do M7b, fase B: o Cancelar chega quando o ultimo formato ja gravou. Nada foi cortado: a tela diz que
    um formato mudou e ficou sem render (contrato_mudou), e nao que o render foi cancelado no meio de um formato."""
    biscoito = tts._entrar(srv)
    _c, v = _pedir(srv, biscoito, DOIS)
    contrato_original, render_original = execucao.montar_contrato, execucao.renderizar

    def mudar(pasta, formato='origem', funcoes=None):
        contrato, bloqueios, confirmar = contrato_original(pasta, formato, funcoes)
        if formato == 'mesma' and contrato is not None:
            contrato = dict(contrato, fora_da_peca=list(contrato['fora_da_peca']) + ['mudou-depois'])
        return contrato, bloqueios, confirmar

    def cancelar_depois(pasta, **k):
        rel = render_original(pasta, **k)
        srv.tarefas.cancelar(srv.tarefas.ultima.id)  # o clique chega com o master ja gravado
        return rel
    monkeypatch.setattr(execucao, 'montar_contrato', mudar)
    monkeypatch.setattr(execucao, 'renderizar', cancelar_depois)
    _codigo, fim = _confirmar(srv, biscoito, v['resposta']['pedido'])
    assert fim['situacao'] == 'parou' and fim['motivo'] == 'contrato_mudou', fim
    assert fim['feitos'] == ['perto'] and fim['resposta']['mudaram'] == ['mesma']
    assert _rel(job, 'perto') is not None and not (job / 'render' / 'perto' / 'parada.json').exists()


# ------------------------------------------------------------------ o fim da tarefa
def test_situacao_final_so_aparece_com_a_trava_solta(tmp_path, monkeypatch):
    """Quem ve "feita" ja acha o job solto e a tela livre: o Confirmar logo depois do preparo nao bate na tarefa."""
    import time
    job = tmp_path / 'job'
    (job / 'laudo').mkdir(parents=True)
    (job / 'estado.json').write_text('{}', encoding='utf-8')
    original = tt.Tarefas._apagar_marcador

    def devagar(self):
        time.sleep(0.3)  # numero-neutro: a limpeza do fim demora mais que a leitura da vista
        return original(self)
    monkeypatch.setattr(tt.Tarefas, '_apagar_marcador', devagar)
    tarefas = tt.Tarefas(job)
    t = tarefas.iniciar('render', lambda tarefa: {'ok': True}, formatos=['f1'])
    vistas = []
    while t.ativa:
        v = t.vista()
        vistas.append((v['situacao'], tarefas.ocupada, (job / nucleo.ARQUIVO_TRAVA).exists()))
    assert t.vista()['situacao'] == 'feita' and not (job / nucleo.ARQUIVO_TRAVA).exists()
    assert all(s in ('na_fila', 'rodando') for s, _o, _tr in vistas if _o or _tr), vistas[-3:]


# ------------------------------------------------------------------ textos
def test_textos_das_decisoes_e_da_tarefa_para_o_da():
    textos = list(tar.DECISOES.values()) + [tar.DECISAO_SEM_TEXTO] + list(tt.TEXTOS_POR_MOTIVO.values()) + \
        list(tt.TEXTOS_POR_TAREFA[tar.TAREFA_PEDIDO].values())
    for texto in textos:
        for proibido in PROIBIDOS:
            assert proibido not in texto, (proibido, texto)
    # toda decisao que o contrato pode pedir tem texto proprio para o DA
    from desdobra.render import contrato as mc
    from desdobra.render import derivado as rd
    pedem = {'largura_divergente', 'efeito_sobre_texto_sem_aplicar', 'clipping_dividido_por_texto',
             'mesclagem_sem_o_fundo_de_outro_elemento'}
    assert pedem <= set(mc.DESCRICOES_BLOQUEIO) | set(rd.DESCRICOES) and pedem == set(tar.DECISOES)


def test_texto_da_confirmacao_junta_formatos_e_decisoes():
    itens = [{'id': 'a', 'nome': '640x320', 'decisoes': ['largura_divergente']},
             {'id': 'b', 'nome': '400x240', 'decisoes': []},
             {'id': 'c', 'nome': '2048x720', 'decisoes': ['largura_divergente', 'codigo_novo']}]
    texto = tar.texto_da_confirmacao(itens)
    assert texto.startswith('Os formatos 640x320, 400x240 e 2048x720 vão para o render.')
    assert 'Nos formatos 640x320 e 2048x720, ' + tar.DECISOES['largura_divergente'][0].lower() in texto
    assert 'No formato 2048x720, ' + tar.DECISAO_SEM_TEXTO[0].lower() in texto
    assert texto.endswith(tar.ACEITE)
    um = tar.texto_da_confirmacao([{'id': 'b', 'nome': '400x240', 'decisoes': []}])
    assert um.startswith('O formato 400x240 vai para o render.') and tar.ACEITE not in um
