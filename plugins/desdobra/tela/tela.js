'use strict';
/* Tela de briefing do desdobra, so de leitura (M7a0, redesenho de 05/11).
   Regras: todo texto do job entra por textContent; posicao e tamanho pelo CSSOM; nada de pedido fora de 'self'.
   O palco usa coordenadas em pixel real da composicao; a escala muda so a exibicao. Cada palco abre em Ajustar (a
   composicao inteira na area, maior ou menor que 1:1); 1:1, Afastar e Aproximar valem ate trocar de formato.
   As abas de composicao sao miniaturas do mesmo modelo do palco, uma por grupo de proporcao parecida (revisao da
   decisao 163). O formato que a derivacao devolve mostra as versoes da galeria do motor ao lado do palco (decisao 164
   e notas de 05/11), a primeira ja escolhida; nada e gravado. O texto da moldura nunca leva identificador do motor:
   tudo passa pelos mapas abaixo. */
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
  const POR = { camada: 'da própria camada', grupo: 'herdada do grupo', decisao_10: 'pela regra da decisão 10' };
  const MODOS = { a: 'Metadados, textos e miniaturas', b: 'Sem imagens', c: 'Sem conteúdo' };
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
    grupo: 'grupo', prancheta: 'prancheta', smart_embutido: 'objeto inteligente embutido',
    smart_linkado: 'objeto inteligente linkado', ajuste: 'camada de ajuste', outro: 'outro tipo'
  };
  const PASSOS = { lido: 1, funcoes: 2, pecas: 3, design: 4 };
  const AMOSTRA = 'Aa Bb Cc 0123';
  const PASSO_ZOOM = 1.25;
  const MARGEM = 40;
  const MINI = { largura: 216, altura: 104, baixa: 84 };
  const MINI_VARIANTE = { largura: 88, altura: 64 };
  let estado = null;
  const familiaCss = new Map();
  const previas = new Map();
  const vista = { k: null, limpo: false, formato: null, modelo: null, variante: null };
  const ajustes = new WeakMap();
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
    document.getElementById('confirmar-composicao').hidden = id !== 'pecas';
    if (id === 'funcoes') desenharKv();
    if (id === 'pecas' && !document.querySelector('#orientacoes [role=tab]')) iniciarPecas(null);
    if (id === 'pecas') reajustar(document.getElementById('palco'));
  }

  /* ---------------------------------------------------------------- falta N */
  function montarFaltam(lista) {
    const botaoFaltam = document.getElementById('faltam');
    const caixa = document.getElementById('lista-faltam');
    const ol = document.getElementById('itens-faltam');
    botaoFaltam.textContent = lista.length === 1 ? 'Falta 1' : 'Faltam ' + lista.length;
    botaoFaltam.classList.toggle('zero', !lista.length);
    limpar(ol);
    if (!lista.length) item(ol, 'Nada falta no que a tela mostra.', 'vazio');
    function fechar() {
      caixa.hidden = true;
      botaoFaltam.setAttribute('aria-expanded', 'false');
    }
    lista.forEach(function (f) {
      const li = el('li');
      li.appendChild(el('span', f.texto, 'texto-item'));
      if (f.detalhe) li.appendChild(el('span', f.detalhe, 'detalhe-item'));
      const ir = botao('Ir até aqui', 'ir');
      ir.addEventListener('click', function () {
        fechar();
        if (f.ir && f.ir.passo === 'pecas' && f.ir.formato) irParaFormato(f.ir.formato);
        else mostrarPasso((f.ir && f.ir.passo) || 'lido');
      });
      li.appendChild(ir);
      ol.appendChild(li);
    });
    botaoFaltam.addEventListener('click', function () {
      caixa.hidden = !caixa.hidden;
      botaoFaltam.setAttribute('aria-expanded', caixa.hidden ? 'false' : 'true');
      if (!caixa.hidden) { const p = caixa.querySelector('button'); if (p) p.focus(); }
    });
    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape' && !caixa.hidden) { fechar(); botaoFaltam.focus(); }
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
  function montarLido(l) {
    const bloqueios = l.bloqueios.map(function (b) { return [(b.descricao || semSublinhado(b.fase)) + ': ' + b.o_que_fazer, 'aviso']; })
      .concat(l.camadas_bloqueadas.map(function (c) {
        return ['Camada ' + c.nome + ': ' + (c.motivos || []).join('; '), 'aviso'];
      }));
    lista(document.getElementById('lido-bloqueios'), bloqueios, 'Nenhum bloqueio.');
    lista(document.getElementById('lido-linkados'), l.linkados.map(function (x) {
      return [x.nome + ': ' + (x.confirmado ? 'arquivo confirmado' : 'espera a confirmação do arquivo'),
        x.confirmado ? '' : 'aviso'];
    }), 'O PSD não tem arquivos linkados.');
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
    const ul = el('ul', null, 'lista-formatos');
    s.formatos.forEach(function (f) {
      const li = el('li');
      li.appendChild(el('span', f.id, 'nome-formato'));
      li.appendChild(el('span', f.sem_folha ? 'formato de teste, sem folha' : (f.tem_spec ? 'com spec confirmada' :
        'sem spec confirmada'), 'estado-formato'));
      ul.appendChild(li);
    });
    sp.appendChild(ul);
    const m = l.modo_dados;
    const md = document.getElementById('lido-modo');
    limpar(md);
    function modo(v) { return v ? (MODOS[v] || 'Modo sem nome') : 'Sem decisão'; }
    const dl = el('dl', null, 'pares');
    [['Do job', modo(m.job)], ['Teto', m.teto ? modo(m.teto) : 'Sem teto'], ['No briefing', modo(m.briefing)]]
      .forEach(function (p) { dl.appendChild(el('dt', p[0])); dl.appendChild(el('dd', p[1])); });
    md.appendChild(dl);
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

  /* ---------------------------------------------------------------- passo 2 */
  let kvDesenhado = false;
  function desenharKv() {
    const area = document.getElementById('palco-kv');
    if (kvDesenhado) { reajustar(area); return; }
    kvDesenhado = true;
    desenharPalco(area, estado.funcoes.palco_kv, { usarVista: false });
  }
  function montarArvore(f) {
    const nav = document.getElementById('arvore');
    limpar(nav);
    function ramo(nos) {
      const ul = el('ul');
      nos.forEach(function (n) {
        const li = el('li', null, n.filhos.length ? 'grupo' : 'camada');
        const b = botao();
        b.appendChild(el('span', n.nome, 'nome'));
        b.appendChild(el('span', nomeFuncao(n.funcao) + (n.por ? ', ' + POR[n.por] : ''), 'funcao'));
        b.addEventListener('click', function () {
          nav.querySelectorAll('button[aria-current]').forEach(function (x) { x.removeAttribute('aria-current'); });
          b.setAttribute('aria-current', 'true');
          detalhar(n, f.resumo);
        });
        li.appendChild(b);
        if (n.filhos.length) li.appendChild(ramo(n.filhos));
        ul.appendChild(li);
      });
      return ul;
    }
    nav.appendChild(ramo(f.arvore));
    detalhar(null, f.resumo);
  }
  function detalhar(n, resumo) {
    const d = document.getElementById('detalhe');
    limpar(d);
    if (n) {
      d.appendChild(el('h2', n.nome));
      const dl = el('dl');
      function par(rotulo, valor) { dl.appendChild(el('dt', rotulo)); dl.appendChild(el('dd', valor)); }
      par('Tipo', nomeTipo(n.tipo));
      par('Função', nomeFuncao(n.funcao));
      if (n.por) par('De onde vem', POR[n.por] + (n.por === 'grupo' ? ' ' + n.nome_raiz : ''));
      if (n.observacao) par('Observação', n.observacao);
      const r = resumo.find(function (x) { return x.funcao === n.funcao; });
      if (r) {
        par('Regra de escala', nomeRegra(r.regra));
        par('Âncora', nomeAncora(r.ancora));
      }
      d.appendChild(dl);
      document.querySelectorAll('#palco-kv .rotulo').forEach(function (x) {
        x.classList.toggle('destaque', n.raiz !== null && x.dataset.raiz === String(n.raiz));
      });
    } else {
      d.appendChild(el('h2', 'Funções da peça'));
      d.appendChild(el('p', 'Escolha um grupo ou uma camada à esquerda para ver a função, a regra de escala e de onde ' +
        'elas vêm. O elemento escolhido fica marcado no KV.', 'nota'));
    }
  }

  /* ---------------------------------------------------------------- design system (so leitura, decisao 161) */
  function montarResumo(resumo) {
    const s = document.getElementById('resumo-design');
    limpar(s);
    s.appendChild(el('p', 'Passo 4', 'sobretitulo'));
    s.appendChild(el('h1', 'Regras e âncoras do briefing'));
    s.appendChild(el('p', 'Resumo só de leitura do que o briefing decidiu para cada função.', 'nota'));
    const t = el('table');
    const cab = el('tr');
    ['Função', 'Regra de escala', 'Âncora', 'Camadas'].forEach(function (x) { cab.appendChild(el('th', x)); });
    t.appendChild(cab);
    resumo.forEach(function (r) {
      const tr = el('tr');
      let ancora = r.ancora ? nomeAncora(r.ancora) : 'sem âncora da função';
      if (r.ancoras_por_elemento) {
        ancora += '; ' + r.ancoras_por_elemento + (r.ancoras_por_elemento === 1 ? ' elemento com âncora própria'
          : ' elementos com âncora própria');
      }
      tr.appendChild(el('td', nomeFuncao(r.funcao)));
      tr.appendChild(el('td', nomeRegra(r.regra), r.regra ? '' : 'sem-valor'));
      tr.appendChild(el('td', ancora, r.ancora ? '' : 'sem-valor'));
      tr.appendChild(el('td', r.camadas, 'numero'));
      t.appendChild(tr);
    });
    s.appendChild(t);
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
      document.getElementById('nome-palco').textContent = 'O briefing não tem formato.';
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
      b.setAttribute('aria-label', 'Composição ' + medidas.join(' e ') + ', ' + plural(fs.length, 'arquivo', 'arquivos'));
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
    f.appendChild(el('span', fs.length === 1 ? 'Arquivo desta composição' : 'Arquivos desta composição', 'legenda'));
    g.composicoes.forEach(function (c) { c.formatos.forEach(function (x) { f.appendChild(fichaDeFormato(x, c)); }); });
    const fid = alvo && alvo.formato && fs.some(function (x) { return x.id === alvo.formato; }) ? alvo.formato : fs[0].id;
    vista.variante = null; // cada grupo abre na primeira versao limpa; entre os arquivos do grupo a escolha fica
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
      dv.textContent = m.devolucao ? (m.devolucao.texto || 'O motor ainda não chegou a uma proposta para este formato.') : '';
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
      return desenharPalco(area, m, { usarVista: true });
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
      b.addEventListener('click', function () { escolherVariante(fid, v); });
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
      m.elementos.forEach(function (e) {
        const r = el('div', null, 'rotulo' + (e.fantasma ? ' fantasma' : ''));
        pos(r, e.caixa);
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
      }, 100);
    });
  }

  /* ---------------------------------------------------------------- partida */
  ligarControles();
  pedir('/api/estado').then(function (e) {
    estado = e;
    (e.fontes || []).forEach(function (f) { familiaCss.set(f.id, f.familia_css); });
    montarFaltam(e.faltam || []);
    montarArvore(e.funcoes);
    montarResumo(e.funcoes.resumo);
    mostrarPasso('lido');
    return montarLido(e.lido).then(function () { return document.fonts.ready; });
  }).then(function () {
    raiz.dataset.pronto = '1';
  }).catch(function () {
    document.getElementById('selo').textContent = 'A tela não conseguiu ler o estado do job.';
    raiz.dataset.pronto = 'erro';
  });
})();
