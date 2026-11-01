# -*- coding: utf-8 -*-
"""Processo filho das folhas de spec: o unico codigo que parseia a folha enviada (PDF, HTML, CSV ou texto).

A folha vem de fora da agencia (o veiculador) ou e um e-mail colado, e por isso e entrada nao confiavel. O PDF e
lido pelo PDFium (codigo nativo, pypdfium2, arquitetura-v1.md 4.8), a mesma classe de risco do psd-tools e do
fontTools (arquitetura 7.1): por isso toda folha, e nao so o PDF, e lida aqui, no mesmo isolador e com o mesmo gancho
de auditoria do leitor (desdobra.leitor.auditoria). O processo principal so ve leitura.json e os recortes PNG.

Chamada:
    python -I -B -m desdobra.specs.filho <arquivo> <pasta_saida> --formato {pdf,html,csv,texto}
        --orcamento-bytes N --escala-recorte S

Ordem:
  1. le os argumentos e espera a linha 'iniciar' (o isolador so a manda depois de confinar);
  2. importa o pypdfium2 (com o PDFium) e o Pillow e instala o gancho de auditoria;
  3. le os bytes do arquivo para a memoria e divide o texto em trechos:
     - PDF: um trecho por retangulo de texto do PDFium, com a pagina e a caixa em pontos (origem embaixo a
       esquerda). Pagina sem nenhum texto vira recorte: a pagina inteira desenhada em PNG, na escala pedida, para o
       DA digitar o valor ao lado (a v1 nao tem OCR). Nunca extrai fonte, imagem nem anexo do PDF;
     - HTML (pagina salva): um trecho por bloco de texto (p, li, div, td, titulo), com a linha do HTML e a secao (o
       titulo mais proximo acima). Tabela (table/tr/td ou div com as classes table, row e col): um trecho por
       celula, com o rotulo do cabecalho da coluna. Script, style e svg ficam de fora; nada e baixado;
     - CSV (exportado pelo DA): um trecho por celula preenchida, com a linha, a coluna e o cabecalho como rotulo;
     - texto ou e-mail (.txt, .eml): um trecho por linha nao vazia. Do .eml so entra o corpo em texto puro;
  4. grava leitura.json (leitura-folha/1) e os recortes em <pasta_saida>, de forma atomica.

Codigos: 0 lida; 3 recusada; 4 memoria; 5 auditoria; 2 argumentos; 1 bug.
"""
import argparse
import enum
import io
import json
import sys
from pathlib import Path


class CodigoFilho(enum.IntEnum):
    OK = 0
    BUG = 1
    ARGUMENTOS = 2
    RECUSADO = 3
    MEMORIA = 4
    AUDITORIA = 5


LINHA_LIBERAR = b'iniciar\n'
ESQUEMA_SAIDA = 'filho/1'
ESQUEMA_LEITURA = 'leitura-folha/1'
ARQUIVO_LEITURA = 'leitura.json'
FORMATOS = ('pdf', 'html', 'csv', 'texto')
ASSINATURA_PDF = b'%PDF-'
TAGS_IGNORADAS = ('script', 'style', 'noscript', 'svg', 'template', 'iframe', 'object')
TAGS_BLOCO = ('p', 'div', 'li', 'ul', 'ol', 'section', 'article', 'header', 'footer', 'main', 'aside', 'nav', 'dt',
              'dd', 'dl', 'blockquote', 'caption', 'figcaption', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'table', 'tr',
              'td', 'th', 'thead', 'tbody', 'form', 'label', 'pre')
TITULOS = ('h1', 'h2', 'h3', 'h4', 'h5', 'h6')
AMOSTRA_CSV = 1 << 14  # numero-neutro: bytes lidos para descobrir o separador do CSV, sem efeito na leitura


class Recusa(Exception):
    def __init__(self, tipo, motivo, codigo):
        super().__init__(motivo)
        self.tipo, self.motivo, self.codigo = tipo, motivo, codigo


