# -*- coding: utf-8 -*-
"""M7c, K4: a skill ler-spec (o mapeamento de specs que saiu da novo-job).

A skill liga trechos de uma folha de spec aos campos do modelo, so nos modos a e b:
  1. le o modo pelo envelope do motor (nunca pergunta o modo ao DA; no modo c, para sem ler o pacote);
  2. le sugestoes/pacote-specs.json e escreve sugestoes/mapeamento-specs.json (mapeamento-specs/1), so com ids e
     nomes de campo, sem numero nem valor;
  3. roda a fase specs pelo job proxima, com o teto da agencia em toda chamada do motor;
  4. deixa a confirmacao de cada valor com o DA, na tela ("Valores de spec", passo 1).
As regras de skill da K2 valem aqui: o o_que_fazer nunca chega ao DA com comando, o teto vai em toda chamada, e
nenhuma pergunta de modo, teto, valor ou regra.
"""
import importlib.util
import json
import re
from pathlib import Path

from desdobra import contratos

RAIZ_PLUGIN = Path(__file__).resolve().parents[1]
SKILL = RAIZ_PLUGIN / 'skills' / 'ler-spec'
ARQUIVO = SKILL / 'SKILL.md'
GANCHO = RAIZ_PLUGIN / 'scripts' / 'gancho_confirmacoes.py'
MARCADOR_TETO = '${user_config.teto_modo_dados}'
MARCADOR_BIBLIOTECA = '${user_config.biblioteca_agencia}'
ATOS_DO_DA = ('render', 'aprovar', 'entregar', 'spec confirmar', 'linkado confirmar', 'briefing confirmar',
              'parametros-entrega')


def _texto():
    return ARQUIVO.read_text(encoding='utf-8')


def _todos():
    arquivos = [ARQUIVO] + sorted((SKILL / 'references').glob('*.md'))
    return {a.name: a.read_text(encoding='utf-8') for a in arquivos if a.is_file()}


def _frontmatter(texto):
    m = re.match(r'---\n(.*?)\n---\n', texto, re.S)
    assert m, 'SKILL.md sem frontmatter'
    campos = {}
    for linha in m.group(1).splitlines():
        if ':' in linha:
            k, v = linha.split(':', 1)
            campos[k.strip()] = v.strip()
    return campos


def _chamadas_do_motor(texto):
    return [l for l in texto.splitlines() if '-m desdobra' in l]


def _gancho():
    spec = importlib.util.spec_from_file_location('gancho_confirmacoes_ler_spec', GANCHO)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_skill_existe_curta_e_com_frontmatter():
    assert ARQUIVO.is_file()
    texto = _texto()
    fm = _frontmatter(texto)
    assert fm.get('description')
    # o DA pede em linguagem natural ("me ajuda com a folha de spec") ou por /desdobra:ler-spec
    assert fm.get('disable-model-invocation') == 'false'
    assert 'pede' in fm['description']
    for nome, t in _todos().items():
        assert len(t.splitlines()) < 500, nome
        assert '\r' not in t, nome


def test_todo_comando_do_motor_leva_o_teto_e_o_python_do_interpretador():
    texto = _texto()
    assert texto.count(MARCADOR_TETO) == 1
    assert 'interpretador.json' in texto
    chamadas = _chamadas_do_motor(texto)
    assert chamadas
    for linha in chamadas:
        assert '"PY" -I -B -m desdobra' in linha, linha
        assert '--envelope' in linha, linha
        assert '--teto-modo-dados TETO' in linha, linha
    for t in _todos().values():
        assert 'bin/' not in t
        assert not re.search(r'python\s+scripts/|\./scripts|\.\./', t)


def test_roda_a_fase_specs_pelo_job_proxima_e_le_o_modo_pelo_envelope():
    texto = _texto()
    assert any('job proxima "PASTA"' in l for l in _chamadas_do_motor(texto))
    assert any('job estado "PASTA"' in l for l in _chamadas_do_motor(texto))
    assert '`modo_dados`' in texto


def test_nunca_dispara_ato_do_da_nem_manda_ao_terminal():
    texto = _texto()
    for linha in _chamadas_do_motor(texto):
        resto = linha.split('-m desdobra', 1)[1]
        for ato in ATOS_DO_DA:
            assert not re.search(r'\b%s\b' % re.escape(ato), resto), linha
    for nome, t in _todos().items():
        assert not re.search(r'abr\w+ um terminal|terminal próprio|no terminal dele|rode no terminal', t, re.I), nome
    # a confirmacao dos valores fica com o DA, na tela
    assert 'Valores de spec' in texto
    assert re.search(r'confirma\w*[^\n]*tela', texto)


