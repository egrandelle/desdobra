# -*- coding: utf-8 -*-
"""Cadeia por formato (M7b, A2 e A3): a derivacao, o render.json, o contrato, a trava do derivado, o portao e a
aprovacao leem a impressao do formato (desdobra.derivacao.impressao) no lugar do sha do briefing inteiro, e a
rederivacao seletiva guarda os formatos que nao mudaram no inventario e em derivacao/devolucoes.json.

Job sintetico de verdade (PSD e fonte gerados na hora, test_derivacao_apoio.psd_derivacao) com quatro formatos:
  - perto (f1): o texto de apoio esta nele;
  - mesma e dobro (f2 e f3): o DA apagou o texto de apoio na familia de cada um (caminho transform);
  - alto: troca forte de orientacao, sem familia, devolvido ao DA (fica em devolucoes.json).
Pronto do A2: depois de mudar a funcao da camada que so aparece em f1, o portao aceita o render e a aprovacao de f2 e
f3 e derruba so f1, com o campo que mudou. O render e o aprovar partem do console simulado (fixture pessoa) e o
encoder e o de teste (o master como arquivo final), como em test_entrega_job.py.
"""
import json
import shutil
import sys
from argparse import Namespace
from pathlib import Path

import pytest

import test_derivacao_apoio as ap
import test_fontes_apoio as fap
import test_render_apoio as rap
from desdobra import arquivos, contratos, entrega, humano
from desdobra.briefing import modelo as mb
from desdobra.derivacao import nucleo as nd
from desdobra.entrega import aprovacao, codificar, portao
from desdobra.job import nucleo
from desdobra.render import execucao

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')

ROT0 = {'graus': 0, 'sentido': None}
FORMATOS = [ap.formato('perto', 400, 240, rotacao=ROT0), ap.formato('mesma', 640, 320, rotacao=ROT0),
            ap.formato('dobro', 960, 480, rotacao=ROT0), ap.formato('alto', 160, 640, rotacao=ROT0)]
RENDERIZADOS = ['perto', 'mesma', 'dobro']
CONF = {'origem': 'da', 'meio': 'tela', 'em': '2026-11-06T10:00:00'}


def _ids(job):
    laudo = contratos.ler(job / mb.ARQUIVO_LAUDO, 'laudo/1')
    return {c['nome']: c['identidade']['layer_id'] for c in laudo['camadas']}


def _familia(fid, edicoes=()):
    return {'familia': 'familia-%s' % fid, 'formatos': [fid], 'versao': None, 'edicoes': list(edicoes),
            'confirmada': True, 'confirmacao': dict(CONF)}


def _mexer_briefing(job, mexer):
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    mexer(b)
    contratos.gravar(job / mb.ARQUIVO, b, 'briefing/1')


def _funcao(job, nome, funcao):
    lid = _ids(job)[nome]
    _mexer_briefing(job, lambda b: next(x for x in b['funcoes'] if x['layer_id'] == lid).update(
        funcao=ap.decisao(funcao)))


def _encoder_de_teste(pasta, formato):
    dados = (Path(pasta) / 'render' / formato / 'master.png').read_bytes()
    return codificar.ArquivoFinal(dados=dados, extensao='png', parametros={'tipo': 'png', 'qualidade': 90})


def _shas(job, *rels):
    return {r: arquivos.sha256_arquivo(job / r) for r in rels}


@pytest.fixture(scope='module')
def job_derivado(tmp_path_factory):
    base = tmp_path_factory.mktemp('cadeia')
    fontes = base / 'origem-fontes'
    fap.gravar(fontes, 'inventada.ttf', fap.fonte(ps=rap.FONTE))
    job = base / 'job'
    nucleo.criar(job, ap.psd_derivacao(base / 'origem' / 'kv.psd'), 'c', fontes=[fontes])
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    laudo = contratos.ler(job / mb.ARQUIVO_LAUDO, 'laudo/1')
    b, ids = ap.briefing_do_job(laudo, FORMATOS)
    apagar = [{'elemento': 'el%d' % ids['texto-apoio'], 'acao': 'apagar'}]
    b['composicoes'] = [_familia('perto'), _familia('mesma', apagar), _familia('dobro', apagar)]
    arq = base / 'fixture-cadeia.json'
    arq.write_text(json.dumps(b), encoding='utf-8')
    mb.importar_teste(job, arq)
    # o briefing do DA so chega com a tela: aqui a origem e trocada a mao, antes de derivar e renderizar
    _mexer_briefing(job, lambda b: b['cabecalho'].update(origem='da', meio='terminal'))
    nd.derivar(job)
    return job


