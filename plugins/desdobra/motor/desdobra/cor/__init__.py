# -*- coding: utf-8 -*-
"""Cor: todo descritor de cor do PSD passa pelo perfil ICC do documento antes de virar token sRGB.

Regras (arquitetura-v1.md, 4.6):
  - preenchimento, overlay, cor de texto e traco vem no espaco do documento. Usados direto, erram de ΔE76
    10,9 a 13,0 nos arquivos Adobe RGB do corpus (pesquisa/corpus-testes.md, 3). A conversao e feita pelo
    LittleCMS do Pillow (ImageCms), do perfil do documento para sRGB. O perfil do documento e dado de cliente: ele so
    e aberto no processo filho isolado (desdobra.cor.filho, arquitetura-v1.md, 7.1), que devolve so numeros ao
    processo principal (converter_isolado e ConversorPronto);
  - documento sem perfil usa a curva sRGB;
  - asset com perfil diferente do documento e convertido do perfil dele para o do documento (decisoes-v1.md,
    29/10, 8, revista em 31/10): no corpus, o pixel que o Photoshop gravou para o smart object bate com a conversao
    (diferenca ate 0,57), e atribuir afastava ate 9,79 no canal R. A conversao dos pixels e feita no render, no
    processo filho, porque abre o perfil do asset;
  - o intent da conversao, a compensacao de ponto preto e a escrita "sRGB sem perfil embutido" sao parametros
    explicitos do job (arquitetura-v1.md, 10.2, pergunta 5). Sem parametro do job, vale o padrao do registro de
    limites, que esta a calibrar.

Cada token guarda a origem: valor no espaco do documento, perfil (nome e sha256), intent e compensacao.
Nada aqui le PSD: o perfil chega em bytes (o filho do leitor grava documento.icc na pasta bruta). A classe
Conversor, que abre o perfil, roda no processo principal so com o perfil sRGB do proprio LittleCMS (documento sem
perfil); com o perfil do documento, ela roda dentro do filho.
"""
import colorsys
import hashlib
import io
import math
from dataclasses import dataclass, field

from PIL import Image, ImageCms, features

from desdobra import limites

INTENTS = {
    'perceptual': ImageCms.Intent.PERCEPTUAL,
    'relativo_colorimetrico': ImageCms.Intent.RELATIVE_COLORIMETRIC,
    'saturacao': ImageCms.Intent.SATURATION,
    'absoluto_colorimetrico': ImageCms.Intent.ABSOLUTE_COLORIMETRIC,
}
SIM_NAO = ('sim', 'nao')
FONTE_CONVERSAO = {'arquivo': 'pesquisa/corpus-testes.md', 'secao': '3'}
FONTE_CONVERTER = {'arquivo': 'decisoes-v1.md', 'secao': '29/10, respostas ao teste do corpus, 8, revista em 31/10'}
FONTE_SEM_PERFIL = {'arquivo': 'arquitetura-v1.md', 'secao': '4.6'}

# perfil do documento -> como o token foi calculado
TRATAMENTO_ICC = 'icc_do_documento'
TRATAMENTO_SEM_PERFIL = 'sem_perfil_usa_srgb'
TRATAMENTO_INDISPONIVEL = 'perfil_indisponivel'
TRATAMENTO_ILEGIVEL = 'perfil_ilegivel'

ESCALA_8_BITS = 255.0  # numero-neutro: escala de cor de 8 bits
DESLOCAMENTO_AB_8_BITS = 128  # numero-neutro: codificacao de a* e b* no modo LAB de 8 bits do Pillow
ESCALA_L_8_BITS = 100.0  # numero-neutro: L* vai de 0 a 100


class ErroCor(Exception):
    pass


def _sim(valor):
    return valor in (True, 'sim')


