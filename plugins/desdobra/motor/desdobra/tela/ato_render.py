# -*- coding: utf-8 -*-
"""O ato de render da tela (M7b, passo B2 do plano e a critica dele; decisoes do Duda Q3, Q4 e Q14).

Um clique do DA pede o render dos formatos que a pagina mostra como afetados, com uma confirmacao so:
  - validar (no fio do pedido, barato): os dados sao {'formatos': [ids]}, uma lista sem repeticao de formatos do
    briefing;
  - preparar (desdobra.tela.servidor.Ato.preparar: tarefa no fio de trabalho, com a trava do job e fora da trava de
    escrita): monta o contrato de cada formato como o render monta (desdobra.render.execucao.montar_contrato). Formato
    com bloqueio para o preparo (formato_bloqueado), sem dialogo. Senao, o texto da confirmacao diz os formatos e cada
    decisao que o contrato pede ao DA (pede_confirmacao), em portugues para o DA; a impressao de cada contrato e os
    aceites ficam so no pedido pendente do servidor;
  - executar (o Confirmar: Ato.longo com selo_por_formato): a confirmacao do DA emite um Disparo por formato, preso a
    ele (humano.exigir_tela com alvo). Na tarefa, com a trava do job, o contrato de cada formato e montado de novo e
    comparado com o confirmado: o que mudou (o contrato ou as decisoes) nao vai para o render, e o selo dele e gasto.
    Os outros vao, um por vez, cada um com o proprio selo (execucao.renderizar, com o progresso e o parar da tarefa).
    Cancelar corta o formato em andamento entre etapas, e os prontos ficam renderizados. O formato que mudou, parou ou
    foi cortado pede render de novo.
O render nunca parte sozinho depois de uma correcao (Q3): so este ato, com a confirmacao do DA na janela, o dispara.
O ato usa o comando 'render' de humano.COMANDOS (a critica do plano: nada novo em ATOS_DA_TELA nem no gancho).
Os textos sao do motor, sem comando, sem nome de arquivo e sem codigo; o formato aparece pela medida dele.
"""
import hashlib
import json
from pathlib import Path

from desdobra.tela import tarefas

COMANDO = 'render'
TAREFA_PEDIDO = tarefas.TAREFA_PREPARO
TITULO = 'Renderizar os formatos'
SIM = 'Confirmar'
NAO = 'Cancelar'
MOTIVO_BLOQUEADO = 'formato_bloqueado'
MOTIVO_MUDOU = 'contrato_mudou'
# as decisoes que o contrato pede ao DA (desdobra.render.contrato e desdobra.render.derivado, pede_confirmacao), ditas
# para o DA. A descricao do motor fala com a Trezion e cita o terminal; esta nunca
DECISOES = {
    'largura_divergente': 'A largura de um texto não bate com a da fonte enviada. O texto pode sair um pouco mais '
                          'largo ou mais estreito que no arquivo original.',
    'efeito_sobre_texto_sem_aplicar': 'Um ajuste de cor ou uma mesclagem fica acima de um texto. No render, esse '
                                      'efeito não pega o texto.',
    'clipping_dividido_por_texto': 'Uma camada recortada fica acima de um texto recortado na mesma base. No render, '
                                   'essa camada não aparece.',
    'mesclagem_sem_o_fundo_de_outro_elemento': 'Uma camada usa um modo de mesclagem. No render, a mesclagem não pega '
                                               'os elementos de baixo.',
}
DECISAO_SEM_TEXTO = 'Há uma diferença que pede a sua decisão antes do render.'
AVISO_TEMPO = 'O render leva alguns minutos. A edição fica parada até ele terminar.'
ACEITE = 'Ao confirmar, você aceita o render com essas diferenças.'


class ErroAtoRender(Exception):
    """O preparo ou o lote nao foram inteiros. motivo: codigo curto (a tela mostra o texto do motor para ele);
    resposta: o que a tela mostra junto (os formatos bloqueados, os que mudaram)."""

    def __init__(self, mensagem, motivo, resposta=None):
        super().__init__(mensagem)
        self.motivo, self.resposta = motivo, resposta


