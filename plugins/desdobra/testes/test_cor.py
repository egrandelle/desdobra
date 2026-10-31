# -*- coding: utf-8 -*-
"""Modulo de cor (desdobra.cor): descritores pelo perfil ICC do documento, documento sem perfil, asset com
outro perfil atribuido sem conversao, parametros do job. Perfis e PSD sinteticos (test_ds_apoio)."""
import io
import sys
from pathlib import Path

import pytest
from PIL import Image

import sinteticos
import test_ds_apoio as apoio
from desdobra import contratos
from desdobra import cor
from desdobra.job import nucleo
from desdobra.job.fases import FASES_M1, _fase_ds

ESTEIRA_DS = FASES_M1 + (_fase_ds(FASES_M1),)


def _parametros(**kw):
    return cor.parametros(**kw)


# ------------------------------------------------------------------ conversao pura
@pytest.mark.parametrize('rgb', [(200, 30, 60), (40, 160, 90), (128, 128, 128), (10, 20, 230), (250, 240, 5)])
def test_adobe_rgb_para_srgb_bate_com_a_referencia(rgb):
    conv = cor.Conversor(apoio.icc_adobe_rgb(), _parametros())
    tok = conv.token({'modelo': 'rgb', 'valores': list(rgb)})
    ref = apoio.adobe_para_srgb_referencia(rgb)
    assert tok['situacao'] == 'convertido'
    assert all(abs(a - b) <= 1.5 for a, b in zip(tok['srgb'], ref)), (tok['srgb'], ref)
    assert cor.delta_e76(tok['srgb'], ref) < 1.0
    assert tok['origem']['valor_documento_8_bits'] == list(rgb)
    assert tok['origem']['perfil']['tratamento'] == cor.TRATAMENTO_ICC
    assert tok['origem']['intent'] == 'relativo_colorimetrico'


def test_sem_conversao_o_erro_e_grande_e_com_conversao_some():
    rgb = (200, 30, 60)
    conv = cor.Conversor(apoio.icc_adobe_rgb(), _parametros())
    ref = apoio.adobe_para_srgb_referencia(rgb)
    assert cor.delta_e76(rgb, ref) > 5.0
    assert cor.delta_e76(conv.token({'modelo': 'rgb', 'valores': list(rgb)})['srgb'], ref) < 1.0


def test_documento_sem_perfil_usa_srgb():
    conv = cor.Conversor(None, _parametros())
    tok = conv.token({'modelo': 'rgb', 'valores': [12.2, 99.6, 240.0]})
    assert conv.tratamento == cor.TRATAMENTO_SEM_PERFIL
    assert tok['srgb'] == [12, 100, 240] and tok['srgb_hex'] == '#0C64F0'


def test_perfil_de_monitor_converte():
    conv = cor.Conversor(apoio.icc_monitor(), _parametros())
    tok = conv.token({'modelo': 'rgb', 'valores': [128, 128, 128]})
    assert tok['situacao'] == 'convertido' and tok['srgb'] != [128, 128, 128]


def test_perfil_indisponivel_nao_inventa():
    conv = cor.Conversor(None, _parametros(), indisponivel=True)
    tok = conv.token({'modelo': 'rgb', 'valores': [1, 2, 3]})
    assert tok['situacao'] == 'nao_convertido' and tok['srgb'] is None and tok['motivo']


def test_perfil_ilegivel_vira_situacao():
    conv = cor.Conversor(b'isto nao e um perfil', _parametros())
    assert conv.tratamento == cor.TRATAMENTO_ILEGIVEL and not conv.converte


