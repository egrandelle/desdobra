# -*- coding: utf-8 -*-
"""A escada do menor ajuste da familia (decisao 199, 3; etapa E2): F1 anda o bloco dentro da sobra, F2 recua a forma
na normal da borda sem perder a sangria nem tirar conteudo de dentro dela, F3 diminui o bloco em volta da ancora ate
derivacao.familia_ajuste_escala_min e nunca abaixo do piso da 133. Vence o menor custo; no empate, F1, F2, F3.

So geometria sintetica (familia_geometria), nenhum PSD e nenhum job.
"""
import json

import pytest

import familia_geometria as G
from desdobra import limites
from desdobra.derivacao import familia as F


def _rampa(x1_asset=1130.0, selo_folga=25.0, yL=1500.0, yR=1400.0):
    """Azul em cima, com a borda em rampa de (0, yL) a (1080, yR); o selo no azul, encostado na borda na ponta
    direita (o azul anda com ele, preso a direita); o titulo e a assinatura centrados, a assinatura no branco."""
    def y(x):
        return yL + (yR - yL) * x / 1080.0
    asset = [-50.0, -50.0, x1_asset, max(y(-50.0), y(x1_asset))]
    pontos = [(-50.0, -50.0), (x1_asset, -50.0), (x1_asset, y(x1_asset)), (-50.0, y(-50.0))]
    ref = {'id': 'f1080x1920', 'W': 1080.0, 'H': 1920.0, 'quadros': G.quadros(1080.0, 1920.0)}
    yb = y(1025.0) - selo_folga
    els = [
        {'id': 'fundo', 'classe': 'base', 'funcao': 'fundo', 'caixa': [0.0, 0.0, 1080.0, 1920.0],
         'sangra': dict(G.TODOS)},
        {'id': 'azul', 'classe': 'base', 'funcao': 'grafismo', 'caixa': [0.0, 0.0, 1080.0, max(y(0.0), y(1080.0))],
         'caixa_asset': asset, 'sangra': {'esq': True, 'topo': True, 'dir': True}},
        {'id': 'titulo', 'classe': 'texto', 'funcao': 'titulo', 'caixa': [100.0, 150.0, 980.0, 400.0]},
        {'id': 'selo', 'classe': 'texto', 'funcao': 'texto_de_apoio', 'caixa': [700.0, yb - 180.0, 1025.0, yb]},
        {'id': 'assinatura', 'classe': 'marca', 'funcao': 'assinatura_institucional',
         'caixa': [340.0, 1560.0, 740.0, 1680.0]},
    ]
    return F.extrair_modelo(ref, els, silhuetas={'azul': {'poligono': G.em_fracao(pontos, asset)}})


# o arquivo com a area segura da folha 10% acima da base: a margem dele e mais baixa, a escala sai da altura, e a sobra
# fica na largura. O selo (preso a direita) leva o azul; a assinatura, no centro, anda a metade: perde folga
MEMBRO_AS = G.membro('f1080x1920as', 1080, 1920, area_segura=[0.0, 0.0, 1080.0, 1728.0])
LIVRE = 'livre_da_tinta:assinatura:azul'


def _tipos(lay):
    return [a['tipo'] for a in lay['ajustes'] if a['codigo'] == 'ajuste_da_familia']


def _sangra(lay, modelo, k):
    a = lay['caixas_asset'][k]
    sg = modelo['elementos'][k]['sangra']
    return all(not sg[lado] or ok for lado, ok in (('esq', a[0] <= 1e-9), ('topo', a[1] <= 1e-9),
                                                   ('dir', a[2] >= lay['W'] - 1e-9),
                                                   ('base', a[3] >= lay['H'] - 1e-9)))


