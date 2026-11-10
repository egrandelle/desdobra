# -*- coding: utf-8 -*-
"""Quebra de linha da familia da tela (M7b, C1; decisoes-v1.md, 167 e 171; secao 9.8 da arquitetura, editor de
mestre), escrita antes do codigo.

A quebra que o DA poe ou tira na familia vai em quebras_por_familia, ligada a familia da tela (familia, com os formatos
dela): os indices das quebras gravadas que ficam (quebras, como antes) e as posicoes de espaco que viram quebra
(inseridas, como na mestre propria). Criterios cobertos aqui:
  - a quebra da familia passa no esquema, na conferencia, e grava e rele igual;
  - a posicao inserida tem de cair num espaco do texto de agora: o do KV ou o editado pelo DA na familia (171); fora de
    espaco, a conferencia recusa;
  - a quebra de familia que o briefing nao tem, ou com outros formatos, e recusada;
  - a quebra que o DA faz ou tira vale aprovada pelo proprio ato (origem da); a proposta pelo motor so vale aprovada, e
    a familia confirmada com quebra proposta sem aprovacao e recusada;
  - duas quebras do mesmo texto na mesma familia conflitam; a da familia nao se mede contra a da faixa (M5);
  - a impressao do formato (fase A) leva a quebra da familia: muda nos formatos da familia e fica igual nos outros, e a
    diferenca diz que a quebra mudou.
Material sintetico (test_derivacao_apoio)."""
import pytest

import test_derivacao_apoio as ap
from desdobra import contratos
from desdobra.briefing import modelo as mb
from desdobra.derivacao import diferenca as mdif
from desdobra.derivacao import impressao as mi
from desdobra.derivacao import nucleo as nd

Q = chr(13)
TEXTO = 'VOX AH' + Q + 'OX HA' + Q
# espacos de TEXTO nas posicoes 3 e 9; a quebra gravada (a unica que abre linha) na 6
FUN = {1: 'fundo', 10: 'titulo', 30: 'logo_principal'}
CONF = {'origem': 'fixture_de_teste', 'meio': 'medicao', 'em': '2026-11-10T10:00:00-03:00'}
CODIGOS_DA_QUEBRA = {'quebra_fora_de_espaco', 'quebra_aprovada_invalida', 'quebra_fora_da_familia',
                     'quebra_proposta_sem_aprovacao', 'quebras_conflitantes', 'quebra_em_caixa_de_paragrafo',
                     'quebra_para_formato_inexistente', 'pendente_obrigatorio'}


def _laudo():
    c = ap.camada(10, 'texto', [20, 40, 260, 110], corpo=30)
    c['texto'].update({'conteudo': TEXTO, 'paragrafos': [], 'justificacao': 'LEFT', 'tipo_caixa': 'ponto'})
    c['texto']['runs'][0].update({'inicio': 0, 'fim': len(TEXTO), 'texto': TEXTO, 'entrelinha_efetiva_px': 23.0})
    return ap.laudo(400, 200, [ap.camada(1, 'pixel', [0, 0, 400, 200]), c,
                               ap.camada(30, 'smart_embutido', [330, 150, 380, 185])])


def _quebra(manter=(0,), inseridas=(3,), familia='vertical-1', formatos=('v1', 'v2'), origem='da', aprovada=True,
            layer_id=10):
    return {'layer_id': layer_id, 'familia': familia, 'formatos': list(formatos), 'quebras': ap.decisao(list(manter)),
            'inseridas': list(inseridas), 'origem': origem, 'aprovada': aprovada}


def _b(quebras, edicoes=None, edicoes_largo=None, confirmada=True):
    b = ap.briefing(funcoes=FUN, formatos=[ap.formato('v1', 300, 600), ap.formato('v2', 320, 600),
                                           ap.formato('largo', 760, 240)])
    b['composicoes'] = [
        {'familia': 'vertical-1', 'formatos': ['v1', 'v2'], 'versao': None, 'edicoes': list(edicoes or []),
         'confirmada': confirmada, 'confirmacao': dict(CONF) if confirmada else None},
        {'familia': 'horizontal-1', 'formatos': ['largo'], 'versao': None, 'edicoes': list(edicoes_largo or []),
         'confirmada': True, 'confirmacao': dict(CONF)}]
    if quebras:
        b['quebras_por_familia'] = quebras
    return b


def _codigos(b):
    contratos.validar(b, mb.ESQUEMA)
    return {e['codigo'] for e in mb.conferir(_laudo(), b)} & CODIGOS_DA_QUEBRA


