# -*- coding: utf-8 -*-
"""Gancho PreToolUse do plugin: o Claude nunca dispara o que so o DA dispara.

Roda com o Python do PATH, so com a biblioteca padrao, na forma exec (hooks/hooks.json):

    python -I -B ${CLAUDE_PLUGIN_ROOT}/scripts/gancho_confirmacoes.py

Le da entrada padrao o JSON do evento (tool_name e tool_input) e nega (permissionDecision "deny"):
  - nas ferramentas Bash e PowerShell, comando que chama o render, a confirmacao de linkado, a confirmacao de spec,
    a do briefing, o aprovar, o entregar ou o parametros-entrega do desdobra (pela linha de comando ou pelo codigo
    Python do motor), que
    mexe na conferencia do disparo humano, ou que escreve num arquivo que so o DA grava;
  - nas ferramentas que gravam arquivo (Write, Edit, MultiEdit, NotebookEdit), arquivo que so o DA grava ou que so o
    motor grava: tudo em briefing/** (o briefing confirmado, o rascunho da tela briefing/rascunho.json, o historico e
    a aprovacao inclusive) e em derivacao/**, o estado.json do job, specs/confirmacoes.json, master, render.json e
    contrato de render/, o que esta em entrega/, o manifesto e o relatorio da entrega e parametros/entrega.json
    (decisoes-v1.md, 159; proposta do M7, 160c). O codigo-fonte do pacote (desdobra/briefing/<modulo>.py,
    desdobra/derivacao/<modulo>.py, desdobra/entrega/<modulo>.py) continua editavel;
  - a ferramenta do painel de terminal do app do Claude (mcp__terminal__run_in_terminal), sempre, como pede a
    decisoes-v1.md, 160, com o motivo MOTIVO_PAINEL: o painel roda no shell do DA, onde o Claude tira as marcas de
    ambiente e, com um salto (explorer.exe abrindo um script), a cadeia de pais que o motor confere;
  - nas ferramentas Bash e PowerShell, pedido as rotas do servidor da tela no loopback (ROTA_DA_TELA), comando que cita
    o perfil temporario do navegador da tela (PERFIL_DA_TELA, com curinga inclusive), codigo que chama o processo de
    fundo ou o servidor da tela (CODIGO_DA_TELA), despejo de memoria de processo (DESPEJO_DE_MEMORIA: o token, a
    sessao e as fontes ficam na memoria do processo de fundo) e teclas ou cliques simulados (TECLAS_SIMULADAS: a
    janela da tela tem DevTools); nas ferramentas de arquivo, escrita no perfil da tela; nas de leitura (Read, Glob,
    Grep), caminho ou padrao no perfil da tela; nas de navegador (mcp__claude-in-chrome__*, mcp__Claude_Browser__*,
    WebFetch), as rotas da tela, o cookie dela (COOKIE_DA_TELA), o cabecalho e a meta do token CSRF das escritas
    (CSRF_DA_TELA; o Claude nunca chega as rotas de escrita da tela) e o perfil. O "desdobra tela abrir" passa: quem abre a
    tela e o Claude (decisoes-v1.md, 159), e o token da entrada nunca sai do processo de fundo;
  - escrita no aval do download do Chromium com janela (aval-chromium-janela.json, decisoes-v1.md, 158), que so o DA
    da.
Escrita pelo terminal inclui redirecao, copia, movimento e troca de nome (os.replace, os.rename, shutil,
Rename-Item, ren, Move-Item, Copy-Item) e a opcao --saida do motor. O motor chamado como desdobra, desdobra.exe,
desdobra.cli ou desdobra.__main__ conta igual. O comando e conferido como chegou e normalizado (sem aspas, sem o
escape ^ do cmd e ` do PowerShell, caminhos sem ./, // e segmento/..), e subcomando numa variavel ($c, %c%) e negado; o
caminho das ferramentas de arquivo tambem e normalizado.
Com a negacao, o Claude recebe o motivo: quem roda isso e o DA, num terminal proprio, fora do Claude. Sem negacao, o
gancho nao imprime nada e o Claude Code segue o fluxo normal de permissao. O codigo de saida e sempre 0.

Desde a revisao do M7a, o codigo que cita o desdobra e chama os gravadores de baixo do motor (contratos.gravar,
arquivos.gravar_*_atomico) e negado sempre, e a escrita com caminho do DA pela constante de um modulo (mb.ARQUIVO) ou
montado por partes entre aspas (Path(j, 'briefing', 'x.json')) tambem.
Desde a segunda revisao do M7b, fase B, o comando que importa um modulo de teste do plugin (MODULO_DE_TESTE: os testes
da tela trazem o servidor, os atos e os ajudantes HTTP), que cita o servidor ou os atos da tela pelo nome
(ServidorTela, atos_do_job, em CODIGO_DA_TELA) ou que tira do ambiente uma marca do Claude (MARCA_DO_CLAUDE com
TIRA_DO_AMBIENTE, ou o ambiente zerado) tambem e negado, cite o desdobra ou nao. Rodar e ler os testes seguem.
Este gancho cobre o caminho direto do Claude, pelo texto do comando e pelo caminho do arquivo: nao le o conteudo de um
script gravado antes nem resolve caminho montado por partes ou nome de modulo partido, entao barra o engano e nao o
desvio feito de proposito (docs/m1-interfaces.md, M6). O motor confere o console de novo (desdobra.humano) so no
comando; um arquivo do DA escrito a mao nao tem prova de quem gravou (confirmado_por e dado sem segredo). Os riscos
residuais (esse e o de um processo do mesmo usuario, fora do Claude, que escreve teclas num console) ficam declarados.
"""
import json
import re
import sys

