# -*- coding: utf-8 -*-
"""Pacote para o modelo (sugestoes/pacote-modelo.json, contrato pacote-modelo/2; M7c, S2).

arquitetura-v1.md, 4.9 e 7.4. O pacote e o que o Claude pode ler para sugerir funcoes, conforme o modo de dados
efetivo do job (desdobra.job.modo_dados.efetivo):

  modo a: metadados e textos das camadas e os caminhos das miniaturas permitidas, copiadas para
          sugestoes/miniaturas/ por desdobra.sugestao.miniaturas (so camadas sem texto; decisoes-v1.md, 190, Q7);
  modo b: metadados e textos das camadas, depois do detector de segredos; sem miniatura e sem a pasta;
  modo c: so contagens, estados, ids e numeros do motor. Nenhum nome, texto ou caminho.

Camada com segredo fica no pacote so com layer_id, pai_id, tipo, situacao e regras, marcada com
segredo_bloqueado; nome, textos e miniatura nunca entram. O detalhe vai para sugestoes/segredos-bloqueados.json.

O pacote e refeito sempre que o modo ou o PSD muda:
  - gravar_pacote: a fase ler (a releitura depois de "job trocar-entrada" do KV inclusive) grava o pacote e refaz
    sugestoes/miniaturas/ no mesmo passo;
  - refazer_pacotes: o ato do modo na tela e o "sugestao pacote" refazem os dois pacotes (este e o das specs);
  - conferir_modo: "tela abrir", "job proxima" e "sugestao pacote" recalculam o modo efetivo com o teto da linha de
    comando e refazem os pacotes se o modo mudou (a agencia baixou o teto sem clique do DA), se o pacote e do
    contrato antigo, se o KV do job nao e mais o do laudo, se um pacote sumiu com a leitura ou o rascunho das specs
    em dia ou se os bytes gravados nao sao os que o motor grava agora (pacote mexido fora do motor, chave repetida
    inclusive). Na falha, fecham tudo o que o Claude le em sugestoes/;
  - curar_specs: a tela (montagem e cada pedido do estado) refaz a fase specs que o ato do modo nao conseguiu refazer
    porque outro processo segurava o job.
Os dois pacotes nao contam para a validade das fases do job (desdobra.job.fases, campo refeitas; M7c, E1): trocar o
modo nao desatualiza a esteira, e e a conferencia acima que garante que o pacote gravado e o do modo e do KV de agora.
Quando o modo efetivo e c, saem tambem as sugestoes do Claude (sugestoes.json, sugestoes-validadas.json e
mapeamento-specs.json): nada com nome ou texto fica legivel pelo Claude. O mapeamento e entrada da fase specs: quando
ele sai e e a unica entrada da fase que mudou, refazer_pacotes (e conferir_modo, se o ato nao conseguiu) refaz a
fase no proprio processo e a grava em dia (sem passo no terminal).

O registro do que foi exposto ao modelo vai para log/eventos.jsonl (evento pacote_modelo_exposto) so com o modo, as
contagens e, das miniaturas, layer_id e sha256; nunca nome, texto ou caminho.

O pacote-modelo/1 (M1) continua so para leitura de jobs antigos (ler_pacote).

Tambem daqui: conteudo_para_resultado(laudo), que monta o Resultado.conteudo que o envelope filtra.
"""
from pathlib import Path

from desdobra import contratos
from desdobra.sugestao import miniaturas as mod_miniaturas
from desdobra.sugestao import segredos

CONTRATO = 'pacote-modelo/2'
CONTRATO_ANTIGO = 'pacote-modelo/1'
ARQUIVO_PACOTE = Path('sugestoes') / 'pacote-modelo.json'
# o que o Claude escreve em sugestoes/ e que leva nome ou texto do cliente: sai quando o modo efetivo vira c
ESCRITOS_DO_CLAUDE = (Path('sugestoes') / 'sugestoes.json', Path('sugestoes') / 'sugestoes-validadas.json',
                      Path('sugestoes') / 'mapeamento-specs.json')
