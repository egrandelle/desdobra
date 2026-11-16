# -*- coding: utf-8 -*-
"""Formatos digitados pelo DA na tela, sem folha de spec (0.9.2).

Sem folha de spec, o job nao tem formato, e o passo 4 da tela (Familias) nunca monta familia. O DA escreve a largura e
a altura de cada formato em pixels no passo 1, em "Valores de spec" (ato formatos_digitados de desdobra.tela.atos;
comando COMANDO em humano.ATOS_DA_TELA, so pelo Disparo da tela, com a confirmacao na propria janela). A lista fica em
briefing/formatos-digitados.json (formatos-digitados/1), que o gancho do plugin nega ao Claude, como todo briefing/**.

Regras:
  - o arquivo e entrada da fase specs: a importacao (desdobra.specs.importar.montar) poe cada formato no rascunho
    das specs como o formato digitado-<L>x<A> do veiculador digitado, circuito digitado:tela, com a dimensao ja
    confirmada pelo DA (origem digitado_pelo_da_na_tela, desdobra.specs.modelo.valor_digitado_na_tela). O briefing de
    partida, as familias, a derivacao e os formatos do job leem o rascunho como sempre: nenhum leitor novo;
  - so a medida (largura e altura em px). Peso, area segura e faixas ficam sem regra do veiculo;
  - a folha vale quando a medida dela esta confirmada: digitar a medida que a folha ja traz confirmada e recusado na
    hora; a folha que chega depois com a mesma medida esconde o digitado no rascunho so depois de confirmada (revisao
    do 0.9.2: a folha em rascunho nao tira do job a medida que o DA ja confirmou). O arquivo do DA fica intacto, a
    tela marca o item, e o digitado volta se a folha sair. O motor nunca apaga a decisao do DA; tirar da lista e outro
    clique;
  - o arquivo vale so para o job dele (job_id) e dentro do contrato. O arquivo de outro job ou ilegivel nao entra no
    job, e o ato recusa (lista_ilegivel) em vez de gravar por cima e perder o historico (revisao do 0.9.2);
  - o formato digitado no modo de teste da tela (origem fixture_de_teste) nunca chega ao master, a entrega nem ao
    registro da marca (desdobra.entrega.portao.confirmacao_de_teste e o bloqueio formato_digitado_no_modo_de_teste
    do contrato do render);
  - o motor e a autoridade (conferir, no pedido e no Confirmar); a pagina espelha interpretar() para o erro na hora,
    com as mensagens daqui (MENSAGENS, mandadas a pagina em na_tela), uma fonte so dos textos;
  - os lados minimo e maximo, o numero de formatos e o tamanho do texto sao limites (specs.digitado_*);
  - o ato refaz a fase specs no proprio processo e a renova se ela estava em dia, como o ato de spec da tela.
"""
import re
from datetime import datetime
from pathlib import Path

from desdobra import contratos, limites
from desdobra.specs import modelo

