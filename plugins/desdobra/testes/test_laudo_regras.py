# -*- coding: utf-8 -*-
"""Laudo como funcao pura: regras B1 a B3 e D1 a D8, falsos positivos medidos, D9 aposentada, coberta no KV,
quadros e variantes ocultas. So dicionarios montados aqui: nenhum PSD."""
import copy

import pytest

from desdobra import contratos, laudo
from desdobra.laudo import efeitos_1260, quadros, regras

SHA = 'a' * 64


def camada(layer_id, kind='pixel', **extra):
    base = {'layer_id': layer_id, 'indice': layer_id, 'nome': 'camada %d' % layer_id, 'kind': kind, 'pai_id': None,
            'caminho_ids': [], 'visivel_propria': True, 'visivel_efetiva': True, 'opacidade': 255, 'preenchimento': 255,
            'blend': 'NORMAL', 'clipping': False, 'caixa': [0, 0, 10, 10], 'caixa_tinta': [0, 0, 10, 10],
            'mascara': {'raster': False, 'vetorial': False}, 'efeitos': [], 'ajuste': None, 'smart_object': None,
            'texto': None, 'medidas_regras': {}, 'alertas': [],
            'pixels': {'erro': None, 'fracao_coberta': 0.0, 'fracao_canvas': 0.01}}
    base.update(extra)
    return base


def estrutura(camadas, largura=100, altura=50, pranchetas=()):
    return {'esquema': 'estrutura/1',
            'leitor': {'motor': '0.1.0', 'psd_tools': '1.26.0', 'python': '3.14.2', 'pacotes': {'aggdraw': True, 'scipy': True}},
            'origem': {'nome': 'kv.psd', 'sha256': SHA, 'bytes': 10, 'profundidade': 0, 'recorte': None, 'pai': None},
            'documento': {'largura': largura, 'altura': altura, 'formato': 'PSD', 'versao': 1, 'modo': 'RGB', 'bits': 8,
                          'canais': 3, 'icc': {'presente': False}, 'gravado_por': {'writer': 'Programa', 'file_version': 1},
                          'tem_previa': True, 'pranchetas': list(pranchetas), 'layer_comps': [], 'n_camadas': len(camadas)},
            'indice_smart': [], 'camadas': camadas, 'prova_pixel': {'feita': False, 'motivo': 'sem_merged'},
            'recursos': {'tempo_s': 0.1, 'orcamento_bytes': 1}, 'erros': [], 'arquivos': {}}


def montar(est, **kw):
    out = laudo.montar(est, origem={'arquivo': 'kv.psd', 'sha256': SHA, 'bytes': 10},
                       recursos={'tempo_s': 0.1, 'pico_bytes': None, 'orcamento_bytes': 1, 'filhos': 1}, **kw)
    contratos.validar(out, 'laudo/1')
    return out


def run(texto, fonte='Fonte-A', **extra):
    r = {'inicio': 0, 'fim': len(texto), 'texto': texto, 'fonte_ps': fonte, 'tem_caractere_visivel': True,
         'tem_tinta': any(not c.isspace() for c in texto), 'faux_bold': False, 'faux_italic': False,
         'baseline_shift': 0.0, 'escala_h': 1.0, 'escala_v': 1.0}
    r.update(extra)
    return r


def texto(*runs):
    return {'conteudo': ''.join(r['texto'] for r in runs), 'runs': list(runs), 'warp': None,
            'fontes_ps': sorted({r['fonte_ps'] for r in runs})}


def regras_de(reg, pacotes=None, fontes=None):
    return [m['regra'] for m in regras.avaliar(reg, pacotes or {'aggdraw': True, 'scipy': True}, fontes)]


# ------------------------------------------------------------------ D9 aposentada
def test_d9_nao_existe_e_o_esquema_recusa():
    assert 'D9' not in regras.REGRAS
    out = montar(estrutura([camada(1)]))
    assert set(out['regras']) == {'B1', 'B2', 'B3'} | {'D%d' % i for i in range(1, 9)}
    ruim = copy.deepcopy(out)
    ruim['camadas'][0]['motivos'] = [{'regra': 'D9', 'descricao': 'x', 'fonte': {'arquivo': 'x'}}]
    with pytest.raises(contratos.ErroContrato):
        contratos.validar(ruim, 'laudo/1')


