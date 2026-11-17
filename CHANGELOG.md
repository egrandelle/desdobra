# Novidades do desdobra

O que muda em cada versão, em palavras simples. O detalhe técnico de cada mudança está em `docs/m1-interfaces.md` e no histórico do git.

## 0.9.3 (16/11/2026): as famílias aparecem depois do Design system

Correção do teste do KV A na 0.9.2: com as funções e o Design system feitos, as famílias não apareciam, o "Salvar e seguir" não dava retorno e o passo das Famílias mandava de volta para Funções. Tudo foi conferido em arquivos sintéticos.

- A tela agora pergunta ao desdobra pelas famílias também depois de cada escolha do Design system. Antes, ela só perguntava depois de uma escolha de função, e quem fazia o Design system por último via a espera velha.
- Quando o desdobra ainda não consegue montar as famílias, o passo das Famílias diz o motivo concreto, com o nome das camadas, marca na lista o item que falta e leva ao lugar certo. A lista nunca fica toda verde junto com a espera.
- Todo motivo que o desdobra pode dar ganhou uma frase para o DA, com o passo onde ele se resolve.
- No KV A, o motivo mais provável é o retângulo de fundo e o grafismo, que se sobrepõem e andam juntos num bloco: as funções deles precisam da mesma regra de escala. O Design system mostra esse aviso no alto, e a contagem "Faltam" conta esse item.
- O "Salvar e seguir" fica desligado enquanto as famílias não aparecem, com o motivo ao lado. A frase "Tudo confirmado. Pode salvar." só aparece com todas as famílias confirmadas.
- Quando o desdobra recusa um clique ou uma escolha não é salva, o aviso aparece no rodapé, ao lado do "Salvar e seguir", com o motivo que o desdobra deu. O botão mostra "Conferindo" enquanto espera a resposta. A frase "Tente de novo" saiu dos casos em que tentar de novo não resolve.
- Quando uma escolha não é salva, o rodapé e o passo das Famílias dizem isso, com o motivo. Antes, a tela podia ficar dizendo "Salvando" sem salvar nada.
- O aviso de um clique recusado sai quando você muda alguma coisa ou troca de passo. O motivo aparece uma vez só, no rodapé, e o foco do teclado volta ao botão.
- A frase curta ao lado do "Salvar e seguir" diz o que fazer, como "Dê a mesma regra de tamanho às funções do bloco". As listas de camadas usam "e" no fim, e uma camada sem nome aparece como "sem nome".
- O botão "Ir para o Design system" mostra o aviso do motivo junto do cartão que resolve, também nas telas menores.
- A regra de bloco que veio de um briefing salvo fora da tela não se muda na tela. Quando ela trava as famílias, a tela diz para pedir ajuda ao Claude, em vez de mandar a um passo sem esse controle.

## 0.9.2 (16/11/2026): formatos digitados na tela

Para o job que chega sem folha de spec. Sem folha, o job não tinha formato nenhum, e as famílias nunca apareciam. Tudo foi conferido em arquivos sintéticos.

- No passo 1 da tela, em "Valores de spec", o bloco "Formatos sem folha de spec" recebe a largura e a altura de cada formato em pixels. Dá para colar vários de uma vez, separados por vírgula, como 1080x1920, 300x600.
- A tela avisa na hora o que não entendeu, o formato repetido e o tamanho fora do que o desdobra aceita.
- Uma janela de confirmação mostra os formatos, e eles entram já confirmados, com quem escreveu e quando. O Claude não escreve formatos.
- Os formatos aparecem em "Formatos e giro" e, com as funções e o Design system completos, nas famílias.

A tela também ficou mais clara para quem desenha:

