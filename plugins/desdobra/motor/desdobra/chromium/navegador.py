# -*- coding: utf-8 -*-
"""Chromium fixado do Playwright para a conferencia de fontes, com perfil temporario num caminho curto.

  - abre o headless shell do Playwright com um perfil novo numa pasta temporaria curta que o motor cria na maquina
    (perfil_curto) e apaga no fim, sem rede fora do loopback (regra de resolucao de nome que so deixa 127.0.0.1).
    O caminho curto importa: com o perfil num caminho longo (acima de uns 220 caracteres no Windows), o Chromium
    deixa de gravar o cache, e o teste de cache daria 0 copia sem provar nada;
  - carrega a pagina do servidor local (desdobra.chromium.servidor), espera as faces do @font-face, mede a
    largura de cada linha (Range.getBoundingClientRect) e pergunta ao Chromium, pelo protocolo de depuracao
    (CDP, CSS.getPlatformFontsForNode), quais faces desenharam cada elemento;
  - fecha o navegador, varre o perfil atras de copia da fonte (sha256, assinatura de fonte e trechos dos bytes
    servidos) e do controle positivo (uma folha de estilo com marcador aleatorio servida com cache liberado) e apaga
    o perfil. O teste de cache so vale quando o controle aparece no perfil: isso prova que o perfil grava cache.

O perfil e o cache nunca saem da maquina, ficam numa pasta so do motor e sao apagados no fim; a varredura fica
registrada na conferencia (arquitetura-v1.md, 3.4, 7.3 e 9.3, teste de cache).
"""
import hashlib
import shutil
import tempfile
from pathlib import Path

from desdobra import arquivos, limites
from desdobra.chromium import apontar_playwright

ARGUMENTOS = ('--disable-lcd-text', '--no-first-run', '--disable-background-networking', '--disable-component-update',
              '--disable-sync', '--disable-default-apps', '--disable-extensions',
              '--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE 127.0.0.1')
TAMANHO_TRECHO = 256  # numero-neutro: bytes de cada trecho procurado na varredura do perfil
METODO_VARREDURA = ('sha256, assinatura de fonte e trechos de 256 bytes (inicio, meio e fim) de cada fonte servida, '
                    'em todo arquivo do perfil, com controle positivo (folha de estilo com cache liberado)')
PREFIXO_PERFIL = 'dsd-'

JS_CARREGAR = """async (familias) => {
  await Promise.all(familias.map(f => document.fonts.load('16px "' + f + '"').catch(() => null)));
  await document.fonts.ready;
  return Array.from(document.fonts).map(f => [f.family.replace(/^"|"$/g, ''), f.status]);
}"""
JS_LARGURAS = """() => { const o = {}; document.querySelectorAll('.l').forEach(d => {
  const r = document.createRange(); r.selectNodeContents(d); o[d.id] = r.getBoundingClientRect().width; }); return o; }"""


class ErroNavegador(Exception):
    """O Chromium nao abriu ou nao respondeu. A mensagem e texto fixo do motor."""


def versao_playwright():
    try:
        from importlib.metadata import version
        return version('playwright')
    except Exception:  # noqa: BLE001
        return None


