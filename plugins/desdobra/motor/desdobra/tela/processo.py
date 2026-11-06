# -*- coding: utf-8 -*-
"""Processo de fundo da tela (M7a2; M7a, fatia 1): servidor da tela e Chromium com janela, ate o DA fechar a janela.

    python -I -B -m desdobra.tela.processo --job <pasta>

Quem chama e o "desdobra tela abrir" (desdobra.tela), solto do terminal. A linha de comando nao leva segredo: o token
da entrada e a sessao do cookie nascem aqui (desdobra.tela.servidor) e vao so ao Chromium, por page.goto
(navegador.Janela.ir). Este processo:
  1. apaga as pastas dsd-tela- orfas (navegador.varrer_orfaos);
  2. monta o conteudo do job (desdobra.tela.estado.montar), com a trava do job so durante a montagem; erro fora do
     previsto vira "recusado erro_interno", com o evento tela_recusou;
  3. sobe o servidor, com a escrita do rascunho e dos atos do passo 1 (desdobra.tela.atos) so quando este processo
     pode abrir a sessao humana da tela (opcoes_do_servidor: sem o modo envelope e sem as marcas do Claude, que o ambiente do fundo ja tira; com elas o
     servidor fica so de leitura, e o evento tela_aberta diz escrita false), cria o perfil dsd-tela- e abre a janela
     (toda recusa daqui em diante apaga o perfil): a entrada
     de uso unico (resposta 204, que nao entra no historico do perfil) e depois a pagina, ja com o cookie (entrar);
  4. avisa quem chamou por uma linha fixa na saida padrao ("pronto" ou "recusado <motivo>") e fecha a saida padrao:
     depois disso nada e escrito nela;
  5. espera a janela fechar; com o Chromium fechado e antes de apagar o perfil, varre o perfil inteiro (copia de
     fonte, controle positivo, token, sessao e CSRF em qualquer arquivo; varrer_fechado); para o servidor, apaga o perfil e
     registra os eventos tela_aberta e tela_fechada em log/eventos.jsonl, so com codigos e contagens.
"""
import argparse
import os
import sys
from pathlib import Path

from desdobra.resultado import Codigo

PRONTO = 'pronto'
RECUSADO = 'recusado'


def _avisar(linha):
    """A unica escrita na saida padrao: uma linha, e a saida e trocada pelo nulo (o pipe de quem chamou fecha)."""
    try:
        sys.stdout.write(linha + '\n')
        sys.stdout.flush()
    except (OSError, ValueError, AttributeError):
        pass
    try:
        nulo = os.open(os.devnull, os.O_WRONLY)
        os.dup2(nulo, 1)
        os.close(nulo)
        sys.stdout = open(os.devnull, 'w', encoding='utf-8')
    except OSError:
        pass


def executar(pasta, avisar=_avisar, ao_abrir=None, teto=None):
    """Roda a tela do job ate a janela fechar. ao_abrir(janela, servidor): so para os testes (a janela ja aberta).
    teto: o teto do modo de dados que o tela abrir recebeu (a tela nunca oferece modo acima dele nem do estado.json).
    Devolve o codigo de saida do processo."""
    from desdobra.chromium import navegador
    from desdobra.job import nucleo
    from desdobra.tela import atos, estado, servidor
    pasta = Path(pasta).resolve()
    try:
        orfaos = navegador.varrer_orfaos()
        conteudo = estado.montar(pasta, teto=teto) if teto else estado.montar(pasta)
    except estado.ErroTela as e:
        _registrar_recusa(pasta, motivo=e.motivo)
        avisar('%s %s' % (RECUSADO, e.motivo))
        return int(Codigo.RECUSADO)
    except Exception as e:  # noqa: BLE001 - JSON corrompido e afins: erro interno com evento, nunca silencio
        _registrar_recusa(pasta, motivo='erro_interno', excecao=type(e).__name__)
        avisar('%s erro_interno' % RECUSADO)
        return int(Codigo.ERRO_INTERNO)
    avisado = False
    perfil = janela = None
    varredura = {}
    try:
        # o servidor sobe antes do perfil existir: a recusa do servidor (id fora do padrao) nao deixa pasta
        opcoes = opcoes_do_servidor(pasta)
        if opcoes:
            # os botoes do passo 1 (modo de dados, linkados e valores de spec), so no servidor que grava
            opcoes['atos'] = atos.atos_do_job(pasta, teto=teto, conteudo=conteudo)
        with servidor.ServidorTela(conteudo, **opcoes) as srv:
            def conferir_perfil(p):
                varredura.update(varrer_fechado(p, srv))

            perfil = navegador.perfil_tela()
            janela = navegador.Janela(perfil, antes_de_apagar=conferir_perfil)
            with janela:
                entrar(janela, srv)
                nucleo.registrar_evento(pasta, 'tela_aberta', chromium=janela.versao,
                                        orfaos_removidos=orfaos['removidas'], orfaos_que_ficaram=orfaos['nao_removidas'],
                                        formatos=len(conteudo['previas']), fontes=len(conteudo['fontes']),
                                        escrita=srv.escreve)
                avisar(PRONTO)
                avisado = True
                if ao_abrir is not None:
                    ao_abrir(janela, srv)
                janela.esperar_fechar()
            contagem = dict(srv.contagem)
    except navegador.ErroNavegador:
        _registrar_recusa(pasta, motivo='chromium_nao_abriu', perfil_apagado=_perfil_apagado(perfil, janela))
        if not avisado:
            avisar('%s chromium_nao_abriu' % RECUSADO)
        return int(Codigo.RECUSADO)
    except Exception as e:  # noqa: BLE001 - nada de traceback: so o nome da excecao, no log do job
        _registrar_recusa(pasta, motivo='erro_interno', excecao=type(e).__name__,
                          perfil_apagado=_perfil_apagado(perfil, janela))
        if not avisado:
            avisar('%s erro_interno' % RECUSADO)
        return int(Codigo.ERRO_INTERNO)
    campos = {'pedidos_%s' % k: v for k, v in sorted(contagem.items())}
    campos.update({'varredura_%s' % k: v for k, v in sorted(varredura.items())})
    nucleo.registrar_evento(pasta, 'tela_fechada', perfil_apagado=janela.perfil_apagado, **campos)
    return 0 if janela.perfil_apagado and varredura.get('limpa') else int(Codigo.ERRO_INTERNO)


