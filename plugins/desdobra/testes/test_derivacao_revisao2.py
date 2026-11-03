# -*- coding: utf-8 -*-
"""Revisao 2 do M5 (scratchpad/m5/revisao2/achados.md) e as decisoes-v1.md 100 e 101, escritos antes do codigo.

A1 bloco partido na pilha; A2 ajuste global com tinta; A3 membro do bloco cortado; A4 e M1 influencia com clipping e
grupo; A5 texto clipado num membro; M2 faixa ambigua do fundo de cena; M3 preparo por prancheta; M4 cena opaca que
passa a cobrir conteudo; baixos B2 a B5; 100 regra por bloco e funcao de cada membro; 101 margem da mestre media.
Tudo pelo caminho real: a derivacao em memoria (mesma funcao que o derivar usa), o conferir e, para o render, um job
sintetico de verdade (PSD gerado na hora).
"""
import sys

import pytest

import test_derivacao_apoio as ap
from desdobra import limites
from desdobra.briefing import modelo as mb
from desdobra.derivacao import elementos as mel
from desdobra.derivacao import nucleo as nd
from desdobra.derivacao import validacao as mval
from test_derivacao_blocos import camada, cena, mascara


def _b(funcoes, formatos=None, regras_bloco=None, **k):
    b = ap.briefing(funcoes=funcoes, formatos=formatos or [ap.formato('f', 480, 300)],
                    ancoras={**ap.ANCORAS, 'imagem': ('direita', 'meio')}, **k)
    if regras_bloco:
        b['regras_bloco'] = [{'layer_id': lid, 'regra': ap.decisao(r)} for lid, r in sorted(regras_bloco.items())]
    return b


def _derivar(laudo, b, ident='f'):
    return nd.derivar_em_memoria(nd.contexto(laudo, b), specs={})['formatos'][ident]


def _mestre(laudo, b):
    res, _e, info = mb.resolver(laudo, b)
    return mel.montar(laudo, res, info['quadro'])


def _codigos(laudo, b):
    return sorted({e['codigo'] for e in mb.conferir(laudo, b)})


# ------------------------------------------------------------------ A1
def _pilha_partida(logo_entre=True, funcao_ajuste='imagem'):
    camadas = [camada(1, 'pixel', [0, 0, 400, 200]), camada(2, 'smart_embutido', [250, 40, 330, 190])]
    logo = camada(30, 'smart_embutido', [20, 150, 70, 190])
    if logo_entre:
        camadas.append(logo)
    camadas += [camada(5, 'ajuste', None, mascara=mascara([255, 60, 325, 170]), ajuste={'tipo': 'curves'}),
                camada(10, 'texto', [20, 20, 220, 60], corpo=40)]
    if not logo_entre:
        camadas.append(logo)
    funcoes = {1: 'fundo', 2: 'imagem', 30: 'logo_principal', 5: funcao_ajuste, 10: 'titulo'}
    return ap.laudo(400, 200, camadas), funcoes


@pytest.mark.parametrize('funcao_ajuste', ['imagem', 'ajuste_global'])
def test_a1_ajuste_do_bloco_separado_por_outro_elemento_devolve(funcao_ajuste):
    laudo, funcoes = _pilha_partida(True, funcao_ajuste)
    d = _derivar(laudo, _b(funcoes, regras_bloco={1: 'cover'}))
    assert d['situacao'] == 'devolvido' and d['devolucao']['motivo'] == 'bloco_partido_na_pilha', d['devolucao']
    partidos = d['devolucao']['medidas']['blocos']
    assert partidos and partidos[0]['separadores'] == [30] and partidos[0]['efeitos'] == [5]


def test_a1_bloco_inteiro_na_pilha_deriva():
    laudo, funcoes = _pilha_partida(False)
    d = _derivar(laudo, _b(funcoes, regras_bloco={1: 'cover'}))
    assert d['situacao'] == 'derivado', d['devolucao']
    assert any({1, 2, 5} <= set(e['layer_ids']) for e in d['elementos'])


