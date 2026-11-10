# -*- coding: utf-8 -*-
"""A derivacao e o render respeitam a quebra de linha da familia da tela (M7b, C2; decisoes-v1.md, 167 e 171; secao
9.8 da arquitetura, editor de mestre), escrita antes do codigo.

A quebra da familia (quebras_por_familia com familia, C1) vale em todo membro da familia, so nela:
  - juntar (os indices das quebras gravadas que ficam) e inserir (as posicoes de espaco que viram quebra) valem fora da
    mestre propria, pela mesma medida da quebra por faixa do M5 (a medida injetada aqui; no job, o Chromium mede);
  - a caixa do texto na mestre da familia e a medida, nos caminhos do motor (transformacao e solver), na versao da
    galeria e com a edicao do DA por cima; a escala do texto sai dessa caixa;
  - cada elemento com a quebra da familia leva quebras_origem ("da", ou "proposta" na quebra que o motor propos) e
    origem_geometria "da" quando a quebra e do DA ou foi aprovada por ele;
  - o texto editado na familia leva a quebra da familia sobre o texto novo, sem medida (o render quebra na caixa);
  - sem a medida, o formato volta ao DA, como na quebra por faixa;
  - a quebra da familia vence a da faixa nos formatos da familia;
  - a derivacao continua deterministica, e a familia sem quebra sai como antes desta fase.
Material sintetico (test_quebras_da_familia: o texto 'VOX AH', quebra, 'OX HA', com espacos nas posicoes 3 e 9)."""
import pytest

import test_derivacao_apoio as ap
import test_quebras_da_familia as q1
from desdobra import contratos
from desdobra.briefing import modelo as mb
from desdobra.derivacao import diferenca as mdif
from desdobra.derivacao import nucleo as nd
from desdobra.derivacao import quebras as mq
from desdobra.render import derivado as rd

HORIZONTAL = ('largo', 'perto')
VERTICAL = ('v1', 'v2')
# a caixa do texto na mestre do KV e a entrelinha dele (test_quebras_da_familia._laudo)
CAIXA_KV = [20.0, 40.0, 260.0, 110.0]
ENTRELINHA = 23.0
# juntar a quebra gravada (uma linha so, mais larga) e inserir no espaco 3 (tres linhas, mais estreitas)
JUNTADA = [20.0, 40.0, 320.0, 110.0 - ENTRELINHA]
INSERIDA = [20.0, 40.0, 140.0, 110.0 + ENTRELINHA]


def _medida(largura):
    """Medida injetada (a que o Chromium daria), no espaco de texto: a linha mais larga da mestre e a do texto novo."""
    return {'largura_texto_mestre': 240.0, 'largura_texto': largura, 'linhas': 1}


def _medidas():
    return {mq.chave(10, []): _medida(300.0), mq.chave(10, [0], [3]): _medida(120.0)}


PADRAO = 'padrao'


def _h(manter=(), inseridas=(), **k):
    """A quebra da familia horizontal (largo e perto, caminhos do motor)."""
    return q1._quebra(manter=manter, inseridas=inseridas, familia='horizontal-1', formatos=HORIZONTAL, **k)


def _b(quebras, edicoes_h=None, edicoes_v=None, confirmada_h=True):
    b = q1._b(quebras, edicoes=edicoes_v, edicoes_largo=edicoes_h)
    b['formatos'].append(ap.formato('perto', 480, 300))
    b['familias'] = {'faixa': ap.decisao(3.0)}
    b['composicoes'][1]['formatos'] = list(HORIZONTAL)
    if not confirmada_h:
        b['composicoes'][1].update(confirmada=False, confirmacao=None)
    return b


def _derivar(b, medidas=PADRAO):
    medidas = _medidas() if medidas == PADRAO else medidas
    contratos.validar(b, mb.ESQUEMA)
    assert mb.conferir(q1._laudo(), b) == []
    ctx = nd.contexto(q1._laudo(), b, medidas_quebras=medidas)
    return nd.derivar_em_memoria(ctx, specs={})['formatos']


def _el(d, eid='el10'):
    return next(e for e in d['elementos'] if e['id'] == eid)


def _escala_da_caixa(e):
    """A escala que a caixa do elemento da sobre a caixa dele na mestre (a da transformacao tem de ser esta)."""
    c, m = e['caixa'], e['caixa_mestre']
    return (c[2] - c[0]) / (m[2] - m[0])


