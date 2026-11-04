---
description: Cria um job do desdobra a partir do PSD ou PSB do KV, das fontes da peça e das folhas de spec do veiculador e roda a esteira do marco M3 (leitura isolada do arquivo, conferência das fontes, segunda passada do laudo, design system e rascunho das specs), explicando cada fase, e explica ao DA a aprovação e a entrega do M6, que são dele. Use quando o DA quiser começar um desdobramento novo de OOH, DOOH ou banner estático.
argument-hint: "[caminho do PSD ou PSB] [pasta nova do job]"
disable-model-invocation: true
---

# Novo job do desdobra

Neste marco, a skill cria o job com o KV, as fontes e as folhas de spec e roda a esteira do M3, que tem cinco fases, nesta ordem: `ler` (a leitura do PSD e o laudo camada por camada), `fontes` (a conferência das fontes contra os arquivos enviados), `laudo-fontes` (a segunda passada do laudo, com a conferência), `ds` (o design system da peça e os limites do job) e `specs` (o rascunho das specs do veiculador, a partir das folhas). O render da origem já existe no motor (M4), mas só parte de uma pessoa: o DA roda o comando no terminal dele e confirma. A derivação por família existe no motor (M5, `desdobra derivar`), a partir do briefing; até a tela de briefing (marco seguinte), esta skill não monta nem grava briefing. A aprovação e a entrega (M6, `desdobra parametros-entrega`, `aprovar` e `entregar`) também são do DA, no terminal dele; a skill explica a ordem e roda só a conferência da entrega, que só lê (passo 10).

Regras desta skill:
- Nunca calcule geometria, posição, escala, corpo ou limite. Quem mede é o motor.
- Nunca dispare render, aprovação nem entrega. Nunca rode `desdobra render`, `desdobra linkado confirmar`, `desdobra spec confirmar`, `desdobra parametros-entrega`, `desdobra aprovar` nem `desdobra entregar`: eles recusam rodar em processo aberto pelo Claude, o gancho do plugin nega esses comandos, e quem roda é o DA, num terminal próprio. Não tente outro caminho para o mesmo efeito (código Python do motor, edição de `briefing/`, `specs/confirmacoes.json`, `render/`, `entrega/`, `parametros/entrega.json` ou `manifesto-licenca.json`).
- Nunca leia, abra ou copie o PSD, o PSB, arquivo de fonte ou imagem do job, nem os arquivos de `entrega/aprovados/`, `entrega/reprovados/`, `entrega/previa/` e `entrega/anteriores/`. Você só passa os caminhos para o motor.
- Nunca leia `laudo/laudo.json`, `laudo/laudo-fontes.json`, `fontes/conferencia.json`, `ds/design-system.json`, `specs/rascunho.json`, as folhas de `entrada/specs/` nem outro arquivo da pasta do job. Tudo o que você sabe do job vem do envelope que o motor imprime. As únicas exceções são `sugestoes/pacote-specs.json`, nos modos a e b (passo 7, fase `specs`), e as contagens do resumo de `entrega/relatorio-entrega.json`, também só nos modos a e b, depois que o DA roda o `entregar` (passo 10).
- Nunca escreva, calcule nem digite número de spec (dimensão, peso, faixa, área segura). O número sai do texto da folha pelo motor, e quem confirma é o DA, no terminal dele. Nunca rode `spec confirmar`.
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
   - as folhas de spec do veiculador, chamadas de SPECS: uma pasta com uma subpasta por veiculador (as folhas de um veiculador ficam juntas, como as páginas salvas da Globo Ads). Explique ao DA:
     - entram PDF (com ou sem camada de texto), página salva em HTML, planilha exportada em CSV e o texto do e-mail salvo em `.txt` ou `.eml`. Planilha `.xlsx`, imagem solta e Word ficam de fora: o DA exporta a planilha em CSV. O motor não lê site: a página entra salva pelo DA;
     - de PDF escaneado (sem camada de texto) o motor não tira número nenhum: ele grava a imagem de cada página, e o DA digita os valores ao lado dela no `spec confirmar`;
     - sem folhas agora, o job pode ser criado sem elas, e o DA acrescenta depois;
   - o modo de dados deste job, chamado de MODO. Mostre só os modos permitidos pelo TETO: com teto `a`, os modos a, b e c; com teto `b`, os modos b e c; com teto `c`, só o c. Explique cada um:
     - a: você vê nomes e textos das camadas e as miniaturas das camadas sem texto;
     - b: você vê nomes e textos das camadas, sem nenhuma imagem;
     - c: você vê só contagens, estados e números do motor.
   Não sugira um modo e não siga sem a resposta do DA.
