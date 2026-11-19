# -*- coding: utf-8 -*-
"""A copia do layout aprovado no arquivo de edicao para os outros arquivos da familia (decisao 199; etapa E1).

Funcoes puras de desdobra.derivacao.familia, so com geometria sintetica (familia_geometria): nenhum PSD, nenhum job.
O caso de aceitacao e a geometria do job de 18/11 que o Duda mediu: o 300x600 saia com a assinatura sobre o azul.
"""
import hashlib
import json
import math
import os
import subprocess
import sys
import textwrap

import pytest

import familia_geometria as G
from conftest import PASTA_MOTOR
from desdobra import limites
from desdobra.derivacao import familia as F

TESTES = os.path.dirname(os.path.abspath(__file__))


def _modelo(**kw):
    ref, els, sil = G.caso_diagonal(**kw)
    return F.extrair_modelo(ref, els, silhuetas=sil)


def _relacao(modelo, rid):
    return next(r for r in modelo['relacoes'] if r['id'] == rid)


def _diagonal_no_membro(lay):
    """Os dois pontos da diagonal do azul levados pela semelhanca da base no membro."""
    b = lay['bases']['azul']
    return [F._ponto(list(p), b['origem'], b['destino'], b['escala']) for p in (G.P1, G.P2)]


# ------------------------------------------------------------------ o arquivo de edicao (199, 1)
def test_arquivo_de_edicao_e_o_maior_sem_giro_e_depois_o_primeiro():
    assert F.arquivo_de_edicao([G.membro('f300x600', 300, 600), G.membro('f1080x1920', 1080, 1920)]) == 'f1080x1920'
    # empate de area (medida em pe): vence o sem giro
    assert F.arquivo_de_edicao([G.membro('g1920x1080r270', 1080, 1920, giro=270),
                                G.membro('f1080x1920', 1080, 1920)]) == 'f1080x1920'
    # empate sem giro: o primeiro da lista
    assert F.arquivo_de_edicao([G.membro('b', 1080, 1920), G.membro('a', 1080, 1920)]) == 'b'
    assert F.arquivo_de_edicao([]) is None


def test_arquivo_de_edicao_gravado_fica_quando_entra_um_maior():
    membros = [G.membro('f1080x1920', 1080, 1920), G.membro('f1200x2400', 1200, 2400)]
    assert F.arquivo_de_edicao(membros) == 'f1200x2400'
    assert F.arquivo_de_edicao(membros, gravado='f1080x1920') == 'f1080x1920'
    # o gravado que saiu da familia nao vale mais
    assert F.arquivo_de_edicao(membros, gravado='f300x600') == 'f1200x2400'


# ------------------------------------------------------------------ o modelo
def test_modelo_do_caso_tem_as_relacoes_da_assinatura_e_do_texto_com_o_azul():
    m = _modelo()
    assert m['elementos']['azul']['papel'] == 'base' and m['elementos']['fundo']['papel'] == 'fundo'
    livre = _relacao(m, 'livre_da_tinta:assinatura:azul')
    assert livre['folga'] == pytest.approx(5.2867, abs=1e-3)  # a assinatura a 5,3 px da diagonal no 1080x1920
    assert _relacao(m, 'dentro_da_tinta:texto:azul') and _relacao(m, 'dentro_da_tinta:titulo:azul')
    # o ponto fixo do azul e o da diagonal mais perto da assinatura
    b = m['bases']['azul']
    assert b['modo'] == 'borda' and b['hospede'] == 'assinatura'
    assert G.distancia_a_reta(b['ponto'], G.P1, G.INCLINACAO) == pytest.approx(0.0, abs=1e-9)
    # a faixa verde sem silhueta e conferida pela caixa, com o aviso
    assert {'codigo': 'forma_conferida_pela_caixa', 'elemento': 'verde'} in m['avisos']


def test_ancoras_do_caso():
    m = _modelo()
    x = {b['id']: b for b in m['blocos']['x']}
    y = {b['id']: b for b in m['blocos']['y']}
    # titulo e texto dividem a borda esquerda: andam juntos na largura
    assert x['x:titulo']['elementos'] == ['titulo', 'texto'] and x['x:titulo']['ancora']['lado'] == 'inicio'
    assert x['x:assinatura']['ancora']['lado'] == 'fim' and y['y:assinatura']['ancora']['lado'] == 'fim'
    assert y['y:titulo']['ancora']['lado'] == 'inicio' and y['y:texto']['ancora']['lado'] == 'inicio'


