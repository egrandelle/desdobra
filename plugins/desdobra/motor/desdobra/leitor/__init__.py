# -*- coding: utf-8 -*-
"""Leitor do PSD, lado do processo principal: chama o filho isolado e monta o laudo.

O processo principal nunca parseia o PSD. Ele so:
  - calcula o sha256 e le os 26 bytes do cabecalho (largura e altura, para o orcamento);
  - calcula o orcamento de memoria do filho a partir do registro de limites;
  - chama o filho pela interface de plataforma (plataforma.obter().executar_isolado), um por documento e um
    por smart object embutido PSD/PSB, ate a profundidade maxima;
  - le e valida o que o filho gravou (estrutura/1 ou recusa/1) e monta o laudo/1 pela funcao pura do laudo.

Comando (docs/m1-interfaces.md, 8.1):
    desdobra ler --job <pasta>              (fase do job: le entrada/kv.* e grava em laudo/; o envelope segue o
                                             modo de dados do job)
    desdobra ler <psd> --saida <pasta>      (avulso, para a regressao; o envelope sai sempre no modo c)
    opcoes dos dois: --teto-memoria-bytes N e --tempo-max-s N, o teto que o DA confirmou depois de uma leitura
    parada num limite a calibrar.

Limites que decidem o codigo de saida (LIMITES_QUE_DECIDEM_CODIGO): o orcamento de memoria e o tempo maximo do
filho. Enquanto algum deles esta a calibrar, a parada nao reprova o arquivo: a recusa sai com a decisao
"pede_confirmacao_do_da", a situacao "bloqueado" e o que fazer para o DA confirmar um teto maior (regra do
registro de limites: sem fonte, o efeito nunca e reprovar).
"""
import ctypes
import math
import os
import shutil
import time
from pathlib import Path

from desdobra import arquivos, contratos, limites, plataforma
from desdobra.leitor import cabecalho
from desdobra.resultado import Codigo, Resultado

MODULO_FILHO = 'desdobra.leitor.filho'
CODIGOS_FILHO_RECUSA = {3: Codigo.RECUSADO, 4: Codigo.ORCAMENTO, 5: Codigo.AUDITORIA}  # numero-neutro: protocolo filho/1

O_QUE_FAZER = {
    Codigo.OK: None,
    Codigo.RECUSADO: 'O arquivo foi recusado na leitura. Veja o motivo em laudo/laudo.json (recusas). Salve o PSD de '
                     'novo no Photoshop e troque a entrada com "desdobra job trocar-entrada".',
    Codigo.ORCAMENTO: 'A leitura passou do orçamento de memória ou de tempo. Feche outros programas e rode de novo; '
                      'se repetir, rode "desdobra doctor" e mande o código para o suporte.',
    Codigo.AUDITORIA: 'O processo de leitura tentou uma ação que o desdobra não permite e foi parado. Não abra este '
                      'arquivo de novo e mande o código para o suporte.',
    Codigo.ERRO_INTERNO: 'O leitor encontrou um erro interno. Rode "desdobra doctor" e mande o código para o suporte.',
    Codigo.NAO_DISPONIVEL: 'O isolamento do processo de leitura não está disponível neste sistema.',
}
O_QUE_FAZER_LIMITE = ('A leitura parou no teto de memória ou de tempo que o motor calcula, e esse teto ainda é um '
                      'valor a calibrar. Por isso a parada fica para o DA decidir. Para tentar de novo com um '
                      'teto maior, o DA confirma o valor e você roda "desdobra job proxima <pasta do job> '
                      '--teto-memoria-bytes N" (memória) ou "desdobra job proxima <pasta do job> --tempo-max-s N" '
                      '(tempo), que lê o arquivo de novo com esse teto. Fora do job, rode "desdobra ler" de novo com a '
                      'mesma opção. O teto calculado e o que parou estão em laudo/laudo.json, recusas.')
O_QUE_FAZER_RECUSAS = ('A leitura terminou, mas parte do arquivo foi recusada (smart object, passada de pixels ou '
                       'composição). Veja as recusas no laudo e decida com o DA antes de seguir para o render.')
O_QUE_FAZER_COMPOSICAO = ('A leitura terminou, mas a composição do documento passou do orçamento de memória ou de '
                          'tempo e a prova de pixel não foi feita. O laudo marca isso em recusas, etapa composicao. Decida com o DA '
                          'antes de seguir para o render.')


