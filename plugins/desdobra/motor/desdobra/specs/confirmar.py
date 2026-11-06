# -*- coding: utf-8 -*-
"""desdobra spec confirmar: o DA confirma, valor por valor, o rascunho das specs, num terminal interativo.

So o DA confirma (arquitetura-v1.md, 6: o Claude propoe, o motor extrai, o DA confirma). Por isso o comando:
  - recusa rodar com --envelope (o modo das skills) e sem terminal interativo (stdin que nao e um terminal, como
    o de uma ferramenta de linha de comando chamada pelo modelo);
  - nao tem opcao que confirme sem pergunta, e nenhuma pergunta tem resposta padrao: Enter vazio repete a pergunta;
  - grava cada acao em specs/confirmacoes.json (spec-confirmacoes/1) com quem, o meio e quando, e refaz o
    rascunho e os formatos do job a partir delas.

Tres tipos de pergunta, nesta ordem:
  1. campo com fontes divergentes (o peso por tag do Half-Page): o DA escolhe uma das leituras, cada uma com a fonte;
  2. valor em rascunho: o DA confirma ou pula;
  3. pagina sem camada de texto: o DA abre o recorte e digita o valor de cada campo ao lado dele.
"""
from datetime import datetime
from pathlib import Path

from desdobra import contratos
from desdobra.specs import importar, modelo

O_QUE_FAZER_TERMINAL = ('A confirmação das specs é do DA: rode "desdobra spec confirmar --job <pasta>" num terminal '
                        'interativo, fora do Claude.')
COMANDO = 'spec confirmar'  # o comando humano do Disparo (desdobra.humano.COMANDOS), no terminal e na tela
SAIR = ('s', 'sair')
QUEM_MAPEOU = {'rotulo_da_folha': 'pelo rótulo da própria folha', 'proposta_do_modelo': 'por proposta do Claude',
               'biblioteca': 'pela curadoria da biblioteca de specs', 'da': 'pelo DA'}


class Interrompida(Exception):
    """O DA saiu com Ctrl+C ou fechou a entrada: as respostas dadas ate ali sao gravadas."""


def _agora():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def descrever(v):
    """Texto curto do valor para o DA (bytes com as duas leituras, dimensao, lista)."""
    x = v.get('valor')
    if isinstance(x, dict) and 'alvo_bytes' in x:
        return ('alvo %s bytes, reprova acima de %s bytes (%s %s, base %s)'
                % (format(x['alvo_bytes'], ',d').replace(',', '.'), format(x['reprova_acima_bytes'], ',d').replace(',', '.'),
                   ', '.join(v.get('numeros_literais') or []), v.get('unidade_original') or '', v.get('base_unidade')))
    if isinstance(x, dict) and 'largura' in x:
        return '%s x %s %s' % (x['largura'], x['altura'], v.get('unidade') or '')
    return str(x)


def _trecho_texto(doc, fonte):
    if not fonte or not fonte.get('trecho'):
        return None
    for f in doc['folhas']:
        if f['id'] == fonte['folha']:
            for t in f['trechos']:
                if t['id'] == fonte['trecho']:
                    return t['texto']
    return None


def _onde(r):
    return r.get('chave') or r['id']


def pendencias(doc, filtro_formato=None, filtro_campo=None):
    """Valores que pedem o DA: divergentes primeiro, depois rascunhos com valor. Registro nao entra."""
    divergentes, rascunhos = [], []
    for r, campo, v in modelo.todos_os_valores(doc):
        if filtro_campo and campo != filtro_campo:
            continue
        if filtro_formato and _onde(r) != filtro_formato and r['id'] != filtro_formato:
            continue
        if v['situacao'] != 'rascunho':
            continue
        if v.get('leituras') and v['valor'] is None:
            divergentes.append((r, campo, v))
        elif v['valor'] is not None:
            rascunhos.append((r, campo, v))
    return divergentes + rascunhos


def recortes_pendentes(doc):
    return [(f, r) for f in doc['folhas'] for r in f['recortes']]


