# -*- coding: utf-8 -*-
"""M7b, B5: o painel de situacao por formato da tela (desdobra.tela.estado.painel_dos_formatos), com a lista "o que
mudou" da fase A, o historico de versoes so para leitura e os botoes "Renderizar os afetados" e "Aprovar" ligados aos
atos do B2 e do B4 (decisoes do Duda Q2, Q3, Q4, Q11, Q12, Q13 e Q14).

Criterio de pronto do plano: o DA ve, sem abrir arquivo, quais formatos cairam, por que e o que mudou em cada um.
Cobertos aqui:
  - a situacao de cada formato: sem layout, layout pronto (derivado), render parado (pede render), render
    desatualizado, renderizado, aprovado e aprovacao caida, com o motivo numa frase simples e a marca de pede render;
  - "o que mudou": os itens da ultima versao do historico que mexeu no formato (briefing/historico/mudancas), com a
    caixa de antes e de depois, ate o formato ser aprovado de novo; arquivo mexido ou ilegivel fica de fora;
  - o historico de versoes, da mais nova para a mais antiga, com a data, a origem e os formatos afetados;
  - o estado servido traz o painel na montagem e depois de cada ato (recarregar);
  - no Chromium, a 1280 px de largura: as linhas, o antes e o depois sobre a imagem, o render dos afetados com uma
    confirmacao, a aprovacao com a imagem final na janela e o lado do giro escolhido na janela, sem rolagem lateral.
Tudo sintetico: o job de test_tela_ato_aprovar (PSD de test_derivacao_apoio, fonte inventada, tres formatos
renderizados por selos de teste) e o meio de teste da tela.
"""
import json
import re
import shutil
import sys

import pytest

import test_cadeia_por_formato as tcp
import test_derivacao_apoio as ap
import test_tela_ato_aprovar as taa_t
import test_tela_ato_render as tar
import test_tela_servidor as tts
from test_tela_ato_aprovar import renderizado  # noqa: F401 - a fixture do job renderizado
from desdobra import arquivos, contratos, humano
from desdobra.briefing import historico
from desdobra.briefing import modelo as mb
from desdobra.briefing import salvar
from desdobra.derivacao import nucleo as nd
from desdobra.entrega import nucleo_aprovar
from desdobra.job import nucleo
from desdobra.tela import estado as te

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')

IDS = taa_t.IDS
NOMES = taa_t.NOMES
SITUACOES = ('sem_derivacao', 'derivado', 'pede_render', 'desatualizado', 'renderizado', 'aprovado',
             'aprovacao_caida')
TRACO = re.compile('[–—]')


@pytest.fixture
def job(renderizado, tmp_path):  # noqa: F811
    destino = tmp_path / 'job'
    shutil.copytree(renderizado, destino)
    return destino


def _painel(job):
    return {f['id']: f for f in te.painel_dos_formatos(job)['formatos']}


def _aprovar(job, formatos):
    """A aprovacao pelo nucleo comum com o selo de teste da tela (o caminho do ato de aprovar, sem a janela)."""
    sessao = humano.abrir_sessao_tela(teste=True)
    try:
        with nucleo.Trava(job):
            conf = nucleo_aprovar.conferir(job, formatos)
            d = humano.exigir_tela('aprovar', sessao, confirmado=True)
            nucleo_aprovar.confirmar(job, formatos, nucleo_aprovar.vista(conf), d)
    finally:
        humano.fechar_sessao_tela(sessao)


def _caixa(job, fid):
    """O id e a caixa do elemento do texto de apoio no formato fid (o que a troca de funcao mexe)."""
    lid = tcp._ids(job)['texto-apoio']
    d = contratos.ler(job / nd.PASTA / ('%s.json' % fid), nd.ESQUEMA)
    e = next(e for e in d['elementos'] if lid in (e.get('layer_ids') or []) and e.get('caixa'))
    return e['id'], [float(v) for v in e['caixa']]


