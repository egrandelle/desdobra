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
  - o render recusa texto editado (o render do texto novo chega no M7b), nunca desenha o texto velho calado;
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
    conteudo = te.montar(job)
    antes = (job / mb.ARQUIVO).read_bytes()
    s = _servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        _preparar_rascunho(job, modelo, s, biscoito, conteudo, confirmar=False)
        assert {p['codigo'] for p in bs.pendencias(job, conteudo)} == {'familia_sem_confirmacao'}
        assert _salvar(s, biscoito, job)[0] == 403
    finally:
        s.parar()
    assert (job / mb.ARQUIVO).read_bytes() == antes
    assert not (job / mb.PASTA_HISTORICO).exists()


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

    def reencaixar(cf, caixas, sangra, apagados=()):
        novas, falha = original(cf, caixas, sangra, apagados)
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


def test_render_recusa_texto_editado(job):
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
    _contrato, bloqueios, _c = derivado.montar(job, 'v1')
    assert [b['codigo'] for b in bloqueios] == ['texto_editado_sem_render']


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
