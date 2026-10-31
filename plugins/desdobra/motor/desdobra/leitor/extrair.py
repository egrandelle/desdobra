# -*- coding: utf-8 -*-
"""Extracao dos fatos de cada camada, portada da sonda da pesquisa (sonda do corpus com psd-tools 1.26.0).

So fatos lidos e medidos: o julgamento (lida, degradada, bloqueante) e do laudo. Roda so no processo filho.
Diferencas para a sonda:
  - smart object: tipo, nome, tamanho e sha256 vem do indice proprio (desdobra.leitor.indice), porque o
    documento e aberto sem os blocos lnk*; do linkado so nome, tamanho e data, nunca o caminho;
  - medidas para falso positivo (largura do traco vetorial, desvio da malha de deformacao, residuo do
    paralelogramo, warp de texto sem efeito) ficam em medidas_regras;
  - a regra D9 foi aposentada: as opcoes de mesclagem clbl/infx e os efeitos legados lrFX viram alertas.
"""
import collections
import io
import math
import re
import unicodedata

from PIL import Image, ImageCms
from psd_tools.api.layers import AdjustmentLayer, Artboard, FillLayer, GroupMixin
from psd_tools.constants import Resource, Tag

from desdobra.laudo import efeitos_1260
from desdobra.leitor import adaptador

JUST_PADRAO_AUTO = 1.2  # numero-neutro: entrelinha automatica padrao do Photoshop (120% do corpo)
_RE_LARG = re.compile(rb'/Width\s+(\d+)')
_RE_ALT = re.compile(rb'/Height\s+(\d+)')
_RE_IMG = re.compile(rb'/Subtype\s*/Image')
_RE_MEDIA = re.compile(rb'/MediaBox\s*\[\s*([-0-9.]+)\s+([-0-9.]+)\s+([-0-9.]+)\s+([-0-9.]+)\s*\]')
JANELA_PDF = 2048  # numero-neutro: janela de busca de /Width e /Height em volta de /Subtype /Image
BLOCO_PDF = 1 << 20  # numero-neutro: bloco de varredura do PDF embutido, sem efeito no resultado


def s(v):
    if isinstance(v, bytes):
        return v.decode('latin-1')
    return v


def plain(v, prof=0):
    """Descritores e engine data do psd-tools em tipos JSON."""
    if prof > 14:  # numero-neutro: limite de recursao da conversao para JSON
        return '...'
    v = adaptador.enum_texto(v)
    if isinstance(v, (bool, int, str)) or v is None:
        return v
    if isinstance(v, float):
        return v if math.isfinite(v) else str(v)
    if isinstance(v, bytes):
        return v.decode('latin-1')
    if hasattr(v, 'items') and callable(v.items):
        try:
            return {str(s(k)): plain(x, prof + 1) for k, x in v.items()}
        except Exception:
            pass
    if isinstance(v, (list, tuple)):
        return [plain(x, prof + 1) for x in v]
    if hasattr(v, 'value'):
        return plain(v.value, prof + 1)
    try:
        return [plain(x, prof + 1) for x in v]
    except Exception:
        return str(v)


def num(v, nd=4):
    try:
        f = float(v)
        return round(f, nd) if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def desc_get(d, *chaves, padrao=None):
    if d is None:
        return padrao
    for k in chaves:
        try:
            if k in d:
                return d[k]
        except Exception:
            pass
    return padrao


def interseccao(a, b):
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    return [x0, y0, x1, y1] if x1 > x0 and y1 > y0 else None


def area(b):
    return 0 if not b else max(0, b[2] - b[0]) * max(0, b[3] - b[1])


def eh_controle(ch):
    return unicodedata.category(ch) in ('Cc', 'Zl', 'Zp')


def tem_tinta(ch):
    """Caractere que deixa marca: nem controle nem espaco."""
    return not eh_controle(ch) and not ch.isspace()


# ------------------------------------------------------------------ documento
def info_icc(psd):
    import hashlib
    out = {'presente': Resource.ICC_PROFILE in psd.image_resources, 'descricao': None, 'sha256': None, 'bytes': None}
    if out['presente']:
        icc = psd.image_resources.get_data(Resource.ICC_PROFILE)
        out['bytes'] = len(icc)
        out['sha256'] = hashlib.sha256(icc).hexdigest()
        try:
            out['descricao'] = ImageCms.getProfileDescription(ImageCms.ImageCmsProfile(io.BytesIO(icc))).strip()
        except Exception:
            out['descricao'] = None
    return out


def dados_icc(psd):
    """Bytes do perfil ICC do documento (recurso 1039), ou None. O filho grava em documento.icc para o modulo de
    cor (desdobra.cor), que converte os descritores sem abrir o PSD no processo principal."""
    if Resource.ICC_PROFILE not in psd.image_resources:
        return None
    dados = psd.image_resources.get_data(Resource.ICC_PROFILE)
    return bytes(dados) if dados else None


