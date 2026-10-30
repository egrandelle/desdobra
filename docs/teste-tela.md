# Teste das três formas de subir a tela de briefing

A tela de briefing (arquitetura-v1.md, 3.4 e 4.13) é um servidor HTTP local do próprio motor. Ela escuta só em 127.0.0.1, numa porta livre, e o DA a abre no navegador. A documentação do Claude Code não trata de um servidor HTTP local iniciado por skill. Por isso o M1 testa três formas, com o plugin já instalado de um marketplace git, porque o plugin carregado por caminho local roda no lugar e esconde os efeitos da cópia para o cache (docs/instalacao-teste.md).

As três formas:

| Forma | Como sobe | O que a documentação garante |
|---|---|---|
| A. Processo em segundo plano pela skill | a skill manda o Claude rodar o comando pelo Bash com `run_in_background: true` | o comando vira uma tarefa em segundo plano, listada e parada por `/tasks`; numa sessão local do terminal, do app desktop ou do VS Code, ela não tem limite de tempo; com `-p`, o limite padrão é de 30 min, ou de 10 min com o prompt passado como texto (https://code.claude.com/docs/en/tools-reference.md, Background commands) |
| B. Servidor MCP stdio do plugin | `.mcp.json` na raiz do plugin, com `command` e `args` | o Claude Code inicia os servidores do plugin ao abrir a sessão e os desliga ao fechar; no Windows, fecha a entrada padrão do servidor e encerra a árvore de processos 300 ms depois; as ferramentas se chamam `mcp__plugin_desdobra_<servidor>__<ferramenta>` (https://code.claude.com/docs/en/mcp.md, Plugin-provided MCP servers e How Claude Code stops a stdio server; https://code.claude.com/docs/en/plugins/components.md, MCP servers) |
| C. Monitor do plugin | `monitors/monitors.json` com `when: "on-skill-invoke:<skill>"` | o monitor nasce na primeira vez que a skill roda e fica até o fim da sessão; o comando roda num shell, com as permissões do usuário, fora do sandbox; cada linha impressa chega ao Claude como notificação; não sobe com `-p`; não recebe `${user_config.*}` nem `CLAUDE_PLUGIN_OPTION_<KEY>`; desligar o plugin no meio da sessão não para o monitor (https://code.claude.com/docs/en/plugins/components.md, Monitors; https://code.claude.com/docs/en/plugins/manifest-reference.md, monitors) |

## A sonda

O teste usa uma sonda no lugar da tela, porque a tela de verdade só existe no M7. A sonda:
- usa só a biblioteca padrão do Python;
- escuta só em 127.0.0.1, numa porta escolhida pelo sistema;
- responde só a `GET /api/saude`, com forma, pid, pid do pai e hora de início;
- grava `${CLAUDE_PLUGIN_DATA}/teste-tela/<forma>-<pid>.json` com a porta e atualiza o campo `vivo_em` a cada 5 s. Assim dá para saber, depois, quando o processo morreu.

Na forma B, ela fala MCP por stdio com uma ferramenta só, `abrir_tela`, que devolve a URL. Na forma C, ela imprime uma linha só, quando a porta fica pronta. Ela não lê nada do job e não serve arquivo.

O rascunho da sonda está fora do repositório, na pasta de trabalho do M1 (`m1/teste-tela/sonda_tela.py`), e já passou por um teste rápido nas formas `mcp` e `monitor`.

## Montagem, num ramo de teste

Nada disto entra no `main`. Num ramo `teste-tela`:
1. Copie a sonda para `plugins/desdobra/dev-tela/sonda_tela.py`.
2. Mude `version` em `plugin.json` para `0.1.1`, para a atualização criar uma pasta nova no cache.
3. Monte as três formas:
   - **A:** `skills/teste-tela-processo/SKILL.md`, que manda rodar, com `run_in_background: true`:
     ```
     python -I -B "${CLAUDE_PLUGIN_ROOT}/dev-tela/sonda_tela.py" --forma processo --dados "${CLAUDE_PLUGIN_DATA}"
     ```
   - **B:** `plugins/desdobra/.mcp.json`:
     ```json
     {"mcpServers": {"tela": {"command": "python",
       "args": ["-I", "-B", "${CLAUDE_PLUGIN_ROOT}/dev-tela/sonda_tela.py", "--forma", "mcp", "--dados", "${CLAUDE_PLUGIN_DATA}"]}}}
     ```
     e `skills/teste-tela-mcp/SKILL.md`, que manda chamar a ferramenta `mcp__plugin_desdobra_tela__abrir_tela`.
   - **C:** `plugins/desdobra/monitors/monitors.json`:
     ```json
     [{"name": "tela", "description": "Sonda da tela de briefing",
       "command": "python -I -B \"${CLAUDE_PLUGIN_ROOT}/dev-tela/sonda_tela.py\" --forma monitor --dados \"${CLAUDE_PLUGIN_DATA}\"",
       "when": "on-skill-invoke:teste-tela-monitor"}]
     ```
     e `skills/teste-tela-monitor/SKILL.md`, que só diz que a tela vai avisar quando estiver pronta.
4. Rode `claude plugin validate` na raiz e no plugin.
5. Faça push do ramo e instale o plugin a partir dele, com `/plugin marketplace add https://github.com/egrandelle/desdobra.git#teste-tela`.

## O que medir em cada forma

Rode cada forma numa sessão nova do app desktop (sessão Local), no Windows. Depois repita no terminal (`claude`) e com `claude -p`.

| # | Medida | Como medir |
|---|---|---|
| 1 | Sobe ou não sobe | `GET /api/saude` responde 200 no navegador do DA |
| 2 | Tempo até responder | do pedido do DA (ou da abertura da sessão, na forma B) até `iniciado_em` no arquivo da sonda |
| 3 | Pedidos de permissão | contar quantos o DA aprovou para a tela subir |
| 4 | Quem é o pai | `ppid` do arquivo da sonda contra `Get-Process -Id <ppid>` no PowerShell: o `claude`, um shell ou outro processo |
| 5 | Janela de console | se abre alguma janela preta no Windows quando a sonda sobe |
| 6 | Vida depois do turno | a sonda responde depois que o Claude termina a resposta |
| 7 | Vida em `/clear` e em `/compact` | a sonda responde depois de cada um |
| 8 | Morte ao fechar a sessão | depois de fechar a sessão, `vivo_em` para de mudar em até 10 s e o pid some de `Get-Process`. Se o processo ficar vivo, é órfão: anote |
| 9 | Morte ao fechar o app | o mesmo do item 8, fechando o app desktop inteiro |
| 10 | O que chega ao Claude | o texto que o Claude recebe: saída do Bash, resultado da ferramenta MCP ou notificação do monitor. A URL da tela, com o token da sessão, não deveria chegar ao Claude (veja abaixo) |
| 11 | Duas sessões ao mesmo tempo | duas sessões com a mesma forma: duas sondas, portas diferentes, sem erro |
| 12 | Com `-p` | se a forma sobe e quando morre num `claude -p` |
| 13 | Sem Git Bash | repetir A e C numa máquina sem Git Bash: o Monitor e os comandos em shell dependem dele no Windows (https://code.claude.com/docs/en/tools-reference.md, Monitor tool) |
| 14 | Plugin desligado no meio | desligar o plugin com a sonda viva e ver se ela para (na forma C, a documentação diz que não para) |
| 15 | Custo quando não se usa a tela | na forma B, a sonda sobe em toda sessão, mesmo sem job; medir a memória do processo parado |

Registre cada rodada numa tabela com a forma, o ambiente (desktop, terminal, `-p`), as 15 medidas e a versão do Claude Code.

## Pontos que o teste precisa decidir

- **Token da tela fora do contexto do Claude.** A tela usa um token de sessão na primeira URL, convertido em cookie HttpOnly (arquitetura-v1.md, 3.4). Nas formas B e C, o que o servidor devolve ou imprime vai para o Claude. Se a URL com o token for por ali, o Claude passa a poder falar com a tela, o que contraria a regra de que render e aprovação só partem do DA (decisoes-v1.md, 29/10, respostas às perguntas da arquitetura, 2). O teste mede se o próprio processo da tela consegue abrir o navegador do DA com a URL, sem passar a URL ao Claude, em cada forma.
- **Saída padrão.** Na forma C, toda linha impressa vira notificação. Se ela for a escolhida, o servidor da tela só imprime o envelope de saída (arquitetura-v1.md, 5.10), e nunca log de acesso, caminho ou nome de camada.
- **Processo isolado.** A tela nunca lê PSD. Ela só lê e grava arquivos de contrato do job e chama o motor para validar. A forma escolhida não muda isso.

## Critério de escolha

Vence a forma que:
1. sobe no app desktop com menos pedidos de permissão;
2. morre com a sessão, sem órfão;
3. não põe a URL com o token no contexto do Claude;
4. funciona sem depender de Git Bash.

Empate entre A e B: fica a que não sobe em toda sessão. Se nenhuma cumprir os itens 2 e 3, a tela passa a ser aberta pelo DA no terminal (`desdobra tela abrir`), e a skill só explica o passo.
