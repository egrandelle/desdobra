# -*- coding: utf-8 -*-
"""Design system da peca e limites do job: "desdobra ds montar" e "desdobra ds parametros-cor".

Fase "ds" da esteira, depois de "ler" e da conferencia de fontes (arquitetura-v1.md, 4.7 e 5.6). Le o laudo
(laudo/laudo.json), a estrutura bruta do documento e dos smart objects abertos (laudo/bruto/<sha256>/), os
assets (laudo/assets/<sha256>.png, so o alfa) e, quando existe, fontes/conferencia.json. Grava:
  - ds/design-system.json (design-system/1): tokens de cor com a origem (desdobra.cor), de tipografia com as
    metricas do arquivo de fonte, medidas, caixa do sujeito pelo alfa ou "pedir ao DA", e o tratamento de cor
    de cada asset (convertido para o perfil do documento, decisoes-v1.md 29/10 nº 8 revista em 31/10);
  - ds/limites.json (limites/1): os limites que valem para o job, com valor, fonte, situacao e efeito. O que vem
    do PSD entra como referencia e nunca como piso.

Sem fontes/conferencia.json, o design system sai com as metricas da fonte ausentes e a pendencia "fontes nao
conferidas", sem quebrar. Os parametros de cor do job ficam em parametros/cor.json (ds-parametros-cor/1),
gravado por "desdobra ds parametros-cor"; sem o arquivo, vale o padrao do registro de limites (a calibrar).

Este modulo nunca abre PSD nem arquivo de fonte, e nunca parseia o perfil ICC do documento: o perfil chega em
documento.icc, gravado pelo filho do leitor, e e aberto e usado so no filho da cor (desdobra.cor.converter_isolado),
que devolve as cores convertidas; as metricas da fonte chegam prontas na conferencia.
"""
from pathlib import Path

from desdobra import __version__, contratos, limites
from desdobra import cor as mod_cor
from desdobra.arquivos import sha256_arquivo
from desdobra.ds import sujeito as mod_sujeito
from desdobra.ds import tokens as mod_tokens
from desdobra.resultado import Codigo, Resultado

ESQUEMA_DS = 'design-system/1'
ESQUEMA_LIMITES = 'limites/1'
ESQUEMA_PARAMETROS = 'ds-parametros-cor/1'
ESQUEMA_CONFERENCIA = 'conferencia-fontes/1'
ARQUIVO_DS = Path('ds') / 'design-system.json'
ARQUIVO_LIMITES = Path('ds') / 'limites.json'
ARQUIVO_PARAMETROS = Path('parametros') / 'cor.json'
ARQUIVO_CONFERENCIA = Path('fontes') / 'conferencia.json'
ARQUIVO_LAUDO = Path('laudo') / 'laudo.json'
TIPOS_CANDIDATOS_SUJEITO = ('pixel', 'smart_embutido')
# limites do registro que o ds cita no limites.json do job
LIMITES_DO_JOB = ('cor.intent_saida', 'cor.compensacao_ponto_preto', 'cor.saida_perfil_embutido',
                  'cor.delta_e76_token_max', 'cor.gama_mistura_texto', 'ds.sujeito_limiar_alfa',
                  'ds.ampliacao_raster_max')
PARAMETRO_DO_LIMITE = {'cor.intent_saida': 'intent', 'cor.compensacao_ponto_preto': 'compensacao_ponto_preto',
                       'cor.saida_perfil_embutido': 'perfil_embutido_na_saida'}

O_QUE_FAZER_OK = 'O design system está em ds/design-system.json e os limites do job em ds/limites.json.'
O_QUE_FAZER_FONTES = (' As fontes não foram conferidas: as métricas do arquivo de fonte ficaram ausentes. Peça ao '
                      'Claude para seguir o job (/desdobra:continuar), que confere as fontes de novo.')
O_QUE_FAZER_PERFIL = (' O documento tem perfil de cor, mas a leitura foi gravada sem o arquivo do perfil, e as cores '
                      'não foram convertidas. A leitura precisa ser refeita com esta versão do motor: peça ao Claude '
                      'para seguir o job (/desdobra:continuar) e, se o aviso voltar, avise a Trezion.')
