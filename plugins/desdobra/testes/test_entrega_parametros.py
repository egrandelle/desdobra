# -*- coding: utf-8 -*-
"""desdobra parametros-entrega: o DA grava parametros/entrega.json pelo terminal (M6; decisoes-v1.md, 137 e 139 e o
bloco de parametros do M6: cor de achatamento e borda de 1 px so quando o DA declara).

Criterios cobertos aqui:
  - so parte do DA, como o aprovar: sem console ou com --envelope recusa e nao grava; o gancho PreToolUse nega o
    comando pelo Claude e continua negando a escrita do arquivo;
  - mostra o antes e o depois de cada campo e pede o sim digitado; cancelado, nada e gravado;
  - grava segundo o contrato parametros-entrega/1, com confirmado_por do Disparo (meio terminal);
  - sentido do giro so nos formatos de 90 e 270 graus; condicao so entre as da folha confirmada, quando a folha diz;
    cor #rrggbb normalizada em minusculas; --limpar tira um campo;
  - gravar o arquivo nao desatualiza o briefing nem invalida fase, e derruba a aprovacao do formato quando o parametro
    entra no encoder (giro, achatamento e borda).

Todo material e sintetico (briefing simulado, master gerado na hora).
"""
import importlib.util
import io
import json

import pytest
from PIL import Image

from conftest import RAIZ_PLUGIN
from desdobra import arquivos, cli, contratos, humano
from desdobra.briefing import modelo as mb
from desdobra.entrega import aprovacao, codificar, portao
from desdobra.job import fases as mod_fases
from desdobra.job import nucleo
from desdobra.resultado import Codigo

JOB = 'a' * 32
FORMATOS = [
    {'id': 'giro', 'chave': 'teste|giro', 'largura': 20, 'altura': 10, 'rotacao': {'graus': 90, 'sentido': None}},
    {'id': 'reto', 'chave': 'teste|reto', 'largura': 20, 'altura': 10, 'rotacao': {'graus': 0, 'sentido': None}},
    {'id': 'meia', 'chave': 'teste|meia', 'largura': 20, 'altura': 10, 'rotacao': {'graus': 180, 'sentido': None}},
    {'id': 'sem-rot', 'chave': 'teste|sem-rot', 'largura': 20, 'altura': 10, 'rotacao': None},
]