def _cor_bruta(d):
    """Descritor de cor do Photoshop como fato: classe (RGBC, HSBC, LbCl, CMYC, Grsc, BkCl) e valores, sem
    conversao. A conversao pelo perfil do documento e do desdobra.cor."""
    if d is None or not hasattr(d, 'items'):
        return None
    cls = getattr(d, 'classID', None)
    cls = getattr(cls, 'value', cls)
    valores = {}
    for k, v in d.items():
        k = getattr(k, 'value', k)
        valores[str(s(k)).strip()] = plain(v)
    return {'classe': str(s(cls)).strip() if cls is not None else None, 'valores': valores}


def descritores_cor(L, efeitos):
    """Cores de preenchimento (SoCo, vscg), traco de forma (vstk), overlay e traco de efeito, no espaco do
    documento. A cor do texto fica nos trechos (cor_valores)."""
    out = []

    def juntar(descritor, d, ativo, **extra):
        cor = _cor_bruta(d)
        if cor is not None:
            out.append(dict(cor, descritor=descritor, ativo=bool(ativo), **extra))

    try:
        if L.kind == 'solidcolorfill':
            juntar('preenchimento', L.data, True, bloco='SoCo')
        if Tag.VECTOR_STROKE_CONTENT_DATA in L.tagged_blocks:
            v = L.tagged_blocks.get_data(Tag.VECTOR_STROKE_CONTENT_DATA)
            vstk = L.tagged_blocks.get_data(Tag.VECTOR_STROKE_DATA) if Tag.VECTOR_STROKE_DATA in L.tagged_blocks else None
            preenche = plain(desc_get(vstk, b'fillEnabled')) if vstk is not None else None
            juntar('preenchimento', desc_get(v, b'Clr '), preenche is not False, bloco='vscg')
        if Tag.VECTOR_STROKE_DATA in L.tagged_blocks:
            vstk = L.tagged_blocks.get_data(Tag.VECTOR_STROKE_DATA)
            conteudo = desc_get(vstk, b'strokeStyleContent')
            juntar('traco_forma', desc_get(conteudo, b'Clr '), bool(plain(desc_get(vstk, b'strokeEnabled'))),
                   bloco='vstk', largura=num(plain(desc_get(vstk, b'strokeStyleLineWidth')), 4))
    except Exception:
        pass
    try:
        fx = L.effects if efeitos else None
        for i, e in enumerate(fx or []):
            tipo = type(e).__name__
            if tipo not in ('ColorOverlay', 'Stroke'):
                continue
            juntar('overlay' if tipo == 'ColorOverlay' else 'traco', getattr(e, 'color', None),
                   bool(fx.enabled and e.enabled), efeito=tipo, indice_efeito=i)
    except Exception:
        pass
    return out


def info_version(psd):
    vi = psd.image_resources.get_data(Resource.VERSION_INFO)
    if not vi:
        return {'writer': None, 'reader': None, 'file_version': None, 'has_composite': None}
    return {'has_composite': bool(vi.has_composite), 'writer': vi.writer, 'reader': vi.reader,
            'file_version': vi.file_version}


def info_dpi(psd):
    ri = psd.image_resources.get_data(Resource.RESOLUTION_INFO)
    if not ri:
        return None
    un = {1: 'ppi', 2: 'ppcm'}  # numero-neutro: codigos de unidade do recurso de resolucao
    return {'horizontal': round(ri.horizontal / 65536.0, 4), 'vertical': round(ri.vertical / 65536.0, 4),  # numero-neutro: ponto fixo 16.16
            'unidade_h': un.get(ri.horizontal_unit, ri.horizontal_unit),
            'unidade_v': un.get(ri.vertical_unit, ri.vertical_unit)}


def dpi_em_ppi(dpi):
    if not dpi:
        return 72.0  # numero-neutro: resolucao padrao do formato quando o recurso falta
    h = dpi['horizontal']
    return h * 2.54 if dpi['unidade_h'] == 'ppcm' else h  # numero-neutro: cm por polegada


