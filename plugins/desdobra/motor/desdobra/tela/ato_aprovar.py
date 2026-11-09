# -*- coding: utf-8 -*-
"""O ato de aprovar da tela (M7b, passo B4 do plano e a critica dele; decisoes do Duda Q2, Q11 e Q13).

O DA marca os formatos que quer aprovar e clica em Aprovar, com uma confirmacao so na janela:
  - validar (no fio do pedido, barato): os dados sao {'formatos': [ids]} ou {'formatos': [ids], 'sentidos': {id:
    sentido}}: uma lista sem repeticao de formatos do briefing e, para os formatos marcados, o sentido do giro que o DA
    escolheu na janela (horario ou anti_horario);
  - preparar (desdobra.tela.servidor.Ato.preparar: tarefa no fio de trabalho, com a trava do job): o formato que gira
    90 ou 270 graus sem sentido gravado em parametros/entrega.json e sem sentido no pedido para o preparo
    (falta_sentido), com as opcoes que a janela mostra e o tamanho da peca antes do giro (composicao, para a figura);
    o sentido gravado que o briefing corrigiu depois conta como falta (so o do briefing e oferecido, e a confirmacao
    troca o gravado; revisao do M7b, fase B), e o gravado pelo modo de teste num job com decisao do DA tambem (segunda
    revisao). O sentido pedido para formato que nao gira, que ja tem sentido gravado em
    dia ou que o briefing recusa (parametros.conferir) tambem para (sentido_recusado). Senao, o portao do aprovar
    roda em cada formato (desdobra.entrega.nucleo_aprovar.conferir, com o arquivo final ja girado no sentido pedido);
    formato com falha para o preparo (formato_com_falha), sem dialogo. Com todos certos, a previa vai para
    entrega/previa/, o servidor mostra o arquivo final de cada formato na janela (/final/<formato>) e o texto da
    confirmacao diz os formatos e o lado de cada giro. O que o DA viu (nucleo_aprovar.vista) fica so no pedido
    pendente;
  - executar (o Confirmar: Ato.longo, com o Disparo do aprovar e, quando ha sentido pedido, o do parametros-entrega da
    mesma confirmacao, Ato.outros_comandos): na tarefa, com a trava do job, o nucleo confere tudo de novo
    (nucleo_aprovar.confirmar). Mudou: nada e gravado (mudou_durante_a_confirmacao). O Cancelar do DA vale ate a
    conferencia acabar: depois dela, nada e gravado se ele chegou; senao, o sentido do giro e gravado
    em parametros/entrega.json (parametros.gravar_formatos, o mesmo gravador do terminal) e a aprovacao de cada formato
    em briefing/aprovacao.json, com o meio e a origem do Disparo da tela (no modo de teste, meio medicao e origem
    fixture_de_teste, que o portao da entrega recusa).
A aprovacao e por formato (Q11): o DA aprova so os marcados, e os registros dos outros ficam. Mudar o que alimenta o
formato, o render, o contrato ou o arquivo final derruba a aprovacao dele (Q2; desdobra.entrega.aprovacao). O botao de
entregar fica para o M8 (Q13). Os textos sao do motor, sem comando, sem nome de arquivo e sem codigo; o formato aparece
pela medida dele.
"""
from pathlib import Path

from desdobra.tela import ato_render, tarefas

COMANDO = 'aprovar'
COMANDO_SENTIDO = 'parametros-entrega'
TITULO = 'Aprovar os arquivos finais'
SIM = 'Confirmar'
NAO = 'Cancelar'
MOTIVO_FALHA = 'formato_com_falha'
MOTIVO_SEM_SENTIDO = 'falta_sentido'
MOTIVO_SENTIDO_RECUSADO = 'sentido_recusado'
MOTIVO_MUDOU = 'mudou_durante_a_confirmacao'
ORDEM_DOS_SENTIDOS = ('horario', 'anti_horario')
# o lado do giro dito para o DA: a opcao da janela e o trecho do texto da confirmacao
SENTIDOS = {'horario': 'Para a direita, no sentido dos ponteiros do relógio',
            'anti_horario': 'Para a esquerda, no sentido contrário ao dos ponteiros do relógio'}
SENTIDOS_NO_TEXTO = {'horario': 'para a direita, no sentido dos ponteiros do relógio',
                     'anti_horario': 'para a esquerda, no sentido contrário ao dos ponteiros do relógio'}
CONFIRA = 'Confira cada arquivo final na janela antes de confirmar.'
QUEDA = 'Se o formato mudar depois, a aprovação dele cai.'


class ErroAtoAprovar(Exception):
    """O preparo ou a confirmacao nao seguiram. motivo: codigo curto (a tela mostra o texto do motor para ele);
    resposta: o que a tela mostra junto (os formatos com falha, os que pedem o sentido, os que mudaram)."""

    def __init__(self, mensagem, motivo, resposta=None):
        super().__init__(mensagem)
        self.motivo, self.resposta = motivo, resposta


