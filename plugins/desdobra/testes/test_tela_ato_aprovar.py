# -*- coding: utf-8 -*-
"""M7b, B4: o ato de aprovar na tela (desdobra.tela.ato_aprovar), o nucleo comum da aprovacao
(desdobra.entrega.nucleo_aprovar) e o sentido do giro gravado na mesma confirmacao (decisoes do Duda Q2, Q11 e Q13; a
critica do plano).

Criterios de pronto cobertos aqui:
  - aprovacao por formato: o pedido roda o portao (conferir com final=True) de cada formato marcado numa tarefa, grava
    a previa em entrega/previa/ e a janela mostra o arquivo final de cada um (/final/<formato>); a confirmacao confere
    tudo de novo com a trava do job e grava um registro por formato, com meio e origem do Disparo da tela;
  - o formato com falha no portao para o pedido sem dialogo; o job que mudou entre o pedido e o Confirmar nao grava;
  - o formato girado 90 ou 270 graus sem o sentido confirmado pede o sentido; o sentido escolhido na janela vale para
    o arquivo final mostrado e e gravado em parametros/entrega.json pela mesma confirmacao, com o Disparo da tela do
    parametros-entrega;
  - o portao da entrega recusa a aprovacao e o sentido do modo de teste (meio medicao, origem fixture_de_teste);
  - pronto do B4: aprovar f1 e f2 na tela, mudar a funcao de uma camada que so afeta f1 (o salvar seletivo do A6),
    reabrir: f1 aparece com a aprovacao caida e o motivo, f2 continua aprovado. A medida dos que ficam e
    aprovacao.diferencas, nunca o portao com aprovacao=True (a critica: a aprovacao do modo de teste ele recusa);
  - a linha de comando da Trezion continua aprovando pelo mesmo nucleo.
Tudo sintetico: o PSD de test_derivacao_apoio.psd_derivacao, uma fonte inventada e o meio de teste da tela.
"""
import json
import shutil
import sys
import threading
from argparse import Namespace
from pathlib import Path

import pytest

import test_cadeia_por_formato as tcp
import test_derivacao_apoio as ap
import test_fontes_apoio as fap
import test_render_apoio as rap
import test_tela_ato_render as tar
import test_tela_escrita as tte
import test_tela_servidor as tts
from desdobra import arquivos, contratos, humano
from desdobra.briefing import modelo as mb
from desdobra.derivacao import nucleo as nd
from desdobra.entrega import aprovacao, codificar, nucleo_aprovar, portao
from desdobra.job import nucleo
from desdobra.render import execucao
from desdobra.tela import ato_aprovar as taa
from desdobra.tela import atos as ta
from desdobra.tela import estado as te
from desdobra.tela import tarefas as tt

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')

ROT0 = {'graus': 0, 'sentido': None}
ROT90 = {'graus': 90, 'sentido': None}
# perto (f1) tem o texto de apoio; mesma (f2) e giro nao (a familia de cada um apagou); giro vai girado 90 graus para o
# veiculo, com a composicao de pe na mesma medida de mesma
FORMATOS = [ap.formato('perto', 400, 240, rotacao=ROT0), ap.formato('mesma', 640, 320, rotacao=ROT0),
            ap.formato('giro', 320, 640, rotacao=ROT90)]
IDS = [f['id'] for f in FORMATOS]
DOIS = ['perto', 'mesma']
TIPOS = {'perto': ['image/jpeg'], 'mesma': ['image/jpeg', 'image/png'], 'giro': ['image/jpeg', 'image/png']}
NOMES = {'perto': '400x240', 'mesma': '640x320', 'giro': '320x640'}
PROIBIDOS = tar.PROIBIDOS + ('aprovacao.json', 'parametros', 'medicao', 'fixture')


def _campos(tipos):
    return {'tipos_aceitos': {'id': 'tipos', 'valor': tipos, 'situacao': 'confirmado'},
            'peso_max': {'id': 'peso', 'valor': {'alvo_bytes': 10 ** 6, 'reprova_acima_bytes': 10 ** 6 + 6000},
                         'condicao': None, 'situacao': 'confirmado'}}


@pytest.fixture(scope='module')
def renderizado(tmp_path_factory):
    """O job da cadeia por formato (test_cadeia_por_formato) com a folha que o encoder le, o briefing de teste com uma
    familia por formato e os tres formatos renderizados por selos de teste presos a cada um."""
    from desdobra.job import fases as mod_fases
    base = tmp_path_factory.mktemp('aprovar')
    fontes = base / 'origem-fontes'
    fap.gravar(fontes, 'inventada.ttf', fap.fonte(ps=rap.FONTE))
    job = base / 'job'
    nucleo.criar(job, ap.psd_derivacao(base / 'origem' / 'kv.psd'), 'c', fontes=[fontes])
    assert nucleo.proxima(job, todas=True).codigo == 0
    arquivos.gravar_json_atomico(job / mb.ARQUIVO_FORMATOS, {'tipo': 'formatos_do_job', 'formatos': [
        {'id': f['id'], 'chave': f['chave'], 'campos': _campos(TIPOS[f['id']])} for f in FORMATOS]})
    estado = nucleo.ler_estado(job)
    estado['fases']['specs']['hash_saidas'] = nucleo.hashes_das_saidas(
        job, next(f for f in mod_fases.ESTEIRA if f.id == 'specs'))
    nucleo.gravar_estado(job, estado)
    assert nucleo.proxima(job, todas=True).codigo == 0
    laudo = contratos.ler(job / mb.ARQUIVO_LAUDO, 'laudo/1')
    b, ids = ap.briefing_do_job(laudo, FORMATOS)
    apagar = [{'elemento': 'el%d' % ids['texto-apoio'], 'acao': 'apagar'}]
    b['composicoes'] = [tcp._familia('perto'), tcp._familia('mesma', apagar), tcp._familia('giro', apagar)]
    arq = base / 'fixture.json'
    arq.write_text(json.dumps(b), encoding='utf-8')
    mb.importar_teste(job, arq)
    nd.derivar(job)
    sessao = humano.abrir_sessao_tela(teste=True)
    try:
        for f in IDS:
            _c, _b, pede = execucao.montar_contrato(job, f)
            d = humano.exigir_tela('render', sessao, confirmado=True, alvo=f)
            execucao.renderizar(job, disparo=d, formato=f, aceites=sorted({c['codigo'] for c in pede}))
    finally:
        humano.fechar_sessao_tela(sessao)
    return job


