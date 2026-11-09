# -*- coding: utf-8 -*-
"""O id da familia da tela preso aos formatos dela (revisao do M7b, fase A): o id deixa de ser a posicao do grupo
na aba (desdobra.tela.estado.abas). Cada grupo novo fica com o id ja conhecido no job (o rascunho da tela e o briefing
gravado, cada um com os formatos dele) com que divide mais formatos, e o grupo sem formato em comum com nenhum id
conhecido ganha o menor '<orientacao>-<n>' livre.

Criterios cobertos aqui:
  - o job novo, sem rascunho nem briefing, numera como antes (a posicao do grupo);
  - o formato mais largo que entra no passo 1 nao renumera as familias que ja existiam, e o salvar depois dele guarda
    a derivacao dos outros formatos;
  - a familia que se divide: a parte que divide mais formatos fica com o id e as edicoes, a outra parte ganha id novo
    e parte da proposta; a que se junta: o id que fica guarda as edicoes, e as do outro id continuam no rascunho;
  - o formato que sai do job, e a edicao que nunca passa para um grupo sem formato em comum com o de quando foi feita;
  - o job velho, com os ids de posicao no rascunho ou no briefing, continua valendo;
  - a familia que muda de formatos perde a confirmacao, e a tela diz ao DA o que entrou ou saiu;
  - o formato que vai para outra familia, e mexido la, e volta: entrou de novo, mesmo na lista velha da familia
    (cedidos no rascunho), e a confirmacao velha nao vale;
  - a frase so fala de edicao quando a outra familia tem edicao;
  - a frase e a marca saem do estado e da pagina quando o DA confirma a familia, e a pagina deixa de contar a
    confirmacao que o servidor nao conta mais (o formato que entra com a tela aberta).
Tudo sintetico: as derivacoes em memoria inventadas aqui e o job de test_tela_salvar (o PSD de test_tela_palco e a
fonte de autoteste do motor)."""
import json

import test_derivacao_apoio as ap
import test_tela_palco as tp
import test_tela_salvar as tsv
import test_tela_servidor as tts
from desdobra import arquivos, contratos
from desdobra.briefing import historico as bh
from desdobra.briefing import modelo as mb
from desdobra.briefing import salvar as bs
from desdobra.derivacao import nucleo as nd
from desdobra.tela import estado as te
from desdobra.tela import rascunho as tr
from test_tela_salvar import job, modelo  # noqa: F401 - as fixtures do job de test_tela_salvar

ROT0 = {'graus': 0, 'sentido': None}
TRAVESSOES = (chr(0x2013), chr(0x2014))  # numero-neutro: meia-risca e travessao


# ------------------------------------------------------------------ abas com derivacoes inventadas
def _derivacao(largura, altura):
    return {'formato': {'composicao': [largura, altura], 'largura': largura, 'altura': altura,
                        'rotacao': {'graus': 0, 'sentido': None}},
            'situacao': 'derivado', 'mestre': {'id': 'kv', 'tipo': 'kv'}, 'caminho': 'solver'}


def _abas(formatos, conhecidas=None, **marcas):
    b = {'formatos': [{'id': fid} for fid, _l, _a in formatos]}
    ds = {fid: _derivacao(lg, al) for fid, lg, al in formatos}
    return te.abas(None, b, ds, conhecidas=conhecidas, **marcas)


def _grupos(orientacoes):
    """[(id, [formatos], aviso)] na ordem das abas."""
    return [(g['id'], [x['id'] for co in g['composicoes'] for x in co['formatos']], g['aviso'])
            for o in orientacoes for g in o['grupos']]


def _ids(orientacoes):
    return {gid: sorted(fids) for gid, fids, _av in _grupos(orientacoes)}


def _avisos(orientacoes):
    return {gid: av for gid, _f, av in _grupos(orientacoes)}


# horizontais de proporcao 2,0, 2,07, 2,13, 3,0 e 5,0: os tres primeiros cabem num grupo so (amplitude 0,13)
A, A2, A3 = ('a', 600, 300), ('a2', 620, 300), ('a3', 640, 300)
B, C, D = ('b', 900, 300), ('c', 1500, 300), ('d', 610, 300)
V, Q = ('v', 300, 600), ('q', 300, 300)


def test_job_novo_numera_pela_posicao_como_antes():
    esperado = [('horizontal-1', ['b'], ''), ('horizontal-2', ['a'], ''), ('quadrado-1', ['q'], ''),
                ('vertical-1', ['v'], '')]
    assert _grupos(_abas([A, B, V, Q])) == esperado
    assert _grupos(_abas([A, B, V, Q], conhecidas={})) == esperado


