# -*- coding: utf-8 -*-
"""Portao do entregar e do aprovar num job sintetico de verdade (M6, fatias 1 e 2 da proposta): PSD e fonte gerados
na hora, briefing de teste, derivacao e render de dois formatos.

Criterios de pronto cobertos aqui (arquitetura-v1.md, 9.7):
  - o fluxo do M5 com briefing de origem fixture de teste (e o rascunho) e recusado pelo entregar em 100% dos formatos;
  - arquivo velho ou trocado e detectado em 100% dos casos de mutacao: masters trocados, render.json trocado, 1 pixel
    mudado, master velho depois de mudar a funcao de uma camada dos formatos (a impressao, M7b; o briefing mudado
    fora dos formatos nao derruba), formato de outro KV, contrato mexido, derivacao mexida;
  - a aprovacao anterior cai quando o master, o render.json, a impressao do formato, o contrato, o arquivo final ou
    os parametros do encoder mudam, e o resultado diz o campo por formato (nº 138); aprovacao mexida a mao, copiada de outro job e de
    formato que nao existe mais;
  - entrega de verdade (bloco 3): com folha confirmada sintetica, o entregar roteia pela validacao final (o formato com
    teto condicional sem a escolha do DA vai para reprovados com a regra e a sugestao, nº 137; o aprovado fica abaixo
    da leitura estrita do teto e passa na conferencia sRGB), e o conferir-entrega pela CLI so le e pega o arquivo
    trocado depois da entrega.

O render e o aprovar so partem de uma pessoa: o console e simulado pelo fixture pessoa (o caminho do Disparo e o de
verdade). Os testes da aprovacao usam um encoder de teste (o master como arquivo final); o encoder de verdade
(desdobra.entrega.codificar) e conferido no fim do arquivo, com specs confirmadas sinteticas gravadas na copia do job, e
num job com um formato girado de 90 graus renderizado de verdade (o master e a composicao; a entrega gira).
"""
import io
import json
import os
import shutil
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import test_derivacao_apoio as ap
import test_fontes_apoio as fap
import test_render_apoio as rap
from desdobra import arquivos, contratos, entrega, humano
from desdobra.briefing import modelo as mb
from desdobra.entrega import aprovacao, codificar, portao
from desdobra.job import nucleo
from desdobra.render import execucao
from desdobra.resultado import Codigo

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')

ROT0 = {'graus': 0, 'sentido': None}
FORMATOS = [ap.formato('mesma', 640, 320, rotacao=ROT0), ap.formato('perto', 400, 240, rotacao=ROT0)]
IDS = [f['id'] for f in FORMATOS]


def _cli(python, *args):
    r = subprocess.run([python, '-m', 'desdobra', '--envelope', *args], capture_output=True, timeout=300)
    return r.returncode, json.loads(r.stdout.decode('utf-8').strip().splitlines()[-1])


def _mudar_briefing(job, **cabecalho):
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    b['cabecalho'].update(cabecalho)
    if b['cabecalho']['origem'] == 'da' and 'composicoes' not in b:
        # o briefing do DA sai do gravador da tela, sempre com as familias confirmadas na janela (revisao do M7a)
        b['composicoes'] = [{'familia': 'familia-%s' % f['id'], 'formatos': [f['id']], 'versao': None, 'edicoes': [],
                             'confirmada': True,
                             'confirmacao': {'origem': 'da', 'meio': 'tela', 'em': '2026-11-05T10:00:00'}}
                            for f in b['formatos']]
    contratos.gravar(job / mb.ARQUIVO, b, 'briefing/1')


def _mudar_funcao(job):
    """A funcao do texto de apoio muda (mesma ancora e mesma regra): a impressao dos formatos que tem a camada muda."""
    laudo = contratos.ler(job / mb.ARQUIVO_LAUDO, 'laudo/1')
    lid = next(c['identidade']['layer_id'] for c in laudo['camadas'] if c['nome'] == 'texto-apoio')
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    next(x for x in b['funcoes'] if x['layer_id'] == lid)['funcao'] = ap.decisao('informacao_de_evento')
    contratos.gravar(job / mb.ARQUIVO, b, 'briefing/1')


@pytest.fixture(scope='module')
def job_ent(tmp_path_factory):
    base = tmp_path_factory.mktemp('entrega')
    fontes = base / 'origem-fontes'
    fap.gravar(fontes, 'inventada.ttf', fap.fonte(ps=rap.FONTE))
    job = base / 'job'
    nucleo.criar(job, ap.psd_derivacao(base / 'origem' / 'kv.psd'), 'c', fontes=[fontes])
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    b, _ids = ap.briefing_do_job(laudo, FORMATOS)
    arq = base / 'fixture-m6.json'
    arq.write_text(json.dumps(b), encoding='utf-8')
    mb.importar_teste(job, arq)
    # o briefing do DA so chega com a tela (M7): aqui a origem e trocada a mao, antes de derivar e renderizar
    _mudar_briefing(job, origem='da', meio='terminal')
    cod, env = _cli(sys.executable, 'derivar', '--job', str(job))
    assert cod == 0, env
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(humano, 'console_interativo', lambda: (True, None))
        for fid in IDS:
            execucao.renderizar(job, disparo=humano.exigir('render'), formato=fid)
    return job


@pytest.fixture
def copia(job_ent, tmp_path):
    destino = tmp_path / 'job'
    shutil.copytree(job_ent, destino)
    return destino


def _codigos(conf, fid):
    return [f['codigo'] for f in conf['formatos'][fid]['falhas']]


def _portao(job, **k):
    k.setdefault('aprovacao', False)
    k.setdefault('final', False)
    return portao.conferir(job, **k)


def _gravar_render(job, fid, mexer):
    """Mexe no render.json do formato e grava de novo, coerente com o contrato (o arquivo continua no contrato)."""
    arq = job / 'render' / fid / 'render.json'
    rel = contratos.ler(arq, execucao.ESQUEMA_RENDER)
    mexer(rel)
    arquivos.gravar_json_atomico(arq, rel)


