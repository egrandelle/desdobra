# -*- coding: utf-8 -*-
"""0.9.6: a aprovacao do DA e soberana, a caixa do texto editado segue as linhas dele e os valores de spec se
confirmam em lote (pedido do Duda em 17/11/2026, depois de testar a 0.9.5).

Criterios de pronto cobertos aqui:
  1. Aprovacao soberana: a familia confirmada pelo DA com "Pede ajuste" (sobreposicao, validacao do motor que
     reprova, texto que passa da borda) sai do "Salvar e seguir" derivada, com o registro aprovado_pelo_da_com_aviso,
     e chega ao passo 5 com "Layout pronto" e o aviso aceito; o contrato do render sai sem bloqueio, e o texto editado
     que passa da borda e cortado nela, com registro. O formato sem layout de uma familia confirmada diz o motivo real.
     Na pagina, "Confirmar familia" fica ligado com o texto na borda, e depois da confirmacao a marca do membro vira
     "Aprovado por você", sem cor de erro.
  2. Caixa das linhas do DA: o texto editado de 4 para 2 linhas tem a caixa de 2 linhas na previa, na conferencia e na
     derivacao gravada, com a mesma escala; o texto em 1 linha descido no 970x250 nao acusa "sai do formato"; alinhar na
     base leva a ultima linha do DA a margem. Na pagina, o rotulo tracejado tem a altura da tinta.
  3. Specs em lote: o ato spec_valores grava uma acao 'confirmar' por valor, igual a do botao de um valor, com um
     Disparo so; recusa id repetido, vazio, inexistente ou divergente, e a folha que mudou no meio. Na pagina, um
     cartao por formato, nada marcado, "Marcar todos" e "Confirmar os marcados" com a janela que lista cada valor.
Tudo sintetico: o KV do relato da 0.9.4 (test_tela_revisao_094), os KVs A e B de testes/sinteticos/kv_a_b.py e as
folhas de spec de test_specs_apoio, com a fonte de autoteste do motor."""
import sys

import pytest

import test_tela_previa_igual_ao_salvar as tpi
import test_tela_revisao_094 as r94
from desdobra import contratos
from desdobra.derivacao import proposta
from desdobra.render import derivado as rd
from desdobra.render import execucao
from desdobra.tela import estado as te
from test_tela_lido import PROIBIDOS, _ato, _servidor, job_divergente, job_spec  # noqa: F401
from test_tela_revisao_094 import relato  # noqa: F401

import test_tela_escrita as tte  # noqa: E402

ambiente_limpo = tte.ambiente_limpo
W970, H970 = 970, 250  # numero-neutro: o formato do relato


def _previa_970(conteudo, edicoes):
    gid = next(g for g, f in conteudo['familias'].items() if 'f970x250' in f['formatos'])
    r = conteudo['editar']({'familia': gid, 'versao': None, 'edicoes': edicoes})
    return next(m for m in r['membros'] if m['formato'] == 'f970x250')


def _caixa(m, eid):
    return next(e['caixa'] for e in m['palco']['elementos'] if e['id'] == eid)


# ------------------------------------------------------------------ 2. a caixa das linhas do DA
def test_caixa_do_texto_editado_encolhe_com_as_linhas_do_da(relato, tmp_path):
    job = r94._copia(relato, tmp_path)
    conteudo = te.montar(job)
    gid = next(g for g, f in conteudo['familias'].items() if 'f970x250' in f['formatos'])
    el = r94._titulo(conteudo, gid)
    kv = _caixa(_previa_970(conteudo, []), el)
    duas = _previa_970(conteudo, [{'elemento': el, 'acao': 'texto', 'texto': 'HAX O\nHOAXAV'}])
    uma = _previa_970(conteudo, [{'elemento': el, 'acao': 'texto', 'texto': 'HAX O'}])
    c2, c1 = _caixa(duas, el), _caixa(uma, el)
    a_kv, a2, a1 = kv[3] - kv[1], c2[3] - c2[1], c1[3] - c1[1]
    # 4 linhas no KV, 2 e 1 do DA: a altura soma uma entrelinha por linha (decisao 196), em volta da ancora
    assert a2 < a_kv * 0.5 and a1 < a2 * 0.5, (a_kv, a2, a1)
    assert c2[1] == pytest.approx(c1[1], abs=1) and abs(c2[1] - kv[1]) < 2, (kv, c2, c1)
    # a escala do texto nao muda (a caixa de geometria continua dando a transformacao)
    esc = {m: next(e['escala'] for e in x['palco']['elementos'] if e['id'] == el)
           for m, x in (('kv', _previa_970(conteudo, [])), ('duas', duas))}
    assert esc['duas'] == pytest.approx(esc['kv'], rel=1e-4)
    assert not duas['falhas'] and not uma['falhas']


