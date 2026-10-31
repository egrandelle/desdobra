---
description: Cria um job do desdobra a partir do PSD ou PSB do KV e das fontes da peça e roda a esteira do marco M2 (leitura isolada do arquivo, conferência das fontes, segunda passada do laudo e design system), explicando cada fase. Use quando o DA quiser começar um desdobramento novo de OOH, DOOH ou banner estático.
argument-hint: "[caminho do PSD ou PSB] [pasta nova do job]"
disable-model-invocation: true
---

# Novo job do desdobra

Neste marco, a skill cria o job com o KV e as fontes e roda a esteira do M2, que tem quatro fases, nesta ordem: `ler` (a leitura do PSD e o laudo camada por camada), `fontes` (a conferência das fontes contra os arquivos enviados), `laudo-fontes` (a segunda passada do laudo, com a conferência) e `ds` (o design system da peça e os limites do job). As fases seguintes (specs, render, tela de briefing) entram nos próximos marcos.

Regras desta skill:
- Nunca calcule geometria, posição, escala, corpo ou limite. Quem mede é o motor.
- Nunca dispare render nem aprovação.
- Nunca leia, abra ou copie o PSD, o PSB, arquivo de fonte ou imagem do job. Você só passa os caminhos para o motor.
- Nunca leia `laudo/laudo.json`, `laudo/laudo-fontes.json`, `fontes/conferencia.json`, `ds/design-system.json` nem outro arquivo da pasta do job. Tudo o que você sabe do job vem do envelope que o motor imprime.
- Nunca escolha o modo de dados pelo DA, nem valor de teto ou parâmetro de cor.
- Nunca mande o DA instalar fonte no sistema. A fonte entra no job só pelo arquivo enviado, e o motor confere a fonte contra esse arquivo.

## Passos

1. Leia `${CLAUDE_PLUGIN_DATA}/interpretador.json` com a ferramenta Read. Se ele não existir, diga ao DA para rodar `/desdobra:doctor` e pare. Guarde o campo `python`, chamado de PY abaixo.
2. Compare o campo `plugin_root` com `${CLAUDE_PLUGIN_ROOT}`, sem diferenciar maiúsculas de minúsculas nem barra normal de barra invertida. Se forem diferentes, peça ao DA para abrir uma sessão nova e pare.
3. O teto do modo de dados é `${user_config.teto_modo_dados}`, chamado de TETO. Se ele não for exatamente `a`, `b` ou `c`, peça ao DA para configurar o plugin em `/plugin`, aba Installed, plugin desdobra, opção Configure, e pare.
4. Pergunte ao DA o que faltar:
   - o caminho do PSD ou PSB do KV (pode vir como primeiro argumento: $0);
   - a pasta nova do job, vazia ou inexistente (pode vir como segundo argumento: $1);
   - as fontes usadas no PSD, chamadas de FONTES: um ou mais arquivos, ou pastas com os arquivos. Explique ao DA:
     - entram OTF, TTF, TTC (e OTC), WOFF e WOFF2, um arquivo solto por face ou coleção. O motor reconhece o formato pela assinatura do arquivo;
     - ficam de fora variable font, fonte Type 1 (PFB, PFA, PFM, AFM, T42), pacote (zip, tar ou comprimido), arquivo que não é fonte e arquivo de fonte que não abre. Se um arquivo for recusado, o job inteiro não é criado;
     - a fonte entra só por essa entrada. Arquivo de fonte (ou pacote com fonte) dentro da pasta de campanha ou de specs é recusado;
     - numa pasta, dois arquivos com o mesmo nome dão erro, porque o job guarda as fontes lado a lado. Os arquivos que o sistema grava sozinho (`.DS_Store`, `Thumbs.db`, `desktop.ini` e os `._*` do Mac) ficam de fora sem erro;
     - se o DA não tiver as fontes agora, o job pode ser criado sem elas, mas a conferência vai marcar as camadas de texto como fonte faltando, e o DA acrescenta os arquivos depois;
     - o desdobra trata toda fonte enviada como fonte com direito de uso, e a responsabilidade pela licença é da agência ou do usuário. O motor não pede arquivo de licenças e não bloqueia nem avisa por licença. Não pergunte ao DA sobre licença;
   - o modo de dados deste job, chamado de MODO. Mostre só os modos permitidos pelo TETO: com teto `a`, os modos a, b e c; com teto `b`, os modos b e c; com teto `c`, só o c. Explique cada um:
     - a: você vê nomes e textos das camadas e as miniaturas das camadas sem texto;
     - b: você vê nomes e textos das camadas, sem nenhuma imagem;
     - c: você vê só contagens, estados e números do motor.
   Não sugira um modo e não siga sem a resposta do DA.