- O Design system passou a ser o passo 3 e as Famílias o passo 4, porque as famílias dependem dele.
- Sem família para mostrar, o passo das Famílias explica por quê, mostra o que falta (formatos, funções, tamanho e âncora) e tem o botão para o lugar certo.
- No topo do passo 1, uma faixa diz o que trava o job e o que falta para as famílias, com o botão "Resolver aqui" ou "Escrever os formatos". Cada bloqueio também ganhou o botão que leva ao lugar onde ele se resolve.
- O motivo do "Salvar e seguir" desligado fica em destaque ao lado do botão, com "Ir até lá".
- As abas dos passos mostram o que já está feito e o que falta. A lista do que falta vem separada por passo.
- Na lista de camadas do passo 2 há busca pelo nome e o filtro "Só as sem função".
- Os nomes no palco ficaram curtos (função e camada); a regra aparece ao parar o mouse em cima e na linha do elemento escolhido. Sem elemento escolhido, a barra de edição mostra só Desfazer e Escolher vários.
- Texto maior nos passos de leitura, cinza mais escuro para ler melhor e botões desligados sem a transparência.
- Cada formato digitado tem o botão "Remover".
- Se a folha de spec trouxer o mesmo formato, vale a folha depois que a medida dela for confirmada, e a tela avisa. Antes disso, o formato que você escreveu continua no job. Se a folha sair, o formato digitado volta.
- Dá para escrever o milhar com ponto, como 1.080 x 1.920.
- Quando as funções e o Design system estão completos e as famílias ainda não aparecem, o passo das Famílias diz o motivo, com o nome das camadas, e o botão leva ao lugar certo.
- O aviso de que uma escolha não foi salva aparece em frase também nas telas menores.
- Na janela de confirmação, o botão que confirma fica em destaque, e o de remover fica na cor de aviso.
- Os botões desligados do passo 5 dizem por que estão desligados quando o mouse para em cima.
- No palco, o nome que ficaria em cima de outro sai da vista. O nome do elemento escolhido sempre aparece.
- A camada com transparência aparece sem o quadrado preto em volta.
- O formato que você escreveu aparece pela medida em "Formatos e giro", sem o código interno.
- Um formato escrito no modo de teste nunca chega ao render, à entrega nem ao padrão da marca.
- Um formato digitado só tem a medida: peso, área segura e faixas ficam sem regra do veículo.

## 0.9.1 (16/11/2026): texto como imagem

Para o KV que tem texto vivo no PSD, mas cuja fonte a agência nunca recebeu em arquivo. Tudo foi conferido em arquivos sintéticos.

- No passo 1 da tela, em "Fontes do job", cada fonte que falta ganha o botão "Não tenho esta fonte: usar o texto como imagem". A janela de confirmação mostra as camadas atingidas e o efeito, e a decisão fica gravada com quem decidiu e quando. O Claude não faz essa declaração.
- Com a decisão, o job deixa de parar nessa fonte. As camadas dela vão pelos pixels do próprio PSD e escalam como imagem, pela regra da função que o DA escolheu. Ampliar acima do tamanho do KV avisa, como em qualquer imagem.
- No palco, essas camadas aparecem com o selo "Texto como imagem": o texto não se edita e a linha não quebra ali.
- O botão também aparece quando o arquivo da fonte chegou, mas não confere com o PSD (outra versão da fonte, por exemplo).
- Se chegar depois o arquivo da fonte que confere, o texto volta a ser texto vivo, e a tela avisa. Um arquivo que não confere deixa a decisão valendo. O botão "Desfazer" (ou "Tirar a declaração") desfaz a decisão com um clique.
- Para o que vai ao Claude nada muda: a camada continua sendo texto e nunca vira miniatura no modo (a).
- O manifesto e o relatório da entrega registram a camada como texto como imagem por decisão do DA, sem recusar a entrega.

## 0.9.0 (13/11/2026): marca, sugestão de função e skills (M7c)

Com esta versão, o Claude pode sugerir a função de cada camada quando o diretor de arte pede, o desdobra guarda o padrão de cada marca da agência e as skills levam o DA da criação do job até a tela sem nenhum comando. Tudo foi conferido em arquivos sintéticos; a rodada com os KVs reais fica para quando o Duda decidir. Antes de usar, veja também "O que ainda não funciona nesta versão", no fim desta entrada.

### Sugestão de função, só quando o DA pede

- O job nasce sem modo de dados. O DA escolhe o modo no passo 1 da tela, e até a escolha nada do conteúdo do job vai ao Claude.
- Depois de gravar o modo (a) ou (b), a tela mostra a frase para escrever ao Claude: "quero sugestões". O Claude prepara as sugestões, o desdobra confere cada uma e a tela as mostra ao lado de cada função, com a alternativa e a fonte.
- A sugestão nunca vira função sozinha: só o clique do DA em "Usar" põe a função no briefing. Com a tela aberta, as sugestões novas aparecem com o aviso "Chegaram as sugestões do Claude", e o que o DA já fez não muda.
- No modo (a), vão ao Claude só as imagens de camadas sem texto. Ficam de fora o grupo, o objeto inteligente com texto dentro ou linkado, a camada escondida e a camada recortada sobre um texto; na dúvida, a camada fica de fora. A tela avisa que letra desenhada em pixel pode ir na imagem.
- Quando o modo muda, ou quando a agência baixa o teto, o desdobra refaz o que o Claude pode ler, e as sugestões do modo antigo saem da tela.
- O desdobra mede quantas sugestões batem com a função que o DA confirmou e o tempo do passo "Funções", com e sem sugestão na tela. Esses números ficam no job, fora do briefing, e o DA não vê.

