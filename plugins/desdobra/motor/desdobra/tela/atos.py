# -*- coding: utf-8 -*-
"""Os atos do passo 1 da tela, "O que eu li" (M7a, fatia 2; decisoes-v1.md, 159 e 170; proposta do M7, 163 e 166).

Cada ato e um botao da tela que pede a confirmacao do DA na propria janela (desdobra.tela.servidor.Ato): o servidor
confere os dados antes do dialogo (validar), monta o texto do dialogo com o que sera gravado (texto) e, so depois do
"Confirmar", grava com o Disparo da tela (meio tela; no modo de teste, meio medicao e origem fixture_de_teste):
  - modo_dados: a escolha do modo de dados do job (desdobra.job.modo_dados), so entre as opcoes dentro do teto da
    agencia, conferido de novo na gravacao; depois de gravar, refaz os dois pacotes do Claude no modo efetivo
    (desdobra.sugestao.pacote.refazer_pacotes; M7c, S2);
  - linkado: o arquivo de entrada/campanha/ que vale para um smart object linkado, so entre os candidatos que o leitor
    propos para ele (desdobra.render.linkados.confirmar);
  - spec_valor: confirmar um valor de spec em rascunho, ou escolher a leitura de um campo com fontes divergentes, so
    entre as pendencias do rascunho gravado (desdobra.specs.confirmar.confirmar_da_tela);
  - spec_valores (0.9.6): os valores de spec que o DA marcou no passo 1, de uma vez, com uma janela que lista cada
    um; uma acao 'confirmar' por valor, igual a do spec_valor (desdobra.specs.confirmar.confirmar_lote_da_tela). O
    divergente e o formato com duas medidas ficam fora do lote;
  - render: o render dos formatos afetados, com uma confirmacao e um selo por formato (desdobra.tela.ato_render; M7b,
    B2);
  - aprovar: a aprovacao dos formatos marcados, com o arquivo final de cada um na janela e o sentido do giro que falta
    gravado pela mesma confirmacao (desdobra.tela.ato_aprovar; M7b, B4);
  - marca: a marca do job, entre as marcas da biblioteca da agencia, a "Marca nova" e "Sem marca", opcional
    (desdobra.marca.job; M7c, M3; decisoes-v1.md, 190, Q5);
  - marca_registrar: guardar o padrao da marca no perfil da biblioteca da agencia, so com a marca escolhida e todos os
    formatos aprovados pelo DA (desdobra.marca.registrar; M7c, M5; decisoes-v1.md, 190, Q2);
  - texto_como_imagem: o DA nao tem o arquivo de uma fonte do PSD e decide usar o texto das camadas dela como imagem,
    ou desfaz a decisao (desdobra.fontes.como_imagem; 0.9.1);
  - formatos_digitados: sem folha de spec, o DA escreve a largura e a altura de cada formato em pixels, ou remove um
    formato da lista dele (desdobra.specs.digitados; 0.9.2).
Os textos sao do motor, em portugues para o DA, sem comando nem identificador; o que vem do cliente (nome de camada,
nome de arquivo, texto da folha) a pagina poe so por textContent.
"""
from pathlib import Path

MODOS = {
    # M7c, S4 (decisoes-v1.md, 190, Q7): o texto em pixel ou em forma vetorial o laudo nao ve, e o risco fica dito
    'a': ('Textos e miniaturas', 'O Claude recebe os nomes e os textos das camadas e miniaturas das imagens sem texto, '
                                 'para sugerir as funções. Uma letra desenhada em pixel ou em forma vetorial o '
                                 'desdobra não enxerga, e ela pode ir na imagem.'),
    'b': ('Sem imagens', 'O Claude recebe os nomes e os textos das camadas, sem nenhuma imagem.'),
    'c': ('Sem conteúdo', 'Nada do conteúdo do arquivo vai ao Claude. Ele recebe só contagens e medidas.'),
}
SIM = 'Confirmar'
NAO = 'Cancelar'


def _chaves(dados, *nomes):
    return isinstance(dados, dict) and set(dados) == set(nomes)


def _laudo(pasta):
    from desdobra import contratos
    try:
        return contratos.ler(Path(pasta) / 'laudo' / 'laudo.json', 'laudo/1')
    except (contratos.ErroContrato, OSError, ValueError):
        return None