def test_area_segura_de_10_por_cento_f2_recua_a_forma_e_a_escala_da_assinatura_nao_muda():
    m = _rampa()
    tr = F.transferir(m, MEMBRO_AS)
    assert [r['id'] for r in F.relacoes_furadas(m, tr)] == [LIVRE]
    lay = F.ajustar_minimo(m, tr)
    assert _tipos(lay) == ['F2'] and lay['situacao'] == 'ajustado'
    aj = lay['ajustes'][0]
    assert aj['elemento'] == 'azul' and aj['relacao'] == LIVRE
    assert aj['frase'] == 'A forma recuou %s px para a assinatura continuar fora dela.' % F._px(aj['px'])
    # a escala da assinatura nao muda: a do resto da familia
    a = lay['caixas']['assinatura']
    assert lay['fatores']['assinatura'] == 1.0 and (a[2] - a[0]) == pytest.approx(400.0 * lay['s'], abs=1e-9)
    # o menor recuo: a folga volta exatamente a do aprovado vezes s, sem perder a sangria nem tirar o selo do azul
    rel = {r['id']: r for r in F.relacoes(m, lay)}
    assert rel[LIVRE]['ok'] and rel[LIVRE]['medida'] == pytest.approx(rel[LIVRE]['alvo'], abs=1e-6)
    assert rel['dentro_da_tinta:selo:azul']['ok'] and _sangra(lay, m, 'azul')
    assert lay['relacoes_quebradas'] == []


def test_f2_nunca_tira_a_sangria():
    """O asset do azul acaba na borda direita do canvas: recuar para a esquerda mostraria a borda dele. F2 fica de
    fora e vence o proximo menor ajuste."""
    m = _rampa(x1_asset=1080.0)
    lay = F.ajustar_minimo(m, F.transferir(m, MEMBRO_AS))
    assert 'F2' not in _tipos(lay) and _tipos(lay) == ['F3']
    assert _sangra(lay, m, 'azul') and lay['situacao'] == 'ajustado' and F.relacoes_furadas(m, lay) == []
    aj = lay['ajustes'][0]
    assert limites.valor('derivacao.familia_ajuste_escala_min') <= aj['fator'] < 1.0
    assert aj['frase'] == 'A assinatura ficou %s%% menor para ficar fora da forma.' % F._px((1.0 - aj['fator']) * 100)


def test_f2_nunca_tira_o_texto_do_azul():
    """O selo esta 2 px dentro da borda do azul: o recuo que a assinatura pede o tiraria do azul."""
    m = _rampa(selo_folga=2.0)
    lay = F.ajustar_minimo(m, F.transferir(m, MEMBRO_AS))
    assert 'F2' not in _tipos(lay)
    rel = {r['id']: r for r in F.relacoes(m, lay)}
    assert rel['dentro_da_tinta:selo:azul']['ok'] and rel['dentro_da_tinta:titulo:azul']['ok'] and rel[LIVRE]['ok']


def test_f1_anda_o_bloco_quando_f2_e_f3_nao_podem():
    """Sem reserva para recuar o azul e com o piso da 133 da assinatura em 100%, sobra andar dentro da sobra."""
    m = _rampa(x1_asset=1080.0)
    tr = F.transferir(m, MEMBRO_AS)
    lay = F.ajustar_minimo(m, tr, pisos={'assinatura': 1.0})
    assert _tipos(lay) == ['F1'] and F.relacoes_furadas(m, lay) == []
    aj = lay['ajustes'][0]
    bloco = tr['blocos']['x'][tr['bloco_do_elemento']['x']['assinatura']]
    # o titulo divide o centro com a assinatura e anda junto; o bloco fica dentro da sobra
    assert bloco['elementos'] == ['titulo', 'assinatura'] and aj['eixo'] == 'x' and aj['px'] > 0
    assert bloco['faixa'][0] - 1e-9 <= bloco['delta'] + aj['px'] <= bloco['faixa'][1] + 1e-9
    assert lay['caixas']['titulo'][0] - tr['caixas']['titulo'][0] == pytest.approx(aj['px'], abs=1e-9)
    assert aj['frase'] == 'A assinatura andou %s px para ficar fora da forma.' % F._px(aj['px'])


