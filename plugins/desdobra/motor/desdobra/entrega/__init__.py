# -*- coding: utf-8 -*-
"""desdobra aprovar, desdobra entregar e desdobra conferir-entrega (M6, arquitetura-v1.md, 9.7; decisoes-v1.md, 138, 139
e 142).

    desdobra aprovar --job <pasta> --formato <id> [--formato <id> ...]
    desdobra entregar --job <pasta>
    desdobra conferir-entrega --job <pasta>
    desdobra parametros-entrega --job <pasta> --formato <id> [--rotacao-sentido ...] [--condicao ...]
        [--cor-de-achatamento #rrggbb] [--borda-1px sim|nao] [--limpar <campo> ...]

aprovar, entregar e parametros-entrega so partem do DA, num terminal interativo (desdobra.humano; o gancho PreToolUse
nega os tres pelo Claude). conferir-entrega so le e qualquer um roda, o Claude inclusive.

"parametros-entrega" grava as decisoes do DA por formato em parametros/entrega.json (desdobra.entrega.parametros): o
sentido do giro (nº 139), a condicao do teto (nº 137), a cor de achatamento e a borda de 1 px. Mostra o antes e o
depois de cada campo e pede o sim digitado, sem resposta padrao, como o aprovar; com o sim, confere de novo com a trava
do job e grava. Giro, achatamento e borda entram nos parametros do encoder: mudar um deles derruba a aprovacao.

"aprovar" confere cada formato pedido como a entrega confere (master, render.json, contrato refeito, KV, briefing e
rotacao; a origem do briefing fica para o entregar), gera o arquivo final de cada um (desdobra.entrega.codificar), grava
a previa em entrega/previa/ e pede uma confirmacao so, sem resposta padrao. Com o sim, confere tudo de novo com a trava
do job e grava um registro por formato em briefing/aprovacao.json (desdobra.entrega.aprovacao). O roteiro e o do
nucleo comum (desdobra.entrega.nucleo_aprovar), o mesmo do ato de aprovar da tela (M7b, B4); o comando fica so para a
Trezion e para os testes, e o DA aprova na tela.

"entregar" roda o portao inteiro em todos os formatos do briefing (desdobra.entrega.portao): briefing de origem 'da' com
a conferencia inteira (fixture de teste e rascunho sao recusados), rotacao decidida, master e render coerentes, contrato
refeito e aprovacao valida. Recusado, o resultado lista o codigo de recusa de cada formato e nada e gravado. O formato
que o encoder recusa por decisao ou folha que falta (validar.RECUSAS_ROTEADAS, como a cor de achatamento de um master com
transparencia) nao fecha o portao: vai para reprovados com a regra e a sugestao, sem arquivo. Com o portao aberto em
todos os formatos, a validacao final confere cada arquivo final (desdobra.entrega.validar), o entregar mostra para onde
vai cada formato e pede o sim digitado, sem resposta padrao, como o aprovar; com o sim, confere tudo de novo com a trava
do job (mudou desde a pergunta: recusa) e a entrega e gravada de uma vez: entrega/aprovados, entrega/reprovados (com a regra e a sugestao) e entrega/relatorio-entrega.json; a
entrega anterior vai para entrega/anteriores/<carimbo>/, e o manifesto-licenca.json da raiz do job fecha junto
(desdobra.entrega.relatorio). A saida termina com o resumo em portugues: o que passou, o que avisou e o que ficou so
como registro.

"conferir-entrega" confere entrega/ contra o relatorio (selo, sha256 e bytes de cada arquivo, nada sobrando, nenhum
arquivo que reprova em aprovados, nenhum arquivo de fonte) e o manifesto da raiz do job contra o selo do relatorio. Nunca grava, nem a trava do job.
"""
from pathlib import Path

from desdobra.resultado import Codigo, Resultado

O_QUE_FAZER_RECUSA = ('A entrega foi recusada. Veja o código de cada formato; com o briefing de teste, a entrega fica '
                      'recusada até o briefing ser confirmado pelo DA.')
O_QUE_FAZER_APROVAR_RECUSA = ('A aprovação foi recusada e nada foi gravado. Veja o código de cada formato e corrija. A '
                              'aprovação é um clique do DA na tela do desdobra: peça ao Claude para abrir a tela do job '
                              '(/desdobra:continuar).')
# o que vale quando o job muda entre a pergunta e a gravacao (so no console interativo; o envelope recusa antes)
O_QUE_FAZER_MUDOU = 'O job mudou durante a confirmação. Nada foi gravado: confirme de novo, com o job de agora.'


