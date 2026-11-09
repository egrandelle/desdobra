# -*- coding: utf-8 -*-
"""Tarefas longas da tela em segundo plano (M7b, passo B1 do plano; decisoes do Duda Q3, Q4 e Q14).

Um ato da tela que demora (o render dos formatos afetados, no B2) nao roda no fio do pedido HTTP: o servidor da tela
(desdobra.tela.servidor) confirma o ato, responde 202 com o id da tarefa e a pagina acompanha por /api/tarefa/<id>.
Regras:
  - um fio de trabalho unico por servidor, daemon, que nunca termina e roda uma tarefa por vez (o mesmo cuidado do fio
    do HiGHS, decisoes-v1.md, 172: um fio que nasce e morre a cada pedido ja travou a tela);
  - a tarefa segura a trava do job (job.nucleo.Trava) do inicio ao fim. A trava e pega no fio do pedido, antes de a
    tarefa existir (job ocupado: o ato e recusado), e solta no fio de trabalho quando a tarefa acaba. Enquanto isso a
    tela mostra o trabalho em andamento com a edicao bloqueada, e nao o aviso de job ocupado;
  - a tarefa diz a etapa e o formato (progresso) e para quando pedem (parar), entre formatos e entre as etapas do
    render (desdobra.render.execucao). O formato cortado nao grava master: ele pede render de novo, e os prontos ficam;
  - o marcador render/em-andamento.json (ESQUEMA_MARCADOR) fica no job enquanto a tarefa roda, com o PID e a
    identidade do processo, os formatos e os prontos, e sai quando ela acaba com a janela aberta (o DA viu o fim na
    tela). Quando a janela fecha no meio (fechar), o motor pede a parada, espera no maximo tela.parar_max_s, grava
    render/<formato>/parada.json no formato cortado e deixa o marcador como "parada";
  - a tarefa sem marcador (o preparo de um pedido, M7b, B2: so le o job) nao grava marcador nem parada. So o render
    corta formato (TAREFAS_QUE_CORTAM): a aprovacao cortada pela janela grava o marcador, com o aviso dela, e nenhuma
    parada de render (revisao do M7b, fase B);
  - a tarefa que termina todos os formatos acaba "feita", mesmo com o Cancelar ou o fechar da janela chegando tarde
    (depois da ultima conferencia de parar): nada ficou pela metade, o marcador sai e a reabertura nao avisa (revisao
    do M7b, fase B). "cancelada" fica para a tarefa que deixou formato por fazer, ou para o preparo cancelado;
  - a situacao final aparece na vista so junto com o fim: quem ve "feita" ja acha a trava do job solta;
  - na abertura seguinte da tela (recuperar, chamado pelo processo de fundo antes de montar o conteudo), o marcador
    vira um aviso na tela e sai. Quando o processo dele morreu com a trava presa, o motor tira a trava, sem pedir ao
    DA para apagar arquivo. A trava de outro processo, ou de um processo que ainda roda, fica.
Os textos sao do motor, para o DA, sem comando nem nome de arquivo. O motivo da parada vai como codigo; o o_que_fazer
do erro (que fala com a Trezion e cita comando) nunca chega a tela.
"""
import os
import queue
import re
import secrets
import threading
import time
from pathlib import Path