def test_ancora_margens_quase_iguais_da_o_centro_ou_a_do_design_system():
    ref = {'id': 'r', 'W': 1080.0, 'H': 1920.0, 'quadros': G.quadros(1080.0, 1920.0)}
    els = [{'id': 'titulo', 'classe': 'texto', 'funcao': 'titulo', 'caixa': [60.0, 100.0, 1030.0, 300.0]}]
    assert F.extrair_modelo(ref, els)['blocos']['x'][0]['ancora'] == {'lado': 'centro', 'quadro': 'margem',
                                                                    'origem': 'centro'}
    els[0]['ancora'] = ('esquerda', 'topo')
    assert F.extrair_modelo(ref, els)['blocos']['x'][0]['ancora'] == {'lado': 'inicio', 'quadro': 'margem',
                                                                    'origem': 'design_system'}
    # a intencao explicita de alinhar (185) vence a borda mais perto
    intencao = [{'elementos': ['titulo'], 'eixo': 'y', 'alvo': 'base', 'referencia': 'area_segura'}]
    assert F.extrair_modelo(ref, els, intencoes=intencao)['blocos']['y'][0]['ancora'] == {
        'lado': 'fim', 'quadro': 'area_segura', 'origem': 'intencao'}


# ------------------------------------------------------------------ o caso de aceitacao (18/11)
def test_300x600_assinatura_no_branco_com_a_largura_do_aprovado_e_sem_ajuste():
    m = _modelo()
    lay = F.ajustar_minimo(m, F.transferir(m, G.membro('f300x600', 300, 600)))
    W, H, s = lay['W'], lay['H'], lay['s']
    assert s == pytest.approx(300.0 / 1080.0, abs=1e-12)
    a = lay['caixas']['assinatura']
    assert (a[2] - a[0]) / W == pytest.approx(0.463, abs=0.01)  # hoje saia com 0,53
    folga_ref = _relacao(m, 'livre_da_tinta:assinatura:azul')['folga']
    rel = {r['id']: r for r in F.relacoes(m, lay)}
    livre = rel['livre_da_tinta:assinatura:azul']
    assert livre['ok'] and not livre['invade'] and livre['medida'] >= folga_ref * s - 1e-6
    assert all(r['ok'] for r in rel.values())
    assert lay['situacao'] == 'igual' and lay['ajustes'] == [] and lay['relacoes_quebradas'] == []
    # conferido fora do motor: o canto de cima a esquerda da assinatura fica abaixo da diagonal levada, com a folga
    p1, p2 = _diagonal_no_membro(lay)
    inclinacao = (p2[1] - p1[1]) / (p2[0] - p1[0])
    assert inclinacao == pytest.approx(G.INCLINACAO, abs=1e-12)  # o mesmo angulo
    assert G.distancia_a_reta([a[0], a[1]], p1, inclinacao) == pytest.approx(folga_ref * s, abs=1e-6)
    # o mesmo lugar em relacao a assinatura (199, 2) faz a diagonal cruzar a borda direita em 0,706 H: com a
    # proporcao 2,0 contra 1,78 do 1080x1920, o mesmo angulo preso a assinatura nao cai nos 0,67 da sonda do cover
    y_dir = p1[1] + (W - p1[0]) * inclinacao
    assert y_dir / H == pytest.approx(0.706, abs=0.01)
    # o titulo e o texto continuam no azul, e o azul cresce so para voltar a sangrar
    assert rel['dentro_da_tinta:texto:azul']['ok'] and rel['dentro_da_tinta:titulo:azul']['ok']
    b = lay['bases']['azul']
    assert b['crescimento'] >= 1.0 and lay['caixas_asset']['azul'][1] <= 0.0 and lay['caixas_asset']['azul'][2] >= W


def test_300x600_com_a_silhueta_em_grade():
    m = _modelo(silhueta='grade')
    assert _relacao(m, 'livre_da_tinta:assinatura:azul')
    lay = F.ajustar_minimo(m, F.transferir(m, G.membro('f300x600', 300, 600)))
    assert lay['situacao'] == 'igual' and F.relacoes_furadas(m, lay) == []


def test_sem_silhueta_a_forma_e_conferida_pela_caixa_com_aviso():
    m = _modelo(silhueta=None)
    assert {'codigo': 'forma_conferida_pela_caixa', 'elemento': 'azul'} in m['avisos']
    lay = F.transferir(m, G.membro('f300x600', 300, 600))
    assert {'codigo': 'forma_conferida_pela_caixa', 'elemento': 'azul'} in lay['avisos']


