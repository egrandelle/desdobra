# -*- coding: utf-8 -*-
"""A familia segue o arquivo de edicao, da previa ao "Salvar e seguir" (decisao 199; etapa E4 do desenho da familia).

O DA edita so o arquivo de edicao (o maior da familia, em pe) pelas rotas da tela, como test_tela_previa_igual_ao_salvar
faz; os outros arquivos copiam o layout aprovado nele (desdobra.derivacao.proposta.layout_da_familia), e a previa e a
derivacao gravada sao a mesma conta. Criterios:
  - o KV da diagonal (sinteticos.kv_diagonal, a geometria do caso de 18/11) com os formatos 1080x1080, 970x250,
    1080x1920, 300x600, g1920x1080r270 e g640x360r90: nenhum arquivo com sobreposicao nem fora do formato; a
    assinatura do 300x600 no branco, livre do azul com a folga do aprovado x s; previa = derivacao (0,00 px); o
    registro transferencia gravado;
  - a regressao do repro B (KV A): o titulo do 300x600 com no maximo 0,95 da largura e o logo na linha da margem;
  - a area segura do arquivo girado medida na composicao, em pe;
  - a familia de 8 arquivos, com giros, abaixo de um teto de tempo.
Tudo sintetico, gerado na hora numa pasta temporaria; nenhum job real.
"""
import copy
import json
import time

import pytest

import familia_geometria as G
import test_derivacao_apoio as ap
import test_tela_escrita as tte
import test_tela_servidor as tts
from desdobra import contratos, plataforma
from desdobra.derivacao import formatos as mod_formatos
from desdobra.derivacao import nucleo as nd
from desdobra.derivacao import proposta
from desdobra.tela import atos as ta
from desdobra.tela import estado as te
from desdobra.tela import rascunho as tr
from desdobra.tela import servidor as ts
from sinteticos import kv_a_b as kv
from sinteticos import kv_diagonal as KD

PLAT = plataforma.obter()
TOL = 0.01  # numero-neutro: px, o arredondamento da caixa gravada
REF = 'f1080x1920'
GIRO = {'graus': 0, 'sentido': None}
FORMATOS = [('f1080x1080', 1080, 1080, 0), ('f970x250', 970, 250, 0), ('f1080x1920', 1080, 1920, 0),
            ('f300x600', 300, 600, 0), ('g1920x1080r270', 1920, 1080, 270), ('g640x360r90', 640, 360, 90)]
VERTICAIS = ['f1080x1920', 'f300x600', 'g1920x1080r270', 'g640x360r90']
TETO_8_S = 20.0  # numero-neutro: segundos, o teto da conta da familia de 8 arquivos (medido: menos de 1 s em 18/11)


def _rotacao(g):
    return {'graus': g, 'sentido': 'horario'} if g else dict(GIRO)


def _passo_2_diagonal(funcoes):
    return {'funcoes': {str(k): {'funcao': v, 'observacao': None} for k, v in funcoes.items()},
            'design': {f: {'regra': r, 'x': x, 'y': y} for f, (r, x, y) in KD.USADAS.items()}}


def _ato(s, biscoito, nome, dados):
    codigo, p = tte._pedir_ato(s, biscoito, nome=nome, dados=dados)
    assert codigo == 200, (nome, codigo)
    c2, _cab, _corpo = tte._escrever(s, '/api/ato/confirmar', {'pedido': p['pedido'], 'resposta': 'confirmar'},
                                     cookie=biscoito)
    assert c2 == 200, (nome, c2)


def _salvar(job, conteudo, escolhas, passo_2, fids):
    """Grava o rascunho com as escolhas de cada familia, confirma todas e clica "Salvar e seguir" pelas rotas da tela
    (modo de teste), como test_tela_previa_igual_ao_salvar._salvar. Devolve {id do formato: derivacao gravada}."""
    s = ts.ServidorTela(conteudo, pasta=job, modo_teste=True, atos=ta.atos_do_job(job, conteudo=conteudo)).iniciar()
    try:
        biscoito = tts._entrar(s)
        familias = {gid: {'versao': e['versao'], 'confirmada': False, 'edicoes': e['edicoes'],
                          'quebras': e.get('quebras') or []} for gid, e in escolhas.items()}
        corpo = dict({'job_id': s.job_id, 'laudo_sha256': s.laudo_sha256, 'familias': familias}, **passo_2)
        assert tte._escrever(s, '/api/rascunho', corpo, cookie=biscoito)[0] == 200
        _ato(s, biscoito, 'modo_dados', {'modo': 'c'})
        for gid, e in familias.items():
            _ato(s, biscoito, 'familia', {'familia': gid, 'versao': e['versao'], 'edicoes': e['edicoes'],
                                          'quebras': e['quebras']})
        dados = json.loads((job / tr.ARQUIVO).read_text(encoding='utf-8'))
        vista = {k: dados[k] for k in ('job_id', 'laudo_sha256', 'familias', 'funcoes', 'cobertas', 'design',
                                       'design_camadas') if k in dados}
        _ato(s, biscoito, 'salvar', {'rascunho': vista})
    finally:
        s.parar()
    return {fid: contratos.ler(job / nd.PASTA / ('%s.json' % fid), nd.ESQUEMA) for fid in fids}


