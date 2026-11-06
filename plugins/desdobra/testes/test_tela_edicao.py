# -*- coding: utf-8 -*-
"""M7a, fatia 4: a edicao da composicao por familia no palco (decisoes-v1.md, 164, 166, 167, 168, 169 e 171).

Criterios de pronto cobertos aqui:
  - cada edicao do DA (mover, escalar, texto, apagar) vale para a familia inteira: o motor leva cada uma em proporcao a
    cada formato membro, refaz o encaixe com o solver do repositorio e devolve o palco de cada membro (as miniaturas
    antes da confirmacao); o formato devolvido parte da versao da galeria escolhida;
  - a intencao de alinhamento (168): bordas e centros quase iguais viram o mesmo valor (x=40 e x=43 ficam iguais; 30 px
    de diferenca ficam), o alinhamento do KV vence quando os dois ja estavam alinhados nele, e senao vence o elemento
    mexido por ultimo; a tolerancia e proporcional a peca e tem fonte;
  - o texto editado: a fonte do job precisa ter todos os caracteres (senao a recusa diz quais, em portugues), a previa
    leva o texto novo com a face real do job, e o texto vale so na familia onde foi editado (171);
  - o elemento apagado sai de todos os membros, fica registrado com origem da e deixa de reprovar a conferencia de
    inventario;
  - "Confirmar familia" e um ato da janela, de um clique com a confirmacao na propria janela: grava no rascunho a
    familia confirmada com a origem do Disparo; a pagina nunca confirma uma familia pelo rascunho, e mexer depois da
    confirmacao exige confirmar de novo;
  - o desempenho: uma edicao numa familia de 5 membros refaz o encaixe abaixo do alvo de latencia registrado;
  - a caixa das linhas juntadas (quebra por familia) acompanha a tinta medida no Chromium, como o render a desenha.
Tudo sintetico: o PSD de test_tela_palco e a fonte de autoteste do motor."""
import json
import time

import pytest

import test_derivacao_apoio as ap
import test_fontes_apoio as fap
import test_tela_escrita as tte
import test_tela_palco as tp
import test_tela_servidor as tts
from desdobra import humano, limites
from desdobra.briefing import modelo as mb
from desdobra.derivacao import quebras as mq
from desdobra.derivacao import validacao as mv
from desdobra.tela import atos as ta
from desdobra.tela import edicao as ed
from desdobra.tela import estado as te
from desdobra.tela import rascunho as tr
from desdobra.tela import servidor as ts

# cinco verticais de proporcao 2,0 a 1,74 (uma familia, derivacao.grupo_proporcao_dif_max) e um quadrado (outra)
VERTICAIS = [('v1', 160, 320), ('v2', 166, 320), ('v3', 172, 320), ('v4', 178, 320), ('v5', 184, 320)]
FORMATOS = [('mesma', 640, 320)] + VERTICAIS + [('quadrado', 320, 320)]


@pytest.fixture(scope='module')
def job_edicao(tmp_path_factory):
    from desdobra import contratos
    from desdobra.job import nucleo
    from desdobra.render import autoteste
    base = tmp_path_factory.mktemp('edicao')
    fontes = base / 'origem-fontes'
    fap.gravar(fontes, 'autoteste.ttf', autoteste.gerar_fonte())
    job = base / 'job'
    nucleo.criar(job, tp._psd_hostil(base / 'origem' / 'kv.psd', autoteste.NOME_PS), 'c', fontes=[fontes])
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    ids = {c['nome']: c['identidade']['layer_id'] for c in laudo['camadas']}
    funcoes = {ids['fundo-sintetico']: 'fundo', ids[tp.NOME_FORM]: 'titulo', ids['quadrado-sintetico']: 'logo_principal',
               ids[tp.NOME_APOIO]: 'texto_de_apoio', ids['solto-sintetico']: 'fora_da_peca'}
    b = ap.briefing(funcoes=funcoes, formatos=[ap.formato(i, w, h) for i, w, h in FORMATOS])
    b.pop('cabecalho')
    b.pop('job_id')
    arq = base / 'fixture.json'
    arq.write_text(json.dumps(b), encoding='utf-8')
    mb.importar_teste(job, arq)
    return job


@pytest.fixture(scope='module')
def conteudo(job_edicao):
    return te.montar(job_edicao)


def _familia_de(estado, fid):
    for o in estado['orientacoes']:
        for g in o['grupos']:
            if any(x['id'] == fid for co in g['composicoes'] for x in co['formatos']):
                return g['id']
    raise AssertionError(fid)


def _membros(estado, gid):
    return [x['id'] for o in estado['orientacoes'] for g in o['grupos'] if g['id'] == gid
            for co in g['composicoes'] for x in co['formatos']]


def _elemento(palco, funcao):
    return next(e for e in palco['elementos'] if e['funcao'] == funcao)


def _versao(conteudo, fid):
    return conteudo['previas'][fid]['galeria']['variantes'][0]['id']


# ------------------------------------------------------------------ a intencao de alinhamento (168), sem job
def test_tolerancia_do_alinhamento_tem_fonte_e_e_proporcional_a_peca():
    lim = limites.obter('derivacao.alinhamento_intencao_tolerancia')
    assert lim.fonte and lim.situacao == 'a_calibrar' and lim.efeito in ('registra', 'avisa')
    assert ed.tolerancia(1920, 1080) == pytest.approx(2 * ed.tolerancia(960, 540))
    assert ed.tolerancia(1920, 1080) == pytest.approx(lim.valor * 1920)


def test_x_40_e_43_ficam_iguais_e_vence_o_mexido_por_ultimo():
    caixas = {'titulo': [40.0, 100.0, 400.0, 160.0], 'apoio': [43.0, 200.0, 300.0, 240.0]}
    novas, alinhados = ed.normalizar(caixas, ['titulo'], 1920, 1080)
    # o titulo foi mexido por ultimo e fica onde o DA o pos; o apoio vem para o x dele, sem mudar de tamanho
    assert novas['titulo'] == caixas['titulo']
    assert novas['apoio'][0] == pytest.approx(40.0) and novas['apoio'][2] - novas['apoio'][0] == pytest.approx(257.0)
    assert novas['apoio'][1] == caixas['apoio'][1]
    assert alinhados and alinhados[0]['linha'] == 'esquerda'


