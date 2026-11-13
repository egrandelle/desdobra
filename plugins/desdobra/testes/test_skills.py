# -*- coding: utf-8 -*-
"""M7c, K6: as regras que valem para todas as skills, varridas em todo skills/*/SKILL.md e skills/*/references/**.

Cada regra e uma funcao que devolve a lista do que achou num texto (vazia quando o texto segue a regra). O mesmo
conjunto roda em dois lugares:
  1. nas skills de verdade, onde cada regra tem de achar 0;
  2. na autoverificacao, com textos de skill ruins escritos aqui (inventados), onde cada regra tem de achar a violacao
     dela. Uma regra que nao pega o caso ruim e uma regra quebrada, e o teste fica vermelho.

As regras (plano do M7c, passo K6; arquitetura-v1.md, 3.5; decisoes-v1.md, 159, 162, 170 e 190):
  - SKILL.md e referencias abaixo de 500 linhas;
  - sem caminho relativo do plugin nem bin/; o Python do desdobra so pelo interpretador.json (o "PY");
  - toda chamada do motor com --teto-modo-dados TETO, o TETO vindo de ${user_config.teto_modo_dados};
  - nenhuma chamada de ato do DA (render, aprovar, entregar, confirmar, parametros-entrega e os atos da tela) e
    nenhuma instrucao ao DA para rodar um deles ou abrir terminal;
  - nenhum pedido de caminho relativo (todo caminho pedido ao DA e absoluto);
  - nenhuma pergunta ao DA, nem escolha pelo DA, de modo, teto, valor, limite ou regra;
  - a regra "nunca leia a biblioteca da agencia" onde a skill toca a biblioteca, e nenhuma instrucao para le-la;
  - o caso de ${user_config.biblioteca_agencia} vazio tratado: --biblioteca "BIBLIOTECA" sempre entre aspas, o
    marcador uma vez so (sem guarda que o cite), o texto do caso vazio e nada que mande tirar a opcao;
  - sugerir-funcoes com disable-model-invocation: false;
  - nenhuma palavra de DESDOBRA_PALAVRAS_PROIBIDAS (a lista mora fora do repositorio; sem a variavel, pula);
  - cada skill da tabela 3.5 existe.
E, pelo conserto do gancho na leva 4 (MOTOR_GERAL aceita -I -B), toda linha do motor de toda skill passa pelo gancho
(decidir_com_motivo) num job sintetico, pela Bash e pela PowerShell, e e aceita pelo analisador do motor.
"""
import importlib.util
import json
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from desdobra import biblioteca, cli, humano
from test_pacote import compilar_palavras, palavras_de_cliente, palavras_do_ambiente

RAIZ_PLUGIN = Path(__file__).resolve().parents[1]
SKILLS = RAIZ_PLUGIN / 'skills'
GANCHO = RAIZ_PLUGIN / 'scripts' / 'gancho_confirmacoes.py'
# arquitetura-v1.md, 3.5 (tabela das skills)
SKILLS_DA_TABELA = ('novo-job', 'continuar', 'doctor', 'sugerir-funcoes', 'ler-spec')
MARCADOR_TETO = '${user_config.teto_modo_dados}'
MARCADOR_BIBLIOTECA = '${user_config.biblioteca_agencia}'
LIMITE_DE_LINHAS = 500  # numero-neutro: limite do plano do M7c, K6 ("abaixo de 500 linhas")
# os atos so do DA: os comandos de terminal (humano.COMANDOS), os botoes da tela (humano.ATOS_DA_TELA) e o registro da
# marca (M7c, M5), que so existe como botao
ATOS_DO_DA = tuple(dict.fromkeys(humano.COMANDOS + humano.ATOS_DA_TELA + ('marca registrar', 'confirmar')))
# os nomes que as linhas do motor usam no lugar dos valores (o Claude troca pelo que leu ou recebeu)
MARCADORES_DAS_LINHAS = ('PY', 'TETO', 'PASTA', 'PSD', 'FONTE1', 'FONTE2', 'SPECS', 'NOME', 'ARQUIVO', 'VEICULADOR',
                         'BIBLIOTECA')


# ------------------------------------------------------------------ leitura das skills
def arquivos_das_skills(raiz=SKILLS):
    """{skill: [SKILL.md, references/**]} de cada pasta de skill."""
    saida = {}
    for pasta in sorted(p for p in raiz.iterdir() if p.is_dir()):
        arquivos = [pasta / 'SKILL.md'] if (pasta / 'SKILL.md').is_file() else []
        refs = pasta / 'references'
        if refs.is_dir():
            arquivos += sorted(a for a in refs.rglob('*') if a.is_file())
        saida[pasta.name] = arquivos
    return saida


def _ler(arquivo):
    # com core.autocrlf, a copia de trabalho pode sair com CRLF; a regra de fim de linha confere o indice do git
    return arquivo.read_text(encoding='utf-8')


def _rel(arquivo):
    return arquivo.relative_to(RAIZ_PLUGIN).as_posix()


def frontmatter(texto):
    m = re.match(r'---\n(.*?)\n---\n', texto, re.S)
    if not m:
        return None
    return {k.strip(): v.strip() for k, v in (l.split(':', 1) for l in m.group(1).splitlines() if ':' in l)}


# ------------------------------------------------------------------ pecas do texto
# toda chamada do Python do desdobra, em qualquer forma (-m, -c com import, o PY entre aspas): a forma certa e conferida
# pela regra do interpretador, e uma forma errada nunca escapa das regras por nao ser reconhecida como chamada
CHAMADA = re.compile(r'-m\s+desdobra\b|"PY"|\bimport\s+desdobra\b|\bfrom\s+desdobra\b|\bdesdobra\.(?:cli|__main__)\b')
SPAN = re.compile(r'`([^`\n]+)`')
CERCA = re.compile(r'^[ \t]*```.*?^[ \t]*```[ \t]*$', re.S | re.M)
NEG = r'\b(?:nunca|não|nem|jamais)\b'
# a negacao governa a palavra logo depois dela (com um artigo ou pronome curto no meio: "não o rode")
NEGACAO_DIRETA = re.compile(NEG + r'\s+(?:\w{1,4}\s+)?$', re.I)
# ou uma enumeracao so de verbos da mesma classe: "Nunca leia, liste nem copie"
NEGACAO_EM_LISTA = re.compile(NEG + r'\s+((?:[\w-]+,?\s+){1,4})$', re.I)


def comandos_do_motor(texto):
    """Cada chamada do motor do texto: o trecho entre crases que a contem ou, no bloco de codigo, a linha inteira."""
    saida = []
    for linha in texto.splitlines():
        if not CHAMADA.search(linha):
            continue
        spans = [s.strip() for s in SPAN.findall(linha) if CHAMADA.search(s)]
        saida.extend(spans or [linha.strip()])
    return saida