5. Crie o job, numa linha só, pela ferramenta Bash (na ferramenta PowerShell, ponha `& ` antes do caminho entre aspas). Ponha cada caminho de FONTES entre aspas, um depois do outro, logo após `--fontes`. Sem fontes, tire `--fontes`. Como cada fonte é conferida num processo isolado antes de entrar, use timeout de 600000 ms:

   ```
   "PY" -I -B -m desdobra --envelope --teto-modo-dados TETO job criar "PASTA" --kv "PSD" --modo-dados MODO --fontes "FONTE1" "FONTE2" --specs "SPECS"
   ```

   Sem folhas de spec, tire `--specs`.

   Se o `codigo` do envelope não for `0`, diga ao DA o `o_que_fazer` e pare. Na recusa de fonte, o `o_que_fazer` diz quais formatos entram.
6. Rode a esteira uma fase por vez, com timeout de 600000 ms em cada chamada, porque um PSB grande pode levar minutos e a conferência de fontes abre um navegador:

   ```
   "PY" -I -B -m desdobra --envelope --teto-modo-dados TETO job proxima "PASTA"
   ```

   Cada chamada roda a primeira fase que falta e diz qual foi no campo `fase`. Depois de cada uma, explique a fase pelo envelope, como no passo 7, e chame de novo. Pare quando:
   - a `situacao` for `concluido` (as cinco fases estão em dia; nada rodou nesta chamada);
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
   Fase `specs` (o rascunho das specs, gravado em `specs/rascunho.json`; os valores confirmados pelo DA ficam em `specs/formatos-do-job.json`):
   - `contagens.folhas`, `contagens.formatos`, `contagens.circuitos` e `contagens.veiculadores`: o que o motor achou nas folhas. `contagens.folhas_recusadas`: folhas fora dos formatos aceitos.
   - `contagens.valores_rascunho`: valores tirados da folha que esperam o DA; `contagens.valores_confirmados`: os que o DA já confirmou; `contagens.registros`: campos que a folha não traz (ficam sem valor, só como registro); `contagens.com_alerta`: valores com armadilha da folha (vírgula decimal, unidade estranha, rótulo longe do valor, praça que mistura estado e cidade).
   - `contagens.divergencias`: campos em que duas fontes dizem valores diferentes (por exemplo o peso por tag do Half-Page da Globo, 550 KB na ficha e 500 KB na tabela por tamanho). O motor não escolhe, e o DA escolhe no `spec confirmar`. Você não recomenda nenhuma das leituras.
   - `contagens.recortes`: páginas sem camada de texto. O DA digita os valores ao lado da imagem da página no `spec confirmar`.
   - `contagens.formatos_do_job`: formatos com a dimensão confirmada pelo DA.
   - Nos modos a e b, você pode ajudar a dizer que trecho da folha vai para que campo (por exemplo, qual frase é a área segura ou a praça). Leia `sugestoes/pacote-specs.json`: ele traz os trechos, os campos e os alvos (ids dos formatos, circuitos e veiculadores). Se o DA quiser, escreva `sugestoes/mapeamento-specs.json` no contrato `mapeamento-specs/1`: `{"esquema": "mapeamento-specs/1", "propostas": [{"folha": "...", "trecho": "...", "campo": "...", "alvo": null}]}`, só com ids e nomes de campo do pacote. Nunca ponha número nem valor na proposta: o motor extrai o número do trecho. Para usar só parte de um trecho, `recorte_texto` leva o pedaço copiado letra por letra do trecho; para um campo que ocupa duas linhas, `adicionais` leva os ids dos outros trechos da mesma página. Depois rode `job proxima` de novo: a fase `specs` refaz o rascunho com as propostas, que continuam esperando o DA. No modo c, o pacote não traz trecho, e você não propõe nada.
   - A confirmação é sempre do DA: diga a ele para abrir um terminal próprio, fora do Claude, e rodar `"PY" -I -B -m desdobra spec confirmar --job "PASTA"`. O comando recusa rodar sem terminal interativo. Depois, rode `job proxima` de novo para a fase `specs` ler as confirmações.
   - Para conferir um arquivo pronto (por exemplo um export humano) contra um formato confirmado, rode `"PY" -I -B -m desdobra --envelope --teto-modo-dados TETO validar "ARQUIVO" --formato "CHAVE" --job "PASTA"`, com a chave do formato dita pelo DA. `codigo` 0: passou (com `contagens.aviso` maior que zero, passou com aviso, por exemplo peso entre as duas leituras de MB); 3: reprovou (`contagens.reprova`); 2: o formato não está confirmado no job. `contagens.nao_verificado` conta o que só é conferido no pixel, na entrega.
