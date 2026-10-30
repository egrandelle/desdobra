# -*- coding: utf-8 -*-
"""Regras do laudo: B1 a B3 (bloqueante) e D1 a D8 (degradada), portadas da sonda da pesquisa.

A regra D9 da sonda foi aposentada: o defeito do pass-through que ela marcava foi corrigido no psd-tools
1.19 e a 1.26.0 adotada nao o tem (pesquisa/render-local-pesquisa.md, 9). As opcoes de mesclagem clbl e infx
e os efeitos legados lrFX, que a sonda juntava na D9, viram alertas da camada, sem mudar a situacao.

Cada regra mede o efeito antes de degradar (pesquisa/corpus-testes.md, 4, item 6):
  - traco vetorial de largura 0 e efeito com tamanho ou opacidade 0 nao desenham nada;
  - malha de deformacao igual a grade identidade nao deforma;
  - warp com curvatura e perspectivas 0 nao deforma;
  - fonte ausente usada so em espaco ou caractere de controle nao deixa marca;
  - recurso de texto (faux, escala, deslocamento) so conta em trecho com tinta.
"""
from desdobra import limites

FONTE_SINTESE = {'arquivo': 'pesquisa/v1-estatico-sintese.md', 'secao': '3'}
FONTE_LINKADO = {'arquivo': 'pesquisa/render-local-pesquisa.md', 'secao': '2'}
FONTE_FONTES = {'arquivo': 'pesquisa/corpus-testes.md', 'secao': '4, itens 6 e 8'}
FONTE_FALSO_POSITIVO = {'arquivo': 'pesquisa/corpus-testes.md', 'secao': '4, item 6'}

REGRAS = {
    'B1': {'descricao': 'Smart object linkado ou externo: o arquivo não está no PSD e o caminho gravado nunca é seguido.',
           'situacao': 'bloqueante', 'fonte': FONTE_LINKADO},
    'B2': {'descricao': 'Erro ao ler os pixels ou os dados da camada.', 'situacao': 'bloqueante', 'fonte': FONTE_SINTESE},
    'B3': {'descricao': 'Camada de texto com fonte ausente num trecho com tinta: o texto não pode ser refeito.',
           'situacao': 'bloqueante', 'fonte': FONTE_FONTES},
    'D1': {'descricao': 'Efeito ativo que o psd-tools 1.26.0 não desenha, ou que exige pacote ausente.',
           'situacao': 'degradada', 'fonte': FONTE_SINTESE},
    'D2': {'descricao': 'Ajuste que não entra no composto do psd-tools 1.26.0.', 'situacao': 'degradada',
           'fonte': FONTE_SINTESE},
    'D3': {'descricao': 'Mesclagem dissolve, que o psd-tools desenha como normal.', 'situacao': 'degradada',
           'fonte': FONTE_SINTESE},
    'D4': {'descricao': 'Máscara com feather (desfoque da borda), que o psd-tools não aplica.', 'situacao': 'degradada',
           'fonte': FONTE_SINTESE},
    'D5': {'descricao': 'Traço vetorial de forma que exige o aggdraw, ausente.', 'situacao': 'degradada',
           'fonte': FONTE_SINTESE},
    'D6': {'descricao': 'Warp ou transformação não afim que deforma de fato a camada.', 'situacao': 'degradada',
           'fonte': FONTE_SINTESE},
    'D7': {'descricao': 'Recurso de texto sem mapeamento: faux bold, faux itálico, deslocamento da linha de base ou '
                         'escala horizontal ou vertical diferente de 100%.', 'situacao': 'degradada', 'fonte': FONTE_SINTESE},
    'D8': {'descricao': 'Camada visível dentro de grupo oculto: a visibilidade própria diz sim e a efetiva diz não.',
           'situacao': 'degradada', 'fonte': FONTE_SINTESE},
}


def motivo(regra, descricao, medida=None, limite_id=None):
    return {'regra': regra, 'descricao': descricao, 'medida': medida,
            'limite': limites.obter(limite_id).citacao() if limite_id else None, 'fonte': REGRAS[regra]['fonte']}


def _warp_tem_efeito(estilo, valores):
    if estilo in (None, 'warpNone'):
        return False
    return any(v not in (0, 0.0, None) for v in valores)


