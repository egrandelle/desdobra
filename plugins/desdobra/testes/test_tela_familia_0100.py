# -*- coding: utf-8 -*-
"""0.10.0: a familia na tela com o arquivo de edicao (decisao 199; etapas E5 e E6 do desenho da familia).

  - o rascunho grava o arquivo de edicao da familia pela regra na primeira gravacao e o guarda: a pagina nunca o manda,
    e o arquivo maior que entra depois nao troca (rascunho._com_a_estrutura);
  - a rota da previa recusa a edicao pedida em outro arquivo;
  - a confirmacao leva o arquivo de edicao e o hash do layout de cada arquivo (a impressao da 175); a confirmada antes
    da 0.10.0 cai uma vez, com a frase do motivo; o "Salvar e seguir" recusa a familia cujo layout saiu diferente do
    confirmado e grava o arquivo de edicao nas composicoes do briefing;
  - os atos da janela trocam o arquivo de edicao (so sem edicao), separam um arquivo em familia propria e o juntam de
    volta, e a tela monta as familias de novo;
  - no Chromium: o palco e so do arquivo de edicao, as fichas "Arquivo desta familia" sairam, o cabecalho diz quem o DA
    edita, a faixa "Como fica em cada arquivo" diz em palavras como cada arquivo ficou, o clique na miniatura abre o
    "Ver grande" so para ver (nada e editado nem gravado), e "Conferir os N arquivos" lista primeiro os que pedem
    ajuste, depois os ajustados, e recolhe os iguais.
Tudo sintetico (o KV da diagonal de testes/sinteticos), numa pasta temporaria; nenhum job real. Com a variavel
DESDOBRA_FOTOS_0100 apontando para uma pasta, o teste do Chromium guarda as fotos da tela nela.
"""
import copy
import json
import os
from pathlib import Path

import pytest

import test_familia_diagonal as tfd
import test_tela_escrita as tte
import test_tela_palco as tp
import test_tela_servidor as tts
from desdobra import contratos, plataforma
from desdobra.briefing import modelo as mb
from desdobra.briefing import salvar as bs
from desdobra.tela import atos as ta
from desdobra.tela import edicao as ted
from desdobra.tela import estado as te
from desdobra.tela import rascunho as tr
from desdobra.tela import servidor as ts
from sinteticos import kv_diagonal as KD

PLAT = plataforma.obter()
REF = tfd.REF
VERTICAIS = tfd.VERTICAIS
FORMATOS = tfd.FORMATOS
TELA = (1600, 1000)  # numero-neutro: janela do teste do Chromium, em px


def _job(base):
    if PLAT.nome in ('sem-suporte', 'mac'):
        pytest.skip('sem isolador neste sistema')
    j = KD.criar_job(base, FORMATOS)
    j['conteudo'] = te.montar(j['job'])
    j['el'] = {papel: 'el%d' % lid for papel, lid in j['ids'].items()}
    return j


@pytest.fixture(scope='module')
def diag(tmp_path_factory):
    return _job(tmp_path_factory.mktemp('familia-0100'))


@pytest.fixture
def novo(tmp_path):
    return _job(tmp_path)


def _gid(conteudo):
    return tfd._familia_de(conteudo, REF)


def _grupo(conteudo, gid):
    return next(g for o in conteudo['estado']['orientacoes'] for g in o['grupos'] if g['id'] == gid)


def _servidor(job, conteudo):
    s = ts.ServidorTela(conteudo, pasta=job, modo_teste=True, atos=ta.atos_do_job(job, conteudo=conteudo)).iniciar()
    return s, tts._entrar(s)


def _gravar_rascunho(s, biscoito, familias):
    corpo = {'job_id': s.job_id, 'laudo_sha256': s.laudo_sha256, 'familias': familias}
    return tte._escrever(s, '/api/rascunho', corpo, cookie=biscoito)[0]


def _ler_rascunho(job):
    return json.loads((job / tr.ARQUIVO).read_text(encoding='utf-8'))


def _escrever_rascunho(job, dados):
    contratos.gravar(job / tr.ARQUIVO, dados, tr.ESQUEMA)


# ------------------------------------------------------------------ o arquivo de edicao no rascunho
def test_arquivo_de_edicao_estavel_e_so_do_servidor():
    # a regra so vale enquanto nada foi gravado: o gravado fica enquanto o arquivo esta na familia
    gravadas = {'v': {'versao': None, 'confirmada': False, 'edicoes': [], 'arquivo_de_edicao': 'a'}}
    pagina = {'v': {'versao': None, 'confirmada': False, 'edicoes': []}}
    saida = tr._com_a_estrutura(pagina, gravadas, {'v': ['a', 'b']}, {'v': 'b'})
    assert saida['v']['arquivo_de_edicao'] == 'a'
    # o gravado que saiu da familia da lugar ao que a tela mostra
    saida = tr._com_a_estrutura(pagina, gravadas, {'v': ['b', 'c']}, {'v': 'b'})
    assert saida['v']['arquivo_de_edicao'] == 'b'
    # a familia nova no rascunho grava o da tela; os separados gravados ficam
    gravadas['v']['separados'] = ['c']
    saida = tr._com_a_estrutura(pagina, gravadas, {'v': ['a', 'b']}, {'v': 'b'})
    assert saida['v']['separados'] == ['c']


