# -*- coding: utf-8 -*-
"""0.9.1, texto como imagem: o KV tem texto vivo, mas a agencia nunca recebeu o arquivo da fonte.

Pedido aprovado pelo dono do produto ("Sim, como imagem"). Criterios cobertos aqui:
  - sem declaracao, o job trava como antes: arquivo_faltando bloqueante e o bloqueio da fase fontes no estado;
  - o DA declara na tela, por face que falta (nome PostScript), "Nao tenho esta fonte: usar o texto como imagem",
    com a confirmacao na propria janela e a rota generica dos atos (token, cookie, CSRF): a declaracao fica em
    briefing/texto-como-imagem.json com origem da, meio tela, quem e quando; o bloqueio da face vira decisao do DA e
    a fase fontes passa sem outro bloqueio; desfazer tambem e clique;
  - o Claude nao declara: o motor recusa sem o Disparo da tela, e o gancho nega a escrita e o codigo;
  - a conferencia e a fonte unica de quais camadas vao como imagem; arquivo que casa com a face derruba a declaracao;
  - derivacao e render tratam a camada inteira como imagem, pelos pixels da camada no PSD, sem quebra nem medida; o
    PNG final sai sem fonte nenhuma no job; ampliacao acima de 100% avisa como raster;
  - no palco, a peca e imagem, sem editar texto nem quebrar linha, com o selo "Texto como imagem";
  - para a classificacao de dados a camada continua texto: nunca vira miniatura no modo a;
  - o manifesto e o relatorio da entrega registram a decisao, sem recusar a entrega.
Tudo sintetico: os KVs de testes/sinteticos/kv_a_b.py, com o texto numa fonte inventada que nao existe no job.
"""
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pytest

import test_derivacao_apoio as ap
import test_fontes_apoio as fap
import test_tela_escrita as tte
import test_tela_servidor as tts
from desdobra import arquivos, contratos, humano
from desdobra.briefing import modelo as mb
from desdobra.derivacao import nucleo as nd
from desdobra.fontes import como_imagem as ci
from desdobra.fontes import conferencia
from desdobra.job import nucleo
from desdobra.tela import atos as ta
from desdobra.tela import estado as te
from desdobra.tela import servidor as ts
from sinteticos import kv_a_b as kv

PS = 'FonteInventada-Bold'
PROIBIDOS = ('\u2014', '\u2013', 'desdobra ', '--job', 'terminal')
SO_WINDOWS = pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')


# ------------------------------------------------------------------ geradores
def _criar_job(base):
    """O job do KV A sem nenhum arquivo de fonte: o titulo e o apoio sao texto vivo na fonte PS."""
    base = Path(base)
    job = base / 'job'
    nucleo.criar(job, kv.psd(base / 'origem' / 'kv-a.psd', 'a', PS), 'c')
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    return job


def _ids(job):
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    por_nome = {c['nome']: c['identidade']['layer_id'] for c in laudo['camadas']}
    return {papel: por_nome[nome] for papel, nome in kv.NOMES.items()}


def _briefing(job, base, da=False):
    """O briefing de teste do KV A (as funcoes, as regras e os tres formatos); com da, a origem trocada a mao como em
    test_cadeia_por_formato.py, para derivar e renderizar."""
    ids = _ids(job)
    funcoes = {ids[papel]: f for papel, f in kv.FUNCOES.items()}
    regras = dict(ap.REGRAS, **{f: r for f, (r, _x, _y) in kv.USADAS.items()})
    ancoras = dict(ap.ANCORAS, **{f: (x, y) for f, (_r, x, y) in kv.USADAS.items()})
    b = ap.briefing(funcoes=funcoes, regras=regras, ancoras=ancoras,
                    formatos=[ap.formato(i, w, h, rotacao={'graus': 0, 'sentido': None}) for i, w, h in kv.FORMATOS])
    b.pop('cabecalho')
    b.pop('job_id')
    arq = Path(base) / 'fixture-texto-imagem.json'
    arq.write_text(json.dumps(b), encoding='utf-8')
    mb.importar_teste(job, arq)
    if da:
        dados = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
        dados['cabecalho'].update(origem='da', meio='terminal')
        contratos.gravar(job / mb.ARQUIVO, dados, 'briefing/1')


def _limpar_ambiente(mp):
    for v in humano.VARIAVEIS_DO_CLAUDE + humano.VARIAVEIS_DO_PAINEL + tuple(humano.MARCAS_DO_PAINEL):
        mp.delenv(v, raising=False)
    from desdobra import cli
    mp.setattr(cli._Analisador, 'modo_envelope', False, raising=False)


def _ato(job, dados, teste=True, nome='texto_como_imagem'):
    """Pede o ato pela rota generica da tela e confirma. (codigo do pedido, codigo da confirmacao, pedido)."""
    s = ts.ServidorTela(tts._conteudo(), pasta=job, modo_teste=teste, atos=ta.atos_do_job(job)).iniciar()
    try:
        biscoito = tts._entrar(s)
        codigo, p = tte._pedir_ato(s, biscoito, nome=nome, dados=dados)
        if codigo != 200:
            return codigo, None, None
        c2 = tte._escrever(s, '/api/ato/confirmar', {'pedido': p['pedido'], 'resposta': 'confirmar'},
                           cookie=biscoito)[0]
        return codigo, c2, p
    finally:
        s.parar()


def _declarar_da(job, acao='declarar', ps=PS):
    with pytest.MonkeyPatch.context() as mp:
        _limpar_ambiente(mp)
        return _ato(job, {'nome_ps': ps, 'acao': acao}, teste=False)


def _conf(job):
    return contratos.ler(job / conferencia.ARQUIVO, conferencia.ESQUEMA)


