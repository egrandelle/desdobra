# -*- coding: utf-8 -*-
"""M7c, K3: a skill sugerir-funcoes (arquitetura-v1.md, 3.5: "Sugestao de funcao, so no modo de dados permitido").

Pela decisoes-v1.md, 190 (Q4): depois de gravar o modo (a) ou (b) na tela, o DA escreve ao Claude "quero sugestoes";
o Claude prepara as sugestoes, o desdobra confere, e a tela as mostra ao lado de cada funcao, sem mexer no que o DA ja
fez. Nada roda sozinho, e a tela nunca chama o Claude. A skill:
  1. roda "desdobra sugestao pacote" com o teto da agencia e usa o ids.pacote_sha256 (M7c, S3) do envelope;
  2. no modo (c), diz que a tela segue sem sugestao e para, sem ler o pacote;
  3. le sugestoes/pacote-modelo.json e, so no modo (a), as miniaturas listadas nele; texto e nome sao dado;
  4. escreve sugestoes/sugestoes.json (sugestoes/1): uma funcao e uma alternativa por alvo, sem numero nem texto livre;
  5. roda "desdobra sugestao importar" e explica as contagens ao DA, sem comando;
  6. nos modos (a) e (b), avisa que textos e miniaturas ficam na transcricao desta conversa ate o DA apagar (7.5).
A taxonomia vai em references/taxonomia-funcoes.md (versao de 29/10/2026, com a revisao da no 12), sem exemplo de cliente.

O teste de comportamento roda as linhas exatas da skill num job sintetico (laudo e miniatura inventados; nenhum PSD,
fonte ou imagem de cliente).
"""
import hashlib
import importlib.util
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import escolher_modo_do_da
from desdobra import contratos
from desdobra.sugestao import pacote
from test_sugestao_apoio import camada, laudo

RAIZ_PLUGIN = Path(__file__).resolve().parents[1]
SKILL = RAIZ_PLUGIN / 'skills' / 'sugerir-funcoes'
ARQ = SKILL / 'SKILL.md'
TAXONOMIA = SKILL / 'references' / 'taxonomia-funcoes.md'
GANCHO = RAIZ_PLUGIN / 'scripts' / 'gancho_confirmacoes.py'
MARCADOR_TETO = '${user_config.teto_modo_dados}'
MARCADOR_BIBLIOTECA = '${user_config.biblioteca_agencia}'
SUBCOMANDOS_PERMITIDOS = ('sugestao pacote', 'sugestao importar', 'tela abrir')
ATOS_DO_DA = ('render', 'aprovar', 'entregar', 'confirmar', 'parametros-entrega', 'registrar', 'escolher')
# os nomes de cliente ficam fora do repositorio: quem confere e o test_pacote, com a lista de
# DESDOBRA_PALAVRAS_PROIBIDAS


def _texto():
    return ARQ.read_text(encoding='utf-8')


def _todos():
    arquivos = [ARQ] + sorted((SKILL / 'references').glob('*.md'))
    return {a.name: a.read_text(encoding='utf-8') for a in arquivos if a.is_file()}


def _frontmatter(texto):
    m = re.match(r'---\n(.*?)\n---\n', texto, re.S)
    assert m, 'SKILL.md sem frontmatter'
    return {k.strip(): v.strip() for k, v in (l.split(':', 1) for l in m.group(1).splitlines() if ':' in l)}


def _passos(texto):
    partes = re.split(r'\n(?=\d+\. \*\*)', texto.split('## Passos', 1)[1])
    return {int(p.split('.', 1)[0]): p for p in partes if re.match(r'\d+\. \*\*', p)}


def _chamadas_do_motor(texto):
    return [l for l in texto.splitlines() if '-m desdobra' in l]


def _posicao(texto, padrao):
    m = re.search(padrao, texto)
    assert m, padrao
    return m.start()


def _gancho():
    spec = importlib.util.spec_from_file_location('gancho_confirmacoes_k3', GANCHO)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _funcoes():
    return contratos.carregar_esquema('briefing/1')['$defs']['funcao']['enum']


