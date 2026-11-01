# -*- coding: utf-8 -*-
"""Extracao dos numeros de um trecho da folha: o unico lugar onde um numero de spec nasce.

Regra (arquitetura-v1.md, 4.8 e 6): o numero sai do texto literal do trecho, por expressao regular, e cada leitura
guarda os numeros como aparecem no texto (numeros_literais). Um teste confere que todo numero literal existe no
trecho citado. O Claude pode propor qual trecho vai para qual campo, mas nunca da o numero.

Cada funcao recebe o texto (e, quando a unidade vem do cabecalho de uma tabela, o rotulo) e devolve uma Leitura,
um dict com: valor, forma (exato, maximo, faixa, conjunto, condicional), numeros_literais, unidade (normalizada),
unidade_original, base_unidade (decimal, binaria ou nao_declarada) e alertas. Sem numero reconhecivel, valor
fica None com o alerta valor_nao_reconhecido: o campo vira rascunho sem valor, nunca um valor inventado.

Armadilhas da folha PME (pesquisa/v1-estatico-sintese.md, 5), cada uma vira alerta e nunca valor confirmado:
  - virgula decimal ("1,17m"): o valor sai 1.17 com o alerta virgula_decimal;
  - ponto que pode ser milhar ou decimal ("1.920"): sem valor, alerta separador_ambiguo;
  - unidade sem declaracao (dimensao "300x600" sem px): alerta unidade_nao_declarada;
  - MB e KB sem dizer se decimal ou binario: base nao_declarada, alvo na leitura estrita e reprovacao so acima
    da folgada (desdobra.specs.extrair.peso_em_bytes).
"""
import re
import unicodedata

# multiplicadores de unidade: definicao do SI e da IEC, nao regra
MULTIPLICADOR_DECIMAL = {'b': 1, 'kb': 1000, 'mb': 1000 ** 2, 'gb': 1000 ** 3}  # numero-neutro: definicao do SI
MULTIPLICADOR_BINARIO = {'b': 1, 'kb': 1024, 'mb': 1024 ** 2, 'gb': 1024 ** 3}  # numero-neutro: definicao da IEC (2^10)
UNIDADES_BINARIAS = {'kib': 'kb', 'mib': 'mb', 'gib': 'gb'}
UNIDADES_COMPRIMENTO = ('px', 'mm', 'cm', 'm')

# tipo de arquivo -> MIME (nomes que as folhas usam)
MIME_POR_NOME = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif',
                 'gif animado': 'image/gif', 'html5': 'text/html', 'html': 'text/html', 'mp4': 'video/mp4',
                 'pdf': 'application/pdf', 'webp': 'image/webp', 'svg': 'image/svg+xml', 'zip': 'application/zip'}

# numero com fronteira: nunca comeca nem termina no meio de outro numero ("5 MB" dentro de "15 MB" nao e numero), e
# com tamanho limitado, para a expressao ficar linear num texto hostil (uma fileira de 40 mil digitos)
_NUM = r'(?<![\d.,])\d{1,7}(?:[.,]\d{1,7}){0,3}(?![\d])'
_RE_DIMENSAO = re.compile(r'(?P<l>%s)\s*(?P<ul>px|mm|cm|m)?\s*[xX×]\s*(?P<a>%s)\s*(?P<ua>px|mm|cm|m)?(?![a-zA-Z])'
                          % (_NUM, _NUM))
_RE_PESO = re.compile(r'(?P<n>%s)\s*(?P<u>[kKmMgG]i?[bB]|bytes?)(?![a-zA-Z])' % _NUM)
_RE_UNIDADE_ROTULO = re.compile(r'\(\s*(?P<u>[kKmMgG]i?[bB]|bytes?)\s*\)')
_RE_PX = re.compile(r'(?P<n>%s)\s*(?:px|pixels?)(?![a-zA-Z])' % _NUM)
_RE_PCT = re.compile(r'(?P<n>%s)\s*%%' % _NUM)
_RE_NUMERO_SOLTO = re.compile(r'^\s*(?P<n>%s)\s*$' % _NUM)
_RE_MAXIMO = re.compile(r'\b(ate|maximo|max|no maximo|limite|limitado)\b|<=|≤')
_RE_FAIXA = re.compile(r'\bentre\b.*\be\b|\bde\b\s*\d.*\ba\b\s*\d')
_RE_CONDICAO = re.compile(r'\b(que tenham|quando|caso|se o|se a|somente se|desde que)\b')
_RE_APROXIMADO = re.compile(r'\b(cerca de|aprox|aproximadamente|em torno de)\b')
_RE_SEM_VALOR = re.compile(r'^\s*[-–—]\s*$')
LADOS = {'superior': 'superior', 'topo': 'superior', 'inferior': 'inferior', 'base': 'inferior', 'rodape': 'inferior',
         'esquerda': 'esquerda', 'esquerdo': 'esquerda', 'direita': 'direita', 'direito': 'direita',
         'laterais': 'laterais', 'lateral': 'laterais'}