def test_grupo_pass_through_com_mascara_nao_degrada():
    g = camada(1, 'group', blend='PASS_THROUGH', opacidade=128, mascara={'raster': True, 'raster_com_dados': True})
    filho = camada(2, pai_id=1, caminho_ids=[1])
    assert regras_de(g) == [] and regras_de(filho) == []


# ------------------------------------------------------------------ falsos positivos: mede antes de degradar
def test_traco_vetorial_de_largura_zero_nao_degrada():
    sem_agg = {'aggdraw': False, 'scipy': True}
    assert regras_de(camada(1, 'shape', medidas_regras={'traco_forma': {'ativo': True, 'largura': 0.0}}), sem_agg) == []
    assert regras_de(camada(1, 'shape', medidas_regras={'traco_forma': {'ativo': True, 'largura': 3.0}}), sem_agg) == ['D5']
    assert regras_de(camada(1, 'shape', medidas_regras={'traco_forma': {'ativo': True, 'largura': 3.0}})) == []


def test_malha_de_deformacao_identidade_nao_degrada():
    def so(desvio):
        return {'unique_id': 'u', 'embutido': True, 'tipo': 'embutido',
                'medidas': {'warp_estilo': 'warpCustom', 'malha_custom': True, 'malha_desvio_max_px': desvio,
                            'nao_afim_diferenca_max_px': 0.0, 'residuo_paralelogramo_px': 0.0}}
    assert regras_de(camada(1, 'smartobject', smart_object=so(2.3e-13))) == []
    assert regras_de(camada(1, 'smartobject', smart_object=so(12.5))) == ['D6']
    assert regras_de(camada(1, 'smartobject', smart_object=so(None))) == ['D6']


def test_quadrilatero_e_nao_afim_usam_tolerancias_do_registro():
    so = {'unique_id': 'u', 'embutido': True, 'tipo': 'embutido',
          'medidas': {'warp_estilo': 'warpNone', 'malha_custom': False, 'malha_desvio_max_px': None,
                      'nao_afim_diferenca_max_px': 0.001, 'residuo_paralelogramo_px': 0.001}}
    assert regras_de(camada(1, 'smartobject', smart_object=so)) == []
    so['medidas']['residuo_paralelogramo_px'] = 5.0
    mot = regras.avaliar(camada(1, 'smartobject', smart_object=so), {'aggdraw': True})
    assert [m['regra'] for m in mot] == ['D6']
    assert mot[0]['limite']['limite_id'] == 'laudo.tolerancia_paralelogramo_px'


def test_warp_de_texto_sem_curvatura_nao_degrada():
    t = texto(run('Oferta'))
    t['warp'] = {'estilo': 'warpArc', 'valor': 0.0, 'perspectiva': 0.0, 'perspectiva_outra': 0.0}
    assert regras_de(camada(1, 'type', texto=t)) == []
    t['warp']['valor'] = 30.0
    assert regras_de(camada(1, 'type', texto=t)) == ['D6']


def test_fonte_ausente_so_em_espaco_nao_bloqueia():
    t = texto(run('Oferta', 'Fonte-A'), run(' ', 'Fonte-Espaco'))
    reg = camada(1, 'type', texto=t)
    assert regras_de(reg, fontes={'Fonte-Espaco': 'ausente', 'Fonte-A': 'presente'}) == []
    assert regras_de(reg, fontes={'Fonte-A': 'ausente'}) == ['B3']
    # no M1 nao ha conferencia de faces instaladas: a B3 nao dispara e a fonte fica nao_conferida
    assert regras_de(reg) == []
    out = montar(estrutura([reg]))
    usadas = {f['fonte_ps']: f for f in out['fontes_usadas']}
    assert usadas['Fonte-Espaco']['so_em_espaco'] is True and usadas['Fonte-A']['so_em_espaco'] is False
    assert {f['situacao'] for f in out['fontes_usadas']} == {'nao_conferida'}


