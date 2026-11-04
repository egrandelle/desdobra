# -*- coding: utf-8 -*-
"""Avaliacao do KV C (03/11; decisoes-v1.md, 131 a 134), escrita antes do codigo.

131 o teto de memoria das pilhas pela area do documento (o 300x600 parou por teto calculado pelo formato) e
render/<formato>/parada.json em toda parada; 132 forca forte "escala de conteudo >= 0,9 x regra" (o Globo 1080x1920
saiu com texto e marca a 1%); 133 piso obrigatorio de 0,5 x regra, que devolve com nome e fonte; 134 a decisao de
largura so dos textos desenhados, um item por camada.
"""
import json
import shutil
import sys

import pytest

import test_derivacao_apoio as ap
from desdobra import limites
from desdobra.derivacao import nucleo as nd
from test_derivacao_blocos import camada
from test_derivacao_job import job_der  # noqa: F401  (fixture do job sintetico)

# a pilha da mestre do KV C (tela 3), em numeros: textos e logos de 157 a 1853, numa folha com area segura de
# 250 a 1670 (13% em cima e embaixo)
CAIXAS = {51: [79, 1722, 192, 1853], 52: [299, 1765, 426, 1852], 53: [536, 1759, 1005, 1851], 54: [75, 1617, 1006, 1653],
          56: [73, 157, 889, 504], 59: [75, 989, 390, 1083], 60: [75, 1201, 439, 1359], 158: [73, 642, 827, 822]}
FUNCOES = {1: 'fundo', 51: 'logo_de_parceiro', 52: 'logo_de_parceiro', 53: 'logo_de_parceiro', 54: 'cta',
           56: 'texto_de_apoio', 59: 'logo_de_parceiro', 60: 'informacao_de_evento', 158: 'texto_de_apoio'}
ANCORAS = {51: ('esquerda', 'base'), 52: ('centro', 'base'), 53: ('direita', 'base'), 54: ('centro', 'base'),
           56: ('centro', 'topo'), 59: ('esquerda', 'meio'), 60: ('esquerda', 'meio'), 158: ('centro', 'meio'),
           1: ('centro', 'meio')}
TEXTOS = (54, 56, 60, 158)


def _globo(segura_pct=13.0):
    camadas = [camada(1, 'pixel', [0, 0, 1080, 1920])]
    for lid, c in sorted(CAIXAS.items()):
        camadas.append(camada(lid, 'texto' if lid in TEXTOS else 'smart_embutido', c, corpo=40))
    regras = {f: ('cover' if f == 'fundo' else 'raiz_area') for f in set(FUNCOES.values())}
    chave = 'teste|globo|1080x1920'
    specs = {chave: ap.spec(chave, {'area_segura': {'pct': segura_pct, 'px': None, 'lados': ['superior', 'inferior']}})}
    b = ap.briefing(funcoes=FUNCOES, regras=regras, ancoras={}, formatos=[ap.formato('globo', 1080, 1920, chave=chave)])
    b['ancoras'] = [{'layer_id': k, 'x': ap.decisao(x), 'y': ap.decisao(y)} for k, (x, y) in sorted(ANCORAS.items())]
    return nd.derivar_em_memoria(nd.contexto(ap.laudo(1080, 1920, camadas), b), specs=specs)['formatos']['globo']


# ------------------------------------------------------------------ 132 e 133
def test_132_conteudo_nao_encolhe_para_cumprir_alinhamento():
    d = _globo()
    assert d['situacao'] == 'derivado', d['devolucao']
    # com a distancia entre linhas (135), forte como ela, o conteudo pode ficar um pouco abaixo de 0,9 da regra; o que
    # nao pode e encolher a quase nada (antes, 0,01)
    for e in d['elementos']:
        if e['classe'] in ('texto', 'marca'):
            assert e['escala'] >= 0.75 * e['escala_regra'], (e['id'], e['escala'], e['escala_regra'])
    assert any(x['nome'].startswith('escala_de_conteudo:') and x['forca'] == 'forte' for x in d['restricoes'])