ARQUIVO_MARCADOR = Path('render') / 'em-andamento.json'
ESQUEMA_MARCADOR = 'tela-tarefa/1'
ID_TAREFA = re.compile(r'^[0-9a-f]{32}$')
SITUACOES = ('na_fila', 'rodando', 'feita', 'cancelada', 'parou')
MOTIVO_JANELA_FECHADA = 'janela_fechada'
MOTIVO_PARADO = 'parado'  # o motivo do ErroRender que o render levanta quando pedem a parada entre etapas
TAREFA_PREPARO = 'preparo'  # o nome da tarefa do preparo de um pedido (servidor.Ato.preparar; M7b, B2)
TAREFAS_QUE_CORTAM = ('render',)  # as tarefas cujo formato cortado ganha a parada do render
PID_MAX = 2 ** 32  # numero-neutro: o PID do Windows e um DWORD; o marcador mexido com outro numero conta como ilegivel
TEXTOS = {
    'na_fila': 'O trabalho vai começar.',
    'rodando': 'O desdobra está trabalhando nos formatos. A edição fica parada até ele terminar.',
    'feita': 'O trabalho terminou.',
    'cancelada': 'O trabalho foi cancelado. Os formatos prontos ficaram como estão. O formato que estava no meio fica '
                 'para depois.',
    'parou': 'O trabalho parou por um problema. Os formatos prontos ficaram como estão. Se acontecer de novo, chame a '
             'Trezion.',
}
TEXTOS_POR_TAREFA = {
    'render': {
        'na_fila': 'O render vai começar.',
        'rodando': 'O desdobra está renderizando. A edição fica parada até o render terminar.',
        'feita': 'O render terminou.',
        'cancelada': 'O render foi cancelado. Os formatos prontos ficaram renderizados. O formato que estava no meio '
                     'pede render de novo.',
        'parou': 'O render parou por um problema. Os formatos prontos ficaram renderizados. Os outros pedem render de '
                 'novo. Se acontecer de novo, chame a Trezion.',
    },
    # o ato de aprovar da tela (M7b, B4): a confirmacao confere de novo e grava a aprovacao de cada formato marcado
    'aprovar': {
        'na_fila': 'A aprovação vai começar.',
        'rodando': 'O desdobra está conferindo e gravando a sua aprovação.',
        'feita': 'A aprovação está gravada.',
        'cancelada': 'A aprovação foi cancelada. Nada foi gravado.',
        'parou': 'A aprovação parou por um problema. Nada foi gravado. Se acontecer de novo, chame a Trezion.',
    },
    # o preparo do pedido de um ato longo (M7b, B2): o motor confere os formatos antes de pedir a confirmacao do DA
    TAREFA_PREPARO: {
        'na_fila': 'O desdobra vai conferir os formatos.',
        'rodando': 'O desdobra está conferindo os formatos antes de pedir a sua confirmação.',
        'feita': 'Os formatos estão conferidos. Falta a sua confirmação.',
        'cancelada': 'A conferência dos formatos foi cancelada. Nada mudou no job.',
        'parou': 'A conferência dos formatos parou por um problema. Nada mudou no job.',
    },
}
# o texto da tarefa que parou por um motivo que o DA entende (M7b, B2), no lugar do texto da situacao
TEXTOS_POR_MOTIVO = {
    'formato_bloqueado': 'Um dos formatos ainda não pode ir para o render. Ele precisa de um ajuste antes. '
                         'Nada mudou no job.',
    'contrato_mudou': 'Um formato mudou depois da sua confirmação e ficou sem render. Ele pede render de novo. '
                      'Os outros formatos seguiram.',
    # o ato de aprovar (M7b, B4)
    'formato_com_falha': 'Um dos formatos ainda não pode ser aprovado. Ele precisa de um render novo ou de um ajuste '
                         'antes. Nada mudou no job.',
    'falta_sentido': 'Um formato vai girado para o veículo. Escolha para que lado ele gira antes de aprovar.',
    'sentido_recusado': 'O lado do giro escolhido não serve para este formato. Nada mudou no job.',
    'mudou_durante_a_confirmacao': 'Um formato mudou depois que a confirmação abriu. Nada foi gravado. Peça a '
                                   'aprovação de novo.',
}
ETAPAS = {'contrato': 'Preparando o formato', 'pilhas': 'Montando as imagens', 'texto': 'Desenhando os textos',
          'composicao': 'Juntando a peça', 'gravacao': 'Gravando o arquivo',
          'portao': 'Conferindo o arquivo final', 'aprovacao': 'Gravando a aprovação'}
AVISO_INACABADO = ('O último render não terminou. A janela fechou no meio dele. Os formatos que ficaram sem render '
                   'pedem render de novo.')
# o aviso da reabertura por tarefa (o marcador diz qual era); o marcador ilegivel ou de outra tarefa fica com o do render
AVISOS_INACABADO = {
    'render': AVISO_INACABADO,
    'aprovar': 'A última aprovação não terminou. A janela fechou no meio dela. A aprovação dos formatos marcados não '
               'foi gravada. Peça a aprovação de novo.',
}


class ErroTarefa(Exception):
    """A tarefa nao pode comecar (outra roda neste servidor). motivo: codigo curto."""

    def __init__(self, mensagem, motivo):
        super().__init__(mensagem)
        self.motivo = motivo