def test_formato_mais_largo_nao_renumera_as_familias_conhecidas():
    # pela posicao, c (o mais largo) tomaria horizontal-1 e empurraria b e a
    assert _ids(_abas([A, B, C])) == {'horizontal-1': ['c'], 'horizontal-2': ['b'], 'horizontal-3': ['a']}
    abas = _abas([A, B, C], conhecidas={'horizontal-1': ['b'], 'horizontal-2': ['a']})
    assert _ids(abas) == {'horizontal-1': ['b'], 'horizontal-2': ['a'], 'horizontal-3': ['c']}
    # a ordem das abas continua pela proporcao; so o id fica
    assert [gid for gid, _f, _a in _grupos(abas)] == ['horizontal-3', 'horizontal-1', 'horizontal-2']
    assert set(_avisos(abas).values()) == {''}


def test_familia_dividida_fica_com_a_parte_maior():
    abas = _abas([A, A2, B], conhecidas={'horizontal-1': ['a', 'a2', 'b']})
    assert _ids(abas) == {'horizontal-1': ['a', 'a2'], 'horizontal-2': ['b']}
    av = _avisos(abas)
    assert 'saiu o formato b' in av['horizontal-1'] and 'confirme' in av['horizontal-1']
    assert 'b' in av['horizontal-2'] and 'outra família' in av['horizontal-2']
    assert 'proposta do desdobra' in av['horizontal-2']


def test_familias_juntadas_ficam_com_o_id_que_divide_mais():
    abas = _abas([A, A2, A3, B], conhecidas={'horizontal-1': ['a', 'a2'], 'horizontal-3': ['a3'],
                                             'horizontal-2': ['b']}, editadas={'horizontal-3'})
    assert _ids(abas) == {'horizontal-1': ['a', 'a2', 'a3'], 'horizontal-2': ['b']}
    av = _avisos(abas)
    assert 'entrou o formato a3' in av['horizontal-1'] and 'outra família' in av['horizontal-1']
    assert av['horizontal-2'] == ''
    # o id que sumiu continua reservado: o formato novo nunca herda as edicoes dele
    abas = _abas([A, A2, A3, D, B, C], conhecidas={'horizontal-1': ['a', 'a2'], 'horizontal-3': ['a3'],
                                                   'horizontal-2': ['b']})
    assert _ids(abas)['horizontal-4'] == ['c']


def test_empate_no_juntar_e_decidido_sempre_igual():
    um = _ids(_abas([A, A2], conhecidas={'horizontal-1': ['a'], 'horizontal-2': ['a2']}))
    outro = _ids(_abas([A, A2], conhecidas={'horizontal-2': ['a2'], 'horizontal-1': ['a']}))
    assert um == outro == {'horizontal-1': ['a', 'a2']}


def test_formato_que_saiu_do_job():
    abas = _abas([A, B], conhecidas={'horizontal-1': ['a', 'a2'], 'horizontal-2': ['b']})
    assert _ids(abas) == {'horizontal-1': ['a'], 'horizontal-2': ['b']}
    av = _avisos(abas)
    assert 'saiu o formato a2' in av['horizontal-1']
    assert av['horizontal-2'] == ''


def test_edicao_nunca_vai_para_grupo_sem_formato_em_comum():
    # a saiu e d entrou na mesma posicao: d nao fica com horizontal-1, que era de a
    abas = _abas([D, B], conhecidas={'horizontal-1': ['a'], 'horizontal-2': ['b']})
    assert _ids(abas) == {'horizontal-2': ['b'], 'horizontal-3': ['d']}
    # o id de outra orientacao nunca vai para o grupo desta: o formato girado parte da proposta
    abas = _abas([V], conhecidas={'horizontal-1': ['v']})
    assert _ids(abas) == {'vertical-1': ['v']}
    # o id que nao diz orientacao (o briefing de teste) segue os formatos
    assert _ids(_abas([V], conhecidas={'familia-v': ['v']})) == {'familia-v': ['v']}


def test_job_velho_com_ids_de_posicao_sem_formatos():
    # o rascunho de antes desta revisao nao guarda os formatos da familia sem confirmacao: o id fica com o grupo da
    # mesma posicao, como antes
    abas = _abas([A, B], conhecidas={'horizontal-1': None, 'horizontal-2': None})
    assert _ids(abas) == {'horizontal-1': ['b'], 'horizontal-2': ['a']}
    assert set(_avisos(abas).values()) == {''}


def test_aviso_sem_travessao_e_com_artigo():
    abas = _abas([A, A2, A3], conhecidas={'horizontal-1': ['a', 'a2', 'b', 'c'], 'horizontal-2': ['a3']})
    texto = _avisos(abas)['horizontal-1']
    assert 'entrou o formato a3' in texto and 'saíram os formatos b e c' in texto
    assert not any(t in texto for t in TRAVESSOES)


