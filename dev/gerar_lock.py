# -*- coding: utf-8 -*-
"""Gera os locks com hash a partir do relatorio do pip (pip install --dry-run --report).

Uso (na raiz do repositorio, com o ambiente de desenvolvimento):
  .venv/Scripts/python.exe -m pip install --dry-run --ignore-installed --only-binary=:all: \
      --index-url https://pypi.org/simple --report rel_run.json -r dev/requisitos-execucao.txt
  .venv/Scripts/python.exe -m pip install --dry-run --ignore-installed --only-binary=:all: \
      --index-url https://pypi.org/simple --report rel_dev.json -r dev/requisitos-execucao.txt -r dev/requisitos-dev.txt
  .venv/Scripts/python.exe dev/gerar_lock.py rel_run.json rel_dev.json

Grava plugins/desdobra/motor/requirements.lock (execucao) e requirements-dev.lock (so o que falta para os
testes, com -r para o lock de execucao). Cada linha leva o hash sha256 do arquivo exato que o pip escolheu
nesta maquina. O relatorio fica fora do repositorio.
"""
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOTOR = os.path.join(RAIZ, 'plugins', 'desdobra', 'motor')

CABECALHO = """# Lock gerado por dev/gerar_lock.py a partir de "pip install --dry-run --report".
# Instalar com: python -m pip install --require-hashes --no-deps --only-binary=:all: -r {nome}
# Hashes conferidos so para Windows x86-64 com CPython 3.14 (rodas cp314-win_amd64 e py3-none-any).
# Os hashes das rodas de Mac (macosx arm64 e x86-64) entram no porte para o Mac, junto com o teste no Mac.
"""


def ler(relatorio):
    d = json.load(open(relatorio, encoding='utf-8'))
    pacotes = {}
    for item in d['install']:
        meta = item['metadata']
        info = item['download_info']
        hashes = (info.get('archive_info') or {}).get('hashes') or {}
        if 'sha256' not in hashes:
            raise SystemExit('pacote sem sha256 no relatorio: %s' % meta['name'])
        nome = meta['name'].lower().replace('_', '-')
        pacotes[nome] = (meta['version'], hashes['sha256'], info['url'].rsplit('/', 1)[-1])
    return pacotes


def linhas(pacotes):
    out = []
    for nome in sorted(pacotes):
        versao, sha, arquivo = pacotes[nome]
        out.append('%s==%s \\\n    --hash=sha256:%s\n    # %s\n' % (nome, versao, sha, arquivo))
    return out


def main():
    execucao, dev = ler(sys.argv[1]), ler(sys.argv[2])
    so_dev = {k: v for k, v in dev.items() if k not in execucao}
    divergentes = [k for k in execucao if k in dev and dev[k][:2] != execucao[k][:2]]
    if divergentes:
        raise SystemExit('versao ou hash diferente entre os relatorios: %s' % divergentes)
    with open(os.path.join(MOTOR, 'requirements.lock'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(CABECALHO.format(nome='requirements.lock'))
        f.writelines(linhas(execucao))
    with open(os.path.join(MOTOR, 'requirements-dev.lock'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(CABECALHO.format(nome='requirements-dev.lock'))
        f.write('# So para desenvolvimento e testes. Nunca entra no ambiente do plugin.\n')
        f.write('-r requirements.lock\n')
        f.writelines(linhas(so_dev))
    print('execucao: %d pacotes; dev: %d a mais' % (len(execucao), len(so_dev)))


if __name__ == '__main__':
    main()
