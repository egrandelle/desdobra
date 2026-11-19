# -*- coding: utf-8 -*-
"""Processo filho da silhueta: decodifica o alfa dos assets das bases e grava a grade de cada um (decisao 199, 3).

O asset e um PNG gravado pelo filho do leitor, mas os pixels vem do PSD do cliente. Decodificar imagem grande e codigo
nativo (o Pillow), entao a decodificacao fica aqui, num processo filho com o mesmo isolador do leitor e da cor (teto de
memoria, 1 processo, tempo de relogio no pai) e com o mesmo gancho de auditoria. O pai recebe so a grade.

Chamada:
    python -I -B -m desdobra.ds.silhueta_filho <pedido.json> <pasta_assets> <pasta_saida> --orcamento-bytes N

pedido.json e gravado pelo proprio motor: o numero de celulas, o limiar e os sha256 pedidos, com as dimensoes que o
leitor gravou. Ordem:
  1. le os argumentos e espera a linha 'iniciar' na entrada padrao (o isolador so a manda depois de confinar);
  2. importa o Pillow, o numpy e os esquemas, le o pedido e instala o gancho de auditoria (a leitura permitida
     depois disso e so a pasta dos assets do laudo, alem do ambiente);
  3. para cada sha256: le o PNG, confere o sha256 dos bytes, a assinatura PNG e as dimensoes, e grava
     <pasta_saida>/<sha256>.json (silhueta/1); o asset que nao confere fica sem arquivo;
  4. grava auditoria.json em <pasta_saida>.
Na saida padrao, no maximo uma linha JSON (filho/1). Codigos: 0 feito (mesmo com asset sem silhueta); 4 memoria;
5 auditoria; 2 argumentos; 1 bug. Nunca abre PSD, smart object nem arquivo linkado.
"""
import argparse
import enum
import json
import sys
from pathlib import Path


class CodigoFilho(enum.IntEnum):
    OK = 0
    BUG = 1
    ARGUMENTOS = 2
    MEMORIA = 4
    AUDITORIA = 5


LINHA_LIBERAR = b'iniciar\n'
ESQUEMA_SAIDA = 'filho/1'
ESQUEMA = 'silhueta/1'
ARQUIVO_AUDITORIA = 'auditoria.json'
ASSINATURA_PNG = b'\x89PNG\r\n\x1a\n'


