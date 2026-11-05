# -*- coding: utf-8 -*-
"""Prepara o ambiente Python do motor na pasta de dados do plugin. E o gancho SessionStart do plugin.

Roda com o Python do PATH, so com a biblioteca padrao (o ambiente do motor ainda pode nao existir). O gancho
chama este arquivo na forma exec, sem shell (hooks/hooks.json):

    python -I -B ${CLAUDE_PLUGIN_ROOT}/scripts/preparar_ambiente.py

O Claude Code exporta CLAUDE_PLUGIN_ROOT e CLAUDE_PLUGIN_DATA para o processo do gancho
(https://code.claude.com/docs/en/plugins/manifest-reference.md, Environment variables).

O que faz, nesta ordem:
  1. confere a versao do Python contra o limite ambiente.python_versoes_aceitas de motor/fontes-de-limites.json;
  2. compara motor/requirements.lock com a copia guardada em DATA/requirements.lock:
       - igual, com DATA/interpretador.json valido e o mesmo CLAUDE_PLUGIN_ROOT: nada a fazer (caminho rapido);
       - igual, mas com outro CLAUDE_PLUGIN_ROOT (versao nova do plugin com o mesmo lock): refaz so a instalacao
         editavel do motor, porque o .pth dela guarda o caminho de motor/;
       - diferente ou sem copia: recria DATA/venv, instala o lock com conferencia de hash e instala o motor;
  3. confere o ambiente novo rodando "python -I -B -m desdobra --version" e "pip check";
  4. so depois de tudo certo, grava a copia do lock e DATA/interpretador.json (com o caminho do Python do
     ambiente, que as skills leem, porque as variaveis do plugin nao existem no Bash do Claude). Os caminhos vao
     com barras normais, que funcionam no Bash e no PowerShell do Windows;
  5. confere o Chromium fixado: o headless shell da revisao que o Playwright do ambiente pede (browsers.json do
     pacote), em DATA/ms-playwright. Se ele nao esta la, baixa com "python -m playwright install --only-shell
     chromium" e PLAYWRIGHT_BROWSERS_PATH=DATA/ms-playwright (a mesma pasta que o motor usa). Ja presente, nao baixa.
     Isso vale tambem no caminho rapido: um ambiente pronto sem o Chromium so baixa o Chromium. A falha do download
     nao desfaz o ambiente Python: a linha de situacao avisa, e o doctor confere.
  6. confere o Chromium com janela da tela de briefing (M7a1, decisoes-v1.md n 158): o 'chromium' da mesma revisao
     (Chrome for Testing), em DATA/ms-playwright. Ele so e baixado com o aval do DA, gravado em
     DATA/aval-chromium-janela.json, com "python -m playwright install --no-shell chromium" (o headless shell ja
     esta la). Sem o aval, nada e baixado e a linha de situacao diz o tamanho e que falta o aval; ja presente, nao
     pede aval nem baixa. A falha do download tambem nao desfaz o ambiente.

Registro: DATA/preparo.json (etapas, codigos e tempos, inclusive o tempo da primeira criacao e o do download do
Chromium, que se medem contra o timeout do gancho) e DATA/preparo.log (saida do venv, do pip e do Playwright).
Nenhum conteudo de job passa por aqui.

Saida: uma linha de situacao so, na saida padrao, que o Claude Code poe no contexto da sessao
(https://code.claude.com/docs/en/hooks.md, SessionStart). O codigo de saida e sempre 0, porque com outro codigo
o Claude Code descarta essa linha; quem diz se o ambiente esta pronto e a linha, o preparo.json e o doctor.
"""
import datetime
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

PREFIXO = 'desdobra: '
ESQUEMA_INTERPRETADOR = 'interpretador/1'
ESQUEMA_PREPARO = 'preparo/1'
NOME_TRAVA = '.preparo.trava'
NOME_COPIA_LOCK = 'requirements.lock'
NOME_INTERPRETADOR = 'interpretador.json'
NOME_PREPARO = 'preparo.json'
NOME_LOG = 'preparo.log'
NOME_VENV = 'venv'
NOME_NAVEGADORES = 'ms-playwright'
NAVEGADOR_FIXADO = 'chromium-headless-shell'
NAVEGADOR_JANELA = 'chromium'
NOME_AVAL_JANELA = 'aval-chromium-janela.json'
# tamanho medido no download de 04/11 (decisoes-v1.md n 158: 179,4 MiB baixados, 408 MB instalados)
TAMANHO_JANELA = 'cerca de 180 MiB para baixar e 410 MB instalados'
MARCA_INSTALADO = 'INSTALLATION_COMPLETE'