MOTIVO = ('O desdobra recusa este comando pelo Claude: render, confirmação de linkado, confirmação de spec, '
          'confirmação de briefing, aprovação, entrega e parâmetros de entrega só partem do DA. Peça ao DA para abrir um terminal próprio, fora do Claude, e rodar '
          'o comando lá; o desdobra pergunta e grava. Não tente outro caminho para o mesmo efeito.')
MOTIVO_PAINEL = ('O desdobra recusa comandos do Claude no painel de terminal do app: o painel roda no terminal do DA, '
                 'e o que só o DA faz não parte do Claude. O que não é do DA (job proxima, doctor) segue pelas '
                 'ferramentas Bash ou PowerShell; o resto só parte do DA. Não tente outro caminho para o mesmo efeito.')
FERRAMENTAS_DE_COMANDO = ('Bash', 'PowerShell')
FERRAMENTAS_DE_ARQUIVO = ('Write', 'Edit', 'MultiEdit', 'NotebookEdit')
# ferramenta do app do Claude que digita um comando no painel de terminal, no shell do DA e fora da sandbox
# (decisoes-v1.md, 160). O motor recusa o painel (desdobra.humano, marcas medidas do painel); o gancho nega a
# ferramenta sempre: o texto do comando nao diz o que ele faz (string partida, script gravado antes). A
# mcp__terminal__open_terminal_tab nao digita comando nenhum e fica de fora
FERRAMENTAS_DO_PAINEL = ('mcp__terminal__run_in_terminal',)
FERRAMENTAS_DE_LEITURA = ('Read', 'Glob', 'Grep')
CAMPOS_DE_LEITURA = ('file_path', 'path', 'pattern', 'glob', 'notebook_path')
# ferramentas de navegador e de rede do Claude: o que elas pedem e conferido pelo texto inteiro da entrada
PREFIXOS_DE_NAVEGADOR = ('mcp__claude-in-chrome__', 'mcp__Claude_Browser__')
FERRAMENTAS_DE_REDE = ('WebFetch',)
# subcomandos humanos do desdobra, depois de "desdobra" e de opcoes globais quaisquer. Os mesmos de
# desdobra.humano.COMANDOS, com teste (aprovar e entregar: decisoes-v1.md, 138 e 142)
SUBCOMANDOS_HUMANOS = ('render', 'linkado confirmar', 'spec confirmar', 'briefing confirmar', 'aprovar', 'entregar',
                       'parametros-entrega')
_PRIMEIRAS = sorted({c.split()[0] for c in SUBCOMANDOS_HUMANOS})
SUBCOMANDO = re.compile(r'desdobra(?:\.exe|\.cli|\.__main__)?["\']?(?:\s+--?[\w-]+(?:[ =](?!%s)[^\s|;&]+)?)*'
                        r'\s+(%s)(?![\w./\\-])' % ('|'.join(r'%s\b' % c for c in _PRIMEIRAS),
                                                 '|'.join(r'\s+'.join(c.split()) for c in SUBCOMANDOS_HUMANOS)),
                        re.IGNORECASE)