def registrar(subparsers):
    a = subparsers.add_parser('aprovar', help='Aprova o arquivo final de um ou mais formatos (só no terminal interativo)')
    a.add_argument('--job', required=True, help='Pasta do job')
    a.add_argument('--formato', required=True, action='append', type=_id_formato,
                   help='Id do formato a aprovar (repita para aprovar vários com uma confirmação só)')
    a.set_defaults(executar=_aprovar, nome_comando='aprovar')
    e = subparsers.add_parser('entregar', help='Confere o portão da entrega de todos os formatos (só no terminal '
                                               'interativo)')
    e.add_argument('--job', required=True, help='Pasta do job')
    e.set_defaults(executar=_entregar, nome_comando='entregar')
    c = subparsers.add_parser('conferir-entrega', help='Confere entrega/ contra o relatório da entrega (só lê)')
    c.add_argument('--job', required=True, help='Pasta do job')
    c.set_defaults(executar=_conferir_entrega, nome_comando='conferir-entrega')
    from desdobra.entrega import parametros
    p = subparsers.add_parser('parametros-entrega', help='Grava os parâmetros de entrega de um formato em '
                                                         'parametros/entrega.json (só no terminal interativo)')
    p.add_argument('--job', required=True, help='Pasta do job')
    p.add_argument('--formato', required=True, type=_id_formato, help='Id do formato do briefing')
    p.add_argument('--rotacao-sentido', choices=parametros.SENTIDOS,
                   help='Sentido do giro confirmado com o veículo (só formato de 90 ou 270 graus, decisão 139)')
    p.add_argument('--condicao', choices=parametros.CONDICOES, help='Condição do teto de peso (decisão 137)')
    p.add_argument('--cor-de-achatamento', metavar='#RRGGBB',
                   help='Cor sobre a qual o master com transparência é achatado')
    p.add_argument('--borda-1px', choices=('sim', 'nao'), help='Condição da borda de 1 px: sim, o fundo da peça é o da '
                                                               'página')
    p.add_argument('--limpar', action='append', default=[], choices=[c.replace('_', '-') for c in parametros.CAMPOS],
                   help='Tira um campo do formato (repita para tirar vários)')
    p.set_defaults(executar=_parametros_entrega, nome_comando='parametros-entrega')


def _id_formato(valor):
    from desdobra.render import _id_formato as id_do_render
    return id_do_render(valor)


def _recusa_terminal(comando, pasta, motivo):
    from desdobra import humano
    return Resultado(comando=comando, codigo=int(Codigo.RECUSADO), situacao='recusado',
                     o_que_fazer=humano.o_que_fazer(comando), pasta_job=pasta, contagens={'recusa_%s' % motivo: 1},
                     linhas_humanas=[humano.linha_recusa(comando)])


def _sem_job(comando, pasta):
    return Resultado(comando=comando, codigo=int(Codigo.USO), situacao='erro', pasta_job=pasta,
                     o_que_fazer='O comando só funciona numa pasta de job do desdobra.',
                     linhas_humanas=['A pasta não é um job do desdobra.'])


def _linhas_das_falhas(conf):
    linhas = []
    for fid, item in conf['formatos'].items():
        for f in item['falhas']:
            campos = (f.get('medidas') or {}).get('campos')
            linhas.append('  %s: %s%s' % (fid, f['codigo'], (' (%s)' % ', '.join(campos)) if campos else ''))
    return linhas


def _recusado(comando, pasta, conf, o_que_fazer):
    from desdobra.entrega import portao
    cont = {'recusa_%s' % k: v for k, v in portao.falhas_por_codigo(conf).items()}
    cont['formatos'] = len(conf['formatos'])
    if conf['briefing'] is not None and not conf['formatos']:
        cont['recusa_%s' % conf['briefing']] = 1
    return Resultado(comando=comando, codigo=int(Codigo.RECUSADO), situacao='recusado', pasta_job=pasta,
                     o_que_fazer=o_que_fazer, contagens=cont,
                     linhas_humanas=['%s recusado:' % comando] + _linhas_das_falhas(conf))


def _erro_job(comando, pasta, e):
    return Resultado(comando=comando, codigo=int(e.codigo), situacao=e.situacao, o_que_fazer=e.o_que_fazer,
                     pasta_job=pasta, linhas_humanas=[str(e)])


