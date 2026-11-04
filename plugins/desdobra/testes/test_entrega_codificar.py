# -*- coding: utf-8 -*-
"""Encoder do arquivo final (M6, fatias 3 e 7 da proposta; decisoes-v1.md, 136, 137, 139 e 140), em imagens sinteticas
geradas na hora.

Criterios de pronto cobertos aqui (arquitetura-v1.md, 9.7):
  - JPEG baseline 4:4:4 (get_sampling 0, nao progressivo), sem EXIF e sem perfil, mesmo com o master trazendo os dois;
  - peso <= alvo_bytes (leitura decimal, nº 136) em imagem chapada e em ruido, com a busca conferindo os bytes finais
    e sem supor que o peso cai sempre com a qualidade (tabelas de peso nao monotonicas);
  - teto condicional sem a escolha do DA: vale o mais estrito, com a regra condicao_nao_decidida (nº 137);
  - regressao do buffer do optimize (400x300 de ruido quebrava com o MAXBLOCK padrao);
  - mesmos bytes em duas execucoes, no mesmo processo e em dois processos;
  - PNG sem perda: os pixels voltam iguais; PNG quando cabe e e aceito, senao JPEG, com a escolha registrada;
  - transparencia sem cor de achatamento recusa; com a cor, o achatamento sai nos pixels;
  - giro de entrega sem reamostrar: horario e anti-horario dao os pixels exatos esperados numa imagem assimetrica, a
    dimensao troca, sentido nulo nos 90 graus e recusado, 180 graus passa sem sentido;
  - entrada mexida (1 pixel, sentido, cor, teto, tipos) muda os bytes ou os parametros em 100% dos casos.
"""
import hashlib
import io
import random
import subprocess
import sys

import numpy as np
import pytest
from PIL import Image, ImageCms, JpegImagePlugin

from conftest import PASTA_MOTOR
from desdobra import limites
from desdobra.entrega import codificar

JPEG, PNG = 'image/jpeg', 'image/png'


def _ruido(largura, altura, semente=1):
    rng = np.random.default_rng(semente)
    return Image.fromarray(rng.integers(0, 256, (altura, largura, 3), dtype=np.uint8), 'RGB')


