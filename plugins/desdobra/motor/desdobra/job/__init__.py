# -*- coding: utf-8 -*-
"""Subcomandos "desdobra job ...": criar, proxima, estado, trocar-entrada e remover-entrada."""
import argparse
from pathlib import Path

from desdobra.job import nucleo
from desdobra.job.nucleo import ErroJob
from desdobra.resultado import MODOS_DADOS, Codigo, Resultado


def registrar(subparsers):
    p = subparsers.add_parser('job', help='Cria e conduz a pasta do job')
    sub = p.add_subparsers(dest='acao_job', metavar='ACAO', required=True)

    c = sub.add_parser('criar', help='Cria a pasta do job e congela as entradas')
    c.add_argument('pasta', help='Pasta nova (ou vazia) do job')
    c.add_argument('--kv', '--psd', dest='psd', required=True, help='O PSD ou PSB do KV')
    c.add_argument('--modo-dados', required=True, choices=MODOS_DADOS,
                   help='O que o Claude pode ver deste job: a (com miniaturas), b (sem imagens) ou c (sem conteúdo)')
    # SUPPRESS: sem a opcao aqui, vale o --teto-modo-dados global (antes do subcomando)
    c.add_argument('--teto-modo-dados', choices=MODOS_DADOS, default=argparse.SUPPRESS,
                   help='Teto autorizado pela agência (vem da configuração do plugin)')
    c.add_argument('--campanha', default=None, help='Pasta com os outros arquivos da campanha')
    c.add_argument('--specs', default=None, help='Pasta com as folhas de spec')
    c.add_argument('--fontes', nargs='+', action='extend', default=None,
                   help='Arquivos de fonte (OTF, TTF, TTC, WOFF, WOFF2) ou pastas com eles; entram em entrada/fontes/')
    c.add_argument('--licencas', default=None,
                   help='Dados de licença das fontes (licencas-fontes/1); entra como entrada/licencas.json')
    c.set_defaults(executar=_criar, nome_comando='job criar')

    x = sub.add_parser('proxima', help='Roda a próxima fase ou para no portão com o que fazer')
    x.add_argument('pasta', nargs='?', default=None, help='Pasta do job')
    x.add_argument('--job', dest='pasta_job', default=None, help='Pasta do job (mesmo que o argumento posicional)')
    x.add_argument('--todas', action='store_true', help='Segue até um portão, uma falha ou o fim')
    x.add_argument('--teto-memoria-bytes', type=int, default=None,
                   help='Teto de memória da leitura confirmado pelo DA, quando a leitura parou no teto calculado')
    x.add_argument('--tempo-max-s', type=float, default=None,
                   help='Tempo máximo da leitura confirmado pelo DA, quando a leitura parou no tempo padrão')
    x.set_defaults(executar=_proxima, nome_comando='job proxima')

    e = sub.add_parser('estado', help='Mostra as fases e o que fazer, sem rodar nada')
    e.add_argument('pasta', help='Pasta do job')
    e.set_defaults(executar=_estado, nome_comando='job estado')

    t = sub.add_parser('trocar-entrada', help='Troca uma entrada congelada e invalida só as fases que dependem dela')
    t.add_argument('pasta', help='Pasta do job')
    t.add_argument('entrada', help='Caminho dentro do job, por exemplo entrada/kv.psd')
    t.add_argument('arquivo', help='Arquivo novo')
    t.set_defaults(executar=_trocar, nome_comando='job trocar-entrada')

    r = sub.add_parser('remover-entrada', help='Tira um arquivo de fonte de entrada/fontes/ e invalida só as fases que '
                                               'dependem dele')
    r.add_argument('pasta', help='Pasta do job')
    r.add_argument('entrada', help='Caminho dentro do job, por exemplo entrada/fontes/<arquivo>')
    r.set_defaults(executar=_remover, nome_comando='job remover-entrada')


def _abs(caminho):
    """Caminho absoluto: as fases rodam em subprocesso com outra pasta de trabalho."""
    return Path(caminho).resolve() if caminho else None


def _erro(comando, e, pasta=None):
    return Resultado(comando=comando, codigo=int(e.codigo), situacao=e.situacao, o_que_fazer=e.o_que_fazer,
                     pasta_job=Path(pasta) if pasta else None, linhas_humanas=[str(e)])