def test_formato_que_volta_de_outra_familia_avisa_mesmo_na_lista_velha():
    # horizontal-1 era [a, a2] e foi confirmada; a2 saiu para horizontal-2, que o DA editou depois (a2 ficou cedido
    # por horizontal-1, que nao foi tocada e guarda a lista velha). a2 volta: a familia mudou desde a ultima vez
    conhecidas = {'horizontal-1': ['a', 'a2'], 'horizontal-2': ['a2']}
    abas = _abas([A, A2], conhecidas=conhecidas, editadas={'horizontal-2'}, cedidos={'horizontal-1': ['a2']})
    assert _ids(abas) == {'horizontal-1': ['a', 'a2']}
    texto = _avisos(abas)['horizontal-1']
    assert 'entrou o formato a2' in texto and 'confirme' in texto, texto
    assert 'O que você editou para o formato a2 em outra família' in texto, texto
    # enquanto a2 esta na outra familia, horizontal-1 diz que ele saiu, e horizontal-2 nao muda de frase
    abas = _abas([A, ('a2', 900, 300)], conhecidas=conhecidas, editadas={'horizontal-2'},
                 cedidos={'horizontal-1': ['a2']})
    assert _ids(abas) == {'horizontal-1': ['a'], 'horizontal-2': ['a2']}
    assert 'saiu o formato a2' in _avisos(abas)['horizontal-1'] and _avisos(abas)['horizontal-2'] == ''


def test_frase_so_fala_de_edicao_que_existe():
    # as duas familias se juntam, e a outra nunca teve edicao (so a versao escolhida, ou so o briefing gravado)
    texto = _avisos(_abas([A, A2], conhecidas={'horizontal-1': ['a'], 'horizontal-2': ['a2']}))['horizontal-1']
    assert 'entrou o formato a2' in texto and 'confirme' in texto, texto
    assert 'editou' not in texto and 'edições' not in texto, texto
    # a parte que sai de uma familia sem edicao: nova, da proposta, sem falar das edicoes de la
    texto = _avisos(_abas([A, B], conhecidas={'horizontal-1': ['a', 'b']}))['horizontal-2']
    assert 'outra família' in texto and 'proposta do desdobra' in texto, texto
    assert 'edições' not in texto, texto
    # com edicao na familia de onde ele saiu, a frase diz que elas ficam la
    texto = _avisos(_abas([A, B], conhecidas={'horizontal-1': ['a', 'b']}, editadas={'horizontal-1'}))['horizontal-2']
    assert 'sem as edições de lá' in texto, texto


# ------------------------------------------------------------------ o rascunho guarda os formatos de cada familia
LAUDO = '1' * 64
JOB = 'a' * 32


def _gravar(pasta, familias, tela):
    return tr.gravar(pasta, {'job_id': JOB, 'laudo_sha256': LAUDO, 'familias': familias}, job_id=JOB,
                     laudo_atual=LAUDO, origem='rascunho', familias_da_tela=tela)


def _fam(edicoes=(), **extra):
    return dict({'versao': None, 'confirmada': False, 'edicoes': list(edicoes)}, **extra)


def test_rascunho_guarda_os_formatos_que_a_tela_mostrava(tmp_path):
    mover = {'elemento': 'el1', 'acao': 'mover', 'dx': 0.1, 'dy': 0.0}
    # os formatos sao do servidor: o que a pagina manda e jogado fora
    g = _gravar(tmp_path, {'horizontal-1': _fam(formatos=['x'])}, {'horizontal-1': ['a', 'b']})
    assert g['familias']['horizontal-1']['formatos'] == ['a', 'b']
    # a familia que nao mudou guarda os formatos de quando o DA mexeu nela, mesmo com outros formatos na tela agora
    g = _gravar(tmp_path, {'horizontal-1': _fam(), 'horizontal-2': _fam([mover])},
                {'horizontal-1': ['a', 'b', 'c'], 'horizontal-2': ['d']})
    assert g['familias']['horizontal-1']['formatos'] == ['a', 'b']
    assert g['familias']['horizontal-2']['formatos'] == ['d']
    # a edicao nova leva os formatos de agora; a familia que a tela nao mostra mais fica como estava
    g = _gravar(tmp_path, {'horizontal-1': _fam([mover]), 'horizontal-2': _fam([mover])},
                {'horizontal-1': ['a', 'b', 'c']})
    assert g['familias']['horizontal-1']['formatos'] == ['a', 'b', 'c']
    assert g['familias']['horizontal-2'] == dict(_fam([mover]), formatos=['d'])
    contratos.validar(json.loads((tmp_path / tr.ARQUIVO).read_text(encoding='utf-8')), tr.ESQUEMA)