def avaliar(reg, pacotes, fontes_status=None):
    """Lista de motivos de uma camada da estrutura/1. fontes_status: {fonte_ps: 'presente'|'ausente'} ou None
    (no M1 a conferencia das faces instaladas nao existe, e a B3 nao dispara)."""
    mot = []
    so = reg.get('smart_object')
    px = reg.get('pixels') or {}
    if so is not None:
        if so.get('tipo') == 'erro':
            mot.append(motivo('B2', 'Erro ao ler o registro do smart object.', {'erro': so.get('erro')}))
        elif not so.get('embutido'):
            mot.append(motivo('B1', 'Smart object %s: só o registro (nome, tamanho e data) foi lido.' % so.get('tipo'),
                              {'tipo': so.get('tipo'), 'linkado': so.get('linkado')}))
    if reg.get('erro_camada'):
        mot.append(motivo('B2', 'Erro ao ler a camada.', {'erro': reg['erro_camada']}))
    if px.get('erro'):
        mot.append(motivo('B2', 'Erro ao ler os pixels da camada.', {'erro': px['erro']}))
    elif px.get('pulado'):
        # a passada de pixels da camada passou do orcamento: sem pixels, sem miniatura, asset nem cobertura
        mot.append(motivo('B2', 'Os pixels da camada não foram lidos: a passada de pixels passou do orçamento.',
                          {'pulado': px['pulado']}))
    tx = reg.get('texto')
    if tx and fontes_status:
        ausentes = sorted({r['fonte_ps'] for r in tx['runs'] if r.get('tem_tinta') and r.get('fonte_ps')
                           and fontes_status.get(r['fonte_ps']) == 'ausente'})
        if ausentes:
            mot.append(motivo('B3', 'Fonte ausente em trecho com tinta.', {'fontes_ps': ausentes}))
    for e in reg.get('efeitos') or []:
        if not e.get('ativo') or e.get('desenhado_pelo_render'):
            continue
        med = e.get('medidas') or {}
        if med.get('opacity') in (0, 0.0):
            continue
        if e['tipo'] == 'Stroke' and med.get('size') in (0, 0.0):
            continue
        texto = 'exige %s, ausente' % e['requer_pacote_ausente'] if e.get('requer_pacote_ausente') else \
            'não desenhado pelo psd-tools 1.26.0'
        mot.append(motivo('D1', 'Efeito %s ativo: %s.' % (e['tipo'], texto), {'tipo': e['tipo'], **med}))
    if reg.get('efeitos_ilegiveis'):
        mot.append(motivo('D1', 'Efeitos que o psd-tools não consegue ler.', {'erro': reg['efeitos_ilegiveis']}))
    aj = reg.get('ajuste')
    if aj and not aj.get('entra_no_composto'):
        mot.append(motivo('D2', 'Ajuste %s fora do composto (%s).' % (aj['tipo'], aj.get('motivo') or 'sem motivo'),
                          {'tipo': aj['tipo']}))
    if reg.get('blend') == 'DISSOLVE':
        mot.append(motivo('D3', 'Mesclagem dissolve.', {'blend': 'DISSOLVE'}))
    mk = reg.get('mascara') or {}
    if mk.get('raster') and not mk.get('desativada') and (mk.get('feather_usuario') or 0) > 0:
        mot.append(motivo('D4', 'Feather da máscara raster.', {'feather_px': mk['feather_usuario']}))
    if mk.get('vetorial') and not mk.get('vetorial_desativada') and (mk.get('feather_vetorial') or 0) > 0:
        mot.append(motivo('D4', 'Feather da máscara vetorial.', {'feather_px': mk['feather_vetorial']}))
    med = reg.get('medidas_regras') or {}
    tf = med.get('traco_forma')
    if tf and tf.get('ativo') and (tf.get('largura') or 0) > 0 and not pacotes.get('aggdraw', False):
        mot.append(motivo('D5', 'Traço vetorial de forma com largura acima de 0 e aggdraw ausente.',
                          {'largura': tf.get('largura')}))
    if tx and tx.get('warp'):
        w = tx['warp']
        if _warp_tem_efeito(w.get('estilo'), (w.get('valor'), w.get('perspectiva'), w.get('perspectiva_outra'))):
            mot.append(motivo('D6', 'Texto com warp %s.' % w.get('estilo'), dict(w)))
    if so is not None:
        ms = so.get('medidas') or {}
        motivos_w, medida = [], {}
        estilo = ms.get('warp_estilo')
        if ms.get('malha_custom') or estilo == 'warpCustom':
            desvio = ms.get('malha_desvio_max_px')
            medida['malha_desvio_max_px'] = desvio
            if desvio is None or desvio > limites.valor('laudo.tolerancia_malha_px'):
                motivos_w.append(('malha de deformação diferente da identidade', 'laudo.tolerancia_malha_px'))
        elif _warp_tem_efeito(estilo, ms.get('warp_valores') or (None,)) or (
                estilo not in (None, 'warpNone') and ms.get('warp_valores') is None):
            medida['warp_estilo'] = estilo
            motivos_w.append(('warp %s' % estilo, None))
        dif = ms.get('nao_afim_diferenca_max_px')
        if dif is not None and dif > limites.valor('laudo.tolerancia_nao_afim_px'):
            medida['nao_afim_diferenca_max_px'] = dif
            motivos_w.append(('transformação não afim', 'laudo.tolerancia_nao_afim_px'))
        res = ms.get('residuo_paralelogramo_px')
        if res is not None and res > limites.valor('laudo.tolerancia_paralelogramo_px'):
            medida['residuo_paralelogramo_px'] = res
            motivos_w.append(('quadrilátero colocado que não é paralelogramo', 'laudo.tolerancia_paralelogramo_px'))
        for texto, lid in motivos_w:
            mot.append(motivo('D6', 'Smart object: %s.' % texto, medida, lid))
    if tx:
        tol = limites.valor('laudo.tolerancia_escala_texto')
        feats = {}
        for r in tx['runs']:
            if not r.get('tem_tinta'):
                continue
            if r.get('faux_bold'):
                feats['faux_bold'] = True
            if r.get('faux_italic'):
                feats['faux_italico'] = True
            if r.get('baseline_shift') not in (0, 0.0, None):
                feats['deslocamento_linha_base'] = r['baseline_shift']
            for chave in ('escala_h', 'escala_v'):
                if r.get(chave) is not None and abs(r[chave] - 1.0) > tol:
                    feats[chave] = r[chave]
        if feats:
            mot.append(motivo('D7', 'Recurso de texto sem mapeamento: %s.' % ', '.join(sorted(feats)), feats,
                              'laudo.tolerancia_escala_texto' if ('escala_h' in feats or 'escala_v' in feats) else None))
    if reg.get('visivel_propria') and not reg.get('visivel_efetiva'):
        mot.append(motivo('D8', 'Visível dentro de grupo oculto.', {'visivel_propria': True, 'visivel_efetiva': False}))
    return mot


def situacao(motivos):
    if any(m['regra'].startswith('B') for m in motivos):
        return 'bloqueante'
    if motivos:
        return 'degradada'
    return 'lida'
