# -*- coding: utf-8 -*-
"""M7b, C5: o cronometro da mestre (arquitetura-v1.md, 9.8, Editor de mestre; plano do M7b, pergunta 9).

Criterios de pronto cobertos aqui:
  - por familia, o cronometro comeca no primeiro clique ou tecla com a familia aberta e para no ato "Confirmar
    familia"; o tempo ativo tira as pausas acima de tela.mestre_pausa_max_s sem clique nem tecla, e o tempo total
    vai da abertura a confirmacao; contam as edicoes e as mudancas de quebra de linha;
  - o tempo entre dois sinais vai a familia do primeiro, so enquanto o cronometro dela corre: trocar de familia, sair
    do passo 3 ou confirmar a familia nunca contam o mesmo tempo duas vezes;
  - a familia confirmada so volta a contar quando o DA mexe nela (edicao, quebra ou a confirmacao caida no rascunho);
  - medicoes/tela.json traz os dois tempos por familia e por sessao (uma sessao por janela aberta), fora do briefing;
  - o servidor da tela recebe o sinal da pagina com as mesmas conferencias de toda escrita, e o ato "Confirmar
    familia" para o cronometro;
  - na pagina: o clique e a tecla mandam o sinal (no maximo um por segundo, com o atraso do ultimo clique), e a
    edicao e a quebra mudada vao contadas.
Relogio falso nos testes do cronometro e do servidor; o job sintetico de test_tela_salvar na pagina."""
import json
import sys

import pytest

import test_tela_escrita as tte
import test_tela_salvar as tsv
import test_tela_servidor as tts
from desdobra import arquivos, contratos, limites
from desdobra.tela import cronometro as tc
from desdobra.tela import estado as te
from desdobra.tela import rascunho as tr
from desdobra.tela import servidor as ts

modelo = tsv.modelo
job = tsv.job
JOB = '0123456789abcdef' * 2  # numero-neutro: id de job sintetico, 32 digitos


class Relogio:
    """O relogio falso: o teste anda com ele."""

    def __init__(self, t=1_800_000_000.0):  # numero-neutro: um instante qualquer, em segundos
        self.t = t

    def __call__(self):
        return self.t

    def andar(self, s):
        self.t += s


@pytest.fixture
def relogio():
    return Relogio()


def _cronometro(pasta, relogio, confirmadas=(), origem='fixture_de_teste'):
    conf = set(confirmadas)
    return tc.Cronometro(pasta, JOB, origem=origem, relogio=relogio, confirmada=lambda g: g in conf)


def _lido(pasta):
    return contratos.ler(pasta / tc.ARQUIVO, tc.ESQUEMA)


def _da_sessao(pasta, gid, n=-1):
    return _lido(pasta)['sessoes'][n]['familias'][gid]


# ------------------------------------------------------------------ o cronometro, com relogio falso
def test_pausa_vem_do_registro_de_limites():
    lim = limites.obter('tela.mestre_pausa_max_s')
    assert lim.valor == 60 and lim.situacao == 'a_calibrar' and lim.efeito == 'registra'
    assert lim.fonte is not None


def test_ativo_tira_as_pausas_longas_e_o_total_vai_ate_a_confirmacao(tmp_path, relogio):
    c = _cronometro(tmp_path, relogio)
    c.sinal('vertical-1')                  # abre a familia
    relogio.andar(10)
    c.sinal('vertical-1', edicoes=1)       # 10 s ativos
    relogio.andar(20)
    c.sinal('vertical-1', quebras=2)       # 20 s ativos
    relogio.andar(100)
    c.sinal('vertical-1', edicoes=1)       # pausa acima de 60 s: nao conta
    relogio.andar(60)
    c.sinal('vertical-1')                  # 60 s em ponto: ainda conta
    relogio.andar(5)
    c.confirmar('vertical-1')              # 5 s ate o clique de confirmar
    f = _da_sessao(tmp_path, 'vertical-1')
    assert f['ativo_s'] == 95 and f['total_s'] == 195
    assert f['edicoes'] == 2 and f['quebras'] == 2
    assert f['confirmada_em'] is not None and f['aberta_em'] != f['confirmada_em']
    total = _lido(tmp_path)['familias']['vertical-1']
    assert total == {'sessoes': 1, 'confirmada_em': f['confirmada_em'], 'ativo_s': 95, 'total_s': 195,
                     'edicoes': 2, 'quebras': 2}
    assert _lido(tmp_path)['pausa_max_s'] == limites.valor('tela.mestre_pausa_max_s')


