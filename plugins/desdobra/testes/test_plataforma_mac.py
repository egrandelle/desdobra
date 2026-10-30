# -*- coding: utf-8 -*-
"""Esqueleto do Mac: recusa rodar com mensagem clara e nunca executa o comando."""
import sys

import pytest

from desdobra import plataforma
from desdobra.plataforma.mac import MENSAGEM, MacNaoSuportado, PlataformaMac


def test_obter_no_mac_devolve_o_esqueleto():
    assert isinstance(plataforma.obter('darwin'), PlataformaMac)


def test_executar_isolado_recusa_sem_executar(tmp_path):
    marca = tmp_path / 'executou.txt'
    r = PlataformaMac().executar_isolado([sys.executable, '-c', 'open(%r, "w").write("x")' % str(marca)],
                                         2 ** 28, 10, tmp_path)
    assert r.situacao == 'recusado' and r.codigo is None and r.pico_bytes is None
    assert r.motivo == MENSAGEM == 'Mac ainda não suportado: aguardando máquina de teste.'
    assert not marca.exists()


def test_o_que_depende_do_sistema_levanta_erro_claro():
    with pytest.raises(MacNaoSuportado, match='Mac ainda não suportado: aguardando máquina de teste'):
        PlataformaMac().fontes_instaladas()


def test_porta_e_interpretador_nao_dependem_do_sistema():
    p = PlataformaMac()
    assert p.porta_livre() > 0 and p.interpretador().is_file()
