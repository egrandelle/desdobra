# -*- coding: utf-8 -*-
"""Galeria de variantes do formato sem familia (decisoes-v1.md, 164 e as notas de 05/11), escrita antes do codigo.

Nenhum formato volta ao DA sem sugestao e nunca ha mestre por orientacao: na troca de orientacao e na proporcao fora
da faixa, o motor monta de 3 a 4 variantes de fato diferentes, so com os blocos do KV, e o DA escolhe uma e ajusta.
So previa em memoria: nada e gravado. Os KVs daqui sao sinteticos (os geradores de test_derivacao_apoio)."""
import itertools
import json
import math
import re
import time

import pytest

import test_derivacao_apoio as ap
from desdobra import arquivos, contratos, limites
from desdobra.derivacao import escala as mesc
from desdobra.derivacao import galeria as mg
from desdobra.derivacao import nucleo as nd
from desdobra.derivacao import solver as ms

DEVOLVIDOS = ('troca_forte_de_orientacao', 'troca_de_orientacao_quadrado', 'fora_da_faixa_de_familia')
TOL = 1.0
ORCAMENTO_S = 2.0  # teto da previa ao vivo para as 4 variantes de um formato (o prototipo levou de 0,08 a 0,2 s)
IDS_DO_MOTOR = re.compile(r'\bel\d+|derivacao\.|_[a-z]')


def _kv_horizontal():
    """O KV horizontal 400 x 200 de test_derivacao_apoio, com um grafismo fino que sangra em cima e embaixo e uma arte
    que sangra em tres lados (35% do canvas), os dois logo acima do fundo na pilha (embaixo do conteudo)."""
    base = ap.laudo()['camadas']
    cams = base[:1] + [ap.camada(70, 'pixel', [226, 0, 232, 200]), ap.camada(80, 'pixel', [260, 0, 400, 200])] + base[1:]
    return ap.laudo(camadas=cams), {**ap.FUNCOES, 70: 'grafismo', 80: 'imagem'}


def _kv_vertical():
    """KV vertical 200 x 400: fundo, titulo, apoio, marca embaixo e legal colado a base."""
    cams = [ap.camada(1, 'pixel', [0, 0, 200, 400]), ap.camada(10, 'texto', [20, 30, 180, 110], corpo=36),
            ap.camada(20, 'texto', [20, 140, 170, 180], corpo=16), ap.camada(30, 'smart_embutido', [60, 300, 140, 350]),
            ap.camada(40, 'texto', [20, 388, 180, 396], corpo=6)]
    return ap.laudo(200, 400, cams), {1: 'fundo', 10: 'titulo', 20: 'texto_de_apoio', 30: 'logo_principal',
                                      40: 'texto_legal'}


FORMATOS_H = [('v', 300, 600), ('alto', 1080, 1920), ('q', 400, 400), ('faixa', 1920, 192),
              ('banner', 728, 90)]
FORMATOS_V = [('h', 1920, 1080), ('h2', 1280, 720), ('q', 500, 500), ('faixa', 1248, 250)]


def _job(kv_fn, formatos, regras=None):
    laudo, funcoes = kv_fn()
    b = ap.briefing(funcoes=funcoes, formatos=[ap.formato(i, w, h) for i, w, h in formatos], regras=regras)
    ctx = nd.contexto(laudo, b)
    r = nd.derivar_em_memoria(ctx, specs={})
    devolvidos = [f for f in b['formatos'] if r['formatos'][f['id']]['situacao'] == 'devolvido'
                  and r['formatos'][f['id']]['devolucao']['motivo'] in DEVOLVIDOS]
    return ctx, r['kv'], devolvidos


@pytest.fixture(scope='module')
def galerias():
    saida = []
    for kv_fn, fmts in ((_kv_horizontal, FORMATOS_H), (_kv_vertical, FORMATOS_V)):
        ctx, kv, devolvidos = _job(kv_fn, fmts)
        assert len(devolvidos) == len(fmts)
        for f in devolvidos:
            saida.append((ctx, kv, f, mg.variantes(ctx, kv, f)))
    return saida