def test_rascunho_marca_o_formato_que_outra_familia_levou(tmp_path):
    mover = {'elemento': 'el1', 'acao': 'mover', 'dx': 0.1, 'dy': 0.0}
    _gravar(tmp_path, {'horizontal-1': _fam()}, {'horizontal-1': ['a', 'b']})
    # b vai para horizontal-2 e o DA mexe nela; horizontal-1 nao foi tocada e guarda a lista de quando foi
    g = _gravar(tmp_path, {'horizontal-1': _fam(), 'horizontal-2': _fam([mover])},
                {'horizontal-1': ['a'], 'horizontal-2': ['b']})
    assert g['familias']['horizontal-1']['formatos'] == ['a', 'b']
    assert g['familias']['horizontal-1']['cedidos'] == ['b']
    assert 'cedidos' not in g['familias']['horizontal-2']
    # o que a pagina manda nesse campo e jogado fora, e a marca fica ate o DA mexer de novo em horizontal-1
    g = _gravar(tmp_path, {'horizontal-1': _fam(cedidos=[]), 'horizontal-2': _fam([mover])},
                {'horizontal-1': ['a', 'b']})
    assert g['familias']['horizontal-1']['cedidos'] == ['b']
    # a confirmacao velha de horizontal-1 (feita com a e b) nao vale quando b volta
    conf = {'origem': 'da', 'meio': 'tela', 'em': 'x', 'formatos': ['a', 'b']}
    f = dict(g['familias']['horizontal-1'], confirmada=True, confirmacao=conf)
    assert tr.confirmada_para(f, ['a', 'b']) is False
    assert tr.confirmada_para(dict(f, cedidos=[]), ['a', 'b']) is True
    # mexer em horizontal-1 tira a marca, e a familia passa a ser dos formatos de agora
    g = _gravar(tmp_path, {'horizontal-1': _fam([mover]), 'horizontal-2': _fam([mover])},
                {'horizontal-1': ['a', 'b']})
    assert g['familias']['horizontal-1']['formatos'] == ['a', 'b']
    assert 'cedidos' not in g['familias']['horizontal-1']
    assert g['familias']['horizontal-2']['cedidos'] == ['b']
    contratos.validar(json.loads((tmp_path / tr.ARQUIVO).read_text(encoding='utf-8')), tr.ESQUEMA)


# ------------------------------------------------------------------ o job sintetico da tela
def _mexer_formatos(job, mexer):
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    mexer(b['formatos'])
    contratos.gravar(job / mb.ARQUIVO, b, 'briefing/1')


def _por_formato(conteudo):
    return {fid: gid for gid, f in conteudo['familias'].items() for fid in f['formatos']}


def _grupo(estado, gid):
    return next(g for o in estado['orientacoes'] for g in o['grupos'] if g['id'] == gid)


def _shas(job, fids):
    return {fid: arquivos.sha256_arquivo(job / nd.PASTA / ('%s.json' % fid)) for fid in fids}


def test_formato_mais_largo_no_passo_1_nao_renumera_e_o_salvar_guarda_os_outros(job, modelo):
    conteudo = te.montar(job)
    s = tsv._servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        tsv._preparar_rascunho(job, modelo, s, biscoito, conteudo)
        assert tsv._salvar(s, biscoito, job)[1] == 200
    finally:
        s.parar()
    antes = _por_formato(conteudo)
    velhos = sorted(antes)
    shas = _shas(job, velhos)
    _mexer_formatos(job, lambda fs: fs.append(ap.formato('largo', 1600, 320, rotacao=ROT0)))
    novo = te.montar(job)
    depois = _por_formato(novo)
    # pela posicao, o grupo de largo (o mais largo) tomaria o id do grupo de mesma
    b = mb.ler(job)
    ds = {fid: contratos.ler(job / nd.PASTA / ('%s.json' % fid), nd.ESQUEMA) for fid in velhos}
    ds['largo'] = dict(ds['mesma'], formato=dict(ds['mesma']['formato'], composicao=[1600, 320]))
    pela_posicao = {x['id']: g['id'] for o in te.abas(None, b, ds) for g in o['grupos']
                    for co in g['composicoes'] for x in co['formatos']}
    assert pela_posicao['mesma'] != antes['mesma']
    assert {fid: depois[fid] for fid in velhos} == antes
    assert depois['largo'] not in antes.values()
    # as familias de antes continuam confirmadas; so a nova pede a confirmacao
    pend = bs.pendencias(job, novo)
    assert pend == [{'codigo': 'familia_sem_confirmacao', 'familia': depois['largo']}], pend
    assert {g['aviso'] for o in novo['estado']['orientacoes'] for g in o['grupos']} == {''}
    s = tsv._servidor(job, novo)
    try:
        biscoito = tts._entrar(s)
        f = novo['familias'][depois['largo']]
        versao = f['versoes'][0] if f['versoes'] else None
        familias = dict(tr.ler(job, s.laudo_sha256)[0]['familias'],
                        **{depois['largo']: {'versao': versao, 'confirmada': False, 'edicoes': []}})
        assert tsv._gravar_rascunho(s, biscoito, familias, tsv._passo_2(modelo['funcoes'])) == 200
        assert tsv._ato(s, biscoito, 'familia', {'familia': depois['largo'], 'versao': versao,
                                                 'edicoes': []})[1] == 200
        assert tsv._salvar(s, biscoito, job)[1] == 200
    finally:
        s.parar()
    assert bh.ler(job)['entradas'][-1]['formatos_afetados'] == ['largo']
    assert _shas(job, velhos) == shas
    from desdobra.render import derivado
    for fid in velhos:
        assert derivado.montar(job, fid)[1] == [], fid


