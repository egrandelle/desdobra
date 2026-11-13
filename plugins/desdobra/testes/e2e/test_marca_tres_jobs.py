# -*- coding: utf-8 -*-
"""M7c, E2: roteiro da marca com tres jobs (plano do M7c, E2 e secao 4; arquitetura-v1.md, 4.14, 5.3, 5.7 e 9.8;
decisoes-v1.md, 162 e 190, Q1, Q2 e Q3).

Uma marca sintetica numa biblioteca da agencia em pasta temporaria e tres jobs do mesmo PSD sintetico
(test_derivacao_apoio.psd_derivacao), cada um com o seu id:
  - job 1: a marca escolhida pelo DA (briefing/marca.json com origem da e meio tela), o briefing do DA gravado como a
    tela grava (com a entrada no indice encadeado), derivacao, render e a aprovacao de todos os formatos pela tela
    (Disparo da tela, origem da); o registro pelo ato "marca registrar" da tela (pedir e confirmar na janela): o
    perfil vai para a versao 1;
  - job 2 da mesma marca: o padrao aparece citado, com a versao e o job de origem, e nenhum campo do Design system
    preenchido; o DA usa o padrao (o clique de "Usar o padrao" no rascunho) em todas as funcoes do perfil menos uma,
    que ele escolhe a mao com o mesmo valor; o briefing grava a origem padrao_marca com o ref so nas clicadas;
  - job 3 da mesma marca: o DA usa o padrao, muda a regra de uma funcao, aprova e registra: versao 2, com o job 3 de
    origem so dessa regra, o job 1 nas outras e a versao 1 igual byte a byte no historico;
  - caso negativo: a copia do job 3 com a aprovacao do modo de teste da tela (origem fixture_de_teste) nao registra;
  - a pasta de dados do plugin (CLAUDE_PLUGIN_DATA deste teste, pasta temporaria) e apagada e a biblioteca reaberta:
    o perfil continua la, e 0 arquivo com nome ou assinatura de fonte em marcas/.
As medicoes da secao 4 do plano para a marca saem na saida do pytest e, quando a variavel de ambiente
DESDOBRA_MEDICAO_MARCA_TRES_JOBS existe, num arquivo JSON fora do repositorio.

Tudo sintetico: o PSD, a fonte inventada e a marca sao gerados na hora; nenhum arquivo de cliente e lido."""
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

import test_derivacao_apoio as ap
import test_fontes_apoio as fap
import test_marca_registrar as tmr
import test_render_apoio as rap
import test_tela_escrita as tte
import test_tela_funcoes as ttf
import test_tela_salvar as tsv
import test_tela_servidor as tts
from desdobra import arquivos, biblioteca, contratos, humano
from desdobra.briefing import modelo as mb
from desdobra.briefing import salvar as bs
from desdobra.entrega import aprovacao, codificar, nucleo_aprovar
from desdobra.job import nucleo
from desdobra.render import execucao
from desdobra.tela import estado as te
from desdobra.tela import funcoes as tf
from desdobra.tela import rascunho as tr

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')

VARIAVEL_MEDICAO = 'DESDOBRA_MEDICAO_MARCA_TRES_JOBS'
MARCA = 'Marca Sintetica Tres Jobs'
FORMATOS = tmr.FORMATOS
IDS = tmr.IDS
FUNCAO_A_MAO = 'fundo'  # no job 2, a funcao que o DA escolhe a mao, com o mesmo valor do padrao, sem o clique
FUNCAO_MUDADA = 'titulo'  # no job 3, a funcao cuja regra o DA muda depois de usar o padrao
REGRA_NOVA = 'lado_curto'


# ------------------------------------------------------------------ ajudantes
def _job_id(job):
    return contratos.ler(Path(job) / 'estado.json', 'estado/1')['job_id']


def _criar_job(base, nome, fontes, marca_id):
    """O job sintetico com o briefing de teste importado e a marca escolhida pelo DA (como o ato da tela grava)."""
    job = base / nome
    nucleo.criar(job, ap.psd_derivacao(base / ('origem-%s' % nome) / 'kv.psd'), 'c', fontes=[fontes])
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    b, _ids = ap.briefing_do_job(laudo, FORMATOS)
    arq = base / ('fixture-%s.json' % nome)
    arq.write_text(json.dumps(b), encoding='utf-8')
    mb.importar_teste(job, arq)
    tmr._marca_do_job(job, marca_id)
    return job, laudo


