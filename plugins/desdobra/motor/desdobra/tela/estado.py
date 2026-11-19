# -*- coding: utf-8 -*-
"""O que a tela so de leitura mostra (M7a2 e M7a3): os passos, as abas, o palco de cada composicao, as faces e os
assets do job.

  - lido (passo 1, "O que eu li"): bloqueios das fases e das camadas, linkados, valores de spec por situacao, modo de
    dados e fontes (decisoes-v1.md n 161); e, desde a revisao do M7a, os formatos com o giro escolhido pelo DA (e o que
    a folha diz do giro, como dica) e as pranchetas do PSD com a previa de cada uma, para o DA escolher de qual a peca
    sai. As duas escolhas ficam no rascunho da tela (desdobra.tela.rascunho.CAMPOS_DO_PASSO_1);
  - funcoes (passo 2, "Funcoes"): a arvore dos grupos do laudo com a funcao resolvida de cada camada e de onde ela vem
    (da propria camada, herdada do grupo ou pela regra da decisao 10; briefing.modelo.resolver), o resumo das regras e
    das ancoras por funcao e o palco do KV, no centro; e, desde a fatia 3 do M7a, as decisoes que o DA toma na tela
    (decisoes_do_passo_2: os nos e as opcoes do esquema, sem valor; as escolhas vao ao rascunho da tela);
  - abas: orientacao da composicao (escala.orientacao, banda derivacao.quadrado_ln_max) e, dentro dela, os grupos
    de composicoes de proporcao parecida (revisao da 163 em 05/11: lado longo sobre lado curto, amplitude ate
    derivacao.grupo_proporcao_dif_max, por ligacao completa), qualquer que seja a familia da derivacao (a mestre que
    ela escolheu, ou SEM_FAMILIA para o formato que volta ao DA, fica como dado da composicao). Cada composicao
    (largura x altura depois do giro) lista os formatos que ela gera, com o giro, e marca a escala pura (o caminho
    transform da derivacao: mesma proporcao da mestre). O id de cada grupo e o id da familia, preso aos formatos dela
    (revisao do M7b, fase A): o grupo fica com o id que o job ja conhece e com que divide mais formatos, e a tela avisa
    o DA quando a familia ganhou ou perdeu formatos desde que ele mexeu nela;
  - previas: o palco de cada formato (palco), montado da derivacao do motor em memoria (derivacao.nucleo.preparar e
    derivar_em_memoria), nada gravado. Cada camada do elemento vira uma peca, na transformacao do elemento
    (destino + (caixa - origem) * s) e no recorte dele: a imagem da camada pelo asset por id, ou o texto com a face do
    job (casamento.casar do nome PostScript do trecho). A tinta do texto e medida no Chromium (tela.js), nunca aqui;
  - fantasmas (n 162, opcao A): elemento sem regra, e todo elemento do KV num formato devolvido, aparece hachurado na
    escala pura da mestre (contain, centrado), com o selo "apoio de desenho, nao gravado". O fantasma e so desenho:
    nao tem regra nem ancora inventada e nunca vai a arquivo nenhum;
  - galeria (n 164 e notas de 05/11): o formato devolvido (troca de orientacao ou proporcao fora da faixa) chega com
    as variantes da galeria do motor (derivacao.galeria.variantes), cada uma com o palco dela no mesmo modelo das
    pecas; no grupo de proporcao com mais de um devolvido, cada variante leva a mesma estrutura a todos os membros
    (variante_para_grupo). So previa: nada gravado, e o que o derivar grava nao muda;
  - faltam: a lista unica do que falta, cada item com o lugar da tela que leva a ele (so leitura no M7a0);
  - fontes: as faces do job (fontes/bruto/<sha>/leitura.json e entrada/fontes/), com os bytes como a conferencia as
    serve ao Chromium (a face de um .ttc emendada, conferencia.bytes_para_servir). O processo nunca abre a fonte: so
    copia bytes;
  - assets: o PNG dos pixels proprios de cada camada (laudo/bruto/<sha>/estrutura.json, pixels.asset_sha256, em
    laudo/assets/), com id a001, a002... por sha256, lidos como bytes e nunca decodificados.

Nada daqui vai ao Claude: o conteudo so sai pelo servidor da tela (desdobra.tela.servidor) para o Chromium que o
motor abre. Texto do cliente (nome de camada, texto do PSD, nome de fonte) vai como dado; a pagina o poe so por
textContent.
"""
import math
import re
from pathlib import Path

from desdobra import limites
from desdobra.derivacao import escala
from desdobra.resultado import Codigo

ESQUEMA = 'tela-estado/1'
SEM_FAMILIA = 'sem_familia'
ORIENTACOES = ('horizontal', 'quadrado', 'vertical')
ROTULOS = {'horizontal': 'Horizontal', 'quadrado': 'Quadrado', 'vertical': 'Vertical', SEM_FAMILIA: 'Sem proposta ainda',
           'kv': 'Mestre do KV'}
ASSINATURA_PNG = bytes([137, 80, 78, 71, 13, 10, 26, 10])  # numero-neutro: assinatura do PNG
COR = re.compile(r'^#[0-9A-Fa-f]{6}$')
SEPARADOR_DE_LINHA = re.compile('[\r\n\x03]')  # fim de paragrafo (\r) e quebra manual (\x03) do texto do PSD
ALINHAMENTOS = {'LEFT': 'esquerda', 'CENTER': 'centro', 'RIGHT': 'direita'}
POR = {'camada': 'camada', 'grupo': 'grupo', 'decisao_10': 'decisao_10'}
# a regra com que a tela monta a previa da familia, na impressao da confirmacao (impressao_das_pecas; decisao 175):
# muda quando a previa passa a mostrar outra coisa para a mesma familia, e a confirmacao de antes cai. Esta e a da
# previa igual ao Salvar (M7b), com o alinhamento so do mexido (decisao 185): a galeria pela regra da derivacao, as
# falhas da conferencia do motor e a edicao que so move o que o DA acabou de mexer
# 0.9.6 (decisao 196, proposta da 198): o texto editado vale nas linhas do DA (caixa_visivel) para alinhar, para o
# Tamanho e para a conferencia. A previa da familia com texto editado muda, e a confirmacao feita antes dela cai
# 0.10.0 (decisao 199): os outros arquivos da familia copiam o layout aprovado no arquivo de edicao, e a impressao
# leva o arquivo de edicao. A confirmacao feita antes cai uma vez, tambem na familia sem edicao (resposta 3 do Duda em
# 18/11), com a frase RECONFIRMAR_0100
REGRA_DA_PREVIA = 'arquivo_de_edicao'
# a frase da familia confirmada antes da 0.10.0, no lugar do aviso da familia, ate o DA confirmar de novo
RECONFIRMAR_0100 = ('Esta família foi confirmada antes da versão 0.10.0 do desdobra. Agora os outros arquivos seguem o '
                    'layout do arquivo de edição, e por isso ela pede a sua confirmação de novo. Confira os arquivos e '
                    'confirme outra vez.')
# a regra de antes da 0.9.6: a familia sem texto editado mostra a mesma previa pelas duas, e a confirmacao dela
# continua valendo (rascunho.confirmada_para, sem_texto)
REGRA_SEM_TEXTO_EDITADO = 'alinha_so_o_mexido'
# a regra de antes da decisao 185: a previa da familia sem edicao do DA e a mesma pelas duas (sem edicao nao ha o que
# alinhar), e a familia vista por ela sem nenhuma edicao continua valendo (rascunho.confirmada_para, sem_edicao)
REGRA_SEM_EDICAO = 'previa_igual_ao_salvar'
# O que a tela diz do formato que a derivacao devolve, em lugar do o_que_fazer do motor: o DA nunca e chamado a
# desenhar uma mestre por orientacao (n 164 e comentarios de 05/11), e o texto da tela nao leva identificador do motor.
PROPOSTA_DEPOIS = 'A proposta do desdobra para este arquivo chega com a galeria de variantes, na próxima versão.'
SEM_VERSOES = 'O desdobra não conseguiu montar versões para este arquivo.'
SELO_VARIANTE = 'variante'
MOTIVOS_TELA = {
    'troca_forte_de_orientacao': 'A orientação muda em relação ao KV.',
    'troca_de_orientacao_quadrado': 'A peça passa para o quadrado, ou sai dele, em relação ao KV.',
    'fora_da_faixa_de_familia': 'A proporção fica longe da proporção do KV.',
}
MOTIVO_GERAL = 'O desdobra ainda não chegou a uma proposta para este formato.'
# o formato com um valor de spec que espera a confirmacao do DA (revisao dos becos, A1): a previa e a lista do que
# falta levam ao passo 1, sem galeria (o desdobra so monta a peca com os valores confirmados), e a familia dele so e
# confirmada depois (o DA nunca confirma uma familia sem ver a galeria de cada formato)
SPEC_POR_CONFIRMAR = ('Um valor de spec deste formato ainda espera a sua confirmação. Confirme os valores dele em '
                      'Valores de spec, no passo 1, e o desdobra monta a peça com os valores confirmados.')
SPEC_POR_CONFIRMAR_FALTA = 'Confirme os valores deste formato em Valores de spec, no passo 1.'
# o formato que deriva da mestre propria do DA cujo formato espera um valor de spec (revisao dos becos, D3): espera
# com ela, como o formato da mestre, sem galeria e com a familia sem confirmacao
MESTRE_POR_CONFIRMAR = ('O formato da mestre desta família ainda espera a confirmação de um valor de spec. Confirme os '
                        'valores dele em Valores de spec, no passo 1, e o desdobra monta as peças da família com os '
                        'valores confirmados.')
# o formato da folha com duas medidas, sem a escolha do DA (revisao dos becos, D2): sem medida nao ha chave nem peca, e
# ele aparece pelo que a folha diz, nunca pelo identificador interno
ONDE_SEM_MEDIDA = 'Formato da folha com duas medidas: %s'
# o mesmo formato na frase da janela de confirmacao ("No formato da folha com duas medidas (...), o campo ...")
FRASE_SEM_MEDIDA = 'formato da folha com duas medidas (%s)'
MEDIDA_A_ESCOLHER_FALTA = ('Um formato da folha traz duas medidas. Escolha a medida dele em Valores de spec, no '
                           'passo 1, e ele entra nos formatos do job.')
MESTRE_POR_CONFIRMAR_FALTA = 'Confirme os valores do formato da mestre desta família em Valores de spec, no passo 1.'


def _versoes(n):
    return '%d versão' % n if n == 1 else '%d versões' % n


def texto_da_devolucao(motivo, variantes=None):
    """A frase da tela para o formato devolvido, sem identificador do motor e sem pedir mestre propria. variantes:
    quantas a galeria montou (None: a galeria nao foi montada)."""
    from desdobra.derivacao import nucleo as nd
    if motivo == nd.MOTIVO_SPEC_POR_CONFIRMAR:
        return SPEC_POR_CONFIRMAR
    if motivo == nd.MOTIVO_MESTRE_POR_CONFIRMAR:
        return MESTRE_POR_CONFIRMAR
    if variantes:
        depois = 'O desdobra montou %s com os blocos do próprio KV.' % _versoes(variantes)  # a nota da galeria pede a escolha
    elif variantes is None:
        depois = PROPOSTA_DEPOIS
    else:
        depois = SEM_VERSOES
    if motivo in MOTIVOS_TELA:
        return MOTIVOS_TELA[motivo] + ' ' + depois
    return MOTIVO_GERAL if variantes is None else MOTIVO_GERAL + ' ' + depois


class ErroTela(Exception):
    def __init__(self, mensagem, motivo):
        super().__init__(mensagem)
        self.motivo = motivo


# ------------------------------------------------------------------ abas
def _rotulo_familia(fam, mestre):
    if fam in ROTULOS:
        return ROTULOS[fam]
    if (mestre or {}).get('tipo') == 'propria':
        return 'Mestre própria'
    return fam


def proporcao(largura, altura):
    """Lado longo sobre lado curto: a mesma medida nas duas orientacoes (decisoes-v1.md, revisao da 163 em 05/11)."""
    return max(largura, altura) / float(min(largura, altura))


def agrupar_por_proporcao(composicoes):
    """Grupos de composicoes de proporcao parecida, dentro de uma orientacao (revisao da 163 em 05/11): ligacao
    completa, a diferenca entre a maior e a menor proporcao do grupo ate derivacao.grupo_proporcao_dif_max. Em uma
    dimensao a ligacao completa so junta vizinhos: as composicoes vao em ordem de proporcao (e de id, no empate) e, a
    cada passo, junta-se o par vizinho de menor amplitude (o primeiro, no empate) enquanto ela couber no limite. A
    cadeia nao passa: 2,0 e 2,2 juntam, 2,2 e 2,4 tambem cabem, mas os tres nao. Devolve listas na ordem da entrada
    ordenada; a amplitude vai nas casas do estado da tela (_arred), para o empate nao depender do float."""
    limite = float(limites.valor('derivacao.grupo_proporcao_dif_max'))
    itens = sorted(composicoes, key=lambda c: (proporcao(c['largura'], c['altura']), c['id']))
    grupos = [[c] for c in itens]

    def amplitude(g):
        ps = [proporcao(c['largura'], c['altura']) for c in g]
        return _arred(max(ps) - min(ps))
    while len(grupos) > 1:
        melhor = min(range(len(grupos) - 1), key=lambda i: (amplitude(grupos[i] + grupos[i + 1]), i))
        if amplitude(grupos[melhor] + grupos[melhor + 1]) > limite:
            break
        grupos[melhor:melhor + 2] = [grupos[melhor] + grupos[melhor + 1]]
    return grupos


def familias_conhecidas(pasta):
    """{id da familia: [formatos] ou None} das familias que o job ja conhece (revisao do M7b, fase A): as do rascunho
    da tela, com os formatos que a tela mostrava quando o DA mexeu nelas (ou, no rascunho de antes desta revisao, os
    da confirmacao), e as composicoes do briefing gravado, mesmo de outra versao dos arquivos do job (o id e os
    formatos dele continuam dizendo de onde as edicoes vieram). O rascunho vale sobre o briefing; None e o id do
    rascunho velho sem formato nenhum (abas o deixa com o grupo da mesma posicao, como antes)."""
    from desdobra import contratos
    from desdobra.briefing import modelo as mb
    from desdobra.tela import rascunho
    saida = {}
    try:
        gravado = mb.ler(pasta)
    except contratos.ErroContrato:
        gravado = None
    for c in (gravado or {}).get('composicoes') or []:
        saida[c['familia']] = list(c['formatos'])
    dados, _de_outro = rascunho.ler(pasta, rascunho.laudo_sha256(pasta))
    for gid, f in ((dados or {}).get('familias') or {}).items():
        fids = f.get('formatos')
        if fids is None:
            fids = (f.get('confirmacao') or {}).get('formatos')
        if fids is not None:
            saida[gid] = list(fids)
        else:
            saida.setdefault(gid, None)
    return saida


def marcas_das_familias(pasta):
    """(editadas, cedidos) das familias que o job ja conhece, para a frase da tela (revisao do M7b, fase A).
    editadas: os ids com edicao no palco ou quebra de linha (o rascunho vale sobre o briefing gravado), e so delas a
    frase diz que as edicoes ficam guardadas; cedidos: {id: [formatos]} que outra familia levou depois que o DA mexeu
    nesta (desdobra.tela.rascunho._ceder): o formato que volta para ela entrou de novo, mesmo estando na lista velha."""
    from desdobra import contratos
    from desdobra.briefing import modelo as mb
    from desdobra.tela import rascunho
    try:
        gravado = mb.ler(pasta)
    except contratos.ErroContrato:
        gravado = None
    # a quebra de linha da familia tambem e edicao dela (M7b, C4; decisoes-v1.md, 171)
    com_quebra = {q['familia'] for q in (gravado or {}).get('quebras_por_familia') or [] if q.get('familia')}
    editadas = {c['familia'] for c in (gravado or {}).get('composicoes') or []
                if c.get('edicoes') or c['familia'] in com_quebra}
    dados, _de_outro = rascunho.ler(pasta, rascunho.laudo_sha256(pasta))
    cedidos = {}
    for gid, f in ((dados or {}).get('familias') or {}).items():
        if f.get('edicoes') or f.get('quebras'):
            editadas.add(gid)
        else:
            editadas.discard(gid)
        if f.get('cedidos'):
            cedidos[gid] = list(f['cedidos'])
    return editadas, cedidos


def _chave_do_id(gid):
    """A ordem dos ids no empate: '<orientacao>-<n>' pelo numero, os outros pelo texto depois deles."""
    ori, _traco, n = gid.rpartition('-')
    if ori in ORIENTACOES and n.isdigit():
        return (0, ORIENTACOES.index(ori), int(n), '')
    return (1, 0, 0, gid)


def _serve_para(gid, ori):
    """O id conhecido pode ir a um grupo desta orientacao: o '<outra orientacao>-<n>' nunca (o formato girado parte
    da proposta, e as edicoes do id ficam para quando ele voltar); o id que nao diz orientacao segue os formatos."""
    outra, _traco, n = gid.rpartition('-')
    return not (outra in ORIENTACOES and n.isdigit() and outra != ori)


def _lista(fids, nomes=None):
    # revisao da 0.10.0: a frase diz o nome do arquivo para o DA (nomes_dos_arquivos), e nunca o id interno
    nomes = nomes or {}
    fids = [nomes.get(f, f) for f in sorted(fids)]
    return fids[0] if len(fids) == 1 else '%s e %s' % (', '.join(fids[:-1]), fids[-1])


def _frase_dos_formatos(fids, um, varios, nomes=None):
    return (um if len(fids) == 1 else varios) % _lista(fids, nomes)


def aviso_da_familia(entraram, sairam, de_outra, nomes=None):
    """A frase da tela para a familia que mudou de formatos desde que o DA mexeu nela (revisao do M7b, fase A).
    entraram e sairam: os formatos que entraram e sairam da familia de mesmo id; de_outra: os que entraram vindos de
    outra familia conhecida com edicao (as edicoes de la ficam guardadas no rascunho e nao valem aqui)."""
    partes = []
    if entraram:
        partes.append(_frase_dos_formatos(entraram, 'entrou o formato %s', 'entraram os formatos %s', nomes))
    if sairam:
        partes.append(_frase_dos_formatos(sairam, 'saiu o formato %s', 'saíram os formatos %s', nomes))
    texto = 'Esta família mudou desde a última vez: %s.' % ' e '.join(partes)
    if de_outra:
        texto += ' ' + _frase_dos_formatos(
            de_outra, 'O que você editou para o formato %s em outra família fica guardado e não vale aqui.',
            'O que você editou para os formatos %s em outra família fica guardado e não vale aqui.', nomes)
    return texto + ' Olhe a família de novo e confirme outra vez.'


def aviso_de_familia_nova(de_outra, com_edicoes=False, nomes=None):
    """A frase da tela para a familia nova com formatos que estavam em outra familia conhecida (a parte que saiu de
    uma familia dividida): ela parte da proposta, e, quando a familia de la tinha edicao (com_edicoes), sem elas."""
    return (_frase_dos_formatos(de_outra, 'Esta família é nova: o formato %s estava em outra família.',
                                'Esta família é nova: os formatos %s estavam em outra família.', nomes) +
            (' Ela parte da proposta do desdobra, sem as edições de lá.' if com_edicoes else
             ' Ela parte da proposta do desdobra.') + ' Olhe a família e confirme.')


def _aviso(gid, fids, conhecidas, editadas, cedidos, nomes=None):
    """A frase da familia gid, hoje com os formatos fids (um conjunto), contra o que o job conhece dela: conhecidas
    {id: conjunto de formatos}, editadas (ids com edicao) e cedidos {id: formatos que outra familia levou depois}. O
    formato cedido que esta de novo na familia entrou de novo: o DA mexeu nele em outra familia no meio tempo."""
    de_editada = {f for g, fk in conhecidas.items() if g != gid and g in editadas for f in fk & fids}
    if gid in conhecidas:
        entraram = (fids - conhecidas[gid]) | (fids & set(cedidos.get(gid) or ()))
        sairam = conhecidas[gid] - fids
        return aviso_da_familia(entraram, sairam, de_editada & entraram, nomes) if entraram or sairam else ''
    de_outra = {f for g, fk in conhecidas.items() if g != gid for f in fk & fids}
    return aviso_de_familia_nova(de_outra, bool(de_editada), nomes) if de_outra else ''