# ------------------------------------------------------------------ A2
@pytest.mark.parametrize('caixa', [[0, 0, 400, 200], [200, 0, 400, 200]])
def test_a2_ajuste_global_com_tinta_sobre_conteudo_devolve_sem_elemento_solto(caixa):
    camadas = [camada(1, 'pixel', [0, 0, 400, 200]), camada(2, 'smart_embutido', [250, 40, 330, 190]),
               camada(10, 'texto', [20, 20, 220, 60], corpo=40), camada(30, 'smart_embutido', [340, 150, 390, 190]),
               camada(90, 'cor_solida', caixa, mascara=mascara(caixa), blend='MULTIPLY')]
    funcoes = {1: 'fundo', 2: 'imagem', 10: 'titulo', 30: 'logo_principal', 90: 'ajuste_global'}
    laudo = ap.laudo(400, 200, camadas)
    b = _b(funcoes, regras_bloco={1: 'cover'})
    m = _mestre(laudo, b)
    assert not any(e['classe'] == 'global' for e in m['elementos'])
    assert m['ajuste_global_sobre_conteudo'] == [90]
    assert 'ancora_faltando' not in _codigos(laudo, b)
    d = _derivar(laudo, b)
    assert d['devolucao']['motivo'] == 'ajuste_global_sem_aplicar', d['devolucao']


def test_a2_ajuste_global_com_tinta_so_sobre_a_cena_entra_no_bloco():
    camadas = [camada(1, 'pixel', [0, 0, 400, 200]), camada(2, 'smart_embutido', [250, 40, 330, 190]),
               camada(90, 'cor_solida', [200, 0, 400, 200], mascara=mascara([200, 0, 400, 200]), blend='MULTIPLY'),
               camada(10, 'texto', [20, 20, 220, 60], corpo=40), camada(30, 'smart_embutido', [340, 150, 390, 190])]
    funcoes = {1: 'fundo', 2: 'imagem', 10: 'titulo', 30: 'logo_principal', 90: 'ajuste_global'}
    laudo = ap.laudo(400, 200, camadas)
    d = _derivar(laudo, _b(funcoes, regras_bloco={1: 'cover'}))
    assert d['situacao'] == 'derivado', d['devolucao']
    assert any(90 in e['layer_ids'] and 2 in e['layer_ids'] for e in d['elementos'])


def test_a2_render_nao_tem_mais_o_bloqueio_morto_do_ajuste_global():
    from desdobra.render import derivado
    assert 'ajuste_global_sem_aplicar_no_formato' not in derivado.DESCRICOES


# ------------------------------------------------------------------ A3
@pytest.mark.parametrize('dims', [(760, 240), (800, 250), (300, 250), (600, 240)])
def test_a3_membro_inteiro_no_canvas_nao_sai_cortado(dims):
    laudo, funcoes = cena()
    W, H = dims
    d = _derivar(laudo, _b(funcoes, formatos=[ap.formato('f', W, H)], regras_bloco={1: 'cover'},
                           familias={'faixa': ap.decisao(4.0)}))
    if d['situacao'] == 'devolvido':
        r = d['devolucao']['restricao'] or {}
        assert d['devolucao']['motivo'] == 'restricao_obrigatoria_nao_fecha', d['devolucao']
        assert r['nome'].startswith('membro_dentro') and r.get('fonte'), r
        return
    bl = next(e for e in d['elementos'] if 2 in e['layer_ids'])
    tr = bl['transformacao']
    s, (ox, oy), (dx, dy) = tr['s'], tr['origem_doc'], tr['destino']
    g = [250, 40, 330, 190]
    gg = [s * (g[0] - ox) + dx, s * (g[1] - oy) + dy, s * (g[2] - ox) + dx, s * (g[3] - oy) + dy]
    tol = limites.valor('derivacao.enquadramento_tolerancia_px')
    assert gg[0] >= -tol and gg[1] >= -tol and gg[2] <= W + tol and gg[3] <= H + tol, gg
    assert any(v['nome'] == 'membro_dentro_do_canvas' for v in d['validacoes'])


