# -*- coding: utf-8 -*-
"""Cabecalho de 26 bytes do PSD/PSB: leitura com struct e conferencia antes de qualquer alocacao.

So fatos do formato (especificacao do Adobe Photoshop File Format) e o eixo maximo que o psd-tools aceita.
Nao importa o psd-tools: o processo principal usa este modulo para estimar o orcamento sem parsear o arquivo.

Layout: assinatura '8BPS' (4), versao (2: 1 = PSD, 2 = PSB), reservado (6, zeros), canais (2), altura (4),
largura (4), profundidade de bits (2), modo de cor (2).
"""
import struct

TAMANHO = 26  # numero-neutro: o cabecalho do PSD/PSB tem 26 bytes (especificacao do formato)
ASSINATURA = b'8BPS'
VERSOES = {1: 'PSD', 2: 'PSB'}  # numero-neutro: versoes do formato
BITS_VALIDOS = (1, 8, 16, 32)  # numero-neutro: profundidades que o formato admite
CANAIS_MAX = 56  # numero-neutro: o formato admite de 1 a 56 canais
MODOS = {0: 'Bitmap', 1: 'Grayscale', 2: 'Indexed', 3: 'RGB', 4: 'CMYK', 7: 'Multichannel', 8: 'Duotone',
         9: 'Lab'}  # numero-neutro: codigos de modo de cor do formato
_FORMATO = '>4sH6sHIIHH'


class CabecalhoInvalido(Exception):
    def __init__(self, motivo, medidas=None, tipo='cabecalho'):
        super().__init__(motivo)
        self.motivo = motivo
        self.medidas = medidas or {}
        self.tipo = tipo


def ler(dados):
    """Le os 26 bytes. Levanta CabecalhoInvalido se nao for PSD/PSB ou se os campos fogem do formato."""
    if len(dados) < TAMANHO:
        raise CabecalhoInvalido('O arquivo tem menos bytes que o cabeçalho de um PSD.', {'bytes': len(dados)},
                                tipo='formato')
    assinatura, versao, reservado, canais, altura, largura, bits, modo = struct.unpack(_FORMATO, dados[:TAMANHO])
    medidas = {'versao': versao, 'canais': canais, 'altura': altura, 'largura': largura, 'bits': bits, 'modo': modo}
    if assinatura != ASSINATURA:
        raise CabecalhoInvalido('O arquivo não começa com a assinatura de PSD (8BPS).', {}, tipo='formato')
    if versao not in VERSOES or reservado != bytes(len(reservado)):
        raise CabecalhoInvalido('A versão do cabeçalho não é de PSD nem de PSB.', medidas)
    if not 1 <= canais <= CANAIS_MAX:
        raise CabecalhoInvalido('O número de canais está fora do formato.', medidas)
    if bits not in BITS_VALIDOS:
        raise CabecalhoInvalido('A profundidade de bits está fora do formato.', medidas)
    if modo not in MODOS:
        raise CabecalhoInvalido('O modo de cor está fora do formato.', medidas)
    if largura < 1 or altura < 1:
        raise CabecalhoInvalido('O cabeçalho declara uma dimensão vazia.', medidas)
    return {'formato': VERSOES[versao], 'versao': versao, 'canais': canais, 'altura': altura, 'largura': largura,
            'bits': bits, 'modo': MODOS[modo], 'modo_codigo': modo}


def bytes_da_imagem(cab):
    """Bytes da imagem crua que o cabecalho declara (o composto gravado, sem compressao)."""
    por_linha = -(-cab['largura'] * cab['bits'] // 8)
    return por_linha * cab['altura'] * cab['canais']


def conferir(cab, orcamento_bytes, eixo_max):
    """Confere eixo e estimativa contra o orcamento. Levanta CabecalhoInvalido; devolve as medidas."""
    medidas = {k: cab[k] for k in ('versao', 'canais', 'altura', 'largura', 'bits')}
    medidas['eixo_max_px'] = eixo_max
    if cab['largura'] > eixo_max or cab['altura'] > eixo_max:
        raise CabecalhoInvalido('O cabeçalho declara um eixo acima do máximo aceito pela biblioteca de leitura.',
                                medidas)
    estimativa = bytes_da_imagem(cab)
    medidas['estimativa_bytes'] = estimativa
    medidas['orcamento_bytes'] = int(orcamento_bytes)
    if estimativa > orcamento_bytes:
        raise CabecalhoInvalido('A imagem que o cabeçalho declara não cabe no orçamento de memória do processo.',
                                medidas, tipo='orcamento')
    return medidas


def ler_de_arquivo(caminho, inicio=0):
    """Le so os 26 bytes a partir de `inicio`. Nao e parse: e o mesmo tipo de leitura da assinatura."""
    with open(caminho, 'rb') as f:
        f.seek(inicio)
        return ler(f.read(TAMANHO))