# ------------------------------------------------------------------ orcamento
# O composto gravado no PSD vem cru ou em PackBits, que guarda no maximo 128 bytes iguais em 2. Um arquivo de N
# bytes nao pode trazer mais que 64 x N pixels de composto por canal. O orcamento nunca acredita num canvas
# maior que isso: e o que faz o cabecalho forjado de 29999 x 29999 com poucos bytes ser recusado antes de alocar.
PIXELS_POR_BYTE_MAX = 64  # numero-neutro: razao maxima do PackBits (128 bytes em 2), fato do formato
LIMITES_DO_ORCAMENTO = ('isolador.base_python_bytes', 'isolador.fator_abertura_max', 'isolador.bytes_por_px_canvas',
                        'isolador.margem_orcamento')
LIMITES_DO_TEMPO = ('isolador.tempo_max_s',)
LIMITES_QUE_DECIDEM_CODIGO = LIMITES_DO_ORCAMENTO + LIMITES_DO_TEMPO
# tipo da recusa -> limites que a decidiram
LIMITES_POR_TIPO_DE_RECUSA = {'memoria': LIMITES_DO_ORCAMENTO, 'orcamento': LIMITES_DO_ORCAMENTO,
                              'tempo': LIMITES_DO_TEMPO}
# na composicao do documento, o filho aloca com o menor entre o orcamento e leitor.max_alloc_bytes
LIMITES_DA_COMPOSICAO_POR_MEMORIA = LIMITES_DO_ORCAMENTO + ('leitor.max_alloc_bytes',)


def pixels_plausiveis(bytes_arquivo, pixels_declarados):
    return min(int(pixels_declarados), int(bytes_arquivo) * PIXELS_POR_BYTE_MAX)


def orcamento_bytes(bytes_abertos, pixels_canvas):
    """(base do Python + fator de abertura x bytes + bytes por pixel do canvas x pixels plausiveis) x margem."""
    base = limites.valor('isolador.base_python_bytes')
    fator = limites.valor('isolador.fator_abertura_max')
    por_px = limites.valor('isolador.bytes_por_px_canvas')
    margem = limites.valor('isolador.margem_orcamento')
    px = pixels_plausiveis(bytes_abertos, pixels_canvas)
    return int((base + fator * bytes_abertos + por_px * px) * margem)


def anotar_limites(recusa, teto_memoria_confirmado=False, tempo_confirmado=False):
    """Acrescenta a recusa decidida por orcamento ou tempo os limites citados e a decisao:
      - teto_confirmado_pelo_da: o DA confirmou o teto usado nesta leitura;
      - pede_confirmacao_do_da: algum limite do calculo esta a calibrar, entao a parada nao reprova;
      - reprova: todos os limites tem fonte."""
    ids = LIMITES_POR_TIPO_DE_RECUSA.get(recusa.get('tipo'))
    if not ids:
        return recusa
    if recusa.get('etapa') == 'composicao' and ids == LIMITES_DO_ORCAMENTO:
        ids = LIMITES_DA_COMPOSICAO_POR_MEMORIA
    lims = [limites.obter(i) for i in ids]
    recusa['limites'] = [lim.citacao() for lim in lims]
    confirmado = tempo_confirmado if ids == LIMITES_DO_TEMPO else teto_memoria_confirmado
    if confirmado:
        recusa['decisao'] = 'teto_confirmado_pelo_da'
    elif any(lim.situacao == 'a_calibrar' for lim in lims):
        recusa['decisao'] = 'pede_confirmacao_do_da'
    else:
        recusa['decisao'] = 'reprova'
    return recusa


def _pixels_do_cabecalho(caminho, inicio=0):
    try:
        c = cabecalho.ler_de_arquivo(caminho, inicio)
        return c['largura'] * c['altura']
    except (cabecalho.CabecalhoInvalido, OSError):
        return 0


# ------------------------------------------------------------------ um filho
def _limpar(pasta):
    pasta = Path(pasta)
    if pasta.exists():
        shutil.rmtree(pasta)
    pasta.mkdir(parents=True)