def _centro(c):
    return (c[0] + c[2]) / 2.0, (c[1] + c[3]) / 2.0


def _distancia(kv, f, a, b):
    """Media do deslocamento do centro de cada elemento de conteudo entre duas variantes, sobre a diagonal."""
    diag = math.hypot(f['largura'], f['altura'])
    ca = {e['id']: e['caixa'] for e in a['elementos']}
    cb = {e['id']: e['caixa'] for e in b['elementos']}
    ds = [math.dist(_centro(ca[e['id']]), _centro(cb[e['id']])) / diag for e in kv['elementos'] if ms.conteudo(e)]
    return sum(ds) / len(ds)


def _sobrepoe(a, b, tol):
    return min(a[2], b[2]) - max(a[0], b[0]) > tol and min(a[3], b[3]) - max(a[1], b[1]) > tol


def _violacoes(kv, f, v):
    """O que a variante quebra, medido aqui por fora: conteudo fora do formato, sobreposicao nova e escala abaixo do
    piso da 133 em fracao da regra verdadeira do formato."""
    W, H = f['largura'], f['altura']
    cx = {e['id']: e for e in v['elementos']}
    piso = limites.valor('derivacao.escala_conteudo_min_da_regra')
    ruins = []
    for e in kv['elementos']:
        if not ms.conteudo(e):
            continue
        c = cx[e['id']]['caixa']
        if c[0] < -TOL or c[1] < -TOL or c[2] > W + TOL or c[3] > H + TOL:
            ruins.append(('fora', e['id']))
        regra = mesc.escala(e['regra'], (kv['largura'], kv['altura']), (W, H))
        if cx[e['id']]['escala'] < piso * regra - 1e-6:
            ruins.append(('piso', e['id']))
    for a, b in itertools.combinations(kv['elementos'], 2):
        if ms.par_que_nao_sobrepoe(a, b) and not _sobrepoe(a['caixa'], b['caixa'], 0.0) and \
                _sobrepoe(cx[a['id']]['caixa'], cx[b['id']]['caixa'], TOL):
            ruins.append(('sobre', a['id'], b['id']))
    return ruins


# ------------------------------------------------------------------ a galeria
def test_todo_formato_devolvido_ganha_de_3_a_4_variantes_com_cada_elemento(galerias):
    maximo = limites.valor('derivacao.galeria_variantes_max')
    for _ctx, kv, f, vs in galerias:
        assert 3 <= len(vs) <= maximo, (f['id'], [v['id'] for v in vs])
        assert [v['ordem'] for v in vs] == list(range(1, len(vs) + 1))
        assert len({v['id'] for v in vs}) == len(vs)
        for v in vs:
            assert {e['id'] for e in v['elementos']} == {e['id'] for e in kv['elementos']}
            for e in v['elementos']:
                assert len(e['caixa']) == 4 and e['escala'] > 0
                assert e['transformacao']['destino'] == e['caixa'][:2]
            assert set(v) >= {'id', 'descricao', 'elementos', 'avisos', 'falhas_obrigatorias', 'ordem'}
            for a in v['avisos'] + v['falhas_obrigatorias']:
                assert set(a) >= {'codigo', 'texto'}


def test_variantes_de_um_formato_sao_de_fato_diferentes(galerias):
    limiar = limites.valor('derivacao.galeria_duplicada_distancia_max')
    for _ctx, kv, f, vs in galerias:
        pares = [_distancia(kv, f, a, b) for a, b in itertools.combinations(vs, 2)]
        assert min(pares) >= limiar, (f['id'], pares)
        assert sum(pares) / len(pares) > limiar


def test_descricao_uma_linha_em_portugues_e_unica_no_formato(galerias):
    for _ctx, _kv, f, vs in galerias:
        descricoes = [v['descricao'] for v in vs]
        assert len(set(descricoes)) == len(descricoes), (f['id'], descricoes)
        for d in descricoes:
            assert d and '\n' not in d and d[0].isupper()
            assert '—' not in d and '–' not in d
            assert not IDS_DO_MOTOR.search(d), d
        for v in vs:
            for a in v['avisos'] + v['falhas_obrigatorias']:
                assert '—' not in a['texto'] and '–' not in a['texto']
                assert not IDS_DO_MOTOR.search(a['texto']), a['texto']