8. Quando o DA quiser resolver um bloqueio de fonte, peça a ele o caminho do arquivo novo e rode, com timeout de 600000 ms:
   - para acrescentar ou trocar uma fonte: `"PY" -I -B -m desdobra --envelope --teto-modo-dados TETO job trocar-entrada "PASTA" "entrada/fontes/NOME" "ARQUIVO"`, em que NOME é o nome do arquivo de fonte;
   - para tirar uma fonte do job (por exemplo, quando dois arquivos têm o mesmo nome PostScript e o DA escolhe qual vale), sem arquivo novo: `"PY" -I -B -m desdobra --envelope --teto-modo-dados TETO job remover-entrada "PASTA" "entrada/fontes/NOME"`. Quem escolhe o arquivo é o DA.
   Para trocar uma fonte, NOME tem de ser o nome do arquivo que já está no job, com as mesmas maiúsculas e minúsculas: um nome que só difere na caixa é recusado. Se o `codigo` não for `0`, diga ao DA o `o_que_fazer`. Senão, volte ao passo 6: a troca ou a remoção invalida só as fases `fontes`, `laudo-fontes` e `ds`, e a leitura do PSD fica como está. Para acrescentar ou trocar uma folha de spec, use o mesmo `job trocar-entrada` com `entrada/specs/VEICULADOR/NOME`: ele invalida só a fase `specs`.