def info_layer_comps(psd, camadas):
    """Recurso 1065 e as entradas cmls de cada camada (melhor esforco, como na sonda)."""
    if Resource.LAYER_COMPS not in psd.image_resources:
        return []
    d = psd.image_resources.get_data(Resource.LAYER_COMPS)
    comps = []
    for it in (desc_get(d, b'list', padrao=[]) or []):
        comps.append({'comp_id': plain(desc_get(it, b'compID')), 'nome': plain(desc_get(it, b'Nm  ')),
                      'camadas_visiveis': [], 'camadas_ocultas': [], 'n_camadas_sem_registro': 0})
    por_id = {c['comp_id']: c for c in comps}
    for L in camadas:
        regs = {}
        try:
            md = L.tagged_blocks.get_data(Tag.METADATA_SETTING)
            for m in (md or []):
                if m.key == b'cmls' and hasattr(m.data, 'items'):
                    for ls in (desc_get(m.data, b'layerSettings', padrao=[]) or []):
                        enab = desc_get(ls, b'enab')
                        for cid in (plain(desc_get(ls, b'compList', padrao=[])) or []):
                            if enab is not None:
                                regs[cid] = bool(plain(enab))
        except Exception:
            pass
        for cid, c in por_id.items():
            if cid in regs:
                (c['camadas_visiveis'] if regs[cid] else c['camadas_ocultas']).append(L.layer_id)
            else:
                c['n_camadas_sem_registro'] += 1
    return comps


def documento(psd, camadas, origem_cab):
    vi = info_version(psd)
    return {
        'largura': psd.width, 'altura': psd.height, 'formato': origem_cab['formato'], 'versao': origem_cab['versao'],
        'modo': psd.color_mode.name, 'bits': psd.depth, 'canais': psd.channels, 'icc': info_icc(psd),
        'gravado_por': vi, 'tem_previa': bool(psd.has_preview()),
        'tem_previa_nota': None if vi.get('writer') else 'sem VERSION_INFO: has_preview() responde verdadeiro por padrão',
        'dpi': info_dpi(psd),
        'pranchetas': [{'layer_id': L.layer_id, 'nome': L.name, 'caixa': list(L.bbox), 'visivel_propria': bool(L.visible)}
                       for L in camadas if isinstance(L, Artboard)],
        'layer_comps': info_layer_comps(psd, camadas),
        'n_camadas': sum(1 for L in camadas if not isinstance(L, GroupMixin)),
        'n_grupos': sum(1 for L in camadas if isinstance(L, GroupMixin)),
    }


# ------------------------------------------------------------------ camada
def caminho_ids(L, psd):
    ids = []
    p = L.parent
    while p is not None and p is not psd:
        ids.append(p.layer_id)
        p = p.parent
    return ids[::-1]


def prancheta_de(L, psd):
    p = L.parent
    while p is not None and p is not psd:
        if isinstance(p, Artboard):
            return p
        p = p.parent
    return None


def info_mascara(L):
    out = {'raster': bool(L.has_mask()), 'desativada': None, 'caixa': None, 'vetorial': bool(L.has_vector_mask())}
    if L.has_mask():
        mk = L.mask
        out['desativada'] = bool(mk.disabled)
        out['caixa'] = list(mk.bbox)
        out['raster_com_dados'] = mk.width > 0 and mk.height > 0
        out['real'] = bool(mk.has_real())
        out['cor_fundo'] = mk.background_color
        p = mk.parameters
        if p is not None:
            out['densidade_usuario'] = p.user_mask_density
            out['feather_usuario'] = p.user_mask_feather
            out['densidade_vetorial'] = p.vector_mask_density
            out['feather_vetorial'] = p.vector_mask_feather
    if L.has_vector_mask():
        vm = L.vector_mask
        out['vetorial_desativada'] = bool(vm.disabled)
        out['vetorial_invertida'] = bool(getattr(vm, 'inverted', False))
        try:
            out['vetorial_n_caminhos'] = len(vm.paths)
        except Exception:
            pass
    return out


def info_traco_forma(L):
    """Traco vetorial da forma (vstk): ativo e largura. Largura 0 nao desenha nada."""
    try:
        st = L.stroke if L.has_vector_mask() else None
    except Exception:
        st = None
    if st is None:
        return None
    try:
        largura = num(st.line_width, 4)
    except Exception:
        largura = None
    return {'ativo': bool(st.enabled), 'largura': largura}


