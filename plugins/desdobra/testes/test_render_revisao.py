# -*- coding: utf-8 -*-
"""Defeitos achados na revisao independente do M4, um teste por defeito (escritos antes da correcao)."""
import ctypes
import hashlib
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import threading
import time
from argparse import Namespace
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import sinteticos
import test_fontes_apoio as ap
import test_render_apoio as rap
from desdobra import arquivos, contratos
from desdobra.chromium import navegador, servidor
from desdobra.job import nucleo
from desdobra.render import contrato as mc
from desdobra.render import execucao, icc, linkados, texto
from desdobra.resultado import Codigo

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')

RAIZ_PLUGIN = Path(__file__).resolve().parent.parent
VARIAVEIS_DO_CLAUDE = ('CLAUDECODE', 'CLAUDE_CODE_ENTRYPOINT', 'CLAUDE_CODE_SESSION_ID', 'CLAUDE_PID', 'AI_AGENT',
                       'TERM_PROGRAM', 'CLAUDE_AGENT_SDK_VERSION')


def _job(base, psd, campanha=None, fontes=True):
    fs = []
    if fontes:
        pasta = base / 'origem-fontes'
        ap.gravar(pasta, 'inventada.ttf', ap.fonte(ps=rap.FONTE))
        fs = [pasta]
    job = base / 'job'
    nucleo.criar(job, psd, 'c', fontes=fs, campanha=campanha)
    assert nucleo.proxima(job, todas=True).codigo == 0
    return job


def _ambiente_sem_claude():
    return {k: v for k, v in os.environ.items() if k not in VARIAVEIS_DO_CLAUDE}


# ------------------------------------------------------------------ 1. disparo humano
def test_renderizar_recusa_disparo_que_nao_veio_da_conferencia(tmp_path):
    from desdobra import humano
    job = _job(tmp_path, rap.psd_render(tmp_path / 'o' / 'kv.psd'))
    with pytest.raises((humano.ErroHumano, execucao.ErroRender)):
        execucao.renderizar(job, disparo={'meio': 'terminal', 'usuario': 'x', 'maquina': 'y', 'quando': 'z'})
    assert not (job / 'render' / 'origem' / 'master.png').exists()


def test_cli_nao_tem_atalho_que_pula_a_conferencia():
    import inspect

    from desdobra import render
    from desdobra.specs import confirmar
    for f in (render._render, render._linkado_confirmar):
        assert list(inspect.signature(f).parameters) == ['args']
    assert 'disparo' in inspect.signature(confirmar.sessao).parameters
    assert 'disparo' in inspect.signature(linkados.confirmar).parameters


def test_confirmacoes_exigem_disparo_conferido(tmp_path):
    from desdobra import humano
    from desdobra.specs import confirmar
    with pytest.raises(humano.ErroHumano):
        linkados.confirmar(tmp_path, 'u', 'entrada/campanha/x.png', disparo={'usuario': 'x', 'maquina': 'y'})
    with pytest.raises(humano.ErroHumano):
        confirmar.sessao(tmp_path, disparo=None, entrada=lambda _p: 's')


def _filho_em_console_novo(codigo, stdin=None, env=None, injetar=None, espera=1.5):
    """Roda python -c codigo num console novo (como o ataque do revisor) e, opcionalmente, injeta teclas nele."""
    p = subprocess.Popen([sys.executable, '-c', codigo], creationflags=subprocess.CREATE_NEW_CONSOLE, stdin=stdin,
                         env=env)
    if injetar is not None:
        _injetar(p.pid, injetar, espera)
    return p.wait(timeout=600)


