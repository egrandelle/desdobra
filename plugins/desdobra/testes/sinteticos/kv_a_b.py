# -*- coding: utf-8 -*-
"""Os KVs A e B sinteticos do roteiro dos seis formatos (M7b, D6), gerados na hora numa pasta temporaria.

A mesma estrutura de camadas dos dois KVs do Duda, sem nada deles: fundo, titulo (texto), linha embaixo do titulo,
texto de apoio, dois icones, a assinatura e o packshot em tres camadas (garrafa, copo e lata) na frente de um circulo
de fundo. Nomes, textos, cores e caixas sao inventados aqui; os textos usam so os glifos da fonte de autoteste do
motor (H, O, A, V, X e o espaco).
  - KV A: o bloco de texto em cima a esquerda, o packshot inteiro a direita e a assinatura no canto de baixo a direita;
  - KV B: o packshot maior, apoiado na base, com o circulo sangrando na base; a assinatura embaixo a esquerda.
Os tres formatos de cada KV sao os do criterio (2048x720, 1008x432 e 800x600), cada um numa familia.

Geradores:
  psd(destino, kv, ps)        o PSD do KV ('a' ou 'b'), com os textos na fonte ps
  criar_job(base, kv)         o job do KV com o laudo e o briefing de teste (funcoes, regras e os tres formatos)
  passo_2(funcoes)            o passo 2 e o Design system como o DA os deixa no rascunho
"""
import json
from pathlib import Path

LARGURA, ALTURA = 400, 200
# os seis formatos do criterio: o mesmo trio nos dois KVs (os ids nao aparecem como identificador na tela)
FORMATOS = [('p2048', 2048, 720), ('p1008', 1008, 432), ('p800', 800, 600)]
TITULO = 'HOAX'
APOIO = 'VOX AH HOAX'  # uma linha no KV; o DA quebra em duas no 1008x432 (os espacos nas posicoes 3 e 6)
CORPO_TITULO, CORPO_APOIO = 28.0, 12.0
# o papel de cada camada e o nome dela no PSD
NOMES = {'fundo': 'fundo-sintetico', 'titulo': 'titulo-sintetico', 'linha': 'linha-sintetica',
         'apoio': 'apoio-sintetico', 'icone1': 'icone-um-sintetico', 'icone2': 'icone-dois-sintetico',
         'assinatura': 'assinatura-sintetica', 'circulo': 'circulo-sintetico', 'garrafa': 'garrafa-sintetica',
         'copo': 'copo-sintetico', 'lata': 'lata-sintetica'}
FUNCOES = {'fundo': 'fundo', 'titulo': 'titulo', 'linha': 'grafismo', 'apoio': 'texto_de_apoio',
           'icone1': 'icone_de_cta', 'icone2': 'icone_de_cta', 'assinatura': 'logo_principal', 'circulo': 'grafismo',
           'garrafa': 'sujeito', 'copo': 'sujeito', 'lata': 'sujeito'}
PACKSHOT = ('garrafa', 'copo', 'lata', 'circulo')
PRODUTOS = ('garrafa', 'copo', 'lata')
BLOCO = ('titulo', 'linha', 'apoio', 'icone1', 'icone2')
# a regra e a ancora de cada funcao usada (o Design system do passo 2)
USADAS = {'fundo': ('cover', 'centro', 'meio'), 'titulo': ('raiz_area', 'esquerda', 'topo'),
          'texto_de_apoio': ('raiz_area', 'esquerda', 'meio'), 'logo_principal': ('raiz_area', 'direita', 'base'),
          'grafismo': ('contain', 'centro', 'meio'), 'icone_de_cta': ('raiz_area', 'esquerda', 'meio'),
          'sujeito': ('raiz_area', 'centro', 'meio')}
# as caixas de cada KV [x0, y0, x1, y1] no PSD 400 x 200; o titulo e o apoio sao a camada de pixels que vira texto.
# No KV A, o topo, o meio e a base dos produtos ficam longe das linhas do bloco de texto (mais que a tolerancia da
# intencao de alinhamento, decisoes-v1.md, 168, somada ao passo do bloco alinhado no quadro): assim o bloco que o DA
# alinha nao puxa os produtos para as linhas dele. Com o apoio e a lata no mesmo topo, como no primeiro desenho, os
# produtos andavam cada um uma conta e a base do packshot se desfazia (relatorio do D6). O apoio fica com folga para
# os icones: quebrado em duas linhas, ele cresce sem encostar neles.
CAIXAS = {
    'a': {'titulo': [24, 40, 108, 72], 'linha': [26, 78, 106, 82], 'apoio': [24, 96, 118, 112],
          'icone1': [26, 136, 46, 156], 'icone2': [54, 136, 74, 156], 'assinatura': [330, 170, 380, 190],
          'circulo': [246, 10, 374, 138], 'garrafa': [270, 4, 300, 130], 'copo': [306, 6, 330, 130],
          'lata': [336, 8, 360, 130]},
    'b': {'titulo': [20, 30, 104, 62], 'linha': [22, 70, 102, 74], 'apoio': [20, 82, 114, 98],
          'icone1': [22, 112, 42, 132], 'icone2': [50, 112, 70, 132], 'assinatura': [22, 168, 72, 188],
          'circulo': [250, 70, 380, 200], 'garrafa': [268, 80, 298, 200], 'copo': [306, 136, 332, 200],
          'lata': [340, 124, 366, 200]},
}
CORES = {'fundo': (236, 232, 222, 255), 'linha': (30, 30, 120, 255), 'icone1': (0, 120, 60, 255),
         'icone2': (0, 90, 120, 255), 'assinatura': (40, 40, 120, 255), 'circulo': (200, 90, 40, 255),
         'garrafa': (30, 70, 40, 255), 'copo': (60, 60, 90, 255), 'lata': (150, 20, 30, 255)}


