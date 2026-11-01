# -*- coding: utf-8 -*-
"""Varredura do pacote: o que vai para a maquina da agencia nao leva material de cliente nem coisa proibida.

O repositorio inteiro e clonado na maquina das agencias que instalam o plugin. Por isso a varredura olha o
que o git levaria: os arquivos versionados e os novos que o .gitignore nao exclui (git ls-files -co
--exclude-standard). Reprova:
  - PSD e PSB (pela extensao e pela assinatura 8BPS);
  - arquivo de fonte (pela extensao e pelas assinaturas de desdobra.arquivos);
  - __pycache__ e bytecode;
  - zip (pela extensao e pela assinatura PK);
  - imagem raster (PNG, JPEG, GIF, BMP, TIFF, WebP), pela extensao e pela assinatura, fora de EXCECOES_IMAGEM;
  - laudo, estrutura, recusa, estado ou relatorio gravado pelo motor (arquivo que nao e codigo .py), fora de
    EXCECOES_SAIDA;
  - relatorio da regressao (regressao-<data>.json e .md), pelo nome;
  - segredo (o mesmo detector do envelope, com os padroes do registro);
  - nome de cliente ou marca do material de teste, no conteudo e no caminho, com a lista de fora do repositorio.

A lista de palavras proibidas nunca fica no repositorio, nem codificada: ela vem de um arquivo fora dele,
apontado pela variavel de ambiente DESDOBRA_PALAVRAS_PROIBIDAS, uma palavra por linha. A linha que comeca com
"sigla:" conta so em maiusculas e como palavra inteira; linha vazia e linha que comeca com # sao ignoradas.
Sem a variavel, o teste de nomes e pulado. A autoverificacao da varredura usa so palavras inventadas.
"""
import os
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

import pytest

from conftest import RAIZ_PLUGIN
from desdobra.arquivos import ASSINATURA_PSD, EXTENSOES_FONTE, EXTENSOES_PSD, assinatura_de_fonte
from desdobra.sugestao import segredos

RAIZ_REPOSITORIO = RAIZ_PLUGIN.parent.parent
VARIAVEL_PALAVRAS = 'DESDOBRA_PALAVRAS_PROIBIDAS'
ASSINATURA_ZIP = b'PK\x03\x04'
EXTENSOES_ZIP = ('.zip',)
EXTENSOES_BYTECODE = ('.pyc', '.pyo')
EXTENSOES_IMAGEM = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tif', '.tiff', '.webp')
ASSINATURAS_IMAGEM = (b'\x89PNG', b'\xff\xd8\xff', b'GIF8', b'II*\x00', b'MM\x00*')
# nenhuma imagem e nenhuma saida do motor fazem parte do pacote hoje; a excecao, se um dia existir, entra aqui
# a imagem de referencia do autoteste do render, desenhada so com a fonte gerada pelo motor (decisoes-v1.md, n. 36)
EXCECOES_IMAGEM = frozenset({'plugins/desdobra/motor/referencias/autoteste-render.png'})
EXCECOES_SAIDA = frozenset()
SAIDA_DO_MOTOR = re.compile(r'"esquema"\s*:\s*"(laudo|estrutura|recusa|estado|regressao|envelope|pacote-modelo)/1"')
# relatorio da regressao (regressao-<data>.json e .md): leva os slugs do corpus no conteudo
RELATORIO_REGRESSAO = re.compile(r'(^|/)regressao-\d{8}-\d{6}\.(json|md)$')


def eh_imagem(sufixo, dados):
    if sufixo in EXTENSOES_IMAGEM:
        return True
    if dados[:4] == b'RIFF' and dados[8:12] == b'WEBP':
        return True
    # BMP: "BM" seguido do tamanho e de 4 bytes reservados em zero
    if dados[:2] == b'BM' and len(dados) > 14 and dados[6:10] == b'\x00\x00\x00\x00':
        return True
    return any(dados.startswith(a) for a in ASSINATURAS_IMAGEM)


