# -*- coding: utf-8 -*-
"""Chromium fixado aberto enquanto a tela esta aberta, para a medida da quebra de linha ao vivo (M7b, C3).

Sem ele, cada medida sem cache (derivacao.medida_quebras) abre e fecha o Chromium fixado com um perfil novo
(navegador.conferir), e quase todo o tempo da remedicao e abrir e fechar. O processo da tela (desdobra.tela.processo)
liga um NavegadorAberto na medida das quebras (medida_quebras.usar_aberto) enquanto a janela esta aberta; a CLI e a
derivacao fora da tela continuam no caminho frio. O render (navegador.imprimir), a conferencia de fontes e o doctor
nao passam por aqui.

Regras:
  - um fio so (NOME_FIO) abre o Playwright e fala com ele, porque a API sincrona do Playwright fica presa ao fio que a
    abriu, e o servidor da tela atende cada pedido num fio. Quem mede poe o pedido na fila do fio e espera no maximo
    chromium.aberto_espera_max_s (a abertura do Chromium conta nessa espera); um pedido de cada vez;
  - o Chromium so abre na primeira medida sem cache. O perfil e um dsd-tela- com dono (navegador.perfil_tela): a
    varredura de orfas da proxima tela, ou do doctor, apaga o que uma queda do processo deixar. A pasta de artefatos
    do Playwright (downloads e afins; PASTA_ARTEFATOS) fica dentro do perfil, nunca solta na pasta temporaria, e os
    contextos recusam download. Antes de abrir, o processo se amarra ao Job Object (processos.amarrar_ao_processo): o
    Chromium morre junto com o Python. Sem a amarra, o aberto nao abre, e toda medida sai pelo caminho frio;
  - cada fio tem o seu driver do Playwright e o seu Chromium: o fio cujo Chromium caiu, ou cujo driver morreu, sai e
    fecha o que e dele, e o pedido seguinte abre um fio novo;
  - cada medida roda num contexto novo sem perfil (browser.new_context, o cache dele fica so na memoria), fechado no
    fim da medida, com a mesma pagina, a mesma janela de medida e as mesmas linhas de medida do caminho frio
    (navegador.medir_na_pagina). O contexto persistente do perfil so carrega, na abertura, a folha do controle positivo
    com cache liberado, que prova que o perfil grava cache;
  - toda vez que o Chromium fecha (fecho da tela, queda, trava), o fio varre o perfil inteiro com o Chromium ja fechado
    atras de copia das fontes servidas a ele (navegador.varrer_perfil, com nova tentativa enquanto algum arquivo nao se
    le) e apaga o perfil. O relatorio guarda so contagens;
  - o Chromium que caiu (a medida falhou): este pedido sai pelo caminho frio na hora, sem esperar o fecho; o fio
    fecha o que sobrou, varre e apaga o perfil depois de responder, e o proximo pedido abre um fio novo, sem esperar
    esse fecho. O driver do Playwright que morreu (quem pede confere o processo dele antes de cada pedido) conta como
    queda: com o driver morto, o Playwright espera para sempre o fecho do contexto, entao o fio nao fecha o contexto,
    mata o Chromium que abriu (so os processos dele, pelo PID e pela identidade) e varre e apaga o perfil;
  - o Chromium que nao abriu (caiu, ou o driver morreu, antes do controle positivo; revisao 2 do aberto): o pedido sai
    pelo caminho frio, o fio fecha o que abriu e sai, e a medida seguinte tenta abrir de novo num fio novo. A abertura
    boa zera a conta; chromium.aberto_falhas_abertura_max aberturas seguidas que falham desligam o aberto ate a tela
    fechar. O servidor da pagina do controle nasce com INTERVALO_SERVIDOR_S, como o da pagina de medida: o parar()
    dele nao espera o meio segundo do serve_forever a cada abertura;
  - o Chromium que travou (passou do teto): o pedido sai pelo caminho frio e o fio fica de lado. Enquanto ele nao
    volta, as medidas vao pelo caminho frio sem abrir outro; quando volta, fecha o Chromium e apaga o perfil, e a
    proxima medida abre um fio novo;
  - fechar() (o fecho da tela) para o fio, espera no maximo tela.parar_max_s e devolve o relatorio. O fio que nao parou
    deixa o perfil para a varredura de orfas; o Chromium dele morre com o processo. O segundo fechar() so devolve o
    relatorio, sem esperar de novo.
O relatorio: {aberturas, falhas_abertura, medidas, quedas, travadas, recusas, presos, varreduras, varreduras_limpas,
copias, ilegiveis, controle, fontes_servidas, perfis_apagados, perfis_que_ficaram, desligado, limpo}. desligado diz que
o aberto ficou desligado ate a tela fechar (sem a amarra, ou no teto de aberturas que falham). limpo exige zero copia,
zero arquivo ilegivel, o controle positivo achado em todo fecho em ordem, nenhum perfil que ficou e nenhum fio preso.
"""
import hashlib
import os
import queue
import threading
import time

