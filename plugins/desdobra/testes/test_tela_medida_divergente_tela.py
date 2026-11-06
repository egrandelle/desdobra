# -*- coding: utf-8 -*-
"""Revisao dos becos, D2, pela tela de verdade (servidor HTTP e Chromium sem janela): com a medida do formato da folha
com duas medidas ainda sem escolha, o servidor recusa Salvar e seguir, e o botao da pagina fica desligado com a dica do
que falta. Tudo sintetico: um e-mail de specs inventado e a proposta de mapeamento do modo b."""
import pytest

import test_fontes_apoio as fap
import test_tela_escrita as tte
import test_tela_palco as tp
import test_tela_partida as tpa
import test_tela_servidor as tts
from conftest import escolher_modo_do_da
from desdobra import contratos
from desdobra.tela import atos as ta
from desdobra.tela import estado as te
from desdobra.tela import servidor as ts

ambiente_limpo = tte.ambiente_limpo
EMAIL = ('Formato: 640x320\nPeso máximo: 250 KB\nMedida da arte 300x600\n'
         'Formato: 300x600\nPeso máximo: 150 KB\n')


@pytest.fixture
def job_d2(tmp_path, ambiente_limpo):
    from desdobra.job import nucleo
    from desdobra.render import autoteste
    fontes = tmp_path / 'origem-fontes'
    fap.gravar(fontes, 'autoteste.ttf', autoteste.gerar_fonte())
    specs = tmp_path / 'origem-specs'
    (specs / 'e').mkdir(parents=True)
    (specs / 'e' / 'email.txt').write_text(EMAIL, encoding='utf-8')
    job = tmp_path / 'job'
    nucleo.criar(job, tp._psd_hostil(tmp_path / 'origem' / 'kv.psd', autoteste.NOME_PS), 'b', fontes=[fontes],
                 specs=specs)
    escolher_modo_do_da(job, 'b')
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    doc = contratos.ler(job / 'specs' / 'rascunho.json', 'spec/1')
    primeiro = next(f for f in doc['formatos'] if f['id'].endswith('-e01'))
    t = next((f['id'], t['id']) for f in doc['folhas'] for t in f['trechos'] if 'Medida da arte' in t['texto'])
    contratos.gravar(job / 'sugestoes' / 'mapeamento-specs.json',
                     {'esquema': 'mapeamento-specs/1',
                      'propostas': [{'folha': t[0], 'trecho': t[1], 'campo': 'dimensao', 'alvo': primeiro['id']}]},
                     'mapeamento-specs/1')
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    ids = {c['nome']: c['identidade']['layer_id'] for c in laudo['camadas']}
    funcoes = {ids['fundo-sintetico']: 'fundo', ids[tp.NOME_FORM]: 'titulo', ids['quadrado-sintetico']: 'logo_principal',
               ids[tp.NOME_APOIO]: 'texto_de_apoio', ids['solto-sintetico']: 'fora_da_peca'}
    return job, funcoes


def _servidor(job):
    conteudo = te.montar(job)
    return ts.ServidorTela(conteudo, pasta=job, modo_teste=False, atos=ta.atos_do_job(job, conteudo=conteudo)).iniciar()


def test_botao_salvar_desligado_com_a_medida_a_escolher_no_chromium(job_d2):
    from playwright.sync_api import sync_playwright

    from desdobra.chromium import navegador
    job, funcoes = job_d2
    s = _servidor(job)
    try:
        b = tts._entrar(s)
        tpa._confirmar_medidas(s, b, job)
        p2 = dict(tpa._passo_2(funcoes), **tpa._passo_1(tpa._estado(s, b)))
        assert tpa._rascunho(s, b, {}, p2) == 200
        e = tpa._estado(s, b)
        familias = {}
        for g in (g for o in e['orientacoes'] for g in o['grupos']):
            versao = None
            for fid in (x['id'] for c in g['composicoes'] for x in c['formatos']):
                variantes = ((tpa._previa(s, b, fid).get('galeria') or {}).get('variantes')) or []
                if variantes:
                    versao = variantes[0]['id']
                    break
            familias[g['id']] = {'versao': versao, 'confirmada': False, 'edicoes': []}
        assert tpa._rascunho(s, b, familias, p2) == 200
        for gid, f in familias.items():
            assert tpa._ato(s, b, 'familia', {'familia': gid, 'versao': f['versao'], 'edicoes': []}) == (200, 200)
        recusa = tpa._ato(s, b, 'salvar', {'rascunho': tpa._vista(job)})
        e = tpa._estado(s, b)
    finally:
        s.parar()
    assert recusa[0] == 403
    assert e['lido']['specs']['sem_medida']
    srv = _servidor(job)
    navegador.apontar_playwright()
    try:
        with sync_playwright() as pw:
            nav, pg = tp._pagina_da_tela(pw, srv, 1600, 900)
            try:
                botao = pg.evaluate('() => { const b = document.getElementById("salvar-seguir");'
                                    ' return [b.disabled, document.getElementById("dica-acoes").textContent]; }')
            finally:
                nav.close()
    finally:
        srv.parar()
    assert botao == [True, 'Escolha a medida do formato com duas medidas no passo 1.'], botao
