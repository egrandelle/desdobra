# -*- coding: utf-8 -*-
"""Briefing do job (briefing/1, arquitetura-v1.md, 5.3).

    desdobra briefing importar --teste <arquivo.json> --job <pasta>
    desdobra briefing rascunho --job <pasta> [--saida <arquivo.json>]
    desdobra briefing funcoes --job <pasta>
    desdobra briefing confirmar --job <pasta>

"importar --teste" grava em briefing/briefing-confirmado.json um briefing escrito a mao (por exemplo o fixture do
M5), com a origem fixture_de_teste e o cabecalho (hashes do laudo, das specs, do design system e da conferencia de
fontes) dos arquivos do job de agora. O motor deriva e renderiza a partir dele; o entregar (M6) recusa todo job cujo
briefing tenha essa origem. Sem --teste, o importar recusa: quem grava como confirmado pelo DA e a tela (M7) ou
"desdobra briefing confirmar" no terminal interativo, que entra com a tela.

"rascunho" monta o briefing sem nenhum valor (todo campo pendente), um item por grupo e por camada desenhavel e a
sugestao citada da regra da decisao 10 nas cobertas: e o ponto de partida da rotulagem do DA. Grava em --saida (por
padrao rotulagem/briefing-rascunho.json; dentro do job, so em rotulagem/). O rascunho tem a
origem "rascunho": o derivar e a entrega recusam.

"confirmar" grava o briefing confirmado a partir do rascunho da tela (as familias confirmadas na janela, o passo 2, o
Design system e o modo de dados escolhido na tela) e deriva, pelo mesmo gravador do "Salvar e seguir" da tela
(desdobra.briefing.salvar). O DA nunca usa o terminal (decisoes-v1.md, 159): o comando fica para os testes e para a
Trezion, so num terminal interativo, com a pergunta no console.

"funcoes" mostra as contagens da heranca (camadas por funcao, de onde veio a funcao), sem texto de peca.
"""
from pathlib import Path

from desdobra.resultado import Codigo, Resultado

O_QUE_FAZER_IMPORTADO = ('O briefing de teste está em briefing/briefing-confirmado.json, com a origem fixture_de_teste. '
                         'Rode "desdobra derivar --job <pasta>". O entregar recusa job com briefing de teste.')
O_QUE_FAZER_SEM_TESTE = ('Sem --teste, o importar não grava: o briefing confirmado pelo DA sai da tela ("Salvar e '
                         'seguir"). Para teste, use --teste.')
PERGUNTA_CONFIRMAR = 'Gravar o briefing confirmado com as famílias confirmadas na tela? Digite sim para gravar: '
O_QUE_FAZER_CONFIRMADO = ('O briefing confirmado está em briefing/briefing-confirmado.json, a versão anterior em '
                          'briefing/historico/ e a derivação em derivacao/.')
O_QUE_FAZER_PENDENTE = ('O briefing não foi gravado: falta confirmar alguma coisa na tela (as famílias, o modo de dados, '
                        'as funções ou o design system).')


def registrar(subparsers):
    p = subparsers.add_parser('briefing', help='Briefing do job: importar de teste, rascunho e funções resolvidas')
    sub = p.add_subparsers(dest='acao_briefing', metavar='ACAO', required=True)
    i = sub.add_parser('importar', help='Grava um briefing escrito à mão, com a origem fixture de teste')
    i.add_argument('arquivo', help='O briefing em JSON (briefing/1, sem o cabeçalho)')
    i.add_argument('--job', required=True, help='Pasta do job')
    i.add_argument('--teste', action='store_true', help='Marca a origem fixture_de_teste (obrigatório)')
    i.set_defaults(executar=_importar, nome_comando='briefing importar')
    r = sub.add_parser('rascunho', help='Monta o briefing sem valor para o DA preencher')
    r.add_argument('--job', required=True, help='Pasta do job')
    r.add_argument('--saida', default=None, help='Arquivo onde gravar (padrão: rotulagem/briefing-rascunho.json do job; '
                                                  'dentro do job, só em rotulagem/)')
    r.set_defaults(executar=_rascunho, nome_comando='briefing rascunho')
    c = sub.add_parser('confirmar', help='Grava o briefing confirmado a partir do rascunho da tela (só num terminal '
                                         'interativo; para teste e para a Trezion)')
    c.add_argument('--job', required=True, help='Pasta do job')
    c.set_defaults(executar=_confirmar, nome_comando='briefing confirmar')
    f = sub.add_parser('funcoes', help='Contagens da herança de funções do briefing gravado')
    f.add_argument('--job', required=True, help='Pasta do job')
    f.set_defaults(executar=_funcoes, nome_comando='briefing funcoes')


