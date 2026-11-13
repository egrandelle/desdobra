# -*- coding: utf-8 -*-
"""M7c, passo M5: registrar o padrao da marca (desdobra.marca.registrar; decisoes-v1.md, 190, Q1, Q2 e Q3).

Criterios de pronto cobertos aqui:
  - o botao aparece so quando o job tem marca (briefing/marca.json do DA, nao "Sem marca") e todos os formatos estao
    aprovados (nucleo_aprovar.situacao com aceita_teste=False), com o briefing de origem da (Q2);
  - o registro recusa aprovacao, briefing e escolha da marca do modo de teste (origem fixture_de_teste), como o portao
    da entrega, para nenhum teste entrar na biblioteca da agencia;
  - o que vai ao perfil: so as regras de escala e as ancoras por funcao confirmadas pelo DA, com o job de origem, e o
    nome PostScript das faces (Q1); nunca arquivo nem caminho de fonte;
  - cada registro e uma versao nova pelo desdobra.marca.perfil, com a anterior inteira no historico; registrar de novo
    o mesmo job sem mudanca nao cria versao (Q3);
  - o ato "marca registrar" e so da tela (humano.ATOS_DA_TELA), com a confirmacao dentro da janela; o Claude nao
    registra: o gancho nega o codigo do registro e a rota da tela, e o Disparo de teste ou forjado e recusado;
  - depois do registro, o segundo job da mesma marca mostra o padrao citado (M4).
Tudo sintetico: o PSD de test_derivacao_apoio.psd_derivacao, uma fonte inventada, marcas sinteticas numa biblioteca
em pasta temporaria.
"""
import copy
import importlib.util
import json
import shutil
import sys
from argparse import Namespace
from pathlib import Path

import pytest

import test_derivacao_apoio as ap
import test_fontes_apoio as fap
import test_render_apoio as rap
import test_tela_escrita as tte
import test_tela_servidor as tts
from desdobra import arquivos, contratos, entrega, humano
from desdobra.briefing import modelo as mb
from desdobra.entrega import aprovacao, codificar
from desdobra.job import nucleo
from desdobra.render import execucao

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')

RAIZ_PLUGIN = Path(__file__).resolve().parents[1]
SCRIPT_GANCHO = RAIZ_PLUGIN / 'scripts' / 'gancho_confirmacoes.py'
ROT0 = {'graus': 0, 'sentido': None}
FORMATOS = [ap.formato('mesma', 640, 320, rotacao=ROT0), ap.formato('perto', 400, 240, rotacao=ROT0)]
IDS = [f['id'] for f in FORMATOS]
MARCA = 'Marca Sintetica Registro'
JOB_ANTERIOR = 'a0' * 16


def _registrar():
    from desdobra.marca import registrar
    return registrar


def _origens_do_da(b):
    """Toda decisao do briefing de teste com a origem do DA (o gravador da tela grava assim)."""
    def trocar(no):
        if isinstance(no, dict):
            if 'situacao' in no and isinstance(no.get('origem'), dict):
                no['origem'] = {'tipo': 'da', 'ref': 'rascunho'}
            for v in no.values():
                trocar(v)
        elif isinstance(no, list):
            for v in no:
                trocar(v)
    trocar(b)
    return b


def _gravar_briefing_do_da(job, b):
    """Grava o briefing como a tela grava (briefing.modelo.gravar_com_historico, sem o disparo): a versao anterior no
    historico e a entrada no indice encadeado, para o briefing nao ficar fora do indice."""
    from desdobra.briefing import historico
    atual = Path(job) / mb.ARQUIVO
    sha_anterior = None
    if atual.is_file():
        sha_anterior = arquivos.sha256_arquivo(atual)
        pasta = Path(job) / mb.PASTA_HISTORICO
        pasta.mkdir(parents=True, exist_ok=True)
        arquivos.gravar_bytes_atomico(pasta / ('%s.json' % sha_anterior), atual.read_bytes())
    contratos.gravar(atual, b, 'briefing/1')
    historico.registrar(job, sha_anterior, arquivos.sha256_arquivo(atual), b.get('cabecalho'))


def _funcoes_aplicadas(job):
    """As funcoes que as pecas aprovadas aplicam (regra_aplicada de cada elemento da derivacao dos formatos)."""
    from desdobra.derivacao import nucleo as nd
    saida = set()
    for fid in IDS:
        d = contratos.ler(Path(job) / nd.PASTA / ('%s.json' % fid), nd.ESQUEMA)
        saida |= {e['regra_aplicada']['funcao'] for e in d['elementos']}
    return saida


def _encoder_de_teste():
    def arquivo_final(pasta, formato):
        dados = (Path(pasta) / 'render' / formato / 'master.png').read_bytes()
        return codificar.ArquivoFinal(dados=dados, extensao='png', parametros={'tipo': 'png', 'qualidade': 90})
    return arquivo_final


@pytest.fixture(scope='module')
def renderizado(tmp_path_factory):
    """O job do DA renderizado nos dois formatos, sem aprovacao."""
    base = tmp_path_factory.mktemp('registrar')
    fontes = base / 'origem-fontes'
    fap.gravar(fontes, 'inventada.ttf', fap.fonte(ps=rap.FONTE))
    job = base / 'job'
    nucleo.criar(job, ap.psd_derivacao(base / 'origem' / 'kv.psd'), 'c', fontes=[fontes])
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    b, _ids = ap.briefing_do_job(laudo, FORMATOS)
    arq = base / 'fixture-m5.json'
    arq.write_text(json.dumps(b), encoding='utf-8')
    mb.importar_teste(job, arq)
    # o briefing do DA so chega pela tela: aqui a origem e trocada a mao, antes de derivar e renderizar
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    _origens_do_da(b)
    b['cabecalho'].update(origem='da', meio='tela')
    b['composicoes'] = [{'familia': 'familia-%s' % f['id'], 'formatos': [f['id']], 'versao': None, 'edicoes': [],
                         'confirmada': True, 'confirmacao': {'origem': 'da', 'meio': 'tela', 'em': '2026-11-13T10:00:00'}}
                        for f in b['formatos']]
    _gravar_briefing_do_da(job, b)
    from desdobra.derivacao import nucleo as nd
    nd.derivar(job)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(humano, 'console_interativo', lambda: (True, None))
        for fid in IDS:
            execucao.renderizar(job, disparo=humano.exigir('render'), formato=fid)
    return job


@pytest.fixture(scope='module')
def aprovado(renderizado, tmp_path_factory):
    """O mesmo job com os dois formatos aprovados pelo DA (o nucleo comum do aprovar, com o encoder de teste)."""
    job = tmp_path_factory.mktemp('aprovado') / 'job'
    shutil.copytree(renderizado, job)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(humano, 'console_interativo', lambda: (True, None))
        mp.setattr(codificar, 'arquivo_final', _encoder_de_teste())
        mp.setattr(humano, 'ler', lambda pergunta: 'sim')
        assert entrega._aprovar(Namespace(job=str(job), formato=list(IDS))).codigo == 0
    return job


@pytest.fixture
def bib(tmp_path):
    from desdobra.marca import perfil
    b = tmp_path / 'biblioteca-da-agencia'
    b.mkdir()
    return b, perfil.criar(b, MARCA)['id']