def test_pausa_um_pouco_acima_do_limite_nao_conta(tmp_path, relogio):
    c = _cronometro(tmp_path, relogio)
    c.sinal('vertical-1')
    relogio.andar(60.5)
    c.sinal('vertical-1')
    f = _da_sessao(tmp_path, 'vertical-1')
    assert f['ativo_s'] == 0 and f['total_s'] == 60.5 and f['confirmada_em'] is None


def test_o_tempo_vai_a_familia_do_sinal_anterior_sem_contar_duas_vezes(tmp_path, relogio):
    c = _cronometro(tmp_path, relogio)
    c.sinal('a')
    relogio.andar(10)
    c.sinal('b')            # os 10 s ate aqui sao de a
    relogio.andar(20)
    c.sinal('a')            # os 20 s ate aqui sao de b
    relogio.andar(10)
    c.confirmar('a')
    relogio.andar(30)
    c.sinal('b')            # os 30 s depois de confirmar a nao sao de ninguem
    relogio.andar(5)
    c.sinal(None)           # saiu do passo 3: os 5 s sao de b
    relogio.andar(5)
    c.sinal('b')            # os 5 s fora do passo 3 nao sao de ninguem
    lido = _lido(tmp_path)
    a, b = lido['sessoes'][0]['familias']['a'], lido['sessoes'][0]['familias']['b']
    assert a['ativo_s'] == 20 and a['total_s'] == 40
    assert b['ativo_s'] == 25 and b['total_s'] == 70 and b['confirmada_em'] is None
    assert lido['sessoes'][0]['ativo_s'] == 45 and lido['sessoes'][0]['total_s'] == 80


def test_familia_confirmada_so_volta_a_contar_quando_o_da_mexe(tmp_path, relogio):
    c = _cronometro(tmp_path, relogio, confirmadas={'a'})
    c.sinal('a')            # a familia ja estava confirmada no rascunho: olhar nao conta
    relogio.andar(10)
    c.sinal('a')
    assert 'a' not in _lido(tmp_path)['sessoes'][0]['familias']
    c.sinal('a', edicoes=1)  # mexeu: a confirmacao caiu, o cronometro abre aqui
    relogio.andar(10)
    c.confirmar('a')
    relogio.andar(10)
    c.sinal('a')            # olhar depois de confirmar nao conta
    relogio.andar(10)
    c.sinal('a', quebras=1)  # mudou a quebra: volta a contar, a partir daqui
    relogio.andar(10)
    c.sinal('a')
    f = _da_sessao(tmp_path, 'a')
    assert f['ativo_s'] == 20 and f['edicoes'] == 1 and f['quebras'] == 1
    # o total vai do primeiro sinal que abriu o cronometro (o da edicao), com a pausa depois da confirmacao
    assert f['confirmada_em'] is None and f['total_s'] == 40


def test_familia_que_perdeu_a_confirmacao_no_rascunho_volta_a_contar(tmp_path, relogio):
    conf = {'a'}
    c = tc.Cronometro(tmp_path, JOB, origem='fixture_de_teste', relogio=relogio, confirmada=lambda g: g in conf)
    c.sinal('a', edicoes=1)
    relogio.andar(10)
    c.confirmar('a')
    conf.discard('a')       # o passo 2 mudou e tirou a confirmacao de toda familia
    relogio.andar(10)
    c.sinal('a')
    relogio.andar(10)
    c.sinal('a')
    f = _da_sessao(tmp_path, 'a')
    # os 10 s entre a confirmacao e o sinal que reabriu nao sao da familia
    assert f['confirmada_em'] is None and f['ativo_s'] == 20 and f['total_s'] == 30


def test_atraso_poe_o_sinal_no_ultimo_clique_sem_voltar_antes_do_anterior(tmp_path, relogio):
    c = _cronometro(tmp_path, relogio)
    c.sinal('a')
    relogio.andar(1)
    c.sinal('a', atraso_s=0.75)        # o ultimo clique foi 0,25 s depois do primeiro
    f = _da_sessao(tmp_path, 'a')
    assert f['ativo_s'] == 0.25
    relogio.andar(1)
    c.sinal('a', atraso_s=30)          # um atraso maior que o tempo desde o sinal anterior para nele
    assert _da_sessao(tmp_path, 'a')['ativo_s'] == 0.25
    relogio.andar(1)
    c.sinal('a', atraso_s=-5)          # atraso negativo vale zero: conta desde o sinal parado no anterior
    assert _da_sessao(tmp_path, 'a')['ativo_s'] == 3


