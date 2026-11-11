# -*- coding: utf-8 -*-
"""Revisao 2 da fase D do M7b: os defeitos que a segunda revisao achou, escritos antes do codigo.

Criterios cobertos aqui:
  - alinhar no quadro: a "Área segura" do membro sem area segura na folha e a margem dele (como a pagina diz); o
    elemento que so encosta na borda da peca continua na linha do grupo, e o segundo clique ou o alinhamento firmado
    depois do solver nunca levam o grupo para fora da peca;
  - o tamanho: o fator forjado que passa do teto numerico em algum passo (1e308 e 1e-308, 1e-200 e 1e200) e recusado
    pela previa, pelo rascunho e pelas pendencias, mesmo quando o produto final da 1; o rascunho gravado antes do D3,
    com o tamanho fora dos limites, nunca trava "Salvar e seguir";
  - a sangria do DA: o elemento que fica inteiro fora da peca nao sangra (pede ajuste, e a validacao devolve o
    formato); o grupo que passa da borda por menos que a tolerancia do enquadramento fica inteiro, como o DA o deixou;
    o lado que so a versao da galeria sangrava (a borda do asset e inteira no KV) nao vira corte a vista;
  - a intencao de alinhamento (168): o elemento que nao foi mexido e que divide uma linha do KV com outro continua
    nela (o packshot nao se desmonta quando o DA anda a assinatura); o resultado nao depende da ordem dos cliques no
    grupo.
Tudo sintetico: laudo montado a mao, PSD sintetico gerado na hora e a fonte de autoteste do motor."""
import itertools
import math

import pytest

import test_derivacao_apoio as ap
import test_tela_alinhar as tal
import test_tela_escala as tes
import test_tela_grupo as tgr
import test_tela_sangria as tsg
from desdobra import contratos
from desdobra.briefing import modelo as mb
from desdobra.derivacao import galeria as mg
from desdobra.derivacao import nucleo as nd
from desdobra.derivacao import proposta
from desdobra.derivacao import solver as mod_solver
from desdobra.tela import edicao as ed
from desdobra.tela import rascunho as tr
from test_tela_escala import conteudo_escala, job_escala  # noqa: F401 - o packshot com a assinatura
from test_tela_salvar import job, modelo  # noqa: F401 - o job sintetico de "Salvar e seguir"

CONF = {'origem': 'fixture_de_teste', 'meio': 'medicao', 'em': '2026-11-11T10:00:00-03:00'}
TOL = 0.5  # numero-neutro: px de folga do arredondamento da derivacao


# ------------------------------------------------------------------ alinhar no quadro
def test_area_segura_sem_folha_e_a_margem_do_membro():
    cf = {'W': 1000.0, 'H': 500.0, 'quadro': [50.0, 40.0, 950.0, 460.0], 'areas': {}}
    assert proposta.quadros_do_membro(cf)['area_segura'] == [50.0, 40.0, 950.0, 460.0]
    # a area util sozinha tambem nao e area segura: a pagina so liga "Área segura" com area segura na folha
    util = dict(cf, areas={'area_util': {'caixa': [10.0, 10.0, 990.0, 490.0]}})
    assert proposta.quadros_do_membro(util)['area_segura'] == [50.0, 40.0, 950.0, 460.0]
    com = dict(cf, areas={'area_segura': {'caixa': [20.0, 20.0, 980.0, 480.0]}})
    assert proposta.quadros_do_membro(com)['area_segura'] == [20.0, 20.0, 980.0, 480.0]


def test_alinhar_de_novo_na_borda_da_peca_nao_tira_o_grupo_dela():
    caixas = {'t': [24.0, 40.0, 200.0, 72.0], 'i': [52.0, 124.0, 72.0, 144.0]}
    um = [{'elemento': 't', 'elementos': ['t', 'i'], 'acao': 'alinhar', 'alvo': 'margem_esquerda',
           'referencia': 'area_segura'}]
    q = {'margem': [20.0, 10.0, 380.0, 190.0], 'area_segura': [0.0, 0.0, 400.0, 200.0]}
    c1 = ed.aplicar(caixas, um, 400, 200, q)[0]
    c2 = ed.aplicar(caixas, um + um, 400, 200, q)[0]
    firmado = ed.firmar(c1, ed.intencoes(um), q, 400, 200)[0]
    for c in (c1, c2, firmado):
        assert c['t'][0] == pytest.approx(0.0) and c['i'][0] == pytest.approx(28.0), c


