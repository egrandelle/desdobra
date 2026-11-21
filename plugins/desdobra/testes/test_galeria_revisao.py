# -*- coding: utf-8 -*-
"""A revisao da galeria nova (19/11): cada achado confirmado pelos revisores, com o KV sintetico que o mostrava. So
numeros: caixas, funcoes, regras e ancoras inventadas.
  - a foto que sangra em dois lados opostos fica limpa na banda (cresce ate passar das duas bordas); a banda que
    deixaria o corte a vista nao existe, e a falha prevista conta o lado que sangra sem passar da borda;
  - a foto que nao cabe em banda nenhuma fica de fundo, e a imagem livre completa o minimo;
  - a versao limpa que esta fora do primeiro lote do solver entra na galeria;
  - a particao e guardada pelo tamanho da area, e o KV denso sai em menos de 2 s;
  - o arredondamento das caixas nao fura o piso da 133, e a frase nunca diz "50%, abaixo do minimo de 50%";
  - o conteudo pequeno no meio do KV nao vira margem (o minimo de versoes);
  - o aviso do conteudo que nao cabe diz a escala que a versao mostra;
  - a foto no meio do KV nao tem lado;
  - o bloco que o solver esmaga e falha;
  - o vao da 135 entre a foto e o conteudo usa a escala do fluxo, nao a da regra;
  - o bloco de regra constante (o legal) nao prende o titulo;
  - a fileira empilhada nao vira escada;
  - a frase concorda com o genero do rotulo;
  - a arte livre nao passa por baixo do conteudo;
  - a impressao da familia conta so se ha galeria, nao a lista das versoes."""
import math
import time

import pytest

import test_derivacao_apoio as ap
import test_derivacao_galeria as tg
import test_galeria_generalidade as tgg
from desdobra import limites
from desdobra.derivacao import escala as mesc
from desdobra.derivacao import galeria as mg
from desdobra.derivacao import nucleo as nd
from desdobra.derivacao import solver as ms
try:
    # a geometria do cartaz fica so na maquina do Duda, fora do repositorio (autorizada so para calibrar, 19/11)
    from sinteticos import kv_cartaz as KC
except ImportError:
    KC = None
SEM_CARTAZ = pytest.mark.skipif(KC is None, reason='testes/sinteticos/kv_cartaz.py fica fora do repositorio')

ORCAMENTO_S = 2.0  # a previa de um formato (decisao do Duda: menos de 2 s)
FOLGA = 1e-6
REGRAS = dict(tgg.REGRAS, informacao_de_evento='altura', logo_de_parceiro='altura', url_ou_contato='altura')
# o conteudo do KV horizontal 1920 x 1080 dos casos de borda: titulo, apoio e marca a esquerda
CONTEUDO_H = [(3, 'texto', [120, 160, 1000, 420], 120), (4, 'texto', [120, 470, 900, 560], 40),
              (5, 'pixel', [120, 900, 420, 1000], None)]
FUNCOES_H = {1: 'fundo', 2: 'sujeito', 3: 'titulo', 4: 'texto_de_apoio', 5: 'logo_principal'}
ANCORAS_H = {'fundo': ('centro', 'meio'), 'sujeito': ('direita', 'meio'), 'titulo': ('esquerda', 'topo'),
             'texto_de_apoio': ('esquerda', 'meio'), 'logo_principal': ('esquerda', 'base')}


def _job(largura, altura, camadas, funcoes, ancoras, formatos, regras=None):
    cams = [ap.camada(lid, tipo, caixa, corpo=corpo) for lid, tipo, caixa, corpo in camadas]
    b = ap.briefing(funcoes=funcoes, regras=regras or REGRAS, ancoras=ancoras,
                    formatos=[ap.formato(i, w, h) for i, w, h in formatos])
    ctx = nd.contexto(ap.laudo(largura, altura, cams), b)
    r = nd.derivar_em_memoria(ctx, specs={})
    return ctx, r['kv'], {f['id']: f for f in b['formatos']}


