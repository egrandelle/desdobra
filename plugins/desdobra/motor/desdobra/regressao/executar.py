# -*- coding: utf-8 -*-
"""Executor da regressao: lista o corpus, roda a leitura de cada arquivo e le o laudo que ela deixou.

A leitura e o proprio comando do motor, avulso, num subprocesso:
    python -I -B -m desdobra --envelope ler <arquivo> --saida <saida>/<slug>
(o ler avulso imprime sempre o envelope do modo c). Esse comando usa o isolador da plataforma para cada processo
filho (docs/m1-interfaces.md, 8.1). O processo da regressao nunca abre PSD: ele so confere os 4 primeiros bytes
(8BPS) ao listar o corpus.

Verificacoes de seguranca por arquivo: a saida padrao do ler no modo c nao pode trazer nome de camada, texto de
peca nem caminho (varrer_saida), e o gancho de auditoria nao pode ter barrado nada. Num arquivo pequeno, a
regressao tambem roda o caminho do job (job criar e job proxima no modo c) e varre a saida padrao, a saida de
erro e o que o job grava para o Claude (verificar_job_modo_c).

Agenda: os arquivos ate regressao.arquivo_grande_bytes rodam primeiro, ate --paralelo por vez; os maiores
rodam depois, um de cada vez, do menor para o maior.

O slug de cada arquivo e o mesmo que o agendador da sonda da pesquisa gerava, para casar com a linha de base.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from desdobra import contratos, limites
from desdobra.arquivos import EXTENSOES_PSD, tem_assinatura_psd
from desdobra.resultado import Codigo

TAMANHO_MARCA = 24       # numero-neutro: formato do slug do agendador da sonda, para casar com a linha de base
TAMANHO_NOME = 48        # numero-neutro: idem
TAMANHO_SUFIXO = 6       # numero-neutro: idem (sufixo sha1 quando dois arquivos dao o mesmo slug)

SITUACAO_POR_CODIGO = {
    int(Codigo.RECUSADO): 'recusado',
    int(Codigo.ORCAMENTO): 'orcamento',
    int(Codigo.AUDITORIA): 'auditoria',
}


@dataclass(frozen=True)
class Item:
    caminho: Path
    relativo: str
    bytes: int
    slug: str


def slugificar(texto, tamanho):
    texto = unicodedata.normalize('NFKD', texto)
    texto = ''.join(ch for ch in texto if not unicodedata.combining(ch)).encode('ascii', 'ignore').decode('ascii').lower()
    texto = re.sub(r'[^a-z0-9]+', '-', texto).strip('-')
    return texto[:tamanho].strip('-')


def listar_corpus(raiz):
    """Lista os PSD e PSB da pasta (recursivo, em ordem), com o slug do agendador da sonda."""
    raiz = Path(raiz)
    itens = []
    for pasta, subpastas, arquivos in os.walk(raiz):
        subpastas.sort()
        for nome in sorted(arquivos):
            if not nome.lower().endswith(EXTENSOES_PSD) or nome.startswith('._'):
                continue
            caminho = Path(pasta) / nome
            try:
                if not tem_assinatura_psd(caminho):
                    continue
            except OSError:
                continue
            itens.append((caminho, os.path.relpath(caminho, raiz), caminho.stat().st_size))
    usados = set()
    saida = []
    for caminho, relativo, tamanho in itens:
        partes = relativo.split(os.sep)
        marca = slugificar(partes[0], TAMANHO_MARCA) if len(partes) > 1 else 'raiz'
        base = '%s--%s' % (marca, slugificar(os.path.splitext(partes[-1])[0], TAMANHO_NOME))
        slug = base
        if slug in usados:
            slug = '%s-%s' % (base, hashlib.sha1(relativo.encode('utf-8')).hexdigest()[:TAMANHO_SUFIXO])
        usados.add(slug)
        saida.append(Item(caminho=caminho, relativo=relativo, bytes=tamanho, slug=slug))
    return saida


def achar_laudo(pasta):
    """O laudo que `ler --saida <pasta>` grava: <pasta>/laudo.json (ou <pasta>/laudo/laudo.json)."""
    for caminho in (Path(pasta) / 'laudo.json', Path(pasta) / 'laudo' / 'laudo.json'):
        if caminho.is_file():
            return caminho
    return None


def _marca(caminho):
    if caminho is None:
        return None
    st = caminho.stat()
    return caminho, st.st_mtime_ns, st.st_size


def ler_laudo(caminho):
    """(laudo, situacao, motivo): situacao ok, sem_laudo ou laudo_invalido."""
    if caminho is None:
        return None, 'sem_laudo', 'a leitura não deixou laudo.json'
    try:
        laudo = contratos.ler(caminho, 'laudo/1')
    except contratos.ErroContrato as e:
        return None, 'laudo_invalido', 'laudo.json não vale contra laudo/1 (campo %s)' % (e.onde or '?')
    return laudo, 'ok', None


def situacao_do_codigo(codigo):
    if codigo == Codigo.OK:
        return 'ok', None
    if codigo in SITUACAO_POR_CODIGO:
        return SITUACAO_POR_CODIGO[codigo], 'a leitura terminou com o código %d' % codigo
    if codigo == Codigo.NAO_DISPONIVEL:
        return 'erro', 'o comando ler não está disponível neste build'
    return 'erro', 'a leitura terminou com o código %s' % codigo


def _envelope_da_saida(stdout):
    for linha in reversed((stdout or b'').decode('utf-8', 'replace').splitlines()):
        linha = linha.strip()
        if linha.startswith('{'):
            try:
                return json.loads(linha)
            except ValueError:
                return None
    return None


def rodar_ler(item, pasta, python=None):
    """Roda a leitura avulsa de um arquivo em `pasta`. Devolve {'execucao', 'laudo'}.

    execucao = {'situacao', 'motivo', 'tempo_s', 'codigo'}. A saida do comando fica so na memoria: nada do
    que ele imprime vai para o relatorio.
    """
    # caminhos absolutos: o subprocesso roda com cwd na propria pasta, e um caminho relativo nao acharia o arquivo
    pasta = Path(pasta).resolve()
    pasta.mkdir(parents=True, exist_ok=True)
    antes = _marca(achar_laudo(pasta))
    comando = [python or sys.executable, '-I', '-B', '-m', 'desdobra', '--envelope', 'ler',
               str(Path(item.caminho).resolve()), '--saida', str(pasta)]
    ambiente = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
    inicio = time.monotonic()
    try:
        proc = subprocess.run(comando, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              cwd=pasta, env=ambiente)
        codigo, stdout = proc.returncode, proc.stdout
    except OSError as e:
        return {'execucao': {'situacao': 'erro', 'motivo': 'não foi possível iniciar a leitura (%s)' % type(e).__name__,
                             'tempo_s': None, 'codigo': None}, 'laudo': None}
    tempo = time.monotonic() - inicio
    envelope = _envelope_da_saida(stdout)
    if isinstance(envelope, dict) and isinstance(envelope.get('codigo'), int):
        codigo = envelope['codigo']
    situacao, motivo = situacao_do_codigo(codigo)

    caminho = achar_laudo(pasta)
    depois = _marca(caminho)
    laudo = None
    if caminho is not None and depois != antes:
        laudo, situacao_laudo, motivo_laudo = ler_laudo(caminho)
        if situacao_laudo != 'ok':
            situacao, motivo = situacao_laudo, motivo_laudo
    elif situacao == 'ok':
        situacao, motivo = 'sem_laudo', 'a leitura terminou sem gravar um laudo.json novo'
    texto_saida = (stdout or b'').decode('utf-8', 'replace')
    (pasta / ARQUIVO_SAIDA_PADRAO).write_text(texto_saida, encoding='utf-8')
    return {'execucao': {'situacao': situacao, 'motivo': motivo, 'tempo_s': round(tempo, 2),  # numero-neutro: exibicao
                         'codigo': codigo}, 'laudo': laudo,
            'verificacoes': verificacoes(item, pasta, laudo, texto_saida)}


# ------------------------------------------------------------------ verificacoes de seguranca por arquivo
ARQUIVO_SAIDA_PADRAO = 'saida-padrao.txt'


def termos_do_laudo(laudo, item):
    """O que nao pode aparecer na saida padrao do modo c: nomes de camada, textos e trechos do proprio laudo,
    o caminho do arquivo, o nome do arquivo e os nomes das pastas dele dentro do corpus."""
    termos = set()
    for c in (laudo or {}).get('camadas') or []:
        termos.add(c.get('nome') or '')
        tx = c.get('texto') or {}
        for t in [tx.get('conteudo')] + [r.get('texto') for r in tx.get('runs') or [] if isinstance(r, dict)]:
            if isinstance(t, str):
                termos.add(t)
                termos.update(t.splitlines())
    caminho = Path(item.caminho)
    termos.update({str(caminho), caminho.as_posix(), caminho.name, caminho.stem, str(item.relativo)})
    termos.update(Path(item.relativo).parts)
    return {t.strip() for t in termos if isinstance(t, str) and t.strip()}


def _valores_de_texto(dados):
    if isinstance(dados, str):
        yield dados
    elif isinstance(dados, dict):
        for v in dados.values():
            yield from _valores_de_texto(v)
    elif isinstance(dados, list):
        for v in dados:
            yield from _valores_de_texto(v)


def _texto_livre(dados):
    """Valores de texto livre do envelope (o_que_fazer e tudo dentro de conteudo), onde um nome curto vazaria."""
    if not isinstance(dados, dict):
        return []
    livre = [dados['o_que_fazer']] if isinstance(dados.get('o_que_fazer'), str) else []
    livre += list(_valores_de_texto(dados.get('conteudo')))
    return livre


def vocabulario_do_motor():
    """Palavras dos textos fixos do motor (as constantes de texto do pacote desdobra). Um termo curto que e
    palavra do proprio motor (por exemplo "de" ou "PSD") nao conta como vazamento quando aparece no o que fazer."""
    import ast
    from desdobra import PASTA_MOTOR
    palavras = set()
    for arq in sorted((PASTA_MOTOR / 'desdobra').rglob('*.py')):
        try:
            arvore = ast.parse(arq.read_text(encoding='utf-8'))
        except (OSError, SyntaxError, ValueError):
            continue
        for no in ast.walk(arvore):
            if isinstance(no, ast.Constant) and isinstance(no.value, str):
                palavras.update(re.findall(r'\w+', no.value.casefold()))
    return frozenset(palavras)


_VOCABULARIO = []


def _vocabulario():
    if not _VOCABULARIO:
        _VOCABULARIO.append(vocabulario_do_motor())
    return _VOCABULARIO[0]


def _palavra_inteira(termo, texto):
    return re.search(r'(?<!\w)' + re.escape(termo) + r'(?!\w)', texto, re.IGNORECASE) is not None


def texto_varrido(texto_saida):
    """O que a varredura olha: os valores de texto de cada linha JSON (as chaves do envelope sao vocabulario fixo do
    motor, como "codigo" e "camadas", e coincidem com nomes de camada comuns) e as linhas que nao sao JSON inteiras.
    Devolve (texto, tem_conteudo)."""
    partes, tem_conteudo = [], False
    for linha in texto_saida.splitlines():
        try:
            dados = json.loads(linha)
        except ValueError:
            partes.append(linha)
            continue
        if isinstance(dados, dict) and 'conteudo' in dados:
            tem_conteudo = True
        partes.extend(_valores_de_texto(dados))
    return '\n'.join(partes), tem_conteudo


def varrer_saida(texto_saida, termos, vocabulario=None):
    """Procura cada termo na saida. Nunca devolve o termo achado.

    Termo longo (de regressao.varredura_min_caracteres para cima): achado se aparece em qualquer valor de texto.
    Termo curto: procurado como palavra inteira, so no texto livre (o_que_fazer, conteudo e linhas que nao sao
    JSON), e nunca dentro de hash hexadecimal nem de chave do envelope. Achado se aparece e nao e palavra dos
    textos fixos do motor; se e, entra so na contagem termos_curtos_vocabulario."""
    minimo = limites.valor('regressao.varredura_min_caracteres')
    vocabulario = _vocabulario() if vocabulario is None else vocabulario
    texto, tem_conteudo = texto_varrido(texto_saida)
    livre = []
    for linha in texto_saida.splitlines():
        try:
            livre.extend(_texto_livre(json.loads(linha)))
        except ValueError:
            livre.append(linha)
    texto_livre = '\n'.join(livre)
    longos = [t for t in termos if len(t) >= minimo]
    achados = sum(1 for t in longos if t in texto)
    curtos = [t for t in termos if len(t) < minimo]
    curtos_presentes = [t for t in curtos if _palavra_inteira(t, texto_livre)]
    do_vocabulario = [t for t in curtos_presentes if t.casefold() in vocabulario]
    achados += len(curtos_presentes) - len(do_vocabulario)
    return {'termos': len(longos), 'achados': achados, 'termos_curtos': len(curtos),
            'termos_curtos_presentes': len(curtos_presentes), 'termos_curtos_vocabulario': len(do_vocabulario),
            'bytes': len(texto_saida.encode('utf-8')), 'linhas': len(texto_saida.splitlines()),
            'tem_conteudo': tem_conteudo}


def _rodar_motor(argumentos, cwd, python=None):
    comando = [python or sys.executable, '-I', '-B', '-m', 'desdobra', '--envelope'] + list(argumentos)
    ambiente = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
    proc = subprocess.run(comando, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd,
                          env=ambiente)
    return proc.returncode, proc.stdout.decode('utf-8', 'replace'), proc.stderr.decode('utf-8', 'replace')


def verificar_job_modo_c(item, pasta, python=None):
    """Roda job criar e job proxima no modo c numa pasta nova dentro de `pasta` e varre a saida padrao, a saida
    de erro, o estado, o log e o pacote do modelo contra os nomes e textos do laudo do proprio job."""
    import shutil
    pasta = Path(pasta).resolve()
    job = pasta / 'job-modo-c'
    if job.exists():
        for p in job.rglob('*'):
            if p.is_file():
                os.chmod(p, 0o666)  # numero-neutro: permissao de gravacao, para apagar as entradas congeladas
        shutil.rmtree(job)
    saidas = []
    cod_criar, out, err = _rodar_motor(['job', 'criar', str(job), '--kv', str(Path(item.caminho).resolve()),
                                        '--modo-dados', 'c'],
                                       pasta, python)
    saidas += [out, err]
    cod_prox = None
    if cod_criar == 0:
        cod_prox, out, err = _rodar_motor(['job', 'proxima', str(job)], pasta, python)
        saidas += [out, err]
    laudo = None
    try:
        laudo = json.loads((job / 'laudo' / 'laudo.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        pass
    termos = termos_do_laudo(laudo, item)
    gravados = []
    for rel in ('estado.json', 'log/eventos.jsonl', 'sugestoes/pacote-modelo.json'):
        try:
            gravados.append((job / rel).read_text(encoding='utf-8'))
        except OSError:
            pass
    # o stderr e os arquivos gravados entram inteiros (texto cru): ali nao ha vocabulario de envelope a separar
    cru = '\n'.join(saidas[1::2] + gravados)
    achados_cru = sum(1 for t in termos if len(t) >= limites.valor('regressao.varredura_min_caracteres') and t in cru)
    v = varrer_saida('\n'.join(saidas[0::2]), termos)
    return {'achados': v['achados'] + achados_cru, 'tem_conteudo': v['tem_conteudo'], 'termos': v['termos'],
            'arquivos_varridos': len(gravados), 'codigo_criar': cod_criar, 'codigo_proxima': cod_prox,
            'stderr_bytes': sum(len(s.encode('utf-8')) for s in saidas[1::2]),
            'falhou': cod_criar != 0 or cod_prox != 0 or laudo is None}


def auditoria_dos_filhos(pasta, laudo):
    """Alarmes do gancho de auditoria em todos os filhos da leitura (bruto/*/estrutura.json e recusas)."""
    filhos, instalados, bloqueios = 0, 0, 0
    for est in sorted((Path(pasta) / 'bruto').glob('*/estrutura.json')):
        try:
            dados = json.loads(est.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        filhos += 1
        aud = dados.get('auditoria') or {}
        instalados += bool(aud.get('instalado'))
        bloqueios += len(aud.get('bloqueios') or [])
    recusas_auditoria = sum(1 for r in (laudo or {}).get('recusas') or [] if r.get('tipo') == 'auditoria')
    linkados = sum(1 for c in (laudo or {}).get('camadas') or [] if c.get('tipo') == 'smart_linkado')
    usados = sum(1 for c in (laudo or {}).get('camadas') or [] if c.get('tipo') == 'smart_linkado'
                 and ((c.get('smart_object') or {}).get('casamento') or {}).get('usado'))
    return {'filhos_com_estrutura': filhos, 'gancho_instalado': instalados, 'bloqueios': bloqueios,
            'recusas_auditoria': recusas_auditoria, 'linkados': linkados, 'linkados_usados': usados}


def verificacoes(item, pasta, laudo, texto_saida):
    return {'saida_padrao': varrer_saida(texto_saida, termos_do_laudo(laudo, item)),
            'auditoria': auditoria_dos_filhos(pasta, laudo)}


def ler_existente(item, pasta):
    """Sem rodar: le o laudo que ja esta em `pasta` (opcao --sem-rodar)."""
    laudo, situacao, motivo = ler_laudo(achar_laudo(pasta))
    if laudo is not None and laudo.get('recusas') and not laudo.get('camadas'):
        situacao, motivo = 'recusado', 'o laudo registra a recusa do arquivo'
    saida = Path(pasta) / ARQUIVO_SAIDA_PADRAO
    texto_saida = saida.read_text(encoding='utf-8') if saida.is_file() else ''
    return {'execucao': {'situacao': situacao, 'motivo': motivo, 'tempo_s': None, 'codigo': None}, 'laudo': laudo,
            'verificacoes': verificacoes(item, pasta, laudo, texto_saida)}


def rodar_todos(itens, saida, *, paralelo=1, rodar=None):
    """Roda `rodar(item, pasta)` para cada item, com a agenda por tamanho. Devolve {slug: retorno}."""
    rodar = rodar or rodar_ler
    grande = limites.valor('regressao.arquivo_grande_bytes')
    pequenos = [i for i in itens if i.bytes <= grande]
    grandes = sorted((i for i in itens if i.bytes > grande), key=lambda i: i.bytes)
    resultados = {}
    with ThreadPoolExecutor(max_workers=max(1, int(paralelo))) as executor:
        futuros = {i.slug: executor.submit(rodar, i, Path(saida) / i.slug) for i in pequenos}
        for slug, futuro in futuros.items():
            resultados[slug] = futuro.result()
    for item in grandes:
        resultados[item.slug] = rodar(item, Path(saida) / item.slug)
    return resultados
