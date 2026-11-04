# -*- coding: utf-8 -*-
"""Processo filho das pilhas do render: compoe com o psd-tools as camadas sem texto de cada pilha do contrato.

O PSD e entrada nao confiavel: este filho roda como o do leitor (arquitetura-v1.md, 7.1), no isolador da plataforma
(teto de memoria, 1 processo, tempo de relogio no pai), com o mesmo gancho de auditoria (desdobra.leitor.auditoria),
e abre o documento do mesmo jeito: confere os 26 bytes do cabecalho contra o orcamento antes de alocar, monta a
vista sem os blocos dos smart objects e abre com os limites de alocacao e de parse da 1.26.0. Nada de smart object
e aberto: a composicao usa os pixels que o Photoshop gravou para cada camada.

Chamada:
    python -I -B -m desdobra.render.filho_pilhas <kv> <pasta_saida> --orcamento-bytes N

Ordem:
  1. espera a linha 'iniciar' na entrada padrao (o isolador so a manda depois de confinar);
  2. importa as bibliotecas e instala o gancho de auditoria;
  3. le pedido.json (gravado pelo processo principal na pasta de saida): o sha256 do KV e as pilhas, cada uma com
     a chave e os indices das camadas (na ordem de descendants(), a mesma da estrutura do leitor);
  4. abre o documento, confere o sha256 e compoe cada pilha em faixas horizontais (o mesmo resultado do composto
     inteiro, com menos memoria), no espaco de cor do documento (sem converter pelo ICC), so com as camadas da pilha
     e os grupos acima delas;
  5. grava cada pilha recortada na caixa de tinta como <sha256>.png e o indice pilhas.json.

Na saida padrao, no maximo uma linha JSON (filho/1). Codigos: 0 ok; 2 argumentos; 3 recusado; 4 memoria;
5 auditoria; 1 bug.
"""
import argparse
import enum
import hashlib
import io
import json
import math
import sys
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
ARQUIVO_PEDIDO = 'pedido.json'
ARQUIVO_INDICE = 'pilhas.json'
PIXELS_POR_FAIXA = 2_000_000  # numero-neutro: tamanho da faixa de composicao; nao muda o resultado
LINHAS_MIN_FAIXA = 32  # numero-neutro: idem
ALFA_CHEIO = 255  # numero-neutro: alfa de 8 bits
COMPRESSAO_PNG = 1  # numero-neutro: nivel de compressao do PNG; nao muda os pixels


class Recusa(Exception):
    def __init__(self, tipo, motivo, codigo):
        super().__init__(motivo)
        self.tipo, self.motivo, self.codigo = tipo, motivo, codigo


