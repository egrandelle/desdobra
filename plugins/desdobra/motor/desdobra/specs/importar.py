# -*- coding: utf-8 -*-
"""Importacao das folhas de spec do job: "desdobra spec importar" e a fase "specs" da esteira.

Le as folhas de entrada/specs/ (cada uma no filho isolado, desdobra.specs.leitura), monta o modelo em 4 niveis
(desdobra.specs.modelo) e grava:
  - specs/rascunho.json (spec/1, tipo rascunho): tudo o que a folha diz, com trecho e recorte por valor;
  - specs/formatos-do-job.json (spec/1, tipo formatos_do_job): so os valores que o DA confirmou;
  - sugestoes/pacote-specs.json (pacote-specs/1): os trechos para o Claude propor o mapeamento, pelo modo de dados.

Veiculador: cada subpasta de entrada/specs/ e um veiculador (todas as folhas dela juntas, como as paginas salvas
da Globo); folha solta direto em entrada/specs/ e um veiculador sozinha. Folha cujo sha256 esta num perfil da
biblioteca (biblioteca-specs/) usa o veiculador e a curadoria de mapeamento desse perfil.

Entram, nesta ordem: as leituras das folhas, as tabelas por tamanho, o mapeamento da biblioteca, as propostas do
Claude (sugestoes/mapeamento-specs.json, so nos modos a e b), os valores digitados pelo DA e as confirmacoes do DA
(specs/confirmacoes.json). O rascunho e funcao dessas entradas: rodar de novo da o mesmo resultado.
"""
from pathlib import Path

from desdobra import PASTA_PLUGIN, __version__, contratos
from desdobra.arquivos import PREFIXO_TEMPORARIO, eh_arquivo_do_sistema, sha256_arquivo
from desdobra.specs import leitura as mod_leitura
from desdobra.specs import modelo

ESQUEMA = modelo.ESQUEMA
ESQUEMA_CONFIRMACOES = 'spec-confirmacoes/1'
ESQUEMA_MAPEAMENTO = 'mapeamento-specs/1'
ARQUIVO_RASCUNHO = Path('specs') / 'rascunho.json'
ARQUIVO_FORMATOS = Path('specs') / 'formatos-do-job.json'
ARQUIVO_CONFIRMACOES = Path('specs') / 'confirmacoes.json'
ARQUIVO_MAPEAMENTO = Path('sugestoes') / 'mapeamento-specs.json'
PASTA_BRUTO = Path('specs') / 'bruto'
PASTA_TRABALHO = Path('specs') / '.trabalho'
PASTA_BIBLIOTECA = PASTA_PLUGIN / 'biblioteca-specs'


class ErroSpec(Exception):
    def __init__(self, mensagem, o_que_fazer=None):
        super().__init__(mensagem)
        self.o_que_fazer = o_que_fazer or mensagem


def id_da_folha(sha256, rel):
    """Id curto da folha, unico por caminho: a mesma folha em duas subpastas sao duas folhas (dois veiculadores)."""
    import hashlib
    h = hashlib.sha256(('%s\0%s' % (sha256, rel)).encode('utf-8')).hexdigest()
    return 'f' + h[:8]  # numero-neutro: prefixo do sha256 so como id curto


def folhas_do_job(pasta):
    """[(caminho relativo, id do veiculador)] das folhas em entrada/specs/, em ordem."""
    base = Path(pasta) / 'entrada' / 'specs'
    if not base.is_dir():
        return []
    saida = []
    for arq in sorted(p for p in base.rglob('*') if p.is_file()):
        if arq.name.startswith(PREFIXO_TEMPORARIO) or eh_arquivo_do_sistema(arq.name):
            continue
        rel = arq.relative_to(base)
        vid = modelo.slug_seguro(rel.parts[0]) if len(rel.parts) > 1 else modelo.slug_seguro(arq.stem)
        saida.append((arq.relative_to(pasta).as_posix(), vid))
    return saida


# ------------------------------------------------------------------ biblioteca
def carregar_biblioteca(pasta=None):
    """{sha256 da folha: perfil} dos perfis versionados de biblioteca-specs/ (spec/1, tipo perfil)."""
    pasta = Path(pasta) if pasta else PASTA_BIBLIOTECA
    por_sha = {}
    for arq in sorted(pasta.glob('*.json')):
        perfil = modelo.completar_documento(contratos.ler(arq, ESQUEMA))
        if perfil['tipo'] != 'perfil':
            continue
        perfil['_arquivo'] = arq.name
        for f in perfil['folhas']:
            por_sha[f['sha256']] = perfil
    return por_sha