def _briefing_do_da(job):
    """O briefing de teste com toda decisao, o cabecalho e as composicoes do DA (o que o gravador da tela grava)."""
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    tmr._origens_do_da(b)
    b['cabecalho'].update(origem='da', meio='tela')
    b['composicoes'] = [{'familia': 'familia-%s' % f['id'], 'formatos': [f['id']], 'versao': None, 'edicoes': [],
                         'confirmada': True, 'confirmacao': {'origem': 'da', 'meio': 'tela', 'em': '2026-11-13T10:00:00'}}
                        for f in b['formatos']]
    return b


def _design_do_briefing(b):
    """O Design system do rascunho com os valores do briefing (o que o DA escolhe a mao, sem origem de padrao)."""
    design = {}
    for r in b['regras_escala']:
        design.setdefault(r['funcao'], {})['regra'] = r['regra']['valor']
    for a in b['ancoras']:
        if 'funcao' in a:
            design.setdefault(a['funcao'], {}).update(x=a['x']['valor'], y=a['y']['valor'])
    return design


def _funcoes_do_rascunho(b):
    return {str(f['layer_id']): {'funcao': f['funcao']['valor'], 'observacao': f.get('observacao')}
            for f in b['funcoes']}


def _usar_o_padrao(job, conteudo, b, padrao, clicadas, mudar=None):
    """O que o "Salvar e seguir" leva ao briefing depois do clique em "Usar o padrao" nas funcoes clicadas: o rascunho
    com o Design system (o clique poe o valor e a origem padrao_marca com o ref) passa pelo gravador real
    (briefing.salvar.montar, com o conteudo da tela do job e o Disparo da tela, origem da), que decide a origem de cada
    regra e ancora. mudar: {funcao: regra} que o DA troca depois do clique (a pagina tira so a origem da regra).
    Devolve (b, dados), com as regras e as ancoras por funcao do briefing b trocadas pelas do gravador."""
    design = _design_do_briefing(b)
    design.update(ttf.design_do_padrao(padrao, *clicadas))
    for f, regra in (mudar or {}).items():
        design[f]['regra'] = regra
        del design[f]['origem']['regra']
    dados = dict(ttf._rascunho_minimo(), funcoes=_funcoes_do_rascunho(b), design=design)
    contratos.validar(dados, tr.ESQUEMA)
    montado = bs.montar(job, conteudo, dados, origem=bs.ORIGEM_DA, meio='tela', por={'usuario': None, 'maquina': None},
                        quando=mb.agora(), modo=None)
    assert [r['funcao'] for r in montado['regras_escala']] == sorted(design)
    b['regras_escala'] = montado['regras_escala']
    b['ancoras'] = [a for a in montado['ancoras'] if 'funcao' in a] + [a for a in b['ancoras'] if 'layer_id' in a]
    return b, dados


def _renderizar_e_aprovar(job, sessao):
    """Derivacao, render dos formatos e a aprovacao de todos pela tela do DA (o nucleo do aprovar, Disparo da tela)."""
    from desdobra.derivacao import nucleo as nd
    nd.derivar(job)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(humano, 'console_interativo', lambda: (True, None))
        for fid in IDS:
            execucao.renderizar(job, disparo=humano.exigir('render'), formato=fid)
    _aprovar(job, sessao)


def _aprovar(job, sessao):
    with nucleo.Trava(job):
        conf = nucleo_aprovar.conferir(job, IDS)
        assert not nucleo_aprovar.com_falha(conf)
        d = humano.exigir_tela('aprovar', sessao, confirmado=True)
        nucleo_aprovar.confirmar(job, IDS, nucleo_aprovar.vista(conf), d)


def _registrar_pela_tela(job, bib, impressao=None):
    """O ato "marca registrar" pela rota generica da tela: pedir (a janela) e confirmar. impressao: a do pedido, quando
    a janela nao mostra nenhuma (o caso negativo); senao, a da janela. Devolve (codigo, resposta)."""
    _conteudo, s = tmr._servidor(job, bib)
    try:
        registro = _conteudo['estado']['lido']['marca']['registro']
        biscoito = tts._entrar(s)
        codigo, p = tte._pedir_ato(s, biscoito, nome='marca_registrar',
                                   dados={'impressao': registro.get('impressao') or impressao or '0' * 64})
        if codigo != 200:
            return codigo, registro
        c2, _cab, corpo = tte._escrever(s, '/api/ato/confirmar', {'pedido': p['pedido'], 'resposta': 'confirmar'},
                                        cookie=biscoito)
        return c2, json.loads(corpo)
    finally:
        s.parar()


