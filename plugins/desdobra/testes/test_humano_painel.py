# -*- coding: utf-8 -*-
"""Fatia a0 do M7 (decisoes-v1.md, 160): o painel de terminal do app do Claude nao dispara o que so o DA dispara.

A medicao do shell do painel (04/11) achou: nenhuma variavel CLAUDECODE/CLAUDE_CODE_*, mas TERM_PROGRAM=claude-desktop,
CLAUDE_AGENT_SDK_VERSION presente e a cadeia de pais powershell.exe -> claude.exe -> claude.exe -> sihost.exe. O motor
recusa cada marca sozinha; o gancho nega sempre a ferramenta que roda comando no painel. Tudo sintetico: ambiente,
cadeia de processos e console sao simulados.
"""
import ctypes
import importlib.util
import json
import os
import subprocess
import sys
import types

import pytest

from conftest import RAIZ_PLUGIN
from desdobra import cli, humano, plataforma
from desdobra.resultado import Codigo

PAINEL = 'mcp__terminal__run_in_terminal'
# a cadeia medida no shell do painel (scratchpad/m7/painel-medicao.json), pid: (nome, pai)
CADEIA_MEDIDA = {30324: ('powershell.exe', 22360), 22360: ('claude.exe', 30064), 30064: ('claude.exe', 7284),
                 7284: ('sihost.exe', 2344), 2344: ('svchost.exe', 1308), 1308: ('services.exe', 1184),
                 1184: ('wininit.exe', 1012)}


class _Tty:
    def isatty(self):
        return True


@pytest.fixture
def console_limpo(monkeypatch):
    """Um console de verdade de uma pessoa: sem variavel do Claude, sem marca do painel, console do sistema ok,
    isatty nos dois e cadeia de pais sem o Claude."""
    for v in humano.VARIAVEIS_DO_CLAUDE + humano.VARIAVEIS_DO_PAINEL + tuple(humano.MARCAS_DO_PAINEL):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(humano, '_modo_envelope', lambda: False)
    monkeypatch.setattr(humano, '_console_do_sistema', lambda: (True, None))
    monkeypatch.setattr(humano, '_ancestrais', lambda: ('powershell.exe', 'explorer.exe'))
    # o sys do proprio modulo: a captura do pytest troca sys.stdin e sys.stdout a cada fase do teste
    monkeypatch.setattr(humano, 'sys', types.SimpleNamespace(stdin=_Tty(), stdout=_Tty()))
    return monkeypatch


MARCAS = [('TERM_PROGRAM', 'claude-desktop'), ('TERM_PROGRAM', 'Claude-Desktop'),
          ('CLAUDE_AGENT_SDK_VERSION', '0.1.0')]


# ------------------------------------------------------------------ motor
def test_console_limpo_continua_aceito(console_limpo):
    assert humano.console_interativo() == (True, None)
    d = humano.exigir('render')
    assert humano.conferir(d, 'render') is d


def test_outro_term_program_nao_e_o_painel(console_limpo):
    console_limpo.setenv('TERM_PROGRAM', 'vscode')
    console_limpo.setenv('CLAUDE_AGENT_SDK_VERSION', '')
    assert humano.console_interativo() == (True, None)


@pytest.mark.parametrize('variavel,valor', MARCAS)
def test_cada_marca_de_ambiente_do_painel_recusa(console_limpo, variavel, valor):
    console_limpo.setenv(variavel, valor)
    assert humano.console_interativo() == (False, 'terminal_do_claude')


@pytest.mark.parametrize('cadeia', [('powershell.exe', 'claude.exe', 'claude.exe', 'sihost.exe'),
                                    ('cmd.exe', 'pwsh.exe', 'CLAUDE.EXE'), ('claude.exe',)])
def test_pai_claude_exe_recusa(console_limpo, cadeia):
    console_limpo.setattr(humano, '_ancestrais', lambda: cadeia)
    assert humano.console_interativo() == (False, 'terminal_do_claude')


