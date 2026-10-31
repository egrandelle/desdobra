# -*- coding: utf-8 -*-
"""Segunda passada do laudo: a regra B3 com a conferencia de fontes (arquitetura-v1.md, 4.4).

A primeira passada (desdobra ler) grava laudo/laudo.json com a B3 pendente: toda camada de texto com tinta leva
o alerta fonte_nao_conferida. Depois da fase fontes (fontes/conferencia.json), a fase laudo-fontes chama
aplicar_conferencia, que devolve uma nova versao do laudo (laudo/laudo-fontes.json, passada 2):
  - tira o alerta fonte_nao_conferida das camadas que a conferencia cobriu;
  - poe a B3 (bloqueante) na camada cujo par (camada, nome PostScript) tem motivo tecnico bloqueante na
    conferencia: arquivo faltando, nome sem par, face divergente, glifo faltando, fallback, face errada no CDP,
    CDP sem resposta, face que nao carregou, mais de um arquivo com o mesmo nome PostScript (o DA tira um) ou
    largura acima do limiar a calibrar (esta ultima e decisao do DA);
  - poe o alerta fonte_conferida_com_aviso quando a conferencia so avisa (par por id unico ou familia e
    estilo, peso do OS/2 diferente do estilo); licenca nao entra (decisoes-v1.md, n. 19);
  - grava a situacao de cada fonte usada (presente, ausente ou divergente), a face e o hash da conferencia. Fonte
    sem arquivo sai ausente mesmo quando so aparece em espaco (ai com so_em_espaco, sem efeito na peca).
Funcao pura: recebe dicionarios e devolve um dicionario.
"""
import copy

from desdobra.laudo import regras

CODIGOS_TECNICOS = ('arquivo_faltando', 'nome_ps_sem_par', 'face_divergente', 'glifo_faltando', 'fallback',
                    'face_cdp_divergente', 'face_nao_carregou', 'largura_divergente', 'chromium_nao_conferiu',
                    'colecao_nao_servivel', 'mais_de_um_arquivo', 'cdp_sem_resposta')
FONTE_CONFERENCIA = {'arquivo': 'arquitetura-v1.md', 'secao': '4.4 e 4.5'}


def _tecnicos(item):
    return [m for m in item['motivos'] if m['codigo'] in CODIGOS_TECNICOS and m['situacao'] == 'bloqueante']


def aplicar_conferencia(laudo, conferencia, sha_conferencia, sha_laudo):
    from desdobra import laudo as mod_laudo
    novo = copy.deepcopy(laudo)
    por_camada = {}
    for item in conferencia.get('camadas') or []:
        por_camada.setdefault(item['layer_id'], []).append(item)
    for c in novo['camadas']:
        lid = c['identidade']['layer_id']
        itens = por_camada.get(lid)
        if not itens:
            continue
        c['alertas'] = [a for a in c.get('alertas') or [] if a.get('codigo') != 'fonte_nao_conferida']
        for item in itens:
            tec = _tecnicos(item)
            if tec:
                lim = next((m.get('limite') for m in tec if m.get('limite')), None)
                c['motivos'].append({
                    'regra': 'B3',
                    'descricao': 'Fonte do trecho não passou na conferência contra o arquivo enviado (%s).'
                                 % ', '.join(sorted({m['codigo'] for m in tec})),
                    'medida': {'fonte_ps': item['nome_ps'], 'face_id': item['face_id'],
                               'motivos': sorted({m['codigo'] for m in tec}), 'glifos_faltando': item['glifos_faltando'],
                               'largura_erro_pct': item.get('largura_erro_pct'), 'face_cdp_confere': item['face_cdp_confere'],
                               'decisao': item.get('decisao')},
                    'limite': lim, 'fonte': regras.REGRAS['B3']['fonte']})
            elif item['situacao'] == 'aviso':
                c['alertas'].append({'codigo': 'fonte_conferida_com_aviso', 'fonte': FONTE_CONFERENCIA,
                                     'descricao': 'A fonte do trecho passou na conferência com aviso (par fora do name '
                                                  'ID 6 ou peso). Veja fontes/conferencia.json.',
                                     'medida': {'fonte_ps': item['nome_ps'], 'face_id': item['face_id'],
                                                'motivos': sorted({m['codigo'] for m in item['motivos']
                                                                   if m['situacao'] == 'aviso'})}})
        c['situacao'] = regras.situacao(c['motivos'])
    por_ps = {}
    for item in conferencia.get('camadas') or []:
        por_ps.setdefault(item['nome_ps'], []).append(item)
    for f in novo['fontes_usadas']:
        itens = por_ps.get(f['fonte_ps'])
        if not itens:
            continue
        com_tinta = [i for i in itens if not any(m['codigo'] == 'so_em_espaco' for m in i['motivos'])]
        if not com_tinta:
            # usada so em espaco: sem efeito na peca, mas sem arquivo continua ausente (nunca presente sem arquivo)
            f['so_em_espaco'] = True
        alvo = com_tinta or itens
        if any(i['face_id'] is None for i in alvo):
            f['situacao'] = 'ausente'
        elif any(_tecnicos(i) for i in alvo):
            f['situacao'] = 'divergente'
        else:
            f['situacao'] = 'presente'
        f['face_id'] = next((i['face_id'] for i in itens if i['face_id']), None)
    novo['passada'] = 2
    novo['conferencia_fontes'] = {'arquivo': 'fontes/conferencia.json', 'sha256': sha_conferencia,
                                  'laudo_primeira_passada_sha256': sha_laudo}
    novo['regras'] = {k: dict(v) for k, v in regras.REGRAS.items()}
    resumo = mod_laudo._resumo(novo['camadas'], (novo.get('documento') or {}).get('quadros') or [], novo['recusas'])
    resumo['n_b3_fontes'] = sum(1 for c in novo['camadas'] if any(m['regra'] == 'B3' for m in c['motivos']))
    novo['resumo'] = resumo
    return novo
