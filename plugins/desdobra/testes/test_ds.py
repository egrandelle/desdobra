# -*- coding: utf-8 -*-
"""Design system da peca (desdobra ds montar): tokens de cor com a origem, corpo pela escala vertical, caixa do
sujeito pelo alfa ou "pedir ao DA", ds sem conferencia de fontes, parametros de cor do job e limites.json."""
import json

import numpy as np
import pytest

import test_ds_apoio as apoio
from desdobra import cli, contratos, limites
from desdobra import cor
from desdobra import ds as mod_ds
from desdobra.ds import sujeito
from desdobra.job import nucleo
from desdobra.job.fases import FASES_M1, _fase_ds

# esteira dos testes: leitura e design system, sem a conferencia de fontes (que pede arquivos de fonte)
ESTEIRA_DS = FASES_M1 + (_fase_ds(FASES_M1),)


@pytest.fixture(scope='module')
def job_adobe(tmp_path_factory):
    base = tmp_path_factory.mktemp('ds-adobe')
    pasta = base / 'job'
    nucleo.criar(pasta, apoio.psd_de_cor(base / 'origem', icc=apoio.icc_adobe_rgb()), 'c', fases=ESTEIRA_DS)
    r = nucleo.proxima(pasta, fases=ESTEIRA_DS, todas=True)
    assert r.codigo == 0, r.linhas_humanas
    return pasta


def _ds(pasta):
    return contratos.ler(pasta / 'ds' / 'design-system.json', 'design-system/1')


def _lim(pasta):
    return contratos.ler(pasta / 'ds' / 'limites.json', 'limites/1')


def _camada(pasta, nome):
    laudo = json.loads((pasta / 'laudo' / 'laudo.json').read_text(encoding='utf-8'))
    return next(c['identidade']['layer_id'] for c in laudo['camadas'] if c['nome'] == nome)


def test_esteira_tem_a_fase_ds_depois_de_ler_e_de_fontes():
    from desdobra.job import fases
    esteira = getattr(fases, 'ESTEIRA', ESTEIRA_DS)
    ids = [f.id for f in esteira]
    ds = next(f for f in esteira if f.id == 'ds')
    assert ids.index('ds') > ids.index('ler') and 'ler' in ds.depende_de
    if 'fontes' in ids:
        assert ids.index('ds') > ids.index('fontes') and 'fontes' in ds.depende_de
    assert 'fontes/conferencia.json' in ds.entradas and 'parametros/cor.json' in ds.entradas
    assert ds.saidas == ('ds/design-system.json', 'ds/limites.json')
    assert ds.comando('P')[-4:] == ['ds', 'montar', '--job', 'P']


def test_tokens_de_cor_passam_pelo_perfil(job_adobe):
    ds = _ds(job_adobe)
    assert ds['documento']['perfil']['tratamento'] == cor.TRATAMENTO_ICC
    por_valor = {tuple(t['origem']['valor_documento_8_bits']): t for t in ds['tokens']['cores']}
    for rgb, descritor in ((apoio.COR_SOLIDA, 'preenchimento'), (apoio.COR_OVERLAY, 'overlay')):
        tok = por_valor[rgb]
        ref = apoio.adobe_para_srgb_referencia(rgb)
        assert all(abs(a - b) <= 1.5 for a, b in zip(tok['srgb'], ref))
        assert tok['usos'][0]['descritor'] == descritor
        assert tok['origem']['perfil']['nome'] == 'Adobe RGB sintetico' and tok['origem']['intent']
    assert any(u['descritor'] == 'texto' for t in ds['tokens']['cores'] for u in t['usos'])


def test_corpo_efetivo_pela_escala_vertical(job_adobe):
    (tok,) = _ds(job_adobe)['tokens']['tipografia']
    assert tok['escala_vertical_matriz'] == apoio.ESCALA_V
    assert tok['corpo_efetivo_px'] == apoio.CORPO_TEXTO * apoio.ESCALA_V
    assert tok['corpo_efetivo_px'] != apoio.CORPO_TEXTO * apoio.ESCALA_H
    assert tok['cor'] and tok['tracking_milesimos_em'] is not None


