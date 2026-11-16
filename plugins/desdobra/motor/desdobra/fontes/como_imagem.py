# -*- coding: utf-8 -*-
"""Texto como imagem por decisao do DA (0.9.1): o KV tem texto vivo, mas a agencia nunca recebeu o arquivo da fonte.

O DA declara na tela, por face que falta (o nome PostScript do PSD), "Nao tenho esta fonte: usar o texto como imagem"
(ato texto_como_imagem do passo 1, desdobra.tela.atos; comando COMANDO em humano.ATOS_DA_TELA, so pelo Disparo da
tela). A declaracao fica em briefing/texto-como-imagem.json (texto-como-imagem/1), que o gancho do plugin nega ao
Claude, como todo briefing/**.

Regras:
  - a conferencia de fontes (fontes/conferencia.json) continua a fonte unica: aplicar() rebaixa a aviso, nos pares
    (camada, nome PostScript) sem face e com tinta, os motivos arquivo_faltando, nome_ps_sem_par e face_divergente da
    face declarada, poe o motivo texto_como_imagem e a decisao texto_como_imagem_do_da, e grava o bloco
    texto_como_imagem com as camadas que vao como imagem. Derivacao, render, tela e entrega leem essa lista (camadas);
  - a face declaravel e a que nao tem arquivo, ou tem um arquivo que nao confere (revisao do 0.9.1: o arquivo de outra
    versao, com largura divergente ou glifo faltando, deixava o DA sem saida). A declaracao rebaixa todo motivo
    bloqueante dos pares da camada atingida;
  - a camada vai inteira: os outros trechos dela (outras faces) tambem deixam de bloquear, porque o Chromium nao
    desenha mais essa camada. Mas so a face declarada vira decisao do DA na segunda passada do laudo: a outra face
    continua faltando na tela. Os motivos das camadas sem declaracao continuam bloqueando;
  - a declaracao vale para o KV em que foi feita (kv_sha256, o PSD de entrada/kv/; revisao do 0.9.1: o laudo.json
    muda a cada leitura, pelos recursos medidos, e nao serve de ancora) e so enquanto a face nao confere: o arquivo que
    chega e confere faz a face voltar a valer, e o nome vai para caidas (a tela avisa). O arquivo que chega e nao
    confere deixa a declaracao valendo. O motor nunca reescreve o arquivo do DA; tirar a declaracao e outro clique;
  - aplicar() guarda no bloco o que rebaixou (rebaixados), e remover() desfaz exatamente: o ato reaplica sem rodar o
    Chromium de novo (reaplicar), refaz a segunda passada do laudo e o design system e renova as fases que estavam em
    dia, como o ato de spec da tela;
  - para a classificacao de dados nada muda: laudo/laudo.json continua com a camada de texto, e o pacote e as
    miniaturas do modo a seguem tratando-a como texto (decisao 192).
"""
import copy
from pathlib import Path

from desdobra import arquivos, contratos

ARQUIVO = Path('briefing') / 'texto-como-imagem.json'
ESQUEMA = 'texto-como-imagem/1'
COMANDO = 'fonte como imagem'
# os motivos da face sem arquivo que a declaracao do DA resolve
CODIGOS = ('arquivo_faltando', 'nome_ps_sem_par', 'face_divergente')
DECISAO = 'texto_como_imagem_do_da'
MOTIVO = 'texto_como_imagem'
REGISTRO_RENDER = 'texto_como_imagem_por_decisao_do_da'
ACOES = ('declarar', 'desfazer')
ORIGEM_DA = 'da'
# as fases que o ato refaz no proprio processo, na ordem da esteira
FASES = ('fontes', 'laudo-fontes', 'ds')
DESCRICAO_MOTIVO = ('O DA decidiu, na tela, que esta camada vai como imagem: os pixels do PSD, sem a fonte. O texto '
                    'não se edita nem quebra linha, e escala como imagem.')


class ErroComoImagem(Exception):
    """A declaracao pedida nao vale agora (face que nao falta, camada sem pixels, face nao declarada)."""


# ------------------------------------------------------------------ leitura
def ler(pasta):
    """A declaracao gravada, ou None (sem arquivo ou fora do contrato)."""
    arq = Path(pasta) / ARQUIVO
    if not arq.is_file():
        return None
    try:
        return contratos.ler(arq, ESQUEMA)
    except (contratos.ErroContrato, OSError, ValueError):
        return None


