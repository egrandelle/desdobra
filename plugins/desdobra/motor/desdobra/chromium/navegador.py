# -*- coding: utf-8 -*-
"""Chromium fixado do Playwright para a conferencia de fontes e o render, com perfil temporario num caminho curto.

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

O render (M4, arquitetura-v1.md, 4.11) usa o mesmo navegador com escala 1, --disable-lcd-text, --disable-gpu e o
perfil de cor sRGB forcado (imprimir): cada pagina e gravada em PDF, e os bytes do PDF ficam so na memoria (o
Playwright devolve os bytes do Page.printToPDF, nenhum caminho de arquivo e passado). A varredura do perfil procura
tambem a assinatura de PDF.

O perfil e o cache nunca saem da maquina, ficam numa pasta so do motor e sao apagados no fim; a varredura fica
registrada na conferencia e no render.json (arquitetura-v1.md, 3.4, 7.3, 9.3 e 9.5, teste de cache).

A tela de briefing (M7a1; decisoes-v1.md n 20, 156 e 158; proposta do M7, secao 3, linhas Lancamento, Perfil e
Varredura com a tela aberta) usa o Chromium com janela da mesma revisao (Janela):
  - perfil num caminho curto com prefixo dsd-tela- (perfil_tela), recusado acima de chromium.perfil_caracteres_max,
    com o arquivo do dono dentro (PID e identidade do processo, desdobra.chromium.processos). O dono e gravado numa
    pasta de nascimento e so depois a pasta ganha o nome final: toda pasta dsd-tela- tem dono desde que existe;
  - varrer_orfaos apaga so a pasta dsd-tela- cujo dono morreu (ou cujo dono falta ou nao se le); a de outra tela
    aberta, de outro job, fica;
  - o Python da tela se amarra a um Job Object antes de abrir o Playwright, e o Chromium morre junto com ele;
  - a URL de entrada vai so por page.goto, nunca na linha de comando do Chromium;
  - apagar_perfil tenta de novo (chromium.apagar_perfil_tentativas, com chromium.apagar_perfil_intervalo_s entre as
    tentativas) e so devolve True quando a pasta sumiu; nada e ignorado calado;
  - na varredura do perfil, arquivo ilegivel e contado (arquivos_ilegiveis), e varredura_limpa exige zero copia,
    zero ilegivel e o controle positivo achado.
Risco declarado da janela (decisoes-v1.md, 159, o mesmo da ferramenta que controla a tela da maquina): a janela e um
Chrome for Testing completo, com DevTools, barra de endereco e menus. Quem dirige o teclado e o mouse da maquina (uso
do computador, teclas simuladas) le por ali o cookie HttpOnly e os bytes da fonte, e o servidor nao distingue esses
pedidos dos da pagina, porque vem do Chromium legitimo. O Chromium nao tem opcao de linha de comando que tire o
DevTools (so a politica DeveloperToolsAvailability, que mexe no registro do sistema). A defesa fica nas regras de
permissao do job e no gancho, que nega as teclas simuladas pelo terminal (scripts/gancho_confirmacoes.py).
"""
import hashlib
import json
import os
import shutil
import stat
import tempfile
import time
from pathlib import Path

from desdobra import arquivos, limites
from desdobra.chromium import apontar_playwright

ARGUMENTOS = ('--disable-lcd-text', '--no-first-run', '--disable-background-networking', '--disable-component-update',
              '--disable-sync', '--disable-default-apps', '--disable-extensions',
              '--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE 127.0.0.1')
# render: sem GPU e com o perfil de cor sRGB forcado (arquitetura-v1.md, 4.11)
ARGUMENTOS_RENDER = ARGUMENTOS + ('--disable-gpu', '--force-color-profile=srgb')
ASSINATURA_PDF = b'%PDF-'
PX_POR_POLEGADA = 96.0  # numero-neutro: px do CSS por polegada
JANELA_MEDIDA = {'width': 1200, 'height': 800}  # numero-neutro: janela da pagina de medida (conferir e o aberto)
TAMANHO_TRECHO = 256  # numero-neutro: bytes de cada trecho procurado na varredura do perfil
METODO_VARREDURA = ('sha256, assinatura de fonte e trechos de 256 bytes (inicio, meio e fim) de cada fonte servida, '
                    'em todo arquivo do perfil, com controle positivo (folha de estilo com cache liberado)')
