# -*- coding: utf-8 -*-
"""0.9.4: Linhas do DA e o render que parava no formato extremo (relato do Duda na tela 0.9.3).

Criterios de pronto cobertos aqui:
  - o texto editado nunca quebra sozinho: o render nao tem largura de quebra (nem na caixa de paragrafo), o contrato
    leva linhas_do_da, e a caixa do texto e a tinta medida das linhas do DA, com o mesmo corpo, em volta da ancora
    (derivacao.quebras.caixa_do_editado; derivacao.medida_quebras.medir_editados, com o cache);
  - o rascunho de antes, com a quebra proposta num texto editado, nao trava a familia: a proposta sai na leitura da
    familia nao confirmada, e "Confirmar familia" passa;
  - o texto editado que passa da borda do formato: a derivacao registra, e desde a 0.9.6 (aprovacao soberana) o
    render corta na borda, com registro; o preparo do ato de render nao para mais por isso;
  - sem a medida, o render que corta o texto editado na borda para com o motivo texto_editado_cortado, e a tela diz o
    motivo com o nome do formato (nunca o "parou por um problema" generico);
  - na pagina: o membro em que o texto editado passa da borda fica marcado, a faixa diz o formato e "Confirmar
    familia" espera o ajuste; nao ha "Aprovar quebra".
Tudo sintetico: o KV de quatro linhas em corpo 60 do diagnostico (fonte de autoteste do motor) e os formatos do
relato (1080x1920, 1080x1080, 300x600 e 970x250)."""
import json
import shutil
import sys

import pytest

import test_derivacao_apoio as ap
import test_fontes_apoio as fap
import test_render_apoio as rap
import test_tela_palco as tp
import test_tela_salvar as tsv
from desdobra import contratos, humano
from desdobra.briefing import modelo as mb
from desdobra.derivacao import medida_quebras
from desdobra.derivacao import nucleo as nd
from desdobra.derivacao import quebras as mq
from desdobra.render import derivado as rd
from desdobra.render import execucao
from desdobra.render import texto as rt
from desdobra.tela import ato_render, tarefas
from desdobra.tela import estado as te
from desdobra.tela import rascunho as tr

ROT0 = {'graus': 0, 'sentido': None}
CONF = {'origem': 'da', 'meio': 'tela', 'em': '2026-11-17T10:00:00'}
FORMATOS = [('f1080x1920', 1080, 1920), ('f1080x1080', 1080, 1080), ('f300x600', 300, 600), ('f970x250', 970, 250)]
LINHAS_KV = ('HAX O', 'HOAXAV', 'H HOXAV', 'OX VA')
CORPO = 60.0
# o texto editado em sete linhas do DA: no 970x250 a tinta passa da base do formato
ALTO = 'HAX O\nHOAXAV\nH HOXAV\nOX VA\nHOX\nVA\nOX'
# o texto editado em duas linhas longas (o "ampliou e modernizou / 3 hospitais em MG" do relato)
LONGO = 'HAX O HOAXAV\nH HOXAV OX VA'
# o job de test_tela_salvar (o apoio 'VOX AH'), para o rascunho de antes da 0.9.4
modelo = tsv.modelo
job = tsv.job


# ------------------------------------------------------------------ funcoes puras
def _camada(just='LEFT', paragrafo=False, matriz=(2.0, 0.0, 0.0, 2.0, 100.0, 50.0)):
    t = {'conteudo': 'AB\rCD', 'matriz': list(matriz), 'tipo_caixa': 'paragrafo' if paragrafo else 'ponto',
         'box_bounds': [10.0, 0.0, 110.0, 50.0] if paragrafo else None,
         'runs': [{'inicio': 0, 'fim': 5, 'texto': 'AB\rCD', 'tem_tinta': True, 'fonte_ps': 'X',
                   'corpo_espaco_texto': 10.0, 'autoleading': True, 'kerning': 3}],
         'paragrafos': [{'inicio': 0, 'fim': 6, 'justificacao': just, 'auto_leading_fator': 1.2}]}
    return {'identidade': {'layer_id': 7}, 'tipo': 'texto', 'texto': t}


TINTA = {'esq': 1.0, 'dir': 41.0, 'sobe': 7.0, 'desce': 2.0}
FACES = {'X': {'metricas': {'ascender': 800, 'unidades_por_em': 1000}}}


def test_camada_do_editado_leva_um_trecho_so_com_as_linhas_do_da():
    c = mq.camada_do_editado(_camada(), ['HAX O HOAXAV', 'H HOXAV'])
    [r] = c['texto']['runs']
    assert r['texto'] == 'HAX O HOAXAV\rH HOXAV' and r['inicio'] == 0 and r['fim'] == len(r['texto'])
    assert r['kerning'] is None and r['corpo_espaco_texto'] == 10.0
    assert c['texto']['paragrafos'][0]['inicio'] == 0 and c['texto']['paragrafos'][0]['fim'] == len(r['texto']) + 1


def test_caixa_do_editado_no_texto_de_ponto_soma_uma_entrelinha_por_linha():
    # texto de ponto: a ancora e a origem da matriz; duas linhas, entrelinha automatica 1,2 x 10 = 12
    c = mq.camada_do_editado(_camada(), ['AB', 'CD'])
    assert mq.caixa_do_editado(c, TINTA, {}) == pytest.approx([102.0, 36.0, 182.0, 78.0])
    # tres linhas, a do meio vazia (dois Enter): a base da ultima desce duas entrelinhas
    c3 = mq.camada_do_editado(_camada(), ['AB', '', 'CD'])
    assert mq.caixa_do_editado(c3, TINTA, {}) == pytest.approx([102.0, 36.0, 182.0, 102.0])
    # a matriz com escala leva a caixa ao documento
    c2 = mq.camada_do_editado(_camada(matriz=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)), ['AB'])
    assert mq.caixa_do_editado(c2, TINTA, {}) == pytest.approx([1.0, -7.0, 41.0, 2.0])


@pytest.mark.parametrize('just,x', [('LEFT', 10.0), ('CENTER', 60.0), ('RIGHT', 110.0)])
def test_caixa_do_editado_na_caixa_de_paragrafo_ancora_na_caixa(just, x):
    # caixa de paragrafo: a ancora e a borda ou o meio da caixa, e a primeira linha de base fica no topo mais a
    # ascendente (0,8 x 10 = 8), como o render (render.texto.origem_das_linhas)
    c = mq.camada_do_editado(_camada(just=just, paragrafo=True, matriz=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)), ['AB'])
    assert mq.caixa_do_editado(c, TINTA, FACES) == pytest.approx([x + 1.0, 1.0, x + 41.0, 10.0])