def test_rascunho_grava_o_arquivo_de_edicao_pela_regra_e_ignora_o_da_pagina(diag):
    job, conteudo = diag['job'], diag['conteudo']
    gid = _gid(conteudo)
    s, biscoito = _servidor(job, conteudo)
    try:
        # a pagina tenta mandar outro arquivo de edicao e um separado: o servidor joga fora
        familias = {gid: {'versao': None, 'confirmada': False, 'edicoes': [], 'arquivo_de_edicao': 'f300x600',
                          'separados': ['f300x600']}}
        assert _gravar_rascunho(s, biscoito, familias) == 200
        f = _ler_rascunho(job)['familias'][gid]
        assert f['arquivo_de_edicao'] == REF and 'separados' not in f
        # a rota da previa recusa a edicao pedida em outro arquivo, e aceita no arquivo de edicao
        pedido = {'familia': gid, 'versao': None, 'edicoes': [], 'quebras': [], 'arquivo': 'f300x600'}
        assert tte._escrever(s, '/api/familia/previa', pedido, cookie=biscoito)[0] != 200
        codigo, _cab, corpo = tte._escrever(s, '/api/familia/previa', dict(pedido, arquivo=REF), cookie=biscoito)
        assert codigo == 200 and json.loads(corpo)['arquivo_de_edicao'] == REF
    finally:
        s.parar()


# ------------------------------------------------------------------ a confirmacao (175) e a migracao
def test_confirmacao_leva_o_arquivo_e_os_layouts_e_a_de_antes_cai_uma_vez(novo):
    job, conteudo = novo['job'], novo['conteudo']
    gid = _gid(conteudo)
    s, biscoito = _servidor(job, conteudo)
    try:
        assert _gravar_rascunho(s, biscoito, {gid: {'versao': None, 'confirmada': False, 'edicoes': []}}) == 200
        codigo, p = tte._pedir_ato(s, biscoito, nome='familia', dados={'familia': gid, 'versao': None,
                                                                        'edicoes': [], 'quebras': []})
        assert codigo == 200 and p['titulo'] == 'Conferir os %d arquivos' % len(VERTICAIS)
        # revisao da 0.10.0: a janela diz o arquivo pela medida, como o passo 5, e nunca pelo id interno
        assert 'o 1080x1920 e os outros' in p['texto'] and REF not in p['texto']
        assert '—' not in p['texto'] and '–' not in p['texto']
        tfd._ato(s, biscoito, 'familia', {'familia': gid, 'versao': None, 'edicoes': [], 'quebras': []})
    finally:
        s.parar()
    dados = _ler_rascunho(job)
    conf = dados['familias'][gid]['confirmacao']
    assert conf['arquivo_de_edicao'] == REF
    previa = conteudo['editar']({'familia': gid, 'versao': None, 'edicoes': [], 'quebras': []})
    assert conf['layouts'] == ted.hash_dos_layouts(previa) and sorted(conf['layouts']) == sorted(VERTICAIS)
    assert gid in te.familias_confirmadas(job, {gid: conteudo['familias'][gid]['formatos']},
                                          pecas={gid: conteudo['familias'][gid]['pecas']})
    # a confirmacao de antes da 0.10.0 (sem o arquivo de edicao) cai uma vez, tambem sem edicao, e a tela diz por que
    velha = copy.deepcopy(dados)
    for k in ('arquivo_de_edicao', 'layouts'):
        velha['familias'][gid]['confirmacao'].pop(k)
    _escrever_rascunho(job, velha)
    outro = te.montar(job)
    g = _grupo(outro, gid)
    assert g['reconfirmar'] == te.RECONFIRMAR_0100
    assert '—' not in te.RECONFIRMAR_0100 and '–' not in te.RECONFIRMAR_0100
    assert gid not in te.familias_confirmadas(job, {gid: outro['familias'][gid]['formatos']},
                                              pecas={gid: outro['familias'][gid]['pecas']})
    assert any(i['texto'] == te.FAMILIA_SEM_CONFIRMACAO for i in outro['estado']['faltam'])
    # confirmada de novo pela tela da 0.10.0, a frase sai
    s, biscoito = _servidor(job, outro)
    try:
        tfd._ato(s, biscoito, 'familia', {'familia': gid, 'versao': None, 'edicoes': [], 'quebras': []})
    finally:
        s.parar()
    assert _grupo(te.montar(job), gid)['reconfirmar'] == ''


def test_salvar_grava_o_arquivo_de_edicao_e_recusa_o_layout_diferente(novo):
    job, conteudo = novo['job'], novo['conteudo']
    gid = _gid(conteudo)
    escolhas = {g: {'versao': tfd._versao_limpa(conteudo, g), 'edicoes': []} for g in conteudo['familias']}
    fids = [f for f, _w, _h, _g in FORMATOS]
    tfd._salvar(job, conteudo, escolhas, tfd._passo_2_diagonal(novo['funcoes']), fids)
    b = mb.ler(job)
    comp = next(c for c in b['composicoes'] if c['familia'] == gid)
    assert comp['arquivo_de_edicao'] == REF and 'layouts' not in (comp['confirmacao'] or {})
    contratos.validar(b, mb.ESQUEMA)
    assert not [p for p in bs.pendencias(job, conteudo) if p['codigo'] == 'layout_diferente_do_confirmado']
    # o layout de um arquivo que nao e o confirmado: o "Salvar e seguir" recusa a familia, com o motivo para o DA
    dados = _ler_rascunho(job)
    dados['familias'][gid]['confirmacao']['layouts']['f300x600'] = '0' * 64
    _escrever_rascunho(job, dados)
    pend = bs.pendencias(job, conteudo)
    # revisao da 0.10.0: o arquivo que mudou vai junto
    assert {'codigo': 'layout_diferente_do_confirmado', 'familia': gid, 'formatos': ['f300x600']} in pend
    motivo = ta.motivo_do_salvar([{'codigo': 'layout_diferente_do_confirmado', 'familia': gid}])
    assert 'confirme a família de novo' in motivo and '—' not in motivo
    motivo = ta.motivo_do_salvar([{'codigo': 'layout_diferente_do_confirmado', 'familia': gid,
                                   'formatos': ['f300x600'], 'nomes': ['300x600'], 'nome_da_familia': '1080x1920'}])
    assert motivo.startswith('O layout do 300x600, na família do 1080x1920, ficou diferente do que você confirmou.')
    assert 'f300x600' not in motivo and '—' not in motivo


