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
  - desde o M7c (M2), a escrita na biblioteca de marcas (perfil de marca, <biblioteca>/marcas/<id>/perfil-marca.json,
    so muda pelo registro do padrao da marca, ato do DA na tela): nas ferramentas de arquivo, caminho com um segmento
    marcas (pelo nome pedido, relativo ao cwd, e pelo alvo real); no terminal, caminho com um segmento marcas (ou o
    cwd dentro de marcas) junto com escrita, apagamento ou criacao de pasta (ESCRITA_EM_MARCAS), o perfil-marca.json
    em ARQUIVOS_DO_DA e o codigo que chama desdobra.marca.perfil ou desdobra.marca.registrar (CODIGO_DA_MARCA), com o
    motivo MOTIVO_MARCA. A leitura de marcas ja era negada desde o P1. Revisao do M2: o pacote desdobra.marca por
    qualquer forma de import, o pasta_marcas do motor, o segmento marcas. (o Windows tira o ponto), o nome marcas
    sozinho com verbo que apaga ou grava por codigo, e o curinga ou a ligacao que cai na biblioteca.
  - desde o M7c (S3), a escrita do Claude no que so o motor grava em sugestoes/ (sugestoes/miniaturas/**,
    pacote-modelo.json, pacote-specs.json e sugestoes-validadas.json), com o motivo MOTIVO_SUGESTOES: nas ferramentas
    de arquivo pelo caminho pedido e pelo alvo real; no terminal pelo alvo de redirecao, pelo destino de copia,
    movimento e ligacao, pelos verbos que gravam o argumento e pelo codigo que grava arquivo
    (decidir_escrito_do_motor_por_comando); e o codigo do motor que grava esses arquivos (CODIGO_DE_SUGESTOES), num
    comando que roda codigo. O Claude escreve so sugestoes.json e mapeamento-specs.json e roda "desdobra sugestao
    importar". Revisao do S3: a palavra do shell com aspas no meio, escape, chaves ou variavel; o nome montado na hora
    numa pasta sugestoes; a ligacao fisica (fsutil hardlink, mklink /H, link, cp -l e cp -s); o comando dentro de outro
    (bash -c, cmd /c, powershell -Command, Start-Process, xargs); o nome do modulo ou da funcao do motor montado em
    pedacos junto com importacao dinamica. Buscar no fonte (grep, rg, git, Select-String) e copiar dali para fora com o
    mesmo nome seguem.
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
import glob
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
# M7c, M2: o perfil de marca da biblioteca da agencia so muda pelo registro do padrao da marca, ato do DA
MOTIVO_MARCA = ('O desdobra recusa esta gravação pelo Claude: o perfil de marca da biblioteca da agência só muda '
                'quando o DA registra o padrão da marca, por um clique na tela do desdobra. Diga ao DA que isso se faz '
                'na tela, onde o desdobra mostra o que entra no perfil e grava. Não tente outro caminho para o mesmo '
                'efeito.')
# M7c, S3: o pacote para o modelo, as miniaturas e as sugestoes conferidas so o motor grava
MOTIVO_SUGESTOES = ('O desdobra recusa esta gravação pelo Claude: o pacote para o modelo, o pacote das specs, as '
                    'miniaturas e as sugestões conferidas só o motor grava. O Claude escreve só sugestoes/sugestoes.json '
                    '(e sugestoes/mapeamento-specs.json) e depois roda o comando sugestao importar do motor. Não tente '
                    'outro caminho para o mesmo efeito.')
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
                            r'parametros[\\/]entrega\.json|aval-chromium-janela\.json|'
                            # o perfil de marca (M7c, M2): marcas/<id>/perfil-marca.json, ou so o nome, com o cwd na
                            # pasta da marca
                            r'(?:marcas[\\/][^\\/]+[\\/])?perfil-marca\.json\b)' % {'f': FONTE_DO_PACOTE},
                            re.IGNORECASE)
# a biblioteca de marcas no texto de um comando: o segmento marcas de um caminho (M7c, M2). docs/marcas.md e o
# codigo-fonte desdobra/marca/ ficam de fora
# Revisao do M2: o segmento marcas. ou "marcas. " tambem conta, porque o Windows tira o ponto e o espaco do fim do
# segmento ao abrir o caminho (docs/marcas.md continua de fora)
SEGMENTO_MARCAS = re.compile(r'(?<![\w.-])marcas[.\s]*[\\/]|[\\/]marcas(?![\w.-])|[\\/]marcas\.+(?![.\w-])',
                             re.IGNORECASE)
# revisao do M2: o nome marcas sozinho (um argumento de codigo como os.path.join(b, 'marcas'), ou rm -rf marcas depois
# de um cd), negado so com um verbo que apaga, move, copia ou grava por codigo. O > sozinho nao conta, para o texto
# comum (echo as marcas > notas.txt) seguir
NOME_MARCAS = re.compile(r'(?<![\w.-])marcas\.*(?![\w.-])', re.IGNORECASE)
ESCRITA_FORTE = re.compile(r'\b(?:cp|mv|ren|rename)\b|copy|move|New-Item|Set-Content|Out-File|Add-Content|'
                           r'\bsed\s+-i|write_text|write_bytes|open\s*\(|os\s*\.\s*(?:replace|rename|link|symlink)|'
                           r'shutil\s*\.|Rename-Item|Move-Item|Copy-Item|--saida|mkdir|unlink|rmdir', re.IGNORECASE)
# curinga num caminho de comando que grava: no maximo tantos nomes conferidos pelo que existe
LIMITE_DO_CURINGA = 2000  # numero-neutro: so limita o tempo do gancho num curinga largo
# o que grava, apaga, cria pasta ou liga no terminal, alem de ESCRITA (M7c, M2): o perfil nunca e apagado
ESCRITA_EM_MARCAS = re.compile(r'(?<![\w-])(?:rm|rmdir|rd|del|erase|mkdir|md|touch|truncate|unlink|ln|mklink|ri|ni|'
                               r'Remove-Item|Clear-Content|rmtree|makedirs|remove|removedirs|chmod|attrib|icacls)'
                               r'(?![\w-])', re.IGNORECASE)
# o codigo do perfil de marca e do registro (M7c, M2; o registrar e do passo M5): o Claude nao le nem grava o perfil
# pelo codigo do motor (a leitura da biblioteca e negada desde o P1)
# Revisao do M2: qualquer referencia ao pacote desdobra.marca (por __import__, import_module, getattr, sys.modules ou
# __import__('desdobra').marca), o import do perfil com a pasta do pacote no sys.path, o arquivo do perfil rodado ou
# carregado (run_path, spec_from_file_location, python <arquivo>) e o caminho da biblioteca pelo motor
# (desdobra.biblioteca.pasta_marcas e PASTA_MARCAS), com que o texto do comando nunca traz o segmento marcas/. O codigo
# montado em variavel ou num script gravado antes continua passando (risco declarado do P1)
# revisao do M4: as funcoes da tela que carregam o perfil da biblioteca (padrao_da_marca, marca_na_tela)
CODIGO_DA_MARCA = re.compile(r'\b(?:padrao_da_marca|marca_na_tela)\b|'
                             r'desdobra[\s\'")\]]*\.\s*marca(?![\w-])|'
                             r'from\s+(?:desdobra\s*\.\s*)?marca\s+import\b|'
                             r'from\s+desdobra\s+import\s+[^\n;]*\bmarca\b|\bmarca\s*\.\s*(?:perfil|registrar)\b|'
                             r'(?:fromlist|getattr|import_module|__import__|find_spec|run_module|sys\s*\.\s*modules)'
                             r'[^\n;]*?[\'"]\.?marca(?:\.\w+)?[\'"]|'
                             r'(?:run_path|spec_from_file_location|SourceFileLoader|runpy|exec\s*\(|compile\s*\(|'
                             r'sys\s*\.\s*path|PYTHONPATH)[^\n]*marca(?![\w-])|'
                             r'marca[\\/][^\n]*(?:\bimport\s+(?:perfil|registrar)\b|from\s+(?:perfil|registrar)\s+import)|'
                             r'(?:^|[\s|;&(\'"])(?:[^\s|;&\'"]*[\\/])?py(?:thon[\d.]*)?(?:\.exe)?[\'"]?\s+(?:-\S+\s+)*'
                             r'[^\s|;&]*marca[\\/]+(?:perfil|registrar)|'
                             r'\bpasta_marcas\b|\bPASTA_MARCAS\b',
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
# leva 4: aceita as opcoes do interpretador sem argumento antes de -m (a forma das skills e "PY" -I -B -m desdobra)
OPCOES_DO_INTERPRETADOR = r'(?:\s+-[IBEsSuOPq]+)*'
MOTOR_GERAL = re.compile(r'^\s*(?:&\s*)?(?P<py>"[^"]+"|\'[^\']+\'|[^\s"\']+)' + OPCOES_DO_INTERPRETADOR +
                         r'\s+-m\s+desdobra(?=\s|$)', re.IGNORECASE)
NOME_DE_PYTHON = re.compile(r'(?:pythonw?[\d.]*|py)(?:\.exe)?', re.IGNORECASE)
# os comandos do motor que recebem PSD ou fonte no argumento: o motor le o arquivo no processo filho isolado (7.6)
COMANDO_DO_MOTOR = re.compile(r'^\s*(?:&\s*)?(?P<py>"[^"]+"|\'[^\']+\'|[^\s"\']+)' + OPCOES_DO_INTERPRETADOR +
                              r'\s+-m\s+desdobra'
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


# ------------------------------------------------------------------ escritos do motor em sugestoes/ (M7c, S3)
# o que so o motor grava em sugestoes/: os dois pacotes, a pasta das miniaturas e as sugestoes conferidas. O Claude
# escreve so sugestoes.json e mapeamento-specs.json
NOMES_DO_MOTOR_EM_SUGESTOES = ('pacote-modelo.json', 'pacote-specs.json', 'sugestoes-validadas.json')
PASTA_DE_SUGESTOES = 'sugestoes'
PASTA_DE_MINIATURAS = 'miniaturas'
# verbos do terminal: o destino e o ultimo argumento (ou o de -t, -Destination), ou todo argumento e gravado
VERBOS_DESTINO_NO_FIM = ('cp', 'copy', 'mv', 'move', 'copy-item', 'cpi', 'move-item', 'mi', 'rename-item', 'rni', 'ren',
                         'rename', 'robocopy', 'xcopy', 'install', 'rsync', 'scp', 'ditto')
# revisao do S3: fsutil (fsutil hardlink create) e link entram; a ligacao fisica a um escrito do motor deixa o Claude
# gravar nele por outro nome
VERBOS_QUE_GRAVAM = ('tee', 'tee-object', 'set-content', 'sc', 'out-file', 'add-content', 'ac', 'new-item', 'ni',
                     'touch', 'mkdir', 'md', 'truncate', 'clear-content', 'clc', 'ln', 'mklink', 'dd', 'export-csv',
                     'link', 'fsutil')
VERBOS_DE_PASTA = ('cd', 'chdir', 'pushd', 'set-location', 'sl')
VERBOS_QUE_DESFAZEM_PASTA = ('popd', 'pop-location')
OPCOES_DE_DESTINO = ('-t', '--target-directory', '-destination', '-dest', '-newname')
# revisao do S3: a copia que liga em vez de copiar (cp -l, cp -s, cp -al, --link, --symbolic-link) confere todo argumento
OPCAO_DE_LIGACAO = re.compile(r'^(?:-[a-zA-Z]*[ls][a-zA-Z]*|--link|--symbolic-link)$')
VERBOS_QUE_LIGAM_COM_OPCAO = ('cp',)
# revisao do S3: o comando dentro de outro (bash -c, cmd /c, powershell -Command, Start-Process, xargs) e conferido de
# novo, na mesma pasta. O que vem depois da opcao do embrulho e o comando; sem ela, os argumentos sem as opcoes
VERBOS_QUE_EMBRULHAM = ('bash', 'sh', 'zsh', 'dash', 'ksh', 'fish', 'busybox', 'cmd', 'powershell', 'pwsh', 'wsl',
                        'start', 'call', 'xargs', 'start-process', 'saps', 'invoke-expression', 'iex', 'nice',
                        'nohup', 'runas', 'parallel')
OPCOES_DO_EMBRULHO = ('-c', '/c', '/k', '/r', '-command', '-commandwithargs')
PROFUNDIDADE_DO_EMBRULHO = 4  # numero-neutro: so limita a conferencia de comando dentro de comando
# revisao do S3: a palavra do shell cola os pedacos entre aspas ao resto (sugestoes-"validadas".json e uma palavra so)
PALAVRA_DO_SHELL = re.compile(r'(?:"[^"]*"|\'[^\']*\'|[^\s"\'])+')
REDIRECAO = re.compile(r'(?:^|[^<>\d])\d?\*?>>?\|?\s*((?:"[^"]*"|\'[^\']*\'|[^\s|;&<>"\'])+)')
SO_A_REDIRECAO = re.compile(r'\d?\*?>>?\|?\s*(?:"[^"]*"|\'[^\']*\'|[^\s|;&<>"\'])+')
SEPARADOR_DE_COMANDO = re.compile(r'\|\|?|&&|;|\n|(?<![>\d])&(?!\d)')
# revisao do S3: o nome que o shell monta na hora (variavel, substituicao de comando, curinga); na pasta do cd, chaves
NOME_MONTADO = re.compile(r'[$%`*?\[]')
PASTA_MONTADA = re.compile(r'[$%`*?\[{]')
LIMITE_DAS_CHAVES = 64  # numero-neutro: so limita a expansao de chaves que o gancho confere
# codigo que grava arquivo (Python, PowerShell, Node): nega com um caminho protegido em qualquer ponto do comando
CODIGO_QUE_GRAVA = re.compile(r'write_text|write_bytes|WriteAll\w*|AppendAll\w*|'
                              r'\bFile\s*\]?\s*::\s*(?:Create|Open\w*|Copy|Move|Replace)|'
                              r'\bos\s*\.\s*(?:replace|rename|renames|link|symlink|makedirs|mkdir|open)\b|shutil\s*\.|'
                              r'\.\s*(?:touch|mkdir|hardlink_to|symlink_to)\s*\(|\)\s*\.\s*(?:rename|replace)\s*\(|'
                              r'open\s*\([^)]*[\'"][rbt]*[wax][rbt+]*[\'"]|'
                              r'\b(?:writeFile|appendFile|copyFile|writeFileSync|appendFileSync|copyFileSync)\b|'
                              r'\bgravar\w*\s*\(',
                              re.IGNORECASE)
# o codigo do motor que grava esses arquivos (os modulos e as funcoes que gravam): o Claude roda so a linha de comando
# (sugestao pacote, sugestao importar)
CODIGO_DE_SUGESTOES = re.compile(
    r'desdobra[\s\'")\]]*\.\s*sugestao\s*\.\s*(?:importar|pacote|miniaturas|specs)(?![\w-])|'
    r'from\s+desdobra\s*\.\s*sugestao\s+import\s+[^\n;]*\b(?:importar|pacote|miniaturas|specs)\b|'
    r'(?:fromlist|getattr|import_module|__import__|find_spec|run_module|sys\s*\.\s*modules)[^\n;]*?'
    r'[\'"]\.?sugestao\.(?:importar|pacote|miniaturas|specs)[\'"]|'
    r'\b(?:gravar_pacote|refazer_pacotes?|gravar_miniaturas|gravar_validadas|apagar_escritos_do_claude)\b',
    re.IGNORECASE)
# revisao do S3: o nome do modulo ou da funcao montado em pedacos ('desdobra.sug' + 'estao', '_'.join([...])). Com
# importacao dinamica no comando, o texto e conferido em minusculas, so com letras e algarismos
IMPORTACAO_DINAMICA = re.compile(r'import_module|__import__|importlib|runpy|run_module|run_path|find_spec|spec_from|'
                                 r'SourceFileLoader|pkgutil|zipimport|sys\s*\.\s*modules|getattr|__dict__|'
                                 r'\b(?:exec|eval|compile|globals|vars)\s*\(', re.IGNORECASE)
CODIGO_DE_SUGESTOES_ACHATADO = re.compile(r'sugestao(?:importar|pacote|miniaturas|specs)|gravarpacote|'
                                          r'refazerpacotes?|gravarminiaturas|gravarvalidadas|apagarescritosdoclaude')
# a linha de comando do motor e o pytest nao rodam codigo escrito no comando: saem do texto antes da conferencia
CHAMADA_DO_MOTOR_OU_DO_TESTE = re.compile(r'-m\s+(?:desdobra|pytest)\b[^\n|;&]*', re.IGNORECASE)
# revisao do S3: comando so de busca e leitura nao roda codigo; o nome da funcao nele e busca no fonte
VERBOS_SO_DE_LEITURA = ('grep', 'egrep', 'fgrep', 'rg', 'ag', 'ack', 'findstr', 'select-string', 'sls', 'git', 'cat',
                        'type', 'get-content', 'gc', 'head', 'tail', 'less', 'more', 'ls', 'dir', 'get-childitem',
                        'gci', 'wc', 'sort', 'uniq', 'diff', 'fc', 'pwd', 'which', 'where', 'get-command', 'gcm')


def _partes_do_caminho(caminho):
    """Os segmentos do caminho em minusculas, sem o ponto e o espaco do fim (o Windows os tira) e sem o fluxo
    alternativo do NTFS (nome:fluxo)."""
    partes = [p for p in re.split(r'[\\/]', caminho) if p]
    saida = []
    for i, p in enumerate(partes):
        if i > 0 or not re.match(r'^[A-Za-z]:$', p):
            p = p.split(':')[0]
        saida.append(p.rstrip(' .').lower())
    return saida


def _escrito_do_motor(caminho):
    """True se o caminho absoluto e um arquivo que so o motor grava em sugestoes/ (ou a pasta das miniaturas)."""
    partes = _partes_do_caminho(caminho)
    for i in range(len(partes) - 1):
        if partes[i] != PASTA_DE_SUGESTOES:
            continue
        if partes[i + 1] == PASTA_DE_MINIATURAS:
            return True
        if partes[i + 1] in NOMES_DO_MOTOR_EM_SUGESTOES and i + 1 == len(partes) - 1:
            return True
    return False


def _desaspar(palavra):
    """A palavra como o shell a entrega: sem as aspas (inclusive as do meio) e sem o escape do PowerShell (`)."""
    pedacos = [next(g for g in m.groups() if g is not None)
               for m in re.finditer(r'"([^"]*)"|\'([^\']*)\'|([^"\']+)', palavra)]
    return re.sub(r'`(.)', r'\1', ''.join(pedacos))


def _chaves(palavra):
    """As palavras que a expansao de chaves da Bash produz ({a,b}), ate LIMITE_DAS_CHAVES."""
    m = re.search(r'\{([^{}]*,[^{}]*)\}', palavra)
    if not m:
        return [palavra]
    saida = []
    for parte in m.group(1).split(','):
        for e in _chaves(palavra[:m.start()] + parte + palavra[m.end():]):
            saida.append(e)
            if len(saida) >= LIMITE_DAS_CHAVES:
                return saida
    return saida


def _segmentos(comando):
    """Os comandos encadeados (|, ||, &&, ;, &, quebra de linha), sem partir o que esta entre aspas."""
    partes, atual, aspa, i = [], [], None, 0
    while i < len(comando):
        ch = comando[i]
        if aspa:
            aspa = None if ch == aspa else aspa
        elif ch in '"\'':
            aspa = ch
        else:
            m = SEPARADOR_DE_COMANDO.match(comando, i)
            if m and m.end() > i:
                partes.append(''.join(atual))
                atual = []
                i = m.end()
                continue
        atual.append(ch)
        i += 1
    partes.append(''.join(atual))
    return partes


def _cita_escrito_do_motor(comando):
    """True se o comando cita, de qualquer jeito, um dos arquivos do motor ou a pasta das miniaturas."""
    for t in (re.sub('[\'"^`]', '', comando), re.sub('[\'"^`\\\\]', '', comando)):
        t = t.lower().replace('\\', '/')
        if any(n in t for n in NOMES_DO_MOTOR_EM_SUGESTOES) or 'sugestoes/miniaturas' in t:
            return True
    return False


def _pasta_e_de_sugestoes(pasta):
    return any(PASTA_DE_SUGESTOES in _partes_do_caminho(p) for p in (pasta, _real(pasta)))


def _protegido(caminho, cwd, pelo_nome=False, cita=False):
    """True se a palavra do shell, como destino de escrita, cai num escrito do motor em sugestoes/: pelo nome pedido,
    pelo alvo real (ligacao simbolica de nome inocente) e pelo curinga que se expande para ele.

    Revisao do S3: a palavra chega crua; as chaves se expandem, as aspas do meio e o escape do PowerShell saem, e o
    escape da Bash (\\) e tirado numa segunda leitura. O nome montado na hora (variavel, substituicao de comando,
    curinga) conta quando a parte fixa dele cai numa pasta sugestoes, quando o comando cita um dos arquivos do motor
    (cita) ou quando a pasta e incerta (pelo_nome). pelo_nome: o nome sozinho de um dos arquivos do motor conta em
    qualquer pasta (cd que o gancho nao acompanha, codigo que muda de pasta)."""
    bruto = caminho.strip()
    if not bruto:
        return False
    for expandido in _chaves(bruto):
        limpo = _desaspar(expandido).strip()
        if not limpo or limpo.startswith('-') or re.match(r'^/[A-Za-z?]{1,2}(?::.*)?$', limpo):
            continue
        montado = bool(NOME_MONTADO.search(expandido))
        for c in {limpo, limpo.replace('\\', '')} if '\\' in limpo else {limpo}:
            if pelo_nome:
                partes = _partes_do_caminho(c)
                if partes and partes[-1] in NOMES_DO_MOTOR_EM_SUGESTOES:
                    return True
            try:
                alvo = _absoluto(c, cwd)
            except (OSError, ValueError):
                continue
            if _escrito_do_motor(alvo) or _escrito_do_motor(_real(alvo)):
                return True
            if montado:
                fixo = NOME_MONTADO.split(c)[0]
                corte = max(fixo.rfind('/'), fixo.rfind('\\'))
                try:
                    pasta = _absoluto(fixo[:corte + 1] if corte >= 0 else '.', cwd)
                except (OSError, ValueError):
                    return True
                if cita or pelo_nome or _pasta_e_de_sugestoes(pasta):
                    return True
            if _sem_curinga(alvo) != alvo:
                vistos = 0
                try:
                    for achado in glob.iglob(alvo):
                        vistos += 1
                        if vistos > LIMITE_DO_CURINGA:
                            return False
                        if _escrito_do_motor(achado) or _escrito_do_motor(_real(achado)):
                            return True
                except (OSError, ValueError, re.error):
                    return False
    return False


def decidir_escrito_do_motor_por_arquivo(caminho, cwd):
    """'deny' quando uma ferramenta de arquivo grava o que so o motor grava em sugestoes/ (M7c, S3)."""
    if not caminho.strip():
        return None
    alvo = _absoluto(caminho, cwd)
    return 'deny' if _escrito_do_motor(alvo) or _escrito_do_motor(_real(alvo)) else None


def _palavras(segmento):
    """As palavras do segmento como o shell as entrega (sem aspas)."""
    return [_desaspar(p) for p in PALAVRA_DO_SHELL.findall(segmento)]


def _verbo(palavras):
    """(indice, verbo em minusculas sem pasta e sem .exe) do comando do segmento."""
    for i, p in enumerate(palavras):
        nome = re.split(r'[\\/]', p.strip('&('))[-1].lower()
        if nome in ('', 'sudo', 'env', 'command', 'builtin', 'exec', 'time', 'nohup'):
            continue
        return i, re.sub(r'\.exe$', '', nome)
    return None, ''


def _opcao(p):
    return p.startswith('-') or bool(re.match(r'^/[A-Za-z?]{1,2}(?::.*)?$', p))


def _comando_embrulhado(args):
    """O comando que vai dentro do embrulho: o que vem depois de -c, /c ou -Command; sem a opcao, os argumentos sem as
    opcoes (Start-Process cmd -ArgumentList '/c ...', xargs -I{} cp ...)."""
    for k, a in enumerate(args):
        if a.lower() in OPCOES_DO_EMBRULHO:
            return ' '.join(args[k + 1:])
    return ' '.join(a for a in args if not a.startswith('-'))


def _roda_codigo(comando):
    """True se algum comando encadeado nao e so de busca ou leitura (grep, rg, git, cat, Select-String)."""
    for segmento in _segmentos(comando):
        i, verbo = _verbo(_palavras(segmento))
        if i is not None and verbo not in VERBOS_SO_DE_LEITURA:
            return True
    return False


def _codigo_do_motor_que_grava(comando):
    """True quando o comando roda o codigo do motor que grava em sugestoes/: o modulo ou a funcao pelo nome, ou montado
    em pedacos junto com importacao dinamica (revisao do S3). A linha de comando do motor e o pytest saem do texto
    antes; busca no fonte nao roda codigo e segue."""
    if not _roda_codigo(comando):
        return False
    texto = CHAMADA_DO_MOTOR_OU_DO_TESTE.sub(' ', comando)
    for c in (texto, normalizar(texto)):
        if CODIGO_DE_SUGESTOES.search(c):
            return True
    if IMPORTACAO_DINAMICA.search(texto):
        return bool(CODIGO_DE_SUGESTOES_ACHATADO.search(re.sub(r'[^a-z0-9]', '', texto.lower())))
    return False


def decidir_escrito_do_motor_por_comando(comando, cwd, _profundidade=0, _incerta=None, _cita=None):
    """'deny' quando um comando da Bash, da PowerShell ou da Monitor grava o que so o motor grava em sugestoes/ (M7c,
    S3): redirecao, o destino de copia, movimento, troca de nome ou ligacao, os verbos que gravam o argumento (tee,
    Set-Content, Out-File, New-Item, touch, mkdir, sed -i, fsutil, link, cp -l), o codigo que grava arquivo com o
    caminho no comando e o codigo do motor que grava esses arquivos. O cd feito antes no mesmo comando muda a pasta dos
    caminhos relativos; o cd que o gancho nao acompanha (variavel, curinga, popd) deixa a pasta incerta, e o nome
    sozinho de um dos arquivos do motor passa a contar. O comando dentro de outro (bash -c, cmd /c) e conferido de
    novo. Ler e copiar dali para fora seguem."""
    if _profundidade == 0:
        if _codigo_do_motor_que_grava(comando):
            return 'deny'
        if CODIGO_QUE_GRAVA.search(comando):
            for c in candidatos(comando)[:LIMITE_DE_CANDIDATOS]:
                if _protegido(c, cwd, pelo_nome=True):
                    return 'deny'
    cita = _cita_escrito_do_motor(comando) if _cita is None else _cita
    incerta = (not cwd) if _incerta is None else _incerta
    pasta = cwd
    for segmento in _segmentos(comando):
        for m in REDIRECAO.finditer(segmento):
            if _protegido(m.group(1), pasta, incerta, cita):
                return 'deny'
        cruas = PALAVRA_DO_SHELL.findall(SO_A_REDIRECAO.sub(' ', segmento))
        palavras = [_desaspar(p) for p in cruas]
        i, verbo = _verbo(palavras)
        if i is None:
            continue
        args, crus = palavras[i + 1:], cruas[i + 1:]
        livres = [c for a, c in zip(args, crus) if not _opcao(a)]
        if verbo in VERBOS_DE_PASTA:
            if not livres:
                pasta = os.path.expanduser('~')
            elif PASTA_MONTADA.search(livres[0]) or _desaspar(livres[0]) == '-':
                incerta = True
            else:
                pasta = _absoluto(_desaspar(livres[0]), pasta)
            continue
        if verbo in VERBOS_QUE_DESFAZEM_PASTA:
            incerta = True
            continue
        if verbo in VERBOS_QUE_EMBRULHAM:
            dentro = _comando_embrulhado(args)
            if _profundidade >= PROFUNDIDADE_DO_EMBRULHO:
                if _cita_escrito_do_motor(dentro):
                    return 'deny'
            elif dentro and decidir_escrito_do_motor_por_comando(dentro, pasta, _profundidade + 1, incerta,
                                                                cita) == 'deny':
                return 'deny'
            continue
        liga = verbo in VERBOS_QUE_LIGAM_COM_OPCAO and any(OPCAO_DE_LIGACAO.match(a) for a in args)
        if liga or verbo in VERBOS_QUE_GRAVAM or (verbo == 'sed' and any(re.match(r'^-\w*i', a) for a in args)):
            if any(_protegido(c, pasta, incerta, cita) for c in livres):
                return 'deny'
            continue
        if verbo in VERBOS_DESTINO_NO_FIM and livres:
            destinos = [crus[k + 1] for k, a in enumerate(args[:-1]) if a.lower() in OPCOES_DE_DESTINO]
            destinos = destinos or [livres[-1]]
            fontes = [c for c in livres if c not in destinos]
            for d in destinos:
                if _protegido(d, pasta, incerta, cita):
                    return 'deny'
                d_limpo = _desaspar(d)
                d_abs = _absoluto(d_limpo, pasta)
                if os.path.isdir(d_abs) or d_limpo.endswith(('/', '\\')):
                    for f in fontes:
                        nome = re.split(r'[\\/]', _desaspar(f).rstrip('/\\'))[-1]
                        if nome and _protegido(os.path.join(d_abs, nome), pasta):
                            return 'deny'
    return None


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
    # revisao do M2: sem o ponto e o espaco do fim do segmento, que o Windows tira ao abrir (marcas. e marcas)
    return any(p.rstrip(' .').lower() == PASTA_DE_MARCAS for p in re.split(r'[\\/]', caminho))


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


def decidir_marca_por_arquivo(caminho, cwd):
    """'deny' quando uma ferramenta de arquivo grava na biblioteca de marcas (M7c, M2): caminho com um segmento marcas,
    pelo nome pedido, relativo ao cwd do evento, e pelo alvo real (ligacao simbolica de nome inocente)."""
    if not caminho.strip():
        return None
    if ARQUIVOS_DO_DA.search(_caminhos(caminho)) and re.search(r'perfil-marca\.json', caminho, re.IGNORECASE):
        return 'deny'
    alvo = _absoluto(caminho, cwd)
    if _tem_marcas(alvo) or _tem_marcas(_real(alvo)):
        return 'deny'
    return None


def decidir_marca_por_comando(comando, cwd):
    """'deny' quando um comando da Bash, da PowerShell ou da Monitor grava, apaga ou cria pasta na biblioteca de marcas,
    ou chama o codigo do perfil de marca ou do registro (M7c, M2)."""
    cwd_em_marcas = bool(cwd) and (_tem_marcas(cwd) or _tem_marcas(_real(cwd)))
    escreve_algum = False
    for c in (comando, normalizar(comando)):
        if CODIGO_DA_MARCA.search(c):
            return 'deny'
        escreve = ESCRITA.search(c) or ESCRITA_EM_MARCAS.search(c)
        escreve_algum = escreve_algum or bool(escreve)
        if escreve and (SEGMENTO_MARCAS.search(c) or cwd_em_marcas or re.search(r'perfil-marca\.json\b', c, re.I)):
            return 'deny'
        if (ESCRITA_EM_MARCAS.search(c) or ESCRITA_FORTE.search(c)) and NOME_MARCAS.search(c):
            return 'deny'
    if escreve_algum and _caminho_cai_em_marcas(comando, cwd):
        return 'deny'
    return None


def _caminho_cai_em_marcas(comando, cwd):
    """Revisao do M2: um caminho do comando que, pelo que existe, cai na biblioteca de marcas (o curinga que a expande,
    rm -rf <bib>/marc*, e a ligacao de nome inocente que aponta para ela)."""
    vistos = 0
    for c in candidatos(comando)[:LIMITE_DE_CANDIDATOS]:
        if not _parece_caminho(c, cwd):
            continue
        alvo = _absoluto(c, cwd)
        if _tem_marcas(alvo) or _tem_marcas(_real(alvo)):
            return True
        if _sem_curinga(alvo) == alvo:
            continue
        try:
            achados = glob.iglob(alvo)
            for achado in achados:
                vistos += 1
                if vistos > LIMITE_DO_CURINGA:
                    return False
                if _tem_marcas(achado) or _tem_marcas(_real(achado)):
                    return True
        except (OSError, ValueError, re.error):
            continue
    return False


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
        if decidir_marca_por_comando(bruto, cwd) == 'deny':
            return ('deny', MOTIVO_MARCA)
        if _decidir_comando(bruto) == 'deny':
            return ('deny', MOTIVO)
        if decidir_leitura_por_comando(bruto, cwd) == 'deny':
            return ('deny', MOTIVO_LEITURA)
        if decidir_escrito_do_motor_por_comando(bruto, cwd) == 'deny':
            return ('deny', MOTIVO_SUGESTOES)
        return (None, None)
    if ferramenta in FERRAMENTAS_DE_ARQUIVO:
        caminho = str(entrada.get('file_path') or entrada.get('notebook_path') or '')
        if decidir_marca_por_arquivo(caminho, cwd) == 'deny':
            return ('deny', MOTIVO_MARCA)
        if ARQUIVOS_DO_DA.search(_caminhos(caminho)) or PERFIL_DA_TELA.search(_caminhos(caminho)):
            return ('deny', MOTIVO)
        if decidir_escrito_do_motor_por_arquivo(caminho, cwd) == 'deny':
            return ('deny', MOTIVO_SUGESTOES)
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
