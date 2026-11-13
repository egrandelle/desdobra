'use strict';
/* Tela de briefing do desdobra, so de leitura (M7a0, redesenho de 05/11).
   Regras: todo texto do job entra por textContent; posicao e tamanho pelo CSSOM; nada de pedido fora de 'self'.
   O palco usa coordenadas em pixel real da composicao; a escala muda so a exibicao. Cada palco abre em Ajustar (a
   composicao inteira na area, maior ou menor que 1:1); 1:1, Afastar e Aproximar valem ate trocar de formato.
   As abas de composicao sao miniaturas do mesmo modelo do palco, uma por grupo de proporcao parecida (revisao da
   decisao 163). O formato que a derivacao devolve mostra as versoes da galeria do motor ao lado do palco (decisao 164
   e notas de 05/11), a primeira ja escolhida. O texto da moldura nunca leva identificador do motor: tudo passa pelos
   mapas abaixo.
   M7a, fatia 1: quando a pagina chega com o token da meta dsd-csrf, a escolha de versao que o DA clica vai ao rascunho
   do job (decisao 167), gravado depois de o DA parar de clicar pela espera que o servidor manda; sem o token a tela
   continua so para ver. Todo botao com data-ato pede ao servidor um pedido de uso unico e abre a confirmacao na
   propria janela, com as duas respostas sem nada marcado e o foco no titulo (Enter nao confirma; Esc cancela);
   so o Confirmar manda o ato. Toda escrita leva o cabecalho X-Desdobra-CSRF.
   M7a, fatia 2: o passo 1 tem as decisoes do DA em botoes (decisoes 159 e 170): o modo de dados, sem nada marcado ate
   a escolha e so com as opcoes dentro do teto; o arquivo de cada linkado, entre os candidatos do motor; e cada valor de
   spec que espera confirmacao. Cada botao leva o ato e os dados dele; depois do Confirmar a tela pede o estado de novo
   e redesenha o passo 1 e a lista do que falta. O que ainda nao tem botao aparece como bloqueio em texto simples.
   M7a, fatia 3: o passo 2 (Funcoes) e o Design system guardam as escolhas do DA no rascunho (desdobra/tela/funcoes.py):
   a funcao por pasta ou por camada (a da pasta passa para dentro; a da camada vale sobre ela), a decisao das camadas
   cobertas no KV e a regra de escala e a ancora de cada funcao. Nada vem marcado: as opcoes sao as do esquema do
   briefing, mandadas pelo motor, e a funcao do briefing de teste nunca aparece como escolha. A heranca e a lista do que
   falta seguem a do motor (resolver e pendencias). Indeterminado so vai ao rascunho com a observacao escrita.
   M7a, fatia 4: a composicao e editada por familia, nunca peca a peca (decisoes 167 a 171). No palco, cada elemento
   e um botao: arrastar move, os cantos escalam, as setas movem 1 px (Shift, 10 px), mais e menos escalam, Delete
   apaga; a barra embaixo do palco tem Diminuir, Aumentar, o campo Tamanho (M7b, D3: a porcentagem sobre o tamanho
   antes das edicoes), Editar texto, Apagar e Desfazer. Durante o arraste so o no
   arrastado muda (transform), com uma linha discreta quando uma borda ou um centro encosta no de outro elemento; ao
   soltar, a edicao vai ao motor (/api/familia/previa), que a leva a cada arquivo da familia, alinha o que ficou quase
   igual e refaz o encaixe; o palco e as miniaturas de cada arquivo voltam desenhados. As edicoes e a versao ficam no
   rascunho; "Confirmar familia" e um ato da janela, com a confirmacao nela, e mexer depois volta a pedir a
   confirmacao. O texto editado vale so na familia (decisao 171) e a recusa do motor aparece no proprio editor.
   M7b, D5: o piso de escala ou de distancia que o elemento mexido pelo DA fura vem da previa em decisoes_do_da e sai
   com a marca discreta "Decisão do DA", com o valor no texto; "Pede ajuste" fica para o que o DA nao decidiu.
   Revisao do M7a: o passo 1 tem duas escolhas do DA que vao ao rascunho, sem nada marcado: a prancheta de onde a peca
   sai (so no PSD com pranchetas, com a previa de cada uma) e o giro de cada formato (o quarto de volta pede o
   sentido; o que a folha diz do giro aparece so como referencia). As duas mudam o layout: as familias voltam a pedir
   confirmacao e o passo 3 e montado de novo. Os avisos do servidor (o briefing salvo de outra versao do PSD ou das
   specs, e a tela que nao conseguiu se atualizar) ficam numa faixa logo abaixo do topo. */