def prosa(texto):
    """O texto sem os blocos de codigo e sem as chamadas do motor entre crases (as chamadas tem regras proprias)."""
    sem_cerca = CERCA.sub(' ', texto)
    return SPAN.sub(lambda m: ' ' if CHAMADA.search(m.group(1)) else m.group(0), sem_cerca)


def frases(texto):
    """Frases da prosa: corta em quebra de linha e em ponto, ponto e virgula, ! e ? seguidos de espaco."""
    for linha in prosa(texto).splitlines():
        for f in re.split(r'(?<=[.;!?])\s+', linha):
            if f.strip():
                yield f


def _negado(frase, pos, verbo=None):
    """True quando uma negacao (nunca, nao, nem, jamais) governa a palavra que comeca em pos: logo antes dela, ou no
    comeco de uma enumeracao so de verbos da mesma classe (verbo). "Se a pasta não existe, peça" nao e negado."""
    antes = frase[:pos]
    if NEGACAO_DIRETA.search(antes):
        return True
    m = NEGACAO_EM_LISTA.search(antes)
    if not (m and verbo):
        return False
    palavras = [p for p in re.findall(r'[\w-]+', m.group(1)) if p.lower() not in ('e', 'ou', 'nem')]
    return bool(palavras) and all(re.fullmatch(verbo, p, re.I) for p in palavras)


def _resto(frase, pos):
    """O que vem depois da palavra, ate o fim da oracao (ponto e virgula ou fim da frase)."""
    return re.split(r';', frase[pos:], maxsplit=1)[0]


def _nao_negadas(texto, padrao):
    """As ocorrencias de padrao no texto sem negacao logo antes (ate duas palavras no meio: "não precisa de terminal")."""
    return [m for m in re.finditer(padrao, texto, re.I)
            if not re.search(NEG + r'\s+(?:[\w-]+\s+){0,2}$', texto[:m.start()], re.I)]


def _achados(frase, verbo, alvo):
    """As ocorrencias nao negadas de verbo seguidas, na mesma oracao, de alvo."""
    saida = []
    for m in re.finditer(verbo, frase, re.I):
        if _negado(frase, m.start(), verbo):
            continue
        if re.search(alvo, _resto(frase, m.end())):
            saida.append(frase.strip())
    return saida


# ------------------------------------------------------------------ regras (cada uma devolve o que achou)
def regra_tamanho(texto):
    n = len(texto.splitlines())
    return ['%d linhas' % n] if n >= LIMITE_DE_LINHAS else []


PASTAS_DO_PLUGIN = ('scripts', 'motor', 'skills', 'hooks', 'tela', 'testes', 'references', 'biblioteca-specs',
                    'plugins', 'venv', '.venv', 'bin')
CAMINHO_RELATIVO = re.compile(r'(?<![\w}\-./\\$%%])(?:\.{1,2}[/\\]|(?:%s)[/\\])'
                              % '|'.join(re.escape(p) for p in PASTAS_DO_PLUGIN))
CAMINHO_SOBE = re.compile(r'[/\\]\.\.(?=[/\\`"\'\s]|$)')
CAMINHO_FIXO = re.compile(r'(?<![\w])[A-Za-z]:[\\/]|(?<![\w}])/(?:Users|home|opt|usr|Applications)/|~[/\\]')
SCRIPT_SOLTO = re.compile(r'\bpython[\d.]*(?:\.exe)?\s+(?:-\S+\s+)*[\w./\\-]+\.py\b|\bpy(?:\.exe)?\s+[\w./\\-]+\.py\b')


def regra_caminho_relativo(texto):
    """Sem caminho relativo do plugin (python scripts/x.py, ./x, ../x, references/x sem a raiz), sem bin/ e sem caminho
    fixo da maquina: o plugin entra so por ${CLAUDE_PLUGIN_ROOT} e ${CLAUDE_PLUGIN_DATA} (3.5)."""
    achados = ['caminho relativo: %s' % m.group(0) for m in CAMINHO_RELATIVO.finditer(texto)]
    # subir de nivel depois de uma barra (${CLAUDE_PLUGIN_ROOT}/../x, sugestoes/../../x) tambem sai da raiz
    achados += ['caminho que sobe: %s' % m.group(0) for m in CAMINHO_SOBE.finditer(texto)]
    achados += ['bin/' for _ in re.finditer(r'(?<![\w-])bin[/\\]', texto)]
    achados += ['caminho fixo: %s' % m.group(0) for m in CAMINHO_FIXO.finditer(texto)]
    achados += ['script solto: %s' % m.group(0) for m in SCRIPT_SOLTO.finditer(texto)]
    return achados


INVOCACAO_SOLTA = re.compile(r'(?:^|[\s`(\'])(?:python[\d.]*|py)(?:\.exe)?(?:\s+-[A-Za-z]+)*\s+-m\s+desdobra\b|'
                             r'`desdobra(?:\.exe)?\s+(?:--|[a-z])|PYTHONPATH|\$\{CLAUDE_PLUGIN_ROOT\}[^\s`"]*'
                             r'(?:motor|venv|python)')
FORMA_DA_LINHA = re.compile(r'^(?:&\s*)?"PY"\s+-I\s+-B\s+-m\s+desdobra\s+--envelope\b')


def regra_interpretador(texto):
    """O Python do desdobra entra so pelo interpretador.json: toda chamada e '"PY" -I -B -m desdobra --envelope', e a
    skill que chama o motor diz de onde vem o PY."""
    achados = ['chamada sem o PY: %s' % m.group(0).strip() for m in INVOCACAO_SOLTA.finditer(texto)]
    comandos = comandos_do_motor(texto)
    for c in comandos:
        if not FORMA_DA_LINHA.match(c):
            achados.append('forma da linha: %s' % c)
    if comandos and not (re.search(r'\$\{CLAUDE_PLUGIN_DATA\}/interpretador\.json', texto) and
                         re.search(r'campo `python`[^\n]*\bPY\b', texto)):
        achados.append('PY sem o interpretador.json')
    return achados


def regra_teto(texto):
    """Toda chamada do motor leva --teto-modo-dados TETO, e o TETO vem da configuracao do plugin (nunca um valor
    escolhido no texto)."""
    comandos = comandos_do_motor(texto)
    achados = ['sem teto: %s' % c for c in comandos if not re.search(r'--teto-modo-dados\s+TETO(?=\s)', c)]
    if comandos and not re.search(re.escape(MARCADOR_TETO) + r'[^\n]*\bTETO\b', texto):
        achados.append('TETO sem ' + MARCADOR_TETO)
    # nada manda tirar o teto da linha. Excecao declarada: a skill cujas chamadas sao todas o doctor, que confere o
    # ambiente sem tocar dado de job e precisa rodar justamente quando o teto nao foi configurado (o motor so aceita a,
    # b ou c em --teto-modo-dados)
    so_doctor = bool(comandos) and all(DOCTOR.search(c) for c in comandos)
    if not so_doctor and TIRAR_TETO.search(texto):
        achados.append('manda tirar --teto-modo-dados: %s' % TIRAR_TETO.search(texto).group(0))
    return achados