5. Crie o job, numa linha só, pela ferramenta Bash (na ferramenta PowerShell, ponha `& ` antes do caminho entre aspas). Ponha cada caminho de FONTES entre aspas, um depois do outro, logo após `--fontes`. Sem fontes, tire `--fontes`. Como cada fonte é conferida num processo isolado antes de entrar, use timeout de 600000 ms:

   ```
   "PY" -I -B -m desdobra --envelope --teto-modo-dados TETO job criar "PASTA" --kv "PSD" --modo-dados MODO --fontes "FONTE1" "FONTE2"
   ```

   Se o `codigo` do envelope não for `0`, diga ao DA o `o_que_fazer` e pare. Na recusa de fonte, o `o_que_fazer` diz quais formatos entram.
6. Rode a esteira uma fase por vez, com timeout de 600000 ms em cada chamada, porque um PSB grande pode levar minutos e a conferência de fontes abre um navegador:

   ```
   "PY" -I -B -m desdobra --envelope --teto-modo-dados TETO job proxima "PASTA"
   ```

   Cada chamada roda a primeira fase que falta e diz qual foi no campo `fase`. Depois de cada uma, explique a fase pelo envelope, como no passo 7, e chame de novo. Pare quando:
   - a `situacao` for `concluido` (as quatro fases estão em dia; nada rodou nesta chamada);
   - a `situacao` for `portao` (`codigo` 10): diga ao DA o `o_que_fazer` do portão;
   - o `codigo` não for `0`: siga o passo 7 para esse código;
   - a `situacao` for `ok_com_bloqueio` e `contagens.fases_rodadas_agora` for `0`: a esteira chegou ao fim, mas o job não está concluído, porque uma fase (o campo `fase`, em geral `fontes`) terminou com bloqueio que continua pendente. Explique o bloqueio pelo `o_que_fazer` e pelas contagens e pare. Não chame `job proxima` de novo esperando outro resultado: o bloqueio só sai quando o DA resolver (passo 8), e aparece também em `job estado`;
   - a `situacao` for `ok_com_bloqueio` com alguma fase rodada: explique o bloqueio e pergunte ao DA se ele quer resolver agora ou seguir para a próxima fase. O bloqueio fica registrado no estado do job (`contagens.bloqueios_pendentes`) e volta em todo `job proxima` até ser resolvido. Só chame `job proxima` de novo com a resposta do DA.