def _familia_de(conteudo, fid):
    return next(g for g, f in conteudo['familias'].items() if fid in f['formatos'])


def _versao_limpa(conteudo, gid):
    """Como a tela abre a familia: a primeira versao sem falha (sem galeria, None)."""
    vs = conteudo['familias'][gid].get('versoes') or []
    for v in vs:
        r = conteudo['editar']({'familia': gid, 'versao': v, 'edicoes': []}, 'fixture_de_teste')
        if not any(m.get('falhas') for m in r['membros']):
            return v
    return vs[0] if vs else None


def _caixas_previa(m):
    return {e['id']: [float(x) for x in e['caixa']] for e in m['palco']['elementos']}


def _caixas_gravadas(d):
    return {e['id']: [float(x) for x in e['caixa']] for e in d['elementos']}


def _confere_igual(m, d):
    """A previa do membro e a derivacao gravada: as mesmas caixas (0,00 px, no arredondamento da caixa gravada) e as
    mesmas falhas."""
    previa, gravada = _caixas_previa(m), _caixas_gravadas(d)
    assert sorted(previa) == sorted(gravada)
    for k, c in previa.items():
        assert gravada[k] == pytest.approx(c, abs=TOL), (k, c, gravada[k])
    registro = next((r for r in d['registros'] if r['codigo'] == 'proposta_com_falha'), None)
    assert sorted({f['codigo'] for f in m['falhas']}) == (registro['medidas']['falhas'] if registro else []), \
        (m['falhas'], d['registros'])
    assert d['situacao'] == 'derivado', d.get('devolucao')


def _no_doc(e, p):
    """O ponto p do documento levado ao formato pela transformacao do elemento e (a conta do render)."""
    tr_ = e['transformacao']
    s = float(tr_['s'])
    return [s * (p[0] - tr_['origem_doc'][0]) + tr_['destino'][0], s * (p[1] - tr_['origem_doc'][1]) +
            tr_['destino'][1]]


# ------------------------------------------------------------------ o KV da diagonal
@pytest.fixture(scope='module')
def diag(tmp_path_factory):
    if PLAT.nome in ('sem-suporte', 'mac'):
        pytest.skip('sem isolador neste sistema')
    j = KD.criar_job(tmp_path_factory.mktemp('familia-diagonal'), FORMATOS)
    conteudo = te.montar(j['job'])
    j['conteudo'] = conteudo
    j['el'] = {papel: 'el%d' % lid for papel, lid in j['ids'].items()}
    return j


def test_arquivo_de_edicao_e_o_maior_em_pe_e_so_ele_tem_galeria(diag):
    conteudo = diag['conteudo']
    gid = _familia_de(conteudo, REF)
    assert sorted(conteudo['familias'][gid]['formatos']) == sorted(VERTICAIS)
    grupo = next(g for o in conteudo['estado']['orientacoes'] for g in o['grupos'] if g['id'] == gid)
    # o 1080x1920 e o 1920x1080 girado empatam na area em pe: vence o sem giro
    assert grupo['arquivo_de_edicao'] == REF and grupo['separados'] == []
    editor = conteudo['editar'].__self__
    assert editor.arquivo_de_edicao(gid) == REF
    # a galeria so no arquivo de edicao (199, 5)
    for fid in VERTICAIS:
        if fid != REF:
            assert 'galeria' not in conteudo['previas'][fid], fid
    # o pedido que diz outro arquivo de edicao e recusado
    assert conteudo['editar']({'familia': gid, 'versao': None, 'edicoes': [], 'arquivo': 'f300x600'},
                              'fixture_de_teste') is None
    assert conteudo['editar']({'familia': gid, 'versao': None, 'edicoes': [], 'arquivo': REF},
                              'fixture_de_teste') is not None