def _pasta(args):
    return Path(args.job).resolve()


def _erro(comando, pasta, texto, codigo=Codigo.USO, contagens=None, linhas=None):
    return Resultado(comando=comando, codigo=int(codigo), situacao='erro' if codigo == Codigo.USO else 'recusado',
                     o_que_fazer=texto, pasta_job=pasta, contagens=contagens or {},
                     linhas_humanas=linhas or [texto])


def _importar(args):
    from desdobra.briefing import modelo
    from desdobra.job import nucleo
    pasta = _pasta(args)
    if not args.teste:
        return _erro('briefing importar', pasta, O_QUE_FAZER_SEM_TESTE, Codigo.RECUSADO)
    if not (pasta / 'estado.json').is_file():
        return _erro('briefing importar', pasta, 'A pasta não é um job do desdobra.')
    try:
        with nucleo.Trava(pasta):
            dados = modelo.importar_teste(pasta, Path(args.arquivo).resolve())
    except modelo.ErroBriefing as e:
        cont = {}
        for item in e.erros:
            cont[item['codigo']] = cont.get(item['codigo'], 0) + 1
        linhas = [str(e)] + ['  %s%s' % (item['codigo'], (' em %s' % item['onde']) if item.get('onde') else '')
                             for item in e.erros]
        return _erro('briefing importar', pasta, 'O briefing foi recusado: corrija o arquivo e importe de novo.',
                     Codigo.RECUSADO, cont, linhas)
    except nucleo.ErroJob as e:
        return Resultado(comando='briefing importar', codigo=int(e.codigo), situacao=e.situacao,
                         o_que_fazer=e.o_que_fazer, pasta_job=pasta, linhas_humanas=[str(e)])
    except (OSError, ValueError) as e:
        return _erro('briefing importar', pasta, 'O arquivo do briefing não abriu como JSON (%s).' % type(e).__name__)
    nucleo.registrar_evento(pasta, 'briefing_importado_teste', n_funcoes=len(dados['funcoes']),
                            n_formatos=len(dados['formatos']))
    return Resultado(comando='briefing importar', situacao='ok', pasta_job=pasta, o_que_fazer=O_QUE_FAZER_IMPORTADO,
                     contagens={'funcoes': len(dados['funcoes']), 'formatos': len(dados['formatos']),
                                'mestres': len(dados['mestres'])},
                     linhas_humanas=['Briefing de teste gravado (origem fixture_de_teste).'])