EVENTO_EXPOSTO = 'pacote_modelo_exposto'
# o rascunho das specs (desdobra.specs.importar.ARQUIVO_RASCUNHO, teste de igualdade): com ele, o pacote das specs existe
ARQUIVO_RASCUNHO_SPECS = Path('specs') / 'rascunho.json'
# o mapeamento do Claude (desdobra.specs.importar.ARQUIVO_MAPEAMENTO, teste de igualdade), entrada da fase specs
ARQUIVO_MAPEAMENTO = Path('sugestoes') / 'mapeamento-specs.json'


def textos_da_camada(camada):
    """Os textos de uma camada do laudo/1: o conteudo do texto ou, sem ele, o texto de cada trecho."""
    texto = camada.get('texto') or None
    if not isinstance(texto, dict):
        return []
    if isinstance(texto.get('conteudo'), str) and texto['conteudo']:
        return [texto['conteudo']]
    return [r['texto'] for r in texto.get('runs') or [] if isinstance(r, dict) and isinstance(r.get('texto'), str)]


def _layer_id(camada):
    ident = camada.get('identidade') or {}
    return ident.get('layer_id', camada.get('layer_id'))


def conteudo_para_resultado(laudo):
    """Resultado.conteudo de um laudo/1: camadas com layer_id, nome, tipo, situacao e textos (o envelope filtra)."""
    camadas = []
    for c in laudo.get('camadas') or []:
        camadas.append({'layer_id': _layer_id(c), 'nome': c.get('nome', ''), 'tipo': c.get('tipo'),
                        'situacao': c.get('situacao'), 'textos': textos_da_camada(c)})
    return {'camadas': camadas}


def _regras(camada):
    return sorted({m.get('regra') for m in camada.get('motivos') or [] if isinstance(m, dict) and m.get('regra')})


def _coberta(camada):
    cob = (camada.get('geometria') or {}).get('coberta_no_kv')
    if not isinstance(cob, dict):
        return None
    sugestao = cob.get('sugestao_da_regra') or None
    return {'coberta': bool(cob.get('coberta')), 'ocupa_canvas': bool(cob.get('ocupa_canvas')),
            'sugestao_da_regra': None if not sugestao else {'funcao': sugestao.get('funcao'),
                                                             'regra': sugestao.get('regra')}}


def caminho_da_miniatura(layer_id):
    return '%s/%d.png' % (mod_miniaturas.PASTA.as_posix(), layer_id)


