# -*- coding: utf-8 -*-
"""Diferenca por formato em linguagem simples (M7b, A5): o que mudou num formato entre duas versoes, item a item, com
uma frase curta para o DA ("O título desceu 24 px", "O logo principal saiu da peça").

Compara dois corpos da impressao do formato (derivacao.impressao.corpo: a derivacao sem gerado_em, briefing_sha256,
inventario_entre_formatos e impressao_formato, e as entradas dele no briefing, no laudo e na folha), ja normalizados
como a impressao os resume. Cada item: {'tipo', 'elemento' (o id do elemento ou None), 'frase'} e, para moveu e
tamanho, 'antes' e 'depois' (as caixas, para a tela desenhar a caixa antiga).

Tipos, na ordem em que saem:
  - formato_novo e formato_saiu (um dos lados sem corpo);
  - situacao (o formato voltou para o DA ou ganhou proposta) e caminho (escala do KV, regras, mestre, galeria);
  - os campos do formato que o DA reconhece (tamanho e giro, areas, mestre, versao e edicoes da familia, PSD, fontes,
    versao do desdobra);
  - por elemento: entrou, saiu, apagado (pelo DA na familia, ou de volta), fora_da_peca (saiu da peca ou voltou),
    funcao, moveu (px e % do lado, pelo centro da caixa), tamanho (cresceu ou diminuiu em px), escala, regra, ancora,
    quebra, texto (o texto editado pelo DA), origem (origem_geometria), camadas, caixa na mestre e detalhe;
  - as camadas soltas que sairam da peca ou voltaram e as apagadas na familia que nao couberam num elemento;
  - os outros campos da derivacao (conferencias, restricoes, registros e o resto), so quando nada acima saiu;
  - entrada: a derivacao ficou igual e mudou o que a alimenta (funcao, regra, ancora, quebra aprovada, familia,
    folha de spec, formato no briefing, mestre); a frase diz que a peca ficou igual.
Toda mudanca de impressao da pelo menos um item: o que nenhum detector explica sai como detalhe (DETALHE_GERAL ou
ENTRADA_GERAL). Impressao igual nao da item. Funcao pura: nao le arquivo.
"""
import json

from desdobra.derivacao import impressao as mi

# o nome de cada funcao com o artigo, como a tela as mostra (tela.js FUNCOES)
ROTULO = {'fundo': 'o fundo', 'imagem': 'a imagem', 'sujeito': 'o sujeito',
          'veu_de_legibilidade': 'o véu de legibilidade', 'grafismo': 'o grafismo', 'titulo': 'o título',
          'texto_de_apoio': 'o texto de apoio', 'cta': 'o CTA', 'url_ou_contato': 'a URL ou contato',
          'texto_legal': 'o texto legal', 'informacao_de_evento': 'a informação de evento',
          'destaque_numerico': 'o destaque numérico', 'icone_de_cta': 'o ícone de CTA',
          'logo_principal': 'o logo principal', 'assinatura_institucional': 'a assinatura institucional',
          'selo': 'o selo', 'logo_de_parceiro': 'o logo de parceiro', 'indeterminado': 'a camada sem função definida',
          'ajuste_global': 'o ajuste global', 'estrutura': 'a estrutura', 'fora_da_peca': 'a camada fora da peça'}
ROTULO_GERAL = 'um elemento'
NOME_GERAL = 'outra função'
# as regras de escala em portugues (tela.js REGRAS; derivacao/escala.py REGRAS)
REGRAS = {'largura': 'pela largura', 'altura': 'pela altura', 'lado_curto': 'pelo lado menor',
          'lado_longo': 'pelo lado maior', 'raiz_area': 'pela área', 'constante': 'tamanho fixo',
          'contain': 'cabe inteiro na peça', 'cover': 'cobre a peça inteira'}
REGRA_GERAL = 'outra regra'
ANCORAS = {'esquerda': 'esquerda', 'centro': 'centro', 'direita': 'direita', 'topo': 'topo', 'meio': 'meio',
           'base': 'base'}
