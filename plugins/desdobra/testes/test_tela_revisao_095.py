# -*- coding: utf-8 -*-
"""0.9.5: o que o DA nao mexeu fica parado, e o Tamanho vai ate 1000% (decisao do Duda em 17/11, depois do teste do
KV A na 0.9.4).

Caso: no 970x250 do KV A, o DA aumentou so o texto de apoio. O encaixe refeito pelo solver depois da edicao subia o
titulo e a barra do fundo junto, ate o titulo sair do formato; ao diminuir o texto, o titulo voltava. Isso contradizia
a decisao 185 (so o elemento que o DA acabou de mexer anda).

Criterios de pronto cobertos aqui:
  - depois de qualquer edicao do DA (escalar, mover, apagar, alinhar, texto), cada elemento que o DA nao mexeu fica
    com a caixa da versao de partida, em todo membro da familia; o motor nao reposiciona nada por conta propria;
  - quando o resultado sobrepoe elementos, sai do formato ou fica mais perto do que o KV pede, a previa avisa (falhas
    ou decisoes_do_da), e nada culpa o solver;
  - a previa e o "Salvar e seguir" dao o mesmo layout;
  - o tamanho vai de 25% a 1000% (tela.escala_max = 10): a previa e o rascunho aceitam 1000% e recusam acima.
Tudo sintetico: o KV A de testes/sinteticos/kv_a_b.py (o titulo empilhado sobre o texto de apoio), com o 970x250 do
relato, e a fonte de autoteste do motor."""
import inspect

import pytest

import test_tela_previa_igual_ao_salvar as tpi
from desdobra import limites
from desdobra.derivacao import galeria as mg
from desdobra.derivacao import proposta
from desdobra.tela import edicao as ed
from desdobra.tela import estado as te
from sinteticos import kv_a_b as kv

TOL = 0.01  # numero-neutro: px, o arredondamento da caixa
FORMATOS = [('f970x250', 970, 250), ('p1008', 1008, 432)]
F970 = 'f970x250'
ORIGEM = 'fixture_de_teste'
# os codigos com que a previa avisa que o resultado da edicao precisa do olhar do DA
AVISOS_DE_LUGAR = ('sobreposicao_nova', 'fora_do_quadro', 'fora_da_area_segura', 'distancia_menor_que_na_mestre',
                   'validacao_reprova')


def _job(base):
    with pytest.MonkeyPatch.context() as m:
        m.setattr(kv, 'FORMATOS', FORMATOS)
        return kv.criar_job(base, 'a')


@pytest.fixture(scope='module')
def job95(tmp_path_factory):
    return _job(tmp_path_factory.mktemp('revisao-095'))


@pytest.fixture(scope='module')
def conteudo95(job95):
    return te.montar(job95['job'])


def _el(j, papel):
    return 'el%d' % j['ids'][papel]


def _gid(conteudo, fid=F970):
    return next(g for g, f in conteudo['familias'].items() if fid in f['formatos'])


def _previa(conteudo, edicoes, fid=F970):
    r = conteudo['editar']({'familia': _gid(conteudo, fid), 'versao': None, 'edicoes': edicoes, 'quebras': []},
                           ORIGEM)
    assert r is not None, edicoes
    return r


def _caixas(previa):
    return {m['formato']: {e['id']: [float(x) for x in e['caixa']] for e in m['palco']['elementos']}
            for m in previa['membros'] if m.get('palco')}


def _confere_parados(antes, depois, mexidos, apagados=()):
    """Cada elemento que o DA nao mexeu fica com a caixa de antes, em todo membro."""
    ca, cd = _caixas(antes), _caixas(depois)
    assert sorted(ca) == sorted(cd)
    for fid, caixas in cd.items():
        assert sorted(caixas) == sorted(k for k in ca[fid] if k not in apagados), fid
        for k, c in caixas.items():
            if k in mexidos:
                continue
            assert c == pytest.approx(ca[fid][k], abs=TOL), (fid, k, ca[fid][k], c)


# ------------------------------------------------------------------ o caso do relato: o apoio maior no 970x250
def _apoio_maior(j, fator=3.0):
    # o apoio cresce em volta do meio dele, contra o titulo e para o lado do packshot. Na 0.9.4, o encaixe refeito
    # empurrava a assinatura e os produtos para a direita no 970x250, sem o DA mexer neles
    return [{'elemento': _el(j, 'apoio'), 'acao': 'escalar', 'fator': fator, 'fx': 0.5, 'fy': 0.5}]


