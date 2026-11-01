# -*- coding: utf-8 -*-
"""Processo filho do render: rasteriza os PDFs do texto com o PDFium e compoe o formato (arquitetura-v1.md, 4.11).

Por que um filho: o PDFium (pypdfium2) e o perfil ICC do documento so sao abertos em processo isolado, como o PSD e
a fonte (arquitetura-v1.md, 7.1); o processo principal nunca importa o pypdfium2. O filho roda no isolador da
plataforma e com o mesmo gancho de auditoria do leitor (desdobra.leitor.auditoria): le so o contrato, os assets das
pilhas, os arquivos confirmados dos linkados e o perfil do documento, e grava so na propria pasta de saida.

Os PDFs chegam pela entrada padrao, depois da linha de liberacao do isolador: uma linha JSON de cabecalho com o
tamanho de cada PDF e os bytes em seguida. O PDF nunca vai para disco: o pypdfium2 abre os bytes na memoria.

Chamada:
    python -I -B -m desdobra.render.filho <contrato.json> <pasta_saida> --orcamento-bytes N
    entrada padrao: 'iniciar' + cabecalho JSON (uma linha) + bytes dos PDFs

Composicao (valores do documento em 0..1, alfa pre-multiplicado, de baixo para cima):
  - pilha e linkado: mesclagem normal com a opacidade da entrada;
  - texto: cobertura de area do PDFium (supersample S, media de blocos S x S, sem o texto nativo do sistema) vezes
    a opacidade, misturada com o fundo pela formula do Photoshop com G sobre a curva do perfil do documento
    (desdobra.render.gama, desdobra.render.icc). Texto de varias cores: uma cobertura por cor, somadas;
  - no fim, os valores do documento vao para 8 bits e o LittleCMS converte para sRGB com o intent e a compensacao
    do job (desdobra.cor.Parametros). Documento sem perfil ja esta em sRGB.
Grava master.png e saida.json (medidas, versoes e tempos). Codigos: 0 ok; 2 argumentos; 3 recusado; 4 memoria;
5 auditoria; 1 bug.
"""
import argparse
import enum
import io
import json
import sys
import time
import traceback
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
ARQUIVO_SAIDA = 'saida.json'
ARQUIVO_MASTER = 'master.png'
PONTOS_POR_PX = 0.75  # numero-neutro: 72 pontos do PDF por 96 px do CSS
DPI_CSS = 96.0  # numero-neutro: px do CSS por polegada
DPI_PDF = 72.0  # numero-neutro: pontos do PDF por polegada
LADO_MAX_PDFIUM = 16384  # numero-neutro: lado do bitmap que o PDFium desenha com folga (o limite dele e menor que 32768)
PIXELS_BANDA = 8_000_000  # numero-neutro: pixels do PDFium por faixa (memoria); nao muda o resultado
ESCALA_8 = 255.0  # numero-neutro: 8 bits por canal
COMPRESSAO_PNG = 1  # numero-neutro: nivel de compressao do PNG; nao muda os pixels
FORMATOS_LINKADO = ('PNG', 'JPEG')


class Recusa(Exception):
    def __init__(self, tipo, motivo, codigo):
        super().__init__(motivo)
        self.tipo, self.motivo, self.codigo = tipo, motivo, codigo