def test_30_px_de_diferenca_e_intencao_do_da_e_fica():
    caixas = {'titulo': [40.0, 100.0, 400.0, 160.0], 'apoio': [70.0, 200.0, 300.0, 240.0]}
    novas, alinhados = ed.normalizar(caixas, ['titulo'], 1920, 1080)
    assert novas == caixas and alinhados == []


def test_alinhamento_do_kv_vence_quando_os_dois_ja_estavam_alinhados_nele():
    caixas = {'titulo': [40.0, 100.0, 400.0, 160.0], 'apoio': [43.0, 200.0, 300.0, 240.0]}
    kv = {'titulo': [20.0, 10.0, 200.0, 40.0], 'apoio': [20.0, 60.0, 150.0, 80.0]}
    novas, _a = ed.normalizar(caixas, ['titulo'], 1920, 1080, kv_caixas=kv, kv_tamanho=(960, 540))
    # no KV os dois tinham a mesma esquerda: o mexido volta para a linha do outro
    assert novas['apoio'] == caixas['apoio']
    assert novas['titulo'][0] == pytest.approx(43.0)


def test_alinhamento_do_kv_resolve_antes_e_nao_deixa_linha_quase_igual():
    # revisao do M7a: com tres elementos, o encaixe do mexido por ultimo nao pode ser desfeito depois pelo do KV
    kv = {'a': [100.0, 0.0, 200.0, 50.0], 'b': [500.0, 600.0, 600.0, 650.0], 'c': [100.0, 300.0, 200.0, 350.0]}
    caixas = {'a': [105.0, 0.0, 205.0, 50.0], 'b': [108.0, 600.0, 208.0, 650.0], 'c': [100.0, 300.0, 200.0, 350.0]}
    novas, _a = ed.normalizar(caixas, ['a'], 1000, 1000, kv_caixas=kv, kv_tamanho=(1000, 1000))
    assert novas['a'][0] == pytest.approx(100.0) and novas['c'] == caixas['c']
    tol = ed.tolerancia(1000, 1000)
    for o in ('b', 'c'):
        for nome in ('esquerda', 'centro', 'direita'):
            d = abs(ed._linha(novas['a'], 'x', nome) - ed._linha(novas[o], 'x', nome))
            assert d <= ed.IGUAL or d > tol, (o, nome, d)


def test_centros_tambem_alinham_e_so_um_eixo_por_vez():
    caixas = {'a': [100.0, 100.0, 300.0, 150.0], 'b': [94.0, 400.0, 314.0, 450.0]}
    novas, alinhados = ed.normalizar(caixas, ['a'], 1920, 1080)
    # o centro x de a e 200, o de b e 204 (as bordas a 6 e 14): o centro alinha, a diferenca menor, e o y fica
    assert (novas['b'][0] + novas['b'][2]) / 2 == pytest.approx(200.0)
    assert novas['b'][1] == caixas['b'][1]
    assert [x['linha'] for x in alinhados] == ['centro']


def test_mover_e_escalar_vao_em_proporcao_ao_formato():
    caixas = {'t': [10.0, 20.0, 110.0, 70.0]}
    edicoes = [{'elemento': 't', 'acao': 'mover', 'dx': 0.1, 'dy': -0.05},
               {'elemento': 't', 'acao': 'escalar', 'fator': 2.0, 'fx': 0.0, 'fy': 0.0}]
    a, _apag, _t, mexidos = ed.aplicar(caixas, edicoes, 200, 400)
    b, _apag, _t, _m = ed.aplicar(caixas, edicoes, 400, 800)
    assert a['t'] == pytest.approx([30.0, 0.0, 230.0, 100.0])
    assert b['t'] == pytest.approx([50.0, -20.0, 250.0, 80.0])
    assert mexidos == ['t']


# ------------------------------------------------------------------ inventario com elemento apagado pelo DA
def test_elemento_apagado_pelo_da_nao_reprova_o_inventario():
    kv = {'el1': {'caixa': [0, 0, 10, 10]}, 'el2': {'caixa': [20, 20, 30, 30]}}
    e = {'id': 'el1', 'sangra': {'esq': False, 'topo': False, 'dir': False, 'base': False}, 'caixa': [0, 0, 10, 10],
         'classe': 'texto', 'funcao': 'titulo', 'regra': None}
    sem = mv.validar((100, 100), {}, [e], [[0, 0, 10, 10]], [1.0], kv, {})
    assert next(v for v in sem if v['nome'] == 'inventario')['situacao'] == 'reprova'
    com = mv.validar((100, 100), {}, [e], [[0, 0, 10, 10]], [1.0], kv, {}, apagados=['el2'])
    inv = next(v for v in com if v['nome'] == 'inventario')
    assert inv['situacao'] == 'ok' and inv['medidas']['apagados_pelo_da'] == ['el2']


# ------------------------------------------------------------------ a familia no job sintetico
def test_mover_na_familia_vai_a_cada_membro_em_proporcao(conteudo):
    estado = conteudo['estado']
    gid = _familia_de(estado, 'v1')
    membros = _membros(estado, gid)
    assert sorted(membros) == sorted(f for f, _w, _h in VERTICAIS)
    vid = _versao(conteudo, 'v1')
    antes = conteudo['editar']({'familia': gid, 'versao': vid, 'edicoes': []})
    el = _elemento(antes['membros'][0]['palco'], 'titulo')['id']
    depois = conteudo['editar']({'familia': gid, 'versao': vid,
                                 'edicoes': [{'elemento': el, 'acao': 'mover', 'dx': 0.0, 'dy': 0.05}]})
    assert [m['formato'] for m in depois['membros']] == [m['formato'] for m in antes['membros']]
    assert sorted(m['formato'] for m in depois['membros']) == sorted(membros)
    for a, d in zip(antes['membros'], depois['membros']):
        ca = next(e for e in a['palco']['elementos'] if e['id'] == el)['caixa']
        cd = next(e for e in d['palco']['elementos'] if e['id'] == el)['caixa']
        # o encaixe pode segurar o elemento na area segura; dentro dela, o deslocamento e 5% da altura de cada membro
        assert cd[1] - ca[1] == pytest.approx(0.05 * d['palco']['altura'], abs=1.0), (d['formato'], ca, cd)
        assert d['palco']['selo'] == 'variante' and d['palco']['pecas']
    assert depois['tempo_ms'] >= 0