@pytest.fixture
def job(renderizado, tmp_path):
    destino = tmp_path / 'job'
    shutil.copytree(renderizado, destino)
    return destino


@pytest.fixture
def srv(job):
    s = tar._servidor(job).iniciar()
    yield s
    s.parar()


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


def _pedir(s, biscoito, formatos, sentidos=None):
    """O pedido do ato de aprovar: 202 com a tarefa do preparo; devolve (codigo, vista da tarefa no fim ou None)."""
    dados = {'formatos': formatos} if sentidos is None else {'formatos': formatos, 'sentidos': sentidos}
    codigo, _c, corpo = tte._escrever(s, '/api/ato/pedir', {'ato': 'aprovar', 'dados': dados}, cookie=biscoito)
    if codigo != 202:  # numero-neutro: codigo HTTP
        return codigo, None
    return codigo, tar._esperar_fim(s, biscoito, json.loads(corpo)['tarefa'])


def _aprovar(s, biscoito, formatos, sentidos=None):
    """Pedido e Confirmar; devolve a vista da tarefa do Confirmar no fim."""
    _c, v = _pedir(s, biscoito, formatos, sentidos)
    assert v['situacao'] == 'feita', v
    codigo, fim = tar._confirmar(s, biscoito, v['resposta']['pedido'])
    assert codigo == 202, codigo  # numero-neutro: codigo HTTP
    return fim


def _aprovacao(job):
    arq = job / aprovacao.ARQUIVO
    return contratos.ler(arq, aprovacao.ESQUEMA) if arq.is_file() else None


def _eventos(job, nome):
    linhas = (job / 'log' / 'eventos.jsonl').read_text(encoding='utf-8').splitlines()
    return [x for x in map(json.loads, linhas) if x['evento'] == nome]


# ------------------------------------------------------------------ o ato
def test_ato_de_aprovar_usa_o_comando_aprovar_sem_ato_novo_da_tela(job):
    ato = ta.atos_do_job(job)['aprovar']
    assert ato.comando == 'aprovar' and ato.longo and callable(ato.preparar) and not ato.selo_por_formato
    assert ato.outros_comandos({'formatos': ['giro'], 'sentidos': {'giro': 'horario'}}) == ['parametros-entrega']
    assert ato.outros_comandos({'formatos': DOIS}) == []
    # M7c, M3: a marca do job e o unico ato da tela novo depois do aprovar
    assert humano.ATOS_DA_TELA == ('modo dados escolher', 'familia confirmar', 'marca escolher')
    assert 'aprovar' in humano.COMANDOS and 'parametros-entrega' in humano.COMANDOS


@pytest.mark.parametrize('dados', [
    {'formatos': []}, {'formatos': ['perto', 'perto']}, {'formatos': ['nao-existe']}, {'formatos': 'perto'},
    {'formatos': ['perto', 1]}, {'formatos': DOIS, 'x': 1}, {'formatos': ['giro'], 'sentidos': {'giro': 'norte'}},
    {'formatos': ['giro'], 'sentidos': {'perto': 'horario'}}, {'formatos': ['giro'], 'sentidos': ['horario']},
    {'formatos': ['giro'], 'sentidos': {'giro': None}}])
def test_pedido_que_nao_serve_e_recusado_sem_tarefa(srv, dados):
    biscoito = tts._entrar(srv)
    codigo, _c, _corpo = tte._escrever(srv, '/api/ato/pedir', {'ato': 'aprovar', 'dados': dados}, cookie=biscoito)
    assert codigo == 403 and srv.tarefas.ultima is None  # numero-neutro: codigo HTTP


# ------------------------------------------------------------------ o pedido
def test_pedido_roda_o_portao_na_tarefa_grava_a_previa_e_mostra_o_final(srv, job, monkeypatch):
    fios = []
    original = portao.conferir

    def anotar(pasta, formatos=None, **k):
        fios.append((list(formatos or []), k.get('final', True), threading.current_thread().name))
        return original(pasta, formatos, **k)
    monkeypatch.setattr(portao, 'conferir', anotar)
    biscoito = tts._entrar(srv)
    codigo, v = _pedir(srv, biscoito, DOIS)
    assert codigo == 202 and v['situacao'] == 'feita' and v['nome'] == tt.TAREFA_PREPARO, v
    # o portao (com o arquivo final) rodou no fio de trabalho, nunca no fio do pedido HTTP
    assert fios and all(final is True and n == 'desdobra-tela-tarefas' for _f, final, n in fios)
    assert sorted(f for fs, _x, _n in fios for f in fs) == sorted(DOIS)
    r = v['resposta']
    assert set(r) == {'pedido', 'titulo', 'texto', 'sim', 'nao', 'formatos'}
    assert [(f['id'], f['nome'], f['sentido']) for f in r['formatos']] == [('perto', '400x240', None),
                                                                          ('mesma', '640x320', None)]
    assert [f['extensao'] for f in r['formatos']] == ['jpg', 'png']
    for proibido in PROIBIDOS:
        assert proibido not in r['texto'], (proibido, r['texto'])
    assert '400x240' in r['texto'] and '640x320' in r['texto']
    # a previa esta gravada, e a janela mostra o arquivo final de cada formato pelo /final
    for f in r['formatos']:
        previa = job / aprovacao.PASTA_PREVIA / ('%s.%s' % (f['id'], f['extensao']))
        assert previa.is_file() and f['bytes'] == len(previa.read_bytes())
        c, cab, corpo = tts._pedir(srv, '/final/%s' % f['id'], cookie=biscoito)
        assert c == 200 and corpo == previa.read_bytes()  # numero-neutro: codigo HTTP
        assert cab['content-type'] == [{'jpg': 'image/jpeg', 'png': 'image/png'}[f['extensao']]]
    # o que o DA viu (hashes, sha do arquivo final e parametros) fica so no pedido pendente
    pedido, nome, dados, preparado = srv._pendente
    assert (pedido, nome, dados) == (r['pedido'], 'aprovar', {'formatos': DOIS})
    assert sorted(preparado['vista']) == sorted(DOIS)
    # o pedido nao grava a aprovacao
    assert _aprovacao(job) is None and not (job / nucleo.ARQUIVO_TRAVA).exists()


