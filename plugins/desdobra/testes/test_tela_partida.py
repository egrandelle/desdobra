# -*- coding: utf-8 -*-
"""M7a: a tela abre no job novo, sem briefing gravado, e o DA chega ao primeiro briefing confirmado so por cliques.

Criterios cobertos aqui:
  - a tela abre com o laudo e as specs do job, sem briefing (nenhum briefing importado antes) e sem gravar nada em
    briefing/ na abertura;
  - os formatos saem das specs do job (a chave, a largura e a altura da folha), todos, confirmados ou nao; o que so o
    DA decide fica pendente;
  - o passo 3 espera o passo 2, com o aviso em portugues, e aparece depois que o passo 2 passa na conferencia, pelo
    GET do estado, sem abrir a tela de novo;
  - modo de dados, prancheta, giro de cada formato, passo 2, versao da galeria, "Confirmar familia" e "Salvar e
    seguir" pelas rotas de escrita, no modo de teste, terminam num briefing-confirmado.json valido e numa derivacao,
    que passa na conferencia do giro e das familias do portao de entrega;
  - o ato de spec da tela deixa a fase das specs em dia, e a tela que nao consegue se atualizar avisa o DA;
  - o briefing salvo de outras specs (ou de outro PSD) nao impede a tela de abrir: ela parte do briefing de partida
    e do rascunho, com o aviso do que mudou;
  - specs sem formato em pixels: a tela diz o que falta e o que fazer.
Tudo sintetico: o PSD de test_tela_palco (e uma variante com pranchetas), a fonte de autoteste do motor e duas fichas
HTML de spec escritas aqui."""
import copy
import json

import pytest

import test_fontes_apoio as fap
import test_render_apoio as rap
import test_specs_apoio as sap
import test_tela_escrita as tte
import test_tela_palco as tp
import test_tela_servidor as tts
from desdobra import contratos
from desdobra.briefing import modelo as mb
from desdobra.derivacao import nucleo as nd
from desdobra.tela import atos as ta
from desdobra.tela import estado as te
from desdobra.tela import rascunho as tr
from desdobra.tela import servidor as ts

USADAS = {'fundo': ('cover', 'centro', 'meio'), 'titulo': ('raiz_area', 'esquerda', 'topo'),
          'logo_principal': ('raiz_area', 'direita', 'base'), 'texto_de_apoio': ('raiz_area', 'esquerda', 'meio')}
# duas folhas no jeito das paginas de midia kit: a mesma proporcao do KV (320 x 160) e uma vertical
FOLHAS = {'globo/mesma.html': sap.html_ficha('Mesma Exemplo', [('dimensão', '640x320'), ('peso (hosted)', 'até 250KB')]),
          'globo/meia.html': sap.html_meia_pagina()}
ROT0 = {'graus': 0, 'sentido': None}
ROT180 = {'graus': 180, 'sentido': None}


def _psd_com_pranchetas(destino, ps):
    """O PSD de test_tela_palco dentro de uma pasta do topo que cobre o canvas, e outra pasta do topo, oculta, com um
    fundo so dela: o laudo le as duas como pranchetas (quadros por grupos do topo)."""
    from PIL import Image
    from psd_tools import PSDImage
    p = PSDImage.new('RGB', (320, 160), color=(255, 255, 255))
    a = p.create_group(name='peca-sintetica')
    a.create_pixel_layer(Image.new('RGBA', (320, 160), (240, 236, 220, 255)), name='fundo-sintetico')
    g = a.create_group(name=tp.NOME_FORM)
    t1 = g.create_pixel_layer(Image.new('RGBA', (200, 30), (20, 20, 20, 255)), name=tp.NOME_IMG, top=20, left=10)
    fap._virar_texto(t1, [('HOAX', 0, 28.0, 0)], [ps], fap.largura('HOAX', 28.0, avancos=tp.AVANCOS), x=12.0, y=44.0)
    g.create_pixel_layer(Image.new('RGBA', (100, 4), (30, 30, 120, 255)), name='linha-sintetica', top=56, left=12)
    a.create_pixel_layer(Image.new('RGBA', (40, 40), (0, 120, 60, 255)), name='quadrado-sintetico', top=100, left=260)
    t2 = a.create_pixel_layer(Image.new('RGBA', (200, 30), (20, 20, 20, 255)), name=tp.NOME_APOIO, top=110, left=10)
    fap._virar_texto(t2, [('VOX AH', 0, 20.0, 0)], [ps], fap.largura('VOX AH', 20.0, avancos=tp.AVANCOS), x=20.0,
                     y=130.0)
    a.create_pixel_layer(Image.new('RGBA', (20, 20), (220, 0, 0, 255)), name='solto-sintetico', top=70, left=200)
    b = p.create_group(name='outra-sintetica')
    b.create_pixel_layer(Image.new('RGBA', (320, 160), (20, 40, 200, 255)), name='fundo-outro')
    b.visible = False
    return rap._salvar(p, destino)


def _criar(tmp_path, psd=None, folhas=FOLHAS):
    """Job sintetico novo: laudo, fontes e specs lidos, sem briefing nenhum. Devolve (job, funcoes por layer_id)."""
    from desdobra.job import nucleo
    from desdobra.render import autoteste
    fontes = tmp_path / 'origem-fontes'
    fap.gravar(fontes, 'autoteste.ttf', autoteste.gerar_fonte())
    specs = None
    if folhas:
        specs = tmp_path / 'origem-specs'
        for rel, texto in folhas.items():
            (specs / rel).parent.mkdir(parents=True, exist_ok=True)
            (specs / rel).write_text(texto, encoding='utf-8')
    job = tmp_path / 'job'
    psd = psd or tp._psd_hostil
    nucleo.criar(job, psd(tmp_path / 'origem' / 'kv.psd', autoteste.NOME_PS), 'c', fontes=[fontes], specs=specs)
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    ids = {c['nome']: c['identidade']['layer_id'] for c in laudo['camadas']}
    funcoes = {ids['fundo-sintetico']: 'fundo', ids[tp.NOME_FORM]: 'titulo', ids['quadrado-sintetico']: 'logo_principal',
               ids[tp.NOME_APOIO]: 'texto_de_apoio', ids['solto-sintetico']: 'fora_da_peca'}
    return job, funcoes


@pytest.fixture
def novo(tmp_path):
    """Job sintetico novo: laudo, fontes e specs lidos, sem briefing nenhum."""
    return _criar(tmp_path)


@pytest.fixture
def com_pranchetas(tmp_path):
    """Job sintetico novo com duas pranchetas no PSD (a peca e uma oculta)."""
    return _criar(tmp_path, psd=_psd_com_pranchetas)


def _passo_2(funcoes):
    return {'funcoes': {str(k): {'funcao': v, 'observacao': None} for k, v in funcoes.items()},
            'design': {f: {'regra': r, 'x': x, 'y': y} for f, (r, x, y) in USADAS.items()}}


def _ato(s, biscoito, nome, dados):
    codigo, p = tte._pedir_ato(s, biscoito, nome=nome, dados=dados)
    if codigo != 200:
        return codigo, None
    return codigo, tte._escrever(s, '/api/ato/confirmar', {'pedido': p['pedido'], 'resposta': 'confirmar'},
                                 cookie=biscoito)[0]


def _estado(s, biscoito):
    codigo, _cab, corpo = tts._pedir(s, '/api/estado', cookie=biscoito)[:3]
    assert codigo == 200
    return json.loads(corpo)


def _previa(s, biscoito, fid):
    codigo, _cab, corpo = tts._pedir(s, '/api/previa/%s' % fid, cookie=biscoito)[:3]
    assert codigo == 200, fid
    return json.loads(corpo)


def _rascunho(s, biscoito, familias, passo_2):
    corpo = dict({'job_id': s.job_id, 'laudo_sha256': s.laudo_sha256, 'familias': familias}, **passo_2)
    return tte._escrever(s, '/api/rascunho', corpo, cookie=biscoito)[0]


def _vista(job):
    dados = json.loads((job / tr.ARQUIVO).read_text(encoding='utf-8'))
    return {k: dados[k] for k in ('job_id', 'laudo_sha256', 'familias', 'funcoes', 'cobertas', 'design',
                                  'design_camadas', 'quadro', 'rotacoes') if k in dados}