def test_confirmar_sem_sinal_na_sessao_registra_a_confirmacao_sem_tempo(tmp_path, relogio):
    c = _cronometro(tmp_path, relogio)
    c.confirmar('a')
    f = _da_sessao(tmp_path, 'a')
    assert f['ativo_s'] == 0 and f['total_s'] == 0 and f['confirmada_em'] is not None


def test_cada_janela_e_uma_sessao_e_as_familias_somam_as_sessoes(tmp_path, relogio):
    c = _cronometro(tmp_path, relogio)
    c.sinal('a')
    relogio.andar(30)
    c.sinal('a', edicoes=3)
    relogio.andar(1000)
    # a janela fechou com a familia aberta; a outra janela abre e confirma
    c2 = _cronometro(tmp_path, relogio)
    c2.sinal('a', quebras=1)
    relogio.andar(20)
    c2.confirmar('a')
    lido = _lido(tmp_path)
    assert len(lido['sessoes']) == 2
    s1, s2 = (s['familias']['a'] for s in lido['sessoes'])
    assert (s1['ativo_s'], s1['total_s'], s1['confirmada_em']) == (30, 30, None)
    assert (s2['ativo_s'], s2['total_s']) == (20, 20) and s2['confirmada_em'] is not None
    assert lido['familias']['a'] == {'sessoes': 2, 'confirmada_em': s2['confirmada_em'], 'ativo_s': 50,
                                     'total_s': 50, 'edicoes': 3, 'quebras': 1}
    assert lido['sessoes'][0]['origem'] == 'fixture_de_teste'


def test_duas_janelas_abertas_no_mesmo_job_guardam_as_duas_sessoes(tmp_path, relogio):
    """Revisao 2 do C: duas janelas da tela abertas ao mesmo tempo no mesmo job. Cada gravacao le o arquivo de agora
    e troca so a sessao da propria janela: nenhuma apaga o que a outra mediu."""
    c1, c2 = _cronometro(tmp_path, relogio), _cronometro(tmp_path, relogio)
    c1.sinal('a')
    relogio.andar(10)
    c2.sinal('b')
    relogio.andar(10)
    c1.sinal('a', edicoes=1)    # 20 s de a na janela 1
    relogio.andar(10)
    c2.sinal('b', edicoes=1)    # 20 s de b na janela 2
    relogio.andar(5)
    c1.confirmar('a')           # mais 15 s de a, desde o ultimo sinal da janela 1
    lido = _lido(tmp_path)
    assert len(lido['sessoes']) == 2
    assert [sorted(s['familias']) for s in lido['sessoes']] == [['a'], ['b']]
    assert {g: (f['ativo_s'], f['edicoes']) for g, f in lido['familias'].items()} == {'a': (35, 1), 'b': (20, 1)}
    # uma terceira janela, depois, so acrescenta a sessao dela
    c3 = _cronometro(tmp_path, relogio)
    c3.sinal(None)
    assert len(_lido(tmp_path)['sessoes']) == 3


def test_janela_sem_sinal_nao_grava_sessao(tmp_path, relogio):
    _cronometro(tmp_path, relogio)
    assert not (tmp_path / tc.ARQUIVO).exists()
    c = _cronometro(tmp_path, relogio)
    c.sinal(None)
    assert _lido(tmp_path)['sessoes'][0]['familias'] == {}


def test_arquivo_ilegivel_fica_guardado_ao_lado(tmp_path, relogio):
    arq = tmp_path / tc.ARQUIVO
    arq.parent.mkdir(parents=True)
    arq.write_text('{"esquema": "outro"}', encoding='utf-8')
    c = _cronometro(tmp_path, relogio)
    c.sinal('a')
    assert len(_lido(tmp_path)['sessoes']) == 1
    assert (tmp_path / tc.ARQUIVO_ILEGIVEL).read_text(encoding='utf-8') == '{"esquema": "outro"}'


def test_falha_ao_gravar_nunca_chega_ao_da(tmp_path, relogio, monkeypatch):
    c = _cronometro(tmp_path, relogio)

    def falhar(*_a, **_k):
        raise OSError('disco cheio')
    monkeypatch.setattr(tc.contratos, 'gravar', falhar)
    c.sinal('a')
    c.confirmar('a')
    assert not (tmp_path / tc.ARQUIVO).exists()