def test_caixa_do_sujeito_por_alfa_e_pedir_ao_da(job_adobe):
    por_camada = {s['camada']: s for s in _ds(job_adobe)['tokens']['sujeito']}
    recorte = por_camada[_camada(job_adobe, 'recorte-alfa')]
    assert recorte['metodo'] == sujeito.METODO_ALFA
    assert recorte['caixa'] == [80, 38, 96, 60]  # so o maior componente, nas coordenadas do documento
    assert recorte['limiar']['limite_id'] == 'ds.sujeito_limiar_alfa'
    foto = por_camada[_camada(job_adobe, 'foto-sem-recorte')]
    assert foto['metodo'] == sujeito.METODO_PEDIR_AO_DA and foto['caixa'] is None
    assert any(p['codigo'] == 'sujeito_pedir_ao_da' for p in _ds(job_adobe)['pendencias'])


def test_caixa_por_alfa_unitario():
    a = np.zeros((10, 20), np.uint8)
    a[2:5, 3:9] = 200
    a[8, 18] = 255
    a[1, 1] = 127  # abaixo do limiar
    r = sujeito.caixa_por_alfa(a, (100, 50))
    assert r['metodo'] == 'alfa' and r['caixa'] == [103, 52, 109, 55] and r['medidas']['n_componentes'] == 2
    assert sujeito.caixa_por_alfa(np.full((4, 4), 255, np.uint8))['metodo'] == 'pedir_ao_da'
    assert sujeito.caixa_por_alfa(np.zeros((4, 4), np.uint8))['metodo'] == 'sem_tinta'
    cheio = np.full((4, 4), 255, np.uint8)
    cheio[0, 0] = 0  # recorte que encosta nas quatro bordas (como uma elipse) continua sendo recorte
    r = sujeito.caixa_por_alfa(cheio)
    assert r['metodo'] == 'alfa' and r['caixa'] == [0, 0, 4, 4]


def test_ds_sem_conferencia_de_fontes(job_adobe):
    ds = _ds(job_adobe)
    assert ds['fontes']['situacao'] == 'fontes_nao_conferidas'
    assert any(p['codigo'] == 'fontes_nao_conferidas' for p in ds['pendencias'])
    (tok,) = ds['tokens']['tipografia']
    assert tok['metricas'] is None and tok['metricas_origem'] is None and tok['situacao_fonte'] == 'fontes_nao_conferidas'


def test_ds_com_conferencia_leva_as_metricas(job_adobe, tmp_path):
    lid = _camada(job_adobe, 'texto-sintetico')
    laudo = json.loads((job_adobe / 'laudo' / 'laudo.json').read_text(encoding='utf-8'))
    conf = apoio.conferencia(lid, job_id=nucleo.ler_estado(job_adobe)['job_id'], arquivo_sha256=laudo['origem']['sha256'])
    (job_adobe / 'fontes').mkdir(exist_ok=True)
    caminho = job_adobe / 'fontes' / 'conferencia.json'
    caminho.write_text(json.dumps(conf), encoding='utf-8')
    try:
        mod_ds.executar_montar(job_adobe)
        ds = _ds(job_adobe)
        (tok,) = ds['tokens']['tipografia']
        assert tok['familia'] == 'Fonte Inventada' and tok['peso'] == 700 and tok['estilo'] == 'Bold'
        assert tok['metricas']['unidades_por_em'] == 1000 and tok['metricas']['cap_height'] == 700
        assert tok['metricas_origem']['sha256'] == 'a' * 64 and tok['situacao_fonte'] == 'ok'
        assert ds['fontes']['situacao'] == 'conferencia_lida' and ds['origem']['conferencia_fontes_sha256']
        texto = json.dumps(ds)
        assert 'Texto sintetico' not in texto and 'texto-sintetico' not in texto  # sem texto de peca nem nome
    finally:
        caminho.unlink()
        mod_ds.executar_montar(job_adobe)


def test_limites_do_job_e_referencias_do_psd(job_adobe):
    lim = {x['id']: x for x in _lim(job_adobe)['limites']}
    assert lim['cor.intent_saida']['situacao'] == 'a_calibrar'
    assert lim['cor.gama_mistura_texto']['valor'] == 1.45 and lim['cor.gama_mistura_texto']['situacao'] == 'decidido'
    assert lim['ds.sujeito_limiar_alfa']['valor'] == limites.valor('ds.sujeito_limiar_alfa')
    ref = lim['psd.corpo_efetivo_min']
    assert ref['situacao'] == 'referencia_do_psd' and ref['piso'] is False and ref['efeito'] == 'registra'
    assert ref['valor'] == apoio.CORPO_TEXTO * apoio.ESCALA_V
    # o contrato recusa referencia do PSD como piso
    ruim = _lim(job_adobe)
    for x in ruim['limites']:
        if x['situacao'] == 'referencia_do_psd':
            x['piso'] = True
    with pytest.raises(contratos.ErroContrato):
        contratos.validar(ruim, 'limites/1')