class Tarefa:
    """Uma tarefa da tela. A funcao dela recebe a propria tarefa e usa:
        tarefa.parar()                    -> True quando pediram para parar (o DA cancelou ou a janela fechou)
        tarefa.progresso(etapa, formato)  -> a etapa (ETAPAS) e o formato em andamento, para a tela
        tarefa.feito(formato)             -> o formato terminou
    A tela le tarefa.vista(). marcador: a tarefa grava o marcador de render em andamento e, quando a janela fecha no
    meio, a parada do formato cortado (o preparo de um pedido, que nao grava nada no job, roda sem ele)."""

    def __init__(self, nome, formatos, marcador=True):
        self.id = secrets.token_hex(16)  # numero-neutro: bytes de entropia do id
        self.nome = nome
        self.marcador = bool(marcador)
        self.formatos = [str(f) for f in formatos]
        self.situacao = 'na_fila'
        self.etapa = None
        self.formato = None
        self.feitos = []
        self.motivo = None
        self.resposta = None
        self._parar = threading.Event()
        self._fim = threading.Event()
        self._inicio = time.monotonic()
        self._decorrido = None
        self._trava = threading.Lock()

    def parar(self):
        return self._parar.is_set()

    def progresso(self, etapa, formato=None):
        with self._trava:
            self.etapa = etapa
            if formato is not None:
                self.formato = str(formato)
                if self.formato not in self.formatos:
                    self.formatos.append(self.formato)

    def feito(self, formato):
        with self._trava:
            if str(formato) not in self.feitos:
                self.feitos.append(str(formato))

    def terminou(self, espera_s=0):
        """True quando a tarefa acabou (espera ate espera_s segundos)."""
        return self._fim.wait(espera_s)

    @property
    def ativa(self):
        return not self._fim.is_set()

    def faltam(self):
        return [f for f in self.formatos if f not in self.feitos]

    def vista(self):
        """O que a tela mostra: so ids de formato, codigos e os textos do motor."""
        textos = dict(TEXTOS, **TEXTOS_POR_TAREFA.get(self.nome, {}))
        with self._trava:
            decorrido = self._decorrido if self._decorrido is not None else time.monotonic() - self._inicio
            texto = TEXTOS_POR_MOTIVO.get(self.motivo) if self.situacao == 'parou' else None
            return {'id': self.id, 'nome': self.nome, 'situacao': self.situacao, 'etapa': self.etapa,
                    'etapa_texto': ETAPAS.get(self.etapa) if self.situacao == 'rodando' else None,
                    'formato': self.formato, 'formatos': list(self.formatos), 'feitos': list(self.feitos),
                    'faltam': [f for f in self.formatos if f not in self.feitos],
                    'decorrido_s': round(decorrido, 1), 'texto': texto or textos[self.situacao],
                    'motivo': self.motivo, 'resposta': self.resposta if isinstance(self.resposta, dict) else None}


