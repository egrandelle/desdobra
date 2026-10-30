# -*- coding: utf-8 -*-
"""Recusa de fonte dentro de pacote: o pacote e reconhecido pela assinatura, e o que nao da para inspecionar sem
extrair conta como suspeito. Todo material e sintetico: a "fonte" e so a assinatura sfnt seguida de zeros."""
import gzip
import io
import tarfile
import zipfile

import pytest

from conftest import psd_minimo
from desdobra.arquivos import eh_arquivo_de_fonte

FONTE_FALSA = b'\x00\x01\x00\x00' + b'\x00' * 60


def _zip(membros):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        for nome, dados in membros.items():
            z.writestr(nome, dados)
    return buf.getvalue()


def _tar(membros, modo='w'):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode=modo, format=tarfile.USTAR_FORMAT) as t:
        for nome, dados in membros.items():
            info = tarfile.TarInfo(nome)
            info.size = len(dados)
            t.addfile(info, io.BytesIO(dados))
    return buf.getvalue()


@pytest.mark.parametrize('nome, dados', [
    ('pacote.zip', _zip({'recursos.dat': _zip({'FonteInventada-Regular.ttf': FONTE_FALSA})})),
    ('pacote.dat', _zip({'leia.bin': FONTE_FALSA})),
    ('pacote.zip', _zip({'recursos.dat': gzip.compress(b'qualquer coisa')})),
    ('pacote.zip', _zip({'recursos.dat': _tar({'leia.txt': b'texto'})})),
    ('fontes.tar.gz', _tar({'FonteInventada-Regular.ttf': FONTE_FALSA}, 'w:gz')),
    ('recursos.dat', _tar({'FonteInventada-Regular.ttf': FONTE_FALSA}, 'w:gz')),
    ('recursos.dat', _tar({'leia.bin': FONTE_FALSA})),
    ('recursos.tar', _tar({'FonteInventada-Regular.ttf': b'x'})),
    ('recursos.dat', _tar({'mais.dat': _zip({'leia.txt': b'texto'})})),
    ('compactado.dat', gzip.compress(b'texto sem fonte, mas sem como conferir sem extrair')),
])
def test_pacote_com_fonte_ou_que_nao_da_para_inspecionar_e_recusado(tmp_path, nome, dados):
    caminho = tmp_path / nome
    caminho.write_bytes(dados)
    assert eh_arquivo_de_fonte(caminho) is True


@pytest.mark.parametrize('nome, dados', [
    ('pacote.zip', _zip({'leia.txt': b'texto qualquer'})),
    ('recursos.dat', _tar({'leia.txt': b'texto qualquer', 'imagens/a.bin': b'\x00' * 300})),
    ('kv.psd', psd_minimo()),
    ('nota.txt', b'texto qualquer'),
])
def test_arquivo_ou_pacote_sem_fonte_passa(tmp_path, nome, dados):
    caminho = tmp_path / nome
    caminho.write_bytes(dados)
    assert eh_arquivo_de_fonte(caminho) is False