def _injetar(pid, texto, espera):
    from ctypes import wintypes
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    time.sleep(espera)

    class KEY(ctypes.Structure):
        _fields_ = [('bKeyDown', wintypes.BOOL), ('wRepeatCount', wintypes.WORD), ('wVirtualKeyCode', wintypes.WORD),
                    ('wVirtualScanCode', wintypes.WORD), ('UnicodeChar', wintypes.WCHAR),
                    ('dwControlKeyState', wintypes.DWORD)]

    class U(ctypes.Union):
        _fields_ = [('KeyEvent', KEY), ('pad', ctypes.c_byte * 16)]

    class REC(ctypes.Structure):
        _fields_ = [('EventType', wintypes.WORD), ('Event', U)]
    k32.FreeConsole()
    if not k32.AttachConsole(pid):
        return
    k32.CreateFileW.restype = wintypes.HANDLE
    h = k32.CreateFileW('CONIN$', 0xC0000000, 3, None, 3, 0, None)
    recs = (REC * (2 * len(texto)))()
    for i, ch in enumerate(texto):
        for j, baixo in enumerate((1, 0)):
            r = recs[2 * i + j]
            r.EventType = 1
            r.Event.KeyEvent.bKeyDown = baixo
            r.Event.KeyEvent.wRepeatCount = 1
            r.Event.KeyEvent.UnicodeChar = ch
            r.Event.KeyEvent.wVirtualKeyCode = 0x0D if ch == '\r' else 0
    n = wintypes.DWORD()
    k32.WriteConsoleInputW(wintypes.HANDLE(h), recs, len(recs), ctypes.byref(n))
    k32.CloseHandle(wintypes.HANDLE(h))
    k32.FreeConsole()


def test_nul_na_entrada_e_recusado_mesmo_com_console(tmp_path):
    """No Windows, isatty() da verdadeiro para NUL; a conferencia pelo modo de console recusa."""
    saida = tmp_path / 'r.txt'
    codigo = ('from desdobra import humano;'
              'open(r"%s","w").write(repr(humano.console_interativo()))' % saida)
    _filho_em_console_novo(codigo, stdin=subprocess.DEVNULL, env=_ambiente_sem_claude())
    ok, motivo = eval(saida.read_text())
    assert ok is False and motivo == 'entrada_sem_console'
    _filho_em_console_novo(codigo, env=_ambiente_sem_claude())
    # o console novo de verdade passa (risco residual declarado), menos quando o teste roda num processo aberto pelo
    # Claude: o console novo continua filho de claude.exe, e a conferencia dos pais recusa (decisoes-v1.md, 160)
    from desdobra import plataforma
    pais = plataforma.obter().processos_ancestrais(64)
    esperado = (False, 'terminal_do_claude') if any(n.lower() == 'claude.exe' for n in pais) else (True, None)
    assert eval(saida.read_text()) == esperado


def test_console_novo_com_teclas_injetadas_por_processo_do_claude_e_recusado(tmp_path):
    """O ataque do revisor (r4): processo aberto pelo Claude abre console novo e escreve "sim" nele."""
    job = _job(tmp_path, rap.psd_render(tmp_path / 'o' / 'kv.psd'))
    env = dict(os.environ, CLAUDE_CODE_SESSION_ID='sessao-de-teste')
    codigo = 'import sys;from desdobra import cli;sys.exit(cli.principal(["render","--job",r"%s"]))' % job
    rc = _filho_em_console_novo(codigo, env=env, injetar='sim\rsim\r')
    assert rc == int(Codigo.RECUSADO)
    assert not (job / 'render' / 'origem' / 'master.png').exists()


def test_gancho_pretooluse_nega_as_confirmacoes_humanas():
    script = RAIZ_PLUGIN / 'scripts' / 'gancho_confirmacoes.py'
    dados = json.loads((RAIZ_PLUGIN / 'hooks' / 'hooks.json').read_text(encoding='utf-8'))
    grupos = dados['hooks']['PreToolUse']
    assert any(set(g['matcher'].split('|')) >= {'Bash', 'PowerShell', 'Write', 'Edit'} for g in grupos)

    def decidir(ferramenta, entrada):
        r = subprocess.run([sys.executable, '-I', '-B', str(script)], input=json.dumps(
            {'hook_event_name': 'PreToolUse', 'tool_name': ferramenta, 'tool_input': entrada}).encode(),
            capture_output=True, timeout=60)
        assert r.returncode == 0
        txt = r.stdout.decode('utf-8').strip()
        return json.loads(txt)['hookSpecificOutput']['permissionDecision'] if txt else 'segue'
    negar = ['"C:/x/python.exe" -I -B -m desdobra render --job "C:/j"',
             'python -m desdobra --envelope render --job j',
             '& "C:\\p\\python.exe" -m desdobra linkado confirmar --job j',
             'python -m desdobra spec confirmar --job j --formato a',
             'desdobra render --job j',
             'python -c "from desdobra.render import execucao; execucao.renderizar(1, disparo=2)"',
             'python -c "from desdobra import humano; humano.console_interativo = lambda: (True, None)"',
             'echo {} > C:/j/briefing/linkados-confirmados.json']
    for c in negar:
        assert decidir('Bash', {'command': c}) == 'deny', c
        assert decidir('PowerShell', {'command': c}) == 'deny', c
    for c in ['python -m desdobra --envelope job proxima j --todas', 'python -m desdobra doctor',
              'cat C:/j/render/origem/render.json', 'python -m desdobra spec importar --job j', 'ls render']:
        assert decidir('Bash', {'command': c}) == 'segue', c
    assert decidir('Write', {'file_path': 'C:/j/briefing/linkados-confirmados.json', 'content': '{}'}) == 'deny'
    assert decidir('Edit', {'file_path': 'C:/j/specs/confirmacoes.json'}) == 'deny'
    assert decidir('Write', {'file_path': 'C:/j/render/origem/master.png'}) == 'deny'
    assert decidir('Write', {'file_path': 'C:/j/notas.txt'}) == 'segue'
    # o codigo-fonte do plugin com pasta briefing (skill, modulo do motor) continua editavel
    assert decidir('Edit', {'file_path': 'C:/repo/plugins/desdobra/skills/briefing/SKILL.md'}) == 'segue'
    assert decidir('Write', {'file_path': 'C:/repo/plugins/desdobra/motor/desdobra/briefing/pagina.py'}) == 'segue'


