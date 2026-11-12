# -*- coding: utf-8 -*-
"""M7a, fatia 5: "Salvar e seguir" e o lado do motor (decisoes-v1.md, 159, 164, 166, 167, 169, 170 e 171).

Criterios de pronto cobertos aqui:
  - com todas as familias confirmadas na janela, "Salvar e seguir" (ato da janela, com a confirmacao na propria
    janela) grava briefing/briefing-confirmado.json com a origem e o meio do Disparo (da e tela; no modo de teste,
    fixture_de_teste e medicao), guarda a versao anterior em briefing/historico/ e roda a derivacao;
  - derivacao/<formato>.json reflete a versao da galeria escolhida e as edicoes do DA por familia, com a origem da
    geometria de cada elemento (da, regra, transformacao, galeria); o elemento apagado sai e fica registrado com a
    origem do DA, sem reprovar o inventario; derivacao/devolucoes.json deixa de listar o formato de familia
    confirmada;
  - a derivacao gravada e a previa da tela dao as mesmas caixas, e a derivacao refeita da o mesmo arquivo (o render
    confere isso);
  - grava, fecha, reabre e rele 100% igual (criterio 1), no modo de teste, em job sintetico;
  - nenhum campo com valor inicial: sem o passo 2, sem o modo de dados ou com familia sem confirmacao, nada e gravado;
    o que vai ao briefing e o que o DA escolheu no rascunho;
  - o entregar recusa formato de familia sem confirmacao e proposta sem confirmacao;
  - o "briefing confirmar" do terminal (so para teste) e a tela usam o mesmo gravador;
  - o render desenha o texto editado (M7b, A7), nunca o texto velho calado;
  - a tela: "Salvar e seguir" so com todas as familias confirmadas, o dialogo sem opcao marcada e o proximo passo
    dito em portugues.
Tudo sintetico: o PSD de test_tela_palco e a fonte de autoteste do motor."""
import json
import shutil

import pytest

import test_derivacao_apoio as ap
import test_fontes_apoio as fap
import test_tela_escrita as tte
import test_tela_palco as tp
import test_tela_servidor as tts
from desdobra import arquivos, contratos, humano
from desdobra.briefing import modelo as mb
from desdobra.briefing import salvar as bs
from desdobra.derivacao import nucleo as nd
from desdobra.tela import atos as ta
from desdobra.tela import estado as te
from desdobra.tela import rascunho as tr
from desdobra.tela import servidor as ts

VERTICAIS = [('v1', 160, 320), ('v2', 166, 320), ('v3', 172, 320)]
FORMATOS = [('mesma', 640, 320)] + VERTICAIS + [('quadrado', 320, 320)]
USADAS = {'fundo': ('cover', 'centro', 'meio'), 'titulo': ('raiz_area', 'esquerda', 'topo'),
          'logo_principal': ('raiz_area', 'direita', 'base'), 'texto_de_apoio': ('raiz_area', 'esquerda', 'meio')}


@pytest.fixture(scope='module')
def modelo(tmp_path_factory):
    """O job sintetico com o briefing de teste importado e os ids das camadas."""
    from desdobra.job import nucleo
    from desdobra.render import autoteste
    base = tmp_path_factory.mktemp('salvar')
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
    # o giro de cada formato ja decidido no briefing de teste (decisoes-v1.md, 139; sem ele, nada e salvo)
    b = ap.briefing(funcoes=funcoes, formatos=[ap.formato(i, w, h, rotacao={'graus': 0, 'sentido': None})
                                               for i, w, h in FORMATOS])
    b.pop('cabecalho')
    b.pop('job_id')
    arq = base / 'fixture.json'
    arq.write_text(json.dumps(b), encoding='utf-8')
    mb.importar_teste(job, arq)
    return {'job': job, 'funcoes': funcoes}


@pytest.fixture
def job(modelo, tmp_path):
    destino = tmp_path / 'job'
    shutil.copytree(modelo['job'], destino)
    return destino


def _passo_2(funcoes):
    """O passo 2 e o Design system como o DA os deixa no rascunho: a funcao de cada camada e a regra e a ancora de cada
    funcao usada."""
    return {'funcoes': {str(k): {'funcao': v, 'observacao': None} for k, v in funcoes.items()},
            'design': {f: {'regra': r, 'x': x, 'y': y} for f, (r, x, y) in USADAS.items()}}


def _servidor(job, conteudo, teste=True):
    return ts.ServidorTela(conteudo, pasta=job, modo_teste=teste,
                           atos=ta.atos_do_job(job, conteudo=conteudo)).iniciar()


def _ato(s, biscoito, nome, dados):
    codigo, p = tte._pedir_ato(s, biscoito, nome=nome, dados=dados)
    if codigo != 200:
        return codigo, None, None
    c2, _cab, corpo = tte._escrever(s, '/api/ato/confirmar', {'pedido': p['pedido'], 'resposta': 'confirmar'},
                                    cookie=biscoito)
    return codigo, c2, p


def _vista(job):
    """O rascunho gravado como a pagina o manda junto com "Salvar e seguir" (o que a janela mostra)."""
    dados = json.loads((job / tr.ARQUIVO).read_text(encoding='utf-8'))
    return {k: dados[k] for k in ('job_id', 'laudo_sha256', 'familias', 'funcoes', 'cobertas', 'design',
                                  'design_camadas') if k in dados}


def _salvar(s, biscoito, job):
    return _ato(s, biscoito, 'salvar', {'rascunho': _vista(job)})


def _gravar_rascunho(s, biscoito, familias, passo_2):
    corpo = dict({'job_id': s.job_id, 'laudo_sha256': s.laudo_sha256, 'familias': familias}, **passo_2)
    return tte._escrever(s, '/api/rascunho', corpo, cookie=biscoito)[0]


def _familia_de(conteudo, fid):
    return next(g for g, f in conteudo['familias'].items() if fid in f['formatos'])


def _titulo(conteudo, gid):
    base = conteudo['editar']({'familia': gid, 'versao': None, 'edicoes': []})
    return next(e['id'] for e in base['membros'][0]['palco']['elementos'] if e['funcao'] == 'titulo')


def _logo(conteudo, gid):
    base = conteudo['editar']({'familia': gid, 'versao': None, 'edicoes': []})
    return next(e['id'] for e in base['membros'][0]['palco']['elementos'] if e['funcao'] == 'logo_principal')


def _escolhas(conteudo):
    """A versao e as edicoes de cada familia: na vertical, a segunda versao, o titulo descido e o logo apagado."""
    gv = _familia_de(conteudo, 'v1')
    versoes = conteudo['familias'][gv]['versoes']
    escolhas = {}
    for gid, f in conteudo['familias'].items():
        escolhas[gid] = {'versao': f['versoes'][0] if f['versoes'] else None, 'confirmada': False, 'edicoes': []}
    escolhas[gv] = {'versao': versoes[-1], 'confirmada': False,
                    'edicoes': [{'elemento': _titulo(conteudo, gv), 'acao': 'mover', 'dx': 0.0, 'dy': 0.04},
                                {'elemento': _logo(conteudo, gv), 'acao': 'apagar'}]}
    return escolhas


def _preparar_rascunho(job, modelo, s, biscoito, conteudo, confirmar=True, passo_2=True, modo=True):
    escolhas = _escolhas(conteudo)
    assert _gravar_rascunho(s, biscoito, escolhas, _passo_2(modelo['funcoes']) if passo_2 else {}) == 200
    if modo:
        assert _ato(s, biscoito, 'modo_dados', {'modo': 'c'})[1] == 200
    if confirmar:
        for gid, f in escolhas.items():
            assert _ato(s, biscoito, 'familia', {'familia': gid, 'versao': f['versao'], 'edicoes': f['edicoes']})[1] == 200, gid
    return escolhas


def _deriv(job, fid):
    return contratos.ler(job / 'derivacao' / ('%s.json' % fid), 'derivacao/1')


# ------------------------------------------------------------------ nenhum valor inicial e o que falta
def test_sem_familia_confirmada_nada_e_gravado(job, modelo):
    from desdobra.briefing import historico as bh
    conteudo = te.montar(job)
    antes = (job / mb.ARQUIVO).read_bytes()
    # o importar --teste do modelo ja abriu o indice do historico (M7b, A4), sem versao anterior guardada
    indice = (job / bh.ARQUIVO).read_bytes()
    s = _servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        _preparar_rascunho(job, modelo, s, biscoito, conteudo, confirmar=False)
        assert {p['codigo'] for p in bs.pendencias(job, conteudo)} == {'familia_sem_confirmacao'}
        assert _salvar(s, biscoito, job)[0] == 403
    finally:
        s.parar()
    assert (job / mb.ARQUIVO).read_bytes() == antes
    assert [p.name for p in (job / mb.PASTA_HISTORICO).iterdir()] == ['indice.json']
    assert (job / bh.ARQUIVO).read_bytes() == indice


def test_sem_o_passo_2_ou_sem_o_modo_nada_e_gravado(job, modelo):
    conteudo = te.montar(job)
    antes = (job / mb.ARQUIVO).read_bytes()
    s = _servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        _preparar_rascunho(job, modelo, s, biscoito, conteudo, passo_2=False, modo=False)
        codigos = {p['codigo'] for p in bs.pendencias(job, conteudo)}
        assert {'modo_dados_sem_escolha', 'briefing_com_problema'} <= codigos
        assert 'familia_sem_confirmacao' not in codigos
        assert _salvar(s, biscoito, job)[0] == 403
    finally:
        s.parar()
    assert (job / mb.ARQUIVO).read_bytes() == antes


def test_confirmar_e_salvar_valem_so_para_o_que_a_janela_mostra(job, modelo):
    # revisao do M7a: o ato leva o que a janela mostra; o rascunho que muda antes do Confirmar nao ganha o clique do DA
    conteudo = te.montar(job)
    s = _servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        escolhas = _preparar_rascunho(job, modelo, s, biscoito, conteudo, confirmar=False)
        gv = _familia_de(conteudo, 'v1')
        f = escolhas[gv]
        assert f['edicoes']
        # a janela mostra outras edicoes, ou nao diz quais: recusado antes do dialogo
        assert _ato(s, biscoito, 'familia', {'familia': gv, 'versao': f['versao'], 'edicoes': []})[0] == 403
        assert _ato(s, biscoito, 'familia', {'familia': gv, 'versao': f['versao']})[0] == 403
        # o rascunho muda entre o pedido e o Confirmar: a familia nao fica confirmada
        codigo, p = tte._pedir_ato(s, biscoito, nome='familia',
                                   dados={'familia': gv, 'versao': f['versao'], 'edicoes': f['edicoes']})
        assert codigo == 200
        mexe = dict(escolhas, **{gv: dict(f, edicoes=f['edicoes'][:1])})
        assert _gravar_rascunho(s, biscoito, mexe, _passo_2(modelo['funcoes'])) == 200
        c2 = tte._escrever(s, '/api/ato/confirmar', {'pedido': p['pedido'], 'resposta': 'confirmar'},
                           cookie=biscoito)[0]
        assert c2 == 403
        assert tr.ler(job, s.laudo_sha256)[0]['familias'][gv]['confirmada'] is False
        # Salvar e seguir: so com a vista da janela igual ao rascunho gravado
        for gid, g in mexe.items():
            assert _ato(s, biscoito, 'familia', {'familia': gid, 'versao': g['versao'], 'edicoes': g['edicoes']})[1] == 200
        vista = _vista(job)
        outra = dict(vista, familias=dict(vista['familias'], **{gv: dict(vista['familias'][gv], edicoes=[])}))
        assert _ato(s, biscoito, 'salvar', {'rascunho': outra})[0] == 403
        assert _ato(s, biscoito, 'salvar', {'rascunho': dict(vista, funcoes={})})[0] == 403
        assert _ato(s, biscoito, 'salvar', {})[0] == 403
        assert _salvar(s, biscoito, job)[1] == 200
    finally:
        s.parar()


