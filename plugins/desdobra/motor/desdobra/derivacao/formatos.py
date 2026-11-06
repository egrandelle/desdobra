# -*- coding: utf-8 -*-
"""Formatos do briefing com o que a folha diz deles, a base do calculo e a familia de cada formato.

Da folha (specs/formatos-do-job.json, ou o rascunho enquanto o DA nao confirmou) vem a area util, as faixas
reservadas e a area segura, cada uma com a fonte (folha e trecho) e a situacao (rascunho ou confirmado). Elas viram
restricoes obrigatorias com fonte (arquitetura-v1.md, 4.10).

Base do calculo (arquitetura-v1.md, 10.2, pergunta 7): arquivo (largura e altura do arquivo, na orientacao da composicao), composicao (a peca como
o publico ve, girada quando o formato tem rotacao de 90 ou 270 graus) ou area_util (a area util da folha, na
composicao). A faixa de familia, a base e o numero de mestres sao parametros do job: valem, nesta ordem, a decisao do
briefing, parametros/derivacao.json e a proposta citada do registro de limites.
"""
from pathlib import Path

from desdobra import arquivos, limites
from desdobra.briefing import modelo as mb
from desdobra.derivacao import escala

ARQUIVO_PARAMETROS = Path('parametros') / 'derivacao.json'
BASES = ('arquivo', 'composicao', 'area_util')
PARAMETROS = (('faixa', 'derivacao.faixa_familia_razao_max'), ('base', 'derivacao.base_calculo'),
              ('mestres_max', 'derivacao.mestres_max'))
# os campos da folha que a derivacao le (nucleo e areas): o formato com um deles em rascunho espera o DA
CAMPOS_DO_LAYOUT = ('dimensao', 'faixas', 'area_util', 'area_segura')


class ErroFormatos(Exception):
    pass


def parametros(pasta, briefing):
    """{nome: {'valor', 'origem'}} da faixa, da base e do numero de mestres."""
    arq = Path(pasta) / ARQUIVO_PARAMETROS if pasta is not None else None
    do_job = arquivos.ler_json(arq) if arq is not None and arq.is_file() else {}
    saida = {}
    for nome, lid in PARAMETROS:
        d = (briefing.get('familias') or {}).get(nome)
        if d is not None and d.get('situacao') == 'confirmado' and d.get('valor') is not None:
            saida[nome] = {'valor': d['valor'], 'origem': {'tipo': 'briefing', 'origem': d['origem']}}
        elif nome in do_job:
            saida[nome] = {'valor': do_job[nome], 'origem': {'tipo': 'parametro_do_job', 'arquivo': ARQUIVO_PARAMETROS.as_posix()}}
        else:
            saida[nome] = {'valor': limites.valor(lid), 'origem': {'tipo': 'proposta', 'limite': limites.obter(lid).citacao()}}
    if saida['base']['valor'] not in BASES:
        raise ErroFormatos('Base do cálculo desconhecida: %r.' % saida['base']['valor'])
    return saida


def specs_do_job(pasta):
    """{chave: formato da folha} do arquivo de specs que vale (formatos do job ou rascunho), e o arquivo."""
    rel = mb.arquivo_de_specs(pasta)
    arq = Path(pasta) / rel
    if not arq.is_file():
        return {}, None
    dados = arquivos.ler_json(arq)
    return {f['chave']: f for f in dados.get('formatos') or [] if f.get('chave')}, rel.as_posix()