# ------------------------------------------------------------------ 2 e 3. entradas trocadas
def test_fonte_trocada_sem_job_proxima_recusa_o_render(tmp_path, pessoa):
    job = _job(tmp_path, rap.psd_render(tmp_path / 'o' / 'kv.psd'))
    execucao.renderizar(job, disparo=pessoa.exigir('render'))
    nova = tmp_path / 'nova' / 'inventada.ttf'
    ap.gravar(nova.parent, 'inventada.ttf', ap.fonte(ps=rap.FONTE, avanco=900))
    rel = next(r for r in contratos.ler(job / 'estado.json', 'estado/1')['entradas'] if r.startswith('entrada/fontes/'))
    nucleo.trocar_entrada(job, rel, nova)
    assert not (job / 'render' / 'origem' / 'master.png').exists()  # o master velho cai com a troca
    with pytest.raises(execucao.ErroRender) as e:
        execucao.renderizar(job, disparo=pessoa.exigir('render'))
    assert e.value.motivo == 'bloqueio' and 'fases_desatualizadas' in str(e.value)


def test_kv_trocado_sem_job_proxima_recusa_e_a_pilha_usa_o_kv_atual(tmp_path, pessoa):
    job = _job(tmp_path, rap.psd_render(tmp_path / 'o' / 'kv.psd'))
    execucao.renderizar(job, disparo=pessoa.exigir('render'))
    outro = rap.psd_ajuste_sobre_texto(tmp_path / 'o2' / 'kv.psd', mesclagem='NORMAL')
    rel = next(r for r in contratos.ler(job / 'estado.json', 'estado/1')['entradas'] if r.startswith('entrada/kv'))
    nucleo.trocar_entrada(job, rel, outro)
    assert not (job / 'render' / 'origem' / 'master.png').exists()
    _c, bloqueios, _conf = mc.montar(job)
    assert {'fases_desatualizadas', 'laudo_de_outro_kv'} <= {b['codigo'] for b in bloqueios}
    nucleo.proxima(job, todas=True)
    contrato, bloqueios, _conf = mc.montar(job)
    kv = contratos.ler(job / 'estado.json', 'estado/1')['entradas'][rel]['sha256']
    assert not bloqueios and contrato['origem']['kv_sha256'] == kv


def test_texto_visivel_sem_trecho_conferido_reprova(tmp_path, pessoa, monkeypatch):
    job = _job(tmp_path, rap.psd_render(tmp_path / 'o' / 'kv.psd'))
    vazio = {'trechos': 0, 'confere': 0, 'diverge': 0, 'sem_resposta': 0, 'faces_carregadas': 0, 'faces_nao_carregadas': 0}
    cache = {'feito': True, 'copias_encontradas': 0, 'pdfs_encontrados': 0, 'arquivos_varridos': 1,
             'controle_encontrado': True, 'perfil_apagado': True, 'cache_control': 'no-store', 'metodo': 'x'}
    monkeypatch.setattr(execucao, 'texto_no_chromium', lambda *a, **k: ({}, [], vazio, cache, 'x'))
    with pytest.raises(execucao.ErroRender) as e:
        execucao.renderizar(job, disparo=pessoa.exigir('render'))
    assert e.value.motivo == 'texto_sem_trecho_conferido'
    assert not (job / 'render' / 'origem' / 'master.png').exists()


