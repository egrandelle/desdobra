# -*- coding: utf-8 -*-
"""Integracao do M1 de ponta a ponta pela CLI de verdade (subprocesso), com PSD sintetico gerado na hora.

  - detector de segredos: chave e token em nome de camada e em texto viram bloqueio em 100% dos casos, com 0
    ocorrencia no envelope, no log e no pacote-modelo; o detalhe fica so no arquivo do DA;
  - modo c: o envelope do job proxima nao leva conteudo nem nome de camada;
  - a fase ler do job proxima repassa as contagens do laudo e grava o pacote-modelo.
"""
import json
import subprocess
import sys

import pytest
from PIL import Image
from psd_tools import PSDImage

import sinteticos
from conftest import escolher_modo_do_da
from desdobra import contratos, plataforma

pytestmark = pytest.mark.skipif(plataforma.obter().nome in ('sem-suporte', 'mac'), reason='sem isolador neste sistema')

# montados aos pedacos para o proprio arquivo de teste nao virar ocorrencia do detector
CHAVE_NO_NOME = 'AKIA' + 'Q' * 16
TOKEN_NO_TEXTO = 'gh' + 'p_' + 'x7' * 18
SEGREDOS = (CHAVE_NO_NOME, TOKEN_NO_TEXTO)


def rodar(*argumentos):
    proc = subprocess.run([sys.executable, '-I', '-B', '-m', 'desdobra', *argumentos], capture_output=True)
    return proc.returncode, proc.stdout.decode('utf-8'), proc.stderr.decode('utf-8')


def envelope_de(saida):
    linhas = saida.strip().splitlines()
    assert len(linhas) == 1, saida
    env = json.loads(linhas[0])
    contratos.validar(env, 'envelope/1')
    return env


def psd_com_segredos(pasta):
    p = PSDImage.new('RGB', (160, 80), color=(255, 255, 255))
    p.create_pixel_layer(Image.new('RGBA', (160, 80), (230, 230, 230, 255)), name='fundo-limpo')
    p.create_pixel_layer(Image.new('RGBA', (30, 20), (200, 0, 0, 255)), name='logo %s' % CHAVE_NO_NOME, top=5, left=5)
    t = p.create_pixel_layer(Image.new('RGBA', (120, 24), (20, 20, 20, 255)), name='texto-com-token', top=40, left=20)
    sinteticos._virar_texto(t, [('acesso ' + TOKEN_NO_TEXTO, 0, False)])
    p.create_pixel_layer(Image.new('RGBA', (20, 20), (0, 0, 200, 255)), name='camada-comum', top=50, left=130)
    return sinteticos._salvar(p, pasta / 'segredos.psd')


@pytest.fixture(scope='module')
def job_b(tmp_path_factory):
    pasta = tmp_path_factory.mktemp('integracao')
    psd = psd_com_segredos(pasta)
    job = pasta / 'job-b'
    codigo, saida, _ = rodar('--envelope', '--teto-modo-dados', 'b', 'job', 'criar', str(job), '--kv', str(psd),
                             '--modo-dados', 'b')
    assert codigo == 0, saida
    escolher_modo_do_da(job, 'b')  # a escolha do DA na tela e a fonte do modo (decisoes-v1.md, 170)
    codigo, saida, erro = rodar('--envelope', '--teto-modo-dados', 'b', 'job', 'proxima', str(job))
    return {'job': job, 'psd': psd, 'codigo': codigo, 'saida': saida, 'erro': erro, 'pasta': pasta}


def test_job_proxima_le_e_repassa_o_laudo(job_b):
    env = envelope_de(job_b['saida'])
    assert job_b['codigo'] == 0 and env['codigo'] == 0 and env['fase'] == 'ler'
    assert env['contagens']['camadas'] == 4 and env['contagens']['codigo_da_fase'] == 0
    assert len(env['ids']['arquivo_sha256']) == 64 and env['modo_dados'] == 'b'
    contratos.ler(job_b['job'] / 'laudo' / 'laudo.json', 'laudo/1')
    contratos.ler(job_b['job'] / 'sugestoes' / 'pacote-modelo.json', 'pacote-modelo/1')
    estado = contratos.ler(job_b['job'] / 'estado.json', 'estado/1')
    assert estado['fases']['ler']['situacao'] == 'concluida'


def test_segredos_bloqueados_em_100_por_cento_e_nunca_saem(job_b):
    env = envelope_de(job_b['saida'])
    job = job_b['job']
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    com_segredo = {c['identidade']['layer_id'] for c in laudo['camadas']
                   if any(s in c['nome'] or s in ((c.get('texto') or {}).get('conteudo') or '') for s in SEGREDOS)}
    assert len(com_segredo) == 2
    # envelope: as duas camadas sairam inteiras, as outras ficaram
    assert env['segredos_bloqueados'] == 2
    no_envelope = {c['layer_id'] for c in env['conteudo']['camadas']}
    assert not (no_envelope & com_segredo) and len(no_envelope) == 2
    # pacote-modelo: camada marcada, sem nome e sem textos
    pacote = json.loads((job / 'sugestoes' / 'pacote-modelo.json').read_text(encoding='utf-8'))
    marcadas = {c['layer_id'] for c in pacote['camadas'] if c.get('segredo_bloqueado')}
    assert marcadas == com_segredo
    for c in pacote['camadas']:
        if c['layer_id'] in com_segredo:
            assert 'nome' not in c and 'textos' not in c
    # arquivo do DA: as duas camadas, o padrao, nunca o trecho
    bloqueios = contratos.ler(job / 'sugestoes' / 'segredos-bloqueados.json', 'segredos-bloqueados/1')
    assert {b['layer_id'] for b in bloqueios['bloqueios'] if b['origem'] == 'camada'} == com_segredo
    # 0 ocorrencia no envelope, no log, no pacote e no arquivo do DA
    textos = {'envelope': job_b['saida'], 'log': (job / 'log' / 'eventos.jsonl').read_text(encoding='utf-8'),
              'pacote': (job / 'sugestoes' / 'pacote-modelo.json').read_text(encoding='utf-8'),
              'arquivo do DA': (job / 'sugestoes' / 'segredos-bloqueados.json').read_text(encoding='utf-8'),
              'estado': (job / 'estado.json').read_text(encoding='utf-8')}
    for onde, texto in textos.items():
        for s in SEGREDOS:
            assert s not in texto, onde


def test_modo_humano_avisa_o_da_sem_mostrar_o_trecho(job_b):
    codigo, saida, _ = rodar('ler', '--job', str(job_b['job']))
    assert codigo == 0
    assert 'parecido com' in saida
    for s in SEGREDOS:
        assert s not in saida


def test_modo_c_nao_leva_conteudo_nem_nome(job_b):
    job = job_b['pasta'] / 'job-c'
    assert rodar('--envelope', 'job', 'criar', str(job), '--kv', str(job_b['psd']), '--modo-dados', 'c')[0] == 0
    codigo, saida, _ = rodar('--envelope', 'job', 'proxima', str(job))
    env = envelope_de(saida)
    assert codigo == 0 and env['modo_dados'] == 'c' and 'conteudo' not in env
    for termo in ('fundo-limpo', 'camada-comum', 'texto-com-token', str(job_b['psd'].name), *SEGREDOS):
        assert termo not in saida
    pacote = json.loads((job / 'sugestoes' / 'pacote-modelo.json').read_text(encoding='utf-8'))
    assert all('nome' not in c for c in pacote['camadas'])
