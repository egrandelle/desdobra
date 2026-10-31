# -*- coding: utf-8 -*-
"""CLI: subcomandos registrados pelos componentes, modo humano e envelope de saida."""
import json
import subprocess
import sys

from desdobra import cli, contratos
from desdobra.resultado import Codigo, Resultado


def rodar(*argumentos, cwd=None):
    proc = subprocess.run([sys.executable, '-I', '-B', '-m', 'desdobra', *argumentos], capture_output=True, cwd=cwd)
    return proc.returncode, proc.stdout.decode('utf-8'), proc.stderr.decode('utf-8')


def envelope_de(saida):
    linhas = saida.strip().splitlines()
    assert len(linhas) == 1, 'o envelope tem de ser uma linha so: %r' % saida
    dados = json.loads(linhas[0])
    contratos.validar(dados, 'envelope/1')
    return dados


def test_versao_e_ajuda():
    codigo, saida, _ = rodar('--version')
    assert codigo == 0 and saida.startswith('desdobra ')
    codigo, saida, _ = rodar('--help')
    assert codigo == 0
    for comando in ('job', 'ler', 'regressao', 'doctor', 'limites', 'fontes'):
        assert comando in saida


def test_job_criar_e_proxima_pela_cli(tmp_path, kv_psd):
    job = tmp_path / 'job'
    codigo, saida, _ = rodar('job', 'criar', str(job), '--psd', str(kv_psd), '--modo-dados', 'c')
    assert codigo == 0 and 'O QUE FAZER' in saida
    codigo, saida, _ = rodar('--envelope', 'job', 'estado', str(job))
    env = envelope_de(saida)
    assert env['modo_dados'] == 'c' and env['fase'] == 'ler' and codigo == 0
    assert len(env['ids']['job_id']) == 32


def test_envelope_nao_ecoa_argumentos_nem_traceback(tmp_path):
    marcador = 'NOME-DE-CLIENTE-NO-CAMINHO'
    codigo, saida, erro = rodar('--envelope', 'job', 'criar', str(tmp_path / marcador))
    env = envelope_de(saida)
    assert codigo == Codigo.USO and env['situacao'] == 'erro'
    assert marcador not in saida and marcador not in erro
    codigo, saida, erro = rodar('--envelope', 'job', 'estado', str(tmp_path / marcador))
    env = envelope_de(saida)
    assert env['codigo'] == Codigo.RECUSADO and marcador not in saida + erro
    codigo, saida, _ = rodar('--envelope', 'comando-que-nao-existe')
    assert envelope_de(saida)['codigo'] == Codigo.USO


def test_envelope_sem_job_e_modo_c_e_corta_conteudo(capsys, monkeypatch):
    def comando_falso(args):
        return Resultado(comando='teste', conteudo={'camadas': [{'layer_id': 1, 'nome': 'NOME-SECRETO'}]},
                         contagens={'camadas': 1})
    analisador_original = cli.montar_analisador

    def montar():
        p = analisador_original()
        sub = next(a for a in p._actions if a.dest == 'comando')
        sub.add_parser('teste').set_defaults(executar=comando_falso, nome_comando='teste')
        return p
    monkeypatch.setattr(cli, 'montar_analisador', montar)
    codigo = cli.principal(['--envelope', 'teste'])
    saida = capsys.readouterr().out
    env = envelope_de(saida)
    assert codigo == 0 and env['modo_dados'] == 'c' and 'conteudo' not in env
    assert 'NOME-SECRETO' not in saida


def test_teto_limita_o_modo_do_job(tmp_path, kv_psd):
    from desdobra.job import nucleo
    job = tmp_path / 'job'
    nucleo.criar(job, kv_psd, 'a')
    r = Resultado(comando='job estado', pasta_job=job)
    assert cli._modo_do_resultado(r, None) == 'a'
    assert cli._modo_do_resultado(r, 'b') == 'b'
    assert cli._modo_do_resultado(Resultado(comando='x'), 'a') == 'c'


def test_componente_ausente_vira_nao_disponivel(capsys, monkeypatch):
    monkeypatch.setattr(cli, 'COMPONENTES', cli.COMPONENTES + (('desdobra.componente_inexistente', ('fantasma',)),))
    codigo = cli.principal(['fantasma'])
    assert codigo == Codigo.NAO_DISPONIVEL
    assert 'não está disponível' in capsys.readouterr().out