def _sem_acento(texto):
    return ''.join(c for c in unicodedata.normalize('NFKD', texto) if not unicodedata.combining(c)).casefold()


def ler_palavras(caminho):
    palavras, siglas = [], []
    for linha in Path(caminho).read_text(encoding='utf-8').splitlines():
        linha = linha.strip()
        if not linha or linha.startswith('#'):
            continue
        if linha.lower().startswith('sigla:'):
            siglas.append(linha.split(':', 1)[1].strip())
        else:
            palavras.append(linha)
    return palavras, siglas


def compilar_palavras(palavras, siglas):
    padroes = []
    for p in palavras:
        palavra = _sem_acento(p)
        corpo = r'[\s_\-]*'.join(re.escape(parte) for parte in re.split(r'[\s_\-]+', palavra))
        padroes.append((palavra, re.compile(r'(?<![a-z0-9])' + corpo + r'(?![a-z0-9])')))
    padroes_siglas = [(s, re.compile(r'(?<![A-Za-z0-9])' + re.escape(s) + r'(?![A-Za-z0-9])')) for s in siglas if s]
    return padroes, padroes_siglas


def palavras_do_ambiente():
    caminho = os.environ.get(VARIAVEL_PALAVRAS)
    if not caminho or not Path(caminho).is_file():
        return None
    return compilar_palavras(*ler_palavras(caminho))


def palavras_de_cliente(texto, padroes):
    if not padroes:
        return []
    palavras, siglas = padroes
    normal = _sem_acento(texto)
    achadas = [p for p, rx in palavras if rx.search(normal)]
    achadas += [s for s, rx in siglas if rx.search(texto)]
    return achadas


def _texto(dados):
    if b'\x00' in dados:
        return None
    try:
        return dados.decode('utf-8')
    except UnicodeDecodeError:
        return None


def varrer(raiz, relativos, detector=None, palavras=None):
    """Lista de (caminho relativo, motivo) do que nao pode ir no pacote. palavras: compilar_palavras(...)."""
    detector = detector or segredos.Detector()
    problemas = []
    for rel in relativos:
        caminho = raiz / rel
        partes = rel.replace('\\', '/').split('/')
        sufixo = caminho.suffix.lower()
        if '__pycache__' in partes or sufixo in EXTENSOES_BYTECODE:
            problemas.append((rel, '__pycache__ ou bytecode'))
        if RELATORIO_REGRESSAO.search(rel.replace('\\', '/')):
            problemas.append((rel, 'relatorio da regressao'))
        if palavras_de_cliente(rel, palavras):
            # o motivo nunca repete a palavra achada, para a mensagem do teste nao virar ocorrencia
            problemas.append((rel, 'nome de cliente no caminho'))
        if not caminho.is_file():
            continue
        dados = caminho.read_bytes()
        inicio = dados[:len(ASSINATURA_PSD)]
        if sufixo in EXTENSOES_PSD or inicio == ASSINATURA_PSD:
            problemas.append((rel, 'PSD ou PSB'))
        if sufixo in EXTENSOES_FONTE or assinatura_de_fonte(dados[:64]):
            problemas.append((rel, 'arquivo de fonte'))
        if sufixo in EXTENSOES_ZIP or inicio == ASSINATURA_ZIP:
            problemas.append((rel, 'zip'))
        if rel not in EXCECOES_IMAGEM and eh_imagem(sufixo, dados):
            problemas.append((rel, 'imagem raster'))
        texto = _texto(dados)
        if texto is None:
            continue
        if sufixo != '.py' and rel not in EXCECOES_SAIDA and SAIDA_DO_MOTOR.search(texto):
            problemas.append((rel, 'saida gravada pelo motor'))
        for nome, _ in detector.procurar(texto):
            problemas.append((rel, 'segredo (%s)' % nome))
        if palavras_de_cliente(texto, palavras):
            problemas.append((rel, 'nome de cliente no conteudo'))
    return problemas