def test_espelhado_no_quadrado_descreve_a_ordem_que_desenha():
    """Defeito do prototipo (revisao): no quadrado, o espelho usava o lado maior do quadro e a descricao o do formato;
    a variante espelhada saia com a mesma frase da reorganizada e outra geometria. O caso: legal fino colado a direita
    de um KV vertical; no quadrado, a reserva dele deixa o quadro mais alto que largo. Desde 19/11 os ids e a ordem
    saem da nota: a candidata espelhada e a mesma particao com outra ordem e diz isso na frase."""
    def kv_legal_na_direita():
        cams = [ap.camada(1, 'pixel', [0, 0, 200, 400]), ap.camada(10, 'texto', [20, 30, 170, 110], corpo=36),
                ap.camada(30, 'smart_embutido', [50, 300, 130, 350]), ap.camada(40, 'texto', [190, 40, 197, 360], corpo=6)]
        return ap.laudo(200, 400, cams), {1: 'fundo', 10: 'titulo', 30: 'logo_principal', 40: 'texto_legal'}
    ctx, kv, devolvidos = _job(kv_legal_na_direita, [('q', 300, 300)])
    cf = mg._contexto(ctx, kv, devolvidos[0], {}, None)
    p = mg.parametros_do_id('reorganizado')
    reto, espelho = mg.gerar(cf, p), mg.gerar(cf, dict(p, espelhar=True))
    assert reto['part'] == espelho['part'] and reto['tipo'] == espelho['tipo']
    assert espelho['caixas']['el10'] != reto['caixas']['el10']
    assert 'na ordem invertida' in mg.descrever(cf, espelho) and 'invertida' not in mg.descrever(cf, reto)
    assert mg.descrever(cf, espelho).replace(', na ordem invertida', '') == mg.descrever(cf, reto)
    # a marca, que vinha depois do titulo, vem antes dele no eixo em que a pilha corre
    eixo = 1 if reto['tipo'] == 'colunas' else 0
    assert reto['caixas']['el10'][eixo] < reto['caixas']['el30'][eixo]
    assert espelho['caixas']['el30'][eixo] < espelho['caixas']['el10'][eixo]
    assert mg.parametros_do_id(mg._id(dict(p, espelhar=True))) == dict(p, espelhar=True)


def test_galeria_e_deterministica(galerias):
    for ctx, kv, f, vs in galerias[:4]:
        assert json.dumps(mg.variantes(ctx, kv, f), sort_keys=True) == json.dumps(vs, sort_keys=True)
    laudo, funcoes = _kv_horizontal()
    b = ap.briefing(funcoes=funcoes, formatos=[ap.formato('v', 300, 600)])
    ctx2 = nd.contexto(laudo, b)
    a = mg.variantes(ctx2, nd.mestre_do_kv(ctx2), b['formatos'][0])
    ref = next(vs for _c, _k, f, vs in galerias if f['id'] == 'v')
    assert json.dumps(a, sort_keys=True) == json.dumps(ref, sort_keys=True)


def test_sem_elemento_fora_sem_sobreposicao_nova_e_com_o_piso_da_133(galerias):
    for _ctx, kv, f, vs in galerias:
        limpas = 0
        for v in vs:
            ruins = _violacoes(kv, f, v)
            if not v['falhas_obrigatorias']:
                assert not ruins, (f['id'], v['id'], ruins)
                limpas += 1
        assert limpas, f['id']


