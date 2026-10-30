# -*- coding: utf-8 -*-
"""desdobra regressao: roda a leitura no corpus e compara com a linha de base da sonda 1.26.0.

    desdobra regressao --corpus <pasta dos PSD> --linha-de-base <pasta com <slug>/laudo.json da sonda>
                       --saida <pasta> [--paralelo N] [--filtro TEXTO ...] [--sem-rodar]

Os caminhos entram so por argumento; nenhum vai para o repositorio. Para cada arquivo, a leitura avulsa grava
em <saida>/<slug>/, e o comparador confere execucao, prova de pixel e, por camada, situacao, caixa, tipo,
visibilidade e texto (docs/m1-interfaces.md, 11). Saida: <saida>/regressao-<data>.json (contrato
regressao/1) e <saida>/regressao-<data>.md (resumo legivel). Codigo 0 quando nada piorou. Contam como piora:
arquivo que piorou (execucao, prova de pixel ou camada mais grave sem causa especifica), falha de seguranca,
arquivo da linha de base que sumiu do corpus e arquivo do corpus sem linha de base.

Partes:
  mapeamento.py  formato antigo da sonda e laudo/1 para a mesma forma normalizada;
  comparar.py    o comparador e as causas registradas;
  executar.py    a lista do corpus, a agenda por tamanho e a chamada da leitura;
  relatorio.py   o JSON e o resumo.
"""
import os
import time
from pathlib import Path

from desdobra import PASTA_PLUGIN, __version__, contratos, limites
from desdobra.resultado import Codigo, Resultado
from desdobra.regressao import comparar, executar, mapeamento, relatorio

CONTRATO = 'regressao/1'
CODIGO_PIOROU = getattr(Codigo, 'REGRESSAO_PIOROU', Codigo.FASE_FALHOU)


def ler_base(linha_de_base, slug):
    """Forma normalizada da linha de base de um slug, ou None se nao ha laudo legivel."""
    caminho = Path(linha_de_base) / slug / 'laudo.json'
    if not caminho.is_file():
        return None
    try:
        from desdobra.arquivos import ler_json
        return mapeamento.normalizar(ler_json(caminho))
    except (OSError, ValueError):
        return None


def execucao_da_base(linha_de_base):
    """Tempo de relogio e paralelo da rodada da linha de base (execucao.json da sonda), quando existir."""
    caminho = Path(linha_de_base) / 'execucao.json'
    try:
        from desdobra.arquivos import ler_json
        dados = ler_json(caminho)
    except (OSError, ValueError):
        return None
    dur, par = dados.get('duracao_s'), dados.get('paralelo_max')
    return {'duracao_s': dur if isinstance(dur, (int, float)) else None,
            'paralelo': par if isinstance(par, int) else None}


def slugs_da_base(linha_de_base):
    pasta = Path(linha_de_base)
    return sorted(p.name for p in pasta.iterdir() if p.is_dir() and (p / 'laudo.json').is_file())


def normalizar_retorno(retorno):
    laudo, execucao = retorno.get('laudo'), retorno['execucao']
    if laudo is None:
        return mapeamento.normalizado_sem_laudo(execucao)
    return mapeamento.normalizar_laudo(laudo, execucao)


