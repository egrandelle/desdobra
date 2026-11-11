# -*- coding: utf-8 -*-
"""M7b, D6: roteiro dos seis formatos, resolvidos so pela tela (arquitetura-v1.md, 9.8; decisoes-v1.md, 164, 167 e
171; plano do M7b, D6 e secao 4; respostas do Duda as perguntas 1, 5 e 10).

Dois jobs sinteticos com a estrutura de camadas dos KVs A e B (testes/sinteticos/kv_a_b.py, gerados na hora): o
packshot em tres camadas na frente de um circulo de fundo, o titulo, a linha, os icones, o apoio e a assinatura. Cada
job tem o 2048x720, o 1008x432 e o 800x600, cada um numa familia. O passo 2 (as funcoes) e o modo de dados ficam
escolhidos antes de abrir a pagina, como no roteiro do editor de mestre (E2); o resto e o DA, so com cliques, arrastos
e o numero digitado no campo Tamanho (modo de teste da tela, meio fixture_de_teste / medicao):
  - KV B 2048x720 (o packshot da pergunta 5): escolhe a garrafa, o copo, a lata e o circulo juntos (clique e
    Shift+clique), digita 85 em Tamanho e arrasta o grupo para baixo, ate os produtos sangrarem na base;
  - KV B 1008x432 (o antes e depois da pergunta 5, revisao 1 da fase D): o mesmo grupo arrastado para a direita ate a
    lata passar da borda (o antes: a tela deixa, sem pedir ajuste), 85 em Tamanho e o grupo para a esquerda e para
    baixo: os tres produtos inteiros, sangrando na base, e o circulo passando da direita;
  - KV B 800x600: arrasta o grupo do packshot para a esquerda e a linha para cima, mais perto do titulo;
  - KV A 2048x720: escolhe o bloco de texto (titulo, linha, apoio e icones) com o retangulo de selecao e clica "À
    esquerda" e "Meio da altura" (pela margem);
  - KV A 1008x432: quebra o apoio em duas linhas (um clique entre as palavras) e alinha o bloco como no 2048x720;
  - KV A 800x600: digita 155 em Tamanho na assinatura e a arrasta para a esquerda, mais perto do apoio;
  - em cada familia, "Confirmar família"; no fim de cada job, "Salvar e seguir".
Conferencias na derivacao gravada (secao 4 do plano), contra a proposta que a tela mostrou antes das edicoes:
  - KV B 2048x720: a area do packshot menor, o centro dele mais baixo, os quatro elementos com as mesmas
    distancias relativas (tudo escalado pelo mesmo fator), os tres produtos inteiros na largura e sangrando na base;
  - KV B 1008x432: a proposta sem produto cortado na lateral, a lata cortada no antes, o grupo a 85% do antes, os tres
    produtos inteiros na largura e sangrando na base, o circulo passando da direita como sangria do DA, e, como no
    2048x720, a area do packshot menor e o centro dele mais baixo que na proposta (revisao 2 da fase D);
  - KV B 800x600: o centro do packshot na largura a esquerda do da proposta; o titulo e a linha mais perto;
  - KV A 2048x720 e 1008x432: a borda esquerda do bloco na margem e o centro do bloco na metade da altura (1 px);
  - KV A 1008x432: o apoio com exatamente 2 linhas na medida do render (derivacao.medida_quebras);
  - KV A 800x600: a assinatura com pelo menos 1,5 vez a escala da proposta e mais perto do apoio;
  - os seis formatos derivados, sem falha que peca ajuste; os elementos que o DA mexeu com origem "da";
  - nenhum arquivo do motor mudou do comeco ao fim do roteiro (sha de motor/desdobra/).
O tempo e o numero de cliques, arrastos e teclas de cada formato vao para o arquivo da variavel de ambiente
DESDOBRA_MEDICAO_SEIS_FORMATOS, quando ela existe (fora do repositorio; sem ela, nada e gravado fora da pasta temporaria
do teste). Tudo sintetico: os PSD gerados na hora e a fonte de autoteste do motor."""
import hashlib
import json
import math
import os
import platform
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

import test_tela_grupo as tgr
from conftest import PASTA_PACOTE
from desdobra import contratos, humano
from desdobra.tela import rascunho as tr
from sinteticos import kv_a_b as kv

VARIAVEL_MEDICAO = 'DESDOBRA_MEDICAO_SEIS_FORMATOS'
TOL = 1.0  # numero-neutro: px, a folga do criterio do bloco na margem e no meio (secao 4)
TOL_GRUPO = 0.5  # numero-neutro: px de folga do arredondamento da derivacao (as distancias do grupo)
PACKSHOT_TAMANHO = '85'  # numero-neutro: o tamanho que o DA digita no packshot (uma leve escala para menor)
ASSINATURA_TAMANHO = '155'  # numero-neutro: o tamanho que o DA digita na assinatura (o D3)
ESCALA_MIN_ASSINATURA = 1.5  # numero-neutro: o criterio da secao 4 (pelo menos 1,5 vez a da proposta)
# os arrastos do DA, em px da peca (convertidos em px de tela pela escala do palco)
DESCER_PACKSHOT = {'p2048': 40.0}  # numero-neutro: ate os produtos sangrarem na base
# o antes e depois do 1008x432 (pergunta 5): o grupo para a direita ate a lata passar da borda; depois, a 85% (preso
# na direita e na base, onde ele chega a borda), para a esquerda ate a lata caber (o circulo, 14 px alem dela, continua
# passando da direita) e para baixo ate os produtos sangrarem na base
LATA_CORTADA = (120.0, 0.0)  # numero-neutro: px da peca
PRODUTOS_INTEIROS = (-38.0, 20.0)  # numero-neutro: px da peca
PACKSHOT_ESQUERDA = 40.0  # numero-neutro: px da peca, o packshot do 800x600 para a esquerda
LINHA_ACIMA = 8.0  # numero-neutro: px da peca, a linha do 800x600 para perto do titulo
ASSINATURA_ARRASTO = (-150.0, -20.0)  # numero-neutro: px da peca, a assinatura do 800x600 para perto do apoio
QUEBRA_APOIO = 6  # numero-neutro: a posicao do espaco entre 'VOX AH' e 'HOAX'
SALVO = ('() => (document.documentElement.dataset.rascunho === "salvo" && '
         'document.documentElement.dataset.previa === "pronta") ? "1" : ""')