ARQUIVO = Path('briefing') / 'formatos-digitados.json'
ESQUEMA = 'formatos-digitados/1'
# o comando do Disparo da tela (humano.ATOS_DA_TELA). Sem o verbo no infinitivo: o nome so aparece no registro
COMANDO = 'formatos digitados'
ACOES = ('acrescentar', 'remover')
VEICULADOR = modelo.VEICULADOR_DIGITADO
ORIGEM_DA = 'da'
# os textos que o DA le na tela, na hora (o espelho da pagina usa estes mesmos, por na_tela). {campo} e trocado pelo
# valor do erro
MENSAGENS = {
    'vazio': 'Escreva pelo menos um formato, como 1080x1920.',
    'nao_entendido': 'Não entendi "{trecho}". Escreva a largura e a altura em pixels, como 1080x1920.',
    'nao_inteiro': 'Use só números inteiros de pixels em "{trecho}", como 1080x1920.',
    'pequeno': 'O formato {largura} x {altura} é pequeno demais. Cada lado precisa ter pelo menos {min} pixels.',
    'grande': ('O formato {largura} x {altura} passa do tamanho que o desdobra aceita. Cada lado pode ter até {max} '
               'pixels.'),
    'repetido_no_texto': 'O formato {largura} x {altura} aparece mais de uma vez no que você escreveu.',
    'ja_na_lista': 'O formato {largura} x {altura} já está na sua lista.',
    'ja_na_folha': 'O formato {largura} x {altura} já vem da folha de spec. Ele já está em Formatos e giro.',
    'demais': 'O job aceita até {max} formatos digitados. Remova algum da lista antes de acrescentar outros.',
    'texto_longo': 'O texto ficou longo demais. Acrescente os formatos em partes.',
    'recusado': 'O desdobra não aceitou estes formatos agora. Confira a lista e tente de novo.',
    'lista_ilegivel': ('A lista de formatos que você escreveu neste job não pôde ser lida, e nada foi gravado por cima '
                       'dela. Conte ao Claude, no chat, o que aparece aqui.'),
}
# a lista colada: virgula, ponto e virgula ou uma por linha. So os brancos comuns (espaco, tab, espaco duro) e so os
# digitos 0 a 9: o espelho em JavaScript tem de dar o mesmo resultado (o \s e o \d do Python e do JS sao outros)
SEPARADOR = re.compile(r'[,;\r\n]+')
BRANCO = '[ \\t\\u00a0]'
APARAR = re.compile(r'^%s+|%s+$' % (BRANCO, BRANCO))
# o numero aceita o milhar com ponto, como o DA escreve no Brasil ("1.080 x 1.920"; revisao do 0.9.2)
NUMERO = r'([0-9]{1,3}(?:[.][0-9]{3})+|[0-9]+)'
MEDIDA = re.compile(r'^{b}*{n}{b}*(?:px)?{b}*[xX×*]{b}*{n}{b}*(?:px)?{b}*$'.format(b=BRANCO, n=NUMERO),
                    re.IGNORECASE)
DECIMAL = re.compile(r'[0-9][.][0-9]')


class ErroDigitado(Exception):
    """O pedido nao vale agora (o codigo de MENSAGENS, ou dados_invalidos e fora_da_lista)."""

    def __init__(self, codigo):
        super().__init__(codigo)
        self.codigo = codigo


def regras():
    """Os limites de agora: {'lado_min', 'lado_max', 'max', 'texto_max'}."""
    return {'lado_min': limites.valor('specs.digitado_lado_min_px'),
            'lado_max': limites.valor('specs.digitado_lado_max_px'),
            'max': limites.valor('specs.digitados_max'),
            'texto_max': limites.valor('specs.digitado_texto_max_caracteres')}


def _erro(codigo, trecho=None, largura=None, altura=None):
    return {'codigo': codigo, 'trecho': trecho, 'largura': largura, 'altura': altura}


def interpretar(texto, r=None):
    """(medidas [(largura, altura)] na ordem, erros [{'codigo', 'trecho', 'largura', 'altura'}]) do texto que o DA
    escreveu. Pura. O espelho e interpretarFormatos, em tela/tela.js."""
    r = r or regras()
    if not isinstance(texto, str):
        return [], [_erro('vazio')]
    if len(texto) > r['texto_max']:
        return [], [_erro('texto_longo')]
    pedacos = [APARAR.sub('', p) for p in SEPARADOR.split(texto)]
    pedacos = [p for p in pedacos if p]
    if not pedacos:
        return [], [_erro('vazio')]
    medidas, erros, repetidas = [], [], set()
    for p in pedacos:
        m = MEDIDA.match(p)
        if m is None:
            erros.append(_erro('nao_inteiro' if DECIMAL.search(p) else 'nao_entendido', trecho=p))
            continue
        largura, altura = int(m.group(1).replace('.', '')), int(m.group(2).replace('.', ''))
        if min(largura, altura) < r['lado_min']:
            erros.append(_erro('pequeno', largura=largura, altura=altura))
        elif max(largura, altura) > r['lado_max']:
            erros.append(_erro('grande', largura=largura, altura=altura))
        elif (largura, altura) in medidas:
            if (largura, altura) not in repetidas:
                repetidas.add((largura, altura))
                erros.append(_erro('repetido_no_texto', largura=largura, altura=altura))
        else:
            medidas.append((largura, altura))
    return medidas, erros


def mensagem(erro, r=None):
    """O texto do erro para o DA, com os valores dele."""
    r = r or regras()
    campos = {'trecho': erro.get('trecho') or '', 'largura': erro.get('largura'), 'altura': erro.get('altura'),
              'min': r['lado_min'], 'max': r['max'] if erro['codigo'] == 'demais' else r['lado_max']}
    texto = MENSAGENS.get(erro['codigo'], MENSAGENS['recusado'])
    for k, v in campos.items():
        texto = texto.replace('{%s}' % k, '' if v is None else str(v))
    return texto