def _marca_do_job(job, marca_id, origem='da'):
    from desdobra.marca import job as mj
    estado = contratos.ler(job / 'estado.json', 'estado/1')
    meio = 'tela' if origem == 'da' else 'medicao'
    contratos.gravar(job / mj.ARQUIVO, {
        'esquema': mj.ESQUEMA, 'job_id': estado['job_id'], 'escolha': 'sem_marca' if marca_id is None else 'marca',
        'marca_id': marca_id, 'origem': origem,
        'escolhido_por': {'usuario': None, 'maquina': None, 'meio': meio, 'quando': '2026-11-13T10:00:00-03:00'}},
        mj.ESQUEMA)


@pytest.fixture
def job(aprovado, bib, tmp_path, monkeypatch):
    """Uma copia do job aprovado com a marca sintetica escolhida pelo DA. O arquivo final e o do encoder de teste, e os
    parametros dele que nao dependem do master sao os do encoder de teste (o job sintetico nao tem folha confirmada)."""
    monkeypatch.setattr(codificar, 'arquivo_final', _encoder_de_teste())
    monkeypatch.setattr(codificar, 'parametros_sem_o_master',
                        lambda pasta, formato, **_k: {'tipo': 'png', 'qualidade': 90})
    destino = tmp_path / 'job'
    shutil.copytree(aprovado, destino)
    _marca_do_job(destino, bib[1])
    return destino


def _job_id(job):
    return contratos.ler(job / 'estado.json', 'estado/1')['job_id']


@pytest.fixture
def tela(monkeypatch):
    """Uma sessao da tela de verdade (meio tela, origem da): o processo de teste nao tem as marcas do Claude."""
    monkeypatch.setattr(humano, 'ambiente_da_tela', lambda: (True, None))
    sessao = humano.abrir_sessao_tela(teste=False)
    yield sessao
    humano.fechar_sessao_tela(sessao)


def _disparo(sessao):
    return humano.exigir_tela(_registrar().COMANDO, sessao, confirmado=True)


# ------------------------------------------------------------------ o ato e so da tela
def test_registrar_e_ato_so_da_tela():
    reg = _registrar()
    assert reg.COMANDO == 'marca registrar'
    assert humano.ATOS_DA_TELA == ('modo dados escolher', 'familia confirmar', 'marca escolher', 'marca registrar')
    assert reg.COMANDO not in humano.COMANDOS
    with pytest.raises(ValueError):
        humano.exigir(reg.COMANDO)  # nao ha comando de terminal para o registro


# ------------------------------------------------------------------ quando o botao aparece (Q2)
def test_job_com_marca_e_tudo_aprovado_pode_registrar(job, bib):
    from desdobra.briefing import historico
    assert historico.conferir(job) == []  # o briefing do job e o ultimo do indice, como a tela grava
    v = _registrar().na_tela(job, bib[0])
    assert v['pode'] is True and v['motivo'] is None and v['guardado'] is False, v
    assert v['nome'] == MARCA and v['versao_atual'] == 0 and v['versao_nova'] == 1
    assert v['formatos'] == len(IDS)


def test_sem_biblioteca_sem_marca_ou_sem_marca_escolhida_nao_mostra_o_botao(job, bib, tmp_path):
    reg = _registrar()
    assert reg.na_tela(job, None)['pode'] is False
    _marca_do_job(job, None)
    v = reg.na_tela(job, bib[0])
    assert (v['pode'], v['motivo']) == (False, 'sem_marca')
    (job / 'briefing' / 'marca.json').unlink()
    assert reg.na_tela(job, bib[0])['motivo'] == 'sem_marca'
    # a marca escolhida que a biblioteca desta tela nao tem
    _marca_do_job(job, 'cd' * 16)
    assert reg.na_tela(job, bib[0])['motivo'] == 'marca_fora_da_biblioteca'
    outra = tmp_path / 'outra'
    outra.mkdir()
    _marca_do_job(job, bib[1])
    assert reg.na_tela(job, outra)['motivo'] == 'marca_fora_da_biblioteca'


def test_formato_sem_aprovacao_nao_mostra_o_botao(renderizado, bib, tmp_path):
    copia = tmp_path / 'sem-aprovacao'
    shutil.copytree(renderizado, copia)
    _marca_do_job(copia, bib[1])
    v = _registrar().na_tela(copia, bib[0])
    assert (v['pode'], v['motivo']) == (False, 'formato_sem_aprovacao')
    assert 'regras' not in v  # sem o botao, nada do conteudo vai a pagina


def test_um_formato_sem_aprovacao_ja_basta_para_esconder(job, bib):
    dados = contratos.ler(job / aprovacao.ARQUIVO, aprovacao.ESQUEMA)
    del dados['formatos']['perto']
    contratos.gravar(job / aprovacao.ARQUIVO, dados, aprovacao.ESQUEMA)
    assert _registrar().na_tela(job, bib[0])['motivo'] == 'formato_sem_aprovacao'


def test_aprovacao_caida_nao_mostra_o_botao(job, bib):
    master = job / 'render' / 'mesma' / 'master.png'
    master.write_bytes(master.read_bytes() + b'\0')
    assert _registrar().na_tela(job, bib[0])['motivo'] == 'formato_sem_aprovacao'


def test_aprovacao_de_teste_e_recusada(job, bib):
    dados = contratos.ler(job / aprovacao.ARQUIVO, aprovacao.ESQUEMA)
    reg = dados['formatos']['mesma']
    reg['aprovado_por'].update(meio='medicao', origem='fixture_de_teste')
    reg['registro_sha256'] = aprovacao.selo(reg)
    contratos.gravar(job / aprovacao.ARQUIVO, dados, aprovacao.ESQUEMA)
    assert _registrar().na_tela(job, bib[0])['motivo'] == 'formato_sem_aprovacao'


@pytest.mark.parametrize('origem, meio, motivo', [('fixture_de_teste', 'importar_teste', 'briefing_de_fixture_de_teste'),
                                                  ('rascunho', 'rascunho', 'briefing_rascunho')])
def test_briefing_que_nao_e_do_da_e_recusado(job, bib, origem, meio, motivo):
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    b['cabecalho'].update(origem=origem, meio=meio)
    contratos.gravar(job / mb.ARQUIVO, b, 'briefing/1')
    assert _registrar().na_tela(job, bib[0])['motivo'] == motivo


def test_marca_escolhida_no_modo_de_teste_e_recusada(job, bib):
    _marca_do_job(job, bib[1], origem='fixture_de_teste')
    assert _registrar().na_tela(job, bib[0])['motivo'] == 'marca_de_teste'


def test_briefing_trocado_fora_da_tela_nao_registra(job, bib, tela):
    """Revisao do M5: o briefing que nao e o ultimo do indice encadeado (trocado fora da tela, com a origem da escrita
    a mao) nao chega a biblioteca da agencia: sem botao, e o gravar recusa."""
    from desdobra.briefing import historico
    from desdobra.marca import perfil
    reg = _registrar()
    imp = reg.na_tela(job, bib[0])['impressao']
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    for r in b['regras_escala']:
        if r['funcao'] == 'cta':
            r['regra']['valor'] = 'largura' if r['regra']['valor'] != 'largura' else 'altura'
    contratos.gravar(job / mb.ARQUIVO, b, 'briefing/1')  # fora da tela: sem entrada no indice
    assert [p['codigo'] for p in historico.conferir(job)] == ['briefing_fora_do_indice']
    v = reg.na_tela(job, bib[0])
    assert (v['pode'], v['guardado'], v['motivo']) == (False, False, 'briefing_fora_do_historico')
    assert 'regras' not in v
    with pytest.raises(reg.ErroRegistro) as e:
        reg.gravar(job, disparo=_disparo(tela), biblioteca=bib[0], impressao=imp)
    assert e.value.motivo == 'briefing_fora_do_historico'
    assert perfil.ler(bib[0], bib[1])['versao'] == 0


