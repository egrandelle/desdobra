# -*- coding: utf-8 -*-
"""Biblioteca da agencia (M7c, passo M1): opcao do plugin, conferencia da pasta, opcao global --biblioteca da CLI e
a pasta passada ao processo da tela, como o teto. Nenhum envelope leva o caminho nem a lista de marcas."""
import json
import sys
from pathlib import Path

import pytest

from conftest import RAIZ_PLUGIN
from desdobra import PASTA_PLUGIN
from desdobra.resultado import Codigo


# ------------------------------------------------------------------ plugin.json
def test_plugin_declara_a_biblioteca_como_pasta_opcional():
    manifesto = json.loads((RAIZ_PLUGIN / '.claude-plugin' / 'plugin.json').read_text(encoding='utf-8'))
    opcao = manifesto['userConfig']['biblioteca_agencia']
    assert opcao['type'] == 'directory'
    assert opcao.get('required', False) is False and 'default' not in opcao
    # chaves aceitas pela referencia do manifesto (objeto estrito)
    assert set(opcao) <= {'type', 'title', 'description', 'required', 'default', 'sensitive'}
    assert opcao['title'] and opcao['description']
    assert '—' not in opcao['description'] and '–' not in opcao['description']
    # o teto continua como estava
    assert manifesto['userConfig']['teto_modo_dados']['required'] is True


# ------------------------------------------------------------------ desdobra.biblioteca
def test_valor_vazio_ou_sem_substituicao_e_biblioteca_nao_configurada():
    from desdobra import biblioteca
    for valor in (None, '', '   ', '${user_config.biblioteca_agencia}', '"${user_config.biblioteca_agencia}"'):
        assert biblioteca.normalizar(valor) is None, valor
        assert biblioteca.conferir(valor).situacao == 'nao_configurada'


def test_pasta_boa_grava_e_nao_deixa_sobra(tmp_path):
    from desdobra import biblioteca
    pasta = tmp_path / 'biblioteca'
    pasta.mkdir()
    r = biblioteca.conferir(str(pasta), dados=tmp_path / 'dados')
    assert r.situacao == 'ok' and r.usavel and r.configurada
    assert list(pasta.iterdir()) == []  # a sonda de escrita apaga o que criou
    assert biblioteca.pasta_marcas(pasta) == pasta / 'marcas'


def test_pasta_ausente_ou_arquivo_ou_relativa(tmp_path):
    from desdobra import biblioteca
    assert biblioteca.conferir(str(tmp_path / 'nao-existe')).situacao == 'ausente'
    arquivo = tmp_path / 'arquivo.txt'
    arquivo.write_text('x', encoding='utf-8')
    assert biblioteca.conferir(str(arquivo)).situacao == 'ausente'
    assert biblioteca.conferir('pasta/relativa').situacao == 'ausente'


def test_pasta_sem_escrita(tmp_path, monkeypatch):
    from desdobra import biblioteca
    pasta = tmp_path / 'so-leitura'
    pasta.mkdir()

    def negar(*_a, **_k):
        raise PermissionError('negado')

    monkeypatch.setattr(biblioteca.tempfile, 'mkstemp', negar)
    r = biblioteca.conferir(str(pasta))
    assert r.situacao == 'sem_escrita' and not r.usavel


def test_pasta_dentro_do_plugin_ou_dos_dados_e_recusada(tmp_path):
    from desdobra import biblioteca
    assert biblioteca.conferir(str(PASTA_PLUGIN)).situacao == 'dentro_do_plugin'
    assert biblioteca.conferir(str(PASTA_PLUGIN / 'motor')).situacao == 'dentro_do_plugin'
    dados = tmp_path / 'dados'
    (dados / 'biblioteca').mkdir(parents=True)
    assert biblioteca.conferir(str(dados), dados=dados).situacao == 'dentro_dos_dados'
    assert biblioteca.conferir(str(dados / 'biblioteca'), dados=dados).situacao == 'dentro_dos_dados'
    # vizinha com o mesmo prefixo de nome nao e "dentro"
    (tmp_path / 'dados-irma').mkdir()
    assert biblioteca.conferir(str(tmp_path / 'dados-irma'), dados=dados).situacao == 'ok'