def _criar(args):
    try:
        estado = nucleo.criar(_abs(args.pasta), _abs(args.psd), args.modo_dados,
                              getattr(args, 'teto_modo_dados', None), _abs(args.campanha), _abs(args.specs),
                              fontes=[_abs(f) for f in args.fontes or ()], licencas=_abs(args.licencas))
    except ErroJob as e:
        return _erro('job criar', e)
    return Resultado(comando='job criar', situacao='ok', o_que_fazer=estado['proxima']['o_que_fazer'],
                     contagens={'entradas': len(estado['entradas']),
                                'fontes': sum(1 for r in estado['entradas'] if r.startswith('entrada/fontes/'))},
                     ids={'job_id': estado['job_id']},
                     pasta_job=_abs(args.pasta), linhas_humanas=['Job criado em %s' % args.pasta])


def _proxima(args):
    pasta = _abs(args.pasta_job or args.pasta)
    if not pasta:
        return Resultado(comando='job proxima', codigo=int(Codigo.USO), situacao='erro',
                         o_que_fazer='Passe a pasta do job.', linhas_humanas=['Falta a pasta do job.'])
    from desdobra.leitor import erro_no_teto
    erro = erro_no_teto(args.teto_memoria_bytes, args.tempo_max_s)
    if erro:
        return Resultado(comando='job proxima', codigo=int(Codigo.USO), situacao='erro', o_que_fazer=erro,
                         linhas_humanas=['Valor inválido em --teto-memoria-bytes ou --tempo-max-s.'])
    opcoes = []
    for opcao, valor in (('--teto-memoria-bytes', args.teto_memoria_bytes), ('--tempo-max-s', args.tempo_max_s)):
        if valor is not None:
            opcoes += [opcao, str(valor)]
    try:
        return nucleo.proxima(pasta, todas=args.todas, opcoes_da_fase=opcoes)
    except ErroJob as e:
        return _erro('job proxima', e, pasta)


def _estado(args):
    args.pasta = _abs(args.pasta)
    try:
        estado = nucleo.ler_estado(args.pasta)
        avaliacao, _ = nucleo.avaliar(args.pasta, estado, nucleo.ESTEIRA)
    except ErroJob as e:
        return _erro('job estado', e, args.pasta)
    linhas = []
    for fid, reg in estado['fases'].items():
        valida, motivo = avaliacao.get(fid, (False, 'fora da esteira'))
        com_bloqueio = ' com bloqueio pendente' if valida and reg.get('bloqueio') else ''
        linhas.append('%s: %s%s%s' % (fid, reg['situacao'], com_bloqueio, '' if valida else ' (%s)' % motivo))
    pendentes = nucleo.bloqueios_pendentes(estado, avaliacao, nucleo.ESTEIRA)
    proxima = nucleo.calcular_proxima(estado, avaliacao, nucleo.ESTEIRA)
    contagens = {'fases_validas': sum(1 for v, _m in avaliacao.values() if v), 'fases': len(avaliacao),
                 'bloqueios_pendentes': len(pendentes)}
    if pendentes:
        for k, v in pendentes[0][1].get('contagens', {}).items():
            contagens.setdefault(k, v)
    return Resultado(comando='job estado', situacao='ok_com_bloqueio' if pendentes else 'ok', fase=proxima['fase'],
                     o_que_fazer=proxima['o_que_fazer'], contagens=contagens,
                     ids={'job_id': estado['job_id']}, pasta_job=Path(args.pasta), linhas_humanas=linhas)


def _trocar(args):
    args.pasta = _abs(args.pasta)
    try:
        estado, avaliacao = nucleo.trocar_entrada(args.pasta, args.entrada, args.arquivo)
    except ErroJob as e:
        return _erro('job trocar-entrada', e, args.pasta)
    invalidas = sorted(k for k, (v, _m) in avaliacao.items() if not v)
    return Resultado(comando='job trocar-entrada', situacao='ok', o_que_fazer=estado['proxima']['o_que_fazer'],
                     contagens={'fases_invalidas': len(invalidas)}, ids={'job_id': estado['job_id']},
                     pasta_job=Path(args.pasta), linhas_humanas=['Fases a refazer: %s' % (', '.join(invalidas) or 'nenhuma')])


def _remover(args):
    args.pasta = _abs(args.pasta)
    try:
        estado, avaliacao = nucleo.remover_entrada(args.pasta, args.entrada)
    except ErroJob as e:
        return _erro('job remover-entrada', e, args.pasta)
    invalidas = sorted(k for k, (v, _m) in avaliacao.items() if not v)
    return Resultado(comando='job remover-entrada', situacao='ok', o_que_fazer=estado['proxima']['o_que_fazer'],
                     contagens={'fases_invalidas': len(invalidas)}, ids={'job_id': estado['job_id']},
                     pasta_job=Path(args.pasta), linhas_humanas=['Fases a refazer: %s' % (', '.join(invalidas) or 'nenhuma')])