def test_mudar_o_passo_2_tira_a_confirmacao_das_familias(job, modelo):
    # revisao do M7a: as funcoes, as regras e as ancoras mudam o layout de todas as familias
    conteudo = te.montar(job)
    s = _servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        escolhas = _preparar_rascunho(job, modelo, s, biscoito, conteudo)
        confirmadas = {g: dict(f, confirmada=True) for g, f in escolhas.items()}
        assert _gravar_rascunho(s, biscoito, confirmadas, _passo_2(modelo['funcoes'])) == 200
        assert all(f['confirmada'] for f in tr.ler(job, s.laudo_sha256)[0]['familias'].values())
        p2 = _passo_2(modelo['funcoes'])
        p2['design']['titulo'] = dict(p2['design']['titulo'], x='direita')
        assert _gravar_rascunho(s, biscoito, confirmadas, p2) == 200
        lido = tr.ler(job, s.laudo_sha256)[0]['familias']
        assert not any(f['confirmada'] or 'confirmacao' in f for f in lido.values())
    finally:
        s.parar()


def test_confirmacao_vale_so_para_os_formatos_da_familia_confirmada(job, modelo):
    # revisao do M7a: o id da familia e uma posicao; a confirmacao guarda os formatos e nao passa para outro conjunto
    conteudo = te.montar(job)
    s = _servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        _preparar_rascunho(job, modelo, s, biscoito, conteudo)
        assert bs.pendencias(job, conteudo) == []
        gv = _familia_de(conteudo, 'v1')
        outro = dict(conteudo, familias=dict(conteudo['familias'], **{
            gv: dict(conteudo['familias'][gv], formatos=conteudo['familias'][gv]['formatos'][:-1])}))
        assert {'codigo': 'familia_sem_confirmacao', 'familia': gv} in bs.pendencias(job, outro)
        assert gv not in te.familias_confirmadas(job, {g: f['formatos'] for g, f in outro['familias'].items()})
        assert gv in te.familias_confirmadas(job, {g: f['formatos'] for g, f in conteudo['familias'].items()})
    finally:
        s.parar()


def test_texto_com_caractere_que_a_fonte_nao_tem_impede_salvar(job, modelo):
    # revisao do M7a: "Salvar e seguir" recusa o texto editado com caractere que falta na fonte do job
    conteudo = te.montar(job)
    gv = _familia_de(conteudo, 'v1')
    base = conteudo['editar']({'familia': gv, 'versao': None, 'edicoes': []})
    apoio = next(e['id'] for e in base['membros'][0]['palco']['elementos'] if e['funcao'] == 'texto_de_apoio')
    s = _servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        escolhas = _preparar_rascunho(job, modelo, s, biscoito, conteudo, confirmar=False)
        escolhas[gv]['edicoes'] = [{'elemento': apoio, 'acao': 'texto', 'texto': 'AÇÃO'}]
        assert _gravar_rascunho(s, biscoito, escolhas, _passo_2(modelo['funcoes'])) == 200
        for gid, f in escolhas.items():
            assert _ato(s, biscoito, 'familia', {'familia': gid, 'versao': f['versao'], 'edicoes': f['edicoes']})[1] == 200, gid
        assert {'codigo': 'texto_sem_caractere', 'familia': gv} in bs.pendencias(job, conteudo)
        assert _salvar(s, biscoito, job)[0] == 403
    finally:
        s.parar()


# ------------------------------------------------------------------ salvar, derivar, fechar, reabrir
def test_salvar_e_seguir_grava_deriva_e_rele_igual(job, modelo):
    conteudo = te.montar(job)
    anterior_sha = arquivos.sha256_arquivo(job / mb.ARQUIVO)
    s = _servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        escolhas = _preparar_rascunho(job, modelo, s, biscoito, conteudo)
        assert bs.pendencias(job, conteudo) == []
        codigo, c2, p = _salvar(s, biscoito, job)
        assert codigo == 200 and c2 == 200
        assert p['sim'] == 'Confirmar' and 'famílias' in p['texto'] and '—' not in p['texto'] and '–' not in p['texto']
        # o estado da tela diz que o briefing esta salvo, para a pagina dizer o proximo passo
        _c, _cab, corpo = tts._pedir(s, '/api/estado', cookie=biscoito)[:3]
        assert json.loads(corpo)['briefing']['salvo'] is True
    finally:
        s.parar()
    b = mb.ler(job)
    assert b['cabecalho']['origem'] == mb.ORIGEM_FIXTURE and b['cabecalho']['meio'] == humano.MEIO_MEDICAO
    # a versao anterior fica no historico
    assert (job / mb.PASTA_HISTORICO / ('%s.json' % anterior_sha)).is_file()
    # e a gravacao entra no indice encadeado (M7b, A4), depois da do importar --teste
    from desdobra.briefing import historico as bh
    entradas = bh.ler(job)['entradas']
    assert [(x['seq'], x['meio']) for x in entradas] == [(1, 'importar_teste'), (2, humano.MEIO_MEDICAO)]
    assert entradas[1]['sha_anterior'] == anterior_sha == entradas[0]['sha_novo']
    assert entradas[1]['sha_novo'] == arquivos.sha256_arquivo(job / mb.ARQUIVO)
    assert bh.conferir(job) == []
    # o que vai ao briefing e o que o DA escolheu: funcoes, regras, ancoras, modo e as familias do rascunho
    assert {x['layer_id']: x['funcao']['valor'] for x in b['funcoes']} == modelo['funcoes']
    assert {x['funcao']: x['regra']['valor'] for x in b['regras_escala']} == {f: v[0] for f, v in USADAS.items()}
    assert {x['funcao']: (x['x']['valor'], x['y']['valor']) for x in b['ancoras']} == \
        {f: (v[1], v[2]) for f, v in USADAS.items()}
    assert b['modo_dados']['valor'] == 'c'
    comp = {c['familia']: c for c in b['composicoes']}
    assert set(comp) == set(conteudo['familias'])
    for gid, f in escolhas.items():
        assert comp[gid]['versao'] == f['versao'] and comp[gid]['edicoes'] == f['edicoes']
        assert comp[gid]['confirmada'] is True and comp[gid]['formatos'] == conteudo['familias'][gid]['formatos']
        assert comp[gid]['confirmacao']['origem'] == mb.ORIGEM_FIXTURE
    # a derivacao reflete a versao e as edicoes; a devolucao some
    gv = _familia_de(conteudo, 'v1')
    titulo, logo = _titulo(conteudo, gv), _logo(conteudo, gv)
    previa = conteudo['editar']({'familia': gv, 'versao': escolhas[gv]['versao'], 'edicoes': escolhas[gv]['edicoes']})
    pv = {m['formato']: {e['id']: e['caixa'] for e in m['palco']['elementos']} for m in previa['membros']}
    for fid, _w, _h in VERTICAIS:
        d = _deriv(job, fid)
        assert d['situacao'] == 'derivado' and d['caminho'] == 'galeria', (fid, d['devolucao'])
        assert d['proposta']['versao'] == escolhas[gv]['versao'] and d['proposta']['confirmada'] is True
        ids = {e['id'] for e in d['elementos']}
        assert logo not in ids
        assert [(a['elemento'], a['origem']) for a in d['apagados_pelo_da']] == [(logo, mb.ORIGEM_FIXTURE)]
        origem = {e['id']: e['origem_geometria'] for e in d['elementos']}
        assert origem[titulo] == 'da'
        assert set(origem.values()) <= {'da', 'galeria'} and 'galeria' in origem.values()
        assert all(e['regra_aplicada']['caminho'] == 'galeria' for e in d['elementos'])
        # a previa da tela e a derivacao gravada dao as mesmas caixas
        for e in d['elementos']:
            assert e['caixa'] == pytest.approx(pv[fid][e['id']], abs=0.01), (fid, e['id'])
    mesma = _deriv(job, 'mesma')
    assert mesma['caminho'] == 'transform' and {e['origem_geometria'] for e in mesma['elementos']} == {'transformacao'}
    dev = arquivos.ler_json(job / nd.ARQUIVO_DEVOLUCOES)
    assert not {x['formato'] for x in dev['devolucoes']} & {'v1', 'v2', 'v3', 'quadrado'}
    assert dev['inventario']['iguais_entre_formatos'] is True
    # a derivacao refeita com os arquivos de agora da o mesmo arquivo (o render confere assim)
    ctx = nd.preparar(job)
    from desdobra.derivacao import formatos as mf
    specs, arq = mf.specs_do_job(job)
    for fid, _w, _h in VERTICAIS:
        de_novo = nd.derivar_em_memoria(ctx, specs=specs, arquivo_specs=arq, params=mf.parametros(job, ctx['briefing']),
                                        so=[fid])['formatos'][fid]
        sem = lambda x: {k: v for k, v in json.loads(json.dumps(x)).items() if k not in ('gerado_em',)}  # noqa: E731
        assert sem(de_novo) == sem(_deriv(job, fid))
    # fechar e reabrir: o rascunho, as familias e a previa voltam iguais
    rascunho_antes = json.loads((job / tr.ARQUIVO).read_text(encoding='utf-8'))
    de_novo = te.montar(job)
    assert de_novo['familias'] == conteudo['familias']
    lido, outro = tr.ler(job, tr.laudo_sha256(job))
    assert outro is False and lido == rascunho_antes
    previa2 = de_novo['editar']({'familia': gv, 'versao': escolhas[gv]['versao'], 'edicoes': escolhas[gv]['edicoes']})
    assert [m['palco'] for m in previa2['membros']] == [m['palco'] for m in previa['membros']]
    assert de_novo['estado']['briefing']['salvo'] is True
    assert {c['familia']: (c['versao'], c['edicoes']) for c in mb.ler(job)['composicoes']} == \
        {g: (f['versao'], f['edicoes']) for g, f in lido['familias'].items()}


def test_editar_depois_de_salvar_tira_o_salvo_da_tela(job, modelo):
    conteudo = te.montar(job)
    s = _servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        escolhas = _preparar_rascunho(job, modelo, s, biscoito, conteudo)
        assert _salvar(s, biscoito, job)[1] == 200
        gv = _familia_de(conteudo, 'v1')
        mexe = dict(escolhas, **{gv: dict(escolhas[gv], edicoes=escolhas[gv]['edicoes'][:1])})
        assert _gravar_rascunho(s, biscoito, mexe, _passo_2(modelo['funcoes'])) == 200
    finally:
        s.parar()
    assert te.montar(job)['estado']['briefing']['salvo'] is False


# ------------------------------------------------------------------ quebra de linha da familia (M7b, C1)
def _apoio(modelo):
    """(elemento, layer_id) do texto de apoio ('VOX AH': o espaco na posicao 3)."""
    lid = next(k for k, v in modelo['funcoes'].items() if v == 'texto_de_apoio')
    return 'el%d' % lid, lid