def _rodar_filho(psd, pasta_saida, pasta_trabalho, orcamento, profundidade, prof_max, plat, recorte=None,
                 sem_composicao=False, tempo_max_s=None):
    _limpar(pasta_saida)
    _limpar(pasta_trabalho)
    cmd = [str(plat.interpretador()), '-I', '-B', '-m', MODULO_FILHO, str(psd), str(pasta_saida),
           '--orcamento-bytes', str(orcamento), '--profundidade', str(profundidade), '--profundidade-max', str(prof_max)]
    if recorte:
        cmd += ['--recorte', '%d:%d' % recorte]
    if sem_composicao:
        cmd.append('--sem-composicao')
    tempo = float(tempo_max_s) if tempo_max_s else float(limites.valor('isolador.tempo_max_s'))
    r = plat.executar_isolado(cmd, orcamento, tempo, pasta_trabalho)
    shutil.rmtree(pasta_trabalho, ignore_errors=True)
    return interpretar(r, Path(pasta_saida), orcamento)


def interpretar(r, pasta_saida, orcamento):
    """Le o disco do filho e decide. Devolve dict com codigo, estrutura, recusa, pico_bytes e tempo_s."""
    out = {'codigo': Codigo.OK, 'estrutura': None, 'recusa': None, 'pico_bytes': r.pico_bytes, 'tempo_s': r.tempo_s,
           'situacao_filho': r.situacao}
    arq_est, arq_rec = pasta_saida / 'estrutura.json', pasta_saida / 'recusa.json'
    if r.situacao == 'recusado':
        out['codigo'] = Codigo.NAO_DISPONIVEL
        out['recusa'] = {'tipo': 'plataforma', 'etapa': 'isolador', 'motivo': r.motivo or 'isolador indisponível'}
        return out
    if arq_rec.is_file() and (r.situacao != 'ok' or r.codigo != 0):
        rec = contratos.ler(arq_rec, 'recusa/1')
        out['recusa'] = {'tipo': rec['tipo'], 'etapa': rec['etapa'], 'motivo': rec['motivo'], 'medidas': rec.get('medidas', {})}
        out['codigo'] = CODIGOS_FILHO_RECUSA.get(rec['codigo'], Codigo.RECUSADO)
        return out
    if arq_est.is_file():
        est = contratos.ler(arq_est, 'estrutura/1')
        pp = est.get('prova_pixel') or {}
        if r.situacao == 'ok' and r.codigo == 0:
            out['estrutura'] = est
            return out
        if pp.get('motivo') == 'pendente':
            # a estrutura foi gravada e o filho caiu na composicao: a leitura vale, a prova nao foi feita
            est['prova_pixel'] = {'feita': False, 'motivo': {'memoria': 'orcamento', 'tempo': 'tempo'}.get(r.situacao, 'erro')}
            out['estrutura'] = est
            return out
    if r.situacao in ('memoria', 'tempo'):
        out['codigo'] = Codigo.ORCAMENTO
        out['recusa'] = {'tipo': 'memoria' if r.situacao == 'memoria' else 'tempo', 'etapa': 'leitura',
                         'motivo': r.motivo or 'orçamento estourado', 'medidas': {'orcamento_bytes': orcamento}}
        return out
    if r.situacao == 'queda':
        out['codigo'] = Codigo.RECUSADO
        out['recusa'] = {'tipo': 'queda', 'etapa': 'leitura', 'motivo': r.motivo or 'o processo de leitura caiu'}
        return out
    out['codigo'] = Codigo.ERRO_INTERNO
    out['recusa'] = {'tipo': 'bug', 'etapa': 'leitura', 'motivo': 'o processo de leitura terminou com erro interno',
                     'medidas': {'codigo_filho': r.codigo}}
    return out