def opcoes_do_servidor(pasta):
    """{'pasta': pasta} quando o servidor pode gravar (o processo abre a sessao humana da tela e o job tem laudo); {}
    para o servidor so de leitura."""
    from desdobra import humano
    from desdobra.tela import rascunho
    ok, _motivo = humano.ambiente_da_tela()
    if not ok or rascunho.laudo_sha256(pasta) is None:
        return {}
    return {'pasta': pasta}


def _perfil_apagado(perfil, janela):
    """Confirma que o perfil sumiu depois de uma recusa: o da Janela quando ela ja apagou, senao apaga aqui. None quando
    o perfil nem chegou a existir."""
    from desdobra.chromium import navegador
    if janela is not None and janela.perfil_apagado is not None:
        return janela.perfil_apagado
    return None if perfil is None else navegador.apagar_perfil(perfil)


def _registrar_recusa(pasta, **campos):
    """Evento tela_recusou no log do job, so quando a pasta e um job (codigos e nomes de excecao, sem texto)."""
    from desdobra.job import nucleo
    try:
        if (pasta / nucleo.ARQUIVO_ESTADO).is_file():
            nucleo.registrar_evento(pasta, 'tela_recusou', **campos)
    except OSError:
        pass


def entrar(janela, srv):
    """A entrada de uso unico (204, que nao entra no historico) e depois a pagina da tela, com o cookie."""
    from desdobra.chromium import navegador
    pg = janela.pagina()
    try:
        pg.goto(srv.url_entrada, wait_until='commit')
    except Exception:  # noqa: BLE001 - o 204 nao completa a navegacao; o que vale e a entrada gasta
        pass
    if not srv.entrada_usada:
        raise navegador.ErroNavegador('O Chromium da tela não fez a entrada.')
    pg.goto(srv.url_pagina, wait_until='load')
    return pg


def _segredos_em(perfil, segredos):
    """Arquivos do perfil que guardam o token da entrada ou a sessao do cookie (bytes), e os que nao se leem."""
    achados, ilegiveis = 0, 0
    for p in Path(perfil).rglob('*'):
        if not p.is_file():
            continue
        try:
            dados = p.read_bytes()
        except OSError:
            ilegiveis += 1
            continue
        if any(s in dados for s in segredos):
            achados += 1
    return achados, ilegiveis


def varrer_fechado(perfil, srv):
    """Varredura do perfil inteiro com o Chromium ja fechado e antes de apagar: copia de fonte, controle positivo
    (navegador.varrer_perfil) e o token e a sessao em qualquer arquivo. Tenta de novo enquanto algum arquivo ainda
    esta preso (chromium.apagar_perfil_tentativas e chromium.apagar_perfil_intervalo_s). So contagens."""
    import time

    from desdobra import limites
    from desdobra.chromium import navegador
    servidos = [d for d, _t in srv.fontes.values()]
    segredos = [srv.token.encode('ascii'), srv.sessao.encode('ascii')]
    if srv.csrf:
        segredos.append(srv.csrf.encode('ascii'))
    tentativas = int(limites.valor('chromium.apagar_perfil_tentativas'))
    for n in range(tentativas):
        r = navegador.varrer_perfil(perfil, servidos, srv.marcador_controle)
        achados, ilegiveis = _segredos_em(perfil, segredos)
        if not r['arquivos_ilegiveis'] and not ilegiveis:
            break
        if n + 1 < tentativas:
            time.sleep(float(limites.valor('chromium.apagar_perfil_intervalo_s')))
    return {'copias': r['copias_encontradas'], 'arquivos': r['arquivos_varridos'],
            'ilegiveis': r['arquivos_ilegiveis'], 'controle': bool(r['controle_encontrado']),
            'limpa': navegador.varredura_limpa(r) and not achados, 'segredos': achados}


def principal(argv=None, ao_abrir=None):
    p = argparse.ArgumentParser(prog='desdobra.tela.processo', add_help=False)
    p.add_argument('--job', required=True)
    p.add_argument('--teto', choices=('a', 'b', 'c'), default=None)
    try:
        args = p.parse_args(list(sys.argv[1:] if argv is None else argv))
    except SystemExit:
        _avisar('%s uso' % RECUSADO)
        return int(Codigo.USO)
    return executar(args.job, ao_abrir=ao_abrir, teto=args.teto)


if __name__ == '__main__':
    sys.exit(principal())