def test_formato_com_falha_no_portao_para_o_pedido_sem_dialogo(srv, job):
    shutil.rmtree(job / 'render' / 'mesma')
    biscoito = tts._entrar(srv)
    codigo, v = _pedir(srv, biscoito, DOIS)
    assert codigo == 202 and v['situacao'] == 'parou' and v['motivo'] == 'formato_com_falha', v
    assert v['resposta'] == {'com_falha': [{'id': 'mesma', 'nome': '640x320', 'codigos': ['sem_master']}]}
    assert v['texto'] == tt.TEXTOS_POR_MOTIVO['formato_com_falha'] and srv._pendente is None
    assert not (job / aprovacao.PASTA_PREVIA).exists()


# ------------------------------------------------------------------ a confirmacao
def test_confirmar_grava_um_registro_por_formato_com_o_disparo_da_tela(srv, job, selos):
    biscoito = tts._entrar(srv)
    fim = _aprovar(srv, biscoito, DOIS)
    assert fim['situacao'] == 'feita' and fim['nome'] == 'aprovar' and fim['feitos'] == DOIS, fim
    dados = _aprovacao(job)
    assert sorted(dados['formatos']) == sorted(DOIS)
    for fid in DOIS:
        reg = dados['formatos'][fid]
        assert reg['aprovado_por']['meio'] == humano.MEIO_MEDICAO
        assert reg['aprovado_por']['origem'] == humano.ORIGEM_FIXTURE
        previa = job / aprovacao.PASTA_PREVIA / ('%s.%s' % (fid, reg['arquivo_entregue']['extensao']))
        assert reg['arquivo_entregue']['sha256'] == arquivos.sha256_arquivo(previa)
    # uma confirmacao do DA, um Disparo do aprovar (sem alvo), gasto quando a tarefa acabou
    assert [(d.comando, d.alvo, d.meio) for d in selos] == [('aprovar', None, humano.MEIO_MEDICAO)]
    with pytest.raises(humano.ErroHumano):
        humano.conferir(selos[0], 'aprovar')
    assert _eventos(job, 'aprovacao_gravada')[-1]['meio'] == humano.MEIO_MEDICAO
    assert not (job / nucleo.ARQUIVO_TRAVA).exists() and not (job / tt.ARQUIVO_MARCADOR).exists()
    # o estado da tela depois da tarefa mostra os dois aprovados
    estado = tar.ttt._json(tts._pedir(srv, '/api/estado', cookie=biscoito))
    assert {f: estado['aprovacoes'][f]['situacao'] for f in IDS} == {'perto': 'aprovado', 'mesma': 'aprovado',
                                                                    'giro': 'sem_aprovacao'}


def test_job_que_mudou_entre_o_pedido_e_o_confirmar_nao_grava(srv, job):
    biscoito = tts._entrar(srv)
    _c, v = _pedir(srv, biscoito, DOIS)
    rel = job / 'render' / 'perto' / 'render.json'
    d = arquivos.ler_json(rel)
    d['gerado_em'] = '2026-11-09T12:00:00-03:00'
    arquivos.gravar_json_atomico(rel, d)
    codigo, fim = tar._confirmar(srv, biscoito, v['resposta']['pedido'])
    assert codigo == 202 and fim['situacao'] == 'parou' and fim['motivo'] == 'mudou_durante_a_confirmacao', fim
    assert fim['resposta'] == {'mudaram': ['perto']}
    assert fim['texto'] == tt.TEXTOS_POR_MOTIVO['mudou_durante_a_confirmacao']
    assert _aprovacao(job) is None


def _confirmar_com_cancelar(srv, biscoito, pedido, monkeypatch, depois_de_gravar):
    """O Confirmar, com o Cancelar do DA chegando pela rota de verdade durante a etapa 'Conferindo o arquivo final' (a
    segunda conferencia, dentro de nucleo_aprovar.confirmar) ou logo depois da gravacao."""
    comecou, cancelado = threading.Event(), threading.Event()
    alvo = aprovacao if depois_de_gravar else portao
    nome = 'gravar' if depois_de_gravar else 'conferir'
    original = getattr(alvo, nome)

    def esperar_o_cancelar(*a, **k):
        saida = original(*a, **k) if depois_de_gravar else None
        comecou.set()
        assert cancelado.wait(30)  # numero-neutro: teto do teste
        return saida if depois_de_gravar else original(*a, **k)
    monkeypatch.setattr(alvo, nome, esperar_o_cancelar)
    codigo, _c, corpo = tte._escrever(srv, '/api/ato/confirmar', {'pedido': pedido, 'resposta': 'confirmar'},
                                      cookie=biscoito)
    assert codigo == 202, codigo  # numero-neutro: codigo HTTP
    tarefa = json.loads(corpo)['tarefa']
    assert comecou.wait(30)  # numero-neutro: teto do teste
    assert tte._escrever(srv, '/api/tarefa/cancelar', {'tarefa': tarefa}, cookie=biscoito)[0] == 204
    cancelado.set()
    return tar._esperar_fim(srv, biscoito, tarefa)


def test_cancelar_durante_a_conferencia_da_confirmacao_nao_grava_nada(srv, job, monkeypatch):
    """Revisao do M7b, fase B: o Cancelar na etapa 'Conferindo o arquivo final' do Confirmar vale. Nada e gravado, e a
    tela diz isso."""
    biscoito = tts._entrar(srv)
    _c, v = _pedir(srv, biscoito, ['perto', 'giro'], sentidos={'giro': 'horario'})
    assert v['situacao'] == 'feita', v
    fim = _confirmar_com_cancelar(srv, biscoito, v['resposta']['pedido'], monkeypatch, depois_de_gravar=False)
    assert fim['situacao'] == 'cancelada' and fim['texto'] == tt.TEXTOS_POR_TAREFA['aprovar']['cancelada'], fim
    assert _aprovacao(job) is None and not (job / portao.ARQUIVO_PARAMETROS).exists()
    assert {f: s['situacao'] for f, s in nucleo_aprovar.situacao(job).items()} == {f: 'sem_aprovacao' for f in IDS}


