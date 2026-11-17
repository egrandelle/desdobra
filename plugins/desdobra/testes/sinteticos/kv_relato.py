# -*- coding: utf-8 -*-
"""O job sintetico do relato do KV A na 0.9.2 (revisao 0.9.3), gerado na hora numa pasta temporaria.

A mesma estrutura de camadas do KV A do relato, sem nada dele: duas pastas do topo que viram pranchetas ("01"
visivel e "02" oculta); dentro da "01", dois fundos, um retangulo, um grafismo que se sobrepoe ao retangulo, o titulo
e o texto de apoio (camadas de texto na fonte de autoteste) e o logo; uma camada "Background" fora das pastas. A folha
de spec e um CSV de uma coluna "Formato" com os quatro formatos do relato. Nomes, cores e caixas sao inventados aqui.

O retangulo (Fundo) e o grafismo se sobrepoem e andam juntos num bloco rigido: com regras de escala diferentes para as
duas funcoes, o motor recusa o briefing (bloco_com_regras_diferentes), como no relato; com a mesma regra, as familias
saem.

Geradores:
  psd(destino, ps)       o PSD 540 x 960
  criar(base)            o job com laudo, fontes e specs lidos, sem briefing: (job, ids por papel, laudo)
  passo_2(ids, design)   o passo 2 e o Design system como o DA os deixa no rascunho
"""
from pathlib import Path

LARGURA, ALTURA = 540, 960
FORMATOS = ['1080x1920', '1080x1080', '300x600', '970x250']
# o papel de cada camada e o nome dela no PSD
NOMES = {'01': '01', 'logo': 'objeto-vetor-sintetico', 'grafismo': 'grafismo-sintetico',
         'retangulo': 'retangulo-sintetico', 'titulo': 'titulo-sintetico', 'apoio': 'apoio-sintetico',
         'bg2': 'bg-dois-sintetico', 'bg1': 'bg-um-sintetico', 'background': 'Background', '02': '02',
         'outro': 'fundo-outro-sintetico'}
# a funcao que o DA deu a cada papel no relato (a pasta "01" como Estrutura, que passa para dentro)
FUNCOES = {'01': 'estrutura', 'logo': 'logo_principal', 'grafismo': 'grafismo', 'retangulo': 'fundo',
           'titulo': 'titulo', 'apoio': 'texto_de_apoio', 'bg2': 'fundo', 'bg1': 'fundo', 'background': 'fundo'}
# o Design system do relato: Grafismo pela altura e Fundo pela area (o bloco com regras diferentes)
DESIGN = {'grafismo': ('altura', 'direita', 'topo'), 'fundo': ('raiz_area', 'direita', 'meio'),
          'titulo': ('altura', 'esquerda', 'topo'), 'texto_de_apoio': ('altura', 'esquerda', 'meio'),
          'logo_principal': ('altura', 'direita', 'base')}
# o mesmo Design system com o Grafismo pela area, como o Fundo: o motor monta as familias
DESIGN_MESMA_REGRA = dict(DESIGN, grafismo=('raiz_area', 'direita', 'topo'))


def psd(destino, ps):
    from PIL import Image
    from psd_tools import PSDImage

    import test_fontes_apoio as fap
    import test_render_apoio as rap
    import test_tela_palco as tp
    p = PSDImage.new('RGB', (LARGURA, ALTURA), color=(255, 255, 255))
    p.create_pixel_layer(Image.new('RGBA', (LARGURA, ALTURA), (0, 110, 60, 255)), name=NOMES['background'])
    g = p.create_group(name=NOMES['01'])
    g.create_pixel_layer(Image.new('RGBA', (LARGURA, ALTURA), (0, 140, 70, 255)), name=NOMES['bg1'])
    g.create_pixel_layer(Image.new('RGBA', (LARGURA, 360), (0, 160, 80, 255)), name=NOMES['bg2'], top=600, left=0)
    g.create_pixel_layer(Image.new('RGBA', (LARGURA, 300), (250, 220, 0, 255)), name=NOMES['retangulo'], top=0,
                         left=0)
    g.create_pixel_layer(Image.new('RGBA', (220, 220), (0, 60, 160, 255)), name=NOMES['grafismo'], top=40, left=300)
    t1 = g.create_pixel_layer(Image.new('RGBA', (240, 40), (20, 20, 20, 255)), name=NOMES['titulo'], top=80, left=30)
    fap._virar_texto(t1, [('HOAX', 0, 36.0, 0)], [ps], fap.largura('HOAX', 36.0, avancos=tp.AVANCOS), x=32.0, y=114.0)
    t2 = g.create_pixel_layer(Image.new('RGBA', (300, 30), (20, 20, 20, 255)), name=NOMES['apoio'], top=400, left=30)
    fap._virar_texto(t2, [('VOX AH HOAX', 0, 20.0, 0)], [ps], fap.largura('VOX AH HOAX', 20.0, avancos=tp.AVANCOS),
                     x=32.0, y=424.0)
    g.create_pixel_layer(Image.new('RGBA', (140, 80), (255, 255, 255, 255)), name=NOMES['logo'], top=850, left=380)
    g2 = p.create_group(name=NOMES['02'])
    g2.create_pixel_layer(Image.new('RGBA', (LARGURA, ALTURA), (20, 40, 200, 255)), name=NOMES['outro'])
    g2.visible = False
    return rap._salvar(p, destino)


def criar(base):
    """O job em base/job, com a folha portalteste.csv; devolve (job, {papel: layer_id}, laudo)."""
    import test_fontes_apoio as fap
    from desdobra import contratos
    from desdobra.job import nucleo
    from desdobra.render import autoteste
    base = Path(base)
    fontes = base / 'origem-fontes'
    fap.gravar(fontes, 'autoteste.ttf', autoteste.gerar_fonte())
    specs = base / 'origem-specs'
    specs.mkdir(parents=True, exist_ok=True)
    (specs / 'portalteste.csv').write_bytes(('Formato\n' + ''.join(f + '\n' for f in FORMATOS)).encode('utf-8'))
    job = base / 'job'
    nucleo.criar(job, psd(base / 'origem' / 'kv.psd', autoteste.NOME_PS), 'c', fontes=[fontes], specs=specs)
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    laudo = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    por_nome = {c['nome']: c['identidade']['layer_id'] for c in laudo['camadas']}
    ids = {papel: por_nome[nome] for papel, nome in NOMES.items() if nome in por_nome}
    return job, ids, laudo


def passo_2(ids, design=None):
    design = design or DESIGN
    return {'funcoes': {str(ids[p]): {'funcao': f, 'observacao': None} for p, f in FUNCOES.items() if p in ids},
            'design': {f: {'regra': r, 'x': x, 'y': y} for f, (r, x, y) in design.items()}}
