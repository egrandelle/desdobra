# -*- coding: utf-8 -*-
"""Material sintetico dos testes de specs, gerado na hora: PDF com texto escrito a mao (rotulo e valor em pedacos
separados, como na folha PME), PDF escaneado (so uma imagem por pagina), HTML salvo no jeito das paginas de midia
kit, CSV exportado pelo DA e e-mail colado. Nenhuma folha real entra no repositorio."""
import struct
import zlib

# larguras da Helvetica (AFM padrao, por 1000 unidades) dos caracteres que os testes encostam um no outro
LARGURA_HELVETICA = {**{d: 556 for d in '0123456789'}, 'p': 556, 'x': 500, ' ': 278}
CORPO = 8


def largura(texto, corpo=CORPO):
    return sum(LARGURA_HELVETICA.get(c, 556) for c in texto) * corpo / 1000


def _pdf_texto(s):
    b = s.encode('cp1252')
    return b.replace(b'\\', b'\\\\').replace(b'(', b'\\(').replace(b')', b'\\)')


def _montar_pdf(paginas_conteudo, recursos):
    """paginas_conteudo: [bytes do content stream]; recursos: dict de recursos (bytes) por pagina."""
    objs = []

    def novo(corpo):
        objs.append(corpo)
        return len(objs)

    fonte = novo(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>')
    catalogo = novo(None)
    paginas = novo(None)
    kids = []
    for conteudo, extra in zip(paginas_conteudo, recursos):
        c = novo(b'<< /Length %d >>\nstream\n' % len(conteudo) + conteudo + b'\nendstream')
        rec = b'<< /Font << /F1 %d 0 R >> %s >>' % (fonte, extra or b'')
        kids.append(novo(b'<< /Type /Page /Parent %d 0 R /MediaBox [0 0 720 405] /Resources %s /Contents %d 0 R >>'
                         % (paginas, rec, c)))
    objs[catalogo - 1] = b'<< /Type /Catalog /Pages %d 0 R >>' % paginas
    objs[paginas - 1] = b'<< /Type /Pages /Kids [%s] /Count %d >>' % (b' '.join(b'%d 0 R' % k for k in kids), len(kids))
    saida = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    deslocamentos = []
    for i, corpo in enumerate(objs, 1):
        deslocamentos.append(len(saida))
        saida += b'%d 0 obj\n' % i + corpo + b'\nendobj\n'
    xref = len(saida)
    saida += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objs) + 1)
    for d in deslocamentos:
        saida += b'%010d 00000 n \n' % d
    saida += b'trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objs) + 1, catalogo, xref)
    return bytes(saida)


def pdf_com_texto(paginas):
    """paginas: [[(x, y, texto)]] em pontos (pagina de 720 x 405, origem embaixo a esquerda)."""
    conteudos = []
    for itens in paginas:
        partes = [b'BT /F1 %d Tf %.2f %.2f Td (%s) Tj ET' % (CORPO, x, y, _pdf_texto(t)) for x, y, t in itens]
        conteudos.append(b'\n'.join(partes))
    return _montar_pdf(conteudos, [b''] * len(paginas))


def pdf_escaneado(n_paginas=2, largura_px=40, altura_px=24):
    """PDF so com imagem (sem camada de texto), como uma folha escaneada."""
    bruto = b''.join(bytes([200, 30 * (i % 8), 90]) * largura_px for i in range(altura_px))
    return _montar_pdf_com_imagem([b'q 720 0 0 405 0 0 cm /Im1 Do Q'] * n_paginas, zlib.compress(bruto), largura_px,
                                  altura_px)


