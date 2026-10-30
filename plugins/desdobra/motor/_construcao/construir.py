# -*- coding: utf-8 -*-
"""Backend de construcao proprio do motor (PEP 517 e PEP 660), sem pacote externo.

Por que existe: a lista de pacotes autorizados nao inclui setuptools, hatchling nem flit, e o pip precisa de
um backend para instalar o motor. O motor roda sempre no lugar, a partir da pasta do plugin, porque os
esquemas (motor/schemas) e o registro de limites (motor/fontes-de-limites.json) ficam fora do pacote.
Por isso so a instalacao editavel e suportada:

    python -m pip install --no-deps --no-build-isolation -e <plugin>/motor

A roda editavel leva um arquivo .pth com o caminho da pasta motor/ e o script de console "desdobra".
A versao vem de plugins/desdobra/.claude-plugin/plugin.json, que e a unica fonte da versao.
"""
import base64
import hashlib
import json
import os
import tomllib
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))
MOTOR = os.path.dirname(AQUI)
PLUGIN = os.path.dirname(MOTOR)


def _projeto():
    with open(os.path.join(MOTOR, 'pyproject.toml'), 'rb') as f:
        dados = tomllib.load(f)
    with open(os.path.join(PLUGIN, '.claude-plugin', 'plugin.json'), encoding='utf-8') as f:
        versao = json.load(f)['version']
    projeto = dados['project']
    return projeto['name'], versao, projeto.get('requires-python'), projeto.get('scripts', {}), \
        projeto.get('description', '')


def _nome_dist(nome):
    return nome.replace('-', '_')


def _metadados(nome, versao, requer_python, descricao):
    linhas = ['Metadata-Version: 2.1', 'Name: %s' % nome, 'Version: %s' % versao]
    if descricao:
        linhas.append('Summary: %s' % descricao)
    if requer_python:
        linhas.append('Requires-Python: %s' % requer_python)
    return '\n'.join(linhas) + '\n'


def _arquivos_dist_info(nome, versao, requer_python, scripts, descricao):
    pasta = '%s-%s.dist-info' % (_nome_dist(nome), versao)
    arquivos = {
        pasta + '/METADATA': _metadados(nome, versao, requer_python, descricao),
        pasta + '/WHEEL': 'Wheel-Version: 1.0\nGenerator: desdobra-construir\nRoot-Is-Purelib: true\nTag: py3-none-any\n',
    }
    if scripts:
        corpo = ''.join('%s = %s\n' % (k, v) for k, v in sorted(scripts.items()))
        arquivos[pasta + '/entry_points.txt'] = '[console_scripts]\n' + corpo
    return pasta, arquivos


def _hash_record(dados):
    resumo = base64.urlsafe_b64encode(hashlib.sha256(dados).digest()).rstrip(b'=').decode('ascii')
    return 'sha256=%s' % resumo


def _gravar_roda(pasta_saida, nome, versao, arquivos, pasta_info):
    nome_roda = '%s-%s-py3-none-any.whl' % (_nome_dist(nome), versao)
    registro = []
    caminho = os.path.join(pasta_saida, nome_roda)
    with zipfile.ZipFile(caminho, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for arq in sorted(arquivos):
            dados = arquivos[arq].encode('utf-8')
            z.writestr(arq, dados)
            registro.append('%s,%s,%d' % (arq, _hash_record(dados), len(dados)))
        registro.append('%s/RECORD,,' % pasta_info)
        z.writestr(pasta_info + '/RECORD', '\n'.join(registro) + '\n')
    return nome_roda


def get_requires_for_build_wheel(config_settings=None):
    return []


def get_requires_for_build_editable(config_settings=None):
    return []


def prepare_metadata_for_build_editable(metadata_directory, config_settings=None):
    nome, versao, requer_python, scripts, descricao = _projeto()
    pasta, arquivos = _arquivos_dist_info(nome, versao, requer_python, scripts, descricao)
    for arq, conteudo in arquivos.items():
        destino = os.path.join(metadata_directory, arq)
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, 'w', encoding='utf-8', newline='\n') as f:
            f.write(conteudo)
    return pasta


def build_editable(wheel_directory, config_settings=None, metadata_directory=None):
    nome, versao, requer_python, scripts, descricao = _projeto()
    pasta, arquivos = _arquivos_dist_info(nome, versao, requer_python, scripts, descricao)
    arquivos['__editable__.%s.pth' % _nome_dist(nome)] = MOTOR + '\n'
    return _gravar_roda(wheel_directory, nome, versao, arquivos, pasta)


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    raise RuntimeError('O motor desdobra roda no lugar, a partir da pasta do plugin. '
                       'Instale com: python -m pip install --no-deps --no-build-isolation -e <plugin>/motor')


def build_sdist(sdist_directory, config_settings=None):
    raise RuntimeError('O motor desdobra nao gera pacote fonte. Ele e distribuido dentro do plugin.')
