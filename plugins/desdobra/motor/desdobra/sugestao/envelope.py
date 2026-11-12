# -*- coding: utf-8 -*-
"""Envelope de saida (envelope/1): a unica coisa que o motor imprime quando chamado por skill.

arquitetura-v1.md, 5.10 e 7.4; docs/m1-interfaces.md, secao 9.

O envelope leva o modo de dados, o comando, a fase, a situacao, o codigo, o "o que fazer", as contagens, os
ids e os numeros do proprio motor, e o numero de segredos bloqueados. O campo conteudo depende do modo:

  modo a: camadas (layer_id, nome, tipo, situacao, textos) e miniaturas (so caminhos em sugestoes/miniaturas/,
          so de camadas sem texto e so os que estao no indice.json que o motor gravou ao copiar; M7c, S2);
  modo b: so camadas;
  modo c: o campo nao existe. Nenhum nome de camada, texto ou caminho de cliente sai.

Antes do filtro do modo, todo nome e texto passa pelo detector de segredos. Camada com achado sai inteira
(nome e textos) e conta em segredos_bloqueados, em qualquer modo. O detalhe vai para
sugestoes/segredos-bloqueados.json do job, que so o DA ve.

Funcoes publicas:
  montar(resultado, modo) -> dict       usada por desdobra.cli; nunca levanta excecao
  imprimir(resultado, modo, fluxo)      a funcao unica de impressao: uma linha JSON, validada
"""
import json
import math
import re
import sys
from pathlib import Path

from desdobra.resultado import MODOS_DADOS, Codigo
from desdobra.sugestao import segredos

CONTRATO = 'envelope/1'
TIPOS_CAMADA = ('texto', 'forma', 'pixel', 'cor_solida', 'preenchimento', 'ajuste', 'grupo', 'prancheta',
                'smart_embutido', 'smart_linkado', 'outro')
SITUACOES_CAMADA = ('lida', 'degradada', 'bloqueante')
SITUACOES = ('ok', 'ok_com_bloqueio', 'portao', 'concluido', 'erro', 'recusado', 'bloqueado', 'nao_disponivel')
_CHAVE = re.compile(r'^[a-z][a-z0-9_]*$')
_HEX = re.compile(r'^[0-9a-f]{8,64}$')
_COMANDO = re.compile(r'^[a-z][a-z -]*$')
_FASE = re.compile(r'^[a-z][a-z0-9-]*$')
_MINIATURA = re.compile(r'^sugestoes/miniaturas/(?P<arquivo>[^/\\]+)\.png$')
O_QUE_FAZER_RETIDO = ('A orientação deste passo foi retida pelo detector de segredos. Rode o mesmo comando sem '
                      '--envelope para ver o aviso no terminal.')