class Falha(Exception):
    """Uma etapa do preparo falhou. `linha` e o texto fixo para o DA."""

    def __init__(self, etapa, linha):
        super().__init__(etapa)
        self.etapa = etapa
        self.linha = linha


# ------------------------------------------------------------------ utilidades
def agora_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


def versao_menor(info=None):
    info = info or sys.version_info
    return '%d.%d' % (info[0], info[1])


def python_do_venv(venv):
    return venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def mesmo_caminho(a, b):
    try:
        return os.path.normcase(os.path.abspath(os.fspath(a))) == os.path.normcase(os.path.abspath(os.fspath(b)))
    except (TypeError, ValueError):
        return False


def ler_json(caminho):
    try:
        with open(caminho, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def gravar_json_atomico(caminho, dados):
    temporario = caminho.with_name('.tmp-' + caminho.name)
    with open(temporario, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporario, caminho)


def gravar_bytes_atomico(caminho, dados):
    temporario = caminho.with_name('.tmp-' + caminho.name)
    with open(temporario, 'wb') as f:
        f.write(dados)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporario, caminho)


def ler_limite(raiz, limite_id):
    """Valor de um limite de motor/fontes-de-limites.json (sem validar o registro: quem valida e o motor)."""
    dados = ler_json(Path(raiz) / 'motor' / 'fontes-de-limites.json')
    if not isinstance(dados, dict):
        raise KeyError(limite_id)
    for item in dados.get('limites', []):
        if item.get('id') == limite_id and item.get('valor') is not None:
            return item['valor']
    raise KeyError(limite_id)


