# -*- coding: utf-8 -*-
"""Material sintetico dos testes do briefing e da derivacao (M5): laudos minimos montados a mao (so os campos que a
heranca e a derivacao leem), briefings de teste e folhas de spec em memoria. Nomes, caixas e funcoes inventados.
Este arquivo nao tem teste: so geradores."""
import copy

JOB = 'ab' * 16


def camada(lid, tipo, caixa, pais=(), quadro=None, visivel=True, coberta=None, corpo=None):
    texto = None
    if tipo == 'texto':
        texto = {'runs': [{'tem_tinta': True, 'corpo_efetivo': float(corpo or 20.0)}]}
    return {'identidade': {'arquivo_sha256': 'cd' * 32, 'layer_id': lid}, 'nome': 'camada-%d' % lid, 'tipo': tipo,
            'pai_id': pais[-1] if pais else None, 'caminho_ids': list(pais), 'quadro': quadro,
            'aparencia': {'visivel_efetiva': visivel}, 'geometria': {'caixa': list(caixa), 'caixa_tinta': list(caixa),
                                                                   'coberta_no_kv': coberta},
            'texto': texto, 'smart_object': None}


def laudo(largura=400, altura=200, camadas=None, quadros=None):
    """KV horizontal 400 x 200: fundo que sangra, grupo de titulo (texto e linha), apoio, logo no canto, legal
    embaixo, uma camada solta para virar fora da peca e uma oculta."""
    if camadas is None:
        camadas = [
            camada(1, 'pixel', [0, 0, 400, 200]),
            camada(10, 'grupo', [20, 20, 220, 80]),
            camada(11, 'texto', [20, 20, 220, 60], pais=(10,), corpo=40),
            camada(12, 'forma', [20, 70, 220, 80], pais=(10,)),
            camada(20, 'texto', [20, 100, 200, 120], corpo=16),
            camada(30, 'smart_embutido', [320, 140, 380, 180]),
            camada(40, 'texto', [20, 170, 300, 182], corpo=8),
            camada(50, 'pixel', [250, 20, 290, 60]),
            camada(60, 'pixel', [100, 100, 150, 150], visivel=False),
        ]
    return {'documento': {'largura': largura, 'altura': altura, 'quadros': quadros or []}, 'camadas': camadas}


def laudo_degenerado():
    """KV vertical 540 x 960 com dois elementos do canvas inteiro, uma faixa de imagem que sangra embaixo e uma grade
    de elementos alinhados: o caso em que o Cassowary chega ao otimo por caminhos diferentes (muita restricao
    redundante), como o KV vertical do corpus. Devolve (laudo, funcoes)."""
    camadas = [camada(1, 'pixel', [0, 0, 540, 960]), camada(2, 'pixel', [0, 0, 540, 960]),
               camada(3, 'pixel', [0, 700, 540, 960]), camada(4, 'pixel', [270, 300, 540, 960])]
    funcoes = {1: 'fundo', 2: 'fundo', 3: 'imagem', 4: 'sujeito'}
    lid = 10
    for linha in range(3):
        for col in range(3):
            camadas.append(camada(lid, 'texto' if col == 0 else 'pixel',
                                  [30 + 170 * col, 60 + 80 * linha, 150 + 170 * col, 100 + 80 * linha], corpo=24))
            funcoes[lid] = ('informacao_de_evento', 'grafismo', 'logo_de_parceiro')[col]
            lid += 1
    return laudo(540, 960, camadas), funcoes


def decisao(valor, origem='fixture_de_teste'):
    return {'valor': valor, 'situacao': 'confirmado', 'origem': {'tipo': origem, 'ref': 'teste'}}


def pendente():
    return {'valor': None, 'situacao': 'pendente', 'origem': {'tipo': 'da', 'ref': None}}


FUNCOES = {1: 'fundo', 10: 'titulo', 20: 'texto_de_apoio', 30: 'logo_principal', 40: 'texto_legal', 50: 'fora_da_peca'}
REGRAS = {'fundo': 'cover', 'titulo': 'raiz_area', 'texto_de_apoio': 'raiz_area', 'logo_principal': 'raiz_area',
          'texto_legal': 'constante', 'grafismo': 'contain', 'imagem': 'contain', 'sujeito': 'raiz_area',
          'cta': 'raiz_area', 'selo': 'raiz_area', 'informacao_de_evento': 'raiz_area', 'logo_de_parceiro': 'raiz_area'}
ANCORAS = {'fundo': ('centro', 'meio'), 'titulo': ('esquerda', 'topo'), 'texto_de_apoio': ('esquerda', 'meio'),
           'logo_principal': ('direita', 'base'), 'texto_legal': ('esquerda', 'base'), 'grafismo': ('centro', 'meio'),
           'imagem': ('centro', 'meio'), 'sujeito': ('centro', 'meio'), 'cta': ('esquerda', 'base'),
           'selo': ('direita', 'topo'), 'informacao_de_evento': ('esquerda', 'meio'),
           'logo_de_parceiro': ('direita', 'topo')}


def formato(ident, largura, altura, chave=None, **extra):
    """Formato do briefing. Sem chave, o formato e de teste sem folha (marcado sem_folha, como os de medicao)."""
    f = {'id': ident, 'chave': chave or 'teste|circuito|%dx%d' % (largura, altura), 'veiculador': 'teste',
         'circuito': 'circuito', 'largura': largura, 'altura': altura}
    if chave is None:
        f['sem_folha'] = True
    f.update(extra)
    return f