def test_sem_saida_acima_do_piso_pede_ajuste_com_o_valor():
    """A faixa branca sangra dos dois lados e cresce para continuar sangrando no 1080x1600: a borda de baixo dela
    desce sobre o legal. Andar nao serve (a escala sai da altura, sem sobra nela), recuar a faixa encosta no texto de
    cima, e diminuir o legal ate o piso nao basta."""
    m = _faixa(com_legal=True)
    membro = G.membro('f1080x1600', 1080, 1600)
    lay = F.ajustar_minimo(m, F.transferir(m, membro))
    assert lay['situacao'] == 'pede_ajuste' and _tipos(lay) == []
    q = lay['relacoes_quebradas']
    assert [x['relacao'] for x in q] == ['livre_da_tinta:legal:faixa']
    assert q[0]['valor_px'] > 10.0
    assert q[0]['frase'] == 'O legal pede ajuste neste arquivo: faltam %s px para ficar fora da forma.' % \
        F._px(q[0]['valor_px'])
    # abaixo do piso, diminuir resolveria: a escada respeita o piso do registro
    abaixo = F.ajustar_minimo(m, F.transferir(m, membro), escala_min=0.5)
    piso = limites.valor('derivacao.familia_ajuste_escala_min')
    assert _tipos(abaixo) == ['F3'] and abaixo['ajustes'][0]['fator'] < piso
    # e o piso da 133 do elemento vale sobre o da escada
    com_piso = F.ajustar_minimo(m, F.transferir(m, membro), escala_min=0.5, pisos={'legal': 0.9})
    assert com_piso['situacao'] == 'pede_ajuste'


def _faixa(com_legal=False):
    from test_familia_transferencia import _faixa_branca
    return _faixa_branca(com_legal=com_legal)


def test_escolher_menor_custo_e_no_empate_f1_f2_f3():
    c = [{'tipo': 'F3', 'custo': 0.01}, {'tipo': 'F2', 'custo': 0.01}, {'tipo': 'F1', 'custo': 0.01}]
    assert F.escolher(c)['tipo'] == 'F1'
    assert F.escolher(c[:2])['tipo'] == 'F2'
    assert F.escolher([{'tipo': 'F1', 'custo': 0.02}, {'tipo': 'F3', 'custo': 0.019}])['tipo'] == 'F3'
    # o empate e ao arredondamento da conta, nao ao ultimo bit
    assert F.escolher([{'tipo': 'F2', 'custo': 0.01 + 1e-13}, {'tipo': 'F1', 'custo': 0.01}])['tipo'] == 'F1'
    assert F.escolher([]) is None


def test_escada_deterministica():
    m = _rampa()
    um = json.dumps(F.ajustar_minimo(m, F.transferir(m, MEMBRO_AS)), sort_keys=True)
    dois = json.dumps(F.ajustar_minimo(_rampa(), F.transferir(_rampa(), MEMBRO_AS)), sort_keys=True)
    assert um == dois


def test_ajuste_nunca_quebra_relacao_nova():
    for kw in ({}, {'x1_asset': 1080.0}, {'selo_folga': 2.0}, {'yL': 1530.0, 'yR': 1200.0}):
        m = _rampa(**kw)
        tr = F.transferir(m, MEMBRO_AS)
        antes = {r['id'] for r in F.relacoes_furadas(m, tr)}
        lay = F.ajustar_minimo(m, tr)
        depois = {r['id'] for r in F.relacoes_furadas(m, lay)}
        assert depois <= antes, kw


def test_frases_para_o_da():
    frases = []
    for kw in ({}, {'x1_asset': 1080.0}):
        m = _rampa(**kw)
        lay = F.ajustar_minimo(m, F.transferir(m, MEMBRO_AS))
        frases += [a['frase'] for a in lay['ajustes']]
    m = _faixa(com_legal=True)
    for membro in (G.membro('f300x600', 300, 600), G.membro('f1080x1600', 1080, 1600)):
        lay = F.ajustar_minimo(m, F.transferir(m, membro))
        frases += [a['frase'] for a in lay['ajustes']] + [q['frase'] for q in lay['relacoes_quebradas']]
    assert len(frases) >= 4
    for f in frases:
        assert '—' not in f and '–' not in f and ' - ' not in f, f
        assert f[0].isupper() and f.endswith('.'), f
        assert 'não é' not in f, f