def _mudar_so_perto(job, itens=None):
    """A troca de funcao da camada que so existe em perto, gravada como o salvar seletivo grava: o briefing com o
    historico (a entrada nova no indice com os afetados), o que mudou em briefing/historico/mudancas/<seq>.json e a
    derivacao so de perto. itens: os da diferenca (por padrao, uma frase de funcao e um moveu com as caixas)."""
    lid = tcp._ids(job)['texto-apoio']
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    next(x for x in b['funcoes'] if x['layer_id'] == lid).update(funcao=ap.decisao('informacao_de_evento'))
    if itens is None:
        eid, c = _caixa(job, 'perto')
        itens = [{'tipo': 'funcao', 'elemento': eid, 'frase': 'O texto de apoio virou informação de evento.'},
                 {'tipo': 'moveu', 'elemento': eid, 'frase': 'O texto de apoio desceu 24 px.',
                  'antes': [c[0], c[1] - 24, c[2], c[3] - 24], 'depois': c}]
    mb.gravar_com_historico(job, b, afetados=['perto'])
    salvar._gravar_mudancas(job, {'perto': itens})
    nd.derivar(job, so=['perto'])
    return itens


# ------------------------------------------------------------------ situacao por formato
def test_tres_formatos_renderizados_pedem_aprovacao(job):
    p = te.painel_dos_formatos(job)
    assert [f['id'] for f in p['formatos']] == IDS
    for f in p['formatos']:
        assert f['nome'] == NOMES[f['id']]
        assert f['situacao'] == 'renderizado' and f['rotulo'] == te.ROTULOS_DA_SITUACAO['renderizado'], f
        assert f['pede_render'] is False and f['pode_aprovar'] is True and f['render_em_dia'] is True
        assert f['motivo'] == te.MOTIVOS_DO_PAINEL['renderizado'] and f['mudou'] is None
    assert p['afetados'] == []
    # o formato girado diz o giro, e o lado dele ainda falta (a janela de aprovar pergunta)
    giro = _painel(job)['giro']
    assert (giro['giro'], giro['sentido']) == (90, None) and (_painel(job)['perto']['giro'], 0) == (0, 0)
    assert giro['composicao'] == [640, 320]


def test_aprovado_e_aprovacao_caida_com_o_que_mudou(job):
    _aprovar(job, ['perto', 'mesma'])
    p = _painel(job)
    assert [p[f]['situacao'] for f in IDS] == ['aprovado', 'aprovado', 'renderizado']
    assert p['perto']['pode_aprovar'] is False and p['perto']['motivo'] == te.MOTIVOS_DO_PAINEL['aprovado']
    itens = _mudar_so_perto(job)
    p = te.painel_dos_formatos(job)
    por = {f['id']: f for f in p['formatos']}
    perto = por['perto']
    assert perto['situacao'] == 'aprovacao_caida' and perto['pede_render'] is True and perto['pode_aprovar'] is False
    assert nucleo_aprovar.MOTIVOS_DA_QUEDA['impressao_formato'] in perto['motivo']
    assert te.PEDE_RENDER_DEPOIS_DA_QUEDA in perto['motivo']
    seq = historico.ler(job)['entradas'][-1]['seq']
    assert perto['mudou']['versao'] == seq and perto['mudou']['itens'] == itens
    assert perto['mudou']['quando_texto']
    # os outros ficam como estavam, sem nada em "o que mudou"
    assert (por['mesma']['situacao'], por['mesma']['mudou']) == ('aprovado', None)
    assert (por['giro']['situacao'], por['giro']['mudou']) == ('renderizado', None)
    assert p['afetados'] == ['perto']


def test_render_desatualizado_pede_render(job):
    _mudar_so_perto(job)
    perto = _painel(job)['perto']
    assert perto['situacao'] == 'desatualizado' and perto['pede_render'] is True
    assert perto['render_em_dia'] is False and perto['pode_aprovar'] is False
    assert perto['motivo'] == te.MOTIVOS_DO_PAINEL['desatualizado'] and perto['mudou']['itens']