def test_formato_que_entra_na_familia_tira_a_confirmacao_e_a_tela_avisa(job, modelo):
    conteudo = te.montar(job)
    gv = tsv._familia_de(conteudo, 'v1')
    s = tsv._servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        tsv._preparar_rascunho(job, modelo, s, biscoito, conteudo)
    finally:
        s.parar()
    familias = {g: f['formatos'] for g, f in conteudo['familias'].items()}
    assert te.familias_confirmadas(job, familias) == set(familias)
    _mexer_formatos(job, lambda fs: fs.append(ap.formato('v4', 182, 320, rotacao=ROT0)))
    novo = te.montar(job)
    assert _por_formato(novo) == dict(_por_formato(conteudo), v4=gv)
    agora = {g: f['formatos'] for g, f in novo['familias'].items()}
    pecas = {g: f['pecas'] for g, f in novo['familias'].items()}
    # a confirmacao foi feita sobre outros formatos e outras pecas: nao conta, e as outras familias continuam
    assert novo['familias'][gv]['pecas'] != conteudo['familias'][gv]['pecas']
    assert te.familias_confirmadas(job, agora, (), pecas) == set(agora) - {gv}
    assert bs.pendencias(job, novo) == [{'codigo': 'familia_sem_confirmacao', 'familia': gv}]
    # a frase da tela, no grupo e na familia do conteudo
    aviso = _grupo(novo['estado'], gv)['aviso']
    assert 'entrou o formato v4' in aviso and 'confirme' in aviso, aviso
    assert not any(t in aviso for t in TRAVESSOES)
    assert novo['familias'][gv]['aviso'] == aviso
    assert {g['aviso'] for o in novo['estado']['orientacoes'] for g in o['grupos'] if g['id'] != gv} == {''}
    assert any(x['texto'] == te.FAMILIA_SEM_CONFIRMACAO and 'v4' in x['detalhe'] for x in novo['estado']['faltam'])


def test_edicao_da_familia_nao_passa_para_o_formato_que_tomou_o_lugar(job, modelo):
    conteudo = te.montar(job)
    gh = tsv._familia_de(conteudo, 'mesma')
    apagar = [{'elemento': tsv._logo(conteudo, gh), 'acao': 'apagar'}]
    s = tsv._servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        escolhas = tsv._escolhas(conteudo)
        escolhas[gh] = dict(escolhas[gh], edicoes=apagar)
        assert tsv._gravar_rascunho(s, biscoito, escolhas, tsv._passo_2(modelo['funcoes'])) == 200
    finally:
        s.parar()

    def trocar(fs):
        fs[:] = [f for f in fs if f['id'] != 'mesma'] + [ap.formato('largo', 1600, 320, rotacao=ROT0)]
    _mexer_formatos(job, trocar)
    novo = te.montar(job)
    assert _por_formato(novo)['largo'] != gh
    assert gh not in novo['familias']
    # as edicoes de mesma continuam no rascunho, guardadas para quando ela voltar
    assert tr.ler(job, tr.laudo_sha256(job))[0]['familias'][gh]['edicoes'] == apagar
    _mexer_formatos(job, lambda fs: fs.append(ap.formato('mesma', 640, 320, rotacao=ROT0)))
    assert _por_formato(te.montar(job))['mesma'] == gh