def _pixel(job, fid):
    arq = job / 'render' / fid / 'master.png'
    img = np.array(Image.open(io.BytesIO(arq.read_bytes())))
    img[0, 0, 0] = (int(img[0, 0, 0]) + 1) % 256  # numero-neutro: um nivel a mais num canal de 8 bits
    buf = io.BytesIO()
    Image.fromarray(img).save(buf, format='PNG')
    arq.write_bytes(buf.getvalue())


# ------------------------------------------------------------------ o job limpo passa no portao
def test_job_do_da_passa_no_portao_ate_a_aprovacao(job_ent):
    conf = _portao(job_ent)
    assert conf['briefing'] is None and sorted(conf['formatos']) == sorted(IDS)
    assert all(not item['falhas'] for item in conf['formatos'].values()), conf
    conf = _portao(job_ent, aprovacao=True)
    assert all(_codigos(conf, fid) == ['sem_aprovacao'] for fid in IDS)


def test_portao_com_o_encoder_recusa_formato_sem_spec_confirmada(job_ent):
    # os formatos do job sintetico sao de teste, sem folha: sem specs/formatos-do-job.json, o encoder nao sabe o tipo
    # nem o teto e recusa (nada e inventado)
    conf = portao.conferir(job_ent, aprovacao=False)
    assert all(_codigos(conf, fid) == ['formato_sem_spec_confirmada'] for fid in IDS)


# ------------------------------------------------------------------ fixture de teste e rascunho: 100% recusado
@pytest.mark.parametrize('origem, meio, codigo', [('fixture_de_teste', 'importar_teste', 'briefing_de_fixture_de_teste'),
                                                  ('rascunho', 'rascunho', 'briefing_rascunho')])
def test_briefing_que_nao_e_do_da_recusa_todo_formato(copia, pessoa, origem, meio, codigo):
    _mudar_briefing(copia, origem=origem, meio=meio)
    conf = _portao(copia, aprovacao=True, final=True)
    assert conf['briefing'] == codigo
    assert {fid: _codigos(conf, fid) for fid in conf['formatos']} == {fid: [codigo] for fid in IDS}
    r = entrega._entregar(Namespace(job=str(copia)))
    assert r.codigo == int(Codigo.RECUSADO)
    assert r.contagens['recusa_%s' % codigo] == len(IDS) == r.contagens['formatos']
    assert not (copia / 'entrega' / 'aprovados').exists()


# ------------------------------------------------------------------ arquivo velho ou trocado
def _trocar_masters(job):
    a, b = (job / 'render' / f / 'master.png' for f in IDS)
    da, db = a.read_bytes(), b.read_bytes()
    a.write_bytes(db)
    b.write_bytes(da)


def _trocar_render_json(job):
    a, b = (job / 'render' / f / 'render.json' for f in IDS)
    da, db = a.read_bytes(), b.read_bytes()
    a.write_bytes(db)
    b.write_bytes(da)


def _outro_kv(job):
    """O formato perto vira um render de outro KV: contrato e render.json coerentes entre si, com outro kv_sha256."""
    arq = job / 'render' / 'perto' / 'contrato.json'
    c = contratos.ler(arq, 'composicao/1')
    c['origem']['kv_sha256'] = 'e' * 64
    contratos.gravar(arq, c, 'composicao/1')
    _gravar_render(job, 'perto', lambda rel: rel.update(contrato_sha256=arquivos.sha256_arquivo(arq)))


def _contrato_mexido_coerente(job):
    arq = job / 'render' / 'perto' / 'contrato.json'
    c = contratos.ler(arq, 'composicao/1')
    c['registros'].append({'codigo': 'registro_inventado'})
    contratos.gravar(arq, c, 'composicao/1')
    _gravar_render(job, 'perto', lambda rel: rel.update(contrato_sha256=arquivos.sha256_arquivo(arq)))


def _contrato_mexido(job):
    arq = job / 'render' / 'perto' / 'contrato.json'
    c = contratos.ler(arq, 'composicao/1')
    c['registros'].append({'codigo': 'registro_inventado'})
    contratos.gravar(arq, c, 'composicao/1')


def _derivacao_mexida(job):
    arq = job / 'derivacao' / 'perto.json'
    d = arquivos.ler_json(arq)
    d['elementos'][0]['transformacao']['destino'][0] += 1
    arquivos.gravar_json_atomico(arq, d)


def _sem_master(job):
    (job / 'render' / 'perto' / 'master.png').unlink()


def _render_de_outro_job(job):
    _gravar_render(job, 'perto', lambda rel: rel.update(job_id='f' * 32))


def _aceite_a_mais(job):
    """O render.json do formato diz que o DA aceitou uma decisao que o contrato de agora nao pede (nº 86)."""
    _gravar_render(job, 'perto', lambda rel: rel.update(aceites=list(rel.get('aceites') or []) +
                                                        [{'codigo': 'decisao_inventada'}]))


MUTACOES_PORTAO = [
    ('aceite_a_mais', _aceite_a_mais, {'perto': 'aceites_diferentes'}),
    ('masters_trocados', _trocar_masters, {'mesma': 'master_diferente_do_render', 'perto': 'master_diferente_do_render'}),
    ('render_json_trocado', _trocar_render_json, {'mesma': 'render_de_outro_formato', 'perto': 'render_de_outro_formato'}),
    ('um_pixel', lambda j: _pixel(j, 'perto'), {'perto': 'master_diferente_do_render'}),
    ('master_velho_depois_da_funcao', lambda j: _mudar_funcao(j),
     {'mesma': 'master_de_outra_impressao', 'perto': 'master_de_outra_impressao'}),
    # o briefing que muda fora do que alimenta os formatos (o carimbo do cabecalho) nao derruba nenhum (M7b, A2)
    ('briefing_mudado_fora_dos_formatos', lambda j: _mudar_briefing(j, quando='2026-11-04T11:00:00-03:00'), {}),
    ('formato_de_outro_kv', _outro_kv, {'perto': 'master_de_outro_kv'}),
    ('contrato_mexido', _contrato_mexido, {'perto': 'contrato_diferente_do_render'}),
    ('contrato_mexido_coerente', _contrato_mexido_coerente, {'perto': 'contrato_desatualizado'}),
    ('derivacao_mexida', _derivacao_mexida, {'perto': 'master_de_outra_impressao'}),
    ('sem_master', _sem_master, {'perto': 'sem_master'}),
    ('render_de_outro_job', _render_de_outro_job, {'perto': 'render_de_outro_job'}),
]


