# -*- coding: utf-8 -*-
"""Render da origem (M4, arquitetura-v1.md, 4.11 e 9.5), com PSD e fontes sinteticos gerados na hora.

Criterios de pronto cobertos aqui: determinismo pixel a pixel; 0 PDF na pasta do job, no perfil (cache) e no log
depois do render; 0 arquivo de fonte fora de entrada/fontes/, inclusive no perfil do Chromium, com Cache-Control:
no-store na rota (e o mesmo teste com o cache liberado acha a copia, o que prova a varredura); CDP confirma a face do
arquivo do job em todos os trechos; recusa sem terminal interativo; smart object linkado renderizado com o asset
casado e confirmado, com o sha256 no render.json; autoteste do caminho PDF + PDFium no doctor.
"""
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import test_fontes_apoio as ap
import test_render_apoio as rap
from desdobra import arquivos, contratos, limites
from desdobra.chromium import navegador, servidor
from desdobra.fontes import conferencia
from desdobra.job import nucleo
from desdobra.render import contrato as mc
from desdobra.render import execucao, gama, icc, linkados, texto
from desdobra.resultado import Codigo

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')

def _disparo(monkeypatch=None):
    """Disparo do render com o console simulado (a conferencia do console tem testes proprios)."""
    from desdobra import humano
    original = humano.console_interativo
    humano.console_interativo = lambda: (True, None)
    try:
        return humano.exigir('render')
    finally:
        humano.console_interativo = original


def _job(base, psd, campanha=None):
    fontes = base / 'origem-fontes'
    ap.gravar(fontes, 'inventada.ttf', ap.fonte(ps=rap.FONTE))
    job = base / 'job'
    nucleo.criar(job, psd, 'c', fontes=[fontes], campanha=campanha)
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    return job


@pytest.fixture(scope='module')
def job_render(tmp_path_factory):
    base = tmp_path_factory.mktemp('render')
    job = _job(base, rap.psd_render(base / 'origem' / 'kv.psd'))
    rel = execucao.renderizar(job, disparo=_disparo())
    master = (job / 'render' / 'origem' / 'master.png').read_bytes()
    return {'job': job, 'rel': rel, 'master': master, 'base': base}


def _pixels(dados):
    return np.asarray(Image.open(io.BytesIO(dados)).convert('RGBA'))


# ------------------------------------------------------------------ funcoes puras
def test_mistura_com_gama_bate_com_a_formula_da_pesquisa():
    fg, bg, a = np.array([0.1, 0.2, 0.3]), np.array([0.9, 0.8, 0.7]), np.array([0.4])
    lin = gama.mistura_texto_photoshop(fg, bg, a, None, gama.CURVA_SRGB)
    assert np.allclose(lin, 0.4 * fg + 0.6 * bg)
    G = limites.valor('cor.gama_mistura_texto')
    esperado = gama.srgb_enc((0.4 * gama.srgb_dec(fg) ** (1 / G) + 0.6 * gama.srgb_dec(bg) ** (1 / G)) ** G)
    assert np.allclose(gama.mistura_texto_photoshop(fg, bg, a, G, gama.CURVA_SRGB), esperado)
    # curva de gama pura g: vira potencia nos valores do documento com k = g / G (pesquisa, 3)
    g = 563 / 256
    k = g / G
    pot = (0.4 * fg ** k + 0.6 * bg ** k) ** (1 / k)
    assert np.allclose(gama.mistura_texto_photoshop(fg, bg, a, G, gama.curva_gama(g)), pot)
    assert G == 1.45


def _perfil_curv(gama_u8f8):
    """Perfil ICC minimo so com rTRC, gTRC e bTRC de gama pura (tag curv com 1 ponto)."""
    import struct
    curv = b'curv' + b'\0' * 4 + struct.pack('>I', 1) + struct.pack('>H', gama_u8f8) + b'\0\0'
    n = 3
    inicio = 128 + 4 + 12 * n
    tabela = b''.join(struct.pack('>4sII', t, inicio, len(curv)) for t in (b'rTRC', b'gTRC', b'bTRC'))
    return b'\0' * 128 + struct.pack('>I', n) + tabela + curv


