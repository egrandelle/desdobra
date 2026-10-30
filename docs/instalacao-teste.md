# Teste de instalação do plugin a partir do repositório privado

Este roteiro instala o plugin `desdobra` de um marketplace adicionado por URL git (HTTPS). Ele serve para o critério de pronto do M1 (arquitetura-v1.md, 9.2):
- o plugin instala do marketplace git;
- é copiado para o cache da versão;
- o gancho cria o ambiente Python;
- o doctor mínimo passa;
- cada passo manual é contado;
- a primeira criação do ambiente é medida contra o timeout de 600 s do gancho.

Um marketplace adicionado por caminho local carrega o plugin no lugar, sem cópia para o cache e sem fixar a versão (https://code.claude.com/docs/en/plugins/loading.md, In-place and copied plugins). Por isso o teste usa a URL git, e nunca a pasta local do repositório.

Nada aqui foi executado ainda. Adicionar o marketplace e instalar o plugin muda a configuração do usuário e depende do push do repositório, que precisa de autorização.

## O que já vale nesta máquina

| Item | Situação conferida |
|---|---|
| Claude Code | 2.1.300 (`claude --version`). O `/plugin install ... --marketplace` pede 2.1.275 ou mais novo, o `claude plugin install ... --marketplace` pede 2.1.292, e campo `options` em `userConfig` pede 2.1.271 |
| Python no PATH | `C:\Python314\python.exe`, Python 3.14.2. Também existe o atalho `python3` da Microsoft Store em `WindowsApps`; o gancho chama `python`, sem o 3 |
| Remoto do repositório | `https://github.com/egrandelle/desdobra.git`, ramo `main` |
| Credencial do git | `credential.helper = manager` (Git Credential Manager). Não há chave SSH, então o caminho é HTTPS |

## Passos manuais

Cada passo numerado é uma ação de quem instala. Anote o tempo e o que aparecer na tela em cada um.

### Uma vez, antes de instalar (Trezion)

1. **Publicar o repositório.** Fazer commit e push do `main` com o M1 para `https://github.com/egrandelle/desdobra.git`. O repositório continua privado.
2. **Guardar a credencial do GitHub no git.** O Claude Code clona com as credenciais que o git já tem e desliga os pedidos de senha do git, então a clonagem falha em vez de perguntar (https://code.claude.com/docs/en/plugins/install.md, Add a private marketplace). Num terminal comum, rode:

   ```
   git ls-remote https://github.com/egrandelle/desdobra.git
   ```

   Se o Git Credential Manager abrir o navegador, entre na conta do GitHub. O passo termina quando o comando lista o `HEAD` sem pedir nada.

### Na máquina de teste

3. **Conferir o Python no PATH do usuário.** No PowerShell, rode `python --version` e confira `Python 3.14.x`. O app desktop no Windows não lê o perfil do PowerShell, então o Python tem de estar no PATH das variáveis de ambiente do usuário ou do sistema, e o app precisa ser reaberto depois de qualquer mudança (https://code.claude.com/docs/en/desktop.md).
4. **Adicionar o marketplace.** Numa sessão do Claude Code:

   ```
   /plugin marketplace add https://github.com/egrandelle/desdobra.git
   ```

   O esperado é `Successfully added marketplace: desdobra`. O nome vem do campo `name` de `.claude-plugin/marketplace.json`. A URL vai com `https://`, porque sem o prefixo o Claude Code lê `owner/repo` do GitHub (mesma página, Add a marketplace).
5. **Instalar o plugin.** Na mesma sessão:

   ```
   /plugin install desdobra@desdobra
   ```

   Escolha o escopo do usuário. O diálogo de configuração abre e pede o **Teto do modo de dados**. Para o teste interno sem autorização de envio de material de cliente, escolha `c` (arquitetura-v1.md, 7.4).

   Pelo terminal, os passos 4 e 5 viram um comando só, que não abre o diálogo e recebe o teto por `--config` (https://code.claude.com/docs/en/plugins/components.md, Ask the user for configuration values):

   ```
   claude plugin install desdobra --marketplace https://github.com/egrandelle/desdobra.git --config teto_modo_dados=c
   ```

6. **Abrir uma sessão nova, Local, numa pasta de trabalho.** Plugins não funcionam em sessão na nuvem nem em WSL (https://code.claude.com/docs/en/desktop.md). O gancho SessionStart roda em segundo plano, e a primeira resposta do Claude espera o gancho terminar (https://code.claude.com/docs/en/hooks.md, SessionStart). Na primeira vez ele cria o ambiente. Mande uma mensagem curta e marque o tempo até a resposta.
7. **Rodar o doctor.** Na sessão:

   ```
   /desdobra:doctor
   ```

   Aprove cada pedido de permissão e conte quantos foram. O esperado é um pedido de leitura do `interpretador.json`, um do Bash para o motor e um de leitura do `doctor.json`.

**Total: 7 passos manuais na primeira instalação.** Os passos 1 e 2 são da Trezion e acontecem uma vez. Os passos 3 a 7 se repetem em cada máquina, e numa máquina com o Python já no PATH o passo 3 é só a conferência. Em cada sessão nova depois disso, o único passo manual é aprovar os pedidos de permissão das skills.

## O que conferir depois do passo 7

Os caminhos abaixo saem de https://code.claude.com/docs/en/plugins/loading.md (Find plugins on disk). O id da pasta de dados troca por `-` todo caractere que não seja letra, número, `_` ou `-` (https://code.claude.com/docs/en/plugins/components.md, Reference plugin paths and store data), então `desdobra@desdobra` vira `desdobra-desdobra`.

| Conferência | Onde | Esperado |
|---|---|---|
| Clone do marketplace | `~/.claude/plugins/marketplaces/desdobra/` | o repositório inteiro |
| Cópia da versão no cache | `~/.claude/plugins/cache/desdobra/desdobra/0.1.0/` | só a pasta `plugins/desdobra`, sem `dev/` nem `docs/` |
| Ambiente Python | `~/.claude/plugins/data/desdobra-desdobra/venv/` | venv com os pacotes do lock |
| Interpretador | `~/.claude/plugins/data/desdobra-desdobra/interpretador.json` | `plugin_root` aponta para a pasta do cache, e nunca para o repositório (defeito b do predecessor) |
| Tempo da primeira criação | `~/.claude/plugins/data/desdobra-desdobra/preparo.json`, campos `tempo_s` e `etapas` | anotar o total e o tempo de cada etapa. Se o total chegar perto de 600 s, a instalação sai do gancho e vai para o doctor (arquitetura-v1.md, 3.6) |
| Saída do pip | `~/.claude/plugins/data/desdobra-desdobra/preparo.log` | sem erro de hash |
| Doctor | `~/.claude/plugins/data/desdobra-desdobra/doctor.json` | `codigo` 0. Os dois testes do isolador com `situacao` ok e o filho que estoura com o pico abaixo do teto |
| Linha do gancho na sessão | o contexto da sessão | uma linha só, começando por `desdobra: ambiente Python criado em` |
| Sessão seguinte | abrir outra sessão e mandar uma mensagem | a linha diz `sem mudança`. A espera até a primeira resposta não pode crescer de forma perceptível |

## Teste de versão fixada e de atualização

1. Faça um commit qualquer no repositório (por exemplo, numa doc) sem mudar o `version` de `plugin.json`, e faça push.
2. Rode `claude plugin update desdobra@desdobra`. O esperado é `desdobra is already at the latest version (0.1.0).`, porque a versão do manifesto vem primeiro (https://code.claude.com/docs/en/plugins/loading.md, How Claude Code computes the version).
3. Mude o `version` para `0.1.1` sem mexer no lock, faça push e rode `claude plugin update desdobra@desdobra`. O esperado é uma pasta nova `cache/desdobra/desdobra/0.1.1/`.
4. Abra uma sessão nova. A linha do gancho tem de dizer que o motor foi religado à versão instalada, sem recriar o ambiente. O `preparo.json` mostra `acao: religar`, com só as etapas `motor` e `conferir`.
5. Mude uma linha do lock (por exemplo, numa versão nova autorizada de um pacote), faça push, atualize e abra uma sessão nova. O esperado é `acao: recriar` e o ambiente recriado do zero.
6. Anote o tempo de cada caso.

## Limpeza depois do teste

- `claude plugin uninstall desdobra@desdobra` apaga também a pasta de dados, a não ser que se passe `--keep-data` (https://code.claude.com/docs/en/plugins/manifest-reference.md, Environment variables).
- `/plugin marketplace remove desdobra` tira o marketplace.

As duas ações mudam a configuração do usuário e só rodam com autorização.

## O que pode dar errado e como reconhecer

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| A clonagem falha sem pedir senha | o git não tem credencial guardada para o GitHub | refazer o passo 2 |
| Aviso `SessionStart hook error` com `No such file` ou sem programa | o `python` não está no PATH que o app enxerga, ou o PATH aponta para o atalho da Microsoft Store | conferir `where python` no PowerShell e reabrir o app |
| A linha do gancho diz que o Python do PATH é outro | o primeiro `python` do PATH não é o 3.14 | pôr o 3.14 antes no PATH do usuário |
| A linha do gancho diz que outra sessão está preparando | duas sessões abriram juntas na primeira vez | esperar e abrir uma sessão nova; uma trava mais velha que `ambiente.trava_preparo_max_s` é retomada sozinha |
| `preparo.json` com `etapa_que_falhou: pip_lock` | rede, proxy ou hash | ler o `preparo.log`; um erro de hash nunca se contorna, e a Trezion confere o lock |