def test_fase_ler_sem_o_leitor_falha_com_codigo_de_fase(tmp_path, kv_psd, monkeypatch):
    """Sem o modulo do leitor, "ler --job" responde 9 (e a fase do job, que exige codigo 0, falha)."""
    monkeypatch.setattr(cli, 'COMPONENTES', tuple(c for c in cli.COMPONENTES if c[0] != 'desdobra.leitor')
                        + (('desdobra.leitor_inexistente', ('ler',)),))
    assert cli.principal(['ler', '--job', str(tmp_path)]) == Codigo.NAO_DISPONIVEL


def test_job_criar_aceita_kv_e_teto_global(tmp_path, kv_psd):
    """--kv e sinonimo de --psd, e o --teto-modo-dados global (antes do subcomando) vale no job criar."""
    args = cli.montar_analisador().parse_args(['--teto-modo-dados', 'b', 'job', 'criar', 'p', '--kv', 'x.psd',
                                                '--modo-dados', 'b'])
    assert args.teto_modo_dados == 'b' and args.psd == 'x.psd'
    args = cli.montar_analisador().parse_args(['job', 'criar', 'p', '--psd', 'x.psd', '--modo-dados', 'c',
                                                '--teto-modo-dados', 'c'])
    assert args.teto_modo_dados == 'c'
    codigo, saida, _ = rodar('--envelope', '--teto-modo-dados', 'b', 'job', 'criar', str(tmp_path / 'j'),
                             '--kv', str(kv_psd), '--modo-dados', 'a')
    assert codigo == Codigo.RECUSADO and envelope_de(saida)['codigo'] == Codigo.RECUSADO
    codigo, saida, _ = rodar('--envelope', '--teto-modo-dados', 'b', 'job', 'criar', str(tmp_path / 'j'),
                             '--kv', str(kv_psd), '--modo-dados', 'b')
    assert codigo == 0
    estado = contratos.ler(tmp_path / 'j' / 'estado.json', 'estado/1')
    assert estado['teto_modo_dados'] == 'b'


def test_job_proxima_repassa_o_envelope_da_fase(tmp_path, kv_psd):
    """A fase roda com --envelope, e o job proxima repassa contagens, ids, numeros e conteudo dela."""
    from desdobra.job import nucleo
    job = tmp_path / 'job'
    nucleo.criar(job, kv_psd, 'b')
    linha = json.dumps({'esquema': 'envelope/1', 'modo_dados': 'b', 'comando': 'ler', 'fase': 'ler',
                        'situacao': 'ok', 'codigo': 0, 'o_que_fazer': None, 'contagens': {'camadas': 2},
                        'ids': {'arquivo_sha256': 'ab' * 32}, 'numeros': {'tempo_s': 1.5},
                        'conteudo': {'camadas': [{'layer_id': 1, 'nome': 'n', 'tipo': 'texto', 'situacao': 'lida',
                                                  'textos': ['t']}]}, 'segredos_bloqueados': 0})

    def executor(argv, pasta):
        assert '--envelope' in argv and argv.index('--envelope') < argv.index('ler')
        for saida in ('laudo/laudo.json', 'sugestoes/pacote-modelo.json'):
            (pasta / saida).parent.mkdir(parents=True, exist_ok=True)
            (pasta / saida).write_text('{}', encoding='utf-8')
        return 0, (linha + '\n').encode('utf-8'), b''
    r = nucleo.proxima(job, executor=executor)
    assert r.codigo == 0 and r.contagens['camadas'] == 2 and r.contagens['codigo_da_fase'] == 0
    assert r.ids['arquivo_sha256'] == 'ab' * 32 and r.ids['job_id']
    assert r.numeros['tempo_s'] == 1.5 and r.conteudo['camadas'][0]['layer_id'] == 1
    assert nucleo.envelope_da_saida(b'lixo\n{"esquema": "outro/1"}\n') is None


def test_modo_humano_mostra_aviso_de_segredo(capsys, monkeypatch):
    chave = 'AKIA' + 'B' * 16

    def comando_falso(args):
        return Resultado(comando='teste', conteudo={'camadas': [{'layer_id': 7, 'nome': chave, 'tipo': 'texto',
                                                                 'situacao': 'lida', 'textos': []}]})
    analisador_original = cli.montar_analisador

    def montar():
        p = analisador_original()
        sub = next(a for a in p._actions if a.dest == 'comando')
        sub.add_parser('teste').set_defaults(executar=comando_falso, nome_comando='teste')
        return p
    monkeypatch.setattr(cli, 'montar_analisador', montar)
    assert cli.principal(['teste']) == 0
    saida = capsys.readouterr().out
    assert chave not in saida and 'A camada 7' in saida


def test_limites_pela_cli():
    codigo, saida, _ = rodar('limites')
    assert codigo == 0 and 'prova_pixel.limiar_diferenca' in saida
