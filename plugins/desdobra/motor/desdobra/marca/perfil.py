# -*- coding: utf-8 -*-
"""Perfil de marca (M7c, passo M2; arquitetura-v1.md, 4.14 e 5.7; decisoes-v1.md, 190, Q1 e Q3).

Arquivo: <biblioteca da agencia>/marcas/<id>/perfil-marca.json, contrato perfil-marca/1.

  - id: 32 hexadecimais ao acaso (secrets), gerado pelo motor na criacao, sem relacao com o nome da marca;
  - marca: o nome dado pelo DA;
  - versao e atual: a versao que vale (0 e atual None no perfil criado sem registro);
  - historico: as versoes anteriores, inteiras, na ordem, nunca apagadas.

Cada versao leva a campanha registrada (job, data, sha256 da aprovacao de cada formato, quem confirmou, origem da e
meio tela), as regras de escala e as ancoras por funcao confirmadas pelo DA, cada uma com o job de origem (o job da
campanha desta versao ou o de uma campanha registrada antes, para o registro poder manter a origem de uma regra que
nao mudou), uma por funcao, e as faces
usadas so pelo nome PostScript. Cores recorrentes sao campo opcional, sem produtor no M7c. A versao da galeria, as
edicoes de palco, o lockup de governo e os limites ficam no job: nova_versao nem recebe esses campos, e o esquema os
recusa.

nova_versao grava uma versao nova a cada registro: a atual vai inteira para o fim do historico. Registrar de novo o
mesmo job sem mudanca no conteudo nem nas aprovacoes nao cria versao. O perfil lido do disco e conferido (versoes
seguidas de 1 a versao), e o perfil com historico adulterado e recusado, para nenhuma gravacao apagar versao.

Gravacao atomica (desdobra.arquivos). A conferencia de fonte olha so o que o desdobra grava, dentro de
<biblioteca>/marcas/<id>/: o motor recusa gravar ali arquivo com nome ou assinatura de fonte (ASSINATURAS_FONTE) e
recusa a pasta da marca que aponta para fora de <biblioteca>/marcas, e a propria <biblioteca>/marcas que e ligacao ou
resolve fora da biblioteca (revisao do M2). Nenhum texto do perfil leva arquivo de fonte nem bytes de fonte codificados
em base64 ou hex (validar). Nada varre o resto da biblioteca. A gravacao
confere que o arquivo nao mudou desde a leitura; nao ha trava entre dois DAs que gravam ao mesmo tempo (risco
declarado no plano do M7c).

Este modulo nao confere a biblioteca (desdobra.biblioteca.conferir): quem chama passa a pasta que ja serve.
"""
import base64
import binascii
import copy
import json
import os
import re
import secrets
from datetime import datetime
from pathlib import Path

from desdobra import contratos
from desdobra.arquivos import (BYTES_ASSINATURA, EXTENSOES_FONTE, assinatura_de_fonte, eh_nome_de_fonte,
                               gravar_bytes_atomico, para_json)
from desdobra.biblioteca import pasta_marcas
from desdobra.contratos import ErroContrato

ESQUEMA = 'perfil-marca/1'
ARQUIVO = 'perfil-marca.json'
BYTES_DO_ID = 16  # numero-neutro: 128 bits ao acaso, o id nao diz nada da marca
TENTATIVAS_DO_ID = 3  # numero-neutro: id repetido com 128 bits ao acaso nao acontece; o laco so evita sobrescrever
_ID = re.compile(r'^[0-9a-f]{32}$')
_NOME_DE_ARQUIVO = re.compile(r'^[\w.-]+$')
# o que compara duas versoes para dizer se o registro mudou algo (quando e quem confirmou nao contam)
_CAMPOS_DO_CONTEUDO = ('job_origem', 'regras_escala', 'ancoras', 'faces', 'cores')
# revisao do M2: os textos livres do perfil nao levam arquivo nem bytes de fonte (_conferir_textos)
_CHAVES_DE_PADRAO_FIXO = ('esquema', 'id', 'job', 'job_origem', 'aprovacao_sha256', 'srgb')
_EXTENSAO_DE_FONTE = re.compile(r'\.(?:%s)(?![A-Za-z0-9_-])' % '|'.join(re.escape(e[1:]) for e in EXTENSOES_FONTE),
                                re.IGNORECASE)
