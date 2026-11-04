# -*- coding: utf-8 -*-
"""Validacao final da entrega, roteamento e conferir-entrega (M6, fatias 4 e 6 da proposta; decisoes-v1.md, 136, 137,
140, 141, 142 e 143), em imagens e contextos sinteticos gerados na hora (rotulos KV A, sem conteudo de cliente).

Criterios de pronto cobertos aqui (arquitetura-v1.md, 9.7):
  - 0 arquivo com verificacao que reprova em entrega/aprovados (teste de propriedade, com casos sorteados);
  - 100% dos arquivos em aprovados abaixo da leitura estrita do teto, ou em reprovados com regra e sugestao (1 byte
    acima do teto, teto condicional sem a escolha do DA);
  - area segura do 1080x1920 da Globo (250 px no topo e na base, nº 141) conferida contra a tinta medida do texto e a
    caixa do logo no layout, com tolerancia 0 px: 1 px dentro reprova;
  - borda de 1 px aplicada e conferida quando o DA declara a condicao; sem a declaracao, nada e desenhado;
  - saida sRGB conferida: PNG com os pixels exatos de transformar(master), JPEG com os mesmos bytes num reencode com os
    parametros gravados, caminho de cor igual aos parametros do job, sem perfil (nº 140);
  - mutacoes detectadas em 100%: borda removida, texto 1 px na area segura, 1 byte acima do teto, dimensao e MIME
    errados, arquivo trocado em entrega/ depois da entrega, perfil ligado, intent trocado, arquivo de outro master;
  - nova entrega move a anterior para entrega/anteriores/<carimbo>/ e a troca volta inteira quando um passo falha;
  - conferir-entrega so le (nenhum arquivo do job muda) e roda sem o console do DA (nao e protegido pelo gancho).

A gravacao da entrega so parte de uma pessoa: o console e simulado pelo fixture pessoa (o caminho do Disparo e o de
verdade).
"""
import io
import os
import random

import numpy as np
import pytest
from PIL import Image, ImageCms

from desdobra import arquivos, cli, contratos, humano
from desdobra import cor as mod_cor
from desdobra.entrega import codificar, validar
from desdobra.resultado import Codigo

JPEG, PNG = 'image/jpeg', 'image/png'
ROT0 = {'graus': 0, 'sentido': None}
PAR = mod_cor.parametros()
QUEM = {'meio': 'terminal', 'usuario': 'teste', 'maquina': 'teste', 'quando': '2026-11-04T10:00:00-03:00'}
GLOBO = (1080, 1920)
SEGURA_PX = 250


def _v(valor, **extra):
    return dict({'id': 'x', 'valor': valor, 'situacao': 'confirmado', 'fonte': {'folha': 'f', 'trecho': 't'}}, **extra)


def _spec(alvo=10 ** 7, tipos=(PNG, JPEG), segura=False, borda=False, condicional=None, faixa=None, dimensao=None):
    """Folha confirmada sintetica. condicional: (alvo hospedado, alvo por tag) no lugar do peso unico."""
    campos = {'tipos_aceitos': _v(list(tipos))}
    if condicional:
        campos['peso_max_hospedado'] = _v({'alvo_bytes': condicional[0], 'reprova_acima_bytes': condicional[0] * 2},
                                          condicao='hospedado')
        campos['peso_max_tag'] = _v({'alvo_bytes': condicional[1], 'reprova_acima_bytes': condicional[1] * 2},
                                    condicao='por_tag')
    elif alvo is not None:
        campos['peso_max'] = _v({'alvo_bytes': alvo, 'reprova_acima_bytes': alvo * 2})
    if segura:
        campos['area_segura'] = _v({'pct': 14, 'px': SEGURA_PX, 'lados': ['inferior', 'superior']})
    if borda:
        campos['borda_1px'] = _v({'espessura_px': 1, 'cor': 'preta'}, condicao='fundo igual ao da página')
    if faixa:
        campos['faixas'] = _v([{'lado': 'inferior', 'px': faixa}])
    if dimensao:
        campos['dimensao'] = _v({'largura': dimensao[0], 'altura': dimensao[1]})
    return {'id': 'kv-a', 'chave': 'veiculo|circuito|kv-a', 'campos': campos}


def _params(**campos):
    return {k: {'valor': v, 'confirmado_por': QUEM} for k, v in campos.items()}


def _render(textos=(), par=PAR, conversao=None):
    return {'parametros': {'cor': par.para_json()},
            'conversao_cor': conversao or {'feita': False, 'motivo': 'documento_sem_perfil'},
            'entradas': [{'id': 'e%d' % k, 'tipo': 'texto', 'tinta': list(t)} for k, t in enumerate(textos)]}


def _derivacao(logos=()):
    sem = {'esq': False, 'topo': False, 'dir': False, 'base': False}
    return {'elementos': [{'id': 'm%d' % k, 'classe': 'marca', 'caixa': list(c), 'transformacao': {'sangra': sem}}
                          for k, c in enumerate(logos)] + [{'id': 'fundo', 'classe': 'cena', 'caixa': [0, 0, 1, 1]}]}