def _texto(t):
    return {'elemento': 'el10', 'acao': 'texto', 'texto': t}


# ------------------------------------------------------------------ grava e rele
def test_quebra_da_familia_no_espaco_passa_grava_e_rele_igual(tmp_path):
    b = _b([_quebra()])
    contratos.validar(b, mb.ESQUEMA)
    assert mb.conferir(_laudo(), b) == []
    arq = tmp_path / 'briefing-confirmado.json'
    contratos.gravar(arq, b, mb.ESQUEMA)
    assert contratos.ler(arq, mb.ESQUEMA) == b
    # juntar a quebra gravada (nenhum indice fica) e inserir nos dois espacos tambem vale
    assert _codigos(_b([_quebra(manter=(), inseridas=(3, 9))])) == set()


# ------------------------------------------------------------------ a posicao cai num espaco do texto de agora
@pytest.mark.parametrize('pos', [1, 6, 7, 99])
def test_posicao_fora_de_espaco_e_recusada(pos):
    # 1 e 7 sao letras, 6 e a quebra gravada, 99 passa do fim do texto
    assert 'quebra_fora_de_espaco' in _codigos(_b([_quebra(inseridas=(pos,))]))


def test_indice_de_quebra_que_o_texto_nao_tem_e_recusado():
    assert 'quebra_aprovada_invalida' in _codigos(_b([_quebra(manter=(1,), inseridas=())]))


def test_quebra_no_texto_editado_vale_para_o_texto_da_familia():
    # o texto editado na familia (171) e o texto de agora: o espaco dele vale, o do KV que la e letra nao
    editado = [_texto('AH VOX OX')]
    assert _codigos(_b([_quebra(manter=(), inseridas=(2,))], edicoes=editado)) == set()
    assert 'quebra_fora_de_espaco' in _codigos(_b([_quebra(manter=(), inseridas=(3,))], edicoes=editado))
    # o texto editado nao tem quebra gravada: o indice 0 do KV nao existe nele
    assert 'quebra_aprovada_invalida' in _codigos(_b([_quebra(manter=(0,), inseridas=())], edicoes=editado))
    # a ultima edicao de texto vale
    duas = [_texto('AH VOX OX'), _texto('VOXAH OX')]
    assert _codigos(_b([_quebra(manter=(), inseridas=(5,))], edicoes=duas)) == set()
    assert 'quebra_fora_de_espaco' in _codigos(_b([_quebra(manter=(), inseridas=(2,))], edicoes=duas))


def test_quebra_do_texto_editado_conta_como_o_render_o_desenha():
    # o render troca CR LF e CR por LF (render.derivado.texto_editado_na_entrada): CR LF e uma quebra so
    editado = [_texto('AH' + Q + '\nVOX OX')]
    assert _codigos(_b([_quebra(manter=(0,), inseridas=(6,))], edicoes=editado)) == set()
    assert 'quebra_aprovada_invalida' in _codigos(_b([_quebra(manter=(1,), inseridas=())], edicoes=editado))


def test_texto_editado_em_outra_familia_nao_muda_o_texto_desta():
    editado = [_texto('AH VOX OX')]
    assert _codigos(_b([_quebra(manter=(), inseridas=(3,))], edicoes_largo=editado)) == set()
    assert 'quebra_fora_de_espaco' in _codigos(_b([_quebra(manter=(), inseridas=(2,))], edicoes_largo=editado))


def test_camada_que_nao_e_texto_e_recusada():
    assert 'quebra_aprovada_invalida' in _codigos(_b([_quebra(layer_id=30, manter=(), inseridas=())]))


# ------------------------------------------------------------------ a familia
def test_quebra_de_familia_que_o_briefing_nao_tem_e_recusada():
    assert 'quebra_fora_da_familia' in _codigos(_b([_quebra(familia='vertical-9')]))
    # a familia existe, mas a quebra diz outros formatos (a familia ganhou ou perdeu formato)
    assert 'quebra_fora_da_familia' in _codigos(_b([_quebra(formatos=('v1',))]))


# ------------------------------------------------------------------ origem e aprovacao
def test_quebra_proposta_vale_so_aprovada_na_familia_confirmada():
    assert 'quebra_proposta_sem_aprovacao' in _codigos(_b([_quebra(origem='proposta', aprovada=False)]))
    assert _codigos(_b([_quebra(origem='proposta', aprovada=True)])) == set()
    # na familia sem confirmacao, a quebra proposta ainda espera o DA
    assert 'quebra_proposta_sem_aprovacao' not in _codigos(_b([_quebra(origem='proposta', aprovada=False)],
                                                              confirmada=False))