def _lista(nomes):
    return nomes[0] if len(nomes) == 1 else '%s e %s' % (', '.join(nomes[:-1]), nomes[-1])


def texto_da_confirmacao(itens):
    """O texto do dialogo: os formatos aprovados, o lado do giro de cada formato girado e o aviso de que a aprovacao
    cai. itens: [{'nome', 'sentido'}], na ordem do pedido."""
    nomes = [i['nome'] for i in itens]
    if len(nomes) == 1:
        partes = ['O arquivo final do formato %s fica aprovado.' % nomes[0]]
    else:
        partes = ['Os arquivos finais dos formatos %s ficam aprovados.' % _lista(nomes)]
    for i in itens:
        if i.get('sentido') in SENTIDOS_NO_TEXTO:
            partes.append('O formato %s vai para o veículo girado %s.' % (i['nome'], SENTIDOS_NO_TEXTO[i['sentido']]))
    partes += [CONFIRA, QUEDA]
    return ' '.join(partes)


def _formatos_e_parametros(pasta):
    """({id: formato do briefing}, {id: parametros de entrega gravados}). Os parametros ilegiveis contam como vazios:
    o portao do formato recusa com o codigo dele."""
    from desdobra import contratos
    from desdobra.briefing import modelo as mb
    from desdobra.entrega import portao
    try:
        b = mb.ler(pasta)
    except (contratos.ErroContrato, OSError, ValueError):
        b = None
    try:
        params = portao.parametros_de_entrega(pasta)
    except (contratos.ErroContrato, OSError, ValueError):
        params = {}
    return {f['id']: f for f in (b or {}).get('formatos') or [] if isinstance(f, dict)}, params


def _sentido_gravado(params, fid):
    return ((params.get(fid) or {}).get('rotacao_sentido') or {}).get('valor')


def _gira(fmt):
    from desdobra.entrega import portao
    return ((fmt or {}).get('rotacao') or {}).get('graus') in portao.GRAUS_QUARTO_DE_VOLTA


def _velho(fmt, gravado):
    """O sentido gravado e o outro que o briefing diz agora (o portao recusaria: rotacao_sentido_divergente)."""
    do_brief = ((fmt or {}).get('rotacao') or {}).get('sentido')
    return do_brief is not None and do_brief != gravado


def _composicao(fmt):
    """[largura, altura] da peca antes do giro (o master), para a figura da janela do lado do giro."""
    from desdobra.derivacao import formatos as mod_formatos
    return list(mod_formatos.composicao(fmt))