def _rodar_em_paralelo(tarefas):
    """Roda [(peso_bytes, funcao)] e devolve os resultados na mesma ordem.

    No maximo leitor.filhos_paralelos ao mesmo tempo, e a soma dos pesos (memoria esperada) dos que rodam juntos
    nao passa de leitor.orcamento_paralelo_bytes. Um filho com peso acima desse total roda sozinho."""
    import threading
    from concurrent.futures import ThreadPoolExecutor
    if not tarefas:
        return []
    maximo = max(1, int(limites.valor('leitor.filhos_paralelos')))
    teto = int(limites.valor('leitor.orcamento_paralelo_bytes'))
    if maximo == 1 or len(tarefas) == 1:
        return [f() for _o, f in tarefas]
    cond = threading.Condition()
    em_uso = [0, 0]  # [orcamento somado, filhos rodando]

    def rodar(orc, f):
        with cond:
            cond.wait_for(lambda: em_uso[1] == 0 or em_uso[0] + orc <= teto)
            em_uso[0] += orc
            em_uso[1] += 1
        try:
            return f()
        finally:
            with cond:
                em_uso[0] -= orc
                em_uso[1] -= 1
                cond.notify_all()
    with ThreadPoolExecutor(max_workers=maximo) as ex:
        futuros = [ex.submit(rodar, o, f) for o, f in tarefas]
        return [fu.result() for fu in futuros]


# ------------------------------------------------------------------ casamento de linkado (so nomes e tamanhos)
def casamentos_de_linkados(estrutura, pasta_campanha):
    """Proposta de casamento de cada linkado com arquivos da pasta da campanha, por nome e tamanho.
    So lista nomes e tamanhos: nenhum arquivo e aberto, e nada e usado antes da confirmacao do DA."""
    if estrutura is None:
        return {}
    arquivos_campanha = []
    if pasta_campanha and Path(pasta_campanha).is_dir():
        base = Path(pasta_campanha)
        arquivos_campanha = [p for p in base.rglob('*') if p.is_file()]
    out = {}
    for item in estrutura.get('indice_smart') or []:
        reg = item.get('linkado')
        if item.get('embutido') or not reg:
            continue
        nome = (reg.get('nome') or '').casefold()
        cands = []
        for p in arquivos_campanha:
            if nome and p.name.casefold() == nome:
                tam = p.stat().st_size
                cands.append({'arquivo': 'campanha/' + p.relative_to(base).as_posix(), 'bytes': tam,
                              'mesmo_tamanho': reg.get('tamanho') == tam})
        out[item['unique_id']] = {'situacao': 'aguardando_confirmacao_do_da' if cands else 'sem_candidato',
                                  'candidatos': cands, 'usado': False}
    return out