@pytest.fixture(scope='module')
def job_aprovado(job_derivado, tmp_path_factory):
    job = tmp_path_factory.mktemp('cadeia-aprovado') / 'job'
    shutil.copytree(job_derivado, job)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(humano, 'console_interativo', lambda: (True, None))
        for fid in RENDERIZADOS:
            execucao.renderizar(job, disparo=humano.exigir('render'), formato=fid)
        mp.setattr(codificar, 'arquivo_final', _encoder_de_teste)
        mp.setattr(humano, 'ler', lambda pergunta: 'sim')
        assert entrega._aprovar(Namespace(job=str(job), formato=list(RENDERIZADOS))).codigo == 0
    return job


@pytest.fixture
def copia(tmp_path):
    def _copia(origem):
        destino = tmp_path / 'job'
        shutil.copytree(origem, destino)
        return destino
    return _copia


def _codigos(conf, fid):
    return [f['codigo'] for f in conf['formatos'][fid]['falhas']]


# ------------------------------------------------------------------ A2: a impressao gravada em cada elo
def test_o_job_tem_os_caminhos_esperados(job_derivado):
    ids = _ids(job_derivado)
    ds = {f['id']: contratos.ler(job_derivado / nd.PASTA / ('%s.json' % f['id']), nd.ESQUEMA) for f in FORMATOS}
    assert {k: d['situacao'] for k, d in ds.items()} == {'perto': 'derivado', 'mesma': 'derivado',
                                                         'dobro': 'derivado', 'alto': 'devolvido'}
    tem_apoio = {k: any(ids['texto-apoio'] in e['layer_ids'] for e in d['elementos']) for k, d in ds.items()}
    assert tem_apoio == {'perto': True, 'mesma': False, 'dobro': False, 'alto': False}


def test_cada_derivacao_grava_a_impressao_do_formato(job_derivado):
    for f in FORMATOS:
        d = contratos.ler(job_derivado / nd.PASTA / ('%s.json' % f['id']), nd.ESQUEMA)
        assert len(d['impressao_formato']) == 64
        assert nd.impressao_de_agora(job_derivado, d) == d['impressao_formato']


def test_render_json_e_contrato_levam_a_impressao(job_aprovado):
    for fid in RENDERIZADOS:
        d = contratos.ler(job_aprovado / nd.PASTA / ('%s.json' % fid), nd.ESQUEMA)
        rel = contratos.ler(job_aprovado / 'render' / fid / 'render.json', execucao.ESQUEMA_RENDER)
        c = contratos.ler(job_aprovado / 'render' / fid / 'contrato.json', 'composicao/1')
        assert rel['derivacao']['impressao_formato'] == d['impressao_formato'] == c['origem']['derivacao_impressao']
        assert 'derivacao_sha256' not in c['origem']
        reg = aprovacao.ler(job_aprovado)['formatos'][fid]
        assert reg['impressao_formato'] == d['impressao_formato'] and 'briefing_sha256' not in reg


def test_mudar_a_funcao_de_camada_so_de_f1_derruba_so_f1(job_aprovado, copia, monkeypatch):
    job = copia(job_aprovado)
    monkeypatch.setattr(codificar, 'arquivo_final', _encoder_de_teste)
    conf = portao.conferir(job)
    assert all(_codigos(conf, fid) == [] for fid in RENDERIZADOS), conf
    rels = ['render/%s/%s' % (fid, a) for fid in ('mesma', 'dobro') for a in ('render.json', 'contrato.json', 'master.png')]
    antes = _shas(job, *rels)
    # mesma ancora e mesma regra: so a funcao resolvida muda, e so perto tem a camada
    _funcao(job, 'texto-apoio', 'informacao_de_evento')
    nd.derivar(job)  # todos os formatos de novo: mesma e dobro saem com outro carimbo e a mesma impressao
    conf = portao.conferir(job)
    assert _codigos(conf, 'mesma') == [] and _codigos(conf, 'dobro') == [], conf
    assert _codigos(conf, 'perto') == ['master_de_outra_impressao', 'aprovacao_caiu'], conf
    caiu = conf['formatos']['perto']['falhas'][1]
    assert caiu['medidas']['campos'] == ['impressao_formato']
    assert _shas(job, *rels) == antes
    # a medida do E1: as aprovacoes dos outros formatos ficam, pelas diferencas do registro
    aprov = aprovacao.ler(job)
    for fid in ('mesma', 'dobro'):
        item = conf['formatos'][fid]
        assert aprovacao.diferencas(aprov['formatos'][fid], aprov['job_id'], item['atual'], item['final']) == []