def test_derivacao_alinha_pela_area_segura_sem_folha_na_margem_de_cada_membro():
    eds = [{'elemento': tal.BLOCO[0], 'elementos': tal.BLOCO, 'acao': 'alinhar', 'alvo': 'margem_esquerda',
            'referencia': 'area_segura'}]
    ctx, depois = tal._derivar(eds)
    for fs in tal.FAMILIAS.values():
        for fid, _w, _h in fs:
            d = depois[fid]
            assert d['situacao'] == 'derivado', (fid, d.get('devolucao'))
            u = tal._uniao([tal._caixas(d)[k] for k in tal.BLOCO])
            assert u[0] == pytest.approx(tal._quadro_do_membro(ctx, fid)[0], abs=TOL), (fid, u)


# ------------------------------------------------------------------ o tamanho com fatores forjados
@pytest.mark.parametrize('par', [(1e308, 1e-308), (1e-200, 1e200), (1e-308, 1e308)],
                         ids=['infinito', 'some', 'some_primeiro'])
def test_escala_fora_recusa_o_passo_que_passa_do_teto(par):
    eds = [{'elemento': 'a', 'acao': 'escalar', 'fator': par[0]}, {'elemento': 'a', 'acao': 'escalar', 'fator': par[1]}]
    assert ed.escala_fora(eds) == ['a']
    # nem o rascunho gravado (as pendencias conferem as edicoes contra elas mesmas) deixa passar
    assert ed.escala_fora(eds, antes=eds) == ['a']


def test_escala_fora_deixa_o_caminho_da_tela():
    # o rascunho de antes do D3 (0,45 x 0,45) e o conserto pela tela continuam passando
    velhas = [{'elemento': 'a', 'acao': 'escalar', 'fator': 0.45}, {'elemento': 'a', 'acao': 'escalar', 'fator': 0.45}]
    assert ed.escala_fora(velhas, antes=velhas) == []
    assert ed.escala_fora(velhas + [{'elemento': 'a', 'acao': 'escalar', 'fator': 2.0}], antes=velhas) == []
    # o caminho de dois passos dentro do teto, com o tamanho final dentro dos limites
    assert ed.escala_fora([{'elemento': 'a', 'acao': 'escalar', 'fator': 0.2},
                           {'elemento': 'a', 'acao': 'escalar', 'fator': 2.0}]) == []


@pytest.mark.parametrize('par', [(1e308, 1e-308), (1e-200, 1e200)], ids=['infinito', 'some'])
def test_rascunho_e_previa_recusam_fatores_que_se_cancelam(job_escala, conteudo_escala, par):  # noqa: F811
    jb, a = job_escala['job'], job_escala['assinatura']
    gid = tes._familia(conteudo_escala)
    laudo = tr.laudo_sha256(jb)
    job_id = conteudo_escala['estado']['job_id']
    eds = [{'elemento': a, 'acao': 'escalar', 'fator': par[0]}, {'elemento': a, 'acao': 'escalar', 'fator': par[1]}]
    try:
        with pytest.raises(tr.ErroRascunho) as erro:
            tr.gravar(jb, {'job_id': job_id, 'laudo_sha256': laudo,
                           'familias': {gid: {'versao': None, 'confirmada': False, 'edicoes': eds}}},
                      job_id=job_id, laudo_atual=laudo, origem='rascunho', elementos_da_tela=conteudo_escala['elementos'])
        assert erro.value.motivo == 'escala'
        assert conteudo_escala['editar']({'familia': gid, 'versao': None, 'edicoes': eds}) is None
        # nem com as edicoes gravadas como "antes" (o caminho das pendencias)
        assert conteudo_escala['editar']({'familia': gid, 'versao': None, 'edicoes': eds}, antes=eds) is None
    finally:
        tgr._limpar_rascunho(jb)