@pytest.mark.parametrize('mexe', [
    lambda q: q.update(aprovada=False),                  # a quebra do DA vale aprovada pelo proprio ato
    lambda q: q.update(origem='motor'),                  # so da ou proposta
    lambda q: q.pop('inseridas'),                        # a quebra da familia diz o que insere (mesmo vazio)
    lambda q: q.pop('aprovada'),
    lambda q: q.pop('formatos'),
    lambda q: q.update(razao_min=0.4),                   # a familia da tela e a lista dos formatos, nunca a faixa
    lambda q: q.update(inseridas=[3, 3]),
    lambda q: q.update(familia='Vertical 1'),
])
def test_esquema_recusa_quebra_da_familia_mal_formada(mexe):
    q = _quebra()
    mexe(q)
    with pytest.raises(contratos.ErroContrato):
        contratos.validar(_b([q]), mb.ESQUEMA)


def test_esquema_recusa_insercao_fora_da_familia_da_tela():
    # a quebra da faixa (M5) so junta: inserir, origem e aprovacao sao da quebra da familia da tela
    for extra in ({'inseridas': [3]}, {'origem': 'da'}, {'aprovada': True}):
        q = dict({'layer_id': 10, 'razao_min': 2.0, 'razao_max': None, 'quebras': ap.decisao([0])}, **extra)
        with pytest.raises(contratos.ErroContrato):
            contratos.validar(_b([q]), mb.ESQUEMA)


# ------------------------------------------------------------------ conflito
def test_duas_quebras_do_mesmo_texto_na_familia_conflitam():
    assert 'quebras_conflitantes' in _codigos(_b([_quebra(inseridas=(3,)), _quebra(inseridas=(9,))]))
    # textos diferentes, ou familias diferentes, nao
    outra = _quebra(familia='horizontal-1', formatos=('largo',), inseridas=(9,))
    assert 'quebras_conflitantes' not in _codigos(_b([_quebra(inseridas=(3,)), outra]))


def test_quebra_da_familia_nao_conflita_com_a_da_faixa():
    faixa = {'layer_id': 10, 'razao_min': 0.1, 'razao_max': 1.0, 'quebras': ap.decisao([])}
    assert 'quebras_conflitantes' not in _codigos(_b([faixa, _quebra()]))


# ------------------------------------------------------------------ impressao por formato (fase A)
def _impressoes(b):
    laudo = _laudo()
    ctx = nd.contexto(laudo, b)
    res = mi.resolvido(ctx['briefing'], ctx['resolvidas'])
    d = {'elementos': [{'id': 'el10', 'layer_ids': [10]}], 'mestre': {'tipo': 'kv'}}
    return {fid: mi.corpo(d, res, fid) for fid in ('v1', 'v2', 'largo')}


def test_impressao_muda_so_nos_formatos_da_familia_da_quebra():
    antes = _impressoes(_b([_quebra(inseridas=(3,))]))
    for mexida in (_quebra(inseridas=(9,)), _quebra(manter=(), inseridas=(3,))):
        depois = _impressoes(_b([mexida]))
        for fid in ('v1', 'v2'):
            assert mi.do_corpo(antes[fid]) != mi.do_corpo(depois[fid]), fid
            frases = [i['frase'] for i in mdif.diferencas(antes[fid], depois[fid])]
            assert any('quebras de linha' in f for f in frases), frases
        assert mi.do_corpo(antes['largo']) == mi.do_corpo(depois['largo'])
    # sem quebra da familia, a impressao e a de antes desta fase (nenhuma chave nova)
    sem = _impressoes(_b([]))
    assert sem['v1']['entradas']['quebras'] == []


def test_quebra_da_familia_entra_na_impressao_por_cima_da_faixa():
    faixa = {'layer_id': 10, 'razao_min': 0.1, 'razao_max': 1.0, 'quebras': ap.decisao([])}
    so_faixa = _impressoes(_b([faixa]))
    com = _impressoes(_b([faixa, _quebra()]))
    assert mi.do_corpo(so_faixa['v1']) != mi.do_corpo(com['v1'])
    assert com['v1']['entradas']['quebras'] == [[10, [0], [3]]]
    assert so_faixa['v1']['entradas']['quebras'] == [[10, []]]
    assert so_faixa['largo'] == com['largo']