def test_apoio_maior_deixa_o_titulo_e_o_fundo_onde_estavam(job95, conteudo95):
    antes = _previa(conteudo95, [])
    depois = _previa(conteudo95, _apoio_maior(job95))
    apoio = _el(job95, 'apoio')
    _confere_parados(antes, depois, [apoio])
    ca, cd = _caixas(antes)[F970], _caixas(depois)[F970]
    for papel in ('titulo', 'fundo'):
        assert cd[_el(job95, papel)] == pytest.approx(ca[_el(job95, papel)], abs=TOL), papel
    for papel in kv.PACKSHOT + ('assinatura',):
        assert cd[_el(job95, papel)] == pytest.approx(ca[_el(job95, papel)], abs=TOL), papel
    # o apoio cresceu 3 vezes (a intencao de alinhamento pode encaixar so ele numa linha vizinha, decisao 185)
    a0, a1 = ca[apoio], cd[apoio]
    assert a1[2] - a1[0] == pytest.approx(3.0 * (a0[2] - a0[0]), abs=TOL)


def _avisos(previa, fid=F970):
    m = next(x for x in previa['membros'] if x['formato'] == fid)
    codigos = [f['codigo'] for f in m['falhas']] + [d['codigo'] for d in m['decisoes_do_da']]
    # nada culpa o solver: sem encaixe refeito, o membro e a proposta com as edicoes do DA
    assert m['situacao'] == 'proposta'
    assert 'solver_nao_fecha' not in codigos
    assert 'não fecham' not in ' '.join(f['texto'] for f in m['falhas'])
    return m, codigos


def test_apoio_maior_que_passa_da_borda_avisa_e_nada_culpa_o_solver(job95, conteudo95):
    depois = _previa(conteudo95, _apoio_maior(job95))
    a = _caixas(depois)[F970][_el(job95, 'apoio')]
    assert a[0] < 0, a  # o apoio 3 vezes maior passa da borda esquerda do 970x250
    m, codigos = _avisos(depois)
    # o texto nunca sangra: a tela avisa que ele saiu do formato, e o DA decide
    assert 'fora_do_quadro' in codigos or 'validacao_reprova' in codigos, (m['falhas'], m['decisoes_do_da'])


def test_apoio_movido_sobre_o_titulo_avisa(job95, conteudo95):
    eds = [{'elemento': _el(job95, 'apoio'), 'acao': 'mover', 'dx': 0.0, 'dy': -0.2}]
    depois = _previa(conteudo95, eds)
    c = _caixas(depois)[F970]
    a, t = c[_el(job95, 'apoio')], c[_el(job95, 'titulo')]
    assert min(a[2], t[2]) > max(a[0], t[0]) and min(a[3], t[3]) > max(a[1], t[1]), (a, t)
    m, codigos = _avisos(depois)
    # a sobreposicao que a edicao do DA criou aparece para ele decidir, citando o par titulo e texto de apoio
    avisos = m['falhas'] + m['decisoes_do_da']
    assert any(x['codigo'] == 'sobreposicao_nova' and 'título' in x['texto'] and 'texto' in x['texto']
               for x in avisos), avisos


def test_apoio_maior_e_menor_de_novo_volta_ao_tamanho_e_o_titulo_nunca_andou(job95, conteudo95):
    antes = _previa(conteudo95, [])
    ida = _apoio_maior(job95)
    volta = ida + [dict(ida[0], fator=1.0 / 3.0)]
    depois = _previa(conteudo95, volta)
    # o apoio e o mexido (a intencao de alinhamento pode encaixar so ele, decisao 185); o resto nunca andou
    _confere_parados(antes, depois, [_el(job95, 'apoio')])


# ------------------------------------------------------------------ as outras edicoes
def _mover(j):
    return [{'elemento': _el(j, 'apoio'), 'acao': 'mover', 'dx': 0.0, 'dy': -0.12}]


def _apagar(j):
    return [{'elemento': _el(j, 'apoio'), 'acao': 'apagar'}]


def _alinhar(j):
    return [{'elemento': _el(j, 'apoio'), 'acao': 'alinhar', 'alvo': 'topo', 'referencia': 'margem'}]