# ------------------------------------------------------------------ A4 e M1
@pytest.mark.parametrize('f5', ['imagem', 'ajuste_global'])
def test_a4_ajuste_clipado_so_atua_na_base_do_clip(f5):
    camadas = [camada(1, 'pixel', [0, 0, 400, 200]), camada(2, 'pixel', [10, 10, 60, 60]),
               camada(30, 'smart_embutido', [20, 150, 70, 190]), camada(3, 'pixel', [300, 60, 380, 180]),
               camada(5, 'ajuste', None, ajuste={'tipo': 'curves'}), camada(10, 'texto', [70, 20, 290, 60], corpo=40)]
    camadas[4]['aparencia']['clipping'] = True
    funcoes = {1: 'fundo', 2: 'grafismo', 30: 'logo_principal', 3: 'imagem', 5: f5, 10: 'titulo'}
    laudo = ap.laudo(400, 200, camadas)
    m = _mestre(laudo, _b(funcoes))
    el3 = next(e for e in m['elementos'] if 3 in e['layer_ids'])
    assert set(el3['layer_ids']) == {3, 5}
    assert m['ajuste_global_sobre_conteudo'] == [] and m['sem_bloco'] == []
    assert _derivar(laudo, _b(funcoes))['situacao'] == 'derivado'


def _grupo(blend_grupo):
    camadas = [camada(1, 'pixel', [0, 0, 400, 200]), camada(2, 'pixel', [100, 60, 200, 160]),
               camada(40, 'grupo', [300, 60, 380, 180], blend=blend_grupo),
               camada(41, 'pixel', [300, 60, 380, 180], pais=(40,)),
               camada(42, 'ajuste', None, ajuste={'tipo': 'curves'}, pais=(40,)),
               camada(10, 'texto', [20, 20, 220, 50], corpo=30), camada(30, 'smart_embutido', [20, 150, 70, 190])]
    return ap.laudo(400, 200, camadas), {1: 'fundo', 2: 'imagem', 40: 'imagem', 10: 'titulo', 30: 'logo_principal'}


def test_m1_ajuste_em_grupo_em_passagem_atua_no_que_esta_embaixo_do_grupo():
    laudo, funcoes = _grupo('PASS_THROUGH')
    m = _mestre(laudo, _b(funcoes))
    el = next(e for e in m['elementos'] if 41 in e['layer_ids'])
    assert {1, 2, 41, 42} <= set(el['layer_ids'])


def test_m1_ajuste_em_grupo_isolado_fica_no_grupo():
    laudo, funcoes = _grupo('NORMAL')
    m = _mestre(laudo, _b(funcoes))
    el = next(e for e in m['elementos'] if 41 in e['layer_ids'])
    assert set(el['layer_ids']) == {41, 42}


# ------------------------------------------------------------------ A5
def test_a5_texto_clipado_num_membro_anda_e_e_validado_com_o_bloco():
    # o texto fica logo acima da imagem 2 (a base do clip) e a imagem 3 se sobrepoe a 2: bloco [2, 3] com o texto
    camadas = [camada(1, 'pixel', [0, 0, 400, 200]), camada(3, 'pixel', [300, 60, 380, 180]),
               camada(2, 'pixel', [10, 10, 390, 120]), camada(10, 'texto', [20, 20, 220, 60], corpo=40),
               camada(30, 'smart_embutido', [20, 150, 70, 190])]
    camadas[3]['aparencia']['clipping'] = True
    funcoes = {1: 'fundo', 2: 'imagem', 3: 'imagem', 10: 'titulo', 30: 'logo_principal'}
    laudo = ap.laudo(400, 200, camadas)
    b = _b(funcoes, formatos=[ap.formato('f', 760, 240)], regras_bloco={2: 'contain'}, familias={'faixa': ap.decisao(4.0)})
    m = _mestre(laudo, b)
    bloco = next(e for e in m['elementos'] if 2 in e['layer_ids'])
    assert 10 in bloco['layer_ids'] and not any(e['id'] == 'el10' for e in m['elementos'])
    d = _derivar(laudo, b)
    if d['situacao'] == 'derivado':
        nomes = [v['nome'] for v in d['validacoes'] if 'el2' in v['elementos']]
        assert 'membro_dentro_da_area_segura' in nomes or 'membro_dentro_do_canvas' in nomes
    else:
        assert (d['devolucao']['restricao'] or {}).get('nome', '').startswith('membro_dentro'), d['devolucao']