def test_cadeia_ilegivel_recusa(console_limpo):
    console_limpo.setattr(humano, '_ancestrais', lambda: None)
    assert humano.console_interativo() == (False, 'cadeia_de_processos_ilegivel')


def test_console_do_sistema_recusado_continua_com_o_motivo_dele(console_limpo):
    console_limpo.setattr(humano, '_console_do_sistema', lambda: (False, 'entrada_sem_console'))
    console_limpo.setattr(humano, '_ancestrais', lambda: ('claude.exe',))
    assert humano.console_interativo() == (False, 'entrada_sem_console')


@pytest.mark.parametrize('comando', humano.COMANDOS)
@pytest.mark.parametrize('marca', ['TERM_PROGRAM', 'CLAUDE_AGENT_SDK_VERSION', 'pai'])
def test_exigir_recusa_o_painel_em_todo_comando_humano(console_limpo, comando, marca):
    if marca == 'pai':
        console_limpo.setattr(humano, '_ancestrais', lambda: ('powershell.exe', 'claude.exe'))
    else:
        console_limpo.setenv(marca, 'claude-desktop' if marca == 'TERM_PROGRAM' else '0.1.0')
    with pytest.raises(humano.ErroHumano) as e:
        humano.exigir(comando)
    assert str(e.value) == 'terminal_do_claude'


def test_o_motivo_tem_texto_em_portugues():
    assert 'painel de terminal do app do Claude' in humano.TEXTO_MOTIVO['terminal_do_claude']
    # M7c, K5: o o_que_fazer manda o DA a tela, sem terminal (o motivo continua no TEXTO_MOTIVO)
    assert 'tela' in humano.O_QUE_FAZER and 'terminal' not in humano.O_QUE_FAZER
    assert humano.TEXTO_MOTIVO['cadeia_de_processos_ilegivel']


@pytest.mark.parametrize('argv', [['render', '--job', '{job}'], ['aprovar', '--job', '{job}', '--formato', 'a'],
                                  ['entregar', '--job', '{job}']])
@pytest.mark.parametrize('marca', ['TERM_PROGRAM', 'CLAUDE_AGENT_SDK_VERSION', 'pai'])
def test_render_aprovar_e_entregar_recusam_o_painel_e_nao_gravam(tmp_path, console_limpo, argv, marca):
    if marca == 'pai':
        console_limpo.setattr(humano, '_ancestrais', lambda: ('powershell.exe', 'claude.exe', 'claude.exe'))
    else:
        console_limpo.setenv(marca, 'claude-desktop' if marca == 'TERM_PROGRAM' else '0.1.0')
    perguntas = []
    console_limpo.setattr(humano, 'ler', lambda p: perguntas.append(p) or 'sim')
    console_limpo.setattr(cli._Analisador, 'modo_envelope', False)
    (tmp_path / 'estado.json').write_text('{}', encoding='utf-8')
    args = cli.montar_analisador().parse_args([a.replace('{job}', str(tmp_path)) for a in argv])
    r = args.executar(args)
    assert r.codigo == int(Codigo.RECUSADO)
    assert r.contagens == {'recusa_terminal_do_claude': 1}
    assert r.o_que_fazer == humano.o_que_fazer(argv[0]) and perguntas == []
    assert sorted(p.name for p in tmp_path.rglob('*')) == ['estado.json']


def test_o_double_pessoa_continua_valendo(pessoa, monkeypatch):
    monkeypatch.setenv('TERM_PROGRAM', 'claude-desktop')  # o double simula a conferencia inteira
    for c in ('render', 'aprovar', 'entregar'):
        d = pessoa.exigir(c)
        assert pessoa.conferir(d, c) is d


# ------------------------------------------------------------------ cadeia de pais
def test_cadeia_medida_do_painel():
    nomes = plataforma.cadeia_de_pais(30324, CADEIA_MEDIDA, 32)
    assert nomes == ('claude.exe', 'claude.exe', 'sihost.exe', 'svchost.exe', 'services.exe', 'wininit.exe')