def _confirmar_tudo(job, conteudo, funcoes):
    """O rascunho com as familias confirmadas pelas rotas da tela, como o DA faria, e o modo de dados escolhido."""
    gid = _gid(conteudo)
    s, biscoito = _servidor(job, conteudo)
    try:
        fams = {g: {'versao': tfd._versao_limpa(conteudo, g), 'confirmada': False, 'edicoes': [], 'quebras': []}
                for g in conteudo['familias']}
        corpo = dict({'job_id': s.job_id, 'laudo_sha256': s.laudo_sha256, 'familias': fams},
                     **tfd._passo_2_diagonal(funcoes))
        assert tte._escrever(s, '/api/rascunho', corpo, cookie=biscoito)[0] == 200
        tfd._ato(s, biscoito, 'modo_dados', {'modo': 'c'})
        for g, e in fams.items():
            tfd._ato(s, biscoito, 'familia', {'familia': g, 'versao': e['versao'], 'edicoes': [], 'quebras': []})
    finally:
        s.parar()
    # o motor seguinte copia diferente (simulado: o hash gravado de um arquivo nao bate mais)
    dados = _ler_rascunho(job)
    dados['familias'][gid]['confirmacao']['layouts']['f300x600'] = '0' * 64
    _escrever_rascunho(job, dados)
    return gid


def test_salvar_recusado_pelo_layout_tira_a_confirmacao_e_diz_o_arquivo(novo):
    """Revisao da 0.10.0: o "Salvar e seguir" recusado por layout_diferente_do_confirmado era um beco sem saida (a
    familia continuava confirmada, o botao "Confirmar familia" desligado e o rodape dizendo "Tudo confirmado"). Agora a
    familia perde a confirmacao, guarda os arquivos que mudaram, a recusa diz o arquivo e a familia pela medida, e a
    confirmacao de novo pela janela limpa a marca."""
    job = novo['job']
    gid = _confirmar_tudo(job, novo['conteudo'], novo['funcoes'])
    conteudo = te.montar(job)
    s, biscoito = _servidor(job, conteudo)
    try:
        codigo, _c, corpo = tte._escrever(s, '/api/ato/pedir', {'ato': 'salvar', 'dados': {'rascunho': _ler_vista(job)}},
                                          cookie=biscoito)
        assert codigo == 403
        motivo = json.loads(corpo)['motivo']
        assert motivo.startswith('O layout do 300x600, na família do 1080x1920, ficou diferente'), motivo
        f = _ler_rascunho(job)['familias'][gid]
        assert f['confirmada'] is False and 'confirmacao' not in f and f['layout_mudou'] == ['f300x600']
        contratos.validar(_ler_rascunho(job), tr.ESQUEMA)
        # o DA confirma de novo pela janela: a marca sai, e o salvar nao recusa mais pelo layout
        tfd._ato(s, biscoito, 'familia', {'familia': gid, 'versao': tfd._versao_limpa(conteudo, gid), 'edicoes': [],
                                          'quebras': []})
        f = _ler_rascunho(job)['familias'][gid]
        assert f['confirmada'] is True and 'layout_mudou' not in f
        assert not [x for x in bs.pendencias(job, conteudo) if x['codigo'] == 'layout_diferente_do_confirmado']
    finally:
        s.parar()


def test_trocar_com_a_versao_da_galeria_escolhida_diz_que_ela_deixa_de_valer(novo):
    """Revisao da 0.10.0: a familia sem edicao, mas com a versao da galeria escolhida, pode trocar o arquivo de edicao
    (a versao nao e edicao), e a janela diz que a escolha deixa de valer, porque a galeria e do arquivo de edicao.
    Antes ela dizia "nada se perde", e a versao sumia calada."""
    job, conteudo = novo['job'], novo['conteudo']
    gid = _gid(conteudo)
    s, biscoito = _servidor(job, conteudo)
    try:
        assert _gravar_rascunho(s, biscoito, {gid: {'versao': 'v2', 'confirmada': False, 'edicoes': []}}) == 200
        codigo, p = tte._pedir_ato(s, biscoito, nome='familia_arquivo', dados={'familia': gid, 'arquivo': 'f300x600'})
        assert codigo == 200
        assert 'A versão que você escolheu na galeria do 1080x1920 deixa de valer' in p['texto'], p['texto']
        assert 'nada se perde' not in p['texto'] and '—' not in p['texto']
    finally:
        s.parar()


def _ler_vista(job):
    """O rascunho como a pagina o manda ao "Salvar e seguir" (so os campos da pagina)."""
    dados = _ler_rascunho(job)
    return {k: v for k, v in dados.items() if k in tr.CAMPOS_DA_PAGINA + tr.CAMPOS_DAS_ESCOLHAS}


