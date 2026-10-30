# -*- coding: utf-8 -*-
"""Detector de segredos em nomes de camada e textos do job.

Os padroes ficam numa lista declarada no registro de limites (limite segredos.padroes em
motor/fontes-de-limites.json): cada item tem "nome" (o que o DA le) e "regex" (expressao regular do Python).
Um item pode ter o grupo nomeado "valor": a entropia e medida so nele (padrao com rotulo, como
"senha: <valor>"). Este modulo nao guarda padrao nenhum no codigo.

Regras:
  - achado vira bloqueio: quem chama tira a camada (nome e textos) de toda saida para o Claude;
  - o Achado guarda o nome do padrao, o campo e o layer_id, nunca o trecho achado;
  - o detalhe vai so para sugestoes/segredos-bloqueados.json do job, que so o DA ve; nunca para o envelope,
    o log ou o pacote do modelo;
  - antes de procurar, o texto e normalizado (NFKC, sem caracteres de largura zero), para que um segredo
    com caractere invisivel no meio tambem seja achado. O texto original tambem e varrido.
"""
import functools
import math
import re
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from desdobra import limites

ID_PADROES = 'segredos.padroes'
ARQUIVO_BLOQUEIOS = Path('sugestoes') / 'segredos-bloqueados.json'
CONTRATO_BLOQUEIOS = 'segredos-bloqueados/1'
# caracteres que nao aparecem na tela e podem partir um segredo ao meio
_INVISIVEIS = dict.fromkeys(map(ord, '­᠎​‌‍⁠⁡⁢⁣⁤﻿'))


class ErroPadrao(Exception):
    pass


@dataclass(frozen=True)
class Padrao:
    nome: str
    regex: re.Pattern


@dataclass
class Achado:
    """Um bloqueio. Nunca guarda o trecho achado."""
    origem: str                      # 'camada', 'fonte', 'quadro', 'o_que_fazer', 'miniatura'
    layer_id: int | None = None
    campos: set = field(default_factory=set)       # 'nome', 'textos', 'fonte_ps', 'arquivo', 'o_que_fazer'
    padroes: set = field(default_factory=set)      # nomes dos padroes do registro
    entropia_bits: float | None = None             # maior entropia medida (registra, para calibrar)

    def juntar(self, outro):
        self.campos |= outro.campos
        self.padroes |= outro.padroes
        if outro.entropia_bits is not None:
            self.entropia_bits = max(self.entropia_bits or 0.0, outro.entropia_bits)

    def para_json(self):
        return {'origem': self.origem, 'layer_id': self.layer_id, 'campos': sorted(self.campos),
                'padroes': sorted(self.padroes),
                'entropia_bits': None if self.entropia_bits is None else round(self.entropia_bits, 3)}  # numero-neutro: arredondamento so de exibicao


def entropia_bits(texto):
    """Entropia de Shannon por caractere, em bits. So medida: nao decide nada neste marco."""
    if not texto:
        return 0.0
    total = len(texto)
    return -sum((n / total) * math.log2(n / total) for n in Counter(texto).values())


def normalizar(texto):
    return unicodedata.normalize('NFKC', texto).translate(_INVISIVEIS)


def compilar(itens):
    """Lista do registro -> lista de Padrao. Erro claro se um item estiver mal formado."""
    padroes = []
    for i, item in enumerate(itens or []):
        if not isinstance(item, dict) or not isinstance(item.get('nome'), str) or not isinstance(item.get('regex'), str):
            raise ErroPadrao('%s: o item %d precisa de "nome" e "regex" em texto' % (ID_PADROES, i))
        try:
            padroes.append(Padrao(nome=item['nome'], regex=re.compile(item['regex'])))
        except re.error as e:
            raise ErroPadrao('%s: o padrao %r nao compila (%s)' % (ID_PADROES, item['nome'], e)) from None
    return tuple(padroes)


@functools.cache
def padroes_do_registro():
    return compilar(limites.valor('segredos.padroes'))


