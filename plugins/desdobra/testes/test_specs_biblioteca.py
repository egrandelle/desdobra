# -*- coding: utf-8 -*-
"""Biblioteca inicial de specs (biblioteca-specs/): perfis versionados da Eletromidia PME e da Globo Ads, com os
valores extraidos e a citacao da folha, sem a folha. E, quando as folhas publicas estao na maquina (fora do
repositorio, na pasta apontada pela variavel DESDOBRA_FOLHAS_SPECS, com as subpastas eletromidia-pme e globo-ads), o criterio do M3 sobre a folha
real: as 25 entradas e os 10 tamanhos da PME aparecem, e o perfil bate com o que o motor extrai de novo."""
import os
import shutil
from pathlib import Path

import pytest

from conftest import RAIZ_PLUGIN, psd_minimo
from desdobra import contratos
from desdobra.job import nucleo
from desdobra.specs import importar, modelo

BIBLIOTECA = RAIZ_PLUGIN / 'biblioteca-specs'
PME = BIBLIOTECA / 'eletromidia-pme-1.json'
GLOBO = BIBLIOTECA / 'globo-ads-1.json'


def _pasta_folhas():
    env = os.environ.get('DESDOBRA_FOLHAS_SPECS')
    p = Path(env) if env else None
    return p if p and (p / 'eletromidia-pme').is_dir() and (p / 'globo-ads').is_dir() else None


def _px(doc):
    return [f for f in doc['formatos'] if f['campos']['dimensao']['unidade'] == 'px']


def _tamanhos(formatos):
    return {(f['campos']['dimensao']['valor']['largura'], f['campos']['dimensao']['valor']['altura']) for f in formatos}


@pytest.fixture(scope='module')
def perfis():
    return importar.perfil_da_biblioteca(PME), importar.perfil_da_biblioteca(GLOBO)


def test_perfis_validos_versionados_e_sem_valor_confirmado(perfis):
    for p in perfis:
        assert p['tipo'] == 'perfil' and p['perfis'][0]['versao'] == 1 and p['job_id'] is None
        assert modelo.conferir_literais(p) == []
        assert {v['situacao'] for _r, _c, v in modelo.todos_os_valores(p)} <= {'rascunho', 'registro'}
        for f in p['folhas']:
            assert '/' not in f['arquivo'] and f['recortes'] == []
            # so os trechos citados, nunca a folha inteira
            assert len(f['trechos']) < 400
    assert importar.carregar_biblioteca(BIBLIOTECA)


def test_perfil_pme_25_entradas_em_10_tamanhos_e_as_armadilhas(perfis):
    pme = perfis[0]
    px = _px(pme)
    assert len(px) == 25 and len(_tamanhos(px)) == 10 and len(pme['formatos']) == 26
    chaves = {f['chave'] for f in px if f['chave'].endswith('|1080x1920')}
    utils = {f['campos']['area_util']['valor']['altura'] for f in px if f['chave'].endswith('|1080x1920')}
    assert len(chaves) > 2 and utils == {1920, 1848}
    assert any(f['campos']['faixas']['valor'] == [{'lado': 'inferior', 'px': 48}] for f in px)
    impresso = next(f for f in pme['formatos'] if f['chave'].endswith('120x175m'))
    assert 'unidade_incoerente' in impresso['campos']['dimensao']['alertas']
    assert 'virgula_decimal' in impresso['campos']['area_util']['alertas']
    pracas = [c['campos']['praca'] for c in pme['circuitos'] if c['campos']['praca']['valor']]
    assert any('praca_mista' in p['alertas'] for p in pracas)
    assert pme['veiculadores'][0]['campos']['nome']['valor'] == 'Eletromidia'


