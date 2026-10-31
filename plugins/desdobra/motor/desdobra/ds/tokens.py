# -*- coding: utf-8 -*-
"""Tokens do design system da peca: cor, tipografia e medidas (arquitetura-v1.md, 4.7 e 5.6).

Funcoes puras: recebem a estrutura/1 do documento, o laudo/1 e a conferencia de fontes (ou None) e devolvem
dicionarios. Quem le e grava os arquivos e desdobra.ds.

  - cor: cada descritor (preenchimento, overlay, traco, traco de forma, cor de texto) passa pelo conversor de
    desdobra.cor. Um token por cor distinta no espaco do documento, com a lista de usos (camada, descritor);
  - tipografia: um token por trecho com tinta. Familia, peso e metricas vem do arquivo de fonte (conferencia);
    corpo, entrelinha e tracking vem do PSD. O corpo efetivo usa a escala VERTICAL da matriz da camada (o
    predecessor usava a horizontal, arquitetura-v1.md 4.7);
  - medidas: caixa de tinta, rotacao, folga por lado ate a area de referencia (canvas ou prancheta), folga pela
    mascara e folga de resolucao do smart object embutido.
Nenhum nome de camada nem texto de peca entra nos tokens: a camada e citada pelo layer_id.
"""
import math

from desdobra import cor as mod_cor
from desdobra import limites

FONTE_TIPOGRAFIA = {'arquivo': 'arquitetura-v1.md', 'secao': '4.7'}
FONTE_METRICAS = {'arquivo': 'decisoes-v1.md', 'secao': '29/10, respostas às perguntas da arquitetura, 1'}
FONTE_FOLGA_RESOLUCAO = {'arquivo': 'pesquisa/corpus-testes.md', 'secao': '4, item 18'}
TIPOS_VETORIAIS = ('pdf', 'ai', 'eps', 'svg')
MILESIMOS_DE_EM = 1000.0  # numero-neutro: o tracking do Photoshop e dado em milesimos de em
SITUACAO_FONTES_NAO_CONFERIDAS = 'fontes_nao_conferidas'
METRICAS_CAMPOS = ('unidades_por_em', 'ascender', 'descender', 'cap_height', 'x_height', 'entrelinha_tipo')


# ------------------------------------------------------------------ cor
def _chave_cor(cor):
    v = cor.get('valores')
    if cor.get('modelo') == 'rgb' and v:
        return ('rgb', tuple(mod_cor.em_8_bits(v)))
    return (cor.get('modelo'), tuple(round(float(x), 4) if isinstance(x, (int, float)) else x for x in (v or ())))


def usos_de_cor(camadas):
    """(cor, uso) de cada descritor das camadas, na ordem das camadas."""
    for reg in camadas:
        lid = reg['layer_id']
        visivel = bool(reg.get('visivel_efetiva'))
        for d in reg.get('cores_descritores') or []:
            cor = mod_cor.cor_do_descritor(d.get('classe'), d.get('valores'))
            uso = {'camada': lid, 'descritor': d.get('descritor'), 'ativo': bool(d.get('ativo')), 'visivel': visivel}
            for k in ('efeito', 'bloco'):
                if d.get(k):
                    uso[k] = d[k]
            yield cor, uso
        tx = reg.get('texto') or {}
        for i, run in enumerate(tx.get('runs') or []):
            if not run.get('tem_tinta'):
                continue
            cor = mod_cor.cor_do_texto(run.get('cor_valores'))
            if cor is None:
                continue
            yield cor, {'camada': lid, 'descritor': 'texto', 'trecho': i, 'ativo': True, 'visivel': visivel}


def tokens_de_cor(camadas, conversor):
    """Lista de tokens de cor e o mapa (camada, descritor, trecho) -> id do token."""
    por_chave, tokens, mapa = {}, [], {}
    for cor, uso in usos_de_cor(camadas):
        chave = _chave_cor(cor)
        tok = por_chave.get(chave)
        if tok is None:
            tok = dict(conversor.token(cor), id='cor-%d' % (len(tokens) + 1), usos=[])
            por_chave[chave] = tok
            tokens.append(tok)
        tok['usos'].append(uso)
        mapa[(uso['camada'], uso['descritor'], uso.get('trecho'))] = tok['id']
    return tokens, mapa