class _Argumentos(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write('argumentos invalidos para o filho das pilhas\n')
        raise SystemExit(int(CodigoFilho.ARGUMENTOS))


def argumentos(argv):
    ap = _Argumentos(prog='desdobra.render.filho_pilhas', add_help=False)
    ap.add_argument('arquivo')
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
    import PIL.PngImagePlugin  # noqa: F401
    import scipy.interpolate  # noqa: F401
    import scipy.ndimage  # noqa: F401
    import scipy.spatial  # noqa: F401
    import psd_tools  # noqa: F401
    import psd_tools.composite  # noqa: F401
    import psd_tools.composite.composite  # noqa: F401
    import psd_tools.composite.effects  # noqa: F401
    import psd_tools.composite.paint  # noqa: F401
    import psd_tools.composite.vector  # noqa: F401
    import psd_tools.composite.adjustments  # noqa: F401
    import jsonschema  # noqa: F401
    from desdobra import arquivos, limites  # noqa: F401
    from desdobra.leitor import adaptador, cabecalho, indice  # noqa: F401
    limites.carregar()
    try:
        import aggdraw  # noqa: F401
    except ImportError:
        pass


def abrir(f, orcamento):
    """Abre o documento como o filho do leitor (cabecalho, vista sem smart objects, limites da 1.26.0)."""
    from psd_tools import PSDImage

    from desdobra import limites
    from desdobra.leitor import adaptador, cabecalho, indice
    f.seek(0)
    try:
        cab = cabecalho.ler(f.read(cabecalho.TAMANHO))
        cabecalho.conferir(cab, orcamento, adaptador.EIXO_MAX_PSD_TOOLS)
    except cabecalho.CabecalhoInvalido as e:
        raise Recusa(e.tipo, e.motivo, CodigoFilho.RECUSADO) from None
    try:
        secoes = indice.ler_secoes(f, 0, None)
    except (indice.ErroIndice, cabecalho.CabecalhoInvalido, ValueError, OSError):
        raise Recusa('leitura', 'A estrutura do arquivo não bate com os comprimentos gravados.',
                     CodigoFilho.RECUSADO) from None
    teto_alloc = min(int(limites.valor('leitor.max_alloc_bytes')), int(orcamento))
    try:
        vista = indice.VistaSemSmart(f, secoes)
        return PSDImage.open(io.BufferedReader(vista), max_alloc_bytes=teto_alloc,
                             parse_limits=adaptador.limites_de_parse(orcamento))
    except MemoryError:
        raise Recusa('memoria', 'A abertura passou do orçamento de memória.', CodigoFilho.MEMORIA) from None
    except (ValueError, OSError) as e:
        if adaptador.eh_estouro_de_orcamento(e):
            raise Recusa('memoria', 'A abertura passou do orçamento de memória.', CodigoFilho.MEMORIA) from None
        raise Recusa('leitura', 'A biblioteca de leitura recusou o arquivo.', CodigoFilho.RECUSADO) from None


def compor_pilha(psd, camadas, indices):
    """RGBA uint8 do canvas inteiro com so as camadas da pilha (e os grupos acima delas), em faixas."""
    import numpy as np
    from psd_tools.constants import ColorMode
    W, H = psd.width, psd.height
    alvo = set()
    for i in indices:
        L = camadas[i]
        alvo.add(id(L))
        p = L.parent
        while p is not None and p is not psd:
            alvo.add(id(p))
            p = p.parent

    def filtro(L):
        return id(L) in alvo and L.is_visible()

    n_alvo = max(1, int(math.ceil(W * H / PIXELS_POR_FAIXA)))
    passo = max(LINHAS_MIN_FAIXA, int(math.ceil(H / n_alvo)))
    rgba = np.zeros((H, W, 4), np.uint8)  # numero-neutro: canais RGBA
    for y0 in range(0, H, passo):
        y1 = min(H, y0 + passo)
        if psd.color_mode in (ColorMode.RGB, ColorMode.GRAYSCALE):
            rgba[y0:y1] = _faixa_rgb_ou_cinza(psd, (0, y0, W, y1), filtro)
            continue
        im = psd.composite(viewport=(0, y0, W, y1), layer_filter=filtro, ignore_preview=True, apply_icc=False)
        if im is not None:
            rgba[y0:y1] = np.asarray(im.convert('RGBA'))
        del im
    return rgba


def _faixa_rgb_ou_cinza(psd, viewport, filtro):
    """RGBA uint8 de uma faixa de documento RGB ou cinza, direto dos arrays float do psd-tools.

    O composite_pil da 1.26.0 trunca o alfa float32 com astype(uint8): sobre fundo opaco, b + s - b*s da
    0.99999994 e a pilha sai com alfa 254 (composite.py:466-468 e :486). Aqui o alfa e arredondado; a cor
    passa pela mesma conta do composite_pil (clip(255 * cor).astype(uint8)), byte a byte igual a de antes.
    Mesmos argumentos que psd.composite passa: fundo branco transparente, sem forcar vetor, sem ICC.
    """
    import numpy as np
    from psd_tools.composite import composite as compor_float
    from psd_tools.constants import ColorMode
    cor, _, alfa = compor_float(psd, color=1.0, alpha=0.0, viewport=viewport, layer_filter=filtro, force=False)
    canais = 1 if psd.color_mode == ColorMode.GRAYSCALE else 3  # numero-neutro: canais do modo de cor
    bytes_cor = np.clip(255 * cor[:, :, :canais], 0, 255).astype(np.uint8)  # numero-neutro: escala de 8 bits
    if canais == 1:
        bytes_cor = np.repeat(bytes_cor, 3, axis=2)  # numero-neutro: cinza vira RGB como no convert('RGBA')
    bytes_alfa = np.rint(np.clip(alfa[:, :, :1], 0, 1) * ALFA_CHEIO).astype(np.uint8)
    return np.concatenate((bytes_cor, bytes_alfa), 2)


def executar(a, gancho):
    import numpy as np
    from PIL import Image

    from desdobra import arquivos
    pasta = Path(a.pasta_saida)
    pedido = json.loads((pasta / ARQUIVO_PEDIDO).read_text(encoding='utf-8'))
    with open(a.arquivo, 'rb') as f:
        h = hashlib.sha256()
        while bloco := f.read(1 << 20):  # numero-neutro: bloco de leitura do hash
            h.update(bloco)
        if h.hexdigest() != pedido['kv_sha256']:
            raise Recusa('kv_mudou', 'O KV não é o mesmo do laudo.', CodigoFilho.RECUSADO)
        psd = abrir(f, a.orcamento_bytes)
        camadas = list(psd.descendants())
        indice_saida = {}
        for p in pedido['pilhas']:
            if any(i >= len(camadas) for i in p['indices']):
                raise Recusa('estrutura_mudou', 'A pilha pede uma camada que o documento não tem.', CodigoFilho.RECUSADO)
            rgba = compor_pilha(psd, camadas, p['indices'])
            nz = np.nonzero(rgba[..., 3])
            if not len(nz[0]):
                indice_saida[p['chave']] = {'sha256': None, 'caixa': None}
                continue
            caixa = [int(nz[1].min()), int(nz[0].min()), int(nz[1].max()) + 1, int(nz[0].max()) + 1]
            recorte = np.ascontiguousarray(rgba[caixa[1]:caixa[3], caixa[0]:caixa[2]])
            del rgba
            buf = io.BytesIO()
            Image.fromarray(recorte, 'RGBA').save(buf, format='PNG', compress_level=COMPRESSAO_PNG)
            dados = buf.getvalue()
            sha = hashlib.sha256(dados).hexdigest()
            arquivos.gravar_bytes_atomico(pasta / ('%s.png' % sha), dados)
            indice_saida[p['chave']] = {'sha256': sha, 'caixa': caixa,
                                        'alfa_cheio': bool((recorte[..., 3] == ALFA_CHEIO).all())}
            del recorte, dados, buf
    from desdobra.leitor import adaptador
    arquivos.gravar_json_atomico(pasta / ARQUIVO_INDICE, {'kv_sha256': pedido['kv_sha256'], 'pilhas': indice_saida,
                                                          'psd_tools': adaptador.versao_psd_tools(),
                                                          'auditoria': {'bloqueios': list(gancho.bloqueios)}})


def main(argv=None):
    a = argumentos(sys.argv[1:] if argv is None else argv)
    if sys.stdin.buffer.readline() != LINHA_LIBERAR:
        sys.stderr.write('o filho das pilhas nao recebeu a liberacao do isolador\n')
        return int(CodigoFilho.ARGUMENTOS)
    importar_bibliotecas()
    import logging

    from desdobra import PASTA_MOTOR
    from desdobra.leitor import auditoria
    pasta = Path(a.pasta_saida)
    gancho = auditoria.Gancho(a.arquivo, pasta, auditoria.raizes_do_ambiente(PASTA_MOTOR))
    gancho.instalar()
    lg = logging.getLogger('psd_tools')
    lg.addHandler(logging.NullHandler())
    lg.propagate = False
    try:
        executar(a, gancho)
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
    except Exception as e:  # noqa: BLE001
        from desdobra.leitor import adaptador
        if gancho.bloqueios:
            linha_saida(CodigoFilho.AUDITORIA, tipo='auditoria')
            return int(CodigoFilho.AUDITORIA)
        if isinstance(e, (ValueError, OSError)) and adaptador.eh_estouro_de_orcamento(e):
            linha_saida(CodigoFilho.MEMORIA, tipo='memoria')
            return int(CodigoFilho.MEMORIA)
        traceback.print_exc(file=sys.stderr)
        return int(CodigoFilho.BUG)


if __name__ == '__main__':
    sys.exit(main())