def test_curva_do_perfil_le_curv_e_para():
    dec, enc, desc = icc.curva_do_perfil(_perfil_curv(563))
    assert desc['tipo'] == 'curv' and abs(desc['gama'] - 563 / 256) < 1e-9 and desc['canais_iguais']
    assert np.allclose(dec(np.array([0.5])), 0.5 ** (563 / 256)) and np.allclose(enc(dec(np.array([0.3]))), 0.3)
    from PIL import ImageCms
    srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    dec, enc, desc = icc.curva_do_perfil(srgb)
    xs = np.linspace(0, 1, 11)
    assert desc['tipo'] in ('para', 'curv')
    assert np.abs(dec(xs) - gama.srgb_dec(xs)).max() < 2e-3
    assert np.abs(enc(dec(xs)) - xs).max() < 2e-3
    with pytest.raises(icc.ErroCurva):
        icc.curva_do_perfil(b'\0' * 140)


def test_linhas_do_texto_seguem_as_quebras_e_a_entrelinha():
    t = {'runs': [{'inicio': 0, 'fim': 4, 'texto': 'AB\rC', 'corpo_espaco_texto': 10, 'autoleading': True},
                  {'inicio': 4, 'fim': 7, 'texto': 'DE\r', 'corpo_espaco_texto': 20, 'autoleading': False,
                   'entrelinha': 30}],
         'paragrafos': [{'inicio': 0, 'fim': 7, 'justificacao': 'CENTER', 'auto_leading_fator': 1.5}]}
    linhas = texto.linhas_da_camada(t)
    assert [''.join(s for s, _r in ln['pedacos']) for ln in linhas] == ['AB', 'CDE']
    assert linhas[0]['entrelinha'] == 15 and linhas[1]['entrelinha'] == 30 and linhas[1]['just'] == 'CENTER'


def test_linha_de_varias_cores_fica_num_tspan_com_gradiente_de_paradas_duras():
    """Separar a cor em tspans internos muda o avanco depois da fronteira; a linha fica num tspan so, e a passada de
    cada cor usa um gradiente nas fronteiras medidas pelo Chromium (pesquisa, fronteiras_de_cor)."""
    face = {'id': 'f01', 'peso_declarado': 700, 'metricas': None}
    runs = [{'inicio': 0, 'fim': 2, 'texto': 'AB', 'fonte_ps': 'X', 'corpo_espaco_texto': 20, 'tracking': 0},
            {'inicio': 2, 'fim': 4, 'texto': 'cd', 'fonte_ps': 'X', 'corpo_espaco_texto': 20, 'tracking': 0}]
    entrada = {'id': 'e01', 'regiao': [0, 0, 64, 32], 'texto': {'matriz': [1, 0, 0, 1, 2, 20], 'runs': runs, 'paragrafos': []},
               'cores': ['c0', 'c1'], 'cores_por_trecho': {'0': 'c0', '2': 'c1'}}
    svg, spans, linhas = texto.montar_svg(entrada, {'X': face}, 'p')
    assert svg.count('<tspan') == 1 and linhas == {'L0': ['c0', 'c0', 'c1', 'c1']} and 'fill:#000000' in svg
    with pytest.raises(ValueError):
        texto.montar_svg(entrada, {'X': face}, 'p', 'c1')
    pos = {'L0': [[0, 0, 10], [10, 0, 20], [21, 0, 30], [30, 0, 40]]}
    svg1, _s, _l = texto.montar_svg(entrada, {'X': face}, 'p', 'c1', pos)
    assert svg1.count('<tspan') == 1 and 'url(#gL0)' in svg1 and '<linearGradient id="gL0"' in svg1
    assert 'stop-opacity="0"/><stop offset' in svg1 and len(spans) == 1
    paginas = texto.paginas_da_entrada(entrada, {'X': face}, [face], 'p')
    assert len(paginas) == 1 and paginas[0]['posicoes'] and not paginas[0]['pdf']
    cores = texto.paginas_de_cor(entrada, {'X': face}, [face], 'p', pos)
    assert [p['cor'] for p in cores] == ['c0', 'c1'] and all(p['pdf'] for p in cores)