def test_falha_da_135_e_conferida_contra_a_mestre_verdadeira():
    """A distancia minima entre conteudo (135) vem da mestre do KV, nunca da mestre sintetica do fluxo: o par que a
    variante aproxima demais aparece em falhas_obrigatorias com o codigo e os dois elementos."""
    ctx, kv, devolvidos = _job(_kv_horizontal, [('v', 300, 600)])
    f = devolvidos[0]
    v = mg.variantes(ctx, kv, f)[0]
    cx = {e['id']: e['caixa'] for e in v['elementos']}
    # aproxima o apoio do titulo: encosta o topo do apoio na base do titulo
    t, a = cx['el10'], cx['el20']
    falsa = [dict(e, caixa=[a[0], t[3], a[2], t[3] + (a[3] - a[1])]) if e['id'] == 'el20' else e for e in v['elementos']]
    falhas = mg.conferir(ctx, kv, f, falsa)['falhas_obrigatorias']
    assert any(x['codigo'] == 'distancia_menor_que_na_mestre' and set(x['elementos']) == {'el10', 'el20'} for x in falhas)


def test_ordem_e_pela_nota_com_as_limpas_primeiro(galerias):
    """Sem molde por proporcao (decisao 166): a ordem nao depende de o formato ser faixa ou nao, sai da nota. As versoes
    sem falha obrigatoria vem antes, da melhor nota para a pior; a com falha so entra para chegar ao minimo."""
    minimo = limites.valor('derivacao.galeria_variantes_min')
    for _ctx, _kv, f, vs in galerias:
        chaves = [(bool(v['falhas_obrigatorias']), -v['nota']) for v in vs]
        assert chaves == sorted(chaves), (f['id'], chaves)
        limpas = sum(1 for v in vs if not v['falhas_obrigatorias'])
        assert len(vs) - limpas <= max(0, minimo - limpas), (f['id'], chaves)


def test_sem_falha_na_primeira_versao_quando_existe_versao_limpa(galerias):
    for _ctx, _kv, f, vs in galerias:
        if any(not v['falhas_obrigatorias'] for v in vs):
            assert not vs[0]['falhas_obrigatorias'], (f['id'], [v['id'] for v in vs])


def test_ids_das_versoes_desfazem_nos_parametros(galerias):
    """A tela le a versao pelo id; variante_para_grupo refaz a mesma versao nos membros pelos parametros do id."""
    for _ctx, _kv, f, vs in galerias:
        for v in vs:
            assert re.fullmatch(r'[a-z][a-z0-9_]*', v['id']), v['id']
            assert mg._id(mg.parametros_do_id(v['id'])) == v['id']
    assert mg.parametros_do_id('id_que_nao_existe') == mg.parametros_do_id('reorganizado')


# ------------------------------------------------------------------ avisos
def _avisos(galerias, fid, kv_fn=_kv_horizontal):
    return {a['codigo']: (v['id'], a) for _c, kv, f, vs in galerias if f['id'] == fid for v in vs for a in v['avisos']}


def test_aviso_de_texto_abaixo_de_8_px(galerias):
    av = _avisos(galerias, 'v')
    assert 'texto_abaixo_de_8px' in av
    assert '8 px' in av['texto_abaixo_de_8px'][1]['texto']


def test_aviso_de_fundo_com_menos_de_30_por_cento_visivel(galerias):
    """O aviso fica para o fundo com imagem que nao cobre o canvas do KV. O fundo que cobre o canvas inteiro (a troca
    de proporcao sempre corta parte dele) e o de cor chapada saem do aviso: o corte nao tira nada do KV."""
    assert 'fundo_pouco_visivel' not in _avisos(galerias, 'faixa')  # o fundo do KV horizontal cobre o canvas

    def kv_fundo(tipo):
        def kv():
            laudo, funcoes = _kv_horizontal()
            # o fundo para 8 px antes da base: ainda e fundo de cena (derivacao.bloco_fundo_fracao), sem cobrir o canvas
            cams = [ap.camada(1, tipo, [0, 0, 400, 192])] + laudo['camadas'][1:]
            return ap.laudo(camadas=cams), funcoes
        return kv
    for tipo, tem in (('pixel', True), ('cor_solida', False)):
        ctx, kv, devolvidos = _job(kv_fundo(tipo), [('faixa', 1920, 192)])
        assert len(devolvidos) == 1, tipo
        avisos = [a for v in mg.variantes(ctx, kv, devolvidos[0]) for a in v['avisos']
                  if a['codigo'] == 'fundo_pouco_visivel']
        assert bool(avisos) == tem, tipo
        assert all('30%' in a['texto'] for a in avisos)


