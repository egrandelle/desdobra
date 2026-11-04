# -*- coding: utf-8 -*-
"""Revisao 3 do M5 (scratchpad/m5/revisao3/achados.md), escrita antes do codigo.

C1 a caixa do texto juntado nao e cortada no canvas; A1 a largura das linhas juntadas vem de medida (no Chromium, com
a fonte servida pelo motor, como na conferencia de fontes) e o render confere a tinta real contra a caixa validada;
A2 quebra por familia em caixa de paragrafo e recusada; A3 e M5 as quebras aprovadas (mestre propria e familia)
chegam ao render, em todos os textos do elemento; M1 a ancora do DA num membro de grupo vale (ou e registrada);
M2 a media vence a fraca de verdade; M3 objeto solto exige opacidade; M4 o conferir das quebras por familia; B1 so
indices no envelope; B2 a mesma regra para a quebra do fim.
"""
import pytest

import test_derivacao_apoio as ap
from desdobra import limites
from desdobra.briefing import modelo as mb
from desdobra.derivacao import nucleo as nd
from desdobra.derivacao import quebras as mq
from desdobra.derivacao import solver as msol
from desdobra.render import derivado as mder
from desdobra.render import texto as mtexto
from test_derivacao_blocos import camada

Q = chr(13)
FUN = {1: 'fundo', 10: 'titulo', 30: 'logo_principal'}


def _titulo(caixa, linhas, paragrafo=False):
    c = camada(10, 'texto', caixa, corpo=30)
    conteudo = Q.join(linhas) + Q
    c['texto'].update({'conteudo': conteudo, 'paragrafos': [], 'justificacao': 'LEFT', 'tipo_caixa': 'ponto'})
    if paragrafo:
        c['texto'].update({'tipo_caixa': 'paragrafo', 'box_bounds': [0, 0, 100, 60]})
    c['texto']['runs'][0].update({'inicio': 0, 'fim': len(conteudo), 'texto': conteudo, 'entrelinha_efetiva_px': 23.0})
    return c


def _laudo(logo=(330, 150, 380, 185), paragrafo=False):
    return ap.laudo(400, 200, [camada(1, 'pixel', [0, 0, 400, 200]),
                               _titulo([20, 40, 260, 110], ['a' * 10] * 3, paragrafo),
                               camada(30, 'smart_embutido', list(logo))])


def _qb(manter=(), **k):
    item = {'layer_id': 10, 'razao_min': 2.5, 'razao_max': None, 'quebras': ap.decisao(list(manter))}
    item.update(k)
    return item


def _b(qb, formatos=None, **k):
    return ap.briefing(funcoes=FUN, formatos=formatos or [ap.formato('largo', 760, 240)],
                       familias={'faixa': ap.decisao(3.0)}, quebras_por_familia=qb, **k)


def _medida(largura_juntada, largura_mestre=240.0):
    """Medida injetada (a que o Chromium daria), no espaco de texto: a linha mais larga da mestre e a do texto juntado."""
    return {'largura_texto_mestre': largura_mestre, 'largura_texto': largura_juntada, 'linhas': 1}


def _derivar(laudo, b, medidas=None, ident='largo'):
    ctx = nd.contexto(laudo, b, medidas_quebras=medidas)
    return nd.derivar_em_memoria(ctx, specs={})['formatos'][ident]


# ------------------------------------------------------------------ C1 e A1
def test_c1_caixa_juntada_nao_e_cortada_no_canvas_da_mestre():
    laudo = _laudo()
    d = _derivar(laudo, _b([_qb()]), {mq.chave(10, []): _medida(740.0)})
    t = next(e for e in d['elementos'] if e['id'] == 'el10') if d['situacao'] == 'derivado' else None
    if t is not None:
        # a linha juntada (740 na escala da mestre, partindo de x 20) passa do canvas de 400: a caixa nao e cortada
        assert t['caixa_mestre'][2] - t['caixa_mestre'][0] == pytest.approx(740.0, abs=0.5)
        assert t['caixa'][2] <= 760 + limites.valor('derivacao.enquadramento_tolerancia_px')
    else:
        assert d['devolucao']['motivo'] in ('restricao_obrigatoria_nao_fecha', 'validacao_obrigatoria_reprovou')