### O padrão da marca

- No passo 1, o DA pode dizer de que marca é o job: uma das marcas da agência, "Marca nova" ou "Sem marca". Nenhuma vem marcada, e a escolha é opcional.
- Quando todos os formatos do job estão aprovados, a tela mostra o botão "Guardar o padrão desta marca". A janela mostra o que vai entrar no padrão (as regras de escala e as âncoras de cada função e o nome das faces) e pede a confirmação na própria janela.
- Cada registro vira uma versão nova do padrão. As versões anteriores ficam guardadas e nunca são apagadas, e registrar de novo o mesmo job sem mudança não cria versão.
- No job seguinte da mesma marca, o Design system mostra o padrão ao lado de cada função, com a versão e o job de origem. Nada fica preenchido: o DA usa o padrão com um clique em "Usar o padrão" ou escolhe outro valor.
- O padrão guarda só o nome das faces. Arquivo de fonte, edições de palco, versão da galeria e lockup de governo ficam no job.

### Biblioteca da agência

- A pasta onde o desdobra guarda o padrão de cada marca é escolhida pelo DA em `/plugin`, no plugin desdobra, opção Configure, com cliques. Ela é opcional: sem ela, o job roda normal, sem marca, e a tela diz onde configurar.
- A pasta fica fora do plugin, por isso desinstalar ou atualizar o desdobra não apaga o padrão das marcas. A conferência da instalação diz se a pasta existe, se dá para gravar nela e se ela está num lugar que o desdobra apagaria.

### O Claude lê menos do job

- Dentro da pasta de um job, o Claude lê só o que o modo de dados permite: os pacotes preparados pelo desdobra, as imagens permitidas do modo (a) e as sugestões. O PSD, as fontes, o laudo, o briefing, as imagens geradas e a biblioteca da agência ficam fechados para ele, por qualquer ferramenta.
- O Claude nunca grava o padrão de uma marca nem o que o desdobra preparou para ele.

### Skills

- `novo-job` foi reescrita para quem não usa terminal: pede os caminhos completos do PSD e das fontes, com a dica de "Copiar como caminho", roda a preparação e abre a tela.
- Skills novas: `continuar` (retoma um job do ponto em que parou), `sugerir-funcoes` (as sugestões de função, só quando o DA pede, só nos modos a e b) e `ler-spec` (ajuda a ler uma folha de especificação nova; a confirmação de cada valor continua na tela).
- Nenhuma skill pede ao DA o modo, o teto, um valor ou uma regra no chat, e nenhuma manda o DA a um terminal. As recusas dos atos do DA e os textos das fases do job, que mandavam rodar comando, passaram a mandar o DA à tela.

### Para quem já usava a 0.8.0

- Configure a biblioteca da agência em `/plugin` se quiser guardar o padrão das marcas. Sem ela, nada muda no job.
- A versão do desdobra entra na impressão de cada formato. Um formato aprovado na 0.8.0 pode pedir render e aprovação de novo, uma vez, quando o job for salvo nesta versão.
- Ao abrir um job que já existia, o desdobra lê de novo as specs dele, uma vez, porque a biblioteca de specs passou a levar a versão nova. As confirmações de spec que o DA já fez entram nessa leitura.
- O pacote que o Claude lê é refeito no formato novo na primeira vez que o job é aberto.

### O que ainda não funciona nesta versão

- Entregar e trocar os parâmetros de entrega ainda não têm botão na tela. A entrega chega no próximo marco.
- Restaurar uma versão antiga do briefing ainda não existe; o histórico aparece só para leitura.
- O padrão de uma marca só aparece depois que a primeira campanha dela é registrada.
- Nos modos (a) e (b), os textos das camadas e, no (a), as imagens permitidas ficam na transcrição local da conversa até o DA apagar. A skill lembra disso ao fim de cada sugestão e ao fechar o job.

