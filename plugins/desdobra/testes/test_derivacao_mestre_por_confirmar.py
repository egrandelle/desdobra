# -*- coding: utf-8 -*-
"""Revisao dos becos, D3: a mestre propria do DA num formato que espera um valor de spec.

A base da mestre propria sai das areas do formato dela. Enquanto um valor que a derivacao le (a medida, a faixa, a area
util ou a area segura) desse formato espera a confirmacao do DA, a derivacao nunca usa o valor sem confirmacao: o
formato da mestre fica spec_por_confirmar e os outros formatos que derivam dessa mestre tambem esperam, devolvidos com
motivo proprio (mestre_por_confirmar). Na tela, eles ficam sem galeria, a familia deles nao pode ser confirmada, a lista
do que falta leva o DA a Valores de spec, no passo 1, e "Salvar e seguir" recusa.
Tudo sintetico: o laudo e o briefing minimos de test_derivacao_apoio e uma folha em memoria."""
import copy
import json

import test_derivacao_apoio as ap
from desdobra.briefing import modelo as mb
from desdobra.derivacao import formatos as mf
from desdobra.derivacao import nucleo as nd
from desdobra.tela import estado as te

CHAVE = 'teste|circuito|300x600'
CAIXAS = {1: [0, 0, 300, 600], 10: [20, 40, 280, 140], 20: [20, 200, 280, 230], 30: [200, 440, 280, 520],
          40: [20, 525, 180, 545]}


def _sem_travessao(texto):
    return '—' not in texto and '–' not in texto and 'motor' not in texto.lower()


def _briefing():
    propria = {'id': 'vertical', 'tipo': 'propria', 'formato': 'v300',
               'elementos': [{'layer_id': k, 'caixa': v, 'quebras': 'origem'} for k, v in sorted(CAIXAS.items())]}
    formatos = [ap.formato('mesmo', 800, 400), ap.formato('v300', 300, 600, chave=CHAVE),
                ap.formato('v320', 320, 560)]
    return ap.briefing(formatos=formatos, mestres=[{'id': 'kv', 'tipo': 'kv'}, propria])


def _derivar(pasta, faixa_confirmada):
    """Grava o rascunho das specs (a medida do 300x600 confirmada, a faixa em rascunho ou confirmada) e os formatos do
    job como specs.modelo.formatos_do_job grava, e deriva em memoria."""
    y = ap.spec(CHAVE, {'dimensao': {'largura': 300, 'altura': 600}, 'faixas': [{'lado': 'inferior', 'px': 48}]})
    y['campos']['dimensao']['situacao'] = 'confirmado'
    if faixa_confirmada:
        y['campos']['faixas']['situacao'] = 'confirmado'
    do_job = copy.deepcopy(y)
    do_job['campos'] = {k: v for k, v in do_job['campos'].items() if v['situacao'] == 'confirmado'}
    (pasta / 'specs').mkdir(exist_ok=True)
    (pasta / mb.ARQUIVO_RASCUNHO_SPECS).write_text(json.dumps({'formatos': [y]}), encoding='utf-8')
    (pasta / mb.ARQUIVO_FORMATOS).write_text(json.dumps({'tipo': 'formatos_do_job', 'formatos': [do_job]}),
                                             encoding='utf-8')
    specs, arq = mf.specs_do_job(pasta)
    return nd.derivar_em_memoria(nd.contexto(ap.laudo(), _briefing(), pasta=pasta), specs=specs, arquivo_specs=arq)


def _motivos(r):
    return {k: (d['situacao'], (d['devolucao'] or {}).get('motivo')) for k, d in r['formatos'].items()}