def executar_regressao(corpus, linha_de_base, saida, *, paralelo=1, filtros=(), sem_rodar=False, rodar=None,
                       verificar_job=None):
    """Roda e compara. Devolve (relatorio, caminho do json, caminho do resumo).

    verificar_job: funcao (item, pasta) que roda o caminho do job no modo c num arquivo pequeno e devolve a
    varredura; o padrao, quando a regressao roda a leitura de verdade, e executar.verificar_job_modo_c."""
    inicio = time.monotonic()
    # caminhos absolutos desde o inicio: a leitura de cada arquivo roda num subprocesso com cwd em <saida>/<slug>
    corpus, linha_de_base, saida = Path(corpus).resolve(), Path(linha_de_base).resolve(), Path(saida).resolve()
    saida.mkdir(parents=True, exist_ok=True)
    itens = executar.listar_corpus(corpus)
    if filtros:
        itens = [i for i in itens if any(f.lower() in i.relativo.lower() or f.lower() in i.slug for f in filtros)]
    if sem_rodar:
        retornos = {i.slug: executar.ler_existente(i, saida / i.slug) for i in itens}
    else:
        retornos = executar.rodar_todos(itens, saida, paralelo=paralelo, rodar=rodar)

    grande = limites.valor('regressao.arquivo_grande_bytes')
    arquivos = {}
    for item in itens:
        agora = normalizar_retorno(retornos[item.slug])
        base = ler_base(linha_de_base, item.slug)
        cabeca = {'bytes': item.bytes, 'grande': item.bytes > grande}
        if base is None:
            arquivos[item.slug] = dict(cabeca, situacao='sem_base', execucao_agora=agora['execucao'],
                                       prova_pixel_agora=agora['prova_pixel'])
            continue
        arquivos[item.slug] = dict(cabeca, situacao='comparado', **comparar.comparar_arquivo(base, agora))
        if retornos[item.slug].get('verificacoes') is not None:
            arquivos[item.slug]['verificacoes'] = retornos[item.slug]['verificacoes']
    if verificar_job is None and not sem_rodar and rodar is None:
        verificar_job = executar.verificar_job_modo_c
    job_nao_rodou = False
    if verificar_job is not None:
        # o menor arquivo comparado que leu sem erro: o caminho do job no modo c, com stdout e stderr varridos
        candidatos = sorted((i for i in itens if (arquivos.get(i.slug) or {}).get('situacao') == 'comparado'
                             and arquivos[i.slug]['execucao']['agora'] == 'ok'), key=lambda i: i.bytes)
        if candidatos:
            item = candidatos[0]
            verif = arquivos[item.slug].setdefault('verificacoes', {})
            verif['job_modo_c'] = verificar_job(item, saida / item.slug)
        else:
            # sem arquivo que leu ok, o caminho do job nao foi varrido: isso nunca vale como 0 achado
            job_nao_rodou = True
    if not filtros:
        for slug in slugs_da_base(linha_de_base):
            if slug not in arquivos:
                arquivos[slug] = {'situacao': 'so_na_base'}

    tot = comparar.totais(arquivos)
    tot['verificacoes'] = comparar.totais_verificacoes(arquivos)
    tot['verificacoes']['job_modo_c_nao_rodou'] = int(job_nao_rodou)
    tot['falhas_de_seguranca'] = comparar.falhas_de_seguranca(tot['verificacoes'])
    piorou = (tot['arquivos_que_pioraram'] > 0 or tot['falhas_de_seguranca'] > 0 or tot['so_na_base'] > 0
              or tot['sem_base'] > 0)
    rel = {
        'esquema': CONTRATO,
        'gerado_em': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'motor': __version__,
        'modo': 'sem_rodar' if sem_rodar else 'rodou',
        'paralelo': int(paralelo),
        'filtros': list(filtros),
        'duracao_s': round(time.monotonic() - inicio, 2),  # numero-neutro: exibicao
        'base_execucao': execucao_da_base(linha_de_base),
        'limites': [limites.obter('regressao.arquivo_grande_bytes').citacao(),
                    limites.obter('prova_pixel.limiar_diferenca').citacao(),
                    limites.obter('regressao.tolerancia_prova_pixel_pct').citacao(),
                    limites.obter('regressao.varredura_min_caracteres').citacao()],
        'causas': comparar.CAUSAS,
        'arquivos': arquivos,
        'totais': tot,
        'resultado': 'piorou' if piorou else 'nada_piorou',
    }
    data = time.strftime('%Y%m%d-%H%M%S')
    caminho_json = saida / ('regressao-%s.json' % data)
    caminho_md = saida / ('regressao-%s.md' % data)
    contratos.gravar(caminho_json, rel, CONTRATO)
    relatorio.gravar_resumo(caminho_md, rel)
    return rel, caminho_json, caminho_md