@dataclass(frozen=True)
class Parametros:
    """Parametros de cor do job. origem diz, para cada campo, se veio do job ou do registro (a calibrar)."""
    intent: str
    compensacao_ponto_preto: bool
    perfil_embutido_na_saida: bool
    origem: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.intent not in INTENTS:
            raise ErroCor('intent de conversão desconhecido: %r (use %s)' % (self.intent, ', '.join(INTENTS)))

    def para_json(self):
        """Os tres parametros com a origem e, quando vem do registro, a citacao do limite."""
        ids = {'intent': 'cor.intent_saida', 'compensacao_ponto_preto': 'cor.compensacao_ponto_preto',
               'perfil_embutido_na_saida': 'cor.saida_perfil_embutido'}
        out = {}
        for campo, lid in ids.items():
            valor = getattr(self, campo)
            item = {'valor': valor, 'origem': self.origem.get(campo, 'registro')}
            if item['origem'] == 'registro':
                item['limite'] = limites.obter(lid).citacao()
            out[campo] = item
        out['saida'] = {'espaco': 'sRGB', 'perfil_embutido': self.perfil_embutido_na_saida}
        return out


def parametros(intent=None, compensacao_ponto_preto=None, perfil_embutido_na_saida=None):
    """Junta os parametros dados pelo job com o padrao do registro. None quer dizer "nao veio do job"."""
    origem = {}
    if intent is None:
        intent = limites.valor('cor.intent_saida')
        origem['intent'] = 'registro'
    else:
        origem['intent'] = 'job'
    if compensacao_ponto_preto is None:
        compensacao_ponto_preto = _sim(limites.valor('cor.compensacao_ponto_preto'))
        origem['compensacao_ponto_preto'] = 'registro'
    else:
        origem['compensacao_ponto_preto'] = 'job'
    if perfil_embutido_na_saida is None:
        perfil_embutido_na_saida = _sim(limites.valor('cor.saida_perfil_embutido'))
        origem['perfil_embutido_na_saida'] = 'registro'
    else:
        origem['perfil_embutido_na_saida'] = 'job'
    return Parametros(intent=intent, compensacao_ponto_preto=bool(_sim(compensacao_ponto_preto)),
                      perfil_embutido_na_saida=bool(_sim(perfil_embutido_na_saida)), origem=origem)


def versao_lcms():
    try:
        return features.version('littlecms2')
    except Exception:
        return None


def perfil_srgb():
    return ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB'))


def descrever_perfil(dados):
    """{'nome', 'sha256', 'bytes'} de um perfil em bytes. ErroCor se o LittleCMS nao le."""
    try:
        p = ImageCms.ImageCmsProfile(io.BytesIO(dados))
        nome = ImageCms.getProfileDescription(p).strip()
    except Exception as e:  # noqa: BLE001 - perfil e entrada nao confiavel
        raise ErroCor('o LittleCMS não leu o perfil (%s)' % type(e).__name__) from None
    return {'nome': nome, 'sha256': hashlib.sha256(dados).hexdigest(), 'bytes': len(dados)}


# ------------------------------------------------------------------ descritores
def cor_do_descritor(classe, valores):
    """Descritor do Photoshop -> {'modelo', 'valores'} no espaco do documento, sem conversao.

    rgb: tres valores de 0 a 255 (RGBC com Rd/Grn/Bl, ou redFloat/greenFloat/blueFloat de 0 a 1);
    hsb: convertido para rgb do documento (o HSB do Photoshop e o mesmo espaco RGB do documento);
    lab: L*, a*, b* (D50);
    cmyk, cinza e cor de catalogo ficam como estao, com modelo proprio (o motor nao converte)."""
    v = {str(k).strip(): x for k, x in (valores or {}).items()}

    def n(*chaves):
        for k in chaves:
            x = v.get(k)
            if isinstance(x, (int, float)) and not isinstance(x, bool):
                return float(x)
        return None

    if classe == 'RGBC':
        r, g, b = n('Rd'), n('Grn'), n('Bl')
        if None in (r, g, b):
            r, g, b = n('redFloat'), n('greenFloat'), n('blueFloat')
            if None in (r, g, b):
                return {'modelo': 'desconhecido', 'valores': None}
            r, g, b = r * ESCALA_8_BITS, g * ESCALA_8_BITS, b * ESCALA_8_BITS
        return {'modelo': 'rgb', 'valores': [r, g, b]}
    if classe == 'HSBC':
        h, s_, b = n('H'), n('Strt'), n('Brgh')
        if None in (h, s_, b):
            return {'modelo': 'desconhecido', 'valores': None}
        r, g, b2 = colorsys.hsv_to_rgb((h % 360.0) / 360.0, s_ / 100.0, b / 100.0)  # numero-neutro: graus e porcentagem do descritor
        return {'modelo': 'rgb', 'valores': [r * ESCALA_8_BITS, g * ESCALA_8_BITS, b2 * ESCALA_8_BITS],
                'convertido_de': 'hsb'}
    if classe == 'LbCl':
        lv, a, b = n('Lmnc'), n('A'), n('B')
        if None in (lv, a, b):
            return {'modelo': 'desconhecido', 'valores': None}
        return {'modelo': 'lab', 'valores': [lv, a, b]}
    if classe == 'CMYC':
        return {'modelo': 'cmyk', 'valores': [n('Cyn'), n('Mgnt'), n('Ylw'), n('Blck')]}
    if classe == 'Grsc':
        return {'modelo': 'cinza', 'valores': [n('Gry')]}
    if classe == 'BkCl':
        return {'modelo': 'catalogo', 'valores': None}
    return {'modelo': 'desconhecido', 'valores': None}


