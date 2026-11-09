# -*- coding: utf-8 -*-
"""Diferenca por formato em linguagem simples (M7b, A5; desdobra.derivacao.diferenca).

Compara dois corpos da impressao de um formato (derivacao.impressao.corpo): um item por mudanca, com uma frase curta
para o DA. Um caso por tipo de mudanca (entrou, saiu, moveu, cresceu ou diminuiu, funcao, quebra, texto, origem da
geometria, fora da peca, apagado pelo DA, so a entrada mudou) e um teste com mudancas aleatorias: toda mudanca de
impressao da pelo menos um item, e impressao igual nao da nenhum. Material sintetico (test_derivacao_apoio)."""
import random

import pytest

import test_derivacao_apoio as ap
import test_impressao_formato as tif
from desdobra.derivacao import diferenca as dif
from desdobra.derivacao import impressao as mi
from desdobra.derivacao import nucleo as nd


def _corpo(b, fid, d=None, specs=None):
    specs = tif._specs() if specs is None else specs
    ctx = nd.contexto(ap.laudo(), b)
    if d is None:
        d = nd.derivar_em_memoria(ctx, specs=specs, arquivo_specs='specs/rascunho.json', so=[fid])['formatos'][fid]
    return mi.corpo(d, mi.resolvido(ctx['briefing'], ctx['resolvidas'], specs), fid)


@pytest.fixture(scope='module')
def base():
    b = tif._briefing()
    return {fid: _corpo(b, fid) for fid in ('mesmo', 'perto', 'vertical', 'alto')}


def _el(c, eid):
    return next(e for e in c['derivacao']['elementos'] if e['id'] == eid)


def _tipos(itens):
    return [i['tipo'] for i in itens]


def _frases(itens):
    return [i['frase'] for i in itens]


def test_impressao_igual_nao_da_item(base):
    for c in base.values():
        assert dif.diferencas(c, ap.copia(c)) == []


def test_corpo_bate_com_a_impressao(base):
    b = tif._briefing()
    imp, _r = tif._todas(b)
    for fid, c in base.items():
        assert mi.do_corpo(c) == imp[fid]


def test_moveu_em_px_e_em_porcento_do_lado(base):
    c = ap.copia(base['perto'])
    caixa = _el(c, 'el10')['caixa']
    caixa[1] += 24
    caixa[3] += 24
    caixa[0] -= 10
    caixa[2] -= 10
    itens = dif.diferencas(base['perto'], c)
    assert _tipos(itens) == ['moveu']
    assert itens[0]['elemento'] == 'el10'
    assert itens[0]['frase'] == 'O título desceu 24 px (8,0% da altura) e foi 10 px para a esquerda (2,1% da largura).'
    assert itens[0]['antes'] != itens[0]['depois']


def test_subiu_menos_de_um_px(base):
    c = ap.copia(base['perto'])
    caixa = _el(c, 'el10')['caixa']
    caixa[1] -= 0.25
    caixa[3] -= 0.25
    assert _frases(dif.diferencas(base['perto'], c)) == ['O título subiu menos de 1 px.']


def test_cresceu_e_diminuiu(base):
    c = ap.copia(base['perto'])
    caixa = _el(c, 'el20')['caixa']
    caixa[0] -= 6
    caixa[2] += 6
    caixa[1] += 2
    caixa[3] -= 2
    itens = dif.diferencas(base['perto'], c)
    assert _tipos(itens) == ['tamanho']
    assert itens[0]['frase'] == 'O texto de apoio cresceu 12 px na largura e diminuiu 4 px na altura.'


def test_ficou_maior_nas_duas_direcoes(base):
    c = ap.copia(base['perto'])
    caixa = _el(c, 'el30')['caixa']
    caixa[2] += 8
    caixa[3] += 8
    itens = dif.diferencas(base['perto'], c)
    assert _tipos(itens) == ['moveu', 'tamanho']
    assert itens[1]['frase'] == 'O logo principal cresceu 8 px na largura e 8 px na altura.'


def test_entrou_e_saiu(base):
    c = ap.copia(base['perto'])
    sai = c['derivacao']['elementos'].pop(1)
    novo = ap.copia(sai)
    novo.update(id='el99', raiz=99, layer_ids=[99], funcao='selo')
    c['derivacao']['elementos'].append(novo)
    itens = dif.diferencas(base['perto'], c)
    assert ('saiu', 'O título saiu do formato.') in [(i['tipo'], i['frase']) for i in itens]
    assert ('entrou', 'O selo entrou no formato.') in [(i['tipo'], i['frase']) for i in itens]


