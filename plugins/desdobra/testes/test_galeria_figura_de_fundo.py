# -*- coding: utf-8 -*-
"""A foto de fundo (decisoes-v1.md, n 202, de 20/11, revendo a 96 so neste caso): no KV deitado com a figura
(galeria.figura), no formato em pe ou quadrado, a versao da galeria sem a foto numa banda deixa a foto de fundo, atras
do conteudo, e o conteudo sobre ela nao e falha. So numeros: o KV A sintetico de test_galeria_generalidade (1920 x
1080, a pessoa a direita, encostada so na base).
  - no v1080x1920, no m300x600 e no q1080, ao menos uma versao de fundo e limpa e esta na galeria; o conteudo dela
    fica sobre a foto sem falha, e a foto fica com o piso da 133;
  - no s160x600, o titulo no piso da 133 e mais largo que o formato: a versao de fundo continua com falha, mas
    nenhuma falha e da foto (sobreposicao, 135, colisao, quadro);
  - as versoes com banda ficam como antes e continuam na galeria (a primeira e a de antes; so
    derivacao.galeria_fundo_max de fundo vem antes das com banda), e o cartaz (KV em pe) nao muda;
  - o formato deitado do KV A nao ganha a foto de fundo;
  - a copia para outro arquivo da familia mantem a versao limpa, e a derivacao grava o registro e o campo (nunca da
    foto que o DA apagou);
  - a validacao do motor: a foto de fundo sai da colisao, e a foto acima de um texto ou de um objeto solto na pilha
    reprova, com a frase da causa na galeria."""
import pytest

import test_derivacao_apoio as ap
import test_galeria_generalidade as tgg
from desdobra import contratos
from desdobra import limites
from desdobra.derivacao import escala as mesc
from desdobra.derivacao import galeria as mg
from desdobra.derivacao import nucleo as nd
from desdobra.derivacao import proposta
from desdobra.derivacao import solver as ms
from desdobra.derivacao import validacao as mval
try:
    # a geometria do cartaz fica so na maquina do Duda, fora do repositorio (autorizada so para calibrar, 19/11)
    import calibracao_galeria as cg
    from sinteticos import kv_cartaz as KC
except ImportError:
    cg = KC = None
SEM_CARTAZ = pytest.mark.skipif(KC is None, reason='testes/sinteticos/kv_cartaz.py fica fora do repositorio')

FOLGA = 1e-6
FIG = 'el2'  # a pessoa do KV A
EM_PE = ('v1080x1920', 'm300x600', 's160x600', 'q1080')
LIMPAS = ('v1080x1920', 'm300x600', 'q1080')
DEITADOS = ('w970x250', 'b728x90')
FRASE = 'fica de fundo, atrás do conteúdo'
KW = {'specs': {}, 'arquivo_specs': None, 'params': None}


def _area(c):
    return max(0.0, c[2] - c[0]) * max(0.0, c[3] - c[1])


def _inter(a, b):
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def _kv_a(formatos=None):
    laudo, funcoes, ancoras, fmts = tgg.kv_a()
    b = ap.briefing(funcoes=funcoes, regras=tgg.REGRAS, ancoras=ancoras,
                    formatos=[ap.formato(i, w, h) for i, w, h in (formatos or fmts)])
    ctx = nd.contexto(laudo, b)
    r = nd.derivar_em_memoria(ctx, specs={})
    return ctx, r, {f['id']: f for f in b['formatos']}


@pytest.fixture(scope='module')
def kv_a():
    ctx, r, fs = _kv_a()
    kv = r['kv']
    assert mg.figura(kv)['id'] == FIG
    return {'ctx': ctx, 'kv': kv, 'formatos': fs,
            'galerias': {fid: mg.variantes(ctx, kv, fs[fid]) for fid in EM_PE + DEITADOS}}


def _de_fundo(vs):
    return [v for v in vs if v['estrutura'].get('figura_de_fundo') == FIG]