def _laudo_sha(pasta):
    arq = Path(pasta) / 'laudo' / 'laudo.json'
    return arquivos.sha256_arquivo(arq) if arq.is_file() else None


def _kv_sha(pasta):
    """O sha256 do PSD de entrada/kv/ no estado do job, ou None."""
    try:
        estado = contratos.ler(Path(pasta) / 'estado.json', 'estado/1')
    except (contratos.ErroContrato, OSError, ValueError):
        return None
    rel = next((r for r in sorted(estado['entradas']) if r.startswith('entrada/kv')), None)
    return estado['entradas'][rel]['sha256'] if rel else None


def vale_para(declaracao, kv_sha):
    """A declaracao foi feita para este KV (o mesmo PSD, por kv_sha256). Pura."""
    return bool(declaracao) and kv_sha is not None and declaracao.get('kv_sha256') == kv_sha


def vigente(pasta):
    """A declaracao gravada, so se ela for do KV de agora; senao None."""
    d = ler(pasta)
    return d if vale_para(d, _kv_sha(pasta)) else None


def _conferencia(pasta):
    from desdobra.fontes import conferencia
    arq = Path(pasta) / conferencia.ARQUIVO
    if not arq.is_file():
        return None
    try:
        return contratos.ler(arq, conferencia.ESQUEMA)
    except (contratos.ErroContrato, OSError, ValueError):
        return None


def bloco(pasta):
    """O bloco texto_como_imagem da conferencia de agora (so a do laudo de agora), ou None."""
    conf = _conferencia(pasta)
    if conf is None or conf.get('laudo_sha256') != _laudo_sha(pasta):
        return None
    return conf.get('texto_como_imagem')


def camadas(pasta):
    """Os layer_ids das camadas de texto que vao como imagem, pela conferencia do laudo de agora."""
    b = bloco(pasta)
    return frozenset(int(x) for x in (b or {}).get('camadas') or [])


# ------------------------------------------------------------------ a conferencia com e sem a declaracao (puras)
def _com_tinta(item):
    return not any(m['codigo'] == 'so_em_espaco' for m in item['motivos'])


def _pendente(item):
    """O par com tinta que a conferencia bloqueia: sem arquivo (CODIGOS) ou com um arquivo que nao confere."""
    return _com_tinta(item) and any(m['situacao'] == 'bloqueante' for m in item['motivos'])


def _resumo(conf, n_camadas=None):
    from desdobra.fontes import conferencia
    r = conferencia._resumo(conf.get('faces') or [], conf.get('camadas') or [], conf.get('arquivos') or [],
                            conf.get('cache') or {'copias_encontradas': None, 'feito': False})
    if n_camadas is not None:
        r['textos_como_imagem'] = n_camadas
    return r


def remover(conf):
    """A conferencia sem a declaracao aplicada: desfaz exatamente o que aplicar() rebaixou. Pura."""
    from desdobra.fontes import conferencia
    novo = copy.deepcopy(conf)
    b = novo.pop('texto_como_imagem', None)
    if not b:
        return novo
    for r in b.get('rebaixados') or []:
        item = next((i for i in novo['camadas'] if i['layer_id'] == r['layer_id'] and i['nome_ps'] == r['nome_ps']),
                    None)
        if item is None:
            continue
        item['motivos'] = [m for m in item['motivos'] if m['codigo'] != MOTIVO]
        for k in r['indices']:
            if 0 <= k < len(item['motivos']):
                item['motivos'][k]['situacao'] = 'bloqueante'
        item['decisao'] = r.get('decisao')
        item['situacao'] = conferencia.pior(item['motivos'])
    novo['resumo'] = _resumo(novo)
    return novo