## 0.8.0 (12/11/2026): a tela corrige, renderiza e aprova (M7b)

Com esta versão, o diretor de arte corrige o briefing depois da aprovação, gera as imagens e aprova cada formato pela tela, sem comando. A entrega continua fora da tela: o botão de entregar fica para uma versão seguinte. Antes de usar, veja também "O que ainda não funciona nesta versão", no fim desta entrada.

### Corrigir sem perder o que já estava pronto

- Quando o DA muda alguma coisa depois de aprovar, o desdobra refaz só os formatos que a mudança atinge. Os outros continuam com a mesma imagem e com a aprovação que já tinham.
- Cada formato mostra, em frase simples, o que mudou desde a última versão. As versões do briefing ficam guardadas em ordem e aparecem para consulta.
- O texto que o DA editou no palco sai na imagem final com as mesmas linhas da prévia. Uma letra que a fonte do job não tem trava o render com uma mensagem clara.
- A família guarda o mesmo nome quando o DA muda os formatos dela, e a tela avisa quando uma família ganhou ou perdeu formatos e precisa ser confirmada de novo.

### Gerar as imagens e aprovar na própria tela

- O botão "Renderizar os afetados" gera as imagens de todos os formatos que pedem render, com uma confirmação só. O render nunca começa sozinho.
- A tela continua respondendo enquanto o render roda, mostra o andamento de cada formato e deixa cancelar entre uma etapa e outra.
- A aprovação é por formato: o DA marca os formatos, vê o arquivo final de cada um na janela e aprova. Quando o formato vai girado na entrega, a janela pergunta para que lado, com um desenho.
- Um painel mostra a situação de cada formato, o motivo e o histórico de versões.

### Editar a mestre da família

- O DA quebra a linha de um texto direto no palco, com as miniaturas dos outros formatos da família ao lado. A quebra vale para a família inteira.
- A quebra que o próprio DA faz já vale como aprovada. A quebra que o desdobra propõe pede um clique em "Aprovar quebra" antes de confirmar a família.
- O tempo para desenhar a mestre de cada família é medido e guardado junto do job, fora do briefing.

### Mais jeitos de mexer no palco

- Escolher vários elementos de uma vez (Shift e clique, o botão "Escolher vários" ou um retângulo) e mover ou mudar o tamanho do grupo inteiro.
- Alinhar pela margem ou pela área segura da folha, nas bordas e no centro.
- Dar o tamanho em porcentagem, de 25% a 400%.
- Passar da borda deixou de ser erro: o DA pode deixar um elemento sangrar. Um elemento que sai inteiro da peça ganha um aviso próprio.
- Quando o DA fura de propósito a distância mínima ou o tamanho mínimo, a peça mostra "Decisão do DA" e não cobra ajuste.
- O botão "Nomes" esconde as etiquetas dos elementos para facilitar o clique num palco cheio. O elemento escolhido continua com o nome.
- A ajuda "Como editar" lista todos os gestos do palco.

### A prévia mostra o que vai ser gravado

- A prévia da tela e o "Salvar e seguir" seguem a mesma regra. Um formato que o "Salvar e seguir" devolveria aparece na prévia com "Pede ajuste" antes da confirmação.
- O alinhamento automático move só o elemento que o DA acabou de mexer. Nenhum outro sai do lugar, e o elemento só encaixa numa linha que fica à frente do movimento: a seta anda 1 px nos dois sentidos.
- Por causa dessas duas correções, a família confirmada numa versão anterior pede uma nova confirmação, uma vez.

### Mais rápido

- O navegador que mede as quebras de linha fica aberto enquanto a tela estiver aberta. A prévia de uma quebra nova caiu de cerca de 1,1 s para cerca de 0,1 s.

### Para quem já usava a 0.7.0

- A aprovação feita na versão anterior pede uma nova aprovação do formato, uma vez.
- Toda família confirmada na 0.7.0 pede uma nova confirmação, uma vez, com ou sem edição.
- Ao abrir um job que já existia, o desdobra lê de novo as specs dele, uma vez, porque a biblioteca de specs passou a levar a versão nova. As confirmações de spec que o DA já fez entram nessa leitura.

### O que ainda não funciona nesta versão

- Trocar os parâmetros de entrega e entregar ainda pedem comando.