def _aprovar(args):
    from desdobra import humano
    from desdobra.entrega import nucleo_aprovar
    from desdobra.job import nucleo
    from desdobra.render import perguntar
    pasta = Path(args.job).resolve()
    try:
        disparo = humano.exigir('aprovar')
    except humano.ErroHumano as e:
        return _recusa_terminal('aprovar', pasta, str(e))
    if not (pasta / 'estado.json').is_file():
        return _sem_job('aprovar', pasta)
    formatos = list(dict.fromkeys(args.formato))
    # o mesmo nucleo do ato de aprovar da tela (M7b, B4): conferir, previa, pergunta sem a trava, confirmar
    try:
        with nucleo.Trava(pasta):
            conf = nucleo_aprovar.conferir(pasta, formatos)
            if nucleo_aprovar.com_falha(conf):
                return _recusado('aprovar', pasta, conf, O_QUE_FAZER_APROVAR_RECUSA)
            previas = nucleo_aprovar.gravar_previas(pasta, conf)
    except nucleo.ErroJob as e:
        return _erro_job('aprovar', pasta, e)
    print('Arquivo final de cada formato (abra e confira antes de aprovar):')
    for fid, item in conf['formatos'].items():
        f = item['final']
        print('  %s: %s, %d bytes, parâmetros do encoder: %s' % (
            fid, previas[fid], len(f.dados), ', '.join('%s %s' % kv for kv in sorted(f.parametros.items()))))
    if not perguntar('Aprovar o arquivo final de %d formato(s)? Digite sim para aprovar: ' % len(formatos)):
        return Resultado(comando='aprovar', codigo=int(Codigo.RECUSADO), situacao='recusado', pasta_job=pasta,
                         o_que_fazer='O DA não aprovou. Nada foi gravado em briefing/aprovacao.json.',
                         linhas_humanas=['Aprovação cancelada.'])
    try:
        with nucleo.Trava(pasta):
            # a pergunta roda sem a trava: confere de novo e so grava se nada mudou desde o que o DA viu
            regs = nucleo_aprovar.confirmar(pasta, formatos, nucleo_aprovar.vista(conf), disparo)
    except nucleo_aprovar.ErroAprovar as e:
        return Resultado(comando='aprovar', codigo=int(Codigo.RECUSADO), situacao='recusado', pasta_job=pasta,
                         o_que_fazer=O_QUE_FAZER_MUDOU, contagens={'recusa_mudou_durante_a_confirmacao': len(e.mudaram)},
                         linhas_humanas=['O job mudou durante a confirmação: %s.' % ', '.join(e.mudaram)])
    except nucleo.ErroJob as e:
        return _erro_job('aprovar', pasta, e)
    return Resultado(comando='aprovar', situacao='ok', pasta_job=pasta, contagens={'aprovados': len(regs)},
                     o_que_fazer='A aprovação está em briefing/aprovacao.json, um registro por formato. Mudar o master, '
                                 'o render, o que alimenta o formato no briefing ou o arquivo final derruba a aprovação '
                                 'do formato.',
                     linhas_humanas=['%d formato(s) aprovado(s).' % len(regs)])


def _assinatura(itens):
    """{formato: o que o DA confirma no entregar}: nome, sha256 do arquivo (None sem arquivo), pasta, regras e hashes
    de origem. Igual antes e depois da pergunta: nada mudou desde o que o DA viu."""
    from desdobra.entrega import validar
    return {i['formato']: (i['nome'], i['final'].sha256 if i['final'] is not None else None,
                           validar.destino(i['verificacoes']),
                           sorted(v['regra'] for v in i['verificacoes'] if v['situacao'] == 'reprova'),
                           sorted((i.get('origem') or {}).items())) for i in itens}


