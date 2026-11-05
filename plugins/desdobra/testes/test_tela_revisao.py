# -*- coding: utf-8 -*-
"""Revisao do M7a0 (fatias a0 a a3): regressoes dos achados confirmados na revisao.

  - o processo de fundo da tela nasce com ambiente por lista de permissao (nada de DEBUG, DEBUG_FILE, NODE_OPTIONS,
    PWDEBUG nem variavel do Claude chega ao driver do Playwright) e, no ambiente do plugin, com os navegadores da
    pasta de dados do plugin;
  - a cadeia de pais do disparo humano para no PID reaproveitado (pai nascido depois do filho);
  - a Janela e o processo de fundo apagam o perfil dsd-tela- em toda recusa antes da janela abrir;
  - excecao fora do previsto na montagem vira erro_interno, com evento;
  - o "tela abrir" que mata o fundo sem resposta tira a trava do job que o fundo morto deixou (so a dele);
  - o doctor so avisa quando o Chromium com janela opcional falta;
  - o gancho: o painel sempre negado (decisoes-v1.md, 160), o aval do download protegido, ferramentas de arquivo e de
    navegador fora do perfil e das rotas da tela, despejo de memoria e teclas simuladas negados;
  - a pagina: escala pura sem aba de outra composicao, identificadores do motor traduzidos, "Falta 1" e o passo
    Design system (decisoes-v1.md, 161).
Tudo sintetico: processos filhos de python -c, perfis em pasta temporaria e tabelas de processo montadas a mao.
"""
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

import pytest

from conftest import RAIZ_PLUGIN
from desdobra.resultado import Codigo


def _gancho():
    spec = importlib.util.spec_from_file_location('gancho_confirmacoes', RAIZ_PLUGIN / 'scripts' / 'gancho_confirmacoes.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _job(pasta):
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / 'estado.json').write_text('{}', encoding='utf-8')
    return pasta


def _eventos(job):
    arq = job / 'log' / 'eventos.jsonl'
    return [json.loads(x) for x in arq.read_text(encoding='utf-8').splitlines()] if arq.exists() else []


# ------------------------------------------------------------------ ambiente do processo de fundo
PERIGOSAS = {'DEBUG': 'pw:api,pw:protocol', 'DEBUG_FILE': 'C:/x/pw.log', 'NODE_OPTIONS': '--require C:/x/h.js',
             'PWDEBUG': '1', 'PW_TEST_SOURCE_TRANSFORM': 'x', 'PLAYWRIGHT_DRIVER_PATH': 'C:/x',
             'CLAUDECODE': '1', 'CLAUDE_AGENT_SDK_VERSION': '0.1.0', 'DSD_QUALQUER': 'x'}
FILHO_AMBIENTE = ('import json, os, sys; open(sys.argv[1], "w").write(json.dumps(dict(os.environ))); '
                  'print("recusado sem_briefing")')


def test_fundo_da_tela_nasce_com_ambiente_por_lista(tmp_path, monkeypatch, capsys):
    from desdobra import cli, tela
    job = _job(tmp_path / 'job')
    for k, v in PERIGOSAS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(tela, '_janela_presente', lambda: True)
    saida = tmp_path / 'ambiente.json'
    monkeypatch.setattr(tela, 'comando_do_filho', lambda pasta: [sys.executable, '-I', '-c', FILHO_AMBIENTE,
                                                                 str(saida)])
    codigo = cli.principal(['--envelope', 'tela', 'abrir', '--job', str(job)])
    capsys.readouterr()
    assert codigo == int(Codigo.RECUSADO)
    recebido = {k.upper() for k in json.loads(saida.read_text(encoding='utf-8'))}
    assert not recebido & set(PERIGOSAS), recebido & set(PERIGOSAS)
    assert not [k for k in recebido if k.startswith(('NODE_', 'DEBUG', 'PW', 'CLAUDE'))]
    # so a lista de permissao, o PATH minimo, a pasta dos navegadores e a marca do lancador do venv
    permitidas = {v.upper() for v in tela.VARIAVEIS_DO_FUNDO} | {'PATH', 'PLAYWRIGHT_BROWSERS_PATH',
                                                                 '__PYVENV_LAUNCHER__'}
    assert recebido <= permitidas, recebido - permitidas
    assert 'PLAYWRIGHT_BROWSERS_PATH' in recebido


