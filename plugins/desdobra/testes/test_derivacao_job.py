# -*- coding: utf-8 -*-
"""Briefing importado de teste, "desdobra derivar" e o render de um formato derivado (M5), com um job sintetico de
verdade (PSD e fonte gerados na hora, leitura e conferencia nos filhos isolados).

O render so parte de uma pessoa: aqui o console e simulado pelo fixture pessoa (o caminho do Disparo e o de verdade).
"""
import io
import json
import shutil
import subprocess
import sys

import numpy as np
import pytest
from PIL import Image

import test_derivacao_apoio as ap
import test_fontes_apoio as fap
import test_render_apoio as rap
from desdobra import arquivos, contratos
from desdobra.briefing import modelo as mb
from desdobra.job import nucleo
from desdobra.render import contrato as mc
from desdobra.render import derivado as mder
from desdobra.render import execucao
from desdobra.resultado import Codigo

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')

FORMATOS = [ap.formato('mesma', 640, 320), ap.formato('perto', 400, 240), ap.formato('vertical', 160, 320)]


def _cli(python, *args):
    r = subprocess.run([python, '-m', 'desdobra', '--envelope', *args], capture_output=True, timeout=300)
    return r.returncode, json.loads(r.stdout.decode('utf-8').strip().splitlines()[-1])


@pytest.fixture(scope='module')
def job_der(tmp_path_factory):
    base = tmp_path_factory.mktemp('derivacao')
    fontes = base / 'origem-fontes'
    fap.gravar(fontes, 'inventada.ttf', fap.fonte(ps=rap.FONTE))
    job = base / 'job'
    nucleo.criar(job, ap.psd_derivacao(base / 'origem' / 'kv.psd'), 'c', fontes=[fontes])
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    b, ids = ap.briefing_do_job(laudo, FORMATOS)
    arq = base / 'fixture-m5.json'
    arq.write_text(json.dumps(b), encoding='utf-8')
    return {'job': job, 'base': base, 'fixture': arq, 'ids': ids}


def _importar(job_der, python, job=None):
    return _cli(python, 'briefing', 'importar', str(job_der['fixture']), '--teste', '--job', str(job or job_der['job']))


def test_importar_sem_teste_recusa_e_com_teste_grava_a_origem_fixture(job_der, python):
    job = job_der['job']
    cod, env = _cli(python, 'briefing', 'importar', str(job_der['fixture']), '--job', str(job))
    assert cod == int(Codigo.RECUSADO) and not (job / mb.ARQUIVO).exists()
    cod, env = _importar(job_der, python)
    assert cod == 0, env
    b = mb.ler(job)
    assert b['cabecalho']['origem'] == 'fixture_de_teste' and b['cabecalho']['meio'] == 'importar_teste'
    assert b['cabecalho']['laudo_sha256'] == arquivos.sha256_arquivo(job / 'laudo' / 'laudo.json')
    assert not mb.desatualizado(job, b)


def test_importar_recusa_briefing_com_pendente_e_nao_grava(job_der, python, tmp_path):
    b = json.loads(job_der['fixture'].read_text(encoding='utf-8'))
    b['modo_dados'] = ap.pendente()
    ruim = tmp_path / 'ruim.json'
    ruim.write_text(json.dumps(b), encoding='utf-8')
    arq = job_der['job'] / mb.ARQUIVO
    antes = arq.read_bytes() if arq.exists() else None
    cod, env = _cli(python, 'briefing', 'importar', str(ruim), '--teste', '--job', str(job_der['job']))
    assert cod == int(Codigo.RECUSADO) and env['contagens'].get('pendente_obrigatorio') == 1
    assert (arq.read_bytes() if arq.exists() else None) == antes


def test_entregar_le_a_marca_e_recusa_o_briefing_de_teste(job_der, python):
    _importar(job_der, python)
    pode, motivo = mb.conferir_para_entrega(job_der['job'])
    assert not pode and motivo == 'briefing_de_fixture_de_teste'


def test_importar_nunca_grava_por_cima_do_briefing_do_da(job_der, python, tmp_path):
    job = tmp_path / 'copia'
    shutil.copytree(job_der['job'], job)
    _importar(job_der, python, job)
    dados = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    dados['cabecalho']['origem'], dados['cabecalho']['meio'] = 'da', 'terminal'
    contratos.gravar(job / mb.ARQUIVO, dados, 'briefing/1')
    antes = (job / mb.ARQUIVO).read_bytes()
    cod, env = _importar(job_der, python, job)
    assert cod == int(Codigo.RECUSADO)
    assert (job / mb.ARQUIVO).read_bytes() == antes
    # o portao de entrega nao aceita o arquivo so pela origem: a prova do disparo humano entra com o "briefing
    # confirmar" (M7); aqui so fica que o importar nunca grava por cima


def test_derivar_grava_cada_formato_e_as_devolucoes(job_der, python):
    _importar(job_der, python)
    cod, env = _cli(python, 'derivar', '--job', str(job_der['job']))
    assert cod == 0, env
    assert env['contagens']['derivados'] == 2 and env['contagens']['devolvidos'] == 1
    assert env['contagens']['motivo_troca_forte_de_orientacao'] == 1
    job = job_der['job']
    for k in ('mesma', 'perto', 'vertical'):
        contratos.ler(job / 'derivacao' / ('%s.json' % k), 'derivacao/1')
    dev = contratos.ler(job / 'derivacao' / 'devolucoes.json', 'devolucoes/1')
    assert [d['formato'] for d in dev['devolucoes']] == ['vertical']
    texto = json.dumps(env)
    for nome in job_der['ids']:
        assert nome not in texto