def test_previa_diz_o_alinhamento_que_a_tela_mostra(conteudo):
    # revisao do M7a: a seta e o + e - nao passam pelo encaixe do arraste; a previa diz, por formato, a linha em que a
    # ultima edicao encostou, para a tela desenhar a guia e avisar
    estado = conteudo['estado']
    gid = _familia_de(estado, 'v1')
    vid = _versao(conteudo, 'v1')
    antes = conteudo['editar']({'familia': gid, 'versao': vid, 'edicoes': []})
    m = next(x for x in antes['membros'] if x['formato'] == 'v1')['palco']
    t, logo = _elemento(m, 'titulo'), _elemento(m, 'logo_principal')
    dx = (logo['caixa'][2] - 1.0) - t['caixa'][2]  # numero-neutro: a 1 px da borda direita do logo
    r = conteudo['editar']({'familia': gid, 'versao': vid,
                            'edicoes': [{'elemento': t['id'], 'acao': 'mover', 'dx': dx / m['largura'], 'dy': 0.0}]})
    assert any(a['formato'] == 'v1' and t['id'] in a['elementos'] and a['eixo'] == 'x' and
               isinstance(a['valor'], float) for a in r['alinhados']), r['alinhados']


def test_edicao_de_uma_familia_nao_mexe_nas_outras(conteudo):
    estado = conteudo['estado']
    gid_v, gid_q = _familia_de(estado, 'v1'), _familia_de(estado, 'quadrado')
    assert gid_v != gid_q
    vq = _versao(conteudo, 'quadrado')
    sem = conteudo['editar']({'familia': gid_q, 'versao': vq, 'edicoes': []})
    el = _elemento(sem['membros'][0]['palco'], 'texto_de_apoio')['id']
    conteudo['editar']({'familia': gid_v, 'versao': _versao(conteudo, 'v1'),
                        'edicoes': [{'elemento': el, 'acao': 'texto', 'texto': 'HAH'}]})
    de_novo = conteudo['editar']({'familia': gid_q, 'versao': vq, 'edicoes': []})
    assert de_novo['membros'][0]['palco'] == sem['membros'][0]['palco']


def test_texto_editado_vai_com_a_face_do_job_e_so_na_familia(conteudo):
    estado = conteudo['estado']
    gid = _familia_de(estado, 'v1')
    vid = _versao(conteudo, 'v1')
    base = conteudo['editar']({'familia': gid, 'versao': vid, 'edicoes': []})
    el = _elemento(base['membros'][0]['palco'], 'texto_de_apoio')['id']
    r = conteudo['editar']({'familia': gid, 'versao': vid,
                            'edicoes': [{'elemento': el, 'acao': 'texto', 'texto': 'HAH\nVOX'}]})
    assert r['recusas'] == []
    assert [x['elemento'] for x in r['textos_editados']] == [el]
    for m in r['membros']:
        pecas = [p for p in m['palco']['pecas'] if p['elemento'] == el and p['tipo'] == 'texto']
        assert pecas and all(p['texto_editado'] for p in pecas)
        linhas = [''.join(t['texto'] for t in ln['trechos']) for ln in pecas[0]['linhas']]
        assert linhas == ['HAH', 'VOX']
        faces = {t['face'] for ln in pecas[0]['linhas'] for t in ln['trechos']}
        assert faces and None not in faces and faces <= {f['id'] for f in estado['fontes']}


def test_texto_com_caractere_que_a_fonte_nao_tem_e_recusado_com_motivo_claro(conteudo):
    estado = conteudo['estado']
    gid = _familia_de(estado, 'v1')
    vid = _versao(conteudo, 'v1')
    base = conteudo['editar']({'familia': gid, 'versao': vid, 'edicoes': []})
    el = _elemento(base['membros'][0]['palco'], 'texto_de_apoio')['id']
    r = conteudo['editar']({'familia': gid, 'versao': vid,
                            'edicoes': [{'elemento': el, 'acao': 'texto', 'texto': 'HAÇ'}]})
    assert [x['elemento'] for x in r['recusas']] == [el]
    texto = r['recusas'][0]['texto']
    assert 'Ç' in texto and 'fonte' in texto and '—' not in texto and '–' not in texto
    assert r['textos_editados'] == []
    # a previa fica com o texto do KV: a edicao recusada nao entra
    for m in r['membros']:
        assert not any(p.get('texto_editado') for p in m['palco']['pecas'])


def test_apagar_tira_o_elemento_de_todos_os_membros_com_origem_da(conteudo):
    estado = conteudo['estado']
    gid = _familia_de(estado, 'v1')
    vid = _versao(conteudo, 'v1')
    base = conteudo['editar']({'familia': gid, 'versao': vid, 'edicoes': []})
    el = _elemento(base['membros'][0]['palco'], 'logo_principal')['id']
    r = conteudo['editar']({'familia': gid, 'versao': vid, 'edicoes': [{'elemento': el, 'acao': 'apagar'}]})
    assert [(x['elemento'], x['origem']) for x in r['apagados']] == [(el, 'da')]
    assert r['apagados'][0]['nome']
    for m in r['membros']:
        assert el not in {e['id'] for e in m['palco']['elementos']}
        assert el not in {p['elemento'] for p in m['palco']['pecas']}
        assert not any(f['codigo'] == 'validacao_reprova' and 'inventario' in f.get('texto', '') for f in m['falhas'])
        assert 'inventario' not in m['validacoes_reprovadas']
    teste = conteudo['editar']({'familia': gid, 'versao': vid, 'edicoes': [{'elemento': el, 'acao': 'apagar'}]},
                               origem=mb.ORIGEM_FIXTURE)
    assert teste['apagados'][0]['origem'] == mb.ORIGEM_FIXTURE