def test_fundo_da_tela_usa_os_navegadores_da_pasta_do_plugin(tmp_path, monkeypatch):
    from desdobra import chromium, tela
    monkeypatch.setenv(chromium.VARIAVEL_NAVEGADORES, str(tmp_path / 'trocado'))
    monkeypatch.setattr(chromium, 'pasta_dados_do_plugin', lambda: tmp_path / 'DATA')
    assert tela.pasta_navegadores_da_tela() == tmp_path / 'DATA' / chromium.PASTA_NAVEGADORES
    assert tela.ambiente_do_fundo()[chromium.VARIAVEL_NAVEGADORES] == str(tmp_path / 'DATA' / chromium.PASTA_NAVEGADORES)
    # fora do plugin (desenvolvimento e testes) vale a variavel, e sem ela o padrao do Playwright, sempre explicito
    monkeypatch.setattr(chromium, 'pasta_dados_do_plugin', lambda: None)
    assert tela.ambiente_do_fundo()[chromium.VARIAVEL_NAVEGADORES] == str(tmp_path / 'trocado')
    monkeypatch.delenv(chromium.VARIAVEL_NAVEGADORES)
    assert tela.ambiente_do_fundo()[chromium.VARIAVEL_NAVEGADORES] == str(chromium.pasta_padrao_do_playwright())


def test_tela_abrir_confere_o_chromium_na_pasta_que_o_fundo_usa(tmp_path, monkeypatch):
    from desdobra import tela
    from desdobra.doctor import chromium as vc
    pastas = []

    def verificar(pasta=None, arquivo_browsers=None):
        pastas.append(pasta)
        return vc.Verificacao('chromium_janela', 'x', situacao='aviso')
    monkeypatch.setattr(vc, 'verificar_chromium_janela', verificar)
    monkeypatch.setattr(tela, 'pasta_navegadores_da_tela', lambda: tmp_path / 'nav')
    # o doctor so avisa quando falta (download opcional), mas a tela nao abre sem ele
    assert tela._janela_presente() is False and pastas == [tmp_path / 'nav']


# ------------------------------------------------------------------ cadeia de pais com PID reaproveitado
def test_cadeia_de_pais_para_no_pid_reaproveitado():
    from desdobra import plataforma
    # 70 era o wt.exe que abriu o terminal e saiu; o Windows deu o PID a um claude.exe mais novo
    tabela = {100: ('python.exe', 90), 90: ('powershell.exe', 80), 80: ('WindowsTerminal.exe', 70),
              70: ('claude.exe', 1)}
    inicios = {100: 40, 90: 30, 80: 20, 70: 25}
    assert plataforma.cadeia_de_pais(100, tabela, 32, inicios.get) == ('powershell.exe', 'WindowsTerminal.exe')
    # o claude.exe que nasceu antes continua na cadeia (e o painel recusa)
    assert plataforma.cadeia_de_pais(100, tabela, 32, {**inicios, 70: 10}.get) == (
        'powershell.exe', 'WindowsTerminal.exe', 'claude.exe')
    # instante desconhecido nao corta a cadeia (na duvida, o pai conta)
    assert plataforma.cadeia_de_pais(100, tabela, 32, {100: 40}.get) == (
        'powershell.exe', 'WindowsTerminal.exe', 'claude.exe')
    assert plataforma.cadeia_de_pais(100, tabela, 32) == ('powershell.exe', 'WindowsTerminal.exe', 'claude.exe')


