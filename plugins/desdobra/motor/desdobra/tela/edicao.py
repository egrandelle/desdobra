# -*- coding: utf-8 -*-
"""Edicao da composicao no palco, por familia (M7a, fatia 4; decisoes-v1.md, 164, 166, 167, 168, 169 e 171).

A familia (as composicoes de proporcao parecida de uma orientacao, desdobra.tela.estado.agrupar_por_proporcao) recebe
as decisoes do DA de uma vez so, nunca peca a peca:
  - o ponto de partida de cada membro e a versao da galeria que o DA escolheu (o formato devolvido) ou a proposta da
    derivacao (o formato derivado); sem escolha, a primeira versao sem falha, como a tela mostra;
  - cada edicao (mover, escalar, texto, apagar) e gravada em fracao do lado da peca e vai a cada membro em proporcao
    ao formato dele (aplicar);
  - depois de cada edicao, a intencao de alinhamento (168): bordas e centros de dois elementos de conteudo que ficam a
    menos de derivacao.alinhamento_intencao_tolerancia do lado maior da peca viram o mesmo valor (normalizar). Quando
    os dois ja estavam alinhados no KV, vence o alinhamento do KV (o mexido volta para a linha do outro); senao, vence o
    elemento mexido por ultimo (o outro vem para a linha dele). Acima da tolerancia, a diferenca e intencao do DA;
  - o encaixe de cada membro e refeito pelo solver do repositorio, com as caixas editadas como mestre sintetica (como a
    galeria faz com a variante), e o layout e conferido contra a mestre verdadeira (desdobra.derivacao.galeria);
  - o texto editado precisa de todos os caracteres na face do job que o desenha (a cobertura do cmap lida pelo filho
    das fontes; o processo principal nunca abre a fonte); a previa leva o texto novo com a face real, e as quebras
    sao refeitas pela pagina na largura da caixa, com a fonte carregada. O texto vale so na familia editada (171);
  - o elemento apagado sai de todos os membros, fica registrado com a origem do rascunho ('da', ou fixture_de_teste no
    modo de teste da tela) e deixa de reprovar o inventario (desdobra.derivacao.validacao, apagados);
  - a quebra de linha da familia (M7b, C3; decisoes-v1.md, 167 e 171): o pedido pode levar as quebras do rascunho da
    familia (quebras, o mesmo formato do rascunho); sem o campo, a familia nao tem quebra no rascunho, como a lista
    vazia (revisao do C). Quando elas diferem das do briefing, a previa mede o texto com a
    quebra nova (desdobra.derivacao.medida_quebras.medir, com o cache: so o texto que mudou vai ao Chromium) e deriva
    de novo os membros da familia com ela, como a derivacao vai fazer depois de "Salvar e seguir"; a previa e a
    derivacao gravada usam a mesma medida. A quebra fora de um espaco do texto de agora e recusada (como o rascunho).
    A previa leva os textos que o DA pode quebrar, com as posicoes (textos_da_quebra, o controle da quebra no palco,
    M7b, C4), e o texto editado sai no palco nas linhas da quebra da familia.
So previa, em memoria: nada aqui grava arquivo. As edicoes ficam no rascunho que a pagina grava (desdobra.tela.rascunho),
e "Confirmar familia" e um ato da janela (desdobra.tela.atos).
"""
import time

from desdobra import limites

ACOES = ('mover', 'escalar', 'texto', 'apagar')
CAMPOS = ('familia', 'versao', 'edicoes')
CAMPOS_OPCIONAIS = ('quebras',)  # M7b, C3: as quebras de linha do rascunho da familia
VIVAS_MAX = 8  # numero-neutro: familias com quebra nova guardadas na previa (a ultima mexida fica)
# as linhas de alinhamento de uma caixa [x0, y0, x1, y1]: (nome para o DA, indice, indice do outro lado para o centro)
LINHAS = {'x': (('esquerda', 0, None), ('centro', 0, 2), ('direita', 2, None)),  # numero-neutro: indices da caixa
          'y': (('topo', 1, None), ('meio', 1, 3), ('base', 3, None))}  # numero-neutro: indices da caixa