def test_job_velho_com_ids_de_posicao(job, modelo):
    conteudo = te.montar(job)
    s = tsv._servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        tsv._preparar_rascunho(job, modelo, s, biscoito, conteudo)
        assert tsv._salvar(s, biscoito, job)[1] == 200
    finally:
        s.parar()
    antes = _por_formato(conteudo)
    # o rascunho de antes desta revisao: sem os formatos da familia nem na confirmacao; so o briefing gravado sabe
    dados = json.loads((job / tr.ARQUIVO).read_text(encoding='utf-8'))
    for f in dados['familias'].values():
        f.pop('formatos', None)
        (f.get('confirmacao') or {}).pop('formatos', None)
    contratos.gravar(job / tr.ARQUIVO, dados, tr.ESQUEMA)
    assert _por_formato(te.montar(job)) == antes
    _mexer_formatos(job, lambda fs: fs.append(ap.formato('largo', 1600, 320, rotacao=ROT0)))
    depois = _por_formato(te.montar(job))
    assert {fid: depois[fid] for fid in antes} == antes


def _remedir(job, fid, largura, altura):
    def mexer(fs):
        for f in fs:
            if f['id'] == fid:
                f.clear()
                f.update(ap.formato(fid, largura, altura, rotacao=ROT0))
    _mexer_formatos(job, mexer)


def _mexer_e_confirmar(job, modelo, conteudo, gid, edicoes, versao=None):
    """O DA escolhe a versao da familia (a primeira da galeria, sem versao), faz estas edicoes e confirma, pelo
    servidor de teste (sem render)."""
    s = tsv._servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        f = conteudo['familias'][gid]
        versao = versao or (f['versoes'][0] if f['versoes'] else None)
        familias = dict(tr.ler(job, s.laudo_sha256)[0]['familias'],
                        **{gid: {'versao': versao, 'confirmada': False, 'edicoes': edicoes}})
        assert tsv._gravar_rascunho(s, biscoito, familias, tsv._passo_2(modelo['funcoes'])) == 200
        assert tsv._ato(s, biscoito, 'familia', {'familia': gid, 'versao': versao, 'edicoes': edicoes})[1] == 200
    finally:
        s.parar()


def test_formato_que_volta_para_a_familia_velha_tira_a_confirmacao_e_avisa(job, modelo):
    conteudo = te.montar(job)
    gv = tsv._familia_de(conteudo, 'v1')
    s = tsv._servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        tsv._preparar_rascunho(job, modelo, s, biscoito, conteudo)
    finally:
        s.parar()
    assert sorted(conteudo['familias'][gv]['formatos']) == ['v1', 'v2', 'v3']
    # v3 fica mais estreito no passo 1 e sai da familia; o DA edita e confirma a familia nova dele, e gv fica parada
    _remedir(job, 'v3', 240, 320)
    meio = te.montar(job)
    gn = _por_formato(meio)['v3']
    assert gn != gv and _por_formato(meio)['v1'] == gv
    edicoes = [{'elemento': tsv._titulo(meio, gn), 'acao': 'mover', 'dx': 0.0, 'dy': 0.08}]
    _mexer_e_confirmar(job, modelo, meio, gn, edicoes)
    # v3 volta para a medida de antes, e as familias se juntam em gv
    _remedir(job, 'v3', 172, 320)
    novo = te.montar(job)
    assert _por_formato(novo)['v3'] == gv and gn not in novo['familias']
    aviso = _grupo(novo['estado'], gv)['aviso']
    assert 'entrou o formato v3' in aviso and 'confirme' in aviso, aviso
    assert 'O que você editou para o formato v3 em outra família' in aviso, aviso
    # a confirmacao velha de gv (feita com v3, antes das edicoes de gn) nao vale, e as edicoes de gn ficam guardadas
    assert {'codigo': 'familia_sem_confirmacao', 'familia': gv} in bs.pendencias(job, novo)
    assert tr.ler(job, tr.laudo_sha256(job))[0]['familias'][gn]['edicoes'] == edicoes


def test_dividir_e_juntar_sem_edicao_na_outra_familia(job, modelo):
    conteudo = te.montar(job)
    gv = tsv._familia_de(conteudo, 'v1')
    s = tsv._servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        tsv._preparar_rascunho(job, modelo, s, biscoito, conteudo)
    finally:
        s.parar()
    _remedir(job, 'v3', 100, 320)
    meio = te.montar(job)
    gn = _por_formato(meio)['v3']
    # a familia nova de v3 so tem a versao escolhida e a confirmacao; gv e confirmada de novo sem v3
    _mexer_e_confirmar(job, modelo, meio, gn, [])
    _mexer_e_confirmar(job, modelo, meio, gv, tr.edicoes_gravadas(job, gv), tr.versao_gravada(job, gv))
    _remedir(job, 'v3', 172, 320)
    novo = te.montar(job)
    assert _por_formato(novo)['v3'] == gv
    aviso = _grupo(novo['estado'], gv)['aviso']
    assert 'entrou o formato v3' in aviso and 'confirme' in aviso, aviso
    assert 'editou' not in aviso and 'edições' not in aviso, aviso
    assert {'codigo': 'familia_sem_confirmacao', 'familia': gv} in bs.pendencias(job, novo)