PREVIA_PRONTA = '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""'
# o meio da etiqueta do elemento, quando nada a cobre
JS_PONTO_NA_ETIQUETA = """i => {
  const e = document.querySelector('#palco .rotulo[data-elemento="' + i + '"] .etiqueta');
  if (!e) return null;
  const r = e.getBoundingClientRect();
  for (let fx = 0.5; fx < 1; fx += 0.1) {
    const x = r.left + fx * r.width, y = r.top + r.height / 2;
    const no = document.elementFromPoint(x, y);
    const rot = no && no.closest('.rotulo');
    if (rot && rot.dataset.elemento === i) return [x, y];
  }
  return null;
}"""


@pytest.fixture
def medida_limpa():
    """O cache da medida da quebra (por processo) vazio na entrada e na saida: o roteiro mede do zero e nao deixa a
    medida dele pronta para o teste seguinte."""
    from desdobra.derivacao import medida_quebras
    medida_quebras.limpar_cache()
    yield
    medida_quebras.limpar_cache()


# ------------------------------------------------------------------ contas
def _uniao(cs):
    return [min(c[0] for c in cs), min(c[1] for c in cs), max(c[2] for c in cs), max(c[3] for c in cs)]


def _area(c):
    return (c[2] - c[0]) * (c[3] - c[1])


def _centro(c):
    return ((c[0] + c[2]) / 2.0, (c[1] + c[3]) / 2.0)


def _distancia(a, b):
    """A menor distancia entre duas caixas (0 quando se tocam ou se cobrem)."""
    dx = max(b[0] - a[2], a[0] - b[2], 0.0)
    dy = max(b[1] - a[3], a[1] - b[3], 0.0)
    return math.hypot(dx, dy)