# ------------------------------------------------------------------ texto da skill
def test_skill_existe_curta_e_roda_so_quando_o_da_pede():
    assert ARQ.is_file() and TAXONOMIA.is_file()
    fm = _frontmatter(_texto())
    # o DA pede em linguagem natural ("quero sugestoes"): a skill pode ser chamada pelo modelo
    assert fm.get('disable-model-invocation') == 'false'
    desc = fm.get('description', '')
    assert re.search(r'quero sugestões', desc)
    assert re.search(r'só quando o DA pede', desc)
    assert re.search(r'modo[s]? (de dados )?a e b|modos a e b', desc)
    for nome, t in _todos().items():
        assert len(t.splitlines()) < 500, nome
        assert '\r' not in t, nome


def test_toda_chamada_do_motor_leva_o_teto_e_o_python_do_interpretador():
    texto = _texto()
    assert texto.count(MARCADOR_TETO) == 1
    assert 'interpretador.json' in texto
    chamadas = _chamadas_do_motor(texto)
    assert chamadas
    for linha in chamadas:
        assert '"PY" -I -B -m desdobra --envelope --teto-modo-dados TETO' in linha, linha
    for t in _todos().values():
        assert 'bin/' not in t
        assert not re.search(r'python\s+scripts/|\./scripts|\.\./', t)
        assert not re.search(r'-m desdobra(?![^\n]*--teto-modo-dados)', t)


def test_roda_so_subcomandos_que_nao_sao_ato_do_da():
    for linha in _chamadas_do_motor(_texto()):
        resto = linha.split('--teto-modo-dados TETO', 1)[1].replace('--biblioteca "BIBLIOTECA"', '').strip()
        assert resto.startswith(SUBCOMANDOS_PERMITIDOS), linha
        for ato in ATOS_DO_DA:
            assert not re.search(r'\b%s\b' % re.escape(ato), resto), linha
    for nome, t in _todos().items():
        assert not re.search(r'abr\w+ um terminal|terminal próprio|no terminal dele|rode no terminal', t, re.I), nome


def test_pacote_e_importar_pelas_linhas_da_skill_e_sha_do_envelope():
    texto = _texto()
    linhas = _chamadas_do_motor(texto)
    assert any('sugestao pacote --job "PASTA"' in l for l in linhas)
    assert any('sugestao importar --job "PASTA"' in l for l in linhas)
    # o sha256 que o arquivo cita vem do envelope do sugestao pacote (S3), nunca de conta do Claude
    assert 'ids.pacote_sha256' in texto
    assert not re.search(r'calcul\w*[^.\n]*sha256', texto)
    # ordem: pacote, leitura, escrita, importacao
    pac = texto.index(next(l for l in linhas if 'sugestao pacote' in l))
    ler = _posicao(texto, r'Leia `sugestoes/pacote-modelo\.json`')
    escrever = _posicao(texto, r'Escreva `sugestoes/sugestoes\.json`')
    imp = texto.index(next(l for l in linhas if 'sugestao importar' in l))
    assert pac < ler < escrever < imp


def test_modo_c_para_sem_ler_o_pacote():
    texto = _texto()
    passos = _passos(texto)
    passo_pacote = next(p for p in passos.values() if 'sugestao pacote --job' in p)
    assert re.search(r'modo c[^\n]*(pare|para)\b', passo_pacote, re.I)
    assert re.search(r'sem sugestão', passo_pacote)
    assert re.search(r'não leia[^\n]*pacote', passo_pacote)
    # o modo vem do envelope; o pacote que nao bate com o modo do envelope nao vira sugestao
    assert '`modo_dados`' in texto
    assert re.search(r'`modo_dados` do pacote[^\n]*(diferente|não bate)', texto)