_HEX = re.compile(r'^(?:[0-9A-Fa-f]{2}){4,}$')
_BASE64 = re.compile(r'^[A-Za-z0-9+/_-]{6,}={0,2}$')


class ErroPerfil(Exception):
    """O perfil nao pode ser lido ou gravado como pedido. A mensagem nao leva o caminho da biblioteca."""


def agora():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def novo_id():
    return secrets.token_hex(BYTES_DO_ID)


def _conferir_id(id_):
    if not isinstance(id_, str) or not _ID.match(id_):
        raise ErroPerfil('O id da marca não está no formato do desdobra.')
    return id_


def pasta_da_marca(biblioteca, id_):
    return pasta_marcas(biblioteca) / _conferir_id(id_)


def caminho(biblioteca, id_):
    return pasta_da_marca(biblioteca, id_) / ARQUIVO


def _mesmo_lugar(a, b):
    return os.path.normcase(str(a)) == os.path.normcase(str(b))


def _conferir_marcas(biblioteca):
    """Revisao do M2: <biblioteca>/marcas, quando existe, e uma pasta de verdade dentro da biblioteca, nunca uma
    ligacao (simbolica ou juncao) que leva para fora dela."""
    marcas = pasta_marcas(biblioteca)
    if not (marcas.exists() or marcas.is_symlink()):
        return marcas
    juncao = getattr(marcas, 'is_junction', lambda: False)()
    dentro = Path(biblioteca).resolve() / marcas.name
    if marcas.is_symlink() or juncao or not marcas.is_dir() or not _mesmo_lugar(marcas.resolve(), dentro):
        raise ErroPerfil('A pasta de marcas aponta para fora da biblioteca da agência.')
    return marcas


def gravar_na_marca(biblioteca, id_, nome, dados):
    """Grava bytes em <biblioteca>/marcas/<id>/<nome>, de forma atomica. Recusa nome ou assinatura de fonte e a pasta
    da marca que, resolvida, sai de <biblioteca>/marcas."""
    if not isinstance(nome, str) or not _NOME_DE_ARQUIVO.match(nome) or nome in ('.', '..'):
        raise ErroPerfil('O desdobra grava na pasta da marca só arquivos com nome simples.')
    if eh_nome_de_fonte(nome) or assinatura_de_fonte(bytes(dados[:BYTES_ASSINATURA])):
        raise ErroPerfil('O desdobra não grava arquivo de fonte na pasta da marca.')
    marcas = pasta_marcas(biblioteca)
    pasta = pasta_da_marca(biblioteca, id_)
    if not (marcas.exists() or marcas.is_symlink()):
        marcas.mkdir(parents=True)
    _conferir_marcas(biblioteca)
    if not (pasta.exists() or pasta.is_symlink()):
        pasta.mkdir()
    alvo = pasta / nome
    if not pasta.is_dir() or pasta.resolve().parent != marcas.resolve() or alvo.is_symlink():
        raise ErroPerfil('A pasta da marca aponta para fora da biblioteca da agência.')
    gravar_bytes_atomico(alvo, bytes(dados))


def _conferir_consistencia(dados):
    """Versoes seguidas de 1 ate versao, historico na ordem, funcao sem repeticao e job de origem igual ao da
    campanha."""
    historico = dados['historico']
    atual = dados['atual']
    if atual is None:
        if dados['versao'] != 0 or historico:
            raise ErroPerfil('O perfil da marca está adulterado: sem versão atual, mas com histórico.')
        return dados
    versoes = [v['versao'] for v in historico] + [atual['versao']]
    if versoes != list(range(1, len(versoes) + 1)) or dados['versao'] != atual['versao']:
        raise ErroPerfil('O perfil da marca está adulterado: as versões do histórico não seguem de 1 até a atual.')
    registrados = set()
    for v in historico + [atual]:
        registrados.add(v['campanha']['job'])
        _conferir_versao(v, registrados)
    return dados