def avisos_das_familias(pasta, familias, nomes=None):
    """{id: frase} das familias que a tela mostra (familias: {id: [formatos]}, os ids ja dados por abas), contra o
    que o job conhece agora: depois de um ato (a familia confirmada) a frase muda sem os ids mudarem. O id conhecido
    sem formatos (o rascunho velho) vale com os formatos do grupo de mesmo id."""
    conhecidas = {g: set(familias.get(g, ()) if f is None else f) for g, f in familias_conhecidas(pasta).items()}
    editadas, cedidos = marcas_das_familias(pasta)
    return {gid: _aviso(gid, set(fids), conhecidas, editadas, cedidos, nomes) for gid, fids in familias.items()}


def _ids_das_familias(grupos, conhecidas, editadas=(), cedidos=None, nomes=None):
    """Os ids dos grupos da tela, na ordem de grupos ([(orientacao, {formatos})], na ordem das abas), e o aviso de
    cada um (revisao do M7b, fase A). Cada grupo fica com o id conhecido (conhecidas: {id: [formatos] ou None}) com
    que divide mais formatos; no empate, o de menos diferenca, depois o grupo que vem antes nas abas e o id menor.
    Cada id vai a um grupo so, e o grupo sem formato em comum com id nenhum ganha o menor '<orientacao>-<n>' que
    nenhum id conhecido usa (o id que sumiu da tela fica reservado: as edicoes dele nunca passam para outros
    formatos). Sem id conhecido, a numeracao e a posicao do grupo na orientacao, como antes desta revisao. O id
    conhecido sem formatos (None, o rascunho velho) fica com os formatos do grupo da mesma posicao. editadas e
    cedidos: marcas_das_familias (a frase de cada grupo, _aviso)."""
    posicao, contagem = [], {}
    for ori, _fids in grupos:
        contagem[ori] = contagem.get(ori, 0) + 1
        posicao.append('%s-%d' % (ori, contagem[ori]))
    conhecidas = dict(conhecidas or {})
    for gid in [g for g, f in conhecidas.items() if f is None]:
        conhecidas[gid] = set(grupos[posicao.index(gid)][1]) if gid in posicao else set()
    conhecidas = {g: set(f) for g, f in conhecidas.items()}
    pares = []
    for i, (ori, fids) in enumerate(grupos):
        for gid, fk in conhecidas.items():
            comum = len(fids & fk)
            if comum and _serve_para(gid, ori):
                pares.append(((-comum, len(fids ^ fk), i, _chave_do_id(gid)), i, gid))
    ids, usados = [None] * len(grupos), set()
    for _chave, i, gid in sorted(pares):
        if ids[i] is None and gid not in usados:
            ids[i] = gid
            usados.add(gid)
    reservados = set(conhecidas) | usados
    for i, (ori, _fids) in enumerate(grupos):
        if ids[i] is None:
            n = 1
            while '%s-%d' % (ori, n) in reservados:
                n += 1
            ids[i] = '%s-%d' % (ori, n)
            reservados.add(ids[i])
    avisos = [_aviso(ids[i], fids, conhecidas, set(editadas or ()), cedidos or {}, nomes)
              for i, (_ori, fids) in enumerate(grupos)]
    return ids, avisos


def _separar_grupos(grupos, separados):
    """Os grupos da orientacao com cada arquivo separado pelo DA (decisao 199, 3) num grupo dele, logo depois do grupo
    de onde saiu: a composicao que tinha mais arquivos fica com os outros. separados: o conjunto dos ids."""
    saida = []
    for g in grupos:
        fora = []
        comps = []
        for c in g['composicoes']:
            ficam = [x for x in c['formatos'] if x['id'] not in separados]
            for x in c['formatos']:
                if x['id'] in separados:
                    fora.append(dict(c, formatos=[x]))
            if ficam:
                comps.append(dict(c, formatos=ficam))
        if comps:
            ps = [c['proporcao'] for c in comps]
            saida.append(dict(g, proporcao=[min(ps), max(ps)], escala_pura=all(c['escala_pura'] for c in comps),
                              composicoes=comps))
        for c in fora:
            saida.append({'proporcao': [c['proporcao'], c['proporcao']], 'escala_pura': c['escala_pura'],
                          'composicoes': [c]})
    return saida


def abas(laudo, briefing, formatos, variantes=None, conhecidas=None, editadas=(), cedidos=None, arquivos=None,
         separados=None):
    """[{'id', 'rotulo', 'grupos': [{'id', 'proporcao': [menor, maior], 'escala_pura', 'aviso', 'composicoes': [{'id',
    'largura', 'altura', 'proporcao', 'escala_pura', 'familia', 'rotulo_familia', 'formatos': [...]}]}]}] na ordem
    horizontal, quadrado, vertical. Dentro da orientacao, as composicoes de proporcao parecida formam um grupo (uma aba
    da tela; agrupar_por_proporcao), qualquer que seja a familia da derivacao: a faixa de familia deixa de separar o
    que a tela agrupa (n 163). formatos: {id: derivacao/1}; variantes: {id: quantas variantes a galeria montou}.
    O id do grupo e o id da familia (o rascunho, os atos e o briefing gravam por ele): desde a revisao do M7b, fase A,
    ele fica preso aos formatos, e nao a posicao do grupo na aba. conhecidas: {id: [formatos] ou None} das familias
    que o job ja conhece (familias_conhecidas); a ordem das abas continua pela proporcao (_ids_das_familias). aviso: a
    frase da tela quando a familia mudou de formatos desde que o DA mexeu nela, ou ''. editadas e cedidos:
    marcas_das_familias (a frase so fala das edicoes que existem, e o formato que volta de outra familia entra).
    arquivos e separados (decisao 199; 0.10.0; desdobra.tela.rascunho.estrutura): {id: arquivo de edicao gravado} e
    {id: [arquivos separados dela]}. Cada grupo leva 'arquivo_de_edicao' (o gravado, enquanto estiver no grupo, senao
    a regra), 'separados' (os que o DA separou dele) e, no grupo de um arquivo separado, 'separado_de' (o id de onde
    ele saiu)."""
    variantes = variantes or {}
    arquivos = arquivos or {}
    separados = {g: list(v) for g, v in (separados or {}).items()}
    todos_separados = {f for v in separados.values() for f in v}
    ordem_briefing = [f['id'] for f in briefing['formatos']]
    por_ori = {}
    for fid in ordem_briefing:
        d = formatos.get(fid)
        if d is None:
            continue
        W, H = d['formato']['composicao']
        ori = escala.orientacao(W, H)
        fam = (d.get('mestre') or {}).get('id') if d['situacao'] == 'derivado' else None
        fam = fam or SEM_FAMILIA
        comp_id = 'c%dx%d-%s' % (W, H, fam)
        mestre = d.get('mestre') if fam != SEM_FAMILIA else None
        comps = por_ori.setdefault(ori, {})
        c = comps.setdefault(comp_id, {'id': comp_id, 'largura': int(W), 'altura': int(H),
                                       'proporcao': _arred(proporcao(W, H)), 'escala_pura': False, 'familia': fam,
                                       'rotulo_familia': _rotulo_familia(fam, mestre), 'formatos': []})
        if d.get('caminho') == 'transform':
            c['escala_pura'] = True
        c['formatos'].append({'id': fid, 'largura': d['formato']['largura'], 'altura': d['formato']['altura'],
                              'rotacao_graus': ((d['formato'].get('rotacao') or {}).get('graus')) or 0,
                              'situacao': d['situacao'], 'caminho': d.get('caminho'),
                              'motivo': (d.get('devolucao') or {}).get('motivo'),
                              'variantes': int(variantes.get(fid, 0))})
    saida = []
    for ori in ORIENTACOES:
        if ori not in por_ori:
            continue
        grupos = []
        for membros in agrupar_por_proporcao(list(por_ori[ori].values())):
            membros = sorted(membros, key=lambda c: (-c['largura'] / c['altura'], c['id']))
            ps = [c['proporcao'] for c in membros]
            grupos.append({'proporcao': [min(ps), max(ps)], 'escala_pura': all(c['escala_pura'] for c in membros),
                           'composicoes': membros})
        grupos.sort(key=lambda g: (-g['composicoes'][0]['largura'] / g['composicoes'][0]['altura'],
                                   g['composicoes'][0]['id']))
        if todos_separados:
            grupos = _separar_grupos(grupos, todos_separados)
        saida.append({'id': ori, 'rotulo': ROTULOS[ori], 'grupos': grupos})
    todos = [(o['id'], g) for o in saida for g in o['grupos']]
    nomes = nomes_dos_formatos_da_derivacao(formatos, ordem_briefing)
    for _ori, g in todos:
        for c in g['composicoes']:
            for x in c['formatos']:
                # o nome do arquivo para o DA (revisao da 0.10.0): a medida e o giro, como no passo 5
                x['nome'] = nomes.get(x['id'], x['id'])
    ids, avisos = _ids_das_familias([(ori, {x['id'] for c in g['composicoes'] for x in c['formatos']})
                                     for ori, g in todos], conhecidas, editadas, cedidos, nomes)
    from desdobra.derivacao import proposta
    for (_ori, g), gid, aviso in zip(todos, ids, avisos):
        g['id'], g['aviso'] = gid, aviso
        # decisao 199 (1): o arquivo de edicao da familia, o gravado no rascunho enquanto estiver nela, senao pela
        # mesma regra da previa e da derivacao (o de maior area na composicao; no empate, o sem giro, depois o
        # primeiro da lista). separados: os arquivos que o DA separou em familia propria (decisao 199, 3)
        fids = [x['id'] for c in g['composicoes'] for x in c['formatos']]
        # revisao da 0.10.0 (a migracao): sem escolha gravada, a regra vale entre os formatos que a familia ja tinha
        # (conhecidas); o irmao maior que entrou depois nunca toma o lugar do arquivo ja aprovado
        g['arquivo_de_edicao'] = proposta.arquivo_de_edicao([dict(formatos[f]['formato'], id=f) for f in fids],
                                                            arquivos.get(gid), (conhecidas or {}).get(gid))
        g['separados'] = [f for f in separados.get(gid) or () if f not in fids]
        mae = next((m for m, v in sorted(separados.items()) if len(fids) == 1 and fids[0] in v and m != gid), None)
        if mae is not None:
            g['separado_de'] = mae
    for o in saida:
        o['grupos'] = [dict({'id': g.pop('id')}, **g) for g in o['grupos']]
    return saida


# ------------------------------------------------------------------ pecas do palco
def _arred(v):
    return round(float(v), 4)  # numero-neutro: casas decimais do pixel no estado da tela


def _mapear(caixa, tr):
    """Caixa do documento para a composicao: destino + (caixa - origem) * s."""
    s, (ox, oy), (dx, dy) = float(tr['s']), tr['origem_doc'], tr['destino']
    return [_arred(dx + (caixa[0] - ox) * s), _arred(dy + (caixa[1] - oy) * s), _arred(dx + (caixa[2] - ox) * s),
            _arred(dy + (caixa[3] - oy) * s)]


def _linhas(texto, face_de, juntar=(), inserir=()):
    """Linhas do texto do PSD como o render as monta (render.texto.linhas_da_camada: quebras gravadas, as juntadas
    pela familia do formato e as inseridas na mestre propria), cada uma com os trechos de estilo dela (texto, face,
    cor, corpo, tracking) e a entrelinha da linha no documento (a distancia da linha de base da anterior, a mesma do
    render: o fator do paragrafo vezes o corpo na automatica, a do trecho na fixa, vezes a escala da matriz). None
    quando o laudo nao traz o texto dos trechos."""
    from desdobra.render import texto as rt
    texto = texto or {}
    runs = texto.get('runs') or []
    if not runs or any(not isinstance(r.get('texto'), str) or not isinstance(r.get('inicio'), int) for r in runs):
        return None
    m = texto.get('matriz') or [1.0, 0.0, 0.0, 1.0]
    sy = math.hypot(float(m[2]), float(m[3]))
    linhas = []
    for ln in rt.linhas_da_camada(texto, quebras=inserir, juntar=juntar):
        trechos = []
        for parte, r in ln['pedacos']:
            cor = r.get('cor_hex') if isinstance(r.get('cor_hex'), str) and COR.match(r.get('cor_hex')) else None
            trechos.append({'texto': parte, 'fonte_ps': r.get('fonte_ps'), 'face': face_de(r.get('fonte_ps')),
                            'cor': cor, 'corpo': r.get('corpo_efetivo'), 'tracking': r.get('tracking') or 0})
        linhas.append({'trechos': trechos, 'entrelinha': _arred(ln['entrelinha'] * sy) if ln['entrelinha'] else None})
    while linhas and not linhas[-1]['trechos']:
        linhas.pop()
    return linhas or None


def pecas_base(laudo, asset_por_camada, face_de):
    """{layer_id: peca no documento} de cada camada desenhavel: 'imagem' (asset por id), 'texto' (linhas com a face
    de cada trecho; sem face para algum trecho, a peca usa a imagem da camada e lista o que falta) ou 'sem_imagem'
    (a caixa so, quando o laudo nao tem pixels da camada)."""
    from desdobra.briefing import modelo as mb
    from desdobra.render import contrato as mc
    doc = laudo.get('documento') or {}
    base = {}
    for ordem, c in enumerate(laudo['camadas']):
        if not mb.desenhavel(c):
            continue
        lid = c['identidade']['layer_id']
        geo = c.get('geometria') or {}
        caixa = geo.get('caixa')
        if not caixa:
            continue
        ap = c.get('aparencia') or {}
        opacidade = ap.get('opacidade')
        peca = {'camada': lid, 'nome': c.get('nome') or '', 'ordem': ordem, 'caixa': [float(x) for x in caixa],
                'opacidade': None if opacidade is None else _arred(opacidade / 255.0),  # numero-neutro: opacidade de 8 bits
                'asset': asset_por_camada.get(lid), 'faltando': []}
        linhas = _linhas(c.get('texto'), face_de) if c.get('tipo') == 'texto' else None
        if linhas is not None:
            faltando = sorted({t['fonte_ps'] or '' for ln in linhas for t in ln['trechos'] if t['face'] is None})
            par = ((c.get('texto') or {}).get('paragrafos') or [{}])[0]
            tinta = [float(x) for x in (geo.get('caixa_tinta') or caixa)]
            regiao = None
            if doc.get('largura') and doc.get('altura'):
                regiao = mc.regiao_do_texto(geo, int(doc['largura']), int(doc['altura']))
            peca.update(linhas=linhas, faltando=faltando, alinhamento=ALINHAMENTOS.get(par.get('justificacao'), 'esquerda'),
                        caixa_tinta=tinta, _texto=c.get('texto'), _regiao=regiao or tinta,
                        _faces={t['fonte_ps']: t['face'] for ln in linhas for t in ln['trechos']})
            peca['tipo'] = 'texto'
            peca['modo'] = 'texto' if not faltando else ('imagem' if peca['asset'] else 'texto')
        else:
            peca['tipo'] = 'imagem' if peca['asset'] else 'sem_imagem'
            if c.get('texto_como_imagem'):
                # 0.9.1: texto como imagem por decisao do DA (o laudo da derivacao, nd.vista_como_imagem): sem linhas,
                # o palco nao edita o texto nem quebra a linha, e a pagina poe o selo
                peca['como_imagem'] = True
        base[lid] = peca
    return base


def _peca_no_formato(peca, tr, el, W, H):
    """A peca no formato: caixa e recorte pela transformacao do elemento. O texto leva as quebras do elemento no
    formato e o recorte e a regiao da pagina do texto no render (a caixa validada com folga), nunca o recorte do
    elemento: o render nao corta o texto ali."""
    from desdobra.derivacao import quebras as mq
    from desdobra.render import derivado as rd
    s = float(tr['s'])
    p = {k: v for k, v in peca.items() if k not in ('caixa', 'caixa_tinta', 'linhas') and not k.startswith('_')}
    p['elemento'] = el['id']
    p['caixa'] = _mapear(peca['caixa'], tr)
    p['recorte'] = _mapear(tr['recorte_doc'], tr)
    if 'linhas' in peca:
        lid = peca['camada']
        alvo = dict(el, transformacao=tr)
        q = el.get('quebras')
        linhas = peca['linhas']

        def face_de(ps):
            return peca['_faces'].get(ps)
        fam = next((x for x in (q.get('familia') or []) if x['layer_id'] == lid), None) if isinstance(q, dict) else None
        if fam is not None:
            # a quebra da familia da tela tambem insere (M7b, C2), como o render
            linhas = _linhas(peca['_texto'], face_de, juntar=mq.juntadas({'texto': peca['_texto']}, fam['aprovadas']),
                             inserir=fam.get('inseridas') or ())
        elif isinstance(q, list) and el.get('quebras_camada') == lid:
            linhas = _linhas(peca['_texto'], face_de, inserir=q)
        cv = rd.caixa_validada_do_texto(alvo, lid, peca['caixa_tinta'])
        p['caixa_tinta'] = _mapear(peca['caixa_tinta'], tr)
        p['caixa_validada'] = [_arred(x) for x in cv]
        regiao = rd.regiao_da_pagina_de_texto(tr, peca['_regiao'], cv, int(W), int(H))
        if regiao[2] > regiao[0] and regiao[3] > regiao[1]:  # fora do formato, o texto fica no recorte do elemento
            p['recorte'] = [float(x) for x in regiao]
        p['linhas'] = [{'trechos': [dict(t, corpo=None if t['corpo'] is None else _arred(t['corpo'] * s)) for t in ln['trechos']],
                        'entrelinha': None if ln['entrelinha'] is None else _arred(ln['entrelinha'] * s)}
                       for ln in linhas or []]
    return p


def escala_pura(kv, W, H):
    """Transformacao da escala pura da mestre na composicao W x H: contain, centrado (n 162: onde o fantasma fica)."""
    x0, y0, x1, y1 = kv['canvas_doc']
    Wm, Hm = x1 - x0, y1 - y0
    s = min(W / Wm, H / Hm)
    return {'s': s, 'origem_doc': [x0, y0], 'destino': [(W - Wm * s) / 2.0, (H - Hm * s) / 2.0],  # numero-neutro: centro
            'recorte_doc': [x0, y0, x1, y1]}


def _identidade(kv):
    x0, y0, x1, y1 = kv['canvas_doc']
    return {'s': 1.0, 'origem_doc': [x0, y0], 'destino': [0.0, 0.0], 'recorte_doc': [x0, y0, x1, y1]}


def _montar_palco(formato, W, H, itens, base, selo, caminho, situacao, devolucao, nomes):
    """itens: [(elemento, transformacao, caixa na composicao, fantasma)]."""
    elementos, pecas = [], []
    for el, tr, caixa, fantasma in itens:
        elementos.append({'id': el['id'], 'raiz': el.get('raiz'), 'nome': nomes.get(el.get('raiz'), ''),
                          'funcao': el.get('funcao'), 'regra': el.get('regra'),
                          'ancora': list(el['ancora']) if el.get('ancora') and el.get('regra') is not None else None,
                          'origem_funcao': el.get('origem_funcao'), 'fantasma': bool(fantasma),
                          'escala': _arred(tr['s']), 'caixa': [_arred(x) for x in caixa],
                          'recorte': _mapear(tr['recorte_doc'], tr)})
        for lid in el.get('layer_ids') or []:
            if lid in base:
                p = _peca_no_formato(base[lid], tr, {'id': el['id']} if fantasma else el, W, H)  # fantasma: as quebras da mestre
                p['fantasma'] = bool(fantasma)
                pecas.append(p)
    pecas.sort(key=lambda p: p['ordem'])
    mundo = [0.0, 0.0, float(W), float(H)]
    for p in pecas:
        c, r = p['caixa'], p['recorte']
        vis = [max(c[0], r[0]), max(c[1], r[1]), min(c[2], r[2]), min(c[3], r[3])]
        if vis[2] > vis[0] and vis[3] > vis[1]:
            mundo = [min(mundo[0], vis[0]), min(mundo[1], vis[1]), max(mundo[2], vis[2]), max(mundo[3], vis[3])]
    return {'formato': formato, 'largura': int(W), 'altura': int(H), 'caminho': caminho, 'situacao': situacao,
            'selo': selo, 'devolucao': devolucao, 'elementos': elementos, 'pecas': pecas,
            'mundo': [_arred(x) for x in mundo], 'fora_do_quadro': mundo != [0.0, 0.0, float(W), float(H)]}


def _nomes(laudo):
    return {c['identidade']['layer_id']: c.get('nome') or '' for c in laudo['camadas']}