def _sem_travessao(texto):
    return '—' not in texto and '–' not in texto and 'motor' not in texto.lower()


def _servidor(job):
    conteudo = te.montar(job)
    s = ts.ServidorTela(conteudo, pasta=job, modo_teste=True, atos=ta.atos_do_job(job, conteudo=conteudo)).iniciar()
    return conteudo, s


def test_tela_abre_no_job_novo_sem_gravar_briefing(novo):
    job, _funcoes = novo
    assert not (job / mb.ARQUIVO).exists()
    with pytest.raises(nd.ErroDerivacao):
        nd.preparar(job)  # a derivacao continua pedindo o briefing confirmado
    antes = sorted(p.name for p in (job / 'briefing').iterdir()) if (job / 'briefing').is_dir() else []
    conteudo = te.montar(job)
    depois = sorted(p.name for p in (job / 'briefing').iterdir()) if (job / 'briefing').is_dir() else []
    assert antes == depois and not (job / mb.ARQUIVO).exists()
    e = conteudo['estado']
    # os formatos vem das specs do job: as chaves da folha, com a largura e a altura dela
    formatos = {f['chave']: f for f in e['lido']['specs']['formatos']}
    assert len(formatos) == 2 and all(f['sem_folha'] is False for f in formatos.values())
    assert {k.rsplit('|', 1)[1] for k in formatos} == {'640x320', '300x600'}
    # nada decidido: o modo, o giro de cada formato, as funcoes e o passo 3 esperam o DA
    assert e['lido']['modo_dados']['escolhido'] is None
    assert all(f['rotacao'] is None and f['giro_da_folha'] is None for f in formatos.values())
    giro = next(x for x in e['faltam'] if x['texto'] == te.GIRO_SEM_ESCOLHA)
    assert giro['ir'] == {'passo': 'lido'} and _sem_travessao(giro['texto'])
    assert e['lido']['quadros'] == []  # sem pranchetas no PSD, nada a escolher
    assert e['passo_3']['aguarda_passo_2'] is True and _sem_travessao(e['passo_3']['texto'])
    assert e['orientacoes'] == [] and conteudo['familias'] == {}
    assert all(n['funcao'] is None for n in e['funcoes']['arvore'])
    assert e['funcoes']['palco_kv']['pecas'], 'o KV aparece no passo 2 antes das funcoes'
    assert e['briefing']['salvo'] is False and e['briefing']['avisos'] == []


def _passo_1(e, rotacoes=None, quadro=None):
    """As escolhas do passo 1 que vao ao rascunho: o giro de cada formato (pela chave da folha) e a prancheta."""
    rotacoes = rotacoes or {}
    saida = {'rotacoes': {f['chave']: rotacoes.get(f['id'], ROT0) for f in e['lido']['specs']['formatos']}}
    if quadro is not None:
        saida['quadro'] = quadro
    return saida


def _confirmar_medida(s, biscoito, job, sufixo=''):
    """O clique do DA em Valores de spec, no passo 1: confirma a dimensao do formato cuja chave termina no sufixo (a
    primeira dimensao pendente sem sufixo). Devolve a chave."""
    alvo = next(x for x in te.specs_pendentes(job) if x['campo'] == 'dimensão' and not x['leituras'] and
                x['onde'].endswith(sufixo))
    assert _ato(s, biscoito, 'spec_valor', {'valor_id': alvo['valor_id']}) == (200, 200)
    return alvo['onde']


def _confirmar_medidas(s, biscoito, job):
    """Confirma a dimensao de todo formato: a derivacao so monta a peca com a medida confirmada (revisao dos becos)."""
    while any(x['campo'] == 'dimensão' and not x['leituras'] for x in te.specs_pendentes(job)):
        _confirmar_medida(s, biscoito, job)


def _ate_salvar(s, biscoito, job, funcoes, quadro=None, rotacoes=None):
    """Do job novo ao "Salvar e seguir" pelas rotas de escrita, no modo de teste: o DA confirma a medida de cada
    formato no passo 1 e segue. Devolve as familias do rascunho."""
    _confirmar_medidas(s, biscoito, job)
    assert _ato(s, biscoito, 'modo_dados', {'modo': 'c'}) == (200, 200)
    # sem o passo 2, o passo 3 espera e nada e salvo
    assert _ato(s, biscoito, 'salvar', {'rascunho': {}})[0] == 403
    p2 = dict(_passo_2(funcoes), **_passo_1(_estado(s, biscoito), rotacoes, quadro))
    assert _rascunho(s, biscoito, {}, p2) == 200
    assert not (job / mb.ARQUIVO).exists()
    # o GET do estado traz o passo 3 montado do passo 2 do rascunho, sem abrir a tela de novo
    e = _estado(s, biscoito)
    assert e['passo_3']['aguarda_passo_2'] is False, e['passo_3']
    grupos = [g for o in e['orientacoes'] for g in o['grupos']]
    assert len(grupos) == 2
    familias = {}
    for g in grupos:
        fids = [x['id'] for c in g['composicoes'] for x in c['formatos']]
        versao = None
        for fid in fids:
            variantes = ((_previa(s, biscoito, fid).get('galeria') or {}).get('variantes')) or []
            if variantes:
                versao = variantes[0]['id']
                break
        familias[g['id']] = {'versao': versao, 'confirmada': False, 'edicoes': []}
    assert any(f['versao'] for f in familias.values()), 'a vertical vem da galeria'
    # o DA escolhe a versao de cada familia (o clique grava no rascunho) e confirma cada uma
    assert _rascunho(s, biscoito, familias, p2) == 200
    for gid, f in familias.items():
        assert _ato(s, biscoito, 'familia', {'familia': gid, 'versao': f['versao'], 'edicoes': []}) == (200, 200), gid
    assert not (job / mb.ARQUIVO).exists()
    assert _ato(s, biscoito, 'salvar', {'rascunho': _vista(job)}) == (200, 200)
    assert _estado(s, biscoito)['briefing']['salvo'] is True
    return familias


def test_confirmar_uma_medida_mantem_os_outros_formatos_e_a_fase_em_dia(novo):
    """Revisao do M7a, becos 1 e 2: confirmar a medida de um formato no passo 1 nao tira os outros do briefing, e o
    ato da tela deixa a fase das specs em dia (a tela reabre e a derivacao prepara sem passo no terminal)."""
    from desdobra.job import nucleo
    job, _funcoes = novo
    _conteudo, s = _servidor(job)
    try:
        biscoito = tts._entrar(s)
        alvo = next(x for x in te.specs_pendentes(job) if x['campo'] == 'dimensão' and not x['leituras'])
        assert _ato(s, biscoito, 'spec_valor', {'valor_id': alvo['valor_id']}) == (200, 200)
        assert mb.arquivo_de_specs(job) == mb.ARQUIVO_FORMATOS  # ja ha formato confirmado
        assert 'specs' not in nucleo.fases_invalidas(job)
        e = _estado(s, biscoito)
        assert not e.get('aviso_atualizacao')
        assert {f['chave'].rsplit('|', 1)[1] for f in e['lido']['specs']['formatos']} == {'640x320', '300x600'}
        assert e['lido']['specs']['confirmados'] >= 1
    finally:
        s.parar()
    assert {f['chave'].rsplit('|', 1)[1] for f in mb.formatos_das_specs(job)} == {'640x320', '300x600'}
    nd.preparar(job, partida=True)
    assert len(te.montar(job)['estado']['lido']['specs']['formatos']) == 2