def _valor_do_layout(doc, fmt, campo):
    """O valor do campo no formato do rascunho das specs, ou o herdado do circuito ou do veiculador (a heranca de
    specs.modelo.resolver, lida com get: o rascunho pode vir sem os niveis). O campo com fontes divergentes (sem valor,
    com leituras) conta como do proprio formato. None sem valor."""
    from desdobra.specs import modelo as ms
    v = (fmt.get('campos') or {}).get(campo)
    if isinstance(v, dict) and (v.get('valor') is not None or v.get('leituras')):
        return v
    if campo not in ms.HERANCA:
        return None
    nivel, campo_pai = ms.HERANCA[campo]
    pai_id = fmt.get('circuito' if nivel == 'circuito' else 'veiculador')
    for r in doc.get('circuitos' if nivel == 'circuito' else 'veiculadores') or []:
        if isinstance(r, dict) and r.get('id') == pai_id:
            vp = (r.get('campos') or {}).get(campo_pai)
            return vp if isinstance(vp, dict) and (vp.get('valor') is not None or vp.get('leituras')) else None
    return None


def chaves_por_confirmar(pasta):
    """As chaves da folha cuja spec ainda espera a confirmacao do DA: no rascunho das specs, um campo que a derivacao
    le (CAMPOS_DO_LAYOUT, do proprio formato ou herdado) esta em rascunho. Vale com qualquer arquivo de specs
    (specs_do_job): antes da primeira confirmacao o rascunho e o arquivo que vale, e depois os formatos do job deixam
    de fora o campo sem confirmacao. O formato dessas chaves nunca deriva do valor sem confirmacao como se fosse
    confirmado, nem sem ele (revisao dos becos, A1). Vazio sem job ou sem rascunho legivel."""
    if pasta is None:
        return set()
    arq = Path(pasta) / mb.ARQUIVO_RASCUNHO_SPECS
    try:
        dados = arquivos.ler_json(arq) if arq.is_file() else {}
    except (OSError, ValueError):
        dados = {}
    saida = set()
    for f in (dados or {}).get('formatos') or []:
        if not isinstance(f, dict) or not f.get('chave'):
            continue
        if any((_valor_do_layout(dados, f, c) or {}).get('situacao') == 'rascunho' for c in CAMPOS_DO_LAYOUT):
            saida.add(f['chave'])
    return saida


def _campo(spec, nome):
    c = ((spec or {}).get('campos') or {}).get(nome)
    if not isinstance(c, dict) or c.get('valor') is None:
        return None
    return c


def _fonte(campo, arquivo_specs):
    f = campo.get('fonte') or {}
    return {'tipo': 'folha', 'arquivo_specs': arquivo_specs, 'folha': f.get('folha'), 'trecho': f.get('trecho'),
            'pagina': f.get('pagina'), 'situacao': campo.get('situacao'), 'campo_id': campo.get('id')}


def composicao(formato):
    """(largura, altura) da composicao: girada nos 90 e 270 graus."""
    w, h = int(formato['largura']), int(formato['altura'])
    graus = ((formato.get('rotacao') or {}).get('graus')) or 0
    return (h, w) if graus in (90, 270) else (w, h)  # numero-neutro: graus do giro de um quarto de volta