def test_aviso_de_grafismo_muito_acima_da_regra(galerias):
    av = _avisos(galerias, 'v')
    assert 'grafismo_acima_da_regra' in av


def test_aviso_de_sangria_da_arte_que_mudou_so_na_imagem_livre(galerias):
    for _c, _kv, f, vs in galerias[:len(FORMATOS_H)]:
        for v in vs:
            tem = any(a['codigo'] == 'sangria_da_arte_mudou' for a in v['avisos'])
            assert tem == v['id'].startswith('imagem_livre'), (f['id'], v['id'])


def test_aviso_de_conteudo_secundario_que_nao_cabe():
    regras = dict(ap.REGRAS, titulo='constante', texto_de_apoio='constante', logo_principal='constante')
    ctx, kv, devolvidos = _job(_kv_horizontal, [('fino', 60, 200)], regras=regras)
    vs = mg.variantes(ctx, kv, devolvidos[0])
    assert vs and all(any(a['codigo'] == 'conteudo_nao_cabe' for a in v['avisos']) for v in vs)


# ------------------------------------------------------------------ grupo de 0,3
def test_variante_para_grupo_aplica_uma_estrutura_a_todos_pelo_pior_membro():
    ctx, kv, devolvidos = _job(_kv_horizontal, [('v', 300, 600), ('alto', 1080, 1920), ('v2', 320, 600)])
    ps = [max(f['largura'], f['altura']) / min(f['largura'], f['altura']) for f in devolvidos]
    assert max(ps) - min(ps) <= limites.valor('derivacao.grupo_proporcao_dif_max')
    g = mg.variante_para_grupo(ctx, kv, devolvidos, 'reorganizado')
    assert g['variante'] == 'reorganizado'
    assert set(g['membros']) == {f['id'] for f in devolvidos}
    estruturas = {json.dumps(v['estrutura'], sort_keys=True) for v in g['membros'].values()}
    assert len(estruturas) == 1
    assert g['estrutura'] == next(iter(g['membros'].values()))['estrutura']
    # a escolhida e a de melhor pior membro entre as candidatas
    melhor = max(g['candidatas'], key=lambda c: (c['membros_sem_falha'], c['pior_escala_relativa']))
    assert (g['membros_sem_falha'], g['pior_escala_relativa']) == (melhor['membros_sem_falha'],
                                                                    melhor['pior_escala_relativa'])
    assert g['membros_sem_falha'] == len(devolvidos)
    for v in g['membros'].values():
        assert not v['falhas_obrigatorias']


# ------------------------------------------------------------------ previa, tempo e limites
def test_galeria_e_so_previa_nada_e_gravado(monkeypatch):
    def proibido(*_a, **_k):
        raise AssertionError('a galeria gravou um arquivo')
    for nome in ('gravar_bytes_atomico', 'gravar_texto_atomico', 'gravar_json_atomico'):
        monkeypatch.setattr(arquivos, nome, proibido)
    monkeypatch.setattr(contratos, 'gravar', proibido)
    ctx, kv, devolvidos = _job(_kv_vertical, [('h', 1920, 1080)])
    assert mg.variantes(ctx, kv, devolvidos[0])
    assert mg.variante_para_grupo(ctx, kv, devolvidos, 'reorganizado')['membros']


def test_quatro_variantes_cabem_na_previa_ao_vivo():
    ctx, kv, devolvidos = _job(_kv_horizontal, [('v', 300, 600)])
    mg.variantes(ctx, kv, devolvidos[0])
    t0 = time.perf_counter()
    vs = mg.variantes(ctx, kv, devolvidos[0])
    assert 3 <= len(vs) <= limites.valor('derivacao.galeria_variantes_max') and time.perf_counter() - t0 < ORCAMENTO_S


