# -*- coding: utf-8 -*-
"""Conferencia das fontes do job (fase "fontes", comando "desdobra fontes conferir").

Quatro partes (arquitetura-v1.md, 4.5 e 9.3):
  1. casa cada nome PostScript usado no laudo com o nome PostScript de um arquivo de entrada/fontes/;
  2. confere a cobertura de glifos do texto de cada trecho;
  3. carrega cada face no Chromium pelo @font-face, servida pela rota propria no loopback, com familia propria do
     job e peso declarado, e confere por CDP que a face usada e a do arquivo;
  4. mede a largura de cada linha contra a caixa TySh do PSD.
Mais a licenca de cada face (desdobra.fontes.licenca), o teste de cache do perfil do Chromium e a varredura da
pasta do job atras de arquivo de fonte fora de entrada/fontes/.

Saidas: fontes/conferencia.json (conferencia-fontes/1) e manifesto-licenca.json (manifesto-licenca/1, rascunho).
Os dois levam ids, hashes, nomes de fonte e numeros; nunca texto de peca, caminho de arquivo ou byte de fonte.
"""
import hashlib
import shutil
from datetime import datetime
from pathlib import Path

from desdobra import arquivos, contratos, limites, plataforma
from desdobra.chromium import navegador, servidor
from desdobra.fontes import casamento, leitura, licenca, medicao

ESQUEMA = 'conferencia-fontes/1'
ESQUEMA_MANIFESTO = 'manifesto-licenca/1'
ESQUEMA_LICENCAS = 'licencas-fontes/1'
ARQUIVO = Path('fontes') / 'conferencia.json'
ARQUIVO_MANIFESTO = Path('manifesto-licenca.json')
ARQUIVO_LICENCAS = Path('entrada') / 'licencas.json'
PASTA_ENTRADA = 'entrada/fontes/'
# o perfil do Chromium fica numa pasta temporaria curta da maquina, criada e apagada pelo motor (navegador.perfil_curto)
PERFIL_TEMPORARIO = 'pasta temporaria curta do motor, apagada no fim'
LINK_CONTROLE = '<link rel="stylesheet" href="%s">' % servidor.ROTA_CONTROLE
SITUACOES = ('ok', 'aviso', 'bloqueante')
# motivos tecnicos da camada: sao os que a segunda passada do laudo leva para a regra B3
TECNICOS = ('arquivo_faltando', 'nome_ps_sem_par', 'face_divergente', 'glifo_faltando', 'fallback',
            'face_cdp_divergente', 'face_nao_carregou', 'largura_divergente', 'chromium_nao_conferiu',
            'colecao_nao_servivel', 'mais_de_um_arquivo', 'cdp_sem_resposta')