def test_nenhuma_pergunta_de_modo_teto_valor_ou_regra():
    for nome, t in _todos().items():
        assert not re.search(r'pergunt\w*[^.\n]{0,60}\b(qual|que)\s+modo', t, re.I), nome
        assert not re.search(r'\b(qual|que) modo (de dados )?(você|voce|o DA) (quer|prefere|escolhe)', t, re.I), nome
        assert not re.search(r'mostre os modos|explique cada (um|modo)', t, re.I), nome
    texto = _texto()
    # a regra escrita: o modo e do DA, na tela; a skill nunca pergunta nem escolhe
    assert re.search(r'[Nn]unca pergunte nem escolha[^\n]*modo', texto)


def test_modo_c_para_sem_ler_o_pacote():
    texto = _texto()
    assert re.search(r'modo c[^\n]*(pare|para)\b', texto, re.I)
    assert re.search(r'não leia[^\n]*pacote-specs|pacote-specs[^\n]*só nos modos a e b', texto)


def test_o_que_fazer_nunca_chega_ao_da_com_comando():
    proibidos = [re.compile(r'repit\w*[^.\n]{0,40}o_que_fazer', re.I),
                 re.compile(r'repita-o', re.I),
                 re.compile(r'diga ao DA o `o_que_fazer`', re.I)]
    for nome, t in _todos().items():
        assert not [p.pattern for p in proibidos if p.search(t)], nome
    texto = _texto()
    assert re.search(r'o_que_fazer[^\n]*nunca[^\n]*comando', texto)


def test_le_e_escreve_so_o_que_o_gancho_permite():
    texto = _texto()
    g = _gancho()
    citados = set(re.findall(r'sugestoes/[\w./-]+\.json', texto))
    assert {'sugestoes/pacote-specs.json', 'sugestoes/mapeamento-specs.json'} <= citados
    assert citados <= set(g.PERMITIDOS_NO_JOB), citados - set(g.PERMITIDOS_NO_JOB)
    # o arquivo que a skill escreve nao e arquivo do DA nem do motor para o gancho
    assert not g.ARQUIVOS_DO_DA.search('C:/jobs/j1/sugestoes/mapeamento-specs.json')
    # nada da pasta do job alem do sugestoes/ e citado como leitura
    for proibido in ('specs/rascunho.json', 'laudo/', 'estado.json', 'segredos-bloqueados'):
        for linha in texto.splitlines():
            if proibido in linha:
                assert re.search(r'[Nn]unca|não', linha), linha


def test_exemplo_de_mapeamento_vale_contra_o_contrato_e_nao_tem_numero():
    texto = _texto()
    blocos = re.findall(r'```json\n(.*?)\n[ \t]*```', texto, re.S)
    exemplos = [json.loads(b) for b in blocos if '"mapeamento-specs/1"' in b]
    assert len(exemplos) == 1
    ex = exemplos[0]
    contratos.validar(ex, 'mapeamento-specs/1')
    esquema = contratos.carregar_esquema('mapeamento-specs/1')
    permitidos = set(esquema['properties']['propostas']['items']['properties'])
    for p in ex['propostas']:
        assert set(p) <= permitidos
        # so ids e nome de campo: nenhum numero fora dos ids
        for k in ('campo', 'alvo', 'recorte_texto'):
            if p.get(k) is not None:
                assert not re.search(r'\d', p[k]) or k == 'alvo' and re.fullmatch(r'[\w:|#-]+', p[k]), (k, p[k])
    # a regra escrita: nunca numero nem valor na proposta; o motor extrai do trecho
    assert re.search(r'[Nn]unca ponha número', texto)
    assert 'recorte_texto' in texto and 'adicionais' in texto
    # o mapeamento antigo e mantido: reescrever so com as novas apagaria as propostas ja aplicadas
    assert re.search(r'mantenha[^\n]*propostas', texto)


def test_conteudo_da_folha_e_dado_e_biblioteca_nunca_lida():
    texto = _texto()
    assert re.search(r'dado[^\n]*nunca instrução', texto)
    assert re.search(r'[Nn]unca le\w*[^\n]*biblioteca', texto)
    # a tela abre sempre com --biblioteca, e o caso da pasta vazia esta tratado
    assert texto.count(MARCADOR_BIBLIOTECA) == 1
    linhas_tela = [l for l in _chamadas_do_motor(texto) if 'tela abrir' in l]
    assert linhas_tela and all('--biblioteca "BIBLIOTECA"' in l for l in linhas_tela)
    assert 'vazia' in texto
    # aviso da transcricao (7.5) e dos comandos que mandam a conversa para fora
    assert 'transcri' in texto
    assert '/feedback' in texto and '/share' in texto