def test_texto_em_uma_linha_descido_nao_acusa_fora_do_formato_e_salva_derivado(relato, tmp_path):
    job = r94._copia(relato, tmp_path)
    conteudo = te.montar(job)
    gid = next(g for g, f in conteudo['familias'].items() if 'f970x250' in f['formatos'])
    el = r94._titulo(conteudo, gid)
    ed = [{'elemento': el, 'acao': 'texto', 'texto': 'HAX O'}, {'elemento': el, 'acao': 'mover', 'dx': 0.0, 'dy': 0.3}]
    m = _previa_970(conteudo, ed)
    # antes da 0.9.6: "O título sai do formato." e "A conferência do motor reprova esta versão." pela caixa de 4 linhas
    assert m['falhas'] == [] and m['validacoes_reprovadas'] == [], m['falhas']
    c = _caixa(m, el)
    assert c[3] < H970 and c[3] - c[1] < 40, c  # numero-neutro: uma linha em corpo de 970x250
    r94._gravar(job, 'HAX O', dy=0.3)
    d = r94._deriv(job, 'f970x250')
    x = r94._editado(d, relato['layer_id'])
    assert d['situacao'] == 'derivado'
    assert not [v for v in d['validacoes'] if v.get('resultado') == 'reprova'], d['validacoes']
    assert not any(r['codigo'] == proposta.CODIGO_APROVADO_COM_AVISO for r in d['registros'])
    # a caixa gravada e a das linhas do DA, a mesma da previa e a da tinta medida (caixa_texto_editado)
    assert x['caixa'] == pytest.approx(c, abs=0.05) and x['caixa'] == pytest.approx(x['caixa_texto_editado'], abs=0.05)


def test_alinhar_na_base_leva_a_ultima_linha_do_da_a_margem(relato, tmp_path):
    job = r94._copia(relato, tmp_path)
    conteudo = te.montar(job)
    gid = next(g for g, f in conteudo['familias'].items() if 'f970x250' in f['formatos'])
    el = r94._titulo(conteudo, gid)
    m = _previa_970(conteudo, [{'elemento': el, 'acao': 'texto', 'texto': 'HAX O\nHOAXAV'},
                               {'elemento': el, 'acao': 'alinhar', 'alvo': 'base', 'referencia': 'margem'}])
    assert _caixa(m, el)[3] == pytest.approx(m['quadro']['margem'][3], abs=0.05), (_caixa(m, el), m['quadro'])
    assert m['falhas'] == []


@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
def test_rotulo_do_texto_editado_tem_a_altura_da_tinta_no_palco(relato, tmp_path):
    import test_tela_edicao as ted
    js = '''i => {
      const r = document.querySelector('#palco .rotulo[data-elemento="' + i + '"]').getBoundingClientRect();
      const t = document.querySelector('#palco .recorte[data-elemento="' + i + '"] .texto').dataset.caixaTinta
        .split(',').map(parseFloat);
      const k = parseFloat(/scale\\(([0-9.e-]+)\\)/.exec(document.querySelector('#palco .mundo').style.transform)[1]);
      return {rotulo: r.height / k, tinta: t[3] - t[1]};
    }'''
    vista = {}

    def corpo(pg, job, gid, titulo, _logo):
        vista['antes'] = pg.evaluate(js, titulo)
        r94._aplicar_no_editor(pg, ted, titulo, 'HAX O\nHOAXAV')
        vista['depois'] = pg.evaluate(js, titulo)

    r94._na_tela_do_relato(relato, tmp_path, corpo, formato='f970x250')
    # antes: o rotulo de 4 linhas (182 px no 970x250); depois: o das 2 linhas do DA, da altura da tinta
    assert vista['depois']['rotulo'] == pytest.approx(vista['depois']['tinta'], abs=3), vista  # numero-neutro: px
    assert vista['depois']['rotulo'] < vista['antes']['rotulo'] * 0.6, vista


# ------------------------------------------------------------------ 1. a aprovacao soberana
def test_familia_confirmada_com_sobreposicao_fica_derivada_e_chega_ao_passo_5(tmp_path, monkeypatch):
    # o 800x600 do KV B (primeiro desenho do D6): o motor o devolve pela validacao obrigatoria, e a versao da galeria
    # escolhida pelo DA tem "Pede ajuste" (distancia e a validacao do motor que reprova)
    j = tpi._job(tmp_path, monkeypatch, 'b', tpi.CAIXAS_B_PRIMEIRO)
    conteudo = te.montar(j['job'])
    gid = tpi._familia_de(conteudo, 'p800')
    escolhida = None
    for v in conteudo['familias'][gid]['versoes']:
        m = tpi._previa(conteudo, gid, 'p800', tpi._escolhas(conteudo, gid, v)[gid])
        if m['validacoes_reprovadas'] and m['falhas']:
            escolhida = v
            break
    assert escolhida is not None
    conteudo = te.montar(j['job'])
    gravadas = tpi._salvar(j, conteudo, tpi._escolhas(conteudo, gid, escolhida))
    d = gravadas['p800']
    assert d['situacao'] == 'derivado' and d['devolucao'] is None, d.get('devolucao')
    aviso = next(r for r in d['registros'] if r['codigo'] == proposta.CODIGO_APROVADO_COM_AVISO)
    assert aviso['medidas']['validacoes'] and aviso['medidas']['falhas']
    # o passo 5: "Layout pronto", com o aviso aceito; nunca "Sem layout"
    linha = next(x for x in te.painel_dos_formatos(j['job'])['formatos'] if x['id'] == 'p800')
    assert linha['situacao'] == 'derivado' and linha['rotulo'] == 'Layout pronto', linha
    assert linha['avisos_aceitos'] and not any(x in ' '.join(linha['avisos_aceitos']) for x in PROIBIDOS), linha
    # o render monta o contrato sem bloqueio, e as outras familias seguem
    for fid in gravadas:
        assert rd.montar(j['job'], fid)[1] == [], fid