def info_efeitos(L, pacotes):
    """Efeitos de camada com a marca desenhado_pelo_render (lista conferida na 1.26.0)."""
    tem_obj = any(t in L.tagged_blocks for t in (Tag.OBJECT_BASED_EFFECTS_LAYER_INFO,
                                                   Tag.OBJECT_BASED_EFFECTS_LAYER_INFO_V0,
                                                   Tag.OBJECT_BASED_EFFECTS_LAYER_INFO_V1))
    legado = Tag.EFFECTS_LAYER in L.tagged_blocks and not tem_obj
    lista = []
    if not tem_obj:
        return lista, legado, None
    fx = L.effects
    master = bool(fx.enabled)
    for e in fx:
        tipo = type(e).__name__
        desenhado, falta = efeitos_1260.efeito_desenhado(tipo, pacotes)
        item = {'tipo': tipo, 'ativo': bool(master and e.enabled), 'desenhado_pelo_render': desenhado,
                'requer_pacote_ausente': falta, 'medidas': {}}
        for att in ('size', 'distance', 'angle', 'opacity', 'choke'):
            try:
                v = getattr(e, att)
                if v is not None and not callable(v):
                    item['medidas'][att] = num(v, 3)
            except Exception:
                pass
        try:
            bmx = e.blend_mode
            bmx = getattr(bmx, 'enum', None) or getattr(bmx, 'name', None) or bmx
            item['medidas']['blend'] = bmx.decode('latin-1') if isinstance(bmx, bytes) else str(bmx)
        except Exception:
            pass
        lista.append(item)
    return lista, legado, master


def decompor(t):
    a, b, c, d = t[0], t[1], t[2], t[3]
    sx = math.hypot(a, b)
    if sx == 0:
        return {'sx': 0.0, 'sy': 0.0, 'rotacao_graus': 0.0, 'cisalhamento': 0.0}
    rot = math.degrees(math.atan2(b, a))
    det = a * d - b * c
    sy = det / sx
    k = (a * c + b * d) / (sx * sx)
    return {'sx': round(sx, 6), 'sy': round(sy, 6), 'rotacao_graus': round(rot, 4), 'cisalhamento': round(k, 6)}


def info_texto(L):
    """Trechos de estilo (runs), paragrafos, caixa, matriz e warp de uma camada de texto."""
    ts = L.typesetting
    ed = L.engine_dict
    t = list(L.transform)
    dec = decompor(t)
    sy = abs(dec['sy'])
    paragrafos = []
    for p in ts.paragraphs:
        st = p.style
        paragrafos.append({'inicio': p.start, 'fim': p.end, 'justificacao': st.justification.name,
                           'auto_leading_fator': num(st.auto_leading, 4), 'recuo_primeira_linha': num(st.first_line_indent, 3),
                           'recuo_inicio': num(st.start_indent, 3), 'recuo_fim': num(st.end_indent, 3),
                           'espaco_antes': num(st.space_before, 3), 'espaco_depois': num(st.space_after, 3)})

    def fator_auto(pos):
        for p in paragrafos:
            if p['inicio'] <= pos < p['fim']:
                return p['auto_leading_fator'] or JUST_PADRAO_AUTO
        return (paragrafos[-1]['auto_leading_fator'] if paragrafos else None) or JUST_PADRAO_AUTO

    runs = []
    for r in ts.runs:
        stl = r.style
        raw_ak = adaptador.estilo_cru(stl, 'AutoKerning')
        fc = stl.fill_color
        cor_hex = None
        if fc and len(fc) == 4:  # numero-neutro: cor ARGB tem 4 componentes
            _a, r_, g_, b_ = fc
            cor_hex = '#%02X%02X%02X' % tuple(max(0, min(255, int(round(x * 255)))) for x in (r_, g_, b_))  # numero-neutro: escala de cor de 8 bits
        corpo = stl.font_size
        autolead = stl.auto_leading
        lead = stl.leading
        lead_ef = (fator_auto(r.start) * corpo if autolead else lead)
        runs.append({
            'inicio': r.start, 'fim': r.end, 'texto': r.text,
            'tem_caractere_visivel': any(not eh_controle(ch) for ch in r.text),
            'tem_tinta': any(tem_tinta(ch) for ch in r.text),
            'fonte_ps': stl.font_name, 'corpo_espaco_texto': num(corpo, 4), 'corpo_efetivo': num((corpo or 0) * sy, 4),
            'tracking': num(stl.tracking, 4), 'entrelinha': num(lead, 4), 'autoleading': bool(autolead),
            'entrelinha_efetiva_px': num((lead_ef or 0) * sy, 4),
            'cor_hex': cor_hex, 'cor_valores': [num(x, 4) for x in fc] if fc else None,
            'font_caps': stl.font_caps.name, 'faux_bold': bool(stl.faux_bold), 'faux_italic': bool(stl.faux_italic),
            'baseline_shift': num(stl.baseline_shift, 4), 'escala_h': num(stl.horizontal_scale, 4),
            'escala_v': num(stl.vertical_scale, 4),
            'autokerning': bool(raw_ak) if raw_ak is not None else True,
            'kerning': num(stl.kerning, 4), 'sublinhado': bool(stl.underline), 'tachado': bool(stl.strikethrough),
            'ligaduras': bool(stl.ligatures), 'traco_texto': bool(stl.stroke_flag),
            'antialiasing': None,
        })
    tipo_caixa, box, ponto_base = None, None, None
    try:
        ch = ed['Rendered']['Shapes']['Children']
        if len(ch) >= 1:
            ck = ch[0]['Cookie']['Photoshop']
            st_ = int(plain(ck.get('ShapeType')))
            tipo_caixa = {0: 'ponto', 1: 'paragrafo'}.get(st_, str(st_))  # numero-neutro: codigos de ShapeType
            bb = ck.get('BoxBounds')
            box = [num(x, 4) for x in plain(bb)] if bb is not None else None
            pb = ck.get('PointBase')
            ponto_base = [num(x, 4) for x in plain(pb)] if pb is not None else None
        if len(ch) > 1:
            tipo_caixa = 'multiplas_formas(%d)' % len(ch)
    except Exception:
        pass
    td = adaptador.dados_texto(L).text_data
    w = L.warp
    warp = None
    if w is not None:
        warp = {'estilo': plain(desc_get(w, b'warpStyle')), 'valor': num(plain(desc_get(w, b'warpValue')), 4),
                'perspectiva': num(plain(desc_get(w, b'warpPerspective')), 4),
                'perspectiva_outra': num(plain(desc_get(w, b'warpPerspectiveOther')), 4),
                'rotacao': plain(desc_get(w, b'warpRotate'))}
    aa = plain(desc_get(td, b'AntA'))
    for r in runs:
        r['antialiasing'] = aa if isinstance(aa, str) else None
    ornt = plain(desc_get(td, b'Ornt'))
    nao_unif = abs(dec['sx'] / dec['sy'] - 1.0) * 100.0 if dec['sy'] else None  # numero-neutro: porcentagem
    caixa_tysh = None
    try:
        dt = adaptador.dados_texto(L)
        caixa_tysh = {'left': dt.left, 'top': dt.top, 'right': dt.right, 'bottom': dt.bottom,
                      'bounds': plain(desc_get(td, b'bounds')), 'bounding_box': plain(desc_get(td, b'boundingBox'))}
    except Exception:
        pass
    return {
        'conteudo': L.text, 'runs': runs, 'paragrafos': paragrafos,
        'tipo_caixa': tipo_caixa, 'box_bounds': box, 'ponto_base': ponto_base, 'caixa_tysh': caixa_tysh,
        'matriz': [round(x, 6) for x in t], 'decomposicao': dec, 'nao_uniforme_pct': num(nao_unif, 3),
        'warp': warp,
        'justificacao': paragrafos[0]['justificacao'] if paragrafos else None,
        'orientacao': {'Hrzn': 'horizontal', 'Vrtc': 'vertical'}.get(ornt, ornt),
        'direcao_escrita': ts.writing_direction.name if ts.writing_direction is not None else None,
        'fontes_ps': sorted({r['fonte_ps'] for r in runs if r['fonte_ps']}),
    }


