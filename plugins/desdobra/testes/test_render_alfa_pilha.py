# -*- coding: utf-8 -*-
"""Alfa das pilhas (M6): o psd-tools compoe o alfa em float32 (b + s - b*s da 0.99999994 sobre fundo opaco) e o
composite_pil trunca com astype(uint8), entao uma pilha com fundo opaco e veu semitransparente saia com alfa 254.
O filho das pilhas arredonda o alfa e mantem os bytes de cor exatamente como o psd-tools os produz.
PSD sintetico gerado na hora: cores e nomes inventados."""
import numpy as np
import pytest
from PIL import Image
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer

from desdobra.render import filho_pilhas

W, H = 64, 48


def _psd(tmp_path, modo, nome):
    """Fundo opaco do canvas inteiro e, por cima, um veu com alfa de 0 a 252 em degraus de 4 por coluna."""
    psd = PSDImage.new(modo, (W, H), color=0)
    PixelLayer.frompil(Image.new('RGBA', (W, H), (40, 120, 200, 255)), psd, name='fundo')
    rampa = np.tile(np.arange(W, dtype=np.uint8) * 4, (H, 1))
    veu = np.dstack([np.full((H, W), 250, np.uint8), np.full((H, W), 30, np.uint8),
                     np.full((H, W), 90, np.uint8), rampa])
    PixelLayer.frompil(Image.fromarray(veu, 'RGBA'), psd, name='veu')
    destino = tmp_path / nome
    psd.save(str(destino))
    return PSDImage.open(str(destino))


def _antigo(psd, camadas, indices):
    """O caminho de antes: psd.composite (composite_pil) e convert('RGBA'), com o mesmo filtro do filho."""
    alvo = set()
    for i in indices:
        L = camadas[i]
        alvo.add(id(L))
        while L.parent is not None and L.parent is not psd:
            L = L.parent
            alvo.add(id(L))
    im = psd.composite(viewport=(0, 0, psd.width, psd.height), layer_filter=lambda L: id(L) in alvo and L.is_visible(),
                       ignore_preview=True, apply_icc=False)
    return np.asarray(im.convert('RGBA'))


@pytest.mark.parametrize('modo', ['RGB', 'L'])
def test_fundo_opaco_com_veu_sai_com_alfa_cheio(tmp_path, modo):
    psd = _psd(tmp_path, modo, 'kv-%s.psd' % modo)
    camadas = list(psd.descendants())
    indices = list(range(len(camadas)))
    antigo = _antigo(psd, camadas, indices)
    # premissa: o caminho antigo trunca para 254 sobre o fundo opaco (se o psd-tools mudar, este teste avisa)
    assert int(antigo[..., 3].min()) == 254
    novo = filho_pilhas.compor_pilha(psd, camadas, indices)
    assert novo.dtype == np.uint8 and novo.shape == (H, W, 4)
    assert (novo[..., 3] == filho_pilhas.ALFA_CHEIO).all()
    # a cor e byte a byte a mesma do psd-tools
    assert np.array_equal(novo[..., :3], antigo[..., :3])


@pytest.mark.parametrize('modo', ['RGB', 'L'])
def test_veu_sozinho_tem_alfa_arredondado_e_cor_identica(tmp_path, modo):
    psd = _psd(tmp_path, modo, 'veu-%s.psd' % modo)
    camadas = list(psd.descendants())
    indices = [i for i, L in enumerate(camadas) if L.name == 'veu']
    antigo = _antigo(psd, camadas, indices)
    novo = filho_pilhas.compor_pilha(psd, camadas, indices)
    assert np.array_equal(novo[..., :3], antigo[..., :3])
    # o alfa e o byte da camada (sem mistura): arredondar devolve a rampa exata; truncar pode perder 1
    rampa = np.tile(np.arange(W, dtype=np.uint8) * 4, (H, 1))
    assert np.array_equal(novo[..., 3], rampa)
    assert int(np.abs(novo[..., 3].astype(int) - antigo[..., 3].astype(int)).max()) <= 1