def test_cancelar_depois_da_gravacao_termina_feita_e_diz_que_gravou(srv, job, monkeypatch):
    """O Cancelar que chega com a aprovacao ja gravada nao a desfaz: a tela diz que ela esta gravada."""
    biscoito = tts._entrar(srv)
    _c, v = _pedir(srv, biscoito, DOIS)
    fim = _confirmar_com_cancelar(srv, biscoito, v['resposta']['pedido'], monkeypatch, depois_de_gravar=True)
    assert fim['situacao'] == 'feita' and fim['texto'] == tt.TEXTOS_POR_TAREFA['aprovar']['feita'], fim
    assert sorted(_aprovacao(job)['formatos']) == sorted(DOIS)


def test_janela_fechada_no_meio_da_aprovacao_avisa_a_aprovacao_e_nao_o_render(job, monkeypatch):
    """Revisao do M7b, fase B: a janela fecha no comeco da tarefa de aprovar. A reabertura avisa que a aprovacao nao
    terminou; nenhum formato pede render, e nenhum ganha a parada do render."""
    import dataclasses
    s = tar._servidor(job).iniciar()
    try:
        biscoito = tts._entrar(s)
        _c, v = _pedir(s, biscoito, DOIS)
        ato = s.atos['aprovar']
        executar = ato.executar

        def executar_com_a_janela_fechando(disparo, d, tarefa, **k):
            while not tarefa.parar():
                threading.Event().wait(0.01)  # numero-neutro: intervalo do teste
            return executar(disparo, d, tarefa, **k)
        s.atos['aprovar'] = dataclasses.replace(ato, executar=executar_com_a_janela_fechando)
        codigo, _x, _y = tte._escrever(s, '/api/ato/confirmar', {'pedido': v['resposta']['pedido'],
                                                                'resposta': 'confirmar'}, cookie=biscoito)
        assert codigo == 202  # numero-neutro: codigo HTTP
    finally:
        s.parar()
    aviso = tt.recuperar(job)
    assert aviso['texto'] == tt.AVISOS_INACABADO['aprovar'] and sorted(aviso['formatos']) == sorted(DOIS)
    assert _aprovacao(job) is None
    assert not any((job / 'render' / f / 'parada.json').exists() for f in IDS)
    assert {f['id']: f['situacao'] for f in te.painel_dos_formatos(job)['formatos']} == {
        f: 'renderizado' for f in IDS}


def _servidor_com_aviso(job, aviso):
    """A tela reaberta como processo.executar faz, com o aviso da tarefa que a janela anterior deixou pela metade."""
    from desdobra.tela import servidor as ts
    conteudo = te.montar(job)
    conteudo['render_inacabado'] = dict(aviso)
    return ts.ServidorTela(conteudo, pasta=job, modo_teste=True, atos=ta.atos_do_job(job, conteudo=conteudo)).iniciar()


def _aviso_no_estado(s, biscoito):
    return json.loads(tts._pedir(s, '/api/estado', cookie=biscoito)[2]).get('render_inacabado')


def _renderizar_na_tela(s, biscoito, formatos):
    _c, v = tar._pedir(s, biscoito, formatos)
    assert v['situacao'] == 'feita', v
    codigo, fim = tar._confirmar(s, biscoito, v['resposta']['pedido'])
    assert codigo == 202 and fim['situacao'] == 'feita', fim  # numero-neutro: codigo HTTP


def test_aviso_da_tarefa_inacabada_sai_quando_o_da_refaz_os_formatos_na_tela(job):
    """Segunda revisao do M7b, fase B: o aviso da reabertura (a aprovacao ou o render que a janela anterior deixou pela
    metade) sai da faixa quando o DA refaz, na mesma janela, os formatos que ele cita, com a tarefa do mesmo tipo. Os
    formatos que ainda faltam ficam no aviso; a tarefa de outro tipo nao mexe nele."""
    aviso = {'texto': tt.AVISOS_INACABADO['aprovar'], 'formatos': list(DOIS), 'quando': None}
    s = _servidor_com_aviso(job, aviso)
    try:
        b = tts._entrar(s)
        assert _aviso_no_estado(s, b) == aviso
        _renderizar_na_tela(s, b, ['perto'])  # o render nao refaz a aprovacao
        assert _aviso_no_estado(s, b) == aviso
        assert _aprovar(s, b, ['perto'])['situacao'] == 'feita'
        assert _aviso_no_estado(s, b) == dict(aviso, formatos=['mesma'])
        assert _aprovar(s, b, ['mesma'])['situacao'] == 'feita'
        assert _aviso_no_estado(s, b) is None
    finally:
        s.parar()
    aviso = {'texto': tt.AVISO_INACABADO, 'formatos': ['giro'], 'quando': None}
    s = _servidor_com_aviso(job, aviso)
    try:
        b = tts._entrar(s)
        assert _aprovar(s, b, ['perto'])['situacao'] == 'feita'  # a aprovacao nao refaz o render
        assert _aviso_no_estado(s, b) == aviso
        _renderizar_na_tela(s, b, ['giro'])
        assert _aviso_no_estado(s, b) is None
    finally:
        s.parar()
    # o marcador ilegivel avisa sem formatos (do render): o primeiro render que termina tira o aviso
    s = _servidor_com_aviso(job, {'texto': tt.AVISO_INACABADO, 'formatos': [], 'quando': None})
    try:
        b = tts._entrar(s)
        _renderizar_na_tela(s, b, ['mesma'])
        assert _aviso_no_estado(s, b) is None
    finally:
        s.parar()


def test_aprovacao_da_tela_no_modo_de_teste_nunca_abre_a_entrega(srv, job):
    biscoito = tts._entrar(srv)
    _aprovar(srv, biscoito, DOIS)
    conf = portao.conferir(job, DOIS, origem=False, aprovacao=True)
    for fid in DOIS:
        falhas = conf['formatos'][fid]['falhas']
        assert [f['codigo'] for f in falhas] == ['aprovacao_de_teste'], falhas
        assert falhas[0]['medidas'] == {'meio': humano.MEIO_MEDICAO, 'origem': humano.ORIGEM_FIXTURE}