def test_rascunho_de_antes_dos_limites_salva_e_segue(job, modelo, monkeypatch):  # noqa: F811
    """O rascunho com o titulo a 20% (a tela de antes do D3) abre, a familia confirma, e as pendencias de "Salvar e
    seguir" nao o recusam: o job nunca trava."""
    import test_tela_salvar as tsv
    import test_tela_servidor as tts
    from desdobra.briefing import salvar as bs
    from desdobra.tela import estado as te
    conteudo = te.montar(job)
    s = tsv._servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        escolhas = tsv._preparar_rascunho(job, modelo, s, biscoito, conteudo)
        gv = tsv._familia_de(conteudo, 'v1')
        tit = tsv._titulo(conteudo, gv)
        velhas = escolhas[gv]['edicoes'] + [{'elemento': tit, 'acao': 'escalar', 'fator': 0.45, 'fx': 0, 'fy': 0}] * 2
        escolhas = {g: dict(f, confirmada=False) for g, f in escolhas.items()}
        escolhas[gv]['edicoes'] = velhas
        with monkeypatch.context() as m:  # o arquivo como a tela de antes do D3 o gravou
            m.setattr(ed, 'escala_fora', lambda edicoes, antes=None: [])
            assert tsv._gravar_rascunho(s, biscoito, escolhas, tsv._passo_2(modelo['funcoes'])) == 200  # numero-neutro: HTTP
        for g, f in escolhas.items():
            assert tsv._ato(s, biscoito, 'familia', {'familia': g, 'versao': f['versao'],
                                                     'edicoes': f['edicoes']})[1] == 200, g  # numero-neutro: HTTP
        assert {'codigo': 'edicao_invalida', 'familia': gv} not in bs.pendencias(job, conteudo)
    finally:
        s.parar()


# ------------------------------------------------------------------ a sangria do DA
def _falhas_do_membro(edicoes, fid):
    """O layout do membro fid da familia do D4 (test_tela_sangria) com as edicoes, como a previa e a derivacao."""
    b = tsg._briefing([])
    ctx = nd.contexto(tsg._laudo(), b)
    antes = nd.derivar_em_memoria(ctx, specs={})['formatos']
    return _layout(ctx, antes, fid, edicoes)


def _layout(ctx, antes, fid, edicoes, elementos=None):
    kv = nd.mestre_do_kv(ctx)
    f = next(x for x in ctx['briefing']['formatos'] if x['id'] == fid)
    cf = mg.contexto_do_formato(ctx, proposta.mestre_do_membro(ctx, kv, f, antes.get(fid)), f, specs={})
    extra = {'kv_por_id': {e['id']: e for e in kv['elementos']},
             'conteudo': [e['id'] for e in kv['elementos'] if mod_solver.conteudo(e)],
             'kv_caixas': {e['id']: [float(x) for x in e['caixa']] for e in kv['elementos']},
             'kv_tamanho': (float(kv['largura']), float(kv['altura']))}
    return proposta.layout_do_membro(cf, elementos if elementos is not None else antes[fid]['elementos'], edicoes,
                                     **extra)


@pytest.mark.parametrize('edicoes, ids', [
    ([{'elemento': tsg.PRODUTOS[-1], 'acao': 'mover', 'dx': 0.6, 'dy': 0.0}], [tsg.PRODUTOS[-1]]),
    ([{'elemento': tsg.GRUPO[0], 'elementos': tsg.GRUPO, 'acao': 'mover', 'dx': 0.0, 'dy': 0.8}], tsg.GRUPO),
], ids=['lata', 'packshot'])
def test_elemento_inteiro_fora_da_peca_pede_ajuste(edicoes, ids):
    depois = tsg._derivar(edicoes)
    for fid, w, h in tsg.HORIZONTAIS:
        d = depois[fid]
        por_id = {e['id']: e for e in d['elementos']}
        for k in ids:
            assert not por_id[k].get('sangria_do_da'), (fid, k, por_id[k].get('sangria_do_da'))
        # o formato volta ao DA: a validacao obrigatoria reprova o enquadramento, e a falha diz o que aconteceu
        assert d['situacao'] == 'devolvido', (fid, d['situacao'], [r['codigo'] for r in d['registros']])
        lay = _falhas_do_membro(edicoes, fid)
        fora = [f for f in lay['falhas'] if f['codigo'] == 'fora_do_quadro']
        assert sorted(k for f in fora for k in f['elementos']) == sorted(ids), lay['falhas']
        assert all('Apagar' in f['texto'] for f in fora), fora
        # a caixa fica onde o DA a pos: a previa mostra o que ele fez
        esperado = ed.aplicar(tsg._caixas(nd.derivar_em_memoria(nd.contexto(tsg._laudo(), tsg._briefing([])),
                                                                specs={})['formatos'][fid]), edicoes, w, h)[0]
        for k in ids:
            assert lay['caixas'][k] == pytest.approx(esperado[k], abs=TOL), (fid, k)


