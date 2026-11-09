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
   apaga; a barra embaixo do palco tem Diminuir, Aumentar, Editar texto, Apagar e Desfazer. Durante o arraste so o no
   arrastado muda (transform), com uma linha discreta quando uma borda ou um centro encosta no de outro elemento; ao
   soltar, a edicao vai ao motor (/api/familia/previa), que a leva a cada arquivo da familia, alinha o que ficou quase
   igual e refaz o encaixe; o palco e as miniaturas de cada arquivo voltam desenhados. As edicoes e a versao ficam no
   rascunho; "Confirmar familia" e um ato da janela, com a confirmacao nela, e mexer depois volta a pedir a
   confirmacao. O texto editado vale so na familia (decisao 171) e a recusa do motor aparece no proprio editor.
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
  const MARCA_GERAL = 'Atenção';
  const APOIO = 'apoio de desenho, não gravado';
  const SEM_REGRA = 'sem regra';
  const POR = { camada: 'da própria camada', grupo: 'herdada da pasta', decisao_10: 'pela sugestão para camada coberta' };
  /* os mesmos nomes e explicacoes do dialogo (desdobra/tela/atos.py MODOS) */
  const MODOS = {
    a: ['Textos e miniaturas', 'O Claude recebe os nomes e os textos das camadas e miniaturas das imagens sem texto, para sugerir as funções.'],
    b: ['Sem imagens', 'O Claude recebe os nomes e os textos das camadas, sem nenhuma imagem.'],
    c: ['Sem conteúdo', 'Nada do conteúdo do arquivo vai ao Claude. Ele recebe só contagens e medidas.']
  };
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
  const PASSOS = { lido: 1, funcoes: 2, pecas: 3, design: 4 };
  const AMOSTRA = 'Aa Bb Cc 0123';
  const PASSO_ZOOM = 1.25;
  const MARGEM = 40;
  const MINI = { largura: 216, altura: 104, baixa: 84 };
  const MINI_VARIANTE = { largura: 88, altura: 64 };
  const MINI_MEMBRO = { largura: 84, altura: 46 };
  let estado = null;
  const familiaCss = new Map();
  const previas = new Map();
  const vista = { k: null, limpo: false, formato: null, modelo: null, variante: null, familia: null, grupo: null };
  const metaCsrf = document.querySelector('meta[name="dsd-csrf"]');
  const csrf = metaCsrf ? metaCsrf.content : '';
  const escrita = csrf !== '';
  const rascunho = { job: null, laudo: null, espera: null, espera_id: null, familias: {} };
  /* as escolhas do passo 2 e do Design system, na forma do rascunho (desdobra/tela/funcoes.py) */
  const CAMPOS_P2 = ['funcoes', 'cobertas', 'design', 'design_camadas'];
  const p2 = { funcoes: {}, cobertas: {}, design: {}, design_camadas: {} };
  const p2obs = {}; // indeterminado sem observacao: fica so na tela ate o DA escrever
  /* as escolhas do passo 1 (revisao do M7a): a prancheta (id do quadro) e o giro por chave do formato na folha */
  const p1 = { quadro: null, rotacoes: {} };
  const giroSemSentido = {}; // quarto de volta escolhido sem o sentido: fica so na tela ate o DA escolher o sentido
  const GIROS = [[0, 'Sem giro'], [90, '90 graus'], [180, '180 graus'], [270, '270 graus']];
  const SENTIDOS = [['horario', 'Horário'], ['anti_horario', 'Anti-horário']];
  const TEXTO_RASCUNHO = {
    pronto: 'Suas escolhas ficam salvas no rascunho',
    pendente: 'Suas escolhas ficam salvas no rascunho',
    salvando: 'Salvando no rascunho',
    salvo: 'Salvo no rascunho',
    erro: 'Não foi possível salvar a última escolha. Ela continua na tela; tente de novo.',
    outro_laudo: 'O PSD foi lido de novo, e as escolhas antigas ficaram de fora. Comece pelas versões desta leitura.'
  };
  const NOTA_GALERIA_RASCUNHO = 'Escolha uma versão para começar. A escolha fica salva no rascunho.';
  /* edicao por familia (fatia 4) */
  const ed = { previa: null, pedido: 0, selecionado: null, tecla: 0, arraste: null };
  const PASSO_SETA = 1;
  const PASSO_SETA_LONGO = 10;
  const FATOR_TECLA = 1.05;
  const JUNTAR_TECLAS_MS = 800;
  const ESCALA_MIN = 0.05;
  const ALCA = 10; // lado da alca do canto, em px da tela
  const MEIO_PX = 0.5; // arraste menor que isto e so um clique
  const FATOR_IGUAL = 0.001;
  const CASAS_FRACAO = 1e6;
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
  const AVISO_SALVO = 'O briefing está salvo, e o desdobra seguiu com o job: cada formato parte agora das famílias que ' +
    'você confirmou. Gerar as imagens chega na próxima versão da tela.';
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
  function pedir(rota) {
    return fetch(rota, { credentials: 'same-origin', cache: 'no-store' }).then(function (r) {
      if (!r.ok) throw new Error('rota ' + r.status);
      return r.json();
    });
  }
  function enviar(rota, dados) {
    return fetch(rota, {
      method: 'POST', credentials: 'same-origin', cache: 'no-store',
      headers: { 'Content-Type': 'application/json', 'X-Desdobra-CSRF': csrf },
      body: JSON.stringify(dados)
    }).then(function (r) {
      if (!r.ok) throw new Error('rota ' + r.status);
      return r.status === 204 ? null : r.json();
    });
  }

  /* ---------------------------------------------------------------- rascunho (decisoes 164 e 167) */
  function marcarRascunho(situacao) {
    raiz.dataset.rascunho = situacao;
    const selo = document.getElementById('selo');
    selo.textContent = TEXTO_RASCUNHO[situacao];
    selo.dataset.estado = situacao;
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
      .then(function () { if (rascunho.espera_id === null) marcarRascunho('salvo'); })
      .then(function () { return refazer ? refazerPasso3() : null; })
      .catch(function () { if (refazer) p2Mudou = true; marcarRascunho('erro'); });
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
  /* a faixa de avisos do servidor: a tela que nao se atualizou e o briefing salvo de outra versao dos arquivos */
  function mostrarAvisos(e) {
    const no = document.getElementById('avisos-tela');
    limpar(no);
    const textos = [];
    if (e.aviso_atualizacao) textos.push(e.aviso_atualizacao);
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
    raiz.dataset.rascunho = 'pendente';
    rascunho.espera_id = setTimeout(gravarRascunho, rascunho.espera);
  }
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
      mostrarAvisos(e);
      atualizarFaltam();
      return Promise.resolve(montarLido(e.lido)).then(sincronizarConfirmacoes);
    });
  }
  const depoisDoAto = {};
  /* o ato leva o que a janela mostra: o servidor confere contra o rascunho gravado, no pedido e no Confirmar */
  function comVista(nome, dados) {
    if (nome === 'familia') {
      const f = rascunho.familias[dados.familia];
      return Object.assign({}, dados, { edicoes: (f && f.edicoes) || [] });
    }
    if (nome === 'salvar') return { rascunho: corpoDoRascunho() };
    return dados;
  }
  function pedirAto(nome, dados) {
    raiz.dataset.estadoAto = '';
    // o rascunho que espera vai antes: o ato confirma o que esta gravado
    let antes = Promise.resolve();
    if (rascunho.espera_id !== null) { clearTimeout(rascunho.espera_id); antes = gravarRascunho(); }
    return antes.then(function () {
      return enviar('/api/ato/pedir', { ato: nome, dados: comVista(nome, dados || {}) });
    }).then(function (p) {
      return confirmarNaJanela(p).then(function (sim) {
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
    ['lido', 'funcoes', 'pecas', 'design'].forEach(function (p) {
      document.getElementById('passo-' + p).hidden = p !== id;
    });
    document.getElementById('passo-atual').textContent = 'Passo ' + PASSOS[id] + ' de 4';
    document.getElementById('confirmar-familia').hidden = id !== 'pecas';
    if (id === 'funcoes') desenharKv();
    if (id === 'design') desenharKvDesign();
    if (id === 'pecas' && !document.querySelector('#orientacoes [role=tab]')) iniciarPecas(null);
    if (id === 'pecas') reajustar(document.getElementById('palco'));
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
    if (m.teto && m.opcoes.length < 3) {
      md.appendChild(el('p', 'A agência limita este job aos modos mostrados aqui.', 'nota modo-nota'));
    }
    if (!escrita) md.appendChild(el('p', SO_PARA_VER, 'nota modo-nota'));
  }
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
    });
    return out;
  }
  function atualizarFaltam() {
    montarFaltam((estado.faltam || []).concat(p2idx.opcoes ? pendenciasP2() : []));
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
  function detalhar(n) {
    const d = document.getElementById('detalhe');
    const foco = document.activeElement && d.contains(document.activeElement) ? document.activeElement : null;
    const chaveFoco = foco ? (foco.id || foco.dataset.funcao || foco.textContent) : null;
    limpar(d);
    marcarNoKv('palco-kv', n ? camadasDentro(n) : [], null);
    if (!n) {
      d.appendChild(el('p', 'Passo 2', 'sobretitulo'));
      d.appendChild(el('h2', 'Funções da peça'));
      d.appendChild(el('p', 'Escolha uma pasta ou uma camada à esquerda. A função dada a uma pasta passa para as ' +
        'camadas de dentro, e você pode trocar uma camada depois.', 'nota'));
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
        return (x.id || x.dataset.funcao || x.textContent) === chaveFoco;
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
    if (campo === 'ancora') { d.x = valor[0]; d.y = valor[1]; } else d.regra = valor;
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
      const pronta = !!(d.regra && d.x && d.y);
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
      ['galeria', 'membros', 'variante-palco', 'barra-edicao', 'editor-texto'].forEach(function (id) {
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
    fecharEditorTexto();
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
    if (area.id === 'palco') area.classList.toggle('limpo', vista.limpo);
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
  function mensagem(texto) { document.getElementById('ed-mensagem').textContent = texto || ''; }
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
  /* a edicao vai ao motor, que a leva a cada arquivo da familia; o pedido mais novo vence */
  function pedirPrevia() {
    const n = ++ed.pedido;
    const dados = { familia: vista.familia, versao: versaoDaFamilia(), edicoes: edicoesDa() };
    raiz.dataset.previa = 'pedindo';
    return enviar('/api/familia/previa', dados).then(function (r) {
      if (n !== ed.pedido) return null;
      ed.previa = r;
      if (r.recusas && r.recusas.length) tirarRecusadas(r.recusas);
      else if (ed.textoPendente) { fecharEditorTexto(); mensagem('O texto novo vale só nesta família.'); }
      ed.textoPendente = null;
      return desenharDaPrevia();
    }).then(function () {
      if (n === ed.pedido) raiz.dataset.previa = 'pronta';
    }).catch(function () {
      if (n !== ed.pedido) return;
      raiz.dataset.previa = 'erro';
      mensagem('A tela não conseguiu refazer a família. A última mudança continua no rascunho; tente de novo.');
    });
  }
  function tirarRecusadas(recusas) {
    const ids = new Set(recusas.map(function (x) { return x.elemento; }));
    const f = familiaAtual();
    f.edicoes = f.edicoes.filter(function (e) { return !(e.acao === 'texto' && ids.has(e.elemento)); });
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
    return desenharPalco(area, m.palco, { usarVista: true, editavel: true }).then(function () {
      if (edicoesDa().length) descreverMembro(m);
      atualizarSelo();
      marcarSelecao();
      atualizarBarra();
      if (quem) mostrarAlinhamento(area, r, quem);
      if (focar && ed.selecionado) {
        const alvo = area.querySelector('.rotulo[data-elemento="' + ed.selecionado + '"]');
        if (alvo) alvo.focus();
      }
    });
  }
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
    marcasDa({ falhas: m.falhas, avisos: m.avisos }).forEach(function (x) {
      no.appendChild(el('span', x[1], 'var-palco-aviso' + (x[2] ? ' ' + x[2] : '')));
    });
  }
  function atualizarSelo() {
    if (familiaConfirmada()) mostrarSelo(SELO_CONFIRMADA, 'confirmada');
    else if (edicoesDa().length) mostrarSelo('Com as suas edições: ' + SELO_VARIANTE, 'proposta');
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
        (m.falhas.length ? ', pede ajuste' : ''));
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
      b.addEventListener('click', function () { mostrarFormato(m.formato); });
      lista.appendChild(b);
      desenharPalco(mini, m.palco, { miniatura: true });
    });
  }
  function nomes(lista) { return lista.map(function (x) { return x.nome || 'sem nome'; }).join(', '); }
  function montarResumo(r) {
    const partes = [];
    if (r.textos_editados.length) partes.push('Texto editado nesta família: ' + nomes(r.textos_editados) + '.');
    if (r.apagados.length) partes.push('Tirado desta família: ' + nomes(r.apagados) + '.');
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
    b.textContent = conf ? SELO_CONFIRMADA : 'Confirmar família';
    b.disabled = conf || semEscolha || semSpec;
    b.title = semSpecProprio ? FAMILIA_SEM_SPEC : (semSpecDaMestre ? FAMILIA_SEM_SPEC_DA_MESTRE :
      (semEscolha ? 'Escolha uma versão na galeria antes de confirmar a família.' : ''));
    b.dataset.ato = 'familia';
    b.dataset.dados = JSON.stringify({ familia: vista.familia, versao: versao });
  }
  function novaEdicao(e, juntar) {
    const f = familiaAtual();
    const ult = f.edicoes[f.edicoes.length - 1];
    if (juntar && ult && ult.acao === 'mover' && e.acao === 'mover' && ult.elemento === e.elemento) {
      ult.dx = fracao(ult.dx + e.dx);
      ult.dy = fracao(ult.dy + e.dy);
    } else {
      f.edicoes.push(e);
    }
    if (temGaleria()) f.versao = versaoDaFamilia();
    f.confirmada = false;
    delete f.confirmacao;
    ed.ultimaEdicao = e.elemento;
    mudouRascunho();
    atualizarBotaoFamilia();
    return pedirPrevia();
  }
  function moverPor(id, dx, dy, juntar) {
    const m = modeloDoPalco();
    return novaEdicao({ elemento: id, acao: 'mover', dx: fracao(dx / m.largura), dy: fracao(dy / m.altura) }, juntar);
  }
  function escalarPor(id, fator, fx, fy) {
    const e = { elemento: id, acao: 'escalar', fator: fracao(fator) };
    if (fx !== undefined) { e.fx = fx; e.fy = fy; }
    return novaEdicao(e, false);
  }
  function apagar(id) {
    ed.selecionado = null;
    mensagem('O elemento saiu de todos os arquivos desta família. Desfazer traz de volta.');
    return novaEdicao({ elemento: id, acao: 'apagar' }, false);
  }
  function desfazer() {
    const f = familiaAtual();
    if (!f || !f.edicoes.length) return null;
    f.edicoes.pop();
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
    fecharEditorTexto();
    marcarSelecao();
    atualizarBarra();
  }
  function marcarSelecao() {
    const area = document.getElementById('palco');
    const g = mundos.get(area);
    area.querySelectorAll('.alca').forEach(function (a) { a.remove(); });
    area.querySelectorAll('.rotulo.editavel').forEach(function (r) {
      const sim = r.dataset.elemento === ed.selecionado;
      r.classList.toggle('selecionado', sim);
      r.setAttribute('aria-pressed', sim ? 'true' : 'false');
      if (!sim || !g) return;
      const lado = ALCA / g.k();
      [['nw', 0, 0], ['ne', 1, 0], ['sw', 0, 1], ['se', 1, 1]].forEach(function (c) {
        const a = el('span', null, 'alca');
        a.dataset.canto = c[0];
        a.setAttribute('aria-hidden', 'true');
        a.style.width = lado + 'px';
        a.style.height = lado + 'px';
        a.style.left = (c[1] * 100) + '%';
        a.style.top = (c[2] * 100) + '%';
        a.style.margin = (-lado / 2) + 'px 0 0 ' + (-lado / 2) + 'px';
        r.appendChild(a);
      });
    });
  }
  function atualizarBarra() {
    const e = ed.selecionado ? elementoDoPalco(ed.selecionado) : null;
    if (ed.selecionado && !e) ed.selecionado = null;
    document.getElementById('elemento-escolhido').textContent = e ? 'Escolhido: ' + rotuloElemento(e) :
      'Clique num elemento do palco para mexer nele: arraste para mover, puxe um canto para mudar o tamanho, use as ' +
      'setas, + e - ou Delete pelo teclado e Ctrl+Z para desfazer. Cada mudança vale para a família inteira.';
    ['ed-diminuir', 'ed-aumentar', 'ed-apagar'].forEach(function (i) { document.getElementById(i).disabled = !e; });
    document.getElementById('ed-texto').disabled = !e || pecasDeTexto(e.id).length !== 1;
    document.getElementById('ed-desfazer').disabled = !edicoesDa().length;
  }
  function nosDoElemento(area, id) {
    return Array.from(area.querySelectorAll('.recorte[data-elemento="' + id + '"], .rotulo[data-elemento="' + id + '"]'));
  }
  /* o encaixe leve do arraste: a borda ou o centro que encosta no de outro elemento de conteudo, a menos da
     tolerancia do motor; a linha discreta mostra onde. O motor alinha de novo depois de cada edicao (decisao 168),
     entao a previa do arraste mostra sempre o encaixe */
  function linhasDe(b) { return { x: [b[0], (b[0] + b[2]) / 2, b[2]], y: [b[1], (b[1] + b[3]) / 2, b[3]] }; }
  function encaixar(m, id, c) {
    const tol = (estado.edicao ? estado.edicao.tolerancia_alinhamento : 0) * Math.max(m.largura, m.altura);
    const meu = linhasDe(c);
    const melhor = { x: null, y: null };
    m.elementos.forEach(function (o) {
      if (o.id === id || CONTEUDO.indexOf(o.funcao) < 0) return;
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
  function aoApertar(ev) {
    if (!editavel() || ev.button !== 0) return;
    const r = ev.target.closest ? ev.target.closest('.rotulo.editavel') : null;
    if (!r) return;
    ev.preventDefault();
    const area = document.getElementById('palco');
    const g = mundos.get(area);
    const id = r.dataset.elemento;
    if (ed.selecionado !== id) selecionarElemento(id);
    r.focus();
    const c = elementoDoPalco(id).caixa;
    const alca = ev.target.closest('.alca');
    const canto = alca ? alca.dataset.canto : null;
    const fx = canto ? FIXO[canto] : null;
    ed.arraste = { id: id, canto: canto, x: ev.clientX, y: ev.clientY, k: g.k(), g: g, m: g.modelo,
      fixo: fx ? [c[0] + fx[0] * (c[2] - c[0]), c[1] + fx[1] * (c[3] - c[1])] : null,
      movel: fx ? [c[0] + (1 - fx[0]) * (c[2] - c[0]), c[1] + (1 - fx[1]) * (c[3] - c[1])] : null,
      nos: nosDoElemento(area, id), dx: 0, dy: 0, f: 1 };
    if (r.setPointerCapture) r.setPointerCapture(ev.pointerId);
    r.classList.add('arrastando');
  }
  function aoMover(ev) {
    const a = ed.arraste;
    if (!a) return;
    let dx = (ev.clientX - a.x) / a.k;
    let dy = (ev.clientY - a.y) / a.k;
    if (!a.canto) {
      const c = elementoDoPalco(a.id).caixa;
      const melhor = encaixar(a.m, a.id, [c[0] + dx, c[1] + dy, c[2] + dx, c[3] + dy]);
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
    a.f = Math.max(ESCALA_MIN, (p[0] * v[0] + p[1] * v[1]) / ((v[0] * v[0] + v[1] * v[1]) || 1));
    a.nos.forEach(function (n) {
      n.style.transformOrigin = (a.fixo[0] - a.g.x0 - parseFloat(n.style.left)) + 'px ' +
        (a.fixo[1] - a.g.y0 - parseFloat(n.style.top)) + 'px';
      n.style.transform = 'scale(' + a.f + ')';
    });
  }
  function aoSoltar() {
    const a = ed.arraste;
    if (!a) return;
    ed.arraste = null;
    a.g.mundo.querySelectorAll('.guia').forEach(function (x) { x.remove(); });
    if (!a.canto && Math.abs(a.dx) + Math.abs(a.dy) >= MEIO_PX) { moverPor(a.id, a.dx, a.dy, false); return; }
    if (a.canto && Math.abs(a.f - 1) > FATOR_IGUAL) { escalarPor(a.id, a.f, FIXO[a.canto][0], FIXO[a.canto][1]); return; }
    a.nos.forEach(function (n) { n.style.transform = ''; n.classList.remove('arrastando'); });
  }
  function aoTeclar(ev) {
    const r = ev.target.closest ? ev.target.closest('.rotulo.editavel') : null;
    if (!r || !editavel()) return;
    const id = r.dataset.elemento;
    const passo = ev.shiftKey ? PASSO_SETA_LONGO : PASSO_SETA;
    const setas = { ArrowLeft: [-passo, 0], ArrowRight: [passo, 0], ArrowUp: [0, -passo], ArrowDown: [0, passo] };
    if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); selecionarElemento(id); r.focus(); return; }
    if (ev.key === 'Escape') { selecionarElemento(null); return; }
    if (setas[ev.key]) {
      ev.preventDefault();
      if (ed.selecionado !== id) selecionarElemento(id);
      const agora = Date.now();
      const juntar = agora - ed.tecla < JUNTAR_TECLAS_MS;
      ed.tecla = agora;
      ed.focar = true;
      moverPor(id, setas[ev.key][0], setas[ev.key][1], juntar);
      return;
    }
    if (ev.key === '+' || ev.key === '=' || ev.key === '-') {
      ev.preventDefault();
      if (ed.selecionado !== id) selecionarElemento(id);
      ed.focar = true;
      escalarPor(id, ev.key === '-' ? 1 / FATOR_TECLA : FATOR_TECLA);
      return;
    }
    if (ev.key === 'Delete' || ev.key === 'Backspace') { ev.preventDefault(); apagar(id); }
  }
  /* ------------------------------------------------ texto (decisoes 169 e 171) */
  function abrirEditorTexto() {
    const ps = ed.selecionado ? pecasDeTexto(ed.selecionado) : [];
    if (ps.length !== 1) return;
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
    ed.textoPendente = id;
    return novaEdicao({ elemento: id, acao: 'texto', texto: campo.value.replace(/\r\n?/g, '\n') }, false);
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
    document.getElementById('ed-diminuir').addEventListener('click', function () { escalarPor(ed.selecionado, 1 / FATOR_TECLA); });
    document.getElementById('ed-aumentar').addEventListener('click', function () { escalarPor(ed.selecionado, FATOR_TECLA); });
    document.getElementById('ed-apagar').addEventListener('click', function () { apagar(ed.selecionado); });
    document.getElementById('ed-desfazer').addEventListener('click', desfazer);
    document.getElementById('ed-texto').addEventListener('click', abrirEditorTexto);
    document.getElementById('ed-texto-cancelar').addEventListener('click', function () {
      fecharEditorTexto();
      document.getElementById('ed-texto').focus();
    });
    document.getElementById('ed-texto-aplicar').addEventListener('click', aplicarTexto);
    depoisDoAto.familia = function () {
      return lerRascunho().then(function () { atualizarSelo(); atualizarBotaoFamilia(); atualizarSalvar(); });
    };
    depoisDoAto.salvar = function () {
      atualizarSalvar();
      document.getElementById('salvo').focus();
    };
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
  lerRascunho().then(function () { return pedir('/api/estado'); }).then(function (e) {
    estado = e;
    salvoNaTela = !!(e.briefing && e.briefing.salvo);
    (e.fontes || []).forEach(function (f) { familiaCss.set(f.id, f.familia_css); });
    iniciarPasso2(e.funcoes);
    mostrarAvisos(e);
    atualizarFaltam();
    mostrarPasso('lido');
    return montarLido(e.lido).then(function () { return document.fonts.ready; });
  }).then(function () {
    raiz.dataset.pronto = '1';
  }).catch(function () {
    document.getElementById('selo').textContent = 'A tela não conseguiu ler o estado do job.';
    raiz.dataset.pronto = 'erro';
  });
})();