@pytest.mark.parametrize('dados', [
    None, [], {'familia': 'a', 'edicoes': 0, 'quebras': 0},
    {'familia': 'a', 'edicoes': 0, 'quebras': 0, 'atraso_ms': 0, 'extra': 1},
    {'familia': 'z', 'edicoes': 0, 'quebras': 0, 'atraso_ms': 0},
    {'familia': 7, 'edicoes': 0, 'quebras': 0, 'atraso_ms': 0},
    {'familia': 'a', 'edicoes': -1, 'quebras': 0, 'atraso_ms': 0},
    {'familia': 'a', 'edicoes': True, 'quebras': 0, 'atraso_ms': 0},
    {'familia': 'a', 'edicoes': 1.5, 'quebras': 0, 'atraso_ms': 0},
    {'familia': 'a', 'edicoes': 0, 'quebras': '1', 'atraso_ms': 0},
    {'familia': 'a', 'edicoes': 0, 'quebras': 0, 'atraso_ms': -1},
    {'familia': 'a', 'edicoes': 2 ** 40, 'quebras': 0, 'atraso_ms': 0},
])
def test_sinal_fora_do_formato_e_recusado(dados):
    assert tc.conferir_sinal(dados, {'a', 'b'}) is None


def test_sinal_no_formato():
    assert tc.conferir_sinal({'familia': 'a', 'edicoes': 2, 'quebras': 1, 'atraso_ms': 250}, {'a'}) == \
        ('a', 2, 1, 0.25)
    assert tc.conferir_sinal({'familia': None, 'edicoes': 0, 'quebras': 0, 'atraso_ms': 0}, {'a'}) == \
        (None, 0, 0, 0)


# ------------------------------------------------------------------ o servidor da tela
def _sinal(s, biscoito, familia, edicoes=0, quebras=0, atraso_ms=0, **kw):
    dados = {'familia': familia, 'edicoes': edicoes, 'quebras': quebras, 'atraso_ms': atraso_ms}
    return tte._escrever(s, '/api/medicao', dados, cookie=biscoito, **kw)[0]


def test_servidor_recebe_o_sinal_com_as_conferencias_da_escrita_e_o_ato_para_o_cronometro(job, modelo):
    from desdobra.tela import atos as ta
    conteudo = te.montar(job)
    gm = tsv._familia_de(conteudo, 'mesma')
    r = Relogio()
    s = ts.ServidorTela(conteudo, pasta=job, modo_teste=True, atos=ta.atos_do_job(job, conteudo=conteudo),
                        relogio=r).iniciar()
    try:
        biscoito = tts._entrar(s)
        # as recusas de toda escrita, sem nada gravado
        assert _sinal(s, None, gm) == 404
        assert _sinal(s, biscoito, gm, csrf=False) == 403
        assert _sinal(s, biscoito, gm, origem='https://exemplo.test') == 403
        assert _sinal(s, biscoito, gm, site='cross-site') == 403
        assert _sinal(s, biscoito, gm, tipo='text/plain') == 403
        assert _sinal(s, biscoito, 'outra-familia') == 403
        assert _sinal(s, biscoito, gm, edicoes=-1) == 403
        assert tts._pedir(s, '/api/medicao', cookie=biscoito)[0] == 404
        assert not (job / tc.ARQUIVO).exists()
        # o sinal aceito: 204, sem corpo, e nada em briefing/ nem em derivacao/
        antes = {p: arquivos.sha256_caminho(job / p) for p in ('briefing', 'derivacao')}
        codigo, cab, corpo = tte._escrever(s, '/api/medicao', {'familia': gm, 'edicoes': 0, 'quebras': 0,
                                                                'atraso_ms': 0}, cookie=biscoito)
        assert codigo == 204 and corpo == b'' and cab['cache-control'] == ['no-store']
        r.andar(12)
        assert _sinal(s, biscoito, gm, edicoes=1) == 204
        r.andar(8)
        assert _sinal(s, biscoito, gm, quebras=1) == 204
        assert {p: arquivos.sha256_caminho(job / p) for p in ('briefing', 'derivacao')} == antes
        # o ato "Confirmar familia" da janela para o cronometro
        escolhas = tsv._escolhas(conteudo)
        assert tsv._gravar_rascunho(s, biscoito, escolhas, tsv._passo_2(modelo['funcoes'])) == 200
        r.andar(5)
        f = escolhas[gm]
        assert tsv._ato(s, biscoito, 'familia', {'familia': gm, 'versao': f['versao'], 'edicoes': f['edicoes']})[1] \
            == 200
        lido = _lido(job)
        sessao = lido['sessoes'][0]['familias'][gm]
        assert sessao['ativo_s'] == 25 and sessao['total_s'] == 25
        assert (sessao['edicoes'], sessao['quebras']) == (1, 1) and sessao['confirmada_em'] is not None
        assert lido['job_id'] == s.job_id and lido['sessoes'][0]['origem'] == 'fixture_de_teste'
        # olhar a familia confirmada (o rascunho diz confirmada) nao conta mais
        r.andar(10)
        assert _sinal(s, biscoito, gm) == 204
        assert _lido(job)['sessoes'][0]['familias'][gm] == sessao
        assert s.contagem['medicao'] == 4  # numero-neutro: os quatro sinais aceitos
    finally:
        s.parar()


