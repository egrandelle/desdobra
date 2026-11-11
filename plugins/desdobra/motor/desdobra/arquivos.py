# -*- coding: utf-8 -*-
"""Arquivos: hash sha256, gravacao atomica, somente leitura e recusa de arquivo de fonte.

Gravacao atomica: grava num temporario na mesma pasta, faz fsync e renomeia com os.replace. Quem le nunca ve
arquivo pela metade. Se o processo cair no meio, sobra no maximo um temporario com prefixo ".tmp-", que o
proximo comando pode apagar. No Windows, a troca recusada porque outro processo le o arquivo naquele instante e
tentada de novo por cerca de meio segundo (TROCA_ESPERAS_S).
"""
import hashlib
import json
import os
import stat
import time
from pathlib import Path

PREFIXO_TEMPORARIO = '.tmp-'
# as esperas entre as tentativas da troca atomica recusada pelo Windows (arquivo aberto por outro naquele instante):
# cerca de meio segundo no total, para a gravacao nunca prender quem espera por ela
TROCA_ESPERAS_S = (0.02, 0.05, 0.1, 0.15, 0.2)  # numero-neutro: segundos entre as tentativas, crescendo
EXTENSOES_FONTE = ('.ttf', '.otf', '.woff', '.woff2', '.ttc', '.otc', '.dfont', '.pfb', '.pfm', '.afm', '.eot',
                   '.pfa', '.fon', '.fnt', '.bdf', '.pcf', '.suit', '.lwfn', '.t42')
# Assinaturas internas de formato de fonte, comparadas com o inicio do arquivo: sfnt TrueType, OpenType CFF,
# colecao, WOFF, WOFF2, Mac "true" e "typ1", Type 1 em texto (.pfa e .ps de fonte), BDF e PCF.
ASSINATURAS_FONTE = (b'\x00\x01\x00\x00', b'OTTO', b'ttcf', b'wOFF', b'wOF2', b'true', b'typ1', b'%!PS-AdobeFont',
                     b'%!FontType1', b'STARTFONT', b'\x01fcp')
# Pacotes, reconhecidos pela assinatura e nao so pela extensao. Zip e tar sao inspecionados sem extrair (lista de
# membros e primeiros bytes de cada um, na memoria). Os comprimidos (gzip, bzip2, xz, 7z, rar, zstd) so dariam
# para conferir descomprimindo, e por isso contam como suspeitos.
ASSINATURA_ZIP = b'PK'
MAGIA_TAR = b'ustar'
POSICAO_MAGIA_TAR = 257  # numero-neutro: posicao do campo magic no cabecalho tar (POSIX ustar)
ASSINATURAS_COMPRIMIDO = (b'\x1f\x8b', b'BZh', b'\xfd7zXZ\x00', b"7z\xbc\xaf'\x1c", b'Rar!\x1a\x07', b'\x28\xb5\x2f\xfd')
BYTES_ASSINATURA = max(max(len(a) for a in ASSINATURAS_FONTE), POSICAO_MAGIA_TAR + len(MAGIA_TAR))
EXTENSOES_PACOTE = ('.zip', '.tar')
EXTENSOES_COMPRIMIDO = ('.gz', '.tgz', '.bz2', '.tbz', '.tbz2', '.xz', '.txz', '.7z', '.rar', '.zst')
EXTENSOES_PSD = ('.psd', '.psb')
ASSINATURA_PSD = b'8BPS'
TAMANHO_BLOCO = 1 << 20  # numero-neutro: bloco de leitura de 1 MiB para o hash, sem efeito no resultado


def sha256_arquivo(caminho):
    h = hashlib.sha256()
    with open(caminho, 'rb') as f:
        while bloco := f.read(TAMANHO_BLOCO):
            h.update(bloco)
    return h.hexdigest()


def sha256_bytes(dados):
    return hashlib.sha256(dados).hexdigest()


def sha256_pasta(pasta):
    """Hash de uma pasta: sha256 da lista ordenada de (caminho relativo com /, sha256 do arquivo)."""
    pasta = Path(pasta)
    h = hashlib.sha256()
    for arq in sorted(p for p in pasta.rglob('*') if p.is_file() and not p.name.startswith(PREFIXO_TEMPORARIO)):
        rel = arq.relative_to(pasta).as_posix()
        h.update(rel.encode('utf-8') + b'\0' + sha256_arquivo(arq).encode('ascii') + b'\n')
    return h.hexdigest()


def sha256_caminho(caminho):
    """sha256 de um arquivo ou de uma pasta; None se nao existe."""
    caminho = Path(caminho)
    if caminho.is_file():
        return sha256_arquivo(caminho)
    if caminho.is_dir():
        return sha256_pasta(caminho)
    return None