O_QUE_FAZER_SUJEITO = (' Em %d camada(s) o sujeito está fundido à foto: o DA marca a caixa do sujeito no briefing.')


class ErroDs(Exception):
    def __init__(self, mensagem, codigo=Codigo.RECUSADO, o_que_fazer=None):
        super().__init__(mensagem)
        self.codigo = codigo
        self.o_que_fazer = o_que_fazer or mensagem


# ------------------------------------------------------------------ entradas
def _ler_estrutura(pasta_bruta):
    caminho = pasta_bruta / 'estrutura.json'
    if not caminho.is_file():
        return None
    return contratos.ler(caminho, 'estrutura/1')


def ler_conferencia(pasta):
    """fontes/conferencia.json validada, ou None quando o arquivo nao existe.

    Valida pelo contrato conferencia-fontes/1 quando o esquema esta instalado; sem ele, confere so a forma
    minima que o ds usa (faces e camadas como listas)."""
    caminho = Path(pasta) / ARQUIVO_CONFERENCIA
    if not caminho.is_file():
        return None
    if ESQUEMA_CONFERENCIA in contratos.listar_esquemas():
        return contratos.ler(caminho, ESQUEMA_CONFERENCIA)
    from desdobra.arquivos import ler_json
    try:
        dados = ler_json(caminho)
    except ValueError as e:
        raise contratos.ErroContrato(ESQUEMA_CONFERENCIA, 'JSON inválido (%s)' % e, origem=caminho.name) from None
    if not isinstance(dados, dict) or not isinstance(dados.get('faces'), list) or not isinstance(dados.get('camadas'), list):
        raise contratos.ErroContrato(ESQUEMA_CONFERENCIA, 'faltam as listas faces e camadas', origem=caminho.name)
    return dados


def ler_parametros(pasta):
    caminho = Path(pasta) / ARQUIVO_PARAMETROS
    if not caminho.is_file():
        return None
    return contratos.ler(caminho, ESQUEMA_PARAMETROS)


def parametros_do_job(dados):
    dados = dados or {}
    return mod_cor.parametros(intent=dados.get('intent'), compensacao_ponto_preto=dados.get('compensacao_ponto_preto'),
                              perfil_embutido_na_saida=dados.get('perfil_embutido_na_saida'))


def _icc(pasta_bruta, doc):
    """(caminho do perfil ou None, indisponivel). indisponivel: o documento tem perfil, mas o arquivo nao veio.
    So confere o sha256 dos bytes; quem abre o perfil e o filho da cor."""
    icc = doc.get('icc') or {}
    if not icc.get('presente'):
        return None, False
    nome = icc.get('arquivo')
    if not nome:
        return None, True
    caminho = (pasta_bruta / nome).resolve()
    if caminho.parent != pasta_bruta.resolve() or not caminho.is_file():
        return None, True
    if icc.get('sha256') and sha256_arquivo(caminho) != icc['sha256']:
        raise ErroDs('O perfil de cor gravado pela leitura não bate com o hash da estrutura.',
                     o_que_fazer='O arquivo do perfil em laudo/bruto mudou fora do motor, e a leitura precisa ser '
                                 'refeita. Peça ao Claude para seguir o job (/desdobra:continuar).')
    return caminho, False


def _alfa_do_asset(caminho):
    """Canal alfa de um asset gravado pelo filho do leitor (PNG do proprio motor), como matriz uint8."""
    import numpy as np
    from PIL import Image
    with Image.open(caminho) as img:
        if img.format != 'PNG':
            raise ValueError('asset fora do formato do motor')
        if img.mode == 'L':
            return np.asarray(img, dtype=np.uint8)
        if 'A' not in img.getbands():
            return np.full((img.height, img.width), int(mod_cor.ESCALA_8_BITS), np.uint8)
        return np.asarray(img.getchannel('A'), dtype=np.uint8)


# ------------------------------------------------------------------ montagem
def _perfil_aninhado(pasta_laudo, so):
    ab = (so or {}).get('abertura') or {}
    if ab.get('situacao') != 'aberto' or not ab.get('pasta'):
        return None
    est = _ler_estrutura((pasta_laudo / ab['pasta']))
    if est is None:
        return None
    icc = est['documento'].get('icc') or {}
    if not icc.get('presente'):
        return {'nome': None, 'sha256': None}
    return {'nome': icc.get('descricao'), 'sha256': icc.get('sha256')}


