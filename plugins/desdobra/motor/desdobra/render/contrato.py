# -*- coding: utf-8 -*-
"""Contrato da composicao (composicao/1): o que o render desenha num formato, montado so de arquivos do job.

No M4 o contrato e o da origem: o KV desenhado em si mesmo, na identidade, montado do laudo (estrutura bruta do
filho do leitor), da conferencia de fontes e dos linkados confirmados pelo DA. O M5 (derivacao) grava o mesmo
formato para os outros formatos: muda o canvas, a escala e a caixa de cada entrada, nunca a forma das entradas.

Entradas, de baixo para cima, na ordem de desenho do PSD:
  - pilha: camadas sem texto que ficam entre duas camadas de texto, compostas juntas pelo compositor do psd-tools
    no processo filho (desdobra.render.pilhas), com as mascaras, mesclagens, ajustes e efeitos que ele desenha. O
    asset da pilha nasce no render e fica em render/assets/<sha256>.png, indexado pelo hash da pilha;
  - texto: uma camada de texto, desenhada pelo caminho do texto (Chromium, PDF em memoria, PDFium, gama);
  - linkado: um smart object linkado, desenhado com o arquivo de entrada/campanha/ que o DA confirmou, pela
    caixa de colocacao da camada (arquitetura-v1.md, 7.2).
Camada com funcao "fora da peca" (funcoes, quando vem da derivacao ou do briefing) nao entra em nenhuma entrada.

Bloqueios (o render recusa enquanto houver): composicao do documento acima do orcamento no laudo, modo de cor fora
da v1, conferencia de fontes ausente ou de outro laudo, fonte com bloqueio tecnico, linkado visivel sem confirmacao.
A divergencia de largura da conferencia de fontes e decisao do DA: o render pede confirmacao no terminal.

Funcao pura dos arquivos lidos: nao abre PSD, fonte nem imagem.
"""
import hashlib
import json
from pathlib import Path

from desdobra import arquivos, contratos, limites
from desdobra.fontes import casamento, conferencia

