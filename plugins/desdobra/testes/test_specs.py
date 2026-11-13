# -*- coding: utf-8 -*-
"""Specs em 4 niveis e validador de arquivo (M3, arquitetura-v1.md 4.8, 5.5 e 9.4), so com folhas sinteticas:
PDF no jeito da PME com as armadilhas, PDF escaneado, HTML no jeito das paginas de midia kit, CSV e e-mail."""
import json
import random
import shutil

import pytest

import test_specs_apoio as apoio
from conftest import escolher_modo_do_da, psd_minimo
from desdobra import cli, contratos, limites
from desdobra.job import fases as mod_fases
from desdobra.job import nucleo
from desdobra.specs import confirmar, extrair, importar, leitura, modelo, validar



def _disparo_spec():
    """Disparo da confirmacao de spec com o console simulado (a conferencia do console tem testes proprios)."""
    from desdobra import humano
    original = humano.console_interativo
    humano.console_interativo = lambda: (True, None)
    try:
        return humano.exigir('spec confirmar')
    finally:
        humano.console_interativo = original

def _job(base, arquivos, modo='b'):
    """Job com as folhas dadas em entrada/specs/ ({caminho relativo: bytes ou texto})."""
    origem = base / 'origem-specs'
    for rel, dados in arquivos.items():
        p = origem / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(dados if isinstance(dados, bytes) else dados.encode('utf-8'))
    (base / 'kv.psd').write_bytes(psd_minimo())
    nucleo.criar(base / 'job', base / 'kv.psd', modo, specs=origem)
    if modo != 'c':
        escolher_modo_do_da(base / 'job', modo)  # a escolha do DA na tela e a fonte do modo (decisoes-v1.md, 170)
    return base / 'job'


def _formato(doc, sufixo_chave):
    achados = [f for f in doc['formatos'] if (f.get('chave') or '').endswith(sufixo_chave)]
    assert len(achados) == 1, [f.get('chave') for f in doc['formatos']]
    return achados[0]


def _valores(doc):
    return [v for _r, _c, v in modelo.todos_os_valores(doc)]


@pytest.fixture(scope='module')
def job_pme(tmp_path_factory):
    base = tmp_path_factory.mktemp('pme')
    job = _job(base, {'pme/folha.pdf': apoio.folha_pme_sintetica()})
    rascunho, formatos, info = importar.importar(job)
    return job, rascunho, formatos, info


@pytest.fixture(scope='module')
def job_globo(tmp_path_factory):
    base = tmp_path_factory.mktemp('globo')
    job = _job(base, {'globo/meia.html': apoio.html_meia_pagina(), 'globo/vertical.html': apoio.html_vertical(),
                      'globo/orientacoes.html': apoio.html_orientacoes()})
    rascunho, _f, _i = importar.importar(job)
    return job, rascunho


# ------------------------------------------------------------------ fixture PME e armadilhas
def test_pme_sintetica_entradas_e_chaves_por_circuito(job_pme):
    _job_, doc, formatos, _info = job_pme
    contratos.validar(doc, 'spec/1')
    assert doc['tipo'] == 'rascunho' and doc['resumo']['formatos'] == 4 and doc['resumo']['formatos_em_px'] == 3
    integral = _formato(doc, 'abrigo-de-onibus-rio-de-janeiro-parana-e-belo-horizonte|1080x1920')
    com_barra = _formato(doc, 'sao-paulo-shopping-exemplo|1080x1920')
    assert integral['chave'] != com_barra['chave']
    assert integral['campos']['area_util']['valor'] == {'largura': 1080, 'altura': 1920}
    assert integral['campos']['faixas']['valor'] == []
    assert com_barra['campos']['area_util']['valor'] == {'largura': 1080, 'altura': 1848}
    assert com_barra['campos']['faixas']['valor'] == [{'lado': 'inferior', 'px': 72}]
    # o valor partido em dois pedacos ("1280px x 720" + "px") volta inteiro
    larga = _formato(doc, 'edificios-comerciais|1280x720')
    assert larga['campos']['area_util']['valor'] == {'largura': 1280, 'altura': 672}
    assert larga['campos']['faixas']['valor'] == [{'lado': 'inferior', 'px': 48}]
    # area util, faixas, area visivel, sangria e margem de seguranca sao campos distintos
    assert {'area_util', 'faixas', 'area_visivel', 'sangria', 'margem_seguranca', 'area_segura'} <= set(larga['campos'])
    assert formatos['formatos'] == []


def test_pme_peso_da_imagem_e_nao_do_video(job_pme):
    doc = job_pme[1]
    for f in doc['formatos']:
        if f['campos']['dimensao']['unidade'] == 'px':
            v = f['campos']['peso_max']
            assert v['valor'] == {'alvo_bytes': 5000000, 'reprova_acima_bytes': 5242880}
            assert v['numeros_literais'] == ['5'] and v['base_unidade'] == 'nao_declarada' and v['forma'] == 'maximo'
            assert v['fonte']['trecho'] != v['fonte']['rotulo_trecho'] and 'rotulo_separado_do_valor' in v['alertas']
            assert f['campos']['tipos_aceitos']['valor'] == ['image/jpeg', 'image/png']


def test_pme_armadilhas_viram_rascunho_ou_registro(job_pme):
    doc = job_pme[1]
    impresso = _formato(doc, '|120x175m')
    dim, util = impresso['campos']['dimensao'], impresso['campos']['area_util']
    assert 'unidade_incoerente' in dim['alertas'] and 'fora_do_escopo_v1' in dim['alertas']
    assert util['valor'] == {'largura': 1.17, 'altura': 1.71} and 'virgula_decimal' in util['alertas']
    assert util['numeros_literais'] == ['1,17', '1,71']
    # rotulo separado do valor: o valor vem de outro trecho, com o alerta
    assert all('rotulo_separado_do_valor' in f['campos']['dimensao']['alertas'] for f in doc['formatos'])
    # praca mista e partida em duas linhas fica no texto do circuito, para o DA (ou o Claude) mapear
    circ = next(c for c in doc['circuitos'] if c['id'].endswith('rio-de-janeiro-parana-e-belo-horizonte'))
    assert circ['texto_original'] == 'Abrigo de Ônibus Rio de Janeiro, Paraná e Belo Horizonte'
    assert circ['campos']['praca']['situacao'] == 'registro' and circ['campos']['praca']['valor'] is None
    restr = next(c for c in doc['circuitos'] if c['id'].endswith('shopping-exemplo'))['restricoes']
    assert [r['valor'] for r in restr] == ['*Não será aceito material animado']
    # 0 valor confirmado sem acao do DA
    assert {v['situacao'] for v in _valores(doc)} <= {'rascunho', 'registro'}
    assert doc['resumo']['valores_confirmados'] == 0