class Tarefas:
    """As tarefas de um servidor da tela, para o job em `pasta`. Uso:
        t = tarefas.iniciar('render', funcao, formatos=[...])   # funcao(tarefa) no fio de trabalho, com a trava
        tarefas.obter(t.id).vista()
        tarefas.cancelar(t.id)
        tarefas.fechar(espera_s)                                # a janela fechou"""

    def __init__(self, pasta):
        self.pasta = Path(pasta).resolve()
        self._tarefas = {}
        self._ultima = None
        self._fila = queue.Queue()
        self._fio = None
        self._fechando = False
        self._trava = threading.Lock()
        self._trava_marcador = threading.Lock()

    @property
    def ocupada(self):
        t = self._ultima
        return t is not None and t.ativa

    @property
    def ultima(self):
        return self._ultima

    def acabadas(self):
        """As tarefas deste servidor que ja acabaram, na ordem em que comecaram."""
        with self._trava:
            todas = list(self._tarefas.values())
        return [t for t in todas if not t.ativa]

    def obter(self, ident):
        return self._tarefas.get(ident) if isinstance(ident, str) else None

    def iniciar(self, nome, funcao, formatos=(), marcador=True):
        """A tarefa nova, ja na fila do fio de trabalho, com a trava do job presa. ErroTarefa quando outra tarefa roda
        neste servidor; job.nucleo.ErroJob quando outro processo do desdobra segura o job. marcador=False: a tarefa
        nao grava nada no job (o preparo de um pedido), e nem o marcador nem a parada sao gravados."""
        from desdobra.job import nucleo
        with self._trava:
            if self.ocupada:
                raise ErroTarefa('Outra tarefa da tela está rodando.', 'tarefa_em_andamento')
            if self._fechando:
                raise ErroTarefa('A tela está fechando.', 'tela_fechando')
            trava = nucleo.Trava(self.pasta)
            trava.__enter__()
            t = Tarefa(nome, formatos, marcador=marcador)
            try:
                if t.marcador:
                    self._gravar_marcador(t, 'rodando')
                if self._fio is None or not self._fio.is_alive():
                    self._fio = threading.Thread(target=self._servir, name='desdobra-tela-tarefas', daemon=True)
                    self._fio.start()
            except BaseException:
                trava.__exit__(None, None, None)
                raise
            self._tarefas[t.id] = t
            self._ultima = t
            self._fila.put((t, funcao, trava))
        return t

    def cancelar(self, ident):
        """Pede a parada da tarefa viva (o DA clicou em cancelar). False quando ela nao existe ou ja acabou."""
        t = self.obter(ident)
        if t is None or not t.ativa:
            return False
        t._parar.set()
        return True

    def fechar(self, espera_s):
        """A janela fechou: pede a parada da tarefa viva e espera no maximo espera_s. O formato cortado ganha
        render/<formato>/parada.json, e o marcador fica como "parada" para o aviso da proxima abertura. A tarefa que
        nao para a tempo segue com a trava ate o processo sair (o filho isolado do render morre com ele). Devolve
        True quando nada ficou rodando."""
        with self._trava:
            self._fechando = True
            t = self._ultima
        if t is None or not t.ativa:
            return True
        t._parar.set()
        parou = t.terminou(float(espera_s))
        if not t.marcador:
            return parou
        with t._trava:
            feita = parou and t.situacao == 'feita'
            cortado = t.formato if t.formato is not None and t.formato not in t.feitos else None
        if feita:
            return parou  # tudo terminou: o fio de trabalho ja tirou o marcador
        if cortado is not None and t.nome in TAREFAS_QUE_CORTAM:
            _gravar_parada(self.pasta, cortado)
        if not parou:
            # a tarefa segue: o marcador fica como "parada" (o fio de trabalho o tira se ela ainda terminar tudo)
            self._gravar_marcador(t, 'parada')
        return parou

    # -------------------------------------------------------------- fio de trabalho
    def _servir(self):
        while True:
            t, funcao, trava = self._fila.get()
            fim = ('parou', 'erro_interno', None)
            try:
                fim = self._rodar(t, funcao)
            finally:
                try:
                    if not t.marcador:
                        pass
                    elif self._fechando and fim[0] != 'feita':
                        self._gravar_marcador(t, 'parada')
                    else:
                        self._apagar_marcador()
                finally:
                    trava.__exit__(None, None, None)
                    # a situacao final aparece junto com o fim: quem ve "feita" ja acha o job solto e a tela livre
                    # para o proximo ato (M7b, B2: o Confirmar logo depois do preparo)
                    with t._trava:
                        t.situacao, t.motivo, t.resposta = fim
                        t._decorrido = time.monotonic() - t._inicio
                        t._fim.set()

    def _rodar(self, t, funcao):
        """(situacao, motivo, resposta) da tarefa. O erro que leva resposta (a lista do que ficou de fora, M7b, B2)
        a entrega a tela junto com o motivo."""
        with t._trava:
            t.situacao = 'rodando'
        situacao, motivo, resposta = 'feita', None, None
        try:
            resposta = funcao(t)
            # o pedido de parar que chegou depois da ultima conferencia nao desfaz o que a funcao terminou: so a
            # tarefa que deixou formato por fazer (ou o preparo, que nao tem formato e cujo dialogo nao abre) e
            # cancelada (revisao do M7b, fase B)
            if t.parar() and (t.faltam() or not t.formatos):
                situacao = 'cancelada'
        except Exception as e:  # noqa: BLE001 - o erro vira situacao e codigo na tela, nunca traceback
            motivo = getattr(e, 'motivo', None) or type(e).__name__
            situacao = 'cancelada' if t.parar() and motivo == MOTIVO_PARADO else 'parou'
            resposta = getattr(e, 'resposta', None)
        return situacao, motivo, resposta

    # -------------------------------------------------------------- marcador
    def _gravar_marcador(self, t, situacao):
        from desdobra import arquivos
        from desdobra.chromium import processos
        from desdobra.render import execucao
        with t._trava:
            formatos, feitos = list(t.formatos), list(t.feitos)
        with self._trava_marcador:
            arq = self.pasta / ARQUIVO_MARCADOR
            arq.parent.mkdir(parents=True, exist_ok=True)
            arquivos.gravar_json_atomico(arq, {
                'esquema': ESQUEMA_MARCADOR, 'tarefa': t.nome, 'pid': os.getpid(),
                'inicio': processos.identidade(os.getpid()), 'quando': execucao.agora(), 'formatos': formatos,
                'feitos': feitos, 'situacao': situacao})

    def _apagar_marcador(self):
        with self._trava_marcador:
            try:
                (self.pasta / ARQUIVO_MARCADOR).unlink()
            except FileNotFoundError:
                pass