def montar_pacote(laudo, modo, *, job_id=None, detector=None, miniaturas=None):
    """Devolve (pacote, achados). O pacote vale contra pacote-modelo/2.

    miniaturas: os itens do indice.json que gravar_miniaturas gravou ({'layer_id', 'sha256'}); entram so no modo a
    e so os de camada sem segredo."""
    detector = detector or segredos.detector_padrao()
    abre_conteudo = modo in ('a', 'b')
    achados = []
    camadas = []
    por_situacao = {'lida': 0, 'degradada': 0, 'bloqueante': 0}
    for c in laudo.get('camadas') or []:
        lid = _layer_id(c)
        situacao = c.get('situacao')
        if situacao in por_situacao:
            por_situacao[situacao] += 1
        item = {'layer_id': lid, 'pai_id': c.get('pai_id'), 'tipo': c.get('tipo'), 'situacao': situacao,
                'regras': _regras(c)}
        nome, textos = c.get('nome', ''), textos_da_camada(c)
        achado = detector.achado_em('camada', lid, {'nome': nome, 'textos': textos})
        if achado is not None:
            achados.append(achado)
            item['segredo_bloqueado'] = True
        elif abre_conteudo:
            geo = c.get('geometria') or {}
            item.update({'nome': nome, 'textos': textos,
                         'visivel': bool((c.get('aparencia') or {}).get('visivel_efetiva')),
                         'caixa': geo.get('caixa'), 'quadro': c.get('quadro'), 'coberta_no_kv': _coberta(c)})
        camadas.append(item)

    caminhos = []
    if modo == 'a':
        bloqueadas = {a.layer_id for a in achados}
        ids = sorted({i['layer_id'] for i in miniaturas or [] if isinstance(i, dict)
                      and isinstance(i.get('layer_id'), int) and not isinstance(i.get('layer_id'), bool)
                      and i['layer_id'] > 0 and i['layer_id'] not in bloqueadas})
        caminhos = [caminho_da_miniatura(lid) for lid in ids]

    doc = laudo.get('documento') or {}
    quadros = doc.get('quadros') or []
    pacote = {
        'esquema': CONTRATO,
        'modo_dados': modo,
        'job_id': job_id,
        'arquivo_sha256': (laudo.get('origem') or {}).get('sha256'),
        'exposto': {'metadados': abre_conteudo, 'textos': abre_conteudo, 'miniaturas': bool(caminhos)},
        'documento': {'largura': doc.get('largura'), 'altura': doc.get('altura'),
                      'n_camadas': len(camadas), 'n_quadros': len(quadros)},
        'contagens': dict(por_situacao, segredos_bloqueados=len(achados), miniaturas=len(caminhos)),
        'camadas': camadas,
        'miniaturas': caminhos,
    }
    if abre_conteudo:
        pacote['documento']['quadros'] = [{'id': q.get('id'), 'layer_id': q.get('layer_id'), 'caixa': q.get('caixa'),
                                           'visivel_ao_salvar': q.get('visivel_ao_salvar')} for q in quadros]
        fontes = []
        for f in laudo.get('fontes_usadas') or []:
            nome = f.get('fonte_ps')
            achado = detector.achado_em('fonte', None, {'fonte_ps': nome})
            if achado is not None:
                achados.append(achado)
                continue
            fontes.append({'fonte_ps': nome, 'camadas': list(f.get('camadas') or [])})
        pacote['fontes_usadas'] = fontes
        pacote['contagens']['segredos_bloqueados'] = len(achados)
    contratos.validar(pacote, CONTRATO)
    return pacote, achados


def ler_pacote(caminho):
    """O pacote gravado: pacote-modelo/2 ou, de job antigo, pacote-modelo/1. ErroContrato se nenhum dos dois."""
    from desdobra import arquivos
    dados = arquivos.ler_json(caminho)
    esquema = dados.get('esquema') if isinstance(dados, dict) else None
    contratos.validar(dados, CONTRATO_ANTIGO if esquema == CONTRATO_ANTIGO else CONTRATO)
    return dados


# Teto da linha de comando do processo (--teto-modo-dados), posto pela CLI antes de rodar o comando. Vale para quem
# chama modo_do_job sem passar o teto (a fase ler grava o pacote, o spec importar grava o das specs): o que o
# Claude le nunca sai mais aberto que o envelope do mesmo comando. So fecha, nunca abre.
_teto_do_processo = None


def definir_teto_do_processo(teto):
    """Guarda o teto da linha de comando deste processo (None quando nao veio)."""
    global _teto_do_processo
    _teto_do_processo = teto


def modo_do_job(pasta_job, estado, teto=None):
    """O modo do job: o escolhido pelo DA na tela (desdobra.job.modo_dados, fonte unica; decisoes-v1.md, 170),
    limitado pelo teto do estado.json, pelo da linha de comando (teto) e pelo do processo; sem escolha, c. O
    modo_dados do estado.json nao vale como fonte."""
    from desdobra.job import modo_dados
    return modo_dados.efetivo(pasta_job, modo_dados.teto(estado.get('teto_modo_dados'), teto, _teto_do_processo))


def _apagar_arquivo(caminho):
    try:
        Path(caminho).unlink()
        return 1
    except FileNotFoundError:
        return 0


def apagar_escritos_do_claude(pasta_job):
    """Apaga sugestoes.json, sugestoes-validadas.json e mapeamento-specs.json. Devolve quantos existiam."""
    return sum(_apagar_arquivo(Path(pasta_job) / rel) for rel in ESCRITOS_DO_CLAUDE)