METADE = 0.5  # numero-neutro: o meio da caixa
IGUAL = 1e-6  # numero-neutro: folga numerica de duas linhas que ja estao no mesmo valor
POR_MS = 1000.0  # numero-neutro: segundos para milissegundos
CASAS_MS = 1  # numero-neutro: casas do tempo gasto


def tolerancia(W, H):
    """A tolerancia da intencao de alinhamento, em px da peca W x H (proporcional ao lado maior)."""
    return float(limites.valor('derivacao.alinhamento_intencao_tolerancia')) * max(float(W), float(H))


def _linha(c, eixo, nome):
    for n, i, j in LINHAS[eixo]:
        if n == nome:
            return c[i] if j is None else (c[i] + c[j]) * METADE
    raise KeyError(nome)


def _deslocar(c, eixo, d):
    if eixo == 'x':
        return [c[0] + d, c[1], c[2] + d, c[3]]
    return [c[0], c[1] + d, c[2], c[3] + d]


# ------------------------------------------------------------------ as edicoes em proporcao
def aplicar(caixas, edicoes, W, H):
    """As edicoes do DA no formato W x H. caixas: {id: [x0, y0, x1, y1]}. Mover anda dx x W e dy x H; escalar multiplica
    a caixa pelo fator em volta do ponto fixo (fx, fy, fracoes da caixa; o meio sem eles). Devolve (caixas, apagados,
    textos {id: texto}, mexidos na ordem, o ultimo por ultimo)."""
    caixas = {k: [float(x) for x in v] for k, v in caixas.items()}
    apagados, textos, mexidos = [], {}, []
    for ed in edicoes:
        eid, acao = ed['elemento'], ed['acao']
        if eid not in caixas or eid in apagados:
            continue
        if acao == 'apagar':
            apagados.append(eid)
            continue
        if acao == 'texto':
            textos[eid] = ed['texto']
            continue
        c = caixas[eid]
        if acao == 'mover':
            dx, dy = float(ed['dx']) * W, float(ed['dy']) * H
            c = [c[0] + dx, c[1] + dy, c[2] + dx, c[3] + dy]
        else:
            k = float(ed['fator'])
            px = c[0] + float(ed.get('fx', METADE)) * (c[2] - c[0])
            py = c[1] + float(ed.get('fy', METADE)) * (c[3] - c[1])
            c = [px + (c[0] - px) * k, py + (c[1] - py) * k, px + (c[2] - px) * k, py + (c[3] - py) * k]
        caixas[eid] = c
        if eid in mexidos:
            mexidos.remove(eid)
        mexidos.append(eid)
    for eid in apagados:
        caixas.pop(eid, None)
        textos.pop(eid, None)
        if eid in mexidos:
            mexidos.remove(eid)
    return caixas, apagados, textos, mexidos