def areas(formato, spec, arquivo_specs):
    """Area util, faixas e area segura na composicao, cada uma com a fonte. Devolve
    {'area_util': {'caixa', 'fonte'} | None, 'faixas': [{'lado', 'px', 'caixa', 'fonte'}],
     'area_segura': {'caixa', 'lados', 'fonte'} | None, 'registros': [...]}."""
    W, H = composicao(formato)
    registros = []
    faixas = []
    c_fx = _campo(spec, 'faixas')
    util = [0.0, 0.0, float(W), float(H)]
    if c_fx:
        for fx in c_fx['valor']:
            px = float(fx.get('px') or 0)
            lado = fx.get('lado')
            caixa = {'inferior': [0.0, H - px, float(W), float(H)], 'superior': [0.0, 0.0, float(W), px],
                     'esquerda': [0.0, 0.0, px, float(H)], 'direita': [W - px, 0.0, float(W), float(H)]}.get(lado)
            if caixa is None:
                registros.append({'codigo': 'faixa_com_lado_desconhecido', 'medidas': {'lado': lado}})
                continue
            faixas.append({'lado': lado, 'px': px, 'caixa': caixa, 'fonte': _fonte(c_fx, arquivo_specs)})
            if lado == 'inferior':
                util[3] = min(util[3], H - px)
            elif lado == 'superior':
                util[1] = max(util[1], px)
            elif lado == 'esquerda':
                util[0] = max(util[0], px)
            else:
                util[2] = min(util[2], W - px)
    c_au = _campo(spec, 'area_util')
    area_util = None
    if c_au:
        aw, ah = float(c_au['valor'].get('largura') or 0), float(c_au['valor'].get('altura') or 0)
        if aw > W or ah > H or aw <= 0 or ah <= 0:
            registros.append({'codigo': 'area_util_fora_do_formato', 'medidas': {'largura': aw, 'altura': ah}})
        else:
            uw, uh = util[2] - util[0], util[3] - util[1]
            if abs(uw - aw) > limites.valor('derivacao.enquadramento_tolerancia_px') or \
                    abs(uh - ah) > limites.valor('derivacao.enquadramento_tolerancia_px'):
                # a folha da a area util sem dizer onde fica: centrada no que sobra das faixas, com registro
                cx, cy = (util[0] + util[2]) / 2.0, (util[1] + util[3]) / 2.0  # numero-neutro: centro
                util = [cx - aw / 2.0, cy - ah / 2.0, cx + aw / 2.0, cy + ah / 2.0]  # numero-neutro: metade
                registros.append({'codigo': 'area_util_centrada_sem_posicao_na_folha'})
            area_util = {'caixa': util, 'fonte': _fonte(c_au, arquivo_specs)}
    elif faixas:
        area_util = {'caixa': util, 'fonte': faixas[0]['fonte']}
    c_seg = _campo(spec, 'area_segura')
    segura = None
    if c_seg:
        v = c_seg['valor']
        lados = v.get('lados') or ['superior', 'inferior', 'esquerda', 'direita']
        caixa = [0.0, 0.0, float(W), float(H)]
        for lado in lados:
            dim = H if lado in ('superior', 'inferior') else W
            px = float(v['px']) if v.get('px') is not None else float(v.get('pct') or 0) / 100.0 * dim  # numero-neutro: porcentagem
            if lado == 'superior':
                caixa[1] = px
            elif lado == 'inferior':
                caixa[3] = H - px
            elif lado == 'esquerda':
                caixa[0] = px
            elif lado == 'direita':
                caixa[2] = W - px
        segura = {'caixa': caixa, 'lados': lados, 'fonte': _fonte(c_seg, arquivo_specs)}
    return {'area_util': area_util, 'faixas': faixas, 'area_segura': segura, 'registros': registros}


def base_do_formato(formato, info_areas, base):
    """(largura, altura) do formato na base do calculo."""
    W, H = composicao(formato)
    if base == 'arquivo':
        # o arquivo na orientacao da composicao: a familia e a troca de orientacao sao sempre da peca como o publico
        # ve (um arquivo deitado que gira 90 graus e um formato em pe)
        return float(W), float(H)
    if base == 'area_util' and info_areas.get('area_util'):
        c = info_areas['area_util']['caixa']
        if c[2] > c[0] and c[3] > c[1]:
            return c[2] - c[0], c[3] - c[1]
    return float(W), float(H)


def familia(base_mestre, base_formato, faixa):
    """{'orientacao_mestre', 'orientacao_formato', 'troca', 'fator', 'na_faixa'} do formato contra a mestre."""
    troca = escala.troca_de_orientacao(base_mestre, base_formato)
    fator = escala.fator_de_proporcao(base_mestre, base_formato)
    return {'orientacao_mestre': escala.orientacao(*base_mestre), 'orientacao_formato': escala.orientacao(*base_formato),
            'troca': troca, 'fator': round(fator, 6), 'na_faixa': troca is None and fator <= float(faixa)}
