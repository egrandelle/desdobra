# -*- coding: utf-8 -*-
"""M7b, D5: o piso de distancia e de escala diante da intencao do DA (pergunta 10 do plano do M7b, resposta
recomendada adotada; decisoes-v1.md, 133, 135 e 167), escrito antes do codigo.

Criterios de pronto cobertos aqui:
  - o elemento que o DA mexeu ou escalou no palco e fura o piso de escala (133) ou de distancia (135) contra a mestre
    verdadeira deixa de "pedir ajuste": a conferencia o separa como decisao do DA (decisoes_do_da), com o valor a
    vista (a porcentagem da escala, ou a distancia e o minimo em px);
  - o elemento que o solver mexeu continua marcado como falha, tambem quando o par dele tem um elemento do DA;
  - a validacao obrigatoria do motor continua devolvendo o formato, com ou sem decisao do DA;
  - a derivacao da familia confirmada registra a decisao do DA (registro decisao_do_da) no lugar de proposta_com_falha;
  - a previa da tela leva decisoes_do_da por membro, sem a falha;
  - na tela (Chromium sem janela): a assinatura a 155% e mais perto do titulo sai com a marca "Decisao do DA" e o valor
    a vista, sem "Pede ajuste";
  - revisao 1 da fase D: o piso que a versao de partida ja furava continua pedindo ajuste quando o DA so anda ou
    alinha o elemento, e a sobreposicao nunca vira decisao com distancia negativa.
Tudo sintetico: laudo montado a mao, PSD sintetico gerado na hora e a fonte de autoteste do motor."""
import pytest

import test_derivacao_apoio as ap
from desdobra import contratos, limites
from desdobra.briefing import modelo as mb
from desdobra.derivacao import galeria as mg
from desdobra.derivacao import nucleo as nd
from desdobra.derivacao import proposta
from desdobra.derivacao import solver as mod_solver
from test_tela_escala import conteudo_escala, job_escala  # noqa: F401 - o job sintetico com a assinatura

CONF = {'origem': 'fixture_de_teste', 'meio': 'medicao', 'em': '2026-11-11T10:00:00-03:00'}
PISO = ('abaixo_do_piso_da_regra', 'distancia_menor_que_na_mestre')

# KV sintetico 400 x 200: fundo, titulo e apoio a esquerda, a assinatura embaixo do apoio e um produto a direita. A
# distancia da assinatura ao apoio na mestre e 46 px (o vizinho de conteudo mais perto na altura)
FUNDO, TITULO, APOIO, ASSINATURA, PRODUTO = 1, 10, 20, 30, 41
CAIXAS_KV = {FUNDO: [0, 0, 400, 200], TITULO: [24, 30, 220, 62], APOIO: [24, 74, 200, 94],
             ASSINATURA: [24, 140, 84, 170], PRODUTO: [300, 40, 340, 170]}
TIPOS = {FUNDO: 'pixel', TITULO: 'texto', APOIO: 'texto', ASSINATURA: 'smart_embutido', PRODUTO: 'pixel'}
CORPOS = {TITULO: 28, APOIO: 12}
FUN = {FUNDO: 'fundo', TITULO: 'titulo', APOIO: 'texto_de_apoio', ASSINATURA: 'logo_principal', PRODUTO: 'sujeito'}
A, T, P = 'el%d' % ASSINATURA, 'el%d' % TITULO, 'el%d' % APOIO
FAMILIAS = {'horizontal': [('h1', 800, 400), ('h2', 840, 420)]}
# o criterio do plano: a assinatura a 155% (crescendo para cima, a partir da base a esquerda) e mais perto do apoio
PERTO = [{'elemento': A, 'acao': 'escalar', 'fator': 1.55, 'fx': 0, 'fy': 1},
         {'elemento': A, 'acao': 'mover', 'dx': 0, 'dy': -0.04}]
# a assinatura encolhida pelo DA abaixo do piso de escala da 133
PEQUENA = [{'elemento': A, 'acao': 'escalar', 'fator': 0.3, 'fx': 0, 'fy': 1}]


def _laudo():
    return ap.laudo(400, 200, [ap.camada(k, TIPOS[k], CAIXAS_KV[k], corpo=CORPOS.get(k)) for k in sorted(CAIXAS_KV)])