# ------------------------------------------------------------------ o que vai ao perfil (Q1)
def test_a_janela_mostra_so_regras_ancoras_job_de_origem_e_faces(job, bib):
    v = _registrar().na_tela(job, bib[0])
    jid = _job_id(job)
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    aplicadas = _funcoes_aplicadas(job)
    usadas = ({r['funcao'] for r in b['regras_escala']} & aplicadas) - {'indeterminado'}
    assert usadas and {r['funcao'] for r in v['regras']} == usadas
    assert all(r['job'] == jid[:8] and r['desta_campanha'] is True for r in v['regras'] + v['ancoras'])
    assert {(a['funcao'], a['x'], a['y']) for a in v['ancoras']} == \
        {(a['funcao'], a['x']['valor'], a['y']['valor']) for a in b['ancoras'] if a.get('funcao') in aplicadas}
    assert v['faces'] == [rap.FONTE]
    assert len(v['impressao']) == 64
    texto = json.dumps(v, ensure_ascii=False)
    # nunca caminho, arquivo de fonte, id da marca nem nada do job alem do id curto
    for proibido in (str(bib[0]), str(job), bib[1], '.ttf', 'inventada', 'entrada', '\\\\', '/'):
        assert proibido not in texto, proibido


def test_conteudo_so_leva_o_que_o_da_confirmou(job, bib):
    """Regra com origem que nao e do DA (de teste, da decisao 10) ou pendente fica fora; a origem padrao_marca mantem o
    job de origem do perfil; a funcao do perfil que o job nao usa continua, com o job de origem dela."""
    from desdobra.marca import perfil
    reg = _registrar()
    jid = _job_id(job)
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    laudo = contratos.ler(job / mb.ARQUIVO_LAUDO, 'laudo/1')
    anterior = {'versao': 1, 'job_origem': JOB_ANTERIOR, 'campanha': {'job': JOB_ANTERIOR},
                'regras_escala': [{'funcao': 'destaque_numerico', 'regra': 'largura', 'job_origem': JOB_ANTERIOR},
                                  {'funcao': 'titulo', 'regra': 'raiz_area', 'job_origem': JOB_ANTERIOR}],
                'ancoras': [{'funcao': 'destaque_numerico', 'x': 'centro', 'y': 'base', 'job_origem': JOB_ANTERIOR}],
                'faces': [{'postscript': 'Antiga-Regular'}]}
    ref = 'marca:%s@v1#job:%s' % (bib[1], JOB_ANTERIOR)
    for r in b['regras_escala']:
        if r['funcao'] == 'titulo':
            r['regra'] = {'valor': 'raiz_area', 'situacao': 'confirmado', 'origem': {'tipo': 'padrao_marca', 'ref': ref}}
        elif r['funcao'] == 'fundo':
            r['regra']['origem'] = {'tipo': 'fixture_de_teste', 'ref': 'teste'}
        elif r['funcao'] == 'logo_principal':
            r['regra'] = {'valor': None, 'situacao': 'pendente', 'origem': {'tipo': 'da', 'ref': None}}
        elif r['funcao'] == 'texto_legal':
            r['regra']['origem'] = {'tipo': 'decisao_10', 'ref': 'decisao 10'}
    aplicadas = _funcoes_aplicadas(job)
    c = reg.conteudo(b, laudo, jid, bib[1], anterior, funcoes=aplicadas)
    regras = {r['funcao']: r for r in c['regras_escala']}
    assert regras['titulo'] == {'funcao': 'titulo', 'regra': 'raiz_area', 'job_origem': JOB_ANTERIOR}
    assert 'fundo' not in regras and 'logo_principal' not in regras and 'texto_legal' not in regras
    assert regras['texto_de_apoio']['job_origem'] == jid
    # a funcao confirmada no briefing que nenhuma peca aprovada aplica fica fora (revisao do M5)
    assert 'cta' not in aplicadas and 'cta' not in regras
    assert 'cta' not in {a['funcao'] for a in c['ancoras']}
    # a funcao que este job nao decidiu fica como estava no perfil
    assert regras['destaque_numerico'] == {'funcao': 'destaque_numerico', 'regra': 'largura', 'job_origem': JOB_ANTERIOR}
    assert {'funcao': 'destaque_numerico', 'x': 'centro', 'y': 'base', 'job_origem': JOB_ANTERIOR} in c['ancoras']
    # as faces sao as desta campanha, so pelo nome PostScript
    assert c['faces'] == [{'postscript': rap.FONTE}]
    # o ref de outra marca nao leva a origem de outro job: a regra conta como deste job
    for r in b['regras_escala']:
        if r['funcao'] == 'titulo':
            r['regra']['origem']['ref'] = 'marca:%s@v1#job:%s' % ('ef' * 16, JOB_ANTERIOR)
    c = reg.conteudo(b, laudo, jid, bib[1], anterior, funcoes=aplicadas)
    assert {r['funcao']: r for r in c['regras_escala']}['titulo']['job_origem'] == jid
    assert perfil.ESQUEMA == 'perfil-marca/1'


def test_face_com_nome_fora_do_contrato_fica_fora(job, bib):
    reg = _registrar()
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    laudo = contratos.ler(job / mb.ARQUIVO_LAUDO, 'laudo/1')
    base = laudo['fontes_usadas'][0]
    laudo['fontes_usadas'] = [dict(base, fonte_ps=n) for n in
                              ('Boa-Regular', 'Arquivo.otf', 'C:/fontes/x', 'com espaco', 'Boa-Regular', 'Outra-Bold')]
    c = reg.conteudo(b, laudo, _job_id(job), bib[1], None, funcoes=_funcoes_aplicadas(job))
    assert c['faces'] == [{'postscript': 'Boa-Regular'}, {'postscript': 'Outra-Bold'}]


# ------------------------------------------------------------------ gravar: versao nova e historico (Q3)
def test_registrar_grava_a_versao_1_com_a_campanha(job, bib, tela):
    from desdobra.marca import perfil
    reg = _registrar()
    v = reg.na_tela(job, bib[0])
    r = reg.gravar(job, disparo=_disparo(tela), biblioteca=bib[0], impressao=v['impressao'])
    assert r == {'versao': 1, 'criou': True}
    p = perfil.ler(bib[0], bib[1])
    atual = p['atual']
    jid = _job_id(job)
    assert p['versao'] == 1 and p['historico'] == [] and atual['job_origem'] == jid
    camp = atual['campanha']
    assert (camp['job'], camp['origem'], camp['meio']) == (jid, 'da', 'tela')
    aprov = contratos.ler(job / aprovacao.ARQUIVO, aprovacao.ESQUEMA)
    assert sorted((f['formato'], f['aprovacao_sha256']) for f in camp['formatos']) == \
        sorted((fid, aprov['formatos'][fid]['registro_sha256']) for fid in IDS)
    assert [f['postscript'] for f in atual['faces']] == [rap.FONTE]
    assert {r['funcao'] for r in atual['regras_escala']} == {r['funcao'] for r in v['regras']}
    # o log do job leva so a versao e se criou: nem o nome nem o id da marca
    log = (job / 'log' / 'eventos.jsonl').read_text(encoding='utf-8')
    linha = [json.loads(x) for x in log.splitlines() if 'padrao_da_marca' in x][-1]
    assert linha['evento'] == 'padrao_da_marca_registrado' and linha['versao'] == 1
    assert MARCA not in log and bib[1] not in log
    # depois do registro, a tela diz que o padrao desta campanha ja esta guardado, sem botao
    depois = reg.na_tela(job, bib[0])
    assert (depois['pode'], depois['guardado'], depois['versao_atual']) == (False, True, 1)
    assert (depois['versao_guardada'], depois['versao_nova']) == (1, None)


