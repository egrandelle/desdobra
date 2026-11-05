# -*- coding: utf-8 -*-
"""A galeria de variantes na tela so de leitura (decisoes-v1.md, 164 e as notas de 05/11), escrita antes do codigo.

Nenhum formato volta ao DA sem sugestao: o formato devolvido pela derivacao (troca de orientacao ou proporcao fora da
faixa de familia) chega a tela com as variantes da galeria do motor (derivacao.galeria), montadas em memoria. No grupo
de proporcao com mais de um formato devolvido, cada variante leva a mesma estrutura a todos os membros
(variante_para_grupo). Criterios cobertos:
  - o modelo: de 3 a 4 variantes por formato devolvido, cada uma com a frase do DA e as pecas do palco (o mesmo modelo
    do palco: imagem pelo asset, texto com a face do job), sem fantasma; nada gravado no job;
  - a tela: as miniaturas das variantes ao lado do palco, com a frase embaixo e os avisos como marcas discretas; a
    primeira ja vem escolhida (o palco nunca abre com fantasmas nesses formatos), com o selo "proposta, nao aprovada";
    clicar (ou as setas) troca o palco; a nota de que nada e gravado;
  - o aviso "apoio de desenho, nao gravado" aparece uma vez por palco, nunca em cada elemento;
  - nenhum identificador do motor no texto da moldura, nenhum pedido fora de 127.0.0.1.
Tudo sintetico: o PSD de test_tela_palco e a fonte de autoteste do motor."""
import copy
import json
import re

import pytest

import test_derivacao_apoio as ap
import test_fontes_apoio as fap
import test_tela_palco as tp
from desdobra.tela import estado as te
from desdobra.tela import servidor as ts

APOIO = 'apoio de desenho, não gravado'
NOTA = 'Escolha uma versão para começar. Nada é gravado nesta versão da tela.'
SELO_PROPOSTA = 'proposta, não aprovada'
# vertical e vertical2: proporcao 2,0 e 1,82, o mesmo grupo (derivacao.grupo_proporcao_dif_max); quadrado e faixa
# tambem voltam da derivacao (troca para o quadrado; proporcao longe da do KV)
FORMATOS = [('mesma', 640, 320), ('vertical', 160, 320), ('vertical2', 176, 320), ('quadrado', 320, 320),
            ('faixa', 1920, 192)]
DEVOLVIDOS = ('vertical', 'vertical2', 'quadrado', 'faixa')
IDS_DO_MOTOR = re.compile(r'[a-z]+_[a-z]+|\bel\d+\b|derivacao\.')
AVISO_INJETADO = {'codigo': 'texto_abaixo_de_8px', 'texto': 'O texto fica com corpo de 6 px, abaixo de 8 px.'}
FALHA_INJETADA = {'codigo': 'distancia_menor_que_na_mestre', 'texto': 'O título e o texto ficam mais perto do que o KV permite.'}


@pytest.fixture(scope='module')
def job_galeria(tmp_path_factory):
    from desdobra import contratos
    from desdobra.briefing import modelo as mb
    from desdobra.job import nucleo
    from desdobra.render import autoteste
    base = tmp_path_factory.mktemp('galeria')
    fontes = base / 'origem-fontes'
    fap.gravar(fontes, 'autoteste.ttf', autoteste.gerar_fonte())
    job = base / 'job'
    nucleo.criar(job, tp._psd_hostil(base / 'origem' / 'kv.psd', autoteste.NOME_PS), 'c', fontes=[fontes])
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    ids = {c['nome']: c['identidade']['layer_id'] for c in laudo['camadas']}
    funcoes = {ids['fundo-sintetico']: 'fundo', ids[tp.NOME_FORM]: 'titulo', ids['quadrado-sintetico']: 'logo_principal',
               ids[tp.NOME_APOIO]: 'texto_de_apoio', ids['solto-sintetico']: 'fora_da_peca'}
    b = ap.briefing(funcoes=funcoes, formatos=[ap.formato(i, w, h) for i, w, h in FORMATOS])
    b.pop('cabecalho')
    b.pop('job_id')
    arq = base / 'fixture.json'
    arq.write_text(json.dumps(b), encoding='utf-8')
    mb.importar_teste(job, arq)
    return job


@pytest.fixture(scope='module')
def conteudo(job_galeria):
    antes = tp._fotografia(job_galeria)
    c = te.montar(job_galeria)
    assert tp._fotografia(job_galeria) == antes  # so previa: nada gravado
    return c