def normalizar(caixas, mexidos, W, H, kv_caixas=None, kv_tamanho=None):
    """A intencao de alinhamento (decisoes-v1.md, 168) entre cada elemento mexido e os outros de caixas. Em cada eixo,
    o par que ja divide uma linha fica; senao, a linha mais perto abaixo da tolerancia vira o mesmo valor, so com
    deslocamento (o tamanho nao muda), um encaixe por elemento e eixo. Duas passadas: primeiro os pares que ja estavam
    alinhados no KV (o mexido volta para a linha do outro), depois os outros (vence o mexido por ultimo), ja com as
    posicoes da primeira; assim um encaixe do KV nunca desfaz um encaixe ja feito e deixa linha quase igual (revisao do
    M7a). Devolve (caixas, alinhados [{'elementos': [o que andou, o que ficou], 'eixo', 'linha', 'valor'}])."""
    tol = tolerancia(W, H)
    tol_kv = tolerancia(*kv_tamanho) if kv_tamanho else None
    caixas = {k: list(v) for k, v in caixas.items()}
    ordem = {e: n for n, e in enumerate(mexidos)}
    feitos, alinhados = set(), []

    def perto_de(m, o, eixo):
        nomes = [n for n, _i, _j in LINHAS[eixo]]
        difs = [(abs(_linha(caixas[m], eixo, n) - _linha(caixas[o], eixo, n)), n) for n in nomes]
        if any(d <= IGUAL for d, _n in difs):
            return []
        return [(d, n) for d, n in difs if d <= tol]

    def encaixar(anda, fica, eixo, nome):
        if (anda, eixo) in feitos:
            return
        valor = _linha(caixas[fica], eixo, nome)
        caixas[anda] = _deslocar(caixas[anda], eixo, valor - _linha(caixas[anda], eixo, nome))
        feitos.add((anda, eixo))
        alinhados.append({'elementos': [anda, fica], 'eixo': eixo, 'linha': nome, 'valor': round(valor, 4)})  # numero-neutro: casas do px

    def do_kv(m, o, eixo, perto):
        if not (kv_caixas and tol_kv is not None and m in kv_caixas and o in kv_caixas):
            return []
        return [(d, n) for d, n in perto
                if abs(_linha(kv_caixas[m], eixo, n) - _linha(kv_caixas[o], eixo, n)) <= tol_kv]

    pares = [(m, o, eixo) for m in mexidos if m in caixas for o in sorted(caixas) if o != m for eixo in ('x', 'y')]
    # 1a passada: o alinhamento do KV vence, o mexido volta para a linha do outro
    for m, o, eixo in pares:
        no_kv = do_kv(m, o, eixo, perto_de(m, o, eixo))
        if no_kv:
            encaixar(m, o, eixo, min(no_kv)[1])
    # 2a passada: o resto, com as posicoes da primeira; vence o mexido por ultimo
    for m, o, eixo in pares:
        perto = perto_de(m, o, eixo)
        if not perto or do_kv(m, o, eixo, perto):
            continue
        nome = min(perto)[1]
        vence = m if ordem.get(m, -1) >= ordem.get(o, -1) else o
        anda, fica = (o, m) if vence == m else (m, o)
        encaixar(anda, fica, eixo, nome)
    return caixas, alinhados


# ------------------------------------------------------------------ texto
def caracteres_que_faltam(texto, face, caixa_alta=False):
    """Os caracteres com tinta do texto que a face nao cobre, em ordem e sem repetir."""
    from desdobra.fontes import casamento
    alvo = texto.upper() if caixa_alta else texto
    vistos = []
    for ch in alvo:
        if casamento.tem_tinta(ch) and not casamento.cobre(face, ord(ch)) and ch not in vistos:
            vistos.append(ch)
    return vistos


def _texto_da_recusa(faltam):
    lista = ', '.join(faltam)
    if len(faltam) == 1:
        return 'A fonte deste texto não tem o caractere %s. Troque o caractere ou envie a fonte que o tenha.' % lista
    return 'A fonte deste texto não tem os caracteres %s. Troque esses caracteres ou envie a fonte que os tenha.' % lista


def trocar_texto(palco, elemento, texto, quebra=None):
    """As pecas de texto do elemento no palco levam o texto novo, linha a linha (as quebras do DA), com o estilo do
    primeiro trecho (face, cor, corpo e tracking ja na escala do formato); a pagina refaz as quebras na largura da
    caixa com a fonte real. quebra: a quebra de linha da familia no texto (o item do rascunho, M7b, C4): as linhas
    juntadas e as inseridas, como o render desenha (desdobra.derivacao.quebras.linhas_do_editado)."""
    from desdobra.derivacao import quebras as mq
    if quebra is not None:
        linhas = mq.linhas_do_editado(texto, quebra['manter'], quebra['inseridas'])
    else:
        linhas = texto.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    for p in palco['pecas']:
        if p.get('elemento') != elemento or p.get('tipo') != 'texto' or not p.get('linhas'):
            continue
        t0 = p['linhas'][0]['trechos'][0]
        ent = next((ln['entrelinha'] for ln in p['linhas'] if ln.get('entrelinha')), None)
        p['linhas'] = [{'trechos': [dict(t0, texto=ln)], 'entrelinha': ent} for ln in linhas]
        p['texto_editado'] = True
        p['modo'] = 'texto'
    return palco


