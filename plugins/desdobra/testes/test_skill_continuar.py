# -*- coding: utf-8 -*-
"""M7c, K2: a skill continuar (arquitetura-v1.md, 3.5: "Le o estado e segue da proxima fase").

1. O estado do job chega ao Claude so pelo envelope do motor (job estado), nunca pela leitura de estado.json ou de
   outro arquivo do job (7.4, P1).
2. Fase do motor pendente: o Claude roda job proxima. O que falta e clique do DA (portao, bloqueio, fases em dia):
   o Claude reabre a tela com tela abrir.
3. Residuo do K1: o texto FIM do motor (job/fases.py) e o o_que_fazer do nucleo citam comandos de terminal. A skill
   nunca os repassa ao DA (no 159).
4. Toda chamada do motor leva --teto-modo-dados; a biblioteca vazia fica tratada sem guarda que cite o marcador; a
   skill nunca le a biblioteca e nunca pergunta modo, teto, valor ou regra.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

from desdobra import contratos, humano
from desdobra.job import nucleo

RAIZ_PLUGIN = Path(__file__).resolve().parents[1]
SKILL = RAIZ_PLUGIN / 'skills' / 'continuar'
ARQ = SKILL / 'SKILL.md'
MARCADOR_BIBLIOTECA = '${user_config.biblioteca_agencia}'
MARCADOR_TETO = '${user_config.teto_modo_dados}'
# o que a skill pode rodar do motor: so o que nao e ato do DA
SUBCOMANDOS_PERMITIDOS = ('job estado', 'job proxima', 'job trocar-entrada', 'job remover-entrada', 'tela abrir')


def _texto():
    return ARQ.read_text(encoding='utf-8')


def _textos():
    arquivos = [ARQ] + sorted((SKILL / 'references').glob('*.md'))
    return {a.name: a.read_text(encoding='utf-8') for a in arquivos if a.is_file()}


def _frontmatter(texto):
    m = re.match(r'---\n(.*?)\n---\n', texto, re.S)
    assert m, 'SKILL.md sem frontmatter'
    return dict(l.split(':', 1) for l in m.group(1).splitlines() if ':' in l)


def _passos(texto):
    """{numero: texto do passo} pelos itens '<n>. **Titulo.**' da secao Passos."""
    partes = re.split(r'\n(?=\d+\. \*\*)', texto.split('## Passos', 1)[1])
    return {int(p.split('.', 1)[0]): p for p in partes if re.match(r'\d+\. \*\*', p)}


def _chamadas_do_motor(texto):
    return [l for l in texto.splitlines() if '-m desdobra' in l]


def test_skill_existe_curta_e_com_descricao():
    texto = _texto()
    meta = _frontmatter(texto)
    assert 'description' in meta and re.search(r'continu|retom', meta['description'], re.I)
    assert meta.get('disable-model-invocation', '').strip() in ('true', 'false')
    assert len(texto.splitlines()) < 500
    assert '\r' not in texto


def test_estado_vem_do_envelope_e_nunca_do_arquivo():
    texto = _texto()
    estado = [l for l in _chamadas_do_motor(texto) if 'job estado' in l]
    assert estado and all('--envelope' in l for l in estado)
    # nunca manda ler estado.json nem arquivo do job pela ferramenta Read
    assert not re.search(r'(leia|abra|Read)[^.\n]*estado\.json', texto)
    assert re.search(r'[Nn]unca[^.\n]*le\w*[^.\n]*(arquivo|pasta) do job|[Nn]unca leia[^.\n]*estado\.json', texto)


def test_toda_chamada_do_motor_leva_o_teto():
    texto = _texto()
    chamadas = _chamadas_do_motor(texto)
    assert chamadas
    assert all('--teto-modo-dados TETO' in l and '--envelope' in l for l in chamadas)
    # TETO vem da configuracao do plugin, uma vez so
    assert texto.count(MARCADOR_TETO) == 1


def test_so_roda_o_que_nao_e_ato_do_da():
    for l in _chamadas_do_motor(_texto()):
        resto = l.split('--teto-modo-dados TETO', 1)[1]
        resto = resto.replace('--biblioteca "BIBLIOTECA"', '').strip()
        assert resto.startswith(SUBCOMANDOS_PERMITIDOS), l
        for ato in humano.COMANDOS:
            assert ' %s ' % ato not in ' %s ' % resto.split('"')[0], l


def test_fase_do_motor_roda_e_clique_do_da_reabre_a_tela():
    texto = _texto()
    assert any('job proxima' in l for l in _chamadas_do_motor(texto))
    tela = [l for l in _chamadas_do_motor(texto) if 'tela abrir' in l]
    assert tela and all('--biblioteca "BIBLIOTECA"' in l for l in tela)
    # a decisao sai dos campos do envelope de job estado
    for campo in ('fase', 'contagens.bloqueios_pendentes', 'situacao', 'codigo'):
        assert '`%s`' % campo in texto, campo
    assert re.search(r'clique[^.\n]*DA[^.\n]*tela|clique dele na tela', texto)


def test_passos_alinhados_com_as_referencias_do_novo_job():
    """A skill usa o fluxo.md e o regras-do-modelo.md do novo-job, que citam 'passo 2', 'passo 7' e 'passo 8 da
    skill'. Os mesmos numeros aqui dizem a mesma coisa."""
    texto = _texto()
    passos = _passos(texto)
    assert 'BIBLIOTECA' in passos[2] and MARCADOR_BIBLIOTECA in passos[2]
    assert 'trocar-entrada' in passos[7] and 'remover-entrada' in passos[7]
    assert 'tela abrir' in passos[8]
    assert any('job proxima' in l for l in passos[6].splitlines())
    for ref in ('regras-do-modelo.md', 'fluxo.md', 'glossario.md'):
        assert '${CLAUDE_PLUGIN_ROOT}/skills/novo-job/references/%s' % ref in texto