def test_parametros_de_cor_do_job_invalidam_o_ds(job_adobe, capsys):
    cod = cli.principal(['ds', 'parametros-cor', '--job', str(job_adobe), '--intent', 'perceptual',
                         '--perfil-embutido', 'sim'])
    assert cod == 0
    dados = contratos.ler(job_adobe / 'parametros' / 'cor.json', 'ds-parametros-cor/1')
    assert dados['intent'] == 'perceptual' and dados['perfil_embutido_na_saida'] is True
    avaliacao, _ = nucleo.avaliar(job_adobe, nucleo.ler_estado(job_adobe), ESTEIRA_DS)
    assert not avaliacao['ds'][0] and avaliacao['ler'][0]
    assert nucleo.proxima(job_adobe, fases=ESTEIRA_DS, todas=True).codigo == 0
    ds = _ds(job_adobe)
    assert ds['cor']['parametros']['intent'] == {'valor': 'perceptual', 'origem': 'job'}
    assert ds['cor']['parametros']['saida']['perfil_embutido'] is True
    lim = {x['id']: x for x in _lim(job_adobe)['limites']}
    assert lim['cor.intent_saida']['situacao'] == 'parametro_do_job' and lim['cor.intent_saida']['valor'] == 'perceptual'
    (job_adobe / 'parametros' / 'cor.json').unlink()
    assert nucleo.proxima(job_adobe, fases=ESTEIRA_DS, todas=True).codigo == 0


def test_documento_sem_perfil_pela_esteira(tmp_path):
    pasta = tmp_path / 'job'
    nucleo.criar(pasta, apoio.psd_de_cor(tmp_path / 'origem', icc=None, com_overlay=False), 'c', fases=ESTEIRA_DS)
    assert nucleo.proxima(pasta, fases=ESTEIRA_DS, todas=True).codigo == 0
    ds = _ds(pasta)
    assert ds['documento']['perfil']['tratamento'] == cor.TRATAMENTO_SEM_PERFIL
    tok = next(t for t in ds['tokens']['cores'] if t['origem']['valor_documento_8_bits'] == list(apoio.COR_SOLIDA))
    assert tok['srgb'] == list(apoio.COR_SOLIDA)


def test_leitura_sem_arquivo_do_perfil_nao_converte(job_adobe):
    laudo = contratos.ler(job_adobe / 'laudo' / 'laudo.json', 'laudo/1')
    bruto = job_adobe / 'laudo' / 'bruto' / laudo['origem']['sha256']
    est = contratos.ler(bruto / 'estrutura.json', 'estrutura/1')
    del est['documento']['icc']['arquivo']  # como uma leitura do M1
    for c in est['camadas']:
        c.pop('cores_descritores', None)
    ds, _lim_ = mod_ds.montar(job_adobe / 'laudo', laudo, est, None, cor.parametros())
    contratos.validar(ds, 'design-system/1')
    assert ds['documento']['perfil']['tratamento'] == cor.TRATAMENTO_INDISPONIVEL
    assert all(t['situacao'] == 'nao_convertido' for t in ds['tokens']['cores'])
    codigos = {p['codigo'] for p in ds['pendencias']}
    assert {'cores_nao_convertidas', 'descritores_nao_lidos'} <= codigos


def test_ds_montar_sem_laudo_e_recusa(tmp_path, kv_psd):
    pasta = tmp_path / 'job'
    nucleo.criar(pasta, kv_psd, 'c')
    assert cli.principal(['ds', 'montar', '--job', str(pasta)]) == 3


def test_envelope_do_ds_sem_conteudo(job_adobe, capsys):
    capsys.readouterr()
    assert cli.principal(['--envelope', 'ds', 'montar', '--job', str(job_adobe), '--teto-memoria-bytes', '10']) == 0
    env = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    contratos.validar(env, 'envelope/1')
    assert env['comando'] == 'ds montar' and env['contagens']['sujeito_alfa'] == 1 and 'conteudo' not in env