def test_texto_que_passa_da_borda_renderiza_cortado_com_registro(relato, tmp_path, pessoa):
    job = r94._copia(relato, tmp_path)
    r94._gravar(job, r94.ALTO)
    d = r94._deriv(job, 'f970x250')
    assert d['situacao'] == 'derivado'
    aviso = next(r for r in d['registros'] if r['codigo'] == proposta.CODIGO_APROVADO_COM_AVISO)
    assert aviso['medidas']['texto_na_borda'][0]['lados'] == ['base']
    contrato, bloqueios, conf = execucao.montar_contrato(job, 'f970x250')
    assert bloqueios == [] and contrato is not None, bloqueios
    assert any(r['codigo'] == rd.CORTADO_PELO_DA for r in contrato['registros'])
    rel = execucao.renderizar(job, disparo=pessoa.exigir('render'), formato='f970x250',
                              aceites=sorted({c['codigo'] for c in conf}))
    assert any(r['codigo'] == rd.CORTADO_PELO_DA for r in rel['registros'])
    linha = next(x for x in te.painel_dos_formatos(job)['formatos'] if x['id'] == 'f970x250')
    assert te.AVISO_TEXTO_CORTADO in linha['avisos_aceitos'], linha


def test_motivo_do_formato_sem_layout_na_familia_confirmada():
    from desdobra.derivacao import nucleo as nd
    # sem familia confirmada, a frase de sempre; confirmada, o motivo real (nunca "espera uma decisao sua")
    assert te.motivo_sem_layout(None, False) == te.MOTIVOS_DO_PAINEL['sem_derivacao']
    assert te.motivo_sem_layout(None, True) == te.SEM_LAYOUT_GRAVADO
    from desdobra import __version__
    dev = {'situacao': 'devolvido', 'devolucao': {'motivo': 'formato_sem_folha'}, 'registros': [],
           'motor_versao': __version__}
    assert te.motivo_sem_layout(dev, True) == te.SEM_LAYOUT_MOTIVO_DO_MOTOR
    # revisao adversarial: a devolucao gravada por uma versao de antes pede "Salvar e seguir" de novo
    assert te.motivo_sem_layout(dict(dev, motor_versao='0.9.5'), True) == te.SEM_LAYOUT_GRAVADO
    erro = dict(dev, registros=[{'codigo': 'erro_na_proposta', 'medidas': {'erro': 'KeyError'}}])
    assert te.motivo_sem_layout(erro, True) == te.SEM_LAYOUT_ERRO
    spec = dict(dev, devolucao={'motivo': nd.MOTIVO_SPEC_POR_CONFIRMAR})
    assert te.motivo_sem_layout(spec, True) == te.SPEC_POR_CONFIRMAR
    for frase in (te.SEM_LAYOUT_GRAVADO, te.SEM_LAYOUT_ERRO, te.SEM_LAYOUT_QUEBRA, te.SEM_LAYOUT_MOTIVO_DO_MOTOR,
                  te.AVISO_VALIDACAO_ACEITA, te.AVISO_TEXTO_CORTADO):
        assert 'Famílias. ' not in frase or 'Tire' in frase
        assert not any(x in frase for x in PROIBIDOS), frase
    # o aviso aceito: as frases da conferencia, sem repetir
    reg = {'codigo': proposta.CODIGO_APROVADO_COM_AVISO,
           'medidas': {'falhas': [{'texto': 'A e B passam a se sobrepor.'}, {'texto': 'A e B passam a se sobrepor.'}],
                       'validacoes': [{'nome': 'enquadramento'}], 'texto_na_borda': []}}
    assert te.avisos_aceitos({'registros': [reg]}) == ['A e B passam a se sobrepor.',
                                                       'Uma parte do elemento fica fora do formato.']
    # revisao adversarial: a falha generica da conferencia sai pela frase concreta de cada validacao, com o lado
    reg2 = {'codigo': proposta.CODIGO_APROVADO_COM_AVISO,
            'medidas': {'falhas': [{'codigo': te.CODIGO_VALIDACAO_GENERICA,
                                    'texto': 'A conferência do motor reprova esta versão.'}],
                        'validacoes': [{'nome': 'membro_dentro_do_canvas', 'elementos': ['f'],
                                        'medidas': {'membros': [{'membro': 1, 'lados': ['base']}]}}]}}
    d = {'registros': [reg2], 'elementos': [{'id': 'f', 'funcao': 'fundo'}]}
    assert te.avisos_aceitos(d) == ['Uma parte do fundo fica fora do formato, na base.']
    assert te.frase_da_validacao({'nome': 'inventario'}) == te.AVISO_VALIDACAO_ACEITA
    for v in te.FRASES_DA_VALIDACAO:
        frase = te.frase_da_validacao({'nome': v, 'elementos': ['f']}, {'f': 'titulo'})
        assert not any(x in frase for x in PROIBIDOS) and 'reprova' not in frase, frase


def test_entrega_poe_a_area_da_folha_como_aviso_no_formato_aprovado_com_aviso():
    from desdobra.entrega import validar
    assert validar.aprovado_com_aviso({'registros': [{'codigo': proposta.CODIGO_APROVADO_COM_AVISO}]})
    assert not validar.aprovado_com_aviso({'registros': [{'codigo': 'decisao_do_da'}]})
    assert not validar.aprovado_com_aviso(None)

    class Lim:
        valor = 2.0
        efeito_efetivo = 'reprova'

        def citacao(self):
            return {'chave': 'x'}
    c = validar._LimiteComAviso(Lim())
    assert c.efeito_efetivo == 'avisa' and c.valor == 2.0 and c.citacao() == {'chave': 'x'}