def _sem_carimbo(d):
    return {k: v for k, v in d.items() if k != 'gerado_em'}


# ------------------------------------------------------------------ juntar e inserir nos caminhos do motor
def test_juntar_vale_em_todo_membro_da_familia():
    fs = _derivar(_b([_h()]))
    for fid in HORIZONTAL:
        d = fs[fid]
        assert d['situacao'] == 'derivado', d['devolucao']
        e = _el(d)
        assert e['quebras'] == {'familia': [{'layer_id': 10, 'aprovadas': [], 'inseridas': [], 'caixa_doc': JUNTADA}]}
        assert e['quebras_origem'] == 'da' and e['origem_geometria'] == 'da'
        assert e['caixa_mestre'] == JUNTADA
        assert e['escala'] == pytest.approx(_escala_da_caixa(e), abs=1e-4)
        contratos.validar(d, nd.ESQUEMA)
    # a outra familia fica como o motor a deixa
    for fid in VERTICAL:
        e = _el(fs[fid])
        assert e['quebras'] == 'congeladas_da_mestre' and 'quebras_origem' not in e


def test_inserir_quebra_no_espaco_fora_da_mestre_propria():
    fs = _derivar(_b([_h(manter=(0,), inseridas=(3,))]))
    for fid in HORIZONTAL:
        e = _el(fs[fid])
        assert fs[fid]['caminho'] in ('transform', 'solver')
        assert e['quebras']['familia'] == [{'layer_id': 10, 'aprovadas': [0], 'inseridas': [3], 'caixa_doc': INSERIDA}]
        assert e['quebras_origem'] == 'da' and e['origem_geometria'] == 'da'
        # a caixa ganha uma entrelinha pela quebra inserida
        assert e['caixa_mestre'] == INSERIDA
        assert e['escala'] == pytest.approx(_escala_da_caixa(e), abs=1e-4)


def test_quebra_na_familia_da_galeria():
    # v1 e v2 trocam de orientacao: saem da versao da galeria, com a caixa da quebra na mestre da galeria
    fs = _derivar(_b([q1._quebra(manter=(0,), inseridas=(3,))]))
    for fid in VERTICAL:
        d = fs[fid]
        assert d['situacao'] == 'derivado' and d['caminho'] == 'galeria', d['devolucao']
        e = _el(d)
        assert e['quebras']['familia'] == [{'layer_id': 10, 'aprovadas': [0], 'inseridas': [3], 'caixa_doc': INSERIDA}]
        assert e['quebras_origem'] == 'da' and e['origem_geometria'] == 'da'
        assert e['caixa_mestre'] == INSERIDA
        assert e['escala'] == pytest.approx(_escala_da_caixa(e), abs=1e-4)
        c = e['caixa']
        # a caixa no formato tem a proporcao da caixa medida, e nao a do texto do KV
        assert (c[2] - c[0]) / (c[3] - c[1]) == pytest.approx(120.0 / 93.0, rel=1e-3)
    for fid in HORIZONTAL:
        assert 'quebras_origem' not in _el(fs[fid])


def test_edicao_de_outro_elemento_mantem_a_quebra_e_a_escala_do_texto():
    mover = [{'elemento': 'el30', 'acao': 'mover', 'dx': 0.01, 'dy': 0.0}]
    fs = _derivar(_b([_h()], edicoes_h=mover))
    for fid in HORIZONTAL:
        d = fs[fid]
        assert d['situacao'] == 'derivado', d['devolucao']
        e = _el(d)
        assert e['quebras']['familia'][0]['caixa_doc'] == JUNTADA
        assert e['quebras_origem'] == 'da' and e['origem_geometria'] == 'da'
        assert e['caixa_mestre'] == JUNTADA
        assert e['escala'] == pytest.approx(_escala_da_caixa(e), abs=1e-4)
        assert _el(d, 'el30')['origem_geometria'] == 'da'