def test_c1_caixa_juntada_que_passa_por_cima_do_logo_na_mestre_nao_entra_por_cima_dele():
    laudo = _laudo(logo=(330, 40, 380, 70))
    d = _derivar(laudo, _b([_qb()]), {mq.chave(10, []): _medida(740.0)})
    if d['situacao'] == 'derivado':
        el = {e['id']: e for e in d['elementos']}
        t, lg = el['el10']['caixa'], el['el30']['caixa']
        tol = limites.valor('derivacao.colisao_tolerancia_px')
        assert min(t[2], lg[2]) - max(t[0], lg[0]) <= tol or min(t[3], lg[3]) - max(t[1], lg[1]) <= tol


def test_a1_largura_vem_da_medida_e_altura_das_linhas_que_ficam():
    laudo = _laudo()
    d = _derivar(laudo, _b([_qb()]), {mq.chave(10, []): _medida(480.0)})
    assert d['situacao'] == 'derivado', d['devolucao']
    t = next(e for e in d['elementos'] if e['id'] == 'el10')
    m = t['caixa_mestre']
    # largura: a medida juntada na proporcao da tinta da mestre (240 de tinta para 240 de texto); altura: 70 menos as
    # duas entrelinhas tiradas (23 px cada)
    assert m[2] - m[0] == pytest.approx(480.0, abs=0.5)
    assert m[3] - m[1] == pytest.approx(70.0 - 2 * 23.0, abs=0.5)


def test_a1_sem_medida_o_formato_volta_ao_da():
    d = _derivar(_laudo(), _b([_qb()]), None)
    assert d['situacao'] == 'devolvido' and d['devolucao']['motivo'] == 'quebra_sem_medida'


def test_a1_render_reprova_tinta_fora_da_caixa_validada():
    entradas = [{'id': 'e01', 'tipo': 'texto', 'layer_id': 10, 'caixa_validada': [100, 50, 300, 80],
                 'regiao': [90, 40, 310, 90]}]
    ok = [{'id': 'e01', 'tipo': 'texto', 'layer_id': 10, 'tinta': [101, 52, 299, 79], 'toca_regiao': []}]
    assert mder.tinta_fora_da_caixa(entradas, ok, 400, 200) == []
    fora = [{'id': 'e01', 'tipo': 'texto', 'layer_id': 10, 'tinta': [101, 52, 330, 79], 'toca_regiao': []}]
    assert [x['layer_id'] for x in mder.tinta_fora_da_caixa(entradas, fora, 400, 200)] == [10]
    cortada = [{'id': 'e01', 'tipo': 'texto', 'layer_id': 10, 'tinta': [101, 52, 300, 79], 'toca_regiao': ['dir']}]
    assert [x['layer_id'] for x in mder.tinta_fora_da_caixa(entradas, cortada, 400, 200)] == [10]
    for lid in ('render.tolerancia_tinta_texto', 'render.tolerancia_tinta_texto_min_px'):
        lim = limites.obter(lid)
        assert lim.fonte and lim.situacao == 'a_calibrar'


# ------------------------------------------------------------------ A2
def test_a2_quebra_por_familia_em_caixa_de_paragrafo_e_recusada():
    laudo = _laudo(paragrafo=True)
    assert 'quebra_em_caixa_de_paragrafo' in {e['codigo'] for e in mb.conferir(laudo, _b([_qb()]))}


# ------------------------------------------------------------------ A3 e M5
def test_a3_quebras_da_mestre_propria_chegam_ao_render():
    el = {'id': 'el10', 'quebras': [3], 'quebras_camada': 11, 'transformacao': {}}
    entrada = {'layer_id': 11, 'texto': {'conteudo': 'aaa bbb' + Q}}
    assert mder.quebras_da_entrada(el, entrada) == {'quebras_inseridas': [3]}
    t = {'runs': [{'inicio': 0, 'fim': 8, 'texto': 'aaa bbb' + Q, 'tem_tinta': True}], 'paragrafos': []}
    linhas = mtexto.linhas_da_camada(t, quebras=[3])
    assert [''.join(p[0] for p in ln['pedacos']) for ln in linhas] == ['aaa', 'bbb']


