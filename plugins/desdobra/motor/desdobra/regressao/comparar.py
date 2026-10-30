# -*- coding: utf-8 -*-
"""Comparador da regressao: linha de base (sonda 1.26.0) contra a leitura de agora, ja normalizadas.

Por arquivo:
  - situacao da execucao: ok na base e outra coisa agora e piora;
  - prova de pixel: a porcentagem de pixels acima do limiar nao pode subir; prova feita na base e nao feita
    agora tambem e piora (decisoes-v1.md, 29/10, respostas as perguntas da arquitetura, 3: a versao nova so
    entra se nada piorar; arquitetura-v1.md, 9.2, criterio de pronto);
  - tempo: registrado, nao decide nada.
Por camada, pela chave layer_id: situacao, tipo, caixa, visibilidade efetiva, texto e trechos de texto. Cada
diferenca sai ligada a uma causa registrada em CAUSAS, ou a "sem_causa", para o Duda aprovar. Camada que fica
mais grave (lida para degradada ou bloqueante, degradada para bloqueante) sem causa especifica e piora, e camada
que existe na linha de base e sumiu agora e piora com qualquer causa.

A prova de pixel compara as contagens inteiras de pixels quando os dois lados as tem. Contra a sonda, que grava
so a porcentagem com 4 casas, a porcentagem de agora e levada a mesma resolucao antes de comparar.

O comparador recebe so formas normalizadas (mapeamento.py) e nunca sabe de que formato veio cada lado.
O texto da camada entra na diferenca so como sha256 e tamanho: o relatorio nunca copia texto de peca.
"""
import hashlib

from desdobra import limites

CAMPOS_CAMADA = ('situacao', 'tipo', 'caixa', 'visivel', 'texto', 'texto_runs')
REGRA_APOSENTADA = 'D9'
GRAVIDADE = {'lida': 0, 'degradada': 1, 'bloqueante': 2}  # numero-neutro: ordem das situacoes, nao e limiar
CASAS_PCT_DA_SONDA = 4  # numero-neutro: a sonda grava a porcentagem com 4 casas decimais (formato da linha de base)
# causas que nao explicam uma camada que ficou mais grave
CAUSAS_GENERICAS = ('regra_do_laudo', 'sem_causa', 'mudanca_de_versao')

CAUSAS = {
    'd9_aposentada': {
        'descricao': 'A regra D9 da sonda foi aposentada no psd-tools 1.26.0, e a camada perdeu só esse motivo.',
        'fonte': {'arquivo': 'pesquisa/render-local-pesquisa.md', 'secao': '9'}},
    'b3_fontes_conferidas_no_m2': {
        'descricao': 'A sonda dava B3 (fonte ausente) olhando as fontes instaladas na máquina da pesquisa. No M1 o '
                     'laudo não confere as faces instaladas: a camada tem texto com tinta e o alerta '
                     'fonte_nao_conferida, e a conferência com licença entra no M2.',
        'fonte': {'arquivo': 'arquitetura-v1.md', 'secao': '9.3'}},
    'd6_falso_positivo_medido': {
        'descricao': 'A sonda dava D6 para uma malha de deformação igual à grade identidade (ou warp sem curvatura). '
                     'O laudo mede o desvio antes de degradar, e ele fica abaixo de laudo.tolerancia_malha_px.',
        'fonte': {'arquivo': 'pesquisa/corpus-testes.md', 'secao': '4, item 6'}},
    'regra_do_laudo': {
        'descricao': 'As regras que o laudo aplicou à camada mudaram (veja regras_so_na_base e regras_so_agora).',
        'fonte': {'arquivo': 'arquitetura-v1.md', 'secao': '4.4'}},
    'mudanca_de_versao': {
        'descricao': 'A versão do psd-tools da leitura de agora é outra que a da linha de base.',
        'fonte': {'arquivo': 'decisoes-v1.md', 'secao': '29/10, respostas às perguntas da arquitetura, 3'}},
    'sem_causa': {
        'descricao': 'Diferença sem causa registrada. Precisa de explicação e da aprovação do Duda.',
        'fonte': {'arquivo': 'arquitetura-v1.md', 'secao': '9.2'}},
}