def test_descritores_de_cor():
    assert cor.cor_do_descritor('RGBC', {'Rd': 1.0, 'Grn': 2.0, 'Bl': 3.0}) == {'modelo': 'rgb', 'valores': [1.0, 2.0, 3.0]}
    assert cor.cor_do_descritor('RGBC', {'redFloat': 1.0, 'greenFloat': 0.0, 'blueFloat': 0.5})['valores'] == [255.0, 0.0, 127.5]
    hsb = cor.cor_do_descritor('HSBC', {'H': 0.0, 'Strt': 100.0, 'Brgh': 100.0})
    assert hsb['modelo'] == 'rgb' and hsb['valores'] == [255.0, 0.0, 0.0]
    assert cor.cor_do_descritor('LbCl', {'Lmnc': 50.0, 'A': 10.0, 'B': -5.0})['modelo'] == 'lab'
    conv = cor.Conversor(None, _parametros())
    for classe, valores in (('CMYC', {'Cyn': 1.0, 'Mgnt': 2.0, 'Ylw': 3.0, 'Blck': 4.0}), ('Grsc', {'Gry': 50.0}),
                            ('BkCl', {'Bk': 'x'}), ('XXXX', {})):
        tok = conv.token(cor.cor_do_descritor(classe, valores))
        assert tok['situacao'] == 'nao_convertido' and tok['motivo']
    lab = conv.token(cor.cor_do_descritor('LbCl', {'Lmnc': 100.0, 'A': 0.0, 'B': 0.0}))
    assert lab['situacao'] == 'convertido' and min(lab['srgb']) >= 250
    texto = cor.cor_do_texto([1.0, 0.1, 0.2, 0.3])
    assert texto['alfa'] == 1.0 and [round(x, 1) for x in texto['valores']] == [25.5, 51.0, 76.5]


def test_parametros_vem_do_registro_ou_do_job():
    padrao = cor.parametros()
    assert padrao.origem == {'intent': 'registro', 'compensacao_ponto_preto': 'registro',
                             'perfil_embutido_na_saida': 'registro'}
    j = padrao.para_json()
    assert j['intent']['limite']['situacao'] == 'a_calibrar' and j['saida']['perfil_embutido'] is False
    do_job = cor.parametros(intent='perceptual', compensacao_ponto_preto=True, perfil_embutido_na_saida=True)
    assert do_job.origem['intent'] == 'job' and do_job.compensacao_ponto_preto and do_job.perfil_embutido_na_saida
    with pytest.raises(cor.ErroCor):
        cor.parametros(intent='inventado')
    # perfis de matriz: perceptual e relativo colorimetrico dao o mesmo numero no LittleCMS
    a = cor.Conversor(apoio.icc_adobe_rgb(), cor.parametros(intent='perceptual')).rgb([200, 30, 60])
    b = cor.Conversor(apoio.icc_adobe_rgb(), cor.parametros(intent='relativo_colorimetrico')).rgb([200, 30, 60])
    assert a == b


def test_asset_com_outro_perfil_e_convertido_para_o_do_documento():
    doc = {'nome': 'documento', 'sha256': 'a' * 64}
    t = cor.tratamento_do_asset(doc, {'nome': 'asset', 'sha256': 'b' * 64})
    assert t['tratamento'] == 'converter_para_perfil_do_documento' and t['converte_pixels'] is True
    assert t['perfil_efetivo'] == doc and t['fonte']['arquivo'] == 'decisoes-v1.md'
    assert 'revista em 31/10' in t['fonte']['secao']
    mesmo = cor.tratamento_do_asset(doc, {'nome': 'x', 'sha256': 'a' * 64})
    assert mesmo['tratamento'] == 'mesmo_perfil' and mesmo['converte_pixels'] is False
    assert cor.tratamento_do_asset(doc, None)['tratamento'] == 'perfil_do_asset_nao_lido'
    assert not hasattr(cor, 'asset_atribuido')


# ------------------------------------------------------------------ pela esteira (leitor + ds)
def _job(tmp_path, psd, nome='job'):
    pasta = tmp_path / nome
    nucleo.criar(pasta, psd, 'c', fases=ESTEIRA_DS)
    r = nucleo.proxima(pasta, fases=ESTEIRA_DS, todas=True)
    assert r.codigo == 0, r.linhas_humanas
    return pasta