def _briefing(edicoes):
    formatos = [ap.formato(i, w, h) for fs in FAMILIAS.values() for i, w, h in fs]
    b = ap.briefing(funcoes=FUN, formatos=formatos)
    b['composicoes'] = [{'familia': g, 'formatos': [i for i, _w, _h in fs], 'versao': None, 'edicoes': list(edicoes),
                         'confirmada': True, 'confirmacao': dict(CONF)} for g, fs in FAMILIAS.items()]
    return b


def _derivar(edicoes):
    b = _briefing(edicoes)
    contratos.validar(b, mb.ESQUEMA)
    assert mb.conferir(_laudo(), b) == []
    ctx = nd.contexto(_laudo(), b)
    return ctx, nd.derivar_em_memoria(ctx, specs={})['formatos']


def _layout(edicoes, fid='h1'):
    """O layout do membro fid com as edicoes, como a previa e a derivacao o montam (proposta.layout_do_membro)."""
    ctx, antes = _derivar([])
    kv = nd.mestre_do_kv(ctx)
    f = next(x for x in ctx['briefing']['formatos'] if x['id'] == fid)
    cf = mg.contexto_do_formato(ctx, proposta.mestre_do_membro(ctx, kv, f, antes[fid]), f, specs={})
    extra = {'kv_por_id': {e['id']: e for e in kv['elementos']},
             'conteudo': [e['id'] for e in kv['elementos'] if mod_solver.conteudo(e)],
             'kv_caixas': {e['id']: [float(x) for x in e['caixa']] for e in kv['elementos']},
             'kv_tamanho': (float(kv['largura']), float(kv['altura']))}
    return proposta.layout_do_membro(cf, antes[fid]['elementos'], edicoes, **extra)


def _codigos(itens):
    return [(x['codigo'], sorted(x['elementos'])) for x in itens]


# ------------------------------------------------------------------ a conta, no layout do membro
def test_distancia_que_o_da_pediu_vira_decisao_do_da_com_o_valor_a_vista():
    lay = _layout(PERTO)
    assert not [f for f in lay['falhas'] if f['codigo'] in PISO], lay['falhas']
    dec = [d for d in lay['decisoes_do_da'] if d['codigo'] == 'distancia_menor_que_na_mestre']
    assert len(dec) == 1 and sorted(dec[0]['elementos']) == sorted([A, P]), lay['decisoes_do_da']
    m = dec[0]['medidas']
    assert m['distancia_px'] < m['minimo_px'], m
    # o valor a vista: a distancia de agora e o minimo, em px, no texto que o DA le
    texto = dec[0]['texto']
    for v in (m['distancia_px'], m['minimo_px']):
        assert mg._numero(v) + ' px' in texto, texto
    assert texto in ('A marca e o texto ficam a %s px um do outro. O KV pede pelo menos %s px.' % (
        mg._numero(m['distancia_px']), mg._numero(m['minimo_px'])),
        'O texto e a marca ficam a %s px um do outro. O KV pede pelo menos %s px.' % (
        mg._numero(m['distancia_px']), mg._numero(m['minimo_px']))), texto
    assert '—' not in texto and '–' not in texto


def test_escala_que_o_da_deu_abaixo_do_piso_vira_decisao_do_da_com_a_porcentagem():
    lay = _layout(PEQUENA)
    assert not [f for f in lay['falhas'] if f['codigo'] in PISO], lay['falhas']
    dec = [d for d in lay['decisoes_do_da'] if d['codigo'] == 'abaixo_do_piso_da_regra']
    assert len(dec) == 1 and dec[0]['elementos'] == [A], lay['decisoes_do_da']
    fr = dec[0]['medidas']['fracao_da_regra']
    piso = limites.valor('derivacao.escala_conteudo_min_da_regra')
    assert fr < piso
    assert dec[0]['medidas']['minimo_da_regra'] == piso
    assert dec[0]['texto'] == 'A marca fica com %d%% da escala prevista. O mínimo é %d%%.' % (
        round(fr * 100), round(piso * 100))  # numero-neutro: porcentagem


def test_sem_edicao_do_da_nao_ha_decisao_do_da():
    lay = _layout([])
    assert lay['decisoes_do_da'] == []


