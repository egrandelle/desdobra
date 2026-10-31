# -*- coding: utf-8 -*-
"""Processo filho da cor: o unico codigo que abre o perfil ICC do documento (dado de cliente) com o LittleCMS.

O perfil ICC vem do PSD do cliente e e entrada nao confiavel: o LittleCMS que o parseia e codigo nativo
(arquitetura-v1.md, 7.1, o processo principal nunca parseia dado de cliente). Por isso o perfil e aberto e as cores
sao convertidas aqui, num processo filho com o mesmo isolador do leitor e das fontes (teto de memoria, 1 processo,
tempo de relogio no pai) e com o mesmo gancho de auditoria. O pai recebe so numeros (e o nome do perfil).

Chamada:
    python -I -B -m desdobra.cor.filho <perfil.icc> <pedido.json> <pasta_saida> --orcamento-bytes N

pedido.json e gravado pelo proprio motor: intent, compensacao de ponto preto e as cores pedidas (rgb do documento em
8 bits e Lab). Ordem:
  1. le os argumentos e espera a linha 'iniciar' na entrada padrao (o isolador so a manda depois de confinar);
  2. importa o Pillow com o ImageCms, le o pedido e instala o gancho de auditoria (a unica leitura permitida
     depois disso e o arquivo do perfil);
  3. le o perfil para a memoria, abre com o LittleCMS a partir de io.BytesIO, monta a transformacao para sRGB e
     converte as cores;
  4. grava conversao.json (conversao-cor/1) em <pasta_saida>, de forma atomica.
Na saida padrao, no maximo uma linha JSON (filho/1). Codigos: 0 convertida (ou perfil ilegivel, com o motivo no
arquivo); 4 memoria; 5 auditoria; 2 argumentos; 1 bug.
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
ESQUEMA_CONVERSAO = 'conversao-cor/1'
ARQUIVO_CONVERSAO = 'conversao.json'


class _Argumentos(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write('argumentos invalidos para o filho da cor\n')
        raise SystemExit(int(CodigoFilho.ARGUMENTOS))


def argumentos(argv):
    ap = _Argumentos(prog='desdobra.cor.filho', add_help=False)
    ap.add_argument('perfil')
    ap.add_argument('pedido')
    ap.add_argument('pasta_saida')
    ap.add_argument('--orcamento-bytes', type=int, required=True)
    a = ap.parse_args(argv)
    if a.orcamento_bytes < 1:
        ap.error('orcamento')
    return a


def importar_bibliotecas():
    """Tudo o que e pesado entra antes do gancho de auditoria (DLL do LittleCMS e esquemas)."""
    from PIL import Image, ImageCms  # noqa: F401
    import jsonschema  # noqa: F401
    from desdobra import contratos, cor, limites  # noqa: F401
    limites.carregar()
    contratos.carregar_esquema(ESQUEMA_CONVERSAO)
    contratos._validador(ESQUEMA_CONVERSAO)
    # o perfil sRGB e o Lab de referencia sao do proprio LittleCMS, sem arquivo
    cor.perfil_srgb()


def linha_saida(codigo):
    sys.stdout.write(json.dumps({'esquema': ESQUEMA_SAIDA, 'codigo': int(codigo), 'arquivo': ARQUIVO_CONVERSAO}) + '\n')
    sys.stdout.flush()


def converter(dados_icc, pedido):
    """Abre o perfil e converte as cores pedidas. Devolve o conteudo de conversao-cor/1 (sem esquema e auditoria)."""
    from desdobra import cor
    parametros = cor.parametros(intent=pedido['intent'], compensacao_ponto_preto=pedido['compensacao_ponto_preto'],
                                perfil_embutido_na_saida=False)
    conv = cor.Conversor(dados_icc, parametros)
    saida = {'perfil': conv.perfil, 'tratamento': conv.tratamento, 'motivo': conv.motivo, 'rgb': [], 'lab': []}
    if not conv.converte:
        return saida
    for v8 in pedido.get('rgb') or []:
        saida['rgb'].append([list(v8), conv.rgb(v8)])
    for lab in pedido.get('lab') or []:
        saida['lab'].append([list(lab), conv.lab(lab)])
    return saida


def _gravar(pasta, gancho, conteudo):
    from desdobra import contratos
    dados = {'esquema': ESQUEMA_CONVERSAO, 'perfil': None, 'tratamento': None, 'motivo': None, 'rgb': [], 'lab': [],
             'recusa': None}
    dados.update(conteudo)
    dados['auditoria'] = {'instalado': bool(gancho and gancho.instalado),
                          'bloqueios': len(gancho.bloqueios) if gancho else 0}
    contratos.gravar(Path(pasta) / ARQUIVO_CONVERSAO, dados, ESQUEMA_CONVERSAO)


def main(argv=None):
    a = argumentos(sys.argv[1:] if argv is None else argv)
    linha = sys.stdin.buffer.readline()
    if linha != LINHA_LIBERAR:
        sys.stderr.write('o filho da cor nao recebeu a liberacao do isolador\n')
        return int(CodigoFilho.ARGUMENTOS)
    importar_bibliotecas()
    from desdobra import PASTA_MOTOR
    from desdobra.leitor import auditoria
    with open(a.pedido, encoding='utf-8') as f:
        pedido = json.load(f)
    pasta = Path(a.pasta_saida)
    pasta.mkdir(parents=True, exist_ok=True)
    gancho = auditoria.Gancho(a.perfil, pasta, auditoria.raizes_do_ambiente(PASTA_MOTOR))
    gancho.instalar()
    try:
        with open(a.perfil, 'rb') as f:
            dados = f.read()
        conteudo = converter(dados, pedido)
        del dados
        if gancho.bloqueios:
            raise PermissionError('auditoria')
        _gravar(pasta, gancho, conteudo)
        linha_saida(CodigoFilho.OK)
        return int(CodigoFilho.OK)
    except MemoryError:
        try:
            _gravar(pasta, gancho, {'recusa': 'memoria'})
            linha_saida(CodigoFilho.MEMORIA)
        except MemoryError:
            pass
        return int(CodigoFilho.MEMORIA)
    except Exception:
        if gancho.bloqueios:
            _gravar(pasta, gancho, {'recusa': 'auditoria'})
            linha_saida(CodigoFilho.AUDITORIA)
            return int(CodigoFilho.AUDITORIA)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return int(CodigoFilho.BUG)


if __name__ == '__main__':
    sys.exit(main())