@pytest.mark.skipif(sys.platform != 'win32', reason='Toolhelp32 so no Windows')
def test_ancestrais_do_windows_conferem_o_instante_de_criacao(monkeypatch):
    from desdobra import plataforma
    from desdobra.plataforma import windows as w
    eu = os.getpid()
    tabela = {eu: ('python.exe', 90), 90: ('powershell.exe', 80), 80: ('WindowsTerminal.exe', 70),
              70: ('claude.exe', 1)}
    inicios = {eu: 40, 90: 30, 80: 20, 70: 25}
    monkeypatch.setattr(w, 'tabela_de_processos', lambda k32=None: tabela)
    monkeypatch.setattr(w, 'identidade_do_processo', lambda pid: inicios.get(pid))
    assert plataforma.obter().processos_ancestrais(32) == ('powershell.exe', 'WindowsTerminal.exe')


# ------------------------------------------------------------------ perfil apagado em toda recusa
def test_janela_que_nao_amarra_apaga_o_perfil(tmp_path, monkeypatch):
    from desdobra.chromium import navegador, processos
    perfil = navegador.perfil_tela(tmp_path)
    monkeypatch.setattr(processos, 'amarrar_ao_processo', lambda: False)
    j = navegador.Janela(perfil)
    with pytest.raises(navegador.ErroNavegador):
        with j:
            pass
    assert not perfil.exists() and j.perfil_apagado is True


def test_janela_sem_playwright_apaga_o_perfil(tmp_path, monkeypatch):
    from desdobra.chromium import navegador, processos
    perfil = navegador.perfil_tela(tmp_path)
    monkeypatch.setattr(processos, 'amarrar_ao_processo', lambda: True)
    monkeypatch.setitem(sys.modules, 'playwright.sync_api', None)
    j = navegador.Janela(perfil)
    with pytest.raises(navegador.ErroNavegador):
        with j:
            pass
    assert not perfil.exists() and j.perfil_apagado is True


@pytest.fixture
def fundo_falso(tmp_path, monkeypatch):
    """O processo de fundo sem job de verdade: sem varredura de orfaos na pasta temporaria do sistema e com o perfil
    numa pasta temporaria do teste."""
    from desdobra.chromium import navegador
    temp = tmp_path / 'temp'
    temp.mkdir()
    monkeypatch.setattr(navegador, 'varrer_orfaos',
                        lambda pasta_temp=None: {'removidas': 0, 'nao_removidas': 0, 'mantidas': 0})
    real = navegador.perfil_tela
    monkeypatch.setattr(navegador, 'perfil_tela', lambda pasta_temp=None: real(temp))
    return _job(tmp_path / 'job'), temp


def test_fundo_apaga_o_perfil_quando_o_servidor_nao_sobe(fundo_falso, monkeypatch):
    from desdobra.tela import estado, processo, servidor
    job, temp = fundo_falso
    monkeypatch.setattr(estado, 'montar', lambda pasta: {'previas': {}, 'fontes': {}})

    def quebra(conteudo):
        raise ValueError('id fora do padrao')
    monkeypatch.setattr(servidor, 'ServidorTela', quebra)
    avisos = []
    codigo = processo.executar(job, avisar=avisos.append)
    assert avisos == ['recusado erro_interno'] and codigo == int(Codigo.ERRO_INTERNO)
    # o servidor sobe antes do perfil existir: a recusa dele nao deixa pasta nenhuma
    assert not list(temp.iterdir())
    ev = _eventos(job)[-1]
    assert ev['evento'] == 'tela_recusou' and ev['motivo'] == 'erro_interno' and ev.get('perfil_apagado') is not False


def test_fundo_apaga_o_perfil_quando_a_janela_nao_amarra(fundo_falso, monkeypatch):
    from desdobra.chromium import processos
    from desdobra.tela import estado, processo
    job, temp = fundo_falso
    monkeypatch.setattr(estado, 'montar', lambda pasta: {'previas': {}, 'fontes': {}, 'assets': {},
                                                         'estado': {}})
    monkeypatch.setattr(processos, 'amarrar_ao_processo', lambda: False)
    avisos = []
    codigo = processo.executar(job, avisar=avisos.append)
    assert avisos == ['recusado chromium_nao_abriu'] and codigo == int(Codigo.RECUSADO)
    assert not list(temp.iterdir())
    ev = _eventos(job)[-1]
    assert ev['evento'] == 'tela_recusou' and ev['perfil_apagado'] is True