def cor_do_texto(cor_valores):
    """FillColor do motor de texto ([A, R, G, B] de 0 a 1) -> {'modelo': 'rgb', 'valores', 'alfa'}."""
    if not cor_valores or len(cor_valores) != 4:  # numero-neutro: cor ARGB tem 4 componentes
        return None
    a, r, g, b = (float(x) for x in cor_valores)
    return {'modelo': 'rgb', 'valores': [r * ESCALA_8_BITS, g * ESCALA_8_BITS, b * ESCALA_8_BITS], 'alfa': a}


def em_8_bits(valores):
    return [max(0, min(int(ESCALA_8_BITS), int(math.floor(float(x) + 0.5)))) for x in valores]  # numero-neutro: arredondamento


def hex_de(rgb):
    return '#%02X%02X%02X' % tuple(rgb)


# ------------------------------------------------------------------ conversor
class Conversor:
    """Converte cores do espaco do documento para sRGB pelo perfil do documento.

    icc: bytes do perfil do documento, ou None quando o documento nao tem perfil (usa a curva sRGB);
    indisponivel: o documento tem perfil, mas os bytes nao chegaram (laudo gravado antes do M2). Nesse caso o
    conversor nao inventa: todo token sai "nao_convertido" com o motivo."""

    def __init__(self, icc, parametros, *, indisponivel=False, otimizar=False):
        self.parametros = parametros
        self.intent = INTENTS[parametros.intent]
        self.flags = ImageCms.Flags.NONE if otimizar else ImageCms.Flags.NOOPTIMIZE
        if parametros.compensacao_ponto_preto:
            self.flags |= ImageCms.Flags.BLACKPOINTCOMPENSATION
        self.srgb = perfil_srgb()
        self.motivo = None
        self.perfil = None
        self._rgb = self._lab = None
        if icc:
            try:
                self.perfil = descrever_perfil(icc)
                self.origem_icc = ImageCms.ImageCmsProfile(io.BytesIO(icc))
                self.tratamento = TRATAMENTO_ICC
            except ErroCor as e:
                self.tratamento, self.motivo, self.origem_icc = TRATAMENTO_ILEGIVEL, str(e), None
        elif indisponivel:
            self.tratamento, self.origem_icc = TRATAMENTO_INDISPONIVEL, None
            self.motivo = ('o documento tem perfil, mas o arquivo do perfil não está na leitura: rode a leitura de '
                           'novo com esta versão do motor')
        else:
            self.tratamento, self.origem_icc = TRATAMENTO_SEM_PERFIL, self.srgb
            self.perfil = {'nome': 'sRGB (documento sem perfil)', 'sha256': None, 'bytes': None}
        if self.origem_icc is not None:
            try:
                self._rgb = ImageCms.buildTransform(self.origem_icc, self.srgb, 'RGB', 'RGB',
                                                    renderingIntent=self.intent, flags=self.flags)
            except Exception as e:  # noqa: BLE001 - perfil de outro espaco (CMYK, cinza) ou quebrado
                self.tratamento = TRATAMENTO_ILEGIVEL
                self.motivo = 'o perfil do documento não converte de RGB para sRGB (%s)' % type(e).__name__
                self._rgb = None

    @property
    def converte(self):
        return self._rgb is not None

    def info(self):
        return {'tratamento': self.tratamento, 'nome': (self.perfil or {}).get('nome'),
                'sha256': (self.perfil or {}).get('sha256'), 'motivo': self.motivo,
                'fonte': FONTE_SEM_PERFIL if self.tratamento == TRATAMENTO_SEM_PERFIL else FONTE_CONVERSAO}

    def rgb(self, valores_8_bits):
        im = Image.new('RGB', (1, 1), tuple(valores_8_bits))
        return list(ImageCms.applyTransform(im, self._rgb).getpixel((0, 0)))

    def lab(self, lab):
        if self._lab is None:
            perfil_lab = ImageCms.ImageCmsProfile(ImageCms.createProfile('LAB'))
            self._lab = ImageCms.buildTransform(perfil_lab, self.srgb, 'LAB', 'RGB', renderingIntent=self.intent,
                                                flags=self.flags)
        lv, a, b = lab
        px = (max(0, min(int(ESCALA_8_BITS), int(round(lv / ESCALA_L_8_BITS * ESCALA_8_BITS)))),
              max(0, min(int(ESCALA_8_BITS), int(round(a)) + DESLOCAMENTO_AB_8_BITS)),
              max(0, min(int(ESCALA_8_BITS), int(round(b)) + DESLOCAMENTO_AB_8_BITS)))
        im = Image.new('LAB', (1, 1), px)
        return list(ImageCms.applyTransform(im, self._lab).getpixel((0, 0)))

    def imagem(self, img):
        """Imagem RGB ou RGBA no espaco do documento -> sRGB (o alfa fica como esta)."""
        if self._rgb is None:
            raise ErroCor(self.motivo or 'sem conversão')
        alfa = img.getchannel('A') if img.mode == 'RGBA' else None
        out = ImageCms.applyTransform(img.convert('RGB'), self._rgb)
        if alfa is not None:
            out.putalpha(alfa)
        return out

    def token(self, cor):
        """{'srgb', 'srgb_hex', 'situacao', 'motivo', 'origem'} de uma cor de cor_do_descritor/cor_do_texto."""
        modelo = (cor or {}).get('modelo')
        valores = (cor or {}).get('valores')
        origem = {'modelo': modelo, 'valor_documento': [round(float(x), 4) for x in valores] if valores
                  and all(x is not None for x in valores) else None,
                  'perfil': {'nome': (self.perfil or {}).get('nome'), 'sha256': (self.perfil or {}).get('sha256'),
                             'tratamento': self.tratamento},
                  'intent': self.parametros.intent, 'compensacao_ponto_preto': self.parametros.compensacao_ponto_preto}
        if cor and cor.get('convertido_de'):
            origem['convertido_de'] = cor['convertido_de']
        base = {'srgb': None, 'srgb_hex': None, 'situacao': 'nao_convertido', 'motivo': None, 'origem': origem}
        if not self.converte:
            base['motivo'] = self.motivo
            return base
        if modelo == 'rgb' and origem['valor_documento']:
            v8 = em_8_bits(valores)
            origem['valor_documento_8_bits'] = v8
            srgb = self.rgb(v8)
        elif modelo == 'lab' and origem['valor_documento']:
            srgb = self.lab(valores)
        else:
            base['motivo'] = 'cor no modelo %s: o motor não converte este modelo de cor' % (modelo or 'desconhecido')
            return base
        base.update(srgb=srgb, srgb_hex=hex_de(srgb), situacao='convertido')
        return base