CORES = ('preta', 'preto', 'branca', 'branco', 'cinza')


def normalizar(texto):
    """Minusculas, sem acento e com espacos simples: so para reconhecer rotulo e palavra, nunca para o valor."""
    sem = ''.join(c for c in unicodedata.normalize('NFKD', texto or '') if not unicodedata.combining(c))
    return ' '.join(sem.lower().split())


def numero(literal):
    """(valor, alerta) de um numero escrito na folha. Virgula e decimal; ponto seguido de 3 digitos e ambiguo."""
    if ',' in literal and '.' in literal:
        return None, 'separador_ambiguo'
    if ',' in literal:
        partes = literal.split(',')
        if len(partes) != 2:  # numero-neutro: um separador decimal
            return None, 'separador_ambiguo'
        return float(literal.replace(',', '.')), 'virgula_decimal'
    if '.' in literal:
        partes = literal.split('.')
        if len(partes) != 2 or len(partes[1]) == 3:  # numero-neutro: grupo de milhar tem 3 digitos
            return None, 'separador_ambiguo'
        return float(literal), None
    return int(literal), None


def _inteiro_se_der(v):
    return int(v) if isinstance(v, float) and v.is_integer() else v


def leitura(valor=None, forma=None, numeros=(), unidade=None, unidade_original=None, base=None, alertas=(),
            condicao=None):
    return {'valor': valor, 'forma': forma, 'numeros_literais': list(numeros), 'unidade': unidade,
            'unidade_original': unidade_original, 'base_unidade': base, 'alertas': sorted(set(alertas)),
            'condicao': condicao}


def sem_valor(alerta='valor_nao_reconhecido'):
    return leitura(alertas=[alerta])


def forma_do_texto(texto, rotulo=None, padrao='exato'):
    n = normalizar('%s %s' % (rotulo or '', texto))
    if _RE_CONDICAO.search(n):
        return 'condicional'
    if _RE_FAIXA.search(n):
        return 'faixa'
    if _RE_MAXIMO.search(n):
        return 'maximo'
    return padrao


# ------------------------------------------------------------------ dimensoes
def dimensoes(texto):
    """[(largura, altura, unidade ou None, literais, alertas)] de cada "L x A" do texto."""
    saida = []
    for m in _RE_DIMENSAO.finditer(texto or ''):
        alertas = []
        largura, a1 = numero(m.group('l'))
        altura, a2 = numero(m.group('a'))
        alertas += [a for a in (a1, a2) if a]
        un = m.group('ua') or m.group('ul')
        if m.group('ua') and m.group('ul') and m.group('ua') != m.group('ul'):
            alertas.append('unidades_diferentes')
        if un is None:
            alertas.append('unidade_nao_declarada')
        saida.append((_inteiro_se_der(largura), _inteiro_se_der(altura), un, [m.group('l'), m.group('a')], alertas))
    return saida


def dimensao(texto, rotulo=None):
    """Dimensao do arquivo ou da area util: {largura, altura}. Mais de uma no texto vira conjunto."""
    achadas = dimensoes(texto)
    if not achadas:
        return sem_valor()
    alertas = []
    numeros = []
    valores = []
    unidades = set()
    for largura, altura, un, lits, al in achadas:
        alertas += al
        numeros += lits
        unidades.add(un or 'px')
        valores.append(None if largura is None or altura is None else {'largura': largura, 'altura': altura})
    unidade = unidades.pop() if len(unidades) == 1 else None
    if unidade is None:
        alertas.append('unidades_diferentes')
    if unidade and unidade != 'px':
        alertas.append('fora_do_escopo_v1')
    if any(v is None for v in valores):
        return leitura(None, 'exato', numeros, unidade, unidade, None, alertas)
    if len(valores) == 1:
        return leitura(valores[0], 'exato', numeros, unidade, unidade, None, alertas)
    alertas.append('mais_de_uma_dimensao')
    return leitura(valores, 'conjunto', numeros, unidade, unidade, None, alertas)