@pytest.mark.parametrize('dados', [
    {'familia': 'nao-existe', 'versao': None, 'edicoes': []},
    {'familia': None, 'versao': None, 'edicoes': []},
    {'versao': None, 'edicoes': []},
    {'familia': 'F', 'versao': None, 'edicoes': [{'elemento': 'el999', 'acao': 'apagar'}]},
    {'familia': 'F', 'versao': None, 'edicoes': [{'elemento': 'x', 'acao': 'girar'}]},
    {'familia': 'F', 'versao': None, 'edicoes': [{'elemento': 'x', 'acao': 'escalar', 'fator': -1}]},
    {'familia': 'F', 'versao': 'nao-existe', 'edicoes': []},
    {'familia': 'F', 'versao': None, 'edicoes': [], 'extra': 1},
])
def test_previa_recusa_dado_fora_do_formato(conteudo, dados):
    gid = _familia_de(conteudo['estado'], 'v1')
    dados = json.loads(json.dumps(dados).replace('"F"', json.dumps(gid)))
    assert conteudo['editar'](dados) is None


def test_desempenho_edicao_numa_familia_de_5_membros(conteudo):
    estado = conteudo['estado']
    gid = _familia_de(estado, 'v1')
    assert len(_membros(estado, gid)) == 5  # numero-neutro: o caso do criterio
    vid = _versao(conteudo, 'v1')
    base = conteudo['editar']({'familia': gid, 'versao': vid, 'edicoes': []})
    el = _elemento(base['membros'][0]['palco'], 'titulo')['id']
    alvo = float(limites.valor('tela.previa_latencia_alvo_ms'))
    lim = limites.obter('tela.previa_latencia_alvo_ms')
    assert lim.fonte and lim.situacao == 'a_calibrar'
    tempos = []
    for k in range(3):  # numero-neutro: tres edicoes seguidas
        t0 = time.perf_counter()
        r = conteudo['editar']({'familia': gid, 'versao': vid,
                                'edicoes': [{'elemento': el, 'acao': 'mover', 'dx': 0.01 * k, 'dy': 0.0},
                                            {'elemento': el, 'acao': 'escalar', 'fator': 1.1}]})
        tempos.append((time.perf_counter() - t0) * 1000.0)  # numero-neutro: ms
        assert len(r['membros']) == 5  # numero-neutro: o caso do criterio
    assert min(tempos) < alvo, tempos


# ------------------------------------------------------------------ Confirmar familia: ato da janela e rascunho
def _servidor(job, conteudo, teste=True):
    return ts.ServidorTela(conteudo, pasta=job, modo_teste=teste,
                           atos=ta.atos_do_job(job, conteudo=conteudo)).iniciar()


def _confirmar(s, biscoito, dados):
    if 'edicoes' not in dados:  # a janela manda as edicoes que mostra: as do rascunho gravado
        gravado, _o = tr.ler(s.pasta, s.laudo_sha256)
        dados = dict(dados, edicoes=(((gravado or {}).get('familias') or {}).get(dados['familia']) or {}).get(
            'edicoes') or [])
    codigo, p = tte._pedir_ato(s, biscoito, nome='familia', dados=dados)
    if codigo != 200:
        return codigo, None, None
    c2 = tte._escrever(s, '/api/ato/confirmar', {'pedido': p['pedido'], 'resposta': 'confirmar'}, cookie=biscoito)[0]
    return codigo, c2, p


def _escolher(s, biscoito, gid, versao):
    """O clique do DA numa versao da galeria, como a pagina grava no rascunho."""
    corpo = {'job_id': s.job_id, 'laudo_sha256': s.laudo_sha256,
             'familias': {gid: {'versao': versao, 'confirmada': False, 'edicoes': []}}}
    return tte._escrever(s, '/api/rascunho', corpo, cookie=biscoito)[0]


def _limpar_rascunho(job):
    arq = job / tr.ARQUIVO
    if arq.exists():
        arq.unlink()


def test_confirmar_familia_grava_no_rascunho_com_a_origem_do_disparo(job_edicao, conteudo):
    _limpar_rascunho(job_edicao)
    gid = _familia_de(conteudo['estado'], 'v1')
    vid = _versao(conteudo, 'v1')
    s = _servidor(job_edicao, conteudo)
    try:
        biscoito = tts._entrar(s)
        # revisao do M7a: sem a versao clicada pelo DA (gravada no rascunho), a familia com galeria nao se confirma
        assert _confirmar(s, biscoito, {'familia': gid, 'versao': vid})[0] == 403
        outra = next(v for v in conteudo['familias'][gid]['versoes'] if v != vid)
        assert _escolher(s, biscoito, gid, outra) == 200
        assert _confirmar(s, biscoito, {'familia': gid, 'versao': vid})[0] == 403
        assert _escolher(s, biscoito, gid, vid) == 200
        codigo, c2, p = _confirmar(s, biscoito, {'familia': gid, 'versao': vid})
        assert codigo == 200 and c2 == 200
        assert 'arquivos desta família ficam confirmados' in p['texto'] and '—' not in p['texto'] and p['sim'] == 'Confirmar'
        # revisao do M7a: o dialogo diz qual versao da galeria fica confirmada
        gal = next(conteudo['previas'][x]['galeria'] for x in conteudo['familias'][gid]['formatos']
                   if conteudo['previas'][x].get('galeria'))
        ordem = next(v['ordem'] for v in gal['variantes'] if v['id'] == vid)
        assert ('na versão %s,' % ordem) in p['texto']
        r = json.loads((job_edicao / tr.ARQUIVO).read_text(encoding='utf-8'))
        f = r['familias'][gid]
        assert f['confirmada'] is True and f['versao'] == vid
        assert f['confirmacao']['origem'] == mb.ORIGEM_FIXTURE and f['confirmacao']['meio'] == humano.MEIO_MEDICAO
        # versao que a familia nao tem, ou familia que nao existe: recusado antes do dialogo
        assert _confirmar(s, biscoito, {'familia': gid, 'versao': 'nao-existe'})[0] == 403
        assert _confirmar(s, biscoito, {'familia': 'nao-existe', 'versao': None})[0] == 403
    finally:
        s.parar()
        _limpar_rascunho(job_edicao)