def test_m5_todos_os_textos_com_quebra_aprovada_do_elemento():
    el = {'id': 'el10', 'quebras': {'familia': [{'layer_id': 11, 'aprovadas': []}, {'layer_id': 12, 'aprovadas': [0]}]}}
    e11 = {'layer_id': 11, 'texto': {'conteudo': 'aa' + Q + 'bb' + Q}}
    e12 = {'layer_id': 12, 'texto': {'conteudo': 'cc' + Q + 'dd' + Q + 'ee' + Q}}
    assert mder.quebras_da_entrada(el, e11) == {'quebras_juntadas': [2]}
    assert mder.quebras_da_entrada(el, e12) == {'quebras_juntadas': [5]}


def test_b1_envelope_so_leva_indices_das_quebras():
    d = _derivar(_laudo(), _b([_qb([1])]), {mq.chave(10, [1]): _medida(250.0)})
    assert d['situacao'] == 'derivado', d['devolucao']
    t = next(e for e in d['elementos'] if e['id'] == 'el10')
    assert t['quebras'] == {'familia': [{'layer_id': 10, 'aprovadas': [1], 'caixa_doc': t['quebras']['familia'][0]['caixa_doc']}]}
    assert 'juntadas' not in str(t['quebras'])


def test_b2_quebra_do_fim_mesma_regra_do_render():
    c = _titulo([0, 0, 10, 10], ['aa', 'bb'])
    c['texto']['conteudo'] = 'aa' + Q + 'bb' + Q + '  '
    # o render abre uma linha so de espacos depois da ultima quebra; o motor conta a mesma quebra
    assert mq.posicoes_de_quebra(c) == [2, 5]
    c['texto']['conteudo'] = 'aa' + Q + 'bb' + Q
    assert mq.posicoes_de_quebra(c) == [2]


# ------------------------------------------------------------------ M1
def _icones(ancora_icones=None):
    from test_derivacao_rodada3 import FUNCOES_ICONES, ANCORAS_ICONES, _icones as ic
    b = ap.briefing(funcoes=FUNCOES_ICONES, formatos=[ap.formato('largo', 760, 240)], ancoras=ANCORAS_ICONES,
                    familias={'faixa': ap.decisao(3.0)})
    if ancora_icones:
        b['ancoras'].append({'layer_id': 5, 'funcao': None, 'x': ap.decisao(ancora_icones[0]),
                             'y': ap.decisao(ancora_icones[1])})
    return ap.laudo(400, 200, ic()), b


def test_m1_ancora_do_da_num_membro_do_grupo_vale_e_fica_registrada():
    laudo, b0 = _icones()
    d0 = nd.derivar_em_memoria(nd.contexto(laudo, b0), specs={})['formatos']['largo']
    laudo, b1 = _icones(('direita', 'topo'))
    d1 = nd.derivar_em_memoria(nd.contexto(laudo, b1), specs={})['formatos']['largo']
    assert d1['situacao'] == 'derivado', d1['devolucao']
    reg = [x for x in d1['restricoes'] if x['nome'].startswith('ancora_do_grupo_y')]
    assert reg and reg[0]['forca'] == 'registro' and reg[0]['elementos'][0] == 'el5'
    g0 = {e['id']: e['caixa'] for e in d0['elementos']}
    g1 = {e['id']: e['caixa'] for e in d1['elementos']}
    assert g0['el5'] != g1['el5']