from desdobra import limites
from desdobra.chromium import apontar_playwright, navegador, processos, servidor

NOME_FIO = 'dsd-aberto'
PASTA_ARTEFATOS = 'artefatos'  # a pasta de artefatos do Playwright, dentro do perfil
INTERVALO_SERVIDOR_S = 0.01  # numero-neutro: intervalo de consulta do servidor da pagina do controle (o parar espera)
PAGINA_CONTROLE = ('<!doctype html><html><head><title>controle</title><link rel="stylesheet" href="/controle">'
                   '</head><body></body></html>')
CONTAGENS = ('aberturas', 'falhas_abertura', 'medidas', 'quedas', 'travadas', 'recusas', 'varreduras', 'varreduras_limpas', 'copias',
             'ilegiveis', 'sem_controle', 'fontes_servidas', 'perfis_apagados', 'perfis_que_ficaram')


def _driver(pw):
    """(pid, identidade) do driver do Playwright de pw, ou None. O Playwright nao da o processo do driver pela API
    publica: o caminho e o da versao fixada (o doctor confere a versao, e o teste do driver morto confere o caminho)."""
    try:
        pid = int(pw._impl_obj._connection._transport._proc.pid)
    except (AttributeError, TypeError, ValueError):
        return None
    inicio = processos.identidade(pid)
    return (pid, inicio) if inicio is not None else None


def _varrer(perfil, servidos, marcador):
    """A varredura do perfil com o Chromium fechado, de novo enquanto algum arquivo ainda nao se le (como a da janela,
    desdobra.tela.processo.varrer_fechado)."""
    tentativas = int(limites.valor('chromium.apagar_perfil_tentativas'))
    for n in range(tentativas):
        r = navegador.varrer_perfil(perfil, servidos, marcador)
        if not r['arquivos_ilegiveis']:
            break
        if n + 1 < tentativas:
            time.sleep(float(limites.valor('chromium.apagar_perfil_intervalo_s')))
    return r


class _Pedido:
    def __init__(self, funcao):
        self.funcao = funcao  # funcao(fio) -> resposta, rodada no fio do aberto
        self.feito = threading.Event()
        self.resposta = None
        self.erro = None


