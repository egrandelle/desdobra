# -*- coding: utf-8 -*-
"""Decisao 185 (revisa a 168): o alinhamento automatico so move o elemento que o DA acabou de mexer, escrito antes do
codigo.

Criterios de pronto cobertos aqui:
  - o elemento mexido por ultimo (ou o grupo dele) encaixa na linha do vizinho, a menos da tolerancia; acima dela,
    nada anda;
  - nenhum outro elemento sai do lugar: nem o que o DA nao mexeu, nem o que ele mexeu antes;
  - o produto alinhado com o bloco de texto no KV nao acompanha o bloco quando o DA move o bloco;
  - o grupo mexido encaixa inteiro;
  - o elemento mexido preso a uma linha do quadro (alinhar) nao anda naquele eixo, e o vizinho tambem nao;
  - a mesma regra vale quando o rascunho inteiro e refeito (a previa e o "Salvar e seguir" refazem todas as edicoes
    da familia): cada edicao alinha so o que ela mexeu, na hora dela;
  - a confirmacao da familia com edicoes feita pela regra de antes cai uma vez (decisao 175); a da familia sem
    edicao continua valendo;
  - revisao da 185: cada edicao parte do que a tela mostra (o arraste solta onde o DA soltou, o grupo anda e alinha
    inteiro, o canto fixo do Tamanho fica); a linha que a edicao deixou para tras nao puxa o mexido de volta (a seta
    anda 1 px nos dois sentidos), e o eixo em que ele nao andou nao encaixa (o alinhar na largura nao muda a altura);
    a edicao de texto nao devolve alinhado.
Tudo sintetico: caixas montadas a mao."""
import pytest

from desdobra.tela import edicao as ed
from desdobra.tela import estado

W, H = 1920, 1080  # a tolerancia e 1% do lado maior: 19,2 px


# ------------------------------------------------------------------ normalizar: so o mexido anda
def test_o_mexido_por_ultimo_encaixa_na_linha_do_vizinho():
    caixas = {'titulo': [40.0, 100.0, 400.0, 160.0], 'apoio': [43.0, 200.0, 300.0, 240.0]}
    novas, alinhados = ed.normalizar(caixas, ['titulo'], W, H)
    assert novas['apoio'] == caixas['apoio']
    assert novas['titulo'] == pytest.approx([43.0, 100.0, 403.0, 160.0])
    assert [(a['elementos'], a['eixo'], a['linha']) for a in alinhados] == [(['titulo', 'apoio'], 'x', 'esquerda')]


def test_acima_da_tolerancia_nada_anda():
    caixas = {'titulo': [40.0, 100.0, 400.0, 160.0], 'apoio': [70.0, 200.0, 300.0, 240.0]}
    novas, alinhados = ed.normalizar(caixas, ['titulo'], W, H)
    assert novas == caixas and alinhados == []


def test_o_mexido_antes_fica_quando_outro_e_mexido_perto_dele():
    # a foi mexido antes e esta onde o DA o deixou; b, mexido agora, para a 4 px da esquerda dele: b encaixa, a fica
    caixas = {'a': [200.0, 100.0, 500.0, 200.0], 'b': [204.0, 400.0, 400.0, 450.0]}
    novas, _a = ed.normalizar(caixas, ['b'], W, H)
    assert novas['a'] == caixas['a']
    assert novas['b'][0] == pytest.approx(200.0)


def _bloco_e_produto():
    # no KV, o bloco de texto (t1 em cima de t2) e o produto p dividem a base (500)
    kv = {'t1': [100.0, 400.0, 500.0, 460.0], 't2': [100.0, 470.0, 400.0, 500.0], 'p': [1200.0, 300.0, 1500.0, 500.0]}
    # o DA subiu o bloco 105 px: o topo de t1 para a 5 px do topo do produto
    caixas = {'t1': [100.0, 295.0, 500.0, 355.0], 't2': [100.0, 365.0, 400.0, 395.0], 'p': list(kv['p'])}
    return kv, caixas


def test_produto_alinhado_no_kv_nao_acompanha_o_bloco_de_texto():
    kv, caixas = _bloco_e_produto()
    novas, alinhados = ed.normalizar(caixas, ['t1', 't2'], W, H, kv_caixas=kv, kv_tamanho=(W, H),
                                     grupos=[['t1', 't2']])
    assert novas['p'] == caixas['p']
    # o bloco encaixa inteiro na linha do produto: desce 5 px
    assert novas['t1'] == pytest.approx([100.0, 300.0, 500.0, 360.0])
    assert novas['t2'] == pytest.approx([100.0, 370.0, 400.0, 400.0])
    assert all(a['elementos'][0] in ('t1', 't2') for a in alinhados), alinhados