def _com_sujeito(caixa):
    """O KV horizontal com o fundo, a foto na caixa dada e o conteudo a esquerda."""
    return [(1, 'pixel', [0, 0, 1920, 1080], None), (2, 'pixel', caixa, None)] + CONTEUDO_H


def _kv_c():
    """KV horizontal 1600 x 900 denso: titulo, apoio, uma grade 2 x 4 de informacoes, quatro logos de parceiro, a
    marca e o contato."""
    cams = [(1, 'pixel', [0, 0, 1600, 900], None), (2, 'texto', [80, 60, 1100, 200], 110),
            (3, 'texto', [80, 230, 900, 280], 30)]
    fun = {1: 'fundo', 2: 'titulo', 3: 'texto_de_apoio'}
    lid = 10
    for linha in range(4):
        for col in range(2):
            cams.append((lid, 'texto', [80 + 560 * col, 320 + 80 * linha, 560 + 560 * col, 370 + 80 * linha], 34))
            fun[lid] = 'informacao_de_evento'
            lid += 1
    for k in range(4):
        cams.append((lid, 'pixel', [80 + 200 * k, 700, 240 + 200 * k, 780], None))
        fun[lid] = 'logo_de_parceiro'
        lid += 1
    cams += [(lid, 'pixel', [1300, 700, 1520, 820], None), (lid + 1, 'texto', [1250, 60, 1520, 100], 28)]
    fun[lid], fun[lid + 1] = 'logo_principal', 'url_ou_contato'
    anc = {'fundo': ('centro', 'meio'), 'titulo': ('esquerda', 'topo'), 'texto_de_apoio': ('esquerda', 'meio'),
           'informacao_de_evento': ('esquerda', 'meio'), 'logo_de_parceiro': ('esquerda', 'base'),
           'logo_principal': ('direita', 'base'), 'url_ou_contato': ('direita', 'topo')}
    return 1600, 900, cams, fun, anc


def _kv_denso():
    """KV vertical 1080 x 1920 com foto, titulo, 14 linhas de informacao, 6 icones iguais, a marca e o legal colado."""
    cams = [(1, 'pixel', [0, 0, 1080, 1920], None), (2, 'pixel', [600, 1100, 1080, 1920], None),
            (3, 'texto', [80, 80, 1000, 300], 120)]
    fun = {1: 'fundo', 2: 'sujeito', 3: 'titulo'}
    lid = 10
    for k in range(14):
        cams.append((lid, 'texto', [80, 340 + 70 * k, 560, 390 + 70 * k], 30))
        fun[lid] = 'informacao_de_evento'
        lid += 1
    for k in range(6):
        cams.append((lid, 'pixel', [80 + 80 * k, 1360, 140 + 80 * k, 1420], None))
        fun[lid] = 'grafismo'
        lid += 1
    cams += [(lid, 'pixel', [80, 1700, 400, 1800], None), (lid + 1, 'texto', [60, 1880, 1020, 1900], 12)]
    fun[lid], fun[lid + 1] = 'logo_principal', 'texto_legal'
    anc = {'fundo': ('centro', 'meio'), 'sujeito': ('direita', 'base'), 'titulo': ('esquerda', 'topo'),
           'informacao_de_evento': ('esquerda', 'meio'), 'grafismo': ('esquerda', 'meio'),
           'logo_principal': ('esquerda', 'base'), 'texto_legal': ('centro', 'base')}
    return 1080, 1920, cams, fun, anc


def _kv_a(formatos):
    laudo, funcoes, ancoras, _fmts = tgg.kv_a()
    b = ap.briefing(funcoes=funcoes, regras=tgg.REGRAS, ancoras=ancoras,
                    formatos=[ap.formato(i, w, h) for i, w, h in formatos])
    ctx = nd.contexto(laudo, b)
    r = nd.derivar_em_memoria(ctx, specs={})
    return ctx, r['kv'], {f['id']: f for f in b['formatos']}