def test_pagina_nunca_confirma_familia_pelo_rascunho(job_edicao, conteudo):
    _limpar_rascunho(job_edicao)
    gid = _familia_de(conteudo['estado'], 'v1')
    vid = _versao(conteudo, 'v1')
    s = _servidor(job_edicao, conteudo)
    try:
        biscoito = tts._entrar(s)

        def gravar(familia):
            corpo = {'job_id': s.job_id, 'laudo_sha256': s.laudo_sha256, 'familias': {gid: familia}}
            return tte._escrever(s, '/api/rascunho', corpo, cookie=biscoito)[0]
        # confirmada pela pagina, sem o ato: recusado
        assert gravar({'versao': vid, 'confirmada': True, 'edicoes': []}) == 403
        assert not (job_edicao / tr.ARQUIVO).exists()
        # pelo ato, e depois a pagina regrava igual (mantem) ou mexe (tem de voltar a pedir confirmacao)
        assert gravar({'versao': vid, 'confirmada': False, 'edicoes': []}) == 200
        assert _confirmar(s, biscoito, {'familia': gid, 'versao': vid})[1] == 200
        assert gravar({'versao': vid, 'confirmada': True, 'edicoes': []}) == 200
        lido = json.loads((job_edicao / tr.ARQUIVO).read_text(encoding='utf-8'))['familias'][gid]
        assert lido['confirmada'] and lido['confirmacao']['origem'] == mb.ORIGEM_FIXTURE
        mexe = [{'elemento': 'el1', 'acao': 'mover', 'dx': 0.01, 'dy': 0.0}]
        assert gravar({'versao': vid, 'confirmada': True, 'edicoes': mexe}) == 403
        assert gravar({'versao': vid, 'confirmada': False, 'edicoes': mexe}) == 200
        lido = json.loads((job_edicao / tr.ARQUIVO).read_text(encoding='utf-8'))['familias'][gid]
        assert lido['confirmada'] is False and 'confirmacao' not in lido
        # a pagina nao forja a confirmacao
        forjada = {'versao': vid, 'confirmada': False, 'edicoes': mexe,
                   'confirmacao': {'origem': 'da', 'meio': 'tela', 'em': '2026-11-05T10:00:00'}}
        assert gravar(forjada) == 200
        lido = json.loads((job_edicao / tr.ARQUIVO).read_text(encoding='utf-8'))['familias'][gid]
        assert 'confirmacao' not in lido
    finally:
        s.parar()
        _limpar_rascunho(job_edicao)


def test_rota_da_previa_da_familia_pede_o_caminho_de_escrita(job_edicao, conteudo):
    gid = _familia_de(conteudo['estado'], 'v1')
    s = _servidor(job_edicao, conteudo)
    try:
        biscoito = tts._entrar(s)
        dados = {'familia': gid, 'versao': _versao(conteudo, 'v1'), 'edicoes': []}
        assert tte._escrever(s, '/api/familia/previa', dados, cookie=biscoito, csrf=False)[0] == 403
        assert tte._escrever(s, '/api/familia/previa', dados, cookie=None)[0] == 404
        codigo, _cab, corpo = tts._pedir(s, '/api/familia/previa', metodo='GET', cookie=biscoito)[:3]
        assert codigo == 404
        codigo, _cab, r = tte._escrever(s, '/api/familia/previa', dados, cookie=biscoito)
        assert codigo == 200
        assert len(json.loads(r)['membros']) == 5  # numero-neutro: os cinco verticais
        assert tte._escrever(s, '/api/familia/previa', {'familia': 'x'}, cookie=biscoito)[0] == 403
        assert not (job_edicao / tr.ARQUIVO).exists()  # a previa nao grava nada
    finally:
        s.parar()


# ------------------------------------------------------------------ a caixa das linhas juntadas
def test_caixa_das_linhas_juntadas_segue_a_tinta_medida():
    """No corpus, a caixa da derivacao das linhas juntadas saia uns 21 px mais baixa que a tinta do render: a altura
    so tirava as entrelinhas, e a linha juntada pode ter acento ou descendente que a ultima linha da mestre nao tinha.
    Com a tinta de cada linha medida no Chromium (subida, descida, esquerda e direita da tinta, no espaco de texto), a
    caixa segue a tinta da origem: topo pela subida da primeira linha, base pela descida da ultima, largura pela tinta
    da linha mais larga."""
    camada = {'texto': {'conteudo': 'AB\rCD\rEF', 'justificacao': 'LEFT', 'matriz': [2.0, 0.0, 0.0, 2.0, 0.0, 0.0],
                        'runs': [{'inicio': 0, 'fim': 8, 'texto': 'AB\rCD\rEF', 'entrelinha_efetiva_px': 40.0}]}}
    caixa = [100.0, 50.0, 200.0, 170.0]  # tinta da mestre: 3 linhas
    antiga = {'largura_texto_mestre': 50.0, 'largura_texto': 100.0}
    c0 = mq.caixa_medida(camada, caixa, [1], antiga)  # sem a tinta medida: a conta de antes
    assert c0 == pytest.approx([100.0, 50.0, 300.0, 130.0])
    medida = dict(antiga, tinta_mestre={'esq': 1.0, 'dir': 49.0, 'sobe': 9.0, 'desce': 1.0},
                  tinta={'esq': 1.0, 'dir': 99.0, 'sobe': 10.0, 'desce': 4.0})
    c1 = mq.caixa_medida(camada, caixa, [1], medida)
    # largura: 100 de tinta da mestre mais (99 - 49) x 2; topo sobe 1 x 2; base: a descida passa de 1 para 4 (x 2)
    assert c1 == pytest.approx([100.0, 48.0, 200.0 + 100.0, 136.0])
    assert c1[3] - c1[1] > c0[3] - c0[1]


