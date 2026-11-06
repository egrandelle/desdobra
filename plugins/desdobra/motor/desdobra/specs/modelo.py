# -*- coding: utf-8 -*-
"""Modelo de spec em 4 niveis (spec/1): folha, veiculador, circuito e formato (arquitetura-v1.md, 4.8 e 5.5).

Funcoes puras: recebem as leituras do filho (leitura-folha/1), as propostas de mapeamento (do Claude ou da
biblioteca) e as acoes do DA, e devolvem o documento spec/1. Nada aqui le arquivo nem chama o modelo.

Regras:
  - todo valor carrega forma, valor, texto original, numeros literais, unidade normalizada, base da unidade, fonte
    (folha, pagina, trecho, recorte), origem e situacao (rascunho, confirmado ou registro);
  - o numero sai do texto literal do trecho (desdobra.specs.extrair); a proposta de mapeamento so diz qual trecho
    vai para qual campo, e o motor extrai o numero do trecho;
  - campo ausente vira registro sem valor (valor_ausente), nunca um valor;
  - nenhum valor fica confirmado sem uma acao do DA (aplicar_acoes, que so o "spec confirmar" grava);
  - a chave do formato junta veiculador, circuito, largura e altura;
  - a divergencia entre fontes (o peso por tag do Half-Page) fica com as duas leituras e valor nulo: o motor nao
    escolhe, e o DA decide.
"""
import hashlib
import json
import re

from desdobra import limites
from desdobra.specs import extrair

ESQUEMA = 'spec/1'
NIVEIS = ('folha', 'veiculador', 'circuito', 'formato')
# campo -> (niveis, extrator, condicao do peso, so registro)
CAMPOS = {
    'versao_impressa': (('folha',), 'texto', None, False),
    'data_impressa': (('folha',), 'texto', None, False),
    'nome': (('veiculador',), 'texto', None, False),
    'apelidos': (('veiculador',), 'lista', None, False),
    'concessionaria': (('veiculador',), 'texto', None, False),
    'prazo_envio': (('veiculador',), 'texto', None, True),
    'ambiente': (('circuito',), 'texto', None, False),
    'praca': (('circuito',), 'praca', None, False),
    'modelo_tela': (('circuito',), 'texto', None, False),
    'faixas_reservadas': (('circuito',), 'faixa', None, False),
    'restricao': (('circuito',), 'texto', None, False),
    'dimensao': (('formato',), 'dimensao', None, False),
    'orientacao_painel': (('formato',), 'texto', None, False),
    'rotacao': (('formato',), 'texto', None, True),
    'area_util': (('circuito', 'formato'), 'area_util', None, False),
    'faixas': (('formato',), 'faixa', None, False),
    'area_segura': (('formato',), 'area_segura', None, False),
    'borda_1px': (('veiculador', 'formato'), 'borda', None, False),
    'peso_max': (('veiculador', 'formato'), 'peso', None, False),
    'peso_max_hospedado': (('veiculador', 'formato'), 'peso', 'hospedado', False),
    'peso_max_tag': (('veiculador', 'formato'), 'peso', 'por_tag', False),
    'peso_max_tag_carga_inicial': (('formato',), 'peso', 'tag_carga_inicial', False),
    'peso_max_tag_carga_posterior': (('formato',), 'peso', 'tag_carga_posterior', False),
    'tipos_aceitos': (('veiculador', 'formato'), 'tipos', None, False),
    'qualidade_jpg_recomendada': (('veiculador', 'formato'), 'porcentagem', None, True),
    'area_visivel': (('formato',), 'area_visivel', None, False),
    'sangria': (('formato',), 'medida', None, False),
    'margem_seguranca': (('formato',), 'medida', None, False),
    'sufixo_nome_arquivo': (('formato',), 'texto', None, False),
}
# o que o DA pode digitar ao lado do recorte: os campos que valem (o so registro fica fora)
CAMPOS_DIGITAVEIS = tuple(sorted(c for c, d in CAMPOS.items() if not d[3]))  # numero-neutro: posicao do so registro na tupla
CAMPOS_DO_NIVEL = {n: tuple(c for c, d in CAMPOS.items() if n in d[0] and c != 'restricao') for n in NIVEIS}
# formato sem o campo herda do circuito ou do veiculador (arquitetura 4.8, modelo com heranca)
HERANCA = {'area_util': ('circuito', 'area_util'), 'faixas': ('circuito', 'faixas_reservadas'),
           'peso_max': ('veiculador', 'peso_max'), 'peso_max_hospedado': ('veiculador', 'peso_max_hospedado'),
           'peso_max_tag': ('veiculador', 'peso_max_tag'), 'tipos_aceitos': ('veiculador', 'tipos_aceitos'),
           'borda_1px': ('veiculador', 'borda_1px'),
           'qualidade_jpg_recomendada': ('veiculador', 'qualidade_jpg_recomendada')}

# Rotulos que a folha usa, sobre o texto normalizado (minusculas, sem acento). O rotulo so vale quando o resto do
# trecho comeca com um valor (ou esta vazio e o valor vem em outro trecho, como no PDF da PME). Os rotulos de texto
# livre (ambiente, praca, veiculador) pedem dois pontos ou cabecalho de coluna.
_VALOR_A_SEGUIR = r'(?=\s*(?:$|:|\d|-|–|ate\b|maximo\b|max\b|no maximo|jpe?g|png|gif|html|mp4|pdf|webp))'
ROTULOS = (
    (r'formato \(area total\)', 'dimensao'),
    (r'(?:dimensao|dimensoes|tamanho do criativo|tamanhos?|sizes(?: \(pixels\))?|resolucao)', 'dimensao'),
    (r'area util', 'area_util'),
    (r'area visivel', 'area_visivel'),
    (r'margem de seguranca', 'margem_seguranca'),
    (r'sangria', 'sangria'),
    (r'area segura', 'area_segura'),
    (r'(?:barra|faixa) (?:inferior|superior|lateral|esquerda|direita)', 'faixas'),
    (r'peso \(hosted\)|peso hospedado', 'peso_max_hospedado'),
    (r'peso \(tag\)|peso por tag', 'peso_max_tag'),
    (r'peso maximo initial load(?: \(kb\))?|carga inicial(?: \(kb\))?', 'peso_max_tag_carga_inicial'),
    (r'peso maximo subload(?: \(kb\))?|carga posterior(?: \(kb\))?', 'peso_max_tag_carga_posterior'),
    (r'(?:peso maximo|peso do arquivo|peso|tamanho do arquivo|tamanho maximo)(?: \([^)]*\))?', 'peso_max'),
    (r'(?:arquivos permitidos|tipos? de arquivo|tipos aceitos|extensao|formatos?)', 'tipos_aceitos'),
    (r'largura(?: \([^)]*\))?', 'largura'),
    (r'altura(?: \([^)]*\))?', 'altura'),
)
ROTULOS_TEXTO = (
    (r'circuito|ambiente', 'ambiente'), (r'praca|pracas|cidade', 'praca'), (r'modelo de tela', 'modelo_tela'),
    (r'veiculador|veiculo', 'nome'), (r'concessionaria', 'concessionaria'),
    (r'sufixo(?: do nome do arquivo)?', 'sufixo_nome_arquivo'), (r'prazo(?: de envio)?', 'prazo_envio'),
    (r'versao', 'versao_impressa'), (r'data', 'data_impressa'), (r'orientacao', 'orientacao_painel'),
)
_RE_ROTULOS = [(re.compile(r'^\s*(?:%s)%s' % (r, _VALOR_A_SEGUIR)), c) for r, c in ROTULOS]
_RE_ROTULOS_TEXTO = [(re.compile(r'^\s*(?:%s)\s*:' % r), c) for r, c in ROTULOS_TEXTO]
_RE_ROTULOS_COLUNA = [(re.compile(r'^\s*(?:%s)\b' % r), c) for r, c in ROTULOS + ROTULOS_TEXTO]
SECOES_FORA = ('video', 'videos', 'audio')  # trecho de video ou audio nao vira valor da peca estatica
SECOES_DENTRO = ('imagem', 'imagens')


