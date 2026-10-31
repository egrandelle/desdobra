# -*- coding: utf-8 -*-
"""Verificacoes do doctor para a conferencia de fontes (arquitetura-v1.md, 4.15 e 9.3).

  - versao fixada do fontTools e do Playwright (so pelos metadados instalados: o processo principal nunca importa o
    fontTools);
  - o Chromium fixado: o headless shell da revisao que o Playwright instalado pede, na pasta de navegadores que o
    motor usa (no ambiente do plugin, <pasta de dados>/ms-playwright, baixado pelo gancho de preparo);
  - um carregamento de verdade de uma fonte sintetica pelo @font-face, servida pela rota propria no loopback, com a
    conferencia por CDP de que a face usada e a do arquivo.

A fonte sintetica nasce num processo filho com o fontBuilder (retangulos, sem desenho de letra), numa pasta
temporaria do doctor apagada no fim. Ela nunca vai para o pacote, para log nem para o doctor.json: so os numeros.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from desdobra import chromium, limites
from desdobra.doctor.verificacoes import Verificacao, versao_instalada, versoes_do_lock

NOME_PS_SINTETICA = 'DesdobraDoctor-Regular'
FAMILIA_SINTETICA = 'dsd-doctor-f01'
TEXTO_SONDA = 'ABC'
# Filho que grava a fonte sintetica: so o fontBuilder, nada de arquivo de cliente.
FILHO_FONTE_SINTETICA = (
    'import sys\n'
    'from fontTools.fontBuilder import FontBuilder\n'
    'from fontTools.pens.ttGlyphPen import TTGlyphPen\n'
    'cars = "ABC"\n'
    'fb = FontBuilder(1000, isTTF=True)\n'
    'nomes = [".notdef"] + ["g%d" % i for i in range(len(cars))]\n'
    'fb.setupGlyphOrder(nomes)\n'
    'fb.setupCharacterMap({ord(c): "g%d" % i for i, c in enumerate(cars)})\n'
    'glifos, metricas = {}, {}\n'
    'for n in nomes:\n'
    '    pen = TTGlyphPen(None)\n'
    '    if n != ".notdef":\n'
    '        pen.moveTo((50, 0)); pen.lineTo((50, 700)); pen.lineTo((450, 700)); pen.lineTo((450, 0)); pen.closePath()\n'
    '    glifos[n] = pen.glyph(); metricas[n] = (500, 50)\n'
    'fb.setupGlyf(glifos)\n'
    'fb.setupHorizontalMetrics(metricas)\n'
    'fb.setupHorizontalHeader(ascent=800, descent=-200)\n'
    'fb.setupNameTable({"familyName": "DesdobraDoctor", "styleName": "Regular", "psName": sys.argv[2]})\n'
    'fb.setupOS2(usWeightClass=400, sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)\n'
    'fb.setupPost()\n'
    'fb.save(sys.argv[1])\n'
)
O_QUE_FAZER_CHROMIUM = ('O Chromium fixado não está na pasta de navegadores do desdobra. Abra uma sessão nova do Claude '
                        'Code para o gancho baixar o Chromium. Se o problema voltar, veja o preparo.log na pasta de '
                        'dados do plugin e mande o doctor.json para a Trezion.')
O_QUE_FAZER_FONTE = ('O Chromium fixado não carregou a fonte de teste pelo @font-face, ou o CDP não confirmou a face. '
                     'Sem isso a conferência de fontes não roda. Mande o doctor.json para a Trezion.')


def verificar_versao(nome, ident, titulo, caminho_lock=None):
    """O pacote instalado na versao fixada do lock (so metadados: nada e importado)."""
    v = Verificacao(ident, titulo)
    try:
        fixada = versoes_do_lock(caminho_lock).get(nome)
    except OSError:
        fixada = None
    instalada = versao_instalada(nome)
    v.detalhe = '%s %s (fixada %s).' % (nome, instalada or 'ausente', fixada or 'fora do lock')
    if instalada is None or fixada is None or instalada != fixada:
        v.situacao = 'falha'
        v.o_que_fazer = ('O %s não está na versão fixada do lock. Apague a cópia requirements.lock da pasta de dados '
                         'do plugin e abra uma sessão nova, para o gancho recriar o ambiente.' % nome)
    return v


def verificar_chromium(pasta=None, arquivo_browsers=None):
    """O headless shell da revisao fixada pelo Playwright instalado, na pasta de navegadores do motor."""
    v = Verificacao('chromium_fixado', 'Chromium fixado do Playwright')
    revisao, versao = chromium.revisao_fixada(arquivo_browsers)
    pasta = Path(pasta) if pasta is not None else (chromium.pasta_navegadores() or chromium.pasta_padrao_do_playwright())
    exe = chromium.executavel_fixado(pasta, revisao)
    v.detalhe = 'Headless shell revisão %s (Chromium %s) em %s: %s.' % (
        revisao or 'desconhecida', versao or 'desconhecido', pasta, 'presente' if exe else 'ausente')
    if revisao is None or exe is None:
        v.situacao = 'falha'
        v.o_que_fazer = O_QUE_FAZER_CHROMIUM
    return v


def _gerar_fonte(destino, tempo_s):
    proc = subprocess.run([sys.executable, '-I', '-B', '-c', FILHO_FONTE_SINTETICA, str(destino), NOME_PS_SINTETICA],
                          capture_output=True, timeout=tempo_s, stdin=subprocess.DEVNULL)
    return proc.returncode == 0 and Path(destino).is_file()


def verificar_fonte_no_chromium():
    """Carrega a fonte sintetica no Chromium fixado pelo @font-face servido no loopback e confere por CDP."""
    from desdobra.chromium import navegador, servidor
    v = Verificacao('fonte_no_chromium', 'Fonte carregada pelo @font-face no Chromium fixado, com conferência por CDP')
    tempo_s = float(limites.valor('chromium.tempo_max_s'))
    v.limite = limites.obter('chromium.tempo_max_s').citacao()
    pagina = ("<!doctype html><html><head><style>@font-face{font-family:'%s';src:url('/fonte/f01');font-weight:400}"
              "</style></head><body><div class='l' id='s' style=\"font-family:'%s';font-weight:400\">%s</div>"
              "</body></html>" % (FAMILIA_SINTETICA, FAMILIA_SINTETICA, TEXTO_SONDA))
    with tempfile.TemporaryDirectory(prefix='desdobra-doctor-') as pasta:
        arquivo = Path(pasta) / 'sintetica.ttf'
        if not _gerar_fonte(arquivo, tempo_s):
            v.situacao = 'falha'
            v.detalhe = 'O fontTools não gerou a fonte sintética do teste.'
            v.o_que_fazer = O_QUE_FAZER_FONTE
            return v
        dados = arquivo.read_bytes()
        arquivo.unlink()
    perfil = navegador.perfil_curto()
    try:
        with servidor.ServidorFontes(pagina, {'f01': (dados, 'font/ttf')}) as srv:
            r = navegador.conferir(srv.url_entrada, perfil, [FAMILIA_SINTETICA], ['s'])
    except navegador.ErroNavegador as e:
        v.situacao = 'falha'
        v.detalhe = str(e)
        v.o_que_fazer = O_QUE_FAZER_FONTE
        return v
    finally:
        copias = navegador.varrer_perfil(perfil, [dados])['copias_encontradas']
        navegador.apagar_perfil(perfil)
    carregada = r['status'].get(FAMILIA_SINTETICA) == 'loaded'
    faces = r['cdp'].get('s')
    confere = bool(faces) and all(f['propria'] and f['nome_ps'] == NOME_PS_SINTETICA for f in faces)
    v.numeros = {'carregada': int(carregada), 'cdp_confere': int(confere), 'copias_no_cache': copias}
    v.detalhe = 'Chromium %s: fonte %s, CDP %s, %d cópia(s) no cache.' % (
        r['chromium'], 'carregada' if carregada else 'não carregada',
        'confere com o arquivo' if confere else ('sem resposta' if faces is None else 'mostra outra face'), copias)
    if not carregada or not confere:
        v.situacao = 'falha'
        v.o_que_fazer = O_QUE_FAZER_FONTE
    return v
