# -*- coding: utf-8 -*-
"""Impressao por formato (M7b, A1): o sha256 de tudo o que alimenta um formato, para a cadeia derivacao, render e
aprovacao cair so no formato que mudou (e nao no job inteiro, como o sha do briefing).

Entra na impressao de um formato:
  - a derivacao/1 dele sem gerado_em, sem briefing_sha256, sem inventario_entre_formatos (o inventario e de todos os
    formatos; a conferencia dele fica com quem le o conjunto), sem a propria impressao_formato e sem quebras_origem
    de cada elemento (quem fez a quebra da familia, o DA ou a proposta aprovada, nao muda o desenho: as quebras, a
    caixa e origem_geometria ficam; revisao 2 do M7b, fase C);
  - as funcoes resolvidas (briefing.modelo.resolver) das camadas no escopo do formato: as dos elementos que estao nele
    e as "fora da peca" (a camada que sai de todo formato); o elemento apagado pelo DA na familia fica fora do escopo;
  - as camadas "fora da peca" de agora (a lista entra em toda derivacao: a camada que sai da peca muda todo formato,
    tambem o gravado antes, que nao a tem na lista dele);
  - as regras de escala das funcoes dessas camadas, as do indeterminado e as de bloco delas, e as ancoras de cada
    uma (a do elemento vale sobre a da funcao, como a derivacao le);
  - as quebras aprovadas que valem no formato (derivacao.quebras.aprovadas_para) e a quebra da familia da tela, com as
    posicoes inseridas, que vale por cima delas (derivacao.quebras.da_familia, M7b, C1);
  - o formato do briefing, a composicao da familia dele (versao e edicoes do DA; da confirmacao, a origem e o meio,
    sem o carimbo, aqui e na proposta da derivacao: confirmar de novo o mesmo nao muda o formato, decisoes-v1.md,
    175) e os valores da folha de spec dele (sem a fonte do campo). Da composicao e da proposta ficam fora o id da
    familia, so um nome (preso aos formatos dela desde a revisao do M7b, fase A, tela.estado.abas; a familia que se
    divide ou se junta pode levar o formato a outro id sem mudar o que ele recebe), e a lista dos formatos dela, que
    so alimenta o formato pela derivacao dele (o irmao novo que nao muda a derivacao nao derruba o formato);
  - a mestre usada: a propria do DA (caixas e quebras), com o formato e a folha dela; a do KV ja esta na derivacao.
Todo numero com casas sai arredondado como na derivacao (nucleo._q, CASAS_ESCALA): a medicao do A0 deu derivacao
igual em 60 rodadas (scratchpad/m7/medicoes/determinismo.txt), e o arredondamento e so guarda. Funcao pura: nao le
arquivo.
"""
import hashlib
import json

from desdobra.briefing import modelo as mb
from desdobra.derivacao import formatos as mod_formatos
from desdobra.derivacao import quebras as mod_quebras

FORA_DA_IMPRESSAO = ('gerado_em', 'briefing_sha256', 'inventario_entre_formatos', 'impressao_formato')
CAMPOS_DA_SPEC_FORA = ('id', 'fonte')
CARIMBO_DA_CONFIRMACAO = ('em',)
# do elemento da derivacao: so diz quem fez a quebra da familia (M7b, C2), e nao muda o que o formato desenha
FORA_DO_ELEMENTO = ('quebras_origem',)
ROTULOS_DA_FAMILIA = ('familia', 'formatos')


def resolvido(briefing, resolvidas, specs=None):
    """O briefing resolvido que a impressao le: o briefing, as funcoes resolvidas (mb.resolver) e as folhas de spec
    ({chave: formato da folha})."""
    return {'briefing': briefing, 'resolvidas': resolvidas, 'specs': specs or {}}


