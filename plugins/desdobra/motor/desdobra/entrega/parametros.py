# -*- coding: utf-8 -*-
"""Parametros de entrega do job (parametros-entrega/1): o que o DA decide por formato ate a tela do M7.

    desdobra parametros-entrega --job <pasta> --formato <id> [--rotacao-sentido horario|anti_horario]
        [--condicao hospedado|por_tag|tag_carga_inicial|tag_carga_posterior] [--cor-de-achatamento #rrggbb]
        [--borda-1px sim|nao] [--limpar <campo> ...]

Campos (decisoes-v1.md, 137 e 139, e o bloco de parametros do M6):
  - rotacao_sentido: o sentido do giro confirmado com o veiculo, so nos formatos que o briefing gira 90 ou 270 graus
    (nº 139; em 0 e 180 graus o sentido nao importa, e o pedido e recusado);
  - condicao: a condicao do teto de peso (nº 137). Quando a folha confirmada do formato tem teto condicional, so as
    condicoes dela; sem folha ou sem teto condicional, o valor e aceito e registrado;
  - cor_de_achatamento: #rrggbb (gravada em minusculas), a cor sobre a qual o master com transparencia e achatado;
  - borda_1px: a condicao da borda de 1 px declarada pelo DA (sim: o fundo da peca e o da pagina).

So parte do DA, como o aprovar: o handler (desdobra.entrega) pede o Disparo de desdobra.humano.exigir
('parametros-entrega'), mostra o antes e o depois de cada campo e pede o sim digitado; gravar() confere o Disparo e
grava com a trava do job, com confirmado_por do Disparo (meio terminal). O sentido do giro tambem sai da janela de
aprovar da tela (M7b, B4: desdobra.tela.ato_aprovar), com o Disparo da tela do parametros-entrega e a mesma
confirmacao do DA que aprova (gravar_formatos; meio tela, ou medicao com origem fixture_de_teste no modo de teste). O gancho PreToolUse nega o comando e a escrita
direta do arquivo pelo Claude; ler() so confere o contrato, e confirmado_por nao prova quem gravou (risco residual
declarado em docs/m1-interfaces.md, M6).

O arquivo nao entra no cabecalho do briefing nem nos padroes de fase (teste). Giro, achatamento e borda entram nos
parametros do encoder (desdobra.entrega.codificar), entao mudar um deles derruba a aprovacao do formato quando muda o
arquivo final (a cor de achatamento so num master com transparencia; a condicao so quando troca o teto que vale).
"""
import re
from pathlib import Path

from desdobra import contratos, humano
from desdobra.entrega import portao

ESQUEMA = portao.ESQUEMA_PARAMETROS
ARQUIVO = portao.ARQUIVO_PARAMETROS
CAMPOS = ('rotacao_sentido', 'condicao', 'cor_de_achatamento', 'borda_1px')
SENTIDOS = ('horario', 'anti_horario')
CONDICOES = ('hospedado', 'por_tag', 'tag_carga_inicial', 'tag_carga_posterior')
COR = re.compile(r'^#[0-9a-f]{6}$')

DESCRICOES = {
    'sem_briefing': 'O job não tem briefing confirmado: os parâmetros de entrega são por formato do briefing.',
    'briefing_invalido': 'O briefing do job não segue o contrato briefing/1.',
    'formato_inexistente': 'O briefing não tem este formato.',
    'rotacao_nao_decidida': 'A rotação do formato não foi decidida no briefing: o sentido do giro só vale com 90 ou 270 '
                            'graus.',
    'rotacao_sem_quarto_de_volta': 'O formato não gira 90 nem 270 graus no briefing: o sentido do giro não importa e não '
                                   'é gravado.',
    'rotacao_sentido_divergente': 'O briefing já diz o sentido do giro do formato, e o pedido é o outro: a entrega '
                                  'recusaria o formato. Confira o sentido com o veículo e, se o briefing estiver '
                                  'errado, corrija o briefing.',
    'condicao_fora_da_folha':'A folha confirmada do formato não tem teto para esta condição.',
    'cor_invalida': 'A cor de achatamento tem de ser #rrggbb (seis dígitos hexadecimais).',
    'parametros_de_entrega_invalidos': 'parametros/entrega.json não segue o contrato parametros-entrega/1: renomeie o '
                                       'arquivo, grave de novo os parâmetros de cada formato e apague o antigo.',
}


class ErroParametros(Exception):
    """O pedido foi recusado. codigo: chave de DESCRICOES; medidas: o que foi medido."""

    def __init__(self, codigo, medidas=None):
        super().__init__(DESCRICOES.get(codigo, codigo))
        self.codigo, self.medidas = codigo, dict(medidas or {})


def ler(pasta):
    """O arquivo gravado ({'esquema', 'formatos': {}} sem ele). ErroParametros quando nao segue o contrato."""
    arq = Path(pasta) / ARQUIVO
    if not arq.is_file():
        return {'esquema': ESQUEMA, 'formatos': {}}
    try:
        return contratos.ler(arq, ESQUEMA)
    except contratos.ErroContrato:
        raise ErroParametros('parametros_de_entrega_invalidos') from None


def normalizar_cor(valor):
    """#rrggbb em minusculas. ErroParametros fora do padrao."""
    cor = str(valor).strip().lower()
    if not COR.match(cor):
        raise ErroParametros('cor_invalida')
    return cor