def aplicar(conf, declaracao):
    """A conferencia com a declaracao do DA (ver o cabecalho). conf pode vir com ou sem uma declaracao aplicada antes
    (ela e tirada primeiro). Quem chama passa so a declaracao do KV de agora (vigente). Pura."""
    from desdobra.fontes import conferencia
    novo = remover(conf)
    if not declaracao:
        return novo
    pedidas = [f for f in declaracao.get('faces') or [] if isinstance(f, dict) and isinstance(f.get('nome_ps'), str)]
    if not pedidas:
        return novo
    efetivas, caidas = [], []
    for f in pedidas:
        itens = [i for i in novo['camadas'] if i['nome_ps'] == f['nome_ps']]
        if any(_pendente(i) for i in itens):
            # sem arquivo, ou com um arquivo que nao confere: a declaracao continua valendo
            efetivas.append(f)
        elif any(i['face_id'] is not None for i in itens):
            # chegou o arquivo e ele confere: a face volta a ser texto vivo
            caidas.append(f['nome_ps'])
    nomes = {f['nome_ps'] for f in efetivas}
    alvo = sorted({i['layer_id'] for i in novo['camadas'] if i['nome_ps'] in nomes and _pendente(i)})
    rebaixados = []
    for item in novo['camadas']:
        if item['layer_id'] not in alvo:
            continue
        indices = [k for k, m in enumerate(item['motivos']) if m['situacao'] == 'bloqueante']
        for k in indices:
            item['motivos'][k]['situacao'] = 'aviso'
        item['motivos'].append({'codigo': MOTIVO, 'situacao': 'aviso', 'descricao': DESCRICAO_MOTIVO,
                                'medida': None, 'limite': None})
        rebaixados.append({'layer_id': item['layer_id'], 'nome_ps': item['nome_ps'], 'indices': indices,
                           'decisao': item.get('decisao')})
        item['decisao'] = DECISAO
        item['situacao'] = conferencia.pior(item['motivos'])
    origens = {f.get('origem') for f in efetivas}
    novo['texto_como_imagem'] = {
        'arquivo': ARQUIVO.as_posix(), 'origem': ORIGEM_DA if origens <= {ORIGEM_DA} else 'fixture_de_teste',
        'faces': [f['nome_ps'] for f in efetivas], 'caidas': caidas, 'camadas': alvo, 'rebaixados': rebaixados}
    novo['resumo'] = _resumo(novo, len(alvo))
    return novo


# ------------------------------------------------------------------ o que o DA pode declarar agora
def _pixels_por_camada(pasta, laudo):
    est = Path(pasta) / 'laudo' / 'bruto' / laudo['origem']['sha256'] / 'estrutura.json'
    try:
        regs = arquivos.ler_json(est).get('camadas') or [] if est.is_file() else []
    except (OSError, ValueError):
        regs = []
    return {r['layer_id']: bool((r.get('pixels') or {}).get('asset_sha256')) for r in regs
            if isinstance(r, dict) and isinstance(r.get('layer_id'), int)}


def declaraveis(pasta):
    """[{'nome_ps', 'camadas': [{'layer_id', 'nome', 'tem_pixels'}], 'declaravel'}] das faces sem arquivo, ou com
    arquivo que nao confere, da conferencia de agora (sem a declaracao aplicada). declaravel: toda camada atingida tem os pixels gravados no PSD
    (sem eles, a camada nao tem o que desenhar)."""
    conf = _conferencia(pasta)
    sha = _laudo_sha(pasta)
    if conf is None or conf.get('laudo_sha256') != sha:
        return []
    base = remover(conf)
    try:
        laudo = contratos.ler(Path(pasta) / 'laudo' / 'laudo.json', 'laudo/1')
    except (contratos.ErroContrato, OSError, ValueError):
        return []
    nomes = {c['identidade']['layer_id']: c.get('nome') or '' for c in laudo['camadas']}
    pixels = _pixels_por_camada(pasta, laudo)
    saida, vistos = [], []
    for item in base['camadas']:
        if item['nome_ps'] not in vistos:
            vistos.append(item['nome_ps'])
    for ps in vistos:
        itens = [i for i in base['camadas'] if i['nome_ps'] == ps]
        lids = sorted({i['layer_id'] for i in itens if _pendente(i)})
        if not lids:
            continue
        cams = [{'layer_id': lid, 'nome': nomes.get(lid, ''), 'tem_pixels': bool(pixels.get(lid))} for lid in lids]
        saida.append({'nome_ps': ps, 'camadas': cams, 'declaravel': all(c['tem_pixels'] for c in cams),
                      'com_arquivo': any(i['face_id'] is not None for i in itens)})
    return saida


def declarada(pasta, nome_ps):
    """A face esta na declaracao do KV de agora (efetiva ou caida)."""
    d = vigente(pasta)
    return bool(d) and any(f['nome_ps'] == nome_ps for f in d['faces'])