def test_caixa_alta_nao_quebra_o_atributo_style():
    """A feature cpsp entre aspas duplas fechava o atributo style="..." e o Chromium perdia o cpsp e o fill (achado no
    corpus do M4; a pagina de medicao da conferencia de fontes tinha o mesmo defeito)."""
    from desdobra.fontes import medicao
    face = {'id': 'f01', 'peso_declarado': 700}
    run = {'corpo_espaco_texto': 20, 'tracking': 0, 'font_caps': 'ALL_CAPS'}
    estilo, _ls = texto._estilo(run, face, 'p')
    assert '"' not in estilo and "'cpsp' 1" in estilo
    assert '"' not in medicao._estilo(face, 'p', 20.0, 0.0, run) and "'cpsp' 1" in medicao._estilo(face, 'p', 20.0, 0.0, run)


def test_pagina_do_texto_usa_so_a_rota_local(job_render):
    contrato = contratos.ler(job_render['job'] / 'render' / 'origem' / 'contrato.json', 'composicao/1')
    paginas = execucao.paginas_do_contrato(contrato, 'dsd-teste')
    assert paginas and all("url('/fonte/f" in p['html'] for p in paginas)
    for p in paginas:
        assert 'base64' not in p['html'] and 'local(' not in p['html'] and 'url(data:' not in p['html']
        assert 'https:' not in p['html'] and 'http://127' not in p['html'] and '//fonts.' not in p['html']
        assert p['largura'] % limites.valor('render.pagina_multiplo_px') == 0


# ------------------------------------------------------------------ contrato
def test_contrato_da_origem_separa_pilhas_e_textos(job_render):
    contrato = contratos.ler(job_render['job'] / 'render' / 'origem' / 'contrato.json', 'composicao/1')
    tipos = [e['tipo'] for e in contrato['entradas']]
    assert tipos == ['pilha', 'texto', 'pilha', 'texto']
    t1, t2 = [e for e in contrato['entradas'] if e['tipo'] == 'texto']
    assert len(t1['cores']) == 2 and t1['opacidade'] == 1.0
    assert abs(t2['opacidade'] - 128 / 255) < 1e-6
    assert contrato['faces'] and all(set(f) >= {'id', 'sha256', 'nome_ps'} for f in contrato['faces'])
    texto_json = json.dumps(contrato['faces'])
    assert 'entrada/fontes' not in texto_json


def test_funcao_fora_da_peca_nao_e_desenhada(job_render):
    contrato, bloqueios, _c = mc.montar(job_render['job'])
    quadrado = next(i for e in contrato['entradas'] if e['tipo'] == 'pilha' for i in e['layer_ids'] if i > 1)
    derivado, bloqueios2, _c = mc.montar(job_render['job'], funcoes={quadrado: 'fora_da_peca'})
    assert not bloqueios and not bloqueios2
    assert quadrado in derivado['fora_da_peca']
    assert all(quadrado not in e.get('layer_ids', []) for e in derivado['entradas'])
    assert derivado['origem']['funcoes'] == 'derivacao'


# ------------------------------------------------------------------ render
def test_render_grava_master_e_render_json(job_render):
    rel = contratos.ler(job_render['job'] / 'render' / 'origem' / 'render.json', 'render/1')
    assert rel['master']['sha256'] == hashlib.sha256(job_render['master']).hexdigest()
    assert rel['parametros']['gama']['valor'] == 1.45 and rel['parametros']['supersample']['valor'] == 8
    assert rel['versoes']['chromium'] and rel['versoes']['pdfium'] and rel['versoes']['pypdfium2']
    face = rel['fontes'][0]
    sha_entrada = next(r['sha256'] for k, r in contratos.ler(job_render['job'] / 'estado.json', 'estado/1')['entradas'].items()
                       if k.startswith('entrada/fontes/'))
    assert face['sha256'] == sha_entrada
    img = _pixels(job_render['master'])
    assert img.shape[:2] == (160, 320)
    # o texto escuro esta onde o PSD manda (linha de base em y=44, comecando em x=12) e o quadrado por cima dele
    assert img[30:44, 12:40, :3].min() < 80
    assert tuple(img[50, 170, :3]) == (0, 120, 60)


def test_cdp_confirma_a_face_do_job_em_todos_os_trechos(job_render):
    cdp = job_render['rel']['cdp']
    assert cdp['trechos'] > 0 and cdp['confere'] == cdp['trechos'] and cdp['diverge'] == 0 and cdp['sem_resposta'] == 0


