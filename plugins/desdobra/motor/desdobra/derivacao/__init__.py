# -*- coding: utf-8 -*-
"""desdobra derivar: derivacao deterministica por familia (M5, arquitetura-v1.md, 4.10 e 9.6).

    desdobra derivar --job <pasta> [--formato <id>]...

Le o briefing gravado (briefing/briefing-confirmado.json, do DA ou fixture de teste), sem tela, e grava
derivacao/<formato>.json de cada formato do briefing e derivacao/devolucoes.json. Recusa sem briefing, com briefing
desatualizado (o cabecalho nao bate com o laudo, as specs, o design system ou a conferencia de fontes), com briefing
que tem pendente obrigatorio e com fases do job desatualizadas. Nao renderiza: o render de cada formato derivado e do
DA ("desdobra render --job <pasta> --formato <id>", num terminal interativo).
"""
from pathlib import Path

from desdobra.resultado import Codigo, Resultado

O_QUE_FAZER_OK = ('As derivações estão em derivacao/<formato>.json e os formatos devolvidos ao DA, com o motivo, em '
                  'derivacao/devolucoes.json. O render de cada formato derivado é um clique do DA na tela do '
                  'desdobra. Peça ao Claude para abrir a tela do job (/desdobra:continuar).')
O_QUE_FAZER_ERRO = {
    'sem_briefing': 'O job não tem briefing. O briefing confirmado sai da tela, no "Salvar e seguir" do DA (nos testes, '
                    'do briefing de teste importado).',
    'briefing_desatualizado': 'O briefing é de outra versão do laudo, das specs, do design system ou das fontes. '
                              'Confirme o briefing de novo (ou importe o de teste de novo).',
    'briefing_com_problema': 'O briefing tem decisão pendente ou incompleta. As contagens das funções mostram o que '
                             'falta; o DA corrige o briefing na tela.',
    'briefing_invalido': 'O briefing não segue o contrato briefing/1.',
    'briefing_rascunho': 'O briefing gravado é um rascunho, sem as decisões do DA. O briefing confirmado sai da tela, '
                         'no "Salvar e seguir" do DA (nos testes, do briefing de teste importado).',
    'fases_desatualizadas': 'Uma fase do job está desatualizada. Peça ao Claude para seguir o job '
                            '(/desdobra:continuar).',
    'entrada_alterada_fora_do_motor': 'Uma entrada congelada do job mudou fora do motor.',
    'formato_desconhecido': 'O formato pedido não está no briefing.',
}


def registrar(subparsers):
    p = subparsers.add_parser('derivar', help='Deriva os formatos do briefing por família (sem tela, sem render)')
    p.add_argument('--job', required=True, help='Pasta do job')
    p.add_argument('--formato', action='append', default=None, help='Só este formato (id do briefing); repetível')
    p.set_defaults(executar=_derivar, nome_comando='derivar')


def _derivar(args):
    from desdobra.derivacao import nucleo as nd
    from desdobra.job import nucleo
    pasta = Path(args.job).resolve()
    if not (pasta / 'estado.json').is_file():
        return Resultado(comando='derivar', codigo=int(Codigo.USO), situacao='erro', pasta_job=pasta,
                         o_que_fazer='O derivar só funciona numa pasta de job.', linhas_humanas=['A pasta não é um job.'])
    try:
        with nucleo.Trava(pasta):
            r = nd.derivar(pasta, so=args.formato)
    except nd.ErroDerivacao as e:
        nucleo.registrar_evento(pasta, 'derivar_recusou', motivo=e.motivo)
        return Resultado(comando='derivar', codigo=int(Codigo.RECUSADO), situacao='recusado', fase='derivar',
                         pasta_job=pasta, o_que_fazer=O_QUE_FAZER_ERRO.get(e.motivo, str(e)),
                         contagens={'recusa_%s' % e.motivo: 1}, linhas_humanas=[str(e)])
    except nucleo.ErroJob as e:
        return Resultado(comando='derivar', codigo=int(e.codigo), situacao=e.situacao, o_que_fazer=e.o_que_fazer,
                         pasta_job=pasta, linhas_humanas=[str(e)])
    cont = {'formatos': len(r['formatos']), 'derivados': 0, 'devolvidos': len(r['devolucoes']),
            'elementos_da_mestre': len(r['inventario']['mestre']),
            'inventario_igual': int(r['inventario']['iguais_entre_formatos'])}
    for d in r['formatos'].values():
        cont['caminho_%s' % d['caminho']] = cont.get('caminho_%s' % d['caminho'], 0) + 1
        if d['situacao'] == 'derivado':
            cont['derivados'] += 1
    for dv in r['devolucoes']:
        cont['motivo_%s' % dv['motivo']] = cont.get('motivo_%s' % dv['motivo'], 0) + 1
    nucleo.registrar_evento(pasta, 'derivar_concluido', **{k: v for k, v in cont.items()})
    linhas = ['%s: %s (%s)%s' % (k, d['situacao'], d['caminho'],
                                 (', ' + d['devolucao']['motivo']) if d['devolucao'] else '')
              for k, d in sorted(r['formatos'].items())]
    return Resultado(comando='derivar', situacao='ok' if not r['devolucoes'] else 'ok_com_bloqueio', fase='derivar',
                     pasta_job=pasta, o_que_fazer=O_QUE_FAZER_OK, contagens=cont, linhas_humanas=linhas)