def _texto(j):
    return [{'elemento': _el(j, 'titulo'), 'acao': 'texto', 'texto': 'HOAX HOAX'}]


def _mover_o_grupo(j):
    ids = [_el(j, 'titulo'), _el(j, 'apoio')]
    return [{'elemento': ids[0], 'elementos': ids, 'acao': 'mover', 'dx': 0.05, 'dy': 0.0}]


@pytest.mark.parametrize('edicoes, mexidos, apagados', [
    (_mover, ['apoio'], []),
    (_apagar, [], ['apoio']),
    (_alinhar, ['apoio'], []),
    # 0.9.6 (decisao 196): o titulo com texto editado tem a caixa das linhas do DA, entao a caixa dele muda com o texto
    # (antes ficava a de 4 linhas); ele conta como mexido, e os outros continuam parados
    (_texto, ['titulo'], []),
    (_mover_o_grupo, ['titulo', 'apoio'], []),
], ids=['mover', 'apagar', 'alinhar', 'texto', 'mover_o_grupo'])
def test_cada_edicao_deixa_os_nao_mexidos_parados(job95, conteudo95, edicoes, mexidos, apagados):
    antes = _previa(conteudo95, [])
    depois = _previa(conteudo95, edicoes(job95))
    _confere_parados(antes, depois, [_el(job95, p) for p in mexidos], [_el(job95, p) for p in apagados])


# ------------------------------------------------------------------ o grupo alinhado e depois um membro mexido
def _grupo_na_margem_direita(j):
    ids = [_el(j, 'titulo'), _el(j, 'apoio')]
    return [{'elemento': ids[0], 'elementos': ids, 'acao': 'alinhar', 'alvo': 'margem_direita',
             'referencia': 'margem'}]


@pytest.mark.parametrize('segunda', ['apagar', 'mover', 'escalar'])
def test_mexer_num_membro_do_grupo_alinhado_deixa_o_outro_parado(job95, conteudo95, segunda):
    # revisao da 0.9.5: o DA alinha o titulo e o apoio juntos na margem direita (a linha e a direita do apoio) e depois
    # mexe so no apoio. O titulo fica onde o alinhamento do grupo o deixou: o motor nao recalcula a linha so com ele
    tit, apo = _el(job95, 'titulo'), _el(job95, 'apoio')
    e1 = _grupo_na_margem_direita(job95)
    e2 = {'apagar': {'elemento': apo, 'acao': 'apagar'},
          'mover': {'elemento': apo, 'acao': 'mover', 'dx': -0.01, 'dy': 0.0},
          'escalar': {'elemento': apo, 'acao': 'escalar', 'fator': 0.9, 'fx': 0.5, 'fy': 0.5}}[segunda]
    antes = _previa(conteudo95, e1)
    depois = _previa(conteudo95, e1 + [e2])
    _confere_parados(antes, depois, [apo], [apo] if segunda == 'apagar' else [])
    assert ed.intencoes(e1 + [e2]) == []


def test_alinhar_um_membro_sozinho_tira_o_grupo_daquele_eixo(job95):
    tit = _el(job95, 'titulo')
    e1 = _grupo_na_margem_direita(job95)
    e2 = {'elemento': tit, 'acao': 'alinhar', 'alvo': 'margem_esquerda', 'referencia': 'margem'}
    assert [i['elementos'] for i in ed.intencoes(e1 + [e2])] == [[tit]]
    # o outro eixo de um grupo continua valendo
    e3 = {'elemento': tit, 'acao': 'alinhar', 'alvo': 'topo', 'referencia': 'margem'}
    assert [(i['elementos'], i['eixo']) for i in ed.intencoes(e1 + [e3])] == [
        ([tit, _el(job95, 'apoio')], 'x'), ([tit], 'y')]


# ------------------------------------------------------------------ o layout do membro, sem encaixe refeito
def test_sem_encaixe_refeito_no_motor():
    # o encaixe refeito pelo solver depois da edicao do DA saiu (decisao do Duda em 17/11): nada o chama mais
    assert not hasattr(mg, 'reencaixar')
    assert 'do_solver' not in inspect.signature(mg.decisoes_do_da).parameters
    assert not hasattr(proposta, 'TEXTO_SOLVER')
    fonte = inspect.getsource(proposta.layout_do_membro)
    assert '_resolver' not in fonte and 'reencaixar' not in fonte


