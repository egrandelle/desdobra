# -*- coding: utf-8 -*-
"""Fontes do job (M2): a entrada entrada/fontes/, a conferencia contra o arquivo enviado e a segunda passada do laudo.

A agencia envia o arquivo de cada fonte usada no PSD (decisoes-v1.md, arquitetura 1), em OTF, TTF, TTC, WOFF ou
WOFF2 (arquitetura 14). Variable font, Type 1 e pacote ficam de fora. O arquivo e lido so no processo filho
isolado (desdobra.fontes.filho, com o fontTools, arquitetura 15) e chega ao Chromium so pela rota propria do
servidor local (desdobra.chromium.servidor).

Comandos (fases da esteira, com --job):
    desdobra fontes conferir --job <pasta>   grava fontes/conferencia.json
    desdobra fontes laudo --job <pasta>      grava laudo/laudo-fontes.json (laudo/1, passada 2, regra B3)
"""
import argparse
from pathlib import Path

from desdobra import arquivos, contratos
from desdobra.resultado import Codigo, Resultado

ARQUIVO_LAUDO_FONTES = Path('laudo') / 'laudo-fontes.json'
MENSAGENS_RECUSA = {
    'pacote': 'O arquivo é um pacote (zip, tar ou comprimido). Fonte entra solta, um arquivo por face.',
    'type1': 'Fonte Type 1 fica fora da v1.',
    'formato_nao_aceito': 'O formato da fonte não é aceito: só OTF, TTF, TTC, WOFF e WOFF2.',
    'nao_abre': 'O arquivo tem extensão de fonte, mas não começa com a assinatura de um formato aceito.',
    'nao_e_fonte': 'O arquivo não é um arquivo de fonte.',
    'variavel': 'Variable font (tabela fvar) fica fora da v1.',
    'malformada': 'O arquivo de fonte não abre: a estrutura não bate com o formato.',
    'formato': 'O arquivo não começa com a assinatura de OTF, TTF, TTC, WOFF ou WOFF2.',
    'memoria': 'A leitura da fonte passou do orçamento de memória.',
    'tempo': 'A leitura da fonte passou do tempo máximo.',
    'queda': 'O processo de leitura da fonte caiu.',
    'auditoria': 'O processo de leitura da fonte tentou uma ação que o desdobra não permite e foi parado.',
    'plataforma': 'O isolamento do processo de leitura não está disponível neste sistema.',
    'bug': 'O processo de leitura da fonte terminou com erro interno.',
}
O_QUE_FAZER_RECUSA = ('Passe em --fontes só arquivos de fonte soltos, em OTF, TTF, TTC, WOFF ou WOFF2, sem variable '
                      'font, Type 1 nem pacote, e crie o job de novo (ou troque com "desdobra job trocar-entrada").')


def validar_arquivo(caminho, pasta_trabalho, *, plat=None):
    """Confere um arquivo oferecido para entrada/fontes/: assinatura no processo principal e leitura das tabelas
    no filho isolado. Devolve (formato, None) ou (None, codigo da recusa). pasta_trabalho e apagada no fim."""
    import shutil
    from desdobra.fontes import leitura
    formato, recusa = arquivos.classificar_fonte(caminho)
    if recusa:
        return None, recusa
    pasta_trabalho = Path(pasta_trabalho)
    try:
        r = leitura.ler(caminho, pasta_trabalho / 'saida', pasta_trabalho / 'trabalho', plat=plat)
    finally:
        shutil.rmtree(pasta_trabalho, ignore_errors=True)
    if r['situacao'] != 'lida':
        return None, r['recusa']['tipo']
    return formato, None


# ------------------------------------------------------------------ CLI

def _aceitar_tetos(p):
    """O job proxima repassa --teto-memoria-bytes e --tempo-max-s a toda fase; as fases de fonte aceitam e ignoram
    (o orcamento do filho de fonte e o tempo do Chromium vem do registro de limites)."""
    p.add_argument('--teto-memoria-bytes', type=int, default=None, help=argparse.SUPPRESS)
    p.add_argument('--tempo-max-s', type=float, default=None, help=argparse.SUPPRESS)


def registrar(subparsers):
    p = subparsers.add_parser('fontes', help='Confere as fontes do job contra os arquivos de entrada/fontes/')
    sub = p.add_subparsers(dest='acao_fontes', metavar='ACAO', required=True)
    c = sub.add_parser('conferir', help='Par de nome PostScript, glifos, Chromium e largura por linha')
    c.add_argument('--job', required=True, help='Pasta do job')
    c.add_argument('--sem-chromium', action='store_true', help='Só para diagnóstico: pula a parte do Chromium')
    _aceitar_tetos(c)
    c.set_defaults(executar=_conferir, nome_comando='fontes conferir')
    lau = sub.add_parser('laudo', help='Segunda passada do laudo: a regra B3 com a conferência de fontes')
    lau.add_argument('--job', required=True, help='Pasta do job')
    _aceitar_tetos(lau)
    lau.set_defaults(executar=_laudo, nome_comando='fontes laudo')