def _formatos_do_estado(estado):
    return {x['id']: x for o in estado['orientacoes'] for g in o['grupos'] for co in g['composicoes']
            for x in co['formatos']}


# ------------------------------------------------------------------ modelo, sem navegador
def test_formato_devolvido_chega_com_a_galeria_no_modelo(conteudo):
    estado, previas = conteudo['estado'], conteudo['previas']
    fs = _formatos_do_estado(estado)
    assert {f for f, x in fs.items() if x['situacao'] == 'devolvido'} == set(DEVOLVIDOS)
    assert 'galeria' not in previas['mesma'] and fs['mesma'].get('variantes', 0) == 0
    for fid in DEVOLVIDOS:
        gal = previas[fid]['galeria']
        vs = gal['variantes']
        assert 3 <= len(vs) <= 4, (fid, len(vs))  # de 3 a derivacao.galeria_variantes_max
        assert fs[fid]['variantes'] == len(vs)
        assert [v['ordem'] for v in vs] == list(range(1, len(vs) + 1))
        assert len({v['id'] for v in vs}) == len(vs)
        for v in vs:
            assert isinstance(v['descricao'], str) and v['descricao'] and not IDS_DO_MOTOR.search(v['descricao'])
            for a in v['avisos'] + v['falhas']:
                assert set(a) >= {'codigo', 'texto'} and not IDS_DO_MOTOR.search(a['texto']), a
            p = v['palco']
            # o mesmo modelo do palco: pecas pela transformacao do elemento, sem fantasma, no tamanho da composicao
            assert p['selo'] == 'variante' and p['formato'] == fid
            assert p['pecas'] and not any(x['fantasma'] for x in p['pecas'])
            assert p['elementos'] and not any(e['fantasma'] for e in p['elementos'])
            assert (p['largura'], p['altura']) == (previas[fid]['largura'], previas[fid]['altura'])
            textos = [x for x in p['pecas'] if x['tipo'] == 'texto']
            assert textos and all(x['modo'] == 'texto' and x['linhas'] for x in textos)
            assert all(x['asset'] in conteudo['assets'] for x in p['pecas'] if x['tipo'] == 'imagem')
        # a frase do formato devolvido fala das versoes, sem identificador do motor e sem pedir mestre propria
        dv = previas[fid]['devolucao']['texto']
        assert 'versões' in dv and 'próxima versão' not in dv and 'mestre própria' not in dv
        assert 'escolha' not in dv.lower()  # quem pede a escolha e a nota da galeria, uma vez so
        assert not IDS_DO_MOTOR.search(dv)
    # faltam N: o formato devolvido continua na lista, pedindo a escolha de uma versao
    itens = [f for f in estado['faltam'] if f['ir'].get('formato') in DEVOLVIDOS]
    assert len(itens) == len(DEVOLVIDOS)
    assert all('versões' in f['texto'] and 'Sem proposta' not in f['texto'] for f in itens)
    json.dumps(estado)
    json.dumps(previas)


def test_grupo_de_devolvidos_leva_a_mesma_estrutura_a_todos(conteudo):
    previas = conteudo['previas']
    a, b = previas['vertical']['galeria'], previas['vertical2']['galeria']
    assert a['grupo'] == b['grupo'] and sorted(a['grupo']) == ['vertical', 'vertical2']
    assert [v['id'] for v in a['variantes']] == [v['id'] for v in b['variantes']]
    for va, vb in zip(a['variantes'], b['variantes']):
        assert va['estrutura'] == vb['estrutura'], (va['id'], va['estrutura'], vb['estrutura'])
    assert previas['quadrado']['galeria']['grupo'] == ['quadrado']


def test_rotulo_do_elemento_fantasma_sem_o_aviso_repetido():
    js = (tp.PASTA_TELA / 'tela.js').read_text(encoding='utf-8')
    corpo = re.search(r'function rotuloElemento\(e\) \{(.*?)\n  \}', js, re.DOTALL).group(1)
    assert 'APOIO' not in corpo
    assert js.count("'apoio de desenho, não gravado'") == 1
    assert NOTA in (tp.PASTA_TELA / 'tela.html').read_text(encoding='utf-8')


# ------------------------------------------------------------------ no Chromium sem janela
def _abrir(pg, estado, fid):
    o, g, _co = tp._onde(estado, fid)
    tp._clicar_aba(pg, 'orientacoes', o['rotulo'])
    tp._clicar_grupo(pg, g['id'])
    pg.evaluate('f => document.querySelector(\'.ficha[data-formato="\' + f + \'"]\').click()', fid)
    tp._esperar(pg, '() => document.getElementById("palco").dataset.pronto || ""')
    assert tp._no_palco(pg) == fid