def psd(destino, kv, ps):
    """O PSD 400 x 200 do KV kv ('a' ou 'b'): uma camada por papel, na ordem do fundo para a frente; o titulo e o apoio
    sao camadas de texto na fonte ps."""
    from PIL import Image, ImageDraw
    from psd_tools import PSDImage

    import test_fontes_apoio as fap
    import test_render_apoio as rap
    import test_tela_palco as tp
    c = CAIXAS[kv]
    p = PSDImage.new('RGB', (LARGURA, ALTURA), color=(255, 255, 255))
    p.create_pixel_layer(Image.new('RGBA', (LARGURA, ALTURA), CORES['fundo']), name=NOMES['fundo'])

    def caixa(papel):
        x0, y0, x1, y1 = c[papel]
        return (x1 - x0, y1 - y0), x0, y0

    for papel, texto, corpo in (('titulo', TITULO, CORPO_TITULO), ('apoio', APOIO, CORPO_APOIO)):
        tam, x0, y0 = caixa(papel)
        t = p.create_pixel_layer(Image.new('RGBA', tam, (20, 20, 20, 255)), name=NOMES[papel], top=y0, left=x0)
        fap._virar_texto(t, [(texto, 0, corpo, 0)], [ps], fap.largura(texto, corpo, avancos=tp.AVANCOS),
                         x=float(x0 + 2), y=float(y0 + tam[1] - 4))
    for papel in ('linha', 'icone1', 'icone2', 'assinatura'):
        tam, x0, y0 = caixa(papel)
        p.create_pixel_layer(Image.new('RGBA', tam, CORES[papel]), name=NOMES[papel], top=y0, left=x0)
    tam, x0, y0 = caixa('circulo')
    disco = Image.new('RGBA', tam, (0, 0, 0, 0))
    ImageDraw.Draw(disco).ellipse([0, 0, tam[0] - 1, tam[1] - 1], fill=CORES['circulo'])
    p.create_pixel_layer(disco, name=NOMES['circulo'], top=y0, left=x0)
    for papel in PRODUTOS:
        tam, x0, y0 = caixa(papel)
        p.create_pixel_layer(Image.new('RGBA', tam, CORES[papel]), name=NOMES[papel], top=y0, left=x0)
    return rap._salvar(p, destino)


def criar_job(base, kv):
    """O job do KV kv em base/kv-<kv>: o PSD, a fonte de autoteste, o laudo e o briefing de teste (as funcoes, as
    regras e os tres formatos, com o giro ja decidido). Devolve {'job', 'ids': papel -> layer_id, 'funcoes':
    layer_id -> funcao}."""
    import test_derivacao_apoio as ap
    import test_fontes_apoio as fap
    from desdobra import contratos
    from desdobra.briefing import modelo as mb
    from desdobra.job import nucleo
    from desdobra.render import autoteste
    base = Path(base) / ('kv-%s' % kv)
    fontes = base / 'origem-fontes'
    fap.gravar(fontes, 'autoteste.ttf', autoteste.gerar_fonte())
    job = base / 'job'
    nucleo.criar(job, psd(base / 'origem' / ('kv-%s.psd' % kv), kv, autoteste.NOME_PS), 'c', fontes=[fontes])
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    por_nome = {c['nome']: c['identidade']['layer_id'] for c in laudo['camadas']}
    ids = {papel: por_nome[nome] for papel, nome in NOMES.items()}
    funcoes = {ids[papel]: f for papel, f in FUNCOES.items()}
    regras = dict(ap.REGRAS, **{f: r for f, (r, _x, _y) in USADAS.items()})
    ancoras = dict(ap.ANCORAS, **{f: (x, y) for f, (_r, x, y) in USADAS.items()})
    b = ap.briefing(funcoes=funcoes, regras=regras, ancoras=ancoras,
                    formatos=[ap.formato(i, w, h, rotacao={'graus': 0, 'sentido': None}) for i, w, h in FORMATOS])
    b.pop('cabecalho')
    b.pop('job_id')
    arq = base / 'fixture.json'
    arq.write_text(json.dumps(b), encoding='utf-8')
    mb.importar_teste(job, arq)
    return {'job': job, 'ids': ids, 'funcoes': funcoes}


def passo_2(funcoes):
    """O passo 2 e o Design system como o DA os deixa no rascunho: a funcao de cada camada e a regra e a ancora de cada
    funcao usada."""
    return {'funcoes': {str(k): {'funcao': v, 'observacao': None} for k, v in funcoes.items()},
            'design': {f: {'regra': r, 'x': x, 'y': y} for f, (r, x, y) in USADAS.items()}}