DESCRICOES = {
    'arquivo_faltando': 'Nenhum arquivo de entrada/fontes/ tem este nome PostScript nem a mesma família.',
    'nome_ps_sem_par': 'Há arquivo da mesma família em entrada/fontes/, mas nenhum com este nome PostScript.',
    'face_divergente': 'O arquivo da mesma família tem outro peso ou estilo: a face não entra no lugar da pedida.',
    'glifo_faltando': 'O arquivo não cobre todos os caracteres com tinta do texto.',
    'fallback': 'O Chromium desenhou parte do texto com outra face (fallback), fora do arquivo do job.',
    'face_cdp_divergente': 'O Chromium usou uma face do job com outro nome PostScript.',
    'face_nao_carregou': 'O Chromium não carregou a face pelo @font-face.',
    'colecao_nao_servivel': 'A face da coleção não pode ser servida sozinha ao Chromium.',
    'chromium_nao_conferiu': 'A conferência no Chromium não rodou: sem ela, a face usada e a largura ficam sem prova.',
    'largura_divergente': 'A largura da linha no Chromium difere da caixa gravada pelo Photoshop acima do limiar a '
                          'calibrar. Pode ser outra versão da fonte ou do mapeamento do texto. Decisão do DA.',
    'casada_por_id_unico': 'Par achado pelo id único (name ID 3), não pelo name ID 6.',
    'casada_por_familia_estilo': 'Par achado pela família e estilo, não pelo name ID 6.',
    'mais_de_um_arquivo': 'Mais de um arquivo de entrada/fontes/ casa com este nome PostScript, e o motor não escolhe '
                          'qual vale. Decisão do DA: tirar o arquivo que não vale com "desdobra job remover-entrada".',
    'cdp_sem_resposta': 'O Chromium não disse por CDP qual face desenhou o trecho: sem essa resposta, a face usada fica '
                        'sem prova.',
    'face_com_bloqueio': 'A face do arquivo está bloqueante ou com aviso (licença ou carregamento).',
    'so_em_espaco': 'Fonte usada só em caracteres sem tinta: não deixa marca.',
    'peso_os2_diverge_do_estilo': 'O usWeightClass do arquivo não bate com o peso do nome do estilo; o @font-face '
                                  'declara o peso do estilo.',
    'face_nao_usada': 'Face enviada que nenhuma camada usa.',
    'instalada_mesmo_nome': 'Há face instalada no sistema com o mesmo nome (só diagnóstico; nunca entra no lugar).',
    'largura_nao_medida_caixa_paragrafo': 'Caixa de parágrafo: a caixa gravada é a da caixa, não a da linha.',
    'largura_nao_medida_sem_caixa': 'A camada não tem a caixa TySh gravada.',
    'largura_nao_medida_face_ausente': 'Um trecho da camada não tem arquivo de fonte: a largura não dá para medir.',
    'largura_nao_medida_faux_bold': 'Faux bold sem emulação no Chromium: a largura não é comparada.',
    'largura_nao_medida_escala': 'Escala horizontal ou vertical do trecho diferente de 100%: a largura não é comparada.',
    'largura_nao_medida_warp': 'Texto com warp: a largura não é comparada.',
}
O_QUE_FAZER_OK = 'As fontes do job conferem com os arquivos de entrada/fontes/. Rode "desdobra job proxima" para seguir.'
O_QUE_FAZER_BLOQUEIO = ('A conferência de fontes achou bloqueios: veja fontes/conferencia.json e o rascunho de '
                        'manifesto-licenca.json. Para fonte faltando ou sem par, traga o arquivo (OTF, TTF, TTC, WOFF '
                        'ou WOFF2) e acrescente com "desdobra job trocar-entrada <pasta> entrada/fontes/<arquivo> '
                        '<arquivo>". Quando dois arquivos têm o mesmo nome PostScript, tire o que não vale com '
                        '"desdobra job remover-entrada <pasta> entrada/fontes/<arquivo>". Divergência de largura e '
                        'bloqueio de licença ficam para o DA decidir; a liberação de licença entra em '
                        'entrada/licencas.json, com justificativa. O bloqueio fica no estado do job até a conferência '
                        'rodar de novo sem ele.')


def agora():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def _motivo(codigo, situacao, medida=None, limite_id=None, descricao=None):
    return {'codigo': codigo, 'situacao': situacao, 'descricao': descricao or DESCRICOES.get(codigo, codigo),
            'medida': medida, 'limite': limites.obter(limite_id).citacao() if limite_id else None}


def pior(motivos):
    sits = {m['situacao'] for m in motivos}
    return 'bloqueante' if 'bloqueante' in sits else ('aviso' if 'aviso' in sits else 'ok')


def varrer_fontes_fora_da_entrada(pasta_job):
    """Quantos arquivos de fonte (extensao, assinatura, ou dentro de zip e tar) ha na pasta do job fora de
    entrada/fontes/ (arquitetura-v1.md, 5.1). Devolve (n, arquivos varridos)."""
    pasta_job = Path(pasta_job)
    n, varridos = 0, 0
    for p in pasta_job.rglob('*'):
        if not p.is_file():
            continue
        rel = p.relative_to(pasta_job).as_posix()
        if rel.startswith(PASTA_ENTRADA):
            continue
        varridos += 1
        if arquivos.eh_arquivo_de_fonte(p):
            n += 1
    return n, varridos


def perfil_do_chromium():
    """Pasta do perfil do Chromium da conferencia (os testes trocam para simular um caminho longo)."""
    return navegador.perfil_curto()


def _com_controle(pagina):
    """A pagina de medicao com a folha de estilo do controle positivo do teste de cache."""
    return pagina.replace('</head>', LINK_CONTROLE + '</head>', 1)


