# -*- coding: utf-8 -*-
"""O nucleo comum da aprovacao (M7b, B4; arquitetura-v1.md, 9.7; decisoes-v1.md, 138): o que o "desdobra aprovar" do
terminal (desdobra.entrega, so para a Trezion e para os testes) e o ato de aprovar da tela (desdobra.tela.ato_aprovar)
fazem igual.

Os dois lados seguem o mesmo roteiro, cada um com a sua pergunta ao DA no meio:
  1. com a trava do job, conferir() roda o portao do aprovar em cada formato pedido (desdobra.entrega.portao: master,
     render.json, contrato refeito, KV, impressao e rotacao; a origem do briefing fica para o entregar) e gera o arquivo
     final de cada um (final=True); com_falha() diz os formatos recusados. gravar_previas() grava o arquivo final em
     entrega/previa/ para o DA ver, e vista() guarda o que ele vai confirmar (os hashes, o sha256 e os parametros do
     arquivo final de cada formato);
  2. a pergunta ao DA roda sem a trava (o sim digitado no terminal; o dialogo da janela na tela);
  3. com a trava de novo, confirmar() confere tudo outra vez e so grava quando nada mudou desde o que o DA viu: um
     registro por formato em briefing/aprovacao.json (desdobra.entrega.aprovacao), com o Disparo do "aprovar", e o
     evento aprovacao_gravada com o meio. Mudou: ErroAprovar mudou_durante_a_confirmacao, com os formatos, e nada e
     gravado.
sentidos: o sentido do giro que o DA escolheu na janela de aprovar da tela para o formato que gira 90 ou 270 graus sem
sentido gravado. Vale no conferir (o arquivo final ja sai girado) e e gravado pela tela antes da aprovacao, dentro do
confirmar (antes_de_gravar), com a mesma confirmacao do DA.

situacao() e a vista da tela da aprovacao de cada formato do briefing, medida com aprovacao.diferencas sobre os hashes
de agora (portao.hashes_do_formato) e com os parametros do arquivo final que nao dependem do master
(codificar.parametros_sem_o_master; revisao do M7b, fase B), sem refazer contrato nem arquivo final (a critica do
plano: o portao com aprovacao=True recusa a aprovacao do modo de teste e nao serve de medida).
"""
from pathlib import Path

from desdobra import contratos

ERRO_FALHA = 'formato_com_falha'
ERRO_MUDOU = 'mudou_durante_a_confirmacao'
# o motivo da queda de uma aprovacao, por campo de aprovacao.diferencas, dito para o DA (a tela o mostra ao lado do
# formato). parametros_encoder.<campo> usa o de parametros_encoder
MOTIVOS_DA_QUEDA = {
    'impressao_formato': 'O briefing mudou numa parte que entra neste formato.',
    'master_sha256': 'O formato foi renderizado de novo.',
    'render_json_sha256': 'O formato foi renderizado de novo.',
    'contrato_sha256': 'O formato foi renderizado de novo.',
    'arquivo_entregue_sha256': 'O arquivo final do formato mudou.',
    'parametros_encoder': 'Um ajuste do arquivo final mudou, como o giro ou a borda.',
    'registro_sha256': 'O registro da aprovação foi mexido fora da tela.',
    'job_id': 'O registro da aprovação é de outro job.',
    'aprovacao_antiga': 'A aprovação foi feita numa versão anterior do desdobra.',
    'aprovacao_ilegivel': 'O registro da aprovação não se lê.',
    'aprovacao_de_teste': 'A aprovação foi feita num teste. Ela não vale para a entrega.',
    'sentido_de_teste': 'O lado do giro foi escolhido num teste. Ele não vale para a entrega.',
}


class ErroAprovar(Exception):
    """A aprovacao nao segue. motivo: ERRO_FALHA (conf: o resultado do portao) ou ERRO_MUDOU (mudaram: os formatos)."""

    def __init__(self, mensagem, motivo, conf=None, mudaram=()):
        super().__init__(mensagem)
        self.motivo, self.conf, self.mudaram = motivo, conf, list(mudaram)


def conferir(pasta, formatos, sentidos=None):
    """O portao do aprovar nos formatos pedidos (portao.conferir com origem=False, aprovacao=False e o arquivo final).
    Quem chama segura a trava do job."""
    from desdobra.entrega import portao
    return portao.conferir(pasta, list(dict.fromkeys(formatos)), origem=False, aprovacao=False, sentidos=sentidos)