def _itens(conf, ps=PS):
    return [c for c in conf['camadas'] if c['nome_ps'] == ps]


def _bloqueio_fontes(job):
    estado = nucleo.ler_estado(job)
    from desdobra.job import fases
    avaliacao, _d = nucleo.avaliar(job, estado, fases.ESTEIRA)
    return dict(nucleo.bloqueios_pendentes(estado, avaliacao, fases.ESTEIRA)).get('fontes')


@pytest.fixture(scope='module')
def job_base(tmp_path_factory):
    return _criar_job(tmp_path_factory.mktemp('texto-imagem'))


@pytest.fixture
def job(job_base, tmp_path):
    destino = tmp_path / 'job'
    shutil.copytree(job_base, destino)
    return destino


@pytest.fixture(scope='module')
def job_derivado(job_base, tmp_path_factory):
    """O job com a declaracao do DA pela tela (origem da), o briefing e a derivacao gravada."""
    base = tmp_path_factory.mktemp('texto-imagem-derivado')
    job = base / 'job'
    shutil.copytree(job_base, job)
    assert _declarar_da(job)[:2] == (200, 200)
    _briefing(job, base, da=True)
    nd.derivar(job)
    return job


# ------------------------------------------------------------------ conferencia e fase
def test_sem_declaracao_o_job_trava_como_antes(job_base):
    conf = _conf(job_base)
    itens = _itens(conf)
    assert len(itens) == 2 and all(i['situacao'] == 'bloqueante' and i['face_id'] is None for i in itens)
    assert all(any(m['codigo'] == 'arquivo_faltando' and m['situacao'] == 'bloqueante' for m in i['motivos'])
               for i in itens)
    assert conf.get('texto_como_imagem') is None and conf['resumo']['camadas_bloqueantes'] == 2
    assert _bloqueio_fontes(job_base) is not None
    assert nd._portao_fontes(job_base) == 'bloqueado'
    assert ci.camadas(job_base) == frozenset()


def _declaracao(nomes, laudo_sha, origem='da'):
    return {'esquema': ci.ESQUEMA, 'job_id': 'ab' * 16, 'laudo_sha256': laudo_sha, 'kv_sha256': 'c' * 64,
            'faces': [{'nome_ps': n, 'camadas': [], 'origem': origem,
                       'decidido_por': {'usuario': 'u', 'maquina': 'm', 'meio': 'tela',
                                        'quando': '2026-11-16T10:00:00-03:00'}} for n in nomes],
            'historico': []}


def _motivo(codigo, situacao='bloqueante'):
    return {'codigo': codigo, 'situacao': situacao, 'descricao': codigo, 'medida': None, 'limite': None}


def _item(lid, ps, face_id, *codigos, situacao='bloqueante'):
    mot = [_motivo(c, situacao) for c in codigos]
    return {'layer_id': lid, 'nome_ps': ps, 'face_id': face_id, 'metodo_casamento': None, 'glifos_faltando': 0,
            'largura_erro_max_pct': None, 'largura_erro_pct': None, 'face_cdp_confere': None,
            'situacao': conferencia.pior(mot) if mot else 'ok', 'decisao': None, 'motivos': mot}


def _conf_a_mao(camadas):
    return {'esquema': conferencia.ESQUEMA, 'laudo_sha256': 'a' * 64, 'faces': [], 'camadas': camadas,
            'arquivos': [], 'cache': {'copias_encontradas': None, 'feito': False}, 'resumo': {}}


def test_declaracao_rebaixa_os_tres_motivos_e_marca_a_decisao():
    conf = _conf_a_mao([_item(1, 'A-Bold', None, 'arquivo_faltando'),
                        _item(2, 'B-Bold', None, 'nome_ps_sem_par', 'face_divergente'),
                        _item(3, 'C-Bold', 'f01', 'glifo_faltando')])
    novo = ci.aplicar(conf, _declaracao(['A-Bold', 'B-Bold'], 'a' * 64))
    a, b, c = novo['camadas']
    for it in (a, b):
        assert it['situacao'] == 'aviso' and it['decisao'] == ci.DECISAO
        assert {m['codigo'] for m in it['motivos'] if m['situacao'] == 'bloqueante'} == set()
        assert any(m['codigo'] == 'texto_como_imagem' for m in it['motivos'])
    # glifo faltando, numa camada sem face declarada, continua bloqueando (fora do escopo)
    assert c['situacao'] == 'bloqueante' and c['decisao'] is None
    bloco = novo['texto_como_imagem']
    assert bloco['faces'] == ['A-Bold', 'B-Bold'] and bloco['camadas'] == [1, 2] and bloco['caidas'] == []
    assert novo['resumo']['camadas_bloqueantes'] == 1 and novo['resumo']['textos_como_imagem'] == 2
    # desfazer e a volta exata
    volta = ci.remover(novo)
    assert volta['camadas'] == conf['camadas'] and 'texto_como_imagem' not in volta


def test_camada_mista_vai_inteira_e_o_trecho_da_outra_face_deixa_de_bloquear():
    conf = _conf_a_mao([_item(1, 'A-Bold', None, 'arquivo_faltando'), _item(1, 'C-Bold', 'f01', 'glifo_faltando'),
                        _item(2, 'C-Bold', 'f01', 'glifo_faltando')])
    novo = ci.aplicar(conf, _declaracao(['A-Bold'], 'a' * 64))
    assert [i['situacao'] for i in novo['camadas']] == ['aviso', 'aviso', 'bloqueante']
    assert novo['texto_como_imagem']['camadas'] == [1]
    assert ci.remover(novo)['camadas'] == conf['camadas']