def test_grupo_que_passa_um_px_da_borda_fica_inteiro():
    eds = [{'elemento': tsg.GRUPO[0], 'elementos': tsg.GRUPO, 'acao': 'escalar', 'fator': 1.9, 'fx': 0.5, 'fy': 1.0}]
    antes = tsg._derivar([])
    depois = tsg._derivar(eds)
    for fid, w, h in tsg.HORIZONTAIS:
        esperado = ed.aplicar(tsg._caixas(antes[fid]), eds, w, h)[0]
        cx = tsg._caixas(depois[fid])
        for k in tsg.GRUPO:
            assert cx[k] == pytest.approx(esperado[k], abs=TOL), (fid, k, cx[k], esperado[k])
        assert len({round(cx[k][3], 1) for k in tsg.PRODUTOS}) == 1, (fid, [cx[k] for k in tsg.PRODUTOS])


# a arte da faixa (_arte_em_banda): na versao da galeria, a foto sangra a esquerda; no KV, a borda esquerda dela e
# inteira (o asset nao acaba ali)
FOTO = 60
CAIXAS_FOTO = {10: [20, 30, 104, 62], 20: [20, 82, 114, 98], 30: [22, 120, 72, 140], FOTO: [200, 0, 400, 200]}
TIPOS_FOTO = {10: 'texto', 20: 'texto', 30: 'smart_embutido', FOTO: 'pixel'}
FUN_FOTO = {1: 'fundo', 10: 'titulo', 20: 'texto_de_apoio', 30: 'logo_principal', FOTO: 'imagem'}


def test_arte_da_faixa_tirada_do_lado_que_so_a_versao_sangrava_nao_e_corte():
    camadas = [ap.camada(1, 'pixel', [0, 0, 400, 200])]
    camadas += [ap.camada(k, TIPOS_FOTO[k], c, corpo={10: 28, 20: 12}.get(k)) for k, c in sorted(CAIXAS_FOTO.items())]
    laudo = ap.laudo(400, 200, camadas)
    b = ap.briefing(funcoes=FUN_FOTO, formatos=[ap.formato('v1', 300, 600)])
    ctx = nd.contexto(laudo, b)
    kv = nd.mestre_do_kv(ctx)
    foto = 'el%d' % FOTO
    assert next(e for e in kv['elementos'] if e['id'] == foto)['sangra']['esq'] is False
    f = ctx['briefing']['formatos'][0]
    por = proposta.galeria_da_familia(ctx, kv, [f], specs={}, arquivo_specs=None, params=None)
    # a versao em que a foto vai para a faixa e sangra a esquerda so nela
    versao = next(v for _n, v in por['v1'] if next(e for e in v['elementos'] if e['id'] == foto)
                  ['transformacao']['sangra']['esq'])
    sem = _layout(ctx, {'v1': {'situacao': 'devolvido'}}, 'v1', [], versao['elementos'])
    com = _layout(ctx, {'v1': {'situacao': 'devolvido'}}, 'v1', [{'elemento': foto, 'acao': 'mover', 'dx': 0.05,
                                                                  'dy': 0.0}], versao['elementos'])
    assert not [x for x in com['falhas'] if x['codigo'] == 'corte_a_mostra'], com['falhas']
    assert com['reprovadas'] == sem['reprovadas'], (sem['reprovadas'], com['reprovadas'])
    # a foto fica onde o DA a pos
    assert com['caixas'][foto][0] == pytest.approx(15.0, abs=TOL), com['caixas'][foto]