def palco(d, kv, laudo, base):
    """Palco de um formato (derivacao/1 em memoria): pecas, elementos, selo e devolucao."""
    W, H = d['formato']['composicao']
    por_kv = {e['id']: e for e in kv['elementos']}
    pura = escala_pura(kv, W, H)
    itens = []
    if d['situacao'] == 'derivado':
        for el in d['elementos']:
            if el.get('regra') is None:
                ek = por_kv.get(el['id'], el)
                itens.append((el, pura, _mapear(ek.get('caixa_doc') or el['caixa_mestre'], pura), True))
            else:
                itens.append((el, el['transformacao'], el['caixa'], False))
        selo = 'escala_pura' if d.get('caminho') == 'transform' else 'proposta'
        devolucao = None
    else:
        for ek in kv['elementos']:
            itens.append((ek, pura, _mapear(ek['caixa_doc'], pura), True))
        selo = 'devolvido'
        dv = d.get('devolucao') or {}
        devolucao = {'motivo': dv.get('motivo'), 'o_que_fazer': dv.get('o_que_fazer'),
                     'texto': texto_da_devolucao(dv.get('motivo'))}
    return _montar_palco(d['formato']['id'], W, H, itens, base, selo, d.get('caminho'), d['situacao'], devolucao,
                         _nomes(laudo))


def palco_kv(kv, laudo, base):
    """Palco da mestre do KV, como a derivacao a ve (o canvas da mestre, sem transformacao)."""
    tr = _identidade(kv)
    itens = [(ek, tr, _mapear(ek['caixa_doc'], tr), ek.get('regra') is None) for ek in kv['elementos']]
    return _montar_palco(None, kv['largura'], kv['altura'], itens, base, 'kv', None, 'mestre', None, _nomes(laudo))


# ------------------------------------------------------------------ galeria (so previa)
def palco_da_variante(formato, W, H, v, laudo, base):
    """O palco de uma variante da galeria: os elementos dela (na forma dos elementos da derivacao) no mesmo modelo de
    pecas do palco, sem fantasma (a variante posiciona todo elemento do KV)."""
    itens = [(el, el['transformacao'], el['caixa'], False) for el in v['elementos']]
    return _montar_palco(formato, W, H, itens, base, SELO_VARIANTE, None, 'variante', None, _nomes(laudo))


def _variante_da_tela(v, ordem, palco_):
    """A variante como a tela a mostra: a frase do DA, os avisos e as falhas (codigo e texto em portugues) e o palco.
    O codigo so serve a tela para escolher a marca; nunca vai ao texto da moldura."""
    est = v.get('estrutura') or {}
    return {'id': v['id'], 'ordem': ordem, 'descricao': v['descricao'],
            'avisos': [{'codigo': a['codigo'], 'texto': a['texto']} for a in v['avisos']],
            'falhas': [{'codigo': f['codigo'], 'texto': f['texto']} for f in v['falhas_obrigatorias']],
            'estrutura': {'tipo': est.get('tipo'), 'trilhas': list(est.get('trilhas') or [])},
            'palco': palco_}


def galerias(ctx, kv, laudo, base, derivados, orientacoes, *, specs, arquivo_specs, params, brutos=None):
    """{id do formato devolvido: {'grupo': [ids], 'variantes': [...]}} para cada grupo de proporcao da tela
    (orientacoes, de abas) com formato devolvido que parte da galeria (desdobra.derivacao.proposta.
    galeria_dos_devolvidos, a mesma regra da derivacao da familia confirmada: previa igual ao Salvar, M7b). Desde a
    decisao 199, so o arquivo de edicao do grupo tem galeria: os outros arquivos copiam o layout aprovado nele. As
    variantes vem da galeria do motor no primeiro devolvido do grupo (derivacao.galeria.variantes); com mais de um devolvido no grupo, cada variante vai a todos pela estrutura que
    deixa o pior membro melhor (variante_para_grupo). Quando nenhuma estrutura serve ao grupo, cada membro fica com a
    variante em todo o grupo. O membro sem nenhuma variante ganha a galeria dele sozinho. So previa, em memoria.
    brutos: {id do formato: {id da variante: variante do motor}} preenchido aqui, para a edicao no palco partir da
    variante escolhida (desdobra.tela.edicao)."""
    from desdobra.derivacao import proposta
    por_id = {f['id']: f for f in ctx['briefing']['formatos']}
    kw = {'specs': specs, 'arquivo_specs': arquivo_specs, 'params': params}
    saida = {}
    for o in orientacoes:
        for g in o['grupos']:
            # a mesma galeria que a derivacao usa quando o DA confirma a familia, pela mesma regra
            # (desdobra.derivacao.proposta.galeria_dos_devolvidos): o formato com a medida por confirmar, o devolvido
            # por uma guarda do motor e a familia com a quebra de linha sem medida ficam fora, na tela e no "Salvar e
            # seguir"
            todos = [por_id[x['id']] for c in g['composicoes'] for x in c['formatos'] if x['id'] in por_id]
            # decisao 199: a galeria e do arquivo de edicao do grupo (o gravado no rascunho, senao a regra)
            por_formato = proposta.galeria_dos_devolvidos(ctx, kv, derivados, todos,
                                                          arquivo=g.get('arquivo_de_edicao'), **kw)[0]
            fids = [f['id'] for f in todos if f['id'] in por_formato]
            for fid in fids:
                pares = por_formato[fid]
                W, H = derivados[fid]['formato']['composicao']
                if brutos is not None:
                    brutos[fid] = {v['id']: v for _n, v in pares}
                saida[fid] = {'grupo': list(fids),
                              'variantes': [_variante_da_tela(v, n, palco_da_variante(fid, W, H, v, laudo, base))
                                            for n, v in pares]}
    return saida


# ------------------------------------------------------------------ passos 1 e 2
def arvore(laudo, briefing, resolvidas, quadro):
    """Arvore dos grupos e camadas da peca, do topo do painel para baixo: [{'camada', 'nome', 'tipo', 'funcao',
    'por', 'raiz', 'propria', 'observacao', 'filhos'}]."""
    from desdobra.briefing import modelo as mb
    camadas = mb.camadas_do_laudo(laudo)
    dadas = {i['layer_id']: i for i in briefing['funcoes'] if mb._decisao_valida(i['funcao'])}
    usados = set()
    for lid, c in camadas.items():
        if mb.desenhavel(c) and mb.no_escopo(c, quadro):
            usados.add(lid)
            usados.update(c.get('caminho_ids') or [])
    nos = {}
    for lid in usados:
        c = camadas.get(lid)
        if c is None:
            continue
        if lid in resolvidas:
            r = resolvidas[lid]
            funcao, por, raiz, obs = r['funcao'], POR.get(r['por']), r['raiz'], r.get('observacao')
        else:
            cadeia = [lid] + list(reversed(c.get('caminho_ids') or []))
            achou = next((x for x in cadeia if x in dadas), None)
            funcao = dadas[achou]['funcao']['valor'] if achou is not None else None
            por = None if achou is None else ('camada' if achou == lid else 'grupo')
            raiz, obs = achou, (dadas[achou].get('observacao') if achou is not None else None)
        nos[lid] = {'camada': lid, 'nome': c.get('nome') or '', 'tipo': c.get('tipo'), 'funcao': funcao, 'por': por,
                    'raiz': raiz, 'nome_raiz': (camadas.get(raiz) or {}).get('nome') or '' if raiz is not None else '',
                    'propria': dadas[lid]['funcao']['valor'] if lid in dadas else None, 'observacao': obs,
                    'visivel': bool((c.get('aparencia') or {}).get('visivel_efetiva')), 'filhos': []}
    raizes = []
    for c in reversed(laudo['camadas']):  # o painel do Photoshop: de cima para baixo
        lid = c['identidade']['layer_id']
        if lid not in nos:
            continue
        pai = c.get('pai_id')
        (nos[pai]['filhos'] if pai in nos else raizes).append(nos[lid])
    return raizes


def resumo_das_funcoes(briefing, resolvidas):
    """Regra e ancora de cada funcao usada (o resumo so de leitura do que o briefing decide; n 161)."""
    from desdobra.briefing import modelo as mb
    regras = mb.regras_por_funcao(briefing)
    ancoras, por_elemento = {}, {}
    for a in briefing.get('ancoras') or []:
        if not (mb._decisao_valida(a.get('x')) and mb._decisao_valida(a.get('y'))):
            continue
        if a.get('funcao'):
            ancoras[a['funcao']] = [a['x']['valor'], a['y']['valor']]
        elif a.get('layer_id') in resolvidas:  # ancora por elemento (layer_id da raiz), que vale sobre a da funcao
            f = resolvidas[a['layer_id']]['funcao']
            por_elemento[f] = por_elemento.get(f, 0) + 1
    contagem = {}
    for r in resolvidas.values():
        contagem[r['funcao']] = contagem.get(r['funcao'], 0) + 1
    return [{'funcao': f, 'regra': regras.get(f), 'ancora': ancoras.get(f), 'ancoras_por_elemento': por_elemento.get(f, 0),
             'camadas': n}
            for f, n in sorted(contagem.items())]


def decisoes_do_passo_2(laudo, quadro):
    """O que o passo 2 e o Design system pedem ao DA (desdobra.tela.funcoes): os grupos e as camadas na ordem do
    painel e as opcoes de cada campo, lidas do esquema briefing/1. Nenhum valor: as escolhas do DA vem so do rascunho
    da tela, e a funcao do briefing de teste nunca aparece como escolha."""
    from desdobra.tela import funcoes as tf
    return {'nos': tf.nos(laudo, quadro), 'opcoes': tf.opcoes(), 'quadro': quadro}


def _ler(arq, esquema):
    from desdobra import contratos
    try:
        return contratos.ler(arq, esquema) if Path(arq).is_file() else None
    except (contratos.ErroContrato, OSError, ValueError):
        return None


def descricao_da_fase(fid):
    """O nome da fase para a tela (a descricao da esteira), nunca o id cru do motor."""
    from desdobra.job import fases as mod_fases
    for f in mod_fases.ESTEIRA:
        if f.id == fid:
            return f.descricao
    return str(fid).replace('_', ' ')


def modo_na_tela(pasta, teto_cli=None):
    """O modo de dados do passo 1 (decisoes-v1.md, 170): o escolhido na tela (o valor gravado, sem nada marcado antes
    da escolha), o teto da agencia e so as opcoes dentro dele. O estado.json nao e fonte do modo."""
    from desdobra.job import modo_dados
    teto = modo_dados.teto_do_job(pasta, teto_cli)
    reg = modo_dados.ler(pasta)
    return {'escolhido': reg['valor'] if reg is not None else None, 'teto': teto, 'opcoes': modo_dados.opcoes(teto)}


def linkados_na_tela(pasta, laudo):
    """Os linkados do laudo para o passo 1: camada, nome, se ja tem arquivo confirmado (e qual) e os candidatos da
    proposta do leitor (caminho do job em entrada/campanha/, bytes e se o tamanho bate com o registro do PSD)."""
    from desdobra.render import contrato as mod_contrato
    try:
        confirmados = mod_contrato.linkados_confirmados(pasta, None, laudo['origem']['sha256']) or {}
    except Exception:  # noqa: BLE001 - arquivo fora do contrato conta como sem confirmacao
        confirmados = {}
    out = []
    for c in laudo['camadas']:
        so = c.get('smart_object') or {}
        if c.get('tipo') != 'smart_linkado' or not so.get('unique_id'):
            continue
        conf = confirmados.get(so['unique_id'])
        cands = [{'arquivo': 'entrada/' + x['arquivo'], 'nome': Path(x['arquivo']).name, 'bytes': x.get('bytes'),
                  'mesmo_tamanho': bool(x.get('mesmo_tamanho'))}
                 for x in (so.get('casamento') or {}).get('candidatos') or [] if isinstance(x.get('arquivo'), str)]
        out.append({'camada': c['identidade']['layer_id'], 'nome': c.get('nome') or '', 'unique_id': so['unique_id'],
                    'confirmado': conf is not None, 'arquivo': conf['arquivo'] if conf else None, 'candidatos': cands})
    return out


# os campos de spec (specs.modelo.CAMPOS) com nome para o DA; o id cru nunca vai a tela
NOMES_CAMPO = {
    'versao_impressa': 'versão impressa', 'data_impressa': 'data impressa', 'nome': 'nome do veículo',
    'apelidos': 'outros nomes', 'concessionaria': 'concessionária', 'prazo_envio': 'prazo de envio',
    'ambiente': 'ambiente', 'praca': 'praça', 'modelo_tela': 'modelo da tela', 'faixas_reservadas': 'faixas reservadas',
    'restricao': 'restrição', 'dimensao': 'dimensão', 'orientacao_painel': 'orientação do painel', 'rotacao': 'rotação',
    'area_util': 'área útil', 'faixas': 'faixas', 'area_segura': 'área segura', 'borda_1px': 'borda de 1 px',
    'peso_max': 'peso máximo', 'peso_max_hospedado': 'peso máximo hospedado', 'peso_max_tag': 'peso máximo por tag',
    'peso_max_tag_carga_inicial': 'peso máximo da carga inicial',
    'peso_max_tag_carga_posterior': 'peso máximo da carga posterior', 'tipos_aceitos': 'tipos de arquivo aceitos',
    'qualidade_jpg_recomendada': 'qualidade de JPG recomendada', 'area_visivel': 'área visível', 'sangria': 'sangria',
    'margem_seguranca': 'margem de segurança', 'sufixo_nome_arquivo': 'final do nome do arquivo',
}


def nome_do_campo(campo):
    return NOMES_CAMPO.get(campo) or str(campo).replace('_', ' ')


def descricao_do_valor(v):
    """O valor de spec em texto para o DA: a dimensao, o texto como esta na folha ou o valor."""
    x = v.get('valor')
    if isinstance(x, dict) and 'largura' in x and 'altura' in x:
        return ('%s x %s %s' % (x['largura'], x['altura'], v.get('unidade') or '')).strip()
    if v.get('texto_original'):
        return str(v['texto_original'])
    if isinstance(x, list):
        return ', '.join(str(i) for i in x)
    return '' if x is None else str(x)


def formatos_sem_medida(pasta):
    """Os formatos do rascunho das specs com a medida divergente, sem a escolha do DA e por isso sem chave (revisao
    dos becos, D2): [{'valor_id', 'leituras': [texto de cada medida], 'texto'}], na ordem da folha. Vazio sem rascunho
    legivel."""
    doc = _ler(Path(pasta) / 'specs' / 'rascunho.json', 'spec/1')
    saida = []
    for f in (doc or {}).get('formatos') or []:
        dim = (f.get('campos') or {}).get('dimensao') or {}
        if f.get('chave') or dim.get('valor') is not None or not dim.get('leituras'):
            continue
        leituras = [descricao_do_valor(lei) for lei in dim['leituras']]
        saida.append({'formato': f['id'], 'valor_id': dim['id'], 'leituras': leituras, 'texto': ' ou '.join(leituras)})
    return saida


def specs_pendentes(pasta):
    """Os valores de spec que esperam o DA no passo 1, na ordem da confirmacao do terminal (divergentes primeiro):
    {'valor_id', 'onde', 'campo' (nome para o DA), 'descricao', 'trecho', 'leituras': [{'indice', 'descricao',
    'trecho'}]}. A leitura so aparece no campo com fontes divergentes."""
    from desdobra.specs import confirmar as mod_confirmar
    out = []
    sem_medida = {x['formato']: x['texto'] for x in formatos_sem_medida(pasta)}
    for r, campo, v in mod_confirmar.pendencias_gravadas(pasta):
        divergente = bool(v.get('leituras')) and v['valor'] is None
        leituras = [{'indice': i, 'descricao': descricao_do_valor(lei), 'trecho': lei.get('texto_original') or ''}
                    for i, lei in enumerate(v.get('leituras') or [])] if divergente else []
        # o formato sem chave (a medida espera a escolha) aparece pelas medidas da folha, em todos os valores dele
        if not r.get('chave') and r['id'] in sem_medida:
            onde, na_frase = ONDE_SEM_MEDIDA % sem_medida[r['id']], FRASE_SEM_MEDIDA % sem_medida[r['id']]
        else:
            onde = r.get('chave') or r['id']
            na_frase = 'formato %s' % onde
        # 0.9.6: o cartao do lote, por formato (a medida da chave) ou "Valores gerais da folha"; o divergente e o
        # formato com duas medidas ficam fora do lote (em_lote False), com a escolha um por um
        if r.get('chave'):
            grupo, grupo_nome = 'f:%s' % r['chave'], medida_da_chave(r['chave'])
        elif r['id'] in sem_medida:
            grupo, grupo_nome = 'm:%s' % r['id'], onde
        else:
            grupo, grupo_nome = 'geral', GRUPO_GERAL
        out.append({'valor_id': v['id'], 'onde': onde, 'na_frase': na_frase, 'campo': nome_do_campo(campo),
                    'descricao': descricao_do_valor(v) if not divergente else 'as folhas trazem valores diferentes',
                    'trecho': v.get('texto_original') or '', 'leituras': leituras, 'grupo': grupo,
                    'grupo_nome': grupo_nome,
                    'em_lote': not divergente and r['id'] not in sem_medida and v.get('valor') is not None})
    return out


GRUPO_GERAL = 'Valores gerais da folha'


def medida_da_chave(chave):
    """O nome legivel de uma chave de formato da folha para o cartao do lote (0.9.6): a medida primeiro, com espacos
    ('1080x1920' vira '1080 x 1920'), e o circuito da folha entre parenteses, sem hifens ('pme|sao-paulo|1080x1920'
    vira '1080 x 1920 (sao paulo)'). A chave sem medida fica como esta. O id interno da folha nunca chega ao DA
    (revisao adversarial da 0.9.6): a folha sem circuito ('f9c478bf8|geral|1080x1920', ou o circuito com o id da
    folha na frente, 'f9c478bf8|f9c478bf8-geral|...') fica so com a medida."""
    partes = str(chave).split('#', 1)[0].split('|')
    m = re.match(r'^(\d+(?:[.,]\d+)?)x(\d+(?:[.,]\d+)?)([a-z]*)$', partes[-1])
    medida = ('%s x %s%s' % (m.group(1), m.group(2), (' ' + m.group(3)) if m.group(3) else '')) if m else partes[-1]
    onde = partes[-2].strip() if len(partes) > 1 else ''
    folha = partes[0].strip() if len(partes) > 2 else ''  # numero-neutro: folha, circuito e medida
    if folha:
        for sep in (':', '-', '_'):
            if onde.startswith(folha + sep):
                onde = onde[len(folha) + 1:]
                break
    onde = '' if onde in ('', folha, CIRCUITO_PADRAO) else onde.replace('-', ' ').strip()
    # o veiculador com o nome da folha na frente ('portalteste-f9c478bf8|f9c478bf8-geral|...'): as partes do id do
    # veiculador e o circuito padrao saem do nome do circuito
    if onde and folha:
        do_veiculador = set(re.split(r'[-_: ]+', folha)) | {CIRCUITO_PADRAO}
        onde = ' '.join(p for p in onde.split() if p not in do_veiculador)
    return '%s (%s)' % (medida, onde) if onde else medida


# o circuito que a folha sem circuito recebe (desdobra.specs.modelo.Montagem.circuito): nao vai ao nome do cartao
CIRCUITO_PADRAO = 'geral'


# as paradas que ainda nao tem botao na tela, em texto para o DA (decisoes-v1.md, 24, 41, 57 e 79; a 159 manda que o
# DA nunca rode nada no terminal: a tela so mostra o bloqueio, sem comando)
PARADA_DEPOIS = 'Esta decisão ainda não tem botão na tela; o job fica parado neste ponto até a próxima versão.'
TEXTOS_PARADA = {
    'largura': 'A largura de uma linha de texto ficou diferente da largura medida no Photoshop. ' + PARADA_DEPOIS,
    'mesclagem': ('Uma camada usa mesclagem ou ajuste sobre outras camadas, e as peças novas podem sair com outra '
                  'aparência nesse ponto. ' + PARADA_DEPOIS),
    'isolador': ('O arquivo passou do limite de memória ou de tempo na leitura, e a composição do KV não foi '
                 'conferida. ' + PARADA_DEPOIS),
}
CODIGOS_PARADA = {'largura_divergente': 'largura', 'efeito_sobre_texto_sem_aplicar': 'mesclagem',
                  'clipping_dividido_por_texto': 'mesclagem', 'composicao_acima_do_orcamento': 'isolador'}
RECUSAS_DO_ISOLADOR = ('memoria', 'tempo', 'orcamento')


def _ids_das_medidas(medidas):
    out = []
    for x in (medidas or {}).get('camadas') or []:
        lid = x.get('layer_id') if isinstance(x, dict) else x
        if isinstance(lid, int) and not isinstance(lid, bool):
            out.append(lid)
    return out


