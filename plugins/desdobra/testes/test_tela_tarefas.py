# -*- coding: utf-8 -*-
"""M7b, B1: tarefas longas em segundo plano no servidor da tela (desdobra.tela.tarefas).

Criterios de pronto cobertos aqui (plano do M7b, passo B1, e a critica dele; decisoes do Duda Q3, Q4 e Q14):
  - o ato longo confirmado na janela responde 202 com o id da tarefa, e /api/tarefa/<id> diz a etapa e o formato;
  - /api/estado e o rascunho respondem durante uma tarefa de 60 s simulada, e a tela mostra o trabalho em andamento
    com a edicao bloqueada, no lugar do aviso de job ocupado;
  - a tarefa segura a trava do job e o marcador de render em andamento do inicio ao fim, num fio de trabalho unico que
    nunca termina (o mesmo cuidado do fio do HiGHS, n 172);
  - cancelar corta o formato em andamento entre etapas; os prontos ficam;
  - fechar a janela no meio para em ordem, com parada.json no formato cortado e o aviso na reabertura; a parada tem
    teto (tela.parar_max_s) mesmo quando a tarefa nao responde;
  - na abertura seguinte o motor tira a trava velha do processo morto, sem pedir nada ao DA;
  - o render (desdobra.render.execucao) diz a etapa e para entre etapas sem gravar master;
  - a janela da tela e um Chromium sem janela num segundo fio rodam no mesmo processo.
Tudo sintetico: atos de teste com o meio de teste e o PSD sintetico do render.
"""
import json
import os
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

import test_tela_escrita as tte
import test_tela_servidor as tts
from desdobra import arquivos, humano, limites
from desdobra.job import nucleo
from desdobra.tela import servidor as ts
from desdobra.tela import tarefas as tt

FORMATOS = ('f1', 'f2')
ESPERA_S = 30  # teto do teste para cada espera de estado da tarefa


@pytest.fixture
def job(tmp_path):
    j = tmp_path / 'job'
    (j / 'laudo').mkdir(parents=True)
    (j / 'laudo' / 'laudo.json').write_text('{"laudo": "sintetico"}', encoding='utf-8')
    (j / 'estado.json').write_text('{}', encoding='utf-8')
    return j


class Fake:
    """O ato longo de teste: um formato por vez, cada um esperando o teste liberar, o parar ou os 60 s."""

    def __init__(self, ignora_parar=False):
        self.liberar = {f: threading.Event() for f in FORMATOS}
        self.disparos = []
        self.fios = []
        self.ignora_parar = ignora_parar

    def executar(self, disparo, dados, tarefa):
        humano.conferir(disparo, 'render', consumir=True)
        self.disparos.append(disparo)
        self.fios.append(threading.current_thread().ident)
        for f in FORMATOS:
            if tarefa.parar():
                break
            tarefa.progresso('pilhas', f)
            fim = time.monotonic() + 60  # numero-neutro: a tarefa de 60 s simulada do plano
            while not self.liberar[f].is_set() and time.monotonic() < fim:
                if tarefa.parar() and not self.ignora_parar:
                    return {'parou_em': f}
                time.sleep(0.01)  # numero-neutro: intervalo do teste
            tarefa.feito(f)
        return {'feito': True}

    def ato(self):
        return ts.Ato(comando='render', titulo='Renderizar os formatos', texto='Os formatos vão para o render.',
                      sim='Confirmar', nao='Cancelar', executar=self.executar, longo=True,
                      formatos=lambda _d: list(FORMATOS))


def _conteudo(job, contas):
    c = tts._conteudo()

    def atualizar():
        # como estado.montar: sem a trava do job, o passo 3 nao se monta
        contas['atualizar'] += 1
        if (job / nucleo.ARQUIVO_TRAVA).exists():
            e = RuntimeError('ocupado')
            e.motivo = 'job_ocupado'
            raise e
        return None

    def recarregar():
        contas['recarregar'] += 1
        return dict(c['estado'], recarregado=contas['recarregar'])

    c['atualizar'] = atualizar
    c['recarregar'] = recarregar
    c['editar'] = lambda dados, origem: {'previa': True}
    return c


@pytest.fixture
def contas():
    return {'atualizar': 0, 'recarregar': 0}


@pytest.fixture
def fake():
    f = Fake()
    yield f
    for ev in f.liberar.values():
        ev.set()


@pytest.fixture
def srv(job, fake, contas):
    s = ts.ServidorTela(_conteudo(job, contas), pasta=job, modo_teste=True, atos={'render': fake.ato()}).iniciar()
    yield s
    for ev in fake.liberar.values():
        ev.set()
    s.parar()


def _json(resposta):
    return json.loads(resposta[2]) if resposta[0] == 200 else None