# ------------------------------------------------------------------ previa igual ao Salvar
def test_previa_e_salvar_dao_o_mesmo_layout_com_o_apoio_maior(tmp_path):
    j = _job(tmp_path)
    conteudo = te.montar(j['job'])
    gid = _gid(conteudo)
    eds = _apoio_maior(j)
    esc = tpi._escolhas(conteudo, gid)
    esc[gid]['edicoes'] = eds
    previa = _previa(conteudo, eds)
    partida = _caixas(_previa(conteudo, []))
    with pytest.MonkeyPatch.context() as m:
        m.setattr(kv, 'FORMATOS', FORMATOS)
        gravadas = tpi._salvar(j, conteudo, esc)
    for membro in previa['membros']:
        d = gravadas[membro['formato']]
        caixas = {e['id']: [float(x) for x in e['caixa']] for e in membro['palco']['elementos']}
        gravada = {e['id']: [float(x) for x in e['caixa']] for e in d['elementos']}
        assert sorted(caixas) == sorted(gravada)
        for k, c in caixas.items():
            assert gravada[k] == pytest.approx(c, abs=TOL), (membro['formato'], k)
            if k != _el(j, 'apoio'):
                # o que o DA nao mexeu fica com a caixa da versao de partida
                assert c == pytest.approx(partida[membro['formato']][k], abs=TOL), (membro['formato'], k)


# ------------------------------------------------------------------ o Tamanho ate 1000%
def test_limites_do_tamanho_vao_de_25_a_1000_por_cento():
    assert limites.valor('tela.escala_max') == 10
    assert ed.limites_da_escala() == (0.25, 10.0)
    assert ed.escala_fora([{'elemento': 'a', 'acao': 'escalar', 'fator': 10.0}]) == []
    assert ed.escala_fora([{'elemento': 'a', 'acao': 'escalar', 'fator': 4.5}]) == []
    assert ed.escala_fora([{'elemento': 'a', 'acao': 'escalar', 'fator': 10.01}]) == ['a']
    assert ed.escala_fora([{'elemento': 'a', 'acao': 'escalar', 'fator': 5.0},
                           {'elemento': 'a', 'acao': 'escalar', 'fator': 2.0}]) == []
    assert ed.escala_fora([{'elemento': 'a', 'acao': 'escalar', 'fator': 5.0},
                           {'elemento': 'a', 'acao': 'escalar', 'fator': 2.1}]) == ['a']


def test_previa_aceita_1000_por_cento_e_recusa_acima(job95, conteudo95):
    assert conteudo95['estado']['edicao']['escala_max'] == 10
    apoio = _el(job95, 'apoio')
    gid = _gid(conteudo95)
    um = {'elemento': apoio, 'acao': 'escalar', 'fator': 10.0, 'fx': 0, 'fy': 1}
    assert conteudo95['editar']({'familia': gid, 'versao': None, 'edicoes': [um], 'quebras': []}, ORIGEM) is not None
    acima = dict(um, fator=10.5)
    assert conteudo95['editar']({'familia': gid, 'versao': None, 'edicoes': [acima], 'quebras': []}, ORIGEM) is None


# ------------------------------------------------------------------ a tela no Chromium (revisao da 0.9.5)
# a caixa de cada rotulo em px da peca: o mundo do palco cresce com o que passa da borda, e a moldura marca a peca
JS_CAIXAS_DA_PECA = '''() => { const o = {}; const q = document.querySelector('#palco .moldura');
  const x0 = parseFloat(q.style.left), y0 = parseFloat(q.style.top);
  document.querySelectorAll('#palco .rotulo').forEach(r => {
  o[r.dataset.elemento] = [parseFloat(r.style.left) - x0, parseFloat(r.style.top) - y0, parseFloat(r.style.width),
    parseFloat(r.style.height)]; }); return o; }'''
JS_ZOOM = '() => (document.getElementById("medida-palco").textContent.match(/exibição em [0-9]+%/) || [""])[0]'
SALVO = '() => (document.documentElement.dataset.rascunho === "salvo" && ' \
        'document.documentElement.dataset.previa === "pronta") ? "1" : ""'