def test_recurso_de_texto_so_conta_em_trecho_com_tinta():
    assert regras_de(camada(1, 'type', texto=texto(run('Oferta'), run(' ', faux_bold=True)))) == []
    assert regras_de(camada(1, 'type', texto=texto(run('Oferta', faux_bold=True)))) == ['D7']
    assert regras_de(camada(1, 'type', texto=texto(run('Oferta', escala_v=1.0000001)))) == []
    assert regras_de(camada(1, 'type', texto=texto(run('Oferta', escala_v=0.9)))) == ['D7']


def test_efeitos_pela_lista_da_1260():
    def ef(tipo, **med):
        desenhado, falta = efeitos_1260.efeito_desenhado(tipo, {'aggdraw': True, 'scipy': True})
        return {'tipo': tipo, 'ativo': True, 'desenhado_pelo_render': desenhado, 'requer_pacote_ausente': falta,
                'medidas': med}
    assert regras_de(camada(1, efeitos=[ef('DropShadow', size=5.0, opacity=75.0)])) == ['D1']
    assert regras_de(camada(1, efeitos=[ef('DropShadow', size=5.0, opacity=0.0)])) == []
    assert regras_de(camada(1, efeitos=[ef('ColorOverlay'), ef('Stroke', size=3.0), ef('GradientOverlay')])) == []
    desenhado, falta = efeitos_1260.efeito_desenhado('GradientOverlay', {'scipy': False})
    assert not desenhado and falta == 'scipy'


def test_ajustes_pela_lista_da_1260():
    for kind, esperado in (('levels', []), ('curves', []), ('vibrance', ['D2']), ('gradientmap', ['D2'])):
        entra, motivo = efeitos_1260.ajuste_no_composto(kind, 'RGB', {'scipy': True})
        reg = camada(1, kind, ajuste={'tipo': kind, 'entra_no_composto': entra, 'motivo': motivo})
        assert regras_de(reg) == esperado, kind


def test_b1_linkado_e_b2_erro_de_pixel_e_d8():
    so = {'unique_id': 'u', 'embutido': False, 'tipo': 'linkado', 'linkado': {'nome': 'a.png', 'tamanho': 3, 'data': None}}
    assert regras_de(camada(1, 'smartobject', smart_object=so)) == ['B1']
    assert regras_de(camada(1, pixels={'erro': 'ValueError'})) == ['B2']
    assert regras_de(camada(1, visivel_efetiva=False)) == ['D8']
    assert regras.situacao(regras.avaliar(camada(1, 'smartobject', smart_object=so), {})) == 'bloqueante'


def test_cada_motivo_tem_regra_medida_e_fonte():
    reg = camada(1, 'type', texto=texto(run('Oferta', faux_bold=True, escala_h=1.2)), visivel_efetiva=False)
    out = montar(estrutura([reg]))
    c = out['camadas'][0]
    assert c['situacao'] == 'degradada'
    for m in c['motivos']:
        assert m['fonte']['arquivo'].startswith('pesquisa/') and m['descricao']
    d7 = [m for m in c['motivos'] if m['regra'] == 'D7'][0]
    assert d7['medida']['escala_h'] == 1.2 and d7['limite']['limite_id'] == 'laudo.tolerancia_escala_texto'