def _norm_1a1(texto):
    """Texto normalizado com o mesmo comprimento do original (cada caractere vira um), para cortar o valor no
    texto original na mesma posicao em que o rotulo terminou no normalizado."""
    import unicodedata
    saida = []
    for c in texto:
        base = ''.join(x for x in unicodedata.normalize('NFKD', c) if not unicodedata.combining(x))
        saida.append((base[:1] or c).lower() if base else c.lower())
    return ''.join(saida)


def slug(texto):
    n = extrair.normalizar(texto)
    return re.sub(r'[^a-z0-9]+', '-', n).strip('-') or 'sem-nome'


def tem_segredo(texto):
    from desdobra.sugestao import segredos
    return bool(texto) and segredos.detector_padrao().tem_segredo(texto)


def slug_seguro(texto):
    """Slug para id (circuito, veiculador): texto com segredo nunca vira id, que sai no pacote do Claude; no lugar
    entra um id neutro, o comeco do sha256 do texto."""
    if tem_segredo(texto):
        return 'oculto-' + hashlib.sha256(texto.encode('utf-8')).hexdigest()[:8]  # numero-neutro: id curto
    return slug(texto)


def numero_no_texto(literal, texto):
    """True quando o numero literal esta no texto com fronteira: "5" nao vale dentro de "15" nem de "1,5"."""
    return re.search(r'(?<![\d.,])%s(?![\d]|[.,]\d)' % re.escape(literal), texto or '') is not None


def corte_com_fronteira(corte, texto):
    """True quando o pedaco literal esta no texto sem partir palavra nem numero ("080x192" dentro de "1080x1920" e
    "5 MB" dentro de "15 MB" nao valem)."""
    if not corte or not corte.strip():
        return False
    for m in re.finditer(re.escape(corte), texto or ''):
        antes, depois = texto[:m.start()], texto[m.end():]
        ruim_antes = antes[-1:].isalnum() or (antes[-1:] in '.,' and antes[-2:-1].isdigit() and antes[-1:] != '')
        ruim_depois = depois[:1].isalnum() or (depois[:1] in '.,' and depois[1:2].isdigit() and depois[:1] != '')
        if not ruim_antes and not ruim_depois:
            return True
    return False


