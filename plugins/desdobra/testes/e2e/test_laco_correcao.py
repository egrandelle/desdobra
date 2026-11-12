# -*- coding: utf-8 -*-
"""M7b, E1: roteiro de ponta a ponta do laco de correcao (arquitetura-v1.md, 9.8, Laco de correcao; decisoes-v1.md,
138, 167 e 175; plano do M7b, E1 e secao 4; respostas do Duda as perguntas Q2, Q3, Q4, Q11 e Q12).

Um job sintetico com seis formatos em tres familias (duas horizontais, duas verticais e duas quadradas). O logo existe
so nos dois formatos horizontais: nas familias vertical e quadrada o DA o apagou. Tudo pelas rotas da tela, no modo de
teste (meio fixture_de_teste / medicao):
  - o rascunho com o passo 2, as edicoes de cada familia e o modo de dados, as tres familias confirmadas e "Salvar e
    seguir" (as rotas que a pagina usa);
  - o render dos seis e a aprovacao dos seis pelos atos da tela (o pedido e o Confirmar da janela);
  - na pagina, no Chromium: o DA troca a funcao do logo (logo principal para selo) no passo 2 e da a regra e a ancora
    do selo no Design system; confirma de novo as tres familias (decisoes-v1.md, 175) e clica em "Salvar e seguir";
  - conferencias da secao 4: os afetados sao so os dois horizontais (precisao e cobertura de 100%); so eles perdem a
    aprovacao e pedem render; os outros quatro ficam aprovados (medido com aprovacao.diferencas, nunca o portao com
    aprovacao=True, que recusa a aprovacao do modo de teste); os arquivos do render e a derivacao dos outros ficam com
    o mesmo sha; uma entrada nova em historico/indice.json; a pagina mostra, em cada afetado, so o item da troca de
    funcao ("O logo principal agora e o selo."), a mudanca real, e nenhum item nos outros;
  - "Renderizar os afetados" na pagina (uma confirmacao) e a aprovacao de novo so dos dois, marcados na pagina;
  - no fim, os seis aprovados, e os renders dos quatro de fora com o mesmo sha do comeco.
Os dois defeitos que o roteiro achou ficam tambem em testes proprios, sem render (corrigidos na fase E; os testes de
unidade da causa estao em test_tela_salvar):
  - test_salvar_e_seguir_volta_depois_de_mudar_o_passo_2: com as familias confirmadas de novo depois da troca de
    funcao, a tela pede outro "Salvar e seguir" (situacao_na_tela compara o briefing que o gravador montaria);
  - test_o_que_mudou_bate_com_a_derivacao_gravada: o "o que mudou" dos afetados e a diferenca entre a derivacao
    gravada antes e a gravada pelo salvar, que so mudou a funcao do logo.
Os numeros medidos vao para o arquivo da variavel de ambiente DESDOBRA_MEDICAO_LACO_CORRECAO, quando ela existe (fora
do repositorio; sem ela, nada e gravado fora da pasta temporaria do teste).
Tudo sintetico: o PSD de test_tela_palco e a fonte de autoteste do motor."""
import contextlib
import json
import os
import platform
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

import test_derivacao_apoio as ap
import test_fontes_apoio as fap
import test_tela_ato_render as tar
import test_tela_escrita as tte
import test_tela_palco as tp
import test_tela_servidor as tts
from desdobra import arquivos, contratos
from desdobra.briefing import historico
from desdobra.briefing import modelo as mb
from desdobra.derivacao import nucleo as nd
from desdobra.entrega import aprovacao, nucleo_aprovar, portao
from desdobra.tela import atos as ta
from desdobra.tela import estado as te
from desdobra.tela import servidor as ts

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')

ROT0 = {'graus': 0, 'sentido': None}
HORIZONTAIS = [('h1', 640, 320), ('h2', 660, 320)]
VERTICAIS = [('v1', 160, 320), ('v2', 166, 320)]
QUADRADOS = [('q1', 320, 320), ('q2', 330, 330)]
FORMATOS = HORIZONTAIS + VERTICAIS + QUADRADOS
IDS = [fid for fid, _w, _h in FORMATOS]
AFETADOS = sorted(fid for fid, _w, _h in HORIZONTAIS)
OUTROS = sorted(set(IDS) - set(AFETADOS))
USADAS = {'fundo': ('cover', 'centro', 'meio'), 'titulo': ('raiz_area', 'esquerda', 'topo'),
          'logo_principal': ('raiz_area', 'direita', 'base'), 'texto_de_apoio': ('raiz_area', 'esquerda', 'meio')}