def test_tela_avisa_quando_nao_consegue_se_atualizar(novo):
    """Revisao do M7a, beco 2: o erro ao montar a tela de novo vira um aviso em portugues no estado, e sai quando a
    tela volta a se atualizar."""
    job, _funcoes = novo
    conteudo = te.montar(job)

    def falha(motivo):
        def atualizar():
            raise te.ErroTela('falhou', motivo)
        return atualizar
    conteudo['atualizar'] = falha('fases_desatualizadas')
    s = ts.ServidorTela(conteudo, pasta=job, modo_teste=True).iniciar()
    try:
        biscoito = tts._entrar(s)
        e = _estado(s, biscoito)
        assert e['aviso_atualizacao'] == ts.AVISO_SEM_ATUALIZAR and _sem_travessao(e['aviso_atualizacao'])
        conteudo['atualizar'] = falha('job_ocupado')
        e = _estado(s, biscoito)
        assert e['aviso_atualizacao'] == ts.AVISO_JOB_OCUPADO and _sem_travessao(e['aviso_atualizacao'])
        conteudo['atualizar'] = lambda: None
        assert not _estado(s, biscoito).get('aviso_atualizacao')
    finally:
        s.parar()


def test_giro_da_folha_vem_do_texto_da_folha():
    doc = {'formatos': [
        {'chave': 'v|c|300x600', 'campos': {'rotacao': {'valor': None, 'texto_original': 'Girar 90 graus, horário',
                                                        'situacao': 'registro'}}},
        {'chave': 'v|c|640x320', 'campos': {'rotacao': {'valor': None, 'texto_original': None,
                                                        'situacao': 'registro'}}}]}
    assert te.giro_da_folha(doc, 'v|c|300x600') == 'Girar 90 graus, horário'
    assert te.giro_da_folha(doc, 'v|c|640x320') is None
    assert te.giro_da_folha(doc, 'v|c|1x1') is None and te.giro_da_folha(None, 'v|c|300x600') is None


def test_giro_de_cada_formato_e_escolha_do_da_no_rascunho(novo):
    """Revisao do M7a, beco 3: o giro de cada formato e escolha do DA no passo 1, salva no rascunho, sem nada marcado;
    o quarto de volta pede o sentido, e sem o giro de todos os formatos nada e salvo."""
    from desdobra.briefing import salvar
    job, funcoes = novo
    conteudo, s = _servidor(job)
    try:
        biscoito = tts._entrar(s)
        assert _ato(s, biscoito, 'modo_dados', {'modo': 'c'}) == (200, 200)
        fs = _estado(s, biscoito)['lido']['specs']['formatos']
        largo = next(f for f in fs if f['chave'].endswith('640x320'))
        meia = next(f for f in fs if f['chave'].endswith('300x600'))
        p2 = _passo_2(funcoes)
        assert _rascunho(s, biscoito, {}, dict(p2, rotacoes={largo['chave']: {'graus': 90, 'sentido': None}})) == 403
        assert _rascunho(s, biscoito, {}, dict(p2, rotacoes={largo['chave']: {'graus': 0, 'sentido': 'horario'}})) == 403
        assert _rascunho(s, biscoito, {}, dict(p2, rotacoes={largo['chave']: {'graus': 90, 'sentido': 'horario'}})) == 200
        e = _estado(s, biscoito)
        por_id = {f['id']: f for f in e['lido']['specs']['formatos']}
        assert por_id[largo['id']]['rotacao'] == {'graus': 90, 'sentido': 'horario'}
        assert por_id[meia['id']]['rotacao'] is None
        # o giro de um quarto de volta troca a composicao: o formato girado sai na outra orientacao
        x = next(x for o in e['orientacoes'] for g in o['grupos'] for c in g['composicoes'] for x in c['formatos']
                 if x['id'] == largo['id'])
        assert x['rotacao_graus'] == 90
        giro = next(i for i in e['faltam'] if i['texto'] == te.GIRO_SEM_ESCOLHA)
        assert giro['detalhe'] == meia['id']
        assert {'codigo': 'rotacao_sem_escolha', 'formato': meia['id']} in salvar.pendencias(job, conteudo)
        dados = tr.ler(job, tr.laudo_sha256(job))[0]
        b = salvar.montar(job, conteudo, dados, origem='da', meio='tela', por={'usuario': None, 'maquina': None},
                          quando=mb.agora(), modo='c')
        assert {f['id']: f.get('rotacao') for f in b['formatos']} == {largo['id']: {'graus': 90, 'sentido': 'horario'},
                                                                       meia['id']: None}
    finally:
        s.parar()


def test_familia_de_antes_do_giro_nao_e_confirmada_nem_salva(novo):
    """Revisao do M7a: o giro gravado no rascunho muda as familias. O ato pedido logo depois, antes de a pagina pedir o
    estado de novo, ja ve as familias novas: a familia que sumiu nao e confirmada, e o briefing nunca sai com as
    familias de antes do giro."""
    job, funcoes = novo
    _conteudo, s = _servidor(job)
    try:
        biscoito = tts._entrar(s)
        assert _ato(s, biscoito, 'modo_dados', {'modo': 'c'}) == (200, 200)
        p2 = dict(_passo_2(funcoes), **_passo_1(_estado(s, biscoito)))
        assert _rascunho(s, biscoito, {}, p2) == 200
        e = _estado(s, biscoito)
        antes = {g['id']: [x['id'] for c in g['composicoes'] for x in c['formatos']]
                 for o in e['orientacoes'] for g in o['grupos']}
        largo = next(f for f in e['lido']['specs']['formatos'] if f['chave'].endswith('640x320'))
        sozinha = next(g for g, fids in antes.items() if fids == [largo['id']])
        # o DA gira o largo um quarto de volta: ele passa para a familia vertical
        girado = dict(p2, rotacoes=dict(p2['rotacoes'], **{largo['chave']: {'graus': 90, 'sentido': 'horario'}}))
        assert _rascunho(s, biscoito, {g: {'versao': None, 'confirmada': False, 'edicoes': []} for g in antes},
                         girado) == 200
        assert _ato(s, biscoito, 'familia', {'familia': sozinha, 'versao': None, 'edicoes': []})[0] == 403
        assert _ato(s, biscoito, 'salvar', {'rascunho': _vista(job)})[0] == 403
        depois = {g['id']: [x['id'] for c in g['composicoes'] for x in c['formatos']]
                  for o in _estado(s, biscoito)['orientacoes'] for g in o['grupos']}
        assert sozinha not in depois
    finally:
        s.parar()
    assert not (job / mb.ARQUIVO).exists()


def test_pranchetas_do_job_novo_ao_briefing_que_passa_no_giro_e_nas_familias(com_pranchetas):
    """Revisao do M7a, becos 3 e 4: no PSD com pranchetas, a prancheta da peca e escolhida no passo 1 (com a previa de
    cada uma), e o clique a clique chega ao briefing que passa na conferencia do giro e das familias do portao de
    entrega. No modo de teste a familia nao vale para a entrega; o mesmo rascunho confirmado pelo DA na janela (origem
    da, meio tela) passa."""
    from desdobra.briefing import salvar
    from desdobra.entrega import portao
    job, funcoes = com_pranchetas
    laudo = contratos.ler(job / mb.ARQUIVO_LAUDO, 'laudo/1')
    quadros = {q['nome']: q['id'] for q in laudo['documento']['quadros']}
    assert set(quadros) == {'peca-sintetica', 'outra-sintetica'}
    peca = quadros['peca-sintetica']
    conteudo, s = _servidor(job)
    e = conteudo['estado']
    assert {q['id'] for q in e['lido']['quadros']} == set(quadros.values())
    assert all(q['escolhido'] is False and 'palco' in q for q in e['lido']['quadros'])
    assert next(q for q in e['lido']['quadros'] if q['id'] == peca)['palco']['pecas']
    assert e['passo_3']['aguarda_passo_2'] is True and e['passo_3']['texto'] == te.AGUARDA_QUADRO
    assert _sem_travessao(te.AGUARDA_QUADRO)
    assert any(x['texto'] == te.QUADRO_SEM_ESCOLHA and x['ir'] == {'passo': 'lido'} for x in e['faltam'])
    meia = next(f['id'] for f in e['lido']['specs']['formatos'] if f['chave'].endswith('300x600'))
    try:
        biscoito = tts._entrar(s)
        # prancheta que o PSD nao tem: recusada
        assert _rascunho(s, biscoito, {}, {'quadro': 'q99'}) == 403
        familias = _ate_salvar(s, biscoito, job, funcoes, quadro=peca, rotacoes={meia: ROT180})
        e = _estado(s, biscoito)
        assert next(q for q in e['lido']['quadros'] if q['id'] == peca)['escolhido'] is True
    finally:
        s.parar()
    b = mb.ler(job)
    assert b['quadro']['valor'] == peca and b['quadro']['situacao'] == 'confirmado'
    assert {f['id']: f['rotacao'] for f in b['formatos']} == {f['id']: (ROT180 if f['id'] == meia else ROT0)
                                                               for f in b['formatos']}
    assert {c['familia'] for c in b['composicoes']} == set(familias)
    for f in b['formatos']:
        assert portao.conferir_rotacao(f, {}) == []
        # a confirmacao do modo de teste (fixture_de_teste, medicao) nao vale para a entrega
        assert [x['codigo'] for x in portao.conferir_familia(job, b, f['id'])] == ['familia_sem_confirmacao']
    assert mb.conferir_para_entrega(job) == (False, 'briefing_de_fixture_de_teste')
    # o mesmo rascunho com as familias confirmadas pelo DA na janela da tela
    dados = copy.deepcopy(tr.ler(job, tr.laudo_sha256(job))[0])
    for f in dados['familias'].values():
        f['confirmacao'] = dict(f['confirmacao'], origem='da', meio='tela')
    da = salvar.montar(job, conteudo, dados, origem='da', meio='tela', por={'usuario': 'da', 'maquina': 'estacao'},
                       quando=mb.agora(), modo='c')
    contratos.validar(da, mb.ESQUEMA)
    assert (da['cabecalho']['origem'], da['cabecalho']['meio']) == ('da', 'tela')
    assert da['quadro'] == {'valor': peca, 'situacao': 'confirmado', 'origem': {'tipo': 'da', 'ref': salvar.REF_RASCUNHO}}
    estado = contratos.ler(job / 'estado.json', 'estado/1')
    assert mb.conferir(laudo, da, estado['job_id']) == []
    for f in da['formatos']:
        assert portao.conferir_rotacao(f, {}) == []
        assert portao.conferir_familia(job, da, f['id']) == []