ANCORA_GERAL = 'outra posição'
ORIGENS = {'da': 'da sua edição', 'regra': 'das regras', 'transformacao': 'da escala do KV',
           'galeria': 'da versão da galeria', 'sugestao_citada': 'da sugestão citada'}
ORIGEM_GERAL = 'de outra origem'
CAMINHOS = {'transform': 'da escala do KV', 'solver': 'das regras', 'mestre_propria': 'da sua mestre',
            'galeria': 'da versão da galeria', 'devolvido': 'de lugar nenhum'}
CAMINHO_GERAL = 'de outro caminho'
CASAS_PORCENTO = 1  # numero-neutro: casas decimais do % do lado na frase
LADOS_DA_CAIXA = 4  # numero-neutro: a caixa e [x0, y0, x1, y1]
PAR = 2  # numero-neutro: a composicao e [largura, altura] e a ancora e [x, y]

# campos do formato que o DA reconhece: saem sempre que mudam
CAMPOS_DO_FORMATO = {
    'formato': 'O tamanho, a chave ou o giro do formato mudou.',
    'areas': 'A área útil, as faixas ou a área segura do formato mudaram.',
    'mestre': 'A mestre do formato mudou.',
    'proposta': 'A versão ou as edições da família deste formato mudaram.',
    'laudo_sha256': 'O PSD do job mudou.',
    'portao_fontes': 'A conferência das fontes mudou.',
    'motor_versao': 'A versão do desdobra mudou.',
}
# os outros campos da derivacao: saem so quando nada mais explica a mudanca
OUTROS_CAMPOS = {
    'validacoes': 'O resultado das conferências de layout do formato mudou.',
    'restricoes': 'As restrições de layout do formato mudaram.',
    'registros': 'Os registros da derivação do formato mudaram.',
    'parametros': 'Os parâmetros da derivação do formato mudaram.',
    'familia': 'A família do formato mudou.',
    'devolucao': 'O motivo de o formato voltar para você mudou.',
    'briefing_origem': 'A origem do briefing mudou.',
    'sem_geometria': 'As camadas sem desenho próprio mudaram.',
    'fora_do_canvas': 'As camadas fora do quadro do PSD mudaram.',
    'fora_do_quadro': 'As camadas fora do quadro do PSD mudaram.',
}
TRATADOS_A_PARTE = ('situacao', 'caminho', 'elementos', 'fora_da_peca', 'apagados_pelo_da')
DETALHE_GERAL = 'Um detalhe da derivação do formato mudou.'
ENTRADA_GERAL = 'Uma decisão do briefing que alimenta este formato mudou, e a peça ficou igual.'
IGUAL = ', e a peça ficou igual.'
ENTRADAS = {
    'composicao': 'A família deste formato mudou no briefing (versão, edições ou confirmação)' + IGUAL,
    'spec': 'A folha de spec deste formato mudou' + IGUAL,
    'formato': 'O formato mudou no briefing (chave, tamanho ou giro)' + IGUAL,
    'mestre': 'A sua mestre mudou' + IGUAL,
    'fora_da_peca': 'A lista de camadas fora da peça mudou no briefing' + IGUAL,
    'regras_indeterminado': 'A regra de uma camada sem função definida mudou no briefing' + IGUAL,
    'regras_bloco': 'A regra de um bloco de camadas mudou no briefing' + IGUAL,
    'funcoes': 'A função de uma camada mudou no briefing' + IGUAL,
    'regras': 'Uma regra de escala mudou no briefing' + IGUAL,
    'ancoras': 'Uma âncora mudou no briefing' + IGUAL,
    'quebras': 'As quebras de linha aprovadas mudaram' + IGUAL,
}


# ------------------------------------------------------------------ apoio
def _canon(v):
    return json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def _igual(a, b):
    return _canon(a) == _canon(b)


def _dic(x):
    return x if isinstance(x, dict) else {}


def _lista(x):
    return x if isinstance(x, list) else []


def _rotulo(funcao):
    return ROTULO.get(funcao, ROTULO_GERAL) if isinstance(funcao, str) else ROTULO_GERAL


