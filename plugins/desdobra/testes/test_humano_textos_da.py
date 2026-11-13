# -*- coding: utf-8 -*-
"""M7c, K5: os textos que chegam ao DA nao mandam ninguem ao terminal (decisoes-v1.md, 159).

O DA nunca roda comando. Todo o_que_fazer e todo FIM que o DA pode ver (pela tela ou pelo Claude, que repassa o
envelope) diz que o ato e um clique dele na tela ou pede ao Claude para abrir a tela ou seguir o job. Os comandos
continuam no motor so para os testes e para a Trezion.

Textos alcancaveis pelo DA, nos modulos deste passo:
  - humano.O_QUE_FAZER (recusa de um ato so do DA que partiu de fora da tela);
  - tela.O_QUE_FAZER_ABERTA e cada tela.O_QUE_FAZER_RECUSA;
  - o FIM da esteira, o o_que_fazer de cada fase da ESTEIRA e os textos de calcular_proxima (fase que falhou, fase que
    ainda nao rodou, job concluido);
  - os o_que_fazer de job/nucleo.py e job/fases.py, lidos do proprio codigo (ast), menos os erros de uso dos
    comandos que so o Claude e os testes rodam (job criar, trocar-entrada, remover-entrada: opcao --kv, --fontes,
    caminho da entrada). Esses ficam listados em SO_DO_CLAUDE, com o motivo.

M7c, ajuste terminal (resposta do Duda ao ponto 8, 13/11): a varredura do fim deste arquivo cobre todo texto de todo
modulo do motor e o envelope de cada comando numa pasta que nao e job (docs/m1-interfaces.md, "M7c, ajuste terminal").
"""
import ast
import inspect
import re
from pathlib import Path

import pytest

from conftest import RAIZ_PLUGIN
from desdobra import humano, tela
from desdobra.job import fases as mod_fases
from desdobra.job import nucleo
from desdobra.job.nucleo import ErroJob

# o que conta como mandar alguem ao terminal num texto para o DA
PROIBIDOS = (
    ('comando entre aspas', re.compile(r'"\s*desdobra\s', re.I)),
    ('subcomando do motor', re.compile(r'\bdesdobra\s+(?:job|spec|render|aprovar|entregar|parametros-entrega|briefing|'
                                       r'ds|fontes|derivar|doctor|conferir-entrega|tela|ler|sugestao|linkado|marca)\b',
                                       re.I)),
    ('opcao de linha de comando', re.compile(r'(?<![\w-])--[a-z]', re.I)),
    ('terminal', re.compile(r'\bterminal\b', re.I)),
    ('prompt de comando', re.compile(r'prompt de comando', re.I)),
    ('powershell', re.compile(r'powershell', re.I)),
    ('rode', re.compile(r'\brode\b', re.I)),
    ('digite', re.compile(r'\bdigite\b', re.I)),
    ('marcador de pasta', re.compile(r'<pasta>', re.I)),
)
TRAVESSAO = ('—', '–')
NAO_E_X_E_Y = re.compile(r'\bnão é [^.;:]{1,60}, é\b', re.I)
# funcoes de job/nucleo.py cujos o_que_fazer sao erro de uso de comando que so o Claude e os testes rodam (a skill
# novo-job cria o job; a continuar troca e remove entrada). O DA nunca ve o argumento; o Claude corrige a chamada
SO_DO_CLAUDE = {
    'criar': 'erro de uso do job criar (opcao --kv, --fontes, --campanha, --specs, modo)',
    'trocar_entrada': 'erro de uso do job trocar-entrada (caminho relativo, caixa, arquivo novo)',
    'remover_entrada': 'erro de uso do job remover-entrada (caminho da fonte)',
    '_arquivos_de_fonte_oferecidos': 'erro de uso de --fontes do job criar',
    '_recusar_fontes': 'erro de uso do job criar (fonte na pasta de campanha ou de specs)',
}
CONSTANTES_SO_DO_CLAUDE = {'O_QUE_FAZER_FONTE_FORA': 'erro de uso do job criar (fonte em --campanha ou --specs)'}


def _problemas(texto):
    achados = [nome for nome, rx in PROIBIDOS if rx.search(texto)]
    if any(t in texto for t in TRAVESSAO):
        achados.append('travessao')
    if NAO_E_X_E_Y.search(texto):
        achados.append('nao e X, e Y')
    return achados


class _Fase:
    def __init__(self, id_, o_que_fazer='', tipo='fase', descricao='uma fase'):
        self.id, self.o_que_fazer, self.tipo, self.descricao = id_, o_que_fazer, tipo, descricao


def _textos_em_tempo_de_execucao():
    textos = {'humano.O_QUE_FAZER': humano.O_QUE_FAZER, 'tela.O_QUE_FAZER_ABERTA': tela.O_QUE_FAZER_ABERTA,
              'fases.FIM': mod_fases.FIM, 'nucleo.FIM': nucleo.FIM}
    textos.update({'tela.O_QUE_FAZER_RECUSA[%s]' % k: v for k, v in tela.O_QUE_FAZER_RECUSA.items()})
    textos.update({'fase %s' % f.id: f.o_que_fazer for f in nucleo.ESTEIRA})
    # calcular_proxima: fase que falhou sem texto proprio, fase que ainda nao rodou, job concluido
    sem_texto = _Fase('x')
    for situacao, rotulo in (('falhou', 'proxima falha'), ('pendente', 'proxima fase')):
        estado = {'fases': {'x': {'situacao': situacao}}}
        textos[rotulo] = nucleo.calcular_proxima(estado, {'x': (False, None)}, [sem_texto])['o_que_fazer']
    textos['proxima concluido'] = nucleo.calcular_proxima({'fases': {}}, {}, [])['o_que_fazer']
    return textos