def test_fundo_avisa_erro_interno_quando_a_montagem_quebra(fundo_falso, monkeypatch):
    from desdobra.tela import estado, processo
    job, temp = fundo_falso

    def quebra(pasta):
        raise ValueError('json corrompido')
    monkeypatch.setattr(estado, 'montar', quebra)
    avisos = []
    codigo = processo.executar(job, avisar=avisos.append)
    assert avisos == ['recusado erro_interno'] and codigo == int(Codigo.ERRO_INTERNO)
    ev = _eventos(job)[-1]
    assert ev['evento'] == 'tela_recusou' and ev['motivo'] == 'erro_interno' and ev['excecao'] == 'ValueError'
    assert not list(temp.iterdir())


# ------------------------------------------------------------------ trava do job no fundo morto
FILHO_TRAVA = ('import os, sys, time; fd = os.open(sys.argv[1], os.O_CREAT | os.O_EXCL | os.O_WRONLY); '
               'os.write(fd, str(os.getpid()).encode()); os.close(fd); open(sys.argv[2], "w").write("1"); '
               'time.sleep(120)')
FILHO_CALADO = 'import sys, time; open(sys.argv[2], "w").write("1"); time.sleep(120)'


def _abrir_sem_resposta(tmp_path, monkeypatch, filho):
    from desdobra import cli, tela
    from desdobra.job import nucleo
    job = _job(tmp_path / 'job')
    trava, marca = job / nucleo.ARQUIVO_TRAVA, tmp_path / 'marca'
    monkeypatch.setattr(tela, '_janela_presente', lambda: True)
    monkeypatch.setattr(tela, 'comando_do_filho', lambda pasta: [sys.executable, '-I', '-c', filho, str(trava),
                                                                 str(marca)])
    # a espera so termina depois que o filho fez o que tinha de fazer (a marca), ou no teto do teste
    monkeypatch.setattr(tela, '_espera_s', lambda: 8.0)  # numero-neutro: teto do teste
    return cli, job, trava, marca


def test_tela_abrir_sem_resposta_tira_a_trava_do_fundo_morto(tmp_path, monkeypatch, capsys):
    cli, job, trava, marca = _abrir_sem_resposta(tmp_path, monkeypatch, FILHO_TRAVA)
    codigo = cli.principal(['--envelope', 'tela', 'abrir', '--job', str(job)])
    env = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert codigo == int(Codigo.ORCAMENTO) and env['contagens'] == {'recusa_tela_nao_respondeu': 1}
    assert marca.exists(), 'o filho nao chegou a pegar a trava'
    assert not trava.exists()


def test_tela_abrir_sem_resposta_deixa_a_trava_de_outro_processo(tmp_path, monkeypatch, capsys):
    cli, job, trava, marca = _abrir_sem_resposta(tmp_path, monkeypatch, FILHO_CALADO)
    trava.write_text(str(os.getpid()), encoding='ascii')  # a trava e de outro desdobra (este pytest), vivo
    codigo = cli.principal(['--envelope', 'tela', 'abrir', '--job', str(job)])
    capsys.readouterr()
    assert codigo == int(Codigo.ORCAMENTO) and trava.read_text(encoding='ascii') == str(os.getpid())


# ------------------------------------------------------------------ doctor
def test_doctor_so_avisa_quando_o_chromium_com_janela_falta(tmp_path):
    import test_tela_janela as ttj
    from desdobra.doctor import chromium as vc
    v = vc.verificar_chromium_janela(tmp_path / 'ms-playwright', ttj._browsers_falso(tmp_path))
    assert v.situacao == 'aviso' and 'aval' in v.o_que_fazer


