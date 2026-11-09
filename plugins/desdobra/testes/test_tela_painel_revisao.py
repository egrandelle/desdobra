# -*- coding: utf-8 -*-
"""Revisao do M7b, fase B: o que o DA ve no passo 5 (desdobra.tela.estado.painel_dos_formatos e tela/tela.js).

Criterios cobertos aqui:
  - a previa do layout no passo 5 e o layout salvo: depois de editar uma familia e salvar na mesma janela, o formato
    sem render em dia mostra a derivacao gravada (a chave salvo de /api/previa/<id>), e nao a previa da abertura;
  - o aviso do briefing salvo cabe no rodape a 1280 x 800;
  - a figura da janela do lado do giro segue a peca: a peca de pe (master 320 x 640) que sai deitada para o veiculo
    aparece de pe antes do giro e deitada depois, nos dois lados.
Tudo sintetico: o job modelo de test_tela_salvar e o PSD de test_derivacao_apoio, com o meio de teste da tela.
"""
import json
import shutil
import sys

import pytest

import test_cadeia_por_formato as tcp
import test_derivacao_apoio as ap
import test_fontes_apoio as fap
import test_render_apoio as rap
import test_tela_ato_aprovar as taa_t
import test_tela_ato_render as tar
import test_tela_escrita as tte
import test_tela_painel as tpn
import test_tela_salvar as tsv
import test_tela_servidor as tts
from test_tela_ato_aprovar import renderizado  # noqa: F401 - a fixture dos tres formatos renderizados
from test_tela_salvar import modelo  # noqa: F401 - a fixture do job modelo
from desdobra import arquivos, contratos, humano
from desdobra.briefing import modelo as mb
from desdobra.derivacao import nucleo as nd
from desdobra.job import nucleo
from desdobra.render import execucao
from desdobra.tela import estado as te

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')


def _abrir_com_o_biscoito(pw, s, biscoito):
    """A pagina do passo 5 a 1280 x 800 com o cookie que o teste ja tem (a entrada e de uso unico)."""
    import test_tela_palco as tp
    from desdobra.chromium import navegador
    nome, _, valor = biscoito.partition('=')
    nav = pw.chromium.launch(headless=True, args=list(navegador.ARGUMENTOS))
    ctx = nav.new_context(viewport={'width': tpn.LARGURA, 'height': tpn.ALTURA}, device_scale_factor=1)
    ctx.add_cookies([{'name': nome, 'value': valor, 'url': 'http://127.0.0.1:%d/' % s.porta}])
    pg = ctx.new_page()
    pg.goto(s.url_pagina, wait_until='load')
    tp._esperar(pg, tp.JS_PRONTO)
    pg.evaluate('() => document.querySelector("#passos [data-passo=formatos]").click()')
    tp._esperar(pg, '() => document.documentElement.dataset.painel || ""', 'pronto')
    return nav, pg