@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
def test_pagina_deixa_confirmar_com_o_texto_na_borda_e_a_marca_vira_aprovado_por_voce(relato, tmp_path):
    import test_tela_edicao as ted
    import test_tela_palco as tp
    vista = {}

    def corpo(pg, job, gid, titulo, _logo):
        ted._focar(pg, titulo)
        pg.keyboard.press('Enter')
        pg.evaluate('() => document.getElementById("ed-texto").click()')
        pg.fill('#ed-campo-texto', r94.ALTO)
        pg.evaluate('() => document.getElementById("ed-texto-aplicar").click()')
        tp._esperar(pg, '() => document.getElementById("editor-texto").hidden ? "1" : ""')
        ted._esperar_salvo(pg)
        tp._esperar(pg, '() => document.getElementById("texto-borda").hidden ? "" : "1"')
        vista['antes'] = pg.evaluate('''() => ({
            faixa: document.getElementById("texto-borda-texto").textContent,
            confirmar: document.getElementById("confirmar-familia").disabled,
            resumo: document.getElementById("resumo-edicao").textContent,
            marcas: Array.from(document.querySelectorAll('#membros-lista .membro[data-formato="f970x250"] .marca-aviso'))
              .map(s => [s.textContent, s.className])})''')
        pg.evaluate('() => document.getElementById("confirmar-familia").click()')
        tp._esperar(pg, '() => document.getElementById("confirmacao").open ? "1" : ""')
        pg.evaluate('''() => Array.from(document.querySelectorAll("#confirmacao button"))
            .find(b => b.textContent === "Confirmar").click()''')
        tp._esperar(pg, '() => document.documentElement.dataset.estadoAto === "feito" ? "1" : ""')
        tp._esperar(pg, '''() => document.querySelector('#membros-lista .membro[data-formato="f970x250"] .marca-aviso.aceito')
            ? "1" : ""''')
        vista['depois'] = pg.evaluate('''() => ({
            marcas: Array.from(document.querySelectorAll('#membros-lista .membro[data-formato="f970x250"] .marca-aviso'))
              .map(s => [s.textContent, s.className]),
            faixa: document.getElementById("texto-borda-texto").textContent})''')
        vista['gravada'] = ted._rascunho_gravado(job)['familias'][gid]

    r94._na_tela_do_relato(relato, tmp_path, corpo, formato='f970x250')
    antes, depois = vista['antes'], vista['depois']
    assert antes['confirmar'] is False, antes
    assert 'Você pode confirmar assim' in antes['faixa'] and 'Você pode confirmar assim' in antes['resumo'], antes
    assert any('forte' in c for _t, c in antes['marcas']), antes
    assert vista['gravada']['confirmada'] is True
    assert depois['marcas'] and all('aceito' in c and 'forte' not in c for _t, c in depois['marcas']), depois
    assert any(t == 'Aprovado por você' for t, _c in depois['marcas']), depois
    for texto in (antes['faixa'], antes['resumo'], depois['faixa']):
        assert not any(x in texto for x in PROIBIDOS), texto


# ------------------------------------------------------------------ 3. specs em lote
def test_lote_grava_uma_confirmacao_por_valor_com_um_disparo(job_spec):  # noqa: F811
    from desdobra.specs import importar, modelo
    lista = te.specs_pendentes(job_spec)
    lote = [x for x in lista if x['em_lote']]
    assert len(lote) >= 3 and all(x['grupo'] and x['grupo_nome'] for x in lote)  # numero-neutro: a folha PME
    nomes = {x['grupo_nome'] for x in lote}
    assert te.GRUPO_GERAL in nomes and not any('|' in n for n in nomes), nomes
    ids = [x['valor_id'] for x in lote[:3]]
    s = _servidor(job_spec)
    try:
        c1, c2, p = _ato(s, 'spec_valores', {'valor_ids': ids})
        assert (c1, c2) == (200, 200)
        assert '3 valores de spec' in p['texto'] and not any(x in p['texto'] + p['titulo'] for x in PROIBIDOS), p
    finally:
        s.parar()
    acoes = importar.ler_confirmacoes(job_spec)['acoes']
    assert [a['valor_id'] for a in acoes] == ids
    assert all(a['acao'] == 'confirmar' and a['meio'] == 'medicao' and a['por'] == 'fixture_de_teste' for a in acoes)
    assert len({a['em'] for a in acoes}) == 1 and [a['n'] for a in acoes] == [1, 2, 3]  # numero-neutro: ordem
    doc = contratos.ler(job_spec / 'specs' / 'rascunho.json', 'spec/1')
    idx = modelo.indice_de_valores(doc)
    assert all(idx[i][2]['situacao'] == 'confirmado' for i in ids)
    assert not set(ids) & {x['valor_id'] for x in te.specs_pendentes(job_spec)}
    from desdobra.entrega import portao
    assert portao.confirmacao_de_teste(job_spec) == 'confirmacao_de_fixture_de_teste'


def test_lote_recusa_pedido_fora_da_regra(job_spec):  # noqa: F811
    lote = [x['valor_id'] for x in te.specs_pendentes(job_spec) if x['em_lote']]
    s = _servidor(job_spec)
    try:
        for dados in ({'valor_ids': []}, {'valor_ids': [lote[0], lote[0]]}, {'valor_ids': ['nao-existe']},
                      {'valor_ids': lote[0]}, {'valor_ids': [lote[0]], 'leitura': 0}, {'valor_id': lote[0]},
                      {'valor_ids': [1]}):
            assert _ato(s, 'spec_valores', dados)[0] == 403, dados
    finally:
        s.parar()
    from desdobra.specs import importar
    assert importar.ler_confirmacoes(job_spec)['acoes'] == []