def arquivos_do_repositorio():
    git = shutil.which('git')
    if git is None or not (RAIZ_REPOSITORIO / '.git').exists():
        pytest.skip('a varredura do pacote precisa do git e do repositorio clonado')
    saida = subprocess.run([git, '-C', str(RAIZ_REPOSITORIO), 'ls-files', '-co', '--exclude-standard', '-z'],
                           capture_output=True, check=True).stdout
    return sorted({p for p in saida.decode('utf-8').split('\0') if p})


# ------------------------------------------------------------------ o pacote de verdade
def test_repositorio_nao_leva_material_proibido():
    relativos = arquivos_do_repositorio()
    assert any(r.startswith('plugins/desdobra/') for r in relativos)
    problemas = varrer(RAIZ_REPOSITORIO, relativos)
    assert problemas == [], '\n'.join('%s: %s' % p for p in problemas)


def test_pasta_do_plugin_nao_leva_material_proibido():
    prefixo = RAIZ_PLUGIN.relative_to(RAIZ_REPOSITORIO).as_posix() + '/'
    relativos = [r for r in arquivos_do_repositorio() if r.startswith(prefixo)]
    assert relativos
    problemas = varrer(RAIZ_REPOSITORIO, relativos)
    assert problemas == [], '\n'.join('%s: %s' % p for p in problemas)


@pytest.mark.skipif(palavras_do_ambiente() is None,
                    reason='defina DESDOBRA_PALAVRAS_PROIBIDAS com o arquivo de palavras, fora do repositorio')
def test_repositorio_nao_leva_nome_de_cliente():
    palavras = palavras_do_ambiente()
    assert palavras[0] or palavras[1]
    problemas = [p for p in varrer(RAIZ_REPOSITORIO, arquivos_do_repositorio(), palavras=palavras)
                 if p[1].startswith('nome de cliente')]
    assert problemas == [], '\n'.join('%s: %s' % p for p in problemas)


def test_gitignore_exclui_material_de_cliente_e_saidas():
    git = shutil.which('git')
    if git is None or not (RAIZ_REPOSITORIO / '.git').exists():
        pytest.skip('precisa do git')
    for nome in ('x.psd', 'x.psb', 'x.ttf', 'x.otf', 'x.woff', 'x.woff2', 'x.pfa', 'x.fon', 'motor/__pycache__/x.pyc',
                 'x.png', 'x.jpg', 'x.jpeg', 'x.tif', 'x.pdf', 'x.indd', 'x.idml', 'qualquer/laudo.json',
                 'qualquer/estrutura.json', 'qualquer/recusa.json', 'qualquer/saida-padrao.txt', 'qualquer/bruto/x',
                 'qualquer/.trabalho/x', 'qualquer/.tmp-x.json.1', 'qualquer/regressao-20261030-100751.json',
                 'qualquer/regressao-20261030-100751.md', 'regressao-final/marca--peca/x.txt',
                 'saida-regressao/marca--peca/x.txt'):
        r = subprocess.run([git, '-C', str(RAIZ_REPOSITORIO), 'check-ignore', '-q', '--no-index', nome],
                           capture_output=True)
        assert r.returncode == 0, '%s deveria estar no .gitignore' % nome
    # o contrato do relatorio e o codigo da regressao continuam versionados
    for nome in ('plugins/desdobra/motor/schemas/regressao-1.json', 'plugins/desdobra/motor/desdobra/regressao/x.py'):
        r = subprocess.run([git, '-C', str(RAIZ_REPOSITORIO), 'check-ignore', '-q', '--no-index', nome],
                           capture_output=True)
        assert r.returncode == 1, '%s nao deveria estar no .gitignore' % nome


# ------------------------------------------------------------------ a varredura funciona
# palavras inventadas: nao sao de nenhum cliente nem do material de teste
PALAVRAS_DE_TESTE = compilar_palavras(['Marca Inventada Zirconia', 'Fonte Quimerica'], ['ZQX'])


