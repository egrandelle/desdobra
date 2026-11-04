# -*- coding: utf-8 -*-
"""Aprovacao por formato, gancho e invalidacao (M6, fatias 1 e 2 da proposta; decisoes-v1.md, 138, 139 e 142).

Criterios de pronto cobertos aqui (arquitetura-v1.md, 9.7):
  - a aprovacao anterior cai quando o hash do master muda, e a diferenca diz o campo, por formato: cada mutacao de
    briefing, master, render.json, contrato, arquivo final e parametros do encoder derruba a aprovacao em 100% dos
    casos, com o campo nomeado; registro mexido a mao e registro de outro job tambem caem;
  - o aprovar e o entregar so partem do DA: os comandos humanos do gancho PreToolUse sao os de desdobra.humano, o gancho
    nega os dois e a escrita em entrega/, na aprovacao, no manifesto e nos parametros de entrega; sem console, os dois
    recusam e nao gravam;
  - rotacao (nº 139): sem decisao recusa; 90 e 270 graus exigem o sentido confirmado; 0 e 180 nao pedem sentido;
  - invalidar_render derruba a aprovacao e o que esta em entrega/ (as entregas anteriores ficam);
  - risco da secao 6 da proposta: gravar briefing/aprovacao.json nao deixa o briefing desatualizado nem invalida fase.

Todo material e sintetico (sem PSD, sem render): os testes com render estao em test_entrega_job.py.
"""
import importlib.util
import json
from argparse import Namespace
from pathlib import Path

import pytest

from conftest import RAIZ_PLUGIN
from desdobra import arquivos, cli, contratos, humano
from desdobra.briefing import modelo as mb
from desdobra.entrega import aprovacao, codificar, portao
from desdobra.job import fases as mod_fases
from desdobra.job import nucleo
from desdobra.resultado import Codigo

JOB = 'a' * 32


