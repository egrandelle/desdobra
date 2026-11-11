# -*- coding: utf-8 -*-
"""M7b: a previa da tela e o "Salvar e seguir" mostram e gravam o mesmo layout do formato devolvido (decisoes-v1.md,
166, 167 e 175; docs/m1-interfaces.md, "Previa igual ao Salvar (M7b)"), escrito antes do codigo.

Defeito achado no D6: a tela montava a galeria para todo formato devolvido, e a derivacao so a aplicava na troca de
orientacao e na proporcao fora da faixa. O formato devolvido pela validacao obrigatoria aparecia na tela numa versao da
galeria, e o "Salvar e seguir" o devolvia de novo. A conferencia da galeria tambem media a colisao contra a mestre com a
quebra de linha, e o motor mede contra o KV: o texto quebrado que crescia sobre os icones saia limpo na previa.

Criterios cobertos aqui:
  - uma regra so (desdobra.derivacao.proposta.usa_galeria) diz se o formato devolvido parte da galeria;
  - o formato que o motor devolve pela validacao obrigatoria sai da versao da galeria que a tela mostrou, com o mesmo
    layout e as mesmas falhas da previa (caso visto 2 do D6: o 800x600 do KV B do primeiro desenho);
  - o texto quebrado em duas linhas que cresce sobre os icones aparece na previa como "Pede ajuste", com a colisao do
    motor, e o "Salvar e seguir" grava o mesmo (caso visto 1 do D6: o 1008x432 do KV A do segundo desenho).
Tudo sintetico: os KVs A e B de testes/sinteticos/kv_a_b.py com as caixas dos dois desenhos de antes, gerados na hora,
e a fonte de autoteste do motor."""
import pytest

import test_tela_escrita as tte
import test_tela_servidor as tts
from desdobra import contratos
from desdobra.derivacao import nucleo as nd
from desdobra.derivacao import proposta
from desdobra.derivacao import validacao as mv
from desdobra.tela import atos as ta
from desdobra.tela import estado as te
from desdobra.tela import servidor as ts
from sinteticos import kv_a_b as kv

TOL = 0.01  # numero-neutro: px, o arredondamento da caixa gravada
# o primeiro desenho do KV B do D6: o packshot maior e mais a esquerda; o 800x600 sai do motor reprovado pela
# validacao obrigatoria
CAIXAS_B_PRIMEIRO = {'titulo': [20, 26, 220, 58], 'linha': [22, 70, 142, 74], 'apoio': [20, 84, 220, 104],
                     'icone1': [22, 116, 42, 136], 'icone2': [50, 116, 70, 136], 'assinatura': [22, 168, 72, 188],
                     'circulo': [230, 50, 380, 200], 'garrafa': [254, 60, 290, 200], 'copo': [298, 126, 330, 200],
                     'lata': [338, 112, 368, 200]}
# o segundo desenho do KV A do D6: o apoio a 12 px dos icones; quebrado em duas linhas, ele cresce sobre eles
CAIXAS_A_SEGUNDO = {'titulo': [24, 40, 108, 72], 'linha': [26, 80, 106, 84], 'apoio': [24, 92, 118, 108],
                    'icone1': [26, 120, 46, 140], 'icone2': [54, 120, 74, 140], 'assinatura': [330, 166, 380, 186],
                    'circulo': [250, 40, 370, 160], 'garrafa': [270, 50, 300, 160], 'copo': [306, 100, 330, 160],
                    'lata': [336, 96, 360, 160]}
QUEBRA_APOIO = 6  # numero-neutro: a posicao do espaco entre 'VOX AH' e 'HOAX'


def _job(tmp_path, monkeypatch, qual, caixas):
    monkeypatch.setitem(kv.CAIXAS, qual, caixas)
    return kv.criar_job(tmp_path, qual)


def _familia_de(conteudo, fid):
    return next(g for g, f in conteudo['familias'].items() if fid in f['formatos'])


def _quebra(ids):
    return {'elemento': 'el%d' % ids['apoio'], 'layer_id': ids['apoio'], 'manter': [], 'inseridas': [QUEBRA_APOIO],
            'origem': 'da', 'aprovada': True}