def test_arquivo_que_casa_derruba_a_declaracao_e_o_que_nao_confere_nao():
    conf = _conf_a_mao([_item(1, 'A-Bold', 'f01')])
    novo = ci.aplicar(conf, _declaracao(['A-Bold'], 'a' * 64))
    assert novo['camadas'] == conf['camadas']
    assert novo['texto_como_imagem']['caidas'] == ['A-Bold'] and novo['texto_como_imagem']['camadas'] == []
    # o arquivo chegou, mas nao confere (largura de outra versao): a declaracao segue valendo
    diverge = _conf_a_mao([_item(1, 'A-Bold', 'f01', 'largura_divergente')])
    outro = ci.aplicar(diverge, _declaracao(['A-Bold'], 'a' * 64))
    assert outro['texto_como_imagem']['camadas'] == [1] and outro['texto_como_imagem']['caidas'] == []
    assert outro['camadas'][0]['situacao'] == 'aviso' and ci.remover(outro)['camadas'] == diverge['camadas']


# ------------------------------------------------------------------ o ato da tela e o gancho
def test_declaracao_pela_tela_de_verdade_libera_a_fase_e_grava_quem_e_quando(job):
    ids = _ids(job)
    codigo, c2, p = _declarar_da(job)
    assert (codigo, c2) == (200, 200)
    assert 'pixels do PSD' in p['texto'] and '2 camadas' in p['texto']
    assert not any(x in p['texto'] for x in PROIBIDOS)
    decl = ci.ler(job)
    face = decl['faces'][0]
    assert face['nome_ps'] == PS and face['origem'] == 'da' and face['decidido_por']['meio'] == 'tela'
    assert face['decidido_por']['quando'] and sorted(face['camadas']) == sorted([ids['titulo'], ids['apoio']])
    conf = _conf(job)
    assert all(i['situacao'] == 'aviso' and i['decisao'] == ci.DECISAO for i in _itens(conf))
    assert conf['texto_como_imagem']['origem'] == 'da'
    assert ci.camadas(job) == frozenset({ids['titulo'], ids['apoio']})
    # a fase fontes fica em dia e sem bloqueio; a segunda passada e o design system tambem
    assert nucleo.fases_invalidas(job) == set() and _bloqueio_fontes(job) is None
    lf = contratos.ler(job / 'laudo' / 'laudo-fontes.json', 'laudo/1')
    usada = next(u for u in lf['fontes_usadas'] if u['fonte_ps'] == PS)
    assert usada['situacao'] == 'texto_como_imagem'
    assert not [c for c in lf['camadas'] if c['situacao'] == 'bloqueante']
    assert nd._portao_fontes(job) == 'passa'
    assert ts._job_do_da(job)  # a declaracao do DA conta como decisao dele: o modo de teste da tela recusa o job
    # desfazer, tambem por clique: o bloqueio volta
    codigo, c2, p = _declarar_da(job, acao='desfazer')
    assert (codigo, c2) == (200, 200) and 'espera' in p['texto']
    assert ci.ler(job)['faces'] == [] and _bloqueio_fontes(job) is not None
    assert all(i['situacao'] == 'bloqueante' for i in _itens(_conf(job)))
    assert [h['acao'] for h in ci.ler(job)['historico']] == ['declarar', 'desfazer']


def test_sem_disparo_da_tela_o_motor_recusa(job):
    with pytest.raises(humano.ErroHumano):
        ci.gravar(job, PS, 'declarar', disparo=None)
    sessao = humano.abrir_sessao_tela(teste=True)
    outro = humano.exigir_tela('modo dados escolher', sessao, confirmado=True)
    with pytest.raises(humano.ErroHumano):
        ci.gravar(job, PS, 'declarar', disparo=outro)
    assert ci.ler(job) is None


@pytest.mark.parametrize('dados', [{'nome_ps': 'OutraFonte-Regular', 'acao': 'declarar'},
                                   {'nome_ps': PS, 'acao': 'desfazer'}, {'nome_ps': PS, 'acao': 'apagar'},
                                   {'nome_ps': PS}, {'nome_ps': 3, 'acao': 'declarar'}])
def test_ato_recusa_antes_da_janela_o_que_nao_e_declaravel(job, dados):
    assert _ato(job, dados)[0] == 403
    assert ci.ler(job) is None


def test_modo_de_teste_grava_fixture_e_o_render_recusa(job):
    assert _ato(job, {'nome_ps': PS, 'acao': 'declarar'})[:2] == (200, 200)
    assert ci.ler(job)['faces'][0]['origem'] == 'fixture_de_teste'
    assert _conf(job)['texto_como_imagem']['origem'] == 'fixture_de_teste'
    from desdobra.render import contrato as mc
    _c, bloqueios, _conf_ = mc.montar(job)
    assert 'texto_como_imagem_no_modo_de_teste' in {b['codigo'] for b in bloqueios}


@pytest.mark.parametrize('caminho', ['C:/jobs/kv/briefing/texto-como-imagem.json', 'briefing\\texto-como-imagem.json'])
def test_gancho_nega_escrever_a_declaracao(caminho):
    g = tts._gancho()
    for ferramenta in ('Write', 'Edit'):
        assert g.decidir({'tool_name': ferramenta, 'tool_input': {'file_path': caminho}}) == 'deny'
    assert g.decidir({'tool_name': 'Bash', 'tool_input': {
        'command': 'echo {} > C:/j/briefing/texto-como-imagem.json'}}) == 'deny'


