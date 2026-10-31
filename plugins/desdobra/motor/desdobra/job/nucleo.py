# -*- coding: utf-8 -*-
"""Pasta do job: criacao, entradas congeladas, estado, invalidacao por hash e a proxima fase.

Pasta do job (arquitetura-v1.md, 5.1):
    estado.json      estado/1, gravado so pelo motor, de forma atomica
    entrada/         kv.psd ou kv.psb, campanha/, specs/ e fontes/ (os arquivos de fonte enviados pela agencia,
                     M2); congelados por sha256 e so leitura. Sem arquivo de licencas (decisoes-v1.md, n. 19)
    laudo/           laudo.json e as pastas do leitor
    log/eventos.jsonl  so eventos e codigos, sem texto das pecas nem conteudo bruto
"""
import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid
from datetime import datetime
from pathlib import Path

from desdobra import __version__, contratos
from desdobra.arquivos import (PREFIXO_TEMPORARIO, eh_arquivo_de_fonte, eh_arquivo_do_sistema, gravar_bytes_atomico,
                               sha256_arquivo, sha256_caminho, tem_assinatura_psd, tornar_gravavel, tornar_somente_leitura)
from desdobra.job.fases import ESTEIRA, FASES_M1, FIM, validar_esteira  # noqa: F401 - FASES_M1 para os testes
from desdobra.resultado import MODOS_DADOS, Codigo, Resultado, modo_permitido

ESQUEMA_ESTADO = 'estado/1'
ARQUIVO_ESTADO = 'estado.json'
ARQUIVO_TRAVA = '.desdobra.trava'
PASTAS_DO_JOB = ('entrada', 'laudo', 'log')


class ErroJob(Exception):
    """Erro esperado, com codigo e o que fazer. A mensagem nunca leva conteudo do job."""

    def __init__(self, mensagem, codigo=Codigo.RECUSADO, o_que_fazer=None, situacao='recusado'):
        super().__init__(mensagem)
        self.codigo = codigo
        self.o_que_fazer = o_que_fazer
        self.situacao = situacao


def agora():
    return datetime.now().astimezone().isoformat(timespec='seconds')


# ------------------------------------------------------------------ estado, trava e log
def caminho_estado(pasta):
    return Path(pasta) / ARQUIVO_ESTADO


def conferir_job(pasta):
    """Erro de uso, com o mesmo o que fazer do job estado, quando a pasta nao e um job do desdobra."""
    if not caminho_estado(pasta).is_file():
        raise ErroJob('A pasta não tem estado.json: ela não é um job do desdobra.',
                      o_que_fazer='Confira a pasta do job ou crie o job com "desdobra job criar".')


def ler_estado(pasta):
    conferir_job(pasta)
    return contratos.ler(caminho_estado(pasta), ESQUEMA_ESTADO)


def gravar_estado(pasta, estado):
    estado['atualizado_em'] = agora()
    contratos.gravar(caminho_estado(pasta), estado, ESQUEMA_ESTADO)