def _kv_h(formatos):
    laudo, funcoes = tg._kv_horizontal()
    b = ap.briefing(funcoes=funcoes, formatos=[ap.formato(i, w, h) for i, w, h in formatos])
    ctx = nd.contexto(laudo, b)
    r = nd.derivar_em_memoria(ctx, specs={})
    return ctx, r['kv'], {f['id']: f for f in b['formatos']}


def _asset(kv, e_id, caixa):
    """A borda do asset do elemento no formato (a caixa visivel mais o que passa da prancheta no KV)."""
    e = next(x for x in kv['elementos'] if x['id'] == e_id)
    m, am = e['caixa'], e.get('caixa_asset') or e['caixa']
    s = (caixa[2] - caixa[0]) / (m[2] - m[0])
    return [caixa[k] + s * (am[k] - m[k]) for k in range(4)]


# ------------------------------------------------------------------ a foto que sangra em dois lados opostos
def test_foto_que_sangra_em_cima_e_embaixo_fica_limpa_na_banda():
    """Achado 1 do revisor de codigo: a banda de lado centrava a foto que sangra em cima e embaixo dentro da area
    util, com o corte a vista; so o solver a levava as bordas, e quando ele nao fechava ficavam a validacao_reprova do
    enquadramento e o solver_nao_fecha (no 800 x 600 e no 300 x 250, nenhuma banda limpa). Agora ela ja sai do fluxo
    passando das duas bordas, e as versoes com a foto ao lado saem limpas."""
    ctx, kv, fs = _job(1920, 1080, _com_sujeito([1200, 0, 1700, 1080]), FUNCOES_H, ANCORAS_H,
                       [('p800x600', 800, 600), ('r300x250', 300, 250)])
    for fid, f in fs.items():
        cf = mg._contexto(ctx, kv, f)
        for lado in ('esq', 'dir'):
            v = mg.gerar(cf, mg.parametros_do_id('figura_%s' % lado))
            a = _asset(kv, 'el2', v['caixas']['el2'])
            assert a[1] <= 0.0 and a[3] >= f['altura'], (fid, lado, a)
        vs = mg.variantes(ctx, kv, f)
        bandas = [v for v in vs if v['estrutura']['figura'] in ('esq', 'dir')]
        assert bandas, (fid, [v['id'] for v in vs])
        for v in bandas:
            assert not v['falhas_obrigatorias'], (fid, v['id'], v['falhas_obrigatorias'])
            c = next(e['caixa'] for e in v['elementos'] if e['id'] == 'el2')
            a = _asset(kv, 'el2', c)
            assert a[1] <= 0.0 and a[3] >= f['altura'], (fid, v['id'], a)


def test_banda_do_lado_oposto_ao_corte_nao_existe():
    """Achado 1: a banda que deixa a vista o corte do lado oposto (a foto que sangra embaixo posta na banda de cima;
    a que sangra a esquerda e a direita posta numa banda de lado) nao gera candidata."""
    ctx, kv, fs = _job(1920, 1080, _com_sujeito([1200, 0, 1700, 1080]), FUNCOES_H, ANCORAS_H, [('q1080', 1080, 1080)])
    cf = mg._contexto(ctx, kv, fs['q1080'])
    for lado in ('topo', 'base'):
        assert mg.gerar(cf, mg.parametros_do_id('figura_%s' % lado)) is None, lado
    ctx, kv, fs = _job(1920, 1080, _com_sujeito([0, 60, 1920, 1080]), FUNCOES_H, ANCORAS_H, [('w970x250', 970, 250)])
    cf = mg._contexto(ctx, kv, fs['w970x250'])
    for lado in ('esq', 'dir', 'topo'):
        assert mg.gerar(cf, mg.parametros_do_id('figura_%s' % lado)) is None, lado


