# -*- coding: utf-8 -*-
"""Processo filho do leitor: o unico codigo que parseia PSD de cliente.

Chamada (docs/m1-interfaces.md, 8.2):
    python -I -B -m desdobra.leitor.filho <arquivo> <pasta_saida> --orcamento-bytes N --profundidade N
        --profundidade-max N [--recorte INICIO:TAMANHO] [--sem-composicao]

Ordem:
  1. le os argumentos e espera a linha 'iniciar' na entrada padrao (o isolador so a manda depois de confinar
     o processo). Antes disso, nada de arriscado;
  2. importa as bibliotecas e instala o gancho de auditoria (alarme);
  3. confere os 26 bytes do cabecalho e a estimativa contra o orcamento, antes de alocar;
  4. leitura estrutural por deslocamento e indice proprio dos smart objects (lnk2, lnk3, lnkD, lnkE);
  5. abre com PSDImage.open, max_alloc_bytes e parse_limits da 1.26.0, sem os dados dos smart objects
     (documento) ou a partir dos bytes do recorte em io.BytesIO (smart object embutido);
  6. extrai a estrutura, as miniaturas e os assets, mede a cobertura e grava estrutura.json;
  7. sem --sem-composicao: grava a previa, recompoe em faixas, faz a prova de pixel e regrava estrutura.json.

Tudo vai para o disco, em <pasta_saida>, com gravacao atomica. Na saida padrao, no maximo uma linha JSON
(filho/1). Codigos: 0 estrutura gravada; 2 argumentos; 3 recusado; 4 memoria; 5 auditoria; 1 bug.
"""
import argparse
import enum
import json
import logging
import os
import sys
import time
import traceback
from pathlib import Path


class CodigoFilho(enum.IntEnum):
    OK = 0
    BUG = 1
    ARGUMENTOS = 2
    RECUSADO = 3
    MEMORIA = 4
    AUDITORIA = 5


LINHA_LIBERAR = b'iniciar\n'
ESQUEMA_SAIDA = 'filho/1'


class Recusa(Exception):
    def __init__(self, tipo, etapa, motivo, codigo, medidas=None):
        super().__init__(motivo)
        self.tipo, self.etapa, self.motivo, self.codigo, self.medidas = tipo, etapa, motivo, codigo, medidas or {}


