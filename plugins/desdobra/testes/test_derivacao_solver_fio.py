# -*- coding: utf-8 -*-
"""O HiGHS do scipy (1.18.1, HiGHS 1.12.0, Windows) so pode rodar num fio que vive o processo inteiro.

O HiGHS guarda um executor por fio do sistema que o chama (thread_local) e cria 5 fios de trabalho para ele. Quando o
fio que chamou termina, o HiGHS desmonta esse executor num callback TLS, com o loader lock do Windows preso; sob carga,
um fio de trabalho fica girando nesse callback (pause; espera um ponteiro que nunca chega) a 100% de um nucleo, e
nenhum fio do processo consegue mais nascer nem terminar. Na tela, cada pedido HTTP roda num fio novo
(ThreadingHTTPServer): o Salvar e seguir deriva num fio que termina, o pedido seguinte trava no Thread.start do
serve_forever e o parar trava no shutdown. As vezes o mesmo desmonte acaba em access violation.

Por isso o solver.resolver manda todo programa linear para um unico fio dedicado, que nao termina. Os testes daqui
conferem isso direto (deterministico) e no efeito (fios curtos em sequencia, num processo filho com teto de tempo,
para que a falha apareca como erro e nao como um pytest girando para sempre)."""
import os
import subprocess
import sys
import textwrap
import threading

from conftest import PASTA_MOTOR
from desdobra.derivacao import solver as ms

TETO_FILHO_S = 120
CICLOS = 1500
JUNTOS = 4


def _lp_pequeno():
    return ms._linprog([1.0, 1.0], [[-1.0, -2.0]], [-2.0], [], [], [(0, None), (0, None)])


def test_o_highs_roda_sempre_no_mesmo_fio_que_nao_termina(monkeypatch):
    import scipy.optimize
    real = scipy.optimize.linprog
    fios = []

    def anotado(*a, **k):
        fios.append(threading.get_ident())
        return real(*a, **k)

    monkeypatch.setattr(scipy.optimize, 'linprog', anotado)
    assert _lp_pequeno().status == 0
    curtos = []

    def num_fio_curto():
        curtos.append(threading.get_ident())
        assert _lp_pequeno().status == 0

    for _ in range(3):
        t = threading.Thread(target=num_fio_curto, daemon=True)
        t.start()
        t.join(timeout=30)
        assert not t.is_alive()
    assert len(fios) == 4
    assert len(set(fios)) == 1, 'o HiGHS rodou em mais de um fio: %r' % fios
    assert fios[0] not in curtos and fios[0] != threading.main_thread().ident
    vivos = {t.ident: t for t in threading.enumerate()}
    assert fios[0] in vivos and vivos[fios[0]].is_alive()


def test_o_erro_do_highs_volta_para_quem_chamou(monkeypatch):
    import scipy.optimize

    def quebra(*a, **k):
        raise ValueError('quebrou')

    monkeypatch.setattr(scipy.optimize, 'linprog', quebra)
    try:
        _lp_pequeno()
    except ValueError as e:
        assert str(e) == 'quebrou'
    else:
        raise AssertionError('o erro do linprog sumiu')
    monkeypatch.undo()
    assert _lp_pequeno().status == 0


def test_fios_curtos_que_resolvem_nao_travam_nem_derrubam_o_processo():
    """O padrao da tela, isolado: fio principal resolve, fio curto resolve duas vezes e termina, em sequencia. Sem o fio
    dedicado, isto (com 4 fios curtos juntos por ciclo) girava ou caia (access violation) em poucos segundos; o filho tem teto e e morto se passar."""
    roteiro = textwrap.dedent('''
        import faulthandler, sys, threading
        faulthandler.enable()
        from desdobra.derivacao import solver as ms

        def lp():
            r = ms._linprog([1.0, 1.0], [[-1.0, -2.0]], [-2.0], [], [], [(0, None), (0, None)])
            assert r.status == 0

        def curto():
            lp()
            lp()

        for i in range(%d):
            lp()
            fios = [threading.Thread(target=curto, daemon=True) for _ in range(%d)]
            for t in fios:
                t.start()
            for t in fios:
                t.join(timeout=30)
            if any(t.is_alive() for t in fios):
                print('preso no ciclo', i)
                sys.stdout.flush()
                import os
                os._exit(3)
        print('ok')
    ''' % (CICLOS, JUNTOS))
    env = dict(os.environ, PYTHONPATH=str(PASTA_MOTOR) + os.pathsep + os.environ.get('PYTHONPATH', ''))
    try:
        r = subprocess.run([sys.executable, '-c', roteiro], capture_output=True, text=True, timeout=TETO_FILHO_S,
                           env=env)
    except subprocess.TimeoutExpired:
        raise AssertionError('o processo filho travou (HiGHS em fio curto) e foi morto depois de %d s' % TETO_FILHO_S)
    assert r.returncode == 0 and r.stdout.strip().endswith('ok'), (r.returncode, r.stdout[-500:], r.stderr[-2000:])


def test_parar_com_o_serve_forever_preso_vira_erro_e_nao_trava(monkeypatch):
    """O shutdown() do socketserver espera sem teto; com o serve_forever preso (o Thread.start que nao voltava), o
    parar da tela travava o processo. Agora espera tela.parar_max_s e levanta erro."""
    import socket
    import time

    import pytest

    import test_tela_servidor as tts
    from desdobra import limites
    from desdobra.tela import servidor as ts

    real = limites.valor
    monkeypatch.setattr(limites, 'valor', lambda i: 1 if i == 'tela.parar_max_s' else real(i))
    chegou, solta = threading.Event(), threading.Event()

    def preso(self, request, client_address):
        chegou.set()
        solta.wait(60)
        self.shutdown_request(request)

    monkeypatch.setattr(ts._ServidorExclusivo, 'process_request', preso)
    s = ts.ServidorTela(tts._conteudo()).iniciar()
    c = socket.create_connection(('127.0.0.1', s.porta), timeout=10)
    try:
        assert chegou.wait(10)
        t0 = time.monotonic()
        with pytest.raises(RuntimeError, match='não parou'):
            s.parar()
        assert time.monotonic() - t0 < 10
    finally:
        solta.set()
        c.close()


def test_parar_normal_continua_rapido():
    import time

    import test_tela_servidor as tts
    from desdobra.tela import servidor as ts

    s = ts.ServidorTela(tts._conteudo()).iniciar()
    tts._pedir(s, '/api/saude')
    t0 = time.monotonic()
    s.parar()
    assert time.monotonic() - t0 < 5
    assert s._srv is None