def test_133_piso_de_conteudo_que_nao_fecha_devolve_com_nome_e_fonte():
    # area segura de 40% em cima e embaixo: 384 px para uma pilha de 946 px de altura somada; nem com 0,5 fecha
    d = _globo(segura_pct=40.0)
    assert d['situacao'] == 'devolvido', d['elementos']
    r = d['devolucao']['restricao'] or {}
    assert d['devolucao']['motivo'] == 'restricao_obrigatoria_nao_fecha' and r['nome'].startswith('escala_minima_de_conteudo'), r
    assert r['fonte'] == {'tipo': 'limite', 'ref': 'derivacao.escala_conteudo_min_da_regra'}
    lim = limites.obter('derivacao.escala_conteudo_min_da_regra')
    assert lim.valor == 0.5 and lim.fonte and lim.situacao == 'a_calibrar'


# ------------------------------------------------------------------ 131
def _copia_com_formato_pequeno(job_der, tmp_path):
    from desdobra.briefing import modelo as mb
    job = tmp_path / 'copia'
    shutil.copytree(job_der['job'], job)
    shutil.rmtree(job / 'render', ignore_errors=True)  # sem cache de pilhas
    b = json.loads(job_der['fixture'].read_text(encoding='utf-8'))
    b['formatos'] = b['formatos'] + [ap.formato('mini', 160, 80)]
    arq = tmp_path / 'fixture-mini.json'
    arq.write_text(json.dumps(b), encoding='utf-8')
    mb.importar_teste(job, arq)
    nd.derivar(job)
    return job


@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
def test_131_teto_das_pilhas_pela_area_do_documento(job_der, tmp_path, pessoa, monkeypatch):
    from desdobra import leitor
    from desdobra.render import execucao
    job = _copia_com_formato_pequeno(job_der, tmp_path)
    tetos = []
    original = execucao._rodar

    def espiao(plat, cmd, orc, *a, **k):
        if execucao.MODULO_PILHAS in cmd:
            tetos.append(orc)
        return original(plat, cmd, orc, *a, **k)
    monkeypatch.setattr(execucao, '_rodar', espiao)
    getattr(execucao, 'renderizar')(job, disparo=pessoa.exigir('render'), formato='mini')
    kv = job / 'entrada' / 'kv.psd'
    assert tetos == [leitor.orcamento_bytes(kv.stat().st_size, 320 * 160)]


@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
def test_131_parada_grava_o_motivo_na_pasta_do_formato(job_der, tmp_path, pessoa, monkeypatch):
    from desdobra.render import execucao

    class Falha:
        situacao, codigo, pico_bytes = 'memoria', None, 123
    original = execucao._rodar
    monkeypatch.setattr(execucao, '_rodar', lambda plat, cmd, *a, **k:
                        Falha() if execucao.MODULO_PILHAS in cmd else original(plat, cmd, *a, **k))
    job = _copia_com_formato_pequeno(job_der, tmp_path)
    with pytest.raises(execucao.ErroRender) as e:
        getattr(execucao, 'renderizar')(job, disparo=pessoa.exigir('render'), formato='mini')
    assert e.value.motivo == 'pilhas_memoria'
    parada = json.loads((job / 'render' / 'mini' / 'parada.json').read_text(encoding='utf-8'))
    assert parada['motivo'] == 'pilhas_memoria' and parada['codigo'] == int(e.value.codigo)
    assert parada['medidas'] == {'pico_bytes': 123} and not (job / 'render' / 'mini' / 'master.png').exists()


