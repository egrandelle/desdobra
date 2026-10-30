# -*- coding: utf-8 -*-
"""Resumo legivel da regressao (regressao-<data>.md) e as linhas do modo humano da CLI.

O resumo tem os slugs, os numeros e as diferencas. Texto de camada aparece so como sha256 e tamanho, como no
JSON. O resumo fica na pasta de saida da regressao, fora do repositorio.
"""
import json

from desdobra.arquivos import gravar_texto_atomico

NOMES_RESULTADO = {'igual': 'igual', 'piorou': 'PIOROU', 'melhorou': 'melhorou', 'mudou': 'mudou',
                   'sem_medida': 'sem medida'}


def _pct(v):
    return 'não feita' if v is None else '%s%%' % v


def _seg(v):
    return 'sem medida' if v is None else str(v)


def _valor(v):
    if isinstance(v, dict) and 'sha256' in v:
        return 'texto sha256 %s..., %d caracteres' % (v['sha256'][:12], v['tamanho'])  # numero-neutro: exibicao
    return json.dumps(v, ensure_ascii=False)


def _relogio(rel):
    base = rel.get('base_execucao') or {}
    return ('Tempo de relógio: agora %s s com paralelo %s; linha de base %s s com paralelo %s.'
            % (_seg(rel.get('duracao_s')), rel.get('paralelo'), _seg(base.get('duracao_s')),
               base.get('paralelo') if base.get('paralelo') is not None else 'sem medida'))


def linhas_humanas(rel):
    tot = rel['totais']
    linhas = ['Regressão: %d arquivos, %d comparados.' % (tot['arquivos'], tot['comparados']),
              'Pioras: %d na execução, %d na prova de pixel. Melhoras na prova de pixel: %d.'
              % (tot['pioras_execucao'], tot['pioras_prova_pixel'], tot['melhoras_prova_pixel']),
              'Diferenças por camada: %d (sem causa: %d).' % (tot['diferencas_camadas'], tot['sem_causa'])]
    if tot['por_causa']:
        linhas.append('Por causa: ' + ', '.join('%s %d' % kv for kv in sorted(tot['por_causa'].items())))
    t = tot['tempo_total_s']
    linhas.append(_relogio(rel))
    linhas.append('Soma dos tempos por arquivo (s): base %s, agora %s.' % (_seg(t['base_externo']),
                                                                        _seg(t['agora_externo'])))
    if tot.get('camadas_mais_graves') or tot['so_na_base'] or tot['sem_base']:
        linhas.append('Camadas mais graves sem causa ou que sumiram: %d. Só na linha de base: %d. '
                      'Sem linha de base: %d.'
                      % (tot.get('camadas_mais_graves', 0), tot['so_na_base'], tot['sem_base']))
    for slug, bloco in rel['arquivos'].items():
        if bloco.get('situacao') != 'comparado':
            linhas.append('  %s: %s' % (slug, bloco.get('situacao')))
            continue
        ex, pp = bloco['execucao'], bloco['prova_pixel']
        linhas.append('  %s: execução %s -> %s (%s); prova de pixel %s -> %s (%s); %d diferenças'
                      % (slug, ex['base'], ex['agora'], NOMES_RESULTADO.get(ex['resultado'], ex['resultado']),
                         _pct(pp['base_pct']), _pct(pp['agora_pct']),
                         NOMES_RESULTADO.get(pp['resultado'], pp['resultado']), len(bloco['diferencas'])))
    linhas.append('Resultado: %s.' % ('algum arquivo piorou' if rel['resultado'] == 'piorou' else 'nada piorou'))
    return linhas