def _assets(laudo, pasta_laudo, perfil_doc):
    out = []
    for c in laudo['camadas']:
        so = c.get('smart_object') or {}
        if not so.get('embutido'):
            continue
        perfil_asset = _perfil_aninhado(pasta_laudo, so)
        trat = mod_cor.tratamento_do_asset(perfil_doc, perfil_asset)
        out.append(dict(trat, camada=c['identidade']['layer_id'], sha256=so.get('sha256'),
                        tipo_detectado=so.get('tipo_detectado'), perfil_asset=perfil_asset))
    return out


def _sujeitos(camadas, laudo_por_id, pasta_laudo):
    out = []
    for reg in camadas:
        lid = reg['layer_id']
        tipo = (laudo_por_id.get(lid) or {}).get('tipo')
        px = reg.get('pixels') or {}
        if tipo not in TIPOS_CANDIDATOS_SUJEITO or not reg.get('visivel_efetiva') or not px.get('asset_sha256'):
            continue
        # com mascara raster ativa, o leitor grava o alfa visivel (alfa vezes mascara): ele decide o recorte
        sha_alfa = px.get('alfa_visivel_sha256') or px['asset_sha256']
        caminho = pasta_laudo / 'assets' / ('%s.png' % sha_alfa)
        item = {'camada': lid, 'tipo': tipo, 'asset_sha256': px['asset_sha256'],
                'alfa': 'alfa_visivel_com_mascara' if px.get('alfa_visivel_sha256') else 'alfa_da_camada'}
        from PIL import Image
        try:
            alfa = _alfa_do_asset(caminho)
        except Image.DecompressionBombError:
            # o processo principal nao decodifica imagem acima do teto do Pillow: o DA marca a caixa
            out.append(dict(item, metodo='nao_medido', caixa=None,
                            motivo='asset grande demais para medir no processo principal: o DA marca a caixa'))
            continue
        except (OSError, ValueError, MemoryError) as e:
            out.append(dict(item, metodo='nao_medido', caixa=None, motivo='asset ilegível (%s)' % type(e).__name__))
            continue
        caixa = reg.get('caixa') or [0, 0, 0, 0]
        out.append(dict(item, **mod_sujeito.caixa_por_alfa(alfa, (caixa[0], caixa[1]))))
        del alfa
    return out


def _referencias_do_psd(tipografia, medidas, arquivo_sha256):
    """Valores do PSD que entram no limites.json so como referencia (nunca piso sozinho)."""
    refs = []
    vis = [t for t in tipografia if t['visivel'] and t['corpo_efetivo_px']]
    if vis:
        menor = min(vis, key=lambda t: t['corpo_efetivo_px'])
        refs.append({'id': 'psd.corpo_efetivo_min', 'valor': menor['corpo_efetivo_px'], 'unidade': 'px do documento',
                     'nota': 'Menor corpo efetivo de texto visível no KV (escala vertical da matriz).',
                     'camada': menor['camada']})
    ampl = [m for m in medidas if (m.get('folga_resolucao') or {}).get('ampliacao') is not None
            and not m['folga_resolucao']['vetorial']]
    if ampl:
        maior = max(ampl, key=lambda m: m['folga_resolucao']['ampliacao'])
        refs.append({'id': 'psd.ampliacao_raster_max', 'valor': maior['folga_resolucao']['ampliacao'],
                     'unidade': 'vezes o original', 'camada': maior['camada'],
                     'nota': 'Maior ampliação de raster que o próprio KV já faz (pesquisa/corpus-testes.md, 4, item 18).'})
    folgas = [(min(m['folga'].values()), m['camada']) for m in medidas if m.get('folga')]
    if folgas:
        v, lid = min(folgas)
        refs.append({'id': 'psd.folga_tinta_min', 'valor': v, 'unidade': 'px do documento', 'camada': lid,
                     'nota': 'Menor distância da tinta de uma camada visível até a borda da área de referência.'})
    for r in refs:
        r.update(fonte={'arquivo': 'laudo/laudo.json', 'arquivo_sha256': arquivo_sha256, 'camada': r.pop('camada')},
                 situacao='referencia_do_psd', efeito='registra', piso=False)
    return refs