# ------------------------------------------------------------------ bytes servidos ao Chromium
def bytes_para_servir(dados, face):
    """Os bytes da face como o Chromium recebe. Fora de colecao, o arquivo como esta. Na colecao, o diretorio da
    face e copiado para o inicio do arquivo (os deslocamentos das tabelas contam do inicio), com os numeros que o
    filho mediu; o processo principal so copia bytes."""
    col = face.get('colecao')
    if face['formato'] != 'ttc':
        return dados
    if not col or not col['emendavel']:
        return None
    buf = bytearray(dados)
    o, t = col['deslocamento_diretorio'], col['tamanho_diretorio']
    buf[0:t] = dados[o:o + t]
    return bytes(buf)


# ------------------------------------------------------------------ conferencia
def _ler_arquivos(pasta_job, estado, plat):
    """Le cada arquivo de entrada/fontes/ no filho. Devolve (leituras [(sha, leitura)], arquivos, caminhos)."""
    bruto = pasta_job / 'fontes' / 'bruto'
    trabalho = pasta_job / 'fontes' / '.trabalho'
    shutil.rmtree(bruto, ignore_errors=True)
    shutil.rmtree(trabalho, ignore_errors=True)
    leituras, saida, caminhos = [], [], {}
    rels = sorted(r for r in estado['entradas'] if r.startswith(PASTA_ENTRADA))
    for n, rel in enumerate(rels, 1):
        sha = estado['entradas'][rel]['sha256']
        caminho = pasta_job / rel
        formato, recusa = arquivos.classificar_fonte(caminho)
        if recusa:
            saida.append({'sha256': sha, 'formato': None, 'situacao': 'recusado', 'motivo': recusa})
            continue
        r = leitura.ler(caminho, bruto / sha, trabalho / str(n), plat=plat)
        if r['situacao'] == 'lida':
            leituras.append((sha, r['leitura']))
            caminhos[sha] = caminho
            saida.append({'sha256': sha, 'formato': formato, 'situacao': 'aceito', 'motivo': None,
                          'faces': len(r['leitura']['faces'])})
        else:
            saida.append({'sha256': sha, 'formato': formato, 'situacao': 'recusado', 'motivo': r['recusa']['tipo']})
    shutil.rmtree(trabalho, ignore_errors=True)
    return leituras, saida, caminhos


def _camadas_de_texto(laudo):
    return [c for c in laudo.get('camadas') or [] if c.get('tipo') == 'texto' and (c.get('texto') or {}).get('runs')]


def _fontes_ps_da_camada(c):
    vistos = []
    for r in c['texto']['runs']:
        ps = r.get('fonte_ps')
        if ps and ps not in vistos:
            vistos.append(ps)
    return vistos