PREFIXO_PERFIL = 'dsd-'
# M7a1: o Chromium com janela da tela
# a janela abre maximizada: o palco usa a tela inteira do DA (decisoes-v1.md, 157: o palco legivel no 2048x720)
ARGUMENTOS_JANELA = ARGUMENTOS + ('--no-proxy-server', '--disable-breakpad', '--start-maximized')
OPCOES_JANELA = {'headless': False, 'no_viewport': True, 'accept_downloads': False, 'service_workers': 'block'}
PREFIXO_PERFIL_TELA = 'dsd-tela-'
PREFIXO_NASCIMENTO = 'dsd-nasce-'
NOME_DONO = 'dsd-dono.json'
ESQUEMA_DONO = 'perfil-dono/1'

JS_CARREGAR = """async (familias) => {
  await Promise.all(familias.map(f => document.fonts.load('16px "' + f + '"').catch(() => null)));
  await document.fonts.ready;
  return Array.from(document.fonts).map(f => [f.family.replace(/^"|"$/g, ''), f.status]);
}"""
JS_POSICOES = """() => { const o = {}; document.querySelectorAll('text[id]').forEach(t => { const a = [];
  for (let i = 0; i < t.getNumberOfChars(); i++) { const s = t.getStartPositionOfChar(i), e = t.getEndPositionOfChar(i);
  a.push([s.x, s.y, e.x]); } o[t.id] = a; }); return o; }"""
JS_LARGURAS = """() => { const o = {}; document.querySelectorAll('.l').forEach(d => {
  const r = document.createRange(); r.selectNodeContents(d); o[d.id] = r.getBoundingClientRect().width; }); return o; }"""
# tinta de cada linha (M7a, fatia 4): [esquerda, direita, subida, descida] em px da pagina, a partir do inicio da
# linha e da linha de base, pela caixa de tinta do canvas com a fonte de cada trecho ja carregada
JS_TINTAS = """() => { const o = {}; const g = document.createElement('canvas').getContext('2d');
  document.querySelectorAll('.l').forEach(d => { const x0 = d.getBoundingClientRect().left; let t = null;
    d.querySelectorAll('span').forEach(s => { const cs = getComputedStyle(s);
      g.font = cs.fontStyle + ' ' + cs.fontWeight + ' ' + cs.fontSize + ' ' + cs.fontFamily;
      g.letterSpacing = cs.letterSpacing === 'normal' ? '0px' : cs.letterSpacing;
      g.fontKerning = cs.fontKerning === 'none' ? 'none' : 'normal';
      const m = g.measureText(s.textContent); const x = s.getBoundingClientRect().left - x0;
      const c = [x - m.actualBoundingBoxLeft, x + m.actualBoundingBoxRight, m.actualBoundingBoxAscent,
                 m.actualBoundingBoxDescent];
      if (!(c[1] > c[0])) return;
      t = t ? [Math.min(t[0], c[0]), Math.max(t[1], c[1]), Math.max(t[2], c[2]), Math.max(t[3], c[3])] : c; });
    if (t) o[d.id] = t; }); return o; }"""


class ErroNavegador(Exception):
    """O Chromium nao abriu ou nao respondeu. A mensagem e texto fixo do motor."""


def versao_playwright():
    try:
        from importlib.metadata import version
        return version('playwright')
    except Exception:  # noqa: BLE001
        return None