def _entregar(args):
    from desdobra import humano
    from desdobra.entrega import portao
    from desdobra.job import nucleo
    from desdobra.entrega import relatorio, validar
    from desdobra.render import perguntar
    pasta = Path(args.job).resolve()
    try:
        disparo = humano.exigir('entregar')
    except humano.ErroHumano as e:
        return _recusa_terminal('entregar', pasta, str(e))
    if not (pasta / 'estado.json').is_file():
        return _sem_job('entregar', pasta)
    try:
        with nucleo.Trava(pasta):
            conf = portao.conferir(pasta)
            cont = portao.falhas_por_codigo(conf)
            itens = None if conf['briefing'] is not None or cont else validar.montar(pasta, conf)
    except nucleo.ErroJob as e:
        return _erro_job('entregar', pasta, e)
    if itens is None:
        nucleo.registrar_evento(pasta, 'entrega_recusada', n_formatos=len(conf['formatos']), codigos=sorted(cont))
        return _recusado('entregar', pasta, conf, O_QUE_FAZER_RECUSA)
    # o entregar pergunta como os outros comandos humanos: sim digitado, sem resposta padrao (decisoes-v1.md, 142)
    destinos = {i['formato']: validar.destino(i['verificacoes']) for i in itens}
    print('O que vai para a entrega (a entrega atual, se houver, vai para entrega/anteriores/):')
    for i in itens:
        regras = sorted(v['regra'] for v in i['verificacoes'] if v['situacao'] == 'reprova')
        print('  %s: entrega/%s/%s%s' % (i['formato'], destinos[i['formato']], i['nome'],
                                         (' (%s)' % ', '.join(regras)) if regras else ''))
    n_aprovados = sum(1 for d in destinos.values() if d == validar.APROVADOS)
    if not perguntar('Entregar %d formato(s), %d em entrega/aprovados e %d em entrega/reprovados? Digite sim para '
                     'entregar: ' % (len(itens), n_aprovados, len(itens) - n_aprovados)):
        return Resultado(comando='entregar', codigo=int(Codigo.RECUSADO), situacao='recusado', pasta_job=pasta,
                         contagens={'recusa_entrega_cancelada': 1},
                         o_que_fazer='O DA não confirmou. Nada foi gravado em entrega/.',
                         linhas_humanas=['Entrega cancelada.'])
    try:
        with nucleo.Trava(pasta):
            # a pergunta roda sem a trava: confere de novo e so grava se nada mudou desde o que o DA viu
            nova = portao.conferir(pasta)
            novos = None if nova['briefing'] is not None or portao.falhas_por_codigo(nova) else validar.montar(pasta, nova)
            if novos is None:  # o portao fechou: os formatos com falha (todos, com o briefing)
                mudou = sorted(fid for fid, item in nova['formatos'].items() if item['falhas']) or sorted(destinos)
            else:
                antes, agora = _assinatura(itens), _assinatura(novos)
                mudou = sorted(fid for fid in set(antes) | set(agora) if antes.get(fid) != agora.get(fid))
            if mudou:
                return Resultado(comando='entregar', codigo=int(Codigo.RECUSADO), situacao='recusado', pasta_job=pasta,
                                 o_que_fazer=O_QUE_FAZER_MUDOU, contagens={'recusa_mudou_durante_a_confirmacao': len(mudou)},
                                 linhas_humanas=['O job mudou durante a confirmação: %s.' % ', '.join(mudou)])
            job_id, _kv = portao.kv_atual(pasta)
            rel, anterior = validar.gravar(pasta, novos, job_id, disparo=disparo)
    except nucleo.ErroJob as e:
        return _erro_job('entregar', pasta, e)
    except validar.ErroEntrega as e:
        return Resultado(comando='entregar', codigo=int(Codigo.ERRO_INTERNO), situacao='erro', pasta_job=pasta,
                         contagens={'recusa_%s' % e.codigo: 1},
                         o_que_fazer='A entrega montada não conferiu e nada foi trocado em entrega/. É bug do motor: '
                                     'guarde a pasta do job.', linhas_humanas=[str(e)])
    except OSError as e:
        # a troca de pastas (validar._trocar) ja voltou o que tinha feito: no Windows, e um arquivo aberto em entrega/
        nucleo.registrar_evento(pasta, 'entrega_recusada', n_formatos=len(itens), codigos=['entrega_em_uso'])
        return Resultado(comando='entregar', codigo=int(Codigo.RECUSADO), situacao='recusado', pasta_job=pasta,
                         contagens={'recusa_entrega_em_uso': 1},
                         o_que_fazer='Um arquivo de entrega/ está aberto em outro programa. Feche os arquivos de entrega/ '
                                     '(e o manifesto-licenca.json) e confirme a entrega de novo; a entrega anterior '
                                     'ficou como estava.',
                         linhas_humanas=['A entrega não foi trocada: %s.' % type(e).__name__])
    nucleo.registrar_evento(pasta, 'entrega_gravada', **rel['contagens'])
    regras = {}
    linhas = ['Entrega gravada: %d arquivo(s) em entrega/aprovados e %d em entrega/reprovados.' % (
        rel['contagens']['aprovados'], rel['contagens']['reprovados'])]
    for a in rel['arquivos']:
        for r in a['regras']:
            regras['reprova_%s' % r] = regras.get('reprova_%s' % r, 0) + 1
        if a['pasta'] == validar.REPROVADOS:
            linhas.append('  %s: %s. %s' % (a['formato'], ', '.join(a['regras']), ' '.join(dict.fromkeys(a['sugestoes']))))
    if anterior is not None:
        linhas.append('A entrega anterior foi para %s.' % anterior.relative_to(pasta).as_posix())
    linhas += relatorio.linhas_do_resumo(rel)
    resumo = rel['resumo']['verificacoes']
    return Resultado(comando='entregar', situacao='ok', pasta_job=pasta,
                     contagens=dict(regras, formatos=len(rel['arquivos']), avisos=resumo['avisou'],
                                    so_registro=resumo['so_registro'], **rel['contagens']),
                     o_que_fazer='Os arquivos para o veículo estão em entrega/aprovados. Os de entrega/reprovados têm a '
                                 'regra e a sugestão em entrega/relatorio-entrega.json.', linhas_humanas=linhas)