def test_arquivo_de_edicao_que_sai_da_familia_editada_diz_a_troca():
    """Revisao da 0.10.0: o arquivo de edicao gravado sai da familia (o DA tirou o formato no passo 1) com a familia
    ja editada. As edicoes passam a valer no arquivo da regra, e a tela diz isso ate o DA confirmar de novo."""
    fam = {'arquivo_de_edicao': 'f1080x1920', 'edicoes': [{'elemento': 'el1', 'acao': 'mover', 'dx': 0.0, 'dy': 0.01}]}
    grupo = {'arquivo_de_edicao': 'f300x600', 'composicoes': [{'formatos': [{'id': 'f300x600'}, {'id': 'f640x360'}]}]}
    assert te.arquivo_trocado(fam, grupo) == {'de': 'f1080x1920', 'para': 'f300x600'}
    assert te.arquivo_trocado(dict(fam, edicoes=[]), grupo) is None
    frase = te.frase_do_arquivo_trocado('f1080x1920', 'f300x600', {'f1080x1920': '1080x1920', 'f300x600': '300x600'})
    assert frase == ('O arquivo em que você editava esta família, o 1080x1920, saiu dela. As suas edições passam a '
                     'valer no 300x600, o maior arquivo que ficou. Confira a família e confirme de novo.')
    # o rascunho grava a troca so na familia editada, e a confirmacao a limpa
    gravadas = {'g': dict(fam, formatos=['f1080x1920', 'f300x600'])}
    pagina = {'g': {'versao': None, 'confirmada': False, 'edicoes': fam['edicoes']}}
    saida = tr._com_a_estrutura(pagina, gravadas, {'g': ['f300x600', 'f640x360']}, {'g': 'f300x600'})
    assert saida['g']['arquivo_de_edicao'] == 'f300x600'
    assert saida['g']['arquivo_trocado'] == {'de': 'f1080x1920', 'para': 'f300x600'}
    sem = tr._com_a_estrutura({'g': dict(pagina['g'], edicoes=[])}, {'g': dict(gravadas['g'], edicoes=[])},
                              {'g': ['f300x600', 'f640x360']}, {'g': 'f300x600'})
    assert 'arquivo_trocado' not in sem['g']


# ------------------------------------------------------------------ os atos da estrutura
def test_trocar_so_sem_edicao_separar_e_juntar(novo):
    job, conteudo, el = novo['job'], novo['conteudo'], novo['el']
    gid = _gid(conteudo)
    eds = [{'elemento': el['titulo'], 'acao': 'mover', 'dx': 0.0, 'dy': 0.005}]
    s, biscoito = _servidor(job, conteudo)
    try:
        # com edicao, o servidor recusa trocar (as edicoes sao fracoes do arquivo de edicao)
        assert _gravar_rascunho(s, biscoito, {gid: {'versao': None, 'confirmada': False, 'edicoes': eds}}) == 200
        assert tte._pedir_ato(s, biscoito, nome='familia_arquivo',
                              dados={'familia': gid, 'arquivo': 'f300x600'})[0] != 200
        # sem edicao, troca com um clique e a janela do servidor
        assert _gravar_rascunho(s, biscoito, {gid: {'versao': None, 'confirmada': False, 'edicoes': []}}) == 200
        codigo, p = tte._pedir_ato(s, biscoito, nome='familia_arquivo', dados={'familia': gid, 'arquivo': 'f300x600'})
        # revisao da 0.10.0: o arquivo pela medida, nunca pelo id
        assert codigo == 200 and 'no 300x600' in p['texto'] and 'f300x600' not in p['texto'] and '—' not in p['texto']
        assert 'nada se perde' in p['texto']
        tfd._ato(s, biscoito, 'familia_arquivo', {'familia': gid, 'arquivo': 'f300x600'})
        assert _ler_rascunho(job)['familias'][gid]['arquivo_de_edicao'] == 'f300x600'
        # a tela monta as familias de novo: o palco e a previa sao do arquivo novo
        estado = json.loads(tts._pedir(s, '/api/estado', cookie=biscoito)[2])
        g = next(x for o in estado['orientacoes'] for x in o['grupos'] if x['id'] == gid)
        assert g['arquivo_de_edicao'] == 'f300x600'
        pedido = {'familia': gid, 'versao': None, 'edicoes': [], 'quebras': [], 'arquivo': REF}
        assert tte._escrever(s, '/api/familia/previa', pedido, cookie=biscoito)[0] != 200
        codigo, _c, corpo = tte._escrever(s, '/api/familia/previa', dict(pedido, arquivo='f300x600'), cookie=biscoito)
        assert codigo == 200 and json.loads(corpo)['arquivo_de_edicao'] == 'f300x600'
        # o arquivo de edicao nunca se separa; outro arquivo, sim
        assert tte._pedir_ato(s, biscoito, nome='familia_separar',
                              dados={'familia': gid, 'arquivo': 'f300x600'})[0] != 200
        tfd._ato(s, biscoito, 'familia_separar', {'familia': gid, 'arquivo': 'g640x360r90'})
        estado = json.loads(tts._pedir(s, '/api/estado', cookie=biscoito)[2])
        grupos = {x['id']: x for o in estado['orientacoes'] for x in o['grupos']}
        mae = grupos[gid]
        fids_mae = [x['id'] for c in mae['composicoes'] for x in c['formatos']]
        assert 'g640x360r90' not in fids_mae and mae['separados'] == ['g640x360r90'] and not mae['aviso']
        filha = next(x for x in grupos.values() if x.get('separado_de') == gid)
        assert [x['id'] for c in filha['composicoes'] for x in c['formatos']] == ['g640x360r90']
        assert filha['arquivo_de_edicao'] == 'g640x360r90'
        # o arquivo separado tem a previa propria, editada nele mesmo
        codigo, _c, corpo = tte._escrever(s, '/api/familia/previa', {'familia': filha['id'], 'versao': None,
                                                                    'edicoes': [], 'quebras': [],
                                                                    'arquivo': 'g640x360r90'}, cookie=biscoito)
        assert codigo == 200 and [m['formato'] for m in json.loads(corpo)['membros']] == ['g640x360r90']
        # e volta com um clique
        tfd._ato(s, biscoito, 'familia_juntar', {'familia': filha['id']})
        estado = json.loads(tts._pedir(s, '/api/estado', cookie=biscoito)[2])
        mae = next(x for o in estado['orientacoes'] for x in o['grupos'] if x['id'] == gid)
        assert 'g640x360r90' in [x['id'] for c in mae['composicoes'] for x in c['formatos']] and mae['separados'] == []
    finally:
        s.parar()


