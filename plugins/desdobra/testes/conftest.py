# -*- coding: utf-8 -*-
"""Fixtures comuns. Todo material de teste e sintetico e gerado na hora."""
import struct
import sys
from pathlib import Path

import pytest

RAIZ_PLUGIN = Path(__file__).resolve().parent.parent
PASTA_MOTOR = RAIZ_PLUGIN / 'motor'
PASTA_PACOTE = PASTA_MOTOR / 'desdobra'


def psd_minimo(largura=1, altura=1, rgb=(200, 0, 0)):
    """Bytes de um PSD RGB de 8 bits sem camadas, escrito a mao (cabecalho de 26 bytes, secoes vazias,
    imagem crua). Serve para os testes do job, que nunca parseiam o arquivo."""
    cabecalho = b'8BPS' + struct.pack('>H', 1) + b'\x00' * 6 + struct.pack('>HIIHH', 3, altura, largura, 8, 3)
    secoes = struct.pack('>I', 0) * 3
    pixels = b''.join(bytes([c]) * (largura * altura) for c in rgb)
    return cabecalho + secoes + struct.pack('>H', 0) + pixels


@pytest.fixture
def kv_psd(tmp_path):
    caminho = tmp_path / 'origem' / 'kv-teste.psd'
    caminho.parent.mkdir(parents=True)
    caminho.write_bytes(psd_minimo())
    return caminho


@pytest.fixture
def python():
    return sys.executable
