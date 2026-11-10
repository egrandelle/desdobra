# -*- coding: utf-8 -*-
"""Cronometro da mestre na tela (M7b, C5; arquitetura-v1.md, 9.8, Editor de mestre: o tempo para desenhar uma mestre
e medido e registrado; plano do M7b, pergunta 9).

O que mede, por familia: do primeiro clique ou tecla com a familia aberta no passo 3 ate o ato "Confirmar familia" da
janela. O tempo ativo tira as pausas acima de tela.mestre_pausa_max_s sem clique nem tecla; o tempo total vai da
abertura a confirmacao (ou ao ultimo clique, sem confirmacao). Conta tambem as edicoes e as mudancas de quebra de linha
do DA (a aprovacao da quebra proposta nao e mudanca). Regras:
  - a pagina manda um sinal a cada clique ou tecla (no maximo um por segundo; o sinal que espera leva o atraso do
    ultimo clique), com a familia aberta (ou nenhuma, fora do passo 3) e as edicoes e as quebras feitas desde o sinal
    anterior. O servidor da tela confere o sinal (conferir_sinal) com as mesmas conferencias de toda escrita
    (desdobra.tela.servidor, rota POST /api/medicao) e usa o proprio relogio: a pagina so diz o atraso, que nunca leva
    o sinal para antes do sinal anterior;
  - o tempo entre dois sinais vai a familia do primeiro, so enquanto o cronometro dela corre e so ate a pausa maxima:
    trocar de familia, sair do passo 3 ou confirmar nunca contam o mesmo tempo duas vezes;
  - a familia confirmada para: olhar a familia depois nao conta. Ela volta a contar quando o DA mexe nela (o sinal com
    edicao ou quebra) ou quando a confirmacao caiu (o passo 2 mudou, ou a confirmacao ficou velha porque a familia
    ganhou um formato: a mesma regra da tela, revisao do C5); o total segue da abertura;
  - uma sessao por janela aberta (um servidor da tela), gravada so no primeiro sinal, com o id dela; familias soma as
    sessoes. Cada gravacao le o arquivo de agora e troca so a sessao da propria janela (pelo id), no lugar dela: duas
    janelas abertas no mesmo job nunca apagam o que a outra mediu (revisao 2 do C). Cada janela grava a sessao dela
    inteira, do comeco: a gravacao que outro processo cobriu no mesmo instante volta no proximo sinal;
  - medicoes/tela.json (esquema medicoes-tela/1), gravado so por este modulo, de forma atomica: fica fora do briefing e
    fora da impressao de cada formato (desdobra.derivacao.impressao le so a derivacao e o briefing), e nenhuma fase o
    le. O arquivo que nao se le fica ao lado (ARQUIVO_ILEGIVEL) e a medicao recomeca;
  - a medicao nunca atrapalha o DA: a falha ao gravar fica so na memoria, e o sinal e o ato seguem.
"""
import secrets
import threading
import time
from datetime import datetime
from pathlib import Path

from desdobra import arquivos, contratos

ESQUEMA = 'medicoes-tela/1'
ARQUIVO = Path('medicoes') / 'tela.json'
ARQUIVO_ILEGIVEL = Path('medicoes') / 'tela-ilegivel.json'
# o que a pagina manda em cada sinal (tela/tela.js, sinalizar)
CAMPOS_DO_SINAL = ('familia', 'edicoes', 'quebras', 'atraso_ms')
CONTAGEM_MAX = 2 ** 31 - 1  # numero-neutro: o maior inteiro de 32 bits, teto de sanidade de uma contagem da pagina
CASAS = 3  # numero-neutro: milissegundos nos tempos gravados
MS = 1000  # numero-neutro: milissegundos num segundo
ID_BYTES = 8  # numero-neutro: bytes de entropia do id da sessao
# as janelas do mesmo processo gravam uma de cada vez: ler o arquivo, trocar a sessao e gravar, sem outra no meio
_TRAVA_DO_ARQUIVO = threading.Lock()


def _inteiro(v):
    return isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= CONTAGEM_MAX


def conferir_sinal(dados, familias):
    """(familia ou None, edicoes, quebras, atraso em segundos) do sinal da pagina, ou None quando ele nao segue o
    formato: as chaves exatas, a familia entre as da tela agora (ou null, fora do passo 3) e as contagens e o atraso
    inteiros, sem sinal."""
    if not isinstance(dados, dict) or set(dados) != set(CAMPOS_DO_SINAL):
        return None
    gid = dados['familia']
    if gid is not None and (not isinstance(gid, str) or gid not in familias):
        return None
    if not all(_inteiro(dados[k]) for k in ('edicoes', 'quebras', 'atraso_ms')):
        return None
    return gid, dados['edicoes'], dados['quebras'], dados['atraso_ms'] / MS