def test_limite_de_variantes_e_respeitado():
    ctx, kv, devolvidos = _job(_kv_horizontal, [('v', 300, 600)])
    assert len(mg.variantes(ctx, kv, devolvidos[0], limite=2)) == 2


def test_limites_novos_da_galeria_tem_fonte_e_nao_reprovam():
    ids = ('derivacao.galeria_duplicada_distancia_max', 'derivacao.galeria_conteudo_fracao',
           'derivacao.galeria_fundo_visivel_min', 'derivacao.galeria_grafismo_sobre_regra_max',
           'derivacao.galeria_variantes_max', 'derivacao.galeria_arte_area_min')
    for lid in ids:
        lim = limites.obter(lid)
        assert lim.situacao == 'a_calibrar' and lim.efeito_efetivo != 'reprova', lid
        assert lim.fonte['arquivo'] == 'decisoes-v1.md' and '05/11' in lim.fonte['secao'], lid
    assert limites.valor('derivacao.galeria_duplicada_distancia_max') == 0.03
    assert limites.valor('derivacao.galeria_conteudo_fracao') == 0.6
    assert limites.valor('derivacao.galeria_fundo_visivel_min') == 0.3
    assert limites.valor('derivacao.galeria_grafismo_sobre_regra_max') == 2.0
    assert limites.valor('derivacao.galeria_variantes_max') == 4
    # sem molde por proporcao (166): o limiar de faixa que decidia a ordem saiu do registro
    with pytest.raises(limites.ErroLimite):
        limites.obter('derivacao.galeria_faixa_razao_min')
    # os da calibracao de 19/11 (o prototipo fluxo com os enxertos do juiz)
    novos = {'derivacao.galeria_variantes_min': 3, 'derivacao.galeria_candidatas_ao_solver': 10,
             'derivacao.galeria_teto_sobre_regra': 3.5, 'derivacao.galeria_expoente_titulo': 1.5,
             'derivacao.galeria_titulo_sobre_outros_max': 1.6, 'derivacao.galeria_expoente_secundario': 0.8,
             'derivacao.galeria_serie_tolerancia': 0.15, 'derivacao.galeria_faixa_distancia_max': 0.06,
             'derivacao.galeria_faixa_espessura_max': 0.06, 'derivacao.galeria_faixa_largura_min': 0.6,
             'derivacao.galeria_figura_area_min': 0.08, 'derivacao.galeria_figura_banda_max': 0.5,
             'derivacao.galeria_figura_teto_sobre_regra': 2.5, 'derivacao.galeria_figura_reducao_passo': 0.9,
             'derivacao.galeria_figura_reducao_min': 0.6, 'derivacao.galeria_sujeito_sangria_extra': 0.03,
             'derivacao.galeria_figura_visivel_min': 0.85, 'derivacao.galeria_nota_satura': 2.0,
             'derivacao.galeria_folga_135': 0.1, 'derivacao.galeria_ordem_tolerancia': 0.01,
             'derivacao.galeria_margem_max_lado_curto': 0.12}
    for lid, valor in novos.items():
        lim = limites.obter(lid)
        assert lim.valor == valor and lim.situacao == 'a_calibrar' and lim.efeito_efetivo == 'registra', lid
        assert lim.fonte['arquivo'] == 'decisoes-v1.md' and '19/11' in lim.fonte['secao'], lid
    pesos = {x['termo']: x['peso'] for x in limites.valor('derivacao.galeria_nota_pesos')}
    assert set(pesos) == {'falha', 'escala', 'menor', 'razao', 'figura', 'cobre', 'lado', 'espelho', 'vazio', 'ordem',
                          'serie_partida'}
    assert all(p > 0 for p in pesos.values())