def test_praca_normalizada_sem_inventar_uf():
    lei = extrair.praca('Rio de Janeiro, Paraná e Belo Horizonte')
    assert lei['valor'] == [
        {'uf': 'RJ', 'municipio': None, 'texto_original': 'Rio de Janeiro', 'ambiguidade': 'uf_ou_municipio'},
        {'uf': 'PR', 'municipio': None, 'texto_original': 'Paraná', 'ambiguidade': None},
        {'uf': None, 'municipio': 'Belo Horizonte', 'texto_original': 'Belo Horizonte', 'ambiguidade': None}]
    assert {'praca_mista', 'praca_ambigua', 'uf_nao_declarada'} <= set(lei['alertas'])
    assert extrair.praca('SP')['valor'][0]['uf'] == 'SP'


def test_todo_numero_extraido_existe_no_trecho(job_pme, job_globo, tmp_path):
    job = _job(tmp_path, {'email.txt': apoio.EMAIL,
                          'lista.csv': apoio.csv_do_da(['Formato', 'Peso máximo'], [['1080x1920', '5 MB']])})
    docs = [job_pme[1], job_globo[1], importar.importar(job)[0]]
    n = 0
    for doc in docs:
        assert modelo.conferir_literais(doc) == []
        textos = {(f['id'], t['id']): t['texto'] for f in doc['folhas'] for t in f['trechos']}
        for v in _valores(doc):
            if v['origem'] != 'extraido_do_trecho':
                continue
            alvo = textos[(v['fonte']['folha'], v['fonte']['trecho'])]
            for lit in v['numeros_literais']:
                assert lit in alvo, (v['id'], lit, alvo)
                n += 1
    assert n > 30


# ------------------------------------------------------------------ peso decimal e binario
def test_peso_5mb_alvo_decimal_e_reprovacao_binaria():
    v = extrair.peso('até 5MB')
    assert v['valor'] == {'alvo_bytes': 5000000, 'reprova_acima_bytes': 5242880} and v['base_unidade'] == 'nao_declarada'
    assert extrair.peso('até 5 MiB')['valor'] == {'alvo_bytes': 5242880, 'reprova_acima_bytes': 5242880}
    assert extrair.peso('100', rotulo='peso máximo subload (kb)')['valor'] == {'alvo_bytes': 100000, 'reprova_acima_bytes': 102400}
    assert extrair.numero('1.920') == (None, 'separador_ambiguo')


@pytest.mark.parametrize('n_bytes, esperado', [(5000000, 'ok'), (5000001, 'aviso'), (5242880, 'aviso'),
                                               (5242881, 'reprova')])
def test_validar_peso_nas_duas_leituras(n_bytes, esperado):
    v = {'id': 'x', 'valor': {'alvo_bytes': 5000000, 'reprova_acima_bytes': 5242880}, 'condicao': None,
         'situacao': 'confirmado', 'fonte': None}
    assert validar.conferir_peso('peso_max', v, n_bytes, None)['situacao'] == esperado
    assert limites.efeito('specs.peso_reprova_acima_da_leitura_binaria') == 'reprova'


# ------------------------------------------------------------------ PDF escaneado
def test_pdf_escaneado_so_tem_valor_digitado_ao_lado_do_recorte(tmp_path):
    job = _job(tmp_path, {'jcd/condicoes.pdf': apoio.pdf_escaneado(2)})
    doc = importar.importar(job)[0]
    folha = doc['folhas'][0]
    assert not folha['camada_texto'] and len(folha['recortes']) == 2 and folha['trechos'] == []
    assert all((job / r['arquivo']).is_file() for r in folha['recortes'])
    assert doc['formatos'] == [] and all(v['origem'] == 'ausente' for v in _valores(doc))
    respostas = iter(['dimensao', '1920 x 1080 px', 'peso_max', 'até 2 MB', '', ''])
    novas, doc, formatos, _info = confirmar.sessao(job, disparo=_disparo_spec(), entrada=lambda _p: next(respostas), saida=lambda *_a: None)
    assert len(novas) == 2
    digitados = [v for v in _valores(doc) if v['origem'] == 'digitado_pelo_da_a_partir_do_recorte']
    assert len(digitados) == 2
    assert all(v['fonte']['recorte'] == folha['recortes'][0]['id'] and v['situacao'] == 'confirmado' for v in digitados)
    assert [v for v in _valores(doc) if v['valor'] is not None and v['origem'] != 'digitado_pelo_da_a_partir_do_recorte'] == []
    fmt = formatos['formatos'][0]
    assert fmt['campos']['dimensao']['valor'] == {'largura': 1920, 'altura': 1080}
    assert fmt['campos']['peso_max']['valor']['alvo_bytes'] == 2000000
    acoes = contratos.ler(job / 'specs' / 'confirmacoes.json', 'spec-confirmacoes/1')['acoes']
    assert {a['por'] for a in acoes} == {'da'} and {a['meio'] for a in acoes} == {'terminal'}


# ------------------------------------------------------------------ e-mail, CSV e HTML
def test_email_colado_vira_trechos_com_fonte(tmp_path):
    job = _job(tmp_path, {'estacao/email.txt': apoio.EMAIL})
    doc = importar.importar(job)[0]
    vertical = _formato(doc, '|1080x1920')
    peso = vertical['campos']['peso_max']
    assert peso['valor']['alvo_bytes'] == 2000000 and 'rotulo_separado_do_valor' in peso['alertas']
    assert peso['fonte']['folha'] == doc['folhas'][0]['id'] and peso['fonte']['trecho']
    trecho = next(t for t in doc['folhas'][0]['trechos'] if t['id'] == peso['fonte']['trecho'])
    assert trecho['texto'] == '2 MB' and trecho['linha'] == 11
    assert vertical['campos']['faixas']['valor'] == [{'lado': 'inferior', 'px': 120}]
    circ = next(c for c in doc['circuitos'] if c['id'] == vertical['circuito'])
    assert circ['campos']['ambiente']['valor'] == 'Estação Exemplo'
    assert 'praca_mista' in circ['campos']['praca']['alertas']
    deitado = _formato(doc, '|1920x1080')
    assert deitado['campos']['peso_max']['valor']['alvo_bytes'] == 1500000
    assert 'virgula_decimal' in deitado['campos']['peso_max']['alertas']