def test_transferir_para_a_propria_referencia_da_0_px():
    m = _modelo()
    lay = F.ajustar_minimo(m, F.transferir(m, G.membro('f1080x1920', 1080, 1920)))
    assert lay['s'] == 1.0 and lay['sobra'] == {'x': 0.0, 'y': 0.0}
    for k in m['ordem']:
        assert lay['caixas'][k] == m['elementos'][k]['caixa'], k
    for k, b in lay['bases'].items():
        assert b['destino'] == b['origem'] and b['escala'] == 1.0, k
        assert lay['caixas_asset'][k] == m['elementos'][k]['caixa_asset'], k
    assert lay['situacao'] == 'igual'


def test_giros_270_identico_e_90_com_as_mesmas_fracoes():
    m = _modelo()
    ref = F.transferir(m, G.membro('f1080x1920', 1080, 1920))
    g270 = F.transferir(m, G.membro('g1920x1080r270', 1080, 1920, giro=270))
    assert g270['caixas'] == ref['caixas'] and g270['bases'] == ref['bases']
    g90 = F.ajustar_minimo(m, F.transferir(m, G.membro('g640x360r90', 360, 640, giro=90)))
    assert g90['situacao'] == 'igual'
    for k in m['ordem']:
        a, b = ref['caixas'][k], g90['caixas'][k]
        for i, lado in enumerate((1080.0, 1920.0, 1080.0, 1920.0)):
            assert b[i] / (lado / 3.0) == pytest.approx(a[i] / lado, abs=1e-6), k


@pytest.mark.parametrize('fid, W, H', [('f1080x1600', 1080, 1600), ('f900x1870', 900, 1870)])
def test_pontas_da_faixa_a_copia_ja_cabe(fid, W, H):
    m = _modelo()
    tr = F.transferir(m, G.membro(fid, W, H))
    assert F.relacoes_furadas(m, tr) == []
    lay = F.ajustar_minimo(m, tr)
    assert lay['situacao'] == 'igual' and lay['ajustes'] == []


def test_mutacao_crescer_a_forma_em_volta_do_centro_faz_a_familia_falhar(monkeypatch):
    """Prova que o teste ve o defeito: com as formas crescendo em volta do proprio centro (como a galeria faz com o
    fundo) e nao em volta do ponto da borda que anda com o conteudo, a copia perde relacoes do aprovado. No 300x600
    a faixa verde invade a folga do titulo e do texto; na ponta larga (1080x1600) a assinatura cai sobre o azul."""
    m = _modelo()
    original = F._ponto_fixo

    def no_centro(modelo, est, k):
        x = modelo['elementos'][k]
        if modelo['bases'][k]['modo'] != 'borda':
            return original(modelo, est, k)
        p = [(x['caixa'][0] + x['caixa'][2]) / 2.0, (x['caixa'][1] + x['caixa'][3]) / 2.0]
        return p, [p[0] * est['W'] / modelo['W'], p[1] * est['H'] / modelo['H']]
    sem_mutacao = {fid: F.relacoes_furadas(m, F.transferir(m, G.membro(fid, W, H)))
                   for fid, W, H in (('f300x600', 300, 600), ('f1080x1600', 1080, 1600))}
    assert sem_mutacao == {'f300x600': [], 'f1080x1600': []}
    monkeypatch.setattr(F, '_ponto_fixo', no_centro)
    f300 = F.relacoes_furadas(m, F.transferir(m, G.membro('f300x600', 300, 600)))
    assert f300 and {r['id'] for r in f300} >= {'livre_da_tinta:titulo:verde', 'livre_da_tinta:texto:verde'}
    larga = {r['id']: r for r in F.relacoes_furadas(m, F.transferir(m, G.membro('f1080x1600', 1080, 1600)))}
    assert larga['livre_da_tinta:assinatura:azul']['invade']