def test_trecho_com_tinta_sem_face_bloqueia(tmp_path, monkeypatch):
    job = _job(tmp_path, rap.psd_render(tmp_path / 'o' / 'kv.psd'))
    from desdobra.fontes import casamento
    monkeypatch.setattr(casamento, 'casar', lambda ps, faces: (None, None, 0))
    _c, bloqueios, _conf = mc.montar(job)
    assert 'trecho_sem_face' in {b['codigo'] for b in bloqueios}


# ------------------------------------------------------------------ 4. PDF fora do disco
def _cabeca_compartilhada(p):
    """Os primeiros bytes de um arquivo que outro processo segura aberto (CreateFileW com compartilhamento total)."""
    from ctypes import wintypes
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    k32.CreateFileW.restype = wintypes.HANDLE
    h = k32.CreateFileW(str(p), 0x80000000, 7, None, 3, 0, None)
    if h in (None, wintypes.HANDLE(-1).value):
        return b''
    try:
        buf, n = ctypes.create_string_buffer(16), wintypes.DWORD()
        k32.ReadFile(wintypes.HANDLE(h), buf, 16, ctypes.byref(n), None)
        return buf.raw[:n.value]
    finally:
        k32.CloseHandle(wintypes.HANDLE(h))


def test_pdf_do_texto_nunca_passa_pela_pasta_temporaria(tmp_path, monkeypatch):
    """O Page.printToPDF em stream grava <guid>.tmp na pasta temporaria do Chromium (r2). Vigia a pasta de verdade."""
    from desdobra.render import autoteste
    dados = autoteste.gerar_fonte()
    vig = tmp_path / 'tmp'
    vig.mkdir()
    for v in ('TMP', 'TEMP'):
        monkeypatch.setenv(v, str(vig))
    import tempfile
    monkeypatch.setattr(tempfile, 'tempdir', None)
    vistos, parar = set(), [False]

    def vigia():
        while not parar[0]:
            for raiz, _d, arqs in os.walk(vig):
                if navegador.PREFIXO_PERFIL in raiz:
                    continue
                for a in arqs:
                    if _cabeca_compartilhada(Path(raiz) / a).startswith(b'%PDF-'):
                        vistos.add(a)
    t = threading.Thread(target=vigia, daemon=True)
    t.start()
    contrato = autoteste.contrato_de_referencia(arquivos.sha256_bytes(dados))
    try:
        for _ in range(3):
            pdfs, *_ = execucao.texto_no_chromium(contrato, {'f01': (dados, 'font/ttf')}, 'dsd-x')
    finally:
        parar[0] = True
        t.join()
    assert pdfs and all(p.startswith(b'%PDF-') for p in pdfs.values())
    assert vistos == set()


# ------------------------------------------------------------------ 5 e 6. o que nao se desenha certo vira decisao
@pytest.mark.parametrize('mesclagem', [None, 'MULTIPLY'])
def test_ajuste_ou_mesclagem_sobre_texto_pede_aceite_do_da(tmp_path, pessoa, mesclagem):
    job = _job(tmp_path, rap.psd_ajuste_sobre_texto(tmp_path / 'o' / 'kv.psd', mesclagem))
    _c, bloqueios, confirmar = mc.montar(job)
    assert not bloqueios and [c['codigo'] for c in confirmar] == ['efeito_sobre_texto_sem_aplicar']
    with pytest.raises(execucao.ErroRender) as e:
        execucao.renderizar(job, disparo=pessoa.exigir('render'))
    assert e.value.motivo == 'pede_decisao_do_da'
    rel = execucao.renderizar(job, disparo=pessoa.exigir('render'), aceites=['efeito_sobre_texto_sem_aplicar'])
    assert rel['aceites'][0]['codigo'] == 'efeito_sobre_texto_sem_aplicar'


def test_clipping_dividido_por_texto_clipado_pede_aceite(tmp_path):
    job = _job(tmp_path, rap.psd_clip_dividido(tmp_path / 'o' / 'kv.psd'))
    _c, bloqueios, confirmar = mc.montar(job)
    assert 'clipping_dividido_por_texto' in {c['codigo'] for c in confirmar}