class Detector:
    """Procura os padroes do registro (ou os dados) num texto."""

    def __init__(self, padroes=None):
        self.padroes = padroes_do_registro() if padroes is None else (
            compilar(padroes) if padroes and isinstance(padroes[0], dict) else tuple(padroes))

    def procurar(self, texto):
        """Devolve [(nome do padrao, entropia em bits do trecho)] para o texto. Nunca devolve o trecho."""
        if not isinstance(texto, str) or not texto:
            return []
        candidatos = [texto]
        normal = normalizar(texto)
        if normal != texto:
            candidatos.append(normal)
        achados = {}
        for padrao in self.padroes:
            for alvo in candidatos:
                m = padrao.regex.search(alvo)
                if m is None:
                    continue
                trecho = m.group('valor') if 'valor' in padrao.regex.groupindex and m.group('valor') else m.group(0)
                achados[padrao.nome] = max(achados.get(padrao.nome, 0.0), entropia_bits(trecho))
                break
        return sorted(achados.items())

    def tem_segredo(self, texto):
        return bool(self.procurar(texto))

    def achado_em(self, origem, layer_id, campos_e_textos):
        """Varre {campo: texto ou lista de textos}. Devolve um Achado ou None."""
        achado = None
        for campo, valor in campos_e_textos.items():
            textos = valor if isinstance(valor, (list, tuple)) else [valor]
            for texto in textos:
                for nome, entropia in self.procurar(texto):
                    if achado is None:
                        achado = Achado(origem=origem, layer_id=layer_id)
                    achado.juntar(Achado(origem=origem, layer_id=layer_id, campos={campo}, padroes={nome},
                                         entropia_bits=entropia))
        return achado


def detector_padrao():
    return Detector()


# ------------------------------------------------------------------ arquivo do DA
def _chave(achado):
    return (achado.origem, achado.layer_id)


def gravar_bloqueios(pasta_job, achados, comando=None):
    """Junta os achados em sugestoes/segredos-bloqueados.json do job (so o DA ve este arquivo).

    Junta com o que ja estava gravado, por (origem, layer_id). Nao grava nada se nao houver achado.
    Devolve o caminho gravado ou None.
    """
    from desdobra import contratos
    if not achados or pasta_job is None:
        return None
    caminho = Path(pasta_job) / ARQUIVO_BLOQUEIOS
    atuais = {}
    if caminho.is_file():
        try:
            dados = contratos.ler(caminho, CONTRATO_BLOQUEIOS)
            for item in dados['bloqueios']:
                a = Achado(origem=item['origem'], layer_id=item.get('layer_id'), campos=set(item['campos']),
                           padroes=set(item['padroes']), entropia_bits=item.get('entropia_bits'))
                atuais[_chave(a)] = a
        except contratos.ErroContrato:
            atuais = {}
    for a in achados:
        if _chave(a) in atuais:
            atuais[_chave(a)].juntar(a)
        else:
            atuais[_chave(a)] = Achado(origem=a.origem, layer_id=a.layer_id, campos=set(a.campos),
                                       padroes=set(a.padroes), entropia_bits=a.entropia_bits)
    ordem = sorted(atuais.values(), key=lambda a: (a.origem, -1 if a.layer_id is None else a.layer_id))
    dados = {'esquema': CONTRATO_BLOQUEIOS, 'atualizado_em': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
             'ultimo_comando': comando, 'total': len(ordem), 'bloqueios': [a.para_json() for a in ordem]}
    contratos.gravar(caminho, dados, CONTRATO_BLOQUEIOS)
    return caminho


_CAMPOS_HUMANOS = {'nome': 'no nome', 'textos': 'no texto', 'fonte_ps': 'no nome da fonte',
                   'arquivo': 'no nome do arquivo', 'o_que_fazer': 'na orientação do motor'}


def linhas_para_o_da(achados):
    """Linhas para o terminal ou a tela do DA. Dizem onde e qual padrao, nunca o trecho."""
    linhas = []
    for a in achados:
        onde = ', '.join(_CAMPOS_HUMANOS.get(c, c) for c in sorted(a.campos))
        quem = 'A camada %d' % a.layer_id if a.layer_id is not None else 'Um item do job'
        linhas.append('%s tem um trecho parecido com %s (%s). Esse conteúdo não vai para o Claude. Confira o '
                      'PSD e apague o segredo, se for o caso.' % (quem, ', '.join(sorted(a.padroes)), onde))
    return linhas