# ------------------------------------------------------------------ smart object
def quad_info(tb):
    if not tb or len(tb) != 8:  # numero-neutro: o quadrilatero tem 4 cantos (8 coordenadas)
        return None
    x1, y1, x2, y2, x3, y3, x4, y4 = [float(v) for v in tb]
    w = math.hypot(x2 - x1, y2 - y1)
    h = math.hypot(x4 - x1, y4 - y1)
    residuo = max(abs((x1 + x3) - (x2 + x4)), abs((y1 + y3) - (y2 + y4)))
    dot = (x2 - x1) * (x4 - x1) + (y2 - y1) * (y4 - y1)
    return {'largura': round(w, 4), 'altura': round(h, 4), 'rotacao_graus': round(math.degrees(math.atan2(y2 - y1, x2 - x1)), 4),
            'residuo_paralelogramo_px': residuo, 'cosseno_angulo': (dot / (w * h)) if w * h else 0.0}


def desvio_malha(warp):
    """Desvio maximo, em pixels da origem, entre a malha customEnvelopeWarp e a grade identidade dos bounds."""
    import numpy as np
    if not isinstance(warp, dict) or 'customEnvelopeWarp' not in warp:
        return None
    try:
        mp = warp['customEnvelopeWarp']['meshPoints']
        hz = vt = None
        itens = mp if isinstance(mp, list) else [mp]
        for it in itens:
            if isinstance(it, dict):
                for k, v in it.items():
                    if k.startswith('Hrzn'):
                        hz = v
                    if k.startswith('Vrtc'):
                        vt = v
        b = warp['bounds']
        top = b.get('Top ', b.get('Top'))
        left, btm, rght = b['Left'], b['Btom'], b['Rght']
        nu, nv = int(warp.get('uOrder', 4)), int(warp.get('vOrder', 4))  # numero-neutro: grade padrao 4 x 4 do Photoshop
        hz = np.array(hz, float).reshape(nv, nu)
        vt = np.array(vt, float).reshape(nv, nu)
        gx = left + (rght - left) * np.arange(nu) / (nu - 1)
        gy = top + (btm - top) * np.arange(nv) / (nv - 1)
        gxx, gyy = np.meshgrid(gx, gy)
        d = np.hypot(hz - gxx, vt - gyy)
        return float(d.max())
    except Exception:
        return None