# ------------------------------------------------------------------ revisao da galeria no motor
def test_legal_colado_fica_fora_do_piso_da_135_e_o_resto_nao():
    """Decisao do Duda (05/11): o legal colado a borda fica fora do piso de distancia da 135 na galeria (a distancia
    dele na mestre vem da largura do KV, nao de intencao de desenho); o piso continua para todo outro par de conteudo."""
    ctx, kv, devolvidos = _job(_kv_vertical, [('h', 1920, 1080)])
    f = devolvidos[0]
    v = mg.variantes(ctx, kv, f)[0]
    cx = {e['id']: e['caixa'] for e in v['elementos']}
    lg, mc = cx['el40'], cx['el30']
    # encosta o topo do legal na base da marca, com as projecoes em x se tocando
    falsa = [dict(e, caixa=[mc[0], mc[3], mc[0] + (lg[2] - lg[0]), mc[3] + (lg[3] - lg[1])]) if e['id'] == 'el40' else e
             for e in v['elementos']]
    r = mg.conferir(ctx, kv, f, falsa)
    assert not any(x['codigo'] == 'distancia_menor_que_na_mestre' and 'el40' in x['elementos']
                   for x in r['falhas_obrigatorias']), r
    # o mesmo encosto entre dois elementos que nao sao legal colado continua falha obrigatoria
    outros = [e['id'] for e in v['elementos'] if e['id'] not in ('el40', 'el30')
              and e['funcao'] not in ('fundo', 'texto_legal')]
    alvo = outros[0]
    ca = cx[alvo]
    falsa2 = [dict(e, caixa=[mc[0], mc[3], mc[0] + (ca[2] - ca[0]), mc[3] + (ca[3] - ca[1])]) if e['id'] == alvo else e
              for e in v['elementos']]
    r2 = mg.conferir(ctx, kv, f, falsa2)
    assert any(x['codigo'] in ('distancia_menor_que_na_mestre', 'sobreposicao_nova') and alvo in x['elementos']
               for x in r2['falhas_obrigatorias']), r2


def _melhor_por_forca_bruta(an, quadro, s_cap, tipos=('colunas', 'linhas'), excluir=()):
    melhor = None
    for tipo in tipos:
        for part in mg.particoes(len(an['atomos'])):
            if (tipo, tuple(len(t) for t in part)) in excluir:
                continue
            score, s, s_fit, esp = mg.avaliar_particao(an, quadro, s_cap, tipo, part)
            if melhor is None or score > melhor[0] + mg.DESEMPATE:
                melhor = (score, s, s_fit, tipo, part, esp)
    return melhor


def _analise_sintetica(dims, vao, estrutura):
    atomos, x = [], 0.0
    for k, (w, h) in enumerate(dims):
        atomos.append({'caixa': [x, 0.0, x + w, h], 'els': [], 'col_mestre': k % estrutura[1]})
        x += w + vao
    return {'atomos': atomos, 'vao': vao, 'estrutura': estrutura}


def test_melhor_particao_e_a_mesma_da_busca_exaustiva():
    """A busca da particao corta o que nao pode ganhar e devolve exatamente a da busca em todas as particoes (mesmo
    desempate), inclusive com atomos iguais e com particoes excluidas."""
    import random
    sorteio = random.Random(7)
    for n in range(1, 10):
        for _rodada in range(12):
            iguais = sorteio.random() < 0.3
            base = (sorteio.uniform(20, 300), sorteio.uniform(10, 120))
            dims = [base if iguais else (sorteio.uniform(20, 300), sorteio.uniform(10, 120)) for _ in range(n)]
            an = _analise_sintetica(dims, sorteio.uniform(0, 30), ('colunas', sorteio.randint(1, 3)))
            quadro = [0.0, 0.0, sorteio.uniform(100, 2000), sorteio.uniform(60, 2000)]
            s_cap = sorteio.uniform(0.2, 1.5)
            assert mg.melhor_particao(an, quadro, s_cap) == _melhor_por_forca_bruta(an, quadro, s_cap), (n, dims)
            for tipo in ('colunas', 'linhas'):
                ref = _melhor_por_forca_bruta(an, quadro, s_cap, tipos=(tipo,))
                exc = {(tipo, tuple(len(t) for t in ref[4]))}
                assert mg.melhor_particao(an, quadro, s_cap, tipos=(tipo,), excluir=exc) == \
                    _melhor_por_forca_bruta(an, quadro, s_cap, tipos=(tipo,), excluir=exc), (n, tipo)