def test_o_grupo_mexido_encaixa_inteiro_e_o_vizinho_fica():
    # a e b andaram juntos; b para a 4 px da esquerda de t: o grupo inteiro anda 4 px, com o circulo c (acompanham)
    caixas = {'a': [500.0, 600.0, 560.0, 700.0], 'b': [104.0, 400.0, 180.0, 450.0], 't': [100.0, 50.0, 400.0, 90.0]}
    circulo = {'c': [450.0, 380.0, 700.0, 720.0]}
    novas, alinhados = ed.normalizar(caixas, ['a', 'b', 'c'], W, H, grupos=[['a', 'b', 'c']], acompanham=circulo)
    assert novas['t'] == caixas['t']
    for k, c in list(caixas.items()) + list(circulo.items()):
        if k != 't':
            assert novas[k] == pytest.approx([c[0] - 4.0, c[1], c[2] - 4.0, c[3]]), k
    assert [(a['elementos'], a['eixo']) for a in alinhados] == [(['b', 't'], 'x')]


def test_o_mexido_preso_ao_quadro_nao_anda_e_o_vizinho_tambem_nao():
    # t, mexido agora, foi alinhado a margem (preso na largura); o esta a 5 px da esquerda dele: nada anda no x
    caixas = {'t': [40.0, 100.0, 300.0, 140.0], 'o': [45.0, 400.0, 200.0, 450.0]}
    novas, alinhados = ed.normalizar(caixas, ['t'], W, H, presos={('t', 'x')})
    assert novas == caixas and alinhados == []


def test_o_vizinho_preso_ao_quadro_recebe_o_mexido():
    caixas = {'t': [40.0, 100.0, 300.0, 140.0], 'o': [45.0, 400.0, 200.0, 450.0]}
    novas, _a = ed.normalizar(caixas, ['o'], W, H, presos={('t', 'x')})
    assert novas['t'] == caixas['t'] and novas['o'][0] == pytest.approx(40.0)


# ------------------------------------------------------------------ o rascunho refeito: cada edicao na hora dela
def _mover(eid, dx_px, dy_px, elementos=None):
    e = {'elemento': eid, 'acao': 'mover', 'dx': dx_px / W, 'dy': dy_px / H}
    if elementos:
        e['elementos'] = list(elementos)
    return e


def test_rascunho_refeito_nunca_tira_do_lugar_o_que_o_da_nao_mexeu():
    kv, caixas = _bloco_e_produto()
    edicoes = [_mover('t1', 0.0, -105.0, ['t1', 't2'])]
    novas, _ap, _tx, mexidos, _al = ed.editar(kv, edicoes, W, H, conteudo=('t1', 't2', 'p'), kv_caixas=kv,
                                              kv_tamanho=(W, H))
    assert novas['p'] == kv['p']
    assert novas['t1'] == pytest.approx([100.0, 300.0, 500.0, 360.0])
    assert mexidos == ['t1', 't2']


def test_rascunho_refeito_guarda_o_encaixe_do_que_foi_mexido_antes():
    # u nunca e mexido; a encaixa na esquerda de u na edicao dele; depois b para perto da direita de a: so b anda
    inicio = {'u': [100.0, 50.0, 300.0, 90.0], 'a': [600.0, 300.0, 900.0, 350.0], 'b': [1300.0, 600.0, 1500.0, 650.0]}
    edicoes = [_mover('a', -496.0, 0.0),  # a vai para x=104, a 4 px da esquerda de u: a encaixa em 100
               _mover('b', -1095.0, 0.0)]  # b vai para x=205 a 405, a 5 px da direita de a (400)
    novas, _ap, _tx, mexidos, alinhados = ed.editar(inicio, edicoes, W, H, conteudo=('u', 'a', 'b'))
    assert novas['u'] == inicio['u']
    # a ficou no encaixe da edicao dele, fora da linha de b
    assert novas['a'] == pytest.approx([100.0, 300.0, 400.0, 350.0])
    # b encaixou na direita de a (400): anda 5 px para a esquerda; a nao vai a b
    assert novas['b'] == pytest.approx([200.0, 600.0, 400.0, 650.0])
    assert mexidos == ['a', 'b']
    # o que a tela mostra e o encaixe da ultima edicao
    assert [a['elementos'] for a in alinhados] == [['b', 'a']]