def test_mudar_a_funcao_sem_derivar_de_novo_tambem_derruba_so_f1(job_aprovado, copia, monkeypatch):
    job = copia(job_aprovado)
    monkeypatch.setattr(codificar, 'arquivo_final', _encoder_de_teste)
    _funcao(job, 'texto-apoio', 'informacao_de_evento')
    conf = portao.conferir(job)
    assert _codigos(conf, 'mesma') == [] and _codigos(conf, 'dobro') == [], conf
    assert _codigos(conf, 'perto') == ['master_de_outra_impressao', 'aprovacao_caiu'], conf


def test_derivacao_mexida_cai_pela_impressao(job_aprovado, copia, monkeypatch):
    job = copia(job_aprovado)
    monkeypatch.setattr(codificar, 'arquivo_final', _encoder_de_teste)
    arq = job / nd.PASTA / 'mesma.json'
    d = arquivos.ler_json(arq)
    d['elementos'][0]['transformacao']['destino'][0] += 1
    arquivos.gravar_json_atomico(arq, d)
    conf = portao.conferir(job)
    assert _codigos(conf, 'mesma') == ['master_de_outra_impressao', 'aprovacao_caiu'], conf
    assert _codigos(conf, 'perto') == [] and _codigos(conf, 'dobro') == [], conf


def test_trava_do_derivado_compara_a_impressao(job_aprovado, copia):
    from desdobra.render import derivado
    job = copia(job_aprovado)
    _funcao(job, 'texto-apoio', 'informacao_de_evento')
    assert derivado.montar(job, 'mesma')[1] == []
    _contrato, bloqueios, _c = derivado.montar(job, 'perto')
    assert [b['codigo'] for b in bloqueios] == ['derivacao_desatualizada']


# ------------------------------------------------------------------ C2: a quebra de linha da familia
def _quebra_de_perto(job, manter=(), inseridas=(2,)):
    """A quebra de linha que o DA pos no texto de apoio ('AB ab') na familia de perto: no espaco da posicao 2."""
    return {'layer_id': _ids(job)['texto-apoio'], 'familia': 'familia-perto', 'formatos': ['perto'],
            'quebras': ap.decisao(list(manter)), 'inseridas': list(inseridas), 'origem': 'da', 'aprovada': True}


def test_mudar_a_quebra_da_familia_derruba_so_os_formatos_dela(job_aprovado, copia, monkeypatch):
    """M7b, C2: a quebra de linha que o DA poe na familia de perto muda a derivacao de perto (a caixa medida do texto
    no Chromium, quebras_origem 'da') e derruba so a aprovacao dela, pela impressao do formato."""
    from desdobra.render import derivado
    from desdobra.render import texto as rt
    job = copia(job_aprovado)
    monkeypatch.setattr(codificar, 'arquivo_final', _encoder_de_teste)
    lid = _ids(job)['texto-apoio']
    rels = ['render/%s/%s' % (fid, a) for fid in ('mesma', 'dobro')
            for a in ('render.json', 'contrato.json', 'master.png')]
    antes = _shas(job, *rels)
    _mexer_briefing(job, lambda b: b.__setitem__('quebras_por_familia', [_quebra_de_perto(job)]))
    nd.derivar(job)
    d = contratos.ler(job / nd.PASTA / 'perto.json', nd.ESQUEMA)
    assert d['situacao'] == 'derivado', d['devolucao']
    x = next(e for e in d['elementos'] if lid in e['layer_ids'])
    assert x['quebras_origem'] == 'da' and x['origem_geometria'] == 'da'
    assert x['quebras']['familia'][0]['inseridas'] == [2]
    conf = portao.conferir(job)
    assert _codigos(conf, 'mesma') == [] and _codigos(conf, 'dobro') == [], conf
    assert _codigos(conf, 'perto') == ['master_de_outra_impressao', 'aprovacao_caiu'], conf
    assert _shas(job, *rels) == antes
    aprov = aprovacao.ler(job)
    for fid in ('mesma', 'dobro'):
        item = conf['formatos'][fid]
        assert aprovacao.diferencas(aprov['formatos'][fid], aprov['job_id'], item['atual'], item['final']) == []
    # o contrato de perto insere a quebra no espaco, e o render desenha a tinta dentro da caixa medida
    contrato, bloqueios, _c = derivado.montar(job, 'perto')
    assert bloqueios == [], bloqueios
    e = next(x for x in contrato['entradas'] if x['tipo'] == 'texto' and x['layer_id'] == lid)
    assert e['quebras_inseridas'] == [2] and rt.linhas_desenhadas(e) == ['AB', 'ab']
    monkeypatch.setattr(humano, 'console_interativo', lambda: (True, None))
    execucao.renderizar(job, disparo=humano.exigir('render'), formato='perto')


