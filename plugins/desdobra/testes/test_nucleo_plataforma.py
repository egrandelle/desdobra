# -*- coding: utf-8 -*-
"""So a interface de plataforma (as implementacoes tem os proprios testes em test_plataforma*)."""
import inspect

import pytest

from desdobra import plataforma
from desdobra.plataforma import Plataforma, PlataformaSemSuporte, ResultadoFilho


def test_resultado_filho_so_aceita_as_situacoes_do_contrato():
    for s in ('ok', 'memoria', 'tempo', 'queda', 'recusado'):
        ResultadoFilho(situacao=s, codigo=None, pico_bytes=None, stdout_bytes=b'', stderr_resumo='')
    with pytest.raises(ValueError):
        ResultadoFilho(situacao='talvez', codigo=0, pico_bytes=None, stdout_bytes=b'', stderr_resumo='')


def test_assinatura_de_executar_isolado():
    parametros = list(inspect.signature(Plataforma.executar_isolado).parameters)
    assert parametros == ['self', 'comando', 'orcamento_bytes', 'tempo_s', 'pasta_trabalho', 'ambiente', 'entrada']
    assert inspect.signature(Plataforma.executar_isolado).parameters['entrada'].kind == inspect.Parameter.KEYWORD_ONLY
    assert inspect.signature(Plataforma.executar_isolado).parameters['ambiente'].kind == inspect.Parameter.KEYWORD_ONLY


def test_sistema_sem_suporte_recusa_com_mensagem(tmp_path):
    p = plataforma.obter('sunos5')
    assert isinstance(p, PlataformaSemSuporte)
    r = p.executar_isolado(['python', '-c', 'pass'], 1, 1.0, tmp_path)
    assert r.situacao == 'recusado' and r.codigo is None and 'sunos5' in r.motivo


def test_obter_devolve_uma_plataforma():
    assert isinstance(plataforma.obter(), Plataforma)


def test_porta_livre_e_interpretador():
    p = PlataformaSemSuporte('teste')
    porta = p.porta_livre()
    assert isinstance(porta, int) and porta > 0
    assert p.interpretador().is_file()
    with pytest.raises(NotImplementedError):
        p.fontes_instaladas()