def test_os_toques_da_seta_andam_1_px_e_nao_voltam_para_a_linha_que_deixaram():
    # a encaixa na esquerda de u (a 4 px); cada toque de 1 px anda 1 px a partir do que a tela mostra, e a linha que
    # o toque deixou para tras nao puxa a de volta, nem no segundo toque. u nunca anda
    inicio = {'u': [100.0, 50.0, 300.0, 90.0], 'a': [600.0, 300.0, 900.0, 350.0]}
    um = [_mover('a', -496.0, 0.0), _mover('a', 1.0, 0.0)]
    novas, _ap, _tx, _mx, alinhados = ed.editar(inicio, um, W, H, conteudo=('u', 'a'))
    assert novas['u'] == inicio['u'] and novas['a'] == pytest.approx([101.0, 300.0, 401.0, 350.0])
    assert alinhados == []
    dois = um + [_mover('a', 1.0, 0.0)]
    novas, _ap, _tx, _mx, alinhados = ed.editar(inicio, dois, W, H, conteudo=('u', 'a'))
    assert novas['u'] == inicio['u'] and novas['a'] == pytest.approx([102.0, 300.0, 402.0, 350.0])
    assert alinhados == []
    # a seta que vai na direcao de uma linha ainda encaixa nela: a anda de 102 para 101 e a linha de u (100) puxa
    volta = dois + [_mover('a', -1.0, 0.0)]
    assert ed.editar(inicio, volta, W, H, conteudo=('u', 'a'))[0]['a'][0] == pytest.approx(100.0)


def test_rascunho_refeito_com_texto_por_ultimo_nao_alinha_nada_de_novo():
    inicio = {'a': [600.0, 300.0, 900.0, 350.0], 'u': [100.0, 50.0, 300.0, 90.0]}
    edicoes = [_mover('a', -100.0, 0.0), {'elemento': 'u', 'acao': 'texto', 'texto': 'X'}]
    novas, _ap, textos, mexidos, _al = ed.editar(inicio, edicoes, W, H, conteudo=('a', 'u'))
    assert novas['u'] == inicio['u'] and novas['a'] == pytest.approx([500.0, 300.0, 800.0, 350.0])
    assert textos == {'u': 'X'} and mexidos == ['a']


def test_rascunho_refeito_o_alinhado_no_quadro_fica_no_eixo_dele():
    # a foi alinhado na margem esquerda (preso no x); a 5 px da esquerda de u: nem a nem u andam no x
    inicio = {'u': [105.0, 50.0, 300.0, 90.0], 'a': [600.0, 300.0, 900.0, 350.0]}
    quadros = {'margem': [100.0, 0.0, 1820.0, 1080.0], 'area_segura': [100.0, 0.0, 1820.0, 1080.0]}
    edicoes = [{'elemento': 'a', 'acao': 'alinhar', 'alvo': 'margem_esquerda', 'referencia': 'margem'}]
    novas, *_r = ed.editar(inicio, edicoes, W, H, quadros=quadros, conteudo=('u', 'a'))
    assert novas['u'] == inicio['u'] and novas['a'][0] == pytest.approx(100.0)


# ------------------------------------------------------------------ a confirmacao de antes cai uma vez (175)
def test_confirmacao_pela_regra_de_antes_cai(monkeypatch):
    agora = estado.impressao_das_pecas(['f1'], {'f1': {}}, [])
    monkeypatch.setattr(estado, 'REGRA_DA_PREVIA', 'previa_igual_ao_salvar')
    assert estado.impressao_das_pecas(['f1'], {'f1': {}}, []) != agora


# ------------------------------------------------------------------ revisao da 185: a edicao parte do que a tela mostra
# tela.js mede o arraste, o Tamanho e o alinhar sobre a caixa que o palco mostra, ja com o encaixe; o motor tambem
def test_grupo_alinhado_na_margem_depois_de_um_encaixe_vai_inteiro_para_a_margem():
    # A encaixa na esquerda de B (100); o DA escolhe A e B e pede a margem esquerda (50): os dois vao a 50
    inicio = {'A': [300.0, 600.0, 400.0, 650.0], 'B': [100.0, 100.0, 400.0, 150.0]}
    e1 = _mover('A', 92.0 - 300.0, 0.0)
    assert ed.editar(inicio, [e1], W, H)[0]['A'][0] == pytest.approx(100.0)
    e2 = {'elemento': 'A', 'elementos': ['A', 'B'], 'acao': 'alinhar', 'alvo': 'margem_esquerda',
          'referencia': 'margem'}
    fim = ed.editar(inicio, [e1, e2], W, H, {'margem': [50.0, 50.0, 1870.0, 1030.0]})[0]
    assert fim['A'][0] == pytest.approx(50.0) and fim['B'][0] == pytest.approx(50.0)