class Sessao:
    def __init__(self, pasta, entrada=input, saida=print):
        self.pasta = Path(pasta).resolve()
        self.entrada, self.saida = entrada, saida
        self.novas = []

    def ler(self, texto):
        try:
            return self.entrada(texto) or ''
        except (KeyboardInterrupt, EOFError):
            raise Interrompida() from None

    def perguntar(self, texto, validas):
        while True:
            r = self.ler(texto).strip().lower()
            if r in validas:
                return r

    def _acao(self, **campos):
        campos.update(por='da', meio='terminal', em=_agora())
        self.novas.append(campos)

    def divergente(self, r, campo, v, doc):
        self.saida('\n%s, campo %s: as fontes divergem e o motor não escolhe.' % (_onde(r), campo))
        for i, lei in enumerate(v['leituras'], 1):
            fon = lei['fonte'] or {}
            self.saida('  [%d] %s  (folha %s, página %s, trecho "%s")' % (
                i, descrever(lei), fon.get('folha'), fon.get('pagina'), _trecho_texto(doc, fon) or lei['texto_original']))
        validas = [str(i) for i in range(1, len(v['leituras']) + 1)] + ['p'] + list(SAIR)
        r_ = self.perguntar('Escolha a leitura (número), [p] pular ou [s] sair: ', validas)
        if r_ in SAIR:
            return False
        if r_ != 'p':
            self._acao(acao='escolher_leitura', valor_id=v['id'], impressao=modelo.impressao(v), leitura=int(r_) - 1)
        return True

    def rascunho(self, r, campo, v, doc):
        self.saida('\n%s, campo %s: %s' % (_onde(r), campo, descrever(v)))
        trecho = _trecho_texto(doc, v.get('fonte'))
        if trecho:
            self.saida('  Trecho (folha %s, página %s): "%s"' % (v['fonte']['folha'], v['fonte']['pagina'], trecho))
        corte = (v.get('fonte') or {}).get('recorte_texto')
        if corte is not None:
            self.saida('  O número saiu só deste pedaço do trecho: "%s"' % corte)
        self.saida('  Campo ligado ao trecho %s.' % QUEM_MAPEOU.get(v.get('mapeamento'), 'sem registro de quem'))
        if v['alertas']:
            self.saida('  Alertas: %s' % ', '.join(v['alertas']))
        r_ = self.perguntar('[c] confirmar, [p] pular ou [s] sair: ', ['c', 'p'] + list(SAIR))
        if r_ in SAIR:
            return False
        if r_ == 'c':
            self._acao(acao='confirmar', valor_id=v['id'], impressao=modelo.impressao(v))
        return True

    def recorte(self, folha, recorte):
        self.saida('\nA página %d da folha %s não tem camada de texto. Abra o recorte %s e digite os valores ao lado '
                   'dele.' % (recorte['pagina'], folha['id'], recorte['arquivo']))
        entrada = 1
        campos = modelo.CAMPOS_DIGITAVEIS
        while True:
            c = self.ler('Campo (%s), [n] próxima entrada da página ou Enter para terminar: ' % ', '.join(campos)).strip()
            if not c:
                return True
            if c.lower() == 'n':
                entrada += 1
                continue
            if c not in campos:
                continue
            texto = self.ler('Valor de %s, como está no recorte: ' % c).strip()
            if texto:
                self._acao(acao='digitar', folha=folha['id'], recorte=recorte['id'], campo=c, texto=texto, entrada=entrada)


def gravar_acoes(pasta, novas):
    atual = importar.ler_confirmacoes(pasta)
    n = len(atual['acoes'])
    for a in novas:
        n += 1
        atual['acoes'].append(dict(a, n=n))
    contratos.gravar(Path(pasta) / importar.ARQUIVO_CONFIRMACOES, atual, importar.ESQUEMA_CONFIRMACOES)