ESQUEMA = 'composicao/1'
FORMATO_ORIGEM = 'origem'
ARQUIVO_LINKADOS = Path('briefing') / 'linkados-confirmados.json'
ESQUEMA_LINKADOS = 'linkados-confirmados/1'
TIPOS_SEM_DESENHO = ('group', 'artboard')
FUNCAO_FORA = 'fora_da_peca'
MODOS_ACEITOS = ('RGB',)
BITS_ACEITOS = (8,)  # numero-neutro: a v1 compoe documentos de 8 bits por canal (o corpus inteiro)
OPACIDADE_CHEIA = 255.0  # numero-neutro: opacidade de 8 bits do PSD
CASAS_COR = 6  # numero-neutro: casas da chave de cor; nao muda o desenho
# motivos de camada da conferencia de fontes que o render nao contorna (a divergencia de largura e decisao do DA)
MOTIVOS_QUE_BLOQUEIAM = tuple(m for m in conferencia.TECNICOS if m != 'largura_divergente')
DESCRICOES_BLOQUEIO = {
    'composicao_acima_do_orcamento': 'A composição do documento passou do orçamento de memória ou de tempo na leitura '
                                     '(laudo, recusas). O render não compõe este documento.',
    'modo_de_cor_fora_da_v1': 'A v1 só compõe documentos RGB de 8 bits por canal.',
    'sem_estrutura': 'O laudo não tem a estrutura lida do documento.',
    'fontes_nao_conferidas': 'A conferência de fontes não rodou para este laudo. Peça ao Claude para seguir o job '
                             '(/desdobra:continuar).',
    'conferencia_desatualizada': 'A conferência de fontes é de outro laudo. Peça ao Claude para seguir o job '
                                 '(/desdobra:continuar).',
    'fonte_bloqueante': 'A conferência de fontes tem bloqueio técnico numa camada de texto visível (arquivo '
                        'faltando, nome sem par, glifo faltando, fallback ou face não confirmada).',
    'arquivo_de_fonte_fora_do_job': 'Um arquivo de fonte da conferência não está mais em entrada/fontes/.',
    'linkado_sem_confirmacao': 'Há smart object linkado visível sem o arquivo casado e confirmado pelo DA. A '
                               'confirmação do arquivo é um clique do DA na tela de briefing.',
    'linkado_confirmado_mudou': 'O arquivo confirmado para um linkado mudou ou saiu de entrada/campanha/.',
    'linkado_confirmado_no_modo_de_teste': 'O linkado foi confirmado no modo de teste da tela, ou antes de a '
                                           'confirmação gravar quem confirmou. Confirme o arquivo do linkado de novo '
                                           'na tela de briefing.',
    'spec_confirmada_no_modo_de_teste': 'Um valor de spec foi confirmado no modo de teste da tela. Confirme o valor '
                                        'de novo na tela de briefing.',
    'largura_divergente': 'A conferência de fontes achou divergência de largura numa camada de texto. É decisão do DA, '
                          'que a aceita na confirmação do render, na tela.',
    'fases_desatualizadas': 'Uma fase de que o render depende (leitura, fontes, segunda passada do laudo ou design '
                            'system) não está válida contra as entradas atuais. Peça ao Claude para seguir o job '
                            '(/desdobra:continuar).',
    'entrada_alterada_fora_do_motor': 'Uma entrada congelada do job mudou, sumiu ou apareceu fora do motor.',
    'laudo_de_outro_kv': 'O laudo não é do KV que está em entrada/. Peça ao Claude para seguir o job '
                         '(/desdobra:continuar).',
    'trecho_sem_face': 'Uma camada de texto visível tem trecho com tinta sem face do job: o texto sairia sem esse trecho.',
    'linkados_de_outro_laudo': 'Os linkados confirmados são de outro laudo ou de outro KV. O DA confirma o arquivo '
                               'de cada linkado de novo, com um clique na tela de briefing.',
    'linkado_formato_sem_suporte': 'O arquivo confirmado para um linkado não é PNG nem JPEG. O render da v1 só coloca '
                                   'linkado PNG ou JPEG; exporte a arte nesse formato e confirme de novo.',
    'efeito_sobre_texto_sem_aplicar': 'Há ajuste ou mesclagem diferente da normal acima de uma camada de texto. O render '
                                      'do M4 compõe essas camadas sem o texto de baixo: o ajuste ou a mesclagem não '
                                      'pega o texto. É decisão do DA aceitar o master assim.',
    'clipping_dividido_por_texto': 'Uma camada clipada fica acima de um texto clipado na mesma base. O render do M4 não '
                                   'desenha essa camada (a base fica na pilha de baixo do texto). É decisão do DA.',
}
FASES_DO_RENDER = ('ler', 'fontes', 'laudo-fontes', 'ds')
FORMATOS_LINKADO = ('image/png', 'image/jpeg')
# a origem do Disparo nas confirmacoes (desdobra.humano): so a do DA vale para o render
ORIGEM_DA = 'da'
ORIGEM_FIXTURE = 'fixture_de_teste'


class ErroContrato(Exception):
    pass