def _como_aprovacao_1(job):
    """briefing/aprovacao.json como o motor de antes gravava (aprovacao/1, com o sha do briefing inteiro)."""
    arq = job / aprovacao.ARQUIVO
    d = arquivos.ler_json(arq)
    for reg in d['formatos'].values():
        reg.pop('impressao_formato')
        reg['briefing_sha256'] = arquivos.sha256_arquivo(job / mb.ARQUIVO)
        reg['registro_sha256'] = aprovacao.selo(reg)
    d['esquema'] = aprovacao.ESQUEMA_ANTIGO
    contratos.validar(d, aprovacao.ESQUEMA_ANTIGO)
    arquivos.gravar_json_atomico(arq, d)


def test_aprovacao_1_conta_como_aprovacao_caida_com_motivo_claro(job_aprovado, copia, monkeypatch):
    job = copia(job_aprovado)
    monkeypatch.setattr(codificar, 'arquivo_final', _encoder_de_teste)
    _como_aprovacao_1(job)
    conf = portao.conferir(job)
    for fid in RENDERIZADOS:
        assert _codigos(conf, fid) == ['aprovacao_antiga'], conf
    desc = conf['formatos']['perto']['falhas'][0]['descricao']
    assert 'aprove' in desc and '—' not in desc and '–' not in desc


def test_gravar_por_cima_da_aprovacao_1_deixa_so_os_registros_novos(job_aprovado, copia):
    job = copia(job_aprovado)
    _como_aprovacao_1(job)
    velha = aprovacao.ler(job)
    novo = dict(velha['formatos']['perto'])
    novo.pop('briefing_sha256')
    novo['impressao_formato'] = 'a' * 64
    novo['registro_sha256'] = aprovacao.selo(novo)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(humano, 'console_interativo', lambda: (True, None))
        dados = aprovacao.gravar(job, [novo], velha['job_id'], disparo=humano.exigir('aprovar'))
    assert dados['esquema'] == aprovacao.ESQUEMA and sorted(dados['formatos']) == ['perto']


# ------------------------------------------------------------------ A3: rederivacao seletiva
def _devolucoes(job):
    return contratos.ler(job / nd.ARQUIVO_DEVOLUCOES, nd.ESQUEMA_DEVOLUCOES)


def test_derivar_so_f1_mantem_os_outros_no_inventario_e_nas_devolucoes(job_derivado, copia):
    job = copia(job_derivado)
    dev = _devolucoes(job)
    assert dev['inventario']['formatos'] == 3 and [x['formato'] for x in dev['devolucoes']] == ['alto']
    outros = ['%s/%s.json' % (nd.PASTA.as_posix(), f) for f in ('mesma', 'dobro', 'alto')]
    antes = _shas(job, *outros)
    _funcao(job, 'texto-apoio', 'informacao_de_evento')
    r = nd.derivar(job, so=['perto'])
    assert r['inventario']['formatos'] == 3 and r['inventario']['iguais_entre_formatos']
    dev = _devolucoes(job)
    assert dev['inventario'] == r['inventario']
    assert [x['formato'] for x in dev['devolucoes']] == ['alto']
    assert _shas(job, *outros) == antes