def ambiente_dos_comandos():
    """Ambiente do pai, sem o que mudaria o Python do venv ou o pip por baixo."""
    env = dict(os.environ)
    for nome in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP', 'PYTHONUSERBASE', 'PIP_USER', 'PIP_TARGET',
                 'PIP_PREFIX', 'PIP_REQUIRE_VIRTUALENV', 'VIRTUAL_ENV'):
        env.pop(nome, None)
    env['PIP_DISABLE_PIP_VERSION_CHECK'] = '1'
    env['PIP_NO_INPUT'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    return env


def executar_comando(argv, log, ambiente=None):
    """Roda argv sem shell e sem janela, manda a saida para o log e devolve (codigo, texto). ambiente: variaveis a
    mais para o comando (por exemplo PLAYWRIGHT_BROWSERS_PATH)."""
    log.write('\n$ %s\n' % ' '.join(str(a) for a in argv))
    log.flush()
    env = ambiente_dos_comandos()
    env.update({k: str(v) for k, v in (ambiente or {}).items()})
    try:
        proc = subprocess.run([str(a) for a in argv], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, env=env, shell=False,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except OSError as e:
        log.write('nao iniciou: %s\n' % type(e).__name__)
        return None, ''
    texto = proc.stdout.decode('utf-8', 'replace')
    log.write(texto)
    log.write('[codigo %s]\n' % proc.returncode)
    log.flush()
    return proc.returncode, texto


# ------------------------------------------------------------------ decisao
def situacao_atual(raiz, dados, lock_bytes):
    """'pronto', 'religar' ou 'recriar', sem rodar nada (e o caminho rapido de toda sessao)."""
    try:
        igual = (dados / NOME_COPIA_LOCK).read_bytes() == lock_bytes
    except OSError:
        igual = False
    interp = ler_json(dados / NOME_INTERPRETADOR)
    if not igual or not isinstance(interp, dict) or interp.get('esquema') != ESQUEMA_INTERPRETADOR:
        return 'recriar'
    python = interp.get('python') or ''
    if not mesmo_caminho(python, python_do_venv(dados / NOME_VENV)) or not Path(python).is_file():
        return 'recriar'
    if interp.get('python_versao_menor') != versao_menor():
        return 'recriar'
    if interp.get('lock_sha256') != hashlib.sha256(lock_bytes).hexdigest():
        return 'recriar'
    if not mesmo_caminho(interp.get('plugin_root') or '', raiz):
        return 'religar'
    return 'pronto'


def tomar_trava(dados, idade_max_s):
    """Cria a trava do preparo. Devolve o caminho, ou None se outra sessao esta preparando agora.

    Trava mais velha que idade_max_s e de um preparo que morreu (por exemplo, cortado pelo timeout do gancho)."""
    trava = dados / NOME_TRAVA
    for _tentativa in range(2):
        try:
            fd = os.open(trava, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                idade = time.time() - trava.stat().st_mtime
            except OSError:
                continue
            if idade < float(idade_max_s):
                return None
            try:
                trava.unlink()
            except OSError:
                return None
            continue
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write('%d %s\n' % (os.getpid(), agora_iso()))
        return trava
    return None


# ------------------------------------------------------------------ Chromium fixado
def revisao_do_chromium(venv, navegador=NAVEGADOR_FIXADO):
    """Revisao de `navegador` (o headless shell, ou o Chromium com janela) que o Playwright instalado no venv pede
    (driver/package/browsers.json), ou None."""
    for arq in sorted(Path(venv).glob('**/site-packages/playwright/driver/package/browsers.json')):
        dados = ler_json(arq)
        for b in (dados or {}).get('browsers') or []:
            if b.get('name') == navegador and b.get('revision'):
                return str(b['revision'])
    return None


def chromium_presente(dados, revisao, navegador=NAVEGADOR_FIXADO):
    pasta = Path(dados) / NOME_NAVEGADORES / ('%s-%s' % (navegador.replace('-', '_'), revisao))
    return (pasta / MARCA_INSTALADO).is_file()


def aval_da_janela(dados):
    """O DA deu o aval para baixar o Chromium com janela (o arquivo do aval existe na pasta de dados)."""
    return (Path(dados) / NOME_AVAL_JANELA).is_file()


def _janela_em_dia(dados):
    """Nada a fazer com o Chromium com janela: ja presente, ou sem aval (entao nao se baixa)."""
    revisao = revisao_do_chromium(Path(dados) / NOME_VENV, NAVEGADOR_JANELA)
    presente = revisao is not None and chromium_presente(dados, revisao, NAVEGADOR_JANELA)
    return presente or not aval_da_janela(dados)


def aviso_sem_janela(dados):
    """Texto que vai junto da linha de situacao enquanto o Chromium com janela falta e o DA nao deu o aval."""
    revisao = revisao_do_chromium(Path(dados) / NOME_VENV, NAVEGADOR_JANELA)
    if revisao is not None and chromium_presente(dados, revisao, NAVEGADOR_JANELA):
        return None
    if aval_da_janela(dados):
        return None
    return ('a tela de briefing precisa do Chromium com janela (%s), que só é baixado com o aval do DA.'
            % TAMANHO_JANELA)


def preparar_chromium_janela(dados, registro, log, executar):
    """Baixa o Chromium com janela fixado para DATA/ms-playwright, so com o aval e so quando ele nao esta la.
    Devolve a linha de aviso (sem o prefixo) quando falha ou falta o aval, ou None. Registra a etapa no preparo.json."""
    venv = Path(dados) / NOME_VENV
    revisao = revisao_do_chromium(venv, NAVEGADOR_JANELA)
    if revisao is None:
        registro['chromium_janela'] = {'situacao': 'falhou', 'revisao': None}
        return ('o Playwright do ambiente não diz qual Chromium com janela usar, e a tela de briefing não abre. '
                'Rode /desdobra:doctor.')
    if chromium_presente(dados, revisao, NAVEGADOR_JANELA):
        registro['chromium_janela'] = {'situacao': 'presente', 'revisao': revisao}
        return None
    if not aval_da_janela(dados):
        registro['chromium_janela'] = {'situacao': 'sem_aval', 'revisao': revisao}
        return aviso_sem_janela(dados)
    inicio = time.monotonic()
    codigo, _texto = executar([python_do_venv(venv), '-I', '-m', 'playwright', 'install', '--no-shell', 'chromium'],
                              log, ambiente={'PLAYWRIGHT_BROWSERS_PATH': Path(dados) / NOME_NAVEGADORES})
    registro['etapas'].append({'etapa': 'chromium_janela', 'codigo': codigo,
                               'tempo_s': round(time.monotonic() - inicio, 3), 'baixado': True})
    if codigo != 0 or not chromium_presente(dados, revisao, NAVEGADOR_JANELA):
        registro['chromium_janela'] = {'situacao': 'falhou', 'revisao': revisao}
        return ('o ambiente Python está pronto, mas o download do Chromium com janela falhou (rede ou proxy), e a '
                'tela de briefing não abre sem ele. Abra uma sessão nova para tentar de novo ou rode /desdobra:doctor.')
    registro['chromium_janela'] = {'situacao': 'baixado', 'revisao': revisao}
    return None


def _juntar(linha, aviso):
    """A linha de situacao com o aviso do Chromium com janela no fim, numa linha so."""
    return linha if not aviso else '%s Também: %s' % (linha, aviso)


def preparar_chromium(dados, registro, log, executar):
    """Baixa o headless shell fixado para DATA/ms-playwright, so quando ele nao esta la. Devolve a linha de aviso
    (sem o prefixo) quando falha, ou None. Registra a etapa e o tempo no preparo.json."""
    venv = Path(dados) / NOME_VENV
    revisao = revisao_do_chromium(venv)
    if revisao is None:
        registro['etapas'].append({'etapa': 'chromium', 'codigo': None, 'tempo_s': 0.0, 'baixado': False})
        registro['chromium'] = {'situacao': 'falhou', 'revisao': None}
        return 'o Playwright do ambiente não diz qual Chromium usar, e o Chromium não foi baixado. Rode /desdobra:doctor.'
    if chromium_presente(dados, revisao):
        registro['etapas'].append({'etapa': 'chromium', 'codigo': 0, 'tempo_s': 0.0, 'baixado': False})
        registro['chromium'] = {'situacao': 'presente', 'revisao': revisao}
        return None
    inicio = time.monotonic()
    codigo, _texto = executar([python_do_venv(venv), '-I', '-m', 'playwright', 'install', '--only-shell', 'chromium'],
                              log, ambiente={'PLAYWRIGHT_BROWSERS_PATH': Path(dados) / NOME_NAVEGADORES})
    registro['etapas'].append({'etapa': 'chromium', 'codigo': codigo, 'tempo_s': round(time.monotonic() - inicio, 3),
                               'baixado': True})
    if codigo != 0 or not chromium_presente(dados, revisao):
        registro['chromium'] = {'situacao': 'falhou', 'revisao': revisao}
        return ('o ambiente Python está pronto, mas o download do Chromium fixado falhou (rede ou proxy), e a '
                'conferência de fontes não roda sem ele. Abra uma sessão nova para tentar de novo ou rode /desdobra:doctor.')
    registro['chromium'] = {'situacao': 'baixado', 'revisao': revisao}
    return None


# ------------------------------------------------------------------ etapas
def _etapa(registro, nome, argv, log, executar, linha_falha, conferir=None):
    inicio = time.monotonic()
    codigo, texto = executar(argv, log)
    registro['etapas'].append({'etapa': nome, 'codigo': codigo, 'tempo_s': round(time.monotonic() - inicio, 3)})
    if codigo != 0 or (conferir is not None and not conferir(texto)):
        raise Falha(nome, linha_falha)
    return texto


def _instalar_motor(raiz, venv, registro, log, executar):
    py = python_do_venv(venv)
    _etapa(registro, 'motor', [py, '-I', '-m', 'pip', 'install', '--no-deps', '--no-build-isolation',
                               '--disable-pip-version-check', '--no-input', '-e', raiz / 'motor'],
           log, executar, 'a instalação do motor no ambiente Python falhou. Rode /desdobra:doctor.')
    _etapa(registro, 'conferir', [py, '-I', '-B', '-m', 'desdobra', '--version'], log, executar,
           'o motor foi instalado, mas não respondeu. Rode /desdobra:doctor.',
           conferir=lambda texto: texto.strip().startswith('desdobra '))


def _recriar(raiz, dados, registro, log, executar, python_base):
    venv = dados / NOME_VENV
    velho = dados / ('venv.velho-%d' % os.getpid())
    if venv.exists():
        try:
            venv.rename(velho)
        except OSError:
            raise Falha('venv_em_uso', 'o ambiente Python precisa ser recriado, mas está em uso por outro processo. '
                                       'Feche as outras sessões do Claude Code e abra uma sessão nova.') from None
    try:
        _etapa(registro, 'venv', [python_base, '-I', '-m', 'venv', venv], log, executar,
               'não consegui criar o ambiente Python. Rode /desdobra:doctor.')
        py = python_do_venv(venv)
        _etapa(registro, 'pip_lock', [py, '-I', '-m', 'pip', 'install', '--require-hashes', '--no-deps',
                                      '--only-binary=:all:', '--disable-pip-version-check', '--no-input',
                                      '-r', raiz / 'motor' / 'requirements.lock'],
               log, executar, 'a instalação das dependências do motor falhou (rede, proxy ou hash). '
                              'Rode /desdobra:doctor.')
        _instalar_motor(raiz, venv, registro, log, executar)
        _etapa(registro, 'pip_check', [py, '-I', '-m', 'pip', 'check'], log, executar,
               'as dependências do motor ficaram inconsistentes. Rode /desdobra:doctor.')
    finally:
        if velho.exists():
            shutil.rmtree(velho, ignore_errors=True)


def preparar(raiz, dados, executar=executar_comando, python_base=None):
    """Prepara o ambiente e devolve a linha de situacao (sem o prefixo)."""
    raiz = Path(raiz)
    dados = Path(dados)
    python_base = python_base or sys.executable
    try:
        aceitas = ler_limite(raiz, 'ambiente.python_versoes_aceitas')
        idade_trava_s = ler_limite(raiz, 'ambiente.trava_preparo_max_s')
    except KeyError:
        return ('o registro de limites do plugin está incompleto, e o ambiente Python não foi preparado. '
                'Reinstale o plugin.')
    versao = versao_menor()
    if versao not in aceitas:
        return ('o Python do PATH é o %s, e o desdobra precisa do Python %s. Instale essa versão, ponha no PATH '
                'do usuário e abra o Claude Code de novo.' % (versao, ' ou '.join(aceitas)))
    try:
        lock_bytes = (raiz / 'motor' / 'requirements.lock').read_bytes()
    except OSError:
        return 'o plugin está sem o arquivo motor/requirements.lock. Reinstale o plugin.'
    try:
        dados.mkdir(parents=True, exist_ok=True)
    except OSError:
        return 'não consegui criar a pasta de dados do plugin. Rode /desdobra:doctor.'

    if situacao_atual(raiz, dados, lock_bytes) == 'pronto' and _chromium_em_dia(dados) and _janela_em_dia(dados):
        return _juntar('ambiente Python pronto (Python %s, sem mudança).' % platform.python_version(),
                       aviso_sem_janela(dados))
    trava = tomar_trava(dados, idade_trava_s)
    if trava is None:
        return ('outra sessão está preparando o ambiente Python agora. Espere alguns minutos e abra uma sessão '
                'nova.')
    try:
        acao = situacao_atual(raiz, dados, lock_bytes)  # outra sessao pode ter terminado enquanto esta esperava
        if acao == 'pronto':
            if _chromium_em_dia(dados) and _janela_em_dia(dados):
                return _juntar('ambiente Python pronto (Python %s, sem mudança).' % platform.python_version(),
                               aviso_sem_janela(dados))
            return _so_chromium(raiz, dados, lock_bytes, executar, python_base)
        return _preparar_com_trava(raiz, dados, lock_bytes, acao, executar, python_base)
    finally:
        try:
            trava.unlink()
        except OSError:
            pass


def _chromium_em_dia(dados):
    revisao = revisao_do_chromium(Path(dados) / NOME_VENV)
    return revisao is not None and chromium_presente(dados, revisao)


def _so_chromium(raiz, dados, lock_bytes, executar, python_base):
    """Caminho rapido de um ambiente pronto sem o Chromium fixado: so o download, com registro."""
    registro = _registro_novo(raiz, lock_bytes, 'chromium', python_base)
    inicio = time.monotonic()
    with open(dados / NOME_LOG, 'w', encoding='utf-8') as log:
        log.write('preparo chromium em %s\n' % registro['inicio'])
        aviso = preparar_chromium(dados, registro, log, executar)
        aviso_janela = preparar_chromium_janela(dados, registro, log, executar)
    registro.update(situacao='ok', fim=agora_iso(), tempo_s=round(time.monotonic() - inicio, 3))
    gravar_json_atomico(dados / NOME_PREPARO, registro)
    if aviso:
        return _juntar(aviso, aviso_janela)
    baixados = [nome for chave, nome in (('chromium', 'o Chromium fixado'), ('chromium_janela', 'o Chromium com janela'))
                if (registro.get(chave) or {}).get('situacao') == 'baixado']
    if not baixados:
        return _juntar('ambiente Python pronto (Python %s, sem mudança).' % platform.python_version(), aviso_janela)
    return _juntar('ambiente Python pronto; %s %s baixado em %d s.' % (
        ' e '.join(baixados), 'foram' if len(baixados) > 1 else 'foi', round(registro['tempo_s'])), aviso_janela)


def _registro_novo(raiz, lock_bytes, acao, python_base):
    return {'esquema': ESQUEMA_PREPARO, 'acao': acao, 'situacao': 'em_andamento', 'inicio': agora_iso(),
            'fim': None, 'tempo_s': None, 'etapa_que_falhou': None, 'lock_sha256': hashlib.sha256(lock_bytes).hexdigest(),
            'plugin_root': str(raiz), 'python_base': str(python_base),
            'python_versao': platform.python_version(), 'etapas': []}


def _preparar_com_trava(raiz, dados, lock_bytes, acao, executar, python_base):
    lock_sha = hashlib.sha256(lock_bytes).hexdigest()
    registro = {'esquema': ESQUEMA_PREPARO, 'acao': acao, 'situacao': 'em_andamento', 'inicio': agora_iso(),
                'fim': None, 'tempo_s': None, 'etapa_que_falhou': None, 'lock_sha256': lock_sha,
                'plugin_root': str(raiz), 'python_base': str(python_base),
                'python_versao': platform.python_version(), 'etapas': []}
    inicio = time.monotonic()
    if acao == 'recriar':
        # sem copia do lock e sem interpretador.json, um preparo cortado no meio refaz tudo na proxima sessao
        for nome in (NOME_INTERPRETADOR, NOME_COPIA_LOCK):
            try:
                (dados / nome).unlink()
            except FileNotFoundError:
                pass
    gravar_json_atomico(dados / NOME_PREPARO, registro)
    linha = None
    aviso_chromium = None
    aviso_janela = None
    with open(dados / NOME_LOG, 'w', encoding='utf-8') as log:
        log.write('preparo %s em %s\n' % (acao, registro['inicio']))
        try:
            if acao == 'recriar':
                _recriar(raiz, dados, registro, log, executar, python_base)
            else:
                _instalar_motor(raiz, dados / NOME_VENV, registro, log, executar)
            aviso_chromium = preparar_chromium(dados, registro, log, executar)
            aviso_janela = preparar_chromium_janela(dados, registro, log, executar)
        except Falha as f:
            registro['situacao'] = 'falhou'
            registro['etapa_que_falhou'] = f.etapa
            linha = f.linha
        except Exception as e:  # noqa: BLE001 - o gancho nunca derruba a sessao; o detalhe fica no log
            log.write(traceback.format_exc())
            registro['situacao'] = 'falhou'
            registro['etapa_que_falhou'] = 'erro_interno_%s' % type(e).__name__
            linha = 'o preparo do ambiente Python parou com um erro interno. Rode /desdobra:doctor.'
    registro['fim'] = agora_iso()
    registro['tempo_s'] = round(time.monotonic() - inicio, 3)
    if linha is not None:
        gravar_json_atomico(dados / NOME_PREPARO, registro)
        return linha
    python = python_do_venv(dados / NOME_VENV)
    gravar_bytes_atomico(dados / NOME_COPIA_LOCK, lock_bytes)
    gravar_json_atomico(dados / NOME_INTERPRETADOR, {
        'esquema': ESQUEMA_INTERPRETADOR, 'python': python.as_posix(), 'plugin_root': raiz.as_posix(),
        'lock_sha256': lock_sha, 'python_versao': platform.python_version(), 'python_versao_menor': versao_menor(),
        'gravado_em': registro['fim']})
    registro['situacao'] = 'ok'
    gravar_json_atomico(dados / NOME_PREPARO, registro)
    if aviso_chromium:
        return _juntar(aviso_chromium, aviso_janela)
    if acao == 'religar':
        return _juntar('ambiente Python pronto; o motor foi religado à versão instalada do plugin.', aviso_janela)
    return _juntar('ambiente Python criado em %d s (Python %s).' % (round(registro['tempo_s']),
                                                                    platform.python_version()), aviso_janela)


def principal():
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, 'reconfigure'):
            fluxo.reconfigure(encoding='utf-8', errors='backslashreplace')
    raiz = os.environ.get('CLAUDE_PLUGIN_ROOT') or str(Path(__file__).resolve().parent.parent)
    dados = os.environ.get('CLAUDE_PLUGIN_DATA')
    if not dados:
        linha = 'o gancho rodou sem a pasta de dados do plugin, e o ambiente Python não foi preparado.'
    else:
        try:
            linha = preparar(raiz, dados)
        except Exception:  # noqa: BLE001 - uma linha so, nunca traceback no contexto da sessao
            linha = 'o preparo do ambiente Python parou com um erro interno. Rode /desdobra:doctor.'
    sys.stdout.write(PREFIXO + linha + '\n')
    sys.stdout.flush()
    return 0


if __name__ == '__main__':
    sys.exit(principal())