@pytest.mark.parametrize('comando', [
    'python -c "from desdobra.fontes import como_imagem; como_imagem.gravar(1, 2, 3, disparo=None)"',
    'python -c "import desdobra.fontes.como_imagem as c"',
    'python -c "from desdobra.fontes.como_imagem import reaplicar; reaplicar(1)"',
])
def test_gancho_nega_o_codigo_da_declaracao(comando):
    g = tts._gancho()
    assert g.decidir({'tool_name': 'Bash', 'tool_input': {'command': comando}}) == 'deny'


def test_ato_da_tela_registrado_no_humano():
    assert ci.COMANDO in humano.ATOS_DA_TELA and ci.COMANDO not in humano.COMANDOS


def test_arquivo_da_fonte_que_chega_derruba_a_declaracao_com_aviso(job, tmp_path):
    assert _declarar_da(job)[:2] == (200, 200)
    fonte = _fonte_que_confere(tmp_path / 'novas')
    nucleo.trocar_entrada(job, 'entrada/fontes/chegou.ttf', fonte)
    nucleo.proxima(job, todas=True)
    conf = _conf(job)
    assert conf['texto_como_imagem']['caidas'] == [PS] and conf['texto_como_imagem']['camadas'] == []
    assert all(i['face_id'] is not None and i['decisao'] != ci.DECISAO for i in _itens(conf))
    assert ci.camadas(job) == frozenset()
    c = te.montar(job)
    caidas = c['estado']['lido']['declaracoes_caidas']
    assert [x['fonte_ps'] for x in caidas] == [PS] and 'texto vivo' in caidas[0]['texto']


# ------------------------------------------------------------------ derivacao e render
def test_elemento_do_texto_declarado_e_imagem_na_mestre(job_derivado):
    ids = _ids(job_derivado)
    ctx = nd.preparar(job_derivado)
    m = nd.mestre_do_kv(ctx)
    el = next(e for e in m['elementos'] if ids['titulo'] in e['layer_ids'])
    assert el['texto'] is False and el['texto_como_imagem'] == [ids['titulo']]
    assert el['folga_resolucao'] == 1.0 and el['corpo_px']
    assert not m['blocos_partidos']


def test_derivacao_avisa_a_ampliacao_e_nao_pede_quebra(job_derivado):
    ids = _ids(job_derivado)
    d = contratos.ler(job_derivado / 'derivacao' / 'p800.json', nd.ESQUEMA)
    el = next(e for e in d['elementos'] if ids['titulo'] in e['layer_ids'])
    assert el['texto_como_imagem'] == [ids['titulo']] and el['quebras'] is None and el['texto'] is False
    folga = [v for v in d['validacoes'] if v['nome'] == 'folga_de_resolucao' and el['id'] in v['elementos']]
    assert folga and folga[0]['situacao'] == 'avisa'
    assert not [v for v in d['validacoes'] if v['nome'] == 'quebras_sem_aprovacao']


def test_contrato_da_origem_poe_a_camada_numa_pilha(job_derivado):
    from desdobra.render import contrato as mc
    ids = _ids(job_derivado)
    contrato, bloqueios, _confirmar = mc.montar(job_derivado)
    assert bloqueios == []
    assert not [e for e in contrato['entradas'] if e['tipo'] == 'texto']
    em_pilha = {lid for e in contrato['entradas'] if e['tipo'] == 'pilha' for lid in e['layer_ids']}
    assert {ids['titulo'], ids['apoio']} <= em_pilha
    regs = [r for r in contrato['registros'] if r['codigo'] == ci.REGISTRO_RENDER]
    assert sorted(r['layer_id'] for r in regs) == sorted([ids['titulo'], ids['apoio']])
    assert contrato['faces'] == []


@SO_WINDOWS
def test_render_do_formato_sai_com_os_pixels_da_camada_sem_fonte(job_derivado, tmp_path):
    from PIL import Image

    from desdobra.render import execucao
    job = tmp_path / 'job'
    shutil.copytree(job_derivado, job)
    ids = _ids(job)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(humano, 'console_interativo', lambda: (True, None))
        execucao.renderizar(job, disparo=humano.exigir('render'), formato='p800')
    assert not [r for r in nucleo.ler_estado(job)['entradas'] if r.startswith('entrada/fontes/')]  # nenhuma fonte
    rj = contratos.ler(job / 'render' / 'p800' / 'render.json', execucao.ESQUEMA_RENDER)
    assert ci.REGISTRO_RENDER in {r['codigo'] for r in rj['registros']}
    assert not [e for e in rj.get('entradas') or [] if e.get('tipo') == 'texto']
    d = contratos.ler(job / 'derivacao' / 'p800.json', nd.ESQUEMA)
    el = next(e for e in d['elementos'] if ids['titulo'] in e['layer_ids'])
    x0, y0, x1, y1 = el['caixa']
    with Image.open(job / 'render' / 'p800' / 'master.png') as img:
        px = img.convert('RGB').getpixel((int((x0 + x1) / 2), int((y0 + y1) / 2)))
    assert all(abs(a - b) <= 6 for a, b in zip(px, (20, 20, 20))), px


# ------------------------------------------------------------------ tela
def test_passo_1_mostra_o_botao_e_depois_a_decisao(job):
    ids = _ids(job)
    c = te.montar(job)
    falta = c['estado']['lido']['fontes_que_faltam']
    assert [(f['fonte_ps'], f['declaravel']) for f in falta] == [(PS, True)]
    assert sorted(falta[0]['camadas_nomes']) == sorted([kv.NOMES['titulo'], kv.NOMES['apoio']])
    assert c['estado']['lido']['textos_como_imagem'] == []
    assert _declarar_da(job)[:2] == (200, 200)
    c = te.montar(job)
    lido = c['estado']['lido']
    assert lido['fontes_que_faltam'] == [] and not lido['bloqueios']
    assert [x['fonte_ps'] for x in lido['textos_como_imagem']] == [PS]
    assert sorted(lido['textos_como_imagem'][0]['camadas']) == sorted([kv.NOMES['titulo'], kv.NOMES['apoio']])
    assert not any(i['detalhe'] == PS for i in c['estado'].get('faltam') or [])
    assert ids['titulo']