class _Argumentos(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write('argumentos invalidos para o filho do leitor\n')
        raise SystemExit(int(CodigoFilho.ARGUMENTOS))


def argumentos(argv):
    ap = _Argumentos(prog='desdobra.leitor.filho', add_help=False)
    ap.add_argument('arquivo')
    ap.add_argument('pasta_saida')
    ap.add_argument('--orcamento-bytes', type=int, required=True)
    ap.add_argument('--profundidade', type=int, required=True)
    ap.add_argument('--profundidade-max', type=int, required=True)
    ap.add_argument('--recorte', default=None)
    ap.add_argument('--sem-composicao', action='store_true')
    a = ap.parse_args(argv)
    if a.recorte is not None:
        try:
            ini, tam = (int(x) for x in a.recorte.split(':'))
        except ValueError:
            ap.error('recorte')
        if ini < 0 or tam < 1:
            ap.error('recorte')
        a.recorte = (ini, tam)
    if a.orcamento_bytes < 1 or a.profundidade < 0 or a.profundidade_max < 0:
        ap.error('numeros')
    return a


# ------------------------------------------------------------------ coletor do log do psd-tools
class ColetorLog(logging.Handler):
    """Guarda o modelo da mensagem (texto fixo da biblioteca), o nivel, a contagem e os layer_id citados.
    Nunca guarda a mensagem formatada, que pode trazer nome de camada."""

    PALAVRAS_PULO = ('skip', 'unsupported', 'cannot', 'not implemented', 'failed', 'undrawable', 'unreadable')

    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.itens = {}

    def emit(self, record):
        try:
            modelo = str(record.msg)[:300]  # numero-neutro: corte do texto do modelo
            chave = (record.levelname, record.name, modelo)
            it = self.itens.get(chave)
            if it is None:
                it = self.itens[chave] = {'nivel': record.levelname, 'logger': record.name, 'modelo': modelo,
                                          'ocorrencias': 0, 'layer_ids': []}
            it['ocorrencias'] += 1
            for a in (record.args if isinstance(record.args, tuple) else ()):
                lid = getattr(a, 'layer_id', None)
                if isinstance(lid, int) and lid not in it['layer_ids'] and len(it['layer_ids']) < 50:  # numero-neutro: teto da lista
                    it['layer_ids'].append(lid)
        except Exception:
            pass

    def avisos(self):
        return [v for v in self.itens.values() if v['nivel'] != 'DEBUG'] + \
            [v for v in self.itens.values() if v['nivel'] == 'DEBUG' and self._eh_pulo(v['modelo'])]

    def efeitos_pulados(self):
        return [v for v in self.itens.values() if self._eh_pulo(v['modelo'])]

    def _eh_pulo(self, modelo):
        m = modelo.lower()
        return any(p in m for p in self.PALAVRAS_PULO)


# ------------------------------------------------------------------ escrita
class Saida:
    def __init__(self, pasta):
        self.pasta = Path(pasta)

    def recusa(self, r, origem_sha=None):
        from desdobra import contratos
        dados = {'esquema': 'recusa/1', 'tipo': r.tipo, 'etapa': r.etapa, 'motivo': r.motivo, 'codigo': int(r.codigo),
                 'medidas': {k: v for k, v in r.medidas.items() if isinstance(v, (int, float, str, bool)) or v is None},
                 'origem_sha256': origem_sha}
        contratos.gravar(self.pasta / 'recusa.json', dados, 'recusa/1')
        return 'recusa.json'

    def estrutura(self, dados):
        from desdobra import contratos
        contratos.gravar(self.pasta / 'estrutura.json', dados, 'estrutura/1')
        return 'estrutura.json'


def linha_saida(codigo, arquivo):
    sys.stdout.write(json.dumps({'esquema': ESQUEMA_SAIDA, 'codigo': int(codigo), 'arquivo': arquivo}) + '\n')
    sys.stdout.flush()


# ------------------------------------------------------------------ trabalho
def importar_bibliotecas():
    """Tudo o que e pesado entra antes do gancho de auditoria (DLLs e dados de pacote)."""
    import numpy  # noqa: F401
    import PIL.Image  # noqa: F401
    import PIL.ImageCms  # noqa: F401
    import PIL.PngImagePlugin  # noqa: F401
    import PIL.JpegImagePlugin  # noqa: F401
    import PIL.TiffImagePlugin  # noqa: F401
    import scipy.interpolate  # noqa: F401
    import scipy.ndimage  # noqa: F401
    import scipy.spatial  # noqa: F401
    import psd_tools  # noqa: F401
    import psd_tools.composite  # noqa: F401
    import psd_tools.composite.composite  # noqa: F401
    import psd_tools.composite.effects  # noqa: F401
    import psd_tools.composite.paint  # noqa: F401
    import psd_tools.composite.vector  # noqa: F401
    import jsonschema  # noqa: F401
    from desdobra import contratos, limites  # noqa: F401
    from desdobra.laudo import efeitos_1260  # noqa: F401
    from desdobra.leitor import adaptador, cabecalho, extrair, indice, pixels  # noqa: F401
    limites.carregar()
    for nome in ('estrutura/1', 'recusa/1'):
        contratos.carregar_esquema(nome)
        contratos._validador(nome)
    try:
        import aggdraw  # noqa: F401
    except ImportError:
        pass


def nome_arquivo_camada(reg):
    return str(reg['layer_id']) if reg.get('_id_unico') else 'idx%d' % reg['indice']


def executar(a, gancho, coletor, t0, info):
    import hashlib
    import io

    from psd_tools import PSDImage

    from desdobra import __version__, limites
    from desdobra.leitor import adaptador, cabecalho, extrair, indice, pixels

    pasta = Path(a.pasta_saida)
    saida = Saida(pasta)
    tempos = {}
    erros = []
    etapa_t = [time.perf_counter()]

    def marcar(nome):
        agora = time.perf_counter()
        tempos[nome] = round(agora - etapa_t[0], 3)
        etapa_t[0] = agora

    if a.profundidade > a.profundidade_max:
        raise Recusa('profundidade', 'argumentos', 'O smart object está mais fundo que a profundidade máxima de leitura.',
                     CodigoFilho.RECUSADO, {'profundidade': a.profundidade, 'profundidade_max': a.profundidade_max})

    f = open(a.arquivo, 'rb')
    try:
        base, tam = (a.recorte if a.recorte else (0, None))
        f.seek(0, io.SEEK_END)
        bytes_arquivo = f.tell()
        if a.recorte and base + tam > bytes_arquivo:
            raise Recusa('formato', 'recorte', 'O recorte pedido passa do fim do arquivo.', CodigoFilho.RECUSADO)
        # sha256 do que esta sendo lido (arquivo inteiro ou recorte)
        h = hashlib.sha256()
        f.seek(base)
        falta = tam if tam is not None else bytes_arquivo
        while falta > 0:
            bloco = f.read(min(indice.TAMANHO_LEITURA, falta))
            if not bloco:
                break
            h.update(bloco)
            falta -= len(bloco)
        sha = h.hexdigest()
        info['sha256'] = sha
        origem = {'nome': os.path.basename(a.arquivo), 'sha256': sha, 'bytes': tam if tam is not None else bytes_arquivo,
                  'profundidade': a.profundidade,
                  'recorte': {'inicio': base, 'tamanho': tam} if a.recorte else None, 'pai': None}
        marcar('sha256')

        # 3. cabecalho, antes de alocar
        f.seek(base)
        try:
            cab = cabecalho.ler(f.read(cabecalho.TAMANHO))
            medidas_cab = cabecalho.conferir(cab, a.orcamento_bytes, adaptador.EIXO_MAX_PSD_TOOLS)
        except cabecalho.CabecalhoInvalido as e:
            raise Recusa(e.tipo, 'cabecalho', e.motivo, CodigoFilho.RECUSADO, e.medidas) from None
        marcar('cabecalho')

        # 4. leitura estrutural e indice
        dados_recorte = None
        if a.recorte:
            f.seek(base)
            dados_recorte = f.read(tam)
            fonte_indice = io.BytesIO(dados_recorte)
            base_indice = 0
        else:
            fonte_indice = f
            base_indice = 0
        try:
            secoes = indice.ler_secoes(fonte_indice, base_indice, tam if a.recorte else None)
            registros, erros_indice = indice.indexar_smart(fonte_indice, secoes)
            indice.completar_embutidos(fonte_indice, registros)
            if a.recorte:
                for r in registros:
                    if r['deslocamento_dados'] is not None:
                        r['deslocamento_dados'] += base
            erros += erros_indice
        except (indice.ErroIndice, cabecalho.CabecalhoInvalido, ValueError, OSError) as e:
            raise Recusa('leitura', 'indice', 'A estrutura do arquivo não bate com os comprimentos gravados.',
                         CodigoFilho.RECUSADO, {'erro': type(e).__name__}) from None
        marcar('indice')

        # 5. abertura
        teto_alloc = min(int(limites.valor('leitor.max_alloc_bytes')), int(a.orcamento_bytes))
        parse = adaptador.limites_de_parse(a.orcamento_bytes)
        vista = None
        try:
            if a.recorte:
                psd = PSDImage.open(io.BytesIO(dados_recorte), max_alloc_bytes=teto_alloc, parse_limits=parse)
            else:
                vista = indice.VistaSemSmart(f, secoes)
                psd = PSDImage.open(io.BufferedReader(vista), max_alloc_bytes=teto_alloc, parse_limits=parse)
        except MemoryError:
            raise Recusa('memoria', 'abrir', 'A abertura passou do orçamento de memória.', CodigoFilho.MEMORIA) from None
        except (ValueError, OSError) as e:
            if adaptador.eh_estouro_de_orcamento(e):
                raise Recusa('memoria', 'abrir', 'A abertura passou do orçamento de memória.', CodigoFilho.MEMORIA,
                             {'erro': type(e).__name__}) from None
            raise Recusa('leitura', 'abrir', 'A biblioteca de leitura recusou o arquivo.', CodigoFilho.RECUSADO,
                         {'erro': type(e).__name__}) from None
        del dados_recorte
        marcar('abrir')

        # 6. estrutura
        pacotes = adaptador.pacotes_opcionais()
        camadas = list(psd.descendants())
        doc = extrair.documento(psd, camadas, cab)
        ppi = extrair.dpi_em_ppi(doc.get('dpi'))
        contexto = {'pacotes': pacotes, 'ppi': ppi, 'indice_por_uid': {r['unique_id']: r for r in registros},
                    'arquivo': f, 'erros': erros, 'nome_arquivo_camada': nome_arquivo_camada,
                    'extrair_assets': a.profundidade == 0}
        base_de = extrair.bases_de_clip(camadas)
        regs = []
        ids_vistos = {}
        for i, L in enumerate(camadas):
            ids_vistos[L.layer_id] = ids_vistos.get(L.layer_id, 0) + 1
        for i, L in enumerate(camadas):
            try:
                reg = extrair.metadados(L, i, psd, base_de, contexto)
            except MemoryError:
                raise
            except Exception as e:
                reg = {'layer_id': int(L.layer_id), 'indice': i, 'nome': str(L.name), 'kind': str(L.kind),
                       'pai_id': None, 'caminho_ids': [], 'visivel_propria': False, 'visivel_efetiva': False,
                       'opacidade': 0, 'preenchimento': 0, 'blend': 'NORMAL', 'clipping': False, 'caixa': [0, 0, 0, 0],
                       'erro_camada': type(e).__name__, 'medidas_regras': {}, 'alertas': []}
                erros.append({'etapa': 'camada', 'tipo': type(e).__name__, 'layer_id': int(L.layer_id)})
            reg['_id_unico'] = L.layer_id > 0 and ids_vistos[L.layer_id] == 1
            regs.append(reg)
        marcar('camadas')
        por_id = {}
        for r in regs:
            por_id.setdefault(r['layer_id'], r)
        parametros = {'miniatura_lado_px': int(limites.valor('laudo.miniatura_lado_px'))}
        # cobertura so no documento: a decisao 10 fala das camadas do KV, nao das de dentro de um smart object
        cobertura = pixels.Cobertura(psd.width, psd.height) if a.profundidade == 0 else None
        # dentro de smart object (profundidade > 0) so a estrutura, o texto e o composto gravado interessam: a
        # passada de pixels (miniaturas, assets, cobertura) fica so para o documento
        for i in (range(len(camadas) - 1, -1, -1) if a.profundidade == 0 else ()):
            L, reg = camadas[i], regs[i]
            if 'erro_camada' in reg:
                continue
            try:
                pixels.medir_camada(L, reg, psd, pasta, cobertura, por_id, parametros, contexto)
            except MemoryError:
                reg['pixels'] = {'erro': None, 'pulado': 'orcamento'}
        del cobertura
        for r in regs:
            if r.get('clipping') and r.get('base_do_clip') is not None and r.get('caixa_tinta'):
                base_r = por_id.get(r['base_do_clip'])
                if base_r and base_r.get('caixa_tinta'):
                    r['caixa_tinta_recortada_pela_base'] = extrair.interseccao(r['caixa_tinta'], base_r['caixa_tinta'])
        marcar('pixels')
        for r in regs:
            r.pop('_id_unico', None)
        indice_saida = []
        for r in registros:
            item = {k: r[k] for k in ('unique_id', 'bloco', 'tipo_registro', 'embutido', 'filetype', 'nome',
                                      'deslocamento_dados', 'tamanho_dados', 'sha256', 'assinatura_hex', 'linkado',
                                      'tipo_detectado', 'cabecalho_psd', 'versao_registro')}
            item['layer_ids'] = [x['layer_id'] for x in regs if (x.get('smart_object') or {}).get('unique_id') == r['unique_id']]
            indice_saida.append(item)
        estrutura = {
            'esquema': 'estrutura/1',
            'leitor': {'motor': __version__, 'psd_tools': adaptador.versao_psd_tools(), 'python': sys.version.split()[0],
                       'pacotes': pacotes, 'adaptador': adaptador.VERSAO_ADAPTADOR},
            'origem': origem, 'documento': dict(doc, cabecalho=medidas_cab,
                                                vista_sem_smart={'blocos_removidos': vista.blocos_removidos,
                                                                 'bytes_removidos': vista.bytes_removidos} if vista else None),
            'indice_smart': indice_saida, 'camadas': regs,
            'prova_pixel': {'feita': False, 'motivo': 'pendente'},
            'recursos': {'tempo_s': round(time.perf_counter() - t0, 3), 'pico_bytes': None,
                         'orcamento_bytes': int(a.orcamento_bytes), 'etapas_s': tempos},
            'erros': erros, 'avisos_psd_tools': coletor.avisos(), 'efeitos_pulados': coletor.efeitos_pulados(),
            'auditoria': {'instalado': gancho.instalado, 'bloqueios': list(gancho.bloqueios)},
            'arquivos': {'previa': None, 'recomposicao': None, 'diferenca': None, 'miniaturas': 'miniaturas',
                         'assets': 'assets'},
        }
        if gancho.bloqueios:
            raise Recusa('auditoria', 'estrutura', 'O gancho de auditoria barrou uma ação do processo de leitura.',
                         CodigoFilho.AUDITORIA, {'bloqueios': len(gancho.bloqueios)})
        saida.estrutura(estrutura)
        marcar('gravar_estrutura')

        # 7. previa, recomposicao e prova de pixel
        lado = int(limites.valor('laudo.previa_lado_px'))
        prova = {'feita': False, 'motivo': None}
        merged = None
        # dentro de smart object, o composto gravado so serve para o alerta de composto de uma cor so com texto
        # visivel (desdobra.laudo, composto_uniforme_com_texto); sem texto visivel, decodificar nao mede nada
        sem_texto_visivel = a.profundidade > 0 and not any(r.get('kind') == 'type' and r.get('visivel_efetiva')
                                                            for r in regs)
        try:
            if sem_texto_visivel:
                prova['motivo'] = 'sem_composicao'
            elif psd.has_preview():
                # no documento, a previa sai com o perfil aplicado, como a recomposicao; dentro de smart object so se
                # mede se o composto gravado e de uma cor so, e a conversao de cor nao muda isso
                merged = psd.topil() if a.profundidade == 0 else psd.topil(apply_icc=False)
                if merged is not None:
                    alvo = merged if merged.mode in ('RGB', 'RGBA', 'L', 'LA') else merged.convert('RGB')
                    from desdobra import arquivos as arq
                    arq.gravar_bytes_atomico(pasta / 'previa.png', pixels.png_bytes(pixels.reduzir(alvo, lado)))
                    estrutura['arquivos']['previa'] = 'previa.png'
                    ext = merged.getextrema()
                    canais = ext if isinstance(ext[0], tuple) else (ext,)
                    estrutura['documento']['previa_uniforme'] = all(lo == hi for lo, hi in canais[:len(merged.getbands())])
                    if merged.mode not in ('RGB', 'RGBA', 'L', 'LA'):
                        prova['motivo'] = 'modo_fora_do_escopo'
                        merged = None
            else:
                prova['motivo'] = 'sem_merged'
        except MemoryError:
            prova['motivo'] = 'orcamento'
            merged = None
        except Exception as e:
            prova['motivo'] = 'orcamento' if adaptador.eh_estouro_de_orcamento(e) else 'erro'
            erros.append({'etapa': 'previa', 'tipo': type(e).__name__})
            merged = None
        marcar('previa')
        if a.sem_composicao:
            prova['motivo'] = prova['motivo'] or 'sem_composicao'
        elif merged is not None:
            limiar = limites.valor('prova_pixel.limiar_diferenca')
            try:
                rec, dmax, hist, faixas = pixels.recompor_e_comparar(psd, merged, limiar)
                n = int(dmax.size)
                canais = {nm: pixels.stats_hist(hist[i], n, limiar) for i, nm in enumerate(('R', 'G', 'B'))}
                prova.update({'feita': True, 'limiar': limiar, 'por_canal': canais,
                              'alfa': pixels.stats_hist(hist[3], n, limiar),
                              'px_acima_qualquer_canal': int((dmax > limiar).sum()), 'px_total': n,
                              'pct_px_acima_qualquer_canal': round(float((dmax > limiar).mean()) * 100, 4),  # numero-neutro: porcentagem, so exibicao
                              'faixas': faixas})
                from desdobra import arquivos as arq
                from PIL import Image
                arq.gravar_bytes_atomico(pasta / 'recomposicao.png',
                                         pixels.png_bytes(pixels.reduzir(Image.fromarray(rec, 'RGBA'), lado)))
                del rec
                mapa, fator = pixels.mapa_diferenca(dmax, merged, lado)
                arq.gravar_bytes_atomico(pasta / 'diferenca.png', pixels.png_bytes(mapa))
                estrutura['arquivos']['recomposicao'] = 'recomposicao.png'
                estrutura['arquivos']['diferenca'] = 'diferenca.png'
                prova['diferenca_reducao'] = fator
                regs_s, meta = pixels.regioes(dmax, limiar, int(limites.valor('prova_pixel.regiao_min_px')),
                                              int(limites.valor('prova_pixel.max_regioes')))
                prova['regioes'] = regs_s
                prova['regioes_meta'] = meta
                prova['por_camada'] = pixels.por_camada(dmax, limiar, regs)
                del dmax
            except MemoryError:
                prova = {'feita': False, 'motivo': 'orcamento'}
            except Exception as e:
                if adaptador.eh_estouro_de_orcamento(e):
                    prova = {'feita': False, 'motivo': 'orcamento'}
                else:
                    prova = {'feita': False, 'motivo': 'erro'}
                    erros.append({'etapa': 'recomposicao', 'tipo': type(e).__name__})
        elif not prova['motivo']:
            prova['motivo'] = 'sem_merged'
        del merged
        marcar('prova_pixel')
        estrutura['prova_pixel'] = prova
        estrutura['recursos']['tempo_s'] = round(time.perf_counter() - t0, 3)
        estrutura['avisos_psd_tools'] = coletor.avisos()
        estrutura['efeitos_pulados'] = coletor.efeitos_pulados()
        estrutura['auditoria'] = {'instalado': gancho.instalado, 'bloqueios': list(gancho.bloqueios)}
        if gancho.bloqueios:
            raise Recusa('auditoria', 'prova_pixel', 'O gancho de auditoria barrou uma ação do processo de leitura.',
                         CodigoFilho.AUDITORIA, {'bloqueios': len(gancho.bloqueios)})
        return saida.estrutura(estrutura), sha
    finally:
        f.close()


def main(argv=None):
    t0 = time.perf_counter()
    a = argumentos(sys.argv[1:] if argv is None else argv)
    # 1. espera o isolador liberar
    linha = sys.stdin.buffer.readline()
    if linha != LINHA_LIBERAR:
        sys.stderr.write('o filho do leitor nao recebeu a liberacao do isolador\n')
        return int(CodigoFilho.ARGUMENTOS)
    # 2. bibliotecas e gancho
    importar_bibliotecas()
    from desdobra import PASTA_MOTOR
    from desdobra.leitor import auditoria
    pasta = Path(a.pasta_saida)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / 'miniaturas').mkdir(exist_ok=True)
    (pasta / 'assets').mkdir(exist_ok=True)
    gancho = auditoria.Gancho(a.arquivo, pasta, auditoria.raizes_do_ambiente(PASTA_MOTOR))
    gancho.instalar()
    coletor = ColetorLog()
    lg = logging.getLogger('psd_tools')
    lg.addHandler(coletor)
    lg.setLevel(logging.DEBUG)
    lg.propagate = False
    logging.captureWarnings(True)
    logging.getLogger('py.warnings').addHandler(coletor)
    saida = Saida(pasta)
    info = {'sha256': None}
    try:
        arquivo, _sha = executar(a, gancho, coletor, t0, info)
        linha_saida(CodigoFilho.OK, arquivo)
        return int(CodigoFilho.OK)
    except Recusa as r:
        if gancho.bloqueios and r.tipo != 'auditoria':
            r = Recusa('auditoria', r.etapa, 'O gancho de auditoria barrou uma ação do processo de leitura.',
                       CodigoFilho.AUDITORIA, {'bloqueios': len(gancho.bloqueios)})
        linha_saida(r.codigo, saida.recusa(r, info['sha256']))
        return int(r.codigo)
    except MemoryError:
        r = Recusa('memoria', 'leitura', 'A leitura passou do orçamento de memória.', CodigoFilho.MEMORIA)
        try:
            linha_saida(r.codigo, saida.recusa(r, info['sha256']))
        except MemoryError:
            pass
        return int(CodigoFilho.MEMORIA)
    except (ValueError, OSError) as e:
        from desdobra.leitor import adaptador
        if gancho.bloqueios:
            r = Recusa('auditoria', 'leitura', 'O gancho de auditoria barrou uma ação do processo de leitura.',
                       CodigoFilho.AUDITORIA, {'bloqueios': len(gancho.bloqueios)})
        elif adaptador.eh_estouro_de_orcamento(e):
            r = Recusa('memoria', 'leitura', 'A leitura passou do orçamento de memória.', CodigoFilho.MEMORIA,
                       {'erro': type(e).__name__})
        else:
            r = Recusa('leitura', 'leitura', 'A biblioteca de leitura recusou o arquivo.', CodigoFilho.RECUSADO,
                       {'erro': type(e).__name__})
        linha_saida(r.codigo, saida.recusa(r, info['sha256']))
        return int(r.codigo)
    except Exception:
        if gancho.bloqueios:
            r = Recusa('auditoria', 'leitura', 'O gancho de auditoria barrou uma ação do processo de leitura.',
                       CodigoFilho.AUDITORIA, {'bloqueios': len(gancho.bloqueios)})
            linha_saida(r.codigo, saida.recusa(r, info['sha256']))
            return int(r.codigo)
        traceback.print_exc(file=sys.stderr)
        return int(CodigoFilho.BUG)


if __name__ == '__main__':
    sys.exit(main())
