# -*- coding: utf-8 -*-
"""Fronteira com o modelo (arquitetura-v1.md, 4.9): a unica porta por onde conteudo do job chega ao Claude.

  - segredos.py: detector de segredos (padroes do registro, segredos.padroes) sobre nomes e textos;
  - envelope.py: o envelope de saida que o motor imprime com --envelope, filtrado pelo modo de dados;
  - pacote.py:   o rascunho de sugestoes/pacote-modelo.json por modo (sem miniaturas no M1).

Achado de segredo vira bloqueio: a camada sai do envelope e do pacote, e o detalhe (layer_id e nome do
padrao, nunca o trecho achado) vai so para sugestoes/segredos-bloqueados.json, que so o DA ve.
"""