def varrer_pdf(f, inicio, tamanho):
    """Varredura dos bytes de um PDF embutido: MediaBox e dimensoes das imagens raster (/Subtype /Image).
    Medida aproximada, sem interpretar o PDF (o pypdfium2 entra no M3)."""
    imagens, media, vistos = [], None, set()
    pos, fim = inicio, inicio + tamanho
    anterior = b''
    while pos < fim:
        f.seek(pos)
        bloco = f.read(min(BLOCO_PDF, fim - pos))
        if not bloco:
            break
        dados = anterior + bloco
        base = pos - len(anterior)
        if media is None:
            m = _RE_MEDIA.search(dados)
            if m:
                media = [num(x, 3) for x in m.groups()]
        for m in _RE_IMG.finditer(dados):
            absoluto = base + m.start()
            if absoluto in vistos:
                continue
            vistos.add(absoluto)
            janela = dados[max(0, m.start() - JANELA_PDF):m.end() + JANELA_PDF]
            mw, mh = _RE_LARG.search(janela), _RE_ALT.search(janela)
            if mw and mh:
                imagens.append([int(mw.group(1)), int(mh.group(1))])
        anterior = dados[-JANELA_PDF:]
        pos += len(bloco)
    out = {'formato': 'PDF', 'vetorial': True, 'unidade': 'pt', 'fonte': 'varredura dos bytes (aproximada)',
           'n_imagens_raster': len(imagens)}
    if media:
        out['largura'] = round(media[2] - media[0], 3)
        out['altura'] = round(media[3] - media[1], 3)
    if imagens:
        maior = max(imagens, key=lambda x: x[0] * x[1])
        out['maior_imagem_px'] = maior
        out['imagens_px'] = imagens
    return out


class _Trecho(io.RawIOBase):
    """Trecho somente leitura de um arquivo, para o PIL ler so o cabecalho de uma imagem embutida."""

    def __init__(self, f, inicio, tamanho):
        super().__init__()
        self._f, self._ini, self._n, self._pos = f, inicio, tamanho, 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self._pos

    def seek(self, d, de=io.SEEK_SET):
        self._pos = {io.SEEK_SET: d, io.SEEK_CUR: self._pos + d, io.SEEK_END: self._n + d}[de]
        return self._pos

    def readinto(self, buf):
        alvo = memoryview(buf).cast('B')
        quanto = max(0, min(len(alvo), self._n - self._pos))
        if not quanto:
            return 0
        self._f.seek(self._ini + self._pos)
        pedaco = self._f.read(quanto)
        alvo[:len(pedaco)] = pedaco
        self._pos += len(pedaco)
        return len(pedaco)


def dims_embutido(f, reg):
    tipo = reg.get('tipo_detectado')
    if tipo in ('psd', 'psb'):
        c = reg.get('cabecalho_psd') or {}
        if 'largura' not in c:
            return None
        return {'largura': c['largura'], 'altura': c['altura'], 'unidade': 'px', 'vetorial': False,
                'fonte': 'cabeçalho PSD/PSB (26 bytes)', 'formato': c['formato'], 'canais': c['canais'], 'bits': c['bits'],
                'modo': c['modo']}
    if tipo == 'pdf':
        return varrer_pdf(f, reg['deslocamento_dados'], reg['tamanho_dados'])
    if tipo == 'eps':
        return {'vetorial': True, 'formato': 'EPS', 'fonte': None}
    if tipo in ('xml', 'svg'):
        return {'vetorial': True, 'formato': 'SVG', 'fonte': None}
    with Image.open(io.BufferedReader(_Trecho(f, reg['deslocamento_dados'], reg['tamanho_dados']))) as im:
        return {'largura': im.width, 'altura': im.height, 'unidade': 'px', 'vetorial': False, 'fonte': 'PIL (cabeçalho)',
                'formato': im.format, 'modo': im.mode}