def montar_limites(parametros, referencias, origem):
    itens = []
    for lid in LIMITES_DO_JOB:
        lim = limites.obter(lid)
        item = {'id': lid, 'valor': lim.valor, 'unidade': lim.unidade, 'fonte': lim.fonte, 'situacao': lim.situacao,
                'efeito': lim.efeito_efetivo, 'piso': False}
        if lim.nota:
            item['nota'] = lim.nota
        campo = PARAMETRO_DO_LIMITE.get(lid)
        if campo and parametros.origem.get(campo) == 'job':
            v = getattr(parametros, campo)
            item.update(valor=v if isinstance(v, str) else ('sim' if v else 'nao'), situacao='parametro_do_job',
                        fonte={'arquivo': ARQUIVO_PARAMETROS.as_posix()}, efeito='registra',
                        padrao_do_registro=lim.citacao())
        itens.append(item)
    return {'esquema': ESQUEMA_LIMITES, 'origem': origem, 'limites': itens + referencias}


def montar(pasta_laudo, laudo, estrutura, conferencia, parametros, *, sha_conferencia=None, sha_parametros=None,
           sha_laudo=None, sha_estrutura=None, pasta_trabalho=None):
    """Monta (design_system, limites) a partir das entradas ja lidas e validadas."""
    pasta_laudo = Path(pasta_laudo)
    sha = laudo['origem']['sha256']
    pasta_bruta = pasta_laudo / 'bruto' / sha
    doc = estrutura['documento']
    icc, indisponivel = _icc(pasta_bruta, doc)
    camadas = estrutura['camadas']
    if icc is not None and doc.get('modo') == 'RGB':
        # o perfil do documento e dado de cliente: so o filho isolado da cor o abre (arquitetura-v1.md, 7.1)
        conversor = mod_cor.converter_isolado(icc, parametros, [c for c, _u in mod_tokens.usos_de_cor(camadas)],
                                              pasta_trabalho or pasta_laudo.parent / 'ds' / '.trabalho-cor')
    else:
        conversor = mod_cor.Conversor(None, parametros, indisponivel=indisponivel or icc is not None)
    if doc.get('modo') != 'RGB':
        conversor.tratamento = 'modo_fora_do_escopo'
        conversor.motivo = 'documento no modo %s: o motor converte só documento RGB' % doc.get('modo')
        conversor._rgb = None
    laudo_por_id = {c['identidade']['layer_id']: c for c in laudo['camadas']}
    descritores_lidos = all('cores_descritores' in r for r in camadas)
    cores, mapa = mod_tokens.tokens_de_cor(camadas, conversor)
    tipografia = mod_tokens.tokens_de_tipografia(camadas, conferencia, mapa, sha)
    medidas = mod_tokens.medidas(camadas, laudo_por_id, doc)
    sujeitos = _sujeitos(camadas, laudo_por_id, pasta_laudo)
    icc_doc = doc.get('icc') or {}
    perfil_doc = ({'nome': icc_doc.get('descricao'), 'sha256': icc_doc.get('sha256')} if icc_doc.get('presente')
                  else {'nome': 'sRGB (documento sem perfil)', 'sha256': None})
    assets = _assets(laudo, pasta_laudo, perfil_doc)
    origem = {'arquivo_sha256': sha, 'laudo_sha256': sha_laudo, 'estrutura_sha256': sha_estrutura,
              'conferencia_fontes_sha256': sha_conferencia, 'parametros_cor_sha256': sha_parametros,
              'motor': __version__}
    pendencias = []
    if conferencia is None:
        pendencias.append({'codigo': mod_tokens.SITUACAO_FONTES_NAO_CONFERIDAS,
                           'descricao': 'fontes não conferidas: as métricas do arquivo de fonte ficaram ausentes'})
    if not conversor.converte:
        pendencias.append({'codigo': 'cores_nao_convertidas', 'descricao': conversor.motivo or 'sem conversão'})
    if not descritores_lidos:
        pendencias.append({'codigo': 'descritores_nao_lidos',
                           'descricao': 'a leitura não gravou os descritores de cor das camadas (leitura anterior ao '
                                        'M2): só a cor de texto entrou nos tokens'})
    n_pedir = sum(1 for s in sujeitos if s['metodo'] == mod_sujeito.METODO_PEDIR_AO_DA)
    if n_pedir:
        pendencias.append({'codigo': 'sujeito_pedir_ao_da', 'descricao': 'sujeito fundido à foto em %d camada(s): o '
                                                                        'DA marca a caixa' % n_pedir})
    ds = {
        'esquema': ESQUEMA_DS, 'origem': origem,
        'documento': {'largura': doc['largura'], 'altura': doc['altura'], 'modo': doc.get('modo'),
                      'perfil': conversor.info()},
        'cor': {'parametros': parametros.para_json(), 'biblioteca': {'lcms': mod_cor.versao_lcms()}},
        'fontes': {'situacao': 'conferencia_lida' if conferencia is not None else mod_tokens.SITUACAO_FONTES_NAO_CONFERIDAS,
                   'n_faces': len((conferencia or {}).get('faces') or []),
                   'n_camadas': len((conferencia or {}).get('camadas') or [])},
        'tokens': {'cores': cores, 'tipografia': tipografia, 'medidas': medidas, 'sujeito': sujeitos},
        'tipografia_resumo': mod_tokens.resumo_tipografia(tipografia),
        'assets': assets,
        'pendencias': pendencias,
        'resumo': {'n_cores': len(cores), 'n_cores_convertidas': sum(1 for c in cores if c['situacao'] == 'convertido'),
                   'n_tipografia': len(tipografia),
                   'n_tipografia_com_metricas': sum(1 for t in tipografia if t['metricas']),
                   'n_medidas': len(medidas),
                   'n_sujeito_alfa': sum(1 for s in sujeitos if s['metodo'] == mod_sujeito.METODO_ALFA),
                   'n_sujeito_pedir_ao_da': n_pedir,
                   'n_assets_perfil_convertido': sum(1 for a in assets
                                                     if a['tratamento'] == 'converter_para_perfil_do_documento')},
    }
    lim = montar_limites(parametros, _referencias_do_psd(tipografia, medidas, sha), origem)
    return ds, lim