def _quebra_do_apoio(modelo, inseridas=(3,), origem='da', aprovada=True):
    el, lid = _apoio(modelo)
    return {'elemento': el, 'layer_id': lid, 'manter': [], 'inseridas': list(inseridas), 'origem': origem,
            'aprovada': aprovada}


def test_quebra_da_familia_vai_do_rascunho_ao_briefing_e_rele_igual(job, modelo):
    conteudo = te.montar(job)
    gv = _familia_de(conteudo, 'v1')
    s = _servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        escolhas = _escolhas(conteudo)
        escolhas[gv]['quebras'] = [_quebra_do_apoio(modelo)]
        assert _gravar_rascunho(s, biscoito, escolhas, _passo_2(modelo['funcoes'])) == 200
        assert _ato(s, biscoito, 'modo_dados', {'modo': 'c'})[1] == 200
        _confirmar_todas(s, biscoito, escolhas)
        assert bs.pendencias(job, conteudo) == []
        assert _salvar(s, biscoito, job)[1] == 200
    finally:
        s.parar()
    _el, lid = _apoio(modelo)
    b = mb.ler(job)
    da_familia = [q for q in b['quebras_por_familia'] if q.get('familia') is not None]
    assert da_familia == [{'layer_id': lid, 'familia': gv, 'formatos': conteudo['familias'][gv]['formatos'],
                           'quebras': {'valor': [], 'situacao': 'confirmado',
                                       'origem': {'tipo': mb.ORIGEM_FIXTURE, 'ref': bs.REF_RASCUNHO}},
                           'inseridas': [3], 'origem': 'da', 'aprovada': True}]
    assert mb.conferir(contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1'), b) == []
    # fechar e reabrir: o briefing e o rascunho releem iguais, e a tela diz que esta salvo
    assert mb.ler(job) == b
    lido, outro = tr.ler(job, tr.laudo_sha256(job))
    assert outro is False and lido['familias'][gv]['quebras'] == [_quebra_do_apoio(modelo)]
    assert te.montar(job)['estado']['briefing']['salvo'] is True


def test_rascunho_recusa_quebra_fora_de_espaco_do_texto_de_agora(job, modelo):
    conteudo = te.montar(job)
    gv = _familia_de(conteudo, 'v1')
    el, _lid = _apoio(modelo)
    s = _servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        escolhas = _escolhas(conteudo)
        p2 = _passo_2(modelo['funcoes'])
        for pos in (1, 6, 40):
            escolhas[gv]['quebras'] = [_quebra_do_apoio(modelo, inseridas=(pos,))]
            assert _gravar_rascunho(s, biscoito, escolhas, p2) == 403, pos
        assert not (job / tr.ARQUIVO).exists()
        # no texto editado na familia, o espaco que vale e o dele (decisoes-v1.md, 171)
        escolhas[gv]['edicoes'] = escolhas[gv]['edicoes'] + [{'elemento': el, 'acao': 'texto', 'texto': 'AH VOX'}]
        escolhas[gv]['quebras'] = [_quebra_do_apoio(modelo, inseridas=(3,))]
        assert _gravar_rascunho(s, biscoito, escolhas, p2) == 403
        escolhas[gv]['quebras'] = [_quebra_do_apoio(modelo, inseridas=(2,))]
        assert _gravar_rascunho(s, biscoito, escolhas, p2) == 200
        # a quebra do DA vale aprovada pelo proprio ato; a proposta pelo motor espera a aprovacao
        escolhas[gv]['quebras'] = [_quebra_do_apoio(modelo, inseridas=(2,), aprovada=False)]
        assert _gravar_rascunho(s, biscoito, escolhas, p2) == 403
        escolhas[gv]['quebras'] = [_quebra_do_apoio(modelo, inseridas=(2,), origem='proposta', aprovada=False)]
        assert _gravar_rascunho(s, biscoito, escolhas, p2) == 200
    finally:
        s.parar()


def test_mudar_a_quebra_pede_confirmar_a_familia_de_novo(job, modelo):
    # a quebra mudada e edicao da familia (decisoes-v1.md, 167 e 171): a confirmacao velha nao vale para ela
    conteudo = te.montar(job)
    gv = _familia_de(conteudo, 'v1')
    s = _servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        escolhas = _preparar_rascunho(job, modelo, s, biscoito, conteudo)
        assert _salvar(s, biscoito, job)[1] == 200
        p2 = _passo_2(modelo['funcoes'])
        confirmadas = {g: dict(f, confirmada=True) for g, f in escolhas.items()}
        com_quebra = dict(confirmadas, **{gv: dict(confirmadas[gv], quebras=[_quebra_do_apoio(modelo)])})
        # a pagina nunca confirma: a familia com a quebra nova e confirmada falsa
        assert _gravar_rascunho(s, biscoito, com_quebra, p2) == 403
        com_quebra[gv]['confirmada'] = False
        assert _gravar_rascunho(s, biscoito, com_quebra, p2) == 200
        assert tr.ler(job, s.laudo_sha256)[0]['familias'][gv]['confirmada'] is False
        assert te.montar(job)['estado']['briefing']['salvo'] is False
        # confirmada de novo com a quebra, a tela so diz salvo depois de "Salvar e seguir"
        f = escolhas[gv]
        # o pedido sem a quebra que o rascunho tem (a janela que nao a mostra) e recusado (revisao do C)
        assert _ato(s, biscoito, 'familia', {'familia': gv, 'versao': f['versao'], 'edicoes': f['edicoes']})[0] \
            != 200
        assert _ato(s, biscoito, 'familia', {'familia': gv, 'versao': f['versao'], 'edicoes': f['edicoes'],
                                             'quebras': com_quebra[gv]['quebras']})[1] == 200
        assert te.montar(job)['estado']['briefing']['salvo'] is False
        assert _salvar(s, biscoito, job)[1] == 200
        assert te.montar(job)['estado']['briefing']['salvo'] is True
    finally:
        s.parar()


# ------------------------------------------------------------------ salvar seletivo (M7b, A6)
def _shas_da_derivacao(job):
    return {fid: arquivos.sha256_arquivo(job / nd.PASTA / ('%s.json' % fid)) for fid, _w, _h in FORMATOS}


def _confirmar_todas(s, biscoito, escolhas):
    for gid, f in escolhas.items():
        # o ato leva as quebras que a janela mostra, como as edicoes (revisao do C)
        assert _ato(s, biscoito, 'familia', {'familia': gid, 'versao': f['versao'], 'edicoes': f['edicoes'],
                                             'quebras': f.get('quebras') or []})[1] == 200, gid


def _eventos(job, nome):
    linhas = (job / 'log' / 'eventos.jsonl').read_text(encoding='utf-8').splitlines()
    return [x for x in map(json.loads, linhas) if x['evento'] == nome]


def test_primeiro_salvar_marca_todos_os_formatos_como_afetados(job, modelo):
    from desdobra.briefing import historico as bh
    conteudo = te.montar(job)
    s = _servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        _preparar_rascunho(job, modelo, s, biscoito, conteudo)
        assert _salvar(s, biscoito, job)[1] == 200
    finally:
        s.parar()
    todos = sorted(fid for fid, _w, _h in FORMATOS)
    ultima = bh.ler(job)['entradas'][-1]
    assert ultima['formatos_afetados'] == todos
    assert _eventos(job, 'briefing_confirmado')[-1]['afetados'] == todos
    mud = contratos.ler(job / bs.PASTA_MUDANCAS / ('%d.json' % ultima['seq']), bs.ESQUEMA_MUDANCAS)
    assert mud['seq'] == ultima['seq'] and sorted(mud['formatos']) == todos
    # sem derivacao gravada antes, cada formato entra no job
    assert all([i['tipo'] for i in itens] == ['formato_novo'] for itens in mud['formatos'].values())


def test_salvar_de_novo_sem_mudanca_nao_regrava_nenhum_formato(job, modelo):
    from desdobra.briefing import historico as bh
    conteudo = te.montar(job)
    s = _servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        _preparar_rascunho(job, modelo, s, biscoito, conteudo)
        assert _salvar(s, biscoito, job)[1] == 200
        antes = _shas_da_derivacao(job)
        dev = (job / nd.ARQUIVO_DEVOLUCOES).read_bytes()
        assert _salvar(s, biscoito, job)[1] == 200
    finally:
        s.parar()
    assert _shas_da_derivacao(job) == antes
    ultima = bh.ler(job)['entradas'][-1]
    assert ultima['formatos_afetados'] == [] and ultima['seq'] == 3
    assert _eventos(job, 'briefing_confirmado')[-1]['afetados'] == []
    mud = contratos.ler(job / bs.PASTA_MUDANCAS / '3.json', bs.ESQUEMA_MUDANCAS)
    assert mud['formatos'] == {}
    # o inventario e as devolucoes saem dos guardados, iguais
    assert json.loads(dev)['devolucoes'] == arquivos.ler_json(job / nd.ARQUIVO_DEVOLUCOES)['devolucoes']
    assert bh.conferir(job) == []


def test_mudar_a_ancora_regrava_so_os_afetados_e_a_outra_familia_fica_intacta(job, modelo):
    # decisoes-v1.md, 175: a mudanca do passo 2 tira a confirmacao de todas as familias, e o DA confirma de novo
    # formatos que nao queria rever; o salvar seletivo regrava so os formatos cuja impressao mudou, e os da familia
    # vertical (o logo apagado pelo DA) ficam com o mesmo arquivo
    from desdobra.briefing import historico as bh
    conteudo = te.montar(job)
    gv = _familia_de(conteudo, 'v1')
    s = _servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        escolhas = _preparar_rascunho(job, modelo, s, biscoito, conteudo)
        assert _salvar(s, biscoito, job)[1] == 200
        antes = _shas_da_derivacao(job)
        derivs = {fid: _deriv(job, fid) for fid, _w, _h in FORMATOS}
        p2 = _passo_2(modelo['funcoes'])
        p2['design']['logo_principal'] = dict(p2['design']['logo_principal'], x='esquerda')
        assert _gravar_rascunho(s, biscoito, escolhas, p2) == 200
        # a familia pede confirmacao de novo, tambem a vertical, onde o logo foi apagado
        assert {p['codigo'] for p in bs.pendencias(job, conteudo)} == {'familia_sem_confirmacao'}
        assert {p['familia'] for p in bs.pendencias(job, conteudo)} == set(conteudo['familias'])
        _confirmar_todas(s, biscoito, escolhas)
        assert _salvar(s, biscoito, job)[1] == 200
    finally:
        s.parar()
    depois = _shas_da_derivacao(job)
    mudaram = sorted(fid for fid in antes if antes[fid] != depois[fid])
    ultima = bh.ler(job)['entradas'][-1]
    assert ultima['formatos_afetados'] == mudaram
    assert _eventos(job, 'briefing_confirmado')[-1]['afetados'] == mudaram
    verticais = sorted(fid for fid, _w, _h in VERTICAIS)
    assert mudaram == ['mesma', 'quadrado']
    assert set(conteudo['familias'][gv]['formatos']) == set(verticais)
    # os que nao mudaram tem a mesma impressao com o briefing novo; os afetados, outra
    for fid, d in derivs.items():
        assert (nd.impressao_de_agora(job, d) == d['impressao_formato']) is (fid not in mudaram), fid
    # a diferenca do A5 de cada afetado, nenhuma dos outros
    mud = contratos.ler(job / bs.PASTA_MUDANCAS / ('%d.json' % ultima['seq']), bs.ESQUEMA_MUDANCAS)
    assert sorted(mud['formatos']) == mudaram
    assert all(mud['formatos'][fid] for fid in mudaram)
    assert [i['frase'] for i in mud['formatos']['mesma'] if i['tipo'] == 'ancora'] == \
        ['A âncora do logo principal mudou: antes direita e base, agora esquerda e base.']
    assert (mud['sha_anterior'], mud['sha_novo']) == (ultima['sha_anterior'], ultima['sha_novo'])
    assert bh.conferir(job) == []
    # a derivacao gravada e a de agora: o render (a trava do derivado) aceita os dois lados
    from desdobra.render import derivado
    for fid, _w, _h in FORMATOS:
        d = _deriv(job, fid)
        assert nd.impressao_de_agora(job, d) == d['impressao_formato'], fid
        assert derivado.montar(job, fid)[1] == [], fid
    dev = arquivos.ler_json(job / nd.ARQUIVO_DEVOLUCOES)
    assert dev['inventario']['formatos'] == len(FORMATOS) and dev['inventario']['iguais_entre_formatos'] is True


def test_confirmar_a_familia_de_novo_e_salvar_deixa_o_render_seguir(job, modelo):
    # a confirmacao nova (outro carimbo, mesma versao e mesmas edicoes) nao regrava o formato, e a trava do derivado,
    # que refaz a derivacao com o briefing de agora, aceita o arquivo guardado
    from desdobra.briefing import historico as bh
    from desdobra.render import derivado
    conteudo = te.montar(job)
    s = _servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        escolhas = _preparar_rascunho(job, modelo, s, biscoito, conteudo)
        assert _salvar(s, biscoito, job)[1] == 200
        assert derivado.montar(job, 'v1')[1] == []
        antes = _shas_da_derivacao(job)
        gv = _familia_de(conteudo, 'v1')
        assert _ato(s, biscoito, 'familia', {'familia': gv, 'versao': escolhas[gv]['versao'],
                                              'edicoes': escolhas[gv]['edicoes']})[1] == 200
        assert _salvar(s, biscoito, job)[1] == 200
    finally:
        s.parar()
    assert _shas_da_derivacao(job) == antes
    assert bh.ler(job)['entradas'][-1]['formatos_afetados'] == []
    for fid, _w, _h in FORMATOS:
        assert derivado.montar(job, fid)[1] == [], fid


def test_sem_a_derivacao_em_memoria_tudo_e_refeito_como_antes(job, modelo, monkeypatch):
    # a derivacao em memoria que nao roda nao impede salvar: afetados fica None no indice e no evento, nenhuma
    # diferenca e gravada, e a derivacao gravada refaz todo formato
    from desdobra.briefing import historico as bh
    conteudo = te.montar(job)
    s = _servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        _preparar_rascunho(job, modelo, s, biscoito, conteudo)
        assert _salvar(s, biscoito, job)[1] == 200
        antes = _shas_da_derivacao(job)
        preparar = nd.preparar

        def falha(pasta, partida=False, briefing=None):
            if briefing is not None:
                raise nd.ErroDerivacao('falha de teste', 'fases_desatualizadas')
            return preparar(pasta, partida=partida)
        monkeypatch.setattr(nd, 'preparar', falha)
        assert _salvar(s, biscoito, job)[1] == 200
    finally:
        s.parar()
    ultima = bh.ler(job)['entradas'][-1]
    assert ultima['seq'] == 3 and ultima['formatos_afetados'] is None
    assert 'afetados' not in _eventos(job, 'briefing_confirmado')[-1]
    assert not (job / bs.PASTA_MUDANCAS / '3.json').exists()
    depois = _shas_da_derivacao(job)
    assert all(antes[fid] != depois[fid] for fid in antes)


# ------------------------------------------------------------------ o laco de correcao (D1 e D2 do E1, fase E)
def _logo_id(modelo):
    return next(k for k, v in modelo['funcoes'].items() if v == 'logo_principal')


def _passo_2_com_selo(modelo):
    """O passo 2 com o logo trocado para selo, e a regra e a ancora do selo iguais as do logo principal no Design
    system: a derivacao so muda a funcao do logo."""
    funcoes = dict(modelo['funcoes'])
    funcoes[_logo_id(modelo)] = 'selo'
    p2 = _passo_2(funcoes)
    p2['design']['selo'] = dict(p2['design']['logo_principal'])
    return p2


def _salvo_e_corrigido(job, modelo, p2, confirmar=True):
    """O briefing salvo pela tela; depois o passo 2 p2 no rascunho e, com confirmar, as familias confirmadas de novo
    (decisoes-v1.md, 175), sem salvar."""
    conteudo = te.montar(job)
    s = _servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        escolhas = _preparar_rascunho(job, modelo, s, biscoito, conteudo)
        assert _salvar(s, biscoito, job)[1] == 200
        assert _gravar_rascunho(s, biscoito, escolhas, p2) == 200
        if confirmar:
            _confirmar_todas(s, biscoito, escolhas)
            assert bs.pendencias(job, conteudo) == []
    finally:
        s.parar()
    return conteudo, escolhas


def _familias(conteudo):
    return {g: f['formatos'] for g, f in conteudo['familias'].items()}


def test_situacao_na_tela_pede_salvar_depois_de_trocar_a_funcao_no_passo_2(job, modelo):
    # D1 do E1: o passo 2 que o briefing gravado guarda (funcoes, regras e ancoras) conta para "Salvar e seguir"
    conteudo, _e = _salvo_e_corrigido(job, modelo, _passo_2_com_selo(modelo))
    assert {x['layer_id']: x['funcao']['valor'] for x in mb.ler(job)['funcoes']}[_logo_id(modelo)] == 'logo_principal'
    assert bs.situacao_na_tela(job, _familias(conteudo))['salvo'] is False
    assert te.montar(job)['estado']['briefing']['salvo'] is False


def test_situacao_na_tela_pede_salvar_depois_de_mudar_so_a_ancora(job, modelo):
    # D1 do E1: so o Design system mudou (a ancora do titulo), as familias confirmadas de novo
    p2 = _passo_2(modelo['funcoes'])
    p2['design']['titulo'] = dict(p2['design']['titulo'], x='direita')
    conteudo, _e = _salvo_e_corrigido(job, modelo, p2)
    assert bs.situacao_na_tela(job, _familias(conteudo))['salvo'] is False


def test_situacao_na_tela_diz_salvo_quando_salvar_nao_mudaria_o_briefing(job, modelo):
    # o mesmo passo 2 de novo, as familias confirmadas de novo com a mesma versao e as mesmas edicoes: nada a salvar;
    # e o que a tela diz bate com o briefing que o gravador montaria (montar), fora o cabecalho e o carimbo
    conteudo, _e = _salvo_e_corrigido(job, modelo, _passo_2(modelo['funcoes']))
    assert bs.situacao_na_tela(job, _familias(conteudo))['salvo'] is True
    dados, _o = bs._rascunho(job)
    b = mb.ler(job)
    novo = bs.montar(job, conteudo, dados, origem=b['cabecalho']['origem'], meio='tela', por={}, quando=None,
                     modo=bs._modo(job, b['cabecalho']['origem']))
    assert bs._decisoes(novo) == bs._decisoes(b)


def test_situacao_na_tela_conta_a_origem_da_confirmacao_e_nao_a_hora(job, modelo):
    # a hora da confirmacao muda a cada clique e nao e decisao; a origem e o meio sao o que o portao da entrega pede
    _salvo_e_corrigido(job, modelo, _passo_2(modelo['funcoes']))
    b = mb.ler(job)
    outra_hora = json.loads(json.dumps(b))
    for c in outra_hora['composicoes']:
        c['confirmacao']['em'] = '2026-01-01T00:00:00-03:00'
    assert bs._decisoes(outra_hora) == bs._decisoes(b)
    da_janela = json.loads(json.dumps(b))
    da_janela['composicoes'][0]['confirmacao'].update(origem='da', meio='tela')
    assert bs._decisoes(da_janela) != bs._decisoes(b)


def test_derivacao_em_memoria_do_salvar_e_a_gravada_depois(job, modelo):
    # D2 do E1: a derivacao em memoria com o briefing novo (o salvar seletivo) confere a regra contra esse briefing,
    # e da o mesmo que a derivacao gravada logo depois; com o gravado de antes, a funcao trocada reprovava a regra
    from desdobra.derivacao import formatos as mf
    conteudo, _e = _salvo_e_corrigido(job, modelo, _passo_2_com_selo(modelo))
    dados, _o = bs._rascunho(job)
    origem = mb.ler(job)['cabecalho']['origem']
    novo = bs.montar(job, conteudo, dados, origem=origem, meio='medicao', por={'usuario': None, 'maquina': None},
                     quando=mb.agora(), modo=bs._modo(job, origem))
    ctx = nd.preparar(job, briefing=novo)
    kv = nd.mestre_do_kv(ctx)
    esperado = nd._esperado(ctx, kv)
    assert {v[0] for v in esperado.values()} >= {'selo'} and 'logo_principal' not in {v[0] for v in esperado.values()}
    specs, arquivo_specs = mf.specs_do_job(job)
    em_memoria = nd.derivar_em_memoria(ctx, specs=specs, arquivo_specs=arquivo_specs,
                                       params=mf.parametros(job, novo))['formatos']
    s = _servidor(job, conteudo)
    try:
        assert _salvar(s, tts._entrar(s), job)[1] == 200
    finally:
        s.parar()
    from desdobra.briefing import historico as bh
    afetados = bh.ler(job)['entradas'][-1]['formatos_afetados']
    assert afetados
    fora = ('gerado_em', 'briefing_sha256', 'inventario_entre_formatos')
    for fid, _w, _h in FORMATOS:
        gravada = _deriv(job, fid)
        if fid in afetados:
            assert {k: v for k, v in gravada.items() if k not in fora} == \
                {k: v for k, v in em_memoria[fid].items() if k not in fora}, fid
        else:
            # o formato guardado (o arquivo de antes, com o carimbo da confirmacao de antes) tem a mesma impressao
            assert gravada['impressao_formato'] == em_memoria[fid]['impressao_formato'], fid


def test_o_que_mudou_da_troca_de_funcao_e_so_o_item_da_funcao(job, modelo):
    # D2 do E1: o "o que mudou" gravado e a diferenca entre a derivacao gravada antes e a gravada por este salvar; a
    # troca de funcao com a mesma regra e a mesma ancora da um item so, nos formatos onde o logo existe
    from desdobra.briefing import historico as bh
    conteudo, _e = _salvo_e_corrigido(job, modelo, _passo_2_com_selo(modelo))
    antes = {fid: _deriv(job, fid) for fid, _w, _h in FORMATOS}
    s = _servidor(job, conteudo)
    try:
        assert _salvar(s, tts._entrar(s), job)[1] == 200
    finally:
        s.parar()
    logo = _logo_id(modelo)
    com_logo = sorted(fid for fid, d in antes.items() if any(logo in (e.get('layer_ids') or []) for e in d['elementos']))
    assert com_logo
    ultima = bh.ler(job)['entradas'][-1]
    assert ultima['formatos_afetados'] == com_logo
    mud = contratos.ler(job / bs.PASTA_MUDANCAS / ('%d.json' % ultima['seq']), bs.ESQUEMA_MUDANCAS)
    assert {f: [(i['tipo'], i['frase']) for i in itens] for f, itens in mud['formatos'].items()} == \
        {f: [('funcao', 'O logo principal agora é o selo.')] for f in com_logo}
    for fid in com_logo:
        d = _deriv(job, fid)
        assert (d['caminho'], d['situacao']) == (antes[fid]['caminho'], antes[fid]['situacao']), fid


# ------------------------------------------------------------------ o mesmo gravador no terminal
def test_briefing_confirmar_do_terminal_usa_o_mesmo_gravador(job, modelo, pessoa, monkeypatch):
    from desdobra import cli
    conteudo = te.montar(job)
    # as familias confirmadas pelo DA na janela de verdade (meio tela, origem da)
    monkeypatch.setattr(humano, 'ambiente_da_tela', lambda: (True, None))
    s = _servidor(job, conteudo, teste=False)
    try:
        biscoito = tts._entrar(s)
        _preparar_rascunho(job, modelo, s, biscoito, conteudo)
    finally:
        s.parar()
    perguntas = []
    monkeypatch.setattr(humano, 'ler', lambda p: perguntas.append(p) or 'sim')
    monkeypatch.setattr(cli._Analisador, 'modo_envelope', False)
    args = cli.montar_analisador().parse_args(['briefing', 'confirmar', '--job', str(job)])
    r = args.executar(args)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas, r.contagens)
    assert len(perguntas) == 1
    b = mb.ler(job)
    assert (b['cabecalho']['origem'], b['cabecalho']['meio']) == (mb.ORIGEM_DA, humano.MEIO_TERMINAL)
    assert {c['confirmacao']['meio'] for c in b['composicoes']} == {humano.MEIO_TELA}
    assert _deriv(job, 'v1')['caminho'] == 'galeria'
    assert mb.conferir_para_entrega(job) == (True, None)