def _pecas_da_camada(c, lid):
    saida = []
    for prev in (c.get('previas') or {}).values():
        saida += [p for p in prev.get('pecas') or [] if p.get('camada') == lid]
    return saida


def test_palco_mostra_a_camada_como_imagem_sem_editar_texto(job_derivado):
    from desdobra.tela import edicao
    ids = _ids(job_derivado)
    c = te.montar(job_derivado)
    pecas = _pecas_da_camada(c, ids['titulo'])
    assert pecas and all(p['tipo'] == 'imagem' and p['como_imagem'] is True and 'linhas' not in p for p in pecas)
    ctx = nd.preparar(job_derivado, partida=True)
    base = te.pecas_base(ctx['laudo'], {}, lambda ps: None)
    assert base[ids['titulo']]['como_imagem'] is True and 'linhas' not in base[ids['titulo']]
    assert edicao.TEXTO_COMO_IMAGEM and not any(x in edicao.TEXTO_COMO_IMAGEM for x in PROIBIDOS)


def test_palco_no_chromium_com_o_selo(job_derivado, tmp_path):
    from playwright.sync_api import sync_playwright

    import test_tela_palco as tp
    from desdobra.chromium import navegador
    ids = _ids(job_derivado)
    c = te.montar(job_derivado)
    navegador.apontar_playwright()
    destino = Path(os.environ.get('DESDOBRA_FOTOS_TEXTO_IMAGEM') or tmp_path)
    with ts.ServidorTela(c) as srv, sync_playwright() as pw:
        nav, pg = tp._pagina_da_tela(pw, srv, 1400, 900)
        try:
            pecas = pg.evaluate('''() => Array.from(document.querySelectorAll("#palco .como-imagem"))
                .map(n => [n.parentElement.dataset.camada, n.parentElement.dataset.elemento,
                           n.querySelectorAll(".selo-texto-imagem").length])''')
            peca = next(p for p in pecas if p[0] == str(ids['titulo']))
            # revisao da tela, D4: o selo vai na etiqueta do elemento, fora dos pixels da camada
            assert peca[2] == 0, pecas
            selo = pg.evaluate('''e => { const s = document.querySelector('#palco .rotulo[data-elemento="' + e +
                '"] .selo-texto-imagem'); return s ? s.textContent : null; }''', peca[1])
            assert selo == 'Texto como imagem'
            # Ver limpo: o selo e o contorno da peca saem com os rotulos
            limpo = pg.evaluate('''() => { const p = document.getElementById("palco"); p.classList.add("limpo");
                const selos = Array.from(p.querySelectorAll(".selo-texto-imagem")).filter(s => s.offsetParent);
                const cont = Array.from(p.querySelectorAll(".peca.como-imagem")).map(n => getComputedStyle(n).outlineStyle);
                p.classList.remove("limpo"); return [selos.length, cont]; }''')
            assert limpo[0] == 0 and all(x == 'none' for x in limpo[1]), limpo
            assert pg.evaluate('''l => document.querySelectorAll('#palco .recorte[data-camada="' + l + '"] .texto')
                .length''', str(ids['titulo'])) == 0
            assert pg.evaluate('() => document.getElementById("ed-texto").disabled') is True
            destino.mkdir(parents=True, exist_ok=True)
            pg.screenshot(path=str(destino / 'palco-texto-como-imagem.png'))
        finally:
            nav.close()


def test_passo_1_no_chromium_botao_janela_e_desfazer(job, tmp_path):
    from playwright.sync_api import sync_playwright

    import test_tela_palco as tp
    from desdobra.chromium import navegador
    c = te.montar(job)
    navegador.apontar_playwright()
    destino = Path(os.environ.get('DESDOBRA_FOTOS_TEXTO_IMAGEM') or tmp_path)
    destino.mkdir(parents=True, exist_ok=True)
    botao = '#fontes button[data-ato="texto_como_imagem"]'
    with ts.ServidorTela(c, pasta=job, modo_teste=True, atos=ta.atos_do_job(job)) as srv, sync_playwright() as pw:
        nav = pw.chromium.launch(headless=True, args=list(navegador.ARGUMENTOS))
        pg = nav.new_context(viewport={'width': 1400, 'height': 900}).new_page()
        try:
            try:
                pg.goto(srv.url_entrada, wait_until='commit')
            except Exception:  # noqa: BLE001 - o 204 nao completa a navegacao
                pass
            pg.goto(srv.url_pagina, wait_until='load')
            tp._esperar(pg, tp.JS_PRONTO)
            assert pg.evaluate('s => document.querySelector(s).textContent', botao) == \
                'Não tenho esta fonte: usar o texto como imagem'
            # revisao da tela, D5: a nota antes do clique fala do que acontece se o DA decidir, no plural certo
            nota = pg.evaluate('() => document.querySelector("#fontes .fonte-falta .nota").textContent')
            assert 'Se você usar o texto como imagem, as 2 camadas vão pelos pixels do PSD' in nota, nota
            assert not any(x in nota for x in PROIBIDOS)
            pg.evaluate('s => document.querySelector(s).scrollIntoView()', botao)
            pg.screenshot(path=str(destino / 'passo-1-botao.png'))
            pg.evaluate('s => document.querySelector(s).click()', botao)
            tp._esperar(pg, '() => document.getElementById("confirmacao").open ? "1" : ""')
            extra = pg.evaluate('() => Array.from(document.querySelectorAll("#confirmacao-extra li"))'
                                '.map(x => x.textContent)')
            assert sorted(extra) == sorted([kv.NOMES['titulo'], kv.NOMES['apoio']])
            texto = pg.evaluate('() => document.getElementById("confirmacao-texto").textContent')
            assert 'pixels do PSD' in texto and not any(x in texto for x in PROIBIDOS)
            pg.screenshot(path=str(destino / 'passo-1-janela.png'))
            pg.evaluate('''() => Array.from(document.querySelectorAll("#confirmacao button"))
                .find(b => b.textContent === "Confirmar").click()''')
            tp._esperar(pg, '() => document.documentElement.dataset.estadoAto === "feito" ? "1" : ""')
            tp._esperar(pg, '() => document.querySelector("#fontes .fonte-como-imagem") ? "1" : ""')
            assert ci.ler(job)['faces'][0]['nome_ps'] == PS
            pg.evaluate('() => document.querySelector("#fontes .fonte-como-imagem").scrollIntoView()')
            pg.screenshot(path=str(destino / 'passo-1-decidido.png'))
            assert pg.evaluate('() => document.querySelectorAll("form, [onerror]").length') == 0
        finally:
            nav.close()
    assert srv.contagem['csrf_recusado'] == 0