def test_familia_com_confirmacao_velha_conta_o_tempo_de_revisar(job, modelo):
    """Revisao do C5: a confirmacao gravada ficou velha sem o rascunho mudar (entrou um formato na familia). A tela
    mostra a familia sem confirmacao, e o cronometro segue a mesma regra (rascunho.sem_confirmacao_velha): o DA revisa
    25 s sem editar e confirma, e os 25 s contam."""
    import test_derivacao_apoio as ap
    import test_tela_familia_estavel as tfe
    from desdobra.tela import atos as ta
    conteudo = te.montar(job)
    s = tsv._servidor(job, conteudo)
    try:
        tsv._preparar_rascunho(job, modelo, s, tts._entrar(s), conteudo)
    finally:
        s.parar()
    tfe._mexer_formatos(job, lambda fs: fs.append(ap.formato('v4', 182, 320, rotacao=tfe.ROT0)))
    novo = te.montar(job)
    gv = tsv._familia_de(novo, 'v1')
    r = Relogio()
    s = ts.ServidorTela(novo, pasta=job, modo_teste=True, atos=ta.atos_do_job(job, conteudo=novo),
                        relogio=r).iniciar()
    try:
        biscoito = tts._entrar(s)
        assert tr.ler(job, s.laudo_sha256)[0]['familias'][gv]['confirmada'] is True  # o arquivo nao mudou
        assert tfe._grupo(tfe._estado_servido(s, biscoito), gv)['aviso']  # a tela pede a confirmacao de novo
        assert _sinal(s, biscoito, gv) == 204
        r.andar(10)
        assert _sinal(s, biscoito, gv) == 204
        r.andar(10)
        assert _sinal(s, biscoito, gv) == 204
        r.andar(5)
        f = tr.ler(job, s.laudo_sha256)[0]['familias'][gv]
        assert tsv._ato(s, biscoito, 'familia', {'familia': gv, 'versao': f['versao'], 'edicoes': f['edicoes']})[1] \
            == 200
        sessao = _lido(job)['sessoes'][-1]['familias'][gv]
        assert sessao['ativo_s'] == 25 and sessao['total_s'] == 25, sessao
    finally:
        s.parar()


def test_sinal_le_o_rascunho_dentro_da_trava_de_escrita(job, modelo):
    """Revisao do C5: o sinal da familia parada le o rascunho para saber se ela esta confirmada. No Windows, o arquivo
    aberto para leitura faz a troca atomica do autosave falhar; a leitura espera a trava de escrita, como as outras
    leituras do rascunho do servidor. O sinal sem leitura (fora do passo 3, ou com edicao) nao espera."""
    import threading
    conteudo = te.montar(job)
    gm = tsv._familia_de(conteudo, 'mesma')
    s = tsv._servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        tsv._preparar_rascunho(job, modelo, s, biscoito, conteudo)
        assert tr.ler(job, s.laudo_sha256)[0]['familias'][gm]['confirmada'] is True
        codigos = []
        with s._trava_escrita:
            assert _sinal(s, biscoito, None) == 204
            assert _sinal(s, biscoito, gm, edicoes=1) == 204
            fio = threading.Thread(target=lambda: codigos.append(_sinal(s, biscoito, gm)))
            fio.start()
            fio.join(0.5)  # numero-neutro: segundos de espera do teste
            esperou = fio.is_alive()
        fio.join()
        assert esperou and codigos == [204]
    finally:
        s.parar()


