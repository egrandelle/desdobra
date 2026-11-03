# -*- coding: utf-8 -*-
"""desdobra doctor: confere o ambiente do motor e grava doctor.json (doctor/1).

Doctor do M1 com o que o M2 pede (arquitetura-v1.md, 4.15, 9.2 e 9.3): versao do Python, versoes fixadas do lock,
psd-tools com o extra composite, versao fixada do fontTools, do Playwright, do pypdfium2 (M3) e do kiwisolver (M5), o Chromium fixado na pasta de
navegadores do motor, o carregamento de uma fonte sintetica pelo @font-face com conferencia por CDP, o autoteste do
caminho PDF + PDFium do render com a fonte gerada pelo motor (M4), o isolador (um filho dentro do teto e outro que
estoura) e o teto do modo de dados.

    desdobra [--envelope] [--teto-modo-dados {a,b,c}] doctor [--saida <pasta>] [--sem-isolador] [--sem-chromium]

Sem --saida, o doctor.json vai para a pasta de dados do plugin, quando o motor roda no ambiente criado pelo
gancho; fora dele (desenvolvimento), so com --saida.

Codigos: 0 quando nada falhou (avisos nao contam); 3 (RECUSADO, situacao bloqueado) quando alguma verificacao
falhou; 9 (NAO_DISPONIVEL) quando o unico problema e o isolador que este sistema ainda nao tem.
"""
import datetime
import platform as _platform
import sys
import time
from pathlib import Path

from desdobra import __version__, contratos, plataforma
from desdobra.doctor import verificacoes as v
from desdobra.resultado import Codigo, Resultado

NOME_ARQUIVO = 'doctor.json'


def registrar(subparsers):
    p = subparsers.add_parser('doctor', help='Confere o ambiente do motor e diz o que fazer')
    p.add_argument('--saida', default=None, help='Pasta onde gravar o doctor.json (padrão: pasta de dados do plugin)')
    p.add_argument('--sem-isolador', action='store_true', help='Pula o teste do isolador (só para desenvolvimento)')
    p.add_argument('--sem-chromium', action='store_true',
                   help='Pula o carregamento da fonte de teste no Chromium (só para desenvolvimento)')
    p.set_defaults(executar=executar, nome_comando='doctor')


def rodar_verificacoes(teto, dados, *, com_isolador=True, plat=None, com_chromium=True):
    """Lista de Verificacao e se o sistema nao tem isolador. Uma verificacao que quebra vira falha, nunca excecao."""
    from desdobra.doctor import chromium as vc
    plat = plat or plataforma.obter()
    lista = []
    sem_suporte = False
    passos = [('python', v.verificar_python), ('ambiente_do_plugin', lambda: v.verificar_ambiente(dados)),
              ('versoes_do_lock', lambda: v.verificar_lock(dados)), ('psd_tools_composite', v.verificar_psd_tools),
              ('fonttools', lambda: vc.verificar_versao('fonttools', 'fonttools', 'Versão fixada do fontTools')),
              ('playwright', lambda: vc.verificar_versao('playwright', 'playwright', 'Versão fixada do Playwright')),
              # M3: o PDFium que le as folhas de spec no filho isolado (arquitetura-v1.md, 4.8)
              ('pypdfium2', lambda: vc.verificar_versao('pypdfium2', 'pypdfium2', 'Versão fixada do pypdfium2')),
              # M5: o solver de restricoes da derivacao (arquitetura-v1.md, 4.10)
              ('kiwisolver', lambda: vc.verificar_versao('kiwisolver', 'kiwisolver', 'Versão fixada do kiwisolver')),
              # M5: o HiGHS do scipy, que resolve o layout da derivacao
              ('scipy_highs', v.verificar_highs),
              ('chromium_fixado', vc.verificar_chromium)]
    for ident, passo in passos:
        try:
            lista.append(passo())
        except Exception as e:  # noqa: BLE001 - o doctor sempre termina e diz o que fazer
            lista.append(_quebrou(ident, e))
    if not com_chromium:
        lista.append(v.Verificacao('fonte_no_chromium', 'Fonte no Chromium', situacao='pulado',
                                   detalhe='Pulado com --sem-chromium.'))
        lista.append(v.Verificacao('autoteste_render', 'Autoteste do render', situacao='pulado',
                                   detalhe='Pulado com --sem-chromium.'))
    elif any(x.id == 'chromium_fixado' and x.situacao != 'ok' for x in lista):
        lista.append(v.Verificacao('fonte_no_chromium', 'Fonte no Chromium', situacao='pulado',
                                   detalhe='Pulado: o Chromium fixado não está instalado.'))
        lista.append(v.Verificacao('autoteste_render', 'Autoteste do render', situacao='pulado',
                                   detalhe='Pulado: o Chromium fixado não está instalado.'))
    else:
        try:
            lista.append(vc.verificar_fonte_no_chromium())
        except Exception as e:  # noqa: BLE001
            lista.append(_quebrou('fonte_no_chromium', e))
        # M4: o autoteste do caminho PDF + PDFium roda o filho do render, entao precisa do isolador
        if plat.nome in ('sem-suporte', 'mac'):
            lista.append(v.Verificacao('autoteste_render', 'Autoteste do render', situacao='pulado',
                                       detalhe='Pulado: o isolador do processo do render não existe neste sistema.'))
        else:
            try:
                lista.append(vc.verificar_autoteste_render(plat))
            except Exception as e:  # noqa: BLE001
                lista.append(_quebrou('autoteste_render', e))
    if com_isolador:
        try:
            feitas, sem_suporte = v.verificar_isolador(plat)
            lista.extend(feitas)
        except Exception as e:  # noqa: BLE001
            lista.append(_quebrou('isolador', e))
    else:
        lista.append(v.Verificacao('isolador', 'Isolador', situacao='pulado', detalhe='Pulado com --sem-isolador.'))
    lista.append(v.verificar_teto(teto, dados))
    return lista, sem_suporte