def _nome(funcao):
    """O nome da funcao sem o artigo (o artigo e a primeira palavra do rotulo)."""
    r = ROTULO.get(funcao) if isinstance(funcao, str) else None
    return r.split(' ', 1)[1] if r else NOME_GERAL


def _maiuscula(t):
    return t[:1].upper() + t[1:]


def _de(rotulo):
    """'de' junto do artigo: do título, da imagem, de um elemento."""
    for artigo, junto in (('o ', 'do '), ('a ', 'da '), ('os ', 'dos '), ('as ', 'das ')):
        if rotulo.startswith(artigo):
            return junto + rotulo[len(artigo):]
    return 'de ' + rotulo


def _px(v):
    n = int(round(abs(v)))
    return 'menos de 1 px' if n == 0 else '%d px' % n


def _porcento(v, lado):
    return ('%.*f' % (CASAS_PORCENTO, 100 * abs(v) / lado)).replace('.', ',') + '%'


def _caixa(e):
    c = e.get('caixa')
    if isinstance(c, list) and len(c) == LADOS_DA_CAIXA and all(isinstance(v, (int, float)) and
                                                                not isinstance(v, bool) for v in c):
        return c
    return None


def _lado(d):
    """(largura, altura) da composicao do formato, ou None."""
    comp = _dic(d.get('formato')).get('composicao')
    if isinstance(comp, list) and len(comp) == PAR and all(isinstance(v, (int, float)) and v for v in comp):
        return comp
    return None


def _ancora(v):
    if isinstance(v, list) and len(v) == PAR:
        return '%s e %s' % tuple(ANCORAS.get(x, ANCORA_GERAL) if isinstance(x, str) else ANCORA_GERAL for x in v)
    return ANCORA_GERAL


def _regra(v):
    return REGRAS.get(v, REGRA_GERAL) if isinstance(v, str) else REGRA_GERAL


def _item(tipo, frase, elemento=None, **mais):
    return dict({'tipo': tipo, 'elemento': elemento, 'frase': frase}, **mais)


def _elementos(d):
    """{(id, n): elemento} na ordem da derivacao; n conta o id repetido."""
    saida, vistos = {}, {}
    for k, e in enumerate(_lista(d.get('elementos'))):
        e = _dic(e)
        eid = e.get('id') if isinstance(e.get('id'), str) else '#%d' % k
        vistos[eid] = vistos.get(eid, -1) + 1
        saida[(eid, vistos[eid])] = e
    return saida


def _ids_apagados(d):
    return {a.get('elemento') for a in _lista(d.get('apagados_pelo_da')) if isinstance(a, dict)}


def _camadas(e):
    return {x for x in _lista(e.get('layer_ids')) if isinstance(x, int)}


def _fora(d):
    return {x for x in _lista(d.get('fora_da_peca')) if isinstance(x, int)}


# ------------------------------------------------------------------ por elemento
def _movimento(eid, nome, a, b, lado):
    """Itens moveu e tamanho de uma caixa [x0, y0, x1, y1] para outra."""
    saida = []
    dx = (b[0] + b[2] - a[0] - a[2]) / 2
    dy = (b[1] + b[3] - a[1] - a[3]) / 2
    partes = []
    if dy:
        partes.append('%s %s' % ('desceu' if dy > 0 else 'subiu', _px(dy)) +
                      (' (%s da altura)' % _porcento(dy, lado[1]) if lado and int(round(abs(dy))) else ''))
    if dx:
        partes.append('foi %s para a %s' % (_px(dx), 'direita' if dx > 0 else 'esquerda') +
                      (' (%s da largura)' % _porcento(dx, lado[0]) if lado and int(round(abs(dx))) else ''))
    if partes:
        saida.append(_item('moveu', '%s %s.' % (_maiuscula(nome), ' e '.join(partes)), eid, antes=a, depois=b))
    partes, ultimo = [], None
    for delta, eixo in (((b[2] - b[0]) - (a[2] - a[0]), 'largura'), ((b[3] - b[1]) - (a[3] - a[1]), 'altura')):
        if delta:
            verbo = 'cresceu' if delta > 0 else 'diminuiu'
            partes.append(('%s na %s' % (_px(delta), eixo)) if verbo == ultimo else
                          ('%s %s na %s' % (verbo, _px(delta), eixo)))
            ultimo = verbo
    if partes:
        saida.append(_item('tamanho', '%s %s.' % (_maiuscula(nome), ' e '.join(partes)), eid, antes=a, depois=b))
    return saida


