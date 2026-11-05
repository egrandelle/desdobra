# -*- coding: utf-8 -*-
"""Chromium fixado do Playwright e o servidor local da rota da fonte do job (M2).

O Chromium fixado e o headless shell da revisao que a versao fixada do Playwright pede (driver/package/browsers.json
do pacote instalado). No ambiente do plugin, o gancho de preparo baixa o headless shell para
<pasta de dados do plugin>/ms-playwright, e o motor aponta o Playwright para la (PLAYWRIGHT_BROWSERS_PATH). Fora do
ambiente do plugin (desenvolvimento), vale o padrao do Playwright, a nao ser que PLAYWRIGHT_BROWSERS_PATH ja venha
definido.
"""
import json
import os
import sys
from pathlib import Path

NOME_INTERPRETADOR = 'interpretador.json'
PASTA_NAVEGADORES = 'ms-playwright'
NAVEGADOR_FIXADO = 'chromium-headless-shell'
VARIAVEL_NAVEGADORES = 'PLAYWRIGHT_BROWSERS_PATH'
# o executavel do headless shell dentro da pasta da revisao, por sistema (layout do Playwright)
EXECUTAVEL = {'win32': ('chrome-headless-shell-win64', 'chrome-headless-shell.exe'),
              'darwin': ('chrome-headless-shell-mac-arm64', 'chrome-headless-shell'),
              'linux': ('chrome-headless-shell-linux64', 'chrome-headless-shell')}
MARCA_INSTALADO = 'INSTALLATION_COMPLETE'
# M7a1: o Chromium com janela da tela (Chrome for Testing), pelo layout do Playwright
NAVEGADOR_JANELA = 'chromium'
EXECUTAVEL_JANELA = {'win32': ('chrome-win64', 'chrome.exe'),
                     'darwin': ('chrome-mac-arm64', 'Google Chrome for Testing.app', 'Contents', 'MacOS',
                                'Google Chrome for Testing'),
                     'linux': ('chrome-linux64', 'chrome')}
_EXECUTAVEIS = {NAVEGADOR_FIXADO: EXECUTAVEL, NAVEGADOR_JANELA: EXECUTAVEL_JANELA}


def pasta_dados_do_plugin():
    """A pasta de dados do plugin, quando o motor roda no venv que o gancho criou (DATA/venv); senao None."""
    if sys.prefix == sys.base_prefix:
        return None
    candidata = Path(sys.prefix).parent
    return candidata if (candidata / NOME_INTERPRETADOR).is_file() else None


def pasta_navegadores():
    """Pasta dos navegadores do Playwright que o motor usa, ou None para o padrao do Playwright."""
    definida = os.environ.get(VARIAVEL_NAVEGADORES)
    if definida:
        return Path(definida)
    dados = pasta_dados_do_plugin()
    return dados / PASTA_NAVEGADORES if dados is not None else None


def pasta_padrao_do_playwright():
    """A pasta padrao do Playwright quando PLAYWRIGHT_BROWSERS_PATH nao vem (documentacao do Playwright)."""
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local') / PASTA_NAVEGADORES
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Caches' / PASTA_NAVEGADORES
    return Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache') / PASTA_NAVEGADORES


def apontar_playwright():
    """Poe PLAYWRIGHT_BROWSERS_PATH no ambiente do processo quando o motor roda no ambiente do plugin."""
    pasta = pasta_navegadores()
    if pasta is not None:
        os.environ[VARIAVEL_NAVEGADORES] = str(pasta)
    return pasta


def revisao_fixada(arquivo_browsers=None, navegador=NAVEGADOR_FIXADO):
    """(revisao, versao do navegador) que o Playwright instalado pede para `navegador` (o headless shell, ou o
    Chromium com janela com NAVEGADOR_JANELA), ou (None, None)."""
    if arquivo_browsers is None:
        try:
            import playwright
        except ImportError:
            return None, None
        arquivo_browsers = Path(playwright.__file__).parent / 'driver' / 'package' / 'browsers.json'
    try:
        with open(arquivo_browsers, encoding='utf-8') as f:
            dados = json.load(f)
    except (OSError, ValueError):
        return None, None
    for b in dados.get('browsers') or []:
        if b.get('name') == navegador:
            return b.get('revision'), b.get('browserVersion')
    return None, None


def executavel_fixado(pasta, revisao, sistema=None, navegador=NAVEGADOR_FIXADO):
    """Caminho do executavel de `navegador` (headless shell por padrao) da revisao dentro da pasta dos navegadores,
    ou None se nao esta instalado."""
    if pasta is None or revisao is None:
        return None
    partes = _EXECUTAVEIS[navegador].get(sistema or sys.platform)
    raiz = Path(pasta) / ('%s-%s' % (navegador.replace('-', '_'), revisao))
    if not partes or not (raiz / MARCA_INSTALADO).is_file():
        return None
    exe = raiz.joinpath(*partes)
    return exe if exe.is_file() else None
