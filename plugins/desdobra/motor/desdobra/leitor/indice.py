# -*- coding: utf-8 -*-
"""Leitura estrutural por deslocamento e indice proprio dos registros de smart object (lnk2, lnk3, lnkD, lnkE).

O que faz, sem carregar os dados dos smart objects:
  1. anda nas secoes do arquivo (cabecalho, modo de cor, recursos, camadas e mascaras, imagem) pelos
     comprimentos gravados;
  2. no fim da secao de camadas e mascaras, anda nos blocos marcados globais e, nos blocos lnk*, le so o
     cabecalho de cada registro: tipo (liFD embutido, liFE externo, liFA alias), unique_id, nome, tipo de
     arquivo, deslocamento e tamanho dos dados. Do linkado guarda so nome, tamanho e data; o caminho gravado
     e lido para andar no arquivo e descartado, nunca seguido;
  3. monta uma vista do arquivo sem os blocos lnk* (VistaSemSmart), que o filho passa ao PSDImage.open. Assim
     o psd-tools nao carrega os dados de todos os smart objects; o filho le do arquivo so o trecho de cada
     embutido, quando precisa (sha256 e abertura em filho proprio).

Os deslocamentos sao absolutos no arquivo de entrada, mesmo quando o documento e um recorte (smart object
aninhado): `base` e o inicio do recorte.

So o processo filho chama este modulo sobre arquivo de cliente.
"""
import datetime
import hashlib
import io
import struct

from desdobra.leitor import adaptador
from desdobra.leitor import cabecalho as cab

ASSINATURAS_BLOCO = (b'8BIM', b'8B64')
TAMANHO_LEITURA = 1 << 20  # numero-neutro: bloco de leitura de 1 MiB para o sha256, sem efeito no resultado
_MAGICOS = ((b'8BPS\x00\x01', 'psd'), (b'8BPS\x00\x02', 'psb'), (b'%PDF-', 'pdf'), (b'\x89PNG', 'png'),
            (b'\xff\xd8\xff', 'jpg'), (b'GIF8', 'gif'), (b'II*\x00', 'tiff'), (b'MM\x00*', 'tiff'),
            (b'%!PS', 'eps'), (b'PK\x03\x04', 'zip'), (b'<?xml', 'xml'), (b'<svg', 'svg'))


class ErroIndice(Exception):
    """A estrutura do arquivo nao bate com os comprimentos gravados."""


def detectar_tipo(inicio):
    for magico, nome in _MAGICOS:
        if inicio.startswith(magico):
            return nome
    return None


def _u(fmt, f):
    tam = struct.calcsize(fmt)
    dados = f.read(tam)
    if len(dados) != tam:
        raise ErroIndice('fim inesperado do arquivo')
    return struct.unpack(fmt, dados)


def ler_secoes(f, base=0, tamanho=None):
    """Mapa das secoes do documento que comeca em `base`. Devolve um dict com deslocamentos absolutos."""
    f.seek(base)
    c = cab.ler(f.read(cab.TAMANHO))
    v2 = c['versao'] != 1
    fmt_len = '>Q' if v2 else '>I'
    fim_doc = base + tamanho if tamanho is not None else None
    pos = base + cab.TAMANHO
    f.seek(pos)
    (n_cm,) = _u('>I', f)
    pos += struct.calcsize('>I') + n_cm
    f.seek(pos)
    (n_ir,) = _u('>I', f)
    ir_ini = pos + struct.calcsize('>I')
    pos = ir_ini + n_ir
    lmi_pos_len = pos
    f.seek(pos)
    (n_lmi,) = _u(fmt_len, f)
    lmi_ini = pos + struct.calcsize(fmt_len)
    lmi_fim = lmi_ini + n_lmi
    secoes = {'cabecalho': c, 'base': base, 'recursos': [ir_ini, n_ir], 'lmi_pos_comprimento': lmi_pos_len,
              'lmi_formato_comprimento': fmt_len, 'lmi': [lmi_ini, n_lmi], 'imagem_inicio': lmi_fim,
              'blocos_globais': [], 'fim_documento': fim_doc}
    if fim_doc is not None and lmi_fim > fim_doc:
        raise ErroIndice('a secao de camadas passa do fim do documento')
    if n_lmi == 0:
        return secoes
    f.seek(lmi_ini)
    (n_li,) = _u(fmt_len, f)
    pos = lmi_ini + struct.calcsize(fmt_len) + n_li
    if pos > lmi_fim:
        raise ErroIndice('a informacao de camadas passa do fim da secao')
    # mascara global (opcional): comprimento de 4 bytes, quando o que vem nao e assinatura de bloco
    if lmi_fim - pos >= struct.calcsize('>4s'):
        f.seek(pos)
        marca = f.read(struct.calcsize('>4s'))
        if marca not in ASSINATURAS_BLOCO:
            f.seek(pos)
            (n_glm,) = _u('>I', f)
            pos += struct.calcsize('>I') + n_glm
    # blocos marcados globais (alinhados em 4 bytes, como o psd-tools le: layer_and_mask.py, padding=4)
    alinhamento = 4  # numero-neutro: alinhamento dos blocos globais da secao de camadas (formato)
    cabeca_bloco = struct.calcsize('>4s4s')
    while lmi_fim - pos >= cabeca_bloco + struct.calcsize('>I'):
        f.seek(pos)
        assinatura, chave = _u('>4s4s', f)
        if assinatura not in ASSINATURAS_BLOCO:
            break
        fmt_bloco = '>' + adaptador.formato_do_comprimento(chave, c['versao'])
        (n_bloco,) = _u(fmt_bloco, f)
        dados_ini = pos + cabeca_bloco + struct.calcsize(fmt_bloco)
        resto = n_bloco % alinhamento
        fim_bloco = dados_ini + n_bloco + ((alinhamento - resto) if resto else 0)
        if dados_ini + n_bloco > lmi_fim:
            raise ErroIndice('bloco global passa do fim da secao de camadas')
        secoes['blocos_globais'].append({'chave': chave.decode('latin-1'), 'inicio': pos, 'dados': [dados_ini, n_bloco],
                                          'fim': min(fim_bloco, lmi_fim)})
        pos = fim_bloco
    return secoes