def test_diagonal_previa_igual_ao_salvar_e_assinatura_no_branco(diag):
    conteudo, el, job = diag['conteudo'], diag['el'], diag['job']
    gid = _familia_de(conteudo, REF)
    # o DA edita so o arquivo de edicao: o titulo desce 10 px no 1080x1920, sem sair do azul
    eds = [{'elemento': el['titulo'], 'acao': 'mover', 'dx': 0.0, 'dy': round(10.0 / 1920.0, 6)}]
    escolhas = {g: {'versao': _versao_limpa(conteudo, g), 'edicoes': []} for g in conteudo['familias']}
    escolhas[gid] = {'versao': None, 'edicoes': eds}
    previas = {}
    for g, e in escolhas.items():
        r = conteudo['editar']({'familia': g, 'versao': e['versao'], 'edicoes': e['edicoes']}, 'fixture_de_teste')
        previas.update({m['formato']: m for m in r['membros']})
        if g == gid:
            assert r['arquivo_de_edicao'] == REF
    fids = [f for f, _w, _h, _g in FORMATOS]
    ds = _salvar(job, conteudo, escolhas, _passo_2_diagonal(diag['funcoes']), fids)
    for fid in fids:
        m, d = previas[fid], ds[fid]
        assert not [f for f in m['falhas'] if f['codigo'] in ('sobreposicao_nova', 'fora_do_quadro')], (fid, m['falhas'])
        _confere_igual(m, d)
    # o arquivo de edicao fica com a edicao do DA; os outros copiam, com o registro
    assert ds[REF]['caminho'] != proposta.CAMINHO_FAMILIA and previas[REF]['arquivo_de_edicao']
    for fid in VERTICAIS:
        if fid == REF:
            continue
        d = ds[fid]
        assert d['caminho'] == proposta.CAMINHO_FAMILIA, fid
        assert {e['origem_geometria'] for e in d['elementos']} == {'familia'}
        reg = next(r for r in d['registros'] if r['codigo'] == proposta.CODIGO_TRANSFERENCIA)['medidas']
        assert reg['arquivo_de_edicao'] == REF and reg['situacao'] == previas[fid]['situacao']
        assert set(reg) >= {'s', 'crescimento', 'ancoras', 'ajustes', 'relacoes_quebradas'}
        assert previas[fid]['situacao'] in ('igual', 'ajustado', 'pede_ajuste')
    # o 300x600: a assinatura com 0,463 da largura, no branco, livre do azul com a folga do aprovado x s, sem ajuste
    d = ds['f300x600']
    reg = next(r for r in d['registros'] if r['codigo'] == proposta.CODIGO_TRANSFERENCIA)['medidas']
    assert reg['ajustes'] == [] and reg['relacoes_quebradas'] == [], reg
    assert previas['f300x600']['situacao'] == 'igual', (previas['f300x600']['falhas'],
                                                        previas['f300x600']['validacoes_reprovadas'])
    por = {e['id']: e for e in d['elementos']}
    a, azul = por[el['assinatura']]['caixa'], por[el['azul']]
    W = d['formato']['composicao'][0]
    assert (a[2] - a[0]) / W == pytest.approx(0.463, abs=0.01)
    p1, p2 = _no_doc(azul, G.P1), _no_doc(azul, G.P2)
    inclinacao = (p2[1] - p1[1]) / (p2[0] - p1[0])
    assert inclinacao == pytest.approx(G.INCLINACAO, rel=1e-6)  # a diagonal no mesmo angulo
    folga_ref = G.distancia_a_reta(G.ASSINATURA[:2], G.P1, G.INCLINACAO)
    assert G.distancia_a_reta(a[:2], p1, inclinacao) >= folga_ref * reg['s'] - TOL
    # o girado 270 e o 1080x1920 em pe: o mesmo layout, 0 px
    ref, g270 = _caixas_gravadas(ds[REF]), _caixas_gravadas(ds['g1920x1080r270'])
    for k, c in ref.items():
        assert g270[k] == pytest.approx(c, abs=TOL), k