def _gancho():
    spec = importlib.util.spec_from_file_location('gancho_confirmacoes', RAIZ_PLUGIN / 'scripts' / 'gancho_confirmacoes.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Disparo:
    def registro(self):
        return {'meio': 'terminal', 'usuario': 'teste', 'maquina': 'teste', 'quando': '2026-11-04T10:00:00-03:00'}


def _do_aprovar():
    """Um Disparo de verdade do "aprovar" (so a conferencia do console fica simulada, como no fixture pessoa): o
    registro de aprovacao confere o disparo."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(humano, 'console_interativo', lambda: (True, None))
        return humano.exigir('aprovar')


def _atual(**troca):
    a = {'briefing_sha256': '1' * 64, 'master_sha256': '2' * 64, 'render_json_sha256': '3' * 64,
         'contrato_sha256': '4' * 64}
    a.update(troca)
    return a


def _final(dados=b'arquivo-final-sintetico', **parametros):
    p = {'tipo': 'jpg', 'qualidade': 90, 'subamostragem': '4:4:4', 'progressivo': False}
    p.update(parametros)
    return codificar.ArquivoFinal(dados=dados, extensao='jpg', parametros=p)


# ------------------------------------------------------------------ gancho e comandos humanos
def test_comandos_do_gancho_sao_os_do_motor():
    g = _gancho()
    assert set(g.SUBCOMANDOS_HUMANOS) == set(humano.COMANDOS)
    assert {'aprovar', 'entregar'} <= set(humano.COMANDOS)


def test_gancho_nega_aprovar_entregar_e_a_escrita_na_entrega():
    g = _gancho()

    def decidir(ferramenta, entrada):
        return g.decidir({'tool_name': ferramenta, 'tool_input': entrada}) or 'segue'
    negar = ['python -m desdobra aprovar --job j --formato a', 'desdobra entregar --job "C:/j"',
             '"C:/x/python.exe" -I -B -m desdobra --envelope aprovar --job j --formato a',
             'desdobra.exe entregar --job j', 'echo x > C:/j/entrega/aprovados/a.jpg',
             'cp a.jpg C:/j/entrega/reprovados/a.jpg', 'echo {} > C:/j/briefing/aprovacao.json',
             'echo {} > C:/j/manifesto-licenca.json', 'echo {} > C:/j/parametros/entrega.json']
    for c in negar:
        assert decidir('Bash', {'command': c}) == 'deny', c
        assert decidir('PowerShell', {'command': c}) == 'deny', c
    for c in ['python -m desdobra conferir-entrega --job j', 'python -m desdobra derivar --job j',
              'cat C:/j/briefing/aprovacao.json', 'ls C:/j/entrega/aprovados']:
        assert decidir('Bash', {'command': c}) == 'segue', c
    for arq in ('C:/j/entrega/aprovados/a.jpg', 'C:/j/entrega/previa/a.png', 'C:/j/briefing/aprovacao.json',
                'C:/j/manifesto-licenca.json', 'C:/j/relatorio-entrega.json', 'C:/j/parametros/entrega.json'):
        assert decidir('Write', {'file_path': arq}) == 'deny', arq
    # o codigo-fonte do pacote desdobra/entrega/ e os testes continuam editaveis
    for arq in ('C:/repo/plugins/desdobra/motor/desdobra/entrega/portao.py',
                'C:/repo/plugins/desdobra/testes/test_entrega_aprovacao.py'):
        assert decidir('Edit', {'file_path': arq}) == 'segue', arq


def test_gancho_nega_os_desvios_de_aspas_escape_caminho_e_codigo_da_entrega():
    # achados da revisao do M6: subcomando entre aspas ou com escape, caminho com ./ e .., nome com .py/.md dentro de
    # entrega/ de um job e o codigo do motor que grava a aprovacao ou a entrega sem passar pelo comando
    g = _gancho()

    def decidir(ferramenta, entrada):
        return g.decidir({'tool_name': ferramenta, 'tool_input': entrada}) or 'segue'
    negar = ['desdobra "entregar" --job C:/j', "desdobra 'aprovar' --job j --formato a",
             'python -m desdobra.cli "aprovar" --job j --formato a', 'desdobra ent^regar --job C:\\job',
             'desdobra ent`regar --job C:/j', "$c='entre'+'gar'; desdobra $c --job C:/j",
             'tee C:/j/entrega/aprovados/{mesma.jpg,x.py} < y.jpg',
             'Set-Content -Path C:/j/entrega/aprovados/mesma.jpg,C:/t/x.py -Value y',
             'cp y.jpg C:/j/entrega/aprovados/mesma.md', 'cp y.json C:/j/entrega/previa/kv.py.jpg',
             'echo > C:/j/entrega/aprovados/x.md', 'cp a C:/j/entrega/aprovados/a.py.jpg',
             'cp a C:/j/parametros/./entrega.json', 'cp a C:/j/entrega/x/../aprovados/kv.jpg',
             'cp a C:\\j\\briefing\\.\\aprovacao.json',
             'python -c "from desdobra.entrega import aprovacao as a, portao as p; from desdobra import contratos as c; '
             'c.gravar(x, a.registro(1, 2, 3, 4, D), a.ESQUEMA)"',
             'python -c "import desdobra.entrega.validar as v; v.gravar(j, i, k, disparo=d)"',
             'python -c "from desdobra import entrega; entrega._entregar(n)"']
    for c in negar:
        assert decidir('Bash', {'command': c}) == 'deny', c
        assert decidir('PowerShell', {'command': c}) == 'deny', c
    for arq in ('C:/j/parametros/./entrega.json', 'C:/j/entrega/x.py/../aprovados/kv.jpg', 'C:/j/briefing/./aprovacao.json',
                'C:/j/briefing//aprovacao.json', 'C:/j/entrega/aprovados/x.md', 'C:\\j\\entrega\\aprovados\\x.py',
                'C:/j/entrega/previa/kv.py.jpg'):
        assert decidir('Write', {'file_path': arq}) == 'deny', arq
    # o codigo-fonte do pacote continua editavel, e ler a entrega e rodar os testes seguem
    for arq in ('C:/repo/plugins/desdobra/motor/desdobra/entrega/validar.py',
                'C:\\repo\\plugins\\desdobra\\motor\\desdobra\\entrega\\__init__.py'):
        assert decidir('Edit', {'file_path': arq}) == 'segue', arq
    for c in ['cat C:/j/entrega/relatorio-entrega.json', 'python -m desdobra conferir-entrega --job "C:/j"',
              'python -m pytest plugins/desdobra/testes/test_entrega_job.py -q',
              'git diff plugins/desdobra/motor/desdobra/entrega/validar.py',
              "sed -i 's/a/b/' plugins/desdobra/motor/desdobra/entrega/validar.py"]:
        assert decidir('Bash', {'command': c}) == 'segue', c


def test_aprovar_e_entregar_sem_console_recusam_e_nao_gravam(tmp_path, monkeypatch):
    monkeypatch.setattr(humano, 'console_interativo', lambda: (False, 'sem_terminal'))
    (tmp_path / 'estado.json').write_text('{}', encoding='utf-8')
    assert cli.principal(['aprovar', '--job', str(tmp_path), '--formato', 'a']) == int(Codigo.RECUSADO)
    assert cli.principal(['entregar', '--job', str(tmp_path)]) == int(Codigo.RECUSADO)
    assert sorted(p.name for p in tmp_path.rglob('*')) == ['estado.json']


def test_o_encoder_nao_inventa_arquivo_sem_job(tmp_path):
    with pytest.raises(codificar.ErroCodificar) as e:
        codificar.arquivo_final(tmp_path, 'a')
    assert e.value.codigo == 'formato_inexistente'


# ------------------------------------------------------------------ queda da aprovacao
def test_registro_vale_e_segue_o_contrato():
    reg = aprovacao.registro('perto', JOB, _atual(), _final(), _do_aprovar())
    contratos.validar({'esquema': 'aprovacao/1', 'job_id': JOB, 'formatos': {'perto': reg}}, 'aprovacao/1')
    assert aprovacao.diferencas(reg, JOB, _atual(), _final()) == []
    assert reg['arquivo_entregue']['sha256'] == arquivos.sha256_bytes(b'arquivo-final-sintetico')


MUTACOES = [
    ('briefing', {'atual': _atual(briefing_sha256='9' * 64)}, ['briefing_sha256']),
    ('master', {'atual': _atual(master_sha256='9' * 64)}, ['master_sha256']),
    ('render_json', {'atual': _atual(render_json_sha256='9' * 64)}, ['render_json_sha256']),
    ('contrato', {'atual': _atual(contrato_sha256='9' * 64)}, ['contrato_sha256']),
    ('arquivo_final', {'final': _final(dados=b'outro-arquivo')}, ['arquivo_entregue_sha256']),
    ('qualidade', {'final': _final(qualidade=80)}, ['parametros_encoder.qualidade']),
    ('subamostragem', {'final': _final(subamostragem='4:2:0')}, ['parametros_encoder.subamostragem']),
    ('parametro_novo', {'final': _final(borda='preta')}, ['parametros_encoder.borda']),
    ('outro_job', {'job_id': 'b' * 32}, ['job_id']),
]


@pytest.mark.parametrize('nome, troca, campos', MUTACOES, ids=[m[0] for m in MUTACOES])
def test_cada_mudanca_derruba_a_aprovacao_e_nomeia_o_campo(nome, troca, campos):
    reg = aprovacao.registro('perto', JOB, _atual(), _final(), _do_aprovar())
    dif = aprovacao.diferencas(reg, troca.get('job_id', JOB), troca.get('atual', _atual()), troca.get('final', _final()))
    assert dif == campos


def test_mutacoes_detectadas_em_100_por_cento():
    reg = aprovacao.registro('perto', JOB, _atual(), _final(), _do_aprovar())
    detectadas = sum(1 for _n, t, _c in MUTACOES
                     if aprovacao.diferencas(reg, t.get('job_id', JOB), t.get('atual', _atual()), t.get('final', _final())))
    assert detectadas == len(MUTACOES)


def test_registro_so_sai_com_o_disparo_do_aprovar(pessoa):
    # a API do motor nao cunha registro sem o DA: um objeto qualquer com registro() ou o disparo de outro comando recusa
    for d in (_Disparo(), pessoa.exigir('render'), pessoa.exigir('entregar')):
        with pytest.raises(humano.ErroHumano):
            aprovacao.registro('perto', JOB, _atual(), _final(), d)
    disparo = pessoa.exigir('aprovar')
    aprovacao.registro('perto', JOB, _atual(), _final(), disparo)
    humano.conferir(disparo, 'aprovar')  # o registro nao consome o disparo: o gravar consome


def test_registro_mexido_a_mao_cai():
    reg = aprovacao.registro('perto', JOB, _atual(), _final(), _do_aprovar())
    mexido = json.loads(json.dumps(reg))
    mexido['parametros_encoder']['qualidade'] = 80
    assert aprovacao.diferencas(mexido, JOB, _atual(), _final()) == ['registro_sha256', 'parametros_encoder.qualidade']
    # mexido de forma coerente com o estado de agora: o selo ainda pega
    mexido = json.loads(json.dumps(reg))
    mexido['master_sha256'] = '9' * 64
    assert aprovacao.diferencas(mexido, JOB, _atual(master_sha256='9' * 64), _final()) == ['registro_sha256']


def test_gravar_so_com_o_disparo_do_aprovar_e_um_registro_por_formato(tmp_path, pessoa):
    reg_a = aprovacao.registro('a', JOB, _atual(), _final(), _do_aprovar())
    reg_b = aprovacao.registro('b', JOB, _atual(), _final(), _do_aprovar())
    with pytest.raises(humano.ErroHumano):
        aprovacao.gravar(tmp_path, [reg_a], JOB, disparo=_Disparo())
    with pytest.raises(humano.ErroHumano):
        aprovacao.gravar(tmp_path, [reg_a], JOB, disparo=pessoa.exigir('render'))
    assert not (tmp_path / aprovacao.ARQUIVO).exists()
    disparo = pessoa.exigir('aprovar')
    aprovacao.gravar(tmp_path, [reg_a], JOB, disparo=disparo)
    with pytest.raises(humano.ErroHumano):  # o disparo serve uma vez
        aprovacao.gravar(tmp_path, [reg_b], JOB, disparo=disparo)
    aprovacao.gravar(tmp_path, [reg_b], JOB, disparo=pessoa.exigir('aprovar'))
    assert sorted(aprovacao.ler(tmp_path)['formatos']) == ['a', 'b']
    # de outro job, os registros velhos saem
    reg_c = aprovacao.registro('c', 'b' * 32, _atual(), _final(), _do_aprovar())
    aprovacao.gravar(tmp_path, [reg_c], 'b' * 32, disparo=pessoa.exigir('aprovar'))
    assert sorted(aprovacao.ler(tmp_path)['formatos']) == ['c']


def test_aprovacao_ausente_de_outro_job_ou_invalida_recusa():
    f = portao._conferir_aprovacao
    assert [x['codigo'] for x in f(None, None, 'a', JOB, _atual(), None)] == ['sem_aprovacao']
    aprov = {'job_id': 'b' * 32, 'formatos': {'a': aprovacao.registro('a', 'b' * 32, _atual(), _final(), _do_aprovar())}}
    assert [x['codigo'] for x in f(aprov, None, 'a', JOB, _atual(), None)] == ['aprovacao_de_outro_job']
    assert [x['codigo'] for x in f(aprov, None, 'outro', JOB, _atual(), None)] == ['sem_aprovacao']
    erro = portao._falha('aprovacao_invalida')
    assert f(None, erro, 'a', JOB, _atual(), None) == [erro]


# ------------------------------------------------------------------ rotacao (nº 139)
def _sentido(valor):
    return {'rotacao_sentido': {'valor': valor, 'confirmado_por': _Disparo().registro()}}


@pytest.mark.parametrize('rotacao, parametros, codigos', [
    (None, None, ['rotacao_nao_decidida']),
    ({'graus': 0, 'sentido': None}, None, []),
    ({'graus': 180, 'sentido': None}, None, []),
    ({'graus': 90, 'sentido': None}, None, ['rotacao_sem_sentido_confirmado']),
    ({'graus': 270, 'sentido': 'horario'}, None, ['rotacao_sem_sentido_confirmado']),
    ({'graus': 90, 'sentido': None}, _sentido('anti_horario'), []),
    ({'graus': 270, 'sentido': 'horario'}, _sentido('horario'), []),
    ({'graus': 90, 'sentido': 'horario'}, _sentido('anti_horario'), ['rotacao_sentido_divergente']),
])
def test_rotacao_na_entrega(rotacao, parametros, codigos):
    formato = {'id': 'a', 'chave': 'k', 'largura': 10, 'altura': 20, 'rotacao': rotacao}
    assert [f['codigo'] for f in portao.conferir_rotacao(formato, parametros)] == codigos


def test_parametros_de_entrega_seguem_o_contrato(tmp_path):
    assert portao.parametros_de_entrega(tmp_path) == {}
    dados = {'esquema': 'parametros-entrega/1', 'formatos': {'a': _sentido('horario')}}
    contratos.gravar(tmp_path / portao.ARQUIVO_PARAMETROS, dados, portao.ESQUEMA_PARAMETROS)
    assert portao.parametros_de_entrega(tmp_path)['a']['rotacao_sentido']['valor'] == 'horario'


# ------------------------------------------------------------------ invalidacao
def _render_e_entrega(pasta):
    for f in ('a', 'b'):
        (pasta / 'render' / f).mkdir(parents=True)
        (pasta / 'render' / f / 'master.png').write_bytes(b'master')
        (pasta / 'render' / f / 'render.json').write_text('{}', encoding='utf-8')
    (pasta / 'briefing').mkdir()
    (pasta / aprovacao.ARQUIVO).write_text('{}', encoding='utf-8')
    for rel in ('entrega/aprovados/a.jpg', 'entrega/reprovados/b.jpg', 'entrega/previa/a.png',
                'entrega/anteriores/2026-11-01/a.jpg'):
        (pasta / rel).parent.mkdir(parents=True, exist_ok=True)
        (pasta / rel).write_bytes(b'x')


def test_invalidar_render_derruba_a_aprovacao_e_a_entrega(tmp_path):
    _render_e_entrega(tmp_path)
    arquivos.tornar_somente_leitura(tmp_path / 'entrega' / 'aprovados' / 'a.jpg')
    assert nucleo.invalidar_render(tmp_path) == 2
    assert not (tmp_path / aprovacao.ARQUIVO).exists()
    assert sorted(p.name for p in (tmp_path / 'entrega').iterdir()) == ['anteriores']
    assert (tmp_path / 'entrega' / 'anteriores' / '2026-11-01' / 'a.jpg').is_file()


def test_invalidar_render_guarda_a_entrega_em_anteriores_sem_apagar(tmp_path):
    # achado da revisao do M6: a entrega invalidada nao e apagada; o relatorio, aprovados, reprovados e o manifesto vao
    # para entrega/anteriores/<carimbo>-invalidada/
    _render_e_entrega(tmp_path)
    carimbo = '20261104T100000-0300'
    (tmp_path / 'entrega' / 'relatorio-entrega.json').write_text(json.dumps({'carimbo': carimbo}), encoding='utf-8')
    (tmp_path / 'manifesto-licenca.json').write_text('{}', encoding='utf-8')
    nucleo.invalidar_render(tmp_path)
    guardada = tmp_path / 'entrega' / 'anteriores' / ('%s-invalidada' % carimbo)
    assert sorted(p.relative_to(guardada).as_posix() for p in guardada.rglob('*') if p.is_file()) == [
        'aprovados/a.jpg', 'manifesto-licenca.json', 'relatorio-entrega.json', 'reprovados/b.jpg']
    assert not (tmp_path / 'manifesto-licenca.json').exists() and not (tmp_path / aprovacao.PASTA_PREVIA).exists()
    assert not (tmp_path / aprovacao.ARQUIVO).exists()


def test_invalidar_render_sem_render_tambem_derruba_a_aprovacao(tmp_path):
    (tmp_path / 'briefing').mkdir()
    (tmp_path / aprovacao.ARQUIVO).write_text('{}', encoding='utf-8')
    assert nucleo.invalidar_render(tmp_path) == 0
    assert not (tmp_path / aprovacao.ARQUIVO).exists()


# ------------------------------------------------------------------ risco da secao 6: briefing/aprovacao.json
def test_gravar_a_aprovacao_nao_desatualiza_o_briefing_nem_invalida_fase(tmp_path):
    for rel, texto in ((mb.ARQUIVO_LAUDO, '{"l": 1}'), (mb.ARQUIVO_DS, '{"d": 1}'), (mb.ARQUIVO_CONFERENCIA, '{"c": 1}'),
                       (mb.ARQUIVO_RASCUNHO_SPECS, '{"s": 1}'), (mb.ARQUIVO, '{"b": 1}')):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(texto, encoding='utf-8')
    por_id = {f.id: f for f in mod_fases.ESTEIRA}
    antes = mb.hashes_atuais(tmp_path)
    briefing_antes = arquivos.sha256_arquivo(tmp_path / mb.ARQUIVO)
    fases_antes = {f.id: nucleo.hashes_da_fase(tmp_path, f, por_id) for f in mod_fases.ESTEIRA}
    (tmp_path / aprovacao.ARQUIVO).write_text('{"esquema": "aprovacao/1"}', encoding='utf-8')
    assert mb.hashes_atuais(tmp_path) == antes
    assert arquivos.sha256_arquivo(tmp_path / mb.ARQUIVO) == briefing_antes
    assert {f.id: nucleo.hashes_da_fase(tmp_path, f, por_id) for f in mod_fases.ESTEIRA} == fases_antes
    assert not any(p.startswith('briefing') for f in mod_fases.ESTEIRA for p in nucleo.padroes_da_fase(f, por_id))


def test_handler_aprovar_recusa_formato_que_o_briefing_nao_tem(tmp_path, pessoa, monkeypatch):
    from desdobra import entrega
    (tmp_path / 'estado.json').write_text(json.dumps({'job_id': JOB}), encoding='utf-8')
    monkeypatch.setattr(portao, 'conferir', lambda pasta, formatos, **k: {
        'briefing': None, 'formatos': {f: {'falhas': [portao._falha('formato_inexistente')], 'atual': {}, 'final': None}
                                       for f in formatos}})
    r = entrega._aprovar(Namespace(job=str(tmp_path), formato=['sumiu']))
    assert r.codigo == int(Codigo.RECUSADO) and r.contagens['recusa_formato_inexistente'] == 1
    assert not (tmp_path / aprovacao.ARQUIVO).exists()
    assert not (Path(tmp_path) / aprovacao.PASTA_PREVIA).exists()