def _linkado(pasta, dados):
    """O linkado do laudo e o candidato pedidos, ou None."""
    from desdobra.tela import estado
    if not _chaves(dados, 'unique_id', 'arquivo') or not all(isinstance(dados[k], str) for k in dados):
        return None
    laudo = _laudo(pasta)
    if laudo is None:
        return None
    for lk in estado.linkados_na_tela(pasta, laudo):
        if lk['unique_id'] == dados['unique_id']:
            cand = next((c for c in lk['candidatos'] if c['arquivo'] == dados['arquivo']), None)
            return (lk, cand) if cand is not None else None
    return None


def _spec(pasta, dados):
    """A pendencia de spec pedida, ou None. O divergente pede a leitura; o rascunho nao aceita leitura."""
    from desdobra.tela import estado
    if not isinstance(dados, dict) or not isinstance(dados.get('valor_id'), str):
        return None
    if set(dados) not in ({'valor_id'}, {'valor_id', 'leitura'}):
        return None
    alvo = next((x for x in estado.specs_pendentes(pasta) if x['valor_id'] == dados['valor_id']), None)
    if alvo is None:
        return None
    leitura = dados.get('leitura')
    if alvo['leituras']:
        if not isinstance(leitura, int) or isinstance(leitura, bool) or not 0 <= leitura < len(alvo['leituras']):
            return None
    elif 'leitura' in dados:
        return None
    return alvo


LOTE_MAX = 500  # numero-neutro: valores de spec num lote (a folha maior dos testes tem 20)


def _lote_de_spec(pasta, dados):
    """0.9.6: os valores pedidos no lote do passo 1, na ordem do pedido, ou None. dados: {'valor_ids': [ids]}, sem
    repeticao, cada um pendente, simples (sem leituras a escolher) e fora do formato com duas medidas (em_lote)."""
    from desdobra.tela import estado
    if not isinstance(dados, dict) or set(dados) != {'valor_ids'}:
        return None
    ids = dados['valor_ids']
    if not isinstance(ids, list) or not ids or len(ids) > LOTE_MAX or \
            not all(isinstance(i, str) for i in ids) or len(set(ids)) != len(ids):
        return None
    por_id = {x['valor_id']: x for x in estado.specs_pendentes(pasta)}
    alvos = [por_id.get(i) for i in ids]
    if any(a is None or not a.get('em_lote') for a in alvos):
        return None
    return alvos