# ------------------------------------------------------------------ conversao no processo filho
MODULO_FILHO = 'desdobra.cor.filho'
ESQUEMA_CONVERSAO = 'conversao-cor/1'
MOTIVO_FILHO = {
    'memoria': 'a conversão de cor no processo isolado passou do orçamento de memória',
    'tempo': 'a conversão de cor no processo isolado passou do tempo máximo',
    'queda': 'o processo isolado da conversão de cor caiu',
    'plataforma': 'o isolamento do processo da conversão de cor não está disponível neste sistema',
    'bug': 'o processo isolado da conversão de cor terminou com erro interno',
}


class ErroAuditoriaCor(ErroCor):
    """O gancho de auditoria barrou uma acao do filho da cor (alarme de seguranca, nunca bloqueio comum)."""


class ConversorPronto(Conversor):
    """Conversor com as cores ja convertidas pelo filho (desdobra.cor.filho): so consulta numeros.

    Tem a mesma interface do Conversor (token, info, converte), mas nunca abre o perfil no processo principal."""

    def __init__(self, parametros, perfil, tratamento, motivo, rgb, lab):  # noqa: super nao e chamado de proposito
        self.parametros = parametros
        self.intent = INTENTS[parametros.intent]
        self.perfil, self.tratamento, self.motivo = perfil, tratamento, motivo
        self.origem_icc = self.srgb = None
        convertido = tratamento == TRATAMENTO_ICC
        self._rgb = {tuple(int(x) for x in a): list(b) for a, b in rgb} if convertido else None
        self._lab = {tuple(float(x) for x in a): list(b) for a, b in lab} if convertido else None

    def rgb(self, valores_8_bits):
        return list(self._rgb[tuple(int(x) for x in valores_8_bits)])

    def lab(self, lab):
        return list(self._lab[tuple(float(x) for x in lab)])

    def imagem(self, img):
        raise ErroCor('o conversor pronto só converte as cores pedidas ao processo isolado')