# ------------------------------------------------------------------ a galeria
def test_versao_de_fundo_limpa_e_listada(kv_a):
    for fid in LIMPAS:
        vs = kv_a['galerias'][fid]
        limpas = [v for v in _de_fundo(vs) if not v['falhas_obrigatorias']]
        assert limpas, (fid, [(v['id'], v['estrutura'].get('figura_de_fundo'), v['falhas_obrigatorias']) for v in vs])
        for v in limpas:
            assert v['estrutura']['figura'] is None
            assert FRASE in v['descricao'], v['descricao']
            # a foto que passa a sangrar nao e a arte da parte livre
            assert not [a for a in v['avisos'] if a['codigo'] == 'sangria_da_arte_mudou'], v['avisos']


def test_conteudo_sobre_a_foto_sem_falha(kv_a):
    kv = kv_a['kv']
    for fid in ('v1080x1920', 'm300x600'):
        for v in [x for x in _de_fundo(kv_a['galerias'][fid]) if not x['falhas_obrigatorias']]:
            cx = {e['id']: e['caixa'] for e in v['elementos']}
            sobre = [e['id'] for e in kv['elementos']
                     if e['id'] != FIG and ms.conteudo(e) and _inter(cx[e['id']], cx[FIG]) > FOLGA * _area(cx[e['id']])]
            assert sobre, (fid, v['id'])


def test_foto_de_fundo_fica_com_o_piso_da_133(kv_a):
    kv = kv_a['kv']
    piso = limites.valor('derivacao.escala_conteudo_min_da_regra')
    e = next(x for x in kv['elementos'] if x['id'] == FIG)
    for fid in EM_PE:
        f = kv_a['formatos'][fid]
        regra = mesc.escala(e['regra'], (kv['largura'], kv['altura']), (f['largura'], f['altura']))
        vs = _de_fundo(kv_a['galerias'][fid])
        assert vs, fid
        for v in vs:
            el = next(x for x in v['elementos'] if x['id'] == FIG)
            assert el['escala'] >= piso * regra - FOLGA, (fid, v['id'], el['escala'], regra)


def test_nenhuma_falha_da_foto_de_fundo_nos_formatos_em_pe(kv_a):
    """Tambem no s160x600, onde o titulo no piso da 133 nao cabe na largura: a falha que fica e do conteudo, nunca da
    foto (antes: sobreposicao, 135, colisao, cena e o quadro da foto)."""
    for fid in EM_PE:
        for v in _de_fundo(kv_a['galerias'][fid]):
            for f in v['falhas_obrigatorias']:
                assert FIG not in f['elementos'], (fid, v['id'], f)
                assert (f.get('medidas') or {}).get('validacao') not in (
                    'colisao_nova_contra_a_origem', 'cena_cobre_conteudo', 'figura_de_fundo_acima_do_conteudo'), \
                    (fid, v['id'], f)
    s160 = kv_a['galerias']['s160x600']
    assert _de_fundo(s160)
    # o titulo no piso da 133 e mais largo que o formato (o que fica nao e da foto)
    assert any(f['codigo'] == 'fora_do_quadro' for v in _de_fundo(s160) for f in v['falhas_obrigatorias'])


def test_formato_deitado_nao_ganha_foto_de_fundo(kv_a):
    ctx, kv, fs = kv_a['ctx'], kv_a['kv'], kv_a['formatos']
    for fid in DEITADOS:
        assert not _de_fundo(kv_a['galerias'][fid]), fid
        cf = mg._contexto(ctx, kv, fs[fid])
        p = mg.parametros_do_id('reorganizado')
        assert mg.figura_de_fundo(cf, p) is None
        v = dict(mg.gerar(cf, p), id='reorganizado')
        out = mg._saida(cf, mg._resolvida(cf, v), 0)
        assert out['estrutura']['figura_de_fundo'] is None
        assert any(f['codigo'] == 'sobreposicao_nova' and FIG in f['elementos'] for f in out['falhas_obrigatorias']), \
            (fid, out['falhas_obrigatorias'])