class _Argumentos(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write('argumentos invalidos para o filho do render\n')
        raise SystemExit(int(CodigoFilho.ARGUMENTOS))


def argumentos(argv):
    ap = _Argumentos(prog='desdobra.render.filho', add_help=False)
    ap.add_argument('contrato')
    ap.add_argument('pasta_saida')
    ap.add_argument('--orcamento-bytes', type=int, required=True)
    a = ap.parse_args(argv)
    if a.orcamento_bytes < 1:
        ap.error('orcamento')
    return a


def linha_saida(codigo, **extra):
    sys.stdout.write(json.dumps(dict({'esquema': ESQUEMA_SAIDA, 'codigo': int(codigo)}, **extra)) + '\n')
    sys.stdout.flush()


def importar_bibliotecas():
    import numpy  # noqa: F401
    import PIL.Image  # noqa: F401
    import PIL.ImageCms  # noqa: F401
    import PIL.PngImagePlugin  # noqa: F401
    import PIL.JpegImagePlugin  # noqa: F401
    import PIL.TiffImagePlugin  # noqa: F401
    import pypdfium2  # noqa: F401
    import pypdfium2.raw  # noqa: F401
    from desdobra import cor, limites  # noqa: F401
    from desdobra.render import gama, icc  # noqa: F401
    limites.carregar()


# ------------------------------------------------------------------ PDFium
def cobertura_do_pdf(dados, largura, altura, regiao_l, regiao_a, supersample):
    """Cobertura de area (0..1) da pagina do PDF na regiao, com supersample e media de blocos, em faixas."""
    import numpy as np
    import pypdfium2 as pdfium
    import pypdfium2.raw as raw
    S = int(supersample)
    escala = DPI_CSS / DPI_PDF * S
    doc = pdfium.PdfDocument(dados)
    try:
        pg = doc[0]
        saida = np.zeros((regiao_a, regiao_l), np.float64)
        # o PDFium nao desenha bitmap mais largo que LADO_MAX_PDFIUM: a pagina larga vai em colunas
        coluna = max(1, min(regiao_l, LADO_MAX_PDFIUM // S))
        for c0 in range(0, regiao_l, coluna):
            c1 = min(regiao_l, c0 + coluna)
            faixa = max(1, PIXELS_BANDA // max(1, (c1 - c0) * S * S))
            for r0 in range(0, regiao_a, faixa):
                r1 = min(regiao_a, r0 + faixa)
                crop = (c0 * PONTOS_POR_PX, (altura - r1) * PONTOS_POR_PX, (largura - c1) * PONTOS_POR_PX,
                        r0 * PONTOS_POR_PX)
                bmp = pg.render(scale=escala, crop=crop, grayscale=True, fill_color=(255, 255, 255, 255),  # numero-neutro: fundo branco do bitmap
                                extra_flags=raw.FPDF_NO_NATIVETEXT, may_draw_forms=False)
                v = bmp.to_numpy()
                if v.ndim == 3:  # numero-neutro: bitmap com eixo de canal
                    v = v[..., 0]
                v = v[:(r1 - r0) * S, :(c1 - c0) * S].astype(np.float64)
                a = 1.0 - v / ESCALA_8
                hh, ww = a.shape[0] // S, a.shape[1] // S
                a = a[:hh * S, :ww * S].reshape(hh, S, ww, S).mean(axis=(1, 3))
                saida[r0:r0 + hh, c0:c0 + ww] = a
                del bmp, v, a
        pg.close()
    finally:
        doc.close()
    return saida


# ------------------------------------------------------------------ composicao
class Canvas:
    """Valores do documento pre-multiplicados (C) e alfa (A), em float64."""

    def __init__(self, largura, altura, fundo=None):
        import numpy as np
        self.w, self.h = largura, altura
        self.C = np.zeros((altura, largura, 3), np.float64)  # numero-neutro: canais RGB
        self.A = np.zeros((altura, largura), np.float64)
        if fundo is not None:
            self.C[...] = np.asarray(fundo, dtype=np.float64)
            self.A[...] = 1.0

    def sobre(self, rgba, x0, y0, opacidade=1.0):
        """Mesclagem normal de um RGBA uint8 com canto em (x0, y0)."""
        import numpy as np
        h, w = rgba.shape[:2]
        cx0, cy0, cx1, cy1 = max(0, x0), max(0, y0), min(self.w, x0 + w), min(self.h, y0 + h)
        if cx1 <= cx0 or cy1 <= cy0:
            return 0
        s = rgba[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0].astype(np.float64) / ESCALA_8
        a = s[..., 3] * float(opacidade)
        C, A = self.C[cy0:cy1, cx0:cx1], self.A[cy0:cy1, cx0:cx1]
        C *= (1.0 - a)[..., None]
        C += s[..., :3] * a[..., None]
        A *= (1.0 - a)
        A += a
        return int((a > 0).sum())

    def texto(self, a, F, x0, y0, G, curva):
        """Texto de cobertura a (h x w, ja com a opacidade) e cor F (h x w x 3) na regiao com canto (x0, y0)."""
        import numpy as np

        from desdobra.render import gama
        h, w = a.shape
        C, A = self.C[y0:y0 + h, x0:x0 + w], self.A[y0:y0 + h, x0:x0 + w]
        with np.errstate(invalid='ignore', divide='ignore'):
            B = np.where(A[..., None] > 0, C / np.maximum(A, 1e-300)[..., None], F)  # numero-neutro: so evita divisao por zero
        gm = gama.mistura_texto_photoshop(F, B, a[..., None], G, curva)
        novo_C = A[..., None] * gm + (1.0 - A)[..., None] * a[..., None] * F
        novo_A = A + (1.0 - A) * a
        C[...] = novo_C
        A[...] = novo_A

    def resultado(self):
        """(rgb uint8 no espaco do documento, alfa uint8)."""
        import numpy as np
        with np.errstate(invalid='ignore', divide='ignore'):
            cor = np.where(self.A[..., None] > 0, self.C / np.maximum(self.A, 1e-300)[..., None], 0.0)  # numero-neutro: so evita divisao por zero
        rgb = np.clip(np.round(cor * ESCALA_8), 0, ESCALA_8).astype(np.uint8)
        alfa = np.clip(np.round(self.A * ESCALA_8), 0, ESCALA_8).astype(np.uint8)
        return rgb, alfa


def _quad_para_coeficientes(quad, w, h):
    """Coeficientes da transformacao PERSPECTIVE do PIL que levam o canvas (relativo a caixa) a imagem w x h."""
    import numpy as np
    destino = [(0, 0), (w, 0), (w, h), (0, h)]
    linhas, b = [], []
    for (x, y), (u, v) in zip(quad, destino):
        linhas.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        linhas.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        b += [u, v]
    return [float(c) for c in np.linalg.solve(np.array(linhas, np.float64), np.array(b, np.float64))]


def desenhar_linkado(canvas, e, pasta_job, perfil_doc, registros):
    """O arquivo confirmado do linkado, colocado no quadrilatero da camada (ou na caixa, sem quadrilatero)."""
    import numpy as np
    from PIL import Image, ImageCms
    caminho = Path(pasta_job) / e['arquivo']
    dados = caminho.read_bytes()
    try:
        with Image.open(io.BytesIO(dados), formats=FORMATOS_LINKADO) as im:
            im.load()
            icc_asset = im.info.get('icc_profile')
            img = im.copy()
    except (OSError, ValueError, SyntaxError):
        raise Recusa('linkado_ilegivel', 'O arquivo do linkado não abriu como PNG ou JPEG.', CodigoFilho.RECUSADO) from None
    destino = perfil_doc if perfil_doc is not None else ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB'))
    alfa = img.getchannel('A') if img.mode in ('RGBA', 'LA', 'PA') else None
    if img.mode == 'P':
        img = img.convert('RGBA')
        alfa = img.getchannel('A')
    base = img.convert('CMYK' if img.mode == 'CMYK' else ('L' if img.mode in ('L', 'LA', 'I', 'I;16') else 'RGB'))
    if icc_asset:
        # o asset vai para o perfil do documento (decisoes-v1.md, 29/10, 8, revista em 31/10); sem perfil no
        # documento, para sRGB, que e como o documento sem perfil e tratado
        try:
            rgb = ImageCms.profileToProfile(base, ImageCms.ImageCmsProfile(io.BytesIO(icc_asset)), destino,
                                            outputMode='RGB')
        except (ImageCms.PyCMSError, OSError, ValueError):
            raise Recusa('linkado_perfil_ilegivel', 'O perfil de cor do linkado não converte.', CodigoFilho.RECUSADO) from None
        registros.append({'codigo': 'linkado_convertido_para_o_perfil_do_documento', 'entrada': e['id']})
    else:
        if base.mode == 'CMYK':
            registros.append({'codigo': 'linkado_cmyk_sem_perfil', 'entrada': e['id']})
        rgb = base.convert('RGB')
    rgb = rgb.convert('RGBA')
    if alfa is not None:
        rgb.putalpha(alfa)
    img = rgb
    if e.get('colocacao'):
        q = e['colocacao']
        quad = [(q[0], q[1]), (q[2], q[3]), (q[4], q[5]), (q[6], q[7])]
    else:
        x0, y0, x1, y1 = e['caixa']
        quad = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    xs, ys = [p[0] for p in quad], [p[1] for p in quad]
    bx0, by0 = int(np.floor(min(xs))), int(np.floor(min(ys)))
    bx1, by1 = int(np.ceil(max(xs))), int(np.ceil(max(ys)))
    rel = [(x - bx0, y - by0) for x, y in quad]
    coef = _quad_para_coeficientes(rel, img.width, img.height)
    colocada = img.transform((bx1 - bx0, by1 - by0), Image.Transform.PERSPECTIVE, coef, Image.Resampling.BICUBIC)
    return canvas.sobre(np.asarray(colocada), bx0, by0, e.get('opacidade', 1.0))


def executar(a, gancho, cabecalho, pdfs):
    import hashlib

    import numpy as np
    from PIL import Image, ImageCms

    from desdobra import arquivos, cor
    from desdobra.render import gama, icc
    t0 = time.perf_counter()
    tempos = {}
    pasta = Path(a.pasta_saida)
    contrato = json.loads(Path(a.contrato).read_text(encoding='utf-8'))
    pasta_job = Path(cabecalho['pasta_job'])
    doc = contrato['documento']
    W, H = int(contrato['formato']['largura']), int(contrato['formato']['altura'])
    G = cabecalho['G']
    S = int(cabecalho['supersample'])
    registros = []
    perfil_doc, curva, desc_curva = None, gama.CURVA_SRGB, {'tipo': 'srgb', 'motivo': 'documento_sem_perfil'}
    if doc.get('perfil'):
        dados_icc = (pasta_job / doc['perfil']['arquivo']).read_bytes()
        perfil_doc = ImageCms.ImageCmsProfile(io.BytesIO(dados_icc))
        try:
            dec, enc, desc_curva = icc.curva_do_perfil(dados_icc)
            curva = (dec, enc)
        except icc.ErroCurva as e:
            desc_curva = {'tipo': 'srgb', 'motivo': 'perfil_sem_curva_legivel', 'erro': str(e)}
            registros.append({'codigo': 'curva_srgb_no_lugar_da_do_perfil'})
    canvas = Canvas(W, H, doc.get('fundo'))
    tempos['preparo'] = round(time.perf_counter() - t0, 3)
    coberturas = {}
    t_pdf = 0.0
    por_entrada = {}
    for p in cabecalho['pdfs']:
        por_entrada.setdefault(p['entrada'], []).append(p)
    estatisticas = []
    for e in contrato['entradas']:
        t1 = time.perf_counter()
        if e['tipo'] == 'pilha':
            info = cabecalho['pilhas'].get(e['id'])
            if not info or not info.get('arquivo'):
                estatisticas.append({'id': e['id'], 'tipo': 'pilha', 'px': 0})
                continue
            with Image.open(info['arquivo']) as im:
                rgba = np.asarray(im.convert('RGBA'))
            n = canvas.sobre(rgba, info['caixa'][0], info['caixa'][1])
            estatisticas.append({'id': e['id'], 'tipo': 'pilha', 'px': n})
            del rgba
        elif e['tipo'] == 'linkado':
            n = desenhar_linkado(canvas, e, pasta_job, perfil_doc, registros)
            estatisticas.append({'id': e['id'], 'tipo': 'linkado', 'px': n})
        elif e['tipo'] == 'texto':
            x0, y0, x1, y1 = e['regiao']
            rw, rh = x1 - x0, y1 - y0
            soma = np.zeros((rh, rw), np.float64)
            F = np.zeros((rh, rw, 3), np.float64)  # numero-neutro: canais RGB
            alfa_cor = np.zeros((rh, rw), np.float64)
            for p in por_entrada.get(e['id'], []):
                tp = time.perf_counter()
                cob = cobertura_do_pdf(pdfs[p['pagina']], p['largura'], p['altura'], rw, rh, S)
                t_pdf += time.perf_counter() - tp
                v = e['valores_cor'][p['cor']]
                soma += cob
                F += cob[..., None] * np.asarray(v['rgb'], np.float64)
                alfa_cor += cob * float(v['alfa'])
            with np.errstate(invalid='ignore', divide='ignore'):
                primeira = np.asarray(e['valores_cor'][e['cores'][0]]['rgb'], np.float64)
                F = np.where(soma[..., None] > 0, F / np.maximum(soma, 1e-300)[..., None], primeira)  # numero-neutro: so evita divisao por zero
                alfa_cor = np.where(soma > 0, alfa_cor / np.maximum(soma, 1e-300), 1.0)  # numero-neutro: idem
            cobertura = np.clip(soma, 0.0, 1.0) * alfa_cor * float(e['opacidade'])
            canvas.texto(cobertura, F, x0, y0, G, curva)
            estatisticas.append({'id': e['id'], 'tipo': 'texto', 'layer_id': e['layer_id'],
                                 'px': int((cobertura > 0).sum()), 'cobertura_soma': round(float(cobertura.sum()), 3),
                                 'paginas': len(por_entrada.get(e['id'], []))})
            if cabecalho.get('guardar_coberturas'):
                coberturas[e['id']] = np.clip(soma, 0.0, 1.0).astype(np.float32)
            del soma, F, alfa_cor, cobertura
        tempos[e['id']] = round(time.perf_counter() - t1, 3)
    tempos['pdfium'] = round(t_pdf, 3)
    t2 = time.perf_counter()
    rgb, alfa = canvas.resultado()
    del canvas
    img = Image.fromarray(rgb, 'RGB')
    conversao = {'feita': False, 'motivo': 'documento_sem_perfil'}
    if perfil_doc is not None:
        par = cabecalho['parametros_cor']
        flags = ImageCms.Flags.BLACKPOINTCOMPENSATION if par['compensacao_ponto_preto'] else ImageCms.Flags.NONE
        img = ImageCms.profileToProfile(img, perfil_doc, cor.perfil_srgb(), renderingIntent=cor.INTENTS[par['intent']],
                                        flags=flags)
        conversao = {'feita': True, 'intent': par['intent'], 'compensacao_ponto_preto': par['compensacao_ponto_preto'],
                     'lcms': cor.versao_lcms()}
    opaco = bool((alfa == int(ESCALA_8)).all())
    if not opaco:
        img = img.convert('RGBA')
        img.putalpha(Image.fromarray(alfa, 'L'))
    buf = io.BytesIO()
    extra = {}
    if cabecalho['parametros_cor'].get('perfil_embutido_na_saida'):
        extra['icc_profile'] = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    img.save(buf, format='PNG', compress_level=COMPRESSAO_PNG, **extra)
    dados = buf.getvalue()
    arquivos.gravar_bytes_atomico(pasta / ARQUIVO_MASTER, dados)
    if coberturas:
        np.savez_compressed(pasta / 'coberturas.npz', **coberturas)
    tempos['saida'] = round(time.perf_counter() - t2, 3)
    tempos['total'] = round(time.perf_counter() - t0, 3)
    import pypdfium2.version as vp
    saida = {'master': {'arquivo': ARQUIVO_MASTER, 'sha256': hashlib.sha256(dados).hexdigest(), 'largura': W,
                        'altura': H, 'modo': img.mode},
             'versoes': {'pypdfium2': vp.PYPDFIUM_INFO.version if hasattr(vp.PYPDFIUM_INFO, 'version') else str(vp.PYPDFIUM_INFO),
                         'pdfium': str(vp.PDFIUM_INFO), 'numpy': np.__version__, 'pillow': Image.__version__},
             'curva': desc_curva, 'conversao': conversao, 'entradas': estatisticas, 'registros': registros,
             'tempos': tempos, 'auditoria': {'bloqueios': list(gancho.bloqueios)}}
    arquivos.gravar_json_atomico(pasta / ARQUIVO_SAIDA, saida)


def ler_entrada():
    """Cabecalho JSON e PDFs da entrada padrao (depois da linha de liberacao). Os PDFs ficam so na memoria."""
    fluxo = sys.stdin.buffer
    cabecalho = json.loads(fluxo.readline().decode('utf-8'))
    pdfs = {}
    for p in cabecalho['pdfs']:
        dados = fluxo.read(int(p['bytes']))
        if len(dados) != int(p['bytes']):
            raise Recusa('entrada', 'Os bytes do PDF chegaram incompletos.', CodigoFilho.RECUSADO)
        pdfs[p['pagina']] = dados
    return cabecalho, pdfs


def main(argv=None):
    a = argumentos(sys.argv[1:] if argv is None else argv)
    if sys.stdin.buffer.readline() != LINHA_LIBERAR:
        sys.stderr.write('o filho do render nao recebeu a liberacao do isolador\n')
        return int(CodigoFilho.ARGUMENTOS)
    importar_bibliotecas()
    from desdobra import PASTA_MOTOR
    from desdobra.leitor import auditoria
    try:
        cabecalho, pdfs = ler_entrada()
    except Recusa as r:
        linha_saida(r.codigo, tipo=r.tipo)
        return int(r.codigo)
    except (ValueError, OSError):
        linha_saida(CodigoFilho.RECUSADO, tipo='entrada')
        return int(CodigoFilho.RECUSADO)
    pasta = Path(a.pasta_saida)
    raizes = list(auditoria.raizes_do_ambiente(PASTA_MOTOR)) + [str(x) for x in cabecalho.get('leitura') or []]
    gancho = auditoria.Gancho(a.contrato, pasta, raizes)
    gancho.instalar()
    try:
        executar(a, gancho, cabecalho, pdfs)
        if gancho.bloqueios:
            linha_saida(CodigoFilho.AUDITORIA, tipo='auditoria')
            return int(CodigoFilho.AUDITORIA)
        linha_saida(CodigoFilho.OK)
        return int(CodigoFilho.OK)
    except Recusa as r:
        codigo = CodigoFilho.AUDITORIA if gancho.bloqueios else r.codigo
        linha_saida(codigo, tipo='auditoria' if gancho.bloqueios else r.tipo)
        return int(codigo)
    except MemoryError:
        linha_saida(CodigoFilho.MEMORIA, tipo='memoria')
        return int(CodigoFilho.MEMORIA)
    except Exception:  # noqa: BLE001
        if gancho.bloqueios:
            linha_saida(CodigoFilho.AUDITORIA, tipo='auditoria')
            return int(CodigoFilho.AUDITORIA)
        traceback.print_exc(file=sys.stderr)
        return int(CodigoFilho.BUG)


if __name__ == '__main__':
    sys.exit(main())