# ------------------------------------------------------------------ 7 e 10. linkado
def test_linkado_confirmado_de_outro_kv_nao_vale(tmp_path, pessoa):
    psd, campanha, _dados = rap.linkado_com_campanha(tmp_path / 'origem')
    job = _job(tmp_path, psd, campanha=campanha, fontes=False)
    uid = 'uuid-linkado-sintetico'
    linkados.confirmar(job, uid, 'entrada/campanha/arte-linkada.png', disparo=pessoa.exigir('linkado confirmar'))
    assert not mc.montar(job)[1]
    arq = job / mc.ARQUIVO_LINKADOS
    d = json.loads(arq.read_text(encoding='utf-8'))
    d['kv_sha256'] = '0' * 64
    arq.write_text(json.dumps(d), encoding='utf-8')
    assert 'linkados_de_outro_laudo' in {b['codigo'] for b in mc.montar(job)[1]}
    d['kv_sha256'] = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')['origem']['sha256']
    d['linkados'][0]['arquivo'] = 'entrada/campanha/../kv.psd'
    arq.write_text(json.dumps(d), encoding='utf-8')
    assert mc.montar(job)[1]


def test_linkado_em_formato_sem_suporte_bloqueia_e_cmyk_renderiza(tmp_path, pessoa):
    base = tmp_path / 'origem'
    campanha = base / 'campanha'
    campanha.mkdir(parents=True)
    isca = base / 'fora' / 'arte-linkada.png'
    isca.parent.mkdir()
    isca.write_bytes(b'x')
    (campanha / 'arte-linkada.png').write_bytes(b'%PDF-1.4 nao e imagem')
    psd = sinteticos.linkado(base / 'psd', isca, tamanho=21)
    job = _job(tmp_path, psd, campanha=campanha, fontes=False)
    linkados.confirmar(job, 'uuid-linkado-sintetico', 'entrada/campanha/arte-linkada.png',
                       disparo=pessoa.exigir('linkado confirmar'))
    assert 'linkado_formato_sem_suporte' in {b['codigo'] for b in mc.montar(job)[1]}
    jpg = rap.jpeg_cmyk_com_icc()
    novo = tmp_path / 'novo' / 'arte-linkada.png'
    novo.parent.mkdir()
    novo.write_bytes(jpg)
    nucleo.trocar_entrada(job, 'entrada/campanha/arte-linkada.png', novo)
    nucleo.proxima(job, todas=True)
    linkados.confirmar(job, 'uuid-linkado-sintetico', 'entrada/campanha/arte-linkada.png',
                       disparo=pessoa.exigir('linkado confirmar'))
    rel = execucao.renderizar(job, disparo=pessoa.exigir('render'))
    img = np.asarray(Image.open(job / 'render' / 'origem' / 'master.png').convert('RGB'))
    assert img[30, 40, 0] < 120 and img[30, 40, 1] > 150  # ciano, convertido do CMYK
    assert any(r['codigo'] == 'linkado_cmyk_sem_perfil' for r in rel['registros'])


# ------------------------------------------------------------------ 8 e 9. caixa de paragrafo e fora do BMP
def _contrato_teste(entradas):
    from desdobra.render import autoteste
    dados = autoteste.gerar_fonte()
    c = autoteste.contrato_de_referencia(arquivos.sha256_bytes(dados))
    c['entradas'] = entradas
    return c, {'f01': (dados, 'font/ttf')}


def _faixas(cob):
    linhas = (cob > 0.5).any(axis=1)
    return int(np.sum(linhas[1:] & ~linhas[:-1]) + linhas[0])


def test_caixa_de_paragrafo_quebra_na_largura_da_caixa():
    from desdobra.render import autoteste, filho
    e = autoteste._texto('e01', [0, 0, 480, 260], [1, 0, 0, 1, 20, 20], [('HOAV XOHA VXOA HOAX', 30.0, 'c0')],
                         {'c0': [0, 0, 0]})
    e['texto']['tipo_caixa'] = 'paragrafo'
    e['texto']['box_bounds'] = [0.0, 0.0, 200.0, 220.0]
    c, servidos = _contrato_teste([e])
    pdfs, paginas, cdp, _cache, _v = execucao.texto_no_chromium(c, servidos, 'dsd-x')
    p = paginas[0]
    cob = filho.cobertura_do_pdf(pdfs[p['id']], p['largura'], p['altura'], 480, 260, 8)
    assert _faixas(cob) >= 2
    assert np.nonzero(cob.any(axis=0))[0].max() < 20 + 200 + 2