def _variante_no_palco(pg):
    return pg.evaluate('() => document.getElementById("palco").dataset.variante || ""')


def test_galeria_no_palco_do_chromium(job_galeria, conteudo):
    from playwright.sync_api import sync_playwright

    from desdobra.chromium import navegador
    antes = tp._fotografia(job_galeria)
    c = copy.deepcopy(conteudo)
    vs = c['previas']['vertical']['galeria']['variantes']
    vs[1]['avisos'] = [dict(AVISO_INJETADO)]  # uma variante marcada, para a marca discreta
    for v in vs[:1] + vs[2:]:
        v['avisos'], v['falhas'] = [], []
    # o quadrado sem galeria (o motor nao conseguiu montar nenhuma): o palco cai nos fantasmas, com o aviso uma vez
    c['previas']['quadrado'].pop('galeria')
    for x in _formatos_do_estado(c['estado']).values():
        if x['id'] == 'quadrado':
            x['variantes'] = 0
    # a faixa com a primeira versao pedindo ajuste e as outras limpas: abre na primeira limpa
    vf = c['previas']['faixa']['galeria']['variantes']
    for v in vf:
        v['avisos'], v['falhas'] = [], []
    vf[0]['falhas'] = [dict(FALHA_INJETADA)]
    navegador.apontar_playwright()
    pedidos = []
    with ts.ServidorTela(c) as srv, sync_playwright() as pw:
        nav, pg = tp._pagina_da_tela(pw, srv, 2048, 720)  # numero-neutro: a tela do Duda (decisao 157)
        pg.on('request', lambda r: pedidos.append(r.url))
        try:
            _abrir(pg, c['estado'], 'vertical')
            # o grupo devolvido no trilho: o selo das versoes, nunca "sem proposta ainda"
            selos = tp._textos(pg, '#composicoes [role=tab][aria-selected=true] .mini-selo')
            assert selos == ['Versões para escolher'], selos
            assert not pg.evaluate('() => document.getElementById("galeria").hidden')
            cartoes = pg.evaluate('() => Array.from(document.querySelectorAll("#variantes [role=tab]")).map(b => ['
                                  'b.querySelector(".var-descricao").textContent, b.getAttribute("aria-selected"),'
                                  ' b.querySelectorAll(".mini-palco .peca").length,'
                                  ' Array.from(b.querySelectorAll(".marca-aviso")).map(m => m.textContent)])')
            assert 3 <= len(cartoes) <= 4 and len(cartoes) == len(vs)
            assert [x[0] for x in cartoes] == [v['descricao'] for v in vs]
            assert [x[1] for x in cartoes] == ['true'] + ['false'] * (len(vs) - 1)
            assert all(x[2] > 0 for x in cartoes), cartoes  # a miniatura e desenhada do modelo do palco
            assert cartoes[1][3] == ['Texto pequeno'] and cartoes[0][3] == [] and cartoes[2][3] == []
            assert pg.evaluate('() => document.querySelector("#variantes [role=tab]:nth-child(2) .marca-aviso")'
                               '.getAttribute("title")') == AVISO_INJETADO['texto']
            assert pg.evaluate('() => document.getElementById("nota-galeria").textContent') == NOTA
            # a primeira variante ja no palco: selo de proposta, sem fantasma
            assert _variante_no_palco(pg) == vs[0]['id']
            selo = pg.evaluate('() => document.getElementById("selo-palco").textContent')
            assert SELO_PROPOSTA in selo and 'Sem proposta' not in selo
            assert pg.evaluate('() => document.querySelectorAll("#palco .fantasma").length') == 0
            assert APOIO not in pg.evaluate('() => document.getElementById("palco").textContent')
            assert vs[0]['descricao'] in pg.evaluate('() => document.getElementById("variante-palco").textContent')
            assert pg.evaluate('() => document.querySelectorAll("#palco .peca").length') > 0
            # clicar troca o palco
            pg.evaluate('() => document.querySelector("#variantes [role=tab]:nth-child(2)").click()')
            tp._esperar(pg, '() => document.getElementById("palco").dataset.pronto || ""')
            assert _variante_no_palco(pg) == vs[1]['id']
            assert vs[1]['descricao'] in pg.evaluate('() => document.getElementById("variante-palco").textContent')
            assert AVISO_INJETADO['texto'] in pg.evaluate('() => document.getElementById("variante-palco").textContent')
            assert SELO_PROPOSTA in pg.evaluate('() => document.getElementById("selo-palco").textContent')
            # pelo teclado: seta para baixo leva a proxima
            pg.evaluate('() => document.querySelector("#variantes [aria-selected=true]").focus()')
            pg.keyboard.press('ArrowDown')
            tp._esperar(pg, '() => document.getElementById("palco").dataset.pronto || ""')
            assert _variante_no_palco(pg) == vs[2]['id']
            assert pg.evaluate('() => document.activeElement.dataset.variante') == vs[2]['id']
            # o outro membro do grupo abre na mesma versao escolhida
            pg.evaluate('() => document.querySelector(\'.ficha[data-formato="vertical2"]\').click()')
            tp._esperar(pg, '() => document.getElementById("palco").dataset.pronto || ""')
            assert tp._no_palco(pg) == 'vertical2' and _variante_no_palco(pg) == vs[2]['id']
            texto = pg.evaluate(tp.JS_TEXTO_DA_MOLDURA)
            assert not tp.IDENTIFICADOR.findall(texto), tp.IDENTIFICADOR.findall(texto)
            # a faixa abre na primeira versao sem falha, nunca numa que pede ajuste quando ha outra limpa
            _abrir(pg, c['estado'], 'faixa')
            assert _variante_no_palco(pg) == vf[1]['id']
            assert pg.evaluate('() => document.querySelector("#variantes [role=tab]:nth-child(1) .marca-aviso.forte")'
                               '.textContent') == 'Pede ajuste'
            assert pg.evaluate('() => document.querySelectorAll("#palco .fantasma").length') == 0
            # o formato sem proposta nem versoes: fantasmas e o aviso uma vez so no palco
            _abrir(pg, c['estado'], 'quadrado')
            assert pg.evaluate('() => document.getElementById("galeria").hidden')
            assert _variante_no_palco(pg) == ''
            assert pg.evaluate('() => document.querySelectorAll("#palco .rotulo.fantasma").length') > 1
            assert pg.evaluate('() => document.getElementById("palco").textContent').count(APOIO) == 1
            assert not any(APOIO in t for t in tp._textos(pg, '#palco .etiqueta'))
            texto = pg.evaluate(tp.JS_TEXTO_DA_MOLDURA)
            assert not tp.IDENTIFICADOR.findall(texto), tp.IDENTIFICADOR.findall(texto)
            assert pg.evaluate('() => document.querySelectorAll("form, [onerror]").length') == 0
        finally:
            nav.close()
        contagem, origem = dict(srv.contagem), srv.origem
    assert pedidos and all(u.startswith(origem + '/') for u in pedidos), pedidos
    assert contagem['nao_encontrado'] == 0 and contagem['proibido'] == 0 and contagem['sem_cookie'] == 0
    assert tp._fotografia(job_galeria) == antes