def _confirmar(s, biscoito):
    codigo, p = tte._pedir_ato(s, biscoito, nome='render')
    assert codigo == 200, codigo
    return tte._escrever(s, '/api/ato/confirmar', {'pedido': p['pedido'], 'resposta': 'confirmar'}, cookie=biscoito)


def _tarefa(s, biscoito, ident):
    return _json(tts._pedir(s, '/api/tarefa/%s' % ident, cookie=biscoito))


def _esperar(condicao, teto_s=ESPERA_S):
    fim = time.monotonic() + teto_s
    while time.monotonic() < fim:
        v = condicao()
        if v:
            return v
        time.sleep(0.02)  # numero-neutro: intervalo do teste
    raise AssertionError('a condicao nao chegou em %s s' % teto_s)


def _iniciar(s, biscoito):
    codigo, _cab, corpo = _confirmar(s, biscoito)
    assert codigo == 202, codigo
    ident = json.loads(corpo)['tarefa']
    _esperar(lambda: (_tarefa(s, biscoito, ident) or {}).get('formato') == 'f1')
    return ident


# ------------------------------------------------------------------ o ato longo e a rota da tarefa
def test_ato_longo_responde_202_e_a_rota_da_tarefa_diz_etapa_e_formato(srv, fake):
    biscoito = tts._entrar(srv)
    codigo, cab, corpo = _confirmar(srv, biscoito)
    assert codigo == 202 and cab['cache-control'] == ['no-store']
    ident = json.loads(corpo)['tarefa']
    assert tt.ID_TAREFA.match(ident)
    v = _esperar(lambda: (lambda x: x if x and x['formato'] == 'f1' else None)(_tarefa(srv, biscoito, ident)))
    assert v['situacao'] == 'rodando' and v['etapa'] == 'pilhas' and v['formatos'] == list(FORMATOS)
    assert v['feitos'] == [] and v['faltam'] == list(FORMATOS) and v['etapa_texto'] and v['texto']
    fake.liberar['f1'].set()
    fake.liberar['f2'].set()
    v = _esperar(lambda: (lambda x: x if x['situacao'] == 'feita' else None)(_tarefa(srv, biscoito, ident)))
    assert v['feitos'] == list(FORMATOS) and v['faltam'] == [] and v['resposta'] == {'feito': True}
    # um Disparo, de teste, gasto pela tarefa
    assert len(fake.disparos) == 1 and fake.disparos[0].meio == humano.MEIO_MEDICAO
    with pytest.raises(humano.ErroHumano):
        humano.conferir(fake.disparos[0], 'render')
    assert srv.contagem['ato_confirmar'] == 1 and srv.contagem['tarefa'] >= 2


def test_estado_e_rascunho_respondem_durante_a_tarefa_e_a_edicao_fica_bloqueada(srv, fake, contas):
    biscoito = tts._entrar(srv)
    ident = _iniciar(srv, biscoito)
    montagens = contas['atualizar']  # o pedir e o confirmar do ato montam a tela antes da tarefa
    tempos = []
    for _ in range(20):  # numero-neutro: pedidos do teste
        t0 = time.perf_counter()
        codigo, _cab, corpo = tts._pedir(srv, '/api/estado', cookie=biscoito)
        tempos.append(time.perf_counter() - t0)
        assert codigo == 200
    estado = json.loads(corpo)
    # o trabalho em andamento no lugar do aviso de job ocupado: o passo 3 nem tenta se montar com a trava presa
    assert 'aviso_atualizacao' not in estado and contas['atualizar'] == montagens
    assert estado['edicao_bloqueada'] is True and estado['tarefa']['id'] == ident
    assert estado['tarefa']['situacao'] == 'rodando'
    assert statistics.median(tempos) < 0.2 and max(tempos) < 1.0  # numero-neutro: meta do plano (secao 4)
    # o rascunho responde e grava
    assert tts._pedir(srv, '/api/rascunho', cookie=biscoito)[0] == 200
    assert tte._escrever(srv, '/api/rascunho', tte._rascunho(srv), cookie=biscoito)[0] == 200
    # a edicao e os outros atos ficam bloqueados ate o fim
    antes = srv.contagem['tarefa_em_andamento']
    assert tte._escrever(srv, '/api/familia/previa', {'familia': 'x'}, cookie=biscoito)[0] == 403
    assert tte._pedir_ato(srv, biscoito, nome='render')[0] == 403
    assert srv.contagem['tarefa_em_andamento'] == antes + 2
    fake.liberar['f1'].set()
    fake.liberar['f2'].set()
    _esperar(lambda: _tarefa(srv, biscoito, ident)['situacao'] == 'feita')
    estado = _json(tts._pedir(srv, '/api/estado', cookie=biscoito))
    # depois da tarefa, a tela se monta de novo uma vez (recarregar) e volta a se atualizar
    assert estado['edicao_bloqueada'] is False and estado['tarefa']['situacao'] == 'feita'
    assert contas['recarregar'] == 1 and estado['recarregado'] == 1 and contas['atualizar'] == montagens + 1
    assert tte._escrever(srv, '/api/familia/previa', {'familia': 'x'}, cookie=biscoito)[0] == 200