def test_funcao_que_nenhuma_peca_aprovada_aplica_fica_fora_do_perfil(job, bib, tela):
    """Revisao do M5: a regra e a ancora de uma funcao sem elemento nas pecas aprovadas ficam fora da impressao da
    aprovacao (mudam depois dela sem derruba-la), entao nao vao ao perfil: so regra de peca conferida (Q2)."""
    from desdobra.marca import perfil
    reg = _registrar()
    aplicadas = _funcoes_aplicadas(job)
    assert 'cta' not in aplicadas
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    for r in b['regras_escala']:
        if r['funcao'] == 'cta':
            r['regra']['valor'] = 'largura' if r['regra']['valor'] != 'largura' else 'altura'
    for a in b['ancoras']:
        if a.get('funcao') == 'cta':
            a['x']['valor'] = 'direita' if a['x']['valor'] != 'direita' else 'esquerda'
    _gravar_briefing_do_da(job, b)  # pela tela, depois da aprovacao dos dois formatos
    v = reg.na_tela(job, bib[0])
    assert v['pode'] is True, v
    assert {i['funcao'] for i in v['regras'] + v['ancoras']} <= aplicadas
    reg.gravar(job, disparo=_disparo(tela), biblioteca=bib[0], impressao=v['impressao'])
    atual = perfil.ler(bib[0], bib[1])['atual']
    assert {i['funcao'] for i in atual['regras_escala'] + atual['ancoras']} <= aplicadas
    assert 'cta' not in {i['funcao'] for i in atual['regras_escala'] + atual['ancoras']}


def test_mesmo_job_depois_do_registro_de_outro_job_continua_guardado(job, bib, tela):
    """Revisao do M5: o job 1 grava a v1 e outro job grava a v2. O job 1 sem mudanca nenhuma continua guardado (na
    versao 1), sem botao, e o gravar recusa com ja_guardado: nao volta o padrao antigo por cima do mais novo."""
    from desdobra.marca import perfil
    reg = _registrar()
    imp = reg.na_tela(job, bib[0])['impressao']
    assert reg.gravar(job, disparo=_disparo(tela), biblioteca=bib[0], impressao=imp)['versao'] == 1
    p1 = perfil.ler(bib[0], bib[1])
    camp = {'job': JOB_ANTERIOR, 'data': '2026-11-14', 'formatos': [{'formato': 'f1', 'aprovacao_sha256': 'e' * 64}],
            'confirmado_por': {'usuario': 'da', 'maquina': 'estacao'}, 'origem': 'da', 'meio': 'tela'}
    regras = [dict(r) for r in p1['atual']['regras_escala']]
    regras[0] = dict(regras[0], regra='largura' if regras[0]['regra'] != 'largura' else 'altura',
                     job_origem=JOB_ANTERIOR)
    perfil.nova_versao(bib[0], bib[1], campanha=camp, quando='2026-11-14T10:00:00-03:00', regras_escala=regras,
                       ancoras=p1['atual']['ancoras'], faces=p1['atual']['faces'])
    arq = bib[0] / 'marcas' / bib[1] / 'perfil-marca.json'
    antes = arq.read_bytes()
    v = reg.na_tela(job, bib[0])
    assert (v['pode'], v['guardado'], v['motivo']) == (False, True, 'ja_guardado'), v
    assert (v['versao_atual'], v['versao_guardada'], v['versao_nova']) == (2, 1, None)
    with pytest.raises(reg.ErroRegistro) as e:
        reg.gravar(job, disparo=_disparo(tela), biblioteca=bib[0], impressao=imp)
    assert e.value.motivo == 'ja_guardado'
    assert arq.read_bytes() == antes and perfil.ler(bib[0], bib[1])['versao'] == 2


def test_registrar_de_novo_sem_mudanca_nao_cria_versao(job, bib, tela):
    reg = _registrar()
    imp = reg.na_tela(job, bib[0])['impressao']
    assert reg.gravar(job, disparo=_disparo(tela), biblioteca=bib[0], impressao=imp)['criou'] is True
    arq = bib[0] / 'marcas' / bib[1] / 'perfil-marca.json'
    antes = arq.read_bytes()
    with pytest.raises(reg.ErroRegistro) as e:
        reg.gravar(job, disparo=_disparo(tela), biblioteca=bib[0], impressao=imp)
    assert e.value.motivo == 'ja_guardado'
    assert arq.read_bytes() == antes


def test_segundo_registro_vira_versao_nova_com_a_anterior_inteira_no_historico(job, bib, tela):
    from desdobra.marca import perfil
    reg = _registrar()
    camp = {'job': JOB_ANTERIOR, 'data': '2026-11-01', 'formatos': [{'formato': 'f1', 'aprovacao_sha256': 'e' * 64}],
            'confirmado_por': {'usuario': 'da', 'maquina': 'estacao'}, 'origem': 'da', 'meio': 'tela'}
    perfil.nova_versao(bib[0], bib[1], campanha=camp, quando='2026-11-01T10:00:00-03:00',
                       regras_escala=[{'funcao': 'destaque_numerico', 'regra': 'largura', 'job_origem': JOB_ANTERIOR}],
                       ancoras=[], faces=[{'postscript': 'Antiga-Regular'}])
    v1 = perfil.ler(bib[0], bib[1])['atual']
    v = reg.na_tela(job, bib[0])
    assert (v['versao_atual'], v['versao_nova']) == (1, 2)
    mantida = next(r for r in v['regras'] if r['funcao'] == 'destaque_numerico')
    # o perfil de antes do ajuste do nome nao tem o nome do job: a tela cai no id curto (job_nome None)
    assert mantida == {'funcao': 'destaque_numerico', 'regra': 'largura', 'job': JOB_ANTERIOR[:8], 'job_nome': None,
                       'desta_campanha': False}
    assert reg.gravar(job, disparo=_disparo(tela), biblioteca=bib[0], impressao=v['impressao'])['versao'] == 2
    p = perfil.ler(bib[0], bib[1])
    assert p['versao'] == 2 and p['atual']['job_origem'] == _job_id(job)
    assert arquivos.para_json(p['historico'][0]) == arquivos.para_json(v1)


def test_registro_recusa_o_que_mudou_depois_da_janela(job, bib, tela):
    reg = _registrar()
    with pytest.raises(reg.ErroRegistro) as e:
        reg.gravar(job, disparo=_disparo(tela), biblioteca=bib[0], impressao='0' * 64)
    assert e.value.motivo == 'mudou_durante_a_confirmacao'
    assert not reg.na_tela(job, bib[0])['guardado']