# ------------------------------------------------------------------ leitura completa
def ler(psd, pasta_laudo, *, plat=None, pasta_campanha=None, nome_origem=None, teto_memoria_bytes=None,
        tempo_max_s=None):
    """Le o PSD no filho isolado, abre os embutidos PSD/PSB ate a profundidade maxima e grava laudo.json.

    psd: arquivo de entrada; pasta_laudo: pasta que recebe laudo.json, bruto/, miniaturas/, assets/;
    teto_memoria_bytes e tempo_max_s: teto confirmado pelo DA, no lugar do calculado, para cada filho.
    Devolve (codigo, laudo, extras)."""
    from desdobra import laudo as mod_laudo
    t0 = time.perf_counter()
    plat = plat or plataforma.obter()
    # caminhos absolutos: o filho roda com a pasta de trabalho como diretorio atual
    psd = Path(psd).resolve()
    pasta_laudo = Path(pasta_laudo).resolve()
    if pasta_campanha is not None:
        pasta_campanha = Path(pasta_campanha).resolve()
    pasta_laudo.mkdir(parents=True, exist_ok=True)
    for sub in ('bruto', 'miniaturas', 'assets', '.trabalho'):  # saidas do proprio leitor, refeitas a cada leitura
        shutil.rmtree(pasta_laudo / sub, ignore_errors=True)
    sha = arquivos.sha256_arquivo(psd)
    n_bytes = psd.stat().st_size
    prof_max = int(limites.valor('leitor.profundidade_max_smart'))
    orc = int(teto_memoria_bytes) if teto_memoria_bytes else orcamento_bytes(n_bytes, _pixels_do_cabecalho(psd))
    contador = [0]
    picos = []

    def trabalho():
        contador[0] += 1
        return pasta_laudo / '.trabalho' / str(contador[0])

    principal = _rodar_filho(psd, pasta_laudo / 'bruto' / sha, trabalho(), orc, 0, prof_max, plat,
                             tempo_max_s=tempo_max_s)
    picos.append(principal['pico_bytes'])
    # alarme do gancho de auditoria em qualquer filho (documento ou smart object) decide o codigo da leitura
    alarme = principal['codigo'] == Codigo.AUDITORIA
    estrutura = principal['estrutura']
    recusas = []
    if principal['recusa']:
        recusas.append(dict(principal['recusa'], layer_id=None))
    aninhadas = {}
    if estrutura is not None:
        nivel, prof = [estrutura], 1
        while nivel:
            # os embutidos PSD/PSB de um nivel, sem repetir, rodam em paralelo (cada um no proprio Job Object)
            pedidos = []
            for est in nivel:
                for item in est.get('indice_smart') or []:
                    if not item.get('embutido') or item.get('tipo_detectado') not in ('psd', 'psb') or not item.get('sha256'):
                        continue
                    if item['sha256'] in aninhadas or item['sha256'] == sha:
                        continue
                    if prof > prof_max:
                        aninhadas[item['sha256']] = {'estrutura': None, 'recusa': None, 'motivo': 'profundidade máxima'}
                        continue
                    cab = item.get('cabecalho_psd') or {}
                    px = (cab.get('largura') or 0) * (cab.get('altura') or 0)
                    aninhadas[item['sha256']] = None  # reservado: o mesmo embutido nao entra duas vezes no nivel
                    orc_item = int(teto_memoria_bytes) if teto_memoria_bytes else orcamento_bytes(
                        item['tamanho_dados'], px)
                    pedidos.append((item, orc_item, trabalho()))
            # o peso de cada filho na agenda paralela e o custo de abrir, sem o termo do canvas: o filho de smart
            # object nao compoe nem faz a passada de pixels, e so decodifica o composto quando ha texto visivel.
            # O teto de memoria de cada filho continua sendo o orcamento inteiro.
            resultados = _rodar_em_paralelo(
                [(orcamento_bytes(item['tamanho_dados'], 0), (lambda it=item, o=orc, pt=pt: _rodar_filho(
                    psd, pasta_laudo / 'bruto' / it['sha256'], pt, o, prof, prof_max, plat,
                    recorte=(it['deslocamento_dados'], it['tamanho_dados']), sem_composicao=True,
                    tempo_max_s=tempo_max_s)))
                 for item, orc, pt in pedidos])
            nivel = []
            for (item, _orc, _pt), res in zip(pedidos, resultados):
                picos.append(res['pico_bytes'])
                alarme = alarme or res['codigo'] == Codigo.AUDITORIA
                aninhadas[item['sha256']] = {'estrutura': res['estrutura'], 'recusa': res['recusa'],
                                             'pasta': 'bruto/%s' % item['sha256'], 'motivo': None}
                if res['recusa']:
                    for lid in item.get('layer_ids') or [None]:
                        recusas.append(dict(res['recusa'], layer_id=lid, etapa='smart_object_%s' % res['recusa']['etapa']))
                if res['estrutura'] is not None:
                    nivel.append(res['estrutura'])
            prof += 1
    # miniaturas do documento e assets de todos os filhos vao para a arvore do laudo
    _organizar_imagens(pasta_laudo, sha, aninhadas)
    shutil.rmtree(pasta_laudo / '.trabalho', ignore_errors=True)
    picos_validos = [p for p in picos if p is not None]
    recursos = {'tempo_s': round(time.perf_counter() - t0, 3), 'pico_bytes': max(picos_validos) if picos_validos else None,
                'orcamento_bytes': orc, 'filhos': contador[0]}
    origem = {'arquivo': nome_origem or psd.name, 'sha256': sha, 'bytes': n_bytes}
    laudo = mod_laudo.montar(estrutura, origem=origem, recursos=recursos, aninhadas=aninhadas, recusa=recusas,
                             casamentos=casamentos_de_linkados(estrutura, pasta_campanha))
    # depois de montar: a recusa da composicao nasce no laudo e recebe os limites e a decisao como as outras
    for rec in laudo['recusas']:
        anotar_limites(rec, bool(teto_memoria_bytes), bool(tempo_max_s))
    contratos.gravar(pasta_laudo / 'laudo.json', laudo, 'laudo/1')
    codigo = Codigo.AUDITORIA if alarme else principal['codigo']
    return codigo, laudo, {'recursos': recursos, 'aninhadas': len(aninhadas)}