class _Argumentos(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write('argumentos invalidos para o filho da silhueta\n')
        raise SystemExit(int(CodigoFilho.ARGUMENTOS))


def argumentos(argv):
    ap = _Argumentos(prog='desdobra.ds.silhueta_filho', add_help=False)
    ap.add_argument('pedido')
    ap.add_argument('pasta_assets')
    ap.add_argument('pasta_saida')
    ap.add_argument('--orcamento-bytes', type=int, required=True)
    a = ap.parse_args(argv)
    if a.orcamento_bytes < 1:
        ap.error('orcamento')
    return a


def importar_bibliotecas():
    """Tudo o que e pesado entra antes do gancho de auditoria (o Pillow com os plugins, o numpy e os esquemas)."""
    import numpy  # noqa: F401
    from PIL import Image, PngImagePlugin  # noqa: F401
    import jsonschema  # noqa: F401
    from desdobra import contratos, limites
    from desdobra.ds import silhueta  # noqa: F401
    Image.preinit()
    Image.init()
    limites.carregar()
    contratos.carregar_esquema(ESQUEMA)
    contratos._validador(ESQUEMA)


def linha_saida(codigo):
    sys.stdout.write(json.dumps({'esquema': ESQUEMA_SAIDA, 'codigo': int(codigo), 'arquivo': ARQUIVO_AUDITORIA}) + '\n')
    sys.stdout.flush()


def _alfa(dados):
    """O canal alfa do PNG (matriz uint8); sem canal alfa, tudo opaco."""
    import io

    import numpy as np
    from PIL import Image
    with Image.open(io.BytesIO(dados)) as img:
        if img.format != 'PNG':
            raise ValueError('asset fora do formato do motor')
        if img.mode == 'L':
            return np.asarray(img, dtype=np.uint8)
        if 'A' not in img.getbands():
            return np.full((img.height, img.width), 255, np.uint8)  # numero-neutro: alfa cheio em 8 bits
        return np.asarray(img.getchannel('A'), dtype=np.uint8)


def silhueta_do_asset(dados, sha, dims, celulas, limiar):
    """O documento silhueta/1 do asset (sem as camadas, que o pai acrescenta), ou None quando o asset nao confere."""
    import hashlib

    from desdobra import __version__, limites
    from desdobra.ds import silhueta
    if not dados.startswith(ASSINATURA_PNG) or hashlib.sha256(dados).hexdigest() != sha:
        return None
    alfa = _alfa(dados)
    h, w = alfa.shape[:2]
    if [w, h] != [int(v) for v in dims]:
        return None
    grade = silhueta.grade_do_alfa(alfa, celulas, limiar)
    del alfa
    return {'esquema': ESQUEMA, 'sha256': sha, 'arquivo_sha256': None, 'origem_alfa': None, 'dims': [int(w), int(h)],
            'grade': grade, 'limiar': limites.obter('ds.sujeito_limiar_alfa').citacao(),
            'celulas': limites.obter('ds.silhueta_celulas').citacao(), 'camadas': [], 'motor': __version__}


def _gravar_auditoria(pasta, gancho, recusa=None):
    dados = {'instalado': bool(gancho and gancho.instalado), 'bloqueios': len(gancho.bloqueios) if gancho else 0,
             'recusa': recusa}
    (Path(pasta) / ARQUIVO_AUDITORIA).write_text(json.dumps(dados), encoding='utf-8')


def main(argv=None):
    a = argumentos(sys.argv[1:] if argv is None else argv)
    linha = sys.stdin.buffer.readline()
    if linha != LINHA_LIBERAR:
        sys.stderr.write('o filho da silhueta nao recebeu a liberacao do isolador\n')
        return int(CodigoFilho.ARGUMENTOS)
    importar_bibliotecas()
    from PIL import Image

    from desdobra import PASTA_MOTOR, contratos
    from desdobra.leitor import auditoria
    with open(a.pedido, encoding='utf-8') as f:
        pedido = json.load(f)
    pasta = Path(a.pasta_saida)
    pasta.mkdir(parents=True, exist_ok=True)
    assets = Path(a.pasta_assets)
    gancho = auditoria.Gancho(a.pedido, pasta, auditoria.raizes_do_ambiente(PASTA_MOTOR) + [str(assets)])
    gancho.instalar()
    try:
        for item in pedido.get('itens') or []:
            sha = str(item['sha256'])
            if len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):  # numero-neutro: hex do sha256
                continue
            try:
                with open(assets / ('%s.png' % sha), 'rb') as f:
                    dados = f.read()
                doc = silhueta_do_asset(dados, sha, item['dims'], pedido['celulas'], pedido['limiar'])
                del dados
            except (OSError, ValueError, Image.DecompressionBombError):
                # o asset ilegivel fica sem silhueta (o pai confere pela caixa, com o aviso); o alarme sobe
                if gancho.bloqueios:
                    raise
                continue
            if gancho.bloqueios:
                raise PermissionError('auditoria')
            if doc is not None:
                contratos.gravar(pasta / ('%s.json' % sha), doc, ESQUEMA)
        if gancho.bloqueios:
            raise PermissionError('auditoria')
        _gravar_auditoria(pasta, gancho)
        linha_saida(CodigoFilho.OK)
        return int(CodigoFilho.OK)
    except MemoryError:
        try:
            _gravar_auditoria(pasta, gancho, 'memoria')
            linha_saida(CodigoFilho.MEMORIA)
        except MemoryError:
            pass
        return int(CodigoFilho.MEMORIA)
    except Exception:
        if gancho.bloqueios:
            _gravar_auditoria(pasta, gancho, 'auditoria')
            linha_saida(CodigoFilho.AUDITORIA)
            return int(CodigoFilho.AUDITORIA)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return int(CodigoFilho.BUG)


if __name__ == '__main__':
    sys.exit(main())