def test_versoes_com_banda_nao_mudam(kv_a, monkeypatch):
    """A versao com a foto numa banda sai igual com e sem a regra da foto de fundo."""
    ctx, kv, fs = kv_a['ctx'], kv_a['kv'], kv_a['formatos']
    for fid in EM_PE:
        ps = [p for p in mg._parametros(mg._contexto(ctx, kv, fs[fid]))
              if p['fig'] is not None and p['modo'] == 'melhor' and not p['espelhar']]
        assert ps, fid

        def saidas():
            cf = mg._contexto(ctx, kv, fs[fid])
            outs = []
            for p in ps:
                v = mg.gerar(cf, p)
                if v is not None:
                    v['id'] = mg._id(p)
                    r = mg._resolvida(cf, v)
                    outs.append((mg._saida(cf, r, 0), mg.nota(cf, r, 0)))
            return outs
        agora = saidas()
        with monkeypatch.context() as m:
            m.setattr(mg, 'figura_de_fundo', lambda _cf, _p: None)
            antes = saidas()
        assert agora == antes, fid


def _com_banda(vs):
    return [v['id'] for v in vs if mg.parametros_do_id(v['id'])['fig'] is not None]


def test_versoes_com_banda_continuam_na_galeria(kv_a, monkeypatch):
    """A versao de fundo e uma opcao a mais, nunca o lugar das versoes com a foto numa banda (revisao da 0.11.0): a
    primeira versao e a de antes (a partida de quem nao escolheu versao nao muda), as com banda vem na ordem de antes,
    as limpas com banda de antes ficam ate o teto menos derivacao.galeria_fundo_max, e so esse tanto de versoes de
    fundo vem antes da ultima com banda."""
    ctx, kv, fs = kv_a['ctx'], kv_a['kv'], kv_a['formatos']
    limite = int(limites.valor('derivacao.galeria_variantes_max'))
    fundo_max = int(limites.valor('derivacao.galeria_fundo_max'))
    monkeypatch.setattr(mg, 'figura_de_fundo', lambda _cf, _p: None)
    for fid in EM_PE:
        antes, agora = mg.variantes(ctx, kv, fs[fid]), kv_a['galerias'][fid]
        assert agora[0]['id'] == antes[0]['id'], fid
        assert agora[0]['estrutura']['figura_de_fundo'] is None, fid
        banda = _com_banda(agora)
        assert banda == _com_banda(antes)[:len(banda)], (fid, banda, _com_banda(antes))

        def limpas(vs):
            return [x for x in _com_banda(vs) if not next(v for v in vs if v['id'] == x)['falhas_obrigatorias']]
        assert limpas(agora) == limpas(antes)[:limite - fundo_max], (fid, limpas(agora), limpas(antes))
        ultima = max(i for i, v in enumerate(agora) if v['id'] in banda)
        assert len(_de_fundo(agora[:ultima])) <= fundo_max, fid


@SEM_CARTAZ
def test_cartaz_em_pe_nao_muda(monkeypatch):
    """O cartaz (KV em pe, test_galeria_calibracao) nunca ganha a foto de fundo, nem no quadrado."""
    ctx, kv, fs = cg.preparar()
    for fid in KC.METAS:
        cf = mg._contexto(ctx, kv, fs[fid])
        assert cf['_figura'] is not None
        assert mg.figura_de_fundo(cf, mg.parametros_do_id('reorganizado')) is None, fid
    agora = {fid: mg.variantes(ctx, kv, fs[fid]) for fid in KC.METAS}
    monkeypatch.setattr(mg, 'figura_de_fundo', lambda _cf, _p: None)
    antes = {fid: mg.variantes(ctx, kv, fs[fid]) for fid in KC.METAS}
    assert agora == antes
    assert all(v['estrutura']['figura_de_fundo'] is None for vs in agora.values() for v in vs)