# ------------------------------------------------------------------ protecao de fundo
def _faixa_branca(com_legal=False):
    """Fundo azul, faixa branca estreita no meio (sangra dos dois lados) com a assinatura dentro, e o texto 5 px
    acima da faixa. A faixa anda com o texto (o mais perto da borda dela); a assinatura, mais perto da base."""
    ref = {'id': 'f1080x1920', 'W': 1080.0, 'H': 1920.0, 'quadros': G.quadros(1080.0, 1920.0)}
    els = [
        {'id': 'fundo', 'classe': 'base', 'funcao': 'fundo', 'caixa': [0.0, 0.0, 1080.0, 1920.0],
         'sangra': dict(G.TODOS)},
        {'id': 'faixa', 'classe': 'base', 'funcao': 'grafismo', 'caixa': [0.0, 1000.0, 1080.0, 1100.0],
         'caixa_asset': [-20.0, 1000.0, 1100.0, 1100.0], 'sangra': {'esq': True, 'dir': True}},
        {'id': 'titulo', 'classe': 'texto', 'funcao': 'titulo', 'caixa': [100.0, 100.0, 980.0, 300.0]},
        {'id': 'texto', 'classe': 'texto', 'funcao': 'texto_de_apoio', 'caixa': [100.0, 900.0, 980.0, 995.0]},
        {'id': 'assinatura', 'classe': 'marca', 'funcao': 'assinatura_institucional',
         'caixa': [390.0, 1020.0, 690.0, 1080.0]},
    ]
    if com_legal:
        els.append({'id': 'legal', 'classe': 'texto', 'funcao': 'texto_legal', 'caixa': [150.0, 1110.0, 930.0, 1160.0]})
    sil = {'faixa': {'poligono': [[0, 0], [1, 0], [1, 1], [0, 1]]}}
    return F.extrair_modelo(ref, els, silhuetas=sil)


def test_protecao_de_fundo_desfaz_a_ancora_que_tiraria_a_assinatura_da_faixa_branca(monkeypatch):
    m = _faixa_branca()
    assert m['bases']['faixa']['hospede'] == 'texto'
    assert _relacao(m, 'dentro_da_tinta:assinatura:faixa')
    membro = G.membro('f300x600', 300, 600)
    lay = F.ajustar_minimo(m, F.transferir(m, membro))
    desfeitas = [a for a in lay['ajustes'] if a['codigo'] == 'ancora_desfeita_pelo_fundo']
    assert [(a['elemento'], a['base']) for a in desfeitas] == [('assinatura', 'faixa')]
    assert desfeitas[0]['frase'] == ('A assinatura ficou no mesmo lugar em relação à forma, como no seu arquivo, '
                                     'para não mudar de fundo.')
    assert lay['situacao'] == 'ajustado' and F.relacoes_furadas(m, lay) == []
    # posicao rigida em relacao a faixa: 20 px abaixo da borda de cima dela, vezes s
    assert lay['caixas']['assinatura'][1] - lay['caixas']['faixa'][1] == pytest.approx(20.0 * lay['s'], abs=1e-9)
    # sem a protecao, a ancora da base levava a assinatura para o azul
    monkeypatch.setattr(F, '_protecao', lambda modelo, est: None)
    sem = {r['id']: r for r in F.relacoes_furadas(m, F.transferir(m, membro))}
    assert not sem['dentro_da_tinta:assinatura:faixa']['ok']


# ------------------------------------------------------------------ a sobra nunca aproxima dois conteudos
def test_sobra_nunca_aproxima_dois_conteudos():
    """A intencao do DA prende o de cima na base e o de baixo no topo: sozinhas, as ancoras os aproximariam na sobra.
    O bloco de baixo anda o mesmo que o de cima, e o vao fica o do aprovado vezes s."""
    ref = {'id': 'r', 'W': 1080.0, 'H': 1920.0, 'quadros': G.quadros(1080.0, 1920.0)}
    els = [{'id': 'a', 'classe': 'texto', 'funcao': 'titulo', 'caixa': [100.0, 800.0, 900.0, 900.0]},
           {'id': 'b', 'classe': 'texto', 'funcao': 'texto_de_apoio', 'caixa': [150.0, 1000.0, 850.0, 1100.0]}]
    intencoes = [{'elementos': ['a'], 'eixo': 'y', 'alvo': 'base', 'referencia': 'margem'},
                 {'elementos': ['b'], 'eixo': 'y', 'alvo': 'topo', 'referencia': 'margem'}]
    m = F.extrair_modelo(ref, els, intencoes=intencoes)
    lay = F.transferir(m, G.membro('f300x600', 300, 600))
    a, b = lay['caixas']['a'], lay['caixas']['b']
    assert b[1] - a[3] >= 100.0 * lay['s'] - 1e-9
    assert lay['blocos']['y']['y:b']['origem'] == 'ordem'


# ------------------------------------------------------------------ determinismo e ordem dos membros
def _texto(resultado):
    return json.dumps(resultado, sort_keys=True, ensure_ascii=False)