def test_apagado_pelo_da_e_de_volta(base):
    antes, depois = base['perto'], ap.copia(base['perto'])
    el = next(e for e in depois['derivacao']['elementos'] if e['id'] == 'el40')
    depois['derivacao']['elementos'].remove(el)
    depois['derivacao']['apagados_pelo_da'] = [{'elemento': 'el40', 'layer_ids': [40], 'origem': 'fixture_de_teste'}]
    assert _frases(dif.diferencas(antes, depois)) == ['Você apagou o texto legal nesta família.']
    assert _frases(dif.diferencas(depois, antes)) == ['O texto legal voltou para esta família.']


def test_saiu_e_voltou_para_a_peca(base):
    antes, depois = base['perto'], ap.copia(base['perto'])
    el = next(e for e in depois['derivacao']['elementos'] if e['id'] == 'el30')
    depois['derivacao']['elementos'].remove(el)
    depois['derivacao']['fora_da_peca'] = sorted(depois['derivacao']['fora_da_peca'] + [30])
    itens = dif.diferencas(antes, depois)
    assert _frases(itens) == ['O logo principal saiu da peça.']
    assert itens[0]['tipo'] == 'fora_da_peca'
    assert _frases(dif.diferencas(depois, antes)) == ['O logo principal voltou para a peça.']


def test_camada_solta_sai_da_peca(base):
    depois = ap.copia(base['perto'])
    depois['derivacao']['fora_da_peca'] = sorted(depois['derivacao']['fora_da_peca'] + [77, 78])
    assert _frases(dif.diferencas(base['perto'], depois)) == ['2 camadas saíram da peça.']


def test_mudou_de_funcao(base):
    depois = ap.copia(base['perto'])
    _el(depois, 'el40')['funcao'] = 'cta'
    itens = dif.diferencas(base['perto'], depois)
    assert _tipos(itens) == ['funcao']
    assert itens[0]['frase'] == 'O texto legal agora é o CTA.'


def test_mudou_a_quebra(base):
    depois = ap.copia(base['perto'])
    _el(depois, 'el10')['quebras'] = {'familia': [{'layer_id': 11, 'posicoes': [3]}]}
    assert _frases(dif.diferencas(base['perto'], depois)) == ['As quebras de linha do título mudaram.']


def test_mudou_o_texto(base):
    depois = ap.copia(base['perto'])
    _el(depois, 'el10')['texto_editado'] = 'novo'
    assert _frases(dif.diferencas(base['perto'], depois)) == ['Você editou o texto do título.']
    outro = ap.copia(depois)
    _el(outro, 'el10')['texto_editado'] = 'outro'
    assert _frases(dif.diferencas(depois, outro)) == ['O texto do título mudou.']
    assert _frases(dif.diferencas(depois, base['perto'])) == ['O texto do título voltou ao do KV.']


def test_mudou_a_origem_da_geometria(base):
    depois = ap.copia(base['perto'])
    _el(depois, 'el10')['origem_geometria'] = 'da'
    assert _frases(dif.diferencas(base['perto'], depois)) == [
        'A caixa do título agora vem da sua edição (antes vinha das regras).']


def test_mudou_a_regra_e_a_ancora_do_elemento(base):
    depois = ap.copia(base['perto'])
    _el(depois, 'el10')['regra'] = 'largura'
    _el(depois, 'el10')['ancora'] = ['centro', 'topo']
    assert _frases(dif.diferencas(base['perto'], depois)) == [
        'A regra de escala do título mudou: antes pela área, agora pela largura.',
        'A âncora do título mudou: antes esquerda e topo, agora centro e topo.']


def test_caminho_e_situacao(base):
    depois = ap.copia(base['perto'])
    depois['derivacao']['situacao'] = 'devolvido'
    depois['derivacao']['caminho'] = 'devolvido'
    depois['derivacao']['devolucao'] = {'motivo': 'restricao_obrigatoria_nao_fecha'}
    itens = dif.diferencas(base['perto'], depois)
    assert _tipos(itens)[0] == 'situacao'
    assert itens[0]['frase'] == 'O desdobra não fechou a proposta deste formato, e ele voltou para você.'
    assert _frases(dif.diferencas(depois, base['perto']))[0] == 'O formato agora tem proposta.'
    outro = ap.copia(base['perto'])
    outro['derivacao']['caminho'] = 'transform'
    assert _frases(dif.diferencas(base['perto'], outro)) == ['O formato agora sai da escala do KV (antes saía das regras).']