def test_tarefa_segura_a_trava_e_o_marcador_no_fio_unico(srv, job, fake):
    biscoito = tts._entrar(srv)
    ident = _iniciar(srv, biscoito)
    trava = job / nucleo.ARQUIVO_TRAVA
    assert trava.read_text(encoding='ascii').strip() == str(os.getpid())
    with pytest.raises(nucleo.ErroJob):
        with nucleo.Trava(job):
            pass
    m = arquivos.ler_json(job / tt.ARQUIVO_MARCADOR)
    assert m['esquema'] == tt.ESQUEMA_MARCADOR and m['situacao'] == 'rodando' and m['pid'] == os.getpid()
    assert m['formatos'] == list(FORMATOS) and m['feitos'] == [] and ident not in json.dumps(m)
    fake.liberar['f1'].set()
    fake.liberar['f2'].set()
    _esperar(lambda: _tarefa(srv, biscoito, ident)['situacao'] == 'feita')
    _esperar(lambda: not trava.exists())
    assert not (job / tt.ARQUIVO_MARCADOR).exists()
    # a segunda tarefa roda no mesmo fio, que segue vivo
    for ev in fake.liberar.values():
        ev.clear()
    ident2 = _iniciar(srv, biscoito)
    assert ident2 != ident
    for ev in fake.liberar.values():
        ev.set()
    _esperar(lambda: _tarefa(srv, biscoito, ident2)['situacao'] == 'feita')
    assert len(set(fake.fios)) == 1 and fake.fios[0] != threading.get_ident()
    fio = next(f for f in threading.enumerate() if f.ident == fake.fios[0])
    assert fio.is_alive() and fio.daemon


def test_job_ocupado_recusa_o_ato_longo_e_gasta_o_disparo(srv, job, fake):
    biscoito = tts._entrar(srv)
    (job / nucleo.ARQUIVO_TRAVA).write_text('1', encoding='ascii')  # outro comando do desdobra no job
    codigo, p = tte._pedir_ato(srv, biscoito, nome='render')
    assert codigo == 200
    assert tte._escrever(srv, '/api/ato/confirmar', {'pedido': p['pedido'], 'resposta': 'confirmar'},
                         cookie=biscoito)[0] == 403
    assert fake.disparos == [] and srv.tarefas.ultima is None
    assert not (job / tt.ARQUIVO_MARCADOR).exists()
    assert (job / nucleo.ARQUIVO_TRAVA).read_text(encoding='ascii') == '1'


def test_uma_tarefa_por_vez(job):
    fila = tt.Tarefas(job)
    solta = threading.Event()
    t = fila.iniciar('teste', lambda tarefa: solta.wait(ESPERA_S), formatos=['f1'])
    try:
        with pytest.raises(tt.ErroTarefa):
            fila.iniciar('teste', lambda tarefa: None)
    finally:
        solta.set()
    assert t.terminou(ESPERA_S) and t.situacao == 'feita'
    assert not fila.ocupada


def test_erro_da_tarefa_vira_parou_com_texto_sem_comando(job):
    from desdobra.render import execucao
    fila = tt.Tarefas(job)

    def quebra(tarefa):
        tarefa.progresso('texto', 'f1')
        raise execucao.ErroRender('O CDP não confirmou a face.', 'face_cdp_nao_confere',
                                  o_que_fazer='Rode "desdobra doctor".')
    t = fila.iniciar('render', quebra, formatos=['f1'])
    assert t.terminou(ESPERA_S)
    v = t.vista()
    assert v['situacao'] == 'parou' and v['motivo'] == 'face_cdp_nao_confere' and v['faltam'] == ['f1']
    assert 'desdobra' not in json.dumps(v, ensure_ascii=False) and 'Rode' not in v['texto']
    assert not (job / nucleo.ARQUIVO_TRAVA).exists() and not (job / tt.ARQUIVO_MARCADOR).exists()


# ------------------------------------------------------------------ cancelar
def test_cancelar_corta_o_formato_em_andamento_e_os_prontos_ficam(srv, job, fake):
    biscoito = tts._entrar(srv)
    ident = _iniciar(srv, biscoito)
    fake.liberar['f1'].set()
    _esperar(lambda: _tarefa(srv, biscoito, ident)['formato'] == 'f2')
    codigo, _cab, resto = tte._escrever(srv, '/api/tarefa/cancelar', {'tarefa': ident}, cookie=biscoito)
    assert codigo == 204 and resto == b''
    v = _esperar(lambda: (lambda x: x if x['situacao'] != 'rodando' else None)(_tarefa(srv, biscoito, ident)))
    assert v['situacao'] == 'cancelada' and v['feitos'] == ['f1'] and v['faltam'] == ['f2']
    assert v['resposta'] == {'parou_em': 'f2'}
    # o DA viu o cancelamento na tela: nada de aviso para a proxima abertura
    _esperar(lambda: not (job / nucleo.ARQUIVO_TRAVA).exists())
    assert not (job / tt.ARQUIVO_MARCADOR).exists()
    assert srv.contagem['tarefa_cancelar'] == 1