def sessao(pasta, *, disparo, entrada=None, saida=print, filtro_formato=None, filtro_campo=None, com_recortes=True,
           plat=None):
    """Roda a sessao do DA. Devolve (acoes novas, rascunho, formatos do job, info).

    disparo: o que desdobra.humano.exigir('spec confirmar') emitiu depois de conferir o console; sem ele, a sessao
    recusa (humano.ErroHumano). As respostas vem do console (humano.ler)."""
    from desdobra import humano
    from desdobra.job import nucleo
    humano.conferir(disparo, 'spec confirmar')
    entrada = entrada or humano.ler
    pasta = Path(pasta).resolve()
    with nucleo.Trava(pasta):
        rascunho, _formatos, _info = importar.importar(pasta, plat=plat)
        s = Sessao(pasta, entrada, saida)
        seguir = True
        try:
            for r, campo, v in pendencias(rascunho, filtro_formato, filtro_campo):
                seguir = (s.divergente if v.get('leituras') and v['valor'] is None else s.rascunho)(r, campo, v, rascunho)
                if not seguir:
                    break
            if seguir and com_recortes:
                for folha, rec in recortes_pendentes(rascunho):
                    if not s.recorte(folha, rec):
                        break
        except Interrompida:
            saida('\nSessão interrompida: as %d resposta(s) dadas até aqui ficam gravadas.' % len(s.novas))
        if s.novas:
            gravar_acoes(pasta, s.novas)
        rascunho, formatos, info = importar.importar(pasta, plat=plat)
        nucleo.registrar_evento(pasta, 'specs_confirmadas', n_acoes=len(s.novas),
                                n_confirmados=rascunho['resumo']['valores_confirmados'])
    return s.novas, rascunho, formatos, info


def pendencias_gravadas(pasta):
    """As pendencias do rascunho de spec gravado do job ([] sem rascunho legivel). So le."""
    arq = Path(pasta) / 'specs' / 'rascunho.json'
    if not arq.is_file():
        return []
    try:
        doc = contratos.ler(arq, 'spec/1')
    except (contratos.ErroContrato, OSError, ValueError):
        return []
    return pendencias(doc)


def confirmar_da_tela(pasta, valor_id, leitura=None, *, disparo):
    """O botao do passo 1 da tela (decisoes-v1.md, 159): confirma um valor em rascunho (leitura None) ou escolhe uma
    leitura de um campo com fontes divergentes. disparo: o da tela (humano.exigir_tela com o comando da confirmacao de
    spec), gasto aqui. A acao grava o meio do Disparo (tela, ou medicao no modo de teste) e por fixture_de_teste no
    modo de teste. Devolve a acao gravada, ou None quando o valor nao e mais pendencia (a folha mudou) ou a leitura nao
    confere.

    A acao e entrada da fase specs, e a fase e refeita aqui mesmo (importar): quando a fase estava em dia antes do ato,
    ela fica gravada em dia de novo (job.nucleo.renovar_fase), e a tela e a derivacao seguem sem passo no terminal
    (revisao do M7a). A fase que ja estava desatualizada por outro motivo (uma folha trocada) fica como estava."""
    from desdobra import humano
    from desdobra.job import nucleo
    humano.conferir(disparo, COMANDO, consumir=True)
    pasta = Path(pasta).resolve()
    with nucleo.Trava(pasta):
        em_dia = nucleo.fase_valida(pasta, 'specs')
        rascunho, _formatos, _info = importar.importar(pasta)
        if em_dia:
            # importar regrava as saidas da fase (com a hora): a fase segue em dia mesmo quando o ato nao grava nada
            nucleo.renovar_fase(pasta, 'specs')
        alvo = next(((r, c, v) for r, c, v in pendencias(rascunho) if v['id'] == valor_id), None)
        if alvo is None:
            return None
        v = alvo[2]
        divergente = bool(v.get('leituras')) and v['valor'] is None
        if divergente != (leitura is not None):
            return None
        acao = {'valor_id': v['id'], 'impressao': modelo.impressao(v), 'por': disparo.origem, 'meio': disparo.meio,
                'em': _agora()}
        if divergente:
            if not isinstance(leitura, int) or isinstance(leitura, bool) or not 0 <= leitura < len(v['leituras']):
                return None
            acao.update(acao='escolher_leitura', leitura=leitura)
        else:
            acao['acao'] = 'confirmar'
        gravar_acoes(pasta, [acao])
        rascunho, _formatos, _info = importar.importar(pasta)
        if em_dia:
            nucleo.renovar_fase(pasta, 'specs')
        nucleo.registrar_evento(pasta, 'specs_confirmadas', n_acoes=1,
                                n_confirmados=rascunho['resumo']['valores_confirmados'])
    return acao