# regra que a sonda aplicava -> [(causa, evidencias do laudo de agora que a explicam)]
EXPLICACAO_POR_REGRA = {
    'B3': (('b3_fontes_conferidas_no_m2', {'fonte_nao_conferida_com_tinta'}),),
    'D6': (('d6_falso_positivo_medido', {'malha_identidade', 'warp_sem_efeito'}),),
}


def _resumo_texto(texto):
    if texto is None:
        return None
    return {'sha256': hashlib.sha256(texto.encode('utf-8')).hexdigest(), 'tamanho': len(texto)}


def _valor_no_relatorio(campo, valor):
    return _resumo_texto(valor) if campo == 'texto' else valor


def causa_da_situacao(base, agora):
    """Causa de uma diferenca de situacao: (causa, detalhe).

    Quando so sairam regras e cada uma tem explicacao (a D9 aposentada, ou um fato medido do laudo de agora em
    EXPLICACAO_POR_REGRA), a causa e a especifica; com mais de uma regra explicada, vale a primeira pela ordem
    de CAUSAS. Outra mudanca de regras fica como regra_do_laudo."""
    rb, ra = set(base.get('regras') or []), set(agora.get('regras') or [])
    detalhe = {'regras_so_na_base': sorted(rb - ra), 'regras_so_agora': sorted(ra - rb)}
    evidencias = set(agora.get('evidencias') or [])
    if evidencias:
        detalhe['evidencias'] = sorted(evidencias)
    if rb == ra:
        return 'sem_causa', detalhe
    if not ra - rb:
        causas = []
        for regra in sorted(rb - ra):
            if regra == REGRA_APOSENTADA:
                causas.append('d9_aposentada')
                continue
            explicada = next((c for c, evs in EXPLICACAO_POR_REGRA.get(regra, ()) if evs & evidencias), None)
            if explicada is None:
                return 'regra_do_laudo', detalhe
            causas.append(explicada)
        return min(causas, key=list(CAUSAS).index), detalhe
    return 'regra_do_laudo', detalhe


def comparar_camadas(base, agora, *, versao_mudou=False):
    """Lista de diferencas por camada. base e agora sao {layer_id: camada normalizada}."""
    diferencas = []
    for lid in sorted(set(base) | set(agora)):
        cb, ca = base.get(lid), agora.get(lid)
        if cb is None or ca is None:
            diferencas.append({'layer_id': lid, 'campo': 'existencia', 'base': cb is not None, 'agora': ca is not None,
                               'causa': 'mudanca_de_versao' if versao_mudou else 'sem_causa', 'detalhe': None})
            continue
        for campo in CAMPOS_CAMADA:
            if cb.get(campo) == ca.get(campo):
                continue
            causa, detalhe = ('sem_causa', None)
            if campo == 'situacao':
                causa, detalhe = causa_da_situacao(cb, ca)
            if causa == 'sem_causa' and versao_mudou:
                causa = 'mudanca_de_versao'
            diferencas.append({'layer_id': lid, 'campo': campo, 'base': _valor_no_relatorio(campo, cb.get(campo)),
                               'agora': _valor_no_relatorio(campo, ca.get(campo)), 'causa': causa, 'detalhe': detalhe})
    return diferencas


def comparar_execucao(base, agora):
    sb, sa = base['execucao']['situacao'], agora['execucao']['situacao']
    if sb == sa:
        resultado = 'igual'
    elif sb == 'ok':
        resultado = 'piorou'
    elif sa == 'ok':
        resultado = 'melhorou'
    else:
        resultado = 'mudou'
    return {'base': sb, 'agora': sa, 'motivo_agora': agora['execucao'].get('motivo'), 'resultado': resultado}