def _registrar_exposto(pasta_job, pacote, indice):
    """O registro do que foi exposto: modo, contagens e, das miniaturas, so layer_id e sha256."""
    from desdobra.job import nucleo
    expostas = {caminho for caminho in pacote['miniaturas']}
    nucleo.registrar_evento(
        pasta_job, EVENTO_EXPOSTO, modo=pacote['modo_dados'],
        camadas=sum(1 for c in pacote['camadas'] if 'nome' in c), textos=int(pacote['exposto']['textos']),
        segredos_bloqueados=pacote['contagens']['segredos_bloqueados'],
        miniaturas=[{'layer_id': i['layer_id'], 'sha256': i['sha256']} for i in (indice or {}).get('miniaturas') or []
                    if caminho_da_miniatura(i['layer_id']) in expostas])


def gravar_pacote(pasta_job, *, detector=None, teto=None):
    """Le estado.json e laudo/laudo.json do job e, conforme o modo efetivo (com o teto da linha de comando, quando
    vem): refaz sugestoes/miniaturas/, grava sugestoes/pacote-modelo.json, o arquivo do DA com os achados e o
    registro do que foi exposto; no modo c apaga tambem as sugestoes do Claude. Devolve (caminho do pacote, numero de
    achados)."""
    pasta_job = Path(pasta_job)
    estado = contratos.ler(pasta_job / 'estado.json', 'estado/1')
    laudo = contratos.ler(pasta_job / 'laudo' / 'laudo.json', 'laudo/1')
    modo = modo_do_job(pasta_job, estado, teto)
    detector = detector or segredos.detector_padrao()
    # primeiro sem miniatura, so para saber quais camadas o detector bloqueia: elas nunca vao para a pasta
    _rascunho, achados = montar_pacote(laudo, modo, job_id=estado.get('job_id'), detector=detector)
    try:
        indice = mod_miniaturas.gravar_miniaturas(pasta_job, modo, laudo=laudo, detector=detector,
                                                  bloqueados={a.layer_id for a in achados if a.layer_id is not None})
    except mod_miniaturas.ErroMiniatura:
        # a copia nao bateu com a origem: a pasta ja foi apagada, e o pacote sai sem miniatura
        indice = None
    pacote, achados = montar_pacote(laudo, modo, job_id=estado.get('job_id'), detector=detector,
                                    miniaturas=(indice or {}).get('miniaturas'))
    destino = pasta_job / ARQUIVO_PACOTE
    contratos.gravar(destino, pacote, CONTRATO)
    if modo == 'c':
        apagar_escritos_do_claude(pasta_job)
    segredos.gravar_bloqueios(pasta_job, achados, comando='pacote')
    _registrar_exposto(pasta_job, pacote, indice)
    return destino, len(achados)


def fechar(pasta_job):
    """Apaga tudo o que o Claude le em sugestoes/ (os dois pacotes, a pasta das miniaturas e as sugestoes dele).
    Usado quando o pacote nao pode ser refeito: o job fica, para o Claude, sem conteudo nenhum."""
    pasta_job = Path(pasta_job)
    from desdobra.sugestao import specs as pacote_specs
    mod_miniaturas.gravar_miniaturas(pasta_job, 'c')
    _apagar_arquivo(pasta_job / ARQUIVO_PACOTE)
    _apagar_arquivo(pasta_job / pacote_specs.ARQUIVO_PACOTE)
    apagar_escritos_do_claude(pasta_job)