# ------------------------------------------------------------------ a familia
class Editor:
    """A previa da edicao por familia, para a rota POST /api/familia/previa do servidor da tela.

    ctx, kv: o contexto e a mestre da derivacao; laudo e base: os do palco (desdobra.tela.estado.pecas_base);
    derivados: {id do formato: derivacao/1 em memoria}; brutos: {id do formato: {id da versao: variante do motor}};
    familias: {id da familia: [ids dos formatos membros]}; faces: as faces servidas do job (com o cmap)."""

    def __init__(self, ctx, kv, laudo, base, derivados, brutos, familias, faces, *, specs, arquivo_specs, params):
        from desdobra.derivacao import solver as mod_solver
        from desdobra.tela import estado
        self.ctx, self.kv, self.laudo, self.base = ctx, kv, laudo, base
        self.derivados, self.brutos, self.familias = derivados, brutos, familias
        self.faces = {f['id']: f for f in faces}
        self.kw = {'specs': specs, 'arquivo_specs': arquivo_specs, 'params': params}
        self.por_formato = {f['id']: f for f in ctx['briefing']['formatos']}
        self.kv_por_id = {e['id']: e for e in kv['elementos']}
        self.conteudo = [e['id'] for e in kv['elementos'] if mod_solver.conteudo(e)]
        self.kv_caixas = {e['id']: [float(x) for x in e['caixa']] for e in kv['elementos']}
        self.kv_tamanho = (float(kv['largura']), float(kv['altura']))
        self.nomes = estado._nomes(laudo)
        self._cf = {}
        # a familia com a quebra de linha do rascunho diferente da do briefing (M7b, C3): {chave: {'chave', 'ctx',
        # 'derivados', 'brutos'}}, a mais nova no fim
        self._vivas = {}

    def versoes(self, gid):
        return {vid for fid in self.familias.get(gid, ()) for vid in (self.brutos.get(fid) or {})}

    def _contexto(self, fid, viva=None):
        from desdobra.derivacao import galeria as mg
        from desdobra.derivacao import proposta
        ctx = viva['ctx'] if viva else self.ctx
        derivados = viva['derivados'] if viva else self.derivados
        chave = (fid, viva['chave'] if viva else None)
        if chave not in self._cf:
            # a mestre de onde o membro parte, com a quebra de linha da familia (a mesma da derivacao, M7b, C2)
            mestre = proposta.mestre_do_membro(ctx, self.kv, self.por_formato[fid], derivados.get(fid))
            self._cf[chave] = mg.contexto_do_formato(ctx, mestre, self.por_formato[fid], **self.kw)
        return self._cf[chave]

    def partida(self, fid, versao, viva=None):
        """Os elementos de onde o membro parte: a versao escolhida, a primeira sem falha ou a proposta derivada (a
        mesma regra da derivacao, desdobra.derivacao.proposta.partida). viva: a familia com a quebra nova (_viva)."""
        from desdobra.derivacao import proposta
        derivados, brutos = (viva['derivados'], viva['brutos']) if viva else (self.derivados, self.brutos)
        return proposta.partida(derivados.get(fid), brutos.get(fid), versao)

    def conferir(self, dados):
        """True quando os dados da pagina seguem o formato da edicao (o mesmo esquema do rascunho). As quebras de
        linha, quando vem, seguem as regras do rascunho (desdobra.tela.rascunho._conferir_quebras)."""
        from desdobra import contratos
        from desdobra.tela import rascunho
        if not isinstance(dados, dict) or not set(CAMPOS) <= set(dados) <= set(CAMPOS + CAMPOS_OPCIONAIS):
            return False
        gid, versao, edicoes = dados['familia'], dados['versao'], dados['edicoes']
        if not isinstance(gid, str) or gid not in self.familias:
            return False
        if versao is not None and (not isinstance(versao, str) or versao not in self.versoes(gid)):
            return False
        familia = {'versao': versao, 'confirmada': False, 'edicoes': edicoes}
        if 'quebras' in dados:
            familia['quebras'] = dados['quebras']
        prova = {'esquema': rascunho.ESQUEMA, 'job_id': '0' * 32, 'laudo_sha256': '0' * 64,  # numero-neutro: tamanhos dos ids
                 'origem': 'rascunho', 'atualizado_em': '2026-01-01T00:00:00', 'familias': {gid: familia}}
        try:
            contratos.validar(prova, rascunho.ESQUEMA)
        except contratos.ErroContrato:
            return False
        if not all(e['elemento'] in self.kv_por_id for e in edicoes):
            return False
        return self._quebras_conferem(edicoes, dados.get('quebras') or [])

    def _quebras_conferem(self, edicoes, quebras):
        """Cada quebra num texto do elemento que ela cita, uma por texto, com os indices e as posicoes no texto de
        agora (o do KV, ou o editado pelo DA nas edicoes da familia, decisoes-v1.md, 171)."""
        from desdobra.briefing import modelo as mb
        from desdobra.derivacao import quebras as mq
        camadas = mb.camadas_do_laudo(self.ctx['laudo'])
        vistos = set()
        for q in quebras:
            el, c = self.kv_por_id.get(q['elemento']), camadas.get(q['layer_id'])
            if el is None or q['layer_id'] not in el['layer_ids'] or q['layer_id'] in vistos or c is None or \
                    c.get('tipo') != 'texto':
                return False
            vistos.add(q['layer_id'])
            if mq.conferir_da_familia(c, q['manter'], q['inseridas'], mq.texto_editado(edicoes, q['elemento'])):
                return False
        return True

    def _viva(self, gid, quebras, edicoes, origem):
        """A familia com as quebras de linha do rascunho (M7b, C3), ou None quando elas sao as do briefing (quebras
        None: as do briefing, sem conferir; a previa manda a lista, vazia sem quebra). O briefing em memoria troca as
        quebras da familia pelas do rascunho e leva as edicoes dela (a derivacao so le delas qual texto foi editado: o
        texto editado nao tem medida); a medida vem de
        desdobra.derivacao.medida_quebras.medir, com o cache, so dos textos do KV com quebra; os membros sao derivados
        de novo com ela, e os devolvidos ganham a galeria de novo, como a tela monta na abertura
        (desdobra.tela.estado.galerias). Guardada pela chave das quebras: a proxima edicao na familia parte dela."""
        import json

        from desdobra.briefing import modelo as mb
        from desdobra.briefing import salvar
        from desdobra.derivacao import medida_quebras
        from desdobra.derivacao import nucleo as nd
        from desdobra.derivacao import proposta
        from desdobra.derivacao import quebras as mq
        from desdobra.job import nucleo
        if quebras is None:
            return None
        b = self.ctx['briefing']
        fids = list(self.familias[gid])
        antes = [q for q in b.get('quebras_por_familia') or []
                 if q.get('familia') is not None and set(q.get('formatos') or ()) & set(fids)]
        tipo = origem if origem in (mb.ORIGEM_DA, mb.ORIGEM_FIXTURE) else mb.ORIGEM_DA
        novas = salvar.quebras_da_familia(gid, fids, {'quebras': quebras}, tipo)
        editados = sorted({q['elemento'] for q in quebras if mq.texto_editado(edicoes, q['elemento']) is not None})
        if _assinatura(novas) == _assinatura(antes) and not editados:
            return None
        chave = json.dumps([gid, _assinatura(novas), editados])
        if chave in self._vivas:
            viva = self._vivas.pop(chave)
            self._vivas[chave] = viva
            return viva
        novo = dict(b, quebras_por_familia=[q for q in b.get('quebras_por_familia') or [] if q not in antes] + novas)
        novo['composicoes'] = [c for c in b.get('composicoes') or [] if not set(c['formatos']) & set(fids)] + [
            {'familia': gid, 'formatos': fids, 'versao': None, 'edicoes': list(edicoes), 'confirmada': False,
             'confirmacao': None}]
        a_medir = [n for n, q in zip(novas, quebras) if q['elemento'] not in editados]
        medidas = dict(self.ctx.get('medidas_quebras') or {})
        if a_medir and self.ctx.get('pasta') is not None:
            pasta = self.ctx['pasta']
            medidas.update(medida_quebras.medir(pasta, self.ctx['laudo'], {'quebras_por_familia': a_medir},
                                                nucleo.ler_estado(pasta)))
        # so as quebras e as composicoes mudam: as funcoes resolvidas do contexto continuam valendo
        ctx = dict(self.ctx, briefing=novo, medidas_quebras=medidas)
        derivados = dict(self.derivados)
        derivados.update(nd.derivar_em_memoria(ctx, so=fids, composicoes=False, **self.kw)['formatos'])
        brutos = dict(self.brutos)
        devolvidos = [f for f in fids if derivados[f]['situacao'] == 'devolvido' and
                      (derivados[f].get('devolucao') or {}).get('motivo') not in nd.MOTIVOS_POR_CONFIRMAR]
        if devolvidos:
            por = proposta.galeria_da_familia(ctx, self.kv, [self.por_formato[f] for f in devolvidos], **self.kw)
            brutos.update({f: {v['id']: v for _n, v in por[f]} for f in devolvidos})
        viva = {'chave': chave, 'ctx': ctx, 'derivados': derivados, 'brutos': brutos}
        self._vivas[chave] = viva
        while len(self._vivas) > VIVAS_MAX:
            velha = next(iter(self._vivas))
            del self._vivas[velha]
            self._cf = {k: v for k, v in self._cf.items() if k[1] != velha}
        return viva

    def _texto(self, eid, texto):
        """(texto aceito, recusa ou None) de uma edicao de texto no elemento."""
        el = self.kv_por_id[eid]
        textos = [lid for lid in el['layer_ids'] if (self.base.get(lid) or {}).get('linhas')]
        if len(textos) != 1:
            return None, 'Este elemento não tem um texto só para editar.'
        if not texto.strip():
            return None, 'O texto ficou vazio. Para tirar o elemento, use Apagar.'
        peca = self.base[textos[0]]
        face_id = next((t['face'] for ln in peca['linhas'] for t in ln['trechos'] if t['face']), None)
        face = self.faces.get(face_id)
        if face is None:
            return None, 'A fonte deste texto não está no job, e sem ela a tela não mostra o texto novo.'
        runs = (peca.get('_texto') or {}).get('runs') or [{}]
        faltam = caracteres_que_faltam(texto, face, runs[0].get('font_caps') in ('ALL_CAPS', 'SMALL_CAPS'))
        if faltam:
            return None, _texto_da_recusa(faltam)
        return texto, None

    def previa(self, dados, origem='da'):
        """{'familia', 'versao', 'membros': [{'formato', 'palco', 'falhas', 'avisos', 'validacoes_reprovadas',
        'situacao'}], 'apagados', 'textos_editados', 'recusas', 'alinhados', 'tempo_ms'}, ou None quando os dados
        nao seguem o formato. So previa: nada e gravado."""
        from desdobra.derivacao import proposta
        from desdobra.tela import estado
        if not self.conferir(dados):
            return None
        inicio = time.perf_counter()
        gid, versao = dados['familia'], dados['versao']
        recusas, aceitas = [], []
        for e in dados['edicoes']:
            if e['acao'] == 'texto':
                texto, recusa = self._texto(e['elemento'], e['texto'])
                if recusa is not None:
                    recusas.append({'elemento': e['elemento'], 'texto': recusa})
                    continue
                e = dict(e, texto=texto)
            aceitas.append(e)
        # a quebra de linha do rascunho diferente da do briefing: os membros partem da derivacao com ela (M7b, C3). O
        # pedido sem o campo e o rascunho sem quebra na familia: a previa nunca volta a quebra do briefing de antes,
        # que "Salvar e seguir" tira (revisao do C)
        quebras = dados.get('quebras') or []
        viva = self._viva(gid, quebras, aceitas, origem)
        # o texto editado no palco sai nas linhas da quebra da familia (M7b, C4)
        quebras_por_elemento = {q['elemento']: q for q in quebras}
        membros, apagados_fam, textos_fam, alinhados_fam = [], [], {}, []
        for fid in self.familias[gid]:
            elementos = self.partida(fid, versao, viva)
            if elementos is None:
                continue
            cf = self._contexto(fid, viva)
            W, H = cf['W'], cf['H']
            # a mesma conta da derivacao da familia confirmada (desdobra.derivacao.proposta)
            lay = proposta.layout_do_membro(cf, elementos, aceitas, kv_por_id=self.kv_por_id, conteudo=self.conteudo,
                                            kv_caixas=self.kv_caixas, kv_tamanho=self.kv_tamanho)
            apagados, textos, alinhados = lay['apagados'], lay['textos'], lay['alinhados']
            falhas, avisos, reprovadas, falha = lay['falhas'], lay['avisos'], lay['reprovadas'], lay['falha_solver']
            els = lay['elementos']
            palco = estado.palco_da_variante(fid, W, H, {'elementos': els}, self.laudo, self.base)
            for eid, texto in textos.items():
                trocar_texto(palco, eid, texto, quebras_por_elemento.get(eid))
            membros.append({'formato': fid, 'palco': palco,
                            'falhas': [{'codigo': f['codigo'], 'texto': f['texto']} for f in falhas],
                            'avisos': [{'codigo': a['codigo'], 'texto': a['texto']} for a in avisos],
                            'validacoes_reprovadas': reprovadas,
                            'situacao': 'proposta' if not falha else 'proposta_sem_solver'})
            for k in apagados:
                if k not in apagados_fam:
                    apagados_fam.append(k)
            textos_fam.update(textos)
            alinhados_fam.extend(dict(a, formato=fid) for a in alinhados)
        nome = self._nome
        return {'familia': gid, 'versao': versao, 'membros': membros,
                'apagados': [{'elemento': k, 'nome': nome(k), 'origem': origem} for k in apagados_fam],
                'textos_editados': [{'elemento': k, 'nome': nome(k)} for k in textos_fam],
                'recusas': recusas, 'alinhados': alinhados_fam,
                'textos_da_quebra': self._textos_da_quebra(aceitas),
                'tempo_ms': round((time.perf_counter() - inicio) * POR_MS, CASAS_MS)}

    def _textos_da_quebra(self, edicoes):
        """Os textos que o DA pode quebrar na familia (M7b, C4), na ordem do KV: o elemento com um texto de ponto so
        (a caixa de paragrafo o render refaz na largura dela; o elemento apagado sai), com o texto de agora e as
        posicoes das quebras gravadas e dos espacos (desdobra.derivacao.quebras.texto_para_quebrar). A pagina monta
        o controle da quebra com eles; o texto do cliente vai a ela so por textContent."""
        from desdobra.briefing import modelo as mb
        from desdobra.derivacao import quebras as mq
        camadas = mb.camadas_do_laudo(self.ctx['laudo'])
        apagados = {e['elemento'] for e in edicoes if e['acao'] == 'apagar'}
        saida = []
        for e in self.kv['elementos']:
            textos = [lid for lid in e['layer_ids'] if (camadas.get(lid) or {}).get('tipo') == 'texto']
            if e['id'] in apagados or len(textos) != 1 or \
                    (camadas[textos[0]].get('texto') or {}).get('tipo_caixa') == 'paragrafo':
                continue
            editado = mq.texto_editado(edicoes, e['id'])
            saida.append(dict(mq.texto_para_quebrar(camadas[textos[0]], editado), elemento=e['id'],
                              layer_id=textos[0], editado=editado is not None))
        return saida

    def _nome(self, eid):
        e = self.kv_por_id[eid]
        return self.nomes.get(e.get('raiz')) or ''


def _assinatura(entradas):
    """As quebras de linha de familia (entradas de quebras_por_familia) sem a origem da decisao, em ordem: o texto, os
    indices que ficam, as posicoes inseridas, quem fez e a aprovacao."""
    return sorted([int(q['layer_id']), sorted(q['quebras']['valor']), sorted(q.get('inseridas') or ()),
                   q.get('origem'), bool(q.get('aprovada'))] for q in entradas)
