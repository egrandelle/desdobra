# -*- coding: utf-8 -*-
"""O master sai com ou sem perfil embutido so pelo parametro do job (decisoes-v1.md, 140).

Achado da medicao do M6 no corpus: com documento que tem perfil, o ImageCms.profileToProfile deixa o perfil sRGB em
img.info e o PNG o gravava mesmo com o job pedindo saida sem perfil.
"""
import io

from PIL import Image, ImageCms

from desdobra.render import filho


def _convertida(modo='RGB'):
    srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB'))
    img = ImageCms.profileToProfile(Image.new('RGB', (4, 3), (10, 20, 30)), srgb, srgb)
    assert img.info.get('icc_profile')  # o caso do achado: a conversao poe o perfil em info
    return img.convert(modo) if modo != 'RGB' else img


def _perfil(dados):
    with Image.open(io.BytesIO(dados)) as im:
        return im.info.get('icc_profile')


def test_master_convertido_sai_sem_perfil_quando_o_job_pede_sem():
    for modo in ('RGB', 'RGBA'):
        assert not _perfil(filho._png_do_master(_convertida(modo), False))


def test_master_sai_com_perfil_srgb_quando_o_job_pede():
    perfil = _perfil(filho._png_do_master(Image.new('RGB', (4, 3)), True))
    assert perfil and ImageCms.getProfileDescription(ImageCms.ImageCmsProfile(io.BytesIO(perfil))).strip()


def test_master_sem_conversao_continua_sem_perfil():
    assert not _perfil(filho._png_do_master(Image.new('RGB', (4, 3)), False))
