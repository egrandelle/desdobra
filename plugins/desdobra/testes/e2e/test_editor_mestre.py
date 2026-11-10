# -*- coding: utf-8 -*-
"""M7b, E2: roteiro de ponta a ponta do editor de mestre (arquitetura-v1.md, 9.8, Editor de mestre; decisoes-v1.md,
164, 167 e 171; plano do M7b, E2 e secao 4).

O DA, so com cliques e teclas na pagina (modo de teste da tela, meio fixture_de_teste / medicao), desenha a mestre da
familia vertical (tres membros, caminho da galeria):
  - abre a aba da familia;
  - move uma caixa (o titulo desce pela seta);
  - muda uma quebra de linha (um clique entre as duas palavras do texto de apoio);
  - edita o texto do titulo, que nao cabe mais na caixa: o desdobra propoe a requebra, e o DA a aprova com um clique;
  - confirma a familia e clica em "Salvar e seguir";
  - fecha a janela (o servidor da tela para) e reabre (um servidor novo, montado do zero).
Conferencias:
  - cada campo editado (a caixa movida, o texto, as duas quebras) aparece no derivacao/<f>.json de cada membro, com o
    valor esperado: a caixa e a da previa que a tela mostrou ao DA, o texto e o que ele digitou e as quebras sao as do
    rascunho; o elemento editado tem origem_geometria "da" (meta 100%);
  - depois de reabrir, o rascunho, o briefing e a derivacao de cada membro relidos sao 100% iguais, a pagina mostra as
    mesmas linhas e a familia confirmada, e a derivacao refeita em memoria da o mesmo arquivo;
  - medicoes/tela.json traz o tempo ativo e o total da familia, as duas edicoes e a uma mudanca de quebra.
Os numeros medidos vao para o arquivo da variavel de ambiente DESDOBRA_MEDICAO_EDITOR_MESTRE, quando ela existe (fora
do repositorio; sem ela, nada e gravado fora da pasta temporaria do teste).
Tudo sintetico: o PSD de test_tela_palco (o texto de apoio 'VOX AH', o titulo 'HOAX') e a fonte de autoteste."""
import json
import os
import platform
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

import test_tela_salvar as tsv
from desdobra import arquivos, contratos, humano
from desdobra.briefing import modelo as mb
from desdobra.tela import estado as te
from desdobra.tela import rascunho as tr

modelo = tsv.modelo
job = tsv.job
APOIO = 'VOX AH'
TITULO = 'HOAX HOAX HOAX'  # o titulo editado: duas palavras cabem na caixa, tres nao
MEMBROS = tuple(fid for fid, _w, _h in tsv.VERTICAIS)
VARIAVEL_MEDICAO = 'DESDOBRA_MEDICAO_EDITOR_MESTRE'
FOLGA_CAIXA = 0.01  # numero-neutro: px, a folga entre a previa da tela e a derivacao gravada (test_tela_salvar)


@pytest.fixture
def medida_limpa():
    """O cache da medida da quebra (por processo) vazio na entrada e na saida: o roteiro mede do zero e nao deixa a
    medida dele pronta para o teste seguinte (a previa de test_quebra_na_tela espera ver a remedicao)."""
    from desdobra.derivacao import medida_quebras
    medida_quebras.limpar_cache()
    yield
    medida_quebras.limpar_cache()


def _esperar_pedido(pg, pedidos, quantos, teto_s=60):
    """Espera a pagina mandar o pedido de numero quantos (pg.on('request') anota)."""
    fim = time.monotonic() + teto_s
    while len(pedidos) < quantos:
        assert time.monotonic() < fim, 'a pagina nao pediu a previa'
        pg.wait_for_timeout(50)  # numero-neutro: ms, intervalo do teste


def _sem_gerado_em(d):
    return {k: v for k, v in json.loads(json.dumps(d)).items() if k != 'gerado_em'}


def _derivacoes(job):
    from desdobra.derivacao import nucleo as nd
    return {fid: contratos.ler(job / nd.PASTA / ('%s.json' % fid), nd.ESQUEMA) for fid in MEMBROS}


def _previa(conteudo, gid, f, edicoes=None):
    pedido = {'familia': gid, 'versao': f['versao'], 'edicoes': f['edicoes'] if edicoes is None else edicoes}
    if f.get('quebras'):
        pedido['quebras'] = f['quebras']
    return {m['formato']: {e['id']: e['caixa'] for e in m['palco']['elementos']}
            for m in conteudo['editar'](pedido)['membros']}