# subcomando passado numa variavel (PowerShell $c, cmd %c%): o gancho nao sabe qual e, entao nega
SUBCOMANDO_EM_VARIAVEL = re.compile(r'desdobra(?:\.exe|\.cli|\.__main__)?(?:\s+--?[\w-]+(?:[ =][^\s|;&]+)?)*\s+[$%]',
                                    re.IGNORECASE)
# codigo do motor que grava o que so o DA grava, ou que mexe na conferencia. Da aprovacao e da entrega: os modulos
# desdobra.entrega.aprovacao e desdobra.entrega.validar, o registro, o selo e a gravacao deles e os handlers do aprovar
# e do entregar (o selo dos registros, registro_sha256 e relatorio_sha256, so pega mexida acidental: e um sha256 sem
# segredo e nao prova quem gravou)
CODIGO = re.compile(r'renderizar\s*\(|linkados\s*\.\s*(confirmar|sessao)|confirmar\s*\.\s*sessao|'
                    r'desdobra\s*\.\s*humano|from\s+desdobra\s+import\s+[^\n;]*\bhumano\b|\bhumano\s*\.\s*\w+\s*=|'
                    r'_SELOS|console_interativo|'
                    r'desdobra\s*\.\s*entrega\s*\.\s*(aprovacao|validar|parametros|_\w)|'
                    r'from\s+desdobra\s*\.\s*entrega\s+import\s+[^\n;]*\b(aprovacao|validar|parametros)\b|'
                    r'from\s+desdobra\s+import\s+[^\n;]*\bentrega\b|'
                    r'aprovacao\s*\.\s*(registro|gravar|selo|ARQUIVO)\b|validar\s*\.\s*(gravar|_trocar|selo|relatorio)\s*\(|'
                    r'\b_(aprovar|entregar|parametros_entrega)\s*\(|'
                    # o nucleo comum da aprovacao (desdobra.entrega.nucleo_aprovar, M7b B4), os atos longos da tela
                    # (desdobra.tela.ato_aprovar e ato_render), o humano lido como atributo de outro modulo do motor
                    # (portao.humano, execucao.humano) e as funcoes que abrem a sessao e emitem o Disparo da tela
                    # (revisao do M7b, fase B). O nome de arquivo .py do nucleo segue livre (git diff, sed no fonte)
                    r'\bnucleo_aprovar\b(?!\.py)|\.\s*humano\b(?!\.py)|\babrir_sessao_tela\b|\bexigir_tela\b|'
                    r'desdobra\s*\.\s*tela\s*\.\s*ato_\w+|from\s+desdobra\s*\.\s*tela\s+import\s+[^\n;]*\bato_\w+|'
                    # os gravadores do M7 (revisao do M7a): o briefing confirmado (desdobra.briefing.salvar e a gravacao
                    # com historico), o rascunho da tela e os atos da janela (desdobra.tela.rascunho e .atos) e o modo
                    # de dados (desdobra.job.modo_dados, decisoes-v1.md, 170), pelo modulo ou pela funcao
                    r'desdobra\s*\.\s*briefing\s*\.\s*salvar\b|from\s+desdobra\s*\.\s*briefing\s+import\s+[^\n;]*\bsalvar\b|'
                    r'desdobra\s*\.\s*tela\s*\.\s*(?:rascunho|atos)\b|'
                    r'from\s+desdobra\s*\.\s*tela\s+import\s+[^\n;]*\b(?:rascunho|atos)\b|'
                    r'desdobra\s*\.\s*job\s*\.\s*modo_dados\b|from\s+desdobra\s*\.\s*job\s+import\s+[^\n;]*\bmodo_dados\b|'
                    r'gravar_com_historico|confirmar_familia|confirmar_da_tela|'
                    # a fase gravada em dia no proprio processo (desdobra.job.nucleo.renovar_fase, so do ato de spec da
                    # tela) e o estado.json pelo codigo (gravar_estado): carimbariam como em dia uma saida de fase escrita
                    # a mao, como specs/formatos-do-job.json (revisao do M7a)
                    r'\brenovar_fase\b|\bgravar_estado\b|'
                    r'\btela\s*\.\s*(?:rascunho|atos)\b|\bbriefing\s*\.\s*salvar\b|\bjob\s*\.\s*modo_dados\b|'
                    # os gravadores do motor por baixo de todos os outros (revisao do M7a): contratos.gravar e os
                    # gravar_*_atomico de desdobra.arquivos gravam qualquer arquivo do DA com o caminho que receberem
                    r'\bcontratos\s*\.\s*gravar\b|\bgravar_(?:bytes|texto|json)_atomico\b', re.IGNORECASE)