def test_diagonal_previa_deterministica_e_sem_edicao_tambem_copia(diag):
    """A familia sem edicao tambem segue o arquivo de edicao (resposta 3 do Duda): a mesma entrada da a mesma saida."""
    conteudo = diag['conteudo']
    gid = _familia_de(conteudo, REF)
    pedido = {'familia': gid, 'versao': None, 'edicoes': []}
    um = conteudo['editar'](copy.deepcopy(pedido), 'fixture_de_teste')
    dois = conteudo['editar'](copy.deepcopy(pedido), 'fixture_de_teste')
    for x in (um, dois):
        x.pop('tempo_ms')
    assert json.dumps(um, sort_keys=True) == json.dumps(dois, sort_keys=True)
    por = {m['formato']: m for m in um['membros']}
    m = por['f300x600']
    assert m['situacao'] == 'igual' and m['ajustes'] == [] and m['falhas'] == []
    # o azul cresce em volta do ponto da diagonal e passa um pouco da base, debaixo da faixa verde: a frase diz qual
    # borda ele passa a tocar e por que (nada calado), sem o valor em px (revisao da 0.10.0), e o lado passa a sangrar
    # neste arquivo
    assert [a['codigo'] for a in m['avisos'] if a['codigo'] == 'base_passa_da_borda'] == ['base_passa_da_borda']
    assert m['frases'] == [a['texto'] for a in m['avisos'] if a['codigo'] == 'base_passa_da_borda']
    assert m['frases'][0] == ('A forma chega até a borda de baixo neste arquivo e fica cortada ali, para o desenho '
                              'ficar no mesmo lugar em relação à assinatura. No seu arquivo, ela não chegava a essa '
                              'borda.'), m['frases']
    assert ' px' not in m['frases'][0]


# ------------------------------------------------------------------ a area segura do arquivo girado
def test_area_segura_do_arquivo_girado_e_medida_em_pe(diag):
    """A folha da area segura de um arquivo girado vale na composicao, em pe (o giro fica na entrega): a copia mantem
    o texto e a assinatura dentro dela, e o quadro do arquivo e o da composicao."""
    ctx = nd.preparar(diag['job'])
    b = copy.deepcopy(ctx['briefing'])
    chave = 'teste|circuito|giro-area-segura'
    for f in b['formatos']:
        if f['id'] == 'g640x360r90':
            f['chave'] = chave
    ctx = dict(ctx, briefing=b)
    r = nd.derivar_em_memoria(ctx, specs={}, composicoes=False)
    params = mod_formatos.parametros(diag['job'], b)
    specs = {chave: {'campos': {'area_segura': {'valor': {'pct': 12, 'lados': ['superior', 'inferior']}}}}}
    lays = proposta.layout_da_familia(ctx, r['kv'], {'familia': 'v', 'formatos': VERTICAIS, 'versao': None,
                                                     'edicoes': []},
                                      derivados=r['formatos'], specs=specs, arquivo_specs=None, params=params)
    lay = lays['g640x360r90']
    W, H = mod_formatos.composicao(next(f for f in b['formatos'] if f['id'] == 'g640x360r90'))
    assert (W, H) == (360, 640)
    seg = lay['cf']['areas']['area_segura']['caixa']
    assert seg == pytest.approx([0.0, 0.12 * 640, 360.0, 640 - 0.12 * 640])
    assert lay['quadros']['area_segura'] == pytest.approx(seg)
    assert not [f for f in lay['falhas'] if f['codigo'] == 'fora_da_area_segura'], lay['falhas']
    for papel in ('titulo', 'texto', 'assinatura'):
        c = lay['caixas_visiveis'][diag['el'][papel]]
        assert c[1] >= seg[1] - TOL and c[3] <= seg[3] + TOL, (papel, c, seg)


# ------------------------------------------------------------------ o teto de tempo
def test_familia_de_oito_arquivos_com_giro_abaixo_do_teto(diag):
    ctx = nd.preparar(diag['job'])
    b = copy.deepcopy(ctx['briefing'])
    oito = [('v1080x1920', 1080, 1920, 0), ('v300x600', 300, 600, 0), ('g1920x1080', 1920, 1080, 270),
            ('g640x360', 640, 360, 90), ('v720x1280', 720, 1280, 0), ('v1080x1700', 1080, 1700, 0),
            ('g1600x900', 1600, 900, 90), ('v540x1080', 540, 1080, 0)]
    b['formatos'] = [ap.formato(i, w, h, rotacao=_rotacao(g)) for i, w, h, g in oito]
    ctx = dict(ctx, briefing=b)
    r = nd.derivar_em_memoria(ctx, specs={}, composicoes=False)
    params = mod_formatos.parametros(diag['job'], b)
    familia = {'familia': 'v', 'formatos': [i for i, _w, _h, _g in oito], 'versao': None, 'edicoes': []}
    inicio = time.perf_counter()
    lays = proposta.layout_da_familia(ctx, r['kv'], familia, derivados=r['formatos'], specs={}, arquivo_specs=None,
                                      params=params)
    gasto = time.perf_counter() - inicio
    assert gasto < TETO_8_S, gasto
    assert lays['v1080x1920']['situacao'] == 'arquivo_de_edicao'
    for fid, lay in lays.items():
        assert lay is not None and 'erro' not in lay, (fid, lay)
        assert not [f for f in lay['falhas'] if f['codigo'] in ('sobreposicao_nova', 'fora_do_quadro')], \
            (fid, lay['falhas'])
    # a ordem dos arquivos na lista nao muda a copia (so o empate do arquivo de edicao)
    outra = dict(familia, formatos=list(reversed(familia['formatos'])))
    lays2 = proposta.layout_da_familia(ctx, r['kv'], outra, derivados=r['formatos'], specs={}, arquivo_specs=None,
                                       params=params)
    for fid in lays:
        assert lays2[fid]['caixas'] == lays[fid]['caixas'], fid