# ------------------------------------------------------------------ no Chromium sem janela
def _pagina(pw, srv, tela=TELA):
    from desdobra.chromium import navegador
    nav = pw.chromium.launch(headless=True, args=list(navegador.ARGUMENTOS))
    pg = nav.new_context(viewport={'width': tela[0], 'height': tela[1]}, device_scale_factor=1).new_page()
    try:
        pg.goto(srv.url_entrada, wait_until='commit')
    except Exception:  # noqa: BLE001 - o 204 nao completa a navegacao
        pass
    pg.goto(srv.url_pagina, wait_until='load')
    tp._esperar(pg, tp.JS_PRONTO)
    pg.evaluate('() => document.querySelector("#passos [data-passo=pecas]").click()')
    tp._esperar(pg, '() => document.getElementById("palco").dataset.pronto || ""')
    return nav, pg


def _abrir_familia(pg, estado, gid):
    o = next(o for o in estado['orientacoes'] if any(g['id'] == gid for g in o['grupos']))
    tp._clicar_aba(pg, 'orientacoes', o['rotulo'])
    tp._clicar_grupo(pg, gid)
    tp._esperar(pg, '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""')
    tp._esperar(pg, '() => Array.from(document.querySelectorAll("#membros-lista .mini-palco"))'
                    '.every(m => m.querySelector(".peca")) ? "1" : ""')


def _foto(pg, nome, seletor=None):
    pasta = os.environ.get('DESDOBRA_FOTOS_0100')
    if not pasta:
        return
    Path(pasta).mkdir(parents=True, exist_ok=True)
    pg.wait_for_timeout(800)  # numero-neutro: ms, o fim das entradas animadas antes da foto
    alvo = pg.locator(seletor) if seletor else pg
    alvo.screenshot(path=str(Path(pasta) / nome))


