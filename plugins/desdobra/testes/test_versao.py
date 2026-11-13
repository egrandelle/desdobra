# -*- coding: utf-8 -*-
"""Versao do plugin: uma fonte so (o manifesto), com a entrada do CHANGELOG e as bibliotecas de specs na mesma versao.

A versao vem so de .claude-plugin/plugin.json (desdobra.__version__ le de la). O M7c entrega contratos novos
(pacote-modelo/2, sugestoes/1, perfil-marca/1, marca-job/1, medicoes-sugestao/1), e a versao que os leva e a 0.9.0
ou uma posterior. A primeira entrada do CHANGELOG e a da versao do manifesto, e o texto dele segue a regra de
escrita do projeto (sem travessao nem meia-risca).
"""
import json
import re

from conftest import RAIZ_PLUGIN

import desdobra

MANIFESTO = RAIZ_PLUGIN / '.claude-plugin' / 'plugin.json'
CHANGELOG = RAIZ_PLUGIN.parent.parent / 'CHANGELOG.md'
SCHEMAS = RAIZ_PLUGIN / 'motor' / 'schemas'
CONTRATOS_DO_M7C = ('pacote-modelo-2.json', 'sugestoes-1.json', 'perfil-marca-1.json', 'marca-job-1.json',
                    'medicoes-sugestao-1.json')


def _versao_do_manifesto():
    return json.loads(MANIFESTO.read_text(encoding='utf-8'))['version']


def _tupla(versao):
    assert re.fullmatch(r'\d+\.\d+\.\d+', versao), versao
    return tuple(int(p) for p in versao.split('.'))


def test_o_motor_le_a_versao_do_manifesto():
    assert desdobra.__version__ == _versao_do_manifesto()


def test_contratos_do_m7c_saem_na_0_9_0_ou_depois():
    for nome in CONTRATOS_DO_M7C:
        assert (SCHEMAS / nome).is_file(), nome
    assert _tupla(_versao_do_manifesto()) >= (0, 9, 0)


def test_primeira_entrada_do_changelog_e_a_versao_do_manifesto():
    texto = CHANGELOG.read_text(encoding='utf-8')
    entradas = re.findall(r'^## (\d+\.\d+\.\d+) ', texto, flags=re.M)
    assert entradas, 'o CHANGELOG nao tem entrada de versao'
    assert entradas[0] == _versao_do_manifesto()
    assert len(entradas) == len(set(entradas))


def test_changelog_sem_travessao_nem_meia_risca():
    texto = CHANGELOG.read_text(encoding='utf-8')
    assert '—' not in texto and '–' not in texto


def test_bibliotecas_de_specs_na_versao_do_manifesto():
    versao = _versao_do_manifesto()
    arquivos = sorted((RAIZ_PLUGIN / 'biblioteca-specs').glob('*.json'))
    assert arquivos
    for arq in arquivos:
        assert json.loads(arq.read_text(encoding='utf-8'))['motor_versao'] == versao, arq.name