def test_apagar_em_f1_e_derivar_so_f1_refaz_o_inventario_com_todos(job_derivado, copia):
    """O caso da critica do plano: o apagado pelo DA conta como presente no inventario (nº 169), e a derivacao so de f1
    confere o inventario contra os formatos guardados (f2 e f3, sem o texto de apoio desde antes), e nao so contra
    ela mesma. O campo de f1 sai igual ao de derivacao/devolucoes.json."""
    job = copia(job_derivado)
    el = 'el%d' % _ids(job)['texto-apoio']
    _mexer_briefing(job, lambda b: b['composicoes'][0]['edicoes'].append({'elemento': el, 'acao': 'apagar'}))
    r = nd.derivar(job, so=['perto'])
    d = contratos.ler(job / nd.PASTA / 'perto.json', nd.ESQUEMA)
    assert el not in {e['id'] for e in d['elementos']}
    assert r['inventario']['formatos'] == 3 and r['inventario']['iguais_entre_formatos']
    assert d['inventario_entre_formatos'] == 'igual' and _devolucoes(job)['inventario'] == r['inventario']


def test_inventario_de_f1_contra_os_guardados_quando_o_conjunto_muda(job_derivado, copia, monkeypatch):
    """Quando o conjunto de elementos de f1 deixa de ser o dos guardados, o campo de f1 diz diferente: a conta e com
    todos os formatos que ficam, e nao so com os derivados agora."""
    job = copia(job_derivado)
    original = nd._inventario

    def sem_o_ultimo_de_perto(kv, resultados):
        if set(resultados) == {'perto'}:
            # a derivacao em memoria so de f1 nunca ve os outros: o inventario dela e de um formato so
            return original(kv, resultados)
        mexidos = dict(resultados)
        p = mexidos.get('perto')
        if p is not None:
            mexidos['perto'] = dict(p, elementos=p['elementos'][:-1])
        return original(kv, mexidos)
    monkeypatch.setattr(nd, '_inventario', sem_o_ultimo_de_perto)
    r = nd.derivar(job, so=['perto'])
    assert r['inventario']['formatos'] == 3 and not r['inventario']['iguais_entre_formatos']
    d = contratos.ler(job / nd.PASTA / 'perto.json', nd.ESQUEMA)
    assert d['inventario_entre_formatos'] == 'diferente'


def test_derivacao_guardada_que_nao_confere_mais_sai_do_inventario(job_derivado, copia):
    """A camada que sai da peca muda todo formato: f2 e f3 gravados antes nao conferem mais com o briefing e nao entram
    na conta (nunca derivacao velha calada no inventario)."""
    job = copia(job_derivado)
    _funcao(job, 'texto-apoio', mb.FUNCAO_FORA)
    r = nd.derivar(job, so=['perto'])
    assert r['inventario']['formatos'] == 1
    assert _devolucoes(job)['devolucoes'] == []


# ------------------------------------------------------------------ A6: o que muda na familia sem mudar o formato
def _rels_de(fid):
    arqs = ('render.json', 'contrato.json', 'master.png')
    return ['derivacao/%s.json' % fid] + ['render/%s/%s' % (fid, a) for a in arqs]


def _salvar_seletivo(job, mexer):
    """O salvar seletivo do A6 (briefing.salvar) sem a tela: os afetados com o briefing novo, o briefing gravado e a
    derivacao so deles. Devolve os afetados."""
    from desdobra.briefing import salvar
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    mexer(b)
    mud = salvar._mudancas(job, b)
    _mexer_briefing(job, mexer)
    nd.derivar(job, so=[f['id'] for f in b['formatos'] if f['id'] in mud])
    return mud


def test_formato_novo_na_familia_nao_derruba_o_irmao(job_aprovado, copia, monkeypatch):
    """A lista dos formatos da familia so alimenta o formato pela derivacao dele: o irmao novo, que nao muda a
    derivacao de mesma, nao derruba o render nem a aprovacao dela."""
    from desdobra.render import derivado
    job = copia(job_aprovado)
    monkeypatch.setattr(codificar, 'arquivo_final', _encoder_de_teste)
    shas = _shas(job, *_rels_de('mesma'))

    def com_irmao(b):
        b['formatos'].append(ap.formato('mesma2', 1280, 640, rotacao=ROT0))
        next(c for c in b['composicoes'] if c['familia'] == 'familia-mesma')['formatos'].append('mesma2')
    mud = _salvar_seletivo(job, com_irmao)
    assert sorted(mud) == ['mesma2'], mud
    assert _codigos(portao.conferir(job, ['mesma']), 'mesma') == []
    assert _shas(job, *_rels_de('mesma')) == shas
    assert derivado.montar(job, 'mesma')[1] == []