# ------------------------------------------------------------------ a previa do layout salvo
def test_previa_do_passo_5_e_o_layout_salvo_depois_de_editar_e_salvar(modelo, tmp_path):  # noqa: F811
    from playwright.sync_api import sync_playwright

    import test_tela_palco as tp
    from desdobra.chromium import navegador
    job = tmp_path / 'job'
    shutil.copytree(modelo['job'], job)
    conteudo = te.montar(job)
    s = tsv._servidor(job, conteudo)
    try:
        b = tts._entrar(s)
        escolhas = tsv._preparar_rascunho(job, modelo, s, b, conteudo)
        assert tsv._salvar(s, b, job)[1] == 200
        gv = tsv._familia_de(conteudo, 'v1')
        # o DA desce o titulo da familia vertical, confirma a familia e salva de novo, na mesma janela
        escolhas[gv]['edicoes'][0]['dy'] = 0.1
        assert tsv._gravar_rascunho(s, b, escolhas, tsv._passo_2(modelo['funcoes'])) == 200
        tsv._confirmar_todas(s, b, escolhas)
        cod, p = tte._pedir_ato(s, b, nome='salvar', dados={'rascunho': tsv._vista(job)})
        assert cod == 200, (cod, p)
        assert tte._escrever(s, '/api/ato/confirmar', {'pedido': p['pedido'], 'resposta': 'confirmar'},
                             cookie=b)[0] == 200
        d = contratos.ler(job / 'derivacao' / 'v1.json', 'derivacao/1')
        titulo = next(e for e in d['elementos'] if e['funcao'] == 'titulo')
        estado = json.loads(tts._pedir(s, '/api/estado', cookie=b)[2])
        v1 = next(f for f in estado['painel']['formatos'] if f['id'] == 'v1')
        assert v1['render_em_dia'] is False and v1['layout']
        # a rota da previa leva o layout salvo, com o titulo onde a derivacao gravada o pos
        previa = json.loads(tts._pedir(s, '/api/previa/v1', cookie=b)[2])
        salvo = previa['salvo']
        assert next(e for e in salvo['elementos'] if e['id'] == titulo['id'])['caixa'] == titulo['caixa']
        assert {e['id'] for e in salvo['elementos']} == {e['id'] for e in d['elementos']}
        navegador.apontar_playwright()
        with sync_playwright() as pw:
            nav, pg = _abrir_com_o_biscoito(pw, s, b)
            try:
                pg.evaluate('() => document.querySelector(\'.linha-formato[data-formato="v1"] .linha-abrir\').click()')
                tp._esperar(pg, '() => document.querySelector("#formato-detalhe .ad-quadro").dataset.pronto || ""')
                visto = pg.evaluate('''(eid) => {
                    const r = n => { if (!n) return null; const b = n.getBoundingClientRect();
                      return [b.left, b.top, b.right, b.bottom]; };
                    const s = document.getElementById("salvo"), f = document.querySelector("footer.acoes");
                    return {recortes: Array.from(document.querySelectorAll("#formato-detalhe .ad-previa .recorte"))
                              .map(n => n.dataset.elemento || ""),
                            titulo: r(document.querySelector('#formato-detalhe .ad-previa .recorte[data-elemento="' + eid + '"]')),
                            depois: r(document.querySelector('#formato-detalhe .caixa-depois[data-elemento="' + eid + '"]')),
                            aviso: r(s), aviso_visivel: !s.hidden, rodape: r(f), altura: innerHeight};
                }''', titulo['id'])
            finally:
                nav.close()
    finally:
        s.parar()
    # so os elementos do layout salvo (o logo que a familia apagou fica de fora)
    assert set(visto['recortes']) == {e['id'] for e in d['elementos']}, visto
    # o titulo desenhado cobre o meio da caixa de "onde ficou"
    meio = (visto['depois'][1] + visto['depois'][3]) / 2
    assert visto['titulo'][1] <= meio <= visto['titulo'][3], visto
    # o aviso do briefing salvo cabe no rodape, dentro da janela
    assert visto['aviso_visivel'], visto
    assert visto['aviso'][1] >= visto['rodape'][1] and visto['aviso'][3] <= min(visto['rodape'][3], visto['altura']), visto


# ------------------------------------------------------------------ a figura do giro
FORMATOS_DE_PE = [ap.formato('perto', 400, 240, rotacao={'graus': 0, 'sentido': None}),
                  ap.formato('deitado', 640, 320, rotacao={'graus': 90, 'sentido': None})]
TIPOS_DE_PE = {'perto': ['image/jpeg'], 'deitado': ['image/jpeg', 'image/png']}


