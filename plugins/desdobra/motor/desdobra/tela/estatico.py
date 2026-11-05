# -*- coding: utf-8 -*-
"""Pagina, script e folha de estilo da tela de briefing (M7a3, so de leitura), lidos de plugins/desdobra/tela/ e
servidos da memoria pelo servidor da tela (desdobra.tela.servidor). Nada vem de fora: sem CDN e sem pedido a outro
endereco (CSP default-src 'none' e so 'self').

Regras dos arquivos da pasta tela/ (testes em testes/test_tela_palco.py):
  - todo texto que vem do job entra so por textContent, nunca como HTML (proposta do M7, secao 3, linha Texto do
    cliente na pagina);
  - nada inline: o script e a folha vem de rotas proprias (CSP script-src 'self', style-src 'self'); posicao e tamanho
    das pecas vao pelo CSSOM (element.style), que a CSP permite;
  - @font-face com uma familia por face, font-weight e font-style normal, font-display block e sem local()
    (proposta do M7, secao 3, linha @font-face): folha_das_fontes, servida em /fontes.css.
"""
from desdobra import PASTA_PLUGIN

PASTA_TELA = PASTA_PLUGIN / 'tela'
ARQUIVOS = (('/', 'tela.html', 'text/html; charset=utf-8'), ('/tela.js', 'tela.js', 'text/javascript; charset=utf-8'),
            ('/tela.css', 'tela.css', 'text/css; charset=utf-8'))

PREFIXO_FAMILIA = 'dsd-'


def familia_css(ident):
    return PREFIXO_FAMILIA + ident


def folha_das_fontes(ids):
    """@font-face de cada face pelo id, sem local() e sem nome de arquivo."""
    regras = ['@font-face{font-family:"%s";src:url(/fonte/%s);font-weight:normal;font-style:normal;'
              'font-display:block}' % (familia_css(i), i) for i in ids]
    return ('\n'.join(regras) + '\n').encode('utf-8')


def arquivos():
    """{rota: (bytes, tipo)} da pagina, do script e da folha, lidos da pasta tela/ do plugin."""
    return {rota: ((PASTA_TELA / nome).read_bytes(), tipo) for rota, nome, tipo in ARQUIVOS}
