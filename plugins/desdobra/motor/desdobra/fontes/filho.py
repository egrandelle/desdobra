# -*- coding: utf-8 -*-
"""Processo filho das fontes: o unico codigo que parseia arquivo de fonte enviado pela agencia.

O arquivo de fonte e entrada nao confiavel, porque o leitor de fonte tambem e superficie de ataque
(arquitetura-v1.md, 4.5 e 7.1). Por isso ele e lido como o PSD: num processo filho isolado pela plataforma
(teto de memoria, 1 processo, tempo de relogio no pai) e com o mesmo gancho de auditoria do leitor
(desdobra.leitor.auditoria). O processo principal nunca importa o fontTools para abrir arquivo de fonte.

Chamada:
    python -I -B -m desdobra.fontes.filho <arquivo> <pasta_saida> --orcamento-bytes N

Ordem:
  1. le os argumentos e espera a linha 'iniciar' na entrada padrao (o isolador so a manda depois de confinar);
  2. importa o fontTools (com o brotli do WOFF2) e instala o gancho de auditoria;
  3. le os bytes do arquivo para a memoria e reconhece o formato pela assinatura;
  4. abre com o fontTools a partir de io.BytesIO (WOFF e WOFF2 sao descompactados na memoria; a colecao TTC e
     aberta face por face) e le so as tabelas name, cmap, OS/2, head, hhea e maxp. Variable font (tabela fvar)
     e recusada;
  5. grava leitura.json (leitura-fonte/1) em <pasta_saida>, de forma atomica.

O filho nunca grava contorno, glifo, atlas nem os bytes da fonte: so nomes, metricas, a cobertura do cmap em
faixas de codigos e marcas de licenca achadas na tabela name (codigos, nunca o texto). Na saida padrao, no
maximo uma linha JSON (filho/1). Codigos: 0 lida; 3 recusada; 4 memoria; 5 auditoria; 2 argumentos; 1 bug.
"""
import argparse
import enum
import io
import json
import re
import struct
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
ESQUEMA_LEITURA = 'leitura-fonte/1'
ARQUIVO_LEITURA = 'leitura.json'
# tabelas que o filho le; o resto do arquivo nunca e decodificado (contornos ficam como bytes, sem uso)
TABELAS_OBRIGATORIAS = ('head', 'hhea', 'maxp', 'cmap', 'name')
# name IDs da tabela name (especificacao OpenType, fato do formato)
NOME_COPYRIGHT, NOME_FAMILIA, NOME_ESTILO, NOME_ID_UNICO, NOME_COMPLETO, NOME_VERSAO, NOME_PS = 0, 1, 2, 3, 4, 5, 6  # numero-neutro: name IDs da especificacao OpenType
NOME_FAMILIA_TIPOGRAFICA, NOME_ESTILO_TIPOGRAFICO = 16, 17  # numero-neutro: name IDs da especificacao OpenType
# name IDs com texto de marca, fabricante, descricao e licenca, onde aparecem as marcas de kit web e de uso
NOMES_COM_MARCAS = (0, 3, 5, 7, 8, 9, 10, 11, 12, 13, 14)  # numero-neutro: name IDs da especificacao OpenType
TAMANHO_CABECALHO_SFNT = 12  # numero-neutro: offset table do sfnt (especificacao OpenType)
TAMANHO_REGISTRO_TABELA = 16  # numero-neutro: table record do sfnt (especificacao OpenType)


class Recusa(Exception):
    def __init__(self, tipo, motivo, codigo, medidas=None):
        super().__init__(motivo)
        self.tipo, self.motivo, self.codigo, self.medidas = tipo, motivo, codigo, medidas or {}