DOCTOR = re.compile(r'--envelope\s+--teto-modo-dados\s+TETO\s+doctor\s*$')
TIRAR_TETO = re.compile(r'\b(?:tir\w*|omit\w*|remov\w*|retir\w*|apagu\w*|apag\w*|sem)\s+(?:a\s+(?:opção|parte)\s+)?`?'
                        r'--teto-modo-dados', re.I)


ATO = re.compile(r'(?<![\w/.-])(?:%s)(?![\w/.-])' % '|'.join(r'\s+'.join(re.escape(p) for p in a.split())
                                                             for a in ATOS_DO_DA), re.I)
TERMINAL = r'\bterminal\b|prompt de comando|linha de comando|\bcmd(?:\.exe)?\b|\bPowerShell\b|\bconsole\b'
PALAVRA_DE_ATO = r'\b(?:render\w*|aprov\w*|entreg\w*|confirm\w*|parametros-entrega|registr\w*)\b'
EXECUCAO = r'\b(?:rod\w*|execut\w*|digit\w*|cham\w*|comando\w*|dispar\w*)\b'
DIRIGIDO = (r'\b(?:peç\w*|pede|pedir|diga|diz|dizer|mand\w*|orient\w*|instru\w*|ensin\w*|explique|explica|indiqu\w*|'
            r'avis\w*|pass\w*|lembr\w*|sugir\w*)\b')
# o DA por qualquer nome: a sigla, o cargo por extenso, o usuario, a pessoa, ou o pronome
QUEM_E_O_DA = r'(?:(?-i:DA)|diretora?\s+de\s+arte|usuári[oa]|designer|pessoa)'
AO_DA = r'\b(?:ao|à|o|a|para\s+o|para\s+a)\s+%s\b|\b(?:a|para)\s+ele\b' % QUEM_E_O_DA
DA_FAZ = (r'(?:\b(?:o|a)\s+%s|\bele)\s+(?:\w+\s+){0,2}?(?:rod\w*|execut\w*|digit\w*|abr\w*|cham\w*|dispar\w*)\b'
          % QUEM_E_O_DA)
ABRIR_TERMINAL = r'\b(?:abr\w*|inici\w*)\s+(?:um|o|uma|a)\s+(?:novo\s+)?(?:terminal|prompt|PowerShell|cmd|console)\b'


def regra_atos_e_terminal(texto):
    """Nenhuma chamada de ato do DA e nenhuma instrucao ao DA para rodar um ato ou abrir terminal (no 159)."""
    achados = ['chamada de ato do DA: %s' % c for c in comandos_do_motor(texto) if ATO.search(c)]
    for f in frases(texto):
        for m in re.finditer(DIRIGIDO, f, re.I):
            if _negado(f, m.start(), DIRIGIDO):
                continue
            resto = _resto(f, m.end())
            alvo = re.search(AO_DA, resto)
            if not alvo:
                continue
            depois = resto[alvo.start():]
            # "Diga ao DA que ele não precisa de terminal" explica o clique: o terminal e a execucao negados nao contam
            if _nao_negadas(depois, TERMINAL) or (re.search(PALAVRA_DE_ATO, depois, re.I) and
                                                  _nao_negadas(depois, EXECUCAO)):
                achados.append('instrução ao DA: %s' % f.strip())
        for m in re.finditer(DA_FAZ, f, re.I):
            if _negado(f, m.start()) or re.search(NEG, m.group(0), re.I):
                continue
            depois = _resto(f, m.start())
            if re.search(TERMINAL, depois, re.I) or re.search(PALAVRA_DE_ATO, depois, re.I):
                achados.append('o DA roda: %s' % f.strip())
        achados += ['abrir terminal: %s' % x for x in _achados(f, ABRIR_TERMINAL, r'')]
        for s in SPAN.finditer(f):
            if ATO.search(s.group(1)) and 'desdobra' in s.group(1) and not _negado(f, s.start()):
                achados.append('comando de ato: %s' % s.group(0))
    return achados


PEDIDO = r'\b(?:peç\w*|pede|pedir|pergunt\w*|solicit\w*|aceit\w*)\b'
VERBO_DE_DAR_CAMINHO = (r'(?:inform|diz|dig|mand|envi|pass|escrev|indi|col|copi|respond|mostr|arrast|sel|apont)\w*|'
                        r'dar|dê|der')


def regra_caminho_absoluto(texto):
    """Todo caminho pedido ao DA e absoluto; nunca um pedido (nem aceite) de caminho relativo da pasta do job."""
    achados = []
    for f in frases(texto):
        for m in re.finditer(PEDIDO, f, re.I):
            if _negado(f, m.start(), PEDIDO):
                continue
            resto = _resto(f, m.end())
            # "Peça ao DA para conferir na tela o caminho" pede uma acao, nao o caminho; so conta o pedido do proprio
            # caminho ("peça o caminho", "peça ao DA para colar o caminho")
            acao = re.match(r'\s*(?:(?:%s)\s+)?(?:para|que)\s+(?:(?:ele|ela|o|a|lhe|nos)\s+)?(\w+)' % AO_DA, resto)
            if acao and not re.fullmatch(VERBO_DE_DAR_CAMINHO, acao.group(1), re.I):
                continue
            # o caminho em qualquer ponto da oracao, ou a pasta pedida como objeto direto ("Peça ao DA a pasta do job")
            pasta = re.match(r'\s*(?:(?:%s)\s+)?(?:(?:de novo|novamente|sempre|também)\s+)?(?:a|uma)\s+pasta\b' % AO_DA,
                             resto)
            if not (re.search(r'\bcaminho', resto, re.I) or pasta):
                continue
            if re.search(r'relativ', resto, re.I):
                achados.append('caminho relativo: %s' % f.strip())
            elif not re.search(r'absolut', resto, re.I):
                achados.append('caminho sem "absoluto": %s' % f.strip())
    return achados


PERGUNTA = r'\b(?:pergunt\w*|question\w*|consult\w*|AskUserQuestion)\b'
ESCOLHA_PELO_DA = r'\b(?:escolha|escolher|escolhe|decida|decidir|decide|defina|definir|define)\s+(?:\w+\s+){0,2}?pelo DA'
ASSUNTO_DO_DA = r'\b(?:modo\w*|teto\w*|valor\w*|regra\w*|limite\w*)\b'