def refazer_pacotes(pasta_job, teto=None):
    """Refaz os dois pacotes (o deste modulo e o das specs) no modo efetivo de agora. Sem laudo (a fase ler ainda nao
    rodou), so a pasta das miniaturas some e nao ha pacote-modelo. Devolve as contagens do que foi feito."""
    from desdobra.sugestao import specs as pacote_specs
    pasta_job = Path(pasta_job)
    estado = contratos.ler(pasta_job / 'estado.json', 'estado/1')
    modo = modo_do_job(pasta_job, estado, teto)
    # contado antes de gravar_pacote, que tambem apaga as sugestoes no modo c
    apagadas = sum(1 for rel in ESCRITOS_DO_CLAUDE if (pasta_job / rel).is_file()) if modo == 'c' else 0
    r = {'modo': modo, 'camadas': 0, 'miniaturas': 0, 'segredos_bloqueados': 0, 'pacote_modelo': 0,
         'pacote_specs': 0, 'sugestoes_apagadas': apagadas}
    if _laudo_do_kv(pasta_job, estado):
        destino, n = gravar_pacote(pasta_job, teto=teto)
        p = contratos.ler(destino, CONTRATO)
        r.update(camadas=len(p['camadas']), miniaturas=len(p['miniaturas']), segredos_bloqueados=n, pacote_modelo=1)
    else:
        # sem laudo, ou com o laudo de um KV que ja foi trocado: nada do pacote velho fica legivel ate a fase ler
        # rodar de novo, nem as sugestoes do Claude feitas sobre ele
        mod_miniaturas.gravar_miniaturas(pasta_job, 'c')
        _apagar_arquivo(pasta_job / ARQUIVO_PACOTE)
        alvos = ESCRITOS_DO_CLAUDE if modo == 'c' else ESCRITOS_DO_CLAUDE[:2]
        r['sugestoes_apagadas'] = sum(_apagar_arquivo(pasta_job / rel) for rel in alvos)
    # o mapeamento do Claude e entrada da fase specs: quando ele sai (o modo c o apaga) com a fase em dia, a fase e
    # refeita aqui mesmo, sem as propostas dele (revisao da correcao A do M7c, E1). Com o job ocupado, a ErroJob sobe
    # e a conferencia seguinte refaz (_precisa_refazer, motivo 'specs')
    if _specs_so_pelo_mapeamento(pasta_job):
        _refazer_fase_specs(pasta_job, modo, estado.get('job_id'))
    destino_specs, n_specs = pacote_specs.refazer_pacote(pasta_job, modo, job_id=estado.get('job_id'))
    if destino_specs is not None:
        r['pacote_specs'] = 1
        r['segredos_bloqueados'] += n_specs
    return r


def _specs_so_pelo_mapeamento(pasta_job):
    """A fase specs foi concluida com o mapeamento do Claude, o mapeamento nao existe mais e ele e a unica entrada que
    mudou: refazer a fase agora so tira as propostas do Claude do rascunho, sem mascarar outra mudanca (a folha, as
    confirmacoes, a biblioteca). A conta cara (o hash das folhas) so roda quando o estado.json diz que a fase rodou
    com o mapeamento e o arquivo sumiu."""
    from desdobra.job import fases as mod_fases
    from desdobra.job import nucleo
    mapa = ARQUIVO_MAPEAMENTO.as_posix()
    if (pasta_job / ARQUIVO_MAPEAMENTO).exists():
        return False
    reg = nucleo.ler_estado(pasta_job)['fases'].get(mod_fases.FASE_SPECS.id) or {}
    gravado = reg.get('hash_entradas') or {}
    if reg.get('situacao') != 'concluida' or gravado.get(mapa) is None:
        return False
    fase = mod_fases.FASE_SPECS
    atual = nucleo.hashes_da_fase(pasta_job, fase, {fase.id: fase})
    mudaram = {k for k in set(atual) | set(gravado) if k not in fase.refeitas and atual.get(k) != gravado.get(k)}
    return mudaram == {mapa}


