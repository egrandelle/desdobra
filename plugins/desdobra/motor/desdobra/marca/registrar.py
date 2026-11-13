# -*- coding: utf-8 -*-
"""Registrar o padrao da marca (M7c, passo M5; arquitetura-v1.md, 4.14 e 5.7; decisoes-v1.md, 190, Q1, Q2 e Q3).

O DA registra o padrao num botao da tela, "A campanha foi aprovada: guardar o padrao desta marca", com a confirmacao
dentro da janela (COMANDO, humano.ATOS_DA_TELA; sem comando de terminal). O botao so aparece (na_tela, 'pode') quando:
  - o job tem marca: briefing/marca.json com uma marca da biblioteca desta tela (nao "Sem marca"), escolhida pelo DA
    (a escolha do modo de teste da tela, origem fixture_de_teste, e recusada: marca_de_teste);
  - o briefing e do DA e passa na conferencia da entrega (briefing.modelo.conferir_para_entrega: o de fixture de teste,
    o rascunho e o desatualizado sao recusados), e o job nao tem confirmacao do modo de teste
    (entrega.portao.confirmacao_de_teste), como o portao da entrega;
  - o briefing gravado e o ultimo do indice encadeado (briefing.historico.conferir sem briefing_fora_do_indice): o
    trocado fora da tela e recusado (briefing_fora_do_historico; revisao do M5);
  - todos os formatos do briefing estao aprovados agora (entrega.nucleo_aprovar.situacao com aceita_teste=False: a
    aprovacao do modo de teste e a caida contam como sem aprovacao).
Assim nenhum teste entra na biblioteca da agencia: o Disparo do modo de teste (origem fixture_de_teste, meio medicao)
tambem e recusado no gravar (registro_de_teste).

O que vai ao perfil (conteudo; Q1): so as regras de escala e as ancoras por funcao confirmadas pelo DA no briefing
(situacao confirmado, origem da ou padrao_marca: o clique em "Usar o padrao"), cada uma com o job de origem, e o nome
PostScript das faces usadas no KV (laudo, fontes_usadas). So entram as funcoes que as pecas aprovadas aplicam
(funcoes_aplicadas, pela derivacao que a impressao da aprovacao cobre): a regra de uma funcao sem elemento nas pecas
muda depois da aprovacao sem derruba-la, entao fica no job (revisao do M5). A origem padrao_marca mantem o job de origem do ref
(marca:<id>@v<N>#job:<id>, da mesma marca e de um job com campanha registrada no perfil); a origem da e a deste job.
A funcao do perfil que este job nao decidiu continua como estava na versao anterior, com o job de origem dela (o
perfil acumula o padrao da marca; vale a versao mais recente, Q3). A decisao da regra 10, a origem de teste, o
pendente, a ancora por elemento e a regra por camada do indeterminado ficam no job. Nunca arquivo, caminho nem bytes
de fonte: a face entra so pelo nome PostScript que o contrato do perfil aceita, e a que nao cabe nele fica de fora.

Cada registro grava uma versao nova pelo desdobra.marca.perfil.nova_versao, com a anterior inteira no historico;
registrar de novo o mesmo job sem mudanca nao cria versao (a tela mostra "guardado" no lugar do botao, e o gravar
recusa com ja_guardado), mesmo depois que outro job registrou uma versao mais nova: a comparacao e com a ultima versao
deste job, calculada sobre a versao de antes dela (revisao do M5). A impressao (sha256 do conteudo, das aprovacoes e da versao de partida) vai a pagina e
volta no pedido: o que mudou entre a janela e o Confirmar e recusado (mudou_durante_a_confirmacao).

O que vai a pagina (na_tela) e o nome da marca (dado do DA, posto so por textContent), as versoes, as funcoes do
enum, os valores do enum, os 8 primeiros caracteres do id do job de origem e os nomes PostScript; nunca o caminho da
biblioteca, o id da marca nem arquivo. O gancho do plugin nega ao Claude o codigo deste modulo (CODIGO_DA_MARCA) e a
rota da tela.
"""
import hashlib
import json
import re
from pathlib import Path

from desdobra import contratos