def test_registro_recusa_o_perfil_que_mudou_entre_a_conferencia_e_a_gravacao(job, bib, tela, monkeypatch):
    """Outro registro da mesma marca grava a v1 depois da conferencia deste e antes da leitura do nova_versao: este
    registro e recusado (mudou_durante_a_confirmacao) e a funcao do outro job continua na versao que vale."""
    from desdobra.marca import perfil
    reg = _registrar()
    v = reg.na_tela(job, bib[0])
    assert v['versao_atual'] == 0
    original = perfil.nova_versao
    camp = {'job': JOB_ANTERIOR, 'data': '2026-11-14', 'formatos': [{'formato': 'f1', 'aprovacao_sha256': 'e' * 64}],
            'confirmado_por': {'usuario': 'da', 'maquina': 'outra'}, 'origem': 'da', 'meio': 'tela'}

    def intercalado(*a, **k):
        original(bib[0], bib[1], campanha=camp, quando='2026-11-14T10:00:00-03:00',
                 regras_escala=[{'funcao': 'veu_de_legibilidade', 'regra': 'largura', 'job_origem': JOB_ANTERIOR}],
                 ancoras=[], faces=[])
        return original(*a, **k)
    monkeypatch.setattr(perfil, 'nova_versao', intercalado)
    with pytest.raises(reg.ErroRegistro) as e:
        reg.gravar(job, disparo=_disparo(tela), biblioteca=bib[0], impressao=v['impressao'])
    assert e.value.motivo == 'mudou_durante_a_confirmacao'
    p = perfil.ler(bib[0], bib[1])
    assert p['versao'] == 1 and p['atual']['campanha']['job'] == JOB_ANTERIOR
    assert 'veu_de_legibilidade' in {x['funcao'] for x in p['atual']['regras_escala']}


ESPERA_DO_OUTRO_S = 1.0  # numero-neutro: sem a trava, o outro registro grava em milissegundos; com ela, fica esperando


def test_registro_concorrente_entre_a_releitura_e_a_gravacao_nao_some_sem_erro(job, bib, tela, monkeypatch):
    """Revisao da correcao B: outro registro da mesma marca que chega entre a releitura final do nova_versao e a
    gravacao deste espera a trava da marca. Este grava a v1; o outro, quando entra, ve a v1 no lugar da v0 que
    conferiu e e recusado. A versao de nenhum dos dois some sem erro."""
    import threading
    from desdobra.marca import perfil
    reg = _registrar()
    v = reg.na_tela(job, bib[0])
    assert v['versao_atual'] == 0
    original = perfil._gravar
    camp = {'job': JOB_ANTERIOR, 'data': '2026-11-14', 'formatos': [{'formato': 'f1', 'aprovacao_sha256': 'e' * 64}],
            'confirmado_por': {'usuario': 'da', 'maquina': 'outra'}, 'origem': 'da', 'meio': 'tela'}
    resultado = {}

    def outro():
        try:
            resultado['outro'] = perfil.nova_versao(
                bib[0], bib[1], campanha=camp, quando='2026-11-14T10:00:00-03:00', ancoras=[], faces=[],
                regras_escala=[{'funcao': 'veu_de_legibilidade', 'regra': 'largura', 'job_origem': JOB_ANTERIOR}],
                versao_esperada=0)
        except perfil.ErroPerfil as e:
            resultado['erro_do_outro'] = str(e)
    linha = threading.Thread(target=outro)

    def gravar_intercalado(biblioteca, dados):
        if 'iniciado' not in resultado:
            resultado['iniciado'] = True
            linha.start()
            linha.join(ESPERA_DO_OUTRO_S)
        return original(biblioteca, dados)
    monkeypatch.setattr(perfil, '_gravar', gravar_intercalado)
    feito = reg.gravar(job, disparo=_disparo(tela), biblioteca=bib[0], impressao=v['impressao'])
    linha.join()
    assert feito == {'versao': 1, 'criou': True}
    p = perfil.ler(bib[0], bib[1])
    jobs = [x['campanha']['job'] for x in [p['atual']] + p['historico']]
    assert 'outro' not in resultado or JOB_ANTERIOR in jobs, 'a versao do outro registro sumiu sem erro'
    assert 'mudou' in resultado.get('erro_do_outro', '')
    assert jobs == [_job_id(job)]


def test_registro_recusa_o_job_que_nao_pode(job, bib, tela):
    reg = _registrar()
    imp = reg.na_tela(job, bib[0])['impressao']
    _marca_do_job(job, None)
    with pytest.raises(reg.ErroRegistro) as e:
        reg.gravar(job, disparo=_disparo(tela), biblioteca=bib[0], impressao=imp)
    assert e.value.motivo == 'sem_marca'


# ------------------------------------------------------------------ o Claude nao registra
def test_disparo_do_modo_de_teste_e_recusado(job, bib):
    from desdobra.marca import perfil
    reg = _registrar()
    imp = reg.na_tela(job, bib[0])['impressao']
    sessao = humano.abrir_sessao_tela(teste=True)
    try:
        d = humano.exigir_tela(reg.COMANDO, sessao, confirmado=True)
        with pytest.raises(reg.ErroRegistro) as e:
            reg.gravar(job, disparo=d, biblioteca=bib[0], impressao=imp)
        assert e.value.motivo == 'registro_de_teste'
    finally:
        humano.fechar_sessao_tela(sessao)
    assert perfil.ler(bib[0], bib[1])['versao'] == 0


def test_disparo_forjado_ou_de_outro_ato_e_recusado(job, bib, tela):
    from desdobra.marca import perfil
    reg = _registrar()
    imp = reg.na_tela(job, bib[0])['impressao']
    forjado = humano.Disparo(comando=reg.COMANDO, meio='tela', usuario=None, maquina=None, quando='2026-11-13',
                             selo='0' * 32)
    with pytest.raises(humano.ErroHumano):
        reg.gravar(job, disparo=forjado, biblioteca=bib[0], impressao=imp)
    outro = humano.exigir_tela('marca escolher', tela, confirmado=True)
    with pytest.raises(humano.ErroHumano):
        reg.gravar(job, disparo=outro, biblioteca=bib[0], impressao=imp)
    assert perfil.ler(bib[0], bib[1])['versao'] == 0


def test_processo_do_claude_nao_abre_a_sessao_da_tela(monkeypatch):
    monkeypatch.setenv('CLAUDECODE', '1')
    with pytest.raises(humano.ErroHumano):
        humano.abrir_sessao_tela(teste=False)


def _gancho():
    spec = importlib.util.spec_from_file_location('gancho_confirmacoes_registrar', SCRIPT_GANCHO)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CASOS_DO_CLAUDE = [
    ('Bash', {'command': 'python -c "from desdobra.marca import registrar; registrar.gravar(1)"'}),
    ('Bash', {'command': 'python -c "import desdobra.marca.registrar as r"'}),
    ('PowerShell', {'command': 'python -c "from desdobra.marca.registrar import gravar"'}),
    ('Bash', {'command': 'curl -X POST http://127.0.0.1:8123/api/ato/pedir -d \'{"ato":"marca_registrar"}\''}),
    ('PowerShell', {'command': 'Invoke-WebRequest -Method Post http://127.0.0.1:8123/api/ato/confirmar'}),
]


@pytest.mark.parametrize('ferramenta, entrada', CASOS_DO_CLAUDE)
def test_gancho_nega_ao_claude_o_codigo_e_a_rota_do_registro(ferramenta, entrada, tmp_path):
    g = _gancho()
    decisao, _motivo = g.decidir_com_motivo({'tool_name': ferramenta, 'tool_input': entrada, 'cwd': str(tmp_path)})
    assert decisao == 'deny', (ferramenta, entrada)