def _solver_que_mexe(monkeypatch, mexer):
    real = mg.reencaixar

    def falso(cf_, caixas, sangra, apagados=(), do_da=()):
        cs, falha = real(cf_, caixas, sangra, apagados, do_da)
        return mexer({k: list(v) for k, v in cs.items()}), falha
    monkeypatch.setattr(mg, 'reencaixar', falso)


def test_elemento_que_o_solver_aproximou_continua_pedindo_ajuste(monkeypatch):
    # o DA so anda o produto um pouco; o solver (aqui de mentira) desce o apoio para perto da assinatura: nenhum dos
    # dois foi mexido pelo DA, entao a distancia continua uma falha
    def desce_o_apoio(cs):
        c = cs[P]
        alvo = cs[A][1] - 4.0  # numero-neutro: px acima do topo da assinatura
        d = alvo - c[3]
        cs[P] = [c[0], c[1] + d, c[2], c[3] + d]
        return cs
    _solver_que_mexe(monkeypatch, desce_o_apoio)
    lay = _layout([{'elemento': 'el%d' % PRODUTO, 'acao': 'mover', 'dx': -0.01, 'dy': 0}])
    assert ('distancia_menor_que_na_mestre', sorted([A, P])) in _codigos(lay['falhas']), lay['falhas']
    assert lay['decisoes_do_da'] == []


def test_par_com_um_elemento_do_da_e_outro_do_solver_continua_pedindo_ajuste(monkeypatch):
    # o DA aproxima a assinatura, e o solver (de mentira) ainda desce o apoio 6 px: o apoio foi mexido pelo solver
    def desce_6(cs):
        c = cs[P]
        cs[P] = [c[0], c[1] + 6.0, c[2], c[3] + 6.0]  # numero-neutro: px do empurrao de mentira
        return cs
    _solver_que_mexe(monkeypatch, desce_6)
    lay = _layout(PERTO)
    assert ('distancia_menor_que_na_mestre', sorted([A, P])) in _codigos(lay['falhas']), lay['falhas']
    assert not [d for d in lay['decisoes_do_da'] if d['codigo'] == 'distancia_menor_que_na_mestre']


def test_escala_que_o_solver_encolheu_continua_pedindo_ajuste(monkeypatch):
    # o solver (de mentira) encolhe o titulo, que o DA nao mexeu, abaixo do piso de escala
    def encolhe_o_titulo(cs):
        c = cs[T]
        cs[T] = [c[0], c[1], c[0] + (c[2] - c[0]) * 0.3, c[1] + (c[3] - c[1]) * 0.3]  # numero-neutro: fator de mentira
        return cs
    _solver_que_mexe(monkeypatch, encolhe_o_titulo)
    lay = _layout([{'elemento': A, 'acao': 'mover', 'dx': 0.01, 'dy': 0}])
    assert ('abaixo_do_piso_da_regra', [T]) in _codigos(lay['falhas']), lay['falhas']
    assert lay['decisoes_do_da'] == []


def test_so_o_piso_vira_decisao_do_da():
    # a sobreposicao, o fora do quadro e a validacao do motor continuam falhas, mesmo com o elemento do DA
    falhas = [{'codigo': 'sobreposicao_nova', 'texto': 'x', 'elementos': [A, P]},
              {'codigo': 'fora_do_quadro', 'texto': 'x', 'elementos': [A]},
              {'codigo': 'validacao_reprova', 'texto': 'x', 'elementos': [A], 'medidas': {'validacao': 'inventario'}},
              {'codigo': 'distancia_menor_que_na_mestre', 'texto': 'x', 'elementos': [A, P],
               'medidas': {'distancia_px': 20.0, 'minimo_px': 30.0}}]
    ctx, _ = _derivar([])
    kv = nd.mestre_do_kv(ctx)
    f = next(x for x in ctx['briefing']['formatos'] if x['id'] == 'h1')
    cf = mg.contexto_do_formato(ctx, kv, f, specs={})
    ficam, decisoes = mg.decisoes_do_da(cf, falhas, do_da=[A], do_solver=[])
    assert [x['codigo'] for x in ficam] == ['sobreposicao_nova', 'fora_do_quadro', 'validacao_reprova']
    assert [x['codigo'] for x in decisoes] == ['distancia_menor_que_na_mestre']
    assert decisoes[0]['texto'] == 'A marca e o texto ficam a 20 px um do outro. O KV pede pelo menos 30 px.'