# caminho de arquivo do DA pela constante de um modulo do motor (mb.ARQUIVO, mc.ARQUIVO_LINKADOS, PASTA_HISTORICO):
# nega junto com uma escrita no comando que cita o desdobra (revisao do M7a)
CONSTANTE_DE_CAMINHO = re.compile(r'\b\w+\s*\.\s*(?:ARQUIVO|PASTA)\w*\b')
# caminho montado por partes, com a pasta do DA como parte entre aspas (Path(j, 'briefing', 'x.json'),
# Path(j) / 'briefing' / 'x.json'): nega junto com uma escrita, no comando como chegou
PARTE_DO_DA = re.compile(r'[\'"](?:briefing|derivacao|entrega|specs|render|parametros)[\'"]\s*[,/)]', re.IGNORECASE)
# entrega/** (menos o codigo-fonte do pacote: desdobra/entrega/<modulo>.py e o __pycache__ dele), o manifesto e o
# relatorio da entrega e os parametros de entrega do job (sentido da rotacao, decisoes-v1.md, 139) tambem sao do DA ou
# do motor. A excecao do codigo-fonte vale so logo depois de desdobra/ e para um nome de modulo inteiro, que termina o
# caminho (nada de aprovados/x.py, {a.jpg,x.py}, a.jpg,x.py, kv.py.jpg nem x.md)
FONTE_DO_PACOTE = r'(?:__pycache__/)?\w+(?:\.[\w-]+)?\.pyc?(?![\w.\\/{},-])'
# briefing/** e derivacao/** inteiros (M7a, fatia 1: o rascunho da tela, o historico e subpastas), com a mesma excecao
# do codigo-fonte do pacote; e o estado.json do job (decisoes-v1.md, 170: o modo de dados sai da tela, nunca do Claude)
ARQUIVOS_DO_DA = re.compile(r'(^|[\\/])((?<!skills[\\/])(?:(?<!desdobra[\\/])briefing[\\/]|briefing[\\/](?!%(f)s))|'
                            r'(?<!skills[\\/])(?:(?<!desdobra[\\/])derivacao[\\/]|derivacao[\\/](?!%(f)s))|'
                            r'estado\.json\b|'
                            r'specs[\\/]confirmacoes\.json|render[\\/][^\\/]+[\\/]'
                            r'(master\.png|render\.json|contrato\.json)|linkados-confirmados\.json|'
                            r'(?<!desdobra[\\/])entrega[\\/]|entrega[\\/](?!%(f)s)|manifesto-licenca\.json|relatorio-entrega\.json|'
                            r'parametros[\\/]entrega\.json|aval-chromium-janela\.json)' % {'f': FONTE_DO_PACOTE},
                            re.IGNORECASE)
# tela de briefing (M7a2; decisoes-v1.md, 159; proposta do M7, 160c): o Claude abre a tela ("desdobra tela abrir"
# passa), mas nao pede as rotas do servidor dela no loopback (a entrada, a api, a fonte, os assets e o controle), nao
# chama o processo de fundo nem o servidor pelo codigo e nao toca no perfil temporario do navegador da tela (pastas
# dsd-, o arquivo do dono)
ROTA_DA_TELA = re.compile(r'(?:127\.0\.0\.1|localhost|\[?::1\]?)(?::[^/\s]*)?/+(?:entrar|api|fonte|asset|controle|'
                          r'render|final|tela\.(?:js|css)|fontes\.css)\b', re.IGNORECASE)
# o perfil pelo nome, ou por curinga logo depois do prefixo dsd- (dsd-t*, dsd-*)
PERFIL_DA_TELA = re.compile(r'(?<![\w-])dsd-(?:tela|nasce)-|dsd-dono\.json|(?<![\w-])dsd-[\w-]*[*?\[]', re.IGNORECASE)
COOKIE_DA_TELA = re.compile(r'dsd_tela', re.IGNORECASE)
# o cabecalho do token CSRF das escritas da tela e a meta da pagina que o entrega (desdobra.tela.servidor)
CSRF_DA_TELA = re.compile(r'x-desdobra-csrf|dsd-csrf', re.IGNORECASE)
# despejo da memoria de um processo (rundll32 comsvcs.dll MiniDump, procdump, createdump do .NET)
DESPEJO_DE_MEMORIA = re.compile(r'minidump|procdump|createdump', re.IGNORECASE)
# teclas e cliques simulados numa janela (SendKeys do Windows Forms e do WScript.Shell, AppActivate, SendInput)
TECLAS_SIMULADAS = re.compile(r'sendkeys|sendwait|sendinput|keybd_event|mouse_event|appactivate|setcursorpos',
                              re.IGNORECASE)