def regra_pergunta_de_modo(texto):
    """Nenhuma pergunta ao DA, nem escolha pelo DA, de modo, teto, valor, limite ou regra (nos 162 e 170)."""
    achados = []
    for f in frases(texto):
        achados += ['pergunta: %s' % x for x in _achados(f, PERGUNTA, ASSUNTO_DO_DA)]
        for m in re.finditer(ESCOLHA_PELO_DA, f, re.I):
            if not _negado(f, m.start(), ESCOLHA_PELO_DA) and re.search(ASSUNTO_DO_DA, _resto(f, m.start()), re.I):
                achados.append('escolha pelo DA: %s' % f.strip())
        for m in re.finditer(r'\b(?:qual|quais|que)\b[^?]*' + ASSUNTO_DO_DA + r'[^?]*\?', f, re.I):
            achados.append('pergunta direta: %s' % m.group(0).strip())
        # pedir ou oferecer ao DA o valor no chat ("Peça ao DA o teto", "Ofereça ao DA as opções de modo"); "peça ao
        # DA para configurar o plugin" pede uma acao fora do chat e nao conta, a menos que a acao seja escolher ou dizer
        for m in re.finditer(PEDIDO_DE_VALOR, f, re.I):
            if _negado(f, m.start(), PEDIDO_DE_VALOR):
                continue
            resto = _resto(f, m.end())
            # o verbo dirigido: logo antes do DA ("peça ao DA") ou no comeco da oracao ("Peça o teto"); "a peça" e
            # "o DA pede" nao sao pedido
            if not (re.match(r'\s*(?:%s)' % AO_DA, resto) or
                    re.search(r'(?:^|[,:;(]|\b(?:e|então|depois))\s*(?:[-*]\s*)?$', f[:m.start()])):
                continue
            acao = re.match(r'\s*(?:(?:%s)\s+)?(?:para|que)\s+(?:(?:ele|ela|o|a|lhe)\s+)?(\w+)' % AO_DA, resto)
            if acao and not re.fullmatch(VERBO_DE_ESCOLHA, acao.group(1), re.I):
                continue
            if re.search(ASSUNTO_DO_DA, resto, re.I) and not re.search(NA_TELA, resto, re.I):
                achados.append('pedido de valor: %s' % f.strip())
        # deixar o DA escolher, aqui no chat ("Deixe o DA escolher o modo"); na tela, a escolha e dele (no 170)
        for m in re.finditer(DEIXAR_O_DA_ESCOLHER, f, re.I):
            if _negado(f, m.start()):
                continue
            resto = _resto(f, m.start())
            if re.search(ASSUNTO_DO_DA, resto, re.I) and not re.search(NA_TELA, resto, re.I):
                achados.append('escolha no chat: %s' % f.strip())
    return achados


PEDIDO_DE_VALOR = r'\b(?:peç\w*|pede|pedir|ofereç\w*|oferec\w*|apresent\w*|solicit\w*|cobr\w*)\b'
VERBO_DE_ESCOLHA = r'(?:escolh|decid|defin|inform|diz|dig|respond|mand|indi|selecion|marc|opt|confirm)\w*|dar|dê|der'
DEIXAR_O_DA_ESCOLHER = (r'\b(?:deix\w*|permit\w*|aguard\w*|esper\w*)\s+(?:que\s+)?(?:o|a)\s+%s\s+(?:\w+\s+)?'
                        r'(?:escolh|decid|defin|selecion|opt|diz|dig|respond)\w*' % QUEM_E_O_DA)
NA_TELA = r'\bna tela\b|\bpasso \d da tela\b|\bclique\b'


TOCA_BIBLIOTECA = re.compile(re.escape(MARCADOR_BIBLIOTECA) + r'|(?i:biblioteca da agência)|\bBIBLIOTECA\b')
# ler por qualquer verbo ou comando: ferramentas do Claude Code e os comandos de listar e ler da Bash e da PowerShell
LEITURA = (r'(?<![\w-])(?:leia|ler|lê|lendo|liste|listar|lista|abra|abrir|copie|copiar|procur\w*|busqu\w*|busca\w*|'
           r'consult\w*|examin\w*|inspecion\w*|olh\w*|veja|ver|vê|vasculh\w*|percorr\w*|varr\w*|explor\w*|'
           r'Read|Glob|Grep|ls|dir|cat|type|tree|find|rg|grep|findstr|gci|Get-ChildItem|Get-Content|'
           r'Select-String)(?![\w-])')
ALVO_BIBLIOTECA = r'(?i:biblioteca da agência)|\bBIBLIOTECA\b|\bmarcas/|perfil-marca'
# "Quem lê a biblioteca é o motor", "o motor lê a biblioteca": descricao de quem le, nao instrucao ao Claude
SUJEITO_MOTOR = re.compile(r'\b(?:o motor|o desdobra)\s+(?:\w+\s+)?$', re.I)


def regra_biblioteca_lida(texto):
    """Nenhuma instrucao para ler, listar, abrir, procurar, consultar ou copiar a biblioteca da agencia, nem por
    comando de shell."""
    achados = []
    for f in frases(texto):
        for m in re.finditer(LEITURA, f, re.I):
            if _negado(f, m.start(), LEITURA):
                continue
            antes = f[:m.start()]
            if SUJEITO_MOTOR.search(antes) or (re.search(r'\bquem\s+$', antes, re.I) and
                                               re.search(r'\bé\s+o\s+(?:motor|desdobra)\b', _resto(f, m.end()))):
                continue
            if re.search(ALVO_BIBLIOTECA, _resto(f, m.end())):
                achados.append('lê a biblioteca: %s' % f.strip())
    return achados


def tem_regra_da_biblioteca(texto):
    """A frase "nunca leia a biblioteca": um verbo de leitura negado (nunca, não, nem, jamais governando o verbo, ou a
    enumeracao "nunca leia, liste nem copie") seguido da biblioteca, ou de essa pasta, que a mesma linha chama de
    BIBLIOTECA. "Nunca deixe de listar a biblioteca" e "Nunca esqueça de levar a opção da biblioteca" nao contam."""
    for f in frases(texto):
        for m in re.finditer(LEITURA, f, re.I):
            if _negado(f, m.start(), LEITURA) and \
                    re.search(r'biblioteca|BIBLIOTECA|\b(?:essa|esta) pasta\b', _resto(f, m.end())):
                return True
    return False


def regra_biblioteca_ausente(textos):
    """Onde a skill toca a biblioteca (no SKILL.md ou nas referencias), a regra de nunca le-la esta presente; o
    SKILL.md que leva o marcador traz a regra no proprio texto."""
    juntos = '\n\n'.join(textos.values())
    achados = []
    if TOCA_BIBLIOTECA.search(juntos) and not tem_regra_da_biblioteca(juntos):
        achados.append('sem a regra de nunca ler a biblioteca')
    for nome, t in textos.items():
        if MARCADOR_BIBLIOTECA in t and not tem_regra_da_biblioteca(t):
            achados.append('%s: marcador sem a regra de nunca ler a biblioteca' % nome)
    return achados