def atos_do_job(pasta, teto=None, conteudo=None):
    """{nome: Ato} do passo 1 para o servidor da tela do job. teto: o teto do modo de dados da linha de comando (o do
    estado.json entra sozinho, lido a cada pedido). conteudo: o da tela (desdobra.tela.estado.montar); com ele entram
    os atos de confirmar a familia e de salvar (_ato_da_familia e _ato_de_salvar), que leem as familias dele a cada
    pedido."""
    from desdobra.job import modo_dados
    from desdobra.render import linkados
    from desdobra.specs import confirmar
    from desdobra.tela import ato_aprovar, ato_render
    from desdobra.tela.servidor import Ato
    pasta = Path(pasta).resolve()

    def teto_agora():
        return modo_dados.teto_do_job(pasta, teto)

    def modo_valido(d):
        return _chaves(d, 'modo') and isinstance(d['modo'], str) and d['modo'] in modo_dados.opcoes(teto_agora())

    def modo_texto(d):
        nome, explica = MODOS[d['modo']]
        return 'O job passa a usar o modo "%s". %s Você pode trocar o modo aqui mesmo, depois.' % (nome, explica)

    def modo_executar(disparo, d):
        from desdobra.sugestao import pacote
        gravado = modo_dados.gravar(pasta, d['modo'], disparo=disparo, teto_=teto_agora())
        # M7c, S2: os dois pacotes do Claude e a pasta das miniaturas seguem o modo efetivo de agora; no modo c saem
        # tambem as sugestoes dele. Na falha, o Claude fica sem nada para ler (conferir_modo fecha)
        try:
            pacote.refazer_pacotes(pasta, teto=teto_agora())
        except Exception:  # noqa: BLE001 - a escolha do DA ja esta gravada; o pacote nunca fica mais aberto que ela
            pacote.conferir_modo(pasta, teto_agora())
        return {'modo': gravado['valor']}

    def linkado_texto(d):
        lk, cand = _linkado(pasta, d)
        return 'O arquivo %s passa a valer para o linkado %s.' % (cand['nome'], lk['nome'] or 'sem nome')

    def linkado_executar(disparo, d):
        from desdobra import humano
        try:
            linkados.confirmar(pasta, d['unique_id'], d['arquivo'], disparo=disparo)
        finally:
            humano.conferir(disparo, 'linkado confirmar', consumir=True)  # o Disparo da tela vale um ato so
        return {'linkado': True}

    def spec_texto(d):
        alvo = _spec(pasta, d)
        if alvo['leituras']:
            lei = alvo['leituras'][d['leitura']]
            return 'No %s, o campo %s passa a valer %s, como está nesta folha.' % (
                alvo['na_frase'], alvo['campo'], lei['descricao'])
        return 'No %s, o campo %s passa a valer %s.' % (alvo['na_frase'], alvo['campo'], alvo['descricao'])

    def spec_executar(disparo, d):
        acao = confirmar.confirmar_da_tela(pasta, d['valor_id'], d.get('leitura'), disparo=disparo)
        return {'spec': acao is not None}

    def lote_texto(d):
        alvos = _lote_de_spec(pasta, d)
        n = len(alvos)
        # os formatos ficam so na lista da janela (revisao adversarial da 0.9.6): a frase nao os repete
        return ('Você confirma %s de spec, como %s nas folhas.'
                % ('1 valor' if n == 1 else '%d valores' % n, 'está' if n == 1 else 'estão'))

    def lote_executar(disparo, d):
        acoes = confirmar.confirmar_lote_da_tela(pasta, d['valor_ids'], disparo=disparo)
        return {'spec': acoes is not None, 'confirmados': len(acoes or [])}

    atos = {'marca': _ato_da_marca(pasta, conteudo), 'marca_registrar': _ato_de_registrar(pasta, conteudo),
            'texto_como_imagem': _ato_texto_como_imagem(pasta),
            'formatos_digitados': _ato_formatos_digitados(pasta)}
    if conteudo is not None:
        # as familias sao lidas do conteudo a cada pedido: no job novo elas nascem depois do passo 2, quando o servidor
        # monta o passo 3 de novo no mesmo dicionario (desdobra.tela.servidor, _atualizar)
        atos['familia'] = _ato_da_familia(pasta, conteudo)
        atos['salvar'] = _ato_de_salvar(pasta, conteudo)
    return dict(atos, **{
        'modo_dados': Ato(comando=modo_dados.ESCOLHER, titulo='Escolher o modo de dados', texto=modo_texto, sim=SIM,
                          nao=NAO, executar=modo_executar, validar=modo_valido),
        'linkado': Ato(comando='linkado confirmar', titulo='Confirmar o arquivo do linkado', texto=linkado_texto,
                       sim=SIM, nao=NAO, executar=linkado_executar,
                       validar=lambda d: _linkado(pasta, d) is not None),
        'spec_valor': Ato(comando=confirmar.COMANDO, titulo='Confirmar o valor da spec', texto=spec_texto, sim=SIM,
                          nao=NAO, executar=spec_executar, validar=lambda d: _spec(pasta, d) is not None),
        # 0.9.6: os valores de spec marcados pelo DA, de uma vez (uma janela, uma acao por valor)
        'spec_valores': Ato(comando=confirmar.COMANDO, titulo='Confirmar os valores de spec', texto=lote_texto,
                            sim=SIM, nao=NAO, executar=lote_executar,
                            validar=lambda d: _lote_de_spec(pasta, d) is not None),
        # o render dos formatos afetados (M7b, B2): ato longo, com preparo e um selo por formato
        'render': ato_render.ato_de_render(pasta),
        # a aprovacao dos formatos marcados, com o sentido do giro que falta (M7b, B4): ato longo, com preparo
        'aprovar': ato_aprovar.ato_de_aprovar(pasta),
    })