def _arquivos_ruins(raiz):
    falsos = __import__('test_sugestao_apoio').segredos_falsos()
    arquivos = {
        'a/kv.psd': b'qualquer',
        'a/disfarcado.bin': ASSINATURA_PSD + b'\x00\x01',
        'b/fonte.ttf': b'x',
        'b/sfnt.dat': b'\x00\x01\x00\x00resto',
        'b/otto.dat': b'OTTOresto',
        'b/woff.dat': b'wOFFresto',
        'b/woff2.dat': b'wOF2resto',
        'b/tipo1.dat': b'%!PS-AdobeFont-1.0: resto',
        'b/bitmap.fon': b'MZresto',
        'c/pacote.zip': b'x',
        'c/disfarcado.dat': ASSINATURA_ZIP + b'resto',
        'd/__pycache__/m.cpython-314.pyc': b'x',
        'e/config.txt': ('chave = ' + falsos['chave de API do Google'] + '\n').encode('utf-8'),
        'f/nota.md': 'Campanha da Marca Inventada Zircônia\n'.encode('utf-8'),
        'g/fonte-quimerica.txt': b'ok',
        'h/sigla.txt': 'peca do ZQX\n'.encode('utf-8'),
        'i/miniatura.png': b'x',
        'i/disfarcada.dat': b'\x89PNG\r\n\x1a\nresto',
        'i/foto.dat': b'\xff\xd8\xff\xe0resto',
        'j/laudo-copiado.json': '{"esquema": "laudo/1", "camadas": []}\n'.encode('utf-8'),
        'k/regressao-20261030-100751.md': '# Regressao\n\n| marca--peca | ok |\n'.encode('utf-8'),
        'k/regressao-20261030-100751.json': '{"resultado": "nada_piorou"}\n'.encode('utf-8'),
        'ok/limpo.py': 'print("tudo certo")\n'.encode('utf-8'),
    }
    for rel, dados in arquivos.items():
        p = raiz / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(dados)
    return sorted(arquivos)


def test_varredura_pega_cada_caso(tmp_path):
    relativos = _arquivos_ruins(tmp_path)
    problemas = varrer(tmp_path, relativos, palavras=PALAVRAS_DE_TESTE)
    sujos = {rel for rel, _ in problemas}
    assert sujos == set(relativos) - {'ok/limpo.py'}
    motivos = {rel: m for rel, m in problemas}
    assert motivos['b/woff2.dat'] == 'arquivo de fonte' and motivos['c/disfarcado.dat'] == 'zip'
    assert motivos['b/tipo1.dat'] == 'arquivo de fonte' and motivos['i/foto.dat'] == 'imagem raster'
    assert motivos['j/laudo-copiado.json'] == 'saida gravada pelo motor'
    assert motivos['k/regressao-20261030-100751.md'] == 'relatorio da regressao'
    assert motivos['k/regressao-20261030-100751.json'] == 'relatorio da regressao'
    assert motivos['e/config.txt'].startswith('segredo')
    assert all('Zirc' not in m and 'Quim' not in m for _r, m in problemas)


def test_lista_de_palavras_vem_de_arquivo(tmp_path):
    lista = tmp_path / 'palavras.txt'
    lista.write_text('# comentario\nMarca Inventada Zirconia\n\nsigla:ZQX\n', encoding='utf-8')
    palavras, siglas = ler_palavras(lista)
    assert palavras == ['Marca Inventada Zirconia'] and siglas == ['ZQX']


@pytest.mark.parametrize('texto, esperado', [
    ('Bbox do grupo', False), ('ZQXA', False), ('azqx', False), ('sigla zqx minuscula', False),
    ('sigla ZQX no meio', True), ('marca_inventada-zirconia', True),
])
def test_siglas_so_como_palavra_inteira(texto, esperado):
    assert bool(palavras_de_cliente(texto, PALAVRAS_DE_TESTE)) is esperado