def test_para_tela_nunca_leva_caminho(tmp_path):
    from desdobra import biblioteca
    pasta = tmp_path / 'biblioteca-da-agencia'
    pasta.mkdir()
    for valor in (None, str(pasta), str(tmp_path / 'sumiu')):
        d = biblioteca.para_tela(biblioteca.conferir(valor))
        assert set(d) == {'configurada', 'usavel', 'situacao', 'o_que_fazer'}
        assert str(tmp_path) not in json.dumps(d, ensure_ascii=False)
        assert 'biblioteca-da-agencia' not in json.dumps(d, ensure_ascii=False)
    d = biblioteca.para_tela(biblioteca.conferir(None))
    assert d['usavel'] is False and '/plugin' in d['o_que_fazer'] and 'Configure' in d['o_que_fazer']


def test_textos_ao_da_sem_travessao():
    from desdobra import biblioteca
    for texto in list(biblioteca.O_QUE_FAZER.values()) + list(biblioteca.DETALHE.values()):
        assert '—' not in texto and '–' not in texto, texto
        # nenhum comando de terminal ao DA
        assert 'rode' not in texto.lower() and '"' not in texto and '--' not in texto, texto


# ------------------------------------------------------------------ CLI
def test_cli_aceita_biblioteca_global(tmp_path):
    from desdobra import cli
    args = cli.montar_analisador().parse_args(['--biblioteca', str(tmp_path), 'doctor', '--sem-isolador'])
    assert args.biblioteca == str(tmp_path)
    args = cli.montar_analisador().parse_args(['doctor'])
    assert args.biblioteca is None


def test_envelope_do_doctor_nao_traz_o_caminho_da_biblioteca(tmp_path, capsys, monkeypatch):
    from desdobra import cli, contratos
    monkeypatch.setattr(cli, 'COMPONENTES', (('desdobra.doctor', ('doctor',)),))
    pasta = tmp_path / 'biblioteca-secreta'
    codigo = cli.principal(['--envelope', '--teto-modo-dados', 'c', '--biblioteca', str(pasta), 'doctor',
                            '--sem-isolador', '--sem-chromium', '--saida', str(tmp_path / 'saida')])
    linha = capsys.readouterr().out.strip().splitlines()[-1]
    env = json.loads(linha)
    contratos.validar(env, 'envelope/1')
    assert 'biblioteca-secreta' not in linha and str(tmp_path) not in linha
    assert codigo == int(Codigo.RECUSADO)  # a pasta configurada nao existe: o doctor acusa
    relatorio = (tmp_path / 'saida' / 'doctor.json').read_text(encoding='utf-8')
    assert 'biblioteca-secreta' not in relatorio


# ------------------------------------------------------------------ tela abrir e processo de fundo
def test_comando_do_filho_leva_a_biblioteca_so_quando_ha(tmp_path):
    from desdobra import tela
    base = tela.comando_do_filho(tmp_path)
    assert '--biblioteca' not in base
    com = tela.comando_do_filho(tmp_path, teto='b', biblioteca=str(tmp_path / 'bib'))
    i = com.index('--biblioteca')
    assert com[i + 1] == str(tmp_path / 'bib') and com[com.index('--teto') + 1] == 'b'


def _job_vazio(pasta):
    from desdobra.job import nucleo
    pasta.mkdir(parents=True)
    (pasta / nucleo.ARQUIVO_ESTADO).write_text('{}', encoding='utf-8')
    return pasta


def test_tela_abrir_passa_a_biblioteca_ao_fundo_sem_por_no_envelope(tmp_path, monkeypatch, capsys):
    from desdobra import cli, tela
    job = _job_vazio(tmp_path / 'job')
    bib = tmp_path / 'biblioteca-da-agencia'
    bib.mkdir()
    pedidos = []

    class Saida:
        def close(self):
            pass

    class Proc:
        stdout = Saida()

    monkeypatch.setattr(tela, '_janela_presente', lambda: True)
    monkeypatch.setattr(tela, '_soltar', lambda argv: pedidos.append(argv) or Proc())
    monkeypatch.setattr(tela, '_ler_aviso', lambda proc, espera: 'pronto')
    codigo = cli.principal(['--envelope', '--teto-modo-dados', 'b', '--biblioteca', str(bib),
                            'tela', 'abrir', '--job', str(job)])
    linha = capsys.readouterr().out.strip().splitlines()[-1]
    assert codigo == 0
    argv = pedidos[0]
    assert argv[argv.index('--biblioteca') + 1] == str(bib) and argv[argv.index('--teto') + 1] == 'b'
    assert 'biblioteca-da-agencia' not in linha
    # sem a opcao, o filho nasce como antes (os testes que trocam comando_do_filho por lambda pasta: seguem valendo)
    pedidos.clear()
    monkeypatch.setattr(tela, 'comando_do_filho', lambda pasta: ['filho', str(pasta)])
    assert cli.principal(['--envelope', 'tela', 'abrir', '--job', str(job)]) == 0
    capsys.readouterr()
    assert pedidos == [['filho', str(job.resolve())]]