def _ato(s, biscoito, nome, dados):
    codigo, p = tte._pedir_ato(s, biscoito, nome=nome, dados=dados)
    assert codigo == 200, (nome, codigo)
    c2, _cab, _corpo = tte._escrever(s, '/api/ato/confirmar', {'pedido': p['pedido'], 'resposta': 'confirmar'},
                                     cookie=biscoito)
    assert c2 == 200, (nome, c2)


def _salvar(j, conteudo, escolhas):
    """Grava o rascunho com as escolhas de cada familia ({id: {'versao', 'edicoes', 'quebras'}}), confirma todas e
    clica "Salvar e seguir" pelas rotas da tela (modo de teste). Devolve {id do formato: derivacao gravada}."""
    import json

    from desdobra.tela import rascunho as tr
    job = j['job']
    s = ts.ServidorTela(conteudo, pasta=job, modo_teste=True, atos=ta.atos_do_job(job, conteudo=conteudo)).iniciar()
    try:
        biscoito = tts._entrar(s)
        familias = {gid: {'versao': e['versao'], 'confirmada': False, 'edicoes': e['edicoes'],
                          'quebras': e.get('quebras') or []} for gid, e in escolhas.items()}
        corpo = dict({'job_id': s.job_id, 'laudo_sha256': s.laudo_sha256, 'familias': familias},
                     **kv.passo_2(j['funcoes']))
        assert tte._escrever(s, '/api/rascunho', corpo, cookie=biscoito)[0] == 200
        _ato(s, biscoito, 'modo_dados', {'modo': 'c'})
        for gid, e in familias.items():
            _ato(s, biscoito, 'familia', {'familia': gid, 'versao': e['versao'], 'edicoes': e['edicoes'],
                                          'quebras': e['quebras']})
        dados = json.loads((job / tr.ARQUIVO).read_text(encoding='utf-8'))
        vista = {k: dados[k] for k in ('job_id', 'laudo_sha256', 'familias', 'funcoes', 'cobertas', 'design',
                                       'design_camadas') if k in dados}
        _ato(s, biscoito, 'salvar', {'rascunho': vista})
    finally:
        s.parar()
    return {fid: contratos.ler(job / nd.PASTA / ('%s.json' % fid), nd.ESQUEMA) for fid, _w, _h in kv.FORMATOS}


def _escolhas(conteudo, gid, versao=None, quebras=()):
    esc = {g: {'versao': None, 'edicoes': []} for g in conteudo['familias']}
    esc[gid] = {'versao': versao, 'edicoes': [], 'quebras': list(quebras)}
    return esc


def _previa(conteudo, gid, fid, escolha):
    r = conteudo['editar']({'familia': gid, 'versao': escolha['versao'], 'edicoes': escolha['edicoes'],
                            'quebras': escolha.get('quebras') or []}, 'fixture_de_teste')
    return next(m for m in r['membros'] if m['formato'] == fid)


def _confere_igual(m, d):
    """O que a previa mostra do membro (caixas e falhas) e o que a derivacao gravou."""
    previa = {e['id']: [float(x) for x in e['caixa']] for e in m['palco']['elementos']}
    gravada = {e['id']: [float(x) for x in e['caixa']] for e in d['elementos']}
    assert sorted(previa) == sorted(gravada)
    for k, c in previa.items():
        assert gravada[k] == pytest.approx(c, abs=TOL), (k, c, gravada[k])
    registro = next((r for r in d['registros'] if r['codigo'] == 'proposta_com_falha'), None)
    gravadas = registro['medidas']['falhas'] if registro else []
    assert sorted({f['codigo'] for f in m['falhas']}) == gravadas, (m['falhas'], d['registros'])
    reprovadas = sorted({v['nome'] for v in mv.reprovadas(d['validacoes'])})
    assert sorted(m['validacoes_reprovadas']) == reprovadas, (m['validacoes_reprovadas'], reprovadas)
    if reprovadas:
        assert d['situacao'] == 'devolvido' and d['devolucao']['motivo'] == 'validacao_obrigatoria_reprovou'
        assert [f for f in m['falhas'] if f['codigo'] == 'validacao_reprova'], m['falhas']
    else:
        assert d['situacao'] == 'derivado', d.get('devolucao')