def test_caixa_das_linhas_juntadas_usa_a_escala_y_no_alto():
    # revisao do M7a: camada de texto com escala diferente em x e y (transformacao livre no Photoshop)
    camada = {'texto': {'conteudo': 'AB\rCD\rEF', 'justificacao': 'LEFT', 'matriz': [2.0, 0.0, 0.0, 3.0, 0.0, 0.0],
                        'runs': [{'inicio': 0, 'fim': 8, 'texto': 'AB\rCD\rEF', 'entrelinha_efetiva_px': 40.0}]}}
    caixa = [100.0, 50.0, 200.0, 170.0]
    medida = {'largura_texto_mestre': 50.0, 'largura_texto': 100.0,
              'tinta_mestre': {'esq': 1.0, 'dir': 49.0, 'sobe': 9.0, 'desce': 1.0},
              'tinta': {'esq': 1.0, 'dir': 99.0, 'sobe': 10.0, 'desce': 4.0}}
    c = mq.caixa_medida(camada, caixa, [1], medida)
    # x pela escala x (2), topo e base pela escala y (3)
    assert c == pytest.approx([100.0, 47.0, 300.0, 139.0])


# ------------------------------------------------------------------ a tela no Chromium sem janela (modo de teste)
def _rascunho_gravado(job):
    arq = job / tr.ARQUIVO
    return json.loads(arq.read_text(encoding='utf-8')) if arq.exists() else None


def _esperar_salvo(pg):
    tp._esperar(pg, '() => (document.documentElement.dataset.rascunho === "salvo"'
                    ' && document.documentElement.dataset.previa === "pronta") ? "1" : ""')


def _focar(pg, eid):
    pg.evaluate('i => document.querySelector(\'#palco .rotulo[data-elemento="\' + i + \'"]\').focus()', eid)


def _quantos_no_palco(pg, eid):
    return pg.evaluate('i => document.querySelectorAll(\'#palco .rotulo[data-elemento="\' + i + \'"]\').length', eid)