def _itens_do_perfil(v):
    """(tipo, funcao, valor) de cada regra e ancora de uma versao do perfil."""
    return ([('regra', r['funcao'], r['regra']) for r in v['regras_escala']] +
            [('ancora', a['funcao'], (a['x'], a['y'])) for a in v['ancoras']])


def _arquivos_de_fonte(pasta):
    """Os arquivos com nome ou assinatura de fonte (desdobra.arquivos) dentro da pasta."""
    achados = []
    for p in Path(pasta).rglob('*'):
        if p.is_file():
            with open(p, 'rb') as f:
                inicio = f.read(arquivos.BYTES_ASSINATURA)
            if arquivos.eh_nome_de_fonte(p.name) or arquivos.assinatura_de_fonte(inicio):
                achados.append(p.name)
    return achados


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    """A pasta de dados do plugin deste teste (CLAUDE_PLUGIN_DATA), fora da biblioteca, o encoder de teste e a tela
    do DA (o processo de teste nao tem as marcas do Claude)."""
    dados = tmp_path / 'dados-do-plugin'
    (dados / 'venv').mkdir(parents=True)
    (dados / 'interpretador.json').write_text('{}', encoding='utf-8')
    monkeypatch.setenv('CLAUDE_PLUGIN_DATA', str(dados))
    monkeypatch.setattr(biblioteca, '_dados_padrao', lambda: Path(os.environ['CLAUDE_PLUGIN_DATA']))
    monkeypatch.setattr(codificar, 'arquivo_final', tmr._encoder_de_teste())
    monkeypatch.setattr(codificar, 'parametros_sem_o_master',
                        lambda pasta, formato, **_k: {'tipo': 'png', 'qualidade': 90})
    monkeypatch.setattr(humano, 'ambiente_da_tela', lambda: (True, None))
    sessao = humano.abrir_sessao_tela(teste=False)
    yield {'dados': dados, 'sessao': sessao}
    humano.fechar_sessao_tela(sessao)