def test_briefing_confirmar_recusa_sem_resposta_sim(job, modelo, pessoa, monkeypatch):
    from desdobra import cli
    antes = (job / mb.ARQUIVO).read_bytes()
    monkeypatch.setattr(humano, 'ler', lambda p: 'nao')
    monkeypatch.setattr(cli._Analisador, 'modo_envelope', False)
    args = cli.montar_analisador().parse_args(['briefing', 'confirmar', '--job', str(job)])
    r = args.executar(args)
    assert r.codigo != 0
    assert (job / mb.ARQUIVO).read_bytes() == antes


def test_briefing_confirmar_recusa_fora_do_terminal_do_da(job, monkeypatch):
    from desdobra import cli
    monkeypatch.setattr(humano, 'console_interativo', lambda: (False, 'sem_terminal'))
    args = cli.montar_analisador().parse_args(['briefing', 'confirmar', '--job', str(job)])
    r = args.executar(args)
    assert r.situacao == 'recusado' and r.contagens == {'recusa_sem_terminal': 1}


def test_gravador_recusa_disparo_de_outro_comando(job, modelo, pessoa):
    conteudo = te.montar(job)
    with pytest.raises(humano.ErroHumano):
        bs.salvar(job, conteudo, pessoa.exigir('render'))


def test_gravar_com_historico_pede_o_disparo_do_briefing_confirmar(job, pessoa):
    # revisao do M7a: o briefing que nao e de teste so e gravado com o Disparo do "briefing confirmar", de uso unico
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    b['cabecalho'].update(origem='da', meio='tela')
    antes = (job / mb.ARQUIVO).read_bytes()
    with pytest.raises(mb.ErroBriefing):
        mb.gravar_com_historico(job, b)
    forjado = humano.Disparo(comando=bs.COMANDO, meio='tela', usuario=None, maquina=None, quando='x', selo='forjado')
    with pytest.raises(humano.ErroHumano):
        mb.gravar_com_historico(job, b, disparo=forjado)
    with pytest.raises(humano.ErroHumano):
        mb.gravar_com_historico(job, b, disparo=pessoa.exigir('render'))
    d = pessoa.exigir(bs.COMANDO)
    with pytest.raises(humano.ErroHumano):  # o Disparo da origem da nao grava briefing de outra origem
        mb.gravar_com_historico(job, dict(b, cabecalho=dict(b['cabecalho'], origem='fixture_de_teste')), disparo=d)
    assert (job / mb.ARQUIVO).read_bytes() == antes
    d = pessoa.exigir(bs.COMANDO)
    mb.gravar_com_historico(job, b, disparo=d)
    assert contratos.ler(job / mb.ARQUIVO, 'briefing/1')['cabecalho']['origem'] == 'da'
    with pytest.raises(humano.ErroHumano):  # de uso unico
        mb.gravar_com_historico(job, b, disparo=d)