@pytest.mark.parametrize('nome, mexer, esperado', MUTACOES_PORTAO, ids=[m[0] for m in MUTACOES_PORTAO])
def test_arquivo_velho_ou_trocado_e_recusado(copia, nome, mexer, esperado):
    mexer(copia)
    conf = _portao(copia)
    for fid in IDS:
        if fid in esperado:
            assert esperado[fid] in _codigos(conf, fid), (nome, fid, _codigos(conf, fid))
        else:
            assert _codigos(conf, fid) == [], (nome, fid, _codigos(conf, fid))


def test_mutacoes_do_portao_detectadas_em_100_por_cento(job_ent, tmp_path):
    detectadas = 0
    for k, (_nome, mexer, esperado) in enumerate(MUTACOES_PORTAO):
        job = tmp_path / ('m%02d' % k)
        shutil.copytree(job_ent, job)
        mexer(job)
        conf = _portao(job)
        detectadas += all(_codigos(conf, fid) for fid in esperado)
    assert detectadas == len(MUTACOES_PORTAO)


# ------------------------------------------------------------------ aprovacao (nº 138)
def _encoder_de_teste(qualidade=90, sufixo=b''):
    def arquivo_final(pasta, formato):
        dados = (Path(pasta) / 'render' / formato / 'master.png').read_bytes() + sufixo
        return codificar.ArquivoFinal(dados=dados, extensao='png', parametros={'tipo': 'png', 'qualidade': qualidade})
    return arquivo_final


def _aprovar(job, monkeypatch, formatos=IDS, resposta='sim'):
    monkeypatch.setattr(humano, 'ler', lambda pergunta: resposta)
    return entrega._aprovar(Namespace(job=str(job), formato=list(formatos)))


def test_aprovar_com_o_encoder_sem_spec_confirmada_recusa_e_nao_grava(copia, pessoa, monkeypatch):
    r = _aprovar(copia, monkeypatch)
    assert r.codigo == int(Codigo.RECUSADO) and r.contagens['recusa_formato_sem_spec_confirmada'] == len(IDS)
    assert not (copia / aprovacao.ARQUIVO).exists()


def test_aprovar_cancelado_nao_grava(copia, pessoa, monkeypatch):
    monkeypatch.setattr(codificar, 'arquivo_final', _encoder_de_teste())
    r = _aprovar(copia, monkeypatch, resposta='nao')
    assert r.codigo == int(Codigo.RECUSADO)
    assert not (copia / aprovacao.ARQUIVO).exists()


def test_aprovar_formato_que_nao_existe_recusa(copia, pessoa, monkeypatch):
    monkeypatch.setattr(codificar, 'arquivo_final', _encoder_de_teste())
    r = _aprovar(copia, monkeypatch, formatos=['perto', 'sumiu'])
    assert r.codigo == int(Codigo.RECUSADO) and r.contagens['recusa_formato_inexistente'] == 1
    assert not (copia / aprovacao.ARQUIVO).exists()


def test_aprovar_recusa_quando_o_job_muda_durante_a_confirmacao(copia, pessoa, monkeypatch):
    monkeypatch.setattr(codificar, 'arquivo_final', _encoder_de_teste())

    def responde_e_mexe(pergunta):
        _gravar_render(copia, 'perto', lambda rel: rel.update(gerado_em='2026-11-04T12:00:00-03:00'))
        return 'sim'
    monkeypatch.setattr(humano, 'ler', responde_e_mexe)
    r = entrega._aprovar(Namespace(job=str(copia), formato=list(IDS)))
    assert r.codigo == int(Codigo.RECUSADO) and r.contagens == {'recusa_mudou_durante_a_confirmacao': 1}
    assert not (copia / aprovacao.ARQUIVO).exists()


def test_aprovar_grava_um_registro_por_formato_e_o_portao_abre(copia, pessoa, monkeypatch):
    monkeypatch.setattr(codificar, 'arquivo_final', _encoder_de_teste())
    r = _aprovar(copia, monkeypatch)
    assert r.codigo == 0, r.linhas_humanas
    dados = contratos.ler(copia / aprovacao.ARQUIVO, aprovacao.ESQUEMA)
    assert sorted(dados['formatos']) == sorted(IDS)
    for fid in IDS:
        reg = dados['formatos'][fid]
        master = copia / 'render' / fid / 'master.png'
        assert reg['master_sha256'] == arquivos.sha256_arquivo(master) == reg['arquivo_entregue']['sha256']
        assert reg['impressao_formato'] == arquivos.ler_json(copia / 'derivacao' / ('%s.json' % fid))['impressao_formato']
        assert reg['parametros_encoder'] == {'qualidade': 90, 'tipo': 'png'}
        assert (copia / aprovacao.PASTA_PREVIA / ('%s.png' % fid)).read_bytes() == master.read_bytes()
    conf = portao.conferir(copia)
    assert all(not item['falhas'] for item in conf['formatos'].values()), conf
    # a aprovacao nao desatualiza o briefing
    pode, motivo = mb.conferir_para_entrega(copia)
    assert pode, motivo
    # com o portao aberto, o entregar grava (bloco 3): sem folha confirmada e com o encoder de teste (sem os
    # parametros de rotacao e perfil), os dois arquivos vao para reprovados e nada vai para aprovados
    r = entrega._entregar(Namespace(job=str(copia)))
    assert r.codigo == 0 and r.contagens['aprovados'] == 0 and r.contagens['reprovados'] == len(IDS), r.linhas_humanas
    assert r.contagens['reprova_formato_sem_spec_confirmada'] == len(IDS)
    assert not list((copia / 'entrega' / 'aprovados').iterdir())
    assert sorted(p.name for p in (copia / 'entrega' / 'reprovados').iterdir()) == sorted('%s.png' % f for f in IDS)


def _master_novo(job):
    """Master novo do formato perto com render.json coerente (como um render novo): so a aprovacao pega."""
    _pixel(job, 'perto')
    novo = arquivos.sha256_arquivo(job / 'render' / 'perto' / 'master.png')
    _gravar_render(job, 'perto', lambda rel: rel['master'].update(sha256=novo))