def test_falha_prevista_conta_o_lado_que_sangra_sem_passar_da_borda():
    """Achado 1: falhas_previstas nao conferia o lado que sangra, e a candidata com o corte a vista entrava com zero
    falha prevista. Descer a foto da banda (o topo dela fica dentro da peca) soma uma falha prevista."""
    ctx, kv, fs = _job(1920, 1080, _com_sujeito([1200, 0, 1700, 1080]), FUNCOES_H, ANCORAS_H, [('w970x250', 970, 250)])
    cf = mg._contexto(ctx, kv, fs['w970x250'])
    v = mg.gerar(cf, mg.parametros_do_id('figura_dir'))
    antes = mg.falhas_previstas(cf, v['caixas'], v['sangra'])
    c = v['caixas']['el2']
    desce = 0.2 * cf['H']
    caixas = dict(v['caixas'], el2=[c[0], c[1] + desce, c[2], c[3] + desce])
    assert mg.falhas_previstas(cf, caixas, v['sangra']) >= antes + 1


def test_foto_que_nao_cabe_em_banda_fica_de_fundo_com_versoes_limpas():
    """Achado 1 (e o 2): a foto que cobre quase o KV todo (sangra a esquerda, a direita e embaixo) nao cabe em banda
    nenhuma no 728 x 90. A galeria abre com uma versao limpa, de 3 versoes para cima (antes: 3 bandas com o corte a
    vista e nenhuma limpa)."""
    ctx, kv, fs = _job(1920, 1080, _com_sujeito([0, 60, 1920, 1080]), FUNCOES_H, ANCORAS_H, [('b728x90', 728, 90)])
    vs = mg.variantes(ctx, kv, fs['b728x90'])
    assert 3 <= len(vs) <= limites.valor('derivacao.galeria_variantes_max'), [v['id'] for v in vs]
    assert not vs[0]['falhas_obrigatorias'], (vs[0]['id'], vs[0]['falhas_obrigatorias'])
    assert all(v['estrutura']['figura'] is None for v in vs)


# ------------------------------------------------------------------ o lote do solver
def test_versao_limpa_fora_do_primeiro_lote_entra(monkeypatch):
    """Achado 2: as versoes com falha do primeiro lote completavam o minimo e o laco parava; a limpa que vinha depois
    nunca chegava ao solver. Aqui so a ultima candidata limpa enviada fica sem falha (as outras ganham uma falha de
    teste), e ela abre a galeria."""
    ctx, kv, fs = _kv_a([('q1080', 1080, 1080)])
    f = fs['q1080']
    cf = mg._contexto(ctx, kv, f)
    cands = []
    for p in mg._parametros(cf):
        v = mg.gerar(cf, p)
        if v is not None:
            v['nota_previa'] = mg.nota(cf, v, mg.falhas_previstas(cf, v['caixas'], v['sangra']))
            v['id'] = mg._id(p)
            cands.append(v)
    cands.sort(key=lambda v: -v['nota_previa'])
    duplicada = limites.valor('derivacao.galeria_duplicada_distancia_max')
    enviadas = []
    for v in cands:
        if not any(mg.distancia(cf, v, k) < duplicada for k in enviadas):
            enviadas.append(v)
    lote = int(limites.valor('derivacao.galeria_candidatas_ao_solver'))
    limpas = [k for k, v in enumerate(enviadas) if not mg._saida(cf, mg._resolvida(cf, v), 0)['falhas_obrigatorias']]
    assert limpas and limpas[-1] >= lote, (len(enviadas), limpas)
    alvo = enviadas[limpas[-1]]['id']
    real = mg._saida

    def saida(cf_, r, ordem):
        out = real(cf_, r, ordem)
        if r['id'] != alvo:
            out['falhas_obrigatorias'] = out['falhas_obrigatorias'] + [mg._item('teste', 'Falha de teste.', [])]
        return out
    monkeypatch.setattr(mg, '_saida', saida)
    vs = mg.variantes(ctx, kv, f)
    assert vs[0]['id'] == alvo and not vs[0]['falhas_obrigatorias'], [v['id'] for v in vs]