# ------------------------------------------------------------------ a familia e o "Salvar e seguir"
def test_copia_da_familia_mantem_a_versao_de_fundo_limpa():
    """O arquivo de edicao (1080x1920) parte da versao de fundo limpa; o 300x600 da mesma familia copia o layout dele
    com a foto de fundo (recalculada pela orientacao do 300x600) e sai sem falha. A derivacao de cada um grava o
    registro figura_de_fundo e o campo no elemento, sem validacao que reprova, no contrato derivacao/1."""
    ctx, r, fs = _kv_a([('v1080x1920', 1080, 1920), ('m300x600', 300, 600)])
    kv = r['kv']
    formatos = [fs['v1080x1920'], fs['m300x600']]
    gal, _mestre, sem = proposta.galeria_dos_devolvidos(ctx, kv, r['formatos'], formatos, **KW)
    assert not sem
    versoes = {fid: {v['id']: v for _n, v in pares} for fid, pares in gal.items()}
    vid = next(k for k, v in versoes['v1080x1920'].items()
               if v['estrutura'].get('figura_de_fundo') == FIG and not v['falhas_obrigatorias'])
    familia = {'familia': 'g', 'formatos': ['v1080x1920', 'm300x600'], 'versao': vid, 'edicoes': []}
    lays = proposta.layout_da_familia(ctx, kv, familia, derivados=r['formatos'], versoes=versoes, **KW)
    ref, copia = lays['v1080x1920'], lays['m300x600']
    assert ref['versao'] == vid and ref['figura_de_fundo'] == FIG
    assert copia['versao'] == vid and copia['figura_de_fundo'] == FIG
    for lay in (ref, copia):
        assert not lay['falhas'] and not lay['reprovadas'], lay['falhas']
    assert copia['situacao'] in ('igual', 'ajustado'), copia['situacao']
    # o conteudo da copia fica sobre a foto, sem falha
    cx = copia['caixas_visiveis']
    assert any(_inter(cx[e['id']], cx[FIG]) > 0 for e in kv['elementos'] if e['id'] != FIG and ms.conteudo(e))
    pr = {'familia': 'g', 'versao': vid, 'edicoes': 0, 'confirmada': False, 'confirmacao': None}
    for fid, lay in lays.items():
        novo = proposta._derivacao(ctx, kv, lay['cf'], r['formatos'][fid], lay, lay['caminho'], pr, 'da',
                                   d_ref=r['formatos']['v1080x1920'])
        assert novo['situacao'] == 'derivado', (fid, novo['devolucao'])
        reg = [x for x in novo['registros'] if x['codigo'] == 'figura_de_fundo']
        assert reg == [{'codigo': 'figura_de_fundo', 'medidas': {'elemento': FIG, 'versao': vid}}], fid
        assert [e['id'] for e in novo['elementos'] if e.get('figura_de_fundo')] == [FIG]
        assert not mval.reprovadas(novo['validacoes']), (fid, mval.reprovadas(novo['validacoes']))
        assert not [x for x in novo['registros'] if x['codigo'] == 'proposta_com_falha'], fid
        contratos.validar(novo, nd.ESQUEMA)
    # sem a versao escolhida, a partida e a primeira sem falha (a com a foto numa banda), e o id efetivo vai junto
    sem_versao = proposta.layout_da_familia(ctx, kv, dict(familia, versao=None), derivados=r['formatos'],
                                            versoes=versoes, **KW)
    assert sem_versao['v1080x1920']['versao'] == proposta.versao_de_partida(None, versoes['v1080x1920'], None)
    assert sem_versao['v1080x1920']['figura_de_fundo'] is None
    # a foto que o DA apagou no palco nao fica de fundo: nem o layout nem a derivacao dizem que fica
    apagada = proposta.layout_da_familia(ctx, kv, dict(familia, edicoes=[{'elemento': FIG, 'acao': 'apagar'}]),
                                         derivados=r['formatos'], versoes=versoes, **KW)
    for fid, lay in apagada.items():
        assert FIG in lay['apagados'] and lay['figura_de_fundo'] is None, fid
        novo = proposta._derivacao(ctx, kv, lay['cf'], r['formatos'][fid], lay, lay['caminho'], pr, 'da',
                                   d_ref=r['formatos']['v1080x1920'])
        assert not [x for x in novo['registros'] if x['codigo'] == 'figura_de_fundo'], fid
        assert not [e for e in novo['elementos'] if e.get('figura_de_fundo')], fid