def test_kv_denso_de_16_linhas_cabe_na_previa():
    """O custo da galeria nao dobra a cada atomo: um KV vertical com 16 linhas de texto vai a um grupo de 3 formatos
    horizontais (variantes e variante_para_grupo de cada uma) dentro do teto da previa ao vivo por formato."""
    n, W, passo = 16, 200, 60
    H = 40 + n * passo
    cams = [ap.camada(1, 'pixel', [0, 0, W, H])]
    fun = {1: 'fundo'}
    for k in range(n):
        y = 20 + k * passo
        cams.append(ap.camada(100 + k, 'texto', [20, y, 180, y + 30], corpo=20))
        fun[100 + k] = 'texto_de_apoio' if k else 'titulo'
    fs = [ap.formato('h', 1920, 1080), ap.formato('h2', 1280, 720), ap.formato('h3', 960, 576)]
    b = ap.briefing(funcoes=fun, formatos=fs)
    ctx = nd.contexto(ap.laudo(W, H, cams), b)
    kv = nd.derivar_em_memoria(ctx, specs={})['kv']
    assert len(mg.analisar(kv)['atomos']) == n
    t0 = time.perf_counter()
    vs = mg.variantes(ctx, kv, b['formatos'][0], specs={})
    for v in vs:
        mg.variante_para_grupo(ctx, kv, b['formatos'], v['id'], specs={})
    assert vs and time.perf_counter() - t0 < ORCAMENTO_S * len(fs)


def test_solver_que_nao_fecha_nao_vira_aviso_de_conteudo_que_nao_cabe(monkeypatch):
    """Quando so o solver nao fecha (o conteudo cabe acima do piso da 133), a falha solver_nao_fecha diz o motivo e o
    aviso de conteudo que nao cabe, com a porcentagem e o pedido de tirar texto, nao aparece."""
    ctx, kv, devolvidos = _job(_kv_vertical, [('h', 1920, 1080)])

    def nao_fecha(*_a, **_k):
        raise ms.NaoFecha({'nome': 'area_segura:sintetica'})
    monkeypatch.setattr(ms, 'resolver', nao_fecha)
    vs = mg.variantes(ctx, kv, devolvidos[0])
    assert vs
    for v in vs:
        assert any(x['codigo'] == 'solver_nao_fecha' for x in v['falhas_obrigatorias']), v['id']
        assert not any(a['codigo'] == 'conteudo_nao_cabe' for a in v['avisos']), (v['id'], v['avisos'])


def test_textos_da_conferencia_falam_como_a_tela(galerias, monkeypatch):
    """Os textos de falha e aviso vao a tela como estao: a tela diz versao e KV, nunca variante nem mestre."""
    textos = [a['texto'] for _c, _kv, _f, vs in galerias for v in vs for a in v['avisos'] + v['falhas_obrigatorias']]
    ctx, kv, devolvidos = _job(_kv_horizontal, [('v', 300, 600)])
    f = devolvidos[0]
    v = mg.variantes(ctx, kv, f)[0]
    cx = {e['id']: e['caixa'] for e in v['elementos']}
    t, a = cx['el10'], cx['el20']
    falsa = [dict(e, caixa=[a[0], t[3], a[2], t[3] + (a[3] - a[1])]) if e['id'] == 'el20' else e for e in v['elementos']]
    r = mg.conferir(ctx, kv, f, falsa)
    textos += [x['texto'] for x in r['falhas_obrigatorias'] + r['avisos']]

    def nao_fecha(*_a, **_k):
        raise ms.NaoFecha({'nome': 'area_segura:sintetica'})
    monkeypatch.setattr(ms, 'resolver', nao_fecha)
    textos += [x['texto'] for v in mg.variantes(ctx, kv, f) for x in v['falhas_obrigatorias']]
    assert any('KV' in x for x in textos)
    for x in textos:
        assert 'mestre' not in x.lower() and 'variante' not in x.lower(), x