# ------------------------------------------------------------------ a intencao de alinhamento (168)
# KV B sintetico 400 x 200 montado a mao: titulo, linha, apoio, dois icones e a assinatura a esquerda; o packshot a
# direita (circulo de fundo, garrafa, copo e lata com a base na mesma linha)
FUNDO, TIT, LIN, APO, IC1, IC2, ASS, CIR, GAR, COP, LAT = 1, 10, 12, 20, 50, 51, 30, 40, 41, 42, 43
CAIXAS_B = {TIT: [20, 30, 104, 62], LIN: [22, 70, 102, 74], APO: [20, 82, 114, 98], IC1: [22, 112, 42, 132],
            IC2: [50, 112, 70, 132], ASS: [22, 168, 72, 188], CIR: [250, 70, 380, 200], GAR: [268, 80, 298, 200],
            COP: [306, 136, 332, 200], LAT: [340, 124, 366, 200]}
TIPOS_B = {TIT: 'texto', APO: 'texto', ASS: 'smart_embutido'}
CORPOS_B = {TIT: 28, APO: 12}
FUN_B = {FUNDO: 'fundo', TIT: 'titulo', LIN: 'grafismo', APO: 'texto_de_apoio', IC1: 'icone_de_cta',
         IC2: 'icone_de_cta', ASS: 'logo_principal', CIR: 'grafismo', GAR: 'sujeito', COP: 'sujeito', LAT: 'sujeito'}
USADAS_B = {'fundo': ('cover', 'centro', 'meio'), 'titulo': ('raiz_area', 'esquerda', 'topo'),
            'texto_de_apoio': ('raiz_area', 'esquerda', 'meio'), 'logo_principal': ('raiz_area', 'direita', 'base'),
            'grafismo': ('contain', 'centro', 'meio'), 'icone_de_cta': ('raiz_area', 'esquerda', 'meio'),
            'sujeito': ('raiz_area', 'centro', 'meio')}
PRODUTOS_B = ['el%d' % k for k in (GAR, COP, LAT)]
PACK_B = PRODUTOS_B + ['el%d' % CIR]
FAMILIA_B = [('h1', 800, 400), ('h2', 840, 400), ('h3', 880, 400)]


def _contexto_b():
    camadas = [ap.camada(FUNDO, 'pixel', [0, 0, 400, 200])]
    camadas += [ap.camada(k, TIPOS_B.get(k, 'pixel'), CAIXAS_B[k], corpo=CORPOS_B.get(k)) for k in sorted(CAIXAS_B)]
    b = ap.briefing(funcoes=FUN_B, regras=dict(ap.REGRAS, **{f: r for f, (r, _x, _y) in USADAS_B.items()}),
                    ancoras=dict(ap.ANCORAS, **{f: (x, y) for f, (_r, x, y) in USADAS_B.items()}),
                    formatos=[ap.formato(i, w, h) for i, w, h in FAMILIA_B])
    contratos.validar(b, mb.ESQUEMA)
    ctx = nd.contexto(ap.laudo(400, 200, camadas), b)
    return ctx, nd.derivar_em_memoria(ctx, specs={})['formatos']


@pytest.mark.parametrize('edicoes', [
    [{'elemento': 'el%d' % ASS, 'acao': 'mover', 'dx': 0.0, 'dy': -0.06}],
    [{'elemento': 'el%d' % ASS, 'acao': 'escalar', 'fator': 1.5, 'fx': 0, 'fy': 1},
     {'elemento': 'el%d' % ASS, 'acao': 'mover', 'dx': 0.0, 'dy': -0.1}],
], ids=['subir', 'aumentar_e_subir'])
def test_mexer_na_assinatura_nao_desmonta_o_packshot(edicoes):
    ctx, antes = _contexto_b()
    for fid, _w, _h in FAMILIA_B:
        lay = _layout(ctx, antes, fid, edicoes)
        partida = tsg._caixas(antes[fid])
        for k in PACK_B:
            assert lay['caixas'][k] == pytest.approx(partida[k], abs=TOL), (fid, k, partida[k], lay['caixas'][k])
        assert not [a for a in lay['alinhados'] if set(a['elementos']) & set(PACK_B)], lay['alinhados']