def _montar_pdf_com_imagem(conteudos, dados_img, w, h):
    objs = []

    def novo(corpo):
        objs.append(corpo)
        return len(objs)

    img = novo(b'<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceRGB /BitsPerComponent 8 '
               b'/Filter /FlateDecode /Length %d >>\nstream\n' % (w, h, len(dados_img)) + dados_img + b'\nendstream')
    catalogo = novo(None)
    paginas = novo(None)
    kids = []
    for conteudo in conteudos:
        c = novo(b'<< /Length %d >>\nstream\n' % len(conteudo) + conteudo + b'\nendstream')
        kids.append(novo(b'<< /Type /Page /Parent %d 0 R /MediaBox [0 0 720 405] /Resources << /XObject << /Im1 %d 0 R >> '
                         b'>> /Contents %d 0 R >>' % (paginas, img, c)))
    objs[catalogo - 1] = b'<< /Type /Catalog /Pages %d 0 R >>' % paginas
    objs[paginas - 1] = b'<< /Type /Pages /Kids [%s] /Count %d >>' % (b' '.join(b'%d 0 R' % k for k in kids), len(kids))
    saida = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    deslocamentos = []
    for i, corpo in enumerate(objs, 1):
        deslocamentos.append(len(saida))
        saida += b'%d 0 obj\n' % i + corpo + b'\nendobj\n'
    xref = len(saida)
    saida += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objs) + 1)
    for d in deslocamentos:
        saida += b'%010d 00000 n \n' % d
    saida += b'trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objs) + 1, catalogo, xref)
    return bytes(saida)


# ------------------------------------------------------------------ folha no jeito da PME, com as armadilhas
ESQ, ROT, VAL = 60, 380, 530


def _tabela(linhas, topo=330, passo=23):
    itens = []
    for i, (rotulo, valor) in enumerate(linhas):
        y = topo - i * passo
        if rotulo:
            itens.append((ROT, y, rotulo))
        if valor:
            itens.append((VAL, y, valor))
    return itens


def _imagem_5mb():
    return [('Imagem', None), ('Formato ', 'JPG ou PNG'), ('Peso (MB) ', 'até 5MB')]


def _video():
    return [('Vídeo', None), ('Extensão ', 'MP4'), ('Peso (MB) ', 'até 20MB')]


def folha_pme_sintetica():
    """PDF de 5 paginas no jeito da folha PME: rotulo e valor em pedacos separados na mesma linha, secao de video com
    outro peso, o mesmo 1080x1920 integral num circuito e com barra de 72 px noutro, o 1280x720 com barra de 48 px
    (com o valor partido em dois pedacos, "1280px x 720" + "px"), praca que mistura estado e cidade em duas linhas e
    a entrada de impresso com "120m x 175m" e virgula decimal."""
    p1 = [(ESQ, 330, 'Mobiliário'), (ESQ, 316, 'Urbano')]
    p2 = [(ESQ, 330, 'Abrigo de Ônibus'), (ESQ, 310, 'Rio de Janeiro, Paraná e '), (ESQ, 298, 'Belo Horizonte')]
    p2 += _tabela([('Formato (Área total) ', '1080px x 1920px'), ('Área útil ', '1080px x 1920px'),
                   ('Barra inferior ', '-')] + _video() + _imagem_5mb())
    p3 = [(ESQ, 330, 'São Paulo'), (ESQ, 316, 'Shopping Exemplo'), (ESQ, 60, '*Não será aceito material animado')]
    p3 += _tabela([('Formato (Área total) ', '1080px x 1920px'), ('Área útil ', '1080px x 1848px'),
                   ('Barra inferior ', '72px')] + _video() + _imagem_5mb())
    p4 = [(ESQ, 330, 'Edifícios'), (ESQ, 316, 'Comerciais ')]
    pedaco = '1280px x 720'
    p4 += [(ROT, 330, 'Formato (Área total) '), (VAL, 330, pedaco), (VAL + largura(pedaco) + 0.3, 330, 'px')]
    p4 += _tabela([('Área útil ', '1280px x 672px'), ('Barra inferior ', '48px')] + _video() + _imagem_5mb(), topo=307)
    p5 = [(ESQ, 330, 'Abrigo de Ônibus'), (ESQ, 316, 'Campinas')]
    p5 += _tabela([('Formato (Área total) ', '120m x 175m'), ('Área útil ', '1,17m x 1,71m'), ('Imagem', None),
                   ('Formato ', 'PDF'), ('Tamanho do arquivo (PDF) ', '48MB')])
    p5 += [(330, 40, '- Envie o arquivo final por e-mail')]
    return pdf_com_texto([p1, p2, p3, p4, p5])


# ------------------------------------------------------------------ HTML no jeito das paginas de midia kit
def _li(nome, valor):
    return '<li><span class="specification-name"> %s </span><span class="specification-value"> %s </span></li>' % (nome, valor)


