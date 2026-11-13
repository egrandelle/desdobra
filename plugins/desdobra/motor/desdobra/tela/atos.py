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
  - render: o render dos formatos afetados, com uma confirmacao e um selo por formato (desdobra.tela.ato_render; M7b,
    B2);
  - aprovar: a aprovacao dos formatos marcados, com o arquivo final de cada um na janela e o sentido do giro que falta
    gravado pela mesma confirmacao (desdobra.tela.ato_aprovar; M7b, B4);
  - marca: a marca do job, entre as marcas da biblioteca da agencia, a "Marca nova" e "Sem marca", opcional
    (desdobra.marca.job; M7c, M3; decisoes-v1.md, 190, Q5).
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

    atos = {'marca': _ato_da_marca(pasta, conteudo)}
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
        # o render dos formatos afetados (M7b, B2): ato longo, com preparo e um selo por formato
        'render': ato_render.ato_de_render(pasta),
        # a aprovacao dos formatos marcados, com o sentido do giro que falta (M7b, B4): ato longo, com preparo
        'aprovar': ato_aprovar.ato_de_aprovar(pasta),
    })


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


def _ato_de_salvar(pasta, conteudo):
    """O ato "Salvar e seguir" (decisoes-v1.md, 167): com todas as familias confirmadas, grava o briefing confirmado e
    deriva os formatos (desdobra.briefing.salvar, o mesmo gravador do "briefing confirmar" do terminal). O servidor
    recusa antes do dialogo quando falta alguma coisa (salvar.pendencias)."""
    from desdobra.briefing import salvar
    from desdobra.tela import rascunho
    from desdobra.tela.servidor import Ato

    def valido(d):
        # a pagina manda o rascunho como a janela o mostra; ele tem de ser o gravado (revisao do M7a). Sem familia
        # (o passo 3 ainda espera o passo 2), nada e salvo
        return _chaves(d, 'rascunho') and bool(conteudo.get('familias')) and \
            rascunho.mesma_vista(pasta, d['rascunho']) and not salvar.pendencias(pasta, conteudo)

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
        return {'salvo': True, 'derivado': r['derivado']}
    return Ato(comando=salvar.COMANDO, titulo='Salvar o briefing', texto=texto, sim=SIM, nao=NAO, executar=executar,
               validar=valido)