# ------------------------------------------------------------------ o roteiro
def test_roteiro_da_marca_com_tres_jobs(tmp_path, ambiente):
    from desdobra.marca import perfil
    from desdobra.marca import registrar as reg
    medicao = {}
    sessao = ambiente['sessao']
    fontes = tmp_path / 'origem-fontes'
    fap.gravar(fontes, 'inventada.ttf', fap.fonte(ps=rap.FONTE))
    bib = tmp_path / 'biblioteca-da-agencia'
    bib.mkdir()
    assert biblioteca.conferir(str(bib)).situacao == 'ok'
    # a biblioteca nunca fica na pasta de dados do plugin, que some na desinstalacao
    assert biblioteca.conferir(str(ambiente['dados'])).situacao == 'dentro_dos_dados'
    marca_id = perfil.criar(bib, MARCA)['id']
    arq_perfil = perfil.caminho(bib, marca_id)

    # ---------------------------------------------------------------- job 1: registro da primeira campanha
    job1, _laudo1 = _criar_job(tmp_path, 'job-1', fontes, marca_id)
    j1 = _job_id(job1)
    assert tf.padrao_da_marca(job1, bib) is None  # versao 0: nada a citar ainda
    b1 = _briefing_do_da(job1)
    tmr._gravar_briefing_do_da(job1, b1)
    _renderizar_e_aprovar(job1, sessao)
    aprov1 = contratos.ler(job1 / aprovacao.ARQUIVO, aprovacao.ESQUEMA)
    assert {(r['aprovado_por']['origem'], r['aprovado_por']['meio']) for r in aprov1['formatos'].values()} == \
        {('da', 'tela')} and set(aprov1['formatos']) == set(IDS)
    assert reg.na_tela(job1, bib)['pode'] is True
    codigo, resp = _registrar_pela_tela(job1, bib)
    assert (codigo, resp) == (200, {'versao': 1, 'criou': True})
    p1 = perfil.ler(bib, marca_id)
    v1 = p1['atual']
    assert p1['versao'] == 1 and v1['job_origem'] == j1 and v1['campanha']['job'] == j1
    itens_v1 = _itens_do_perfil(v1)
    assert itens_v1 and all(i['job_origem'] == j1 for i in v1['regras_escala'] + v1['ancoras'])
    funcoes_v1 = sorted({f for _t, f, _v in itens_v1})
    assert FUNCAO_A_MAO in funcoes_v1 and FUNCAO_MUDADA in funcoes_v1
    # ajuste nome: o nome do job (o da pasta que o DA deu) fica ao lado do id, na campanha e em cada regra e ancora
    assert v1['campanha']['job_nome'] == job1.name
    assert {i['job_origem_nome'] for i in v1['regras_escala'] + v1['ancoras']} == {job1.name}
    bytes_v1 = arquivos.para_json(v1)

    # ---------------------------------------------------------------- job 2: o padrao citado, 0 campo preenchido
    job2, laudo2 = _criar_job(tmp_path, 'job-2', fontes, marca_id)
    conteudo2 = te.montar(job2, biblioteca=str(bib))
    padrao2 = tsv._marca_na_tela(conteudo2)['padrao']
    assert padrao2 == tf.padrao_da_marca(job2, bib) and padrao2['versao'] == 1
    ref_j1 = tf.ref_do_padrao(marca_id, 1, j1)
    citadas = 0
    for tipo, f, valor in itens_v1:
        cit = (padrao2['funcoes'].get(f) or {}).get(tipo)
        if cit is None:
            continue
        mostrado = cit['valor'] if tipo == 'regra' else (cit['x'], cit['y'])
        citadas += int(mostrado == valor and cit['ref'] == ref_j1 and cit['job'] == j1)
    medicao['citadas'] = (citadas, len(itens_v1))
    assert citadas == len(itens_v1)  # meta: 100%
    # ajuste nome: o padrao citado no job 2 leva o nome do job 1, e o ref continua pelo id
    nomes_citados = {x['job_nome'] for c in padrao2['funcoes'].values() for x in c.values() if x}
    medicao['padrao_com_o_nome_do_job'] = nomes_citados == {job1.name}
    assert nomes_citados == {job1.name}
    # nada preenchido antes do clique: a tela nao grava rascunho, e o Design system pede cada funcao do perfil
    assert not (job2 / tr.ARQUIVO).exists()
    sem_clique = {'funcoes': _funcoes_do_rascunho(contratos.ler(job2 / mb.ARQUIVO, 'briefing/1'))}
    pend = tf.pendencias(laudo2, sem_clique)
    usadas = {r['funcao'] for r in v1['regras_escala']} | {a['funcao'] for a in v1['ancoras']}
    faltando = [f for f in usadas if {'tipo': 'regra', 'funcao': f} in pend and {'tipo': 'ancora', 'funcao': f} in pend]
    medicao['preenchidos_antes_do_clique'] = len(usadas) - len(faltando)
    assert sorted(faltando) == sorted(usadas)
    parcial = tf.briefing_parcial(sem_clique)
    assert parcial['regras_escala'] == [] and parcial['ancoras'] == []
    # o DA usa o padrao em todas as funcoes do perfil menos uma, que ele escolhe a mao com o mesmo valor
    clicadas = [f for f in funcoes_v1 if f != FUNCAO_A_MAO]
    b2, _dados2 = _usar_o_padrao(job2, conteudo2, _briefing_do_da(job2), padrao2, clicadas)
    tmr._gravar_briefing_do_da(job2, b2)
    b2 = mb.ler(job2)
    origens = [(r['funcao'], r['regra']['origem']) for r in b2['regras_escala']] + \
        [(a['funcao'], a[e]['origem']) for a in b2['ancoras'] if 'funcao' in a for e in ('x', 'y')]
    do_padrao = {f for f, o in origens if o['tipo'] == 'padrao_marca'}
    assert do_padrao == set(clicadas)
    assert all(o == {'tipo': 'padrao_marca', 'ref': ref_j1} for f, o in origens if f in clicadas)
    sem_clique_gravadas = sum(1 for f, o in origens if o['tipo'] == 'padrao_marca' and f not in clicadas)
    medicao['gravadas_sem_clique'] = sem_clique_gravadas
    assert sem_clique_gravadas == 0
    a_mao = [o for f, o in origens if f == FUNCAO_A_MAO]
    assert a_mao and all(o['tipo'] == 'da' for o in a_mao)  # mesmo valor do padrao, sem o clique: escolha do DA
    assert mb.conferir_para_entrega(job2)[0] is True
    assert tf.padrao_invalido({'design': _dados2['design']}, tf.padrao_da_marca(job2, bib)) == []

    # ---------------------------------------------------------------- job 3: muda uma regra, aprova e registra
    job3, _laudo3 = _criar_job(tmp_path, 'job-3', fontes, marca_id)
    j3 = _job_id(job3)
    assert len({j1, _job_id(job2), j3}) == 3
    padrao3 = tf.padrao_da_marca(job3, bib)
    regra_v1 = padrao3['funcoes'][FUNCAO_MUDADA]['regra']['valor']
    assert regra_v1 != REGRA_NOVA
    b3, _dados3 = _usar_o_padrao(job3, te.montar(job3, biblioteca=str(bib)), _briefing_do_da(job3), padrao3,
                                 funcoes_v1, mudar={FUNCAO_MUDADA: REGRA_NOVA})
    tmr._gravar_briefing_do_da(job3, b3)
    _renderizar_e_aprovar(job3, sessao)
    janela = reg.na_tela(job3, bib)
    assert janela['pode'] is True and (janela['versao_atual'], janela['versao_nova']) == (1, 2), janela
    desta = {('regra', r['funcao']) for r in janela['regras'] if r['desta_campanha']} | \
        {('ancora', a['funcao']) for a in janela['ancoras'] if a['desta_campanha']}
    assert desta == {('regra', FUNCAO_MUDADA)}
    # a janela diz "deste job" na regra mudada e o nome do job 1 nas outras (que vieram do padrao)
    assert {i['job_nome'] for i in janela['regras'] + janela['ancoras'] if not i['desta_campanha']} == {job1.name}
    assert {i['job_nome'] for i in janela['regras'] + janela['ancoras'] if i['desta_campanha']} == {job3.name}

    # ---------------------------------------------------------------- caso negativo: aprovacao do modo de teste
    copia = tmp_path / 'job-3-aprovado-no-teste'
    shutil.copytree(job3, copia)
    teste = humano.abrir_sessao_tela(teste=True)
    try:
        _aprovar(copia, teste)
    finally:
        humano.fechar_sessao_tela(teste)
    aprov_t = contratos.ler(copia / aprovacao.ARQUIVO, aprovacao.ESQUEMA)
    assert {r['aprovado_por']['origem'] for r in aprov_t['formatos'].values()} == {humano.ORIGEM_FIXTURE}
    antes = arq_perfil.read_bytes()
    # a impressao que a janela da copia mostraria se a aprovacao de teste valesse (so ela fica no caminho): o pedido e o
    # gravar levam essa, e a recusa so pode vir da aprovacao de teste, nunca de uma impressao que nao bate
    formatos_t = [{'formato': fid, 'aprovacao_sha256': aprov_t['formatos'][fid]['registro_sha256']}
                  for fid in sorted(aprov_t['formatos'])]
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(reg, '_aprovacoes', lambda _pasta: (formatos_t, None))
        se_valesse = reg.conferir(copia, bib)
    assert se_valesse['pode'] is True, se_valesse['motivo']
    impressao_t = se_valesse['impressao']
    v_teste = reg.na_tela(copia, bib)
    assert v_teste == {'pode': False, 'motivo': 'formato_sem_aprovacao', 'guardado': False}, v_teste
    codigo_t, _r = _registrar_pela_tela(copia, bib, impressao=impressao_t)
    assert codigo_t == 403
    with pytest.raises(reg.ErroRegistro) as recusa:
        reg.gravar(copia, disparo=humano.exigir_tela(reg.COMANDO, sessao, confirmado=True), biblioteca=bib,
                   impressao=impressao_t)
    assert recusa.value.motivo == 'formato_sem_aprovacao'
    registros_de_teste = int(arq_perfil.read_bytes() != antes)
    medicao['registros_com_aprovacao_de_teste'] = registros_de_teste
    assert registros_de_teste == 0 and perfil.ler(bib, marca_id)['versao'] == 1

    # ---------------------------------------------------------------- registro do job 3: versao 2
    codigo, resp = _registrar_pela_tela(job3, bib)
    assert (codigo, resp) == (200, {'versao': 2, 'criou': True})
    p2 = perfil.ler(bib, marca_id)
    v2 = p2['atual']
    assert p2['versao'] == 2 and v2['campanha']['job'] == j3 and v2['job_origem'] == j3
    origem_v2 = {('regra', r['funcao']): r['job_origem'] for r in v2['regras_escala']}
    origem_v2.update({('ancora', a['funcao']): a['job_origem'] for a in v2['ancoras']})
    assert origem_v2[('regra', FUNCAO_MUDADA)] == j3
    assert next(r['regra'] for r in v2['regras_escala'] if r['funcao'] == FUNCAO_MUDADA) == REGRA_NOVA
    assert all(j == j1 for k, j in origem_v2.items() if k != ('regra', FUNCAO_MUDADA))
    assert set(origem_v2) == {(t, f) for t, f, _v in itens_v1}
    assert len(p2['historico']) == 1
    # ajuste nome: na versao 2, cada regra e ancora leva o nome do job de origem dela, e a campanha o do job 3
    assert v2['campanha']['job_nome'] == job3.name
    nomes_v2 = {('regra', r['funcao']): r['job_origem_nome'] for r in v2['regras_escala']}
    nomes_v2.update({('ancora', a['funcao']): a['job_origem_nome'] for a in v2['ancoras']})
    assert nomes_v2 == {k: (job3.name if j == j3 else job1.name) for k, j in origem_v2.items()}
    historico_igual = arquivos.para_json(p2['historico'][0]) == bytes_v1
    medicao['job3'] = {'versao': p2['versao'], 'origem_da_regra_mudada': 'job 3' if origem_v2[('regra', FUNCAO_MUDADA)]
                       == j3 else 'outro', 'versao_1_igual_no_historico': historico_igual}
    assert historico_igual
    bytes_v2 = arq_perfil.read_bytes()

    # ---------------------------------------------------------------- apagar a pasta de dados do plugin e reabrir
    shutil.rmtree(ambiente['dados'])
    assert not ambiente['dados'].exists()
    assert biblioteca.conferir(str(bib)).situacao == 'ok'
    assert perfil.listar(bib) == [{'id': marca_id, 'marca': MARCA}]
    presente = arq_perfil.read_bytes() == bytes_v2 and perfil.ler(bib, marca_id)['versao'] == 2
    medicao['perfil_depois_de_apagar_os_dados'] = presente
    assert presente
    reaberta = te.montar(job3, biblioteca=str(bib))
    marca = tsv._marca_na_tela(reaberta)
    assert marca['padrao']['versao'] == 2
    assert marca['registro']['guardado'] is True and marca['registro']['versao_guardada'] == 2

    # ---------------------------------------------------------------- 0 arquivo de fonte em marcas/
    de_fonte = _arquivos_de_fonte(biblioteca.pasta_marcas(bib))
    medicao['arquivos_de_fonte_em_marcas'] = len(de_fonte)
    assert de_fonte == []
    texto = arq_perfil.read_text(encoding='utf-8')
    # o caminho da pasta das fontes em toda forma que um JSON pode ter: cru, com a barra invertida escapada (Windows)
    # e com a barra normal; e o nome da pasta sozinho
    formas = {str(fontes), json.dumps(str(fontes))[1:-1], fontes.as_posix(), fontes.name}
    assert [f for f in formas if f in texto] == []
    assert 'inventada' not in texto and rap.FONTE in texto
    # o nome do job vai so ao perfil (marcas/**, negado ao Claude pelo gancho): nem o log do job nem o envelope do
    # job estado o levam
    for j in (job1, job3):
        assert j.name not in (j / 'log' / 'eventos.jsonl').read_text(encoding='utf-8')

    print('\n[medicao E2] job 2: %d de %d regras e ancoras do perfil citadas; %d campo preenchido antes do clique; '
          '%d gravada sem clique' % (medicao['citadas'] + (medicao['preenchidos_antes_do_clique'],
                                                          medicao['gravadas_sem_clique'])))
    print('[medicao E2] job 3: versao %(versao)d, regra mudada com origem no %(origem_da_regra_mudada)s, versao 1 igual '
          'byte a byte no historico: %(versao_1_igual_no_historico)s' % medicao['job3'])
    print('[medicao E2] perfil presente depois de apagar a pasta de dados: %s; registros com aprovacao de teste: %d; '
          'arquivos de fonte em marcas/: %d' % (medicao['perfil_depois_de_apagar_os_dados'],
                                                medicao['registros_com_aprovacao_de_teste'],
                                                medicao['arquivos_de_fonte_em_marcas']))
    destino = os.environ.get(VARIAVEL_MEDICAO)
    if destino:
        Path(destino).write_text(json.dumps(medicao, ensure_ascii=False, indent=2), encoding='utf-8')