def _organizar_imagens(pasta_laudo, sha, aninhadas):
    bruto = pasta_laudo / 'bruto'
    mini_origem = bruto / sha / 'miniaturas'
    if mini_origem.is_dir():
        destino = pasta_laudo / 'miniaturas'
        _limpar(destino)
        for p in mini_origem.iterdir():
            os.replace(p, destino / p.name)
    destino_assets = pasta_laudo / 'assets'
    destino_assets.mkdir(exist_ok=True)
    for s in [sha] + [k for k, v in aninhadas.items() if v.get('pasta')]:
        pa = bruto / s / 'assets'
        if pa.is_dir():
            for p in pa.iterdir():
                os.replace(p, destino_assets / p.name)


# ------------------------------------------------------------------ CLI
def registrar(subparsers):
    p = subparsers.add_parser('ler', help='Lê o PSD num processo isolado e grava o laudo')
    p.add_argument('psd', nargs='?', help='PSD ou PSB (uso avulso, com --saida)')
    p.add_argument('--job', default=None, help='Pasta do job (fase ler: lê entrada/kv.* e grava em laudo/)')
    p.add_argument('--saida', default=None, help='Pasta de saída no uso avulso')
    p.add_argument('--teto-memoria-bytes', type=int, default=None,
                   help='Teto de memória de cada processo de leitura, confirmado pelo DA (no lugar do calculado)')
    p.add_argument('--tempo-max-s', type=float, default=None,
                   help='Tempo máximo de cada processo de leitura, confirmado pelo DA (no lugar do padrão)')
    p.set_defaults(executar=_executar, nome_comando='ler')


def _uso(texto):
    return Resultado(comando='ler', codigo=int(Codigo.USO), situacao='erro', o_que_fazer=texto)


def erro_no_teto(teto_memoria_bytes=None, tempo_max_s=None):
    """Texto do erro de uso quando o teto confirmado pelo DA nao serve; None quando serve (ou nao foi dado)."""
    if teto_memoria_bytes is not None:
        if teto_memoria_bytes <= 0:
            return 'O teto de memória tem de ser um número inteiro de bytes maior que zero.'
        if teto_memoria_bytes > ctypes.c_size_t(-1).value:
            return ('O teto de memória passa do maior valor que o sistema aceita (%d bytes).'
                    % ctypes.c_size_t(-1).value)
    if tempo_max_s is not None and not (math.isfinite(tempo_max_s) and tempo_max_s > 0):
        return 'O tempo máximo tem de ser um número finito de segundos maior que zero.'
    return None


def _executar(args):
    pasta_job = None
    campanha = None
    erro = erro_no_teto(args.teto_memoria_bytes, args.tempo_max_s)
    if erro:
        return _uso(erro)
    if args.job:
        pasta_job = Path(args.job).resolve()
        candidatos = sorted((pasta_job / 'entrada').glob('kv.*'))
        if len(candidatos) != 1:
            return _uso('A pasta do job precisa ter um único entrada/kv.psd ou entrada/kv.psb.')
        psd = candidatos[0]
        pasta_laudo = pasta_job / 'laudo'
        campanha = pasta_job / 'entrada' / 'campanha'
    else:
        if not args.psd or not args.saida:
            return _uso('Use "desdobra ler --job <pasta>" ou "desdobra ler <psd> --saida <pasta>".')
        psd = Path(args.psd).resolve()
        pasta_laudo = Path(args.saida).resolve()
    if not psd.is_file():
        return _uso('O arquivo de entrada não existe.')
    if arquivos.eh_arquivo_de_fonte(psd):
        return Resultado(comando='ler', codigo=int(Codigo.RECUSADO), situacao='recusado',
                         o_que_fazer='O arquivo de entrada é uma fonte. O desdobra não lê arquivo de fonte.')
    if not arquivos.tem_assinatura_psd(psd):
        return Resultado(comando='ler', codigo=int(Codigo.RECUSADO), situacao='recusado',
                         o_que_fazer='O arquivo de entrada não é PSD nem PSB.')
    codigo, laudo, extras = ler(psd, pasta_laudo, pasta_campanha=campanha, teto_memoria_bytes=args.teto_memoria_bytes,
                                tempo_max_s=args.tempo_max_s)
    if pasta_job is not None:
        # rascunho do pacote para o modelo (sugestoes/pacote-modelo.json), filtrado pelo modo do job
        from desdobra.sugestao import pacote
        pacote.gravar_pacote(pasta_job)
    return resultado_de(codigo, laudo, extras, pasta_job)