def cores_pedidas(cores):
    """(rgb em 8 bits, lab) distintos das cores que o token vai converter, na ordem em que aparecem."""
    rgb, lab = [], []
    for c in cores:
        valores = (c or {}).get('valores')
        if not valores or any(x is None for x in valores):
            continue
        if c.get('modelo') == 'rgb':
            v8 = em_8_bits(valores)
            if v8 not in rgb:
                rgb.append(v8)
        elif c.get('modelo') == 'lab':
            v = [float(x) for x in valores]
            if v not in lab:
                lab.append(v)
    return rgb, lab


def orcamento_filho(n_bytes):
    """(isolador.base_python_bytes + cor.fator_abertura_max x bytes do perfil) x isolador.margem_orcamento."""
    base = limites.valor('isolador.base_python_bytes')
    fator = limites.valor('cor.fator_abertura_max')
    margem = limites.valor('isolador.margem_orcamento')
    return int((base + fator * int(n_bytes)) * margem)


def converter_isolado(caminho_icc, parametros, cores, pasta_trabalho, *, plat=None):
    """Abre o perfil ICC do documento e converte as cores no filho isolado. Devolve um ConversorPronto.

    Queda, memoria, tempo e bug do filho viram perfil_ilegivel com o motivo (as cores ficam nao convertidas);
    o alarme do gancho de auditoria levanta ErroAuditoriaCor. pasta_trabalho e apagada no fim."""
    import json
    import shutil
    from pathlib import Path

    from desdobra import contratos, plataforma
    plat = plat or plataforma.obter()
    caminho_icc, pasta_trabalho = Path(caminho_icc).resolve(), Path(pasta_trabalho).resolve()
    shutil.rmtree(pasta_trabalho, ignore_errors=True)
    saida, trabalho = pasta_trabalho / 'saida', pasta_trabalho / 'trabalho'
    saida.mkdir(parents=True)
    trabalho.mkdir(parents=True)
    rgb, lab = cores_pedidas(cores)
    pedido = pasta_trabalho / 'pedido.json'
    pedido.write_text(json.dumps({'intent': parametros.intent, 'compensacao_ponto_preto': parametros.compensacao_ponto_preto,
                                  'rgb': rgb, 'lab': lab}), encoding='utf-8')
    orc = orcamento_filho(caminho_icc.stat().st_size)
    cmd = [str(plat.interpretador()), '-I', '-B', '-m', MODULO_FILHO, str(caminho_icc), str(pedido), str(saida),
           '--orcamento-bytes', str(orc)]
    try:
        r = plat.executar_isolado(cmd, orc, float(limites.valor('cor.tempo_max_s')), trabalho)
        arq = saida / 'conversao.json'
        conv = None
        if arq.is_file():
            try:
                conv = contratos.ler(arq, ESQUEMA_CONVERSAO)
            except contratos.ErroContrato:
                conv = None
    finally:
        shutil.rmtree(pasta_trabalho, ignore_errors=True)
    if conv is not None and (conv['recusa'] == 'auditoria' or conv['auditoria']['bloqueios']):
        raise ErroAuditoriaCor('o gancho de auditoria barrou uma ação do processo da conversão de cor')
    if r.situacao == 'recusado':
        motivo = MOTIVO_FILHO['plataforma']
    elif conv is not None and r.situacao == 'ok' and r.codigo == 0 and conv['recusa'] is None:
        return ConversorPronto(parametros, conv['perfil'], conv['tratamento'], conv['motivo'], conv['rgb'], conv['lab'])
    elif (conv or {}).get('recusa') == 'memoria' or r.situacao == 'memoria':
        motivo = MOTIVO_FILHO['memoria']
    else:
        motivo = MOTIVO_FILHO.get(r.situacao, MOTIVO_FILHO['bug'])
    return ConversorPronto(parametros, None, TRATAMENTO_ILEGIVEL, motivo, [], [])