7. Explique cada fase só pelo envelope. Sempre que o `o_que_fazer` não for nulo, repita-o ao DA, qualquer que seja o código e a fase.

   Para qualquer fase:
   - `codigo` 20: a fase falhou; o código da própria fase está em `contagens.codigo_da_fase`. Na leitura: 3, o arquivo foi recusado inteiro; 4, a leitura passou do orçamento de memória ou de tempo; 5, o isolador barrou uma ação do leitor, alarme de segurança: peça ao DA para avisar a Trezion. Nas outras fases, repita o `o_que_fazer`, que diz qual comando mostra o motivo.
   - `codigo` 21: outro comando do desdobra está usando o job.
   - Se `segredos_bloqueados` for maior que zero, diga que o motor segurou essa quantidade de itens porque o nome ou o texto parece chave ou senha, e que só o DA vê o detalhe, em `sugestoes/segredos-bloqueados.json` da pasta do job. Você não abre esse arquivo.

   Fase `ler` (a leitura do PSD):
   - `situacao` `ok`: laudo gravado, mesmo com camadas bloqueantes.
   - `situacao` `ok_com_bloqueio`: o laudo foi gravado, mas há bloqueio que pede decisão do DA. Diga quantos: `contagens.bloqueios_documento` (o documento inteiro, por exemplo a composição que passou do orçamento de memória, com a prova de pixel não feita; o mesmo caso aparece em `contagens.bloqueios_composicao`) e `contagens.recusas` (partes recusadas, como um smart object). Não diga que o laudo está sem bloqueios. Se `contagens.recusas_pedem_confirmacao` for maior que zero, parte do arquivo parou num teto de memória ou de tempo a calibrar: siga como no caso `bloqueado` abaixo, porque o `job proxima` com o teto novo lê o arquivo de novo.
   - `situacao` `bloqueado` (com `codigo` 20): a leitura parou num teto de memória ou de tempo que ainda é um valor a calibrar, e a decisão é do DA. Pergunte ao DA se ele quer tentar de novo com um teto maior e qual valor. Só com o valor dado por ele, rode `"PY" -I -B -m desdobra --envelope --teto-modo-dados TETO job proxima "PASTA" --teto-memoria-bytes N` (ou `--tempo-max-s N`). Nunca escolha o valor pelo DA.
   - `contagens`: quantas camadas foram lidas, degradadas (lidas com perda, com o motivo medido) e bloqueantes (impedem seguir sem decisão do DA); quantos quadros; quantas camadas estão cobertas no KV; quantos smart objects.
   - Camada coberta no KV: está visível mas totalmente coberta por outras. O laudo cita a regra da decisão 10 como sugestão (estrutura quando ocupa o canvas inteiro, fora da peça quando é um elemento solto). Quem decide é o DA, na tela de briefing.
   - `contagens.fontes_nao_conferidas` e `contagens.camadas_com_fonte_nao_conferida`: a leitura ainda não confere as fontes. Diga ao DA que quem confere é a fase `fontes`, a seguinte, contra os arquivos enviados.
   - `numeros.pct_px_acima_qualquer_canal`: a prova de pixel, a fração dos pixels da recomposição que diferem do composto salvo no PSD.
   - Nos modos a e b, `conteudo.camadas` traz nome, tipo, situação e textos de cada camada. Use isso para dizer quais camadas são degradadas ou bloqueantes. No modo c, fale só de contagens.

   Fase `fontes` (a conferência das fontes, que vale em qualquer modo, só com contagens):
   - `contagens.faces` e `contagens.arquivos`: quantas faces e quantos arquivos de fonte o motor leu; `contagens.arquivos_recusados`: arquivos que ficaram de fora na leitura.
   - `contagens.camadas`: quantos pares de camada de texto e fonte do PSD foram conferidos; `contagens.camadas_ok`, `contagens.camadas_aviso` e `contagens.camadas_bloqueantes` dizem como cada par saiu.
   - `contagens.camadas_bloqueantes` maior que zero também cobre dois arquivos de `entrada/fontes/` com o mesmo nome PostScript: o motor não escolhe qual vale, e o DA tira o que não vale (passo 8). Cobre ainda o caso em que o navegador não respondeu qual face desenhou o trecho: sem essa resposta a face fica sem prova, e o DA roda `/desdobra:doctor`.
   - `contagens.cache_provado` igual a 0: o teste de cache do navegador não provou que o perfil grava cache, então a contagem de cópias da fonte no cache (`contagens.copias_no_cache`) fica sem prova. Diga isso ao DA.
   - `contagens.sem_par`: pares sem face no job. Ou o arquivo da fonte está faltando, ou há face da mesma família com outro nome PostScript ou outro peso. O motor nunca põe uma face de outro peso no lugar. O DA traz o arquivo certo (passo 8).
   - `contagens.glifos_faltando`: quantos caracteres do texto a fonte enviada não cobre. O DA confere se o arquivo é a versão certa da fonte.
   - `contagens.larguras_divergentes`: linhas em que a largura medida no navegador passou do limite de divergência contra a caixa do PSD (`numeros.largura_erro_max_pct` é a maior diferença, em porcentagem). Esse caso pede decisão do DA, sem reprovação automática: pode ser outra versão da fonte ou um ajuste manual no PSD. Você não decide.
   - `contagens.cdp_confere` e `contagens.cdp_diverge`: em quantos pares o navegador confirmou que desenhou com a face enviada, e em quantos entrou outra face.
   - `contagens.chromium_feito` igual a 0: a medição no navegador não rodou, e as camadas ficam sem essa conferência. Peça ao DA para rodar `/desdobra:doctor`.
   - `contagens.faces_bloqueantes` e `contagens.faces_aviso`: faces com bloqueio ou aviso técnico (face que não carregou no navegador, outra face no navegador, coleção que não dá para servir, peso do arquivo diferente do nome do estilo). O detalhe de cada face fica em `fontes/conferencia.json` da pasta do job, que só o DA abre.
   - `contagens.fontes_fora_da_entrada` maior que zero: há arquivo de fonte na pasta do job fora de `entrada/fontes/`. Diga isso ao DA.

   Fase `laudo-fontes` (a segunda passada do laudo, gravada em `laudo/laudo-fontes.json`; o laudo da primeira passada não muda):
   - `contagens.camadas`, `contagens.lidas`, `contagens.degradadas` e `contagens.bloqueantes`: o laudo de novo, agora com a conferência de fontes.
   - `contagens.b3_fontes`: camadas que ficaram bloqueantes pela fonte (fonte faltando, sem par, glifo faltando, outra face no navegador, face que não carregou ou largura divergente).
   - `contagens.fontes_presentes`, `contagens.fontes_ausentes` e `contagens.fontes_divergentes`: como saiu cada fonte usada no PSD.
   - Nos modos a e b, `conteudo.camadas` traz a situação nova de cada camada. No modo c, fale só de contagens.

   Fase `ds` (o design system, gravado em `ds/design-system.json`, e os limites do job, em `ds/limites.json`):
   - `contagens.cores` e `contagens.cores_convertidas`: tokens de cor e quantos foram convertidos para sRGB pelo perfil do documento. Com `situacao` `ok_com_bloqueio`, as cores não foram convertidas, e o `o_que_fazer` diz por quê.
   - `contagens.tipografia` e `contagens.tipografia_com_metricas`: tokens de tipografia e quantos têm as métricas da face conferida.
   - `contagens.medidas`, `contagens.limites` e `contagens.pendencias`: medidas por camada, limites que o job usa e pendências do design system.
   - `contagens.sujeito_alfa` e `contagens.sujeito_pedir_ao_da`: em quantas camadas o motor achou a caixa do sujeito pelo recorte, e em quantas o sujeito está fundido à foto e o DA marca a caixa no briefing.
   - `contagens.assets_perfil_convertido`: imagens com outro perfil de cor, que são convertidas para o perfil do documento, como o Photoshop faz no próprio KV.
   - Os parâmetros de cor da saída (intent, compensação de ponto preto e perfil embutido) são decisão do DA. Sem decisão dele, vale o padrão do registro, que ainda é um valor a calibrar. Diga isso ao DA e, se ele quiser mudar, explique as opções sem recomendar nenhuma: intent `perceptual`, `relativo_colorimetrico`, `saturacao` ou `absoluto_colorimetrico`; compensação de ponto preto `sim` ou `nao`; perfil sRGB embutido na saída `sim` ou `nao`. Só com os valores dados por ele, rode `"PY" -I -B -m desdobra --envelope --teto-modo-dados TETO ds parametros-cor --job "PASTA"` com as opções que ele escolheu (`--intent X`, `--compensacao-ponto-preto sim|nao`, `--perfil-embutido sim|nao`) e depois `job proxima` de novo, que monta o design system com os parâmetros novos.