NOVA_FUNCAO = 'selo'  # a funcao certa do logo, que o DA corrige depois da aprovacao
NOVA_REGRA = ('raiz_area', 'direita', 'base')
FRASE_DA_TROCA = 'O logo principal agora \u00e9 o selo.'  # derivacao/diferenca.py, item de tipo funcao
VARIAVEL_MEDICAO = 'DESDOBRA_MEDICAO_LACO_CORRECAO'
ARQUIVOS_DO_RENDER = ('master.png', 'render.json', 'contrato.json')
TETO_RENDER_S = 900  # numero-neutro: segundos de teto do teste para um lote de render na pagina
TETO_PREPARO_S = 120  # numero-neutro: segundos de teto do preparo de um ato longo na pagina
JS_DIALOGO = '() => document.getElementById("confirmacao").open ? "1" : ""'
JS_ATO = ('() => { const v = document.documentElement.dataset.estadoAto || "";'
          ' return ["parou", "erro", "cancelado"].includes(v) ? "erro" : v; }')
SALVO = '() => document.documentElement.dataset.rascunho === "salvo" ? "1" : ""'
PARADO = '() => ["pendente", "salvando"].includes(document.documentElement.dataset.rascunho) ? "" : "1"'


def _campos(tipos):
    return {'tipos_aceitos': {'id': 'tipos', 'valor': tipos, 'situacao': 'confirmado'},
            'peso_max': {'id': 'peso', 'valor': {'alvo_bytes': 10 ** 6, 'reprova_acima_bytes': 10 ** 6 + 6000},
                         'condicao': None, 'situacao': 'confirmado'}}


@pytest.fixture(scope='module')
def modelo(tmp_path_factory):
    """O job sintetico (o PSD de test_tela_palco, a fonte de autoteste) com a folha que o encoder le e o briefing de
    teste com os seis formatos; as familias e o passo 2 ficam para a tela."""
    from desdobra.job import fases as mod_fases
    from desdobra.job import nucleo
    from desdobra.render import autoteste
    base = tmp_path_factory.mktemp('laco')
    fontes = base / 'origem-fontes'
    fap.gravar(fontes, 'autoteste.ttf', autoteste.gerar_fonte())
    job = base / 'job'
    nucleo.criar(job, tp._psd_hostil(base / 'origem' / 'kv.psd', autoteste.NOME_PS), 'c', fontes=[fontes])
    assert nucleo.proxima(job, todas=True).codigo == 0
    formatos = [ap.formato(i, w, h, rotacao=dict(ROT0)) for i, w, h in FORMATOS]
    arquivos.gravar_json_atomico(job / mb.ARQUIVO_FORMATOS, {'tipo': 'formatos_do_job', 'formatos': [
        {'id': f['id'], 'chave': f['chave'], 'campos': _campos(['image/jpeg', 'image/png'])} for f in formatos]})
    estado = nucleo.ler_estado(job)
    estado['fases']['specs']['hash_saidas'] = nucleo.hashes_das_saidas(
        job, next(f for f in mod_fases.ESTEIRA if f.id == 'specs'))
    nucleo.gravar_estado(job, estado)
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    ids = {c['nome']: c['identidade']['layer_id'] for c in laudo['camadas']}
    funcoes = {ids['fundo-sintetico']: 'fundo', ids[tp.NOME_FORM]: 'titulo',
               ids['quadrado-sintetico']: 'logo_principal', ids[tp.NOME_APOIO]: 'texto_de_apoio', ids['solto-sintetico']: 'fora_da_peca'}
    b = ap.briefing(funcoes=funcoes, formatos=formatos)
    b.pop('cabecalho')
    b.pop('job_id')
    arq = base / 'fixture.json'
    arq.write_text(json.dumps(b), encoding='utf-8')
    mb.importar_teste(job, arq)
    return {'job': job, 'funcoes': funcoes, 'logo': ids['quadrado-sintetico']}


@pytest.fixture
def job(modelo, tmp_path):
    destino = tmp_path / 'job'
    shutil.copytree(modelo['job'], destino)
    return destino


# ------------------------------------------------------------------ as rotas da tela
def _passo_2(funcoes):
    return {'funcoes': {str(k): {'funcao': v, 'observacao': None} for k, v in funcoes.items()},
            'design': {f: {'regra': r, 'x': x, 'y': y} for f, (r, x, y) in USADAS.items()}}


def _ato(s, biscoito, nome, dados):
    """Pedido e Confirmar de um ato curto da janela; devolve o codigo do Confirmar."""
    codigo, p = tte._pedir_ato(s, biscoito, nome=nome, dados=dados)
    assert codigo == 200, (nome, codigo)
    c2, _cab, corpo = tte._escrever(s, '/api/ato/confirmar', {'pedido': p['pedido'], 'resposta': 'confirmar'},
                                    cookie=biscoito)
    assert c2 == 200, (nome, c2, corpo)
    return c2


