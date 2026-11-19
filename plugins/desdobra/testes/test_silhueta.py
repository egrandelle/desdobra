# -*- coding: utf-8 -*-
"""A silhueta das bases e a conferencia sem ponto cego (decisao 199, 3; etapa E3 do desenho da familia).

O preparo (desdobra.ds.silhueta) grava a grade do alfa de cada base que sangra, decodificado so no processo filho
isolado; a derivacao le so o JSON (desdobra.derivacao.silhueta) e a galeria confere o par conteudo x base que ja se
sobrepunha na mestre pela tinta da base (relacao_quebrada). O KV e o sintetico da diagonal (sinteticos.kv_diagonal),
com a geometria do caso de 18/11; nenhum job real.
"""
import copy
import json
import math
import shutil
from pathlib import Path

import numpy as np
import pytest

import familia_geometria as G
import test_derivacao_apoio as ap
from desdobra import arquivos, contratos, limites, plataforma
from desdobra.derivacao import familia as F
from desdobra.derivacao import galeria as mg
from desdobra.derivacao import nucleo as nd
from desdobra.derivacao import silhueta as dsil
from desdobra.ds import silhueta as mod_silhueta
from desdobra.ds import silhueta_filho
from sinteticos import kv_diagonal as KD

PLAT = plataforma.obter()
precisa_isolador = pytest.mark.skipif(PLAT.nome in ('sem-suporte', 'mac'), reason='sem isolador neste sistema')
TOL = 1.0


# ------------------------------------------------------------------ a grade (funcao pura)
def test_dimensoes_da_grade_no_lado_longo_sem_passar_dos_pixels():
    assert mod_silhueta.dimensoes_da_grade(1180, 2000, 256) == (152, 256)  # o azul do caso: 7,8 px por celula
    assert mod_silhueta.dimensoes_da_grade(2000, 1180, 256) == (256, 152)
    assert mod_silhueta.dimensoes_da_grade(10, 5, 256) == (10, 5)  # nunca mais celulas que pixels
    assert mod_silhueta.dimensoes_da_grade(1, 1, 256) == (1, 1)
    assert mod_silhueta.dimensoes_da_grade(1000, 3, 256) == (256, 1)


def test_celula_com_tinta_quando_metade_chega_ao_limiar():
    limiar = int(limites.valor('ds.sujeito_limiar_alfa'))
    alfa = np.zeros((2, 4), np.uint8)
    alfa[:, 0:2] = 255  # a celula da esquerda cheia
    alfa[0, 2] = 255  # a do meio (colunas 2 e 3 de uma grade de 2) com 1 de 4: sem tinta
    g = mod_silhueta.grade_do_alfa(alfa, 2, limiar)
    assert g == {'colunas': 2, 'linhas': 1, 'celulas': ['10']}
    alfa[1, 3] = 255  # 2 de 4: metade, com tinta
    assert mod_silhueta.grade_do_alfa(alfa, 2, limiar)['celulas'] == ['11']
    # o limiar: abaixo dele nao e tinta
    meio = np.full((1, 1), limiar - 1, np.uint8)
    assert mod_silhueta.grade_do_alfa(meio, 4, limiar)['celulas'] == ['0']
    assert mod_silhueta.grade_do_alfa(meio + 1, 4, limiar)['celulas'] == ['1']


# ------------------------------------------------------------------ o preparo no job da diagonal
@pytest.fixture(scope='module')
def diag(tmp_path_factory):
    if PLAT.nome in ('sem-suporte', 'mac'):
        pytest.skip('sem isolador neste sistema')
    d = KD.criar_job(tmp_path_factory.mktemp('silhueta'))
    d['ctx'] = nd.preparar(d['job'])
    d['r'] = nd.derivar_em_memoria(d['ctx'])
    d['kv'] = d['r']['kv']
    d['formatos'] = {f['id']: f for f in d['ctx']['briefing']['formatos']}
    d['el'] = {papel: next(e['id'] for e in d['kv']['elementos'] if lid in e['layer_ids'])
               for papel, lid in d['ids'].items()}
    return d


def _arquivos(job):
    return {p.name: p.read_bytes() for p in sorted((Path(job) / mod_silhueta.PASTA).glob('*.json'))}