def paradas(pasta, laudo):
    """Bloqueios do passo 1 em texto simples: a divergencia de largura, a mesclagem (no KV, pelo contrato do render, e
    nas pecas derivadas, pelas camadas visiveis do laudo com mesclagem) e as paradas do isolador (recusa de memoria ou
    tempo do laudo). [{'tipo', 'texto', 'camadas': [nome]}], um por tipo."""
    from desdobra.derivacao import elementos
    from desdobra.render import contrato as mod_contrato
    nomes = {c['identidade']['layer_id']: c.get('nome') or '' for c in laudo.get('camadas') or []}
    por_tipo = {}

    def juntar(tipo, ids=()):
        item = por_tipo.setdefault(tipo, {'tipo': tipo, 'texto': TEXTOS_PARADA[tipo], 'camadas': []})
        for lid in ids:
            nome = nomes.get(lid)
            if nome and nome not in item['camadas']:
                item['camadas'].append(nome)

    try:
        _c, bloqueios, confirmar = mod_contrato.montar(pasta)
    except Exception:  # noqa: BLE001 - sem contrato legivel a tela segue; o render recusa do jeito dele
        bloqueios, confirmar = [], []
    for b in list(bloqueios or []) + list(confirmar or []):
        tipo = CODIGOS_PARADA.get(b.get('codigo'))
        if tipo:
            juntar(tipo, _ids_das_medidas(b.get('medidas')))
    mesclas = [c['identidade']['layer_id'] for c in laudo.get('camadas') or []
               if elementos.mesclagem(c) and (c.get('aparencia') or {}).get('visivel_efetiva', True)]
    if mesclas:
        juntar('mesclagem', mesclas)
    if any(r.get('tipo') in RECUSAS_DO_ISOLADOR for r in laudo.get('recusas') or []):
        juntar('isolador')
    return [por_tipo[t] for t in ('largura', 'mesclagem', 'isolador') if t in por_tipo]


# revisao do 0.9.2: o texto do bloqueio segue o botao da pagina (Resolver aqui, nas specs e no laudo das fontes) e a
# frase de baixo (o bloqueio sem botao se resolve com o Claude); nunca diz que a tela ainda nao traz o caminho
BLOQUEIO_DE_FASE = ('O desdobra parou nesta etapa, e ela não se resolve nesta tela. Conte ao Claude, no chat, o que '
                    'aparece aqui.')
BLOQUEIO_DAS_SPECS = 'O desdobra parou nas specs. Em Valores de spec, no passo 1, veja o que falta.'
BLOQUEIO_DO_LAUDO_DAS_FONTES = 'O desdobra parou na conferência das fontes. Em Fontes do job, veja o que falta.'
# 0.9.1: o bloqueio das fontes leva ao que o DA faz na propria tela (o arquivo da fonte, ou o texto como imagem)
BLOQUEIO_DAS_FONTES = ('O desdobra parou nas fontes. Em Fontes do job, veja o que falta: mande o arquivo da fonte ao '
                       'Claude ou, sem ele, use o texto como imagem.')
# revisao do 0.9.1: sem face que o DA possa declarar (nenhum botao na tela), o bloqueio nao manda usar o texto como
# imagem
BLOQUEIO_DAS_FONTES_SEM_BOTAO = ('O desdobra parou nas fontes. Em Fontes do job, veja o que falta e mande ao Claude o '
                                 'arquivo da fonte que confere com o PSD.')


def bloqueio_na_tela(fid, bloqueio, declaravel=False):
    """O bloqueio de uma fase em texto para o DA: o nome da etapa e uma frase fixa, nunca o o_que_fazer do motor, que
    cita comando de terminal. declaravel: ha face que o DA pode mandar como imagem agora (o botao do passo 1)."""
    if fid == 'fontes':
        texto = BLOQUEIO_DAS_FONTES if declaravel else BLOQUEIO_DAS_FONTES_SEM_BOTAO
    elif fid == 'specs':
        texto = BLOQUEIO_DAS_SPECS
    elif fid == 'laudo-fontes':
        texto = BLOQUEIO_DO_LAUDO_DAS_FONTES
    else:
        texto = BLOQUEIO_DE_FASE
    return {'fase': fid, 'descricao': descricao_da_fase(fid), 'texto': texto}


def giro_da_folha(doc, chave):
    """O que a folha de spec diz do giro do formato (o campo rotacao, so registro), no texto da folha, ou None quando
    ela nao diz nada. So dica para o DA: o giro do briefing e escolha dele."""
    for f in (doc or {}).get('formatos') or []:
        if f.get('chave') == chave:
            v = (f.get('campos') or {}).get('rotacao') or {}
            texto = v.get('texto_original')
            return texto if isinstance(texto, str) and texto.strip() else None
    return None


def quadros_na_tela(laudo, briefing):
    """As pranchetas do PSD para o passo 1 (decisao 1; revisao do M7a): [{'id', 'nome', 'largura', 'altura',
    'visivel', 'escolhido'}], na ordem do laudo, sem nada escolhido antes do DA. O PSD sem prancheta da lista vazia. A
    previa de cada uma (palco) entra em montar."""
    from desdobra.briefing import modelo as mb
    d = briefing.get('quadro')
    escolhido = d['valor'] if mb._decisao_valida(d) else None
    saida = []
    for q in (laudo.get('documento') or {}).get('quadros') or []:
        x0, y0, x1, y1 = q['caixa']
        saida.append({'id': q['id'], 'nome': q.get('nome') or '', 'largura': int(round(x1 - x0)),
                      'altura': int(round(y1 - y0)), 'visivel': bool(q.get('visivel_ao_salvar')),
                      'escolhido': q['id'] == escolhido})
    return saida


def lido(pasta, estado_job, laudo, briefing, formatos, faces_servidas, teto=None):
    """Passo 1: o que o motor leu do job, com as decisoes do DA que ja tem botao (modo de dados, linkados e valores de
    spec; decisoes-v1.md, 159 e 170) e as paradas em texto simples."""
    from desdobra.job import fases as mod_fases
    from desdobra.job import nucleo
    from desdobra.specs import confirmar as mod_confirmar
    from desdobra.specs import digitados as mod_digitados
    from desdobra.specs import modelo as mod_specs
    pasta = Path(pasta)
    avaliacao, _d = nucleo.avaliar(pasta, estado_job, mod_fases.ESTEIRA)
    como = textos_como_imagem_na_tela(pasta, laudo)
    declaraveis = {d['nome_ps'] for d in como['declaraveis'] if d['declaravel']}
    bloqueios = [bloqueio_na_tela(fid, b, declaravel=bool(declaraveis))
                 for fid, b in nucleo.bloqueios_pendentes(estado_job, avaliacao, mod_fases.ESTEIRA)]
    camadas_bloqueadas = [{'camada': c['identidade']['layer_id'], 'nome': c.get('nome') or '',
                           'motivos': [m.get('descricao') or m.get('regra') for m in c.get('motivos') or []]}
                          for c in laudo['camadas'] if c.get('situacao') == 'bloqueante']
    linkados = linkados_na_tela(pasta, laudo)
    doc = _ler(pasta / 'specs' / 'rascunho.json', 'spec/1')
    specs = {'confirmados': 0, 'rascunhos': 0, 'divergentes': 0, 'registros': 0, 'pendentes': 0, 'tem_rascunho': doc
             is not None}
    if doc is not None:
        for _r, _campo, v in mod_specs.todos_os_valores(doc):
            if v['situacao'] == 'confirmado':
                specs['confirmados'] += 1
            elif v['situacao'] == 'registro':
                specs['registros'] += 1
            elif v.get('leituras') and v['valor'] is None:
                specs['divergentes'] += 1
            else:
                specs['rascunhos'] += 1
        specs['pendentes'] = len(mod_confirmar.pendencias(doc))
    specs['lista'] = specs_pendentes(pasta) if doc is not None else []
    specs['recortes'] = sum(len(f.get('recortes') or []) for f in (doc or {}).get('folhas') or [])
    specs['folhas'] = len((doc or {}).get('folhas') or [])
    specs['sem_medida'] = formatos_sem_medida(pasta) if doc is not None else []
    # o giro de cada formato e escolha do DA (revisao do M7a): o que a folha diz do giro vai como dica, nunca marcado
    # 0.9.2: o formato que o DA digitou na tela, sem folha de spec (desdobra.specs.digitados), e o bloco dele
    specs['formatos'] = [{'id': f['id'], 'chave': f.get('chave'), 'sem_folha': bool(f.get('sem_folha')),
                          'digitado': (f.get('chave') or '').startswith(mod_digitados.VEICULADOR + '|'),
                          'tem_spec': bool(((formatos.get(f['id']) or {}).get('formato') or {}).get('tem_spec')),
                          'largura': f['largura'], 'altura': f['altura'], 'rotacao': f.get('rotacao'),
                          'giro_da_folha': giro_da_folha(doc, f.get('chave'))}
                         for f in briefing['formatos']]
    # sem formato em pixels: o que o DA faz, no lugar da lista (revisao do M7a)
    specs['sem_formatos'] = '' if specs['formatos'] else \
        (SEM_MEDIDA_EM_PIXELS if specs['folhas'] else SEM_FOLHA_DE_SPEC)
    specs['digitados'] = mod_digitados.na_tela(pasta)
    lf = _ler(pasta / 'laudo' / 'laudo-fontes.json', 'laudo/1')
    usadas = (lf or laudo).get('fontes_usadas') or []
    nomes = {c['identidade']['layer_id']: c.get('nome') or '' for c in laudo['camadas']}
    return {'bloqueios': bloqueios, 'camadas_bloqueadas': camadas_bloqueadas, 'linkados': linkados, 'specs': specs,
            'quadros': quadros_na_tela(laudo, briefing),
            'modo_dados': modo_na_tela(pasta, teto), 'paradas': paradas(pasta, laudo),
            'fontes': faces_servidas,
            'fontes_que_faltam': [{'fonte_ps': u['fonte_ps'], 'situacao': u['situacao'], 'camadas': len(u['camadas']),
                                   'camadas_nomes': [nomes.get(x, '') for x in u['camadas']],
                                   'declaravel': u['fonte_ps'] in declaraveis}
                                  for u in usadas if u.get('situacao') in ('ausente', 'divergente')],
            # 0.9.1: o texto como imagem por decisao do DA (desdobra.fontes.como_imagem)
            'textos_como_imagem': como['declaradas'], 'declaracoes_caidas': como['caidas']}


CAIDA = 'Chegou o arquivo da fonte %s. O texto volta a ser texto vivo, e a sua decisão de usar como imagem deixa de valer.'


def textos_como_imagem_na_tela(pasta, laudo):
    """{'declaraveis', 'declaradas', 'caidas'} do passo 1 (0.9.1): as faces sem arquivo que o DA pode declarar (com o
    nome de cada camada atingida, que a pagina poe so por textContent), as declaradas que valem agora (fontes/
    conferencia.json, bloco texto_como_imagem) e as declaradas que um arquivo enviado derrubou, com o aviso."""
    from desdobra.fontes import como_imagem
    nomes = {c['identidade']['layer_id']: c.get('nome') or '' for c in laudo['camadas']}
    decl = como_imagem.ler(pasta) or {}
    por_ps = {f['nome_ps']: f for f in decl.get('faces') or []}
    b = como_imagem.bloco(pasta) or {}
    camadas = set(b.get('camadas') or [])
    declaradas = []
    for ps in b.get('faces') or []:
        f = por_ps.get(ps) or {}
        lids = [x for x in f.get('camadas') or [] if x in camadas]
        declaradas.append({'fonte_ps': ps, 'camadas': [nomes.get(x, '') for x in lids],
                           'decidido_em': (f.get('decidido_por') or {}).get('quando'),
                           'teste': f.get('origem') != como_imagem.ORIGEM_DA})
    caidas = [{'fonte_ps': ps, 'texto': CAIDA % ps} for ps in b.get('caidas') or [] if ps in por_ps]
    return {'declaraveis': como_imagem.declaraveis(pasta), 'declaradas': declaradas, 'caidas': caidas}


FAMILIA_SEM_CONFIRMACAO = 'Confirme a família quando ela estiver como você quer.'


def por_confirmar(formatos):
    """Os ids dos formatos devolvidos com um valor de spec a espera do DA, na derivacao em memoria ({id: derivacao}):
    o do proprio formato (spec_por_confirmar) e o do formato da mestre propria de que ele deriva (mestre_por_confirmar;
    revisao dos becos, D3)."""
    from desdobra.derivacao import nucleo as nd
    return {fid for fid, d in (formatos or {}).items()
            if (d.get('devolucao') or {}).get('motivo') in nd.MOTIVOS_POR_CONFIRMAR}


def familias_confirmadas(pasta, familias, pendentes=(), pecas=None, sem_edicao=None):
    """Os ids das familias confirmadas no rascunho da tela agora (decisoes-v1.md, 167), so para os formatos que cada
    uma tem hoje (familias: {id: [formatos]}; desdobra.tela.rascunho.confirmada_para). A familia com formato em
    pendentes (por_confirmar) nunca conta como confirmada: o DA nao viu a galeria dele. pecas: {id: impressao}
    (impressao_das_pecas); com ela, a confirmacao feita sobre outras pecas nao conta. sem_edicao: {id: impressao pela
    REGRA_SEM_EDICAO}, que vale para a familia sem edicao (rascunho.confirmada_para)."""
    from desdobra.tela import rascunho
    dados, _de_outro = rascunho.ler(pasta, rascunho.laudo_sha256(pasta))
    return {g for g, f in ((dados or {}).get('familias') or {}).items()
            if rascunho.confirmada_para(f, familias.get(g, ()), None if pecas is None else pecas.get(g, ''),
                                        sem_edicao=(sem_edicao or {}).get(g))
            and not set(familias.get(g, ())) & set(pendentes)}