class _Fio(threading.Thread):
    """O fio dono do Playwright e do Chromium aberto. So ele chama o Playwright."""

    def __init__(self, dono):
        super().__init__(name=NOME_FIO, daemon=True)
        self.dono = dono
        self.fila = queue.Queue()
        self.abandonado = False  # o pedido passou do teto: o fio fecha tudo quando voltar
        self.caiu = False  # o Chromium caiu ou o driver morreu: o fio responde, fecha o que e dele e sai
        self.sair = False
        self.driver = None  # (pid, identidade) do driver do Playwright deste fio
        self.chromium = []  # [(pid, identidade)] dos processos do Chromium deste fio, na abertura
        self.pw = None
        self.ctx = None
        self.perfil = None
        self.versao = None
        self.marcador = None
        self.servidos = {}  # {sha256: bytes} servidos ao Chromium deste perfil, para a varredura do fecho

    def run(self):
        try:
            while not (self.abandonado or self.sair or self.caiu):
                pedido = self.fila.get()
                if pedido is None:
                    break
                try:
                    pedido.resposta = pedido.funcao(self)
                except BaseException as e:  # noqa: BLE001 - quem pediu decide; o fio continua
                    pedido.erro = e
                finally:
                    pedido.feito.set()
        finally:
            # fecho em ordem (pedido None) exige o controle positivo; trava e queda ja contaram a falha
            self._fechar_navegador(exigir_controle=not (self.abandonado or self.caiu))
            self._parar_playwright()

    # -------------------------------------------------------------- abrir e fechar
    def _abrir(self):
        if not self.dono.amarrar():
            self.dono._contar('recusas')
            self.dono._desligar()
            self.sair = True
            raise navegador.ErroNavegador('O sistema não amarrou o Chromium aberto da tela a este processo.')
        apontar_playwright()
        tempo_ms = float(limites.valor('chromium.tempo_max_s')) * 1000  # numero-neutro: segundos para milissegundos
        try:
            from playwright.sync_api import sync_playwright
            if self.pw is None:
                self.pw = sync_playwright().start()
                self.driver = _driver(self.pw)
            self.perfil = navegador.perfil_tela(self.dono.pasta_temp)
            self.ctx = self.pw.chromium.launch_persistent_context(str(self.perfil), headless=True,
                                                                  args=list(navegador.ARGUMENTOS),
                                                                  viewport=dict(navegador.JANELA_MEDIDA),
                                                                  device_scale_factor=1, timeout=tempo_ms,
                                                                  accept_downloads=False,
                                                                  artifacts_dir=str(self.perfil / PASTA_ARTEFATOS))
            if self.driver is not None:
                self.chromium = [(p, processos.identidade(p)) for p, _nome in processos.descendentes(self.driver[0])]
            self.ctx.set_default_timeout(tempo_ms)
            if self.ctx.browser is None:
                raise navegador.ErroNavegador('O Chromium aberto não deu o navegador do contexto.')
            self.versao = self.ctx.browser.version
            # o controle positivo no contexto persistente: prova, na varredura do fecho, que o perfil grava cache
            with servidor.ServidorFontes(PAGINA_CONTROLE, {}, intervalo_s=INTERVALO_SERVIDOR_S) as srv:
                pg = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
                pg.goto(srv.url_entrada, wait_until='load')
                self.marcador = srv.marcador_controle
        except Exception:  # noqa: BLE001 - a medida sai pelo caminho frio; a seguinte tenta abrir num fio novo
            self._fechar_navegador(exigir_controle=False)
            self._parar_playwright()
            self.sair = True
            self.dono._falhou_abertura()
            raise navegador.ErroNavegador('O Chromium aberto da tela não abriu.') from None
        self.dono._abriu()

    def driver_vivo(self):
        """O driver do Playwright deste fio ainda roda (sem o processo conhecido, conta como vivo)."""
        d = self.driver
        return d is None or processos.vivo(d[0], d[1])

    def _matar_chromium(self):
        """Mata o Chromium deste fio (o driver morreu, e o Playwright nao fecha mais nada): so os processos que ele
        abriu, pelo PID e pela identidade, e os filhos deles. Espera no maximo chromium.tempo_max_s eles sairem."""
        import signal
        vivos = [p for p, i in self.chromium if i is not None and processos.vivo(p, i)]
        alvos = set(vivos) | {f for p in vivos for f, _nome in processos.descendentes(p)}
        for p in alvos:
            try:
                os.kill(p, signal.SIGTERM)  # no Windows e TerminateProcess
            except OSError:
                pass
        fim = time.monotonic() + float(limites.valor('chromium.tempo_max_s'))
        while any(processos.identidade(p) is not None for p in alvos) and time.monotonic() < fim:
            time.sleep(float(limites.valor('chromium.apagar_perfil_intervalo_s')))

    def _fechar_navegador(self, exigir_controle):
        """Fecha o Chromium, varre o perfil inteiro (quando alguma fonte foi servida a ele) e apaga o perfil."""
        ctx, perfil, servidos, marcador = self.ctx, self.perfil, list(self.servidos.values()), self.marcador
        self.ctx, self.perfil, self.servidos, self.marcador = None, None, {}, None
        if ctx is not None:
            if self.driver_vivo():
                try:
                    ctx.close()
                except Exception:  # noqa: BLE001 - o Chromium ja pode ter caido; o que importa e a varredura e a pasta
                    pass
            else:
                # com o driver morto, ctx.close() espera para sempre o aviso de fecho que nao vem
                self._matar_chromium()
        if perfil is None:
            return
        r = _varrer(perfil, servidos, marcador) if servidos else None
        apagado = navegador.apagar_perfil(perfil)
        self.dono._registrar_fecho(r, len(servidos), apagado, exigir_controle)

    def _parar_playwright(self):
        pw, self.pw = self.pw, None
        if pw is not None:
            try:
                pw.stop()
            except Exception:  # noqa: BLE001 - o driver ja pode ter saido
                pass

    # -------------------------------------------------------------- medir
    def medir(self, url_entrada, familias, ids_cdp, servidos):
        if self.ctx is None:
            self._abrir()
        for d in servidos:
            self.servidos[hashlib.sha256(d).hexdigest()] = d
        tempo_ms = float(limites.valor('chromium.tempo_max_s')) * 1000  # numero-neutro: segundos para milissegundos
        try:
            # o contexto sem perfil: o cache dele fica na memoria e some com ele
            c = self.ctx.browser.new_context(viewport=dict(navegador.JANELA_MEDIDA), device_scale_factor=1,
                                             accept_downloads=False)
            try:
                c.set_default_timeout(tempo_ms)
                medida = navegador.medir_na_pagina(c, c.new_page(), url_entrada, familias, ids_cdp)
            finally:
                if self.driver_vivo():  # com o driver morto no meio da medida, close() espera para sempre
                    c.close()
        except Exception:  # noqa: BLE001 - Chromium que caiu ou nao respondeu: o fio fecha tudo depois de responder
            self.dono._contar('quedas')
            self.caiu = True
            raise navegador.ErroNavegador('O Chromium aberto da tela não mediu.') from None
        self.dono._contar('medidas')
        return {'chromium': self.versao, 'playwright': navegador.versao_playwright(), **medida}