def _do_elemento(eid, a, b, lado):
    """Os itens de um elemento que esta nos dois lados."""
    nome = _rotulo(a.get('funcao'))
    saida = []
    if not _igual(a.get('funcao'), b.get('funcao')):
        saida.append(_item('funcao', '%s agora é %s.' % (_maiuscula(nome), _rotulo(b.get('funcao'))), eid))
    ca, cb = _caixa(a), _caixa(b)
    if ca and cb and not _igual(ca, cb):
        saida += _movimento(eid, nome, ca, cb, lado)
    elif not _igual(a.get('caixa'), b.get('caixa')):
        saida.append(_item('tamanho', 'A caixa %s mudou.' % _de(nome), eid))
    if _igual(a.get('caixa'), b.get('caixa')) and not _igual(a.get('escala'), b.get('escala')):
        saida.append(_item('escala', 'A escala %s mudou, com a mesma caixa.' % _de(nome), eid))
    if not _igual(a.get('regra'), b.get('regra')):
        saida.append(_item('regra', 'A regra de escala %s mudou: antes %s, agora %s.'
                           % (_de(nome), _regra(a.get('regra')), _regra(b.get('regra'))), eid))
    if not _igual(a.get('ancora'), b.get('ancora')):
        saida.append(_item('ancora', 'A âncora %s mudou: antes %s, agora %s.'
                           % (_de(nome), _ancora(a.get('ancora')), _ancora(b.get('ancora'))), eid))
    if not (_igual(a.get('quebras'), b.get('quebras')) and _igual(a.get('quebras_camada'), b.get('quebras_camada'))):
        saida.append(_item('quebra', 'As quebras de linha %s mudaram.' % _de(nome), eid))
    ta, tb = a.get('texto_editado'), b.get('texto_editado')
    if not _igual(ta, tb):
        frase = ('Você editou o texto %s.' if ta is None else
                 'O texto %s voltou ao do KV.' if tb is None else 'O texto %s mudou.') % _de(nome)
        saida.append(_item('texto', frase, eid))
    if not _igual(a.get('origem_geometria'), b.get('origem_geometria')):
        saida.append(_item('origem', 'A caixa %s agora vem %s (antes vinha %s).'
                           % (_de(nome), ORIGENS.get(b.get('origem_geometria'), ORIGEM_GERAL),
                              ORIGENS.get(a.get('origem_geometria'), ORIGEM_GERAL)), eid))
    if not _igual(a.get('layer_ids'), b.get('layer_ids')):
        saida.append(_item('camadas', 'As camadas %s mudaram.' % _de(nome), eid))
    if not _igual(a.get('caixa_mestre'), b.get('caixa_mestre')):
        saida.append(_item('caixa_mestre', 'A caixa %s na mestre mudou.' % _de(nome), eid))
    if not saida and not _igual(a, b):
        saida.append(_item('detalhe', 'Um detalhe %s mudou na derivação.' % _de(nome), eid))
    return saida