def _normal(v):
    from desdobra.derivacao import nucleo as nd
    if isinstance(v, float):
        return nd._q(v, nd.CASAS_ESCALA)
    if isinstance(v, dict):
        return {str(k): _normal(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_normal(x) for x in v]
    return v


def _spec(specs, chave):
    s = specs.get(chave)
    if s is None:
        return None
    return {k: {c: x for c, x in campo.items() if c not in CAMPOS_DA_SPEC_FORA}
            for k, campo in sorted((s.get('campos') or {}).items())}


def _quebras(b, lids, formato, W, H):
    """As quebras que valem no formato, por camada: [layer_id, indices que ficam] da faixa ou da lista de formatos
    (M5), ou [layer_id, indices que ficam, posicoes inseridas] da familia da tela (M7b, C1), que vale por cima. A
    origem e a aprovacao nao entram: so o que o formato desenha."""
    saida = []
    for x in lids:
        fam = mod_quebras.da_familia(b, x, formato['id'])
        if fam is not None:
            saida.append([x, list(fam['quebras']['valor']), list(fam.get('inseridas') or ())])
            continue
        q = mod_quebras.aprovadas_para(b, x, formato, W, H)
        if q is not None:
            saida.append([x, q])
    return saida


def entradas(derivacao_formato, briefing_resolvido, fid):
    """O que alimenta o formato fid, alem da derivacao dele (ver o cabecalho do modulo)."""
    d, b = derivacao_formato, briefing_resolvido['briefing']
    resolvidas, specs = briefing_resolvido['resolvidas'], briefing_resolvido['specs']
    formato = next(f for f in b['formatos'] if f['id'] == fid)
    lids = sorted({x for e in d['elementos'] for x in e['layer_ids']} | set(d.get('fora_da_peca') or []))
    funcoes = {x: resolvidas[x] for x in lids if x in resolvidas}
    nomes = {r['funcao'] for r in funcoes.values()}
    W, H = mod_formatos.composicao(formato)
    mestre = None
    md = d.get('mestre') or {}
    if md.get('tipo') == 'propria':
        mp = next((m for m in b['mestres'] if m['id'] == md['id']), None)
        fm = next((f for f in b['formatos'] if mp and f['id'] == mp.get('formato')), None)
        mestre = {'mestre': mp, 'formato': fm, 'spec': _spec(specs, fm['chave']) if fm else None}
    return {
        'formato': formato,
        'funcoes': [[x, funcoes[x]] for x in sorted(funcoes)],
        'fora_da_peca': sorted(x for x, r in resolvidas.items() if r['funcao'] == mb.FUNCAO_FORA),
        'regras': sorted([f, r] for f, r in mb.regras_por_funcao(b).items() if f in nomes),
        'regras_indeterminado': sorted([x, r] for x, r in mb.regras_indeterminado(b).items() if x in lids),
        'regras_bloco': sorted([x, r] for x, r in mb.regras_bloco(b).items() if x in lids),
        'ancoras': [[x, list(mb.ancora_do_elemento(b, r['raiz'], r['funcao'])), list(mb.ancora_explicita(b, r['raiz']))]
                    for x, r in sorted(funcoes.items())],
        'quebras': _quebras(b, lids, formato, W, H),
        'composicao': next((c for c in b.get('composicoes') or [] if fid in c['formatos']), None),
        'spec': _spec(specs, formato['chave']),
        'mestre': mestre,
    }


def sem_carimbo(item):
    """A composicao do briefing ou a proposta da derivacao sem o que nao muda o formato: o carimbo da confirmacao
    (confirmar a familia de novo, com a mesma versao e as mesmas edicoes, como a mudanca do passo 2 pede de toda
    familia; decisoes-v1.md, 175), o id da familia (so um nome; tela.estado.abas) e a lista dos formatos dela. A origem
    e o meio da confirmacao, a versao e as edicoes ficam. A trava do derivado (render.derivado) compara assim tambem."""
    if not isinstance(item, dict):
        return item
    item = {k: v for k, v in item.items() if k not in ROTULOS_DA_FAMILIA}
    if not isinstance(item.get('confirmacao'), dict):
        return item
    return dict(item, confirmacao={k: v for k, v in item['confirmacao'].items() if k not in CARIMBO_DA_CONFIRMACAO})


def corpo(derivacao_formato, briefing_resolvido, fid):
    """O que a impressao do formato fid resume, normalizado: {'derivacao' (sem os campos de FORA_DA_IMPRESSAO, os
    elementos sem FORA_DO_ELEMENTO e a proposta sem_carimbo), 'entradas'}. A diferenca por formato (derivacao.diferenca, A5) compara dois
    destes."""
    d = {k: v for k, v in derivacao_formato.items() if k not in FORA_DA_IMPRESSAO}
    if isinstance(d.get('elementos'), list):
        d['elementos'] = [{k: v for k, v in e.items() if k not in FORA_DO_ELEMENTO} if isinstance(e, dict) else e
                          for e in d['elementos']]
    if 'proposta' in d:
        d['proposta'] = sem_carimbo(d['proposta'])
    e = entradas(derivacao_formato, briefing_resolvido, fid)
    e['composicao'] = sem_carimbo(e['composicao'])
    return _normal({'derivacao': d, 'entradas': e})


def do_corpo(c):
    """sha256 (hex) de um corpo (corpo)."""
    texto = json.dumps(c, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()


def impressao(derivacao_formato, briefing_resolvido, fid):
    """sha256 (hex) da derivacao do formato fid (sem os campos de FORA_DA_IMPRESSAO) e das entradas dele."""
    return do_corpo(corpo(derivacao_formato, briefing_resolvido, fid))