COMANDO = 'marca registrar'
TIPOS_DO_DA = ('da', 'padrao_marca')
CARACTERES_DO_JOB = 8  # numero-neutro: o id curto do job que a tela ja mostra no padrao da marca (M4)
_POSTSCRIPT = re.compile(r'^[!-~]{1,63}$')
_FORA_DO_POSTSCRIPT = re.compile(r'[\[\](){}<>/%\\:]')
_QUEM = re.compile(r'^[^/\\:*?"<>|\x00-\x1f]{1,128}$')

MOTIVOS = ('sem_biblioteca', 'sem_marca', 'marca_de_teste', 'marca_fora_da_biblioteca', 'perfil_ilegivel',
           'briefing_fora_do_historico', 'sem_formatos', 'formato_sem_aprovacao', 'confirmacao_de_fixture_de_teste',
           'ja_guardado', 'registro_de_teste', 'mudou_durante_a_confirmacao')


class ErroRegistro(Exception):
    """O registro nao segue. motivo: codigo curto (MOTIVOS ou o da conferencia do briefing). A mensagem nao leva o
    caminho da biblioteca nem o nome da marca."""

    def __init__(self, motivo):
        super().__init__('O padrão da marca não foi guardado (%s).' % motivo)
        self.motivo = motivo


def funcoes_do_perfil():
    return tuple(contratos.carregar_esquema('perfil-marca/1')['$defs']['funcao']['enum'])


def _postscript_serve(nome):
    from desdobra.marca import perfil
    return isinstance(nome, str) and bool(_POSTSCRIPT.match(nome)) and not _FORA_DO_POSTSCRIPT.search(nome) and \
        not perfil._EXTENSAO_DE_FONTE.search(nome)


def _job_do_ref(ref, marca_id, registrados):
    """O job de origem que o ref do padrao cita, quando ele e da mesma marca e de um job registrado no perfil."""
    from desdobra.tela import funcoes
    m = funcoes.FORMA_DO_REF.match(ref or '')
    if m is None or m.group(1) != marca_id or m.group(3) not in registrados:
        return None
    return m.group(3)


def _origem(decisoes, job_id, marca_id, registrados):
    """O job de origem das decisoes do DA (todas confirmadas, com valor e origem da ou padrao_marca), ou None quando
    alguma nao e do DA. Todas padrao_marca do mesmo job registrado: esse job; senao, este."""
    jobs = set()
    for d in decisoes:
        if not isinstance(d, dict) or d.get('situacao') != 'confirmado' or d.get('valor') is None:
            return None
        o = d.get('origem') or {}
        if o.get('tipo') not in TIPOS_DO_DA:
            return None
        jobs.add(_job_do_ref(o.get('ref'), marca_id, registrados) if o['tipo'] == 'padrao_marca' else None)
    return jobs.pop() if len(jobs) == 1 and None not in jobs else job_id


def _registrados(anterior, historico=()):
    jobs = {v['campanha']['job'] for v in historico if isinstance(v.get('campanha'), dict)}
    if anterior is not None and isinstance(anterior.get('campanha'), dict):
        jobs.add(anterior['campanha']['job'])
    return jobs