def _ato_texto_como_imagem(pasta):
    """O ato "texto_como_imagem" do passo 1 (0.9.1): o DA nao tem o arquivo de uma fonte do PSD e decide usar o texto
    das camadas dela como imagem, pelos pixels do PSD (desdobra.fontes.como_imagem). Dados: {'nome_ps', 'acao'}, com
    acao 'declarar' (so a face que falta agora, com os pixels de toda camada atingida) ou 'desfazer' (so a face
    declarada). O dialogo diz quantas camadas mudam e o efeito; a pagina mostra o nome de cada uma so por textContent."""
    from desdobra.fontes import como_imagem
    from desdobra.tela.servidor import Ato

    def alvo(d):
        if not _chaves(d, 'nome_ps', 'acao') or not isinstance(d['nome_ps'], str) or d['acao'] not in como_imagem.ACOES:
            return None
        if d['acao'] == 'declarar':
            return next((x for x in como_imagem.declaraveis(pasta) if x['nome_ps'] == d['nome_ps'] and x['declaravel']),
                        None)
        return {'nome_ps': d['nome_ps'], 'camadas': []} if como_imagem.declarada(pasta, d['nome_ps']) else None

    def quantas(n):
        return 'A camada que usa' if n == 1 else 'As %d camadas que usam' % n

    def texto(d):
        a = alvo(d)
        if d['acao'] == 'declarar':
            n = len(a['camadas'])
            falta = ('O arquivo da fonte %s não confere com o PSD.' if a.get('com_arquivo') else
                     'A fonte %s não tem arquivo no job.') % d['nome_ps']
            return ('%s %s esta fonte %s pelos pixels do PSD: %s como imagem, sem editar o texto nem quebrar linha na '
                    'tela. Se chegar o arquivo da fonte que confere, o texto volta a ser texto vivo. Você pode desfazer '
                    'aqui mesmo, depois.'
                    % (falta, quantas(n), 'vai' if n == 1 else 'vão', 'escala' if n == 1 else 'escalam'))
        if d['nome_ps'] in ((como_imagem.bloco(pasta) or {}).get('caidas') or []):
            # revisao do 0.9.1: o arquivo que confere ja chegou, e a declaracao so sai do registro
            return ('O arquivo da fonte %s já chegou e confere, e o texto já é texto vivo. A sua decisão de usar o '
                    'texto como imagem sai do registro do job, e nada muda nas peças.' % d['nome_ps'])
        return ('As camadas com a fonte %s voltam a esperar o arquivo da fonte, e o job fica parado nesse ponto até ele '
                'chegar ou até você decidir de novo.' % d['nome_ps'])

    def executar(disparo, d):
        como_imagem.gravar(pasta, d['nome_ps'], d['acao'], disparo=disparo)
        return {'texto_como_imagem': d['acao']}
    return Ato(comando=como_imagem.COMANDO, titulo='Texto como imagem', texto=texto, sim=SIM, nao=NAO,
               executar=executar, validar=lambda d: alvo(d) is not None)


def _ato_formatos_digitados(pasta):
    """O ato "formatos_digitados" do passo 1 (0.9.2): sem folha de spec, o DA escreve a largura e a altura de cada
    formato em pixels, um ou varios de uma vez, ou remove um da lista (desdobra.specs.digitados). Dados: {'acao':
    'acrescentar', 'texto'} ou {'acao': 'remover', 'largura', 'altura'}. O motor confere no pedido e no Confirmar; o
    dialogo diz as medidas como o motor as leu."""
    from desdobra.specs import digitados
    from desdobra.tela.servidor import Ato

    def texto(d):
        if d['acao'] == 'acrescentar':
            medidas = digitados.interpretar(d['texto'])[0]
            frase = digitados.frase_das_medidas(medidas)
            if len(medidas) == 1:
                return ('O formato %s entra no job como você digitou, sem folha de spec. Ele aparece em Formatos e '
                        'giro, e as famílias passam a contar com ele. Você pode remover o formato aqui mesmo, depois.'
                        % frase)
            return ('Os %d formatos %s entram no job como você digitou, sem folha de spec. Eles aparecem em Formatos e '
                    'giro, e as famílias passam a contar com eles. Você pode remover cada formato aqui mesmo, depois.'
                    % (len(medidas), frase))
        medida = (d['largura'], d['altura'])
        nome = digitados.medida_na_tela(*medida)
        if medida in digitados.medidas_da_folha(digitados.rascunho_gravado(pasta)):
            return ('O formato %s sai da sua lista. Nada muda nas peças, porque a folha de spec já traz este formato.'
                    % nome)
        return ('O formato %s sai do job. Se ele estava numa família já confirmada, a família volta a pedir a sua '
                'confirmação.' % nome)

    def executar(disparo, d):
        gravado = digitados.gravar(pasta, d, disparo=disparo)
        return {'formatos_digitados': d['acao'], 'n': len(gravado['formatos'])}
    return Ato(comando=digitados.COMANDO, titulo='Formatos digitados', texto=texto, sim=SIM, nao=NAO,
               executar=executar, validar=lambda d: digitados.conferir(pasta, d) is None)