def ato_de_aprovar(pasta):
    """O Ato "Aprovar os arquivos finais" do servidor da tela do job em `pasta`."""
    from desdobra.entrega import parametros
    from desdobra.tela.servidor import Ato
    pasta = Path(pasta).resolve()

    def valido(d):
        if not isinstance(d, dict) or set(d) not in ({'formatos'}, {'formatos', 'sentidos'}):
            return False
        fs = d['formatos']
        if not isinstance(fs, list) or not fs or not all(isinstance(f, str) for f in fs) or len(set(fs)) != len(fs):
            return False
        sentidos = d.get('sentidos', {})
        if not isinstance(sentidos, dict) or not set(sentidos) <= set(fs) or \
                not all(s in parametros.SENTIDOS for s in sentidos.values()):
            return False
        do_briefing = ato_render._formatos_do_briefing(pasta)
        return all(f in do_briefing for f in fs)

    def outros_comandos(d):
        return [COMANDO_SENTIDO] if d.get('sentidos') else []

    def preparar(d, tarefa):
        from desdobra.entrega import nucleo_aprovar
        from desdobra.tela import servidor
        nomes = ato_render._formatos_do_briefing(pasta)
        sentidos = dict(d.get('sentidos') or {})
        do_briefing, params = _formatos_e_parametros(pasta)
        # o job com decisao do DA (o mesmo criterio do painel, desdobra.tela.estado): o sentido gravado pelo modo de
        # teste nao vale para ele
        do_da = servidor._job_do_da(pasta)
        sem_sentido, recusados = [], []
        for f in d['formatos']:
            fmt, gravado = do_briefing.get(f), _sentido_gravado(params, f)
            # o sentido gravado que o briefing corrigiu depois (o giro mudou no passo 1) ficou velho, e o do modo de
            # teste num job do DA nunca chega a entrega: a janela pede o sentido de novo, e a mesma confirmacao troca o
            # gravado (revisao do M7b, fase B)
            pede = _gira(fmt) and (gravado is None or _velho(fmt, gravado) or
                                   (do_da and nucleo_aprovar.sentido_de_teste(params, f)))
            if f in sentidos:
                try:
                    if not pede:
                        raise parametros.ErroParametros('rotacao_sem_quarto_de_volta')
                    parametros.conferir(pasta, f, {'rotacao_sentido': sentidos[f]})
                except parametros.ErroParametros:
                    recusados.append({'id': f, 'nome': nomes.get(f, f)})
            elif pede:
                do_brief = fmt['rotacao'].get('sentido')
                opcoes = [do_brief] if do_brief in SENTIDOS else list(ORDEM_DOS_SENTIDOS)
                sem_sentido.append({'id': f, 'nome': nomes.get(f, f), 'graus': fmt['rotacao']['graus'],
                                    'sentido_do_briefing': do_brief, 'composicao': _composicao(fmt),
                                    'opcoes': [{'valor': s, 'texto': SENTIDOS[s]} for s in opcoes]})
        if recusados:
            raise ErroAtoAprovar('O sentido pedido nao serve.', MOTIVO_SENTIDO_RECUSADO, {'recusados': recusados})
        if sem_sentido:
            raise ErroAtoAprovar('Falta o sentido do giro.', MOTIVO_SEM_SENTIDO, {'sem_sentido': sem_sentido})
        conf = {'briefing': None, 'formatos': {}}
        for f in d['formatos']:
            if tarefa.parar():
                raise ErroAtoAprovar('O preparo foi parado.', tarefas.MOTIVO_PARADO)
            tarefa.progresso('portao', f)
            um = nucleo_aprovar.conferir(pasta, [f], sentidos={f: sentidos[f]} if f in sentidos else None)
            conf['formatos'].update(um['formatos'])
        falhas = nucleo_aprovar.com_falha(conf)
        if falhas:
            raise ErroAtoAprovar('Um formato tem falha no portao.', MOTIVO_FALHA, {'com_falha': [
                {'id': f, 'nome': nomes.get(f, f),
                 'codigos': sorted({x['codigo'] for x in conf['formatos'][f]['falhas']})} for f in falhas]})
        nucleo_aprovar.gravar_previas(pasta, conf)
        itens = []
        for f in d['formatos']:
            final = conf['formatos'][f]['final']
            sentido = sentidos.get(f) or (_sentido_gravado(params, f) if _gira(do_briefing.get(f)) else None)
            itens.append({'id': f, 'nome': nomes.get(f, f), 'sentido': sentido, 'extensao': final.extensao,
                          'bytes': len(final.dados)})
        return {'texto': texto_da_confirmacao(itens), 'vista': {'formatos': itens},
                'guardado': {'vista': nucleo_aprovar.vista(conf), 'sentidos': sentidos},
                'finais': {f: item['final'] for f, item in conf['formatos'].items()}}

    def executar(disparo, d, tarefa, preparado, outros):
        from desdobra.entrega import nucleo_aprovar, portao
        from desdobra.job import nucleo
        sentidos = dict(preparado['sentidos'])
        if tarefa.parar():
            raise ErroAtoAprovar('A aprovacao foi parada.', tarefas.MOTIVO_PARADO)
        tarefa.progresso('portao')

        def gravar_sentidos():
            # o ultimo ponto em que o Cancelar do DA vale, depois da conferencia de novo e antes da primeira gravacao:
            # cancelado aqui, nada e gravado (revisao do M7b, fase B). Daqui em diante a confirmacao grava tudo, e a
            # tarefa acaba "feita" mesmo com o Cancelar chegando no meio (desdobra.tela.tarefas)
            if tarefa.parar():
                raise ErroAtoAprovar('A aprovacao foi parada antes de gravar.', tarefas.MOTIVO_PARADO)
            # com a mesma confirmacao do DA, antes da aprovacao: o arquivo final que o portao acabou de conferir ja
            # saiu girado neste sentido
            tarefa.progresso('aprovacao')
            if not sentidos:
                return
            parametros.gravar_formatos(pasta, {f: ({'rotacao_sentido': s}, []) for f, s in sentidos.items()},
                                       disparo=outros[COMANDO_SENTIDO])
            gravados = portao.parametros_de_entrega(pasta)
            if any(_sentido_gravado(gravados, f) != s for f, s in sentidos.items()):
                raise ErroAtoAprovar('O sentido gravado nao e o pedido.', MOTIVO_MUDOU, {'mudaram': sorted(sentidos)})
            nucleo.registrar_evento(pasta, 'parametros_entrega_gravados', campos=['rotacao_sentido'],
                                    n_formatos=len(sentidos), meio=outros[COMANDO_SENTIDO].meio)
        try:
            regs = nucleo_aprovar.confirmar(pasta, d['formatos'], preparado['vista'], disparo,
                                            sentidos=sentidos or None, antes_de_gravar=gravar_sentidos)
        except nucleo_aprovar.ErroAprovar as e:
            raise ErroAtoAprovar(str(e), MOTIVO_MUDOU, {'mudaram': e.mudaram}) from None
        for r in regs:
            tarefa.feito(r['formato'])
        return {'aprovados': [r['formato'] for r in regs], 'sentidos': sentidos}

    return Ato(comando=COMANDO, titulo=TITULO, texto='', sim=SIM, nao=NAO, executar=executar, validar=valido,
               longo=True, formatos=lambda d: list(d['formatos']), preparar=preparar, outros_comandos=outros_comandos)