def test_gancho_nega_o_navegador_do_claude_na_tela():
    g = _gancho()
    entrada = {'url': 'http://127.0.0.1:8123/api/ato/pedir'}
    assert g.decidir_com_motivo({'tool_name': 'mcp__Claude_Browser__navigate', 'tool_input': entrada,
                                 'cwd': '.'})[0] == 'deny'


# ------------------------------------------------------------------ o ato pela rota generica da tela
def _servidor(job, bib, teste=False):
    from desdobra.tela import atos as ta
    from desdobra.tela import estado as te
    from desdobra.tela import servidor as ts
    conteudo = te.montar(job, biblioteca=str(bib))
    return conteudo, ts.ServidorTela(conteudo, pasta=job, modo_teste=teste,
                                     atos=ta.atos_do_job(job, conteudo=conteudo)).iniciar()


def test_ato_da_tela_registra_com_a_confirmacao_na_janela(job, bib, monkeypatch):
    from desdobra.marca import perfil
    monkeypatch.setattr(humano, 'ambiente_da_tela', lambda: (True, None))
    conteudo, s = _servidor(job, bib[0])
    try:
        registro = conteudo['estado']['lido']['marca']['registro']
        assert registro['pode'] is True
        biscoito = tts._entrar(s)
        # o pedido com o conteudo que a janela nao mostra e recusado antes do dialogo
        assert tte._pedir_ato(s, biscoito, nome='marca_registrar', dados={'impressao': '0' * 64})[0] == 403
        assert tte._pedir_ato(s, biscoito, nome='marca_registrar', dados={})[0] == 403
        codigo, p = tte._pedir_ato(s, biscoito, nome='marca_registrar', dados={'impressao': registro['impressao']})
        assert codigo == 200, codigo
        assert MARCA in p['texto'] and 'versão 1' in p['texto']
        assert (p['sim'], p['nao']) == ('Guardar o padrão', 'Cancelar')
        for proibido in (str(bib[0]), bib[1], '—', '–', '.ttf'):
            assert proibido not in json.dumps(p, ensure_ascii=False)
        assert perfil.ler(bib[0], bib[1])['versao'] == 0  # nada gravado antes do Confirmar
        c2, _cab, corpo = tte._escrever(s, '/api/ato/confirmar', {'pedido': p['pedido'], 'resposta': 'confirmar'},
                                        cookie=biscoito)
        assert c2 == 200 and json.loads(corpo) == {'versao': 1, 'criou': True}
        assert perfil.ler(bib[0], bib[1])['versao'] == 1
        # a tela recarregada diz que o padrao esta guardado, e o mesmo pedido nao passa de novo
        assert conteudo['recarregar']()['lido']['marca']['registro']['guardado'] is True
        assert tte._pedir_ato(s, biscoito, nome='marca_registrar', dados={'impressao': registro['impressao']})[0] == 403
    finally:
        s.parar()


def test_segundo_job_da_marca_mostra_o_padrao_registrado(job, bib, tela, tmp_path):
    """M4 depois do M5: o segundo job da mesma marca abre com o padrao citado, versao 1, do job 1."""
    from desdobra.tela import funcoes as tf
    reg = _registrar()
    imp = reg.na_tela(job, bib[0])['impressao']
    reg.gravar(job, disparo=_disparo(tela), biblioteca=bib[0], impressao=imp)
    segundo = tmp_path / 'segundo'
    (segundo / 'briefing').mkdir(parents=True)
    shutil.copy(job / 'estado.json', segundo / 'estado.json')
    _marca_do_job(segundo, bib[1])
    p = tf.padrao_da_marca(segundo, bib[0])
    jid = _job_id(job)
    v = reg.na_tela(job, bib[0])
    assert p['versao'] == 1
    assert set(p['funcoes']) == {r['funcao'] for r in v['regras']} | {a['funcao'] for a in v['ancoras']}
    titulo = p['funcoes']['titulo']
    assert titulo['regra']['ref'] == 'marca:%s@v1#job:%s' % (bib[1], jid)
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    assert titulo['regra']['valor'] == next(r['regra']['valor'] for r in b['regras_escala'] if r['funcao'] == 'titulo')
    assert copy.deepcopy(p) == p


# ------------------------------------------------------------------ M7c, ajuste nome: o nome do job de origem
# Resposta do Duda ao ponto 3 (13/11): a tela mostra o nome do job de origem, e nao o id curto. O nome do job e o da
# pasta que o DA deu ao job na criacao (o estado.json so tem o id). O ref e a conferencia continuam pelo id.
NOME_DO_JOB = 'Campanha Sintetica Verao'
NOME_ANTERIOR = 'Campanha Sintetica Antiga'


@pytest.fixture
def job_nomeado(job, tmp_path):
    """O job aprovado numa pasta com o nome que o DA deu ao job."""
    destino = tmp_path / NOME_DO_JOB
    shutil.move(str(job), str(destino))
    return destino


def _campanha_anterior(nome=NOME_ANTERIOR):
    camp = {'job': JOB_ANTERIOR, 'data': '2026-11-01', 'formatos': [{'formato': 'f1', 'aprovacao_sha256': 'e' * 64}],
            'confirmado_por': {'usuario': 'da', 'maquina': 'estacao'}, 'origem': 'da', 'meio': 'tela'}
    if nome is not None:
        camp['job_nome'] = nome
    return camp


def test_nome_do_job_e_o_nome_da_pasta(job_nomeado, tmp_path):
    reg = _registrar()
    assert reg.nome_do_job(job_nomeado) == NOME_DO_JOB
    # a pasta com nome fora do contrato do perfil (aqui, com extensao de fonte) fica sem nome: a tela usa o id curto
    estranho = tmp_path / 'Campanha.otf'
    estranho.mkdir()
    assert reg.nome_do_job(estranho) is None


def test_a_janela_mostra_o_nome_do_job_deste_e_do_job_mantido(job_nomeado, bib):
    from desdobra.marca import perfil
    perfil.nova_versao(bib[0], bib[1], campanha=_campanha_anterior(), quando='2026-11-01T10:00:00-03:00',
                       regras_escala=[{'funcao': 'destaque_numerico', 'regra': 'largura', 'job_origem': JOB_ANTERIOR,
                                       'job_origem_nome': NOME_ANTERIOR}],
                       ancoras=[], faces=[{'postscript': 'Antiga-Regular'}])
    v = _registrar().na_tela(job_nomeado, bib[0])
    assert v['pode'] is True, v
    mantida = next(r for r in v['regras'] if r['funcao'] == 'destaque_numerico')
    assert (mantida['job'], mantida['job_nome'], mantida['desta_campanha']) == (JOB_ANTERIOR[:8], NOME_ANTERIOR, False)
    deste = [i for i in v['regras'] + v['ancoras'] if i['desta_campanha']]
    assert deste and {i['job_nome'] for i in deste} == {NOME_DO_JOB}
    # nada de caminho: so o nome da pasta
    texto = json.dumps(v, ensure_ascii=False)
    for proibido in (str(bib[0]), str(job_nomeado), bib[1], '\\\\', '/'):
        assert proibido not in texto, proibido