# ------------------------------------------------------------------ comandos
def _sha(caminho):
    return sha256_arquivo(caminho) if Path(caminho).is_file() else None


def executar_montar(pasta):
    pasta = Path(pasta).resolve()
    caminho_laudo = pasta / ARQUIVO_LAUDO
    if not caminho_laudo.is_file():
        raise ErroDs('O laudo do job ainda não existe.', o_que_fazer='A leitura vem antes. Peça ao Claude para '
                                                                  'seguir o job (/desdobra:continuar).')
    laudo = contratos.ler(caminho_laudo, 'laudo/1')
    sha = laudo['origem']['sha256']
    pasta_laudo = caminho_laudo.parent
    caminho_estrutura = pasta_laudo / 'bruto' / sha / 'estrutura.json'
    estrutura = _ler_estrutura(caminho_estrutura.parent)
    if estrutura is None:
        raise ErroDs('A leitura do documento não deixou a estrutura bruta: o arquivo foi recusado na leitura.',
                     o_que_fazer='Veja as recusas no laudo e peça ao Claude para trocar o KV do job '
                                 '(/desdobra:continuar).')
    if estrutura['origem']['sha256'] != sha:
        raise ErroDs('A estrutura bruta não é do mesmo arquivo do laudo.',
                     o_que_fazer='A pasta laudo/ foi mexida fora do motor, e a leitura precisa ser refeita. Peça '
                                 'ao Claude para seguir o job (/desdobra:continuar).')
    conferencia = ler_conferencia(pasta)
    dados_param = ler_parametros(pasta)
    parametros = parametros_do_job(dados_param)
    ds, lim = montar(pasta_laudo, laudo, estrutura, conferencia, parametros,
                     sha_conferencia=_sha(pasta / ARQUIVO_CONFERENCIA), sha_parametros=_sha(pasta / ARQUIVO_PARAMETROS),
                     sha_laudo=_sha(caminho_laudo), sha_estrutura=_sha(caminho_estrutura))
    (pasta / 'ds').mkdir(exist_ok=True)
    contratos.gravar(pasta / ARQUIVO_DS, ds, ESQUEMA_DS)
    contratos.gravar(pasta / ARQUIVO_LIMITES, lim, ESQUEMA_LIMITES)
    return ds, lim