def test_csv_do_da_com_sufixo_literal_e_colunas_de_largura_e_altura(tmp_path):
    csv = apoio.csv_do_da(['Largura', 'Altura', 'Peso máximo', 'Sufixo', 'Praça'],
                          [['1080', '1920', '5 MB', '_80px_', 'Curitiba'], ['300', '600', '200KB', '_v2_', 'PR']])
    job = _job(tmp_path, {'lista.csv': csv})
    doc = importar.importar(job)[0]
    f = _formato(doc, '|1080x1920')
    assert f['campos']['dimensao']['fonte']['trechos_adicionais'] and 'dimensao_de_duas_colunas' in f['campos']['dimensao']['alertas']
    # o sufixo fica literal e nunca vira geometria
    assert f['campos']['sufixo_nome_arquivo']['valor'] == '_80px_'
    assert f['campos']['sufixo_nome_arquivo']['numeros_literais'] == []
    assert f['campos']['faixas']['valor'] is None and f['campos']['area_util']['valor'] is None
    assert modelo.conferir_literais(doc) == []


def test_html_tetos_por_tag_area_segura_e_divergencia_do_meia_pagina(job_globo):
    job, doc = job_globo
    veic = doc['veiculadores'][0]
    assert len(veic['tetos_por_tamanho']) == 2
    meia = _formato(doc, 'meia|300x600')
    c = meia['campos']
    assert c['peso_max_hospedado']['valor']['alvo_bytes'] == 250000 and c['peso_max_hospedado']['condicao'] == 'hospedado'
    assert c['peso_max_tag_carga_inicial']['valor']['alvo_bytes'] == 250000
    assert c['peso_max_tag_carga_posterior']['valor']['alvo_bytes'] == 500000
    tag = c['peso_max_tag']
    assert tag['valor'] is None and 'fontes_divergentes' in tag['alertas'] and tag['situacao'] == 'rascunho'
    assert sorted(x['valor']['alvo_bytes'] for x in tag['leituras']) == [500000, 550000]
    assert len({x['fonte']['folha'] for x in tag['leituras']}) == 2
    vertical = _formato(doc, 'vertical|1080x1920')
    assert vertical['campos']['peso_max']['valor']['alvo_bytes'] == 500000
    # o peso de 10 MB da secao de video e o "999KB" do script nao viram valor
    assert all(v['valor'] != {'alvo_bytes': 10000000, 'reprova_acima_bytes': 10485760} for v in _valores(doc))
    assert len(doc['formatos']) == 2


def test_da_escolhe_a_leitura_e_o_motor_nao(job_globo, tmp_path):
    origem = job_globo[0]
    job = tmp_path / 'job'
    shutil.copytree(origem, job)
    doc = importar.importar(job)[0]
    tag = _formato(doc, 'meia|300x600')['campos']['peso_max_tag']
    escolha = next(i for i, x in enumerate(tag['leituras']) if x['valor']['alvo_bytes'] == 500000)
    respostas = iter([str(escolha + 1)] + ['p'] * 200)
    confirmar.sessao(job, disparo=_disparo_spec(), entrada=lambda _p: next(respostas), saida=lambda *_a: None, filtro_campo='peso_max_tag')
    doc = contratos.ler(job / 'specs' / 'rascunho.json', 'spec/1')
    tag = _formato(doc, 'meia|300x600')['campos']['peso_max_tag']
    assert tag['situacao'] == 'confirmado' and tag['valor']['alvo_bytes'] == 500000 and tag['confirmacao']['leitura'] == escolha
    assert len(tag['leituras']) == 2


# ------------------------------------------------------------------ propriedade: campo ausente nunca vira valor
def test_propriedade_campo_ausente_nunca_vira_valor(tmp_path):
    colunas = {'Formato': lambda r: '%dx%d' % (r.randint(1, 4000), r.randint(1, 4000)),
               'Peso máximo': lambda r: '%d MB' % r.randint(1, 50), 'Área útil': lambda r: '%dx%d' % (r.randint(1, 900), r.randint(1, 900)),
               'Barra inferior': lambda r: '%dpx' % r.randint(1, 200), 'Tipos aceitos': lambda r: r.choice(['JPG', 'PNG', 'JPG ou PNG']),
               'Sufixo': lambda r: '_%d_' % r.randint(1, 99), 'Praça': lambda r: r.choice(['Curitiba', 'BA', 'Recife e PE'])}
    campo_da_coluna = {'Peso máximo': 'peso_max', 'Área útil': 'area_util', 'Barra inferior': 'faixas',
                       'Tipos aceitos': 'tipos_aceitos', 'Sufixo': 'sufixo_nome_arquivo'}
    sorteio = random.Random(20261031)
    for rodada in range(12):
        escolhidas = ['Formato'] + sorteio.sample(sorted(c for c in colunas if c != 'Formato'), sorteio.randint(0, 5))
        linhas = [[colunas[c](sorteio) for c in escolhidas] for _ in range(sorteio.randint(1, 4))]
        job = _job(tmp_path / str(rodada), {'lista.csv': apoio.csv_do_da(escolhidas, linhas)})
        doc = importar.importar(job)[0]
        assert doc['formatos']
        for f in doc['formatos']:
            for coluna, campo in campo_da_coluna.items():
                v = f['campos'][campo]
                if coluna not in escolhidas:
                    assert v['valor'] is None and v['situacao'] == 'registro' and v['origem'] == 'ausente', (rodada, campo)
            for campo in ('area_segura', 'borda_1px', 'sangria', 'area_visivel', 'rotacao', 'orientacao_painel'):
                assert f['campos'][campo]['valor'] is None and f['campos'][campo]['situacao'] == 'registro'
        for v in _valores(doc):
            if v['origem'] == 'ausente':
                assert v['valor'] is None and v['situacao'] == 'registro'


# ------------------------------------------------------------------ propostas do Claude e confirmacao do DA
def _proposta(doc, pedaco, campo):
    t = next((f['id'], t['id']) for f in doc['folhas'] for t in f['trechos'] if pedaco in t['texto'])
    return {'folha': t[0], 'trecho': t[1], 'campo': campo}