def _medidas_comparaveis(pb, pa):
    """(base, agora, tolerancia) na mesma resolucao: contagens inteiras quando os dois lados as tem para o mesmo
    canvas; senao porcentagens, com a de agora arredondada as casas da linha de base."""
    tolerancia = limites.valor('regressao.tolerancia_prova_pixel_pct')
    if (isinstance(pb.get('px_acima'), int) and isinstance(pa.get('px_acima'), int) and pb.get('px_total')
            and pb.get('px_total') == pa.get('px_total')):
        return pb['px_acima'], pa['px_acima'], tolerancia * pb['px_total'] / 100  # numero-neutro: pontos percentuais para pixels
    casas = None if isinstance(pb.get('px_acima'), int) else CASAS_PCT_DA_SONDA
    agora = round(pa['pct'], casas) if casas is not None else pa['pct']
    return pb['pct'], agora, tolerancia


def comparar_prova_pixel(base, agora):
    pb, pa = base['prova_pixel'], agora['prova_pixel']
    if not pb['feita']:
        resultado = 'melhorou' if pa['feita'] else 'sem_medida'
    elif not pa['feita']:
        resultado = 'piorou'
    else:
        vb, va, tolerancia = _medidas_comparaveis(pb, pa)
        if va > vb + tolerancia:
            resultado = 'piorou'
        elif va < vb:
            resultado = 'melhorou'
        else:
            resultado = 'igual'
    return {'base_pct': pb['pct'], 'agora_pct': pa['pct'], 'base_feita': pb['feita'], 'agora_feita': pa['feita'],
            'agora_px_acima': pa.get('px_acima'), 'motivo_agora': pa.get('motivo') if not pa['feita'] else None,
            'resultado': resultado}


def ficou_mais_grave(d):
    """Piora por camada: diferenca de situacao para mais grave sem causa especifica, ou camada que existe na linha
    de base e sumiu agora (com qualquer causa, inclusive mudanca_de_versao)."""
    if d['campo'] == 'existencia':
        return bool(d['base']) and not d['agora']
    if d['campo'] != 'situacao' or d['causa'] not in CAUSAS_GENERICAS:
        return False
    gb, ga = GRAVIDADE.get(d['base']), GRAVIDADE.get(d['agora'])
    return gb is not None and ga is not None and ga > gb


def comparar_arquivo(base, agora):
    """Compara duas formas normalizadas. Devolve o bloco do arquivo para o relatorio (sem slug)."""
    versao_mudou = bool(base.get('psd_tools') and agora.get('psd_tools') and base['psd_tools'] != agora['psd_tools'])
    execucao = comparar_execucao(base, agora)
    prova = comparar_prova_pixel(base, agora)
    # sem laudo agora, a lista de camadas some inteira: isso ja e a piora da execucao, nao diferenca por camada
    if not agora.get('tem_laudo', True):
        diferencas = []
    else:
        diferencas = comparar_camadas(base['camadas'], agora['camadas'], versao_mudou=versao_mudou)
    por_causa = {}
    for d in diferencas:
        por_causa[d['causa']] = por_causa.get(d['causa'], 0) + 1
    mais_graves = sum(1 for d in diferencas if ficou_mais_grave(d))
    return {'psd_tools': {'base': base.get('psd_tools'), 'agora': agora.get('psd_tools')},
            'execucao': execucao, 'prova_pixel': prova,
            'tempo_s': {'base': base['tempo_s'], 'agora': agora['tempo_s']},
            'camadas': {'base': len(base['camadas']), 'agora': len(agora['camadas']),
                        'com_diferenca': len({d['layer_id'] for d in diferencas})},
            'diferencas': diferencas, 'por_causa': por_causa, 'camadas_mais_graves': mais_graves,
            'piorou': execucao['resultado'] == 'piorou' or prova['resultado'] == 'piorou' or mais_graves > 0}


def _soma(valores):
    vals = [v for v in valores if isinstance(v, (int, float))]
    return round(sum(vals), 2) if vals else None  # numero-neutro: arredondamento so de exibicao