# ------------------------------------------------------------------ a regressao do repro B (KV A)
def test_repro_b_titulo_cabe_e_logo_fica_na_linha_da_margem(tmp_path, monkeypatch):
    """O repro B de 18/11: o DA so mexe no 1080x1920 (o titulo em 2 linhas e maior, alinhado a margem esquerda e a
    base, o bloco de apoio sobe, o logo vai para a margem esquerda). Antes, o titulo do 300x600 saia com 1,064 da
    largura e o logo a 0,026 da largura fora da linha da margem."""
    monkeypatch.setattr(kv, 'TITULO', 'HOAX VA')
    t = kv.CAIXAS['a']['titulo']
    monkeypatch.setitem(kv.CAIXAS, 'a', dict(kv.CAIXAS['a'], titulo=[t[0], t[1], t[0] + 136, t[3]]))
    monkeypatch.setattr(kv, 'FORMATOS', [('f1080x1080', 1080, 1080), ('f970x250', 970, 250),
                                         ('f1080x1920', 1080, 1920), ('f300x600', 300, 600)])
    j = kv.criar_job(tmp_path, 'a')
    conteudo = te.montar(j['job'])
    gid = _familia_de(conteudo, REF)
    el = {p: 'el%d' % lid for p, lid in j['ids'].items()}
    versao = _versao_limpa(conteudo, gid)
    qb = [{'elemento': el['titulo'], 'layer_id': j['ids']['titulo'], 'manter': [], 'inseridas': [4],
           'origem': 'da', 'aprovada': True}]
    eds = []
    W, H = 1080.0, 1920.0

    def rep():
        r = conteudo['editar']({'familia': gid, 'versao': versao, 'edicoes': eds, 'quebras': qb}, 'fixture_de_teste')
        m = next(x for x in r['membros'] if x['formato'] == REF)
        return {e['id']: e['caixa'] for e in m['palco']['elementos']}, m, r
    c, _m, _r = rep()
    eds.append({'elemento': el['titulo'], 'acao': 'escalar',
                'fator': round(0.90 * W / (c[el['titulo']][2] - c[el['titulo']][0]), 6)})
    eds.append({'elemento': el['titulo'], 'acao': 'alinhar', 'alvo': 'margem_esquerda', 'referencia': 'margem'})
    eds.append({'elemento': el['titulo'], 'acao': 'alinhar', 'alvo': 'base', 'referencia': 'margem'})
    c, _m, _r = rep()
    bloco = [el[p] for p in ('linha', 'apoio', 'icone1', 'icone2')]
    eds.append({'elemento': bloco[0], 'elementos': bloco, 'acao': 'mover', 'dx': 0.0,
                'dy': round((c[el['titulo']][1] - 0.012 * H - max(c[k][3] for k in bloco)) / H, 6)})
    c, m, _r = rep()
    eds.append({'elemento': el['assinatura'], 'acao': 'mover',
                'dx': round((m['quadro']['margem'][0] - c[el['assinatura']][0]) / W, 6), 'dy': 0.0})
    _c, _m, r = rep()
    membro = next(x for x in r['membros'] if x['formato'] == 'f300x600')
    caixas = _caixas_previa(membro)
    w = float(membro['palco']['largura'])
    titulo, logo = caixas[el['titulo']], caixas[el['assinatura']]
    assert (titulo[2] - titulo[0]) / w <= 0.95, (titulo, w)
    assert abs(logo[0] - membro['quadro']['margem'][0]) / w <= 0.002, (logo, membro['quadro'])
    # e o "Salvar e seguir" grava o mesmo
    escolhas = {g: {'versao': _versao_limpa(conteudo, g), 'edicoes': []} for g in conteudo['familias']}
    escolhas[gid] = {'versao': r['versao'], 'edicoes': eds, 'quebras': qb}
    ds = _salvar(j['job'], conteudo, escolhas, kv.passo_2(j['funcoes']), ['f300x600', REF])
    _confere_igual(membro, ds['f300x600'])