# ------------------------------------------------------------------ a regra
def test_uma_regra_so_diz_se_o_formato_parte_da_galeria():
    def dv(motivo):
        return {'situacao': 'devolvido', 'devolucao': {'motivo': motivo}}
    for motivo in ('troca_forte_de_orientacao', 'troca_de_orientacao_quadrado', 'fora_da_faixa_de_familia',
                   'validacao_obrigatoria_reprovou'):
        assert proposta.usa_galeria(dv(motivo)), motivo
    # as guardas do motor e a medida por confirmar nunca saem da galeria
    for motivo in ('formato_sem_folha', 'dimensao_diferente_da_folha', 'indeterminado_sem_regra',
                   'bloco_partido_na_pilha', 'spec_por_confirmar', 'mestre_por_confirmar', 'quebra_sem_medida',
                   'erro_no_formato'):
        assert not proposta.usa_galeria(dv(motivo)), motivo
    assert not proposta.usa_galeria({'situacao': 'derivado', 'devolucao': None})
    assert not proposta.usa_galeria(None)


# ------------------------------------------------------------------ caso visto 2 do D6
def test_devolvido_pela_validacao_obrigatoria_grava_a_versao_que_a_tela_mostrou(tmp_path, monkeypatch):
    j = _job(tmp_path, monkeypatch, 'b', CAIXAS_B_PRIMEIRO)
    conteudo = te.montar(j['job'])
    p = conteudo['previas']['p800']
    assert p['situacao'] == 'devolvido' and p['devolucao']['motivo'] == 'validacao_obrigatoria_reprovou'
    gid = _familia_de(conteudo, 'p800')
    versoes = conteudo['familias'][gid]['versoes']
    assert versoes, 'a tela oferece a galeria'
    # cada versao da galeria, escolhida com um clique (a familia com galeria so e confirmada com uma versao)
    for versao in versoes:
        # a tela aberta de novo a cada vez, como o DA a ve depois de "Salvar e seguir"
        conteudo = te.montar(j['job'])
        esc = _escolhas(conteudo, gid, versao)
        m = _previa(conteudo, gid, 'p800', esc[gid])
        d = _salvar(j, conteudo, esc)['p800']
        _confere_igual(m, d)
        assert any(r['codigo'] == 'proposta_da_galeria' for r in d['registros']), d['registros']


# ------------------------------------------------------------------ caso visto 1 do D6
def test_apoio_quebrado_sobre_os_icones_pede_ajuste_na_previa_e_no_salvar(tmp_path, monkeypatch):
    from desdobra.derivacao import medida_quebras
    medida_quebras.limpar_cache()
    try:
        j = _job(tmp_path, monkeypatch, 'a', CAIXAS_A_SEGUNDO)
        conteudo = te.montar(j['job'])
        gid = _familia_de(conteudo, 'p1008')
        esc = _escolhas(conteudo, gid, None, [_quebra(j['ids'])])
        m = _previa(conteudo, gid, 'p1008', esc[gid])
        apoio, icone = 'el%d' % j['ids']['apoio'], 'el%d' % j['ids']['icone1']
        caixas = {e['id']: e['caixa'] for e in m['palco']['elementos']}
        a, i = caixas[apoio], caixas[icone]
        sobre = min(a[2], i[2]) > max(a[0], i[0]) and min(a[3], i[3]) > max(a[1], i[1])
        if sobre:
            # o apoio que cresce sobre o icone e colisao nova contra o KV, como o motor mede
            assert 'colisao_nova_contra_a_origem' in m['validacoes_reprovadas'], m['falhas']
        d = _salvar(j, conteudo, esc)['p1008']
        _confere_igual(m, d)
    finally:
        medida_quebras.limpar_cache()