def test_mantida_sem_nome_cai_no_nome_da_campanha_do_job(job_nomeado, bib):
    """A regra mantida gravada sem o nome (perfil de antes do ajuste) mostra o nome que uma campanha do mesmo job
    registrou depois; sem nenhum, a tela cai no id curto."""
    from desdobra.marca import perfil
    perfil.nova_versao(bib[0], bib[1], campanha=_campanha_anterior(), quando='2026-11-01T10:00:00-03:00',
                       regras_escala=[{'funcao': 'destaque_numerico', 'regra': 'largura', 'job_origem': JOB_ANTERIOR}],
                       ancoras=[], faces=[])
    v = _registrar().na_tela(job_nomeado, bib[0])
    assert next(r for r in v['regras'] if r['funcao'] == 'destaque_numerico')['job_nome'] == NOME_ANTERIOR


def test_registrar_grava_o_nome_do_job_ao_lado_do_id(job_nomeado, bib, tela):
    from desdobra.marca import perfil
    reg = _registrar()
    perfil.nova_versao(bib[0], bib[1], campanha=_campanha_anterior(), quando='2026-11-01T10:00:00-03:00',
                       regras_escala=[{'funcao': 'destaque_numerico', 'regra': 'largura', 'job_origem': JOB_ANTERIOR}],
                       ancoras=[], faces=[])
    v1 = perfil.ler(bib[0], bib[1])['atual']
    v = reg.na_tela(job_nomeado, bib[0])
    assert reg.gravar(job_nomeado, disparo=_disparo(tela), biblioteca=bib[0], impressao=v['impressao'])['versao'] == 2
    p = perfil.ler(bib[0], bib[1])
    atual = p['atual']
    jid = _job_id(job_nomeado)
    assert atual['campanha']['job'] == jid and atual['campanha']['job_nome'] == NOME_DO_JOB
    for item in atual['regras_escala'] + atual['ancoras']:
        if item['job_origem'] == jid:
            assert item['job_origem_nome'] == NOME_DO_JOB, item
    # a regra mantida, gravada sem nome, fica como estava (o nome dela sai da campanha do job, na leitura)
    mantida = next(r for r in atual['regras_escala'] if r['funcao'] == 'destaque_numerico')
    assert mantida == {'funcao': 'destaque_numerico', 'regra': 'largura', 'job_origem': JOB_ANTERIOR}
    assert arquivos.para_json(p['historico'][0]) == arquivos.para_json(v1)
    # o ref continua pelo id
    from desdobra.tela import funcoes as tf
    assert tf.FORMA_DO_REF.pattern.endswith('#job:([0-9a-f]{8,64})$')
    # o nome do job nao vai ao log do job
    log = (job_nomeado / 'log' / 'eventos.jsonl').read_text(encoding='utf-8')
    assert NOME_DO_JOB not in log and 'Verao' not in log


def test_perfil_antigo_sem_nome_continua_guardado(job_nomeado, bib, tela, monkeypatch):
    """O job registrado antes do ajuste (perfil sem o nome) continua guardado: o nome que a tela tem agora nao vira
    versao nova, e a janela ja mostra o nome."""
    from desdobra.marca import perfil
    reg = _registrar()
    original = reg.nome_do_job
    monkeypatch.setattr(reg, 'nome_do_job', lambda pasta: None)  # como antes do ajuste
    imp = reg.na_tela(job_nomeado, bib[0])['impressao']
    reg.gravar(job_nomeado, disparo=_disparo(tela), biblioteca=bib[0], impressao=imp)
    atual = perfil.ler(bib[0], bib[1])['atual']
    assert 'job_nome' not in atual['campanha']
    assert all('job_origem_nome' not in i for i in atual['regras_escala'] + atual['ancoras'])
    monkeypatch.setattr(reg, 'nome_do_job', original)
    arq = bib[0] / 'marcas' / bib[1] / 'perfil-marca.json'
    antes = arq.read_bytes()
    v = reg.na_tela(job_nomeado, bib[0])
    assert (v['pode'], v['guardado'], v['motivo']) == (False, True, 'ja_guardado'), v
    assert {i['job_nome'] for i in v['regras'] + v['ancoras']} == {NOME_DO_JOB}
    assert arq.read_bytes() == antes


def test_job_renomeado_aparece_com_um_nome_so_na_janela(job_nomeado, bib):
    """Revisao do ajuste nome: o job anterior registrou com a pasta 'Velha', a pasta foi renomeada e o mesmo job
    registrou de novo como 'Nova', mantendo a regra decidida antes (que guarda 'Velha'). A janela mostra o job anterior
    com um nome so, o da campanha mais recente dele."""
    from desdobra.marca import perfil
    velho, novo = 'Pasta Sintetica Velha', 'Pasta Sintetica Nova'
    perfil.nova_versao(bib[0], bib[1], campanha=_campanha_anterior(velho), quando='2026-11-01T10:00:00-03:00',
                       regras_escala=[{'funcao': 'destaque_numerico', 'regra': 'largura', 'job_origem': JOB_ANTERIOR,
                                       'job_origem_nome': velho}], ancoras=[], faces=[])
    camp = dict(_campanha_anterior(novo), formatos=[{'formato': 'f1', 'aprovacao_sha256': 'f' * 64}])
    _, criou = perfil.nova_versao(
        bib[0], bib[1], campanha=camp, quando='2026-11-02T10:00:00-03:00',
        regras_escala=[{'funcao': 'destaque_numerico', 'regra': 'largura', 'job_origem': JOB_ANTERIOR,
                        'job_origem_nome': velho}],
        ancoras=[{'funcao': 'destaque_numerico', 'x': 'centro', 'y': 'topo', 'job_origem': JOB_ANTERIOR,
                  'job_origem_nome': novo}], faces=[])
    assert criou
    v = _registrar().na_tela(job_nomeado, bib[0])
    do_anterior = [i for i in v['regras'] + v['ancoras'] if i['job'] == JOB_ANTERIOR[:8]]
    assert do_anterior and {i['job_nome'] for i in do_anterior} == {novo}, do_anterior


def test_pasta_com_nome_que_nao_vira_utf8_cai_no_id_curto(job, tmp_path, bib):
    """Revisao do ajuste nome: o NTFS aceita na pasta metade de um par UTF-16. O nome fica de fora (None), a janela
    cai no id curto e o registro continua possivel, como antes do ajuste."""
    destino = tmp_path / 'Campanha \ud800 Sintetica'
    try:
        shutil.move(str(job), str(destino))
    except (OSError, UnicodeError):
        pytest.skip('o sistema de arquivos desta maquina nao aceita o nome')
    reg = _registrar()
    assert reg.nome_do_job(destino) is None
    v = reg.na_tela(destino, bib[0])
    assert v['pode'] is True and v.get('motivo') != 'perfil_ilegivel', v
    assert all(i['job_nome'] is None for i in v['regras'] + v['ancoras'] if i['desta_campanha'])


def test_o_nome_do_job_do_perfil_nao_vai_ao_envelope_do_claude(job_nomeado, bib, tela, capsys):
    """O envelope que vai ao Claude (o do job estado) nao leva o nome de job que o perfil guarda (o Claude so conhece a
    pasta do job que ele mesmo passou ao motor)."""
    from desdobra import cli
    from desdobra.marca import perfil
    perfil.nova_versao(bib[0], bib[1], campanha=_campanha_anterior(), quando='2026-11-01T10:00:00-03:00',
                       regras_escala=[{'funcao': 'destaque_numerico', 'regra': 'largura', 'job_origem': JOB_ANTERIOR,
                                       'job_origem_nome': NOME_ANTERIOR}], ancoras=[], faces=[])
    reg = _registrar()
    reg.gravar(job_nomeado, disparo=_disparo(tela), biblioteca=bib[0],
               impressao=reg.na_tela(job_nomeado, bib[0])['impressao'])
    capsys.readouterr()
    cli.principal(['--envelope', 'job', 'estado', str(job_nomeado)])
    saida = capsys.readouterr().out
    assert json.loads(saida)['contagens']['marca_escolhida'] == 1
    assert NOME_ANTERIOR not in saida and 'Antiga' not in saida