def test_grupo_movido_depois_de_um_encaixe_anda_inteiro():
    inicio = {'A': [300.0, 600.0, 400.0, 650.0], 'B': [100.0, 100.0, 400.0, 150.0]}
    e1 = _mover('A', 92.0 - 300.0, 0.0)
    fim = ed.editar(inicio, [e1, _mover('A', 300.0, 0.0, ['A', 'B'])], W, H)[0]
    assert fim['A'][0] == pytest.approx(400.0) and fim['B'][0] == pytest.approx(400.0)


def test_mover_so_no_x_nao_mexe_no_y_do_encaixe_de_antes():
    # o topo de A encaixa no topo de B (300); B desce; o DA arrasta A so na horizontal: o topo de A fica em 300
    inicio = {'A': [500.0, 500.0, 700.0, 550.0], 'B': [1000.0, 300.0, 1200.0, 500.0]}
    edicoes = [_mover('A', 0.0, -208.0), _mover('B', 0.0, 400.0)]
    assert ed.editar(inicio, edicoes, W, H)[0]['A'][1] == pytest.approx(300.0)
    fim = ed.editar(inicio, edicoes + [_mover('A', 100.0, 0.0)], W, H)[0]
    assert fim['A'] == pytest.approx([600.0, 300.0, 800.0, 350.0])


def test_arraste_depois_do_encaixe_cai_onde_o_da_soltou():
    inicio = {'A': [100.0, 100.0, 300.0, 200.0], 'B': [115.0, 500.0, 315.0, 600.0], 'C': [600.0, 120.0, 700.0, 180.0]}
    e1 = _mover('A', 3.0, 0.0)  # A a 12 px da esquerda de B: encaixa em 115
    tela = ed.editar(inicio, [e1], W, H)[0]
    assert tela['A'][0] == pytest.approx(115.0)
    assert ed.editar(inicio, [e1, _mover('A', 300.0, 0.0)], W, H)[0]['A'][0] == pytest.approx(415.0)
    # o grupo formado depois do encaixe anda inteiro, como o palco mostrava
    fim = ed.editar(inicio, [e1, _mover('A', 300.0, 0.0, ['A', 'C'])], W, H)[0]
    assert fim['C'][0] - fim['A'][0] == pytest.approx(tela['C'][0] - tela['A'][0])


def test_escalar_com_canto_fixo_depois_do_encaixe_deixa_o_canto_onde_a_tela_mostrou():
    inicio = {'A': [100.0, 100.0, 300.0, 200.0], 'B': [115.0, 500.0, 195.0, 600.0]}
    e1 = _mover('A', 3.0, 0.0)
    e2 = {'elemento': 'A', 'acao': 'escalar', 'fator': 0.5, 'fx': 0.0, 'fy': 0.0}
    assert ed.editar(inicio, [e1, e2], W, H)[0]['A'] == pytest.approx([115.0, 100.0, 215.0, 150.0])


def test_seta_depois_do_encaixe_anda_1_px_nos_dois_sentidos():
    # o arraste encaixa A em 115; a seta e uma edicao nova (tela.js so junta toques de tecla): 1 toque, 1 px
    inicio = {'A': [100.0, 100.0, 300.0, 200.0], 'B': [115.0, 500.0, 315.0, 600.0]}
    e1 = _mover('A', 3.0, 0.0)
    for sinal in (1.0, -1.0):
        assert ed.editar(inicio, [e1, _mover('A', sinal, 0.0)], W, H)[0]['A'][0] == pytest.approx(115.0 + sinal)


def _encaixar_da_pagina(elementos, ids, c, tol):
    """O encaixe leve do arraste de tela.js (encaixar), linha por linha: o deslocamento ate a linha mais perto."""
    def linhas(b):
        return {'x': [b[0], (b[0] + b[2]) / 2, b[2]], 'y': [b[1], (b[1] + b[3]) / 2, b[3]]}
    meu, melhor = linhas(c), {'x': None, 'y': None}
    for oid, caixa in elementos.items():
        if oid in ids:
            continue
        dele = linhas(caixa)
        for eixo in ('x', 'y'):
            for i in range(3):
                d = dele[eixo][i] - meu[eixo][i]
                if abs(d) <= tol and (melhor[eixo] is None or abs(d) < abs(melhor[eixo])):
                    melhor[eixo] = d
    return melhor