def test_perfil_globo_tetos_area_segura_borda_e_meia_pagina(perfis):
    globo = perfis[1]
    por_chave = {f['chave']: f for f in globo['formatos']}
    vertical = por_chave['globo-ads|publicidade-vertical-display|1080x1920']['campos']
    assert vertical['peso_max']['valor']['alvo_bytes'] == 500000
    assert vertical['area_segura']['valor'] == {'pct': 14, 'px': 250, 'lados': ['inferior', 'superior']}
    meia = por_chave['globo-ads|half-page|300x600']['campos']
    assert meia['peso_max_hospedado']['valor']['alvo_bytes'] == 250000
    assert meia['peso_max_tag_carga_inicial']['valor']['alvo_bytes'] == 250000
    assert meia['peso_max_tag_carga_posterior']['valor']['alvo_bytes'] == 500000
    tag = meia['peso_max_tag']
    assert tag['valor'] is None and 'fontes_divergentes' in tag['alertas']
    leituras = {x['valor']['alvo_bytes']: x['fonte']['folha'] for x in tag['leituras']}
    folhas = {f['id']: f['arquivo'] for f in globo['folhas']}
    assert folhas[leituras[550000]] == 'half-page.html' and folhas[leituras[500000]] == 'orientacoes-gerais.html'
    assert '1248x250' in ' '.join(por_chave)
    veic = globo['veiculadores'][0]
    assert veic['campos']['borda_1px']['forma'] == 'condicional' and veic['campos']['borda_1px']['valor']['espessura_px'] == 1
    tetos = [l['campos']['peso_max_tag_carga_posterior']['valor']['alvo_bytes'] for l in veic['tetos_por_tamanho']]
    assert tetos == [100000, 150000, 300000, 400000, 500000]
    assert veic['campos']['qualidade_jpg_recomendada']['situacao'] == 'registro'


# ------------------------------------------------------------------ folhas reais (fora do repositorio)
@pytest.fixture(scope='module')
def folhas_reais():
    pasta = _pasta_folhas()
    if pasta is None:
        pytest.skip('DESDOBRA_FOLHAS_SPECS não aponta para as folhas públicas da PME e da Globo Ads')
    return pasta


def _job_real(base, pasta, vid, arquivos):
    origem = base / 'specs'
    (origem / vid).mkdir(parents=True)
    for a in arquivos:
        shutil.copyfile(a, origem / vid / a.name)
    (base / 'kv.psd').write_bytes(psd_minimo())
    nucleo.criar(base / 'job', base / 'kv.psd', 'c', specs=origem)
    return base / 'job'


def test_folha_real_pme_25_entradas_10_tamanhos(folhas_reais, tmp_path):
    pdf = next((folhas_reais / 'eletromidia-pme').glob('*.pdf'))
    job = _job_real(tmp_path, folhas_reais, 'eletromidia', [pdf])
    sem_biblioteca, _ = importar.montar(job, biblioteca={})
    px = _px(sem_biblioteca)
    assert len(px) == 25 and len(_tamanhos(px)) == 10
    assert modelo.conferir_literais(sem_biblioteca) == []
    assert sem_biblioteca['resumo']['valores_confirmados'] == 0
    # com a biblioteca: o perfil e o que o motor extrai de novo da mesma folha
    doc = importar.importar(job)[0]
    perfil = importar.perfil_da_biblioteca(PME)
    assert doc['perfis'][0]['biblioteca']['perfil'] == 'eletromidia-pme'
    _comparar(doc, perfil)


def test_folha_real_globo_bate_com_o_perfil(folhas_reais, tmp_path):
    arqs = sorted((folhas_reais / 'globo-ads').glob('*.html'))
    job = _job_real(tmp_path, folhas_reais, 'globo-ads', arqs)
    doc = importar.importar(job)[0]
    _comparar(doc, importar.perfil_da_biblioteca(GLOBO))
    meia = next(f for f in doc['formatos'] if f['chave'] == 'globo-ads|half-page|300x600')
    assert meia['campos']['peso_max_tag']['valor'] is None and len(meia['campos']['peso_max_tag']['leituras']) == 2


def _comparar(doc, perfil):
    def valores(d):
        return {(f['chave'], c): (v['valor'], [x['valor'] for x in v.get('leituras') or []])
                for f in d['formatos'] for c, v in f['campos'].items()}
    assert valores(doc) == valores(perfil)
    assert {c['id']: {k: v['valor'] for k, v in c['campos'].items()} for c in doc['circuitos']} == \
           {c['id']: {k: v['valor'] for k, v in c['campos'].items()} for c in perfil['circuitos']}