def test_intencao_de_alinhamento_nao_depende_da_ordem_dos_cliques():
    # o icone i, que o DA nao mexeu, fica perto do topo de a (5 px) e do topo de b (3 px), dois do mesmo grupo
    caixas = {'a': [100.0, 100.0, 150.0, 150.0], 'b': [160.0, 92.0, 200.0, 152.0], 'i': [400.0, 95.0, 420.0, 120.0]}
    saidas = []
    for ordem in (['a', 'b'], ['b', 'a']):
        novas, _alinhados = ed.normalizar(caixas, ordem, 800, 400, grupos=[ordem])
        saidas.append(novas)
    assert saidas[0] == saidas[1], saidas
    assert saidas[0]['i'][1] == pytest.approx(92.0)  # a linha mais perto


@pytest.mark.parametrize('fator', [1.32, 1.34, 1.36])
def test_derivacao_do_grupo_nao_depende_da_ordem_dos_cliques(fator):
    ctx, antes = _contexto_b()
    resultados = set()
    for ordem in itertools.permutations(PACK_B):
        eds = [{'elemento': ordem[0], 'elementos': list(ordem), 'acao': 'escalar', 'fator': fator, 'fx': 0.5,
                'fy': 1.0}]
        lay = _layout(ctx, antes, 'h1', eds)
        resultados.add(tuple(tuple(round(v, 2) for v in lay['caixas'][k]) for k in sorted(lay['caixas'])))
    assert len(resultados) == 1


def test_fatores_dentro_do_teto_deixam_a_caixa_finita():
    eds = [{'elemento': 'a', 'acao': 'escalar', 'fator': 0.2}, {'elemento': 'a', 'acao': 'escalar', 'fator': 2.0}]
    c = ed.aplicar({'a': [100.0, 100.0, 200.0, 200.0]}, eds, 800, 400)[0]['a']
    assert all(math.isfinite(v) for v in c) and c[2] > c[0]


# ================================================================== a tela (Chromium sem janela)
MSG = '() => document.getElementById("ed-mensagem").textContent'
CAMPO = '() => document.getElementById("ed-tamanho").value'
JS_MEDIDAS = """() => {
  const n = document.getElementById('elemento-escolhido');
  const p = document.getElementById('palco').getBoundingClientRect();
  return {barra: Math.round(document.getElementById('barra-edicao').getBoundingClientRect().height),
          palco: [Math.round(p.top), Math.round(p.height)], cortada: n.scrollWidth > n.clientWidth + 1,
          texto: n.textContent};
}"""


def _tela(conteudo, job, largura, altura):
    import test_tela_revisao_d as trd
    return trd._tela(conteudo, job, largura, altura)


def _esperar_edicoes(pg, job, gid, n):
    """Espera o rascunho com n edicoes da familia (mais ou menos que antes) e a pagina pronta."""
    import time

    import test_tela_palco as tp
    import test_tela_revisao_d as trd
    fim = time.monotonic() + 30  # numero-neutro: segundos de teto do teste
    while len(tgr._edicoes(job, gid)) != n:
        assert time.monotonic() < fim, tgr._edicoes(job, gid)
        pg.wait_for_timeout(100)  # numero-neutro: ms, intervalo do teste
    tp._esperar(pg, trd.SALVO)
    return tgr._edicoes(job, gid)


def _tamanho(pg, valor):
    pg.fill('#ed-tamanho', valor)
    pg.press('#ed-tamanho', 'Enter')