def test_processo_le_a_biblioteca_da_linha_de_comando(monkeypatch, tmp_path):
    from desdobra.tela import processo
    recebidos = []
    monkeypatch.setattr(processo, 'executar', lambda job, ao_abrir=None, teto=None, biblioteca=None:
                        recebidos.append((job, teto, biblioteca)) or 0)
    assert processo.principal(['--job', str(tmp_path), '--teto', 'a', '--biblioteca', str(tmp_path / 'b')]) == 0
    assert processo.principal(['--job', str(tmp_path)]) == 0
    assert recebidos == [(str(tmp_path), 'a', str(tmp_path / 'b')), (str(tmp_path), None, None)]


@pytest.mark.parametrize('configurada', [False, True])
def test_conteudo_da_tela_leva_a_situacao_da_biblioteca_sem_caminho(tmp_path, monkeypatch, configurada):
    from desdobra.chromium import navegador
    from desdobra.tela import estado, processo, tarefas
    job = tmp_path / 'job'
    job.mkdir()
    bib = tmp_path / 'biblioteca-da-agencia'
    bib.mkdir()
    conteudo = {'estado': {}, 'previas': {}, 'fontes': {}}
    monkeypatch.setattr(navegador, 'varrer_orfaos', lambda: {'removidas': 0, 'nao_removidas': 0})
    monkeypatch.setattr(tarefas, 'recuperar', lambda pasta: None)
    monkeypatch.setattr(estado, 'montar', lambda pasta, **k: conteudo)

    class Parar(Exception):
        pass

    def parar(pasta):
        raise Parar()

    monkeypatch.setattr(processo, 'opcoes_do_servidor', parar)
    avisos = []
    codigo = processo.executar(job, avisar=avisos.append, biblioteca=str(bib) if configurada else None)
    assert codigo == int(Codigo.ERRO_INTERNO) and avisos == ['recusado erro_interno']
    tela_bib = conteudo['biblioteca']
    assert tela_bib['configurada'] is configurada and tela_bib['usavel'] is configurada
    assert str(tmp_path) not in json.dumps(tela_bib, ensure_ascii=False)
    # o caminho fica so no processo de fundo, fora do que vai a pagina
    assert conteudo.get('pasta_biblioteca') == (Path(bib).resolve() if configurada else None)
    assert 'biblioteca' not in conteudo['estado']


# ------------------------------------------------------------------ revisao do M1
def _instalado(base, monkeypatch, versao='0.8.0'):
    """Layout sintetico do plugin instalado: <config>/plugins/cache/<mkt>/desdobra/<versao>."""
    from desdobra import biblioteca
    plugins = base / 'config' / 'plugins'
    atual = plugins / 'cache' / 'mkt' / 'desdobra' / versao
    atual.mkdir(parents=True)
    monkeypatch.setattr(biblioteca, 'PASTA_PLUGIN', atual)
    return plugins, atual


def test_outra_versao_e_o_cache_do_plugin_instalado_sao_recusados(tmp_path, monkeypatch):
    from desdobra import biblioteca
    plugins, atual = _instalado(tmp_path, monkeypatch)
    velha = atual.parent / '0.7.0'
    marketplace = plugins / 'marketplaces' / 'mkt'
    for pasta in (velha, marketplace):
        pasta.mkdir(parents=True)
    for pasta in (atual, velha, atual.parent, atual.parent.parent, plugins / 'cache', marketplace, plugins):
        assert biblioteca.conferir(str(pasta), dados=None).situacao == 'dentro_do_plugin', pasta
    # fora da pasta de plugins da configuracao, serve
    fora = tmp_path / 'config' / 'biblioteca'
    fora.mkdir()
    assert biblioteca.conferir(str(fora), dados=None).situacao == 'ok'
    vizinha = tmp_path / 'config' / 'plugins-irma'
    vizinha.mkdir()
    assert biblioteca.conferir(str(vizinha), dados=None).situacao == 'ok'


def test_pasta_de_versao_protege_as_outras_versoes(tmp_path, monkeypatch):
    from desdobra import biblioteca
    atual = tmp_path / 'cache' / 'mkt' / 'desdobra' / '0.8.0'
    velha = atual.parent / '0.7.0'
    atual.mkdir(parents=True)
    velha.mkdir()
    monkeypatch.setattr(biblioteca, 'PASTA_PLUGIN', atual)
    for pasta in (velha, atual.parent):
        assert biblioteca.conferir(str(pasta), dados=None).situacao == 'dentro_do_plugin', pasta