def condicoes_da_folha(pasta, formato):
    """Condicoes dos tetos condicionais confirmados na folha do formato, ou None quando a folha nao diz. Com o mesmo
    filtro de codificar.teto_estrito: teto sem valor (dict) nao conta."""
    from desdobra.entrega import codificar
    from desdobra.specs import validar
    try:
        spec = codificar.spec_confirmada(pasta, formato.get('chave'))
    except (OSError, ValueError):
        return None
    condicoes = set()
    for campo in validar.PESOS:
        v = ((spec or {}).get('campos') or {}).get(campo)
        if (v is not None and v.get('situacao') == 'confirmado' and isinstance(v.get('valor'), dict)
                and v.get('condicao')):
            condicoes.add(v['condicao'])
    return sorted(condicoes) or None


def _formato_do_briefing(pasta, formato):
    from desdobra.briefing import modelo as mb
    try:
        b = mb.ler(pasta)
    except contratos.ErroContrato:
        raise ErroParametros('briefing_invalido') from None
    if b is None:
        raise ErroParametros('sem_briefing')
    fmt = next((f for f in b.get('formatos') or [] if f['id'] == formato), None)
    if fmt is None:
        raise ErroParametros('formato_inexistente')
    return fmt


def conferir(pasta, formato, valores):
    """Os valores pedidos ({campo: valor}) conferidos e normalizados contra o briefing e a folha. ErroParametros."""
    fmt = _formato_do_briefing(pasta, formato)
    saida = {}
    for campo, valor in valores.items():
        if campo == 'rotacao_sentido':
            graus = (fmt.get('rotacao') or {}).get('graus')
            if graus is None:
                raise ErroParametros('rotacao_nao_decidida')
            if graus not in portao.GRAUS_QUARTO_DE_VOLTA:
                raise ErroParametros('rotacao_sem_quarto_de_volta', {'graus': graus})
            # o briefing que ja diz o sentido manda: outro sentido o portao recusa (rotacao_sentido_divergente)
            do_briefing = fmt['rotacao'].get('sentido')
            if do_briefing is not None and do_briefing != valor:
                raise ErroParametros('rotacao_sentido_divergente', {'graus': graus, 'sentido_do_briefing': do_briefing})
            saida[campo] = valor
        elif campo == 'condicao':
            da_folha = condicoes_da_folha(pasta, fmt)
            if da_folha is not None and valor not in da_folha:
                raise ErroParametros('condicao_fora_da_folha', {'condicoes': da_folha})
            saida[campo] = valor
        elif campo == 'cor_de_achatamento':
            saida[campo] = normalizar_cor(valor)
        else:
            saida[campo] = bool(valor)
    return saida


def plano(pasta, formato, valores, limpar):
    """{campo: (antes, depois)} so dos campos que mudam (None: sem valor). ErroParametros."""
    dados = ler(pasta)
    novos = conferir(pasta, formato, valores)
    atuais = {k: v['valor'] for k, v in (dados['formatos'].get(formato) or {}).items()}
    mudancas = {}
    for campo in CAMPOS:
        if campo in novos and atuais.get(campo) != novos[campo]:
            mudancas[campo] = (atuais.get(campo), novos[campo])
        elif campo in limpar and campo in atuais:
            mudancas[campo] = (atuais[campo], None)
    return mudancas


def gravar(pasta, formato, valores, limpar, *, disparo):
    """Grava os valores pedidos do formato e tira os campos de limpar, por cima do arquivo (os outros formatos e campos
    ficam). humano.ErroHumano sem o disparo do "parametros-entrega"; ErroParametros quando o pedido nao confere."""
    return gravar_formatos(pasta, {formato: (valores, limpar)}, disparo=disparo)


def gravar_formatos(pasta, pedidos, *, disparo):
    """O gravar de varios formatos com um Disparo so ({formato: (valores, limpar)}): a janela de aprovar da tela grava
    o sentido do giro de cada formato marcado com a mesma confirmacao do DA (M7b, B4). Tudo e conferido antes de gravar:
    um formato recusado (ErroParametros) nao grava nenhum. confirmado_por leva o meio e a origem do Disparo (o do modo de
    teste da tela, fixture_de_teste, o portao da entrega recusa)."""
    humano.conferir(disparo, 'parametros-entrega', consumir=True)
    pasta = Path(pasta).resolve()
    dados = ler(pasta)
    conferidos = {formato: conferir(pasta, formato, valores) for formato, (valores, _limpar) in pedidos.items()}
    formatos = dict(dados['formatos'])
    for formato, (_valores, limpar) in pedidos.items():
        do_formato = dict(formatos.get(formato) or {})
        for campo in limpar:
            do_formato.pop(campo, None)
        for campo, valor in conferidos[formato].items():
            if (do_formato.get(campo) or {}).get('valor') != valor:
                do_formato[campo] = {'valor': valor, 'confirmado_por': dict(disparo.registro(), origem=disparo.origem)}
        if do_formato:
            formatos[formato] = dict(sorted(do_formato.items()))
        else:
            formatos.pop(formato, None)
    saida = {'esquema': ESQUEMA, 'formatos': dict(sorted(formatos.items()))}
    contratos.gravar(pasta / ARQUIVO, saida, ESQUEMA)
    return saida