@pytest.mark.parametrize('caso', ['sem_csrf', 'origin_de_fora', 'site_de_fora', 'texto'])
def test_cancelar_passa_pelas_conferencias_da_escrita(srv, fake, caso):
    biscoito = tts._entrar(srv)
    ident = _iniciar(srv, biscoito)
    kw = dict(tte.RECUSAS[caso])
    corpo = kw.pop('corpo', None)
    codigo = tte._escrever(srv, '/api/tarefa/cancelar', {'tarefa': ident}, cookie=biscoito, corpo=corpo, **kw)[0]
    assert codigo in (403, 404)
    assert _tarefa(srv, biscoito, ident)['situacao'] == 'rodando'


def test_cancelar_tarefa_errada_e_recusado(srv, fake):
    biscoito = tts._entrar(srv)
    ident = _iniciar(srv, biscoito)
    for dados in ({'tarefa': '0' * 32}, {'tarefa': ident, 'x': 1}, {'tarefa': 1}, {}):
        assert tte._escrever(srv, '/api/tarefa/cancelar', dados, cookie=biscoito)[0] == 403, dados
    assert _tarefa(srv, biscoito, ident)['situacao'] == 'rodando'


# ------------------------------------------------------------------ a rota da tarefa
def test_rota_da_tarefa_recusa_id_errado_sem_cookie_e_post(srv, fake):
    biscoito = tts._entrar(srv)
    ident = _iniciar(srv, biscoito)
    codigo, cab, _corpo = tts._pedir(srv, '/api/tarefa/%s' % ident, cookie=biscoito)
    assert codigo == 200 and cab['cache-control'] == ['no-store'] and cab['x-frame-options'] == ['DENY']
    assert cab['content-type'] == [ts.MIME_JSON]
    for rota in ('/api/tarefa/%s' % ('0' * 32), '/api/tarefa/%s' % ident.upper(), '/api/tarefa/%s/' % ident,
                 '/api/tarefa/../estado', '/api/tarefa/x.ttf', '/api/tarefa/%s.json' % ident, '/api/tarefa/',
                 '/api/tarefa', '/api/tarefa/cancelar', '/api/tarefa/%s?x=1' % ident):
        assert tts._pedir(srv, rota, cookie=biscoito)[0] == 404, rota
    assert tts._pedir(srv, '/api/tarefa/%s' % ident)[0] == 404
    assert tte._escrever(srv, '/api/tarefa/%s' % ident, {}, cookie=biscoito)[0] == 404


def test_servidor_so_de_leitura_nao_tem_tarefa():
    s = ts.ServidorTela(tts._conteudo()).iniciar()
    try:
        biscoito = tts._entrar(s)
        assert s.tarefas is None
        assert tts._pedir(s, '/api/tarefa/%s' % ('0' * 32), cookie=biscoito)[0] == 404
        estado = _json(tts._pedir(s, '/api/estado', cookie=biscoito))
        assert 'tarefa' not in estado and 'render_inacabado' not in estado
    finally:
        s.parar()


# ------------------------------------------------------------------ fechar a janela no meio
def test_fechar_a_janela_no_meio_para_em_ordem_com_parada_e_aviso(job, contas):
    f = Fake()
    s = ts.ServidorTela(_conteudo(job, contas), pasta=job, modo_teste=True, atos={'render': f.ato()}).iniciar()
    biscoito = tts._entrar(s)
    ident = _iniciar(s, biscoito)
    f.liberar['f1'].set()
    _esperar(lambda: _tarefa(s, biscoito, ident)['formato'] == 'f2')
    t0 = time.perf_counter()
    s.parar()
    assert time.perf_counter() - t0 < float(limites.valor('tela.parar_max_s'))
    t = s.tarefas.obter(ident)
    assert t.situacao == 'cancelada'
    # o formato cortado tem parada.json; o pronto nao
    parada = arquivos.ler_json(job / 'render' / 'f2' / 'parada.json')
    assert parada['motivo'] == 'janela_fechada' and parada['formato'] == 'f2'
    assert not (job / 'render' / 'f1' / 'parada.json').exists()
    assert not (job / nucleo.ARQUIVO_TRAVA).exists()
    m = arquivos.ler_json(job / tt.ARQUIVO_MARCADOR)
    assert m['situacao'] == 'parada' and m['feitos'] == ['f1'] and m['formatos'] == list(FORMATOS)
    # a reabertura: o aviso vem do marcador, que sai
    aviso = tt.recuperar(job)
    assert aviso['formatos'] == ['f2'] and aviso['texto'] == tt.AVISO_INACABADO
    assert not (job / tt.ARQUIVO_MARCADOR).exists() and tt.recuperar(job) is None
    eventos = [json.loads(x) for x in (job / 'log' / 'eventos.jsonl').read_text(encoding='utf-8').splitlines()]
    assert any(e['evento'] == 'render_inacabado' and e['formatos'] == 1 for e in eventos)