def _ato_longo(s, biscoito, nome, dados):
    """Pedido (a tarefa do preparo) e Confirmar (a tarefa do ato) de um ato longo; devolve a vista da tarefa no fim."""
    codigo, _c, corpo = tte._escrever(s, '/api/ato/pedir', {'ato': nome, 'dados': dados}, cookie=biscoito)
    assert codigo == 202, (nome, codigo, corpo)  # numero-neutro: codigo HTTP
    v = tar._esperar_fim(s, biscoito, json.loads(corpo)['tarefa'])
    assert v['situacao'] == 'feita', (nome, v)
    codigo, fim = tar._confirmar(s, biscoito, v['resposta']['pedido'])
    assert codigo == 202, (nome, codigo)  # numero-neutro: codigo HTTP
    assert fim['situacao'] == 'feita', (nome, json.dumps(fim, ensure_ascii=False))
    return fim


def _familia_de(conteudo, fid):
    return next(g for g, f in conteudo['familias'].items() if fid in f['formatos'])


def _id_do_logo(conteudo, gid):
    base = conteudo['editar']({'familia': gid, 'versao': None, 'edicoes': []})
    return next(e['id'] for e in base['membros'][0]['palco']['elementos'] if e['funcao'] == 'logo_principal')


def _escolhas(conteudo):
    """A versao e as edicoes de cada familia: nas familias vertical e quadrada, o logo apagado pelo DA."""
    escolhas = {}
    sem_logo = {_familia_de(conteudo, 'v1'), _familia_de(conteudo, 'q1')}
    for gid, f in conteudo['familias'].items():
        edicoes = [{'elemento': _id_do_logo(conteudo, gid), 'acao': 'apagar'}] if gid in sem_logo else []
        escolhas[gid] = {'versao': f['versoes'][0] if f['versoes'] else None, 'confirmada': False,
                         'edicoes': edicoes}
    return escolhas


def _vista(job):
    from desdobra.tela import rascunho as tr
    dados = json.loads((job / tr.ARQUIVO).read_text(encoding='utf-8'))
    return {k: dados[k] for k in ('job_id', 'laudo_sha256', 'familias', 'funcoes', 'cobertas', 'design',
                                  'design_camadas') if k in dados}


def _preparar_pelas_rotas(s, biscoito, job, modelo, conteudo):
    """O briefing do DA pelas rotas que a pagina usa: o rascunho, o modo de dados, as tres familias e o salvar."""
    escolhas = _escolhas(conteudo)
    corpo = dict({'job_id': s.job_id, 'laudo_sha256': s.laudo_sha256, 'familias': escolhas},
                 **_passo_2(modelo['funcoes']))
    assert tte._escrever(s, '/api/rascunho', corpo, cookie=biscoito)[0] == 200
    _ato(s, biscoito, 'modo_dados', {'modo': 'c'})
    for gid, f in escolhas.items():
        _ato(s, biscoito, 'familia', {'familia': gid, 'versao': f['versao'], 'edicoes': f['edicoes'], 'quebras': []})
    _ato(s, biscoito, 'salvar', {'rascunho': _vista(job)})
    return escolhas


# ------------------------------------------------------------------ medidas
def _sha(job, rel):
    arq = job / rel
    return arquivos.sha256_arquivo(arq) if arq.is_file() else None


def _shas_do_render(job):
    return {fid: {n: _sha(job, Path('render') / fid / n) for n in ARQUIVOS_DO_RENDER} for fid in IDS}


def _shas_da_derivacao(job):
    return {fid: _sha(job, nd.PASTA / ('%s.json' % fid)) for fid in IDS}


def _diferencas_da_aprovacao(job, registros):
    """{formato: campos que mudaram desde o registro} pela medida da critica do plano (aprovacao.diferencas com os
    hashes de agora), sem o portao com aprovacao=True."""
    b = mb.ler(job)
    saida = {}
    for fid in IDS:
        atual = portao.hashes_do_formato(job, fid, portao.impressao_do_formato(job, b, fid))
        saida[fid] = aprovacao.diferencas(registros['formatos'][fid], registros['job_id'], atual)
    return saida


def _caminhos(job):
    """{formato: o caminho da derivacao gravada} (escala do KV, regras, galeria)."""
    return {fid: contratos.ler(job / nd.PASTA / ('%s.json' % fid), nd.ESQUEMA)['caminho'] for fid in IDS}


def _mudou_contra_gravada(job, painel):
    """{formato: [(tipo, frase, caixa "depois" do item, caixa do elemento na derivacao gravada)]} de todos os itens de
    "o que mudou", e o caminho e a situacao da derivacao gravada: o que a tela diz contra o que foi gravado."""
    saida = {}
    for fid in AFETADOS:
        d = contratos.ler(job / nd.PASTA / ('%s.json' % fid), nd.ESQUEMA)
        caixas = {e['id']: e.get('caixa') for e in d['elementos']}
        itens = (painel[fid].get('mudou') or {}).get('itens') or []
        saida[fid] = {'gravada': [d['caminho'], d['situacao']],
                      'itens': [[i['tipo'], i['frase'], i.get('depois'), caixas.get(i.get('elemento'))]
                                for i in itens]}
    return saida