def _aprovacao_mexida(job):
    arq = job / aprovacao.ARQUIVO
    d = arquivos.ler_json(arq)
    d['formatos']['perto']['parametros_encoder']['qualidade'] = 95
    arquivos.gravar_json_atomico(arq, d)


def _aprovacao_de_outro_job(job):
    arq = job / aprovacao.ARQUIVO
    d = arquivos.ler_json(arq)
    d['job_id'] = 'f' * 32
    arquivos.gravar_json_atomico(arq, d)


MUTACOES_APROVACAO = [
    ('master', _master_novo, None, 'aprovacao_caiu', {'master_sha256', 'render_json_sha256', 'arquivo_entregue_sha256'}),
    ('render_json', lambda j: _gravar_render(j, 'perto', lambda rel: rel.update(gerado_em='2026-11-04T12:00:00-03:00')),
     None, 'aprovacao_caiu', {'render_json_sha256'}),
    ('funcao', _mudar_funcao, None, 'aprovacao_caiu', {'impressao_formato'}),
    ('contrato', _contrato_mexido_coerente, None, 'aprovacao_caiu', {'contrato_sha256', 'render_json_sha256'}),
    ('parametros_encoder', None, _encoder_de_teste(qualidade=80), 'aprovacao_caiu', {'parametros_encoder.qualidade'}),
    ('arquivo_final', None, _encoder_de_teste(sufixo=b'x'), 'aprovacao_caiu', {'arquivo_entregue_sha256'}),
    ('aprovacao_mexida_a_mao', _aprovacao_mexida, None, 'aprovacao_caiu',
     {'registro_sha256', 'parametros_encoder.qualidade'}),
    ('aprovacao_de_outro_job', _aprovacao_de_outro_job, None, 'aprovacao_de_outro_job', None),
]


@pytest.fixture(scope='module')
def job_aprovado(job_ent, tmp_path_factory):
    job = tmp_path_factory.mktemp('aprovado') / 'job'
    shutil.copytree(job_ent, job)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(humano, 'console_interativo', lambda: (True, None))
        mp.setattr(codificar, 'arquivo_final', _encoder_de_teste())
        mp.setattr(humano, 'ler', lambda pergunta: 'sim')
        assert entrega._aprovar(Namespace(job=str(job), formato=list(IDS))).codigo == 0
    return job


def _aprovacao_do_formato(conf, fid):
    return [f for f in conf['formatos'][fid]['falhas'] if f['codigo'].startswith('aprovacao') or f['codigo'] ==
            'sem_aprovacao']


@pytest.mark.parametrize('nome, mexer, encoder, codigo, campos', MUTACOES_APROVACAO,
                         ids=[m[0] for m in MUTACOES_APROVACAO])
def test_aprovacao_cai_e_diz_o_campo(job_aprovado, tmp_path, monkeypatch, nome, mexer, encoder, codigo, campos):
    job = tmp_path / 'job'
    shutil.copytree(job_aprovado, job)
    monkeypatch.setattr(codificar, 'arquivo_final', encoder or _encoder_de_teste())
    if mexer:
        mexer(job)
    conf = portao.conferir(job)
    quedas = _aprovacao_do_formato(conf, 'perto')
    assert [f['codigo'] for f in quedas] == [codigo], (nome, conf['formatos']['perto']['falhas'])
    if campos is not None:
        assert set(quedas[0]['medidas']['campos']) == campos, (nome, quedas[0]['medidas'])


def test_mutacoes_da_aprovacao_detectadas_em_100_por_cento(job_aprovado, tmp_path, monkeypatch):
    detectadas = 0
    for k, (_nome, mexer, encoder, _codigo, _campos) in enumerate(MUTACOES_APROVACAO):
        job = tmp_path / ('m%02d' % k)
        shutil.copytree(job_aprovado, job)
        monkeypatch.setattr(codificar, 'arquivo_final', encoder or _encoder_de_teste())
        if mexer:
            mexer(job)
        detectadas += bool(_aprovacao_do_formato(portao.conferir(job), 'perto'))
    assert detectadas == len(MUTACOES_APROVACAO)


def test_registro_de_formato_que_saiu_do_briefing_nao_conta(job_aprovado, tmp_path, monkeypatch):
    job = tmp_path / 'job'
    shutil.copytree(job_aprovado, job)
    monkeypatch.setattr(codificar, 'arquivo_final', _encoder_de_teste())
    arq = job / aprovacao.ARQUIVO
    d = arquivos.ler_json(arq)
    d['formatos']['sumiu'] = dict(d['formatos']['perto'], formato='sumiu')
    arquivos.gravar_json_atomico(arq, d)
    conf = portao.conferir(job)
    assert sorted(conf['formatos']) == sorted(IDS)
    assert all(not item['falhas'] for item in conf['formatos'].values())


def test_entregar_lista_a_queda_por_formato(job_aprovado, tmp_path, pessoa, monkeypatch):
    job = tmp_path / 'job'
    shutil.copytree(job_aprovado, job)
    monkeypatch.setattr(codificar, 'arquivo_final', _encoder_de_teste())
    _master_novo(job)
    r = entrega._entregar(Namespace(job=str(job)))
    assert r.codigo == int(Codigo.RECUSADO) and r.contagens['recusa_aprovacao_caiu'] == 1
    linha = next(x for x in r.linhas_humanas if x.strip().startswith('perto: aprovacao_caiu'))
    assert 'master_sha256' in linha


def test_invalidar_render_derruba_a_aprovacao_do_job(job_aprovado, tmp_path):
    job = tmp_path / 'job'
    shutil.copytree(job_aprovado, job)
    assert nucleo.invalidar_render(job) >= len(IDS)
    assert not (job / aprovacao.ARQUIVO).exists() and not (job / aprovacao.PASTA_PREVIA).exists()


# ------------------------------------------------------------------ encoder de verdade no job (fatias 3 e 7)
TIPOS = {'id': 'tipos', 'valor': ['image/jpeg', 'image/png'], 'situacao': 'confirmado'}


def _peso(alvo, condicao=None):
    return {'id': 'peso', 'valor': {'alvo_bytes': alvo, 'reprova_acima_bytes': alvo + 6000}, 'condicao': condicao,
            'situacao': 'confirmado'}