# ------------------------------------------------------------------ o sentido do giro
def test_formato_girado_sem_sentido_pede_o_sentido_sem_dialogo(srv, job):
    biscoito = tts._entrar(srv)
    codigo, v = _pedir(srv, biscoito, ['mesma', 'giro'])
    assert codigo == 202 and v['situacao'] == 'parou' and v['motivo'] == 'falta_sentido', v
    # composicao: o tamanho da peca antes do giro, para a figura da janela (revisao do M7b, fase B)
    assert v['resposta'] == {'sem_sentido': [{'id': 'giro', 'nome': '320x640', 'graus': 90,
                                              'sentido_do_briefing': None, 'composicao': [640, 320],
                                              'opcoes': [{'valor': s, 'texto': taa.SENTIDOS[s]}
                                                         for s in ('horario', 'anti_horario')]}]}
    assert v['texto'] == tt.TEXTOS_POR_MOTIVO['falta_sentido'] and srv._pendente is None
    assert not (job / aprovacao.PASTA_PREVIA).exists() and not (job / portao.ARQUIVO_PARAMETROS).exists()


def test_sentido_para_formato_que_nao_gira_e_recusado(srv, job):
    biscoito = tts._entrar(srv)
    codigo, v = _pedir(srv, biscoito, ['mesma'], sentidos={'mesma': 'horario'})
    assert codigo == 202 and v['situacao'] == 'parou' and v['motivo'] == 'sentido_recusado', v
    assert v['resposta'] == {'recusados': [{'id': 'mesma', 'nome': '640x320'}]}
    assert not (job / portao.ARQUIVO_PARAMETROS).exists()


@pytest.mark.parametrize('sentido', ['horario', 'anti_horario'])
def test_sentido_escolhido_vale_no_final_e_e_gravado_na_mesma_confirmacao(srv, job, selos, sentido):
    from PIL import Image
    biscoito = tts._entrar(srv)
    codigo, v = _pedir(srv, biscoito, ['giro'], sentidos={'giro': sentido})
    assert codigo == 202 and v['situacao'] == 'feita', v
    r = v['resposta']
    assert [(f['id'], f['sentido']) for f in r['formatos']] == [('giro', sentido)]
    assert taa.SENTIDOS_NO_TEXTO[sentido] in r['texto']
    for proibido in PROIBIDOS:
        assert proibido not in r['texto'], (proibido, r['texto'])
    # o arquivo final mostrado ja sai girado no sentido escolhido, e nada foi gravado ainda
    final = tts._pedir(srv, '/final/giro', cookie=biscoito)[2]
    master = Image.open(job / 'render' / 'giro' / 'master.png')
    with Image.open(__import__('io').BytesIO(final)) as img:
        assert img.size == (320, 640) and master.size == (640, 320)
    assert not (job / portao.ARQUIVO_PARAMETROS).exists()
    codigo, fim = tar._confirmar(srv, biscoito, r['pedido'])
    assert fim['situacao'] == 'feita', fim
    params = contratos.ler(job / portao.ARQUIVO_PARAMETROS, portao.ESQUEMA_PARAMETROS)['formatos']['giro']
    assert params['rotacao_sentido']['valor'] == sentido
    assert params['rotacao_sentido']['confirmado_por']['meio'] == humano.MEIO_MEDICAO
    assert params['rotacao_sentido']['confirmado_por']['origem'] == humano.ORIGEM_FIXTURE
    reg = _aprovacao(job)['formatos']['giro']
    assert reg['parametros_encoder']['rotacao'] == {'graus': 90, 'sentido': sentido}
    # uma confirmacao, dois selos (o do aprovar e o do parametros-entrega), os dois gastos
    assert sorted(d.comando for d in selos) == ['aprovar', 'parametros-entrega']
    for d in selos:
        with pytest.raises(humano.ErroHumano):
            humano.conferir(d, d.comando)
    # o portao do aprovar, agora pelo arquivo gravado, da o mesmo arquivo que o DA viu
    conf = portao.conferir(job, ['giro'], origem=False, aprovacao=False)
    assert conf['formatos']['giro']['final'].sha256 == reg['arquivo_entregue']['sha256']
    # o sentido do modo de teste nunca chega a entrega
    assert portao.confirmacao_de_teste(job) == 'confirmacao_de_fixture_de_teste'


def test_sentido_ja_confirmado_nao_e_pedido_de_novo(srv, job):
    biscoito = tts._entrar(srv)
    _aprovar(srv, biscoito, ['giro'], sentidos={'giro': 'horario'})
    codigo, v = _pedir(srv, biscoito, ['giro'])
    assert codigo == 202 and v['situacao'] == 'feita', v
    assert v['resposta']['formatos'][0]['sentido'] == 'horario'
    # e trocar o sentido gravado pela janela de aprovar e recusado (o sentido so e pedido quando falta)
    codigo, v = _pedir(srv, biscoito, ['giro'], sentidos={'giro': 'anti_horario'})
    assert v['situacao'] == 'parou' and v['motivo'] == 'sentido_recusado', v


def _renderizar_de_novo(job, f):
    sessao = humano.abrir_sessao_tela(teste=True)
    try:
        _c, _b, pede = execucao.montar_contrato(job, f)
        d = humano.exigir_tela('render', sessao, confirmado=True, alvo=f)
        execucao.renderizar(job, disparo=d, formato=f, aceites=sorted({c['codigo'] for c in pede}))
    finally:
        humano.fechar_sessao_tela(sessao)