@pytest.fixture
def job_de_pe(tmp_path):
    """Dois formatos renderizados por selos de teste presos a cada um; deitado (640 x 320) gira 90 graus para o
    veiculo, entao a peca dele (o master) e de pe, 320 x 640."""
    from desdobra.job import fases as mod_fases
    fontes = tmp_path / 'origem-fontes'
    fap.gravar(fontes, 'inventada.ttf', fap.fonte(ps=rap.FONTE))
    job = tmp_path / 'job'
    nucleo.criar(job, ap.psd_derivacao(tmp_path / 'origem' / 'kv.psd'), 'c', fontes=[fontes])
    assert nucleo.proxima(job, todas=True).codigo == 0
    arquivos.gravar_json_atomico(job / mb.ARQUIVO_FORMATOS, {'tipo': 'formatos_do_job', 'formatos': [
        {'id': f['id'], 'chave': f['chave'], 'campos': taa_t._campos(TIPOS_DE_PE[f['id']])} for f in FORMATOS_DE_PE]})
    estado = nucleo.ler_estado(job)
    estado['fases']['specs']['hash_saidas'] = nucleo.hashes_das_saidas(
        job, next(f for f in mod_fases.ESTEIRA if f.id == 'specs'))
    nucleo.gravar_estado(job, estado)
    assert nucleo.proxima(job, todas=True).codigo == 0
    laudo = contratos.ler(job / mb.ARQUIVO_LAUDO, 'laudo/1')
    b, _ids = ap.briefing_do_job(laudo, FORMATOS_DE_PE)
    b['composicoes'] = [tcp._familia('perto'), tcp._familia('deitado')]
    arq = tmp_path / 'fixture.json'
    arq.write_text(json.dumps(b), encoding='utf-8')
    mb.importar_teste(job, arq)
    nd.derivar(job)
    sessao = humano.abrir_sessao_tela(teste=True)
    try:
        for f in ('perto', 'deitado'):
            _c, _b, pede = execucao.montar_contrato(job, f)
            d = humano.exigir_tela('render', sessao, confirmado=True, alvo=f)
            execucao.renderizar(job, disparo=d, formato=f, aceites=sorted({c['codigo'] for c in pede}))
    finally:
        humano.fechar_sessao_tela(sessao)
    return job


def test_figura_do_giro_mostra_a_peca_de_pe_que_sai_deitada(job_de_pe):
    import io

    from PIL import Image
    from playwright.sync_api import sync_playwright

    import test_tela_palco as tp
    from desdobra.chromium import navegador
    from desdobra.entrega import codificar
    with Image.open(job_de_pe / 'render' / 'deitado' / 'master.png') as m:
        master = m.size
    assert master[0] < master[1]  # a peca e de pe
    navegador.apontar_playwright()
    s = tar._servidor(job_de_pe).iniciar()
    try:
        b = tts._entrar(s)
        with sync_playwright() as pw:
            nav, pg = _abrir_com_o_biscoito(pw, s, b)
            try:
                pg.evaluate('() => document.querySelector(\'.linha-formato[data-formato="deitado"] .linha-marca\').click()')
                pg.evaluate('() => document.getElementById("aprovar-marcados").click()')
                tp._esperar(pg, '() => document.getElementById("sentido").open ? "1" : ""', teto_s=120)
                figuras = pg.evaluate('''() => Array.from(document.querySelectorAll("#sentido .sentido-opcao")).map(b => {
                    const r = n => [+n.getAttribute("x"), +n.getAttribute("y"), +n.getAttribute("width"), +n.getAttribute("height")];
                    const pecas = Array.from(b.querySelectorAll("svg rect.giro-peca")).map(r);
                    const topos = Array.from(b.querySelectorAll("svg rect.giro-topo")).map(r);
                    return {sentido: b.dataset.sentido, pecas: pecas, topos: topos}; })''')
                pg.evaluate('() => document.querySelector("#sentido [data-resposta=nao]").click()')
            finally:
                nav.close()
    finally:
        s.parar()
    assert [f['sentido'] for f in figuras] == ['horario', 'anti_horario'], figuras
    for f in figuras:
        antes, depois = f['pecas']
        fin = codificar.arquivo_final(job_de_pe, 'deitado', sentido=f['sentido'])
        with Image.open(io.BytesIO(fin.dados)) as im:
            final = im.size
        assert antes[2] < antes[3] and depois[2] > depois[3] and final[0] > final[1], (f, final)
        # o topo antes do giro e a borda de cima; depois, uma borda do lado, dentro da peca e da figura
        topo_antes, topo_depois = f['topos']
        assert topo_antes[1] == antes[1] and topo_antes[2] == antes[2]
        assert topo_depois[3] == depois[3] and depois[0] <= topo_depois[0] <= depois[0] + depois[2] - topo_depois[2]
        assert depois[0] + depois[2] <= 148 and depois[1] + depois[3] <= 64  # numero-neutro: o viewBox da figura
        lado = 'direita' if topo_depois[0] > depois[0] else 'esquerda'
        assert lado == ('direita' if f['sentido'] == 'horario' else 'esquerda'), f
    assert not (job_de_pe / 'parametros').exists()  # a janela foi cancelada: nada gravado