def test_determinismo_pixel_a_pixel(job_render):
    rel2 = execucao.renderizar(job_render['job'], disparo=_disparo())
    segundo = (job_render['job'] / 'render' / 'origem' / 'master.png').read_bytes()
    assert segundo == job_render['master']
    assert np.array_equal(_pixels(segundo), _pixels(job_render['master']))
    assert rel2['pilhas_do_cache'] == 2  # o segundo render nao abre o PSD: as pilhas vem do cache por hash


def _arquivos_com_pdf(pasta, pular=()):
    achados = []
    for p in Path(pasta).rglob('*'):
        if p.is_file() and not any(p.relative_to(pasta).as_posix().startswith(x) for x in pular):
            if b'%PDF-' in p.read_bytes():
                achados.append(p)
    return achados


def test_zero_pdf_e_zero_fonte_fora_da_entrada(job_render):
    job, rel = job_render['job'], job_render['rel']
    assert rel['varredura']['pdfs_no_job'] == 0 and rel['varredura']['arquivos_de_fonte_fora_da_entrada'] == 0
    assert rel['cache']['pdfs_encontrados'] == 0 and rel['cache']['copias_encontradas'] == 0
    assert rel['cache']['controle_encontrado'] is True and rel['cache']['perfil_apagado'] is True
    assert rel['cache']['cache_control'] == 'no-store'
    assert _arquivos_com_pdf(job, pular=('entrada/',)) == []
    assert conferencia.varrer_fontes_fora_da_entrada(job)[0] == 0
    log = (job / 'log' / 'eventos.jsonl').read_bytes() if (job / 'log' / 'eventos.jsonl').is_file() else b''
    assert b'%PDF' not in log
    assert not (job / 'render' / '.trabalho').exists()


def test_teste_de_cache_com_no_store_e_com_cache_liberado(job_render):
    """Confirma a proposta da pergunta 16: com no-store na rota, 0 copia da fonte no perfil; o mesmo render com o cache
    liberado deixa copia, o que prova que a varredura acha."""
    job = job_render['job']
    contrato = contratos.ler(job / 'render' / 'origem' / 'contrato.json', 'composicao/1')
    estado = contratos.ler(job / 'estado.json', 'estado/1')
    servidos = execucao.bytes_das_faces(job, contrato, estado)
    _p, _pg, _cdp, sem, _v = execucao.texto_no_chromium(contrato, servidos, 'dsd-cache', cache_control='no-store')
    _p, _pg, _cdp, com, _v = execucao.texto_no_chromium(contrato, servidos, 'dsd-cache', cache_control='max-age=3600')
    assert sem['controle_encontrado'] and sem['copias_encontradas'] == 0 and sem['pdfs_encontrados'] == 0
    assert com['controle_encontrado'] and com['copias_encontradas'] > 0
    assert sem['perfil_apagado'] and com['perfil_apagado']


def test_pdf_nunca_tem_caminho_de_arquivo():
    import inspect
    fonte = inspect.getsource(navegador.imprimir) + inspect.getsource(navegador.imprimir_pdf)
    assert "'transferMode': 'ReturnAsBase64'" in fonte and 'pg.pdf(' not in fonte and 'path=' not in fonte


def test_rasterizacao_em_faixas_e_igual_a_inteira(job_render, monkeypatch):
    from desdobra.render import filho
    contrato = contratos.ler(job_render['job'] / 'render' / 'origem' / 'contrato.json', 'composicao/1')
    estado = contratos.ler(job_render['job'] / 'estado.json', 'estado/1')
    servidos = execucao.bytes_das_faces(job_render['job'], contrato, estado)
    pdfs, paginas, _cdp, _cache, _v = execucao.texto_no_chromium(contrato, servidos, 'dsd-faixa')
    p = paginas[0]
    e = next(x for x in contrato['entradas'] if x['id'] == p['entrada'])
    rw, rh = e['regiao'][2] - e['regiao'][0], e['regiao'][3] - e['regiao'][1]
    inteira = filho.cobertura_do_pdf(pdfs[p['id']], p['largura'], p['altura'], rw, rh, 8)
    monkeypatch.setattr(filho, 'PIXELS_BANDA', p['largura'] * 64 * 3)
    em_faixas = filho.cobertura_do_pdf(pdfs[p['id']], p['largura'], p['altura'], rw, rh, 8)
    assert inteira.sum() > 0 and np.array_equal(inteira, em_faixas)
    # pagina mais larga que o bitmap que o PDFium desenha: colunas (um titulo largo do corpus cortava em 4000 px)
    monkeypatch.setattr(filho, 'LADO_MAX_PDFIUM', 8 * 37)
    em_colunas = filho.cobertura_do_pdf(pdfs[p['id']], p['largura'], p['altura'], rw, rh, 8)
    assert np.array_equal(inteira, em_colunas)


