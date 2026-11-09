# -*- coding: utf-8 -*-
"""M7b, B3: as rotas de imagem da tela, /render/<formato> (o master do render) e /final/<formato> (o arquivo final
que o portao gerou para a aprovacao).

Criterios de pronto cobertos aqui:
  - o id confere com ID_PREVIA e com o briefing confirmado: formato fora do briefing, sem render ou de outro job da
    404, mesmo com os arquivos na pasta;
  - os bytes so sao lidos depois do cookie; sem cookie, 404 sem tocar no disco;
  - o master so sai quando o sha256 dos bytes lidos bate com o render.json do formato; o arquivo final so sai quando
    bate com o que o portao gerou nesta janela (ServidorTela.mostrar_final);
  - so image/png e image/jpeg, conferidos tambem pelos primeiros bytes: um PDF ou uma fonte no lugar do master, mesmo
    com o render.json acertado, da 404; nunca .trabalho, PDF nem pagina de texto;
  - no-store, nosniff e os cabecalhos fixos da tela;
  - a matriz de 404 cobre id invalido, caminho com .., extensao de fonte e PDF;
  - a pasta do formato que aponta para fora do job (juncao do Windows) da 404.
Tudo sintetico: o job de duas linhas de test_tela_ato_render, com a fonte de autoteste do motor e o meio de teste.
"""
import dataclasses
import json
import shutil
import sys

import pytest

import test_derivacao_apoio as ap
import test_fontes_apoio as fap
import test_tela_ato_render as tar
import test_tela_palco as tp
import test_tela_servidor as tts
from desdobra import arquivos, contratos, humano
from desdobra.job import nucleo
from desdobra.briefing import modelo as mb
from desdobra.derivacao import nucleo as nd
from desdobra.entrega import aprovacao, codificar, portao
from desdobra.render import execucao
from desdobra.tela import servidor as ts

PNG_SIG = bytes([137, 80, 78, 71, 13, 10, 26, 10])
PDF = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n'
CABECALHOS = {'cache-control': ['no-store'], 'pragma': ['no-cache'], 'x-content-type-options': ['nosniff'],
              'cross-origin-resource-policy': ['same-origin'], 'referrer-policy': ['no-referrer'],
              'content-security-policy': [tts.CSP], 'x-frame-options': ['DENY']}
TIPOS_POR_FORMATO = {'mesma': ['image/jpeg', 'image/png'], 'perto': ['image/jpeg']}


def _campos(tipos):
    return {'tipos_aceitos': {'id': 'tipos', 'valor': tipos, 'situacao': 'confirmado'},
            'peso_max': {'id': 'peso', 'valor': {'alvo_bytes': 10 ** 6, 'reprova_acima_bytes': 10 ** 6 + 6000},
                         'condicao': None, 'situacao': 'confirmado'}}


@pytest.fixture(scope='module')
def renderizado(tmp_path_factory):
    """O job de duas linhas de test_tela_ato_render com 'mesma' e 'perto' renderizados (um selo de teste preso a cada
    formato). A folha do job sintetico e so o que o encoder le, gravada antes do briefing com a fase specs acertada,
    como em test_entrega_job (job_entregue): 'mesma' aceita png e jpeg (o png cabe no teto) e 'perto' so jpeg."""
    from desdobra.job import fases as mod_fases
    from desdobra.render import autoteste
    base = tmp_path_factory.mktemp('imagens')
    fontes = base / 'origem-fontes'
    fap.gravar(fontes, 'autoteste.ttf', autoteste.gerar_fonte())
    destino = base / 'job'
    nucleo.criar(destino, tp._psd_duas_linhas(base / 'origem' / 'kv.psd', autoteste.NOME_PS), 'c', fontes=[fontes])
    assert nucleo.proxima(destino, todas=True).codigo == 0
    formatos = [ap.formato(i, w, h, rotacao=tar.ROT0) for i, w, h in tp.FORMATOS_DUAS]
    chaves = {f['id']: f['chave'] for f in formatos}
    arquivos.gravar_json_atomico(destino / mb.ARQUIVO_FORMATOS, {'tipo': 'formatos_do_job', 'formatos': [
        {'id': f, 'chave': chaves[f], 'campos': _campos(t)} for f, t in TIPOS_POR_FORMATO.items()]})
    estado = nucleo.ler_estado(destino)
    estado['fases']['specs']['hash_saidas'] = nucleo.hashes_das_saidas(
        destino, next(f for f in mod_fases.ESTEIRA if f.id == 'specs'))
    nucleo.gravar_estado(destino, estado)
    assert nucleo.proxima(destino, todas=True).codigo == 0
    laudo = contratos.ler(destino / mb.ARQUIVO_LAUDO, 'laudo/1')
    ids = {c['nome']: c['identidade']['layer_id'] for c in laudo['camadas']}
    funcoes = {ids['fundo-sintetico']: 'fundo', ids['duas-linhas']: 'titulo',
               ids['quadrado-sintetico']: 'logo_principal'}
    b = ap.briefing(funcoes=funcoes, formatos=formatos)
    b.pop('cabecalho')
    b.pop('job_id')
    arq = base / 'fixture.json'
    arq.write_text(json.dumps(b), encoding='utf-8')
    mb.importar_teste(destino, arq)
    nd.derivar(destino)
    sessao = humano.abrir_sessao_tela(teste=True)
    try:
        for f in ('mesma', 'perto'):
            d = humano.exigir_tela('render', sessao, confirmado=True, alvo=f)
            execucao.renderizar(destino, disparo=d, formato=f, aceites=('largura_divergente',))
    finally:
        humano.fechar_sessao_tela(sessao)
    return destino