def _gravar_specs(job, campos_por_formato):
    """specs/formatos-do-job.json sintetico, so com o que o encoder le (chave, tipos e pesos confirmados)."""
    b = mb.ler(job)
    chaves = {f['id']: f['chave'] for f in b['formatos']}
    doc = {'tipo': 'formatos_do_job', 'formatos': [{'id': fid, 'chave': chaves[fid], 'campos': campos}
                                                  for fid, campos in campos_por_formato.items()]}
    arquivos.gravar_json_atomico(job / mb.ARQUIVO_FORMATOS, doc)


def _gravar_parametros(job, por_formato):
    quem = {'meio': 'terminal', 'usuario': 'teste', 'maquina': 'teste', 'quando': '2026-11-04T10:00:00-03:00'}
    formatos = {fid: {k: {'valor': v, 'confirmado_por': quem} for k, v in campos.items()}
                for fid, campos in por_formato.items()}
    contratos.gravar(job / portao.ARQUIVO_PARAMETROS, {'esquema': portao.ESQUEMA_PARAMETROS, 'formatos': formatos},
                     portao.ESQUEMA_PARAMETROS)


def _mudar_formato(job, fid, **campos):
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    for f in b['formatos']:
        if f['id'] == fid:
            f.update(campos)
    contratos.gravar(job / mb.ARQUIVO, b, 'briefing/1')


def _pixels(dados):
    return np.asarray(Image.open(io.BytesIO(dados)).convert('RGB'))


def _master(job, fid):
    return np.asarray(Image.open(job / 'render' / fid / 'master.png').convert('RGB'))


def test_arquivo_final_do_job_fica_abaixo_do_teto_estrito(copia):
    _gravar_specs(copia, {'mesma': {'tipos_aceitos': dict(TIPOS, valor=['image/jpeg']), 'peso_max': _peso(9000)},
                          'perto': {'tipos_aceitos': TIPOS, 'peso_max_hospedado': _peso(250000, 'hospedado'),
                                    'peso_max_tag': _peso(500000, 'por_tag')}})
    f = codificar.arquivo_final(copia, 'mesma')
    assert f.extensao == 'jpg' and len(f.dados) <= 9000 and f.parametros['teto']['regra'] == 'leitura_decimal'
    assert Image.open(io.BytesIO(f.dados)).size == (640, 320)
    f = codificar.arquivo_final(copia, 'perto')
    assert f.parametros['teto']['regra'] == 'condicao_nao_decidida' and f.parametros['teto']['alvo_bytes'] == 250000
    assert f.extensao == 'png' and np.array_equal(_pixels(f.dados), _master(copia, 'perto'))
    _gravar_parametros(copia, {'perto': {'condicao': 'por_tag'}})
    f = codificar.arquivo_final(copia, 'perto')
    assert (f.parametros['teto']['alvo_bytes'], f.parametros['teto']['regra'], f.parametros['teto']['condicao']) == \
        (500000, 'leitura_decimal', 'por_tag')
    # duas execucoes, os mesmos bytes
    assert codificar.arquivo_final(copia, 'perto').sha256 == f.sha256


def test_arquivo_final_recusa_perfil_embutido_e_transparencia_sem_cor(copia):
    from desdobra import ds
    _gravar_specs(copia, {'perto': {'tipos_aceitos': TIPOS, 'peso_max': _peso(10 ** 6)}})
    contratos.gravar(copia / ds.ARQUIVO_PARAMETROS, {'esquema': ds.ESQUEMA_PARAMETROS, 'perfil_embutido_na_saida': True},
                     ds.ESQUEMA_PARAMETROS)
    with pytest.raises(codificar.ErroCodificar) as e:
        codificar.arquivo_final(copia, 'perto')
    assert e.value.codigo == 'perfil_embutido_sem_perfil_fixo'
    (copia / ds.ARQUIVO_PARAMETROS).unlink()
    arq = copia / 'render' / 'perto' / 'master.png'
    img = Image.open(io.BytesIO(arq.read_bytes())).convert('RGBA')
    img.putpixel((0, 0), (0, 0, 0, 0))
    img.save(arq, format='PNG')
    with pytest.raises(codificar.ErroCodificar) as e:
        codificar.arquivo_final(copia, 'perto')
    assert e.value.codigo == 'cor_de_achatamento_nao_definida'
    _gravar_parametros(copia, {'perto': {'cor_de_achatamento': '#ffffff'}})
    f = codificar.arquivo_final(copia, 'perto')
    assert f.parametros['achatamento'] == {'cor': '#ffffff'} and tuple(_pixels(f.dados)[0, 0]) == (255, 255, 255)


def test_arquivo_final_gira_no_sentido_confirmado(copia):
    _gravar_specs(copia, {'perto': {'tipos_aceitos': dict(TIPOS, valor=['image/png']), 'peso_max': _peso(10 ** 6)}})
    master = _master(copia, 'perto')  # 400 x 240: a composicao
    # o arquivo do veiculo e 240 x 400, girado 90 graus
    _mudar_formato(copia, 'perto', largura=240, altura=400, rotacao={'graus': 90, 'sentido': None})
    with pytest.raises(codificar.ErroCodificar) as e:
        codificar.arquivo_final(copia, 'perto')
    assert e.value.codigo == 'rotacao_sem_sentido_confirmado'
    for sentido, k in (('horario', -1), ('anti_horario', 1)):
        _gravar_parametros(copia, {'perto': {'rotacao_sentido': sentido}})
        out = _pixels(codificar.arquivo_final(copia, 'perto').dados)
        assert out.shape == (400, 240, 3) and np.array_equal(out, np.rot90(master, k)), sentido
    # 180 graus: sem sentido, mesma dimensao
    _mudar_formato(copia, 'perto', largura=400, altura=240, rotacao={'graus': 180, 'sentido': None})
    (copia / portao.ARQUIVO_PARAMETROS).unlink()
    assert np.array_equal(_pixels(codificar.arquivo_final(copia, 'perto').dados), master[::-1, ::-1])
    # rotacao sem decisao recusa
    _mudar_formato(copia, 'perto', rotacao=None)
    with pytest.raises(codificar.ErroCodificar) as e:
        codificar.arquivo_final(copia, 'perto')
    assert e.value.codigo == 'rotacao_nao_decidida'
    # master que nao e a composicao do formato (dimensao trocada sem rotacao)
    _mudar_formato(copia, 'perto', largura=240, altura=400, rotacao={'graus': 0, 'sentido': None})
    with pytest.raises(codificar.ErroCodificar) as e:
        codificar.arquivo_final(copia, 'perto')
    assert e.value.codigo == 'master_com_dimensao_errada'