def test_mesma_entrada_mesma_saida_byte_a_byte_e_ordem_dos_membros_nao_muda_nada():
    m = _modelo()
    membros = G.membros_do_caso()
    um = _texto(F.copiar_familia(m, membros))
    assert _texto(F.copiar_familia(_modelo(), membros)) == um
    assert _texto(F.copiar_familia(m, list(reversed(membros)))) == um
    assert _texto(F.copiar_familia(m, membros[2:] + membros[:2])) == um
    for ordem in (membros, list(reversed(membros))):
        assert F.arquivo_de_edicao(ordem) == 'f1080x1920'


def test_mesma_saida_com_outro_hash_do_processo():
    """O texto de saida nao depende da ordem de conjuntos nem do hash de texto do processo."""
    codigo = textwrap.dedent('''
        import hashlib, json
        import familia_geometria as G
        from desdobra.derivacao import familia as F
        ref, els, sil = G.caso_diagonal()
        m = F.extrair_modelo(ref, els, silhuetas=sil)
        r = F.copiar_familia(m, G.membros_do_caso())
        print(hashlib.sha256(json.dumps([m, r], sort_keys=True).encode()).hexdigest())
    ''')
    saidas = []
    for semente in ('0', '4242'):
        env = dict(os.environ, PYTHONHASHSEED=semente,
                   PYTHONPATH=os.pathsep.join([str(PASTA_MOTOR), TESTES]))
        p = subprocess.run([sys.executable, '-c', codigo], env=env, capture_output=True, text=True, timeout=120)
        assert p.returncode == 0, p.stderr
        saidas.append(p.stdout.strip())
    m = _modelo()
    texto = json.dumps([m, F.copiar_familia(m, G.membros_do_caso())], sort_keys=True)
    aqui = hashlib.sha256(texto.encode()).hexdigest()
    assert saidas == [aqui, aqui]


def test_o_modulo_e_puro():
    """Nada de arquivo, rede ou processo no modulo da familia."""
    fonte = open(F.__file__, encoding='utf-8').read()
    for proibido in ('open(', 'pathlib', 'subprocess', 'socket', 'contratos.', 'json.load', 'smart_object'):
        assert proibido not in fonte, proibido
    assert math.isfinite(limites.valor('derivacao.bloco_fundo_fracao'))


def test_escala_da_copia_nunca_passa_de_1_com_a_area_segura_do_arquivo_de_edicao():
    """Revisao da 0.10.0 (199, 1): a area segura do arquivo de edicao aperta o quadro dele; o membro um pouco menor e
    sem area segura dava s = 1,11, e a assinatura saia com 555 px contra os 500 do aprovado."""
    ref, els, sil = G.caso_diagonal()
    ref['quadros'] = G.quadros(1080.0, 1920.0, area_segura=[150.0, 150.0, 930.0, 1770.0])
    m = F.extrair_modelo(ref, els, silhuetas=sil)
    assert F.arquivo_de_edicao([{'id': 'ref', 'W': 1080, 'H': 1920}, {'id': 'm', 'W': 1000, 'H': 1900}]) == 'ref'
    tr = F.transferir(m, G.membro('f1000x1900', 1000, 1900))
    assert tr['s'] == 1.0
    a = tr['caixas']['assinatura']
    assert a[2] - a[0] == pytest.approx(500.0)


def test_grupo_com_a_faixa_que_sangra_nao_muda_a_ancora_da_assinatura():
    """Revisao da 0.10.0: o DA junta a assinatura com a faixa verde (que sangra no topo, na base e a esquerda) sem mexer
    em nada. A ancora do bloco sai do que nao sangra: a assinatura fica presa a base como antes, e a faixa a segue e
    cresce so para continuar sangrando. Antes, a caixa da faixa levava a ancora ao centro e a assinatura subia 33 px."""
    ref, els, sil = G.caso_diagonal()
    solto = F.extrair_modelo(ref, els, silhuetas=sil)
    junto = F.extrair_modelo(ref, els, silhuetas=sil, grupos=[['assinatura', 'verde']])
    mem = G.membro('f300x600', 300, 600)
    a, b = F.transferir(solto, mem), F.transferir(junto, mem)
    assert b['caixas']['assinatura'] == pytest.approx(a['caixas']['assinatura'], abs=1e-6)
    v = b['caixas']['verde']
    assert v[0] <= 1e-6 and v[1] <= 1e-6 and v[3] >= 600.0 - 1e-6