@pytest.fixture
def job(renderizado, tmp_path):
    destino = tmp_path / 'job'
    shutil.copytree(renderizado, destino)
    return destino


@pytest.fixture
def srv(job):
    s = tar._servidor(job).iniciar()
    yield s
    s.parar()


def _rel(job, fid='mesma'):
    return arquivos.ler_json(job / 'render' / fid / 'render.json')


def _gravar_rel(job, rel, fid='mesma'):
    arquivos.gravar_json_atomico(job / 'render' / fid / 'render.json', rel)


def _final(job, fid='mesma'):
    """O arquivo final do formato pelo portao, gravado na previa como o aprovar grava."""
    conf = portao.conferir(job, [fid], origem=False, aprovacao=False)
    item = conf['formatos'][fid]
    assert not item['falhas'], item['falhas']
    aprovacao.gravar_previa(job, fid, item['final'])
    return item['final']


def _sem_rota_contada(s, antes):
    for rota in ts.ROTAS:
        assert s.contagem[rota] == antes[rota], rota


# ------------------------------------------------------------------ as rotas na tabela
def test_rotas_de_imagem_estao_na_contagem():
    assert 'render' in ts.ROTAS and 'final' in ts.ROTAS
    assert ts.MIME_IMAGEM == {'png': 'image/png', 'jpg': 'image/jpeg'}


# ------------------------------------------------------------------ o master
@tar.RENDER
def test_master_do_formato_renderizado_sai_com_cabecalhos_fixos(srv, job):
    biscoito = tts._entrar(srv)
    codigo, cab, corpo = tts._pedir(srv, '/render/mesma', cookie=biscoito)
    assert codigo == 200  # numero-neutro: codigo HTTP
    assert corpo == (job / 'render' / 'mesma' / 'master.png').read_bytes() and corpo.startswith(PNG_SIG)
    assert arquivos.sha256_bytes(corpo) == _rel(job)['master']['sha256']
    assert cab['content-type'] == ['image/png']
    for k, v in CABECALHOS.items():
        assert cab[k] == v, k
    assert 'access-control-allow-origin' not in cab and 'set-cookie' not in cab
    assert srv.contagem['render'] == 1


@tar.RENDER
@pytest.mark.parametrize('rota', ['/render/mesma', '/final/mesma'])
def test_rotas_de_imagem_sem_cookie_dao_404_sem_ler_o_disco(srv, job, rota, monkeypatch):
    srv.mostrar_final('mesma', _final(job))
    lidos = []
    original = srv._imagem
    monkeypatch.setattr(srv, '_imagem', lambda *a: lidos.append(a) or original(*a))
    for cookie in (None, 'dsd_tela=%s' % ('0' * 32)):
        assert tts._pedir(srv, rota, cookie=cookie)[0] == 404  # numero-neutro: codigo HTTP
    assert lidos == [] and srv.contagem['sem_cookie'] == 2
    assert tts._pedir(srv, rota, cookie=tts._entrar(srv))[0] == 200  # numero-neutro: codigo HTTP
    assert len(lidos) == 1