def test_plugin_fora_do_cache_protege_so_a_propria_pasta(tmp_path, monkeypatch):
    from desdobra import biblioteca
    plugin = tmp_path / 'repo' / 'plugins' / 'desdobra'
    plugin.mkdir(parents=True)
    irma = tmp_path / 'repo' / 'plugins' / 'outra'
    irma.mkdir()
    monkeypatch.setattr(biblioteca, 'PASTA_PLUGIN', plugin)
    assert biblioteca.conferir(str(plugin / 'x'), dados=None).situacao == 'dentro_do_plugin'
    assert biblioteca.conferir(str(irma), dados=None).situacao == 'ok'


@pytest.mark.skipif(sys.platform != 'win32', reason='prefixos de caminho do Windows')
def test_prefixo_estendido_e_compartilhamento_local_nao_escapam(tmp_path, monkeypatch):
    import os
    from desdobra import biblioteca
    plugin = tmp_path / 'plugin'
    (plugin / 'lib').mkdir(parents=True)
    monkeypatch.setattr(biblioteca, 'PASTA_PLUGIN', plugin)
    dados = tmp_path / 'dados'
    (dados / 'lib').mkdir(parents=True)
    b = chr(92)  # barra invertida
    estendido = b + b + '?' + b
    assert biblioteca.conferir(estendido + str(plugin / 'lib'), dados=None).situacao == 'dentro_do_plugin'
    assert biblioteca.conferir(estendido + str(plugin / 'nova'), dados=None).situacao == 'dentro_do_plugin'
    assert biblioteca.conferir(estendido + str(dados / 'lib'), dados=dados).situacao == 'dentro_dos_dados'
    local = b + b + '127.0.0.1' + b
    unc = local + str(plugin)[0] + '$' + str(plugin / 'lib')[2:]
    if not os.path.isdir(unc):
        pytest.skip('sem compartilhamento administrativo local')
    assert biblioteca.conferir(unc, dados=None).situacao == 'dentro_do_plugin'
    unc_dados = local + str(dados)[0] + '$' + str(dados / 'lib')[2:]
    assert biblioteca.conferir(unc_dados, dados=dados).situacao == 'dentro_dos_dados'


def test_pasta_real_com_cifrao_e_chave_no_nome_e_configurada(tmp_path):
    from desdobra import biblioteca
    pasta = tmp_path / 'lib${x}'
    pasta.mkdir()
    assert biblioteca.normalizar(str(pasta)) is not None
    assert biblioteca.conferir(str(pasta), dados=None).situacao == 'ok'
    # a substituicao que nao aconteceu continua valendo como nao configurada
    assert biblioteca.conferir('${user_config.biblioteca_agencia}').situacao == 'nao_configurada'
    assert biblioteca.conferir(' ${ user_config.biblioteca_agencia } ').situacao == 'nao_configurada'


def test_marcas_como_arquivo_ou_sem_escrita_nao_serve(tmp_path, monkeypatch):
    from desdobra import biblioteca
    arquivo = tmp_path / 'com-arquivo'
    arquivo.mkdir()
    (arquivo / 'marcas').write_bytes(b'')
    r = biblioteca.conferir(str(arquivo), dados=None)
    assert r.situacao == 'marcas_bloqueada' and not r.usavel and r.o_que_fazer
    assert str(tmp_path) not in r.detalhe + r.o_que_fazer

    trancada = tmp_path / 'com-pasta'
    (trancada / 'marcas').mkdir(parents=True)
    original = biblioteca.tempfile.mkstemp

    def negar_em_marcas(*a, **k):
        if Path(k.get('dir', '')).name == 'marcas':
            raise PermissionError('negado')
        return original(*a, **k)

    monkeypatch.setattr(biblioteca.tempfile, 'mkstemp', negar_em_marcas)
    assert biblioteca.conferir(str(trancada), dados=None).situacao == 'marcas_bloqueada'
    monkeypatch.setattr(biblioteca.tempfile, 'mkstemp', original)
    assert biblioteca.conferir(str(trancada), dados=None).situacao == 'ok'
    assert list((trancada / 'marcas').iterdir()) == []  # a sonda em marcas tambem apaga o que criou


def test_doctor_acusa_marcas_bloqueada(tmp_path):
    from desdobra.doctor import verificacoes as v
    pasta = tmp_path / 'biblioteca'
    pasta.mkdir()
    (pasta / 'marcas').write_bytes(b'')
    r = v.verificar_biblioteca(str(pasta), None)
    assert r.situacao == 'falha' and r.o_que_fazer and r.numeros == {'configurada': 1, 'usavel': 0}