def test_briefing_salvo_de_outras_specs_abre_a_tela_do_rascunho(novo):
    """Revisao do M7a, beco 5: o DA confirma um valor de spec depois de salvar. O briefing salvo fica de outra versao das
    specs, e a tela continua abrindo: parte do briefing de partida e do rascunho (as escolhas que valem ficam), com o
    aviso do que mudou, e "Salvar e seguir" grava o briefing com as specs de agora. Os formatos velhos nunca sao
    carimbados como atuais."""
    from desdobra.briefing import salvar
    job, funcoes = novo
    conteudo, s = _servidor(job)
    try:
        biscoito = tts._entrar(s)
        _ate_salvar(s, biscoito, job, funcoes)
        assert salvar.pendencias(job, conteudo) == []
        alvo = next(x for x in te.specs_pendentes(job) if not x['leituras'])
        assert _ato(s, biscoito, 'spec_valor', {'valor_id': alvo['valor_id']}) == (200, 200)
        assert mb.desatualizado(job, mb.ler(job)) == ['specs_sha256']
        reaberta = te.montar(job)['estado']  # a tela abre de novo, sem passo no terminal
        assert reaberta['briefing']['avisos'] == [te.AVISO_SPECS_MUDARAM] and _sem_travessao(te.AVISO_SPECS_MUDARAM)
        e = _estado(s, biscoito)
        assert not e.get('aviso_atualizacao')
        assert e['briefing']['salvo'] is False and e['briefing']['avisos'] == [te.AVISO_SPECS_MUDARAM]
        assert e['passo_3']['aguarda_passo_2'] is False  # o passo 2 do rascunho continua valendo
        assert all(f['rotacao'] == ROT0 for f in e['lido']['specs']['formatos'])  # o giro tambem
        assert 'briefing_desatualizado' not in [p['codigo'] for p in salvar.pendencias(job, conteudo)]
        assert _ato(s, biscoito, 'salvar', {'rascunho': _vista(job)}) == (200, 200)
    finally:
        s.parar()
    b = mb.ler(job)
    assert mb.desatualizado(job, b) == []
    assert [f['chave'] for f in b['formatos']] == [f['chave'] for f in mb.formatos_das_specs(job)]
    assert te.montar(job)['estado']['briefing'] == {'salvo': True, 'em': b['cabecalho']['quando'], 'avisos': []}


def test_briefing_salvo_com_quebra_da_familia_e_de_outras_specs_abre_o_passo_3(novo):
    """Revisao 2 do M7b, fase C: o briefing salvo tem a quebra de linha de uma familia (M7b, C1) e depois fica de outra
    versao das specs. A retomada nao leva as composicoes (as familias ficam no rascunho da tela), entao tambem nao leva
    a quebra da familia: as duas voltam do rascunho em "Salvar e seguir". O passo 3 abre com as familias, e salvar
    passa. A quebra da faixa (M5), que nao e de familia, continua."""
    job, funcoes = novo
    lid = next(k for k, v in funcoes.items() if v == 'texto_de_apoio')
    conteudo, s = _servidor(job)
    try:
        biscoito = tts._entrar(s)
        _ate_salvar(s, biscoito, job, funcoes)
        b = mb.ler(job)
        comp = b['composicoes'][0]
        da_familia = {'layer_id': lid, 'familia': comp['familia'], 'formatos': list(comp['formatos']),
                      'quebras': {'valor': [], 'situacao': 'confirmado',
                                  'origem': {'tipo': 'fixture_de_teste', 'ref': None}},
                      'inseridas': [3], 'origem': 'da', 'aprovada': True}
        b['quebras_por_familia'] = [da_familia]
        contratos.gravar(job / mb.ARQUIVO, b, 'briefing/1')
        alvo = next(x for x in te.specs_pendentes(job) if not x['leituras'])
        assert _ato(s, biscoito, 'spec_valor', {'valor_id': alvo['valor_id']}) == (200, 200)
        assert mb.desatualizado(job, mb.ler(job)) == ['specs_sha256']
    finally:
        s.parar()
    base = mb.base_da_tela(job)
    assert not base.get('quebras_por_familia') and not base.get('composicoes')
    laudo = contratos.ler(job / mb.ARQUIVO_LAUDO, 'laudo/1')
    job_id = contratos.ler(job / 'estado.json', 'estado/1')['job_id']
    assert 'quebra_fora_da_familia' not in {e['codigo'] for e in mb.conferir(laudo, base, job_id)}
    # a quebra da faixa (sem familia) e decisao das camadas, e continua na retomada
    faixa = {'layer_id': lid, 'razao_min': 0.1, 'razao_max': 10.0,
             'quebras': {'valor': [], 'situacao': 'confirmado', 'origem': {'tipo': 'fixture_de_teste', 'ref': None}}}
    gravado = dict(mb.ler(job), quebras_por_familia=[faixa, da_familia])
    assert mb.retomada(job, gravado)['quebras_por_familia'] == [faixa]
    conteudo, s = _servidor(job)
    try:
        biscoito = tts._entrar(s)
        e = _estado(s, biscoito)
        assert e['passo_3']['aguarda_passo_2'] is False, e['passo_3']['texto']
        assert conteudo['familias']
        assert _ato(s, biscoito, 'salvar', {'rascunho': _vista(job)}) == (200, 200)
    finally:
        s.parar()