# ------------------------------------------------------------------ coberta no KV (decisao 10)
def test_coberta_no_kv_da_a_funcao_so_como_sugestao_citada():
    fundo = camada(1, pixels={'erro': None, 'fracao_coberta': 1.0, 'fracao_canvas': 1.0})
    solto = camada(2, pixels={'erro': None, 'fracao_coberta': 1.0, 'fracao_canvas': 0.02})
    meio = camada(3, pixels={'erro': None, 'fracao_coberta': 0.5, 'fracao_canvas': 0.3})
    oculta = camada(4, visivel_propria=False, visivel_efetiva=False,
                    pixels={'erro': None, 'fracao_coberta': None, 'fracao_canvas': 0.3})
    out = montar(estrutura([fundo, solto, meio, oculta]))
    cb = {c['identidade']['layer_id']: c['geometria']['coberta_no_kv'] for c in out['camadas']}
    assert cb[1]['coberta'] and cb[1]['ocupa_canvas']
    assert cb[1]['sugestao_da_regra'] == {'funcao': 'estrutura', 'regra': 'decisao-10',
                                          'fonte': {'arquivo': 'decisoes-v1.md', 'secao': '29/10, respostas ao teste do corpus, 10'}}
    assert 'funcao_sugerida_pela_regra' not in cb[1] and 'fonte_da_sugestao' not in cb[1]
    assert cb[2]['coberta'] and not cb[2]['ocupa_canvas'] and cb[2]['sugestao_da_regra']['funcao'] == 'fora_da_peca'
    assert not cb[3]['coberta'] and cb[3]['sugestao_da_regra'] is None
    assert cb[4] is None
    lim = {x['limite_id']: x for x in cb[1]['limites']}
    assert lim['coberta_no_kv.ocupa_canvas_fracao']['situacao'] == 'a_calibrar'
    assert lim['coberta_no_kv.ocupa_canvas_fracao']['efeito'] != 'reprova'
    assert out['resumo']['n_cobertas_no_kv'] == 2
    # a funcao nunca vira valor: o laudo nao tem campo de funcao na camada
    assert all('funcao' not in c for c in out['camadas'])


# ------------------------------------------------------------------ quadros e variantes ocultas
def test_quadros_por_grupos_de_topo_e_variantes_ocultas():
    cams = []
    for i, vis in enumerate((True, False, False)):
        g = 10 * (i + 1)
        cams.append(camada(g, 'group', visivel_propria=vis, visivel_efetiva=vis, caixa=[0, 0, 100, 50]))
        cams.append(camada(g + 1, pai_id=g, caminho_ids=[g], caixa=[0, 0, 100, 50], visivel_efetiva=vis))
    cams.append(camada(40, 'group', visivel_propria=False, visivel_efetiva=False, caixa=[0, 0, 0, 0]))
    cams.append(camada(41, pai_id=40, caminho_ids=[40], caixa=[5, 5, 20, 20], visivel_efetiva=False))
    est = estrutura(cams)
    q = quadros.detectar(est)
    assert [x['layer_id'] for x in q] == [10, 20, 30] and [x['visivel_ao_salvar'] for x in q] == [True, False, False]
    assert q[0]['regra'] == 'grupos_de_topo' and q[0]['limite']['limite_id'] == 'quadros.fracao_canvas_grupo_topo'
    out = montar(est)
    assert out['resumo']['n_quadros'] == 3
    assert [v['layer_id'] for v in out['documento']['variantes_ocultas']] == [40]
    assert {c['identidade']['layer_id']: c['quadro'] for c in out['camadas']}[21] == 'q2'


def test_tela_com_fundo_em_72_por_cento_do_canvas_vira_quadro_e_40_por_cento_nao():
    # caso do corpus: a terceira tela de um DOOH vertical tem o maior fundo em 0,72 do canvas (decisoes-v1.md, 26)
    cams = []
    for i, (vis, x1) in enumerate(((True, 100), (False, 100), (False, 72), (False, 40))):
        g = 10 * (i + 1)
        cams.append(camada(g, 'group', visivel_propria=vis, visivel_efetiva=vis, caixa=[0, 0, x1, 50]))
        cams.append(camada(g + 1, pai_id=g, caminho_ids=[g], caixa=[0, 0, x1, 50], visivel_efetiva=vis))
    q = quadros.detectar(estrutura(cams))
    assert [x['layer_id'] for x in q] == [10, 20, 30]


def test_pranchetas_viram_quadros():
    p = [{'layer_id': 7, 'nome': 'p1', 'caixa': [0, 0, 50, 50], 'visivel_propria': True},
         {'layer_id': 8, 'nome': 'p2', 'caixa': [60, 0, 110, 50], 'visivel_propria': True}]
    est = estrutura([camada(7, 'artboard'), camada(8, 'artboard'), camada(9, pai_id=8, caminho_ids=[8])], 110, 50, p)
    out = montar(est)
    assert [(x['regra'], x['layer_id']) for x in out['documento']['quadros']] == [('pranchetas', 7), ('pranchetas', 8)]
    assert {c['identidade']['layer_id']: c['quadro'] for c in out['camadas']}[9] == 'q2'