def registrar_evento(pasta, evento, **campos):
    """Acrescenta uma linha a log/eventos.jsonl. So eventos, codigos e numeros; nunca texto de peca."""
    linha = {'quando': agora(), 'evento': evento}
    linha.update({k: v for k, v in campos.items() if v is not None})
    log = Path(pasta) / 'log'
    log.mkdir(exist_ok=True)
    with open(log / 'eventos.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps(linha, ensure_ascii=False) + '\n')


class Trava:
    """Impede dois processos do desdobra de mexer no mesmo job ao mesmo tempo."""

    def __init__(self, pasta):
        self.caminho = Path(pasta) / ARQUIVO_TRAVA

    def __enter__(self):
        conferir_job(self.caminho.parent)
        try:
            fd = os.open(self.caminho, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileNotFoundError:
            conferir_job(self.caminho.parent)
            raise
        except FileExistsError:
            raise ErroJob('Outro processo do desdobra está usando este job.', codigo=Codigo.OCUPADO,
                          o_que_fazer='Espere o outro comando terminar. Se nenhum desdobra estiver rodando, apague o '
                                      'arquivo %s da pasta do job e tente de novo.' % ARQUIVO_TRAVA,
                          situacao='erro') from None
        with os.fdopen(fd, 'w') as f:
            f.write(str(os.getpid()))
        return self

    def __exit__(self, *exc):
        try:
            self.caminho.unlink()
        except FileNotFoundError:
            pass
        return False


# ------------------------------------------------------------------ entradas congeladas
def _copiar_congelado(origem, destino):
    """Copia de forma atomica, confere o hash da copia contra a origem e deixa so leitura."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_name('%s%s.%d' % (PREFIXO_TEMPORARIO, destino.name, os.getpid()))
    shutil.copyfile(origem, temporario)
    sha_origem, sha_copia = sha256_arquivo(origem), sha256_arquivo(temporario)
    if sha_origem != sha_copia:
        temporario.unlink()
        raise ErroJob('A cópia da entrada saiu diferente da origem.', codigo=Codigo.ERRO_INTERNO, situacao='erro',
                      o_que_fazer='Confira o disco e tente de novo.')
    if destino.exists():
        tornar_gravavel(destino)
    os.replace(temporario, destino)
    tornar_somente_leitura(destino)
    return {'sha256': sha_copia, 'bytes': destino.stat().st_size, 'congelada_em': agora()}


def _arquivos_de(pasta):
    return sorted(p for p in Path(pasta).rglob('*') if p.is_file())


def _sem_arquivos_do_sistema(arquivos, ignorados):
    """Tira da lista o que o sistema grava sozinho numa pasta copiada (.DS_Store, Thumbs.db, desktop.ini e os
    AppleDouble ._* do Mac). Soma em ignorados[0] quantos ficaram de fora, para o log."""
    saida = []
    for p in arquivos:
        if eh_arquivo_do_sistema(p.name):
            ignorados[0] += 1
        else:
            saida.append(p)
    return saida


MENSAGEM_FONTE_FORA = ('A pasta de campanha ou de specs tem arquivo de fonte, ou um pacote com fonte dentro. Arquivo de '
                       'fonte só entra no job pela entrada própria, entrada/fontes/.')
O_QUE_FAZER_FONTE_FORA = ('Tire os arquivos de fonte e os pacotes com fontes dessa pasta e passe as fontes soltas (OTF, '
                          'TTF, TTC, WOFF ou WOFF2) em --fontes, e crie o job de novo.')


def _recusar_fontes(arquivos):
    for arq in arquivos:
        if eh_arquivo_de_fonte(arq):
            raise ErroJob(MENSAGEM_FONTE_FORA, o_que_fazer=O_QUE_FAZER_FONTE_FORA)


def _arquivos_de_fonte_oferecidos(origens, ignorados=None):
    """Arquivos de --fontes (arquivos soltos ou pastas; no destino ficam lado a lado). Devolve [(nome, caminho)]."""
    saida, nomes = [], set()
    ignorados = ignorados if ignorados is not None else [0]
    for origem in origens or ():
        origem = Path(origem).resolve()
        if origem.is_dir():
            lista = _sem_arquivos_do_sistema(_arquivos_de(origem), ignorados)
        elif origem.is_file():
            lista = _sem_arquivos_do_sistema([origem], ignorados)
        else:
            raise ErroJob('Um dos caminhos de --fontes não foi encontrado.',
                          o_que_fazer='Confira os caminhos passados em --fontes.')
        for p in lista:
            if p.name.casefold() in nomes:
                raise ErroJob('Dois arquivos de fonte têm o mesmo nome.',
                              o_que_fazer='Renomeie um deles: entrada/fontes/ guarda os arquivos lado a lado.')
            nomes.add(p.name.casefold())
            saida.append((p.name, p))
    return saida


def validar_fonte(caminho, pasta_trabalho):
    """Confere um arquivo para entrada/fontes/ (assinatura aqui; tabelas no filho isolado). ErroJob se recusado."""
    from desdobra import fontes
    _formato, recusa = fontes.validar_arquivo(caminho, pasta_trabalho)
    if recusa:
        raise ErroJob('Arquivo de fonte recusado: %s' % fontes.MENSAGENS_RECUSA.get(recusa, recusa),
                      o_que_fazer=fontes.O_QUE_FAZER_RECUSA)


def conferir_entradas(pasta, estado):
    """Confere se entrada/ esta como foi congelada. Devolve a lista de caminhos alterados, sumidos ou novos."""
    pasta = Path(pasta)
    problemas = []
    for rel, reg in estado['entradas'].items():
        p = pasta / rel
        if not p.is_file():
            problemas.append(rel)
        elif sha256_arquivo(p) != reg['sha256']:
            problemas.append(rel)
    conhecidos = set(estado['entradas'])
    for arq in _arquivos_de(pasta / 'entrada'):
        rel = arq.relative_to(pasta).as_posix()
        if rel not in conhecidos and not arq.name.startswith(PREFIXO_TEMPORARIO):
            problemas.append(rel)
    return problemas


# ------------------------------------------------------------------ hash das fases e invalidacao
def hash_padrao(pasta, padrao):
    """sha256 do que o padrao glob encontra na pasta do job. None se nao encontra nada."""
    pasta = Path(pasta)
    achados = sorted(p for p in pasta.glob(padrao) if not p.name.startswith(PREFIXO_TEMPORARIO))
    if not achados:
        return None
    if len(achados) == 1:
        return sha256_caminho(achados[0])
    h = hashlib.sha256()
    for p in achados:
        h.update(p.relative_to(pasta).as_posix().encode('utf-8') + b'\0' + (sha256_caminho(p) or '').encode('ascii') + b'\n')
    return h.hexdigest()


def padroes_da_fase(fase, por_id):
    padroes = list(fase.entradas)
    for d in fase.depende_de:
        padroes.extend(s for s in por_id[d].saidas if s not in padroes)
    return padroes


def hashes_da_fase(pasta, fase, por_id):
    return {p: hash_padrao(pasta, p) for p in padroes_da_fase(fase, por_id)}


def hashes_das_saidas(pasta, fase):
    return {s: hash_padrao(pasta, s) for s in fase.saidas}


def _registro_vazio():
    return {'situacao': 'pendente', 'hash_entradas': {}, 'tentativas': 0, 'codigo': None, 'inicio': None,
            'fim': None, 'duracao_s': None, 'motivo': None}


def avaliar(pasta, estado, fases):
    """Para cada fase, (valida, motivo). Valida = concluida, mesmas entradas e dependencias validas.

    Devolve tambem o conjunto das fases cujas entradas mudaram diretamente (para gravar como invalidadas)."""
    por_id = {f.id: f for f in fases}
    resultado, diretas = {}, {}
    for f in fases:
        reg = estado['fases'].get(f.id) or _registro_vazio()
        if reg['situacao'] != 'concluida':
            resultado[f.id] = (False, reg['situacao'])
            continue
        atual = hashes_da_fase(pasta, f, por_id)
        mudaram = sorted(k for k in set(atual) | set(reg['hash_entradas']) if atual.get(k) != reg['hash_entradas'].get(k))
        if mudaram:
            motivo = 'entradas mudaram: %s' % ', '.join(mudaram)
            resultado[f.id] = (False, motivo)
            diretas[f.id] = motivo
            continue
        # as saidas da propria fase: apagada ou mudada depois de concluida, a fase tem de rodar de novo
        if 'hash_saidas' in reg:
            saidas_agora = hashes_das_saidas(pasta, f)
            mexidas = sorted(s for s in set(saidas_agora) | set(reg['hash_saidas'])
                             if saidas_agora.get(s) != reg['hash_saidas'].get(s))
        else:
            mexidas = [s for s in f.saidas if hash_padrao(pasta, s) is None]
        if mexidas:
            motivo = 'saídas mudaram ou sumiram: %s' % ', '.join(mexidas)
            resultado[f.id] = (False, motivo)
            diretas[f.id] = motivo
            continue
        deps_invalidas = [d for d in f.depende_de if not resultado[d][0]]
        if deps_invalidas:
            resultado[f.id] = (False, 'depende de fase invalida: %s' % ', '.join(deps_invalidas))
            continue
        resultado[f.id] = (True, None)
    return resultado, diretas


def fases_invalidas(pasta, fases=ESTEIRA):
    """Conjunto das fases que nao estao validas agora (sem gravar nada)."""
    estado = ler_estado(pasta)
    avaliacao, _ = avaliar(pasta, estado, fases)
    return {k for k, (valida, _m) in avaliacao.items() if not valida}


def bloqueios_pendentes(estado, avaliacao, fases):
    """[(id da fase, bloqueio)] das fases validas que terminaram com bloqueio gravado (Fase.bloqueio_persiste)."""
    out = []
    for f in fases:
        reg = estado['fases'].get(f.id) or {}
        if avaliacao.get(f.id, (False, None))[0] and reg.get('bloqueio'):
            out.append((f.id, reg['bloqueio']))
    return out


def calcular_proxima(estado, avaliacao, fases):
    for f in fases:
        valida, _ = avaliacao[f.id]
        if valida:
            continue
        reg = estado['fases'].get(f.id) or _registro_vazio()
        if reg['situacao'] == 'falhou':
            return {'tipo': 'falha', 'fase': f.id,
                    'o_que_fazer': f.o_que_fazer or 'A fase %s falhou. Corrija e rode "desdobra job proxima".' % f.id}
        if f.tipo == 'portao':
            return {'tipo': 'portao', 'fase': f.id, 'o_que_fazer': f.o_que_fazer}
        return {'tipo': 'fase', 'fase': f.id,
                'o_que_fazer': 'Rode "desdobra job proxima" para a fase %s (%s).' % (f.id, f.descricao)}
    pendentes = bloqueios_pendentes(estado, avaliacao, fases)
    if pendentes:
        fid, bloqueio = pendentes[0]
        return {'tipo': 'bloqueio', 'fase': fid, 'o_que_fazer': '%s %s' % (MENSAGEM_BLOQUEIO % fid, bloqueio['o_que_fazer'])}
    return {'tipo': 'concluido', 'fase': None, 'o_que_fazer': FIM}


MENSAGEM_BLOQUEIO = ('A fase %s terminou com bloqueio, que continua pendente: o job só fica concluído quando o DA '
                     'resolver.')


def _bloqueio_do_envelope(envelope):
    """O que fica gravado no estado de uma fase que terminou com bloqueio: a situacao, o o_que_fazer (texto fixo do
    motor) e as contagens inteiras do envelope dela. Nunca conteudo do job."""
    contagens = {k: v for k, v in (envelope.get('contagens') or {}).items()
                 if isinstance(v, int) and not isinstance(v, bool)}
    return {'situacao': envelope.get('situacao'), 'o_que_fazer': envelope.get('o_que_fazer') or '',
            'contagens': contagens}


# ------------------------------------------------------------------ criar
def criar(pasta, psd, modo_dados, teto_modo_dados=None, campanha=None, specs=None, fases=ESTEIRA, fontes=None):
    validar_esteira(fases)
    # caminhos absolutos: as fases rodam em subprocesso com outra pasta de trabalho
    pasta, psd = Path(pasta).resolve(), Path(psd).resolve()
    if modo_dados not in MODOS_DADOS:
        raise ErroJob('Escolha o modo de dados do job: a, b ou c.', codigo=Codigo.USO,
                      o_que_fazer='Use --modo-dados com a, b ou c. Não há valor inicial.')
    if teto_modo_dados is not None and not modo_permitido(modo_dados, teto_modo_dados):
        raise ErroJob('O modo de dados escolhido é mais aberto que o teto autorizado pela agência.',
                      o_que_fazer='Escolha um modo igual ou mais fechado que o teto (%s).' % teto_modo_dados)
    if pasta.exists() and (not pasta.is_dir() or any(pasta.iterdir())):
        raise ErroJob('A pasta do job já existe e não está vazia.',
                      o_que_fazer='Escolha uma pasta nova ou vazia para o job.')
    if not psd.is_file():
        raise ErroJob('O arquivo do KV não foi encontrado.', o_que_fazer='Confira o caminho passado em --kv.')
    extensao = psd.suffix.lower()
    if extensao not in ('.psd', '.psb') or not tem_assinatura_psd(psd):
        raise ErroJob('O arquivo do KV não é um PSD nem um PSB.',
                      o_que_fazer='Passe em --kv o arquivo .psd ou .psb salvo pelo Photoshop.')
    pastas_extra = {}
    ignorados = [0]
    for nome, origem in (('campanha', campanha), ('specs', specs)):
        if origem is None:
            continue
        origem = Path(origem).resolve()
        if not origem.is_dir():
            raise ErroJob('A pasta de %s não foi encontrada.' % nome, o_que_fazer='Confira o caminho passado em --%s.' % nome)
        arquivos = _sem_arquivos_do_sistema(_arquivos_de(origem), ignorados)
        _recusar_fontes(arquivos)
        pastas_extra[nome] = (origem, arquivos)
    oferecidas = _arquivos_de_fonte_oferecidos(fontes, ignorados)

    existia = pasta.exists()
    for sub in PASTAS_DO_JOB:
        (pasta / sub).mkdir(parents=True, exist_ok=True)
    try:
        # cada fonte e conferida no filho isolado antes de entrar (variable font e arquivo que nao abre ficam fora)
        for i, (_nome, arq) in enumerate(oferecidas, 1):
            validar_fonte(arq, pasta / 'fontes' / '.trabalho' / str(i))
    except ErroJob:
        _desfazer_criacao(pasta, existia)
        raise
    shutil.rmtree(pasta / 'fontes', ignore_errors=True)
    entradas = {}
    rel_kv = 'entrada/kv%s' % extensao
    entradas[rel_kv] = _copiar_congelado(psd, pasta / rel_kv)
    for nome, (origem, arquivos) in pastas_extra.items():
        for arq in arquivos:
            rel = 'entrada/%s/%s' % (nome, arq.relative_to(origem).as_posix())
            entradas[rel] = _copiar_congelado(arq, pasta / rel)
    for nome, arq in oferecidas:
        entradas['entrada/fontes/%s' % nome] = _copiar_congelado(arq, pasta / 'entrada' / 'fontes' / nome)

    instante = agora()
    estado = {'esquema': ESQUEMA_ESTADO, 'job_id': uuid.uuid4().hex, 'criado_em': instante, 'atualizado_em': instante,
              'motor_versao': __version__, 'modo_dados': modo_dados, 'teto_modo_dados': teto_modo_dados,
              'entradas': entradas, 'fases': {f.id: _registro_vazio() for f in fases},
              'proxima': {'tipo': 'fase', 'fase': None, 'o_que_fazer': ''}}
    avaliacao, _ = avaliar(pasta, estado, fases)
    estado['proxima'] = calcular_proxima(estado, avaliacao, fases)
    gravar_estado(pasta, estado)
    registrar_evento(pasta, 'job_criado', job_id=estado['job_id'], n_entradas=len(entradas), n_fontes=len(oferecidas))
    if ignorados[0]:
        registrar_evento(pasta, 'arquivos_do_sistema_ignorados', n=ignorados[0])
    return estado


def _desfazer_criacao(pasta, existia):
    """Apaga o que o job criar fez antes de uma recusa (a pasta era nova ou vazia)."""
    for p in sorted(Path(pasta).rglob('*'), reverse=True):
        try:
            if p.is_dir():
                p.rmdir()
            else:
                tornar_gravavel(p)
                p.unlink()
        except OSError:
            pass
    if not existia:
        try:
            Path(pasta).rmdir()
        except OSError:
            pass


# ------------------------------------------------------------------ trocar entrada
def trocar_entrada(pasta, rel, novo, fases=ESTEIRA):
    pasta, novo = Path(pasta).resolve(), Path(novo).resolve()
    with Trava(pasta):
        estado = ler_estado(pasta)
        rel = Path(rel).as_posix()
        if not rel.startswith('entrada/') or '..' in Path(rel).parts:
            raise ErroJob('O caminho da entrada tem de começar com entrada/.', codigo=Codigo.USO,
                          o_que_fazer='Use o caminho relativo à pasta do job, por exemplo entrada/kv.psd.')
        de_fonte = rel.startswith('entrada/fontes/')
        if de_fonte and (len(Path(rel).parts) != 3 or Path(rel).name.startswith(PREFIXO_TEMPORARIO)):  # numero-neutro: entrada/fontes/<arquivo>
            raise ErroJob('A fonte entra direto em entrada/fontes/, sem subpasta.', codigo=Codigo.USO,
                          o_que_fazer='Use entrada/fontes/<nome do arquivo>.')
        if rel not in estado['entradas'] and not de_fonte and not rel.startswith(('entrada/campanha/', 'entrada/specs/')):
            raise ErroJob('Só dá para trocar uma entrada que já existe ou acrescentar em entrada/campanha, '
                          'entrada/specs ou entrada/fontes.',
                          codigo=Codigo.USO, o_que_fazer='Confira o caminho com "desdobra job estado".')
        # no Windows (e no disco padrao do Mac) dois nomes que so diferem na caixa sao o mesmo arquivo: a mesma
        # conferencia casefold do job criar evita que o arquivo novo escreva por cima de outra entrada
        if any(r != rel and r.casefold() == rel.casefold() for r in estado['entradas']):
            raise ErroJob('Já há no job uma entrada com este nome em outra caixa (maiúsculas e minúsculas).',
                          codigo=Codigo.USO,
                          o_que_fazer='Para trocar, use o caminho com a mesma caixa da entrada que já está no job; para '
                                      'acrescentar, dê outro nome ao arquivo novo.')
        if not novo.is_file():
            raise ErroJob('O arquivo novo não foi encontrado.', o_que_fazer='Confira o caminho do arquivo novo.')
        if de_fonte:
            validar_fonte(novo, pasta / 'fontes' / '.trabalho-troca')
        elif eh_arquivo_de_fonte(novo):
            raise ErroJob('O arquivo novo é um arquivo de fonte, ou um pacote com fonte dentro. Fonte só entra em '
                          'entrada/fontes/.',
                          o_que_fazer='Troque a fonte com "desdobra job trocar-entrada <pasta> entrada/fontes/<arquivo> '
                                      '<arquivo>".')
        if rel.startswith('entrada/kv') and (Path(rel).suffix.lower() != novo.suffix.lower() or not tem_assinatura_psd(novo)):
            raise ErroJob('O KV novo tem de ser do mesmo tipo do anterior (%s).' % Path(rel).suffix,
                          o_que_fazer='Salve o KV no mesmo formato ou crie um job novo.')
        estado['entradas'][rel] = _copiar_congelado(novo, pasta / rel)
        avaliacao, diretas = avaliar(pasta, estado, fases)
        _marcar_invalidadas(estado, diretas)
        estado['proxima'] = calcular_proxima(estado, avaliacao, fases)
        gravar_estado(pasta, estado)
        registrar_evento(pasta, 'entrada_trocada', invalidadas=sorted(k for k, (v, _m) in avaliacao.items() if not v))
        return estado, avaliacao


# ------------------------------------------------------------------ remover entrada
def remover_entrada(pasta, rel, fases=ESTEIRA):
    """Tira um arquivo de entrada/fontes/ (por exemplo, quando dois arquivos tem o mesmo nome PostScript e o DA
    escolhe qual vale). Apaga so a copia congelada no job, tira do estado e invalida pelo hash as fases que usam
    entrada/fontes (fontes e, em cadeia, laudo-fontes e ds)."""
    pasta = Path(pasta).resolve()
    with Trava(pasta):
        estado = ler_estado(pasta)
        rel = Path(rel).as_posix()
        partes = Path(rel).parts
        if not rel.startswith('entrada/fontes/') or len(partes) != 3 or '..' in partes:  # numero-neutro: entrada/fontes/<arquivo>
            raise ErroJob('Só dá para remover um arquivo de fonte, direto em entrada/fontes/.', codigo=Codigo.USO,
                          o_que_fazer='Use entrada/fontes/<nome do arquivo>, com o nome exato do arquivo no job.')
        if rel not in estado['entradas']:
            raise ErroJob('O job não tem esta entrada.', codigo=Codigo.USO,
                          o_que_fazer='Confira o nome do arquivo, com a mesma caixa (maiúsculas e minúsculas) do que '
                                      'foi passado em --fontes.')
        arq = pasta / rel
        if arq.exists():
            tornar_gravavel(arq)
            arq.unlink()
        del estado['entradas'][rel]
        avaliacao, diretas = avaliar(pasta, estado, fases)
        _marcar_invalidadas(estado, diretas)
        estado['proxima'] = calcular_proxima(estado, avaliacao, fases)
        gravar_estado(pasta, estado)
        registrar_evento(pasta, 'entrada_removida', invalidadas=sorted(k for k, (v, _m) in avaliacao.items() if not v))
        return estado, avaliacao


def _marcar_invalidadas(estado, diretas):
    for fid, motivo in diretas.items():
        reg = estado['fases'].setdefault(fid, _registro_vazio())
        reg['situacao'] = 'invalidada'
        reg['motivo'] = motivo
        reg.pop('bloqueio', None)


# ------------------------------------------------------------------ proxima
def _executar_comando(argv, pasta):
    proc = subprocess.run(argv, cwd=str(pasta), capture_output=True)
    return proc.returncode, proc.stdout, proc.stderr


def proxima(pasta, fases=ESTEIRA, todas=False, executor=_executar_comando, opcoes_da_fase=()):
    """Roda a proxima fase (ou todas ate um portao, falha ou fim, com todas=True). Devolve um Resultado.

    opcoes_da_fase: argumentos acrescentados ao comando das fases do motor (por exemplo o teto de memoria que o
    DA confirmou depois de uma leitura parada num limite a calibrar). A fase grava as opcoes com que rodou; dadas
    opcoes diferentes das gravadas, a fase concluida fica invalidada e roda de novo com elas."""
    validar_esteira(fases)
    pasta = Path(pasta).resolve()
    por_id = {f.id: f for f in fases}
    opcoes_da_fase = [str(o) for o in opcoes_da_fase]
    linhas = []
    rodadas = []
    # com --todas, a fase que termina com bloqueio (codigo 0) nao para a esteira, mas o envelope final diz isso
    envelope_bloqueio, fase_bloqueio = None, None
    with Trava(pasta):
        estado = ler_estado(pasta)
        problemas = conferir_entradas(pasta, estado)
        if problemas:
            registrar_evento(pasta, 'entrada_alterada_fora_do_motor', n=len(problemas))
            raise ErroJob('Uma entrada congelada do job mudou, sumiu ou apareceu fora do motor (%d arquivo(s)).' % len(problemas),
                          o_que_fazer='Restaure a pasta entrada/ como estava ou troque a entrada com '
                                      '"desdobra job trocar-entrada", que registra a troca e invalida só as fases '
                                      'que dependem dela.')
        if opcoes_da_fase:
            invalidadas = _invalidar_por_opcoes(estado, fases, opcoes_da_fase)
            if invalidadas:
                registrar_evento(pasta, 'fases_invalidadas', fases=invalidadas, motivo='opcoes_da_fase')
        while True:
            avaliacao, diretas = avaliar(pasta, estado, fases)
            if diretas:
                _marcar_invalidadas(estado, diretas)
                registrar_evento(pasta, 'fases_invalidadas', fases=sorted(diretas))
            alvo = next((f for f in fases if not avaliacao[f.id][0]), None)
            if alvo is None:
                estado['proxima'] = calcular_proxima(estado, avaliacao, fases)
                gravar_estado(pasta, estado)
                return _resultado(estado, pasta, 'concluido', Codigo.OK, fase_bloqueio, rodadas, linhas,
                                  envelope_bloqueio, avaliacao, fases)
            reg = estado['fases'].setdefault(alvo.id, _registro_vazio())
            if alvo.tipo == 'portao':
                if alvo.cumprido(pasta):
                    reg.update(situacao='concluida', hash_entradas=hashes_da_fase(pasta, alvo, por_id), codigo=0,
                               hash_saidas=hashes_das_saidas(pasta, alvo), fim=agora(), motivo=None)
                    registrar_evento(pasta, 'portao_cumprido', fase=alvo.id)
                    gravar_estado(pasta, estado)
                    continue
                reg['situacao'] = 'aguardando_portao'
                avaliacao, _ = avaliar(pasta, estado, fases)
                estado['proxima'] = calcular_proxima(estado, avaliacao, fases)
                gravar_estado(pasta, estado)
                registrar_evento(pasta, 'parou_no_portao', fase=alvo.id)
                return _resultado(estado, pasta, 'portao', Codigo.PORTAO, alvo.id, rodadas, linhas,
                                  avaliacao=avaliacao, fases=fases)
            # fase do motor
            antes = hashes_da_fase(pasta, alvo, por_id)
            reg.update(situacao='pendente', tentativas=reg['tentativas'] + 1, inicio=agora(), fim=None, codigo=None,
                       motivo=None)
            reg.pop('bloqueio', None)
            gravar_estado(pasta, estado)
            registrar_evento(pasta, 'fase_iniciada', fase=alvo.id)
            t0 = time.monotonic()
            codigo, saida, erro = executor(list(alvo.comando(pasta)) + list(opcoes_da_fase), pasta)
            duracao = round(time.monotonic() - t0, 3)
            reg.update(fim=agora(), duracao_s=duracao, codigo=codigo, opcoes=list(opcoes_da_fase))
            rodadas.append(alvo.id)
            ultimo_envelope = envelope_da_saida(saida)
            if ultimo_envelope and ultimo_envelope.get('o_que_fazer'):
                linhas.append('Fase %s: %s' % (alvo.id, ultimo_envelope['o_que_fazer']))
            if codigo != 0:
                reg.update(situacao='falhou', motivo='código de retorno %d' % codigo)
                linhas.extend(_ultimas_linhas(erro))
            else:
                faltando = [s for s in alvo.saidas if hash_padrao(pasta, s) is None]
                depois = hashes_da_fase(pasta, alvo, por_id)
                if faltando:
                    reg.update(situacao='falhou', motivo='saída ausente: %s' % ', '.join(faltando))
                elif depois != antes:
                    reg.update(situacao='falhou', motivo='uma entrada mudou durante a fase')
                else:
                    reg.update(situacao='concluida', hash_entradas=antes, hash_saidas=hashes_das_saidas(pasta, alvo),
                               motivo=None)
                    if alvo.bloqueio_persiste and (ultimo_envelope or {}).get('situacao') in SITUACOES_DE_BLOQUEIO:
                        reg['bloqueio'] = _bloqueio_do_envelope(ultimo_envelope)
            registrar_evento(pasta, 'fase_terminada', fase=alvo.id, codigo=codigo, duracao_s=duracao,
                             situacao=reg['situacao'])
            avaliacao, _ = avaliar(pasta, estado, fases)
            estado['proxima'] = calcular_proxima(estado, avaliacao, fases)
            gravar_estado(pasta, estado)
            if reg['situacao'] != 'concluida':
                return _resultado(estado, pasta, 'erro', Codigo.FASE_FALHOU, alvo.id, rodadas, linhas,
                                  ultimo_envelope, avaliacao, fases)
            if not todas:
                return _resultado(estado, pasta, 'ok', Codigo.OK, alvo.id, rodadas, linhas, ultimo_envelope,
                                  avaliacao, fases)
            if (ultimo_envelope or {}).get('situacao') in SITUACOES_DE_BLOQUEIO:
                envelope_bloqueio, fase_bloqueio = ultimo_envelope, alvo.id


SITUACOES_DE_BLOQUEIO = ('ok_com_bloqueio', 'bloqueado')
MOTIVO_OPCOES = 'o teto confirmado pelo DA mudou: a fase roda de novo com ele'


def _invalidar_por_opcoes(estado, fases, opcoes):
    """Invalida as fases do motor concluidas com opcoes diferentes das dadas agora. Devolve os ids."""
    out = []
    for f in fases:
        reg = estado['fases'].get(f.id)
        if f.tipo != 'fase' or not reg or reg['situacao'] != 'concluida':
            continue
        if list(reg.get('opcoes') or []) != list(opcoes):
            reg['situacao'] = 'invalidada'
            reg['motivo'] = MOTIVO_OPCOES
            out.append(f.id)
    return out


def _ultimas_linhas(erro):
    """Fim do erro do subprocesso, so para o modo humano (nunca vai para o envelope nem para o log)."""
    texto = (erro or b'').decode('utf-8', 'replace').strip().splitlines()
    return texto[-8:]


def envelope_da_saida(saida):
    """O envelope (ultima linha JSON com esquema envelope/1) que a fase imprimiu, ou None."""
    if not saida:
        return None
    texto = saida.decode('utf-8', 'replace') if isinstance(saida, bytes) else str(saida)
    for linha in reversed(texto.strip().splitlines()):
        linha = linha.strip()
        if not linha.startswith('{'):
            continue
        try:
            dados = json.loads(linha)
        except ValueError:
            return None
        return dados if isinstance(dados, dict) and dados.get('esquema') == 'envelope/1' else None
    return None


def _resultado(estado, pasta, situacao, codigo, fase, rodadas, linhas, envelope_fase=None, avaliacao=None, fases=()):
    """Resultado do job proxima. Com o envelope da ultima fase rodada, repassa contagens, ids, numeros e conteudo
    dela (o conteudo ja veio filtrado pelo modo do job e passa de novo pelo envelope do proprio job proxima)."""
    contagens, ids, numeros, conteudo = {}, {}, {}, {}
    ja_bloqueados = 0
    if envelope_fase:
        ja_bloqueados = int(envelope_fase.get('segredos_bloqueados') or 0)
        if ja_bloqueados:
            linhas = list(linhas) + ['O detector de segredos segurou %d item(ns) nesta fase. O detalhe, só para o DA, '
                                     'está em sugestoes/segredos-bloqueados.json da pasta do job.' % ja_bloqueados]
        contagens.update(envelope_fase.get('contagens') or {})
        ids.update(envelope_fase.get('ids') or {})
        numeros.update(envelope_fase.get('numeros') or {})
        conteudo = dict(envelope_fase.get('conteudo') or {})
        contagens['codigo_da_fase'] = int(envelope_fase.get('codigo') or 0)
    for reg in estado['fases'].values():
        contagens['fases_' + reg['situacao']] = contagens.get('fases_' + reg['situacao'], 0) + 1
    contagens['fases_rodadas_agora'] = len(rodadas)
    ids['job_id'] = estado['job_id']
    o_que_fazer = estado['proxima']['o_que_fazer']
    # bloqueio gravado por uma fase (Fase.bloqueio_persiste): continua visivel em todo job proxima seguinte
    pendentes = bloqueios_pendentes(estado, avaliacao, fases) if avaliacao is not None else []
    contagens['bloqueios_pendentes'] = len(pendentes)
    if pendentes:
        for k, v in pendentes[0][1].get('contagens', {}).items():
            contagens.setdefault(k, v)
    if pendentes and situacao == 'concluido':
        # a esteira chegou ao fim, mas o job nao esta concluido: vale o bloqueio pendente
        situacao, fase = 'ok_com_bloqueio', pendentes[0][0]
        linhas = list(linhas) + [MENSAGEM_BLOQUEIO % fase]
    # a fase terminou com bloqueio que pede decisao do DA: o envelope do job proxima diz isso, e nao so "ok"
    situacao_fase = (envelope_fase or {}).get('situacao')
    if situacao_fase in SITUACOES_DE_BLOQUEIO and situacao in ('ok', 'concluido', 'erro'):
        situacao = 'bloqueado' if situacao == 'erro' else 'ok_com_bloqueio'
        o_que_fazer = envelope_fase.get('o_que_fazer') or o_que_fazer
    elif situacao == 'erro' and (envelope_fase or {}).get('codigo') == int(Codigo.AUDITORIA):
        # alarme do gancho de auditoria na fase: vale o o_que_fazer da auditoria, que a fase mandou
        o_que_fazer = envelope_fase.get('o_que_fazer') or o_que_fazer
    elif pendentes and situacao == 'ok':
        fid, bloqueio = pendentes[0]
        situacao = 'ok_com_bloqueio'
        o_que_fazer = '%s %s %s' % (o_que_fazer, MENSAGEM_BLOQUEIO % fid, bloqueio['o_que_fazer'])
        linhas = list(linhas) + [MENSAGEM_BLOQUEIO % fid]
    return Resultado(comando='job proxima', codigo=int(codigo), situacao=situacao, fase=fase,
                     o_que_fazer=o_que_fazer, contagens=contagens, ids=ids, numeros=numeros,
                     conteudo=conteudo, pasta_job=Path(pasta), linhas_humanas=linhas,
                     segredos_ja_bloqueados=ja_bloqueados)