def test_formato_da_mestre_propria_com_spec_por_confirmar_faz_a_familia_esperar(tmp_path):
    r = _derivar(tmp_path, faixa_confirmada=False)
    assert mf.chaves_por_confirmar(tmp_path) == {CHAVE}
    m = _motivos(r)
    assert m['v300'] == ('devolvido', 'spec_por_confirmar')
    # o formato que deriva da mestre propria espera com ela, e nunca deriva de uma base com o valor sem confirmacao
    assert m['v320'] == ('devolvido', 'mestre_por_confirmar'), m
    d = r['formatos']['v320']
    assert d['mestre']['id'] == 'vertical' and not d['elementos']
    assert d['devolucao']['medidas']['formato_da_mestre'] == 'v300'
    assert d['devolucao']['medidas']['chave_da_mestre'] == CHAVE
    # o formato que deriva do KV segue
    assert m['mesmo'][0] == 'derivado'
    assert {x['formato']: x['motivo'] for x in r['devolucoes']} == {'v300': 'spec_por_confirmar',
                                                                   'v320': 'mestre_por_confirmar'}
    assert _sem_travessao(nd.O_QUE_FAZER['mestre_por_confirmar'])
    assert 'Valores de spec' in nd.O_QUE_FAZER['mestre_por_confirmar']


def test_com_a_spec_da_mestre_confirmada_a_familia_deriva(tmp_path):
    r = _derivar(tmp_path, faixa_confirmada=True)
    assert mf.chaves_por_confirmar(tmp_path) == set()
    m = _motivos(r)
    assert m['v300'] == ('derivado', None) and m['v320'] == ('derivado', None), m
    assert r['formatos']['v320']['mestre']['id'] == 'vertical'


def test_tela_trata_a_familia_da_mestre_por_confirmar_como_a_spec_por_confirmar(tmp_path):
    """Sem galeria, sem confirmacao da familia, e o que falta leva ao passo 1 com o texto da mestre."""
    r = _derivar(tmp_path, faixa_confirmada=False)
    pend = te.por_confirmar(r['formatos'])
    assert pend == {'v300', 'v320'}
    assert te.texto_da_devolucao('mestre_por_confirmar') == te.MESTRE_POR_CONFIRMAR
    assert 'Valores de spec' in te.MESTRE_POR_CONFIRMAR and 'passo 1' in te.MESTRE_POR_CONFIRMAR
    assert _sem_travessao(te.MESTRE_POR_CONFIRMAR) and _sem_travessao(te.MESTRE_POR_CONFIRMAR_FALTA)
    lido_ = {'modo_dados': {'escolhido': 'c'}, 'bloqueios': [], 'paradas': [], 'camadas_bloqueadas': [],
             'linkados': [], 'specs': {'pendentes': 0, 'formatos': [{'id': 'v300', 'rotacao': {'graus': 0}}],
                                       'folhas': 1},
             'quadros': [], 'fontes_que_faltam': []}
    familias = {'g1': ['v300', 'v320']}
    itens = te.faltam(lido_, {k: r['formatos'][k] for k in ('v300', 'v320')}, {}, familias,
                      te.familias_confirmadas(tmp_path, familias, pend))
    assert not [x for x in itens if x['texto'] == te.FAMILIA_SEM_CONFIRMACAO]
    mestre = [x for x in itens if x['texto'] == te.MESTRE_POR_CONFIRMAR_FALTA]
    assert [x['detalhe'] for x in mestre] == ['v320'] and mestre[0]['ir'] == {'passo': 'lido'}
    assert [x['detalhe'] for x in itens if x['texto'] == te.SPEC_POR_CONFIRMAR_FALTA] == [CHAVE]
    assert not [x for x in itens if x['texto'].startswith('Sem proposta')]


def test_botao_da_familia_desliga_tambem_com_a_mestre_por_confirmar():
    """O tela.js desliga "Confirmar familia" pelos dois motivos, com o texto da mestre no segundo."""
    from desdobra.tela import estatico
    js = (estatico.PASTA_TELA / 'tela.js').read_text(encoding='utf-8')
    assert "'mestre_por_confirmar'" in js and "'spec_por_confirmar'" in js
    assert 'FAMILIA_SEM_SPEC_DA_MESTRE' in js