def test_caractere_fora_do_bmp_em_linha_de_varias_cores():
    from desdobra.render import autoteste
    e = autoteste._texto('e02', [0, 30, 480, 100], [1, 0, 0, 1, 10.0, 80.4],
                         [('HO\U0001F600AV', 40.0, 'c0'), ('X OHA', 40.0, 'c1')], {'c0': [0, 0, 0], 'c1': [1, 0, 0]})
    c, servidos = _contrato_teste([e])
    try:
        execucao.texto_no_chromium(c, servidos, 'dsd-x')
    except execucao.ErroRender:
        pass


# ------------------------------------------------------------------ 11. prazo da entrada do filho
def test_entrada_do_filho_conta_no_prazo(tmp_path, python):
    from desdobra import plataforma
    filho = 'import sys, time\nsys.stdin.buffer.readline()\ntime.sleep(60)\n'
    t0 = time.monotonic()
    r = plataforma.obter().executar_isolado([python, '-I', '-B', '-c', filho], 1 << 30, 3, tmp_path,
                                            entrada=b'x' * (64 << 20))
    assert r.situacao == 'tempo' and time.monotonic() - t0 < 30


# ------------------------------------------------------------------ 12 e 13. cache e temporarios
def test_cache_de_pilha_com_asset_alterado_e_refeito(tmp_path, pessoa):
    job = _job(tmp_path, rap.psd_render(tmp_path / 'o' / 'kv.psd'))
    rel = execucao.renderizar(job, disparo=pessoa.exigir('render'))
    a = next(x for x in rel['assets'] if x['sha256'])
    p = job / a['arquivo']
    os.chmod(p, 0o666)
    Image.new('RGBA', (5, 5), (255, 0, 255, 255)).save(p)
    rel2 = execucao.renderizar(job, disparo=pessoa.exigir('render'))
    assert rel2['pilhas_do_cache'] < rel['pilhas_do_cache'] + len([x for x in rel['assets'] if x['tipo'] == 'pilha'])
    assert hashlib.sha256(p.read_bytes()).hexdigest() == a['sha256']
    assert rel2['master']['sha256'] == rel['master']['sha256']


def test_varredura_que_falha_nao_deixa_master_nem_trabalho(tmp_path, pessoa, monkeypatch):
    job = _job(tmp_path, rap.psd_render(tmp_path / 'o' / 'kv.psd'))
    monkeypatch.setattr(execucao, 'varrer_pdfs_no_job', lambda pasta: (1, 1))
    with pytest.raises(execucao.ErroRender):
        execucao.renderizar(job, disparo=pessoa.exigir('render'))
    destino = job / 'render' / 'origem'
    assert not (destino / 'master.png').exists() and not (destino / 'render.json').exists()
    assert not (job / 'render' / '.trabalho').exists()
    assert not [p for p in destino.glob('*') if p.name.startswith('.tmp-')]


# ------------------------------------------------------------------ 14. perfil ICC defeituoso
def _perfil_curv(corpo):
    n = 3
    inicio = 128 + 4 + 12 * n
    return b'\0' * 128 + struct.pack('>I', n) + b''.join(
        struct.pack('>4sII', t, inicio, len(corpo)) for t in (b'rTRC', b'gTRC', b'bTRC')) + corpo


@pytest.mark.parametrize('corpo', [
    b'curv' + b'\0' * 4 + struct.pack('>I', 1) + struct.pack('>H', 0) + b'\0\0',   # gama 0
    b'para' + b'\0' * 4 + struct.pack('>H', 1) + b'\0\0' + struct.pack('>3i', 65536 * 2, 0, 0),  # a = 0
    b'curv' + b'\0' * 4,  # truncada
    b'para' + b'\0' * 4 + struct.pack('>H', 4) + b'\0\0',  # parametros faltando
])
def test_perfil_defeituoso_vira_erro_de_curva(corpo):
    with pytest.raises(icc.ErroCurva):
        dec, enc, _d = icc.curva_do_perfil(_perfil_curv(corpo))
        enc(dec(np.linspace(0, 1, 5)))