def _derivacao_sem_funcao(job, fid):
    """O caminho, a situacao e os elementos (id, caixa e camadas) da derivacao gravada, sem a funcao: o que a troca de
    funcao do logo, com a mesma regra e a mesma ancora, deixa igual."""
    d = contratos.ler(job / nd.PASTA / ('%s.json' % fid), nd.ESQUEMA)
    return [d['caminho'], d['situacao'],
            [[e['id'], e.get('caixa'), e.get('layer_ids')] for e in d['elementos']]]


def _painel(job):
    return {f['id']: f for f in te.painel_dos_formatos(job)['formatos']}


def _contar_cadeia(job, ids_do_logo):
    """Os elementos de cada derivacao que vem do logo (o que a troca de funcao mexe)."""
    saida = {}
    for fid in IDS:
        d = contratos.ler(job / nd.PASTA / ('%s.json' % fid), nd.ESQUEMA)
        saida[fid] = [e['funcao'] for e in d['elementos'] if ids_do_logo in (e.get('layer_ids') or [])]
    return saida


# ------------------------------------------------------------------ a pagina
def _clicar(pg, seletor):
    pg.evaluate('(s) => { const b = document.querySelector(s); if (!b) throw new Error(s); b.click(); }', seletor)


def _salvo(pg):
    tp._esperar(pg, PARADO)
    tp._esperar(pg, SALVO)


def _confirmar_na_janela(pg, seletor):
    tp._esperar(pg, '() => document.querySelector(%s).disabled ? "" : "1"' % json.dumps(seletor))
    _clicar(pg, seletor)
    tp._esperar(pg, '() => document.getElementById("confirmacao").open ? "1" : ""')
    pg.evaluate('''() => Array.from(document.querySelectorAll("#confirmacao button"))
        .find(b => b.textContent === "Confirmar").click()''')
    tp._esperar(pg, '() => document.documentElement.dataset.estadoAto === "feito" ? "1" : ""')


def _abrir_painel(pg):
    _clicar(pg, '#passos [data-passo=formatos]')
    tp._esperar(pg, '() => document.documentElement.dataset.painel || ""', 'pronto')


def _situacoes_na_tela(pg):
    return dict(pg.evaluate('() => Array.from(document.querySelectorAll("#lista-formatos .linha-formato"))'
                            '.map(l => [l.dataset.formato, l.dataset.situacao])'))


def _o_que_mudou_na_tela(pg):
    """{formato: [frases de "o que mudou"]} abrindo o detalhe de cada linha do painel."""
    saida = {}
    for fid in IDS:
        _clicar(pg, '.linha-formato[data-formato="%s"] .linha-abrir' % fid)
        tp._esperar(pg, '() => document.getElementById("formato-detalhe").dataset.formato', fid)
        saida[fid] = tp._textos(pg, '#formato-detalhe .mudou-item')
    return saida


def _corrigir_na_pagina(pg, s, job, conteudo, modelo, medidas, entradas_antes):
    """O DA, na pagina: troca a funcao do logo, da a regra e a ancora da funcao nova, confirma as tres familias de novo
    e clica em "Salvar e seguir"."""
    import test_tela_galeria as tg
    inicio = time.monotonic()
    _clicar(pg, '#passos [data-passo=funcoes]')
    _clicar(pg, '#arvore button[data-camada="%d"]' % modelo['logo'])
    _clicar(pg, '#detalhe button[data-funcao="%s"]' % NOVA_FUNCAO)
    _salvo(pg)
    _clicar(pg, '#passos [data-passo=design]')
    chave = '#resumo-design [data-chave="f%s"]' % NOVA_FUNCAO
    _clicar(pg, chave + ' .funcao-ds-topo')
    regra, x, y = NOVA_REGRA
    _clicar(pg, chave + ' button[data-regra="%s"]' % regra)
    _clicar(pg, chave + ' button[data-x="%s"][data-y="%s"]' % (x, y))
    _salvo(pg)
    medidas['passo_2_s'] = time.monotonic() - inicio
    # decisoes-v1.md, 175: a mudanca do passo 2 tira a confirmacao de todas as familias
    inicio = time.monotonic()
    _clicar(pg, '#passos [data-passo=pecas]')
    tp._esperar(pg, '() => document.getElementById("palco").dataset.pronto || ""')
    for fid in ('h1', 'v1', 'q1'):
        tg._abrir(pg, conteudo['estado'], fid)
        tp._esperar(pg, '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""')
        _confirmar_na_janela(pg, '#confirmar-familia')
    medidas['confirmar_familias_s'] = time.monotonic() - inicio
    inicio = time.monotonic()
    # com as familias confirmadas de novo, a tela pede outro "Salvar e seguir": o botao ligado (correcao do D1)
    tp._esperar(pg, '() => document.getElementById("salvar-seguir").disabled ? "" : "1"')
    medidas['salvar_na_pagina'] = True
    # o clique do DA (o mesmo passo de test_editor_mestre). O estadoAto ja vem "feito" da ultima familia confirmada,
    # entao o fim do salvar e esperado no proprio job: a entrada nova do historico
    _confirmar_na_janela(pg, '#salvar-seguir')
    _esperar_entrada_nova(job, entradas_antes)
    tp._esperar(pg, '() => document.getElementById("salvo").hidden ? "" : "1"')
    medidas['salvar_s'] = time.monotonic() - inicio