8. Quando o DA quiser resolver um bloqueio de fonte, peça a ele o caminho do arquivo novo e rode, com timeout de 600000 ms:
   - para acrescentar ou trocar uma fonte: `"PY" -I -B -m desdobra --envelope --teto-modo-dados TETO job trocar-entrada "PASTA" "entrada/fontes/NOME" "ARQUIVO"`, em que NOME é o nome do arquivo de fonte;
   - para tirar uma fonte do job (por exemplo, quando dois arquivos têm o mesmo nome PostScript e o DA escolhe qual vale), sem arquivo novo: `"PY" -I -B -m desdobra --envelope --teto-modo-dados TETO job remover-entrada "PASTA" "entrada/fontes/NOME"`. Quem escolhe o arquivo é o DA.
   Para trocar uma fonte, NOME tem de ser o nome do arquivo que já está no job, com as mesmas maiúsculas e minúsculas: um nome que só difere na caixa é recusado. Se o `codigo` não for `0`, diga ao DA o `o_que_fazer`. Senão, volte ao passo 6: a troca ou a remoção invalida só as fases `fontes`, `laudo-fontes` e `ds`, e a leitura do PSD fica como está.
9. Pare quando a esteira estiver concluída ou o DA quiser parar. Diga ao DA o que foi gravado na pasta do job: o laudo da leitura em `laudo/laudo.json`, a conferência de fontes em `fontes/conferencia.json`, o laudo com a conferência em `laudo/laudo-fontes.json` e o design system e os limites em `ds/design-system.json` e `ds/limites.json` (só os das fases que rodaram). Diga também que as próximas fases (specs, render e tela de briefing) entram nos próximos marcos.

Lembre o DA de não usar `/feedback`, `/bug` nem `/share` numa sessão com job de cliente, porque esses comandos enviam a conversa.