MARCA_TROCA = 'Você pode trocar a marca aqui mesmo, depois.'


def _ato_da_marca(pasta, conteudo):
    """O ato "marca" do passo 1 (M7c, M3; decisoes-v1.md, 190, Q5): uma marca da biblioteca da agencia, a "Marca nova"
    com o nome que o DA digitou ou "Sem marca", com a confirmacao na janela (desdobra.marca.job). A pasta da
    biblioteca e a do conteudo da montagem (pasta_biblioteca, so no processo de fundo), lida a cada pedido; sem ela, so
    "Sem marca" passa."""
    from desdobra.marca import job as marca_job
    from desdobra.tela.servidor import Ato

    def biblioteca():
        return (conteudo or {}).get('pasta_biblioteca')

    def texto(d):
        e = marca_job.conferir(d, biblioteca())
        if e['escolha'] == 'sem_marca':
            return 'O job segue sem marca, e nenhum padrão de marca aparece como sugestão. ' + MARCA_TROCA
        if e['escolha'] == 'nova':
            return ('A marca "%s" entra na biblioteca da agência, ainda sem padrão guardado, e o job passa a ser '
                    'dela. %s' % (e['nome'], MARCA_TROCA))
        return ('O job passa a ser da marca "%s". O padrão que ela tiver aparece como sugestão, e nada muda sem o seu '
                'clique. %s' % (e['nome'], MARCA_TROCA))

    def executar(disparo, d):
        reg = marca_job.gravar(pasta, d, disparo=disparo, biblioteca=biblioteca())
        return {'marca': reg['escolha']}
    return Ato(comando=marca_job.COMANDO, titulo='Escolher a marca do job', texto=texto, sim=SIM, nao=NAO,
               executar=executar, validar=lambda d: marca_job.conferir(d, biblioteca()) is not None)


REGISTRAR_SIM = 'Guardar o padrão'


def _ato_de_registrar(pasta, conteudo):
    """O ato "marca_registrar" (M7c, M5; decisoes-v1.md, 190, Q1 a Q3): o botao "A campanha foi aprovada: guardar o
    padrao desta marca", que a pagina mostra so com lido.marca.registro.pode (desdobra.marca.registrar.na_tela). Os
    dados sao {'impressao': <a do registro que a janela mostra>}: o registro que mudou depois que a pagina montou a
    janela e recusado antes do dialogo, e de novo no Confirmar. A pasta da biblioteca e a do conteudo da montagem,
    lida a cada pedido, como no ato da marca."""
    from desdobra.marca import registrar
    from desdobra.tela.servidor import Ato

    def biblioteca():
        return (conteudo or {}).get('pasta_biblioteca')

    def valido(d):
        if not _chaves(d, 'impressao') or not isinstance(d['impressao'], str):
            return False
        v = registrar.na_tela(pasta, biblioteca())
        return v['pode'] is True and v['impressao'] == d['impressao']

    def texto(_d):
        v = registrar.na_tela(pasta, biblioteca())
        anterior = ('' if not v['versao_atual'] else
                    ' A versão %d continua guardada no histórico da marca.' % v['versao_atual'])
        return ('A campanha aprovada vira a versão %d do padrão da marca "%s": as regras de escala e as âncoras que '
                'você confirmou, cada uma com o job de origem, e o nome das faces usadas.%s Nos próximos jobs desta '
                'marca, o padrão aparece como sugestão, e nada muda sem o seu clique.'
                % (v['versao_nova'], v['nome'], anterior))

    def executar(disparo, d):
        return registrar.gravar(pasta, disparo=disparo, biblioteca=biblioteca(), impressao=d['impressao'])
    return Ato(comando=registrar.COMANDO, titulo='Guardar o padrão desta marca', texto=texto, sim=REGISTRAR_SIM,
               nao=NAO, executar=executar, validar=valido)


