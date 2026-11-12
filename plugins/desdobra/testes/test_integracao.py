# -*- coding: utf-8 -*-
"""Integracao do M1 de ponta a ponta pela CLI de verdade (subprocesso), com PSD sintetico gerado na hora.

  - detector de segredos: chave e token em nome de camada e em texto viram bloqueio em 100% dos casos, com 0
    ocorrencia no envelope, no log e no pacote-modelo; o detalhe fica so no arquivo do DA;
  - modo c: o envelope do job proxima nao leva conteudo nem nome de camada;
  - a fase ler do job proxima repassa as contagens do laudo e grava o pacote-modelo;
  - M7c, S2: nos tres modos os dois pacotes batem com a tabela da 7.4, a queda de teto refaz sem clique do DA, a
    troca do PSD no modo (a) refaz pacote e pasta, e nenhum byte, caminho ou miniatura de glifo de fonte sai.
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
    codigo, saida, _ = rodar('--envelope', '--teto-modo-dados', 'b', 'job', 'criar', str(job), '--kv', str(psd))
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
    contratos.ler(job_b['job'] / 'sugestoes' / 'pacote-modelo.json', 'pacote-modelo/2')
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
    assert rodar('--envelope', 'job', 'criar', str(job), '--kv', str(job_b['psd']))[0] == 0
    codigo, saida, _ = rodar('--envelope', 'job', 'proxima', str(job))
    env = envelope_de(saida)
    assert codigo == 0 and env['modo_dados'] == 'c' and 'conteudo' not in env
    for termo in ('fundo-limpo', 'camada-comum', 'texto-com-token', str(job_b['psd'].name), *SEGREDOS):
        assert termo not in saida
    pacote = json.loads((job / 'sugestoes' / 'pacote-modelo.json').read_text(encoding='utf-8'))
    assert all('nome' not in c for c in pacote['camadas'])


# ------------------------------------------------------------------ M7c, S2: pacote-modelo/2 por modo
FONTE_NOME = 'FonteSinteticaSegunda.ttf'


@pytest.fixture(scope='module')
def kv_s2(tmp_path_factory):
    from desdobra.render import autoteste
    pasta = tmp_path_factory.mktemp('s2')
    mini = sinteticos.miniaturas(pasta / 'psd')
    seg = psd_com_segredos(pasta)
    fonte = pasta / 'fontes-origem' / FONTE_NOME
    fonte.parent.mkdir()
    fonte.write_bytes(autoteste.gerar_fonte())
    return {'pasta': pasta, 'mini': mini, 'seg': seg, 'fonte': fonte}


def _criar_e_ler(kv, nome, modo, teto='a'):
    job = kv['pasta'] / nome
    codigo, saida, _ = rodar('--envelope', '--teto-modo-dados', teto, 'job', 'criar', str(job), '--kv', str(kv['mini']),
                             '--fontes', str(kv['fonte']))
    assert codigo == 0, saida
    if modo is not None:
        escolher_modo_do_da(job, modo)
    codigo, saida, erro = rodar('--envelope', '--teto-modo-dados', teto, 'job', 'proxima', str(job))
    assert codigo == 0, saida + erro
    return job, saida


def _pacote(job):
    return contratos.ler(job / 'sugestoes' / 'pacote-modelo.json', 'pacote-modelo/2')


def _textos_do_claude(job):
    """O que o gancho deixa o Claude ler em sugestoes/, como bytes."""
    pasta = job / 'sugestoes'
    if not pasta.exists():
        return b''
    return b'\n'.join(p.read_bytes() for p in sorted(pasta.rglob('*'))
                      if p.is_file() and p.name != 'segredos-bloqueados.json')


def _ids_por_nome(laudo):
    out = {}
    for c in laudo['camadas']:
        out.setdefault(c['nome'], c['identidade']['layer_id'])
    return out


def _sem_fonte(job, kv, *saidas):
    """0 byte, 0 caminho e 0 miniatura de glifo da fonte no que o Claude le e no envelope."""
    import hashlib
    lido = _textos_do_claude(job) + b'\n'.join(s.encode('utf-8') for s in saidas)
    pedaco = hashlib.sha256(kv['fonte'].read_bytes()).hexdigest()  # o teste compara pelo hash, sem guardar a fonte
    for termo in (FONTE_NOME, 'FonteSinteticaSegunda', str(kv['fonte']), kv['fonte'].as_posix(), 'entrada/fontes',
                  'fontes-origem', pedaco):
        assert termo.encode('utf-8') not in lido, termo
    pasta = job / 'sugestoes'
    for p in pasta.rglob('*'):
        assert p.suffix.lower() not in ('.ttf', '.otf', '.ttc', '.woff', '.woff2')
        if p.is_file():
            assert hashlib.sha256(p.read_bytes()).hexdigest() != pedaco
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    por_id = {}
    for c in laudo['camadas']:
        por_id.setdefault(c['identidade']['layer_id'], []).append(c)
    for caminho in _pacote(job)['miniaturas']:
        lid = int(caminho.rsplit('/', 1)[1][:-4])
        assert all(c['tipo'] != 'texto' and c.get('texto') is None for c in por_id[lid])


@pytest.mark.parametrize('modo', ['a', 'b', 'c'])
def test_s2_os_dois_pacotes_batem_com_o_modo(kv_s2, modo):
    job, saida_ler = _criar_e_ler(kv_s2, 'job-s2-%s' % modo, modo)
    env_ler = envelope_de(saida_ler)
    codigo, saida, _ = rodar('--envelope', '--teto-modo-dados', 'a', 'sugestao', 'pacote', '--job', str(job))
    env = envelope_de(saida)
    assert codigo == 0 and env['comando'] == 'sugestao pacote' and env['modo_dados'] == modo
    # o sugestao pacote devolve so contagens e o modo: nenhuma camada, nome ou texto
    assert not (env.get('conteudo') or {}).get('camadas') and not (env.get('conteudo') or {}).get('miniaturas')
    p = _pacote(job)
    assert p['modo_dados'] == modo and p['exposto']['miniaturas'] is (modo == 'a')
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    ids = _ids_por_nome(laudo)
    pasta = job / 'sugestoes' / 'miniaturas'
    if modo == 'a':
        esperado = sorted(ids[n] for n, entra in sinteticos.CASOS_MINIATURAS.items() if entra)
        assert esperado and p['miniaturas'] == ['sugestoes/miniaturas/%d.png' % i for i in esperado]
        assert sorted(x.name for x in pasta.iterdir()) == sorted(['%d.png' % i for i in esperado] + ['indice.json'])
        assert env['contagens']['miniaturas'] == len(esperado)
        assert set(env_ler['conteudo']['miniaturas']) <= set(p['miniaturas'])
    else:
        assert p['miniaturas'] == [] and not pasta.exists() and env['contagens']['miniaturas'] == 0
    if modo == 'c':
        lido = _textos_do_claude(job)
        for nome in list(ids) + [sinteticos.TEXTO_SINTETICO]:
            assert nome.encode('utf-8') not in lido, nome
    _sem_fonte(job, kv_s2, saida, saida_ler)


def test_s2_queda_de_teto_com_a_escolha_a_ja_gravada(kv_s2):
    job, _ = _criar_e_ler(kv_s2, 'job-s2-teto', 'a')
    assert (job / 'sugestoes' / 'miniaturas').is_dir()
    sug = job / 'sugestoes' / 'sugestoes.json'
    sug.write_text(json.dumps({'texto': sinteticos.TEXTO_SINTETICO}), encoding='utf-8')
    # a agencia baixa o teto para (b) sem clique do DA: o pacote cai junto
    codigo, saida, _ = rodar('--envelope', '--teto-modo-dados', 'b', 'sugestao', 'pacote', '--job', str(job))
    assert codigo == 0 and envelope_de(saida)['modo_dados'] == 'b'
    assert _pacote(job)['modo_dados'] == 'b' and not (job / 'sugestoes' / 'miniaturas').exists()
    assert sug.is_file()
    # e para (c): as sugestoes do Claude somem e nada legivel tem nome ou texto
    codigo, saida, _ = rodar('--envelope', '--teto-modo-dados', 'c', 'sugestao', 'pacote', '--job', str(job))
    assert codigo == 0 and envelope_de(saida)['modo_dados'] == 'c'
    assert _pacote(job)['modo_dados'] == 'c' and not sug.exists()
    lido = _textos_do_claude(job)
    for nome in list(_ids_por_nome(contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1'))) + [sinteticos.TEXTO_SINTETICO]:
        assert nome.encode('utf-8') not in lido


def test_s2_tela_abrir_e_job_proxima_conferem_o_modo(kv_s2, monkeypatch, capsys):
    from pathlib import Path

    import desdobra.tela as mod_tela
    from desdobra import cli
    from desdobra.job import nucleo
    from desdobra.resultado import Resultado
    job, _ = _criar_e_ler(kv_s2, 'job-s2-cli', 'a')
    vistos = []

    def abrir_falso(args):
        vistos.append(_pacote(job)['modo_dados'])
        return Resultado(comando='tela abrir', situacao='ok', pasta_job=Path(args.job))

    def proxima_falsa(pasta, **_k):
        vistos.append(_pacote(job)['modo_dados'])
        return Resultado(comando='job proxima', situacao='ok', pasta_job=Path(pasta))
    monkeypatch.setattr(mod_tela, '_abrir', abrir_falso)
    monkeypatch.setattr(nucleo, 'proxima', proxima_falsa)
    assert cli.principal(['--envelope', '--teto-modo-dados', 'b', 'tela', 'abrir', '--job', str(job)]) == 0
    assert vistos == ['b'] and not (job / 'sugestoes' / 'miniaturas').exists()
    (job / 'sugestoes' / 'sugestoes.json').write_text('{}', encoding='utf-8')
    assert cli.principal(['--envelope', '--teto-modo-dados', 'c', 'job', 'proxima', str(job)]) == 0
    assert vistos == ['b', 'c'] and not (job / 'sugestoes' / 'sugestoes.json').exists()
    capsys.readouterr()


def test_s2_troca_do_psd_no_modo_a(kv_s2):
    import hashlib
    job, _ = _criar_e_ler(kv_s2, 'job-s2-troca', 'a')
    antes = _pacote(job)
    assert antes['miniaturas']
    codigo, saida, _ = rodar('--envelope', '--teto-modo-dados', 'a', 'job', 'trocar-entrada', str(job), 'entrada/kv.psd',
                             str(kv_s2['seg']))
    assert codigo == 0, saida
    codigo, saida, erro = rodar('--envelope', '--teto-modo-dados', 'a', 'job', 'proxima', str(job))
    env = envelope_de(saida)
    assert codigo == 0 and env['fase'] == 'ler', saida + erro
    p = _pacote(job)
    assert p['arquivo_sha256'] == hashlib.sha256(kv_s2['seg'].read_bytes()).hexdigest() != antes['arquivo_sha256']
    ids = _ids_por_nome(contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1'))
    esperado = sorted([ids['fundo-limpo'], ids['camada-comum']])
    assert p['miniaturas'] == ['sugestoes/miniaturas/%d.png' % i for i in esperado]
    assert sorted(x.name for x in (job / 'sugestoes' / 'miniaturas').iterdir()) == \
        sorted(['%d.png' % i for i in esperado] + ['indice.json'])
    # o segredo sintetico vira bloqueio: 0 ocorrencia no pacote, no envelope, no log e na pasta
    assert p['contagens']['segredos_bloqueados'] == 2
    lido = _textos_do_claude(job) + saida.encode('utf-8') + (job / 'log' / 'eventos.jsonl').read_bytes()
    for s in SEGREDOS:
        assert s.encode('utf-8') not in lido
    _sem_fonte(job, kv_s2, saida)


# ------------------------------------------------------------------ M7c, S2: comandos que gravam o que o Claude le
def _eventos_expostos(job):
    linhas = (job / 'log' / 'eventos.jsonl').read_text(encoding='utf-8').splitlines()
    return [e for e in (json.loads(x) for x in linhas) if e['evento'] == 'pacote_modelo_exposto']


def _job_com_queda_para_c(kv_s2, nome):
    import test_specs_apoio as apoio
    specs = kv_s2['pasta'] / ('specs-' + nome) / 'veiculo'
    specs.mkdir(parents=True)
    (specs / 'vertical.html').write_text(apoio.html_vertical(), encoding='utf-8')
    job = kv_s2['pasta'] / nome
    codigo, saida, _ = rodar('--envelope', '--teto-modo-dados', 'a', 'job', 'criar', str(job), '--kv', str(kv_s2['mini']),
                             '--specs', str(specs.parent))
    assert codigo == 0, saida
    escolher_modo_do_da(job, 'a')
    assert rodar('--envelope', '--teto-modo-dados', 'a', 'job', 'proxima', str(job))[0] == 0
    assert _pacote(job)['modo_dados'] == 'a'
    # a agencia baixa o teto para (c) sem clique do DA
    assert rodar('--envelope', '--teto-modo-dados', 'c', 'sugestao', 'pacote', '--job', str(job))[0] == 0
    return job


def _sem_nome_nem_texto(job):
    lido = _textos_do_claude(job)
    for nome in list(_ids_por_nome(contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1'))) + [sinteticos.TEXTO_SINTETICO]:
        assert nome.encode('utf-8') not in lido


def test_s2_ler_respeita_o_teto_da_linha_de_comando(kv_s2):
    job = _job_com_queda_para_c(kv_s2, 'job-s2-teto-ler')
    n_eventos = len(_eventos_expostos(job))
    # o ler com o mesmo teto (c) nunca regrava o pacote no modo (a)
    codigo, saida, erro = rodar('--envelope', '--teto-modo-dados', 'c', 'ler', '--job', str(job))
    assert codigo == 0 and envelope_de(saida)['modo_dados'] == 'c', saida + erro
    assert _pacote(job)['modo_dados'] == 'c' and not (job / 'sugestoes' / 'miniaturas').exists()
    assert all(e['modo'] == 'c' for e in _eventos_expostos(job)[n_eventos:])
    _sem_nome_nem_texto(job)


def test_s2_spec_importar_respeita_o_teto_da_linha_de_comando(kv_s2):
    job = _job_com_queda_para_c(kv_s2, 'job-s2-teto-spec')
    # o spec importar com o mesmo teto (c) nunca grava o pacote das specs no modo (a)
    codigo, saida, erro = rodar('--envelope', '--teto-modo-dados', 'c', 'spec', 'importar', '--job', str(job))
    assert codigo == 0 and envelope_de(saida)['modo_dados'] == 'c', saida + erro
    ps = json.loads((job / 'sugestoes' / 'pacote-specs.json').read_text(encoding='utf-8'))
    assert ps['modo_dados'] == 'c' and not ps.get('trechos')
    assert _pacote(job)['modo_dados'] == 'c'
    _sem_nome_nem_texto(job)


def test_s2_trocar_entrada_fecha_o_pacote_do_kv_antigo(kv_s2):
    job, _ = _criar_e_ler(kv_s2, 'job-s2-troca-fecha', 'a')
    (job / 'sugestoes' / 'sugestoes.json').write_text('{}', encoding='utf-8')
    assert _pacote(job)['miniaturas']
    codigo, saida, _ = rodar('--envelope', '--teto-modo-dados', 'a', 'job', 'trocar-entrada', str(job), 'entrada/kv.psd',
                             str(kv_s2['seg']))
    assert codigo == 0, saida
    # logo depois da troca, nada do KV antigo fica legivel ate a fase ler rodar de novo
    assert not (job / 'sugestoes' / 'pacote-modelo.json').exists()
    assert not (job / 'sugestoes' / 'miniaturas').exists()
    assert not (job / 'sugestoes' / 'sugestoes.json').exists()