# ------------------------------------------------------------------ a pagina no Chromium sem janela
JS_FAIXA = '() => document.getElementById("registro-marca").hidden'
JS_BOTAO = '() => document.getElementById("registro-guardar").hidden'


def _abrir_formatos(pw, srv, largura, altura):
    import test_tela_palco as tp
    from desdobra.chromium import navegador
    nav = pw.chromium.launch(headless=True, args=list(navegador.ARGUMENTOS))
    pg = nav.new_context(viewport={'width': largura, 'height': altura}, device_scale_factor=1).new_page()
    try:
        pg.goto(srv.url_entrada, wait_until='commit')
    except Exception:  # noqa: BLE001 - o 204 nao completa a navegacao
        pass
    pg.goto(srv.url_pagina, wait_until='load')
    tp._esperar(pg, tp.JS_PRONTO)
    pg.evaluate('() => document.querySelector("#passos [data-passo=formatos]").click()')
    tp._esperar(pg, '() => document.documentElement.dataset.painel === "pronto" ? "1" : ""')
    return nav, pg


def _fotos(pg, capturas, nome, telas):
    if capturas is None:
        return
    atual = pg.viewport_size
    for w, h in telas:
        pg.set_viewport_size({'width': w, 'height': h})
        pg.wait_for_timeout(450)  # numero-neutro: as entradas da faixa e da janela terminam (0,3 s)
        pg.screenshot(path=str(capturas / ('%s-%dx%d.png' % (nome, w, h))))
    pg.set_viewport_size(atual)


def test_botao_escondido_antes_de_todas_as_aprovacoes_no_chromium(renderizado, bib, tmp_path, monkeypatch,
                                                                  capturas=None, telas=((1600, 900),)):
    from playwright.sync_api import sync_playwright

    from desdobra.chromium import navegador
    copia = tmp_path / 'sem-aprovacao'
    shutil.copytree(renderizado, copia)
    _marca_do_job(copia, bib[1])
    monkeypatch.setattr(humano, 'ambiente_da_tela', lambda: (True, None))
    navegador.apontar_playwright()
    _conteudo, s = _servidor(copia, bib[0])
    try:
        with sync_playwright() as pw:
            nav, pg = _abrir_formatos(pw, s, *telas[0])
            try:
                assert pg.evaluate(JS_FAIXA) is True and pg.evaluate(JS_BOTAO) is True
                _fotos(pg, capturas, 'm5-1-botao-escondido', telas)
            finally:
                nav.close()
    finally:
        s.parar()


def test_registrar_no_chromium_com_a_janela_e_depois(job, bib, monkeypatch, capturas=None, telas=((1600, 900),)):
    """A faixa com o botao, a janela com o que vai ao perfil (sem caminho, sem arquivo de fonte, sem travessao), o
    Confirmar e a faixa de padrao guardado."""
    from playwright.sync_api import sync_playwright

    import test_tela_palco as tp
    from desdobra.chromium import navegador
    from desdobra.marca import perfil
    monkeypatch.setattr(humano, 'ambiente_da_tela', lambda: (True, None))
    navegador.apontar_playwright()
    _conteudo, s = _servidor(job, bib[0])
    try:
        with sync_playwright() as pw:
            nav, pg = _abrir_formatos(pw, s, *telas[0])
            try:
                assert pg.evaluate(JS_FAIXA) is False and pg.evaluate(JS_BOTAO) is False
                faixa = pg.evaluate('() => document.getElementById("registro-marca").innerText')
                assert MARCA in faixa and 'A campanha foi aprovada' in faixa
                _fotos(pg, capturas, 'm5-2-botao', telas)
                pg.evaluate('() => document.getElementById("registro-guardar").click()')
                tp._esperar(pg, '() => document.getElementById("confirmacao").open ? "1" : ""')
                assert pg.evaluate('() => document.activeElement.tagName') != 'BUTTON'
                janela = pg.evaluate('() => document.getElementById("confirmacao").innerText')
                assert 'Regras de escala' in janela and 'Âncoras' in janela and rap.FONTE in janela
                assert 'deste job' in janela and 'versão 1' in janela and MARCA in janela
                for proibido in (str(bib[0]), bib[1], '.ttf', '—', '–', 'marca:', 'padrao_marca'):
                    assert proibido not in janela, proibido
                assert perfil.ler(bib[0], bib[1])['versao'] == 0  # a janela aberta nao grava nada
                _fotos(pg, capturas, 'm5-3-janela', telas)
                pg.evaluate('''() => Array.from(document.querySelectorAll("#confirmacao button"))
                    .find(b => b.textContent === "Guardar o padrão").click()''')
                tp._esperar(pg, '() => document.documentElement.dataset.estadoAto === "feito" ? "1" : ""')
                assert perfil.ler(bib[0], bib[1])['versao'] == 1
                assert pg.evaluate(JS_FAIXA) is False and pg.evaluate(JS_BOTAO) is True
                depois = pg.evaluate('() => document.getElementById("registro-marca").innerText')
                assert 'Padrão guardado' in depois and 'versão 1' in depois
                _fotos(pg, capturas, 'm5-4-guardado', telas)
            finally:
                nav.close()
    finally:
        s.parar()


def test_janela_do_registro_mostra_o_nome_do_job_no_chromium(job_nomeado, bib, monkeypatch, capturas=None,
                                                             telas=((1600, 900),)):
    """Ajuste nome: a janela diz "do job <nome>, mantida" na regra que veio de outra campanha, com o nome que o perfil
    guarda; o id curto so aparece quando o perfil nao tem o nome."""
    from playwright.sync_api import sync_playwright

    import test_tela_palco as tp
    from desdobra.chromium import navegador
    from desdobra.marca import perfil
    perfil.nova_versao(bib[0], bib[1], campanha=_campanha_anterior(), quando='2026-11-01T10:00:00-03:00',
                       regras_escala=[{'funcao': 'destaque_numerico', 'regra': 'largura', 'job_origem': JOB_ANTERIOR,
                                       'job_origem_nome': NOME_ANTERIOR}],
                       ancoras=[{'funcao': 'selo', 'x': 'direita', 'y': 'topo', 'job_origem': JOB_ANTERIOR}],
                       faces=[])
    monkeypatch.setattr(humano, 'ambiente_da_tela', lambda: (True, None))
    navegador.apontar_playwright()
    _conteudo, s = _servidor(job_nomeado, bib[0])
    try:
        with sync_playwright() as pw:
            nav, pg = _abrir_formatos(pw, s, *telas[0])
            try:
                pg.evaluate('() => document.getElementById("registro-guardar").click()')
                tp._esperar(pg, '() => document.getElementById("confirmacao").open ? "1" : ""')
                janela = pg.evaluate('() => document.getElementById("confirmacao").innerText')
                assert 'do job %s, mantida' % NOME_ANTERIOR in janela, janela
                assert JOB_ANTERIOR[:8] not in janela
                assert 'deste job' in janela
                _fotos(pg, capturas, 'nome-1-janela', telas)
            finally:
                nav.close()
    finally:
        s.parar()