def test_parada_tem_teto_quando_a_tarefa_nao_responde(job, contas, monkeypatch):
    f = Fake(ignora_parar=True)
    s = ts.ServidorTela(_conteudo(job, contas), pasta=job, modo_teste=True, atos={'render': f.ato()}).iniciar()
    biscoito = tts._entrar(s)
    ident = _iniciar(s, biscoito)
    real = limites.valor
    monkeypatch.setattr(limites, 'valor', lambda i: 0.3 if i == 'tela.parar_max_s' else real(i))
    try:
        t0 = time.perf_counter()
        s.parar()
        assert time.perf_counter() - t0 < 5  # numero-neutro: teto do teste, bem acima de duas vezes 0,3 s
        assert arquivos.ler_json(job / 'render' / 'f1' / 'parada.json')['motivo'] == 'janela_fechada'
        m = arquivos.ler_json(job / tt.ARQUIVO_MARCADOR)
        assert m['situacao'] == 'parada' and m['feitos'] == []
        # a tarefa presa segue com a trava: no processo de verdade ela morre com ele
        assert (job / nucleo.ARQUIVO_TRAVA).exists() and s.tarefas.obter(ident).situacao == 'rodando'
    finally:
        for ev in f.liberar.values():
            ev.set()
    assert s.tarefas.obter(ident).terminou(ESPERA_S)
    _esperar(lambda: not (job / nucleo.ARQUIVO_TRAVA).exists())
    assert arquivos.ler_json(job / tt.ARQUIVO_MARCADOR)['situacao'] == 'parada'


# ------------------------------------------------------------------ o fim que a tela diz (revisao do M7b, fase B)
def test_cancelar_depois_que_todos_os_formatos_ficaram_prontos_termina_feita(job):
    """O Cancelar chega na gravacao do ultimo formato: a funcao termina tudo, e a tela nao diz que um formato ficou
    pela metade."""
    fila = tt.Tarefas(job)
    pediu = threading.Event()

    def tudo(tarefa):
        for f in FORMATOS:
            tarefa.progresso('gravacao', f)
            if f == FORMATOS[-1]:
                fila.cancelar(tarefa.id)
                pediu.set()
            tarefa.feito(f)
        return {'feitos': list(FORMATOS)}
    t = fila.iniciar('render', tudo, formatos=list(FORMATOS))
    assert t.terminou(ESPERA_S) and pediu.is_set() and t.parar()
    v = t.vista()
    assert v['situacao'] == 'feita' and v['faltam'] == [] and v['texto'] == tt.TEXTOS_POR_TAREFA['render']['feita']


def test_cancelar_com_formato_por_fazer_continua_cancelada(job):
    fila = tt.Tarefas(job)

    def corta(tarefa):
        tarefa.feito(FORMATOS[0])
        fila.cancelar(tarefa.id)
        return {'feitos': [FORMATOS[0]]}
    t = fila.iniciar('render', corta, formatos=list(FORMATOS))
    assert t.terminou(ESPERA_S) and t.vista()['situacao'] == 'cancelada'
    # o preparo de um pedido (sem formatos) cancelado continua cancelado: o dialogo nao abre
    p = fila.iniciar(tt.TAREFA_PREPARO, lambda tarefa: fila.cancelar(tarefa.id) and None, marcador=False)
    assert p.terminou(ESPERA_S) and p.vista()['situacao'] == 'cancelada'


def test_janela_fechada_com_a_tarefa_que_termina_tudo_tira_o_marcador(job):
    """A janela fecha, e a tarefa ainda termina todos os formatos dentro do teto: nada fica para avisar."""
    fila = tt.Tarefas(job)
    comecou = threading.Event()

    def ignora(tarefa):
        comecou.set()
        _esperar(tarefa.parar)
        for f in FORMATOS:
            tarefa.progresso('gravacao', f)
            tarefa.feito(f)
        return {'feitos': list(FORMATOS)}
    t = fila.iniciar('render', ignora, formatos=list(FORMATOS))
    assert comecou.wait(ESPERA_S)
    assert fila.fechar(ESPERA_S) is True
    assert t.situacao == 'feita'
    assert not (job / tt.ARQUIVO_MARCADOR).exists() and tt.recuperar(job) is None
    assert not any((job / 'render' / f / 'parada.json').exists() for f in FORMATOS)