def _gancho():
    spec = importlib.util.spec_from_file_location('gancho_confirmacoes', RAIZ_PLUGIN / 'scripts' / 'gancho_confirmacoes.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def job(tmp_path, monkeypatch):
    pasta = tmp_path / 'job'
    pasta.mkdir()
    (pasta / 'estado.json').write_text(json.dumps({'job_id': JOB}), encoding='utf-8')
    monkeypatch.setattr(mb, 'ler', lambda p: {'formatos': [dict(f) for f in FORMATOS]})
    return pasta


def _rodar(monkeypatch, *argv, resposta='sim'):
    perguntas = []

    def ler(pergunta):
        perguntas.append(pergunta)
        return resposta
    monkeypatch.setattr(humano, 'ler', ler)
    args = cli.montar_analisador().parse_args(['parametros-entrega', *argv])
    return args.executar(args), perguntas


def _gravado(pasta):
    return contratos.ler(pasta / portao.ARQUIVO_PARAMETROS, portao.ESQUEMA_PARAMETROS)


def _specs(pasta, campos_por_chave):
    arquivos.gravar_json_atomico(pasta / mb.ARQUIVO_FORMATOS, {
        'tipo': 'formatos_do_job', 'formatos': [{'id': c, 'chave': c, 'campos': campos}
                                               for c, campos in campos_por_chave.items()]})


# ------------------------------------------------------------------ so o DA
def test_comandos_do_gancho_sao_os_do_motor_com_o_parametros_entrega():
    g = _gancho()
    assert 'parametros-entrega' in humano.COMANDOS
    assert set(g.SUBCOMANDOS_HUMANOS) == set(humano.COMANDOS)


def test_sem_console_recusa_e_nao_grava(job, monkeypatch):
    monkeypatch.setattr(humano, 'console_interativo', lambda: (False, 'sem_terminal'))
    r, perguntas = _rodar(monkeypatch, '--job', str(job), '--formato', 'giro', '--rotacao-sentido', 'horario')
    assert r.codigo == int(Codigo.RECUSADO) and r.contagens == {'recusa_sem_terminal': 1}
    assert perguntas == [] and not (job / portao.ARQUIVO_PARAMETROS).exists()


def test_com_envelope_recusa_e_nao_grava(job, monkeypatch):
    monkeypatch.setattr(cli._Analisador, 'modo_envelope', False)
    monkeypatch.setattr(humano, '_console_do_sistema', lambda: (True, None))
    monkeypatch.setattr(humano, 'ler', lambda pergunta: 'sim')
    cod = cli.principal(['--envelope', 'parametros-entrega', '--job', str(job), '--formato', 'giro',
                         '--rotacao-sentido', 'horario'])
    assert cod == int(Codigo.RECUSADO)
    assert not (job / portao.ARQUIVO_PARAMETROS).exists()


def test_gancho_nega_o_comando_pelo_claude_e_a_escrita_do_arquivo():
    g = _gancho()

    def decidir(ferramenta, entrada):
        return g.decidir({'tool_name': ferramenta, 'tool_input': entrada}) or 'segue'
    negar = ['desdobra parametros-entrega --job C:/j --formato a --rotacao-sentido horario',
             'python -m desdobra parametros-entrega --job "C:/j" --formato a --condicao hospedado',
             '"C:/x/python.exe" -I -B -m desdobra --envelope parametros-entrega --job j --formato a --borda-1px sim',
             'desdobra "parametros-entrega" --job j --formato a --limpar condicao',
             'desdobra parametros-entre^ga --job j --formato a --cor-de-achatamento #ffffff',
             'python -c "from desdobra.entrega import parametros as p; p.gravar(j, f, v, disparo=d)"',
             'python -c "import desdobra.entrega.parametros as p; p.gravar(j, f, v, disparo=d)"',
             'python -c "from desdobra import entrega; entrega._parametros_entrega(n)"',
             'echo {} > C:/j/parametros/entrega.json']
    for c in negar:
        assert decidir('Bash', {'command': c}) == 'deny', c
        assert decidir('PowerShell', {'command': c}) == 'deny', c
    for arq in ('C:/j/parametros/entrega.json', 'C:\\j\\parametros\\entrega.json', 'C:/j/parametros/./entrega.json'):
        assert decidir('Write', {'file_path': arq}) == 'deny', arq
    # o codigo-fonte do modulo novo e o teste continuam editaveis; ler o arquivo segue
    for arq in ('C:/repo/plugins/desdobra/motor/desdobra/entrega/parametros.py',
                'C:/repo/plugins/desdobra/testes/test_entrega_parametros.py'):
        assert decidir('Edit', {'file_path': arq}) == 'segue', arq
    for c in ['cat C:/j/parametros/entrega.json', 'python -m desdobra conferir-entrega --job j',
              'python -m pytest plugins/desdobra/testes/test_entrega_parametros.py -q']:
        assert decidir('Bash', {'command': c}) == 'segue', c


def test_sugestoes_dizem_que_a_decisao_e_do_da_sem_comando():
    # M7c, ajuste terminal: o parametros-entrega ainda nao tem botao na tela (M8); as sugestoes dizem que a decisao e
    # do DA e que o botao chega no proximo marco, sem comando de terminal (humano.O_QUE_FAZER_SEM_BOTAO)
    from desdobra.entrega import validar
    textos = [validar.SUGESTOES['condicao_nao_decidida'], validar.SUGESTOES['cor_de_achatamento_nao_definida'],
              validar.SUGESTOES['borda_sem_valor_confirmado'], portao.DESCRICOES['rotacao_sem_sentido_confirmado']]
    for t in textos:
        assert 'parametros-entrega' not in t and 'terminal' not in t and '--' not in t, t
        assert 'DA' in t and 'próximo marco' in t, t
    # as opcoes do comando (que fica para os testes e a Trezion) continuam existindo
    ajuda = cli.montar_analisador()._subparsers._group_actions[0].choices['parametros-entrega'].format_help()
    for opcao in ('--condicao', '--cor-de-achatamento', '--rotacao-sentido', '--limpar', '--borda-1px'):
        assert opcao in ajuda


def test_documentacao_diz_os_nomes_que_o_limpar_aceita():
    escolhas = cli.montar_analisador()._subparsers._group_actions[0].choices['parametros-entrega']._option_string_actions[
        '--limpar'].choices
    raiz = RAIZ_PLUGIN.parent.parent
    # M7c K1: a skill novo-job nao manda mais o DA ao terminal, e a entrega e do M8; os parametros saem dela
    assert 'parametros-entrega' not in (RAIZ_PLUGIN / 'skills' / 'novo-job' / 'SKILL.md').read_text(encoding='utf-8')
    for doc in (raiz / 'README.md', raiz / 'docs' / 'm1-interfaces.md'):
        texto = doc.read_text(encoding='utf-8')
        for nome in escolhas:
            assert nome in texto, (doc.name, nome)
        assert '`--limpar` aceita' in texto or 'com hífen' in texto, doc.name
    # os codigos de recusa documentados sao os que o motor emite
    from desdobra.entrega import parametros
    interfaces = (raiz / 'docs' / 'm1-interfaces.md').read_text(encoding='utf-8')
    for codigo in list(parametros.DESCRICOES) + ['gravacao_cancelada', 'mudou_durante_a_confirmacao']:
        assert '`%s`' % codigo in interfaces, codigo
    assert 'mudou_desde_a_confirmacao' not in interfaces


# ------------------------------------------------------------------ pergunta e gravacao
def test_cancelado_nao_grava(job, pessoa, monkeypatch):
    r, perguntas = _rodar(monkeypatch, '--job', str(job), '--formato', 'giro', '--rotacao-sentido', 'horario',
                          resposta='nao')
    assert r.codigo == int(Codigo.RECUSADO) and r.contagens == {'recusa_gravacao_cancelada': 1}
    assert len(perguntas) == 1 and 'Digite sim para gravar' in perguntas[0]
    assert not (job / portao.ARQUIVO_PARAMETROS).exists()


def test_mostra_antes_e_depois_e_grava_segundo_o_contrato(job, pessoa, monkeypatch, capsys):
    r, perguntas = _rodar(monkeypatch, '--job', str(job), '--formato', 'giro', '--rotacao-sentido', 'horario')
    assert r.codigo == 0 and r.situacao == 'ok', r.linhas_humanas
    assert len(perguntas) == 1
    saida = capsys.readouterr().out
    assert 'rotacao_sentido' in saida and '(nada)' in saida and 'horario' in saida
    dados = _gravado(job)
    reg = dados['formatos']['giro']['rotacao_sentido']
    assert reg['valor'] == 'horario'
    assert reg['confirmado_por']['meio'] == 'terminal' and reg['confirmado_por']['quando']
    # a origem do Disparo vai junto (M7b, B4): a do modo de teste da tela o portao da entrega recusa
    assert set(reg['confirmado_por']) == {'usuario', 'maquina', 'meio', 'quando', 'origem'}
    assert reg['confirmado_por']['origem'] == 'da'
    # o portao e o encoder leem o que foi gravado
    assert portao.parametros_de_entrega(job)['giro']['rotacao_sentido']['valor'] == 'horario'
    assert portao.conferir_rotacao(FORMATOS[0], portao.parametros_de_entrega(job)['giro']) == []


@pytest.mark.parametrize('argv, campo, valor', [
    (['--formato', 'giro', '--rotacao-sentido', 'anti_horario'], 'rotacao_sentido', 'anti_horario'),
    (['--formato', 'reto', '--condicao', 'por_tag'], 'condicao', 'por_tag'),
    (['--formato', 'reto', '--cor-de-achatamento', '#A0B1C2'], 'cor_de_achatamento', '#a0b1c2'),
    (['--formato', 'reto', '--borda-1px', 'sim'], 'borda_1px', True),
    (['--formato', 'reto', '--borda-1px', 'nao'], 'borda_1px', False),
])
def test_cada_campo_vai_e_volta(job, pessoa, monkeypatch, argv, campo, valor):
    r, _p = _rodar(monkeypatch, '--job', str(job), *argv)
    assert r.codigo == 0, r.linhas_humanas
    fid = argv[1]
    assert _gravado(job)['formatos'][fid][campo]['valor'] == valor
    # limpar o campo tira o registro e o formato que fica vazio
    r, _p = _rodar(monkeypatch, '--job', str(job), '--formato', fid, '--limpar', campo.replace('_', '-'))
    assert r.codigo == 0, r.linhas_humanas
    assert fid not in _gravado(job)['formatos']


def test_limpar_tira_so_o_campo_pedido(job, pessoa, monkeypatch):
    r, _p = _rodar(monkeypatch, '--job', str(job), '--formato', 'giro', '--rotacao-sentido', 'horario',
                   '--condicao', 'hospedado', '--cor-de-achatamento', '#FFFFFF')
    assert r.codigo == 0, r.linhas_humanas
    assert sorted(_gravado(job)['formatos']['giro']) == ['condicao', 'cor_de_achatamento', 'rotacao_sentido']
    r, _p = _rodar(monkeypatch, '--job', str(job), '--formato', 'giro', '--limpar', 'condicao')
    assert r.codigo == 0, r.linhas_humanas
    assert sorted(_gravado(job)['formatos']['giro']) == ['cor_de_achatamento', 'rotacao_sentido']


def test_outros_formatos_ficam(job, pessoa, monkeypatch):
    _rodar(monkeypatch, '--job', str(job), '--formato', 'giro', '--rotacao-sentido', 'horario')
    _rodar(monkeypatch, '--job', str(job), '--formato', 'reto', '--condicao', 'hospedado')
    assert sorted(_gravado(job)['formatos']) == ['giro', 'reto']


# ------------------------------------------------------------------ recusas
@pytest.mark.parametrize('fid, codigo', [('reto', 'rotacao_sem_quarto_de_volta'), ('meia', 'rotacao_sem_quarto_de_volta'),
                                         ('sem-rot', 'rotacao_nao_decidida')])
def test_sentido_do_giro_so_em_90_e_270_graus(job, pessoa, monkeypatch, fid, codigo):
    r, perguntas = _rodar(monkeypatch, '--job', str(job), '--formato', fid, '--rotacao-sentido', 'horario')
    assert r.codigo == int(Codigo.RECUSADO) and r.contagens == {'recusa_%s' % codigo: 1}
    assert perguntas == [] and not (job / portao.ARQUIVO_PARAMETROS).exists()


def test_sentido_diferente_do_briefing_recusa(job, pessoa, monkeypatch):
    # o briefing ja diz o sentido: gravar o outro faria o portao recusar o formato (rotacao_sentido_divergente)
    com_sentido = {'id': 'giro-h', 'chave': 'teste|giro-h', 'largura': 20, 'altura': 10,
                   'rotacao': {'graus': 270, 'sentido': 'horario'}}
    monkeypatch.setattr(mb, 'ler', lambda p: {'formatos': [dict(f) for f in FORMATOS] + [dict(com_sentido)]})
    r, perguntas = _rodar(monkeypatch, '--job', str(job), '--formato', 'giro-h', '--rotacao-sentido', 'anti_horario')
    assert r.codigo == int(Codigo.RECUSADO) and r.contagens == {'recusa_rotacao_sentido_divergente': 1}
    assert perguntas == [] and not (job / portao.ARQUIVO_PARAMETROS).exists()
    r, _p = _rodar(monkeypatch, '--job', str(job), '--formato', 'giro-h', '--rotacao-sentido', 'horario')
    assert r.codigo == 0, r.linhas_humanas
    assert portao.conferir_rotacao(com_sentido, portao.parametros_de_entrega(job)['giro-h']) == []


def test_formato_que_o_briefing_nao_tem_recusa(job, pessoa, monkeypatch):
    r, perguntas = _rodar(monkeypatch, '--job', str(job), '--formato', 'sumiu', '--condicao', 'hospedado')
    assert r.codigo == int(Codigo.RECUSADO) and r.contagens == {'recusa_formato_inexistente': 1}
    assert perguntas == [] and not (job / portao.ARQUIVO_PARAMETROS).exists()


def test_sem_briefing_recusa(job, pessoa, monkeypatch):
    monkeypatch.setattr(mb, 'ler', lambda p: None)
    r, _p = _rodar(monkeypatch, '--job', str(job), '--formato', 'giro', '--rotacao-sentido', 'horario')
    assert r.codigo == int(Codigo.RECUSADO) and r.contagens == {'recusa_sem_briefing': 1}
    assert not (job / portao.ARQUIVO_PARAMETROS).exists()


def test_condicao_so_entre_as_da_folha_quando_a_folha_diz(job, pessoa, monkeypatch):
    _specs(job, {'teste|reto': {'peso_max_hospedado': {'valor': {'alvo_bytes': 250000}, 'condicao': 'hospedado',
                                                       'situacao': 'confirmado'},
                                'peso_max_tag': {'valor': {'alvo_bytes': 500000}, 'condicao': 'por_tag',
                                                 'situacao': 'confirmado'}}})
    r, perguntas = _rodar(monkeypatch, '--job', str(job), '--formato', 'reto', '--condicao', 'tag_carga_inicial')
    assert r.codigo == int(Codigo.RECUSADO) and r.contagens == {'recusa_condicao_fora_da_folha': 1}
    assert perguntas == [] and not (job / portao.ARQUIVO_PARAMETROS).exists()
    r, _p = _rodar(monkeypatch, '--job', str(job), '--formato', 'reto', '--condicao', 'por_tag')
    assert r.codigo == 0 and _gravado(job)['formatos']['reto']['condicao']['valor'] == 'por_tag'
    # sem a folha do formato, a condicao e aceita e registrada
    r, _p = _rodar(monkeypatch, '--job', str(job), '--formato', 'giro', '--condicao', 'tag_carga_posterior')
    assert r.codigo == 0 and _gravado(job)['formatos']['giro']['condicao']['valor'] == 'tag_carga_posterior'


def test_condicao_sem_teto_com_valor_nao_conta_como_da_folha(job, pessoa, monkeypatch):
    # o mesmo filtro do encoder (codificar.teto_estrito): teto confirmado sem valor nao e condicao da folha
    _specs(job, {'teste|reto': {'peso_max_hospedado': {'valor': None, 'condicao': 'hospedado',
                                                       'situacao': 'confirmado'},
                                'peso_max_tag': {'valor': {'alvo_bytes': 500000}, 'condicao': 'por_tag',
                                                 'situacao': 'confirmado'}}})
    with pytest.raises(codificar.ErroCodificar):
        codificar.teto_estrito(codificar.spec_confirmada(job, 'teste|reto'), 'hospedado')
    r, perguntas = _rodar(monkeypatch, '--job', str(job), '--formato', 'reto', '--condicao', 'hospedado')
    assert r.codigo == int(Codigo.RECUSADO) and r.contagens == {'recusa_condicao_fora_da_folha': 1}
    assert perguntas == [] and not (job / portao.ARQUIVO_PARAMETROS).exists()


@pytest.mark.parametrize('cor', ['ffffff', '#fff', '#gggggg', '#ffffff0', 'branco'])
def test_cor_fora_do_padrao_recusa(job, pessoa, monkeypatch, cor):
    r, perguntas = _rodar(monkeypatch, '--job', str(job), '--formato', 'reto', '--cor-de-achatamento', cor)
    assert r.codigo == int(Codigo.RECUSADO) and r.contagens == {'recusa_cor_invalida': 1}
    assert perguntas == [] and not (job / portao.ARQUIVO_PARAMETROS).exists()


def test_sem_mudanca_pedida_e_erro_de_uso(job, pessoa, monkeypatch):
    r, perguntas = _rodar(monkeypatch, '--job', str(job), '--formato', 'giro')
    assert r.codigo == int(Codigo.USO) and perguntas == []
    r, perguntas = _rodar(monkeypatch, '--job', str(job), '--formato', 'giro', '--condicao', 'hospedado',
                          '--limpar', 'condicao')
    assert r.codigo == int(Codigo.USO) and perguntas == []
    assert not (job / portao.ARQUIVO_PARAMETROS).exists()


def test_valor_igual_ao_gravado_nao_pergunta_nem_grava(job, pessoa, monkeypatch):
    _rodar(monkeypatch, '--job', str(job), '--formato', 'giro', '--rotacao-sentido', 'horario')
    antes = (job / portao.ARQUIVO_PARAMETROS).read_bytes()
    r, perguntas = _rodar(monkeypatch, '--job', str(job), '--formato', 'giro', '--rotacao-sentido', 'horario')
    assert r.codigo == 0 and perguntas == [] and r.contagens == {'campos_mudados': 0}
    assert (job / portao.ARQUIVO_PARAMETROS).read_bytes() == antes


def test_arquivo_fora_do_contrato_recusa_sem_gravar_por_cima(job, pessoa, monkeypatch):
    arq = job / portao.ARQUIVO_PARAMETROS
    arq.parent.mkdir(parents=True)
    arq.write_text('{"esquema": "parametros-entrega/1", "formatos": {"giro": {"x": 1}}}', encoding='utf-8')
    r, perguntas = _rodar(monkeypatch, '--job', str(job), '--formato', 'giro', '--rotacao-sentido', 'horario')
    assert r.codigo == int(Codigo.RECUSADO) and r.contagens == {'recusa_parametros_de_entrega_invalidos': 1}
    assert perguntas == [] and json.loads(arq.read_text(encoding='utf-8'))['formatos'] == {'giro': {'x': 1}}


def test_recusa_quando_o_arquivo_muda_durante_a_confirmacao(job, pessoa, monkeypatch):
    from desdobra.entrega import parametros

    def responde_e_mexe(pergunta):
        dados = {'esquema': portao.ESQUEMA_PARAMETROS, 'formatos': {'giro': {'rotacao_sentido': {
            'valor': 'anti_horario', 'confirmado_por': {'meio': 'terminal', 'quando': '2026-11-04T10:00:00-03:00'}}}}}
        contratos.gravar(job / portao.ARQUIVO_PARAMETROS, dados, portao.ESQUEMA_PARAMETROS)
        return 'sim'
    monkeypatch.setattr(humano, 'ler', responde_e_mexe)
    args = cli.montar_analisador().parse_args(['parametros-entrega', '--job', str(job), '--formato', 'giro',
                                               '--rotacao-sentido', 'horario'])
    r = args.executar(args)
    assert r.codigo == int(Codigo.RECUSADO) and r.contagens == {'recusa_mudou_durante_a_confirmacao': 1}
    assert parametros.ler(job)['formatos']['giro']['rotacao_sentido']['valor'] == 'anti_horario'


def test_job_ocupado_recusa_antes_da_pergunta(job, pessoa, monkeypatch):
    (job / nucleo.ARQUIVO_TRAVA).write_text('1', encoding='utf-8')
    r, perguntas = _rodar(monkeypatch, '--job', str(job), '--formato', 'giro', '--rotacao-sentido', 'horario')
    assert r.codigo == int(Codigo.OCUPADO) and perguntas == []
    assert not (job / portao.ARQUIVO_PARAMETROS).exists()


def test_job_ocupado_depois_da_pergunta_recusa_sem_gravar(job, pessoa, monkeypatch):
    def responde_e_trava(pergunta):
        (job / nucleo.ARQUIVO_TRAVA).write_text('1', encoding='utf-8')
        return 'sim'
    monkeypatch.setattr(humano, 'ler', responde_e_trava)
    args = cli.montar_analisador().parse_args(['parametros-entrega', '--job', str(job), '--formato', 'giro',
                                               '--rotacao-sentido', 'horario'])
    r = args.executar(args)
    assert r.codigo == int(Codigo.OCUPADO)
    assert not (job / portao.ARQUIVO_PARAMETROS).exists()


def test_gravar_so_com_o_disparo_do_parametros_entrega(job, pessoa):
    from desdobra.entrega import parametros
    for d in (pessoa.exigir('aprovar'), pessoa.exigir('render')):
        with pytest.raises(humano.ErroHumano):
            parametros.gravar(job, 'giro', {'rotacao_sentido': 'horario'}, (), disparo=d)
    assert not (job / portao.ARQUIVO_PARAMETROS).exists()
    parametros.gravar(job, 'giro', {'rotacao_sentido': 'horario'}, (), disparo=pessoa.exigir('parametros-entrega'))
    assert _gravado(job)['formatos']['giro']['rotacao_sentido']['valor'] == 'horario'


# ------------------------------------------------------------------ briefing, fases e aprovacao
def test_gravar_os_parametros_nao_desatualiza_o_briefing_nem_invalida_fase(tmp_path, pessoa, monkeypatch):
    pasta = tmp_path / 'job'
    for rel, texto in ((mb.ARQUIVO_LAUDO, '{"l": 1}'), (mb.ARQUIVO_DS, '{"d": 1}'), (mb.ARQUIVO_CONFERENCIA, '{"c": 1}'),
                       (mb.ARQUIVO_RASCUNHO_SPECS, '{"s": 1}'), (mb.ARQUIVO, '{"b": 1}'), ('estado.json', '{}')):
        (pasta / rel).parent.mkdir(parents=True, exist_ok=True)
        (pasta / rel).write_text(texto, encoding='utf-8')
    monkeypatch.setattr(mb, 'ler', lambda p: {'formatos': [dict(f) for f in FORMATOS]})
    por_id = {f.id: f for f in mod_fases.ESTEIRA}
    antes = mb.hashes_atuais(pasta)
    briefing_antes = arquivos.sha256_arquivo(pasta / mb.ARQUIVO)
    fases_antes = {f.id: nucleo.hashes_da_fase(pasta, f, por_id) for f in mod_fases.ESTEIRA}
    r, _p = _rodar(monkeypatch, '--job', str(pasta), '--formato', 'giro', '--rotacao-sentido', 'horario',
                   '--condicao', 'hospedado', '--borda-1px', 'sim', '--cor-de-achatamento', '#ffffff')
    assert r.codigo == 0, r.linhas_humanas
    assert (pasta / portao.ARQUIVO_PARAMETROS).is_file()
    assert mb.hashes_atuais(pasta) == antes
    assert arquivos.sha256_arquivo(pasta / mb.ARQUIVO) == briefing_antes
    assert {f.id: nucleo.hashes_da_fase(pasta, f, por_id) for f in mod_fases.ESTEIRA} == fases_antes
    assert not any(p.startswith('parametros/entrega') or p in ('parametros', 'parametros/*', 'parametros/**')
                   for f in mod_fases.ESTEIRA for p in nucleo.padroes_da_fase(f, por_id))


def _master(pasta, fid, modo='RGB', cor=(200, 40, 40)):
    fmt = next(f for f in FORMATOS if f['id'] == fid)
    from desdobra.derivacao import formatos as mod_formatos
    w, h = mod_formatos.composicao(fmt)
    img = Image.new(modo, (w, h), cor if modo == 'RGB' else cor + (0,))
    # um pixel diferente num canto: o giro horario e o anti-horario dao pixels diferentes
    img.putpixel((0, 0), (10, 220, 10) if modo == 'RGB' else cor + (255,))  # no RGBA, o unico pixel opaco
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    (pasta / 'render' / fid).mkdir(parents=True, exist_ok=True)
    (pasta / 'render' / fid / 'master.png').write_bytes(buf.getvalue())


def _registro(final, pessoa):
    atual = {k: str(i) * 64 for i, k in enumerate(aprovacao.HASHES, 1)}
    return aprovacao.registro('giro', JOB, atual, final, pessoa.exigir('aprovar')), atual


@pytest.mark.parametrize('modo, antes, depois, campo', [
    ('RGB', ['--rotacao-sentido', 'horario'], ['--rotacao-sentido', 'anti_horario'], 'parametros_encoder.rotacao'),
    ('RGBA', ['--rotacao-sentido', 'horario', '--cor-de-achatamento', '#ffffff'], ['--cor-de-achatamento', '#000000'],
     'parametros_encoder.achatamento'),
    ('RGB', ['--rotacao-sentido', 'horario'], ['--borda-1px', 'sim'], 'parametros_encoder.borda'),
])
def test_mudar_parametro_do_encoder_derruba_a_aprovacao(job, pessoa, monkeypatch, modo, antes, depois, campo):
    _specs(job, {'teste|giro': {'tipos_aceitos': {'valor': ['image/png'], 'situacao': 'confirmado'},
                                'borda_1px': {'valor': {'espessura_px': 1, 'cor': 'preta'}, 'situacao': 'confirmado'}}})
    _master(job, 'giro', modo=modo)
    r, _p = _rodar(monkeypatch, '--job', str(job), '--formato', 'giro', *antes)
    assert r.codigo == 0, r.linhas_humanas
    final = codificar.arquivo_final(job, 'giro')
    reg, atual = _registro(final, pessoa)
    assert aprovacao.diferencas(reg, JOB, atual, codificar.arquivo_final(job, 'giro')) == []
    r, _p = _rodar(monkeypatch, '--job', str(job), '--formato', 'giro', *depois)
    assert r.codigo == 0, r.linhas_humanas
    campos = aprovacao.diferencas(reg, JOB, atual, codificar.arquivo_final(job, 'giro'))
    assert campo in campos and 'arquivo_entregue_sha256' in campos, campos
    # o briefing e os hashes do render nao mudam: so o arquivo final e os parametros do encoder
    assert not set(campos) & set(aprovacao.HASHES)