def test_limites_novos_tem_fonte_e_ficam_a_calibrar():
    lim = limites.obter('derivacao.familia_ajuste_escala_min')
    assert lim.situacao == 'a_calibrar' and lim.efeito_efetivo == 'registra' and lim.valor == 0.85
    assert lim.fonte['arquivo'] == 'decisoes-v1.md' and '199' in lim.fonte['secao']
    cel = limites.obter('ds.silhueta_celulas')
    assert cel.situacao == 'a_calibrar' and cel.efeito_efetivo == 'registra' and cel.valor > 0
    # o piso da escada nunca fica abaixo do piso da 133
    assert lim.valor >= limites.valor('derivacao.escala_conteudo_min_da_regra')


def _duas_rampas():
    """Duas formas em rampa sobre a assinatura (revisao da 0.10.0): cada uma pede um F3 no mesmo bloco, em voltas
    seguidas da escada."""
    def rampa(yL, yR, x1=1080.0):
        def y(x):
            return yL + (yR - yL) * x / 1080.0
        asset = [-50.0, -50.0, x1, max(y(-50.0), y(x1))]
        pts = [(-50.0, -50.0), (x1, -50.0), (x1, y(x1)), (-50.0, y(-50.0))]
        return asset, {'poligono': G.em_fracao(pts, asset)}
    ref = {'id': 'f1080x1920', 'W': 1080.0, 'H': 1920.0, 'quadros': G.quadros(1080.0, 1920.0)}
    a_az, s_az = rampa(1480.0, 1440.0)
    a_ve, s_ve = rampa(1550.0, 1450.0)
    yb = 1480.0 + (1440.0 - 1480.0) * 1025.0 / 1080.0 - 25.0
    els = [
        {'id': 'fundo', 'classe': 'base', 'funcao': 'fundo', 'caixa': [0.0, 0.0, 1080.0, 1920.0],
         'sangra': dict(G.TODOS)},
        {'id': 'azul', 'classe': 'base', 'funcao': 'grafismo', 'caixa': [0.0, 0.0, 1080.0, a_az[3]], 'caixa_asset': a_az,
         'sangra': {'esq': True, 'topo': True, 'dir': True}},
        {'id': 'veu', 'classe': 'base', 'funcao': 'grafismo', 'caixa': [0.0, 0.0, 1080.0, a_ve[3]], 'caixa_asset': a_ve,
         'sangra': {'esq': True, 'topo': True, 'dir': True}},
        {'id': 'titulo', 'classe': 'texto', 'funcao': 'titulo', 'caixa': [100.0, 150.0, 980.0, 400.0]},
        {'id': 'selo', 'classe': 'texto', 'funcao': 'texto_de_apoio', 'caixa': [700.0, yb - 180.0, 1025.0, yb]},
        {'id': 'assinatura', 'classe': 'marca', 'funcao': 'assinatura_institucional',
         'caixa': [340.0, 1560.0, 740.0, 1680.0]},
    ]
    return F.extrair_modelo(ref, els, silhuetas={'azul': s_az, 'veu': s_ve})


@pytest.mark.parametrize('kw', [{'escala_min': 0.98}, {'pisos': {'assinatura': 0.98}, 'escala_min': 0.9}])
def test_dois_f3_no_mesmo_bloco_nunca_passam_do_piso_somados(kw):
    """Revisao da 0.10.0: o piso do F3 vale sobre o tamanho copiado. Antes, cada F3 respeitava o piso sobre o tamanho
    atual, e dois seguidos deixavam a assinatura em 0,9735 com o piso em 0,98, como "ajustado"."""
    m = _duas_rampas()
    lay = F.ajustar_minimo(m, F.transferir(m, MEMBRO_AS), **kw)
    assert lay['fatores']['assinatura'] >= 0.98 - 1e-9
    assert lay['reducao']['assinatura'] >= 0.98 - 1e-9
    f3 = [a for a in lay['ajustes'] if a.get('tipo') == 'F3']
    prod = 1.0
    for a in f3:
        if 'assinatura' in a['elementos']:
            prod *= a['fator']
    assert prod >= 0.98 - 1e-9