# ------------------------------------------------------------------ dados e entrega
def test_modo_a_a_camada_continua_texto_e_nunca_vira_miniatura(job_derivado, tmp_path):
    from conftest import escolher_modo_do_da
    from desdobra.sugestao import miniaturas, pacote
    job = tmp_path / 'job'
    shutil.copytree(job_derivado, job)
    ids = _ids(job)
    escolher_modo_do_da(job, 'a')
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    assert ids['titulo'] not in miniaturas.camadas_permitidas(laudo, pasta_laudo=job / 'laudo')
    pacote.gravar_pacote(job)
    pac = arquivos.ler_json(job / pacote.ARQUIVO_PACOTE)
    item = next(x for x in pac['camadas'] if x['layer_id'] == ids['titulo'])
    assert item['tipo'] == 'texto'
    assert pac['modo_dados'] == 'a' and pac['miniaturas']  # o modo a mandou miniaturas de outras camadas
    assert pacote.caminho_da_miniatura(ids['titulo']) not in pac['miniaturas']
    assert pacote.caminho_da_miniatura(ids['apoio']) not in pac['miniaturas']


def test_manifesto_e_relatorio_registram_a_decisao_sem_recusar(job_derivado):
    from desdobra.entrega import relatorio, validar
    ids = _ids(job_derivado)
    man = relatorio.manifesto(job_derivado, 'ab' * 16, datetime.now().astimezone())
    reg = man['textos_como_imagem']
    assert [x['nome_ps'] for x in reg] == [PS] and reg[0]['decidido_por']['meio'] == 'tela'
    assert sorted(reg[0]['camadas']) == sorted([ids['titulo'], ids['apoio']])
    d = contratos.ler(job_derivado / 'derivacao' / 'p800.json', nd.ESQUEMA)
    ctx = {'render': {'entradas': [], 'registros': [{'codigo': ci.REGISTRO_RENDER, 'layer_id': ids['titulo'],
                                                    'medidas': {}}]},
           'derivacao': d}
    itens = validar.texto_como_imagem(ctx)
    assert [(i['nome'], i['situacao'], i['regra']) for i in itens] == \
        [('texto_como_imagem', 'registra', ci.REGISTRO_RENDER)]
    assert itens[0]['medidas']['camadas'] == [ids['titulo']]
    caixas = {cid for cid, _c, _s in validar.caixas_de_conteudo(ctx)}
    el = next(e for e in d['elementos'] if ids['titulo'] in e['layer_ids'])
    assert 'texto_como_imagem:%s:%d' % (el['id'], ids['titulo']) in caixas


# ------------------------------------------------------------------ revisoes adversariais do 0.9.1
def _fonte_que_confere(pasta):
    """A fonte PS com as larguras do KV A (as de test_tela_palco.AVANCOS): a conferencia passa sem motivo."""
    import test_tela_palco as tp
    return fap.gravar(pasta, 'confere.ttf', fap.fonte(ps=PS, familia='FonteInventada', avancos=tp.AVANCOS))


def _fonte_que_nao_confere(pasta):
    """A fonte PS de outra versao: casa pelo nome PostScript, mas a largura diverge da do PSD."""
    return fap.gravar(pasta, 'outra-versao.ttf', fap.fonte(ps=PS, familia='FonteInventada'))


def test_releitura_do_mesmo_psd_mantem_a_declaracao(job, tmp_path):
    """Corretude 1: o laudo.json muda a cada leitura (recursos), mas o KV e o mesmo: a declaracao continua valendo."""
    from PIL import Image
    ids = _ids(job)
    assert _declarar_da(job)[:2] == (200, 200)
    sha_antes = arquivos.sha256_arquivo(job / 'laudo' / 'laudo.json')
    arq = tmp_path / 'campanha-x.png'
    Image.new('RGB', (4, 4), (1, 2, 3)).save(arq)
    nucleo.trocar_entrada(job, 'entrada/campanha/campanha-x.png', arq)
    nucleo.proxima(job, todas=True)
    assert arquivos.sha256_arquivo(job / 'laudo' / 'laudo.json') != sha_antes  # o motor releu o PSD
    assert ci.camadas(job) == frozenset({ids['titulo'], ids['apoio']})
    assert _bloqueio_fontes(job) is None
    lido = te.montar(job)['estado']['lido']
    assert [x['fonte_ps'] for x in lido['textos_como_imagem']] == [PS] and lido['declaracoes_caidas'] == []