def com_falha(conf):
    """Os formatos que o portao recusou, na ordem do pedido."""
    return [fid for fid, item in conf['formatos'].items() if item['falhas']]


def gravar_previas(pasta, conf):
    """{formato: caminho relativo} do arquivo final de cada formato em entrega/previa/, para o DA ver antes de
    aprovar."""
    from desdobra.entrega import aprovacao
    return {fid: aprovacao.gravar_previa(pasta, fid, item['final']) for fid, item in conf['formatos'].items()}


def vista(conf):
    """{formato: {'atual', 'sha256', 'parametros'}}: o que o DA confirma (os hashes medidos, o sha256 e os parametros do
    arquivo final mostrado). Em JSON simples: fica no pedido pendente da tela e na pergunta do terminal."""
    import json
    return {fid: {'atual': dict(item['atual']), 'sha256': item['final'].sha256,
                  'parametros': json.loads(json.dumps(item['final'].parametros, sort_keys=True))}
            for fid, item in conf['formatos'].items()}


def mudaram(antes, conf):
    """Os formatos que falham agora ou que mudaram desde a vista que o DA viu (antes: vista())."""
    agora = {fid: item for fid, item in conf['formatos'].items() if not item['falhas']}
    novo = vista({'formatos': agora})
    return sorted(fid for fid in set(antes) | set(conf['formatos']) if fid not in novo or novo[fid] != antes.get(fid))


def confirmar(pasta, formatos, antes, disparo, *, sentidos=None, antes_de_gravar=None):
    """Com a trava do job (quem chama segura): confere de novo e grava um registro por formato com o Disparo do
    "aprovar". antes: a vista() que o DA confirmou. antes_de_gravar(): o que a tela grava com a mesma confirmacao
    depois da conferencia e antes da aprovacao (o sentido do giro). ErroAprovar(ERRO_MUDOU) quando algo mudou, sem gravar
    nada. Devolve os registros gravados."""
    from desdobra.entrega import aprovacao, portao
    from desdobra.job import nucleo
    pasta = Path(pasta).resolve()
    nova = conferir(pasta, formatos, sentidos=sentidos)
    mud = mudaram(antes, nova)
    if mud:
        raise ErroAprovar('O job mudou durante a confirmação: %s.' % ', '.join(mud), ERRO_MUDOU, mudaram=mud)
    if antes_de_gravar is not None:
        antes_de_gravar()
    job_id, _kv = portao.kv_atual(pasta)
    regs = [aprovacao.registro(fid, job_id, item['atual'], item['final'], disparo)
            for fid, item in nova['formatos'].items()]
    aprovacao.gravar(pasta, regs, job_id, disparo=disparo)
    nucleo.registrar_evento(pasta, 'aprovacao_gravada', n_formatos=len(regs), meio=disparo.meio)
    return regs


def _motivos(campos):
    textos = [MOTIVOS_DA_QUEDA.get(c.split('.', 1)[0], MOTIVOS_DA_QUEDA['registro_sha256']) for c in campos]
    return list(dict.fromkeys(textos))


def _de_teste(por):
    """O registro da aprovacao saiu do modo de teste da tela (o mesmo criterio do portao da entrega, aprovacao_de_teste;
    o registro de antes da origem gravada conta como do DA)."""
    from desdobra import humano
    return por.get('meio') == humano.MEIO_MEDICAO or por.get('origem', humano.ORIGEM_DA) != humano.ORIGEM_DA


def sentido_de_teste(params, fid):
    """O sentido do giro do formato em parametros/entrega.json saiu do modo de teste da tela (o mesmo criterio da
    aprovacao, _de_teste; o portao da entrega recusa o job inteiro com ele, portao.confirmacao_de_teste). params: o de
    portao.parametros_de_entrega."""
    c = ((params or {}).get(fid) or {}).get('rotacao_sentido')
    return isinstance(c, dict) and _de_teste(c.get('confirmado_por') or {})