def test_lote_deixa_o_divergente_fora(job_divergente):  # noqa: F811
    lista = te.specs_pendentes(job_divergente)
    div = next(x for x in lista if x['leituras'])
    assert div['em_lote'] is False
    s = _servidor(job_divergente)
    try:
        assert _ato(s, 'spec_valores', {'valor_ids': [div['valor_id']]})[0] == 403
    finally:
        s.parar()


def test_lote_com_a_folha_mudada_no_meio_nao_grava_nada(job_spec, monkeypatch):  # noqa: F811
    from desdobra import humano
    from desdobra.specs import confirmar, importar
    lote = [x['valor_id'] for x in te.specs_pendentes(job_spec) if x['em_lote']]
    monkeypatch.setattr(humano, 'console_interativo', lambda: (True, None))
    d = humano.exigir(confirmar.COMANDO)
    # um id que deixou de ser pendencia (a folha mudou): o lote inteiro e recusado, nada e gravado
    assert confirmar.confirmar_lote_da_tela(job_spec, lote[:2] + ['sumiu'], disparo=d) is None
    assert importar.ler_confirmacoes(job_spec)['acoes'] == []


def test_nome_legivel_do_formato_da_folha():
    assert te.medida_da_chave('1080x1920') == '1080 x 1920'
    assert te.medida_da_chave('pme|sao-paulo-shopping|1080x1920') == '1080 x 1920 (sao paulo shopping)'
    assert te.medida_da_chave('pme|campinas|120x175m') == '120 x 175 m (campinas)'
    # revisao adversarial: a folha sem circuito (o CSV de uma coluna "Formato") nunca mostra o id interno da folha
    assert te.medida_da_chave('f9c478bf8|geral|1080x1920') == '1080 x 1920'
    assert te.medida_da_chave('f9c478bf8|f9c478bf8-geral|970x250') == '970 x 250'
    assert te.medida_da_chave('f9c478bf8|f9c478bf8:campinas|300x600') == '300 x 600 (campinas)'
    # o veiculador com o nome da folha na frente (a chave que a tela de verdade monta para o CSV de uma coluna)
    assert te.medida_da_chave('portalteste-f9c478bf8|f9c478bf8-geral|1080x1920') == '1080 x 1920'
    assert te.medida_da_chave('pme|pme-sao-paulo|300x600') == '300 x 600 (sao paulo)'


EMAIL = 'Formato: 640x320\nPeso máximo: 250 KB\nFormato: 300x600\nPeso máximo: 150 KB\n'


@pytest.fixture
def job_email(tmp_path, ambiente_limpo):  # noqa: F811
    import test_fontes_apoio as fap
    import test_tela_palco as tp
    from conftest import escolher_modo_do_da
    from desdobra.job import nucleo
    from desdobra.render import autoteste
    fontes = tmp_path / 'origem-fontes'
    fap.gravar(fontes, 'autoteste.ttf', autoteste.gerar_fonte())
    specs = tmp_path / 'origem-specs'
    (specs / 'e').mkdir(parents=True)
    (specs / 'e' / 'email.txt').write_text(EMAIL, encoding='utf-8')
    job = tmp_path / 'job'
    nucleo.criar(job, tp._psd_hostil(tmp_path / 'origem' / 'kv.psd', autoteste.NOME_PS), 'b', fontes=[fontes],
                 specs=specs)
    escolher_modo_do_da(job, 'b')
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    return job


