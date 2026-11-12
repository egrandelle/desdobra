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
  - desde o M7c (P1), a leitura do job pelo Claude so pelo que a secao 7.4 da arquitetura permite: dentro de uma pasta
    de job (achada subindo do caminho pedido ate um estado.json), so PERMITIDOS_NO_JOB e sugestoes/miniaturas/**; fora
    de um job, nunca PSD, PSB, arquivo de fonte (EXTENSOES_FONTE, igual a do motor) nem a biblioteca de marcas. Vale
    para Read, Glob e Grep, para os comandos de leitura da Bash e da PowerShell (VERBO_DE_LEITURA, python -c, open()
    e para as ferramentas que sobem arquivo ou agem sem o DA (mcp__*, Artifact, SendUserFile), com a entrada inteira
    conferida como texto (TEXTO_QUE_SOBE) e cada caminho dela pela mesma regra. A busca recursiva com raiz que contem
    pasta negada e negada, menos na raiz sugestoes/ (e, na busca de conteudo, so sem o arquivo de segredos abaixo). Os
    comandos job criar, trocar-entrada e remover-entrada do motor pelo interpretador do interpretador.json passam com
    PSD ou fonte no argumento: o motor le o arquivo no processo filho isolado (7.6). Um script gravado antes e rodado
    com outro caminho continua de fora (risco declarado na 7.6). Desde a revisao do P1, no terminal (Bash, PowerShell e
    Monitor) o caminho do job e conferido com qualquer verbo (decidir_leitura_por_comando), o alvo real de uma ligacao
    simbolica e a ligacao fisica na lista permitida tambem, e o root do Artifact e base dos caminhos de files.
Escrita pelo terminal inclui redirecao, copia, movimento e troca de nome (os.replace, os.rename, shutil,
Rename-Item, ren, Move-Item, Copy-Item) e a opcao --saida do motor. O motor chamado como desdobra, desdobra.exe,
desdobra.cli ou desdobra.__main__ conta igual. O comando e conferido como chegou e normalizado (sem aspas, sem o
escape ^ do cmd e ` do PowerShell, caminhos sem ./, // e segmento/..), e subcomando numa variavel ($c, %c%) e negado; o
caminho das ferramentas de arquivo tambem e normalizado.
Com a negacao, o Claude recebe o motivo: o ato e do DA, na tela do desdobra (MOTIVO), ou a leitura nao e permitida
(MOTIVO_LEITURA). Sem negacao, o
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
import os
import re
import sys

MOTIVO = ('O desdobra recusa este comando pelo Claude: render, confirmação de linkado, confirmação de spec, '
          'confirmação de briefing, aprovação, entrega e parâmetros de entrega só partem do DA, por um clique na '
          'tela do desdobra. Diga ao DA que isso se faz na tela, onde o desdobra pergunta e grava. Não tente outro '
          'caminho para o mesmo efeito.')
# M7c, P1: a leitura do job pelo Claude so pelo que a secao 7.4 da arquitetura permite
MOTIVO_LEITURA = ('O desdobra recusa esta leitura pelo Claude. Dentro da pasta de um job, o Claude lê só o pacote para '
                  'o modelo e as sugestões, na pasta sugestoes/; o PSD, os arquivos de fonte, o laudo, o briefing, o '
                  'render, a entrega e a biblioteca de marcas não chegam ao Claude nem à API. O que o DA precisa ver '
                  'está na tela do desdobra. Não tente outro caminho para o mesmo efeito.')
MOTIVO_PAINEL = ('O desdobra recusa comandos do Claude no painel de terminal do app: o painel roda no terminal do DA, '
                 'e o que só o DA faz não parte do Claude. O que não é do DA (job proxima, doctor) segue pelas '
                 'ferramentas Bash ou PowerShell; o resto só parte do DA. Não tente outro caminho para o mesmo efeito.')
# a Monitor do Claude Code tambem roda um comando no shell (revisao do P1, M7c): as mesmas regras da Bash
FERRAMENTAS_DE_COMANDO = ('Bash', 'PowerShell', 'Monitor')
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


# ------------------------------------------------------------------ leitura do job (M7c, P1; arquitetura 7.4 e 7.6)
# as mesmas de desdobra.arquivos.EXTENSOES_FONTE (teste de igualdade): o gancho roda so com a biblioteca padrao
EXTENSOES_FONTE = ('.ttf', '.otf', '.woff', '.woff2', '.ttc', '.otc', '.dfont', '.pfb', '.pfm', '.afm', '.eot',
                   '.pfa', '.fon', '.fnt', '.bdf', '.pcf', '.suit', '.lwfn', '.t42')
EXTENSOES_NEGADAS = ('.psd', '.psb') + EXTENSOES_FONTE
EXTENSAO_NEGADA = re.compile(r'\.(?:%s)(?![\w-])' % '|'.join(re.escape(e[1:]) for e in EXTENSOES_NEGADAS),
                             re.IGNORECASE)
ESTADO_DO_JOB = 'estado.json'
# dentro de um job, o Claude le so isto (relativo a pasta do job)
PERMITIDOS_NO_JOB = ('sugestoes/pacote-modelo.json', 'sugestoes/pacote-specs.json', 'sugestoes/sugestoes.json',
                     'sugestoes/mapeamento-specs.json')
PASTA_PERMITIDA_NO_JOB = 'sugestoes/miniaturas'
RAIZ_DE_BUSCA_NO_JOB = 'sugestoes'
# a biblioteca da agencia (perfis de marca): negada em qualquer lugar
PASTA_DE_MARCAS = 'marcas'
# ferramentas que sobem arquivo local para fora ou agem sem o DA: mcp__* (navegador e uso do computador inclusive),
# Artifact e SendUserFile. A entrada inteira e conferida como texto
FERRAMENTAS_QUE_SOBEM = ('Artifact', 'SendUserFile')
PREFIXO_MCP = 'mcp__'
TEXTO_QUE_SOBE = re.compile(r'(?:^|[/\s"\'=:,(\[{])(?:entrada|laudo|render|entrega|briefing|marcas)/', re.IGNORECASE)
# comandos de leitura pela Bash e pela PowerShell, na posicao de comando (inicio, depois de |, ;, &, (, $( ou xargs)
VERBO_DE_LEITURA = re.compile(
    r'(?:^|[|;&({\n]|\$\(|\bxargs\s)\s*(?:&\s*)?(?:sudo\s+)?(?:[\w.:-]*[/\\])?'
    r'(?:cat|type|gc|get-content|head|tail|more|less|cp|copy|copy-item|cpi|select-string|sls|findstr|grep|egrep|'
    r'fgrep|rg|sed|awk|nl|xxd|od|strings|base64|import-csv)(?:\.exe)?(?![\w-])', re.IGNORECASE)
LEITURA_POR_CODIGO = re.compile(r'\bpy(?:thon[\d.]*)?(?:\.exe)?["\']?\s+(?:-[A-Za-z]+\s+)*-c\b|\bopen\s*\(|'
                                r'read_text|read_bytes', re.IGNORECASE)
BUSCA_RECURSIVA = re.compile(r'\b[ef]?grep\b[^|;&\n]*\s-(?:[A-Za-z]*[rR][A-Za-z]*|-recursive)\b|'
                             r'(?:^|[|;&(\s])rg(?:\.exe)?(?![\w-])|\bfindstr\b[^|;&\n]*\s/s\b|-Recurse\b|'
                             r'\b(?:cp|copy-item|cpi)\b[^|;&\n]*\s-(?:[A-Za-z]*[rR][A-Za-z]*)\b', re.IGNORECASE)
# revisao do P1: o que leva uma pasta inteira (copia em arvore, pacote, envio de pasta, find com -exec, xargs). Com a
# busca recursiva, a pasta citada que contem um job ou a biblioteca de marcas e negada
COPIA_EM_ARVORE = re.compile(r'(?<![\w-])(?:tar|zip|7z|7za|robocopy|xcopy|rsync|scp|rclone|gsutil|compress-archive)'
                             r'(?:\.exe)?(?![\w-])|\bfind\b[^|;&\n]*\s-(?:exec|execdir|ok)\b|\bxargs\b', re.IGNORECASE)
# revisao do P1: comandos que sobem arquivo para fora. Contam como leitura: o caminho citado e conferido mesmo que ainda
# nao exista
VERBO_DE_ENVIO = re.compile(r'(?<![\w-])(?:curl|wget|scp|sftp|ftp|rsync|rclone|gsutil|nc|ncat|bitsadmin|certutil|'
                            r'invoke-webrequest|iwr|invoke-restmethod|irm|start-bitstransfer)(?:\.exe)?(?![\w-])',
                            re.IGNORECASE)
# revisao do P1: qualquer comando do motor (python -m desdobra ...), sozinho, passa pela regra do job: e o motor que
# decide o que sai do job (7.6). O interpretador tem nome de python ou e o do interpretador.json
MOTOR_GERAL = re.compile(r'^\s*(?:&\s*)?(?P<py>"[^"]+"|\'[^\']+\'|[^\s"\']+)\s+-m\s+desdobra(?=\s|$)', re.IGNORECASE)
NOME_DE_PYTHON = re.compile(r'(?:pythonw?[\d.]*|py)(?:\.exe)?', re.IGNORECASE)
# os comandos do motor que recebem PSD ou fonte no argumento: o motor le o arquivo no processo filho isolado (7.6)
COMANDO_DO_MOTOR = re.compile(r'^\s*(?:&\s*)?(?P<py>"[^"]+"|\'[^\']+\'|[^\s"\']+)\s+-m\s+desdobra'
                              r'(?:\s+--?[\w-]+(?:[ =](?!job\b)[^\s|;&<>]+)?)*\s+job\s+'
                              r'(?:criar|trocar-entrada|remover-entrada)(?=\s|$)', re.IGNORECASE)
NOME_INTERPRETADOR = 'interpretador.json'
# a busca de cima para baixo por um job ou pela biblioteca: limitada, para o gancho responder rapido
BUSCA_PROFUNDIDADE = 4
BUSCA_LIMITE = 4000
# as pastas ocultas entram (revisao do P1: um job em .cache/ escapava do grep -r); a busca e em largura, o raso primeiro
PASTAS_PULADAS = ('node_modules', '__pycache__', 'site-packages', '.git')
# caminhos conferidos por entrada de ferramenta que sobe arquivo (texto longo nao trava o gancho)
LIMITE_DE_CANDIDATOS = 500


def _absoluto(caminho, cwd):
    """O caminho como o sistema o abre: barras normalizadas, file:// e /c/ do Git Bash viram caminho do Windows,
    relativo ao cwd do evento."""
    c = caminho.strip().strip('\'"').replace('\\', '/')
    if c.lower().startswith('file:///'):
        c = c[8:] if re.match(r'^[A-Za-z]:/', c[8:]) else c[7:]
    elif c.lower().startswith('file://'):
        c = c[7:]
    if os.name == 'nt':
        m = re.match(r'^/([A-Za-z])/(.*)$', c)
        if m:
            c = '%s:/%s' % (m.group(1).upper(), m.group(2))
    c = os.path.expanduser(c)
    if not (os.path.isabs(c) or re.match(r'^[A-Za-z]:/', c)):
        c = os.path.join(cwd or os.getcwd(), c)
    return os.path.normpath(c)


def _sem_curinga(caminho):
    """A parte do caminho antes do primeiro segmento com curinga."""
    partes = re.split(r'[\\/]', caminho)
    fixas = []
    for p in partes:
        if re.search(r'[*?\[{]', p):
            break
        fixas.append(p)
    base = os.sep.join(fixas)
    if re.match(r'^[A-Za-z]:$', base):
        base += os.sep
    return base or os.sep


def _real(caminho):
    try:
        return os.path.realpath(caminho)
    except (OSError, ValueError):
        return caminho


def pasta_do_job(caminho):
    """A pasta do job que contem o caminho: sobe ate achar um estado.json; None fora de um job."""
    d = caminho
    while True:
        try:
            if os.path.isfile(os.path.join(d, ESTADO_DO_JOB)):
                return d
        except (OSError, ValueError):
            pass
        pai = os.path.dirname(d)
        if not pai or pai == d:
            return None
        d = pai


def _relativo(caminho, job):
    try:
        rel = os.path.relpath(caminho, job).replace('\\', '/')
    except ValueError:
        return None
    return '' if rel == '.' else rel


def _rel_permitido(rel):
    r = rel.lower()
    return r in PERMITIDOS_NO_JOB or r.startswith(PASTA_PERMITIDA_NO_JOB + '/')


def _tem_marcas(caminho):
    return any(p.lower() == PASTA_DE_MARCAS for p in re.split(r'[\\/]', caminho))


def _contem_pasta_negada(raiz):
    """Busca limitada de cima para baixo: True se ha um job (estado.json) ou a biblioteca de marcas abaixo da raiz."""
    pilha, vistos = [(raiz, 0)], 0
    while pilha:
        d, nivel = pilha.pop(0)
        try:
            with os.scandir(d) as it:
                entradas = list(it)
        except (OSError, ValueError):
            continue
        for e in entradas:
            vistos += 1
            if vistos > BUSCA_LIMITE:
                return False
            nome = e.name.lower()
            try:
                if nome == ESTADO_DO_JOB and e.is_file():
                    return True
                if e.is_dir(follow_symlinks=False):
                    if nome == PASTA_DE_MARCAS:
                        return True
                    if nivel + 1 < BUSCA_PROFUNDIDADE and nome not in PASTAS_PULADAS:
                        pilha.append((e.path, nivel + 1))
            except OSError:
                continue
    return False


def _sugestoes_com_arquivo_negado(pasta, job):
    """True se ha, abaixo da pasta (dentro de sugestoes/), um arquivo fora da lista permitida (o de segredos)."""
    for raiz, _pastas, arquivos in os.walk(pasta):
        for nome in arquivos:
            p = os.path.join(raiz, nome)
            rel = _relativo(p, job)
            if rel is None or not _rel_permitido(rel) or _ligado(p):
                return True
    return False


def _ligado(caminho):
    """True se o arquivo tem mais de um nome (ligacao fisica): na lista permitida, pode ser o PSD ou a fonte do job com
    outro nome (revisao do P1). O realpath nao desfaz ligacao fisica."""
    try:
        return os.path.isfile(caminho) and os.stat(caminho).st_nlink > 1
    except (OSError, ValueError):
        return False


def _negado_pelo_nome(caminho):
    ultimo = re.split(r'[\\/]', caminho)[-1]
    return bool(EXTENSAO_NEGADA.search(ultimo)) or _tem_marcas(caminho)


def decidir_caminho(caminho, cwd, busca=None, recursiva=False):
    """'deny' ou None para um caminho pedido. busca None: ler o caminho; 'nomes': listar (Glob); 'conteudo': buscar
    no conteudo (Grep, grep -r, rg). recursiva: a busca desce nas pastas, e a pasta que contem um job ou a biblioteca de
    marcas e negada."""
    alvo = _absoluto(caminho, cwd)
    if _negado_pelo_nome(alvo):
        return 'deny'
    base = _sem_curinga(alvo)
    com_curinga = base != alvo
    real = _real(base)
    # revisao do P1: a ligacao simbolica (ou o nome curto 8.3) de nome inocente e conferida pelo alvo real
    if _negado_pelo_nome(real):
        return 'deny'
    job = pasta_do_job(real)
    if job is None:
        if busca and recursiva and os.path.isdir(real) and _contem_pasta_negada(real):
            return 'deny'
        return None
    rel = _relativo(real, job)
    if rel is None:
        return 'deny'
    if busca == 'conteudo' and os.path.isfile(real):
        busca = None
    if busca is None:
        if com_curinga:
            return None if rel.lower() == PASTA_PERMITIDA_NO_JOB or _rel_permitido(rel) else 'deny'
        return None if _rel_permitido(rel) and not _ligado(real) else 'deny'
    if rel.lower() == RAIZ_DE_BUSCA_NO_JOB or rel.lower().startswith(RAIZ_DE_BUSCA_NO_JOB + '/'):
        if busca == 'nomes':
            return None
        return 'deny' if os.path.isdir(real) and _sugestoes_com_arquivo_negado(real, job) else None
    return 'deny'


def _parece_caminho(texto, cwd):
    t = texto.strip()
    if not t or t[0] in '-$%' or re.search(r'[\'"<>|\n]', t) or len(t) > 1000:
        return False
    if '://' in t and not t.lower().startswith('file://'):
        return False
    if re.match(r'^/[A-Za-z?]{1,2}(?::.*)?$', t):  # opcao do cmd (/s, /i, /c:x)
        return False
    if re.search(r'[\\/*?]', t) or re.match(r'^[A-Za-z]:', t) or EXTENSAO_NEGADA.search(t) or t.startswith('~'):
        return True
    try:
        return os.path.exists(os.path.join(cwd or os.getcwd(), t))
    except (OSError, ValueError):
        return False


def candidatos(texto):
    """Os pedacos do texto que podem ser caminho: o que esta entre aspas e as palavras soltas."""
    achados = []
    citados = []
    for padrao in (r"'([^'\n]*)'", r'"([^"\n]*)"'):
        citados += [m.group(1) for m in re.finditer(padrao, texto)]
    achados += citados
    sem_aspas = re.sub(r"'[^'\n]*'|\"[^\"\n]*\"", ' ', texto)
    # revisao do P1: o que esta entre aspas tambem e partido em palavras ("$(<arquivo)", bash -c "cat arquivo"), e o
    # @ do curl (-F f=@arquivo, --data-binary @arquivo) sai da frente
    for parte in [sem_aspas] + citados:
        for t in re.split(r'[\s|;&<>(),=]+', parte):
            t = t.strip('{}[]`^').lstrip('@$')
            if t:
                achados.append(t)
    return [re.sub(r'^-\w+:(?!/)', '', a) for a in achados if a]


def _interpretador():
    dados = os.environ.get('CLAUDE_PLUGIN_DATA')
    if not dados:
        return None
    try:
        with open(os.path.join(dados, NOME_INTERPRETADOR), 'rb') as f:
            py = json.loads(f.read().decode('utf-8')).get('python')
    except (OSError, ValueError, AttributeError):
        return None
    return py if isinstance(py, str) and py else None


def _mesmo_arquivo(a, b):
    return os.path.normcase(os.path.normpath(a.replace('/', os.sep))) == \
        os.path.normcase(os.path.normpath(b.replace('/', os.sep)))


def comando_do_motor(comando):
    """True se o comando e so um job criar, trocar-entrada ou remover-entrada do motor pelo interpretador do
    interpretador.json, sem outro comando encadeado."""
    m = COMANDO_DO_MOTOR.match(comando)
    if not m:
        return False
    pedido = m.group('py').strip('\'"')
    py = _interpretador()
    if py:
        if not _mesmo_arquivo(pedido, py):
            return False
    elif os.environ.get('CLAUDE_PLUGIN_DATA') or not NOME_DE_PYTHON.fullmatch(re.split(r'[\\/]', pedido)[-1]):
        # sem CLAUDE_PLUGIN_DATA no processo do gancho, nao ha como conferir o interpretador: vale um com nome de python,
        # como antes da revisao do P1. Com a pasta de dados e sem um interpretador.json legivel, nada passa
        return False
    resto = comando[m.end('py'):]
    return not re.search(r'[|;&<>\n`]|\$\(', resto)


def motor_geral(comando):
    """True se o comando e so uma chamada do motor (python -m desdobra ...), sem outro comando encadeado, pelo
    interpretador do interpretador.json ou por um interpretador com nome de python."""
    m = MOTOR_GERAL.match(comando)
    if not m:
        return False
    py = m.group('py').strip('\'"')
    certo = _interpretador()
    if not (NOME_DE_PYTHON.fullmatch(re.split(r'[\\/]', py)[-1]) or (certo and _mesmo_arquivo(py, certo))):
        return False
    return not re.search(r'[|;&<>\n`]|\$\(', comando[m.end():])


def decidir_leitura_por_comando(comando, cwd):
    """'deny' quando um comando da Bash ou da PowerShell cita um caminho que o Claude nao le.

    Desde a revisao do P1, com qualquer verbo: o gancho nao conhece todos os jeitos de ler (env cat, find -exec, jq,
    [IO.File]::ReadAllText, node -e), de copiar ou ligar (robocopy, mv, tar, ln, New-Item HardLink) nem de subir
    (curl -F @, Invoke-WebRequest -InFile). Todo caminho dentro de um job fora da lista permitida e negado. Fora de um
    job, PSD, fonte e marcas sao negados quando o arquivo existe, ou sempre com um verbo de leitura ou de envio. Com
    copia em arvore ou busca recursiva, a pasta que contem um job ou a biblioteca de marcas e negada. A chamada do
    motor sozinha passa pela regra do job (o motor decide o que sai, 7.6); PSD e fonte no argumento dela so nos tres
    comandos de entrada pelo interpretador do interpretador.json."""
    if comando_do_motor(comando):
        return None
    do_motor = motor_geral(comando)
    leitura = bool(VERBO_DE_LEITURA.search(comando) or LEITURA_POR_CODIGO.search(comando) or
                   VERBO_DE_ENVIO.search(comando))
    recursiva = bool(BUSCA_RECURSIVA.search(comando) or COPIA_EM_ARVORE.search(comando))
    pasta_citada = False
    for c in candidatos(comando):
        if not _parece_caminho(c, cwd):
            continue
        alvo = _absoluto(c, cwd)
        base = _sem_curinga(alvo)
        com_curinga = base != alvo
        real = _real(base)
        if do_motor:
            if _negado_pelo_nome(alvo) or _negado_pelo_nome(real):
                return 'deny'
            continue
        e_pasta = os.path.isdir(real)
        pasta_citada = pasta_citada or e_pasta
        no_job = pasta_do_job(real) is not None
        if not (leitura or no_job):
            # sem verbo de leitura e fora de um job: so o arquivo que existe (git diff -- "*.psd" segue)
            if com_curinga or not os.path.lexists(alvo):
                continue
        busca = 'conteudo' if (e_pasta or com_curinga) and (no_job or recursiva) else None
        if decidir_caminho(c, cwd, busca=busca, recursiva=recursiva) == 'deny':
            return 'deny'
    if not do_motor and recursiva and not pasta_citada and BUSCA_RECURSIVA.search(comando):
        return decidir_caminho(cwd or os.getcwd(), cwd, busca='conteudo', recursiva=True)
    return None


def decidir_leitura(ferramenta, entrada, cwd):
    """Read, Glob e Grep pelo que a 7.4 permite."""
    if ferramenta == 'Read':
        caminho = str(entrada.get('file_path') or entrada.get('notebook_path') or '')
        return decidir_caminho(caminho, cwd) if caminho else None
    if ferramenta == 'Glob':
        padrao = str(entrada.get('pattern') or '')
        raiz = str(entrada.get('path') or cwd or os.getcwd())
        alvo = padrao if re.match(r'^(?:[A-Za-z]:)?[\\/]', padrao) else os.path.join(raiz, padrao)
        return decidir_caminho(alvo, cwd, busca='nomes', recursiva='**' in padrao)
    if ferramenta == 'Grep':
        filtro = str(entrada.get('glob') or '')
        if EXTENSAO_NEGADA.search(filtro) or _tem_marcas(filtro):
            return 'deny'
        raiz = str(entrada.get('path') or cwd or os.getcwd())
        return decidir_caminho(raiz, cwd, busca='conteudo', recursiva=True)
    return None


def _textos(valor):
    if isinstance(valor, dict):
        for k, v in valor.items():
            yield str(k)
            yield from _textos(v)
    elif isinstance(valor, (list, tuple)):
        for v in valor:
            yield from _textos(v)
    elif valor is not None:
        yield str(valor)


def decidir_envio(entrada, cwd):
    """'deny' quando a ferramenta que sobe arquivo ou age sem o DA cita PSD, fonte, uma pasta do job que o Claude nao
    le ou a biblioteca de marcas."""
    texto = _texto_da_entrada(entrada)
    for t in (texto, _caminhos(texto)):
        if EXTENSAO_NEGADA.search(t) or TEXTO_QUE_SOBE.search(t):
            return 'deny'
    # revisao do P1: o root do Artifact (e de qualquer ferramenta que o traga) e mais uma base dos caminhos relativos, e a
    # pasta citada e conferida inteira (uma ferramenta que sobe pasta leva o job junto)
    bases = [cwd]
    root = entrada.get('root')
    if isinstance(root, str) and root.strip():
        bases.append(_absoluto(root, cwd))
    conferidos = 0
    for s in _textos(entrada):
        for c in [s] + candidatos(s):
            for base in bases:
                if conferidos >= LIMITE_DE_CANDIDATOS:
                    return None
                if not _parece_caminho(c, base):
                    continue
                conferidos += 1
                busca = 'conteudo' if os.path.isdir(_real(_sem_curinga(_absoluto(c, base)))) else None
                if decidir_caminho(c, base, busca=busca, recursiva=True) == 'deny':
                    return 'deny'
    return None


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


def decidir_com_motivo(evento):
    """('deny', motivo) ou (None, None)."""
    ferramenta = evento.get('tool_name') or ''
    entrada = evento.get('tool_input') or {}
    if not isinstance(entrada, dict):
        entrada = {'valor': entrada}
    cwd = evento.get('cwd') or None
    if ferramenta in FERRAMENTAS_DO_PAINEL:
        return (decidir_painel(entrada, cwd), MOTIVO_PAINEL)
    if ferramenta.startswith(PREFIXOS_DE_NAVEGADOR) or ferramenta in FERRAMENTAS_DE_REDE:
        if decidir_navegador(entrada) == 'deny':
            return ('deny', MOTIVO)
    if ferramenta.startswith(PREFIXO_MCP) or ferramenta in FERRAMENTAS_QUE_SOBEM:
        return ('deny', MOTIVO_LEITURA) if decidir_envio(entrada, cwd) == 'deny' else (None, None)
    if ferramenta in FERRAMENTAS_DE_LEITURA:
        for campo in CAMPOS_DE_LEITURA:
            if PERFIL_DA_TELA.search(_caminhos(str(entrada.get(campo) or ''))):
                return ('deny', MOTIVO)
        return ('deny', MOTIVO_LEITURA) if decidir_leitura(ferramenta, entrada, cwd) == 'deny' else (None, None)
    if ferramenta in FERRAMENTAS_DE_COMANDO:
        bruto = str(entrada.get('command') or '')
        if _decidir_comando(bruto) == 'deny':
            return ('deny', MOTIVO)
        if decidir_leitura_por_comando(bruto, cwd) == 'deny':
            return ('deny', MOTIVO_LEITURA)
        return (None, None)
    if ferramenta in FERRAMENTAS_DE_ARQUIVO:
        caminho = str(entrada.get('file_path') or entrada.get('notebook_path') or '')
        if ARQUIVOS_DO_DA.search(_caminhos(caminho)) or PERFIL_DA_TELA.search(_caminhos(caminho)):
            return ('deny', MOTIVO)
    return (None, None)


def _decidir_comando(bruto):
    """As regras dos atos do DA e da tela num comando da Bash ou da PowerShell."""
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
        if AMBIENTE_ZERADO.search(comando) or                 (MARCA_DO_CLAUDE.search(comando) and TIRA_DO_AMBIENTE.search(comando)):
            return 'deny'
        if DESPEJO_DE_MEMORIA.search(comando) or TECLAS_SIMULADAS.search(comando):
            return 'deny'
    return None


def decidir(evento):
    """'deny' ou None."""
    return decidir_com_motivo(evento)[0]


def main():
    try:
        evento = json.loads(sys.stdin.buffer.read().decode('utf-8') or '{}')
    except (ValueError, UnicodeDecodeError):
        return 0
    if not isinstance(evento, dict):
        return 0
    decisao, motivo = decidir_com_motivo(evento)
    if decisao == 'deny':
        saida = json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                                   'permissionDecisionReason': motivo}}, ensure_ascii=False)
        sys.stdout.buffer.write(saida.encode('utf-8') + bytes([10]))
        sys.stdout.buffer.flush()
    return 0


if __name__ == '__main__':
    sys.exit(main())