# ------------------------------------------------------------------ CLI
def registrar(subparsers):
    p = subparsers.add_parser('regressao', help='Roda a leitura no corpus e compara com a linha de base da sonda')
    p.add_argument('--corpus', required=True, help='Pasta com os PSD e PSB do corpus (só leitura)')
    p.add_argument('--linha-de-base', required=True, dest='linha_de_base',
                   help='Pasta com <slug>/laudo.json da sonda com psd-tools 1.26.0')
    p.add_argument('--saida', required=True, help='Pasta onde ficam as leituras e o relatório')
    p.add_argument('--paralelo', type=int, default=1,
                   help='Quantas leituras de arquivos pequenos rodam ao mesmo tempo (os grandes rodam sozinhos)')
    p.add_argument('--filtro', action='append', default=[], help='Só os arquivos cujo caminho ou slug contém o texto')
    p.add_argument('--sem-rodar', action='store_true', dest='sem_rodar',
                   help='Não roda a leitura: compara os laudos que já estão na pasta de saída')
    p.set_defaults(executar=_executar, nome_comando='regressao')


def _erro_de_uso(texto):
    return Resultado(comando='regressao', codigo=int(Codigo.USO), situacao='erro', o_que_fazer=texto,
                     linhas_humanas=[texto])


def raiz_do_repositorio():
    """Pasta do repositorio de onde o plugin roda (<repositorio>/plugins/desdobra): a primeira, subindo da pasta do
    plugin ate dois niveis, com .git ou com .claude-plugin/marketplace.json; sem nenhuma, a pasta do plugin."""
    for pasta in (PASTA_PLUGIN, PASTA_PLUGIN.parent, PASTA_PLUGIN.parent.parent):
        if (pasta / '.git').exists() or (pasta / '.claude-plugin' / 'marketplace.json').is_file():
            return pasta
    return PASTA_PLUGIN


def _dentro_de(caminho, pasta):
    caminho = Path(os.path.normcase(str(Path(caminho).resolve())))
    pasta = Path(os.path.normcase(str(Path(pasta).resolve())))
    return caminho == pasta or pasta in caminho.parents


def _executar(args):
    if _dentro_de(args.saida, raiz_do_repositorio()) or _dentro_de(args.saida, PASTA_PLUGIN):
        return _erro_de_uso('A pasta de saída fica dentro do repositório do plugin, e o relatório da regressão leva '
                            'os nomes dos arquivos do corpus. Passe em --saida uma pasta fora do repositório.')
    if not Path(args.corpus).is_dir():
        return _erro_de_uso('A pasta do corpus não existe. Confira o caminho passado em --corpus.')
    if not Path(args.linha_de_base).is_dir():
        return _erro_de_uso('A pasta da linha de base não existe. Confira o caminho passado em --linha-de-base.')
    if args.paralelo < 1:
        return _erro_de_uso('O valor de --paralelo tem de ser 1 ou mais.')
    rel, caminho_json, caminho_md = executar_regressao(args.corpus, args.linha_de_base, args.saida,
                                                        paralelo=args.paralelo, filtros=tuple(args.filtro),
                                                        sem_rodar=args.sem_rodar)
    tot = rel['totais']
    piorou = rel['resultado'] == 'piorou'
    if not rel['arquivos']:
        o_que_fazer = 'Nenhum PSD ou PSB foi achado no corpus. Confira a pasta passada em --corpus.'
    elif piorou:
        o_que_fazer = ('Algum arquivo piorou contra a linha de base. Abra o resumo regressao-<data>.md na pasta de '
                       'saída, explique cada piora e não aceite a versão até resolver.')
    elif tot['sem_causa']:
        o_que_fazer = ('Nada piorou, mas há diferenças sem causa registrada. Explique cada uma no resumo '
                       'regressao-<data>.md da pasta de saída e leve para aprovação.')
    else:
        o_que_fazer = 'Nada piorou e toda diferença tem causa registrada.'
    contagens = {k: v for k, v in tot.items() if isinstance(v, int)}
    contagens.update({'verificacao_' + k: v for k, v in tot['verificacoes'].items()})
    numeros = {'tempo_' + k: v for k, v in tot['tempo_total_s'].items()}
    numeros['duracao_s'] = rel['duracao_s']
    linhas = relatorio.linhas_humanas(rel) + ['', 'Relatório: %s' % caminho_json, 'Resumo: %s' % caminho_md]
    return Resultado(comando='regressao', codigo=int(CODIGO_PIOROU) if piorou else int(Codigo.OK),
                     situacao='bloqueado' if piorou else 'ok', o_que_fazer=o_que_fazer, contagens=contagens,
                     numeros=numeros, linhas_humanas=linhas)