def conferir(pasta_job, *, plat=None, usar_chromium=True, cache_control='no-store'):
    """Roda a conferencia e grava fontes/conferencia.json e manifesto-licenca.json. Devolve a conferencia."""
    pasta_job = Path(pasta_job).resolve()
    plat = plat or plataforma.obter()
    estado = contratos.ler(pasta_job / 'estado.json', 'estado/1')
    laudo_arq = pasta_job / 'laudo' / 'laudo.json'
    laudo = contratos.ler(laudo_arq, 'laudo/1')
    licencas = contratos.ler(pasta_job / ARQUIVO_LICENCAS, ESQUEMA_LICENCAS) if (pasta_job / ARQUIVO_LICENCAS).is_file() else None
    leituras, arqs, caminhos = _ler_arquivos(pasta_job, estado, plat)
    faces = casamento.montar_faces(leituras)
    servidos = {}
    for f in faces:
        dados = bytes_para_servir(caminhos[f['sha256']].read_bytes(), f)
        f['servivel'] = dados is not None
        if dados is not None:
            servidos[f['id']] = (dados, servidor.MIME_POR_FORMATO[f['formato']])

    camadas_texto = _camadas_de_texto(laudo)
    usados = []
    for c in camadas_texto:
        for ps in _fontes_ps_da_camada(c):
            if ps not in usados:
                usados.append(ps)
    pares, metodos, n_cands = {}, {}, {}
    for ps in usados:
        face, metodo, n = casamento.casar(ps, faces)
        pares[ps], metodos[ps], n_cands[ps] = face, metodo, n

    prefixo = 'dsd-%s' % estado['job_id'][:8]  # numero-neutro: prefixo curto do job no nome da familia
    pagina, plano = medicao.montar(camadas_texto, pares, faces, prefixo)
    chromium = {'feito': False, 'motivo': None, 'versao': None, 'playwright': navegador.versao_playwright()}
    resposta = None
    cache = {'feito': False, 'copias_encontradas': None, 'arquivos_varridos': 0, 'metodo': navegador.METODO_VARREDURA,
             'cache_control': cache_control, 'perfil_apagado': None, 'perfil': PERFIL_TEMPORARIO,
             'perfil_caracteres': None, 'controle_encontrado': None, 'motivo': None}
    if not servidos:
        chromium['motivo'] = 'sem_face_servivel'
    elif not usar_chromium:
        chromium['motivo'] = 'desligado'
    else:
        # perfil num caminho curto: com o perfil num caminho longo o Chromium deixa de gravar cache, e o teste daria
        # 0 copia sem provar nada. O controle positivo (folha de estilo com cache liberado) prova que o perfil grava
        perfil = perfil_do_chromium()
        cache['perfil_caracteres'] = len(str(perfil))
        marcador = None
        try:
            with servidor.ServidorFontes(_com_controle(pagina), servidos, cache_control=cache_control) as srv:
                marcador = srv.marcador_controle
                resposta = navegador.conferir(srv.url_entrada, perfil,
                                              [medicao.familia_css(prefixo, i) for i in servidos],
                                              medicao.ids_para_cdp(plano))
                chromium['rotas'] = dict(srv.contagem)
            chromium.update(feito=True, versao=resposta['chromium'])
        except navegador.ErroNavegador as e:
            chromium['motivo'] = str(e)
        finally:
            cache.update(navegador.varrer_perfil(perfil, [d for d, _t in servidos.values()], marcador))
            # cache.feito so vale quando a varredura provou que o perfil grava cache
            cache['feito'] = bool(cache['controle_encontrado'])
            if not cache['feito']:
                cache['motivo'] = 'perfil_nao_gravou_o_controle' if resposta is not None else 'chromium_nao_rodou'
            cache['perfil_apagado'] = navegador.apagar_perfil(perfil)
    status = (resposta or {}).get('status') or {}
    cdp = (resposta or {}).get('cdp') or {}
    larguras = (resposta or {}).get('larguras') or {}

    # ---------------------------------------------------------- faces
    usadas = {f['id'] for f in pares.values() if f is not None}
    por_face = {}
    faces_saida = []
    for f in faces:
        mot = []
        carregada, confere, instalada = None, None, None
        if not f['servivel']:
            mot.append(_motivo('colecao_nao_servivel', 'bloqueante'))
        elif resposta is not None:
            carregada = status.get(medicao.familia_css(prefixo, f['id'])) == 'loaded'
            if not carregada:
                mot.append(_motivo('face_nao_carregou', 'bloqueante'))
            pid = plano['sondas'].get(f['id'])
            confere = medicao.face_confere(cdp.get(pid), f) if pid else None
            if confere is False and carregada:
                mot.append(_motivo('face_cdp_divergente', 'bloqueante'))
            elif confere is None and carregada:
                # sem resposta do CDP a face fica sem prova: nunca passa calada
                mot.append(_motivo('cdp_sem_resposta', 'bloqueante' if f['id'] in usadas else 'aviso'))
            did = plano['diagnostico'].get(f['id'])
            if did and cdp.get(did):
                nomes = {casamento.normalizar(n) for n in f['nomes_ps']}
                instalada = any(not x['propria'] and casamento.normalizar(x['nome_ps']) in nomes for x in cdp[did])
                if instalada:
                    mot.append(_motivo('instalada_mesmo_nome', 'ok'))
        elif f['id'] in usadas:
            mot.append(_motivo('chromium_nao_conferiu', 'bloqueante', {'motivo': chromium['motivo']}))
        if f['peso_estilo'] and f['us_weight_class'] and f['peso_estilo'] != f['us_weight_class']:
            mot.append(_motivo('peso_os2_diverge_do_estilo', 'aviso',
                               {'us_weight_class': f['us_weight_class'], 'peso_do_estilo': f['peso_estilo']}))
        if f['id'] not in usadas:
            mot.append(_motivo('face_nao_usada', 'ok'))
        canal, reg, mot_lic = licenca.avaliar(f, licencas)
        mot.extend(mot_lic)
        sit = pior(mot)
        por_face[f['id']] = {'canal': canal, 'registro': reg, 'situacao': sit, 'motivos': mot,
                             'instalada_mesmo_nome': instalada, 'carregada': carregada, 'confere': confere,
                             'conferencia': {'metodo': 'cdp_css_getplatformfontsfornode' if resposta else None,
                                             'face_cdp_confere': confere, 'largura_erro_max_pct': None}}
        faces_saida.append({
            'id': f['id'], 'nome_ps': f['nome_ps'], 'nomes_ps': f['nomes_ps'], 'familia': f['familia'],
            'estilo': f['estilo'], 'formato': f['formato'], 'sha256': f['sha256'], 'indice': f['indice'],
            'versao_name': f['versao_name'], 'peso_declarado': f['peso_declarado'],
            'us_weight_class': f['us_weight_class'], 'metricas': f['metricas'], 'canal': canal,
            'usada': f['id'] in usadas, 'carregada': carregada, 'face_cdp_confere': confere,
            'instalada_mesmo_nome': instalada, 'situacao': sit, 'motivos': mot})

    # ---------------------------------------------------------- camadas
    limiar = limites.obter('fontes.largura_divergencia_pct')
    itens_plano = {it['layer_id']: it for it in plano['camadas']}
    camadas_saida = []
    for c in camadas_texto:
        lid = c['identidade']['layer_id']
        item = itens_plano[lid]
        erro = medicao.erro_largura_pct(item, larguras) if resposta is not None else None
        for ps in _fontes_ps_da_camada(c):
            runs = [r for r in c['texto']['runs'] if r.get('fonte_ps') == ps]
            com_tinta = any(any(casamento.tem_tinta(ch) for ch in casamento.texto_do_trecho(r)) for r in runs)
            face = pares.get(ps)
            mot, glifos, confere, decisao = [], 0, None, None
            if not com_tinta:
                mot.append(_motivo('so_em_espaco', 'ok'))
            if face is None:
                if com_tinta:
                    mesma = casamento.faces_da_mesma_familia(ps, faces)
                    if mesma:
                        mot.append(_motivo('nome_ps_sem_par', 'bloqueante', {'faces_da_mesma_familia': len(mesma)}))
                        pedido = casamento.peso_do_estilo(ps)
                        if pedido is not None and all(m['peso_declarado'] != pedido for m in mesma):
                            mot.append(_motivo('face_divergente', 'bloqueante', {'peso_pedido': pedido}))
                    else:
                        mot.append(_motivo('arquivo_faltando', 'bloqueante'))
            else:
                if metodos[ps] != 'nome_ps':
                    mot.append(_motivo('casada_por_%s' % metodos[ps], 'aviso'))
                if n_cands[ps] > 1:
                    mot.append(_motivo('mais_de_um_arquivo', 'bloqueante', {'arquivos': n_cands[ps]}))
                glifos = casamento.glifos_faltando(face, [casamento.texto_do_trecho(r) for r in runs])
                if glifos:
                    mot.append(_motivo('glifo_faltando', 'bloqueante', {'caracteres': glifos}))
                if resposta is None:
                    if com_tinta:
                        mot.append(_motivo('chromium_nao_conferiu', 'bloqueante', {'motivo': chromium['motivo']}))
                else:
                    spans = [s for s in item['spans'] if s['fonte_ps'] == ps and s['cdp']]
                    resp = [medicao.face_confere(cdp.get(s['id']), face) for s in spans]
                    confere = None if not spans or any(x is None for x in resp) else all(resp)
                    if confere is False:
                        estranha = any(not x['propria'] for s in spans for x in (cdp.get(s['id']) or []))
                        mot.append(_motivo('fallback' if estranha else 'face_cdp_divergente', 'bloqueante'))
                    elif confere is None and com_tinta:
                        mot.append(_motivo('cdp_sem_resposta', 'bloqueante',
                                           {'trechos_sem_resposta': sum(1 for x in resp if x is None),
                                            'trechos': len(spans)}))
                fsit = por_face[face['id']]['situacao']
                if fsit != 'ok':
                    mot.append(_motivo('face_com_bloqueio', fsit, {'face_id': face['id']}))
            if com_tinta and face is not None:
                if item['motivo_sem_largura']:
                    mot.append(_motivo(item['motivo_sem_largura'], 'ok'))
                elif erro is not None and abs(erro) > limiar.valor:
                    decisao = 'pede_decisao_do_da'
                    mot.append(_motivo('largura_divergente', 'bloqueante', {'erro_pct': round(erro, 4)},  # numero-neutro: casas da medida
                                       'fontes.largura_divergencia_pct'))
            sit = pior(mot)
            camadas_saida.append({
                'layer_id': lid, 'nome_ps': ps, 'face_id': face['id'] if face else None,
                'metodo_casamento': metodos.get(ps), 'glifos_faltando': glifos,
                'largura_erro_max_pct': round(abs(erro), 4) if erro is not None and face is not None else None,  # numero-neutro: casas da medida
                'largura_erro_pct': round(erro, 4) if erro is not None and face is not None else None,  # numero-neutro: casas da medida
                'face_cdp_confere': confere, 'situacao': sit, 'decisao': decisao, 'motivos': mot})
    for f in faces:
        erros = [x['largura_erro_max_pct'] for x in camadas_saida if x['face_id'] == f['id'] and x['largura_erro_max_pct'] is not None]
        por_face[f['id']]['conferencia']['largura_erro_max_pct'] = max(erros) if erros else None

    fora, varridos = varrer_fontes_fora_da_entrada(pasta_job)
    resumo = _resumo(faces_saida, camadas_saida, arqs, cache)
    conf = {'esquema': ESQUEMA, 'job_id': estado['job_id'], 'gerado_em': agora(),
            'laudo_sha256': arquivos.sha256_arquivo(laudo_arq), 'arquivo_sha256': laudo['origem']['sha256'],
            'licencas_sha256': arquivos.sha256_arquivo(pasta_job / ARQUIVO_LICENCAS) if licencas is not None else None,
            'limites': [limiar.citacao()], 'chromium': chromium, 'faces': faces_saida, 'camadas': camadas_saida,
            'arquivos': arqs, 'cache': cache,
            'varredura': {'arquivos_de_fonte_fora_da_entrada': fora, 'arquivos_varridos': varridos},
            'resumo': resumo}
    contratos.gravar(pasta_job / ARQUIVO, conf, ESQUEMA)
    man = licenca.manifesto(estado['job_id'], faces, [{k: a[k] for k in ('sha256', 'formato', 'situacao', 'motivo')}
                                                       for a in arqs], por_face, conf['gerado_em'])
    contratos.gravar(pasta_job / ARQUIVO_MANIFESTO, man, ESQUEMA_MANIFESTO)
    return conf