# ------------------------------------------------------------------ M2
def test_m2_media_vence_fraca_e_o_teste_falha_com_a_ordem_invertida(monkeypatch):
    sg = {'esq': False, 'topo': False, 'dir': False, 'base': False}
    # um grafismo (nao conteudo: a forca forte da escala de conteudo, decisoes-v1.md 132, nao entra)
    els = [{'id': 'a', 'caixa': [100.0, 100.0, 300.0, 140.0], 'sangra': sg, 'classe': 'base', 'funcao': 'grafismo',
            'regra': 'constante', 'ancora': ('esquerda', 'topo')}]

    def escala():
        _c, escalas, _r = msol.resolver(els, (1920.0, 1080.0), (3840.0, 1080.0), {}, [3.0])
        return escalas[0]
    # a margem da mestre (media) prende a altura: 100 em cima e 940 embaixo deixam 40 px, escala 1; a regra (fraca)
    # pedia 3
    assert escala() == pytest.approx(1.0, abs=1e-4)
    monkeypatch.setattr(msol, 'FORCAS', ('strong', 'weak', 'medium'))
    assert escala() != pytest.approx(1.0, abs=1e-4)


# ------------------------------------------------------------------ M3
@pytest.mark.parametrize('opacidade', [20, 0])
def test_m3_objeto_solto_exige_opacidade(opacidade):
    from test_derivacao_rodada3 import ANCORAS_ICONES, FUNCOES_ICONES, _icones as ic
    cams = ic()
    cams[2]['aparencia']['opacidade'] = opacidade
    b = ap.briefing(funcoes=FUNCOES_ICONES, formatos=[ap.formato('largo', 760, 240)], ancoras=ANCORAS_ICONES,
                    familias={'faixa': ap.decisao(3.0)})
    d = nd.derivar_em_memoria(nd.contexto(ap.laudo(400, 200, cams), b), specs={})['formatos']['largo']
    assert not any('el5' in x['elementos'] for x in d['restricoes'] if x['nome'].startswith(('nao_sobrepor', 'proximidade')))
    lim = limites.obter('derivacao.objeto_solto_opacidade_min')
    assert lim.fonte and lim.situacao == 'a_calibrar'


# ------------------------------------------------------------------ M4
def test_m4_conferir_das_quebras_por_familia():
    laudo = _laudo()

    def codigos(qb):
        return {e['codigo'] for e in mb.conferir(laudo, _b(qb))}
    assert 'quebra_para_formato_inexistente' in codigos([_qb(formatos=['nao-existe'], razao_min=None)])
    assert 'quebra_com_faixa_invertida' in codigos([_qb(razao_min=3.0, razao_max=2.0)])
    assert 'quebras_conflitantes' in codigos([_qb([0], razao_min=2.0, razao_max=3.5), _qb([1], razao_min=3.0)])
    assert not codigos([_qb([0], razao_min=2.0, razao_max=2.9), _qb([1], razao_min=3.0)]) & {
        'quebras_conflitantes', 'quebra_com_faixa_invertida', 'quebra_para_formato_inexistente'}


def test_m4_formato_vence_faixa():
    b = _b([_qb([1]), _qb([0], formatos=['largo'], razao_min=None)])
    assert mq.aprovadas_para(b, 10, {'id': 'largo'}, 760, 240) == [0]


# ------------------------------------------------------------------ A1 pelo caminho real: medida no Chromium e render
def _psd_quebras(destino):
    """PSD 320 x 160: fundo creme, um texto de duas linhas (a primeira de 8 'i' estreitos, a segunda de 3 'W' largos:
    a linha com mais caracteres nao e a mais larga) e um logo verde."""
    from PIL import Image
    from psd_tools import PSDImage

    import test_render_apoio as rap
    p = PSDImage.new('RGB', (320, 160), color=(255, 255, 255))
    p.create_pixel_layer(Image.new('RGBA', (320, 160), (240, 236, 220, 255)), name='fundo-sintetico')
    t = p.create_pixel_layer(Image.new('RGBA', (70, 50), (20, 20, 20, 255)), name='texto-duas-linhas', top=20, left=10)
    rap._virar_texto(t, [('iiiiiiii' + Q + 'WWW', 20.0, rap.COR_1)], 10.0, 40.0, 60.0)
    p.create_pixel_layer(Image.new('RGBA', (40, 40), (0, 120, 60, 255)), name='logo-sintetico', top=110, left=260)
    return rap._salvar(p, destino)


