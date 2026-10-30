# -*- coding: utf-8 -*-
"""Contratos versionados: carrega os esquemas JSON de motor/schemas e valida os arquivos trocados.

Convencao:
  - cada contrato tem nome e versao, escritos "nome/versao" (por exemplo "estado/1");
  - o esquema fica em motor/schemas/<nome>-<versao>.json (por exemplo estado-1.json);
  - todo arquivo de contrato tem o campo "esquema" com o mesmo "nome/versao";
  - uma versao publicada nunca muda de forma incompativel: mudanca incompativel cria a versao seguinte.

Uso:
    from desdobra import contratos
    contratos.validar(dados, 'estado/1')            # ErroContrato se nao bater
    dados = contratos.ler(caminho, 'estado/1')       # le e valida
    contratos.gravar(caminho, dados, 'estado/1')     # valida e grava de forma atomica
"""
import functools
import json
import re
from pathlib import Path

import jsonschema
from jsonschema.validators import validator_for

from desdobra import PASTA_MOTOR
from desdobra.arquivos import gravar_json_atomico, ler_json

PASTA_ESQUEMAS = PASTA_MOTOR / 'schemas'
_NOME = re.compile(r'^[a-z][a-z0-9-]*/[1-9][0-9]*$')


class ErroContrato(Exception):
    """O dado nao segue o contrato. A mensagem diz qual contrato, onde e o que falhou."""

    def __init__(self, esquema, mensagem, onde=None, origem=None):
        self.esquema = esquema
        self.onde = onde
        self.origem = origem
        partes = ['O dado']
        if origem:
            partes = ['O arquivo %s' % origem]
        texto = '%s não segue o contrato %s' % (partes[0], esquema)
        if onde:
            texto += ', no campo %s' % onde
        super().__init__('%s: %s' % (texto, mensagem))


def arquivo_do_esquema(nome_versao):
    if not _NOME.match(nome_versao or ''):
        raise ValueError('nome de contrato inválido: %r (use "nome/versão", por exemplo "estado/1")' % nome_versao)
    nome, versao = nome_versao.split('/')
    return PASTA_ESQUEMAS / ('%s-%s.json' % (nome, versao))


@functools.cache
def carregar_esquema(nome_versao):
    caminho = arquivo_do_esquema(nome_versao)
    if not caminho.is_file():
        raise ErroContrato(nome_versao, 'esquema não encontrado em motor/schemas (%s)' % caminho.name)
    with open(caminho, encoding='utf-8') as f:
        esquema = json.load(f)
    classe = validator_for(esquema)
    classe.check_schema(esquema)
    return esquema


@functools.cache
def _validador(nome_versao):
    esquema = carregar_esquema(nome_versao)
    return validator_for(esquema)(esquema)


def listar_esquemas():
    return sorted('%s/%s' % tuple(p.stem.rsplit('-', 1)) for p in PASTA_ESQUEMAS.glob('*-*.json'))


def _onde(erro):
    if not erro.absolute_path:
        return '(raiz)'
    return '/' + '/'.join(str(p) for p in erro.absolute_path)


def validar(dados, nome_versao, origem=None):
    validador = _validador(nome_versao)
    erro = jsonschema.exceptions.best_match(validador.iter_errors(dados))
    if erro is not None:
        raise ErroContrato(nome_versao, erro.message, onde=_onde(erro), origem=origem)
    if isinstance(dados, dict) and dados.get('esquema') != nome_versao:
        raise ErroContrato(nome_versao, 'o campo "esquema" deveria ser %r e veio %r' % (nome_versao, dados.get('esquema')),
                           onde='/esquema', origem=origem)
    return dados


def ler(caminho, nome_versao):
    caminho = Path(caminho)
    try:
        dados = ler_json(caminho)
    except FileNotFoundError:
        raise ErroContrato(nome_versao, 'arquivo não encontrado', origem=caminho.name) from None
    except ValueError as e:
        raise ErroContrato(nome_versao, 'JSON inválido (%s)' % e, origem=caminho.name) from None
    return validar(dados, nome_versao, origem=caminho.name)


def gravar(caminho, dados, nome_versao):
    validar(dados, nome_versao, origem=Path(caminho).name)
    gravar_json_atomico(caminho, dados)