def _diagonal(dy=0.0):
    """O caso de 18/11 (familia_geometria.caso_diagonal), com a assinatura levada dy px no eixo y."""
    ref, els, sil = G.caso_diagonal()
    for e in els:
        if e['id'] == 'assinatura':
            e['caixa'] = [e['caixa'][0], e['caixa'][1] + dy, e['caixa'][2], e['caixa'][3] + dy]
    return F.extrair_modelo(ref, els, silhuetas=sil)


def _pedidos_de_crescimento(lay):
    return {q['elementos'][0]: q for q in lay['relacoes_quebradas'] if q['tipo'] == 'crescimento'}


def test_crescimento_da_forma_ate_o_limite_nao_pede_ajuste_no_caso_aprovado():
    """No aprovado, o azul cresce 1,42 no 1080x1600 e a faixa verde 1,19 no 900x1870 (resposta do Duda em 18/11: o
    limite de 1,5 deixa o caso inteiro sem pedido)."""
    m = _diagonal()
    for membro in G.membros_do_caso():
        lay = F.ajustar_minimo(m, F.transferir(m, membro))
        assert _pedidos_de_crescimento(lay) == {} and lay['situacao'] != 'pede_ajuste', membro['id']
    lay = F.ajustar_minimo(m, F.transferir(m, G.membro('f1080x1600', 1080, 1600)))
    assert 1.4 < lay['bases']['azul']['crescimento'] < limites.valor('derivacao.familia_crescimento_max')


def test_forma_que_cresce_alem_do_limite_pede_ajuste_com_o_valor():
    """A assinatura sobre o azul: o hospede do azul passa a ser o texto, longe da diagonal, e o azul cresce 1,8 no
    1080x1600 para continuar sangrando. O arquivo pede ajuste, com a frase e o valor; o layout fica como a copia deu."""
    m = _diagonal(dy=-200.0)
    membro = G.membro('f1080x1600', 1080, 1600)
    tr = F.transferir(m, membro)
    lay = F.ajustar_minimo(m, tr)
    g = tr['bases']['azul']['crescimento']
    assert g == pytest.approx(1.802, abs=1e-3)
    assert lay['situacao'] == 'pede_ajuste' and list(_pedidos_de_crescimento(lay)) == ['azul']
    q = _pedidos_de_crescimento(lay)['azul']
    assert q['relacao'] == 'crescimento:azul' and q['crescimento'] == g and q['valor_px'] == 0.0
    assert q['frase'] == ('A forma precisou ficar 1,8 vezes maior neste arquivo para continuar chegando às bordas '
                          'esquerda, de cima e direita, e o desdobra só aumenta até 1,5 vezes sem pedir o seu olhar. '
                          'Confira este arquivo antes de confirmar.')
    assert lay['caixas_asset']['azul'] == tr['caixas_asset']['azul'] and _sangra(lay, m, 'azul')
    # os outros arquivos do mesmo caso continuam sem pedido de crescimento
    for outro in G.membros_do_caso():
        if outro['id'] != 'f1080x1600':
            assert _pedidos_de_crescimento(F.ajustar_minimo(m, F.transferir(m, outro))) == {}, outro['id']


def test_o_fundo_puro_cresce_sem_limite():
    """Com o limite de 1,1, a forma (1,42 e 1,13) e a faixa (1,19 no 900x1870) pedem ajuste, e o fundo (1,215 e 1,17)
    nunca: ele cresce o quanto precisar para cobrir o arquivo."""
    m = _diagonal()
    lay = F.ajustar_minimo(m, F.transferir(m, G.membro('f1080x1600', 1080, 1600)), crescimento_max=1.1)
    assert lay['bases']['fundo']['crescimento'] > 1.1
    assert set(_pedidos_de_crescimento(lay)) == {'azul'}
    lay = F.ajustar_minimo(m, F.transferir(m, G.membro('f900x1870', 900, 1870)), crescimento_max=1.1)
    assert lay['bases']['fundo']['crescimento'] > 1.1 and set(_pedidos_de_crescimento(lay)) == {'azul', 'verde'}