def totais_verificacoes(arquivos):
    """Soma das verificacoes de seguranca por arquivo: saida padrao do modo c e gancho de auditoria."""
    blocos = [b['verificacoes'] for b in arquivos.values() if isinstance(b.get('verificacoes'), dict)]
    soma = lambda grupo, campo: sum(int((b.get(grupo) or {}).get(campo) or 0) for b in blocos)  # noqa: E731
    return {
        'arquivos_verificados': len(blocos),
        'saida_padrao_achados': soma('saida_padrao', 'achados'),
        'saida_padrao_com_conteudo': sum(1 for b in blocos if (b.get('saida_padrao') or {}).get('tem_conteudo')),
        'saida_padrao_termos': soma('saida_padrao', 'termos'),
        'saida_padrao_termos_curtos_presentes': soma('saida_padrao', 'termos_curtos_presentes'),
        'saida_padrao_termos_curtos_vocabulario': soma('saida_padrao', 'termos_curtos_vocabulario'),
        'job_modo_c_verificados': sum(1 for b in blocos if isinstance(b.get('job_modo_c'), dict)),
        'job_modo_c_achados': soma('job_modo_c', 'achados'),
        'job_modo_c_com_conteudo': sum(1 for b in blocos if (b.get('job_modo_c') or {}).get('tem_conteudo')),
        'job_modo_c_falhas': sum(1 for b in blocos if (b.get('job_modo_c') or {}).get('falhou')),
        'auditoria_bloqueios': soma('auditoria', 'bloqueios'),
        'auditoria_recusas': soma('auditoria', 'recusas_auditoria'),
        'filhos_com_estrutura': soma('auditoria', 'filhos_com_estrutura'),
        'gancho_instalado': soma('auditoria', 'gancho_instalado'),
        'linkados': soma('auditoria', 'linkados'),
        'linkados_usados': soma('auditoria', 'linkados_usados'),
    }


def falhas_de_seguranca(verif):
    """Achado na saida padrao, alarme do gancho ou linkado usado: cada um conta como piora. O caminho do job no
    modo c que falhou (job criar ou job proxima com codigo diferente de 0, ou sem laudo) ou que nao rodou tambem
    conta, porque nada foi varrido."""
    return (verif['saida_padrao_achados'] + verif['saida_padrao_com_conteudo'] + verif['auditoria_bloqueios']
            + verif['auditoria_recusas'] + verif['linkados_usados'] + verif.get('job_modo_c_achados', 0)
            + verif.get('job_modo_c_com_conteudo', 0) + verif.get('job_modo_c_falhas', 0)
            + verif.get('job_modo_c_nao_rodou', 0))


def totais(arquivos):
    """Totais do relatorio a partir dos blocos por arquivo (dict slug -> bloco)."""
    por_causa = {}
    for bloco in arquivos.values():
        for causa, n in (bloco.get('por_causa') or {}).items():
            por_causa[causa] = por_causa.get(causa, 0) + n
    comparados = [b for b in arquivos.values() if 'execucao' in b]
    return {
        'arquivos': len(arquivos),
        'comparados': len(comparados),
        'sem_base': sum(1 for b in arquivos.values() if b.get('situacao') == 'sem_base'),
        'so_na_base': sum(1 for b in arquivos.values() if b.get('situacao') == 'so_na_base'),
        'pioras_execucao': sum(1 for b in comparados if b['execucao']['resultado'] == 'piorou'),
        'pioras_prova_pixel': sum(1 for b in comparados if b['prova_pixel']['resultado'] == 'piorou'),
        'melhoras_prova_pixel': sum(1 for b in comparados if b['prova_pixel']['resultado'] == 'melhorou'),
        'arquivos_que_pioraram': sum(1 for b in comparados if b['piorou']),
        'camadas_mais_graves': sum(b.get('camadas_mais_graves', 0) for b in comparados),
        'diferencas_camadas': sum(len(b['diferencas']) for b in comparados),
        'por_causa': por_causa,
        'sem_causa': por_causa.get('sem_causa', 0),
        'tempo_total_s': {
            'base_interno': _soma(b['tempo_s']['base']['interno'] for b in comparados),
            'base_externo': _soma(b['tempo_s']['base']['externo'] for b in comparados),
            'agora_interno': _soma(b['tempo_s']['agora']['interno'] for b in comparados),
            'agora_externo': _soma(b['tempo_s']['agora']['externo'] for b in comparados)},
    }
