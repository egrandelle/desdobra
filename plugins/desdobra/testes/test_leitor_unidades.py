# -*- coding: utf-8 -*-
"""Partes do leitor sem processo filho: cabecalho, orcamento, indice por deslocamento, vista sem smart objects e
gancho de auditoria (chamado direto, sem instalar: um gancho instalado nao sai mais do processo de teste)."""
import hashlib
import io
import os
import struct

import pytest
from psd_tools import PSDImage

import sinteticos
from desdobra import leitor
from desdobra.leitor import auditoria, cabecalho, indice


# ------------------------------------------------------------------ cabecalho
def test_cabecalho_bomba_recusado_pela_estimativa(tmp_path):
    caminho = sinteticos.bomba(tmp_path)
    c = cabecalho.ler_de_arquivo(caminho)
    assert (c['largura'], c['altura'], c['canais'], c['bits']) == (29999, 29999, 3, 8)
    orc = leitor.orcamento_bytes(caminho.stat().st_size, c['largura'] * c['altura'])
    with pytest.raises(cabecalho.CabecalhoInvalido) as e:
        cabecalho.conferir(c, orc, 30000)
    assert e.value.tipo == 'orcamento' and e.value.medidas['estimativa_bytes'] > orc


def test_cabecalho_fora_do_formato():
    bom = b'8BPS' + struct.pack('>H', 1) + b'\x00' * 6 + struct.pack('>HIIHH', 3, 10, 10, 8, 3)
    assert cabecalho.ler(bom)['formato'] == 'PSD'
    for ruim, tipo in ((b'XXXX' + bom[4:], 'formato'), (bom[:4] + struct.pack('>H', 3) + bom[6:], 'cabecalho'),
                       (bom[:12] + struct.pack('>H', 0) + bom[14:], 'cabecalho'), (bom[:22] + struct.pack('>H', 7) + bom[24:], 'cabecalho'),
                       (bom[:10], 'formato')):
        with pytest.raises(cabecalho.CabecalhoInvalido) as e:
            cabecalho.ler(ruim)
        assert e.value.tipo == tipo
    eixo = cabecalho.ler(bom[:14] + struct.pack('>II', 10, 30001) + bom[22:])
    with pytest.raises(cabecalho.CabecalhoInvalido):
        cabecalho.conferir(eixo, 10 ** 12, 30000)


def test_orcamento_nao_acredita_em_canvas_maior_que_o_arquivo():
    pequeno = leitor.orcamento_bytes(60, 29999 * 29999)
    assert pequeno == leitor.orcamento_bytes(60, 60 * leitor.PIXELS_POR_BYTE_MAX)
    real = leitor.orcamento_bytes(3_000_000, 2160 * 3840)
    assert real > leitor.orcamento_bytes(3_000_000, 0)


# ------------------------------------------------------------------ indice e vista sem smart objects
def test_indice_acha_o_embutido_por_deslocamento(tmp_path):
    caminho, dados = sinteticos.embutido(tmp_path)
    with open(caminho, 'rb') as f:
        secoes = indice.ler_secoes(f)
        regs, erros = indice.indexar_smart(f, secoes)
        indice.completar_embutidos(f, regs)
        assert erros == [] and len(regs) == 1
        r = regs[0]
        assert r['embutido'] and r['tipo_registro'] == 'liFD' and r['tipo_detectado'] == 'psb'
        assert r['tamanho_dados'] == len(dados) and r['sha256'] == hashlib.sha256(dados).hexdigest()
        f.seek(r['deslocamento_dados'])
        assert f.read(r['tamanho_dados']) == dados
        assert r['cabecalho_psd']['largura'] == 64 and r['cabecalho_psd']['formato'] == 'PSB'
        vista = indice.VistaSemSmart(f, secoes)
        assert vista.blocos_removidos == 1 and vista.bytes_removidos > len(dados)
        psd = PSDImage.open(io.BufferedReader(vista))
        camadas = list(psd.descendants())
        assert [c.kind for c in camadas] == ['smartobject'] and camadas[0].smart_object.unique_id == r['unique_id']
        assert camadas[0].smart_object._data is None  # os dados do smart object nao foram carregados
        assert psd.size == (80, 60)


def test_indice_do_linkado_guarda_so_nome_tamanho_e_data(tmp_path):
    isca = tmp_path / 'isca' / 'isca.txt'
    isca.parent.mkdir()
    isca.write_text('isca')
    caminho = sinteticos.linkado(tmp_path, isca)
    with open(caminho, 'rb') as f:
        secoes = indice.ler_secoes(f)
        regs, erros = indice.indexar_smart(f, secoes)
    assert erros == [] and len(regs) == 1
    r = regs[0]
    assert not r['embutido'] and r['tipo_registro'] == 'liFE' and r['deslocamento_dados'] is None
    assert r['linkado'] == {'nome': 'isca.txt', 'tamanho': 1234, 'data': '2026-10-29T12:30:00'}
    assert str(isca) not in repr(r) and str(tmp_path) not in repr(r)