def test_sentido_corrigido_no_briefing_e_pedido_de_novo_e_aprovado_na_tela(job, selos):
    """Revisao do M7b, fase B: o DA aprovou giro com o sentido horario e depois corrigiu o giro no passo 1 para
    anti_horario. O sentido gravado ficou velho: a janela pede o sentido de novo, so com o do briefing, e a mesma
    confirmacao troca o sentido gravado e aprova."""
    s = tar._servidor(job).iniciar()
    try:
        assert _aprovar(s, tts._entrar(s), ['giro'], sentidos={'giro': 'horario'})['situacao'] == 'feita'
    finally:
        s.parar()
    afetados = _salvar_seletivo(job, lambda b: next(f for f in b['formatos'] if f['id'] == 'giro').update(
        rotacao={'graus': 90, 'sentido': 'anti_horario'}))
    assert afetados == ['giro']
    _renderizar_de_novo(job, 'giro')
    s = tar._servidor(job).iniciar()
    try:
        biscoito = tts._entrar(s)
        _c, v = _pedir(s, biscoito, ['giro'])
        assert v['situacao'] == 'parou' and v['motivo'] == 'falta_sentido', v
        pede = v['resposta']['sem_sentido'][0]
        assert pede['sentido_do_briefing'] == 'anti_horario'
        assert pede['opcoes'] == [{'valor': 'anti_horario', 'texto': taa.SENTIDOS['anti_horario']}]
        # o sentido velho no pedido continua recusado: o briefing diz o outro
        _c, v = _pedir(s, biscoito, ['giro'], sentidos={'giro': 'horario'})
        assert v['situacao'] == 'parou' and v['motivo'] == 'sentido_recusado', v
        _c, v = _pedir(s, biscoito, ['giro'], sentidos={'giro': 'anti_horario'})
        assert v['situacao'] == 'feita', v
        codigo, fim = tar._confirmar(s, biscoito, v['resposta']['pedido'])
        assert fim['situacao'] == 'feita', fim
    finally:
        s.parar()
    params = contratos.ler(job / portao.ARQUIVO_PARAMETROS, portao.ESQUEMA_PARAMETROS)['formatos']['giro']
    assert params['rotacao_sentido']['valor'] == 'anti_horario'
    assert _aprovacao(job)['formatos']['giro']['parametros_encoder']['rotacao'] == {'graus': 90,
                                                                                     'sentido': 'anti_horario'}
    assert nucleo_aprovar.situacao(job)['giro']['situacao'] == 'aprovado'


# ------------------------------------------------------------------ pronto do B4
def _salvar_seletivo(job, mexer):
    """O salvar seletivo do A6 (briefing.salvar) sem a tela: a impressao de cada formato com o briefing novo contra a
    gravada, o briefing gravado e a derivacao so dos que mudaram. Devolve os afetados. (A derivacao em memoria do
    salvar, salvar._mudancas, marca os tres formatos como devolvidos neste job de teste, cujas familias vem do briefing
    de teste e nao da confirmacao da tela; a comparacao da impressao e o criterio que o salvar usa depois dela.)"""
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    mexer(b)
    gravadas = {f: contratos.ler(job / nd.PASTA / ('%s.json' % f), nd.ESQUEMA) for f in IDS}
    afetados = [f for f, d in gravadas.items() if nd.impressao_de_agora(job, d, b) != d['impressao_formato']]
    tcp._mexer_briefing(job, mexer)
    nd.derivar(job, so=afetados)
    return afetados


def test_aprovar_f1_e_f2_mudar_funcao_so_de_f1_e_reabrir(job):
    s = tar._servidor(job).iniciar()
    try:
        biscoito = tts._entrar(s)
        assert _aprovar(s, biscoito, DOIS)['situacao'] == 'feita'
    finally:
        s.parar()
    antes = _aprovacao(job)
    shas = {f: arquivos.sha256_arquivo(job / nd.PASTA / ('%s.json' % f)) for f in IDS}
    # o salvar seletivo do A6: so perto tem a camada, e so perto e regravado
    afetados = _salvar_seletivo(job, lambda b: next(
        x for x in b['funcoes'] if x['layer_id'] == tcp._ids(job)['texto-apoio']).update(
        funcao=ap.decisao('informacao_de_evento')))
    assert afetados == ['perto']
    assert {f for f in IDS if arquivos.sha256_arquivo(job / nd.PASTA / ('%s.json' % f)) != shas[f]} == {'perto'}
    assert _aprovacao(job) == antes  # o arquivo da aprovacao nao muda: a queda e medida, nunca gravada
    # reabrir: a tela nova mostra f1 com a aprovacao caida e o motivo, e f2 aprovado
    s = tar._servidor(job).iniciar()
    try:
        biscoito = tts._entrar(s)
        estado = tar.ttt._json(tts._pedir(s, '/api/estado', cookie=biscoito))
    finally:
        s.parar()
    ap_ = estado['aprovacoes']
    assert ap_['perto']['situacao'] == 'caiu' and ap_['perto']['campos'] == ['impressao_formato']
    assert ap_['perto']['motivos'] == [nucleo_aprovar.MOTIVOS_DA_QUEDA['impressao_formato']]
    assert ap_['mesma'] == dict(ap_['mesma'], situacao='aprovado', campos=[], motivos=[])
    assert ap_['giro']['situacao'] == 'sem_aprovacao'
    # a medida da critica: as aprovacoes dos outros ficam pelas diferencas do registro, sem o portao com aprovacao
    b = mb.ler(job)
    for fid, caiu in (('perto', True), ('mesma', False)):
        atual = portao.hashes_do_formato(job, fid, portao.impressao_do_formato(job, b, fid))
        campos = aprovacao.diferencas(antes['formatos'][fid], antes['job_id'], atual)
        assert bool(campos) is caiu, (fid, campos)


# ------------------------------------------------------------------ o nucleo comum e a linha de comando
def test_situacao_das_aprovacoes_sem_arquivo_e_com_registro_mexido(job):
    sit = nucleo_aprovar.situacao(job)
    assert {f: v['situacao'] for f, v in sit.items()} == {f: 'sem_aprovacao' for f in IDS}
    sessao = humano.abrir_sessao_tela(teste=True)
    try:
        with nucleo.Trava(job):
            conf = nucleo_aprovar.conferir(job, ['perto'])
            d = humano.exigir_tela('aprovar', sessao, confirmado=True)
            nucleo_aprovar.confirmar(job, ['perto'], nucleo_aprovar.vista(conf), d)
    finally:
        humano.fechar_sessao_tela(sessao)
    assert nucleo_aprovar.situacao(job)['perto']['situacao'] == 'aprovado'
    arq = job / aprovacao.ARQUIVO
    dados = arquivos.ler_json(arq)
    dados['formatos']['perto']['parametros_encoder']['qualidade'] = 1
    arquivos.gravar_json_atomico(arq, dados)
    sit = nucleo_aprovar.situacao(job)['perto']
    assert sit['situacao'] == 'caiu' and 'registro_sha256' in sit['campos']
    assert nucleo_aprovar.MOTIVOS_DA_QUEDA['registro_sha256'] in sit['motivos']