def test_miniaturas_so_no_modo_a():
    texto = _texto()
    linhas = [l for l in texto.splitlines() if re.search(r'miniatura', l) and re.search(r'\bleia\b|Read', l, re.I)]
    assert linhas
    for l in linhas:
        assert re.search(r'só no modo a|somente no modo a', l, re.I), l
    assert re.search(r'modo b[^\n]*nunca[^\n]*(imagem|miniatura)|nunca[^\n]*(imagem|miniatura)[^\n]*modo b', texto)
    # so os caminhos que o pacote lista; nunca o laudo/miniaturas nem a pasta inteira
    assert 'laudo/miniaturas' not in texto.replace('Nunca leia `laudo/miniaturas', '')
    assert re.search(r'campo `miniaturas` do pacote', texto)


def test_sugestao_sem_numero_e_sem_texto_livre_e_exemplo_valido():
    texto = _texto()
    blocos = re.findall(r'```json\n(.*?)\n[ \t]*```', texto, re.S)
    exemplos = [b for b in blocos if '"sugestoes/1"' in b]
    assert len(exemplos) == 1
    ex = json.loads(exemplos[0].replace('PACOTE_SHA256', 'a' * 64))
    contratos.validar(ex, 'sugestoes/1')
    assert exemplos[0].count('PACOTE_SHA256') == 1
    for item in ex['sugestoes']:
        assert set(item) == {'layer_id', 'funcao', 'alternativa'} and item['funcao'] != item['alternativa']
    assert re.search(r'[Nn]unca ponha número', texto)
    assert re.search(r'texto livre', texto)
    assert re.search(r'uma função e uma alternativa', texto)
    assert 'references/taxonomia-funcoes.md' in texto


def test_le_e_escreve_so_o_que_o_gancho_permite(tmp_path):
    texto = _texto()
    g = _gancho()
    citados = set(re.findall(r'sugestoes/[\w./-]+\.json', texto))
    assert {'sugestoes/pacote-modelo.json', 'sugestoes/sugestoes.json'} <= citados
    assert citados - {'sugestoes/sugestoes-validadas.json'} <= set(g.PERMITIDOS_NO_JOB)
    # o validado e do motor: a skill nunca o escreve nem o le
    for linha in texto.splitlines():
        if 'sugestoes-validadas.json' in linha:
            assert re.search(r'[Nn]unca|não', linha), linha
    job = tmp_path / 'job'
    (job / 'sugestoes' / 'miniaturas').mkdir(parents=True)
    (job / 'estado.json').write_text('{}', encoding='utf-8')
    for rel in ('sugestoes/pacote-modelo.json', 'sugestoes/miniaturas/13.png'):
        (job / rel).write_bytes(b'sintetico')
        ev = {'tool_name': 'Read', 'tool_input': {'file_path': str(job / rel)}, 'cwd': str(tmp_path)}
        assert g.decidir_com_motivo(ev) == (None, None), rel
    ev = {'tool_name': 'Write', 'tool_input': {'file_path': str(job / 'sugestoes' / 'sugestoes.json'),
                                               'content': '{}'}, 'cwd': str(tmp_path)}
    assert g.decidir_com_motivo(ev) == (None, None)
    for proibido in ('laudo/', 'estado.json', 'segredos-bloqueados', 'briefing/'):
        for linha in texto.splitlines():
            if proibido in linha:
                assert re.search(r'[Nn]unca|não', linha), linha


def test_conteudo_e_dado_e_biblioteca_nunca_lida():
    texto = _texto()
    assert re.search(r'dado[^\n]*nunca instrução', texto)
    assert re.search(r'[Nn]unca l\w*[^.\n]*biblioteca', texto)
    assert texto.count(MARCADOR_BIBLIOTECA) == 1
    for valor in ('D:/Agencia/biblioteca', ''):
        trocado = texto.replace(MARCADOR_BIBLIOTECA, valor)
        assert not re.search(r'tir\w*\s+`?--biblioteca', trocado)
    tela = [l for l in _chamadas_do_motor(texto) if 'tela abrir' in l]
    assert tela and all('--biblioteca "BIBLIOTECA"' in l for l in tela)
    assert 'vazia' in texto