# ------------------------------------------------------------------ texto editado com a quebra da familia (A7)
def test_texto_editado_leva_a_quebra_da_familia_sem_medida():
    editado = [q1._texto('AH VOX OX')]
    fs = _derivar(_b([_h(manter=(), inseridas=(2,))], edicoes_h=editado), medidas=None)
    for fid in HORIZONTAL:
        d = fs[fid]
        assert d['situacao'] == 'derivado', d['devolucao']
        e = _el(d)
        assert e['texto_editado'] == 'AH VOX OX'
        assert e['quebras'] == {'familia': [{'layer_id': 10, 'aprovadas': [], 'inseridas': [2]}]}
        assert e['quebras_origem'] == 'da' and e['origem_geometria'] == 'da'
        assert 'quebras_camada' not in e
    # sem quebra da familia, o texto editado leva so as quebras dele, como no A7
    fs = _derivar(_b([], edicoes_h=editado), medidas=None)
    e = _el(fs['largo'])
    assert e['quebras'] == 'do_texto_editado' and 'quebras_origem' not in e


# ------------------------------------------------------------------ sem medida, faixa e origem
def test_sem_medida_o_formato_volta_ao_da():
    fs = _derivar(_b([_h()]), medidas=None)
    for fid in HORIZONTAL:
        assert fs[fid]['situacao'] == 'devolvido'
        assert fs[fid]['devolucao']['motivo'] == 'quebra_sem_medida'
    fs = _derivar(_b([q1._quebra()]), medidas=None)
    for fid in VERTICAL:
        # a galeria sem a medida da quebra nao sai: o formato fica devolvido, com o registro
        assert fs[fid]['situacao'] == 'devolvido'
        assert any(r['codigo'] == 'quebra_sem_medida' for r in fs[fid]['registros'])


def test_quebra_da_familia_vence_a_da_faixa():
    faixa = {'layer_id': 10, 'razao_min': 0.1, 'razao_max': None, 'quebras': ap.decisao([0])}
    fs = _derivar(_b([faixa, _h()]))
    e = _el(fs['largo'])
    assert e['quebras']['familia'] == [{'layer_id': 10, 'aprovadas': [], 'inseridas': [], 'caixa_doc': JUNTADA}]
    assert e['quebras_origem'] == 'da'


def test_quebra_proposta_pelo_motor_leva_a_origem_dela():
    fs = _derivar(_b([_h(origem='proposta', aprovada=False)], confirmada_h=False))
    for fid in HORIZONTAL:
        e = _el(fs[fid])
        assert e['quebras_origem'] == 'proposta'
        # sem a aprovacao do DA, a caixa nao e dele
        assert e['origem_geometria'] != 'da'
    fs = _derivar(_b([_h(origem='proposta', aprovada=True)]))
    for fid in HORIZONTAL:
        e = _el(fs[fid])
        assert e['quebras_origem'] == 'proposta' and e['origem_geometria'] == 'da'


# ------------------------------------------------------------------ determinismo
def test_derivacao_com_quebra_da_familia_e_deterministica():
    b = _b([_h(manter=(0,), inseridas=(3,)), q1._quebra(manter=(), inseridas=())])
    um, dois = _derivar(b), _derivar(b)
    assert {k: _sem_carimbo(d) for k, d in um.items()} == {k: _sem_carimbo(d) for k, d in dois.items()}


def test_familia_sem_quebra_sai_como_antes():
    sem = _derivar(_b([]))
    com = _derivar(_b([_h()]))
    for fid in VERTICAL:
        assert _sem_carimbo(sem[fid]) == _sem_carimbo(com[fid])
    assert not any('quebras_origem' in e for d in sem.values() for e in d['elementos'])


# ------------------------------------------------------------------ a medida
def test_pedidos_e_pagina_de_medida_levam_a_quebra_inserida():
    b = _b([_h(manter=(0,), inseridas=(3,))])
    assert (10, (0,), (3,)) in mq.pedidos(b)
    c = mq.com_juntadas(q1._laudo()['camadas'][1], [0], [3])
    assert c['texto']['conteudo'] == 'VOX' + q1.Q + 'AH' + q1.Q + 'OX HA' + q1.Q
    assert c['texto']['runs'][0]['texto'] == c['texto']['conteudo']
    # a chave sem inseridas e a de antes (a medida da faixa do M5 continua valendo)
    assert mq.chave(10, [0]) == mq.chave(10, [0], []) == '10:0'
    assert mq.chave(10, [0], [3]) != mq.chave(10, [0])