def _parametros_do_final(pasta, fid, reg):
    """Os campos parametros_encoder.<campo> que mudaram desde a aprovacao, dos que nao dependem dos bytes do master
    (codificar.parametros_sem_o_master: o teto, o giro, o achatamento, a borda, as versoes do encoder e os do tipo
    aprovado que vem dos limites do pacote), como o portao os nomeia. O arquivo final que nao sai mais conta como
    parametros_encoder."""
    import json
    from desdobra.entrega import codificar
    antes = reg.get('parametros_encoder') or {}
    try:
        agora = codificar.parametros_sem_o_master(pasta, fid, achatado=antes.get('achatamento') is not None,
                                                  tipo=antes.get('tipo'))
    except codificar.ErroCodificar:
        return ['parametros_encoder']
    agora = json.loads(json.dumps(agora, sort_keys=True))
    return ['parametros_encoder.%s' % k for k in sorted(agora) if antes.get(k) != agora[k]]


def situacao(pasta, hashes=None, aceita_teste=True):
    """{formato: {'situacao', 'campos', 'motivos', 'meio', 'quando'}} de cada formato do briefing ({} sem briefing
    legivel). situacao: 'aprovado', 'caiu' (campos: os de aprovacao.diferencas; motivos: as frases para o DA) ou
    'sem_aprovacao'. Mede os hashes de agora e os parametros do arquivo final que nao dependem do master (revisao do M7b,
    fase B: a condicao do teto, o giro, a borda, a cor de achatamento e as versoes do encoder derrubam a aprovacao no
    portao, e a tela diz o mesmo), sem refazer contrato nem arquivo final: o arquivo inteiro e conferido de novo no
    aprovar e no entregar. hashes: {formato: portao.hashes_do_formato} ja medidos por quem chama (o painel da tela, M7b,
    B5), para nao ler o master duas vezes; o formato que falta nele e medido aqui. aceita_teste=False (o job com decisao
    do DA, que o modo de teste nunca abre): a aprovacao do modo de teste conta como caida (aprovacao_de_teste), e o DA
    aprova de novo com um clique. O sentido do giro do modo de teste (sentido_de_teste) tambem derruba a aprovacao do
    formato girado, e a janela de aprovar pede o lado de novo (segunda revisao do M7b, fase B)."""
    from desdobra.briefing import modelo as mb
    from desdobra.entrega import aprovacao, portao
    pasta = Path(pasta).resolve()
    try:
        b = mb.ler(pasta)
    except (contratos.ErroContrato, OSError, ValueError):
        return {}
    ids = [f['id'] for f in (b or {}).get('formatos') or [] if isinstance(f, dict) and isinstance(f.get('id'), str)]
    vazio = {'situacao': 'sem_aprovacao', 'campos': [], 'motivos': [], 'meio': None, 'quando': None}
    try:
        aprov = aprovacao.ler(pasta)
    except (contratos.ErroContrato, OSError, ValueError):
        caiu = dict(vazio, situacao='caiu', campos=['aprovacao_ilegivel'],
                    motivos=[MOTIVOS_DA_QUEDA['aprovacao_ilegivel']])
        return {fid: dict(caiu) for fid in ids}
    try:
        job_id, _kv = portao.kv_atual(pasta)
    except (contratos.ErroContrato, OSError, ValueError):
        job_id = None
    try:
        params = portao.parametros_de_entrega(pasta) if not aceita_teste else {}
    except (contratos.ErroContrato, OSError, ValueError):
        params = {}  # ilegivel: o portao recusa com o codigo dele, e o arquivo final conta como parametros_encoder
    saida = {}
    for fid in ids:
        reg = (aprov or {}).get('formatos', {}).get(fid)
        if reg is None:
            saida[fid] = dict(vazio)
            continue
        por = reg.get('aprovado_por') or {}
        if aprov['esquema'] != aprovacao.ESQUEMA:
            campos = ['aprovacao_antiga']
        elif not aceita_teste and (_de_teste(por) or sentido_de_teste(params, fid)):
            campos = (['aprovacao_de_teste'] if _de_teste(por) else []) +                 (['sentido_de_teste'] if sentido_de_teste(params, fid) else [])
        else:
            atual = (hashes or {}).get(fid) or \
                portao.hashes_do_formato(pasta, fid, portao.impressao_do_formato(pasta, b, fid))
            campos = aprovacao.diferencas(reg, job_id, atual) or _parametros_do_final(pasta, fid, reg)
        saida[fid] = {'situacao': 'caiu' if campos else 'aprovado', 'campos': campos, 'motivos': _motivos(campos),
                      'meio': por.get('meio'), 'quando': por.get('quando')}
    return saida