# ------------------------------------------------------------------ a imagem de agora na mesma pagina
# os pixels da imagem desenhada na pagina, para comparar com o arquivo no disco
JS_PIXELS = '''(sel) => { const i = document.querySelector(sel); if (!i || !i.complete || !i.naturalWidth) return null;
    const c = document.createElement("canvas"); c.width = i.naturalWidth; c.height = i.naturalHeight;
    const x = c.getContext("2d"); x.drawImage(i, 0, 0); const d = x.getImageData(0, 0, c.width, c.height).data;
    let s = ""; for (let k = 0; k < d.length; k += 8192) s += String.fromCharCode.apply(null, d.subarray(k, k + 8192));
    return [c.width, c.height, btoa(s)]; }'''  # numero-neutro: o tamanho do pedaco da conversao para texto
JS_JANELA_COM_IMAGENS = '''() => { const is = Array.from(document.querySelectorAll("#confirmacao-extra img"));
    return document.getElementById("confirmacao").open && is.length && is.every(i => i.complete && i.naturalWidth > 0)
      ? "1" : ""; }'''


def _rgba(dados):
    import io

    from PIL import Image
    with Image.open(io.BytesIO(dados)) as im:
        return im.size, im.convert('RGBA').tobytes()


def _da_pagina(v):
    import base64
    return (v[0], v[1]), base64.b64decode(v[2])


def _dif(a, b):
    """A diferenca media por canal entre duas imagens do mesmo tamanho (None com tamanhos diferentes)."""
    if a[0] != b[0]:
        return None
    return sum(abs(p - q) for p, q in zip(a[1], b[1])) / len(a[1])