@pytest.mark.parametrize('janela', [(1280, 800), (2048, 720)], ids=['1280x800', '2048x720'])
def test_ajuda_cabe_e_como_editar_mostra_todos_os_gestos(job_escala, conteudo_escala, janela):  # noqa: F811
    job = job_escala['job']
    with _tela(conteudo_escala, job, *janela) as (_srv, pg, _gid):
        pg.keyboard.press('Escape')
        antes = pg.evaluate(JS_MEDIDAS)
        assert not antes['cortada'], antes
        # "Como editar" abre a lista dos gestos por cima do palco: nada na barra nem no palco muda de lugar
        pg.click('#ed-ajuda')
        assert pg.evaluate('() => document.getElementById("ed-ajuda").getAttribute("aria-expanded")') == 'true'
        painel = pg.evaluate("""() => { const p = document.getElementById('ed-ajuda-painel');
          const b = p.getBoundingClientRect();
          return {visivel: !p.hidden && b.height > 0, dentro: b.left >= 0 && b.top >= 0 &&
                  b.right <= innerWidth && b.bottom <= innerHeight, texto: p.textContent}; }""")
        assert painel['visivel'] and painel['dentro'], painel
        for parte in ('Shift', 'Escolher vários', 'retângulo', 'Tamanho', 'Alinhar', 'Ctrl+Z', 'família'):
            assert parte in painel['texto'], (parte, painel['texto'])
        assert pg.evaluate(JS_MEDIDAS)['barra'] == antes['barra']
        assert pg.evaluate(JS_MEDIDAS)['palco'] == antes['palco']
        pg.keyboard.press('Escape')
        assert pg.evaluate('() => document.getElementById("ed-ajuda-painel").hidden') is True


def test_ctrl_z_no_campo_tamanho_desfaz_a_edicao(job_escala, conteudo_escala):  # noqa: F811
    job, a = job_escala['job'], job_escala['assinatura']
    with _tela(conteudo_escala, job, 1600, 900) as (_srv, pg, gid):  # numero-neutro: janela do teste
        x, y = tgr._ponto(pg, a)
        pg.mouse.click(x, y)
        _tamanho(pg, '155')
        _esperar_edicoes(pg, job, gid, 1)
        assert pg.evaluate('() => document.activeElement.id') == 'ed-tamanho'
        pg.keyboard.press('Control+z')
        assert _esperar_edicoes(pg, job, gid, 0) == []
        assert pg.evaluate(CAMPO) == '100'


def test_foco_volta_ao_grupo_depois_de_desfazer(job_escala, conteudo_escala):  # noqa: F811
    job, grupo = job_escala['job'], job_escala['grupo']
    with _tela(conteudo_escala, job, 1600, 900) as (_srv, pg, gid):  # numero-neutro: janela do teste
        x, y = tgr._ponto(pg, grupo[0])
        pg.mouse.click(x, y)
        tgr._shift_clique(pg, grupo[1])
        pg.keyboard.press('ArrowLeft')
        _esperar_edicoes(pg, job, gid, 1)
        pg.click('#ed-desfazer')
        _esperar_edicoes(pg, job, gid, 0)
        pg.keyboard.press('ArrowLeft')
        eds = _esperar_edicoes(pg, job, gid, 1)
        assert eds[0]['acao'] == 'mover' and sorted(eds[0]['elementos']) == sorted(grupo[:2]), eds
        pg.keyboard.press('Escape')
        assert pg.evaluate(tgr.JS_ESCOLHIDOS) == []


def test_grupo_misto_confere_o_tamanho_de_cada_um(job_escala, conteudo_escala):  # noqa: F811
    job, a, copo = job_escala['job'], job_escala['assinatura'], job_escala['grupo'][1]
    with _tela(conteudo_escala, job, 1600, 900) as (_srv, pg, gid):  # numero-neutro: janela do teste
        x, y = tgr._ponto(pg, a)
        pg.mouse.click(x, y)
        _tamanho(pg, '300')
        _esperar_edicoes(pg, job, gid, 1)
        pg.keyboard.press('Escape')
        x, y = tgr._ponto(pg, copo)
        pg.mouse.click(x, y)
        _tamanho(pg, '150')
        _esperar_edicoes(pg, job, gid, 2)
        tgr._shift_clique(pg, a)
        assert pg.evaluate(CAMPO) == '100'
        # 20 do tamanho de agora: a assinatura fica com 60% e o copo com 30%, os dois dentro dos limites
        _tamanho(pg, '20')
        eds = _esperar_edicoes(pg, job, gid, 3)
        assert eds[2]['fator'] == 0.2 and sorted(eds[2]['elementos']) == sorted([a, copo]), eds
        # 10 levaria o copo a 15%, abaixo do limite: recusado
        _tamanho(pg, '10')
        pg.wait_for_timeout(600)  # numero-neutro: ms, mais que a espera do rascunho
        assert len(tgr._edicoes(job, gid)) == 3
        assert 'passaria do limite' in pg.evaluate(MSG)