def test_gravador_gasta_o_disparo_mesmo_sem_gravar(job, pessoa):
    conteudo = te.montar(job)
    d = pessoa.exigir(bs.COMANDO)
    with pytest.raises(bs.ErroSalvar):
        bs.salvar(job, conteudo, d)
    with pytest.raises(humano.ErroHumano):
        humano.conferir(d, bs.COMANDO)


# ------------------------------------------------------------------ o entregar e o render
def _briefing_do_da(job, **mudar):
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    b['cabecalho'].update(origem='da', meio='terminal')
    b.update(mudar)
    contratos.gravar(job / mb.ARQUIVO, b, 'briefing/1')
    nd.derivar(job)


def test_entregar_recusa_familia_e_proposta_sem_confirmacao(job):
    from desdobra.entrega import portao
    conteudo = te.montar(job)
    comps = []
    for gid, f in conteudo['familias'].items():
        comps.append({'familia': gid, 'formatos': f['formatos'], 'versao': f['versoes'][0] if f['versoes'] else None,
                      'edicoes': [], 'confirmada': 'mesma' in f['formatos'], 'confirmacao': None})
    for c in comps:
        if c['confirmada']:
            c['confirmacao'] = {'origem': 'da', 'meio': 'tela', 'em': '2026-11-05T10:00:00'}
    _briefing_do_da(job, composicoes=comps)
    assert _deriv(job, 'v1')['caminho'] == 'galeria' and _deriv(job, 'v1')['proposta']['confirmada'] is False
    conf = portao.conferir(job, aprovacao=False, final=False)
    for fid in ('v1', 'v2', 'v3', 'quadrado'):
        codigos = [x['codigo'] for x in conf['formatos'][fid]['falhas']]
        assert 'familia_sem_confirmacao' in codigos and 'proposta_sem_confirmacao' in codigos, (fid, codigos)
    assert 'familia_sem_confirmacao' not in [x['codigo'] for x in conf['formatos']['mesma']['falhas']]


def test_entregar_recusa_familia_confirmada_fora_da_janela_do_da(job):
    # revisao do M7a: a confirmacao da familia tem de ser do DA na janela da tela; a do modo de teste nao vale
    from desdobra.entrega import portao
    conteudo = te.montar(job)
    gid = _familia_de(conteudo, 'mesma')
    comps = []
    for g, f in conteudo['familias'].items():
        conf = {'origem': 'fixture_de_teste', 'meio': 'medicao', 'em': '2026-11-05T10:00:00'} if g == gid else \
            {'origem': 'da', 'meio': 'tela', 'em': '2026-11-05T10:00:00'}
        comps.append({'familia': g, 'formatos': f['formatos'], 'versao': f['versoes'][0] if f['versoes'] else None,
                      'edicoes': [], 'confirmada': True, 'confirmacao': conf})
    _briefing_do_da(job, composicoes=comps)
    conf = portao.conferir(job, aprovacao=False, final=False)
    assert 'familia_sem_confirmacao' in [x['codigo'] for x in conf['formatos']['mesma']['falhas']]
    assert 'familia_sem_confirmacao' not in [x['codigo'] for x in conf['formatos']['quadrado']['falhas']]


def test_passo_3_parte_do_passo_2_do_rascunho(job, modelo):
    # revisao do M7a: as familias (passo 3) saem das funcoes e do Design system do rascunho, os que "Salvar e seguir"
    # vai gravar, e nao do briefing gravado
    def regra_do_titulo(conteudo):
        els = conteudo['previas']['mesma']['elementos']
        return next(e['regra'] for e in els if e['funcao'] == 'titulo')
    assert regra_do_titulo(te.montar(job)) == 'raiz_area'
    passo_2 = _passo_2(modelo['funcoes'])
    passo_2['design']['titulo'] = dict(passo_2['design']['titulo'], regra='contain')
    laudo = tr.laudo_sha256(job)
    estado = contratos.ler(job / 'estado.json', 'estado/1')
    tr.gravar(job, dict({'job_id': estado['job_id'], 'laudo_sha256': laudo, 'familias': {}}, **passo_2),
              job_id=estado['job_id'], laudo_atual=laudo, origem=mb.ORIGEM_FIXTURE)
    conteudo = te.montar(job)
    assert regra_do_titulo(conteudo) == 'contain'
    gid = _familia_de(conteudo, 'mesma')
    previa = conteudo['editar']({'familia': gid, 'versao': None if not conteudo['familias'][gid]['versoes'] else
                                 conteudo['familias'][gid]['versoes'][0], 'edicoes': []})
    titulo = next(e for m in previa['membros'] for e in m['palco']['elementos'] if e['funcao'] == 'titulo')
    assert titulo['regra'] == 'contain'
    # o passo 2 do rascunho ainda incompleto nao vale: a tela fica no briefing gravado
    passo_2['funcoes'].pop(next(iter(passo_2['funcoes'])))
    tr.gravar(job, dict({'job_id': estado['job_id'], 'laudo_sha256': laudo, 'familias': {}}, **passo_2),
              job_id=estado['job_id'], laudo_atual=laudo, origem=mb.ORIGEM_FIXTURE)
    assert regra_do_titulo(te.montar(job)) == 'raiz_area'


def test_entregar_recusa_briefing_do_da_sem_composicoes(job):
    # revisao do M7a: o gravador do briefing (tela e terminal) sempre grava as composicoes; briefing do DA sem elas nao
    # passou pela confirmacao das familias
    from desdobra.entrega import portao
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    assert 'composicoes' not in b
    _briefing_do_da(job)
    conf = portao.conferir(job, aprovacao=False, final=False)
    for fid, _w, _h in FORMATOS:
        assert 'familia_sem_confirmacao' in [x['codigo'] for x in conf['formatos'][fid]['falhas']], fid