def _estado_servido(s, biscoito):
    codigo, _cab, corpo = tts._pedir(s, '/api/estado', cookie=biscoito)
    assert codigo == 200
    return json.loads(corpo)


def test_aviso_sai_do_estado_depois_de_confirmar(job, modelo):
    conteudo = te.montar(job)
    s = tsv._servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        tsv._preparar_rascunho(job, modelo, s, biscoito, conteudo)
    finally:
        s.parar()
    _mexer_formatos(job, lambda fs: fs.append(ap.formato('v4', 182, 320, rotacao=ROT0)))
    novo = te.montar(job)
    gv = tsv._familia_de(novo, 'v1')
    s = tsv._servidor(job, novo)
    try:
        biscoito = tts._entrar(s)
        assert _grupo(_estado_servido(s, biscoito), gv)['aviso']
        f = tr.ler(job, s.laudo_sha256)[0]['familias'][gv]
        assert tsv._ato(s, biscoito, 'familia', {'familia': gv, 'versao': f['versao'],
                                                 'edicoes': f['edicoes']})[1] == 200
        # o estado depois do ato (e o da pagina recarregada) ja nao pede a confirmacao nem diz que a familia mudou
        e = _estado_servido(s, biscoito)
        assert not any(x['texto'] == te.FAMILIA_SEM_CONFIRMACAO for x in e['faltam'])
        assert _grupo(e, gv)['aviso'] == ''
        assert novo['familias'][gv]['aviso'] == ''
        # os ids e os formatos das familias sao os mesmos: so a frase mudou
        assert {g['id']: g['composicoes'] for o in e['orientacoes'] for g in o['grupos']} == \
            {g['id']: g['composicoes'] for o in novo['estado']['orientacoes'] for g in o['grupos']}
    finally:
        s.parar()


# ------------------------------------------------------------------ a frase na pagina
def test_aviso_da_familia_aparece_na_pagina(job, modelo):
    from playwright.sync_api import sync_playwright

    import test_tela_galeria as tg
    from desdobra.chromium import navegador
    from desdobra.tela import atos as ta
    from desdobra.tela import servidor as ts
    conteudo = te.montar(job)
    s = tsv._servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        tsv._preparar_rascunho(job, modelo, s, biscoito, conteudo)
    finally:
        s.parar()
    _mexer_formatos(job, lambda fs: fs.append(ap.formato('v4', 182, 320, rotacao=ROT0)))
    novo = te.montar(job)
    gv = tsv._familia_de(novo, 'v1')
    navegador.apontar_playwright()
    with ts.ServidorTela(novo, pasta=job, modo_teste=True, atos=ta.atos_do_job(job, conteudo=novo)) as srv, \
            sync_playwright() as pw:
        nav, pg = tp._pagina_da_tela(pw, srv, 2048, 720)  # numero-neutro: a tela do Duda (decisao 157)
        try:
            tg._abrir(pg, novo['estado'], 'mesma')
            assert pg.evaluate('() => document.getElementById("aviso-familia").hidden') is True
            tg._abrir(pg, novo['estado'], 'v1')
            assert pg.evaluate('() => document.getElementById("aviso-familia").hidden') is False
            texto = pg.evaluate('() => document.getElementById("aviso-familia").textContent')
            assert texto == _grupo(novo['estado'], gv)['aviso']
            marca = pg.evaluate('g => document.querySelector(\'#composicoes [data-grupo="\' + g + \'"]\')'
                                '.classList.contains("mudou")', gv)
            assert marca is True
        finally:
            nav.close()


def _confirmar_na_pagina(pg, seletor):
    pg.evaluate('s => document.querySelector(s).click()', seletor)
    tp._esperar(pg, '() => document.getElementById("confirmacao").open ? "1" : ""')
    pg.evaluate('''() => Array.from(document.querySelectorAll("#confirmacao button"))
        .find(b => b.textContent === "Confirmar").click()''')
    tp._esperar(pg, '() => document.documentElement.dataset.estadoAto === "feito" ? "1" : ""')


BOTAO_DA_FAMILIA = ('() => [document.getElementById("confirmar-familia").textContent, '
                    'document.getElementById("confirmar-familia").disabled]')
AVISO_NA_PAGINA = ('() => [document.getElementById("aviso-familia").hidden, '
                   'Array.from(document.querySelectorAll("#composicoes .mini-mudou")).length]')
