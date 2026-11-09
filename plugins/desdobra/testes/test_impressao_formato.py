# -*- coding: utf-8 -*-
"""Impressao por formato (M7b, A1; desdobra.derivacao.impressao): o sha256 de tudo o que alimenta um formato muda com
cada entrada dele (funcao, regra, ancora, quebra, composicao da familia, spec, mestre, derivacao) e fica igual quando
a mudanca e fora do escopo dele. Material sintetico (test_derivacao_apoio)."""
import pytest

import test_derivacao_apoio as ap
from desdobra.briefing import modelo as mb
from desdobra.derivacao import impressao as mi
from desdobra.derivacao import nucleo as nd

CONF = {'origem': 'fixture_de_teste', 'meio': 'medicao', 'em': '2026-11-06T10:00:00'}
CH = 'teste|folha|800x400'


def _briefing():
    """mesmo (transform, com folha, el20 apagado pelo DA na familia dele), perto (solver), vertical e alto
    (galeria)."""
    fmts = [ap.formato('mesmo', 800, 400, chave=CH), ap.formato('perto', 480, 300), ap.formato('vertical', 300, 600),
            ap.formato('alto', 1080, 1920)]
    b = ap.briefing(formatos=fmts)
    b['composicoes'] = [
        {'familia': 'grande', 'formatos': ['mesmo'], 'versao': None, 'edicoes': [{'elemento': 'el20', 'acao': 'apagar'}],
         'confirmada': True, 'confirmacao': CONF},
        {'familia': 'horizontais', 'formatos': ['perto'], 'versao': None, 'edicoes': [], 'confirmada': True,
         'confirmacao': CONF},
        {'familia': 'verticais', 'formatos': ['vertical', 'alto'], 'versao': None, 'edicoes': [], 'confirmada': True,
         'confirmacao': CONF}]
    return b


def _specs(util=360):
    return {CH: ap.spec(CH, {'dimensao': {'largura': 800, 'altura': 400}, 'area_util': {'largura': 800, 'altura': util}})}


def _todas(b, specs=None, laudo=None):
    """{id: impressao} de cada formato, derivado de novo."""
    specs = _specs() if specs is None else specs
    ctx = nd.contexto(laudo or ap.laudo(), b)
    r = nd.derivar_em_memoria(ctx, specs=specs, arquivo_specs='specs/rascunho.json')
    res = mi.resolvido(ctx['briefing'], ctx['resolvidas'], specs)
    return {k: mi.impressao(d, res, k) for k, d in r['formatos'].items()}, r


def _fixa(b, specs=None, fid='mesmo', base=None):
    """A impressao de fid com a derivacao de base (a do briefing de _briefing) e as entradas de b: so a parte das
    entradas muda."""
    specs = _specs() if specs is None else specs
    d = (base or _todas(_briefing())[1])['formatos'][fid]
    ctx = nd.contexto(ap.laudo(), b)
    return mi.impressao(d, mi.resolvido(ctx['briefing'], ctx['resolvidas'], specs), fid)


@pytest.fixture(scope='module')
def base():
    imp, r = _todas(_briefing())
    return imp, r


def _funcao(b, lid, funcao):
    next(x for x in b['funcoes'] if x['layer_id'] == lid)['funcao'] = ap.decisao(funcao)


def _regra(b, funcao, regra):
    item = next((x for x in b['regras_escala'] if x['funcao'] == funcao), None)
    if item is None:
        b['regras_escala'].append({'funcao': funcao, 'regra': ap.decisao(regra)})
    else:
        item['regra'] = ap.decisao(regra)


def test_caminhos_da_base_e_sha_de_64(base):
    imp, r = base
    assert {k: d['caminho'] for k, d in r['formatos'].items()} == {
        'mesmo': 'transform', 'perto': 'solver', 'vertical': 'galeria', 'alto': 'galeria'}
    assert all(d['situacao'] == 'derivado' for d in r['formatos'].values())
    assert 'el20' not in {e['id'] for e in r['formatos']['mesmo']['elementos']}
    assert all(len(v) == 64 and int(v, 16) >= 0 for v in imp.values())
    assert len(set(imp.values())) == len(imp)