def _esperar_entrada_nova(job, antes, teto_s=TETO_PREPARO_S):
    limite = time.monotonic() + teto_s
    while len(historico.ler(job)['entradas']) <= antes:
        assert time.monotonic() < limite, 'o "Salvar e seguir" nao gravou entrada nova no historico'
        time.sleep(0.2)  # numero-neutro: intervalo de leitura do teste


def _renderizar_afetados_na_pagina(pg, medidas):
    inicio = time.monotonic()
    _clicar(pg, '#renderizar-afetados')
    tp._esperar(pg, JS_DIALOGO, teto_s=TETO_PREPARO_S)
    lista = tp._textos(pg, '#confirmacao-extra li')
    pg.evaluate('() => document.querySelector("#confirmacao [data-resposta=sim]").click()')
    tp._esperar(pg, JS_ATO, 'feito', teto_s=TETO_RENDER_S)
    medidas['render_afetados_s'] = time.monotonic() - inicio
    return lista


def _aprovar_na_pagina(pg, formatos, medidas):
    inicio = time.monotonic()
    for fid in formatos:
        _clicar(pg, '.linha-formato[data-formato="%s"] .linha-marca' % fid)
    _clicar(pg, '#aprovar-marcados')
    tp._esperar(pg, JS_DIALOGO, teto_s=TETO_PREPARO_S)
    nomes = tp._textos(pg, '#confirmacao-extra .final-nome')
    pg.evaluate('() => document.querySelector("#confirmacao [data-resposta=sim]").click()')
    tp._esperar(pg, JS_ATO, 'feito', teto_s=120)  # numero-neutro: teto do teste para a aprovacao
    medidas['aprovar_afetados_s'] = time.monotonic() - inicio
    return nomes