# ------------------------------------------------------------------ peso
def peso_em_bytes(n, unidade):
    """(alvo_bytes, reprova_acima_bytes, base) de "n unidade" (arquitetura-v1.md, 4.8 e 5.5).

    Nenhuma folha diz se MB e decimal ou binario: o alvo e a leitura estrita (decimal, 5 MB = 5.000.000) e a
    reprovacao so vale acima da folgada (binaria, 5 MB = 5.242.880). Com KiB ou MiB declarados, as duas leituras
    sao a mesma."""
    u = unidade.lower()
    if u in ('byte', 'bytes'):
        u = 'b'
    if u in UNIDADES_BINARIAS:
        b = int(round(n * MULTIPLICADOR_BINARIO[UNIDADES_BINARIAS[u]]))
        return b, b, 'binaria'
    if u == 'b':
        return int(round(n)), int(round(n)), 'decimal'
    return int(round(n * MULTIPLICADOR_DECIMAL[u])), int(round(n * MULTIPLICADOR_BINARIO[u])), 'nao_declarada'


def peso(texto, rotulo=None, condicao=None):
    """Peso maximo do arquivo: {alvo_bytes, reprova_acima_bytes}. A unidade pode vir do cabecalho da tabela."""
    alertas = []
    achados = list(_RE_PESO.finditer(texto or ''))
    if achados:
        literais = [(m.group('n'), m.group('u')) for m in achados]
    else:
        m = _RE_NUMERO_SOLTO.match(texto or '')
        u = _RE_UNIDADE_ROTULO.search(rotulo or '')
        if not m or not u:
            return sem_valor()
        literais = [(m.group('n'), u.group('u'))]
        alertas.append('unidade_do_rotulo')
    # "Kb" e "Mb" (b minusculo) tambem se escrevem para bit: o motor le byte, mas avisa e nao escolhe pelo DA
    if any(un[-1:] == 'b' and un.lower() not in ('b', 'byte', 'bytes') for _lit, un in literais):
        alertas.append('unidade_bit_ou_byte')
    valores = []
    for lit, un in literais:
        n, al = numero(lit)
        if al:
            alertas.append(al)
        if n is None:
            return leitura(None, 'maximo', [lit], 'bytes', un, None, alertas, condicao)
        alvo, reprova, base = peso_em_bytes(n, un)
        valores.append(({'alvo_bytes': alvo, 'reprova_acima_bytes': reprova}, lit, un, base))
    forma = 'condicional' if condicao else 'maximo'
    if len(valores) == 1:
        v, lit, un, base = valores[0]
        return leitura(v, forma, [lit], 'bytes', un, base, alertas, condicao)
    # mais de um peso no mesmo trecho: o motor nao escolhe
    alertas.append('mais_de_um_numero')
    out = leitura(None, forma, [x[1] for x in valores], 'bytes', valores[0][2], valores[0][3], alertas, condicao)
    out['leituras'] = [leitura(v, forma, [lit], 'bytes', un, base, [], condicao) for v, lit, un, base in valores]
    return out


# ------------------------------------------------------------------ tipos de arquivo
def tipos(texto, rotulo=None):
    """Conjunto de MIME dos tipos citados ("JPG ou PNG", "JPG , PNG , HTML5 , GIF ANIMADO")."""
    n = normalizar(texto)
    partes = [p.strip(' .') for p in re.split(r',|/|\bou\b|\be\b|;', n) if p.strip(' .')]
    mimes, alertas = [], []
    for p in partes:
        mime = MIME_POR_NOME.get(p) or MIME_POR_NOME.get(p.lstrip('.'))
        if mime is None:
            alertas.append('tipo_nao_reconhecido')
        elif mime not in mimes:
            mimes.append(mime)
    if not mimes:
        return sem_valor()
    return leitura(mimes, 'conjunto', [], 'mime', None, None, alertas)


def tem_tipo(texto):
    return any(MIME_POR_NOME.get(p.strip(' .')) for p in re.split(r',|/|\bou\b|;', normalizar(texto)))


# ------------------------------------------------------------------ faixas, area segura, borda
def lados(texto):
    n = normalizar(texto)
    return sorted({LADOS[p] for p in re.findall(r'[a-z]+', n) if p in LADOS})


