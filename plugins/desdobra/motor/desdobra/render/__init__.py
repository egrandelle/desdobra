# -*- coding: utf-8 -*-
"""desdobra render: renderiza a origem do job (M4, arquitetura-v1.md, 4.11 e 9.5).

    desdobra render --job <pasta> [--formato origem]
    desdobra linkado confirmar --job <pasta>

Render protegido (decisoes-v1.md, arquitetura n. 2): o render so parte de uma pessoa, pela tela (clique do DA, no M7)
ou pela CLI com confirmacao num terminal interativo. Quem confere e desdobra.humano: sem console interativo (modo
envelope, entrada ou saida redirecionada, NUL, console sem janela, processo aberto pelo Claude), o comando recusa com
codigo diferente de zero. Nao ha parametro que pule a conferencia: o render e a confirmacao de linkado so gravam com
o Disparo que a propria conferencia emite. Depois:
  - pergunta ao DA, sem resposta padrao (Enter vazio repete), se renderiza; quando o contrato pede decisao do DA
    (divergencia de largura, efeito sobre texto que o render nao aplica, clipping dividido por texto), pergunta
    tambem, e o aceite vai para o render.json;
  - as perguntas rodam sem a trava do job; o render pega a trava e monta o contrato de novo, e so segue se as
    decisoes pedidas continuam as que o DA aceitou;
  - registra quem disparou (usuario do sistema e maquina), o meio e quando.

"desdobra linkado confirmar" e a confirmacao do DA do arquivo de cada smart object linkado (arquitetura-v1.md, 7.2),
com a mesma conferencia, e grava briefing/linkados-confirmados.json com a trava do job.
"""
from pathlib import Path

from desdobra.resultado import Codigo, Resultado

O_QUE_FAZER_OK = ('O master está em render/origem/master.png e o registro em render/origem/render.json. Confira o '
                  'master antes de seguir.')
CANCELAR = ('n', 'nao', 'não', 'sair')
SIM = ('sim',)


def registrar(subparsers):
    p = subparsers.add_parser('render', help='Renderiza a origem do job (só no terminal interativo, com confirmação)')
    p.add_argument('--job', required=True, help='Pasta do job')
    p.add_argument('--formato', default='origem', choices=('origem',),
                   help='Formato a renderizar (no M4, só a origem)')
    p.set_defaults(executar=_render, nome_comando='render')

    lk = subparsers.add_parser('linkado', help='Confirmação do DA do arquivo de cada smart object linkado')
    sub = lk.add_subparsers(dest='acao_linkado', metavar='ACAO', required=True)
    c = sub.add_parser('confirmar', help='Confirma, no terminal interativo, o arquivo casado de cada linkado')
    c.add_argument('--job', required=True, help='Pasta do job')
    c.set_defaults(executar=_linkado_confirmar, nome_comando='linkado confirmar')


def perguntar(pergunta):
    """Pergunta sem resposta padrao, pelo console: Enter vazio repete. True para 'sim', False para cancelar."""
    from desdobra import humano
    while True:
        try:
            r = humano.ler(pergunta).strip().casefold()
        except (EOFError, KeyboardInterrupt):
            return False
        if r in SIM:
            return True
        if r in CANCELAR:
            return False
        print('Responda "sim" para seguir ou "nao" para cancelar.')


def _recusa_terminal(comando, pasta, motivo):
    from desdobra import humano
    return Resultado(comando=comando, codigo=int(Codigo.RECUSADO), situacao='recusado',
                     o_que_fazer=humano.O_QUE_FAZER, pasta_job=pasta, contagens={'recusa_%s' % motivo: 1},
                     linhas_humanas=['%s só roda num terminal interativo, com a confirmação do DA.' % comando])