SALVAR_DESABILITADO = '() => document.getElementById("salvar-seguir").disabled'


def test_na_pagina_o_aviso_sai_depois_de_confirmar(job, modelo):
    from playwright.sync_api import sync_playwright

    import test_tela_galeria as tg
    from desdobra.chromium import navegador
    from desdobra.tela import atos as ta
    from desdobra.tela import servidor as ts
    conteudo = te.montar(job)
    s = tsv._servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        tsv._preparar_rascunho(job, modelo, s, biscoito, conteudo)
    finally:
        s.parar()
    _mexer_formatos(job, lambda fs: fs.append(ap.formato('v4', 182, 320, rotacao=ROT0)))
    novo = te.montar(job)
    navegador.apontar_playwright()
    with ts.ServidorTela(novo, pasta=job, modo_teste=True, atos=ta.atos_do_job(job, conteudo=novo)) as srv, \
            sync_playwright() as pw:
        nav, pg = tp._pagina_da_tela(pw, srv, 2048, 720)  # numero-neutro: a tela do Duda (decisao 157)
        try:
            tg._abrir(pg, novo['estado'], 'v1')
            tp._esperar(pg, '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""')
            assert pg.evaluate(AVISO_NA_PAGINA) == [False, 1]
            assert pg.evaluate(BOTAO_DA_FAMILIA) == ['Confirmar família', False]
            _confirmar_na_pagina(pg, '#confirmar-familia')
            # a familia confirmada sai da lista do que falta, e a frase e a marca saem junto, sem a tela sair do lugar
            assert pg.evaluate(BOTAO_DA_FAMILIA) == ['Família confirmada', True]
            assert pg.evaluate(AVISO_NA_PAGINA) == [True, 0]
            assert pg.evaluate(SALVAR_DESABILITADO) is False
        finally:
            nav.close()


def test_na_pagina_a_confirmacao_velha_cai_quando_o_formato_entra_com_a_tela_aberta(job, modelo):
    from playwright.sync_api import sync_playwright

    import test_tela_galeria as tg
    from desdobra.chromium import navegador
    from desdobra.tela import atos as ta
    from desdobra.tela import servidor as ts
    conteudo = te.montar(job)
    s = tsv._servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        tsv._preparar_rascunho(job, modelo, s, biscoito, conteudo)
    finally:
        s.parar()
    conteudo = te.montar(job)
    navegador.apontar_playwright()
    with ts.ServidorTela(conteudo, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo)) as srv, sync_playwright() as pw:
        nav, pg = tp._pagina_da_tela(pw, srv, 2048, 720)  # numero-neutro: a tela do Duda (decisao 157)
        try:
            tp._esperar(pg, '() => document.getElementById("salvar-seguir").disabled ? "" : "1"')
            # o passo 1 muda com a tela aberta (como depois do ato de spec): v4 entra na familia vertical, e a tela e
            # montada de novo no proximo pedido do estado, pelo mesmo gancho do servidor
            _mexer_formatos(job, lambda fs: fs.append(ap.formato('v4', 182, 320, rotacao=ROT0)))
            feito = []

            def remontar():
                if feito:
                    return None
                feito.append(1)
                return te.montar(job)
            srv._conteudo['atualizar'] = remontar
            # um ato qualquer da pagina traz o estado novo (recarregarEstado e aplicarEstado)
            _confirmar_na_pagina(pg, 'button[data-ato="modo_dados"][data-modo="b"]')
            e = srv.estado
            gv = next(g['id'] for o in e['orientacoes'] for g in o['grupos']
                      if any(x['id'] == 'v4' for co in g['composicoes'] for x in co['formatos']))
            assert _grupo(e, gv)['aviso'] and any(x['texto'] == te.FAMILIA_SEM_CONFIRMACAO for x in e['faltam'])
            tg._abrir(pg, e, 'v1')
            tp._esperar(pg, '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""')
            # a pagina deixa de contar a confirmacao velha: o DA pode confirmar, e Salvar e seguir espera
            assert pg.evaluate(AVISO_NA_PAGINA)[0] is False
            assert pg.evaluate(BOTAO_DA_FAMILIA) == ['Confirmar família', False]
            assert pg.evaluate(SALVAR_DESABILITADO) is True
            _confirmar_na_pagina(pg, '#confirmar-familia')
            assert pg.evaluate(BOTAO_DA_FAMILIA) == ['Família confirmada', True]
            assert pg.evaluate(AVISO_NA_PAGINA) == [True, 0]
            assert pg.evaluate(SALVAR_DESABILITADO) is False
        finally:
            nav.close()