def test_declaracao_de_outro_kv_nao_vale():
    decl = dict(_declaracao([PS], 'a' * 64), kv_sha256='c' * 64)
    assert ci.vale_para(decl, 'c' * 64) and not ci.vale_para(decl, 'd' * 64) and not ci.vale_para(None, 'c' * 64)


def test_area_segura_do_texto_como_imagem_usa_a_caixa_da_camada():
    """Corretude 2: a funcao dada a um grupo (faixa que sangra com o texto dentro): a area segura confere a caixa da
    camada de texto escalada, nunca a caixa do elemento inteiro."""
    from desdobra.entrega import validar as v
    zona = [40.0, 40.0, 1040.0, 1040.0]
    el = {'id': 'e07', 'caixa': [0.0, 800.0, 1080.0, 1000.0], 'classe': 'conteudo', 'layer_ids': [11, 12],
          'texto_como_imagem': [12], 'caixas_texto_como_imagem': [{'layer_id': 12, 'caixa': [120, 860, 960, 940]}],
          'transformacao': {'sangra': {'esq': True, 'dir': True}}}
    ctx = {'render': {'entradas': [], 'registros': []}, 'derivacao': {'elementos': [el]}}
    caixas = v.caixas_de_conteudo(ctx)
    assert [(cid, c) for cid, c, _s in caixas] == [('texto_como_imagem:e07:12', [120.0, 860.0, 960.0, 940.0])]
    assert all(not v._fora(c, zona, 0.0, sg) for _cid, c, sg in caixas)


def test_derivacao_grava_a_caixa_da_camada_como_imagem(job_derivado):
    ids = _ids(job_derivado)
    d = contratos.ler(job_derivado / 'derivacao' / 'p800.json', nd.ESQUEMA)
    el = next(e for e in d['elementos'] if ids['titulo'] in e['layer_ids'])
    cx = {x['layer_id']: x['caixa'] for x in el['caixas_texto_como_imagem']}
    assert set(cx) == {ids['titulo']}
    c, e = cx[ids['titulo']], el['caixa']
    assert c[0] >= e[0] - 0.5 and c[1] >= e[1] - 0.5 and c[2] <= e[2] + 0.5 and c[3] <= e[3] + 0.5 and c[2] > c[0]


def test_face_nao_declarada_na_camada_declarada_continua_faltando(job_base):
    """Corretude 3: a camada do titulo usa F e G, sem arquivo; o DA declara so F. A camada vai inteira como imagem, mas
    G nunca vira decisao do DA na segunda passada: continua ausente na tela."""
    import copy

    from desdobra.laudo import fontes as segunda
    g = 'OutraInventada-Regular'
    tit = _ids(job_base)['titulo']
    laudo = copy.deepcopy(contratos.ler(job_base / 'laudo' / 'laudo.json', 'laudo/1'))
    conf = copy.deepcopy(_conf(job_base))
    item_f = next(i for i in conf['camadas'] if i['layer_id'] == tit and i['nome_ps'] == PS)
    conf['camadas'].append(dict(copy.deepcopy(item_f), nome_ps=g))
    laudo['fontes_usadas'].append(dict(next(u for u in laudo['fontes_usadas'] if u['fonte_ps'] == PS),
                                       fonte_ps=g, camadas=[tit]))
    novo = ci.aplicar(conf, _declaracao([PS], conf['laudo_sha256']))
    assert novo['texto_como_imagem']['faces'] == [PS] and tit in novo['texto_como_imagem']['camadas']
    assert novo['resumo']['camadas_bloqueantes'] == 0
    lf = segunda.aplicar_conferencia(laudo, novo, 'x' * 64, conf['laudo_sha256'])
    sit = {u['fonte_ps']: u['situacao'] for u in lf['fontes_usadas']}
    assert sit == {PS: 'texto_como_imagem', g: 'ausente'}


@pytest.mark.parametrize('ferramenta,cwd,comando', [
    ('PowerShell', 'C:\\jobs\\kv-x\\briefing', "Set-Content -Path texto-como-imagem.json -Value '{}'"),
    ('Bash', 'C:\\jobs\\kv-x\\briefing', "echo '{}' > texto-como-imagem.json"),
    ('Bash', 'C:\\jobs\\kv-x\\briefing', "echo '{}' > outro.json"),
    ('PowerShell', None, "Set-Location C:\\jobs\\kv-x\\briefing; Set-Content -Path texto-como-imagem.json -Value '{}'"),
    ('Bash', None, "cd /c/jobs/kv-x/briefing && echo '{}' > texto-como-imagem.json"),
    ('Bash', None, 'cp /c/tmp/texto-como-imagem.json /c/jobs/kv-x/briefing'),
    ('Bash', None, 'cp /c/tmp/x.json /c/jobs/kv-x/briefing'),
    ('PowerShell', None, 'Copy-Item C:\\tmp\\texto-como-imagem.json -Destination C:\\jobs\\kv-x\\briefing'),
    ('PowerShell', None, 'Copy-Item C:\\tmp\\x.json -Destination C:\\jobs\\kv-x\\derivacao'),
    ('Bash', 'C:\\jobs\\kv-x', 'cp /c/tmp/x.json briefing'),
])
def test_gancho_nega_a_declaracao_pelo_cwd_e_pela_pasta_sem_barra(ferramenta, cwd, comando):
    """Seguranca D1: o gancho olha o cwd do evento e a pasta do DA sem a barra do fim."""
    g = tts._gancho()
    assert g.decidir({'tool_name': ferramenta, 'cwd': cwd, 'tool_input': {'command': comando}}) == 'deny'