def test_caminhos_do_plugin_so_pela_raiz_e_referencias_existem():
    texto = _texto()
    assert 'bin/' not in texto
    for m in re.finditer(r'\$\{CLAUDE_PLUGIN_ROOT\}/([^\s`"\']+)', texto):
        assert (RAIZ_PLUGIN / m.group(1).rstrip('.,;:)')).exists(), m.group(0)
    # todo caminho de skill do plugin vem pela raiz do plugin, nunca relativo
    for m in re.finditer(r'(\S*)skills/', texto):
        assert m.group(1).endswith('${CLAUDE_PLUGIN_ROOT}/'), m.group(0)
    assert '${CLAUDE_PLUGIN_DATA}/interpretador.json' in texto


def test_pasta_do_job_so_por_caminho_absoluto():
    texto = _texto()
    assert 'caminho absoluto' in texto and 'Copiar como caminho' in texto
    assert re.search(r'nunca[^.\n]*caminho relativo', texto, re.I)


def test_biblioteca_vazia_tratada_sem_guarda_que_cite_o_marcador():
    texto = _texto()
    assert texto.count(MARCADOR_BIBLIOTECA) == 1
    for valor in ('D:/Agencia/biblioteca', ''):
        trocado = texto.replace(MARCADOR_BIBLIOTECA, valor)  # a troca que o Claude Code faz no texto
        assert not re.search(r'tir\w*\s+`?--biblioteca', trocado)
        assert 'sem troca' not in trocado
    assert 'vazia' in texto
    assert re.search(r'[Nn]unca l\w*[^.\n]*biblioteca|biblioteca[^.\n]*nunca l\w*', texto)


def test_nunca_repassa_o_o_que_fazer_nem_o_fim_do_motor():
    texto = _texto()
    proibidos = [re.compile(r'repit\w*[^.\n]{0,40}o_que_fazer', re.I),
                 re.compile(r'repita-o', re.I),
                 re.compile(r'diga ao DA o `o_que_fazer`', re.I)]
    for nome, t in _textos().items():
        assert not [m.group(0) for p in proibidos for m in p.finditer(t)], nome
    assert re.search(r'o_que_fazer[^\n]*nunca[^\n]*comando|comando[^\n]*o_que_fazer[^\n]*nunca', texto)
    # o concluido (FIM do motor) vira a tela, sem repassar o texto
    assert re.search(r'`concluido`[^\n]*', texto) and re.search(r'[Nn]ão repasse[^.\n]*texto', texto)


def test_nunca_manda_o_da_ao_terminal():
    texto = _texto()
    for padrao in (r'abr\w+ um terminal', r'rod\w+ no terminal', r'num terminal', r'Prompt de Comando',
                   r'digite[^.\n]*comando'):
        for m in re.finditer(padrao, texto, re.I):
            linha = texto[texto.rfind('\n', 0, m.start()) + 1:texto.find('\n', m.end())]
            assert re.search(r'\bnunca\b|\bnão\b', linha, re.I), linha
    assert re.search(r'DA nunca roda comando', texto)


def test_nunca_pergunta_modo_teto_valor_nem_regra():
    texto = _texto()
    # verbos de pedir ao DA ("peça" sozinho e tambem o substantivo, a peca do cliente)
    verbos = r'\b(pergunt\w*|escolh\w*|peça (?:ao DA|a ele))'
    for m in re.finditer(verbos + r'[^.\n]{0,60}\b(modo|teto|valor|regra|limite)\b', texto, re.I):
        linha = texto[texto.rfind('\n', 0, m.start()) + 1:texto.find('\n', m.end())]
        assert re.search(r'\bnunca\b|\bnão\b|\bnem\b|o DA escolhe|do DA', linha, re.I), linha
    assert re.search(r'[Nn]unca pergunte nem escolha[^.\n]*modo[^.\n]*teto[^.\n]*valor[^.\n]*regra', texto)