def test_versao_n_e_a_mesma_variante_em_todo_o_grupo_quando_o_grupo_nao_fecha(job_galeria, monkeypatch):
    """Quando nenhuma estrutura de uma variante serve a todo o grupo (variante_para_grupo levanta ValueError), cada
    membro fica com a variante de mesmo id da galeria dele, e o numero da versao e o do primeiro membro: Versao N aponta
    a mesma variante em todos os arquivos do grupo."""
    from desdobra.derivacao import galeria as mg
    original = mg.variante_para_grupo
    alvo = {}

    def falha_na_segunda(ctx, kv, formatos, escolha, **kw):
        alvo.setdefault('id', None)
        if escolha == mg.variantes(ctx, kv, formatos[0], **kw)[1]['id']:
            alvo['id'] = escolha
            raise ValueError('nenhuma estrutura serve ao grupo')
        return original(ctx, kv, formatos, escolha, **kw)
    monkeypatch.setattr(mg, 'variante_para_grupo', falha_na_segunda)
    previas = te.montar(job_galeria)['previas']
    assert alvo['id']
    a, b = previas['vertical']['galeria']['variantes'], previas['vertical2']['galeria']['variantes']
    por_ordem_a = {v['ordem']: v['id'] for v in a}
    por_ordem_b = {v['ordem']: v['id'] for v in b}
    assert alvo['id'] in por_ordem_a.values() and alvo['id'] in por_ordem_b.values()
    for n in set(por_ordem_a) & set(por_ordem_b):
        assert por_ordem_a[n] == por_ordem_b[n], (n, por_ordem_a, por_ordem_b)
    assert set(por_ordem_b.items()) <= set(por_ordem_a.items())