9. Pare quando a esteira estiver concluída ou o DA quiser parar. Diga ao DA o que foi gravado na pasta do job: o laudo da leitura em `laudo/laudo.json`, a conferência de fontes em `fontes/conferencia.json`, o laudo com a conferência em `laudo/laudo-fontes.json`, o design system e os limites em `ds/design-system.json` e `ds/limites.json` e o rascunho das specs em `specs/rascunho.json`, com os valores confirmados pelo DA em `specs/formatos-do-job.json` (só os das fases que rodaram). Diga também que o render da origem é do DA: ele abre um terminal próprio, fora do Claude, e roda `"PY" -I -B -m desdobra render --job "PASTA"`, que pergunta antes de renderizar e grava `render/origem/master.png` e `render/origem/render.json`. Se o laudo tiver smart object linkado, antes disso o DA confirma o arquivo de cada um com `"PY" -I -B -m desdobra linkado confirmar --job "PASTA"`. A tela de briefing entra num marco seguinte.
10. A entrega também é do DA, num terminal próprio, fora do Claude. Quando ele perguntar, explique a ordem, sem rodar nenhum destes comandos:
   - `"PY" -I -B -m desdobra parametros-entrega --job "PASTA" --formato ID` com as opções que ele decidir: `--rotacao-sentido horario|anti_horario` (só formato que o briefing gira 90 ou 270 graus, com o sentido confirmado com o veículo), `--condicao` (a condição do teto de peso), `--cor-de-achatamento #rrggbb` (master com transparência), `--borda-1px sim|nao` e `--limpar CAMPO`, em que CAMPO é `rotacao-sentido`, `condicao`, `cor-de-achatamento` ou `borda-1px` (com hífen). O comando mostra o antes e o depois e pede o sim digitado. Você não escolhe nenhum desses valores;
   - `"PY" -I -B -m desdobra aprovar --job "PASTA" --formato ID` (repita `--formato` para vários): grava a prévia do arquivo final em `entrega/previa/`, que o DA abre antes de digitar sim, e a aprovação em `briefing/aprovacao.json`. Mudar o master, o render ou o briefing derruba a aprovação do formato. Um parâmetro de entrega derruba a aprovação quando muda o arquivo final: o giro e a borda sempre, a cor de achatamento só num master com transparência e a condição só quando troca o teto de peso que vale;
   - `"PY" -I -B -m desdobra entregar --job "PASTA"`: confere todos os formatos do briefing, pede o sim e grava `entrega/aprovados/`, `entrega/reprovados/` (com a regra e a sugestão), `entrega/relatorio-entrega.json` e o `manifesto-licenca.json` da raiz do job. A entrega anterior vai para `entrega/anteriores/`.

   Depois que o DA rodar o `entregar`, nos modos a e b, você pode ler `entrega/relatorio-entrega.json` com a ferramenta Read, só para dizer ao DA as contagens: `contagens.aprovados` e `contagens.reprovados`, e do `resumo` as contagens de `verificacoes` (`passou`, `avisou`, `so_registro`, `reprovou`), `aprovados_sem_aviso` e as regras com a contagem em `avisos` e `registros`. Não repita hash, nome de arquivo, medida nem parâmetro do relatório, e não abra os arquivos entregues. No modo c, não leia o relatório: o que você diz da entrega vem só do envelope do `conferir-entrega`.

   Você pode rodar a conferência da entrega, que só lê e não grava nada, com timeout de 600000 ms:

   ```
   "PY" -I -B -m desdobra --envelope --teto-modo-dados TETO conferir-entrega --job "PASTA"
   ```

   Explique pelo envelope:
   - `codigo` 0: `entrega/` confere com o relatório. `contagens.conferem` arquivos conferem pelo sha256 e pelos bytes, de `contagens.arquivos` listados;
   - `codigo` 3: `entrega/` mudou depois da entrega ou não foi gravada pelo motor. Diga ao DA o que cada contagem maior que zero quer dizer: `divergem` (arquivo com outro conteúdo), `faltam` (arquivo do relatório que sumiu), `sobram` (arquivo que o relatório não lista), `reprovado_em_aprovados` (arquivo que reprova dentro de `aprovados/`), `aprovado_em_reprovados` e `arquivos_de_fonte` (arquivo de fonte dentro de `entrega/`). Uma contagem com outro nome igual a 1 é o motivo do relatório ou do manifesto (por exemplo relatório ausente ou com o selo errado). Repita o `o_que_fazer`: quem refaz a entrega é o DA, com o `entregar`, num terminal próprio. Você não conserta nada em `entrega/`;
   - `codigo` 2: a pasta não é um job do desdobra.

Lembre o DA de não usar `/feedback`, `/bug` nem `/share` numa sessão com job de cliente, porque esses comandos enviam a conversa.