# ------------------------------------------------------------------ o roteiro
def test_laco_de_correcao_pela_tela(job, modelo):
    from playwright.sync_api import sync_playwright

    from desdobra.chromium import navegador
    medidas = {}
    conteudo = te.montar(job)
    familias = {fid: _familia_de(conteudo, fid) for fid in IDS}
    assert len(set(familias.values())) == 3, conteudo['familias']  # numero-neutro: tres familias
    for grupo in (HORIZONTAIS, VERTICAIS, QUADRADOS):
        assert len({familias[fid] for fid, _w, _h in grupo}) == 1, (grupo, familias)
    s = ts.ServidorTela(conteudo, pasta=job, modo_teste=True, atos=ta.atos_do_job(job, conteudo=conteudo)).iniciar()
    try:
        biscoito = tts._entrar(s)
        _preparar_pelas_rotas(s, biscoito, job, modelo, conteudo)
        # o logo so existe nos dois horizontais
        cadeia = _contar_cadeia(job, modelo['logo'])
        assert {fid: bool(v) for fid, v in cadeia.items()} == {fid: fid in AFETADOS for fid in IDS}, cadeia
        # o render e a aprovacao dos seis pelos atos da tela
        inicio = time.monotonic()
        fim = _ato_longo(s, biscoito, 'render', {'formatos': list(IDS)})
        medidas['render_seis_s'] = time.monotonic() - inicio
        medidas['render_por_formato_s'] = fim['resposta']['tempos_s'] if fim.get('resposta') else None
        inicio = time.monotonic()
        _ato_longo(s, biscoito, 'aprovar', {'formatos': list(IDS)})
        medidas['aprovar_seis_s'] = time.monotonic() - inicio
    finally:
        s.parar()
    assert {f: v['situacao'] for f, v in nucleo_aprovar.situacao(job).items()} == {f: 'aprovado' for f in IDS}
    registros = aprovacao.ler(job)
    render_antes = _shas_do_render(job)
    deriv_antes = _shas_da_derivacao(job)
    caminho_antes = _caminhos(job)
    entradas_antes = len(historico.ler(job)['entradas'])
    assert _diferencas_da_aprovacao(job, registros) == {f: [] for f in IDS}

    # a correcao na pagina, com a tela reaberta (um servidor novo, montado do zero)
    conteudo = te.montar(job)
    navegador.apontar_playwright()
    s = ts.ServidorTela(conteudo, pasta=job, modo_teste=True, atos=ta.atos_do_job(job, conteudo=conteudo)).iniciar()
    try:
        with sync_playwright() as pw:
            nav, pg = tp._pagina_da_tela(pw, s, 1600, 900)  # numero-neutro: janela do teste
            try:
                _abrir_painel(pg)
                assert _situacoes_na_tela(pg) == {f: 'aprovado' for f in IDS}
                _corrigir_na_pagina(pg, s, job, conteudo, modelo, medidas, entradas_antes)

                # ---- conferencias da secao 4, logo depois de "Salvar e seguir"
                entradas = historico.ler(job)['entradas']
                assert len(entradas) == entradas_antes + 1, entradas[entradas_antes:]
                marcados = entradas[-1]['formatos_afetados']
                deriv_depois = _shas_da_derivacao(job)
                regravados = sorted(f for f in IDS if deriv_depois[f] != deriv_antes[f])
                caidas = _diferencas_da_aprovacao(job, registros)
                painel = _painel(job)
                _abrir_painel(pg)
                na_tela = _situacoes_na_tela(pg)
                mudou = _o_que_mudou_na_tela(pg)
                medidas['mudou_contra_gravada'] = _mudou_contra_gravada(job, painel)
                medidas.update({
                    'marcados': marcados, 'regravados': regravados,
                    'caidas': {f: c for f, c in caidas.items() if c},
                    'pede_render': sorted(f for f, v in painel.items() if v['pede_render']),
                    'situacao_no_painel': {f: v['situacao'] for f, v in painel.items()},
                    'situacao_na_tela': na_tela, 'o_que_mudou': mudou,
                    'render_igual_antes_do_render': sorted(
                        f for f in IDS if _shas_do_render(job)[f] == render_antes[f])})
                assert marcados == AFETADOS, marcados
                assert regravados == AFETADOS, regravados
                assert sorted(f for f, c in caidas.items() if c) == AFETADOS, caidas
                assert all(c == ['impressao_formato'] for f, c in caidas.items() if c), caidas
                assert medidas['pede_render'] == AFETADOS, painel
                assert all(painel[f]['situacao'] == 'aprovacao_caida' for f in AFETADOS), painel
                assert all(painel[f]['situacao'] == 'aprovado' for f in OUTROS), painel
                assert na_tela == {f: painel[f]['situacao'] for f in IDS}
                # o "o que mudou" de cada afetado e exatamente a mudanca real (a troca de funcao), e nada nos outros
                assert {f: mudou[f] for f in AFETADOS} == {f: [FRASE_DA_TROCA] for f in AFETADOS}, mudou
                assert {f: [i[:2] for i in v['itens']] for f, v in medidas['mudou_contra_gravada'].items()} == \
                    {f: [['funcao', FRASE_DA_TROCA]] for f in AFETADOS}, medidas['mudou_contra_gravada']
                assert not any(mudou[f] for f in OUTROS), mudou
                assert _shas_do_render(job) == render_antes  # nada renderizado sozinho (Q3)

                # ---- "Renderizar os afetados" e a aprovacao de novo so dos dois
                lista = _renderizar_afetados_na_pagina(pg, medidas)
                assert sorted(lista) == sorted('%dx%d' % (w, h) for _f, w, h in HORIZONTAIS), lista
                render_depois = _shas_do_render(job)
                medidas['render_mudou'] = sorted(f for f in IDS if render_depois[f] != render_antes[f])
                assert medidas['render_mudou'] == AFETADOS, medidas['render_mudou']
                # o render em dia: a aprovacao velha continua caida, sem pedir render, e o formato pode ser aprovado
                assert _situacoes_na_tela(pg) == {f: 'aprovacao_caida' if f in AFETADOS else 'aprovado' for f in IDS}
                painel = _painel(job)
                assert all(not painel[f]['pede_render'] and painel[f]['pode_aprovar'] for f in AFETADOS), painel
                nomes = _aprovar_na_pagina(pg, AFETADOS, medidas)
                assert sorted(nomes) == sorted(lista), nomes
                assert _situacoes_na_tela(pg) == {f: 'aprovado' for f in IDS}
                medidas['o_que_mudou_depois'] = _o_que_mudou_na_tela(pg)
            finally:
                nav.close()
        contagem = dict(s.contagem)
    finally:
        s.parar()
    assert {f: v['situacao'] for f, v in nucleo_aprovar.situacao(job).items()} == {f: 'aprovado' for f in IDS}
    depois = aprovacao.ler(job)
    # os registros dos quatro de fora sao os mesmos do comeco; os dois afetados tem registro novo
    assert {f: depois['formatos'][f] == registros['formatos'][f] for f in IDS} == {f: f in OUTROS for f in IDS}
    assert _diferencas_da_aprovacao(job, depois) == {f: [] for f in IDS}
    assert {f: _shas_do_render(job)[f] == render_antes[f] for f in IDS} == {f: f in OUTROS for f in IDS}
    assert _shas_da_derivacao(job) == deriv_depois
    assert not any(medidas['o_que_mudou_depois'].values()), medidas['o_que_mudou_depois']
    assert contagem['proibido'] == 0 and contagem['csrf_recusado'] == 0 and contagem['dado_recusado'] == 0, contagem
    medidas['funcao_do_logo'] = _contar_cadeia(job, modelo['logo'])
    medidas['caminho'] = {f: (caminho_antes[f], _caminhos(job)[f]) for f in IDS}
    _gravar_medicao(medidas)