CODIGO_DA_TELA = re.compile(r'desdobra\s*\.\s*tela\s*\.\s*(?:processo|servidor)\b|'
                            r'from\s+desdobra\s*\.\s*tela\s+import\s+[^\n;]*\b(?:processo|servidor)\b|'
                            # o servidor e os atos da tela pelo nome, lidos como atributo de qualquer modulo (segunda
                            # revisao do M7b, fase B: test_tela_ato_render.ts.ServidorTela, test_tela_ato_aprovar.ta)
                            r'\bServidorTela\b|\batos_do_job\b',
                            re.IGNORECASE)
# modulo de teste do plugin importado num comando (segunda revisao do M7b, fase B): os testes da tela trazem o servidor,
# os atos e os ajudantes HTTP com cookie e CSRF (_entrar, _pedir, _confirmar), e uma linha comum subiria a tela e
# aprovaria pelo caminho do clique do DA. Rodar e ler os testes seguem (pytest testes/test_x.py, cat, git diff): so o
# import do modulo pelo nome e negado
MODULO_DE_TESTE = re.compile(r'\bimport[ \t]+[\w \t,.]*?\b(?:test_\w+|conftest)\b(?!\.py)|'
                             r'\bfrom[ \t]+[\w.]*?\b(?:test_\w+|conftest)[ \t]+import\b|'
                             r'(?:import_module|__import__|run_module|run_path|spec_from_file_location|SourceFileLoader)'
                             r'\s*\([^)]*\b(?:test_\w+|conftest)\b', re.IGNORECASE)
# as marcas do Claude tiradas do ambiente (desdobra.humano.VARIAVEIS_DO_CLAUDE e as do painel): o processo da tela so
# confere essas marcas (ambiente_da_tela), e sem elas o Disparo sairia com meio tela e origem da. Nega a remocao ou a troca
# de uma marca pelo nome (o nome em maiusculas, como o ambiente o tem) e o ambiente zerado (segunda revisao do M7b,
# fase B). Ler o ambiente segue
MARCA_DO_CLAUDE = re.compile(r'\b(?:CLAUDE\w*|AI_AGENT|TERM_PROGRAM)\b')
TIRA_DO_AMBIENTE = re.compile(r'environ\s*\.\s*(?:pop|popitem|clear|update|setdefault|__delitem__)\b|'
                              r'\bdel\s+os\s*\.\s*environ|environ\s*\[[^\]]*\]\s*=(?!=)|\b(?:un|put)setenv\b|'
                              r'\bunset\b|\benv\s+(?:-\w*u\b|--unset)|Remove-Item\b[^\n|;]*\benv:|'
                              r'\$env:\w+\s*=(?!=)|SetEnvironmentVariable|\bset\s+\w+=', re.IGNORECASE)
AMBIENTE_ZERADO = re.compile(r'\benv\s+(?:-\w*i\b|--ignore-environment)|environ\s*\.\s*clear\b|UseNewEnvironment',
                             re.IGNORECASE)
ESCRITA = re.compile(r'(>|\btee\b|Set-Content|Out-File|Add-Content|\bcp\b|\bmv\b|copy|move|New-Item|\bsed\s+-i|'
                     r'write_text|write_bytes|open\s*\(|os\s*\.\s*(replace|rename|link|symlink)|shutil\s*\.|'
                     r'Rename-Item|\bren\b|\brename\b|Move-Item|Copy-Item|--saida)', re.IGNORECASE)


def _caminhos(texto):
    """Barras para /, sem /./, sem // e sem segmento/.. (o Windows resolve o .. pelo texto do caminho)."""
    s = texto.replace('\\', '/')
    while True:
        novo = re.sub(r'(?<=[^/:])/{2,}', '/', re.sub(r'/\.(?=/)', '', s))
        novo = re.sub(r'(^|/)(?!\.\.(?:/|$))[^/\s|;&<>,{}]+/\.\.(?:/|$)', r'\1', novo)
        if novo == s:
            return s
        s = novo