def _ato_da_familia(pasta, conteudo):
    """O ato "Confirmar familia" (decisoes-v1.md, 167): um clique, com a confirmacao na janela, confirma a familia
    inteira como a tela mostra, com a versao escolhida e as edicoes do rascunho. As familias ({id: {'formatos',
    'versoes'}}) sao as do conteudo da tela agora (desdobra.tela.estado.montar). A familia com quebra de linha
    proposta pelo desdobra e ainda nao aprovada e recusada antes do dialogo (M7b, C4). O pedido leva as quebras de
    linha que a janela mostra, como leva as edicoes (a quebra e edicao da familia, decisoes-v1.md, 171): sem o campo,
    a janela nao mostra quebra (revisao do C)."""
    from desdobra.tela import rascunho
    from desdobra.tela.servidor import Ato

    def valido(d):
        familias = conteudo.get('familias') or {}
        if not (_chaves(d, 'familia', 'versao', 'edicoes') or _chaves(d, 'familia', 'versao', 'edicoes', 'quebras')) \
                or not isinstance(d['familia'], str) or d['familia'] not in familias:
            return False
        if familias[d['familia']].get('por_confirmar'):
            # um formato da familia tem valor de spec a espera do DA, sem galeria: a confirmacao seria as cegas
            # (revisao da correcao dos becos)
            return False
        versoes = familias[d['familia']]['versoes']
        if d['versao'] is None:
            if versoes:
                return False
        elif not isinstance(d['versao'], str) or d['versao'] not in versoes:
            return False
        if rascunho.por_aprovar({'quebras': rascunho.quebras_gravadas(pasta, d['familia'])}):
            # a quebra de linha que o desdobra propos espera o clique "Aprovar quebra" do DA (M7b, C4)
            return False
        # as edicoes, as quebras de linha e a versao que a janela mostra sao as do rascunho gravado: a versao vale so
        # depois do clique do DA na galeria, que a grava no rascunho (revisao do M7a); a quebra que a gravacao nao
        # levou nunca e confirmada as cegas (revisao do C). A versao gravada que a galeria nao tem mais (o rascunho da
        # tela de antes da previa igual ao Salvar, M7b) conta como nenhuma, como a pagina mostra a familia
        return rascunho.edicoes_gravadas(pasta, d['familia']) == d['edicoes'] and \
            rascunho.quebras_gravadas(pasta, d['familia']) == d.get('quebras', []) and \
            rascunho.versao_de_agora(rascunho.versao_gravada(pasta, d['familia']), versoes) == d['versao']

    def ordem_da_versao(d):
        familias = conteudo.get('familias') or {}
        # o numero da versao como a galeria da tela mostra (revisao do M7a: o dialogo diz qual versao fica)
        for fid in familias[d['familia']]['formatos']:
            gal = ((conteudo.get('previas') or {}).get(fid) or {}).get('galeria') or {}
            v = next((x for x in gal.get('variantes') or [] if x.get('id') == d['versao']), None)
            if v is not None:
                return v.get('ordem')
        return None

    def texto(d):
        n = len(conteudo['familias'][d['familia']]['formatos'])
        quantas = 'O arquivo desta família fica confirmado' if n == 1 else \
            'Os %d arquivos desta família ficam confirmados' % n
        ordem = ordem_da_versao(d) if d['versao'] is not None else None
        na = ' na versão %s' % ordem if ordem is not None else ''
        return ('%s%s, como a tela mostra agora, com as suas edições. Se você mexer de novo nesta família, ela volta '
                'a pedir a sua confirmação.' % (quantas, na))

    def executar(disparo, d):
        f = rascunho.confirmar_familia(pasta, d['familia'], d['versao'], disparo=disparo,
                                       job_id=conteudo['estado'].get('job_id'),
                                       laudo_atual=rascunho.laudo_sha256(pasta), edicoes=d['edicoes'],
                                       quebras=d.get('quebras', []),
                                       formatos=conteudo['familias'][d['familia']]['formatos'],
                                       pecas=conteudo['familias'][d['familia']].get('pecas'),
                                       versoes=conteudo['familias'][d['familia']]['versoes'])
        return {'familia': d['familia'], 'confirmada': f['confirmada']}
    return Ato(comando=rascunho.COMANDO_FAMILIA, titulo='Confirmar a família', texto=texto, sim=SIM, nao=NAO,
               executar=executar, validar=valido)