def _corrigir_pelas_rotas(s, biscoito, job, modelo, escolhas):
    """A troca da funcao do logo no passo 2 (com a regra e a ancora da funcao nova) e as tres familias confirmadas de
    novo, pelas rotas que a pagina usa."""
    funcoes = dict(modelo['funcoes'])
    funcoes[modelo['logo']] = NOVA_FUNCAO
    p2 = _passo_2(funcoes)
    p2['design'][NOVA_FUNCAO] = dict(zip(('regra', 'x', 'y'), NOVA_REGRA))
    corpo = dict({'job_id': s.job_id, 'laudo_sha256': s.laudo_sha256, 'familias': escolhas}, **p2)
    assert tte._escrever(s, '/api/rascunho', corpo, cookie=biscoito)[0] == 200
    for gid, f in escolhas.items():
        _ato(s, biscoito, 'familia', {'familia': gid, 'versao': f['versao'], 'edicoes': f['edicoes'], 'quebras': []})


def test_salvar_e_seguir_volta_depois_de_mudar_o_passo_2(job, modelo):
    """Repro minima do D1 do E1, sem render: briefing salvo pela tela; o DA troca a funcao do logo no passo 2 (e da a
    regra e a ancora da funcao nova) e confirma as tres familias de novo, com a mesma versao e as mesmas edicoes. O
    briefing gravado ainda tem a funcao velha, entao a tela pede outro "Salvar e seguir" (salvo False). Antes da
    correcao, ela dizia "Briefing salvo" e a pagina deixava o botao desligado."""
    from desdobra.briefing import salvar
    conteudo = te.montar(job)
    s = ts.ServidorTela(conteudo, pasta=job, modo_teste=True, atos=ta.atos_do_job(job, conteudo=conteudo)).iniciar()
    try:
        with _preparo():
            biscoito = tts._entrar(s)
            _corrigir_pelas_rotas(s, biscoito, job, modelo, _preparar_pelas_rotas(s, biscoito, job, modelo, conteudo))
            assert salvar.pendencias(job, conteudo) == []
            gravada = {x['layer_id']: x['funcao']['valor'] for x in mb.ler(job)['funcoes']}[modelo['logo']]
            assert gravada == 'logo_principal'
            familias = {g: f['formatos'] for g, f in conteudo['familias'].items()}
        # a conferencia do defeito, a unica que levanta AssertionError
        assert salvar.situacao_na_tela(job, familias)['salvo'] is False
    finally:
        s.parar()


def test_o_que_mudou_bate_com_a_derivacao_gravada(job, modelo):
    """Repro minima do D2 do E1, sem render: briefing salvo pela tela; troca da funcao do logo (logo principal para
    selo, mesma regra e mesma ancora), as familias confirmadas de novo e o salvar pela rota da tela. A derivacao
    gravada dos dois horizontais fica no mesmo caminho (escala do KV e regras), com a mesma situacao e as mesmas
    caixas, e so a funcao do logo muda (o preparo confere isso); o "o que mudou" gravado tem um item so em cada
    afetado, o da troca de funcao. Antes da correcao, ele dizia que o formato voltou para o DA, que as caixas vinham da
    galeria e que o titulo, o logo e o apoio andaram ate 47 px."""
    conteudo = te.montar(job)
    s = ts.ServidorTela(conteudo, pasta=job, modo_teste=True, atos=ta.atos_do_job(job, conteudo=conteudo)).iniciar()
    try:
        with _preparo():
            biscoito = tts._entrar(s)
            escolhas = _preparar_pelas_rotas(s, biscoito, job, modelo, conteudo)
            antes = {f: _derivacao_sem_funcao(job, f) for f in AFETADOS}
            _corrigir_pelas_rotas(s, biscoito, job, modelo, escolhas)
            _ato(s, biscoito, 'salvar', {'rascunho': _vista(job)})
    finally:
        s.parar()
    with _preparo():
        assert historico.ler(job)['entradas'][-1]['formatos_afetados'] == AFETADOS
        # a derivacao gravada so mudou a funcao do logo: o "o que mudou" certo e o item da troca, sozinho
        assert {f: _derivacao_sem_funcao(job, f) for f in AFETADOS} == antes
        r = _mudou_contra_gravada(job, _painel(job))
    # a conferencia do defeito, a unica que levanta AssertionError
    assert {f: [i[1] for i in v['itens']] for f, v in r.items()} == {f: [FRASE_DA_TROCA] for f in AFETADOS}, r