def test_linhas_editadas_sao_as_do_da_com_a_quebra_da_familia():
    assert mq.linhas_editadas('HAX O HOAXAV\r\nH HOXAV') == ['HAX O HOAXAV', 'H HOXAV']
    assert mq.linhas_editadas('HAX O\nHOAXAV', {'aprovadas': [], 'inseridas': [3]}) == ['HAX', 'O HOAXAV']
    assert mq.chave_editado(7, ['A']) != mq.chave_editado(7, ['B']) and mq.chave_editado(7, ['A']).startswith('ed:7:')


def test_render_nunca_quebra_o_texto_editado_na_largura():
    par = {'texto': {'tipo_caixa': 'paragrafo', 'box_bounds': [0, 0, 100, 50]}}
    assert rt.largura_da_quebra(par) == 100.0
    assert rt.largura_da_quebra(dict(par, linhas_do_da=True)) is None
    assert rt.largura_da_quebra({'texto': {}, 'linhas_do_da': True, 'largura_quebra': 30}) is None
    entrada = {'texto': {'runs': [{'inicio': 0, 'texto': 'AB', 'tem_tinta': True, 'fonte_ps': 'X'}],
                         'paragrafos': [{'inicio': 0, 'fim': 3, 'justificacao': 'LEFT'}], 'matriz': [1, 0, 0, 1, 0, 0]},
               'cores_por_trecho': {'0': 'c0'}, 'valores_cor': {'c0': {'rgb': [0, 0, 0], 'alfa': 1}},
               'faces': {'X': 'f1'}, 'largura_quebra': 5.0}
    novo = rd.texto_editado_na_entrada(entrada, 'HAX O HOAXAV\nH HOXAV')
    assert 'largura_quebra' not in novo and novo['linhas_do_da'] is True and novo['texto_editado'] is True


def test_tinta_do_texto_editado_alem_da_caixa_medida_reprova():
    # com a caixa medida, o excesso alem da tolerancia tambem reprova, mesmo sem tocar a borda
    e = {'id': 'e01', 'tipo': 'texto', 'layer_id': 7, 'regiao': [0, 0, 400, 300],
         'caixa_validada': [100, 100, 200, 150], 'texto_editado': True}
    st = {'id': 'e01', 'tipo': 'texto', 'tinta': [100, 100, 260, 150], 'toca_regiao': []}
    [x] = rd.tinta_fora_da_caixa([e], [st], 400, 300)
    assert x['excesso_px'] == 60 and x['cortada_na_regiao'] == []
    assert rd.tinta_fora_da_caixa([e], [dict(st, tinta=[100, 100, 200, 150])], 400, 300) == []


# ------------------------------------------------------------------ o motivo para o DA
def test_motivo_do_render_parado_vira_texto_com_o_formato():
    r = {'feitos': ['a'], 'mudaram': [], 'pararam': {'f970x250': 'texto_editado_cortado'},
         'nomes': {'f970x250': '970x250'}}
    texto = tarefas.texto_do_motivo('texto_editado_cortado', r)
    assert texto.startswith('O render do formato 970x250 parou porque um texto passou da borda dele.')
    dois = dict(r, pararam={'a1': 'texto_editado_cortado', 'b2': 'texto_editado_cortado'}, nomes={'a1': '1x2'})
    assert 'dos formatos 1x2 e b2' in tarefas.texto_do_motivo('texto_editado_cortado', dois)
    # 0.9.6 (aprovacao soberana): o preparo nao para mais com texto_passa_da_borda, e o texto dele saiu
    assert 'texto_passa_da_borda' not in tarefas.TEXTOS_POR_MOTIVO
    assert 'texto_passa_da_borda' not in tarefas.TEXTOS_POR_MOTIVO_COM_FORMATO
    # sem o nome, o texto do motivo; o motivo sem texto fica com o texto da situacao
    assert tarefas.texto_do_motivo('tinta_fora_da_caixa_validada', None) == \
        tarefas.TEXTOS_POR_MOTIVO['tinta_fora_da_caixa_validada']
    assert tarefas.texto_do_motivo('outro', r) is None
    t = tarefas.Tarefa('render', ['f970x250'])
    t.situacao, t.motivo, t.resposta = 'parou', 'texto_editado_cortado', r
    assert t.vista()['texto'] == texto and 'chame a Trezion' not in texto
    todos = list(tarefas.TEXTOS_POR_MOTIVO.values()) + [x for par in tarefas.TEXTOS_POR_MOTIVO_COM_FORMATO.values()
                                                        for x in par]
    for x in todos:
        assert '—' not in x and '–' not in x


def test_preparo_nao_tem_mais_o_bloqueio_da_borda():
    # 0.9.6 (aprovacao soberana; revisao adversarial): o contrato do texto que passa da borda sai cortado, com o
    # registro; o ramo do preparo e o texto do bloqueio saem. O contrato do formato na borda vai ao render como os outros
    from desdobra.render import derivado as rd
    assert not hasattr(ato_render, 'BLOQUEIO_BORDA') and not hasattr(ato_render, 'MOTIVO_BORDA')
    assert 'texto_editado_passa_do_formato' not in rd.DESCRICOES


# ------------------------------------------------------------------ o rascunho de antes da 0.9.4
def test_rascunho_velho_perde_a_proposta_no_texto_editado_so_na_familia_aberta():
    ed = [{'elemento': 'el2', 'acao': 'texto', 'texto': 'HAX O HOAXAV'}]
    prop = {'elemento': 'el2', 'layer_id': 2, 'manter': [], 'inseridas': [5], 'origem': 'proposta', 'aprovada': False}
    aprov = dict(prop, aprovada=True)
    do_da = {'elemento': 'el3', 'layer_id': 3, 'manter': [], 'inseridas': [2], 'origem': 'da', 'aprovada': True}
    no_kv = dict(prop, elemento='el4', layer_id=4)
    dados = {'familias': {
        'aberta': {'edicoes': ed, 'quebras': [prop, do_da, no_kv], 'confirmada': False},
        'aprovada': {'edicoes': ed, 'quebras': [aprov], 'confirmada': False},
        'confirmada': {'edicoes': ed, 'quebras': [aprov], 'confirmada': True}}}
    tr.sem_proposta_velha(dados)
    fs = dados['familias']
    # a proposta no texto editado sai (aprovada ou nao); a do DA e a do texto do KV ficam
    assert fs['aberta']['quebras'] == [do_da, no_kv] and fs['aprovada']['quebras'] == []
    # a familia confirmada fica como o DA a confirmou
    assert fs['confirmada']['quebras'] == [aprov]
    assert tr.por_aprovar(fs['aberta']) == [no_kv]