def faixa(texto, rotulo=None):
    """Faixa reservada ("Barra inferior 48px"): [{lado, px}]. O traco ("-") diz que nao ha faixa."""
    if _RE_SEM_VALOR.match(texto or ''):
        return leitura([], 'exato', [], 'px')
    achados = list(_RE_PX.finditer(texto or '')) or ([_RE_NUMERO_SOLTO.match(texto)] if _RE_NUMERO_SOLTO.match(texto or '') else [])
    if not achados:
        return sem_valor()
    lado = lados(rotulo or '') or lados(texto) or [None]
    alertas = [] if lado[0] else ['lado_nao_declarado']
    saida, numeros = [], []
    for m in achados:
        n, al = numero(m.group('n'))
        if al:
            alertas.append(al)
        numeros.append(m.group('n'))
        if n is None:
            return leitura(None, 'exato', numeros, 'px', 'px', None, alertas)
        saida.append({'lado': lado[0], 'px': _inteiro_se_der(n)})
    return leitura(saida, 'exato', numeros, 'px', 'px', None, alertas)


def area_segura(texto, rotulo=None):
    """Area segura: {pct, px, lados}. "cerca de" e "aprox." viram o alerta aproximado."""
    n = normalizar(texto)
    pcts, pxs, alertas, numeros = [], [], [], []
    for m in _RE_PCT.finditer(texto or ''):
        v, al = numero(m.group('n'))
        pcts.append(v)
        numeros.append(m.group('n'))
        if al:
            alertas.append(al)
    for m in _RE_PX.finditer(texto or ''):
        v, al = numero(m.group('n'))
        pxs.append(v)
        numeros.append(m.group('n'))
        if al:
            alertas.append(al)
    if not pcts and not pxs:
        return sem_valor()
    if len(pcts) > 1 or len(pxs) > 1:
        alertas.append('mais_de_um_numero')
        return leitura(None, 'exato', numeros, 'pct', None, None, alertas)
    if _RE_APROXIMADO.search(n):
        alertas.append('aproximado')
    valor = {'pct': _inteiro_se_der(pcts[0]) if pcts else None, 'px': _inteiro_se_der(pxs[0]) if pxs else None,
             'lados': lados(texto)}
    return leitura(valor, 'exato', numeros, 'pct' if pcts else 'px', None, None, alertas)


def borda(texto, rotulo=None):
    """Borda de 1 px: {espessura_px, cor}. Com "que tenham", "quando" ou "se", a forma e condicional e a condicao
    e o proprio texto original (o motor nao interpreta a condicao: o DA confere)."""
    achados = list(_RE_PX.finditer(texto or ''))
    if not achados:
        return sem_valor()
    if len(achados) > 1:
        return leitura(None, 'exato', [m.group('n') for m in achados], 'px', 'px', None, ['mais_de_um_numero'])
    v, al = numero(achados[0].group('n'))
    n = normalizar(texto)
    cor = next((c for c in CORES if re.search(r'\b%s\b' % c, n)), None)
    forma = forma_do_texto(texto)
    condicao = texto.strip() if forma == 'condicional' else None
    return leitura({'espessura_px': _inteiro_se_der(v), 'cor': cor}, forma, [achados[0].group('n')], 'px', 'px', None,
                   [al] if al else [], condicao)


_RE_MEDIDA = re.compile(r'(?P<n>%s)\s*(?P<u>px|mm|cm|m)(?![a-zA-Z])' % _NUM)


def medida(texto, rotulo=None):
    """Uma medida com unidade (sangria, margem de seguranca de impresso): {n, unidade}."""
    achados = list(_RE_MEDIDA.finditer(texto or ''))
    if not achados:
        return sem_valor()
    if len(achados) > 1:
        return leitura(None, 'exato', [m.group('n') for m in achados], None, None, None, ['mais_de_um_numero'])
    v, al = numero(achados[0].group('n'))
    un = achados[0].group('u')
    alertas = [a for a in (al,) if a] + ([] if un == 'px' else ['fora_do_escopo_v1'])
    return leitura(None if v is None else _inteiro_se_der(v), 'exato', [achados[0].group('n')], un, un, None, alertas)