def test_so_a_entrada_mudou(base):
    # a regra do legal muda no briefing e a derivacao fica igual: o item diz que a peca ficou igual
    b = tif._briefing()
    tif._regra(b, 'texto_legal', 'raiz_area')
    depois = _corpo(b, 'perto', d=ap.copia(base['perto']['derivacao']))
    assert mi.do_corpo(depois) != mi.do_corpo(base['perto'])
    itens = dif.diferencas(base['perto'], depois)
    assert _tipos(itens) == ['entrada']
    assert itens[0]['frase'] == ('A regra de escala do texto legal mudou no briefing (antes tamanho fixo, agora pela '
                                 'área), e a peça ficou igual.')


def test_so_a_spec_mudou(base):
    depois = _corpo(tif._briefing(), 'mesmo', d=ap.copia(base['mesmo']['derivacao']), specs=tif._specs(util=300))
    assert _frases(dif.diferencas(base['mesmo'], depois)) == ['A folha de spec deste formato mudou, e a peça ficou igual.']


def test_so_a_composicao_mudou(base):
    b = tif._briefing()
    b['composicoes'][1]['versao'] = 'reorganizado'
    depois = _corpo(b, 'perto', d=ap.copia(base['perto']['derivacao']))
    assert _frases(dif.diferencas(base['perto'], depois)) == [
        'A família deste formato mudou no briefing (versão, edições ou confirmação), e a peça ficou igual.']


def test_formato_novo_e_formato_que_saiu(base):
    assert _frases(dif.diferencas(None, base['perto'])) == ['O formato entrou no job.']
    assert _frases(dif.diferencas(base['perto'], None)) == ['O formato saiu do job.']
    assert dif.diferencas(None, None) == []


def test_derivacao_de_verdade_com_outra_funcao(base):
    # de ponta a ponta: o legal vira CTA no briefing e o formato e derivado de novo
    b = tif._briefing()
    tif._funcao(b, 40, 'cta')
    depois = _corpo(b, 'perto')
    itens = dif.diferencas(base['perto'], depois)
    assert itens and 'O texto legal agora é o CTA.' in _frases(itens)


def test_frases_seguem_as_regras_de_portugues(base):
    frases = []
    for c in base.values():
        for k in range(40):
            frases += _frases(dif.diferencas(c, _mexer(c, random.Random(k))))
    frases += [dif.ENTRADA_GERAL, dif.DETALHE_GERAL]
    assert frases
    for t in frases:
        assert '—' not in t and '–' not in t, t
        assert not t.startswith(('não é', 'Não é')) and ', é ' not in t, t
        assert t[0].isupper() or t[0].isdigit(), t
        assert t.endswith('.'), t
        assert '_' not in t, t


# ------------------------------------------------------------------ mudancas aleatorias
def _folhas(x, caminho=()):
    """Os caminhos de cada folha e de cada lista e dicionario do corpo."""
    yield caminho, x
    if isinstance(x, dict):
        for k, v in x.items():
            yield from _folhas(v, caminho + (k,))
    elif isinstance(x, list):
        for k, v in enumerate(x):
            yield from _folhas(v, caminho + (k,))


def _mexer(c, rnd):
    """Uma copia do corpo com uma mudanca aleatoria: numero, texto, booleano, nulo, item de lista ou chave."""
    novo = ap.copia(c)
    caminhos = [p for p, _v in _folhas(novo) if p]
    caminho = rnd.choice(caminhos)
    pai = novo
    for k in caminho[:-1]:
        pai = pai[k]
    chave, v = caminho[-1], pai[caminho[-1]]
    if isinstance(v, bool):
        pai[chave] = not v
    elif isinstance(v, (int, float)):
        pai[chave] = v + rnd.choice((1, -1, 0.5, 37))
    elif isinstance(v, str):
        pai[chave] = v + 'x'
    elif v is None:
        pai[chave] = 'x'
    elif isinstance(v, list):
        if v and rnd.random() < 0.5:
            v.pop(rnd.randrange(len(v)))
        else:
            v.append(ap.copia(v[0]) if v else 'x')
    elif isinstance(v, dict):
        if v and rnd.random() < 0.5:
            v.pop(rnd.choice(sorted(v, key=str)))
        else:
            v['chave_nova'] = 'x'
    return novo


def test_toda_mudanca_de_impressao_da_pelo_menos_um_item(base):
    rnd = random.Random(177)
    mudou = 0
    for _k in range(1500):
        c = base[rnd.choice(sorted(base))]
        novo = _mexer(c, rnd)
        itens = dif.diferencas(c, novo)
        if mi.do_corpo(novo) == mi.do_corpo(c):
            assert itens == []
        else:
            mudou += 1
            assert itens, novo
            assert all(i['frase'] for i in itens)
            assert dif.diferencas(novo, c), novo
    assert mudou > 1000