# ------------------------------------------------------------------ o tempo
def test_particao_guardada_pelo_tamanho_da_area(monkeypatch):
    """Achado 3: a chave do cache da particao tinha a posicao da area, e cada banda, imagem livre ou faixa refazia a
    mesma conta. Duas areas do mesmo tamanho em lugares diferentes fazem a particao uma vez so."""
    ctx, kv, fs = _kv_a([('q1080', 1080, 1080)])
    cf = mg._contexto(ctx, kv, fs['q1080'])
    contas = []
    real = mg._particao_calc

    def conta(*args):
        contas.append(1)
        return real(*args)
    monkeypatch.setattr(mg, '_particao_calc', conta)
    idx = list(range(len(cf['an']['atomos'])))
    cap = limites.valor('derivacao.galeria_teto_sobre_regra') * cf['regra_ref']
    um = mg._particao(cf, cf['an'], idx, [60.0, 60.0, 500.0, 1020.0], cap, 'melhor', False, None)
    outro = mg._particao(cf, cf['an'], idx, [580.0, 60.0, 1020.0, 1020.0], cap, 'melhor', False, None)
    assert len(contas) == 1 and um[1] == outro[1]


def test_kv_denso_em_menos_de_2_s():
    """Achado 3: a previa de um KV vertical denso (17 atomos com foto) passava de 2 s no 728 x 90."""
    ctx, kv, fs = _job(*_kv_denso(), [('b728x90', 728, 90), ('faixa', 1920, 192), ('w970x250', 970, 250)],
                       regras=dict(REGRAS, texto_legal='altura'))
    mg.variantes(ctx, kv, fs['w970x250'])  # aquecimento
    for fid, f in fs.items():
        t0 = time.perf_counter()
        vs = mg.variantes(ctx, kv, f)
        t = time.perf_counter() - t0
        assert vs and t < ORCAMENTO_S, (fid, t)


# ------------------------------------------------------------------ o piso da 133 e o arredondamento
@SEM_CARTAZ
def test_arredondamento_das_caixas_nao_fura_o_piso():
    """Achado 4: a escala colocada um fio acima do piso (folga de 1e-6) caia abaixo dele quando _elementos arredonda a
    caixa a 4 casas, e a conferencia acusava "fica com 50% da escala prevista, abaixo do minimo de 50%" no cartaz em
    160 x 600."""
    ctx = nd.contexto(KC.laudo(), KC.briefing([('s160x600', 160, 600)]))
    r = nd.derivar_em_memoria(ctx, specs={})
    kv, f = r['kv'], ctx['briefing']['formatos'][0]
    piso = limites.valor('derivacao.escala_conteudo_min_da_regra')
    for v in mg.variantes(ctx, kv, f):
        assert all(x['codigo'] != 'abaixo_do_piso_da_regra' for x in v['falhas_obrigatorias']), v['id']
        cx = {e['id']: e for e in v['elementos']}
        for e in kv['elementos']:
            if ms.conteudo(e):
                regra = mesc.escala(e['regra'], (kv['largura'], kv['altura']), (f['largura'], f['altura']))
                assert cx[e['id']]['escala'] >= piso * regra, (v['id'], e['id'])