def test_avisos_de_fechamento():
    texto = _texto()
    for item in ('/feedback', '/bug', '/share', 'transcrições', 'próximo marco'):
        assert item in texto, item


def test_texto_sem_travessao_sem_meia_risca_e_sem_contraste_forcado():
    for nome, t in _textos().items():
        assert '\u2014' not in t and '\u2013' not in t, nome
        assert not re.search(r'não é [^,.\n]{1,40}, é ', t), nome


def _rodar(*argumentos):
    proc = subprocess.run([sys.executable, '-I', '-B', '-m', 'desdobra', *argumentos], capture_output=True)
    linhas = proc.stdout.decode('utf-8').strip().splitlines()
    assert len(linhas) == 1
    dados = json.loads(linhas[0])
    contratos.validar(dados, 'envelope/1')
    return dados


def test_contrato_do_envelope_que_a_skill_le(tmp_path, kv_psd):
    """O que a skill decide sai destes campos do job estado: fase do motor pendente (fase com nome, sem bloqueio)."""
    job = tmp_path / 'job'
    env = _rodar('--envelope', '--teto-modo-dados', 'a', 'job', 'criar', str(job), '--kv', str(kv_psd))
    assert env['codigo'] == 0
    env = _rodar('--envelope', '--teto-modo-dados', 'a', 'job', 'estado', str(job))
    assert env['codigo'] == 0 and env['situacao'] == 'ok' and env['fase'] == 'ler'
    assert env['contagens']['bloqueios_pendentes'] == 0 and env['modo_dados'] == 'c'
    # pasta que nao e job: codigo diferente de zero, e a skill pede o caminho de novo
    env = _rodar('--envelope', '--teto-modo-dados', 'a', 'job', 'estado', str(tmp_path / 'nada'))
    assert env['codigo'] != 0


def test_fases_em_dia_saem_sem_fase_e_com_o_texto_fim():
    """Fases em dia e sem bloqueio: fase nula e o texto FIM, que a skill nao repassa (residuo do K1)."""
    estado = {'fases': {f.id: {'situacao': 'concluida'} for f in nucleo.ESTEIRA}}
    avaliacao = {f.id: (True, None) for f in nucleo.ESTEIRA}
    proxima = nucleo.calcular_proxima(estado, avaliacao, nucleo.ESTEIRA)
    assert proxima['fase'] is None and proxima['tipo'] == 'concluido' and proxima['o_que_fazer'] == nucleo.FIM
    estado['fases']['fontes']['bloqueio'] = {'o_que_fazer': 'x'}
    proxima = nucleo.calcular_proxima(estado, avaliacao, nucleo.ESTEIRA)
    assert proxima['tipo'] == 'bloqueio' and proxima['fase'] == 'fontes'


def test_bloqueio_com_fase_do_motor_pendente_traz_a_fase_pendente():
    """Revisao K2: com bloqueio gravado na fase fontes e uma fase depois dela ainda por rodar, job estado traz em
    `fase` a fase pendente (ds), nao a fase bloqueada. So com todas as fases em dia a `fase` e a do bloqueio."""
    ids = [f.id for f in nucleo.ESTEIRA]
    estado = {'fases': {i: {'situacao': 'concluida'} for i in ids}}
    estado['fases']['fontes']['bloqueio'] = {'o_que_fazer': 'x'}
    avaliacao = {i: (True, None) for i in ids}
    avaliacao['ds'] = (False, 'sem registro')
    proxima = nucleo.calcular_proxima(estado, avaliacao, nucleo.ESTEIRA)
    assert proxima['tipo'] == 'fase' and proxima['fase'] == 'ds'
    assert nucleo.bloqueios_pendentes(estado, avaliacao, nucleo.ESTEIRA)


def test_passo_5_roda_as_fases_pendentes_antes_de_tratar_o_bloqueio():
    """Revisao K2: o ramo de bloqueio do passo 5 so vale com as fases em dia (fases_validas igual a fases). Com fase
    do motor pendente, a skill segue o passo 6 mesmo com bloqueio, e nunca explica o bloqueio pela fase pendente."""
    passos = _passos(_texto())
    assert not re.search(r'nula quando as fases estão em dia\)', passos[4])
    ramos = [l for l in passos[5].splitlines() if l.lstrip().startswith('- ')]
    pendente = [i for i, l in enumerate(ramos) if '`contagens.fases_validas`' in l and 'menor' in l]
    bloqueio = [i for i, l in enumerate(ramos) if '`contagens.bloqueios_pendentes`' in l and 'maior que zero' in l]
    assert pendente and bloqueio and pendente[0] < bloqueio[0]
    assert 'passo 6' in ramos[pendente[0]] and re.search(r'mesmo com bloqueio', ramos[pendente[0]])
    assert re.search(r'`contagens.fases_validas`[^\n]*igual[^\n]*`contagens.fases`', ramos[bloqueio[0]])