def test_rascunho_velho_com_proposta_no_texto_editado_confirma_a_familia(job, modelo):
    # o job de test_tela_salvar (o apoio 'VOX AH'): o rascunho gravado antes da 0.9.4 com a quebra proposta, sem
    # aprovacao, no apoio editado. A leitura tira a proposta, e "Confirmar familia" passa
    conteudo = te.montar(job)
    gm = tsv._familia_de(conteudo, 'mesma')
    el, lid = tsv._apoio(modelo)
    s = tsv._servidor(job, conteudo)
    try:
        escolhas = tsv._escolhas(conteudo)
        f = escolhas[gm]
        f['edicoes'] = [{'elemento': el, 'acao': 'texto', 'texto': 'VOX AH VOX'}]
        f['quebras'] = [{'elemento': el, 'layer_id': lid, 'manter': [], 'inseridas': [6], 'origem': 'proposta',
                         'aprovada': False}]
        corpo = dict({'job_id': s.job_id, 'laudo_sha256': s.laudo_sha256, 'familias': escolhas},
                     **tsv._passo_2(modelo['funcoes']))
        tr.gravar(job, corpo, job_id=s.job_id, laudo_atual=s.laudo_sha256, origem=s.origem_rascunho)
        lido = tr.ler(job, s.laudo_sha256)[0]['familias'][gm]
        assert lido['quebras'] == [] and tr.por_aprovar(lido) == []
        d = humano.exigir_tela(tr.COMANDO_FAMILIA, s._sessao_humana, confirmado=True)
        g = tr.confirmar_familia(job, gm, lido['versao'], disparo=d, job_id=s.job_id, laudo_atual=s.laudo_sha256,
                                 edicoes=lido['edicoes'], quebras=[], formatos=conteudo['familias'][gm]['formatos'])
        assert g['confirmada'] is True
    finally:
        s.parar()


# ------------------------------------------------------------------ o job do relato (sintetico)
def _psd(destino, ps):
    from PIL import Image
    from psd_tools import PSDImage
    p = PSDImage.new('RGB', (540, 960), color=(255, 255, 255))
    p.create_pixel_layer(Image.new('RGBA', (540, 960), (0, 140, 70, 255)), name='fundo-sintetico')
    larga = max(fap.largura(t, CORPO, avancos=tp.AVANCOS) for t in LINHAS_KV)
    alto = int(1.2 * CORPO * len(LINHAS_KV))
    topo, esq = 89, 30
    t = p.create_pixel_layer(Image.new('RGBA', (int(larga) + 2, alto), (20, 20, 20, 255)), name='titulo-sintetico',
                             top=topo, left=esq)
    fap._virar_texto(t, [('\r'.join(LINHAS_KV), 0, CORPO, 0)], [ps], larga, x=float(esq), y=float(topo + CORPO * 0.7))
    p.create_pixel_layer(Image.new('RGBA', (140, 80), (255, 255, 255, 255)), name='logo-sintetico', top=850, left=380)
    return rap._salvar(p, destino)


@pytest.fixture(scope='module')
def relato(tmp_path_factory):
    from desdobra.job import nucleo
    from desdobra.render import autoteste
    base = tmp_path_factory.mktemp('relato-094')
    fontes = base / 'origem-fontes'
    fap.gravar(fontes, 'autoteste.ttf', autoteste.gerar_fonte())
    job = base / 'job'
    nucleo.criar(job, _psd(base / 'origem' / 'kv.psd', autoteste.NOME_PS), 'c', fontes=[fontes])
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    laudo = contratos.ler(job / mb.ARQUIVO_LAUDO, 'laudo/1')
    ids = {c['nome']: c['identidade']['layer_id'] for c in laudo['camadas']}
    funcoes = {ids['fundo-sintetico']: 'fundo', ids['titulo-sintetico']: 'titulo',
               ids['logo-sintetico']: 'logo_principal'}
    b = ap.briefing(funcoes=funcoes, formatos=[ap.formato(i, w, h, rotacao=ROT0) for i, w, h in FORMATOS])
    b.pop('cabecalho')
    b.pop('job_id')
    arq = base / 'fixture.json'
    arq.write_text(json.dumps(b), encoding='utf-8')
    mb.importar_teste(job, arq)
    return {'job': job, 'layer_id': ids['titulo-sintetico']}


def _copia(m, tmp_path):
    destino = tmp_path / 'job'
    shutil.copytree(m['job'], destino)
    return destino


def _titulo(conteudo, gid):
    base = conteudo['editar']({'familia': gid, 'versao': None, 'edicoes': []})
    return next(e['id'] for e in base['membros'][0]['palco']['elementos'] if e['funcao'] == 'titulo')


def _gravar(job, texto, dy=0.0):
    """O briefing do DA com o texto editado em toda familia, confirmado, e a derivacao. dy: o titulo movido na
    vertical, em fracao do formato."""
    conteudo = te.montar(job)
    comps = []
    for g, f in conteudo['familias'].items():
        el = _titulo(conteudo, g)
        ed = [{'elemento': el, 'acao': 'texto', 'texto': texto}] if texto is not None else []
        if dy:
            ed.append({'elemento': el, 'acao': 'mover', 'dx': 0.0, 'dy': dy})
        comps.append({'familia': g, 'formatos': f['formatos'], 'versao': None, 'edicoes': ed,
                      'confirmada': True, 'confirmacao': dict(CONF)})
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    b['cabecalho'].update(origem='da', meio='terminal')
    b['composicoes'] = comps
    contratos.gravar(job / mb.ARQUIVO, b, 'briefing/1')
    nd.derivar(job)
    return conteudo


def _deriv(job, fid):
    return contratos.ler(job / nd.PASTA / ('%s.json' % fid), nd.ESQUEMA)


def _editado(d, layer_id):
    return next(e for e in d['elementos'] if layer_id in e['layer_ids'])


def test_texto_longo_cresce_com_o_mesmo_corpo_e_renderiza_nas_linhas_do_da(relato, tmp_path, pessoa):
    job = _copia(relato, tmp_path)
    _gravar(job, None)
    sem = {fid: _editado(_deriv(job, fid), relato['layer_id']) for fid, _w, _h in FORMATOS}
    _gravar(job, LONGO)
    for fid, _w, _h in FORMATOS:
        x = _editado(_deriv(job, fid), relato['layer_id'])
        # o mesmo corpo: a escala do elemento e a do texto do KV no formato
        assert x['transformacao']['s'] == pytest.approx(sem[fid]['transformacao']['s'], rel=1e-4), fid
        assert len(x['caixa_texto_editado']) == 4 and x['quebras'] == 'do_texto_editado', fid
    contrato, bloqueios, conf = execucao.montar_contrato(job, 'f1080x1080')
    assert bloqueios == [], bloqueios
    e = next(y for y in contrato['entradas'] if y['tipo'] == 'texto' and y['layer_id'] == relato['layer_id'])
    assert e['linhas_do_da'] is True and 'largura_quebra' not in e
    rel = execucao.renderizar(job, disparo=humano.exigir('render'), formato='f1080x1080',
                              aceites=sorted({c['codigo'] for c in conf}))
    assert [x['linhas'] for x in rel['textos']['editados']] == [LONGO.split('\n')]
    # a tinta do render cabe na caixa medida (tinta_fora_da_caixa nao reprovou) e nao encosta na borda
    st = next(s for s in rel['entradas'] if s['id'] == e['id'])
    assert st['toca_regiao'] == []
    tol = rd._tolerancia_tinta(e['caixa_validada'])
    assert st['tinta'] == pytest.approx(e['caixa_validada'], abs=tol), (st['tinta'], e['caixa_validada'])