def test_marcador_parado_com_todos_os_formatos_prontos_nao_avisa(job):
    pid, inicio = _pid_morto()
    _marcador(job, pid, inicio, situacao='parada', feitos=FORMATOS)
    assert tt.recuperar(job) is None
    assert not (job / tt.ARQUIVO_MARCADOR).exists()


def test_aprovacao_cortada_pela_janela_avisa_a_aprovacao_e_nao_grava_parada_de_render(job):
    """A tarefa de aprovar cortada pela janela: o aviso da reabertura fala da aprovacao, e nenhum formato ganha a
    parada do render (os masters seguem em dia)."""
    from desdobra.render import execucao
    fila = tt.Tarefas(job)
    comecou = threading.Event()

    def aprovar(tarefa):
        tarefa.progresso('portao', FORMATOS[0])
        comecou.set()
        _esperar(tarefa.parar)
        raise execucao.ErroRender('parado', tt.MOTIVO_PARADO)
    t = fila.iniciar('aprovar', aprovar, formatos=list(FORMATOS))
    assert comecou.wait(ESPERA_S)
    assert fila.fechar(ESPERA_S) is True
    assert t.situacao == 'cancelada'
    assert not any((job / 'render' / f / 'parada.json').exists() for f in FORMATOS)
    m = arquivos.ler_json(job / tt.ARQUIVO_MARCADOR)
    assert m['tarefa'] == 'aprovar' and m['situacao'] == 'parada'
    aviso = tt.recuperar(job)
    assert aviso['texto'] == tt.AVISOS_INACABADO['aprovar'] and aviso['formatos'] == list(FORMATOS)
    assert 'render' not in aviso['texto']


# ------------------------------------------------------------------ a reabertura
def _pid_morto():
    p = subprocess.Popen([sys.executable, '-I', '-c', 'pass'])
    from desdobra.chromium import processos
    inicio = processos.identidade(p.pid)
    p.wait()
    return p.pid, inicio


def _marcador(job, pid, inicio, situacao='rodando', feitos=()):
    (job / tt.ARQUIVO_MARCADOR).parent.mkdir(parents=True, exist_ok=True)
    arquivos.gravar_json_atomico(job / tt.ARQUIVO_MARCADOR, {
        'esquema': tt.ESQUEMA_MARCADOR, 'tarefa': 'render', 'pid': pid, 'inicio': inicio,
        'quando': '2026-11-09T10:00:00-03:00', 'formatos': list(FORMATOS), 'feitos': list(feitos),
        'situacao': situacao})


def test_reabertura_tira_a_trava_velha_do_processo_morto(job):
    pid, inicio = _pid_morto()
    _marcador(job, pid, inicio, feitos=['f1'])
    (job / nucleo.ARQUIVO_TRAVA).write_text(str(pid), encoding='ascii')
    aviso = tt.recuperar(job)
    assert aviso == {'texto': tt.AVISO_INACABADO, 'formatos': ['f2'], 'quando': '2026-11-09T10:00:00-03:00'}
    assert not (job / nucleo.ARQUIVO_TRAVA).exists() and not (job / tt.ARQUIVO_MARCADOR).exists()
    with nucleo.Trava(job):
        pass


def test_reabertura_nao_mexe_na_trava_de_outro_processo(job):
    pid, inicio = _pid_morto()
    _marcador(job, pid, inicio)
    (job / nucleo.ARQUIVO_TRAVA).write_text(str(pid + 1), encoding='ascii')  # numero-neutro: outro PID
    assert tt.recuperar(job)['formatos'] == list(FORMATOS)
    assert (job / nucleo.ARQUIVO_TRAVA).read_text(encoding='ascii') == str(pid + 1)


def test_reabertura_com_a_outra_tela_ainda_renderizando_nao_mexe_em_nada(job):
    vivo = subprocess.Popen([sys.executable, '-I', '-c', 'import sys; sys.stdin.readline()'], stdin=subprocess.PIPE)
    try:
        from desdobra.chromium import processos
        _marcador(job, vivo.pid, processos.identidade(vivo.pid))
        (job / nucleo.ARQUIVO_TRAVA).write_text(str(vivo.pid), encoding='ascii')
        assert tt.recuperar(job) is None
        assert (job / nucleo.ARQUIVO_TRAVA).exists() and (job / tt.ARQUIVO_MARCADOR).exists()
    finally:
        vivo.stdin.close()
        vivo.wait()


def test_reabertura_com_marcador_ilegivel_avisa_e_nao_mexe_na_trava(job):
    (job / tt.ARQUIVO_MARCADOR).parent.mkdir(parents=True)
    (job / tt.ARQUIVO_MARCADOR).write_text('{"esquema": ', encoding='utf-8')
    (job / nucleo.ARQUIVO_TRAVA).write_text('1', encoding='ascii')
    assert tt.recuperar(job) == {'texto': tt.AVISO_INACABADO, 'formatos': [], 'quando': None}
    assert (job / nucleo.ARQUIVO_TRAVA).exists() and not (job / tt.ARQUIVO_MARCADOR).exists()