TEXTOS = _textos_em_tempo_de_execucao()


@pytest.mark.parametrize('rotulo', sorted(TEXTOS))
def test_texto_do_da_sem_comando_de_terminal(rotulo):
    texto = TEXTOS[rotulo]
    assert isinstance(texto, str) and texto.strip(), rotulo
    assert _problemas(texto) == [], (rotulo, texto)


def test_job_sem_pasta_de_job_manda_ao_claude(tmp_path):
    with pytest.raises(ErroJob) as e:
        nucleo.conferir_job(tmp_path)
    assert _problemas(e.value.o_que_fazer) == [] and 'Claude' in e.value.o_que_fazer


def test_o_que_fazer_do_ato_do_da_e_um_clique_na_tela():
    t = humano.O_QUE_FAZER
    assert 'clique seu na tela' in t and 'Peça ao Claude para abrir a tela' in t


def test_fim_manda_o_da_a_tela():
    assert 'Peça ao Claude para abrir a tela' in nucleo.FIM and 'clique' in nucleo.FIM
    # os FIM antigos dos marcos M1 a M6, com comando de terminal, sairam do motor
    assert not [n for n in vars(mod_fases) if re.fullmatch(r'FIM_M\d+', n)]


def test_falha_de_fase_manda_ao_claude_e_ao_doctor():
    for f in nucleo.ESTEIRA:
        assert 'Peça ao Claude' in f.o_que_fazer and 'doctor' in f.o_que_fazer, f.id