# ------------------------------------------------------------------ laudo de arquivo recusado
def test_laudo_de_arquivo_recusado_e_valido_e_sem_camadas():
    rec = [{'tipo': 'cabecalho', 'etapa': 'cabecalho', 'motivo': 'não cabe', 'layer_id': None, 'medidas': {'largura': 1}}]
    out = montar(None, recusa=rec)
    assert out['camadas'] == [] and out['recusas'] == rec and out['prova_pixel']['feita'] is False
    assert out['prova_pixel']['limiar']['limite_id'] == 'prova_pixel.limiar_diferenca'
    assert out['prova_pixel']['limiar']['valor'] == 24 and out['prova_pixel']['limiar']['situacao'] == 'medido'


def test_identidade_e_o_par_sha256_layer_id():
    out = montar(estrutura([camada(5), camada(6)]))
    assert [c['identidade'] for c in out['camadas']] == [{'arquivo_sha256': SHA, 'layer_id': 5},
                                                          {'arquivo_sha256': SHA, 'layer_id': 6}]
    assert out['origem']['gravado_por'] == {'programa': 'Programa', 'versao': '1'}
    assert out['efeitos_suportados'] == efeitos_1260.descricao()


def test_warp_de_smart_object_sem_curvatura_nao_degrada():
    def so(valores):
        return {'unique_id': 'u', 'embutido': True, 'tipo': 'embutido',
                'medidas': {'warp_estilo': 'warpArc', 'warp_valores': valores, 'malha_custom': False}}
    assert regras_de(camada(1, 'smartobject', smart_object=so([0.0, 0.0, 0.0]))) == []
    assert regras_de(camada(1, 'smartobject', smart_object=so([25.0, 0.0, 0.0]))) == ['D6']
    assert regras_de(camada(1, 'smartobject', smart_object=so(None))) == ['D6']


def test_composicao_que_estoura_o_orcamento_vira_bloqueio_tipado():
    est = estrutura([camada(1)])
    est['prova_pixel'] = {'feita': False, 'motivo': 'orcamento'}
    out = montar(est)
    rec = [r for r in out['recusas'] if r['etapa'] == 'composicao']
    assert len(rec) == 1 and rec[0]['tipo'] == 'memoria' and rec[0]['layer_id'] is None
    assert out['camadas'] and out['prova_pixel']['motivo'] == 'orcamento'
    est['prova_pixel'] = {'feita': False, 'motivo': 'sem_merged'}
    assert not montar(est)['recusas']


def test_embutido_sem_composto_real_e_com_texto_vira_alerta():
    so = {'tipo': 'embedded', 'embutido': True, 'unique_id': 'u1', 'tipo_detectado': 'psb', 'sha256': 'cd' * 32}
    reg = camada(1, 'smartobject', smart_object=so)
    interno = estrutura([camada(2, 'type', texto=texto(run('Oi')))])
    interno['origem']['profundidade'] = 1
    for tem_previa, uniforme, esperado in ((False, None, 'composto_ausente_com_texto'),
                                           (True, True, 'composto_uniforme_com_texto'), (True, False, None)):
        interno['documento']['tem_previa'] = tem_previa
        interno['documento']['previa_uniforme'] = uniforme
        out = montar(estrutura([reg]), aninhadas={'cd' * 32: {'estrutura': interno, 'recusa': None, 'pasta': 'bruto/x'}})
        codigos = [a['codigo'] for a in out['camadas'][0]['alertas']]
        assert codigos == ([esperado] if esperado else []), codigos


# ------------------------------------------------------------------ ramos das regras que faltavam
def test_d3_dissolve_degrada():
    assert regras_de(camada(1, blend='DISSOLVE')) == ['D3']