def impressao(contrato):
    """O sha256 do contrato em JSON canonico: o mesmo contrato montado de novo da a mesma impressao."""
    return hashlib.sha256(json.dumps(contrato, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def _lista(nomes):
    return nomes[0] if len(nomes) == 1 else '%s e %s' % (', '.join(nomes[:-1]), nomes[-1])


def texto_da_confirmacao(itens):
    """O texto do dialogo: os formatos, o tempo e cada decisao pedida, agrupada pelos formatos que a pedem.
    itens: [{'id', 'nome', 'decisoes': [codigos]}], na ordem do pedido."""
    nomes = [i['nome'] for i in itens]
    if len(nomes) == 1:
        partes = ['O formato %s vai para o render.' % nomes[0]]
    else:
        partes = ['Os formatos %s vão para o render.' % _lista(nomes)]
    partes.append(AVISO_TEMPO)
    grupos = {}
    for i in itens:
        for codigo in i['decisoes']:
            grupos.setdefault(codigo, []).append(i['nome'])
    for codigo, ns in grupos.items():
        frase = DECISOES.get(codigo, DECISAO_SEM_TEXTO)
        inicio = 'No formato %s, ' % ns[0] if len(ns) == 1 else 'Nos formatos %s, ' % _lista(ns)
        partes.append(inicio + frase[0].lower() + frase[1:])
    if grupos:
        partes.append(ACEITE)
    return ' '.join(partes)


def _formatos_do_briefing(pasta):
    """{id: nome para o DA} dos formatos do briefing confirmado, na ordem dele ({} sem briefing legivel). O nome e a
    medida (a mesma da tela); duas medidas iguais levam o id junto."""
    from desdobra import contratos
    from desdobra.briefing import modelo as mb
    try:
        b = mb.ler(pasta)
    except (contratos.ErroContrato, OSError, ValueError):
        return {}
    fs = [f for f in (b or {}).get('formatos') or [] if isinstance(f, dict) and isinstance(f.get('id'), str)]
    medidas = ['%sx%s' % (f.get('largura'), f.get('altura')) for f in fs]
    return {f['id']: m if medidas.count(m) == 1 else '%s (%s)' % (m, f['id']) for f, m in zip(fs, medidas)}


def ato_de_render(pasta):
    """O Ato "Renderizar os formatos" do servidor da tela do job em `pasta`."""
    from desdobra.tela.servidor import Ato
    pasta = Path(pasta).resolve()

    def valido(d):
        if not isinstance(d, dict) or set(d) != {'formatos'} or not isinstance(d['formatos'], list):
            return False
        fs = d['formatos']
        if not fs or not all(isinstance(f, str) for f in fs) or len(set(fs)) != len(fs):
            return False
        do_briefing = _formatos_do_briefing(pasta)
        return all(f in do_briefing for f in fs)

    def preparar(d, tarefa):
        from desdobra.render import execucao
        nomes = _formatos_do_briefing(pasta)
        itens, bloqueados, guardado = [], [], {}
        for f in d['formatos']:
            if tarefa.parar():
                raise ErroAtoRender('O preparo foi parado.', tarefas.MOTIVO_PARADO)
            tarefa.progresso('contrato')
            contrato, bloqueios, confirmar = execucao.montar_contrato(pasta, f)
            nome = nomes.get(f, f)
            if bloqueios or contrato is None:
                bloqueados.append({'id': f, 'nome': nome})
                continue
            aceites = sorted({c['codigo'] for c in confirmar})
            guardado[f] = {'contrato': impressao(contrato), 'aceites': aceites}
            itens.append({'id': f, 'nome': nome, 'decisoes': aceites})
        if bloqueados:
            raise ErroAtoRender('Um formato tem bloqueio.', MOTIVO_BLOQUEADO, resposta={'bloqueados': bloqueados})
        decisoes = {}
        for i in itens:
            for codigo in i['decisoes']:
                decisoes.setdefault(codigo, []).append(i['id'])
        vista = {'formatos': [{'id': i['id'], 'nome': i['nome']} for i in itens],
                 'decisoes': [{'codigo': c, 'formatos': fs, 'texto': DECISOES.get(c, DECISAO_SEM_TEXTO)}
                              for c, fs in decisoes.items()]}
        return {'texto': texto_da_confirmacao(itens), 'vista': vista, 'guardado': guardado}

    def executar(disparos, d, tarefa, preparado):
        from desdobra import humano
        from desdobra.job import nucleo
        from desdobra.render import execucao
        feitos, mudaram, pararam, tempos = [], [], {}, {}
        cortou = False  # o Cancelar (ou o fechar da janela) cortou o lote antes do fim
        for f in d['formatos']:
            if tarefa.parar():
                cortou = True
                break
            disparo, esperado = disparos[f], preparado[f]
            tarefa.progresso('contrato', f)
            # o contrato de agora, com a trava do job: o DA confirmou o que o preparo mostrou, e so isso vai ao render
            contrato, bloqueios, confirmar = execucao.montar_contrato(pasta, f)
            if bloqueios or contrato is None or impressao(contrato) != esperado['contrato'] or \
                    sorted({c['codigo'] for c in confirmar}) != esperado['aceites']:
                humano.gastar(disparo)
                mudaram.append(f)
                nucleo.registrar_evento(pasta, 'render_parou', formato=f, motivo=MOTIVO_MUDOU, meio=disparo.meio)
                continue
            try:
                rel = execucao.renderizar(pasta, disparo=disparo, aceites=esperado['aceites'], formato=f,
                                          progresso=lambda etapa, f=f: tarefa.progresso(etapa, f), parar=tarefa.parar)
            except execucao.ErroRender as e:
                nucleo.registrar_evento(pasta, 'render_parou', formato=f, motivo=e.motivo, codigo=int(e.codigo),
                                        meio=disparo.meio)
                if e.motivo == tarefas.MOTIVO_PARADO and tarefa.parar():
                    cortou = True
                    break  # o DA cancelou: o formato cortado pede render de novo, e os prontos ficam
                pararam[f] = e.motivo
                continue
            tarefa.feito(f)
            feitos.append(f)
            tempos[f] = rel['tempo_s']
            nucleo.registrar_evento(pasta, 'render_concluido', formato=f, tempo_s=rel['tempo_s'],
                                    n_textos=rel['textos']['camadas'], n_paginas_pdf=rel['textos']['paginas_pdf'],
                                    meio=disparo.meio)
        resposta = {'feitos': feitos, 'mudaram': mudaram, 'pararam': pararam, 'tempos_s': tempos}
        # o Cancelar que chegou depois do ultimo formato nao esconde o formato que mudou ou parou por um problema
        if not cortou and (mudaram or pararam):
            motivo = next(iter(pararam.values())) if pararam else MOTIVO_MUDOU
            raise ErroAtoRender('Nem todo formato saiu do render.', motivo, resposta=resposta)
        return resposta

    return Ato(comando=COMANDO, titulo=TITULO, texto='', sim=SIM, nao=NAO, executar=executar, validar=valido,
               longo=True, formatos=lambda d: list(d['formatos']), preparar=preparar, selo_por_formato=True)