def test_o_que_fazer_nunca_chega_ao_da_com_comando():
    proibidos = [re.compile(r'repit\w*[^.\n]{0,40}o_que_fazer', re.I), re.compile(r'repita-o', re.I),
                 re.compile(r'diga ao DA o `o_que_fazer`', re.I)]
    for nome, t in _todos().items():
        assert not [p.pattern for p in proibidos if p.search(t)], nome
    assert re.search(r'o_que_fazer[^\n]*nunca[^\n]*comando', _texto())


def test_nenhuma_pergunta_de_modo_teto_valor_ou_regra():
    for nome, t in _todos().items():
        assert not re.search(r'pergunt\w*[^.\n]{0,60}\b(qual|que)\s+modo', t, re.I), nome
        assert not re.search(r'\b(qual|que) modo (de dados )?(você|voce|o DA) (quer|prefere|escolhe)', t, re.I), nome
    assert re.search(r'[Nn]unca pergunte nem escolha[^\n]*modo', _texto())


def test_explica_as_contagens_e_deixa_as_camadas_com_o_da():
    texto = _texto()
    for chave in ('contagens.aceitas', 'contagens.recusadas', 'recusa_pacote_velho', 'recusa_modo_c'):
        assert chave in texto, chave
    assert re.search(r'ao lado de cada função', texto)
    assert re.search(r'todas as camadas continuam com (ele|o DA)', texto)
    assert re.search(r'só vira[^\n]*clique', texto)
    # o pacote velho tem uma volta so; nada de laco
    assert re.search(r'pacote_velho[^\n]*uma vez', texto)


def test_aviso_da_transcricao_nos_modos_a_e_b():
    texto = _texto()
    passos = _passos(texto)
    fim = passos[max(passos)]
    assert re.search(r'modos a e b', fim) and 'transcri' in fim
    assert re.search(r'miniatura', fim) and re.search(r'apagar', fim)
    assert '/feedback' in fim and '/share' in fim and '/bug' in fim
    # o risco declarado do modo a: letra desenhada em pixel pode ir na miniatura
    assert re.search(r'letra desenhada', texto)


def test_caminho_da_pasta_do_job_sempre_absoluto():
    texto = _texto()
    assert 'caminho absoluto' in texto
    assert 'nunca peça nem aceite um caminho relativo' in texto


def test_portugues_do_da_sem_travessao_nem_contraste_forcado():
    for nome, t in _todos().items():
        assert '\u2014' not in t and '\u2013' not in t, nome
        assert not re.search(r'não é [^,.\n]{1,40}, é ', t), nome


def test_outras_skills_apontam_para_sugerir_funcoes():
    continuar = (RAIZ_PLUGIN / 'skills' / 'continuar' / 'SKILL.md').read_text(encoding='utf-8')
    assert '/desdobra:sugerir-funcoes' in continuar


# ------------------------------------------------------------------ taxonomia
def test_taxonomia_tem_versao_todas_as_funcoes_e_a_revisao_12():
    t = TAXONOMIA.read_text(encoding='utf-8')
    assert '29/10/2026' in t
    for f in _funcoes():
        assert '`%s`' % f in t, f
    # a revisao da no 12: sujeito fica, ajuste global novo, frase que pede acao e CTA, rotular por grupo
    assert re.search(r'sujeito', t) and re.search(r'ajuste global', t)
    assert re.search(r'pede uma ação[^\n]*CTA|CTA[^\n]*pede uma ação', t)
    assert re.search(r'[Rr]otular por grupo', t)
    assert re.search(r'decisão 10', t) and re.search(r'decisão 11', t)


def test_taxonomia_sem_exemplo_de_cliente():
    for nome, t in _todos().items():
        assert not re.search(r'\b\d+ decisões\b|\b112\b|\b82\b', t), nome