def html_ficha(titulo, itens, descricao=''):
    lis = ''.join(_li(n, v) for n, v in itens)
    return ('<!doctype html><html><head><meta charset="utf-8"><title>MIDIA KIT | %s</title><style>.x{}</style>'
            '<script>var a = "peso 999KB";</script></head><body><nav><ul><li>Vídeo</li><li>Imagens</li></ul></nav>'
            '<div class="specification-listing-description">%s</div><div class="card"><h3>%s</h3>'
            '<ul class="specification-data-list">%s</ul></div></body></html>' % (titulo, descricao, titulo, lis))


def html_orientacoes():
    linhas = [('P', '320x50', '100', '100'), ('G', '970x250/300x600', '250', '500')]
    corpo = ''.join('<div class="row"><div class="col">%s</div><div class="col">%s</div><div class="col">%s</div>'
                    '<div class="col">%s</div></div>' % l for l in linhas)
    return ('<!doctype html><html><head><meta charset="utf-8"><title>Orientações</title></head><body>'
            '<h2 id="peso">Peso por tag</h2><div class="table"><div class="row table-title"><div class="col">Área</div>'
            '<div class="col">sizes (pixels)</div><div class="col">peso máximo <br>initial load (kb)</div>'
            '<div class="col">peso máximo <br>subload (kb)</div></div>%s</div>'
            '<h2 id="borda">Borda</h2><p class="text"> Banners que tenham o fundo da mesma cor da página deverão ter '
            'borda preta de 1 px. </p><h2 id="video">Vídeo</h2><p>Peso máximo: 10MB</p></body></html>' % corpo)


def html_vertical():
    return html_ficha('Vertical Exemplo', [('Dimensão', '1080x1920'), ('Peso do arquivo', 'até 500 KB'),
                                           ('arquivos permitidos', 'JPG , PNG')],
                      descricao='<b>Área de atenção</b><br>Considere deixar cerca de 14% (aprox. 250 pixels) das partes '
                                'superior e inferior sem texto.')


def html_meia_pagina():
    return html_ficha('Meia Exemplo', [('dimensão', '300x600'), ('peso (hosted)', 'até 250KB'),
                                       ('peso (tag)', 'até 550KB'), ('arquivos permitidos', 'JPG , PNG , GIF ANIMADO')],
                      descricao='Formato vertical padrão na proporção 300x600, ao lado do conteúdo.')


# ------------------------------------------------------------------ CSV e e-mail
def csv_do_da(colunas, linhas, separador=';'):
    texto = separador.join(colunas) + '\n' + ''.join(separador.join(l) + '\n' for l in linhas)
    return texto.encode('utf-8')


EMAIL = """Olá, equipe,

segue a especificação dos painéis da estação, conforme combinado.

Circuito: Estação Exemplo
Praça: Bahia e Salvador
Formato: 1080x1920
Área útil: 1080x1800
Barra inferior: 120px
Peso máximo:
2 MB
Tipos de arquivo: JPG ou PNG

Formato: 1920x1080
Peso máximo: 1,5 MB

Abraços.
"""


def png_de_tamanho(largura_px, altura_px, n_bytes):
    """Bytes que comecam como um PNG (assinatura e IHDR com a dimensao) e tem exatamente n_bytes. O validador le so
    o cabecalho: o resto e preenchimento."""
    ihdr = struct.pack('>IIBBBBB', largura_px, altura_px, 8, 2, 0, 0, 0)
    cab = b'\x89PNG\r\n\x1a\n' + struct.pack('>I', len(ihdr)) + b'IHDR' + ihdr + struct.pack('>I', zlib.crc32(b'IHDR' + ihdr))
    return cab + b'\x00' * (n_bytes - len(cab))


def jpeg_de_tamanho(largura_px, altura_px, n_bytes):
    """Cabecalho JPEG (SOI, APP0 e SOF0 com a dimensao) e preenchimento ate n_bytes."""
    app0 = b'\xff\xe0' + struct.pack('>H', 16) + b'JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
    sof = b'\xff\xc0' + struct.pack('>HBHHB', 11, 8, altura_px, largura_px, 1) + b'\x01\x11\x00'
    cab = b'\xff\xd8' + app0 + sof
    return cab + b'\x00' * (n_bytes - len(cab))
