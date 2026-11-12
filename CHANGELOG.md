# Novidades do desdobra

O que muda em cada versão, em palavras simples. O detalhe técnico de cada mudança está em `docs/m1-interfaces.md` e no histórico do git.

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