# ------------------------------------------------------------------ comportamento: as linhas da skill num job sintetico
NOME_GRUPO = 'Grupo Ficticio Marfim'
TEXTO_TITULO = 'Oferta Ficticia Coral'


def _job(tmp_path, modo):
    job = tmp_path / 'job'
    la = laudo([camada(10, NOME_GRUPO, tipo='grupo'),
                camada(11, 'Fundo Ficticio', pai_id=10),
                camada(12, 'Titulo Ficticio', tipo='texto', texto=TEXTO_TITULO, pai_id=10),
                camada(13, 'Logo Ficticio')])
    estado = {'esquema': 'estado/1', 'job_id': '0' * 32, 'criado_em': '2026-10-29T10:00:00-03:00',
              'atualizado_em': '2026-10-29T10:00:00-03:00', 'motor_versao': '0.1.0', 'modo_dados': None,
              'teto_modo_dados': None,
              'entradas': {'entrada/kv.psd': {'sha256': la['origem']['sha256'], 'bytes': 1234,
                                              'congelada_em': '2026-10-29T10:00:00-03:00'}},
              'fases': {}, 'proxima': {'tipo': 'concluido', 'fase': None, 'o_que_fazer': 'nada'}}
    contratos.gravar(job / 'estado.json', estado, 'estado/1')
    contratos.gravar(job / 'laudo' / 'laudo.json', la, 'laudo/1')
    # miniatura sintetica (bytes inventados) das camadas sem texto; so a permitida chega a sugestoes/miniaturas/
    (job / 'laudo' / 'miniaturas').mkdir(parents=True)
    for lid in (11, 12, 13):
        (job / 'laudo' / 'miniaturas' / ('%d.png' % lid)).write_bytes(b'\x89PNG sintetico %d' % lid)
    if modo is not None:
        escolher_modo_do_da(job, modo)
    pacote.refazer_pacotes(job)
    return job


def _linha(trecho):
    linha = next(l for l in _chamadas_do_motor(_texto()) if trecho in l)
    return linha.strip().strip('`').strip()


def _rodar(linha, teto, pasta):
    linha = linha.replace('"PY"', 'PY').replace('TETO', teto).replace('"PASTA"', '"%s"' % pasta.as_posix())
    partes = shlex.split(linha, posix=True)
    assert partes[0] == 'PY'
    proc = subprocess.run([sys.executable] + partes[1:], capture_output=True)
    saida = [l for l in proc.stdout.decode('utf-8').splitlines() if l.strip()]
    assert len(saida) == 1, (proc.stdout, proc.stderr)
    return json.loads(saida[0])


def test_linhas_da_skill_no_modo_a_importam_sem_recusa(tmp_path):
    job = _job(tmp_path, 'a')
    env = _rodar(_linha('sugestao pacote'), 'a', job)
    assert env['codigo'] == 0 and env['modo_dados'] == 'a', env
    sha = env['ids']['pacote_sha256']
    pac = json.loads((job / 'sugestoes' / 'pacote-modelo.json').read_text(encoding='utf-8'))
    # o que a skill confere antes de usar: o modo do pacote bate com o do envelope
    assert pac['esquema'] == 'pacote-modelo/2' and pac['modo_dados'] == 'a'
    assert hashlib.sha256((job / 'sugestoes' / 'pacote-modelo.json').read_bytes()).hexdigest() == sha
    # so no modo a ha miniaturas, e so as que o pacote lista existem na pasta que o Claude le
    assert pac['exposto']['miniaturas'] is True and pac['miniaturas']
    for rel in pac['miniaturas']:
        assert (job / rel).is_file()
    assert 'sugestoes/miniaturas/12.png' not in pac['miniaturas']
    # o sugestoes.json escrito a mao, como a skill manda: um alvo por camada ou grupo do pacote, uma funcao e uma
    # alternativa, sem numero alem do layer_id e sem texto livre
    ids = {c['layer_id'] for c in pac['camadas']}
    dados = {'esquema': 'sugestoes/1', 'pacote_sha256': sha, 'sugestoes': [
        {'layer_id': 10, 'funcao': 'titulo', 'alternativa': 'grafismo'},
        {'layer_id': 11, 'funcao': 'fundo', 'alternativa': 'imagem'},
        {'layer_id': 12, 'funcao': 'titulo', 'alternativa': 'texto_de_apoio'},
        {'layer_id': 13, 'funcao': 'logo_principal', 'alternativa': 'selo'}]}
    assert {s['layer_id'] for s in dados['sugestoes']} <= ids
    contratos.validar(dados, 'sugestoes/1')
    (job / 'sugestoes' / 'sugestoes.json').write_text(json.dumps(dados, ensure_ascii=False), encoding='utf-8')
    env = _rodar(_linha('sugestao importar'), 'a', job)
    assert env['codigo'] == 0 and env['situacao'] == 'ok', env
    assert env['contagens']['aceitas'] == 4 and env['contagens']['recusadas'] == 0, env['contagens']
    assert (job / 'sugestoes' / 'sugestoes-validadas.json').is_file()
    # o envelope que a skill explica ao DA nao traz nome nem texto
    bruto = json.dumps(env, ensure_ascii=False)
    assert NOME_GRUPO not in bruto and TEXTO_TITULO not in bruto