def _uso(comando, texto):
    return Resultado(comando=comando, codigo=int(Codigo.USO), situacao='erro', o_que_fazer=texto)


def _conferir(args):
    from desdobra.fontes import conferencia
    pasta = Path(args.job).resolve()
    if not (pasta / 'estado.json').is_file() or not (pasta / 'laudo' / 'laudo.json').is_file():
        return _uso('fontes conferir', 'Rode a conferência numa pasta de job com laudo/laudo.json ("desdobra job proxima").')
    conf = conferencia.conferir(pasta, usar_chromium=not args.sem_chromium)
    r = conf['resumo']
    bloqueio = r['faces_bloqueantes'] or r['camadas_bloqueantes'] or r['arquivos_recusados']
    contagens = {k: v for k, v in r.items() if isinstance(v, int)}
    contagens['chromium_feito'] = int(conf['chromium']['feito'])
    contagens['fontes_fora_da_entrada'] = conf['varredura']['arquivos_de_fonte_fora_da_entrada']
    linhas = ['Conferência de fontes: %d face(s), %d bloqueante(s); %d par(es) de camada, %d bloqueante(s).' % (
        r['faces'], r['faces_bloqueantes'], r['camadas'], r['camadas_bloqueantes'])]
    if conf['cache']['copias_encontradas'] is not None:
        linhas.append('Cópias da fonte no perfil do Chromium: %d.' % conf['cache']['copias_encontradas'])
        if not conf['cache']['feito']:
            linhas.append('O teste de cache não provou que o perfil do Chromium grava cache (o controle positivo não '
                          'apareceu): a contagem de cópias fica sem prova.')
    return Resultado(comando='fontes conferir', codigo=int(Codigo.OK),
                     situacao='ok_com_bloqueio' if bloqueio else 'ok', fase='fontes',
                     o_que_fazer=conferencia.O_QUE_FAZER_BLOQUEIO if bloqueio else conferencia.O_QUE_FAZER_OK,
                     contagens=contagens, ids={'conferencia_sha256': conferencia.sha256(pasta)},
                     numeros={'largura_erro_max_pct': r['largura_erro_max_pct']}, pasta_job=pasta,
                     linhas_humanas=linhas)


def _laudo(args):
    from desdobra.fontes import conferencia
    from desdobra.laudo import fontes as segunda
    from desdobra.sugestao import pacote
    pasta = Path(args.job).resolve()
    arq_conf = pasta / conferencia.ARQUIVO
    arq_laudo = pasta / 'laudo' / 'laudo.json'
    if not arq_conf.is_file() or not arq_laudo.is_file():
        return _uso('fontes laudo', 'A segunda passada precisa de laudo/laudo.json e fontes/conferencia.json.')
    laudo = contratos.ler(arq_laudo, 'laudo/1')
    conf = contratos.ler(arq_conf, conferencia.ESQUEMA)
    novo = segunda.aplicar_conferencia(laudo, conf, arquivos.sha256_arquivo(arq_conf), arquivos.sha256_arquivo(arq_laudo))
    contratos.gravar(pasta / ARQUIVO_LAUDO_FONTES, novo, 'laudo/1')
    res = novo['resumo']
    bloqueio = res['por_situacao']['bloqueante'] > 0 or res.get('bloqueios_documento', 0) > 0
    return Resultado(comando='fontes laudo', situacao='ok_com_bloqueio' if bloqueio else 'ok', fase='laudo-fontes',
                     o_que_fazer=('O laudo com a conferência de fontes está em laudo/laudo-fontes.json, com camadas '
                                  'bloqueantes para o DA decidir.' if bloqueio else
                                  'O laudo com a conferência de fontes está em laudo/laudo-fontes.json.'),
                     contagens={'camadas': res['n_camadas'], 'lidas': res['por_situacao']['lida'],
                                'degradadas': res['por_situacao']['degradada'],
                                'bloqueantes': res['por_situacao']['bloqueante'], 'b3_fontes': res['n_b3_fontes'],
                                'fontes_presentes': sum(1 for f in novo['fontes_usadas'] if f['situacao'] == 'presente'),
                                'fontes_ausentes': sum(1 for f in novo['fontes_usadas'] if f['situacao'] == 'ausente'),
                                'fontes_divergentes': sum(1 for f in novo['fontes_usadas'] if f['situacao'] == 'divergente'),
                                'camadas_com_fonte_nao_conferida': res.get('n_fonte_nao_conferida', 0)},
                     ids={'conferencia_sha256': novo['conferencia_fontes']['sha256'],
                          'arquivo_sha256': novo['origem']['sha256']},
                     conteudo=pacote.conteudo_para_resultado(novo), pasta_job=pasta,
                     linhas_humanas=['Laudo da segunda passada gravado: %d camada(s) com B3 de fonte.' % res['n_b3_fontes']])