def test_texto_que_passa_da_borda_vai_ao_render_cortado_na_borda(relato, tmp_path, monkeypatch):
    # 0.9.6 (aprovacao soberana; revisa a 196 neste ponto): o DA confirmou a familia vendo o texto na borda. A derivacao
    # registra, o contrato sai sem bloqueio com o registro do corte e o preparo do render segue (antes: recusa
    # texto_editado_passa_do_formato e motivo texto_passa_da_borda)
    job = _copia(relato, tmp_path)
    _gravar(job, ALTO)
    d = _deriv(job, 'f970x250')
    x = _editado(d, relato['layer_id'])
    assert x['caixa_texto_editado'][3] > 250
    assert any(r['codigo'] == 'texto_editado_passa_da_borda' and r['medidas']['elemento'] == x['id'] and
               'base' in r['medidas']['lados'] for r in d['registros'])
    contrato, bloqueios, _c = rd.montar(job, 'f970x250')
    assert contrato is not None and bloqueios == [], bloqueios
    corte = next(r for r in contrato['registros'] if r['codigo'] == rd.CORTADO_PELO_DA)
    assert corte['medidas']['textos'][0]['lados'] == ['base']
    # o formato alto continua sem bloqueio
    assert rd.montar(job, 'f1080x1920')[1] == []

    class Tarefa:
        def parar(self):
            return False

        def progresso(self, *a):
            return None
    preparado = ato_render.ato_de_render(job).preparar({'formatos': ['f1080x1920', 'f970x250']}, Tarefa())
    assert [f['id'] for f in preparado['vista']['formatos']] == ['f1080x1920', 'f970x250']


def test_sem_a_medida_o_corte_na_borda_fica_registrado(relato, tmp_path, pessoa, monkeypatch):
    # a rede de seguranca: sem a medida do texto editado (o Chromium que nao mediu), a pagina e o formato inteiro e o
    # corte na borda e conferido depois de compor. 0.9.6 (aprovacao soberana): o texto editado na familia que o DA
    # confirmou nunca para o render; o corte fica registrado no render.json com os lados (antes: ErroRender
    # texto_editado_cortado). O texto do motivo continua para o render de antes que parou assim
    monkeypatch.setattr(medida_quebras, 'medir_editados', lambda *a, **k: {})
    job = _copia(relato, tmp_path)
    _gravar(job, ALTO)
    d = _deriv(job, 'f970x250')
    assert 'caixa_texto_editado' not in _editado(d, relato['layer_id'])
    assert any(r['codigo'] == 'texto_editado_sem_medida' for r in d['registros'])
    contrato, bloqueios, conf = execucao.montar_contrato(job, 'f970x250')
    assert bloqueios == [], bloqueios
    rel = execucao.renderizar(job, disparo=humano.exigir('render'), formato='f970x250',
                              aceites=sorted({c['codigo'] for c in conf}))
    reg = next(r for r in rel['registros'] if r['codigo'] == 'texto_editado_cortado_registrado')
    assert 'base' in reg['medidas']['textos'][0]['cortada_na_regiao']
    r = {'pararam': {'f970x250': 'texto_editado_cortado'}, 'nomes': {'f970x250': '970x250'}}
    assert tarefas.texto_do_motivo('texto_editado_cortado', r).startswith(
        'O render do formato 970x250 parou porque um texto')


def test_medida_do_texto_editado_usa_o_cache(relato, tmp_path, monkeypatch):
    job = _copia(relato, tmp_path)
    laudo = contratos.ler(job / mb.ARQUIVO_LAUDO, 'laudo/1')
    estado = contratos.ler(job / 'estado.json', 'estado/1')
    medida_quebras.limpar_cache()
    chamadas = []
    original = medida_quebras._conferir
    monkeypatch.setattr(medida_quebras, '_conferir', lambda *a, **k: chamadas.append(1) or original(*a, **k))
    pedido = [(relato['layer_id'], LONGO.split('\n'))]
    um = medida_quebras.medir_editados(job, laudo, estado, pedido)
    dois = medida_quebras.medir_editados(job, laudo, estado, pedido)
    assert um == dois and len(chamadas) == 1
    [m] = um.values()
    assert m['linhas'] == 2 and len(m['caixa_doc']) == 4
    medida_quebras.medir_editados(job, laudo, estado, [(relato['layer_id'], ['HAX O'])])
    assert len(chamadas) == 2  # numero-neutro: o texto novo vai ao Chromium
    medida_quebras.limpar_cache()


# ------------------------------------------------------------------ na pagina
@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
def test_pagina_marca_o_membro_em_que_o_texto_passa_da_borda(relato, tmp_path):
    from playwright.sync_api import sync_playwright

    import test_tela_edicao as ted
    import test_tela_galeria as tg
    from desdobra.chromium import navegador
    from desdobra.tela import atos as ta
    from desdobra.tela import servidor as ts
    job = _copia(relato, tmp_path)
    conteudo = te.montar(job)
    gid = next(g for g, f in conteudo['familias'].items() if 'f970x250' in f['formatos'])
    el = _titulo(conteudo, gid)
    navegador.apontar_playwright()
    with ts.ServidorTela(conteudo, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo)) as srv, sync_playwright() as pw:
        nav, pg = tp._pagina_da_tela(pw, srv, 1600, 900)  # numero-neutro: janela do teste
        try:
            tg._abrir(pg, conteudo['estado'], 'f970x250')
            ted._focar(pg, el)
            pg.keyboard.press('Enter')
            pg.evaluate('() => document.getElementById("ed-texto").click()')
            pg.fill('#ed-campo-texto', ALTO)
            pg.evaluate('() => document.getElementById("ed-texto-aplicar").click()')
            tp._esperar(pg, '() => document.getElementById("editor-texto").hidden ? "1" : ""')
            ted._esperar_salvo(pg)
            tp._esperar(pg, '() => document.getElementById("texto-borda").hidden ? "" : "1"')
            vista = pg.evaluate('''() => ({
                faixa: document.getElementById("texto-borda-texto").textContent,
                membro: Array.from(document.querySelectorAll("#membros-lista .membro.na-borda"))
                  .map(b => b.dataset.formato),
                confirmar: document.getElementById("confirmar-familia").disabled,
                titulo: document.getElementById("confirmar-familia").title,
                rotulo: !!document.querySelector("#palco .rotulo.passa-da-borda"),
                linhas: Array.from(document.querySelectorAll("#palco .texto.editado .linha")).map(l => l.textContent),
                aprovar: !!document.getElementById("ed-quebra-aprovar") || !!document.getElementById("aprovar-quebra")
            })''')
        finally:
            nav.close()
    assert 'f970x250' in vista['membro'], vista
    assert '970x250' in vista['faixa'] and 'passa da borda' in vista['faixa'], vista
    # 0.9.6 (aprovacao soberana): "Confirmar familia" fica ligado; o aviso vai no title (antes: desligado)
    assert vista['confirmar'] is False and 'passa da borda' in vista['titulo'], vista
    assert vista['rotulo'] is True and vista['aprovar'] is False, vista
    assert vista['linhas'] == ALTO.split('\n'), vista
    gravada = ted._rascunho_gravado(job)['familias'][gid]
    assert not gravada.get('quebras')