# ------------------------------------------------------------------ disparo humano
def test_render_recusa_sem_terminal_e_com_envelope(job_render, python):
    job = job_render['job']
    antes = (job / 'render' / 'origem' / 'master.png').stat().st_mtime_ns
    for extra in ([], ['--envelope']):
        r = subprocess.run([python, '-m', 'desdobra', *extra, 'render', '--job', str(job)], capture_output=True,
                           stdin=subprocess.PIPE, timeout=120)
        assert r.returncode == int(Codigo.RECUSADO)
        if extra:
            env = json.loads(r.stdout.decode('utf-8').strip().splitlines()[-1])
            assert env['situacao'] == 'recusado' and 'terminal' in env['o_que_fazer']
    assert (job / 'render' / 'origem' / 'master.png').stat().st_mtime_ns == antes


def test_render_no_terminal_pergunta_sem_resposta_padrao(job_render, pessoa, monkeypatch, capsys):
    from argparse import Namespace

    from desdobra import render
    respostas = iter(['', 'talvez', 'nao'])
    perguntas = []
    monkeypatch.setattr(pessoa, 'ler', lambda p: (perguntas.append(p), next(respostas))[1])
    r = render._render(Namespace(job=str(job_render['job']), formato='origem'))
    assert r.codigo == int(Codigo.RECUSADO) and r.situacao == 'recusado'
    assert len(perguntas) == 3  # Enter vazio e resposta fora da lista repetem a pergunta


def test_divergencia_de_largura_pede_o_aceite_do_da(tmp_path):
    psd = ap.psd_textos(tmp_path / 'origem' / 'kv.psd', [([('ABC', rap.FONTE, 24.0, 0)], ap.largura('ABC', 24.0) * 1.05)])
    job = _job(tmp_path, psd)
    _c, bloqueios, confirmar = mc.montar(job)
    assert not bloqueios and [c['codigo'] for c in confirmar] == ['largura_divergente']
    with pytest.raises(execucao.ErroRender) as e:
        execucao.renderizar(job, disparo=_disparo())
    assert e.value.motivo == 'pede_decisao_do_da' and not (job / 'render' / 'origem' / 'master.png').exists()
    rel = execucao.renderizar(job, disparo=_disparo(), aceites=['largura_divergente'])
    assert rel['aceites'][0]['codigo'] == 'largura_divergente'


def test_fonte_faltando_bloqueia_o_render(tmp_path):
    psd = ap.psd_textos(tmp_path / 'origem' / 'kv.psd', [([('ABC', 'Sumida-Bold', 24.0, 0)], ap.largura('ABC', 24.0))])
    job = _job(tmp_path, psd)
    _c, bloqueios, _conf = mc.montar(job)
    assert 'fonte_bloqueante' in {b['codigo'] for b in bloqueios}
    with pytest.raises(execucao.ErroRender) as e:
        execucao.renderizar(job, disparo=_disparo())
    assert e.value.motivo == 'bloqueio'