# ------------------------------------------------------------------ gancho
@pytest.mark.parametrize('entrada', [{'command': 'npm run dev'}, {'command': 'git status', 'cwd': 'C:/repo'},
                                     {'command': "$p='des'+'dobra'; & $p ren''der --job ..\\kv",
                                      'cwd': 'C:/Users/u/Desktop'},
                                     {'command': 'powershell -File C:/x/a.ps1'}, {}])
def test_gancho_nega_sempre_o_painel(entrada):
    # decisoes-v1.md, 160: "o gancho nega sempre a ferramenta que roda comando no painel"
    assert _gancho().decidir({'tool_name': 'mcp__terminal__run_in_terminal', 'tool_input': entrada}) == 'deny'


@pytest.mark.parametrize('evento', [
    {'tool_name': 'Write', 'tool_input': {'file_path': 'C:/Users/u/.claude/plugins/data/desdobra-desdobra/'
                                                      'aval-chromium-janela.json', 'content': '{}'}},
    {'tool_name': 'Bash', 'tool_input': {'command': 'echo {} > C:/d/aval-chromium-janela.json'}},
    {'tool_name': 'PowerShell', 'tool_input': {'command': "Set-Content $env:DATA\\aval-chromium-janela.json '{}'"}},
])
def test_gancho_protege_o_aval_do_download(evento):
    assert _gancho().decidir(evento) == 'deny'


@pytest.mark.parametrize('evento', [
    {'tool_name': 'Read', 'tool_input': {'file_path': 'C:/Users/u/AppData/Local/Temp/dsd-tela-abc/Default/Cookies'}},
    {'tool_name': 'Glob', 'tool_input': {'pattern': 'dsd-t*/**', 'path': 'C:/Users/u/AppData/Local/Temp'}},
    {'tool_name': 'Grep', 'tool_input': {'pattern': 'x', 'path': 'C:/Temp/dsd-nasce-1/dsd-dono.json'}},
    {'tool_name': 'PowerShell', 'tool_input': {'command': 'Get-ChildItem $env:TEMP\\dsd-t*'}},
    {'tool_name': 'Bash', 'tool_input': {'command': 'ls /tmp/dsd-*'}},
    {'tool_name': 'mcp__claude-in-chrome__navigate', 'tool_input': {'url': 'http://127.0.0.1:5000/fonte/f01'}},
    {'tool_name': 'mcp__Claude_Browser__navigate', 'tool_input': {'url': 'http://127.0.0.1:5000/api/estado'}},
    {'tool_name': 'mcp__Claude_Browser__javascript_tool',
     'tool_input': {'action': 'javascript_exec', 'text': "document.cookie = 'dsd_tela=abc'"}},
    {'tool_name': 'WebFetch', 'tool_input': {'url': 'http://127.0.0.1:5000/entrar/abc', 'prompt': 'x'}},
    {'tool_name': 'PowerShell',
     'tool_input': {'command': 'rundll32 C:\\Windows\\System32\\comsvcs.dll, MiniDump 123 C:\\x\\d.dmp full'}},
    {'tool_name': 'Bash', 'tool_input': {'command': 'procdump -ma 123 C:/x/d.dmp'}},
    {'tool_name': 'PowerShell',
     'tool_input': {'command': "Add-Type -A System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('{F12}')"}},
    {'tool_name': 'PowerShell', 'tool_input': {'command': "$w = New-Object -ComObject WScript.Shell; $w.AppActivate('x')"}},
])
def test_gancho_nega_o_caminho_ate_o_perfil_as_rotas_e_a_memoria_da_tela(evento):
    assert _gancho().decidir(evento) == 'deny', evento


