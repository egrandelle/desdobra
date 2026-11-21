# -*- coding: utf-8 -*-
"""A galeria em KVs que nao sao o da calibracao (os KVs A e B do juiz da calibracao de 19/11), para a nota e os
limites nao ficarem presos ao cartaz. So numeros: caixas, funcoes, regras e ancoras inventadas.
  - KV A: horizontal 1920 x 1080, o sujeito a direita encostado so na base, o conteudo a esquerda com tres icones lado
    a lado;
  - KV B: vertical 1080 x 1920 sem sujeito, a marca no topo, quatro itens iguais empilhados e o legal colado a base.
Criterios:
  - a primeira versao de cada formato nao tem falha quando a galeria de antes tambem tinha uma primeira versao sem
    falha (GALERIA_DE_ANTES_LIMPA), e sempre que alguma versao do formato e limpa;
  - nenhum conteudo coberto pelo sujeito na primeira versao (o sujeito fica do lado dele e o conteudo no espaco livre),
    fora a versao com a foto de fundo (decisoes-v1.md, n 202);
  - nenhum conteudo abaixo do piso da 133 contra a regra verdadeira, em nenhuma versao;
  - o sujeito fica do lado em que esta no KV na primeira versao;
  - cada formato em menos de 2 s."""
import time

import pytest

import test_derivacao_apoio as ap
from desdobra import limites
from desdobra.derivacao import escala as mesc
from desdobra.derivacao import galeria as mg
from desdobra.derivacao import nucleo as nd
from desdobra.derivacao import solver as ms

ORCAMENTO_S = 2.0
FOLGA = 1e-6
REGRAS = {'fundo': 'raiz_area', 'sujeito': 'altura', 'titulo': 'altura', 'texto_de_apoio': 'altura', 'cta': 'altura',
          'grafismo': 'altura', 'logo_principal': 'altura', 'texto_legal': 'altura'}


def kv_a():
    cams = [ap.camada(1, 'pixel', [0, 0, 1920, 1080]), ap.camada(2, 'pixel', [1180, 140, 1820, 1080]),
            ap.camada(3, 'texto', [120, 160, 1020, 420], corpo=120), ap.camada(4, 'texto', [120, 470, 940, 560], corpo=40),
            ap.camada(5, 'pixel', [120, 620, 300, 760]), ap.camada(6, 'pixel', [340, 620, 520, 760]),
            ap.camada(7, 'pixel', [560, 620, 740, 760]), ap.camada(8, 'texto', [120, 820, 480, 900], corpo=44),
            ap.camada(9, 'pixel', [120, 940, 420, 1020])]
    funcoes = {1: 'fundo', 2: 'sujeito', 3: 'titulo', 4: 'texto_de_apoio', 5: 'grafismo', 6: 'grafismo', 7: 'grafismo',
               8: 'cta', 9: 'logo_principal'}
    ancoras = {'fundo': ('centro', 'meio'), 'sujeito': ('direita', 'base'), 'titulo': ('esquerda', 'topo'),
               'texto_de_apoio': ('esquerda', 'meio'), 'grafismo': ('esquerda', 'meio'), 'cta': ('esquerda', 'meio'),
               'logo_principal': ('esquerda', 'base')}
    formatos = [('v1080x1920', 1080, 1920), ('m300x600', 300, 600), ('s160x600', 160, 600), ('q1080', 1080, 1080),
                ('r300x250', 300, 250), ('w970x250', 970, 250), ('b728x90', 728, 90)]
    return ap.laudo(1920, 1080, cams), funcoes, ancoras, formatos


def kv_b():
    cams = [ap.camada(1, 'pixel', [0, 0, 1080, 1920]), ap.camada(2, 'pixel', [390, 100, 690, 200]),
            ap.camada(3, 'texto', [100, 300, 980, 700], corpo=150), ap.camada(4, 'texto', [140, 760, 940, 880], corpo=44),
            ap.camada(5, 'pixel', [240, 960, 840, 1080]), ap.camada(6, 'pixel', [240, 1110, 840, 1230]),
            ap.camada(7, 'pixel', [240, 1260, 840, 1380]), ap.camada(8, 'pixel', [240, 1410, 840, 1530]),
            ap.camada(9, 'texto', [300, 1620, 780, 1720], corpo=50), ap.camada(10, 'texto', [60, 1868, 1020, 1892], corpo=12)]
    funcoes = {1: 'fundo', 2: 'logo_principal', 3: 'titulo', 4: 'texto_de_apoio', 5: 'grafismo', 6: 'grafismo',
               7: 'grafismo', 8: 'grafismo', 9: 'cta', 10: 'texto_legal'}
    ancoras = {'fundo': ('centro', 'meio'), 'logo_principal': ('centro', 'topo'), 'titulo': ('centro', 'topo'),
               'texto_de_apoio': ('centro', 'meio'), 'grafismo': ('centro', 'meio'), 'cta': ('centro', 'meio'),
               'texto_legal': ('centro', 'base')}
    formatos = [('h1920', 1920, 1080), ('h1280', 1280, 720), ('w970x250', 970, 250), ('b728x90', 728, 90),
                ('q1080', 1080, 1080), ('r300x250', 300, 250)]
    return ap.laudo(1080, 1920, cams), funcoes, ancoras, formatos