def conteudo(briefing, laudo, job_id, marca_id, anterior, historico=(), *, funcoes):
    """{'regras_escala', 'ancoras', 'faces'} da versao nova, como nova_versao recebe. anterior: a versao atual do
    perfil (None no perfil sem registro); historico: as versoes anteriores dela (os jobs registrados que o ref pode
    citar); funcoes: as funcoes que as pecas aprovadas aplicam (funcoes_aplicadas). A regra e a ancora de uma funcao
    que nenhuma peca aprovada aplica ficam fora: elas nao entram na impressao da aprovacao e podem mudar depois dela
    sem derruba-la (revisao do M5). Funcao pura."""
    validas = tuple(f for f in funcoes_do_perfil() if f in set(funcoes))
    registrados = _registrados(anterior, historico)
    regras, ancoras = {}, {}
    for r in briefing.get('regras_escala') or []:
        f = r.get('funcao')
        if f in validas and f not in regras:
            origem = _origem([r.get('regra')], job_id, marca_id, registrados)
            if origem is not None:
                regras[f] = {'funcao': f, 'regra': r['regra']['valor'], 'job_origem': origem}
    for a in briefing.get('ancoras') or []:
        f = a.get('funcao')
        if f in validas and 'layer_id' not in a and f not in ancoras:
            origem = _origem([a.get('x'), a.get('y')], job_id, marca_id, registrados)
            if origem is not None:
                ancoras[f] = {'funcao': f, 'x': a['x']['valor'], 'y': a['y']['valor'], 'job_origem': origem}
    # a funcao que este job nao decidiu fica como estava no perfil, com o job de origem dela
    for item in (anterior or {}).get('regras_escala') or []:
        regras.setdefault(item['funcao'], dict(item))
    for item in (anterior or {}).get('ancoras') or []:
        ancoras.setdefault(item['funcao'], dict(item))
    faces = []
    for f in laudo.get('fontes_usadas') or []:
        nome = f.get('fonte_ps') if isinstance(f, dict) else None
        if _postscript_serve(nome) and {'postscript': nome} not in faces:
            faces.append({'postscript': nome})
    ordem = {f: i for i, f in enumerate(funcoes_do_perfil())}
    return {'regras_escala': sorted(regras.values(), key=lambda x: ordem[x['funcao']]),
            'ancoras': sorted(ancoras.values(), key=lambda x: ordem[x['funcao']]),
            'faces': sorted(faces, key=lambda x: x['postscript'])}