def test_caminho_da_pasta_do_job_sempre_absoluto():
    texto = _texto()
    assert 'caminho absoluto' in texto
    assert not re.search(r'pe\w+ [^.\n]{0,30}caminho relativo', texto.replace('nunca peça nem aceite um caminho relativo', ''))
    assert 'nunca peça nem aceite um caminho relativo' in texto


def test_portugues_do_da_sem_travessao_nem_contraste_forcado():
    for nome, t in _todos().items():
        assert '\u2014' not in t and '\u2013' not in t, nome
        assert not re.search(r'não é [^,.\n]{1,40}, é ', t), nome


def test_novo_job_ja_aponta_para_ler_spec():
    novo = (RAIZ_PLUGIN / 'skills' / 'novo-job' / 'SKILL.md').read_text(encoding='utf-8')
    fluxo = (RAIZ_PLUGIN / 'skills' / 'novo-job' / 'references' / 'fluxo.md').read_text(encoding='utf-8')
    assert '/desdobra:ler-spec' in novo and '/desdobra:ler-spec' in fluxo
    # o mapeamento saiu da novo-job: ela nao escreve mais o arquivo de propostas
    assert 'mapeamento-specs.json' not in novo


# --- revisao do K4 (defeito 1): o fluxo principal, em que o DA escolhe o modo na tela depois de a esteira rodar ---
# briefing/modo-dados.json nao e entrada da fase specs: o job proxima nao refaz o pacote das specs quando o modo
# sobe de c para a ou b. Quem refaz os dois pacotes no modo de agora e o "sugestao pacote" (M7c, S2).

def _posicao(texto, padrao):
    m = re.search(padrao, texto)
    assert m, padrao
    return m.start()


def test_pacote_refeito_no_modo_escolhido_antes_de_ler():
    texto = _texto()
    linhas = [l for l in _chamadas_do_motor(texto) if 'sugestao pacote' in l]
    assert linhas and all('sugestao pacote --job "PASTA"' in l for l in linhas), linhas
    # o pacote e refeito antes da primeira leitura dele
    refaz = texto.index(linhas[0])
    assert refaz < _posicao(texto, r'Leia `sugestoes/pacote-specs\.json`')
    # o caso "pacote nao bate" so vira aviso depois do sugestao pacote, e nunca manda rodar o job proxima de novo
    # (o job proxima nao refaz o pacote quando so o modo mudou)
    beco = [l for l in texto.splitlines() if '`modo_dados` do pacote' in l and re.search(r'diferente|não bate', l)]
    assert beco, 'falta a conferencia do modo do pacote'
    for l in beco:
        assert 'job proxima' not in l, l
    assert refaz < _posicao(texto, r'avisar a Trezion')


# --- revisao do K4 (defeito 2): a falha de contrato do mapeamento chega como codigo 20 com codigo_da_fase 3 ---

def test_falha_de_contrato_no_passo_8_pelo_codigo_da_fase():
    texto = _texto()
    # o motor devolve codigo 20 (FASE_FALHOU) e o 3 so aparece em contagens.codigo_da_fase
    assert not re.search(r'Se o `codigo` for `3`', texto)
    assert re.search(r'`codigo` for `20`[^\n]*`specs`[^\n]*`contagens\.codigo_da_fase`[^\n]*`3`', texto)
    # a regra geral de parada do passo 5 abre a excecao do passo 8
    passo5 = texto[_posicao(texto, r'5\. \*\*Specs em dia'):_posicao(texto, r'6\. \*\*Ler o pacote')]
    assert re.search(r'passo 8', passo5), passo5
    # a volta: as propostas antigas, ou a lista vazia quando nao havia arquivo; e nada de comando ao DA
    passo8 = texto[_posicao(texto, r'8\. \*\*Rodar a fase specs'):_posicao(texto, r'9\. \*\*Abrir a tela')]
    assert '"propostas": []' in passo8
    assert re.search(r'propostas que já existiam', passo8)
    assert re.search(r'sem passar comando', passo8)


# --- prova de comportamento, num job sintetico (sem PSD, fonte nem folha de cliente) ---