# ------------------------------------------------------------------ varredura do codigo
def _strings(no):
    return [n.value for n in ast.walk(no) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def _o_que_fazer_do_codigo(modulo):
    """(rotulo, texto) de cada string que vira o_que_fazer ou FIM no codigo do modulo: argumento o_que_fazer=, chave
    'o_que_fazer' de dict, constante O_QUE_FAZER* ou FIM* e o_que_fazer de Fase(...). Pula o que esta em SO_DO_CLAUDE."""
    arvore = ast.parse(Path(inspect.getsourcefile(modulo)).read_text(encoding='utf-8'))
    pais = {}
    for no in ast.walk(arvore):
        for filho in ast.iter_child_nodes(no):
            pais[filho] = no

    def funcao_de(no):
        while no in pais:
            no = pais[no]
            if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return no.name
        return None

    saida = []
    for no in ast.walk(arvore):
        alvos = []
        if isinstance(no, ast.keyword) and no.arg == 'o_que_fazer':
            alvos.append(no.value)
        elif isinstance(no, ast.Dict):
            alvos += [v for k, v in zip(no.keys, no.values)
                      if isinstance(k, ast.Constant) and k.value == 'o_que_fazer']
        elif isinstance(no, ast.Assign):
            nomes = [t.id for t in no.targets if isinstance(t, ast.Name)]
            if any(re.match(r'(O_QUE_FAZER|FIM)', n) for n in nomes):
                if any(n in CONSTANTES_SO_DO_CLAUDE for n in nomes):
                    continue
                alvos.append(no.value)
        for alvo in alvos:
            if funcao_de(alvo) in SO_DO_CLAUDE:
                continue
            for s in _strings(alvo):
                saida.append(('%s:%d' % (modulo.__name__, getattr(alvo, 'lineno', 0)), s))
    return saida


@pytest.mark.parametrize('modulo', [humano, tela, mod_fases, nucleo], ids=lambda m: m.__name__)
def test_codigo_sem_o_que_fazer_com_comando_de_terminal(modulo):
    achados = [(r, s, _problemas(s)) for r, s in _o_que_fazer_do_codigo(modulo) if _problemas(s)]
    assert achados == []


def test_a_varredura_acha_um_comando_de_terminal():
    """A varredura pega o caso que ela existe para pegar (e nao passa em branco por um texto que mudou de forma)."""
    assert 'comando entre aspas' in _problemas('Rode "desdobra job proxima".')
    assert 'terminal' in _problemas('Abra um terminal próprio.')
    assert 'opcao de linha de comando' in _problemas('Passe --job <pasta>.')
    assert _problemas('Peça ao Claude para abrir a tela do job.') == []
    # a varredura do nucleo ve os textos de fase e o FIM
    vistos = [s for _r, s in _o_que_fazer_do_codigo(nucleo)]
    assert any('falhou' in s for s in vistos)


# ------------------------------------------------------------------ docs
DOC = RAIZ_PLUGIN.parents[1] / 'docs' / 'm1-interfaces.md'


def test_doc_nao_diz_mais_que_o_modo_vem_do_estado_nem_que_modo_dados_e_obrigatorio():
    texto = DOC.read_text(encoding='utf-8')
    assert '`--modo-dados` é obrigatório' not in texto
    assert 'O modo do envelope é o `modo_dados` do `estado.json`' not in texto
    assert '## M7c, K5' in texto


# ------------------------------------------------------------------ revisao do K5: a recusa inteira, o doctor e as skills
# A recusa de um ato so do DA (o envelope que o Claude recebe quando tenta um deles) leva o o_que_fazer e as linhas
# humanas. As duas partes chegam ao DA juntas e nenhuma manda ao terminal nem contradiz a outra.
class _Args:
    """Argumentos do comando: so a pasta do job; o resto e None (a recusa vem antes de qualquer outro argumento)."""

    def __init__(self, job):
        self.job = str(job)

    def __getattr__(self, nome):
        return None


def _comandos_de_recusa():
    from desdobra import briefing, entrega, render, specs
    return {'render': render._render, 'linkado confirmar': render._linkado_confirmar,
            'spec confirmar': specs._confirmar, 'briefing confirmar': briefing._confirmar,
            'aprovar': entrega._aprovar, 'entregar': entrega._entregar,
            'parametros-entrega': entrega._parametros_entrega}


def test_todo_comando_humano_tem_recusa_conferida():
    assert set(_comandos_de_recusa()) == set(humano.COMANDOS)


@pytest.mark.parametrize('comando', sorted(humano.COMANDOS))
def test_recusa_do_ato_do_da_sem_terminal_e_sem_contradicao(comando, tmp_path, monkeypatch):
    from desdobra.resultado import Codigo
    monkeypatch.setattr(humano, 'console_interativo', lambda: (False, 'sem_terminal'))
    r = _comandos_de_recusa()[comando](_Args(tmp_path))
    assert r.codigo == int(Codigo.RECUSADO) and r.situacao == 'recusado', (comando, r.o_que_fazer)
    for texto in [r.o_que_fazer] + list(r.linhas_humanas):
        assert _problemas(texto) == [], (comando, texto)
    if comando in humano.ATOS_SEM_BOTAO:
        # a tela ainda nao tem este ato (M8): o texto nao promete um clique que o DA nao acha
        assert 'clique seu na tela' not in r.o_que_fazer and 'próximo marco' in r.o_que_fazer, r.o_que_fazer
    else:
        assert r.o_que_fazer == humano.O_QUE_FAZER


def test_atos_sem_botao_sao_os_que_a_tela_nao_tem():
    from desdobra.tela import atos
    fonte = inspect.getsource(atos)
    assert set(humano.ATOS_SEM_BOTAO) <= set(humano.COMANDOS)
    for comando in humano.ATOS_SEM_BOTAO:
        assert "'%s'" % comando not in fonte, comando
    assert humano.o_que_fazer('render') == humano.O_QUE_FAZER
    assert humano.o_que_fazer('entregar') == humano.O_QUE_FAZER_SEM_BOTAO


def test_verificacao_quebrada_do_doctor_nao_manda_ao_terminal():
    from desdobra.doctor import _quebrou
    t = _quebrou('x', RuntimeError()).o_que_fazer
    assert _problemas(t) == [] and 'Claude' in t, t


SKILLS = RAIZ_PLUGIN / 'skills'


def test_skills_nao_dizem_que_o_texto_final_do_motor_cita_terminal():
    for rel in ('continuar/SKILL.md', 'novo-job/SKILL.md', 'novo-job/references/fluxo.md'):
        texto = (SKILLS / rel).read_text(encoding='utf-8')
        assert 'cita atos do DA pelo terminal' not in texto, rel
        assert 'com comandos de terminal' not in texto, rel
    # M7c, ajuste terminal: o o_que_fazer cita skill, e nao comando
    for rel in ('continuar/SKILL.md', 'novo-job/SKILL.md', 'novo-job/references/regras-do-modelo.md'):
        texto = (SKILLS / rel).read_text(encoding='utf-8')
        assert 'cita comandos do desdobra' not in texto and 'cita uma skill do desdobra' in texto, rel
    assert 'porque ele fala de terminal' not in (SKILLS / 'ler-spec' / 'SKILL.md').read_text(encoding='utf-8')


def test_skill_doctor_nao_manda_o_da_ao_terminal():
    texto = (SKILLS / 'doctor' / 'SKILL.md').read_text(encoding='utf-8')
    assert 'Peça ao DA para rodar' not in texto
    assert not re.search(r'\bno terminal\b', texto)


# ------------------------------------------------------------------ M7c, ajuste terminal: todo texto do motor
# Resposta do Duda ao ponto 8 (13/11): nenhum texto que o motor pode pôr num envelope (o_que_fazer, linhas humanas,
# mensagem de erro, FIM, recusa, verificação do doctor) manda alguém rodar comando de terminal. Ato do DA com botão é
# clique dele na tela; ato sem botão segue humano.O_QUE_FAZER_SEM_BOTAO; passo do Claude cita a skill ou "peça ao
# Claude"; erro de uso explica o argumento sem comando. Comando fica só no --help do argparse, nos docs, nos testes e
# nos comentários.
MOTOR = RAIZ_PLUGIN / 'motor' / 'desdobra'
COMANDO_DE_TERMINAL = (
    ('subcomando do motor', re.compile(r'\bdesdobra\s+(?:job|spec|specs|validar|render|aprovar|entregar|'
                                       r'parametros-entrega|briefing|ds|fontes|derivar|doctor|conferir-entrega|tela|'
                                       r'ler|sugestao|linkado|marca|regressao|limites|laudo|cor)\b', re.I)),
    ('comando entre aspas', re.compile(r'"\s*desdobra\s', re.I)),
    ('subcomando entre aspas', re.compile(r'"(?:job|spec|briefing|derivar|render|aprovar|entregar|parametros-entrega|'
                                          r'ler|fontes|ds|sugestao|linkado|doctor|tela|conferir-entrega|validar)'
                                          r'(?:\s[^"]*)?"')),
    ('python -m', re.compile(r'\b(?:python[\d.]*|py)(?:\.exe)?\s+-[mIB]', re.I)),
    # M7c, ajuste terminal-2 (revisão dos textos, defeito 2): o motor entre aspas simples, o cmd e o verbo de comando
    ('motor entre aspas', re.compile(r'[\'‘’]\s*desdobra\b', re.I)),
    ('cmd', re.compile(r'\bcmd(?:\.exe)?\b', re.I)),
    ('execute o comando', re.compile(r'\bexecut(?:e|em)\b|\bcham(?:e|em)\s+(?:o\s+|um\s+)?(?:comando|motor|desdobra|'
                                     r'script|programa)\b', re.I)),
    ('opcao de linha de comando', re.compile(r'(?<![\w-])--[a-z]', re.I)),
    ('no terminal', re.compile(r'\b(?:no|num|ao|pelo|em\s+um|de\s+um)\s+terminal\b|\bterminal\s+(?:próprio|interativo)'
                               r'|\babr[aei]\w*\s+(?:um|o)\s+terminal', re.I)),
    ('rode', re.compile(r'\b(?:rode|rodem|rodar|digite|digitar)\b', re.I)),
    ('linha de comando', re.compile(r'linha de comando', re.I)),
    ('prompt de comando', re.compile(r'prompt de comando', re.I)),
    ('powershell', re.compile(r'powershell', re.I)),
    ('marcador de pasta', re.compile(r'<pasta(?: do job)?>', re.I)),
)
# o nome de uma opção sozinho: argv de processo filho e nome de opção do argparse, nunca prosa
OPCAO_SOZINHA = re.compile(r'--[a-z][a-z0-9-]*(?:=.*)?', re.S)
# uma palavra só, sem espaço: valor de enum ou chave (o meio 'terminal', a ação 'digitar'), nunca prosa
IDENTIFICADOR = re.compile(r'[a-z_]+')
# argumentos do argparse que são o --help do comando (o lugar onde o comando pode ficar)
ARGS_DO_HELP = ('help', 'description', 'epilog', 'usage', 'metavar', 'prog', 'version')
# o console interativo do DA (humano.exigir): pergunta e saída de quem já está num console próprio. Nunca vai a
# envelope nem ao Claude: o envelope recusa o ato antes (humano.exigir), e a tela não usa o console
CHAMADAS_DO_CONSOLE = ('ler', 'perguntar', 'saida', 'input')
CONSTANTES_DO_CONSOLE = re.compile(r'PERGUNTA')
# erros de uso de comandos que só o Claude, os testes ou a Trezion rodam: o texto explica o argumento errado pelo nome
# da opção, sem comando. (arquivo relativo a motor/desdobra, texto exato) -> motivo
_CRIAR = 'erro de uso do job criar, que só a skill novo-job roda; o DA nunca vê o argumento'
_REGRESSAO = 'erro de uso da regressão, que só a Trezion roda sobre o corpus dela'
_ACERTO = 'erro de uso do sugestao acerto, que só a Trezion e os testes rodam com o gabarito'
USO_PELO_NOME_DA_OPCAO = {
    ('job/nucleo.py', 'Tire os arquivos de fonte e os pacotes com fontes dessa pasta e passe as fontes soltas (OTF, '
                      'TTF, TTC, WOFF ou WOFF2) em --fontes, e crie o job de novo.'): _CRIAR,
    ('job/nucleo.py', 'Confira o caminho passado em --kv.'): _CRIAR,
    ('job/nucleo.py', 'Passe em --kv o arquivo .psd ou .psb salvo pelo Photoshop.'): _CRIAR,
    ('job/nucleo.py', 'Um dos caminhos de --fontes não foi encontrado.'): _CRIAR,
    ('job/nucleo.py', 'Confira o nome do arquivo, com a mesma caixa (maiúsculas e minúsculas) do que foi passado em '
                      '--fontes.'): _CRIAR,
    ('job/nucleo.py', 'Confira os caminhos passados em --fontes.'): _CRIAR,
    ('regressao/__init__.py', 'Nenhum PSD ou PSB foi achado no corpus. Confira a pasta passada em --corpus.'):
        _REGRESSAO,
    ('regressao/__init__.py', 'A pasta de saída fica dentro do repositório do plugin, e o relatório da regressão leva '
                              'os nomes dos arquivos do corpus. Passe em --saida uma pasta fora do repositório.'):
        _REGRESSAO,
    ('regressao/__init__.py', 'A pasta do corpus não existe. Confira o caminho passado em --corpus.'): _REGRESSAO,
    ('regressao/__init__.py', 'A pasta da linha de base não existe. Confira o caminho passado em --linha-de-base.'):
        _REGRESSAO,
    ('regressao/__init__.py', 'O valor de --paralelo tem de ser 1 ou mais.'): _REGRESSAO,
    ('sugestao/__init__.py', 'O job não tem briefing gravado. Sem --gabarito, a medida é contra o briefing salvo na '
                             'tela.'): _ACERTO,
    ('sugestao/__init__.py', 'O gabarito não se lê ou não tem a forma da ficha (kvs com respostas de layer_id e '
                             'funcao). Confira o arquivo passado em --gabarito.'): _ACERTO,
    ('sugestao/__init__.py', 'Nenhum KV do gabarito tem o sha256 do PSD deste job. Passe em --corpus a pasta dos PSD '
                             'do gabarito, ou ponha o sha256 no KV do gabarito.'): _ACERTO,
}


def _comando_de_terminal(texto):
    achados = [nome for nome, rx in COMANDO_DE_TERMINAL if rx.search(texto)]
    # o subcomando solto, sem o prefixo desdobra e sem aspas ("job proxima", "conferir-entrega"): o nome de cada
    # comando de mais de uma palavra ou com hífen sai do próprio analisador do motor (revisão dos textos, defeito 2).
    # O texto que é só o nome do comando é o campo comando do envelope ou o argumento de humano.exigir, nunca prosa
    if _SUBCOMANDO_SOLTO().search(texto) and not _SUBCOMANDO_SOLTO().fullmatch(texto.strip()):
        achados.append('subcomando solto')
    return achados


_CACHE_SUBCOMANDO = []


def _SUBCOMANDO_SOLTO():
    if not _CACHE_SUBCOMANDO:
        from desdobra import cli
        nomes = {' '.join(n) for n, _s in _folhas(cli.montar_analisador()) if n}
        nomes |= {n[0] for n in (x.split() for x in nomes) if '-' in n[0]}
        compostos = sorted((n for n in nomes if ' ' in n or '-' in n), key=len, reverse=True)
        _CACHE_SUBCOMANDO.append(re.compile(r'(?<![\w/:-])(?:%s)(?![\w/-])' % '|'.join(
            r'\s+'.join(map(re.escape, n.split())) for n in compostos), re.I))
    return _CACHE_SUBCOMANDO[0]


def _excluidos(arvore):
    """ids dos nós de string que não vão a envelope: docstring, --help do argparse, nome de opção (add_argument e
    argv), console interativo e o bloco de script de desenvolvimento (if __name__ == '__main__')."""
    fora = set()

    def tudo(no):
        fora.update(id(n) for n in ast.walk(no))

    for no in ast.walk(arvore):
        if isinstance(no, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and no.body:
            p = no.body[0]
            if isinstance(p, ast.Expr) and isinstance(p.value, ast.Constant) and isinstance(p.value.value, str):
                fora.add(id(p.value))
        if isinstance(no, ast.keyword) and no.arg in ARGS_DO_HELP:
            tudo(no.value)
        if isinstance(no, ast.Call):
            nome = getattr(no.func, 'attr', None) or getattr(no.func, 'id', None)
            if nome in ('add_argument', 'add_parser', 'add_mutually_exclusive_group'):
                for a in no.args:
                    tudo(a)
            if nome in CHAMADAS_DO_CONSOLE:
                for a in no.args:
                    tudo(a)
        if isinstance(no, ast.Assign) and any(isinstance(t, ast.Name) and CONSTANTES_DO_CONSOLE.search(t.id)
                                              for t in no.targets):
            tudo(no.value)
        if (isinstance(no, ast.If) and isinstance(no.test, ast.Compare) and isinstance(no.test.left, ast.Name)
                and no.test.left.id == '__name__'):
            tudo(no)
    return fora


def _textos_do_codigo(fonte, rel):
    """(rel:linha, texto) de cada constante de texto do módulo que pode ir a um envelope."""
    arvore = ast.parse(fonte)
    fora = _excluidos(arvore)
    saida = []
    for no in ast.walk(arvore):
        if not (isinstance(no, ast.Constant) and isinstance(no.value, str)) or id(no) in fora:
            continue
        if OPCAO_SOZINHA.fullmatch(no.value) or IDENTIFICADOR.fullmatch(no.value):
            continue
        if USO_PELO_NOME_DA_OPCAO.get((rel, no.value)):
            continue
        saida.append(('%s:%d' % (rel, no.lineno), no.value))
    # o texto montado por + ou % (ou f-string) a partir de pedaços que passam sozinhos: a varredura dobra a montagem,
    # com o valor das constantes de texto do módulo, e um pedaço que só se sabe em tempo de execução vira um espaço
    # (revisão dos textos, defeito 2)
    constantes = {t.id: n.value.value for n in arvore.body if isinstance(n, ast.Assign)
                  and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)
                  for t in n.targets if isinstance(t, ast.Name)}
    montagens = [no for no in ast.walk(arvore) if _montagem(no)]
    dentro = {id(f) for no in montagens for f in ast.iter_child_nodes(no)}
    for no in montagens:
        if id(no) in dentro or id(no) in fora:
            continue
        texto = _dobrar(no, constantes)
        if texto is not None and not USO_PELO_NOME_DA_OPCAO.get((rel, texto)):
            saida.append(('%s:%d (montado)' % (rel, no.lineno), texto))
    return saida


def _montagem(no):
    return isinstance(no, ast.JoinedStr) or (isinstance(no, ast.BinOp) and isinstance(no.op, (ast.Add, ast.Mod)))


def _dobrar(no, constantes, fundo=True):
    """O texto que a montagem dá, ou None quando ela não é de texto; o pedaço desconhecido vira um espaço."""
    if isinstance(no, ast.Constant):
        return no.value if isinstance(no.value, str) else None
    if isinstance(no, ast.Name):
        return constantes.get(no.id, None if fundo else ' ')
    if isinstance(no, ast.JoinedStr):
        return ''.join(_dobrar(v, constantes, False) or ' ' for v in no.values)
    if isinstance(no, ast.FormattedValue):
        return _dobrar(no.value, constantes, False) or ' '
    if isinstance(no, ast.BinOp) and isinstance(no.op, ast.Add):
        a, b = _dobrar(no.left, constantes), _dobrar(no.right, constantes)
        if a is None and b is None:
            return None
        return (a if a is not None else ' ') + (b if b is not None else ' ')
    if isinstance(no, ast.BinOp) and isinstance(no.op, ast.Mod):
        modelo = _dobrar(no.left, constantes)
        if modelo is None:
            return None
        partes = no.right.elts if isinstance(no.right, ast.Tuple) else [no.right]
        try:
            return modelo % tuple(_dobrar(p, constantes, False) or ' ' for p in partes)
        except (TypeError, ValueError, KeyError):
            return modelo
    return None


MODULOS_DO_MOTOR = sorted(p.relative_to(MOTOR).as_posix() for p in MOTOR.rglob('*.py')
                          if '__pycache__' not in p.parts)


def _achados_no_modulo(rel):
    fonte = (MOTOR / rel).read_text(encoding='utf-8')
    return [(onde, texto, _comando_de_terminal(texto)) for onde, texto in _textos_do_codigo(fonte, rel)
            if _comando_de_terminal(texto)]


@pytest.mark.parametrize('rel', MODULOS_DO_MOTOR)
def test_nenhum_texto_do_motor_manda_ao_terminal(rel):
    assert _achados_no_modulo(rel) == []


def test_varredura_do_motor_ve_todos_os_modulos():
    assert len(MODULOS_DO_MOTOR) > 100
    for rel in ('cli.py', 'humano.py', 'ds/__init__.py', 'entrega/validar.py', 'render/execucao.py',
                'doctor/verificacoes.py', 'sugestao/envelope.py'):
        assert rel in MODULOS_DO_MOTOR, rel


def test_uso_pelo_nome_da_opcao_so_tem_texto_que_existe_e_sem_comando():
    """A lista de erros de uso aceitos não guarda texto velho nem texto que cite comando ou terminal."""
    for (rel, texto), motivo in USO_PELO_NOME_DA_OPCAO.items():
        assert motivo, (rel, texto)
        fonte = (MOTOR / rel).read_text(encoding='utf-8')
        vistos = [v.value for v in ast.walk(ast.parse(fonte)) if isinstance(v, ast.Constant)]
        assert texto in vistos, (rel, texto)
        assert _comando_de_terminal(texto) == ['opcao de linha de comando'], (rel, texto)


RUINS = (
    'Rode "desdobra job proxima".',
    'Rode o "desdobra derivar" de novo.',
    'desdobra spec confirmar --job X',
    'Confira com "job estado".',
    'python -m desdobra doctor',
    'Passe --job.',
    'Peça ao DA para rodar o comando, num terminal próprio.',
    'O render só parte de uma pessoa num terminal interativo.',
    'Veja a lista no terminal.',
    'Abra um terminal e confira.',
    'Rode a leitura de novo.',
    'Digite os valores.',
    'Use a linha de comando.',
    'Abra o Prompt de Comando.',
    'Abra o PowerShell.',
    'Grave em <pasta>.',
    # os pontos cegos achados na revisão dos textos (defeito 2)
    'Execute o comando job proxima de novo.',
    'Chame conferir-entrega na pasta do job.',
    'py -m desdobra doctor',
    'python3.12 -m desdobra doctor',
    'Abra o cmd e execute o motor.',
    "Rode 'desdobra' de novo.",
    'Confira com spec importar.',
)
BONS = (
    'Isto é um clique seu na tela do desdobra. Peça ao Claude para abrir a tela do job.',
    'Peça ao Claude para seguir o job (/desdobra:continuar).',
    'Peça ao Claude para conferir a instalação do desdobra (/desdobra:doctor).',
    'O comando veio do painel de terminal do app do Claude.',
    'O sistema não deixou ler os processos pais deste terminal.',
    'A leitura roda no processo isolado.',
    'O "Salvar e seguir" grava o briefing.',
    'Peça ao Claude para seguir o job (/desdobra:continuar) e abrir a tela do desdobra.',
    'job proxima',
)


def test_autoteste_da_varredura_do_motor():
    """A varredura acha o caso ruim e deixa passar o bom, e o excluído é só o que nunca vai a envelope."""
    for ruim in RUINS:
        assert _comando_de_terminal(ruim), ruim
    for bom in BONS:
        assert _comando_de_terminal(bom) == [], bom
    fonte = '\n'.join((
        '"""Docstring: desdobra job proxima --job <pasta>."""',
        'import argparse',
        'O_QUE_FAZER_X = \'Rode "desdobra job proxima".\'',
        'PERGUNTA_X = "Digite sim para gravar: "',
        'def f(p, humano, R):',
        '    """desdobra render --job <pasta>"""',
        '    p.add_argument("--job", help="Rode desdobra job criar antes")',
        '    humano.ler("Digite sim: ")',
        '    argv = ["--orcamento-bytes", "10"]',
        '    return R(o_que_fazer="Confira no terminal.", linhas_humanas=["Passe --job <pasta>."])',
        'O_QUE_FAZER_Y = "Confira com " + "job" + " estado."',
        'OPC = "--job"',
        'Z = "Passe %s." % OPC',
        'W = f"Rode {OPC} de novo"',
        'if __name__ == "__main__":',
        '    print("uso: python -m desdobra.x --gravar")',
    ))
    achados = [(o, t) for o, t in _textos_do_codigo(fonte, 'x.py') if _comando_de_terminal(t)]
    assert sorted(t for _o, t in achados) == sorted(['Rode "desdobra job proxima".', 'Confira no terminal.',
                                                     'Passe --job <pasta>.', 'Rode ', 'Confira com job estado.',
                                                     'Passe --job.', 'Rode --job de novo'])


# o envelope de cada comando do motor, numa pasta que não é job (as recusas de entrada de todos os comandos), com o
# console recusado (as recusas de ato só do DA). Ficam de fora os comandos que fazem trabalho de verdade fora de um job
FORA_DO_ENVELOPE_EM_PASTA_VAZIA = {
    'doctor': 'confere a instalação de verdade (Chromium, isolador); o texto de cada verificação passa pela varredura '
              'do código e o _quebrou tem teste próprio',
    'regressao': 'roda o corpus da Trezion; os textos passam pela varredura do código',
    'job criar': 'cria a pasta do job; os erros de uso passam pela varredura do código',
}


def _folhas(analisador, prefixo=()):
    import argparse
    for acao in analisador._actions:
        if isinstance(acao, argparse._SubParsersAction):
            for nome, sub in acao.choices.items():
                yield from _folhas(sub, prefixo + (nome,))
            return
    yield prefixo, analisador


def _argv_minimo(analisador, pasta):
    import argparse
    argv = []
    do_grupo = {id(g._group_actions[0]) for g in analisador._mutually_exclusive_groups if g.required}
    for acao in analisador._actions:
        if isinstance(acao, (argparse._HelpAction, argparse._VersionAction)):
            continue
        valor = list(acao.choices)[0] if acao.choices else ('f1' if acao.dest == 'formato' else str(pasta))
        if not acao.option_strings:
            if acao.nargs == argparse.REMAINDER:
                continue
            argv.append(valor)
        elif acao.required or id(acao) in do_grupo:
            argv += [acao.option_strings[0], valor]
    return argv


def _comandos_do_motor():
    from desdobra import cli
    return [(' '.join(nome), sub) for nome, sub in _folhas(cli.montar_analisador()) if nome]


COMANDOS_DO_MOTOR = _comandos_do_motor()


@pytest.mark.parametrize('nome', [n for n, _s in COMANDOS_DO_MOTOR])
def test_envelope_de_cada_comando_numa_pasta_vazia_sem_terminal(nome, tmp_path, monkeypatch, capsys):
    import json
    from desdobra import cli
    if nome in FORA_DO_ENVELOPE_EM_PASTA_VAZIA or nome.split()[0] in FORA_DO_ENVELOPE_EM_PASTA_VAZIA:
        pytest.skip(FORA_DO_ENVELOPE_EM_PASTA_VAZIA.get(nome) or FORA_DO_ENVELOPE_EM_PASTA_VAZIA[nome.split()[0]])
    monkeypatch.setattr(humano, 'console_interativo', lambda: (False, 'sem_terminal'))
    monkeypatch.setenv('CLAUDE_PLUGIN_DATA', str(tmp_path / 'dados'))
    pasta = tmp_path / 'vazia'
    pasta.mkdir()
    sub = dict(COMANDOS_DO_MOTOR)[nome]
    capsys.readouterr()
    cli.principal(['--envelope'] + nome.split() + _argv_minimo(sub, pasta))
    env = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    # o argv mínimo é aceito pelo argparse: o envelope é o do próprio comando, e não o do erro de argumento
    assert env['comando'] != 'desdobra', (nome, env)
    assert _comando_de_terminal(env['o_que_fazer'] or '') == [], (nome, env['o_que_fazer'])
    assert _comando_no_envelope(env, pasta) == [], (nome, env)


# campos do envelope que não são prosa: o nome do comando, a fase, a situação e os caminhos
CAMPOS_FORA_DA_PROSA = ('comando', 'fase', 'situacao', 'pasta_job', 'esquema', 'versao')


def _comando_no_envelope(env, pasta=None):
    """Todo texto do envelope inteiro (o_que_fazer, linhas humanas, erro e o que mais vier), não só o o_que_fazer
    (revisão dos textos, defeito 2). O caminho da pasta do teste sai do texto antes da varredura."""
    achados = []

    def andar(valor, chave):
        if isinstance(valor, dict):
            for k, v in valor.items():
                if k not in CAMPOS_FORA_DA_PROSA:
                    andar(v, k)
        elif isinstance(valor, list):
            for v in valor:
                andar(v, chave)
        elif isinstance(valor, str):
            texto = valor.replace(str(pasta), 'PASTA') if pasta else valor
            if _comando_de_terminal(texto):
                achados.append((chave, valor, _comando_de_terminal(texto)))

    andar(env, None)
    return achados


def test_a_varredura_do_envelope_olha_todos_os_campos():
    env = {'comando': 'job proxima', 'o_que_fazer': 'Peça ao Claude para seguir o job (/desdobra:continuar).',
           'linhas_humanas': ['Rode "desdobra job proxima".'], 'erro': {'mensagem': 'Passe --job.'}}
    assert [c for c, _v, _p in _comando_no_envelope(env)] == ['linhas_humanas', 'mensagem']


def test_envelope_do_erro_de_argumento_e_do_erro_interno_sem_terminal(capsys, monkeypatch):
    import json
    from desdobra import cli
    capsys.readouterr()
    cli.principal(['--envelope', 'nao-existe'])
    env = json.loads(capsys.readouterr().out.strip())
    assert env['codigo'] == 2 and _comando_de_terminal(env['o_que_fazer']) == [], env
    assert _comando_no_envelope(env) == [], env

    def quebra(args):
        raise RuntimeError('x')

    monkeypatch.setattr(cli, '_executar', quebra)
    cli.principal(['--envelope', 'job', 'estado', 'x'])
    env = json.loads(capsys.readouterr().out.strip())
    assert env['codigo'] == 1 and _comando_de_terminal(env['o_que_fazer']) == [], env
    assert _comando_no_envelope(env) == [], env


# ------------------------------------------------------------------ M7c, ajuste terminal-2 (revisão dos textos)
# Defeito 1: a página sem texto de uma folha de spec ainda não tem botão na tela (tela/estado.py, faltam). O envelope
# de spec importar não promete um clique que o DA não acha: confirmar e escolher a leitura são cliques dele na tela
# ("Valores de spec", no passo 1), e o valor da página sem texto segue o estilo de humano.O_QUE_FAZER_SEM_BOTAO
def _spec_importar(tmp_path, monkeypatch, recortes, confirmados=0):
    import argparse
    from desdobra import specs
    from desdobra.specs import importar
    pasta = tmp_path / 'job'
    pasta.mkdir()
    (pasta / 'estado.json').write_text('{}', encoding='utf-8')
    resumo = {'folhas': 1, 'formatos': 1, 'valores_rascunho': 2, 'valores_confirmados': confirmados,
              'divergencias': 0, 'recortes': recortes}
    formatos = {'formatos': [{'id': 'f1'}] if confirmados else []}
    monkeypatch.setattr(importar, 'importar', lambda _p: ({'resumo': resumo}, formatos, {'folhas_recusadas': 0}))
    return specs._importar(argparse.Namespace(job=str(pasta)))


def _frases(texto):
    return [f for f in re.split(r'(?<=[.:;])\s+', texto) if f]


@pytest.mark.parametrize('confirmados', [0, 1])
def test_spec_importar_com_pagina_sem_texto_nao_promete_clique(tmp_path, monkeypatch, confirmados):
    from desdobra.tela import estado
    r = _spec_importar(tmp_path, monkeypatch, recortes=2, confirmados=confirmados)
    assert r.situacao == 'ok'
    promete = [f for f in _frases(r.o_que_fazer) if 'sem texto' in f and re.search(r'clique|botão d|na tela', f)
               and 'ainda não têm botão' not in f]
    assert promete == [], r.o_que_fazer
    assert 'ainda não têm botão na tela' in r.o_que_fazer, r.o_que_fazer
    # a tela diz o mesmo no que falta do passo 1
    lido = {'modo_dados': {'escolhido': 'c'}, 'bloqueios': [], 'paradas': [], 'camadas_bloqueadas': [],
            'linkados': [], 'quadros': [], 'fontes_que_faltam': [],
            'specs': {'recortes': 2, 'pendentes': 0, 'folhas': 1, 'formatos': [{'id': 'f1', 'rotacao': 0}]}}
    assert any('ainda não têm botão na tela' in i['texto'] for i in estado.faltam(lido, {}))
    assert _comando_de_terminal(r.o_que_fazer) == []


def test_spec_importar_sem_pagina_sem_texto_nao_fala_dela(tmp_path, monkeypatch):
    from desdobra import specs
    r = _spec_importar(tmp_path, monkeypatch, recortes=0)
    assert r.o_que_fazer == specs.O_QUE_FAZER_PENDENTE and 'sem texto' not in r.o_que_fazer
    assert 'cliques dele na tela' in r.o_que_fazer


def test_skills_nao_prometem_digitar_o_valor_da_pagina_sem_texto_na_tela():
    for rel in ('skills/ler-spec/SKILL.md', 'skills/novo-job/references/fluxo.md'):
        texto = (RAIZ_PLUGIN / rel).read_text(encoding='utf-8')
        assert 'ainda não têm botão na tela' in texto, rel
        for linha in texto.splitlines():
            if 'sem texto' in linha and re.search(r'digit', linha):
                assert 'ainda não têm botão' in linha, (rel, linha)