def test_copia_para_arquivo_deitado_confere_a_foto_como_conteudo():
    """A regra vale por arquivo: o arquivo deitado na familia de um arquivo de edicao em pe com a foto de fundo confere
    a foto como conteudo (a sobreposicao com ela pede ajuste)."""
    ctx, r, fs = _kv_a([('v1080x1920', 1080, 1920), ('w970x250', 970, 250)])
    kv = r['kv']
    formatos = [fs['v1080x1920'], fs['w970x250']]
    gal, _mestre, _sem = proposta.galeria_dos_devolvidos(ctx, kv, r['formatos'], formatos, **KW)
    versoes = {fid: {v['id']: v for _n, v in pares} for fid, pares in gal.items()}
    vid = next(k for k, v in versoes['v1080x1920'].items() if v['estrutura'].get('figura_de_fundo') == FIG)
    familia = {'familia': 'g', 'formatos': ['v1080x1920', 'w970x250'], 'versao': vid, 'edicoes': []}
    lays = proposta.layout_da_familia(ctx, kv, familia, derivados=r['formatos'], versoes=versoes, **KW)
    assert lays['v1080x1920']['figura_de_fundo'] == FIG
    deitado = lays['w970x250']
    assert deitado['figura_de_fundo'] is None
    assert any(f['codigo'] == 'sobreposicao_nova' and FIG in f['elementos'] for f in deitado['falhas'])


# ------------------------------------------------------------------ a validacao do motor
def _validar(z_foto, fundo):
    sg = {'esq': False, 'topo': False, 'dir': False, 'base': False}
    els = [{'id': 'el1', 'funcao': 'titulo', 'regra': 'x', 'classe': 'texto', 'sangra': sg, 'z': [2, 2]},
           {'id': 'el2', 'funcao': 'sujeito', 'regra': 'x', 'classe': 'base', 'sangra': dict(sg, base=True),
            'z': [z_foto, z_foto]}]
    kv = {'el1': {'caixa': [0, 0, 10, 10], 'z': [2, 2]}, 'el2': {'caixa': [20, 0, 30, 100], 'z': [z_foto, z_foto]}}
    esperado = {'el1': ('titulo', 'x'), 'el2': ('sujeito', 'x')}
    val = mval.validar((100, 100), {}, els, [[0, 0, 25, 10], [5, 0, 100, 100]], [1.0, 1.0], kv, esperado,
                       fundo=fundo)
    return {v['nome']: v for v in val}


def test_validacao_da_foto_de_fundo():
    # sem a foto de fundo, a foto sobre o titulo e colisao nova (decisoes-v1.md, 96), e a validacao nova nao aparece
    v = _validar(1, ())
    assert v['colisao_nova_contra_a_origem']['situacao'] == 'reprova'
    assert 'figura_de_fundo_acima_do_conteudo' not in v
    # de fundo, abaixo do titulo na pilha: nada reprova
    v = _validar(1, ('el2',))
    assert v['colisao_nova_contra_a_origem']['situacao'] == 'ok'
    assert v['figura_de_fundo_acima_do_conteudo']['situacao'] == 'ok'
    # de fundo, mas acima do titulo na pilha: o render pintaria a foto por cima dele
    v = _validar(3, ('el2',))
    assert v['colisao_nova_contra_a_origem']['situacao'] == 'ok'
    acima = v['figura_de_fundo_acima_do_conteudo']
    assert acima['situacao'] == 'reprova' and acima['medidas']['pares'] == [['el2', 'el1']]
    assert '202' in acima['fonte']['ref']