def _impressao(c, aprovacoes, versao_atual):
    corpo = {'conteudo': c, 'aprovacoes': aprovacoes, 'versao_atual': versao_atual}
    return hashlib.sha256(json.dumps(corpo, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def _aprovacoes(pasta):
    """([{'formato', 'aprovacao_sha256'}], motivo): o registro de cada formato do briefing, todos aprovados agora."""
    from desdobra.entrega import aprovacao, nucleo_aprovar, portao
    sit = nucleo_aprovar.situacao(pasta, aceita_teste=False)
    if not sit:
        return None, 'sem_formatos'
    if any(s['situacao'] != 'aprovado' for s in sit.values()):
        return None, 'formato_sem_aprovacao'
    if portao.confirmacao_de_teste(pasta):
        return None, 'confirmacao_de_fixture_de_teste'
    try:
        aprov = aprovacao.ler(pasta)
    except contratos.ErroContrato:
        return None, 'formato_sem_aprovacao'
    saida = []
    for fid in sorted(sit):
        reg = (aprov or {}).get('formatos', {}).get(fid) or {}
        por = reg.get('aprovado_por') or {}
        # o mesmo criterio do portao da entrega: a aprovacao do modo de teste nunca vai ao perfil
        if por.get('origem') != 'da' or por.get('meio') == 'medicao' or not reg.get('registro_sha256'):
            return None, 'formato_sem_aprovacao'
        saida.append({'formato': fid, 'aprovacao_sha256': reg['registro_sha256']})
    return saida, None


def funcoes_aplicadas(pasta, formatos):
    """As funcoes que as pecas dos formatos aplicam (a regra_aplicada de cada elemento de derivacao/<formato>.json, a
    derivacao que a impressao da aprovacao cobre), ou None quando falta uma derivacao legivel."""
    from desdobra.derivacao import nucleo as nd
    saida = set()
    for fid in formatos:
        try:
            d = contratos.ler(Path(pasta) / nd.PASTA / ('%s.json' % fid), nd.ESQUEMA)
        except (contratos.ErroContrato, OSError):
            return None
        saida |= {e['regra_aplicada']['funcao'] for e in d['elementos']}
    return saida


def _ja_guardado(dados, b, laudo, job_id, marca_id, formatos, funcoes):
    """(versao, conteudo) da ultima versao do perfil registrada por este job quando o job nao mudou desde aquele
    registro (o mesmo conteudo, calculado sobre a versao de antes dela, e as mesmas aprovacoes); senao None. Vale
    tambem quando outro job registrou depois (revisao do M5): o job sem mudanca nao volta o padrao antigo por cima."""
    from desdobra.marca import perfil
    versoes = list(dados['historico']) + ([dados['atual']] if dados['atual'] is not None else [])
    for i in range(len(versoes) - 1, -1, -1):
        if (versoes[i].get('campanha') or {}).get('job') != job_id:
            continue
        antes = versoes[i - 1] if i > 0 else None
        c = conteudo(b, laudo, job_id, marca_id, antes, versoes[:max(i - 1, 0)], funcoes=funcoes)
        igual = perfil._conteudo(versoes[i]) == \
            perfil._conteudo(dict(c, job_origem=job_id, campanha={'formatos': formatos}))
        return (versoes[i]['versao'], c) if igual else None
    return None


def conferir(pasta, biblioteca):
    """O que o registro faria agora: {'pode', 'motivo', 'guardado', ...}. Com 'pode' ou 'guardado', leva tambem
    'marca_id', 'nome', 'perfil', 'conteudo', 'formatos' (as aprovacoes), 'job_id' e 'impressao'; com 'guardado',
    'versao_guardada' (a versao deste job) e, em 'conteudo', o que ela guardou. Nunca grava."""
    from desdobra.briefing import historico
    from desdobra.briefing import modelo as mb
    from desdobra.marca import job as marca_job
    from desdobra.marca import perfil
    pasta = Path(pasta).resolve()
    nao = {'pode': False, 'guardado': False}
    if biblioteca is None:
        return dict(nao, motivo='sem_biblioteca')
    reg = marca_job.ler(pasta)
    if reg is None or reg['escolha'] != 'marca' or not reg.get('marca_id'):
        return dict(nao, motivo='sem_marca')
    if reg.get('origem') != 'da' or (reg.get('escolhido_por') or {}).get('meio') != 'tela':
        return dict(nao, motivo='marca_de_teste')
    marca_id = reg['marca_id']
    try:
        dados = perfil.ler(biblioteca, marca_id)
    except perfil.ErroPerfil:
        try:
            existe = perfil.caminho(biblioteca, marca_id).is_file()
        except perfil.ErroPerfil:
            existe = False
        return dict(nao, motivo='perfil_ilegivel' if existe else 'marca_fora_da_biblioteca')
    except OSError:
        return dict(nao, motivo='perfil_ilegivel')
    pode, motivo = mb.conferir_para_entrega(pasta)
    if not pode:
        return dict(nao, motivo=motivo)
    # o briefing trocado fora da tela (nao e o ultimo do indice encadeado) nao chega a biblioteca (revisao do M5)
    if any(p['codigo'] == 'briefing_fora_do_indice' for p in historico.conferir(pasta)):
        return dict(nao, motivo='briefing_fora_do_historico')
    formatos, motivo = _aprovacoes(pasta)
    if formatos is None:
        return dict(nao, motivo=motivo)
    funcoes = funcoes_aplicadas(pasta, [f['formato'] for f in formatos])
    if funcoes is None:
        return dict(nao, motivo='formato_sem_aprovacao')
    try:
        b = mb.ler(pasta)
        laudo = contratos.ler(pasta / mb.ARQUIVO_LAUDO, 'laudo/1')
        job_id = contratos.ler(pasta / 'estado.json', 'estado/1')['job_id']
    except (contratos.ErroContrato, OSError):
        return dict(nao, motivo='briefing_desatualizado')
    c = conteudo(b, laudo, job_id, marca_id, dados['atual'], dados['historico'], funcoes=funcoes)
    saida = {'marca_id': marca_id, 'nome': dados['marca'], 'perfil': dados, 'conteudo': c, 'formatos': formatos,
             'job_id': job_id, 'impressao': _impressao(c, formatos, dados['versao']), 'motivo': None,
             'versao_guardada': None}
    guardado = _ja_guardado(dados, b, laudo, job_id, marca_id, formatos, funcoes)
    if guardado is not None:
        return dict(saida, pode=False, guardado=True, motivo='ja_guardado', versao_guardada=guardado[0],
                    conteudo=guardado[1])
    return dict(saida, pode=True, guardado=False)


def _linhas(itens, job_id, chaves):
    return [dict({k: i[k] for k in chaves}, funcao=i['funcao'], job=i['job_origem'][:CARACTERES_DO_JOB],
                 desta_campanha=i['job_origem'] == job_id) for i in itens]


def na_tela(pasta, biblioteca):
    """O bloco do registro na tela: {'pode', 'motivo', 'guardado'} e, com o botao ('pode') ou com o padrao ja guardado,
    'nome' (da marca), 'versao_atual', 'versao_nova' (None quando guardado), 'versao_guardada' (a versao deste job
    quando guardado, senao None), 'regras' ([{funcao, regra, job,
    desta_campanha}]), 'ancoras' ([{funcao, x, y, job, desta_campanha}]), 'faces' (nomes PostScript), 'formatos' (o
    numero de formatos aprovados) e 'impressao' (volta no pedido do ato). Sem caminho e sem o id da marca."""
    try:
        c = conferir(pasta, biblioteca)
    except Exception:  # noqa: BLE001 - na duvida, a tela nao mostra o botao
        return {'pode': False, 'motivo': 'perfil_ilegivel', 'guardado': False}
    saida = {'pode': c['pode'], 'motivo': c['motivo'], 'guardado': c['guardado']}
    if not (c['pode'] or c['guardado']):
        return saida
    versao = c['perfil']['versao']
    cont = c['conteudo']
    saida.update({'nome': c['nome'], 'versao_atual': versao, 'versao_nova': versao + 1 if c['pode'] else None,
                  'versao_guardada': c['versao_guardada'],
                  'regras': _linhas(cont['regras_escala'], c['job_id'], ('regra',)),
                  'ancoras': _linhas(cont['ancoras'], c['job_id'], ('x', 'y')),
                  'faces': [f['postscript'] for f in cont['faces']], 'formatos': len(c['formatos']),
                  'impressao': c['impressao']})
    return saida


def _quem(valor):
    return valor if isinstance(valor, str) and _QUEM.match(valor) else None


def gravar(pasta, *, disparo, biblioteca, impressao):
    """Grava a versao nova do perfil da marca do job. disparo: o da tela (humano.exigir_tela(COMANDO, ...)), gasto aqui
    mesmo quando o registro e recusado; o do modo de teste e recusado (registro_de_teste). impressao: a que a janela
    mostrou (na_tela). Devolve {'versao', 'criou'}. ErroRegistro com o motivo."""
    from desdobra import humano
    from desdobra.job import nucleo
    from desdobra.marca import perfil
    humano.conferir(disparo, COMANDO, consumir=True)
    if disparo.origem != humano.ORIGEM_DA or disparo.meio != humano.MEIO_TELA:
        raise ErroRegistro('registro_de_teste')
    pasta = Path(pasta).resolve()
    with nucleo.Trava(pasta):
        c = conferir(pasta, biblioteca)
        if not c['pode']:
            raise ErroRegistro(c['motivo'])
        if c['impressao'] != impressao:
            raise ErroRegistro('mudou_durante_a_confirmacao')
        reg = disparo.registro()
        campanha = {'job': c['job_id'], 'data': str(reg['quando'])[:10], 'formatos': c['formatos'],
                    'confirmado_por': {'usuario': _quem(reg['usuario']), 'maquina': _quem(reg['maquina'])},
                    'origem': humano.ORIGEM_DA, 'meio': humano.MEIO_TELA}
        try:
            novo, criou = perfil.nova_versao(biblioteca, c['marca_id'], campanha=campanha, quando=reg['quando'],
                                             versao_esperada=c['perfil']['versao'], **c['conteudo'])
        except perfil.ErroPerfilOcupado:
            # outro registro da mesma marca segurou a trava alem da espera: pede a janela de novo
            raise ErroRegistro('mudou_durante_a_confirmacao') from None
        except perfil.ErroPerfil:
            # o perfil que mudou desde a conferencia (outro registro da mesma marca) pede a janela de novo
            try:
                mudou = perfil.ler(biblioteca, c['marca_id'])['versao'] != c['perfil']['versao']
            except (perfil.ErroPerfil, OSError):
                mudou = False
            raise ErroRegistro('mudou_durante_a_confirmacao' if mudou else 'perfil_ilegivel') from None
        # no log, so a versao e se criou: nem o nome nem o id da marca
        nucleo.registrar_evento(pasta, 'padrao_da_marca_registrado', versao=novo['versao'], criou=criou)
    return {'versao': novo['versao'], 'criou': criou}