def test_tela_palco_so_do_arquivo_de_edicao_e_ver_grande_so_para_ver(diag):
    from playwright.sync_api import sync_playwright

    from desdobra.chromium import navegador
    job, conteudo = diag['job'], diag['conteudo']
    gid = _gid(conteudo)
    antes = _ler_rascunho(job) if (job / tr.ARQUIVO).exists() else None
    navegador.apontar_playwright()
    with ts.ServidorTela(conteudo, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo)) as srv, sync_playwright() as pw:
        nav, pg = _pagina(pw, srv)
        try:
            _abrir_familia(pg, conteudo['estado'], gid)
            vista = pg.evaluate('''() => ({
                fichas: document.querySelectorAll(".ficha, #fichas").length,
                cabecalho: document.querySelector("#cabecalho-familia .cabecalho-texto").textContent,
                palco: document.getElementById("palco").dataset.formato,
                membros: Array.from(document.querySelectorAll("#membros-lista .membro")).map(b => [
                  b.dataset.formato, b.dataset.situacao, b.classList.contains("membro-seu"),
                  (b.querySelector(".selo-copia") || {}).textContent || "",
                  (b.querySelector(".etiqueta-giro") || {}).textContent || "",
                  Math.round(b.querySelector(".membro-quadro").getBoundingClientRect().height)]),
                titulo: document.getElementById("t-membros").textContent})''')
            assert vista['fichas'] == 0
            # revisao da 0.10.0: o arquivo pela medida, como o passo 5; o id interno nunca aparece
            assert vista['cabecalho'] == 'Você edita o 1080x1920. Os outros %d arquivos seguem este layout.' % (
                len(VERTICAIS) - 1)
            assert vista['palco'] == REF and vista['titulo'] == 'Como fica em cada arquivo'
            membros = {m[0]: m for m in vista['membros']}
            assert sorted(membros) == sorted(VERTICAIS) and vista['membros'][0][0] == REF and membros[REF][2]
            # o caso do Duda: o 300x600 sai igual ao seu, sem ajuste; o girado em pe, com a etiqueta do giro com o
            # sentido, a mesma frase do passo 5 (revisao da 0.10.0)
            assert membros['f300x600'][1] == 'igual' and membros['f300x600'][3].startswith('Igual ao seu')
            assert membros['g1920x1080r270'][4] == 'girado 270 graus na entrega'
            assert membros['g640x360r90'][4] == 'girado 90 graus na entrega'
            textos = pg.evaluate('() => document.getElementById("membros").innerText')
            assert not [f for f in VERTICAIS if f in textos], textos
            # o aviso embaixo do selo aparece inteiro, sem reticencias (revisao da 0.10.0)
            notas = pg.evaluate('''() => Array.from(document.querySelectorAll("#membros-lista .selo-nota")).map(n =>
                [n.scrollHeight <= n.clientHeight + 1, getComputedStyle(n).webkitLineClamp])''')
            assert all(ok and clamp in ('none', '') for ok, clamp in notas), notas
            # "Trocar arquivo de edicao" aberto nunca passa da borda direita da janela (revisao da 0.10.0)
            pg.evaluate('() => document.querySelector("#cabecalho-familia .trocar-arquivo").open = true')
            lista = pg.evaluate('''() => { const r = document.querySelector(".trocar-lista").getBoundingClientRect();
                return [r.right, window.innerWidth, document.documentElement.scrollWidth,
                        document.querySelector(".trocar-lista").innerText]; }''')
            assert lista[0] <= lista[1] and lista[2] <= lista[1], lista
            assert '1920x1080' in lista[3] and 'g1920x1080r270' not in lista[3], lista
            pg.evaluate('() => document.querySelector("#cabecalho-familia .trocar-arquivo").open = false')
            assert all(m[5] >= 190 for m in vista['membros']), vista['membros']  # numero-neutro: cerca de 200 px
            for m in vista['membros']:
                assert '—' not in m[3] and '–' not in m[3]
            _foto(pg, '1-palco-do-1080x1920.png')
            _foto(pg, '2-faixa-dos-arquivos.png', '#membros')
            # o titulo do "Ver grande" de um girado diz o giro uma vez so (antes: "girado 270 graus girado 270 graus")
            girado = pg.evaluate('''() => {
                document.querySelector('#membros-lista .membro[data-formato="g1920x1080r270"]').click();
                const t = document.getElementById("ver-grande-titulo").textContent;
                document.getElementById("ver-grande").close();
                return t; }''')
            assert girado == '1920x1080 girado 270 graus. Aqui ele aparece em pé, 1080x1920, como o público vê.', girado
            # o clique na miniatura abre o "Ver grande", so para ver: o palco continua no arquivo de edicao
            pg.evaluate('() => document.querySelector(\'#membros-lista .membro[data-formato="f300x600"]\').click()')
            tp._esperar(pg, '() => document.getElementById("ver-grande").dataset.pronto || ""')
            grande = pg.evaluate('''() => ({
                aberta: document.getElementById("ver-grande").open,
                titulo: document.getElementById("ver-grande-titulo").textContent,
                selo: document.getElementById("ver-grande-selo").textContent,
                pecas: document.querySelectorAll("#ver-grande-palco .peca").length,
                altura: document.getElementById("ver-grande-palco").getBoundingClientRect().height,
                palco: document.getElementById("palco").dataset.formato,
                separar: !!document.querySelector('#ver-grande-atos [data-ato="familia_separar"]')})''')
            assert grande['aberta'] and grande['titulo'] == '300x600' and grande['pecas'] > 0
            assert grande['selo'].startswith('Igual ao seu') and grande['palco'] == REF and grande['separar']
            assert grande['altura'] > 400  # numero-neutro: px, maior que a faixa
            pg.evaluate('() => document.getElementById("ver-grande-por-cima").click()')
            tp._esperar(pg, '() => document.querySelector("#ver-grande-palco .por-cima .contorno-seu") ? "1" : ""')
            # revisao da 0.10.0: no arquivo "Igual ao seu", o contorno do seu arquivo levado pela copia cai em cima de
            # cada elemento (antes, o 1080x1920 centrado mostrava o titulo em dobro e a assinatura sobre o azul)
            pares = pg.evaluate('''() => {
                const area = document.getElementById("ver-grande-palco").getBoundingClientRect();
                return Array.from(document.querySelectorAll("#ver-grande-palco .contorno-seu")).map(d => {
                  const r = d.getBoundingClientRect();
                  const e = document.querySelector('#ver-grande-palco .contorno-ajuste[data-elemento="' +
                    d.dataset.elemento + '"]');
                  return [d.dataset.elemento, r.left - area.left, r.top - area.top, r.width, r.height]; }); }''')
            m300 = next(m for m in conteudo['editar']({'familia': gid, 'versao': None, 'edicoes': []},
                                                       'fixture_de_teste')['membros'] if m['formato'] == 'f300x600')
            por_id = {e['id']: e['caixa'] for e in m300['palco']['elementos'] if e.get('caixa')}
            k = grande['altura'] / m300['palco']['altura']
            assert pares and all(abs(x - por_id[eid][0] * k) <= 1.5 and abs(y - por_id[eid][1] * k) <= 1.5 and
                                 abs(w - (por_id[eid][2] - por_id[eid][0]) * k) <= 1.5 for eid, x, y, w, _h in pares
                                 if eid in por_id), (pares, k)
            _foto(pg, '4-ver-grande-do-300x600.png', '#ver-grande')
            # clicar e arrastar no "Ver grande" nao edita nada
            caixa = pg.locator('#ver-grande-palco').bounding_box()
            pg.mouse.move(caixa['x'] + caixa['width'] / 2, caixa['y'] + caixa['height'] / 2)
            pg.mouse.down()
            pg.mouse.move(caixa['x'] + caixa['width'] / 2 + 30, caixa['y'] + caixa['height'] / 2 + 30)
            pg.mouse.up()
            pg.evaluate('() => document.querySelector("#ver-grande [data-resposta=fechar]").click()')
            assert pg.evaluate('() => document.getElementById("ver-grande").open') is False
            assert pg.evaluate('() => document.getElementById("palco").dataset.formato') == REF
            # "Confirmar familia" abre "Conferir os N arquivos" com a lista
            pg.evaluate('() => document.getElementById("confirmar-familia").click()')
            tp._esperar(pg, '() => document.getElementById("confirmacao").open ? "1" : ""')
            janela = pg.evaluate('''() => ({
                titulo: document.getElementById("confirmacao-titulo").textContent,
                contagem: document.querySelector("#confirmacao .conferir-contagem").textContent,
                itens: Array.from(document.querySelectorAll("#confirmacao .conferir-item")).map(li =>
                  [li.dataset.formato, li.dataset.situacao, li.closest("details") ? "recolhido" : "a vista"])})''')
            assert janela['titulo'] == 'Conferir os %d arquivos' % len(VERTICAIS)
            assert '3 iguais ao seu' in janela['contagem']
            assert ['f300x600', 'igual', 'recolhido'] in janela['itens'] and [REF, 'seu', 'a vista'] in janela['itens']
            pg.evaluate('() => document.querySelector("#confirmacao details.conferir-iguais").open = true')
            _foto(pg, '3-janela-conferir.png', '#confirmacao')
            pg.evaluate('''() => Array.from(document.querySelectorAll("#confirmacao button"))
                .find(b => b.textContent === "Cancelar").click()''')
        finally:
            nav.close()
    # ver, abrir o "Ver grande" e a janela nao gravam edicao nenhuma
    depois = _ler_rascunho(job) if (job / tr.ARQUIVO).exists() else None
    eds = lambda d: ((((d or {}).get('familias') or {}).get(gid) or {}).get('edicoes') or [])  # noqa: E731
    assert eds(depois) == eds(antes) == []