class _Argumentos(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write('argumentos invalidos para o filho das fontes\n')
        raise SystemExit(int(CodigoFilho.ARGUMENTOS))


def argumentos(argv):
    ap = _Argumentos(prog='desdobra.fontes.filho', add_help=False)
    ap.add_argument('arquivo')
    ap.add_argument('pasta_saida')
    ap.add_argument('--orcamento-bytes', type=int, required=True)
    a = ap.parse_args(argv)
    if a.orcamento_bytes < 1:
        ap.error('orcamento')
    return a


def importar_bibliotecas():
    """Tudo o que e pesado entra antes do gancho de auditoria (DLL do brotli e modulos das tabelas)."""
    import brotli  # noqa: F401
    import fontTools  # noqa: F401
    import fontTools.ttLib  # noqa: F401
    import fontTools.ttLib.sfnt  # noqa: F401
    import fontTools.ttLib.ttCollection  # noqa: F401
    import fontTools.ttLib.woff2  # noqa: F401
    from fontTools.ttLib.tables import (O_S_2f_2, _c_m_a_p, _f_v_a_r, _h_e_a_d, _h_h_e_a, _h_m_t_x,  # noqa: F401
                                        _m_a_x_p, _n_a_m_e)
    import jsonschema  # noqa: F401
    from desdobra import contratos, limites
    limites.carregar()
    contratos.carregar_esquema(ESQUEMA_LEITURA)
    contratos._validador(ESQUEMA_LEITURA)


def linha_saida(codigo):
    sys.stdout.write(json.dumps({'esquema': ESQUEMA_SAIDA, 'codigo': int(codigo), 'arquivo': ARQUIVO_LEITURA}) + '\n')
    sys.stdout.flush()


# ------------------------------------------------------------------ leitura de uma face
def _texto_do_registro(r):
    try:
        return r.toUnicode()
    except Exception:  # noqa: BLE001 - registro com codificacao desconhecida: fica de fora
        return None


def _nomes(tabela, ids):
    """Todos os textos, sem repetir, dos registros com estes name IDs (Mac e Windows)."""
    out = []
    for r in tabela.names:
        if r.nameID in ids:
            t = _texto_do_registro(r)
            if t and t.strip() and t not in out:
                out.append(t.strip())
    return out


def _primeiro(tabela, ident):
    """O texto preferido de um name ID: o registro do Windows em ingles, ou o primeiro que decodifica."""
    t = tabela.getDebugName(ident)
    if t:
        return t.strip() or None
    lista = _nomes(tabela, (ident,))
    return lista[0] if lista else None


def _faixas(codigos):
    """[[inicio, fim], ...] das faixas continuas de codigos Unicode do cmap (inclusive)."""
    faixas = []
    for c in sorted(codigos):
        if faixas and c == faixas[-1][1] + 1:
            faixas[-1][1] = c
        else:
            faixas.append([c, c])
    return faixas


def _marcas(tabela, os2):
    """Codigos das marcas de licenca achadas no arquivo, pelas expressoes do registro de limites."""
    from desdobra import limites
    textos = ' \n '.join(_nomes(tabela, NOMES_COM_MARCAS)).casefold()
    marcas = []
    for codigo, limite_id in (('kit_web', 'fontes.marcas_kit_web'), ('proibe_desktop', 'fontes.marcas_proibe_desktop'),
                              ('ofl', 'fontes.marcas_ofl')):
        if any(re.search(p, textos) for p in limites.valor(limite_id)):
            marcas.append(codigo)
    if os2 is not None and any(os2.fsType & int(b) for b in limites.valor('fontes.fs_type_bits_restritos')):
        marcas.append('fs_type_restrito')
    return marcas


def ler_face(fonte, indice, colecao=None):
    for tag in TABELAS_OBRIGATORIAS:
        if tag not in fonte:
            raise Recusa('malformada', 'O arquivo de fonte não tem uma das tabelas obrigatórias.', CodigoFilho.RECUSADO,
                         {'tabela': tag})
    if 'fvar' in fonte:
        raise Recusa('variavel', 'Variable font (tabela fvar) fica fora da v1.', CodigoFilho.RECUSADO)
    nome = fonte['name']
    head, hhea, maxp = fonte['head'], fonte['hhea'], fonte['maxp']
    os2 = fonte['OS/2'] if 'OS/2' in fonte else None
    cmap = fonte.getBestCmap() or {}
    face = {
        'indice': indice,
        'nomes': {'ps': _nomes(nome, (NOME_PS,)), 'familia': _primeiro(nome, NOME_FAMILIA),
                  'estilo': _primeiro(nome, NOME_ESTILO), 'familia_tipografica': _primeiro(nome, NOME_FAMILIA_TIPOGRAFICA),
                  'estilo_tipografico': _primeiro(nome, NOME_ESTILO_TIPOGRAFICO),
                  'nome_completo': _primeiro(nome, NOME_COMPLETO), 'id_unico': _nomes(nome, (NOME_ID_UNICO,)),
                  'versao': _primeiro(nome, NOME_VERSAO)},
        'contornos': 'cff' if 'CFF ' in fonte else ('cff2' if 'CFF2' in fonte else 'glyf'),
        'n_glifos': int(maxp.numGlyphs),
        'head': {'unidades_por_em': int(head.unitsPerEm), 'revisao': round(float(head.fontRevision), 5),  # numero-neutro: casas do Fixed 16.16
                 'mac_style': int(head.macStyle)},
        'hhea': {'ascender': int(hhea.ascent), 'descender': int(hhea.descent), 'line_gap': int(hhea.lineGap)},
        'os2': None,
        'cmap': _faixas(cmap.keys()),
        'n_codigos': len(cmap),
        'marcas': _marcas(nome, os2),
        'colecao': colecao,
    }
    if os2 is not None:
        face['os2'] = {'versao': int(os2.version), 'us_weight_class': int(os2.usWeightClass),
                       'us_width_class': int(os2.usWidthClass), 'fs_type': int(os2.fsType),
                       'fs_selection': int(os2.fsSelection), 's_typo_ascender': int(os2.sTypoAscender),
                       's_typo_descender': int(os2.sTypoDescender), 's_typo_line_gap': int(os2.sTypoLineGap),
                       'us_win_ascent': int(os2.usWinAscent), 'us_win_descent': int(os2.usWinDescent),
                       's_cap_height': int(getattr(os2, 'sCapHeight', 0) or 0) or None,
                       's_x_height': int(getattr(os2, 'sxHeight', 0) or 0) or None}
    return face


def diretorios_da_colecao(dados):
    """Para cada face da TTC: deslocamento e tamanho do diretorio de tabelas e se ele pode ser copiado para o
    inicio do arquivo sem cobrir dado de tabela (os deslocamentos da colecao contam do inicio do arquivo).
    Com isso o processo principal serve a face pedida ao Chromium so copiando bytes, sem parsear a fonte."""
    try:
        n = struct.unpack('>I', dados[8:12])[0]  # numero-neutro: campo numFonts do cabecalho TTC
        desl = struct.unpack('>%dI' % n, dados[12:12 + 4 * n])  # numero-neutro: cabecalho TTC
    except struct.error:
        raise Recusa('malformada', 'O cabeçalho da coleção de fontes não bate com o tamanho do arquivo.',
                     CodigoFilho.RECUSADO) from None
    out = []
    for o in desl:
        try:
            n_tab = struct.unpack('>H', dados[o + 4:o + 6])[0]  # numero-neutro: campo numTables da offset table
            tamanho = TAMANHO_CABECALHO_SFNT + TAMANHO_REGISTRO_TABELA * n_tab
            regs = [struct.unpack('>4sIII', dados[o + TAMANHO_CABECALHO_SFNT + TAMANHO_REGISTRO_TABELA * i:
                                                  o + TAMANHO_CABECALHO_SFNT + TAMANHO_REGISTRO_TABELA * (i + 1)])
                    for i in range(n_tab)]
        except struct.error:
            raise Recusa('malformada', 'O diretório de tabelas de uma face da coleção não bate com o tamanho do arquivo.',
                         CodigoFilho.RECUSADO) from None
        primeiro = min((r[2] for r in regs), default=0)
        out.append({'deslocamento_diretorio': int(o), 'tamanho_diretorio': int(tamanho),
                    'emendavel': bool(regs) and primeiro >= tamanho and o + tamanho <= len(dados)})
    return out


def executar(a, gancho, info):
    import hashlib

    from fontTools.ttLib import TTFont
    from fontTools.ttLib.ttCollection import TTCollection

    from desdobra import __version__, arquivos
    import fontTools

    with open(a.arquivo, 'rb') as f:
        dados = f.read()
    info['sha256'] = hashlib.sha256(dados).hexdigest()
    info['bytes'] = len(dados)
    formato = None
    for assinatura, fmt in arquivos.FORMATOS_FONTE_POR_ASSINATURA:
        if dados.startswith(assinatura):
            formato = fmt
            break
    info['formato'] = formato
    info['leitor'] = {'motor': __version__, 'fonttools': fontTools.version}
    if formato is None:
        if dados.startswith(arquivos.ASSINATURAS_TYPE1):
            raise Recusa('type1', 'Fonte Type 1 fica fora da v1.', CodigoFilho.RECUSADO)
        raise Recusa('formato', 'O arquivo não começa com a assinatura de OTF, TTF, TTC, WOFF ou WOFF2.',
                     CodigoFilho.RECUSADO)
    faces = []
    try:
        if formato == 'ttc':
            diretorios = diretorios_da_colecao(dados)
            colecao = TTCollection(io.BytesIO(dados), lazy=True)
            if not colecao.fonts:
                raise Recusa('malformada', 'A coleção de fontes não tem nenhuma face.', CodigoFilho.RECUSADO)
            for i, fonte in enumerate(colecao.fonts):
                faces.append(ler_face(fonte, i, diretorios[i] if i < len(diretorios) else None))
        else:
            fonte = TTFont(io.BytesIO(dados), lazy=True)
            faces.append(ler_face(fonte, 0))
    except (Recusa, MemoryError, PermissionError):
        raise
    except Exception as e:  # noqa: BLE001 - o fontTools nao e endurecido: qualquer erro de parse e arquivo malformado
        raise Recusa('malformada', 'O arquivo de fonte não abre: a estrutura não bate com o formato.',
                     CodigoFilho.RECUSADO, {'erro': type(e).__name__}) from None
    del dados
    if gancho.bloqueios:
        raise Recusa('auditoria', 'O gancho de auditoria barrou uma ação do processo de leitura da fonte.',
                     CodigoFilho.AUDITORIA, {'bloqueios': len(gancho.bloqueios)})
    return faces


def _gravar(pasta, info, gancho, faces=None, recusa=None):
    from desdobra import contratos
    dados = {'esquema': ESQUEMA_LEITURA, 'leitor': info.get('leitor') or {'motor': '', 'fonttools': ''},
             'origem': {'sha256': info.get('sha256'), 'bytes': info.get('bytes')}, 'formato': info.get('formato'),
             'situacao': 'recusada' if recusa else 'lida', 'recusa': None, 'faces': faces or [],
             'auditoria': {'instalado': bool(gancho and gancho.instalado),
                           'bloqueios': len(gancho.bloqueios) if gancho else 0}}
    if recusa:
        dados['recusa'] = {'tipo': recusa.tipo, 'motivo': recusa.motivo, 'codigo': int(recusa.codigo),
                           'medidas': {k: v for k, v in recusa.medidas.items()
                                       if isinstance(v, (int, float, str, bool)) or v is None}}
    contratos.gravar(Path(pasta) / ARQUIVO_LEITURA, dados, ESQUEMA_LEITURA)


def main(argv=None):
    a = argumentos(sys.argv[1:] if argv is None else argv)
    linha = sys.stdin.buffer.readline()
    if linha != LINHA_LIBERAR:
        sys.stderr.write('o filho das fontes nao recebeu a liberacao do isolador\n')
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
        faces = executar(a, gancho, info)
        _gravar(pasta, info, gancho, faces=faces)
        linha_saida(CodigoFilho.OK)
        return int(CodigoFilho.OK)
    except Recusa as r:
        if gancho.bloqueios and r.tipo != 'auditoria':
            r = Recusa('auditoria', 'O gancho de auditoria barrou uma ação do processo de leitura da fonte.',
                       CodigoFilho.AUDITORIA, {'bloqueios': len(gancho.bloqueios)})
        _gravar(pasta, info, gancho, recusa=r)
        linha_saida(r.codigo)
        return int(r.codigo)
    except MemoryError:
        r = Recusa('memoria', 'A leitura da fonte passou do orçamento de memória.', CodigoFilho.MEMORIA)
        try:
            _gravar(pasta, info, gancho, recusa=r)
            linha_saida(r.codigo)
        except MemoryError:
            pass
        return int(CodigoFilho.MEMORIA)
    except Exception:
        if gancho.bloqueios:
            r = Recusa('auditoria', 'O gancho de auditoria barrou uma ação do processo de leitura da fonte.',
                       CodigoFilho.AUDITORIA, {'bloqueios': len(gancho.bloqueios)})
            _gravar(pasta, info, gancho, recusa=r)
            linha_saida(r.codigo)
            return int(r.codigo)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return int(CodigoFilho.BUG)


if __name__ == '__main__':
    sys.exit(main())