def _confirmar(args):
    from desdobra import humano
    from desdobra.briefing import salvar
    from desdobra.tela import estado
    pasta = _pasta(args)
    nome = salvar.COMANDO
    try:
        disparo = humano.exigir(nome)
    except humano.ErroHumano as e:
        return Resultado(comando=nome, codigo=int(Codigo.RECUSADO), situacao='recusado',
                         o_que_fazer=humano.O_QUE_FAZER, pasta_job=pasta, contagens={'recusa_%s' % e: 1},
                         linhas_humanas=['Este comando só roda num terminal interativo.'])
    if not (pasta / 'estado.json').is_file():
        return _erro(nome, pasta, 'A pasta não é um job do desdobra.')
    try:
        conteudo = estado.montar(pasta)
    except estado.ErroTela as e:
        return _erro(nome, pasta, 'O job não tem o que a tela mostra: %s' % e, Codigo.RECUSADO,
                     {'recusa_%s' % e.motivo: 1})
    pend = salvar.pendencias(pasta, conteudo, disparo.origem)
    if pend:
        cont = {}
        for p in pend:
            cont[p['codigo']] = cont.get(p['codigo'], 0) + 1
        return _erro(nome, pasta, O_QUE_FAZER_PENDENTE, Codigo.RECUSADO, cont,
                     [O_QUE_FAZER_PENDENTE] + ['  %s' % p['codigo'] for p in pend])
    if humano.ler(PERGUNTA_CONFIRMAR).strip().lower() != 'sim':
        return _erro(nome, pasta, 'Nada foi gravado.', Codigo.RECUSADO, {'sem_confirmacao': 1})
    try:
        r = salvar.salvar(pasta, conteudo, disparo)
    except salvar.ErroSalvar as e:
        return _erro(nome, pasta, O_QUE_FAZER_PENDENTE, Codigo.RECUSADO, {p['codigo']: 1 for p in e.pendencias})
    return Resultado(comando=nome, situacao='ok' if r['derivado'] else 'ok_com_bloqueio', pasta_job=pasta,
                     o_que_fazer=O_QUE_FAZER_CONFIRMADO,
                     contagens={'familias': len(r['briefing']['composicoes']), 'derivado': int(r['derivado']),
                                'devolvidos': r['devolucoes'] or 0},
                     linhas_humanas=['Briefing confirmado gravado (origem %s).' % r['briefing']['cabecalho']['origem']])


def _rascunho(args):
    from desdobra import arquivos
    from desdobra.briefing import modelo
    pasta = _pasta(args)
    if not (pasta / 'estado.json').is_file():
        return _erro('briefing rascunho', pasta, 'A pasta não é um job do desdobra.')
    destino = modelo.destino_do_rascunho(pasta, args.saida)
    if destino is None or destino.is_dir():
        return _erro('briefing rascunho', pasta, 'O rascunho não grava dentro da pasta do job fora de rotulagem/ '
                     '(nunca em briefing/, specs/, render/, derivacao/ nem em arquivo do DA). Use o padrão ou um '
                     'caminho fora do job.', Codigo.RECUSADO)
    dados, cont = modelo.rascunho(pasta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    arquivos.gravar_json_atomico(destino, dados)
    return Resultado(comando='briefing rascunho', situacao='ok', pasta_job=pasta, contagens=cont,
                     o_que_fazer='O rascunho do briefing está gravado. Preencha cada decisão (valor, situação '
                                 'confirmado e origem) e importe.',
                     linhas_humanas=['Rascunho gravado em %s.' % destino])


def _funcoes(args):
    from desdobra import contratos
    from desdobra.briefing import modelo
    pasta = _pasta(args)
    try:
        b = modelo.ler(pasta)
    except contratos.ErroContrato as e:
        return _erro('briefing funcoes', pasta, 'O briefing não segue o contrato: %s' % e, Codigo.RECUSADO)
    if b is None:
        return _erro('briefing funcoes', pasta, 'O job não tem briefing.', Codigo.RECUSADO)
    laudo = contratos.ler(pasta / modelo.ARQUIVO_LAUDO, 'laudo/1')
    resolvidas, erros, info = modelo.resolver(laudo, b)
    cont = {'camadas': len(resolvidas), 'erros': len(erros), 'fora_do_quadro': info['fora_do_quadro'],
            'invisiveis': info['invisiveis']}
    for r in resolvidas.values():
        cont['funcao_%s' % r['funcao']] = cont.get('funcao_%s' % r['funcao'], 0) + 1
        cont['por_%s' % r['por']] = cont.get('por_%s' % r['por'], 0) + 1
    return Resultado(comando='briefing funcoes', situacao='ok' if not erros else 'ok_com_bloqueio', pasta_job=pasta,
                     contagens=cont, o_que_fazer='Funções resolvidas pela herança do briefing gravado.',
                     linhas_humanas=['%d camada(s) com função resolvida, %d erro(s).' % (len(resolvidas), len(erros))])