def _conferir_versao(v, registrados):
    """O job de origem da versao e o da campanha; o de cada regra, ancora e cor e um job com campanha registrada ate
    esta versao (o desta ou o de uma anterior)."""
    if v['job_origem'] != v['campanha']['job']:
        raise ErroPerfil('A versão do perfil cita um job de origem diferente do job da campanha.')
    for campo in ('regras_escala', 'ancoras', 'cores'):
        if any(item['job_origem'] not in registrados for item in v.get(campo) or ()):
            raise ErroPerfil('A versão do perfil cita em %s um job de origem sem campanha registrada.' % campo)
    for campo in ('regras_escala', 'ancoras'):
        funcoes = [item['funcao'] for item in v[campo]]
        if len(funcoes) != len(set(funcoes)):
            raise ErroPerfil('A versão do perfil repete uma função em %s.' % campo)


def _decodificados(texto):
    """Os bytes que o texto daria lido como base64 (padrao ou de URL, com ou sem preenchimento) ou como hex."""
    saida = []
    if _HEX.match(texto):
        saida.append(bytes.fromhex(texto))
    if _BASE64.match(texto):
        corpo = texto.rstrip('=')
        corpo += '=' * (-len(corpo) % 4)
        for alfabeto in (None, b'-_'):
            try:
                saida.append(base64.b64decode(corpo, altchars=alfabeto))
            except (binascii.Error, ValueError):
                continue
    return saida


def _conferir_textos(valor, chave=None):
    """Revisao do M2: nenhum texto do perfil leva arquivo de fonte (extensao em qualquer ponto) nem bytes de fonte
    codificados (base64 ou hex que comeca com a assinatura de um arquivo de fonte). Os hashes e os ids, de padrao fixo
    no esquema, ficam de fora."""
    if isinstance(valor, dict):
        for k, v in valor.items():
            _conferir_textos(v, k)
    elif isinstance(valor, list):
        for v in valor:
            _conferir_textos(v, chave)
    elif isinstance(valor, str) and chave not in _CHAVES_DE_PADRAO_FIXO:
        if _EXTENSAO_DE_FONTE.search(valor):
            raise ErroPerfil('O perfil da marca não guarda arquivo de fonte (campo %s).' % chave)
        if any(assinatura_de_fonte(b[:BYTES_ASSINATURA]) for b in _decodificados(valor.strip())):
            raise ErroPerfil('O perfil da marca não guarda bytes de fonte (campo %s).' % chave)


def validar(dados):
    contratos.validar(dados, ESQUEMA)
    _conferir_textos(dados)
    return _conferir_consistencia(dados)


def _ler_bytes(biblioteca, id_):
    _conferir_marcas(biblioteca)
    arquivo = caminho(biblioteca, id_)
    try:
        return arquivo.read_bytes()
    except FileNotFoundError:
        raise ErroPerfil('A marca não tem perfil na biblioteca da agência.') from None
    except OSError:
        raise ErroPerfil('O desdobra não conseguiu ler o perfil da marca.') from None