def test_retomada_nao_reaproveita_decisao_de_outro_psd(novo):
    """Revisao do M7a, beco 5: o briefing de partida com o que ainda vale do briefing salvo. Com o mesmo PSD, as decisoes
    das camadas ficam; com outro PSD, so o giro (que e do formato da folha) fica, e o aviso diz o que mudou."""
    job, _funcoes = novo
    gravado = mb.partida(job)
    gravado['cabecalho'] = dict(gravado['cabecalho'], origem=mb.ORIGEM_DA, specs_sha256='0' * 64)
    gravado['funcoes'][0]['funcao'] = {'valor': 'fundo', 'situacao': 'confirmado', 'origem': {'tipo': 'da', 'ref': None}}
    gravado['formatos'][0]['rotacao'] = ROT180
    mesmo = mb.retomada(job, gravado)
    contratos.validar(mesmo, mb.ESQUEMA)
    assert mesmo['cabecalho']['origem'] == mb.ORIGEM_RASCUNHO and mb.desatualizado(job, mesmo) == []
    assert mesmo['funcoes'][0]['funcao']['valor'] == 'fundo' and mesmo['formatos'][0]['rotacao'] == ROT180
    assert not mesmo.get('composicoes')
    assert te.avisos_de_retomada(job, gravado) == [te.AVISO_SPECS_MUDARAM]
    outro = copy.deepcopy(gravado)
    outro['cabecalho']['laudo_sha256'] = '0' * 64
    r = mb.retomada(job, outro)
    assert r['funcoes'][0]['funcao']['situacao'] == 'pendente' and r['funcoes'][0]['funcao']['valor'] is None
    assert r['formatos'][0]['rotacao'] == ROT180
    avisos = te.avisos_de_retomada(job, outro)
    assert te.AVISO_PSD_MUDOU in avisos and all(_sem_travessao(t) for t in avisos)


def test_specs_sem_formato_em_pixels_dizem_o_que_fazer(tmp_path):
    """Revisao do M7a, beco 6: sem formato em pixels nas specs, o passo 3 e a lista do que falta dizem o que falta e o
    que o DA faz, e "Salvar e seguir" nao segue sem formato."""
    from desdobra.briefing import salvar
    job, funcoes = _criar(tmp_path, folhas=None)
    conteudo = te.montar(job)
    e = conteudo['estado']
    assert e['lido']['specs']['formatos'] == []
    assert e['passo_3']['aguarda_passo_2'] is True and e['passo_3']['texto'] == te.SEM_FORMATOS
    item = next(x for x in e['faltam'] if x['texto'] == te.SEM_FORMATOS_FALTA)
    assert item['ir'] == {'passo': 'lido'} and item['detalhe'] == te.SEM_FOLHA_DE_SPEC
    assert all(_sem_travessao(t) for t in (te.SEM_FORMATOS, te.SEM_FORMATOS_FALTA, te.SEM_FOLHA_DE_SPEC,
                                           te.SEM_MEDIDA_EM_PIXELS))
    tr.gravar(job, dict({'job_id': e['job_id'], 'laudo_sha256': tr.laudo_sha256(job), 'familias': {}},
                        **_passo_2(funcoes)), job_id=e['job_id'], laudo_atual=tr.laudo_sha256(job),
              origem=mb.ORIGEM_FIXTURE)
    assert {'codigo': 'sem_formatos'} in salvar.pendencias(job, conteudo)


def test_do_job_novo_ao_primeiro_briefing_so_por_cliques(novo):
    job, funcoes = novo
    _conteudo, s = _servidor(job)
    try:
        biscoito = tts._entrar(s)
        familias = _ate_salvar(s, biscoito, job, funcoes)
    finally:
        s.parar()
    _depois_do_primeiro_salvar(job, funcoes, familias)


def _depois_do_primeiro_salvar(job, funcoes, familias):
    b = mb.ler(job)
    assert b is not None and b['cabecalho']['origem'] == mb.ORIGEM_FIXTURE  # o modo de teste da tela
    estado = contratos.ler(job / 'estado.json', 'estado/1')
    laudo = contratos.ler(job / mb.ARQUIVO_LAUDO, 'laudo/1')
    assert mb.conferir(laudo, b, estado['job_id']) == [] and mb.desatualizado(job, b) == []
    assert {x['layer_id']: x['funcao']['valor'] for x in b['funcoes']} == funcoes
    assert b['modo_dados']['valor'] == 'c'
    assert {f['chave'].rsplit('|', 1)[1] for f in b['formatos']} == {'640x320', '300x600'}
    assert all(f['rotacao'] == ROT0 for f in b['formatos'])
    assert {c['familia'] for c in b['composicoes']} == set(familias)
    assert all(c['confirmada'] for c in b['composicoes'])
    # a derivacao gravada: todo formato derivado, nenhum devolvido
    for f in b['formatos']:
        d = contratos.ler(job / 'derivacao' / ('%s.json' % f['id']), 'derivacao/1')
        assert d['situacao'] == 'derivado', (f['id'], d['devolucao'])
    dev = json.loads((job / nd.ARQUIVO_DEVOLUCOES).read_text(encoding='utf-8'))
    assert dev['devolucoes'] == []
    # o entregar continua recusando o briefing do modo de teste
    assert mb.conferir_para_entrega(job) == (False, 'briefing_de_fixture_de_teste')


def test_passo_1_no_chromium_escolhe_prancheta_e_giro(com_pranchetas):
    """A prancheta e o giro sao cliques no passo 1, sem nada marcado ao abrir: o clique vai ao rascunho, o quarto de
    volta so vai depois do sentido, e o botao "Salvar e seguir" diz o que falta."""
    import os

    from playwright.sync_api import sync_playwright

    from desdobra.chromium import navegador
    job, _funcoes = com_pranchetas
    laudo = contratos.ler(job / mb.ARQUIVO_LAUDO, 'laudo/1')
    peca = next(q['id'] for q in laudo['documento']['quadros'] if q['nome'] == 'peca-sintetica')
    conteudo = te.montar(job)
    fs = conteudo['estado']['lido']['specs']['formatos']
    meia = next(f for f in fs if f['chave'].endswith('300x600'))
    largo = next(f for f in fs if f['chave'].endswith('640x320'))
    salvo = '() => document.documentElement.dataset.rascunho === "salvo" ? "1" : ""'

    def gravado():
        arq = job / tr.ARQUIVO
        return json.loads(arq.read_text(encoding='utf-8')) if arq.exists() else {}

    def clicar(seletor):
        pg.evaluate('s => document.querySelector(s).click()', seletor)

    def giro(f, graus, sentido=''):
        return 'button[data-giro="%s|%s|%s"]' % (f['chave'], graus, sentido)
    navegador.apontar_playwright()
    with ts.ServidorTela(conteudo, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo)) as srv, sync_playwright() as pw:
        nav = pw.chromium.launch(headless=True, args=list(navegador.ARGUMENTOS))
        pg = nav.new_context(viewport={'width': 1280, 'height': 800}, device_scale_factor=1).new_page()
        try:
            try:
                pg.goto(srv.url_entrada, wait_until='commit')
            except Exception:  # noqa: BLE001 - o 204 nao completa a navegacao
                pass
            pg.goto(srv.url_pagina, wait_until='load')
            tp._esperar(pg, tp.JS_PRONTO)
            assert not pg.evaluate('() => document.getElementById("bloco-quadros").hidden')
            botoes = pg.evaluate('() => Array.from(document.querySelectorAll("#lido-quadros button")).map(b => '
                                 '[b.dataset.quadro, b.getAttribute("aria-pressed"), b.querySelectorAll(".peca").length])')
            assert {b[0] for b in botoes} == {q['id'] for q in laudo['documento']['quadros']}
            assert all(b[1] == 'false' for b in botoes)  # nada marcado ao abrir
            assert next(b for b in botoes if b[0] == peca)[2] > 0  # a previa da prancheta
            assert pg.evaluate('() => document.querySelectorAll("#lido-formatos button[aria-pressed=true]").length') == 0
            assert pg.evaluate('() => document.getElementById("salvar-seguir").disabled') is True
            # a prancheta: um clique, salvo no rascunho
            clicar('#lido-quadros button[data-quadro="%s"]' % peca)
            tp._esperar(pg, salvo)
            assert gravado()['quadro'] == peca
            # o quarto de volta pede o sentido: sem ele, nada do giro vai ao rascunho
            clicar(giro(meia, 90))
            assert pg.evaluate('s => !!document.querySelector(s)', giro(meia, 90, 'horario'))
            pg.wait_for_timeout(int(srv.espera_rascunho_ms) + 300)  # numero-neutro: a espera do rascunho e folga
            assert meia['chave'] not in (gravado().get('rotacoes') or {})
            clicar(giro(meia, 90, 'horario'))
            tp._esperar(pg, salvo)
            clicar(giro(largo, 0))
            tp._esperar(pg, salvo)
            pg.wait_for_timeout(int(srv.espera_rascunho_ms) + 300)  # numero-neutro: a espera do rascunho e folga
            assert gravado()['rotacoes'] == {meia['chave']: {'graus': 90, 'sentido': 'horario'},
                                             largo['chave']: {'graus': 0, 'sentido': None}}
            # a pagina nao corre para o lado, e os textos novos nao falam de motor
            assert pg.evaluate('() => document.documentElement.scrollWidth <= window.innerWidth')
            texto = pg.evaluate('() => document.getElementById("passo-lido").innerText')
            assert _sem_travessao(texto)
            pasta = os.environ.get('DESDOBRA_CAPTURA_TELA')
            if pasta:
                pg.screenshot(path=os.path.join(pasta, 'passo-1.png'), full_page=True)
                pg.locator('#bloco-quadros').screenshot(path=os.path.join(pasta, 'pranchetas.png'))
        finally:
            nav.close()