# ------------------------------------------------------------------ revisao da correcao
def test_sem_a_medida_da_quebra_a_previa_mostra_o_membro_devolvido_como_o_salvar(tmp_path, monkeypatch):
    """Sem a medida da quebra de linha da familia (o Chromium que nao mede), a galeria nao sai: a previa mostra o
    membro devolvido, com a falha que diz por que, e o "Salvar e seguir" o grava devolvido (revisao da correcao, 1)."""
    from desdobra.chromium import navegador
    from desdobra.derivacao import medida_quebras
    monkeypatch.setattr(kv, 'FORMATOS', [('h1', 2048, 720), ('v1', 400, 800), ('v2', 440, 800)])

    def nao_mede(*_a, **_k):
        raise navegador.ErroNavegador('chromium que nao mede, simulado')
    medida_quebras.limpar_cache()
    monkeypatch.setattr(medida_quebras, '_conferir', nao_mede)
    try:
        j = kv.criar_job(tmp_path, 'a')
        conteudo = te.montar(j['job'])
        gid = _familia_de(conteudo, 'v1')
        assert conteudo['previas']['v1']['devolucao']['motivo'] == 'troca_forte_de_orientacao'
        versao = conteudo['familias'][gid]['versoes'][0]
        esc = _escolhas(conteudo, gid, versao, [_quebra(j['ids'])])
        r = conteudo['editar']({'familia': gid, 'versao': versao, 'edicoes': [], 'quebras': esc[gid]['quebras']},
                               'fixture_de_teste')
        membros = {m['formato']: m for m in r['membros']}
        ds = _salvar(j, conteudo, esc)
        for fid in ('v1', 'v2'):
            m, d = membros[fid], ds[fid]
            assert d['situacao'] == 'devolvido' and any(x['codigo'] == 'quebra_sem_medida' for x in d['registros'])
            # a previa mostra o mesmo: o membro devolvido, sem versao da galeria, e pede ajuste
            assert m['situacao'] == 'devolvido', m['situacao']
            assert [f['codigo'] for f in m['falhas']] == ['quebra_sem_medida'], m['falhas']
            assert m['palco']['selo'] == 'devolvido'
    finally:
        medida_quebras.limpar_cache()


@pytest.mark.parametrize('fid, w, h, versao', [('f1', 1920, 192, 'imagem_livre_fim'),
                                               ('f2000', 2000, 150, 'outra_estrutura')])
def test_as_falhas_da_versao_na_galeria_sao_as_que_o_salvar_grava(tmp_path, monkeypatch, fid, w, h, versao):
    """A versao da galeria que o DA escolhe sem editar: as falhas que a galeria mostra sao as da conferencia das caixas
    que a derivacao grava (arredondadas), e nao as do ruido do solver (revisao da correcao, 2)."""
    monkeypatch.setattr(kv, 'FORMATOS', [(fid, w, h)])
    j = kv.criar_job(tmp_path, 'a')
    conteudo = te.montar(j['job'])
    gid = _familia_de(conteudo, fid)
    v = next(x for x in conteudo['previas'][fid]['galeria']['variantes'] if x['id'] == versao)
    bruto = conteudo['editar'].__self__.brutos[fid][versao]
    na_tela = sorted({f['codigo'] for f in v['falhas']})
    validacoes_na_tela = sorted({f['medidas']['validacao'] for f in bruto['falhas_obrigatorias']
                                 if f['codigo'] == 'validacao_reprova'})
    d = _salvar(j, conteudo, _escolhas(conteudo, gid, versao))[fid]
    registro = next((r for r in d['registros'] if r['codigo'] == 'proposta_com_falha'), None)
    assert na_tela == (registro['medidas']['falhas'] if registro else []), (v['falhas'], d['registros'])
    assert validacoes_na_tela == sorted({x['nome'] for x in mv.reprovadas(d['validacoes'])})
    tela = {e['id']: [float(x) for x in e['caixa']] for e in v['palco']['elementos']}
    for e in d['elementos']:
        assert [float(x) for x in e['caixa']] == pytest.approx(tela[e['id']], abs=TOL)