@pytest.mark.parametrize('janela', [(1280, 800), (1366, 768)], ids=['1280x800', '1366x768'])
def test_barra_nao_muda_de_altura_com_a_frase(job_escala, conteudo_escala, janela):  # noqa: F811
    job, grupo = job_escala['job'], job_escala['grupo']
    with _tela(conteudo_escala, job, *janela) as (_srv, pg, gid):
        x, y = tgr._ponto(pg, grupo[0])
        pg.mouse.click(x, y)
        sem_frase = pg.evaluate(JS_MEDIDAS)
        _tamanho(pg, '120')
        _esperar_edicoes(pg, job, gid, 1)
        pg.wait_for_timeout(300)  # numero-neutro: ms, o palco se ajusta
        uma = pg.evaluate(JS_MEDIDAS)
        _tamanho(pg, '110')
        _esperar_edicoes(pg, job, gid, 2)
        pg.wait_for_timeout(300)  # numero-neutro: ms, o palco se ajusta
        duas = pg.evaluate(JS_MEDIDAS)
        assert len(pg.evaluate(MSG)) > 100  # numero-neutro: a frase longa do Tamanho
        assert sem_frase['barra'] == uma['barra'] == duas['barra'], (sem_frase, uma, duas)
        assert uma['palco'] == duas['palco'], (uma, duas)


JS_CURSOR_DA_ETIQUETA = """i => { const e = document.querySelector('#palco .rotulo[data-elemento="' + i + '"] .etiqueta');
  return getComputedStyle(e).cursor; }"""


def test_etiqueta_so_mostra_a_mao_de_arrastar_no_escolhido(job_escala, conteudo_escala):  # noqa: F811
    job, grupo = job_escala['job'], job_escala['grupo']
    with _tela(conteudo_escala, job, 1600, 900) as (_srv, pg, _gid):  # numero-neutro: janela do teste
        pg.keyboard.press('Escape')
        # a etiqueta de quem nao esta escolhido: o clique escolhe, e o arraste desenha o retangulo
        assert pg.evaluate(JS_CURSOR_DA_ETIQUETA, grupo[0]) not in ('grab', 'grabbing')
        x, y = tgr._ponto(pg, grupo[0])
        pg.mouse.click(x, y)
        assert pg.evaluate(JS_CURSOR_DA_ETIQUETA, grupo[0]) == 'grab'


def test_fechar_logo_depois_da_edicao_grava_o_rascunho(job_escala, conteudo_escala):  # noqa: F811
    import time
    job, grupo = job_escala['job'], job_escala['grupo']
    with _tela(conteudo_escala, job, 1600, 900) as (_srv, pg, gid):  # numero-neutro: janela do teste
        x, y = tgr._ponto(pg, grupo[0])
        pg.mouse.click(x, y)
        for eid in grupo[1:]:
            tgr._shift_clique(pg, eid)
        dialogos = []
        pg.on('dialog', lambda d: (dialogos.append(d.type), d.dismiss()))
        _tamanho(pg, '85')
        pg.wait_for_timeout(100)  # numero-neutro: ms, menos que a espera do rascunho
        assert pg.evaluate('() => document.documentElement.dataset.rascunho') == 'pendente'
        # enquanto espera, o selo diz que ainda esta salvando
        assert pg.evaluate('() => document.getElementById("selo").textContent') == 'Salvando no rascunho'
        pg.close(run_before_unload=True)
        fim = time.monotonic() + 5  # numero-neutro: segundos de teto do teste
        while not tgr._edicoes(job, gid) and time.monotonic() < fim:
            time.sleep(0.1)  # numero-neutro: segundos, intervalo do teste
        eds = tgr._edicoes(job, gid)
        assert len(eds) == 1 and eds[0]['fator'] == 0.85 and dialogos == [], (eds, dialogos)