# ------------------------------------------------------------------ revisao 1 da fase D
def _layout_de(elementos, edicoes, fid='h1'):
    """O layout do membro fid com as edicoes, partindo dos elementos dados (a versao de onde o membro parte)."""
    ctx, antes = _derivar([])
    kv = nd.mestre_do_kv(ctx)
    f = next(x for x in ctx['briefing']['formatos'] if x['id'] == fid)
    cf = mg.contexto_do_formato(ctx, proposta.mestre_do_membro(ctx, kv, f, antes[fid]), f, specs={})
    extra = {'kv_por_id': {e['id']: e for e in kv['elementos']},
             'conteudo': [e['id'] for e in kv['elementos'] if mod_solver.conteudo(e)],
             'kv_caixas': {e['id']: [float(x) for x in e['caixa']] for e in kv['elementos']},
             'kv_tamanho': (float(kv['largura']), float(kv['altura']))}
    return proposta.layout_do_membro(cf, elementos, edicoes, **extra)


def _partida_com_a_assinatura_a(fracao):
    """Os elementos da proposta de h1 com a assinatura a fracao do tamanho dela, presa no canto de baixo a esquerda:
    a versao de onde o membro parte ja fura o piso de escala ("Pede ajuste" na galeria)."""
    import copy
    _ctx, antes = _derivar([])
    els = copy.deepcopy(antes['h1']['elementos'])
    for e in els:
        if e['id'] == A:
            c = [float(v) for v in e['caixa']]
            e['caixa'] = [c[0], c[3] - fracao * (c[3] - c[1]), c[0] + fracao * (c[2] - c[0]), c[3]]
    return els


@pytest.mark.parametrize('edicoes', [
    [{'elemento': A, 'acao': 'mover', 'dx': 1 / 800, 'dy': 0}],
    [{'elemento': A, 'acao': 'alinhar', 'alvo': 'margem_esquerda', 'referencia': 'margem'}],
], ids=['mover_1px', 'alinhar'])
def test_piso_que_ja_vinha_da_partida_continua_pedindo_ajuste(edicoes):
    # o DA so anda ou alinha a assinatura pequena da versao de partida; ele nunca a escalou: o piso furado e do motor
    lay = _layout_de(_partida_com_a_assinatura_a(0.3), edicoes)
    assert ('abaixo_do_piso_da_regra', [A]) in _codigos(lay['falhas']), lay['falhas']
    assert not [d for d in lay['decisoes_do_da'] if d['codigo'] == 'abaixo_do_piso_da_regra'], lay['decisoes_do_da']


def test_escala_que_o_da_deu_sobre_a_partida_boa_continua_decisao_dele():
    # a mesma partida, sem a assinatura pequena: o DA a encolhe a 30% e a decisao e dele
    lay = _layout_de(_partida_com_a_assinatura_a(1.0), PEQUENA)
    assert [d['codigo'] for d in lay['decisoes_do_da']] == ['abaixo_do_piso_da_regra'], lay['decisoes_do_da']


def test_sobreposicao_nunca_vira_decisao_do_da_com_distancia_negativa():
    # o DA anda o produto para cima do titulo e do apoio: a sobreposicao pede ajuste, sem distancia negativa a vista
    lay = _layout([{'elemento': 'el%d' % PRODUTO, 'acao': 'mover', 'dx': -0.3, 'dy': 0.0}])
    assert 'sobreposicao_nova' in [f['codigo'] for f in lay['falhas']], lay['falhas']
    assert not [d for d in lay['decisoes_do_da'] if d['medidas'].get('distancia_px', 1) <= 0], lay['decisoes_do_da']
    assert not [d for d in lay['decisoes_do_da'] if '-' in d['texto']], lay['decisoes_do_da']
    # o mesmo par nunca leva "Pede ajuste" e "Decisão do DA" juntos
    pares_falha = {tuple(sorted(f['elementos'])) for f in lay['falhas']}
    assert not [d for d in lay['decisoes_do_da'] if tuple(sorted(d['elementos'])) in pares_falha]