def _chapada(largura, altura):
    a = np.zeros((altura, largura, 3), np.uint8)
    a[:, :] = (12, 90, 200)
    a[altura // 3:, :] = (240, 200, 20)
    a[:, largura // 2:largura // 2 + 40] = (255, 255, 255)
    return Image.fromarray(a, 'RGB')


def _assimetrica():
    """3 x 2 com todo pixel diferente: qualquer giro ou espelho errado aparece."""
    a = np.arange(3 * 2 * 3, dtype=np.uint8).reshape(2, 3, 3) * 10
    return Image.fromarray(a, 'RGB'), a


def _abrir(final):
    img = Image.open(io.BytesIO(final.dados))
    img.load()
    return img


def _teto(alvo):
    return {'alvo_bytes': alvo, 'campo': 'peso_max', 'regra': 'leitura_decimal', 'condicao': None}


def _peso(alvo, condicao=None, situacao='confirmado'):
    return {'valor': {'alvo_bytes': alvo, 'reprova_acima_bytes': int(alvo * 1.024)}, 'condicao': condicao,
            'situacao': situacao}


# ------------------------------------------------------------------ JPEG: baseline 4:4:4, sem EXIF, sem perfil
def test_jpeg_baseline_444_sem_exif_e_sem_perfil():
    img = _ruido(400, 300)
    img.info['icc_profile'] = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    img.info['exif'] = Image.Exif().tobytes()
    final = codificar.codificar(img, tipos_aceitos=[JPEG], teto=_teto(150000))
    assert final.extensao == 'jpg' and final.dados[:3] == b'\xff\xd8\xff'
    out = _abrir(final)
    assert JpegImagePlugin.get_sampling(out) == 0
    assert not out.info.get('progressive') and not out.info.get('progression')
    assert 'icc_profile' not in out.info and 'exif' not in out.info and not out.getexif()
    assert b'Exif\x00\x00' not in final.dados and b'ICC_PROFILE' not in final.dados
    p = final.parametros
    assert (p['tipo'], p['subamostragem'], p['progressivo'], p['optimize'], p['perfil_embutido'], p['exif']) == \
        ('jpg', '4:4:4', False, True, False, False)
    assert p['buffer_bytes'] == limites.valor('entrega.jpeg_buffer_bytes')


def test_png_sem_perfil_nem_exif_herdados_do_master():
    img = _chapada(300, 200)
    img.info['icc_profile'] = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    final = codificar.codificar(img, tipos_aceitos=[PNG, JPEG], teto=_teto(250000))
    assert final.extensao == 'png'
    for chunk in (b'iCCP', b'eXIf', b'tIME', b'tEXt', b'zTXt', b'iTXt'):
        assert chunk not in final.dados, chunk


# ------------------------------------------------------------------ peso abaixo do teto estrito
@pytest.mark.parametrize('nome, img, alvo', [
    ('chapada', _chapada(1080, 1920), 60000), ('chapada', _chapada(1080, 1920), 250000),
    ('ruido', _ruido(400, 300), 60000), ('ruido', _ruido(400, 300), 150000), ('ruido', _ruido(300, 600), 250000)])
def test_jpeg_fica_abaixo_do_alvo(nome, img, alvo):
    final = codificar.codificar(img, tipos_aceitos=[JPEG], teto=_teto(alvo))
    assert len(final.dados) <= alvo and final.medidas['cabe_no_teto'] is True, nome
    q, tent = final.parametros['qualidade'], final.medidas['tentativas']
    assert tent[str(q)] == len(final.dados)
    # a qualidade logo acima foi medida e nao coube (ou a escolhida e o teto da busca)
    assert q == limites.valor('entrega.jpeg_qualidade_max') or tent[str(q + 1)] > alvo


def test_nada_cabe_sai_na_qualidade_minima_marcado_fora_do_teto():
    final = codificar.codificar(_ruido(400, 300), tipos_aceitos=[JPEG], teto=_teto(1000))
    assert final.parametros['qualidade'] == limites.valor('entrega.jpeg_qualidade_min')
    assert final.medidas['cabe_no_teto'] is False and len(final.dados) > 1000
    assert final.medidas['sugestao_qualidade'] is None


def test_busca_confere_os_bytes_finais_sem_supor_peso_monotonico(monkeypatch):
    """Tabelas de peso aleatorias e nao monotonicas: a qualidade devolvida sempre cabe pelo peso medido."""
    q_min, q_max = limites.valor('entrega.jpeg_qualidade_min'), limites.valor('entrega.jpeg_qualidade_max')
    rnd = random.Random(7)
    casos = 0
    for _ in range(200):
        tabela = {q: rnd.randint(1000, 9000) for q in range(q_min, q_max + 1)}
        alvo = rnd.randint(1000, 9000)
        monkeypatch.setattr(codificar, '_jpeg', lambda img, q, t=tabela: b'x' * t[q])
        q, dados, tent, cabe = codificar.buscar_qualidade(None, alvo)
        assert tent[q] == len(dados)
        if cabe:
            assert len(dados) <= alvo
            assert q == q_max or tent[q + 1] > alvo
        else:
            assert q == q_min and tabela[q_min] > alvo
        casos += 1
    assert casos == 200


# ------------------------------------------------------------------ teto estrito (nº 136 e 137)
def test_teto_e_a_leitura_decimal():
    spec = {'campos': {'peso_max': _peso(250000)}}
    t = codificar.teto_estrito(spec)
    assert (t['alvo_bytes'], t['regra'], t['leitura']) == (250000, 'leitura_decimal', 'decimal')
    assert limites.obter('entrega.peso_reprova_acima_da_leitura_decimal').efeito_efetivo == 'reprova'
    assert codificar.teto_estrito({'campos': {}}) is None
    assert codificar.teto_estrito({'campos': {'peso_max': _peso(250000, situacao='rascunho')}}) is None


def test_teto_condicional_sem_escolha_do_da_vale_o_mais_estrito():
    spec = {'campos': {'peso_max_hospedado': _peso(250000, 'hospedado'), 'peso_max_tag': _peso(500000, 'por_tag')}}
    t = codificar.teto_estrito(spec)
    assert (t['alvo_bytes'], t['regra'], t['campo']) == (250000, 'condicao_nao_decidida', 'peso_max_hospedado')
    t = codificar.teto_estrito(spec, 'por_tag')
    assert (t['alvo_bytes'], t['regra'], t['condicao']) == (500000, 'leitura_decimal', 'por_tag')
    with pytest.raises(codificar.ErroCodificar) as e:
        codificar.teto_estrito(spec, 'tag_carga_inicial')
    assert e.value.codigo == 'teto_da_condicao_sem_valor'
    # teto sem condicao vale sempre, junto com o da condicao escolhida
    spec['campos']['peso_max'] = _peso(400000)
    assert codificar.teto_estrito(spec, 'por_tag')['alvo_bytes'] == 400000


# ------------------------------------------------------------------ buffer do optimize
@pytest.mark.parametrize('qualidade', [50, 90, 94, 95])
def test_regressao_do_buffer_do_optimize(qualidade):
    from PIL import ImageFile
    antes = ImageFile.MAXBLOCK
    dados = codificar._jpeg(_ruido(400, 300), qualidade)
    assert ImageFile.MAXBLOCK == antes
    assert len(dados) > antes  # o arquivo nao caberia no buffer padrao do Pillow
    assert Image.open(io.BytesIO(dados)).size == (400, 300)


# ------------------------------------------------------------------ determinismo
_SCRIPT = r'''
import hashlib, sys
import numpy as np
from PIL import Image
from desdobra.entrega import codificar
rng = np.random.default_rng(3)
img = Image.fromarray(rng.integers(0, 256, (240, 320, 3), dtype=np.uint8), 'RGB')
t = {'alvo_bytes': 90000, 'campo': 'peso_max', 'regra': 'leitura_decimal', 'condicao': None}
for tipos in (['image/jpeg'], ['image/png', 'image/jpeg']):
    f = codificar.codificar(img, tipos_aceitos=tipos, teto=dict(t, alvo_bytes=90000 if len(tipos) == 1 else 10 ** 6))
    print(f.extensao, hashlib.sha256(f.dados).hexdigest())
'''


def _no_processo():
    rng = np.random.default_rng(3)
    img = Image.fromarray(rng.integers(0, 256, (240, 320, 3), dtype=np.uint8), 'RGB')
    linhas = []
    for tipos, alvo in (([JPEG], 90000), ([PNG, JPEG], 10 ** 6)):
        f = codificar.codificar(img, tipos_aceitos=tipos, teto=_teto(alvo))
        linhas.append('%s %s' % (f.extensao, hashlib.sha256(f.dados).hexdigest()))
    return linhas


def test_mesmos_bytes_em_duas_execucoes_e_em_dois_processos():
    um = _no_processo()
    assert um == _no_processo()
    assert [x.split()[0] for x in um] == ['jpg', 'png']
    for _ in range(2):
        r = subprocess.run([sys.executable, '-c', _SCRIPT], capture_output=True, timeout=120, cwd=str(PASTA_MOTOR))
        assert r.returncode == 0, r.stderr.decode('utf-8', 'replace')
        assert r.stdout.decode('ascii').split() == ' '.join(um).split()


# ------------------------------------------------------------------ PNG sem perda e escolha do tipo
def test_png_devolve_os_pixels_iguais():
    img = _ruido(64, 48, semente=9)
    final = codificar.codificar(img, tipos_aceitos=[PNG, JPEG], teto=_teto(10 ** 6))
    assert final.extensao == 'png' and final.parametros['nivel_png'] == 9
    assert final.medidas['escolha'] == 'png_sem_perda'
    out = _abrir(final)
    assert out.mode == 'RGB' and np.array_equal(np.asarray(out), np.asarray(img))


def test_escolha_entre_png_e_jpeg_fica_registrada():
    img = _ruido(400, 300)
    final = codificar.codificar(img, tipos_aceitos=[PNG, JPEG], teto=_teto(150000))
    assert final.extensao == 'jpg' and final.medidas['escolha'] == 'jpeg_png_nao_cabe'
    assert final.medidas['png_bytes'] > 150000 >= len(final.dados)
    final = codificar.codificar(_chapada(400, 300), tipos_aceitos=[JPEG], teto=_teto(150000))
    assert final.extensao == 'jpg' and final.medidas['escolha'] == 'jpeg'
    final = codificar.codificar(img, tipos_aceitos=[PNG], teto=_teto(150000))
    assert final.extensao == 'png' and final.medidas['cabe_no_teto'] is False
    assert final.medidas['escolha'] == 'png_fora_do_teto_sem_jpeg_aceito'
    with pytest.raises(codificar.ErroCodificar) as e:
        codificar.codificar(img, tipos_aceitos=['image/gif'], teto=_teto(150000))
    assert e.value.codigo == 'sem_tipo_com_encoder'


# ------------------------------------------------------------------ transparencia
def _rgba(alfa):
    a = np.zeros((4, 4, 4), np.uint8)
    a[..., 1] = 200
    a[..., 3] = 255
    a[0, 0, 3] = alfa
    return Image.fromarray(a, 'RGBA')


def test_master_com_transparencia_sem_cor_recusa():
    with pytest.raises(codificar.ErroCodificar) as e:
        codificar.codificar(_rgba(0), tipos_aceitos=[PNG, JPEG], teto=_teto(10 ** 6))
    assert e.value.codigo == 'cor_de_achatamento_nao_definida'


def test_achatamento_com_a_cor_do_da_e_master_opaco_sem_mudanca():
    final = codificar.codificar(_rgba(0), tipos_aceitos=[PNG], teto=_teto(10 ** 6), cor_de_achatamento='#ff0000')
    out = np.asarray(_abrir(final))
    assert out.shape == (4, 4, 3) and tuple(out[0, 0]) == (255, 0, 0) and tuple(out[1, 1]) == (0, 200, 0)
    assert final.parametros['achatamento'] == {'cor': '#ff0000'}
    opaco = codificar.codificar(_rgba(255), tipos_aceitos=[PNG], teto=_teto(10 ** 6))
    assert opaco.parametros['achatamento'] is None and tuple(np.asarray(_abrir(opaco))[0, 0]) == (0, 200, 0)


# ------------------------------------------------------------------ giro de entrega (nº 139)
def test_giro_horario_e_anti_horario_dao_os_pixels_exatos():
    img, a = _assimetrica()  # 3 de largura, 2 de altura
    hor = np.asarray(_abrir(codificar.codificar(img, tipos_aceitos=[PNG], graus=90, sentido='horario')))
    anti = np.asarray(_abrir(codificar.codificar(img, tipos_aceitos=[PNG], graus=90, sentido='anti_horario')))
    assert hor.shape == anti.shape == (3, 2, 3)  # a dimensao troca
    # horario: a primeira coluna de baixo para cima vira a primeira linha
    assert [tuple(p) for p in hor[0]] == [tuple(a[1, 0]), tuple(a[0, 0])]
    assert [tuple(p) for p in anti[0]] == [tuple(a[0, 2]), tuple(a[1, 2])]
    for y in range(3):
        for x in range(2):
            assert tuple(hor[y, x]) == tuple(a[1 - x, y])
            assert tuple(anti[y, x]) == tuple(a[x, 2 - y])
    assert not np.array_equal(hor, anti)
    # 270 num sentido e 90 no outro
    h270 = np.asarray(_abrir(codificar.codificar(img, tipos_aceitos=[PNG], graus=270, sentido='horario')))
    assert np.array_equal(h270, anti)


def test_meia_volta_sem_sentido_e_quarto_de_volta_sem_sentido_recusa():
    img, a = _assimetrica()
    final = codificar.codificar(img, tipos_aceitos=[PNG], graus=180, sentido=None)
    assert np.array_equal(np.asarray(_abrir(final)), a[::-1, ::-1])
    assert final.parametros['rotacao'] == {'graus': 180, 'sentido': None}
    for graus in (90, 270):
        with pytest.raises(codificar.ErroCodificar) as e:
            codificar.codificar(img, tipos_aceitos=[PNG], graus=graus, sentido=None)
        assert e.value.codigo == 'rotacao_sem_sentido_confirmado'


def test_giro_no_jpeg_e_transposicao_do_arquivo():
    img = _ruido(40, 24)
    final = codificar.codificar(img, tipos_aceitos=[JPEG], teto=_teto(10 ** 6), graus=90, sentido='horario')
    assert _abrir(final).size == (24, 40)
    assert final.parametros['rotacao'] == {'graus': 90, 'sentido': 'horario'}


# ------------------------------------------------------------------ mutacoes: 100% detectadas
def _pixel_mudado(img):
    a = np.asarray(img).copy()
    a[5, 7, 0] = (int(a[5, 7, 0]) + 1) % 256  # numero-neutro: um nivel a mais num canal de 8 bits
    return Image.fromarray(a, 'RGB')


MUTACOES = [
    ('um_pixel', lambda k: dict(k, img=_pixel_mudado(k['img']))),
    ('sentido', lambda k: dict(k, sentido='anti_horario')),
    ('graus', lambda k: dict(k, graus=270)),
    ('teto', lambda k: dict(k, teto=_teto(30000))),
    ('tipos', lambda k: dict(k, tipos_aceitos=[JPEG])),
    ('meia_volta', lambda k: dict(k, graus=180, sentido=None)),
]


def test_entrada_mexida_muda_os_bytes_ou_os_parametros_em_100_por_cento():
    base = {'img': _ruido(64, 40, semente=4), 'tipos_aceitos': [PNG, JPEG], 'teto': _teto(10 ** 6), 'graus': 90,
            'sentido': 'horario'}

    def rodar(k):
        k = dict(k)
        return codificar.codificar(k.pop('img'), **k)
    ref = rodar(base)
    detectadas = 0
    for nome, mexer in MUTACOES:
        f = rodar(mexer(base))
        if f.sha256 != ref.sha256 or f.parametros != ref.parametros:
            detectadas += 1
        else:
            pytest.fail(nome)
    assert detectadas == len(MUTACOES)
    # e a cor de achatamento, num master com transparencia
    t = _rgba(0)
    a = codificar.codificar(t, tipos_aceitos=[PNG], cor_de_achatamento='#ff0000')
    b = codificar.codificar(t, tipos_aceitos=[PNG], cor_de_achatamento='#fe0000')
    assert a.sha256 != b.sha256 and a.parametros != b.parametros