def test_formato_de_escala_pura_refeito_pelo_solver_diz_regra(job, monkeypatch):
    # revisao do M7a: depois de uma edicao, o encaixe e refeito pelo solver; caixa que mudou nao e mais escala pura, e
    # a regra aplicada diz o caminho do solver
    from desdobra.derivacao import galeria as mg
    original = mg.reencaixar
    andou = {}

    def reencaixar(cf, caixas, sangra, apagados=(), do_da=()):
        novas, falha = original(cf, caixas, sangra, apagados, do_da)
        novas = {k: list(v) for k, v in novas.items()}
        logo = next(e['id'] for e in cf['kv']['elementos'] if e['funcao'] == 'logo_principal')
        novas[logo] = [v - 2.0 for v in novas[logo]]  # numero-neutro: o solver tirou o logo do lugar em 2 px
        andou['logo'] = logo
        return novas, falha
    monkeypatch.setattr(mg, 'reencaixar', reencaixar)
    conteudo = te.montar(job)
    gid = _familia_de(conteudo, 'mesma')
    comps = []
    for g, f in conteudo['familias'].items():
        comps.append({'familia': g, 'formatos': f['formatos'], 'versao': f['versoes'][0] if f['versoes'] else None,
                      'edicoes': [], 'confirmada': True,
                      'confirmacao': {'origem': 'da', 'meio': 'tela', 'em': '2026-11-05T10:00:00'}})
    _briefing_do_da(job, composicoes=comps)
    antes = {e['id']: e for e in _deriv(job, 'mesma')['elementos']}
    titulo = next(e['id'] for e in antes.values() if e['funcao'] == 'titulo')
    for c in comps:
        if c['familia'] == gid:
            c['edicoes'] = [{'elemento': titulo, 'acao': 'mover', 'dx': 0.0, 'dy': 0.04}]
    _briefing_do_da(job, composicoes=comps)
    depois = _deriv(job, 'mesma')
    for e in depois['elementos']:
        if e['origem_geometria'] == 'da':
            continue
        mudou = e['caixa'] != antes[e['id']]['caixa']
        assert e['origem_geometria'] == ('regra' if mudou else 'transformacao'), (e['id'], mudou)
        assert e['regra_aplicada']['caminho'] == ('solver' if mudou else 'transform'), (e['id'], mudou)
    logo = next(e for e in depois['elementos'] if e['id'] == andou['logo'])
    assert (logo['origem_geometria'], logo['regra_aplicada']['caminho']) == ('regra', 'solver')


def test_entregar_recusa_formato_fora_das_familias_confirmadas(job):
    from desdobra.entrega import portao
    conteudo = te.montar(job)
    gid = _familia_de(conteudo, 'mesma')
    comps = [{'familia': gid, 'formatos': conteudo['familias'][gid]['formatos'], 'versao': None, 'edicoes': [],
              'confirmada': True, 'confirmacao': {'origem': 'da', 'meio': 'tela', 'em': '2026-11-05T10:00:00'}}]
    _briefing_do_da(job, composicoes=comps)
    conf = portao.conferir(job, aprovacao=False, final=False)
    assert 'familia_sem_confirmacao' in [x['codigo'] for x in conf['formatos']['quadrado']['falhas']]
    assert 'familia_sem_confirmacao' not in [x['codigo'] for x in conf['formatos']['mesma']['falhas']]


def test_composicao_que_cita_formato_inexistente_e_recusada(job):
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    laudo = contratos.ler(job / mb.ARQUIVO_LAUDO, 'laudo/1')
    c = {'familia': 'vertical-1', 'formatos': ['nao-existe'], 'versao': None, 'edicoes': [], 'confirmada': True,
         'confirmacao': {'origem': 'da', 'meio': 'tela', 'em': '2026-11-05T10:00:00'}}
    erros = mb.conferir(laudo, dict(b, composicoes=[c]))
    assert 'composicao_com_formato_inexistente' in {e['codigo'] for e in erros}
    dois = [dict(c, formatos=['v1']), dict(c, familia='vertical-2', formatos=['v1'])]
    assert 'formato_em_duas_composicoes' in {e['codigo'] for e in mb.conferir(laudo, dict(b, composicoes=dois))}


def test_render_desenha_o_texto_editado(job):
    from desdobra.render import derivado
    conteudo = te.montar(job)
    gv = _familia_de(conteudo, 'v1')
    base = conteudo['editar']({'familia': gv, 'versao': None, 'edicoes': []})
    apoio = next(e['id'] for e in base['membros'][0]['palco']['elementos'] if e['funcao'] == 'texto_de_apoio')
    comps = []
    for gid, f in conteudo['familias'].items():
        ed = [{'elemento': apoio, 'acao': 'texto', 'texto': 'HAH'}] if gid == gv else []
        comps.append({'familia': gid, 'formatos': f['formatos'], 'versao': None, 'edicoes': ed, 'confirmada': True,
                      'confirmacao': {'origem': 'da', 'meio': 'tela', 'em': '2026-11-05T10:00:00'}})
    _briefing_do_da(job, composicoes=comps)
    d = _deriv(job, 'v1')
    el = next(e for e in d['elementos'] if e['id'] == apoio)
    assert el['texto_editado'] == 'HAH' and el['origem_geometria'] == 'da'
    # o texto vale so na familia editada (171)
    assert not any(e.get('texto_editado') for e in _deriv(job, 'quadrado')['elementos'])
    # o render desenha o texto novo (M7b, A7): nunca o texto velho calado
    contrato, bloqueios, _c = derivado.montar(job, 'v1')
    assert bloqueios == []
    editados = [e for e in contrato['entradas'] if e.get('texto_editado')]
    assert [e['elemento'] for e in editados] == [apoio]
    assert [r['texto'] for r in editados[0]['texto']['runs']] == ['HAH']


# ------------------------------------------------------------------ a tela no Chromium sem janela (modo de teste)
def test_salvar_e_seguir_no_chromium(job, modelo):
    from playwright.sync_api import sync_playwright

    import test_tela_galeria as tg
    from desdobra.chromium import navegador
    conteudo = te.montar(job)
    navegador.apontar_playwright()
    gv = _familia_de(conteudo, 'v1')
    with ts.ServidorTela(conteudo, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo)) as srv, sync_playwright() as pw:
        # o rascunho, o modo e as familias que nao sao a vertical confirmados antes de abrir a pagina
        escolhas = _escolhas(conteudo)
        corpo = dict({'job_id': srv.job_id, 'laudo_sha256': srv.laudo_sha256, 'familias': escolhas},
                     **_passo_2(modelo['funcoes']))
        tr.gravar(job, corpo, job_id=srv.job_id, laudo_atual=srv.laudo_sha256, origem=srv.origem_rascunho)
        for gid, f in escolhas.items():
            if gid != gv:
                d = humano.exigir_tela(tr.COMANDO_FAMILIA, srv._sessao_humana, confirmado=True)
                tr.confirmar_familia(job, gid, f['versao'], disparo=d, job_id=srv.job_id,
                                     laudo_atual=srv.laudo_sha256, edicoes=f['edicoes'],
                                     formatos=conteudo['familias'][gid]['formatos'],
                                     pecas=conteudo['familias'][gid]['pecas'])
        from desdobra.job import modo_dados
        modo_dados.gravar(job, 'c', disparo=humano.exigir_tela(modo_dados.ESCOLHER, srv._sessao_humana,
                                                               confirmado=True))
        srv.estado = conteudo['recarregar']()  # o modo escolhido entra no passo 1 que a pagina le
        nav, pg = tp._pagina_da_tela(pw, srv, 2048, 720)  # numero-neutro: a tela do Duda (decisao 157)
        try:
            salvar = '() => document.getElementById("salvar-seguir")'
            assert pg.evaluate(salvar + '.disabled') is True
            assert 'família' in pg.evaluate('() => document.getElementById("dica-acoes").textContent')
            tg._abrir(pg, conteudo['estado'], 'v1')
            tp._esperar(pg, '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""')
            pg.evaluate('() => document.getElementById("confirmar-familia").click()')
            tp._esperar(pg, '() => document.getElementById("confirmacao").open ? "1" : ""')
            pg.evaluate('''() => Array.from(document.querySelectorAll("#confirmacao button"))
                .find(b => b.textContent === "Confirmar").click()''')
            tp._esperar(pg, '() => document.documentElement.dataset.estadoAto === "feito" ? "1" : ""')
            tp._esperar(pg, salvar + '.disabled ? "" : "1"')
            pg.evaluate(salvar + '.click()')
            tp._esperar(pg, '() => document.getElementById("confirmacao").open ? "1" : ""')
            # nenhuma resposta em foco: Enter nao grava nada
            assert pg.evaluate('() => document.activeElement.tagName') != 'BUTTON'
            assert 'famílias' in pg.evaluate('() => document.getElementById("confirmacao-texto").textContent')
            pg.evaluate('''() => Array.from(document.querySelectorAll("#confirmacao button"))
                .find(b => b.textContent === "Confirmar").click()''')
            tp._esperar(pg, '() => document.documentElement.dataset.estadoAto === "feito" ? "1" : ""')
            tp._esperar(pg, '() => document.getElementById("salvo").hidden ? "" : "1"')
            aviso = pg.evaluate('() => document.getElementById("salvo").textContent')
            assert 'briefing' in aviso and 'salvo' in aviso
            assert '—' not in aviso and '–' not in aviso
            assert pg.evaluate(salvar + '.textContent') == 'Briefing salvo'
            texto = pg.evaluate(tp.JS_TEXTO_DA_MOLDURA)
            assert not tp.IDENTIFICADOR.findall(texto), tp.IDENTIFICADOR.findall(texto)
            # reabrir a pagina: o aviso de salvo volta
            pg.reload(wait_until='load')
            tp._esperar(pg, tp.JS_PRONTO)
            assert pg.evaluate('() => document.getElementById("salvo").hidden') is False
        finally:
            nav.close()
    assert mb.ler(job)['cabecalho']['origem'] == mb.ORIGEM_FIXTURE
    assert _deriv(job, 'v1')['caminho'] == 'galeria'


# ------------------------------------------------------------------ M7c, M3: a marca do job no passo 1
# decisoes-v1.md, 190 (Q5): a lista das marcas da biblioteca da agencia, "Marca nova" e "Sem marca", nenhuma marcada;
# a escolha e opcional e nunca trava o "Salvar e seguir". Nomes de marca sinteticos.
MARCA_UM = 'Marca Sintetica Um'
MARCA_DOIS = 'Marca Sintetica Dois'


@pytest.fixture
def biblioteca(tmp_path):
    """A biblioteca da agencia com duas marcas sinteticas, criadas pelo modulo do perfil (M2)."""
    from desdobra.marca import perfil
    bib = tmp_path / 'biblioteca-da-agencia'
    bib.mkdir()
    ids = {perfil.criar(bib, nome)['id']: nome for nome in (MARCA_UM, MARCA_DOIS)}
    return bib, ids


def _marca_na_tela(conteudo):
    return conteudo['estado']['lido']['marca']


def test_marca_sem_biblioteca_mostra_so_sem_marca(job):
    from desdobra.marca import job as mj
    conteudo = te.montar(job)
    m = _marca_na_tela(conteudo)
    assert m['biblioteca']['configurada'] is False and m['biblioteca']['usavel'] is False
    assert m['biblioteca']['o_que_fazer']  # a nota simples de onde configurar
    assert m['marcas'] == [] and m['escolhida'] is None and m['pode_criar'] is False
    # nada falta por causa da marca: ela e opcional
    assert not any('marca' in f['texto'].lower() for f in conteudo['estado']['faltam'])
    s = _servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        # sem biblioteca, so "Sem marca" passa
        assert _ato(s, biscoito, 'marca', {'escolha': 'nova', 'nome': MARCA_UM})[0] == 403
        assert _ato(s, biscoito, 'marca', {'escolha': 'marca', 'id': '0' * 32})[0] == 403
        codigo, c2, p = _ato(s, biscoito, 'marca', {'escolha': 'sem_marca'})
        assert codigo == 200 and c2 == 200 and p['sim'] == 'Confirmar'
        assert '—' not in p['texto'] and '–' not in p['texto']
        _c, _cab, corpo = tts._pedir(s, '/api/estado', cookie=biscoito)[:3]
        assert json.loads(corpo)['lido']['marca']['escolhida'] == {'escolha': 'sem_marca', 'id': None, 'nome': None}
    finally:
        s.parar()
    reg = mj.ler(job)
    assert reg['escolha'] == 'sem_marca' and reg['marca_id'] is None