# os formatos devolvidos de cada KV e os que a galeria de antes (ate 19/11) abria com uma versao sem falha
DEVOLVIDOS = {'A': {'v1080x1920', 'm300x600', 's160x600', 'q1080', 'w970x250', 'b728x90'},
              'B': {'h1920', 'h1280', 'w970x250', 'b728x90', 'q1080', 'r300x250'}}
GALERIA_DE_ANTES_LIMPA = {'A': {'w970x250', 'b728x90'},
                          'B': {'h1920', 'h1280', 'w970x250', 'b728x90', 'q1080', 'r300x250'}}


def _area(c):
    return max(0.0, c[2] - c[0]) * max(0.0, c[3] - c[1])


def _inter(a, b):
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


@pytest.fixture(scope='module', params=['A', 'B'])
def galeria(request):
    laudo, funcoes, ancoras, fmts = {'A': kv_a, 'B': kv_b}[request.param]()
    b = ap.briefing(funcoes=funcoes, regras=REGRAS, ancoras=ancoras,
                    formatos=[ap.formato(i, w, h) for i, w, h in fmts])
    ctx = nd.contexto(laudo, b)
    r = nd.derivar_em_memoria(ctx, specs={})
    kv = r['kv']
    devolvidos = [f for f in b['formatos'] if r['formatos'][f['id']]['situacao'] == 'devolvido']
    assert {f['id'] for f in devolvidos} == DEVOLVIDOS[request.param]
    mg.variantes(ctx, kv, devolvidos[0])  # aquecimento
    saida = []
    for f in devolvidos:
        t0 = time.perf_counter()
        vs = mg.variantes(ctx, kv, f)
        saida.append((f, vs, time.perf_counter() - t0))
    return request.param, kv, saida


def test_primeira_versao_sem_falha(galeria):
    nome, _kv, saida = galeria
    maximo = limites.valor('derivacao.galeria_variantes_max')
    for f, vs, _t in saida:
        assert 3 <= len(vs) <= maximo, (nome, f['id'], len(vs))
        if f['id'] in GALERIA_DE_ANTES_LIMPA[nome] or any(not v['falhas_obrigatorias'] for v in vs):
            assert not vs[0]['falhas_obrigatorias'], (nome, f['id'], vs[0]['falhas_obrigatorias'])


def test_nenhum_conteudo_coberto_pelo_sujeito_na_primeira_versao(galeria):
    nome, kv, saida = galeria
    sujeitos = [e['id'] for e in kv['elementos'] if e['funcao'] == 'sujeito']
    for f, vs, _t in saida:
        cx = {e['id']: e['caixa'] for e in vs[0]['elementos']}
        for s in sujeitos:
            if vs[0]['estrutura'].get('figura_de_fundo') == s:
                # decisoes-v1.md, n 202: na versao com a foto de fundo (KV deitado, formato em pe ou quadrado), o
                # conteudo sobre ela nao e defeito (test_galeria_figura_de_fundo)
                continue
            for e in kv['elementos']:
                if e['id'] == s or not ms.conteudo(e):
                    continue
                assert _inter(cx[e['id']], cx[s]) <= FOLGA * _area(cx[e['id']]), (nome, f['id'], e['id'])


def test_sujeito_fica_do_lado_do_kv_na_primeira_versao(galeria):
    nome, kv, saida = galeria
    for e in kv['elementos']:
        if e['funcao'] != 'sujeito':
            continue
        no_kv = (e['caixa'][0] + e['caixa'][2]) / 2.0 > kv['largura'] / 2.0
        for f, vs, _t in saida:
            c = next(x['caixa'] for x in vs[0]['elementos'] if x['id'] == e['id'])
            if f['largura'] > f['altura']:  # na peca deitada, o lado e o mesmo do KV
                assert ((c[0] + c[2]) / 2.0 > f['largura'] / 2.0) == no_kv, (nome, f['id'], c)


def test_nenhum_conteudo_abaixo_do_piso(galeria):
    nome, kv, saida = galeria
    piso = limites.valor('derivacao.escala_conteudo_min_da_regra')
    for f, vs, _t in saida:
        for v in vs:
            cx = {e['id']: e for e in v['elementos']}
            for e in kv['elementos']:
                if not ms.conteudo(e):
                    continue
                regra = mesc.escala(e['regra'], (kv['largura'], kv['altura']), (f['largura'], f['altura']))
                assert cx[e['id']]['escala'] >= piso * regra - FOLGA, (nome, f['id'], v['id'], e['id'])


def test_cada_formato_em_menos_de_2_s(galeria):
    nome, _kv, saida = galeria
    for f, _vs, t in saida:
        assert t < ORCAMENTO_S, (nome, f['id'], t)