# ------------------------------------------------------------------ texto escrito no palco (duplo clique, F2, Enter)
CAMPO = '#palco textarea.texto-no-palco'
JS_CAMPO = '''i => {
    const c = document.querySelector("#palco textarea.texto-no-palco");
    const t = document.querySelector('#palco .recorte[data-elemento="' + i + '"] .texto');
    if (!c) return null;
    const tr = t.querySelector(".trecho");
    const cs = getComputedStyle(c), ts = getComputedStyle(tr);
    const k = parseFloat(/scale\\(([0-9.e-]+)\\)/.exec(document.querySelector("#palco .mundo").style.transform)[1]);
    const rc = c.getBoundingClientRect(), r0 = tr.getBoundingClientRect();
    const base = t.querySelector(".linha .marco").getBoundingClientRect().bottom;
    return {valor: c.value, foco: document.activeElement === c, k: k, fonte: cs.fontFamily, fonteTexto: ts.fontFamily,
            corpo: parseFloat(cs.fontSize), corpoTexto: parseFloat(ts.fontSize), linha: parseFloat(cs.lineHeight),
            escondido: getComputedStyle(t).visibility, esq: rc.left, esqTexto: r0.left, topo: rc.top, alto: rc.height,
            base: base, largura: c.clientWidth, rolagem: c.scrollWidth, invalido: c.getAttribute("aria-invalid"),
            soLeitura: c.readOnly};
}'''


def _centro(pg, eid):
    return pg.evaluate('i => { const r = document.querySelector(\'#palco .rotulo[data-elemento="\' + i + \'"]\')'
                       '.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }', eid)


def _edicoes(ted, job, gid):
    r = ted._rascunho_gravado(job)
    return ((r or {}).get('familias', {}).get(gid) or {}).get('edicoes', [])


def _na_tela_do_relato(relato, tmp_path, corpo, formato='f1080x1080', janela=(1600, 900)):  # numero-neutro: px
    """Abre a familia do formato (o 1080x1080) do job do relato no Chromium e chama corpo(pg, job, gid, titulo, logo)."""
    from playwright.sync_api import sync_playwright

    import test_tela_galeria as tg
    from desdobra.chromium import navegador
    from desdobra.tela import atos as ta
    from desdobra.tela import servidor as ts
    job = _copia(relato, tmp_path)
    conteudo = te.montar(job)
    gid = next(g for g, f in conteudo['familias'].items() if formato in f['formatos'])
    base = conteudo['editar']({'familia': gid, 'versao': None, 'edicoes': []})
    elementos = base['membros'][0]['palco']['elementos']
    titulo = next(e['id'] for e in elementos if e['funcao'] == 'titulo')
    logo = next(e['id'] for e in elementos if e['funcao'] == 'logo_principal')
    navegador.apontar_playwright()
    with ts.ServidorTela(conteudo, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo)) as srv, sync_playwright() as pw:
        # 0.10.0 (decisao 199): o DA edita so o arquivo de edicao; o formato do relato passa a ser o da familia
        tg._trocar_para(srv, job, conteudo, gid, formato)
        nav, pg = tp._pagina_da_tela(pw, srv, *janela)
        try:
            tg._abrir(pg, conteudo['estado'], formato)
            tp._esperar(pg, '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""')
            corpo(pg, job, gid, titulo, logo)
        finally:
            nav.close()
        contagem = dict(srv.contagem)
    assert contagem['proibido'] == 0 and contagem['csrf_recusado'] == 0 and contagem['dado_recusado'] == 0


@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
def test_duplo_clique_escreve_o_texto_no_palco_nas_linhas_do_da(relato, tmp_path):
    """Item 1 do relato: o duplo clique no texto abre o campo ali mesmo, sobre o texto, na mesma face e corpo na
    escala do palco. O campo nunca quebra sozinho e cresce com a linha mais longa; Enter quebra a linha; as teclas do
    palco nao valem dentro dele; Ctrl+Enter aplica pelo caminho do editor de baixo, com as linhas do DA."""
    import test_tela_edicao as ted

    def corpo(pg, job, gid, titulo, _logo):
        x, y = _centro(pg, titulo)
        pg.mouse.dblclick(x, y)
        tp._esperar(pg, '() => document.querySelector("%s") ? "1" : ""' % CAMPO)
        v = pg.evaluate(JS_CAMPO, titulo)
        assert v['valor'] == '\n'.join(LINHAS_KV) and v['foco'], v
        assert v['fonte'] == v['fonteTexto'], v
        assert v['corpo'] == pytest.approx(v['corpoTexto'] * v['k'], rel=0.02), v
        assert v['escondido'] == 'hidden', v
        assert abs(v['esq'] - v['esqTexto']) <= 2, v  # numero-neutro: 2 px de tela
        assert v['topo'] < v['base'] < v['topo'] + v['linha'], v  # a primeira linha de base cai na primeira linha
        assert not _edicoes(ted, job, gid)  # abrir nao grava nada
        assert 'Ctrl+Enter' in pg.evaluate('() => document.getElementById("ed-mensagem").textContent')
        # o texto longo do relato: uma linha so, sem quebra automatica; Enter quebra onde o DA quer
        primeira, segunda = LONGO.split('\n')
        pg.keyboard.press('Control+a')
        pg.keyboard.type(primeira)
        v = pg.evaluate(JS_CAMPO, titulo)
        assert v['rolagem'] <= v['largura'] + 1 and v['alto'] == pytest.approx(v['linha'], abs=1), v
        pg.keyboard.press('Enter')
        pg.keyboard.type(segunda)
        v2 = pg.evaluate(JS_CAMPO, titulo)
        assert v2['alto'] == pytest.approx(2 * v2['linha'], abs=1), v2  # numero-neutro: duas linhas
        # as teclas do palco ficam na escrita: nada anda, nada some, nada vai ao rascunho
        # (Ctrl+Z dentro do campo e o desfazer da escrita, do proprio campo)
        for tecla in ('ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'):
            pg.keyboard.press(tecla)
        pg.evaluate('() => { const c = document.querySelector("%s"); c.value = c.value; '
                    'c.setSelectionRange(c.value.length, c.value.length); }' % CAMPO)
        pg.keyboard.press('Backspace')
        pg.keyboard.type(LONGO[-1])
        assert pg.evaluate(JS_CAMPO, titulo)['valor'] == LONGO
        assert not _edicoes(ted, job, gid)
        assert ted._quantos_no_palco(pg, titulo) == 1
        pg.keyboard.press('Control+Enter')
        tp._esperar(pg, '() => document.querySelector("%s") ? "" : "1"' % CAMPO)
        ted._esperar_salvo(pg)
        edicoes = _edicoes(ted, job, gid)
        assert [(e['acao'], e.get('texto')) for e in edicoes] == [('texto', LONGO)], edicoes
        fim = pg.evaluate('''() => ({
            foco: (document.activeElement || {}).dataset ? document.activeElement.dataset.elemento : null,
            msg: document.getElementById("ed-mensagem").textContent,
            linhas: Array.from(document.querySelectorAll("#palco .texto.editado .linha")).map(l => l.textContent)})''')
        assert fim['foco'] == titulo and 'vale só nesta família' in fim['msg'], fim
        assert fim['linhas'] == LONGO.split('\n'), fim

    _na_tela_do_relato(relato, tmp_path, corpo)