def conferir(url_entrada, perfil, familias, ids_cdp):
    """Abre a pagina, mede e consulta o CDP. Devolve {'chromium', 'playwright', 'status', 'larguras', 'cdp'}.

    familias: nomes de familia do @font-face para esperar; ids_cdp: ids de elemento para o CDP."""
    perfil = Path(perfil)
    shutil.rmtree(perfil, ignore_errors=True)
    perfil.mkdir(parents=True)
    apontar_playwright()
    tempo_ms = float(limites.valor('chromium.tempo_max_s')) * 1000  # numero-neutro: segundos para milissegundos
    try:
        from playwright.sync_api import Error as ErroPlaywright
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ErroNavegador('O Playwright não está instalado no ambiente do motor.') from None
    try:
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(str(perfil), headless=True, args=list(ARGUMENTOS),
                                                        viewport={'width': 1200, 'height': 800},  # numero-neutro: janela de medicao
                                                        device_scale_factor=1, timeout=tempo_ms)
            try:
                ctx.set_default_timeout(tempo_ms)
                pg = ctx.pages[0] if ctx.pages else ctx.new_page()
                pg.goto(url_entrada, wait_until='load')
                status = pg.evaluate(JS_CARREGAR, list(familias))
                larguras = pg.evaluate(JS_LARGURAS)
                cdp = ctx.new_cdp_session(pg)
                cdp.send('DOM.enable')
                cdp.send('CSS.enable')
                raiz = cdp.send('DOM.getDocument', {'depth': -1})['root']['nodeId']
                fontes_por_id = {}
                for ident in ids_cdp:
                    no = cdp.send('DOM.querySelector', {'nodeId': raiz, 'selector': '#' + ident})['nodeId']
                    if not no:
                        fontes_por_id[ident] = None
                        continue
                    fontes_por_id[ident] = [{'familia': f.get('familyName'), 'nome_ps': f.get('postScriptName'),
                                             'propria': bool(f.get('isCustomFont')), 'glifos': f.get('glyphCount')}
                                            for f in cdp.send('CSS.getPlatformFontsForNode', {'nodeId': no})['fonts']]
                versao = ctx.browser.version if ctx.browser else None
            finally:
                ctx.close()
    except ErroPlaywright:
        raise ErroNavegador('O Chromium do Playwright não abriu ou não respondeu a tempo.') from None
    return {'chromium': versao, 'playwright': versao_playwright(),
            'status': {f: s for f, s in status}, 'larguras': larguras, 'cdp': fontes_por_id}


def trechos(dados):
    """Trechos dos bytes servidos que a varredura procura (inicio, meio e fim)."""
    n = len(dados)
    if n <= TAMANHO_TRECHO:
        return [bytes(dados)]
    meio = n // 2
    return [bytes(dados[:TAMANHO_TRECHO]), bytes(dados[meio:meio + TAMANHO_TRECHO]), bytes(dados[-TAMANHO_TRECHO:])]


def perfil_curto():
    """Pasta nova e vazia para o perfil do Chromium, num caminho curto da pasta temporaria do sistema."""
    return Path(tempfile.mkdtemp(prefix=PREFIXO_PERFIL))


def varrer_perfil(perfil, servidos, controle=None):
    """Conta os arquivos do perfil que guardam copia de uma fonte servida. servidos: lista de bytes servidos;
    controle: o marcador do controle positivo (bytes), que tem de aparecer no perfil para o teste valer.

    Uma copia e: sha256 igual ao de um arquivo servido, assinatura de fonte no inicio, ou um dos trechos de algum
    arquivo servido dentro dele (o cache grava a resposta com cabecalhos antes do corpo)."""
    perfil = Path(perfil)
    shas = {hashlib.sha256(d).hexdigest() for d in servidos}
    procura = [t for d in servidos for t in trechos(d)]
    copias, varridos, controle_achado = 0, 0, False
    if not perfil.is_dir():
        return {'copias_encontradas': 0, 'arquivos_varridos': 0, 'controle_encontrado': False}
    for p in perfil.rglob('*'):
        if not p.is_file():
            continue
        varridos += 1
        try:
            dados = p.read_bytes()
        except OSError:
            continue
        if controle and controle in dados:
            controle_achado = True
        if hashlib.sha256(dados).hexdigest() in shas or arquivos.assinatura_de_fonte(dados[:arquivos.BYTES_ASSINATURA]) \
                or any(t in dados for t in procura):
            copias += 1
    return {'copias_encontradas': copias, 'arquivos_varridos': varridos, 'controle_encontrado': controle_achado}


def apagar_perfil(perfil):
    shutil.rmtree(perfil, ignore_errors=True)
    return not Path(perfil).exists()