# ------------------------------------------------------------------ M2
def test_m2_fundo_na_faixa_ambigua_registra_e_avisa():
    camadas = [camada(1, 'pixel', [0, 0, 400, 189]), camada(2, 'pixel', [10, 10, 60, 60]),
               camada(3, 'pixel', [330, 120, 390, 180]), camada(10, 'texto', [70, 20, 300, 60], corpo=40),
               camada(30, 'smart_embutido', [20, 150, 70, 190])]
    funcoes = {1: 'fundo', 2: 'grafismo', 3: 'imagem', 10: 'titulo', 30: 'logo_principal'}
    laudo = ap.laudo(400, 200, camadas)
    b = _b(funcoes, regras_bloco={1: 'cover'})
    m = _mestre(laudo, b)
    assert [x['elemento'] for x in m['fundo_ambiguo']] == ['el1']
    d = _derivar(laudo, b)
    assert any(v['nome'] == 'fundo_de_cena_ambiguo' and v['situacao'] == 'avisa' for v in d['validacoes'])
    lim = limites.obter('derivacao.bloco_fundo_faixa_ambigua')
    assert lim.fonte and lim.situacao == 'a_calibrar'


# ------------------------------------------------------------------ M3
def test_m3_preparo_mede_por_prancheta():
    from desdobra.laudo import preparo

    def tela(dx, k):
        return [camada(k, 'pixel', [dx, 0, dx + 400, 200]), camada(k + 1, 'smart_embutido', [dx + 20, 150, dx + 70, 190]),
                camada(k + 2, 'smart_embutido', [dx + 300, 20, dx + 380, 60]),
                camada(k + 3, 'texto', [dx + 20, 20, dx + 220, 60], corpo=40)]
    camadas = tela(0, 1) + tela(400, 11) + tela(800, 21)
    for k, c in enumerate(camadas):
        c['quadro'] = 'q%d' % (k // 4)
    tres = ap.laudo(1200, 200, camadas, quadros=[{'id': 'q%d' % k, 'regra': 'pranchetas',
                                                   'caixa': [400 * k, 0, 400 * k + 400, 200]} for k in range(3)])
    c = preparo.contar(tres)
    assert c['aglomerados_sobrepostos'] == 0 and preparo.recomendacao(c) is None


# ------------------------------------------------------------------ M4
def test_m4_cena_opaca_acima_do_texto_que_passa_a_cobrir_reprova():
    sg = {'esq': False, 'topo': False, 'dir': False, 'base': False}
    els = [{'id': 'el1', 'funcao': 'titulo', 'regra': 'raiz_area', 'classe': 'texto', 'sangra': sg, 'z': [1, 1],
            'opaco': True},
           {'id': 'el2', 'funcao': 'grafismo', 'regra': 'contain', 'classe': 'base', 'sangra': sg, 'z': [2, 2],
            'opaco': True}]
    kv = {'el1': {'caixa': [0, 0, 10, 10], 'classe': 'texto', 'z': [1, 1]},
          'el2': {'caixa': [20, 0, 30, 10], 'classe': 'base', 'z': [2, 2]}}
    esperado = {'el1': ('titulo', 'raiz_area'), 'el2': ('grafismo', 'contain')}
    val = mval.validar((100, 100), {}, els, [[0, 0, 10, 10], [5, 0, 15, 10]], [1.0, 1.0], kv, esperado)
    v = next(x for x in val if x['nome'] == 'cena_cobre_conteudo')
    assert v['situacao'] == 'reprova' and v['medidas']['pares'] == [['el2', 'el1']]
    # a mesma cena embaixo do texto nao reprova
    els[1]['z'] = kv['el2']['z'] = [0, 0]
    val = mval.validar((100, 100), {}, els, [[0, 0, 10, 10], [5, 0, 15, 10]], [1.0, 1.0], kv, esperado)
    assert next(x for x in val if x['nome'] == 'cena_cobre_conteudo')['situacao'] == 'ok'
    lim = limites.obter('derivacao.cobertura_nova_cena_sobre_conteudo_max')
    assert lim.fonte and lim.situacao == 'a_calibrar'


# ------------------------------------------------------------------ baixos
def test_b2_origem_da_funcao_e_a_do_maior_membro():
    # a camada de menor id do bloco tem a funcao pelo grupo; o maior membro (o fundo) tem a funcao na propria camada
    camadas = [camada(50, 'pixel', [0, 0, 400, 200]), camada(0, 'grupo', [250, 40, 330, 190]),
               camada(2, 'smart_embutido', [250, 40, 330, 190], pais=(0,)),
               camada(4, 'smart_embutido', [200, 0, 400, 120], blend='SCREEN'),
               camada(10, 'texto', [20, 20, 220, 60], corpo=40)]
    laudo = ap.laudo(400, 200, camadas)
    d = _derivar(laudo, _b({50: 'fundo', 0: 'imagem', 4: 'imagem', 10: 'titulo'}, regras_bloco={50: 'cover'}))
    assert d['situacao'] == 'derivado', d['devolucao']
    bl = next(e for e in d['elementos'] if 50 in e['layer_ids'])
    assert bl['layer_ids'][0] == 2 and bl['raiz'] == 50 and bl['origem_funcao'] == 'camada'


def test_b3_desempate_do_maior_membro_pela_ordem_da_pilha():
    # luz em tela e fundo com a mesma area: vale o de baixo na pilha (o fundo), qualquer que seja o id
    camadas = [camada(9, 'pixel', [0, 0, 400, 200]), camada(1, 'pixel', [0, 0, 400, 200], blend='SCREEN'),
               camada(10, 'texto', [20, 20, 220, 60], corpo=40)]
    laudo = ap.laudo(400, 200, camadas)
    m = _mestre(laudo, _b({9: 'fundo', 1: 'imagem', 10: 'titulo'}))
    bl = next(e for e in m['elementos'] if 9 in e['layer_ids'])
    assert bl['raiz'] == 9 and bl['funcao'] == 'fundo'


def test_b4_indeterminado_com_tinta_conta_como_conteudo_na_colisao():
    sg = {'esq': False, 'topo': False, 'dir': False, 'base': False}
    els = [{'id': 'el1', 'funcao': 'indeterminado', 'regra': 'x', 'classe': 'indeterminado', 'sangra': sg},
           {'id': 'el2', 'funcao': 'titulo', 'regra': 'x', 'classe': 'texto', 'sangra': sg}]
    kv = {'el1': {'caixa': [0, 0, 10, 10]}, 'el2': {'caixa': [20, 0, 30, 10]}}
    val = mval.validar((100, 100), {}, els, [[0, 0, 25, 10], [20, 0, 30, 10]], [1.0, 1.0], kv,
                       {'el1': ('indeterminado', 'x'), 'el2': ('titulo', 'x')})
    assert next(v for v in val if v['nome'] == 'colisao_nova_contra_a_origem')['situacao'] == 'reprova'


def test_b5_corpo_do_texto_legal_abaixo_do_minimo_avisa():
    sg = {'esq': False, 'topo': False, 'dir': False, 'base': False}
    els = [{'id': 'el40', 'funcao': 'texto_legal', 'regra': 'constante', 'classe': 'texto', 'sangra': sg,
            'corpo_px': 8.0}]
    kv = {'el40': {'caixa': [0, 0, 50, 8]}}
    minimo = limites.valor('derivacao.corpo_minimo_legal_px')
    val = mval.validar((100, 100), {}, els, [[0, 0, 25, 4]], [0.5], kv, {'el40': ('texto_legal', 'constante')})
    v = next(x for x in val if x['nome'] == 'corpo_minimo_do_legal')
    assert (v['situacao'] == 'avisa') == (8.0 * 0.5 < minimo)
    assert limites.obter('derivacao.corpo_minimo_legal_px').situacao == 'a_calibrar'


def test_colisao_nova_reprova_texto_contra_texto():
    sg = {'esq': False, 'topo': False, 'dir': False, 'base': False}
    els = [{'id': 'el1', 'funcao': 'titulo', 'regra': 'x', 'classe': 'texto', 'sangra': sg},
           {'id': 'el2', 'funcao': 'texto_legal', 'regra': 'x', 'classe': 'texto', 'sangra': sg}]
    kv = {'el1': {'caixa': [0, 0, 10, 10]}, 'el2': {'caixa': [20, 0, 30, 10]}}
    val = mval.validar((100, 100), {}, els, [[0, 0, 25, 10], [20, 0, 30, 10]], [1.0, 1.0], kv,
                       {'el1': ('titulo', 'x'), 'el2': ('texto_legal', 'x')})
    assert next(v for v in val if v['nome'] == 'colisao_nova_contra_a_origem')['situacao'] == 'reprova'


# ------------------------------------------------------------------ mutacao: ajuste trocado para texto
def test_ajuste_do_bloco_trocado_para_texto_nao_vai_a_fora_do_canvas():
    laudo, funcoes = cena()
    m = _mestre(laudo, _b({**funcoes, 5: 'cta'}))
    assert 5 not in m['fora_do_canvas']
    assert any(5 in e['layer_ids'] and 2 in e['layer_ids'] for e in m['elementos'])


# ------------------------------------------------------------------ 100
def test_100_bloco_com_regras_diferentes_e_recusado_no_conferir():
    laudo, funcoes = cena()
    b = _b(funcoes)
    erros = [e for e in mb.conferir(laudo, b) if e['codigo'] == 'bloco_com_regras_diferentes']
    assert len(erros) == 1
    assert set(erros[0]['medidas']['camadas']) == {1, 2, 3, 4, 5}
    assert erros[0]['medidas']['regras'] == ['contain', 'cover']
    d = _derivar(laudo, b)
    assert d['devolucao']['motivo'] == 'bloco_com_regras_diferentes'


def test_100_regra_do_bloco_vale_para_o_bloco():
    laudo, funcoes = cena()
    b = _b(funcoes, regras_bloco={3: 'contain'})
    assert 'bloco_com_regras_diferentes' not in _codigos(laudo, b)
    d = _derivar(laudo, b)
    bl = next(e for e in d['elementos'] if 1 in e['layer_ids'])
    assert bl['regra'] == 'contain'
    b2 = _b(funcoes, regras_bloco={3: 'contain', 4: 'cover'})
    assert 'regra_de_bloco_conflitante' in _codigos(laudo, b2)
    b3 = _b(funcoes, regras_bloco={1: 'cover', 10: 'cover'})
    assert 'regra_de_bloco_sem_bloco' in _codigos(laudo, b3)


def test_100_validacao_confere_a_funcao_de_cada_membro():
    laudo, funcoes = cena()
    b = _b(funcoes, regras_bloco={1: 'cover'})
    d0 = _derivar(laudo, b)
    v0 = next(v for v in d0['validacoes'] if v['nome'] == 'regra_por_funcao' and 'el1' in v['elementos'])
    b2 = _b({**funcoes, 3: 'grafismo'}, regras_bloco={1: 'cover'})
    d1 = _derivar(laudo, b2)
    v1 = next(v for v in d1['validacoes'] if v['nome'] == 'regra_por_funcao' and 'el1' in v['elementos'])
    assert v0['medidas']['funcoes_membros'] != v1['medidas']['funcoes_membros']
    assert [3, 'grafismo'] in v1['medidas']['funcoes_membros']
    # o layout com a funcao de um membro diferente da do briefing relido reprova
    ctx = nd.contexto(laudo, b)
    kv = nd.mestre_do_kv(ctx)
    esp = nd.esperado_do_briefing(laudo, b2, kv['elementos'])
    bl = next(e for e in kv['elementos'] if e['id'] == 'el1')
    val = mval.validar((400, 200), {}, [bl], [bl['caixa']], [1.0], {'el1': bl}, esp)
    assert next(v for v in val if v['nome'] == 'regra_por_funcao')['situacao'] == 'reprova'


# ------------------------------------------------------------------ 101
def test_101_margem_da_mestre_e_media():
    laudo, funcoes = cena()
    d = _derivar(laudo, _b(funcoes, regras_bloco={1: 'cover'}))
    forcas = {x['forca'] for x in d['restricoes'] if x['nome'].startswith('margem_da_mestre')}
    assert forcas == {'media'}
    assert {x['forca'] for x in d['restricoes'] if x['nome'].startswith('margem_minima')} == {'obrigatoria'}


# ------------------------------------------------------------------ render: job sintetico com mesclagem
def _psd_partido(destino):
    """PSD 320 x 160: fundo creme, imagem azul, logo verde, luz em tela sobre a imagem (acima do logo na pilha)."""
    from PIL import Image
    from psd_tools import PSDImage
    from psd_tools.constants import BlendMode

    import test_render_apoio as rap
    p = PSDImage.new('RGB', (320, 160), color=(255, 255, 255))
    p.create_pixel_layer(Image.new('RGBA', (320, 160), (240, 236, 220, 255)), name='fundo-sintetico')
    p.create_pixel_layer(Image.new('RGBA', (100, 100), (20, 40, 160, 255)), name='imagem-sintetica', top=30, left=190)
    p.create_pixel_layer(Image.new('RGBA', (40, 40), (0, 120, 60, 255)), name='logo-sintetico', top=110, left=10)
    luz = p.create_pixel_layer(Image.new('RGBA', (90, 60), (200, 200, 200, 255)), name='luz-sintetica', top=40, left=195)
    luz.blend_mode = BlendMode.SCREEN
    return rap._salvar(p, destino)


@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
def test_a1_render_de_bloco_partido_por_outro_elemento_nao_compoe_pedaco_sozinho(tmp_path, python):
    import json as _json

    import test_derivacao_job as tj
    import test_fontes_apoio as fap
    import test_render_apoio as rap
    from desdobra import contratos
    from desdobra.job import nucleo
    from desdobra.render import derivado as mder
    fontes = tmp_path / 'origem-fontes'
    fap.gravar(fontes, 'inventada.ttf', fap.fonte(ps=rap.FONTE))
    job = tmp_path / 'job'
    nucleo.criar(job, _psd_partido(tmp_path / 'origem' / 'kv.psd'), 'c', fontes=[fontes])
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    ids = {c['nome']: c['identidade']['layer_id'] for c in laudo['camadas']}
    funcoes = {ids['fundo-sintetico']: 'fundo', ids['imagem-sintetica']: 'imagem', ids['logo-sintetico']: 'logo_principal',
               ids['luz-sintetica']: 'imagem'}
    b = _b(funcoes, formatos=[ap.formato('perto', 400, 240)], regras_bloco={ids['fundo-sintetico']: 'cover'})
    b.pop('cabecalho')
    b.pop('job_id')
    arq = tmp_path / 'fixture.json'
    arq.write_text(_json.dumps(b), encoding='utf-8')
    cod, env = tj._cli(python, 'briefing', 'importar', str(arq), '--teste', '--job', str(job))
    assert cod == 0, env
    cod, env = tj._cli(python, 'derivar', '--job', str(job))
    contrato, bloqueios, confirmar = mder.montar(job, 'perto')
    assert contrato is None and [x['codigo'] for x in bloqueios] == ['formato_devolvido']
    assert bloqueios[0]['medidas']['motivo'] == 'bloco_partido_na_pilha'


def test_texto_clipado_fora_da_base_sai_do_formato_e_nao_entra_no_bloco():
    """Achado ao rodar de novo o e8 com o clipping no laudo (escrito depois da correcao): o texto clipado numa base que
    ele nao toca nao tem tinta visivel; ia para fora_do_canvas e tambem para o bloco da base."""
    camadas = [camada(1, 'pixel', [0, 0, 400, 200]), camada(2, 'pixel', [10, 10, 390, 120]),
               camada(3, 'pixel', [300, 60, 380, 180]), camada(10, 'texto', [20, 20, 220, 60], corpo=40),
               camada(30, 'smart_embutido', [20, 150, 70, 190])]
    camadas[3]['aparencia']['clipping'] = True
    laudo = ap.laudo(400, 200, camadas)
    m = _mestre(laudo, _b({1: 'fundo', 2: 'imagem', 3: 'imagem', 10: 'titulo', 30: 'logo_principal'}))
    assert m['fora_do_canvas'] == [10]
    assert not any(10 in e['layer_ids'] for e in m['elementos'])