def test_sem_render_render_parado_e_sem_layout(job):
    shutil.rmtree(job / 'render' / 'mesma')
    for nome in ('master.png', 'render.json', 'contrato.json'):
        (job / 'render' / 'giro' / nome).unlink()
    arquivos.gravar_json_atomico(job / 'render' / 'giro' / 'parada.json', {'formato': 'giro', 'motivo': 'parado'})
    p = _painel(job)
    assert p['mesma']['situacao'] == 'derivado' and p['mesma']['pede_render'] is True
    assert p['mesma']['motivo'] == te.MOTIVOS_DO_PAINEL['derivado']
    assert p['giro']['situacao'] == 'pede_render' and p['giro']['pede_render'] is True
    assert p['giro']['motivo'] == te.MOTIVOS_DO_PAINEL['pede_render']
    # a parada por outro problema diz que parou por um problema
    arquivos.gravar_json_atomico(job / 'render' / 'giro' / 'parada.json', {'formato': 'giro', 'motivo': 'memoria'})
    assert _painel(job)['giro']['motivo'] == te.RENDER_PAROU_POR_PROBLEMA
    # o render em dia vale mais que a parada de uma tentativa depois dele (ou que a parada ilegivel): nada a refazer
    (job / 'render' / 'perto' / 'parada.json').write_text('{', encoding='utf-8')
    assert _painel(job)['perto']['situacao'] == 'renderizado' and _painel(job)['perto']['pede_render'] is False
    (job / nd.PASTA / 'perto.json').unlink()
    p = te.painel_dos_formatos(job)
    perto = next(f for f in p['formatos'] if f['id'] == 'perto')
    assert perto['situacao'] == 'sem_derivacao' and perto['pede_render'] is False and perto['pode_aprovar'] is False
    assert perto['motivo'] == te.MOTIVOS_DO_PAINEL['sem_derivacao']
    assert p['afetados'] == ['mesma', 'giro']


def test_master_mexido_derruba_o_render(job):
    arq = job / 'render' / 'mesma' / 'master.png'
    arq.write_bytes(arq.read_bytes() + b'\0')
    assert _painel(job)['mesma']['situacao'] == 'desatualizado'


def test_o_que_mudou_ilegivel_ou_mexido_fica_de_fora(job):
    _mudar_so_perto(job)
    seq = historico.ler(job)['entradas'][-1]['seq']
    arq = job / salvar.PASTA_MUDANCAS / ('%d.json' % seq)
    dados = arquivos.ler_json(arq)
    dados['formatos']['perto'][0]['frase'] = 7
    arquivos.gravar_json_atomico(arq, dados)
    assert _painel(job)['perto']['mudou'] is None
    arq.write_text('{', encoding='utf-8')
    assert _painel(job)['perto']['mudou'] is None
    # o arquivo com outro numero no nome que o seq dentro dele nao conta
    shutil.copy(job / salvar.PASTA_MUDANCAS / ('%d.json' % seq), job / salvar.PASTA_MUDANCAS / 'x.json')
    assert _painel(job)['perto']['mudou'] is None


def test_o_que_mudou_some_quando_o_formato_e_aprovado_de_novo(job):
    _mudar_so_perto(job)
    sessao = humano.abrir_sessao_tela(teste=True)
    try:
        from desdobra.render import execucao
        _c, _b, pede = execucao.montar_contrato(job, 'perto')
        d = humano.exigir_tela('render', sessao, confirmado=True, alvo='perto')
        execucao.renderizar(job, disparo=d, formato='perto', aceites=sorted({c['codigo'] for c in pede}))
    finally:
        humano.fechar_sessao_tela(sessao)
    perto = _painel(job)['perto']
    assert perto['situacao'] == 'renderizado' and perto['mudou'] is not None
    _aprovar(job, ['perto'])
    assert _painel(job)['perto']['mudou'] is None


# ------------------------------------------------------------------ historico
def test_historico_de_versoes_do_mais_novo_para_o_mais_antigo(job):
    antes = (historico.ler(job) or {'entradas': []})['entradas']
    _mudar_so_perto(job)
    h = te.painel_dos_formatos(job)['historico']
    assert len(h) == len(antes) + 1
    assert [x['versao'] for x in h] == sorted((x['versao'] for x in h), reverse=True)
    novo = h[0]
    assert novo['formatos'] == ['400x240'] and novo['origem_texto'] == te.ORIGENS_DA_VERSAO['teste']
    assert novo['formatos_texto'] == 'Mudou o formato 400x240.'
    assert re.match(r'^\d{2}/\d{2}/\d{4}, \d{2}:\d{2}$', novo['quando_texto']), novo
    # a gravacao sem os afetados calculados diz que eles nao foram registrados
    dados = historico.ler(job)
    for e in dados['entradas']:
        e['formatos_afetados'] = None
    contratos.gravar(job / historico.ARQUIVO, dados, historico.ESQUEMA)
    h = te.painel_dos_formatos(job)['historico'][0]
    assert h['formatos'] is None and h['formatos_texto'] == te.SEM_AFETADOS_REGISTRADOS
    dados['entradas'][-1]['formatos_afetados'] = []
    contratos.gravar(job / historico.ARQUIVO, dados, historico.ESQUEMA)
    assert te.painel_dos_formatos(job)['historico'][0]['formatos_texto'] == te.NENHUM_AFETADO