# revisao 0.9.3: o motivo da recusa do "Salvar e seguir", em portugues para o DA, na ordem do que ele resolve primeiro
MOTIVO_RASCUNHO_GRAVANDO = ('As suas últimas escolhas ainda estão sendo salvas no rascunho. Espere o selo dizer Salvo '
                            'no rascunho e clique de novo em Salvar e seguir.')
SEM_FAMILIAS = 'As famílias ainda não foram montadas. '
MOTIVOS_DO_SALVAR = {
    'sem_rascunho': MOTIVO_RASCUNHO_GRAVANDO,
    'modo_dados_sem_escolha': 'Escolha o modo de dados no passo 1.',
    'sem_formatos': 'O job ainda não tem formato com medida em pixels. Veja Valores de spec, no passo 1.',
    'formato_sem_medida': 'Um formato da folha tem duas medidas e espera a sua escolha em Valores de spec, no passo 1.',
    'rotacao_sem_escolha': 'Escolha o giro de cada formato no passo 1.',
    'padrao_marca_desatualizado': ('O padrão da marca mudou depois do seu clique. No Design system, use o padrão de '
                                   'novo ou clique de novo no valor que quer manter.'),
    'formato_com_spec_por_confirmar': ('Um formato de uma família espera a confirmação de um valor de spec. Confirme '
                                       'os valores dele em Valores de spec, no passo 1, e depois confirme a família.'),
    'versao_que_a_familia_nao_tem': ('Uma família foi confirmada numa versão que ela não tem mais. Nas Famílias, '
                                     'escolha a versão e confirme a família de novo.'),
    'edicao_invalida': ('Uma edição feita numa família não vale mais com as escolhas de agora. Nas Famílias, confira as '
                        'edições e confirme a família de novo.'),
    'texto_sem_caractere': ('Um texto editado numa família usa uma letra que a fonte do job não tem. Nas Famílias, '
                            'troque a letra e confirme a família de novo.'),
    'briefing_invalido': ('As suas escolhas não formam um briefing que o desdobra consiga gravar. Peça ajuda ao Claude '
                          'e diga qual foi o seu último clique.'),
}
ORDEM_DO_SALVAR = ('rascunho_de_outro_laudo', 'sem_rascunho', 'modo_dados_sem_escolha', 'sem_formatos',
                   'formato_sem_medida', 'rotacao_sem_escolha', 'briefing_com_problema', 'padrao_marca_desatualizado',
                   'formato_com_spec_por_confirmar', 'familia_sem_confirmacao', 'versao_que_a_familia_nao_tem',
                   'edicao_invalida', 'texto_sem_caractere', 'briefing_invalido')


def motivo_sem_familias(conteudo):
    """O motivo do "Salvar e seguir" sem familia nenhuma: o da espera das Familias, como o servidor a monta."""
    from desdobra.tela import estado
    p3 = (conteudo.get('estado') or {}).get('passo_3') or {}
    m = p3.get('motivo') or {}
    return SEM_FAMILIAS + (m.get('texto') or p3.get('texto') or estado.AGUARDA_PASSO_2)