def test_proposta_de_mapeamento_o_numero_e_do_motor(job_globo, tmp_path):
    job = tmp_path / 'job'
    shutil.copytree(job_globo[0], job)
    doc = importar.importar(job)[0]
    pacote = contratos.ler(job / 'sugestoes' / 'pacote-specs.json', 'pacote-specs/1')
    assert pacote['exposto']['textos'] and any('14%' in t['texto'] for t in pacote['trechos'])
    propostas = [_proposta(doc, 'cerca de 14%', 'area_segura'), _proposta(doc, 'borda preta de 1 px', 'borda_1px'),
                 dict(_proposta(doc, 'cerca de 14%', 'area_segura'), recorte_texto='99% (aprox. 999 pixels)')]
    contratos.gravar(job / 'sugestoes' / 'mapeamento-specs.json', {'esquema': 'mapeamento-specs/1', 'propostas': propostas},
                     'mapeamento-specs/1')
    doc, _f, info = importar.importar(job)
    assert info['propostas_do_modelo'] == 2 and info['propostas_ignoradas'] == 1
    seg = _formato(doc, 'vertical|1080x1920')['campos']['area_segura']
    assert seg['valor'] == {'pct': 14, 'px': 250, 'lados': ['inferior', 'superior']} and 'aproximado' in seg['alertas']
    assert seg['mapeamento'] == 'proposta_do_modelo' and seg['situacao'] == 'rascunho'
    borda = doc['veiculadores'][0]['campos']['borda_1px']
    assert borda['valor'] == {'espessura_px': 1, 'cor': 'preta'} and borda['forma'] == 'condicional' and borda['condicao']
    # a proposta nao tem lugar para valor: o contrato recusa
    with pytest.raises(contratos.ErroContrato):
        contratos.validar({'esquema': 'mapeamento-specs/1', 'propostas': [dict(propostas[0], valor=14)]}, 'mapeamento-specs/1')


def test_modo_c_nao_expoe_trecho_e_ignora_proposta(tmp_path):
    job = _job(tmp_path, {'globo/vertical.html': apoio.html_vertical()}, modo='c')
    doc = importar.importar(job)[0]
    pacote = contratos.ler(job / 'sugestoes' / 'pacote-specs.json', 'pacote-specs/1')
    assert pacote['trechos'] == [] and pacote['alvos'] == [] and not pacote['exposto']['textos']
    contratos.gravar(job / 'sugestoes' / 'mapeamento-specs.json',
                     {'esquema': 'mapeamento-specs/1', 'propostas': [_proposta(doc, 'cerca de 14%', 'area_segura')]},
                     'mapeamento-specs/1')
    doc, _f, info = importar.importar(job)
    assert info['propostas_ignoradas_modo_c'] == 1
    assert _formato(doc, '|1080x1920')['campos']['area_segura']['valor'] is None


def test_segredo_num_trecho_nao_vai_para_o_pacote(tmp_path):
    texto = apoio.EMAIL + '\nchave: AIza' + 'B' * 35 + '\n'
    job = _job(tmp_path, {'email.txt': texto})
    importar.importar(job)
    pacote = contratos.ler(job / 'sugestoes' / 'pacote-specs.json', 'pacote-specs/1')
    assert pacote['contagens']['segredos_bloqueados'] == 1
    assert not any('AIza' in t['texto'] for t in pacote['trechos'])
    assert (job / 'sugestoes' / 'segredos-bloqueados.json').is_file()


def test_confirmar_e_formatos_do_job_so_com_confirmados(job_pme, tmp_path):
    job = tmp_path / 'job'
    shutil.copytree(job_pme[0], job)
    alvo = 'sao-paulo-shopping-exemplo|1080x1920'
    doc = importar.importar(job)[0]
    chave = _formato(doc, alvo)['chave']
    respostas = iter(['', 'x', 'c', 'c', 'p', 's'])
    novas, doc, formatos, _ = confirmar.sessao(job, disparo=_disparo_spec(), entrada=lambda _p: next(respostas), saida=lambda *_a: None,
                                               filtro_formato=chave, com_recortes=False)
    assert [a['acao'] for a in novas] == ['confirmar', 'confirmar']
    contratos.validar(formatos, 'spec/1')
    assert formatos['tipo'] == 'formatos_do_job' and len(formatos['formatos']) == 1
    so = formatos['formatos'][0]
    assert so['chave'] == chave and all(v['situacao'] == 'confirmado' for v in so['campos'].values())
    assert set(so['campos']) == {'dimensao', 'area_util'}
    # a confirmacao vale para a folha e o conteudo: a folha nova e um perfil novo, e o DA confirma de novo
    nova = apoio.folha_pme_sintetica().replace(b'1080px x 1848px', b'1080px x 1840px')
    origem = tmp_path / 'nova.pdf'
    origem.write_bytes(nova)
    nucleo.trocar_entrada(job, 'entrada/specs/pme/folha.pdf', origem)
    doc, formatos, info = importar.importar(job)
    assert info['acoes_ignoradas'] == 2 and info['acoes_aplicadas'] == 0 and formatos['formatos'] == []
    assert {_formato(doc, alvo)['campos'][c]['situacao'] for c in ('dimensao', 'area_util')} == {'rascunho'}
    assert doc['perfis'][0]['versao'] == 2 and len(doc['perfis'][0]['historico']) == 1


def test_confirmar_recusa_sem_terminal_e_no_envelope(job_pme, capsys):
    job = job_pme[0]
    assert cli.principal(['spec', 'confirmar', '--job', str(job)]) == 3
    capsys.readouterr()
    assert cli.principal(['--envelope', 'spec', 'confirmar', '--job', str(job)]) == 3
    env = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    # M7c, revisao do K5: a recusa manda o DA a tela, sem terminal (decisoes-v1.md, 159)
    from desdobra import humano
    assert env['situacao'] == 'recusado' and env['o_que_fazer'] == humano.O_QUE_FAZER
    assert 'terminal' not in env['o_que_fazer'] and 'terminal' not in ' '.join(env.get('linhas_humanas') or [])
    assert not (job / 'specs' / 'confirmacoes.json').exists()


# ------------------------------------------------------------------ validar
def _formatos_confirmados(job, tmp_path):
    destino = tmp_path / 'jobv'
    shutil.copytree(job, destino)
    doc = importar.importar(destino)[0]
    chave = _formato(doc, 'sao-paulo-shopping-exemplo|1080x1920')['chave']
    confirmar.sessao(destino, disparo=_disparo_spec(), entrada=lambda _p: 'c', saida=lambda *_a: None, filtro_formato=chave, com_recortes=False)
    return destino, chave