@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
def test_texto_no_palco_pelo_teclado_recusa_e_clique_fora(relato, tmp_path):
    """F2 e Enter no texto escolhido abrem o campo; Esc desiste; o texto igual nao grava; o vazio e o caractere fora
    da fonte ficam no campo com o motivo; o clique fora aplica sem escolher nem mover outro elemento; o duplo clique
    no logo nao abre nada; o campo segue o zoom; o clique tremido nao vira arraste."""
    import test_tela_edicao as ted

    def aberto(pg):
        return pg.evaluate('() => !!document.querySelector("%s")' % CAMPO)

    def msg(pg):
        return pg.evaluate('() => document.getElementById("ed-mensagem").textContent')

    def corpo(pg, job, gid, titulo, logo):
        # F2 no titulo (ainda nao escolhido) escolhe e abre; Esc desiste sem gravar e o foco volta ao elemento
        ted._focar(pg, titulo)
        pg.keyboard.press('F2')
        assert aberto(pg)
        pg.keyboard.type('HOX')
        pg.keyboard.press('Escape')
        assert not aberto(pg) and not _edicoes(ted, job, gid)
        estado = pg.evaluate('''i => ({foco: document.activeElement.dataset.elemento,
            escolhido: (document.querySelector("#palco .rotulo.selecionado") || {dataset: {}}).dataset.elemento,
            visivel: getComputedStyle(document.querySelector('#palco .recorte[data-elemento="' + i + '"] .texto'))
              .visibility})''', titulo)
        assert estado == {'foco': titulo, 'escolhido': titulo, 'visivel': 'visible'}, estado
        # Enter no titulo ja escolhido abre; Ctrl+Enter sem mudanca fecha sem gravar
        pg.keyboard.press('Enter')
        assert aberto(pg)
        pg.keyboard.press('Control+Enter')
        assert not aberto(pg) and not _edicoes(ted, job, gid)
        # o texto vazio fica no campo, com o motivo
        pg.keyboard.press('Enter')
        pg.keyboard.press('Control+a')
        pg.keyboard.press('Delete')
        pg.keyboard.press('Control+Enter')
        assert aberto(pg) and pg.evaluate(JS_CAMPO, titulo)['invalido'] == 'true'
        assert 'ficou vazio' in msg(pg) and not _edicoes(ted, job, gid)
        # o caractere fora da fonte: a recusa volta ao campo, com o texto do DA
        pg.keyboard.type('HAÇ')
        pg.keyboard.press('Control+Enter')
        tp._esperar(pg, '''() => { const c = document.querySelector("%s");
            return c && !c.readOnly && c.getAttribute("aria-invalid") === "true" ? "1" : ""; }''' % CAMPO)
        assert pg.evaluate(JS_CAMPO, titulo)['valor'] == 'HAÇ' and 'Ç' in msg(pg)
        assert not [e for e in _edicoes(ted, job, gid) if e['acao'] == 'texto']
        # o campo segue o zoom
        pg.evaluate('() => document.getElementById("aproximar").click()')
        pg.wait_for_timeout(200)  # numero-neutro: ms para o palco se ajustar
        v = pg.evaluate(JS_CAMPO, titulo)
        assert abs(v['esq'] - v['esqTexto']) <= 2 and v['topo'] < v['base'] < v['topo'] + v['linha'], v
        # o clique fora (no logo) aplica: o titulo continua escolhido e o logo nao anda
        pg.evaluate('() => document.querySelector("%s").focus()' % CAMPO)
        pg.keyboard.press('Control+a')
        pg.keyboard.type('HOX')
        x, y = _centro(pg, logo)
        pg.mouse.click(x, y)
        tp._esperar(pg, '() => document.querySelector("%s") ? "" : "1"' % CAMPO)
        ted._esperar_salvo(pg)
        edicoes = _edicoes(ted, job, gid)
        assert [(e['acao'], e.get('texto')) for e in edicoes] == [('texto', 'HOX')], edicoes
        assert pg.evaluate('() => document.querySelector("#palco .rotulo.selecionado").dataset.elemento') == titulo
        # o duplo clique no logo nao abre nada
        x, y = _centro(pg, logo)
        pg.mouse.dblclick(x, y)
        pg.wait_for_timeout(100)  # numero-neutro: ms
        assert not aberto(pg)
        # o clique tremido (2 px de tela) nao grava mover; o arraste de 20 px grava
        pg.mouse.move(x, y)
        pg.mouse.down()
        pg.mouse.move(x + 2, y, steps=2)  # numero-neutro: 2 px de tela
        pg.mouse.up()
        pg.wait_for_timeout(300)  # numero-neutro: ms
        assert len(_edicoes(ted, job, gid)) == 1
        pg.mouse.move(x, y)
        pg.mouse.down()
        pg.mouse.move(x + 20, y, steps=4)  # numero-neutro: 20 px de tela
        pg.mouse.up()
        ted._esperar_salvo(pg)
        assert [e['acao'] for e in _edicoes(ted, job, gid)] == ['texto', 'mover']
        # o duplo clique tremido no titulo abre o campo e nao grava mover
        x, y = _centro(pg, titulo)
        pg.mouse.move(x, y)
        pg.mouse.down()
        pg.mouse.move(x + 2, y)  # numero-neutro: 2 px de tela
        pg.mouse.up()
        pg.mouse.down(click_count=2)
        pg.mouse.up(click_count=2)
        tp._esperar(pg, '() => document.querySelector("%s") ? "1" : ""' % CAMPO)
        assert [e['acao'] for e in _edicoes(ted, job, gid)] == ['texto', 'mover']
        pg.keyboard.press('Escape')
        texto = pg.evaluate(tp.JS_TEXTO_DA_MOLDURA)
        assert '—' not in texto and '–' not in texto

    _na_tela_do_relato(relato, tmp_path, corpo)