def _pedido_de_parametros(args):
    """({campo: valor}, [campos a limpar]) do parametros-entrega, com os nomes do contrato."""
    valores = {}
    if args.rotacao_sentido is not None:
        valores['rotacao_sentido'] = args.rotacao_sentido
    if args.condicao is not None:
        valores['condicao'] = args.condicao
    if args.cor_de_achatamento is not None:
        valores['cor_de_achatamento'] = args.cor_de_achatamento
    if args.borda_1px is not None:
        valores['borda_1px'] = args.borda_1px == 'sim'
    return valores, list(dict.fromkeys(c.replace('-', '_') for c in args.limpar))


def _recusa_parametros(pasta, e):
    return Resultado(comando='parametros-entrega', codigo=int(Codigo.RECUSADO), situacao='recusado', pasta_job=pasta,
                     contagens={'recusa_%s' % e.codigo: 1}, linhas_humanas=[str(e)],
                     o_que_fazer='Nada foi gravado em parametros/entrega.json. Corrija o pedido e confirme de novo.')


def _texto_do_valor(valor):
    if valor is None:
        return '(nada)'
    if isinstance(valor, bool):
        return 'sim' if valor else 'nao'
    return valor


def _parametros_entrega(args):
    from desdobra import humano
    from desdobra.entrega import parametros
    from desdobra.job import nucleo
    from desdobra.render import perguntar
    pasta = Path(args.job).resolve()
    try:
        disparo = humano.exigir('parametros-entrega')
    except humano.ErroHumano as e:
        return _recusa_terminal('parametros-entrega', pasta, str(e))
    if not (pasta / 'estado.json').is_file():
        return _sem_job('parametros-entrega', pasta)
    valores, limpar = _pedido_de_parametros(args)
    if not valores and not limpar:
        return Resultado(comando='parametros-entrega', codigo=int(Codigo.USO), situacao='erro', pasta_job=pasta,
                         o_que_fazer='Diga ao menos um campo: o sentido do giro, a condição, a cor de achatamento, a '
                                     'borda de 1 px ou um campo a limpar.', linhas_humanas=['Nenhuma mudança pedida.'])
    if set(valores) & set(limpar):
        return Resultado(comando='parametros-entrega', codigo=int(Codigo.USO), situacao='erro', pasta_job=pasta,
                         o_que_fazer='Um campo não pode ser gravado e limpo no mesmo comando.',
                         linhas_humanas=['Campo pedido e limpo ao mesmo tempo: %s.' % ', '.join(
                             sorted(set(valores) & set(limpar)))])
    try:
        with nucleo.Trava(pasta):
            mudancas = parametros.plano(pasta, args.formato, valores, limpar)
    except nucleo.ErroJob as e:
        return _erro_job('parametros-entrega', pasta, e)
    except parametros.ErroParametros as e:
        return _recusa_parametros(pasta, e)
    if not mudancas:
        return Resultado(comando='parametros-entrega', situacao='ok', pasta_job=pasta, contagens={'campos_mudados': 0},
                         o_que_fazer='Nada mudou: parametros/entrega.json já tem esses valores.',
                         linhas_humanas=['Nada mudou no formato %s.' % args.formato])
    print('Parâmetros de entrega do formato %s (antes -> depois):' % args.formato)
    for campo, (antes, depois) in mudancas.items():
        print('  %s: %s -> %s' % (campo, _texto_do_valor(antes), _texto_do_valor(depois)))
    if not perguntar('Gravar %d mudança(s) em parametros/entrega.json? Digite sim para gravar: ' % len(mudancas)):
        return Resultado(comando='parametros-entrega', codigo=int(Codigo.RECUSADO), situacao='recusado', pasta_job=pasta,
                         contagens={'recusa_gravacao_cancelada': 1},
                         o_que_fazer='O DA não confirmou. Nada foi gravado em parametros/entrega.json.',
                         linhas_humanas=['Gravação cancelada.'])
    try:
        with nucleo.Trava(pasta):
            # a pergunta roda sem a trava: confere de novo e so grava se nada mudou desde o que o DA viu
            if parametros.plano(pasta, args.formato, valores, limpar) != mudancas:
                return Resultado(comando='parametros-entrega', codigo=int(Codigo.RECUSADO), situacao='recusado',
                                 pasta_job=pasta, contagens={'recusa_mudou_durante_a_confirmacao': 1},
                                 o_que_fazer='parametros/entrega.json mudou durante a confirmação. Nada foi gravado: '
                                             'confirme de novo, com o arquivo de agora.',
                                 linhas_humanas=['O arquivo mudou durante a confirmação.'])
            parametros.gravar(pasta, args.formato, valores, limpar, disparo=disparo)
    except nucleo.ErroJob as e:
        return _erro_job('parametros-entrega', pasta, e)
    except parametros.ErroParametros as e:
        return _recusa_parametros(pasta, e)
    nucleo.registrar_evento(pasta, 'parametros_entrega_gravados', campos=sorted(mudancas))
    return Resultado(comando='parametros-entrega', situacao='ok', pasta_job=pasta,
                     contagens={'campos_mudados': len(mudancas)},
                     o_que_fazer='Os parâmetros estão em parametros/entrega.json. Quando a mudança muda o arquivo '
                                 'final (o giro e a borda sempre; a cor de achatamento só num master com transparência; '
                                 'a condição só quando troca o teto de peso que vale), a aprovação do formato cai: o '
                                 'DA aprova de novo com um clique na tela do desdobra, e a entrega dos arquivos '
                                 'finais chega no próximo marco do desdobra.',
                     linhas_humanas=['%d campo(s) gravado(s) no formato %s.' % (len(mudancas), args.formato)])


