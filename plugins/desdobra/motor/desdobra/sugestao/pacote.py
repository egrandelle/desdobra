# -*- coding: utf-8 -*-
"""Rascunho do pacote para o modelo (sugestoes/pacote-modelo.json, contrato pacote-modelo/1).

arquitetura-v1.md, 4.9 e 7.4. O pacote e o que o Claude pode ler para sugerir funcoes, conforme o modo de
dados do job:

  modo a: metadados e textos das camadas e, a partir do M7, miniaturas so de camadas sem texto. No M1 o
          pacote nao leva miniatura nenhuma (exposto.miniaturas = false);
  modo b: metadados e textos das camadas, depois do detector de segredos;
  modo c: so contagens, estados, ids e numeros do motor. Nenhum nome, texto ou caminho.

Camada com segredo fica no pacote so com layer_id, pai_id, tipo, situacao e regras, marcada com
segredo_bloqueado; nome e textos nunca entram. O detalhe vai para sugestoes/segredos-bloqueados.json.

Tambem daqui: conteudo_para_resultado(laudo), que monta o Resultado.conteudo que o envelope filtra.
"""
from pathlib import Path

from desdobra import contratos
from desdobra.resultado import modo_mais_fechado
from desdobra.sugestao import segredos

CONTRATO = 'pacote-modelo/1'
ARQUIVO_PACOTE = Path('sugestoes') / 'pacote-modelo.json'


def textos_da_camada(camada):
    """Os textos de uma camada do laudo/1: o conteudo do texto ou, sem ele, o texto de cada trecho."""
    texto = camada.get('texto') or None
    if not isinstance(texto, dict):
        return []
    if isinstance(texto.get('conteudo'), str) and texto['conteudo']:
        return [texto['conteudo']]
    return [r['texto'] for r in texto.get('runs') or [] if isinstance(r, dict) and isinstance(r.get('texto'), str)]


def _layer_id(camada):
    ident = camada.get('identidade') or {}
    return ident.get('layer_id', camada.get('layer_id'))


def conteudo_para_resultado(laudo):
    """Resultado.conteudo de um laudo/1: camadas com layer_id, nome, tipo, situacao e textos (o envelope filtra)."""
    camadas = []
    for c in laudo.get('camadas') or []:
        camadas.append({'layer_id': _layer_id(c), 'nome': c.get('nome', ''), 'tipo': c.get('tipo'),
                        'situacao': c.get('situacao'), 'textos': textos_da_camada(c)})
    return {'camadas': camadas}


def _regras(camada):
    return sorted({m.get('regra') for m in camada.get('motivos') or [] if isinstance(m, dict) and m.get('regra')})


def _coberta(camada):
    cob = (camada.get('geometria') or {}).get('coberta_no_kv')
    if not isinstance(cob, dict):
        return None
    sugestao = cob.get('sugestao_da_regra') or None
    return {'coberta': bool(cob.get('coberta')), 'ocupa_canvas': bool(cob.get('ocupa_canvas')),
            'sugestao_da_regra': None if not sugestao else {'funcao': sugestao.get('funcao'),
                                                             'regra': sugestao.get('regra')}}


def montar_pacote(laudo, modo, *, job_id=None, detector=None):
    """Devolve (pacote, achados). O pacote vale contra pacote-modelo/1."""
    detector = detector or segredos.detector_padrao()
    abre_conteudo = modo in ('a', 'b')
    achados = []
    camadas = []
    por_situacao = {'lida': 0, 'degradada': 0, 'bloqueante': 0}
    for c in laudo.get('camadas') or []:
        lid = _layer_id(c)
        situacao = c.get('situacao')
        if situacao in por_situacao:
            por_situacao[situacao] += 1
        item = {'layer_id': lid, 'pai_id': c.get('pai_id'), 'tipo': c.get('tipo'), 'situacao': situacao,
                'regras': _regras(c)}
        nome, textos = c.get('nome', ''), textos_da_camada(c)
        achado = detector.achado_em('camada', lid, {'nome': nome, 'textos': textos})
        if achado is not None:
            achados.append(achado)
            item['segredo_bloqueado'] = True
        elif abre_conteudo:
            geo = c.get('geometria') or {}
            item.update({'nome': nome, 'textos': textos,
                         'visivel': bool((c.get('aparencia') or {}).get('visivel_efetiva')),
                         'caixa': geo.get('caixa'), 'quadro': c.get('quadro'), 'coberta_no_kv': _coberta(c)})
        camadas.append(item)

    doc = laudo.get('documento') or {}
    quadros = doc.get('quadros') or []
    pacote = {
        'esquema': CONTRATO,
        'modo_dados': modo,
        'job_id': job_id,
        'arquivo_sha256': (laudo.get('origem') or {}).get('sha256'),
        'exposto': {'metadados': abre_conteudo, 'textos': abre_conteudo, 'miniaturas': False},
        'nota': 'Rascunho do M1: sem miniaturas. A sugestão de função entra no M7.',
        'documento': {'largura': doc.get('largura'), 'altura': doc.get('altura'),
                      'n_camadas': len(camadas), 'n_quadros': len(quadros)},
        'contagens': dict(por_situacao, segredos_bloqueados=len(achados)),
        'camadas': camadas,
        'miniaturas': [],
    }
    if abre_conteudo:
        pacote['documento']['quadros'] = [{'id': q.get('id'), 'layer_id': q.get('layer_id'), 'caixa': q.get('caixa'),
                                           'visivel_ao_salvar': q.get('visivel_ao_salvar')} for q in quadros]
        fontes = []
        for f in laudo.get('fontes_usadas') or []:
            nome = f.get('fonte_ps')
            achado = detector.achado_em('fonte', None, {'fonte_ps': nome})
            if achado is not None:
                achados.append(achado)
                continue
            fontes.append({'fonte_ps': nome, 'camadas': list(f.get('camadas') or [])})
        pacote['fontes_usadas'] = fontes
        pacote['contagens']['segredos_bloqueados'] = len(achados)
    contratos.validar(pacote, CONTRATO)
    return pacote, achados


def modo_do_job(estado):
    return modo_mais_fechado(estado.get('modo_dados') or 'c', estado.get('teto_modo_dados'))


def gravar_pacote(pasta_job, *, detector=None):
    """Le estado.json e laudo/laudo.json do job, grava sugestoes/pacote-modelo.json e, se houver achado,
    sugestoes/segredos-bloqueados.json. Devolve (caminho do pacote, numero de achados)."""
    pasta_job = Path(pasta_job)
    estado = contratos.ler(pasta_job / 'estado.json', 'estado/1')
    laudo = contratos.ler(pasta_job / 'laudo' / 'laudo.json', 'laudo/1')
    pacote, achados = montar_pacote(laudo, modo_do_job(estado), job_id=estado.get('job_id'), detector=detector)
    destino = pasta_job / ARQUIVO_PACOTE
    contratos.gravar(destino, pacote, CONTRATO)
    segredos.gravar_bloqueios(pasta_job, achados, comando='pacote')
    return destino, len(achados)