def ler(pasta):
    """O medicoes/tela.json do job, ou None sem arquivo ou fora do esquema."""
    try:
        return contratos.ler(Path(pasta) / ARQUIVO, ESQUEMA)
    except (contratos.ErroContrato, OSError):
        return None


def _quando(t):
    return datetime.fromtimestamp(t).astimezone().isoformat(timespec='seconds')


def _confirmada_no_rascunho(pasta):
    from desdobra.tela import rascunho

    def confirmada(gid):
        try:
            dados, _de_outro = rascunho.ler(pasta, rascunho.laudo_sha256(pasta))
        except (OSError, ValueError):
            return False  # o rascunho que nao se le agora: a familia conta como aberta
        return bool((((dados or {}).get('familias') or {}).get(gid) or {}).get('confirmada'))
    return confirmada


class Cronometro:
    """O cronometro de uma janela da tela (uma sessao). relogio() -> segundos (time.time; o relogio falso nos
    testes). confirmada(familia) -> bool: a familia esta confirmada como a tela a mostra agora (padrao: o campo do
    briefing/rascunho.json; o servidor da tela passa a dele, que le o rascunho sob a trava de escrita e tira a
    confirmacao velha, desdobra.tela.servidor.ServidorTela._confirmada_na_tela). Chamada fora da trava do cronometro.
    origem: 'da' ou 'fixture_de_teste' (o modo de teste da tela)."""

    def __init__(self, pasta, job_id, *, origem, relogio=None, confirmada=None):
        from desdobra import limites
        self.pasta = Path(pasta)
        self.job_id = job_id
        self.origem = origem
        self.relogio = relogio or time.time
        self.confirmada = confirmada or _confirmada_no_rascunho(self.pasta)
        self.pausa = float(limites.valor('tela.mestre_pausa_max_s'))
        self._trava = threading.Lock()
        self._aberta = self.relogio()
        self._ultimo = None   # o instante do ultimo sinal da sessao
        self._corrente = None  # a familia do ultimo sinal, quando o cronometro dela corre
        self._familias = {}    # {familia: {'inicio', 'ultimo', 'confirmada', 'ativo', 'edicoes', 'quebras'}}
        self._id = secrets.token_hex(ID_BYTES)  # a sessao desta janela no arquivo

    # -------------------------------------------------------------- o que a tela chama
    def sinal(self, familia, edicoes=0, quebras=0, atraso_s=0.0):
        """Um clique ou tecla na pagina, com a familia aberta (None fora do passo 3) e o que o DA fez desde o sinal
        anterior. atraso_s: ha quanto tempo foi o ultimo clique que este sinal leva."""
        chegou = self.relogio()
        # o sinal sem edicao pergunta se a familia esta confirmada antes da trava do cronometro: quem responde pode
        # esperar a trava de escrita do servidor (revisao do C5), e o ato que confirma chama confirmar com ela
        confirmada = familia is not None and not (edicoes or quebras) and self.confirmada(familia)
        with self._trava:
            agora = self.relogio()
            # o atraso so volta ate o sinal anterior (ou a abertura da janela), nunca antes, e nunca passa da pausa
            t = chegou - min(max(float(atraso_s), 0.0), self.pausa)
            t = min(max(t, self._ultimo if self._ultimo is not None else self._aberta), agora)
            self._passar(t)
            f = self._familias.get(familia) if familia is not None else None
            if familia is not None and not (f is not None and f['confirmada'] is None):
                # parado: so o DA mexendo, ou a confirmacao caida, abre (ou reabre) o cronometro
                if edicoes or quebras or not confirmada:
                    f = self._abrir(familia, t)
                else:
                    f = None
            if f is not None:
                f['edicoes'] += edicoes
                f['quebras'] += quebras
                f['ultimo'] = t
            self._corrente = familia if f is not None else None
            self._ultimo = t
            self._gravar()

    def confirmar(self, familia):
        """O ato "Confirmar familia" da janela confirmou a familia: o cronometro dela para agora."""
        with self._trava:
            t = self.relogio()
            if self._ultimo is not None:
                t = max(t, self._ultimo)
            self._passar(t)
            f = self._familias.get(familia)
            if f is None:
                # a confirmacao sem nenhum sinal da familia nesta janela: fica registrada, sem tempo
                f = self._abrir(familia, t)
            f['ultimo'] = t
            f['confirmada'] = t
            self._corrente = None
            self._ultimo = t
            self._gravar()

    # -------------------------------------------------------------- por dentro
    def _abrir(self, familia, t):
        f = self._familias.get(familia)
        if f is None:
            f = {'inicio': t, 'ultimo': t, 'confirmada': None, 'ativo': 0.0, 'edicoes': 0, 'quebras': 0}
            self._familias[familia] = f
        f['confirmada'] = None
        return f

    def _passar(self, t):
        """O tempo desde o ultimo sinal vai a familia dele, quando o cronometro dela corre e a pausa nao passou do
        teto."""
        if self._corrente is None or self._ultimo is None:
            return
        passou = t - self._ultimo
        if 0 < passou <= self.pausa:
            self._familias[self._corrente]['ativo'] += passou

    def _sessao(self):
        familias = {}
        for gid, f in sorted(self._familias.items()):
            fim = f['confirmada'] if f['confirmada'] is not None else f['ultimo']
            familias[gid] = {'aberta_em': _quando(f['inicio']), 'ultima_atividade_em': _quando(f['ultimo']),
                             'confirmada_em': _quando(f['confirmada']) if f['confirmada'] is not None else None,
                             'ativo_s': round(f['ativo'], CASAS), 'total_s': round(max(fim - f['inicio'], 0.0), CASAS),
                             'edicoes': f['edicoes'], 'quebras': f['quebras']}
        ultimo = self._ultimo
        return {'id': self._id, 'aberta_em': _quando(self._aberta),
                'ultima_atividade_em': _quando(ultimo) if ultimo is not None else None,
                'origem': self.origem,
                'ativo_s': round(sum(f['ativo'] for f in self._familias.values()), CASAS),
                'total_s': round(max((ultimo if ultimo is not None else self._aberta) - self._aberta, 0.0), CASAS),
                'familias': familias}

    def _gravadas(self):
        """As sessoes no arquivo de agora, lidas a cada gravacao (as de outras janelas e a desta, se ja gravou). O
        arquivo fora do esquema, ou de outro job, fica ao lado e a medicao recomeca. OSError quando o arquivo nao se
        le agora (outra janela no meio de uma gravacao): quem chama grava no proximo sinal."""
        arq = self.pasta / ARQUIVO
        if not arq.is_file():
            return []
        try:
            dados = contratos.ler(arq, ESQUEMA)
        except contratos.ErroContrato:
            dados = None
        if dados is None or dados['job_id'] != self.job_id:
            try:
                arquivos.gravar_bytes_atomico(self.pasta / ARQUIVO_ILEGIVEL, arq.read_bytes())
            except OSError:
                pass
            return []
        return list(dados['sessoes'])

    def _gravar(self):
        with _TRAVA_DO_ARQUIVO:
            try:
                sessoes = self._gravadas()
            except OSError:
                return  # a medicao nunca atrapalha o DA: a sessao inteira vai no proximo sinal
            esta = self._sessao()
            # a sessao desta janela fica no lugar dela; a primeira gravacao da janela entra no fim
            lugar = next((i for i, x in enumerate(sessoes) if x.get('id') == self._id), len(sessoes))
            sessoes[lugar:lugar + 1] = [esta]
            dados = {'esquema': ESQUEMA, 'job_id': self.job_id, 'pausa_max_s': self.pausa,
                     'atualizado_em': _quando(self.relogio()), 'sessoes': sessoes, 'familias': _somar(sessoes)}
            try:
                contratos.gravar(self.pasta / ARQUIVO, dados, ESQUEMA)
            except (OSError, contratos.ErroContrato):
                pass  # a medicao nunca atrapalha o DA: o que nao gravou fica na memoria e vai no proximo sinal


def _somar(sessoes):
    """As familias somadas sobre as sessoes; confirmada_em e a da ultima sessao em que a familia apareceu."""
    total = {}
    for s in sessoes:
        for gid, f in s['familias'].items():
            t = total.setdefault(gid, {'sessoes': 0, 'confirmada_em': None, 'ativo_s': 0.0, 'total_s': 0.0,
                                       'edicoes': 0, 'quebras': 0})
            t['sessoes'] += 1
            t['confirmada_em'] = f['confirmada_em']
            for k in ('ativo_s', 'total_s'):
                t[k] = round(t[k] + f[k], CASAS)
            for k in ('edicoes', 'quebras'):
                t[k] += f[k]
    return dict(sorted(total.items()))