def _de_bytes(bruto, id_):
    try:
        dados = json.loads(bruto.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        raise ErroPerfil('O perfil da marca não é um JSON legível.') from None
    try:
        validar(dados)
    except ErroContrato as e:
        raise ErroPerfil('O perfil da marca não segue o contrato %s: %s' % (ESQUEMA, e)) from None
    if dados['id'] != id_:
        raise ErroPerfil('O perfil da marca está numa pasta com outro id.')
    return dados


def ler(biblioteca, id_):
    _conferir_id(id_)
    return _de_bytes(_ler_bytes(biblioteca, id_), id_)


def atual(dados):
    """A versao que vale (a mais recente), ou None no perfil sem registro."""
    return dados['atual']


def listar(biblioteca):
    """[{'id', 'marca'}] dos perfis legiveis em <biblioteca>/marcas, pelo nome. O que nao e perfil do desdobra fica
    de fora, sem erro."""
    marcas = _conferir_marcas(biblioteca)
    if not marcas.is_dir():
        return []
    achados = []
    for pasta in marcas.iterdir():
        if not _ID.match(pasta.name) or not pasta.is_dir():
            continue
        try:
            dados = ler(biblioteca, pasta.name)
        except ErroPerfil:
            continue
        achados.append({'id': dados['id'], 'marca': dados['marca']})
    return sorted(achados, key=lambda m: (m['marca'].casefold(), m['id']))


def _gravar(biblioteca, dados):
    validar(dados)
    gravar_na_marca(biblioteca, dados['id'], ARQUIVO, para_json(dados).encode('utf-8'))


def criar(biblioteca, nome, *, quando=None):
    """Cria o perfil de uma marca nova, sem registro (versao 0), com id ao acaso."""
    for _tentativa in range(TENTATIVAS_DO_ID):
        id_ = novo_id()
        if not pasta_da_marca(biblioteca, id_).exists():
            break
    else:
        raise ErroPerfil('O desdobra não conseguiu gerar um id novo para a marca.')
    dados = {'esquema': ESQUEMA, 'id': id_, 'marca': nome, 'criado_em': quando or agora(), 'versao': 0, 'atual': None,
             'historico': []}
    try:
        _gravar(biblioteca, dados)
    except ErroContrato as e:
        raise ErroPerfil('O nome da marca não pode ser gravado: %s' % e) from None
    return dados


def _conteudo(versao):
    return {k: versao.get(k) for k in _CAMPOS_DO_CONTEUDO} | {
        'aprovacoes': sorted((f['formato'], f['aprovacao_sha256']) for f in versao['campanha']['formatos'])}


def nova_versao(biblioteca, id_, *, campanha, regras_escala, ancoras, faces, cores=None, quando=None):
    """Grava a versao nova do perfil com o registro de uma campanha aprovada. Devolve (perfil, criou). A versao atual
    vai inteira para o fim do historico; o mesmo job sem mudanca devolve o perfil como estava e criou False."""
    bruto = _ler_bytes(biblioteca, id_)
    dados = _de_bytes(bruto, _conferir_id(id_))
    anterior = dados['atual']
    versao = {'versao': dados['versao'] + 1, 'job_origem': campanha.get('job') if isinstance(campanha, dict) else None,
              'quando': quando or agora(), 'campanha': copy.deepcopy(campanha),
              'regras_escala': copy.deepcopy(list(regras_escala)), 'ancoras': copy.deepcopy(list(ancoras)),
              'faces': copy.deepcopy(list(faces))}
    if cores is not None:
        versao['cores'] = copy.deepcopy(list(cores))
    if anterior is not None and _conteudo(anterior) == _conteudo(versao):
        return dados, False
    novo = copy.deepcopy(dados)
    if anterior is not None:
        novo['historico'].append(copy.deepcopy(anterior))
    novo['atual'] = versao
    novo['versao'] = versao['versao']
    try:
        contratos.validar(novo, ESQUEMA)
    except ErroContrato as e:
        raise ErroPerfil('A versão nova do perfil não segue o contrato %s: %s' % (ESQUEMA, e)) from None
    _conferir_consistencia(novo)
    # nenhuma versao anterior muda nem some
    if [para_json(v) for v in novo['historico'][:len(dados['historico'])]] != \
            [para_json(v) for v in dados['historico']]:
        raise ErroPerfil('A gravação mudaria o histórico do perfil da marca.')
    if _ler_bytes(biblioteca, id_) != bruto:
        raise ErroPerfil('O perfil da marca mudou durante o registro. Registre de novo.')
    _gravar(biblioteca, novo)
    return novo, True