def test_d4_feather_raster_e_vetorial():
    assert regras_de(camada(1, mascara={'raster': True, 'vetorial': False, 'feather_usuario': 2.0})) == ['D4']
    assert regras_de(camada(1, mascara={'raster': True, 'vetorial': False, 'desativada': True,
                                        'feather_usuario': 2.0})) == []
    assert regras_de(camada(1, mascara={'raster': False, 'vetorial': True, 'feather_vetorial': 1.5})) == ['D4']
    assert regras_de(camada(1, mascara={'raster': False, 'vetorial': True, 'vetorial_desativada': True,
                                        'feather_vetorial': 1.5})) == []


def test_d7_faux_italico_e_linha_de_base_so_em_trecho_com_tinta():
    mot = regras.avaliar(camada(1, 'type', texto=texto(run('Oi', faux_italic=True))), {'aggdraw': True})
    assert [m['regra'] for m in mot] == ['D7'] and mot[0]['medida'] == {'faux_italico': True}
    mot = regras.avaliar(camada(2, 'type', texto=texto(run('Oi', baseline_shift=3.0))), {'aggdraw': True})
    assert [m['regra'] for m in mot] == ['D7'] and mot[0]['medida'] == {'deslocamento_linha_base': 3.0}
    assert regras_de(camada(3, 'type', texto=texto(run('  ', baseline_shift=3.0, faux_italic=True)))) == []


def test_stroke_ativo_de_tamanho_zero_nao_degrada():
    def traco(size):
        return {'tipo': 'Stroke', 'ativo': True, 'desenhado_pelo_render': False, 'medidas': {'size': size}}
    assert regras_de(camada(1, efeitos=[traco(0)])) == []
    assert regras_de(camada(1, efeitos=[traco(3)])) == ['D1']


def test_passada_de_pixels_acima_do_orcamento_e_bloqueante():
    reg = camada(1, pixels={'erro': None, 'pulado': 'orcamento'})
    mot = regras.avaliar(reg, {'aggdraw': True})
    assert [m['regra'] for m in mot] == ['B2'] and mot[0]['medida'] == {'pulado': 'orcamento'}
    assert montar(estrutura([reg]))['camadas'][0]['situacao'] == 'bloqueante'


def test_coberta_compara_contagens_inteiras_sem_arredondar():
    # 1 pixel visivel descoberto em 3 milhoes: a fracao arredondada a 6 casas daria 1,0
    quase = {'erro': None, 'fracao_coberta': 1.0, 'fracao_canvas': 1.0, 'px_visiveis': 3_000_000,
             'px_cobertos': 2_999_999, 'px_area_ref': 3_000_000}
    cb = montar(estrutura([camada(1, pixels=quase)]))['camadas'][0]['geometria']['coberta_no_kv']
    assert not cb['coberta'] and cb['sugestao_da_regra'] is None
    # coberta por inteiro, mas falta 1 pixel do canvas: nao ocupa o canvas, e a sugestao e fora da peca
    falta_um = dict(quase, px_visiveis=2_073_599, px_cobertos=2_073_599, px_area_ref=2_073_600)
    cb = montar(estrutura([camada(1, pixels=falta_um)]))['camadas'][0]['geometria']['coberta_no_kv']
    assert cb['coberta'] and not cb['ocupa_canvas'] and cb['sugestao_da_regra']['funcao'] == 'fora_da_peca'


def test_texto_com_tinta_sem_conferencia_de_fonte_tem_alerta():
    com_tinta = camada(1, 'type', texto=texto(run('Oi', fonte='Fonte-X')))
    so_espaco = camada(2, 'type', texto=texto(run('   ', fonte='Fonte-Y')))
    out = montar(estrutura([com_tinta, so_espaco]))
    alertas = {c['identidade']['layer_id']: [a['codigo'] for a in c['alertas']] for c in out['camadas']}
    assert alertas == {1: ['fonte_nao_conferida'], 2: []}
    assert out['camadas'][0]['situacao'] == 'lida' and out['resumo']['n_fonte_nao_conferida'] == 1
    assert montar(estrutura([com_tinta]), fontes_status={'Fonte-X': 'presente'})['camadas'][0]['alertas'] == []