# ------------------------------------------------------------------ linkado
def test_linkado_renderiza_com_o_asset_casado_e_confirmado(tmp_path):
    psd, campanha, dados = rap.linkado_com_campanha(tmp_path / 'origem')
    job = tmp_path / 'job'
    nucleo.criar(job, psd, 'c', campanha=campanha)
    assert nucleo.proxima(job, todas=True).codigo == 0
    _c, bloqueios, _conf = mc.montar(job)
    assert [b['codigo'] for b in bloqueios] == ['linkado_sem_confirmacao']
    # o DA confirma no terminal (a sessao com a resposta do DA)
    from desdobra import humano
    resposta = iter(['1'])
    original_ler, original_console = humano.ler, humano.console_interativo
    humano.ler, humano.console_interativo = (lambda _p: next(resposta)), (lambda: (True, None))
    try:
        dados_conf, novos = linkados.sessao(job, disparo=humano.exigir('linkado confirmar'), saida=lambda *_a: None)
    finally:
        humano.ler, humano.console_interativo = original_ler, original_console
    assert novos == 1 and dados_conf['linkados'][0]['arquivo'] == 'entrada/campanha/arte-linkada.png'
    sha = hashlib.sha256(dados).hexdigest()
    assert dados_conf['linkados'][0]['sha256'] == sha
    rel = execucao.renderizar(job, disparo=_disparo())
    assets = [a for a in rel['assets'] if a['tipo'] == 'linkado']
    assert len(assets) == 1 and assets[0]['sha256'] == sha
    img = _pixels((job / 'render' / 'origem' / 'master.png').read_bytes())
    # o asset casado (azul) entra no lugar dos pixels verdes gravados na camada
    assert tuple(img[30, 40, :3]) == (0, 0, 220)
    # o arquivo-isca do caminho gravado no PSD nunca entra em nada que o job gravou
    for p in job.rglob('*.json'):
        assert 'fora-da-entrada' not in p.read_text(encoding='utf-8')


def test_linkado_confirmar_recusa_sem_terminal(tmp_path, python):
    r = subprocess.run([python, '-m', 'desdobra', 'linkado', 'confirmar', '--job', str(tmp_path)], capture_output=True,
                       stdin=subprocess.PIPE, timeout=60)
    assert r.returncode == int(Codigo.RECUSADO)


# ------------------------------------------------------------------ servidor, plataforma e doctor
def test_servidor_serve_varias_paginas_so_com_o_cookie():
    import http.client
    with servidor.ServidorFontes({'p1': '<p>um</p>', 'p2': '<p>dois</p>'}, {}) as s:
        def get(caminho, cookie=None):
            c = http.client.HTTPConnection('127.0.0.1', s.porta, timeout=10)
            c.request('GET', caminho, headers={'Host': '127.0.0.1:%d' % s.porta, **({'Cookie': cookie} if cookie else {})})
            r = c.getresponse()
            return r.status, r.getheader('Location'), r.getheader('Set-Cookie'), r.read()
        st, loc, ck, _ = get('/entrar/%s' % s.token)
        assert st == 303 and loc == '/pagina/p1'
        cookie = ck.split(';')[0]
        assert get('/pagina/p2')[0] == 403
        assert get('/pagina/p2', cookie)[3] == b'<p>dois</p>'
        assert get('/pagina/p3', cookie)[0] == 404 and get('/pagina', cookie)[0] == 404


def test_plataforma_entrega_os_bytes_da_entrada_depois_da_liberacao(tmp_path, python):
    from desdobra import plataforma
    plat = plataforma.obter()
    filho = ('import sys\n'
             'assert sys.stdin.buffer.readline() == b"iniciar\\n"\n'
             'dados = sys.stdin.buffer.read()\n'
             'print(len(dados), dados[:5].decode())\n')
    r = plat.executar_isolado([python, '-I', '-B', '-c', filho], 512 * 1024 * 1024, 60, tmp_path,
                              entrada=b'%PDF-' + b'x' * 300000)
    assert r.situacao == 'ok' and r.codigo == 0 and r.stdout_bytes.split() == [b'300005', b'%PDF-']


def test_autoteste_do_render_com_fonte_gerada_passa():
    from desdobra.doctor import chromium as vc
    from desdobra.render import autoteste
    assert autoteste.REFERENCIA.is_file()
    v = vc.verificar_autoteste_render()
    assert v.situacao == 'ok', v.detalhe
    assert v.numeros['maximo'] <= limites.valor('render.autoteste_max_abs')
    assert v.numeros['cdp_confere'] == v.numeros['cdp_trechos'] > 0
    assert v.numeros['copias_no_cache'] == 0 and v.numeros['pdfs_no_cache'] == 0
    assert limites.obter('render.autoteste_media_max').situacao == 'a_calibrar'
    # a fonte gerada sai igual byte a byte (a imagem de referencia depende disso)
    assert autoteste.gerar_fonte() == autoteste.gerar_fonte()


def test_pacote_nao_leva_arquivo_de_fonte_nem_pdf():
    from desdobra import PASTA_MOTOR
    for p in PASTA_MOTOR.rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:
            assert not arquivos.eh_arquivo_de_fonte(p), p.name
            assert not p.read_bytes().startswith(b'%PDF-'), p.name