# ------------------------------------------------------------------ gravacao (so o Disparo da tela)
def gravar(pasta, nome_ps, acao, *, disparo):
    """Grava a declaracao do DA (acao 'declarar') ou a tira ('desfazer'), e reaplica. disparo: o da tela
    (humano.exigir_tela(COMANDO, ...)), gasto aqui. ErroComoImagem quando a face nao e declaravel agora, ou nao esta
    declarada no desfazer."""
    from desdobra import humano
    from desdobra.job import nucleo
    humano.conferir(disparo, COMANDO, consumir=True)
    if acao not in ACOES or not isinstance(nome_ps, str) or not nome_ps:
        raise ErroComoImagem('acao_invalida')
    pasta = Path(pasta).resolve()
    with nucleo.Trava(pasta):
        estado = contratos.ler(pasta / 'estado.json', 'estado/1')
        sha = _laudo_sha(pasta)
        kv_sha = _kv_sha(pasta)
        em_dia = {f: nucleo.fase_valida(pasta, f) for f in FASES}
        atual = ler(pasta)
        if atual is not None and not vale_para(atual, kv_sha):
            # o KV mudou: a declaracao de antes nao vale para este PSD; o historico fica
            atual = dict(atual, faces=[])
        faces = list((atual or {}).get('faces') or [])
        historico = list((atual or {}).get('historico') or [])
        reg = disparo.registro()
        por = {'usuario': reg['usuario'], 'maquina': reg['maquina'], 'meio': reg['meio'], 'quando': reg['quando']}
        if acao == 'declarar':
            alvo = next((d for d in declaraveis(pasta) if d['nome_ps'] == nome_ps and d['declaravel']), None)
            if alvo is None:
                raise ErroComoImagem('face_nao_declaravel')
            faces = [f for f in faces if f['nome_ps'] != nome_ps]
            faces.append({'nome_ps': nome_ps, 'camadas': [c['layer_id'] for c in alvo['camadas']],
                          'origem': disparo.origem, 'decidido_por': por})
        else:
            if not any(f['nome_ps'] == nome_ps for f in faces):
                raise ErroComoImagem('face_nao_declarada')
            faces = [f for f in faces if f['nome_ps'] != nome_ps]
        historico.append({'acao': acao, 'nome_ps': nome_ps, 'origem': disparo.origem, 'por': por})
        dados = {'esquema': ESQUEMA, 'job_id': estado['job_id'], 'laudo_sha256': sha, 'kv_sha256': kv_sha,
                 'faces': faces, 'historico': historico}
        contratos.gravar(pasta / ARQUIVO, dados, ESQUEMA)
        nucleo.registrar_evento(pasta, 'texto_como_imagem', acao=acao, faces=len(faces), origem=disparo.origem)
        reaplicar(pasta, em_dia)
    return dados


def reaplicar(pasta, em_dia):
    """Refaz, no proprio processo e sem Chromium, a conferencia com a declaracao de agora, a segunda passada do laudo e
    o design system, e renova as fases que estavam em dia antes do ato (em_dia: {fase: bool}). A fase fontes leva o
    bloqueio de agora (ou fica sem ele). Quem chama segura a trava do job. Se algo falhar no meio, as fases ficam
    desatualizadas e o seguir do job refaz tudo pela conferencia inteira, que le a declaracao."""
    from desdobra import ds as mod_ds
    from desdobra import fontes as mod_fontes
    from desdobra.fontes import conferencia
    from desdobra.job import nucleo
    from desdobra.laudo import fontes as segunda
    pasta = Path(pasta)
    conf = _conferencia(pasta)
    sha = _laudo_sha(pasta)
    if conf is None or conf.get('laudo_sha256') != sha:
        return None
    novo = aplicar(conf, vigente(pasta))
    arq_conf = pasta / conferencia.ARQUIVO
    contratos.gravar(arq_conf, novo, conferencia.ESQUEMA)
    if em_dia.get('fontes'):
        nucleo.renovar_fase(pasta, 'fontes', bloqueio=mod_fontes.bloqueio_da_conferencia(novo))
    if em_dia.get('laudo-fontes'):
        laudo = contratos.ler(pasta / 'laudo' / 'laudo.json', 'laudo/1')
        lf = segunda.aplicar_conferencia(laudo, novo, arquivos.sha256_arquivo(arq_conf), sha)
        contratos.gravar(pasta / mod_fontes.ARQUIVO_LAUDO_FONTES, lf, 'laudo/1')
        nucleo.renovar_fase(pasta, 'laudo-fontes')
    if em_dia.get('ds'):
        try:
            mod_ds.executar_montar(pasta)
        except Exception:  # noqa: BLE001 - a fase ds fica desatualizada, e o seguir do job a refaz
            return novo
        nucleo.renovar_fase(pasta, 'ds')
    return novo