def porcentagem(texto, rotulo=None):
    """Uma porcentagem (qualidade de JPG recomendada). Mais de uma no trecho: o motor nao escolhe."""
    achados = list(_RE_PCT.finditer(texto or ''))
    if not achados:
        return sem_valor()
    if len(achados) > 1:
        return leitura(None, 'exato', [m.group('n') for m in achados], 'pct', '%', None, ['mais_de_um_numero'])
    v, al = numero(achados[0].group('n'))
    return leitura(_inteiro_se_der(v), 'exato', [achados[0].group('n')], 'pct', '%', None, [al] if al else [])


def texto_livre(texto, rotulo=None):
    """Campo de texto (nome, ambiente, prazo, sufixo de arquivo): o texto literal, sem extrair numero dele. Sufixo
    de nome de arquivo fica literal e nunca vira geometria (arquitetura-v1.md, 4.8)."""
    t = ' '.join((texto or '').split())
    if not t:
        return sem_valor()
    return leitura(t, 'exato', [], None)


def lista_de_textos(texto, rotulo=None):
    partes = [p.strip() for p in re.split(r',|;', texto or '') if p.strip()]
    if not partes:
        return sem_valor()
    return leitura(partes, 'conjunto', [], None)


# ------------------------------------------------------------------ praca
# Unidades da federacao por nome (fato da divisao politica). Sao Paulo e Rio de Janeiro tambem sao nomes de
# municipio (a capital): o motor nao escolhe entre estado e municipio, e o DA decide.
UF_POR_NOME = {'acre': 'AC', 'alagoas': 'AL', 'amapa': 'AP', 'amazonas': 'AM', 'bahia': 'BA', 'ceara': 'CE',
               'distrito federal': 'DF', 'espirito santo': 'ES', 'goias': 'GO', 'maranhao': 'MA', 'mato grosso': 'MT',
               'mato grosso do sul': 'MS', 'minas gerais': 'MG', 'para': 'PA', 'paraiba': 'PB', 'parana': 'PR',
               'pernambuco': 'PE', 'piaui': 'PI', 'rio de janeiro': 'RJ', 'rio grande do norte': 'RN',
               'rio grande do sul': 'RS', 'rondonia': 'RO', 'roraima': 'RR', 'santa catarina': 'SC',
               'sao paulo': 'SP', 'sergipe': 'SE', 'tocantins': 'TO'}
UF_HOMONIMA_DA_CAPITAL = ('sao paulo', 'rio de janeiro')
SIGLAS_UF = frozenset(UF_POR_NOME.values())


def praca(texto, rotulo=None):
    """Praca normalizada: [{uf, municipio, texto_original}]. So vale o que a folha diz: municipio sem UF fica com uf
    None (o motor nao completa a UF de uma cidade), nome de estado fica sem municipio, e o nome que e estado e
    capital ao mesmo tempo fica ambiguo. Estado e cidade na mesma praca vira o alerta praca_mista."""
    t = ' '.join((texto or '').split())
    partes = [p.strip(' .') for p in re.split(r'\s*,\s*|\s+e\s+|\s*/\s*|\s*;\s*', t) if p.strip(' .')]
    if not partes:
        return sem_valor()
    itens, alertas, niveis = [], [], set()
    for p in partes:
        n = normalizar(p)
        sigla = p.upper() if p.upper() in SIGLAS_UF and len(p) == 2 else None  # numero-neutro: sigla de UF tem 2 letras
        if n in UF_HOMONIMA_DA_CAPITAL:
            itens.append({'uf': UF_POR_NOME[n], 'municipio': None, 'texto_original': p, 'ambiguidade': 'uf_ou_municipio'})
            alertas.append('praca_ambigua')
            niveis.add('ambiguo')
        elif n in UF_POR_NOME or sigla:
            itens.append({'uf': sigla or UF_POR_NOME[n], 'municipio': None, 'texto_original': p, 'ambiguidade': None})
            niveis.add('uf')
        else:
            itens.append({'uf': None, 'municipio': p, 'texto_original': p, 'ambiguidade': None})
            alertas.append('uf_nao_declarada')
            niveis.add('municipio')
    if 'uf' in niveis and 'municipio' in niveis:
        alertas.append('praca_mista')
    return leitura(itens, 'conjunto' if len(itens) > 1 else 'exato', [], None, None, None, alertas)


EXTRATORES = {'dimensao': dimensao, 'area_util': dimensao, 'area_visivel': dimensao, 'peso': peso,
              'tipos': tipos, 'faixa': faixa, 'area_segura': area_segura, 'borda': borda,
              'porcentagem': porcentagem, 'texto': texto_livre, 'lista': lista_de_textos, 'praca': praca,
              'medida': medida}