def _com_situacoes(conteudo, gid, mudar):
    """O conteudo com a previa da familia gid mudada por mudar(membros): a janela e a faixa da tela sao conferidas com
    arquivos que pedem ajuste e que o desdobra ajustou (o KV da diagonal sai igual em todos)."""
    real = conteudo['editar']

    def editar(dados, *a, **k):
        r = real(dados, *a, **k)
        if r is not None and dados.get('familia') == gid:
            r = copy.deepcopy(r)
            mudar({m['formato']: m for m in r['membros']})
        return r
    return dict(conteudo, editar=editar)


def test_conferir_lista_os_que_pedem_ajuste_primeiro(diag):
    from playwright.sync_api import sync_playwright

    from desdobra.chromium import navegador
    job, conteudo = diag['job'], diag['conteudo']
    gid = _gid(conteudo)

    def mudar(por):
        por['g640x360r90'].update(situacao='pede_ajuste', falhas=[{
            'codigo': 'relacao_quebrada', 'elementos': [diag['el']['assinatura']],
            'texto': 'A assinatura invade a forma azul em 6,2 px neste arquivo.'}])
        por['g1920x1080r270'].update(situacao='ajustado', ajustes=[{
            'tipo': 'F2', 'elementos': [diag['el']['azul']],
            'frase': 'A forma azul recuou 12 px para a assinatura caber no branco.'}])
    falso = _com_situacoes(conteudo, gid, mudar)
    navegador.apontar_playwright()
    with ts.ServidorTela(falso, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=falso)) as srv, sync_playwright() as pw:
        nav, pg = _pagina(pw, srv)
        try:
            _abrir_familia(pg, falso['estado'], gid)
            selos = pg.evaluate('''() => Object.fromEntries(Array.from(document.querySelectorAll("#membros-lista .membro"))
                .map(b => [b.dataset.formato, b.querySelector(".selo-copia").textContent]))''')
            assert selos['g640x360r90'] == 'Pede ajuste: a assinatura invade a forma azul em 6,2 px neste arquivo.'
            assert selos['g1920x1080r270'] == ('Ajustado pelo desdobra: a forma azul recuou 12 px para a assinatura '
                                               'caber no branco.')
            # o "Ver grande" do ajustado marca em contorno o que o desdobra mexeu
            pg.evaluate('() => document.querySelector(\'#membros-lista .membro[data-formato="g1920x1080r270"]\').click()')
            tp._esperar(pg, '() => document.getElementById("ver-grande").dataset.pronto || ""')
            assert pg.evaluate('() => document.querySelectorAll("#ver-grande-palco .contorno-ajuste").length') == 1
            pg.evaluate('() => document.querySelector("#ver-grande [data-resposta=fechar]").click()')
            pg.evaluate('() => document.getElementById("confirmar-familia").click()')
            tp._esperar(pg, '() => document.getElementById("confirmacao").open ? "1" : ""')
            itens = pg.evaluate('''() => Array.from(document.querySelectorAll("#confirmacao .conferir-item"))
                .map(li => [li.dataset.formato, li.dataset.situacao, li.closest("details") ? 1 : 0])''')
            # as excecoes primeiro: o que pede ajuste, o ajustado, o arquivo de edicao, e os iguais recolhidos
            assert [i[0] for i in itens] == ['g640x360r90', 'g1920x1080r270', REF, 'f300x600'], itens
            assert [i[2] for i in itens] == [0, 0, 0, 1]
            contagem = pg.evaluate('() => document.querySelector("#confirmacao .conferir-contagem").textContent')
            assert contagem == '1 pede ajuste, 1 ajustado pelo desdobra e 1 igual ao seu.'
            # o filtro mostra so os que pedem ajuste
            pg.evaluate('() => document.querySelector(\'#confirmacao .conferir-filtro [data-filtro="pede"]\').click()')
            visiveis = pg.evaluate('''() => Array.from(document.querySelectorAll("#confirmacao .conferir-item"))
                .filter(li => !li.hidden && !(li.closest("details") || {}).hidden).map(li => li.dataset.formato)''')
            assert visiveis == ['g640x360r90']
            pg.evaluate('''() => Array.from(document.querySelectorAll("#confirmacao button"))
                .find(b => b.textContent === "Cancelar").click()''')
        finally:
            nav.close()