def _geradores():
    import sinteticos
    import test_render_apoio as ra
    return [('simples', lambda p: sinteticos.simples(p)), ('coberta', lambda p: sinteticos.coberta(p)),
            ('quadros', lambda p: sinteticos.quadros(p)), ('render', lambda p: ra.psd_render(p / 'r.psd')),
            ('ajuste', lambda p: ra.psd_ajuste_sobre_texto(p / 'a.psd')),
            ('multiplicar', lambda p: ra.psd_ajuste_sobre_texto(p / 'm.psd', 'MULTIPLY')),
            ('clip', lambda p: ra.psd_clip_dividido(p / 'c.psd'))]


@pytest.mark.parametrize('nome', [n for n, _g in _geradores()])
def test_cor_identica_ao_caminho_antigo_nos_psd_sinteticos(tmp_path, nome):
    gerar = dict(_geradores())[nome]
    psd = PSDImage.open(str(gerar(tmp_path)))
    camadas = list(psd.descendants())
    pilhas = [[i] for i, L in enumerate(camadas) if L.kind != 'group'] + [list(range(len(camadas)))]
    for indices in pilhas:
        antigo = _antigo(psd, camadas, indices)
        novo = filho_pilhas.compor_pilha(psd, camadas, indices)
        assert np.array_equal(novo[..., :3], antigo[..., :3]), (nome, indices)
        # o alfa so pode subir 1 (arredondar em vez de truncar), nunca descer
        dif = novo[..., 3].astype(int) - antigo[..., 3].astype(int)
        assert dif.min() >= 0 and dif.max() <= 1, (nome, indices)


def test_faixas_dao_o_mesmo_resultado_que_o_canvas_inteiro(tmp_path, monkeypatch):
    psd = _psd(tmp_path, 'RGB', 'faixas.psd')
    camadas = list(psd.descendants())
    indices = list(range(len(camadas)))
    inteiro = filho_pilhas.compor_pilha(psd, camadas, indices)
    monkeypatch.setattr(filho_pilhas, 'PIXELS_POR_FAIXA', W * 5)
    monkeypatch.setattr(filho_pilhas, 'LINHAS_MIN_FAIXA', 5)
    assert np.array_equal(filho_pilhas.compor_pilha(psd, camadas, indices), inteiro)


@pytest.mark.parametrize('modo', ['RGB', 'L'])
def test_faixas_com_linhas_diferentes_dao_o_mesmo_resultado(tmp_path, monkeypatch, modo):
    """Cada linha tem cor e alfa proprios: uma faixa composta com o deslocamento errado (y0) sai diferente."""
    psd = PSDImage.new(modo, (W, H), color=0)
    linhas = np.repeat((np.arange(H, dtype=np.uint8) * 5)[:, None], W, axis=1)
    fundo = np.dstack([linhas, 255 - linhas, np.full((H, W), 60, np.uint8), np.full((H, W), 255, np.uint8)])
    PixelLayer.frompil(Image.fromarray(fundo, 'RGBA'), psd, name='fundo')
    veu = np.dstack([np.full((H, W), 250, np.uint8), linhas, np.full((H, W), 90, np.uint8), linhas])
    PixelLayer.frompil(Image.fromarray(veu, 'RGBA'), psd, name='veu')
    psd.save(str(tmp_path / 'linhas.psd'))
    psd = PSDImage.open(str(tmp_path / 'linhas.psd'))
    camadas = list(psd.descendants())
    for indices in ([i for i, L in enumerate(camadas) if L.name == 'veu'], list(range(len(camadas)))):
        inteiro = filho_pilhas.compor_pilha(psd, camadas, indices)
        assert np.array_equal(inteiro[..., :3], _antigo(psd, camadas, indices)[..., :3])
        with monkeypatch.context() as m:
            m.setattr(filho_pilhas, 'PIXELS_POR_FAIXA', W * 5)
            m.setattr(filho_pilhas, 'LINHAS_MIN_FAIXA', 5)
            assert np.array_equal(filho_pilhas.compor_pilha(psd, camadas, indices), inteiro), indices