class _Argumentos(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write('argumentos invalidos para o filho das specs\n')
        raise SystemExit(int(CodigoFilho.ARGUMENTOS))


def argumentos(argv):
    ap = _Argumentos(prog='desdobra.specs.filho', add_help=False)
    ap.add_argument('arquivo')
    ap.add_argument('pasta_saida')
    ap.add_argument('--formato', required=True, choices=FORMATOS)
    ap.add_argument('--orcamento-bytes', type=int, required=True)
    ap.add_argument('--escala-recorte', type=float, required=True)
    a = ap.parse_args(argv)
    if a.orcamento_bytes < 1 or a.escala_recorte <= 0:
        ap.error('orcamento')
    return a


def importar_bibliotecas():
    """Tudo o que carrega biblioteca nativa entra antes do gancho de auditoria (o PDFium e o Pillow)."""
    import csv  # noqa: F401
    import email  # noqa: F401
    import email.policy  # noqa: F401
    import html.parser  # noqa: F401
    import PIL.Image  # noqa: F401
    import PIL.PngImagePlugin  # noqa: F401
    import pypdfium2  # noqa: F401
    import pypdfium2.raw  # noqa: F401
    import jsonschema  # noqa: F401
    from desdobra import contratos, limites
    limites.carregar()
    contratos.carregar_esquema(ESQUEMA_LEITURA)
    contratos._validador(ESQUEMA_LEITURA)


def linha_saida(codigo):
    sys.stdout.write(json.dumps({'esquema': ESQUEMA_SAIDA, 'codigo': int(codigo), 'arquivo': ARQUIVO_LEITURA}) + '\n')
    sys.stdout.flush()


def _limpo(texto):
    return ' '.join((texto or '').split())


def _decodificar(dados):
    for cod in ('utf-8-sig', 'cp1252'):
        try:
            return dados.decode(cod)
        except UnicodeDecodeError:
            continue
    return dados.decode('utf-8', 'replace')


def _trecho(pagina=None, texto='', **campos):
    t = {'pagina': pagina, 'texto': texto, 'caixa': None, 'linha': None, 'coluna': None, 'tabela': None,
         'linha_tabela': None, 'rotulo': None, 'secao': None, 'papel': 'texto'}
    t.update(campos)
    return t


# ------------------------------------------------------------------ PDF
def ler_pdf(dados, pasta, escala):
    import pypdfium2 as pdfium
    from desdobra.arquivos import gravar_bytes_atomico, sha256_bytes
    if not dados.startswith(ASSINATURA_PDF):
        raise Recusa('formato', 'O arquivo não começa com a assinatura de PDF.', CodigoFilho.RECUSADO)
    try:
        doc = pdfium.PdfDocument(dados)
    except pdfium.PdfiumError:
        raise Recusa('malformado', 'O PDF não abre: a estrutura não bate com o formato, ou ele tem senha.',
                     CodigoFilho.RECUSADO) from None
    paginas, trechos = [], []
    try:
        for i in range(len(doc)):
            pag = doc[i]
            largura, altura = pag.get_size()
            tp = pag.get_textpage()
            pedacos = []
            for r in range(tp.count_rects()):
                x0, y0, x1, y1 = tp.get_rect(r)
                texto = tp.get_text_bounded(x0, y0, x1, y1)
                if texto and texto.strip():
                    pedacos.append(_trecho(i + 1, texto.replace('\r', ' ').replace('\n', ' '),
                                           caixa=[round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)]))  # numero-neutro: casas de exibicao
            tp.close()
            registro = {'numero': i + 1, 'largura_pt': round(largura, 2), 'altura_pt': round(altura, 2),  # numero-neutro: casas de exibicao
                        'tem_texto': bool(pedacos), 'recorte': None, 'recorte_sha256': None}
            if not pedacos:
                imagem = pag.render(scale=escala).to_pil()
                buf = io.BytesIO()
                imagem.save(buf, format='PNG')
                nome = 'p%02d.png' % (i + 1)
                gravar_bytes_atomico(Path(pasta) / nome, buf.getvalue())
                registro.update(recorte=nome, recorte_sha256=sha256_bytes(buf.getvalue()))
            pag.close()
            paginas.append(registro)
            trechos.extend(pedacos)
    except pdfium.PdfiumError:
        raise Recusa('malformado', 'Uma página do PDF não abre.', CodigoFilho.RECUSADO) from None
    finally:
        doc.close()
    return paginas, trechos, None