def test_vista_sem_smart_e_identica_quando_nao_ha_smart(tmp_path):
    caminho = sinteticos.simples(tmp_path)
    original = caminho.read_bytes()
    with open(caminho, 'rb') as f:
        vista = indice.VistaSemSmart(f, indice.ler_secoes(f))
        assert io.BufferedReader(vista).read() == original


# ------------------------------------------------------------------ gancho de auditoria (sem instalar)
def test_gancho_permite_entrada_ambiente_e_saida_e_barra_o_resto(tmp_path):
    entrada = tmp_path / 'kv.psd'
    saida = tmp_path / 'saida'
    ambiente = tmp_path / 'ambiente'
    g = auditoria.Gancho(entrada, saida, [ambiente])
    g('open', (str(entrada), 'r', os.O_RDONLY))
    g('open', (str(ambiente / 'modulo.py'), 'r', os.O_RDONLY))
    g('open', (str(saida / 'estrutura.json'), 'wb', os.O_WRONLY | os.O_CREAT))
    g('os.rename', (str(saida / '.tmp-x'), str(saida / 'x'), None, None))
    assert g.bloqueios == []
    for evento, args in (('open', (str(tmp_path / 'isca.txt'), 'r', os.O_RDONLY)),
                         ('open', (str(ambiente / 'fonte.ttf'), 'rb', os.O_RDONLY)),
                         ('open', (str(entrada), 'wb', os.O_WRONLY)),
                         ('os.remove', (str(tmp_path / 'outro'), None)),
                         ('subprocess.Popen', ('cmd', ['cmd'], None, None)),
                         ('os.system', ('dir',)),
                         ('socket.connect', (None, ('127.0.0.1', 80))),
                         ('socket.getaddrinfo', ('exemplo', 80, 0, 0, 0))):
        with pytest.raises(PermissionError):
            g(evento, args)
    assert len(g.bloqueios) == 8
    assert all(str(tmp_path) not in repr(b) for b in g.bloqueios)


@pytest.mark.skipif(os.name != 'nt', reason='juncao e _winapi so no Windows')
def test_gancho_barra_link_juncao_copia_para_fora_e_hardlink(tmp_path):
    import _winapi
    saida, fora = tmp_path / 'saida', tmp_path / 'fora'
    saida.mkdir()
    fora.mkdir()
    (fora / 'alvo.txt').write_text('x')
    entrada = tmp_path / 'entrada.bin'
    entrada.write_bytes(b'x')
    g = auditoria.Gancho(entrada, saida, [])
    barrados = [
        ('os.link', (str(fora / 'alvo.txt'), str(saida / 'hl.txt'), -1, -1)),
        ('os.symlink', (str(fora / 'alvo.txt'), str(saida / 'ln.txt'), -1)),
        ('_winapi.CreateJunction', (str(fora), str(saida / 'j'))),
        ('_winapi.CopyFile2', (str(saida / 'a.txt'), str(fora / 'b.txt'), 8)),
        ('_winapi.CreateFile', (str(fora / 'c.txt'), 0x40000000, 0, 2, 0x80)),
        ('_winapi.CreateNamedPipe', ('pipe', 3, 0)),
        ('os.utime', (str(fora / 'alvo.txt'), None, None, -1)),
        ('os.listdir', (str(fora),)),
        ('os.scandir', (str(tmp_path),)),
        ('ctypes.dlopen', ('kernel32',)),
        ('winreg.OpenKey', (1, 'Software', 1)),
        ('os.kill', (1, 0)),
    ]
    for evento, args in barrados:
        with pytest.raises(PermissionError):
            g(evento, args)
    # juncao criada por fora do gancho dentro da saida: gravar por ela e barrado (o caminho e resolvido)
    _winapi.CreateJunction(str(fora), str(saida / 'junc'))
    with pytest.raises(PermissionError):
        g('open', (str(saida / 'junc' / 'novo.txt'), 'w', 0))
    # hardlink criado por fora dentro da saida: ler ou gravar por ele e barrado
    os.link(fora / 'alvo.txt', saida / 'hl.txt')
    with pytest.raises(PermissionError):
        g('open', (str(saida / 'hl.txt'), 'a', 0))
    assert len(g.bloqueios) == len(barrados) + 2
    # o que vale continua valendo
    g('open', (str(saida / 'novo.txt'), 'w', 0))
    g('_winapi.CopyFile2', (str(saida / 'a.txt'), str(saida / 'b.txt'), 8))
    g('os.listdir', (str(saida),))
    g('_winapi.CreateFile', (str(entrada), 0x80000000, 1, 3, 0x80))
    g('os.utime', (str(saida / 'novo.txt'), None, None, -1))
    assert len(g.bloqueios) == len(barrados) + 2
    os.rmdir(saida / 'junc')