def regra_biblioteca_vazia(texto):
    """O caso de ${user_config.biblioteca_agencia} vazio: o marcador aparece uma vez (o Claude Code troca o marcador no
    texto inteiro, e uma guarda que o cite vira sempre verdadeira), o paragrafo dele trata a pasta vazia, a tela abre
    sempre com --biblioteca "BIBLIOTECA" entre aspas (vazio vira "" e o motor le como biblioteca ausente) e nada manda
    tirar a opcao."""
    achados = []
    if MARCADOR_BIBLIOTECA in texto:
        if texto.count(MARCADOR_BIBLIOTECA) != 1:
            achados.append('marcador citado %d vezes' % texto.count(MARCADOR_BIBLIOTECA))
        paragrafo = next(p for p in re.split(r'\n\s*\n', texto) if MARCADOR_BIBLIOTECA in p)
        if not re.search(r'\bvazi[ao]\b|não configurad', paragrafo):
            achados.append('caso vazio sem tratamento')
        if not re.search(r'\bBIBLIOTECA\b', paragrafo):
            achados.append('marcador sem o nome BIBLIOTECA')
    for c in comandos_do_motor(texto):
        if 'tela abrir' in c and '--biblioteca "BIBLIOTECA"' not in c:
            achados.append('tela sem --biblioteca "BIBLIOTECA": %s' % c)
        for m in re.finditer(r'--biblioteca(?:\s+|=)(\S+)', c):
            if m.group(1) != '"BIBLIOTECA"':
                achados.append('--biblioteca sem aspas: %s' % c)
    for valor in ('', 'D:/Agencia/biblioteca'):
        trocado = texto.replace(MARCADOR_BIBLIOTECA, valor)
        if re.search(r'\b(?:tir\w*|omit\w*|remov\w*|retir\w*|sem a opção|sem a parte)\s+`?--biblioteca', trocado, re.I):
            achados.append('manda tirar --biblioteca')
            break
    return achados


def regra_invocacao(nome_skill, texto):
    fm = frontmatter(texto)
    if fm is None or not fm.get('description'):
        return ['sem frontmatter com description']
    if nome_skill == 'sugerir-funcoes' and fm.get('disable-model-invocation') != 'false':
        return ['sugerir-funcoes sem disable-model-invocation: false']
    return []


def skills_faltando(raiz=SKILLS):
    return [s for s in SKILLS_DA_TABELA if not (raiz / s / 'SKILL.md').is_file()]


REGRAS_DE_TEXTO = {
    'tamanho': regra_tamanho,
    'caminho_relativo': regra_caminho_relativo,
    'interpretador': regra_interpretador,
    'teto': regra_teto,
    'atos_e_terminal': regra_atos_e_terminal,
    'caminho_absoluto': regra_caminho_absoluto,
    'pergunta_de_modo': regra_pergunta_de_modo,
    'biblioteca_lida': regra_biblioteca_lida,
    'biblioteca_vazia': regra_biblioteca_vazia,
}


# ------------------------------------------------------------------ as skills de verdade
def _todos_os_arquivos():
    return [(s, a) for s, arquivos in arquivos_das_skills().items() for a in arquivos]


def test_cada_skill_da_tabela_3_5_existe():
    assert skills_faltando() == []
    # e toda pasta de skill tem o SKILL.md
    assert all(arquivos and arquivos[0].name == 'SKILL.md' for arquivos in arquivos_das_skills().values())


@pytest.mark.parametrize('regra', sorted(REGRAS_DE_TEXTO))
def test_skills_seguem_a_regra(regra):
    achados = []
    for _, arquivo in _todos_os_arquivos():
        achados += ['%s: %s' % (_rel(arquivo), a) for a in REGRAS_DE_TEXTO[regra](_ler(arquivo))]
    assert achados == [], '\n'.join(achados)


def test_regra_da_biblioteca_presente_onde_a_skill_a_toca():
    achados = []
    for skill, arquivos in arquivos_das_skills().items():
        textos = {_rel(a): _ler(a) for a in arquivos}
        achados += ['%s: %s' % (skill, a) for a in regra_biblioteca_ausente(textos)]
    assert achados == [], '\n'.join(achados)


def test_frontmatter_e_sugerir_funcoes_chamada_pelo_modelo():
    achados = []
    for skill, arquivos in arquivos_das_skills().items():
        achados += ['%s: %s' % (skill, a) for a in regra_invocacao(skill, _ler(arquivos[0]))]
    assert achados == [], '\n'.join(achados)
    fm = frontmatter(_ler(SKILLS / 'sugerir-funcoes' / 'SKILL.md'))
    assert fm['disable-model-invocation'] == 'false'


def test_arquivos_das_skills_em_utf8_com_lf():
    # o que vai no pacote e o indice do git (a copia de trabalho segue o core.autocrlf da maquina); o arquivo novo,
    # ainda fora do indice, confere-se pelos bytes
    git = shutil.which('git')
    if git is None or not (RAIZ_PLUGIN.parents[1] / '.git').exists():
        pytest.skip('precisa do git')
    saida = subprocess.run([git, '-C', str(RAIZ_PLUGIN), 'ls-files', '--eol', '--', 'skills'],
                           capture_output=True, check=True).stdout.decode('utf-8')
    no_indice = {}
    for linha in saida.splitlines():
        info, caminho = linha.split('\t', 1)
        no_indice[(RAIZ_PLUGIN / caminho).resolve()] = info.split()[0]
    assert no_indice
    for _, arquivo in _todos_os_arquivos():
        dados = arquivo.read_bytes()
        dados.decode('utf-8')
        eol = no_indice.get(arquivo.resolve())
        if eol is None:
            assert b'\r' not in dados, _rel(arquivo)
        else:
            assert eol in ('i/lf', 'i/none'), (_rel(arquivo), eol)


@pytest.mark.skipif(palavras_do_ambiente() is None,
                    reason='defina DESDOBRA_PALAVRAS_PROIBIDAS com o arquivo de palavras, fora do repositorio')
def test_skills_sem_palavra_proibida():
    palavras = palavras_do_ambiente()
    # o motivo nunca repete a palavra achada, para a mensagem do teste nao virar ocorrencia
    achados = [_rel(a) for _, a in _todos_os_arquivos() if palavras_de_cliente(_ler(a), palavras)
               or palavras_de_cliente(_rel(a), palavras)]
    assert achados == []


# ------------------------------------------------------------------ autoverificacao: cada regra pega o caso ruim
CABECALHO_BOM = ('1. Leia `${CLAUDE_PLUGIN_DATA}/interpretador.json` com a ferramenta Read. Guarde o campo `python`, '
                 'chamado de PY abaixo.\n\n2. O teto do modo de dados é `' + MARCADOR_TETO + '`, chamado de TETO.\n\n')