def _montar(args):
    pasta = Path(args.pasta_job).resolve() if args.pasta_job else None
    if pasta is None:
        return Resultado(comando='ds montar', codigo=int(Codigo.USO), situacao='erro',
                         o_que_fazer='Falta a pasta do job.')
    try:
        ds, lim = executar_montar(pasta)
    except ErroDs as e:
        return Resultado(comando='ds montar', fase='ds', codigo=int(e.codigo), situacao='recusado',
                         o_que_fazer=e.o_que_fazer, pasta_job=pasta, linhas_humanas=[str(e)])
    except mod_cor.ErroAuditoriaCor as e:
        return Resultado(comando='ds montar', fase='ds', codigo=int(Codigo.AUDITORIA), situacao='recusado',
                         o_que_fazer='O processo da conversão de cor tentou uma ação que o desdobra não permite e foi '
                                     'parado. Não peça a fase de novo: mande o código para o suporte.',
                         pasta_job=pasta, linhas_humanas=[str(e)])
    except (contratos.ErroContrato, mod_cor.ErroCor) as e:
        return Resultado(comando='ds montar', fase='ds', codigo=int(Codigo.RECUSADO), situacao='recusado',
                         o_que_fazer='Um arquivo do job não segue o contrato. Peça ao Claude para seguir o job '
                                     '(/desdobra:continuar), que refaz a fase que grava esse arquivo.',
                         pasta_job=pasta, linhas_humanas=[str(e)])
    r = ds['resumo']
    codigos = {p['codigo'] for p in ds['pendencias']}
    o_que_fazer = O_QUE_FAZER_OK
    situacao = 'ok'
    if 'cores_nao_convertidas' in codigos and ds['documento']['perfil']['tratamento'] == mod_cor.TRATAMENTO_INDISPONIVEL:
        o_que_fazer += O_QUE_FAZER_PERFIL
        situacao = 'ok_com_bloqueio'
    elif 'cores_nao_convertidas' in codigos:
        o_que_fazer += ' As cores não foram convertidas para sRGB: veja ds/design-system.json, pendências.'
        situacao = 'ok_com_bloqueio'
    if mod_tokens.SITUACAO_FONTES_NAO_CONFERIDAS in codigos:
        o_que_fazer += O_QUE_FAZER_FONTES
    if r['n_sujeito_pedir_ao_da']:
        o_que_fazer += O_QUE_FAZER_SUJEITO % r['n_sujeito_pedir_ao_da']
    contagens = {'cores': r['n_cores'], 'cores_convertidas': r['n_cores_convertidas'],
                 'tipografia': r['n_tipografia'], 'tipografia_com_metricas': r['n_tipografia_com_metricas'],
                 'medidas': r['n_medidas'], 'sujeito_alfa': r['n_sujeito_alfa'],
                 'sujeito_pedir_ao_da': r['n_sujeito_pedir_ao_da'],
                 'assets_perfil_convertido': r['n_assets_perfil_convertido'], 'limites': len(lim['limites']),
                 'pendencias': len(ds['pendencias'])}
    linhas = ['Design system gravado em %s' % (pasta / ARQUIVO_DS), 'Limites do job em %s' % (pasta / ARQUIVO_LIMITES),
              'Perfil do documento: %s (%s)' % (ds['documento']['perfil']['nome'], ds['documento']['perfil']['tratamento']),
              'Intent: %s' % ds['cor']['parametros']['intent']['valor']]
    linhas += ['Pendência: %s' % p['descricao'] for p in ds['pendencias']]
    return Resultado(comando='ds montar', fase='ds', situacao=situacao, o_que_fazer=o_que_fazer, contagens=contagens,
                     ids={'arquivo_sha256': ds['origem']['arquivo_sha256']}, pasta_job=pasta, linhas_humanas=linhas)


def _sim_nao(v):
    return None if v is None else v == 'sim'


