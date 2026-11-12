# -*- coding: utf-8 -*-
"""Importador das sugestoes de funcao do Claude (contrato sugestoes/1; M7c, S3).

O Claude le sugestoes/pacote-modelo.json (e, no modo a, as miniaturas) e escreve sugestoes/sugestoes.json. O motor
confere o arquivo e grava sugestoes/sugestoes-validadas.json so com o que passou. A tela (S4) mostra as validadas ao
lado de cada funcao, sem gravar: sugestao so vira valor com o clique do DA (decisoes-v1.md, 162).

Recusa do arquivo inteiro (nada e gravado; codigo em importar()['recusa']):
  modo_c         o modo efetivo agora (escolha do DA limitada pelo teto do estado.json, da linha de comando e do
                 processo) e c: nada de conteudo saiu para o Claude, e nada volta;
  sem_sugestoes  sugestoes/sugestoes.json nao existe, nao e arquivo comum ou e atalho;
  grande_demais  o arquivo passa de LIMITE_BYTES;
  json_invalido  nao e JSON, tem NaN ou Infinity, tem chave repetida ou e tao aninhado que o decodificador desiste;
  esquema        nao e objeto, o esquema nao e sugestoes/1, falta campo, o sha256 nao e hexadecimal ou a lista nao e lista;
  campo_extra    campo fora de esquema, pacote_sha256 e sugestoes (inclusive modo_dados, job_id e arquivo_sha256, que so
                 o motor escreve);
  numero         campo extra com numero (geometria, escala, confianca);
  sem_pacote     sugestoes/pacote-modelo.json ou o laudo nao existe;
  pacote_velho   o sha256 citado nao e o do pacote de agora, ou o pacote e de outro modo, de outro KV ou do contrato antigo.

Recusa de uma sugestao (as outras seguem; contadas por codigo em importar()['recusadas']):
  item_invalido     o item nao e objeto;
  numero            campo extra com numero (caixa, escala, ancora) ou layer_id que nao e inteiro de verdade (13.0);
  campo_extra       campo extra sem numero (texto livre);
  alvo_invalido     layer_id ausente ou que nao e numero (texto, booleano);
  item_incompleto   falta a funcao ou a alternativa;
  funcao_fora       funcao ou alternativa fora do $defs.funcao do briefing/1;
  alternativa_igual a alternativa repete a funcao;
  alvo_repetido     mais de uma sugestao para o mesmo alvo: todas as do alvo saem;
  alvo_inexistente  o layer_id nao e de uma camada nem de um grupo do laudo.

O resultado e o registro em log/eventos.jsonl (evento EVENTO) levam so o modo, contagens e codigos; nunca nome, texto
ou caminho. O arquivo validado leva so ids, o enum de funcoes e os sha256.
"""
import hashlib
import json
import re
from pathlib import Path

from desdobra import contratos

CONTRATO = 'sugestoes/1'
ARQUIVO_SUGESTOES = Path('sugestoes') / 'sugestoes.json'
ARQUIVO_VALIDADAS = Path('sugestoes') / 'sugestoes-validadas.json'
EVENTO = 'sugestoes_importadas'
LIMITE_BYTES = 1 << 20  # numero-neutro: so limita a leitura; uma sugestao por camada cabe com folga
CAMPOS_DO_ARQUIVO = ('esquema', 'pacote_sha256', 'sugestoes')
CAMPOS_DO_ITEM = ('layer_id', 'funcao', 'alternativa')
RECUSAS_DO_ARQUIVO = ('modo_c', 'sem_sugestoes', 'grande_demais', 'json_invalido', 'esquema', 'campo_extra', 'numero',
                      'sem_pacote', 'pacote_velho')
RECUSAS_DO_ITEM = ('item_invalido', 'numero', 'campo_extra', 'alvo_invalido', 'item_incompleto', 'funcao_fora',
                   'alternativa_igual', 'alvo_repetido', 'alvo_inexistente')


class _JsonRuim(ValueError):
    pass


def funcoes_da_taxonomia():
    """As funcoes do $defs.funcao do briefing/1, na ordem do esquema."""
    return tuple(contratos.carregar_esquema('briefing/1')['$defs']['funcao']['enum'])


def _sem_repetida(pares):
    vistos = {}
    for k, v in pares:
        if k in vistos:
            raise _JsonRuim('chave repetida')
        vistos[k] = v
    return vistos


