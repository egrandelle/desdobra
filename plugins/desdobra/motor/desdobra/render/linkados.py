# -*- coding: utf-8 -*-
"""Confirmacao do DA do arquivo de cada smart object linkado (arquitetura-v1.md, 7.2; criterio do M4, 9.5).

O registro do linkado no PSD so traz nome, tamanho e data, nunca hash. O leitor propoe o casamento com os arquivos
de entrada/campanha/ por nome e tamanho (laudo, smart_object.casamento) e nunca segue o caminho gravado no PSD. Aqui
o DA confirma, num terminal interativo, qual arquivo vale para cada linkado. A confirmacao grava
briefing/linkados-confirmados.json (linkados-confirmados/1) com o arquivo, o sha256 congelado em estado.json, o
sha256 do laudo e do KV a que ela vale, quem confirmou, o meio e quando. O render usa so o arquivo confirmado, e so
quando o laudo e o KV sao os mesmos da confirmacao; o sha256 vai para o render.json.

So grava com o Disparo que desdobra.humano.exigir('linkado confirmar') emite depois de conferir o console, e com a
trava do job. Nenhuma pergunta tem resposta padrao: Enter vazio repete. No M7a a mesma confirmar() serve ao botao do
passo 1 da tela (desdobra.tela.atos), com o Disparo da tela (meio tela; no modo de teste, meio medicao e origem
fixture_de_teste, gravada em confirmado_por.origem).
"""
from pathlib import Path

from desdobra import arquivos, contratos, humano
from desdobra.render import contrato as mod_contrato


class ErroLinkado(Exception):
    pass


def pendentes(pasta):
    """[(camada do laudo, candidatos)] dos linkados do laudo, com os candidatos da proposta do leitor."""
    laudo = contratos.ler(Path(pasta) / 'laudo' / 'laudo.json', 'laudo/1')
    out = []
    for c in laudo['camadas']:
        so = c.get('smart_object') or {}
        if c.get('tipo') != 'smart_linkado' or not so.get('unique_id'):
            continue
        out.append((c, (so.get('casamento') or {}).get('candidatos') or []))
    return laudo, out


def _gravar(pasta, laudo, itens):
    dados = {'esquema': mod_contrato.ESQUEMA_LINKADOS,
             'laudo_sha256': arquivos.sha256_arquivo(Path(pasta) / 'laudo' / 'laudo.json'),
             'kv_sha256': laudo['origem']['sha256'], 'linkados': itens}
    contratos.gravar(Path(pasta) / mod_contrato.ARQUIVO_LINKADOS, dados, mod_contrato.ESQUEMA_LINKADOS)
    return dados


def confirmar(pasta, unique_id, arquivo, *, disparo):
    """Grava a confirmacao de um linkado. arquivo: caminho relativo ao job, dentro de entrada/campanha/. disparo: o
    emitido pela conferencia do console (humano.ErroHumano sem ele)."""
    from desdobra.job import nucleo
    humano.conferir(disparo, 'linkado confirmar')
    pasta = Path(pasta).resolve()
    with nucleo.Trava(pasta):
        estado = contratos.ler(pasta / 'estado.json', 'estado/1')
        if not arquivo.startswith('entrada/campanha/') or arquivo not in estado['entradas']:
            raise ErroLinkado('O arquivo confirmado tem de ser uma entrada congelada de entrada/campanha/.')
        laudo, lista = pendentes(pasta)
        camadas = [c for c, _cands in lista if c['smart_object']['unique_id'] == unique_id]
        if not camadas:
            raise ErroLinkado('O laudo não tem linkado com este identificador.')
        existentes = {}
        arq = pasta / mod_contrato.ARQUIVO_LINKADOS
        if arq.is_file():
            antigos = contratos.ler(arq, mod_contrato.ESQUEMA_LINKADOS)
            if antigos['kv_sha256'] == laudo['origem']['sha256']:
                existentes = {x['unique_id']: x for x in antigos['linkados']}
        reg = estado['entradas'][arquivo]
        existentes[unique_id] = {'unique_id': unique_id,
                                 'layer_ids': sorted(c['identidade']['layer_id'] for c in camadas),
                                 'arquivo': arquivo, 'sha256': reg['sha256'], 'bytes': reg['bytes'],
                                 'registro_no_psd': camadas[0]['smart_object'].get('registro'),
                                 'confirmado_por': dict(disparo.registro(), origem=disparo.origem)}
        return _gravar(pasta, laudo, sorted(existentes.values(), key=lambda x: x['unique_id']))


def sessao(pasta, *, disparo, saida=print):
    """Pergunta, linkado por linkado, qual arquivo da campanha vale. Devolve (dados gravados, novos)."""
    humano.conferir(disparo, 'linkado confirmar')
    pasta = Path(pasta).resolve()
    if not (pasta / 'estado.json').is_file():
        raise ErroLinkado('A confirmação só funciona numa pasta de job do desdobra.')
    _laudo, lista = pendentes(pasta)
    if not lista:
        raise ErroLinkado('O laudo não tem smart object linkado.')
    dados, novos = {'linkados': list(mod_contrato.linkados_confirmados(pasta).values())}, 0
    for c, cands in lista:
        so = c['smart_object']
        reg = so.get('registro') or {}
        saida('Camada %s: linkado gravado no PSD como %s (%s bytes, %s).' % (
            c['identidade']['layer_id'], reg.get('nome'), reg.get('tamanho'), reg.get('data')))
        if not cands:
            saida('  Nenhum arquivo de entrada/campanha/ tem esse nome. Acrescente o arquivo em '
                  'entrada/campanha/ do job e confirme de novo.')
            continue
        for k, cand in enumerate(cands, 1):
            saida('  %d) %s, %s bytes%s' % (k, cand['arquivo'], cand['bytes'],
                                            '' if cand.get('mesmo_tamanho') else ' (tamanho diferente do registro)'))
        while True:
            try:
                r = humano.ler('Número do arquivo que vale para este linkado, ou "pular": ').strip().casefold()
            except (EOFError, KeyboardInterrupt):
                return dados, novos
            if r == 'pular':
                break
            if r.isdigit() and 1 <= int(r) <= len(cands):
                dados = confirmar(pasta, so['unique_id'], 'entrada/' + cands[int(r) - 1]['arquivo'], disparo=disparo)
                novos += 1
                break
            saida('Responda com o número de um arquivo da lista ou "pular".')
    return dados, novos