def test_cadeia_respeita_a_profundidade_e_para_em_ciclo_e_pai_ausente():
    assert plataforma.cadeia_de_pais(30324, CADEIA_MEDIDA, 2) == ('claude.exe', 'claude.exe')
    assert plataforma.cadeia_de_pais(30324, CADEIA_MEDIDA, 0) == ()
    ciclo = {10: ('a.exe', 20), 20: ('b.exe', 10)}
    assert plataforma.cadeia_de_pais(10, ciclo, 32) == ('b.exe',)
    assert plataforma.cadeia_de_pais(10, {10: ('a.exe', 0)}, 32) == ()
    assert plataforma.cadeia_de_pais(10, {10: ('a.exe', 10)}, 32) == ()
    assert plataforma.cadeia_de_pais(99, CADEIA_MEDIDA, 32) is None


def test_ancestrais_do_motor_usam_o_limite_registrado(monkeypatch):
    from desdobra import limites
    pedidos = []

    class _Plat:
        def processos_ancestrais(self, profundidade_max):
            pedidos.append(profundidade_max)
            return ('x.exe',)
    monkeypatch.setattr(plataforma, 'obter', lambda: _Plat())
    assert humano._ancestrais() == ('x.exe',)
    lim = limites.obter('humano.profundidade_max_ancestrais')
    assert pedidos == [int(lim.valor)] and lim.fonte


def test_base_sem_lista_de_processos_devolve_vazio():
    assert plataforma.PlataformaSemSuporte('x').processos_ancestrais(32) == ()


windows = pytest.mark.skipif(sys.platform != 'win32', reason='Toolhelp32 so no Windows')


@windows
def test_foto_falsa_de_processos_do_windows():
    from desdobra.plataforma import windows as w

    class _K32:
        def __init__(self, linhas, falha=False):
            self.linhas, self.falha, self.i, self.fechado = linhas, falha, 0, False

        def CreateToolhelp32Snapshot(self, flags, pid):
            assert flags == w.Constante.TH32CS_SNAPPROCESS
            return w._INVALIDO if self.falha else 77

        def _encher(self, ref):
            if self.i >= len(self.linhas):
                return False
            e = ref._obj
            assert e.dwSize == ctypes.sizeof(w.PROCESSENTRY32W)
            e.th32ProcessID, e.th32ParentProcessID, e.szExeFile = self.linhas[self.i]
            self.i += 1
            return True

        def Process32FirstW(self, foto, ref):
            return self._encher(ref)

        def Process32NextW(self, foto, ref):
            return self._encher(ref)

        def CloseHandle(self, h):
            self.fechado = True
            return True
    k = _K32([(pid, pai, nome) for pid, (nome, pai) in CADEIA_MEDIDA.items()])
    assert w.tabela_de_processos(k) == CADEIA_MEDIDA and k.fechado
    assert w.tabela_de_processos(_K32([], falha=True)) is None


@windows
def test_cadeia_real_do_windows_ve_o_python_pai(tmp_path):
    saida = tmp_path / 'a.json'
    codigo = ('import json;from desdobra import plataforma;'
              'open(r"%s","w").write(json.dumps(plataforma.obter().processos_ancestrais(32)))' % saida)
    env = dict(os.environ, PYTHONPATH=str(RAIZ_PLUGIN / 'motor'))
    subprocess.run([sys.executable, '-c', codigo], env=env, timeout=120, check=True)
    nomes = json.loads(saida.read_text())
    assert nomes and nomes[0].lower() == os.path.basename(sys.executable).lower()
    assert all(isinstance(n, str) for n in nomes)