# ------------------------------------------------------------------ 134
@pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')
def test_134_decisao_de_largura_um_item_por_camada(job_der, tmp_path):
    from desdobra.render import contrato as mc
    job = tmp_path / 'copia2'
    shutil.copytree(job_der['job'], job)
    arq = job / 'fontes' / 'conferencia.json'
    conf = json.loads(arq.read_text(encoding='utf-8'))
    alvo = job_der['ids']['texto-apoio']
    item = next(c for c in conf['camadas'] if c['layer_id'] == alvo)
    item['motivos'] = [{'codigo': 'largura_divergente', 'situacao': 'bloqueante', 'descricao': 'sintetico'}]
    item['largura_erro_pct'] = -1.0
    conf['camadas'].append(dict(item, nome_ps='Outra-Face', largura_erro_pct=-0.5))
    arq.write_text(json.dumps(conf), encoding='utf-8')
    _c, _b, confirmar = mc.montar(job)
    camadas = next(x for x in confirmar if x['codigo'] == 'largura_divergente')['medidas']['camadas']
    assert [c['layer_id'] for c in camadas] == [alvo] and camadas[0]['erro_pct'] == -1.0


# ------------------------------------------------------------------ 135
def _gap(d, a, b):
    el = {e['id']: e for e in d['elementos']}
    return el[b]['caixa'][1] - el[a]['caixa'][3], el[a]['escala']


def test_135_distancia_entre_linhas_de_conteudo_fica_proporcional():
    """Globo 1080x1920 (03/11): o cta (base em 1653 na mestre) e a linha de logos (topo em 1722) ficaram encostados
    (-1 px) para o conteudo caber na area segura com escala 0,9."""
    d = _globo()
    assert d['situacao'] == 'derivado', d['devolucao']
    gap, s = _gap(d, 'el54', 'el51')
    # a forca forte pede a distancia inteira na escala; com ela fraca, a distancia cairia no piso (metade)
    assert gap >= 0.9 * s * 69 - 0.5, (gap, s)
    nomes = {x['nome'].split(':')[0]: x['forca'] for x in d['restricoes'] if 'distancia' in x['nome']}
    assert nomes.get('distancia_entre_conteudo') == 'forte' and nomes.get('distancia_minima_entre_conteudo') == 'obrigatoria'
    lim = limites.obter('derivacao.distancia_entre_linhas_min')
    assert lim.valor == 0.5 and lim.fonte and lim.situacao == 'a_calibrar'


def test_135_piso_da_distancia_que_nao_fecha_devolve_com_nome_e_fonte():
    # dois textos com 235 px entre eles na mestre de 400x300, num formato de 800x80: o piso de escala de conteudo
    # (metade da regra) cabe, a metade da distancia nao
    camadas = [camada(1, 'pixel', [0, 0, 400, 300]), camada(10, 'texto', [20, 10, 220, 40], corpo=30),
               camada(20, 'texto', [20, 275, 220, 290], corpo=15)]
    b = ap.briefing(funcoes={1: 'fundo', 10: 'titulo', 20: 'texto_de_apoio'},
                    regras={'fundo': 'cover', 'titulo': 'constante', 'texto_de_apoio': 'constante'},
                    formatos=[ap.formato('fino', 800, 80)], familias={'faixa': ap.decisao(10.0)})
    d = nd.derivar_em_memoria(nd.contexto(ap.laudo(400, 300, camadas), b), specs={})['formatos']['fino']
    assert d['situacao'] == 'devolvido', [(e['id'], e['caixa']) for e in d['elementos']]
    r = d['devolucao']['restricao'] or {}
    assert d['devolucao']['motivo'] == 'restricao_obrigatoria_nao_fecha', d['devolucao']
    assert r['nome'].startswith('distancia_minima_entre_conteudo'), r
    assert r['fonte'] == {'tipo': 'limite', 'ref': 'derivacao.distancia_entre_linhas_min'}


def test_135_vizinho_mais_perto_so_entre_conteudo_sem_explosao_de_pares():
    d = _globo()
    pares = [x['elementos'] for x in d['restricoes'] if x['nome'].startswith('distancia_minima_entre_conteudo')]
    assert pares and not any('el1' in p for p in pares)
    # um vizinho por eixo e por elemento, no maximo: nunca todos os pares
    assert len(pares) <= 2 * 8