# ------------------------------------------------------------------ a derivacao da familia confirmada
def test_derivacao_registra_a_decisao_do_da_no_lugar_da_falha():
    _ctx, depois = _derivar(PERTO)
    for fs in FAMILIAS.values():
        for fid, _w, _h in fs:
            d = depois[fid]
            assert d['situacao'] == 'derivado', (fid, d.get('devolucao'))
            codigos = [r['codigo'] for r in d['registros']]
            assert 'proposta_com_falha' not in codigos, d['registros']
            reg = [r for r in d['registros'] if r['codigo'] == 'decisao_do_da']
            assert len(reg) == 1, d['registros']
            dec = reg[0]['medidas']['decisoes']
            assert [x['codigo'] for x in dec] == ['distancia_menor_que_na_mestre'], dec
            assert sorted(dec[0]['elementos']) == sorted([A, P])
            assert dec[0]['medidas']['distancia_px'] < dec[0]['medidas']['minimo_px']


def test_validacao_obrigatoria_continua_devolvendo_o_formato_com_decisao_do_da(monkeypatch):
    real = mg.validacoes_do_layout

    def reprova(cf, caixas, sangra, apagados=()):
        vs = real(cf, caixas, sangra, apagados)
        return vs + [{'nome': 'colisao_nova_contra_a_origem', 'situacao': 'reprova',
                      'fonte': {'tipo': 'mestre', 'ref': None}, 'elementos': [A]}]
    monkeypatch.setattr(mg, 'validacoes_do_layout', reprova)
    _ctx, depois = _derivar(PERTO)
    for fs in FAMILIAS.values():
        for fid, _w, _h in fs:
            d = depois[fid]
            assert d['situacao'] == 'devolvido', fid
            assert d['devolucao']['motivo'] == 'validacao_obrigatoria_reprovou', d['devolucao']


def test_derivacao_com_decisao_do_da_e_deterministica():
    _c1, a = _derivar(PERTO)
    _c2, b = _derivar(PERTO)
    for fid in a:
        ra = [r for r in a[fid]['registros'] if r['codigo'] == 'decisao_do_da']
        rb = [r for r in b[fid]['registros'] if r['codigo'] == 'decisao_do_da']
        assert ra == rb and [e['caixa'] for e in a[fid]['elementos']] == [e['caixa'] for e in b[fid]['elementos']]


# ------------------------------------------------------------------ a previa no job sintetico com a assinatura
def _familia(conteudo):
    return next(g for g, f in conteudo['familias'].items() if 'h1' in f['formatos'])


def _perto_do_titulo(eid):
    # a assinatura (no canto de baixo a esquerda do KV) a 155%, crescendo para cima, e subida para perto do titulo
    return [{'elemento': eid, 'acao': 'escalar', 'fator': 1.55, 'fx': 0, 'fy': 1},
            {'elemento': eid, 'acao': 'mover', 'dx': 0, 'dy': -0.25}]


def test_previa_da_tela_leva_a_decisao_do_da_sem_pedir_ajuste(job_escala, conteudo_escala):  # noqa: F811
    eid = job_escala['assinatura']
    gid = _familia(conteudo_escala)
    r = conteudo_escala['editar']({'familia': gid, 'versao': None, 'edicoes': _perto_do_titulo(eid)})
    assert r['membros']
    for m in r['membros']:
        assert not [f for f in m['falhas'] if f['codigo'] in PISO], (m['formato'], m['falhas'])
        dec = [d for d in m['decisoes_do_da'] if d['codigo'] == 'distancia_menor_que_na_mestre']
        assert len(dec) == 1 and eid in dec[0]['elementos'], (m['formato'], m['decisoes_do_da'])
        assert ' px' in dec[0]['texto'] and 'O KV pede pelo menos' in dec[0]['texto'], dec[0]['texto']
    # sem edicao, nenhuma decisao do DA
    base = conteudo_escala['editar']({'familia': gid, 'versao': None, 'edicoes': []})
    assert all(m['decisoes_do_da'] == [] for m in base['membros'])