def info_so(L, ppi_doc, indice_por_uid, f):
    cfg_bloco, placed = adaptador.registro_smart(L)
    cfg = cfg_bloco.data if cfg_bloco is not None else None
    out = {'unique_id': None, 'embutido': False, 'tipo': 'sem_registro', 'filetype': None, 'tipo_detectado': None,
           'nome': None, 'bytes': None, 'sha256': None, 'dims': None, 'linkado': None, 'transformacao': None,
           'warp_ou_nao_afim': None, 'medidas': {}}
    try:
        out['unique_id'] = L.smart_object.unique_id
    except Exception:
        out['unique_id'] = ''
        return out
    reg = indice_por_uid.get(out['unique_id'])
    if reg is not None:
        out['tipo'] = {'liFD': 'embutido', 'liFE': 'linkado', 'liFA': 'alias'}.get(reg['tipo_registro'], reg['tipo_registro'])
        out['embutido'] = reg['embutido']
        out['filetype'] = reg['filetype']
        out['tipo_detectado'] = reg['tipo_detectado']
        out['nome'] = reg['nome']
        out['bytes'] = reg['tamanho_dados'] if reg['embutido'] else (reg.get('linkado') or {}).get('tamanho')
        out['sha256'] = reg['sha256']
        out['linkado'] = reg.get('linkado')
        if reg['embutido']:
            try:
                out['dims'] = dims_embutido(f, reg)
            except Exception as e:
                out['dims'] = None
                out['dims_erro'] = type(e).__name__
    tb = None
    try:
        tb = L.smart_object.transform_box
    except Exception:
        pass
    if tb is None and cfg is not None:
        tb = plain(desc_get(cfg, b'Trnf'))
    out['transformacao'] = [num(v, 4) for v in tb] if tb else None
    q = quad_info(tb)
    out['quad_colocado'] = q
    sz = plain(desc_get(cfg, b'Sz  ')) if cfg is not None else None
    out['tamanho_colocado'] = sz
    out['resolucao_colocada'] = num(plain(desc_get(cfg, b'Rslt')), 4) if cfg is not None else None
    dm = out.get('dims') or {}
    if q and dm.get('largura') and dm.get('altura'):
        fator = (ppi_doc / 72.0) if dm.get('unidade') == 'pt' else 1.0  # numero-neutro: pontos por polegada
        out['escala_sobre_original'] = {'sx': round(q['largura'] / (float(dm['largura']) * fator), 6),
                                        'sy': round(q['altura'] / (float(dm['altura']) * fator), 6)}
    warp = plain(desc_get(cfg, b'warp')) if cfg is not None else None
    estilo = warp.get('warpStyle') if isinstance(warp, dict) else None
    naf = plain(desc_get(cfg, b'nonAffineTransform')) if cfg is not None else None
    trnf = plain(desc_get(cfg, b'Trnf')) if cfg is not None else None
    dif_naf = None
    if naf and trnf:
        try:
            dif_naf = max(abs(float(a) - float(b)) for a, b in zip(naf, trnf))
        except (TypeError, ValueError):
            dif_naf = None
    out['medidas'] = {'warp_estilo': estilo,
                      'warp_valores': [num(warp.get(k), 4) for k in ('warpValue', 'warpPerspective', 'warpPerspectiveOther')]
                      if isinstance(warp, dict) else None,
                      'malha_custom': bool(isinstance(warp, dict) and 'customEnvelopeWarp' in warp),
                      'malha_desvio_max_px': desvio_malha(warp),
                      'nao_afim_diferenca_max_px': dif_naf,
                      'residuo_paralelogramo_px': q['residuo_paralelogramo_px'] if q else None}
    try:
        tipo_pl = getattr(getattr(placed, 'layer_type', None), 'name', None) if placed is not None else None
        out['tipo_colocado'] = tipo_pl
    except Exception:
        pass
    if cfg is not None:
        ffx = desc_get(cfg, b'filterFX')
        if ffx is not None:
            lst = desc_get(ffx, b'filterFXList', padrao=[]) or []
            out['filtros_inteligentes'] = [{'nome': plain(desc_get(x, b'Nm  ')), 'ativo': plain(desc_get(x, b'enab'))} for x in lst]
        out['pagina'] = plain(desc_get(cfg, b'PgNm'))
    return out