def _trocar(temporario, caminho):
    """os.replace com novas tentativas curtas: no Windows, a troca falha enquanto outro processo le o arquivo naquele
    instante (o laco de espera de um teste, um antivirus, o indexador). Depois da ultima, o erro sobe."""
    for espera in TROCA_ESPERAS_S:
        try:
            os.replace(temporario, caminho)
            return
        except PermissionError:
            time.sleep(espera)
    os.replace(temporario, caminho)


def gravar_bytes_atomico(caminho, dados):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_name('%s%s.%d' % (PREFIXO_TEMPORARIO, caminho.name, os.getpid()))
    try:
        with open(temporario, 'wb') as f:
            f.write(dados)
            f.flush()
            os.fsync(f.fileno())
        _trocar(temporario, caminho)
    finally:
        if temporario.exists():
            temporario.unlink()


def gravar_texto_atomico(caminho, texto):
    gravar_bytes_atomico(caminho, texto.encode('utf-8'))


def para_json(dados):
    return json.dumps(dados, ensure_ascii=False, indent=1, sort_keys=False) + '\n'


def gravar_json_atomico(caminho, dados):
    gravar_texto_atomico(caminho, para_json(dados))


def ler_json(caminho):
    with open(caminho, encoding='utf-8') as f:
        return json.load(f)