def test_impressao_e_pura_e_ignora_carimbo_sha_do_briefing_e_inventario(base):
    imp, r = base
    b = _briefing()
    for k, d in r['formatos'].items():
        assert _fixa(b, fid=k, base=r) == imp[k]
        outro = dict(d, gerado_em='2099-01-01T00:00:00+00:00', briefing_sha256='f' * 64,
                     inventario_entre_formatos='diferente' if d['inventario_entre_formatos'] == 'igual' else 'igual')
        ctx = nd.contexto(ap.laudo(), b)
        assert mi.impressao(outro, mi.resolvido(ctx['briefing'], ctx['resolvidas'], _specs()), k) == imp[k]


def test_ruido_de_ponto_flutuante_abaixo_das_casas_nao_muda(base):
    imp, r = base
    d = ap.copia(r['formatos']['perto'])
    d['elementos'][0]['caixa'] = [v + 1e-9 for v in d['elementos'][0]['caixa']]
    ctx = nd.contexto(ap.laudo(), _briefing())
    assert mi.impressao(d, mi.resolvido(ctx['briefing'], ctx['resolvidas'], {}), 'perto') == imp['perto']


def test_mudar_a_derivacao_muda(base):
    imp, r = base
    d = ap.copia(r['formatos']['perto'])
    d['elementos'][0]['caixa'][0] += 1
    ctx = nd.contexto(ap.laudo(), _briefing())
    assert mi.impressao(d, mi.resolvido(ctx['briefing'], ctx['resolvidas'], {}), 'perto') != imp['perto']


def test_funcao_resolvida_de_camada_do_formato_muda(base):
    imp, r = base
    b = _briefing()
    _funcao(b, 40, 'cta')  # o legal vira cta: mesma geometria na derivacao fixa, entrada diferente
    assert _fixa(b, base=r) != imp['mesmo']


def test_regra_de_escala_da_funcao_do_formato_muda(base):
    imp, r = base
    b = _briefing()
    _regra(b, 'texto_legal', 'raiz_area')
    assert _fixa(b, base=r) != imp['mesmo']


def test_regra_do_indeterminado_e_do_bloco_mudam(base):
    imp, r = base
    b = _briefing()
    b['regras_indeterminado'].append({'layer_id': 40, 'regra': ap.decisao('contain')})
    assert _fixa(b, base=r) != imp['mesmo']
    b = _briefing()
    b['regras_bloco'] = [{'layer_id': 11, 'regra': ap.decisao('contain')}]
    assert _fixa(b, base=r) != imp['mesmo']


def test_ancora_da_funcao_e_do_elemento_mudam(base):
    imp, r = base
    b = _briefing()
    next(a for a in b['ancoras'] if a['funcao'] == 'titulo')['x'] = ap.decisao('direita')
    assert _fixa(b, base=r) != imp['mesmo']
    b = _briefing()
    b['ancoras'].append({'layer_id': 30, 'x': ap.decisao('esquerda'), 'y': ap.decisao('topo')})
    assert _fixa(b, base=r) != imp['mesmo']


def test_quebra_aprovada_para_o_formato_muda_e_a_de_outro_formato_nao(base):
    imp, r = base
    b = _briefing()
    b['quebras_por_familia'] = [{'layer_id': 11, 'formatos': ['mesmo'], 'quebras': ap.decisao([])}]
    assert _fixa(b, base=r) != imp['mesmo']
    b['quebras_por_familia'] = [{'layer_id': 11, 'formatos': ['perto'], 'quebras': ap.decisao([])}]
    assert _fixa(b, base=r) == imp['mesmo']
    # pela faixa de proporcao: 800 x 400 e razao 2
    b['quebras_por_familia'] = [{'layer_id': 11, 'razao_min': 1.5, 'razao_max': 2.5, 'quebras': ap.decisao([])}]
    assert _fixa(b, base=r) != imp['mesmo']
    b['quebras_por_familia'] = [{'layer_id': 11, 'razao_min': 0.2, 'razao_max': 0.8, 'quebras': ap.decisao([])}]
    assert _fixa(b, base=r) == imp['mesmo']