def impressao_das_pecas(fids, formatos, versoes, regra=None, arquivo=None):
    """A impressao do que a tela mostra da familia (revisao 3 da regra spec_por_confirmar): de cada formato, a
    composicao, a situacao, o motivo da devolucao e as areas que vem da spec (a area util, as faixas e a area segura),
    e as versoes da galeria. A folha trocada (outra area segura) ou a galeria que aparece depois da confirmacao mudam
    a impressao, e a confirmacao de antes deixa de valer (desdobra.tela.rascunho.confirmada_para). A impressao leva
    tambem a regra da previa (REGRA_DA_PREVIA): a confirmacao feita numa tela que mostrava a familia por outra regra
    (sem as falhas que o "Salvar e seguir" acha, por exemplo) cai, e o DA confirma de novo o que a tela mostra agora.
    formatos: {id: derivacao}. regra: outra regra da previa (REGRA_SEM_EDICAO); None, a de agora. arquivo: o arquivo
    de edicao da familia (decisao 199, 5; 0.10.0): trocar o arquivo de edicao muda a impressao."""
    import hashlib
    import json
    itens = []
    for fid in fids:
        d = formatos.get(fid) or {}
        a = d.get('areas') or {}
        au, seg = a.get('area_util'), a.get('area_segura')
        itens.append([fid, (d.get('formato') or {}).get('composicao'), d.get('situacao'),
                      (d.get('devolucao') or {}).get('motivo'), au and au.get('caixa'),
                      [[x.get('lado'), x.get('px'), x.get('caixa')] for x in a.get('faixas') or []],
                      seg and [seg.get('caixa'), seg.get('lados')]])
    corpo = {'formatos': itens, 'versoes': sorted(versoes), 'regra_da_previa': regra or REGRA_DA_PREVIA}
    if arquivo is not None:
        corpo['arquivo_de_edicao'] = arquivo
    texto = json.dumps(corpo, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()


def faltam(lido_, formatos, variantes=None, familias=None, confirmadas=(), arquivos=None):
    """A lista unica do que falta, cada item com o lugar da tela que leva a ele. variantes: {id do formato: quantas
    variantes a galeria montou}; o formato devolvido com versoes pede a escolha de uma. familias: {id: [formatos]}; a
    familia sem confirmacao no rascunho pede a confirmacao, e a confirmada deixa de pedir a escolha da versao.
    arquivos: {id: arquivo de edicao} das familias como a tela mostra (decisao 199; sem ele, a regra)."""
    variantes = variantes or {}
    familias = familias or {}
    resolvidos = {f for g in confirmadas for f in familias.get(g, ())}
    itens = []
    if lido_['modo_dados']['escolhido'] is None:
        itens.append({'texto': 'Escolha o modo de dados do job.', 'detalhe': '', 'ir': {'passo': 'lido'}})
    for b in lido_['bloqueios']:
        if b['fase'] == 'fontes' and lido_['fontes_que_faltam']:
            # revisao do 0.9.1: o bloqueio das fontes e a fonte que falta sao o mesmo pendente; fica o item da fonte,
            # com o nome dela
            continue
        itens.append({'texto': b['texto'], 'detalhe': b['descricao'], 'ir': {'passo': 'lido'}})
    for p in lido_['paradas']:
        itens.append({'texto': p['texto'], 'detalhe': ', '.join(p['camadas']), 'ir': {'passo': 'lido'}})
    for c in lido_['camadas_bloqueadas']:
        itens.append({'texto': 'Uma camada do PSD não pôde ser lida.', 'detalhe': c['nome'], 'ir': {'passo': 'lido'}})
    for x in lido_['linkados']:
        if not x['confirmado']:
            itens.append({'texto': 'Um linkado espera a confirmação do arquivo.', 'detalhe': x['nome'],
                          'ir': {'passo': 'lido'}})
    if lido_['specs'].get('recortes'):
        itens.append({'texto': 'Uma folha de spec tem página sem texto, e os valores dela ainda não têm botão na tela.',
                      'detalhe': str(lido_['specs']['recortes']), 'ir': {'passo': 'lido'}})
    if lido_['specs']['pendentes']:
        itens.append({'texto': 'Há valores de spec que esperam a sua confirmação.',
                      'detalhe': str(lido_['specs']['pendentes']), 'ir': {'passo': 'lido'}})
    # o formato da folha com duas medidas espera a escolha do DA, e nunca some do job em silencio (revisao dos becos, D2)
    for x in lido_['specs'].get('sem_medida') or []:
        itens.append({'texto': MEDIDA_A_ESCOLHER_FALTA, 'detalhe': x['texto'], 'ir': {'passo': 'lido'}})
    # o passo 1 da revisao do M7a: specs sem formato em pixels, a prancheta e o giro de cada formato
    if not lido_['specs']['formatos']:
        itens.append({'texto': SEM_FORMATOS_FALTA, 'ir': {'passo': 'lido'},
                      'detalhe': SEM_MEDIDA_EM_PIXELS if lido_['specs'].get('folhas') else SEM_FOLHA_DE_SPEC})
    if lido_.get('quadros') and not any(q['escolhido'] for q in lido_['quadros']):
        itens.append({'texto': QUADRO_SEM_ESCOLHA, 'detalhe': '', 'ir': {'passo': 'lido'}})
    # o formato escrito na tela aparece pela medida, sem o id do motor (revisao do 0.9.2)
    sem_giro = [('%d x %d' % (f['largura'], f['altura']) if f.get('digitado') else f['id'])
                for f in lido_['specs']['formatos'] if f.get('rotacao') is None]
    if sem_giro:
        itens.append({'texto': GIRO_SEM_ESCOLHA, 'detalhe': ', '.join(sem_giro), 'ir': {'passo': 'lido'}})
    for f in lido_['fontes_que_faltam']:
        itens.append({'texto': 'Uma fonte do PSD falta ou não confere com o arquivo enviado.', 'detalhe': f['fonte_ps'],
                      'ir': {'passo': 'lido'}})
    pendentes = por_confirmar(formatos)
    # decisao 199: o arquivo devolvido que copia o layout do arquivo de edicao da familia (o de edicao com proposta ou
    # com versoes) nao pede escolha propria: segue o arquivo de edicao, e a confirmacao da familia o cobre
    from desdobra.derivacao import proposta
    copiam = set()
    for gid, fids in familias.items():
        fs = [f for f in fids if f in formatos]
        if not fs:
            continue
        ref = proposta.arquivo_de_edicao([dict(formatos[f]['formato'], id=f) for f in fs], (arquivos or {}).get(gid))
        if formatos[ref]['situacao'] == 'derivado' or (proposta.usa_galeria(formatos[ref]) and variantes.get(ref)):
            copiam |= {f for f in fs if f != ref and proposta.usa_galeria(formatos[f])}
    for gid, fids in familias.items():
        # a familia com formato por confirmar espera o passo 1: o item do formato, logo abaixo, leva a ele
        if gid not in confirmadas and fids and not set(fids) & pendentes:
            itens.append({'texto': FAMILIA_SEM_CONFIRMACAO, 'detalhe': ', '.join(fids),
                          'ir': {'passo': 'pecas', 'formato': fids[0]}})
    for fid, d in formatos.items():
        if fid in copiam:
            continue
        if d['situacao'] == 'devolvido' and not (fid in resolvidos and variantes.get(fid)):
            motivo = (d.get('devolucao') or {}).get('motivo')
            if fid in pendentes and motivo == 'mestre_por_confirmar':
                # o formato espera a spec do formato da mestre, que tem o item dele com a chave da folha
                itens.append({'texto': MESTRE_POR_CONFIRMAR_FALTA, 'detalhe': fid, 'ir': {'passo': 'lido'}})
                continue
            if fid in pendentes:
                # a chave da folha, como a lista de Valores de spec mostra o formato
                itens.append({'texto': SPEC_POR_CONFIRMAR_FALTA, 'detalhe': d['formato'].get('chave') or fid,
                              'ir': {'passo': 'lido'}})
                continue
            inicio = 'Escolha uma das versões do desdobra. ' if variantes.get(fid) else 'Sem proposta do desdobra. '
            itens.append({'texto': inicio + MOTIVOS_TELA.get(motivo, MOTIVO_GERAL),
                          'detalhe': fid, 'ir': {'passo': 'pecas', 'formato': fid}})
    return itens


# ------------------------------------------------------------------ fontes e assets
def fontes_do_job(pasta, estado_job):
    """({id: (bytes, mime)} das faces servidas, a lista para o estado [{'id', 'sha256', 'formato', 'familia_css',
    'familia', 'estilo', 'nome_ps'}], as faces de casamento.montar_faces que sao servidas)."""
    import hashlib

    from desdobra import arquivos, contratos
    from desdobra.chromium import servidor
    from desdobra.fontes import casamento, conferencia
    from desdobra.tela import estatico
    leituras, por_sha = [], {}
    for rel, reg in sorted((estado_job.get('entradas') or {}).items()):
        if not rel.startswith(conferencia.PASTA_ENTRADA):
            continue
        arq = Path(pasta) / 'fontes' / 'bruto' / reg['sha256'] / 'leitura.json'
        if arq.is_file():
            leitura = contratos.ler(arq, 'leitura-fonte/1')
            if leitura.get('situacao') == 'lida':
                leituras.append((reg['sha256'], leitura))
                por_sha[reg['sha256']] = rel
    servidos, lista, faces = {}, [], []
    for f in casamento.montar_faces(leituras):
        rel = por_sha.get(f['sha256'])
        dados = (Path(pasta) / rel).read_bytes() if rel else None
        if dados is None or arquivos.sha256_bytes(dados) != f['sha256']:
            continue
        servir = conferencia.bytes_para_servir(dados, f)
        if servir is None:
            continue
        servidos[f['id']] = (servir, servidor.MIME_POR_FORMATO[f['formato']])
        faces.append(f)
        lista.append({'id': f['id'], 'sha256': hashlib.sha256(servir).hexdigest(), 'formato': f['formato'],
                      'familia_css': estatico.familia_css(f['id']), 'familia': f.get('familia'),
                      'estilo': f.get('estilo'), 'nome_ps': f.get('nome_ps')})
    return servidos, lista, faces


def assets_das_camadas(pasta, laudo):
    """({id: (bytes, 'image/png')}, {layer_id: id}): o PNG dos pixels proprios de cada camada do KV, pelo
    pixels.asset_sha256 da estrutura/1 do leitor; um id por sha256, na ordem das camadas. Bytes conferidos pelo
    sha256 e pela assinatura do PNG, nunca decodificados."""
    from desdobra import arquivos
    sha_kv = laudo['origem']['sha256']
    estrutura = Path(pasta) / 'laudo' / 'bruto' / sha_kv / 'estrutura.json'
    try:
        regs = arquivos.ler_json(estrutura).get('camadas') or [] if estrutura.is_file() else []
    except (OSError, ValueError):
        regs = []
    por_id = {}
    for r in regs:
        px = r.get('pixels') or {}
        sha, sha_alfa = px.get('asset_sha256'), px.get('alfa_visivel_sha256')
        if isinstance(r.get('layer_id'), int) and isinstance(sha, str) and re.match(r'^[0-9a-f]{64}$', sha):
            if not (isinstance(sha_alfa, str) and re.match(r'^[0-9a-f]{64}$', sha_alfa)):
                sha_alfa = None
            por_id[r['layer_id']] = (sha, sha_alfa)
    servidos, por_sha, por_camada = {}, {}, {}

    def _ler(s):
        try:
            dados = (Path(pasta) / 'laudo' / 'assets' / ('%s.png' % s)).read_bytes()
        except OSError:
            return None
        if not dados.startswith(ASSINATURA_PNG) or arquivos.sha256_bytes(dados) != s:
            return None
        return dados

    for c in laudo['camadas']:
        lid = c['identidade']['layer_id']
        par = por_id.get(lid)
        if par is None:
            continue
        if par not in por_sha:
            dados = _ler(par[0])
            if dados is None:
                continue
            if par[1] is not None:
                # revisao do 0.9.2 (A7): o asset guarda so os pixels proprios; com mascara (ou com o alfa que o PSD
                # guarda na mascara), a tela mostra a camada com o alfa visivel, sem o quadrado opaco em volta
                dados = _com_alfa_visivel(dados, _ler(par[1])) or dados
            ident = 'a%03d' % (len(por_sha) + 1)
            por_sha[par] = ident
            servidos[ident] = (dados, 'image/png')
        por_camada[lid] = por_sha[par]
    return servidos, por_camada


def _com_alfa_visivel(dados, dados_alfa):
    """O PNG da camada com o alfa visivel (o alfa proprio vezes a mascara, gravado pelo leitor), ou None quando o alfa
    falta ou nao tem o tamanho da camada. Os dois PNG sao do motor, conferidos pelo sha256."""
    import io

    from PIL import Image
    if dados_alfa is None:
        return None
    try:
        with Image.open(io.BytesIO(dados)) as img, Image.open(io.BytesIO(dados_alfa)) as alfa:
            if img.size != alfa.size:
                return None
            rgba = img.convert('RGBA')
            rgba.putalpha(alfa.convert('L'))
            saida = io.BytesIO()
            rgba.save(saida, format='PNG')
            return saida.getvalue()
    except (OSError, ValueError, Image.DecompressionBombError):
        return None


# ------------------------------------------------------------------ montagem
def com_o_passo_2_do_rascunho(pasta, ctx):
    """O contexto da derivacao com as funcoes, as cobertas e o Design system do rascunho da tela por cima do briefing
    gravado, ou do de partida no job novo (revisao do M7a): as familias do passo 3 partem do que "Salvar e seguir" vai
    gravar (desdobra.briefing.salvar.montar). Sem passo 2 no rascunho, ou com ele ainda incompleto (a conferencia do
    motor acha problema), fica o contexto de antes. O passo 2 mudado com a tela aberta vale no proximo GET do estado
    (montar, atualizar); as confirmacoes das familias caem na gravacao (desdobra.tela.rascunho.gravar)."""
    from desdobra.derivacao import nucleo as nd
    conferido = conferencia_do_passo_2(pasta, ctx)
    if conferido is None or conferido[1]:
        return ctx
    novo = conferido[0]
    return nd.contexto(ctx['laudo'], novo, ds=ctx['ds'], job_id=ctx['estado']['job_id'], pasta=ctx['pasta'],
                       briefing_sha256=ctx['briefing_sha256'], portao_fontes=ctx['portao_fontes'],
                       medidas_quebras=ctx['medidas_quebras'], da_tela=True, silhuetas=ctx.get('silhuetas'))


def conferencia_do_passo_2(pasta, ctx):
    """(briefing com o passo 2 e o Design system do rascunho por cima, erros da conferencia do motor sem o modo de
    dados), ou None sem passo 2 no rascunho. Os erros dizem tambem o motivo da espera das Familias (revisao do 0.9.2)."""
    import copy

    from desdobra.briefing import modelo as mb
    from desdobra.briefing import salvar
    from desdobra.tela import funcoes, rascunho
    dados, _de_outro = rascunho.ler(pasta, rascunho.laudo_sha256(pasta))
    if not dados or not dados.get('funcoes'):
        return None
    base = ctx['briefing']
    novo = copy.deepcopy(base)
    quadro = base['quadro']['valor'] if mb._decisao_valida(base['quadro']) else None
    parcial = funcoes.briefing_parcial(dados, quadro)
    tipo = mb.ORIGEM_FIXTURE if dados.get('origem') == mb.ORIGEM_FIXTURE else mb.ORIGEM_DA
    for k in salvar.CAMPOS_DO_RASCUNHO:
        novo[k] = salvar._com_origem(parcial[k], tipo)
    if novo['cabecalho']['origem'] == mb.ORIGEM_RASCUNHO:
        # o de partida (job novo): a previa leva a origem que "Salvar e seguir" vai gravar; so em memoria
        novo['cabecalho'] = dict(novo['cabecalho'], origem=tipo)
    erros = [e for e in mb.conferir(ctx['laudo'], novo, ctx['estado']['job_id'])
             if not (e['codigo'] == 'pendente_obrigatorio' and e.get('onde') == '/modo_dados')]
    return novo, erros




# o passo 3 que espera o passo 2 (job novo, sem briefing confirmado): o aviso da tela, sem identificador do motor
AGUARDA_PASSO_2 = ('As famílias aparecem aqui quando todas as camadas tiverem função, no passo 2, e cada função tiver '
                   'regra de escala e âncora, no Design system.')
AGUARDA_CONFERENCIA = ('As funções e o Design system estão preenchidos, mas o desdobra ainda não consegue montar as '
                       'famílias com essas escolhas. Confira as funções das camadas no passo 2.')
# revisao do 0.9.2: com a lista toda feita e a conferencia do motor recusando, a espera diz o motivo concreto e o botao
# leva ao passo dele (motivo_da_conferencia). {camadas}: o nome das camadas
AGUARDA_CONFERENCIA_COM_MOTIVO = ('As funções e o Design system estão preenchidos, mas o desdobra ainda não consegue '
                                  'montar as famílias. %s')
# revisao 0.9.3: todo codigo da conferencia do motor (desdobra.briefing.modelo.conferir) tem a frase para o DA, o passo
# onde ele se resolve (DESTINO_DO_MOTIVO: 'lido', 'funcoes', 'design' ou 'pecas'; None quando a tela nao tem o
# controle e a frase manda pedir ajuda ao Claude) e o nome curto da lista da espera
# (CURTO_DO_MOTIVO). {camadas}: o nome das camadas; {funcoes}: o nome das funcoes delas (testes/test_tela_revisao_093.py
# percorre todos os codigos)
MOTIVOS_DA_CONFERENCIA = {
    'pendente_obrigatorio': ('Uma escolha obrigatória do briefing ainda está sem valor. Abra a lista Faltam, no alto da '
                             'tela, e resolva o primeiro item.'),
    'indeterminado_sem_observacao': ('A camada {camadas} está com a função indeterminado e ainda não tem a sua '
                                     'observação. Em Funções, escreva a observação ou escolha outra função.'),
    'camada_inexistente': ('As escolhas citam uma camada que o PSD lido agora não tem. Em Funções, confira as camadas e '
                           'escolha a função delas de novo.'),
    'quadro_invalido': ('A prancheta escolhida não existe no PSD lido agora. Escolha de novo a prancheta da peça no '
                        'passo 1.'),
    'quadro_sem_escolha': 'O PSD tem pranchetas, e a peça ainda não diz de qual delas sai. Escolha a prancheta no passo 1.',
    'camada_sem_funcao': 'A camada {camadas} ainda não tem função. Em Funções, escolha a função dela.',
    'coberta_sem_decisao': ('A camada {camadas} fica coberta por outra no KV e ainda espera a sua decisão. Em Funções, '
                            'decida o que fazer com ela.'),
    'regra_de_escala_faltando': ('A função {funcoes} ainda não tem regra de escala. No Design system, escolha o tamanho '
                                 'dessa função.'),
    'ancora_faltando': ('A camada {camadas}, com a função {funcoes}, ainda não tem âncora. No Design system, escolha a '
                        'âncora dessa função.'),
    'formato_repetido': ('Dois formatos do job ficaram com o mesmo nome. Confira os formatos em Valores de spec, no '
                         'passo 1, e peça ajuda ao Claude se a lista estiver certa.'),
    'mestre_invalida': ('Uma família cita um formato que o job não tem mais. Confira os formatos no passo 1 e confirme '
                        'as famílias de novo.'),
    'job_diferente': ('As escolhas salvas são de outro job. Feche esta janela e peça ao Claude para abrir a tela do job '
                      'certo.'),
    'camada_sem_tinta_sem_bloco': ('A camada {camadas} não tem nada visível na peça e não está em nenhum bloco. Em '
                                   'Funções, mude a função dela para Fora da peça.'),
    'mestre_sem_elemento': ('Nenhuma camada ficou dentro da peça: todas estão em Fora da peça ou sem nada visível. Em '
                            'Funções, dê a função certa às camadas que aparecem na peça.'),
    'bloco_com_regras_diferentes': ('As camadas {camadas} andam juntas num bloco, e as funções delas ({funcoes}) têm '
                                    'regras de escala diferentes. No Design system, dê a mesma regra a essas funções.'),
    # revisao 0.9.3 (corretude D2): a regra de bloco (regras_bloco) vem de um briefing salvo fora da tela, e a tela
    # nao tem controle dela; o motivo nao manda a um passo (DESTINO_DO_MOTIVO None) e diz que o Claude resolve
    'regra_de_bloco_conflitante': ('As camadas {camadas} andam juntas num bloco, e o briefing salvo dá a elas regras '
                                   'de bloco que não combinam. Essa regra não se muda na tela. Peça ajuda ao Claude '
                                   'para deixar uma regra só nesse bloco.'),
    'regra_de_bloco_sem_bloco': ('A camada {camadas} tem uma regra de bloco no briefing salvo, mas não anda junto com '
                                 'outra camada. Essa regra não se muda na tela. Peça ajuda ao Claude para tirar a '
                                 'regra de bloco dessa camada.'),
    'quebra_em_caixa_de_paragrafo': ('A quebra de linha da camada {camadas} está num texto de caixa de parágrafo, que '
                                     'quebra sozinho na largura da caixa. Nas Famílias, tire a quebra desse texto.'),
    'quebra_para_formato_inexistente': ('A quebra de linha da camada {camadas} cita um formato que o job não tem '
                                        'mais. Nas Famílias, confira a quebra desse texto.'),
    'quebra_com_faixa_invertida': ('A quebra de linha da camada {camadas} vale para uma faixa de proporções que não '
                                   'existe. Nas Famílias, confira a quebra desse texto.'),
    'quebras_conflitantes': ('A camada {camadas} tem duas quebras de linha diferentes para os mesmos formatos. Nas '
                             'Famílias, fique com uma só.'),
    'quebras_da_mestre_propria_ambiguas': ('A camada {camadas} junta mais de um texto, e a quebra de linha dela não diz '
                                           'de qual texto é. Nas Famílias, confira a quebra desse elemento.'),
    'quebra_aprovada_invalida': ('A quebra de linha da camada {camadas} cita uma posição que o texto não tem. Nas '
                                 'Famílias, confira a quebra desse texto.'),
    'quebra_fora_de_espaco': ('A quebra de linha da camada {camadas} cai fora de um espaço do texto. Nas Famílias, '
                              'mude a quebra para um espaço entre as palavras.'),
    'quebra_fora_da_familia': ('Uma quebra de linha cita uma família que mudou de formatos. Nas Famílias, confira a '
                               'quebra e confirme a família de novo.'),
    'quebra_proposta_sem_aprovacao': ('Uma família confirmada tem uma quebra de linha proposta pelo desdobra que ainda '
                                      'espera a sua aprovação. Nas Famílias, aprove ou mude a quebra.'),
    'composicao_com_formato_inexistente': ('Uma família confirmada cita um formato que o job não tem mais. Nas '
                                           'Famílias, confirme essa família de novo.'),
    'formato_em_duas_composicoes': ('Um formato ficou em duas famílias confirmadas. Nas Famílias, confirme de novo as '
                                    'famílias desse formato.'),
    'formato_id_reservado': ('Um formato do job ficou com um nome que o desdobra não aceita. Peça ajuda ao Claude para '
                             'trocar o nome desse formato.'),
}
DESTINO_DO_MOTIVO = {
    'pendente_obrigatorio': 'lido', 'indeterminado_sem_observacao': 'funcoes', 'camada_inexistente': 'funcoes',
    'quadro_invalido': 'lido', 'quadro_sem_escolha': 'lido', 'camada_sem_funcao': 'funcoes',
    'coberta_sem_decisao': 'funcoes', 'regra_de_escala_faltando': 'design', 'ancora_faltando': 'design',
    'formato_repetido': 'lido', 'mestre_invalida': 'pecas', 'job_diferente': 'lido',
    'camada_sem_tinta_sem_bloco': 'funcoes', 'mestre_sem_elemento': 'funcoes', 'bloco_com_regras_diferentes': 'design',
    'regra_de_bloco_conflitante': None, 'regra_de_bloco_sem_bloco': None, 'quebra_em_caixa_de_paragrafo': 'pecas',
    'quebra_para_formato_inexistente': 'pecas', 'quebra_com_faixa_invertida': 'pecas', 'quebras_conflitantes': 'pecas',
    'quebras_da_mestre_propria_ambiguas': 'pecas', 'quebra_aprovada_invalida': 'pecas', 'quebra_fora_de_espaco': 'pecas',
    'quebra_fora_da_familia': 'pecas', 'quebra_proposta_sem_aprovacao': 'pecas',
    'composicao_com_formato_inexistente': 'pecas', 'formato_em_duas_composicoes': 'pecas', 'formato_id_reservado': 'lido',
}
# revisao 0.9.3 (UX 6): o curto aparece ao lado de "Salvar e seguir" e diz o que fazer, em ate 60 letras
CURTO_DO_MOTIVO = {
    'pendente_obrigatorio': 'Resolva o primeiro item da lista Faltam',
    'indeterminado_sem_observacao': 'Escreva a observação da camada indeterminada',
    'camada_inexistente': 'Confira as camadas em Funções',
    'quadro_invalido': 'Escolha de novo a prancheta no passo 1',
    'quadro_sem_escolha': 'Escolha a prancheta no passo 1',
    'camada_sem_funcao': 'Escolha a função da camada em Funções',
    'coberta_sem_decisao': 'Decida o que fazer com a camada coberta',
    'regra_de_escala_faltando': 'Escolha o tamanho da função no Design system',
    'ancora_faltando': 'Escolha a âncora da função no Design system',
    'formato_repetido': 'Confira os nomes dos formatos no passo 1',
    'mestre_invalida': 'Confirme as famílias de novo',
    'job_diferente': 'Feche a janela e peça ao Claude o job certo',
    'camada_sem_tinta_sem_bloco': 'Mude a camada sem nada visível para Fora da peça',
    'mestre_sem_elemento': 'Dê função às camadas que aparecem na peça',
    'bloco_com_regras_diferentes': 'Dê a mesma regra de tamanho às funções do bloco',
    'regra_de_bloco_conflitante': 'Peça ajuda ao Claude com a regra do bloco',
    'regra_de_bloco_sem_bloco': 'Peça ajuda ao Claude com a regra de bloco',
    'quebra_em_caixa_de_paragrafo': 'Tire a quebra do texto de parágrafo',
    'quebra_para_formato_inexistente': 'Confira a quebra de linha nas Famílias',
    'quebra_com_faixa_invertida': 'Confira a quebra de linha nas Famílias',
    'quebras_conflitantes': 'Fique com uma quebra só para o texto',
    'quebras_da_mestre_propria_ambiguas': 'Confira a quebra de linha nas Famílias',
    'quebra_aprovada_invalida': 'Confira a quebra de linha nas Famílias',
    'quebra_fora_de_espaco': 'Mude a quebra para um espaço entre as palavras',
    'quebra_fora_da_familia': 'Confira a quebra e confirme a família de novo',
    'quebra_proposta_sem_aprovacao': 'Aprove ou mude a quebra proposta',
    'composicao_com_formato_inexistente': 'Confirme a família de novo',
    'formato_em_duas_composicoes': 'Confirme de novo as famílias do formato',
    'formato_id_reservado': 'Peça ao Claude para trocar o nome do formato',
}
# o nome de cada funcao para o DA, como a pagina (tela/tela.js, FUNCOES)
NOMES_DAS_FUNCOES = {
    'fundo': 'fundo', 'imagem': 'imagem', 'sujeito': 'sujeito', 'veu_de_legibilidade': 'véu de legibilidade',
    'grafismo': 'grafismo', 'titulo': 'título', 'texto_de_apoio': 'texto de apoio', 'cta': 'CTA',
    'url_ou_contato': 'URL ou contato', 'texto_legal': 'texto legal', 'informacao_de_evento': 'informação de evento',
    'destaque_numerico': 'destaque numérico', 'icone_de_cta': 'ícone de CTA', 'logo_principal': 'logo principal',
    'assinatura_institucional': 'assinatura institucional', 'selo': 'selo', 'logo_de_parceiro': 'logo de parceiro',
    'ajuste_global': 'ajuste global', 'estrutura': 'estrutura', 'fora_da_peca': 'fora da peça',
    'indeterminado': 'indeterminado',
}
# o passo 2 com escolha faltando e as specs sem formato: a espera leva ao passo do primeiro que falta
CURTO_PASSO_2 = 'Escolha o que falta em Funções ou no Design system'
CURTO_SEM_FORMATOS = 'Escreva os formatos com medida em pixels no passo 1'
CURTO_CONFERENCIA = 'Confira as funções das camadas em Funções'
AGUARDA_QUADRO = 'O PSD tem pranchetas. Escolha no passo 1 de qual prancheta a peça sai, e as famílias aparecem aqui.'
# specs sem nenhum formato em pixels (revisao do M7a): o passo 3 e a lista do que falta dizem o que falta e o que fazer
SEM_FORMATOS = ('As famílias saem dos formatos das specs, e o job ainda não tem nenhum formato com medida em pixels. '
                'Veja no passo 1 o que falta.')
SEM_FORMATOS_FALTA = 'As specs do job ainda não têm nenhum formato com medida em pixels.'
# 0.9.2: sem folha, o DA escreve os formatos na tela (desdobra.specs.digitados)
SEM_FOLHA_DE_SPEC = ('O job ainda não tem folha de spec. Escreva a largura e a altura de cada formato no passo 1, em '
                     'Valores de spec, ou consiga com o veículo a folha com as medidas em pixels e peça para incluí-la '
                     'no job.')
SEM_MEDIDA_EM_PIXELS = ('As folhas de spec do job não trazem uma medida em pixels que o desdobra consiga usar. Se as '
                        'folhas trazem medidas diferentes para o mesmo formato, escolha a certa em Valores de spec. Se a '
                        'medida está em outra unidade, consiga com o veículo a folha em pixels e peça para incluí-la no '
                        'job.')
# as escolhas do passo 1 que ainda faltam (revisao do M7a)
QUADRO_SEM_ESCOLHA = 'Escolha de qual prancheta do PSD a peça sai.'
GIRO_SEM_ESCOLHA = 'Escolha o giro de cada formato.'
# o briefing salvo de outra versao dos arquivos do job: a tela parte do briefing de partida e do rascunho
# (desdobra.briefing.modelo.retomada) e diz o que mudou e o que pede a confirmacao de novo (revisao do M7a)
AVISO_PSD_MUDOU = ('O PSD foi lido de novo depois que o briefing foi salvo. A prancheta, as funções, o design system e '
                   'as famílias precisam ser escolhidos e confirmados de novo. O giro de cada formato continua como '
                   'estava.')
AVISO_SPECS_MUDARAM = ('As specs do job mudaram depois que o briefing foi salvo. Confira os formatos e o giro de cada um '
                       'no passo 1, confirme de novo as famílias que mudaram e salve o briefing outra vez.')
AVISO_FONTES_MUDARAM = ('As fontes ou o design system do PSD mudaram depois que o briefing foi salvo. Confira as '
                        'famílias e salve o briefing outra vez.')


def avisos_de_retomada(pasta, gravado):
    """Os avisos da tela quando o briefing gravado e de outra versao dos arquivos do job ([] quando ele vale ou nao
    ha briefing confirmado)."""
    from desdobra.briefing import modelo as mb
    if gravado is None or gravado['cabecalho']['origem'] == mb.ORIGEM_RASCUNHO:
        return []
    velhos = set(mb.desatualizado(pasta, gravado))
    saida = []
    if 'laudo_sha256' in velhos:
        saida.append(AVISO_PSD_MUDOU)
    if 'specs_sha256' in velhos:
        saida.append(AVISO_SPECS_MUDARAM)
    if velhos & {'ds_sha256', 'conferencia_sha256'}:
        saida.append(AVISO_FONTES_MUDARAM)
    return saida


def _avisos_do_job(pasta):
    from desdobra import contratos
    from desdobra.briefing import historico
    from desdobra.briefing import modelo as mb
    try:
        retomada = avisos_de_retomada(pasta, mb.ler(pasta))
    except contratos.ErroContrato:
        retomada = []
    # o indice do historico mexido fora do desdobra (M7b, A4): so a adulteracao ingenua, risco 177 continua
    return retomada + historico.avisos(pasta)


def com_o_passo_1_do_rascunho(pasta, ctx):
    """O contexto da derivacao com as escolhas do passo 1 do rascunho da tela (a prancheta e o giro de cada formato;
    desdobra.briefing.salvar.escolhas_do_passo_1) por cima do briefing, como "Salvar e seguir" vai gravar. Vale mesmo
    com o passo 2 incompleto: a prancheta escolhe as camadas que o passo 2 mostra. Sem escolha nova, o contexto de
    antes."""
    from desdobra.briefing import modelo as mb
    from desdobra.briefing import salvar
    from desdobra.derivacao import nucleo as nd
    from desdobra.tela import rascunho
    dados, _de_outro = rascunho.ler(pasta, rascunho.laudo_sha256(pasta))
    if not dados or not any(dados.get(k) for k in rascunho.CAMPOS_DO_PASSO_1):
        return ctx
    tipo = mb.ORIGEM_FIXTURE if dados.get('origem') == mb.ORIGEM_FIXTURE else mb.ORIGEM_DA
    novo = salvar.escolhas_do_passo_1(ctx['briefing'], dados, ctx['laudo'], tipo)
    if novo['quadro'] == ctx['briefing']['quadro'] and novo['formatos'] == ctx['briefing']['formatos']:
        return ctx
    return nd.contexto(ctx['laudo'], novo, ds=ctx['ds'], job_id=ctx['estado']['job_id'], pasta=ctx['pasta'],
                       briefing_sha256=ctx['briefing_sha256'], portao_fontes=ctx['portao_fontes'],
                       medidas_quebras=ctx['medidas_quebras'], da_tela=True, silhuetas=ctx.get('silhuetas'))


def _sem_passo_2(pasta):
    """O rascunho da tela ainda nao tem nada do passo 2 nem do Design system."""
    from desdobra.tela import rascunho
    dados = rascunho.ler(pasta, rascunho.laudo_sha256(pasta))[0] or {}
    return not any(dados.get(k) for k in rascunho.CAMPOS_DO_PASSO_2)


def _escolhas_do_passo_1(pasta):
    import json

    from desdobra.tela import rascunho
    dados = rascunho.ler(pasta, rascunho.laudo_sha256(pasta))[0] or {}
    return json.dumps({k: dados.get(k) for k in rascunho.CAMPOS_DO_PASSO_1}, sort_keys=True)


def assinatura_do_passo_2(pasta):
    """A prancheta, o giro (passo 1), o passo 2 e o Design system do rascunho da tela agora, em texto canonico (as
    familias ficam de fora): quando muda, o passo 3 e montado de novo (montar, atualizar). pasta None: a assinatura do
    rascunho sem escolha nenhuma."""
    import json

    from desdobra.tela import rascunho
    dados = None if pasta is None else rascunho.ler(pasta, rascunho.laudo_sha256(pasta))[0]
    return json.dumps({k: (dados or {}).get(k) or {} for k in rascunho.CAMPOS_DAS_ESCOLHAS}, sort_keys=True)


def espera_do_passo_3(pasta, ctx):
    """None quando o briefing do contexto passa na conferencia do motor (o modo de dados fica para o passo 1), senao o
    aviso do passo 3 que espera: as specs sem formato em pixels, a prancheta sem escolha, o passo 2 com escolha
    faltando, ou o passo 2 completo que a conferencia ainda recusa."""
    return espera_e_motivo(pasta, ctx)[0]


def espera_e_motivo(pasta, ctx):
    """(aviso do passo 3 que espera ou None, motivo ou None). O motivo (revisao 0.9.3) e o que a pagina usa para nunca
    contradizer o servidor: {'codigo', 'texto', 'curto', 'passo', 'camadas', 'funcoes'}, com o passo onde a espera se
    resolve ('lido', 'funcoes', 'design', 'pecas' ou None), o nome das camadas e as funcoes envolvidas (a pagina marca os
    cartoes do Design system delas)."""
    from desdobra.briefing import modelo as mb
    from desdobra.tela import funcoes, rascunho
    if not ctx['briefing']['formatos']:
        return SEM_FORMATOS, _motivo('sem_formatos', SEM_FORMATOS, CURTO_SEM_FORMATOS, 'lido')
    erros = [e for e in mb.conferir(ctx['laudo'], ctx['briefing'], ctx['estado']['job_id'])
             if not (e['codigo'] == 'pendente_obrigatorio' and e.get('onde') == '/modo_dados')]
    if not erros:
        return None, None
    quadro = next((e for e in erros if e['codigo'] in ('quadro_sem_escolha', 'quadro_invalido')), None)
    if quadro is not None:
        return AGUARDA_QUADRO, motivo_da_conferencia([quadro], ctx['laudo'])
    dados, _de_outro = rascunho.ler(pasta, rascunho.laudo_sha256(pasta))
    pend = funcoes.pendencias(ctx['laudo'], dados or {}, ctx['info'].get('quadro'))
    if pend:
        primeira = pend[0]
        passo = 'funcoes' if primeira['tipo'] in ('funcao', 'coberta') else 'design'
        f = primeira.get('funcao')
        return AGUARDA_PASSO_2, _motivo('passo_2_incompleto', AGUARDA_PASSO_2, CURTO_PASSO_2, passo,
                                        funcoes=[f] if f else [])
    # o motivo vem da conferencia do briefing com o passo 2 do rascunho por cima (o ctx pode ser o de antes dele)
    conferido = conferencia_do_passo_2(pasta, ctx)
    briefing = conferido[0] if conferido else ctx['briefing']
    try:
        resolvidas = mb.resolver(ctx['laudo'], briefing)[0]
    except (KeyError, TypeError, ValueError):
        resolvidas = {}
    motivo = motivo_da_conferencia(conferido[1] if conferido else erros, ctx['laudo'], resolvidas)
    if motivo is None:
        return AGUARDA_CONFERENCIA, _motivo('conferencia', AGUARDA_CONFERENCIA, CURTO_CONFERENCIA, 'funcoes')
    return AGUARDA_CONFERENCIA_COM_MOTIVO % motivo['texto'], motivo


def _motivo(codigo, texto, curto, passo, camadas=(), funcoes=()):
    return {'codigo': codigo, 'texto': texto, 'curto': curto, 'passo': passo, 'camadas': list(camadas),
            'funcoes': list(funcoes)}


SEM_NOME = 'sem nome'


def lista_pt(itens):
    """Os itens numa frase para o DA (revisao 0.9.3, UX 5): 'a', 'a e b' ou 'a, b e c'; '' sem item."""
    itens = [str(i) for i in itens]
    if not itens:
        return ''
    *inicio, ultimo = itens
    return ', '.join(inicio) + ' e ' + ultimo if inicio else ultimo


def motivo_da_conferencia(erros, laudo, resolvidas=None):
    """O motivo do primeiro erro da conferencia do briefing ({'codigo', 'texto', 'curto', 'passo', 'camadas',
    'funcoes'}), com o nome das camadas e das funcoes delas, ou None quando nenhum erro tem motivo. passo: o lugar da
    tela onde o DA resolve ('lido', 'funcoes', 'design' ou 'pecas'), para onde o botao da espera leva, ou None (o
    Claude resolve; a espera fica sem botao). resolvidas:
    {layer_id: {'funcao', ...}} do briefing conferido, para dizer as funcoes das camadas (revisao 0.9.3)."""
    nomes = {c['identidade']['layer_id']: c.get('nome') or '' for c in laudo.get('camadas') or []}
    resolvidas = resolvidas or {}
    for e in erros:
        codigo = e.get('codigo')
        if codigo not in MOTIVOS_DA_CONFERENCIA:
            continue
        m = e.get('medidas') or {}
        ids = m.get('camadas') or ([m['layer_id']] if m.get('layer_id') is not None else [])
        # revisao 0.9.3 (regressao 4): a camada sem nome nunca mostra o id do motor ao DA
        camadas = [nomes.get(i) or SEM_NOME for i in ids]
        funcoes = []
        for f in ([m['funcao']] if m.get('funcao') else []) + [(resolvidas.get(i) or {}).get('funcao') for i in ids]:
            if f and f not in funcoes:
                funcoes.append(f)
        texto = MOTIVOS_DA_CONFERENCIA[codigo].replace('{camadas}', lista_pt(camadas) or 'citada') \
            .replace('{funcoes}', lista_pt([NOMES_DAS_FUNCOES.get(f, f.replace('_', ' ')) for f in funcoes]) or 'citada')
        return _motivo(codigo, texto, CURTO_DO_MOTIVO[codigo], DESTINO_DO_MOTIVO[codigo], camadas, funcoes)
    return None


def passo_3_na_tela(espera, motivo, aplicado):
    """O passo 3 do estado da tela: se espera, o texto do servidor, o motivo estruturado e o passo para onde o botao da
    espera leva (ir), e se a pagina ja mostra o passo 2 do rascunho."""
    return {'aguarda_passo_2': espera is not None, 'texto': espera or '', 'passo_2_aplicado': aplicado,
            'ir': motivo['passo'] if (espera is not None and motivo) else None,
            'motivo': motivo if espera is not None else None}


def palco_do_documento(laudo, base, resolvidas, quadro):
    """O palco do passo 2 antes de as funcoes fecharem: cada camada desenhavel da peca como ela esta no KV (sem
    transformacao, sem fantasma), com a funcao que a heranca ja da (ou nenhuma). So desenho: nenhuma regra nem ancora."""
    from desdobra.briefing import modelo as mb
    doc = laudo.get('documento') or {}
    canvas = [0.0, 0.0, float(doc.get('largura') or 1), float(doc.get('altura') or 1)]
    q = next((x for x in doc.get('quadros') or [] if x.get('id') == quadro), None)
    if q is not None and q.get('caixa'):
        canvas = [float(v) for v in q['caixa']]
    tr = {'s': 1.0, 'origem_doc': canvas[:2], 'destino': [0.0, 0.0], 'recorte_doc': canvas}
    itens = []
    for c in laudo['camadas']:
        lid = c['identidade']['layer_id']
        if lid not in base or not mb.no_escopo(c, quadro):
            continue
        r = resolvidas.get(lid) or {}
        el = {'id': 'c%d' % lid, 'raiz': lid, 'layer_ids': [lid], 'funcao': r.get('funcao'), 'regra': None,
              'origem_funcao': r.get('por')}
        itens.append((el, tr, _mapear(base[lid]['caixa'], tr), False))
    return _montar_palco(None, canvas[2] - canvas[0], canvas[3] - canvas[1], itens, base, 'kv', None, 'mestre', None,
                         _nomes(laudo))


# ------------------------------------------------------------------ painel de situacao por formato (M7b, B5)
# a situacao de cada formato, como a tela a nomeia (o codigo nunca vai a tela)
ROTULOS_DA_SITUACAO = {
    'sem_derivacao': 'Sem layout',
    'derivado': 'Layout pronto',
    'pede_render': 'Render interrompido',
    'desatualizado': 'Render desatualizado',
    'renderizado': 'Renderizado',
    'aprovado': 'Aprovado',
    'aprovacao_caida': 'Aprovação caiu',
}
# o motivo de cada situacao numa frase simples para o DA
MOTIVOS_DO_PAINEL = {
    'sem_derivacao': 'Este formato ainda não tem layout. Ele espera uma decisão sua em Famílias.',
    'derivado': 'O layout está pronto. Falta o render.',
    'pede_render': 'O render deste formato foi interrompido. Ele pede render de novo.',
    'desatualizado': 'O briefing mudou depois do último render. Este formato pede render de novo.',
    'renderizado': 'O render está em dia. Confira o arquivo final e aprove.',
    'aprovado': 'O arquivo final está aprovado.',
    'aprovacao_caida': 'A aprovação deste formato caiu.',
}
# 0.9.6: o formato sem layout cuja familia o DA ja confirmou, com o motivo real
SEM_LAYOUT_GRAVADO = ('A família deste formato está confirmada, mas o layout dele não foi gravado. Clique em Salvar e '
                      'seguir de novo. Se continuar, fale com a Trezion.')
SEM_LAYOUT_ERRO = ('A família deste formato está confirmada, mas o desdobra teve um erro ao montar o layout dele. '
                   'Fale com a Trezion.')
SEM_LAYOUT_QUEBRA = ('A família deste formato está confirmada, mas a quebra de linha dela ficou sem medida. Tire a '
                     'quebra em Famílias ou fale com a Trezion.')
SEM_LAYOUT_MOTIVO_DO_MOTOR = ('A família deste formato está confirmada, mas o desdobra não monta o layout dele. Fale '
                              'com a Trezion.')
# 0.9.6: o aviso que o DA aceitou ao confirmar a familia (aprovacao soberana)
AVISO_ACEITO = 'Aviso aceito por você'
AVISO_VALIDACAO_ACEITA = 'A conferência do motor pediu ajuste nesta versão.'
# a falha da conferencia que so diz "a conferencia do motor reprova" (desdobra.derivacao.galeria): no aviso aceito, a
# frase concreta de cada validacao toma o lugar dela
CODIGO_VALIDACAO_GENERICA = 'validacao_reprova'
# a frase de cada validacao do motor no aviso aceito (frase_da_validacao): %(elemento)s e o rotulo do elemento ("o
# fundo"), %(onde)s o lado (", na base"), vazio sem ele
FRASES_DA_VALIDACAO = {
    'enquadramento': 'uma parte d%(elemento)s fica fora do formato%(onde)s.',
    'membro_dentro_do_canvas': 'uma parte d%(elemento)s fica fora do formato%(onde)s.',
    'area_util_e_faixa': 'uma parte d%(elemento)s passa da área útil da folha%(onde)s.',
    'membro_dentro_da_area_util': 'uma parte d%(elemento)s passa da área útil da folha%(onde)s.',
    'area_segura': 'uma parte d%(elemento)s passa da área segura%(onde)s.',
    'membro_dentro_da_area_segura': 'uma parte d%(elemento)s passa da área segura%(onde)s.',
    'colisao_nova_contra_a_origem': '%(elemento)s e outro elemento passam a se encostar.',
    'cena_cobre_conteudo': 'parte do fundo cobre %(elemento)s.',
    'corpo_minimo_do_legal': 'o corpo d%(elemento)s fica abaixo do mínimo do legal.',
    'escala_longe_da_regra': 'a escala d%(elemento)s fica longe da prevista.',
    'residuo_da_regra': 'a escala d%(elemento)s fica longe da prevista.',
    'folga_de_resolucao': 'a imagem d%(elemento)s fica ampliada além da resolução dela.',
}
AVISO_TEXTO_CORTADO = 'O texto que você editou sai cortado na borda do formato.'
PEDE_RENDER_DEPOIS_DA_QUEDA = 'Ele pede render antes de uma nova aprovação.'
APROVE_DE_NOVO = 'Confira o arquivo final e aprove de novo.'
RENDER_PAROU_POR_PROBLEMA = 'O último render deste formato parou por um problema. Ele pede render de novo.'
SEM_AFETADOS_REGISTRADOS = 'Esta versão não registrou os formatos afetados.'
NENHUM_AFETADO = 'Nenhum formato mudou.'
# de onde veio cada versao do briefing (o cabecalho: origem e meio)
ORIGENS_DA_VERSAO = {'tela': 'Salva por você na tela', 'fora': 'Salva fora da tela', 'teste': 'Versão de teste',
                     'sem_registro': 'Sem registro de origem'}
PARADAS_CORTADAS = ('parado', 'janela_fechada')  # o DA cancelou ou a janela fechou no meio (Q14)
PEDEM_RENDER = ('derivado', 'pede_render', 'desatualizado')
FORMATO_DA_DATA = '%d/%m/%Y, %H:%M'


def _data(quando):
    """A data do carimbo ISO como a tela mostra (o fuso do carimbo), ou None."""
    import datetime
    try:
        return datetime.datetime.fromisoformat(quando)
    except (TypeError, ValueError):
        return None


def _data_texto(quando):
    d = _data(quando)
    return d.strftime(FORMATO_DA_DATA) if d is not None else None


def origem_da_versao(entrada):
    """A origem de uma versao do historico em palavras (ORIGENS_DA_VERSAO)."""
    origem, meio = entrada.get('origem'), entrada.get('meio')
    if origem == 'fixture_de_teste' or meio in ('medicao', 'importar_teste'):
        return ORIGENS_DA_VERSAO['teste']
    if origem == 'da' and meio == 'tela':
        return ORIGENS_DA_VERSAO['tela']
    if origem == 'da':
        return ORIGENS_DA_VERSAO['fora']
    return ORIGENS_DA_VERSAO['sem_registro']


def _nomes_dos_formatos(fs):
    """{id: nome para o DA}: a medida, como no ato de render (tela.ato_render); duas medidas iguais levam o id."""
    medidas = ['%sx%s' % (f.get('largura'), f.get('altura')) for f in fs]
    return {f['id']: m if medidas.count(m) == 1 else '%s (%s)' % (m, f['id']) for f, m in zip(fs, medidas)}


def nomes_dos_arquivos(fs):
    """{id: nome do arquivo para o DA} nas frases da familia (revisao da 0.10.0): a medida, como o passo 5 a mostra
    (_nomes_dos_formatos), e o giro do formato que vai girado ("1920x1080 girado 270 graus"). O id interno (a chave
    da folha) nunca aparece numa frase, so quando duas medidas sao iguais. fs: os formatos do briefing ou da derivacao
    ({'id', 'largura', 'altura', 'rotacao'})."""
    nomes = _nomes_dos_formatos(fs)
    saida = {}
    for f in fs:
        g = int(((f.get('rotacao') or {}).get('graus')) or 0) % 360  # numero-neutro: graus de uma volta
        saida[f['id']] = nomes[f['id']] + (' girado %d graus' % g if g else '')
    return saida


def nomes_dos_formatos_da_derivacao(formatos, ordem=None):
    """nomes_dos_arquivos dos formatos derivados ({id: derivacao/1}), na ordem do briefing (ordem), quando dada."""
    ids = [f for f in (ordem or sorted(formatos)) if formatos.get(f) is not None]
    return nomes_dos_arquivos([dict(formatos[f]['formato'], id=f) for f in ids])


def arquivo_trocado(familia, grupo):
    """{'de', 'para'} quando o arquivo de edicao gravado da familia editada saiu dela (revisao da 0.10.0): o gravado
    pelo servidor (rascunho._com_a_estrutura) ou, antes da proxima gravacao, o que a tela vai gravar. None no resto.
    familia: a do rascunho gravado; grupo: o da tela (abas)."""
    f = familia or {}
    if f.get('arquivo_trocado'):
        return dict(f['arquivo_trocado'])
    fids = [x['id'] for c in grupo['composicoes'] for x in c['formatos']]
    gravado = f.get('arquivo_de_edicao')
    if gravado and gravado not in fids and (f.get('edicoes') or f.get('quebras')):
        return {'de': gravado, 'para': grupo['arquivo_de_edicao']}
    return None


def frase_do_arquivo_trocado(de, para, nomes=None):
    nomes = nomes or {}
    return ('O arquivo em que você editava esta família, o %s, saiu dela. As suas edições passam a valer no %s, o '
            'maior arquivo que ficou. Confira a família e confirme de novo.' % (nomes.get(de, de), nomes.get(para, para)))


def nomes_da_tela(conteudo):
    """{id: nome do arquivo para o DA} dos formatos que a tela mostra nas familias (abas, o campo 'nome')."""
    saida = {}
    for o in (conteudo.get('estado') or {}).get('orientacoes') or []:
        for g in o.get('grupos') or []:
            for c in g.get('composicoes') or []:
                for x in c.get('formatos') or []:
                    saida[x['id']] = x.get('nome') or x['id']
    return saida


def _entradas_do_historico(pasta):
    from desdobra import contratos
    from desdobra.briefing import historico
    try:
        dados = historico.ler(pasta)
    except (contratos.ErroContrato, OSError, ValueError):
        return []
    return list((dados or {}).get('entradas') or [])


def _mudancas_por_formato(pasta, entradas):
    """{formato: {'versao', 'quando', 'quando_texto', 'itens'}}: os itens da versao mais nova do historico que mexeu
    em cada formato (briefing/historico/mudancas/<seq>.json, esquema historico-mudancas/1). O arquivo ilegivel, fora do
    esquema ou com outro seq dentro que o do nome fica de fora; a data e a da entrada do indice com o mesmo seq e o
    mesmo sha novo."""
    from desdobra import contratos
    from desdobra.briefing import salvar
    pasta_m = Path(pasta) / salvar.PASTA_MUDANCAS
    if not pasta_m.is_dir():
        return {}
    por_seq = {e.get('seq'): e for e in entradas}
    arquivos_ = sorted(((int(a.stem), a) for a in pasta_m.glob('*.json') if re.fullmatch(r'[1-9][0-9]*', a.stem)),
                       reverse=True)
    saida = {}
    for seq, arq in arquivos_:
        try:
            dados = contratos.ler(arq, salvar.ESQUEMA_MUDANCAS)
        except (contratos.ErroContrato, OSError, ValueError):
            continue
        if dados['seq'] != seq:
            continue
        e = por_seq.get(seq)
        quando = e.get('quando') if e is not None and e.get('sha_novo') == dados['sha_novo'] else None
        for fid, itens in dados['formatos'].items():
            saida.setdefault(fid, {'versao': seq, 'quando': quando, 'quando_texto': _data_texto(quando),
                                   'itens': itens})
    return saida


def _historico_na_tela(entradas, nomes):
    """As versoes do briefing, da mais nova para a mais antiga, so para leitura (Q12): numero, data, origem e os
    formatos afetados pela medida (None quando a gravacao nao os calculou)."""
    saida = []
    for e in reversed(entradas):
        afetados = e.get('formatos_afetados')
        ns = None if afetados is None else [nomes.get(f, f) for f in afetados]
        if ns is None:
            texto = SEM_AFETADOS_REGISTRADOS
        elif not ns:
            texto = NENHUM_AFETADO
        else:
            texto = ('Mudou o formato %s.' if len(ns) == 1 else 'Mudou os formatos %s.') % _lista(ns)
        saida.append({'versao': e.get('seq'), 'quando_texto': _data_texto(e.get('quando')),
                      'origem_texto': origem_da_versao(e), 'formatos': ns, 'formatos_texto': texto})
    return saida


def _render_do_formato(pasta, fid, job_id, impressao, atual):
    """(em_dia, tem_render, parada) do render/<fid>/: em dia quando o render.json e deste job e deste formato, o
    master, o contrato e a impressao da derivacao batem com os de agora; parada: o motivo de render/<fid>/parada.json
    ('' quando ilegivel; None sem parada). O portao confere o resto (o contrato refeito) no aprovar."""
    from desdobra import contratos
    from desdobra.render import execucao
    base = Path(pasta) / 'render' / fid
    rel = None
    if atual['render_json_sha256'] is not None and atual['master_sha256'] is not None:
        try:
            rel = contratos.ler(base / 'render.json', execucao.ESQUEMA_RENDER)
        except (contratos.ErroContrato, OSError, ValueError):
            rel = None
    em_dia = rel is not None and impressao is not None and rel['formato']['chave'] == fid and \
        rel['job_id'] == job_id and rel['master']['sha256'] == atual['master_sha256'] and \
        rel['contrato_sha256'] == atual['contrato_sha256'] and \
        (rel.get('derivacao') or {}).get('impressao_formato') == impressao
    parada = None
    if (base / 'parada.json').is_file():
        try:
            from desdobra import arquivos
            dados = arquivos.ler_json(base / 'parada.json')
            parada = dados.get('motivo') if isinstance(dados, dict) and isinstance(dados.get('motivo'), str) else ''
        except (OSError, ValueError):
            parada = ''
    return em_dia, rel is not None, parada


def motivo_sem_layout(d, confirmada):
    """0.9.6: a frase do formato sem layout no passo 5, com o motivo real. d: a derivacao gravada (None sem arquivo);
    confirmada: a familia do formato esta confirmada no briefing. Nunca diz "espera uma decisao sua em Familias" do
    formato cuja familia o DA ja confirmou."""
    from desdobra.derivacao import nucleo as nd
    motivo = ((d or {}).get('devolucao') or {}).get('motivo')
    if motivo in (nd.MOTIVO_SPEC_POR_CONFIRMAR, nd.MOTIVO_MESTRE_POR_CONFIRMAR):
        return texto_da_devolucao(motivo)
    if not confirmada:
        return MOTIVOS_DO_PAINEL['sem_derivacao']
    if d is None:
        return SEM_LAYOUT_GRAVADO
    from desdobra import __version__
    if d.get('motor_versao') != __version__:
        # a derivacao gravada por uma versao de antes (a devolucao da familia confirmada antes da aprovacao soberana):
        # o "Salvar e seguir" volta ligado (briefing.salvar.situacao_na_tela) e monta o layout de novo
        return SEM_LAYOUT_GRAVADO
    codigos = {r.get('codigo') for r in d.get('registros') or []}
    # decisao 199: o arquivo que nao copiou o layout porque o arquivo de edicao ficou sem ele diz o motivo de la
    codigos |= {(r.get('medidas') or {}).get('motivo') for r in d.get('registros') or []
                if r.get('codigo') == 'familia_sem_arquivo_de_edicao'}
    if codigos & {'erro_na_proposta', 'erro_na_galeria'}:
        return SEM_LAYOUT_ERRO
    if 'quebra_sem_medida' in codigos:
        return SEM_LAYOUT_QUEBRA
    return SEM_LAYOUT_MOTIVO_DO_MOTOR


def frase_da_validacao(v, funcoes=None):
    """A frase concreta de uma validacao do motor que reprova ({'nome', 'elementos', 'medidas'}), para o aviso que o
    DA aceitou (0.9.6): o que acontece, com o elemento e o lado quando a validacao os traz. funcoes: {id do elemento:
    funcao}. A validacao sem frase propria fica com AVISO_VALIDACAO_ACEITA."""
    from desdobra.derivacao import galeria as mg
    modelo = FRASES_DA_VALIDACAO.get(v.get('nome'))
    if modelo is None:
        return AVISO_VALIDACAO_ACEITA
    els = list(v.get('elementos') or [])
    rotulo = mg.ROTULO.get((funcoes or {}).get(els[0]), mg.ROTULO_GERAL) if els else mg.ROTULO_GERAL
    medidas = v.get('medidas') or {}
    lados = list(medidas.get('lados') or [])
    for m in medidas.get('membros') or []:
        lados += [x for x in m.get('lados') or [] if x not in lados]
    onde = (', ' + ' e '.join(mg.BORDAS_DO_KV[x] for x in lados if x in mg.BORDAS_DO_KV)) if lados else ''
    frase = modelo % {'elemento': rotulo, 'onde': onde}
    return frase[0].upper() + frase[1:]


def avisos_aceitos(d):
    """0.9.6: as frases dos avisos que o DA aceitou ao confirmar a familia (o registro aprovado_pelo_da_com_aviso da
    derivacao), sem repetir, na ordem. Vazio sem o registro. A falha generica da conferencia ("a conferencia do motor
    reprova") sai pela frase concreta de cada validacao (frase_da_validacao): o DA le o que aceitou."""
    from desdobra.derivacao import proposta
    funcoes = {e.get('id'): e.get('funcao') or (e.get('regra_aplicada') or {}).get('funcao')
               for e in (d or {}).get('elementos') or []}
    frases = []
    for r in (d or {}).get('registros') or []:
        if r.get('codigo') != proposta.CODIGO_APROVADO_COM_AVISO:
            continue
        m = r.get('medidas') or {}
        frases += [f.get('texto') for f in m.get('falhas') or []
                   if f.get('texto') and f.get('codigo') != CODIGO_VALIDACAO_GENERICA]
        frases += [frase_da_validacao(v, funcoes) for v in m.get('validacoes') or []]
        if m.get('texto_na_borda'):
            frases.append(AVISO_TEXTO_CORTADO)
    saida = []
    for x in frases:
        if x not in saida:
            saida.append(x)
    return saida


def _situacao_do_formato(derivado, aprov, em_dia, tem_render, parada, sem_layout=None):
    """(situacao, pede_render, motivo) de um formato (a ordem da decisao: sem layout, aprovacao, render). sem_layout:
    a frase do formato sem layout (motivo_sem_layout); sem ela, a de sempre."""
    if not derivado:
        return 'sem_derivacao', False, sem_layout or MOTIVOS_DO_PAINEL['sem_derivacao']
    if aprov.get('situacao') == 'aprovado':
        return 'aprovado', False, MOTIVOS_DO_PAINEL['aprovado']
    if aprov.get('situacao') == 'caiu':
        motivos = ' '.join(aprov.get('motivos') or [MOTIVOS_DO_PAINEL['aprovacao_caida']])
        return 'aprovacao_caida', not em_dia, \
            '%s %s' % (motivos, APROVE_DE_NOVO if em_dia else PEDE_RENDER_DEPOIS_DA_QUEDA)
    if em_dia:
        return 'renderizado', False, MOTIVOS_DO_PAINEL['renderizado']
    if tem_render:
        return 'desatualizado', True, MOTIVOS_DO_PAINEL['desatualizado']
    if parada is not None:
        return 'pede_render', True, MOTIVOS_DO_PAINEL['pede_render'] if parada in PARADAS_CORTADAS else \
            RENDER_PAROU_POR_PROBLEMA
    return 'derivado', True, MOTIVOS_DO_PAINEL['derivado']


TAMANHO_DA_MARCA = 16  # numero-neutro: caracteres hexadecimais da marca do layout salvo


def _marca_do_layout(d):
    """Uma marca curta da derivacao gravada do formato (None sem ela): muda quando o layout salvo muda, e a pagina pede a
    previa do layout salvo de novo (revisao do M7b, fase B)."""
    if d is None:
        return None
    import hashlib
    import json
    texto = json.dumps(d, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()[:TAMANHO_DA_MARCA]


def palcos_salvos(derivacoes, kv, laudo, base):
    """{formato: palco do layout gravado em derivacao/<formato>.json, ou None}: a previa do passo 5 para o formato sem
    render em dia (revisao do M7b, fase B). A previa da abertura (palco) parte da proposta do motor com o rascunho por
    cima e serve ao passo 3; depois de salvar, o layout do formato e o gravado."""
    saida = {}
    for fid, d in derivacoes.items():
        try:
            saida[fid] = palco(d, kv, laudo, base) if d is not None and d.get('situacao') == 'derivado' else None
        except (KeyError, TypeError, ValueError):
            saida[fid] = None  # a derivacao que nao serve ao palco: a pagina fica com a previa da abertura
    return saida


def _painel_e_aprovacoes(pasta, lidas=None):
    """(painel, aprovacoes): o painel de painel_dos_formatos e a situacao da aprovacao de cada formato
    (entrega.nucleo_aprovar.situacao), medidos com os mesmos hashes (o master e lido uma vez). No job com decisao do DA
    (o que o modo de teste da tela recusa), a aprovacao do modo de teste conta como caida (revisao do M7b, fase B).
    lidas: um dict que recebe {formato: derivacao gravada ou None}, para a previa do layout salvo (montar)."""
    from desdobra import contratos
    from desdobra.briefing import modelo as mb
    from desdobra.derivacao import nucleo as nd
    from desdobra.entrega import nucleo_aprovar, portao
    from desdobra.tela import servidor
    pasta = Path(pasta).resolve()
    aceita_teste = not servidor._job_do_da(pasta)
    vazio = {'formatos': [], 'historico': [], 'afetados': []}
    try:
        b = mb.ler(pasta)
    except (contratos.ErroContrato, OSError, ValueError):
        b = None
    if not b:
        return vazio, nucleo_aprovar.situacao(pasta, aceita_teste=aceita_teste)
    fs = [f for f in b.get('formatos') or [] if isinstance(f, dict) and isinstance(f.get('id'), str)]
    nomes = _nomes_dos_formatos(fs)
    try:
        job_id, _kv = portao.kv_atual(pasta)
    except (contratos.ErroContrato, OSError, ValueError):
        job_id = None
    try:
        params = portao.parametros_de_entrega(pasta)
    except (contratos.ErroContrato, OSError, ValueError):
        params = {}
    derivacoes, hashes = {}, {}
    for f in fs:
        arq = pasta / nd.PASTA / ('%s.json' % f['id'])
        try:
            d = contratos.ler(arq, nd.ESQUEMA) if arq.is_file() else None
        except contratos.ErroContrato:
            d = None
        derivacoes[f['id']] = d
        imp = nd.impressao_de_agora(pasta, d, b) if d is not None else None
        hashes[f['id']] = portao.hashes_do_formato(pasta, f['id'], imp)
    if lidas is not None:
        lidas.update(derivacoes)
    aprovacoes = nucleo_aprovar.situacao(pasta, hashes=hashes, aceita_teste=aceita_teste)
    entradas = _entradas_do_historico(pasta)
    mudancas = _mudancas_por_formato(pasta, entradas)
    linhas = []
    confirmados = {x for c in b.get('composicoes') or [] if c.get('confirmada') for x in c.get('formatos') or []}
    for f in fs:
        fid, d, atual = f['id'], derivacoes[f['id']], hashes[f['id']]
        aprov = aprovacoes.get(fid) or {}
        em_dia, tem_render, parada = _render_do_formato(pasta, fid, job_id, atual['impressao_formato'], atual)
        derivado = d is not None and d.get('situacao') == 'derivado'
        situacao, pede, motivo = _situacao_do_formato(derivado, aprov, em_dia, tem_render, parada,
                                                      sem_layout=motivo_sem_layout(d, fid in confirmados))
        comp = ((d or {}).get('formato') or {}).get('composicao')
        if not (isinstance(comp, list) and len(comp) == 2):  # numero-neutro: [largura, altura]
            comp = [f.get('largura'), f.get('altura')]
        mudou = mudancas.get(fid)
        if mudou is not None and situacao == 'aprovado':
            mudou = None  # o DA aprovou o formato depois da mudanca
        elif mudou is not None and aprov.get('quando'):
            # a aprovacao que caiu por outro motivo depois da versao: a mudanca ja tinha sido vista e aprovada
            antes, depois = _data(mudou['quando']), _data(aprov['quando'])
            if antes is not None and depois is not None and depois > antes:
                mudou = None
        giro = (f.get('rotacao') or {}).get('graus') or 0
        sentido = ((params.get(fid) or {}).get('rotacao_sentido') or {}).get('valor')
        linhas.append({'id': fid, 'nome': nomes[fid], 'largura': f.get('largura'), 'altura': f.get('altura'),
                       'composicao': comp, 'giro': giro, 'sentido': sentido, 'situacao': situacao,
                       'rotulo': ROTULOS_DA_SITUACAO[situacao], 'motivo': motivo, 'pede_render': pede,
                       'pode_aprovar': situacao in ('renderizado', 'aprovacao_caida') and em_dia,
                       'render_em_dia': em_dia, 'mudou': mudou, 'layout': _marca_do_layout(d),
                       # 0.9.6: os avisos que o DA aceitou ao confirmar a familia (aviso discreto no passo 5)
                       'avisos_aceitos': avisos_aceitos(d) if derivado else []})
    painel = {'formatos': linhas, 'historico': _historico_na_tela(entradas, nomes),
              'afetados': [x['id'] for x in linhas if x['pede_render']]}
    return painel, aprovacoes


def painel_dos_formatos(pasta):
    """O painel de situacao por formato da tela (M7b, B5): {'formatos', 'historico', 'afetados'}.

    formatos: uma linha por formato do briefing confirmado, na ordem dele: id, nome (a medida), largura, altura,
    composicao (o tamanho do master, antes do giro), giro e sentido gravado, situacao (sem_derivacao, derivado,
    pede_render, desatualizado, renderizado, aprovado ou aprovacao_caida), rotulo e motivo para o DA, pede_render,
    pode_aprovar, render_em_dia (o master em /render/<id> e o desta versao) e mudou (a lista "o que mudou" da versao
    mais nova do historico que mexeu no formato, com as caixas de antes e de depois; None quando o formato foi aprovado
    depois dela). A situacao sai dos hashes de agora, sem refazer contrato nem arquivo final: o portao confere tudo de
    novo quando o DA aprova. historico: as versoes do briefing, so para leitura (Q12). afetados: os formatos que pedem
    render (o botao "Renderizar os afetados"; o render nunca parte sozinho, Q3). Sem briefing confirmado, tudo vazio."""
    return _painel_e_aprovacoes(pasta)[0]


def _sem_previa(_dados, origem=None, antes=None):
    """A previa da edicao enquanto o passo 3 espera: nenhuma familia para editar."""
    return None


def marca_na_tela(pasta, conferencia):
    """M7c, M3: o bloco da marca do job no passo 1 (desdobra.marca.job.na_tela), sem o caminho da biblioteca. M7c, M4:
    'padrao', o padrao da marca escolhida para o Design system (desdobra.tela.funcoes.padrao_da_marca: regra e ancora
    por funcao com a versao e o job de origem, ou None), lido de novo a cada montagem e a cada recarregar, sem gravar.
    M7c, M5: 'registro', o botao de guardar o padrao da marca (desdobra.marca.registrar.na_tela: so com a marca
    escolhida e todos os formatos aprovados pelo DA, com o que vai ao perfil; sem caminho nem id da marca)."""
    from desdobra.marca import job as marca_job
    from desdobra.marca import registrar
    from desdobra.tela import funcoes as funcoes_da_tela
    bloco = marca_job.na_tela(pasta, conferencia)
    bib = conferencia.pasta if conferencia.usavel else None
    bloco['padrao'] = funcoes_da_tela.padrao_da_marca(pasta, bib)
    bloco['registro'] = registrar.na_tela(pasta, bib)
    return bloco


def montar(pasta, teto=None, biblioteca=None):
    """Conteudo do servidor da tela para o job: {'estado', 'previas', 'assets', 'fontes', 'recarregar', 'editar',
    'familias', 'elementos', 'atualizar', 'biblioteca', 'pasta_biblioteca'}. biblioteca: a pasta da biblioteca da
    agencia que o processo da tela recebeu (M7c, M1), ou None; ela e conferida uma vez aqui, e o passo 1 leva a marca
    do job (lido.marca; M7c, M3), com a lista das marcas lida de novo a cada recarregar. 'biblioteca' e
    'pasta_biblioteca' seguem desdobra.tela.processo.com_biblioteca: o caminho fica so no processo de fundo, para o
    ato da marca. editar(dados, origem) e a previa da edicao por familia
    (desdobra.tela.edicao.Editor.previa); familias: {id: {'formatos', 'versoes', 'pecas', 'por_confirmar', 'aviso'}}
    para o ato de confirmar a familia (o id e o que o job ja conhece para esses formatos; familias_conhecidas e abas);
    elementos: {id: [layer_ids]} da mestre da tela (None enquanto o passo 3 espera), que o rascunho usa para conferir
    a quebra de linha. ErroTela com o motivo (texto fixo do
    motor) quando o job nao tem o que mostrar. teto: o teto do modo de dados da linha de comando (o do estado.json entra
    sozinho). recarregar() refaz o passo 1, a lista do que falta e a frase de cada familia (aviso; a familia
    confirmada deixa de dizer que mudou) depois de um ato da tela, sem derivar de novo: as composicoes e os ids das
    familias seguem os da abertura. atualizar() monta tudo de novo quando o passo 2 do rascunho mudou desde
    esta montagem (None quando nao mudou): o GET do estado leva o passo 3 novo a pagina, sem abrir a tela de novo.

    No job novo, sem briefing confirmado, a tela parte do briefing de partida (desdobra.briefing.modelo.partida: os
    formatos das specs do job e tudo o mais pendente), e nada e gravado na abertura. Enquanto o passo 2 nao passa na
    conferencia do motor, o passo 3 espera (estado passo_3), sem familia nem previa."""
    from desdobra.derivacao import formatos as mf
    from desdobra.derivacao import nucleo as nd
    from desdobra.fontes import casamento
    from desdobra.job import nucleo
    pasta = Path(pasta).resolve()
    from desdobra.briefing import modelo as mb
    from desdobra.sugestao import pacote as sugestao_pacote
    # a fase specs que o ato do modo nao conseguiu refazer (outro processo segurava o job) e refeita aqui, antes de
    # a tela recusar por fase desatualizada: o DA nunca precisa do terminal (revisao 2 da correcao A do M7c, E1)
    sugestao_pacote.curar_specs(pasta, teto)
    assinatura = assinatura_do_passo_2(pasta)
    passo_1 = _escolhas_do_passo_1(pasta)
    try:
        with nucleo.Trava(pasta):
            estado_job = nucleo.ler_estado(pasta)
            # os arquivos do job desta montagem: o ato de spec da tela (ou outro que mude o laudo, as specs, o design
            # system ou as fontes) pede a tela montada de novo no proximo GET do estado (atualizar)
            arquivos_feitos = mb.hashes_atuais(pasta)
            ctx_gravado = nd.preparar(pasta, partida=True)
            # a prancheta e o giro do passo 1 valem antes do passo 2: a prancheta escolhe as camadas que ele mostra
            ctx_base = com_o_passo_1_do_rascunho(pasta, ctx_gravado)
            ctx = com_o_passo_2_do_rascunho(pasta, ctx_base)
            # o passo 3 mostra o passo 2 do rascunho (ou o rascunho nao tem passo 2): a pagina tira o aviso de que as
            # familias ainda sao as de antes
            aplicado = ctx is not ctx_base or _sem_passo_2(pasta)
            espera, motivo_da_espera = espera_e_motivo(pasta, ctx)
            specs, arquivo_specs = mf.specs_do_job(pasta)
            params = mf.parametros(pasta, ctx['briefing'])
            if espera is None:
                # sem as familias ja confirmadas: a tela parte da proposta do motor e leva as edicoes do rascunho por
                # cima, como a derivacao faz depois de "Salvar e seguir" (desdobra.derivacao.proposta)
                r = nd.derivar_em_memoria(ctx, specs=specs, arquivo_specs=arquivo_specs, params=params,
                                          composicoes=False)
            else:
                r = {'formatos': {}, 'devolucoes': [], 'kv': None}
            fontes, lista_fontes, faces = fontes_do_job(pasta, estado_job)
            assets, asset_por_camada = assets_das_camadas(pasta, ctx['laudo'])
            lido_ = lido(pasta, estado_job, ctx['laudo'], ctx['briefing'], r['formatos'], lista_fontes, teto)
    except nd.ErroDerivacao as e:
        raise ErroTela(str(e), e.motivo) from None
    except nucleo.ErroJob as e:
        raise ErroTela(str(e), 'job_ocupado' if int(e.codigo) == int(Codigo.OCUPADO) else 'nao_e_job') from None

    def face_de(ps):
        if not ps:
            return None
        f, _metodo, _n = casamento.casar(ps, faces)
        return f['id'] if f is not None and f['id'] in fontes else None

    from desdobra import biblioteca as mod_biblioteca
    from desdobra.tela import edicao
    from desdobra.tela import funcoes as funcoes_da_tela
    b, laudo = ctx['briefing'], ctx['laudo']
    base = pecas_base(laudo, asset_por_camada, face_de)
    conferencia = mod_biblioteca.conferir(biblioteca)
    pasta_da_biblioteca = conferencia.pasta if conferencia.usavel else None

    def com_previas_dos_quadros(l):
        # a previa de cada prancheta no passo 1: as camadas dela como estao no KV, so desenho; e a marca do job (M7c,
        # M3), com as marcas da biblioteca de agora (a "Marca nova" entra na lista depois do ato)
        for q in l['quadros']:
            q['palco'] = palco_do_documento(laudo, base, ctx['resolvidas'], q['id'])
        l['marca'] = marca_na_tela(pasta, conferencia)
        return l
    com_previas_dos_quadros(lido_)
    previas = {fid: palco(d, r['kv'], laudo, base) for fid, d in r['formatos'].items()}
    brutos = {}
    gals = {}
    # os ids das familias que o job ja conhece: cada id fica com os formatos dele, e nao com a posicao do grupo
    conhecidas = familias_conhecidas(pasta)
    editadas, cedidos = marcas_das_familias(pasta)
    # decisao 199 (0.10.0): o arquivo de edicao gravado de cada familia e os arquivos separados em familia propria
    from desdobra.tela import rascunho as mod_rascunho
    arquivos_gravados, separados = mod_rascunho.estrutura(pasta)
    if espera is None:
        gals = galerias(ctx, r['kv'], laudo, base, r['formatos'],
                        abas(laudo, b, r['formatos'], conhecidas=conhecidas, editadas=editadas, cedidos=cedidos,
                             arquivos=arquivos_gravados, separados=separados),
                        specs=specs, arquivo_specs=arquivo_specs, params=params, brutos=brutos)
    for fid, gal in gals.items():
        previas[fid]['galeria'] = gal
        dv = previas[fid]['devolucao']
        dv['texto'] = texto_da_devolucao(dv['motivo'], len(gal['variantes']))
    n_variantes = {fid: len(gal['variantes']) for fid, gal in gals.items()}
    quadro = ctx['info'].get('quadro')
    kv_palco = palco_kv(r['kv'], laudo, base) if espera is None else \
        palco_do_documento(laudo, base, ctx['resolvidas'], quadro)
    estado = {'esquema': ESQUEMA, 'job_id': estado_job['job_id'], 'somente_leitura': True,
              'briefing_origem': b['cabecalho']['origem'],
              'mestre': {'largura': laudo['documento']['largura'], 'altura': laudo['documento']['altura']},
              'orientacoes': abas(laudo, b, r['formatos'], n_variantes, conhecidas, editadas, cedidos,
                                  arquivos_gravados, separados),
              'fontes': lista_fontes,
              'assets': [{'id': i} for i in sorted(assets)], 'devolucoes': len(r['devolucoes']),
              'lido': lido_,
              'funcoes': {'arvore': arvore(laudo, b, ctx['resolvidas'], quadro),
                          'resumo': resumo_das_funcoes(b, ctx['resolvidas']), 'palco_kv': kv_palco,
                          'decisoes': decisoes_do_passo_2(laudo, quadro)},
              'passo_3': passo_3_na_tela(espera, motivo_da_espera, aplicado),
              'faltam': [],
              # a tolerancia da intencao de alinhamento e os limites do tamanho no palco (M7b, D3)
              'edicao': {'tolerancia_alinhamento': limites.valor('derivacao.alinhamento_intencao_tolerancia'),
                         'escala_min': limites.valor('tela.escala_min'),
                         'escala_max': limites.valor('tela.escala_max')}}
    familias = {g['id']: [x['id'] for co in g['composicoes'] for x in co['formatos']]
                for o in estado['orientacoes'] for g in o['grupos']}
    # o nome de cada arquivo para o DA nas frases (revisao da 0.10.0)
    nomes_dos_formatos_do_job = nomes_dos_formatos_da_derivacao(r['formatos'], [f['id'] for f in b['formatos']])
    avisos = {g['id']: g['aviso'] for o in estado['orientacoes'] for g in o['grupos']}
    grupos_da_tela = {g['id']: g for o in estado['orientacoes'] for g in o['grupos']}
    # decisao 199: o arquivo de edicao de cada familia como a tela mostra (o gravado ou a regra)
    arquivos = {gid: g['arquivo_de_edicao'] for gid, g in grupos_da_tela.items()}
    from desdobra.briefing import salvar
    estado['briefing'] = dict(salvar.situacao_na_tela(pasta, familias, pasta_da_biblioteca), avisos=_avisos_do_job(pasta))
    # a aprovacao de cada formato do briefing (M7b, B4): aprovado, caiu (com o campo e o motivo para o DA) ou sem
    # aprovacao, e o painel de situacao por formato (M7b, B5), medidos a cada montagem e depois de cada ato
    # (recarregar)
    lidas = {}
    estado['painel'], estado['aprovacoes'] = _painel_e_aprovacoes(pasta, lidas)

    def com_os_layouts_salvos(lidas):
        # a previa do layout salvo de cada formato (o passo 5; revisao do M7b, fase B) vai no mesmo dict que o
        # servidor serve em /api/previa/<id>, na chave 'salvo'. A chave existe desde a montagem e so o valor troca
        # depois de cada ato: a leitura da rota nunca ve o dict mudar de tamanho
        salvos = palcos_salvos({fid: lidas.get(fid) for fid in previas}, r['kv'], laudo, base) \
            if r['kv'] is not None else {}
        for fid, p in previas.items():
            p['salvo'] = salvos.get(fid)
    com_os_layouts_salvos(lidas)
    if espera is not None:
        editor = None
    else:
        editor = edicao.Editor(ctx, r['kv'], laudo, base, r['formatos'], brutos, familias,
                               [f for f in faces if f['id'] in fontes], specs=specs, arquivo_specs=arquivo_specs,
                               params=params, arquivos=arquivos)
    versoes = {gid: sorted(editor.versoes(gid)) if editor else [] for gid in familias}
    pecas = {gid: impressao_das_pecas(fids, r['formatos'], versoes[gid], arquivo=arquivos.get(gid))
             for gid, fids in familias.items()}
    # a familia sem edicao vista pela regra de antes da 185 continua valendo: a previa dela e a mesma. A familia sem
    # texto editado vista pela regra de antes da 0.9.6 tambem (rascunho.confirmada_para, 'sem_texto')
    sem_edicao = {gid: {'sem_edicao': impressao_das_pecas(fids, r['formatos'], versoes[gid], regra=REGRA_SEM_EDICAO),
                        'sem_texto': impressao_das_pecas(fids, r['formatos'], versoes[gid],
                                                         regra=REGRA_SEM_TEXTO_EDITADO)}
                  for gid, fids in familias.items()}
    estado['faltam'] = faltam(lido_, r['formatos'], n_variantes, familias,
                              familias_confirmadas(pasta, familias, por_confirmar(r['formatos']), pecas, sem_edicao),
                              arquivos)

    def com_a_reconfirmacao(orientacoes):
        # decisao 199 (5): a familia confirmada antes da 0.10.0 cai uma vez, e a tela diz por que (reconfirmar), ate
        # o DA confirmar de novo. Revisao da 0.10.0: o arquivo de edicao que saiu da familia editada tambem, com os
        # nomes dos dois arquivos
        dados_r, _de_outro = mod_rascunho.ler(pasta, mod_rascunho.laudo_sha256(pasta))
        fams_r = (dados_r or {}).get('familias') or {}
        velhas = {g for g, f in fams_r.items() if mod_rascunho.confirmada_de_antes(f)}

        def frase(g):
            partes = [RECONFIRMAR_0100] if g['id'] in velhas else []
            t = arquivo_trocado(fams_r.get(g['id']), g)
            if t:
                partes.append(frase_do_arquivo_trocado(t['de'], t['para'], nomes_dos_formatos_do_job))
            return ' '.join(partes)
        return [dict(o, grupos=[dict(g, reconfirmar=frase(g)) for g in o['grupos']]) for o in orientacoes]
    estado['orientacoes'] = com_a_reconfirmacao(estado['orientacoes'])

    def com_os_avisos_de_agora():
        # a familia confirmada (ou mexida) depois da montagem: os ids e os formatos ficam, e so a frase de cada uma
        # segue o rascunho de agora, no estado e no que os atos leem (conteudo['familias'])
        agora = avisos_das_familias(pasta, familias, nomes_dos_formatos_do_job)
        for gid, aviso in agora.items():
            conteudo['familias'][gid]['aviso'] = aviso
        return com_a_reconfirmacao([dict(o, grupos=[dict(g, aviso=agora[g['id']]) for g in o['grupos']])
                                    for o in estado['orientacoes']])

    def recarregar():
        novo_job = nucleo.ler_estado(pasta)
        novo_lido = com_previas_dos_quadros(lido(pasta, novo_job, laudo, b, r['formatos'], lista_fontes, teto))
        lidas_agora = {}
        painel, aprovacoes = _painel_e_aprovacoes(pasta, lidas_agora)
        com_os_layouts_salvos(lidas_agora)
        return dict(estado, lido=novo_lido, orientacoes=com_os_avisos_de_agora(),
                    faltam=faltam(novo_lido, r['formatos'], n_variantes, familias,
                                  familias_confirmadas(pasta, familias, por_confirmar(r['formatos']), pecas, sem_edicao),
                                  arquivos),
                    briefing=dict(salvar.situacao_na_tela(pasta, familias, pasta_da_biblioteca), avisos=_avisos_do_job(pasta)),
                    aprovacoes=aprovacoes, painel=painel)

    conteudo = {'estado': estado, 'previas': previas, 'assets': assets, 'fontes': fontes, 'recarregar': recarregar,
                'editar': editor.previa if editor is not None else _sem_previa,
                # os elementos da mestre que a tela mostra, para o rascunho conferir a quebra de linha (revisao 2 do C)
                'elementos': ({e['id']: list(e['layer_ids']) for e in r['kv']['elementos']}
                              if editor is not None else None),
                'familias': {gid: {'formatos': fids, 'versoes': versoes[gid], 'pecas': pecas[gid], 'pecas_sem_edicao': sem_edicao[gid],
                                   'por_confirmar': sorted(set(fids) & por_confirmar(r['formatos'])),
                                   'aviso': avisos[gid],
                                   # decisao 199: o arquivo de edicao (o gravado ou a regra), os separados dela e a
                                   # familia de onde ela saiu, quando o DA a separou
                                   'arquivo_de_edicao': arquivos.get(gid),
                                   'separados': list(grupos_da_tela[gid].get('separados') or []),
                                   'separado_de': grupos_da_tela[gid].get('separado_de')}
                             for gid, fids in familias.items()},
                # a situacao da biblioteca (sem caminho) e a pasta, so no processo de fundo (M7c, M1 e M3)
                'biblioteca': mod_biblioteca.para_tela(conferencia),
                'pasta_biblioteca': conferencia.pasta if conferencia.usavel else None,
                # M7c, S4: a rota leve /api/sugestoes le de novo, a cada pedido, o arquivo validado do modo de agora
                # (com o teto desta tela), sem gravar nada (desdobra.tela.funcoes.sugestoes_na_tela)
                'sugestoes': lambda: funcoes_da_tela.sugestoes_na_tela(pasta, teto)}

    def atualizador(feita, atual):
        def atualizar():
            # cada pedido do estado (e o servidor antes de cada ato): a fase specs atrasada so pelo mapeamento que o
            # ato do modo apagou com o job ocupado e refeita, e o rascunho novo pede a tela montada de novo
            sugestao_pacote.curar_specs(pasta, teto)
            if mb.hashes_atuais(pasta) != arquivos_feitos:
                # o laudo, as specs, o design system ou as fontes mudaram com a tela aberta (o ato de spec do passo
                # 1): os formatos e o briefing de onde a tela parte sao outros
                return montar(pasta, teto, biblioteca)
            if estrutura_de_agora() != estrutura_feita:
                # decisao 199 (0.10.0): o ato da janela trocou o arquivo de edicao ou separou (ou juntou) um arquivo:
                # as familias da tela sao outras
                return montar(pasta, teto, biblioteca)
            nova = assinatura_do_passo_2(pasta)
            if nova == feita:
                return None
            if ctx is ctx_base and _escolhas_do_passo_1(pasta) == passo_1 and                     com_o_passo_2_do_rascunho(pasta, ctx_base) is ctx_base:
                # o passo 2 mudou e ainda nao fecha, como antes: as familias e as previas sao as mesmas, e so o aviso
                # do passo 3 muda (sem derivar de novo a cada clique do DA)
                espera_nova, motivo_novo = espera_e_motivo(pasta, ctx_base)
                p3 = passo_3_na_tela(espera_nova, motivo_novo, _sem_passo_2(pasta))
                novo = dict(atual, estado=dict(atual['estado'], passo_3=p3),
                            recarregar=lambda: dict(recarregar(), passo_3=p3))
                novo['atualizar'] = atualizador(nova, novo)
                return novo
            return montar(pasta, teto, biblioteca)
        return atualizar
    def estrutura_de_agora():
        # o arquivo de edicao efetivo de cada familia mostrada (o gravado que ainda esta nela, senao o de agora) e os
        # separados: a primeira gravacao da familia, que grava o arquivo da regra, nao monta a tela de novo
        gravados, seps = mod_rascunho.estrutura(pasta)
        efetivos = {gid: (gravados[gid] if gravados.get(gid) in fids else arquivos.get(gid))
                    for gid, fids in familias.items()}
        return efetivos, {g: sorted(v) for g, v in seps.items()}
    estrutura_feita = estrutura_de_agora()
    conteudo['atualizar'] = atualizador(assinatura, conteudo)
    return conteudo