class NavegadorAberto:
    """O Chromium fixado aberto da tela. Uso (so o processo da tela; desdobra.tela.processo):

        aberto = NavegadorAberto()
        medida_quebras.usar_aberto(aberto)
        ...                                   # as medidas sem cache passam por aberto.conferir
        medida_quebras.usar_aberto(None)
        relatorio = aberto.fechar()

    amarrar(): a amarra do Job Object (padrao processos.amarrar_ao_processo); os testes no proprio pytest passam outra.
    pasta_temp: onde nasce o perfil dsd-tela- (padrao a pasta temporaria do sistema). espera_s: o teto de cada pedido
    (padrao chromium.aberto_espera_max_s)."""

    def __init__(self, amarrar=None, pasta_temp=None, espera_s=None):
        from desdobra.chromium import processos
        self.amarrar = amarrar if amarrar is not None else processos.amarrar_ao_processo
        self.pasta_temp = pasta_temp
        self.espera_s = float(espera_s if espera_s is not None else limites.valor('chromium.aberto_espera_max_s'))
        self._trava = threading.Lock()  # o estado e as contagens
        self._trava_pedido = threading.Lock()  # um pedido de cada vez no fio
        self._fio = None
        self._presos = []
        self._fechando = []  # os fios que cairam e ainda fecham o que e deles (nao seguram o fio novo)
        self._fechado = False
        self._desligado = False
        self._falhas_seguidas = 0  # aberturas seguidas que falharam (a boa zera)
        self._contagem = {k: 0 for k in CONTAGENS}

    @property
    def perfil(self):
        """O perfil do Chromium aberto agora, ou None."""
        fio = self._fio
        return fio.perfil if fio is not None else None

    def conferir(self, url_entrada, familias, ids_cdp, servidos=()):
        """A medida de navegador.conferir no Chromium aberto (sem o perfil: ele e do aberto). servidos: os bytes das
        fontes que a pagina pede, para a varredura do perfil no fecho. Levanta navegador.ErroNavegador quando o aberto
        nao mediu (fechado, desligado, sem amarra, caiu, travou ou ocupado alem do teto): quem chama mede pelo caminho
        frio."""
        servidos = [bytes(d) for d in servidos]
        return self._pedir(lambda fio: fio.medir(url_entrada, list(familias), list(ids_cdp), servidos))

    def _no_fio(self, funcao):
        """Roda funcao(fio) no fio do aberto, com o Chromium ja aberto (os testes)."""
        return self._pedir(funcao)

    def _pedir(self, funcao):
        inicio = time.monotonic()
        if not self._trava_pedido.acquire(timeout=self.espera_s):
            raise navegador.ErroNavegador('O Chromium aberto da tela está ocupado.')
        try:
            with self._trava:
                if self._fechado or self._desligado:
                    raise navegador.ErroNavegador('O Chromium aberto da tela está fechado.')
                self._presos = [f for f in self._presos if f.is_alive()]
                if self._presos:
                    raise navegador.ErroNavegador('O Chromium aberto da tela ainda não voltou da trava.')
                self._fechando = [f for f in self._fechando if f.is_alive()]
                velho = self._fio
                if velho is not None and velho.is_alive() and (velho.caiu or not velho.driver_vivo()):
                    # o fio que caiu fecha o que e dele sozinho; o driver morto com o fio parado conta como queda
                    if not velho.caiu:
                        velho.caiu = True
                        self._contagem['quedas'] += 1
                        velho.fila.put(None)
                    self._fechando.append(velho)
                    self._fio = None
                if self._fio is None or not self._fio.is_alive() or self._fio.sair:
                    # o fio que nao abriu (sair) ainda pode estar saindo: o pedido nunca vai a fila dele
                    self._fio = _Fio(self)
                    self._fio.start()
                fio = self._fio
            pedido = _Pedido(funcao)
            fio.fila.put(pedido)
            if not pedido.feito.wait(max(0.0, self.espera_s - (time.monotonic() - inicio))):
                with self._trava:
                    fio.abandonado = True
                    self._contagem['travadas'] += 1
                    if self._fio is fio:
                        self._fio = None
                    self._presos.append(fio)
                fio.fila.put(None)  # o fio que ja voltou para a fila sai por aqui
                raise navegador.ErroNavegador('O Chromium aberto da tela não respondeu a tempo.')
            if pedido.erro is not None:
                if isinstance(pedido.erro, navegador.ErroNavegador):
                    raise pedido.erro
                raise navegador.ErroNavegador('O Chromium aberto da tela não respondeu.') from None
            return pedido.resposta
        finally:
            self._trava_pedido.release()

    def fechar(self):
        """Para o fio (e os presos e os que fecham), espera no maximo tela.parar_max_s e devolve o relatorio. O
        segundo fechar() so devolve o relatorio."""
        with self._trava:
            segundo = self._fechado
            self._fechado = True
            fios = ([self._fio] if self._fio is not None else []) + list(self._presos) + list(self._fechando)
            self._fio, self._fechando = None, []
        if segundo:
            return self.relatorio()
        fim = time.monotonic() + float(limites.valor('tela.parar_max_s'))
        for f in fios:
            f.fila.put(None)
        for f in fios:
            f.join(max(0.0, fim - time.monotonic()))
        with self._trava:
            self._presos = [f for f in fios if f.is_alive()]
        return self.relatorio()

    # -------------------------------------------------------------- contagens (chamadas pelo fio)
    def _contar(self, chave, n=1):
        with self._trava:
            self._contagem[chave] += n

    def _desligar(self):
        with self._trava:
            self._desligado = True

    def _abriu(self):
        with self._trava:
            self._contagem['aberturas'] += 1
            self._falhas_seguidas = 0

    def _falhou_abertura(self):
        """A abertura que falhou: a proxima medida tenta de novo, ate o teto de falhas seguidas, que desliga o aberto."""
        teto = int(limites.valor('chromium.aberto_falhas_abertura_max'))
        with self._trava:
            self._contagem['falhas_abertura'] += 1
            self._falhas_seguidas += 1
            if self._falhas_seguidas >= teto:
                self._desligado = True

    def _registrar_fecho(self, varredura, fontes, apagado, exigir_controle):
        with self._trava:
            c = self._contagem
            c['perfis_apagados' if apagado else 'perfis_que_ficaram'] += 1
            if varredura is None:
                return
            c['varreduras'] += 1
            c['fontes_servidas'] += fontes
            c['copias'] += varredura['copias_encontradas'] + varredura['pdfs_encontrados']
            c['ilegiveis'] += varredura['arquivos_ilegiveis']
            c['varreduras_limpas'] += int(navegador.varredura_limpa(varredura))
            if exigir_controle and not varredura['controle_encontrado']:
                c['sem_controle'] += 1

    def relatorio(self):
        with self._trava:
            presos = sum(1 for f in self._presos if f.is_alive())
            r = {k: v for k, v in self._contagem.items() if k != 'sem_controle'}
            r['presos'] = presos
            r['controle'] = not self._contagem['sem_controle']
            r['desligado'] = self._desligado
            r['limpo'] = (not r['copias'] and not r['ilegiveis'] and r['controle'] and not r['perfis_que_ficaram']
                          and not presos)
        return r
