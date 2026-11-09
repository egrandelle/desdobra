# -*- coding: utf-8 -*-
"""Determinismo da derivacao (M7b, A0): o mesmo briefing sintetico derivado de novo, no mesmo processo e em processos
separados (PYTHONHASHSEED diferente), da o mesmo derivacao/<f>.json normalizado (sem gerado_em) nos tres caminhos:
transformacao, solver e galeria. A impressao por formato (desdobra.derivacao.impressao) parte disto. A medicao de 30
rodadas fica fora do repositorio (scratchpad/m7/medicoes/determinismo.txt)."""
import json
import os
import subprocess
from pathlib import Path

import test_derivacao_apoio as ap
from desdobra.derivacao import nucleo as nd

CONF = {'origem': 'fixture_de_teste', 'meio': 'medicao', 'em': '2026-11-06T10:00:00'}
CAMINHOS = {'transform', 'solver', 'galeria'}


def casos():
    """[(ctx, specs)]: o KV horizontal do apoio com tres familias (uma com edicao do DA) e o KV degenerado (muita
    restricao redundante) com folha de faixa."""
    fmts = [ap.formato('mesmo', 800, 400), ap.formato('perto', 480, 300), ap.formato('vertical', 300, 600),
            ap.formato('alto', 1080, 1920), ap.formato('quadrado', 500, 500)]
    b = ap.briefing(formatos=fmts)
    b['composicoes'] = [
        {'familia': 'horizontais', 'formatos': ['mesmo', 'perto'], 'versao': None, 'edicoes': [], 'confirmada': True,
         'confirmacao': CONF},
        {'familia': 'verticais', 'formatos': ['vertical', 'alto'], 'versao': None,
         'edicoes': [{'elemento': 'el20', 'acao': 'mover', 'dx': 0.03, 'dy': 0.05}], 'confirmada': True,
         'confirmacao': CONF},
        {'familia': 'quadrados', 'formatos': ['quadrado'], 'versao': None, 'edicoes': [], 'confirmada': True,
         'confirmacao': CONF}]
    laudo, funcoes = ap.laudo_degenerado()
    ch = 'teste|faixa|1080x1920'
    specs = {ch: ap.spec(ch, {'area_util': {'largura': 1080, 'altura': 1848}, 'faixas': [{'lado': 'inferior', 'px': 72}]})}
    deg = ap.briefing(funcoes=funcoes, formatos=[ap.formato('d%d' % k, w, h, chave=ch) for k, (w, h) in
                                                 enumerate([(1080, 1920), (360, 1080), (400, 600), (320, 448)])])
    return [(nd.contexto(ap.laudo(), b), {}), (nd.contexto(laudo, deg), specs)]


def rodada():
    """{n/formato: [caminho, json normalizado]}."""
    saida = {}
    for n, (ctx, specs) in enumerate(casos()):
        for k, d in nd.derivar_em_memoria(ctx, specs=specs, arquivo_specs='specs/rascunho.json')['formatos'].items():
            d = dict(d)
            d.pop('gerado_em')
            saida['%d/%s' % (n, k)] = [d['caminho'], json.dumps(d, sort_keys=True)]
    return saida


def test_derivacao_igual_no_mesmo_processo_nos_tres_caminhos():
    a = rodada()
    assert {c for c, _j in a.values()} >= CAMINHOS
    for _ in range(2):
        b = rodada()
        assert sorted(a) == sorted(b)
        diferentes = sorted(k for k in a if a[k] != b[k])
        assert not diferentes, diferentes


def test_derivacao_igual_em_processos_separados(python):
    raiz = Path(__file__).parent
    codigo = chr(10).join([
        'import sys, json; sys.path[:0] = [%r, %r]' % (str(raiz), str(raiz.parent / 'motor')),
        'lixo = [object() for _ in range(int(sys.argv[1]))]',
        'import test_determinismo_derivacao as t',
        'print(json.dumps(t.rodada(), sort_keys=True))'])
    saidas = []
    for n, semente in ((0, '0'), (7919, '1'), (31337, '29')):
        r = subprocess.run([python, '-c', codigo, str(n)], capture_output=True, text=True,
                           env=dict(os.environ, PYTHONHASHSEED=semente))
        assert r.returncode == 0, r.stderr[-800:]
        saidas.append(json.loads(r.stdout))
    assert {c for c, _j in saidas[0].values()} >= CAMINHOS
    for s in saidas[1:]:
        diferentes = sorted(k for k in saidas[0] if saidas[0][k] != s.get(k))
        assert not diferentes, diferentes
    assert saidas[0] == rodada()