def motivo_do_salvar(pend, detalhes=None):
    """O texto da recusa do "Salvar e seguir" para o DA, pela primeira pendencia (salvar.pendencias) na ordem do que
    ele resolve primeiro. detalhes: o briefing montado e os erros inteiros da conferencia, para dizer as camadas."""
    from desdobra.tela import servidor
    from desdobra.tela import estado
    detalhes = detalhes or {}
    codigos = {p['codigo'] for p in pend}
    for codigo in ORDEM_DO_SALVAR + tuple(sorted(codigos - set(ORDEM_DO_SALVAR))):
        if codigo not in codigos:
            continue
        if codigo == 'rascunho_de_outro_laudo':
            return servidor.MOTIVO_PSD_RELIDO
        if codigo == 'familia_sem_confirmacao':
            n = sum(1 for p in pend if p['codigo'] == codigo)
            return 'Falta confirmar 1 família para salvar.' if n == 1 else \
                'Falta confirmar %d famílias para salvar.' % n
        if codigo == 'briefing_com_problema':
            m = None
            if detalhes.get('erros') is not None and detalhes.get('laudo') is not None:
                try:
                    from desdobra.briefing import modelo as mb
                    resolvidas = mb.resolver(detalhes['laudo'], detalhes['briefing'])[0]
                except (KeyError, TypeError, ValueError):
                    resolvidas = {}
                m = estado.motivo_da_conferencia(detalhes['erros'], detalhes['laudo'], resolvidas)
            return m['texto'] if m else estado.AGUARDA_CONFERENCIA
        if codigo in MOTIVOS_DO_SALVAR:
            return MOTIVOS_DO_SALVAR[codigo]
    return MOTIVOS_DO_SALVAR['briefing_invalido']


def _ato_de_salvar(pasta, conteudo):
    """O ato "Salvar e seguir" (decisoes-v1.md, 167): com todas as familias confirmadas, grava o briefing confirmado e
    deriva os formatos (desdobra.briefing.salvar, o mesmo gravador do "briefing confirmar" do terminal). O servidor
    recusa antes do dialogo quando falta alguma coisa (salvar.pendencias)."""
    from desdobra.briefing import salvar
    from desdobra.tela import rascunho
    from desdobra.tela.servidor import Ato

    def valido(d):
        # a pagina manda o rascunho como a janela o mostra; ele tem de ser o gravado (revisao do M7a). Sem familia
        # (o passo 3 ainda espera o passo 2), nada e salvo. Revisao 0.9.3: a recusa que o DA resolve leva o motivo
        # em portugues (servidor.Recusa), e a pagina o mostra ao lado do botao
        from desdobra.tela.servidor import Recusa
        if not _chaves(d, 'rascunho') or not isinstance(d['rascunho'], dict):
            return False
        if not conteudo.get('familias'):
            return Recusa(motivo_sem_familias(conteudo))
        if not rascunho.mesma_vista(pasta, d['rascunho']):
            return Recusa(MOTIVO_RASCUNHO_GRAVANDO)
        detalhes = {}
        pend = salvar.pendencias(pasta, conteudo, detalhes=detalhes)
        return Recusa(motivo_do_salvar(pend, detalhes)) if pend else True

    def texto(_d):
        n = len(conteudo['familias'])
        quantas = 'a família confirmada' if n == 1 else 'as %d famílias confirmadas' % n
        laudo = _laudo(pasta) or {}
        quadros = bool((laudo.get('documento') or {}).get('quadros'))
        quantas += ', a prancheta da peça' if quadros else ''
        return ('O briefing do job fica salvo com %s, o giro de cada formato, as funções e o design system que você '
                'escolheu. O desdobra refaz cada formato a partir dele, e a versão anterior do briefing fica guardada.'
                % quantas)

    def executar(disparo, _d):
        r = salvar.salvar(pasta, conteudo, disparo)
        # 0.9.6: a tela diz quando a derivacao nao gravou o layout (nunca "salvo" calado) e quais formatos ficaram
        # sem layout, pela medida
        nomes = {f['id']: '%sx%s' % (f.get('largura'), f.get('altura'))
                 for f in (r.get('briefing') or {}).get('formatos') or []}
        return {'salvo': True, 'derivado': r['derivado'],
                'sem_layout': [nomes.get(fid, fid) for fid in r.get('sem_layout') or []]}
    return Ato(comando=salvar.COMANDO, titulo='Salvar o briefing', texto=texto, sim=SIM, nao=NAO, executar=executar,
               validar=valido)
