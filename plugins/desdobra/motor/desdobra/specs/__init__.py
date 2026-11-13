# -*- coding: utf-8 -*-
"""Specs do veiculador em 4 niveis (M3) e o validador de arquivo (arquitetura-v1.md, 4.8 e 5.5).

Comandos:
    desdobra spec importar --job <pasta>     fase "specs": le as folhas de entrada/specs/ no filho isolado e grava
                                             specs/rascunho.json, specs/formatos-do-job.json e
                                             sugestoes/pacote-specs.json
    desdobra spec confirmar --job <pasta>    so no terminal interativo: o DA confirma os valores, escolhe a leitura
                                             nas fontes divergentes e digita o valor ao lado do recorte da pagina
                                             sem texto
    desdobra validar <arquivo> --formato <chave> (--job <pasta> | --perfil <spec.json>) [--condicao X]
                                             confere qualquer arquivo, inclusive export humano, contra um formato

Modulos: filho (o unico que parseia a folha), leitura (lado do processo principal), extrair (o numero sai do
texto literal do trecho), modelo (os 4 niveis), importar (o job), confirmar (o DA), validar (o arquivo).
"""
import argparse
from pathlib import Path

from desdobra import contratos
from desdobra.resultado import Codigo, Resultado

O_QUE_FAZER_SEM_FOLHAS = ('O job não tem folha de spec. Acrescente as folhas em entrada/specs/ com "desdobra job '
                          'trocar-entrada <pasta> entrada/specs/<veiculador>/<arquivo> <arquivo>" (PDF, HTML salvo, '
                          'CSV ou texto do e-mail).')
O_QUE_FAZER_PENDENTE = ('O rascunho das specs está em specs/rascunho.json. Nenhum valor vale sem o DA: rode "desdobra '
                        'spec confirmar --job <pasta>" num terminal interativo para confirmar os valores, escolher a '
                        'leitura onde as fontes divergem e digitar os valores das páginas sem texto.')
O_QUE_FAZER_OK = ('As specs confirmadas estão em specs/formatos-do-job.json. Para rever, rode "desdobra spec confirmar '
                  '--job <pasta>" num terminal interativo.')
O_QUE_FAZER_RECUSA = (' Uma ou mais folhas foram recusadas: só entram PDF (com ou sem camada de texto), HTML salvo, '
                      'CSV e texto (.txt ou .eml). Planilha .xlsx e imagem solta ficam fora da v1.')


def _aceitar_tetos(p):
    """O job proxima repassa --teto-memoria-bytes e --tempo-max-s a toda fase; a fase de specs aceita e ignora."""
    p.add_argument('--teto-memoria-bytes', type=int, default=None, help=argparse.SUPPRESS)
    p.add_argument('--tempo-max-s', type=float, default=None, help=argparse.SUPPRESS)


def registrar(subparsers):
    p = subparsers.add_parser('spec', help='Folhas de spec do veiculador: rascunho em 4 níveis e confirmação pelo DA')
    sub = p.add_subparsers(dest='acao_spec', metavar='ACAO', required=True)
    i = sub.add_parser('importar', help='Lê as folhas de entrada/specs/ e grava o rascunho e os formatos do job')
    i.add_argument('--job', required=True, help='Pasta do job')
    _aceitar_tetos(i)
    i.set_defaults(executar=_importar, nome_comando='spec importar')
    c = sub.add_parser('confirmar', help='Só no terminal interativo: o DA confirma os valores do rascunho')
    c.add_argument('--job', required=True, help='Pasta do job')
    c.add_argument('--formato', default=None, help='Só os valores deste formato (chave ou id)')
    c.add_argument('--campo', default=None, help='Só os valores deste campo')
    c.set_defaults(executar=_confirmar, nome_comando='spec confirmar')

    v = subparsers.add_parser('validar', help='Valida um arquivo (inclusive export humano) contra um formato de spec')
    v.add_argument('arquivo', help='O arquivo (JPG, PNG, GIF)')
    v.add_argument('--formato', required=True, help='Chave do formato (veiculador|circuito|LxA) ou id')
    origem = v.add_mutually_exclusive_group(required=True)
    origem.add_argument('--job', default=None, help='Pasta do job: valida contra specs/formatos-do-job.json')
    origem.add_argument('--perfil', default=None, help='Perfil da biblioteca ou rascunho (spec/1), só para diagnóstico')
    v.add_argument('--condicao', default=None, choices=validar_condicoes(), help='Como a peça vai ser servida, quando o peso é condicional '
                                                    '(hospedado, por_tag, tag_carga_inicial, tag_carga_posterior)')
    v.add_argument('--saida', default=None, help='Arquivo JSON onde gravar o relatório (validacao-arquivo/1)')
    v.set_defaults(executar=_validar, nome_comando='validar')