def test_caixa_medida_ganha_uma_entrelinha_por_quebra_inserida():
    camada = q1._laudo()['camadas'][1]
    sem = mq.caixa_medida(camada, CAIXA_KV, [0], _medida(240.0))
    com = mq.caixa_medida(camada, CAIXA_KV, [0], _medida(240.0), inseridas=[3])
    assert sem == CAIXA_KV
    assert com[3] - com[1] == pytest.approx(sem[3] - sem[1] + ENTRELINHA)


# ------------------------------------------------------------------ o render
def test_render_junta_e_insere_a_quebra_da_familia():
    texto = q1._laudo()['camadas'][1]['texto']
    el = {'quebras': {'familia': [{'layer_id': 10, 'aprovadas': [], 'inseridas': [3], 'caixa_doc': INSERIDA}]}}
    assert rd.quebras_da_entrada(el, {'layer_id': 10, 'texto': texto}) == {'quebras_juntadas': [6],
                                                                        'quebras_inseridas': [3]}
    # a quebra por faixa (M5) so junta, como antes
    el = {'quebras': {'familia': [{'layer_id': 10, 'aprovadas': [0], 'caixa_doc': CAIXA_KV}]}}
    assert rd.quebras_da_entrada(el, {'layer_id': 10, 'texto': texto}) == {'quebras_juntadas': []}


def test_quebras_do_texto_editado_contam_no_texto_novo():
    el = {'quebras': {'familia': [{'layer_id': 10, 'aprovadas': [], 'inseridas': [6]}]},
          'texto_editado': 'AH' + chr(13) + chr(10) + 'VOX OX'}
    # o texto como o render o desenha (AH, LF, VOX OX): CR LF vira uma quebra so, na posicao 2, e o espaco fica na 6
    assert rd.quebras_do_texto_editado(el, 10) == {'quebras_juntadas': [2], 'quebras_inseridas': [6]}
    el['quebras']['familia'][0]['aprovadas'] = [0]
    assert rd.quebras_do_texto_editado(el, 10) == {'quebras_juntadas': [], 'quebras_inseridas': [6]}
    el = {'quebras': {'familia': [{'layer_id': 10, 'aprovadas': [], 'inseridas': [6]}]}, 'texto_editado': 'AH VOX OX'}
    assert rd.quebras_do_texto_editado(el, 10) == {'quebras_juntadas': [], 'quebras_inseridas': [6]}
    assert rd.quebras_do_texto_editado({'quebras': 'do_texto_editado', 'texto_editado': 'AH'}, 10) == {}


def test_so_a_origem_da_quebra_nao_muda_a_impressao_nem_a_diferenca():
    """Revisao 2 do C: a proposta do desdobra que o DA aprovou vira a quebra do DA nas mesmas posicoes (ele clica o
    mesmo vao de novo). O formato desenha o mesmo: a impressao fica igual (a aprovacao nao cai) e a diferenca nao diz
    que a quebra mudou. quebras_origem continua na derivacao, para o DA saber de onde veio a quebra."""
    from desdobra.derivacao import impressao as mi
    proposta = _b([_h(manter=(0,), inseridas=(3,), origem='proposta', aprovada=True)])
    do_da = _b([_h(manter=(0,), inseridas=(3,), origem='da', aprovada=True)])
    fp, fd = _derivar(proposta), _derivar(do_da)
    for fid in HORIZONTAL:
        assert _el(fp[fid])['quebras_origem'] == 'proposta' and _el(fd[fid])['quebras_origem'] == 'da'
        assert _el(fp[fid])['quebras'] == _el(fd[fid])['quebras']
        cp = mi.corpo(fp[fid], mi.resolvido(proposta, mb.resolver(q1._laudo(), proposta)[0]), fid)
        cd = mi.corpo(fd[fid], mi.resolvido(do_da, mb.resolver(q1._laudo(), do_da)[0]), fid)
        assert mi.do_corpo(cp) == mi.do_corpo(cd)
        assert mdif.diferencas(cp, cd) == []
    # a quebra que muda de verdade continua dizendo que mudou
    a = {'id': 'el10', 'funcao': 'titulo', 'quebras': {'familia': []}, 'quebras_origem': 'proposta'}
    b = dict(a, quebras={'familia': [{'layer_id': 10, 'aprovadas': [], 'inseridas': [3]}]})
    assert [i['tipo'] for i in mdif._do_elemento('el10', a, b, None)] == ['quebra']