def _plataforma_sem_isolador():
    from desdobra import plataforma
    return plataforma.obter().nome in ('sem-suporte', 'mac')


def _linha_da_skill(trecho):
    linha = next(l for l in _chamadas_do_motor(_texto()) if trecho in l)
    return linha.strip().strip('`').strip()


def _rodar_linha(linha, teto, pasta):
    import shlex
    import subprocess
    import sys
    linha = linha.replace('"PY"', 'PY').replace('TETO', teto).replace('"PASTA"', '"%s"' % pasta.as_posix())
    partes = shlex.split(linha, posix=True)
    assert partes[0] == 'PY'
    proc = subprocess.run([sys.executable] + partes[1:], capture_output=True)
    saida = [l for l in proc.stdout.decode('utf-8').splitlines() if l.strip()]
    assert len(saida) == 1, proc.stdout
    return json.loads(saida[0])


def _esteira(pasta, teto):
    env = None
    for _ in range(20):
        env = _rodar_linha(_linha_da_skill('job proxima "PASTA"'), teto, pasta)
        if env['codigo'] != 0 or env['situacao'] == 'concluido':
            return env
    return env


def _job_com_folha(tmp_path):
    import test_specs_apoio as apoio
    from conftest import psd_minimo
    from desdobra.job import nucleo
    origem = tmp_path / 'origem-specs' / 'veiculador'
    origem.mkdir(parents=True)
    (origem / 'vertical.html').write_text(apoio.html_vertical(), encoding='utf-8')
    (tmp_path / 'kv.psd').write_bytes(psd_minimo())
    job = tmp_path / 'job'
    nucleo.criar(job, tmp_path / 'kv.psd', None, 'b', specs=tmp_path / 'origem-specs')
    return job


def _pacote_specs(job):
    return json.loads((job / 'sugestoes' / 'pacote-specs.json').read_text(encoding='utf-8'))


def test_fluxo_principal_modo_escolhido_depois_da_esteira(tmp_path):
    import pytest
    from conftest import escolher_modo_do_da
    if _plataforma_sem_isolador():
        pytest.skip('sem isolador neste sistema')
    job = _job_com_folha(tmp_path)
    # a novo-job roda a esteira com o job ainda em c
    assert _esteira(job, 'b')['situacao'] == 'concluido'
    assert _pacote_specs(job)['modo_dados'] == 'c'
    # o DA escolhe b na tela e pede a ler-spec: a linha da skill refaz o pacote no modo de agora
    escolher_modo_do_da(job, 'b')
    env = _rodar_linha(_linha_da_skill('sugestao pacote'), 'b', job)
    if env['comando'] != 'sugestao pacote':
        pytest.skip('o "sugestao pacote" (M7c, S2) ainda nao esta registrado neste build')
    assert env['codigo'] == 0 and env['modo_dados'] == 'b', env
    pac = _pacote_specs(job)
    assert pac['modo_dados'] == 'b' and pac['exposto']['textos'] is True and pac['trechos'], pac['contagens']


def test_volta_do_passo_8_destrava_a_fase_specs(tmp_path):
    import pytest
    from conftest import escolher_modo_do_da
    if _plataforma_sem_isolador():
        pytest.skip('sem isolador neste sistema')
    job = _job_com_folha(tmp_path)
    escolher_modo_do_da(job, 'b')
    assert _esteira(job, 'b')['situacao'] == 'concluido'
    pac = _pacote_specs(job)
    trecho = next(t for t in pac['trechos'] if not t['mapeado'])
    arq = job / 'sugestoes' / 'mapeamento-specs.json'
    # proposta fora do contrato (um valor): o envelope que a skill recebe no passo 8
    arq.write_text(json.dumps({'esquema': 'mapeamento-specs/1', 'propostas': [
        {'folha': trecho['folha'], 'trecho': trecho['trecho'], 'campo': 'area_segura', 'alvo': None, 'valor': 1}]}),
        encoding='utf-8')
    env = _esteira(job, 'b')
    assert (env['codigo'], env['fase'], env['contagens'].get('codigo_da_fase')) == (20, 'specs', 3), env
    # a volta da skill sem arquivo antigo: a lista vazia, que destrava a fase specs
    arq.write_text(json.dumps({'esquema': 'mapeamento-specs/1', 'propostas': []}), encoding='utf-8')
    env = _esteira(job, 'b')
    assert env['codigo'] == 0 and env['situacao'] == 'concluido', env