@pytest.mark.skipif(sys.platform != 'win32', reason='a troca atomica so falha com o arquivo aberto no Windows')
def test_sinal_nunca_derruba_o_autosave_do_rascunho(job, modelo):
    """Revisao do C5: tres fios mandam sinais da familia confirmada (cada um le o rascunho) enquanto a pagina grava
    o rascunho 150 vezes. Nenhuma gravacao falha."""
    import threading
    conteudo = te.montar(job)
    gm = tsv._familia_de(conteudo, 'mesma')
    s = tsv._servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        tsv._preparar_rascunho(job, modelo, s, biscoito, conteudo)
        corpo = tsv._vista(job)
        fim = threading.Event()
        codigos = []

        def sinais():
            while not fim.is_set():
                _sinal(s, biscoito, gm)
        fios = [threading.Thread(target=sinais) for _ in range(3)]  # numero-neutro: fios do teste
        for f in fios:
            f.start()
        try:
            for _ in range(150):  # numero-neutro: gravacoes do teste
                codigos.append(tte._escrever(s, '/api/rascunho', corpo, cookie=biscoito)[0])
        finally:
            fim.set()
            for f in fios:
                f.join()
        assert codigos == [200] * len(codigos)
    finally:
        s.parar()


def test_servidor_so_de_leitura_nao_tem_o_cronometro():
    s = ts.ServidorTela(tts._conteudo()).iniciar()
    try:
        biscoito = tts._entrar(s)
        assert s.cronometro is None
        assert _sinal(s, biscoito, 'a', csrf='x') == 404
    finally:
        s.parar()


# ------------------------------------------------------------------ a pagina
@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
def test_pagina_manda_o_sinal_e_a_confirmacao_para_o_cronometro(job, modelo):
    from playwright.sync_api import sync_playwright

    import test_quebra_na_tela as tqt
    import test_tela_edicao as ted
    import test_tela_familia_estavel as tfe
    import test_tela_galeria as tg
    import test_tela_palco as tp
    from desdobra.chromium import navegador
    from desdobra.tela import atos as ta
    conteudo = te.montar(job)
    gm = tsv._familia_de(conteudo, 'mesma')
    apoio, _lid = tsv._apoio(modelo)
    titulo = tsv._titulo(conteudo, gm)
    navegador.apontar_playwright()
    with ts.ServidorTela(conteudo, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo)) as srv, sync_playwright() as pw:
        escolhas = tsv._escolhas(conteudo)
        escolhas[gm] = {'versao': escolhas[gm]['versao'], 'confirmada': False, 'edicoes': []}
        corpo = dict({'job_id': srv.job_id, 'laudo_sha256': srv.laudo_sha256, 'familias': escolhas},
                     **tsv._passo_2(modelo['funcoes']))
        tr.gravar(job, corpo, job_id=srv.job_id, laudo_atual=srv.laudo_sha256, origem=srv.origem_rascunho)
        srv.estado = conteudo['recarregar']()
        nav, pg = tp._pagina_da_tela(pw, srv, 1600, 900)  # numero-neutro: janela do teste
        sinais = []
        pg.on('request', lambda r: sinais.append(json.loads(r.post_data)) if '/api/medicao' in r.url else None)
        try:
            pg.evaluate('() => document.querySelector("#passos [data-passo=pecas]").click()')
            tg._abrir(pg, conteudo['estado'], 'mesma')
            tp._esperar(pg, '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""')
            # duas edicoes seguidas: um sinal agora e o outro com a contagem, no fim do segundo
            ted._focar(pg, titulo)
            pg.keyboard.press('ArrowDown')
            ted._esperar_salvo(pg)
            pg.wait_for_timeout(1200)  # numero-neutro: ms, um sinal por segundo
            pg.keyboard.press('Shift+ArrowDown')
            ted._esperar_salvo(pg)
            # uma mudanca de quebra
            tqt._abrir_controle(pg, apoio)
            pg.evaluate('() => document.querySelector(\'#quebra-linhas button[data-pos="3"]\').click()')
            ted._esperar_salvo(pg)
            tp._esperar(pg, '() => document.documentElement.dataset.sinal === "enviado" ? "1" : ""')
            tfe._confirmar_na_pagina(pg, '#confirmar-familia')
        finally:
            nav.close()
    do_gm = [x for x in sinais if x['familia'] == gm]
    assert do_gm and all(set(x) == {'familia', 'edicoes', 'quebras', 'atraso_ms'} for x in sinais)
    assert sum(x['edicoes'] for x in do_gm) == 2 and sum(x['quebras'] for x in do_gm) == 1
    lido = _lido(job)
    f = lido['sessoes'][0]['familias'][gm]
    assert f['edicoes'] == 2 and f['quebras'] == 1 and f['confirmada_em'] is not None
    assert 0 < f['ativo_s'] <= f['total_s']
    assert lido['familias'][gm]['sessoes'] == 1