# ------------------------------------------------------------------ asset com outro perfil
def tratamento_do_asset(perfil_documento, perfil_asset):
    """Como o asset entra na peca: com perfil diferente do documento, os pixels sao convertidos para o do documento.

    perfil_documento, perfil_asset: {'nome', 'sha256'} ou None (sem perfil, ou nao lido)."""
    sha_doc = (perfil_documento or {}).get('sha256')
    sha_asset = (perfil_asset or {}).get('sha256')
    if perfil_asset is None:
        tratamento = 'perfil_do_asset_nao_lido'
    elif sha_asset is None:
        tratamento = 'asset_sem_perfil'
    elif sha_asset == sha_doc:
        tratamento = 'mesmo_perfil'
    else:
        tratamento = 'converter_para_perfil_do_documento'
    return {'tratamento': tratamento, 'converte_pixels': tratamento == 'converter_para_perfil_do_documento',
            'perfil_efetivo': perfil_documento, 'fonte': FONTE_CONVERTER}


# ------------------------------------------------------------------ medida de diferenca (registro)
_SRGB_PARA_XYZ = ((0.4124564, 0.3575761, 0.1804375),  # numero-neutro: matriz da norma sRGB (IEC 61966-2-1), D65
                  (0.2126729, 0.7151522, 0.0721750),  # numero-neutro: idem
                  (0.0193339, 0.1191920, 0.9503041))  # numero-neutro: idem
_BRANCO_D65 = (0.95047, 1.0, 1.08883)  # numero-neutro: branco de referencia D65


def _linear(c):
    c = c / ESCALA_8_BITS
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4  # numero-neutro: curva da norma sRGB


def _f_lab(t):
    return t ** (1.0 / 3.0) if t > (6.0 / 29.0) ** 3 else t / (3 * (6.0 / 29.0) ** 2) + 4.0 / 29.0  # numero-neutro: CIE Lab


def srgb_para_lab(rgb):
    """sRGB de 8 bits (0 a 255, aceita fracao) -> CIE Lab D65, em ponto flutuante."""
    lin = [_linear(float(c)) for c in rgb]
    xyz = [sum(m * c for m, c in zip(linha, lin)) for linha in _SRGB_PARA_XYZ]
    fx, fy, fz = (_f_lab(x / w) for x, w in zip(xyz, _BRANCO_D65))
    return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))  # numero-neutro: CIE Lab


def delta_e76(rgb1, rgb2):
    """ΔE76 entre duas cores sRGB de 8 bits (a medida da pesquisa, pesquisa/corpus-testes.md, 3)."""
    a, b = srgb_para_lab(rgb1), srgb_para_lab(rgb2)
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))