def montar_resumo(rel):
    tot = rel['totais']
    t = tot['tempo_total_s']
    md = ['# Regressão da leitura contra a linha de base', '',
          'Gerado em %s, motor %s, modo %s.' % (rel['gerado_em'], rel['motor'], rel['modo']), '',
          '## Resultado', '',
          '**%s**' % ('Algum arquivo piorou.' if rel['resultado'] == 'piorou' else 'Nada piorou.'), '',
          '- Arquivos: %d, comparados: %d, sem linha de base: %d, só na linha de base: %d.'
          % (tot['arquivos'], tot['comparados'], tot['sem_base'], tot['so_na_base']),
          '- Pioras na execução: %d. Pioras na prova de pixel: %d. Melhoras na prova de pixel: %d.'
          % (tot['pioras_execucao'], tot['pioras_prova_pixel'], tot['melhoras_prova_pixel']),
          '- Diferenças por camada: %d, das quais %d sem causa registrada.' % (tot['diferencas_camadas'], tot['sem_causa']),
          '- Camadas que ficaram mais graves sem causa específica ou que sumiram: %d.'
          % tot.get('camadas_mais_graves', 0),
          '- Falhas de segurança: %d (caminho do job no modo c que falhou: %d; que não rodou: %d).'
          % (tot.get('falhas_de_seguranca', 0), (tot.get('verificacoes') or {}).get('job_modo_c_falhas', 0),
             (tot.get('verificacoes') or {}).get('job_modo_c_nao_rodou', 0)),
          '- %s' % _relogio(rel),
          '- Soma dos tempos por arquivo, em segundos (não é o tempo de relógio, porque arquivos rodam em paralelo): '
          'base %s (dentro da sonda %s), agora %s (dentro do leitor %s).'
          % (_seg(t['base_externo']), _seg(t['base_interno']), _seg(t['agora_externo']), _seg(t['agora_interno'])), '',
          '## Causas registradas', '']
    for cid, causa in rel['causas'].items():
        fonte = causa['fonte']
        md.append('- `%s`: %s Fonte: %s, seção %s. Diferenças: %d.'
                  % (cid, causa['descricao'], fonte['arquivo'], fonte['secao'], tot['por_causa'].get(cid, 0)))
    md += ['', '## Por arquivo', '',
           '| arquivo | execução (base, agora) | prova de pixel (base, agora) | diferenças | sem causa |',
           '|---|---|---|---|---|']
    for slug, bloco in rel['arquivos'].items():
        if bloco.get('situacao') != 'comparado':
            md.append('| %s | %s | | | |' % (slug, bloco.get('situacao')))
            continue
        ex, pp = bloco['execucao'], bloco['prova_pixel']
        md.append('| %s | %s, %s: %s | %s, %s: %s | %d | %d |'
                  % (slug, ex['base'], ex['agora'], NOMES_RESULTADO.get(ex['resultado'], ex['resultado']),
                     _pct(pp['base_pct']), _pct(pp['agora_pct']), NOMES_RESULTADO.get(pp['resultado'], pp['resultado']),
                     len(bloco['diferencas']), bloco['por_causa'].get('sem_causa', 0)))
    md += ['', '## Diferenças por camada', '']
    algum = False
    for slug, bloco in rel['arquivos'].items():
        difs = bloco.get('diferencas') or []
        if not difs:
            continue
        algum = True
        md += ['### %s' % slug, '']
        for d in difs:
            extra = ''
            if d.get('detalhe'):
                extra = ' (regras só na base: %s; só agora: %s)' % (
                    ', '.join(d['detalhe']['regras_so_na_base']) or 'nenhuma',
                    ', '.join(d['detalhe']['regras_so_agora']) or 'nenhuma')
            md.append('- camada %s, %s: base %s, agora %s. Causa: `%s`%s.'
                      % (d['layer_id'], d['campo'], _valor(d['base']), _valor(d['agora']), d['causa'], extra))
        md.append('')
    if not algum:
        md.append('Nenhuma diferença por camada.')
    return '\n'.join(md) + '\n'


def gravar_resumo(caminho, rel):
    gravar_texto_atomico(caminho, montar_resumo(rel))