# ------------------------------------------------------------------ gancho
def _gancho():
    spec = importlib.util.spec_from_file_location('gancho_confirmacoes', RAIZ_PLUGIN / 'scripts' / 'gancho_confirmacoes.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


NEGAR_NO_PAINEL = [
    {'command': 'desdobra render --job C:/j'},
    {'command': 'python -m desdobra aprovar --job C:/j --formato a'},
    {'command': 'python -m desdobra doctor'},  # qualquer chamada do desdobra pelo painel
    {'command': 'C:/x/.venv/Scripts/python.exe -m DESDOBRA entregar --job C:/j'},
    {'command': '& "C:\\p\\desdobra.exe" render --job j'},
    {'command': 'cat C:/j/estado.json'},
    {'command': 'type C:\\j\\briefing\\aprovacao.json'},
    {'command': 'python x.py', 'cwd': 'C:/Users/u/plugins/desdobra/motor'},
    {'command': 'python -c "import os; os.system(chr(100))"', 'cwd': 'C:\\Users\\u\\Desdobra'},
    {'command': 'echo 1 > C:/j/parametros/entrega.json'},
    {'command': 'rmdir C:/Users/u/AppData/Local/Temp/dsd-tela-abc'},
]


@pytest.mark.parametrize('entrada', NEGAR_NO_PAINEL)
def test_gancho_nega_o_painel_quando_fala_do_desdobra_ou_do_job(entrada):
    assert _gancho().decidir({'tool_name': PAINEL, 'tool_input': entrada}) == 'deny', entrada


def test_gancho_nega_o_painel_com_cwd_numa_pasta_de_job(tmp_path):
    job = tmp_path / 'campanha'
    (job / 'origem').mkdir(parents=True)
    (job / 'estado.json').write_text('{}', encoding='utf-8')
    g = _gancho()
    for cwd in (job, job / 'origem'):
        assert g.decidir({'tool_name': PAINEL, 'tool_input': {'command': 'python a.py', 'cwd': str(cwd)}}) == 'deny'
    # o comando que cita a pasta do job pelo caminho tambem
    assert g.decidir({'tool_name': PAINEL, 'tool_input': {'command': 'python a.py "%s"' % job}}) == 'deny'


@pytest.mark.parametrize('entrada', [{'command': 'npm run dev'}, {'command': 'git status', 'cwd': 'C:/repo'},
                                     {'command': 'python -m http.server 8000'}, {},
                                     {'command': 'dir C:/Duda/desdobramento-de-midia/pesquisa'}])
def test_gancho_nega_o_painel_mesmo_fora_do_desdobra(entrada, tmp_path):
    # decisoes-v1.md, 160: o gancho nega sempre a ferramenta que roda comando no painel (revisao do M7a0)
    entrada = dict(entrada)
    if entrada and 'cwd' not in entrada:
        entrada['cwd'] = str(tmp_path)  # pasta sem estado.json
    assert _gancho().decidir({'tool_name': PAINEL, 'tool_input': entrada}) == 'deny'


def test_gancho_nao_mexe_no_open_terminal_tab_que_nao_roda_comando():
    assert _gancho().decidir({'tool_name': 'mcp__terminal__open_terminal_tab', 'tool_input': {'cwd': 'C:/x'}}) is None


def test_gancho_pelo_processo_devolve_o_motivo_do_painel():
    script = RAIZ_PLUGIN / 'scripts' / 'gancho_confirmacoes.py'
    r = subprocess.run([sys.executable, '-I', '-B', str(script)], input=json.dumps(
        {'hook_event_name': 'PreToolUse', 'tool_name': PAINEL,
         'tool_input': {'command': 'desdobra entregar --job C:/j'}}).encode(), capture_output=True, timeout=60)
    assert r.returncode == 0
    saida = json.loads(r.stdout.decode('utf-8'))['hookSpecificOutput']
    assert saida['permissionDecision'] == 'deny'
    assert 'painel de terminal' in saida['permissionDecisionReason']


def test_hooks_json_casa_a_ferramenta_do_painel():
    import re
    dados = json.loads((RAIZ_PLUGIN / 'hooks' / 'hooks.json').read_text(encoding='utf-8'))
    grupos = dados['hooks']['PreToolUse']
    gancho = [g for g in grupos if any('gancho_confirmacoes.py' in ' '.join(h.get('args', [])) for h in g['hooks'])]
    assert gancho
    for nome in ('Bash', 'PowerShell', 'Write', 'Edit', 'MultiEdit', 'NotebookEdit', PAINEL):
        assert any(re.fullmatch(g['matcher'], nome) for g in gancho), nome
    assert PAINEL in _gancho().FERRAMENTAS_DO_PAINEL