def medida_na_tela(largura, altura):
    return '%d x %d' % (largura, altura)


def frase_das_medidas(medidas):
    """"1080 x 1920", "1080 x 1920 e 300 x 600", "a, b e c"."""
    nomes = [medida_na_tela(*m) for m in medidas]
    return nomes[0] if len(nomes) == 1 else '%s e %s' % (', '.join(nomes[:-1]), nomes[-1])


# ------------------------------------------------------------------ leitura
def _job_id(pasta):
    try:
        return contratos.ler(Path(pasta) / 'estado.json', 'estado/1')['job_id']
    except (contratos.ErroContrato, OSError, ValueError, KeyError):
        return None


def ler_com_problema(pasta):
    """(lista gravada ou None, problema): problema None (lista valida ou sem arquivo), 'ilegivel' (fora do contrato)
    ou 'outro_job' (job_id de outro job, uma copia; revisao do 0.9.2)."""
    arq = Path(pasta) / ARQUIVO
    if not arq.is_file():
        return None, None
    try:
        dados = contratos.ler(arq, ESQUEMA)
    except (contratos.ErroContrato, OSError, ValueError):
        return None, 'ilegivel'
    if dados.get('job_id') != _job_id(pasta):
        return None, 'outro_job'
    return dados, None


def ler(pasta):
    """A lista gravada deste job, ou None (sem arquivo, fora do contrato ou de outro job)."""
    return ler_com_problema(pasta)[0]


def lista(pasta):
    """[(largura, altura)] dos formatos digitados, na ordem da lista do DA."""
    return [(f['largura'], f['altura']) for f in ((ler(pasta) or {}).get('formatos') or [])]


def lista_para_o_modelo(pasta):
    """[{'largura', 'altura', 'confirmacao'}] para desdobra.specs.modelo.Montagem.adicionar_digitados: a confirmacao
    do valor tem quem decidiu (da ou fixture_de_teste), o meio (tela ou medicao) e quando."""
    saida = []
    for f in (ler(pasta) or {}).get('formatos') or []:
        por = f['decidido_por']
        saida.append({'largura': f['largura'], 'altura': f['altura'],
                      'confirmacao': {'por': f['origem'], 'meio': por['meio'], 'em': por['quando'], 'leitura': None}})
    return saida


def rascunho_gravado(pasta):
    from desdobra.specs import importar
    arq = Path(pasta) / importar.ARQUIVO_RASCUNHO
    if not arq.is_file():
        return None
    try:
        return contratos.ler(arq, modelo.ESQUEMA)
    except (contratos.ErroContrato, OSError, ValueError):
        return None


def medidas_da_folha(rascunho):
    """{(largura, altura)} dos formatos da folha de spec com chave e medida em px confirmada no rascunho, as que cobrem
    o digitado (desdobra.specs.modelo.medidas_confirmadas_da_folha). Pura."""
    return modelo.medidas_confirmadas_da_folha((rascunho or {}).get('formatos') or [])


# ------------------------------------------------------------------ conferencia (no pedido e no Confirmar)
def _inteiro(x):
    return isinstance(x, int) and not isinstance(x, bool)


def conferir(pasta, dados):
    """None quando o pedido vale agora; senao o codigo da recusa. dados: {'acao': 'acrescentar', 'texto'} ou {'acao':
    'remover', 'largura', 'altura'}."""
    if not isinstance(dados, dict) or dados.get('acao') not in ACOES:
        return 'dados_invalidos'
    if ler_com_problema(pasta)[1] is not None:
        # o arquivo de outro job ou ilegivel: nada e gravado por cima dele, e o historico fica (revisao do 0.9.2)
        return 'lista_ilegivel'
    atual = lista(pasta)
    if dados['acao'] == 'remover':
        if set(dados) != {'acao', 'largura', 'altura'} or not (_inteiro(dados['largura']) and
                                                              _inteiro(dados['altura'])):
            return 'dados_invalidos'
        return None if (dados['largura'], dados['altura']) in atual else 'fora_da_lista'
    if set(dados) != {'acao', 'texto'} or not isinstance(dados['texto'], str):
        return 'dados_invalidos'
    r = regras()
    medidas, erros = interpretar(dados['texto'], r)
    if erros:
        return erros[0]['codigo']
    if any(m in atual for m in medidas):
        return 'ja_na_lista'
    if any(m in medidas_da_folha(rascunho_gravado(pasta)) for m in medidas):
        return 'ja_na_folha'
    if len(atual) + len(medidas) > r['max']:
        return 'demais'
    return None