def test_frase_do_piso_nunca_diz_o_proprio_minimo():
    """Achado 4: a fracao um fio abaixo do piso arredondava para o proprio minimo na frase do DA. Fica um ponto
    abaixo."""
    ctx, kv, fs = _kv_a([('w970x250', 970, 250)])
    f = fs['w970x250']
    v = mg.variantes(ctx, kv, f)[0]
    piso = limites.valor('derivacao.escala_conteudo_min_da_regra')
    regra = mesc.escala('altura', (kv['largura'], kv['altura']), (f['largura'], f['altura']))
    e = next(x for x in kv['elementos'] if x['funcao'] == 'cta')
    escala = piso * regra * (1.0 - 1e-5)
    m = e['caixa']
    els = [dict(x, caixa=[x['caixa'][0], x['caixa'][1], x['caixa'][0] + (m[2] - m[0]) * escala,
                          x['caixa'][1] + (m[3] - m[1]) * escala]) if x['id'] == e['id'] else x for x in v['elementos']]
    falhas = mg.conferir(ctx, kv, f, els)['falhas_obrigatorias']
    textos = [x['texto'] for x in falhas if x['codigo'] == 'abaixo_do_piso_da_regra']
    assert textos == ['A chamada fica com 49% da escala prevista, abaixo do mínimo de 50%.'], textos
    falha = next(x for x in falhas if x['codigo'] == 'abaixo_do_piso_da_regra')
    cf = mg.contexto_do_formato(ctx, kv, f)
    _ficam, decisoes = mg.decisoes_do_da(cf, [falha], [e['id']])
    assert decisoes[0]['texto'] == 'A chamada fica com 49% da escala prevista. O mínimo é 50%.', decisoes


# ------------------------------------------------------------------ a margem e o minimo de versoes
def test_conteudo_no_meio_do_kv_nao_vira_margem():
    """Achado 5: com um titulo so, centrado no KV 1920 x 1080, a margem do quadro (a menor distancia de um item a
    borda) virava 400 px no quadrado 1080; o conteudo ia ao piso, duas versoes saiam iguais e a galeria ficava com 2."""
    camadas = [(1, 'pixel', [0, 0, 1920, 1080], None), (3, 'texto', [600, 400, 1300, 600], 120)]
    ctx, kv, fs = _job(1920, 1080, camadas, {1: 'fundo', 3: 'titulo'},
                       {'fundo': ('centro', 'meio'), 'titulo': ('centro', 'meio')}, [('q1080', 1080, 1080)])
    f = fs['q1080']
    cf = mg._contexto(ctx, kv, f)
    assert cf['quadro'][0] <= limites.valor('derivacao.galeria_margem_max_lado_curto') * 1080 + FOLGA
    vs = mg.variantes(ctx, kv, f)
    assert limites.valor('derivacao.galeria_variantes_min') <= len(vs), [v['id'] for v in vs]


def test_aviso_diz_a_escala_que_a_versao_mostra():
    """Achado menor: o aviso dizia "o conteudo so cabe com 39%" numa versao que mostra o conteudo a 50%, porque o
    piso por bloco o sobe. Agora diz que o conteudo ficou no minimo e passa do espaco livre."""
    ctx, kv, fs = _kv_a([('v1080x1920', 1080, 1920)])
    textos = [a['texto'] for v in mg.variantes(ctx, kv, fs['v1080x1920']) for a in v['avisos']
              if a['codigo'] == 'conteudo_nao_cabe']
    assert textos
    for t in textos:
        assert t == ('O conteúdo fica no mínimo de 50% da escala prevista e passa do espaço livre. Vale ver se '
                     'algum texto secundário pode sair.'), t


# ------------------------------------------------------------------ a nota
def test_foto_no_meio_do_kv_nao_tem_lado():
    """Achado menor: a foto centrada no KV contava como a direita (comparacao com <), e a nota punia a banda da
    esquerda sem motivo. A mesma candidata com a foto de um lado ou do outro tem a mesma nota."""
    ctx, kv, fs = _job(1920, 1080, _com_sujeito([760, 200, 1160, 1080]), FUNCOES_H,
                       dict(ANCORAS_H, sujeito=('centro', 'base')), [('w970x250', 970, 250)])
    cf = mg._contexto(ctx, kv, fs['w970x250'])
    v = mg.gerar(cf, mg.parametros_do_id('figura_esq'))
    outro = dict(v, p=dict(v['p'], fig=('x', 'dir')))
    assert mg.nota(cf, v, 0) == pytest.approx(mg.nota(cf, outro, 0), abs=1e-12)