def test_validar_contra_o_job_dimensao_peso_e_tipo(job_pme, tmp_path, capsys):
    job, chave = _formatos_confirmados(job_pme[0], tmp_path)
    casos = [('ok.png', apoio.png_de_tamanho(1080, 1920, 4000000), 0, 'aprovado'),
             ('entre.jpg', apoio.jpeg_de_tamanho(1080, 1920, 5100000), 0, 'aviso'),
             ('pesado.png', apoio.png_de_tamanho(1080, 1920, 5242881), 3, 'reprovado'),
             ('girado.png', apoio.png_de_tamanho(1920, 1080, 1000), 3, 'reprovado'),
             ('tipo.gif', b'GIF89a' + b'\x38\x04\x80\x07' + b'\x00' * 100, 3, 'reprovado'),
             ('trocado.jpg', apoio.png_de_tamanho(1080, 1920, 1000), 0, 'aviso')]
    for nome, dados, codigo, resultado in casos:
        arq = tmp_path / nome
        arq.write_bytes(dados)
        saida = tmp_path / (nome + '.json')
        capsys.readouterr()
        assert cli.principal(['--envelope', 'validar', str(arq), '--formato', chave, '--job', str(job),
                              '--saida', str(saida)]) == codigo, nome
        env = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert env['codigo'] == codigo and env['comando'] == 'validar'
        assert nome not in json.dumps(env, ensure_ascii=False)
        rel = contratos.ler(saida, 'validacao-arquivo/1')
        assert rel['resultado'] == resultado and rel['contra'] == 'formatos_do_job', (nome, rel['verificacoes'])
    rel = contratos.ler(tmp_path / 'girado.png.json', 'validacao-arquivo/1')
    assert next(i for i in rel['verificacoes'] if i['campo'] == 'dimensao')['motivo'] == 'girado'
    assert cli.principal(['validar', str(tmp_path / 'ok.png'), '--formato', 'nao|existe|1x1', '--job', str(job)]) == 2


def test_validar_sem_confirmacao_nao_tem_regra(job_pme, tmp_path):
    arq = tmp_path / 'a.png'
    arq.write_bytes(apoio.png_de_tamanho(1080, 1920, 9000000))
    doc = contratos.ler(job_pme[0] / 'specs' / 'formatos-do-job.json', 'spec/1')
    assert doc['formatos'] == []
    rascunho = contratos.ler(job_pme[0] / 'specs' / 'rascunho.json', 'spec/1')
    chave = _formato(rascunho, 'sao-paulo-shopping-exemplo|1080x1920')['chave']
    rel = validar.validar(arq, rascunho, chave, 'formatos_do_job')
    assert {i['situacao'] for i in rel['verificacoes']} == {'sem_regra'}
    # sem regra confirmada o arquivo nunca sai aprovado
    assert rel['resultado'] == 'aviso'
    rel = validar.validar(arq, rascunho, chave, 'rascunho')
    assert rel['resultado'] == 'reprovado'


def test_validar_peso_condicional_depende_da_condicao(job_globo, tmp_path):
    doc = job_globo[1]
    chave = _formato(doc, 'meia|300x600')['chave']
    arq = tmp_path / 'm.png'
    arq.write_bytes(apoio.png_de_tamanho(300, 600, 300000))
    sem = validar.validar(arq, doc, chave, 'rascunho')
    assert sem['resultado'] == 'aviso'
    hosp = validar.validar(arq, doc, chave, 'rascunho', condicao='hospedado')
    assert next(i for i in hosp['verificacoes'] if i['campo'] == 'peso_max_hospedado')['situacao'] == 'reprova'
    assert next(i for i in hosp['verificacoes'] if i['campo'] == 'peso_max_tag')['motivo'] == 'fontes_divergentes_o_da_decide'


def test_cabecalho_de_imagem_sem_decodificar():
    assert validar.dimensao_do_cabecalho(apoio.jpeg_de_tamanho(321, 123, 400), 'image/jpeg') == (321, 123)
    assert validar.dimensao_do_cabecalho(apoio.png_de_tamanho(77, 66, 100), 'image/png') == (77, 66)
    assert validar.mime_do_arquivo(b'%PDF-1.4') == 'application/pdf'


# ------------------------------------------------------------------ filho isolado, esteira e recusas
def test_folha_malformada_vira_recusa_tipada(tmp_path):
    ruim = tmp_path / 'ruim.pdf'
    ruim.write_bytes(b'%PDF-1.4\n' + b'\x00lixo' * 100)
    r = leitura.ler(ruim, tmp_path / 'saida', tmp_path / 'trab')
    assert r['situacao'] == 'recusada' and r['recusa']['tipo'] == 'malformado'
    assert r['leitura']['auditoria']['instalado']
    planilha = tmp_path / 'tabela.xlsx'
    planilha.write_bytes(b'PK\x03\x04' + b'\x00' * 50)
    assert leitura.formato_da_folha(planilha) is None


def test_leitura_no_filho_tem_gancho_e_e_reaproveitada(tmp_path):
    folha = tmp_path / 'f.pdf'
    folha.write_bytes(apoio.folha_pme_sintetica())
    r = leitura.ler(folha, tmp_path / 's', tmp_path / 't')
    assert r['situacao'] == 'lida' and r['leitura']['auditoria'] == {'instalado': True, 'bloqueios': 0}
    marca = (tmp_path / 's' / 'leitura.json').stat().st_mtime_ns
    assert leitura.ler(folha, tmp_path / 's', tmp_path / 't')['situacao'] == 'lida'
    assert (tmp_path / 's' / 'leitura.json').stat().st_mtime_ns == marca


def test_esteira_tem_a_fase_specs():
    ids = [f.id for f in mod_fases.ESTEIRA]
    specs = next(f for f in mod_fases.ESTEIRA if f.id == 'specs')
    assert ids[-1] == 'specs' and specs.depende_de == ()
    assert set(specs.entradas) == {'entrada/specs', 'specs/confirmacoes.json', 'sugestoes/mapeamento-specs.json'}
    assert specs.comando('P')[-4:] == ['spec', 'importar', '--job', 'P']