def test_derivar_recusa_sem_briefing_e_com_briefing_desatualizado(job_der, python, tmp_path):
    job = tmp_path / 'copia'
    shutil.copytree(job_der['job'], job)
    if (job / mb.ARQUIVO).exists():
        arquivos.tornar_gravavel(job / mb.ARQUIVO)
        (job / mb.ARQUIVO).unlink()
    cod, env = _cli(python, 'derivar', '--job', str(job))
    assert cod == int(Codigo.RECUSADO) and env['contagens'] == {'recusa_sem_briefing': 1}
    _importar(job_der, python, job)
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    b['cabecalho']['ds_sha256'] = '0' * 64
    contratos.gravar(job / mb.ARQUIVO, b, 'briefing/1')
    cod, env = _cli(python, 'derivar', '--job', str(job))
    assert cod == int(Codigo.RECUSADO) and env['contagens'] == {'recusa_briefing_desatualizado': 1}


# ------------------------------------------------------------------ render do formato derivado
def _derivado(job_der, python):
    _importar(job_der, python)
    cod, env = _cli(python, 'derivar', '--job', str(job_der['job']))
    assert cod == 0, env


def test_contrato_do_derivado_escala_as_entradas_e_tira_o_fora_da_peca(job_der, python):
    _derivado(job_der, python)
    contrato, bloqueios, _c = mder.montar(job_der['job'], 'perto')
    assert not bloqueios, bloqueios
    assert contrato['formato']['chave'] == 'perto'
    assert (contrato['formato']['largura'], contrato['formato']['altura']) == (400, 240)
    assert contrato['origem']['funcoes'] == 'derivacao'
    solto = job_der['ids']['solto-sintetico']
    assert solto in contrato['fora_da_peca']
    assert all(solto not in e.get('layer_ids', []) and e.get('layer_id') != solto for e in contrato['entradas'])
    pilhas = [e for e in contrato['entradas'] if e['tipo'] == 'pilha']
    assert pilhas and all(e.get('transformacao') for e in pilhas)
    textos = [e for e in contrato['entradas'] if e['tipo'] == 'texto']
    assert len(textos) == 2
    for e in textos:
        x0, y0, x1, y1 = e['regiao']
        assert 0 <= x0 < x1 <= 400 and 0 <= y0 < y1 <= 240
    contratos.validar(contrato, 'composicao/1')


def test_formato_devolvido_ou_sem_derivacao_nao_tem_contrato(job_der, python):
    _derivado(job_der, python)
    _c, bloqueios, _p = mder.montar(job_der['job'], 'vertical')
    assert [b['codigo'] for b in bloqueios] == ['formato_devolvido']
    _c, bloqueios, _p = mder.montar(job_der['job'], 'inexistente')
    assert [b['codigo'] for b in bloqueios] == ['formato_sem_derivacao']


def test_render_do_derivado_grava_o_master_no_tamanho_do_formato(job_der, python, pessoa):
    _derivado(job_der, python)
    job = job_der['job']
    rel = execucao.renderizar(job, disparo=pessoa.exigir('render'), formato='perto')
    master = (job / 'render' / 'perto' / 'master.png').read_bytes()
    img = np.asarray(Image.open(io.BytesIO(master)).convert('RGBA'))
    assert img.shape[:2] == (240, 400)
    assert rel['formato']['chave'] == 'perto' and rel['cdp']['confere'] == rel['cdp']['trechos'] > 0
    d = contratos.ler(job / 'derivacao' / 'perto.json', 'derivacao/1')
    logo = next(e for e in d['elementos'] if e['funcao'] == 'logo_principal')
    x0, y0, x1, y1 = (int(round(v)) for v in logo['caixa'])
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    assert tuple(img[cy, cx, :3]) == (0, 120, 60)
    assert tuple(img[2, 2, :3]) == (240, 236, 220)
    # o quadrado fora da peca (220, 0, 0) nao aparece; o vermelho do texto e outro (204, 25, 25)
    assert not ((img[..., 0] > 210) & (img[..., 1] < 10) & (img[..., 2] < 10)).any()
    # o texto sai escuro dentro da caixa do titulo derivado
    tit = next(e for e in d['elementos'] if e['funcao'] == 'titulo')
    tx0, ty0, tx1, ty1 = (int(round(v)) for v in tit['caixa'])
    assert img[ty0:ty1, tx0:tx1, :3].min() < 90
    assert rel['derivacao']['briefing_origem'] == 'fixture_de_teste'
    # a origem continua renderizando como antes
    rel_o = execucao.renderizar(job, disparo=pessoa.exigir('render'))
    assert rel_o['formato']['chave'] == 'origem' and rel_o['formato']['largura'] == 320


def test_render_recusa_formato_devolvido(job_der, python, pessoa):
    _derivado(job_der, python)
    with pytest.raises(execucao.ErroRender) as e:
        execucao.renderizar(job_der['job'], disparo=pessoa.exigir('render'), formato='vertical')
    assert e.value.motivo == 'bloqueio'
    assert not (job_der['job'] / 'render' / 'vertical' / 'master.png').exists()


def test_render_de_formato_derivado_tambem_recusa_sem_terminal(job_der, python):
    _derivado(job_der, python)
    r = subprocess.run([python, '-m', 'desdobra', 'render', '--job', str(job_der['job']), '--formato', 'perto'],
                       capture_output=True, stdin=subprocess.PIPE, timeout=120)
    assert r.returncode == int(Codigo.RECUSADO)


def test_contrato_da_origem_nao_mudou(job_der):
    contrato, bloqueios, _c = mc.montar(job_der['job'])
    assert contrato['formato']['chave'] == 'origem' and contrato['origem']['funcoes'] == 'identidade'