# ------------------------------------------------------------------ o solver
def test_bloco_que_o_solver_esmaga_e_falha(monkeypatch):
    """Achado 1 do revisor geral: o icone que o solver levava a 2 px so pesava na nota, e a versao saia limpa e em
    primeiro. Agora o bloco esmagado e falha, com a frase para o DA."""
    ctx, kv, fs = _kv_a([('w970x250', 970, 250)])
    real = mg._resolver

    def esmaga(cf, caixas, sangra):
        cx, falha = real(cf, caixas, sangra)
        c = cx['el5']
        return dict(cx, el5=[c[0], c[1], c[0] + 2.0, c[1] + 2.0]), falha
    monkeypatch.setattr(mg, '_resolver', esmaga)
    vs = mg.variantes(ctx, kv, fs['w970x250'])
    for v in vs:
        f = [x for x in v['falhas_obrigatorias'] if x['codigo'] == 'bloco_esmagado']
        assert f and f[0]['elementos'] == ['el5'], (v['id'], v['falhas_obrigatorias'])
        assert f[0]['texto'] == 'Nesta versão, o ajuste final encolhe demais o grafismo.'


# ------------------------------------------------------------------ o vao da 135 entre a foto e o conteudo
def test_vao_da_135_usa_a_escala_do_fluxo():
    """Achado 2 do revisor geral: a escala que da o vao da 135 entre a foto e o conteudo comecava na regra e so subia;
    no KV A em 1080 x 1920 a regra e 1,78 e o fluxo fica em 0,89, e o vao saia 557 px no lugar de 372 (o conteudo
    preso no piso com o espaco vazio). O vao fica perto do que a escala do fluxo pede, sem ficar abaixo dele."""
    ctx, kv, fs = _kv_a([('v1080x1920', 1080, 1920)])
    cf = mg._contexto(ctx, kv, fs['v1080x1920'])
    fx = cf['_figura']
    ins = cf['an']['margem_rel'] * min(cf['W'], cf['H'])
    for vid in ('figura_base', 'figura_base__outra_estrutura'):
        v = mg.gerar(cf, mg.parametros_do_id(vid))
        fig = v['fig_caixa']
        s_fig = (fig[2] - fig[0]) / (fx['caixa'][2] - fx['caixa'][0])
        esc = mg._escalas(kv, v['caixas'])
        maior = max(esc[e['id']] for e in kv['elementos'] if mg.em_fluxo(e))
        pede = mg._vao_135(cf, {fx['id']: fig}, s_fig, maior, ins)
        vao = fig[1] - v['q'][3]
        assert pede * (1.0 - FOLGA) <= vao <= 1.1 * pede, (vid, vao, pede)


# ------------------------------------------------------------------ a hierarquia com regras diferentes
def test_legal_de_regra_constante_nao_prende_o_titulo():
    """Achado 3 do revisor geral: o fluxo poe uma escala so, e o legal de regra constante (regra 1, contra 5,09 do
    titulo no 1080 x 1920) ficava a 3,16 vezes a regra dele, com a largura dele prendendo o titulo a 0,62 da regra.
    Cada bloco cresce sobre a regra dele: o titulo nunca fica abaixo dos outros textos sobre a regra, e a primeira
    versao da ao titulo pelo menos 0,8 da regra (a galeria de antes de 19/11 dava 0,84 e 0,79)."""
    ctx, kv, fs = _kv_h([('alto', 1080, 1920), ('v', 300, 600)])
    for fid, f in fs.items():
        vs = mg.variantes(ctx, kv, f)
        for v in vs:
            rel = {e['funcao']: e['escala'] / e['escala_regra'] for e in v['elementos']
                   if e['escala_regra'] and ms.conteudo(e)}
            assert all(rel['titulo'] >= x - FOLGA for k, x in rel.items() if k != 'titulo'), (fid, v['id'], rel)
            if v is vs[0]:
                assert rel['titulo'] >= 0.8, (fid, rel)