@pytest.mark.parametrize('evento', [
    {'tool_name': 'Read', 'tool_input': {'file_path': 'C:/repo/plugins/desdobra/motor/desdobra/tela/servidor.py'}},
    {'tool_name': 'Glob', 'tool_input': {'pattern': '**/*.py', 'path': 'C:/repo'}},
    {'tool_name': 'Grep', 'tool_input': {'pattern': 'def principal', 'path': 'C:/repo'}},
    {'tool_name': 'mcp__claude-in-chrome__navigate', 'tool_input': {'url': 'https://example.com/fonte/f01'}},
    {'tool_name': 'mcp__Claude_Browser__navigate', 'tool_input': {'url': 'http://localhost:3000/'}},
    {'tool_name': 'WebFetch', 'tool_input': {'url': 'https://docs.python.org/3/', 'prompt': 'x'}},
    {'tool_name': 'Bash', 'tool_input': {'command': 'git diff --stat'}},
])
def test_gancho_deixa_o_que_nao_e_da_tela(evento):
    assert _gancho().decidir(evento) is None, evento


def test_hooks_json_casa_as_ferramentas_de_arquivo_e_de_navegador():
    dados = json.loads((RAIZ_PLUGIN / 'hooks' / 'hooks.json').read_text(encoding='utf-8'))
    gancho = [g for g in dados['hooks']['PreToolUse']
              if any('gancho_confirmacoes.py' in ' '.join(h.get('args', [])) for h in g['hooks'])]
    for nome in ('Read', 'Glob', 'Grep', 'WebFetch', 'mcp__claude-in-chrome__navigate',
                 'mcp__claude-in-chrome__javascript_tool', 'mcp__Claude_Browser__navigate',
                 'mcp__Claude_Browser__javascript_tool', 'mcp__terminal__run_in_terminal', 'Bash', 'Write'):
        assert any(re.fullmatch(g['matcher'], nome) for g in gancho), nome


# ------------------------------------------------------------------ pagina
def _js():
    return (RAIZ_PLUGIN / 'tela' / 'tela.js').read_text(encoding='utf-8')


def test_pagina_traduz_as_regras_os_tipos_e_as_fases_do_motor():
    from desdobra.derivacao import escala
    from desdobra.laudo import TIPOS
    js = _js()
    bloco = re.search(r'const REGRAS = \{([^}]*)\}', js)
    assert bloco, 'tela.js sem o mapa REGRAS'
    for r in escala.REGRAS:
        assert re.search(r'(?<![\w])%s:' % r, bloco.group(1)), r
    bloco = re.search(r'const TIPOS = \{([^}]*)\}', js)
    assert bloco, 'tela.js sem o mapa TIPOS'
    for t in set(TIPOS.values()) | {'smart_embutido', 'smart_linkado', 'ajuste', 'outro'}:
        assert re.search(r'(?<![\w])%s:' % t, bloco.group(1)), t
    # nada de identificador cru do motor no rotulo de regra, no tipo e na fase
    assert "par('Tipo', n.tipo)" not in js and "par('Regra de escala', r.regra" not in js
    assert "'Fase ' + b.fase" not in js


def test_bloqueio_leva_a_descricao_da_fase():
    from desdobra.job import fases
    from desdobra.tela import estado
    assert estado.descricao_da_fase('ler') == next(f.descricao for f in fases.ESTEIRA if f.id == 'ler')
    assert estado.descricao_da_fase('nao_existe') == 'nao existe'


def test_contador_concorda_com_o_numero():
    js = _js()
    assert "textContent = 'Faltam ' + lista.length" not in js
    assert re.search(r"lista\.length === 1 \? 'Falta 1'", js)


def test_pagina_tem_o_passo_design_system_so_de_leitura():
    html = (RAIZ_PLUGIN / 'tela' / 'tela.html').read_text(encoding='utf-8')
    assert re.search(r'data-passo="design"[^>]*>[^<]*Design system<', html)
    assert 'id="passo-design"' in html and 'id="resumo-design"' in html


def test_janela_abre_maximizada():
    from desdobra.chromium import navegador
    assert '--start-maximized' in navegador.ARGUMENTOS_JANELA