_PACOTE = Path(__file__).resolve().parents[1] / 'motor' / 'desdobra'


@pytest.mark.parametrize('cwd,comando', [
    (None, 'echo o briefing do job > notas.txt'),
    ('C:\\jobs\\kv-x', 'cat briefing/briefing.json'),
    (str(_PACOTE / 'derivacao'), "sed -i 's/a/b/' nucleo.py"),
    (str(_PACOTE), "cd entrega && sed -i 's/a/b/' validar.py"),
])
def test_gancho_deixa_o_que_nao_grava_na_pasta_do_da(cwd, comando):
    g = tts._gancho()
    assert g.decidir({'tool_name': 'Bash', 'cwd': cwd, 'tool_input': {'command': comando}}) is None


def test_arquivo_que_confere_derruba_a_declaracao_e_libera(job, tmp_path):
    """Tela D1 e D3: so o arquivo que confere derruba a declaracao. A janela de tirar a declaracao caida nao diz que o
    job vai esperar o arquivo."""
    assert _declarar_da(job)[:2] == (200, 200)
    nucleo.trocar_entrada(job, 'entrada/fontes/confere.ttf', _fonte_que_confere(tmp_path / 'novas'))
    nucleo.proxima(job, todas=True)
    conf = _conf(job)
    assert conf['texto_como_imagem']['caidas'] == [PS] and conf['texto_como_imagem']['camadas'] == []
    assert _bloqueio_fontes(job) is None
    lido = te.montar(job)['estado']['lido']
    assert lido['fontes_que_faltam'] == [] and [x['fonte_ps'] for x in lido['declaracoes_caidas']] == [PS]
    texto = ta.atos_do_job(job)['texto_como_imagem'].texto({'nome_ps': PS, 'acao': 'desfazer'})
    assert 'espera' not in texto and 'parado' not in texto and not any(x in texto for x in PROIBIDOS)


def test_arquivo_que_nao_confere_mantem_a_declaracao(job, tmp_path):
    """Tela D1: chega um arquivo com o mesmo nome PostScript, mas de outra versao (largura divergente). A face continua
    sem conferir, a declaracao continua valendo e o job nao volta a travar."""
    ids = _ids(job)
    assert _declarar_da(job)[:2] == (200, 200)
    nucleo.trocar_entrada(job, 'entrada/fontes/outra-versao.ttf', _fonte_que_nao_confere(tmp_path / 'novas'))
    nucleo.proxima(job, todas=True)
    conf = _conf(job)
    assert all(i['face_id'] is not None and i['decisao'] == ci.DECISAO for i in _itens(conf))
    assert conf['texto_como_imagem']['caidas'] == [] and ci.camadas(job) == frozenset({ids['titulo'], ids['apoio']})
    assert _bloqueio_fontes(job) is None
    lido = te.montar(job)['estado']['lido']
    assert lido['fontes_que_faltam'] == [] and lido['declaracoes_caidas'] == []
    assert [x['fonte_ps'] for x in lido['textos_como_imagem']] == [PS]


def test_fonte_que_nao_confere_pode_ir_como_imagem(job, tmp_path):
    """Tela D1 e D2: com o arquivo que nao confere ja no job, a tela oferece o botao, e o bloqueio fala do texto como
    imagem porque ha botao."""
    nucleo.trocar_entrada(job, 'entrada/fontes/outra-versao.ttf', _fonte_que_nao_confere(tmp_path / 'novas'))
    nucleo.proxima(job, todas=True)
    lido = te.montar(job)['estado']['lido']
    assert [(f['fonte_ps'], f['situacao'], f['declaravel']) for f in lido['fontes_que_faltam']] == \
        [(PS, 'divergente', True)]
    assert [b['fase'] for b in lido['bloqueios']] == ['fontes'] and 'texto como imagem' in lido['bloqueios'][0]['texto']
    assert _declarar_da(job)[:2] == (200, 200)
    assert _bloqueio_fontes(job) is None


def test_bloqueio_das_fontes_so_fala_do_texto_como_imagem_quando_ha_botao():
    """Tela D2: sem face que o DA possa declarar, o bloqueio nao manda usar o texto como imagem."""
    b = {'situacao': 'ok_com_bloqueio', 'o_que_fazer': 'x', 'contagens': {}}
    sem = te.bloqueio_na_tela('fontes', b)['texto']
    com = te.bloqueio_na_tela('fontes', b, declaravel=True)['texto']
    assert 'texto como imagem' not in sem and 'texto como imagem' in com
    assert not any(x in sem + com for x in PROIBIDOS if x != 'desdobra ')


def test_fonte_que_falta_conta_uma_vez_em_faltam():
    """Tela D6: o bloqueio da fase fontes e a fonte que falta sao o mesmo pendente."""
    lido_ = {'modo_dados': {'escolhido': 'b'}, 'paradas': [], 'camadas_bloqueadas': [], 'linkados': [],
             'bloqueios': [te.bloqueio_na_tela('fontes', {'situacao': 'ok_com_bloqueio'}, declaravel=True)],
             'specs': {'pendentes': 0, 'formatos': [{'id': 'p800', 'rotacao': {'graus': 0}}]}, 'quadros': [],
             'fontes_que_faltam': [{'fonte_ps': PS, 'situacao': 'ausente', 'camadas': 2}]}
    itens = te.faltam(lido_, {})
    assert len(itens) == 1 and itens[0]['detalhe'] == PS
    lido_['fontes_que_faltam'] = []
    assert [i['detalhe'] for i in te.faltam(lido_, {})] == [te.descricao_da_fase('fontes')]