def _refazer_fase_specs(pasta_job, modo, job_id):
    """Refaz a fase specs no proprio processo, sob a trava do job, e grava a fase em dia (job.nucleo.renovar_fase),
    como faz o ato de spec da tela (desdobra.specs.confirmar.confirmar_da_tela). So quando _specs_so_pelo_mapeamento
    (conferido de novo dentro da trava): o rascunho sai sem as propostas do Claude, e o DA nunca precisa do terminal.
    O pacote das specs nao e gravado aqui: quem chama o refaz em seguida, no modo de agora."""
    from datetime import datetime

    from desdobra.job import nucleo
    from desdobra.specs import importar
    with nucleo.Trava(pasta_job):
        if not _specs_so_pelo_mapeamento(pasta_job):
            return
        agora = datetime.now().astimezone().isoformat(timespec='seconds')
        rascunho, _info = importar.montar(pasta_job, modo=modo, agora=agora, job_id=job_id)
        importar.gravar(pasta_job, rascunho)
        nucleo.renovar_fase(pasta_job, 'specs')
        nucleo.registrar_evento(pasta_job, 'specs_refeita_sem_mapeamento', modo=modo)


def _kv_do_estado(estado):
    """sha256 da entrada do KV no estado.json (entrada/kv.psd ou entrada/kv.psb), ou None."""
    for rel, info in (estado.get('entradas') or {}).items():
        if rel.startswith('entrada/kv.') and isinstance(info, dict):
            return info.get('sha256')
    return None


def _laudo_do_kv(pasta_job, estado):
    """O laudo do job existe e e do KV que esta no estado.json agora (sem KV registrado, vale o laudo que houver)."""
    arq = Path(pasta_job) / 'laudo' / 'laudo.json'
    if not arq.is_file():
        return False
    kv = _kv_do_estado(estado)
    if kv is None:
        return True
    laudo = contratos.ler(arq, 'laudo/1')
    return (laudo.get('origem') or {}).get('sha256') == kv


def _precisa_refazer(pasta_job, estado, modo):
    """Motivo para refazer os pacotes, ou None quando o que esta gravado ja e do modo e do KV de agora."""
    from desdobra import arquivos
    from desdobra.sugestao import specs as pacote_specs
    tem_pasta = (pasta_job / mod_miniaturas.PASTA).exists()
    if tem_pasta and modo != 'a':
        return 'modo'
    if modo == 'c' and any((pasta_job / rel).exists() for rel in ESCRITOS_DO_CLAUDE):
        return 'modo'
    if _specs_so_pelo_mapeamento(pasta_job):
        # o ato do modo apagou o mapeamento e nao conseguiu refazer a fase specs (job ocupado): refazer_pacotes refaz
        return 'specs'
    arq = pasta_job / ARQUIVO_PACOTE
    if arq.is_file():
        try:
            p = arquivos.ler_json(arq)
        except (OSError, ValueError):
            return 'ilegivel'
        if not isinstance(p, dict) or p.get('esquema') != CONTRATO:
            return 'contrato'
        if p.get('modo_dados') != modo:
            return 'modo'
        if modo == 'a' and bool(p.get('miniaturas')) != tem_pasta:
            return 'modo'
        kv = _kv_do_estado(estado)
        if kv is not None and p.get('arquivo_sha256') != kv:
            return 'kv'
    elif tem_pasta:
        return 'modo'
    elif _laudo_do_kv(pasta_job, estado):
        # os pacotes nao contam para a validade das fases (desdobra.job.fases, refeitas): o que sumiu (fechar, na
        # falha de um refazer) volta aqui, sem reler o PSD
        return 'falta'
    arq_specs = pasta_job / pacote_specs.ARQUIVO_PACOTE
    if arq_specs.is_file():
        try:
            ps = arquivos.ler_json(arq_specs)
        except (OSError, ValueError):
            return 'ilegivel'
        if not isinstance(ps, dict) or ps.get('modo_dados') != modo:
            return 'modo'
    elif (pasta_job / ARQUIVO_RASCUNHO_SPECS).is_file():
        return 'falta'
    return _conteudo_mexido(pasta_job, estado, modo)