@pytest.fixture(scope='module')
def job_girado(tmp_path_factory):
    """Job com um formato girado de 90 graus (240 x 400 no arquivo, 400 x 240 na composicao), renderizado de verdade
    pelo caminho do Disparo (console simulado, como no job_ent)."""
    base = tmp_path_factory.mktemp('girado')
    fontes = base / 'origem-fontes'
    fap.gravar(fontes, 'inventada.ttf', fap.fonte(ps=rap.FONTE))
    job = base / 'job'
    nucleo.criar(job, ap.psd_derivacao(base / 'origem' / 'kv.psd'), 'c', fontes=[fontes])
    assert nucleo.proxima(job, todas=True).codigo == 0
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    formatos = [FORMATOS[0], ap.formato('girado', 240, 400, rotacao={'graus': 90, 'sentido': None})]
    b, _ids = ap.briefing_do_job(laudo, formatos)
    arq = base / 'fixture-girado.json'
    arq.write_text(json.dumps(b), encoding='utf-8')
    mb.importar_teste(job, arq)
    _mudar_briefing(job, origem='da', meio='terminal')
    cod, env = _cli(sys.executable, 'derivar', '--job', str(job))
    assert cod == 0, env
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(humano, 'console_interativo', lambda: (True, None))
        execucao.renderizar(job, disparo=humano.exigir('render'), formato='girado')
    return job


def test_formato_girado_renderiza_a_composicao_e_a_entrega_gira(job_girado, tmp_path):
    job = tmp_path / 'job'
    shutil.copytree(job_girado, job)
    master = _master(job, 'girado')
    assert master.shape == (240, 400, 3)  # a composicao: 400 x 240
    _contrato, bloqueios, _c = execucao.montar_contrato(job, 'girado')
    assert not bloqueios
    assert _codigos(_portao(job, formatos=['girado']), 'girado') == ['rotacao_sem_sentido_confirmado']
    _gravar_parametros(job, {'girado': {'rotacao_sentido': 'horario'}})
    assert _codigos(_portao(job, formatos=['girado']), 'girado') == []
    _gravar_specs(job, {'girado': {'tipos_aceitos': dict(TIPOS, valor=['image/png']), 'peso_max': _peso(10 ** 6)}})
    out = _pixels(codificar.arquivo_final(job, 'girado').dados)
    assert out.shape == (400, 240, 3) and np.array_equal(out, np.rot90(master, -1))


# ------------------------------------------------------------------ entrega de verdade no job (fatias 4 e 6)
# folha confirmada sintetica gravada antes do briefing (o cabecalho guarda o hash dela): 'mesma' so aceita JPEG com
# teto unico que cabe; 'perto' tem teto condicional (hospedado e por tag) sem a escolha do DA, e o hospedado e menor
# que qualquer JPEG do formato
SPECS_ENTREGA = {'mesma': {'tipos_aceitos': dict(TIPOS, valor=['image/jpeg']), 'peso_max': _peso(9000)},
                 'perto': {'tipos_aceitos': TIPOS, 'peso_max_hospedado': _peso(500, 'hospedado'),
                           'peso_max_tag': _peso(900000, 'por_tag')}}


@pytest.fixture(scope='module')
def job_entregue(tmp_path_factory):
    """Job com folha confirmada, renderizado, aprovado com o encoder de verdade e entregue, pelo caminho do Disparo
    (console simulado, como no job_ent)."""
    base = tmp_path_factory.mktemp('entregue')
    fontes = base / 'origem-fontes'
    fap.gravar(fontes, 'inventada.ttf', fap.fonte(ps=rap.FONTE))
    job = base / 'job'
    nucleo.criar(job, ap.psd_derivacao(base / 'origem' / 'kv.psd'), 'c', fontes=[fontes])
    assert nucleo.proxima(job, todas=True).codigo == 0
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    b, _ids = ap.briefing_do_job(laudo, FORMATOS)
    chaves = {f['id']: f['chave'] for f in FORMATOS}
    arquivos.gravar_json_atomico(job / mb.ARQUIVO_FORMATOS, {
        'tipo': 'formatos_do_job', 'formatos': [{'id': fid, 'chave': chaves[fid], 'campos': campos}
                                               for fid, campos in SPECS_ENTREGA.items()]})
    # o "spec confirmar" do DA grava este arquivo pela fase specs; aqui a fase fica com o hash da saida sintetica
    from desdobra.job import fases as mod_fases
    estado = nucleo.ler_estado(job)
    estado['fases']['specs']['hash_saidas'] = nucleo.hashes_das_saidas(
        job, next(f for f in mod_fases.ESTEIRA if f.id == 'specs'))
    nucleo.gravar_estado(job, estado)
    assert nucleo.proxima(job, todas=True).codigo == 0
    arq = base / 'fixture-entrega.json'
    arq.write_text(json.dumps(b), encoding='utf-8')
    mb.importar_teste(job, arq)
    _mudar_briefing(job, origem='da', meio='terminal')
    cod, env = _cli(sys.executable, 'derivar', '--job', str(job))
    assert cod == 0, env
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(humano, 'console_interativo', lambda: (True, None))
        for fid in IDS:
            execucao.renderizar(job, disparo=humano.exigir('render'), formato=fid)
        mp.setattr(humano, 'ler', lambda pergunta: 'sim')
        assert entrega._aprovar(Namespace(job=str(job), formato=list(IDS))).codigo == 0
        r = entrega._entregar(Namespace(job=str(job)))
    return job, r