def _conferir_entrega(args):
    from desdobra.entrega import validar
    pasta = Path(args.job).resolve()
    if not (pasta / 'estado.json').is_file():
        return _sem_job('conferir-entrega', pasta)
    s = validar.conferir_entrega(pasta)
    cont = {'arquivos': s['arquivos'], 'conferem': s['conferem'], 'arquivos_de_fonte': s['arquivos_de_fonte']}
    cont.update({k: len(s[k]) for k in ('divergem', 'faltam', 'sobram', 'reprovado_em_aprovados',
                                        'aprovado_em_reprovados')})
    for motivo in (s['relatorio'], s['manifesto']):
        if motivo is not None:
            cont[motivo] = 1
    if s['ok']:
        return Resultado(comando='conferir-entrega', situacao='ok', pasta_job=pasta, contagens=cont,
                         o_que_fazer='entrega/ confere com o relatório da entrega.',
                         linhas_humanas=['%d arquivo(s) conferem com o relatório.' % s['conferem']])
    linhas = ['entrega/ não confere com o relatório:'] + (['  relatório: %s' % s['relatorio']] if s['relatorio'] else [])
    for k in ('divergem', 'faltam', 'sobram', 'reprovado_em_aprovados', 'aprovado_em_reprovados'):
        linhas += ['  %s: %s' % (k, x) for x in s[k]]
    if s['arquivos_de_fonte']:
        linhas.append('  arquivos de fonte em entrega/: %d' % s['arquivos_de_fonte'])
    if s['manifesto']:
        linhas.append('  manifesto-licenca.json: %s' % s['manifesto'])
    return Resultado(comando='conferir-entrega', codigo=int(Codigo.RECUSADO), situacao='recusado', pasta_job=pasta,
                     contagens=cont, linhas_humanas=linhas,
                     o_que_fazer='entrega/ mudou depois da entrega ou não foi gravada pelo motor, e a entrega precisa '
                                 'ser feita de novo pelo DA. A entrega dos arquivos finais chega no próximo marco do '
                                 'desdobra; por enquanto, o job termina na aprovação de cada formato, na tela.')
