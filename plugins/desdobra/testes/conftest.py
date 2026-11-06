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


@pytest.fixture
def pessoa(monkeypatch):
    """O DA num console interativo: so a conferencia do console fica simulada (o caminho do Disparo e o de verdade).
    Uso: execucao.renderizar(job, disparo=pessoa.exigir('render'))."""
    from desdobra import humano
    monkeypatch.setattr(humano, 'console_interativo', lambda: (True, None))
    return humano


def escolher_modo_do_da(job, modo, teto=None):
    """A escolha do modo de dados como o DA a deixa na tela (briefing/modo-dados.json com origem da; decisoes-v1.md,
    170), gravada direto, para os testes que precisam do job num modo aberto. O caminho da tela tem teste proprio
    (test_tela_lido.py)."""
    import json as _json

    from desdobra import contratos
    from desdobra.job import modo_dados
    estado = _json.loads((Path(job) / 'estado.json').read_text(encoding='utf-8'))
    contratos.gravar(Path(job) / modo_dados.ARQUIVO,
                     {'esquema': modo_dados.ESQUEMA, 'job_id': estado['job_id'], 'valor': modo, 'teto': teto,
                      'origem': 'da', 'escolhido_por': {'usuario': None, 'maquina': None, 'meio': 'tela',
                                                        'quando': '2026-11-05T10:00:00-03:00'}},
                     modo_dados.ESQUEMA)