# ------------------------------------------------------------------ a tela no Chromium sem janela (modo de teste)
def test_decisao_do_da_na_tela_do_chromium(job_escala, conteudo_escala):  # noqa: F811
    from playwright.sync_api import sync_playwright

    import test_tela_galeria as tg
    import test_tela_grupo as tgr
    import test_tela_palco as tp
    from test_tela_escala import _digitar
    from desdobra.chromium import navegador
    from desdobra.tela import atos as ta
    from desdobra.tela import servidor as ts
    job, eid = job_escala['job'], job_escala['assinatura']
    tgr._limpar_rascunho(job)
    estado = conteudo_escala['estado']
    gid = _familia(conteudo_escala)
    titulo = next(e['id'] for e in conteudo_escala['editar']({'familia': gid, 'versao': None, 'edicoes': []})
                  ['membros'][0]['palco']['elementos'] if e.get('funcao') == 'titulo')
    salvo = '() => (document.documentElement.dataset.rascunho === "salvo" && ' \
            'document.documentElement.dataset.previa === "pronta") ? "1" : ""'
    marcas = '''() => Array.from(document.querySelectorAll('#membros-lista .membro')).map(b => ({
        formato: b.dataset.formato, marcas: Array.from(b.querySelectorAll('.marca-aviso')).map(s => s.textContent),
        titulos: Array.from(b.querySelectorAll('.marca-aviso')).map(s => s.title),
        rotulo: b.getAttribute('aria-label')}))'''
    avisos = '''() => Array.from(document.querySelectorAll('#variante-palco .var-palco-aviso'))
        .map(s => [s.textContent, s.className])'''
    navegador.apontar_playwright()
    with ts.ServidorTela(conteudo_escala, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo_escala)) as srv, sync_playwright() as pw:
        nav, pg = tp._pagina_da_tela(pw, srv, 2048, 720)  # numero-neutro: a tela do Duda (decisao 157)
        try:
            tg._abrir(pg, estado, 'h1')
            tp._esperar(pg, '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""')
            # o DA escolhe a assinatura, digita 155 e a arrasta para cima, ate perto do titulo
            x, y = tgr._ponto(pg, eid)
            pg.mouse.click(x, y)
            _digitar(pg, '155')
            tp._esperar(pg, salvo)
            caixa_t = pg.evaluate('''i => { const r = document.querySelector('#palco .rotulo[data-elemento="' + i +
                '"]').getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; }''', titulo)
            caixa_a = pg.evaluate('''i => { const r = document.querySelector('#palco .rotulo[data-elemento="' + i +
                '"]').getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; }''', eid)
            # o topo da assinatura a um quinto da distancia de antes ate a base do titulo
            sobe = (caixa_a[1] - caixa_t[3]) * 0.8  # numero-neutro: fracao do caminho ate o titulo
            x, y = tgr._ponto(pg, eid)
            pg.mouse.move(x, y)
            pg.mouse.down()
            pg.mouse.move(x, y - sobe, steps=6)
            pg.mouse.up()
            tp._esperar(pg, salvo)
            eds = tgr._edicoes(job, gid)
            assert [e['acao'] for e in eds] == ['escalar', 'mover'], eds
            # cada arquivo da familia: a marca "Decisao do DA", com o valor no title, e nunca "Pede ajuste"
            lista = pg.evaluate(marcas)
            assert lista
            for b in lista:
                assert 'Pede ajuste' not in b['marcas'], b
                assert 'Decisão do DA' in b['marcas'], b
                t = b['titulos'][b['marcas'].index('Decisão do DA')]
                assert ' px' in t and 'O KV pede pelo menos' in t, t
                assert 'decisão do DA' in b['rotulo'] and 'pede ajuste' not in b['rotulo'], b['rotulo']
            # o palco do arquivo aberto diz a decisao com o valor a vista
            av = pg.evaluate(avisos)
            assert any(' px' in t and 'do-da' in c for t, c in av), av
            assert not any('forte' in c for _t, c in av), av
            texto = pg.evaluate(tp.JS_TEXTO_DA_MOLDURA)
            assert not tp.IDENTIFICADOR.findall(texto), tp.IDENTIFICADOR.findall(texto)
            assert '—' not in texto and '–' not in texto
        finally:
            nav.close()
        contagem = dict(srv.contagem)
    assert contagem['proibido'] == 0 and contagem['csrf_recusado'] == 0 and contagem['dado_recusado'] == 0
    tgr._limpar_rascunho(job)