# ------------------------------------------------------------------ HTML
def ler_html(dados):
    from html.parser import HTMLParser

    class Leitor(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.ignorar = 0
            self.texto = []
            self.linha_texto = None
            self.trechos = []
            self.secao = None
            self.titulo = None
            self.no_titulo = False
            self.pilha = []          # (tag, papel): papel em tabela, linha, celula ou None
            self.tabelas = []        # {indice, cabecalho, linhas, linha_atual, cabecalho_na_linha}
            self.n_tabelas = 0

        def _papel(self, tag, attrs):
            classes = set((dict(attrs).get('class') or '').split())
            if tag == 'table' or (tag == 'div' and 'table' in classes):
                return 'tabela'
            if tag == 'tr' or (tag == 'div' and 'row' in classes and self.tabelas):
                return 'linha'
            if tag in ('td', 'th') or (tag == 'div' and 'col' in classes and self.tabelas and
                                        self.tabelas[-1]['linha_atual'] is not None):
                return 'celula'
            return None

        def _descarregar(self, papel_fim=None):
            texto = _limpo(''.join(self.texto))
            self.texto = []
            linha = self.linha_texto
            self.linha_texto = None
            if not texto:
                return
            if self.tabelas and self.tabelas[-1]['celula'] is not None:
                self.tabelas[-1]['celula'].append(texto)
                return
            self.trechos.append(_trecho(1, texto, linha=linha, secao=self.secao))

        def handle_starttag(self, tag, attrs):
            if tag in TAGS_IGNORADAS:
                self.ignorar += 1
                return
            if tag == 'title':
                self.no_titulo = True
                return
            if tag == 'br' or tag in TAGS_BLOCO:
                self._descarregar()
            papel = self._papel(tag, attrs) if tag in ('table', 'tr', 'td', 'th', 'div') else None
            classes = set((dict(attrs).get('class') or '').split())
            if papel == 'tabela':
                self.n_tabelas += 1
                self.tabelas.append({'indice': self.n_tabelas, 'cabecalho': None, 'n_linhas': 0, 'linha_atual': None,
                                     'cabecalho_na_linha': False, 'celula': None, 'linha_html': self.getpos()[0]})
            elif papel == 'linha':
                t = self.tabelas[-1]
                t['linha_atual'] = []
                t['cabecalho_na_linha'] = 'table-title' in classes or t['cabecalho'] is None
                t['linha_html'] = self.getpos()[0]
            elif papel == 'celula':
                t = self.tabelas[-1]
                t['celula'] = []
                if tag == 'th':
                    t['cabecalho_na_linha'] = True
            if tag != 'br':
                self.pilha.append((tag, papel))

        def handle_startendtag(self, tag, attrs):
            if tag == 'br':
                self._descarregar()

        def handle_endtag(self, tag):
            if tag in TAGS_IGNORADAS:
                self.ignorar = max(0, self.ignorar - 1)
                return
            if tag == 'title':
                self.no_titulo = False
                return
            if tag in TAGS_BLOCO:
                self._descarregar()
            # fecha ate a tag aberta correspondente (HTML salvo nem sempre fecha tudo)
            while self.pilha:
                aberta, papel = self.pilha.pop()
                self._fechar_papel(papel)
                if aberta == tag:
                    break
            if tag in TITULOS and self.trechos:
                self.secao = self.trechos[-1]['texto']

        def _fechar_papel(self, papel):
            if not self.tabelas or papel is None:
                return
            t = self.tabelas[-1]
            if papel == 'celula' and t['celula'] is not None and t['linha_atual'] is not None:
                t['linha_atual'].append(' '.join(t['celula']))
                t['celula'] = None
            elif papel == 'linha' and t['linha_atual'] is not None:
                celulas = t['linha_atual']
                t['linha_atual'] = None
                t['n_linhas'] += 1
                eh_cabecalho = t['cabecalho_na_linha'] and t['cabecalho'] is None
                if eh_cabecalho:
                    t['cabecalho'] = celulas
                for col, texto in enumerate(celulas, 1):
                    if not texto:
                        continue
                    rotulo = None
                    if not eh_cabecalho and t['cabecalho'] and col <= len(t['cabecalho']):
                        rotulo = t['cabecalho'][col - 1] or None
                    self.trechos.append(_trecho(1, texto, linha=t['linha_html'], coluna=col, tabela=t['indice'],
                                                linha_tabela=t['n_linhas'], rotulo=rotulo, secao=self.secao,
                                                papel='cabecalho' if eh_cabecalho else 'celula'))
            elif papel == 'tabela':
                self.tabelas.pop()

        def handle_data(self, data):
            if self.ignorar:
                return
            if self.no_titulo:
                self.titulo = _limpo((self.titulo or '') + ' ' + data) or None
                return
            if data.strip() and self.linha_texto is None:
                self.linha_texto = self.getpos()[0]
            self.texto.append(data)

    leitor = Leitor()
    leitor.feed(_decodificar(dados))
    leitor.close()
    leitor._descarregar()
    return [{'numero': 1, 'largura_pt': None, 'altura_pt': None, 'tem_texto': bool(leitor.trechos), 'recorte': None,
             'recorte_sha256': None}], leitor.trechos, leitor.titulo


# ------------------------------------------------------------------ CSV e texto
def ler_csv(dados):
    import csv
    texto = _decodificar(dados)
    try:
        dialeto = csv.Sniffer().sniff(texto[:AMOSTRA_CSV], delimiters=',;\t')
    except csv.Error:
        dialeto = csv.excel
    linhas = list(csv.reader(io.StringIO(texto), dialeto))
    trechos, cabecalho = [], None
    for n, linha in enumerate(linhas, 1):
        if not any(c.strip() for c in linha):
            continue
        if cabecalho is None:
            cabecalho = [_limpo(c) for c in linha]
            for col, c in enumerate(cabecalho, 1):
                if c:
                    trechos.append(_trecho(1, c, linha=n, coluna=col, tabela=1, linha_tabela=1, papel='cabecalho'))
            continue
        for col, c in enumerate(linha, 1):
            if _limpo(c):
                rotulo = cabecalho[col - 1] if col <= len(cabecalho) and cabecalho[col - 1] else None
                trechos.append(_trecho(1, _limpo(c), linha=n, coluna=col, tabela=1, linha_tabela=n, rotulo=rotulo,
                                       papel='celula'))
    return [{'numero': 1, 'largura_pt': None, 'altura_pt': None, 'tem_texto': bool(trechos), 'recorte': None,
             'recorte_sha256': None}], trechos, None


def ler_texto(dados, eml):
    if eml:
        import email
        import email.policy
        msg = email.message_from_bytes(dados, policy=email.policy.default)
        partes = []
        for parte in msg.walk():
            if parte.get_content_type() == 'text/plain' and not parte.is_attachment():
                try:
                    partes.append(parte.get_content())
                except (LookupError, UnicodeDecodeError):
                    partes.append(_decodificar(parte.get_payload(decode=True) or b''))
        texto = '\n'.join(partes)
    else:
        texto = _decodificar(dados)
    trechos = [_trecho(1, _limpo(l), linha=n) for n, l in enumerate(texto.splitlines(), 1) if _limpo(l)]
    return [{'numero': 1, 'largura_pt': None, 'altura_pt': None, 'tem_texto': bool(trechos), 'recorte': None,
             'recorte_sha256': None}], trechos, None


# ------------------------------------------------------------------ execucao
def executar(a, gancho, info):
    import hashlib

    import pypdfium2
    from desdobra import __version__

    with open(a.arquivo, 'rb') as f:
        dados = f.read()
    info['sha256'] = hashlib.sha256(dados).hexdigest()
    info['bytes'] = len(dados)
    info['leitor'] = {'motor': __version__, 'pypdfium2': str(pypdfium2.PYPDFIUM_INFO), 'pdfium': str(pypdfium2.PDFIUM_INFO)}
    if a.formato == 'pdf':
        paginas, trechos, titulo = ler_pdf(dados, a.pasta_saida, a.escala_recorte)
    elif a.formato == 'html':
        paginas, trechos, titulo = ler_html(dados)
    elif a.formato == 'csv':
        paginas, trechos, titulo = ler_csv(dados)
    else:
        paginas, trechos, titulo = ler_texto(dados, a.arquivo.lower().endswith('.eml'))
    del dados
    if gancho.bloqueios:
        raise Recusa('auditoria', 'O gancho de auditoria barrou uma ação do processo de leitura da folha.',
                     CodigoFilho.AUDITORIA)
    conferir_tetos(trechos)
    return paginas, trechos, titulo


def conferir_tetos(trechos):
    """Folha com trecho longo demais ou trechos demais (uma folha hostil, ou que nao e folha de spec) e recusada
    inteira, com o tipo da recusa: o processo principal nunca recebe texto sem limite."""
    from desdobra import limites
    if len(trechos) > limites.valor('specs.trechos_max'):
        raise Recusa('trechos_demais', 'A folha tem trechos de texto demais para uma folha de spec.', CodigoFilho.RECUSADO)
    if any(len(t['texto']) > limites.valor('specs.trecho_caracteres_max') for t in trechos):
        raise Recusa('trecho_longo', 'A folha tem um trecho de texto longo demais para uma folha de spec.',
                     CodigoFilho.RECUSADO)
    por_pagina = {}
    for t in trechos:
        if t['caixa'] is not None:
            por_pagina[t['pagina']] = por_pagina.get(t['pagina'], 0) + 1
    if por_pagina and max(por_pagina.values()) > limites.valor('specs.pdf_trechos_por_pagina_max'):
        raise Recusa('trechos_demais', 'Uma página do PDF tem pedaços de texto demais para uma folha de spec.',
                     CodigoFilho.RECUSADO)


def _gravar(pasta, a, info, gancho, resultado=None, recusa=None):
    from desdobra import contratos
    paginas, trechos, titulo = resultado or ([], [], None)
    dados = {'esquema': ESQUEMA_LEITURA, 'leitor': info.get('leitor') or {'motor': '', 'pypdfium2': '', 'pdfium': ''},
             'origem': {'sha256': info.get('sha256'), 'bytes': info.get('bytes')}, 'formato': a.formato,
             'escala_recorte': float(a.escala_recorte),
             'situacao': 'recusada' if recusa else 'lida', 'recusa': None, 'titulo': titulo,
             'paginas': paginas, 'trechos': trechos,
             'auditoria': {'instalado': bool(gancho and gancho.instalado),
                           'bloqueios': len(gancho.bloqueios) if gancho else 0}}
    if recusa:
        dados['recusa'] = {'tipo': recusa.tipo, 'motivo': recusa.motivo, 'codigo': int(recusa.codigo)}
    contratos.gravar(Path(pasta) / ARQUIVO_LEITURA, dados, ESQUEMA_LEITURA)


def main(argv=None):
    a = argumentos(sys.argv[1:] if argv is None else argv)
    linha = sys.stdin.buffer.readline()
    if linha != LINHA_LIBERAR:
        sys.stderr.write('o filho das specs nao recebeu a liberacao do isolador\n')
        return int(CodigoFilho.ARGUMENTOS)
    importar_bibliotecas()
    from desdobra import PASTA_MOTOR
    from desdobra.leitor import auditoria
    pasta = Path(a.pasta_saida)
    pasta.mkdir(parents=True, exist_ok=True)
    gancho = auditoria.Gancho(a.arquivo, pasta, auditoria.raizes_do_ambiente(PASTA_MOTOR))
    gancho.instalar()
    info = {}
    try:
        resultado = executar(a, gancho, info)
        _gravar(pasta, a, info, gancho, resultado=resultado)
        linha_saida(CodigoFilho.OK)
        return int(CodigoFilho.OK)
    except Recusa as r:
        if gancho.bloqueios and r.tipo != 'auditoria':
            r = Recusa('auditoria', 'O gancho de auditoria barrou uma ação do processo de leitura da folha.',
                       CodigoFilho.AUDITORIA)
        _gravar(pasta, a, info, gancho, recusa=r)
        linha_saida(r.codigo)
        return int(r.codigo)
    except MemoryError:
        r = Recusa('memoria', 'A leitura da folha passou do orçamento de memória.', CodigoFilho.MEMORIA)
        try:
            _gravar(pasta, a, info, gancho, recusa=r)
            linha_saida(r.codigo)
        except MemoryError:
            pass
        return int(CodigoFilho.MEMORIA)
    except Exception:
        if gancho.bloqueios:
            r = Recusa('auditoria', 'O gancho de auditoria barrou uma ação do processo de leitura da folha.',
                       CodigoFilho.AUDITORIA)
            _gravar(pasta, a, info, gancho, recusa=r)
            linha_saida(r.codigo)
            return int(r.codigo)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return int(CodigoFilho.BUG)


if __name__ == '__main__':
    sys.exit(main())