def test_origem_da_versao_em_palavras():
    assert te.origem_da_versao({'origem': 'da', 'meio': 'tela'}) == te.ORIGENS_DA_VERSAO['tela']
    assert te.origem_da_versao({'origem': 'da', 'meio': 'terminal'}) == te.ORIGENS_DA_VERSAO['fora']
    assert te.origem_da_versao({'origem': 'fixture_de_teste', 'meio': 'medicao'}) == te.ORIGENS_DA_VERSAO['teste']
    assert te.origem_da_versao({'origem': None, 'meio': None}) == te.ORIGENS_DA_VERSAO['sem_registro']


def test_job_sem_briefing_da_painel_vazio(tmp_path):
    p = te.painel_dos_formatos(tmp_path)
    assert p == {'formatos': [], 'historico': [], 'afetados': []}


# ------------------------------------------------------------------ o estado servido
def test_estado_da_tela_traz_o_painel_na_montagem_e_depois_do_ato(job):
    c = te.montar(job)
    assert [f['id'] for f in c['estado']['painel']['formatos']] == IDS
    _aprovar(job, ['mesma'])
    novo = c['recarregar']()
    assert {f['id']: f['situacao'] for f in novo['painel']['formatos']}['mesma'] == 'aprovado'
    # a aprovacao do B4 continua no estado, e o painel le os mesmos dados
    assert novo['aprovacoes']['mesma']['situacao'] == 'aprovado'


# ------------------------------------------------------------------ no Chromium, a 1280 px de largura
LARGURA, ALTURA = 1280, 800  # numero-neutro: a checagem de largura do plano (B5) e uma altura de notebook
JS_ATO = ('() => { const v = document.documentElement.dataset.estadoAto || "";'
          ' return ["parou", "erro", "cancelado"].includes(v) ? "erro" : v; }')


def _abrir_painel(pw, srv):
    import test_tela_palco as tp
    from desdobra.chromium import navegador
    nav = pw.chromium.launch(headless=True, args=list(navegador.ARGUMENTOS))
    pg = nav.new_context(viewport={'width': LARGURA, 'height': ALTURA}, device_scale_factor=1).new_page()
    try:
        pg.goto(srv.url_entrada, wait_until='commit')
    except Exception:  # noqa: BLE001 - o 204 nao completa a navegacao
        pass
    pg.goto(srv.url_pagina, wait_until='load')
    tp._esperar(pg, tp.JS_PRONTO)
    pg.evaluate('() => document.querySelector("#passos [data-passo=formatos]").click()')
    tp._esperar(pg, '() => document.documentElement.dataset.painel || ""', 'pronto')
    return nav, pg


def _situacoes_na_tela(pg):
    return pg.evaluate('() => Array.from(document.querySelectorAll("#lista-formatos .linha-formato"))'
                       '.map(l => [l.dataset.formato, l.dataset.situacao])')


def _sem_rolagem_lateral(pg):
    return pg.evaluate('''() => [document.documentElement.scrollWidth, document.documentElement.clientWidth,
        ...Array.from(document.querySelectorAll(".painel-coluna, .formato-detalhe, .linha-formato, .topo"))
          .map(n => n.scrollWidth - n.clientWidth)]''')