def _lado(p, pontos):
    """O ponto dentro do poligono (o mesmo teste de familia_geometria)."""
    x, y = p
    c = False
    for i in range(len(pontos)):
        (x0, y0), (x1, y1) = pontos[i - 1], pontos[i]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            c = not c
    return c


def test_preparo_grava_a_silhueta_das_bases_que_sangram(diag):
    lidas = {d['camadas'][0]['layer_id']: d for d in
             (contratos.ler(p, 'silhueta/1') for p in sorted((diag['job'] / mod_silhueta.PASTA).glob('*.json')))}
    ids = diag['ids']
    # o fundo, o azul e a faixa verde encostam na borda; o titulo e o texto sao texto, e a assinatura fica solta
    assert set(lidas) == {ids['fundo'], ids['azul'], ids['verde']}
    azul = lidas[ids['azul']]
    assert azul['camadas'] == [{'layer_id': ids['azul'], 'caixa_asset': KD.AZUL_ASSET}]  # o asset passa do canvas
    assert azul['dims'] == [1180, 2000] and (azul['grade']['colunas'], azul['grade']['linhas']) == (152, 256)
    assert azul['limiar']['limite_id'] == 'ds.sujeito_limiar_alfa'
    assert azul['celulas']['limite_id'] == 'ds.silhueta_celulas'
    assert azul['arquivo_sha256'] == diag['ctx']['laudo']['origem']['sha256']
    assert all(set(linha) == {'1'} for linha in lidas[ids['verde']]['grade']['celulas'])
    # a grade do azul e a do poligono do caso: a celula que nao cruza a diagonal (os quatro cantos do mesmo lado) bate
    a, n, m = KD.AZUL_ASSET, azul['grade']['colunas'], azul['grade']['linhas']
    xs = [a[0] + (i * (a[2] - a[0])) // n for i in range(n + 1)]  # as bordas inteiras da celula, como no preparo
    ys = [a[1] + (j * (a[3] - a[1])) // m for j in range(m + 1)]
    inteiras, bordas = 0, 0
    for j in range(m):
        for i in range(n):
            cantos = {_lado((x, y), G.AZUL_PONTOS) for x in (xs[i] + 0.01, xs[i + 1] - 0.01)
                      for y in (ys[j] + 0.01, ys[j + 1] - 0.01)}
            if len(cantos) == 1:
                inteiras += 1
                assert azul['grade']['celulas'][j][i] == ('1' if cantos.pop() else '0'), (i, j)
            else:
                bordas += 1
    assert inteiras > 0.9 * n * m and bordas < 2 * (n + m)  # so a diagonal cruza celulas


def test_preparo_e_deterministico(diag):
    antes = _arquivos(diag['job'])
    estrutura = arquivos.ler_json(diag['job'] / 'laudo' / 'bruto' / diag['ctx']['laudo']['origem']['sha256'] /
                                  'estrutura.json')
    resumo = mod_silhueta.preparar(diag['job'], estrutura)
    assert resumo == {'pedidas': 3, 'gravadas': 3, 'sem_silhueta': [], 'motivo': None}
    assert _arquivos(diag['job']) == antes
    assert not (diag['job'] / 'ds' / '.trabalho-silhueta').exists()


def test_contexto_carrega_as_silhuetas_e_ignora_as_de_outro_kv(diag, tmp_path):
    ctx, ids = diag['ctx'], diag['ids']
    assert set(ctx['silhuetas']) == {ids['fundo'], ids['azul'], ids['verde']}
    assert ctx['silhuetas'][ids['azul']]['caixa_asset'] == [float(v) for v in KD.AZUL_ASSET]
    # a silhueta gravada para outro KV (ou fora do contrato) fica de fora: a camada cai na caixa
    copia = tmp_path / 'outro'
    shutil.copytree(diag['job'] / mod_silhueta.PASTA, copia / mod_silhueta.PASTA)
    for p in (copia / mod_silhueta.PASTA).glob('*.json'):
        d = json.loads(p.read_text(encoding='utf-8'))
        if d['camadas'][0]['layer_id'] == ids['azul']:
            d['arquivo_sha256'] = '0' * 64
            p.write_text(json.dumps(d), encoding='utf-8')
        elif d['camadas'][0]['layer_id'] == ids['verde']:
            p.write_text('{', encoding='utf-8')
    assert set(dsil.carregar(copia, ctx['laudo'])) == {ids['fundo']}
    # o job lido antes desta versao, sem a pasta: nenhuma silhueta
    assert dsil.carregar(tmp_path / 'sem-pasta', ctx['laudo']) == {}


# ------------------------------------------------------------------ a galeria sem ponto cego
def _mover(elementos, eid, dx, dy):
    els = copy.deepcopy(elementos)
    for e in els:
        if e['id'] == eid:
            e['caixa'] = [e['caixa'][0] + dx, e['caixa'][1] + dy, e['caixa'][2] + dx, e['caixa'][3] + dy]
    return els


def test_relacao_do_kv_medida_pela_silhueta(diag):
    cf = mg._contexto(diag['ctx'], diag['kv'], diag['formatos']['f1080x1920'])
    por_id = {e['id']: e for e in diag['kv']['elementos']}
    mestre, _tinta, _de, sem = mg._tinta_da_base(cf, por_id[diag['el']['azul']])
    assert not sem
    # a assinatura no branco: livre da tinta do azul, mesmo com a caixa do azul cobrindo a dela; o texto dentro
    rel = dsil.relacao(por_id[diag['el']['assinatura']]['caixa'], mestre, TOL)
    assert rel['tipo'] == dsil.LIVRE and 0.0 < rel['folga'] <= G.distancia_a_reta(G.ASSINATURA[:2], G.P1, G.INCLINACAO)
    for papel in ('titulo', 'texto'):
        assert dsil.relacao(por_id[diag['el'][papel]]['caixa'], mestre, TOL) == {'tipo': dsil.DENTRO}


def test_galeria_confere_o_par_que_ja_se_sobrepunha_na_mestre(diag):
    ctx, kv, el = diag['ctx'], diag['kv'], diag['el']
    for fid in ('f1080x1920', 'f300x600'):
        f = diag['formatos'][fid]
        assert mg._contexto(ctx, kv, f)['copia_do_kv']
        elementos = diag['r']['formatos'][fid]['elementos']
        res = mg.conferir(ctx, kv, f, elementos)
        assert [x for x in res['falhas_obrigatorias'] if x['codigo'] == 'relacao_quebrada'] == []
        s = f['largura'] / 1080.0
        # a assinatura sobe 40 px (no 1080): a caixa do azul ja cobria a dela na mestre, e hoje o par era pulado
        res = mg.conferir(ctx, kv, f, _mover(elementos, el['assinatura'], 0.0, -40.0 * s))
        quebra = [x for x in res['falhas_obrigatorias'] if x['codigo'] == 'relacao_quebrada']
        assert [(x['texto'], x['elementos'], x['medidas']['relacao']) for x in quebra] == [
            ('A assinatura passa por cima do grafismo, e no KV ficava fora dele.', [el['assinatura'], el['azul']],
             'livre_da_tinta')]
        assert 0.0 < quebra[0]['medidas']['fracao_sobre_a_forma'] < 1.0
        # o titulo desce para o branco: sai do azul em que estava
        res = mg.conferir(ctx, kv, f, _mover(elementos, el['titulo'], 300.0 * s, 1400.0 * s))
        assert [(x['texto'], x['medidas']['relacao']) for x in res['falhas_obrigatorias']
                if x['codigo'] == 'relacao_quebrada'] == [
            ('O título deixa de ficar inteiro sobre o grafismo, como estava no KV.', 'dentro_da_tinta')]


def test_relacao_que_o_da_desfez_no_palco_e_decisao_dele(diag):
    ctx, kv, el = diag['ctx'], diag['kv'], diag['el']
    f = diag['formatos']['f1080x1920']
    cf = mg.contexto_do_formato(ctx, kv, f)
    elementos = _mover(diag['r']['formatos']['f1080x1920']['elementos'], el['assinatura'], 0.0, -40.0)
    caixas = {e['id']: e['caixa'] for e in elementos}
    falhas, _avisos, _rep = mg.conferir_edicao(cf, caixas, {})
    assert [x['codigo'] for x in falhas] == ['relacao_quebrada']
    ficam, decisoes = mg.decisoes_do_da(cf, falhas, {el['assinatura']})
    assert ficam == [] and [d['texto'] for d in decisoes] == [
        'A assinatura passa por cima do grafismo, e no KV ficava fora dele.']
    # sem a mao do DA (o elemento parado), continua falha
    ficam, decisoes = mg.decisoes_do_da(cf, falhas, {el['titulo']})
    assert [x['codigo'] for x in ficam] == ['relacao_quebrada'] and decisoes == []


def test_variante_da_galeria_reorganiza_sem_a_relacao_do_kv(diag):
    """Na troca de orientacao, a galeria reorganiza o conteudo sobre a cena de proposito (a imagem livre): a relacao
    de fundo do KV so vale no formato que copia o layout dele."""
    f = ap.formato('h1920', 1920, 1080)
    assert not mg._contexto(diag['ctx'], diag['kv'], f)['copia_do_kv']


def test_familia_com_a_grade_do_preparo_fecha_o_caso_de_aceitacao(diag):
    """A grade que o preparo gravou serve a copia da familia (etapa E1): o 300x600 sai igual ao aprovado."""
    sil, ids = diag['ctx']['silhuetas'], diag['ids']
    ref, els, _sem = G.caso_diagonal(silhueta=None)
    silhuetas = {papel: {'grade': sil[ids[papel]]['grade']} for papel in ('fundo', 'azul', 'verde')}
    for e in els:
        if e['id'] in ('azul', 'verde'):
            assert sil[ids[e['id']]]['caixa_asset'] == e['caixa_asset']
    m = F.extrair_modelo(ref, els, silhuetas=silhuetas)
    assert not [a for a in m['avisos'] if a['codigo'] == 'forma_conferida_pela_caixa']
    livre = next(r for r in m['relacoes'] if r['id'] == 'livre_da_tinta:assinatura:azul')
    lay = F.ajustar_minimo(m, F.transferir(m, G.membro('f300x600', 300, 600)))
    a = lay['caixas']['assinatura']
    assert (a[2] - a[0]) / lay['W'] == pytest.approx(0.463, abs=0.01)
    assert lay['situacao'] == 'igual' and lay['ajustes'] == [] and F.relacoes_furadas(m, lay) == []
    rel = {r['id']: r for r in F.relacoes(m, lay)}['livre_da_tinta:assinatura:azul']
    assert rel['ok'] and rel['medida'] >= livre['folga'] * lay['s'] - 1e-6


# ------------------------------------------------------------------ sem silhueta: a caixa, com o aviso
def test_sem_silhueta_a_base_e_conferida_pela_caixa_com_aviso():
    """Job lido antes desta versao (ou base sem asset): a tinta e a caixa, e a tela diz que a forma foi conferida
    assim. KV vertical 200 x 400 com uma faixa que sangra no topo e o titulo dentro dela."""
    cams = [ap.camada(1, 'pixel', [0, 0, 200, 400]), ap.camada(5, 'pixel', [0, 0, 200, 140]),
            ap.camada(10, 'texto', [20, 30, 180, 110], corpo=36), ap.camada(30, 'smart_embutido', [60, 300, 140, 350])]
    funcoes = {1: 'fundo', 5: 'grafismo', 10: 'titulo', 30: 'logo_principal'}
    b = ap.briefing(funcoes=funcoes, formatos=[ap.formato('v', 300, 600)])
    ctx = nd.contexto(ap.laudo(200, 400, cams), b)
    assert ctx['silhuetas'] == {}
    r = nd.derivar_em_memoria(ctx, specs={})
    kv, f = r['kv'], b['formatos'][0]
    titulo = next(e['id'] for e in kv['elementos'] if 10 in e['layer_ids'])
    faixa = next(e['id'] for e in kv['elementos'] if 5 in e['layer_ids'])
    elementos = r['formatos']['v']['elementos']
    res = mg.conferir(ctx, kv, f, elementos)
    assert [x for x in res['falhas_obrigatorias'] if x['codigo'] == 'relacao_quebrada'] == []
    assert [(a['codigo'], a['texto'], a['elementos']) for a in res['avisos'] if a['codigo'] == dsil.AVISO_CAIXA] == [
        ('forma_conferida_pela_caixa', 'O desdobra conferiu o grafismo pela caixa, porque não tem o desenho dele.',
         [faixa])]
    # o titulo sai da faixa: a relacao quebra, medida pela caixa
    res = mg.conferir(ctx, kv, f, _mover(elementos, titulo, 0.0, 250.0))
    assert [x['texto'] for x in res['falhas_obrigatorias'] if x['codigo'] == 'relacao_quebrada'] == [
        'O título deixa de ficar inteiro sobre o grafismo, como estava no KV.']


def test_partes_sem_silhueta_usam_a_caixa_da_tinta(diag):
    ctx = nd.contexto(diag['ctx']['laudo'], diag['ctx']['briefing'], ds=diag['ctx']['ds'], silhuetas={})
    azul = next(e for e in diag['kv']['elementos'] if e['id'] == diag['el']['azul'])
    partes = dsil.partes_do_elemento(ctx, azul, diag['kv']['canvas_doc'])
    assert partes == [([float(v) for v in KD.AZUL_ASSET], None)]  # a caixa da tinta, que passa do canvas
    _tinta, sem = dsil.tinta_do_elemento(partes, azul['caixa'], 1080.0, 1920.0)
    assert sem


# ------------------------------------------------------------------ o isolamento do preparo
class _PlataformaFalsa:
    """Plataforma que nao roda nada: grava na pasta de saida o que o teste pede."""
    nome = 'falsa'

    def __init__(self, situacao='ok', codigo=0, auditoria=None):
        self.situacao, self.codigo, self.auditoria = situacao, codigo, auditoria
        self.comandos = []

    def interpretador(self):
        return Path('python')

    def executar_isolado(self, comando, orcamento_bytes, tempo_s, pasta_trabalho, *, ambiente=None, entrada=b''):
        self.comandos.append(list(comando))
        if self.auditoria is not None:
            (Path(comando[7]) / silhueta_filho.ARQUIVO_AUDITORIA).write_text(json.dumps(self.auditoria),
                                                                            encoding='utf-8')
        return plataforma.ResultadoFilho(situacao=self.situacao, codigo=self.codigo, pico_bytes=None,
                                         stdout_bytes=b'', stderr_resumo='')


def _estrutura(diag):
    return arquivos.ler_json(diag['job'] / 'laudo' / 'bruto' / diag['ctx']['laudo']['origem']['sha256'] /
                             'estrutura.json')


def test_alarme_de_auditoria_no_filho_para_o_preparo(diag, tmp_path):
    job = tmp_path / 'copia'
    shutil.copytree(diag['job'] / 'laudo' / 'assets', job / 'laudo' / 'assets')
    plat = _PlataformaFalsa(situacao='ok', codigo=int(silhueta_filho.CodigoFilho.AUDITORIA),
                            auditoria={'instalado': True, 'bloqueios': 1, 'recusa': 'auditoria'})
    with pytest.raises(mod_silhueta.ErroAuditoriaSilhueta):
        mod_silhueta.preparar(job, _estrutura(diag), plat=plat)
    assert not (job / mod_silhueta.PASTA).exists()
    # o comando e o do filho isolado, com o orcamento do registro de limites
    cmd = plat.comandos[0]
    assert cmd[1:5] == ['-I', '-B', '-m', mod_silhueta.MODULO_FILHO] and cmd[8] == '--orcamento-bytes'


def test_sem_isolador_ou_sem_asset_a_base_fica_sem_silhueta(diag, tmp_path):
    job = tmp_path / 'copia'
    shutil.copytree(diag['job'] / 'laudo' / 'assets', job / 'laudo' / 'assets')
    resumo = mod_silhueta.preparar(job, _estrutura(diag), plat=_PlataformaFalsa(situacao='recusado', codigo=None))
    assert resumo['gravadas'] == 0 and len(resumo['sem_silhueta']) == 3
    assert resumo['motivo'] == mod_silhueta.MOTIVO_FILHO['plataforma']
    assert not (job / mod_silhueta.PASTA).exists()
    # o asset que sumiu do laudo nem vai ao filho
    shutil.rmtree(job / 'laudo' / 'assets')
    plat = _PlataformaFalsa()
    resumo = mod_silhueta.preparar(job, _estrutura(diag), plat=plat)
    assert plat.comandos == [] and resumo['gravadas'] == 0
    assert {x['motivo'] for x in resumo['sem_silhueta']} == {'asset ausente no laudo'}


def test_o_preparo_nunca_abre_psd_smart_object_nem_linkado(diag, monkeypatch):
    """O processo principal so le o JSON do filho; o filho le so os PNG do laudo (o gancho de auditoria barra o
    resto). Nenhum dos dois importa o psd-tools."""
    import psd_tools
    from psd_tools.api import smart_object

    def proibido(*_a, **_k):
        raise AssertionError('o preparo da silhueta abriu PSD ou smart object')
    monkeypatch.setattr(psd_tools.PSDImage, 'open', proibido)
    monkeypatch.setattr(smart_object.SmartObject, 'open', proibido)
    resumo = mod_silhueta.preparar(diag['job'], _estrutura(diag))
    assert resumo['gravadas'] == 3
    for mod in (mod_silhueta, silhueta_filho, dsil):
        fonte = Path(mod.__file__).read_text(encoding='utf-8')
        assert 'psd_tools' not in fonte and 'smart_object' not in fonte.replace('smart object', '')
    assert math.isfinite(limites.valor('ds.silhueta_celulas'))


# ------------------------------------------------------------------ revisao da 0.10.0: o job preparado antes
@pytest.fixture(scope='module')
def diag_faixa(tmp_path_factory):
    """O KV da diagonal com o 1080x1920 e a ponta larga da faixa (1080x1600): sem silhueta, o azul vira fundo pela
    caixa, e a copia punha a assinatura 60 px dentro dele."""
    if PLAT.nome in ('sem-suporte', 'mac'):
        pytest.skip('sem isolador neste sistema')
    return KD.criar_job(tmp_path_factory.mktemp('silhueta-faixa'),
                        [('f1080x1920', 1080, 1920), ('f1080x1600', 1080, 1600)])


def test_job_de_antes_da_0100_refaz_a_fase_ds_com_as_silhuetas(diag_faixa):
    """Revisao da 0.10.0: o job preparado na 0.9.6 tinha a fase ds valida pelo hash das entradas e nunca gravava
    ds/silhuetas. O preparo entra como externa da fase: o job de antes fica desatualizado uma vez, e o job proxima
    refaz o design system com as silhuetas."""
    from desdobra.job import nucleo
    job = diag_faixa['job']
    antes = _arquivos(job)
    assert antes
    estado = nucleo.ler_estado(job)
    assert 'externa:preparo-silhueta' in estado['fases']['ds']['hash_entradas']
    # o job de antes: sem a externa no registro e sem a pasta das silhuetas
    del estado['fases']['ds']['hash_entradas']['externa:preparo-silhueta']
    nucleo.gravar_estado(job, estado)
    shutil.rmtree(job / mod_silhueta.PASTA)
    assert 'ds' in nucleo.fases_invalidas(job)
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    assert nucleo.fases_invalidas(job) == set()
    assert _arquivos(job) == antes


def test_sem_silhueta_a_copia_nunca_sai_igual_com_conteudo_sobre_a_caixa_da_forma(diag_faixa, tmp_path):
    """Revisao da 0.10.0: com o filho da silhueta parado (sem isolador, memoria, tempo), o azul e conferido pela caixa,
    que cobre 99% do canvas. A copia nao sabe se a assinatura fica no branco: o arquivo pede o olhar do DA, com a
    frase, e nunca mostra "Igual ao seu"."""
    from desdobra.tela import estado as te
    job = tmp_path / 'job'
    shutil.copytree(diag_faixa['job'], job)
    shutil.rmtree(job / mod_silhueta.PASTA)
    conteudo = te.montar(job)
    gid = next(g for g, f in conteudo['familias'].items() if 'f1080x1920' in f['formatos'])
    assert 'f1080x1600' in conteudo['familias'][gid]['formatos']
    r = conteudo['editar']({'familia': gid, 'versao': None, 'edicoes': []}, 'fixture_de_teste')
    m = next(x for x in r['membros'] if x['formato'] == 'f1080x1600')
    assert m['situacao'] == 'pede_ajuste'
    frases = [f['texto'] for f in m['falhas'] if f['codigo'] == 'relacao_quebrada']
    assert any(f.startswith('O desdobra não tem o desenho') and 'a assinatura' in f and
               f.endswith('Confira este arquivo antes de confirmar.') for f in frases), frases
    # com a silhueta, o mesmo arquivo sai igual
    conteudo = te.montar(diag_faixa['job'])
    gid = next(g for g, f in conteudo['familias'].items() if 'f1080x1920' in f['formatos'])
    r = conteudo['editar']({'familia': gid, 'versao': None, 'edicoes': []}, 'fixture_de_teste')
    m = next(x for x in r['membros'] if x['formato'] == 'f1080x1600')
    assert m['situacao'] == 'igual', (m['falhas'], m['avisos'])