def test_composicao_da_familia_muda_e_a_de_outra_familia_nao(base):
    imp, r = base
    b = _briefing()
    b['composicoes'][0]['edicoes'] = [{'elemento': 'el30', 'acao': 'mover', 'dx': 0.01, 'dy': 0.0}]
    assert _fixa(b, base=r) != imp['mesmo']
    b = _briefing()
    b['composicoes'][0]['versao'] = 'v2'
    assert _fixa(b, base=r) != imp['mesmo']
    b = _briefing()
    b['composicoes'][1]['edicoes'].append({'elemento': 'el30', 'acao': 'mover', 'dx': 0.01, 'dy': 0.0})
    assert _fixa(b, base=r) == imp['mesmo']


def test_confirmar_a_familia_de_novo_sem_mudar_nada_deixa_igual(base):
    # decisoes-v1.md, 175 (M7b, A6): a mudanca do passo 2 pede nova confirmacao de toda familia; confirmar de novo a
    # mesma versao e as mesmas edicoes so muda o carimbo da confirmacao, que fica fora da conta (na composicao e na
    # proposta gravada)
    imp, _r = base
    b = _briefing()
    for c in b['composicoes']:
        c['confirmacao'] = dict(CONF, em='2026-11-07T09:30:00')
    imp2, r2 = _todas(b)
    assert imp2 == imp
    assert r2['formatos']['perto']['proposta']['confirmacao']['em'] == '2026-11-07T09:30:00'
    # a origem da confirmacao continua na conta (o apagado leva a origem dela)
    b = _briefing()
    b['composicoes'][0]['confirmacao'] = dict(CONF, origem='da', meio='tela')
    imp3, _r3 = _todas(b)
    assert imp3['mesmo'] != imp['mesmo'] and imp3['perto'] == imp['perto']


def test_valor_de_spec_do_formato_muda_e_o_de_outro_formato_nao(base):
    imp, r = base
    b = _briefing()
    assert _fixa(b, specs=_specs(util=350), base=r) != imp['mesmo']
    outra = dict(_specs(), **{'teste|outra|1x1': ap.spec('teste|outra|1x1', {'area_util': {'largura': 1, 'altura': 1}})})
    assert _fixa(b, specs=outra, base=r) == imp['mesmo']
    # a fonte do campo (pagina, trecho) nao alimenta o formato
    sp = _specs()
    sp[CH]['campos']['area_util']['fonte'] = {'folha': 'f2', 'trecho': 'p09-t999', 'pagina': 9}
    assert _fixa(b, specs=sp, base=r) == imp['mesmo']


def test_formato_do_briefing_muda():
    b = _briefing()
    r = _todas(b)[1]
    imp = _fixa(b, base=r)
    b['formatos'][0]['rotacao'] = {'graus': 180, 'sentido': None}
    assert _fixa(b, base=r) != imp


def _com_propria(caixa_titulo=(20, 40, 280, 140)):
    caixas = {1: [0, 0, 300, 600], 10: list(caixa_titulo), 20: [20, 200, 280, 230], 30: [200, 500, 280, 580],
              40: [20, 560, 180, 580]}
    b = ap.briefing(formatos=[ap.formato('mesmo', 800, 400), ap.formato('v300', 300, 600), ap.formato('v320', 320, 560)],
                    mestres=[{'id': 'kv', 'tipo': 'kv'},
                             {'id': 'vertical', 'tipo': 'propria', 'formato': 'v300',
                              'elementos': [{'layer_id': k, 'caixa': v, 'quebras': 'origem'}
                                            for k, v in sorted(caixas.items())]}])
    return b


