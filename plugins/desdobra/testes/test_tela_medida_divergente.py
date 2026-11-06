# -*- coding: utf-8 -*-
"""Revisao dos becos, D2: o formato da folha com a medida divergente (duas leituras, valor nulo) nunca sai do job em
silencio.

Na importacao, a chave do formato sai da medida, e a medida divergente nao tem valor: o formato fica sem chave e os
formatos do job o deixavam de fora. Agora:
  - enquanto o DA nao escolhe a medida, o passo 1 lista o formato em Valores de spec com as duas leituras (o botao
    "Usar este valor"), nomeado pelo que a folha diz, e nunca pelo identificador interno; a lista do que falta traz um
    item que leva ao passo 1; "Salvar e seguir" recusa com a pendencia formato_sem_medida;
  - depois da escolha, a chave do formato e montada (a escolha vem depois das chaves na importacao), sem mexer na chave
    de nenhum formato que ja tinha a sua, e o formato entra nos formatos do job e no briefing como qualquer outro.
Tudo sintetico: um e-mail de specs inventado e a proposta de mapeamento do modo b, que liga um segundo trecho a medida
do mesmo formato."""
import json

import pytest

import test_specs as tsp
from desdobra import contratos, humano
from desdobra.briefing import modelo as mb
from desdobra.specs import confirmar, importar
from desdobra.tela import estado as te

EMAIL = 'Formato: 1080x1920\nPeso máximo: 15 MB\nMedida da arte 1080x1350\nFormato: 1080x1350\nPeso máximo: 10 MB\n'


def _proposta(doc, pedaco, campo):
    t = next((f['id'], t['id']) for f in doc['folhas'] for t in f['trechos'] if pedaco in t['texto'])
    return {'folha': t[0], 'trecho': t[1], 'campo': campo}


@pytest.fixture
def job(tmp_path):
    """Importacao de verdade de uma folha de teste no modo b: a proposta liga "Medida da arte 1080x1350" a medida do
    primeiro formato, que ja tem 1080x1920, e a medida fica divergente."""
    def props(doc):
        primeiro = next(f for f in doc['formatos'] if f['id'].endswith('-e01'))
        return [dict(_proposta(doc, 'Medida da arte', 'dimensao'), alvo=primeiro['id'])]
    return tsp._job_com_propostas(tmp_path, EMAIL, props)


def _rascunho(job):
    return contratos.ler(job / 'specs' / 'rascunho.json', 'spec/1')


def _divergente(doc):
    return next(f for f in doc['formatos'] if f['id'].endswith('-e01'))


def _disparo():
    return humano.exigir_tela(confirmar.COMANDO, humano.abrir_sessao_tela(teste=True), confirmado=True)


def _escolher(job, indice_de_valor):
    vid = _divergente(_rascunho(job))['campos']['dimensao']['id']
    alvo = next(x for x in te.specs_pendentes(job) if x['valor_id'] == vid)
    i = next(lei['indice'] for lei in alvo['leituras'] if lei['descricao'].startswith(indice_de_valor))
    return confirmar.confirmar_da_tela(job, vid, i, disparo=_disparo())


def test_importacao_deixa_a_medida_divergente_sem_chave(job):
    doc = importar.importar(job)[0]
    f = _divergente(doc)
    dim = f['campos']['dimensao']
    assert dim['valor'] is None and len(dim['leituras']) == 2 and 'fontes_divergentes' in dim['alertas']
    assert f['chave'] is None
    # o outro formato tem a chave dele, e o divergente ainda nao entra nos formatos do briefing
    assert [x['chave'].rsplit('|', 1)[1] for x in mb.formatos_das_specs(job)] == ['1080x1350']


def test_passo_1_lista_o_formato_sem_medida_e_salvar_recusa(job):
    from desdobra.briefing import salvar
    importar.importar(job)
    sem = te.formatos_sem_medida(job)
    assert len(sem) == 1 and sem[0]['texto'] == '1080 x 1920 px ou 1080 x 1350 px', sem
    # Valores de spec: o formato aparece com as duas leituras e o nome do que a folha diz
    item = next(x for x in te.specs_pendentes(job) if x['valor_id'] == sem[0]['valor_id'])
    assert [lei['descricao'] for lei in item['leituras']] == ['1080 x 1920 px', '1080 x 1350 px']
    assert item['onde'] == te.ONDE_SEM_MEDIDA % sem[0]['texto']
    assert _divergente(_rascunho(job))['id'] not in item['onde']
    # o que falta: um item que leva ao passo 1
    lido_ = {'modo_dados': {'escolhido': 'b'}, 'bloqueios': [], 'paradas': [], 'camadas_bloqueadas': [],
             'linkados': [], 'specs': {'pendentes': 0, 'formatos': [{'id': 'x', 'rotacao': {'graus': 0}}],
                                       'folhas': 1, 'sem_medida': sem},
             'quadros': [], 'fontes_que_faltam': []}
    falta = [x for x in te.faltam(lido_, {}) if x['texto'] == te.MEDIDA_A_ESCOLHER_FALTA]
    assert falta == [{'texto': te.MEDIDA_A_ESCOLHER_FALTA, 'detalhe': '1080 x 1920 px ou 1080 x 1350 px',
                      'ir': {'passo': 'lido'}}]
    for texto in (te.MEDIDA_A_ESCOLHER_FALTA, te.ONDE_SEM_MEDIDA):
        assert '—' not in texto and '–' not in texto and 'motor' not in texto.lower()
    # Salvar e seguir recusa enquanto a medida espera a escolha
    pend = salvar.pendencias(job, {'familias': {}})
    assert {'codigo': 'formato_sem_medida', 'formatos': ['1080 x 1920 px ou 1080 x 1350 px']} in pend