def briefing(funcoes=None, regras=None, ancoras=None, formatos=None, mestres=None, quadro=None, cobertas=(),
             indeterminado=None, familias=None, quebras_por_familia=None):
    funcoes = FUNCOES if funcoes is None else funcoes
    regras = REGRAS if regras is None else regras
    ancoras = ANCORAS if ancoras is None else ancoras
    b = {'esquema': 'briefing/1', 'job_id': JOB,
         'cabecalho': {'laudo_sha256': '1' * 64, 'specs_sha256': None, 'ds_sha256': None, 'conferencia_sha256': None,
                       'origem': 'fixture_de_teste', 'meio': 'importar_teste',
                       'por': {'usuario': 'teste', 'maquina': 'teste'}, 'quando': '2026-11-02T10:00:00-03:00'},
         'quadro': decisao(quadro) if quadro else {'valor': None, 'situacao': 'confirmado',
                                                   'origem': {'tipo': 'fixture_de_teste', 'ref': None}},
         'funcoes': [{'layer_id': k, 'funcao': decisao(v),
                      'observacao': 'observacao inventada' if v == 'indeterminado' else None}
                     for k, v in sorted(funcoes.items())],
         'cobertas': [{'layer_id': k, 'decisao': decisao(v)} for k, v in cobertas],
         'regras_escala': [{'funcao': f, 'regra': decisao(r)} for f, r in sorted(regras.items())],
         'regras_indeterminado': [{'layer_id': k, 'regra': decisao(v)} for k, v in sorted((indeterminado or {}).items())],
         'ancoras': [{'funcao': f, 'x': decisao(x), 'y': decisao(y)} for f, (x, y) in sorted(ancoras.items())],
         'formatos': formatos if formatos is not None else [formato('mesmo', 800, 400), formato('perto', 480, 300),
                                                            formato('vertical', 300, 600)],
         'mestres': mestres if mestres is not None else [{'id': 'kv', 'tipo': 'kv'}],
         'modo_dados': decisao('c')}
    if familias:
        b['familias'] = familias
    if quebras_por_familia:
        b['quebras_por_familia'] = quebras_por_familia
    return b


def spec(chave, campos):
    """Formato de folha em memoria, com cada campo na forma do rascunho (valor, situacao, fonte)."""
    return {'chave': chave, 'campos': {k: {'id': 'f1-e01/%s' % k, 'valor': v, 'situacao': 'rascunho',
                                           'fonte': {'folha': 'f1', 'trecho': 'p01-t%03d' % n, 'pagina': 1}}
                                       for n, (k, v) in enumerate(sorted(campos.items()), 1)}}


def copia(x):
    return copy.deepcopy(x)


def psd_derivacao(destino):
    """PSD 320 x 160 para a derivacao com render: fundo creme do canvas inteiro, grupo de titulo com um texto de duas
    cores e uma linha, logo verde no canto, texto de apoio e um quadrado vermelho solto que vira fora da peca."""
    from PIL import Image
    from psd_tools import PSDImage

    import test_fontes_apoio as fap
    import test_render_apoio as rap
    p = PSDImage.new('RGB', (320, 160), color=(255, 255, 255))
    p.create_pixel_layer(Image.new('RGBA', (320, 160), (240, 236, 220, 255)), name='fundo-sintetico')
    g = p.create_group(name='grupo-sintetico')
    t1 = g.create_pixel_layer(Image.new('RGBA', (200, 30), (20, 20, 20, 255)), name='texto-cores', top=20, left=10)
    rap._virar_texto(t1, [('ABC', 28.0, rap.COR_1), ('abc', 28.0, rap.COR_2)], 12.0, 44.0, fap.largura('ABCabc', 28.0))
    g.create_pixel_layer(Image.new('RGBA', (100, 4), (30, 30, 120, 255)), name='linha-sintetica', top=56, left=12)
    p.create_pixel_layer(Image.new('RGBA', (40, 40), (0, 120, 60, 255)), name='quadrado-sintetico', top=100, left=260)
    t2 = p.create_pixel_layer(Image.new('RGBA', (200, 30), (20, 20, 20, 255)), name='texto-apoio', top=110, left=10)
    rap._virar_texto(t2, [('AB ab', 20.0, rap.COR_1)], 20.0, 130.0, fap.largura('AB ab', 20.0))
    p.create_pixel_layer(Image.new('RGBA', (20, 20), (220, 0, 0, 255)), name='solto-sintetico', top=70, left=200)
    return rap._salvar(p, destino)


def briefing_do_job(laudo, formatos):
    """Briefing de teste para o PSD de psd_derivacao, montado pelos ids do laudo (os que o psd-tools gravou)."""
    ids = {c['nome']: c['identidade']['layer_id'] for c in laudo['camadas']}
    funcoes = {ids['fundo-sintetico']: 'fundo', ids['grupo-sintetico']: 'titulo',
               ids['quadrado-sintetico']: 'logo_principal', ids['texto-apoio']: 'texto_de_apoio',
               ids['solto-sintetico']: 'fora_da_peca'}
    b = briefing(funcoes=funcoes, formatos=formatos)
    b.pop('cabecalho')
    b.pop('job_id')
    return b, ids