def test_fase_specs_pela_esteira_e_invalidada_so_pela_folha(job_pme, tmp_path):
    """A esteira inteira, com as outras fases simuladas (gravam as saidas): trocar a folha invalida so a specs."""
    job = tmp_path / 'job'
    shutil.copytree(job_pme[0], job)
    por_argv = {tuple(f.comando(job)): f for f in mod_fases.ESTEIRA}

    def executor(argv, pasta):
        fase = por_argv[tuple(argv)]
        if fase.id == 'specs':
            return nucleo._executar_comando(argv, pasta)
        for saida in fase.saidas:
            (pasta / saida).parent.mkdir(parents=True, exist_ok=True)
            (pasta / saida).write_text('{"fase": "%s"}' % fase.id, encoding='utf-8')
        return 0, b'', b''
    r = nucleo.proxima(job, todas=True, executor=executor)
    assert r.codigo == 0 and r.situacao == 'concluido'
    avaliacao, _ = nucleo.avaliar(job, nucleo.ler_estado(job), mod_fases.ESTEIRA)
    assert all(v for v, _m in avaliacao.values())
    assert contratos.ler(job / 'specs' / 'rascunho.json', 'spec/1')['resumo']['formatos'] == 4
    origem = tmp_path / 'outra.html'
    origem.write_text(apoio.html_vertical(), encoding='utf-8')
    nucleo.trocar_entrada(job, 'entrada/specs/globo/vertical.html', origem)
    avaliacao, _ = nucleo.avaliar(job, nucleo.ler_estado(job), mod_fases.ESTEIRA)
    assert {k for k, (v, _m) in avaliacao.items() if not v} == {'specs'}


def test_doctor_confere_a_versao_fixada_do_pypdfium2():
    import inspect

    from desdobra import doctor
    from desdobra.doctor import chromium as vc
    assert vc.verificar_versao('pypdfium2', 'pypdfium2', 'Versão fixada do pypdfium2').situacao == 'ok'
    assert "('pypdfium2', lambda: vc.verificar_versao('pypdfium2'" in inspect.getsource(doctor.rodar_verificacoes)


# ------------------------------------------------------------------ correcoes da revisao
def _job_com_propostas(tmp_path, texto, propostas_de):
    job = _job(tmp_path, {'e/email.txt': texto})
    doc = importar.importar(job)[0]
    props = propostas_de(doc)
    contratos.gravar(job / 'sugestoes' / 'mapeamento-specs.json', {'esquema': 'mapeamento-specs/1', 'propostas': props},
                     'mapeamento-specs/1')
    return job


def test_recorte_texto_no_meio_de_um_numero_e_ignorado(tmp_path):
    """H1: "5 MB" dentro de "15 MB" e "080x192" dentro de "1080x1920" nao fabricam numero."""
    def props(doc):
        fmt = doc['formatos'][0]['id']
        return [dict(_proposta(doc, '15 MB', 'peso_max'), alvo=fmt, recorte_texto='5 MB'),
                dict(_proposta(doc, '1080x1920', 'area_util'), alvo=fmt, recorte_texto='080x192'),
                dict(_proposta(doc, '1080x1920', 'area_util'), alvo=fmt, recorte_texto='1080x1920')]
    job = _job_com_propostas(tmp_path, 'Formato: 1080x1920\nPeso máximo: 15 MB\n', props)
    doc, _f, info = importar.importar(job)
    f = doc['formatos'][0]['campos']
    assert info['propostas_do_modelo'] == 1 and info['propostas_ignoradas'] == 2
    assert f['peso_max']['valor']['alvo_bytes'] == 15000000 and not f['peso_max'].get('leituras')
    assert f['area_util']['valor'] == {'largura': 1080, 'altura': 1920}
    assert modelo.conferir_literais(doc) == []
    # o DA ve o pedaco do trecho e quem ligou o campo ao trecho
    linhas = []
    confirmar.sessao(job, disparo=_disparo_spec(), entrada=lambda _p: 's', saida=lambda *a: linhas.append(' '.join(map(str, a))),
                     filtro_campo='area_util')
    assert any('"1080x1920"' in l and 'pedaço' in l for l in linhas) and any('proposta do Claude' in l for l in linhas)


def test_literal_com_fronteira_de_numero():
    assert modelo.numero_no_texto('15', 'até 15 MB') and not modelo.numero_no_texto('5', 'até 15 MB')
    assert not modelo.numero_no_texto('1', 'tem 1,5 MB') and modelo.numero_no_texto('1,5', 'tem 1,5 MB.')
    assert modelo.corte_com_fronteira('usar 60%', 'seria usar 60%.') and not modelo.corte_com_fronteira('5 MB', '15 MB')
    assert not modelo.corte_com_fronteira('1.5', '11.5 MB') and not modelo.corte_com_fronteira('', 'x')
    assert extrair.peso('até 15 MB')['numeros_literais'] == ['15']
    doc = {'folhas': [{'id': 'f00000001', 'campos': {}, 'trechos': [{'id': 'p01-t001', 'texto': 'Peso: 15 MB'}]}], 'veiculadores': [],
           'circuitos': [], 'formatos': [{'id': 'x', 'campos': {'peso_max': {
               'id': 'x/peso_max', 'origem': 'extraido_do_trecho', 'numeros_literais': ['5'], 'situacao': 'rascunho',
               'fonte': {'folha': 'f00000001', 'trecho': 'p01-t001', 'recorte_texto': '5 MB'}}}}]}
    assert modelo.conferir_literais(doc) == [('x/peso_max', '5 MB'), ('x/peso_max', '5')]


def test_segredo_no_titulo_no_circuito_e_na_pasta_nao_sai(tmp_path):
    """H2: segredo no titulo do HTML (secao), no nome do circuito e no nome da pasta do veiculador."""
    chave = 'AIza' + 'C' * 35
    html = '<html><body><h2>nota %s</h2><ul><li>Dimensão: 300x250</li><li>Peso: até 150KB</li></ul></body></html>' % chave
    job = _job(tmp_path, {'g/x.html': html, 'e/email.txt': 'Circuito: %s\nFormato: 1080x1920\n' % chave,
                          'pasta%s/f.txt' % chave: 'Formato: 300x600\n'})
    doc = importar.importar(job)[0]
    texto = (job / 'sugestoes' / 'pacote-specs.json').read_text(encoding='utf-8')
    pacote = json.loads(texto)
    assert chave not in texto and pacote['contagens']['segredos_bloqueados'] >= 3
    assert any(t['texto'] == 'Dimensão: 300x250' and t['secao'] is None for t in pacote['trechos'])
    # o id que viria do texto com segredo e neutro ja no rascunho
    assert all(chave.lower() not in c['id'] for c in doc['circuitos']) and all(chave.lower() not in v['id'] for v in doc['veiculadores'])
    assert any(c['id'].split(':', 1)[1].startswith('oculto-') for c in doc['circuitos'])