@pytest.mark.parametrize('campos', [{'pid': 2 ** 40}, {'pid': -5}, {'pid': True}, {'inicio': 'x'},  # numero-neutro: PIDs fora do DWORD
                                    {'situacao': 'outra'}, {'formatos': 'f1'}])
def test_reabertura_com_marcador_mexido_avisa_e_nao_quebra_a_abertura(job, campos):
    _marcador(job, 1, None)
    m = dict(arquivos.ler_json(job / tt.ARQUIVO_MARCADOR), **campos)
    arquivos.gravar_json_atomico(job / tt.ARQUIVO_MARCADOR, m)
    (job / nucleo.ARQUIVO_TRAVA).write_text(str(m['pid']), encoding='ascii')
    assert tt.recuperar(job) == {'texto': tt.AVISO_INACABADO, 'formatos': [], 'quando': None}
    assert (job / nucleo.ARQUIVO_TRAVA).exists() and not (job / tt.ARQUIVO_MARCADOR).exists()


def test_aviso_de_render_inacabado_vai_no_estado(job, contas):
    c = _conteudo(job, contas)
    c['render_inacabado'] = {'texto': tt.AVISO_INACABADO, 'formatos': ['f2'], 'quando': None}
    s = ts.ServidorTela(c, pasta=job, modo_teste=True).iniciar()
    try:
        estado = _json(tts._pedir(s, '/api/estado', cookie=tts._entrar(s)))
        assert estado['render_inacabado']['formatos'] == ['f2']
        assert estado['tarefa'] is None and estado['edicao_bloqueada'] is False
    finally:
        s.parar()


def test_processo_recupera_antes_de_montar_e_leva_o_aviso(job, monkeypatch):
    from desdobra.chromium import navegador
    from desdobra.tela import estado as te
    from desdobra.tela import processo
    pid, inicio = _pid_morto()
    _marcador(job, pid, inicio)
    (job / nucleo.ARQUIVO_TRAVA).write_text(str(pid), encoding='ascii')
    visto = {}

    def montar(pasta, teto=None):
        visto['trava_na_montagem'] = (Path(pasta) / nucleo.ARQUIVO_TRAVA).exists()
        return {'estado': {'job_id': 'x'}, 'previas': {}, 'fontes': {}}

    class Parou(Exception):
        pass

    def servidor(conteudo, **_k):
        visto['conteudo'] = conteudo
        raise Parou()

    monkeypatch.setattr(navegador, 'varrer_orfaos', lambda: {'removidas': 0, 'nao_removidas': 0})
    monkeypatch.setattr(te, 'montar', montar)
    monkeypatch.setattr(processo, 'opcoes_do_servidor', lambda pasta: {})
    monkeypatch.setattr(ts, 'ServidorTela', servidor)
    avisos = []
    processo.executar(job, avisar=avisos.append)
    assert visto['trava_na_montagem'] is False
    assert visto['conteudo']['render_inacabado']['formatos'] == list(FORMATOS)


# ------------------------------------------------------------------ os textos do DA
def test_textos_da_tarefa_para_o_da():
    textos = [tt.AVISO_INACABADO] + list(tt.TEXTOS.values()) + list(tt.ETAPAS.values()) + \
        list(getattr(tt, 'AVISOS_INACABADO', {}).values())
    for nome in tt.TEXTOS_POR_TAREFA:
        textos += list(tt.TEXTOS_POR_TAREFA[nome].values())
    for texto in textos:
        assert texto and '–' not in texto and '—' not in texto, texto
        for proibido in ('desdobra doctor', 'desdobra render', 'desdobra job', 'desdobra tela', 'Rode', 'rode ',
                         'terminal', 'comando', '.json', '--', 'não é', 'nao e '):
            assert proibido not in texto, (proibido, texto)


# ------------------------------------------------------------------ o render diz a etapa e para entre etapas
RENDER = pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')


@pytest.fixture(scope='module')
def job_render(tmp_path_factory):
    import test_render as trd
    import test_render_apoio as rap
    base = tmp_path_factory.mktemp('tarefa_render')
    return trd._job(base, rap.psd_render(base / 'origem' / 'kv.psd'))


@RENDER
def test_render_diz_cada_etapa_em_ordem(job_render):
    import test_render as trd
    from desdobra.render import execucao
    etapas = []
    rel = execucao.renderizar(job_render, disparo=trd._disparo(), progresso=etapas.append, parar=lambda: False)
    assert etapas == ['contrato', 'pilhas', 'texto', 'composicao', 'gravacao']
    assert (job_render / 'render' / 'origem' / 'master.png').is_file() and rel['tempo_s'] > 0