def _gravar_parada(pasta, formato):
    """render/<formato>/parada.json do formato que a janela cortou, com o mesmo registro de toda parada do render."""
    from desdobra.render import execucao
    execucao._gravar_parada(pasta, formato, execucao.ErroRender(
        'A janela da tela fechou no meio do render deste formato.', MOTIVO_JANELA_FECHADA))


def _inteiro(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _marcador_valido(m):
    """O marcador como o motor grava: o PID cabe num DWORD (o Windows recusa outro) e a identidade e inteira ou None."""
    return isinstance(m, dict) and m.get('esquema') == ESQUEMA_MARCADOR and \
        _inteiro(m.get('pid')) and 0 < m['pid'] < PID_MAX and \
        (m.get('inicio') is None or _inteiro(m['inicio'])) and \
        isinstance(m.get('formatos'), list) and isinstance(m.get('feitos'), list) and \
        m.get('situacao') in ('rodando', 'parada')


def aviso_depois_da_tarefa(aviso, tarefa):
    """O aviso da reabertura (o de recuperar) depois que a tarefa acabou nesta janela: os formatos que a tarefa do mesmo
    tipo terminou saem dele, e sem formato por fazer o aviso sai (None). O aviso sem formatos (o do marcador ilegivel)
    sai com o primeiro formato terminado. A tarefa de outro tipo (o render depois da aprovacao cortada) ou que nao
    terminou formato nenhum deixa o aviso como esta (segunda revisao do M7b, fase B: a faixa seguia pedindo o que o DA
    ja tinha refeito). O tipo vem do texto do aviso (AVISOS_INACABADO; outro texto conta como o do render)."""
    if not isinstance(aviso, dict) or tarefa is None or tarefa.ativa:
        return aviso
    tipo = next((k for k, t in AVISOS_INACABADO.items() if t == aviso.get('texto')), 'render')
    with tarefa._trava:
        feitos = list(tarefa.feitos)
    if tarefa.nome != tipo or not feitos:
        return aviso
    faltam = [f for f in aviso.get('formatos') or [] if f not in feitos]
    return dict(aviso, formatos=faltam) if faltam else None


def recuperar(pasta):
    """Na abertura da tela, antes de montar o conteudo: o aviso do render que ficou pela metade ({'texto',
    'formatos', 'quando'}), ou None. Tira a trava do job quando ela e do processo do marcador e esse processo morreu
    (mesmo PID e mesma identidade: o PID reaproveitado conta como morto). Com o processo do marcador ainda rodando a
    tarefa (outra tela aberta no job), nada muda e nao ha aviso. O marcador ilegivel avisa sem formatos e nunca tira a
    trava. O marcador lido sai, com o evento render_inacabado no log do job. O texto e o da tarefa do marcador
    (AVISOS_INACABADO: o render ou a aprovacao), e o marcador legivel sem formato por fazer nao avisa (revisao do M7b,
    fase B)."""
    from desdobra import arquivos
    from desdobra.chromium import processos
    from desdobra.job import nucleo
    pasta = Path(pasta).resolve()
    arq = pasta / ARQUIVO_MARCADOR
    if not arq.is_file():
        return None
    try:
        m = arquivos.ler_json(arq)
    except (OSError, ValueError):
        m = None
    if not _marcador_valido(m):
        m = None
    trava_removida = False
    if m is not None:
        proprio = m['pid'] == os.getpid()
        vivo = not proprio and processos.vivo(m['pid'], m.get('inicio'))
        if m['situacao'] == 'rodando' and (proprio or vivo):
            return None
        trava = pasta / nucleo.ARQUIVO_TRAVA
        try:
            dono = int(trava.read_text(encoding='ascii').strip())
        except (OSError, ValueError):
            dono = None
        if dono == m['pid'] and not proprio and not vivo:
            try:
                trava.unlink()
                trava_removida = True
            except OSError:
                pass
    try:
        arq.unlink()
    except OSError:
        pass
    faltam = [f for f in m['formatos'] if f not in m['feitos']] if m is not None else []
    faltam = [f for f in faltam if isinstance(f, str)]
    try:
        nucleo.registrar_evento(pasta, 'render_inacabado', formatos=len(faltam), trava_removida=trava_removida,
                                marcador_legivel=m is not None)
    except OSError:
        pass
    if m is not None and not faltam:
        return None  # o marcador legivel com todos os formatos prontos: nada ficou pela metade
    texto = AVISOS_INACABADO.get(m.get('tarefa'), AVISO_INACABADO) if m is not None else AVISO_INACABADO
    return {'texto': texto, 'formatos': faltam, 'quando': m.get('quando') if m is not None else None}