def _parametros_cor(args):
    from desdobra.job import nucleo
    pasta = Path(args.pasta_job).resolve() if args.pasta_job else None
    if pasta is None:
        return Resultado(comando='ds parametros-cor', codigo=int(Codigo.USO), situacao='erro',
                         o_que_fazer='Falta a pasta do job.')
    novos = {'intent': args.intent, 'compensacao_ponto_preto': _sim_nao(args.compensacao_ponto_preto),
             'perfil_embutido_na_saida': _sim_nao(args.perfil_embutido)}
    try:
        with nucleo.Trava(pasta):
            atual = ler_parametros(pasta) or {}
            dados = {'esquema': ESQUEMA_PARAMETROS}
            for k in ('intent', 'compensacao_ponto_preto', 'perfil_embutido_na_saida'):
                v = novos[k] if novos[k] is not None else atual.get(k)
                if v is not None:
                    dados[k] = v
            if any(v is not None for v in novos.values()):
                (pasta / ARQUIVO_PARAMETROS.parent).mkdir(exist_ok=True)
                contratos.gravar(pasta / ARQUIVO_PARAMETROS, dados, ESQUEMA_PARAMETROS)
                nucleo.registrar_evento(pasta, 'parametros_cor_gravados', n=len(dados) - 1)
    except nucleo.ErroJob as e:
        return Resultado(comando='ds parametros-cor', codigo=int(e.codigo), situacao=e.situacao,
                         o_que_fazer=e.o_que_fazer, linhas_humanas=[str(e)])
    except contratos.ErroContrato as e:
        return Resultado(comando='ds parametros-cor', codigo=int(Codigo.RECUSADO), situacao='recusado',
                         o_que_fazer='parametros/cor.json não segue o contrato: apague o arquivo e grave os '
                                     'parâmetros de novo.', pasta_job=pasta, linhas_humanas=[str(e)])
    p = parametros_do_job(dados).para_json()
    linhas = ['%s = %s (%s)' % (k, p[k]['valor'], 'do job' if p[k]['origem'] == 'job' else 'padrão do registro, a calibrar')
              for k in ('intent', 'compensacao_ponto_preto', 'perfil_embutido_na_saida')]
    return Resultado(comando='ds parametros-cor', situacao='ok', pasta_job=pasta,
                     o_que_fazer='Parâmetros de cor do job gravados em parametros/cor.json. A fase ds roda de novo quando '
                                 'o Claude seguir o job (/desdobra:continuar).',
                     contagens={'parametros_do_job': len(dados) - 1}, linhas_humanas=linhas)


def registrar(subparsers):
    p = subparsers.add_parser('ds', help='Design system da peça e limites do job')
    sub = p.add_subparsers(dest='acao_ds', metavar='ACAO', required=True)
    m = sub.add_parser('montar', help='Monta ds/design-system.json e ds/limites.json a partir do laudo e das fontes')
    m.add_argument('--job', dest='pasta_job', required=True, help='Pasta do job')
    # opcoes que o job proxima repassa a toda fase do motor; o ds nao le PSD e nao usa as duas
    m.add_argument('--teto-memoria-bytes', type=int, default=None, help=argparse_suprimido())
    m.add_argument('--tempo-max-s', type=float, default=None, help=argparse_suprimido())
    m.set_defaults(executar=_montar, nome_comando='ds montar')
    c = sub.add_parser('parametros-cor', help='Grava o intent e a saída de cor do job (parametros/cor.json)')
    c.add_argument('--job', dest='pasta_job', required=True, help='Pasta do job')
    c.add_argument('--intent', choices=tuple(mod_cor.INTENTS), default=None, help='Intent da conversão para sRGB')
    c.add_argument('--compensacao-ponto-preto', choices=mod_cor.SIM_NAO, default=None,
                   help='Compensação de ponto preto na conversão')
    c.add_argument('--perfil-embutido', choices=mod_cor.SIM_NAO, default=None,
                   help='A saída leva o perfil sRGB embutido (sim) ou sai sem perfil (nao)')
    c.set_defaults(executar=_parametros_cor, nome_comando='ds parametros-cor')


def argparse_suprimido():
    import argparse
    return argparse.SUPPRESS