MATRIZ = ['/render/', '/render', '/final/', '/final', '/render/MESMA', '/render/-mesma', '/render/mesma/',
          '/render/mesma/master.png', '/render/mesma.png', '/final/mesma.jpg', '/final/mesma.png',
          '/render/..', '/render/../estado.json', '/render/%2e%2e', '/render/mesma/../../estado.json',
          '/render/..%2Fmesma', '/final/..', '/final/../briefing/aprovacao.json', '/render/.trabalho',
          '/render/mesma.ttf', '/final/mesma.woff2', '/render/autoteste.TTF', '/render/kv.psd',
          '/render/mesma.pdf', '/final/mesma.pdf', '/render/kv.PDF', '/render/mesma?x=1', '/render/mesma%00',
          '/render/mesma.json', '/render/mesma.txt', '/render/mesma.html', '/RENDER/mesma', '//render/mesma',
          '/render//mesma', '/api/render/mesma', '/render/nao-existe', '/final/nao-existe']
FONTE = [c for c in MATRIZ if any(x in c.lower() for x in ('.ttf', '.woff', '.psd'))]


@tar.RENDER
@pytest.mark.parametrize('caminho', MATRIZ)
def test_matriz_de_404_das_rotas_de_imagem(srv, job, caminho):
    srv.mostrar_final('mesma', _final(job))
    biscoito = tts._entrar(srv)
    antes = dict(srv.contagem)
    codigo, cab, corpo = tts._pedir(srv, caminho, cookie=biscoito)
    assert codigo == 404 and corpo == b'' and cab['cache-control'] == ['no-store'], caminho  # numero-neutro: codigo HTTP
    _sem_rota_contada(srv, antes)
    if caminho in FONTE:
        assert srv.contagem['extensao_recusada'] == antes['extensao_recusada'] + 1, caminho


@tar.RENDER
def test_formato_sem_render_ou_fora_do_briefing_da_404(srv, job):
    biscoito = tts._entrar(srv)
    # 'largo' esta no briefing e nao tem render; 'origem' nao e formato do briefing
    for fid in ('largo', 'origem'):
        assert tts._pedir(srv, '/render/%s' % fid, cookie=biscoito)[0] == 404, fid  # numero-neutro: codigo HTTP
    # os arquivos certos de 'mesma' copiados para um formato que o briefing nao tem: 404
    shutil.copytree(job / 'render' / 'mesma', job / 'render' / 'fora')
    rel = _rel(job, 'fora')
    rel['formato']['chave'] = 'fora'
    _gravar_rel(job, rel, 'fora')
    assert tts._pedir(srv, '/render/fora', cookie=biscoito)[0] == 404  # numero-neutro: codigo HTTP
    assert srv.contagem['render'] == 0


@tar.RENDER
@pytest.mark.parametrize('mexer', ['formato', 'job', 'esquema', 'ilegivel'])
def test_render_json_de_outro_formato_ou_job_ou_ilegivel_da_404(srv, job, mexer):
    rel = _rel(job)
    if mexer == 'formato':
        rel['formato']['chave'] = 'perto'
    elif mexer == 'job':
        rel['job_id'] = 'outro-job'
    elif mexer == 'esquema':
        rel.pop('master')
    if mexer == 'ilegivel':
        (job / 'render' / 'mesma' / 'render.json').write_bytes(b'{nao e json')
    else:
        _gravar_rel(job, rel)
    assert tts._pedir(srv, '/render/mesma', cookie=tts._entrar(srv))[0] == 404  # numero-neutro: codigo HTTP
    assert srv.contagem['render'] == 0


@tar.RENDER
def test_master_que_nao_bate_com_o_render_json_da_404(srv, job):
    arq = job / 'render' / 'mesma' / 'master.png'
    arq.write_bytes(arq.read_bytes() + b'\0')
    biscoito = tts._entrar(srv)
    assert tts._pedir(srv, '/render/mesma', cookie=biscoito)[0] == 404  # numero-neutro: codigo HTTP
    (job / 'render' / 'mesma' / 'master.png').unlink()
    assert tts._pedir(srv, '/render/mesma', cookie=biscoito)[0] == 404  # numero-neutro: codigo HTTP


@tar.RENDER
@pytest.mark.parametrize('troca', ['pdf', 'fonte', 'texto', 'html'])
def test_pdf_fonte_ou_texto_no_lugar_do_master_da_404_mesmo_com_o_sha_acertado(srv, job, troca):
    dados = {'pdf': PDF, 'fonte': fap.fonte(ps='Inventada-Imagem'), 'texto': b'texto solto\n',
             'html': b'<!doctype html><title>x</title>'}[troca]
    (job / 'render' / 'mesma' / 'master.png').write_bytes(dados)
    rel = _rel(job)
    rel['master']['sha256'] = arquivos.sha256_bytes(dados)
    _gravar_rel(job, rel)
    codigo, _c, corpo = tts._pedir(srv, '/render/mesma', cookie=tts._entrar(srv))
    assert codigo == 404 and corpo == b''  # numero-neutro: codigo HTTP