def test_limite_do_crescimento_tem_fonte_e_fica_a_calibrar():
    lim = limites.obter('derivacao.familia_crescimento_max')
    assert lim.situacao == 'a_calibrar' and lim.efeito_efetivo == 'registra' and lim.valor == 1.5
    assert lim.fonte['arquivo'] == 'decisoes-v1.md' and '199' in lim.fonte['secao']


def test_forma_agrupada_a_um_conteudo_tambem_tem_o_limite():
    """A faixa verde que o DA juntou a assinatura anda como conteudo e cresce em volta do centro (_sangrar_movel): o
    limite vale para ela como para a forma solta (revisao do limite). Sem o azul, so a faixa conta."""
    ref, els, sil = G.caso_diagonal()
    els = [e for e in els if e['id'] != 'azul']
    membro = G.membro('f300x900', 300, 900)
    for grupos in ((), (['verde', 'assinatura'],)):
        m = F.extrair_modelo(ref, els, silhuetas={}, grupos=grupos)
        lay = F.ajustar_minimo(m, F.transferir(m, membro))
        assert lay['situacao'] == 'pede_ajuste' and list(_pedidos_de_crescimento(lay)) == ['verde'], grupos
    assert m['elementos']['verde']['papel'] == 'movel' and lay['crescimento_movel']['verde'] > 1.5
    assert _pedidos_de_crescimento(lay)['verde']['frase'].startswith(
        'O grafismo precisou ficar 2,4 vezes maior neste arquivo para continuar chegando às bordas esquerda, de cima '
        'e de baixo,')
    # no 300x600 a faixa agrupada cresce 1,25: sem pedido
    lay = F.ajustar_minimo(m, F.transferir(m, G.membro('f300x600', 300, 600)))
    assert _pedidos_de_crescimento(lay) == {} and lay['situacao'] == 'igual'


def test_o_valor_da_frase_nunca_empata_com_o_limite():
    """Entre 1,5 e 1,55 a casa decimal mostraria 1,5 dos dois lados: o valor sobe para 1,6."""
    m = _diagonal()
    na_beira = 0
    for fid, W, H in (('f300x780', 300, 780), ('f300x820', 300, 820)):
        lay = F.ajustar_minimo(m, F.transferir(m, G.membro(fid, W, H)))
        for k, q in _pedidos_de_crescimento(lay).items():
            if q['crescimento'] < 1.55:
                na_beira += 1
                assert '1,6 vezes maior' in q['frase'] and 'até 1,5 vezes' in q['frase'], (fid, k, q['crescimento'])
    assert na_beira >= 1  # a faixa verde no 300x780 (1,53) e o azul no 300x820 (1,53)
    assert '1,6 vezes maior' in F._frase_crescimento(m, 'azul', 1.5001, 1.5)
    assert '1,8 vezes maior' in F._frase_crescimento(m, 'azul', 1.802, 1.5)
    assert 'chegando à borda esquerda,' in F._frase_crescimento(
        dict(m, elementos=dict(m['elementos'], azul=dict(m['elementos']['azul'], sangra={'esq': True}))),
        'azul', 1.8, 1.5)


def test_frases_do_crescimento_seguem_as_regras_de_escrita():
    m = _diagonal(dy=-200.0)
    frases = [q['frase'] for q in F.ajustar_minimo(m, F.transferir(m, G.membro('f1080x1600', 1080, 1600)),
                                                    crescimento_max=1.05)['relacoes_quebradas']]
    assert frases
    for f in frases:
        assert '—' not in f and '–' not in f and ' - ' not in f, f
        assert f[0].isupper() and f.endswith('.') and 'não é' not in f, f