# ------------------------------------------------------------------ tipografia
def _faces(conferencia):
    if not conferencia:
        return {}, {}, {}
    faces = {f['id']: f for f in conferencia.get('faces') or [] if f.get('id') is not None}
    por_ps = {}
    for f in faces.values():
        if f.get('nome_ps'):
            por_ps.setdefault(f['nome_ps'], f)
    camadas = {}
    for c in conferencia.get('camadas') or []:
        camadas.setdefault(c.get('layer_id'), []).append(c)
    return faces, por_ps, camadas


def _escala_vertical(texto):
    """Escala vertical da matriz da camada de texto: det / |coluna x| (a mesma decomposicao do leitor)."""
    m = texto.get('matriz')
    if m and len(m) >= 4:  # numero-neutro: a, b, c, d da matriz afim
        a, b, c, d = (float(x) for x in m[:4])  # numero-neutro: idem
        sx = math.hypot(a, b)
        if sx:
            return abs((a * d - b * c) / sx), math.degrees(math.atan2(b, a))
    dec = texto.get('decomposicao') or {}
    sy = dec.get('sy')
    return (abs(float(sy)) if sy is not None else None), dec.get('rotacao_graus')


def _metricas(face):
    if not face:
        return None
    m = face.get('metricas') or {}
    return {k: m.get(k) for k in METRICAS_CAMPOS}


def tokens_de_tipografia(camadas, conferencia, mapa_cor, arquivo_sha256):
    faces, por_ps, conf_camadas = _faces(conferencia)
    tokens = []
    for reg in camadas:
        tx = reg.get('texto')
        if not tx:
            continue
        lid = reg['layer_id']
        sy, rot = _escala_vertical(tx)
        conf = conf_camadas.get(lid) or []
        for i, run in enumerate(tx.get('runs') or []):
            if not run.get('tem_tinta'):
                continue
            ps = run.get('fonte_ps')
            face = por_ps.get(ps)
            conf_run = next((c for c in conf if c.get('nome_ps') == ps), conf[0] if len(conf) == 1 else None)
            if face is None and conf_run and conf_run.get('face_id') in faces:
                face = faces[conf_run['face_id']]
            corpo = run.get('corpo_espaco_texto')
            lead = run.get('entrelinha')
            tracking = run.get('tracking')
            if conferencia is None:
                situacao_fonte = SITUACAO_FONTES_NAO_CONFERIDAS
            elif conf_run is not None:
                situacao_fonte = conf_run.get('situacao')
            else:
                situacao_fonte = 'sem_registro_na_conferencia'
            tok = {
                'id': 'tipo-%d-%d' % (lid, i), 'camada': lid, 'trecho': i, 'visivel': bool(reg.get('visivel_efetiva')),
                'fonte_ps': ps,
                'familia': (face or {}).get('familia'), 'estilo': (face or {}).get('estilo'),
                'peso': (face or {}).get('peso_declarado'),
                'corpo_espaco_texto': corpo,
                'escala_vertical_matriz': round(sy, 6) if sy is not None else None,
                'corpo_efetivo_px': round(corpo * sy, 4) if corpo is not None and sy is not None else None,
                'escala_h_estilo': run.get('escala_h'), 'escala_v_estilo': run.get('escala_v'),
                'entrelinha': lead, 'autoleading': run.get('autoleading'),
                'entrelinha_efetiva_px': run.get('entrelinha_efetiva_px'),
                'tracking_milesimos_em': tracking,
                'tracking_em': round(tracking / MILESIMOS_DE_EM, 6) if tracking is not None else None,
                'caixa_alta': run.get('font_caps'), 'faux_bold': run.get('faux_bold'),
                'faux_italic': run.get('faux_italic'), 'baseline_shift': run.get('baseline_shift'),
                'antialiasing': run.get('antialiasing'), 'justificacao': tx.get('justificacao'),
                'rotacao_graus': round(rot, 4) if rot is not None else None,
                'cor': mapa_cor.get((lid, 'texto', i)),
                'origem': {'arquivo_sha256': arquivo_sha256, 'camada': lid, 'trecho': i, 'fonte': FONTE_TIPOGRAFIA},
                'metricas': _metricas(face),
                'metricas_origem': ({'face_id': face.get('id'), 'sha256': face.get('sha256'), 'nome_ps': face.get('nome_ps'),
                                     'formato': face.get('formato'), 'versao_name': face.get('versao_name'),
                                     'conferencia': 'fontes/conferencia.json', 'fonte': FONTE_METRICAS}
                                    if face else None),
                'situacao_fonte': situacao_fonte,
            }
            tokens.append(tok)
    return tokens


