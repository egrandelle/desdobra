# -*- coding: utf-8 -*-
"""Registro de limites: todo numero usado como regra vem de motor/fontes-de-limites.json.

Cada limite tem id, valor, unidade, fonte, situacao e efeito:
  - situacao: medido (pesquisa), decidido (decisoes-v1.md), folha (folha de spec de veiculo) ou a_calibrar;
  - efeito: reprova, avisa ou registra;
  - sem fonte, a situacao e a_calibrar, e um limite a_calibrar nunca reprova (o carregador recusa o registro).

Uso no codigo:
    from desdobra import limites
    if fracao > limites.valor('prova_pixel.limiar_diferenca'): ...
    lim = limites.obter('coberta_no_kv.ocupa_canvas_fracao')   # Limite com fonte, para citar no laudo
    efeito = limites.efeito('prova_pixel.fracao_reprova')        # nunca 'reprova' se a_calibrar

Convencao verificada por teste (testes/test_limites.py, regra de numeros sem fonte):
  fora deste arquivo, no pacote desdobra, e proibido
    1. constante numerica como operando direto de comparacao (<, <=, >, >=, ==, !=, in, not in), inclusive
       dentro de tupla, lista ou conjunto comparado;
    2. atribuicao a nome em MAIUSCULAS no nivel do modulo ou de classe cujo valor contenha constante numerica;
  exceto os numeros neutros 0, 1 e -1 (e 0.0, 1.0, -1.0), os membros de classes Enum/IntEnum (codigos de
  protocolo) e a linha marcada com o comentario "# numero-neutro: <motivo>" (fato de formato de arquivo,
  tamanho de buffer, coisa que nao e regra), com o motivo escrito.
"""
import functools
import json
from dataclasses import dataclass
from pathlib import Path

from desdobra import PASTA_MOTOR

ARQUIVO_REGISTRO = PASTA_MOTOR / 'fontes-de-limites.json'
SITUACOES = ('medido', 'decidido', 'folha', 'a_calibrar')
EFEITOS = ('reprova', 'avisa', 'registra')


class ErroLimite(Exception):
    pass


@dataclass(frozen=True)
class Limite:
    id: str
    valor: object
    unidade: str
    fonte: dict | None
    situacao: str
    efeito: str
    nota: str | None = None

    @property
    def efeito_efetivo(self):
        """O efeito que o codigo aplica: a_calibrar nunca reprova (cai para avisa)."""
        if self.situacao == 'a_calibrar' and self.efeito == 'reprova':
            return 'avisa'
        return self.efeito

    def citacao(self):
        """O que o laudo e os relatorios gravam ao lado de uma medida: id, valor, fonte e situacao."""
        return {'limite_id': self.id, 'valor': self.valor, 'unidade': self.unidade,
                'fonte': self.fonte, 'situacao': self.situacao, 'efeito': self.efeito_efetivo}


def _conferir(item):
    lid = item.get('id')
    if item.get('situacao') not in SITUACOES:
        raise ErroLimite('%s: situacao %r fora de %s' % (lid, item.get('situacao'), SITUACOES))
    if item.get('efeito') not in EFEITOS:
        raise ErroLimite('%s: efeito %r fora de %s' % (lid, item.get('efeito'), EFEITOS))
    if item['situacao'] == 'a_calibrar' and item['efeito'] == 'reprova':
        raise ErroLimite('%s: limite a calibrar não pode reprovar' % lid)
    if item['situacao'] != 'a_calibrar' and not item.get('fonte'):
        raise ErroLimite('%s: sem fonte, a situacao tem de ser a_calibrar' % lid)
    if item['situacao'] != 'a_calibrar' and item.get('valor') is None:
        raise ErroLimite('%s: só limite a calibrar pode ficar sem valor' % lid)


@functools.cache
def carregar(caminho=None):
    """Carrega e confere o registro. Devolve {id: Limite}. Erro claro se algo nao bate."""
    from desdobra import contratos
    caminho = Path(caminho) if caminho else ARQUIVO_REGISTRO
    dados = contratos.ler(caminho, 'fontes-de-limites/1')
    registro = {}
    for item in dados['limites']:
        _conferir(item)
        if item['id'] in registro:
            raise ErroLimite('id repetido no registro: %s' % item['id'])
        registro[item['id']] = Limite(id=item['id'], valor=item.get('valor'), unidade=item['unidade'],
                                      fonte=item.get('fonte'), situacao=item['situacao'], efeito=item['efeito'],
                                      nota=item.get('nota'))
    return registro


def obter(limite_id):
    try:
        return carregar()[limite_id]
    except KeyError:
        raise ErroLimite('limite %r não está em fontes-de-limites.json' % limite_id) from None


def valor(limite_id):
    lim = obter(limite_id)
    if lim.valor is None:
        raise ErroLimite('limite %r está a calibrar e ainda não tem valor' % limite_id)
    return lim.valor


def efeito(limite_id):
    return obter(limite_id).efeito_efetivo


def registrar(subparsers):
    p = subparsers.add_parser('limites', help='Mostra o registro de limites (valor, fonte e efeito)')
    p.set_defaults(executar=_executar_listar, nome_comando='limites')


def _executar_listar(args):
    from desdobra.resultado import Resultado
    registro = carregar()
    linhas = []
    for lim in registro.values():
        fonte = ('%s %s' % (lim.fonte.get('arquivo'), lim.fonte.get('secao') or '')).strip() if lim.fonte else 'sem fonte'
        linhas.append('%s = %s %s [%s, %s] (%s)' % (lim.id, json.dumps(lim.valor, ensure_ascii=False), lim.unidade,
                                                    lim.situacao, lim.efeito_efetivo, fonte))
    por_situacao = {s: sum(1 for x in registro.values() if x.situacao == s) for s in SITUACOES}
    return Resultado(comando='limites', contagens=dict(limites=len(registro), **por_situacao), linhas_humanas=linhas)