@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
def test_passo_1_confirma_os_valores_marcados_em_lote_no_chromium(job_email):
    from playwright.sync_api import sync_playwright

    import test_tela_palco as tp
    from desdobra.chromium import navegador
    from desdobra.specs import importar
    from desdobra.tela import atos as ta
    from desdobra.tela import servidor as ts
    lote = [x for x in te.specs_pendentes(job_email) if x['em_lote']]
    assert len(lote) >= 4  # numero-neutro: dimensao e peso dos dois formatos do e-mail
    conteudo = te.montar(job_email)
    navegador.apontar_playwright()
    with ts.ServidorTela(conteudo, pasta=job_email, modo_teste=False,
                         atos=ta.atos_do_job(job_email, conteudo=conteudo)) as srv, sync_playwright() as pw:
        nav = pw.chromium.launch(headless=True, args=list(navegador.ARGUMENTOS))
        pg = nav.new_context(viewport={'width': 1440, 'height': 900}).new_page()  # numero-neutro: janela do teste
        try:
            try:
                pg.goto(srv.url_entrada, wait_until='commit')
            except Exception:  # noqa: BLE001 - o 204 nao completa a navegacao
                pass
            pg.goto(srv.url_pagina, wait_until='load')
            tp._esperar(pg, tp.JS_PRONTO)
            pg.evaluate('() => document.querySelector("#passos [data-passo=lido]").click()')
            tp._esperar(pg, '() => document.getElementById("spec-lote") ? "1" : ""')
            antes = pg.evaluate('''() => ({
                cartoes: Array.from(document.querySelectorAll("#spec-lote .spec-cartao .spec-cartao-nome"))
                  .map(n => n.textContent),
                marcados: document.querySelectorAll("#spec-lote input:checked").length,
                valores: document.querySelectorAll("#spec-lote input.spec-valor-marca").length,
                confirmar: document.getElementById("spec-lote-confirmar").disabled,
                texto: document.getElementById("lido-specs-pendentes").textContent})''')
            assert antes['marcados'] == 0 and antes['confirmar'] is True, antes
            assert antes['valores'] == len(lote) and any('640 x 320' in c for c in antes['cartoes']), antes
            assert not any(x in antes['texto'] for x in PROIBIDOS), antes['texto']
            # um cartao inteiro pela caixa dele: o contador do botao acompanha
            pg.evaluate('() => document.querySelector("#spec-lote input.spec-grupo-marca").click()')
            um = pg.evaluate('''() => [document.querySelectorAll("#spec-lote input.spec-valor-marca:checked").length,
                document.querySelector("#spec-lote-confirmar .contagem-botao").textContent]''')
            assert um[0] >= 1 and um[1] == str(um[0]), um
            pg.evaluate('() => document.getElementById("spec-lote-todos").click()')
            assert pg.evaluate('() => document.getElementById("spec-lote-todos").textContent') == 'Desmarcar todos'
            assert pg.evaluate('() => document.querySelector("#spec-lote-confirmar .contagem-botao").textContent') == \
                str(len(lote))
            pg.evaluate('() => document.getElementById("spec-lote-confirmar").click()')
            tp._esperar(pg, '() => document.getElementById("confirmacao").open ? "1" : ""')
            janela = pg.evaluate('''() => ({texto: document.getElementById("confirmacao-texto").textContent,
                itens: document.querySelectorAll("#confirmacao-extra .spec-lista-janela li").length,
                foco: document.activeElement.tagName})''')
            assert janela['itens'] == len(lote) and janela['foco'] != 'BUTTON', janela
            assert ('%d valores de spec' % len(lote)) in janela['texto'], janela
            # revisao adversarial: a frase nao repete os formatos, que a lista ja mostra; o numero do grupo tem unidade
            assert '640 x 320' not in janela['texto'] and '300 x 600' not in janela['texto'], janela
            contas = pg.evaluate('''() => Array.from(document.querySelectorAll("#confirmacao-extra .registro-conta"))
                .map(n => n.textContent)''')
            assert contas and all(c.endswith('valor') or c.endswith('valores') for c in contas), contas
            pg.evaluate('''() => Array.from(document.querySelectorAll("#confirmacao button"))
                .find(b => b.textContent === "Confirmar").click()''')
            tp._esperar(pg, '() => document.documentElement.dataset.estadoAto === "feito" ? "1" : ""')
            tp._esperar(pg, '() => document.getElementById("spec-lote") ? "" : "1"')
            # revisao adversarial (pedido 3): o giro em lote. Nada vem marcado; um clique do DA deixa sem giro os
            # formatos que faltam e em que a folha nao fala de giro, e o rascunho grava
            giro = pg.evaluate('''() => ({b: document.getElementById("giro-lote") && document.getElementById("giro-lote").textContent,
                feitos: document.querySelectorAll("#lido-formatos article.giro.feita").length,
                todos: document.querySelectorAll("#lido-formatos article.giro").length})''')
            assert giro['b'] and giro['feitos'] == 0 and giro['todos'] >= 2, giro
            pg.evaluate('() => document.getElementById("giro-lote").click()')
            tp._esperar(pg, '() => document.getElementById("giro-lote") ? "" : "1"')
            depois = pg.evaluate('''() => [document.querySelectorAll("#lido-formatos article.giro.feita").length,
                document.querySelectorAll("#lido-formatos article.giro").length,
                document.getElementById("dica-acoes").textContent]''')
            assert depois[0] == depois[1] == giro['todos'], depois
            assert 'giro' not in depois[2], depois
        finally:
            nav.close()
        assert srv.contagem['ato_confirmar'] == 1 and srv.contagem['csrf_recusado'] == 0
    acoes = importar.ler_confirmacoes(job_email)['acoes']
    assert sorted(a['valor_id'] for a in acoes) == sorted(x['valor_id'] for x in lote)
    assert all(a['acao'] == 'confirmar' and a['meio'] == 'tela' and a['por'] == 'da' for a in acoes)


# ------------------------------------------------------------------ revisao adversarial da 0.9.6
def test_confirmacao_de_antes_da_096_cai_so_na_familia_com_texto_editado():
    from desdobra.tela import rascunho
    formatos = {'f1': {'formato': {'composicao': 'c'}, 'situacao': 'derivado'}}
    agora = te.impressao_das_pecas(['f1'], formatos, [])
    antes = te.impressao_das_pecas(['f1'], formatos, [], regra=te.REGRA_SEM_TEXTO_EDITADO)
    sem = te.impressao_das_pecas(['f1'], formatos, [], regra=te.REGRA_SEM_EDICAO)
    assert len({agora, antes, sem}) == 3
    alt = {'sem_edicao': sem, 'sem_texto': antes}
    mover = {'elemento': 'a', 'acao': 'mover', 'dx': 0.1, 'dy': 0.0}
    texto = {'elemento': 'a', 'acao': 'texto', 'texto': 'X'}

    def fam(edicoes, pecas):
        return {'confirmada': True, 'edicoes': edicoes, 'confirmacao': {'formatos': ['f1'], 'pecas': pecas}}
    # a familia sem texto editado confirmada na 0.9.5 continua confirmada: a previa dela nao mudou
    assert rascunho.confirmada_para(fam([mover], antes), ['f1'], agora, sem_edicao=alt)
    assert rascunho.confirmada_para(fam([], antes), ['f1'], agora, sem_edicao=alt)
    assert rascunho.confirmada_para(fam([], sem), ['f1'], agora, sem_edicao=alt)
    # a familia com texto editado confirmada antes cai uma vez: a caixa das linhas do DA muda o alinhar e o Tamanho
    assert not rascunho.confirmada_para(fam([mover, texto], antes), ['f1'], agora, sem_edicao=alt)
    assert not rascunho.confirmada_para(fam([mover], sem), ['f1'], agora, sem_edicao=alt)
    assert rascunho.confirmada_para(fam([mover, texto], agora), ['f1'], agora, sem_edicao=alt)
    # a impressao sem edicao sozinha (o valor de antes da 0.9.6) continua aceita
    assert rascunho.confirmada_para(fam([], sem), ['f1'], agora, sem_edicao=sem)
    assert rascunho.sem_confirmacao_velha({'familias': {'g': fam([texto], antes)}}, {'g': ['f1']}, {'g': agora},
                                          {'g': alt})['familias']['g']['confirmada'] is False