def resumo_tipografia(tokens):
    """Escala tipografica do KV: corpos efetivos distintos e a razao de cada um ao maior (so leitura)."""
    corpos = sorted({t['corpo_efetivo_px'] for t in tokens if t['visivel'] and t['corpo_efetivo_px']}, reverse=True)
    if not corpos:
        return {'corpos_efetivos_px': [], 'razoes_ao_maior': []}
    return {'corpos_efetivos_px': corpos, 'razoes_ao_maior': [round(c / corpos[0], 4) for c in corpos]}


# ------------------------------------------------------------------ medidas
def _area_ref(reg, documento):
    ref = [0, 0, documento['largura'], documento['altura']]
    pid = reg.get('prancheta_id')
    if pid is not None:
        for p in documento.get('pranchetas') or []:
            if p.get('layer_id') == pid:
                c = p['caixa']
                ref = [max(ref[0], c[0]), max(ref[1], c[1]), min(ref[2], c[2]), min(ref[3], c[3])]
    return ref


def _folga(caixa, ref):
    if not caixa:
        return None
    return {'esq': caixa[0] - ref[0], 'topo': caixa[1] - ref[1], 'dir': ref[2] - caixa[2], 'base': ref[3] - caixa[3]}


def _folga_mascara(reg):
    mk = reg.get('mascara') or {}
    if not mk.get('raster') or mk.get('desativada') or not mk.get('caixa'):
        if mk.get('vetorial') and not mk.get('vetorial_desativada'):
            return {'tipo': 'vetorial', 'por_lado': None, 'motivo': 'máscara vetorial: a caixa não fica gravada'}
        return None
    m, c = mk['caixa'], reg.get('caixa') or [0, 0, 0, 0]
    # pixels da camada que a mascara esconde em cada lado: folga para reenquadrar sem faltar imagem
    return {'tipo': 'raster', 'caixa_mascara': m, 'cor_fundo': mk.get('cor_fundo'),
            'por_lado': {'esq': m[0] - c[0], 'topo': m[1] - c[1], 'dir': c[2] - m[2], 'base': c[3] - m[3]}}


def _folga_resolucao(so, lim_ampl):
    if not so or not so.get('embutido'):
        return None
    esc = so.get('escala_sobre_original') or {}
    sx, sy = esc.get('sx'), esc.get('sy')
    out = {'tipo_detectado': so.get('tipo_detectado'), 'vetorial': so.get('tipo_detectado') in TIPOS_VETORIAIS,
           'escala_sobre_original': esc or None, 'ampliacao': None, 'folga': None, 'aviso': None,
           'fonte': FONTE_FOLGA_RESOLUCAO, 'limite': lim_ampl.citacao()}
    if sx is None or sy is None:
        out['motivo'] = 'sem as dimensões do original'
        return out
    ampl = max(float(sx), float(sy))
    out['ampliacao'] = round(ampl, 6)
    out['folga'] = round(1.0 / ampl, 6) if ampl else None
    if not out['vetorial'] and lim_ampl.valor is not None and ampl > lim_ampl.valor:
        out['aviso'] = 'o KV já amplia este raster acima do limite registrado'
    return out


def medidas(camadas, laudo_por_id, documento):
    lim_ampl = limites.obter('ds.ampliacao_raster_max')
    out = []
    for reg in camadas:
        lid = reg['layer_id']
        cam = laudo_por_id.get(lid) or {}
        tipo = cam.get('tipo')
        if tipo in ('grupo', 'prancheta') or not reg.get('visivel_efetiva'):
            continue
        ref = _area_ref(reg, documento)
        rot = None
        tx = reg.get('texto')
        so = reg.get('smart_object') or {}
        if tx:
            _sy, rot = _escala_vertical(tx)
        elif so.get('quad_colocado'):
            rot = so['quad_colocado'].get('rotacao_graus')
        out.append({'camada': lid, 'tipo': tipo, 'caixa': reg.get('caixa'), 'caixa_tinta': reg.get('caixa_tinta'),
                    'area_ref': ref, 'rotacao_graus': round(rot, 4) if rot is not None else None,
                    'folga': _folga(reg.get('caixa_tinta'), ref), 'folga_mascara': _folga_mascara(reg),
                    'folga_resolucao': _folga_resolucao(so, lim_ampl)})
    return out