# ------------------------------------------------------------------ revisao dos becos do job novo
def _ctx_da_tela(job):
    """O mesmo contexto e a mesma derivacao em memoria que te.montar monta para as previas."""
    from desdobra.derivacao import formatos as mf
    ctx = te.com_o_passo_2_do_rascunho(job, te.com_o_passo_1_do_rascunho(job, nd.preparar(job, partida=True)))
    specs, arq = mf.specs_do_job(job)
    r = nd.derivar_em_memoria(ctx, specs=specs, arquivo_specs=arq, params=mf.parametros(job, ctx['briefing']),
                              composicoes=False)
    return ctx, r


def _reprovas_da_regra(r):
    return {fid: [v['medidas'] for v in d.get('validacoes') or []
                  if v['nome'] == 'regra_por_funcao' and v['situacao'] == 'reprova']
            for fid, d in r['formatos'].items()}


def test_previa_depois_de_salvar_confere_a_regra_nova_do_design_system(novo):
    """Revisao dos becos, A2: depois de salvar, o DA troca a regra de uma funcao no Design system. A previa monta o
    layout com a regra nova do rascunho e confere contra o mesmo briefing, e nunca contra o gravado no disco: nenhum
    formato reprova regra_por_funcao nem vira devolvido por isso."""
    job, funcoes = novo
    _conteudo, s = _servidor(job)
    try:
        biscoito = tts._entrar(s)
        _ate_salvar(s, biscoito, job, funcoes)
        _ctx, r0 = _ctx_da_tela(job)
        assert all(not v for v in _reprovas_da_regra(r0).values())
        p2 = _passo_2(funcoes)
        p2['design']['titulo']['regra'] = 'largura'  # o DA troca a regra do titulo
        p2.update(_passo_1(_estado(s, biscoito)))
        assert _rascunho(s, biscoito, tr.ler(job, tr.laudo_sha256(job))[0]['familias'], p2) == 200
    finally:
        s.parar()
    ctx, r = _ctx_da_tela(job)
    assert any(x['regra']['valor'] == 'largura' for x in ctx['briefing']['regras_escala'] if x['funcao'] == 'titulo')
    assert all(not v for v in _reprovas_da_regra(r).values()), _reprovas_da_regra(r)
    # a derivacao gravada continua conferindo contra o briefing gravado no disco
    assert nd.preparar(job).get('da_tela') is not True


def _situacoes(s, biscoito, e):
    """{id do formato: (situacao, motivo, variantes da galeria)} das previas do passo 3."""
    saida = {}
    for o in e['orientacoes']:
        for g in o['grupos']:
            for c in g['composicoes']:
                for x in c['formatos']:
                    pv = _previa(s, biscoito, x['id'])
                    saida[x['id']] = (pv['situacao'], (pv.get('devolucao') or {}).get('motivo'),
                                      len(((pv.get('galeria') or {}).get('variantes')) or []))
    return saida


def _familia_de(e, fid):
    return next(g['id'] for o in e['orientacoes'] for g in o['grupos']
                if fid in [x['id'] for c in g['composicoes'] for x in c['formatos']])


def _itens_da_medida(e):
    return [x for x in e['faltam'] if x['texto'] == te.SPEC_POR_CONFIRMAR_FALTA]


def test_formato_com_medida_por_confirmar_tem_estado_proprio_e_item_no_que_falta(novo):
    """Revisao dos becos, A1: o DA confirma a medida de um formato no passo 1. O outro formato continua com a medida
    esperando a confirmacao: a derivacao nunca usa o valor sem confirmacao como se fosse confirmado, e o formato fica
    devolvido com motivo proprio (spec_por_confirmar, e nao formato_sem_folha), sem galeria. A lista do que falta
    nomeia o formato e leva ao passo 1, e o passo 1 diz que a spec dele nao esta confirmada."""
    job, funcoes = novo
    _conteudo, s = _servidor(job)
    try:
        biscoito = tts._entrar(s)
        chave = _confirmar_medida(s, biscoito, job, '640x320')
        assert mb.arquivo_de_specs(job) == mb.ARQUIVO_FORMATOS
        assert _ato(s, biscoito, 'modo_dados', {'modo': 'c'}) == (200, 200)
        p2 = dict(_passo_2(funcoes), **_passo_1(_estado(s, biscoito)))
        assert _rascunho(s, biscoito, {}, p2) == 200
        e = _estado(s, biscoito)
        sit = _situacoes(s, biscoito, e)
        outro = next(f for f in e['lido']['specs']['formatos'] if f['chave'] != chave)
        previa = _previa(s, biscoito, outro['id'])
    finally:
        s.parar()
    confirmado = next(f for f in e['lido']['specs']['formatos'] if f['chave'] == chave)
    assert sit[confirmado['id']][:2] == ('derivado', None)
    assert sit[outro['id']] == ('devolvido', 'spec_por_confirmar', 0)
    assert previa['devolucao']['texto'] == te.texto_da_devolucao('spec_por_confirmar')
    assert confirmado['tem_spec'] is True and outro['tem_spec'] is False
    # o que falta: um item do formato, com a chave dele, que leva ao passo 1
    itens = _itens_da_medida(e)
    assert [x['detalhe'] for x in itens] == [outro['chave']] and itens[0]['ir'] == {'passo': 'lido'}
    assert _sem_travessao(te.SPEC_POR_CONFIRMAR_FALTA) and _sem_travessao(te.texto_da_devolucao('spec_por_confirmar'))
    assert _sem_travessao(nd.O_QUE_FAZER['spec_por_confirmar'])
    assert not any(x['detalhe'] == outro['id'] and x['texto'].startswith('Sem proposta') for x in e['faltam'])


def test_sem_medida_confirmada_nenhum_formato_deriva_do_rascunho(novo):
    """Revisao da correcao, becos 2, 4 e 6: antes de qualquer confirmacao, o rascunho das specs e o arquivo que vale, e
    mesmo assim a derivacao nunca usa a medida sem confirmacao. Todo formato fica spec_por_confirmar, com o item dele
    no que falta, e o passo 1 nunca diz "Com spec confirmada". Confirmar a medida de um formato muda so ele."""
    job, funcoes = novo
    assert mb.arquivo_de_specs(job) == mb.ARQUIVO_RASCUNHO_SPECS
    _conteudo, s = _servidor(job)
    try:
        biscoito = tts._entrar(s)
        assert _ato(s, biscoito, 'modo_dados', {'modo': 'c'}) == (200, 200)
        p2 = dict(_passo_2(funcoes), **_passo_1(_estado(s, biscoito)))
        assert _rascunho(s, biscoito, {}, p2) == 200
        e0 = _estado(s, biscoito)
        sit0 = _situacoes(s, biscoito, e0)
        _confirmar_medida(s, biscoito, job, '640x320')
        e1 = _estado(s, biscoito)
        sit1 = _situacoes(s, biscoito, e1)
    finally:
        s.parar()
    assert len(sit0) == 2 and set(sit0.values()) == {('devolvido', 'spec_por_confirmar', 0)}, sit0
    assert not any(f['tem_spec'] for f in e0['lido']['specs']['formatos'])
    assert sorted(x['detalhe'] for x in _itens_da_medida(e0)) == \
        sorted(f['chave'] for f in e0['lido']['specs']['formatos'])
    # o formato que ganhou a medida deriva; o outro segue como estava, sem sumir de repente
    h = next(f['id'] for f in e1['lido']['specs']['formatos'] if f['chave'].endswith('640x320'))
    v = next(f['id'] for f in e1['lido']['specs']['formatos'] if f['chave'].endswith('300x600'))
    assert sit1[h][:2] == ('derivado', None) and sit1[v] == sit0[v]