def _dos_elementos(da, db):
    """Itens dos elementos (entrou, saiu, apagado, fora_da_peca e os do elemento) e as camadas explicadas por eles."""
    ea, eb = _elementos(da), _elementos(db)
    apag_a, apag_b = _ids_apagados(da), _ids_apagados(db)
    fora_a, fora_b = _fora(da), _fora(db)
    lado = _lado(db) or _lado(da)
    saida, explicadas = [], set()
    for chave, a in ea.items():
        eid, nome = chave[0], _rotulo(a.get('funcao'))
        if chave in eb:
            saida += _do_elemento(eid, a, eb[chave], lado)
        elif eid in apag_b - apag_a:
            saida.append(_item('apagado', 'Você apagou %s nesta família.' % nome, eid))
        elif _camadas(a) and _camadas(a) <= fora_b - fora_a:
            saida.append(_item('fora_da_peca', '%s saiu da peça.' % _maiuscula(nome), eid))
            explicadas |= _camadas(a)
        else:
            saida.append(_item('saiu', '%s saiu do formato.' % _maiuscula(nome), eid))
    for chave, b in eb.items():
        if chave in ea:
            continue
        eid, nome = chave[0], _rotulo(b.get('funcao'))
        if eid in apag_a - apag_b:
            saida.append(_item('apagado', '%s voltou para esta família.' % _maiuscula(nome), eid))
        elif _camadas(b) and _camadas(b) <= fora_a - fora_b:
            saida.append(_item('fora_da_peca', '%s voltou para a peça.' % _maiuscula(nome), eid))
            explicadas |= _camadas(b)
        else:
            saida.append(_item('entrou', '%s entrou no formato.' % _maiuscula(nome), eid))
    if not saida and not _igual(da.get('elementos'), db.get('elementos')):
        saida.append(_item('detalhe', 'A ordem ou a lista dos elementos do formato mudou.'))
    return saida, explicadas


def _soltas(da, db, explicadas):
    """As camadas que sairam da peca ou voltaram sem caber num elemento, e as apagadas na familia que sobraram."""
    saida = []
    fora_a, fora_b = _fora(da), _fora(db)
    sairam, voltaram = len(fora_b - fora_a - explicadas), len(fora_a - fora_b - explicadas)
    if sairam:
        saida.append(_item('fora_da_peca', 'Uma camada saiu da peça.' if sairam == 1 else
                           '%d camadas saíram da peça.' % sairam))
    if voltaram:
        saida.append(_item('fora_da_peca', 'Uma camada voltou para a peça.' if voltaram == 1 else
                           '%d camadas voltaram para a peça.' % voltaram))
    if not saida and not explicadas and not _igual(da.get('fora_da_peca'), db.get('fora_da_peca')):
        saida.append(_item('fora_da_peca', 'A lista de camadas fora da peça mudou.'))
    return saida


# ------------------------------------------------------------------ o formato
def _do_formato(da, db):
    saida = []
    sa, sb = da.get('situacao'), db.get('situacao')
    if not _igual(sa, sb):
        if sb == 'devolvido':
            frase = 'O desdobra não fechou a proposta deste formato, e ele voltou para você.'
        elif sb == 'derivado':
            frase = 'O formato agora tem proposta.'
        else:
            frase = 'A situação do formato mudou.'
        saida.append(_item('situacao', frase))
    elif not _igual(da.get('caminho'), db.get('caminho')):
        saida.append(_item('caminho', 'O formato agora sai %s (antes saía %s).'
                           % (CAMINHOS.get(db.get('caminho'), CAMINHO_GERAL),
                              CAMINHOS.get(da.get('caminho'), CAMINHO_GERAL))))
    for k, frase in CAMPOS_DO_FORMATO.items():
        if not _igual(da.get(k), db.get(k)):
            saida.append(_item('formato', frase))
    return saida


def _outros(da, db):
    saida = []
    for k in sorted(set(da) | set(db)):
        if k in TRATADOS_A_PARTE or k in CAMPOS_DO_FORMATO or _igual(da.get(k), db.get(k)):
            continue
        frase = OUTROS_CAMPOS.get(k, DETALHE_GERAL)
        if frase not in [i['frase'] for i in saida]:
            saida.append(_item('detalhe', frase))
    if not _igual(da.get('apagados_pelo_da'), db.get('apagados_pelo_da')):
        saida.append(_item('apagado', 'As camadas que você apagou nesta família mudaram.'))
    return saida