def perfil_da_biblioteca(caminho):
    """O perfil lido e completo: o campo que o arquivo nao traz volta como registro sem valor."""
    return modelo.completar_documento(contratos.ler(caminho, ESQUEMA))


def _mapeamento_no_job(perfil, folhas_no_job):
    """A curadoria do perfil cita a folha pelo id do perfil; no job, a mesma folha (mesmo sha256) tem outro id."""
    sha_do_id = {f['id']: f['sha256'] for f in perfil['folhas']}
    saida = []
    for p in perfil.get('mapeamento') or []:
        for fid in folhas_no_job.get(sha_do_id.get(p['folha']), []):
            saida.append(dict(p, folha=fid))
    return saida


def hash_da_biblioteca(pasta=None):
    """sha256 dos perfis da biblioteca (entra no hash da fase specs: perfil novo refaz o rascunho)."""
    from desdobra.arquivos import sha256_pasta
    return sha256_pasta(Path(pasta) if pasta else PASTA_BIBLIOTECA)


def hash_dos_limites():
    """sha256 dos limites que a leitura e o modelo de specs usam (specs.* e os do isolador)."""
    import hashlib
    import json

    from desdobra import limites
    usados = {k: v.valor for k, v in limites.carregar().items() if k.startswith(('specs.', 'isolador.'))}
    return hashlib.sha256(json.dumps(usados, sort_keys=True).encode('utf-8')).hexdigest()


# ------------------------------------------------------------------ entradas do DA e do Claude
def ler_confirmacoes(pasta):
    arq = Path(pasta) / ARQUIVO_CONFIRMACOES
    if not arq.is_file():
        return {'esquema': ESQUEMA_CONFIRMACOES, 'acoes': []}
    return contratos.ler(arq, ESQUEMA_CONFIRMACOES)


def ler_mapeamento(pasta):
    arq = Path(pasta) / ARQUIVO_MAPEAMENTO
    if not arq.is_file():
        return None
    return contratos.ler(arq, ESQUEMA_MAPEAMENTO)


def _versoes(anterior, grupos, biblioteca_por_vid):
    """Um perfil por veiculador, com versao: folha nova (outro conjunto de sha256) gera a versao seguinte, e a
    anterior fica no historico (arquitetura-v1.md, 4.8: cada folha nova gera um perfil novo, com versao)."""
    antes = {p['id']: p for p in (anterior or {}).get('perfis') or []}
    perfis = []
    for vid, shas in sorted(grupos.items()):
        shas = sorted(shas)
        velho = antes.get(vid)
        if velho is None:
            versao, historico = 1, []
        elif velho['folhas_sha256'] == shas:
            versao, historico = velho['versao'], velho['historico']
        else:
            versao = velho['versao'] + 1
            historico = velho['historico'] + [{'versao': velho['versao'], 'folhas_sha256': velho['folhas_sha256']}]
        bib = biblioteca_por_vid.get(vid)
        perfis.append({'id': vid, 'versao': versao, 'folhas_sha256': shas, 'historico': historico,
                       'biblioteca': None if bib is None else {'arquivo': bib['_arquivo'],
                                                               'perfil': bib['perfis'][0]['id'],
                                                               'versao': bib['perfis'][0]['versao']}})
    return perfis