def _data_iso(ts):
    try:
        ano, mes, dia, hora, minuto, seg = ts
        return datetime.datetime(int(ano), int(mes), int(dia), int(hora), int(minuto), int(seg)).isoformat()
    except (TypeError, ValueError, OverflowError):
        return None


def _registro(f, inicio_item, fim_item, bloco):
    """Le o cabecalho de um registro de smart object posicionado em inicio_item (depois do comprimento)."""
    f.seek(inicio_item)
    (tipo,) = adaptador.ler_fmt('4s', f)
    (versao,) = adaptador.ler_fmt('I', f)
    uid = adaptador.ler_pascal(f)
    nome = adaptador.ler_unicode(f)
    filetype, criador, n_dados, tem_open = adaptador.ler_fmt('4s4sQB', f)
    if tem_open:
        adaptador.pular_descritor(f)
    tipo_txt = tipo.decode('latin-1')
    reg = {'unique_id': uid, 'bloco': bloco, 'tipo_registro': tipo_txt, 'versao_registro': versao,
           'embutido': tipo_txt == 'liFD', 'filetype': filetype.decode('latin-1').strip('\x00 ') or None,
           'nome': nome.strip('\x00'), 'deslocamento_dados': None, 'tamanho_dados': None, 'sha256': None,
           'assinatura_hex': None, 'tipo_detectado': None, 'cabecalho_psd': None, 'linkado': None}
    if tipo_txt == 'liFD':
        reg['deslocamento_dados'] = f.tell()
        reg['tamanho_dados'] = n_dados
        if f.tell() + n_dados > fim_item:
            raise ErroIndice('dados do smart object passam do fim do registro')
    elif tipo_txt == 'liFE':
        adaptador.pular_descritor(f)  # o descritor do arquivo externo (caminhos): lido para andar, descartado
        data = None
        if versao > 3:  # numero-neutro: a data entra na versao 4 do registro (formato)
            data = _data_iso(adaptador.ler_fmt('I4Bd', f))
        (tam_externo,) = adaptador.ler_fmt('Q', f)
        reg['linkado'] = {'nome': reg['nome'], 'tamanho': tam_externo, 'data': data}
    else:
        reg['linkado'] = {'nome': reg['nome'], 'tamanho': None, 'data': None}
    return reg


def indexar_smart(f, secoes):
    """Lista os registros de smart object dos blocos lnk* globais, sem ler os dados."""
    registros, erros = [], []
    with adaptador.contexto_de_parse():
        for bloco in secoes['blocos_globais']:
            if bloco['chave'].encode('latin-1') not in adaptador.CHAVES_SMART_BYTES:
                continue
            ini, n = bloco['dados']
            pos, fim = ini, ini + n
            tam_comprimento = struct.calcsize('>Q')
            while fim - pos >= tam_comprimento:
                f.seek(pos)
                (n_item,) = _u('>Q', f)
                ini_item = pos + tam_comprimento
                fim_item = ini_item + n_item
                if fim_item > fim:
                    erros.append({'etapa': 'indice_smart', 'tipo': 'ErroIndice',
                                  'mensagem': 'registro de smart object passa do fim do bloco'})
                    break
                try:
                    registros.append(_registro(f, ini_item, fim_item, bloco['chave']))
                except (ValueError, OSError, ErroIndice, struct.error) as e:
                    erros.append({'etapa': 'indice_smart', 'tipo': type(e).__name__,
                                  'mensagem': 'registro de smart object ilegivel'})
                resto = n_item % 4  # numero-neutro: registros alinhados em 4 bytes (psd-tools, linked_layer.py)
                pos = fim_item + ((4 - resto) if resto else 0)  # numero-neutro: idem
    return registros, erros