def test_tamanho_ate_1000_e_de_volta_a_100_no_chromium(tmp_path):
    """No 970x250, o DA leva o apoio a 200%, 1000% e de volta a 100% pelo campo Tamanho. O apoio volta a caixa de
    partida (o ponto fixo de quem passa das duas bordas e o da edicao anterior); o titulo e o fundo nunca andam; a
    exibicao do palco fica a de antes da primeira edicao; o canto diz o tamanho final."""
    from playwright.sync_api import sync_playwright

    import test_tela_galeria as tg
    import test_tela_grupo as tgr
    import test_tela_palco as tp
    from desdobra.chromium import navegador
    from desdobra.tela import atos as ta
    from desdobra.tela import servidor as ts
    j = _job(tmp_path)
    job = j['job']
    conteudo = te.montar(job)
    apoio, titulo, fundo = _el(j, 'apoio'), _el(j, 'titulo'), _el(j, 'fundo')
    msg = '() => document.getElementById("ed-mensagem").textContent'
    navegador.apontar_playwright()
    with ts.ServidorTela(conteudo, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo)) as srv, sync_playwright() as pw:
        nav, pg = tp._pagina_da_tela(pw, srv, 1600, 1000)  # numero-neutro: px da janela do teste
        try:
            tg._abrir(pg, conteudo['estado'], F970)
            tp._esperar(pg, '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""')
            c0 = pg.evaluate(JS_CAIXAS_DA_PECA)
            zoom0 = pg.evaluate(JS_ZOOM)
            assert zoom0
            x, y = tgr._ponto(pg, apoio)
            pg.mouse.click(x, y)
            for v in ('200', '1000', '100'):
                pg.fill('#ed-tamanho', v)
                pg.press('#ed-tamanho', 'Enter')
                tp._esperar(pg, SALVO)
                c = pg.evaluate(JS_CAIXAS_DA_PECA)
                for k in (titulo, fundo):
                    assert c[k] == pytest.approx(c0[k], abs=TOL), (v, k)
                # a faixa de avisos e o apoio fora da peca nao mudam a exibicao do palco
                assert pg.evaluate(JS_ZOOM) == zoom0, v
            # os tres passos escalam em volta do mesmo ponto: a conta das edicoes devolve a caixa de partida, e o
            # apoio so pode ter encostado na linha de um vizinho pela intencao de alinhamento (decisao 185). Antes da
            # revisao, a volta a 100% o levava para cima dos produtos, a 0,6 da largura do formato
            eds = tgr._edicoes(job, _gid(conteudo))
            assert len(eds) == 3 and len({(e.get('fx'), e.get('fy')) for e in eds}) == 1, eds
            caixas = _caixas(_previa(conteudo, eds))[F970]
            assert c[apoio][:2] == pytest.approx(caixas[apoio][:2], abs=TOL), (c[apoio], caixas[apoio])
            assert abs(c[apoio][0] - c0[apoio][0]) < 0.01 * 970 and abs(c[apoio][1] - c0[apoio][1]) < 0.02 * 250, \
                (c0[apoio], c[apoio])  # numero-neutro: o encaixe numa linha vizinha
            # o canto da alca diz o tamanho final, como o Tamanho digitado
            alcas = pg.evaluate('''() => Array.from(document.querySelectorAll("#palco .alca")).map(a => {
                const b = a.getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; })''')
            canto = max(alcas, key=lambda a: a[0] + a[1])
            pg.mouse.move(canto[0], canto[1])
            pg.mouse.down()
            pg.mouse.move(canto[0] + 40, canto[1] + 20, steps=8)  # numero-neutro: px do arraste
            pg.mouse.up()
            tp._esperar(pg, SALVO)
            valor = pg.evaluate('() => document.getElementById("ed-tamanho").value')
            assert valor != '100' and ('O tamanho ficou em ' + valor + '%') in pg.evaluate(msg)
            # a frase repetida pelo motor aparece uma vez so na faixa de avisos
            faixa = pg.evaluate('() => Array.from(document.querySelectorAll("#variante-palco .var-palco-aviso"))'
                                '.map(s => s.textContent)')
            for t in faixa:
                frases = [f for f in t.split('. ') if f]
                assert len(frases) == len(set(frases)), t
        finally:
            nav.close()
        contagem = dict(srv.contagem)
    assert contagem['proibido'] == 0 and contagem['csrf_recusado'] == 0