def tornar_somente_leitura(caminho):
    modo = os.stat(caminho).st_mode
    os.chmod(caminho, modo & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def tornar_gravavel(caminho):
    os.chmod(caminho, os.stat(caminho).st_mode | stat.S_IWUSR)


def eh_somente_leitura(caminho):
    return not os.access(caminho, os.W_OK)


def assinatura_de_fonte(inicio):
    """True se os bytes iniciais de um arquivo batem com uma assinatura de fonte."""
    return any(bytes(inicio).startswith(a) for a in ASSINATURAS_FONTE)


def eh_nome_de_fonte(nome):
    return str(nome).lower().endswith(EXTENSOES_FONTE)


def tipo_de_pacote(nome, inicio):
    """'zip', 'tar' ou 'comprimido' pela assinatura dos primeiros bytes ou pela extensao; None se nao e pacote."""
    inicio = bytes(inicio)
    nome = str(nome).lower()
    if inicio.startswith(ASSINATURA_PSD):
        return None
    if inicio.startswith(ASSINATURA_ZIP) or nome.endswith('.zip'):
        return 'zip'
    if inicio.startswith(ASSINATURAS_COMPRIMIDO) or nome.endswith(EXTENSOES_COMPRIMIDO):
        return 'comprimido'
    if inicio[POSICAO_MAGIA_TAR:POSICAO_MAGIA_TAR + len(MAGIA_TAR)] == MAGIA_TAR or nome.endswith('.tar'):
        return 'tar'
    return None


def _membro_suspeito(nome, inicio):
    """Membro de pacote com nome ou assinatura de fonte, ou que e outro pacote (que nao da para conferir sem
    extrair)."""
    return eh_nome_de_fonte(nome) or assinatura_de_fonte(inicio) or tipo_de_pacote(nome, inicio) is not None


def _zip_tem_fonte(caminho):
    """True se o zip tem membro suspeito. So le a lista de nomes e os primeiros bytes de cada membro; nada e
    extraido para o disco."""
    import zipfile
    try:
        with zipfile.ZipFile(caminho) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                with z.open(info) as m:
                    if _membro_suspeito(info.filename, m.read(BYTES_ASSINATURA)):
                        return True
    except (zipfile.BadZipFile, OSError, RuntimeError, NotImplementedError, ValueError, EOFError):
        # zip ilegivel ou cifrado: sem conferir, conta como suspeito
        return True
    return False


def _tar_tem_fonte(caminho):
    """True se o tar (sem compressao) tem membro suspeito. Le os cabecalhos e os primeiros bytes de cada membro na
    memoria; nada e extraido para o disco."""
    import tarfile
    try:
        with tarfile.open(caminho, mode='r:') as t:
            for info in t:
                if info.isdir():
                    continue
                inicio = b''
                if info.isfile():
                    m = t.extractfile(info)
                    inicio = m.read(BYTES_ASSINATURA) if m is not None else b''
                if _membro_suspeito(info.name, inicio):
                    return True
    except (tarfile.TarError, OSError, ValueError, EOFError):
        # tar ilegivel: sem conferir, conta como suspeito
        return True
    return False


def eh_arquivo_de_fonte(caminho):
    """True se o arquivo parece fonte, pela extensao ou pelos primeiros bytes, ou se e pacote com fonte dentro ou
    pacote que nao da para inspecionar sem extrair. O pacote e reconhecido pela assinatura (zip, tar, gzip e os
    outros comprimidos) e pela extensao. Nunca le mais que os primeiros bytes de cada arquivo."""
    caminho = Path(caminho)
    if eh_nome_de_fonte(caminho.name):
        return True
    try:
        with open(caminho, 'rb') as f:
            inicio = f.read(BYTES_ASSINATURA)
    except OSError:
        return False
    if assinatura_de_fonte(inicio):
        return True
    tipo = tipo_de_pacote(caminho.name, inicio)
    if tipo == 'zip':
        return _zip_tem_fonte(caminho)
    if tipo == 'tar':
        return _tar_tem_fonte(caminho)
    return tipo == 'comprimido'


# ------------------------------------------------------------------ fontes do job (entrada/fontes/, M2)
# Formatos aceitos em entrada/fontes/ (decisoes-v1.md, arquitetura 14), reconhecidos pela assinatura do inicio do
# arquivo, nunca so pela extensao. A colecao OTC tem a mesma assinatura da TTC. Variable font so se ve abrindo
# as tabelas (fvar), o que so o processo filho faz (desdobra.fontes.filho).
FORMATOS_FONTE_POR_ASSINATURA = ((b'OTTO', 'otf'), (b'\x00\x01\x00\x00', 'ttf'), (b'true', 'ttf'), (b'ttcf', 'ttc'),
                                 (b'wOFF', 'woff'), (b'wOF2', 'woff2'))
FORMATOS_FONTE_ACEITOS = ('otf', 'ttf', 'ttc', 'woff', 'woff2')
EXTENSOES_FONTE_ACEITAS = ('.otf', '.ttf', '.ttc', '.otc', '.woff', '.woff2')
# Type 1: em texto (PFA), binario (PFB, que comeca com o marcador de segmento 0x80 0x01) e o "typ1" do Mac
ASSINATURAS_TYPE1 = (b'%!PS-AdobeFont', b'%!FontType1', b'\x80\x01', b'typ1')
EXTENSOES_TYPE1 = ('.pfb', '.pfa', '.pfm', '.afm', '.t42')
# arquivos que o sistema grava sozinho numa pasta copiada (nunca sao fonte); ficam fora da entrada de fontes
ARQUIVOS_DO_SISTEMA = ('.ds_store', 'thumbs.db', 'desktop.ini')
PREFIXO_APPLEDOUBLE = '._'  # metadados que o Mac grava ao lado de cada arquivo copiado para disco sem HFS


def eh_arquivo_do_sistema(nome):
    """True para o que o sistema grava sozinho numa pasta copiada, que nunca e entrada do job."""
    nome = str(nome)
    return nome.lower() in ARQUIVOS_DO_SISTEMA or nome.startswith(PREFIXO_APPLEDOUBLE)


def classificar_fonte(caminho):
    """Classifica um arquivo oferecido como fonte do job, so pelos primeiros bytes e pela extensao (sem parse).

    Devolve (formato, None) quando a assinatura e de um formato aceito, ou (None, motivo) com motivo em
    'pacote', 'type1', 'formato_nao_aceito' (outra fonte, como bitmap ou EOT), 'nao_abre' (extensao de fonte
    sem assinatura conhecida) e 'nao_e_fonte'. A leitura das tabelas (variable font, arquivo malformado) e do
    processo filho."""
    caminho = Path(caminho)
    try:
        with open(caminho, 'rb') as f:
            inicio = f.read(BYTES_ASSINATURA)
    except OSError:
        return None, 'nao_abre'
    if tipo_de_pacote(caminho.name, inicio) is not None:
        return None, 'pacote'
    nome = caminho.name.lower()
    if inicio.startswith(ASSINATURAS_TYPE1) or nome.endswith(EXTENSOES_TYPE1):
        return None, 'type1'
    for assinatura, formato in FORMATOS_FONTE_POR_ASSINATURA:
        if inicio.startswith(assinatura):
            return formato, None
    if assinatura_de_fonte(inicio):
        return None, 'formato_nao_aceito'
    if nome.endswith(EXTENSOES_FONTE_ACEITAS):
        return None, 'nao_abre'
    if eh_nome_de_fonte(nome):
        return None, 'formato_nao_aceito'
    return None, 'nao_e_fonte'


def tem_assinatura_psd(caminho):
    """Confere so os 4 primeiros bytes (8BPS). Nao e parse: o processo principal nunca parseia PSD."""
    with open(caminho, 'rb') as f:
        return f.read(len(ASSINATURA_PSD)) == ASSINATURA_PSD