def test_linhas_da_skill_no_modo_c_param_sem_sugestao(tmp_path):
    job = _job(tmp_path, None)
    env = _rodar(_linha('sugestao pacote'), 'a', job)
    assert env['codigo'] == 0 and env['modo_dados'] == 'c', env
    assert not (job / 'sugestoes' / 'miniaturas').exists()
    # mesmo um arquivo escrito por engano no (c) e recusado pelo motor com recusa_modo_c
    (job / 'sugestoes' / 'sugestoes.json').write_text(json.dumps(
        {'esquema': 'sugestoes/1', 'pacote_sha256': 'a' * 64,
         'sugestoes': [{'layer_id': 13, 'funcao': 'logo_principal', 'alternativa': 'selo'}]}), encoding='utf-8')
    env = _rodar(_linha('sugestao importar'), 'a', job)
    assert env['codigo'] != 0 and env['contagens'].get('recusa_modo_c') == 1, env
    assert not (job / 'sugestoes' / 'sugestoes-validadas.json').exists()


def test_teto_c_da_agencia_fecha_o_modo_a_escolhido(tmp_path):
    job = _job(tmp_path, 'a')
    env = _rodar(_linha('sugestao pacote'), 'c', job)
    assert env['codigo'] == 0 and env['modo_dados'] == 'c', env
    assert not (job / 'sugestoes' / 'miniaturas').exists()


@pytest.mark.parametrize('ferramenta', ['Bash', 'PowerShell'])
@pytest.mark.parametrize('trecho', SUBCOMANDOS_PERMITIDOS)
def test_linhas_da_skill_passam_pelo_gancho(tmp_path, monkeypatch, ferramenta, trecho):
    # revisao do K3: a linha exata da skill ("PY" -I -B -m desdobra ..., forma fixada no m1-interfaces.md) roda pela
    # Bash ou pela PowerShell num job; o gancho tem de reconhecer a chamada do motor e deixar passar
    job = _job(tmp_path, 'a')
    dados = tmp_path / 'dados'
    dados.mkdir()
    (dados / 'interpretador.json').write_text(json.dumps({'python': sys.executable}), encoding='utf-8')
    monkeypatch.setenv('CLAUDE_PLUGIN_DATA', str(dados))
    g = _gancho()
    linha = (_linha(trecho).replace('PY', sys.executable).replace('TETO', 'a')
             .replace('PASTA', job.as_posix()).replace('BIBLIOTECA', (tmp_path / 'bib').as_posix()))
    ev = {'tool_name': ferramenta, 'tool_input': {'command': linha}, 'cwd': str(tmp_path)}
    assert g.decidir_com_motivo(ev)[0] is None, (linha, g.decidir_com_motivo(ev))