# ------------------------------------------------------------------ revisao da 0.9.4
def test_tinta_do_texto_editado_na_borda_dentro_da_folga_nao_e_corte():
    # a caixa medida chega a borda do formato dentro de derivacao.enquadramento_tolerancia_px: a tela, a derivacao e o
    # preparo deixaram passar, e a tinta na ultima linha de pixel da pagina nao para o render
    W, H = 970, 250
    st = {'id': 'e01', 'tipo': 'texto', 'tinta': [12, 0, 514, 28], 'toca_regiao': ['topo']}
    for topo in (0.4, -0.5):
        e = {'id': 'e01', 'tipo': 'texto', 'layer_id': 2, 'regiao': [0, 0, 600, 60],
             'caixa_validada': [12.12, topo, 514.27, 27.71], 'texto_editado': True}
        assert rd.tinta_fora_da_caixa([e], [st], W, H) == [], topo
    # a caixa longe da borda e a tinta cortada nela: corte
    e = {'id': 'e01', 'tipo': 'texto', 'layer_id': 2, 'regiao': [0, 0, 600, 60],
         'caixa_validada': [12.12, 3.0, 514.27, 27.71], 'texto_editado': True}
    [x] = rd.tinta_fora_da_caixa([e], [st], W, H)
    assert x['cortada_na_regiao'] == ['topo']
    # sem a medida (a caixa e o formato inteiro), toda tinta na borda e corte
    sem = dict(e, caixa_validada=[0, 0, W, H], regiao=[0, 0, W, H])
    [x] = rd.tinta_fora_da_caixa([sem], [st], W, H)
    assert x['cortada_na_regiao'] == ['topo']


def test_motivo_da_tinta_fora_so_diz_borda_quando_ha_corte():
    corte = {'layer_id': 2, 'excesso_px': 0.4, 'tolerancia_px': 25.0, 'cortada_na_regiao': ['topo']}
    excesso = {'layer_id': 2, 'excesso_px': 40.0, 'tolerancia_px': 25.0, 'cortada_na_regiao': []}
    assert execucao.motivo_da_tinta_fora([], {2}) is None
    assert execucao.motivo_da_tinta_fora([corte], {2}) == 'texto_editado_cortado'
    # a medida e o render divergem dentro do formato: o texto nao passou da borda
    assert execucao.motivo_da_tinta_fora([excesso], {2}) == 'tinta_fora_da_caixa_validada'
    assert execucao.motivo_da_tinta_fora([corte], {3}) == 'tinta_fora_da_caixa_validada'


@pytest.mark.parametrize('folga', [-0.4, 0.5])
def test_texto_editado_na_borda_dentro_da_folga_renderiza(relato, tmp_path, pessoa, folga):
    # o 970x250 do relato: o titulo editado numa linha so, levado ate a borda de cima (topo da caixa em -folga). O
    # preparo e a tela deixam passar, e o render tambem (antes parava com texto_editado_cortado)
    from desdobra.derivacao import proposta as mp
    uma = 'HAX O HOAXAV H HOXAV'
    job = _copia(relato, tmp_path)
    _gravar(job, uma)
    c = _editado(_deriv(job, 'f970x250'), relato['layer_id'])['caixa_texto_editado']
    _gravar(job, uma, dy=(-folga - c[1]) / 250.0)  # numero-neutro: a altura do formato
    d = _deriv(job, 'f970x250')
    c2 = _editado(d, relato['layer_id'])['caixa_texto_editado']
    assert d['situacao'] == 'derivado'
    assert c2[1] == pytest.approx(-folga, abs=0.3), c2
    assert not mp.lados_fora(c2, 970, 250, 1.0)  # numero-neutro: o formato e a folga de 1 px
    contrato, bloqueios, conf = execucao.montar_contrato(job, 'f970x250')
    assert bloqueios == [], bloqueios
    rel = execucao.renderizar(job, disparo=humano.exigir('render'), formato='f970x250',
                              aceites=sorted({k['codigo'] for k in conf}))
    assert [x['linhas'] for x in rel['textos']['editados']] == [[uma]]


def test_chave_da_medida_do_editado_fica_fora_da_chave_da_quebra():
    # a camada do KV com um trecho so e kerning None, e a camada sintetica do editado com as mesmas linhas: sem o
    # espaco, as chaves eram iguais e a medida de uma servia a outra
    c = _camada()
    c['texto']['runs'][0]['kerning'] = None
    faces = [('f1', 'a' * 64)]  # numero-neutro: sha de mentira
    sint = mq.camada_do_editado(c, ['AB', 'CD'])
    assert medida_quebras.chave_da_medida(sint, (), (), faces) == medida_quebras.chave_da_medida(c, [], [], faces)
    assert medida_quebras.chave_da_medida(sint, (), (), faces, espaco='editado') != \
        medida_quebras.chave_da_medida(c, [], [], faces)


def test_preparo_com_a_derivacao_de_antes_pede_salvar_e_seguir(tmp_path, monkeypatch):
    # a familia confirmada numa versao anterior: a derivacao gravada nao confere com a de agora
    def montar(pasta, f):
        if f == 'f970x250':
            return None, [{'codigo': 'derivacao_desatualizada', 'descricao': '', 'medidas': {}}], []
        return {'formato': f}, [], []
    monkeypatch.setattr(execucao, 'montar_contrato', montar)
    monkeypatch.setattr(ato_render, '_formatos_do_briefing', lambda p: {'f970x250': '970x250', 'f1080x1080': '1080x1080'})

    class Tarefa:
        def parar(self):
            return False

        def progresso(self, *a):
            return None
    with pytest.raises(ato_render.ErroAtoRender) as e:
        ato_render.ato_de_render(tmp_path).preparar({'formatos': ['f1080x1080', 'f970x250']}, Tarefa())
    assert e.value.motivo == 'derivacao_velha'
    texto = tarefas.texto_do_motivo(e.value.motivo, e.value.resposta)
    assert texto == ('A família do formato 970x250 precisa ser salva de novo. Clique em Salvar e seguir e peça o '
                     'render de novo. Nada mudou no job.')
    # o outro bloqueio continua "formato bloqueado"
    monkeypatch.setattr(execucao, 'montar_contrato',
                        lambda p, f: (None, [{'codigo': 'formato_devolvido', 'descricao': '', 'medidas': {}}], []))
    with pytest.raises(ato_render.ErroAtoRender) as e:
        ato_render.ato_de_render(tmp_path).preparar({'formatos': ['f970x250']}, Tarefa())
    assert e.value.motivo == ato_render.MOTIVO_BLOQUEADO