def _aprovar_no_nucleo(job, formatos):
    sessao = humano.abrir_sessao_tela(teste=True)
    try:
        with nucleo.Trava(job):
            conf = nucleo_aprovar.conferir(job, formatos)
            d = humano.exigir_tela('aprovar', sessao, confirmado=True)
            nucleo_aprovar.confirmar(job, formatos, nucleo_aprovar.vista(conf), d)
    finally:
        humano.fechar_sessao_tela(sessao)


def _campos_do_portao(job, fid):
    """Os campos que o portao (com o arquivo final refeito) da como mudados desde a aprovacao do formato."""
    reg = aprovacao.ler(job)['formatos'][fid]
    agora = portao.conferir(job, [fid], origem=False, aprovacao=False)['formatos'][fid]
    return aprovacao.diferencas(reg, reg['job_id'], agora['atual'], agora['final'])


def _linha(job, fid):
    return next(f for f in te.painel_dos_formatos(job)['formatos'] if f['id'] == fid)


def test_situacao_cai_quando_um_ajuste_do_arquivo_final_muda_como_no_portao(job):
    """Revisao do M7b, fase B: a condicao do teto muda em parametros/entrega.json depois da aprovacao. O portao derruba
    a aprovacao por parametros_encoder.teto, e o painel diz o mesmo, sem refazer o arquivo final."""
    from desdobra.entrega import parametros
    _aprovar_no_nucleo(job, ['mesma'])
    assert nucleo_aprovar.situacao(job)['mesma']['situacao'] == 'aprovado' and not _campos_do_portao(job, 'mesma')
    sessao = humano.abrir_sessao_tela(teste=True)
    try:
        with nucleo.Trava(job):
            dp = humano.exigir_tela('parametros-entrega', sessao, confirmado=True)
            parametros.gravar(job, 'mesma', {'condicao': 'hospedado'}, [], disparo=dp)
    finally:
        humano.fechar_sessao_tela(sessao)
    campos = _campos_do_portao(job, 'mesma')
    assert campos == ['parametros_encoder.teto'], campos
    sit = nucleo_aprovar.situacao(job)['mesma']
    assert sit['situacao'] == 'caiu' and sit['campos'] == campos
    assert sit['motivos'] == [nucleo_aprovar.MOTIVOS_DA_QUEDA['parametros_encoder']]
    linha = _linha(job, 'mesma')
    assert linha['situacao'] == 'aprovacao_caida' and linha['pode_aprovar'] is True


def test_situacao_cai_quando_a_versao_do_encoder_muda_como_no_portao(job, monkeypatch):
    _aprovar_no_nucleo(job, ['perto'])
    real = codificar.versoes
    monkeypatch.setattr(codificar, 'versoes', lambda: dict(real(), pillow='0.0.0'))
    campos = _campos_do_portao(job, 'perto')
    assert 'parametros_encoder.versoes' in campos, campos
    sit = nucleo_aprovar.situacao(job)['perto']
    assert sit['situacao'] == 'caiu' and 'parametros_encoder.versoes' in sit['campos']


@pytest.mark.parametrize('fid, limite, mudar, campo', [
    ('mesma', 'entrega.png_nivel_compressao', lambda v: int(v) - 1, 'nivel_png'),
    ('perto', 'entrega.jpeg_buffer_bytes', lambda v: int(v) + 1, 'buffer_bytes'),
    ('perto', 'entrega.jpeg_optimize', lambda v: 'nao' if v == 'sim' else 'sim', 'optimize'),
    ('perto', 'entrega.jpeg_progressivo', lambda v: 'nao' if v == 'sim' else 'sim', 'progressivo'),
])
def test_situacao_cai_quando_um_limite_do_encoder_do_tipo_aprovado_muda_como_no_portao(job, monkeypatch, fid, limite,
                                                                                         mudar, campo):
    """Segunda revisao do M7b, fase B: os parametros do tipo aprovado que vem dos limites do pacote (o nivel do png; a
    subamostragem, o progressivo, o optimize e o buffer do jpg) tambem nao dependem do master, e o portao os compara.
    perto sai em jpg e mesma em png no job sintetico."""
    _aprovar_no_nucleo(job, [fid])
    assert _linha(job, fid)['situacao'] == 'aprovado'
    real = codificar.limites.valor
    monkeypatch.setattr(codificar.limites, 'valor', lambda i: mudar(real(i)) if i == limite else real(i))
    assert 'parametros_encoder.%s' % campo in _campos_do_portao(job, fid)
    sit = nucleo_aprovar.situacao(job)[fid]
    assert sit['situacao'] == 'caiu' and sit['campos'] == ['parametros_encoder.%s' % campo], sit
    # o outro tipo nao entra: o limite do png nao derruba o jpg aprovado, nem o do jpg o png
    outro = 'perto' if fid == 'mesma' else 'mesma'
    _aprovar_no_nucleo(job, [outro])
    assert nucleo_aprovar.situacao(job)[outro]['situacao'] == 'aprovado'