def _arte(largura, altura, semente=0):
    """Arte chapada com blocos de cor (como um banner simples)."""
    a = np.full((altura, largura, 3), 235, np.uint8)
    rng = np.random.default_rng(semente)
    for _ in range(6):
        x, y = int(rng.integers(0, largura - 8)), int(rng.integers(0, altura - 8))
        a[y:y + altura // 6, x:x + largura // 5] = rng.integers(0, 256, 3, dtype=np.uint8)
    return Image.fromarray(a, 'RGB')


def _ctx(master, spec, *, params=None, render=None, derivacao=None, par=PAR, fmt=None):
    fmt = fmt or {'id': 'kv-a', 'chave': spec['chave'] if spec else 'veiculo|circuito|kv-a', 'largura': master.width,
                  'altura': master.height, 'rotacao': ROT0}
    return {'formato': fmt, 'spec': spec, 'parametros': params or {}, 'master': master, 'render': render or _render(),
            'cor': par, 'derivacao': derivacao, 'arquivo_specs': 'specs/formatos-do-job.json'}


def _final(ctx, **troca):
    """O arquivo final do contexto, como o encoder do job faz (troca: argumentos do codificar trocados)."""
    p, spec = ctx['parametros'], ctx['spec']
    rot = ctx['formato']['rotacao']
    img = troca.pop('img', ctx['master'])
    k = {'tipos_aceitos': list(spec['campos']['tipos_aceitos']['valor']),
         'teto': codificar.teto_estrito(spec, (p.get('condicao') or {}).get('valor')),
         'graus': rot['graus'], 'sentido': (p.get('rotacao_sentido') or {}).get('valor'),
         'cor_de_achatamento': (p.get('cor_de_achatamento') or {}).get('valor'),
         'borda': codificar.borda_declarada(spec, p)}
    k.update(troca)
    return codificar.codificar(img, **k)


def _validar(final, ctx, nome=None):
    return validar.validar(final, nome or 'kv-a.%s' % final.extensao, ctx)


def _reprovas(itens):
    return sorted({i['regra'] for i in itens if i['situacao'] == 'reprova'})


def _com_dados(final, dados):
    return codificar.ArquivoFinal(dados=dados, extensao=final.extensao, parametros=final.parametros,
                                  medidas=final.medidas)


def _png(img, **k):
    buf = io.BytesIO()
    img.save(buf, format='PNG', **k)
    return buf.getvalue()


def _pixel(img, x=5, y=7):
    a = np.array(img)
    a[y, x, 0] = (int(a[y, x, 0]) + 1) % 256  # numero-neutro: um nivel a mais num canal de 8 bits
    return Image.fromarray(a, img.mode)


# ------------------------------------------------------------------ o caso limpo passa
def _globo(**k):
    """Globo 1080x1920 sintetico: texto com a tinta a 0 px da area segura no topo e na base, logo na base."""
    master = _arte(*GLOBO)
    textos = k.pop('textos', [(100, SEGURA_PX, 980, 400), (100, 1500, 980, GLOBO[1] - SEGURA_PX)])
    logos = k.pop('logos', [(400, 1580, 680, GLOBO[1] - SEGURA_PX)])
    spec = k.pop('spec', None) or _spec(segura=True, borda=True)
    return _ctx(master, spec, render=_render(textos), derivacao=_derivacao(logos), **k)


def test_caso_limpo_do_globo_passa_com_tolerancia_zero():
    ctx = _globo()
    itens = _validar(_final(ctx), ctx)
    assert _reprovas(itens) == [], [i for i in itens if i['situacao'] == 'reprova']
    segura = next(i for i in itens if i['nome'] == 'area_segura')
    assert segura['medidas']['caixa'] == [0.0, 250.0, 1080.0, 1670.0] and segura['medidas']['elementos'] == 3
    assert segura['fonte']['tolerancia']['limite_id'] == 'entrega.tolerancia_area_px'
    assert segura['fonte']['tolerancia']['valor'] == 0 and segura['fonte']['tolerancia']['efeito'] == 'reprova'
    logo = next(i for i in itens if i['nome'] == 'logo')
    assert (logo['situacao'], logo['regra']) == ('registra', 'logo_pela_caixa_do_layout')
    # a folha tem borda condicional e o DA nao declarou: nada desenhado, so registro
    borda = next(i for i in itens if i['nome'] == 'borda_1px')
    assert (borda['situacao'], borda['regra']) == ('registra', 'borda_sem_condicao_declarada')
    assert validar.destino(itens) == validar.APROVADOS


@pytest.mark.parametrize('lado, textos, logos', [
    ('topo, texto', [(100, SEGURA_PX - 1, 980, 400)], []),
    ('base, texto', [(100, 1500, 980, GLOBO[1] - SEGURA_PX + 1)], []),
    ('base, logo', [], [(400, 1580, 680, GLOBO[1] - SEGURA_PX + 1)]),
    ('topo, logo', [], [(400, SEGURA_PX - 1, 680, 400)]),
])
def test_um_pixel_dentro_da_area_segura_reprova(lado, textos, logos):
    ctx = _globo(textos=textos, logos=logos)
    itens = _validar(_final(ctx), ctx)
    assert _reprovas(itens) == ['fora_da_area_segura'], lado
    seg = next(i for i in itens if i['nome'] == 'area_segura')
    assert seg['sugestao'] and len(seg['medidas']['fora']) == 1, seg
    assert validar.destino(itens) == validar.REPROVADOS


def test_faixa_e_area_util_com_tolerancia_zero():
    master = _arte(400, 300)
    spec = _spec(faixa=40)
    ok = _ctx(master, spec, render=_render([(10, 10, 200, 260)]))
    assert _reprovas(_validar(_final(ok), ok)) == []
    dentro = _ctx(master, spec, render=_render([(10, 10, 200, 261)]))
    assert _reprovas(_validar(_final(dentro), dentro)) == ['dentro_da_faixa', 'fora_da_area_util']


# ------------------------------------------------------------------ peso (nº 136 e 137)
def test_um_byte_acima_do_teto_reprova_com_regra_e_sugestao():
    ctx = _ctx(_arte(300, 600), _spec())
    final = _final(ctx)
    n = len(final.dados)
    for alvo, esperado in ((n, []), (n - 1, ['acima_do_teto_estrito'])):
        c = dict(ctx, spec=_spec(alvo=alvo))
        itens = _validar(final, c)
        assert _reprovas(itens) == esperado, alvo
    peso = next(i for i in _validar(final, dict(ctx, spec=_spec(alvo=n - 1))) if i['nome'] == 'peso')
    assert peso['medidas']['bytes'] == n and peso['medidas']['alvo_bytes'] == n - 1 and peso['sugestao']
    assert peso['fonte']['limite']['limite_id'] == 'entrega.peso_reprova_acima_da_leitura_decimal'


def test_teto_condicional_sem_a_escolha_do_da_mede_contra_o_mais_estrito():
    ctx = _ctx(_arte(300, 600), _spec(condicional=(250000, 500000)))
    final = _final(ctx)
    tamanho = len(final.dados)
    apertada = dict(ctx, spec=_spec(condicional=(tamanho - 1, 10 ** 7)))
    itens = _validar(final, apertada)
    assert _reprovas(itens) == ['condicao_nao_decidida']
    assert 'parametros/entrega.json' in next(i for i in itens if i['nome'] == 'peso')['sugestao']
    # com a condicao escolhida pelo DA, vale o teto dela
    assert _reprovas(_validar(final, dict(apertada, parametros=_params(condicao='por_tag')))) == []


def test_sem_peso_ou_sem_folha_confirmada_reprova():
    ctx = _ctx(_arte(64, 32), _spec(alvo=None))
    assert 'peso_sem_valor_confirmado' in _reprovas(_validar(_final(ctx), ctx))
    final = _final(ctx)
    assert {'formato_sem_spec_confirmada', 'peso_sem_valor_confirmado', 'sem_tipos_aceitos_confirmados'} <= \
        set(_reprovas(_validar(final, dict(ctx, spec=None))))


# ------------------------------------------------------------------ borda de 1 px
def test_borda_declarada_e_desenhada_e_conferida():
    ctx = _globo(params=_params(borda_1px=True))
    final = _final(ctx)
    assert final.parametros['borda'] == {'espessura_px': 1, 'cor': '#000000'}
    img = np.asarray(Image.open(io.BytesIO(final.dados)))
    assert (img[0] == 0).all() and (img[-1] == 0).all() and (img[:, 0] == 0).all() and (img[:, -1] == 0).all()
    assert (img[1:-1, 1:-1] == np.asarray(ctx['master'])[1:-1, 1:-1]).all()  # a arte nao encolhe
    itens = _validar(final, ctx)
    assert _reprovas(itens) == []
    assert next(i for i in itens if i['nome'] == 'borda_1px')['situacao'] == 'ok'
    # JPEG: conferida nos pixels antes do encoder, que o reencode liga ao arquivo
    cj = _globo(params=_params(borda_1px=True), spec=_spec(segura=True, borda=True, tipos=(JPEG,)))
    fj = _final(cj)
    assert fj.extensao == 'jpg' and _reprovas(_validar(fj, cj, 'kv-a.jpg')) == []


# um lado do anel sem os cantos (os cantos sao dos dois lados): cada mutacao so mexe num lado
LADOS_DA_BORDA = {'topo': (slice(0, 1), slice(1, -1)), 'base': (slice(-1, None), slice(1, -1)),
                  'esq': (slice(1, -1), slice(0, 1)), 'dir': (slice(1, -1), slice(-1, None))}


@pytest.mark.parametrize('lado', sorted(LADOS_DA_BORDA))
def test_borda_sem_um_lado_e_pega(lado):
    # cada lado do anel e conferido: tirar so um lado (os pixels da arte no lugar) reprova
    borda = {'espessura_px': 1, 'cor': '#000000'}
    arte = _arte(40, 30, 3)
    com = codificar.desenhar_borda(arte, borda)
    assert validar.tem_borda(com, borda)
    a = np.array(com)
    a[LADOS_DA_BORDA[lado]] = np.array(arte)[LADOS_DA_BORDA[lado]]
    assert not validar.tem_borda(Image.fromarray(a, 'RGB'), borda), lado


def test_mutacoes_de_um_lado_da_borda_detectadas_em_100_por_cento():
    borda = {'espessura_px': 1, 'cor': '#000000'}
    arte = _arte(40, 30, 3)
    detectadas = 0
    for faixa in LADOS_DA_BORDA.values():
        a = np.array(codificar.desenhar_borda(arte, borda))
        a[faixa] = np.array(arte)[faixa]
        detectadas += not validar.tem_borda(Image.fromarray(a, 'RGB'), borda)
    assert detectadas == len(LADOS_DA_BORDA)


def test_nomes_que_colidem_caem_para_o_id_com_aviso():
    # 'a' com o sufixo '-b' e 'a-b' sem sufixo dariam o mesmo nome; no Windows, a caixa tambem colide
    sufixo = {'campos': {'sufixo_nome_arquivo': _v('-b')}}
    caixa = {'campos': {'sufixo_nome_arquivo': _v('-B')}}
    nomes = validar.nomes_dos_arquivos([('a', sufixo, 'jpg'), ('a-b', None, 'jpg'), ('c', sufixo, 'png'),
                                        ('d', caixa, 'jpg'), ('d-b', None, 'jpg')])
    assert [n for n, _x in nomes] == ['a.jpg', 'a-b.jpg', 'c-b.png', 'd.jpg', 'd-b.jpg']
    # so o formato cujo nome mudou leva o aviso (o que ja sai com o id fica como esta)
    avisos = [x for _n, x in nomes if x is not None]
    assert [x is not None for _n, x in nomes] == [True, False, False, True, False] and all((x['situacao'], x['regra']) == ('avisa', 'nome_de_arquivo_repetido')
                                    for x in avisos)
    assert len({n.casefold() for n, _x in nomes}) == len(nomes)


def test_borda_declarada_sem_valor_na_folha_recusa():
    ctx = _ctx(_arte(64, 32), _spec(), params=_params(borda_1px=True))
    with pytest.raises(codificar.ErroCodificar) as e:
        codificar.borda_declarada(ctx['spec'], ctx['parametros'])
    assert e.value.codigo == 'borda_sem_valor_confirmado'


# ------------------------------------------------------------------ mutacoes
def _borda_removida():
    ctx = _globo(params=_params(borda_1px=True))
    return _final(ctx, borda=None), ctx


def _borda_removida_dos_pixels():
    ctx = _globo(params=_params(borda_1px=True))
    f = _final(ctx)
    sem = codificar._rgb(ctx['master'], None)[0]
    return _com_dados(f, _png(sem)), ctx


def _texto_na_area_segura():
    ctx = _globo(textos=[(100, SEGURA_PX - 1, 980, 400)])
    return _final(ctx), ctx


def _logo_na_area_segura():
    ctx = _globo(logos=[(400, 1580, 680, GLOBO[1] - SEGURA_PX + 1)])
    return _final(ctx), ctx


def _byte_acima():
    ctx = _ctx(_arte(300, 600), _spec())
    f = _final(ctx)
    return f, dict(ctx, spec=_spec(alvo=len(f.dados) - 1))


def _condicao_nao_decidida():
    ctx = _ctx(_arte(300, 600), _spec())
    f = _final(ctx)
    return f, dict(ctx, spec=_spec(condicional=(len(f.dados) - 1, 10 ** 7)))


def _dimensao_errada():
    ctx = _ctx(_arte(300, 600), _spec())
    f = _final(ctx)
    return f, dict(ctx, formato=dict(ctx['formato'], largura=301))


def _dimensao_da_folha_errada():
    ctx = _ctx(_arte(300, 600), _spec(dimensao=(300, 601)))
    return _final(ctx), ctx


def _mime_nao_aceito():
    ctx = _ctx(_arte(300, 600), _spec())
    f = _final(ctx)
    return f, dict(ctx, spec=_spec(tipos=(JPEG,)))


def _mime_com_nome_errado():
    ctx = _ctx(_arte(300, 600), _spec(tipos=(JPEG,)))
    f = _final(ctx)
    return codificar.ArquivoFinal(dados=f.dados, extensao='png', parametros=f.parametros), ctx


def _perfil_no_arquivo():
    ctx = _ctx(_arte(300, 600), _spec())
    f = _final(ctx)
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    return _com_dados(f, _png(Image.open(io.BytesIO(f.dados)), icc_profile=icc)), ctx


def _perfil_pedido_pelo_job():
    ctx = _ctx(_arte(300, 600), _spec())
    return _final(ctx), dict(ctx, cor=mod_cor.parametros(perfil_embutido_na_saida=True))


def _icc_srgb():
    return ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()


def _master_com_perfil():
    # o master do render com perfil embutido e o job sem perfil na saida (nº 140): o arquivo final sai sem perfil, mas
    # o master que o originou nao segue o caminho de cor do job
    master = _arte(300, 600)
    master.info['icc_profile'] = _icc_srgb()
    ctx = _ctx(master, _spec())
    return _final(ctx), ctx


def _intent_trocado_no_job():
    ctx = _ctx(_arte(300, 600), _spec())
    return _final(ctx), dict(ctx, cor=mod_cor.parametros(intent='perceptual' if PAR.intent != 'perceptual'
                                                         else 'relativo_colorimetrico'))


def _intent_trocado_na_conversao():
    outro = 'perceptual' if PAR.intent != 'perceptual' else 'relativo_colorimetrico'
    conv = {'feita': True, 'intent': outro, 'compensacao_ponto_preto': PAR.compensacao_ponto_preto}
    ctx = _ctx(_arte(300, 600), _spec(), render=_render(conversao=conv))
    return _final(ctx), ctx


def _png_de_outro_master():
    ctx = _ctx(_arte(300, 600), _spec())
    return _final(ctx, img=_pixel(ctx['master'])), ctx


def _jpeg_de_outro_master():
    # o master de outro render (outra arte). Um nivel num pixel so pode sumir na quantizacao do JPEG e dar os mesmos
    # bytes, isto e, o mesmo arquivo; o master trocado em si o portao ja pega pelo sha256 (test_entrega_job)
    ctx = _ctx(_arte(300, 600), _spec(tipos=(JPEG,)))
    return _final(ctx, img=_arte(300, 600, semente=5)), ctx


def _jpeg_de_outra_qualidade():
    ctx = _ctx(_arte(300, 600), _spec(tipos=(JPEG,)))
    f = _final(ctx)
    return codificar.ArquivoFinal(dados=f.dados, extensao='jpg', parametros=dict(f.parametros, qualidade=80)), ctx


def _com_alfa():
    ctx = _ctx(_arte(300, 600), _spec())
    f = _final(ctx)
    rgba = Image.open(io.BytesIO(f.dados)).convert('RGBA')
    rgba.putpixel((0, 0), (0, 0, 0, 0))
    return _com_dados(f, _png(rgba)), ctx


def _sentido_trocado():
    master = _arte(300, 200)
    fmt = {'id': 'kv-a', 'chave': 'veiculo|circuito|kv-a', 'largura': 200, 'altura': 300,
           'rotacao': {'graus': 90, 'sentido': None}}
    ctx = _ctx(master, _spec(), params=_params(rotacao_sentido='horario'), fmt=fmt)
    return _final(ctx, sentido='anti_horario'), ctx


MUTACOES = [
    ('borda_removida', _borda_removida, {'parametros_diferentes_das_decisoes', 'borda_ausente'}),
    ('borda_removida_dos_pixels', _borda_removida_dos_pixels, {'pixels_diferentes_do_master', 'borda_nao_conferida'}),
    ('texto_1px_na_area_segura', _texto_na_area_segura, {'fora_da_area_segura'}),
    ('logo_1px_na_area_segura', _logo_na_area_segura, {'fora_da_area_segura'}),
    ('um_byte_acima_do_teto', _byte_acima, {'acima_do_teto_estrito'}),
    ('condicao_nao_decidida', _condicao_nao_decidida, {'condicao_nao_decidida'}),
    ('dimensao_errada', _dimensao_errada, {'dimensao_diferente'}),
    ('dimensao_da_folha_errada', _dimensao_da_folha_errada, {'dimensao_diferente'}),
    ('mime_nao_aceito', _mime_nao_aceito, {'tipo_nao_aceito'}),
    ('mime_com_nome_errado', _mime_com_nome_errado, {'extensao_nao_bate_com_o_tipo'}),
    ('perfil_no_arquivo', _perfil_no_arquivo, {'perfil_embutido_no_arquivo'}),
    ('perfil_pedido_pelo_job', _perfil_pedido_pelo_job, {'job_pede_perfil_embutido', 'conversao_cor_diferente_do_job'}),
    ('master_com_perfil', _master_com_perfil, {'master_com_perfil_embutido'}),
    ('intent_trocado_no_job', _intent_trocado_no_job, {'conversao_cor_diferente_do_job'}),
    ('intent_trocado_na_conversao', _intent_trocado_na_conversao, {'conversao_cor_diferente_do_job'}),
    ('png_de_outro_master', _png_de_outro_master, {'pixels_diferentes_do_master'}),
    ('jpeg_de_outro_master', _jpeg_de_outro_master, {'bytes_diferentes_do_reencode'}),
    ('jpeg_de_outra_qualidade', _jpeg_de_outra_qualidade, {'bytes_diferentes_do_reencode'}),
    ('com_alfa', _com_alfa, {'arquivo_com_alfa', 'pixels_diferentes_do_master'}),
    ('sentido_trocado', _sentido_trocado, {'parametros_diferentes_das_decisoes'}),
]


@pytest.mark.parametrize('nome, mexer, esperado', MUTACOES, ids=[m[0] for m in MUTACOES])
def test_mutacao_reprova_com_a_regra(nome, mexer, esperado):
    final, ctx = mexer()
    itens = _validar(final, ctx)
    assert set(_reprovas(itens)) == esperado, (nome, _reprovas(itens))
    assert validar.destino(itens) == validar.REPROVADOS
    assert all(i.get('sugestao') for i in itens if i['situacao'] == 'reprova')


def test_mutacoes_da_validacao_detectadas_em_100_por_cento():
    detectadas = 0
    for _nome, mexer, _esperado in MUTACOES:
        final, ctx = mexer()
        detectadas += validar.destino(_validar(final, ctx)) == validar.REPROVADOS
    assert detectadas == len(MUTACOES)


def test_conferencia_srgb_png_exato_e_jpeg_pelo_reencode():
    master = _arte(120, 80)
    ctx = _ctx(master, _spec())
    f = _final(ctx)
    assert f.extensao == 'png'
    item = next(i for i in _validar(f, ctx) if i['nome'] == 'arquivo_do_master')
    assert (item['situacao'], item['medidas']['comparacao']) == ('ok', 'pixels_exatos')
    cj = _ctx(master, _spec(tipos=(JPEG,)))
    fj = _final(cj)
    item = next(i for i in _validar(fj, cj, 'kv-a.jpg') if i['nome'] == 'arquivo_do_master')
    assert (item['situacao'], item['medidas']['comparacao'], item['medidas']['versoes_iguais']) == \
        ('ok', 'bytes_do_reencode', True)
    assert codificar._jpeg(validar.transformar(master, fj.parametros), fj.parametros['qualidade'],
                           gravados=fj.parametros) == fj.dados
    caminho = next(i for i in _validar(f, ctx) if i['nome'] == 'caminho_de_cor')
    assert caminho['situacao'] == 'ok' and caminho['medidas']['conversao'] == 'documento_sem_perfil'


def _perfil_do_master(itens):
    return next(i for i in itens if i['nome'] == 'perfil_do_master')


def test_perfil_do_master_reprova_so_quando_o_job_nao_pede_perfil():
    final, ctx = _master_com_perfil()
    item = _perfil_do_master(_validar(final, ctx))
    assert (item['situacao'], item['regra']) == ('reprova', 'master_com_perfil_embutido')
    assert item['sugestao']
    sem = _ctx(_arte(300, 600), _spec())
    assert 'icc_profile' not in sem['master'].info
    item = _perfil_do_master(_validar(_final(sem), sem))
    assert (item['situacao'], item['regra']) == ('ok', None)
    # com o job pedindo perfil, o master com perfil segue o job: a regra do master fica de fora (o job reprova sozinho)
    pede = dict(ctx, cor=mod_cor.parametros(perfil_embutido_na_saida=True))
    itens = _validar(final, pede)
    assert _perfil_do_master(itens)['situacao'] == 'ok'
    assert 'master_com_perfil_embutido' not in _reprovas(itens)


def test_transformar_refaz_achatamento_e_giro():
    rgba = Image.new('RGBA', (30, 20), (10, 20, 30, 255))
    rgba.putpixel((3, 4), (200, 100, 50, 0))
    fmt = {'id': 'kv-a', 'chave': 'veiculo|circuito|kv-a', 'largura': 20, 'altura': 30,
           'rotacao': {'graus': 90, 'sentido': None}}
    ctx = _ctx(rgba, _spec(), params=_params(rotacao_sentido='horario', cor_de_achatamento='#ffffff'), fmt=fmt)
    f = _final(ctx)
    assert _reprovas(_validar(f, ctx)) == []
    sem_cor = dict(ctx, parametros=_params(rotacao_sentido='horario'))
    assert 'parametros_diferentes_das_decisoes' in _reprovas(_validar(f, sem_cor))


# ------------------------------------------------------------------ gravacao, troca e conferir-entrega
def _item(fid, final, ctx):
    nome, extra = validar.nome_do_arquivo(fid, ctx['spec'], final.extensao)
    return {'formato': fid, 'nome': nome, 'final': final,
            'verificacoes': ([extra] if extra else []) + validar.validar(final, nome, ctx)}


def _itens_de(casos):
    return [_item('kv-a-%02d' % k, f, c) for k, (f, c) in enumerate(casos)]


def _limpo(semente=0, jpeg=False):
    ctx = _ctx(_arte(96, 64, semente), _spec(tipos=(JPEG,) if jpeg else (PNG, JPEG)))
    return _final(ctx), ctx


def _entregar(pasta, itens):
    return validar.gravar(pasta, itens, 'j' * 32, disparo=humano.exigir('entregar'))


def test_gravar_so_com_o_disparo_do_entregar(tmp_path, pessoa):
    with pytest.raises(humano.ErroHumano):
        validar.gravar(tmp_path, _itens_de([_limpo()]), 'j' * 32, disparo=pessoa.exigir('aprovar'))
    assert not (tmp_path / 'entrega').exists()


def test_roteamento_grava_aprovados_reprovados_e_o_relatorio(tmp_path, pessoa):
    itens = _itens_de([_limpo(1), _byte_acima(), _limpo(2, jpeg=True), _texto_na_area_segura()])
    rel, anterior = _entregar(tmp_path, itens)
    assert anterior is None
    raiz = tmp_path / 'entrega'
    assert sorted(p.name for p in (raiz / 'aprovados').iterdir()) == ['kv-a-00.png', 'kv-a-02.jpg']
    assert sorted(p.name for p in (raiz / 'reprovados').iterdir()) == ['kv-a-01.png', 'kv-a-03.png']
    assert rel['contagens'] == {'aprovados': 2, 'reprovados': 2}
    dados = contratos.ler(raiz / validar.ARQUIVO_RELATORIO, validar.ESQUEMA)
    assert dados == rel and dados['relatorio_sha256'] == validar.selo(dados)
    por_nome = {a['nome']: a for a in dados['arquivos']}
    assert por_nome['kv-a-01.png']['regras'] == ['acima_do_teto_estrito'] and por_nome['kv-a-01.png']['sugestoes']
    assert por_nome['kv-a-03.png']['regras'] == ['fora_da_area_segura']
    assert por_nome['kv-a-00.png']['sha256'] == arquivos.sha256_arquivo(raiz / 'aprovados' / 'kv-a-00.png')
    assert not [p for p in raiz.iterdir() if p.name.startswith(arquivos.PREFIXO_TEMPORARIO)]
    assert validar.conferir_entrega(tmp_path)['ok']


@pytest.mark.parametrize('codigo', sorted(validar.RECUSAS_ROTEADAS))
def test_recusa_do_encoder_vai_para_reprovados_com_regra_e_sugestao_sem_arquivo(tmp_path, pessoa, codigo):
    # master com transparencia sem a cor de achatamento (e as outras recusas por formato): o formato fica em
    # reprovados com a regra e a sugestao, sem bytes, e os outros formatos seguem para a entrega
    sem = validar.item_sem_arquivo('kv-b', codificar.ErroCodificar(codigo, {'alfa_min': 0}), {'master_sha256': None})
    rel, _a = _entregar(tmp_path, _itens_de([_limpo(1)]) + [sem])
    raiz = tmp_path / 'entrega'
    assert rel['contagens'] == {'aprovados': 1, 'reprovados': 1}
    a = next(x for x in rel['arquivos'] if x['formato'] == 'kv-b')
    assert (a['pasta'], a['sha256'], a['regras']) == ('reprovados', None, [codigo]) and a['sugestoes']
    assert a['sugestoes'][0] != validar.SUGESTAO_PADRAO
    assert not list((raiz / 'reprovados').iterdir())
    assert validar.conferir_entrega(tmp_path)['ok']
    # um arquivo posto no lugar da entrada sem arquivo sobra
    (raiz / 'reprovados' / 'kv-b.png').write_bytes(b'x')
    assert validar.conferir_entrega(tmp_path)['sobram'] == ['reprovados/kv-b.png']


def test_entrada_sem_arquivo_movida_para_aprovados_e_pega(tmp_path, pessoa):
    sem = validar.item_sem_arquivo('kv-b', codificar.ErroCodificar('cor_de_achatamento_nao_definida'), {})
    _entregar(tmp_path, _itens_de([_limpo(1)]) + [sem])
    arq = tmp_path / 'entrega' / validar.ARQUIVO_RELATORIO
    d = arquivos.ler_json(arq)
    next(a for a in d['arquivos'] if a['formato'] == 'kv-b').update(pasta='aprovados', regras=[], sugestoes=[])
    d['relatorio_sha256'] = validar.selo(d)
    arquivos.gravar_json_atomico(arq, d)
    assert validar.conferir_entrega(tmp_path)['reprovado_em_aprovados'] == ['aprovados/kv-b']


def test_propriedade_nenhum_arquivo_que_reprova_em_aprovados(tmp_path, pessoa):
    """Casos sorteados (limpos e mutados): todo arquivo em aprovados passa de novo na validacao, e todo mutado esta em
    reprovados."""
    rng = random.Random(20261104)
    for rodada in range(12):
        casos, mutados = [], set()
        for k in range(rng.randint(1, 5)):
            if rng.random() < 0.5:
                casos.append(_limpo(rng.randint(0, 99), jpeg=rng.random() < 0.3))
            else:
                _nome, mexer, _e = rng.choice(MUTACOES)
                casos.append(mexer())
                mutados.add('kv-a-%02d' % k)
        pasta = tmp_path / ('r%02d' % rodada)
        itens = _itens_de(casos)
        rel, _anterior = _entregar(pasta, itens)
        raiz = pasta / 'entrega'
        por_formato = {i['formato']: i for i in itens}
        for reg in rel['arquivos']:
            caminho = raiz / reg['pasta'] / reg['nome']
            assert caminho.is_file()
            if reg['pasta'] == validar.APROVADOS:
                assert reg['formato'] not in mutados
                f, c = casos[int(reg['formato'][-2:])]
                de_novo = validar.validar(_com_dados(f, caminho.read_bytes()), reg['nome'], c)
                assert _reprovas(de_novo) == [] and not reg['regras']
            else:
                assert reg['regras'] and reg['sugestoes']
        assert {r['formato'] for r in rel['arquivos'] if r['pasta'] == validar.REPROVADOS} >= mutados
        assert len(rel['arquivos']) == len(por_formato)
        assert validar.conferir_entrega(pasta)['ok']


def test_nova_entrega_move_a_anterior_e_deixa_a_previa(tmp_path, pessoa):
    previa = tmp_path / 'entrega' / 'previa' / 'kv-a-00.png'
    arquivos.gravar_bytes_atomico(previa, b'previa')
    rel1, _a = _entregar(tmp_path, _itens_de([_limpo(1)]))
    rel2, anterior = _entregar(tmp_path, _itens_de([_limpo(2), _byte_acima()]))
    raiz = tmp_path / 'entrega'
    assert anterior == raiz / 'anteriores' / rel1['carimbo']
    velho = contratos.ler(anterior / validar.ARQUIVO_RELATORIO, validar.ESQUEMA)
    assert velho == rel1 and validar.conferir_pasta(anterior)['ok']
    assert contratos.ler(raiz / validar.ARQUIVO_RELATORIO, validar.ESQUEMA) == rel2
    assert previa.read_bytes() == b'previa'
    # a terceira no mesmo segundo nao sobrescreve a pasta anterior
    _rel3, anterior3 = _entregar(tmp_path, _itens_de([_limpo(3)]))
    assert anterior3 != anterior and anterior.is_dir() and validar.conferir_entrega(tmp_path)['ok']


def test_troca_que_falha_no_meio_volta_inteira(tmp_path, pessoa, monkeypatch):
    rel1, _a = _entregar(tmp_path, _itens_de([_limpo(1)]))
    antes = {p.relative_to(tmp_path).as_posix(): arquivos.sha256_arquivo(p)
             for p in tmp_path.rglob('*') if p.is_file()}
    original = os.replace

    def falha_no_reprovados(a, b):
        if arquivos.PREFIXO_TEMPORARIO in str(a) and str(a).endswith(validar.REPROVADOS):
            raise OSError('simulado')
        return original(a, b)
    monkeypatch.setattr(validar.os, 'replace', falha_no_reprovados)
    with pytest.raises(OSError):
        _entregar(tmp_path, _itens_de([_limpo(2), _limpo(3)]))
    monkeypatch.setattr(validar.os, 'replace', original)
    depois = {p.relative_to(tmp_path).as_posix(): arquivos.sha256_arquivo(p)
              for p in tmp_path.rglob('*') if p.is_file()}
    assert depois == antes and not (tmp_path / 'entrega' / 'anteriores').exists()
    assert validar.conferir_entrega(tmp_path)['ok']


def _trocar_arquivo(raiz):
    p = next((raiz / 'aprovados').iterdir())
    p.write_bytes(p.read_bytes()[:-1] + bytes([p.read_bytes()[-1] ^ 1]))  # numero-neutro: um bit trocado


def _trocar_por_outro(raiz):
    p = next((raiz / 'aprovados').iterdir())
    f, _c = _limpo(77)
    p.write_bytes(f.dados)


def _apagar_um(raiz):
    next((raiz / 'aprovados').iterdir()).unlink()


def _sobra(raiz):
    (raiz / 'aprovados' / 'extra.png').write_bytes(b'x')


def _fonte(raiz):
    (raiz / 'previa' / 'letra.ttf').parent.mkdir(parents=True, exist_ok=True)
    (raiz / 'previa' / 'letra.ttf').write_bytes(b'\0\1\0\0')


def _mover_reprovado(raiz):
    p = next((raiz / 'reprovados').iterdir())
    p.replace(raiz / 'aprovados' / p.name)


def _relatorio_mexido(raiz):
    arq = raiz / validar.ARQUIVO_RELATORIO
    d = arquivos.ler_json(arq)
    p = next((raiz / 'aprovados').iterdir())
    _trocar_por_outro(raiz)
    next(a for a in d['arquivos'] if a['nome'] == p.name).update(sha256=arquivos.sha256_arquivo(p),
                                                                  bytes=p.stat().st_size)
    arquivos.gravar_json_atomico(arq, d)


def _relatorio_resselado(raiz):
    """O reprovado movido para aprovados com o relatorio refeito e o selo recalculado: o roteamento nao bate."""
    arq = raiz / validar.ARQUIVO_RELATORIO
    d = arquivos.ler_json(arq)
    p = next((raiz / 'reprovados').iterdir())
    p.replace(raiz / 'aprovados' / p.name)
    next(a for a in d['arquivos'] if a['nome'] == p.name)['pasta'] = 'aprovados'
    d['relatorio_sha256'] = validar.selo(d)
    arquivos.gravar_json_atomico(arq, d)


def _sem_relatorio(raiz):
    (raiz / validar.ARQUIVO_RELATORIO).unlink()


def _resselado_sem_regras(raiz):
    """O reprovado movido para aprovados, com pasta e regras refeitas no relatorio e o selo recalculado: so as
    verificacoes (que ainda reprovam) dizem que o arquivo nao e de aprovados."""
    arq = raiz / validar.ARQUIVO_RELATORIO
    d = arquivos.ler_json(arq)
    p = next((raiz / 'reprovados').iterdir())
    p.replace(raiz / 'aprovados' / p.name)
    next(a for a in d['arquivos'] if a['nome'] == p.name).update(pasta='aprovados', regras=[], sugestoes=[])
    d['relatorio_sha256'] = validar.selo(d)
    arquivos.gravar_json_atomico(arq, d)


MUTACOES_DA_PASTA = [
    ('relatorio_resselado_sem_regras', _resselado_sem_regras, 'reprovado_em_aprovados'),
    ('um_bit_trocado', _trocar_arquivo, 'divergem'),
    ('arquivo_trocado_por_outro', _trocar_por_outro, 'divergem'),
    ('arquivo_apagado', _apagar_um, 'faltam'),
    ('arquivo_a_mais', _sobra, 'sobram'),
    ('arquivo_de_fonte', _fonte, 'arquivos_de_fonte'),
    ('reprovado_movido_para_aprovados', _mover_reprovado, 'faltam'),
    ('relatorio_mexido_a_mao', _relatorio_mexido, 'relatorio'),
    ('relatorio_resselado', _relatorio_resselado, 'reprovado_em_aprovados'),
    ('sem_relatorio', _sem_relatorio, 'relatorio'),
]


@pytest.fixture
def entregue(tmp_path, pessoa):
    _entregar(tmp_path, _itens_de([_limpo(1), _byte_acima()]))
    return tmp_path


@pytest.mark.parametrize('nome, mexer, chave', MUTACOES_DA_PASTA, ids=[m[0] for m in MUTACOES_DA_PASTA])
def test_arquivo_trocado_em_entrega_depois_da_entrega_e_detectado(entregue, nome, mexer, chave):
    mexer(entregue / 'entrega')
    s = validar.conferir_entrega(entregue)
    assert not s['ok'] and s[chave], (nome, s)


def test_mutacoes_da_pasta_detectadas_em_100_por_cento(tmp_path, pessoa):
    detectadas = 0
    for k, (_nome, mexer, _chave) in enumerate(MUTACOES_DA_PASTA):
        pasta = tmp_path / ('m%02d' % k)
        _entregar(pasta, _itens_de([_limpo(1), _byte_acima()]))
        assert validar.conferir_entrega(pasta)['ok']
        mexer(pasta / 'entrega')
        detectadas += not validar.conferir_entrega(pasta)['ok']
    assert detectadas == len(MUTACOES_DA_PASTA)


def _foto(pasta):
    """Cada caminho da pasta com o sha256 (arquivo) e o mtime: qualquer gravacao muda a foto."""
    return {p.relative_to(pasta).as_posix(): (p.is_file() and arquivos.sha256_arquivo(p), p.stat().st_mtime_ns)
            for p in pasta.rglob('*')}


def test_conferir_entrega_so_le_e_roda_sem_o_console_do_da(entregue, monkeypatch):
    (entregue / 'estado.json').write_text('{}', encoding='utf-8')
    antes = _foto(entregue)
    monkeypatch.setattr(humano, 'console_interativo', lambda: (False, 'sem_terminal'))
    assert 'conferir-entrega' not in humano.COMANDOS
    assert cli.principal(['conferir-entrega', '--job', str(entregue)]) == 0
    _trocar_arquivo(entregue / 'entrega')
    meio = _foto(entregue)
    assert cli.principal(['conferir-entrega', '--job', str(entregue)]) == int(Codigo.RECUSADO)
    assert _foto(entregue) == meio and set(meio) == set(antes)