def _escolhida_com_aviso(conteudo, gid):
    for v in conteudo['familias'][gid]['versoes']:
        m = tpi._previa(conteudo, gid, 'p800', tpi._escolhas(conteudo, gid, v)[gid])
        if m['validacoes_reprovadas'] and m['falhas']:
            return v
    return None


def _briefing_e_linha(job, fid):
    conteudo = te.montar(job)
    linha = next(x for x in te.painel_dos_formatos(job)['formatos'] if x['id'] == fid)
    return conteudo, conteudo['estado']['briefing'], linha


def test_job_salvo_numa_versao_de_antes_com_devolvido_volta_a_pedir_salvar(tmp_path, monkeypatch):
    # o job do Duda: salvo na 0.9.5 com o formato devolvido (validacao_obrigatoria_reprovou) numa familia confirmada.
    # Na 0.9.6 a tela abre com "Salvar e seguir" ligado e o motivo que leva a ele; o clique monta o layout
    from desdobra.derivacao import nucleo as nd
    j = tpi._job(tmp_path, monkeypatch, 'b', tpi.CAIXAS_B_PRIMEIRO)
    conteudo = te.montar(j['job'])
    gid = tpi._familia_de(conteudo, 'p800')
    escolhida = _escolhida_com_aviso(conteudo, gid)
    assert escolhida is not None
    real = proposta._derivacao

    def da_095(ctx, kv_, cf, d, lay, caminho, prop, origem):
        return real(ctx, kv_, cf, d, lay, caminho, dict(prop, confirmada=False), origem)
    with monkeypatch.context() as m:
        m.setattr(proposta, '_derivacao', da_095)
        m.setattr(nd, '__version__', '0.9.5')
        gravadas = tpi._salvar(j, te.montar(j['job']), tpi._escolhas(conteudo, gid, escolhida))
    assert gravadas['p800']['situacao'] == 'devolvido' and gravadas['p800']['motor_versao'] == '0.9.5'
    conteudo, briefing, linha = _briefing_e_linha(j['job'], 'p800')
    assert briefing['salvo'] is False and briefing['refazer_layout'] == ['p800'], briefing
    assert linha['situacao'] == 'sem_derivacao' and linha['motivo'] == te.SEM_LAYOUT_GRAVADO, linha
    gravadas = tpi._salvar(j, conteudo, tpi._escolhas(conteudo, gid, escolhida))
    assert gravadas['p800']['situacao'] == 'derivado', gravadas['p800'].get('devolucao')
    _c, briefing, linha = _briefing_e_linha(j['job'], 'p800')
    assert briefing['salvo'] is True and not briefing.get('refazer_layout'), briefing
    assert linha['rotulo'] == 'Layout pronto', linha


@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
def test_derivacao_que_quebra_no_salvar_deixa_o_botao_ligado_com_o_aviso(tmp_path, monkeypatch):
    # a derivacao que quebra depois de gravar o briefing: o servidor pede "Salvar e seguir" de novo, a pagina deixa o
    # botao ligado com o aviso no rodape (que nao some no proximo clique), e o passo 5 diz para clicar nele
    from playwright.sync_api import sync_playwright

    import test_tela_palco as tp
    from desdobra.chromium import navegador
    from desdobra.derivacao import nucleo as nd
    from desdobra.tela import atos as ta
    from desdobra.tela import servidor as ts
    j = tpi._job(tmp_path, monkeypatch, 'b', tpi.CAIXAS_B_PRIMEIRO)
    conteudo = te.montar(j['job'])
    gid = tpi._familia_de(conteudo, 'p800')
    escolhida = _escolhida_com_aviso(conteudo, gid)

    def quebra(*_a, **_k):
        raise RuntimeError('derivacao simulada que quebra')
    with monkeypatch.context() as m:
        m.setattr(nd, 'derivar', quebra)
        try:
            tpi._salvar(j, te.montar(j['job']), tpi._escolhas(conteudo, gid, escolhida))
        except (contratos.ErroContrato, OSError):
            pass  # nenhuma derivacao gravada para ler
    conteudo, briefing, linha = _briefing_e_linha(j['job'], 'p800')
    assert briefing['salvo'] is False and 'p800' in briefing['refazer_layout'], briefing
    assert linha['motivo'] == te.SEM_LAYOUT_GRAVADO, linha
    navegador.apontar_playwright()
    with ts.ServidorTela(conteudo, pasta=j['job'], modo_teste=True,
                         atos=ta.atos_do_job(j['job'], conteudo=conteudo)) as srv, sync_playwright() as pw:
        nav, pg = tp._pagina_da_tela(pw, srv, 1440, 900)  # numero-neutro: janela do teste
        try:
            v = pg.evaluate('''() => ({b: document.getElementById("salvar-seguir").disabled,
                t: document.getElementById("salvar-seguir").textContent,
                aviso: document.getElementById("salvo").hidden ? "" : document.getElementById("salvo").textContent,
                dica: document.getElementById("dica-acoes").textContent})''')
        finally:
            nav.close()
    assert v['b'] is False and 'não conseguiu montar os layouts' in v['aviso'], v
    assert 'Salvar e seguir' in v['dica'], v
    for texto in (v['aviso'], v['dica'], linha['motivo']):
        assert not any(x in texto for x in PROIBIDOS), texto
    # sem a falha, o clique monta os layouts e a tela volta a "salvo"
    gravadas = tpi._salvar(j, conteudo, tpi._escolhas(conteudo, gid, escolhida))
    assert gravadas['p800']['situacao'] == 'derivado'
    assert _briefing_e_linha(j['job'], 'p800')[1]['salvo'] is True