def test_familia_com_medida_por_confirmar_nao_e_confirmada_as_cegas(novo):
    """Revisao da correcao, beco 1: a familia que tem formato com a medida por confirmar nao tem galeria para o DA ver.
    O que falta pede a medida, e nunca a confirmacao da familia; "Confirmar familia" e "Salvar e seguir" recusam.
    Depois que o DA confirma a medida, a galeria aparece, e o que falta leva o DA a ela."""
    job, funcoes = novo
    _conteudo, s = _servidor(job)
    try:
        biscoito = tts._entrar(s)
        _confirmar_medida(s, biscoito, job, '640x320')
        assert _ato(s, biscoito, 'modo_dados', {'modo': 'c'}) == (200, 200)
        p2 = dict(_passo_2(funcoes), **_passo_1(_estado(s, biscoito)))
        assert _rascunho(s, biscoito, {}, p2) == 200
        e = _estado(s, biscoito)
        v = next(f['id'] for f in e['lido']['specs']['formatos'] if f['chave'].endswith('300x600'))
        h = next(f['id'] for f in e['lido']['specs']['formatos'] if f['chave'].endswith('640x320'))
        gv, gh = _familia_de(e, v), _familia_de(e, h)
        familias = {g: {'versao': None, 'confirmada': False, 'edicoes': []} for g in (gv, gh)}
        assert _rascunho(s, biscoito, familias, p2) == 200
        pede_familia = [x['detalhe'] for x in e['faltam'] if x['texto'] == te.FAMILIA_SEM_CONFIRMACAO]
        recusa = _ato(s, biscoito, 'familia', {'familia': gv, 'versao': None, 'edicoes': []})
        if gh != gv:
            assert _ato(s, biscoito, 'familia', {'familia': gh, 'versao': None, 'edicoes': []}) == (200, 200)
        salvar = _ato(s, biscoito, 'salvar', {'rascunho': _vista(job)})
        _confirmar_medida(s, biscoito, job, '300x600')
        e2 = _estado(s, biscoito)
        pv = _previa(s, biscoito, v)
        fam = tr.ler(job, tr.laudo_sha256(job))[0]['familias'][gv]
    finally:
        s.parar()
    assert v not in ', '.join(pede_familia), pede_familia
    assert recusa[0] != 200 and salvar[0] != 200 and not (job / mb.ARQUIVO).exists()
    assert not fam.get('confirmada')
    assert pv['situacao'] == 'devolvido' and ((pv.get('galeria') or {}).get('variantes'))
    assert not _itens_da_medida(e2)
    assert [x for x in e2['faltam'] if v in (x.get('detalhe') or '') and x['ir'].get('passo') == 'pecas']


def _pede_familia(e, gid):
    fids = next([x['id'] for c in g['composicoes'] for x in c['formatos']]
                for o in e['orientacoes'] for g in o['grupos'] if g['id'] == gid)
    return [x for x in e['faltam'] if x['texto'] == te.FAMILIA_SEM_CONFIRMACAO and x['detalhe'] == ', '.join(fids)]


def test_folha_trocada_depois_de_salvar_pede_a_familia_de_novo(tmp_path):
    """Revisao 3 da regra spec_por_confirmar: o briefing esta salvo, e a folha do 640x320 e trocada por uma com area
    segura (a medida volta a rascunho). Depois que o DA confirma a medida e a area segura no passo 1, a peca da familia
    e outra: a confirmacao feita sobre a peca de antes nao conta sozinha. O que falta pede a familia de novo e "Salvar
    e seguir" recusa ate o DA confirmar a familia com a peca nova."""
    from desdobra.job import nucleo
    job, funcoes = _criar(tmp_path)
    _conteudo, s = _servidor(job)
    try:
        b = tts._entrar(s)
        _ate_salvar(s, b, job, funcoes)
        e0 = _estado(s, b)
        h = next(f['id'] for f in e0['lido']['specs']['formatos'] if f['chave'].endswith('640x320'))
        gid = _familia_de(e0, h)
        nova = tmp_path / 'nova' / 'mesma.html'
        nova.parent.mkdir()
        nova.write_text(sap.html_ficha('Mesma Exemplo', [('dimensão', '640x320'), ('peso (hosted)', 'até 250KB'),
                                                         ('área segura', '60px')]), encoding='utf-8')
        nucleo.trocar_entrada(job, 'entrada/specs/globo/mesma.html', nova)
        assert nucleo.proxima(job, todas=True).codigo == 0
        for campo in ('dimensao', 'area_segura'):
            alvo = next(x for x in te.specs_pendentes(job) if x['onde'].endswith('640x320') and
                        x['valor_id'].endswith('/' + campo) and not x['leituras'])
            assert _ato(s, b, 'spec_valor', {'valor_id': alvo['valor_id']}) == (200, 200)
        e1 = _estado(s, b)
        salvar = _ato(s, b, 'salvar', {'rascunho': _vista(job)})
        lido_pela_pagina = json.loads(tts._pedir(s, '/api/rascunho', cookie=b)[2])
        versao = tr.versao_gravada(job, gid)
        de_novo = _ato(s, b, 'familia', {'familia': gid, 'versao': versao, 'edicoes': []})
        e2 = _estado(s, b)
    finally:
        s.parar()
    assert _pede_familia(e1, gid), [x['texto'] for x in e1['faltam']]
    assert salvar[0] != 200
    # a pagina recebe a familia sem a confirmacao velha, e o botao volta a confirmar
    assert lido_pela_pagina['rascunho']['familias'][gid]['confirmada'] is False
    assert de_novo == (200, 200) and not _pede_familia(e2, gid)


def test_confirmacao_sem_galeria_nao_vale_quando_a_galeria_aparece(tmp_path):
    """Revisao 3 da regra spec_por_confirmar: um rascunho de antes da regra tem a familia do 300x600 confirmada sem
    versao, de quando a medida dele estava em rascunho e nao havia galeria. Depois que o DA confirma a medida, a
    galeria aparece, e a confirmacao de antes nao conta: o 300x600 segue no que falta e "Salvar e seguir" recusa."""
    job, funcoes = _criar(tmp_path)
    _conteudo, s = _servidor(job)
    try:
        b = tts._entrar(s)
        _confirmar_medida(s, b, job, '640x320')
        assert _ato(s, b, 'modo_dados', {'modo': 'c'}) == (200, 200)
        p2 = dict(_passo_2(funcoes), **_passo_1(_estado(s, b)))
        assert _rascunho(s, b, {}, p2) == 200
        e = _estado(s, b)
        v = next(f['id'] for f in e['lido']['specs']['formatos'] if f['chave'].endswith('300x600'))
        hh = next(f['id'] for f in e['lido']['specs']['formatos'] if f['chave'].endswith('640x320'))
        gv, gh = _familia_de(e, v), _familia_de(e, hh)
        assert gv != gh
        assert _rascunho(s, b, {g: {'versao': None, 'confirmada': False, 'edicoes': []} for g in (gv, gh)}, p2) == 200
        assert _ato(s, b, 'familia', {'familia': gh, 'versao': None, 'edicoes': []}) == (200, 200)
        # o estado de antes da regra: a familia do 300x600 confirmada como a tela de antes gravava (versao None, sem
        # galeria, sem a impressao das pecas)
        dados = json.loads((job / tr.ARQUIVO).read_text(encoding='utf-8'))
        velha = {k: v_ for k, v_ in dados['familias'][gh]['confirmacao'].items() if k != 'pecas'}
        velha['formatos'] = [x['id'] for o in e['orientacoes'] for g in o['grupos'] if g['id'] == gv
                             for c in g['composicoes'] for x in c['formatos']]
        dados['familias'][gv] = {'versao': None, 'confirmada': True, 'edicoes': [], 'confirmacao': velha}
        (job / tr.ARQUIVO).write_text(json.dumps(dados, ensure_ascii=False), encoding='utf-8')
        _confirmar_medida(s, b, job, '300x600')
        e2 = _estado(s, b)
        pv = _previa(s, b, v)
        salvar = _ato(s, b, 'salvar', {'rascunho': _vista(job)})
    finally:
        s.parar()
    assert ((pv.get('galeria') or {}).get('variantes'))
    assert [x for x in e2['faltam'] if v in (x.get('detalhe') or '')], [x['texto'] for x in e2['faltam']]
    assert salvar[0] != 200 and not (job / mb.ARQUIVO).exists()