def _resumo(faces, camadas, arqs, cache):
    def contar(itens, sit):
        return sum(1 for x in itens if x['situacao'] == sit)
    erros = [c['largura_erro_max_pct'] for c in camadas if c['largura_erro_max_pct'] is not None]
    return {'faces': len(faces), 'faces_ok': contar(faces, 'ok'), 'faces_aviso': contar(faces, 'aviso'),
            'faces_bloqueantes': contar(faces, 'bloqueante'),
            'arquivos': len(arqs), 'arquivos_recusados': sum(1 for a in arqs if a['situacao'] == 'recusado'),
            'camadas': len(camadas), 'camadas_ok': contar(camadas, 'ok'), 'camadas_aviso': contar(camadas, 'aviso'),
            'camadas_bloqueantes': contar(camadas, 'bloqueante'),
            'sem_par': sum(1 for c in camadas if c['face_id'] is None and c['situacao'] == 'bloqueante'),
            'glifos_faltando': sum(c['glifos_faltando'] for c in camadas),
            'larguras_divergentes': sum(1 for c in camadas if c['decisao'] == 'pede_decisao_do_da'),
            'cdp_confere': sum(1 for c in camadas if c['face_cdp_confere'] is True),
            'cdp_diverge': sum(1 for c in camadas if c['face_cdp_confere'] is False),
            'largura_erro_max_pct': max(erros) if erros else None,
            'copias_no_cache': cache['copias_encontradas'], 'cache_provado': int(bool(cache['feito']))}


def sha256(pasta_job):
    p = Path(pasta_job) / ARQUIVO
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