AVANCOS = {'i': 200, 'W': 1000}


@pytest.fixture(scope='module')
def job_quebras(tmp_path_factory):
    import sys
    if sys.platform != 'win32':
        pytest.skip('o isolador dos filhos roda no Windows')
    import json as _json

    import test_fontes_apoio as fap
    import test_render_apoio as rap
    from desdobra import contratos
    from desdobra.job import nucleo
    base = tmp_path_factory.mktemp('quebras')
    fontes = base / 'origem-fontes'
    fap.gravar(fontes, 'inventada.ttf', fap.fonte(ps=rap.FONTE, avancos=AVANCOS))
    job = base / 'job'
    nucleo.criar(job, _psd_quebras(base / 'origem' / 'kv.psd'), 'c', fontes=[fontes])
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    ids = {c['nome']: c['identidade']['layer_id'] for c in laudo['camadas']}
    texto = ids['texto-duas-linhas']
    b = ap.briefing(funcoes={ids['fundo-sintetico']: 'fundo', texto: 'titulo', ids['logo-sintetico']: 'logo_principal'},
                    formatos=[ap.formato('largo', 720, 200)], familias={'faixa': ap.decisao(3.0)},
                    quebras_por_familia=[{'layer_id': texto, 'razao_min': 3.0, 'razao_max': None,
                                          'quebras': ap.decisao([])}])
    b.pop('cabecalho')
    b.pop('job_id')
    arq = base / 'fixture.json'
    arq.write_text(_json.dumps(b), encoding='utf-8')
    return {'job': job, 'fixture': arq, 'texto': texto, 'laudo': laudo}


def _derivar_job(job_quebras, python):
    import test_derivacao_job as tj
    cod, env = tj._cli(python, 'briefing', 'importar', str(job_quebras['fixture']), '--teste', '--job',
                       str(job_quebras['job']))
    assert cod == 0, env
    cod, env = tj._cli(python, 'derivar', '--job', str(job_quebras['job']))
    assert cod == 0, env


def test_a1_largura_juntada_medida_no_chromium(job_quebras, python):
    import test_fontes_apoio as fap
    from desdobra import contratos
    _derivar_job(job_quebras, python)
    d = contratos.ler(job_quebras['job'] / 'derivacao' / 'largo.json', 'derivacao/1')
    assert d['situacao'] == 'derivado', d['devolucao']
    el = next(e for e in d['elementos'] if job_quebras['texto'] in e['layer_ids'])
    fam = el['quebras']['familia'][0]
    tinta = next(c for c in job_quebras['laudo']['camadas'] if c['identidade']['layer_id'] == job_quebras['texto'])
    w0 = tinta['geometria']['caixa_tinta'][2] - tinta['geometria']['caixa_tinta'][0]
    w1 = fam['caixa_doc'][2] - fam['caixa_doc'][0]
    juntada = fap.largura('iiiiiiii WWW', 20.0, avancos=AVANCOS)
    mestre = fap.largura('WWW', 20.0, avancos=AVANCOS)
    # a medida: a linha juntada contra a mais larga da mestre (a de 'W'); a contagem de caracteres daria 12 / 8
    assert w1 / w0 == pytest.approx(juntada / mestre, rel=0.03)
    assert abs(w1 / w0 - 12 / 8.0) > 0.1


def test_a1_render_da_quebra_juntada_confere_a_tinta(job_quebras, python, pessoa):
    from desdobra.render import execucao
    _derivar_job(job_quebras, python)
    contrato, bloqueios, _c = mder.montar(job_quebras['job'], 'largo')
    assert not bloqueios, bloqueios
    t = next(e for e in contrato['entradas'] if e['tipo'] == 'texto')
    assert t['quebras_juntadas'] and t['caixa_validada']
    rel = getattr(execucao, 'renderizar')(job_quebras['job'], disparo=pessoa.exigir('render'), formato='largo')
    assert rel['formato']['chave'] == 'largo'
