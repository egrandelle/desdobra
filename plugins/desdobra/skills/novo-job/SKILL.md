---
description: Cria um job do desdobra a partir do PSD ou PSB do KV e roda a leitura isolada do arquivo, com o laudo camada por camada. Use quando o DA quiser começar um desdobramento novo de OOH, DOOH ou banner estático.
argument-hint: "[caminho do PSD ou PSB] [pasta nova do job]"
disable-model-invocation: true
---

# Novo job do desdobra

Neste marco, a skill só cria o job, roda a leitura do PSD e explica o laudo. As fases seguintes (fontes, specs, tela de briefing) entram nos próximos marcos.

Regras desta skill:
- Nunca calcule geometria, posição, escala, corpo ou limite. Quem mede é o motor.
- Nunca dispare render nem aprovação.
- Nunca leia, abra ou copie o PSD, o PSB, arquivo de fonte ou imagem do job. Você só passa o caminho do PSD para o motor.
- Nunca leia `laudo/laudo.json` nem outro arquivo da pasta do job. Tudo o que você sabe do job vem do envelope que o motor imprime.
- Nunca escolha o modo de dados pelo DA.

## Passos

1. Leia `${CLAUDE_PLUGIN_DATA}/interpretador.json` com a ferramenta Read. Se ele não existir, diga ao DA para rodar `/desdobra:doctor` e pare. Guarde o campo `python`, chamado de PY abaixo.
2. Compare o campo `plugin_root` com `${CLAUDE_PLUGIN_ROOT}`, sem diferenciar maiúsculas de minúsculas nem barra normal de barra invertida. Se forem diferentes, peça ao DA para abrir uma sessão nova e pare.
3. O teto do modo de dados é `${user_config.teto_modo_dados}`, chamado de TETO. Se ele não for exatamente `a`, `b` ou `c`, peça ao DA para configurar o plugin em `/plugin`, aba Installed, plugin desdobra, opção Configure, e pare.
4. Pergunte ao DA o que faltar:
   - o caminho do PSD ou PSB do KV (pode vir como primeiro argumento: $0);
   - a pasta nova do job, vazia ou inexistente (pode vir como segundo argumento: $1);
   - o modo de dados deste job, chamado de MODO. Mostre só os modos permitidos pelo TETO: com teto `a`, os modos a, b e c; com teto `b`, os modos b e c; com teto `c`, só o c. Explique cada um:
     - a: você vê nomes e textos das camadas e as miniaturas das camadas sem texto;
     - b: você vê nomes e textos das camadas, sem nenhuma imagem;
     - c: você vê só contagens, estados e números do motor.
   Não sugira um modo e não siga sem a resposta do DA.
5. Crie o job, numa linha só, pela ferramenta Bash (na ferramenta PowerShell, ponha `& ` antes do caminho entre aspas):

   ```
   "PY" -I -B -m desdobra --envelope --teto-modo-dados TETO job criar "PASTA" --kv "PSD" --modo-dados MODO
   ```

   Se o `codigo` do envelope não for `0`, diga ao DA o `o_que_fazer` e pare.
6. Rode a próxima fase da esteira, que neste marco é a leitura, com timeout de 600000 ms, porque um PSB grande pode levar minutos:

   ```
   "PY" -I -B -m desdobra --envelope --teto-modo-dados TETO job proxima "PASTA"
   ```

7. Explique o laudo só pelo envelope. Sempre que o `o_que_fazer` não for nulo, repita-o ao DA, qualquer que seja o código.
   - `codigo` 0 com `situacao` `ok`: laudo gravado, mesmo com camadas bloqueantes.
   - `codigo` 0 com `situacao` `ok_com_bloqueio`: o laudo foi gravado, mas há bloqueio que pede decisão do DA. Diga quantos: `contagens.bloqueios_documento` (o documento inteiro, por exemplo a composição que passou do orçamento de memória, com a prova de pixel não feita; o mesmo caso aparece em `contagens.bloqueios_composicao`) e `contagens.recusas` (partes recusadas, como um smart object). Não diga que o laudo está sem bloqueios. Se `contagens.recusas_pedem_confirmacao` for maior que zero, parte do arquivo parou num teto de memória ou de tempo a calibrar: siga como no caso `bloqueado` abaixo, porque o `job proxima` com o teto novo lê o arquivo de novo.
   - `codigo` 20: a fase de leitura falhou; o código da leitura está em `contagens.codigo_da_fase` (3: o arquivo foi recusado inteiro; 4: a leitura passou do orçamento de memória ou de tempo; 5: o isolador barrou uma ação do leitor, alarme de segurança: peça ao DA para avisar a Trezion).
   - `situacao` `bloqueado` (com `codigo` 20): a leitura parou num teto de memória ou de tempo que ainda é um valor a calibrar, e a decisão é do DA. Pergunte ao DA se ele quer tentar de novo com um teto maior e qual valor. Só com o valor dado por ele, rode `"PY" -I -B -m desdobra --envelope --teto-modo-dados TETO job proxima "PASTA" --teto-memoria-bytes N` (ou `--tempo-max-s N`). Nunca escolha o valor pelo DA.
   - `codigo` 21: outro comando do desdobra está usando o job.
   - `contagens`: quantas camadas foram lidas, degradadas (lidas com perda, com o motivo medido) e bloqueantes (impedem seguir sem decisão do DA); quantos quadros; quantas camadas estão cobertas no KV; quantos smart objects.
   - Camada coberta no KV: está visível mas totalmente coberta por outras. O laudo cita a regra da decisão 10 como sugestão (estrutura quando ocupa o canvas inteiro, fora da peça quando é um elemento solto). Quem decide é o DA, na tela de briefing.
   - `contagens.fontes_nao_conferidas` e `contagens.camadas_com_fonte_nao_conferida`: neste marco o motor ainda não confere se as fontes estão instaladas. Uma camada de texto "lida" pode usar fonte ausente; diga isso ao DA quando esses números forem maiores que zero.
   - `numeros.pct_px_acima_qualquer_canal`: a prova de pixel, a fração dos pixels da recomposição que diferem do composto salvo no PSD.
   - Nos modos a e b, `conteudo.camadas` traz nome, tipo, situação e textos de cada camada. Use isso para dizer quais camadas são degradadas ou bloqueantes. No modo c, fale só de contagens.
   - Se `segredos_bloqueados` for maior que zero, diga que o motor segurou essa quantidade de camadas porque o nome ou o texto parece chave ou senha, e que só o DA vê o detalhe, em `sugestoes/segredos-bloqueados.json` da pasta do job. Você não abre esse arquivo.
8. Pare. Diga ao DA que o laudo está em `laudo/laudo.json` da pasta do job e que as próximas fases ainda não existem neste marco.

Lembre o DA de não usar `/feedback`, `/bug` nem `/share` numa sessão com job de cliente, porque esses comandos enviam a conversa.