def _constante_ruim(_nome):
    raise _JsonRuim('NaN ou Infinity')


def _ler_json(bruto):
    # revisao do S3: JSON pequeno e muito aninhado estoura a recursao do decodificador; e recusa, nunca erro interno
    try:
        return json.loads(bruto.decode('utf-8'), object_pairs_hook=_sem_repetida, parse_constant=_constante_ruim)
    except (_JsonRuim, ValueError, UnicodeDecodeError, RecursionError):
        raise _JsonRuim('json') from None


def _e_inteiro(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _tem_numero(valor):
    """True se ha numero (fora bool) em qualquer nivel do valor; sem recursao (revisao do S3: valor muito aninhado)."""
    pilha = [valor]
    while pilha:
        v = pilha.pop()
        if isinstance(v, dict):
            pilha.extend(v.values())
        elif isinstance(v, list):
            pilha.extend(v)
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            return True
    return False


_SHA256 = re.compile(r'^[0-9a-f]{64}$')


def _hex64(v):
    return isinstance(v, str) and bool(_SHA256.match(v))


def _recusa(modo, codigo):
    return {'situacao': 'recusado', 'recusa': codigo, 'modo': modo, 'aceitas': 0, 'recusadas': {}, 'gravou': False}


def _ids_do_laudo(laudo):
    ids = set()
    for c in laudo.get('camadas') or []:
        lid = (c.get('identidade') or {}).get('layer_id', c.get('layer_id'))
        if _e_inteiro(lid):
            ids.add(lid)
    return ids


def _codigo_do_item(item, funcoes):
    """O codigo de recusa da sugestao, ou None quando a forma dela vale (o alvo e conferido depois)."""
    if not isinstance(item, dict):
        return 'item_invalido'
    extras = [k for k in item if k not in CAMPOS_DO_ITEM]
    if extras:
        return 'numero' if any(_tem_numero(item[k]) for k in extras) else 'campo_extra'
    lid = item.get('layer_id')
    if isinstance(lid, float):
        return 'numero'
    if not _e_inteiro(lid) or lid < 0:
        return 'alvo_invalido'
    if 'funcao' not in item or 'alternativa' not in item:
        return 'item_incompleto'
    if item['funcao'] not in funcoes or item['alternativa'] not in funcoes:
        return 'funcao_fora'
    if item['funcao'] == item['alternativa']:
        return 'alternativa_igual'
    return None


def conferir_itens(itens, ids_do_laudo, funcoes=None):
    """Devolve (aceitas, recusadas por codigo). Uma sugestao e uma alternativa por alvo; o alvo e um layer_id do
    laudo (camada ou grupo)."""
    funcoes = funcoes or funcoes_da_taxonomia()
    codigos = [_codigo_do_item(i, funcoes) for i in itens]
    por_alvo = {}
    for item in itens:
        if isinstance(item, dict) and _e_inteiro(item.get('layer_id')):
            por_alvo[item['layer_id']] = por_alvo.get(item['layer_id'], 0) + 1
    aceitas, recusadas = [], {}
    for item, codigo in zip(itens, codigos):
        if codigo is None and por_alvo.get(item['layer_id'], 0) > 1:
            codigo = 'alvo_repetido'
        if codigo is None and item['layer_id'] not in ids_do_laudo:
            codigo = 'alvo_inexistente'
        if codigo is None:
            aceitas.append({k: item[k] for k in CAMPOS_DO_ITEM})
        else:
            recusadas[codigo] = recusadas.get(codigo, 0) + 1
    return sorted(aceitas, key=lambda i: i['layer_id']), recusadas


def _conferir_arquivo(dados):
    """O codigo de recusa do arquivo inteiro pela forma, ou None."""
    if not isinstance(dados, dict):
        return 'esquema'
    extras = [k for k in dados if k not in CAMPOS_DO_ARQUIVO]
    if extras:
        return 'numero' if any(_tem_numero(dados[k]) for k in extras) else 'campo_extra'
    if dados.get('esquema') != CONTRATO or not _hex64(dados.get('pacote_sha256')) or \
            not isinstance(dados.get('sugestoes'), list):
        return 'esquema'
    return None


def _ler_sugestoes(pasta_job):
    """(dados, None) ou (None, codigo de recusa)."""
    arq = pasta_job / ARQUIVO_SUGESTOES
    try:
        if arq.is_symlink() or not arq.is_file():
            return None, 'sem_sugestoes'
        if arq.stat().st_size > LIMITE_BYTES:
            return None, 'grande_demais'
        bruto = arq.read_bytes()
    except OSError:
        return None, 'sem_sugestoes'
    if len(bruto) > LIMITE_BYTES:
        return None, 'grande_demais'
    try:
        return _ler_json(bruto), None
    except _JsonRuim:
        return None, 'json_invalido'


def _conferir_pacote(pasta_job, estado, modo, citado):
    """(laudo, None) quando o pacote citado e o de agora, do modo e do KV de agora; senao (None, codigo)."""
    from desdobra.sugestao import pacote
    arq = pasta_job / pacote.ARQUIVO_PACOTE
    arq_laudo = pasta_job / 'laudo' / 'laudo.json'
    if arq.is_symlink() or not arq.is_file() or not arq_laudo.is_file():
        return None, 'sem_pacote'
    bruto = arq.read_bytes()
    if hashlib.sha256(bruto).hexdigest() != citado:
        return None, 'pacote_velho'
    try:
        p = json.loads(bruto.decode('utf-8'))
        contratos.validar(p, pacote.CONTRATO)
        laudo = contratos.ler(arq_laudo, 'laudo/1')
    except (ValueError, UnicodeDecodeError, contratos.ErroContrato):
        return None, 'pacote_velho'
    sha_laudo = (laudo.get('origem') or {}).get('sha256')
    kv = pacote._kv_do_estado(estado)  # noqa: SLF001 - a mesma regra do KV que o pacote usa
    if p.get('modo_dados') != modo or p.get('arquivo_sha256') != sha_laudo or (kv is not None and kv != sha_laudo):
        return None, 'pacote_velho'
    return laudo, None


def _registrar(pasta_job, r):
    from desdobra.job import nucleo
    try:
        nucleo.registrar_evento(pasta_job, EVENTO, modo=r['modo'], aceitas=r['aceitas'],
                                recusadas=dict(r['recusadas']), recusa=r['recusa'])
    except OSError:
        pass  # o registro nunca derruba a importacao


def importar(pasta_job, teto=None):
    """Confere sugestoes/sugestoes.json e grava sugestoes/sugestoes-validadas.json com as sugestoes aceitas.

    Devolve {'situacao': 'ok' | 'recusado', 'recusa': codigo do arquivo ou None, 'modo', 'aceitas': n,
    'recusadas': {codigo: n}, 'gravou': bool}. So grava quando ha ao menos uma aceita; a recusa deixa o arquivo
    validado anterior como estava."""
    from desdobra.sugestao import pacote
    pasta_job = Path(pasta_job)
    estado = contratos.ler(pasta_job / 'estado.json', 'estado/1')
    modo = pacote.modo_do_job(pasta_job, estado, teto)
    if modo not in ('a', 'b'):
        r = _recusa('c', 'modo_c')
        _registrar(pasta_job, r)
        return r
    dados, codigo = _ler_sugestoes(pasta_job)
    if codigo is None:
        codigo = _conferir_arquivo(dados)
    laudo = None
    if codigo is None:
        laudo, codigo = _conferir_pacote(pasta_job, estado, modo, dados['pacote_sha256'])
    if codigo is not None:
        r = _recusa(modo, codigo)
        _registrar(pasta_job, r)
        return r
    aceitas, recusadas = conferir_itens(dados['sugestoes'], _ids_do_laudo(laudo))
    r = {'situacao': 'ok' if aceitas else 'recusado', 'recusa': None, 'modo': modo, 'aceitas': len(aceitas),
         'recusadas': recusadas, 'gravou': False}
    if aceitas:
        validadas = {'esquema': CONTRATO, 'pacote_sha256': dados['pacote_sha256'], 'modo_dados': modo,
                     'job_id': estado.get('job_id'), 'arquivo_sha256': (laudo.get('origem') or {}).get('sha256'),
                     'sugestoes': aceitas}
        contratos.gravar(pasta_job / ARQUIVO_VALIDADAS, validadas, CONTRATO)
        r['gravou'] = True
    _registrar(pasta_job, r)
    return r