# ------------------------------------------------------------------ registro completo de uma camada (sem pixels)
def metadados(L, i, psd, base_de, contexto):
    W, H = psd.width, psd.height
    bm = L.blend_mode
    reg = {'layer_id': L.layer_id, 'indice': i, 'nome': L.name, 'kind': L.kind, 'classe': type(L).__name__}
    ids = caminho_ids(L, psd)
    reg.update({'pai_id': ids[-1] if ids else None, 'caminho_ids': ids,
                'visivel_propria': bool(L.visible), 'visivel_efetiva': bool(L.is_visible()),
                'opacidade': int(L.opacity), 'preenchimento': int(L.fill_opacity),
                'blend': getattr(bm, 'name', str(bm)), 'clipping': bool(L.clipping),
                'base_do_clip': (base_de[id(L)].layer_id if id(L) in base_de else None) if L.clipping else None,
                'caixa': [int(x) for x in L.bbox]})
    art = prancheta_de(L, psd)
    reg['prancheta_id'] = art.layer_id if art is not None else None
    reg['mascara'] = info_mascara(L)
    alertas = []
    try:
        lst, legado, master = info_efeitos(L, contexto['pacotes'])
        reg['efeitos'] = lst
        reg['efeitos_master'] = master
        if legado:
            alertas.append('efeitos legados (lrFX) sem lfx2: o psd-tools não lê')
    except Exception as e:
        reg['efeitos'] = []
        reg['efeitos_ilegiveis'] = type(e).__name__
    try:
        clbl = L.tagged_blocks.get_data(Tag.BLEND_CLIPPING_ELEMENTS) if Tag.BLEND_CLIPPING_ELEMENTS in L.tagged_blocks else None
        infx = L.tagged_blocks.get_data(Tag.BLEND_INTERIOR_ELEMENTS) if Tag.BLEND_INTERIOR_ELEMENTS in L.tagged_blocks else None
        if clbl is not None and not bool(clbl):
            alertas.append('opção de mesclagem clbl (camadas clipadas como grupo) desligada: o psd-tools ignora')
        if infx is not None and bool(infx):
            alertas.append('opção de mesclagem infx (efeitos internos como grupo) ligada: o psd-tools ignora')
    except Exception:
        pass
    if isinstance(L, AdjustmentLayer):
        entra, motivo = efeitos_1260.ajuste_no_composto(L.kind, psd.color_mode.name, contexto['pacotes'])
        reg['ajuste'] = {'tipo': L.kind, 'entra_no_composto': entra, 'motivo': motivo}
    else:
        reg['ajuste'] = None
    reg['preenchimento_tipo'] = L.kind if isinstance(L, FillLayer) else None
    reg['cores_descritores'] = descritores_cor(L, bool(reg.get('efeitos')))
    reg['smart_object'] = None
    if L.kind == 'smartobject':
        try:
            reg['smart_object'] = info_so(L, contexto['ppi'], contexto['indice_por_uid'], contexto['arquivo'])
        except Exception as e:
            reg['smart_object'] = {'unique_id': '', 'embutido': False, 'tipo': 'erro', 'erro': type(e).__name__}
            contexto['erros'].append({'etapa': 'smart_object', 'tipo': type(e).__name__, 'layer_id': L.layer_id})
    reg['texto'] = None
    if L.kind == 'type':
        try:
            reg['texto'] = info_texto(L)
        except Exception as e:
            reg['texto_erro'] = type(e).__name__
            contexto['erros'].append({'etapa': 'texto', 'tipo': type(e).__name__, 'layer_id': L.layer_id})
    medidas = {'traco_forma': info_traco_forma(L)}
    sem_pixel_com_preenchimento = (not L.has_pixels()) and adaptador.tem_preenchimento(L)
    medidas['preenchimento_sem_pixel'] = sem_pixel_com_preenchimento
    if sem_pixel_com_preenchimento:
        pac = efeitos_1260.PREENCHIMENTOS.get(L.kind)
        if pac and not contexto['pacotes'].get(pac, False):
            medidas['preenchimento_exige_pacote_ausente'] = pac
        alertas.append('preenchimento sem pixel guardado, desenhado pelo psd-tools: %s' % L.kind)
    for e in reg.get('efeitos') or []:
        if e['ativo'] and e['desenhado_pelo_render'] and e['tipo'] != 'ColorOverlay':
            alertas.append('efeito desenhado pelo psd-tools por aproximação: %s (conferir na prova de pixel)' % e['tipo'])
    if reg.get('texto') and any(r['traco_texto'] for r in reg['texto']['runs'] if r['tem_caractere_visivel']):
        alertas.append('texto com traço (StrokeFlag) no motor de texto')
    so = reg.get('smart_object') or {}
    if so.get('filtros_inteligentes'):
        alertas.append('smart object com filtros inteligentes: re-rasterizar o original perde os filtros')
    reg['medidas_regras'] = medidas
    reg['alertas'] = alertas
    reg['fora_do_canvas_px'] = None
    b = reg['caixa']
    if area(b):
        reg['fora_do_canvas_px'] = {'esq': max(0, -b[0]), 'dir': max(0, b[2] - W), 'topo': max(0, -b[1]),
                                    'base': max(0, b[3] - H)}
    return reg


def bases_de_clip(camadas):
    base_de = {}
    for L in camadas:
        try:
            if not L.clipping and L.has_clip_layers():
                for c in L.clip_layers:
                    base_de[id(c)] = L
        except Exception:
            pass
    return base_de


def contar(regs):
    return collections.Counter(r.get('kind') for r in regs)