def test_painel_no_chromium_a_1280_renderiza_e_aprova_pela_tela(job):
    from playwright.sync_api import sync_playwright

    import test_tela_palco as tp
    from desdobra.chromium import navegador
    from desdobra.entrega import portao
    _mudar_so_perto(job)
    navegador.apontar_playwright()
    s = tar._servidor(job).iniciar()
    try:
        with sync_playwright() as pw:
            nav, pg = _abrir_painel(pw, s)
            try:
                assert _situacoes_na_tela(pg) == [['perto', 'desatualizado'], ['mesma', 'renderizado'],
                                                  ['giro', 'renderizado']]
                assert pg.evaluate('() => document.getElementById("passo-atual").textContent') == 'Passo 5 de 5'
                largura = _sem_rolagem_lateral(pg)
                assert largura[0] <= largura[1] == LARGURA and all(x <= 0 for x in largura[2:]), largura
                # o formato que pede atencao abre sozinho: o motivo, o que mudou e o antes e o depois
                assert pg.evaluate('() => document.getElementById("formato-detalhe").dataset.formato') == 'perto'
                tp._esperar(pg, '() => document.querySelector("#formato-detalhe .ad-quadro").dataset.pronto || ""')
                caixas = pg.evaluate('''() => Array.from(document.querySelectorAll("#formato-detalhe .ad-caixas > div"))
                    .map(c => [c.className, getComputedStyle(c).borderTopStyle, c.getBoundingClientRect().height > 0])''')
                assert caixas == [['caixa-antes', 'dashed', True], ['caixa-depois', 'solid', True]], caixas
                assert tp._textos(pg, '#formato-detalhe .mudou-item') == [
                    'O texto de apoio virou informação de evento.', 'O texto de apoio desceu 24 px.']
                assert te.MOTIVOS_DO_PAINEL['desatualizado'] in tp._textos(pg, '#formato-detalhe .detalhe-motivo')
                # sem render em dia, a imagem e a previa do layout; o antes fica 24 px acima do depois
                antes, depois = pg.evaluate('''() => Array.from(document.querySelectorAll("#formato-detalhe .ad-caixas > div"))
                    .map(c => c.getBoundingClientRect().top)''')
                assert antes < depois
                assert pg.evaluate('() => document.querySelectorAll("#formato-detalhe .ad-previa .recorte").length') > 0
                # o historico so para leitura, da versao mais nova para a mais antiga
                versoes = tp._textos(pg, '#historico-versoes .versao-formatos')
                assert versoes[0] == 'Mudou o formato 400x240.'
                assert pg.evaluate('() => document.querySelectorAll("#historico-versoes button, #historico-versoes '
                                   'input").length') == 0
                # nada vem marcado, e o perto (render velho) nao pode ser marcado para aprovar
                assert pg.evaluate('() => Array.from(document.querySelectorAll(".linha-marca"))'
                                   '.map(c => [c.checked, c.disabled])') == [[False, True], [False, False],
                                                                             [False, False]]
                assert pg.evaluate('() => document.getElementById("aprovar-marcados").disabled') is True
                # Renderizar os afetados: uma confirmacao para todos os que pedem render
                pg.evaluate('() => document.getElementById("renderizar-afetados").click()')
                tp._esperar(pg, '() => document.getElementById("confirmacao").open ? "1" : ""')
                assert '400x240' in pg.evaluate('() => document.getElementById("confirmacao-texto").textContent')
                assert tp._textos(pg, '#confirmacao-extra li') == ['400x240']
                pg.evaluate('() => document.querySelector("#confirmacao [data-resposta=sim]").click()')
                tp._esperar(pg, JS_ATO, 'feito', teto_s=600)  # numero-neutro: teto do teste para o render
                assert _situacoes_na_tela(pg)[0] == ['perto', 'renderizado']
                assert pg.evaluate('() => document.getElementById("renderizar-afetados").disabled') is True
                assert pg.evaluate('() => document.getElementById("painel-mensagem").textContent') == \
                    'O render terminou.'
                # o detalhe do perto agora mostra o master pela rota /render
                pg.evaluate('() => document.querySelector(\'.linha-formato[data-formato="perto"] .linha-abrir\').click()')
                tp._esperar(pg, '() => document.querySelector("#formato-detalhe .ad-quadro").dataset.pronto || ""')
                assert pg.evaluate('() => { const i = document.querySelector("#formato-detalhe .ad-imagem");'
                                   ' return i && i.naturalWidth; }') == 400  # numero-neutro: largura de perto
                # Aprovar perto e giro: o giro sem lado abre a janela do lado, com a figura de cada opcao
                pg.evaluate('''() => ["perto", "giro"].forEach(f => document.querySelector(
                    '.linha-formato[data-formato="' + f + '"] .linha-marca').click())''')
                pg.evaluate('() => document.getElementById("aprovar-marcados").click()')
                tp._esperar(pg, '() => document.getElementById("sentido").open ? "1" : ""')
                opcoes = pg.evaluate('''() => Array.from(document.querySelectorAll("#sentido .sentido-opcao"))
                    .map(b => [b.dataset.sentido, b.getAttribute("aria-pressed"), !!b.querySelector("svg .giro-topo")])''')
                assert opcoes == [['horario', 'false', True], ['anti_horario', 'false', True]], opcoes
                assert pg.evaluate('() => document.querySelector("#sentido [data-resposta=sim]").disabled') is True
                pg.evaluate('() => document.querySelector("#sentido .sentido-opcao[data-sentido=horario]").click()')
                pg.evaluate('() => document.querySelector("#sentido [data-resposta=sim]").click()')
                tp._esperar(pg, '() => document.getElementById("confirmacao").open ? "1" : ""', teto_s=120)  # numero-neutro: teto do preparo
                tp._esperar(pg, '''() => { const is = Array.from(document.querySelectorAll("#confirmacao-extra img"));
                    return is.length === 2 && is.every(i => i.complete && i.naturalWidth > 0) ? "1" : ""; }''')
                assert tp._textos(pg, '#confirmacao-extra .final-nome') == ['400x240', '320x640']
                assert pg.evaluate('() => document.getElementById("confirmacao").classList.contains('
                                   '"confirmacao-larga")') is True
                # o arquivo final do giro ja vem girado: de pe
                assert pg.evaluate('() => Array.from(document.querySelectorAll("#confirmacao-extra img"))'
                                   '.map(i => i.naturalHeight > i.naturalWidth)') == [False, True]
                pg.evaluate('() => document.querySelector("#confirmacao [data-resposta=sim]").click()')
                tp._esperar(pg, JS_ATO, 'feito', teto_s=120)  # numero-neutro: teto do teste para a aprovacao
                assert _situacoes_na_tela(pg) == [['perto', 'aprovado'], ['mesma', 'renderizado'],
                                                  ['giro', 'aprovado']]
                assert pg.evaluate('() => document.querySelectorAll(".linha-marca:checked").length') == 0
                largura = _sem_rolagem_lateral(pg)
                assert largura[0] <= largura[1] and all(x <= 0 for x in largura[2:]), largura
            finally:
                nav.close()
    finally:
        s.parar()
    sentido = contratos.ler(job / portao.ARQUIVO_PARAMETROS, portao.ESQUEMA_PARAMETROS)['formatos']['giro']
    assert sentido['rotacao_sentido']['valor'] == 'horario'
    assert {f: v['situacao'] for f, v in nucleo_aprovar.situacao(job).items()} == {
        'perto': 'aprovado', 'mesma': 'sem_aprovacao', 'giro': 'aprovado'}
    # o servidor nunca recebeu pedido fora da tabela nem sem cookie
    assert s.contagem['proibido'] == 0 and s.contagem['sem_cookie'] == 0