def test_entregar_roteia_pela_validacao_final(job_entregue):
    job, r = job_entregue
    assert r.codigo == 0 and r.situacao == 'ok', r.linhas_humanas
    assert (r.contagens['aprovados'], r.contagens['reprovados']) == (1, 1)
    raiz = job / 'entrega'
    assert [p.name for p in (raiz / 'aprovados').iterdir()] == ['mesma.jpg']
    assert [p.name for p in (raiz / 'reprovados').iterdir()] == ['perto.jpg']
    rel = contratos.ler(raiz / 'relatorio-entrega.json', 'relatorio-entrega/1')
    por = {a['formato']: a for a in rel['arquivos']}
    # 100% de aprovados abaixo da leitura estrita do teto; o reprovado tem regra e sugestao
    assert por['mesma']['bytes'] <= 9000 and por['mesma']['regras'] == []
    assert por['perto']['regras'] == ['condicao_nao_decidida'] and por['perto']['sugestoes']
    assert (raiz / 'aprovados' / 'mesma.jpg').read_bytes() == codificar.arquivo_final(job, 'mesma').dados
    # o arquivo entregue e o aprovado (nº 138) e passou pela conferencia sRGB
    aprov = contratos.ler(job / aprovacao.ARQUIVO, aprovacao.ESQUEMA)
    assert aprov['formatos']['mesma']['arquivo_entregue']['sha256'] == por['mesma']['sha256']
    srgb = {v['nome']: v for v in por['mesma']['verificacoes']}
    assert srgb['arquivo_do_master']['situacao'] == srgb['caminho_de_cor']['situacao'] == 'ok'
    assert srgb['arquivo_do_master']['medidas']['comparacao'] == 'bytes_do_reencode'
    # nenhum arquivo de fonte na entrega (nº 143), e a previa da aprovacao fica fora da troca
    assert not [p for p in raiz.rglob('*') if p.is_file() and arquivos.eh_arquivo_de_fonte(p)]
    assert (raiz / 'previa').is_dir()


def test_conferir_entrega_pela_cli_so_le(job_entregue, tmp_path):
    job = tmp_path / 'job'
    shutil.copytree(job_entregue[0], job)

    def foto():
        return {p.relative_to(job).as_posix(): (p.is_file() and arquivos.sha256_arquivo(p), p.stat().st_mtime_ns)
                for p in job.rglob('*')}
    antes = foto()
    cod, env = _cli(sys.executable, 'conferir-entrega', '--job', str(job))
    assert cod == 0 and env['contagens']['conferem'] == 2, env
    assert foto() == antes
    arq = job / 'entrega' / 'aprovados' / 'mesma.jpg'
    arq.write_bytes(arq.read_bytes() + b'\0')
    meio = foto()
    cod, env = _cli(sys.executable, 'conferir-entrega', '--job', str(job))
    assert cod == int(Codigo.RECUSADO) and env['contagens']['divergem'] == 1, env
    assert foto() == meio


def test_relatorio_e_manifesto_do_job_entregue(job_entregue):
    """Bloco 4 (fatia 5): o relatorio do job de verdade nao tem numero sem fonte nem texto da peca, grava a build do
    encoder e a aprovacao de cada formato; o manifesto fica na raiz do job com o arquivo de fonte congelado; a saida do
    entregar termina com o resumo em portugues."""
    from desdobra.entrega import relatorio as mr
    job, r = job_entregue
    rel = contratos.ler(job / 'entrega' / 'relatorio-entrega.json', 'relatorio-entrega/1')
    assert mr.numeros_sem_fonte(rel) == []
    texto = json.dumps(rel, ensure_ascii=False)
    for proibido in ('ABCabc', 'AB ab', 'texto-cores', 'texto-apoio', 'fundo-sintetico', 'quadrado-sintetico'):
        assert proibido not in texto, proibido
    enc = rel['ambiente']['encoder']['versoes']
    assert enc['libjpeg_turbo'] and enc['zlib'] and enc['pillow']
    fontes = [s for k, s in ((k, v['sha256']) for k, v in nucleo.ler_estado(job)['entradas'].items())
              if k.startswith('entrada/fontes/')]
    assert rel['ambiente']['render']['fontes_sha256'] == sorted(set(fontes))
    aprov = contratos.ler(job / aprovacao.ARQUIVO, aprovacao.ESQUEMA)
    for a in rel['arquivos']:
        assert a['aprovacao']['registro_sha256'] == aprov['formatos'][a['formato']]['registro_sha256']
        assert a['aprovacao']['diferencas'] == [] and a['mudou_desde_a_entrega_anterior'] is None
        assert a['origem']['master_sha256'] == arquivos.sha256_arquivo(job / 'render' / a['formato'] / 'master.png')
    man = contratos.ler(job / 'manifesto-licenca.json', 'manifesto-licenca/1')
    assert [(m['nome'], m['sha256']) for m in man['arquivos']] == [('inventada.ttf', fontes[0])]
    assert man['arquivos'][0]['faces'] and man['conferencia_fontes_sha256']
    assert rel['manifesto_sha256'] == mr.selo_manifesto(man)
    assert not list((job / 'entrega').rglob('manifesto-licenca.json'))
    assert [l.split(':')[0] for l in r.linhas_humanas[-3:]] == ['Passou', 'Avisou', 'Só registro']
    assert r.contagens['so_registro'] >= 1 and 'avisos' in r.contagens


# ------------------------------------------------------------------ achados da revisao do M6
def _foto_da_entrega(job):
    raiz = job / 'entrega'
    fora = [job / 'manifesto-licenca.json', job / aprovacao.ARQUIVO, job / 'estado.json']
    return {p.relative_to(job).as_posix(): arquivos.sha256_arquivo(p)
            for p in list(raiz.rglob('*')) + fora if p.is_file()}


@pytest.fixture
def entregue(job_entregue, tmp_path):
    job = tmp_path / 'job'
    shutil.copytree(job_entregue[0], job)
    return job


def test_entregar_pede_sim_digitado_e_cancelado_nao_grava(entregue, pessoa, monkeypatch):
    perguntas = []

    def nao(pergunta):
        perguntas.append(pergunta)
        return 'nao'
    monkeypatch.setattr(humano, 'ler', nao)
    antes = _foto_da_entrega(entregue)
    r = entrega._entregar(Namespace(job=str(entregue)))
    assert r.codigo == int(Codigo.RECUSADO) and r.contagens == {'recusa_entrega_cancelada': 1}
    assert len(perguntas) == 1 and 'Digite sim' in perguntas[0]
    assert _foto_da_entrega(entregue) == antes


