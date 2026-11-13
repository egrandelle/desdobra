# Funções de camada

Cópia da lista de funções do desdobra, versão de 29/10/2026, com a revisão da decisão 12 (sujeito fica na lista, função nova "ajuste global", frase que pede uma ação conta como CTA e rotulagem por grupo). Os exemplos de peças de cliente da lista original ficaram de fora.

Esta é a lista que o desdobra usa para dizer o que cada camada do KV faz na peça. Ela vale para qualquer marca. A sugestão do Claude é só uma sugestão: quem decide a função é o DA, na tela de briefing.

Entre crases está o id que vai no `sugestoes.json`. O arquivo aceita só esses ids, escritos assim, nos campos `funcao` e `alternativa`.

## Base

- **fundo** (`fundo`): preenche o canvas atrás de tudo.
- **imagem** (`imagem`): foto ou ilustração de cena que não é o sujeito recortado.
- **sujeito** (`sujeito`): pessoa, produto ou personagem recortado, foco visual.
  - A fronteira com "imagem" depende do julgamento do DA em cada peça. Na dúvida entre as duas, sugira uma e deixe a outra como alternativa.
- **véu de legibilidade** (`veu_de_legibilidade`): degradê, sombra ou véu que existe para dar contraste ao texto.
- **grafismo** (`grafismo`): forma, ornamento, textura ou elemento de identidade sem texto.

## Conteúdo

- **título** (`titulo`): mensagem principal.
- **texto de apoio** (`texto_de_apoio`): subtítulo, complemento ou corpo.
- **CTA** (`cta`): chamada para ação.
  - Vale também para uma frase que pede uma ação, mesmo sem botão e mesmo com URL dentro (decidido em 29/10).
- **ícone de CTA** (`icone_de_cta`): ícone, seta ou botão ligado ao CTA.
- **URL ou contato** (`url_ou_contato`): URL, @, telefone ou QR code.
- **texto legal** (`texto_legal`): texto jurídico, condições ou advertência obrigatória.
- **informação de evento** (`informacao_de_evento`): data, local, horário ou serviço.
- **destaque numérico** (`destaque_numerico`): preço, porcentagem ou número em destaque.

## Marca

- **logo principal** (`logo_principal`): marca do anunciante.
- **assinatura institucional** (`assinatura_institucional`): lockup de governo, ministério, holding ou assinatura da campanha.
  - Quando o anunciante é o governo, o DA decide em cada caso se o lockup é logo principal, assinatura ou parceiro (decisão 11). Nesse caso, sugira uma das três e deixe outra como alternativa.
- **selo** (`selo`): selo, badge ou certificação.
- **logo de parceiro** (`logo_de_parceiro`): patrocinador, co-realizador ou parceiro.

## Outros

- **ajuste global** (`ajuste_global`, nova em 29/10): ajuste ou efeito que atua sobre a peça inteira, sem ligação com um elemento só.
  - Exemplos: correção de cor, contraste, luz ou grão no topo da pilha.
  - Nos desdobramentos, ele é aplicado sobre o formato inteiro.
- **estrutura** (`estrutura`): camada sem pixel visível ou só organizacional.
  - Uma camada visível, mas coberta, que ocupa o canvas inteiro entra aqui (decisão 10).
- **fora da peça** (`fora_da_peca`): oculta, rascunho ou guia; não vai para os desdobramentos.
  - Um elemento solto, visível, mas coberto, entra aqui (decisão 10).
- **indeterminado** (`indeterminado`): tem função, mas nenhuma das opções serve. O DA explica na observação.

Quando o pacote traz na camada a regra `decisao-10` (camada coberta no KV), o motor já mostra ao DA a sugestão de estrutura ou de fora da peça pela decisão 10. Você pode sugerir a mesma função ou outra; quem escolhe é o DA.

## Rotular por grupo

Decidido em 29/10: na tela de briefing, a função que o DA dá a um grupo passa para as camadas de dentro, e o DA pode mudar uma camada específica depois. É assim que o DA pensa a peça: os efeitos de um produto fazem parte da imagem, e a linha do título faz parte do título.

Para a sugestão, isso quer dizer:
- quando um grupo inteiro faz uma coisa só (um produto com os efeitos dele, um título com a linha embaixo), sugira a função no grupo; as camadas de dentro herdam na tela;
- quando um grupo mistura funções (o título e o logo no mesmo grupo, por exemplo), sugira camada por camada e deixe o grupo sem sugestão;
- uma camada de dentro que faz algo diferente do grupo ganha a sugestão própria dela.