# ------------------------------------------------------------------ campos fixos
def _inteiro(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _contagens(d):
    saida = {}
    for k, v in (d or {}).items():
        if not isinstance(k, str) or not _CHAVE.match(k):
            continue
        if isinstance(v, bool):
            v = int(v)
        if _inteiro(v):
            saida[k] = int(v)
    return saida


def _ids(d):
    saida = {}
    for k, v in (d or {}).items():
        if not isinstance(k, str) or not _CHAVE.match(k):
            continue
        if _inteiro(v):
            saida[k] = int(v)
        elif isinstance(v, str) and _HEX.match(v):
            saida[k] = v
        elif isinstance(v, (list, tuple)) and all(_inteiro(x) for x in v):
            saida[k] = [int(x) for x in v]
    return saida


def _numeros(d):
    saida = {}
    for k, v in (d or {}).items():
        if not isinstance(k, str) or not _CHAVE.match(k):
            continue
        if v is None:
            saida[k] = None
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            saida[k] = float(v) if isinstance(v, float) and math.isfinite(v) else (v if _inteiro(v) else None)
    return saida


def _texto_fixo(v, padrao):
    return v if isinstance(v, str) and padrao.match(v) else None


def campos_fixos(resultado, modo):
    """Os campos que todo envelope tem, ja limpos para valer contra envelope/1."""
    situacao = resultado.situacao if resultado.situacao in SITUACOES else 'erro'
    codigo = resultado.codigo if _inteiro(resultado.codigo) else int(Codigo.ERRO_INTERNO)
    return {'esquema': CONTRATO, 'modo_dados': modo,
            'comando': _texto_fixo(resultado.comando, _COMANDO) or 'desdobra',
            'fase': _texto_fixo(resultado.fase, _FASE),
            'situacao': situacao, 'codigo': int(codigo),
            'o_que_fazer': resultado.o_que_fazer if isinstance(resultado.o_que_fazer, str) else None,
            'contagens': _contagens(resultado.contagens), 'ids': _ids(resultado.ids),
            'numeros': _numeros(resultado.numeros), 'segredos_bloqueados': 0}


# ------------------------------------------------------------------ conteudo
def _textos(v):
    if isinstance(v, str):
        return [v]
    if isinstance(v, (list, tuple)):
        return [t for t in v if isinstance(t, str)]
    return []


def _camada_limpa(item):
    """Copia so os campos que o envelope aceita. None se o item nao tem layer_id inteiro."""
    if not isinstance(item, dict) or not _inteiro(item.get('layer_id')):
        return None
    saida = {'layer_id': int(item['layer_id'])}
    if isinstance(item.get('nome'), str):
        saida['nome'] = item['nome']
    if 'tipo' in item:
        saida['tipo'] = item['tipo'] if item['tipo'] in TIPOS_CAMADA else 'outro'
    if item.get('situacao') in SITUACOES_CAMADA:
        saida['situacao'] = item['situacao']
    textos = _textos(item.get('textos'))
    if textos or 'textos' in item:
        saida['textos'] = textos
    return saida


def _miniaturas(itens):
    """[(layer_id ou None, caminho)] das miniaturas que tem caminho no formato aceito."""
    saida = []
    for item in itens or []:
        if isinstance(item, str):
            caminho, lid = item, None
        elif isinstance(item, dict) and isinstance(item.get('arquivo'), str):
            caminho, lid = item['arquivo'], item.get('layer_id')
        else:
            continue
        m = _MINIATURA.match(caminho)
        if not m:
            continue
        if not _inteiro(lid):
            lid = int(m.group('arquivo')) if m.group('arquivo').isdigit() else None
        saida.append((lid, caminho))
    return saida


def miniaturas_do_indice(pasta_job):
    """Os caminhos das miniaturas que o motor copiou para sugestoes/miniaturas/ do job (M7c, S1), pelo indice.json:
    so arquivo comum dentro da pasta, sem atalho, com o sha256 do indice. Sem job, sem indice ou com indice estranho,
    nenhum (lista vazia)."""
    from desdobra import arquivos
    from desdobra.sugestao import miniaturas as mod_miniaturas
    if pasta_job is None:
        return []
    try:
        pasta = Path(pasta_job) / mod_miniaturas.PASTA
        arq = Path(pasta_job) / mod_miniaturas.ARQUIVO_INDICE
        if pasta.is_symlink() or arq.is_symlink() or not arq.is_file():
            return []
        dados = json.loads(arq.read_text(encoding='utf-8'))
        saida = []
        for item in dados.get('miniaturas') or []:
            lid, sha = item.get('layer_id'), item.get('sha256')
            if not _inteiro(lid) or lid < 1 or not isinstance(sha, str):
                continue
            png = pasta / ('%d.png' % lid)
            if png.is_symlink() or not png.is_file() or arquivos.sha256_arquivo(png) != sha:
                continue
            png.resolve().relative_to(pasta.resolve())
            saida.append('%s/%d.png' % (mod_miniaturas.PASTA.as_posix(), lid))
        return saida
    except (OSError, ValueError, AttributeError, TypeError):
        return []


def filtrar_conteudo(conteudo, modo, detector, indice=None):
    """Passa o conteudo pelo detector e pelo filtro do modo. Devolve (conteudo do envelope ou None, achados).

    O detector roda em qualquer modo, inclusive no c, para que o DA saiba do segredo mesmo quando nada sai.
    indice: os caminhos de miniaturas_do_indice; no modo a, so eles podem sair (M7c, S2). Quando o conteudo nao traz
    a lista de miniaturas, o envelope do modo a usa a do indice.
    """
    conteudo = conteudo if isinstance(conteudo, dict) else {}
    achados = []
    camadas = []
    for item in conteudo.get('camadas') or []:
        camada = _camada_limpa(item)
        if camada is None:
            continue
        achado = detector.achado_em('camada', camada['layer_id'],
                                    {'nome': camada.get('nome'), 'textos': camada.get('textos', [])})
        if achado is not None:
            achados.append(achado)
            continue
        camadas.append(camada)

    miniaturas = []
    if modo == 'a':
        no_indice = set(indice or ())
        sem_texto = {c['layer_id'] for c in camadas if c.get('tipo') != 'texto' and not c.get('textos')}
        pedidas = conteudo['miniaturas'] if 'miniaturas' in conteudo else list(indice or ())
        for lid, caminho in _miniaturas(pedidas):
            if lid not in sem_texto or caminho not in no_indice or caminho in miniaturas:
                continue
            achado = detector.achado_em('miniatura', lid, {'arquivo': caminho})
            if achado is not None:
                achados.append(achado)
                continue
            miniaturas.append(caminho)

    if modo == 'c':
        return None, achados
    saida = {'camadas': camadas}
    if modo == 'a':
        saida['miniaturas'] = miniaturas
    return saida, achados


# ------------------------------------------------------------------ montagem e impressao
def envelope_seguro(resultado):
    """Envelope do modo c sem conteudo, montado so com os campos fixos limpos. Sempre vale contra envelope/1."""
    return campos_fixos(resultado, 'c')


def montar(resultado, modo, *, detector=None, gravar_bloqueios=True):
    """Monta o envelope do Resultado no modo dado. Nunca levanta excecao: se algo falhar, devolve o envelope
    seguro (modo c, sem conteudo)."""
    from desdobra import contratos
    try:
        modo = modo if modo in MODOS_DADOS else 'c'
        detector = detector or segredos.detector_padrao()
        env = campos_fixos(resultado, modo)
        indice = miniaturas_do_indice(resultado.pasta_job) if modo == 'a' else []
        conteudo, achados = filtrar_conteudo(resultado.conteudo, modo, detector, indice)
        if env['o_que_fazer'] is not None:
            achado = detector.achado_em('o_que_fazer', None, {'o_que_fazer': env['o_que_fazer']})
            if achado is not None:
                achados.append(achado)
                env['o_que_fazer'] = O_QUE_FAZER_RETIDO
        env['segredos_bloqueados'] = len(achados) + max(0, int(getattr(resultado, 'segredos_ja_bloqueados', 0) or 0))
        if conteudo is not None:
            env['conteudo'] = conteudo
        contratos.validar(env, CONTRATO)
        if achados and gravar_bloqueios and resultado.pasta_job is not None:
            segredos.gravar_bloqueios(resultado.pasta_job, achados, comando=env['comando'])
        return env
    except Exception:  # noqa: BLE001 - o envelope nunca derruba a CLI nem vaza o motivo
        return envelope_seguro(resultado)


def avisos_de_segredo(resultado, *, detector=None, gravar_bloqueios=True):
    """Para o modo humano da CLI: roda o detector sobre o conteudo e o o_que_fazer do Resultado, grava o
    arquivo do DA (se houver job) e devolve as linhas do aviso, que dizem onde e qual padrao, nunca o trecho."""
    try:
        detector = detector or segredos.detector_padrao()
        _, achados = filtrar_conteudo(resultado.conteudo, 'c', detector)
        if isinstance(resultado.o_que_fazer, str):
            achado = detector.achado_em('o_que_fazer', None, {'o_que_fazer': resultado.o_que_fazer})
            if achado is not None:
                achados.append(achado)
        if achados and gravar_bloqueios and resultado.pasta_job is not None:
            segredos.gravar_bloqueios(resultado.pasta_job, achados, comando=resultado.comando)
        return segredos.linhas_para_o_da(achados)
    except Exception:  # noqa: BLE001 - o aviso nunca derruba o comando
        return []


def para_linha(env):
    return json.dumps(env, ensure_ascii=False, separators=(',', ':')) + '\n'


def imprimir(resultado, modo, fluxo=None, **opcoes):
    """A funcao unica de impressao do envelope: monta, valida e escreve uma linha JSON. Devolve o envelope."""
    env = montar(resultado, modo, **opcoes)
    fluxo = fluxo or sys.stdout
    fluxo.write(para_linha(env))
    fluxo.flush()
    return env