def _esperados(conteudo, gid, f, titulo, apoio):
    """[(formato, elemento, campo, conferir(elemento da derivacao) -> bool)] de cada campo que o DA editou, em cada
    membro. O valor esperado vem do que o DA fez e viu: a caixa da previa da tela com as edicoes do rascunho (e
    diferente da previa sem o movimento), o texto digitado e as quebras gravadas no rascunho."""
    mover = [e for e in f['edicoes'] if e['acao'] == 'mover']
    assert [e['elemento'] for e in mover] == [titulo]
    com = _previa(conteudo, gid, f)
    sem = _previa(conteudo, gid, f, edicoes=[e for e in f['edicoes'] if e['acao'] != 'mover'])
    quebra = {q['elemento']: q for q in f['quebras']}
    campos = []
    for fid in MEMBROS:
        caixa, antes = com[fid][titulo], sem[fid][titulo]
        assert caixa != pytest.approx(antes, abs=FOLGA_CAIXA), (fid, 'o movimento nao mudou a previa')
        campos += [(fid, titulo, 'caixa (mover)', _caixa_igual(caixa)),
                   (fid, titulo, 'texto', lambda e: e.get('texto_editado') == TITULO),
                   (fid, titulo, 'quebra proposta aprovada', _quebra_igual(quebra[titulo])),
                   (fid, apoio, 'quebra do DA', _quebra_igual(quebra[apoio]))]
    return campos


def _caixa_igual(caixa):
    return lambda e: e['caixa'] == pytest.approx(caixa, abs=FOLGA_CAIXA)


def _quebra_igual(q):
    """A quebra da familia no elemento da derivacao: as posicoes inseridas e a origem do rascunho."""
    return lambda e: [x['inseridas'] for x in (e.get('quebras') or {}).get('familia') or []] == [q['inseridas']] \
        and e.get('quebras_origem') == q['origem']


def _conferir(derivacoes, campos):
    """(refletidos, com origem da, total, o que falhou) dos campos editados na derivacao de cada membro."""
    refletidos = origem_da = 0
    falhas = []
    for fid, eid, campo, conferir in campos:
        e = {x['id']: x for x in derivacoes[fid]['elementos']}.get(eid)
        ok, da = e is not None and conferir(e), e is not None and e['origem_geometria'] == 'da'
        refletidos += ok
        origem_da += da
        falhas += [(fid, eid, campo, 'valor')] * (not ok) + [(fid, eid, campo, 'origem')] * (not da)
    return refletidos, origem_da, len(campos), falhas


def _shas(job):
    from desdobra.derivacao import nucleo as nd
    nomes = [job / tr.ARQUIVO, job / mb.ARQUIVO] + [job / nd.PASTA / ('%s.json' % fid) for fid in MEMBROS]
    return {p.relative_to(job).as_posix(): arquivos.sha256_arquivo(p) for p in nomes}


def _gravar_medicao(texto):
    destino = os.environ.get(VARIAVEL_MEDICAO)
    if destino:
        Path(destino).parent.mkdir(parents=True, exist_ok=True)
        Path(destino).write_text(texto, encoding='utf-8', newline='\n')


def _abrir_familia(pg, conteudo, fid):
    import test_tela_galeria as tg
    import test_tela_palco as tp
    tg._abrir(pg, conteudo['estado'], fid)
    tp._esperar(pg, '() => document.documentElement.dataset.previa === "pronta" ? "1" : ""')