LINHA_BOA = '"PY" -I -B -m desdobra --envelope --teto-modo-dados TETO job estado "PASTA"'

CASOS_RUINS = {
    'tamanho': ['linha\n' * 500],
    'caminho_relativo': [
        'Rode `python scripts/bb.py job` na pasta do plugin.',
        'Leia `references/taxonomia-funcoes.md` antes.',
        'Leia `../motor/desdobra/cli.py`.',
        'Use o executável `bin/desdobra`.',
        'Leia `C:\\Users\\agencia\\plugin\\skills\\x.md`.',
        'Rode `py motor/rodar.py`.',
        'Leia `${CLAUDE_PLUGIN_ROOT}/../outro-plugin/x.md`.',
        'Leia `sugestoes/../../../segredo.txt` da PASTA.',
    ],
    'interpretador': [
        CABECALHO_BOM + '```\npython -m desdobra --envelope --teto-modo-dados TETO doctor\n```\n',
        CABECALHO_BOM + 'Rode `desdobra --envelope --teto-modo-dados TETO doctor`.\n',
        CABECALHO_BOM + '```\n"${CLAUDE_PLUGIN_ROOT}/venv/python" -m desdobra --envelope --teto-modo-dados TETO doctor\n```\n',
        '2. O teto é `' + MARCADOR_TETO + '`, chamado de TETO.\n\n```\n' + LINHA_BOA + '\n```\n',
        CABECALHO_BOM + 'Defina PYTHONPATH antes de rodar.\n',
        CABECALHO_BOM + '```\n"PY" -I -B -c "import desdobra.cli as c; c.main([\'job\',\'estado\',\'PASTA\'])"\n```\n',
    ],
    'teto': [
        CABECALHO_BOM + '```\n"PY" -I -B -m desdobra --envelope job estado "PASTA"\n```\n',
        CABECALHO_BOM + '```\n"PY" -I -B -m desdobra --envelope --teto-modo-dados a job estado "PASTA"\n```\n',
        CABECALHO_BOM + 'Rode `"PY" -I -B -m desdobra --envelope job proxima "PASTA"` de novo.\n',
        '1. Leia `${CLAUDE_PLUGIN_DATA}/interpretador.json`. Guarde o campo `python`, chamado de PY.\n\n```\n'
        + LINHA_BOA + '\n```\n',
        CABECALHO_BOM + 'Se o teto estiver vazio, tire `--teto-modo-dados TETO` do comando.\n\n```\n' + LINHA_BOA
        + '\n```\n',
        CABECALHO_BOM + 'Sem teto, rode o passo 4 sem a parte `--teto-modo-dados TETO`.\n\n```\n' + LINHA_BOA
        + '\n```\n',
        CABECALHO_BOM + '```\n"PY" -I -B -c "import desdobra.cli as c; c.main([\'job\',\'estado\',\'PASTA\'])"\n```\n',
    ],
    'atos_e_terminal': [
        CABECALHO_BOM + '```\n"PY" -I -B -m desdobra --envelope --teto-modo-dados TETO render --job "PASTA"\n```\n',
        CABECALHO_BOM + '```\n"PY" -I -B -m desdobra --envelope --teto-modo-dados TETO aprovar --job "PASTA"\n```\n',
        CABECALHO_BOM + 'Rode `"PY" -I -B -m desdobra --envelope --teto-modo-dados TETO entregar --job "PASTA"`.\n',
        CABECALHO_BOM + '```\n"PY" -I -B -m desdobra --envelope --teto-modo-dados TETO spec confirmar "PASTA"\n```\n',
        CABECALHO_BOM + '```\n"PY" -I -B -m desdobra --envelope --teto-modo-dados TETO parametros-entrega "PASTA"\n```\n',
        CABECALHO_BOM + '```\n"PY" -I -B -m desdobra --envelope --teto-modo-dados TETO marca registrar "PASTA"\n```\n',
        'Peça ao DA para rodar `desdobra aprovar` no terminal.',
        'Diga ao DA para abrir um terminal e rodar o render.',
        'Explique ao DA que ele roda a entrega pelo comando do desdobra.',
        'O DA roda o comando de confirmação no PowerShell.',
        'Abra um terminal e digite o comando da tela.',
        'Mostre ao DA o comando `desdobra parametros-entrega --job X`.',
        'Instrua o diretor de arte a digitar o comando de aprovação no terminal.',
        'Peça ao usuário para rodar o render pelo comando do desdobra.',
        'Diga à diretora de arte que ela digita o comando de entrega no PowerShell.',
    ],
    'caminho_absoluto': [
        'Peça ao DA o caminho relativo da pasta do job.',
        'Peça ao DA o caminho da pasta do job.',
        'Se a pasta não existe, peça o caminho de novo.',
        'Aceite um caminho relativo da pasta do job, se ele mandar.',
        'Pergunte ao DA o caminho da pasta, a partir da pasta atual.',
        'Peça ao DA a pasta do job.',
        'Peça ao DA para colar o caminho da pasta do job.',
    ],
    'pergunta_de_modo': [
        'Pergunte ao DA qual modo de dados ele quer.',
        'Pergunte ao DA o teto da agência.',
        'Pergunte ao DA o valor da área segura.',
        'Escolha pelo DA a regra de escala da função.',
        'Qual modo de dados você prefere?',
        'Consulte o DA sobre o limite de memória.',
        'Deixe o DA escolher o modo de dados (a), (b) ou (c) aqui no chat.',
        'Peça ao DA o teto do modo de dados.',
        'Ofereça ao DA as opções de modo de dados: a, b ou c.',
        'Peça ao DA o valor da margem de segurança em pixels.',
        'Peça ao DA para escolher o modo de dados aqui no chat.',
    ],
    'biblioteca_lida': [
        'Leia o perfil da marca na biblioteca da agência.',
        'Liste a pasta BIBLIOTECA para achar a marca.',
        'Copie `marcas/x/perfil-marca.json` para o job.',
        'Procure a marca dentro da pasta BIBLIOTECA.',
        'Rode `ls "BIBLIOTECA/marcas"` para ver as marcas.',
        'Consulte o perfil-marca.json da marca antes de sugerir.',
        'Rode `Get-ChildItem "BIBLIOTECA"` na PowerShell.',
        'Nunca deixe de listar a biblioteca da agência para o DA.',
    ],
    'biblioteca_vazia': [
        '2. A pasta da biblioteca é `' + MARCADOR_BIBLIOTECA + '`, chamada de BIBLIOTECA.\n',
        '2. A biblioteca é `' + MARCADOR_BIBLIOTECA + '`, chamada de BIBLIOTECA, mesmo com ela vazia.\n\n'
        'Se `' + MARCADOR_BIBLIOTECA + '` estiver vazio, não passe a opção.\n',
        '2. A biblioteca é `' + MARCADOR_BIBLIOTECA + '`, chamada de BIBLIOTECA, mesmo vazia. Se ela estiver vazia, '
        'tire `--biblioteca` do comando.\n',
        CABECALHO_BOM + '```\n"PY" -I -B -m desdobra --envelope --teto-modo-dados TETO tela abrir --job "PASTA"\n```\n',
        CABECALHO_BOM + '```\n"PY" -I -B -m desdobra --envelope --teto-modo-dados TETO --biblioteca BIBLIOTECA '
        'tela abrir --job "PASTA"\n```\n',
    ],
}