def test_validar_sem_regra_confirmada_nao_aprova(tmp_path):
    """M1: so a dimensao confirmada, um PNG de 50 MB nao sai aprovado."""
    job = _job(tmp_path, {'e/email.txt': 'Formato: 1080x1920\nPeso máximo: 5 MB\nTipos de arquivo: JPG\n'})
    respostas = iter(['c'] + ['p'] * 20)
    confirmar.sessao(job, disparo=_disparo_spec(), entrada=lambda _p: next(respostas), saida=lambda *_a: None, filtro_campo='dimensao')
    fj = contratos.ler(job / 'specs' / 'formatos-do-job.json', 'spec/1')
    arq = tmp_path / 'g.png'
    arq.write_bytes(apoio.png_de_tamanho(1080, 1920, 50000000))
    rel = validar.validar(arq, fj, fj['formatos'][0]['chave'], 'formatos_do_job')
    assert rel['resultado'] == 'aviso'
    assert {i['campo'] for i in rel['verificacoes'] if i['situacao'] == 'sem_regra'} == {'peso_max', 'tipos_aceitos'}


def test_jpeg_com_metadados_grandes_e_orientacao_exif(tmp_path):
    """M2 e L6: mais de 64 KiB de APP antes do SOF, e a tag Orientation do Exif vira aviso."""
    import struct
    app = b''.join(b'\xff\xe2' + struct.pack('>H', 65535) + b'\x00' * 65533 for _ in range(2))
    tiff = b'II*\x00' + struct.pack('<I', 8) + struct.pack('<H', 1) + struct.pack('<HHIHH', 0x0112, 3, 1, 6, 0) + b'\x00' * 4
    exif = b'\xff\xe1' + struct.pack('>H', 2 + 6 + len(tiff)) + b'Exif\x00\x00' + tiff
    sof = b'\xff\xc0' + struct.pack('>HBHHB', 11, 8, 1920, 1080, 1) + b'\x01\x11\x00'
    arq = tmp_path / 'grande.jpg'
    arq.write_bytes(b'\xff\xd8' + exif + app + sof + b'\x00' * 100)
    info = validar.ler_arquivo(arq)
    assert (info['largura'], info['altura'], info['orientacao_exif']) == (1080, 1920, 6)
    rascunho = importar.importar(_job(tmp_path / 'j', {'e/email.txt': 'Formato: 1080x1920\n'}))[0]
    rel = validar.validar(arq, rascunho, rascunho['formatos'][0]['chave'], 'rascunho')
    assert next(i for i in rel['verificacoes'] if i['campo'] == 'orientacao_exif')['situacao'] == 'aviso'


def test_mesma_folha_em_duas_pastas_e_mesmos_bytes_em_dois_formatos(tmp_path):
    """M3: a folha e unica pelo caminho; a leitura reaproveitada e por sha256 e formato."""
    pdf = apoio.folha_pme_sintetica()
    csv = apoio.csv_do_da(['Formato', 'Peso máximo'], [['1080x1920', '5 MB']])
    job = _job(tmp_path, {'a/f.pdf': pdf, 'b/f.pdf': pdf, 'c/lista.txt': csv, 'd/lista.csv': csv})
    doc = importar.importar(job)[0]
    assert len({f['id'] for f in doc['folhas']}) == 4
    assert {v['id']: len(v['folhas']) for v in doc['veiculadores']} == {'a': 1, 'b': 1, 'c': 1, 'd': 1}
    assert {f['arquivo'].split('/')[2]: f['formato'] for f in doc['folhas']}['d'] == 'csv'
    assert any(f['chave'] == 'd|%s-geral|1080x1920' % next(x['id'] for x in doc['folhas'] if x['formato'] == 'csv')
               for f in doc['formatos'])


def test_texto_hostil_nao_trava_e_folha_com_trecho_longo_e_recusada(tmp_path):
    """M4: regex linear e teto de trecho no filho."""
    import time
    t0 = time.monotonic()
    for f in (extrair.dimensao, extrair.peso, extrair.area_segura, extrair.faixa):
        f('1' * 40000)
    assert time.monotonic() - t0 < limites.valor('specs.tempo_max_s')
    longo = tmp_path / 'longo.csv'
    longo.write_bytes(apoio.csv_do_da(['Formato'], [['1' * (limites.valor('specs.trecho_caracteres_max') + 1)]]))
    r = leitura.ler(longo, tmp_path / 's', tmp_path / 't')
    assert r['situacao'] == 'recusada' and r['recusa']['tipo'] == 'trecho_longo'


def test_tabela_por_tamanho_diverge_da_ficha_e_de_outra_linha(tmp_path):
    """M5: carga inicial da ficha diferente da tabela, e duas linhas da tabela para o mesmo tamanho."""
    ficha = apoio.html_ficha('Meia', [('dimensão', '300x600'), ('carga inicial', '200KB')])
    tabela = apoio.html_orientacoes().replace('<div class="col">P</div><div class="col">320x50</div>',
                                              '<div class="col">P</div><div class="col">300x600</div>')
    job = _job(tmp_path, {'g/meia.html': ficha, 'g/orientacoes.html': tabela})
    doc = importar.importar(job)[0]
    c = _formato(doc, '|300x600')['campos']
    ini = c['peso_max_tag_carga_inicial']
    assert ini['valor'] is None and 'fontes_divergentes' in ini['alertas']
    assert sorted(x['valor']['alvo_bytes'] for x in ini['leituras']) == [100000, 200000, 250000]
    post = c['peso_max_tag_carga_posterior']
    assert post['valor'] is None and sorted(x['valor']['alvo_bytes'] for x in post['leituras']) == [100000, 500000]


def test_confirmar_interrompido_grava_o_que_ja_foi_respondido(job_pme, tmp_path):
    """L1: Ctrl+C no meio da sessao nao perde as respostas."""
    job = tmp_path / 'job'
    shutil.copytree(job_pme[0], job)
    respostas = iter(['c', 'c'])

    def entrada(_p):
        try:
            return next(respostas)
        except StopIteration:
            raise KeyboardInterrupt from None
    novas = confirmar.sessao(job, disparo=_disparo_spec(), entrada=entrada, saida=lambda *_a: None, com_recortes=False)[0]
    assert len(novas) == 2
    assert len(contratos.ler(job / 'specs' / 'confirmacoes.json', 'spec-confirmacoes/1')['acoes']) == 2


