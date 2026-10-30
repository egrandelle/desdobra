# -*- coding: utf-8 -*-
"""A lista de efeitos e ajustes que o laudo marca como "suportado pelo render" bate com o psd-tools instalado."""
import inspect

import psd_tools
from psd_tools.api import adjustments as api_ajustes
from psd_tools.api import effects as api_efeitos
from psd_tools.api.layers import AdjustmentLayer

from desdobra.laudo import efeitos_1260
from desdobra.leitor import adaptador


def test_versao_conferida_e_a_instalada():
    assert psd_tools.__version__ == efeitos_1260.VERSAO_CONFERIDA == adaptador.VERSAO_PSD_TOOLS_CONFERIDA


def test_efeitos_lidos_pela_api():
    classes = {nome for nome, obj in inspect.getmembers(api_efeitos, inspect.isclass)
               if obj.__module__ == api_efeitos.__name__ and not nome.startswith('_') and nome != 'Effects'}
    assert classes == set(efeitos_1260.EFEITOS_LIDOS)


def test_overlays_e_traco_desenhados_pelo_compositor():
    overlays = set(adaptador.overlays_do_compositor())
    desenhados = {n.lower() for n in efeitos_1260.EFEITOS_DESENHADOS} - {'stroke'}
    assert overlays == desenhados
    cc = adaptador.modulo_compositor()
    fonte = inspect.getsource(cc.Compositor._add_stroke_effects)
    assert '_readable(layer, "stroke")' in fonte
    nao = inspect.getsource(cc.Compositor._compose_effects)
    assert 'not drawn at all' in nao


def test_ajustes_no_composto():
    assert set(adaptador.ajustes_do_compositor()) == set(efeitos_1260.AJUSTES_NO_COMPOSTO)
    kinds = {obj.__name__.lower() for _n, obj in inspect.getmembers(api_ajustes, inspect.isclass)
             if issubclass(obj, AdjustmentLayer) and obj is not AdjustmentLayer and obj.__module__ == api_ajustes.__name__}
    assert kinds == set(efeitos_1260.AJUSTES_NO_COMPOSTO) | set(efeitos_1260.AJUSTES_FORA_DO_COMPOSTO)


def test_pacotes_do_composto_presentes_no_ambiente():
    assert adaptador.pacotes_opcionais() == {'aggdraw': True, 'scipy': True}