def test_sentido_do_modo_de_teste_num_job_do_da_e_pedido_de_novo_e_trocado_na_confirmacao(job, monkeypatch):
    """Segunda revisao do M7b, fase B: o sentido do giro gravado pela janela do modo de teste num job que passou a ter
    decisao do DA nunca chega a entrega (portao.confirmacao_de_teste). O painel mostra a aprovacao do formato girado como
    caida, com o motivo, a janela pede o lado do giro de novo e a mesma confirmacao troca o sentido gravado."""
    from desdobra.tela import servidor as ts
    s = tar._servidor(job).iniciar()
    try:
        assert _aprovar(s, tts._entrar(s), ['giro'], sentidos={'giro': 'horario'})['situacao'] == 'feita'
    finally:
        s.parar()
    assert portao.confirmacao_de_teste(job) == 'confirmacao_de_fixture_de_teste'
    assert _linha(job, 'giro')['situacao'] == 'aprovado'  # o job sintetico: o modo de teste vale
    # a janela do modo de teste abre antes (ela recusa o job do DA so na abertura); o job passa a ser do DA depois
    s = tar._servidor(job).iniciar()
    monkeypatch.setattr(ts, '_job_do_da', lambda pasta: True)
    try:
        # o sentido de teste: o portao da entrega ainda recusa o job, e o painel diz que a aprovacao caiu
        params = portao.parametros_de_entrega(job)
        assert params['giro']['rotacao_sentido']['confirmado_por']['origem'] == humano.ORIGEM_FIXTURE
        sit = nucleo_aprovar.situacao(job, aceita_teste=False)['giro']
        assert sit['situacao'] == 'caiu' and 'sentido_de_teste' in sit['campos'], sit
        linha = _linha(job, 'giro')
        assert linha['situacao'] == 'aprovacao_caida' and linha['pode_aprovar'] is True
        assert nucleo_aprovar.MOTIVOS_DA_QUEDA['sentido_de_teste'] in linha['motivo']
        # a janela pede o lado do giro de novo, sem dialogo
        b = tts._entrar(s)
        _c, v = _pedir(s, b, ['giro'])
        assert v['situacao'] == 'parou' and v['motivo'] == taa.MOTIVO_SEM_SENTIDO, v
        assert [x['id'] for x in v['resposta']['sem_sentido']] == ['giro']
        # o lado pedido serve, e a mesma confirmacao troca o sentido gravado (aqui, de novo pelo meio de teste)
        fim = _aprovar(s, b, ['giro'], sentidos={'giro': 'anti_horario'})
        assert fim['situacao'] == 'feita', fim
    finally:
        s.parar()
    assert portao.parametros_de_entrega(job)['giro']['rotacao_sentido']['valor'] == 'anti_horario'
    # com o sentido gravado pela tela do DA, a aprovacao volta a valer no painel
    gravado = portao.parametros_de_entrega(job)
    monkeypatch.setattr(portao, 'parametros_de_entrega', lambda pasta: {
        f: {k: dict(c, confirmado_por=dict(c['confirmado_por'], meio=humano.MEIO_TELA, origem=humano.ORIGEM_DA))
            for k, c in campos.items()} for f, campos in gravado.items()})
    assert 'sentido_de_teste' not in nucleo_aprovar.situacao(job, aceita_teste=False)['giro']['campos']


def test_aprovacao_do_modo_de_teste_num_job_do_da_aparece_caida_e_pode_ser_refeita(job, monkeypatch):
    """Revisao do M7b, fase B: um registro de aprovacao do modo de teste num job com decisao do DA nunca chega a
    entrega. O painel o mostra como aprovacao caida, com o motivo, e a caixa para aprovar de novo fica livre."""
    from desdobra.tela import servidor as ts
    _aprovar_no_nucleo(job, ['perto'])
    assert _linha(job, 'perto')['situacao'] == 'aprovado'  # o job sintetico: o modo de teste vale
    monkeypatch.setattr(ts, '_job_do_da', lambda pasta: True)
    linha = _linha(job, 'perto')
    assert linha['situacao'] == 'aprovacao_caida' and linha['pode_aprovar'] is True
    assert linha['motivo'].startswith(nucleo_aprovar.MOTIVOS_DA_QUEDA['aprovacao_de_teste'])
    assert nucleo_aprovar.situacao(job, aceita_teste=False)['perto']['campos'] == ['aprovacao_de_teste']


def test_linha_de_comando_da_trezion_aprova_pelo_mesmo_nucleo(job, pessoa, monkeypatch):
    from desdobra import entrega
    chamadas = []
    for nome in ('conferir', 'confirmar'):
        original = getattr(nucleo_aprovar, nome)
        monkeypatch.setattr(nucleo_aprovar, nome,
                            (lambda o, n: lambda *a, **k: chamadas.append(n) or o(*a, **k))(original, nome))
    monkeypatch.setattr(humano, 'ler', lambda pergunta: 'sim')
    r = entrega._aprovar(Namespace(job=str(job), formato=list(DOIS)))
    assert r.codigo == 0, r.linhas_humanas
    # o conferir antes da pergunta e o de dentro do confirmar, com a trava de novo
    assert chamadas == ['conferir', 'confirmar', 'conferir']
    reg = _aprovacao(job)['formatos']['perto']
    assert (reg['aprovado_por']['meio'], reg['aprovado_por']['origem']) == ('terminal', 'da')
    # a aprovacao do terminal do DA passa pelo portao da entrega (a origem do briefing de teste fica de fora aqui)
    conf = portao.conferir(job, DOIS, origem=False, aprovacao=True)
    assert all(not item['falhas'] for item in conf['formatos'].values()), conf
    assert _eventos(job, 'aprovacao_gravada')[-1]['meio'] == 'terminal'


def test_textos_do_ato_de_aprovar_para_o_da():
    textos = list(taa.SENTIDOS.values()) + list(taa.SENTIDOS_NO_TEXTO.values()) + \
        list(nucleo_aprovar.MOTIVOS_DA_QUEDA.values()) + list(tt.TEXTOS_POR_TAREFA['aprovar'].values()) + \
        [tt.TEXTOS_POR_MOTIVO[m] for m in ('formato_com_falha', 'falta_sentido', 'sentido_recusado',
                                            'mudou_durante_a_confirmacao')] + \
        [taa.texto_da_confirmacao([{'nome': '400x240', 'sentido': None}, {'nome': '320x640', 'sentido': 'horario'}])]
    for texto in textos:
        # a Trezion pode aparecer no texto de quando algo deu errado (como nos outros textos da tarefa); comando nunca
        for proibido in [p for p in PROIBIDOS if p != 'Trezion'] + ['não é', 'não são']:
            assert proibido not in texto, (proibido, texto)
    assert all('Trezion' not in t for t in list(taa.SENTIDOS.values()) + list(nucleo_aprovar.MOTIVOS_DA_QUEDA.values()))
    um = taa.texto_da_confirmacao([{'nome': '400x240', 'sentido': None}])
    assert um.startswith('O arquivo final do formato 400x240 fica aprovado.')
    varios = taa.texto_da_confirmacao([{'nome': '400x240', 'sentido': None}, {'nome': '320x640', 'sentido': 'horario'}])
    assert varios.startswith('Os arquivos finais dos formatos 400x240 e 320x640 ficam aprovados.')
    assert 'O formato 320x640 vai para o veículo girado %s.' % taa.SENTIDOS_NO_TEXTO['horario'] in varios