def test_botao_da_familia_com_spec_por_confirmar_fica_desligado_no_chromium(tmp_path):
    """Revisao 3 da regra spec_por_confirmar: na familia com um formato que espera a spec, o servidor recusa
    "Confirmar a familia". O botao fica desligado e diz o que fazer, e o DA nunca clica para ver a mensagem de tentar
    de novo."""
    from playwright.sync_api import sync_playwright

    import test_tela_galeria as tg
    from desdobra.chromium import navegador
    job, funcoes = _criar(tmp_path)
    _c, s = _servidor(job)
    try:
        b = tts._entrar(s)
        _confirmar_medida(s, b, job, '640x320')
        assert _ato(s, b, 'modo_dados', {'modo': 'c'}) == (200, 200)
        p2 = dict(_passo_2(funcoes), **_passo_1(_estado(s, b)))
        assert _rascunho(s, b, {}, p2) == 200
    finally:
        s.parar()
    conteudo, srv = _servidor(job)
    e = conteudo['estado']
    v = next(f['id'] for f in e['lido']['specs']['formatos'] if f['chave'].endswith('300x600'))
    navegador.apontar_playwright()
    try:
        with sync_playwright() as pw:
            nav, pg = tp._pagina_da_tela(pw, srv, 1600, 900)
            try:
                tg._abrir(pg, e, v)
                tp._esperar(pg, '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""')
                botao = pg.evaluate('() => { const b = document.getElementById("confirmar-familia");'
                                    ' return [b.disabled, b.title]; }')
            finally:
                nav.close()
    finally:
        srv.parar()
    assert botao[0] is True, botao
    assert 'Valores de spec' in botao[1] and _sem_travessao(botao[1])


def test_dimensao_confirmada_com_faixa_em_rascunho_espera_o_da(tmp_path):
    """Revisao da correcao, beco 5: o DA confirma so a dimensao, e a faixa da folha segue em rascunho. Os formatos do
    job levam so a dimensao, e o formato nunca deriva sem a faixa como se a spec estivesse completa: fica
    spec_por_confirmar, sem spec, ate o DA confirmar a faixa."""
    import test_derivacao_apoio as ap
    from desdobra.derivacao import formatos as mf
    chave = 'teste|faixa|480x300'
    y = ap.spec(chave, {'dimensao': {'largura': 480, 'altura': 300}, 'faixas': [{'lado': 'inferior', 'px': 48}]})
    y['campos']['dimensao']['situacao'] = 'confirmado'
    do_job = copy.deepcopy(y)
    do_job['campos'] = {'dimensao': do_job['campos']['dimensao']}  # o que specs.modelo.formatos_do_job grava

    def gravar():
        (tmp_path / 'specs').mkdir(exist_ok=True)
        (tmp_path / mb.ARQUIVO_RASCUNHO_SPECS).write_text(json.dumps({'formatos': [y]}), encoding='utf-8')
        (tmp_path / mb.ARQUIVO_FORMATOS).write_text(json.dumps({'tipo': 'formatos_do_job', 'formatos': [do_job]}),
                                                    encoding='utf-8')
        specs, arq = mf.specs_do_job(tmp_path)
        return nd.derivar_em_memoria(nd.contexto(ap.laudo(), b, pasta=tmp_path), specs=specs, arquivo_specs=arq)
    b = ap.briefing(formatos=[ap.formato('faixa', 480, 300, chave=chave)])
    d = gravar()
    assert mf.chaves_por_confirmar(tmp_path) == {chave}
    f = d['formatos']['faixa']
    assert (f['situacao'], f['devolucao']['motivo'], f['formato']['tem_spec']) == \
        ('devolvido', 'spec_por_confirmar', False)
    assert [x['motivo'] for x in d['devolucoes']] == ['spec_por_confirmar']
    # com a faixa confirmada, o formato deriva com a faixa
    y['campos']['faixas']['situacao'] = 'confirmado'
    do_job['campos']['faixas'] = y['campos']['faixas']
    f = gravar()['formatos']['faixa']
    assert mf.chaves_por_confirmar(tmp_path) == set()
    assert (f['devolucao'] or {}).get('motivo') != 'spec_por_confirmar' and f['areas']['faixas']


def _specs_de_rascunho(pasta, chaves):
    (pasta / 'specs').mkdir(parents=True, exist_ok=True)
    formatos = [{'chave': c, 'campos': {'dimensao': {'unidade': 'px', 'valor': {'largura': int(c.rsplit('|', 1)[1].split('x')[0]),
                                                                                 'altura': int(c.rsplit('|', 1)[1].split('x')[1])}}}}
                for c in chaves]
    (pasta / mb.ARQUIVO_RASCUNHO_SPECS).write_text(json.dumps({'formatos': formatos}), encoding='utf-8')


def test_id_do_formato_nao_depende_da_ordem_da_folha(tmp_path):
    """Revisao dos becos, A3: duas chaves que so mudam em maiuscula ou pontuacao dao o mesmo id base. O sufixo vai pela
    ordem da chave exata, e nunca pela ordem da folha; as chaves sem choque ficam com o id de antes."""
    a, b, c = 'Globo|Meia|300x600', 'GLOBO|meia|300x600', 'Globo|Mesma|640x320'
    ids = []
    for n, ordem in enumerate(((a, b, c), (c, b, a), (b, c, a))):
        pasta = tmp_path / str(n)
        _specs_de_rascunho(pasta, ordem)
        saida = mb.formatos_das_specs(pasta)
        assert [f['chave'] for f in saida] == list(ordem)  # a lista segue na ordem da folha
        ids.append({f['chave']: f['id'] for f in saida})
    assert ids[0] == ids[1] == ids[2]
    assert ids[0][c] == 'globo-mesma-640x320'
    assert sorted((ids[0][a], ids[0][b])) == ['globo-meia-300x600', 'globo-meia-300x600-2']


def test_id_do_formato_segue_o_briefing_gravado_quando_a_folha_muda(tmp_path):
    """Revisao da correcao, beco 3: a folha nova acrescenta uma chave que da o mesmo id base de uma chave que o briefing
    gravado ja tem. A chave de antes fica com o id de antes (a retomada leva as mestres, as quebras e as familias pelo
    id), e o id de uma chave que saiu da folha nunca vai para outra chave."""
    a, b = 'Globo|Meia|300x600', 'GLOBO|meia|300x600'
    _specs_de_rascunho(tmp_path / 'v1', [a])
    _specs_de_rascunho(tmp_path / 'v2', [a, b])
    _specs_de_rascunho(tmp_path / 'v3', [b])
    id1 = {f['chave']: f['id'] for f in mb.formatos_das_specs(tmp_path / 'v1')}
    id2 = {f['chave']: f['id'] for f in mb.formatos_das_specs(tmp_path / 'v2', ids_de_antes=id1)}
    id3 = {f['chave']: f['id'] for f in mb.formatos_das_specs(tmp_path / 'v3', ids_de_antes=id1)}
    assert id1 == {a: 'globo-meia-300x600'}
    assert id2 == {a: 'globo-meia-300x600', b: 'globo-meia-300x600-2'}
    assert id3 == {b: 'globo-meia-300x600-2'}
    # sem briefing de antes, o id nao depende da ordem da folha (A3)
    assert {f['chave']: f['id'] for f in mb.formatos_das_specs(tmp_path / 'v2')} == \
        {a: 'globo-meia-300x600-2', b: 'globo-meia-300x600'}