def _quebrou(ident, e):
    return v.Verificacao(ident, 'Verificação %s' % ident, situacao='falha',
                         detalhe='A verificação parou com um erro interno (%s).' % type(e).__name__,
                         o_que_fazer='Rode "desdobra doctor" no terminal, sem --envelope, e mande a saída para a Trezion.')


def resumir(lista):
    contar = lambda s: sum(1 for x in lista if x.situacao == s)  # noqa: E731
    return {'verificacoes': len(lista), 'ok': contar('ok'), 'falhas': contar('falha'), 'avisos': contar('aviso'),
            'pulados': contar('pulado')}


def montar_relatorio(lista, resumo, codigo, teto, dados, plat):
    return {
        'esquema': 'doctor/1', 'motor_versao': __version__,
        'gerado_em': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
        'plataforma': {'sistema': sys.platform, 'isolador': plat.nome, 'python_versao': _platform.python_version(),
                       'python_executavel': sys.executable, 'em_venv': v.em_venv()},
        'pasta_dados': str(dados) if dados is not None else None,
        'teto_modo_dados': teto, 'verificacoes': [x.como_dict() for x in lista], 'resumo': resumo,
        'codigo': int(codigo)}


def executar(args):
    inicio = time.monotonic()
    teto = getattr(args, 'teto_modo_dados', None)
    dados = v.pasta_dados()
    plat = plataforma.obter()
    lista, sem_suporte = rodar_verificacoes(teto, dados, com_isolador=not args.sem_isolador, plat=plat,
                                            com_chromium=not getattr(args, 'sem_chromium', False))
    resumo = resumir(lista)
    falhas = [x for x in lista if x.situacao == 'falha']
    so_isolador = all(x.id.startswith('isolador') for x in falhas)
    if not falhas:
        codigo, situacao = Codigo.OK, 'ok'
        o_que_fazer = ('O ambiente está pronto para criar um job.' if not resumo['avisos'] else
                       'O ambiente passou, com avisos. Veja o doctor.json antes de criar um job.')
    elif sem_suporte and so_isolador:
        codigo, situacao = Codigo.NAO_DISPONIVEL, 'nao_disponivel'
        o_que_fazer = ' '.join(dict.fromkeys(x.o_que_fazer for x in falhas if x.o_que_fazer))
    else:
        codigo, situacao = Codigo.RECUSADO, 'bloqueado'
        o_que_fazer = ' '.join(dict.fromkeys(x.o_que_fazer for x in falhas if x.o_que_fazer))

    pasta_saida = Path(args.saida) if args.saida else dados
    linhas = ['[%s] %s: %s' % (x.situacao, x.titulo, x.detalhe) for x in lista]
    if pasta_saida is not None:
        relatorio = montar_relatorio(lista, resumo, codigo, teto, dados, plat)
        pasta_saida.mkdir(parents=True, exist_ok=True)
        contratos.gravar(pasta_saida / NOME_ARQUIVO, relatorio, 'doctor/1')
        linhas.append('Relatório gravado em %s.' % (pasta_saida / NOME_ARQUIVO))
    else:
        linhas.append('Sem pasta de dados do plugin: o doctor.json só é gravado com --saida.')

    numeros = {'tempo_s': round(time.monotonic() - inicio, 3)}
    for x in lista:
        if x.id.startswith('isolador_') and 'pico_bytes' in x.numeros:
            numeros['%s_pico_bytes' % x.id] = x.numeros['pico_bytes']
    return Resultado(comando='doctor', codigo=int(codigo), situacao=situacao, o_que_fazer=o_que_fazer,
                     contagens=resumo, numeros=numeros, linhas_humanas=linhas)