# frases boas, tiradas da forma das skills: as regras nao podem acusar a negacao nem a explicacao do clique
CASOS_BONS = [
    'O DA nunca roda comando no terminal. Você roda os comandos do motor.',
    'Você nunca passa ao DA um comando nem um texto do motor que fale em terminal.',
    'Diga ao DA que o render e a aprovação são cliques dele na tela.',
    'Não explique o `o_que_fazer` ao DA, porque ele fala de terminal.',
    'Peça o caminho absoluto da pasta do job; nunca peça nem aceite um caminho relativo.',
    'Nunca pergunte nem escolha pelo DA o modo de dados, o teto, um valor de spec, um limite ou uma regra.',
    'Nunca leia, liste nem copie a biblioteca da agência.',
    'Na ferramenta PowerShell, ponha `& ` antes do caminho entre aspas.',
    'Pergunte ao DA se ele quer resolver agora ou seguir.',
    'Diga ao DA que ele não precisa de terminal: tudo é clique na tela.',
    'Diga ao DA que ele não precisa rodar nada, porque o render é um clique dele na tela.',
    'Quem lê a biblioteca da agência é o motor; você nunca lê essa pasta.',
    'O motor lê a biblioteca da agência sozinho.',
    'Peça ao DA para conferir na tela o caminho da pasta de entrega.',
    'Peça ao DA para configurar o teto do plugin em `/plugin`, opção Configure, e pare.',
    'Peça ao DA para escolher o modo de dados no passo 1 da tela.',
    # a excecao declarada da regra do teto: so o doctor, que nao toca dado de job, roda sem o teto nao configurado
    CABECALHO_BOM + 'Se o teto não estiver configurado, rode o passo 3 sem a parte `--teto-modo-dados TETO`.\n\n3. Rode:'
    '\n\n```\n"PY" -I -B -m desdobra --envelope --teto-modo-dados TETO doctor\n```\n',
    CABECALHO_BOM + '3. A pasta da biblioteca da agência é `' + MARCADOR_BIBLIOTECA + '`, chamada de BIBLIOTECA. Passe '
    'sempre `--biblioteca "BIBLIOTECA"`, mesmo com ela vazia. Você nunca lê nem lista essa pasta.\n\n```\n'
    '"PY" -I -B -m desdobra --envelope --teto-modo-dados TETO --biblioteca "BIBLIOTECA" tela abrir --job "PASTA"\n'
    '```\n\nLeia `${CLAUDE_PLUGIN_ROOT}/skills/x/references/y.md` e `sugestoes/pacote-modelo.json` da PASTA.\n',
]


@pytest.mark.parametrize('regra,indice', [(r, i) for r, casos in sorted(CASOS_RUINS.items())
                                          for i in range(len(casos))])
def test_autoverificacao_cada_regra_pega_o_caso_ruim(regra, indice):
    assert REGRAS_DE_TEXTO[regra](CASOS_RUINS[regra][indice]), (regra, CASOS_RUINS[regra][indice])


def test_autoverificacao_toda_regra_tem_caso_ruim():
    assert set(CASOS_RUINS) == set(REGRAS_DE_TEXTO)


@pytest.mark.parametrize('indice', range(len(CASOS_BONS)))
def test_autoverificacao_casos_bons_passam(indice):
    texto = CASOS_BONS[indice]
    achados = {r: f(texto) for r, f in REGRAS_DE_TEXTO.items()}
    assert {r: a for r, a in achados.items() if a} == {}
    assert regra_biblioteca_ausente({'x': texto}) == [] or MARCADOR_BIBLIOTECA not in texto


def test_autoverificacao_biblioteca_sem_a_regra():
    tocada = '2. A pasta da biblioteca da agência é `' + MARCADOR_BIBLIOTECA + '`, chamada de BIBLIOTECA, mesmo vazia.'
    assert regra_biblioteca_ausente({'SKILL.md': tocada})
    # a regra so na referencia nao basta para o SKILL.md que leva o marcador
    assert regra_biblioteca_ausente({'SKILL.md': tocada, 'ref.md': 'Nunca leia a biblioteca da agência.'})
    assert regra_biblioteca_ausente({'SKILL.md': tocada + ' Você nunca lê nem lista essa pasta.'}) == []
    # a referencia que so cita a biblioteca vale pela regra do SKILL.md da mesma skill
    assert regra_biblioteca_ausente({'glossario.md': 'Biblioteca da agência: a pasta das marcas.'})
    assert regra_biblioteca_ausente({'glossario.md': 'Biblioteca da agência: a pasta das marcas.',
                                     'SKILL.md': 'Nunca leia, liste nem copie a biblioteca da agência.'}) == []
    # a regra e um verbo de leitura negado; frases com "nunca" e "biblioteca" que dizem outra coisa nao contam
    assert regra_biblioteca_ausente({'SKILL.md': tocada + ' Nunca esqueça de levar a opção da biblioteca no comando.'})
    assert regra_biblioteca_ausente({'SKILL.md': tocada + ' Nunca deixe de listar a biblioteca para o DA.'})
    assert not tem_regra_da_biblioteca('Nunca deixe de listar a biblioteca para o DA.')
    assert not tem_regra_da_biblioteca('Nunca esqueça de levar a opção da biblioteca no comando.')
    assert tem_regra_da_biblioteca('Você nunca lê, lista nem copia essa pasta.')
    assert tem_regra_da_biblioteca('Nunca procure nada na biblioteca da agência.')


def test_autoverificacao_frontmatter():
    assert regra_invocacao('sugerir-funcoes', '---\ndescription: x\ndisable-model-invocation: true\n---\n')
    assert regra_invocacao('sugerir-funcoes', '---\ndescription: x\n---\n')
    assert regra_invocacao('doctor', '# sem frontmatter\n')
    assert regra_invocacao('sugerir-funcoes', '---\ndescription: x\ndisable-model-invocation: false\n---\n') == []


def test_autoverificacao_skill_da_tabela_faltando(tmp_path):
    for s in SKILLS_DA_TABELA[1:]:
        (tmp_path / s).mkdir()
        (tmp_path / s / 'SKILL.md').write_text('---\ndescription: x\n---\n', encoding='utf-8')
    assert skills_faltando(tmp_path) == [SKILLS_DA_TABELA[0]]