def test_marca_lista_a_biblioteca_sem_nenhuma_marcada_e_sem_caminho(job, biblioteca):
    bib, ids = biblioteca
    conteudo = te.montar(job, biblioteca=str(bib))
    m = _marca_na_tela(conteudo)
    assert m['biblioteca']['usavel'] is True and m['pode_criar'] is True
    assert [x['nome'] for x in m['marcas']] == sorted(ids.values(), key=str.casefold)
    assert {x['id'] for x in m['marcas']} == set(ids)
    assert m['escolhida'] is None
    # o caminho da biblioteca nunca vai a pagina
    texto = json.dumps(conteudo['estado'], ensure_ascii=False, default=str)
    assert str(bib) not in texto and bib.as_posix() not in texto and str(bib.parent) not in texto
    assert not any('marca' in f['texto'].lower() for f in conteudo['estado']['faltam'])


def test_marca_biblioteca_vazia_ou_com_problema_mostra_so_sem_marca(job, tmp_path):
    vazia = tmp_path / 'biblioteca-vazia'
    vazia.mkdir()
    m = _marca_na_tela(te.montar(job, biblioteca=str(vazia)))
    assert m['biblioteca']['usavel'] is True and m['marcas'] == [] and m['pode_criar'] is True
    m = _marca_na_tela(te.montar(job, biblioteca=str(tmp_path / 'nao-existe')))
    assert m['biblioteca']['usavel'] is False and m['marcas'] == [] and m['pode_criar'] is False
    assert m['biblioteca']['o_que_fazer']


def test_escolher_a_marca_grava_fecha_e_reabre_igual(job, biblioteca):
    from desdobra.marca import job as mj
    bib, ids = biblioteca
    alvo = next(i for i, n in ids.items() if n == MARCA_DOIS)
    conteudo = te.montar(job, biblioteca=str(bib))
    s = _servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        # id que nao e da biblioteca, campo a mais ou escolha fora da lista: recusado antes do dialogo
        assert _ato(s, biscoito, 'marca', {'escolha': 'marca', 'id': 'f' * 32})[0] == 403
        assert _ato(s, biscoito, 'marca', {'escolha': 'marca', 'id': alvo, 'nome': 'x'})[0] == 403
        assert _ato(s, biscoito, 'marca', {'escolha': 'outra'})[0] == 403
        assert _ato(s, biscoito, 'marca', {})[0] == 403
        assert not (job / mj.ARQUIVO).exists()
        codigo, c2, p = _ato(s, biscoito, 'marca', {'escolha': 'marca', 'id': alvo})
        assert codigo == 200 and c2 == 200
        assert MARCA_DOIS in p['texto'] and alvo not in p['texto']
        _c, _cab, corpo = tts._pedir(s, '/api/estado', cookie=biscoito)[:3]
        assert json.loads(corpo)['lido']['marca']['escolhida'] == {'escolha': 'marca', 'id': alvo, 'nome': MARCA_DOIS}
    finally:
        s.parar()
    reg = contratos.ler(job / mj.ARQUIVO, mj.ESQUEMA)
    assert reg['escolha'] == 'marca' and reg['marca_id'] == alvo
    # no modo de teste da tela, o Disparo sai com a origem de teste e o meio medicao, como os outros atos
    assert reg['origem'] == humano.ORIGEM_FIXTURE and reg['escolhido_por']['meio'] == humano.MEIO_MEDICAO
    # o nome da marca fica so na biblioteca: o arquivo do job leva o id
    assert MARCA_DOIS not in (job / mj.ARQUIVO).read_text(encoding='utf-8')
    # fechar e reabrir a tela: a mesma marca escolhida
    reaberta = _marca_na_tela(te.montar(job, biblioteca=str(bib)))
    assert reaberta['escolhida'] == {'escolha': 'marca', 'id': alvo, 'nome': MARCA_DOIS}
    # reabrir sem a biblioteca configurada: a escolha continua, sem o nome
    sem_bib = _marca_na_tela(te.montar(job))
    assert sem_bib['escolhida'] == {'escolha': 'marca', 'id': alvo, 'nome': None}


def test_marca_nova_cria_o_perfil_na_biblioteca_e_vale_para_o_job(job, biblioteca):
    from desdobra.marca import job as mj
    from desdobra.marca import perfil
    bib, ids = biblioteca
    conteudo = te.montar(job, biblioteca=str(bib))
    s = _servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        # nome vazio, so espacos, com barra, longo demais, de outro tipo ou de uma marca que ja existe: recusado
        for ruim in ('', '   ', 'marca/com-barra', 'x' * 121, 7, MARCA_UM.upper()):
            assert _ato(s, biscoito, 'marca', {'escolha': 'nova', 'nome': ruim})[0] == 403, ruim
        assert len(perfil.listar(bib)) == 2
        codigo, c2, p = _ato(s, biscoito, 'marca', {'escolha': 'nova', 'nome': '  Marca Sintetica Tres '})
        assert codigo == 200 and c2 == 200 and 'Marca Sintetica Tres' in p['texto']
        _c, _cab, corpo = tts._pedir(s, '/api/estado', cookie=biscoito)[:3]
        m = json.loads(corpo)['lido']['marca']
    finally:
        s.parar()
    novas = [x for x in perfil.listar(bib) if x['id'] not in ids]
    assert [x['marca'] for x in novas] == ['Marca Sintetica Tres']
    nova = novas[0]['id']
    assert perfil.ler(bib, nova)['versao'] == 0  # o perfil nasce sem registro (M2)
    assert mj.ler(job)['marca_id'] == nova
    assert m['escolhida'] == {'escolha': 'marca', 'id': nova, 'nome': 'Marca Sintetica Tres'}
    assert 'Marca Sintetica Tres' in [x['nome'] for x in m['marcas']]


def test_trocar_a_marca_por_sem_marca(job, biblioteca):
    from desdobra.marca import job as mj
    bib, ids = biblioteca
    conteudo = te.montar(job, biblioteca=str(bib))
    s = _servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        assert _ato(s, biscoito, 'marca', {'escolha': 'marca', 'id': next(iter(ids))})[1] == 200
        assert _ato(s, biscoito, 'marca', {'escolha': 'sem_marca'})[1] == 200
    finally:
        s.parar()
    reg = mj.ler(job)
    assert reg['escolha'] == 'sem_marca' and reg['marca_id'] is None
    assert _marca_na_tela(te.montar(job, biblioteca=str(bib)))['escolhida']['escolha'] == 'sem_marca'


def test_marca_nao_trava_salvar_e_seguir(job, modelo, biblioteca):
    from desdobra.marca import job as mj
    bib, _ids = biblioteca
    conteudo = te.montar(job, biblioteca=str(bib))
    s = _servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        _preparar_rascunho(job, modelo, s, biscoito, conteudo)
        assert bs.pendencias(job, conteudo) == []
        assert _salvar(s, biscoito, job)[1] == 200
    finally:
        s.parar()
    assert not (job / mj.ARQUIVO).exists()


def test_marca_e_ato_humano_da_tela(job, biblioteca, pessoa):
    from desdobra.marca import job as mj
    bib, ids = biblioteca
    assert mj.COMANDO in humano.ATOS_DA_TELA and mj.COMANDO not in humano.COMANDOS
    # sem o Disparo do clique, ou com o de outro ato, nada e gravado
    with pytest.raises(humano.ErroHumano):
        mj.gravar(job, {'escolha': 'sem_marca'}, disparo=None)
    with pytest.raises(humano.ErroHumano):
        mj.gravar(job, {'escolha': 'sem_marca'}, disparo=pessoa.exigir('render'))
    assert not (job / mj.ARQUIVO).exists()
    sessao = humano.abrir_sessao_tela(teste=True)
    try:
        d = humano.exigir_tela(mj.COMANDO, sessao, confirmado=True)
        mj.gravar(job, {'escolha': 'marca', 'id': next(iter(ids))}, disparo=d, biblioteca=bib)
        # o Disparo vale um ato so
        with pytest.raises(humano.ErroHumano):
            mj.gravar(job, {'escolha': 'sem_marca'}, disparo=d)
    finally:
        humano.fechar_sessao_tela(sessao)


def test_envelope_do_claude_diz_so_se_ha_marca(job, biblioteca, capsys):
    from desdobra import cli
    from desdobra.marca import job as mj
    bib, ids = biblioteca
    alvo = next(iter(ids))

    def envelope():
        capsys.readouterr()
        cli.principal(['--envelope', 'job', 'estado', str(job)])
        return capsys.readouterr().out

    saida = envelope()
    assert json.loads(saida)['contagens']['marca_escolhida'] == 0
    sessao = humano.abrir_sessao_tela(teste=True)
    try:
        mj.gravar(job, {'escolha': 'marca', 'id': alvo}, disparo=humano.exigir_tela(mj.COMANDO, sessao, True),
                  biblioteca=bib)
    finally:
        humano.fechar_sessao_tela(sessao)
    saida = envelope()
    assert json.loads(saida)['contagens']['marca_escolhida'] == 1
    assert alvo not in saida and ids[alvo] not in saida and str(bib) not in saida


def test_gancho_nega_ao_claude_ler_e_escrever_a_marca_do_job(job):
    import importlib.util

    from conftest import RAIZ_PLUGIN
    from desdobra.marca import job as mj
    spec = importlib.util.spec_from_file_location('gancho_m3', RAIZ_PLUGIN / 'scripts' / 'gancho_confirmacoes.py')
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    alvo = job / mj.ARQUIVO
    alvo.write_text('{}', encoding='utf-8')
    c, p = str(alvo), alvo.as_posix()
    eventos = [('Read', {'file_path': c}), ('Grep', {'pattern': 'x', 'path': c}),
               ('Write', {'file_path': c, 'content': '{}'}),
               ('Edit', {'file_path': c, 'old_string': '{}', 'new_string': '[]'}),
               ('Bash', {'command': 'cat "%s"' % p}), ('Bash', {'command': 'echo {} > "%s"' % p}),
               ('PowerShell', {'command': 'Get-Content -Raw "%s"' % c}),
               ('PowerShell', {'command': 'Set-Content -Path "%s" -Value x' % c})]
    for ferramenta, entrada in eventos:
        evento = {'tool_name': ferramenta, 'tool_input': entrada, 'cwd': str(job.parent)}
        assert g.decidir(evento) == 'deny', (ferramenta, entrada)


JS_MARCAS_MARCADAS = '''() => Array.from(document.querySelectorAll("#lido-marca button[data-ato=marca]"))
    .filter(b => b.getAttribute("aria-pressed") === "true").map(b => b.textContent)'''


