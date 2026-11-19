# -*- coding: utf-8 -*-
"""Silhueta das bases: o preparo que grava a forma de cada camada que sangra (decisao 199, 3; etapa E3 do desenho).

A familia confere as relacoes do layout aprovado (a assinatura livre da tinta do azul, o texto dentro dela) pelo
desenho da forma, com a diagonal, e nunca so pela caixa. O desenho sai do alfa do asset que o leitor ja grava
(laudo/assets/<sha256>.png; com mascara raster ativa, o alfa visivel, alfa_visivel_sha256, como o design system faz
na caixa do sujeito), reduzido a uma grade:
  - ds.silhueta_celulas celulas no lado longo do asset (nunca mais celulas que pixels), o outro lado na mesma medida;
  - a celula tem tinta quando ao menos metade dos pixels dela chega ao limiar ds.sujeito_limiar_alfa.
Entram as camadas visiveis com asset, menos o texto, cuja tinta encosta numa borda do documento ou de uma prancheta
(a base que sangra; a forma solta nao tem relacao de fundo na familia).

O alfa e decodificado so no processo filho isolado (desdobra.ds.silhueta_filho), com o mesmo isolador e o mesmo gancho
de auditoria do leitor e da cor: o processo principal so le o JSON que o filho grava. Nada aqui abre PSD, smart object
ou arquivo linkado. Grava um JSON por sha256 do alfa lido (silhueta/1) em ds/silhuetas/, com as camadas que usam o
asset e a caixa do asset no documento. A derivacao le so esses JSON (desdobra.derivacao.silhueta.carregar).

Sem isolador (Mac, sistema sem suporte), com o filho parado por memoria, tempo ou erro, ou com o asset ausente, a
camada fica sem silhueta, e a forma e conferida pela caixa, com o aviso "forma conferida pela caixa". O alarme do
gancho de auditoria nunca vira so aviso: levanta ErroAuditoriaSilhueta, e a fase ds para com o codigo de auditoria.
"""
import json
import shutil
from pathlib import Path

from desdobra import __version__, arquivos, contratos, limites

ESQUEMA = 'silhueta/1'
PASTA = Path('ds') / 'silhuetas'
MODULO_FILHO = 'desdobra.ds.silhueta_filho'
ARQUIVO_PEDIDO = 'pedido.json'
TIPOS_SEM_SILHUETA = ('type',)  # o texto e conteudo: a tinta dele nunca e fundo de outro elemento
ORIGEM_ALFA_VISIVEL = 'alfa_visivel_com_mascara'
ORIGEM_ALFA_CAMADA = 'alfa_da_camada'
MOTIVO_FILHO = {
    'memoria': 'o preparo da silhueta no processo isolado passou do orçamento de memória',
    'tempo': 'o preparo da silhueta no processo isolado passou do tempo máximo',
    'queda': 'o processo isolado do preparo da silhueta caiu',
    'plataforma': 'o isolamento do processo do preparo da silhueta não está disponível neste sistema',
    'bug': 'o processo isolado do preparo da silhueta terminou com erro interno',
}


class ErroAuditoriaSilhueta(Exception):
    """O gancho de auditoria barrou uma acao do filho da silhueta."""