@contextlib.contextmanager
def _preparo():
    """O preparo de um repro: a falha dele vira pytest.fail, com a mensagem de que o preparo falhou antes da
    conferencia do defeito."""
    try:
        yield
    except AssertionError as e:
        pytest.fail('o preparo do repro falhou antes da conferencia do defeito: %s' % e)


# ------------------------------------------------------------------ registro das medidas
def _gravar_medicao(m):
    destino = os.environ.get(VARIAVEL_MEDICAO)
    if not destino:
        return
    acertos = len(set(m['marcados']) & set(AFETADOS))
    mantidas = [f for f in OUTROS if f not in m['caidas']]
    linhas = [
        'Medicao do E1 (M7b): roteiro do laco de correcao pela tela, %s.' % datetime.now().strftime('%Y-%m-%d %H:%M'),
        'Job sintetico (PSD de test_tela_palco, fonte de autoteste), modo de teste da tela (meio fixture_de_teste /',
        'medicao). Seis formatos em tres familias; o logo so existe nos dois horizontais (h1 e h2).',
        '%s, Python %s.' % (platform.platform(), platform.python_version()),
        '',
        'Afetados marcados no historico: %s; esperados: %s.' % (', '.join(m['marcados']), ', '.join(AFETADOS)),
        'Precisao %.0f%%, cobertura %.0f%%.' % (100.0 * acertos / max(len(m['marcados']), 1),
                                                100.0 * acertos / len(AFETADOS)),
        'Derivacoes regravadas pelo salvar: %s.' % ', '.join(m['regravados']),
        'Aprovacoes caidas (aprovacao.diferencas): %s.' % json.dumps(m['caidas'], ensure_ascii=False, sort_keys=True),
        'Aprovacoes mantidas nos nao afetados: %d de %d (%.0f%%).' % (len(mantidas), len(OUTROS),
                                                                    100.0 * len(mantidas) / len(OUTROS)),
        'Pedem render no painel: %s.' % ', '.join(m['pede_render']),
        'Situacao na pagina depois do salvar: %s.' % json.dumps(m['situacao_na_tela'], sort_keys=True),
        'Itens de "o que mudou" na pagina por formato: %s.' % json.dumps(
            {f: len(v) for f, v in m['o_que_mudou'].items()}, sort_keys=True),
    ]
    for f in AFETADOS:
        linhas.append('  %s: %s' % (f, ' | '.join(m['o_que_mudou'][f])))
    linhas.append('Itens alem da troca de funcao (a derivacao gravada so mudou a funcao): %s.' % json.dumps(
        {f: len([x for x in m['o_que_mudou'][f] if x != FRASE_DA_TROCA]) for f in AFETADOS}, sort_keys=True))
    linhas += [
        'Formatos com master, render.json e contrato de sha igual do comeco ate antes do novo render: %d de %d.'
        % (len(m['render_igual_antes_do_render']), len(IDS)),
        'Formatos com render novo depois de "Renderizar os afetados": %s.' % ', '.join(m['render_mudou']),
        'Entradas novas em historico/indice.json: 1.',
        'Caminho da derivacao (antes, depois): %s.' % json.dumps(m['caminho'], sort_keys=True),
        '"O que mudou" contra a derivacao gravada (tipo, frase, caixa do item, caixa gravada):',
        json.dumps(m['mudou_contra_gravada'], ensure_ascii=False, sort_keys=True, indent=1),
        'Funcao do elemento do logo em cada formato no fim: %s.' % json.dumps(m['funcao_do_logo'], sort_keys=True),
        'Salvar e seguir pelo clique na pagina: %s.' % ('sim' if m['salvar_na_pagina'] else 'nao'),
        '',
        'Tempos (relogio do teste, time.monotonic; robo, nunca tempo de DA):',
        '  render dos seis pelo ato da tela: %.1f s; por formato: %s' % (
            m['render_seis_s'], json.dumps(m['render_por_formato_s'], sort_keys=True)),
        '  aprovacao dos seis: %.1f s' % m['aprovar_seis_s'],
        '  passo 2 na pagina (funcao e Design system): %.1f s' % m['passo_2_s'],
        '  confirmar as tres familias de novo: %.1f s' % m['confirmar_familias_s'],
        '  Salvar e seguir (com a derivacao seletiva): %.1f s' % m['salvar_s'],
        '  Renderizar os afetados: %.1f s' % m['render_afetados_s'],
        '  aprovar os dois de novo: %.1f s' % m['aprovar_afetados_s'],
        '',
    ]
    Path(destino).parent.mkdir(parents=True, exist_ok=True)
    Path(destino).write_text('\n'.join(linhas), encoding='utf-8', newline='\n')