# ------------------------------------------------------------------ a fileira empilhada
def test_fileira_empilhada_nao_vira_escada():
    """Achado 4 do revisor geral: ao empilhar a fileira de 3 icones, cada um guardava o x que tinha no KV e o conjunto
    virava uma diagonal (x 60, 129 e 210). Os itens que ficavam lado a lado no KV e agora vao um embaixo do outro
    comecam no mesmo x."""
    ctx, kv, fs = _kv_a([('q1080', 1080, 1080)])
    cf = mg._contexto(ctx, kv, fs['q1080'])
    icones = [e['id'] for e in kv['elementos'] if e['funcao'] == 'grafismo']
    vistos = 0
    for p in mg._parametros(cf):
        v = mg.gerar(cf, p)
        if v is None:
            continue
        cx = [v['caixas'][k] for k in icones]
        # um embaixo do outro: nenhum par divide a mesma faixa de altura
        empilhados = all(a[3] <= b[1] or b[3] <= a[1] for k, a in enumerate(cx) for b in cx[k + 1:])
        if empilhados:
            vistos += 1
            assert max(c[0] for c in cx) - min(c[0] for c in cx) <= FOLGA, (mg._id(p), cx)
    assert vistos


# ------------------------------------------------------------------ a frase para o DA
def test_frase_concorda_com_o_genero_do_rotulo():
    """Achado menor do revisor geral: "com as informacoes um embaixo do outro" passa a "uma embaixo da outra"."""
    ctx, kv, fs = _job(*_kv_c(), [('q1080', 1080, 1080)])
    frases = [v['descricao'] for v in mg.variantes(ctx, kv, fs['q1080'])]
    assert any('com as informações uma embaixo da outra' in x for x in frases), frases
    assert not any('as informações um embaixo do outro' in x for x in frases), frases


# ------------------------------------------------------------------ a arte livre
def test_arte_livre_nao_passa_por_baixo_do_conteudo():
    """Achado menor do revisor geral: no KV H em 1080 x 1920, a arte livre crescia para cobrir a largura e passava de
    80% da altura, por baixo do conteudo. O que sobra dela sai pelo lado de fora da peca."""
    ctx, kv, fs = _kv_h([('alto', 1080, 1920)])
    f = fs['alto']
    vs = [v for v in mg.variantes(ctx, kv, f) if v['estrutura']['imagem_livre']]
    assert vs
    for v in vs:
        cx = {e['id']: e['caixa'] for e in v['elementos']}
        arte = cx['el80']
        for e in kv['elementos']:
            if mg.em_fluxo(e) and ms.conteudo(e):
                c = cx[e['id']]
                inter = max(0.0, min(c[2], arte[2]) - max(c[0], arte[0])) * \
                    max(0.0, min(c[3], arte[3]) - max(c[1], arte[1]))
                assert inter <= FOLGA, (v['id'], e['id'], c, arte)
        assert math.isclose(arte[2] - arte[0], f['largura'], rel_tol=1e-9) or arte[2] - arte[0] > f['largura']


def test_a_impressao_da_familia_conta_so_se_ha_galeria():
    """A lista de versoes da galeria nova depende da medida do conteudo: a quebra de linha aprovada pelo DA troca a
    lista depois do "Salvar e seguir" (o roteiro do editor de mestre, test_editor_mestre). A impressao da familia
    (desdobra.tela.estado.impressao_das_pecas) conta so se a galeria existe; a lista trocada nao derruba a familia."""
    from desdobra.tela import estado as te
    formatos = {'f1': {'situacao': 'derivado'}}
    antes = te.impressao_das_pecas(['f1'], formatos, ['a', 'b', 'c'])
    assert te.impressao_das_pecas(['f1'], formatos, ['a', 'b__c', 'd']) == antes
    assert te.impressao_das_pecas(['f1'], formatos, []) != antes