def resultado_de(codigo, laudo, extras, pasta_job=None):
    cam = laudo['camadas']
    if any(r.get('tipo') == 'auditoria' for r in laudo['recusas']):
        # alarme de seguranca, mesmo vindo do filho de um smart object: nunca vira bloqueio comum
        codigo = Codigo.AUDITORIA
    res = laudo['resumo']
    pp = laudo['prova_pixel']
    situacao = {Codigo.OK: 'ok', Codigo.NAO_DISPONIVEL: 'nao_disponivel', Codigo.ERRO_INTERNO: 'erro'}.get(codigo, 'recusado')
    pede_confirmacao = any(r.get('decisao') == 'pede_confirmacao_do_da' for r in laudo['recusas'])
    from desdobra.sugestao import pacote
    conteudo = pacote.conteudo_para_resultado(laudo)
    linhas = ['Laudo gravado: %d camadas (%d lidas, %d degradadas, %d bloqueantes).' % (
        res['n_camadas'], res['por_situacao']['lida'], res['por_situacao']['degradada'], res['por_situacao']['bloqueante'])]
    if pp.get('feita'):
        linhas.append('Prova de pixel: %.4f%% dos pixels acima do limiar.' % pp['pct_px_acima_qualquer_canal'])
    else:
        linhas.append('Prova de pixel não feita (%s).' % (pp.get('motivo') or 'sem motivo'))
    for r in laudo['recusas']:
        linhas.append('Recusa: %s (%s).' % (r['motivo'], r['tipo']))
    o_que_fazer = O_QUE_FAZER.get(codigo)
    if codigo not in (Codigo.OK, Codigo.AUDITORIA) and pede_confirmacao:
        # parada num limite a calibrar: nao reprova, fica com o DA (o alarme de auditoria nunca vira bloqueio)
        situacao, o_que_fazer = 'bloqueado', O_QUE_FAZER_LIMITE
    elif codigo == Codigo.OK and laudo['recusas']:
        # a leitura vale, mas ha bloqueio do documento ou recusa de parte dele: o envelope nao pode dizer so "ok"
        situacao = 'ok_com_bloqueio'
        if any(r.get('etapa') == 'composicao' for r in laudo['recusas']):
            o_que_fazer = O_QUE_FAZER_COMPOSICAO
        else:
            o_que_fazer = O_QUE_FAZER_RECUSAS
        if pede_confirmacao:
            o_que_fazer += ' ' + O_QUE_FAZER_LIMITE
    return Resultado(
        comando='ler', codigo=int(codigo), situacao=situacao, fase='ler' if pasta_job else None,
        o_que_fazer=o_que_fazer,
        contagens={'camadas': res['n_camadas'], 'lidas': res['por_situacao']['lida'],
                   'degradadas': res['por_situacao']['degradada'], 'bloqueantes': res['por_situacao']['bloqueante'],
                   'quadros': res['n_quadros'], 'cobertas_no_kv': res.get('n_cobertas_no_kv', 0),
                   'smart_objects': sum(1 for c in cam if c['tipo'] in ('smart_embutido', 'smart_linkado')),
                   'recusas': len(laudo['recusas']), 'filhos': extras['recursos']['filhos'],
                   'bloqueios_composicao': sum(1 for r in laudo['recusas'] if r.get('etapa') == 'composicao'),
                   'bloqueios_documento': res.get('bloqueios_documento', 0),
                   'recusas_pedem_confirmacao': sum(1 for r in laudo['recusas']
                                                    if r.get('decisao') == 'pede_confirmacao_do_da'),
                   'fontes_nao_conferidas': sum(1 for f in laudo['fontes_usadas'] if f['situacao'] == 'nao_conferida'),
                   'camadas_com_fonte_nao_conferida': res.get('n_fonte_nao_conferida', 0)},
        ids={'arquivo_sha256': laudo['origem']['sha256']},
        numeros={'tempo_s': extras['recursos']['tempo_s'],
                 'pico_bytes': float(extras['recursos']['pico_bytes']) if extras['recursos']['pico_bytes'] is not None else None,
                 'pct_px_acima_qualquer_canal': pp.get('pct_px_acima_qualquer_canal')},
        conteudo=conteudo, pasta_job=pasta_job, linhas_humanas=linhas)