# ------------------------------------------------------------------ gravacao (so o Disparo da tela)
def gravar(pasta, dados, *, disparo):
    """Grava o pedido do DA (acrescentar a lista do texto, ou remover uma medida) e refaz a fase specs no proprio
    processo. disparo: o da tela (humano.exigir_tela(COMANDO, ...)), gasto aqui. ErroDigitado quando o pedido nao
    vale agora. Devolve o dado gravado."""
    from desdobra import humano
    from desdobra.job import nucleo
    from desdobra.specs import importar
    humano.conferir(disparo, COMANDO, consumir=True)
    pasta = Path(pasta).resolve()
    with nucleo.Trava(pasta):
        codigo = conferir(pasta, dados)
        if codigo is not None:
            raise ErroDigitado(codigo)
        estado = contratos.ler(pasta / 'estado.json', 'estado/1')
        em_dia = nucleo.fase_valida(pasta, 'specs')
        atual = ler(pasta) or {}
        formatos = list(atual.get('formatos') or [])
        historico = list(atual.get('historico') or [])
        reg = disparo.registro()
        por = {'usuario': reg['usuario'], 'maquina': reg['maquina'], 'meio': reg['meio'], 'quando': reg['quando']}
        if dados['acao'] == 'acrescentar':
            medidas = interpretar(dados['texto'])[0]
            for largura, altura in medidas:
                formatos.append({'largura': largura, 'altura': altura, 'origem': disparo.origem,
                                 'decidido_por': dict(por)})
                historico.append({'acao': 'acrescentar', 'largura': largura, 'altura': altura,
                                  'origem': disparo.origem, 'por': dict(por)})
        else:
            alvo = (dados['largura'], dados['altura'])
            formatos = [f for f in formatos if (f['largura'], f['altura']) != alvo]
            historico.append({'acao': 'remover', 'largura': alvo[0], 'altura': alvo[1], 'origem': disparo.origem,
                              'por': dict(por)})
        novo = {'esquema': ESQUEMA, 'job_id': estado['job_id'], 'formatos': formatos, 'historico': historico}
        contratos.gravar(pasta / ARQUIVO, novo, ESQUEMA)
        nucleo.registrar_evento(pasta, 'formatos_digitados', acao=dados['acao'], formatos=len(formatos),
                                origem=disparo.origem)
        # a lista e entrada da fase specs: a fase e refeita aqui mesmo, e fica em dia se estava (como o ato de spec)
        importar.importar(pasta)
        if em_dia:
            nucleo.renovar_fase(pasta, 'specs')
    return novo


# ------------------------------------------------------------------ o que a tela mostra
def _quando(texto):
    try:
        return datetime.fromisoformat(texto).strftime('%d/%m, %H:%M')
    except (TypeError, ValueError):
        return ''


def na_tela(pasta):
    """O bloco "Formatos sem folha de spec" do passo 1: a lista do DA (com a medida, quando, se a folha ja traz a
    mesma medida e se e de teste), os limites, as medidas da folha (a recusa na hora) e as mensagens do parser."""
    r = regras()
    da_folha = medidas_da_folha(rascunho_gravado(pasta))
    problema = ler_com_problema(pasta)[1]
    itens = []
    for f in (ler(pasta) or {}).get('formatos') or []:
        medida = (f['largura'], f['altura'])
        itens.append({'largura': f['largura'], 'altura': f['altura'], 'medida': medida_na_tela(*medida),
                      'quando': _quando(f['decidido_por'].get('quando')), 'na_folha': medida in da_folha,
                      'teste': f['origem'] != ORIGEM_DA})
    return {'lista': itens, 'lado_min': r['lado_min'], 'lado_max': r['lado_max'], 'max': r['max'],
            'texto_max': r['texto_max'], 'da_folha': sorted([list(m) for m in da_folha]),
            'mensagens': dict(MENSAGENS), 'problema': MENSAGENS['lista_ilegivel'] if problema else ''}