# ------------------------------------------------------------------ revisao da 0.10.0, na pagina
JS_ALTURAS = '''() => {
  const peca = document.querySelector("#palco .moldura").getBoundingClientRect();
  const minis = Array.from(document.querySelectorAll("#membros-lista .membro-quadro"))
    .map(q => q.getBoundingClientRect().height);
  return {peca: peca.height, base: peca.bottom, janela: window.innerHeight, minis: minis,
          coluna: document.querySelector(".mesa-palco").classList.contains("faixa-coluna"),
          rola_x: document.documentElement.scrollWidth > window.innerWidth};
}'''


@pytest.mark.parametrize('tela', [(1366, 768), (1280, 800), (1440, 900), (2048, 720)])
def test_palco_do_arquivo_de_edicao_maior_que_as_miniaturas_nas_janelas_comuns(diag, tela):
    """Revisao da 0.10.0: abaixo de 1500 px a faixa ficava embaixo do palco e comia a altura dele (no 1366 x 768, a
    peca com 173 px contra miniaturas de 100). Na janela deitada com o arquivo de edicao em pe, a faixa vira coluna: a
    peca em que o DA edita fica maior que cada miniatura. E, na janela do Duda, a primeira edicao nunca esconde a base
    da peca (a linha acima do palco ja esta a vista desde a abertura)."""
    from playwright.sync_api import sync_playwright

    from desdobra.chromium import navegador
    job, conteudo = diag['job'], diag['conteudo']
    gid = _gid(conteudo)
    navegador.apontar_playwright()
    with ts.ServidorTela(conteudo, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo)) as srv, sync_playwright() as pw:
        nav, pg = _pagina(pw, srv, tela)
        try:
            _abrir_familia(pg, conteudo['estado'], gid)
            m = pg.evaluate(JS_ALTURAS)
            assert m['coluna'] and not m['rola_x'], m
            assert m['minis'] and m['peca'] > max(m['minis']), m
            assert m['base'] <= m['janela'], m
            if tela == (2048, 720):
                # a primeira edicao (a seta na assinatura) faz a linha "Com as suas edicoes" aparecer no lugar da
                # frase de quem edita: a base da peca continua dentro da janela
                antes = pg.evaluate('() => document.getElementById("variante-palco").getBoundingClientRect().height')
                assert antes > 0
                pg.evaluate('''() => document.querySelector('#palco .rotulo[data-elemento="%s"]').focus()'''
                            % diag['el']['assinatura'])
                pg.keyboard.press('ArrowUp')
                tp._esperar(pg, '() => document.getElementById("variante-palco").textContent'
                                '.indexOf("Com as suas edições") >= 0 ? "1" : ""')
                depois = pg.evaluate(JS_ALTURAS)
                assert depois['base'] <= depois['janela'], depois
        finally:
            nav.close()


def test_salvar_recusado_pelo_layout_deixa_confirmar_de_novo_na_pagina(novo):
    """Revisao da 0.10.0, o caminho inteiro na pagina: o layout do 300x600 mudou depois da confirmacao. O clique em
    "Salvar e seguir" e recusado com o nome do arquivo, a familia volta a mostrar "Confirmar familia" ligado, o rodape
    deixa de dizer "Tudo confirmado", e a frase acima do palco diz qual arquivo mudou."""
    from playwright.sync_api import sync_playwright

    from desdobra.chromium import navegador
    job = novo['job']
    gid = _confirmar_tudo(job, novo['conteudo'], novo['funcoes'])
    conteudo = te.montar(job)
    navegador.apontar_playwright()
    with ts.ServidorTela(conteudo, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo)) as srv, sync_playwright() as pw:
        nav, pg = _pagina(pw, srv)
        try:
            _abrir_familia(pg, conteudo['estado'], gid)
            botao = '() => [document.getElementById("confirmar-familia").disabled, ' \
                    'document.getElementById("dica-acoes").textContent]'
            assert pg.evaluate(botao)[0] is True
            pg.evaluate('() => document.getElementById("salvar-seguir").click()')
            tp._esperar(pg, '() => (document.getElementById("aviso-acoes").textContent || "")'
                            '.indexOf("300x600") >= 0 ? "1" : ""')
            aviso = pg.evaluate('() => document.getElementById("aviso-acoes").textContent')
            assert aviso.startswith('O layout do 300x600, na família do 1080x1920, ficou diferente'), aviso
            tp._esperar(pg, '() => document.getElementById("confirmar-familia").disabled ? "" : "1"')
            desligado, dica = pg.evaluate(botao)
            assert desligado is False and 'Tudo confirmado' not in dica, dica
            frase = pg.evaluate('() => document.getElementById("aviso-familia").textContent')
            assert 'O layout do 300x600 ficou diferente do que você confirmou.' in frase, frase
        finally:
            nav.close()