def _render(args):
    from desdobra import humano
    from desdobra.job import nucleo
    from desdobra.render import contrato as mod_contrato
    from desdobra.render import execucao
    pasta = Path(args.job).resolve()
    try:
        disparo = humano.exigir('render')
    except humano.ErroHumano as e:
        return _recusa_terminal('render', pasta, str(e))
    if not (pasta / 'estado.json').is_file():
        return Resultado(comando='render', codigo=int(Codigo.USO), situacao='erro', pasta_job=pasta,
                         o_que_fazer='Rode o render numa pasta de job ("desdobra job criar").',
                         linhas_humanas=['A pasta não é um job do desdobra.'])
    try:
        _contrato, bloqueios, confirmar = mod_contrato.montar(pasta)
        if bloqueios:
            return _parou(execucao.ErroRender('O render tem bloqueio.', 'bloqueio', medidas={'bloqueios': bloqueios},
                                              o_que_fazer=' '.join(dict.fromkeys(b['descricao'] for b in bloqueios))),
                          pasta)
        if not perguntar('Renderizar o formato %s deste job? Digite sim para renderizar: ' % args.formato):
            return Resultado(comando='render', codigo=int(Codigo.RECUSADO), situacao='recusado', pasta_job=pasta,
                             o_que_fazer='O DA cancelou o render. Nada foi gravado.',
                             linhas_humanas=['Render cancelado.'])
        aceites = []
        for c in confirmar:
            print(c['descricao'])
            for item in c['medidas'].get('camadas') or []:
                print('  camada %s: %s' % (item.get('layer_id'), ', '.join('%s %s' % kv for kv in item.items()
                                                                          if kv[0] != 'layer_id')))
            if not perguntar('Aceita renderizar assim? Digite sim para aceitar: '):
                return Resultado(comando='render', codigo=int(Codigo.RECUSADO), situacao='recusado',
                                 pasta_job=pasta, o_que_fazer='O DA não aceitou. Nada foi gravado.',
                                 linhas_humanas=['Render cancelado.'])
            aceites.append(c['codigo'])
        with nucleo.Trava(pasta):
            rel = execucao.renderizar(pasta, disparo=disparo, aceites=aceites)
    except execucao.ErroRender as e:
        return _parou(e, pasta)
    except nucleo.ErroJob as e:
        return Resultado(comando='render', codigo=int(e.codigo), situacao=e.situacao, o_que_fazer=e.o_que_fazer,
                         pasta_job=pasta, linhas_humanas=[str(e)])
    nucleo.registrar_evento(pasta, 'render_concluido', formato=rel['formato']['chave'], tempo_s=rel['tempo_s'],
                            n_textos=rel['textos']['camadas'], n_paginas_pdf=rel['textos']['paginas_pdf'])
    cont = {'textos': rel['textos']['camadas'], 'sharp_pequeno': rel['textos']['sharp_pequeno'],
            'paginas_pdf': rel['textos']['paginas_pdf'], 'cdp_trechos': rel['cdp']['trechos'],
            'cdp_confere': rel['cdp']['confere'], 'assets': len(rel['assets']), 'registros': len(rel['registros']),
            'copias_no_cache': rel['cache']['copias_encontradas'] or 0,
            'fontes_fora_da_entrada': rel['varredura']['arquivos_de_fonte_fora_da_entrada'],
            'pdfs_no_job': rel['varredura']['pdfs_no_job']}
    return Resultado(comando='render', situacao='ok', fase='render', o_que_fazer=O_QUE_FAZER_OK, contagens=cont,
                     ids={'master_sha256': rel['master']['sha256']}, numeros={'tempo_s': rel['tempo_s']},
                     pasta_job=pasta,
                     linhas_humanas=['Master gravado em render/%s/master.png (%d x %d).' % (
                         rel['formato']['chave'], rel['master']['largura'], rel['master']['altura']),
                         'CDP: face do arquivo do job em %d de %d trechos.' % (rel['cdp']['confere'],
                                                                               rel['cdp']['trechos'])])


def _parou(e, pasta):
    from desdobra.job import nucleo
    if (pasta / 'estado.json').is_file():
        nucleo.registrar_evento(pasta, 'render_parou', motivo=e.motivo, codigo=int(e.codigo))
    situacao = 'bloqueado' if e.motivo in ('bloqueio', 'pede_decisao_do_da') else 'erro'
    return Resultado(comando='render', codigo=int(e.codigo), situacao=situacao, fase='render',
                     o_que_fazer=e.o_que_fazer or 'O render parou: %s.' % e.motivo, pasta_job=pasta,
                     contagens={'bloqueios': len(e.medidas.get('bloqueios') or [])}, linhas_humanas=[str(e)])


def _linkado_confirmar(args):
    from desdobra import humano
    from desdobra.render import linkados
    pasta = Path(args.job).resolve()
    try:
        disparo = humano.exigir('linkado confirmar')
    except humano.ErroHumano as e:
        return _recusa_terminal('linkado confirmar', pasta, str(e))
    try:
        dados, n_novos = linkados.sessao(pasta, disparo=disparo)
    except linkados.ErroLinkado as e:
        return Resultado(comando='linkado confirmar', codigo=int(Codigo.USO), situacao='erro', pasta_job=pasta,
                         o_que_fazer=str(e), linhas_humanas=[str(e)])
    return Resultado(comando='linkado confirmar', situacao='ok', pasta_job=pasta,
                     contagens={'linkados_confirmados': len(dados['linkados']), 'novos': n_novos},
                     o_que_fazer='Os linkados confirmados estão em briefing/linkados-confirmados.json.',
                     linhas_humanas=['%d linkado(s) confirmado(s).' % len(dados['linkados'])])