def _sha_texto(dados):
    return hashlib.sha256(json.dumps(dados, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def _bloqueio(codigo, **medidas):
    return {'codigo': codigo, 'descricao': DESCRICOES_BLOQUEIO[codigo], 'medidas': medidas}


def _registro(codigo, layer_id=None, **medidas):
    return {'codigo': codigo, 'layer_id': layer_id, 'medidas': medidas}


# ------------------------------------------------------------------ leitura dos arquivos do job
def estrutura_do_documento(pasta_job, laudo):
    caminho = Path(pasta_job) / 'laudo' / 'bruto' / laudo['origem']['sha256'] / 'estrutura.json'
    if not caminho.is_file():
        return None, None
    return contratos.ler(caminho, 'estrutura/1'), caminho


def faces_do_job(pasta_job, estado):
    """As faces do job como a conferencia montou (mesma ordem e mesmos ids), a partir das leituras gravadas pela
    fase fontes em fontes/bruto/<sha256>/leitura.json. O processo principal nao abre o arquivo de fonte."""
    leituras = []
    for rel, reg in sorted(estado['entradas'].items()):
        if not rel.startswith(conferencia.PASTA_ENTRADA):
            continue
        arq = Path(pasta_job) / 'fontes' / 'bruto' / reg['sha256'] / 'leitura.json'
        if arq.is_file():
            leitura = contratos.ler(arq, 'leitura-fonte/1')
            if leitura.get('situacao') == 'lida':
                leituras.append((reg['sha256'], leitura))
    return casamento.montar_faces(leituras)


def linkados_confirmados(pasta_job, laudo_sha256=None, kv_sha256=None):
    """{unique_id: confirmacao}. Com laudo_sha256 e kv_sha256, devolve None quando o arquivo e de outro laudo ou KV."""
    arq = Path(pasta_job) / ARQUIVO_LINKADOS
    if not arq.is_file():
        return {}
    dados = contratos.ler(arq, ESQUEMA_LINKADOS)
    if (laudo_sha256 is not None and dados['laudo_sha256'] != laudo_sha256) or \
            (kv_sha256 is not None and dados['kv_sha256'] != kv_sha256):
        return None
    return {item['unique_id']: item for item in dados['linkados']}


def _intersecta(a, b):
    return bool(a and b and _interseccao(a, b))


# ------------------------------------------------------------------ geometria
def _interseccao(a, b):
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    return [x0, y0, x1, y1] if x1 > x0 and y1 > y0 else None


def _uniao(a, b):
    if not a:
        return b
    if not b:
        return a
    return [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]


def regiao_do_texto(reg, largura, altura):
    """Caixa da camada (e a de tinta) com a margem do render, dentro do canvas."""
    m = int(limites.valor('render.margem_regiao_px'))
    caixa = _uniao(reg.get('caixa'), reg.get('caixa_tinta'))
    if not caixa:
        return None
    return _interseccao([caixa[0] - m, caixa[1] - m, caixa[2] + m, caixa[3] + m], [0, 0, largura, altura])


def corpo_no_dispositivo(texto):
    """Maior corpo da camada no dispositivo, pelos eixos da matriz (como na pesquisa, gama/g_comum.py)."""
    xx, xy, yx, yy = texto['matriz'][:4]
    ex, ey = (xx * xx + xy * xy) ** 0.5, (yx * yx + yy * yy) ** 0.5
    corpos = [float(r.get('corpo_espaco_texto') or 0) for r in texto.get('runs') or [] if r.get('tem_tinta')]
    return max(corpos, default=0.0) * max(ex, ey)


# ------------------------------------------------------------------ texto
def _cor_do_overlay(reg):
    """Cor de um ColorOverlay ativo, normal e opaco na camada de texto (no espaco do documento), ou None."""
    for d in reg.get('cores_descritores') or []:
        if d.get('descritor') != 'overlay' or not d.get('ativo') or d.get('classe') != 'RGBC':
            continue
        efs = reg.get('efeitos') or []
        k = d.get('indice_efeito')
        med = (efs[k].get('medidas') or {}) if k is not None and k < len(efs) else {}
        if med.get('blend') not in (None, 'NORMAL', 'Nrml', 'normal') or med.get('opacity') not in (None, 100.0, 100):  # numero-neutro: opacidade cheia do efeito em porcentagem
            return None
        v = d.get('valores') or {}
        try:
            return [float(v['Rd']) / OPACIDADE_CHEIA, float(v['Grn']) / OPACIDADE_CHEIA, float(v['Bl']) / OPACIDADE_CHEIA]
        except (KeyError, TypeError, ValueError):
            return None
    return None


def _opacidade_dos_grupos(reg, por_id):
    op = 1.0
    for gid in reg.get('caminho_ids') or []:
        g = por_id.get(gid)
        if g is not None:
            op *= float(g.get('opacidade', OPACIDADE_CHEIA)) / OPACIDADE_CHEIA
    return op


def _entrada_texto(reg, ident, por_id, pares, doc, registros):
    t = reg['texto']
    lid = reg['layer_id']
    regiao = regiao_do_texto(reg, doc['largura'], doc['altura'])
    if regiao is None:
        registros.append(_registro('texto_fora_do_canvas', lid))
        return None
    overlay = _cor_do_overlay(reg)
    if overlay is not None:
        registros.append(_registro('color_overlay_como_cor_do_texto', lid))
    for e in reg.get('efeitos') or []:
        if e.get('ativo') and not (e.get('tipo') == 'ColorOverlay' and overlay is not None):
            registros.append(_registro('efeito_de_texto_nao_desenhado', lid, efeito=e.get('tipo')))
    runs, cores, valores, por_trecho, faces = [], [], {}, {}, {}
    for r in t.get('runs') or []:
        if not r.get('texto'):
            continue
        cv = r.get('cor_valores') or [1.0, 0.0, 0.0, 0.0]
        rgb = overlay if overlay is not None else [float(x) for x in cv[1:4]]
        chave = ','.join('%.*f' % (CASAS_COR, x) for x in rgb)
        if chave not in valores:
            valores[chave] = {'id': 'c%d' % len(valores), 'rgb': rgb, 'alfa': float(cv[0]) if overlay is None else 1.0}
            cores.append(valores[chave]['id'])
        por_trecho[str(r['inicio'])] = valores[chave]['id']
        ps = r.get('fonte_ps')
        face = pares.get(ps)
        if face is not None:
            faces[ps] = face['id']
        if r.get('tem_tinta'):
            for campo, codigo in (('faux_bold', 'faux_bold_sem_emulacao'), ('faux_italic', 'faux_italic_sem_emulacao'),
                                  ('sublinhado', 'sublinhado_nao_desenhado'), ('tachado', 'tachado_nao_desenhado'),
                                  ('traco_texto', 'traco_de_texto_nao_desenhado')):
                if r.get(campo):
                    registros.append(_registro(codigo, lid))
            if r.get('baseline_shift'):
                registros.append(_registro('deslocamento_de_linha_de_base_nao_desenhado', lid))
            for k in ('escala_h', 'escala_v'):
                if r.get(k) is not None and abs(float(r[k]) - 1.0) > limites.valor('laudo.tolerancia_escala_texto'):
                    registros.append(_registro('escala_de_trecho_nao_desenhada', lid, eixo=k))
        runs.append({k: r.get(k) for k in ('inicio', 'fim', 'texto', 'fonte_ps', 'corpo_espaco_texto', 'tracking',
                                           'entrelinha', 'autoleading', 'font_caps', 'autokerning', 'kerning',
                                           'ligaduras', 'tem_tinta', 'faux_bold')})
    if not any(r.get('tem_tinta') for r in runs):
        return None
    if t.get('tipo_caixa') != 'ponto':
        registros.append(_registro('caixa_de_paragrafo_quebrada_pela_largura_da_caixa', lid))
    if (t.get('warp') or {}).get('estilo') not in (None, 'warpNone'):
        registros.append(_registro('warp_de_texto_nao_desenhado', lid))
    if reg.get('blend') not in ('NORMAL', 'PASS_THROUGH'):
        registros.append(_registro('mesclagem_de_texto_desenhada_como_normal', lid, blend=reg.get('blend')))
    if reg.get('clipping'):
        registros.append(_registro('texto_clipado_desenhado_sem_clip', lid))
    for gid in reg.get('caminho_ids') or []:
        g = por_id.get(gid) or {}
        gm = g.get('mascara') or {}
        if g.get('blend') not in ('PASS_THROUGH', 'NORMAL') or (gm.get('raster') and not gm.get('desativada')) or \
                (gm.get('vetorial') and not gm.get('vetorial_desativada')):
            registros.append(_registro('texto_em_grupo_com_mascara_ou_mesclagem', lid, grupo=gid))
            break
    corpo = corpo_no_dispositivo(t)
    aa = (t.get('runs') or [{}])[0].get('antialiasing')
    sharp_pequeno = aa == 'antiAliasSharp' and corpo <= limites.valor('render.corpo_sharp_pequeno_px')
    opacidade = (float(reg.get('opacidade', OPACIDADE_CHEIA)) / OPACIDADE_CHEIA *
                 float(reg.get('preenchimento', OPACIDADE_CHEIA)) / OPACIDADE_CHEIA * _opacidade_dos_grupos(reg, por_id))
    return {'id': ident, 'tipo': 'texto', 'indice': reg['indice'], 'layer_id': lid, 'regiao': regiao,
            'opacidade': round(opacidade, 6), 'blend': reg.get('blend'),
            'texto': {'matriz': t['matriz'], 'runs': runs, 'paragrafos': t.get('paragrafos') or [],
                      'tipo_caixa': t.get('tipo_caixa'), 'box_bounds': t.get('box_bounds')},
            'faces': faces, 'cores': cores, 'valores_cor': {v['id']: {'rgb': v['rgb'], 'alfa': v['alfa']} for v in valores.values()},
            'cores_por_trecho': por_trecho, 'antialiasing': aa, 'corpo_dispositivo_px': round(corpo, 4),
            'sharp_pequeno': bool(sharp_pequeno)}


# ------------------------------------------------------------------ montagem
def _folhas(regs):
    return [r for r in regs if r.get('kind') not in TIPOS_SEM_DESENHO and r.get('visivel_efetiva')]


def montar(pasta_job, *, funcoes=None, formato=FORMATO_ORIGEM):
    """Monta o contrato da origem. funcoes: {layer_id: funcao} (da derivacao ou do briefing; no M4, opcional).
    Devolve (contrato, bloqueios, pede_confirmacao): bloqueios param o render; pede_confirmacao sao decisoes que o
    DA confirma no terminal (divergencia de largura)."""
    pasta_job = Path(pasta_job).resolve()
    estado = contratos.ler(pasta_job / 'estado.json', 'estado/1')
    laudo_arq = pasta_job / 'laudo' / 'laudo.json'
    laudo = contratos.ler(laudo_arq, 'laudo/1')
    bloqueios, confirmar, registros = [], [], []
    # o render so vale com as fases de que depende validas contra as entradas atuais (troca de entrada sem job
    # proxima deixa o laudo, a conferencia ou o design system velhos)
    from desdobra.job import fases as mod_fases, nucleo
    if nucleo.conferir_entradas(pasta_job, estado):
        bloqueios.append(_bloqueio('entrada_alterada_fora_do_motor'))
    avaliacao, _diretas = nucleo.avaliar(pasta_job, estado, mod_fases.ESTEIRA)
    invalidas = sorted(f for f in FASES_DO_RENDER if f in avaliacao and not avaliacao[f][0])
    if invalidas:
        bloqueios.append(_bloqueio('fases_desatualizadas', fases=invalidas))
    rel_kv = next((r for r in sorted(estado['entradas']) if r.startswith('entrada/kv')), None)
    kv_atual = estado['entradas'][rel_kv]['sha256'] if rel_kv else None
    if kv_atual != laudo['origem']['sha256']:
        bloqueios.append(_bloqueio('laudo_de_outro_kv'))
    laudo_sha = arquivos.sha256_arquivo(laudo_arq)
    from desdobra.specs import importar
    try:
        acoes_spec = importar.ler_confirmacoes(pasta_job)['acoes']
    except (contratos.ErroContrato, OSError, ValueError):
        acoes_spec = []
    if any(a.get('por') == ORIGEM_FIXTURE for a in acoes_spec):
        # o valor de spec confirmado no modo de teste da tela nunca chega ao master (revisao do M7a)
        bloqueios.append(_bloqueio('spec_confirmada_no_modo_de_teste'))
    doc_l = laudo['documento']
    if any(r.get('etapa') == 'composicao' for r in laudo.get('recusas') or []):
        bloqueios.append(_bloqueio('composicao_acima_do_orcamento'))
    if doc_l.get('modo') not in MODOS_ACEITOS or doc_l.get('bits') not in BITS_ACEITOS:
        bloqueios.append(_bloqueio('modo_de_cor_fora_da_v1', modo=doc_l.get('modo'), bits=doc_l.get('bits')))
    estrutura, arq_estrutura = estrutura_do_documento(pasta_job, laudo)
    if estrutura is None:
        bloqueios.append(_bloqueio('sem_estrutura'))
        return None, bloqueios, confirmar
    regs = estrutura['camadas']
    por_id = {}
    for r in regs:
        por_id.setdefault(r['layer_id'], r)
    doc = {'largura': estrutura['documento']['largura'], 'altura': estrutura['documento']['altura'],
           'modo': doc_l.get('modo'), 'bits': doc_l.get('bits')}
    icc = estrutura['documento'].get('icc') or {}
    perfil = None
    if icc.get('arquivo'):
        rel = (arq_estrutura.parent / icc['arquivo']).relative_to(pasta_job).as_posix()
        perfil = {'arquivo': rel, 'sha256': icc.get('sha256'), 'nome': icc.get('descricao')}
    doc['perfil'] = perfil

    # fontes: a conferencia tem de ser deste laudo
    conf_arq = pasta_job / conferencia.ARQUIVO
    conf = contratos.ler(conf_arq, conferencia.ESQUEMA) if conf_arq.is_file() else None
    # so os textos que este render desenha: a camada fora da peca (no formato derivado, a que nao tem elemento, como a
    # de outra tela) nao entra na conferencia das fontes nem na decisao de largura
    fora_do_render = {int(k) for k, v in (funcoes or {}).items() if v == FUNCAO_FORA}
    textos = [r for r in _folhas(regs) if r.get('kind') == 'type' and (r.get('texto') or {}).get('runs')
              and r['layer_id'] not in fora_do_render]
    faces = faces_do_job(pasta_job, estado)
    pares = {}
    if textos:
        if conf is None:
            bloqueios.append(_bloqueio('fontes_nao_conferidas'))
        elif conf['laudo_sha256'] != arquivos.sha256_arquivo(laudo_arq):
            bloqueios.append(_bloqueio('conferencia_desatualizada'))
        else:
            for ps in sorted({r.get('fonte_ps') for c in textos for r in c['texto']['runs'] if r.get('fonte_ps')}):
                pares[ps] = casamento.casar(ps, faces)[0]
            shas = {reg['sha256'] for rel, reg in estado['entradas'].items() if rel.startswith(conferencia.PASTA_ENTRADA)}
            if any(f['sha256'] not in shas for f in pares.values() if f is not None):
                bloqueios.append(_bloqueio('arquivo_de_fonte_fora_do_job'))
            ids_textos = {c['layer_id'] for c in textos}
            sem_face = sorted({c['layer_id'] for c in textos for r in c['texto']['runs']
                               if r.get('tem_tinta') and pares.get(r.get('fonte_ps')) is None})
            if sem_face:
                bloqueios.append(_bloqueio('trecho_sem_face', camadas=sem_face))
            divergentes = []
            for item in conf['camadas']:
                if item['layer_id'] not in ids_textos:
                    continue
                codigos = {m['codigo'] for m in item['motivos'] if m['situacao'] == 'bloqueante'}
                if codigos & set(MOTIVOS_QUE_BLOQUEIAM) or ('face_com_bloqueio' in codigos):
                    bloqueios.append(_bloqueio('fonte_bloqueante', layer_id=item['layer_id'],
                                               motivos=sorted(codigos - {'largura_divergente'})))
                if 'largura_divergente' in codigos and item['layer_id'] not in {x['layer_id'] for x in divergentes}:
                    # um item por camada (a conferencia tem um por face da camada; vale o primeiro, o da face do
                    # primeiro trecho)
                    divergentes.append({'layer_id': item['layer_id'], 'erro_pct': item.get('largura_erro_pct')})
            if divergentes:
                confirmar.append(dict(_bloqueio('largura_divergente'), medidas={'camadas': divergentes}))

    # linkados: so com o arquivo casado e confirmado pelo DA
    confirmados = linkados_confirmados(pasta_job, laudo_sha, laudo['origem']['sha256'])
    if confirmados is None:
        bloqueios.append(_bloqueio('linkados_de_outro_laudo'))
        confirmados = {}
    divididos = []
    funcoes = {int(k): v for k, v in (funcoes or {}).items()}
    entradas, pilha = [], []
    fora = []
    tipo_por_indice = {}

    def fechar_pilha():
        if pilha:
            ids = [regs[i]['layer_id'] for i in pilha]
            entradas.append({'id': 'e%02d' % (len(entradas) + 1), 'tipo': 'pilha', 'indices': list(pilha),
                             'layer_ids': ids, 'chave': None})
            pilha.clear()

    for reg in _folhas(regs):
        i, lid = reg['indice'], reg['layer_id']
        if funcoes.get(lid) == FUNCAO_FORA:
            fora.append(lid)
            continue
        if reg.get('clipping'):
            base = por_id.get(reg.get('base_do_clip'))
            tipo_base = tipo_por_indice.get(base['indice']) if base is not None else None
            if tipo_base in ('texto', 'linkado'):
                registros.append(_registro('camada_clipada_em_%s_nao_desenhada' % tipo_base, lid))
                continue
            if tipo_base is None and base is not None and funcoes.get(base['layer_id']) == FUNCAO_FORA:
                fora.append(lid)
                continue
            if tipo_base == 'pilha' and base['indice'] not in pilha:
                # a base ficou numa pilha de baixo (um texto clipado no meio): o psd-tools so desenha a camada clipada
                # junto da base, entao ela sumiria em silencio
                divididos.append({'layer_id': lid, 'base': base['layer_id']})
                tipo_por_indice[i] = 'dividida'
                continue
        so = reg.get('smart_object') or {}
        if reg.get('kind') == 'type' and (reg.get('texto') or {}).get('runs'):
            fechar_pilha()
            e = _entrada_texto(reg, 'e%02d' % (len(entradas) + 1), por_id, pares, doc, registros)
            tipo_por_indice[i] = 'texto'
            if e is not None:
                entradas.append(e)
            continue
        if reg.get('kind') == 'smartobject' and not so.get('embutido') and so.get('tipo') == 'linkado':
            fechar_pilha()
            tipo_por_indice[i] = 'linkado'
            c = confirmados.get(so.get('unique_id'))
            if c is None:
                bloqueios.append(_bloqueio('linkado_sem_confirmacao', layer_id=lid))
                continue
            if (c.get('confirmado_por') or {}).get('origem') != ORIGEM_DA:
                # so a confirmacao do DA vale; a do modo de teste e a sem origem gravada, nao (revisao do M7a)
                bloqueios.append(_bloqueio('linkado_confirmado_no_modo_de_teste', layer_id=lid))
                continue
            reg_entrada = estado['entradas'].get(c['arquivo'])
            if not c['arquivo'].startswith('entrada/campanha/') or reg_entrada is None or \
                    reg_entrada['sha256'] != c['sha256']:
                bloqueios.append(_bloqueio('linkado_confirmado_mudou', layer_id=lid))
                continue
            from desdobra.specs import validar as mod_validar
            cab = mod_validar.ler_arquivo(pasta_job / c['arquivo'])
            if cab['mime'] not in FORMATOS_LINKADO or not cab['largura'] or not cab['altura']:
                bloqueios.append(_bloqueio('linkado_formato_sem_suporte', layer_id=lid))
                continue
            if reg.get('efeitos') and any(e.get('ativo') for e in reg['efeitos']):
                registros.append(_registro('efeito_de_linkado_nao_desenhado', lid))
            mk = reg.get('mascara') or {}
            if (mk.get('raster') and not mk.get('desativada')) or (mk.get('vetorial') and not mk.get('vetorial_desativada')):
                registros.append(_registro('mascara_de_linkado_nao_desenhada', lid))
            entradas.append({'id': 'e%02d' % (len(entradas) + 1), 'tipo': 'linkado', 'indice': i, 'layer_id': lid,
                             'arquivo': c['arquivo'], 'sha256': c['sha256'],
                             'colocacao': so.get('transformacao') if so.get('transformacao') and len(so['transformacao']) == 8 else None,  # numero-neutro: o quadrilatero tem 8 coordenadas
                             'caixa': reg.get('caixa'),
                             'opacidade': round(float(reg.get('opacidade', OPACIDADE_CHEIA)) / OPACIDADE_CHEIA *
                                                float(reg.get('preenchimento', OPACIDADE_CHEIA)) / OPACIDADE_CHEIA *
                                                _opacidade_dos_grupos(reg, por_id), 6),
                             'blend': reg.get('blend'), 'dims': [cab['largura'], cab['altura']]})
            if reg.get('blend') not in ('NORMAL', 'PASS_THROUGH'):
                registros.append(_registro('mesclagem_de_linkado_desenhada_como_normal', lid, blend=reg.get('blend')))
            continue
        tipo_por_indice[i] = 'pilha'
        pilha.append(i)
    fechar_pilha()

    # pilhas acima de texto sao compostas isoladas e entram por cima em mesclagem normal: o ajuste (que atua no
    # formato inteiro) e a mesclagem diferente da normal que cruza um texto de baixo nao pegam esse texto. O M4 nao
    # aplica isso certo: vira decisao do DA, nunca so registro
    regioes_abaixo, efeitos = [], []
    for e in entradas:
        if e['tipo'] == 'texto':
            regioes_abaixo.append(e['regiao'])
        elif e['tipo'] == 'pilha' and regioes_abaixo:
            for i in e['indices']:
                r = regs[i]
                if r.get('ajuste'):
                    efeitos.append({'layer_id': r['layer_id'], 'ajuste': (r['ajuste'] or {}).get('tipo')})
                elif r.get('blend') not in ('NORMAL', 'PASS_THROUGH') and any(
                        _intersecta(r.get('caixa_tinta') or r.get('caixa'), g) for g in regioes_abaixo):
                    efeitos.append({'layer_id': r['layer_id'], 'blend': r.get('blend')})
    if efeitos:
        confirmar.append(dict(_bloqueio('efeito_sobre_texto_sem_aplicar'), medidas={'camadas': efeitos}))
    if divididos:
        confirmar.append(dict(_bloqueio('clipping_dividido_por_texto'), medidas={'camadas': divididos}))
    for e in entradas:
        if e['tipo'] == 'pilha':
            # a chave da pilha e o sha256 do KV que esta em entrada/ agora (nunca o do laudo, que pode ser de outro)
            e['chave'] = _sha_texto({'kv': kv_atual, 'indices': e['indices']})
    contrato = {
        'esquema': ESQUEMA, 'job_id': estado['job_id'],
        'formato': {'chave': formato, 'largura': doc['largura'], 'altura': doc['altura'], 'escala': 1.0},
        'documento': doc,
        'origem': {'kv_sha256': kv_atual, 'laudo_sha256': laudo_sha,
                   'conferencia_sha256': arquivos.sha256_arquivo(conf_arq) if conf_arq.is_file() else None,
                   'linkados_sha256': arquivos.sha256_caminho(pasta_job / ARQUIVO_LINKADOS),
                   'funcoes': 'derivacao' if funcoes else 'identidade'},
        'faces': [{'id': f['id'], 'sha256': f['sha256'], 'nome_ps': f['nome_ps'], 'nomes_ps': f['nomes_ps'],
                   'formato': f['formato'], 'indice': f['indice'], 'peso_declarado': f['peso_declarado'],
                   'colecao': f.get('colecao'), 'metricas': f.get('metricas')}
                  for f in faces if f['id'] in {p['id'] for p in pares.values() if p is not None}],
        'entradas': entradas, 'fora_da_peca': sorted(set(fora)), 'registros': registros,
    }
    return contrato, bloqueios, confirmar


def gravar(pasta_job, contrato):
    destino = Path(pasta_job) / 'render' / contrato['formato']['chave'] / 'contrato.json'
    contratos.gravar(destino, contrato, ESQUEMA)
    return destino