@RENDER
@pytest.mark.parametrize('antes_de', ['contrato', 'pilhas', 'gravacao'])
def test_render_parado_entre_etapas_nao_grava_master(job_render, antes_de):
    import test_render as trd
    from desdobra.render import execucao
    destino = job_render / 'render' / 'origem'
    for nome in ('master.png', 'render.json'):
        if (destino / nome).exists():
            arquivos.tornar_gravavel(destino / nome)
            (destino / nome).unlink()
    ordem = ['contrato', 'pilhas', 'texto', 'composicao', 'gravacao']
    etapas = []
    disparo = trd._disparo()
    with pytest.raises(execucao.ErroRender) as e:
        execucao.renderizar(job_render, disparo=disparo, progresso=etapas.append,
                            parar=lambda: len(etapas) == ordem.index(antes_de))
    assert e.value.motivo == 'parado' and e.value.medidas == {'etapa': antes_de}
    assert etapas == ordem[:ordem.index(antes_de)]
    assert not (destino / 'master.png').exists() and not (destino / 'render.json').exists()
    assert arquivos.ler_json(destino / 'parada.json')['motivo'] == 'parado'
    assert not (job_render / 'render' / '.trabalho').exists()
    # o selo foi gasto: o render parado nao serve de novo
    with pytest.raises(humano.ErroHumano):
        humano.conferir(disparo, 'render')


# ------------------------------------------------------------------ janela e Chromium sem janela no mesmo processo
FILHO_DOIS_FIOS = r'''
import json, os, sys, threading, time
from pathlib import Path
from desdobra.chromium import navegador, servidor
from desdobra.tela import tarefas
pasta, job = sys.argv[1], Path(sys.argv[2])
perfil = navegador.perfil_tela(pasta)
pagina = '<!doctype html><html><head><title>t</title></head><body><p id="x">tela sintetica</p></body></html>'
saida = {}
with servidor.ServidorFontes(pagina, {}) as srv:
    with navegador.Janela(perfil) as j:
        pg = j.ir(srv.url_entrada)
        fila = tarefas.Tarefas(job)

        def medir(t):
            t.progresso('texto', 'f1')
            curto = navegador.perfil_curto()
            try:
                with servidor.ServidorFontes(pagina, {}) as srv2:
                    r = navegador.conferir(srv2.url_entrada, curto, [], ['x'])
            finally:
                navegador.apagar_perfil(curto)
            t.feito('f1')
            return {'chromium': r['chromium'], 'cdp': bool(r['cdp'].get('x')), 'fio': threading.get_ident()}

        t = fila.iniciar('teste', medir, formatos=['f1'])
        lidas = 0
        while not t.terminou(0.05):
            if pg.inner_text('#x') == 'tela sintetica':
                lidas += 1
        saida = {'vista': t.vista(), 'resposta': t.resposta, 'lidas': lidas, 'principal': threading.get_ident(),
                 'janela_depois': pg.inner_text('#x')}
        j.ctx.new_cdp_session(pg).send('Browser.close')
        j.esperar_fechar()
saida['perfil_apagado'] = j.perfil_apagado
print(json.dumps(saida), flush=True)
'''


def test_janela_e_chromium_sem_janela_em_dois_fios_do_mesmo_processo(job):
    import tempfile

    import test_tela_janela as ttj
    navegadores = ttj._pasta_com_janela()
    if navegadores is None:
        pytest.skip('Chromium com janela fixado ausente nesta maquina')
    if sys.platform != 'win32':
        pytest.skip('a amarra do Chromium ao processo so existe no Windows')
    from desdobra import chromium
    pasta_temp = Path(tempfile.mkdtemp(prefix='dsdt-'))
    env = dict(os.environ, **{chromium.VARIAVEL_NAVEGADORES: str(navegadores)})
    try:
        r = subprocess.run([sys.executable, '-c', FILHO_DOIS_FIOS, str(pasta_temp), str(job)], capture_output=True,
                           env=env, timeout=4 * float(limites.valor('chromium.tempo_max_s')))  # numero-neutro: duas aberturas e folga
    finally:
        import shutil
        shutil.rmtree(pasta_temp, ignore_errors=True)
    assert r.returncode == 0, r.stderr.decode('utf-8', 'replace')[-3000:]
    saida = json.loads([x for x in r.stdout.decode('utf-8').splitlines() if x.startswith('{')][-1])
    assert saida['vista']['situacao'] == 'feita' and saida['vista']['feitos'] == ['f1']
    assert saida['resposta']['chromium'] and saida['resposta']['cdp']
    assert saida['resposta']['fio'] != saida['principal']
    assert saida['lidas'] > 0 and saida['janela_depois'] == 'tela sintetica'
    assert saida['perfil_apagado'] is True
    assert not (job / nucleo.ARQUIVO_TRAVA).exists() and not (job / tt.ARQUIVO_MARCADOR).exists()