def validar_condicoes():
    from desdobra.specs import validar
    return validar.CONDICOES


def _uso(comando, texto, pasta=None):
    return Resultado(comando=comando, codigo=int(Codigo.USO), situacao='erro', o_que_fazer=texto,
                     pasta_job=Path(pasta) if pasta else None, linhas_humanas=[texto])


def _contagens(rascunho, info):
    r = rascunho['resumo']
    cont = {k: v for k, v in r.items() if isinstance(v, int)}
    for k in ('folhas_recusadas', 'acoes_aplicadas', 'acoes_ignoradas', 'propostas_aplicadas', 'propostas_ignoradas',
              'propostas_do_modelo', 'propostas_ignoradas_modo_c'):
        cont[k] = int(info.get(k) or 0)
    return cont


def _importar(args):
    from desdobra.specs import importar
    pasta = Path(args.job).resolve()
    if not (pasta / 'estado.json').is_file():
        return _uso('spec importar', 'Rode a importação numa pasta de job ("desdobra job criar").', pasta)
    try:
        rascunho, formatos, info = importar.importar(pasta)
    except contratos.ErroContrato as e:
        return Resultado(comando='spec importar', codigo=int(Codigo.RECUSADO), situacao='recusado', fase='specs',
                         o_que_fazer='Um arquivo de specs do job não segue o contrato. Rode "desdobra spec importar '
                                     '--job <pasta>" sem --envelope para ver qual.',
                         pasta_job=pasta, linhas_humanas=[str(e)])
    r = rascunho['resumo']
    if not r['folhas'] and not info['folhas_recusadas']:
        o_que_fazer = O_QUE_FAZER_SEM_FOLHAS
    elif formatos['formatos']:
        o_que_fazer = O_QUE_FAZER_OK
    else:
        o_que_fazer = O_QUE_FAZER_PENDENTE
    if info['folhas_recusadas']:
        o_que_fazer += O_QUE_FAZER_RECUSA
    cont = _contagens(rascunho, info)
    cont['formatos_do_job'] = len(formatos['formatos'])
    linhas = ['Specs: %d folha(s), %d formato(s), %d valor(es) em rascunho, %d confirmado(s), %d divergência(s), '
              '%d recorte(s) de página sem texto.' % (r['folhas'], r['formatos'], r['valores_rascunho'],
                                                       r['valores_confirmados'], r['divergencias'], r['recortes']),
              'Formatos do job (só valores confirmados): %d.' % len(formatos['formatos'])]
    return Resultado(comando='spec importar', situacao='ok', fase='specs', o_que_fazer=o_que_fazer, contagens=cont,
                     segredos_ja_bloqueados=int(info.get('segredos_bloqueados') or 0), pasta_job=pasta,
                     linhas_humanas=linhas)