(function () {
  const raiz = document.documentElement;
  const SELOS = {
    proposta: 'Primeira tentativa: proposta, não aprovada',
    escala_pura: 'Escala pura, medida',
    devolvido: 'Sem proposta ainda',
    kv: 'Mestre do KV'
  };
  /* decisao 164: nenhum formato e devolvido ao designer sem sugestao; o formato que a derivacao devolve chega com as
     versoes da galeria do motor, e so cai nos fantasmas quando a galeria nao montou nenhuma */
  const SELOS_CURTOS = { proposta: 'Proposta', escala_pura: 'Escala pura', devolvido: 'Sem proposta ainda',
    galeria: 'Versões para escolher' };
  const SELO_VARIANTE = 'proposta, não aprovada';
  /* as marcas discretas da variante: o codigo do aviso do motor vira um nome curto; o texto inteiro vai no title */
  const MARCAS = {
    texto_abaixo_de_8px: 'Texto pequeno', fundo_pouco_visivel: 'Fundo cortado', grafismo_acima_da_regra: 'Grafismo grande',
    sangria_da_arte_mudou: 'Sangria muda', conteudo_nao_cabe: 'Conteúdo apertado'
  };
  const MARCA_FALHA = 'Pede ajuste';
  /* M7b, D5: o piso que o DA furou com a edicao dele; o valor vai no texto, e a marca nao e de alerta */
  const MARCA_DO_DA = 'Decisão do DA';
  const MARCA_GERAL = 'Atenção';
  const APOIO = 'apoio de desenho, não gravado';
  const SEM_REGRA = 'sem regra';
  const POR = { camada: 'da própria camada', grupo: 'herdada da pasta', decisao_10: 'pela sugestão para camada coberta' };
  /* os mesmos nomes e explicacoes do dialogo (desdobra/tela/atos.py MODOS) */
  const MODOS = {
    a: ['Textos e miniaturas', 'O Claude recebe os nomes e os textos das camadas e miniaturas das imagens sem texto, para sugerir as funções. Uma letra desenhada em pixel ou em forma vetorial o desdobra não enxerga, e ela pode ir na imagem.'],
    b: ['Sem imagens', 'O Claude recebe os nomes e os textos das camadas, sem nenhuma imagem.'],
    c: ['Sem conteúdo', 'Nada do conteúdo do arquivo vai ao Claude. Ele recebe só contagens e medidas.']
  };
  /* M7c, S4 (decisao 190, Q4): a frase que o DA escreve ao Claude para pedir sugestoes (desdobra/tela/funcoes.py
     FRASE_PEDIR_SUGESTOES). A tela nunca chama o Claude; ela so mostra a sugestao que o desdobra conferiu */
  const FRASE_PEDIR_SUGESTOES = 'Para ver sugestões de função, escreva ao Claude: quero sugestões';
  const PEDIDO_SUGESTOES = 'quero sugestões';
  // a consulta leve do sha256 das sugestoes, so com o passo 2 aberto
  const SUGESTOES_MS = 3000;
  const SO_PARA_VER = 'Nesta janela a tela só mostra. As escolhas ficam para a janela que o desdobra abre para você.';
  const SITUACOES = { derivado: 'proposta', devolvido: 'sem proposta ainda' };
  /* as funcoes do briefing (briefing/modelo.py CLASSES) com acento, para o DA; o id cru nunca vai a tela */
  const FUNCOES = {
    fundo: 'fundo', imagem: 'imagem', sujeito: 'sujeito', veu_de_legibilidade: 'véu de legibilidade',
    grafismo: 'grafismo', titulo: 'título', texto_de_apoio: 'texto de apoio', cta: 'CTA',
    url_ou_contato: 'URL ou contato', texto_legal: 'texto legal', informacao_de_evento: 'informação de evento',
    destaque_numerico: 'destaque numérico', icone_de_cta: 'ícone de CTA', logo_principal: 'logo principal',
    assinatura_institucional: 'assinatura institucional', selo: 'selo', logo_de_parceiro: 'logo de parceiro',
    ajuste_global: 'ajuste global', estrutura: 'estrutura', fora_da_peca: 'fora da peça', indeterminado: 'indeterminado'
  };
  /* os identificadores do motor em portugues para o DA (derivacao/escala.py REGRAS; laudo TIPOS) */
  const REGRAS = {
    largura: 'pela largura', altura: 'pela altura', lado_curto: 'pelo lado menor', lado_longo: 'pelo lado maior',
    raiz_area: 'pela área', constante: 'tamanho fixo', contain: 'cabe inteiro na peça', cover: 'cobre a peça inteira'
  };
  const TIPOS = {
    texto: 'texto', forma: 'forma', pixel: 'imagem', cor_solida: 'cor sólida', preenchimento: 'preenchimento',
    grupo: 'pasta de camadas', prancheta: 'prancheta', smart_embutido: 'objeto inteligente embutido',
    smart_linkado: 'objeto inteligente linkado', ajuste: 'camada de ajuste', outro: 'outro tipo'
  };
  /* o que cada regra faz, em palavras de designer (derivacao/escala.py) */
  const REGRAS_TEXTO = {
    largura: 'Acompanha a largura da peça.', altura: 'Acompanha a altura da peça.',
    lado_curto: 'Acompanha o lado menor da peça.', lado_longo: 'Acompanha o lado maior da peça.',
    raiz_area: 'Acompanha a área da peça.', constante: 'Fica sempre do mesmo tamanho.',
    contain: 'Cabe inteiro na peça, sem corte.', cover: 'Cobre a peça inteira e pode ser cortado.'
  };
  const ANCORA_X = { esquerda: 'à esquerda', centro: 'no centro', direita: 'à direita' };
  const ANCORA_Y = { topo: 'No topo', meio: 'No meio', base: 'Na base' };
  /* as classes do briefing (briefing/modelo.py CLASSES) como grupos de botoes do passo 2 */
  const CLASSES_FUNCAO = [['base', 'Imagem e fundo'], ['texto', 'Texto'], ['marca', 'Marca'],
    ['global', 'Da peça inteira'], ['fora', 'Fora da peça'], ['indeterminado', 'Outra função']];
  const INVERSA = { estrutura: 'fora_da_peca', fora_da_peca: 'estrutura' };
  const PASSOS = { lido: 1, funcoes: 2, pecas: 3, design: 4, formatos: 5 };
  const AMOSTRA = 'Aa Bb Cc 0123';
  const PASSO_ZOOM = 1.25;
  const MARGEM = 40;
  const MINI = { largura: 216, altura: 104, baixa: 84 };
  const MINI_VARIANTE = { largura: 88, altura: 64 };
  const MINI_MEMBRO = { largura: 84, altura: 46 };
  let estado = null;
  const familiaCss = new Map();
  const previas = new Map();
  const previasSalvas = new Map();
  const vista = { k: null, limpo: false, nomes: true, formato: null, modelo: null, variante: null, familia: null, grupo: null };
  const metaCsrf = document.querySelector('meta[name="dsd-csrf"]');
  const csrf = metaCsrf ? metaCsrf.content : '';
  const escrita = csrf !== '';
  const rascunho = { job: null, laudo: null, espera: null, espera_id: null, familias: {}, tentativas: 0 };
  /* revisao 1 da fase D: as esperas antes de cada nova tentativa do rascunho que nao gravou */
  const REPETIR_RASCUNHO_MS = [1000, 2000, 4000, 8000, 8000];
  /* as escolhas do passo 2 e do Design system, na forma do rascunho (desdobra/tela/funcoes.py) */
  const CAMPOS_P2 = ['funcoes', 'cobertas', 'design', 'design_camadas'];
  const p2 = { funcoes: {}, cobertas: {}, design: {}, design_camadas: {} };
  const p2obs = {}; // indeterminado sem observacao: fica so na tela ate o DA escrever
  /* M7c, S4: a sugestao do Claude que o desdobra conferiu (GET /api/sugestoes), por camada ou pasta. Ela so aparece:
     nunca entra em p2 sem o clique do DA em "Usar". chegou: a leitura nova que espera o "Mostrar" */
  const sug = { modo: null, sha: null, por: new Map(), chegou: null, lida: false, consultando: false };
  /* as escolhas do passo 1 (revisao do M7a): a prancheta (id do quadro) e o giro por chave do formato na folha */
  const p1 = { quadro: null, rotacoes: {} };
  const giroSemSentido = {}; // quarto de volta escolhido sem o sentido: fica so na tela ate o DA escolher o sentido
  const GIROS = [[0, 'Sem giro'], [90, '90 graus'], [180, '180 graus'], [270, '270 graus']];
  const SENTIDOS = [['horario', 'Horário'], ['anti_horario', 'Anti-horário']];
  const TEXTO_RASCUNHO = {
    pronto: 'Suas escolhas ficam salvas no rascunho',
    pendente: 'Salvando no rascunho', // revisao 2 da fase D: a mudanca que espera a gravacao nunca parece salva
    salvando: 'Salvando no rascunho',
    salvo: 'Salvo no rascunho',
    erro: 'Não foi possível salvar a última escolha. Ela continua na tela, e o desdobra tenta de novo sozinho.',
    erro_parado: 'Não foi possível salvar a última escolha. Ela continua na tela. Faça uma mudança para tentar de novo.',
    outro_laudo: 'O PSD foi lido de novo, e as escolhas antigas ficaram de fora. Comece pelas versões desta leitura.'
  };
  const NOTA_GALERIA_RASCUNHO = 'Escolha uma versão para começar. A escolha fica salva no rascunho.';
  /* edicao por familia (fatia 4) */
  const ed = { previa: null, pedido: 0, selecionado: null, tecla: 0, arraste: null, esperaQuebra: null,
    /* M7b, D1: os elementos escolhidos juntos (o selecionado e o ultimo deles) e o modo "Escolher vários" */
    selecao: [], varios: false,
    /* M7b, D2: por onde alinhar no quadro (a margem ou a area segura de cada arquivo) e o ultimo alinhamento pedido,
       para a linha no palco e a frase quando a previa volta */
    referencia: 'margem', alinhou: null,
    /* revisao 1 da fase D: o tamanho de cada um quando o grupo de tamanhos diferentes foi escolhido (o 100 do campo) */
    baseGrupo: null };
  /* M7b, D2: os botoes de alinhar no quadro, o alvo de cada um e a frase depois do alinhamento */
  const ALINHAR = { 'ed-al-esquerda': 'margem_esquerda', 'ed-al-centro': 'centro_horizontal',
    'ed-al-direita': 'margem_direita', 'ed-al-topo': 'topo', 'ed-al-meio': 'centro_vertical', 'ed-al-base': 'base' };
  const FRASE_ALINHAR = { margem_esquerda: 'Encostou à esquerda', centro_horizontal: 'Ficou no centro da largura',
    margem_direita: 'Encostou à direita', topo: 'Encostou no topo', centro_vertical: 'Ficou no meio da altura',
    base: 'Encostou na base' };
  const FRASE_REFERENCIA = { margem: ', pela margem de cada arquivo desta família.',
    area_segura: ', pela área segura de cada arquivo desta família.' };
  const RETANGULO_MIN_PX = 3; // retangulo menor que isto, em px da tela, e so um clique
  /* M7b, C3: a quebra de linha mudada pede a previa (e a medida no desdobra) so depois de 300 ms sem clique */
  const ESPERA_QUEBRA_MS = 300;
  const PASSO_SETA = 1;
  const PASSO_SETA_LONGO = 10;
  const FATOR_TECLA = 1.05;
  const JUNTAR_TECLAS_MS = 800;
  const ESCALA_MIN = 0.05;
  const ALCA = 10; // lado da alca do canto, em px da tela
  const MEIO_PX = 0.5; // arraste menor que isto e so um clique
  // a folga, em px da peca, do escolhido que chega a borda (a de derivacao.enquadramento_tolerancia_px no desdobra)
  const BORDA_PX = 0.5;
  const FRASE_GRUPO_MISTO = 'Os elementos escolhidos têm tamanhos diferentes. Em Tamanho, 100% é o tamanho de cada ' +
    'um quando você escolheu o grupo.';
  const APAGAR_SO_UM ='Para apagar, escolha um elemento só. Com vários escolhidos, nenhum é apagado.';
  const FATOR_IGUAL = 0.001;
  const CASAS_FRACAO = 1e6;
  /* M7b, D3: o tamanho por numero. Os limites vem do desdobra (estado.edicao, tela.escala_min e tela.escala_max); a
     folga cobre o arredondamento do fator em 6 casas (desdobra.tela.edicao.FOLGA_ESCALA) */
  const ESCALA_PADRAO = [0.25, 4];
  const FOLGA_ESCALA = 1e-4;
  const POR_CENTO = 100;
  const CASAS_TAMANHO = 10; // o tamanho aparece com uma casa depois da virgula, so quando ela nao e zero
  const CONTEUDO = ['titulo', 'texto_de_apoio', 'cta', 'icone_de_cta', 'url_ou_contato', 'texto_legal',
    'informacao_de_evento', 'destaque_numerico', 'logo_principal', 'assinatura_institucional', 'selo', 'logo_de_parceiro'];
  const SELO_CONFIRMADA = 'Família confirmada';
  // a marca curta da familia que mudou de formatos, na lista das familias (a frase inteira vem do servidor)
  const MINI_MUDOU = 'Mudou, confirme de novo';
  // o motivo do motor para o formato com valor de spec a espera do DA (desdobra.derivacao.nucleo.MOTIVO_SPEC_POR_CONFIRMAR)
  const MOTIVO_SEM_SPEC = 'spec_por_confirmar';
  // o formato que deriva da mestre propria cujo formato espera a spec (desdobra.derivacao.nucleo.MOTIVO_MESTRE_POR_CONFIRMAR)
  const MOTIVO_SEM_SPEC_DA_MESTRE = 'mestre_por_confirmar';
  const FAMILIA_SEM_SPEC = 'Um formato desta família espera a confirmação de um valor de spec. Confirme os valores dele em Valores de spec, no passo 1, e depois confirme a família.';
  const FAMILIA_SEM_SPEC_DA_MESTRE = 'O formato da mestre desta família espera a confirmação de um valor de spec. Confirme os valores dele em Valores de spec, no passo 1, e depois confirme a família.';
  /* Salvar e seguir (decisao 167): so com todas as familias confirmadas; depois, o proximo passo em palavras */
  const SALVAR = 'Salvar e seguir';
  const SALVO = 'Briefing salvo';
  const DICA_SO_VER = 'Nesta janela nada é gravado.';
  const DICA_PRONTA = 'Tudo confirmado. Pode salvar.';
  const DICA_P2 = 'Faltam escolhas nas funções ou no design system.';
  const DICA_MODO = 'Escolha o modo de dados no passo 1.';
  const DICA_SEM_FORMATOS = 'O job ainda não tem formato com medida em pixels. Veja o passo 1.';
  const DICA_QUADRO = 'Escolha a prancheta da peça no passo 1.';
  const DICA_GIRO = 'Escolha o giro de cada formato no passo 1.';
  const DICA_MEDIDA = 'Escolha a medida do formato com duas medidas no passo 1.';
  /* curto para caber em duas linhas no rodape a 1280 px (revisao do M7b, fase B) */
  const AVISO_SALVO = 'O briefing está salvo. Cada formato parte agora das famílias que você confirmou. ' +
    'O render e a aprovação ficam no passo 5.';
  let salvoNaTela = false;
  let p2Mudou = false;
  const ajustes = new WeakMap();
  const mundos = new WeakMap(); // o mundo de cada palco desenhado, para marcar camadas por cima
  const regua = document.createElement('canvas').getContext('2d');

  function el(tag, texto, classe) {
    const e = document.createElement(tag);
    if (texto !== undefined && texto !== null) e.textContent = String(texto);
    if (classe) e.className = classe;
    return e;
  }
  function limpar(no) { while (no.firstChild) no.removeChild(no.firstChild); }
  /* o unico GET da tela: pedir() le o JSON e carregarImagem() le a imagem pela mesma chamada */
  function buscar(rota) {
    return fetch(rota, { credentials: 'same-origin', cache: 'no-store' }).then(function (r) {
      if (!r.ok) throw new Error('rota ' + r.status);
      return r;
    });
  }
  function pedir(rota) {
    return buscar(rota).then(function (r) { return r.json(); });
  }
  /* a imagem de /render/<id> e /final/<id> pedida sempre de novo ao servidor. A URL e a mesma para o formato, e o
     Chromium reaproveita na mesma pagina a imagem que ja carregou para ela, mesmo com no-store: depois de um render
     novo, o DA veria o master ou o arquivo final de antes. O fetch sem cache vira um blob local (a CSP aceita img-src
     blob:), solto quando a imagem carrega ou falha. A falha do pedido chega a imagem como o erro dela */
  function carregarImagem(img, rota) {
    buscar(rota).then(function (r) { return r.blob(); }).then(function (b) {
      const url = URL.createObjectURL(b);
      const soltar = function () { URL.revokeObjectURL(url); };
      img.addEventListener('load', soltar, { once: true });
      img.addEventListener('error', soltar, { once: true });
      img.src = url;
    }).catch(function () { img.dispatchEvent(new Event('error')); });
  }
  /* o unico POST da tela. aoFechar (revisao 2 da fase D): o pedido sobrevive ao fechamento da janela (keepalive) */
  function enviar(rota, dados, aoFechar) {
    return fetch(rota, {
      method: 'POST', credentials: 'same-origin', cache: 'no-store', keepalive: !!aoFechar,
      headers: { 'Content-Type': 'application/json', 'X-Desdobra-CSRF': csrf },
      body: JSON.stringify(dados)
    }).then(function (r) {
      if (!r.ok) throw new Error('rota ' + r.status);
      return r.status === 204 ? null : r.json();
    });
  }

  /* ---------------------------------------------------------------- rascunho (decisoes 164 e 167) */
  function marcarRascunho(situacao) {
    const antes = raiz.dataset.rascunho;
    raiz.dataset.rascunho = situacao;
    const selo = document.getElementById('selo');
    selo.textContent = situacao === 'erro' && rascunho.tentativas >= REPETIR_RASCUNHO_MS.length ?
      TEXTO_RASCUNHO.erro_parado : TEXTO_RASCUNHO[situacao];
    selo.dataset.estado = situacao;
    // "Confirmar família" segue o rascunho gravado: desliga no erro e volta quando ele grava
    if ((antes === 'erro') !== (situacao === 'erro') && typeof atualizarBotaoFamilia === 'function' && vista.familia) {
      atualizarBotaoFamilia();
    }
  }
  function lerRascunho() {
    if (!escrita) return Promise.resolve(null);
    document.getElementById('nota-galeria').textContent = NOTA_GALERIA_RASCUNHO;
    return pedir('/api/rascunho').then(function (r) {
      rascunho.job = r.job_id;
      rascunho.laudo = r.laudo_sha256;
      rascunho.espera = r.espera_ms;
      rascunho.familias = (r.rascunho && r.rascunho.familias) || {};
      CAMPOS_P2.forEach(function (k) { p2[k] = (r.rascunho && r.rascunho[k]) || {}; });
      p1.quadro = (r.rascunho && r.rascunho.quadro) || null;
      p1.rotacoes = (r.rascunho && r.rascunho.rotacoes) || {};
      marcarRascunho(r.de_outro_laudo ? 'outro_laudo' : 'pronto');
    }).catch(function () { marcarRascunho('erro'); });
  }
  function corpoDoRascunho() {
    const corpo = { job_id: rascunho.job, laudo_sha256: rascunho.laudo, familias: rascunho.familias };
    CAMPOS_P2.forEach(function (k) { if (Object.keys(p2[k]).length) corpo[k] = p2[k]; });
    if (p1.quadro) corpo.quadro = p1.quadro;
    if (Object.keys(p1.rotacoes).length) corpo.rotacoes = p1.rotacoes;
    return corpo;
  }
  function gravarRascunho() {
    rascunho.espera_id = null;
    marcarRascunho('salvando');
    // o passo 2 ou o Design system mudou: depois de gravado, o servidor monta o passo 3 de novo (o GET do estado)
    const refazer = p2Mudou;
    p2Mudou = false;
    return enviar('/api/rascunho', corpoDoRascunho())
      .then(function () {
        rascunho.tentativas = 0;
        if (rascunho.espera_id === null) marcarRascunho('salvo');
      })
      .then(function () { return refazer ? refazerPasso3() : null; })
      .then(function () { return true; })
      .catch(function () {
        if (refazer) p2Mudou = true;
        marcarRascunho('erro');
        repetirRascunho();
        return false;
      });
  }
  /* o rascunho que nao gravou (revisao 1 da fase D): a pagina tenta de novo sozinha, com esperas maiores a cada vez;
     a mudanca nova do DA tambem tenta. Enquanto isso, "Confirmar família" fica desligado */
  function repetirRascunho() {
    if (rascunho.espera_id !== null || rascunho.tentativas >= REPETIR_RASCUNHO_MS.length) return;
    rascunho.espera_id = setTimeout(gravarRascunho, REPETIR_RASCUNHO_MS[rascunho.tentativas]);
    rascunho.tentativas += 1;
  }
  /* o passo 3 montado de novo com o passo 2 do rascunho: as familias, as previas e o KV do passo 2, sem abrir a tela
     de novo; enquanto o passo 2 nao fecha, o passo 3 espera e diz o que falta */
  function refazerPasso3() {
    return pedir('/api/estado').then(aplicarEstado);
  }
  /* o estado novo do servidor inteiro na pagina: o passo 1, a arvore do passo 2 quando a prancheta mudou, o passo 3 e
     os avisos (depois de um ato ou do rascunho gravado com escolha que muda o layout) */
  function aplicarEstado(e) {
    const quadroAntes = estado.funcoes && estado.funcoes.decisoes ? estado.funcoes.decisoes.quadro : null;
    estado.orientacoes = e.orientacoes;
    estado.passo_3 = e.passo_3;
    estado.devolucoes = e.devolucoes;
    estado.funcoes.palco_kv = e.funcoes.palco_kv;
    estado.lido = e.lido;
    estado.faltam = e.faltam;
    estado.briefing = e.briefing;
    estado.aviso_atualizacao = e.aviso_atualizacao;
    salvoNaTela = !!(e.briefing && e.briefing.salvo);
    previas.clear();
    previasSalvas.clear();
    trocarPainel(e);
    if ((e.funcoes.decisoes || {}).quadro !== quadroAntes) {
      // a prancheta escolhe as camadas do passo 2: a arvore e o Design system sao montados de novo
      estado.funcoes = e.funcoes;
      p2idx.por = new Map();
      p2idx.filhos = new Map();
      p2idx.atual = null;
      iniciarPasso2(e.funcoes);
    }
    document.getElementById('aviso-passo-2').hidden = !!(e.passo_3 && e.passo_3.passo_2_aplicado);
    limpar(document.getElementById('orientacoes'));
    limpar(document.getElementById('composicoes'));
    if (!document.getElementById('passo-pecas').hidden) iniciarPecas(null);
    mostrarAvisos(e);
    atualizarFaltam();
    // M7c, M4: o padrao da marca citado no Design system segue a marca de agora
    if (!document.getElementById('passo-design').hidden) montarDesign();
    // M7c, S4: o ato (o modo de dados, por exemplo) pode ter mudado o que a tela mostra como sugestao
    if (sug.lida) lerSugestoes();
    return Promise.resolve(montarLido(e.lido)).then(sincronizarConfirmacoes);
  }
  /* as familias que o servidor deixou de contar como confirmadas (um formato entrou ou saiu, ou voltou de outra
     familia, com a tela aberta) deixam de estar confirmadas na pagina tambem: o DA pode confirmar de novo, e Salvar e
     seguir espera. So tira a confirmacao, nunca poe, e as edicoes que esperam a gravacao ficam */
  function sincronizarConfirmacoes() {
    if (!escrita) return null;
    return pedir('/api/rascunho').then(function (r) {
      const gravadas = (r.rascunho && r.rascunho.familias) || {};
      Object.keys(rascunho.familias).forEach(function (g) {
        const f = rascunho.familias[g];
        if (f && f.confirmada && !(gravadas[g] && gravadas[g].confirmada)) { f.confirmada = false; delete f.confirmacao; }
      });
      if (vista.familia) atualizarBotaoFamilia();
      atualizarSalvar();
    }).catch(function () { return null; });
  }
  /* as familias do estado sem a frase de cada uma: a frase que muda sozinha nao redesenha o passo 3 */
  function semAvisos(orientacoes) {
    return JSON.stringify(orientacoes, function (k, v) { return k === 'aviso' ? undefined : v; });
  }
  /* a faixa de avisos do servidor: a tela que nao se atualizou, o render que a janela anterior deixou pela metade e o
     briefing salvo de outra versao dos arquivos */
  function mostrarAvisos(e) {
    const no = document.getElementById('avisos-tela');
    limpar(no);
    const textos = [];
    if (e.aviso_atualizacao) textos.push(e.aviso_atualizacao);
    if (e.render_inacabado && e.render_inacabado.texto) textos.push(e.render_inacabado.texto);
    ((e.briefing && e.briefing.avisos) || []).forEach(function (t) { textos.push(t); });
    textos.forEach(function (t) { no.appendChild(el('p', t, 'aviso-tela')); });
    no.hidden = !textos.length;
  }
  /* cada mudanca recomeca a espera: o rascunho vai ao servidor quando o DA para de mexer */
  function mudouRascunho() {
    if (!escrita || rascunho.espera === null) return;
    // o briefing salvo deixa de valer para a tela: a mudanca nova pede outro Salvar e seguir
    if (salvoNaTela) { salvoNaTela = false; atualizarSalvar(); }
    clearTimeout(rascunho.espera_id);
    rascunho.tentativas = 0; // a mudanca nova tenta de novo, tambem depois das tentativas sozinhas
    marcarRascunho('pendente');
    rascunho.espera_id = setTimeout(gravarRascunho, rascunho.espera);
  }
  /* a janela que fecha com o rascunho por gravar (revisao 2 da fase D): a espera, a gravacao em andamento ou a que
     falhou vao ao servidor na hora, por um pedido que sobrevive ao fechamento (keepalive), com o mesmo cookie, o mesmo
     cabecalho do CSRF e o mesmo corpo da gravacao de sempre. Quando a ultima gravacao falhou, ou o corpo passa do que
     o pedido que sobrevive leva, o navegador pergunta antes de fechar */
  const KEEPALIVE_MAX = 60000; // bytes: o Chromium leva ate 64 KiB nos pedidos que sobrevivem ao fechamento
  function gravarAoFechar() {
    const situacao = raiz.dataset.rascunho;
    if (!escrita || rascunho.espera === null || rascunho.fechando ||
        (situacao !== 'pendente' && situacao !== 'salvando' && situacao !== 'erro')) return true;
    rascunho.fechando = true; // beforeunload e pagehide: um pedido so
    clearTimeout(rascunho.espera_id);
    rascunho.espera_id = null;
    const corpo = corpoDoRascunho();
    if (JSON.stringify(corpo).length > KEEPALIVE_MAX) return false;
    try {
      enviar('/api/rascunho', corpo, true).catch(function () { return null; });
    } catch (e) {
      return false;
    }
    if (situacao === 'erro') return false;
    raiz.dataset.rascunho = 'salvando';
    return true;
  }
  window.addEventListener('beforeunload', function (ev) {
    if (gravarAoFechar()) return;
    // o DA pode ficar na pagina: as tentativas sozinhas continuam, e a proxima vez que ele fechar manda de novo
    rascunho.fechando = false;
    repetirRascunho();
    ev.preventDefault();
    ev.returnValue = '';
  });
  window.addEventListener('pagehide', function () { gravarAoFechar(); });
  function escolherNoRascunho(vid) {
    if (!escrita || !vista.familia) return;
    const f = rascunho.familias[vista.familia] || { versao: null, confirmada: false, edicoes: [] };
    if (f.versao === vid) return;
    f.versao = vid;
    f.confirmada = false;
    delete f.confirmacao;
    rascunho.familias[vista.familia] = f;
    mudouRascunho();
    if (typeof atualizarBotaoFamilia === 'function') atualizarBotaoFamilia();
  }

  /* ---------------------------------------------------------------- cronometro da mestre (M7b, C5)
     cada clique ou tecla manda ao servidor um sinal com a familia aberta no passo 3 (ou nenhuma, fora dele) e as
     edicoes e as quebras mudadas desde o sinal anterior. Sai no maximo um sinal por segundo; o que espera leva o
     atraso do ultimo clique. O servidor mede com o relogio dele (desdobra/tela/cronometro.py), e nada aparece na tela */
  const SINAL_MS = 1000;
  const cron = { pendente: null, ultimoEnvio: -Infinity, espera: null };
  function familiaDoSinal() {
    return !document.getElementById('passo-pecas').hidden && vista.familia ? vista.familia : null;
  }
  /* M7c, S4: com o passo 2 aberto, o sinal leva tambem passo_2 e se havia sugestao do Claude a vista */
  function passo2DoSinal() {
    if (document.getElementById('passo-funcoes').hidden) return null;
    return { passo_2: true, sugestao: sug.por.size > 0 };
  }
  function chaveDoSinal(familia, p) { return String(familia) + '|' + (p ? (p.sugestao ? 's' : 'p') : ''); }
  function anotarSinal(familia, edicoes, quebras) {
    if (!escrita) return;
    const p = familia === null ? passo2DoSinal() : null;
    const chave = chaveDoSinal(familia, p);
    // a familia (ou o passo 2) mudou: o sinal da anterior sai antes, com o tempo dela
    if (cron.pendente && cron.pendente.chave !== chave) enviarSinal();
    if (!cron.pendente) cron.pendente = { familia: familia, passo: p, chave: chave, edicoes: 0, quebras: 0, em: 0 };
    cron.pendente.edicoes += edicoes;
    cron.pendente.quebras += quebras;
    cron.pendente.em = performance.now();
    raiz.dataset.sinal = 'esperando';
    const falta = cron.ultimoEnvio + SINAL_MS - performance.now();
    if (falta <= 0) enviarSinal();
    else if (!cron.espera) cron.espera = setTimeout(enviarSinal, falta);
  }
  function enviarSinal() {
    clearTimeout(cron.espera);
    cron.espera = null;
    const p = cron.pendente;
    if (!p) return;
    cron.pendente = null;
    const agora = performance.now();
    cron.ultimoEnvio = agora;
    raiz.dataset.sinal = 'enviando';
    const corpo = { familia: p.familia, edicoes: p.edicoes, quebras: p.quebras,
      atraso_ms: Math.max(0, Math.round(agora - p.em)) };
    if (p.passo) { corpo.passo_2 = true; corpo.sugestao = p.passo.sugestao; }
    // a medicao nunca atrapalha o DA: o sinal recusado ou perdido so fica de fora
    enviar('/api/medicao', corpo).catch(function () { return null; }).then(function () {
      if (!cron.pendente && !cron.espera) raiz.dataset.sinal = 'enviado';
    });
  }
  function contarNoCronometro(tipo) {
    anotarSinal(familiaDoSinal(), tipo === 'edicoes' ? 1 : 0, tipo === 'quebras' ? 1 : 0);
  }
  /* o sinal sai depois dos tratadores do clique: o clique na aba de uma familia ja conta para ela */
  ['pointerdown', 'click', 'keydown'].forEach(function (tipo) {
    document.addEventListener(tipo, function () {
      setTimeout(function () { anotarSinal(familiaDoSinal(), 0, 0); }, 0);
    }, true);
  });

  /* ---------------------------------------------------------------- confirmacao na janela (decisao 159) */
  function confirmarNaJanela(p) {
    const d = document.getElementById('confirmacao');
    const titulo = document.getElementById('confirmacao-titulo');
    const sim = d.querySelector('[data-resposta=sim]');
    const nao = d.querySelector('[data-resposta=nao]');
    titulo.textContent = p.titulo;
    document.getElementById('confirmacao-texto').textContent = p.texto;
    sim.textContent = p.sim;
    nao.textContent = p.nao;
    // o que o ato mostra alem do texto (M7b, B5): os formatos do render, o arquivo final de cada formato a aprovar
    const extra = document.getElementById('confirmacao-extra');
    limpar(extra);
    extra.hidden = !p.extra;
    if (p.extra) extra.appendChild(p.extra);
    d.classList.toggle('confirmacao-larga', !!p.larga);
    const antes = document.activeElement;
    return new Promise(function (resolver) {
      let respondido = false;
      function fim(resposta) {
        if (respondido) return; // uma resposta por pedido, mesmo com Esc e clique juntos
        respondido = true;
        d.removeEventListener('cancel', aoCancelar);
        sim.removeEventListener('click', aoSim);
        nao.removeEventListener('click', aoNao);
        if (d.open) d.close();
        limpar(extra);
        extra.hidden = true;
        d.classList.remove('confirmacao-larga');
        if (antes && antes.focus) antes.focus();
        resolver(resposta);
      }
      function aoCancelar(ev) { ev.preventDefault(); fim(false); }
      function aoSim() { fim(true); }
      function aoNao() { fim(false); }
      d.addEventListener('cancel', aoCancelar);
      sim.addEventListener('click', aoSim);
      nao.addEventListener('click', aoNao);
      d.showModal();
      titulo.focus(); // nenhuma resposta em foco: Enter nao confirma nada
    });
  }
  /* depois de um ato feito: o estado novo do servidor redesenha o passo 1 e a lista do que falta */
  function recarregarEstado() {
    return pedir('/api/estado').then(function (e) {
      // o ato de spec pode mudar os formatos e as familias: so entao o estado inteiro volta, como depois do rascunho
      // gravado; nos outros atos o palco fica onde o DA estava, e so a frase da familia muda (a familia confirmada)
      if (semAvisos(e.orientacoes) !== semAvisos(estado.orientacoes)) return aplicarEstado(e);
      trocarAvisos(e.orientacoes || []);
      estado.lido = e.lido;
      estado.faltam = e.faltam;
      estado.briefing = e.briefing;
      estado.aviso_atualizacao = e.aviso_atualizacao;
      salvoNaTela = !!(e.briefing && e.briefing.salvo);
      trocarPainel(e);
      mostrarAvisos(e);
      atualizarFaltam();
      // M7c, M4: a marca escolhida ou trocada no passo 1 muda o padrao citado no Design system
      if (!document.getElementById('passo-design').hidden) montarDesign();
      // revisao do S4: depois de qualquer ato (o modo de dados, por exemplo), o modo que vale e as sugestoes de novo
      if (sug.lida) lerSugestoes();
      return Promise.resolve(montarLido(e.lido)).then(sincronizarConfirmacoes);
    });
  }
  const depoisDoAto = {};
  /* o ato leva o que a janela mostra: o servidor confere contra o rascunho gravado, no pedido e no Confirmar. Na
     familia, as edicoes e as quebras de linha (a quebra e edicao da familia; a quebra que nao gravou nunca e
     confirmada as cegas) */
  function comVista(nome, dados) {
    if (nome === 'familia') {
      const f = rascunho.familias[dados.familia];
      return Object.assign({}, dados, { edicoes: (f && f.edicoes) || [], quebras: (f && f.quebras) || [] });
    }
    if (nome === 'salvar') return { rascunho: corpoDoRascunho() };
    return dados;
  }
  function pedirAto(nome, dados, aoRecusar) {
    /* aoRecusar (revisao do M3): quem chama sabe dizer ao DA por que o motor recusou o pedido (403 antes da janela);
       entao o aviso fica com ele, sem a frase de tentar de novo, que nao resolve */
    let recusado = false;
    raiz.dataset.estadoAto = '';
    // o rascunho que espera, ou que nao gravou, vai antes: o ato confirma o que esta gravado. Sem gravar, o ato nao
    // vai (revisao 1 da fase D)
    let antes = Promise.resolve(true);
    if (rascunho.espera_id !== null || raiz.dataset.rascunho === 'erro') {
      clearTimeout(rascunho.espera_id);
      antes = gravarRascunho();
    }
    return antes.then(function (gravou) {
      if (gravou === false) throw new Error('rascunho');
      return enviar('/api/ato/pedir', { ato: nome, dados: comVista(nome, dados || {}) }).catch(function (e) {
        recusado = !!(e && e.message === 'rota 403');
        throw e;
      });
    }).then(function (p) {
      // M7c, M5: a janela do registro do padrao da marca mostra o que vai ao perfil
      const extra = nome === 'marca_registrar' ? extraDoRegistro() : null;
      return confirmarNaJanela(extra ? Object.assign({}, p, { extra: extra, larga: true }) : p).then(function (sim) {
        if (!sim) return enviar('/api/ato/cancelar', { pedido: p.pedido }).then(function () { raiz.dataset.estadoAto = 'cancelado'; });
        const chave = JSON.stringify(dados || {});
        return enviar('/api/ato/confirmar', { pedido: p.pedido, resposta: 'confirmar' })
          .then(recarregarEstado)
          .then(function () { return depoisDoAto[nome] ? depoisDoAto[nome](dados) : null; })
          .then(function () {
            raiz.dataset.estadoAto = 'feito';
            /* o botao clicado foi redesenhado: o foco volta ao botao novo do mesmo ato, para o teclado seguir dali */
            const novo = Array.from(document.querySelectorAll('button[data-ato]')).find(function (b) {
              return b.dataset.ato === nome && b.dataset.dados === chave;
            });
            if (novo) novo.focus();
          });
      });
    }).catch(function () {
      raiz.dataset.estadoAto = 'erro';
      if (recusado && aoRecusar) { aoRecusar(); return; }
      document.getElementById('selo').textContent = 'A tela não conseguiu registrar a ação. Tente de novo.';
    });
  }
  function ligarAtos() {
    if (!escrita) return;
    document.addEventListener('click', function (ev) {
      const b = ev.target && ev.target.closest ? ev.target.closest('button[data-ato]') : null;
      if (!b || b.disabled || !b.dataset.ato) return;
      ev.preventDefault();
      let dados = {};
      try { dados = b.dataset.dados ? JSON.parse(b.dataset.dados) : {}; } catch (e) { return; }
      pedirAto(b.dataset.ato, dados);
    });
  }

  function semSublinhado(v) { return String(v).replace(/_/g, ' '); }
  function nomeFuncao(f) { return f ? (FUNCOES[f] || semSublinhado(f)) : 'sem função'; }
  function nomeRegra(r) { return r ? (REGRAS[r] || semSublinhado(r)) : SEM_REGRA; }
  function nomeTipo(t) { return t ? (TIPOS[t] || semSublinhado(t)) : TIPOS.outro; }
  function nomeAncora(a) { return a ? a.map(semSublinhado).join(', ') : 'sem âncora'; }
  function dimensao(l, a) { return l + 'x' + a; }
  function plural(n, um, varios) { return n + ' ' + (n === 1 ? um : varios); }
  function item(lista, texto, classe) { const li = el('li', texto, classe); lista.appendChild(li); return li; }
  function botao(texto, classe) { const b = el('button', texto, classe); b.type = 'button'; return b; }
  function previa(fid) {
    if (previas.has(fid)) return previas.get(fid);
    const p = pedir('/api/previa/' + encodeURIComponent(fid));
    previas.set(fid, p);
    p.catch(function () { previas.delete(fid); });
    return p;
  }
  /* a previa do passo 5: o servidor leva nela o layout salvo do formato (salvo), que muda depois de cada ato. A marca do
     layout (f.layout, do painel) diz quando pedir de novo */
  function previaSalva(f) {
    const guardada = previasSalvas.get(f.id);
    if (guardada && guardada.marca === f.layout) return guardada.promessa;
    const p = pedir('/api/previa/' + encodeURIComponent(f.id));
    previasSalvas.set(f.id, { marca: f.layout, promessa: p });
    p.catch(function () { previasSalvas.delete(f.id); });
    return p;
  }
  /* setas movem entre as abas de uma lista (role=tablist), Home e End vao as pontas */
  function navegarComSetas(lista) {
    lista.addEventListener('keydown', function (ev) {
      const abas = Array.from(lista.querySelectorAll('[role=tab]'));
      const i = abas.indexOf(document.activeElement);
      if (i < 0) return;
      let j = null;
      if (ev.key === 'ArrowRight' || ev.key === 'ArrowDown') j = (i + 1) % abas.length;
      else if (ev.key === 'ArrowLeft' || ev.key === 'ArrowUp') j = (i - 1 + abas.length) % abas.length;
      else if (ev.key === 'Home') j = 0;
      else if (ev.key === 'End') j = abas.length - 1;
      if (j === null) return;
      ev.preventDefault();
      abas[j].focus();
      abas[j].click();
    });
  }

  /* ---------------------------------------------------------------- passos */
  function mostrarPasso(id) {
    document.querySelectorAll('#passos [role=tab]').forEach(function (b) {
      const sim = b.dataset.passo === id;
      b.setAttribute('aria-selected', sim ? 'true' : 'false');
      b.tabIndex = sim ? 0 : -1;
    });
    Object.keys(PASSOS).forEach(function (p) {
      document.getElementById('passo-' + p).hidden = p !== id;
    });
    document.getElementById('passo-atual').textContent = 'Passo ' + PASSOS[id] + ' de ' + Object.keys(PASSOS).length;
    document.getElementById('confirmar-familia').hidden = id !== 'pecas';
    if (id === 'funcoes') desenharKv();
    if (id === 'design') desenharKvDesign();
    if (id === 'pecas' && !document.querySelector('#orientacoes [role=tab]')) iniciarPecas(null);
    if (id === 'pecas') reajustar(document.getElementById('palco'));
    if (id === 'formatos') montarPainel();
  }

  /* ---------------------------------------------------------------- falta N */
  function fecharFaltam() {
    document.getElementById('lista-faltam').hidden = true;
    document.getElementById('faltam').setAttribute('aria-expanded', 'false');
  }
  function montarFaltam(lista) {
    const botaoFaltam = document.getElementById('faltam');
    const ol = document.getElementById('itens-faltam');
    botaoFaltam.textContent = lista.length === 1 ? 'Falta 1' : 'Faltam ' + lista.length;
    botaoFaltam.classList.toggle('zero', !lista.length);
    limpar(ol);
    if (!lista.length) item(ol, 'Nada falta no que a tela mostra.', 'vazio');
    lista.forEach(function (f) {
      const li = el('li');
      li.appendChild(el('span', f.texto, 'texto-item'));
      if (f.detalhe) li.appendChild(el('span', f.detalhe, 'detalhe-item'));
      const ir = botao('Ir até aqui', 'ir');
      ir.addEventListener('click', function () {
        fecharFaltam();
        if (f.ir && f.ir.passo === 'pecas' && f.ir.formato) irParaFormato(f.ir.formato);
        else if (f.ir && f.ir.passo === 'funcoes' && f.ir.camada !== undefined) irParaCamada(f.ir.camada);
        else if (f.ir && f.ir.passo === 'design' && f.ir.chave) irParaDesign(f.ir.chave);
        else mostrarPasso((f.ir && f.ir.passo) || 'lido');
      });
      li.appendChild(ir);
      ol.appendChild(li);
    });
  }
  function ligarFaltam() {
    const botaoFaltam = document.getElementById('faltam');
    const caixa = document.getElementById('lista-faltam');
    botaoFaltam.addEventListener('click', function () {
      caixa.hidden = !caixa.hidden;
      botaoFaltam.setAttribute('aria-expanded', caixa.hidden ? 'false' : 'true');
      if (!caixa.hidden) { const p = caixa.querySelector('button'); if (p) p.focus(); }
    });
    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape' && !caixa.hidden) { fecharFaltam(); botaoFaltam.focus(); }
    });
  }

  /* ---------------------------------------------------------------- passo 1 */
  function lista(no, itens, vazio) {
    limpar(no);
    if (!itens.length) { no.appendChild(el('p', vazio, 'vazio-calmo')); return; }
    const ul = el('ul');
    itens.forEach(function (t) { item(ul, t[0], t[1]); });
    no.appendChild(ul);
  }
  function numero(valor, rotulo, aviso) {
    const d = el('div', null, 'numero-bloco' + (aviso ? ' aviso' : ''));
    d.appendChild(el('span', valor, 'numero'));
    d.appendChild(el('span', rotulo, 'rotulo-numero'));
    return d;
  }
  /* botao de ato: o nome do ato e os dados vao no proprio botao; sem a escrita, o botao fica desligado */
  function botaoAto(texto, ato, dados, classe) {
    const b = botao(texto, classe || 'botao');
    b.dataset.ato = ato;
    b.dataset.dados = JSON.stringify(dados);
    if (!escrita) b.disabled = true;
    return b;
  }
  function montarBloqueios(l) {
    const no = document.getElementById('lido-bloqueios');
    limpar(no);
    const itens = [];
    l.bloqueios.forEach(function (b) { itens.push([b.descricao, b.texto, []]); });
    l.camadas_bloqueadas.forEach(function (c) {
      itens.push(['Camada que não pôde ser lida', (c.motivos || []).join('; '), [c.nome]]);
    });
    (l.paradas || []).forEach(function (p) { itens.push([null, p.texto, p.camadas]); });
    if (!itens.length) { no.appendChild(el('p', 'Nenhum bloqueio.', 'vazio-calmo')); return; }
    const ul = el('ul', null, 'paradas');
    itens.forEach(function (t) {
      const li = el('li', null, 'parada');
      if (t[0]) li.appendChild(el('span', t[0], 'parada-titulo'));
      li.appendChild(el('span', t[1], 'parada-texto'));
      if (t[2] && t[2].length) li.appendChild(el('span', t[2].join(', '), 'parada-camadas'));
      ul.appendChild(li);
    });
    no.appendChild(ul);
  }
  function montarLinkados(lks) {
    const no = document.getElementById('lido-linkados');
    limpar(no);
    if (!lks.length) { no.appendChild(el('p', 'O PSD não tem arquivos linkados.', 'vazio-calmo')); return; }
    lks.forEach(function (x) {
      const art = el('article', null, 'decisao' + (x.confirmado ? ' feita' : ''));
      const topo = el('div', null, 'decisao-topo');
      topo.appendChild(el('span', x.nome || 'Linkado sem nome', 'decisao-nome'));
      topo.appendChild(el('span', x.confirmado ? 'Arquivo confirmado' : 'Escolha o arquivo', 'decisao-estado'));
      art.appendChild(topo);
      if (!x.candidatos.length) {
        art.appendChild(el('p', 'Nenhum arquivo enviado tem o nome deste linkado. Envie o arquivo da arte junto com o job.', 'decisao-nota aviso'));
      }
      const ul = el('ul', null, 'opcoes-lista');
      x.candidatos.forEach(function (c) {
        const li = el('li', null, 'opcao-linha');
        const info = el('span', null, 'opcao-info');
        info.appendChild(el('span', c.nome, 'opcao-nome'));
        info.appendChild(el('span', c.mesmo_tamanho ? 'mesmo tamanho do arquivo do PSD' : 'tamanho diferente do arquivo do PSD',
          c.mesmo_tamanho ? 'opcao-detalhe' : 'opcao-detalhe aviso'));
        li.appendChild(info);
        if (x.confirmado && x.arquivo === c.arquivo) li.appendChild(el('span', 'Em uso', 'opcao-em-uso'));
        else li.appendChild(botaoAto(x.confirmado ? 'Usar este' : 'Usar este arquivo', 'linkado',
          { unique_id: x.unique_id, arquivo: c.arquivo }));
        ul.appendChild(li);
      });
      art.appendChild(ul);
      no.appendChild(art);
    });
  }
  function montarSpecs(s) {
    const no = document.getElementById('lido-specs-pendentes');
    limpar(no);
    const lista = s.lista || [];
    if (!lista.length) return;
    no.appendChild(el('h3', lista.length === 1 ? '1 valor espera a sua confirmação' : lista.length + ' valores esperam a sua confirmação', 'subtitulo'));
    lista.forEach(function (v) {
      const art = el('article', null, 'decisao');
      const topo = el('div', null, 'decisao-topo');
      topo.appendChild(el('span', v.campo, 'decisao-nome'));
      topo.appendChild(el('span', v.onde, 'decisao-estado'));
      art.appendChild(topo);
      if (v.leituras.length) {
        art.appendChild(el('p', 'As folhas trazem valores diferentes. Escolha o que vale.', 'decisao-nota'));
        const ul = el('ul', null, 'opcoes-lista');
        v.leituras.forEach(function (lei) {
          const li = el('li', null, 'opcao-linha');
          const info = el('span', null, 'opcao-info');
          info.appendChild(el('span', lei.descricao, 'opcao-nome'));
          if (lei.trecho && lei.trecho !== lei.descricao) info.appendChild(el('span', lei.trecho, 'opcao-detalhe'));
          li.appendChild(info);
          li.appendChild(botaoAto('Usar este valor', 'spec_valor', { valor_id: v.valor_id, leitura: lei.indice }));
          ul.appendChild(li);
        });
        art.appendChild(ul);
      } else {
        const linha = el('div', null, 'opcao-linha');
        const info = el('span', null, 'opcao-info');
        info.appendChild(el('span', v.descricao, 'opcao-nome'));
        if (v.trecho && v.trecho !== v.descricao) info.appendChild(el('span', v.trecho, 'opcao-detalhe'));
        linha.appendChild(info);
        linha.appendChild(botaoAto('Confirmar valor', 'spec_valor', { valor_id: v.valor_id }));
        art.appendChild(linha);
      }
      no.appendChild(art);
    });
  }
  /* ---------------------------------------------------------------- passo 1: giro e prancheta (revisao do M7a) */
  function giroDe(f) {
    if (Object.prototype.hasOwnProperty.call(giroSemSentido, f.chave)) return { graus: giroSemSentido[f.chave], sentido: null };
    // o rascunho primeiro; sem ele, o giro que o briefing ja tem (o servidor manda os dois juntos em f.rotacao)
    return p1.rotacoes[f.chave] || f.rotacao || null;
  }
  function giroCompleto(g) { return !!g && (g.graus === 0 || g.graus === 180 || !!g.sentido); }
  function descreverGiro(g) {
    if (!giroCompleto(g)) return 'Giro não escolhido';
    if (g.graus === 0) return 'Sem giro';
    const sentido = g.sentido === 'horario' ? ', sentido horário' : (g.sentido === 'anti_horario' ? ', sentido anti-horário' : '');
    return 'Girado ' + g.graus + ' graus' + sentido;
  }
  /* uma escolha do passo 1 muda o layout de todas as familias, como o passo 2 (mudouP2) */
  function mudouP1() {
    p2Mudou = true;
    tirarConfirmacoes();
    mudouRascunho();
  }
  function escolherGiro(f, graus, sentido) {
    const quarto = graus === 90 || graus === 270;
    if (quarto && !sentido) {
      // o quarto de volta pede o sentido: ate a escolha, o giro fica so na tela e o formato segue sem giro gravado
      giroSemSentido[f.chave] = graus;
      if (p1.rotacoes[f.chave]) { delete p1.rotacoes[f.chave]; mudouP1(); }
    } else {
      delete giroSemSentido[f.chave];
      const novo = { graus: graus, sentido: quarto ? sentido : null };
      const antes = p1.rotacoes[f.chave];
      if (!(antes && antes.graus === novo.graus && antes.sentido === novo.sentido)) {
        p1.rotacoes[f.chave] = novo;
        mudouP1();
      }
    }
    montarFormatos(estado.lido.specs, f.chave + '|' + graus + '|' + (sentido || ''));
    atualizarSalvar();
  }
  function botaoGiro(texto, pressionado, chave, acao) {
    const b = botaoOpcao(texto, pressionado, acao);
    b.dataset.giro = chave;
    return b;
  }
  function montarFormatos(s, foco) {
    const no = document.getElementById('lido-formatos');
    limpar(no);
    if (!s.formatos.length) {
      const vazio = el('div', null, 'vazio-formatos');
      vazio.appendChild(el('p', 'As specs do job ainda não têm nenhum formato com medida em pixels.', 'vazio-titulo'));
      if (s.sem_formatos) vazio.appendChild(el('p', s.sem_formatos, 'nota'));
      no.appendChild(vazio);
      return;
    }
    s.formatos.forEach(function (f) {
      const g = giroDe(f);
      const art = el('article', null, 'decisao giro' + (giroCompleto(g) ? ' feita' : ''));
      const topo = el('div', null, 'decisao-topo');
      const nome = el('span', null, 'decisao-nome');
      nome.appendChild(el('span', f.id, 'giro-id'));
      nome.appendChild(el('span', dimensao(f.largura, f.altura), 'giro-medida'));
      topo.appendChild(nome);
      topo.appendChild(el('span', descreverGiro(g), 'decisao-estado'));
      art.appendChild(topo);
      art.appendChild(el('p', f.sem_folha ? 'Formato de teste, sem folha.' : (f.tem_spec ? 'Com spec confirmada.' :
        'Sem spec confirmada.'), 'decisao-nota giro-spec'));
      art.appendChild(el('p', f.giro_da_folha ? 'A folha diz: ' + f.giro_da_folha : 'A folha não fala de giro.', 'giro-folha'));
      const linha = el('div', null, 'opcoes-funcao giro-opcoes');
      linha.setAttribute('role', 'group');
      linha.setAttribute('aria-label', 'Giro de ' + f.id);
      GIROS.forEach(function (x) {
        linha.appendChild(botaoGiro(x[1], !!g && g.graus === x[0], f.chave + '|' + x[0] + '|', function () {
          escolherGiro(f, x[0], null);
        }));
      });
      art.appendChild(linha);
      if (g && (g.graus === 90 || g.graus === 270)) {
        const sent = el('div', null, 'opcoes-funcao giro-opcoes');
        sent.setAttribute('role', 'group');
        sent.setAttribute('aria-label', 'Sentido do giro de ' + f.id);
        sent.appendChild(el('span', 'Sentido', 'giro-rotulo'));
        SENTIDOS.forEach(function (x) {
          sent.appendChild(botaoGiro(x[1], g.sentido === x[0], f.chave + '|' + g.graus + '|' + x[0], function () {
            escolherGiro(f, g.graus, x[0]);
          }));
        });
        art.appendChild(sent);
        if (!g.sentido) art.appendChild(el('p', 'Escolha o sentido do giro, como o veículo pede.', 'decisao-nota aviso'));
      }
      no.appendChild(art);
    });
    if (foco) {
      const b = Array.from(no.querySelectorAll('button[data-giro]')).find(function (x) { return x.dataset.giro === foco; });
      if (b) b.focus();
    }
  }
  function montarQuadros(qs) {
    const bloco = document.getElementById('bloco-quadros');
    const no = document.getElementById('lido-quadros');
    limpar(no);
    bloco.hidden = !qs.length;
    const escolhido = p1.quadro || (qs.find(function (q) { return q.escolhido; }) || {}).id;
    qs.forEach(function (q) {
      const b = botaoOpcao('', escolhido === q.id, function () {
        if (p1.quadro !== q.id) {
          p1.quadro = q.id;
          mudouP1();
        }
        montarQuadros(estado.lido.quadros || []);
        const novo = no.querySelector('[data-quadro="' + q.id + '"]');
        if (novo) novo.focus();
        atualizarSalvar();
      }, 'quadro');
      b.dataset.quadro = q.id;
      const caixa = el('span', null, 'quadro-previa');
      const mini = el('span', null, 'mini-palco');
      caixaMini(mini, q.largura, q.altura, 168, 96);
      caixa.appendChild(mini);
      b.appendChild(caixa);
      const texto = el('span', null, 'quadro-texto');
      texto.appendChild(el('span', q.nome || 'Prancheta sem nome', 'quadro-nome'));
      texto.appendChild(el('span', dimensao(q.largura, q.altura) + (q.visivel ? '' : ', oculta no PSD'), 'quadro-medida'));
      b.appendChild(texto);
      no.appendChild(b);
      if (q.palco && q.palco.pecas && q.palco.pecas.length) desenharPalco(mini, q.palco, { miniatura: true });
      else mini.appendChild(el('span', 'sem prévia', 'quadro-sem-previa'));
    });
    if (qs.length && !escrita) no.appendChild(el('p', SO_PARA_VER, 'nota'));
  }

  /* M7c, S4: a frase do pedido de sugestoes, com o que o DA escreve destacado (a tela nunca chama o Claude) */
  function frasePedirSugestoes(classe) {
    const p = el('p', FRASE_PEDIR_SUGESTOES.slice(0, FRASE_PEDIR_SUGESTOES.length - PEDIDO_SUGESTOES.length), 'pedir-sugestoes ' + classe);
    p.appendChild(el('span', PEDIDO_SUGESTOES, 'pedido'));
    return p;
  }
  /* revisao do S4: a frase do passo 1 aparece com o modo a ou b gravado E valendo. O modo que vale (a escolha do DA
     limitada pelo teto do job e da linha de comando; a escolha de teste vale c) vem da rota das sugestoes, a mesma
     conta da importacao: com o teto em c, o pedido seria recusado, e a frase nao aparece */
  let modoNoPasso1 = null;
  function atualizarPedidoDoPasso1() {
    const lugar = document.getElementById('modo-pedido-lugar');
    if (!lugar) return;
    const gravado = !!modoNoPasso1 && (modoNoPasso1.escolhido === 'a' || modoNoPasso1.escolhido === 'b');
    const vale = sug.modo === 'a' || sug.modo === 'b';
    if (gravado && vale) {
      if (!lugar.firstChild) lugar.appendChild(frasePedirSugestoes('modo-pedido'));
    } else {
      limpar(lugar);
    }
  }
  /* o modo de dados (decisao 170): nada marcado ate o DA escolher; so os modos dentro do teto aparecem */
  function montarModo(m) {
    const md = document.getElementById('lido-modo');
    limpar(md);
    md.appendChild(el('p', m.escolhido ? 'O modo vale para o job inteiro. Você pode trocar quando quiser.' :
      'Escolha o que pode ir ao Claude neste job. Até a escolha, nada do conteúdo do arquivo vai a ele.', 'nota modo-nota'));
    const grade = el('div', null, 'modos');
    grade.setAttribute('role', 'group');
    grade.setAttribute('aria-label', 'Modo de dados');
    m.opcoes.forEach(function (v) {
      const sim = m.escolhido === v;
      const b = botaoAto('', 'modo_dados', { modo: v }, 'modo');
      b.dataset.modo = v;
      b.setAttribute('aria-pressed', sim ? 'true' : 'false');
      b.appendChild(el('span', null, 'modo-marca'));
      const corpo = el('span', null, 'modo-corpo');
      corpo.appendChild(el('span', (MODOS[v] || ['Modo'])[0], 'modo-nome'));
      corpo.appendChild(el('span', (MODOS[v] || ['', ''])[1], 'modo-texto'));
      b.appendChild(corpo);
      grade.appendChild(b);
    });
    md.appendChild(grade);
    modoNoPasso1 = m;
    const lugar = el('div', null, 'modo-pedido-lugar');
    lugar.id = 'modo-pedido-lugar';
    md.appendChild(lugar);
    atualizarPedidoDoPasso1();
    if (m.teto && m.opcoes.length < 3) {
      md.appendChild(el('p', 'A agência limita este job aos modos mostrados aqui.', 'nota modo-nota'));
    }
    if (!escrita) md.appendChild(el('p', SO_PARA_VER, 'nota modo-nota'));
  }
  /* M7c, M3: a marca do job (decisao 190, Q5). As marcas da biblioteca da agencia, "Sem marca" e a "Marca nova",
     nenhuma marcada ate o clique do DA; a escolha e opcional e nunca entra no que falta. Sem biblioteca que sirva, so
     "Sem marca", com a nota de onde configurar. O nome da marca e dado do DA: so por textContent */
  let marcaNova = '';
  let marcaNovaRecusada = null;
  const MARCA_NOVA_MAX = 120;
  /* revisao do M3: o nome na forma que o motor grava (NFC, um espaco so entre as palavras) e a chave que diz se duas
     marcas sao a mesma, perto do casefold do motor (desdobra.marca.job.chave). O motor confere de novo no pedido */
  function formaDaMarca(s) { return String(s).split(/[^\S﻿]+/).filter(Boolean).join(' ').normalize('NFC'); }
  function chaveDaMarca(s) { return formaDaMarca(s).toUpperCase().toLowerCase().normalize('NFC'); }
  function extensaoDeFonte(extensoes) {
    if (!extensoes || !extensoes.length) return null;
    const partes = extensoes.map(function (x) { return String(x).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); });
    return new RegExp('\\.(?:' + partes.join('|') + ')(?![A-Za-z0-9_-])', 'i');
  }
  function linhaMarca(nome, texto, dados, sim) {
    const b = botaoAto('', 'marca', dados, 'modo marca-linha');
    b.setAttribute('aria-pressed', sim ? 'true' : 'false');
    b.appendChild(el('span', null, 'modo-marca'));
    const corpo = el('span', null, 'modo-corpo');
    corpo.appendChild(el('span', nome, 'modo-nome'));
    if (texto) corpo.appendChild(el('span', texto, 'modo-texto'));
    b.appendChild(corpo);
    return b;
  }
  function montarMarca(m) {
    const no = document.getElementById('lido-marca');
    limpar(no);
    if (!m) return;
    const e = m.escolhida;
    const usavel = !!(m.biblioteca && m.biblioteca.usavel);
    no.appendChild(el('p', e ? 'A marca vale para o job inteiro. Você pode trocar quando quiser.' :
      'Escolha de que marca é este job, se quiser. O padrão que a marca tiver aparece como sugestão, e nada muda sem o seu clique.',
      'nota modo-nota'));
    if (e && e.escolha === 'marca' && !e.nome) {
      no.appendChild(el('p', 'Este job tem uma marca escolhida que não aparece na biblioteca desta janela.', 'nota marca-escolhida-fora'));
    }
    if (usavel && m.marcas.length) {
      const lista = el('div', null, 'modos marcas');
      lista.setAttribute('role', 'group');
      lista.setAttribute('aria-label', 'Marcas da agência');
      m.marcas.forEach(function (x) {
        lista.appendChild(linhaMarca(x.nome, '', { escolha: 'marca', id: x.id }, !!e && e.escolha === 'marca' && e.id === x.id));
      });
      no.appendChild(lista);
    } else if (usavel) {
      no.appendChild(el('p', 'A biblioteca da agência ainda não tem marca. Crie a primeira abaixo, ou siga sem marca.', 'vazio-calmo modo-nota'));
    } else {
      no.appendChild(el('p', (m.biblioteca && m.biblioteca.o_que_fazer) || 'A biblioteca da agência não está configurada. O job segue sem marca.', 'nota modo-nota'));
    }
    const sem = el('div', null, 'modos marca-sem');
    sem.appendChild(linhaMarca('Sem marca', 'O job segue sem padrão de marca.', { escolha: 'sem_marca' }, !!e && e.escolha === 'sem_marca'));
    no.appendChild(sem);
    if (usavel && m.pode_criar) no.appendChild(campoMarcaNova(m.marcas, m.extensoes_fonte));
    if (!escrita) no.appendChild(el('p', SO_PARA_VER, 'nota modo-nota'));
  }
  function campoMarcaNova(marcas, extensoes) {
    const deFonte = extensaoDeFonte(extensoes);
    const chaves = marcas.map(function (x) { return chaveDaMarca(x.nome); });
    const caixa = el('div', null, 'marca-nova');
    const rotulo = el('label', 'Marca nova');
    rotulo.htmlFor = 'marca-nova-nome';
    const linha = el('div', null, 'marca-nova-linha');
    const campo = el('input');
    campo.id = 'marca-nova-nome';
    campo.type = 'text';
    campo.autocomplete = 'off';
    campo.spellcheck = false;
    campo.maxLength = MARCA_NOVA_MAX;
    campo.value = marcaNova;
    campo.disabled = !escrita;
    campo.setAttribute('aria-describedby', 'marca-nova-ajuda');
    const criar = botao('Criar e usar', 'botao');
    criar.id = 'marca-nova-criar';
    const ajuda = el('p', 'Digite o nome como a agência chama a marca. Ela entra na biblioteca, ainda sem padrão guardado.', 'nota ajuda');
    ajuda.id = 'marca-nova-ajuda';
    const erro = el('p', '', 'erro-campo');
    erro.id = 'marca-nova-erro';
    erro.hidden = true;
    const conferir = function () {
      marcaNova = campo.value;
      const nome = formaDaMarca(campo.value);
      const chave = chaveDaMarca(nome);
      const repetida = !!nome && chaves.indexOf(chave) >= 0;
      const ruim = /[\\/]/.test(nome);
      const fonte = !!deFonte && deFonte.test(nome);
      if (marcaNovaRecusada !== null && marcaNovaRecusada !== chave) marcaNovaRecusada = null;
      const recusada = !!nome && marcaNovaRecusada === chave;
      const texto = repetida ? 'Essa marca já está na lista acima. Escolha ela lá.' :
        ruim ? 'O nome da marca não leva barra.' :
        fonte ? 'O nome da marca não leva extensão de arquivo de fonte, como .otf ou .ttf.' :
        recusada ? 'O desdobra não aceitou esse nome. Ele pode repetir de outro jeito uma marca da lista acima ou parecer dado de fonte. Mude o nome para criar a marca.' : '';
      erro.hidden = !texto;
      erro.textContent = texto;
      campo.setAttribute('aria-invalid', texto ? 'true' : 'false');
      criar.disabled = !escrita || !nome || !!texto;
      return !criar.disabled;
    };
    campo.addEventListener('input', conferir);
    campo.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter' && conferir()) { ev.preventDefault(); criar.click(); }
    });
    criar.addEventListener('click', function () {
      if (!conferir()) return;
      const nome = formaDaMarca(campo.value);
      pedirAto('marca', { escolha: 'nova', nome: nome }, function () {
        // o motor recusou o nome antes da janela: o motivo fica no campo, e o botao desliga ate o DA mudar o nome
        marcaNovaRecusada = chaveDaMarca(nome);
        conferir();
        campo.focus();
      });
    });
    linha.appendChild(campo);
    linha.appendChild(criar);
    caixa.appendChild(rotulo);
    caixa.appendChild(linha);
    caixa.appendChild(erro);
    caixa.appendChild(ajuda);
    conferir();
    return caixa;
  }
  depoisDoAto.marca = function (d) {
    if (d && d.escolha === 'nova') {
      marcaNova = '';
      marcaNovaRecusada = null;
      const campo = document.getElementById('marca-nova-nome');
      if (campo) campo.value = '';
      montarMarca(estado.lido && estado.lido.marca);
    }
  };
  function montarLido(l) {
    montarBloqueios(l);
    montarLinkados(l.linkados);
    const s = l.specs;
    const sp = document.getElementById('lido-specs');
    limpar(sp);
    if (!s.tem_rascunho) sp.appendChild(el('p', 'O job não tem folha de spec.', 'vazio-calmo'));
    else {
      const n = el('div', null, 'numeros');
      n.appendChild(numero(s.confirmados, 'confirmados'));
      n.appendChild(numero(s.rascunhos, 'em rascunho'));
      n.appendChild(numero(s.divergentes, 'divergentes', s.divergentes > 0));
      n.appendChild(numero(s.registros, 'só registro'));
      sp.appendChild(n);
    }
    montarSpecs(s);
    montarFormatos(s);
    montarQuadros(l.quadros || []);
    montarModo(l.modo_dados);
    montarMarca(l.marca);
    const fo = document.getElementById('fontes');
    limpar(fo);
    if (!l.fontes.length) fo.appendChild(el('p', 'O job não tem fonte enviada.', 'vazio-calmo'));
    l.fontes_que_faltam.forEach(function (f) {
      fo.appendChild(el('p', 'Falta ou não confere: ' + f.fonte_ps + ', ' + plural(f.camadas, 'camada', 'camadas'), 'fonte-falta'));
    });
    l.fontes.forEach(function (f) {
      const c = el('article', null, 'especime');
      c.appendChild(el('p', [f.familia, f.estilo].filter(Boolean).join(' ') || f.nome_ps || 'Fonte enviada', 'nome-fonte'));
      if (f.nome_ps) c.appendChild(el('p', f.nome_ps, 'rotulo-fonte'));
      const p = el('p', AMOSTRA, 'amostra');
      p.id = 'amostra-' + f.id;
      p.style.fontFamily = '"' + f.familia_css + '"';
      c.appendChild(p);
      fo.appendChild(c);
    });
    return Promise.all(l.fontes.map(function (f) {
      return document.fonts.load('22px "' + f.familia_css + '"').catch(function () { return null; });
    }));
  }

  /* ---------------------------------------------------------------- passo 2: funcoes (fatia 3) */
  const p2idx = { nos: [], por: new Map(), filhos: new Map(), opcoes: null, atual: null, design: null };
  function iniciarPasso2(f) {
    const d = f.decisoes || { nos: [], opcoes: { funcoes: [], regras: [], ancora_x: [], ancora_y: [], cobertas: [] } };
    p2idx.nos = d.nos;
    p2idx.opcoes = d.opcoes;
    d.nos.forEach(function (n) {
      p2idx.por.set(n.camada, n);
      if (!p2idx.filhos.has(n.pai)) p2idx.filhos.set(n.pai, []);
      p2idx.filhos.get(n.pai).push(n);
    });
    montarArvore();
    detalhar(null);
    montarDesign();
  }

  /* ---------------------------------------------------------------- sugestao do Claude (M7c, S4; decisao 190, Q4)
     a pagina le a rota leve na partida, depois de cada ato e a cada SUGESTOES_MS com o passo 2 aberto. A primeira
     leitura aparece direto; quando o sha256 muda depois, a faixa "Chegaram as sugestoes" espera o "Mostrar", e nada do
     que o DA escolheu muda. Sem sugestao no modo de agora (modo c, outro modo, outro KV), ela some na hora */
  function sugestaoDe(lid) { return sug.por.get(Number(lid)) || null; }
  function redesenharSugestoes() {
    atualizarArvore();
    if (p2idx.atual !== null) detalhar(p2idx.por.get(p2idx.atual));
    else detalhar(null);
  }
  function aplicarSugestoes(r) {
    sug.modo = r.modo || null;
    sug.sha = r.sha256 || null;
    sug.por = new Map();
    (r.sugestoes || []).forEach(function (x) { sug.por.set(x.layer_id, x); });
    sug.chegou = null;
    document.getElementById('sugestoes-chegaram').hidden = true;
    raiz.dataset.sugestoes = sug.sha ? 'mostradas' : 'nenhuma';
    redesenharSugestoes();
    atualizarPedidoDoPasso1();
  }
  function lerSugestoes() {
    if (sug.consultando) return Promise.resolve(null);
    sug.consultando = true;
    return pedir('/api/sugestoes').then(function (r) {
      sug.consultando = false;
      if (!r || typeof r !== 'object') return;
      const sha = r.sha256 || null;
      if (!sug.lida || !sha) {
        // a primeira leitura, ou nenhuma sugestao no modo de agora: a tela segue direto, sem esperar clique
        sug.lida = true;
        if (!sha || sha !== sug.sha || r.modo !== sug.modo) aplicarSugestoes(r);
        return;
      }
      if (sha === sug.sha) {
        if (sug.chegou) { sug.chegou = null; document.getElementById('sugestoes-chegaram').hidden = true; }
        return;
      }
      if (sug.chegou && sug.chegou.sha256 === sha) return;
      sug.chegou = r;
      raiz.dataset.sugestoes = 'chegaram';
      document.getElementById('sugestoes-chegaram').hidden = false;
      // revisao do S4: com a faixa a vista, o painel sem camada aberta deixa de pedir as sugestoes que ja chegaram
      if (p2idx.atual === null) detalhar(null);
    }).catch(function () { sug.consultando = false; });
  }
  function ligarSugestoes() {
    document.getElementById('mostrar-sugestoes').addEventListener('click', function () {
      if (sug.chegou) aplicarSugestoes(sug.chegou);
    });
    lerSugestoes();
    setInterval(function () {
      if (!document.getElementById('passo-funcoes').hidden && !document.hidden) lerSugestoes();
    }, SUGESTOES_MS);
  }
  function quadroDaSugestao(n) {
    const s = sugestaoDe(n.camada);
    if (!s) return null;
    const lid = String(n.camada);
    const own = p2.funcoes[lid] || null;
    const box = el('section', null, 'sugestao');
    box.dataset.sugestao = lid;
    box.setAttribute('aria-label', 'Sugestão do Claude');
    const topo = el('p', null, 'sugestao-fonte');
    topo.appendChild(el('span', 'Sugestão do Claude, modo (' + sug.modo + ')', 'sugestao-selo'));
    box.appendChild(topo);
    [[s.funcao, 'Sugestão'], [s.alternativa, 'Alternativa']].forEach(function (par, i) {
      const linha = el('div', null, 'sugestao-linha' + (i ? ' alternativa' : ''));
      const info = el('span', null, 'sugestao-info');
      info.appendChild(el('span', par[1], 'sugestao-rotulo'));
      info.appendChild(el('span', maiuscula(nomeFuncao(par[0])), 'sugestao-funcao'));
      linha.appendChild(info);
      if (own && own.funcao === par[0]) {
        linha.appendChild(el('span', 'Em uso', 'sugestao-em-uso'));
      } else {
        const b = botao('Usar', 'botao usar');
        b.dataset.usar = par[0];
        b.setAttribute('aria-label', 'Usar ' + nomeFuncao(par[0]));
        if (!escrita) b.disabled = true;
        b.addEventListener('click', function () { escolherFuncao(n, par[0]); });
        linha.appendChild(b);
      }
      box.appendChild(linha);
    });
    box.appendChild(el('p', 'Nada fica gravado até você clicar em Usar ou escolher outra função abaixo.', 'nota sugestao-nota'));
    return box;
  }
  function geometria(f) {
    const o = (p2idx.opcoes.funcoes || []).find(function (x) { return x.id === f; });
    return o ? o.geometria : true;
  }
  function maiuscula(t) { return t ? t.charAt(0).toUpperCase() + t.slice(1) : t; }
  /* a heranca do motor (briefing/modelo.py resolver): a camada coberta no KV nao herda da pasta; as outras pegam a
     escolha mais proxima, da propria camada para cima */
  function resolver(n) {
    if (!n) return null;
    const lid = String(n.camada);
    if (n.folha && n.coberta && !p2.funcoes[lid]) {
      const d = p2.cobertas[lid], sug = n.coberta.sugestao;
      if (d && INVERSA[sug]) return { funcao: d === 'aceita' ? sug : INVERSA[sug], por: 'decisao_10', raiz: n.camada };
      return null;
    }
    let x = n;
    while (x) {
      const e = p2.funcoes[String(x.camada)];
      if (e) return { funcao: e.funcao, por: x === n ? 'camada' : 'grupo', raiz: x.camada };
      x = x.pai === null ? null : p2idx.por.get(x.pai);
    }
    return null;
  }
  function chaveDesign(r) { return r.funcao === 'indeterminado' ? 'c' + r.raiz : 'f' + r.funcao; }
  function designDe(chave) {
    return (chave.charAt(0) === 'c' ? p2.design_camadas[chave.slice(1)] : p2.design[chave.slice(1)]) || null;
  }
  /* o que o Design system pede: uma entrada por funcao com geometria e uma por elemento indeterminado, na ordem do
     painel (desdobra/tela/funcoes.py pendencias) */
  function vistasDoDesign() {
    const vistas = [], por = new Map();
    p2idx.nos.forEach(function (n) {
      if (!n.folha) return;
      const r = resolver(n);
      if (!r || !geometria(r.funcao)) return;
      const k = chaveDesign(r);
      if (!por.has(k)) { por.set(k, { chave: k, funcao: r.funcao, raiz: r.raiz, camadas: [] }); vistas.push(por.get(k)); }
      por.get(k).camadas.push(n.camada);
    });
    return vistas;
  }
  function nomeDaVista(v) {
    if (v.funcao !== 'indeterminado') return maiuscula(nomeFuncao(v.funcao));
    const n = p2idx.por.get(v.raiz);
    return 'Outra função: ' + (n ? n.nome : '');
  }
  function pendenciasP2() {
    const out = [];
    p2idx.nos.forEach(function (n) {
      if (!n.folha || resolver(n)) return;
      const coberta = !!n.coberta && !p2.funcoes[String(n.camada)];
      out.push({ texto: coberta ? 'Decida a camada que fica coberta no KV.' : 'Escolha a função da camada.',
        detalhe: n.nome, ir: { passo: 'funcoes', camada: n.camada }, tipo: coberta ? 'coberta' : 'funcao' });
    });
    vistasDoDesign().forEach(function (v) {
      const d = designDe(v.chave) || {};
      const nome = nomeDaVista(v);
      if (!d.regra) out.push({ texto: 'Escolha a regra de escala.', detalhe: nome, ir: { passo: 'design', chave: v.chave }, tipo: 'regra' });
      if (!d.x || !d.y) out.push({ texto: 'Escolha a âncora.', detalhe: nome, ir: { passo: 'design', chave: v.chave }, tipo: 'ancora' });
      // M7c, M4: o valor do padrao da marca de antes da versao nova: o servidor recusa salvar ate o DA decidir
      if (padraoVencido(v)) out.push({ texto: padraoDe(v) ? 'Use o padrão da marca de novo ou clique de novo no valor que quer manter.' : 'Clique de novo no tamanho e na âncora que quer manter.', detalhe: nome, ir: { passo: 'design', chave: v.chave }, tipo: 'padrao' });
    });
    return out;
  }
  function atualizarFaltam() {
    montarFaltam((estado.faltam || []).concat(p2idx.opcoes ? pendenciasP2() : [], escrita ? pendenciasDasQuebras() : []));
    atualizarSalvar();
  }
  function idsDasFamilias() {
    const ids = [];
    (estado.orientacoes || []).forEach(function (o) { o.grupos.forEach(function (g) { ids.push(g.id); }); });
    return ids;
  }
  function dicaDasFamilias(n) {
    return n === 1 ? 'Falta confirmar 1 família para salvar.' : 'Falta confirmar ' + n + ' famílias para salvar.';
  }
  /* o botao Salvar e seguir e a linha ao lado dele: o que ainda falta, ou o briefing salvo e o proximo passo */
  function atualizarSalvar() {
    const b = document.getElementById('salvar-seguir');
    const dica = document.getElementById('dica-acoes');
    const aviso = document.getElementById('salvo');
    aviso.hidden = !salvoNaTela;
    aviso.textContent = salvoNaTela ? AVISO_SALVO : '';
    dica.classList.remove('pronta');
    if (!escrita || !estado) { b.disabled = true; dica.textContent = DICA_SO_VER; return; }
    b.dataset.ato = 'salvar';
    b.dataset.dados = '{}';
    if (salvoNaTela) { b.disabled = true; b.textContent = SALVO; dica.textContent = ''; return; }
    b.textContent = SALVAR;
    const semConfirmar = idsDasFamilias().filter(function (id) {
      const f = rascunho.familias[id];
      return !(f && f.confirmada);
    }).length;
    const semModo = !(estado.lido && estado.lido.modo_dados && estado.lido.modo_dados.escolhido);
    const p2falta = p2idx.opcoes ? pendenciasP2().length : 0;
    const lido = estado.lido || { specs: { formatos: [] }, quadros: [] };
    const semFormatos = !lido.specs.formatos.length;
    const semQuadro = (lido.quadros || []).length > 0 && !p1.quadro && !lido.quadros.some(function (q) { return q.escolhido; });
    const semGiro = lido.specs.formatos.some(function (f) { return !giroCompleto(giroDe(f)); });
    /* o formato da folha com duas medidas, sem a escolha do DA: o servidor recusa salvar (formato_sem_medida) */
    const semMedida = (lido.specs.sem_medida || []).length > 0;
    if (semFormatos) dica.textContent = DICA_SEM_FORMATOS;
    else if (semMedida) dica.textContent = DICA_MEDIDA;
    else if (semModo) dica.textContent = DICA_MODO;
    else if (semQuadro) dica.textContent = DICA_QUADRO;
    else if (semGiro) dica.textContent = DICA_GIRO;
    else if (p2falta) dica.textContent = DICA_P2;
    else if (semConfirmar) dica.textContent = dicaDasFamilias(semConfirmar);
    else { dica.textContent = DICA_PRONTA; dica.classList.add('pronta'); }
    b.disabled = !!(semConfirmar || p2falta || semModo || semFormatos || semQuadro || semGiro || semMedida);
  }
  /* o passo 2 ou o Design system mudou: as familias confirmadas voltam a pedir confirmacao (o servidor faz o mesmo,
     desdobra.tela.rascunho.gravar), e o passo 3, montado com o passo 2 de quando a tela abriu (desdobra.tela.estado),
     avisa que ainda mostra o de antes */
  function tirarConfirmacoes() {
    document.getElementById('aviso-passo-2').hidden = false;
    Object.keys(rascunho.familias).forEach(function (g) {
      const f = rascunho.familias[g];
      if (f && f.confirmada) { f.confirmada = false; delete f.confirmacao; }
    });
    if (typeof atualizarBotaoFamilia === 'function' && vista.familia) atualizarBotaoFamilia();
  }
  function mudouP2() {
    p2Mudou = true;
    tirarConfirmacoes();
    mudouRascunho();
    atualizarArvore();
    atualizarFaltam();
    if (p2idx.atual !== null) detalhar(p2idx.por.get(p2idx.atual));
    montarDesign();
  }
  function descricaoDoNo(n) {
    if (!n.folha) {
      const own = p2.funcoes[String(n.camada)];
      if (own) return maiuscula(nomeFuncao(own.funcao)) + ', passa para dentro';
      const herdada = n.pai === null ? null : resolver(p2idx.por.get(n.pai));
      return herdada ? maiuscula(nomeFuncao(herdada.funcao)) + ', da pasta de cima' : 'Sem função';
    }
    const r = resolver(n);
    if (r) {
      if (r.por === 'camada') return maiuscula(nomeFuncao(r.funcao));
      if (r.por === 'decisao_10') return maiuscula(nomeFuncao(r.funcao)) + ', camada coberta';
      const raiz = p2idx.por.get(r.raiz);
      return maiuscula(nomeFuncao(r.funcao)) + ', da pasta ' + (raiz ? raiz.nome : '');
    }
    return n.coberta && !p2.funcoes[String(n.camada)] ? 'Coberta no KV, espera a sua decisão' : 'Sem função';
  }
  function falta(n) { return n.folha && !resolver(n); }
  function montarArvore() {
    const nav = document.getElementById('arvore');
    limpar(nav);
    if (!p2idx.nos.length) { nav.appendChild(el('p', 'O PSD não tem camadas para desdobrar.', 'vazio-calmo')); return; }
    function ramo(pai) {
      const ul = el('ul');
      (p2idx.filhos.get(pai) || []).forEach(function (n) {
        const li = el('li', null, n.folha ? 'camada' : 'pasta');
        const b = botao();
        b.dataset.camada = String(n.camada);
        b.appendChild(el('span', n.nome || 'Camada sem nome', 'nome'));
        b.appendChild(el('span', '', 'funcao'));
        const marcaSug = el('span', '', 'sugestao-arvore');
        marcaSug.hidden = true;
        b.appendChild(marcaSug);
        b.addEventListener('click', function () { escolherNo(n.camada); });
        li.appendChild(b);
        if (p2idx.filhos.has(n.camada)) li.appendChild(ramo(n.camada));
        ul.appendChild(li);
      });
      return ul;
    }
    nav.appendChild(ramo(null));
    /* setas sobem e descem na lista, como no painel de camadas */
    nav.addEventListener('keydown', function (ev) {
      if (ev.key !== 'ArrowDown' && ev.key !== 'ArrowUp') return;
      const bs = Array.from(nav.querySelectorAll('button[data-camada]'));
      const i = bs.indexOf(document.activeElement);
      if (i < 0) return;
      ev.preventDefault();
      const j = Math.max(0, Math.min(bs.length - 1, i + (ev.key === 'ArrowDown' ? 1 : -1)));
      bs[j].focus();
      bs[j].click();
    });
    atualizarArvore();
  }
  function atualizarArvore() {
    document.querySelectorAll('#arvore button[data-camada]').forEach(function (b) {
      const n = p2idx.por.get(Number(b.dataset.camada));
      b.querySelector('.funcao').textContent = descricaoDoNo(n);
      b.classList.toggle('falta', falta(n));
      b.classList.toggle('propria', !!p2.funcoes[b.dataset.camada]);
      // M7c, S4: a sugestao do Claude ao lado, so enquanto o DA nao escolheu a funcao desta camada ou pasta
      const s = sugestaoDe(b.dataset.camada);
      const marca = b.querySelector('.sugestao-arvore');
      const mostrar = !!s && !p2.funcoes[b.dataset.camada];
      marca.hidden = !mostrar;
      marca.textContent = mostrar ? 'Sugestão: ' + nomeFuncao(s.funcao) : '';
    });
  }
  function escolherNo(lid) {
    p2idx.atual = lid;
    document.querySelectorAll('#arvore button[aria-current]').forEach(function (x) { x.removeAttribute('aria-current'); });
    const b = document.querySelector('#arvore button[data-camada="' + lid + '"]');
    if (b) b.setAttribute('aria-current', 'true');
    detalhar(p2idx.por.get(lid));
  }
  function irParaCamada(lid) {
    mostrarPasso('funcoes');
    escolherNo(lid);
    const b = document.querySelector('#arvore button[data-camada="' + lid + '"]');
    if (b) { b.scrollIntoView({ block: 'nearest' }); b.focus(); }
  }
  function camadasDentro(n) {
    if (n.folha) return [n.camada];
    let out = [];
    (p2idx.filhos.get(n.camada) || []).forEach(function (f) { out = out.concat(camadasDentro(f)); });
    return out;
  }
  function escolherFuncao(n, f) {
    const lid = String(n.camada);
    if (f === 'indeterminado') {
      const obs = (p2obs[lid] !== undefined ? p2obs[lid] : ((p2.funcoes[lid] || {}).observacao || '')).trim();
      if (!obs) { // sem observacao, a escolha fica so na tela (o motor recusa o rascunho sem ela)
        p2obs[lid] = '';
        delete p2.funcoes[lid];
        mudouP2();
        const t = document.getElementById('observacao');
        if (t) t.focus();
        return;
      }
      p2.funcoes[lid] = { funcao: f, observacao: obs };
    } else {
      delete p2obs[lid];
      p2.funcoes[lid] = { funcao: f, observacao: null };
    }
    mudouP2();
  }
  function botaoOpcao(texto, pressionado, acao, classe) {
    const b = botao(texto, classe || 'opcao');
    b.setAttribute('aria-pressed', pressionado ? 'true' : 'false');
    if (!escrita) b.disabled = true;
    b.addEventListener('click', acao);
    return b;
  }
  function chaveDoControle(x) {
    return x.id || x.dataset.funcao || (x.dataset.usar ? 'usar:' + x.dataset.usar : '') || x.textContent;
  }
  function detalhar(n) {
    const d = document.getElementById('detalhe');
    const foco = document.activeElement && d.contains(document.activeElement) ? document.activeElement : null;
    const chaveFoco = foco ? chaveDoControle(foco) : null;
    limpar(d);
    marcarNoKv('palco-kv', n ? camadasDentro(n) : [], null);
    if (!n) {
      d.appendChild(el('p', 'Passo 2', 'sobretitulo'));
      d.appendChild(el('h2', 'Funções da peça'));
      d.appendChild(el('p', 'Escolha uma pasta ou uma camada à esquerda. A função dada a uma pasta passa para as ' +
        'camadas de dentro, e você pode trocar uma camada depois.', 'nota'));
      // M7c, S4: com o modo a ou b, quantas tem sugestao, ou a frase para pedir ao Claude
      if (sug.modo === 'a' || sug.modo === 'b') {
        if (sug.por.size) {
          d.appendChild(el('p', plural(sug.por.size, 'pasta ou camada tem', 'pastas ou camadas têm') +
            ' sugestão do Claude, marcada na lista à esquerda. Nada muda sem o seu clique.', 'nota sugestao-resumo'));
        } else if (escrita && !sug.chegou) {
          // com sugestoes chegadas a espera do "Mostrar", a faixa ja diz o que fazer (revisao do S4)
          d.appendChild(frasePedirSugestoes('passo-pedido'));
        }
      }
      if (!escrita) d.appendChild(el('p', SO_PARA_VER, 'nota'));
      return;
    }
    const lid = String(n.camada);
    const own = p2.funcoes[lid] || null;
    d.appendChild(el('p', n.folha ? maiuscula(nomeTipo(n.tipo)) : 'Pasta de camadas, ' +
      plural(camadasDentro(n).length, 'camada dentro', 'camadas dentro'), 'sobretitulo'));
    d.appendChild(el('h2', n.nome || 'Camada sem nome'));
    if (n.folha && n.coberta && !own) {
      const box = el('section', null, 'coberta');
      box.appendChild(el('h3', 'Camada coberta no KV', 'subtitulo'));
      const sug = n.coberta.sugestao;
      if (INVERSA[sug]) {
        box.appendChild(el('p', 'Ela fica escondida por outras camadas. A sugestão do desdobra é ' + nomeFuncao(sug) +
          ', e nada fica gravado até você decidir.', 'nota'));
        const linha = el('div', null, 'opcoes-coberta');
        linha.setAttribute('role', 'group');
        linha.setAttribute('aria-label', 'Decisão da camada coberta');
        const a = botaoOpcao('Usar ' + nomeFuncao(sug), p2.cobertas[lid] === 'aceita', function () {
          p2.cobertas[lid] = 'aceita'; mudouP2();
        });
        a.dataset.coberta = 'aceita';
        const i = botaoOpcao('Usar ' + nomeFuncao(INVERSA[sug]), p2.cobertas[lid] === 'inverte', function () {
          p2.cobertas[lid] = 'inverte'; mudouP2();
        });
        i.dataset.coberta = 'inverte';
        linha.appendChild(a);
        linha.appendChild(i);
        box.appendChild(linha);
        box.appendChild(el('p', 'Ou dê outra função abaixo.', 'nota'));
      } else {
        box.appendChild(el('p', 'Ela fica escondida por outras camadas. Dê a função dela abaixo.', 'nota'));
      }
      d.appendChild(box);
    }
    const herdada = n.pai === null ? null : resolver(p2idx.por.get(n.pai));
    const herda = herdada && !(n.folha && n.coberta);
    const estadoTxt = own ? (n.folha ? 'Função escolhida para esta camada.' : 'Esta função passa para as camadas de dentro.') :
      (herda ? 'Herdada da pasta: ' + nomeFuncao(herdada.funcao) + '. Escolha abaixo para trocar só aqui.' :
        'Sem função ainda.');
    d.appendChild(el('p', estadoTxt, 'estado-funcao'));
    const quadroSug = quadroDaSugestao(n);
    if (quadroSug) d.appendChild(quadroSug);
    const escolhida = p2obs[lid] !== undefined ? 'indeterminado' : (own ? own.funcao : null);
    CLASSES_FUNCAO.forEach(function (c) {
      const fs = (p2idx.opcoes.funcoes || []).filter(function (f) { return f.classe === c[0]; });
      if (!fs.length) return;
      const sec = el('div', null, 'classe-funcao');
      sec.appendChild(el('h3', c[1], 'subtitulo'));
      const grade = el('div', null, 'opcoes-funcao');
      grade.setAttribute('role', 'group');
      grade.setAttribute('aria-label', c[1]);
      fs.forEach(function (f) {
        const b = botaoOpcao(maiuscula(nomeFuncao(f.id)), escolhida === f.id, function () { escolherFuncao(n, f.id); });
        b.dataset.funcao = f.id;
        grade.appendChild(b);
      });
      sec.appendChild(grade);
      d.appendChild(sec);
    });
    if (escolhida === 'indeterminado') {
      const campo = el('div', null, 'campo');
      const rotulo = el('label', 'O que esta camada faz na peça');
      rotulo.htmlFor = 'observacao';
      const t = document.createElement('textarea');
      t.id = 'observacao';
      t.rows = 3;
      t.maxLength = 2000;
      t.value = p2obs[lid] !== undefined ? p2obs[lid] : ((own && own.observacao) || '');
      if (!escrita) t.disabled = true;
      const ajuda = el('p', 'Nenhuma das funções serve? Explique com suas palavras.', 'nota ajuda');
      const erro = el('p', 'Escreva a observação. Sem ela a escolha não fica salva.', 'erro-campo');
      erro.id = 'observacao-erro';
      erro.hidden = !!t.value.trim();
      t.setAttribute('aria-describedby', 'observacao-erro');
      t.addEventListener('input', function () {
        const v = t.value.trim();
        erro.hidden = !!v;
        if (v) { delete p2obs[lid]; p2.funcoes[lid] = { funcao: 'indeterminado', observacao: v }; }
        else { p2obs[lid] = t.value; delete p2.funcoes[lid]; }
        mudouRascunho();
        atualizarArvore();
        atualizarFaltam();
        montarDesign();
      });
      campo.appendChild(rotulo);
      campo.appendChild(t);
      campo.appendChild(ajuda);
      campo.appendChild(erro);
      d.appendChild(campo);
    }
    if (own || p2obs[lid] !== undefined) {
      const tirar = botao(herda ? 'Voltar a herdar da pasta' : 'Tirar a escolha', 'botao tirar');
      if (!escrita) tirar.disabled = true;
      tirar.addEventListener('click', function () { delete p2.funcoes[lid]; delete p2obs[lid]; mudouP2(); });
      d.appendChild(tirar);
    }
    /* o painel foi redesenhado: o foco volta ao mesmo controle, para o teclado seguir dali */
    if (chaveFoco) {
      const alvo = Array.from(d.querySelectorAll('button, textarea')).find(function (x) {
        return chaveDoControle(x) === chaveFoco;
      });
      if (alvo) alvo.focus();
    }
  }

  /* ---------------------------------------------------------------- KV no palco, com as camadas marcadas */
  let kvDesenhado = false;
  function desenharKv() {
    const area = document.getElementById('palco-kv');
    if (kvDesenhado) { reajustar(area); return; }
    kvDesenhado = true;
    desenharPalco(area, estado.funcoes.palco_kv, { usarVista: false, semRotulos: true }).then(function () {
      if (p2idx.atual !== null) marcarNoKv('palco-kv', camadasDentro(p2idx.por.get(p2idx.atual)), null);
    });
  }
  let kvDesign = false;
  function desenharKvDesign() {
    const area = document.getElementById('palco-ds');
    if (kvDesign) { reajustar(area); marcarDesign(); return; }
    kvDesign = true;
    desenharPalco(area, estado.funcoes.palco_kv, { usarVista: false, semRotulos: true }).then(marcarDesign);
  }
  /* as camadas escolhidas ficam marcadas no KV; com a ancora, um ponto no lugar dela em cada elemento */
  function marcarNoKv(id, camadas, ancora, raizes) {
    const area = document.getElementById(id);
    const g = area ? mundos.get(area) : null;
    if (!g) return;
    g.mundo.querySelectorAll('.marca-peca, .ponto-ancora').forEach(function (x) { x.remove(); });
    const quer = new Set(camadas.map(Number));
    const caixas = new Map();
    let marcadas = 0;
    g.pecas.forEach(function (p) {
      if (!quer.has(p.camada)) return;
      marcadas += 1;
      const m = el('div', null, 'marca-peca');
      g.pos(m, p.caixa);
      g.mundo.appendChild(m);
      const r = raizes ? raizes.get(p.camada) : 0;
      const c = caixas.get(r);
      caixas.set(r, c ? [Math.min(c[0], p.caixa[0]), Math.min(c[1], p.caixa[1]), Math.max(c[2], p.caixa[2]),
        Math.max(c[3], p.caixa[3])] : p.caixa.slice());
    });
    area.dataset.marcadas = String(marcadas);
    area.dataset.ancoras = '0';
    if (!ancora || !ancora.x || !ancora.y) return;
    const fx = { esquerda: 0, centro: 0.5, direita: 1 }[ancora.x], fy = { topo: 0, meio: 0.5, base: 1 }[ancora.y];
    caixas.forEach(function (c) {
      const ponto = el('div', null, 'ponto-ancora');
      const x = c[0] + (c[2] - c[0]) * fx, y = c[1] + (c[3] - c[1]) * fy;
      g.pos(ponto, [x, y, x, y]);
      ponto.style.setProperty('--k', String(1 / (g.k() || 1)));
      g.mundo.appendChild(ponto);
    });
    area.dataset.ancoras = String(caixas.size);
  }

  /* ---------------------------------------------------------------- design system: regra e ancora (fatia 3) */
  function irParaDesign(chave) {
    p2idx.design = chave;
    mostrarPasso('design');
    montarDesign();
    const b = document.querySelector('#resumo-design [data-chave="' + chave + '"] button');
    if (b) { b.scrollIntoView({ block: 'nearest' }); b.focus(); }
  }
  function gravarDesign(v, campo, valor) {
    const alvo = v.funcao === 'indeterminado' ? p2.design_camadas : p2.design;
    const k = v.funcao === 'indeterminado' ? String(v.raiz) : v.funcao;
    const d = alvo[k] || { regra: null, x: null, y: null };
    const mudou = campo === 'ancora' ? (d.x !== valor[0] || d.y !== valor[1]) : d.regra !== valor;
    // revisao do M4: o clique no mesmo valor com a origem vencida (versao nova que mudou o campo, ou outra marca) e a
    // escolha do DA: a origem vencida sai, e o aviso some
    const vencida = !!(d.origem && d.origem[campo]) && v.funcao !== 'indeterminado' && !usaOPadrao(d, padraoDe(v), campo);
    if (campo === 'ancora') { d.x = valor[0]; d.y = valor[1]; } else d.regra = valor;
    // M7c, M4: o campo que o DA muda deixa de ser o padrao da marca (a origem dele sai; a do outro campo fica)
    if ((mudou || vencida) && d.origem) { delete d.origem[campo]; if (!Object.keys(d.origem).length) delete d.origem; }
    alvo[k] = d;
    p2idx.design = v.chave;
    tirarConfirmacoes();
    mudouRascunho();
    atualizarFaltam();
    const foco = document.activeElement;
    const marca = foco ? [foco.dataset.regra, foco.dataset.x, foco.dataset.y].join('|') : null;
    montarDesign();
    const novo = Array.from(document.querySelectorAll('#resumo-design [data-chave="' + v.chave + '"] button')).find(function (b) {
      return [b.dataset.regra, b.dataset.x, b.dataset.y].join('|') === marca;
    });
    if (novo) novo.focus();
  }
  /* ---------------------------------------------------------------- padrao da marca (M7c, M4; decisoes 162 e 190)
     a regra e a ancora que o perfil da marca escolhida no passo 1 guarda para a funcao, com a versao e o job de
     origem. Borda tracejada, como a sugestao do Claude: e sugestao citada, nunca valor. So o clique em "Usar o padrao"
     poe o valor no rascunho, com a origem padrao_marca e o ref; o DA que muda um campo tira a origem dele */
  function padraoDaMarca() {
    return (estado && estado.lido && estado.lido.marca && estado.lido.marca.padrao) || null;
  }
  function padraoDe(v) {
    const p = padraoDaMarca();
    if (!p || v.funcao === 'indeterminado') return null;
    return (p.funcoes || {})[v.funcao] || null;
  }
  function jobCurto(j) { return String(j || '').slice(0, 8); }
  /* ajuste nome do M7c (resposta do Duda ao ponto 3): o job de origem pelo nome que o DA deu a pasta do job, gravado
     no perfil ao lado do id; o perfil de antes do ajuste nao tem o nome, e a tela cai no id curto */
  function nomeDoJob(i) { return (i && i.job_nome) || jobCurto(i && i.job); }
  /* revisao do M4: o ref do clique vale com a mesma marca e o mesmo job de origem, numa versao entre a primeira com o
     valor de hoje (desde) e a atual, como no motor (desdobra.tela.funcoes._ref_vale): a versao nova que nao muda a
     funcao nao derruba o clique de antes */
  function refVale(ref, i) {
    const forma = /^marca:([0-9a-f]{32})@v([1-9][0-9]*)#job:([0-9a-f]{8,64})$/;
    const a = forma.exec(ref || ''), b = forma.exec(i.ref || '');
    const p = padraoDaMarca();
    if (!a || !b || !p || a[1] !== b[1] || a[3] !== b[3]) return false;
    const n = Number(a[2]);
    return n >= Number(i.desde || p.versao) && n <= Number(p.versao);
  }
  function usaOPadrao(d, x, campo) {
    const o = d && d.origem && d.origem[campo];
    if (!o || !x || !x[campo] || !refVale(o.ref, x[campo])) return false;
    return campo === 'regra' ? d.regra === x.regra.valor : d.x === x.ancora.x && d.y === x.ancora.y;
  }
  /* as origens do padrao no rascunho que nao batem mais com o perfil (a marca ganhou versao nova ou foi trocada no
     passo 1): o servidor recusa salvar (padrao_marca_desatualizado), e a tela pede o clique de novo */
  function padraoVencido(v) {
    if (v.funcao === 'indeterminado') return false;
    const d = p2.design[v.funcao];
    if (!d || !d.origem) return false;
    const x = padraoDe(v) || {};
    return ['regra', 'ancora'].some(function (c) { return d.origem[c] && !usaOPadrao(d, x, c); });
  }
  /* revisao do M4: o aviso da origem vencida diz o que o DA pode fazer; sem padrao na tela (Sem marca, outra marca
     sem registro), o aviso nao manda usar um padrao que nao existe */
  function avisoDoPadrao(v) {
    if (padraoDe(v)) {
      return 'O padrão da marca mudou depois do seu clique. Use o padrão de novo, ou clique de novo no tamanho e na ' +
        'âncora que quer manter.';
    }
    return 'A marca do job mudou depois do seu clique em Usar o padrão. Clique de novo no tamanho e na âncora que ' +
      'quer manter, ou escolha outro valor.';
  }
  function usarPadrao(v) {
    const x = padraoDe(v);
    if (!x) return;
    const d = p2.design[v.funcao] || { regra: null, x: null, y: null };
    const origem = {};
    if (x.regra) { d.regra = x.regra.valor; origem.regra = { tipo: 'padrao_marca', ref: x.regra.ref }; }
    if (x.ancora) { d.x = x.ancora.x; d.y = x.ancora.y; origem.ancora = { tipo: 'padrao_marca', ref: x.ancora.ref }; }
    d.origem = origem;
    p2.design[v.funcao] = d;
    p2idx.design = v.chave;
    tirarConfirmacoes();
    mudouRascunho();
    atualizarFaltam();
    montarDesign();
    const b = document.querySelector('#resumo-design [data-chave="' + v.chave + '"] .padrao-marca');
    if (b) b.focus();
  }
  function quadroDoPadrao(v, d) {
    const x = padraoDe(v);
    if (!x) return null;
    const p = padraoDaMarca();
    const itens = [x.regra, x.ancora].filter(Boolean);
    const jobs = itens.map(function (i) { return i.job; });
    const umJob = jobs.every(function (j) { return j === jobs[0]; });
    const box = el('section', null, 'sugestao padrao-marca');
    box.tabIndex = -1;
    box.setAttribute('aria-label', 'Padrão da marca');
    const topo = el('p', null, 'sugestao-fonte');
    const selo = el('span', 'Padrão da marca, versão ' + p.versao + (umJob ? ', do job ' + nomeDoJob(itens[0]) : ''),
      'sugestao-selo');
    if (umJob) selo.title = 'Job de origem ' + jobs[0];
    topo.appendChild(selo);
    box.appendChild(topo);
    const linhas = el('div', null, 'padrao-linhas');
    [['regra', 'Tamanho'], ['ancora', 'Âncora']].forEach(function (par) {
      const i = x[par[0]];
      if (!i) return;
      const linha = el('div', null, 'padrao-linha' + (usaOPadrao(d, x, par[0]) ? ' em-uso' : ''));
      linha.appendChild(el('span', par[1] + (umJob ? '' : ', do job ' + nomeDoJob(i)), 'sugestao-rotulo'));
      linha.appendChild(el('span', par[0] === 'regra' ? maiuscula(nomeRegra(i.valor)) :
        (ANCORA_Y[i.y] || i.y) + ' ' + (ANCORA_X[i.x] || i.x), 'sugestao-funcao'));
      linhas.appendChild(linha);
    });
    box.appendChild(linhas);
    const tudo = ['regra', 'ancora'].every(function (c) { return !x[c] || usaOPadrao(d, x, c); });
    const pe = el('div', null, 'padrao-pe');
    if (tudo) {
      pe.appendChild(el('span', 'Em uso', 'sugestao-em-uso'));
    } else {
      const b = botao('Usar o padrão', 'botao usar');
      b.dataset.usarPadrao = v.funcao;
      b.setAttribute('aria-label', 'Usar o padrão da marca em ' + nomeDaVista(v));
      if (!escrita) b.disabled = true;
      b.addEventListener('click', function () { usarPadrao(v); });
      pe.appendChild(b);
    }
    // revisao do M4: com valor ja escolhido, a nota diz o que o clique faz, sem dizer que nada esta gravado
    const escolhido = !!(d && (d.regra || d.x || d.y));
    pe.appendChild(el('p', tudo ? 'Você pode trocar qualquer valor abaixo.' : escolhido ?
      'O valor marcado abaixo fica gravado. Usar o padrão troca pelo valor da marca.' :
      'Nada fica gravado até você clicar em Usar o padrão ou escolher abaixo.', 'nota sugestao-nota'));
    box.appendChild(pe);
    return box;
  }
  function montarDesign() {
    const s = document.getElementById('resumo-design');
    if (!s || !p2idx.opcoes) return;
    const rolagem = s.scrollTop;
    limpar(s);
    s.appendChild(el('p', 'Passo 4', 'sobretitulo'));
    s.appendChild(el('h1', 'Design system'));
    s.appendChild(el('p', 'Para cada função, escolha como o tamanho muda de uma peça para outra e onde ela se prende. ' +
      'O elemento escolhido fica marcado no KV ao lado.', 'nota'));
    const vistas = vistasDoDesign();
    if (!vistas.length) {
      const vazio = el('div', null, 'vazio-design');
      vazio.appendChild(el('p', 'Nenhuma função com tamanho para decidir ainda.', 'vazio-titulo'));
      vazio.appendChild(el('p', 'Dê as funções das camadas no passo 2, e elas aparecem aqui.', 'nota'));
      const ir = botao('Ir para Funções', 'botao');
      ir.addEventListener('click', function () { mostrarPasso('funcoes'); });
      vazio.appendChild(ir);
      s.appendChild(vazio);
      marcarDesign();
      return;
    }
    if (!vistas.some(function (v) { return v.chave === p2idx.design; })) p2idx.design = vistas[0].chave;
    vistas.forEach(function (v, i) {
      const d = designDe(v.chave) || {};
      // revisao do M4: com a origem do padrao vencida, o servidor recusa salvar, entao o card nao se diz pronto
      const pronta = !!(d.regra && d.x && d.y) && !padraoVencido(v);
      const art = el('article', null, 'funcao-ds' + (v.chave === p2idx.design ? ' atual' : '') + (pronta ? ' feita' : ''));
      art.dataset.chave = v.chave;
      art.style.setProperty('--i', String(i));
      const topo = botao(null, 'funcao-ds-topo');
      topo.setAttribute('aria-pressed', v.chave === p2idx.design ? 'true' : 'false');
      topo.dataset.topo = '1';
      topo.appendChild(el('span', nomeDaVista(v), 'decisao-nome'));
      topo.appendChild(el('span', plural(v.camadas.length, 'camada', 'camadas') + (pronta ? ', pronta' : ''), 'decisao-estado'));
      topo.addEventListener('click', function () { p2idx.design = v.chave; montarDesign(); });
      art.appendChild(topo);
      // M7c, M4: o padrao da marca citado, com a fonte, e o aviso quando o clique de antes nao vale mais
      if (padraoVencido(v)) art.appendChild(el('p', avisoDoPadrao(v), 'aviso-padrao'));
      const quadroPadrao = quadroDoPadrao(v, d);
      if (quadroPadrao) art.appendChild(quadroPadrao);
      const corpo = el('div', null, 'funcao-ds-corpo');
      const blocoRegra = el('div', null, 'bloco-ds');
      blocoRegra.appendChild(el('h3', 'Tamanho', 'subtitulo'));
      const regras = el('div', null, 'regras');
      regras.setAttribute('role', 'group');
      regras.setAttribute('aria-label', 'Regra de escala: ' + nomeDaVista(v));
      (p2idx.opcoes.regras || []).forEach(function (r) {
        const b = botaoOpcao(maiuscula(nomeRegra(r)), d.regra === r, function () { gravarDesign(v, 'regra', r); }, 'opcao regra');
        b.dataset.regra = r;
        b.title = REGRAS_TEXTO[r] || '';
        regras.appendChild(b);
      });
      blocoRegra.appendChild(regras);
      blocoRegra.appendChild(el('p', d.regra ? (REGRAS_TEXTO[d.regra] || '') : 'Escolha uma regra.', 'nota explica'));
      corpo.appendChild(blocoRegra);
      const blocoAncora = el('div', null, 'bloco-ds');
      blocoAncora.appendChild(el('h3', 'Âncora', 'subtitulo'));
      const grade = el('div', null, 'grade-ancora');
      grade.setAttribute('role', 'group');
      grade.setAttribute('aria-label', 'Âncora: ' + nomeDaVista(v));
      (p2idx.opcoes.ancora_y || []).forEach(function (y) {
        (p2idx.opcoes.ancora_x || []).forEach(function (x) {
          const b = botaoOpcao('', d.x === x && d.y === y, function () { gravarDesign(v, 'ancora', [x, y]); }, 'ponto');
          b.dataset.x = x;
          b.dataset.y = y;
          b.setAttribute('aria-label', (ANCORA_Y[y] || y) + ' ' + (ANCORA_X[x] || x));
          b.title = (ANCORA_Y[y] || y) + ' ' + (ANCORA_X[x] || x);
          grade.appendChild(b);
        });
      });
      blocoAncora.appendChild(grade);
      blocoAncora.appendChild(el('p', d.x && d.y ? (ANCORA_Y[d.y] || d.y) + ' ' + (ANCORA_X[d.x] || d.x) + '.' :
        'Escolha um ponto.', 'nota explica'));
      corpo.appendChild(blocoAncora);
      art.appendChild(corpo);
      s.appendChild(art);
    });
    s.scrollTop = rolagem;
    marcarDesign();
  }
  function marcarDesign() {
    const v = vistasDoDesign().find(function (x) { return x.chave === p2idx.design; });
    if (!v) { marcarNoKv('palco-ds', [], null); return; }
    const raizes = new Map();
    v.camadas.forEach(function (c) { const r = resolver(p2idx.por.get(c)); raizes.set(c, r ? r.raiz : 0); });
    marcarNoKv('palco-ds', v.camadas, designDe(v.chave), raizes);
  }

  /* ---------------------------------------------------------------- composicoes */
  function formatosDoGrupo(g) {
    return g.composicoes.reduce(function (n, c) { return n.concat(c.formatos); }, []);
  }
  function contarFormatos(o) {
    return o.grupos.reduce(function (n, g) { return n + formatosDoGrupo(g).length; }, 0);
  }
  function seloDoGrupo(g) {
    const fs = formatosDoGrupo(g);
    if (g.escala_pura) return 'escala_pura';
    if (fs.some(function (x) { return x.situacao === 'derivado'; })) return 'proposta';
    if (fs.some(function (x) { return x.variantes > 0; })) return 'galeria';
    return 'devolvido';
  }
  function variantesDe(m) { return (m && m.galeria && m.galeria.variantes) || []; }
  /* o que o formato mostra primeiro: a primeira versao da galeria, quando ha, ou o modelo do palco */
  function vistaInicial(m) { const vs = variantesDe(m); return vs.length ? vs[0].palco : m; }
  /* uma caixa com a proporcao do quadro, dentro de largura x altura */
  function caixaMini(no, l, a, largura, altura) {
    const k = Math.min(largura / l, altura / a);
    no.style.width = Math.max(8, l * k) + 'px';
    no.style.height = Math.max(8, a * k) + 'px';
  }
  function onde(fid) {
    for (const o of estado.orientacoes) {
      for (const g of o.grupos) {
        if (formatosDoGrupo(g).some(function (x) { return x.id === fid; })) return { orientacao: o.id, grupo: g.id, formato: fid };
      }
    }
    return null;
  }
  function irParaFormato(fid) {
    mostrarPasso('pecas');
    iniciarPecas(onde(fid));
  }
  function selecionar(lista, b) {
    Array.from(lista.querySelectorAll('[role=tab]')).forEach(function (x) {
      x.setAttribute('aria-selected', x === b ? 'true' : 'false');
      x.tabIndex = x === b ? 0 : -1;
    });
  }
  function iniciarPecas(alvo) {
    const no = document.getElementById('orientacoes');
    limpar(no);
    if (!estado.orientacoes.length) {
      document.getElementById('palco').dataset.pronto = '1';
      // sem familia (o passo 3 espera o passo 2): nada de familia antiga no palco
      ['palco', 'fichas'].forEach(function (id) { limpar(document.getElementById(id)); });
      ['galeria', 'membros', 'variante-palco', 'barra-edicao', 'editor-texto', 'editor-quebra', 'quebra-proposta'].forEach(function (id) {
        document.getElementById(id).hidden = true;
      });
      vista.familia = null;
      vista.grupo = null;
      document.getElementById('confirmar-familia').disabled = true;
      const espera = estado.passo_3 && estado.passo_3.aguarda_passo_2;
      document.getElementById('nome-palco').textContent = espera ? estado.passo_3.texto : 'O briefing não tem formato.';
      return;
    }
    let inicial = null;
    estado.orientacoes.forEach(function (o, i) {
      const b = botao();
      b.setAttribute('role', 'tab');
      b.dataset.id = o.id;
      b.appendChild(document.createTextNode(o.rotulo + ' '));
      b.appendChild(el('span', contarFormatos(o), 'contagem'));
      b.setAttribute('aria-label', o.rotulo + ', ' + plural(contarFormatos(o), 'arquivo', 'arquivos'));
      b.addEventListener('click', function () { selecionar(no, b); orientacao(o, null); });
      no.appendChild(b);
      if ((alvo && alvo.orientacao === o.id) || (!alvo && i === 0)) inicial = [b, o];
    });
    if (!inicial) inicial = [no.firstChild, estado.orientacoes[0]];
    selecionar(no, inicial[0]);
    orientacao(inicial[1], alvo);
  }
  function orientacao(o, alvo) {
    const no = document.getElementById('composicoes');
    limpar(no);
    const baixa = window.innerHeight <= 800;
    let inicial = null;
    o.grupos.forEach(function (g, i) {
      const fs = formatosDoGrupo(g);
      const medidas = g.composicoes.map(function (c) { return dimensao(c.largura, c.altura); });
      const b = botao(null, 'miniatura');
      b.setAttribute('role', 'tab');
      b.dataset.grupo = g.id;
      b.setAttribute('aria-label', 'Família ' + medidas.join(' e ') + ', ' + plural(fs.length, 'arquivo', 'arquivos'));
      b.style.animationDelay = (i * 45) + 'ms';
      const quadro = el('div', null, 'mini-quadro');
      const mini = el('div', null, 'mini-palco carregando');
      const c0 = g.composicoes[0];
      const altura = baixa ? MINI.baixa : MINI.altura;
      caixaMini(mini, c0.largura, c0.altura, MINI.largura - 24, altura - 20);
      quadro.appendChild(mini);
      b.appendChild(quadro);
      const linha = el('div', null, 'mini-texto');
      linha.appendChild(el('span', medidas.join(', '), 'mini-medidas'));
      linha.appendChild(el('span', plural(fs.length, 'arquivo', 'arquivos'), 'mini-arquivos'));
      b.appendChild(linha);
      const tipo = seloDoGrupo(g);
      const selo = el('span', SELOS_CURTOS[tipo], 'selo mini-selo selo-' + tipo);
      b.appendChild(selo);
      b.dataset.rotulo = b.getAttribute('aria-label');
      marcarMudou(b, g);
      b.addEventListener('click', function () { selecionar(no, b); grupo(g, null); });
      no.appendChild(b);
      previa(fs[0].id).then(function (m) {
        mini.classList.remove('carregando');
        return desenharPalco(mini, vistaInicial(m), { miniatura: true });
      }).catch(function () { mini.classList.remove('carregando'); });
      if ((alvo && alvo.grupo === g.id) || (!alvo && i === 0)) inicial = [b, g];
    });
    if (!inicial && o.grupos.length) inicial = [no.firstChild, o.grupos[0]];
    if (inicial) {
      selecionar(no, inicial[0]);
      grupo(inicial[1], alvo);
    }
  }
  /* a familia que ganhou ou perdeu formatos desde que o DA mexeu nela: a marca curta na aba e, na familia aberta, a
     frase inteira acima do palco; a marca e a frase saem quando o servidor deixa de mandar o aviso (a familia
     confirmada) */
  function marcarMudou(b, g) {
    b.classList.toggle('mudou', !!g.aviso);
    b.setAttribute('aria-label', b.dataset.rotulo + (g.aviso ? '. ' + MINI_MUDOU : ''));
    const velha = b.querySelector('.mini-mudou');
    if (velha) velha.remove();
    if (g.aviso) b.appendChild(el('span', MINI_MUDOU, 'mini-mudou'));
  }
  function mostrarAvisoDaFamilia(g) {
    const aviso = document.getElementById('aviso-familia');
    aviso.textContent = g.aviso || '';
    aviso.hidden = !g.aviso;
  }
  /* o estado novo com as mesmas familias e so outra frase em alguma: a frase muda no lugar, sem redesenhar o passo 3
     nem tirar o DA da familia em que ele esta */
  function trocarAvisos(orientacoes) {
    const novos = {};
    orientacoes.forEach(function (o) { o.grupos.forEach(function (g) { novos[g.id] = g.aviso || ''; }); });
    const lista = document.getElementById('composicoes');
    (estado.orientacoes || []).forEach(function (o) {
      o.grupos.forEach(function (g) {
        g.aviso = novos[g.id] || '';
        const b = lista.querySelector('[data-grupo="' + g.id + '"]');
        if (b) marcarMudou(b, g);
        if (vista.familia === g.id) mostrarAvisoDaFamilia(g);
      });
    });
  }
  function fichaDeFormato(x, c) {
    const b = botao(null, 'ficha');
    b.setAttribute('aria-pressed', 'false');
    b.dataset.formato = x.id;
    b.appendChild(el('span', x.id, 'ficha-nome'));
    b.appendChild(el('span', dimensao(x.largura, x.altura) + (x.rotacao_graus ? ', girado ' + x.rotacao_graus + ' graus' : ''),
      'ficha-medida'));
    let situacao = c.escala_pura ? 'escala pura' : (SITUACOES[x.situacao] || 'sem situação');
    if (x.situacao === 'devolvido' && x.variantes > 0) situacao = plural(x.variantes, 'versão', 'versões') + ' para escolher';
    b.appendChild(el('span', situacao, 'situacao'));
    b.addEventListener('click', function () { mostrarFormato(x.id); });
    return b;
  }
  function grupo(g, alvo) {
    const f = document.getElementById('fichas');
    limpar(f);
    const fs = formatosDoGrupo(g);
    f.appendChild(el('span', fs.length === 1 ? 'Arquivo desta família' : 'Arquivos desta família', 'legenda'));
    g.composicoes.forEach(function (c) { c.formatos.forEach(function (x) { f.appendChild(fichaDeFormato(x, c)); }); });
    const fid = alvo && alvo.formato && fs.some(function (x) { return x.id === alvo.formato; }) ? alvo.formato : fs[0].id;
    // cada familia abre na versao do rascunho ou, sem ela, na primeira versao limpa; entre os arquivos da familia a
    // escolha fica
    vista.familia = g.id;
    vista.grupo = g;
    vista.variante = (rascunho.familias[g.id] || {}).versao || null;
    // o id da familia segue os formatos dela; quando eles mudaram, a frase do servidor diz o que entrou ou saiu
    mostrarAvisoDaFamilia(g);
    ed.previa = null;
    ed.selecionado = null;
    ed.selecao = [];
    fecharEditorTexto();
    fecharControle();
    mostrarProposta();
    mostrarFormato(fid);
  }
  function mostrarSelo(texto, tipo) {
    const selo = document.getElementById('selo-palco');
    selo.textContent = texto;
    selo.className = 'selo selo-' + tipo;
  }
  function mostrarFormato(fid) {
    const area = document.getElementById('palco');
    area.dataset.pronto = '';
    area.dataset.formato = fid;
    vista.formato = fid;
    vista.k = null;
    document.querySelectorAll('.ficha').forEach(function (b) {
      b.setAttribute('aria-pressed', b.dataset.formato === fid ? 'true' : 'false');
    });
    return previa(fid).then(function (m) {
      if (vista.formato !== fid) return null;
      vista.modelo = m;
      document.getElementById('nome-palco').textContent = fid;
      const dv = document.getElementById('devolucao');
      dv.hidden = !m.devolucao;
      dv.textContent = m.devolucao ? (m.devolucao.texto || 'O desdobra ainda não chegou a uma proposta para este formato.') : '';
      const vs = variantesDe(m);
      // com versoes, o motivo vai ao topo da galeria e a faixa da devolucao sai de cima do palco
      dv.hidden = !m.devolucao || vs.length > 0;
      document.getElementById('motivo-galeria').textContent = vs.length ? dv.textContent : '';
      montarGaleria(fid, vs);
      if (vs.length) {
        // a escolhida no grupo; sem ela, a primeira que nao pede ajuste (a ordem do motor), e so entao a primeira
        const v = vs.find(function (x) { return x.id === vista.variante; }) ||
          vs.find(function (x) { return !(x.falhas && x.falhas.length); }) || vs[0];
        return escolherVariante(fid, v);
      }
      area.dataset.variante = '';
      mostrarSelo(SELOS[m.selo] || '', m.selo);
      descreverVariante(null);
      return desenharPalco(area, m, { usarVista: true }).then(function () { return depoisDoDesenho(fid); });
    }).then(function () {
      if (vista.formato === fid) area.dataset.pronto = '1';
    }).catch(function () {
      area.dataset.pronto = 'erro';
      document.getElementById('nome-palco').textContent = 'A tela não conseguiu ler a prévia deste formato.';
    });
  }

  /* ---------------------------------------------------------------- galeria de versoes (so previa, nada gravado) */
  function marcasDa(v) {
    const marcas = [];
    if (v.falhas && v.falhas.length) {
      marcas.push([MARCA_FALHA, v.falhas.map(function (f) { return f.texto; }).join(' '), 'forte']);
    }
    if (v.decisoes_do_da && v.decisoes_do_da.length) {
      marcas.push([MARCA_DO_DA, v.decisoes_do_da.map(function (f) { return f.texto; }).join(' '), 'do-da']);
    }
    (v.avisos || []).forEach(function (a) { marcas.push([MARCAS[a.codigo] || MARCA_GERAL, a.texto, '']); });
    return marcas;
  }
  function montarGaleria(fid, vs) {
    const aside = document.getElementById('galeria');
    const lista = document.getElementById('variantes');
    limpar(lista);
    aside.hidden = !vs.length;
    vs.forEach(function (v, i) {
      const b = botao(null, 'variante');
      b.setAttribute('role', 'tab');
      b.setAttribute('aria-selected', 'false');
      b.setAttribute('aria-controls', 'palco');
      b.setAttribute('aria-label', 'Versão ' + v.ordem + ': ' + v.descricao);
      b.tabIndex = -1;
      b.dataset.variante = v.id;
      b.style.animationDelay = (i * 45) + 'ms';
      const quadro = el('div', null, 'var-quadro');
      const mini = el('div', null, 'mini-palco');
      caixaMini(mini, v.palco.largura, v.palco.altura, MINI_VARIANTE.largura, MINI_VARIANTE.altura);
      quadro.appendChild(mini);
      b.appendChild(quadro);
      const texto = el('div', null, 'var-texto');
      texto.appendChild(el('span', 'Versão ' + v.ordem, 'var-numero'));
      texto.appendChild(el('span', v.descricao, 'var-descricao'));
      const marcas = marcasDa(v);
      if (marcas.length) {
        const caixa = el('span', null, 'var-marcas');
        marcas.forEach(function (x) {
          const s = el('span', x[0], 'marca-aviso' + (x[2] ? ' ' + x[2] : ''));
          s.title = x[1];
          caixa.appendChild(s);
        });
        texto.appendChild(caixa);
      }
      b.appendChild(texto);
      b.addEventListener('click', function () {
        escolherNoRascunho(v.id); // so o clique do DA vai ao rascunho; a primeira versao do motor, nao
        ed.previa = null;
        escolherVariante(fid, v);
      });
      lista.appendChild(b);
      desenharPalco(mini, v.palco, { miniatura: true });
    });
  }
  function descreverVariante(v) {
    const no = document.getElementById('variante-palco');
    limpar(no);
    no.hidden = !v;
    if (!v) return;
    no.appendChild(el('span', 'Versão ' + v.ordem, 'var-numero'));
    no.appendChild(el('span', v.descricao, 'var-palco-descricao'));
    marcasDa(v).forEach(function (x) { no.appendChild(el('span', x[1], 'var-palco-aviso' + (x[2] ? ' ' + x[2] : ''))); });
  }
  /* a versao escolhida vai ao palco com o selo de proposta; a vista (Ajustar ou o zoom) continua a do formato */
  function escolherVariante(fid, v) {
    const area = document.getElementById('palco');
    if (vista.formato !== fid) return Promise.resolve(null);
    vista.variante = v.id;
    area.dataset.pronto = '';
    area.dataset.variante = v.id;
    const lista = document.getElementById('variantes');
    const b = Array.from(lista.querySelectorAll('[role=tab]')).find(function (x) { return x.dataset.variante === v.id; });
    if (b) selecionar(lista, b);
    const total = lista.querySelectorAll('[role=tab]').length;
    mostrarSelo('Versão ' + v.ordem + ' de ' + total + ': ' + SELO_VARIANTE, 'proposta');
    descreverVariante(v);
    return desenharPalco(area, v.palco, { usarVista: true }).then(function () {
      return depoisDoDesenho(fid);
    }).then(function () {
      if (vista.formato === fid && vista.variante === v.id) area.dataset.pronto = '1';
    });
  }

  /* ---------------------------------------------------------------- palco */
  /* o nome curto do elemento: o da camada, ou a funcao sem ele */
  function nomeCurto(e) { return e.nome || nomeFuncao(e.funcao); }
  function rotuloElemento(e) {
    const partes = [nomeFuncao(e.funcao)];
    if (e.nome) partes.push(e.nome);
    if (e.fantasma) { if (!e.regra) partes.push(SEM_REGRA); } else if (e.regra) partes.push(nomeRegra(e.regra));
    return partes.join(' · ');
  }
  /* opcoes.miniatura: o mesmo modelo, so o quadro (sem rotulos nem sangria), no tamanho da caixa da aba */
  function desenharPalco(area, m, opcoes) {
    limpar(area);
    const mini = !!opcoes.miniatura;
    const x0 = m.mundo[0], y0 = m.mundo[1];
    const Wm = m.mundo[2] - x0, Hm = m.mundo[3] - y0;
    const caixa = el('div', null, mini ? null : 'escala');
    const mundo = el('div', null, 'mundo');
    mundo.style.width = Wm + 'px';
    mundo.style.height = Hm + 'px';
    function pos(no, c) {
      no.style.left = (c[0] - x0) + 'px';
      no.style.top = (c[1] - y0) + 'px';
      no.style.width = Math.max(0, c[2] - c[0]) + 'px';
      no.style.height = Math.max(0, c[3] - c[1]) + 'px';
    }
    const quadro = [0, 0, m.largura, m.altura];
    const fundo = el('div', null, 'quadro-fundo');
    pos(fundo, quadro);
    mundo.appendChild(fundo);
    const textos = [];
    m.pecas.forEach(function (p) {
      const rec = el('div', null, 'recorte');
      rec.dataset.camada = String(p.camada);
      if (p.elemento) rec.dataset.elemento = p.elemento;
      pos(rec, p.recorte);
      const no = criarPeca(p, textos);
      if (!no) return;
      if (p.fantasma) no.classList.add('fantasma');
      if (p.opacidade !== null && p.opacidade !== undefined && p.opacidade < 1) no.style.opacity = String(p.opacidade);
      rec.appendChild(no);
      mundo.appendChild(rec);
    });
    const etiquetas = [];
    if (!mini) {
      [[x0, y0, m.mundo[2], 0], [x0, m.altura, m.mundo[2], m.mundo[3]], [x0, 0, 0, m.altura],
        [m.largura, 0, m.mundo[2], m.altura]].forEach(function (c) {
        if (c[2] > c[0] && c[3] > c[1]) { const f = el('div', null, 'fora'); pos(f, c); mundo.appendChild(f); }
      });
      const moldura = el('div', null, 'moldura');
      pos(moldura, quadro);
      mundo.appendChild(moldura);
      (opcoes.semRotulos ? [] : m.elementos).forEach(function (e) {
        const r = el('div', null, 'rotulo' + (e.fantasma ? ' fantasma' : ''));
        pos(r, e.caixa);
        r.dataset.elemento = e.id;
        if (opcoes.editavel) {
          r.classList.add('editavel');
          r.tabIndex = 0;
          r.setAttribute('role', 'button');
          r.setAttribute('aria-label', 'Mexer em ' + rotuloElemento(e));
          if (CONTEUDO.indexOf(e.funcao) >= 0) r.classList.add('de-conteudo'); // o conteudo fica por cima do fundo
          if (e.id === ed.selecionado) r.classList.add('selecionado');
        }
        if (e.raiz !== null && e.raiz !== undefined) r.dataset.raiz = String(e.raiz);
        const et = el('span', rotuloElemento(e), 'etiqueta');
        r.appendChild(et);
        etiquetas.push([et, e.caixa]);
        mundo.appendChild(r);
      });
      mundo.style.setProperty('--recorte-limpo', 'inset(' + (-y0) + 'px ' + (m.mundo[2] - m.largura) + 'px ' +
        (m.mundo[3] - m.altura) + 'px ' + (-x0) + 'px)');
    }
    caixa.appendChild(mundo);
    area.appendChild(caixa);
    /* o fantasma (decisao 162) e so desenho: o aviso vai uma vez por palco, nunca em cada elemento */
    if (!mini && m.elementos.some(function (e) { return e.fantasma; })) {
      const aviso = el('p', null, 'aviso-apoio');
      const amostra = el('span', null, 'amostra-hachura');
      amostra.setAttribute('aria-hidden', 'true');
      aviso.appendChild(amostra);
      aviso.appendChild(el('span', 'Hachurado: ' + APOIO));
      area.appendChild(aviso);
    }
    if (area.id === 'palco') {
      area.classList.toggle('limpo', vista.limpo);
      area.classList.toggle('sem-nomes', !vista.nomes);
    }
    const medida = document.getElementById('medida-palco');
    function ajustar() {
      if (mini) {
        // a caixa da aba ja tem a proporcao do quadro: a escala leva o quadro a ela, a sangria fica fora
        const k = Math.min(area.clientWidth / m.largura, area.clientHeight / m.altura) || 1;
        mundo.style.left = (x0 * k) + 'px';
        mundo.style.top = (y0 * k) + 'px';
        mundo.style.transform = 'scale(' + k + ')';
        return;
      }
      let k = opcoes.usarVista && vista.k ? vista.k :
        Math.min((area.clientWidth - MARGEM) / Wm, (area.clientHeight - MARGEM) / Hm);
      if (!(k > 0)) k = 1;
      caixa.style.width = (Wm * k) + 'px';
      caixa.style.height = (Hm * k) + 'px';
      mundo.style.transform = 'scale(' + k + ')';
      // a etiqueta fica no tamanho da tela; perto da borda direita ela se alinha pela direita, sem passar do palco
      etiquetas.forEach(function (par) {
        const et = par[0];
        const direita = par[1][0] - x0 + et.offsetWidth / k > Wm;
        et.classList.toggle('pela-direita', direita);
        et.style.transform = 'scale(' + (1 / k) + ') translateY(-100%)';
      });
      if (opcoes.usarVista && medida) {
        medida.textContent = dimensao(m.largura, m.altura) + ' px, exibição em ' + Math.round(k * 100) + '%' +
          (opcoes.usarVista && vista.k ? '' : ', ajustada');
        area.dataset.vista = opcoes.usarVista && vista.k ? 'zoom' : 'ajustar';
      }
    }
    ajustes.set(area, ajustar);
    mundos.set(area, { mundo: mundo, pos: pos, pecas: m.pecas, modelo: m, x0: x0, y0: y0, k: function () {
      const t = /scale\(([0-9.e-]+)\)/.exec(mundo.style.transform); return t ? parseFloat(t[1]) : 1; } });
    return document.fonts.ready.then(function () {
      mundo.style.transform = 'none';
      textos.forEach(medirTexto);
      ajustar();
    });
  }
  function reajustar(area) { const f = ajustes.get(area); if (f) f(); }
  function criarPeca(p, textos) {
    const [cx0, cy0, cx1, cy1] = p.caixa;
    function dentro(no, c) {
      no.style.left = (c[0] - p.recorte[0]) + 'px';
      no.style.top = (c[1] - p.recorte[1]) + 'px';
      no.style.width = Math.max(0, c[2] - c[0]) + 'px';
      no.style.height = Math.max(0, c[3] - c[1]) + 'px';
    }
    const desenhoDeImagem = p.tipo === 'imagem' || (p.tipo === 'texto' && p.modo === 'imagem');
    if (desenhoDeImagem && p.asset) {
      const img = document.createElement('img');
      img.className = 'peca';
      img.alt = '';
      img.draggable = false;
      img.src = '/asset/' + encodeURIComponent(p.asset);
      dentro(img, [cx0, cy0, cx1, cy1]);
      return img;
    }
    if (p.tipo === 'texto') {
      const t = el('div', null, 'peca texto');
      const alvo = p.caixa_tinta;
      t.style.left = (alvo[0] - p.recorte[0]) + 'px';
      t.style.top = (alvo[1] - p.recorte[1]) + 'px';
      t.style.width = Math.max(0, alvo[2] - alvo[0]) + 'px';
      t.style.textAlign = { esquerda: 'left', centro: 'center', direita: 'right' }[p.alinhamento] || 'left';
      if (p.texto_editado) t.classList.add('editado');
      if (p.faltando && p.faltando.length) t.classList.add('sem-fonte');
      p.linhas.forEach(function (ln) {
        const linha = el('div', null, 'linha');
        linha.appendChild(el('span', null, 'marco'));
        ln.trechos.forEach(function (tr) {
          const s = el('span', tr.texto, 'trecho');
          if (tr.face && familiaCss.has(tr.face)) s.style.fontFamily = '"' + familiaCss.get(tr.face) + '"';
          if (tr.corpo) s.style.fontSize = tr.corpo + 'px';
          if (tr.cor) s.style.color = tr.cor;
          if (tr.tracking && tr.corpo) s.style.letterSpacing = (tr.tracking * tr.corpo / 1000) + 'px';
          linha.appendChild(s);
        });
        if (ln.entrelinha) linha.dataset.entrelinha = String(ln.entrelinha);
        /* a linha do texto editado que quebra na largura da caixa desce uma entrelinha, como no render */
        if (p.texto_editado && ln.entrelinha) linha.style.lineHeight = ln.entrelinha + 'px';
        t.appendChild(linha);
      });
      textos.push({ no: t, peca: p, x: alvo[0] - p.recorte[0], y: alvo[1] - p.recorte[1], largura: alvo[2] - alvo[0] });
      return t;
    }
    const v = el('div', null, 'peca sem-imagem');
    dentro(v, [cx0, cy0, cx1, cy1]);
    return v;
  }
  /* A tinta do texto medida no proprio Chromium: o marco de largura zero da a linha de base de cada linha, e o
     canvas, com a mesma face carregada, da a caixa de tinta de cada trecho (actualBoundingBox). A distancia entre as
     linhas de base e a entrelinha do PSD, como no render (render/texto.py: y += entrelinha da linha): a caixa de linha
     do CSS soma a meia entrelinha do strut, na fonte da pagina, a do trecho e fica mais alta que a entrelinha, entao
     cada linha e levada a linha de base certa. O bloco e deslocado para a tinta cair na caixa de tinta da camada,
     levada ao formato pela transformacao do elemento. */
  function medirTexto(t) {
    const base = t.no.getBoundingClientRect();
    let tinta = null;
    const linhas = Array.from(t.no.querySelectorAll('.linha'));
    const bases = linhas.map(function (linha) {
      return linha.querySelector('.marco').getBoundingClientRect().bottom - base.top;
    });
    let yBase = bases.length ? bases[0] : 0;
    linhas.forEach(function (linha, n) {
      if (n > 0) {
        const e = parseFloat(linha.dataset.entrelinha);
        yBase += e > 0 ? e : bases[n] - bases[n - 1];
      }
      linha.style.top = (yBase - bases[n]) + 'px';
      linha.querySelectorAll('.trecho').forEach(function (s) {
        const r = s.getBoundingClientRect();
        const cs = getComputedStyle(s);
        regua.font = cs.fontStyle + ' ' + cs.fontWeight + ' ' + cs.fontSize + ' ' + cs.fontFamily;
        regua.letterSpacing = cs.letterSpacing === 'normal' ? '0px' : cs.letterSpacing;
        const mm = regua.measureText(s.textContent);
        const x = r.left - base.left;
        const c = [x - mm.actualBoundingBoxLeft, yBase - mm.actualBoundingBoxAscent, x + mm.actualBoundingBoxRight,
          yBase + mm.actualBoundingBoxDescent];
        if (c[2] - c[0] <= 0 || c[3] - c[1] <= 0) return;
        tinta = tinta ? [Math.min(tinta[0], c[0]), Math.min(tinta[1], c[1]), Math.max(tinta[2], c[2]),
          Math.max(tinta[3], c[3])] : c;
      });
    });
    if (!tinta) { t.no.dataset.tinta = ''; return; }
    const w = tinta[2] - tinta[0];
    let dx = -tinta[0];
    if (t.peca.alinhamento === 'centro') dx = (t.largura - w) / 2 - tinta[0];
    else if (t.peca.alinhamento === 'direita') dx = t.largura - tinta[2];
    const dy = -tinta[1];
    t.no.style.left = (t.x + dx) + 'px';
    t.no.style.top = (t.y + dy) + 'px';
    t.no.dataset.tinta = w.toFixed(2) + ',' + (tinta[3] - tinta[1]).toFixed(2);
    t.no.dataset.desvio = dx.toFixed(2) + ',' + dy.toFixed(2);
    const ox = t.peca.recorte[0] + t.x + dx, oy = t.peca.recorte[1] + t.y + dy;
    t.no.dataset.caixaTinta = [ox + tinta[0], oy + tinta[1], ox + tinta[2], oy + tinta[3]].map(function (v) {
      return v.toFixed(2);
    }).join(',');
  }

  /* ---------------------------------------------------------------- edicao por familia (decisoes 167 a 171) */
  function familiaAtual() {
    if (!vista.familia) return null;
    if (!rascunho.familias[vista.familia]) rascunho.familias[vista.familia] = { versao: null, confirmada: false, edicoes: [] };
    return rascunho.familias[vista.familia];
  }
  function edicoesDa() { const f = rascunho.familias[vista.familia]; return (f && f.edicoes) || []; }
  function temGaleria() {
    return !!(vista.grupo && formatosDoGrupo(vista.grupo).some(function (x) { return x.variantes > 0; }));
  }
  function versaoDaFamilia() { return temGaleria() ? (vista.variante || null) : null; }
  function familiaConfirmada() { const f = rascunho.familias[vista.familia]; return !!(f && f.confirmada); }
  function editavel() { return escrita && rascunho.espera !== null && !!vista.familia; }
  function fracao(v) { return Math.round(v * CASAS_FRACAO) / CASAS_FRACAO; }
  function mensagem(texto, erro) {
    const no = document.getElementById('ed-mensagem');
    no.textContent = texto || '';
    no.title = texto || ''; // a frase que passa da altura da linha termina em reticencias: inteira no title
    no.classList.toggle('erro', !!erro);
  }
  function modeloDoPalco() { const g = mundos.get(document.getElementById('palco')); return g ? g.modelo : null; }
  function elementoDoPalco(id) {
    const m = modeloDoPalco();
    return m ? m.elementos.find(function (e) { return e.id === id; }) || null : null;
  }
  function pecasDeTexto(id) {
    const m = modeloDoPalco();
    return m ? m.pecas.filter(function (p) { return p.elemento === id && p.tipo === 'texto' && p.linhas && p.linhas.length; }) : [];
  }
  function depoisDoDesenho() {
    atualizarBotaoFamilia();
    if (!editavel()) return null;
    document.getElementById('barra-edicao').hidden = false;
    return pedirPrevia();
  }
  /* a edicao vai ao motor, que a leva a cada arquivo da familia; o pedido mais novo vence. As quebras de linha do
     rascunho da familia (M7b, C3) vao sempre junto, a lista vazia quando o DA tirou a ultima: o motor mede o texto
     com elas e refaz os membros, e nunca volta a quebra do briefing de antes */
  function pedirPrevia() {
    clearTimeout(ed.esperaQuebra);
    ed.esperaQuebra = null;
    const n = ++ed.pedido;
    const fam = rascunho.familias[vista.familia];
    const dados = { familia: vista.familia, versao: versaoDaFamilia(), edicoes: edicoesDa(),
      quebras: (fam && fam.quebras) || [] };
    raiz.dataset.previa = 'pedindo';
    atualizarBotaoFamilia();
    return enviar('/api/familia/previa', dados).then(function (r) {
      if (n !== ed.pedido) return null;
      ed.previa = r;
      if (r.recusas && r.recusas.length) tirarRecusadas(r.recusas);
      else if (ed.textoPendente) { fecharEditorTexto(); mensagem('O texto novo vale só nesta família.'); }
      ed.textoPendente = null;
      return desenharDaPrevia();
    }).then(function () {
      if (n !== ed.pedido) return;
      raiz.dataset.previa = 'pronta';
      atualizarBotaoFamilia();
    }).catch(function () {
      if (n !== ed.pedido) return;
      raiz.dataset.previa = 'erro';
      atualizarBotaoFamilia();
      mensagem('A tela não conseguiu refazer a família. A última mudança continua no rascunho; tente de novo.');
    });
  }
  /* a quebra de linha mudada no palco (o controle da quebra chama aqui): a previa espera 300 ms sem clique, e cada
     clique nesse meio tempo recomeca a espera; o pedido leva as quebras que estiverem no rascunho na hora */
  function pedirPreviaDaQuebra() {
    clearTimeout(ed.esperaQuebra);
    ed.esperaQuebra = setTimeout(pedirPrevia, ESPERA_QUEBRA_MS);
    atualizarBotaoFamilia();
  }
  /* a previa da familia ainda nao mostra a ultima mudanca: a espera da quebra ou o pedido no caminho */
  function esperandoPrevia() { return !!ed.esperaQuebra || raiz.dataset.previa === 'pedindo'; }
  document.addEventListener('pointerdown', function () {
    if (ed.esperaQuebra) pedirPreviaDaQuebra();
  }, true);
  function tirarRecusadas(recusas) {
    const ids = new Set(recusas.map(function (x) { return x.elemento; }));
    const f = familiaAtual();
    f.edicoes = f.edicoes.filter(function (e) { return !(e.acao === 'texto' && ids.has(e.elemento)); });
    ids.forEach(tirarQuebra);
    mudouRascunho();
    if (!document.getElementById('editor-texto').hidden) {
      const campo = document.getElementById('ed-campo-texto');
      document.getElementById('ed-erro-texto').textContent = recusas[0].texto;
      campo.setAttribute('aria-invalid', 'true');
      campo.focus();
    } else {
      mensagem(recusas[0].texto);
    }
  }
  function desenharDaPrevia() {
    const r = ed.previa;
    if (!r) return null;
    montarMembros(r);
    montarResumo(r);
    const m = r.membros.find(function (x) { return x.formato === vista.formato; });
    if (!m) return null;
    const area = document.getElementById('palco');
    const focar = ed.focar;
    ed.focar = false;
    const quem = ed.ultimaEdicao;
    ed.ultimaEdicao = null;
    const alinhou = ed.alinhou;
    ed.alinhou = null;
    const tamanho = ed.fraseTamanho;
    ed.fraseTamanho = null;
    return desenharPalco(area, m.palco, { usarVista: true, editavel: true }).then(function () {
      if (comEdicoes()) descreverMembro(m);
      atualizarSelo();
      marcarSelecao();
      atualizarBarra();
      if (alinhou) mostrarNoQuadro(area, r, alinhou);
      else if (quem) mostrarAlinhamento(area, r, quem);
      // o tamanho digitado (M7b, D3): a frase vem antes da do alinhamento, quando ele encostou em outro elemento
      if (tamanho) {
        const depois = document.getElementById('ed-mensagem').textContent;
        mensagem(tamanho + (depois && depois !== tamanho ? ' ' + depois : ''));
      }
      if (focar && ed.selecionado) {
        const alvo = area.querySelector('.rotulo[data-elemento="' + ed.selecionado + '"]');
        if (alvo) alvo.focus();
      }
      // a quebra de linha (M7b, C4): a proposta do desdobra marcada no palco, o controle com o texto de agora e o
      // texto editado que quebrou na largura da caixa, que vira proposta e pede a previa com ela
      marcarQuebrasNoPalco();
      mostrarProposta();
      if (controleAberto()) desenharControle(null);
      if (proporQuebras()) return pedirPrevia();
      return null;
    });
  }
  /* a familia tem edicao do DA: as edicoes do palco ou uma quebra de linha mudada (M7b, C4) */
  function comEdicoes() { return edicoesDa().length > 0 || quebrasDa(vista.familia).length > 0; }
  /* o desdobra alinha de novo depois de cada edicao (decisao 168), tambem a das setas e do + e -, que nao passam pelo
     encaixe do arraste: quando a ultima edicao encostou na linha de outro elemento, a mesma linha discreta do
     arraste fica no palco e a tela diz o que aconteceu */
  function mostrarAlinhamento(area, r, quem) {
    const g = mundos.get(area);
    if (!g) return;
    const melhor = { x: null, y: null };
    (r.alinhados || []).forEach(function (a) {
      if (a.formato === vista.formato && a.elementos.indexOf(quem) >= 0) melhor[a.eixo] = { valor: a.valor };
    });
    if (!melhor.x && !melhor.y) return;
    guias(g, melhor, g.modelo);
    mensagem('Ficou alinhado com outro elemento, pela linha que aparece no palco. Desfazer volta ao lugar de antes.');
  }
  function descreverMembro(m) {
    const no = document.getElementById('variante-palco');
    limpar(no);
    no.hidden = false;
    no.appendChild(el('span', 'Com as suas edições', 'var-numero'));
    no.appendChild(el('span', 'Cada edição vale para todos os arquivos desta família.', 'var-palco-descricao'));
    marcasDa({ falhas: m.falhas, decisoes_do_da: m.decisoes_do_da, avisos: m.avisos }).forEach(function (x) {
      no.appendChild(el('span', x[1], 'var-palco-aviso' + (x[2] ? ' ' + x[2] : '')));
    });
  }
  function atualizarSelo() {
    if (familiaConfirmada()) mostrarSelo(SELO_CONFIRMADA, 'confirmada');
    else if (comEdicoes()) mostrarSelo('Com as suas edições: ' + SELO_VARIANTE, 'proposta');
  }
  function montarMembros(r) {
    const sec = document.getElementById('membros');
    const lista = document.getElementById('membros-lista');
    limpar(lista);
    sec.hidden = !r.membros.length;
    r.membros.forEach(function (m, i) {
      const b = botao(null, 'membro');
      b.dataset.formato = m.formato;
      b.style.animationDelay = (i * 35) + 'ms';
      b.setAttribute('aria-pressed', m.formato === vista.formato ? 'true' : 'false');
      b.setAttribute('aria-label', m.formato + ', ' + dimensao(m.palco.largura, m.palco.altura) +
        (m.falhas.length ? ', pede ajuste' : '') + (decisoes(m).length ? ', decisão do DA' : ''));
      const quadro = el('div', null, 'membro-quadro');
      const mini = el('div', null, 'mini-palco');
      caixaMini(mini, m.palco.largura, m.palco.altura, MINI_MEMBRO.largura, MINI_MEMBRO.altura);
      quadro.appendChild(mini);
      b.appendChild(quadro);
      b.appendChild(el('span', m.formato, 'membro-nome'));
      b.appendChild(el('span', dimensao(m.palco.largura, m.palco.altura), 'membro-medida'));
      if (m.falhas.length) {
        const s = el('span', MARCA_FALHA, 'marca-aviso forte');
        s.title = m.falhas.map(function (f) { return f.texto; }).join(' ');
        b.appendChild(s);
      }
      if (decisoes(m).length) {
        const s = el('span', MARCA_DO_DA, 'marca-aviso do-da');
        s.title = decisoes(m).map(function (f) { return f.texto; }).join(' ');
        b.appendChild(s);
      }
      b.addEventListener('click', function () { mostrarFormato(m.formato); });
      lista.appendChild(b);
      desenharPalco(mini, m.palco, { miniatura: true });
    });
  }
  function nomes(lista) { return lista.map(function (x) { return x.nome || 'sem nome'; }).join(', '); }
  /* o piso que o DA furou no membro (M7b, D5); a previa sem o campo nao tem decisao */
  function decisoes(m) { return m.decisoes_do_da || []; }
  function montarResumo(r) {
    const partes = [];
    if (r.textos_editados.length) partes.push('Texto editado nesta família: ' + nomes(r.textos_editados) + '.');
    if (r.apagados.length) partes.push('Tirado desta família: ' + nomes(r.apagados) + '.');
    const quebras = quebrasDa(vista.familia).length;
    if (quebras) partes.push(quebras === 1 ? 'Quebra de linha mudada em 1 texto desta família.' :
      'Quebra de linha mudada em ' + quebras + ' textos desta família.');
    document.getElementById('resumo-edicao').textContent = partes.join(' ');
  }
  function atualizarBotaoFamilia() {
    const b = document.getElementById('confirmar-familia');
    if (!editavel()) { b.disabled = true; return; }
    const conf = familiaConfirmada();
    // a versao confirmada e a que o DA escolheu (clique na galeria ou edicao sobre ela), gravada no rascunho; a
    // primeira versao que a tela mostra sozinha nao conta como escolha
    const f = rascunho.familias[vista.familia];
    const versao = temGaleria() ? ((f && f.versao) || null) : null;
    const semEscolha = temGaleria() && !versao;
    // um formato da familia espera a confirmacao de um valor de spec no passo 1: o servidor recusa a confirmacao
    const doGrupo = vista.grupo ? formatosDoGrupo(vista.grupo) : [];
    const semSpecProprio = doGrupo.some(function (x) { return x.motivo === MOTIVO_SEM_SPEC; });
    const semSpecDaMestre = doGrupo.some(function (x) { return x.motivo === MOTIVO_SEM_SPEC_DA_MESTRE; });
    const semSpec = semSpecProprio || semSpecDaMestre;
    // a quebra de linha proposta pelo desdobra espera o clique do DA (M7b, C4): o servidor recusa tambem
    const semQuebra = porAprovar(vista.familia).length > 0;
    // a previa da ultima mudanca ainda nao voltou (revisao 2 do C): o DA confirma a familia que viu, e a quebra que o
    // texto editado ganha na largura da caixa so vira proposta quando a previa volta
    const semPrevia = esperandoPrevia();
    // o rascunho que nao gravou (revisao 1 da fase D): a familia confirmada seria a gravada antes, sem a ultima escolha
    const semGravar = raiz.dataset.rascunho === 'erro';
    b.textContent = conf ? SELO_CONFIRMADA : 'Confirmar família';
    b.disabled = conf || semEscolha || semSpec || semQuebra || semPrevia || semGravar;
    b.title = semSpecProprio ? FAMILIA_SEM_SPEC : (semSpecDaMestre ? FAMILIA_SEM_SPEC_DA_MESTRE :
      (semEscolha ? 'Escolha uma versão na galeria antes de confirmar a família.' : (semQuebra ? QUEBRA_SEM_APROVAR :
        (semPrevia ? FAMILIA_ESPERA_PREVIA : (semGravar ? FAMILIA_SEM_GRAVAR : '')))));
    b.dataset.ato = 'familia';
    b.dataset.dados = JSON.stringify({ familia: vista.familia, versao: versao });
  }
  /* a lista do grupo de uma edicao (M7b, D1), em texto, para comparar duas edicoes */
  function grupoDe(e) { return JSON.stringify(e.elementos || [e.elemento]); }
  function novaEdicao(e, juntar) {
    const f = familiaAtual();
    const ult = f.edicoes[f.edicoes.length - 1];
    if (juntar && ult && ult.acao === 'mover' && e.acao === 'mover' && grupoDe(ult) === grupoDe(e)) {
      ult.dx = fracao(ult.dx + e.dx);
      ult.dy = fracao(ult.dy + e.dy);
    } else {
      f.edicoes.push(e);
      contarNoCronometro('edicoes'); // a seta que junta com a anterior e a mesma edicao
    }
    if (temGaleria()) f.versao = versaoDaFamilia();
    f.confirmada = false;
    delete f.confirmacao;
    ed.ultimaEdicao = e.elemento;
    mudouRascunho();
    atualizarBotaoFamilia();
    return pedirPrevia();
  }
  /* a edicao de um elemento, ou do grupo (M7b, D1): com dois ou mais, a lista vai junto e o primeiro e o elemento.
     No escalar do grupo, fx e fy sao fracoes da caixa que junta o grupo, e cada arquivo da familia escala o grupo em
     volta do mesmo ponto dele */
  function edicaoDe(ids, acao) {
    const lista = [].concat(ids);
    const e = { elemento: lista[0], acao: acao };
    if (lista.length > 1) e.elementos = lista;
    return e;
  }
  function moverPor(ids, dx, dy, juntar) {
    const m = modeloDoPalco();
    const e = edicaoDe(ids, 'mover');
    e.dx = fracao(dx / m.largura);
    e.dy = fracao(dy / m.altura);
    return novaEdicao(e, juntar);
  }
  /* o fator para no limite do tamanho (M7b, D3): Diminuir, Aumentar, + e - e o canto nunca passam dele. Sem espaco
     para mexer, nada e gravado e a tela diz por que */
  /* o ponto fixo de Tamanho, Diminuir, Aumentar e + e - (revisao 1 da fase D): o meio do escolhido, menos no lado em
     que ele chega a borda da peca no arquivo do palco. Ali ele fica preso a borda: o circulo que sangra na base muda
     de tamanho sem sair dela, e o corte que ele tinha no KV nunca aparece. undefined: o meio nos dois eixos */
  function pontoFixo(ids) {
    const m = modeloDoPalco();
    if (!m) return undefined;
    const c = caixaDoGrupo(ids);
    const lado = function (a, b, total) {
      const antes = a <= BORDA_PX;
      const depois = b >= total - BORDA_PX;
      return antes && !depois ? 0 : (depois && !antes ? 1 : 0.5);
    };
    const fx = lado(c[0], c[2], m.largura);
    const fy = lado(c[1], c[3], m.altura);
    return fx === 0.5 && fy === 0.5 ? undefined : [fx, fy];
  }
  function escalarNoLugar(ids, fator) {
    const p = pontoFixo(ids);
    return p ? escalarPor(ids, fator, p[0], p[1]) : escalarPor(ids, fator);
  }
  function escalarPor(ids, fator, fx, fy) {
    if (!ids || ![].concat(ids).length) return null;
    const faixa = faixaDoFator([].concat(ids));
    const f = Math.min(faixa[1], Math.max(faixa[0], fator));
    if (Math.abs(f - 1) <= FATOR_IGUAL) {
      ed.focar = false;
      mensagem(fraseDoLimite(fator > 1));
      atualizarBarra();
      return null;
    }
    const e = edicaoDe(ids, 'escalar');
    e.fator = fracao(f);
    if (fx !== undefined) { e.fx = fx; e.fy = fy; }
    return novaEdicao(e, false);
  }
  /* ------------------------------------------------ o tamanho por numero (M7b, D3)
     O tamanho de cada elemento e a conta dos fatores das edicoes de escalar que o levam, sozinho ou no grupo, como o
     desdobra faz (desdobra.tela.edicao.escalas): 100% e o tamanho antes das edicoes do DA. O campo Tamanho mostra o
     tamanho do escolhido, ou do grupo quando todos tem o mesmo; o numero digitado vira um escalar so, o que leva do
     tamanho de agora ao digitado. No grupo com tamanhos diferentes, o numero muda o tamanho de agora de cada um. */
  function limitesEscala() {
    const e = estado.edicao || {};
    return [typeof e.escala_min === 'number' ? e.escala_min : ESCALA_PADRAO[0],
      typeof e.escala_max === 'number' ? e.escala_max : ESCALA_PADRAO[1]];
  }
  function membrosDa(e) { return e.elementos || [e.elemento]; }
  function tamanhoDe(id) {
    let s = 1;
    edicoesDa().forEach(function (e) {
      if (e.acao === 'apagar' && e.elemento === id) s = 1;
      else if (e.acao === 'escalar' && membrosDa(e).indexOf(id) >= 0) s *= e.fator;
    });
    return s;
  }
  /* o tamanho comum dos escolhidos, ou null quando eles tem tamanhos diferentes */
  function tamanhoDaSelecao(ids) {
    if (!ids.length) return null;
    const s = tamanhoDe(ids[0]);
    return ids.every(function (i) { return Math.abs(tamanhoDe(i) - s) <= s * FOLGA_ESCALA; }) ? s : null;
  }
  /* no grupo com tamanhos diferentes (revisao 1 da fase D), o campo mostra o tamanho do grupo desde que ele foi
     escolhido: 100 no comeco. O numero digitado e esse tamanho, como no elemento so: digitar o mesmo numero de novo
     nao grava nada, e o campo mostra o numero que vale agora */
  function baseDoGrupo(ids) {
    const chave = ids.join(' ');
    if (!ed.baseGrupo || ed.baseGrupo.chave !== chave) {
      const t = {};
      ids.forEach(function (i) { t[i] = tamanhoDe(i); });
      ed.baseGrupo = { chave: chave, tamanhos: t };
    }
    return ed.baseGrupo.tamanhos;
  }
  function tamanhoDoGrupo(ids) {
    const base = baseDoGrupo(ids);
    const r = tamanhoDe(ids[0]) / base[ids[0]];
    if (ids.every(function (i) { return Math.abs(tamanhoDe(i) / base[i] - r) <= r * FOLGA_ESCALA; })) return r;
    ed.baseGrupo = null; // um do grupo mudou sozinho: o tamanho de agora volta a ser 100
    baseDoGrupo(ids);
    return 1;
  }
  /* [menor, maior] fator que deixa cada escolhido dentro dos limites do tamanho */
  function faixaDoFator(ids) {
    const lim = limitesEscala();
    let fmin = 0;
    let fmax = Infinity;
    ids.forEach(function (i) {
      const s = tamanhoDe(i);
      fmin = Math.max(fmin, lim[0] / s);
      fmax = Math.min(fmax, lim[1] / s);
    });
    return [fmin, fmax];
  }
  function porcento(v) { return String(Math.round(v * CASAS_TAMANHO) / CASAS_TAMANHO).replace('.', ','); }
  function fraseDaFaixa() {
    const lim = limitesEscala();
    return 'O tamanho vai de ' + porcento(lim[0] * POR_CENTO) + '% a ' + porcento(lim[1] * POR_CENTO) + '%.';
  }
  function fraseDoLimite(maior) {
    return (maior ? 'Chegou ao maior tamanho. ' : 'Chegou ao menor tamanho. ') + fraseDaFaixa();
  }
  /* o numero digitado: aceita virgula ou ponto e o % no fim; null sem numero */
  function lerPorcentagem(texto) {
    const t = String(texto || '').replace(/%/g, '').replace(/\s+/g, '').replace(',', '.');
    if (!/^\d+(\.\d+)?$/.test(t) && !/^\.\d+$/.test(t)) return null;
    return parseFloat(t);
  }
  function campoTamanho() { return document.getElementById('ed-tamanho'); }
  function errarTamanho(texto) {
    const campo = campoTamanho();
    campo.setAttribute('aria-invalid', 'true');
    mensagem(texto, true);
    campo.focus();
    campo.select();
  }
  function aplicarTamanho() {
    const ids = escolhidos();
    const campo = campoTamanho();
    if (!ids.length || campo.disabled) return null;
    const v = lerPorcentagem(campo.value);
    const lim = limitesEscala();
    if (v === null) { errarTamanho('Digite o tamanho em número, por exemplo 155. ' + fraseDaFaixa()); return null; }
    const alvo = v / POR_CENTO;
    const atual = tamanhoDaSelecao(ids);
    // o limite vale para o tamanho de cada elemento: no grupo de tamanhos diferentes, o numero e relativo ao grupo e
    // a conta e a de cada um, mais abaixo (revisao 2 da fase D)
    if (atual !== null && (alvo < lim[0] * (1 - FOLGA_ESCALA) || alvo > lim[1] * (1 + FOLGA_ESCALA))) {
      errarTamanho(fraseDaFaixa() + ' Digite um número nesse intervalo.');
      return null;
    }
    const fator = alvo / (atual === null ? tamanhoDoGrupo(ids) : atual);
    if (atual === null) {
      // tamanhos diferentes: o numero e o tamanho do grupo desde que ele foi escolhido, e nenhum pode passar do limite
      const faixa = faixaDoFator(ids);
      if (fator < faixa[0] * (1 - FOLGA_ESCALA) || fator > faixa[1] * (1 + FOLGA_ESCALA)) {
        errarTamanho('Com esse número, um dos elementos escolhidos passaria do limite. ' + fraseDaFaixa());
        return null;
      }
    }
    campo.removeAttribute('aria-invalid');
    delete campo.dataset.sujo;
    if (Math.abs(fator - 1) <= FOLGA_ESCALA) {
      mostrarTamanho(ids);
      mensagem('O tamanho já é este.');
      return null;
    }
    ed.fraseTamanho = atual === null ?
      'Os elementos escolhidos têm tamanhos diferentes. Cada um ficou com ' + porcento(v) +
        '% do tamanho que tinha quando você escolheu o grupo.' :
      'O tamanho ficou em ' + porcento(v) + '% em todos os arquivos desta família. 100% é o tamanho antes das suas edições.';
    campo.value = porcento(v);
    const e = edicaoDe(ids, 'escalar');
    e.fator = fracao(fator);
    const p = pontoFixo(ids);
    if (p) { e.fx = p[0]; e.fy = p[1]; }
    return novaEdicao(e, false);
  }
  /* o campo mostra o tamanho dos escolhidos; o numero que o DA esta digitando fica ate ele aplicar ou trocar a escolha */
  function mostrarTamanho(ids) {
    const campo = campoTamanho();
    const aplicar = document.getElementById('ed-tamanho-aplicar');
    const chave = ids.join(' ');
    if (campo.dataset.escolha !== chave) { delete campo.dataset.sujo; campo.removeAttribute('aria-invalid'); }
    campo.dataset.escolha = chave;
    campo.disabled = !ids.length;
    aplicar.disabled = !ids.length;
    if (!ids.length) { campo.value = ''; campo.placeholder = ''; return; }
    const s = tamanhoDaSelecao(ids);
    campo.placeholder = '';
    campo.title = s === null ? FRASE_GRUPO_MISTO :
      'Digite o tamanho em porcentagem e aperte Enter ou Aplicar. 100% é o tamanho antes das suas edições.';
    if (!campo.dataset.sujo) campo.value = porcento((s === null ? tamanhoDoGrupo(ids) : s) * POR_CENTO);
  }
  /* M7b, D2: o elemento escolhido, ou o grupo, encosta na linha do quadro de cada arquivo da familia (a margem dele ou
     a area segura dele); o desdobra faz a conta em cada arquivo, e a previa volta com o resultado */
  function alinharNoQuadro(ids, alvo) {
    if (!ids || ![].concat(ids).length) return null;
    const e = edicaoDe(ids, 'alinhar');
    e.alvo = alvo;
    e.referencia = ed.referencia;
    ed.alinhou = { elemento: e.elemento, alvo: alvo, referencia: e.referencia };
    return novaEdicao(e, false);
  }
  /* depois da previa: a linha do quadro onde o bloco encostou fica no palco, e a tela diz o que aconteceu */
  function mostrarNoQuadro(area, r, pedido) {
    const g = mundos.get(area);
    if (!g) return;
    const feito = (r.no_quadro || []).find(function (a) {
      return a.formato === vista.formato && a.alvo === pedido.alvo && a.elementos.indexOf(pedido.elemento) >= 0;
    });
    if (!feito) return;
    const melhor = { x: null, y: null };
    melhor[feito.eixo] = { valor: feito.valor };
    guias(g, melhor, g.modelo);
    mensagem(FRASE_ALINHAR[pedido.alvo] + FRASE_REFERENCIA[pedido.referencia]);
  }
  function escolherReferencia(ref) {
    ed.referencia = ref;
    atualizarBarra();
  }
  function apagar(id) {
    ed.selecionado = null;
    ed.selecao = [];
    fecharControle();
    tirarQuebra(id); // o texto apagado nao tem mais linha para quebrar
    marcarQuebrasNoPalco();
    mostrarProposta();
    mensagem('O elemento saiu de todos os arquivos desta família. Desfazer traz de volta.');
    return novaEdicao({ elemento: id, acao: 'apagar' }, false);
  }
  function desfazer() {
    const f = familiaAtual();
    if (!f || !f.edicoes.length) return null;
    const desfeita = f.edicoes.pop();
    // o texto volta ao de antes: a quebra que contava no texto desfeito sai com ele
    if (desfeita.acao === 'texto') tirarQuebra(desfeita.elemento);
    f.confirmada = false;
    delete f.confirmacao;
    mensagem('A última edição foi desfeita.');
    mudouRascunho();
    atualizarBotaoFamilia();
    return pedirPrevia();
  }
  /* ------------------------------------------------ escolha, arraste e teclado no palco */
  function selecionarElemento(id) {
    ed.selecionado = id;
    ed.selecao = id ? [id] : [];
    fecharEditorTexto();
    // o controle da quebra aberto segue o texto escolhido, e fecha no elemento sem texto para quebrar
    if (controleAberto()) { if (id && textoDaQuebra(id)) desenharControle(null); else fecharControle(); }
    marcarSelecao();
    atualizarBarra();
  }
  /* M7b, D1: os escolhidos que estao no palco agora (o elemento apagado sai) e o grupo, com dois ou mais */
  function escolhidos() { return ed.selecao.filter(function (id) { return !!elementoDoPalco(id); }); }
  function emGrupo() { return escolhidos().length > 1; }
  function caixaDoGrupo(ids) {
    const cs = ids.map(function (id) { return elementoDoPalco(id).caixa; });
    return [Math.min.apply(null, cs.map(function (c) { return c[0]; })), Math.min.apply(null, cs.map(function (c) { return c[1]; })),
      Math.max.apply(null, cs.map(function (c) { return c[2]; })), Math.max.apply(null, cs.map(function (c) { return c[3]; }))];
  }
  /* o grupo muda de uma vez: Shift+clique, o modo "Escolher vários" ou o retangulo. Texto e quebra sao de um
     elemento so, entao o editor e o controle fecham com o grupo */
  function escolherVarios(ids) {
    ed.selecao = ids.slice();
    ed.selecionado = ids.length ? ids[ids.length - 1] : null;
    if (ids.length > 1) {
      fecharEditorTexto();
      fecharControle();
      ed.baseGrupo = null; // o grupo novo comeca em 100 no campo Tamanho
      mensagem('Os ' + ids.length + ' elementos escolhidos andam e mudam de tamanho juntos, em volta do mesmo ponto.' +
        (tamanhoDaSelecao(ids) === null ? ' ' + FRASE_GRUPO_MISTO : ''));
    }
    marcarSelecao();
    atualizarBarra();
  }
  function alternarNaSelecao(id) {
    const ids = escolhidos();
    const i = ids.indexOf(id);
    if (i >= 0) ids.splice(i, 1); else ids.push(id);
    escolherVarios(ids);
  }
  function alcas(no, lado) {
    [['nw', 0, 0], ['ne', 1, 0], ['sw', 0, 1], ['se', 1, 1]].forEach(function (c) {
      const a = el('span', null, 'alca');
      a.dataset.canto = c[0];
      a.setAttribute('aria-hidden', 'true');
      a.style.width = lado + 'px';
      a.style.height = lado + 'px';
      a.style.left = (c[1] * 100) + '%';
      a.style.top = (c[2] * 100) + '%';
      a.style.margin = (-lado / 2) + 'px 0 0 ' + (-lado / 2) + 'px';
      no.appendChild(a);
    });
  }
  function marcarSelecao() {
    const area = document.getElementById('palco');
    const g = mundos.get(area);
    area.querySelectorAll('.alca, .caixa-grupo').forEach(function (a) { a.remove(); });
    const ids = escolhidos();
    area.querySelectorAll('.rotulo.editavel').forEach(function (r) {
      const sim = ids.indexOf(r.dataset.elemento) >= 0;
      r.classList.toggle('selecionado', sim);
      r.classList.toggle('no-grupo', sim && ids.length > 1);
      r.setAttribute('aria-pressed', sim ? 'true' : 'false');
      if (sim && g && ids.length === 1) alcas(r, ALCA / g.k());
    });
    // o grupo: uma caixa so em volta dos escolhidos, com os cantos para mudar o tamanho de todos juntos
    if (g && ids.length > 1) {
      const caixa = el('div', null, 'caixa-grupo');
      caixa.setAttribute('aria-hidden', 'true');
      caixa.style.setProperty('--k', String(1 / (g.k() || 1))); // a linha fica com a mesma espessura na tela
      g.pos(caixa, caixaDoGrupo(ids));
      alcas(caixa, ALCA / g.k());
      g.mundo.appendChild(caixa);
    }
  }
  /* revisao 2 da fase D: a linha do nome cabe numa linha em qualquer janela; todos os gestos ficam na lista de
     "Como editar" (tela.html, #ed-ajuda-painel), que abre por cima do palco */
  const AJUDA_PALCO = 'Clique num elemento do palco para mexer nele. Os outros jeitos de editar estão em Como editar.';
  function abrirAjuda(abrir) {
    const painel = document.getElementById('ed-ajuda-painel');
    const botao = document.getElementById('ed-ajuda');
    painel.hidden = !abrir;
    botao.setAttribute('aria-expanded', abrir ? 'true' : 'false');
    if (abrir) document.getElementById('ed-ajuda-fechar').focus();
  }
  function atualizarBarra() {
    const ids = escolhidos();
    if (ed.selecionado && ids.indexOf(ed.selecionado) < 0) ed.selecionado = ids.length ? ids[ids.length - 1] : null;
    ed.selecao = ids;
    const e = ids.length === 1 ? elementoDoPalco(ids[0]) : null;
    const no = document.getElementById('elemento-escolhido');
    if (ids.length > 1) {
      // o grupo pelos nomes curtos, para caber inteiro numa linha (revisao 1 da fase D); o rotulo completo fica no
      // title e na etiqueta de cada um no palco
      no.textContent = 'Escolhidos juntos: ' + ids.length + ' elementos (' +
        ids.map(function (i) { return nomeCurto(elementoDoPalco(i)); }).join(', ') + ')';
      no.title = ids.map(function (i) { return rotuloElemento(elementoDoPalco(i)); }).join('; ');
    } else {
      no.textContent = e ? 'Escolhido: ' + rotuloElemento(e) : AJUDA_PALCO;
      no.title = no.textContent;
    }
    // Diminuir e Aumentar desligam no limite do tamanho; o campo Tamanho mostra o tamanho dos escolhidos (M7b, D3)
    const faixa = faixaDoFator(ids);
    document.getElementById('ed-diminuir').disabled = !ids.length || faixa[0] >= 1 - FATOR_IGUAL;
    document.getElementById('ed-aumentar').disabled = !ids.length || faixa[1] <= 1 + FATOR_IGUAL;
    mostrarTamanho(ids);
    // apagar, texto e quebra sao de um elemento so
    const botaoApagar = document.getElementById('ed-apagar');
    botaoApagar.disabled = !e;
    botaoApagar.title = ids.length > 1 ? APAGAR_SO_UM : '';
    document.getElementById('ed-texto').disabled = !e || pecasDeTexto(e.id).length !== 1;
    document.getElementById('ed-quebra').disabled = !e || !textoDaQuebra(e.id);
    document.getElementById('ed-desfazer').disabled = !edicoesDa().length;
    const varios = document.getElementById('ed-varios');
    varios.setAttribute('aria-pressed', ed.varios ? 'true' : 'false');
    // alinhar no quadro (M7b, D2) vale para o elemento ou para o grupo; a area segura so com area segura na folha
    Object.keys(ALINHAR).forEach(function (i) { document.getElementById(i).disabled = !ids.length; });
    const comSegura = !!(ed.previa && ed.previa.membros.some(function (x) { return x.quadro && x.quadro.area_segura; }));
    if (!comSegura && ed.referencia === 'area_segura') ed.referencia = 'margem';
    const segura = document.getElementById('ed-ref-segura');
    segura.disabled = !comSegura;
    segura.title = comSegura ? 'A área segura de cada arquivo da família, pela folha.' :
      'Os arquivos desta família não têm área segura na folha.';
    segura.setAttribute('aria-pressed', ed.referencia === 'area_segura' ? 'true' : 'false');
    document.getElementById('ed-ref-margem').setAttribute('aria-pressed', ed.referencia === 'margem' ? 'true' : 'false');
  }
  function nosDoElemento(area, id) {
    return Array.from(area.querySelectorAll('.recorte[data-elemento="' + id + '"], .rotulo[data-elemento="' + id + '"]'));
  }
  /* o encaixe leve do arraste: a borda ou o centro que encosta no de outro elemento de conteudo, a menos da
     tolerancia do motor; a linha discreta mostra onde. O motor alinha de novo depois de cada edicao (decisao 168),
     entao a previa do arraste mostra sempre o encaixe */
  function linhasDe(b) { return { x: [b[0], (b[0] + b[2]) / 2, b[2]], y: [b[1], (b[1] + b[3]) / 2, b[3]] }; }
  /* ids: o elemento ou o grupo que anda (c, a caixa que junta o grupo); os do grupo nao encaixam entre si */
  function encaixar(m, ids, c) {
    const tol = (estado.edicao ? estado.edicao.tolerancia_alinhamento : 0) * Math.max(m.largura, m.altura);
    const meu = linhasDe(c);
    const melhor = { x: null, y: null };
    m.elementos.forEach(function (o) {
      if (ids.indexOf(o.id) >= 0 || CONTEUDO.indexOf(o.funcao) < 0) return;
      const dele = linhasDe(o.caixa);
      ['x', 'y'].forEach(function (eixo) {
        for (let i = 0; i < 3; i++) {
          const d = dele[eixo][i] - meu[eixo][i];
          if (Math.abs(d) <= tol && (melhor[eixo] === null || Math.abs(d) < Math.abs(melhor[eixo].d))) {
            melhor[eixo] = { d: d, valor: dele[eixo][i] };
          }
        }
      });
    });
    return melhor;
  }
  function guias(g, melhor, m) {
    g.mundo.querySelectorAll('.guia').forEach(function (x) { x.remove(); });
    const meio = 0.5 / g.k();
    if (melhor.x) {
      const v = el('div', null, 'guia');
      g.pos(v, [melhor.x.valor - meio, 0, melhor.x.valor + meio, m.altura]);
      g.mundo.appendChild(v);
    }
    if (melhor.y) {
      const h = el('div', null, 'guia');
      g.pos(h, [0, melhor.y.valor - meio, m.largura, melhor.y.valor + meio]);
      g.mundo.appendChild(h);
    }
  }
  const FIXO = { nw: [1, 1], ne: [0, 1], sw: [1, 0], se: [0, 0] };
  /* o ponto da tela no mundo do palco (px da peca) */
  function noMundo(g, ev) {
    const r = g.mundo.getBoundingClientRect();
    const k = g.k();
    return [(ev.clientX - r.left) / k + g.x0, (ev.clientY - r.top) / k + g.y0];
  }
  /* o fundo da peca cobre o quadro inteiro: arrastar a partir dele, sem ele escolhido, desenha o retangulo de selecao
     (M7b, D1); o clique sem arrastar escolhe o fundo, e o fundo escolhido anda como os outros */
  function eDeFundo(id) { const e = elementoDoPalco(id); return !!e && e.funcao === 'fundo'; }
  function aoApertar(ev) {
    if (!editavel() || ev.button !== 0) return;
    const area = document.getElementById('palco');
    const g = mundos.get(area);
    if (!g) return;
    const alcaDoGrupo = ev.target.closest ? ev.target.closest('.caixa-grupo .alca') : null;
    const r = ev.target.closest ? ev.target.closest('.rotulo.editavel') : null;
    const somar = ev.shiftKey || ed.varios;
    // a etiqueta fica fora da caixa do elemento (revisao 1 da fase D): em cima dela, o elemento ainda nao escolhido
    // nao anda. O arraste desenha o retangulo, e o clique sem arrastar escolhe o elemento
    const naEtiqueta = !!(r && ev.target.closest('.etiqueta') && escolhidos().indexOf(r.dataset.elemento) < 0);
    if (!alcaDoGrupo && (!r || naEtiqueta || (eDeFundo(r.dataset.elemento) && escolhidos().indexOf(r.dataset.elemento) < 0))) {
      // o retangulo de selecao: no palco fora dos elementos, na etiqueta de um elemento ainda nao escolhido, ou a
      // partir do fundo ainda nao escolhido
      if (!area.querySelector('.rotulo.editavel')) return;
      ev.preventDefault();
      const p = noMundo(g, ev);
      const no = el('div', null, 'retangulo-selecao');
      no.setAttribute('aria-hidden', 'true');
      no.style.setProperty('--k', String(1 / (g.k() || 1)));
      g.pos(no, [p[0], p[1], p[0], p[1]]);
      g.mundo.appendChild(no);
      ed.arraste = { retangulo: true, inicio: p, no: no, g: g, x: ev.clientX, y: ev.clientY, somar: somar,
        fundo: r ? r.dataset.elemento : null, etiqueta: naEtiqueta };
      if (area.setPointerCapture) area.setPointerCapture(ev.pointerId);
      return;
    }
    ev.preventDefault();
    let canto = null;
    let ids;
    let tirar = null;
    if (alcaDoGrupo) {
      ids = escolhidos();
      canto = alcaDoGrupo.dataset.canto;
    } else {
      const id = r.dataset.elemento;
      if (somar && escolhidos().indexOf(id) < 0) {
        // Shift+clique ou "Escolher vários": o elemento entra no grupo, sem arrastar
        alternarNaSelecao(id);
        r.focus();
        return;
      }
      // o escolhido, com Shift ou "Escolher vários": arrastar leva o grupo, e o clique sem arrastar o tira do grupo
      // (revisao 1 da fase D: o modo ligado nunca impede de arrastar o grupo)
      tirar = somar ? id : null;
      if (escolhidos().indexOf(id) < 0) selecionarElemento(id);
      r.focus();
      const alca = ev.target.closest('.alca');
      canto = alca ? alca.dataset.canto : null;
      ids = escolhidos().length > 1 ? escolhidos() : [id];
    }
    // a caixa que junta o grupo (a do elemento, quando ele esta so) da o ponto fixo do canto
    const c = caixaDoGrupo(ids);
    const fx = canto ? FIXO[canto] : null;
    let nos = [];
    ids.forEach(function (i) { nos = nos.concat(nosDoElemento(area, i)); });
    nos = nos.concat(Array.from(area.querySelectorAll('.caixa-grupo')));
    ed.arraste = { id: ids[0], ids: ids, canto: canto, x: ev.clientX, y: ev.clientY, k: g.k(), g: g, m: g.modelo,
      fixo: fx ? [c[0] + fx[0] * (c[2] - c[0]), c[1] + fx[1] * (c[3] - c[1])] : null,
      movel: fx ? [c[0] + (1 - fx[0]) * (c[2] - c[0]), c[1] + (1 - fx[1]) * (c[3] - c[1])] : null,
      caixa: c, nos: nos, dx: 0, dy: 0, f: 1, faixa: faixaDoFator(ids),
      clicado: alcaDoGrupo || canto ? null : r.dataset.elemento, tirar: canto ? null : tirar };
    const alvo = alcaDoGrupo || r;
    if (alvo.setPointerCapture) alvo.setPointerCapture(ev.pointerId);
    nos.forEach(function (n) { if (n.classList.contains('rotulo')) n.classList.add('arrastando'); });
  }
  function moverRetangulo(a, ev) {
    const p = noMundo(a.g, ev);
    const c = [Math.min(a.inicio[0], p[0]), Math.min(a.inicio[1], p[1]), Math.max(a.inicio[0], p[0]), Math.max(a.inicio[1], p[1])];
    a.g.pos(a.no, c);
    a.caixa = c;
  }
  /* o retangulo escolhe os elementos que ficam inteiros dentro dele (o fundo, maior que o quadro, fica de fora);
     com Shift ou "Escolher vários", eles entram no grupo que ja estava escolhido */
  function soltarRetangulo(a, ev) {
    a.no.remove();
    const pequeno = Math.abs(ev.clientX - a.x) + Math.abs(ev.clientY - a.y) < RETANGULO_MIN_PX;
    if (pequeno || !a.caixa) {
      // o clique na etiqueta, ou no fundo, escolhe o elemento dela
      if (a.fundo) { if (a.somar) alternarNaSelecao(a.fundo); else selecionarElemento(a.fundo); }
      else if (!a.somar) selecionarElemento(null);
      const dele = a.etiqueta ? document.querySelector('#palco .rotulo[data-elemento="' + a.fundo + '"]') : null;
      if (dele) dele.focus();
      return;
    }
    const c = a.caixa;
    const dentro = a.g.modelo.elementos.filter(function (e) {
      const b = e.caixa;
      return b[0] >= c[0] && b[1] >= c[1] && b[2] <= c[2] && b[3] <= c[3];
    }).map(function (e) { return e.id; });
    const ids = a.somar ? escolhidos() : [];
    dentro.forEach(function (i) { if (ids.indexOf(i) < 0) ids.push(i); });
    if (ids.length === 1) selecionarElemento(ids[0]); else escolherVarios(ids);
    if (!ids.length) mensagem('O retângulo não pegou nenhum elemento inteiro. Desenhe em volta dos elementos que quer escolher.');
    const primeiro = ids.length ? document.querySelector('#palco .rotulo[data-elemento="' + ids[ids.length - 1] + '"]') : null;
    if (primeiro) primeiro.focus();
  }
  function aoMover(ev) {
    const a = ed.arraste;
    if (!a) return;
    if (a.retangulo) { moverRetangulo(a, ev); return; }
    let dx = (ev.clientX - a.x) / a.k;
    let dy = (ev.clientY - a.y) / a.k;
    if (!a.canto) {
      const c = a.caixa;
      const melhor = encaixar(a.m, a.ids, [c[0] + dx, c[1] + dy, c[2] + dx, c[3] + dy]);
      if (melhor.x) dx += melhor.x.d;
      if (melhor.y) dy += melhor.y.d;
      guias(a.g, melhor, a.m);
      a.dx = dx;
      a.dy = dy;
      a.nos.forEach(function (n) { n.style.transform = 'translate(' + dx + 'px,' + dy + 'px)'; });
      return;
    }
    const v = [a.movel[0] - a.fixo[0], a.movel[1] - a.fixo[1]];
    const p = [v[0] + dx, v[1] + dy];
    // o canto para no limite do tamanho de cada escolhido (M7b, D3)
    a.f = Math.min(a.faixa[1], Math.max(ESCALA_MIN, a.faixa[0],
      (p[0] * v[0] + p[1] * v[1]) / ((v[0] * v[0] + v[1] * v[1]) || 1)));
    a.nos.forEach(function (n) {
      n.style.transformOrigin = (a.fixo[0] - a.g.x0 - parseFloat(n.style.left)) + 'px ' +
        (a.fixo[1] - a.g.y0 - parseFloat(n.style.top)) + 'px';
      n.style.transform = 'scale(' + a.f + ')';
    });
  }
  function aoSoltar(ev) {
    const a = ed.arraste;
    if (!a) return;
    ed.arraste = null;
    if (a.retangulo) { soltarRetangulo(a, ev); return; }
    a.g.mundo.querySelectorAll('.guia').forEach(function (x) { x.remove(); });
    // depois da previa, o foco volta ao escolhido: as setas seguem mexendo no mesmo elemento ou grupo
    ed.focar = true;
    if (!a.canto && Math.abs(a.dx) + Math.abs(a.dy) >= MEIO_PX) { moverPor(a.ids, a.dx, a.dy, false); return; }
    if (a.canto && Math.abs(a.f - 1) > FATOR_IGUAL) { escalarPor(a.ids, a.f, FIXO[a.canto][0], FIXO[a.canto][1]); return; }
    ed.focar = false;
    a.nos.forEach(function (n) { n.style.transform = ''; n.classList.remove('arrastando'); });
    // com Shift ou "Escolher vários", o clique sem arrastar tira o elemento do grupo
    if (a.tirar) { alternarNaSelecao(a.tirar); return; }
    // o clique sem arrastar num elemento do grupo escolhe so ele (arrastar leva o grupo)
    if (a.clicado && a.ids.length > 1) selecionarElemento(a.clicado);
  }
  /* o que a seta e o + e - mexem: o grupo escolhido quando o elemento com o foco esta nele, senao o elemento */
  function doTeclado(id) {
    const ids = escolhidos();
    if (ids.length > 1 && ids.indexOf(id) >= 0) return ids;
    if (ed.selecionado !== id || ids.length !== 1) selecionarElemento(id);
    return [id];
  }
  function aoTeclar(ev) {
    const r = ev.target.closest ? ev.target.closest('.rotulo.editavel') : null;
    if (!r || !editavel()) return;
    const id = r.dataset.elemento;
    const passo = ev.shiftKey ? PASSO_SETA_LONGO : PASSO_SETA;
    const setas = { ArrowLeft: [-passo, 0], ArrowRight: [passo, 0], ArrowUp: [0, -passo], ArrowDown: [0, passo] };
    if (ev.key === 'Enter' || ev.key === ' ') {
      ev.preventDefault();
      if (ev.shiftKey || ed.varios) alternarNaSelecao(id); else selecionarElemento(id);
      r.focus();
      return;
    }
    if (ev.key === 'Escape') { selecionarElemento(null); return; }
    if (setas[ev.key]) {
      ev.preventDefault();
      const ids = doTeclado(id);
      const agora = Date.now();
      const juntar = agora - ed.tecla < JUNTAR_TECLAS_MS;
      ed.tecla = agora;
      ed.focar = true;
      moverPor(ids, setas[ev.key][0], setas[ev.key][1], juntar);
      return;
    }
    if (ev.key === '+' || ev.key === '=' || ev.key === '-') {
      ev.preventDefault();
      const ids = doTeclado(id);
      ed.focar = true;
      escalarNoLugar(ids, ev.key === '-' ? 1 / FATOR_TECLA : FATOR_TECLA);
      return;
    }
    if (ev.key !== 'Delete' && ev.key !== 'Backspace') return;
    ev.preventDefault();
    // apagar e de um elemento so: com o grupo escolhido, a tecla nao apaga ninguem do grupo, e a tela diz por que
    if (emGrupo() && escolhidos().indexOf(id) >= 0) { mensagem(APAGAR_SO_UM); return; }
    apagar(id);
  }
  /* ------------------------------------------------ texto (decisoes 169 e 171) */
  function abrirEditorTexto() {
    const ps = ed.selecionado ? pecasDeTexto(ed.selecionado) : [];
    if (ps.length !== 1) return;
    fecharControle();
    const campo = document.getElementById('ed-campo-texto');
    campo.value = ps[0].linhas.map(function (ln) {
      return ln.trechos.map(function (t) { return t.texto; }).join('');
    }).join('\n');
    campo.removeAttribute('aria-invalid');
    document.getElementById('ed-erro-texto').textContent = '';
    document.getElementById('editor-texto').hidden = false;
    document.querySelector('.mesa-palco').classList.add('escrevendo');
    campo.focus();
  }
  function fecharEditorTexto() {
    const no = document.getElementById('editor-texto');
    if (no) no.hidden = true;
    const mesa = document.querySelector('.mesa-palco');
    if (mesa) mesa.classList.remove('escrevendo');
  }
  function aplicarTexto() {
    const id = ed.selecionado;
    const campo = document.getElementById('ed-campo-texto');
    const erro = document.getElementById('ed-erro-texto');
    if (!id) return null;
    if (!campo.value.trim()) {
      erro.textContent = 'O texto ficou vazio. Para tirar o elemento, use Apagar.';
      campo.setAttribute('aria-invalid', 'true');
      return null;
    }
    erro.textContent = '';
    campo.removeAttribute('aria-invalid');
    const f = familiaAtual();
    f.edicoes = f.edicoes.filter(function (e) { return !(e.acao === 'texto' && e.elemento === id); });
    // as posicoes da quebra contam no texto de antes: a quebra deste texto sai, e a tela olha o texto novo de novo
    tirarQuebra(id);
    ed.textoPendente = id;
    return novaEdicao({ elemento: id, acao: 'texto', texto: campo.value.replace(/\r\n?/g, '\n') }, false);
  }

  /* ------------------------------------------------ quebra de linha (M7b, C4; decisoes 167 e 171)
     Com um texto escolhido, "Quebrar linha" abre o controle embaixo do palco: o texto de agora (o do KV ou o editado
     nesta familia), nas linhas de agora e com a fonte do job. O clique entre duas palavras poe a quebra ali, e o
     clique na marca da quebra junta as linhas. A quebra vale para a familia inteira, como o texto editado, e fica no
     rascunho (quebras, uma por texto), aprovada pelo proprio clique do DA. A previa dos membros espera 300 ms sem
     clique (pedirPreviaDaQuebra). O texto editado que nao cabe na caixa quebra na largura dela, como no render: a tela
     le onde o Chromium quebrou e grava a quebra como proposta do desdobra, marcada no palco ate o DA aprovar com um
     clique ou mudar a quebra. "Confirmar familia" espera a aprovacao (o servidor recusa tambem). As posicoes vem do
     motor (textos_da_quebra da previa); o texto do cliente entra so por textContent. */
  const QUEBRA_UMA = 'O texto editado não coube na caixa. O desdobra quebrou a linha na largura dela. Aprove a quebra ou mude a quebra antes de confirmar a família.';
  const QUEBRA_FALTA_UMA = 'Uma quebra de linha proposta pelo desdobra espera a sua aprovação.';
  const QUEBRA_SEM_APROVAR = 'Aprove a quebra de linha proposta pelo desdobra, ou mude a quebra, antes de confirmar a família.';
  const FAMILIA_ESPERA_PREVIA = 'Espere a família aparecer com a sua última mudança.';
  const FAMILIA_SEM_GRAVAR = 'A sua última mudança ainda não foi salva no rascunho. Espere o desdobra salvar.';
  const MARCA_QUEBRA = 'quebra proposta';
  const SITUACAO_QUEBRA = {
    kv: 'As quebras são as do KV.',
    editado: 'As linhas são as que você escreveu.',
    da: 'Esta quebra é sua e vale para todos os arquivos desta família.',
    proposta: 'O desdobra propôs esta quebra. Aprove a quebra ou mude a quebra.',
    aprovada: 'Você aprovou a quebra proposta pelo desdobra. Ela vale para todos os arquivos desta família.'
  };
  function textosDaQuebra() { return (ed.previa && ed.previa.textos_da_quebra) || []; }
  function textoDaQuebra(id) {
    return textosDaQuebra().find(function (t) { return t.elemento === id; }) || null;
  }
  function quebrasDa(gid) { const f = rascunho.familias[gid]; return (f && f.quebras) || []; }
  function quebraDo(id) { return quebrasDa(vista.familia).find(function (q) { return q.elemento === id; }) || null; }
  function porAprovar(gid) {
    return quebrasDa(gid).filter(function (q) { return q.origem === 'proposta' && !q.aprovada; });
  }
  function emOrdem(s) { return Array.from(s).sort(function (a, b) { return a - b; }); }
  function todasGravadas(t) { return t.gravadas.map(function (_p, k) { return k; }); }
  /* tira a quebra do texto sem gravar: quem chama grava (a edicao de texto, apagar, desfazer) */
  function tirarQuebra(id) {
    const f = rascunho.familias[vista.familia];
    if (!f || !f.quebras) return;
    f.quebras = f.quebras.filter(function (q) { return q.elemento !== id; });
    if (!f.quebras.length) delete f.quebras;
  }
  /* a quebra nova do texto (ou nenhuma) e edicao da familia: tira a confirmacao e vai ao rascunho */
  function guardarQuebra(id, q) {
    const f = familiaAtual();
    tirarQuebra(id);
    if (q) f.quebras = (f.quebras || []).concat([q]);
    if (temGaleria()) f.versao = versaoDaFamilia();
    f.confirmada = false;
    delete f.confirmacao;
    mudouRascunho();
    atualizarBotaoFamilia();
    atualizarFaltam();
    marcarQuebrasNoPalco();
    mostrarProposta();
  }
  /* as quebras que valem agora no texto: as gravadas que ficam e as inseridas */
  function quebrasAtivas(t, q) {
    const s = new Set();
    t.gravadas.forEach(function (p, k) { if (!q || q.manter.indexOf(k) >= 0) s.add(p); });
    if (q) q.inseridas.forEach(function (p) { s.add(p); });
    return s;
  }
  function trocarQuebra(id, pos) {
    const t = textoDaQuebra(id);
    if (!t) return;
    const q = quebraDo(id);
    const manter = new Set(q ? q.manter : todasGravadas(t));
    const inseridas = new Set(q ? q.inseridas : []);
    const k = t.gravadas.indexOf(pos);
    const lista = k >= 0 ? manter : inseridas;
    const valor = k >= 0 ? k : pos;
    if (k < 0 && t.espacos.indexOf(pos) < 0) return;
    if (lista.has(valor)) lista.delete(valor); else lista.add(valor);
    const novo = { elemento: id, layer_id: t.layer_id, manter: emOrdem(manter), inseridas: emOrdem(inseridas),
      origem: 'da', aprovada: true };
    // de volta as quebras do KV, a quebra sai do rascunho; no texto editado ela fica, para a tela nao propor de novo
    const comoNoKv = !novo.inseridas.length && novo.manter.length === t.gravadas.length;
    guardarQuebra(id, comoNoKv && !t.editado ? null : novo);
    contarNoCronometro('quebras');
    desenharControle(pos);
    pedirPreviaDaQuebra();
  }
  function controleAberto() { return !document.getElementById('editor-quebra').hidden; }
  /* com o controle aberto, o palco fica com o espaco (revisao do C): .quebrando tira as miniaturas da frente, como
     no editor de texto, e o resumo da familia fica; a frase da ultima acao sai, e o controle diz a situacao */
  function abrirControle() {
    if (!ed.selecionado || !textoDaQuebra(ed.selecionado)) return;
    fecharEditorTexto();
    mensagem('');
    document.getElementById('editor-quebra').hidden = false;
    document.querySelector('.mesa-palco').classList.add('quebrando');
    document.getElementById('ed-quebra').setAttribute('aria-pressed', 'true');
    desenharControle(null);
    const primeiro = document.querySelector('#quebra-linhas button');
    if (primeiro) primeiro.focus();
  }
  function fecharControle() {
    const no = document.getElementById('editor-quebra');
    if (no) no.hidden = true;
    const mesa = document.querySelector('.mesa-palco');
    if (mesa) mesa.classList.remove('quebrando');
    const b = document.getElementById('ed-quebra');
    if (b) b.setAttribute('aria-pressed', 'false');
    if (document.getElementById('quebra-proposta')) mostrarProposta();
  }
  function botaoDaQuebra(pos, classe, rotulo) {
    const b = botao(null, classe);
    b.dataset.pos = String(pos);
    b.setAttribute('aria-label', rotulo);
    b.title = rotulo;
    b.addEventListener('click', function () { trocarQuebra(ed.selecionado, pos); });
    return b;
  }
  function marcaDaQuebra(pos, tipo) {
    const b = botaoDaQuebra(pos, 'quebra-marca' + (tipo ? ' ' + tipo : ''), 'Juntar com a linha de baixo');
    const svg = noSvg('svg', { viewBox: '0 0 16 16', width: '14', height: '14', 'aria-hidden': 'true', focusable: 'false' });
    svg.appendChild(noSvg('path', { d: 'M12.5 3.5v5a2 2 0 0 1-2 2h-7M6 8l-2.5 2.5L6 13', fill: 'none',
      stroke: 'currentColor', 'stroke-width': '1.5', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }));
    b.appendChild(svg);
    return b;
  }
  /* o texto em linhas, com o vao entre as palavras e a marca no fim de cada linha quebrada: a do KV discreta, a do DA
     no acento e a proposta do desdobra tracejada. foco: a posicao do botao que fica com o foco depois */
  function desenharControle(foco) {
    const caixa = document.getElementById('quebra-linhas');
    const t = ed.selecionado ? textoDaQuebra(ed.selecionado) : null;
    if (!t) { fecharControle(); return; }
    const tinhaFoco = caixa.contains(document.activeElement);
    const q = quebraDo(t.elemento);
    const ativas = quebrasAtivas(t, q);
    const propostas = new Set(q && q.origem === 'proposta' && !q.aprovada ? q.inseridas : []);
    const separa = new Set(t.gravadas.concat(t.espacos));
    limpar(caixa);
    const p = pecasDeTexto(t.elemento)[0];
    const tr0 = p && p.linhas[0] && p.linhas[0].trechos[0];
    caixa.style.fontFamily = tr0 && tr0.face && familiaCss.has(tr0.face) ? '"' + familiaCss.get(tr0.face) + '"' : '';
    let linha = el('div', null, 'quebra-linha');
    let palavra = '';
    let n = 0;
    function fecharPalavra() { linha.appendChild(el('span', palavra, 'trecho quebra-palavra')); palavra = ''; n += 1; }
    for (let i = 0; i < t.texto.length; i++) {
      if (!separa.has(i)) { palavra += t.texto[i]; continue; }
      fecharPalavra();
      if (ativas.has(i)) {
        const tipo = propostas.has(i) ? 'proposta' : (t.gravadas.indexOf(i) >= 0 && !t.editado ? 'do-kv' : '');
        linha.appendChild(marcaDaQuebra(i, tipo));
        caixa.appendChild(linha);
        linha = el('div', null, 'quebra-linha');
      } else {
        linha.appendChild(botaoDaQuebra(i, 'quebra-vao', 'Quebrar a linha depois da palavra ' + n));
      }
    }
    fecharPalavra();
    caixa.appendChild(linha);
    let situacao = t.editado ? 'editado' : 'kv';
    if (q) situacao = q.origem === 'da' ? 'da' : (q.aprovada ? 'aprovada' : 'proposta');
    document.getElementById('quebra-situacao').textContent = SITUACAO_QUEBRA[situacao];
    const volta = document.getElementById('ed-quebra-kv');
    volta.hidden = !q;
    volta.textContent = t.editado ? 'Voltar às linhas do texto' : 'Voltar às quebras do KV';
    // a proposta deste texto se aprova aqui mesmo; a faixa de cima sai quando so ela esperava (mostrarProposta)
    document.getElementById('ed-quebra-aprovar').hidden = situacao !== 'proposta';
    mostrarProposta();
    if (tinhaFoco && foco !== null && foco !== undefined) {
      const alvo = caixa.querySelector('button[data-pos="' + foco + '"]');
      if (alvo) alvo.focus();
    }
  }
  /* as linhas do texto de agora com a quebra da familia q (ou sem ela), como o motor as manda ao palco
     (desdobra.derivacao.quebras.linhas_do_editado): a quebra gravada fora de manter vira espaco e o espaco inserido
     vira quebra. Cada linha leva a posicao do texto onde ela comeca */
  function linhasComQuebra(t, q) {
    const juntar = new Set();
    const novas = new Set(q ? q.inseridas : []);
    if (q) t.gravadas.forEach(function (p, k) { if (q.manter.indexOf(k) < 0) juntar.add(p); });
    const linhas = [];
    let atual = '';
    let inicio = 0;
    for (let i = 0; i < t.texto.length; i++) {
      const quebra = (t.gravadas.indexOf(i) >= 0 && !juntar.has(i)) || (novas.has(i) && t.texto[i] === ' ');
      if (quebra) {
        linhas.push({ texto: atual, inicio: inicio });
        atual = '';
        inicio = i + 1;
      } else {
        atual += juntar.has(i) ? ' ' : t.texto[i];
      }
    }
    linhas.push({ texto: atual, inicio: inicio });
    return linhas;
  }
  /* onde o Chromium quebrou o texto editado na largura da caixa: a posicao do espaco antes de cada palavra que desceu
     de linha, no texto de agora (o espaco, ou a quebra gravada que o DA juntou). So com o palco desenhado com a
     quebra q de agora, linha a linha como o motor o mandou; o palco de um pedido anterior da null */
  function quebrasDaLargura(no, t, q) {
    const linhas = linhasComQuebra(t, q);
    const nos = Array.from(no.querySelectorAll('.linha'));
    if (nos.length !== linhas.length) return null;
    const r = document.createRange();
    const saida = [];
    for (let i = 0; i < linhas.length; i++) {
      const parte = linhas[i].texto;
      const s = nos[i].querySelector('.trecho');
      const tn = s ? s.firstChild : null;
      if (!parte) continue;
      if (!tn || tn.nodeType !== 3 || tn.data !== parte) return null;
      let topo = null;
      for (let k = 0; k < parte.length; k++) {
        if (parte[k] === ' ' || (k > 0 && parte[k - 1] !== ' ')) continue;
        r.setStart(tn, k);
        r.setEnd(tn, k + 1);
        const c = r.getClientRects()[0];
        if (!c) continue;
        const pos = linhas[i].inicio + k - 1;
        const cabe = t.espacos.indexOf(pos) >= 0 || t.gravadas.indexOf(pos) >= 0;
        if (topo !== null && c.top > topo + c.height / 2 && cabe) saida.push(pos);
        topo = c.top;
      }
    }
    return saida;
  }
  /* o texto editado que quebrou na largura da caixa vira a quebra proposta pelo desdobra, com as quebras que ja
     valiam. Tambem quando o DA juntou ou aprovou as linhas e uma delas ainda nao cabe: o render quebra ali do mesmo
     jeito, e essa quebra volta marcada ate o DA aprovar ou mudar (revisao do C). Abrir a familia confirmada nao
     propoe: a confirmacao e do DA, e so cai quando ele mexe na familia */
  const QUEBRA_DE_NOVO = 'Uma linha não coube na caixa. O desdobra quebrou a linha de novo na largura dela. Aprove a quebra ou mude a quebra.';
  function proporQuebras() {
    if (!editavel() || familiaConfirmada()) return false;
    const area = document.getElementById('palco');
    let propos = false;
    let deNovo = false;
    textosDaQuebra().forEach(function (t) {
      if (!t.editado) return;
      const q = quebraDo(t.elemento);
      const no = area.querySelector('.recorte[data-elemento="' + t.elemento + '"] .texto.editado');
      const pos = no ? quebrasDaLargura(no, t, q) : null;
      if (!pos || !pos.length) return;
      const manter = new Set(q ? q.manter : todasGravadas(t));
      const inseridas = new Set(q ? q.inseridas : []);
      pos.forEach(function (p) {
        const k = t.gravadas.indexOf(p);
        if (k >= 0) manter.add(k); else inseridas.add(p);
      });
      const novo = { elemento: t.elemento, layer_id: t.layer_id, manter: emOrdem(manter), inseridas: emOrdem(inseridas),
        origem: 'proposta', aprovada: false };
      if (q && JSON.stringify([q.manter, q.inseridas]) === JSON.stringify([novo.manter, novo.inseridas])) return;
      guardarQuebra(t.elemento, novo);
      propos = true;
      if (q) deNovo = true;
    });
    if (deNovo) mensagem(QUEBRA_DE_NOVO);
    return propos;
  }
  function aprovarQuebra() {
    const lista = porAprovar(vista.familia);
    const q = lista.find(function (x) { return x.elemento === ed.selecionado; }) || lista[0];
    if (!q) return;
    guardarQuebra(q.elemento, Object.assign({}, q, { aprovada: true }));
    mensagem('A quebra proposta pelo desdobra está aprovada. Ela vale para todos os arquivos desta família.');
    if (controleAberto()) desenharControle(null);
  }
  function verQuebraProposta() {
    const q = porAprovar(vista.familia)[0];
    if (!q) return;
    selecionarElemento(q.elemento);
    abrirControle();
  }
  /* a faixa da quebra proposta, acima da barra, e a marca no palco no elemento dela. Com o controle aberto no texto
     da unica proposta, a faixa sai: o controle diz o mesmo e tem o "Aprovar quebra" */
  function mostrarProposta() {
    const no = document.getElementById('quebra-proposta');
    const lista = editavel() ? porAprovar(vista.familia) : [];
    const n = lista.length;
    const noControle = controleAberto() && lista.every(function (q) { return q.elemento === ed.selecionado; });
    no.hidden = !n || noControle;
    document.getElementById('quebra-proposta-texto').textContent = n === 1 ? QUEBRA_UMA :
      'O desdobra propôs ' + n + ' quebras de linha nesta família. Aprove cada quebra ou mude a quebra antes de confirmar a família.';
  }
  function marcarQuebrasNoPalco() {
    const area = document.getElementById('palco');
    const pendentes = new Set((editavel() ? porAprovar(vista.familia) : []).map(function (q) { return q.elemento; }));
    area.querySelectorAll('.rotulo.editavel').forEach(function (r) {
      const sim = pendentes.has(r.dataset.elemento);
      const e = elementoDoPalco(r.dataset.elemento);
      const et = r.querySelector('.etiqueta');
      if (r.classList.contains('quebra-proposta') === sim || !e) return;
      r.classList.toggle('quebra-proposta', sim);
      const rotulo = rotuloElemento(e) + (sim ? ' · ' + MARCA_QUEBRA : '');
      r.setAttribute('aria-label', 'Mexer em ' + rotulo);
      if (et) et.textContent = rotulo;
    });
    reajustar(area);
  }
  /* o que falta: a familia com quebra proposta ainda sem aprovacao leva a ela */
  function pendenciasDasQuebras() {
    const out = [];
    (estado.orientacoes || []).forEach(function (o) {
      o.grupos.forEach(function (g) {
        const n = porAprovar(g.id).length;
        const fs = formatosDoGrupo(g);
        if (!n || !fs.length) return;
        out.push({ texto: n === 1 ? QUEBRA_FALTA_UMA : n + ' quebras de linha propostas pelo desdobra esperam a sua aprovação.',
          detalhe: fs.map(function (x) { return x.id; }).join(', '), ir: { passo: 'pecas', formato: fs[0].id } });
      });
    });
    return out;
  }
  function ligarEdicao() {
    const area = document.getElementById('palco');
    area.addEventListener('pointerdown', aoApertar);
    area.addEventListener('pointermove', aoMover);
    area.addEventListener('pointerup', aoSoltar);
    area.addEventListener('pointercancel', aoSoltar);
    area.addEventListener('keydown', aoTeclar);
    // Ctrl+Z (Cmd+Z no Mac) desfaz a ultima edicao da familia, fora dos campos de texto
    document.addEventListener('keydown', function (ev) {
      if (!(ev.ctrlKey || ev.metaKey) || ev.shiftKey || ev.altKey || String(ev.key).toLowerCase() !== 'z') return;
      const t = ev.target;
      if (t && (t.tagName === 'TEXTAREA' || t.tagName === 'INPUT' || t.isContentEditable)) return;
      if (!editavel() || !edicoesDa().length) return;
      ev.preventDefault();
      desfazer();
    });
    document.getElementById('ed-campo-texto').addEventListener('keydown', function (ev) {
      if (ev.key !== 'Escape') return;
      ev.preventDefault();
      ev.stopPropagation();
      fecharEditorTexto();
      const r = ed.selecionado ? document.querySelector('#palco .rotulo[data-elemento="' + ed.selecionado + '"]') : null;
      if (r && r.focus) r.focus();
    });
    // a barra, o editor de texto e as miniaturas mudam a altura do palco: ele volta a Ajustar no espaco novo
    if (window.ResizeObserver) {
      let quadro = null;
      new ResizeObserver(function () {
        cancelAnimationFrame(quadro);
        quadro = requestAnimationFrame(function () { reajustar(area); });
      }).observe(area);
    }
    // Diminuir e Aumentar mudam o tamanho do elemento escolhido, ou do grupo inteiro em volta do meio dele (M7b, D1)
    // depois da previa, o foco volta ao escolhido: as setas e Esc seguem valendo (revisao 1 da fase D)
    document.getElementById('ed-diminuir').addEventListener('click', function () {
      ed.focar = true;
      escalarNoLugar(escolhidos(), 1 / FATOR_TECLA);
    });
    document.getElementById('ed-aumentar').addEventListener('click', function () {
      ed.focar = true;
      escalarNoLugar(escolhidos(), FATOR_TECLA);
    });
    // o tamanho por numero (M7b, D3): Enter ou Aplicar gravam; Esc volta ao tamanho de agora
    const campoT = campoTamanho();
    campoT.addEventListener('input', function () {
      campoT.dataset.sujo = '1';
      campoT.removeAttribute('aria-invalid');
    });
    campoT.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter') { ev.preventDefault(); aplicarTamanho(); return; }
      // Ctrl+Z com o campo mostrando o tamanho de agora (nada digitado) desfaz a ultima edicao, como no palco; com um
      // numero sendo digitado, desfaz a digitacao (revisao 2 da fase D)
      if ((ev.ctrlKey || ev.metaKey) && !ev.shiftKey && !ev.altKey && String(ev.key).toLowerCase() === 'z' &&
          !campoT.dataset.sujo) {
        ev.preventDefault();
        if (editavel() && edicoesDa().length) desfazer();
        return;
      }
      if (ev.key !== 'Escape') return;
      ev.preventDefault();
      ev.stopPropagation();
      delete campoT.dataset.sujo;
      campoT.removeAttribute('aria-invalid');
      mostrarTamanho(escolhidos());
    });
    document.getElementById('ed-tamanho-aplicar').addEventListener('click', aplicarTamanho);
    // "Escolher vários": com o botao ligado, cada clique num elemento poe ou tira ele do grupo, como Shift+clique
    document.getElementById('ed-varios').addEventListener('click', function () {
      ed.varios = !ed.varios;
      mensagem(ed.varios ? 'Clique nos elementos que vão andar juntos. Clique de novo para tirar um deles.' : '');
      atualizarBarra();
    });
    // alinhar no quadro (M7b, D2): um clique, para o elemento escolhido ou o grupo; a referencia vale ate mudar
    Object.keys(ALINHAR).forEach(function (i) {
      document.getElementById(i).addEventListener('click', function () {
        ed.focar = true;
        alinharNoQuadro(escolhidos(), ALINHAR[i]);
      });
    });
    document.getElementById('ed-ref-margem').addEventListener('click', function () { escolherReferencia('margem'); });
    document.getElementById('ed-ref-segura').addEventListener('click', function () { escolherReferencia('area_segura'); });
    document.getElementById('ed-apagar').addEventListener('click', function () { apagar(ed.selecionado); });
    // depois de Desfazer, o foco volta ao escolhido: as setas e Esc seguem valendo (revisao 2 da fase D)
    document.getElementById('ed-desfazer').addEventListener('click', function () {
      ed.focar = true;
      desfazer();
    });
    // "Como editar" (revisao 2 da fase D): a lista dos gestos abre e fecha pelo botao, por Fechar e por Esc
    document.getElementById('ed-ajuda').addEventListener('click', function () {
      abrirAjuda(document.getElementById('ed-ajuda-painel').hidden);
    });
    document.getElementById('ed-ajuda-fechar').addEventListener('click', function () {
      abrirAjuda(false);
      document.getElementById('ed-ajuda').focus();
    });
    document.addEventListener('keydown', function (ev) {
      if (ev.key !== 'Escape' || document.getElementById('ed-ajuda-painel').hidden) return;
      ev.preventDefault();
      ev.stopPropagation();
      abrirAjuda(false);
      document.getElementById('ed-ajuda').focus();
    }, true);
    document.getElementById('ed-texto').addEventListener('click', abrirEditorTexto);
    document.getElementById('ed-texto-cancelar').addEventListener('click', function () {
      fecharEditorTexto();
      document.getElementById('ed-texto').focus();
    });
    document.getElementById('ed-texto-aplicar').addEventListener('click', aplicarTexto);
    // a quebra de linha (M7b, C4): o botao da barra abre e fecha o controle; Esc fecha e volta ao elemento
    document.getElementById('ed-quebra').addEventListener('click', function () {
      if (controleAberto()) fecharControle(); else abrirControle();
    });
    document.getElementById('ed-quebra-fechar').addEventListener('click', function () {
      fecharControle();
      document.getElementById('ed-quebra').focus();
    });
    document.getElementById('ed-quebra-kv').addEventListener('click', function () {
      const id = ed.selecionado;
      if (!id || !quebraDo(id)) return;
      guardarQuebra(id, null);
      contarNoCronometro('quebras');
      desenharControle(null);
      pedirPreviaDaQuebra();
    });
    document.getElementById('editor-quebra').addEventListener('keydown', function (ev) {
      if (ev.key !== 'Escape') return;
      ev.preventDefault();
      ev.stopPropagation();
      fecharControle();
      document.getElementById('ed-quebra').focus();
    });
    document.getElementById('aprovar-quebra').addEventListener('click', aprovarQuebra);
    document.getElementById('ed-quebra-aprovar').addEventListener('click', function () {
      aprovarQuebra();
      // o botao some com a proposta aprovada: o foco fica no controle
      document.getElementById('ed-quebra-fechar').focus();
    });
    document.getElementById('ver-quebra').addEventListener('click', verQuebraProposta);
    depoisDoAto.familia = function () {
      return lerRascunho().then(function () {
        atualizarSelo(); atualizarBotaoFamilia(); atualizarSalvar(); mostrarProposta(); marcarQuebrasNoPalco();
      });
    };
    depoisDoAto.salvar = function () {
      atualizarSalvar();
      document.getElementById('salvo').focus();
    };
  }

  /* ---------------------------------------------------------------- render e aprovacao (M7b, B5)
     Uma linha por formato com a situacao que o motor mede (desdobra/tela/estado.py, painel_dos_formatos), o motivo
     numa frase e a marca de quem pede render. O formato escolhido mostra a imagem (o master em dia pela rota /render,
     ou a previa do layout) com a caixa de antes tracejada e a de depois cheia, e a lista "o que mudou" da ultima versao
     do briefing que mexeu nele. "Renderizar os afetados" pede o render de todos os que pedem render, com uma
     confirmacao so (Q3 e Q4); "Aprovar" pede a aprovacao dos formatos marcados, com o arquivo final de cada um na
     janela (Q11), e pergunta antes o lado do giro do formato que vai girado sem lado gravado (Q13). Os dois atos rodam
     como tarefa no servidor: a pagina acompanha a etapa e o formato por /api/tarefa, e Cancelar corta o formato em
     andamento (Q14). Nada vem marcado, e o render nunca parte sozinho. O historico de versoes e so para leitura (Q12).
     Todo texto do job entra por textContent; as caixas vao pelo CSSOM, em % do tamanho do master. */
  const pn = { escolhido: null, marcados: new Set(), ocupado: false, acompanhando: null };
  const ESPERA_TAREFA_MS = 400;
  const NOME_PREPARO = 'preparo';
  const SITUACOES_VIVAS = ['na_fila', 'rodando'];
  const PAINEL_VAZIO = 'Os formatos aparecem aqui depois que você salva o briefing.';
  const PAINEL_SO_VER = 'Nesta janela a tela só mostra. O render e a aprovação ficam para a janela que o desdobra abre para você.';
  const PEDE_RENDER = 'Pede render';
  const PODE_APROVAR = 'Pode aprovar';
  const ESCOLHA_UM_FORMATO = 'Escolha um formato na lista para ver o que mudou nele.';
  const IMAGEM_RENDER = 'Último render';
  const IMAGEM_PREVIA = 'Prévia do layout, ainda sem render';
  const IMAGEM_SEM = 'Este formato ainda não tem imagem.';
  const LEGENDA_ANTES = 'Tracejado: onde estava';
  const LEGENDA_DEPOIS = 'Contínuo: onde ficou';
  const TITULO_MUDOU = 'O que mudou';
  const SEM_MUDANCA = 'Nenhuma mudança à espera neste formato.';
  const SEM_VERSOES = 'Nenhuma versão salva ainda.';
  const ERRO_PEDIDO = 'A tela não conseguiu pedir o trabalho. Tente de novo.';
  const ERRO_TAREFA = 'A tela perdeu o andamento do trabalho. Confira os formatos de novo.';
  const TEXTO_SENTIDO_UM = 'Este formato vai girado para o veículo. Escolha para que lado ele gira. O lado fica gravado junto com a aprovação.';
  const TEXTO_SENTIDO_VARIOS = 'Estes formatos vão girados para o veículo. Escolha para que lado cada um gira. O lado fica gravado junto com a aprovação.';
  const TOPO_DA_PECA = 'A barra mostra onde fica o topo da peça.';
  const SVG = 'http://www.w3.org/2000/svg';

  function noSvg(tag, attrs) {
    const n = document.createElementNS(SVG, tag);
    Object.keys(attrs).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    return n;
  }
  function formatosDoPainel() { return (estado && estado.painel && estado.painel.formatos) || []; }
  function formatoDoPainel(fid) { return formatosDoPainel().find(function (f) { return f.id === fid; }) || null; }
  function nomeDoFormato(fid) { const f = formatoDoPainel(fid); return f ? f.nome : fid; }
  function listaDeNomes(ns) { return ns.length <= 1 ? ns.join('') : ns.slice(0, -1).join(', ') + ' e ' + ns[ns.length - 1]; }
  function tarefaViva(t) { return !!(t && SITUACOES_VIVAS.indexOf(t.situacao) >= 0); }
  function mensagemDoPainel(texto, tipo) {
    const no = document.getElementById('painel-mensagem');
    no.textContent = texto || '';
    no.dataset.tipo = tipo || '';
    no.hidden = !texto;
  }
  /* o estado novo do servidor no painel: as marcas so ficam nos formatos que ainda podem ser aprovados */
  function trocarPainel(e) {
    estado.painel = e.painel;
    estado.tarefa = e.tarefa;
    estado.edicao_bloqueada = e.edicao_bloqueada;
    const podem = new Set(formatosDoPainel().filter(function (f) { return f.pode_aprovar; }).map(function (f) { return f.id; }));
    Array.from(pn.marcados).forEach(function (fid) { if (!podem.has(fid)) pn.marcados.delete(fid); });
    if (!document.getElementById('passo-formatos').hidden) montarPainel();
  }
  function contagens(fs) {
    const n = function (teste) { return fs.filter(teste).length; };
    const partes = [plural(fs.length, 'formato', 'formatos')];
    const pede = n(function (f) { return f.pede_render; });
    const podem = n(function (f) { return f.pode_aprovar; });
    const aprovados = n(function (f) { return f.situacao === 'aprovado'; });
    if (pede) partes.push(pede === 1 ? '1 pede render' : pede + ' pedem render');
    if (podem) partes.push(podem === 1 ? '1 pode ser aprovado' : podem + ' podem ser aprovados');
    if (aprovados) partes.push(aprovados === 1 ? '1 aprovado' : aprovados + ' aprovados');
    return partes.join(', ') + '.';
  }
  function montarPainel() {
    const fs = formatosDoPainel();
    const lista = document.getElementById('lista-formatos');
    limpar(lista);
    document.getElementById('painel-resumo').textContent = !escrita ? PAINEL_SO_VER : (fs.length ? contagens(fs) : '');
    if (!fs.length) {
      const vazio = el('div', null, 'painel-vazio');
      vazio.appendChild(el('p', PAINEL_VAZIO, 'vazio-titulo'));
      lista.appendChild(vazio);
    }
    fs.forEach(function (f, i) { lista.appendChild(linhaDoFormato(f, i)); });
    montarRegistro();
    montarHistorico((estado.painel && estado.painel.historico) || []);
    if (!pn.escolhido || !formatoDoPainel(pn.escolhido)) {
      // o primeiro que pede atencao do DA; sem nenhum, o primeiro da lista
      const primeiro = fs.find(function (f) { return f.mudou || f.pede_render || f.pode_aprovar; }) || fs[0];
      pn.escolhido = primeiro ? primeiro.id : null;
    }
    mostrarDetalhe(pn.escolhido);
    atualizarBotoesDoPainel();
    if (tarefaViva(estado.tarefa) && !pn.acompanhando) retomarTarefa(estado.tarefa);
  }
  function linhaDoFormato(f, i) {
    const linha = el('div', null, 'linha-formato');
    linha.setAttribute('role', 'listitem');
    linha.dataset.formato = f.id;
    linha.dataset.situacao = f.situacao;
    linha.style.animationDelay = (i * 35) + 'ms';
    const marca = el('input', null, 'linha-marca');
    marca.type = 'checkbox';
    marca.checked = pn.marcados.has(f.id);
    marca.disabled = !escrita || !f.pode_aprovar;
    marca.setAttribute('aria-label', 'Marcar o formato ' + f.nome + ' para aprovar');
    marca.addEventListener('change', function () {
      if (marca.checked) pn.marcados.add(f.id); else pn.marcados.delete(f.id);
      atualizarBotoesDoPainel();
    });
    linha.appendChild(marca);
    const abrir = botao(null, 'linha-abrir');
    abrir.setAttribute('aria-pressed', pn.escolhido === f.id ? 'true' : 'false');
    const mini = el('span', null, 'linha-mini');
    mini.setAttribute('aria-hidden', 'true');
    const forma = el('span', null, 'linha-forma');
    caixaMini(forma, f.composicao[0] || 1, f.composicao[1] || 1, 30, 22);
    mini.appendChild(forma);
    abrir.appendChild(mini);
    const textos = el('span', null, 'linha-textos');
    const nome = el('span', null, 'linha-nome');
    nome.appendChild(el('span', f.nome, 'linha-medida'));
    if (f.giro) nome.appendChild(el('span', 'girado ' + f.giro + ' graus', 'linha-giro'));
    if (f.mudou && f.mudou.itens.length) {
      nome.appendChild(el('span', plural(f.mudou.itens.length, 'mudança', 'mudanças'), 'conta-mudancas'));
    }
    textos.appendChild(nome);
    textos.appendChild(el('span', f.motivo, 'linha-motivo'));
    abrir.appendChild(textos);
    abrir.addEventListener('click', function () {
      pn.escolhido = f.id;
      document.querySelectorAll('#lista-formatos .linha-abrir').forEach(function (b) {
        b.setAttribute('aria-pressed', b.closest('.linha-formato').dataset.formato === f.id ? 'true' : 'false');
      });
      mostrarDetalhe(f.id);
    });
    linha.appendChild(abrir);
    const marcas = el('span', null, 'linha-marcas');
    marcas.appendChild(el('span', f.rotulo, 'chip chip-' + f.situacao));
    if (f.pede_render) marcas.appendChild(el('span', PEDE_RENDER, 'etiqueta-painel pede'));
    else if (f.pode_aprovar) marcas.appendChild(el('span', PODE_APROVAR, 'etiqueta-painel pode'));
    linha.appendChild(marcas);
    return linha;
  }
  function atualizarBotoesDoPainel() {
    const fs = formatosDoPainel();
    const ocupado = pn.ocupado || tarefaViva(estado && estado.tarefa);
    const afetados = (estado && estado.painel && estado.painel.afetados) || [];
    const r = document.getElementById('renderizar-afetados');
    const a = document.getElementById('aprovar-marcados');
    function rotular(b, texto, n, um, varios) {
      limpar(b);
      b.appendChild(document.createTextNode(texto));
      if (n) b.appendChild(el('span', n, 'contagem-botao'));
      b.setAttribute('aria-label', n ? texto + ', ' + plural(n, um, varios) : texto);
    }
    rotular(r, 'Renderizar os afetados', afetados.length, 'formato', 'formatos');
    rotular(a, 'Aprovar', pn.marcados.size, 'formato marcado', 'formatos marcados');
    r.disabled = !escrita || ocupado || !afetados.length;
    a.disabled = !escrita || ocupado || !pn.marcados.size;
    document.getElementById('registro-guardar').disabled = !escrita || ocupado;
    document.querySelectorAll('#lista-formatos .linha-marca').forEach(function (c) {
      const f = formatoDoPainel(c.closest('.linha-formato').dataset.formato);
      c.disabled = !escrita || ocupado || !(f && f.pode_aprovar);
    });
    raiz.dataset.painel = fs.length ? 'pronto' : 'vazio';
  }
  /* ---------------------------------------------------------------- o padrao da marca (M7c, M5; decisao 190, Q1 a Q3)
     O botao "Guardar o padrão desta marca" so aparece quando o motor diz que pode (desdobra/marca/registrar.py,
     na_tela: o job tem marca e todos os formatos estao aprovados pelo DA). Ele e um ato da janela, como os outros: a
     confirmacao mostra o que vai ao perfil (as regras de escala e as ancoras por funcao com o job de origem, e o nome
     das faces) e so o Confirmar grava. Depois, a faixa diz em que versao o padrao ficou guardado, sem botao. O nome da
     marca e o das faces entram so por textContent. */
  const REGISTRO_SELO = 'Padrão da marca';
  const REGISTRO_TITULO = 'A campanha foi aprovada';
  const REGISTRO_GUARDADO = 'Padrão guardado';
  const REGISTRO_FORA = 'Fica de fora do perfil: as edições de palco, a versão da galeria e os arquivos de fonte. ' +
    'O perfil guarda só o nome de cada face.';
  function registroDaMarca() {
    return (estado && estado.lido && estado.lido.marca && estado.lido.marca.registro) || null;
  }
  function montarRegistro() {
    const r = registroDaMarca();
    const faixa = document.getElementById('registro-marca');
    const b = document.getElementById('registro-guardar');
    const mostra = !!(r && (r.pode || r.guardado));
    faixa.hidden = !mostra;
    b.hidden = !(mostra && r.pode);
    if (!mostra) { delete b.dataset.dados; return; }
    faixa.dataset.situacao = r.pode ? 'pode' : 'guardado';
    document.getElementById('registro-selo').textContent = r.nome;
    faixa.setAttribute('aria-label', REGISTRO_SELO + ' ' + r.nome);
    document.getElementById('registro-titulo').textContent = r.pode ? REGISTRO_TITULO : REGISTRO_GUARDADO;
    document.getElementById('registro-nota').textContent = r.pode ?
      (r.formatos === 1 ? 'O formato do job está aprovado.' : 'Os ' + r.formatos + ' formatos do job estão aprovados.') +
        ' Guarde as regras de escala e as âncoras deste job para os próximos jobs desta marca.' :
      'O padrão desta campanha está na versão ' + (r.versao_guardada || r.versao_atual) + ' da marca.' +
        (r.versao_guardada && r.versao_guardada < r.versao_atual ?
          ' A versão que vale agora é a ' + r.versao_atual + ', de uma campanha mais nova.' : '') +
        ' Os próximos jobs dela mostram o padrão como sugestão.';
    if (r.pode) {
      b.dataset.dados = JSON.stringify({ impressao: r.impressao });
      b.disabled = !escrita || pn.ocupado;
    }
  }
  function linhaDoRegistro(lista, nome, valor, i) {
    const li = el('li', null, 'registro-linha');
    li.appendChild(el('span', maiuscula(nomeFuncao(i.funcao)), 'registro-funcao'));
    li.appendChild(el('span', valor, 'registro-valor'));
    const origem = el('span', i.desta_campanha ? 'deste job' : 'do job ' + nomeDoJob(i) + ', mantida',
      'registro-origem');
    if (!i.desta_campanha) origem.title = 'Este job não decidiu esta função. Ela fica como estava no padrão.';
    li.appendChild(origem);
    li.setAttribute('aria-label', nome + ' de ' + nomeFuncao(i.funcao) + ': ' + valor + ', ' + origem.textContent);
    lista.appendChild(li);
  }
  /* o que a janela de confirmacao do registro mostra alem do texto do motor */
  function extraDoRegistro() {
    const r = registroDaMarca();
    if (!r || !r.pode) return null;
    const corpo = el('div', null, 'registro-extra');
    [['Regras de escala', r.regras, function (i) { return maiuscula(nomeRegra(i.regra)); }],
      ['Âncoras', r.ancoras, function (i) { return (ANCORA_Y[i.y] || i.y) + ' ' + (ANCORA_X[i.x] || i.x); }]
    ].forEach(function (g) {
      const bloco = el('section', null, 'registro-grupo');
      const topo = el('div', null, 'registro-grupo-topo');
      topo.appendChild(el('h3', g[0]));
      topo.appendChild(el('span', String(g[1].length), 'registro-conta'));
      bloco.appendChild(topo);
      if (!g[1].length) bloco.appendChild(el('p', 'Nenhuma confirmada neste job.', 'nota'));
      else {
        const ul = el('ul', null, 'registro-lista');
        g[1].forEach(function (i) { linhaDoRegistro(ul, g[0] === 'Âncoras' ? 'Âncora' : 'Regra', g[2](i), i); });
        bloco.appendChild(ul);
      }
      corpo.appendChild(bloco);
    });
    const faces = el('section', null, 'registro-grupo');
    const topo = el('div', null, 'registro-grupo-topo');
    topo.appendChild(el('h3', 'Faces usadas'));
    topo.appendChild(el('span', String(r.faces.length), 'registro-conta'));
    faces.appendChild(topo);
    if (!r.faces.length) faces.appendChild(el('p', 'Nenhuma face de texto no KV.', 'nota'));
    else {
      const ul = el('ul', null, 'formatos-do-ato registro-faces');
      r.faces.forEach(function (f) { ul.appendChild(el('li', f, 'chip chip-neutro')); });
      faces.appendChild(ul);
    }
    corpo.appendChild(faces);
    corpo.appendChild(el('p', REGISTRO_FORA, 'nota registro-fora'));
    return corpo;
  }
  function montarHistorico(h) {
    const ol = document.getElementById('historico-versoes');
    limpar(ol);
    if (!h.length) { ol.appendChild(el('li', SEM_VERSOES, 'vazio')); return; }
    h.forEach(function (v) {
      const li = el('li', null, 'versao');
      const topo = el('div', null, 'versao-topo');
      topo.appendChild(el('span', 'Versão ' + v.versao, 'versao-numero'));
      if (v.quando_texto) topo.appendChild(el('span', v.quando_texto, 'versao-data'));
      li.appendChild(topo);
      li.appendChild(el('span', v.origem_texto, 'versao-origem'));
      li.appendChild(el('span', v.formatos_texto, 'versao-formatos'));
      ol.appendChild(li);
    });
  }
  function emPorcento(no, c, W, H) {
    no.style.left = (c[0] / W * 100) + '%';
    no.style.top = (c[1] / H * 100) + '%';
    no.style.width = (Math.max(0, c[2] - c[0]) / W * 100) + '%';
    no.style.height = (Math.max(0, c[3] - c[1]) / H * 100) + '%';
  }
  /* a imagem do formato com as caixas de antes (tracejada) e de depois (cheia) de cada item que moveu ou mudou de
     tamanho; o item da lista realca as caixas do elemento dele */
  function antesEDepois(f, aside) {
    const fig = el('figure', null, 'antes-depois');
    const quadro = el('div', null, 'ad-quadro carregando');
    const W = f.composicao[0] || 1, H = f.composicao[1] || 1;
    const largura = Math.max(160, aside.clientWidth - 48);
    caixaMini(quadro, W, H, largura, 300);
    fig.appendChild(quadro);
    const legenda = el('figcaption', null, 'ad-legenda');
    fig.appendChild(legenda);
    const caixas = el('div', null, 'ad-caixas');
    const itens = ((f.mudou && f.mudou.itens) || []).filter(function (x) { return x.antes && x.depois; });
    itens.forEach(function (x) {
      [['antes', 'caixa-antes'], ['depois', 'caixa-depois']].forEach(function (par) {
        const c = el('div', null, par[1]);
        if (x.elemento) c.dataset.elemento = x.elemento;
        emPorcento(c, x[par[0]], W, H);
        caixas.appendChild(c);
      });
    });
    function pronto(texto) {
      quadro.classList.remove('carregando');
      quadro.appendChild(caixas);
      legenda.appendChild(el('span', texto, 'ad-origem'));
      if (itens.length) {
        legenda.appendChild(el('span', LEGENDA_ANTES, 'ad-antes'));
        legenda.appendChild(el('span', LEGENDA_DEPOIS, 'ad-depois'));
      }
      quadro.dataset.pronto = '1';
    }
    function comPrevia() {
      if (f.situacao === 'sem_derivacao') { pronto(IMAGEM_SEM); return; }
      const mini = el('div', null, 'mini-palco ad-previa');
      mini.style.width = quadro.style.width;
      mini.style.height = quadro.style.height;
      quadro.appendChild(mini);
      previaSalva(f).then(function (m) {
        // o layout salvo do formato (m.salvo); sem ele, a previa da abertura
        return desenharPalco(mini, m.salvo || vistaInicial(m), { miniatura: true });
      }).then(function () { pronto(IMAGEM_PREVIA); }).catch(function () { mini.remove(); pronto(IMAGEM_SEM); });
    }
    if (f.render_em_dia) {
      const img = document.createElement('img');
      img.className = 'ad-imagem';
      img.alt = 'Último render do formato ' + f.nome;
      img.addEventListener('load', function () { pronto(IMAGEM_RENDER); });
      img.addEventListener('error', function () { img.remove(); comPrevia(); });
      quadro.appendChild(img);
      carregarImagem(img, '/render/' + encodeURIComponent(f.id));
    } else {
      comPrevia();
    }
    return fig;
  }
  function mostrarDetalhe(fid) {
    const aside = document.getElementById('formato-detalhe');
    limpar(aside);
    const f = fid ? formatoDoPainel(fid) : null;
    aside.dataset.formato = f ? f.id : '';
    if (!f) { aside.appendChild(el('p', formatosDoPainel().length ? ESCOLHA_UM_FORMATO : PAINEL_VAZIO, 'nota')); return; }
    const topo = el('header', null, 'detalhe-formato-topo');
    topo.appendChild(el('h2', f.nome, 'detalhe-formato-nome'));
    topo.appendChild(el('span', f.rotulo, 'chip chip-' + f.situacao));
    aside.appendChild(topo);
    if (f.giro) {
      aside.appendChild(el('p', 'Vai para o veículo girado ' + f.giro + ' graus. A imagem mostra a peça antes do giro.',
        'detalhe-giro'));
    }
    aside.appendChild(antesEDepois(f, aside));
    aside.appendChild(el('p', f.motivo, 'detalhe-motivo'));
    const sec = el('section', null, 'mudou');
    sec.setAttribute('aria-label', TITULO_MUDOU);
    const cab = el('div', null, 'mudou-topo');
    cab.appendChild(el('h3', TITULO_MUDOU));
    if (f.mudou) cab.appendChild(el('span', 'Versão ' + f.mudou.versao + (f.mudou.quando_texto ? ', ' + f.mudou.quando_texto : ''), 'mudou-versao'));
    sec.appendChild(cab);
    if (!f.mudou) {
      sec.appendChild(el('p', SEM_MUDANCA, 'nota'));
    } else {
      const ol = el('ol', null, 'mudou-itens');
      f.mudou.itens.forEach(function (x, i) {
        const li = el('li', x.frase, 'mudou-item');
        li.style.animationDelay = (i * 30) + 'ms';
        if (x.elemento && x.antes) {
          li.dataset.elemento = x.elemento;
          li.tabIndex = 0;
          const realce = function (sim) {
            aside.querySelectorAll('.ad-caixas [data-elemento]').forEach(function (c) {
              c.classList.toggle('realce', sim && c.dataset.elemento === x.elemento);
            });
          };
          ['mouseenter', 'focus'].forEach(function (ev) { li.addEventListener(ev, function () { realce(true); }); });
          ['mouseleave', 'blur'].forEach(function (ev) { li.addEventListener(ev, function () { realce(false); }); });
        }
        ol.appendChild(li);
      });
      sec.appendChild(ol);
    }
    aside.appendChild(sec);
  }

  /* ---- tarefas: o preparo do pedido, o render e a aprovacao rodam no servidor; a pagina acompanha */
  function mostrarTarefa(v) {
    const caixa = document.getElementById('tarefa-painel');
    caixa.hidden = false;
    caixa.dataset.situacao = v.situacao;
    caixa.dataset.nome = v.nome;
    document.getElementById('tarefa-texto').textContent = v.texto;
    const partes = [];
    if (v.etapa_texto) partes.push(v.etapa_texto + (v.formato ? ', ' + nomeDoFormato(v.formato) : ''));
    if (v.nome !== NOME_PREPARO && v.formatos.length) partes.push(v.feitos.length + ' de ' + v.formatos.length + ' prontos');
    document.getElementById('tarefa-detalhe').textContent = partes.join('. ') + (partes.length ? '.' : '');
    const barra = document.getElementById('tarefa-barra');
    const parte = v.nome !== NOME_PREPARO && v.formatos.length ? v.feitos.length / v.formatos.length : null;
    barra.parentNode.classList.toggle('indeterminada', parte === null);
    barra.style.transform = 'scaleX(' + (parte === null ? 1 : Math.max(0.02, parte)) + ')';
    document.getElementById('tarefa-cancelar').hidden = !tarefaViva(v) || !escrita;
    raiz.dataset.tarefa = v.situacao;
  }
  function esconderTarefa() {
    document.getElementById('tarefa-painel').hidden = true;
    raiz.dataset.tarefa = '';
  }
  function acompanhar(id) {
    pn.acompanhando = id;
    return new Promise(function (resolver, recusar) {
      function ver() {
        pedir('/api/tarefa/' + encodeURIComponent(id)).then(function (v) {
          mostrarTarefa(v);
          if (tarefaViva(v)) { setTimeout(ver, ESPERA_TAREFA_MS); return; }
          pn.acompanhando = null;
          resolver(v);
        }).catch(function (e) { pn.acompanhando = null; recusar(e); });
      }
      ver();
    });
  }
  /* a tarefa que ja rodava quando a pagina abriu (ou voltou): so acompanhar, e o estado novo no fim */
  function retomarTarefa(t) {
    pn.ocupado = true;
    atualizarBotoesDoPainel();
    acompanhar(t.id).then(function (fim) {
      mensagemDoPainel(fim.texto, fim.situacao);
      esconderTarefa();
    }).catch(function () { mensagemDoPainel(ERRO_TAREFA, 'parou'); esconderTarefa(); }).then(function () {
      pn.ocupado = false;
      return recarregarEstado();
    }).catch(function () { return null; });
  }
  function nomesDaResposta(r) {
    const lista = (r && (r.bloqueados || r.com_falha || r.recusados || r.mudaram)) || [];
    return lista.map(function (x) { return typeof x === 'string' ? nomeDoFormato(x) : x.nome; });
  }
  function textoDoFim(v) {
    const ns = nomesDaResposta(v.resposta);
    if (!ns.length) return v.texto;
    return v.texto + ' ' + (ns.length === 1 ? 'Formato: ' : 'Formatos: ') + listaDeNomes(ns) + '.';
  }
  function extraDoAto(nome, p) {
    const fs = p.formatos || [];
    if (!fs.length) return null;
    if (nome === 'aprovar') {
      const grade = el('div', null, 'finais');
      fs.forEach(function (f) {
        const fig = el('figure', null, 'final');
        const caixa = el('div', null, 'final-caixa carregando');
        const img = document.createElement('img');
        img.alt = 'Arquivo final do formato ' + f.nome;
        img.addEventListener('load', function () { caixa.classList.remove('carregando'); });
        caixa.appendChild(img);
        carregarImagem(img, '/final/' + encodeURIComponent(f.id));
        fig.appendChild(caixa);
        const leg = el('figcaption', null, 'final-legenda');
        leg.appendChild(el('span', f.nome, 'final-nome'));
        if (f.extensao) leg.appendChild(el('span', String(f.extensao).toUpperCase(), 'final-tipo'));
        fig.appendChild(leg);
        grade.appendChild(fig);
      });
      return grade;
    }
    const lista = el('ul', null, 'formatos-do-ato');
    fs.forEach(function (f) { lista.appendChild(el('li', f.nome, 'chip chip-neutro')); });
    return lista;
  }
  /* a figura do giro: a peca como o layout dela (composicao, antes do giro), a seta do lado escolhido e a peca como
     sai para o veiculo, com o lado maior trocado; a barra marca o topo da peca */
  function figuraDoGiro(graus, sentido, composicao) {
    const s = noSvg('svg', { viewBox: '0 0 148 64', width: '148', height: '64', 'aria-hidden': 'true', focusable: 'false', 'class': 'figura-giro' });
    const deitada = !composicao || composicao[0] >= composicao[1];
    // antes: deitada 46x28 ou de pe 28x46, centrada na metade esquerda; depois: o contrario, na metade direita
    const antes = deitada ? { x: 6, y: 19, l: 46, a: 28 } : { x: 15, y: 9, l: 28, a: 46 };
    const depois = deitada ? { x: 106, y: 6, l: 28, a: 46 } : { x: 96, y: 18, l: 46, a: 28 };
    s.appendChild(noSvg('rect', { x: String(antes.x), y: String(antes.y), width: String(antes.l), height: String(antes.a), rx: '3', 'class': 'giro-peca' }));
    s.appendChild(noSvg('rect', { x: String(antes.x), y: String(antes.y), width: String(antes.l), height: '5', rx: '2', 'class': 'giro-topo' }));
    const horario = sentido === 'horario';
    s.appendChild(noSvg('path', { d: horario ? 'M62 36 A11 11 0 0 1 84 36' : 'M84 36 A11 11 0 0 0 62 36', 'class': 'giro-seta' }));
    s.appendChild(noSvg('path', { d: horario ? 'M80 32 L84 37 L88 32' : 'M58 32 L62 37 L66 32', 'class': 'giro-seta' }));
    // o quarto de volta no sentido do relogio leva o topo para a direita; ao contrario, para a esquerda
    const direita = horario === (graus === 90);
    s.appendChild(noSvg('rect', { x: String(depois.x), y: String(depois.y), width: String(depois.l), height: String(depois.a), rx: '3', 'class': 'giro-peca' }));
    s.appendChild(noSvg('rect', { x: String(direita ? depois.x + depois.l - 5 : depois.x), y: String(depois.y), width: '5', height: String(depois.a), rx: '2', 'class': 'giro-topo' }));
    return s;
  }
  /* a janela do lado do giro (Q13): nada vem marcado; Seguir so com o lado de cada formato escolhido */
  function escolherSentido(lista) {
    const d = document.getElementById('sentido');
    const corpo = document.getElementById('sentido-formatos');
    const sim = d.querySelector('[data-resposta=sim]');
    const nao = d.querySelector('[data-resposta=nao]');
    document.getElementById('sentido-texto').textContent = (lista.length === 1 ? TEXTO_SENTIDO_UM : TEXTO_SENTIDO_VARIOS) + ' ' + TOPO_DA_PECA;
    limpar(corpo);
    const escolhas = {};
    sim.disabled = true;
    lista.forEach(function (f) {
      const bloco = el('div', null, 'sentido-formato');
      bloco.appendChild(el('p', f.nome + ', girado ' + f.graus + ' graus', 'sentido-nome'));
      const grupo = el('div', null, 'sentido-opcoes');
      grupo.setAttribute('role', 'group');
      grupo.setAttribute('aria-label', 'Lado do giro do formato ' + f.nome);
      f.opcoes.forEach(function (o) {
        const b = botao(null, 'sentido-opcao');
        b.setAttribute('aria-pressed', 'false');
        b.dataset.formato = f.id;
        b.dataset.sentido = o.valor;
        b.appendChild(figuraDoGiro(f.graus, o.valor, f.composicao));
        b.appendChild(el('span', o.texto, 'sentido-opcao-texto'));
        b.addEventListener('click', function () {
          escolhas[f.id] = o.valor;
          grupo.querySelectorAll('.sentido-opcao').forEach(function (x) { x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
          sim.disabled = lista.some(function (x) { return !escolhas[x.id]; });
        });
        grupo.appendChild(b);
      });
      bloco.appendChild(grupo);
      corpo.appendChild(bloco);
    });
    const antes = document.activeElement;
    return new Promise(function (resolver) {
      let respondido = false;
      function fim(resposta) {
        if (respondido) return;
        respondido = true;
        d.removeEventListener('cancel', aoCancelar);
        sim.removeEventListener('click', aoSim);
        nao.removeEventListener('click', aoNao);
        if (d.open) d.close();
        if (antes && antes.focus) antes.focus();
        resolver(resposta ? escolhas : null);
      }
      function aoCancelar(ev) { ev.preventDefault(); fim(false); }
      function aoSim() { if (!sim.disabled) fim(true); }
      function aoNao() { fim(false); }
      d.addEventListener('cancel', aoCancelar);
      sim.addEventListener('click', aoSim);
      nao.addEventListener('click', aoNao);
      d.showModal();
      document.getElementById('sentido-titulo').focus();
    });
  }
  /* o pedido de um ato longo (render ou aprovar): o preparo roda no servidor e, no fim, a confirmacao na janela; o
     Confirmar inicia a tarefa, que a pagina acompanha ate o fim, e o estado novo redesenha o painel */
  function pedirAtoLongo(nome, dados) {
    if (pn.ocupado) return Promise.resolve(null);
    pn.ocupado = true;
    atualizarBotoesDoPainel();
    mensagemDoPainel('');
    raiz.dataset.estadoAto = '';
    let antes = Promise.resolve();
    if (rascunho.espera_id !== null) { clearTimeout(rascunho.espera_id); antes = gravarRascunho(); }
    let seguir = null;
    let emTarefa = false;
    return antes.then(function () {
      return enviar('/api/ato/pedir', { ato: nome, dados: dados });
    }).then(function (r) {
      emTarefa = true;
      return acompanhar(r.tarefa);
    }).then(function (v) {
      esconderTarefa();
      if (v.situacao !== 'feita') {
        if (v.motivo === 'falta_sentido' && v.resposta && v.resposta.sem_sentido) {
          return escolherSentido(v.resposta.sem_sentido).then(function (escolhas) {
            if (!escolhas) { raiz.dataset.estadoAto = 'cancelado'; return null; }
            seguir = { formatos: dados.formatos, sentidos: Object.assign({}, dados.sentidos || {}, escolhas) };
            return null;
          });
        }
        mensagemDoPainel(textoDoFim(v), 'parou');
        raiz.dataset.estadoAto = 'parou';
        return null;
      }
      const p = v.resposta;
      return confirmarNaJanela(Object.assign({}, p, { extra: extraDoAto(nome, p), larga: nome === 'aprovar' })).then(function (sim) {
        if (!sim) {
          return enviar('/api/ato/cancelar', { pedido: p.pedido }).then(function () { raiz.dataset.estadoAto = 'cancelado'; });
        }
        return enviar('/api/ato/confirmar', { pedido: p.pedido, resposta: 'confirmar' }).then(function (r) {
          return acompanhar(r.tarefa);
        }).then(function (fim) {
          esconderTarefa();
          mensagemDoPainel(textoDoFim(fim), fim.situacao);
          if (fim.situacao === 'feita' && nome === 'aprovar') pn.marcados.clear();
          // o painel redesenhado com o estado novo antes de dizer que o ato acabou
          return recarregarEstado().then(function () {
            raiz.dataset.estadoAto = fim.situacao === 'feita' ? 'feito' : fim.situacao;
          });
        });
      });
    }).catch(function () {
      esconderTarefa();
      raiz.dataset.estadoAto = 'erro';
      mensagemDoPainel(emTarefa ? ERRO_TAREFA : ERRO_PEDIDO, 'parou');
      pn.acompanhando = null;
    }).then(function () {
      pn.ocupado = false;
      atualizarBotoesDoPainel();
      // o lado do giro escolhido: o mesmo pedido de novo, agora com o lado (a confirmacao do DA grava os dois)
      if (seguir) return pedirAtoLongo(nome, seguir);
      return null;
    });
  }
  function ligarPainel() {
    document.getElementById('renderizar-afetados').addEventListener('click', function () {
      const afetados = (estado && estado.painel && estado.painel.afetados) || [];
      if (afetados.length) pedirAtoLongo('render', { formatos: afetados.slice() });
    });
    document.getElementById('aprovar-marcados').addEventListener('click', function () {
      const ids = formatosDoPainel().map(function (f) { return f.id; }).filter(function (fid) { return pn.marcados.has(fid); });
      if (ids.length) pedirAtoLongo('aprovar', { formatos: ids });
    });
    document.getElementById('tarefa-cancelar').addEventListener('click', function () {
      const b = document.getElementById('tarefa-cancelar');
      if (!pn.acompanhando) return;
      b.disabled = true;
      enviar('/api/tarefa/cancelar', { tarefa: pn.acompanhando }).catch(function () { return null; }).then(function () { b.disabled = false; });
    });
  }

  /* ---------------------------------------------------------------- controles do palco */
  function zoom(novo) {
    vista.k = novo;
    reajustar(document.getElementById('palco'));
  }
  function atual() {
    const m = document.querySelector('#palco .mundo');
    const t = m ? /scale\(([0-9.e-]+)\)/.exec(m.style.transform) : null;
    return t ? parseFloat(t[1]) : 1;
  }
  function ligarControles() {
    document.getElementById('ajustar').addEventListener('click', function () { zoom(null); });
    document.getElementById('um-por-um').addEventListener('click', function () { zoom(1); });
    document.getElementById('aproximar').addEventListener('click', function () { zoom(atual() * PASSO_ZOOM); });
    document.getElementById('afastar').addEventListener('click', function () { zoom(atual() / PASSO_ZOOM); });
    // Nomes (pedido de 11/11): sem as etiquetas o DA clica no elemento quando o palco esta cheio; as caixas ficam
    const nomes = document.getElementById('ver-nomes');
    nomes.addEventListener('click', function () {
      vista.nomes = !vista.nomes;
      nomes.setAttribute('aria-pressed', vista.nomes ? 'true' : 'false');
      document.getElementById('palco').classList.toggle('sem-nomes', !vista.nomes);
    });
    const limpo = document.getElementById('ver-limpo');
    limpo.addEventListener('click', function () {
      vista.limpo = !vista.limpo;
      limpo.setAttribute('aria-pressed', vista.limpo ? 'true' : 'false');
      document.getElementById('palco').classList.toggle('limpo', vista.limpo);
    });
    document.querySelectorAll('#passos [role=tab]').forEach(function (b) {
      b.addEventListener('click', function () { mostrarPasso(b.dataset.passo); });
    });
    ['passos', 'orientacoes', 'composicoes', 'variantes'].forEach(function (id) { navegarComSetas(document.getElementById(id)); });
    let espera = null;
    window.addEventListener('resize', function () {
      clearTimeout(espera);
      espera = setTimeout(function () {
        reajustar(document.getElementById('palco'));
        reajustar(document.getElementById('palco-kv'));
        reajustar(document.getElementById('palco-ds'));
      }, 100);
    });
  }

  /* ---------------------------------------------------------------- partida */
  ligarControles();
  ligarAtos();
  ligarEdicao();
  ligarFaltam();
  ligarPainel();
  lerRascunho().then(function () { return pedir('/api/estado'); }).then(function (e) {
    estado = e;
    salvoNaTela = !!(e.briefing && e.briefing.salvo);
    (e.fontes || []).forEach(function (f) { familiaCss.set(f.id, f.familia_css); });
    iniciarPasso2(e.funcoes);
    ligarSugestoes();
    mostrarAvisos(e);
    atualizarFaltam();
    mostrarPasso('lido');
    atualizarBotoesDoPainel();
    if (tarefaViva(e.tarefa)) retomarTarefa(e.tarefa);
    return montarLido(e.lido).then(function () { return document.fonts.ready; });
  }).then(function () {
    raiz.dataset.pronto = '1';
  }).catch(function () {
    document.getElementById('selo').textContent = 'A tela não conseguiu ler o estado do job.';
    raiz.dataset.pronto = 'erro';
  });
})();