# ------------------------------------------------------------------ so a entrada
def _pares(x):
    """{chave: valor} de uma lista de pares [chave, valor, ...] (a forma das entradas da impressao)."""
    saida = {}
    for p in _lista(x):
        if isinstance(p, list) and p and isinstance(p[0], (int, str)):
            saida[p[0]] = p[1:]
    return saida


def _funcao_da_camada(entradas, lid):
    v = _pares(entradas.get('funcoes')).get(lid)
    return _dic(v[0]).get('funcao') if v else None


def _das_entradas(ea, eb):
    saida = []
    for k in sorted(set(ea) | set(eb)):
        a, b = ea.get(k), eb.get(k)
        if _igual(a, b):
            continue
        frases = []
        if k == 'funcoes':
            pa, pb = _pares(a), _pares(b)
            for lid in sorted(set(pa) | set(pb), key=str):
                fa, fb = [_dic((p.get(lid) or [None])[0]).get('funcao') for p in (pa, pb)]
                if fa != fb and fa and fb:
                    frases.append('A função de uma camada mudou no briefing (antes %s, agora %s)%s'
                                  % (_nome(fa), _nome(fb), IGUAL))
        elif k == 'regras':
            pa, pb = _pares(a), _pares(b)
            for f in sorted(set(pa) | set(pb), key=str):
                if pa.get(f) != pb.get(f):
                    ra, rb = (pa.get(f) or [None])[0], (pb.get(f) or [None])[0]
                    detalhe = ' (antes %s, agora %s)' % (_regra(ra), _regra(rb)) if ra and rb else ''
                    frases.append('A regra de escala %s mudou no briefing%s%s' % (_de(_rotulo(f)), detalhe, IGUAL))
        elif k in ('ancoras', 'quebras'):
            pa, pb = _pares(a), _pares(b)
            for lid in sorted(set(pa) | set(pb), key=str):
                if pa.get(lid) != pb.get(lid):
                    nome = _de(_rotulo(_funcao_da_camada(eb, lid) or _funcao_da_camada(ea, lid)))
                    frases.append(('A âncora %s mudou no briefing' if k == 'ancoras' else
                                   'As quebras de linha aprovadas %s mudaram') % nome + IGUAL)
        if not frases:
            frases = [ENTRADAS.get(k, ENTRADA_GERAL)]
        for t in frases:
            if t not in [i['frase'] for i in saida]:
                saida.append(_item('entrada', t))
    return saida


# ------------------------------------------------------------------ entrada publica
def diferencas(antes, depois):
    """Lista de itens do que mudou no formato de antes para depois (corpos de derivacao.impressao.corpo; None quando
    o formato nao existe daquele lado). [] quando as impressoes sao iguais; pelo menos um item quando diferem."""
    if antes is None or depois is None:
        if antes is None and depois is None:
            return []
        return [_item('formato_novo', 'O formato entrou no job.') if antes is None else
                _item('formato_saiu', 'O formato saiu do job.')]
    if mi.do_corpo(antes) == mi.do_corpo(depois):
        return []
    da, db = _dic(antes.get('derivacao')), _dic(depois.get('derivacao'))
    if not _igual(da, db):
        saida = _do_formato(da, db)
        dos, explicadas = _dos_elementos(da, db)
        saida += dos + _soltas(da, db, explicadas)
        if not saida:
            saida = _outros(da, db)
    else:
        saida = _das_entradas(_dic(antes.get('entradas')), _dic(depois.get('entradas')))
    if not saida:
        # o que nenhum detector explica (o corpo mexido fora da forma da derivacao/1)
        saida = [_item('detalhe', ENTRADA_GERAL if _igual(da, db) else DETALHE_GERAL)]
    return saida


def do_formato(d_antes, briefing_antes, d_depois, briefing_depois, fid):
    """diferencas de duas derivacoes do formato fid, cada uma com o briefing resolvido dela (impressao.resolvido);
    None numa derivacao: o formato nao existe daquele lado."""
    antes = None if d_antes is None else mi.corpo(d_antes, briefing_antes, fid)
    depois = None if d_depois is None else mi.corpo(d_depois, briefing_depois, fid)
    return diferencas(antes, depois)