def _confirmar(args):
    from desdobra import humano
    from desdobra.specs import confirmar
    pasta = Path(args.job).resolve()
    try:
        disparo = humano.exigir('spec confirmar')
    except humano.ErroHumano as e:
        return Resultado(comando='spec confirmar', codigo=int(Codigo.RECUSADO), situacao='recusado',
                         o_que_fazer=humano.o_que_fazer('spec confirmar'), pasta_job=pasta,
                         contagens={'recusa_%s' % e: 1},
                         linhas_humanas=[humano.linha_recusa('spec confirmar')])
    if not (pasta / 'estado.json').is_file():
        return _uso('spec confirmar', 'Rode a confirmação numa pasta de job ("desdobra job criar").', pasta)
    novas, rascunho, formatos, info = confirmar.sessao(pasta, disparo=disparo, filtro_formato=args.formato,
                                                       filtro_campo=args.campo)
    cont = _contagens(rascunho, info)
    cont.update(acoes_novas=len(novas), formatos_do_job=len(formatos['formatos']))
    return Resultado(comando='spec confirmar', situacao='ok', fase='specs',
                     o_que_fazer=O_QUE_FAZER_OK if formatos['formatos'] else O_QUE_FAZER_PENDENTE, contagens=cont,
                     pasta_job=pasta, linhas_humanas=['%d ação(ões) do DA gravada(s) em specs/confirmacoes.json; %d '
                                                      'formato(s) do job.' % (len(novas), len(formatos['formatos']))])


def _validar(args):
    from desdobra.specs import importar, validar
    arquivo = Path(args.arquivo)
    if not arquivo.is_file():
        return _uso('validar', 'O arquivo a validar não foi encontrado. Confira o caminho.')
    if args.job:
        pasta = Path(args.job).resolve()
        caminho = pasta / importar.ARQUIVO_FORMATOS
        if not caminho.is_file():
            return _uso('validar', 'O job não tem specs/formatos-do-job.json: rode a fase specs e confirme os valores '
                                   'com "desdobra spec confirmar".', pasta)
        doc, contra = contratos.ler(caminho, 'spec/1'), 'formatos_do_job'
    else:
        pasta = None
        from desdobra.specs import modelo
        doc = modelo.completar_documento(contratos.ler(Path(args.perfil), 'spec/1'))
        contra = 'perfil' if doc['tipo'] == 'perfil' else ('rascunho' if doc['tipo'] == 'rascunho' else 'formatos_do_job')
    try:
        rel = validar.validar(arquivo, doc, args.formato, contra, condicao=args.condicao)
    except validar.ErroValidar:
        return _uso('validar', 'O formato não está nas specs. Use a chave do formato (veiculador|circuito|LxA) que '
                               'está em specs/formatos-do-job.json.', pasta)
    if args.saida:
        contratos.gravar(Path(args.saida), rel, validar.ESQUEMA)
    itens = rel['verificacoes']
    cont = {s: sum(1 for i in itens if i['situacao'] == s) for s in ('ok', 'aviso', 'reprova', 'nao_verificado', 'sem_regra')}
    cont['verificacoes'] = len(itens)
    cont['contra_valor_nao_confirmado'] = int(contra != 'formatos_do_job')
    reprovado = rel['resultado'] == 'reprovado'
    linhas = ['%s: %s (medido %s, esperado %s%s)' % (i['campo'], i['situacao'], i['medida'], i['esperado'],
                                                     ', %s' % i['motivo'] if i['motivo'] else '') for i in itens]
    linhas.insert(0, 'Resultado: %s.' % rel['resultado'])
    if contra != 'formatos_do_job':
        linhas.append('Validação contra valores que o DA ainda não confirmou: só diagnóstico.')
    o_que_fazer = ('O arquivo reprovou: veja a lista de verificações no terminal.' if reprovado else
                   'A validação ficou incompleta: o formato não tem regra confirmada de dimensão, peso ou tipo. '
                   'Confirme as specs com "desdobra spec confirmar" e valide de novo.' if cont['sem_regra'] else
                   'O arquivo passou com avisos: veja a lista no terminal.' if rel['resultado'] == 'aviso' else
                   'O arquivo passou nas verificações deste formato.')
    return Resultado(comando='validar', codigo=int(Codigo.RECUSADO if reprovado else Codigo.OK),
                     situacao='recusado' if reprovado else 'ok', o_que_fazer=o_que_fazer, contagens=cont,
                     ids={'arquivo_sha256': rel['arquivo']['sha256']},
                     numeros={'bytes': rel['arquivo']['bytes'], 'largura': rel['arquivo']['largura'],
                              'altura': rel['arquivo']['altura']},
                     pasta_job=pasta, linhas_humanas=linhas)
