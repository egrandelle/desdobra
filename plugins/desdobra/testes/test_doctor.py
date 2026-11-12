# -*- coding: utf-8 -*-
"""desdobra doctor: verificacoes, doctor.json (doctor/1), envelope e o teste do isolador."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import PASTA_MOTOR, RAIZ_PLUGIN
from desdobra import chromium, contratos, limites, plataforma
from desdobra.doctor import verificacoes as v
from desdobra.plataforma import ResultadoFilho
from desdobra.resultado import Codigo

# Limites que o plugin pediu ao integrador (pendencia). Enquanto nao estiverem em motor/fontes-de-limites.json,
# os testes usam uma copia do registro com eles; depois de aplicados, a fixture nao muda nada.
LIMITES_PROPOSTOS = [
    {'id': 'ambiente.python_versoes_aceitas', 'valor': ['3.14'], 'unidade': 'versão maior.menor do CPython',
     'fonte': {'arquivo': 'pesquisa/wf_ec5e3b89-c45-resultado.json',
               'secao': 'A24, dependências do extra composite; ambiente da pesquisa com Python 3.14.2'},
     'situacao': 'medido', 'efeito': 'reprova',
     'nota': 'Só o 3.14 foi testado e o lock só tem hashes cp314. As rodas do 3.12 e do 3.13 existem no PyPI, mas '
             'entram só com hashes no lock e regressão nessa versão.'},
    {'id': 'ambiente.trava_preparo_max_s', 'valor': 600, 'unidade': 'segundos de idade da trava do preparo',
     'fonte': {'arquivo': 'arquitetura-v1.md', 'secao': '3.6'}, 'situacao': 'a_calibrar', 'efeito': 'registra',
     'nota': 'Trava mais velha que o timeout padrão do gancho (600 s, hooks.md) é de um preparo que morreu.'},
]


@pytest.fixture
def registro(tmp_path, monkeypatch):
    dados = json.loads(limites.ARQUIVO_REGISTRO.read_text(encoding='utf-8'))
    existentes = {x['id'] for x in dados['limites']}
    dados['limites'].extend(x for x in LIMITES_PROPOSTOS if x['id'] not in existentes)
    caminho = tmp_path / 'fontes-de-limites.json'
    caminho.write_text(json.dumps(dados, ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(limites, 'ARQUIVO_REGISTRO', caminho)
    limites.carregar.cache_clear()
    yield caminho
    limites.carregar.cache_clear()


class PlataformaFalsa(plataforma.Plataforma):
    nome = 'falsa'

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.pedidos = []

    def executar_isolado(self, comando, orcamento_bytes, tempo_s, pasta_trabalho, *, ambiente=None):
        assert Path(pasta_trabalho).is_dir() and not any(Path(pasta_trabalho).iterdir())
        self.pedidos.append((comando, orcamento_bytes, tempo_s))
        return self.respostas.pop(0)


def _filho(situacao, codigo, pico=None):
    return ResultadoFilho(situacao=situacao, codigo=codigo, pico_bytes=pico, stdout_bytes=b'', stderr_resumo='',
                          tempo_s=0.1, motivo=None if situacao == 'ok' else 'motivo fixo')


# ------------------------------------------------------------------ verificacoes isoladas
def test_lock_lido_e_bate_com_o_ambiente_de_desenvolvimento():
    fixadas = v.versoes_do_lock()
    assert fixadas['psd-tools'] == '1.26.0'
    assert {'aggdraw', 'scipy', 'numpy', 'pillow'} <= set(fixadas)
    r = v.verificar_lock(None)
    assert r.situacao in ('ok', 'aviso'), r.detalhe  # no venv de desenvolvimento ha pytest a mais
    assert r.numeros['pacotes_errados'] == 0


def test_lock_com_versao_diferente_falha(tmp_path):
    lock = tmp_path / 'requirements.lock'
    lock.write_text('psd-tools==0.0.1 \\\n    --hash=sha256:00\n', encoding='utf-8')
    r = v.verificar_lock(None, lock)
    assert r.situacao == 'falha' and 'psd-tools' in r.detalhe and r.o_que_fazer


def test_psd_tools_com_extra_composite():
    r = v.verificar_psd_tools()
    assert r.situacao == 'ok', r.detalhe
    assert 'aggdraw 1.4.1' in r.detalhe and 'scipy' in r.detalhe


def test_python_aceito_vem_do_registro(registro, monkeypatch):
    r = v.verificar_python()
    assert r.limite['limite_id'] == 'ambiente.python_versoes_aceitas'
    assert r.situacao == ('ok' if '%d.%d' % sys.version_info[:2] in r.limite['valor'] else 'falha')
    monkeypatch.setattr(sys, 'version_info', (3, 13, 0, 'final', 0))
    r = v.verificar_python()
    assert r.situacao == 'falha' and '3.14' in r.o_que_fazer


def test_teto_do_modo_de_dados():
    assert v.verificar_teto('b', None).situacao == 'ok'
    assert v.verificar_teto(None, None).situacao == 'aviso'
    assert v.verificar_teto(None, Path('.')).situacao == 'falha'


def test_ambiente_do_plugin_confere_interpretador(tmp_path):
    dados = tmp_path / 'dados'
    dados.mkdir()
    (dados / 'interpretador.json').write_text(json.dumps({
        'esquema': 'interpretador/1', 'python': sys.executable, 'plugin_root': str(RAIZ_PLUGIN)}), encoding='utf-8')
    (dados / 'preparo.json').write_text(json.dumps({'situacao': 'ok', 'acao': 'recriar', 'tempo_s': 81.5}),
                                        encoding='utf-8')
    r = v.verificar_ambiente(dados)
    assert r.situacao == 'ok' and r.numeros['preparo_tempo_s'] == 81.5
    (dados / 'interpretador.json').write_text(json.dumps({
        'python': sys.executable, 'plugin_root': str(tmp_path / 'outra-versao')}), encoding='utf-8')
    r = v.verificar_ambiente(dados)
    assert r.situacao == 'falha' and 'outra versão' in r.detalhe
    assert v.verificar_ambiente(None).situacao == 'aviso'


# ------------------------------------------------------------------ isolador (com plataforma falsa)
def test_isolador_passa_quando_um_cabe_e_o_outro_estoura(registro):
    plat = PlataformaFalsa([_filho('ok', 0, 9_000_000), _filho('memoria', 4, 100_000_000)])
    feitas, sem_suporte = v.verificar_isolador(plat)
    assert [x.situacao for x in feitas] == ['ok', 'ok'] and not sem_suporte
    teto = limites.valor('isolador.base_python_bytes')
    (cmd1, teto1, _t1), (cmd2, teto2, _t2) = plat.pedidos
    assert teto1 == teto2 == teto
    assert cmd1[1:4] == ['-I', '-B', '-c'] and cmd2[-1] == str(teto + teto)


def test_isolador_que_nao_segura_o_teto_falha(registro):
    plat = PlataformaFalsa([_filho('ok', 0), _filho('ok', 0)])
    feitas, _ = v.verificar_isolador(plat)
    assert feitas[1].situacao == 'falha' and 'Não leia PSD' in feitas[1].o_que_fazer


def test_isolador_recusado_vira_sem_suporte(registro):
    plat = PlataformaFalsa([_filho('recusado', None)])
    feitas, sem_suporte = v.verificar_isolador(plat)
    assert sem_suporte and feitas[0].situacao == 'falha' and feitas[1].situacao == 'pulado'
    assert len(plat.pedidos) == 1


def test_mac_sem_suporte_da_codigo_9(registro, monkeypatch, tmp_path):
    from desdobra import doctor
    mac = plataforma.obter('darwin')
    monkeypatch.setattr(plataforma, 'obter', lambda sistema=None: mac)
    monkeypatch.setattr(v, 'verificar_lock', lambda dados: v.Verificacao('versoes_do_lock', 'x'))
    monkeypatch.setattr(v, 'verificar_python', lambda: v.Verificacao('python', 'x'))
    args = type('A', (), {'teto_modo_dados': 'c', 'saida': str(tmp_path), 'sem_isolador': False})()
    r = doctor.executar(args)
    assert r.codigo == Codigo.NAO_DISPONIVEL and r.situacao == 'nao_disponivel'
    assert 'Windows' in r.o_que_fazer
    relatorio = contratos.ler(tmp_path / 'doctor.json', 'doctor/1')
    assert relatorio['plataforma']['isolador'] == 'mac'


# ------------------------------------------------------------------ comando inteiro
def test_doctor_grava_relatorio_valido(registro, tmp_path):
    from desdobra import doctor
    args = type('A', (), {'teto_modo_dados': 'b', 'saida': str(tmp_path / 'saida'), 'sem_isolador': True})()
    r = doctor.executar(args)
    relatorio = contratos.ler(tmp_path / 'saida' / 'doctor.json', 'doctor/1')
    assert relatorio['codigo'] == r.codigo and relatorio['teto_modo_dados'] == 'b'
    ids = [x['id'] for x in relatorio['verificacoes']]
    assert ids[:4] == ['python', 'ambiente_do_plugin', 'versoes_do_lock', 'psd_tools_composite']
    assert r.contagens['verificacoes'] == len(ids)


def test_o_que_fazer_do_doctor_nunca_leva_caminho(registro, tmp_path, monkeypatch):
    from desdobra import doctor
    falha = v.Verificacao('versoes_do_lock', 'x', situacao='falha', detalhe=str(tmp_path), o_que_fazer='Texto fixo.')
    monkeypatch.setattr(v, 'verificar_lock', lambda dados: falha)
    args = type('A', (), {'teto_modo_dados': 'c', 'saida': None, 'sem_isolador': True})()
    r = doctor.executar(args)
    assert r.codigo == Codigo.RECUSADO and r.situacao == 'bloqueado'
    assert str(tmp_path) not in r.o_que_fazer and r.o_que_fazer == 'Texto fixo.'


def test_doctor_pela_cli_com_envelope(registro, tmp_path, capsys, monkeypatch):
    """O envelope sai numa linha, valida contra envelope/1 e nunca traz conteudo (doctor nao tem job: modo c).

    So o componente do doctor entra no analisador, para o teste nao depender dos outros componentes."""
    from desdobra import cli
    monkeypatch.setattr(cli, 'COMPONENTES', (('desdobra.doctor', ('doctor',)),))
    codigo = cli.principal(['--envelope', '--teto-modo-dados', 'b', 'doctor', '--sem-isolador',
                            '--saida', str(tmp_path)])
    linhas = capsys.readouterr().out.strip().splitlines()
    assert len(linhas) == 1
    env = json.loads(linhas[0])
    contratos.validar(env, 'envelope/1')
    assert env['comando'] == 'doctor' and env['modo_dados'] == 'c' and 'conteudo' not in env
    assert env['codigo'] == codigo and env['contagens']['verificacoes'] >= 1
    assert str(tmp_path) not in linhas[0]


def test_doctor_pelo_processo_do_motor(tmp_path):
    """python -I -B -m desdobra doctor responde pelo analisador inteiro (como as skills chamam)."""
    proc = subprocess.run([sys.executable, '-I', '-B', '-m', 'desdobra', '--envelope', 'doctor', '--sem-isolador',
                           '--saida', str(tmp_path)], capture_output=True)
    env = json.loads(proc.stdout.decode('utf-8').strip().splitlines()[-1])
    contratos.validar(env, 'envelope/1')
    if env['comando'] != 'doctor':
        pytest.skip('outro componente do motor ainda nao carrega neste build (%s)' % env['o_que_fazer'])
    assert env['codigo'] == proc.returncode


# ------------------------------------------------------------------ isolador de verdade (so no Windows)
@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador do M1 existe so no Windows')
def test_isolador_de_verdade_no_windows(registro):
    plat = plataforma.obter()
    if plat.nome != 'windows':
        pytest.skip('a implementacao de plataforma do Windows ainda nao esta neste build')
    feitas, sem_suporte = v.verificar_isolador(plat)
    assert not sem_suporte
    assert feitas[0].situacao == 'ok', feitas[0].detalhe
    assert feitas[1].situacao == 'ok', feitas[1].detalhe
    assert feitas[1].numeros['pico_bytes'] <= feitas[1].numeros['teto_bytes']


def test_esquema_doctor_esta_na_pasta_de_esquemas():
    assert (PASTA_MOTOR / 'schemas' / 'doctor-1.json').is_file()
    assert 'doctor/1' in contratos.listar_esquemas()


# ------------------------------------------------------------------ correcoes da revisao do M2
def test_motor_aponta_o_playwright_para_a_pasta_de_dados_do_plugin(tmp_path, monkeypatch):
    dados = tmp_path / 'data'
    (dados / 'venv').mkdir(parents=True)
    (dados / 'interpretador.json').write_text('{}', encoding='utf-8')
    # setenv antes do delenv: o monkeypatch guarda o valor de antes e o restaura no fim, mesmo que o motor grave
    monkeypatch.setenv(chromium.VARIAVEL_NAVEGADORES, 'x')
    monkeypatch.delenv(chromium.VARIAVEL_NAVEGADORES)
    monkeypatch.setattr(sys, 'prefix', str(dados / 'venv'))
    assert chromium.pasta_navegadores() == dados / 'ms-playwright'
    chromium.apontar_playwright()
    assert os.environ[chromium.VARIAVEL_NAVEGADORES] == str(dados / 'ms-playwright')


def test_doctor_confere_versao_do_fonttools_e_do_playwright(tmp_path):
    from desdobra.doctor import chromium as vc
    for nome in ('fonttools', 'playwright'):
        assert vc.verificar_versao(nome, nome, nome).situacao == 'ok'
    lock = tmp_path / 'requirements.lock'
    lock.write_text('fonttools==0.0.1 \\\n    --hash=sha256:aa\n', encoding='utf-8')
    v = vc.verificar_versao('fonttools', 'fonttools', 'fonttools', lock)
    assert v.situacao == 'falha' and v.o_que_fazer
    assert vc.verificar_versao('playwright', 'playwright', 'playwright', lock).situacao == 'falha'


@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador do filho roda no Windows')
def test_doctor_acha_o_chromium_fixado_e_falha_sem_ele(tmp_path):
    from desdobra.doctor import chromium as vc
    revisao, _versao = chromium.revisao_fixada()
    assert revisao is not None
    padrao = chromium.pasta_padrao_do_playwright()
    if chromium.executavel_fixado(padrao, revisao) is None:
        pytest.skip('o headless shell fixado nao esta na pasta padrao do Playwright desta maquina')
    assert vc.verificar_chromium(padrao).situacao == 'ok'
    v = vc.verificar_chromium(tmp_path / 'vazia')
    assert v.situacao == 'falha' and v.o_que_fazer == vc.O_QUE_FAZER_CHROMIUM and str(tmp_path) not in v.o_que_fazer


@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador do filho roda no Windows')
def test_doctor_carrega_fonte_sintetica_pelo_font_face_e_confere_por_cdp():
    from desdobra.doctor import chromium as vc
    padrao = chromium.pasta_navegadores() or chromium.pasta_padrao_do_playwright()
    if chromium.executavel_fixado(padrao, chromium.revisao_fixada()[0]) is None:
        pytest.skip('o headless shell fixado nao esta instalado nesta maquina')
    v = vc.verificar_fonte_no_chromium()
    assert v.situacao == 'ok', v.detalhe
    assert v.numeros == {'carregada': 1, 'cdp_confere': 1, 'copias_no_cache': 0}


def test_doctor_lista_as_verificacoes_do_m2(monkeypatch):
    from desdobra import doctor
    lista, _sem = doctor.rodar_verificacoes('c', None, com_isolador=False, com_chromium=False)
    ids = [x.id for x in lista]
    assert {'fonttools', 'playwright', 'chromium_fixado', 'fonte_no_chromium'} <= set(ids)
    assert next(x for x in lista if x.id == 'fonte_no_chromium').situacao == 'pulado'


# ------------------------------------------------------------------ biblioteca da agencia (M7c, M1)
def test_doctor_biblioteca_nao_configurada_passa_e_diz_onde_configurar():
    r = v.verificar_biblioteca(None, None)
    assert r.id == 'biblioteca_agencia' and r.situacao == 'ok'
    assert '/plugin' in r.detalhe and 'Configure' in r.detalhe


def test_doctor_biblioteca_boa(tmp_path):
    pasta = tmp_path / 'biblioteca'
    pasta.mkdir()
    r = v.verificar_biblioteca(str(pasta), tmp_path / 'dados')
    assert r.situacao == 'ok' and str(tmp_path) not in r.detalhe and r.o_que_fazer is None


@pytest.mark.parametrize('caso', ['ausente', 'sem_escrita', 'dentro_do_plugin', 'dentro_dos_dados'])
def test_doctor_acusa_biblioteca_configurada_com_problema(tmp_path, monkeypatch, caso):
    from desdobra import PASTA_PLUGIN, biblioteca
    dados = tmp_path / 'dados'
    dados.mkdir()
    pasta = {'ausente': tmp_path / 'sumiu', 'sem_escrita': tmp_path / 'trancada', 'dentro_do_plugin': PASTA_PLUGIN,
             'dentro_dos_dados': dados / 'biblioteca'}[caso]
    if caso in ('sem_escrita', 'dentro_dos_dados'):
        pasta.mkdir()
    if caso == 'sem_escrita':
        def negar(*_a, **_k):
            raise PermissionError('negado')
        monkeypatch.setattr(biblioteca.tempfile, 'mkstemp', negar)
    r = v.verificar_biblioteca(str(pasta), dados)
    assert r.situacao == 'falha' and r.o_que_fazer
    assert r.numeros == {'configurada': 1, 'usavel': 0}
    for texto in (r.detalhe, r.o_que_fazer):
        assert str(pasta) not in texto and str(tmp_path) not in texto and str(PASTA_PLUGIN) not in texto
        assert '—' not in texto and '–' not in texto


def test_doctor_roda_a_verificacao_da_biblioteca(tmp_path):
    from desdobra import doctor
    lista, _sem = doctor.rodar_verificacoes('c', None, com_isolador=False, com_chromium=False,
                                            biblioteca=str(tmp_path / 'sumiu'))
    bib = next(x for x in lista if x.id == 'biblioteca_agencia')
    assert bib.situacao == 'falha'
    lista, _sem = doctor.rodar_verificacoes('c', None, com_isolador=False, com_chromium=False)
    assert next(x for x in lista if x.id == 'biblioteca_agencia').situacao == 'ok'