def completar_embutidos(f, registros):
    """sha256, assinatura, tipo detectado e cabecalho PSD de cada embutido, lendo so o trecho no arquivo."""
    for reg in registros:
        if not reg['embutido'] or reg['tamanho_dados'] is None:
            continue
        h = hashlib.sha256()
        f.seek(reg['deslocamento_dados'])
        falta = reg['tamanho_dados']
        inicio = b''
        while falta > 0:
            bloco = f.read(min(TAMANHO_LEITURA, falta))
            if not bloco:
                break
            if not inicio:
                inicio = bloco[:cab.TAMANHO]
            h.update(bloco)
            falta -= len(bloco)
        reg['sha256'] = h.hexdigest()
        reg['assinatura_hex'] = inicio[:8].hex()
        reg['tipo_detectado'] = detectar_tipo(inicio)
        if reg['tipo_detectado'] in ('psd', 'psb'):
            try:
                reg['cabecalho_psd'] = cab.ler(inicio)
            except cab.CabecalhoInvalido as e:
                reg['cabecalho_psd'] = {'invalido': e.motivo}
    return registros


# ------------------------------------------------------------------ vista do arquivo sem os blocos lnk*
class VistaSemSmart(io.RawIOBase):
    """Arquivo somente leitura que mostra o documento sem os blocos lnk* globais.

    Segmentos: trechos do arquivo original e, no lugar do comprimento da secao de camadas e mascaras, o
    comprimento novo. Nada do arquivo e copiado para a memoria alem do que o leitor pede."""

    def __init__(self, f, secoes):
        super().__init__()
        self._f = f
        base = secoes['base']
        fim = secoes['fim_documento']
        if fim is None:
            f.seek(0, io.SEEK_END)
            fim = f.tell()
        remover = [b for b in secoes['blocos_globais'] if b['chave'].encode('latin-1') in adaptador.CHAVES_SMART_BYTES]
        removidos = sum(b['fim'] - b['inicio'] for b in remover)
        pos_len = secoes['lmi_pos_comprimento']
        fmt_len = secoes['lmi_formato_comprimento']
        novo_len = struct.pack(fmt_len, secoes['lmi'][1] - removidos)
        segs = [('arq', base, pos_len), ('mem', novo_len)]
        cursor = pos_len + struct.calcsize(fmt_len)
        for b in sorted(remover, key=lambda x: x['inicio']):
            segs.append(('arq', cursor, b['inicio']))
            cursor = b['fim']
        segs.append(('arq', cursor, fim))
        self._segs = []
        virtual = 0
        for s in segs:
            n = len(s[1]) if s[0] == 'mem' else s[2] - s[1]
            if n > 0:
                self._segs.append((virtual, n, s))
                virtual += n
        self._tamanho = virtual
        self._pos = 0
        self.bytes_removidos = removidos
        self.blocos_removidos = len(remover)

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self._pos

    def seek(self, deslocamento, de_onde=io.SEEK_SET):
        if de_onde == io.SEEK_SET:
            novo = deslocamento
        elif de_onde == io.SEEK_CUR:
            novo = self._pos + deslocamento
        elif de_onde == io.SEEK_END:
            novo = self._tamanho + deslocamento
        else:
            raise ValueError('de_onde invalido')
        if novo < 0:
            raise ValueError('posicao negativa')
        self._pos = novo
        return novo

    def readinto(self, buffer):
        alvo = memoryview(buffer).cast('B')
        total = 0
        while total < len(alvo) and self._pos < self._tamanho:
            for ini_v, n, s in self._segs:
                if ini_v <= self._pos < ini_v + n:
                    break
            desloc = self._pos - ini_v
            quanto = min(n - desloc, len(alvo) - total)
            if s[0] == 'mem':
                pedaco = s[1][desloc:desloc + quanto]
            else:
                self._f.seek(s[1] + desloc)
                pedaco = self._f.read(quanto)
                if not pedaco:
                    break
            alvo[total:total + len(pedaco)] = pedaco
            total += len(pedaco)
            self._pos += len(pedaco)
        return total