def test_digitar_no_recorte_so_campos_que_valem(tmp_path):
    """L2: rotacao, prazo e qualidade (so registro) nao se digitam; restricao vai para a lista do circuito."""
    job = _job(tmp_path, {'j/c.pdf': apoio.pdf_escaneado(1)})
    respostas = iter(['rotacao', 'prazo_envio', 'dimensao', '1080x1920', 'restricao', 'sem animação', ''])
    novas, doc, _f, _i = confirmar.sessao(job, disparo=_disparo_spec(), entrada=lambda _p: next(respostas), saida=lambda *_a: None)
    assert [a['campo'] for a in novas] == ['dimensao', 'restricao']
    circ = next(c for c in doc['circuitos'] if c['restricoes'])
    assert circ['restricoes'][0]['valor'] == 'sem animação' and circ['restricoes'][0]['situacao'] == 'confirmado'
    assert circ['id'].endswith('%s-p01' % doc['folhas'][0]['id'])
    assert all(v['situacao'] != 'confirmado' for f in doc['formatos'] for c, v in f['campos'].items() if c == 'rotacao')


def test_chave_repetida_nao_depende_da_ordem(tmp_path):
    """L3: duas entradas iguais no mesmo circuito ganham o id do formato na chave, as duas."""
    job = _job(tmp_path, {'e/email.txt': 'Formato: 1080x1920\nPeso máximo: 5 MB\n\nFormato: 1080x1920\n'})
    doc = importar.importar(job)[0]
    chaves = sorted(f['chave'] for f in doc['formatos'])
    assert len(chaves) == 2 and all('#' in c and c.split('#')[1] in {f['id'] for f in doc['formatos']} for c in chaves)


def test_condicao_invalida_e_erro_de_uso(job_globo, tmp_path):
    """L4: --condicao so aceita as condicoes conhecidas."""
    arq = tmp_path / 'a.png'
    arq.write_bytes(apoio.png_de_tamanho(300, 600, 100))
    assert cli.principal(['--envelope', 'validar', str(arq), '--formato', 'x', '--perfil',
                          str(job_globo[0] / 'specs' / 'rascunho.json'), '--condicao', 'qualquer']) == 2


def test_fase_specs_depende_da_biblioteca_e_dos_limites(job_pme, tmp_path, monkeypatch):
    """L5: perfil novo na biblioteca ou limite de specs mudado invalida a fase specs."""
    job = tmp_path / 'job'
    shutil.copytree(job_pme[0], job)
    specs = [f for f in mod_fases.ESTEIRA if f.id == 'specs']
    assert nucleo.proxima(job, fases=specs).codigo == 0
    assert nucleo.avaliar(job, nucleo.ler_estado(job), specs)[0]['specs'][0]
    monkeypatch.setattr(importar, 'hash_da_biblioteca', lambda pasta=None: '0' * 64)
    assert not nucleo.avaliar(job, nucleo.ler_estado(job), specs)[0]['specs'][0]
    monkeypatch.undo()
    monkeypatch.setattr(importar, 'hash_dos_limites', lambda: '1' * 64)
    assert not nucleo.avaliar(job, nucleo.ler_estado(job), specs)[0]['specs'][0]


def test_eml_quoted_printable_e_multipart(tmp_path):
    """L7: o corpo em texto puro do .eml, codificado ou em multipart; a parte HTML e o cabecalho ficam de fora."""
    import quopri
    qp = (b'From: a@b.c\nSubject: specs\nMIME-Version: 1.0\nContent-Type: text/plain; charset="utf-8"\n'
          b'Content-Transfer-Encoding: quoted-printable\n\n' + quopri.encodestring(apoio.EMAIL.encode('utf-8')))
    mp = ('From: a@b.c\nSubject: specs\nMIME-Version: 1.0\nContent-Type: multipart/alternative; boundary="X"\n\n--X\n'
          'Content-Type: text/plain; charset=utf-8\n\n' + apoio.EMAIL + '\n--X\nContent-Type: text/html\n\n'
          '<p>Formato: 999x999</p>\n--X--\n').encode('utf-8')
    job = _job(tmp_path, {'q/a.eml': qp, 'm/b.eml': mp})
    doc = importar.importar(job)[0]
    for vid in ('q', 'm'):
        chaves = sorted(f['chave'].split('|')[-1] for f in doc['formatos'] if f['veiculador'] == vid)
        assert chaves == ['1080x1920', '1920x1080'], (vid, chaves)
    assert not any('a@b.c' in t['texto'] for f in doc['folhas'] for t in f['trechos'])


def test_filho_que_estoura_tempo_ou_memoria_vira_recusa_tipada(tmp_path):
    """L7: o pai transforma tempo e memoria do filho em recusa, sem cair (plataforma falsa)."""
    from desdobra.plataforma import Plataforma, ResultadoFilho

    class Falsa(Plataforma):
        nome = 'falsa'

        def __init__(self, situacao):
            self.situacao = situacao

        def executar_isolado(self, comando, orcamento_bytes, tempo_s, pasta_trabalho, *, ambiente=None):
            return ResultadoFilho(situacao=self.situacao, codigo=None, pico_bytes=None, stdout_bytes=b'',
                                  stderr_resumo='', motivo='teste')
    folha = tmp_path / 'f.pdf'
    folha.write_bytes(apoio.folha_pme_sintetica())
    for sit in ('tempo', 'memoria', 'queda'):
        r = leitura.ler(folha, tmp_path / sit / 's', tmp_path / sit / 't', plat=Falsa(sit), reaproveitar=False)
        assert r['situacao'] == 'recusada' and r['recusa']['tipo'] == sit


def test_perfil_enxuto_sem_registros_vazios():
    """L8: o arquivo do perfil nao repete os campos ausentes; ao ler, eles voltam como registro."""
    from conftest import RAIZ_PLUGIN
    arq = RAIZ_PLUGIN / 'biblioteca-specs' / 'eletromidia-pme-1.json'
    bruto = contratos.ler(arq, 'spec/1')
    assert all(v['origem'] != 'ausente' for _r, _c, v in modelo.todos_os_valores(bruto))
    cheio = importar.perfil_da_biblioteca(arq)
    assert cheio['formatos'][0]['campos']['rotacao']['situacao'] == 'registro'


def test_kb_minusculo_avisa_bit_ou_byte():
    assert 'unidade_bit_ou_byte' in extrair.peso('até 500 Kb')['alertas']
    assert 'unidade_bit_ou_byte' not in extrair.peso('até 500 KB')['alertas']