@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
def test_editor_de_mestre_de_ponta_a_ponta(job, modelo, medida_limpa):
    from playwright.sync_api import sync_playwright

    import test_quebra_na_tela as tqt
    import test_tela_edicao as ted
    import test_tela_familia_estavel as tfe
    import test_tela_palco as tp
    from desdobra.chromium import navegador
    from desdobra.derivacao import formatos as mf
    from desdobra.derivacao import nucleo as nd
    from desdobra.job import modo_dados
    from desdobra.tela import atos as ta
    from desdobra.tela import cronometro as tc
    from desdobra.tela import servidor as ts
    conteudo = te.montar(job)
    gv = tsv._familia_de(conteudo, MEMBROS[0])
    assert sorted(conteudo['familias'][gv]['formatos']) == sorted(MEMBROS)
    apoio, lid = tsv._apoio(modelo)
    titulo = tsv._titulo(conteudo, gv)
    navegador.apontar_playwright()
    tempos = {}
    with ts.ServidorTela(conteudo, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo)) as srv, sync_playwright() as pw:
        # o passo 2, o modo e as outras familias ja decididos; a familia vertical fica com o DA, so com a versao da
        # galeria escolhida
        escolhas = tsv._escolhas(conteudo)
        escolhas[gv] = {'versao': escolhas[gv]['versao'], 'confirmada': False, 'edicoes': []}
        corpo = dict({'job_id': srv.job_id, 'laudo_sha256': srv.laudo_sha256, 'familias': escolhas},
                     **tsv._passo_2(modelo['funcoes']))
        tr.gravar(job, corpo, job_id=srv.job_id, laudo_atual=srv.laudo_sha256, origem=srv.origem_rascunho)
        for gid, f in escolhas.items():
            if gid != gv:
                d = humano.exigir_tela(tr.COMANDO_FAMILIA, srv._sessao_humana, confirmado=True)
                tr.confirmar_familia(job, gid, f['versao'], disparo=d, job_id=srv.job_id,
                                     laudo_atual=srv.laudo_sha256, edicoes=f['edicoes'],
                                     formatos=conteudo['familias'][gid]['formatos'],
                                     pecas=conteudo['familias'][gid]['pecas'])
        modo_dados.gravar(job, 'c', disparo=humano.exigir_tela(modo_dados.ESCOLHER, srv._sessao_humana,
                                                               confirmado=True))
        srv.estado = conteudo['recarregar']()
        nav, pg = tp._pagina_da_tela(pw, srv, 1600, 900)  # numero-neutro: janela do teste
        previas = []
        pg.on('request', lambda r: previas.append(r.url) if '/api/familia/previa' in r.url else None)
        try:
            inicio = time.monotonic()
            # abrir a aba da familia
            _abrir_familia(pg, conteudo, MEMBROS[0])
            # mover uma caixa: o titulo desce pela seta
            ted._focar(pg, titulo)
            pg.keyboard.press('ArrowDown')
            ted._esperar_salvo(pg)
            # mudar uma quebra: um clique entre as duas palavras do apoio
            tqt._abrir_controle(pg, apoio)
            assert pg.evaluate(tqt.JS_LINHAS_DO_CONTROLE) == [APOIO]
            antes = len(previas)
            pg.evaluate('() => document.querySelector(\'#quebra-linhas button[data-pos="3"]\').click()')
            assert pg.evaluate(tqt.JS_LINHAS_DO_CONTROLE) == ['VOX', 'AH']
            _esperar_pedido(pg, previas, antes + 1)  # a previa da quebra, 300 ms depois do clique
            ted._esperar_salvo(pg)
            assert pg.evaluate(tqt.JS_LINHAS, apoio) == ['VOX', 'AH']
            # o texto novo do titulo nao cabe na caixa: o desdobra propoe a requebra, marcada no palco
            tqt._escolher(pg, titulo)
            pg.evaluate('() => document.getElementById("ed-texto").click()')
            pg.fill('#ed-campo-texto', TITULO)
            pg.evaluate('() => document.getElementById("ed-texto-aplicar").click()')
            tp._esperar(pg, '() => document.getElementById("quebra-proposta").hidden ? "" : "1"')
            ted._esperar_salvo(pg)
            [proposta] = tqt._do_elemento(ted._rascunho_gravado(job), gv, titulo)
            assert proposta['origem'] == 'proposta' and proposta['aprovada'] is False and proposta['inseridas']
            assert pg.evaluate('() => document.getElementById("confirmar-familia").disabled') is True
            # aprovar a requebra com um clique
            pg.evaluate('() => document.getElementById("aprovar-quebra").click()')
            tp._esperar(pg, '() => document.getElementById("quebra-proposta").hidden ? "1" : ""')
            ted._esperar_salvo(pg)
            assert pg.evaluate('() => document.getElementById("confirmar-familia").disabled') is False
            # o ultimo sinal do cronometro chega antes da confirmacao
            tp._esperar(pg, '() => document.documentElement.dataset.sinal === "enviado" ? "1" : ""')
            # confirmar a familia e "Salvar e seguir"
            tfe._confirmar_na_pagina(pg, '#confirmar-familia')
            tempos['desenho_s'] = time.monotonic() - inicio
            tp._esperar(pg, tfe.SALVAR_DESABILITADO + ' ? "" : "1"')
            antes_de_salvar = time.monotonic()
            tfe._confirmar_na_pagina(pg, '#salvar-seguir')
            tp._esperar(pg, '() => document.getElementById("salvo").hidden ? "" : "1"')
            tempos['salvar_s'] = time.monotonic() - antes_de_salvar
            linhas = {e: pg.evaluate(tqt.JS_LINHAS, e) for e in (apoio, titulo)}
            texto = pg.evaluate(tp.JS_TEXTO_DA_MOLDURA)
            assert not tp.IDENTIFICADOR.findall(texto), tp.IDENTIFICADOR.findall(texto)
        finally:
            nav.close()
    # fechado: o que ficou gravado
    rascunho = ted._rascunho_gravado(job)
    f = rascunho['familias'][gv]
    assert f['confirmada'] is True
    assert [e['acao'] for e in f['edicoes']] == ['mover', 'texto']
    quebras = sorted((q['elemento'], q['origem'], q['aprovada'], tuple(q['inseridas'])) for q in f['quebras'])
    assert quebras == sorted([(apoio, 'da', True, (3,)), (titulo, 'proposta', True, tuple(proposta['inseridas']))])
    b = mb.ler(job)
    comp = {c['familia']: c for c in b['composicoes']}[gv]
    assert (comp['versao'], comp['edicoes'], comp['confirmada']) == (f['versao'], f['edicoes'], True)
    assert sorted((q['layer_id'], q['origem'], q['aprovada'], tuple(q['inseridas'])) for q in b['quebras_por_familia']
                  if q.get('familia') == gv) == \
        sorted([(lid, 'da', True, (3,)), (proposta['layer_id'], 'proposta', True, tuple(proposta['inseridas']))])
    derivacoes = _derivacoes(job)
    for fid, d in derivacoes.items():
        assert d['situacao'] == 'derivado' and d['caminho'] == 'galeria', (fid, d.get('devolucao'))
        assert d['proposta']['versao'] == f['versao'] and d['proposta']['confirmada'] is True
    # campo a campo: cada edicao em cada membro, com o valor esperado e a origem da
    campos = _esperados(te.montar(job), gv, f, titulo, apoio)
    refletidos, origem_da, total, falhas = _conferir(derivacoes, campos)
    assert refletidos == total and origem_da == total, falhas
    shas = _shas(job)
    medicao_antes = tc.ler(job)

    # reabrir: um servidor novo, montado do zero, e uma janela nova
    conteudo2 = te.montar(job)
    assert conteudo2['familias'] == conteudo['familias']
    assert conteudo2['estado']['briefing']['salvo'] is True
    with ts.ServidorTela(conteudo2, pasta=job, modo_teste=True,
                         atos=ta.atos_do_job(job, conteudo=conteudo2)) as srv, sync_playwright() as pw:
        nav, pg = tp._pagina_da_tela(pw, srv, 1600, 900)  # numero-neutro: janela do teste
        try:
            _abrir_familia(pg, conteudo2, MEMBROS[0])
            assert {e: pg.evaluate(tqt.JS_LINHAS, e) for e in (apoio, titulo)} == linhas
            assert pg.evaluate('() => document.getElementById("quebra-proposta").hidden') is True
            assert pg.evaluate('() => document.getElementById("confirmar-familia").textContent') == 'Família confirmada'
            assert pg.evaluate('() => document.getElementById("salvo").hidden') is False
            tqt._abrir_controle(pg, apoio)
            assert pg.evaluate(tqt.JS_LINHAS_DO_CONTROLE) == ['VOX', 'AH']
        finally:
            nav.close()
    # relido depois de reabrir: 100% igual
    iguais = {}
    iguais['arquivos'] = [k for k, v in _shas(job).items() if shas[k] == v]
    relidas = _derivacoes(job)
    iguais['campos'] = _conferir(relidas, campos)
    iguais['derivacoes'] = [fid for fid in MEMBROS if relidas[fid] == derivacoes[fid]]
    ctx = nd.preparar(job)
    specs, arq = mf.specs_do_job(job)
    refeitas = nd.derivar_em_memoria(ctx, specs=specs, arquivo_specs=arq, params=mf.parametros(job, ctx['briefing']),
                                     so=list(MEMBROS))['formatos']
    iguais['refeitas'] = [fid for fid in MEMBROS if _sem_gerado_em(refeitas[fid]) == _sem_gerado_em(relidas[fid])]
    assert iguais['arquivos'] == list(shas), shas
    assert iguais['campos'] == (total, total, total, [])
    assert iguais['derivacoes'] == list(MEMBROS) and iguais['refeitas'] == list(MEMBROS)
    assert ted._rascunho_gravado(job) == rascunho and mb.ler(job) == b

    # o cronometro da mestre: a familia vertical numa sessao, confirmada, com as duas edicoes e a quebra do DA
    medicao = tc.ler(job)
    assert medicao is not None and medicao['job_id'] == conteudo['estado']['job_id']
    sessao = medicao['sessoes'][0]['familias'][gv]
    # numero-neutro: as contagens do roteiro (mover e o texto; um clique na quebra; a aprovacao nao conta)
    assert (sessao['edicoes'], sessao['quebras']) == (2, 1) and sessao['confirmada_em'] is not None
    assert 0 < sessao['ativo_s'] <= sessao['total_s']
    assert medicao['sessoes'][0]['origem'] == 'fixture_de_teste'
    soma = medicao['familias'][gv]
    assert soma == {'sessoes': 1, 'confirmada_em': sessao['confirmada_em'], 'ativo_s': sessao['ativo_s'],
                    'total_s': sessao['total_s'], 'edicoes': 2, 'quebras': 1}  # numero-neutro: as contagens do DA
    # a reabertura so olhou a familia confirmada: o tempo dela nao mudou
    assert medicao_antes['familias'][gv] == soma
    # o cronometro fica fora do briefing e da derivacao
    assert 'medicoes' not in json.dumps(b) and all('medicoes' not in json.dumps(d) for d in relidas.values())

    _gravar_medicao('\n'.join([
        'Medicao do E2 (M7b): roteiro do editor de mestre, %s.' % datetime.now().strftime('%Y-%m-%d %H:%M'),
        'Job sintetico de test_tela_salvar (PSD de test_tela_palco, fonte de autoteste), modo de teste da tela.',
        '%s, Python %s.' % (platform.platform(), platform.python_version()),
        'Familia vertical (%s), caminho da galeria, versao %s.' % (', '.join(MEMBROS), f['versao']),
        'Roteiro: abrir a aba, mover o titulo (seta), quebrar o apoio entre as palavras, editar o titulo (%r,' % TITULO,
        '  a requebra proposta em %s), aprovar a quebra, confirmar a familia, Salvar e seguir, fechar e reabrir.'
        % proposta['inseridas'],
        '',
        'Campos editados refletidos na derivacao: %d de %d (%.0f%%); com origem_geometria "da": %d de %d (%.0f%%).'
        % (refletidos, total, 100.0 * refletidos / total, origem_da, total, 100.0 * origem_da / total),
        '  por membro: caixa do titulo movida (igual a previa da tela, folga %.2f px), texto do titulo, quebra proposta'
        % FOLGA_CAIXA,
        '  aprovada (inseridas %s, quebras_origem "proposta"), quebra do DA no apoio (inseridas [3], quebras_origem'
        % proposta['inseridas'],
        '  "da").',
        'Relido depois de reabrir: arquivos com o mesmo sha %d de %d (rascunho, briefing e a derivacao dos membros);'
        % (len(iguais['arquivos']), len(shas)),
        '  campos editados %d de %d; derivacoes iguais %d de %d; derivacao refeita em memoria igual %d de %d.'
        % (iguais['campos'][0], total, len(iguais['derivacoes']), len(MEMBROS), len(iguais['refeitas']), len(MEMBROS)),
        '',
        'medicoes/tela.json, familia %s: ativo %.3f s, total %.3f s, edicoes %d, quebras %d, sessoes %d.'
        % (gv, soma['ativo_s'], soma['total_s'], soma['edicoes'], soma['quebras'], soma['sessoes']),
        '  sessao 1: ativo %.3f s, total %.3f s (da abertura da janela ao ultimo clique); %d sessao(oes) no arquivo.'
        % (medicao['sessoes'][0]['ativo_s'], medicao['sessoes'][0]['total_s'], len(medicao['sessoes'])),
        'Relogio do teste (time.monotonic): do clique na aba a confirmacao da familia %.2f s;' % tempos['desenho_s'],
        '  Salvar e seguir (do clique ao aviso de salvo, com a derivacao) %.2f s.' % tempos['salvar_s'],
        'O tempo do roteiro e de um robo: serve para conferir o registro, nunca como tempo de um DA.',
        '']))