def test_versao_gravada_que_a_galeria_nao_tem_mais_nao_trava_a_familia(tmp_path):
    """O rascunho da tela de antes guarda uma versao numa familia que hoje nao tem galeria. A pagina confirma a familia
    sem versao, como ela a mostra, e o "Salvar e seguir" passa (revisao da correcao, 3)."""
    import json

    from desdobra.briefing import salvar
    from desdobra.tela import rascunho as tr
    j = kv.criar_job(tmp_path, 'a')
    job = j['job']
    conteudo = te.montar(job)
    sem_galeria = [g for g, f in conteudo['familias'].items() if not f['versoes']]
    assert sem_galeria
    gid = sem_galeria[0]
    s = ts.ServidorTela(conteudo, pasta=job, modo_teste=True, atos=ta.atos_do_job(job, conteudo=conteudo)).iniciar()
    try:
        biscoito = tts._entrar(s)
        familias = {g: {'versao': ('espelhado' if g == gid else f['versoes'][0] if f['versoes'] else None),
                        'confirmada': False, 'edicoes': [], 'quebras': []}
                    for g, f in conteudo['familias'].items()}
        corpo = dict({'job_id': s.job_id, 'laudo_sha256': s.laudo_sha256, 'familias': familias},
                     **kv.passo_2(j['funcoes']))
        assert tte._escrever(s, '/api/rascunho', corpo, cookie=biscoito)[0] == 200
        _ato(s, biscoito, 'modo_dados', {'modo': 'c'})
        for g, f in familias.items():
            # o que a pagina manda: sem galeria, a versao vai nula (tela.js, atualizarBotaoFamilia)
            _ato(s, biscoito, 'familia', {'familia': g, 'versao': None if g == gid else f['versao'], 'edicoes': [],
                                          'quebras': []})
        dados = json.loads((job / tr.ARQUIVO).read_text(encoding='utf-8'))
        assert dados['familias'][gid]['confirmada'] and dados['familias'][gid]['versao'] is None
        assert [x for x in salvar.pendencias(job, conteudo) if x.get('familia') == gid] == []
    finally:
        s.parar()


def test_confirmacao_da_tela_de_antes_da_previa_igual_ao_salvar_cai(tmp_path):
    """A impressao da confirmacao leva a regra da previa: a familia confirmada pela tela de antes da correcao (a
    impressao sem a regra) pede a confirmacao de novo, porque a previa agora pode mostrar falha que antes nao mostrava
    (decisao 175; revisao da correcao, 4)."""
    import hashlib
    import json

    from desdobra.briefing import salvar
    from desdobra.tela import rascunho as tr

    def impressao_de_antes(fids, formatos, versoes):
        # a impressao das pecas como a tela de antes (cf50eb3) a gravava
        itens = []
        for f in fids:
            d = formatos.get(f) or {}
            a = d.get('areas') or {}
            au, seg = a.get('area_util'), a.get('area_segura')
            itens.append([f, (d.get('formato') or {}).get('composicao'), d.get('situacao'),
                          (d.get('devolucao') or {}).get('motivo'), au and au.get('caixa'),
                          [[x.get('lado'), x.get('px'), x.get('caixa')] for x in a.get('faixas') or []],
                          seg and [seg.get('caixa'), seg.get('lados')]])
        texto = json.dumps({'formatos': itens, 'versoes': sorted(versoes)}, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(texto.encode('utf-8')).hexdigest()
    j = kv.criar_job(tmp_path, 'a')
    job = j['job']
    conteudo = te.montar(job)
    s = ts.ServidorTela(conteudo, pasta=job, modo_teste=True, atos=ta.atos_do_job(job, conteudo=conteudo)).iniciar()
    try:
        biscoito = tts._entrar(s)
        familias = {g: {'versao': f['versoes'][0] if f['versoes'] else None, 'confirmada': False, 'edicoes': [],
                        'quebras': []} for g, f in conteudo['familias'].items()}
        corpo = dict({'job_id': s.job_id, 'laudo_sha256': s.laudo_sha256, 'familias': familias},
                     **kv.passo_2(j['funcoes']))
        assert tte._escrever(s, '/api/rascunho', corpo, cookie=biscoito)[0] == 200
        _ato(s, biscoito, 'modo_dados', {'modo': 'c'})
        for g, e in familias.items():
            _ato(s, biscoito, 'familia', {'familia': g, 'versao': e['versao'], 'edicoes': [], 'quebras': []})
    finally:
        s.parar()
    assert [x for x in salvar.pendencias(job, conteudo) if x.get('familia')] == []
    # o mesmo rascunho com a impressao que a tela de antes gravava
    derivados = conteudo['editar'].__self__.derivados
    dados = json.loads((job / tr.ARQUIVO).read_text(encoding='utf-8'))
    for g, f in dados['familias'].items():
        f['confirmacao']['pecas'] = impressao_de_antes(conteudo['familias'][g]['formatos'], derivados,
                                                       conteudo['familias'][g]['versoes'])
    contratos.gravar(job / tr.ARQUIVO, dados, tr.ESQUEMA)
    conteudo = te.montar(job)
    pend = sorted(x['familia'] for x in salvar.pendencias(job, conteudo)
                  if x.get('codigo') == 'familia_sem_confirmacao')
    assert pend == sorted(conteudo['familias']), pend