def impressao(valor):
    """sha256 do conteudo de um valor (o que o DA confirmou). Mudou a folha, muda a impressao, e a confirmacao
    antiga deixa de valer."""
    base = {'valor': valor.get('valor'), 'texto_original': valor.get('texto_original'),
            'numeros_literais': valor.get('numeros_literais'), 'unidade': valor.get('unidade'),
            'fonte': valor.get('fonte'), 'leituras': [(x.get('valor'), x.get('fonte')) for x in valor.get('leituras') or []]}
    return hashlib.sha256(json.dumps(base, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


# ------------------------------------------------------------------ valores
def valor_ausente(ident, campo):
    """Campo que a folha nao traz: registro sem valor. Nunca um valor (teste de propriedade)."""
    return {'id': ident, 'campo': campo, 'forma': None, 'valor': None, 'texto_original': None, 'numeros_literais': [],
            'unidade': None, 'unidade_original': None, 'base_unidade': None, 'condicao': None, 'fonte': None,
            'origem': 'ausente', 'mapeamento': None, 'situacao': 'registro', 'alertas': [], 'confirmacao': None}


def fonte(folha, trecho, rotulo_trecho=None, recorte=None, recorte_texto=None):
    return {'folha': folha, 'pagina': trecho['pagina'] if trecho else None, 'trecho': trecho['id'] if trecho else None,
            'rotulo_trecho': rotulo_trecho['id'] if rotulo_trecho else None, 'recorte': recorte,
            'secao': trecho.get('secao') if trecho else None, 'recorte_texto': recorte_texto}


def valor_do_trecho(ident, campo, trecho, folha_id, *, rotulo_trecho=None, mapeamento='rotulo_da_folha',
                    recorte_texto=None, alertas_extra=()):
    """Extrai o valor do texto literal do trecho (ou de um pedaco literal dele) com o extrator do campo."""
    _niveis, nome_extrator, condicao, so_registro = CAMPOS[campo]
    texto = recorte_texto if recorte_texto is not None else trecho['texto_valor']
    rotulo = trecho.get('rotulo') or (rotulo_trecho['texto'] if rotulo_trecho else None)
    if nome_extrator == 'peso':
        lei = extrair.peso(texto, rotulo, condicao)
    else:
        lei = extrair.EXTRATORES[nome_extrator](texto, rotulo)
    alertas = list(lei['alertas']) + list(alertas_extra)
    if rotulo_trecho is not None and rotulo_trecho['id'] != trecho['id']:
        alertas.append('rotulo_separado_do_valor')
    v = {'id': ident, 'campo': campo, 'forma': lei['forma'], 'valor': lei['valor'], 'texto_original': texto.strip(),
         'numeros_literais': lei['numeros_literais'], 'unidade': lei['unidade'],
         'unidade_original': lei['unidade_original'], 'base_unidade': lei['base_unidade'],
         'condicao': lei['condicao'] or condicao, 'fonte': fonte(folha_id, trecho, rotulo_trecho, recorte_texto=recorte_texto),
         'origem': 'extraido_do_trecho', 'mapeamento': mapeamento,
         'situacao': 'registro' if so_registro else 'rascunho', 'alertas': sorted(set(alertas)), 'confirmacao': None}
    if lei.get('leituras'):
        v['leituras'] = [_leitura_com_fonte(x, v['fonte'], texto) for x in lei['leituras']]
    return v


def _leitura_com_fonte(lei, fonte_, texto):
    return {'valor': lei['valor'], 'forma': lei['forma'], 'texto_original': texto.strip(),
            'numeros_literais': lei['numeros_literais'], 'unidade': lei['unidade'],
            'unidade_original': lei['unidade_original'], 'base_unidade': lei['base_unidade'],
            'condicao': lei['condicao'], 'fonte': fonte_}


def valor_digitado(ident, campo, texto, folha_id, recorte):
    """Valor que o DA digitou ao lado do recorte de uma pagina sem texto. O numero sai do que o DA digitou, pelo
    mesmo extrator, com o recorte como fonte; nunca vem do Claude (so o "spec confirmar" no terminal grava)."""
    trecho = {'id': None, 'pagina': recorte['pagina'], 'texto_valor': texto, 'texto': texto, 'rotulo': None, 'secao': None}
    v = valor_do_trecho(ident, campo, trecho, folha_id, mapeamento='da')
    v['fonte'] = {'folha': folha_id, 'pagina': recorte['pagina'], 'trecho': None, 'rotulo_trecho': None,
                  'recorte': recorte['id'], 'secao': None, 'recorte_texto': None}
    v['origem'] = 'digitado_pelo_da_a_partir_do_recorte'
    v['texto_digitado'] = texto.strip()
    return v


def tem_valor(v):
    return bool(v) and v.get('valor') is not None


def divergencia(atual, novo):
    """Duas fontes para o mesmo campo com valores diferentes: valor nulo e as duas leituras, cada uma com a fonte.
    O motor nao escolhe."""
    leituras = list(atual.get('leituras') or [])
    for v in (atual, novo):
        if v.get('valor') is not None:
            leituras.append({'valor': v['valor'], 'forma': v['forma'], 'texto_original': v['texto_original'],
                             'numeros_literais': v['numeros_literais'], 'unidade': v['unidade'],
                             'unidade_original': v['unidade_original'], 'base_unidade': v['base_unidade'],
                             'condicao': v['condicao'], 'fonte': v['fonte']})
    out = dict(atual)
    out.update(valor=None, leituras=leituras, situacao='rascunho', confirmacao=None,
               alertas=sorted(set(atual['alertas']) | set(novo['alertas']) | {'fontes_divergentes'}))
    return out


def por(novo_valor, alvo, campo):
    """Grava novo_valor em alvo['campos'][campo]: campo vazio recebe; mesmo valor fica; valor diferente diverge."""
    atual = alvo['campos'].get(campo)
    if atual is None or atual['origem'] == 'ausente' or (atual.get('valor') is None and not atual.get('leituras')):
        alvo['campos'][campo] = novo_valor
        return
    if novo_valor.get('valor') is None:
        return
    if atual.get('valor') == novo_valor.get('valor') and not atual.get('leituras'):
        return
    if any(x['valor'] == novo_valor.get('valor') for x in atual.get('leituras') or []):
        return
    alvo['campos'][campo] = divergencia(atual, novo_valor)


# ------------------------------------------------------------------ trechos
def preparar_trechos(folha_id, leitura):
    """Trechos da folha com id estavel (p<pagina>-t<ordem>), na ordem de leitura. No PDF, juntam-se os pedacos que
    o PDFium partiu no meio de uma palavra ("1008px x 432" + "px"): mesma linha, sem espaco entre eles."""
    brutos = [dict(t) for t in leitura['trechos']]
    if leitura['formato'] == 'pdf':
        brutos = _colar_pedacos(brutos)
        brutos.sort(key=lambda t: (t['pagina'], -t['caixa'][3], t['caixa'][0]))
    saida = []
    contagem = {}
    for t in brutos:
        contagem[t['pagina']] = contagem.get(t['pagina'], 0) + 1
        t['id'] = 'p%02d-t%03d' % (t['pagina'], contagem[t['pagina']])
        t['texto'] = ' '.join(t['texto'].split())
        t['folha'] = folha_id
        saida.append(t)
    return saida


def _mesma_linha(a, b):
    return a['caixa'][1] <= b['caixa'][3] and b['caixa'][1] <= a['caixa'][3]


def _colar_pedacos(trechos):
    por_pagina = {}
    for t in trechos:
        por_pagina.setdefault(t['pagina'], []).append(t)
    saida = []
    for pag in sorted(por_pagina):
        itens = sorted(por_pagina[pag], key=lambda t: (-t['caixa'][3], t['caixa'][0]))
        usados = set()
        for i, a in enumerate(itens):
            if i in usados:
                continue
            atual = dict(a)
            while True:
                largura_letra = (atual['caixa'][2] - atual['caixa'][0]) / max(len(atual['texto']), 1)
                seguinte = None
                for j, b in enumerate(itens):
                    if j in usados or j == i or b is a:
                        continue
                    folga = b['caixa'][0] - atual['caixa'][2]
                    if (_mesma_linha(atual, b) and not atual['texto'][-1:].isspace() and
                            -largura_letra <= folga <= largura_letra):
                        seguinte = j
                        break
                if seguinte is None:
                    break
                b = itens[seguinte]
                usados.add(seguinte)
                atual['texto'] = atual['texto'] + b['texto']
                atual['caixa'] = [min(atual['caixa'][0], b['caixa'][0]), min(atual['caixa'][1], b['caixa'][1]),
                                  max(atual['caixa'][2], b['caixa'][2]), max(atual['caixa'][3], b['caixa'][3])]
            usados.add(i)
            saida.append(atual)
    return _colar_continuacoes(saida)


def _sobrepoe_x(a, b):
    return a['caixa'][0] <= b['caixa'][2] and b['caixa'][0] <= a['caixa'][2]


def _colar_continuacoes(trechos):
    """Linha que termina com virgula ou com "e" continua na linha de baixo da mesma coluna ("Rio de Janeiro, Paraná
    e" + "Belo Horizonte"): as duas viram um trecho so, para a praca nao ficar partida."""
    restantes = list(trechos)
    saida = []
    while restantes:
        a = restantes.pop(0)
        while re.search(r'(,|\s(e|ou))\s*$', a['texto']):
            altura = a['caixa'][3] - a['caixa'][1]
            # a linha de baixo: o topo dela abaixo do topo desta, a no maximo uma altura de linha do pe desta
            abaixo = [b for b in restantes if b['pagina'] == a['pagina'] and
                      a['caixa'][1] - altura <= b['caixa'][3] < a['caixa'][3] and _sobrepoe_x(a, b)]
            if not abaixo:
                break
            b = max(abaixo, key=lambda x: x['caixa'][3])
            restantes.remove(b)
            a = dict(a, texto=a['texto'].rstrip() + ' ' + b['texto'],
                     caixa=[min(a['caixa'][0], b['caixa'][0]), min(a['caixa'][1], b['caixa'][1]),
                            max(a['caixa'][2], b['caixa'][2]), max(a['caixa'][3], b['caixa'][3])])
        saida.append(a)
    return saida


def rotulo_do_trecho(t):
    """(campo, texto do valor) quando o trecho comeca com um rotulo conhecido. O valor pode ser vazio (vem em outro
    trecho). Celula de tabela e de CSV usa o cabecalho da coluna como rotulo."""
    if t.get('papel') == 'cabecalho':
        return None, None
    if t.get('rotulo'):
        rn = _norm_1a1(t['rotulo'])
        for rx, campo in _RE_ROTULOS_COLUNA:
            if rx.match(rn):
                return campo, t['texto']
        return None, None
    n = _norm_1a1(t['texto'])
    for rx, campo in _RE_ROTULOS + _RE_ROTULOS_TEXTO:
        m = rx.match(n)
        if m:
            resto = t['texto'][m.end():].strip()
            return campo, resto[1:].strip() if resto.startswith(':') else resto
    return None, None


def _campo_de_formato(campo, valor_texto):
    """O rotulo "Formato" e ambiguo: com "L x A" e dimensao; com tipo de arquivo, tipos aceitos."""
    if campo == 'tipos_aceitos' and extrair.dimensoes(valor_texto):
        return 'dimensao'
    if campo == 'tipos_aceitos' and valor_texto and not extrair.tem_tipo(valor_texto):
        return None
    return campo


def associar(trechos, formato):
    """[(campo, trecho do valor, trecho do rotulo)] na ordem de leitura. No PDF, o rotulo sem valor procura o
    valor a direita na mesma linha; no texto, na linha seguinte (rotulo separado do valor). Depois do marcador
    "Vídeo" (ou dentro de uma secao de video do HTML), nada vira valor da peca estatica, ate o marcador "Imagem"."""
    pares = []
    consumidos = set()
    secao, pagina = None, None
    for i, t in enumerate(trechos):
        if formato == 'pdf' and t['pagina'] != pagina:
            secao, pagina = None, t['pagina']
        n = extrair.normalizar(t['texto'])
        # o marcador solto so vale no PDF (no HTML salvo, "Vídeo" tambem aparece no menu; la vale o titulo da secao)
        if formato == 'pdf' and n in SECOES_FORA + SECOES_DENTRO:
            secao = n
            t['marcador_secao'] = True
            continue
        if t['id'] in consumidos:
            continue
        campo, resto = rotulo_do_trecho(t)
        if campo is None:
            continue
        t['eh_rotulo'] = True
        secao_html = extrair.normalizar(t.get('secao') or '').split(' ')[0]
        if secao in SECOES_FORA or secao_html in SECOES_FORA:
            continue
        if resto:
            campo = _campo_de_formato(campo, resto)
            if campo:
                t['texto_valor'] = resto
                pares.append((campo, t, t))
            continue
        alvo = _valor_separado(trechos, i, formato, consumidos)
        if alvo is None:
            pares.append((campo, None, t))
            continue
        campo = _campo_de_formato(campo, alvo['texto'])
        consumidos.add(alvo['id'])
        alvo['eh_valor'] = True
        alvo['texto_valor'] = alvo['texto']
        if campo:
            pares.append((campo, alvo, t))
    return pares


def _valor_separado(trechos, i, formato, consumidos):
    t = trechos[i]
    if formato == 'pdf':
        candidatos = [o for o in trechos if o['pagina'] == t['pagina'] and o['id'] != t['id'] and
                      o['id'] not in consumidos and _mesma_linha(t, o) and o['caixa'][0] >= t['caixa'][2] and
                      rotulo_do_trecho(o)[0] is None]
        if candidatos:
            return min(candidatos, key=lambda o: o['caixa'][0])
    if i + 1 < len(trechos):
        o = trechos[i + 1]
        if o['pagina'] == t['pagina'] and rotulo_do_trecho(o)[0] is None and o['id'] not in consumidos:
            return o
    return None


# ------------------------------------------------------------------ montagem
def novo_registro(ident, nivel, **extra):
    r = {'id': ident, 'campos': {}}
    r.update(extra)
    return r


def completar(registro, nivel):
    """Todo campo do nivel que ficou sem valor vira registro sem valor."""
    for campo in CAMPOS_DO_NIVEL[nivel]:
        if campo not in registro['campos']:
            registro['campos'][campo] = valor_ausente('%s/%s' % (registro['id'], campo), campo)


def chave_do_formato(veiculador_id, circuito_id, dim):
    v = (dim or {}).get('valor')
    if not isinstance(v, dict):
        return None
    sufixo = '' if (dim.get('unidade') or 'px') == 'px' else dim['unidade']
    return '%s|%s|%sx%s%s' % (veiculador_id, circuito_id, v['largura'], v['altura'], sufixo)


class Montagem:
    """Monta o spec/1 de um conjunto de folhas, folha por folha, e depois aplica tabelas, propostas e acoes."""

    def __init__(self):
        self.folhas, self.veiculadores, self.circuitos, self.formatos = {}, {}, {}, {}
        self.trechos = {}       # (folha, id) -> trecho
        self.tetos = {}         # veiculador -> [linha de tabela]
        self.contagem = {'propostas_aplicadas': 0, 'propostas_ignoradas': 0, 'acoes_aplicadas': 0,
                         'acoes_ignoradas': 0}

    # -------------------------------------------------------------- folha
    def veiculador(self, vid):
        if vid not in self.veiculadores:
            self.veiculadores[vid] = novo_registro(vid, 'veiculador', folhas=[])
        return self.veiculadores[vid]

    def circuito(self, vid, texto, rid=None):
        cid = '%s:%s' % (vid, rid or slug_seguro(texto or 'geral'))
        if cid not in self.circuitos:
            self.circuitos[cid] = novo_registro(cid, 'circuito', veiculador=vid, texto_original=texto, restricoes=[])
        return self.circuitos[cid]

    def adicionar_folha(self, meta, leitura, vid):
        """meta: {id, arquivo, sha256, bytes, formato}. leitura: leitura-folha/1 lida."""
        fid = meta['id']
        trechos = preparar_trechos(fid, leitura)
        recortes = [{'id': '%s-p%02d' % (fid, p['numero']), 'pagina': p['numero'], 'arquivo': p['recorte'],
                     'sha256': p['recorte_sha256']} for p in leitura['paginas'] if p['recorte']]
        folha = novo_registro(fid, 'folha', arquivo=meta['arquivo'], sha256=meta['sha256'], bytes=meta['bytes'],
                              formato=meta['formato'], n_paginas=len(leitura['paginas']),
                              camada_texto=any(p['tem_texto'] for p in leitura['paginas']), titulo=leitura.get('titulo'),
                              veiculador=vid, recortes=recortes, trechos=trechos)
        self.folhas[fid] = folha
        for t in trechos:
            self.trechos[(fid, t['id'])] = t
        veic = self.veiculador(vid)
        veic['folhas'].append(fid)
        pares = associar(trechos, meta['formato'])
        if meta['formato'] == 'pdf':
            self._entradas_pdf(folha, veic, trechos, pares)
        elif meta['formato'] == 'csv':
            self._entradas_csv(folha, veic, pares)
        else:
            self._entradas_sequenciais(folha, veic, pares)

    def _valor(self, ident, campo, trecho, rotulo, fid, **kw):
        if trecho is None:
            v = valor_ausente(ident, campo)
            v.update(situacao='rascunho', alertas=['rotulo_sem_valor'],
                     fonte=fonte(fid, rotulo), origem='extraido_do_trecho', mapeamento='rotulo_da_folha',
                     texto_original=rotulo['texto'])
            return v
        return valor_do_trecho(ident, campo, trecho, fid, rotulo_trecho=rotulo, **kw)

    def _novo_formato(self, folha, veic, circ, ordem, pagina=None):
        sufixo = ('p%02d-e%02d' % (pagina, ordem)) if pagina else ('e%02d' % ordem)
        fmt = novo_registro('%s-%s' % (folha['id'], sufixo), 'formato', veiculador=veic['id'], circuito=circ['id'],
                            entrada={'folha': folha['id'], 'pagina': pagina, 'ordem': ordem}, chave=None)
        self.formatos[fmt['id']] = fmt
        return fmt

    def _destino(self, campo, fmt, circ, veic, folha):
        if campo not in CAMPOS:
            return None
        niveis = CAMPOS[campo][0]
        if 'formato' in niveis and fmt is not None:
            return fmt
        if 'circuito' in niveis and circ is not None:
            return circ
        if 'veiculador' in niveis:
            return veic
        if 'folha' in niveis:
            return folha
        return None

    def _gravar_par(self, campo, trecho, rotulo, destino, fid):
        if destino is None or campo not in CAMPOS:
            return
        if campo == 'restricao':
            destino['restricoes'].append(self._valor('%s/restricao/%d' % (destino['id'], len(destino['restricoes']) + 1),
                                                     campo, trecho, rotulo, fid))
            return
        por(self._valor('%s/%s' % (destino['id'], campo), campo, trecho, rotulo, fid), destino, campo)

    def _entradas_pdf(self, folha, veic, trechos, pares):
        """Cada pagina com dimensao e uma entrada (o PDF da PME e uma pagina por formato). O texto sem rotulo que
        fica todo a esquerda da coluna dos rotulos e o circuito (ambiente e praca, para o DA ou o Claude mapear); o
        que comeca com "*" e restricao do circuito. O resto da pagina (a tabela de video, observacoes de envio)
        fica so como trecho."""
        por_pagina = {}
        for campo, t, rot in pares:
            por_pagina.setdefault(rot['pagina'], []).append((campo, t, rot))
        for pagina, lista in sorted(por_pagina.items()):
            if not any(c == 'dimensao' for c, _t, _r in lista):
                for campo, t, rot in lista:
                    self._gravar_par(campo, t, rot, self._destino(campo, None, None, veic, folha), folha['id'])
                continue
            da_pagina = [x for x in trechos if x['pagina'] == pagina]
            coluna = min(x['caixa'][0] for x in da_pagina if x.get('eh_rotulo'))
            livres = [x for x in da_pagina if not x.get('eh_rotulo') and not x.get('eh_valor') and
                      not x.get('marcador_secao') and any(ch.isalnum() for ch in x['texto'])]
            restricoes = [x for x in livres if x['texto'].startswith('*')]
            circuito_txt = [x for x in livres if not x['texto'].startswith('*') and x['caixa'][2] <= coluna]
            texto = ' '.join(x['texto'] for x in circuito_txt) or None
            circ = self.circuito(veic['id'], texto, None if texto else '%s-p%02d' % (folha['id'], pagina))
            circ.setdefault('trechos', [])
            for x in circuito_txt:
                ref = '%s:%s' % (folha['id'], x['id'])
                if ref not in circ['trechos']:
                    circ['trechos'].append(ref)
            for x in restricoes:
                x['texto_valor'] = x['texto']
                if not any(r['fonte']['trecho'] == x['id'] and r['fonte']['folha'] == folha['id'] for r in circ['restricoes']):
                    self._gravar_par('restricao', x, x, circ, folha['id'])
            ordem, fmt = 0, None
            antes = []
            for campo, t, rot in lista:
                if campo == 'dimensao':
                    ordem += 1
                    fmt = self._novo_formato(folha, veic, circ, ordem, pagina)
                    for c2, t2, r2 in antes:
                        self._gravar_par(c2, t2, r2, self._destino(c2, fmt, circ, veic, folha), folha['id'])
                    antes = []
                if fmt is None:
                    antes.append((campo, t, rot))
                    continue
                self._gravar_par(campo, t, rot, self._destino(campo, fmt, circ, veic, folha), folha['id'])

    def _entradas_sequenciais(self, folha, veic, pares):
        """HTML e texto: cada dimensao abre uma entrada; o que vem antes da primeira e do veiculador. Celula de
        tabela do HTML com tamanho e peso e regra do veiculador por tamanho (os tetos por tag da Globo)."""
        blocos, linhas_tabela, do_circuito = [[]], {}, []
        for campo, t, rot in pares:
            if t is not None and t.get('papel') == 'celula':
                linhas_tabela.setdefault((t['tabela'], t['linha_tabela']), []).append((campo, t, rot))
                continue
            # no e-mail o circuito e a praca vem antes do formato: ficam com a entrada seguinte
            if campo in CAMPOS and CAMPOS[campo][0] == ('circuito',):
                do_circuito.append((campo, t, rot))
                continue
            if campo == 'dimensao':
                blocos.append(do_circuito)
                do_circuito = []
            blocos[-1].append((campo, t, rot))
        if do_circuito and len(blocos) > 1:
            blocos[-1].extend(do_circuito)
        for campo, t, rot in blocos[0]:
            self._gravar_par(campo, t, rot, self._destino(campo, None, None, veic, folha), folha['id'])
        for ordem, bloco in enumerate(blocos[1:], 1):
            if folha['formato'] == 'html':
                # pagina salva da Globo: um formato por pagina; o circuito e o nome da pagina salva
                circ = self.circuito(veic['id'], None, slug_seguro(folha['arquivo'].rsplit('/', 1)[-1].rsplit('.', 1)[0]))
            else:
                textos = [t['texto_valor'] for c, t, _r in bloco if c in ('ambiente', 'praca') and t is not None]
                circ = self.circuito(veic['id'], ' '.join(textos) or None, None if textos else '%s-geral' % folha['id'])
            fmt = self._novo_formato(folha, veic, circ, ordem)
            for campo, t, rot in bloco:
                self._gravar_par(campo, t, rot, self._destino(campo, fmt, circ, veic, folha), folha['id'])
        for (tab, lin), celulas in sorted(linhas_tabela.items()):
            self._linha_de_tetos(folha, veic, tab, lin, celulas)

    def _linha_de_tetos(self, folha, veic, tab, lin, celulas):
        campos = {c for c, _t, _r in celulas}
        if 'dimensao' not in campos or not campos & {'peso_max_tag_carga_inicial', 'peso_max_tag_carga_posterior',
                                                     'peso_max', 'peso_max_tag'}:
            return
        rid = '%s-tab%02d-l%03d' % (folha['id'], tab, lin)
        linha = {'id': rid, 'campos': {}}
        for campo, t, rot in celulas:
            if campo in ('dimensao', 'peso_max_tag_carga_inicial', 'peso_max_tag_carga_posterior', 'peso_max',
                         'peso_max_tag'):
                linha['campos'][campo] = self._valor('%s/%s' % (rid, campo), campo, t, rot, folha['id'])
        self.tetos.setdefault(veic['id'], []).append(linha)

    def _entradas_csv(self, folha, veic, pares):
        """CSV exportado pelo DA: cada linha com dimensao (ou largura e altura) e um formato; o circuito sai das
        colunas de ambiente e praca da propria linha."""
        por_linha = {}
        for campo, t, rot in pares:
            if t is not None:
                por_linha.setdefault(t['linha'], []).append((campo, t, rot))
        for ordem, (_lin, lista) in enumerate(sorted(por_linha.items()), 1):
            campos = {c: (t, r) for c, t, r in lista}
            if 'dimensao' not in campos and not ('largura' in campos and 'altura' in campos):
                for campo, t, rot in lista:
                    if campo not in ('largura', 'altura'):
                        self._gravar_par(campo, t, rot, self._destino(campo, None, None, veic, folha), folha['id'])
                continue
            textos_circ = [campos[c][0]['texto'] for c in ('ambiente', 'praca') if c in campos]
            circ = self.circuito(veic['id'], ' '.join(textos_circ) or None, None if textos_circ else '%s-geral' % folha['id'])
            fmt = self._novo_formato(folha, veic, circ, ordem)
            for campo, t, rot in lista:
                if campo in ('largura', 'altura'):
                    continue
                self._gravar_par(campo, t, rot, self._destino(campo, fmt, circ, veic, folha), folha['id'])
            if 'dimensao' not in campos:
                fmt['campos']['dimensao'] = self._dimensao_de_colunas(fmt, campos, folha['id'])

    def _dimensao_de_colunas(self, fmt, campos, fid):
        tl, tr_ = campos['largura'][0], campos['altura'][0]
        lit_l, lit_a = tl['texto'].strip(), tr_['texto'].strip()
        lei = extrair.dimensao('%s x %s' % (lit_l, lit_a))
        v = valor_do_trecho('%s/dimensao' % fmt['id'], 'dimensao', dict(tl, texto_valor='%s x %s' % (lit_l, lit_a)), fid)
        v.update(valor=lei['valor'], numeros_literais=lei['numeros_literais'], texto_original='%s x %s' % (lit_l, lit_a))
        v['fonte']['trechos_adicionais'] = [tr_['id']]
        v['alertas'] = sorted(set(v['alertas']) | {'dimensao_de_duas_colunas'})
        return v

    # -------------------------------------------------------------- depois das folhas
    def aplicar_tetos(self):
        """A tabela de peso por tamanho do veiculador (os tetos por tag da Globo) vale para o formato do mesmo
        tamanho. Se a ficha do formato da outro teto por tag que a tabela, o campo peso_max_tag fica com as duas
        leituras (o Half-Page: 550 KB na ficha contra 500 KB na carga posterior da tabela)."""
        for vid, linhas in self.tetos.items():
            self.veiculador(vid)['tetos_por_tamanho'] = linhas
            for fmt in self.formatos.values():
                if fmt['veiculador'] != vid:
                    continue
                dim = fmt['campos'].get('dimensao', {}).get('valor')
                if not isinstance(dim, dict):
                    continue
                for linha in linhas:
                    tam = linha['campos']['dimensao'].get('valor')
                    tamanhos = tam if isinstance(tam, list) else [tam]
                    if dim not in tamanhos:
                        continue
                    # ficha e tabela (e duas linhas da tabela) pelo mesmo caminho: valor diferente vira divergencia
                    for campo in ('peso_max_tag_carga_inicial', 'peso_max_tag_carga_posterior'):
                        if campo not in linha['campos'] or linha['campos'][campo].get('valor') is None:
                            continue
                        v = dict(linha['campos'][campo])
                        v['id'] = '%s/%s' % (fmt['id'], campo)
                        v['alertas'] = sorted(set(v['alertas']) | {'aplicado_pela_tabela_por_tamanho'})
                        por(v, fmt, campo)
                    if 'peso_max_tag_carga_posterior' in linha['campos'] and tem_valor(fmt['campos'].get('peso_max_tag')):
                        nova = dict(linha['campos']['peso_max_tag_carga_posterior'])
                        if nova.get('valor') is not None:
                            nova.update(id='%s/peso_max_tag' % fmt['id'], condicao='por_tag')
                            por(nova, fmt, 'peso_max_tag')

    def conferir_unidades(self):
        """Area total e area util da mesma entrada, na mesma unidade: util maior que total, ou total maior que util
        pelo fator specs.fator_incoerencia_unidade (o "120m x 175m" da PME), vira alerta nas duas."""
        fator = limites.valor('specs.fator_incoerencia_unidade')
        for fmt in self.formatos.values():
            dim, util = fmt['campos'].get('dimensao'), fmt['campos'].get('area_util')
            if not (tem_valor(dim) and tem_valor(util)) or not isinstance(dim['valor'], dict) or \
                    not isinstance(util['valor'], dict) or dim['unidade'] != util['unidade']:
                continue
            alerta = None
            eixos = ('largura', 'altura')
            if any(util['valor'][e] > dim['valor'][e] for e in eixos):
                alerta = 'area_util_maior_que_total'
            elif all(dim['valor'][e] > fator * util['valor'][e] for e in eixos):
                alerta = 'unidade_incoerente'
            if alerta:
                for v in (dim, util):
                    v['alertas'] = sorted(set(v['alertas']) | {alerta})

    def localizar_trecho(self, folha_id, trecho_id=None, pagina=None, texto=None):
        if trecho_id:
            return self.trechos.get((folha_id, trecho_id))
        for (fid, _tid), t in self.trechos.items():
            if fid == folha_id and t['pagina'] == pagina and t['texto'] == texto:
                return t
        return None

    def aplicar_propostas(self, propostas, mapeamento):
        """Propostas de mapeamento trecho -> campo (do Claude, por sugestoes/mapeamento-specs.json, ou da curadoria
        da biblioteca). A proposta nunca traz numero: o motor extrai do texto literal do trecho (mais os trechos
        adicionais da mesma pagina, quando o campo ocupa duas linhas, como "Edifícios" e "Comerciais"), ou de um
        pedaco literal dele (recorte_texto). O valor continua rascunho ate o DA confirmar."""
        for p in propostas:
            t = self.localizar_trecho(p['folha'], p.get('trecho'), p.get('pagina'), p.get('texto'))
            adicionais = [self._adicional(p['folha'], t, a) for a in p.get('adicionais') or []] if t else []
            texto = ' '.join([t['texto']] + [a['texto'] for a in adicionais if a]) if t else ''
            corte = p.get('recorte_texto')
            if t is None or None in adicionais or p['campo'] not in CAMPOS or (
                    corte is not None and not corte_com_fronteira(corte, texto)):
                self.contagem['propostas_ignoradas'] += 1
                continue
            destino = self._destino_da_proposta(p, t)
            if destino is None:
                self.contagem['propostas_ignoradas'] += 1
                continue
            t2 = dict(t, texto_valor=texto)
            if p['campo'] == 'restricao':
                ident = '%s/restricao/%d' % (destino['id'], len(destino['restricoes']) + 1)
                v = valor_do_trecho(ident, 'restricao', t2, t['folha'], mapeamento=mapeamento, recorte_texto=corte)
            else:
                v = valor_do_trecho('%s/%s' % (destino['id'], p['campo']), p['campo'], t2, t['folha'],
                                    mapeamento=mapeamento, recorte_texto=corte)
            if adicionais:
                v['fonte']['trechos_adicionais'] = [a['id'] for a in adicionais]
            if p['campo'] == 'restricao':
                destino['restricoes'].append(v)
            else:
                por(v, destino, p['campo'])
            self.contagem['propostas_aplicadas'] += 1

    def _adicional(self, folha_id, t, a):
        """Trecho adicional da proposta: o id (proposta do Claude) ou o texto exato na mesma pagina (curadoria)."""
        if isinstance(a, str):
            o = self.localizar_trecho(folha_id, a)
        else:
            o = self.localizar_trecho(folha_id, a.get('trecho'), t['pagina'], a.get('texto'))
        return o if o is not None and o['pagina'] == t['pagina'] else None

    def _destino_da_proposta(self, p, t):
        niveis = CAMPOS[p['campo']][0]
        alvo = p.get('alvo')
        for tabela, nivel in ((self.formatos, 'formato'), (self.circuitos, 'circuito'),
                              (self.veiculadores, 'veiculador'), (self.folhas, 'folha')):
            if alvo and alvo in tabela:
                return tabela[alvo] if nivel in niveis else None
        if alvo:
            return None
        folha = self.folhas[t['folha']]
        da_pagina = [f for f in self.formatos.values() if f['entrada']['folha'] == folha['id'] and
                     f['entrada']['pagina'] in (t['pagina'], None)]
        if 'formato' in niveis and len(da_pagina) == 1:
            return da_pagina[0]
        if 'circuito' in niveis:
            circs = {f['circuito'] for f in da_pagina}
            return self.circuitos[circs.pop()] if len(circs) == 1 else None
        if 'veiculador' in niveis:
            return self.veiculadores[folha['veiculador']]
        if 'folha' in niveis:
            return folha
        return None

    def fechar_chaves(self):
        """Chave = veiculador|circuito|LxA. Chave repetida (o mesmo tamanho no mesmo circuito, em duas paginas) fica
        com o alerta chave_repetida e um sufixo, sem juntar as entradas."""
        chaves = {}
        for fmt in self.formatos.values():
            chave = chave_do_formato(fmt['veiculador'], fmt['circuito'].split(':', 1)[1], fmt['campos'].get('dimensao'))
            fmt['chave'] = chave
            if chave:
                chaves.setdefault(chave, []).append(fmt)
        # todas as entradas com a mesma chave ganham o id do formato: a chave nao depende da ordem das folhas
        for chave, lista in chaves.items():
            if len(lista) > 1:
                for fmt in lista:
                    fmt['alertas'] = ['chave_repetida']
                    fmt['chave'] = '%s#%s' % (chave, fmt['id'])

    def completar_tudo(self):
        for nivel, tabela in (('folha', self.folhas), ('veiculador', self.veiculadores), ('circuito', self.circuitos),
                              ('formato', self.formatos)):
            for r in tabela.values():
                completar(r, nivel)
                r.setdefault('alertas', [])
        for v in self.veiculadores.values():
            v.setdefault('tetos_por_tamanho', [])


# ------------------------------------------------------------------ acoes do DA
def chaves_depois_das_escolhas(doc):
    """A chave do formato que so ganha medida pela acao do DA (revisao dos becos, D2): a medida divergente (duas
    leituras, valor nulo) deixa o formato sem chave em fechar_chaves, e a escolha da leitura (aplicar_acoes) vem
    depois. Aqui a chave e montada da medida escolhida. As chaves que ja existiam nunca mudam: a nova que repete uma
    delas leva o sufixo do id do formato (como chave_repetida em fechar_chaves), so ela. A repeticao conta tambem a
    chave que fechar_chaves ja sufixou (K#<id> repete K). Devolve quantas montou."""
    existentes = set()
    for f in doc['formatos']:
        if f.get('chave'):
            existentes |= {f['chave'], f['chave'].split('#', 1)[0]}
    novas = 0
    for fmt in doc['formatos']:
        if fmt.get('chave'):
            continue
        chave = chave_do_formato(fmt['veiculador'], fmt['circuito'].split(':', 1)[1], fmt['campos'].get('dimensao'))
        if chave is None:
            continue
        if chave in existentes:
            fmt['alertas'] = sorted(set(fmt.get('alertas') or []) | {'chave_repetida'})
            chave = '%s#%s' % (chave, fmt['id'])
        fmt['chave'] = chave
        existentes.add(chave)
        novas += 1
    return novas


def completar_documento(doc):
    """O perfil da biblioteca guarda so os campos que a folha traz (o registro sem valor fica implicito, para o arquivo
    nao repetir centenas de campos vazios). Ao ler, o campo que falta volta como registro sem valor."""
    for nivel, lista in (('folha', 'folhas'), ('veiculador', 'veiculadores'), ('circuito', 'circuitos'),
                         ('formato', 'formatos')):
        for r in doc[lista]:
            completar(r, nivel)
    return doc


def enxugar_documento(doc):
    """O contrario de completar_documento: tira os registros sem valor (origem ausente)."""
    for lista in ('folhas', 'veiculadores', 'circuitos', 'formatos'):
        for r in doc[lista]:
            r['campos'] = {c: v for c, v in r['campos'].items() if v['origem'] != 'ausente'}
    return doc


def todos_os_valores(doc):
    """(registro, campo, valor) de todo valor do documento, inclusive restricoes e linhas de tetos."""
    for nivel in ('folhas', 'veiculadores', 'circuitos', 'formatos'):
        for r in doc[nivel]:
            for campo, v in r['campos'].items():
                yield r, campo, v
            for i, v in enumerate(r.get('restricoes') or []):
                yield r, 'restricao', v
            for linha in r.get('tetos_por_tamanho') or []:
                for campo, v in linha['campos'].items():
                    yield linha, campo, v


def indice_de_valores(doc):
    return {v['id']: (r, campo, v) for r, campo, v in todos_os_valores(doc)}


def aplicar_digitados(montagem, acoes):
    """Acoes "digitar" do DA: valor digitado ao lado do recorte de uma pagina sem texto (a dimensao cria o
    formato). Vem antes das chaves, porque o formato digitado tambem tem chave. Devolve (aplicadas, ignoradas)."""
    aplicadas, ignoradas = 0, 0
    for acao in acoes:
        if acao['acao'] != 'digitar':
            continue
        if _digitar(montagem, acao):
            aplicadas += 1
        else:
            ignoradas += 1
    return aplicadas, ignoradas


def aplicar_acoes(doc, acoes):
    """Aplica as acoes do DA (specs/confirmacoes.json, gravado so pelo "spec confirmar" no terminal e pelo botao do
    passo 1 da tela):
      - confirmar: o valor com a mesma impressao vira confirmado;
      - escolher_leitura: num campo com fontes divergentes, a leitura escolhida vira o valor confirmado.
    Acao que nao bate mais (a folha mudou e a impressao e outra) fica de fora e conta como ignorada."""
    aplicadas, ignoradas = 0, 0
    indice = indice_de_valores(doc)
    for acao in acoes:
        if acao['acao'] == 'digitar':
            continue
        alvo = indice.get(acao['valor_id'])
        if alvo is None or impressao(alvo[2]) != acao['impressao']:
            ignoradas += 1
            continue
        reg, campo, v = alvo
        # quem e o meio vem da acao: o terminal (por da, meio terminal) ou o botao da tela (meio tela; no modo de
        # teste da tela, por fixture_de_teste e meio medicao)
        conf = {'por': acao.get('por', 'da'), 'meio': acao.get('meio', 'terminal'), 'em': acao['em'], 'leitura': None}
        if acao['acao'] == 'confirmar' and v.get('valor') is not None:
            v.update(situacao='confirmado', confirmacao=conf)
        elif acao['acao'] == 'escolher_leitura' and v.get('leituras') and 0 <= acao['leitura'] < len(v['leituras']):
            lei = v['leituras'][acao['leitura']]
            for k in ('valor', 'forma', 'texto_original', 'numeros_literais', 'unidade', 'unidade_original',
                      'base_unidade', 'fonte'):
                v[k] = lei[k]
            conf['leitura'] = acao['leitura']
            v.update(situacao='confirmado', confirmacao=conf)
        else:
            ignoradas += 1
            continue
        aplicadas += 1
    return aplicadas, ignoradas


def _digitar(montagem, acao):
    folha = montagem.folhas.get(acao['folha'])
    if folha is None or acao['campo'] not in CAMPOS_DIGITAVEIS:
        return False
    recorte = next((r for r in folha['recortes'] if r['id'] == acao['recorte']), None)
    if recorte is None:
        return False
    veic = montagem.veiculador(folha['veiculador'])
    circ = montagem.circuito(veic['id'], None, '%s-p%02d' % (folha['id'], recorte['pagina']))
    fid = '%s-r%02d-e%02d' % (folha['id'], recorte['pagina'], int(acao.get('entrada') or 1))
    niveis = CAMPOS[acao['campo']][0]
    if 'formato' in niveis:
        if fid not in montagem.formatos:
            if acao['campo'] != 'dimensao':
                return False
            fmt = novo_registro(fid, 'formato', veiculador=veic['id'], circuito=circ['id'], chave=None,
                                entrada={'folha': folha['id'], 'pagina': recorte['pagina'],
                                         'ordem': int(acao.get('entrada') or 1)})
            montagem.formatos[fid] = fmt
        destino = montagem.formatos[fid]
    elif 'circuito' in niveis:
        destino = circ
    elif 'veiculador' in niveis:
        destino = veic
    else:
        destino = folha
    if acao['campo'] == 'restricao':
        ident = '%s/restricao/%d' % (destino['id'], len(destino['restricoes']) + 1)
    else:
        ident = '%s/%s' % (destino['id'], acao['campo'])
    v = valor_digitado(ident, acao['campo'], acao['texto'], folha['id'], recorte)
    if v['valor'] is None:
        return False
    v.update(situacao='confirmado', confirmacao={'por': 'da', 'meio': 'terminal', 'em': acao['em'], 'leitura': None})
    if acao['campo'] == 'restricao':
        destino['restricoes'].append(v)
    else:
        destino['campos'][acao['campo']] = v
    return True


# ------------------------------------------------------------------ documento
def documento(montagem, *, tipo='rascunho', perfis=(), job_id=None, motor_versao='', gerado_em=None):
    def lista(tabela):
        return [tabela[k] for k in sorted(tabela)]
    doc = {'esquema': ESQUEMA, 'tipo': tipo, 'gerado_em': gerado_em, 'motor_versao': motor_versao, 'job_id': job_id,
           'perfis': list(perfis), 'folhas': lista(montagem.folhas), 'veiculadores': lista(montagem.veiculadores),
           'circuitos': lista(montagem.circuitos), 'formatos': lista(montagem.formatos)}
    for f in doc['folhas']:
        f['trechos'] = [_trecho_publico(t) for t in f['trechos']]
    for c in doc['circuitos']:
        c.setdefault('trechos', [])
    doc['resumo'] = resumo(doc)
    _situacao_das_folhas(doc)
    return doc


def _trecho_publico(t):
    return {k: t.get(k) for k in ('id', 'pagina', 'texto', 'caixa', 'linha', 'coluna', 'tabela', 'linha_tabela', 'rotulo',
                                  'secao', 'papel')}


def _situacao_das_folhas(doc):
    por_folha = {}
    for _r, _c, v in todos_os_valores(doc):
        f = (v.get('fonte') or {}).get('folha')
        if f and v['situacao'] in ('rascunho', 'confirmado'):
            por_folha.setdefault(f, set()).add(v['situacao'])
    for f in doc['folhas']:
        s = por_folha.get(f['id'], set())
        f['situacao_confirmacao'] = 'confirmada' if s == {'confirmado'} else ('parcial' if 'confirmado' in s else 'rascunho')


def resumo(doc):
    valores = list(todos_os_valores(doc))
    por_sit = {'rascunho': 0, 'confirmado': 0, 'registro': 0}
    for _r, _c, v in valores:
        por_sit[v['situacao']] += 1
    em_px = [f for f in doc['formatos'] if (f['campos'].get('dimensao') or {}).get('unidade') == 'px'
             and isinstance((f['campos'].get('dimensao') or {}).get('valor'), dict)]
    tamanhos = {(f['campos']['dimensao']['valor']['largura'], f['campos']['dimensao']['valor']['altura']) for f in em_px}
    return {'folhas': len(doc['folhas']), 'trechos': sum(len(f['trechos']) for f in doc['folhas']),
            'recortes': sum(len(f['recortes']) for f in doc['folhas']), 'veiculadores': len(doc['veiculadores']),
            'circuitos': len(doc['circuitos']), 'formatos': len(doc['formatos']), 'formatos_em_px': len(em_px),
            'tamanhos_em_px': len(tamanhos), 'valores': len(valores), 'valores_rascunho': por_sit['rascunho'],
            'valores_confirmados': por_sit['confirmado'], 'registros': por_sit['registro'],
            'sem_valor': sum(1 for _r, _c, v in valores if v['valor'] is None),
            'com_alerta': sum(1 for _r, _c, v in valores if v['alertas']),
            'divergencias': sum(1 for _r, _c, v in valores if 'fontes_divergentes' in v['alertas'] and v['valor'] is None),
            'digitados': sum(1 for _r, _c, v in valores if v['origem'] == 'digitado_pelo_da_a_partir_do_recorte')}


def conferir_literais(doc):
    """[(id do valor, numero)] de todo numero literal que nao existe no trecho citado (ou no texto que o DA
    digitou). Lista vazia e o esperado: o rascunho so tem numero que esta na folha."""
    textos = {(f['id'], t['id']): t['texto'] for f in doc['folhas'] for t in f['trechos']}
    erros = []

    def conferir(ident, v):
        fon = v.get('fonte') or {}
        if v.get('origem') == 'digitado_pelo_da_a_partir_do_recorte':
            base = v.get('texto_digitado') or ''
        elif v.get('origem') == 'extraido_do_trecho' and fon.get('trecho'):
            base = textos.get((fon['folha'], fon['trecho']), '')
            for extra in fon.get('trechos_adicionais') or []:
                base += ' ' + textos.get((fon['folha'], extra), '')
            if fon.get('recorte_texto') is not None and not corte_com_fronteira(fon['recorte_texto'], base):
                erros.append((ident, fon['recorte_texto']))
        else:
            base = ''
        for n in v.get('numeros_literais') or []:
            if not numero_no_texto(n, base):
                erros.append((ident, n))

    for _r, _c, v in todos_os_valores(doc):
        conferir(v['id'], v)
        for lei in v.get('leituras') or []:
            conferir(v['id'], dict(lei, origem='extraido_do_trecho'))
    return erros


# ------------------------------------------------------------------ formatos do job e heranca
def resolver(doc, fmt, campo):
    """O valor do campo no formato, ou herdado do circuito ou do veiculador (HERANCA). None sem valor."""
    v = fmt['campos'].get(campo)
    if tem_valor(v):
        return v
    if campo in HERANCA:
        nivel, campo_pai = HERANCA[campo]
        tabela = {r['id']: r for r in doc['circuitos' if nivel == 'circuito' else 'veiculadores']}
        pai = tabela.get(fmt['circuito' if nivel == 'circuito' else 'veiculador'])
        if pai is not None and tem_valor(pai['campos'].get(campo_pai)):
            return dict(pai['campos'][campo_pai], herdado_de=pai['campos'][campo_pai]['id'])
    return None


def formatos_do_job(rascunho):
    """specs/formatos-do-job.json: so valores confirmados pelo DA. Formato entra quando a dimensao esta
    confirmada; campo sem valor confirmado (do proprio formato ou herdado) fica de fora."""
    import copy
    doc = copy.deepcopy(rascunho)
    doc['tipo'] = 'formatos_do_job'
    usados_c, usados_v, citados = set(), set(), set()
    formatos = []
    for fmt in doc['formatos']:
        dim = fmt['campos'].get('dimensao')
        if not fmt.get('chave') or not dim or dim['situacao'] != 'confirmado':
            continue
        campos = {}
        for campo in CAMPOS_DO_NIVEL['formato']:
            v = resolver(rascunho, fmt, campo)
            if v is not None and v['situacao'] == 'confirmado':
                campos[campo] = v
        fmt['campos'] = campos
        formatos.append(fmt)
        usados_c.add(fmt['circuito'])
        usados_v.add(fmt['veiculador'])
    doc['formatos'] = formatos

    def so_confirmados(r):
        r['campos'] = {c: v for c, v in r['campos'].items() if v['situacao'] == 'confirmado'}
        if 'restricoes' in r:
            r['restricoes'] = [v for v in r['restricoes'] if v['situacao'] == 'confirmado']
        for linha in r.get('tetos_por_tamanho') or []:
            linha['campos'] = {c: v for c, v in linha['campos'].items() if v['situacao'] == 'confirmado'}
        if 'tetos_por_tamanho' in r:
            r['tetos_por_tamanho'] = [x for x in r['tetos_por_tamanho'] if x['campos']]
        return r
    doc['circuitos'] = [so_confirmados(c) for c in doc['circuitos'] if c['id'] in usados_c]
    doc['veiculadores'] = [so_confirmados(v) for v in doc['veiculadores'] if v['id'] in usados_v]
    for f in doc['folhas']:
        so_confirmados(f)
    for _r, _c, v in todos_os_valores(doc):
        fon = v.get('fonte') or {}
        if fon.get('trecho'):
            citados.add((fon['folha'], fon['trecho']))
        for extra in fon.get('trechos_adicionais') or []:
            citados.add((fon['folha'], extra))
    for f in doc['folhas']:
        f['trechos'] = [t for t in f['trechos'] if (f['id'], t['id']) in citados]
    doc['resumo'] = resumo(doc)
    return doc