def test_detalhe_e_janela_de_aprovar_mostram_a_imagem_de_agora_na_mesma_pagina(tmp_path, renderizado):  # noqa: F811
    """Segunda revisao do M7b, fase B: a URL de /render/<id> e de /final/<id> e sempre a mesma para o formato, e o
    Chromium reaproveita na mesma pagina a imagem que ja carregou para a URL, mesmo com no-store. Depois que o formato
    muda e e renderizado de novo na mesma janela, o detalhe e a janela de aprovar mostram o master e o arquivo final de
    agora, e nao os de antes (a decisao Q11: o DA confere o arquivo que fica aprovado)."""
    import time

    from playwright.sync_api import sync_playwright

    import test_tela_palco as tp
    from desdobra.chromium import navegador
    job = tmp_path / 'job'
    shutil.copytree(renderizado, job)
    navegador.apontar_playwright()
    s = tar._servidor(job).iniciar()
    pedidos = []

    def marcar_e_pedir(pg, fid):
        pg.evaluate('(f) => document.querySelector(\'.linha-formato[data-formato="\' + f + \'"] .linha-marca\').click()',
                    fid)
        pg.evaluate('() => document.getElementById("aprovar-marcados").click()')
        tp._esperar(pg, JS_JANELA_COM_IMAGENS, teto_s=120)
        time.sleep(0.3)

    def confirmar(pg, teto_s=120):
        pg.evaluate('() => document.querySelector("#confirmacao [data-resposta=sim]").click()')
        tp._esperar(pg, tpn.JS_ATO, 'feito', teto_s=teto_s)

    def detalhe(pg, fid):
        pg.evaluate('(f) => document.querySelector(\'.linha-formato[data-formato="\' + f + \'"] .linha-abrir\').click()',
                    fid)
        tp._esperar(pg, '() => { const q = document.querySelector("#formato-detalhe .ad-quadro");'
                        ' return q && q.dataset.pronto || ""; }')
        time.sleep(0.3)
        return _da_pagina(pg.evaluate(JS_PIXELS, '#formato-detalhe .ad-imagem'))
    try:
        with sync_playwright() as pw:
            nav, pg = tpn._abrir_painel(pw, s)
            pg.on('request', lambda r: pedidos.append(r.url.split('/', 3)[3]))
            try:
                master_1 = (job / 'render' / 'perto' / 'master.png').read_bytes()
                vis_master_1 = detalhe(pg, 'perto')
                marcar_e_pedir(pg, 'perto')
                final_1 = next((job / 'entrega' / 'previa').glob('perto.*')).read_bytes()
                vis_final_1 = _da_pagina(pg.evaluate(JS_PIXELS, '#confirmacao-extra img'))
                confirmar(pg)
                # o briefing muda so em perto, fora da pagina: a familia de perto apaga o texto de apoio
                eid = tpn._caixa(job, 'perto')[0]
                afetados = taa_t._salvar_seletivo(job, lambda b: next(
                    c for c in b['composicoes'] if 'perto' in c['formatos'])['edicoes'].append(
                    {'elemento': eid, 'acao': 'apagar'}))
                assert afetados == ['perto'], afetados
                # a aprovacao de mesma traz o estado novo para a pagina: perto pede render
                marcar_e_pedir(pg, 'mesma')
                confirmar(pg)
                pg.evaluate('() => document.getElementById("renderizar-afetados").click()')
                tp._esperar(pg, '() => document.getElementById("confirmacao").open ? "1" : ""', teto_s=120)
                confirmar(pg, teto_s=600)
                # o render novo derruba a aprovacao de antes de perto (Q2)
                assert dict(tpn._situacoes_na_tela(pg))['perto'] == 'aprovacao_caida'
                master_2 = (job / 'render' / 'perto' / 'master.png').read_bytes()
                vis_master_2 = detalhe(pg, 'perto')
                marcar_e_pedir(pg, 'perto')
                final_2 = next((job / 'entrega' / 'previa').glob('perto.*')).read_bytes()
                vis_final_2 = _da_pagina(pg.evaluate(JS_PIXELS, '#confirmacao-extra img'))
                pg.evaluate('() => document.querySelector("#confirmacao [data-resposta=nao]").click()')
            finally:
                nav.close()
    finally:
        s.parar()
    m1, m2, f1, f2 = _rgba(master_1), _rgba(master_2), _rgba(final_1), _rgba(final_2)
    assert master_1 != master_2 and final_1 != final_2
    # antes da mudanca, a pagina mostra o que estava no disco
    assert _dif(vis_master_1, m1) == 0 and _dif(vis_final_1, f1) == 0
    # depois do render novo, o master e o arquivo final de agora, pedidos de novo ao servidor
    assert _dif(vis_master_2, m2) == 0 and _dif(vis_master_2, m1) > 0, (_dif(vis_master_2, m2), _dif(vis_master_2, m1))
    assert _dif(vis_final_2, f2) < _dif(vis_final_2, f1), (_dif(vis_final_2, f2), _dif(vis_final_2, f1))
    assert len([p for p in pedidos if p == 'render/perto']) >= 2
    assert len([p for p in pedidos if p == 'final/perto']) == 2