def test_mestre_usada_muda_e_a_mestre_de_outra_familia_nao():
    b = _com_propria()
    ctx = nd.contexto(ap.laudo(), b)
    r = nd.derivar_em_memoria(ctx, specs={}, arquivo_specs='specs/rascunho.json')
    assert r['formatos']['v320']['mestre']['id'] == 'vertical' and r['formatos']['mesmo']['mestre']['id'] == 'kv'
    antes = {k: mi.impressao(r['formatos'][k], mi.resolvido(b, ctx['resolvidas'], {}), k) for k in ('v320', 'mesmo')}
    b2 = _com_propria(caixa_titulo=(20, 40, 280, 150))
    depois = {k: mi.impressao(r['formatos'][k], mi.resolvido(b2, ctx['resolvidas'], {}), k) for k in ('v320', 'mesmo')}
    assert depois['v320'] != antes['v320']
    assert depois['mesmo'] == antes['mesmo']


def test_funcao_de_camada_fora_do_escopo_deixa_a_impressao_igual(base):
    """el20 (camada 20) foi apagado pelo DA na familia de mesmo (transform): mudar a funcao e a regra dela (mesma
    ancora) deixa mesmo igual e muda os formatos onde el20 esta, derivando tudo de novo."""
    imp, _r = base
    b = _briefing()
    _funcao(b, 20, 'informacao_de_evento')
    _regra(b, 'informacao_de_evento', 'contain')
    depois, r = _todas(b)
    assert r['formatos']['mesmo']['situacao'] == 'derivado'
    assert depois['mesmo'] == imp['mesmo']
    assert all(depois[k] != imp[k] for k in ('perto', 'vertical', 'alto'))


def test_apagado_na_familia_da_galeria_ainda_alimenta_os_outros_elementos():
    """Na galeria, a versao sai com todos os elementos e o apagado sai depois, com o encaixe refeito: a funcao dele
    muda a caixa dos outros, e a impressao cai junto (dependencia de verdade, pela derivacao)."""
    b = _briefing()
    b['composicoes'][2]['edicoes'] = [{'elemento': 'el20', 'acao': 'apagar'}]
    antes, r = _todas(b)
    assert 'el20' not in {e['id'] for e in r['formatos']['vertical']['elementos']}
    _funcao(b, 20, 'cta')
    _regra(b, 'cta', 'contain')
    depois, r2 = _todas(b)
    caixas = [{e['id']: e['caixa'] for e in x['formatos']['vertical']['elementos']} for x in (r, r2)]
    assert caixas[0] != caixas[1] and depois['vertical'] != antes['vertical']


def test_regra_e_ancora_de_funcao_sem_camada_no_formato_deixam_igual(base):
    imp, r = base
    b = _briefing()
    _regra(b, 'selo', 'contain')
    next(a for a in b['ancoras'] if a['funcao'] == 'selo')['x'] = ap.decisao('esquerda')
    assert {k: _fixa(b, fid=k, base=r) for k in imp} == imp
    assert mb.FUNCAO_FORA not in {e['funcao'] for d in r['formatos'].values() for e in d['elementos']}


def test_camada_que_vira_fora_da_peca_muda_a_impressao_de_todo_formato(base):
    """A lista "fora da peca" entra em toda derivacao: a camada que sai da peca (aqui a 20, apagada pelo DA em mesmo)
    muda mesmo tambem, com a derivacao gravada de antes (a derivacao gravada nao sabe da camada nova fora dela)."""
    imp, r = base
    b = _briefing()
    _funcao(b, 20, mb.FUNCAO_FORA)
    assert _fixa(b, base=r) != imp['mesmo']


def test_a_propria_impressao_gravada_fica_fora_da_conta(base):
    imp, r = base
    d = dict(r['formatos']['perto'], impressao_formato='f' * 64)
    ctx = nd.contexto(ap.laudo(), _briefing())
    assert mi.impressao(d, mi.resolvido(ctx['briefing'], ctx['resolvidas'], _specs()), 'perto') == imp['perto']