def _conteudo_mexido(pasta_job, estado, modo):
    """'conteudo' quando um pacote gravado nao tem os bytes que o motor grava agora com o laudo do KV (e o indice das
    miniaturas) ou com o rascunho das specs, no modo de agora; senao None. Os pacotes nao contam para a validade das fases
    (desdobra.job.fases, refeitas), e e esta conferencia que pega o pacote mexido fora do motor (revisao da correcao A
    do M7c, E1). O pacote sem laudo do KV ou sem rascunho tambem conta como mexido: refazer o apaga."""
    from desdobra import arquivos
    from desdobra.specs import importar
    from desdobra.sugestao import specs as pacote_specs
    detector = segredos.detector_padrao()
    job_id = estado.get('job_id')
    arq = pasta_job / ARQUIVO_PACOTE
    if arq.is_file():
        if not _laudo_do_kv(pasta_job, estado):
            return 'conteudo'
        laudo = contratos.ler(pasta_job / 'laudo' / 'laudo.json', 'laudo/1')
        indice = None
        if modo == 'a' and (pasta_job / mod_miniaturas.ARQUIVO_INDICE).is_file():
            indice = arquivos.ler_json(pasta_job / mod_miniaturas.ARQUIVO_INDICE)
        miniaturas = indice.get('miniaturas') if isinstance(indice, dict) else None
        esperado, _achados = montar_pacote(laudo, modo, job_id=job_id, detector=detector, miniaturas=miniaturas)
        if not _bytes_do_motor(arq, esperado):
            return 'conteudo'
    arq_specs = pasta_job / pacote_specs.ARQUIVO_PACOTE
    if arq_specs.is_file():
        if not (pasta_job / ARQUIVO_RASCUNHO_SPECS).is_file():
            return 'conteudo'
        rascunho = contratos.ler(pasta_job / ARQUIVO_RASCUNHO_SPECS, importar.ESQUEMA)
        esperado, _achados = pacote_specs.montar_pacote(rascunho, modo, job_id=job_id, detector=detector)
        if not _bytes_do_motor(arq_specs, esperado):
            return 'conteudo'
    return None


def _bytes_do_motor(arq, esperado):
    """O arquivo tem exatamente os bytes que o motor grava para `esperado` (contratos.gravar, arquivos.para_json).
    Comparar o JSON lido nao basta: com uma chave repetida, a ultima vence no json.load, e os bytes que o Claude le
    trazem a primeira (revisao 2 da correcao A do M7c, E1)."""
    from desdobra import arquivos
    try:
        return Path(arq).read_bytes() == arquivos.para_json(esperado).encode('utf-8')
    except OSError:
        return False


def curar_specs(pasta_job, teto=None):
    """A tela (montagem e cada pedido do estado, que o servidor tambem faz antes de cada ato) se cura da fase specs
    atrasada so porque o mapeamento do Claude saiu (_specs_so_pelo_mapeamento): o ato do modo nao a refez porque outro
    processo segurava o job. Fora desse caso nao faz nada (a conta e barata: so le o estado.json e ve se o mapeamento
    existe). Nunca levanta excecao. Devolve True quando mexeu (conferir_modo)."""
    pasta_job = Path(pasta_job)
    try:
        if not _specs_so_pelo_mapeamento(pasta_job):
            return False
    except Exception:  # noqa: BLE001 - sem estado legivel, a montagem da tela diz o que houve
        return False
    return conferir_modo(pasta_job, teto)


def conferir_modo(pasta_job, teto=None):
    """Recalcula o modo efetivo com o teto da linha de comando e refaz os pacotes quando o gravado nao bate. Com o KV
    trocado e o laudo ainda do KV antigo, fecha tudo o que o Claude le ate a fase ler rodar de novo. Nunca levanta
    excecao: na falha, fecha. Devolve True quando mexeu em alguma coisa."""
    pasta_job = Path(pasta_job)
    try:
        estado = contratos.ler(pasta_job / 'estado.json', 'estado/1')
        modo = modo_do_job(pasta_job, estado, teto)
        motivo = _precisa_refazer(pasta_job, estado, modo)
        if motivo is None:
            return False
        refazer_pacotes(pasta_job, teto=teto)
        return True
    except Exception:  # noqa: BLE001 - na duvida, o Claude fica sem nada para ler
        try:
            fechar(pasta_job)
        except Exception:  # noqa: BLE001
            pass
        return True