def conferir(url_entrada, perfil, familias, ids_cdp):
    """Abre a pagina, mede e consulta o CDP. Devolve {'chromium', 'playwright', 'status', 'larguras', 'tintas', 'cdp'}.

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
                                                        viewport=dict(JANELA_MEDIDA), device_scale_factor=1,
                                                        timeout=tempo_ms)
            try:
                ctx.set_default_timeout(tempo_ms)
                pg = ctx.pages[0] if ctx.pages else ctx.new_page()
                medida = medir_na_pagina(ctx, pg, url_entrada, familias, ids_cdp)
                versao = ctx.browser.version if ctx.browser else None
            finally:
                ctx.close()
    except ErroPlaywright:
        raise ErroNavegador('O Chromium do Playwright não abriu ou não respondeu a tempo.') from None
    return {'chromium': versao, 'playwright': versao_playwright(), **medida}


def medir_na_pagina(ctx, pg, url_entrada, familias, ids_cdp):
    """A medida de conferir na pagina pg do contexto ctx (o caminho frio e o Chromium aberto da tela,
    desdobra.chromium.aberto, medem pelas mesmas linhas). Devolve {'status', 'larguras', 'tintas', 'cdp'}."""
    pg.goto(url_entrada, wait_until='load')
    status = pg.evaluate(JS_CARREGAR, list(familias))
    larguras = pg.evaluate(JS_LARGURAS)
    tintas = pg.evaluate(JS_TINTAS)
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
    return {'status': {f: s for f, s in status}, 'larguras': larguras, 'tintas': tintas, 'cdp': fontes_por_id}


def imprimir_pdf(cdp, largura, altura):
    """Bytes do PDF da pagina aberta, pelo CDP com transferMode ReturnAsBase64: o PDF vem inteiro na resposta.
    O page.pdf() do Playwright pede ReturnAsStream, e o Chromium grava o stream num arquivo temporario (<guid>.tmp na
    pasta temporaria do sistema) antes de entregar; por base64 nada toca o disco."""
    import base64
    r = cdp.send('Page.printToPDF', {'paperWidth': largura / PX_POR_POLEGADA, 'paperHeight': altura / PX_POR_POLEGADA,
                                     'marginTop': 0, 'marginBottom': 0, 'marginLeft': 0, 'marginRight': 0,
                                     'printBackground': True, 'preferCSSPageSize': True, 'scale': 1,
                                     'transferMode': 'ReturnAsBase64'})
    return base64.b64decode(r['data'])


def imprimir(url_entrada, url_pagina, perfil, familias, paginas, depois=None):
    """Abre cada pagina do render, espera as faces, pergunta ao CDP que faces desenharam cada trecho e grava o PDF
    na memoria. paginas: [{'id', 'largura', 'altura', 'spans': [{'id', 'cdp'}], 'pdf', 'posicoes'}]; url_pagina(id)
    da a URL. Pagina com 'posicoes' devolve a posicao de cada caractere de cada linha <text id> (getStartPositionOfChar
    e getEndPositionOfChar, no espaco do texto), e depois(pagina, posicoes) devolve as paginas que entram na fila em
    seguida (o render usa isso para as passadas de cor). Pagina com 'pdf' falso nao e impressa.

    Devolve {'chromium', 'playwright', 'paginas': {id: {'pdf': bytes ou None, 'status': {familia: status},
    'cdp': {span_id: [faces] ou None}, 'posicoes': {linha: [[x inicio, y, x fim], ...]} ou None}}}."""
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
    saida = {}
    try:
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(str(perfil), headless=True, args=list(ARGUMENTOS_RENDER),
                                                        device_scale_factor=1, timeout=tempo_ms)
            try:
                ctx.set_default_timeout(tempo_ms)
                pg = ctx.pages[0] if ctx.pages else ctx.new_page()
                pg.goto(url_entrada, wait_until='load')
                cdp = ctx.new_cdp_session(pg)
                cdp.send('DOM.enable')
                cdp.send('CSS.enable')
                cdp.send('Page.enable')
                fila = list(paginas)
                while fila:
                    p = fila.pop(0)
                    pg.set_viewport_size({'width': int(p['largura']), 'height': int(p['altura'])})
                    pg.goto(url_pagina(p['id']), wait_until='load')
                    status = pg.evaluate(JS_CARREGAR, list(familias))
                    raiz = cdp.send('DOM.getDocument', {'depth': -1})['root']['nodeId']
                    fontes_por_id = {}
                    for s in p['spans']:
                        if not s.get('cdp'):
                            continue
                        no = cdp.send('DOM.querySelector', {'nodeId': raiz, 'selector': '#' + s['id']})['nodeId']
                        if not no:
                            fontes_por_id[s['id']] = None
                            continue
                        fontes_por_id[s['id']] = [
                            {'familia': f.get('familyName'), 'nome_ps': f.get('postScriptName'),
                             'propria': bool(f.get('isCustomFont')), 'glifos': f.get('glyphCount')}
                            for f in cdp.send('CSS.getPlatformFontsForNode', {'nodeId': no})['fonts']]
                    posicoes = pg.evaluate(JS_POSICOES) if p.get('posicoes') else None
                    pdf = None
                    if p.get('pdf', True):
                        pdf = imprimir_pdf(cdp, p['largura'], p['altura'])
                    saida[p['id']] = {'pdf': pdf, 'status': {f: st for f, st in status}, 'cdp': fontes_por_id,
                                      'posicoes': posicoes}
                    if posicoes is not None and depois is not None:
                        fila.extend(depois(p, posicoes))
                versao = ctx.browser.version if ctx.browser else None
            finally:
                ctx.close()
    except ErroPlaywright:
        raise ErroNavegador('O Chromium do Playwright não abriu, não respondeu a tempo ou não gravou o PDF.') from None
    return {'chromium': versao, 'playwright': versao_playwright(), 'paginas': saida}


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
    copias, varridos, controle_achado, pdfs, ilegiveis = 0, 0, False, 0, 0
    if not perfil.is_dir():
        return {'copias_encontradas': 0, 'arquivos_varridos': 0, 'controle_encontrado': False, 'pdfs_encontrados': 0,
                'arquivos_ilegiveis': 0}
    for p in perfil.rglob('*'):
        if not p.is_file():
            continue
        varridos += 1
        try:
            dados = p.read_bytes()
        except OSError:
            # arquivo que nao se le pode guardar a fonte: conta, e varredura_limpa recusa
            ilegiveis += 1
            continue
        if controle and controle in dados:
            controle_achado = True
        if ASSINATURA_PDF in dados:
            pdfs += 1
        if hashlib.sha256(dados).hexdigest() in shas or arquivos.assinatura_de_fonte(dados[:arquivos.BYTES_ASSINATURA]) \
                or any(t in dados for t in procura):
            copias += 1
    return {'copias_encontradas': copias, 'arquivos_varridos': varridos, 'controle_encontrado': controle_achado,
            'pdfs_encontrados': pdfs, 'arquivos_ilegiveis': ilegiveis}


def varredura_limpa(r):
    """A varredura prova perfil sem copia: zero copia, zero PDF, zero arquivo ilegivel e o controle positivo achado."""
    return (not r['copias_encontradas'] and not r['pdfs_encontrados'] and not r.get('arquivos_ilegiveis')
            and bool(r['controle_encontrado']))


def _liberar_e_repetir(funcao, caminho, _exc):
    """rmtree: arquivo so de leitura (o Chromium grava alguns assim) perde a marca e e apagado de novo."""
    os.chmod(caminho, stat.S_IWRITE | stat.S_IREAD)
    funcao(caminho)


def apagar_perfil(perfil):
    """Apaga o perfil e confirma que a pasta sumiu. Tenta de novo enquanto o Chromium ainda segura arquivo; devolve
    False quando a pasta fica depois da ultima tentativa (nunca ignora o erro calado)."""
    perfil = Path(perfil)
    tentativas = int(limites.valor('chromium.apagar_perfil_tentativas'))
    intervalo = float(limites.valor('chromium.apagar_perfil_intervalo_s'))
    for n in range(tentativas):
        if not perfil.exists():
            return True
        try:
            shutil.rmtree(perfil, onexc=_liberar_e_repetir)
        except OSError:
            pass  # arquivo ainda em uso: a proxima tentativa vem depois do intervalo
        if not perfil.exists():
            return True
        if n + 1 < tentativas:
            time.sleep(intervalo)
    return not perfil.exists()


# ------------------------------------------------------------------ perfil da tela (M7a1)
def perfil_tela(pasta_temp=None):
    """Pasta nova do perfil da tela, dsd-tela-<sufixo>, num caminho curto da pasta temporaria do sistema (n 20), com
    o arquivo do dono gravado antes de a pasta ganhar o nome final."""
    from desdobra.chromium import processos
    base = Path(pasta_temp) if pasta_temp is not None else Path(tempfile.gettempdir())
    teto = int(limites.valor('chromium.perfil_caracteres_max'))
    nascendo = Path(tempfile.mkdtemp(prefix=PREFIXO_NASCIMENTO, dir=base))
    destino = base / (PREFIXO_PERFIL_TELA + nascendo.name[len(PREFIXO_NASCIMENTO):])
    try:
        if len(str(destino)) > teto:
            raise ErroNavegador('A pasta temporária do sistema fica num caminho longo demais para o perfil do '
                                'Chromium da tela.')
        dono = {'esquema': ESQUEMA_DONO, 'pid': os.getpid(), 'inicio': processos.identidade(os.getpid())}
        with open(nascendo / NOME_DONO, 'w', encoding='utf-8') as f:
            json.dump(dono, f)
            f.flush()
            os.fsync(f.fileno())
        os.rename(nascendo, destino)
    except BaseException:
        apagar_perfil(nascendo)
        raise
    return destino


def dono_do_perfil(perfil):
    """{'pid', 'inicio'} gravado no perfil da tela, ou None quando o arquivo falta ou nao se le."""
    try:
        with open(Path(perfil) / NOME_DONO, encoding='utf-8') as f:
            dono = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(dono, dict) or dono.get('esquema') != ESQUEMA_DONO or not isinstance(dono.get('pid'), int):
        return None
    return {'pid': dono['pid'], 'inicio': dono.get('inicio')}


def perfil_orfao(perfil):
    """O dono do perfil morreu (ou falta, ou o PID agora e de outro processo)."""
    from desdobra.chromium import processos
    dono = dono_do_perfil(perfil)
    return dono is None or not processos.vivo(dono['pid'], dono['inicio'])


def varrer_orfaos(pasta_temp=None):
    """Apaga as pastas dsd-tela- orfas da pasta temporaria. Devolve {'removidas', 'nao_removidas', 'mantidas'}: quem
    chama avisa o DA quando removeu ou nao conseguiu remover alguma."""
    base = Path(pasta_temp) if pasta_temp is not None else Path(tempfile.gettempdir())
    contagem = {'removidas': 0, 'nao_removidas': 0, 'mantidas': 0}
    try:
        candidatas = sorted(p for p in base.glob(PREFIXO_PERFIL_TELA + '*') if p.is_dir())
    except OSError:
        return contagem
    for p in candidatas:
        if not perfil_orfao(p):
            contagem['mantidas'] += 1
        elif apagar_perfil(p):
            contagem['removidas'] += 1
        else:
            contagem['nao_removidas'] += 1
    return contagem


class Janela:
    """O Chromium com janela da tela, com o perfil `perfil` (de perfil_tela). Uso:

        with Janela(perfil) as j:
            j.ir(url_de_entrada)      # so por page.goto, nunca na linha de comando
            j.esperar_fechar()        # volta quando o DA fecha a janela
        j.perfil_apagado              # True so quando a pasta sumiu

    Antes de abrir o Playwright, o processo se amarra a um Job Object (processos.amarrar_ao_processo): o driver e o
    Chromium morrem junto com ele."""

    def __init__(self, perfil, antes_de_apagar=None):
        # antes_de_apagar(perfil): chamado com o navegador ja fechado e o perfil ainda no disco (a tela varre o perfil
        # inteiro aqui, quando nenhum arquivo esta mais preso pelo Chromium; M7a2)
        self.perfil = Path(perfil)
        self.ctx = None
        self.versao = None
        self.perfil_apagado = None
        self._pw = None
        self._antes_de_apagar = antes_de_apagar

    def __enter__(self):
        # toda recusa antes da janela abrir apaga o perfil aqui: o __exit__ nao roda quando o __enter__ levanta
        # (revisao do M7a0; a amarra recusada, o Playwright ausente e o Chromium que nao abre)
        try:
            self._abrir()
        except BaseException:
            self._encerrar()
            self.perfil_apagado = apagar_perfil(self.perfil)
            raise
        return self

    def _abrir(self):
        from desdobra.chromium import processos
        if not processos.amarrar_ao_processo():
            raise ErroNavegador('O sistema não amarrou o Chromium da tela a este processo, e a tela não abre sem '
                                'isso.')
        apontar_playwright()
        tempo_ms = float(limites.valor('chromium.tempo_max_s')) * 1000  # numero-neutro: segundos para milissegundos
        try:
            from playwright.sync_api import Error as ErroPlaywright
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise ErroNavegador('O Playwright não está instalado no ambiente do motor.') from None
        try:
            self._pw = sync_playwright().start()
            self.ctx = self._pw.chromium.launch_persistent_context(str(self.perfil), args=list(ARGUMENTOS_JANELA),
                                                                   timeout=tempo_ms, **OPCOES_JANELA)
            self.ctx.set_default_timeout(tempo_ms)
            produto = self.ctx.new_cdp_session(self.pagina()).send('Browser.getVersion').get('product') or ''
            self.versao = produto.rsplit('/', 1)[-1] or None
        except ErroPlaywright:
            raise ErroNavegador('O Chromium com janela não abriu ou não respondeu a tempo.') from None

    def pagina(self):
        return self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()

    def ir(self, url):
        pg = self.pagina()
        pg.goto(url, wait_until='load')
        return pg

    def esperar_fechar(self):
        """Espera o DA fechar a janela (o contexto persistente fecha junto com o navegador), sem teto de tempo."""
        self.ctx.wait_for_event('close', timeout=0)

    def _encerrar(self):
        try:
            if self.ctx is not None:
                self.ctx.close()
        except Exception:  # noqa: BLE001 - a janela ja pode ter fechado; o que importa e a pasta sumir
            pass
        try:
            if self._pw is not None:
                self._pw.stop()
        except Exception:  # noqa: BLE001
            pass
        self.ctx, self._pw = None, None

    def __exit__(self, *exc):
        self._encerrar()
        try:
            if self._antes_de_apagar is not None:
                self._antes_de_apagar(self.perfil)
        finally:
            self.perfil_apagado = apagar_perfil(self.perfil)
        return False