@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
def test_pagina_mantem_pede_ajuste_no_membro_sem_layout_da_familia(tmp_path, monkeypatch):
    # o membro que a previa traz devolvido (a quebra sem medida tira a galeria dele) nunca vira "Aprovado por você":
    # a confirmacao da familia nao monta o layout dele, e o resumo diz qual arquivo fica sem layout
    from playwright.sync_api import sync_playwright

    import test_tela_escrita as tte_
    import test_tela_galeria as tg
    import test_tela_palco as tp
    import test_tela_servidor as tts
    from desdobra.chromium import navegador
    from desdobra.derivacao import medida_quebras
    from desdobra.tela import atos as ta
    from desdobra.tela import servidor as ts
    from sinteticos import kv_a_b as kv
    monkeypatch.setattr(kv, 'FORMATOS', [('h1', 2048, 720), ('v1', 400, 800), ('v2', 440, 800)])

    def nao_mede(*_a, **_k):
        raise navegador.ErroNavegador('chromium que nao mede, simulado')
    medida_quebras.limpar_cache()
    monkeypatch.setattr(medida_quebras, '_conferir', nao_mede)
    try:
        j = kv.criar_job(tmp_path, 'a')
        conteudo = te.montar(j['job'])
        gid = tpi._familia_de(conteudo, 'v1')
        versao = conteudo['familias'][gid]['versoes'][0]
        quebras = [tpi._quebra(j['ids'])]
        r = conteudo['editar']({'familia': gid, 'versao': versao, 'edicoes': [], 'quebras': quebras},
                               'fixture_de_teste')
        devolvidos = sorted(m['formato'] for m in r['membros'] if m['situacao'] == 'devolvido')
        assert devolvidos, [(m['formato'], m['situacao']) for m in r['membros']]
        # o rascunho com a quebra da familia, como o DA o deixou
        s = ts.ServidorTela(conteudo, pasta=j['job'], modo_teste=True,
                            atos=ta.atos_do_job(j['job'], conteudo=conteudo)).iniciar()
        try:
            biscoito = tts._entrar(s)
            familias = {gid: {'versao': versao, 'confirmada': False, 'edicoes': [], 'quebras': quebras}}
            corpo = dict({'job_id': s.job_id, 'laudo_sha256': s.laudo_sha256, 'familias': familias},
                         **kv.passo_2(j['funcoes']))
            assert tte_._escrever(s, '/api/rascunho', corpo, cookie=biscoito)[0] == 200
        finally:
            s.parar()
        navegador.apontar_playwright()
        marca = '#membros-lista .membro[data-formato="%s"] .marca-aviso' % devolvidos[0]
        with ts.ServidorTela(conteudo, pasta=j['job'], modo_teste=True,
                             atos=ta.atos_do_job(j['job'], conteudo=conteudo)) as srv, sync_playwright() as pw:
            nav, pg = tp._pagina_da_tela(pw, srv, 1600, 900)  # numero-neutro: janela do teste
            try:
                tg._abrir(pg, conteudo['estado'], devolvidos[0])
                tp._esperar(pg, '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""')
                tp._esperar(pg, '() => document.querySelector(\'%s\') ? "1" : ""' % marca)
                ler = '''s => ({marcas: Array.from(document.querySelectorAll(s)).map(x => [x.textContent, x.className]),
                    resumo: document.getElementById("resumo-edicao").textContent,
                    confirmar: document.getElementById("confirmar-familia").disabled})'''
                antes = pg.evaluate(ler, marca)
                # o membro sem layout nao desliga "Confirmar familia": os outros membros seguem
                assert antes['confirmar'] is False, antes
                pg.evaluate('() => document.getElementById("confirmar-familia").click()')
                tp._esperar(pg, '() => document.getElementById("confirmacao").open ? "1" : ""')
                pg.evaluate('''() => Array.from(document.querySelectorAll("#confirmacao button"))
                    .find(b => b.textContent === "Confirmar").click()''')
                tp._esperar(pg, '() => document.documentElement.dataset.estadoAto === "feito" ? "1" : ""')
                tp._esperar(pg, '''() => document.getElementById("confirmar-familia").textContent !==
                    "Confirmar família" ? "1" : ""''')
                depois = pg.evaluate(ler, marca)
            finally:
                nav.close()
    finally:
        medida_quebras.limpar_cache()
    assert any(t == 'Pede ajuste' and 'forte' in c for t, c in antes['marcas']), antes
    assert 'sem layout' in antes['resumo'] and devolvidos[0] in antes['resumo'], antes
    assert not any(x in antes['resumo'] for x in PROIBIDOS), antes['resumo']
    assert all(t != 'Aprovado por você' and 'aceito' not in c for t, c in depois['marcas']), depois
    assert any('forte' in c for _t, c in depois['marcas']), depois
    assert 'sem layout' in depois['resumo'], depois