def test_edicao_da_familia_no_chromium(job_edicao, conteudo):
    from playwright.sync_api import sync_playwright

    import test_tela_galeria as tg
    from desdobra.chromium import navegador
    _limpar_rascunho(job_edicao)
    estado = conteudo['estado']
    gid = _familia_de(estado, 'v1')
    base = conteudo['editar']({'familia': gid, 'versao': None, 'edicoes': []})
    palco0 = base['membros'][0]['palco']
    titulo = _elemento(palco0, 'titulo')['id']
    logo = _elemento(palco0, 'logo_principal')['id']
    apoio = _elemento(palco0, 'texto_de_apoio')['id']
    navegador.apontar_playwright()
    with ts.ServidorTela(conteudo, pasta=job_edicao, modo_teste=True,
                         atos=ta.atos_do_job(job_edicao, conteudo=conteudo)) as srv, sync_playwright() as pw:
        nav, pg = tp._pagina_da_tela(pw, srv, 2048, 720)  # numero-neutro: a tela do Duda (decisao 157)
        try:
            tg._abrir(pg, estado, 'v1')
            tp._esperar(pg, '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""')
            # as miniaturas de cada arquivo da familia, desenhadas pelo motor, antes de qualquer edicao
            membros = pg.evaluate('() => Array.from(document.querySelectorAll("#membros-lista .membro")).map(b => '
                                  '[b.dataset.formato, b.querySelectorAll(".peca").length])')
            assert sorted(m[0] for m in membros) == sorted(f for f, _w, _h in VERTICAIS)
            assert all(m[1] > 0 for m in membros), membros
            assert not pg.evaluate('() => document.getElementById("barra-edicao").hidden')
            # revisao do M7a: a versao que a tela mostra sozinha nao e escolha do DA; sem clique nem edicao, nada a
            # confirmar
            assert pg.evaluate('() => document.getElementById("confirmar-familia").disabled') is True
            assert _rascunho_gravado(job_edicao) is None  # abrir e ver nao grava nada
            # teclado: escolher o titulo e descer 3 vezes com Shift (10 px cada): uma edicao so, na familia
            _focar(pg, titulo)
            pg.keyboard.press('Enter')
            assert pg.evaluate('() => document.querySelector("#palco .rotulo.selecionado").dataset.elemento') == titulo
            for _ in range(3):  # numero-neutro: tres toques
                pg.keyboard.press('Shift+ArrowDown')
            _esperar_salvo(pg)
            f = _rascunho_gravado(job_edicao)['familias'][gid]
            assert [e['acao'] for e in f['edicoes']] == ['mover'] and f['edicoes'][0]['elemento'] == titulo
            assert f['edicoes'][0]['dy'] == pytest.approx(30.0 / 320, abs=1e-4) and f['confirmada'] is False
            assert f['versao'] in conteudo['familias'][gid]['versoes']
            # a edicao sobre a versao do palco e escolha do DA: a familia ja pode ser confirmada
            assert pg.evaluate('() => document.getElementById("confirmar-familia").disabled') is False
            # revisao do M7a: a seta passa pelo alinhamento do desdobra; quando ele encosta a edicao na linha de outro
            # elemento, a guia fica no palco e a tela avisa, senao nada aparece
            tp._esperar(pg, '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""')
            r = conteudo['editar']({'familia': gid, 'versao': f['versao'], 'edicoes': f['edicoes']})
            alinhou = any(a['formato'] == 'v1' and titulo in a['elementos'] for a in r['alinhados'])
            assert (pg.evaluate('() => document.querySelectorAll("#palco .guia").length') > 0) == alinhou
            assert ('Ficou alinhado' in pg.evaluate('() => document.getElementById("ed-mensagem").textContent')) == \
                alinhou
            assert pg.evaluate('() => document.activeElement.dataset.elemento') == titulo
            assert 'proposta, não aprovada' in pg.evaluate('() => document.getElementById("selo-palco").textContent')
            # arrastar com o mouse: mais uma edicao, so ao soltar
            caixa = pg.evaluate('i => { const r = document.querySelector(\'#palco .rotulo[data-elemento="\' + i + \'"]\')'
                                '.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }', titulo)
            pg.mouse.move(caixa[0], caixa[1])
            pg.mouse.down()
            pg.mouse.move(caixa[0] + 20, caixa[1], steps=4)  # numero-neutro: 20 px de tela
            assert len(_rascunho_gravado(job_edicao)['familias'][gid]['edicoes']) == 1
            pg.mouse.up()
            _esperar_salvo(pg)
            assert len(_rascunho_gravado(job_edicao)['familias'][gid]['edicoes']) == 2  # numero-neutro: duas edicoes
            # apagar o logo: sai de todos os arquivos, a tela diz o que foi tirado, Desfazer traz de volta
            _focar(pg, logo)
            pg.keyboard.press('Delete')
            _esperar_salvo(pg)
            assert 'Tirado desta família' in pg.evaluate('() => document.getElementById("resumo-edicao").textContent')
            assert _quantos_no_palco(pg, logo) == 0
            pg.evaluate('() => document.getElementById("ed-desfazer").click()')
            _esperar_salvo(pg)
            assert _quantos_no_palco(pg, logo) == 1
            # revisao do M7a: Ctrl+Z desfaz pelo teclado, como Desfazer
            _focar(pg, logo)
            pg.keyboard.press('Delete')
            _esperar_salvo(pg)
            assert _quantos_no_palco(pg, logo) == 0
            pg.keyboard.press('Control+z')
            _esperar_salvo(pg)
            assert _quantos_no_palco(pg, logo) == 1
            # texto: o caractere que a fonte nao tem e recusado no proprio editor; o aceito vai ao palco
            _focar(pg, apoio)
            pg.keyboard.press('Enter')
            zoom = '() => parseInt(document.getElementById("medida-palco").textContent.split("em ")[1], 10)'
            sem_editor = pg.evaluate(zoom)
            pg.evaluate('() => document.getElementById("ed-texto").click()')
            assert not pg.evaluate('() => document.getElementById("editor-texto").hidden')
            # revisao do M7a: com o editor aberto, o palco fica com o espaco (sem miniaturas, so a etiqueta do
            # escolhido) e o texto ainda se le; Esc fecha o editor sem mudar nada
            pg.wait_for_timeout(300)  # numero-neutro: ms para o palco se ajustar ao espaco novo
            visiveis = pg.evaluate('() => Array.from(document.querySelectorAll("#palco .rotulo .etiqueta"))'
                                   '.filter(e => getComputedStyle(e).display !== "none").length')
            assert visiveis <= 1, visiveis
            assert pg.evaluate('() => getComputedStyle(document.getElementById("membros")).display') == 'none'
            assert pg.evaluate(zoom) >= sem_editor * 0.6, (pg.evaluate(zoom), sem_editor)
            pg.keyboard.press('Escape')
            assert pg.evaluate('() => document.getElementById("editor-texto").hidden')
            pg.evaluate('() => document.getElementById("ed-texto").click()')
            pg.fill('#ed-campo-texto', 'HAÇ')
            pg.evaluate('() => document.getElementById("ed-texto-aplicar").click()')
            tp._esperar(pg, '() => document.getElementById("ed-erro-texto").textContent ? "1" : ""')
            assert 'Ç' in pg.evaluate('() => document.getElementById("ed-erro-texto").textContent')
            pg.fill('#ed-campo-texto', 'HAH')
            pg.evaluate('() => document.getElementById("ed-texto-aplicar").click()')
            tp._esperar(pg, '() => document.getElementById("editor-texto").hidden ? "1" : ""')
            _esperar_salvo(pg)
            assert pg.evaluate('() => document.querySelectorAll("#palco .texto.editado").length') >= 1
            assert 'Texto editado nesta família' in pg.evaluate(
                '() => document.getElementById("resumo-edicao").textContent')
            edicoes = _rascunho_gravado(job_edicao)['familias'][gid]['edicoes']
            assert [e['texto'] for e in edicoes if e['acao'] == 'texto'] == ['HAH']
            # Confirmar familia: a confirmacao na janela, sem opcao marcada; o selo muda
            pg.evaluate('() => document.getElementById("confirmar-familia").click()')
            tp._esperar(pg, '() => document.getElementById("confirmacao").open ? "1" : ""')
            assert pg.evaluate('() => document.activeElement.tagName') != 'BUTTON'
            assert '5 arquivos' in pg.evaluate('() => document.getElementById("confirmacao-texto").textContent')
            pg.evaluate('''() => Array.from(document.querySelectorAll("#confirmacao button"))
                .find(b => b.textContent === "Confirmar").click()''')
            tp._esperar(pg, '() => document.documentElement.dataset.estadoAto === "feito" ? "1" : ""')
            f = _rascunho_gravado(job_edicao)['familias'][gid]
            assert f['confirmada'] is True and f['confirmacao']['origem'] == mb.ORIGEM_FIXTURE
            assert pg.evaluate('() => document.getElementById("selo-palco").textContent') == 'Família confirmada'
            assert pg.evaluate('() => document.getElementById("confirmar-familia").disabled') is True
            # mexer depois da confirmacao: a familia volta a pedir confirmacao
            _focar(pg, titulo)
            pg.keyboard.press('ArrowRight')
            _esperar_salvo(pg)
            assert _rascunho_gravado(job_edicao)['familias'][gid]['confirmada'] is False
            assert pg.evaluate('() => document.getElementById("confirmar-familia").disabled') is False
            # pela seta, o titulo para 2 px antes da borda direita que ele divide com o logo e o apoio no KV: o
            # desdobra alinha de novo, e a tela mostra a guia e avisa (revisao do M7a)
            f = _rascunho_gravado(job_edicao)['familias'][gid]
            largura = next(x for x in conteudo['editar']({'familia': gid, 'versao': f['versao'], 'edicoes': []})[
                'membros'] if x['formato'] == 'v1')['palco']['largura']
            andou = sum(e['dx'] for e in f['edicoes'] if e['acao'] == 'mover' and e['elemento'] == titulo) * largura
            for _ in range(int(round(andou)) + 2):  # numero-neutro: 2 px antes da linha, dentro da tolerancia
                pg.keyboard.press('ArrowLeft')
            _esperar_salvo(pg)
            tp._esperar(pg, '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""')
            f = _rascunho_gravado(job_edicao)['familias'][gid]
            r = conteudo['editar']({'familia': gid, 'versao': f['versao'], 'edicoes': f['edicoes']})
            assert any(a['formato'] == 'v1' and titulo in a['elementos'] for a in r['alinhados'])
            assert pg.evaluate('() => document.querySelectorAll("#palco .guia").length') > 0
            assert 'Ficou alinhado' in pg.evaluate('() => document.getElementById("ed-mensagem").textContent')
            texto = pg.evaluate(tp.JS_TEXTO_DA_MOLDURA)
            assert not tp.IDENTIFICADOR.findall(texto), tp.IDENTIFICADOR.findall(texto)
            assert '—' not in texto and '–' not in texto
            assert pg.evaluate('() => document.querySelectorAll("form, [onerror]").length') == 0
        finally:
            nav.close()
        contagem = dict(srv.contagem)
    assert contagem['proibido'] == 0 and contagem['csrf_recusado'] == 0 and contagem['dado_recusado'] == 0
    _limpar_rascunho(job_edicao)