@tar.RENDER
@pytest.mark.skipif(sys.platform != 'win32', reason='juncao do Windows')
def test_pasta_do_formato_que_aponta_para_fora_do_job_da_404(srv, job, tmp_path):
    import _winapi
    fora = tmp_path / 'fora-do-job'
    shutil.move(str(job / 'render' / 'mesma'), str(fora))
    _winapi.CreateJunction(str(fora), str(job / 'render' / 'mesma'))
    assert (job / 'render' / 'mesma' / 'master.png').is_file()
    assert tts._pedir(srv, '/render/mesma', cookie=tts._entrar(srv))[0] == 404  # numero-neutro: codigo HTTP


# ------------------------------------------------------------------ o arquivo final
@tar.RENDER
@pytest.mark.parametrize('fid, extensao', [('mesma', 'png'), ('perto', 'jpg')])
def test_final_so_sai_com_o_arquivo_que_o_portao_gerou_nesta_janela(srv, job, fid, extensao):
    biscoito, rota = tts._entrar(srv), '/final/%s' % fid
    final = _final(job, fid)
    assert final.extensao == extensao
    assert final.dados.startswith(ts.ASSINATURAS_IMAGEM[final.extensao])
    # o arquivo esta na previa, mas o portao nao o mostrou nesta janela: 404
    assert tts._pedir(srv, rota, cookie=biscoito)[0] == 404  # numero-neutro: codigo HTTP
    srv.mostrar_final(fid, final)
    codigo, cab, corpo = tts._pedir(srv, rota, cookie=biscoito)
    assert codigo == 200 and corpo == final.dados  # numero-neutro: codigo HTTP
    assert cab['content-type'] == [ts.MIME_IMAGEM[final.extensao]]
    for k, v in CABECALHOS.items():
        assert cab[k] == v, k
    assert srv.contagem['final'] == 1
    # o arquivo da previa trocado no disco: 404
    arq = job / aprovacao.PASTA_PREVIA / ('%s.%s' % (fid, final.extensao))
    arq.write_bytes(final.dados + b'\0')
    assert tts._pedir(srv, rota, cookie=biscoito)[0] == 404  # numero-neutro: codigo HTTP
    arq.write_bytes(final.dados)
    assert tts._pedir(srv, rota, cookie=biscoito)[0] == 200  # numero-neutro: codigo HTTP
    # o portao tirou o formato da janela: 404
    srv.mostrar_final(fid, None)
    assert tts._pedir(srv, rota, cookie=biscoito)[0] == 404  # numero-neutro: codigo HTTP
    assert srv.contagem['final'] == 2


@tar.RENDER
def test_final_de_pdf_com_o_sha_registrado_da_404(srv, job):
    final = _final(job)
    falso = dataclasses.replace(final, dados=PDF)
    (job / aprovacao.PASTA_PREVIA / ('mesma.%s' % final.extensao)).write_bytes(PDF)
    srv.mostrar_final('mesma', falso)
    assert tts._pedir(srv, '/final/mesma', cookie=tts._entrar(srv))[0] == 404  # numero-neutro: codigo HTTP


@tar.RENDER
def test_mostrar_final_recusa_o_que_nao_e_imagem_nem_formato(job):
    s = tar._servidor(job)
    try:
        png = codificar.ArquivoFinal(dados=PNG_SIG + b'x', extensao='png', parametros={})
        for fid in ('..', 'MESMA', 'mesma.ttf', 'a/b', ''):
            with pytest.raises(ValueError):
                s.mostrar_final(fid, png)
        for ext in ('pdf', 'trabalho', 'html', 'jpeg', 'PNG'):
            with pytest.raises(ValueError):
                s.mostrar_final('mesma', dataclasses.replace(png, extensao=ext))
        s.mostrar_final('mesma', png)
        s.mostrar_final('mesma', None)
    finally:
        s.parar()


def test_servidor_so_de_leitura_nao_serve_imagem_nem_mostra_final():
    s = ts.ServidorTela(tts._conteudo()).iniciar()
    try:
        biscoito = tts._entrar(s)
        for rota in ('/render/mesmo', '/final/mesmo'):
            assert tts._pedir(s, rota, cookie=biscoito)[0] == 404, rota  # numero-neutro: codigo HTTP
        with pytest.raises(ValueError):
            s.mostrar_final('mesmo', codificar.ArquivoFinal(dados=PNG_SIG, extensao='png', parametros={}))
    finally:
        s.parar()