def test_arraste_so_vertical_deixa_o_x_que_a_pagina_mostrou():
    inicio = {'u': [100.0, 50.0, 300.0, 90.0], 'a': [600.0, 300.0, 900.0, 350.0], 'v': [1300.0, 700.0, 1500.0, 750.0]}
    conteudo = ('u', 'a', 'v')
    edicoes = [_mover('a', -482.0, 0.0), _mover('v', -1170.0, 0.0)]  # a encaixa em u (100); v vai a 130
    tela = ed.editar(inicio, edicoes, W, H, conteudo=conteudo)[0]
    assert tela['a'][0] == pytest.approx(100.0) and tela['v'][0] == pytest.approx(130.0)
    arrastada = [tela['a'][0], tela['a'][1] + 100.0, tela['a'][2], tela['a'][3] + 100.0]
    melhor = _encaixar_da_pagina({k: v for k, v in tela.items() if k != 'a'}, ['a'], arrastada, ed.tolerancia(W, H))
    dx = melhor['x'] or 0.0
    fim = ed.editar(inicio, edicoes + [_mover('a', dx, 100.0 + (melhor['y'] or 0.0))], W, H, conteudo=conteudo)[0]
    assert fim['a'][0] == pytest.approx(arrastada[0] + dx)


def test_alinhar_no_quadro_nao_move_o_mexido_no_outro_eixo():
    # decisao 185: o mexido preso a uma linha do quadro nao anda; o topo de a, a 5 px do de u, fica
    inicio = {'u': [500.0, 300.0, 700.0, 340.0], 'a': [800.0, 305.0, 1000.0, 345.0]}
    quadros = {'margem': [100.0, 0.0, 1820.0, 1080.0], 'area_segura': [100.0, 0.0, 1820.0, 1080.0]}
    edicoes = [{'elemento': 'a', 'acao': 'alinhar', 'alvo': 'margem_esquerda', 'referencia': 'margem'}]
    novas, _ap, _tx, _mx, alinhados = ed.editar(inicio, edicoes, W, H, quadros=quadros, conteudo=('u', 'a'))
    assert novas['a'] == pytest.approx([100.0, 305.0, 300.0, 345.0]) and alinhados == []


def test_edicao_de_texto_depois_do_encaixe_nao_devolve_alinhado():
    # tela.js mostrarAlinhamento desenha a linha do alinhado da ultima edicao: o texto nao alinhou nada
    inicio = {'u': [100.0, 50.0, 300.0, 90.0], 'a': [600.0, 300.0, 900.0, 350.0]}
    edicoes = [_mover('a', -496.0, 0.0), {'elemento': 'a', 'acao': 'texto', 'texto': 'Novo'}]
    assert ed.editar(inicio, edicoes, W, H, conteudo=('u', 'a'))[4] == []


def test_familia_sem_edicao_vista_antes_da_185_continua_valendo():
    from desdobra.tela import rascunho
    formatos = {'f1': {'formato': {'composicao': 'c'}, 'situacao': 'derivado'}}
    agora = estado.impressao_das_pecas(['f1'], formatos, [])
    antes = estado.impressao_das_pecas(['f1'], formatos, [], regra=estado.REGRA_SEM_EDICAO)
    assert antes != agora
    sem = {'confirmada': True, 'edicoes': [], 'confirmacao': {'formatos': ['f1'], 'pecas': antes}}
    assert rascunho.confirmada_para(sem, ['f1'], agora, sem_edicao=antes)
    assert rascunho.sem_confirmacao_velha({'familias': {'g': sem}}, {'g': ['f1']}, {'g': agora},
                                          {'g': antes})['familias']['g']['confirmada']
    # a familia com edicoes vista pela regra de antes pede o clique de novo: a previa dela pode mudar
    com = dict(sem, edicoes=[_mover('f', 1.0, 0.0)])
    assert not rascunho.confirmada_para(com, ['f1'], agora, sem_edicao=antes)
    assert rascunho.confirmada_para(dict(com, confirmacao={'formatos': ['f1'], 'pecas': agora}), ['f1'], agora,
                                    sem_edicao=antes)


def test_docs_sem_a_regra_de_antes_da_185():
    from pathlib import Path
    doc = (Path(__file__).resolve().parents[3] / 'docs' / 'm1-interfaces.md').read_text(encoding='utf-8')
    for velha in ('no par, o outro vem para a linha dele', 'o elemento que andaria para a linha do mexido',
                  'As edições andam sobre as caixas sem os encaixes'):
        assert velha not in doc, velha
