# -*- coding: utf-8 -*-
"""Esqueleto do Mac. Nada foi testado no Mac ainda (decisoes-v1.md, render no 2: nada de esforco de Mac ate
haver Mac). O caminho registrado para o isolador e um vigia de memoria no pai mais timeout
(pesquisa/render-local-pesquisa.md, 2), nunca testado.

executar_isolado nunca executa: devolve 'recusado' com a mensagem fixa (o contrato da interface proibe
levantar excecao por causa do filho). O resto do que depende do sistema levanta MacNaoSuportado com a mesma
mensagem. porta_livre e interpretador vem da classe base, que nao depende do sistema.
"""
from desdobra.plataforma import Plataforma, ResultadoFilho

MENSAGEM = 'Mac ainda não suportado: aguardando máquina de teste.'


class MacNaoSuportado(RuntimeError):
    """O desdobra ainda nao roda no Mac."""

    def __init__(self, mensagem=MENSAGEM):
        super().__init__(mensagem)


class PlataformaMac(Plataforma):
    nome = 'mac'

    def executar_isolado(self, comando, orcamento_bytes, tempo_s, pasta_trabalho, *, ambiente=None):
        return ResultadoFilho(situacao='recusado', codigo=None, pico_bytes=None, stdout_bytes=b'', stderr_resumo='',
                              motivo=MENSAGEM)

    def fontes_instaladas(self):
        raise MacNaoSuportado()