def test_escolha_da_leitura_monta_a_chave_sem_mexer_nas_outras(job):
    from desdobra.briefing import salvar
    doc0 = importar.importar(job)[0]
    outro0 = next(f for f in doc0['formatos'] if not f['id'].endswith('-e01'))
    ids0 = {f['chave']: f['id'] for f in mb.formatos_das_specs(job)}
    # a leitura escolhida e a mesma medida do outro formato do mesmo circuito: a chave do outro fica como estava
    assert _escolher(job, '1080 x 1350') is not None
    doc = _rascunho(job)
    f = _divergente(doc)
    outro = next(x for x in doc['formatos'] if x['id'] == outro0['id'])
    assert outro['chave'] == outro0['chave']
    assert f['chave'] == '%s#%s' % (outro0['chave'], f['id'])
    assert f['campos']['dimensao']['situacao'] == 'confirmado'
    assert te.formatos_sem_medida(job) == []
    assert not [x for x in salvar.pendencias(job, {'familias': {}}) if x['codigo'] == 'formato_sem_medida']
    # entra nos formatos do briefing com a medida escolhida, e o id do outro fica
    novos = {x['chave']: x for x in mb.formatos_das_specs(job)}
    assert (novos[f['chave']]['largura'], novos[f['chave']]['altura']) == (1080, 1350)
    assert novos[outro0['chave']]['id'] == ids0[outro0['chave']]
    # e nos formatos do job, como os confirmados
    do_job = json.loads((job / mb.ARQUIVO_FORMATOS).read_text(encoding='utf-8'))
    assert f['chave'] in [x['chave'] for x in do_job['formatos']]


def test_escolha_da_outra_leitura_da_a_chave_da_medida(job):
    importar.importar(job)
    assert _escolher(job, '1080 x 1920') is not None
    f = _divergente(_rascunho(job))
    assert f['chave'].endswith('|1080x1920') and '#' not in f['chave']
    assert f['chave'] in [x['chave'] for x in mb.formatos_das_specs(job)]


def test_os_outros_valores_do_formato_sem_medida_tambem_aparecem_pelo_que_a_folha_diz(job):
    """Revisao 4: o peso maximo do formato sem medida tambem espera o DA; ele aparece pelas medidas da folha, nunca
    pelo id interno, e a janela da confirmacao diz a frase sem repetir a palavra formato."""
    from desdobra.tela import atos as ta
    importar.importar(job)
    div = _divergente(_rascunho(job))
    sem = te.formatos_sem_medida(job)[0]
    do_formato = [x for x in te.specs_pendentes(job) if x['valor_id'].startswith(div['id'] + '/')]
    assert len(do_formato) >= 2, do_formato
    for x in do_formato:
        assert x['onde'] == te.ONDE_SEM_MEDIDA % sem['texto'] and div['id'] not in x['onde'], x
    texto = ta.atos_do_job(job)['spec_valor'].texto
    peso = next(x for x in do_formato if not x['leituras'])
    frases = [texto({'valor_id': peso['valor_id']}), texto({'valor_id': sem['valor_id'], 'leitura': 0})]
    for frase in frases:
        assert div['id'] not in frase and 'formato formato' not in frase.lower(), frase
        assert frase.count('formato') == 1, frase
        assert '—' not in frase and '–' not in frase
    assert frases[1].startswith('No formato da folha com duas medidas (%s), o campo dimensão passa a valer '
                                '1080 x 1920 px' % sem['texto']), frases[1]


def test_terceira_entrada_do_mesmo_tamanho_leva_o_sufixo_e_o_alerta(tmp_path):
    """Revisao 4: com duas entradas do mesmo tamanho ja sufixadas (K#a, K#b), a leitura K escolhida no formato
    divergente tambem repete K: leva o sufixo do id e o alerta chave_repetida, e as chaves das outras ficam."""
    email = ('Formato: 1080x1920\nMedida da arte 1080x1350\nFormato: 1080x1350\nPeso máximo: 10 MB\n'
             'Formato: 1080x1350\nPeso máximo: 5 MB\n')

    def props(doc):
        primeiro = next(f for f in doc['formatos'] if f['id'].endswith('-e01'))
        return [dict(_proposta(doc, 'Medida da arte', 'dimensao'), alvo=primeiro['id'])]
    job = tsp._job_com_propostas(tmp_path, email, props)
    doc0 = importar.importar(job)[0]
    antes = {f['id']: f['chave'] for f in doc0['formatos'] if f['chave']}
    assert len(antes) == 2 and all('#' in k for k in antes.values())
    assert _escolher(job, '1080 x 1350') is not None
    doc = _rascunho(job)
    f = _divergente(doc)
    base = next(iter(antes.values())).split('#', 1)[0]
    assert f['chave'] == '%s#%s' % (base, f['id']) and 'chave_repetida' in f['alertas'], f
    assert {x['id']: x['chave'] for x in doc['formatos'] if x['id'] in antes} == antes