def test_composicao_estourada_chega_ao_envelope_como_ok_com_bloqueio():
    from desdobra import leitor
    from desdobra.resultado import Codigo
    from desdobra.sugestao import envelope
    est = estrutura([camada(1)])
    est['prova_pixel'] = {'feita': False, 'motivo': 'orcamento'}
    out = montar(est)
    assert out['resumo']['bloqueios_documento'] == 1
    r = leitor.resultado_de(Codigo.OK, out, {'recursos': {'tempo_s': 1.0, 'pico_bytes': None, 'filhos': 1}})
    assert r.codigo == 0 and r.situacao == 'ok_com_bloqueio' and r.o_que_fazer == leitor.O_QUE_FAZER_COMPOSICAO
    assert r.contagens['bloqueios_documento'] == 1 and r.contagens['bloqueios_composicao'] == 1
    env = envelope.montar(r, 'c')
    contratos.validar(env, 'envelope/1')
    assert env['situacao'] == 'ok_com_bloqueio'


def test_parada_por_limite_a_calibrar_pede_confirmacao_do_da():
    from desdobra import leitor
    from desdobra.resultado import Codigo
    rec = leitor.anotar_limites({'tipo': 'memoria', 'etapa': 'leitura', 'motivo': 'x', 'layer_id': None})
    assert rec['decisao'] == 'pede_confirmacao_do_da'
    assert {x['limite_id'] for x in rec['limites']} == set(leitor.LIMITES_DO_ORCAMENTO)
    out = montar(None, recusa=[rec])
    r = leitor.resultado_de(Codigo.ORCAMENTO, out, {'recursos': {'tempo_s': 1.0, 'pico_bytes': None, 'filhos': 1}})
    assert r.codigo == int(Codigo.ORCAMENTO) and r.situacao == 'bloqueado' and r.o_que_fazer == leitor.O_QUE_FAZER_LIMITE
    assert r.contagens['recusas_pedem_confirmacao'] == 1
    tempo = leitor.anotar_limites({'tipo': 'tempo', 'etapa': 'leitura', 'motivo': 'x'}, tempo_confirmado=True)
    assert tempo['decisao'] == 'teto_confirmado_pelo_da'
    assert 'decisao' not in leitor.anotar_limites({'tipo': 'leitura', 'etapa': 'abrir', 'motivo': 'x'})


def test_quadros_pedem_um_so_visivel_e_o_minimo_de_candidatos():
    def grupo(g, vis):
        return [camada(g, 'group', visivel_propria=vis, visivel_efetiva=vis, caixa=[0, 0, 100, 50]),
                camada(g + 1, pai_id=g, caminho_ids=[g], caixa=[0, 0, 100, 50], visivel_efetiva=vis)]
    assert quadros.detectar(estrutura(grupo(10, True))) == []
    assert quadros.detectar(estrutura(grupo(10, True) + grupo(20, True))) == []
    assert len(quadros.detectar(estrutura(grupo(10, True) + grupo(20, False)))) == 2


def test_smart_object_alem_da_profundidade_fica_nao_aberto_com_alerta():
    so = {'tipo': 'embedded', 'embutido': True, 'unique_id': 'u1', 'tipo_detectado': 'psd', 'sha256': 'ef' * 32}
    out = montar(estrutura([camada(1, 'smartobject', smart_object=so)]),
                 aninhadas={'ef' * 32: {'estrutura': None, 'recusa': None, 'motivo': 'profundidade máxima'}})
    c = out['camadas'][0]
    assert c['smart_object']['abertura'] == {'situacao': 'nao_aberto', 'motivo': 'profundidade máxima'}
    assert [a['codigo'] for a in c['alertas']] == ['smart_object_nao_aberto']


@pytest.mark.parametrize('parte, todo, limite, esperado', [
    (7, 100, 0.07, True), (14, 100, 0.14, True), (28, 100, 0.28, True), (1_020_000, 3_000_000, 0.34, True),
    (57, 100, 0.57, True), (56, 100, 0.57, False), (6, 100, 0.07, False), (3, 3, 1.0, True), (2, 3, 1, False),
])
def test_contagem_inteira_no_limiar_compara_sem_float(parte, todo, limite, esperado):
    # a contagem exatamente no limiar atinge o limiar: 0,07 x 100 em float da 7,000000000000001
    assert laudo._atinge(parte, todo, None, limite) is esperado