def _abrir_passo_1(pw, srv):
    from desdobra.chromium import navegador
    nav = pw.chromium.launch(headless=True, args=list(navegador.ARGUMENTOS))
    pg = nav.new_context(viewport={'width': 1440, 'height': 900}, device_scale_factor=1).new_page()  # numero-neutro: janela de teste
    try:
        pg.goto(srv.url_entrada, wait_until='commit')
    except Exception:  # noqa: BLE001 - o 204 nao completa a navegacao
        pass
    pg.goto(srv.url_pagina, wait_until='load')
    tp._esperar(pg, tp.JS_PRONTO)
    pg.evaluate('() => document.querySelector("#passos [data-passo=lido]").click()')
    pg.evaluate('() => document.getElementById("bloco-marca").scrollIntoView()')
    return nav, pg


def _confirmar_na_janela(pg):
    tp._esperar(pg, '() => document.getElementById("confirmacao").open ? "1" : ""')
    # nenhuma resposta em foco: Enter nao grava nada
    assert pg.evaluate('() => document.activeElement.tagName') != 'BUTTON'
    texto = pg.evaluate('() => document.getElementById("confirmacao-texto").textContent')
    pg.evaluate('''() => Array.from(document.querySelectorAll("#confirmacao button"))
        .find(b => b.textContent === "Confirmar").click()''')
    tp._esperar(pg, '() => document.documentElement.dataset.estadoAto === "feito" ? "1" : ""')
    return texto


def test_marca_no_chromium_escolher_fechar_e_reabrir(job, biblioteca, capturas=None):
    """A marca no passo 1 da pagina: nenhuma marcada, a escolha pela janela, a marca nova pelo campo e, depois de
    fechar e abrir a tela de novo, a mesma marca marcada. capturas: pasta para as fotos da verificacao (fora do
    repositorio), ou None."""
    from playwright.sync_api import sync_playwright

    from desdobra.chromium import navegador
    from desdobra.marca import job as mj
    bib, ids = biblioteca
    navegador.apontar_playwright()

    def foto(pg, nome):
        if capturas is not None:
            pg.locator('#bloco-marca').screenshot(path=str(capturas / ('%s.png' % nome)))

    conteudo = te.montar(job, biblioteca=str(bib))
    with ts.ServidorTela(conteudo, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo)) as srv, sync_playwright() as pw:
        nav, pg = _abrir_passo_1(pw, srv)
        try:
            nomes = pg.evaluate('''() => Array.from(document.querySelectorAll("#lido-marca button[data-ato=marca]"))
                .map(b => b.querySelector(".modo-nome").textContent)''')
            assert nomes == sorted(ids.values(), key=str.casefold) + ['Sem marca']
            assert pg.evaluate(JS_MARCAS_MARCADAS) == []
            assert pg.evaluate('() => document.getElementById("marca-nova-criar").disabled') is True
            foto(pg, '1-nenhuma-marcada')
            # a marca dois, pela janela de confirmacao
            pg.evaluate('''() => Array.from(document.querySelectorAll("#lido-marca button[data-ato=marca]"))
                .find(b => b.textContent === "%s").click()''' % MARCA_DOIS)
            assert MARCA_DOIS in _confirmar_na_janela(pg)
            assert pg.evaluate(JS_MARCAS_MARCADAS) == [MARCA_DOIS]
            foto(pg, '2-marca-escolhida')
            # a marca nova: o nome repetido mostra o erro e nao deixa criar
            pg.fill('#marca-nova-nome', MARCA_UM.lower())
            assert pg.evaluate('() => document.getElementById("marca-nova-erro").hidden') is False
            assert pg.evaluate('() => document.getElementById("marca-nova-criar").disabled') is True
            foto(pg, '3-marca-nova-repetida')
            pg.fill('#marca-nova-nome', 'Marca Sintetica Tres')
            assert pg.evaluate('() => document.getElementById("marca-nova-criar").disabled') is False
            pg.click('#marca-nova-criar')
            assert 'Marca Sintetica Tres' in _confirmar_na_janela(pg)
            assert pg.evaluate(JS_MARCAS_MARCADAS) == ['Marca Sintetica Tres']
            assert pg.evaluate('() => document.getElementById("marca-nova-nome").value') == ''
            foto(pg, '4-marca-nova-escolhida')
            texto = pg.evaluate(tp.JS_TEXTO_DA_MOLDURA)
            assert '—' not in texto and '–' not in texto
            assert str(bib) not in pg.content()
        finally:
            nav.close()
    escolhido = mj.ler(job)['marca_id']
    # fechar a tela e abrir de novo: a mesma marca marcada
    conteudo = te.montar(job, biblioteca=str(bib))
    with ts.ServidorTela(conteudo, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo)) as srv, sync_playwright() as pw:
        nav, pg = _abrir_passo_1(pw, srv)
        try:
            assert pg.evaluate(JS_MARCAS_MARCADAS) == ['Marca Sintetica Tres']
            foto(pg, '5-reaberta')
        finally:
            nav.close()
    assert mj.ler(job)['marca_id'] == escolhido


def test_marca_no_chromium_sem_biblioteca(job, capturas=None):
    from playwright.sync_api import sync_playwright

    from desdobra.chromium import navegador
    navegador.apontar_playwright()
    conteudo = te.montar(job)
    with ts.ServidorTela(conteudo, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo)) as srv, sync_playwright() as pw:
        nav, pg = _abrir_passo_1(pw, srv)
        try:
            nomes = pg.evaluate('''() => Array.from(document.querySelectorAll("#lido-marca button[data-ato=marca]"))
                .map(b => b.querySelector(".modo-nome").textContent)''')
            assert nomes == ['Sem marca'] and pg.evaluate(JS_MARCAS_MARCADAS) == []
            assert pg.evaluate('() => document.getElementById("marca-nova-nome")') is None
            assert 'Configure' in pg.evaluate('() => document.getElementById("lido-marca").textContent')
            if capturas is not None:
                pg.locator('#bloco-marca').screenshot(path=str(capturas / '6-sem-biblioteca.png'))
        finally:
            nav.close()


# revisao do M3: o mesmo nome escrito de outro jeito (Unicode NFD, espacos repetidos ou de outro tipo, maiusculas que
# so o casefold junta) e a mesma marca; o nome novo entra na biblioteca na forma NFC, com um espaco so entre as palavras
CAFE = 'Café Sintético'
STRASSE = 'Marca Straße'


def _iguais_a_cafe_e_strasse():
    import unicodedata
    return (unicodedata.normalize('NFD', CAFE), 'Café  Sintético', 'Café Sintético',
            'CAFÉ SINTÉTICO', 'MARCA STRASSE', 'Marca　Straße')


def test_marca_nova_recusa_o_mesmo_nome_escrito_de_outro_jeito(job, tmp_path):
    import unicodedata

    from desdobra.marca import job as mj
    from desdobra.marca import perfil
    bib = tmp_path / 'biblioteca-da-agencia'
    bib.mkdir()
    perfil.criar(bib, CAFE)
    perfil.criar(bib, STRASSE)
    for nome in _iguais_a_cafe_e_strasse():
        assert mj.nome_novo(nome, bib) is None, ascii(nome)
    # o controle continua recusado, mesmo entre as palavras
    assert mj.nome_novo('Marca\tTab', bib) is None
    # o nome novo vai na forma NFC, com um espaco so
    assert mj.nome_novo(unicodedata.normalize('NFD', 'Marca Cinco Sintética'), bib) == 'Marca Cinco Sintética'
    assert mj.nome_novo(' Marca   Seis ', bib) == 'Marca Seis'
    conteudo = te.montar(job, biblioteca=str(bib))
    s = _servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        for nome in _iguais_a_cafe_e_strasse():
            assert _ato(s, biscoito, 'marca', {'escolha': 'nova', 'nome': nome})[0] == 403, ascii(nome)
        codigo, c2, p = _ato(s, biscoito, 'marca', {'escolha': 'nova',
                                                    'nome': unicodedata.normalize('NFD', 'Marca  Sete Sintética')})
        assert codigo == 200 and c2 == 200 and 'Marca Sete Sintética' in p['texto']
    finally:
        s.parar()
    nomes = [m['marca'] for m in perfil.listar(bib)]
    assert len(nomes) == 3 and 'Marca Sete Sintética' in nomes
    assert all(unicodedata.is_normalized('NFC', n) for n in nomes)


def test_marca_nova_no_chromium_avisa_o_nome_que_o_motor_recusa(job, biblioteca, capturas=None):
    """revisao do M3: o nome que o motor recusa (extensao de arquivo de fonte, a mesma marca escrita de outro jeito)
    desliga o "Criar e usar" com o motivo na linha do campo. O que so o motor sabe recusar volta como aviso no campo,
    sem a frase de tentar de novo, e o botao fica desligado ate o DA mudar o nome."""
    from playwright.sync_api import sync_playwright

    from desdobra.chromium import navegador
    from desdobra.marca import perfil
    bib, ids = biblioteca
    perfil.criar(bib, CAFE)
    perfil.criar(bib, STRASSE)
    navegador.apontar_playwright()
    js_erro = '() => { const e = document.getElementById("marca-nova-erro"); return e.hidden ? "" : e.textContent; }'
    js_desligado = '() => document.getElementById("marca-nova-criar").disabled'
    conteudo = te.montar(job, biblioteca=str(bib))
    with ts.ServidorTela(conteudo, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo)) as srv, sync_playwright() as pw:
        nav, pg = _abrir_passo_1(pw, srv)
        try:
            for nome in ('Studio.otf', 'Marca.TTF', 'Logo.woff2 final'):
                pg.fill('#marca-nova-nome', nome)
                assert pg.evaluate(js_desligado) is True, nome
                assert 'fonte' in pg.evaluate(js_erro), nome
            for nome in _iguais_a_cafe_e_strasse() + (MARCA_UM.upper(),):
                pg.fill('#marca-nova-nome', nome)
                assert pg.evaluate(js_desligado) is True, ascii(nome)
                assert 'lista acima' in pg.evaluate(js_erro), ascii(nome)
            if capturas is not None:
                pg.locator('#bloco-marca').screenshot(path=str(capturas / '7-nome-repetido-de-outro-jeito.png'))
            # o nome que so o motor recusa (bytes de fonte em base64): o aviso fica no campo
            pg.fill('#marca-nova-nome', 'T1RUTw')
            assert pg.evaluate(js_desligado) is False and pg.evaluate(js_erro) == ''
            pg.click('#marca-nova-criar')
            tp._esperar(pg, '() => document.documentElement.dataset.estadoAto === "erro" ? "1" : ""')
            assert pg.evaluate('() => document.getElementById("confirmacao").open') is False
            aviso = pg.evaluate(js_erro)
            assert 'não aceitou esse nome' in aviso, aviso
            assert '—' not in aviso and '–' not in aviso
            assert pg.evaluate(js_desligado) is True
            assert 'Tente de novo' not in pg.evaluate('() => document.getElementById("selo").textContent')
            if capturas is not None:
                pg.locator('#bloco-marca').screenshot(path=str(capturas / '8-nome-recusado-pelo-motor.png'))
            # mudar o nome tira o aviso e liga o botao de novo
            pg.fill('#marca-nova-nome', 'Marca Sintetica Oito')
            assert pg.evaluate(js_desligado) is False and pg.evaluate(js_erro) == ''
        finally:
            nav.close()
    assert len(perfil.listar(bib)) == 4