# ------------------------------------------------------------------ a grade (funcao pura)
def dimensoes_da_grade(largura, altura, celulas):
    """(colunas, linhas) da grade: celulas no lado longo, sem passar do numero de pixels; o lado curto na mesma medida,
    arredondado para cima."""
    largura, altura, celulas = int(largura), int(altura), int(celulas)
    longo, curto = max(largura, altura), min(largura, altura)
    n = max(1, min(celulas, longo))
    m = max(1, min(curto, -(-curto * n // longo)))
    return (n, m) if largura >= altura else (m, n)


def grade_do_alfa(alfa, celulas, limiar):
    """{'colunas', 'linhas', 'celulas'} do alfa (matriz uint8, altura x largura): uma linha de texto por linha da grade,
    de cima para baixo, '1' na celula com tinta e '0' sem. A celula vai de (i x largura) // colunas a ((i + 1) x
    largura) // colunas, em inteiros: a mesma entrada da a mesma grade."""
    import numpy as np
    alfa = np.asarray(alfa)
    h, w = alfa.shape[:2]
    colunas, linhas = dimensoes_da_grade(w, h, celulas)
    tinta = (alfa >= int(limiar)).astype(np.int32)
    xs = [(i * w) // colunas for i in range(colunas + 1)]
    ys = [(j * h) // linhas for j in range(linhas + 1)]
    # soma por faixa de linhas e depois por faixa de colunas (reduceat nos inicios de cada celula)
    por_linha = np.add.reduceat(tinta, ys[:-1], axis=0)
    contagem = np.add.reduceat(por_linha, xs[:-1], axis=1)
    areas = np.outer(np.diff(ys), np.diff(xs))
    cheia = 2 * contagem >= areas  # numero-neutro: ao menos metade da celula (2 x contagem >= area)
    return {'colunas': int(colunas), 'linhas': int(linhas),
            'celulas': [''.join('1' if v else '0' for v in linha) for linha in cheia.tolist()]}


# ------------------------------------------------------------------ as camadas que entram
def _quadros(estrutura):
    doc = estrutura['documento']
    qs = [[0, 0, int(doc['largura']), int(doc['altura'])]]
    for p in doc.get('pranchetas') or []:
        c = p.get('caixa')
        if c and c[2] > c[0] and c[3] > c[1]:
            qs.append([int(v) for v in c])
    return qs


def _encosta(caixa, quadros, tol):
    """A tinta encosta numa borda (ou passa dela) de algum quadro que ela toca."""
    for q in quadros:
        if caixa[2] <= q[0] or caixa[0] >= q[2] or caixa[3] <= q[1] or caixa[1] >= q[3]:
            continue
        if caixa[0] <= q[0] + tol or caixa[1] <= q[1] + tol or caixa[2] >= q[2] - tol or caixa[3] >= q[3] - tol:
            return True
    return False


def candidatas(estrutura):
    """{sha256 do alfa: {'origem_alfa', 'dims', 'camadas': [{'layer_id', 'caixa_asset'}]}} das camadas da estrutura
    bruta do documento que ganham silhueta, na ordem das camadas."""
    tol = float(limites.valor('derivacao.enquadramento_tolerancia_px'))
    quadros = _quadros(estrutura)
    saida = {}
    for reg in estrutura.get('camadas') or []:
        px = reg.get('pixels') or {}
        sha = px.get('asset_sha256')
        tinta = reg.get('caixa_tinta')
        if not sha or not tinta or not reg.get('visivel_efetiva') or reg.get('kind') in TIPOS_SEM_SILHUETA:
            continue
        if px.get('origem') != 'pixels_proprios' or not px.get('asset_dims'):
            continue
        if not _encosta(tinta, quadros, tol):
            continue
        sha_alfa = px.get('alfa_visivel_sha256') or sha
        caixa = reg.get('caixa') or [0, 0, 0, 0]
        w, h = (int(v) for v in px['asset_dims'])
        item = saida.setdefault(sha_alfa, {'origem_alfa': ORIGEM_ALFA_VISIVEL if px.get('alfa_visivel_sha256')
                                           else ORIGEM_ALFA_CAMADA, 'dims': [w, h], 'camadas': []})
        item['camadas'].append({'layer_id': int(reg['layer_id']),
                                'caixa_asset': [int(caixa[0]), int(caixa[1]), int(caixa[0]) + w, int(caixa[1]) + h]})
    return saida


# ------------------------------------------------------------------ o preparo no processo filho
def hash_do_preparo():
    """sha256 do que decide a grade gravada: o esquema e os limites ds.silhueta_celulas e ds.sujeito_limiar_alfa.
    Entra como externa na fase ds (revisao da 0.10.0): o job preparado antes da 0.10.0 nunca gravou ds/silhuetas, e a
    fase ds dele ficava valida pelo hash das entradas, sem o preparo rodar nunca. Com a externa, a fase fica
    desatualizada uma vez, e o job proxima a refaz com as silhuetas; o mesmo vale quando a grade muda de medida."""
    import hashlib
    usados = {'esquema': ESQUEMA, 'celulas': limites.valor('ds.silhueta_celulas'),
              'limiar': limites.valor('ds.sujeito_limiar_alfa')}
    return hashlib.sha256(json.dumps(usados, sort_keys=True).encode('utf-8')).hexdigest()


def orcamento_filho(bytes_max, px_max):
    """(isolador.base_python_bytes + isolador.fator_abertura_max x bytes do maior PNG + isolador.bytes_por_px_canvas
    x pixels do maior asset) x isolador.margem_orcamento: o filho decodifica um asset por vez."""
    base = limites.valor('isolador.base_python_bytes')
    fator = limites.valor('isolador.fator_abertura_max')
    por_px = limites.valor('isolador.bytes_por_px_canvas')
    margem = limites.valor('isolador.margem_orcamento')
    return int((base + fator * int(bytes_max) + por_px * int(px_max)) * margem)


def preparar(pasta_job, estrutura, *, plat=None):
    """Grava ds/silhuetas/<sha256>.json de cada camada candidata, pelo filho isolado. Apaga as silhuetas de antes.
    Devolve {'pedidas', 'gravadas', 'sem_silhueta': [{'sha256', 'motivo'}], 'motivo'}; levanta ErroAuditoriaSilhueta
    no alarme do gancho de auditoria."""
    from desdobra import plataforma
    pasta_job = Path(pasta_job).resolve()
    destino = pasta_job / PASTA
    shutil.rmtree(destino, ignore_errors=True)
    pedidas = candidatas(estrutura)
    resumo = {'pedidas': len(pedidas), 'gravadas': 0, 'sem_silhueta': [], 'motivo': None}
    if not pedidas:
        return resumo
    pasta_assets = pasta_job / 'laudo' / 'assets'
    presentes = {}
    for sha in pedidas:
        caminho = pasta_assets / ('%s.png' % sha)
        if caminho.is_file():
            presentes[sha] = caminho.stat().st_size
        else:
            resumo['sem_silhueta'].append({'sha256': sha, 'motivo': 'asset ausente no laudo'})
    if not presentes:
        return resumo
    plat = plat or plataforma.obter()
    raiz = pasta_job / 'ds' / '.trabalho-silhueta'
    shutil.rmtree(raiz, ignore_errors=True)
    saida, trabalho = raiz / 'saida', raiz / 'trabalho'
    saida.mkdir(parents=True)
    trabalho.mkdir(parents=True)
    pedido = raiz / ARQUIVO_PEDIDO
    pedido.write_text(json.dumps({'celulas': int(limites.valor('ds.silhueta_celulas')),
                                  'limiar': int(limites.valor('ds.sujeito_limiar_alfa')),
                                  'itens': [{'sha256': s, 'dims': pedidas[s]['dims']} for s in presentes]}),
                      encoding='utf-8')
    px_max = max(pedidas[s]['dims'][0] * pedidas[s]['dims'][1] for s in presentes)
    orc = orcamento_filho(max(presentes.values()), px_max)
    cmd = [str(plat.interpretador()), '-I', '-B', '-m', MODULO_FILHO, str(pedido), str(pasta_assets), str(saida),
           '--orcamento-bytes', str(orc)]
    try:
        r = plat.executar_isolado(cmd, orc, float(limites.valor('isolador.tempo_max_s')), trabalho)
        auditoria = _ler_auditoria(saida)
        if auditoria:
            raise ErroAuditoriaSilhueta('o gancho de auditoria barrou uma ação do processo do preparo da silhueta')
        lidas = {}
        if r.situacao == 'ok' and r.codigo == 0:
            for sha in presentes:
                arq = saida / ('%s.json' % sha)
                try:
                    dados = contratos.ler(arq, ESQUEMA)
                except contratos.ErroContrato:
                    continue
                if dados['sha256'] == sha:
                    lidas[sha] = dados
        else:
            resumo['motivo'] = MOTIVO_FILHO['plataforma' if r.situacao == 'recusado' else
                                            r.situacao if r.situacao in MOTIVO_FILHO else 'bug']
    finally:
        shutil.rmtree(raiz, ignore_errors=True)
    sha_kv = (estrutura.get('origem') or {}).get('sha256')
    for sha in presentes:
        dados = lidas.get(sha)
        if dados is None:
            resumo['sem_silhueta'].append({'sha256': sha, 'motivo': resumo['motivo'] or 'asset ilegível no preparo'})
            continue
        dados.update(arquivo_sha256=sha_kv, origem_alfa=pedidas[sha]['origem_alfa'], camadas=pedidas[sha]['camadas'],
                     motor=__version__)
        contratos.gravar(destino / ('%s.json' % sha), dados, ESQUEMA)
        resumo['gravadas'] += 1
    return resumo


def _ler_auditoria(saida):
    arq = Path(saida) / 'auditoria.json'
    if not arq.is_file():
        return False
    try:
        dados = arquivos.ler_json(arq)
    except (OSError, ValueError):
        return True
    return bool(dados.get('bloqueios')) or dados.get('recusa') == 'auditoria'