def test_entregar_recusa_quando_o_job_muda_durante_a_confirmacao(entregue, pessoa, monkeypatch):
    def responde_e_mexe(pergunta):
        _gravar_render(entregue, 'perto', lambda rel: rel.update(gerado_em='2026-11-04T12:00:00-03:00'))
        return 'sim'
    monkeypatch.setattr(humano, 'ler', responde_e_mexe)
    antes = {k: v for k, v in _foto_da_entrega(entregue).items()}
    r = entrega._entregar(Namespace(job=str(entregue)))
    assert r.codigo == int(Codigo.RECUSADO) and r.contagens == {'recusa_mudou_durante_a_confirmacao': 1}
    assert _foto_da_entrega(entregue) == antes


def test_entregar_com_arquivo_da_entrega_em_uso_recusa_sem_erro_interno(entregue, pessoa, monkeypatch):
    from desdobra.entrega import validar
    real = os.replace

    def em_uso(de, para):
        if Path(de).name == validar.APROVADOS and validar.PASTA_ANTERIORES in Path(para).parts:
            raise PermissionError('arquivo aberto')
        return real(de, para)
    monkeypatch.setattr(humano, 'ler', lambda pergunta: 'sim')
    monkeypatch.setattr(validar.os, 'replace', em_uso)
    antes = _foto_da_entrega(entregue)
    r = entrega._entregar(Namespace(job=str(entregue)))
    assert r.codigo == int(Codigo.RECUSADO) and r.contagens == {'recusa_entrega_em_uso': 1}, r.linhas_humanas
    assert 'feche' in r.o_que_fazer.casefold()
    assert _foto_da_entrega(entregue) == antes


def test_recusa_do_encoder_vai_para_reprovados_e_o_resto_e_entregue(entregue, pessoa, monkeypatch):
    # decisoes-v1.md, bloco de parametros do M6: master com transparencia vai para reprovados ate o DA definir a cor;
    # os outros formatos sao entregues
    real = codificar.arquivo_final

    def transparente(pasta, formato):
        if formato == 'perto':
            raise codificar.ErroCodificar('cor_de_achatamento_nao_definida', {'alfa_min': 0})
        return real(pasta, formato)
    monkeypatch.setattr(codificar, 'arquivo_final', transparente)
    monkeypatch.setattr(humano, 'ler', lambda pergunta: 'sim')
    # o aprovar recusa o formato (nao ha arquivo para aprovar)
    r = entrega._aprovar(Namespace(job=str(entregue), formato=['perto']))
    assert r.codigo == int(Codigo.RECUSADO) and r.contagens['recusa_cor_de_achatamento_nao_definida'] == 1
    r = entrega._entregar(Namespace(job=str(entregue)))
    assert r.codigo == 0, r.linhas_humanas
    assert (r.contagens['aprovados'], r.contagens['reprovados']) == (1, 1)
    assert r.contagens['reprova_cor_de_achatamento_nao_definida'] == 1
    raiz = entregue / 'entrega'
    assert [p.name for p in (raiz / 'aprovados').iterdir()] == ['mesma.jpg']
    assert not list((raiz / 'reprovados').iterdir())
    rel = contratos.ler(raiz / 'relatorio-entrega.json', 'relatorio-entrega/1')
    perto = next(a for a in rel['arquivos'] if a['formato'] == 'perto')
    assert perto['regras'] == ['cor_de_achatamento_nao_definida'] and perto['sugestoes'] and perto['sha256'] is None
    from desdobra.entrega import validar
    assert validar.conferir_entrega(entregue)['ok']


def test_trocar_entrada_guarda_a_entrega_em_anteriores(entregue, tmp_path):
    # a entrega invalidada por uma entrada nova vai inteira para entrega/anteriores/<carimbo>-invalidada/ (o relatorio,
    # aprovados, reprovados e o manifesto), nada e apagado; a previa e a aprovacao caem
    rel = contratos.ler(entregue / 'entrega' / 'relatorio-entrega.json', 'relatorio-entrega/1')
    antes = _foto_da_entrega(entregue)
    novo = tmp_path / 'folha.pdf'
    novo.write_bytes(b'%PDF-1.4 folha sintetica')
    nucleo.trocar_entrada(entregue, 'entrada/specs/folha.pdf', novo)
    raiz = entregue / 'entrega'
    assert sorted(p.name for p in raiz.iterdir()) == ['anteriores']
    guardada = raiz / 'anteriores' / ('%s-invalidada' % rel['carimbo'])
    for k in ('entrega/relatorio-entrega.json', 'entrega/aprovados/mesma.jpg', 'entrega/reprovados/perto.jpg'):
        assert arquivos.sha256_arquivo(guardada / k[len('entrega/'):]) == antes[k], k
    assert arquivos.sha256_arquivo(guardada / 'manifesto-licenca.json') == antes['manifesto-licenca.json']
    assert not (entregue / 'manifesto-licenca.json').exists() and not (entregue / aprovacao.ARQUIVO).exists()


def test_trocar_entrada_com_a_entrega_em_uso_nao_muda_a_entrada(entregue, tmp_path, monkeypatch):
    from desdobra.entrega import validar
    real = os.replace

    def em_uso(de, para):
        if Path(de).name == validar.APROVADOS:
            raise PermissionError('arquivo aberto')
        return real(de, para)
    monkeypatch.setattr(validar.os, 'replace', em_uso)
    antes = _foto_da_entrega(entregue)
    novo = tmp_path / 'folha.pdf'
    novo.write_bytes(b'%PDF-1.4 folha sintetica')
    with pytest.raises(nucleo.ErroJob) as e:
        nucleo.trocar_entrada(entregue, 'entrada/specs/folha.pdf', novo)
    assert 'feche' in e.value.o_que_fazer.casefold()
    assert not (entregue / 'entrada' / 'specs' / 'folha.pdf').exists()
    assert _foto_da_entrega(entregue) == antes
    assert all((entregue / 'render' / fid / 'master.png').is_file() for fid in IDS)
