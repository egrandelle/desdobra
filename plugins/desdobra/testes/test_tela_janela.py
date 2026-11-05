# -*- coding: utf-8 -*-
"""M7a1: Chromium com janela da tela, perfil dsd-tela- com dono, varredura de orfaos e fecho confirmado.

Decisoes-v1.md n 20, 156 e 158; proposta do M7, secao 3 (linhas Lancamento, Perfil e Varredura com a tela aberta) e
fatia a1. Tudo e sintetico: a pagina servida e um paragrafo fixo, sem fonte nem arquivo de cliente.

Os testes de perfil e de dono rodam sem navegador. Os dois testes com janela abrem o Chromium com janela de verdade
num processo filho (a amarra do Job Object vale para o processo inteiro, e o pytest nao deve ficar amarrado): um fecha
o navegador como o usuario fecharia a janela, o outro mata o Python do filho e confere que o Chromium morre junto e que
a proxima varredura apaga a pasta orfa.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from desdobra import chromium, limites
from desdobra.chromium import navegador, processos

ESPERA_MORTE_S = 30  # teto do teste para o Chromium morrer depois do Python


@pytest.fixture
def temp_curta():
    """Pasta curta na pasta temporaria do sistema, no lugar dela nos testes (a do pytest passa de 220 caracteres)."""
    pasta = Path(tempfile.mkdtemp(prefix='dsdt-'))
    yield pasta
    shutil.rmtree(pasta, ignore_errors=True)


def _python_que_dorme():
    return subprocess.Popen([sys.executable, '-I', '-c', 'import sys; sys.stdin.readline()'], stdin=subprocess.PIPE)


def _perfil_com_dono(pasta, nome, pid, inicio):
    p = pasta / (navegador.PREFIXO_PERFIL_TELA + nome)
    p.mkdir()
    (p / navegador.NOME_DONO).write_text(json.dumps({'esquema': navegador.ESQUEMA_DONO, 'pid': pid, 'inicio': inicio}),
                                         encoding='utf-8')
    (p / 'Default').mkdir()
    (p / 'Default' / 'Cookies').write_bytes(b'x' * 64)
    return p


# ------------------------------------------------------------------ perfil e dono, sem navegador
def test_perfil_da_tela_nasce_com_prefixo_e_dono_e_some_no_fecho(temp_curta):
    perfil = navegador.perfil_tela(temp_curta)
    assert perfil.parent == temp_curta and perfil.name.startswith(navegador.PREFIXO_PERFIL_TELA)
    dono = navegador.dono_do_perfil(perfil)
    assert dono['pid'] == os.getpid() and dono['inicio'] == processos.identidade(os.getpid())
    assert not navegador.perfil_orfao(perfil)
    # nenhuma pasta de nascimento sobra
    assert [p.name for p in temp_curta.iterdir()] == [perfil.name]
    (perfil / 'Default' / 'Cache').mkdir(parents=True)
    (perfil / 'Default' / 'Cache' / 'f_000001').write_bytes(b'y' * 128)
    os.chmod(perfil / 'Default' / 'Cache' / 'f_000001', 0o444)  # numero-neutro: so leitura, o fecho tem de apagar
    assert navegador.apagar_perfil(perfil) is True and not perfil.exists()


def test_perfil_da_tela_recusa_caminho_longo(tmp_path):
    longa = tmp_path / ('x' * 120) / ('y' * 60)  # numero-neutro: so para passar do teto
    longa.mkdir(parents=True)
    teto = limites.valor('chromium.perfil_caracteres_max')
    assert len(str(longa)) > teto - len(navegador.PREFIXO_PERFIL_TELA)
    with pytest.raises(navegador.ErroNavegador):
        navegador.perfil_tela(longa)
    assert list(longa.iterdir()) == []


def test_apagar_perfil_tenta_de_novo_e_confirma(temp_curta, monkeypatch):
    perfil = navegador.perfil_tela(temp_curta)
    real = shutil.rmtree
    falhas = {'n': 2}

    def rmtree_que_falha(caminho, *a, **k):
        assert not k.get('ignore_errors'), 'o fecho nao pode ignorar erro'
        if falhas['n']:
            falhas['n'] -= 1
            raise PermissionError('arquivo em uso')
        return real(caminho, *a, **k)

    monkeypatch.setattr(navegador.shutil, 'rmtree', rmtree_que_falha)
    monkeypatch.setattr(navegador.time, 'sleep', lambda s: None)
    assert navegador.apagar_perfil(perfil) is True and not perfil.exists() and falhas['n'] == 0


def test_apagar_perfil_devolve_falso_quando_a_pasta_fica(temp_curta, monkeypatch):
    perfil = navegador.perfil_tela(temp_curta)
    chamadas = []

    def sempre_falha(caminho, *a, **k):
        chamadas.append(caminho)
        raise PermissionError('arquivo em uso')

    monkeypatch.setattr(navegador.shutil, 'rmtree', sempre_falha)
    monkeypatch.setattr(navegador.time, 'sleep', lambda s: None)
    assert navegador.apagar_perfil(perfil) is False and perfil.exists()
    assert len(chamadas) == limites.valor('chromium.apagar_perfil_tentativas')


def test_varredura_apaga_so_a_pasta_de_dono_morto(temp_curta):
    vivo = _python_que_dorme()
    morto = subprocess.Popen([sys.executable, '-I', '-c', 'pass'])
    inicio_morto = processos.identidade(morto.pid)
    morto.wait()
    try:
        # segunda tela aberta noutro job: o dono esta vivo, a pasta fica
        outra = _perfil_com_dono(temp_curta, 'outrojob', vivo.pid, processos.identidade(vivo.pid))
        # dono morto: a pasta e orfa e sai
        orfa = _perfil_com_dono(temp_curta, 'orfa', morto.pid, inicio_morto)
        # PID reaproveitado pelo sistema: o PID vive, mas o processo e outro (inicio diferente)
        reaproveitado = _perfil_com_dono(temp_curta, 'reapr', vivo.pid, (processos.identidade(vivo.pid) or 0) + 1)
        # sem dono legivel: nao e uma tela nascendo (o dono e gravado antes do nome final), entao e orfa
        sem_dono = temp_curta / (navegador.PREFIXO_PERFIL_TELA + 'semdono')
        sem_dono.mkdir()
        # pasta de outro uso do motor (prefixo dsd- sem tela): nunca e tocada
        render = temp_curta / 'dsd-render0'
        render.mkdir()
        r = navegador.varrer_orfaos(temp_curta)
        assert outra.is_dir() and render.is_dir()
        assert not orfa.exists() and not reaproveitado.exists() and not sem_dono.exists()
        assert r == {'removidas': 3, 'nao_removidas': 0, 'mantidas': 1}
    finally:
        vivo.stdin.close()
        vivo.wait()


def test_varredura_do_perfil_falha_com_arquivo_ilegivel(temp_curta, monkeypatch):
    perfil = navegador.perfil_tela(temp_curta)
    (perfil / 'Default').mkdir()
    (perfil / 'Default' / 'Preferences').write_bytes(b'{}')
    trancado = perfil / 'Default' / 'Cookies'
    trancado.write_bytes(b'z' * 32)
    controle = b'controle-positivo-sintetico'
    (perfil / 'Default' / 'cache-controle').write_bytes(b'cabecalho ' + controle)
    limpo = navegador.varrer_perfil(perfil, [b'fonte-sintetica' * 40], controle)
    assert limpo['arquivos_ilegiveis'] == 0 and navegador.varredura_limpa(limpo)
    real = Path.read_bytes

    def ler(self):
        if self.name == 'Cookies':
            raise PermissionError('em uso')
        return real(self)

    monkeypatch.setattr(Path, 'read_bytes', ler)
    r = navegador.varrer_perfil(perfil, [b'fonte-sintetica' * 40], controle)
    assert r['arquivos_ilegiveis'] == 1 and r['copias_encontradas'] == 0 and r['controle_encontrado']
    assert not navegador.varredura_limpa(r)
    monkeypatch.setattr(Path, 'read_bytes', real)
    # sem o controle positivo a varredura tambem nao prova nada
    (perfil / 'Default' / 'cache-controle').unlink()
    assert not navegador.varredura_limpa(navegador.varrer_perfil(perfil, [b'fonte-sintetica' * 40], controle))
    assert navegador.apagar_perfil(perfil)


def test_argumentos_da_janela():
    for a in ('--no-proxy-server', '--disable-breakpad', '--disable-extensions'):
        assert a in navegador.ARGUMENTOS_JANELA
    assert any(a.startswith('--host-resolver-rules=') for a in navegador.ARGUMENTOS_JANELA)
    assert not any(a.startswith('http') for a in navegador.ARGUMENTOS_JANELA)
    assert navegador.OPCOES_JANELA == {'headless': False, 'no_viewport': True, 'accept_downloads': False,
                                       'service_workers': 'block'}


# ------------------------------------------------------------------ Chromium com janela de verdade (processo filho)
FILHO_JANELA = r'''
import json, os, sys
from desdobra.chromium import navegador, processos, servidor
pasta, modo = sys.argv[1], sys.argv[2]
perfil = navegador.perfil_tela(pasta)
pagina = '<!doctype html><html><head><title>t</title></head><body><p id="x">tela sintetica</p></body></html>'
with servidor.ServidorFontes(pagina, {}) as srv:
    with navegador.Janela(perfil) as j:
        pg = j.ir(srv.url_entrada)
        chrome = [p for p, nome in processos.descendentes(os.getpid()) if nome.lower().startswith('chrome')]
        print(json.dumps({'perfil': str(perfil), 'chrome': chrome, 'versao': j.versao, 'texto': pg.inner_text('#x'),
                          'amarrado': processos.amarrado(), 'pid': os.getpid(), 'token': srv.token,
                          'no_job': [processos.amarrado(p) for p in chrome],
                          'dono': navegador.dono_do_perfil(perfil)}), flush=True)
        sys.stdin.readline()  # o teste confere a linha de comando do Chromium aqui (ou mata este processo)
        if modo == 'usuario':
            j.ctx.new_cdp_session(pg).send('Browser.close')  # como o usuario fechando a janela
            j.esperar_fechar()
    print(json.dumps({'perfil_apagado': j.perfil_apagado, 'existe': os.path.exists(str(perfil))}), flush=True)
'''


def _pasta_com_janela():
    revisao, _v = chromium.revisao_fixada(navegador=chromium.NAVEGADOR_JANELA)
    candidatas = [chromium.pasta_navegadores(),
                  Path.home() / '.claude' / 'plugins' / 'data' / 'desdobra-desdobra' / chromium.PASTA_NAVEGADORES,
                  chromium.pasta_padrao_do_playwright()]
    for c in candidatas:
        if c is not None and chromium.executavel_fixado(c, revisao, navegador=chromium.NAVEGADOR_JANELA):
            return c
    return None


def _filho(pasta_temp, modo):
    navegadores = _pasta_com_janela()
    if navegadores is None:
        pytest.skip('Chromium com janela fixado ausente nesta maquina')
    if sys.platform != 'win32':
        pytest.skip('a amarra do Chromium ao processo so existe no Windows')
    env = dict(os.environ, **{chromium.VARIAVEL_NAVEGADORES: str(navegadores)})
    return subprocess.Popen([sys.executable, '-c', FILHO_JANELA, str(pasta_temp), modo], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)


def _linhas_de_comando(pids):
    """Linha de comando de cada processo (Win32_Process), so para o teste conferir que a URL nao vai nela."""
    lista = ','.join(str(int(p)) for p in pids)
    script = ('Get-CimInstance Win32_Process | Where-Object { @(%s) -contains $_.ProcessId } | '
              'ForEach-Object { $_.CommandLine }' % lista)
    r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script], capture_output=True,
                       stdin=subprocess.DEVNULL, timeout=float(limites.valor('chromium.tempo_max_s')))
    return r.stdout.decode('utf-8', 'replace')


def _morreram(pids, teto_s):
    fim = time.monotonic() + teto_s
    while time.monotonic() < fim:
        if all(processos.identidade(p) is None for p in pids):
            return True
        time.sleep(0.2)  # numero-neutro: intervalo do teste
    return False


def test_janela_de_verdade_fecha_pelo_usuario_e_o_perfil_some(temp_curta):
    proc = _filho(temp_curta, 'usuario')
    try:
        linha = proc.stdout.readline()
        assert linha.startswith(b'{'), proc.stderr.read().decode('utf-8', 'replace')[-2000:] if proc.poll() else linha
        aberta = json.loads(linha)
        # a URL de entrada (com o token) vai so por page.goto: nenhuma linha de comando do Chromium a tem
        comandos = _linhas_de_comando(aberta['chrome'])
        assert '--user-data-dir' in comandos and aberta['token'] not in comandos and '/entrar/' not in comandos
        assert '--no-proxy-server' in comandos and '--disable-breakpad' in comandos
        saida, erro = proc.communicate(b'\n', timeout=float(limites.valor('chromium.tempo_max_s')))
    finally:
        if proc.poll() is None:
            proc.kill()
    assert proc.returncode == 0, erro.decode('utf-8', 'replace')[-2000:]
    fechada = [json.loads(x) for x in saida.decode('utf-8').splitlines() if x.startswith('{')][-1]
    assert aberta['texto'] == 'tela sintetica' and aberta['amarrado'] is True and aberta['chrome']
    assert all(aberta['no_job'])
    assert aberta['versao'] and aberta['versao'].startswith(chromium.revisao_fixada(navegador=chromium.NAVEGADOR_JANELA)[1])
    assert aberta['dono']['pid'] == aberta['pid']
    assert fechada == {'perfil_apagado': True, 'existe': False}
    assert _morreram(aberta['chrome'], ESPERA_MORTE_S)
    assert list(temp_curta.iterdir()) == []


def test_chromium_nao_sobrevive_ao_python_morto_e_a_varredura_apaga_a_orfa(temp_curta):
    proc = _filho(temp_curta, 'esperar')
    try:
        linha = proc.stdout.readline()
        assert linha.startswith(b'{'), proc.stderr.read().decode('utf-8', 'replace')[-2000:] if proc.poll() else linha
        aberta = json.loads(linha)
        assert aberta['chrome'] and aberta['amarrado'] is True and all(aberta['no_job'])
        perfil = Path(aberta['perfil'])
        assert perfil.is_dir() and not navegador.perfil_orfao(perfil)
        # mata o Python de verdade (o sys.executable do venv pode ser um lancador que roda o Python num filho)
        os.kill(aberta['pid'], signal.SIGTERM)  # no Windows e TerminateProcess: o Python nao fecha nada
        proc.wait(timeout=ESPERA_MORTE_S)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    assert _morreram(aberta['chrome'], ESPERA_MORTE_S), 'o Chromium sobreviveu ao Python morto'
    assert perfil.is_dir() and navegador.perfil_orfao(perfil)
    r = navegador.varrer_orfaos(temp_curta)
    assert r['removidas'] == 1 and r['nao_removidas'] == 0 and not perfil.exists()


# ------------------------------------------------------------------ doctor
def _browsers_falso(pasta, revisao='9001', versao='147.0.1.2'):
    arq = pasta / 'browsers.json'
    arq.write_text(json.dumps({'browsers': [{'name': 'chromium', 'revision': revisao, 'browserVersion': versao},
                                            {'name': 'chromium-headless-shell', 'revision': revisao,
                                             'browserVersion': versao}]}), encoding='utf-8')
    return arq


def _instalar_falso(navegadores, revisao='9001', versao='147.0.1.2'):
    pasta_exe, nome_exe = chromium.EXECUTAVEL_JANELA[sys.platform]
    raiz = navegadores / ('chromium-%s' % revisao)
    (raiz / pasta_exe).mkdir(parents=True)
    (raiz / chromium.MARCA_INSTALADO).write_bytes(b'')
    exe = raiz / pasta_exe / nome_exe
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_bytes(b'')
    (raiz / pasta_exe / ('%s.manifest' % versao)).write_text('<assembly/>', encoding='utf-8')
    return raiz


def test_doctor_confere_o_chromium_com_janela(tmp_path):
    from desdobra.doctor import chromium as vc
    arq = _browsers_falso(tmp_path)
    navegadores = tmp_path / 'ms-playwright'
    v = vc.verificar_chromium_janela(navegadores, arq)
    assert v.id == 'chromium_janela' and v.situacao == 'aviso' and 'aval' in v.o_que_fazer  # download opcional
    raiz = _instalar_falso(navegadores)
    v = vc.verificar_chromium_janela(navegadores, arq)
    assert v.situacao == 'ok', v.detalhe
    assert '9001' in v.detalhe and '147.0.1.2' in v.detalhe
    if sys.platform == 'win32':
        # a versao gravada no pacote do navegador tem de ser a que o Playwright pede
        pasta_exe = chromium.EXECUTAVEL_JANELA['win32'][0]
        (raiz / pasta_exe / '147.0.1.2.manifest').rename(raiz / pasta_exe / '146.0.0.0.manifest')
        v = vc.verificar_chromium_janela(navegadores, arq)
        assert v.situacao == 'falha' and '146.0.0.0' in v.detalhe


def test_doctor_confere_o_chromium_com_janela_instalado_de_verdade():
    from desdobra.doctor import chromium as vc
    pasta = _pasta_com_janela()
    if pasta is None:
        pytest.skip('Chromium com janela fixado ausente nesta maquina')
    v = vc.verificar_chromium_janela(pasta)
    assert v.situacao == 'ok', v.detalhe


def test_doctor_apaga_perfil_orfao_da_tela_e_avisa(temp_curta):
    from desdobra.doctor import chromium as vc
    assert vc.verificar_perfis_da_tela(temp_curta).situacao == 'ok'
    morto = subprocess.Popen([sys.executable, '-I', '-c', 'pass'])
    inicio = processos.identidade(morto.pid)
    morto.wait()
    orfa = _perfil_com_dono(temp_curta, 'orfa', morto.pid, inicio)
    vivo = navegador.perfil_tela(temp_curta)
    v = vc.verificar_perfis_da_tela(temp_curta)
    assert v.situacao == 'aviso' and v.numeros == {'removidas': 1, 'nao_removidas': 0, 'mantidas': 1}
    assert not orfa.exists() and vivo.is_dir() and v.o_que_fazer
    assert str(temp_curta) not in v.detalhe
    assert navegador.apagar_perfil(vivo)


def test_doctor_registra_as_checagens_da_tela():
    from desdobra import doctor
    lista, _sem = doctor.rodar_verificacoes('c', None, com_isolador=False, com_chromium=False)
    ids = [x.id for x in lista]
    assert 'chromium_janela' in ids and 'perfis_da_tela' in ids