def test_autoverificacao_palavras_proibidas_inventadas():
    padroes = compilar_palavras(['Marca Inventada Zeta'], ['ZQX'])
    assert palavras_de_cliente('Leia a peça da marca-inventada-zeta.', padroes)
    assert palavras_de_cliente('O job ZQX abriu.', padroes)
    assert palavras_de_cliente(_ler(SKILLS / 'doctor' / 'SKILL.md'), padroes) == []


# ------------------------------------------------------------------ as linhas do motor: analisador e gancho
def linhas_por_skill(raiz=SKILLS):
    """{skill: [linha do motor, ...]}: a contagem por skill sai daqui, nunca do id do pytest (os nomes das skills tem
    hifen)."""
    return {skill: [c for arquivo in arquivos for c in comandos_do_motor(_ler(arquivo))]
            for skill, arquivos in arquivos_das_skills(raiz).items()}


def _linhas_do_motor():
    saida = []
    for skill, arquivos in arquivos_das_skills().items():
        for arquivo in arquivos:
            for i, c in enumerate(comandos_do_motor(_ler(arquivo))):
                saida.append(pytest.param(c, id='%s-%s-%d' % (skill, arquivo.stem, i)))
    return saida


LINHAS_DO_MOTOR = _linhas_do_motor()


def skills_sem_linha_do_motor(raiz=SKILLS):
    # novo-job, continuar, doctor, sugerir-funcoes e ler-spec chamam o motor (3.5): cada uma tem de ter linha na
    # varredura, ou o gancho e o analisador passam sem testar nada dela
    por_skill = linhas_por_skill(raiz)
    return [s for s in SKILLS_DA_TABELA if not por_skill.get(s)]


def test_toda_skill_que_chama_o_motor_tem_linhas():
    assert skills_sem_linha_do_motor() == []
    assert len(LINHAS_DO_MOTOR) == sum(len(v) for v in linhas_por_skill().values())


def test_autoverificacao_skill_sem_linha_do_motor(tmp_path):
    for s in SKILLS_DA_TABELA:
        (tmp_path / s).mkdir()
        (tmp_path / s / 'SKILL.md').write_text('---\ndescription: x\n---\n\n```\n' + LINHA_BOA + '\n```\n',
                                               encoding='utf-8')
    assert skills_sem_linha_do_motor(tmp_path) == []
    # a skill que perde todas as linhas, ou que troca o -m desdobra por outra forma, aparece
    (tmp_path / 'sugerir-funcoes' / 'SKILL.md').write_text('---\ndescription: x\n---\n\nsem linha\n', encoding='utf-8')
    assert skills_sem_linha_do_motor(tmp_path) == ['sugerir-funcoes']


def _valores(tmp_path, biblioteca_valor):
    job = tmp_path / 'job'
    (job / 'sugestoes').mkdir(parents=True, exist_ok=True)
    (job / 'estado.json').write_text('{}', encoding='utf-8')
    origem = tmp_path / 'origem'
    origem.mkdir(exist_ok=True)
    return {'PY': sys.executable, 'TETO': 'a', 'PASTA': job.as_posix(), 'PSD': (origem / 'kv-sintetico.psd').as_posix(),
            'FONTE1': (origem / 'face-sintetica-1.otf').as_posix(),
            'FONTE2': (origem / 'face-sintetica-2.ttf').as_posix(), 'SPECS': (origem / 'specs').as_posix(),
            'NOME': 'arquivo-sintetico.otf', 'ARQUIVO': (origem / 'novo-sintetico.otf').as_posix(),
            'VEICULADOR': 'veiculador-sintetico', 'BIBLIOTECA': biblioteca_valor}


def _trocar(linha, valores):
    sobra = set(re.findall(r'\b[A-Z][A-Z0-9_]+\b', linha)) - set(MARCADORES_DAS_LINHAS)
    assert not sobra, 'marcador novo na linha da skill: %s' % sorted(sobra)
    return re.sub(r'\b(%s)\b' % '|'.join(MARCADORES_DAS_LINHAS), lambda m: valores[m.group(1)], linha)


@pytest.mark.parametrize('linha', LINHAS_DO_MOTOR)
@pytest.mark.parametrize('teto', ['a', 'b', 'c'])
@pytest.mark.parametrize('com_biblioteca', [False, True])
def test_linha_da_skill_e_aceita_pelo_analisador_do_motor(tmp_path, linha, teto, com_biblioteca):
    bib = (tmp_path / 'bib').as_posix() if com_biblioteca else ''
    valores = dict(_valores(tmp_path, bib), TETO=teto)
    partes = shlex.split(_trocar(linha.lstrip('& ').strip(), valores), posix=True)
    assert partes[:4] == [sys.executable, '-I', '-B', '-m'] and partes[4] == 'desdobra', partes
    args = cli.montar_analisador().parse_args(partes[5:])
    assert args.envelope is True and args.teto_modo_dados == teto
    if '--biblioteca' in partes:
        # vazio vira "" no comando, e o motor le como biblioteca ausente: o job roda sem marca
        esperado = None if not com_biblioteca else Path(bib)
        assert biblioteca.normalizar(args.biblioteca) == esperado


def _gancho():
    spec = importlib.util.spec_from_file_location('gancho_confirmacoes_k6', GANCHO)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize('linha', LINHAS_DO_MOTOR)
@pytest.mark.parametrize('ferramenta,prefixo', [('Bash', ''), ('PowerShell', ''), ('PowerShell', '& ')])
@pytest.mark.parametrize('com_biblioteca', [False, True])
def test_linha_da_skill_passa_pelo_gancho(tmp_path, monkeypatch, linha, ferramenta, prefixo, com_biblioteca):
    # modelado no test_skill_sugerir_funcoes.py::test_linhas_da_skill_passam_pelo_gancho, agora para toda linha de
    # toda skill: o gancho reconhece a chamada do motor ("PY" -I -B -m desdobra, MOTOR_GERAL da leva 4) e deixa passar
    bib = tmp_path / 'bib'
    if com_biblioteca:
        bib.mkdir()
    valores = _valores(tmp_path, bib.as_posix() if com_biblioteca else '')
    dados = tmp_path / 'dados'
    dados.mkdir()
    (dados / 'interpretador.json').write_text(json.dumps({'python': sys.executable}), encoding='utf-8')
    monkeypatch.setenv('CLAUDE_PLUGIN_DATA', str(dados))
    comando = prefixo + _trocar(linha.lstrip('& ').strip(), valores)
    ev = {'tool_name': ferramenta, 'tool_input': {'command': comando}, 'cwd': str(tmp_path)}
    assert _gancho().decidir_com_motivo(ev) == (None, None), comando