def test_trocar_texto_leva_a_ancora_do_kv():
    from desdobra.tela import edicao
    t0 = {'texto': 'HAX O', 'corpo': 30.0}

    def palco(linhas):
        return {'largura': 100, 'altura': 100, 'pecas': [{'elemento': 'el1', 'tipo': 'texto', 'recorte': [0, 0, 1, 1],
                                                         'linhas': linhas}]}
    p = edicao.trocar_texto(palco([{'trechos': [t0], 'entrelinha': None},
                                   {'trechos': [dict(t0, texto='HOAXAV')], 'entrelinha': 36.0}]),
                            'el1', '\nHAX O')['pecas'][0]
    assert p['ancora_kv'] == {'texto': 'HAX O', 'acima': 0.0}
    assert [ln['trechos'][0]['texto'] for ln in p['linhas']] == ['', 'HAX O']
    # a primeira linha do KV sem tinta: a ancora e a primeira com tinta, uma entrelinha abaixo
    p = edicao.trocar_texto(palco([{'trechos': [dict(t0, texto=' ')], 'entrelinha': None},
                                   {'trechos': [dict(t0, texto='HOAXAV')], 'entrelinha': 36.0}]),
                            'el1', 'HAX O')['pecas'][0]
    assert p['ancora_kv'] == {'texto': 'HOAXAV', 'acima': 36.0}


JS_CAIXA_EDITADA = '() => document.querySelector("#palco .texto.editado").dataset.caixaTinta'


def _aplicar_no_editor(pg, ted, titulo, texto):
    ted._focar(pg, titulo)
    pg.keyboard.press('Enter')
    pg.evaluate('() => document.getElementById("ed-texto").click()')
    pg.fill('#ed-campo-texto', texto)
    pg.evaluate('() => document.getElementById("ed-texto-aplicar").click()')
    tp._esperar(pg, '() => document.getElementById("editor-texto").hidden ? "1" : ""')
    ted._esperar_salvo(pg)
    tp._esperar(pg, '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""')
    tp._esperar(pg, '() => { const t = document.querySelector("#palco .texto.editado"); '
                    'return t && t.dataset.caixaTinta ? "1" : ""; }')


@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
@pytest.mark.parametrize('texto', ['HAX O\nHOAXAV', '\nHAX O\nHOAXAV'])
def test_caixa_da_tela_bate_com_a_do_motor_tambem_com_a_primeira_linha_vazia(relato, tmp_path, texto):
    # a previa ancora o texto editado pela primeira linha de base, como o render: a primeira linha vazia ocupa uma
    # entrelinha e o texto desce (antes a tela o deixava uma entrelinha acima do render)
    import test_tela_edicao as ted
    vista = {}

    def corpo(pg, job, gid, titulo, _logo):
        _aplicar_no_editor(pg, ted, titulo, texto)
        vista['caixa'] = [float(v) for v in pg.evaluate(JS_CAIXA_EDITADA).split(',')]

    _na_tela_do_relato(relato, tmp_path / 'tela', corpo)
    job = _copia(relato, tmp_path / 'motor')
    _gravar(job, texto)
    no_motor = _editado(_deriv(job, 'f1080x1080'), relato['layer_id'])['caixa_texto_editado']
    assert vista['caixa'] == pytest.approx(no_motor, abs=3), (vista['caixa'], no_motor)  # numero-neutro: px


JS_PONTA = '''i => {
    const r = document.querySelector('#palco .rotulo[data-elemento="' + i + '"]').getBoundingClientRect();
    const ts = Array.from(document.querySelectorAll('#palco .recorte[data-elemento="' + i + '"] .texto .linha'));
    const l = ts[0].querySelectorAll('.trecho');
    const b = l[l.length - 1].getBoundingClientRect();
    return {rotulo: [r.left, r.top, r.right, r.bottom], ponta: [b.right - 4, b.top + b.height / 2]};
}'''


@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
def test_rotulo_cobre_o_texto_que_cresceu_e_o_duplo_clique_ali_abre_o_campo(relato, tmp_path):
    import test_tela_edicao as ted

    def corpo(pg, job, gid, titulo, _logo):
        _aplicar_no_editor(pg, ted, titulo, LONGO)
        g = pg.evaluate(JS_PONTA, titulo)
        # a moldura (o rotulo) vai ate a ponta da linha que cresceu
        assert g['rotulo'][2] >= g['ponta'][0] + 3, g  # numero-neutro: px de tela
        pg.mouse.dblclick(*g['ponta'])
        tp._esperar(pg, '() => document.querySelector("%s") ? "1" : ""' % CAMPO)
        assert pg.evaluate(JS_CAMPO, titulo)['valor'] == LONGO
        # em escrita, a etiqueta do rotulo some (o contorno do campo passava por cima dela)
        assert pg.evaluate('''i => getComputedStyle(document.querySelector('#palco .rotulo[data-elemento="' + i +
                              '"] .etiqueta')).visibility''', titulo) == 'hidden'
        pg.keyboard.press('Escape')
        # a faixa da borda chama o membro de arquivo, como o resto da tela
        assert pg.evaluate('() => document.getElementById("ver-borda").textContent') == 'Ver o arquivo'

    _na_tela_do_relato(relato, tmp_path, corpo)


@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
def test_no_970_o_campo_fica_legivel_e_a_etiqueta_do_logo_nao_tapa_o_titulo(relato, tmp_path):
    def corpo(pg, job, gid, titulo, logo):
        x, y = _centro(pg, titulo)
        # no 970x250 ajustado, a etiqueta do logo cobre o meio do titulo; o duplo clique passa por ela
        em_cima = pg.evaluate('''([x, y]) => { const n = document.elementFromPoint(x, y);
            return [!!n.closest(".etiqueta"), n.closest(".rotulo").dataset.elemento]; }''', [x, y])
        assert em_cima == [True, logo], em_cima
        pg.mouse.dblclick(x, y)
        tp._esperar(pg, '() => document.querySelector("%s") ? "1" : ""' % CAMPO)
        assert pg.evaluate('() => document.querySelector("%s").dataset.elemento' % CAMPO) == titulo
        v = pg.evaluate(JS_CAMPO, titulo)
        assert v['corpo'] >= 14 - 0.1, v  # numero-neutro: CAMPO_CORPO_MIN_PX da tela
        assert v['corpo'] == pytest.approx(v['corpoTexto'] * v['k'], rel=0.02), v
        pg.keyboard.press('Escape')

    # 0.10.0 (decisao 199): a familia de um arquivo so (o 970x250) nao mostra mais a faixa "Como fica em cada arquivo",
    # e o palco ganhou a altura dela. A janela perde essa altura, para o palco ter a exibicao do relato, com a etiqueta
    # do logo sobre o titulo
    _na_tela_do_relato(relato, tmp_path, corpo, formato='f970x250', janela=(1600, 790))  # numero-neutro: px