def _grupo_da_tela(job, fid, conhecidas=None):
    from desdobra.tela import estado
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    laudo = contratos.ler(job / mb.ARQUIVO_LAUDO, 'laudo/1')
    ds = {f['id']: contratos.ler(job / nd.PASTA / ('%s.json' % f['id']), nd.ESQUEMA) for f in b['formatos']
          if (job / nd.PASTA / ('%s.json' % f['id'])).is_file()}
    return next(g['id'] for o in estado.abas(laudo, b, ds, conhecidas=conhecidas) for g in o['grupos']
                for c in g['composicoes'] for x in c['formatos'] if x['id'] == fid)


def test_familia_renumerada_na_tela_nao_derruba_os_formatos_dela(job_aprovado, copia, monkeypatch):
    """Pela posicao do grupo na tela (tela.estado.abas sem os ids que o job ja conhece), o formato mais largo que
    entra no passo 1 empurraria o grupo de mesma de horizontal-1 para horizontal-2. Mesmo confirmada de novo com a
    mesma versao e as mesmas edicoes, so com o id novo, mesma fica: o render, a aprovacao e a trava do derivado."""
    from desdobra.render import derivado
    job = copia(job_aprovado)
    monkeypatch.setattr(codificar, 'arquivo_final', _encoder_de_teste)
    gid_antes = _grupo_da_tela(job, 'mesma')
    _mexer_briefing(job, lambda b: b['formatos'].append(ap.formato('largo', 1600, 320, rotacao=ROT0)))
    nd.derivar(job, so=['largo'])
    gid = _grupo_da_tela(job, 'mesma')
    assert gid != gid_antes
    shas = _shas(job, *_rels_de('mesma'))

    def renumerar(b):
        next(c for c in b['composicoes'] if c['familia'] == 'familia-mesma')['familia'] = gid
    assert _salvar_seletivo(job, renumerar) == {}
    assert _codigos(portao.conferir(job, ['mesma']), 'mesma') == []
    assert _shas(job, *_rels_de('mesma')) == shas
    assert derivado.montar(job, 'mesma')[1] == []


def test_formato_mais_largo_nao_muda_o_id_da_familia_de_mesma(job_aprovado, copia, monkeypatch):
    """Com os ids que o job ja conhece (tela.estado.familias_conhecidas: o briefing gravado e o rascunho da tela), o
    grupo de mesma fica com o id de antes quando o formato mais largo entra no passo 1, e o salvar que so traz a
    familia nova de largo nao derruba o render, a aprovacao nem a trava do derivado de mesma."""
    from desdobra.render import derivado
    from desdobra.tela import estado
    job = copia(job_aprovado)
    monkeypatch.setattr(codificar, 'arquivo_final', _encoder_de_teste)
    gid_antes = _grupo_da_tela(job, 'mesma', estado.familias_conhecidas(job))
    _mexer_briefing(job, lambda b: b['formatos'].append(ap.formato('largo', 1600, 320, rotacao=ROT0)))
    nd.derivar(job, so=['largo'])
    conhecidas = estado.familias_conhecidas(job)
    gid, gid_largo = _grupo_da_tela(job, 'mesma', conhecidas), _grupo_da_tela(job, 'largo', conhecidas)
    assert gid == gid_antes and gid_largo not in conhecidas
    shas = _shas(job, *_rels_de('mesma'))

    def com_largo(b):
        b['composicoes'].append({'familia': gid_largo, 'formatos': ['largo'], 'versao': None, 'edicoes': [],
                                 'confirmada': True, 'confirmacao': dict(CONF)})
    assert 'mesma' not in _salvar_seletivo(job, com_largo)
    assert _codigos(portao.conferir(job, ['mesma']), 'mesma') == []
    assert _shas(job, *_rels_de('mesma')) == shas
    assert derivado.montar(job, 'mesma')[1] == []