def test_asset_embutido_com_outro_perfil_fica_para_converter(tmp_path):
    psd, _dados = sinteticos.embutido(tmp_path / 'origem', dados=apoio.interno_com_perfil(apoio.icc_adobe_rgb()))
    job = _job(tmp_path, psd)
    ds = contratos.ler(job / 'ds' / 'design-system.json', 'design-system/1')
    assert ds['documento']['perfil']['tratamento'] == cor.TRATAMENTO_SEM_PERFIL
    (asset,) = ds['assets']
    assert asset['tratamento'] == 'converter_para_perfil_do_documento' and asset['converte_pixels'] is True
    assert asset['perfil_asset']['sha256'] == cor.descrever_perfil(apoio.icc_adobe_rgb())['sha256']
    assert ds['resumo']['n_assets_perfil_convertido'] == 1


def test_leitor_grava_o_perfil_e_os_descritores(tmp_path):
    job = _job(tmp_path, apoio.psd_de_cor(tmp_path / 'origem', icc=apoio.icc_adobe_rgb()))
    (bruto,) = [p for p in (job / 'laudo' / 'bruto').iterdir()]
    assert (bruto / 'documento.icc').read_bytes() == apoio.icc_adobe_rgb()
    est = contratos.ler(bruto / 'estrutura.json', 'estrutura/1')
    assert est['documento']['icc']['arquivo'] == 'documento.icc'
    descritores = {(d['descritor'], d['classe']) for c in est['camadas'] for d in c.get('cores_descritores') or []}
    assert ('preenchimento', 'RGBC') in descritores and ('overlay', 'RGBC') in descritores


# ------------------------------------------------------------------ correcoes da revisao do M2
@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador do filho roda no Windows')
def test_perfil_icc_do_documento_e_aberto_so_no_filho(tmp_path, monkeypatch):
    from PIL import ImageCms

    from desdobra import cor
    from desdobra import ds as mod_ds
    from desdobra.job.fases import _fase_ds
    esteira = FASES_M1 + (_fase_ds(FASES_M1),)
    job = tmp_path / 'job'
    nucleo.criar(job, apoio.psd_de_cor(tmp_path / 'origem', icc=apoio.icc_adobe_rgb()), 'c', fases=esteira)
    assert nucleo.proxima(job, fases=esteira, todas=True).codigo == 0
    original = ImageCms.ImageCmsProfile

    def vigia(perfil):
        assert not isinstance(perfil, (io.BytesIO, bytes, str, Path)), 'o processo principal abriu o ICC do cliente'
        return original(perfil)
    monkeypatch.setattr(ImageCms, 'ImageCmsProfile', vigia)
    ds, _lim = mod_ds.executar_montar(job)
    assert ds['documento']['perfil']['tratamento'] == cor.TRATAMENTO_ICC
    assert ds['documento']['perfil']['nome'] == 'Adobe RGB sintetico'
    por_valor = {tuple(t['origem']['valor_documento_8_bits']): t for t in ds['tokens']['cores']}
    tok = por_valor[apoio.COR_SOLIDA]
    ref = apoio.adobe_para_srgb_referencia(apoio.COR_SOLIDA)
    assert all(abs(a - b) <= 1.5 for a, b in zip(tok['srgb'], ref))
    assert not (job / 'ds' / '.trabalho-cor').exists()


@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador do filho roda no Windows')
def test_perfil_ilegivel_no_filho_vira_motivo_sem_derrubar(tmp_path):
    from desdobra import cor
    icc = tmp_path / 'ruim.icc'
    icc.write_bytes(b'isto nao e um perfil' * 10)
    conv = cor.converter_isolado(icc, cor.parametros(), [{'modelo': 'rgb', 'valores': [10, 20, 30]}], tmp_path / 't')
    assert conv.tratamento == cor.TRATAMENTO_ILEGIVEL and not conv.converte and conv.motivo
    assert conv.token({'modelo': 'rgb', 'valores': [10, 20, 30]})['situacao'] == 'nao_convertido'
    assert not (tmp_path / 't').exists()