# ------------------------------------------------------------------ montagem do job
def montar(pasta, *, modo='c', plat=None, biblioteca=None, agora=None, job_id=None):
    """Le as folhas do job e devolve (rascunho, informacoes). Nao grava o rascunho (quem grava e gravar)."""
    pasta = Path(pasta).resolve()
    biblioteca = carregar_biblioteca() if biblioteca is None else biblioteca
    m = modelo.Montagem()
    info = {'folhas_recusadas': 0, 'recusas': [], 'propostas_do_modelo': 0, 'propostas_ignoradas_modo_c': 0}
    grupos, bib_por_vid, usados, por_perfil = {}, {}, [], {}
    for i, (rel, vid) in enumerate(folhas_do_job(pasta), 1):
        arq = pasta / rel
        sha = sha256_arquivo(arq)
        formato = mod_leitura.formato_da_folha(arq) or 'recusada'
        r = mod_leitura.ler(arq, pasta / PASTA_BRUTO / ('%s-%s' % (sha, formato)), pasta / PASTA_TRABALHO / str(i),
                            plat=plat)
        if r['situacao'] != 'lida':
            info['folhas_recusadas'] += 1
            info['recusas'].append(r['recusa']['tipo'])
            continue
        perfil = biblioteca.get(sha)
        if perfil is not None:
            vid = perfil['veiculadores'][0]['id']
            bib_por_vid[vid] = perfil
            if perfil not in usados:
                usados.append(perfil)
        leitura = r['leitura']
        for p in leitura['paginas']:
            if p['recorte']:
                p['recorte'] = (PASTA_BRUTO / ('%s-%s' % (sha, leitura['formato'])) / p['recorte']).as_posix()
        meta = {'id': id_da_folha(sha, rel), 'arquivo': rel, 'sha256': sha, 'bytes': arq.stat().st_size,
                'formato': leitura['formato']}
        m.adicionar_folha(meta, leitura, vid)
        grupos.setdefault(vid, set()).add(sha)
        if perfil is not None:
            por_perfil.setdefault(id(perfil), {}).setdefault(sha, []).append(meta['id'])
    _limpar_trabalho(pasta)
    m.aplicar_tetos()
    for perfil in usados:
        m.aplicar_propostas(_mapeamento_no_job(perfil, por_perfil.get(id(perfil), {})), 'biblioteca')
    mapeamento = ler_mapeamento(pasta)
    if mapeamento is not None:
        if modo == 'c':
            # no modo c o Claude nao viu trecho nenhum: proposta dele nao entra
            info['propostas_ignoradas_modo_c'] = len(mapeamento['propostas'])
        else:
            antes = m.contagem['propostas_aplicadas']
            m.aplicar_propostas(mapeamento['propostas'], 'proposta_do_modelo')
            info['propostas_do_modelo'] = m.contagem['propostas_aplicadas'] - antes
    acoes = ler_confirmacoes(pasta)['acoes']
    dig_ok, dig_ign = modelo.aplicar_digitados(m, acoes)
    m.conferir_unidades()
    m.fechar_chaves()
    m.completar_tudo()
    anterior = None
    if (pasta / ARQUIVO_RASCUNHO).is_file():
        try:
            anterior = contratos.ler(pasta / ARQUIVO_RASCUNHO, ESQUEMA)
        except contratos.ErroContrato:
            anterior = None
    perfis = _versoes(anterior, grupos, bib_por_vid)
    doc = modelo.documento(m, perfis=perfis, job_id=job_id, motor_versao=__version__, gerado_em=agora)
    ok, ign = modelo.aplicar_acoes(doc, acoes)
    # a medida escolhida pelo DA num formato de medida divergente da a chave dele (revisao dos becos, D2)
    modelo.chaves_depois_das_escolhas(doc)
    doc['resumo'] = modelo.resumo(doc)
    modelo._situacao_das_folhas(doc)
    info.update(acoes_aplicadas=ok + dig_ok, acoes_ignoradas=ign + dig_ign,
                propostas_aplicadas=m.contagem['propostas_aplicadas'],
                propostas_ignoradas=m.contagem['propostas_ignoradas'])
    erros = modelo.conferir_literais(doc)
    if erros:
        raise AssertionError('número sem trecho no rascunho: %d valor(es)' % len(erros))
    return doc, info


def _limpar_trabalho(pasta):
    import shutil
    shutil.rmtree(Path(pasta) / PASTA_TRABALHO, ignore_errors=True)


def gravar(pasta, rascunho):
    """Grava o rascunho e os formatos do job (so confirmados). Devolve os formatos do job."""
    pasta = Path(pasta)
    contratos.gravar(pasta / ARQUIVO_RASCUNHO, rascunho, ESQUEMA)
    formatos = modelo.formatos_do_job(rascunho)
    contratos.gravar(pasta / ARQUIVO_FORMATOS, formatos, ESQUEMA)
    return formatos


def importar(pasta, *, plat=None, biblioteca=None):
    """A fase specs inteira: monta, grava o rascunho, os formatos do job e o pacote para o Claude."""
    from datetime import datetime

    from desdobra.sugestao import pacote as mod_pacote
    from desdobra.sugestao import specs as pacote_specs
    pasta = Path(pasta).resolve()
    estado = contratos.ler(pasta / 'estado.json', 'estado/1')
    modo = mod_pacote.modo_do_job(pasta, estado)
    agora = datetime.now().astimezone().isoformat(timespec='seconds')
    rascunho, info = montar(pasta, modo=modo, plat=plat, biblioteca=biblioteca, agora=agora, job_id=estado['job_id'])
    formatos = gravar(pasta, rascunho)
    _caminho, n_segredos = pacote_specs.gravar_pacote(pasta, rascunho, modo, job_id=estado['job_id'])
    info['segredos_bloqueados'] = n_segredos
    return rascunho, formatos, info
