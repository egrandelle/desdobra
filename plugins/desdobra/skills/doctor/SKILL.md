---
description: Confere o ambiente do desdobra (Python, versões fixadas, psd-tools com o compositor, fontTools, Playwright e pypdfium2, o Chromium fixado com um teste de fonte, o autoteste do render com a fonte gerada pelo motor, isolador de memória e teto do modo de dados) e diz o que fazer quando algo falha. Use quando o DA pedir para conferir a instalação, quando outra skill do desdobra mandar rodar o doctor ou quando o motor não responder.
---

# Doctor do desdobra

Quem confere o ambiente é o motor. Você roda um comando e explica o resultado ao DA em português simples.

Regras desta skill:
- Nunca calcule geometria, posição, escala ou limite.
- Nunca dispare render nem aprovação.
- Nunca leia PSD, PSB ou arquivo de fonte, nem peça para ver um.
- Nunca instale pacote, nunca mexa na pasta `venv` e nunca edite arquivo do plugin. A correção é sempre a que o motor diz no O QUE FAZER.

## Passos

1. Leia `${CLAUDE_PLUGIN_DATA}/interpretador.json` com a ferramenta Read.
   - Se ele não existir, o ambiente ainda não foi preparado. Leia `${CLAUDE_PLUGIN_DATA}/preparo.json`, se existir, e diga ao DA em que etapa o preparo parou (campo `etapa_que_falhou`) e que o detalhe técnico está em `${CLAUDE_PLUGIN_DATA}/preparo.log`. Se nenhum dos dois existir, peça ao DA para conferir se o Python 3.14 está no PATH do usuário e para abrir uma sessão nova do Claude Code. Pare aqui.
   - Guarde o campo `python`. Ele é o caminho do Python do ambiente, chamado de PY abaixo.
2. Compare o campo `plugin_root` com `${CLAUDE_PLUGIN_ROOT}`, sem diferenciar maiúsculas de minúsculas nem barra normal de barra invertida. Se forem diferentes, o plugin foi atualizado depois do preparo: peça ao DA para abrir uma sessão nova e pare.
3. O teto do modo de dados configurado é `${user_config.teto_modo_dados}`. Chame esse valor de TETO. Se ele não for exatamente `a`, `b` ou `c`, o teto não foi configurado: avise o DA que ele configura em `/plugin`, aba Installed, plugin desdobra, opção Configure, e rode o passo 4 sem a parte `--teto-modo-dados TETO`.
4. Rode numa linha só, pela ferramenta Bash:

   ```
   "PY" -I -B -m desdobra --envelope --teto-modo-dados TETO doctor
   ```

   Na ferramenta PowerShell, ponha `& ` antes do caminho entre aspas. O teste do isolador, o teste de fonte no navegador e o autoteste do render levam alguns segundos. O autoteste do render desenha uma página de referência com uma fonte que o próprio motor gera e compara com a imagem gravada no plugin: ele não usa fonte do DA nem dispara render de job.
5. A saída é uma linha JSON, o envelope do motor. Explique pelo campo `codigo`:
   - `0`: o ambiente está pronto. Se `contagens.avisos` for maior que zero, conte quantos avisos há.
   - `3`: alguma verificação falhou. Diga ao DA o que está no campo `o_que_fazer`, com as palavras do motor.
   - `9`: este sistema ainda não tem o isolador de memória. O desdobra só lê PSD no Windows por enquanto.
   - `1` ou `2`: erro do motor. Rode o passo 4 de novo uma vez. Se o erro continuar, diga ao DA, sem passar comando a ele, que a conferência da instalação travou e que isso é um caso para avisar a Trezion.
6. Para o detalhe de cada verificação, leia `${CLAUDE_PLUGIN_DATA}/doctor.json`. Ele só tem fatos do ambiente (versões, caminhos da instalação, números do teste do isolador), sem nada de job. Liste ao DA só as verificações com `situacao` igual a `falha` ou `aviso`, com o título e o `o_que_fazer` de cada uma.

Lembre o DA de não usar `/feedback`, `/bug` nem `/share` numa sessão com job de cliente, porque esses comandos enviam a conversa.