def _sha_do_motor():
    """O sha256 de cada arquivo de motor/desdobra/, fora o cache do Python."""
    return {p.relative_to(PASTA_PACOTE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(PASTA_PACOTE.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}


def _caixas_da_previa(r):
    return {m['formato']: {e['id']: [float(x) for x in e['caixa']] for e in m['palco']['elementos']}
            for m in r['membros']}


def _derivacao(job, fid):
    from desdobra.derivacao import nucleo as nd
    return contratos.ler(job / nd.PASTA / ('%s.json' % fid), nd.ESQUEMA)


def _caixas(d):
    return {e['id']: [float(x) for x in e['caixa']] for e in d['elementos']}


def _rascunho(job):
    """O rascunho gravado, relido quando o servidor da tela esta no meio da troca do arquivo (no Windows, o arquivo
    trocado fica sem leitura por um instante)."""
    fim = time.monotonic() + 5  # numero-neutro: segundos de teto da releitura
    while True:
        try:
            return tgr._rascunho_gravado(job) or {}
        except (PermissionError, ValueError):
            if time.monotonic() > fim:
                raise
            time.sleep(0.05)  # numero-neutro: intervalo do teste


def _edicoes(job, gid):
    return (_rascunho(job).get('familias', {}).get(gid) or {}).get('edicoes') or []


# ------------------------------------------------------------------ o DA na pagina, contado
class DA:
    """Os gestos do DA na pagina, contados por formato: cliques (com ou sem Shift), arrastos e teclas."""

    def __init__(self, pg, job, conteudo=None):
        self.pg, self.job, self.conteudo = pg, job, conteudo
        self.contas = {}
        self.conta = None
        self.antes_lateral = {}  # {formato: caixas} do antes da pergunta 5, na previa da tela

    def formato(self, fid):
        self.conta = self.contas.setdefault(fid, {'cliques': 0, 'arrastos': 0, 'teclas': 0, 'tempo_s': 0.0})

    def clicar(self, seletor):
        self.pg.click(seletor)
        self.conta['cliques'] += 1

    def clicar_no_elemento(self, eid, shift=False):
        x, y = self.ponto(eid)
        if shift:
            self.pg.keyboard.down('Shift')
        self.pg.mouse.click(x, y)
        if shift:
            self.pg.keyboard.up('Shift')
        self.conta['cliques'] += 1

    def ponto(self, eid):
        """Um ponto de tela que pega o elemento: dentro da caixa dele ou, quando a etiqueta de um vizinho cobre a caixa
        (a linha fina embaixo do titulo), na etiqueta dele, que tambem e a alca do elemento."""
        p = self.pg.evaluate(tgr.JS_PONTO, eid) or self.pg.evaluate(JS_PONTO_NA_ETIQUETA, eid)
        assert p, eid
        return p

    def arrastar(self, eid, dx, dy):
        """Arrasta o elemento (ou o grupo escolhido em que ele esta) dx, dy px da peca."""
        import test_tela_palco as tp
        k = tp._escala_do_palco(self.pg)
        x, y = self.ponto(eid)
        self.pg.mouse.move(x, y)
        self.pg.mouse.down()
        self.pg.mouse.move(x + dx * k, y + dy * k, steps=6)  # numero-neutro: passos do arrasto
        self.pg.mouse.up()
        self.conta['arrastos'] += 1

    def retangulo(self, ids):
        """O retangulo de selecao em volta dos elementos, de baixo para cima a partir do fundo."""
        r = self.pg.evaluate('''ids => { const rs = ids.map(i => document.querySelector(
            '#palco .rotulo[data-elemento="' + i + '"]').getBoundingClientRect());
            return [Math.min(...rs.map(r => r.left)), Math.min(...rs.map(r => r.top)),
                    Math.max(...rs.map(r => r.right)), Math.max(...rs.map(r => r.bottom))]; }''', ids)
        folga = 6  # numero-neutro: px de tela fora da caixa dos elementos
        self.pg.mouse.move(r[2] + folga, r[3] + folga)
        self.pg.mouse.down()
        self.pg.mouse.move(r[0] - folga, r[1] - folga, steps=6)  # numero-neutro: passos do arrasto
        self.pg.mouse.up()
        self.conta['arrastos'] += 1

    def tamanho(self, texto):
        """Clica no campo Tamanho, digita o numero e aperta Enter."""
        self.clicar('#ed-tamanho')
        self.pg.fill('#ed-tamanho', '')
        self.pg.keyboard.type(texto)
        self.pg.keyboard.press('Enter')
        self.conta['teclas'] += len(texto) + 1

    def edicoes(self, gid):
        return _edicoes(self.job, gid)

    def esperar_edicao(self, gid, n):
        """Espera o rascunho gravado com n edicoes na familia e a previa de volta."""
        import test_tela_palco as tp
        fim = time.monotonic() + 60  # numero-neutro: segundos de teto do teste
        while len(self.edicoes(gid)) < n:
            assert time.monotonic() < fim, ('a edicao nao foi gravada', gid, n, self.edicoes(gid))
            self.pg.wait_for_timeout(50)  # numero-neutro: ms, intervalo do teste
        tp._esperar(self.pg, SALVO)


def _escolhidos(pg):
    return pg.evaluate(tgr.JS_ESCOLHIDOS)


def _abrir_familia(da, estado, gid, fid):
    """A aba da familia e, quando o palco nao a mostra, a ficha do formato: os cliques do DA."""
    import test_tela_palco as tp
    o, g, _co = tp._onde(estado, fid)
    assert g['id'] == gid
    aba = da.pg.evaluate('t => { const b = Array.from(document.querySelectorAll("#orientacoes [role=tab]"))'
                         '.find(x => x.textContent.startsWith(t)); return b.getAttribute("aria-selected"); }',
                         o['rotulo'])
    if aba != 'true':
        da.pg.locator('#orientacoes [role=tab]', has_text=o['rotulo']).first.click()
        da.conta['cliques'] += 1
        tp._esperar(da.pg, '() => document.getElementById("palco").dataset.pronto || ""')
    da.clicar('#composicoes [data-grupo="%s"]' % gid)
    tp._esperar(da.pg, '() => document.getElementById("palco").dataset.pronto || ""')
    if tp._no_palco(da.pg) != fid:
        da.clicar('.ficha[data-formato="%s"]' % fid)
        tp._esperar(da.pg, '() => document.getElementById("palco").dataset.pronto || ""')
    assert tp._no_palco(da.pg) == fid
    tp._esperar(da.pg, PREVIA_PRONTA)


def _confirmar(da, seletor):
    """O botao e o "Confirmar" do dialogo da janela: dois cliques."""
    import test_tela_palco as tp
    tp._esperar(da.pg, '() => document.querySelector(%s).disabled ? "" : "1"' % json.dumps(seletor))
    da.clicar(seletor)
    tp._esperar(da.pg, '() => document.getElementById("confirmacao").open ? "1" : ""')
    da.pg.locator('#confirmacao button').filter(has_text=re.compile(r'^Confirmar$')).click()
    da.conta['cliques'] += 1
    tp._esperar(da.pg, '() => document.documentElement.dataset.estadoAto === "feito" ? "1" : ""')


# ------------------------------------------------------------------ o que o DA faz em cada formato
def _packshot_menor_e_mais_baixo(da, gid, fid, ids):
    """KV B 2048x720 e 1008x432: o grupo do packshot a 85% e arrastado para baixo, sangrando na base."""
    grupo = [ids[p] for p in kv.PACKSHOT]
    da.clicar_no_elemento(grupo[0])
    for eid in grupo[1:]:
        da.clicar_no_elemento(eid, shift=True)
    assert _escolhidos(da.pg) == sorted(grupo)
    n = len(da.edicoes(gid))
    da.tamanho(PACKSHOT_TAMANHO)
    da.esperar_edicao(gid, n + 1)
    da.arrastar(grupo[0], 0.0, DESCER_PACKSHOT[fid])
    da.esperar_edicao(gid, n + 2)
    eds = da.edicoes(gid)
    assert [e['acao'] for e in eds] == ['escalar', 'mover'] and all(e.get('elementos') == grupo for e in eds), eds


def _membro_da_previa(da, gid, fid):
    """O membro fid da previa da tela com as edicoes gravadas da familia (o que o palco mostra ao DA agora)."""
    r = da.conteudo['editar']({'familia': gid, 'versao': None, 'edicoes': da.edicoes(gid)})
    return next(m for m in r['membros'] if m['formato'] == fid)


def _packshot_cortado_na_lateral_e_inteiro(da, gid, fid, ids):
    """KV B 1008x432, o antes e depois do Duda (pergunta 5): a lata cortada pela borda direita, depois o grupo a 85% e
    para a esquerda, com os tres produtos inteiros, sangrando na base, e o circulo passando da direita. A proposta do
    desdobra nunca corta um produto inteiro no KV pela lateral (o solver o deixa dentro do quadro); o corte do antes e
    o DA que arrasta o grupo para a direita, como o layout que o Duda mostrou."""
    grupo = [ids[p] for p in kv.PACKSHOT]
    lata = ids['lata']
    da.clicar_no_elemento(grupo[0])
    for eid in grupo[1:]:
        da.clicar_no_elemento(eid, shift=True)
    assert _escolhidos(da.pg) == sorted(grupo)
    da.arrastar(grupo[0], *LATA_CORTADA)
    da.esperar_edicao(gid, 1)
    # o antes: a lata passa da borda direita, e a tela deixa (sangria do DA, sem "Pede ajuste")
    m = _membro_da_previa(da, gid, fid)
    assert 'dir' in (m['sangria_do_da'].get(lata) or []), m['sangria_do_da']
    assert m['falhas'] == [], m['falhas']
    da.antes_lateral[fid] = {e['id']: [float(x) for x in e['caixa']] for e in m['palco']['elementos']}
    da.tamanho(PACKSHOT_TAMANHO)
    da.esperar_edicao(gid, 2)
    da.arrastar(grupo[0], *PRODUTOS_INTEIROS)
    da.esperar_edicao(gid, 3)
    eds = da.edicoes(gid)
    assert [e['acao'] for e in eds] == ['mover', 'escalar', 'mover'] and all(e.get('elementos') == grupo for e in eds)


def _packshot_a_esquerda_e_linha_perto(da, gid, fid, ids):
    """KV B 800x600: o grupo do packshot para a esquerda; a linha para cima, perto do titulo."""
    grupo = [ids[p] for p in kv.PACKSHOT]
    da.clicar_no_elemento(grupo[0])
    for eid in grupo[1:]:
        da.clicar_no_elemento(eid, shift=True)
    da.arrastar(grupo[0], -PACKSHOT_ESQUERDA, 0.0)
    da.esperar_edicao(gid, 1)
    da.pg.keyboard.press('Escape')
    da.conta['teclas'] += 1
    # a linha fina fica embaixo da etiqueta do apoio: o DA a escolhe pela etiqueta dela e entao a arrasta (a etiqueta
    # de um elemento ainda nao escolhido comeca o retangulo de selecao, revisao 1 da fase D)
    da.clicar_no_elemento(ids['linha'])
    da.arrastar(ids['linha'], 0.0, -LINHA_ACIMA)
    da.esperar_edicao(gid, 2)
    eds = da.edicoes(gid)
    assert [(e['acao'], e['elemento']) for e in eds] == [('mover', grupo[0]), ('mover', ids['linha'])], eds
    assert eds[0]['dx'] < 0 and eds[1]['dy'] < 0 and 'elementos' not in eds[1]


def _bloco_na_margem_e_no_meio(da, gid, fid, ids):
    """KV A 2048x720 e 1008x432: o bloco de texto pelo retangulo, "À esquerda" e "Meio da altura" pela margem."""
    bloco = [ids[p] for p in kv.BLOCO]
    da.pg.keyboard.press('Escape')
    da.conta['teclas'] += 1
    da.retangulo(bloco)
    assert _escolhidos(da.pg) == sorted(bloco)
    n = len(da.edicoes(gid))
    da.clicar('#ed-al-esquerda')
    da.esperar_edicao(gid, n + 1)
    da.clicar('#ed-al-meio')
    da.esperar_edicao(gid, n + 2)
    eds = da.edicoes(gid)[n:]
    assert [(e['acao'], e['alvo'], e['referencia'], sorted(e['elementos'])) for e in eds] == \
        [('alinhar', 'margem_esquerda', 'margem', sorted(bloco)),
         ('alinhar', 'centro_vertical', 'margem', sorted(bloco))]


def _apoio_em_duas_linhas_e_bloco(da, gid, fid, ids):
    """KV A 1008x432: o apoio quebrado entre 'VOX AH' e 'HOAX' (um clique) e o bloco como no 2048x720."""
    import test_quebra_na_tela as tqt
    import test_tela_palco as tp
    apoio = ids['apoio']
    previas = []
    da.pg.on('request', lambda r: previas.append(r.url) if '/api/familia/previa' in r.url else None)
    da.clicar_no_elemento(apoio)
    da.clicar('#ed-quebra')
    tp._esperar(da.pg, '() => document.getElementById("editor-quebra").hidden ? "" : "1"')
    assert da.pg.evaluate(tqt.JS_LINHAS_DO_CONTROLE) == [kv.APOIO]
    antes = len(previas)
    da.clicar('#quebra-linhas button[data-pos="%d"]' % QUEBRA_APOIO)
    assert da.pg.evaluate(tqt.JS_LINHAS_DO_CONTROLE) == ['VOX AH', 'HOAX']
    fim = time.monotonic() + 60  # numero-neutro: segundos de teto do teste
    while len(previas) == antes:  # a previa da quebra sai 300 ms depois do clique
        assert time.monotonic() < fim, 'a pagina nao pediu a previa da quebra'
        da.pg.wait_for_timeout(50)  # numero-neutro: ms, intervalo do teste
    tp._esperar(da.pg, SALVO)
    assert da.pg.evaluate(tqt.JS_LINHAS, apoio) == ['VOX AH', 'HOAX']
    quebras = _rascunho(da.job)['familias'][gid].get('quebras') or []
    assert [(q['elemento'], q['inseridas'], q['origem']) for q in quebras] == [(apoio, [QUEBRA_APOIO], 'da')]
    _bloco_na_margem_e_no_meio(da, gid, fid, ids)


def _assinatura_maior_e_perto(da, gid, fid, ids):
    """KV A 800x600: a assinatura a 155% e arrastada para a esquerda, perto do apoio."""
    a = ids['assinatura']
    da.clicar_no_elemento(a)
    da.tamanho(ASSINATURA_TAMANHO)
    da.esperar_edicao(gid, 1)
    da.arrastar(a, *ASSINATURA_ARRASTO)
    da.esperar_edicao(gid, 2)
    eds = da.edicoes(gid)
    assert eds[0] == {'elemento': a, 'acao': 'escalar', 'fator': 1.55}, eds
    assert eds[1]['acao'] == 'mover' and eds[1]['dx'] < 0, eds


ROTEIRO = {
    'b': [('p2048', _packshot_menor_e_mais_baixo), ('p1008', _packshot_cortado_na_lateral_e_inteiro),
          ('p800', _packshot_a_esquerda_e_linha_perto)],
    'a': [('p2048', _bloco_na_margem_e_no_meio), ('p1008', _apoio_em_duas_linhas_e_bloco),
          ('p800', _assinatura_maior_e_perto)],
}


def _resolver_pela_tela(j, chave):
    """Abre a tela do job, resolve os tres formatos so pela pagina e clica "Salvar e seguir". Devolve (proposta,
    previas da tela, contas do DA, contagem do servidor, ids, familias, o antes da pergunta 5 por formato)."""
    from playwright.sync_api import sync_playwright

    import test_tela_palco as tp
    from desdobra.chromium import navegador
    from desdobra.job import modo_dados
    from desdobra.tela import atos as ta
    from desdobra.tela import estado as te
    from desdobra.tela import servidor as ts
    job, ids = j['job'], {p: 'el%d' % lid for p, lid in j['ids'].items()}
    conteudo = te.montar(job)
    familia = {fid: next(g for g, f in conteudo['familias'].items() if fid in f['formatos'])
               for fid, _w, _h in kv.FORMATOS}
    assert len(set(familia.values())) == len(kv.FORMATOS), conteudo['familias']
    # a proposta que a tela mostra antes das edicoes do DA, por formato
    proposta = {}
    for fid, gid in familia.items():
        r = conteudo['editar']({'familia': gid, 'versao': None, 'edicoes': []})
        proposta[fid] = {'caixas': _caixas_da_previa(r)[fid],
                         'quadro': next(m['quadro'] for m in r['membros'] if m['formato'] == fid)}
    navegador.apontar_playwright()
    with ts.ServidorTela(conteudo, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo)) as srv, sync_playwright() as pw:
        # o passo 2 e o modo de dados ja escolhidos; as tres familias ficam com o DA, sem nada
        familias = {gid: {'versao': None, 'confirmada': False, 'edicoes': []} for gid in familia.values()}
        corpo = dict({'job_id': srv.job_id, 'laudo_sha256': srv.laudo_sha256, 'familias': familias},
                     **kv.passo_2(j['funcoes']))
        tr.gravar(job, corpo, job_id=srv.job_id, laudo_atual=srv.laudo_sha256, origem=srv.origem_rascunho)
        modo_dados.gravar(job, 'c', disparo=humano.exigir_tela(modo_dados.ESCOLHER, srv._sessao_humana,
                                                               confirmado=True))
        srv.estado = conteudo['recarregar']()
        nav, pg = tp._pagina_da_tela(pw, srv, 1600, 900)  # numero-neutro: janela do teste
        da = DA(pg, job, conteudo)
        try:
            for fid, fazer in ROTEIRO[chave]:
                da.formato(fid)
                inicio = time.monotonic()
                _abrir_familia(da, conteudo['estado'], familia[fid], fid)
                fazer(da, familia[fid], fid, ids)
                _confirmar(da, '#confirmar-familia')
                da.conta['tempo_s'] = time.monotonic() - inicio
                assert pg.evaluate('() => document.getElementById("confirmar-familia").textContent') == \
                    'Família confirmada'
            # "Salvar e seguir": dois cliques, contados a parte (valem para os tres formatos do job)
            da.formato('salvar')
            inicio = time.monotonic()
            _confirmar(da, '#salvar-seguir')
            tp._esperar(pg, '() => document.getElementById("salvo").hidden ? "" : "1"')
            da.conta['tempo_s'] = time.monotonic() - inicio
            texto = pg.evaluate(tp.JS_TEXTO_DA_MOLDURA)
            assert not tp.IDENTIFICADOR.findall(texto), tp.IDENTIFICADOR.findall(texto)
            assert chr(0x2014) not in texto and chr(0x2013) not in texto
            # a previa que a tela mostrou ao DA no fim, por formato
            rascunho = _rascunho(job)
            previas = {}
            for fid, gid in familia.items():
                f = rascunho['familias'][gid]
                assert f['confirmada'] is True, (fid, f)
                pedido = {'familia': gid, 'versao': f['versao'], 'edicoes': f['edicoes']}
                if f.get('quebras'):
                    pedido['quebras'] = f['quebras']
                previas[fid] = next(m for m in conteudo['editar'](pedido)['membros'] if m['formato'] == fid)
        finally:
            nav.close()
        contagem = dict(srv.contagem)
    return proposta, previas, da.contas, contagem, ids, familia, da.antes_lateral


# ------------------------------------------------------------------ as conferencias da secao 4
def _conferir_packshot_menor(d, prop, ids, W, H):
    grupo = [ids[p] for p in kv.PACKSHOT]
    produtos = [ids[p] for p in kv.PRODUTOS]
    cd, cp = _caixas(d), prop['caixas']
    ud, up = _uniao([cd[i] for i in grupo]), _uniao([cp[i] for i in grupo])
    k = (cd[grupo[0]][2] - cd[grupo[0]][0]) / (cp[grupo[0]][2] - cp[grupo[0]][0])
    tgr._confere_grupo(cp, cd, k, 0.5, 0.5, grupo, tol=TOL_GRUPO, ponto=False)
    inteiros = all(cd[i][0] >= 0 and cd[i][2] <= W for i in produtos)
    sangram = all(cd[i][3] > H for i in produtos)
    return {'area': (_area(ud), _area(up)), 'centro_y': (_centro(ud)[1], _centro(up)[1]), 'fator': k,
            'inteiros_na_largura': inteiros, 'sangram_na_base': sangram,
            'ok': _area(ud) < _area(up) and _centro(ud)[1] > _centro(up)[1] and inteiros and sangram}


def _conferir_packshot_lateral(d, prop, antes, ids, W, H):
    """O antes e depois da pergunta 5: no antes (o palco depois do primeiro arrasto) a lata passa da borda direita; no
    depois, o grupo a 85% do antes, os tres produtos inteiros na largura e sangrando na base, e o circulo passando da
    direita, como sangria do DA. A proposta do desdobra nunca cortava um produto pela lateral. Como no 2048x720 (secao
    4), a area do packshot fica menor e o centro dele mais baixo que na proposta (revisao 2 da fase D)."""
    grupo = [ids[p] for p in kv.PACKSHOT]
    produtos = [ids[p] for p in kv.PRODUTOS]
    cd, cp = _caixas(d), prop['caixas']
    ud, up = _uniao([cd[i] for i in grupo]), _uniao([cp[i] for i in grupo])
    menor_e_mais_baixo = _area(ud) < _area(up) and _centro(ud)[1] > _centro(up)[1]
    por_id = {e['id']: e for e in d['elementos']}
    k = (cd[grupo[0]][2] - cd[grupo[0]][0]) / (antes[grupo[0]][2] - antes[grupo[0]][0])
    tgr._confere_grupo(antes, cd, k, 0.5, 0.5, grupo, tol=TOL_GRUPO, ponto=False)
    proposta_sem_corte = all(cp[i][0] >= 0 and cp[i][2] <= W for i in produtos)
    antes_cortada = antes[ids['lata']][2] > W
    inteiros = all(cd[i][0] >= 0 and cd[i][2] <= W for i in produtos)
    sangram = all(cd[i][3] > H for i in produtos)
    circulo = cd[ids['circulo']][2] > W and 'dir' in (por_id[ids['circulo']].get('sangria_do_da') or [])
    return {'proposta_sem_corte_na_lateral': proposta_sem_corte, 'antes_lata_x1': (antes[ids['lata']][2], W),
            'fator': k, 'inteiros_na_largura': inteiros, 'sangram_na_base': sangram,
            'circulo_passa_da_direita': (cd[ids['circulo']][2], W),
            'area': (_area(ud), _area(up)), 'centro_y': (_centro(ud)[1], _centro(up)[1]),
            'ok': proposta_sem_corte and antes_cortada and abs(k - float(PACKSHOT_TAMANHO) / 100) < 0.01 and
            inteiros and sangram and circulo and menor_e_mais_baixo}  # numero-neutro: porcentagem e folga do fator


def _conferir_packshot_esquerda(d, prop, ids):
    grupo = [ids[p] for p in kv.PACKSHOT]
    cd, cp = _caixas(d), prop['caixas']
    xd, xp = _centro(_uniao([cd[i] for i in grupo]))[0], _centro(_uniao([cp[i] for i in grupo]))[0]
    t, ln = ids['titulo'], ids['linha']
    dd, dp = _distancia(cd[t], cd[ln]), _distancia(cp[t], cp[ln])
    return {'centro_x': (xd, xp), 'titulo_linha': (dd, dp), 'ok': xd < xp and dd < dp}


def _conferir_bloco(d, prop, ids, H):
    bloco = [ids[p] for p in kv.BLOCO]
    u = _uniao([_caixas(d)[i] for i in bloco])
    margem = prop['quadro']['margem']
    erro_borda, erro_meio = abs(u[0] - margem[0]), abs((u[1] + u[3]) / 2.0 - H / 2.0)
    return {'borda': (u[0], margem[0]), 'meio': ((u[1] + u[3]) / 2.0, H / 2.0), 'erro': (erro_borda, erro_meio),
            'ok': erro_borda <= TOL and erro_meio <= TOL}


def _conferir_assinatura(d, prop, ids):
    a, ap_ = ids['assinatura'], ids['apoio']
    cd, cp = _caixas(d), prop['caixas']
    escala = (cd[a][2] - cd[a][0]) / (cp[a][2] - cp[a][0])
    dd, dp = _distancia(cd[a], cd[ap_]), _distancia(cp[a], cp[ap_])
    return {'escala': escala, 'assinatura_apoio': (dd, dp), 'ok': escala >= ESCALA_MIN_ASSINATURA and dd < dp}


def _linhas_do_apoio(job, ids):
    """As linhas do apoio do 1008x432 na medida do render (derivacao.medida_quebras, a que o render usa)."""
    from desdobra.briefing import modelo as mb
    from desdobra.derivacao import medida_quebras
    from desdobra.derivacao import quebras as mq
    lid = int(ids['apoio'][2:])
    b = mb.ler(job)
    estado = contratos.ler(job / 'estado.json', 'estado/1')
    laudo = contratos.ler(job / mb.ARQUIVO_LAUDO, 'laudo/1')
    [q] = [q for q in b['quebras_por_familia'] if q['layer_id'] == lid]
    medidas = medida_quebras.medir(job, laudo, b, estado)
    return medidas[mq.chave(lid, q.get('manter') or [], q.get('inseridas') or [])]


def _gravar_medicao(texto):
    destino = os.environ.get(VARIAVEL_MEDICAO)
    if destino:
        Path(destino).parent.mkdir(parents=True, exist_ok=True)
        Path(destino).write_text(texto, encoding='utf-8', newline='\n')


@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
@pytest.mark.parametrize('dy, ok', [(31, False), (60, True)], ids=['mais_alto', 'mais_baixo'])
def test_conferencia_lateral_pede_o_packshot_menor_e_mais_baixo(dy, ok):
    """Revisao 2 da fase D: no KV B 1008x432, a secao 4 pede tambem a area do packshot menor e o centro dele mais baixo
    que na proposta. Derivacao montada a mao: o grupo a 85% do antes, os produtos inteiros e sangrando na base, o
    circulo passando da direita; so a altura do grupo muda."""
    W, H = 1008, 432  # numero-neutro: o formato do criterio
    ids = {'garrafa': 'g', 'copo': 'c', 'lata': 'l', 'circulo': 'o'}
    proposta = {'o': [600, 200, 900, 700], 'g': [610, 200, 640, 440], 'c': [650, 300, 680, 440],
                'l': [865, 280, 895, 440]}
    antes = {i: [c[0] + 120, c[1], c[2] + 120, c[3]] for i, c in proposta.items()}  # a lata passa da direita
    k, px, py = 0.85, 720.0, 200.0  # numero-neutro: o fator e o canto do grupo no antes
    depois = {i: [px + k * (c[0] - px) + 35, py + k * (c[1] - py) + dy, px + k * (c[2] - px) + 35,
                  py + k * (c[3] - py) + dy] for i, c in antes.items()}
    d = {'elementos': [{'id': i, 'caixa': c, 'sangria_do_da': ['dir'] if i == 'o' else ['base']}
                       for i, c in depois.items()]}
    r = _conferir_packshot_lateral(d, {'caixas': proposta}, antes, ids, W, H)
    assert r['ok'] is ok, r


def test_seis_formatos_so_pela_tela(tmp_path_factory, medida_limpa):
    base = tmp_path_factory.mktemp('seis')
    jobs = {chave: kv.criar_job(base, chave) for chave in ('a', 'b')}
    sha_antes = _sha_do_motor()
    resultados, contas, contagens = {}, {}, {}
    for chave in ('b', 'a'):
        proposta, previas, contas[chave], contagens[chave], ids, familia, antes_lateral = \
            _resolver_pela_tela(jobs[chave], chave)
        job = jobs[chave]['job']
        tamanhos = {fid: (w, h) for fid, w, h in kv.FORMATOS}
        for fid, _fazer in ROTEIRO[chave]:
            d = _derivacao(job, fid)
            W, H = tamanhos[fid]
            # sem "Pede ajuste" na tela, e a derivacao gravada e a que a tela mostrou ao DA
            assert previas[fid]['falhas'] == [] and previas[fid]['validacoes_reprovadas'] == [], \
                (chave, fid, previas[fid]['falhas'], previas[fid]['validacoes_reprovadas'])
            assert d['situacao'] == 'derivado', (chave, fid, json.dumps(d.get('devolucao'), ensure_ascii=True))
            registros = [r['codigo'] for r in d.get('registros') or []]
            assert 'proposta_com_falha' not in registros, (chave, fid, d.get('registros'))
            assert d['proposta']['confirmada'] is True
            vistas = {e['id']: [float(x) for x in e['caixa']] for e in previas[fid]['palco']['elementos']}
            assert sorted(vistas) == sorted(_caixas(d)), (chave, fid)
            assert all(_caixas(d)[i] == pytest.approx(c, abs=0.01) for i, c in vistas.items()), (chave, fid)
            prop = proposta[fid]
            if chave == 'b' and fid in DESCER_PACKSHOT:
                r = _conferir_packshot_menor(d, prop, ids, W, H)
            elif chave == 'b' and fid in antes_lateral:
                r = _conferir_packshot_lateral(d, prop, antes_lateral[fid], ids, W, H)
            elif chave == 'b':
                r = _conferir_packshot_esquerda(d, prop, ids)
            elif fid == 'p800':
                r = _conferir_assinatura(d, prop, ids)
            else:
                r = _conferir_bloco(d, prop, ids, H)
                if fid == 'p1008':
                    medida = _linhas_do_apoio(job, ids)
                    r['linhas_do_apoio'] = medida.get('linhas')
                    r['ok'] = r['ok'] and medida.get('linhas') == 2  # numero-neutro: o criterio (2 linhas)
                    apoio = {e['id']: e for e in d['elementos']}[ids['apoio']]
                    assert apoio['quebras_origem'] == 'da' and apoio['quebras']['familia'][0]['inseridas'] == \
                        [QUEBRA_APOIO]
            origem = {e['id']: e['origem_geometria'] for e in d['elementos']}
            mexidos = {i for e in _edicoes(job, familia[fid]) for i in e.get('elementos') or [e['elemento']]}
            assert mexidos
            assert all(origem[i] == 'da' for i in mexidos if i in origem), origem
            r['registros'] = registros
            r['decisoes_do_da'] = [x['texto'] for x in previas[fid].get('decisoes_do_da') or []]
            resultados[(chave, fid)] = r
    sha_depois = _sha_do_motor()
    mudou = sorted(k for k in set(sha_antes) | set(sha_depois) if sha_antes.get(k) != sha_depois.get(k))
    falhou = {k: v for k, v in resultados.items() if not v['ok']}
    assert not falhou, falhou
    assert mudou == [], mudou
    for chave, c in contagens.items():
        assert c['proibido'] == 0 and c['csrf_recusado'] == 0 and c['dado_recusado'] == 0, (chave, c)

    linhas = [
        'Medicao do D6 (M7b): roteiro dos seis formatos so pela tela, %s.' % datetime.now().strftime('%Y-%m-%d %H:%M'),
        'Jobs sinteticos com a estrutura dos KVs A e B (testes/sinteticos/kv_a_b.py), fonte de autoteste,',
        'modo de teste da tela (meio fixture_de_teste / medicao).',
        '%s, Python %s.' % (platform.platform(), platform.python_version()),
        'O passo 2 e o modo de dados escolhidos antes de abrir a pagina; cada formato numa familia.',
        'Tempo: do clique na aba da familia ao "feito" de "Confirmar família", no relogio do teste (time.monotonic).',
        'Cliques: clique e Shift+clique do mouse em elemento ou botao, com o "Confirmar" do dialogo.',
        'Arrastos: mover e o retangulo de selecao. Teclas: o numero digitado no campo Tamanho, o Enter e o Esc.',
        '',
        '%-4s %-6s %8s %7s %8s %6s' % ('KV', 'formato', 'tempo_s', 'cliques', 'arrastos', 'teclas'),
    ]
    for chave in ('b', 'a'):
        for fid, _f in ROTEIRO[chave]:
            c = contas[chave][fid]
            linhas.append('%-4s %-6s %8.2f %7d %8d %6d'
                          % (chave.upper(), fid, c['tempo_s'], c['cliques'], c['arrastos'], c['teclas']))
        s = contas[chave]['salvar']
        linhas.append('%-4s %-6s %8.2f %7d %8d %6d  (Salvar e seguir, com a derivacao dos tres)'
                      % (chave.upper(), 'salvar', s['tempo_s'], s['cliques'], s['arrastos'], s['teclas']))
    total = [c for k in contas for f, c in contas[k].items() if f != 'salvar']
    linhas += ['Seis formatos: %.2f s, %d cliques, %d arrastos, %d teclas (sem os dois Salvar e seguir).'
               % (sum(c['tempo_s'] for c in total), sum(c['cliques'] for c in total),
                  sum(c['arrastos'] for c in total), sum(c['teclas'] for c in total)),
               'O tempo e de um robo: serve para comparar o numero de passos com o bb-dooh-jobs,',
               'nunca como tempo de DA.', '',
               'Conferencias da secao 4 na derivacao gravada, contra a proposta que a tela mostrou antes das edicoes:']
    for (chave, fid), r in sorted(resultados.items()):
        partes = ['%s=%s' % (k, _texto(v)) for k, v in sorted(r.items()) if k not in ('ok',)]
        linhas.append('  KV %s %s: %s; %s' % (chave.upper(), fid, 'passa' if r['ok'] else 'falha', '; '.join(partes)))
    linhas += ['Arquivos de motor/desdobra/ com sha diferente do comeco ao fim do roteiro: %d de %d.'
               % (len(mudou), len(sha_antes)),
               'Servidor da tela: proibido, csrf_recusado e dado_recusado em 0 nos dois jobs.', '']
    _gravar_medicao('\n'.join(linhas))


def _texto(v):
    if isinstance(v, float):
        return '%.2f' % v
    if isinstance(v, (tuple, list)):
        return '(%s)' % ', '.join(_texto(x) for x in v)
    return str(v)