def _validar_icone(z_foto):
    """O icone opaco que nao sangra (objeto solto) embaixo da foto de fundo: o "nao sobrepor" o protege."""
    sg = {'esq': False, 'topo': False, 'dir': False, 'base': False}
    els = [{'id': 'el1', 'funcao': 'grafismo', 'regra': 'x', 'classe': 'base', 'opaco': True, 'sangra': sg,
            'z': [2, 2]},
           {'id': 'el2', 'funcao': 'sujeito', 'regra': 'x', 'classe': 'base', 'sangra': dict(sg, base=True),
            'z': [z_foto, z_foto]}]
    assert ms.objeto_solto(els[0]) and ms.par_que_nao_sobrepoe(els[0], els[1])
    kv = {'el1': {'caixa': [0, 0, 10, 10], 'z': [2, 2]}, 'el2': {'caixa': [20, 0, 30, 100], 'z': [z_foto, z_foto]}}
    esperado = {'el1': ('grafismo', 'x'), 'el2': ('sujeito', 'x')}
    val = mval.validar((100, 100), {}, els, [[0, 0, 25, 10], [5, 0, 100, 100]], [1.0, 1.0], kv, esperado,
                       fundo=('el2',))
    return {v['nome']: v for v in val}


def test_foto_de_fundo_acima_de_objeto_solto_reprova():
    v = _validar_icone(1)
    assert v['colisao_nova_contra_a_origem']['situacao'] == 'ok'
    assert v['figura_de_fundo_acima_do_conteudo']['situacao'] == 'ok'
    v = _validar_icone(3)
    acima = v['figura_de_fundo_acima_do_conteudo']
    assert acima['situacao'] == 'reprova' and acima['medidas']['pares'] == [['el2', 'el1']]


def test_foto_de_fundo_acima_do_conteudo_tem_frase_propria(kv_a, monkeypatch):
    """Na galeria e no palco, a foto de fundo acima de um conteudo na pilha vem com a causa e o que fazer, nunca so
    "a conferencia do motor reprova"; a validacao continua reprovando (o "Salvar e seguir" devolve). No aviso aceito
    pelo DA, a frase da validacao nao repete a da falha."""
    from desdobra.tela import estado
    v = next(x for x in kv_a['galerias']['q1080'] if x['estrutura'].get('figura_de_fundo') == FIG)
    cf = mg._contexto(kv_a['ctx'], kv_a['kv'], kv_a['formatos']['q1080'])
    caixas = {e['id']: e['caixa'] for e in v['elementos']}
    tit = next(e['id'] for e in kv_a['kv']['elementos'] if e['funcao'] == 'titulo')
    item = {'nome': mg.FUNDO_ACIMA, 'situacao': 'reprova', 'fonte': mval.FONTE_FUNDO, 'elementos': [FIG, tit],
            'medidas': {'pares': [[FIG, tit]]}}
    monkeypatch.setattr(mg, '_validacoes', lambda *_a, **_k: [item])
    falhas, _avisos, nomes = mg._conferir(cf, caixas, {}, com_validacoes=True, fundo=(FIG,))
    assert nomes == [mg.FUNDO_ACIMA]
    assert not [f for f in falhas if f['codigo'] == 'validacao_reprova']
    f = next(f for f in falhas if f['codigo'] == mg.FUNDO_ACIMA)
    assert f['elementos'] == [FIG, tit]
    assert f['texto'].startswith('A foto fica acima do título') and 'ordem das camadas do PSD' in f['texto'], f['texto']
    d = {'elementos': [], 'registros': [{'codigo': proposta.CODIGO_APROVADO_COM_AVISO,
                                         'medidas': {'falhas': [f], 'validacoes': [item]}}]}
    assert estado.avisos_aceitos(d) == [f['texto']]