def normalizar(comando):
    """O comando como o shell o le, para o casamento: sem aspas, sem o escape do cmd (^) e do PowerShell (`), e com os
    caminhos normalizados (_caminhos)."""
    return _caminhos(re.sub('[\'"^`]', '', comando))


def decidir_painel(entrada, cwd_da_sessao=None):
    """'deny' sempre (decisoes-v1.md, 160): o comando do painel roda no shell do DA, e o texto dele nao diz o que ele
    faz."""
    return 'deny'


def _texto_da_entrada(entrada):
    try:
        return json.dumps(entrada, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(entrada)


def decidir_navegador(entrada):
    """'deny' quando a ferramenta de navegador ou de rede pede as rotas da tela, mexe no cookie dela ou cita o
    perfil."""
    texto = _texto_da_entrada(entrada)
    for t in (texto, _caminhos(texto)):
        if ROTA_DA_TELA.search(t) or COOKIE_DA_TELA.search(t) or PERFIL_DA_TELA.search(t) or CSRF_DA_TELA.search(t):
            return 'deny'
    return None


def decidir(evento):
    """'deny' ou None."""
    ferramenta = evento.get('tool_name') or ''
    entrada = evento.get('tool_input') or {}
    if ferramenta in FERRAMENTAS_DO_PAINEL:
        return decidir_painel(entrada, evento.get('cwd'))
    if ferramenta.startswith(PREFIXOS_DE_NAVEGADOR) or ferramenta in FERRAMENTAS_DE_REDE:
        return decidir_navegador(entrada)
    if ferramenta in FERRAMENTAS_DE_LEITURA:
        for campo in CAMPOS_DE_LEITURA:
            if PERFIL_DA_TELA.search(_caminhos(str(entrada.get(campo) or ''))):
                return 'deny'
        return None
    if ferramenta in FERRAMENTAS_DE_COMANDO:
        bruto = str(entrada.get('command') or '')
        if PARTE_DO_DA.search(bruto) and ESCRITA.search(bruto):
            return 'deny'
        for comando in (bruto, normalizar(bruto)):
            if 'desdobra' in comando and CONSTANTE_DE_CAMINHO.search(comando) and ESCRITA.search(comando):
                return 'deny'
            if SUBCOMANDO.search(comando) or SUBCOMANDO_EM_VARIAVEL.search(comando):
                return 'deny'
            if 'desdobra' in comando and CODIGO.search(comando):
                return 'deny'
            if ARQUIVOS_DO_DA.search(comando) and ESCRITA.search(comando):
                return 'deny'
            if ROTA_DA_TELA.search(comando) or PERFIL_DA_TELA.search(comando) or CODIGO_DA_TELA.search(comando):
                return 'deny'
            if CSRF_DA_TELA.search(comando) or MODULO_DE_TESTE.search(comando):
                return 'deny'
            if AMBIENTE_ZERADO.search(comando) or \
                    (MARCA_DO_CLAUDE.search(comando) and TIRA_DO_AMBIENTE.search(comando)):
                return 'deny'
            if DESPEJO_DE_MEMORIA.search(comando) or TECLAS_SIMULADAS.search(comando):
                return 'deny'
        return None
    if ferramenta in FERRAMENTAS_DE_ARQUIVO:
        caminho = str(entrada.get('file_path') or entrada.get('notebook_path') or '')
        if ARQUIVOS_DO_DA.search(_caminhos(caminho)) or PERFIL_DA_TELA.search(_caminhos(caminho)):
            return 'deny'
    return None


def main():
    try:
        evento = json.loads(sys.stdin.buffer.read().decode('utf-8') or '{}')
    except (ValueError, UnicodeDecodeError):
        return 0
    if not isinstance(evento, dict):
        return 0
    if decidir(evento) == 'deny':
        motivo = MOTIVO_PAINEL if evento.get('tool_name') in FERRAMENTAS_DO_PAINEL else MOTIVO
        saida = json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                                   'permissionDecisionReason': motivo}}, ensure_ascii=False)
        sys.stdout.buffer.write(saida.encode('utf-8') + bytes([10]))
        sys.stdout.buffer.flush()
    return 0


if __name__ == '__main__':
    sys.exit(main())