def test_tela_so_para_ver_mostra_o_painel_sem_botao_ligado(job):
    from playwright.sync_api import sync_playwright

    from desdobra.chromium import navegador
    from desdobra.tela import servidor as ts
    navegador.apontar_playwright()
    with ts.ServidorTela(te.montar(job)) as srv, sync_playwright() as pw:
        nav, pg = _abrir_painel(pw, srv)
        try:
            assert [x[1] for x in _situacoes_na_tela(pg)] == ['renderizado'] * 3
            assert pg.evaluate('''() => [document.getElementById("renderizar-afetados").disabled,
                document.getElementById("aprovar-marcados").disabled,
                Array.from(document.querySelectorAll(".linha-marca")).every(c => c.disabled)]''') == [True, True, True]
            assert 'só mostra' in pg.evaluate('() => document.getElementById("painel-resumo").textContent')
            # a tela so para ver nao serve o master: a imagem e a previa
            import test_tela_palco as tp
            tp._esperar(pg, '() => document.querySelector("#formato-detalhe .ad-quadro").dataset.pronto || ""')
            assert pg.evaluate('() => document.querySelectorAll("#formato-detalhe .ad-imagem").length') == 0
        finally:
            nav.close()


def test_textos_do_painel_para_o_da():
    textos = list(te.ROTULOS_DA_SITUACAO.values()) + list(te.MOTIVOS_DO_PAINEL.values()) + \
        list(te.ORIGENS_DA_VERSAO.values()) + [te.PEDE_RENDER_DEPOIS_DA_QUEDA, te.APROVE_DE_NOVO,
                                               te.RENDER_PAROU_POR_PROBLEMA, te.SEM_AFETADOS_REGISTRADOS,
                                               te.NENHUM_AFETADO]
    assert set(te.ROTULOS_DA_SITUACAO) == set(SITUACOES) and set(te.MOTIVOS_DO_PAINEL) == set(SITUACOES)
    for t in textos:
        assert not TRACO.search(t), t
        for proibido in tar.PROIBIDOS + ('não é', 'não são', 'terminal', 'comando', 'rode ', 'rodar'):
            assert proibido not in t, (proibido, t)