# ------------------------------------------------------------------ revisao do M7a: texto da tela
def test_texto_da_tela_nao_fala_em_motor():
    """Quem le a tela e designer: a tela fala em "o desdobra", nunca no motor."""
    import re
    from desdobra.tela import estatico
    for motivo in list(te.MOTIVOS_TELA) + ['outro']:
        for n in (None, 0, 1, 4):  # numero-neutro: sem galeria, vazia, uma e quatro versoes
            assert 'motor' not in te.texto_da_devolucao(motivo, n).lower(), (motivo, n)
    html = (estatico.PASTA_TELA / 'tela.html').read_text(encoding='utf-8')
    visivel = re.sub(r'<[^>]+>', ' ', re.sub(r'<!--.*?-->', ' ', html, flags=re.S))
    assert 'motor' not in visivel.lower()
    js = (estatico.PASTA_TELA / 'tela.js').read_text(encoding='utf-8')
    sem_comentarios = re.sub(r'/\*.*?\*/', ' ', js, flags=re.S)
    sem_comentarios = re.sub(r'(?m)^\s*//.*$|\s//\s.*$', ' ', sem_comentarios)
    textos = re.findall(r"'([^'\\]*(?:\\.[^'\\]*)*)'", sem_comentarios)
    assert not [t for t in textos if re.search(r'\bmotor\b', t, re.I)]
    assert 'data:,' not in html and 'Faltam confirmar' not in js
    # revisao do M7a: a lista do que falta e o que a tela diz quando nao abre tambem
    from desdobra import tela
    devolvido = {'situacao': 'devolvido', 'devolucao': {'motivo': 'outro'}}
    # o passo 1 da revisao do M7a: sem formato (com e sem folha), a prancheta e o giro sem escolha
    for formatos, folhas in (([], 0), ([], 1), ([{'id': 'v1', 'rotacao': None}], 1)):
        lido_ = {'modo_dados': {'escolhido': 'c'}, 'bloqueios': [], 'paradas': [], 'camadas_bloqueadas': [],
                 'linkados': [], 'specs': {'pendentes': 0, 'formatos': formatos, 'folhas': folhas},
                 'quadros': [{'id': 'q1', 'escolhido': False}], 'fontes_que_faltam': []}
        for n in (0, 3):  # numero-neutro: sem versoes e com tres
            for item in te.faltam(lido_, {'v1': devolvido}, {'v1': n}):
                assert not re.search(r'\bmotor\b', item['texto'] + item['detalhe'], re.I), item['texto']
    assert not [t for t in tela.O_QUE_FAZER_RECUSA.values() if re.search(r'\bmotor\b', t, re.I)]


def test_tela_chama_o_grupo_de_familia_e_nunca_de_composicao():
    """Revisao do M7a: na tela, o grupo de proporcao parecida e a familia, e cada formato dela e um arquivo; a palavra
    composicao, que dizia as duas coisas, sai do que o designer le."""
    import re
    from desdobra.tela import estatico
    html = (estatico.PASTA_TELA / 'tela.html').read_text(encoding='utf-8')
    sem_comentarios_html = re.sub(r'<!--.*?-->', ' ', html, flags=re.S)
    visivel = re.sub(r'<[^>]+>', ' ', sem_comentarios_html)
    rotulos = re.findall(r'(?:aria-label|title|alt)="([^"]*)"', sem_comentarios_html)
    assert not [t for t in [visivel] + rotulos if re.search(r'composi', t, re.I)]
    js = (estatico.PASTA_TELA / 'tela.js').read_text(encoding='utf-8')
    sem_comentarios = re.sub(r'/\*.*?\*/', ' ', js, flags=re.S)
    sem_comentarios = re.sub(r'(?m)^\s*//.*$|\s//\s.*$', ' ', sem_comentarios)
    textos = re.findall(r"'([^'\\]*(?:\\.[^'\\]*)*)'", sem_comentarios)
    assert not [t for t in textos if re.search(r'composi[cç][aã]o\b|composi[cç][oõ]es\b', t, re.I)
                and ' ' in t]
    for motivo in list(te.MOTIVOS_TELA) + ['outro']:
        for n in (None, 0, 1, 4):  # numero-neutro: sem galeria, vazia, uma e quatro versoes
            assert 'composi' not in te.texto_da_devolucao(motivo, n).lower(), (motivo, n)
    assert 'composi' not in (te.PROPOSTA_DEPOIS + te.SEM_VERSOES).lower()


def test_icone_da_aba_vem_do_servidor_sem_quebrar_a_csp():
    """O icone data: quebrava a CSP img-src 'self' (erro no console a cada abertura): vem de uma rota da tela."""
    from desdobra.tela import estatico
    pagina = (estatico.PASTA_TELA / 'tela.html').read_text(encoding='utf-8')
    assert 'href="/icone.svg"' in pagina and 'data:,' not in pagina
    s = ts.ServidorTela(tts._conteudo()).iniciar()
    try:
        biscoito = tts._entrar(s)
        codigo, cab, corpo = tts._pedir(s, '/icone.svg', cookie=biscoito)[:3]
        assert codigo == 200 and cab['content-type'][0].startswith('image/svg+xml') and corpo.startswith(b'<svg')
    finally:
        s.parar()
