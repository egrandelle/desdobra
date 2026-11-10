# -*- coding: utf-8 -*-
"""desdobra tela abrir: abre a tela de briefing do job (M7a0, fatia a2; M7a, fatia 1, com o rascunho e os atos).

    desdobra tela abrir --job <pasta>

Quem roda e o Claude, pela skill (decisoes-v1.md, n 159: o DA nunca roda nada num terminal). Por isso este comando
nao e humano (fica fora de desdobra.humano.COMANDOS e do gancho) e nao grava nada do job alem dos eventos. O que a
tela grava (o rascunho, os atos que o DA confirma na janela e o cronometro da mestre em medicoes/tela.json) grava o
processo de fundo, pelo servidor da tela (desdobra.tela.servidor), nunca este comando. Ele:
  - confere a pasta do job e o Chromium com janela fixado (doctor.chromium.verificar_chromium_janela);
  - solta o processo de fundo (desdobra.tela.processo), sem segredo na linha de comando, sem console visivel e fora
    do grupo de processos de quem chamou;
  - espera a linha de aviso do fundo ("pronto" ou "recusado <motivo>") por no maximo tela.partida_max_s e volta. A
    janela fica aberta com o DA; o fundo sai sozinho quando ele a fecha, e o perfil temporario e apagado.

O token da entrada e a sessao do cookie nunca passam por aqui: nascem no processo de fundo e vao so ao Chromium que ele
abre. A saida, o envelope e os eventos levam so fatos sem segredo (tela aberta, o job, o motivo da recusa).

O fundo nasce com ambiente por lista de permissao (ambiente_do_fundo, revisao do M7a0): o ambiente de quem chama e do
Claude, e o driver do Playwright copia o ambiente do processo inteiro. DEBUG e DEBUG_FILE gravariam a URL de entrada e
os cabecalhos do protocolo num arquivo, NODE_OPTIONS rodaria codigo no driver que segura o Chromium; nada disso passa.
No ambiente do plugin, a pasta dos navegadores e sempre a da pasta de dados do plugin, nunca a da variavel de quem
chama (pasta_navegadores_da_tela). Risco declarado: o executavel do Chromium e conferido pelo layout e pelo manifesto
da versao (doctor), sem hash; trocar os arquivos da pasta de dados do plugin e coisa de um processo do mesmo usuario.
"""
import os
import subprocess
import sys
import threading
from pathlib import Path

from desdobra import limites
from desdobra.resultado import Codigo, Resultado

O_QUE_FAZER_ABERTA = ('A tela de briefing abriu numa janela do navegador do desdobra. O que o DA escolhe nela fica '
                      'salvo sozinho no rascunho do job, que não vale como briefing confirmado. O modo de dados do '
                      'job é escolhido pelo DA no passo 1 da tela; até lá, o job fica no modo c. Peça ao DA para '
                      'trabalhar nas abas e fechar a janela quando terminar; ao fechar, o desdobra apaga a pasta '
                      'temporária do navegador.')
O_QUE_FAZER_RECUSA = {
    'nao_e_job': 'A pasta não é um job do desdobra. Confira a pasta ou crie o job com "desdobra job criar".',
    'job_ocupado': 'Outro comando do desdobra está usando este job. Espere ele terminar e abra a tela de novo.',
    'sem_briefing': 'O job ainda não tem briefing para a tela mostrar. No M7a0 a tela mostra o briefing de teste '
                    '("desdobra briefing importar --teste <arquivo> --job <pasta>").',
    'briefing_rascunho': 'O briefing gravado é um rascunho, sem decisões. A tela do M7a0 mostra só um briefing '
                         'completo, como o de teste.',
    'briefing_desatualizado': 'O briefing é de outra versão do laudo, das specs, do design system ou das fontes. '
                              'Importe o briefing de teste de novo.',
    'briefing_com_problema': 'O briefing tem decisão pendente ou incompleta. Rode "desdobra briefing funcoes --job '
                             '<pasta>" para ver as contagens.',
    'briefing_invalido': 'O briefing não segue o contrato briefing/1.',
    'fases_desatualizadas': 'Uma fase do job está desatualizada. Rode "desdobra job proxima <pasta> --todas".',
    'entrada_alterada_fora_do_motor': 'Uma entrada congelada do job mudou fora do desdobra.',
    'sem_chromium_com_janela': 'O navegador com janela do desdobra não está instalado. Rode o doctor do desdobra, '
                               'que diz como pedir o aval do DA para o download.',
    'chromium_nao_abriu': 'O navegador com janela não abriu. Rode o doctor do desdobra e tente de novo.',
    'tela_nao_respondeu': 'A tela não respondeu a tempo e foi fechada. Rode o doctor do desdobra e tente de novo.',
    'erro_interno': 'Erro interno do desdobra ao abrir a tela. Rode o doctor do desdobra e mande o doctor.json para a '
                    'Trezion se voltar.',
    'uso': 'Erro interno do desdobra ao abrir a tela (argumentos do processo de fundo).',
}
CODIGO_DA_RECUSA = {'tela_nao_respondeu': Codigo.ORCAMENTO, 'erro_interno': Codigo.ERRO_INTERNO,
                    'uso': Codigo.ERRO_INTERNO, 'job_ocupado': Codigo.OCUPADO}


# variaveis do ambiente de quem chama que o fundo recebe: so as do sistema, do usuario e das pastas que o Windows, o
# Python, o driver do Playwright (node) e o Chromium leem. O resto (DEBUG*, NODE_*, PW*, PLAYWRIGHT_*, as do Claude,
# tokens e configuracao do usuario) fica de fora
VARIAVEIS_DO_FUNDO = ('SYSTEMROOT', 'SYSTEMDRIVE', 'WINDIR', 'TEMP', 'TMP', 'PATHEXT', 'COMSPEC', 'NUMBER_OF_PROCESSORS',
                      'PROCESSOR_ARCHITECTURE', 'PROCESSOR_IDENTIFIER', 'OS', 'USERPROFILE', 'LOCALAPPDATA', 'APPDATA',
                      'HOMEDRIVE', 'HOMEPATH', 'USERNAME', 'USERDOMAIN', 'COMPUTERNAME', 'PROGRAMDATA', 'PROGRAMFILES',
                      'PROGRAMFILES(X86)', 'PROGRAMW6432', 'COMMONPROGRAMFILES', 'PUBLIC', 'ALLUSERSPROFILE',
                      'HOME', 'USER', 'LOGNAME', 'TMPDIR', 'LANG', 'LC_ALL', 'DISPLAY', 'WAYLAND_DISPLAY',
                      'XDG_RUNTIME_DIR', 'XAUTHORITY')


def pasta_navegadores_da_tela():
    """Pasta dos navegadores do Playwright que a tela usa: no ambiente do plugin, sempre DATA/ms-playwright; fora dele
    (desenvolvimento e testes), a do motor (variavel ou padrao do Playwright)."""
    from desdobra import chromium
    dados = chromium.pasta_dados_do_plugin()
    if dados is not None:
        return dados / chromium.PASTA_NAVEGADORES
    return chromium.pasta_navegadores() or chromium.pasta_padrao_do_playwright()


def _path_minimo():
    """PATH do fundo: a pasta do Python e as pastas do sistema."""
    pastas = [os.path.dirname(sys.executable)]
    if sys.platform == 'win32':
        raiz = os.environ.get('SYSTEMROOT') or os.environ.get('WINDIR') or 'C:\\Windows'
        pastas += [os.path.join(raiz, 'System32'), raiz]
    else:
        pastas += ['/usr/bin', '/bin']
    return os.pathsep.join(pastas)


def ambiente_do_fundo():
    """Ambiente do processo de fundo, montado do zero: VARIAVEIS_DO_FUNDO, o PATH minimo e a pasta dos navegadores."""
    from desdobra import chromium
    env = {}
    for k, v in os.environ.items():
        if k.upper() in VARIAVEIS_DO_FUNDO:
            env[k] = v
    env['PATH'] = _path_minimo()
    env[chromium.VARIAVEL_NAVEGADORES] = str(pasta_navegadores_da_tela())
    return env


def registrar(subparsers):
    p = subparsers.add_parser('tela', help='Tela de briefing do job')
    sub = p.add_subparsers(dest='acao_tela', metavar='ACAO', required=True)
    a = sub.add_parser('abrir', help='Abre a tela do job numa janela do navegador do desdobra e volta')
    a.add_argument('--job', required=True, help='Pasta do job')
    a.set_defaults(executar=_abrir, nome_comando='tela abrir')


def comando_do_filho(pasta, teto=None):
    """A linha de comando do processo de fundo: so o modulo, a pasta e o teto do modo de dados, nenhum segredo."""
    argv = [sys.executable, '-I', '-B', '-m', 'desdobra.tela.processo', '--job', str(pasta)]
    return argv + ['--teto', teto] if teto else argv


def _janela_presente():
    """O Chromium com janela fixado esta na pasta que o fundo vai usar (o doctor so avisa quando ele falta, porque o
    download e opcional; a tela nao abre sem ele)."""
    from desdobra.doctor import chromium as vc
    return vc.verificar_chromium_janela(pasta_navegadores_da_tela()).situacao == 'ok'


def _espera_s():
    return float(limites.valor('tela.partida_max_s'))


def _soltar(argv):
    """Processo de fundo solto de quem chamou: saida padrao num pipe so para a linha de aviso, entrada e erro no nulo,
    sem console visivel e num grupo de processos proprio. No Windows, tenta sair do Job Object de quem chamou (o
    terminal do Claude pode fechar a arvore dele no fim do comando); quando o job nao deixa, segue dentro dele."""
    base = dict(stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, close_fds=True,
                env=ambiente_do_fundo())
    if sys.platform != 'win32':
        return subprocess.Popen(argv, start_new_session=True, **base)
    criacao = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        return subprocess.Popen(argv, creationflags=criacao | subprocess.CREATE_BREAKAWAY_FROM_JOB, **base)
    except OSError:
        return subprocess.Popen(argv, creationflags=criacao, **base)


def _ler_aviso(proc, espera_s):
    """A linha de aviso do fundo, ou None quando ela nao chega a tempo."""
    caixa = []

    def ler():
        try:
            caixa.append(proc.stdout.readline())
        except (OSError, ValueError):
            caixa.append(b'')

    fio = threading.Thread(target=ler, daemon=True)
    fio.start()
    fio.join(espera_s)
    if not caixa:
        return None
    return caixa[0].decode('ascii', 'replace').strip()


def _encerrar(proc, pasta):
    """Mata o processo de fundo e os descendentes dele. A morta forcada nao roda o __exit__ da trava do job
    (job.nucleo.Trava): a trava que um dos mortos gravou (o PID dele dentro) sai aqui; a de outro processo fica."""
    import signal

    from desdobra.chromium import processos
    mortos = {int(proc.pid)}
    for pid, _nome in reversed(processos.descendentes(proc.pid)):
        mortos.add(int(pid))
        try:
            os.kill(pid, signal.SIGTERM)  # no Windows e TerminateProcess
        except OSError:
            pass
    if proc.poll() is None:
        proc.kill()
    try:
        proc.wait(timeout=_espera_s())
    except subprocess.TimeoutExpired:
        pass
    _tirar_trava_dos_mortos(pasta, mortos)


def _tirar_trava_dos_mortos(pasta, mortos):
    from desdobra.job import nucleo
    trava = Path(pasta) / nucleo.ARQUIVO_TRAVA
    try:
        dono = int(trava.read_text(encoding='ascii').strip())
    except (OSError, ValueError):
        return
    if dono in mortos:
        try:
            trava.unlink()
        except OSError:
            pass


def _recusa(pasta, motivo, linhas=None):
    codigo = CODIGO_DA_RECUSA.get(motivo, Codigo.RECUSADO)
    situacao = 'recusado' if codigo == Codigo.RECUSADO or codigo == Codigo.OCUPADO else 'erro'
    return Resultado(comando='tela abrir', codigo=int(codigo), situacao=situacao, fase='tela', pasta_job=pasta,
                     o_que_fazer=O_QUE_FAZER_RECUSA.get(motivo, O_QUE_FAZER_RECUSA['erro_interno']),
                     contagens={'recusa_%s' % motivo: 1},
                     linhas_humanas=linhas or ['A tela não abriu (%s).' % motivo])


def _abrir(args):
    from desdobra.job import nucleo
    pasta = Path(args.job).resolve()
    if not (pasta / nucleo.ARQUIVO_ESTADO).is_file():
        return Resultado(comando='tela abrir', codigo=int(Codigo.USO), situacao='erro',
                         o_que_fazer=O_QUE_FAZER_RECUSA['nao_e_job'], linhas_humanas=['A pasta não é um job.'])
    if not _janela_presente():
        return _recusa(pasta, 'sem_chromium_com_janela')
    teto = getattr(args, 'teto_modo_dados', None)
    proc = _soltar(comando_do_filho(pasta, teto) if teto else comando_do_filho(pasta))
    aviso = _ler_aviso(proc, _espera_s())
    if not aviso:
        # sem aviso a tempo (ou o fundo saiu calado): o fundo e encerrado com os filhos dele (o Python de verdade, sob
        # o lancador do venv); a amarra dele leva o Chromium junto. O pipe fica com o fio de leitura, que e daemon:
        # fechar o pipe aqui esperaria a leitura presa
        _encerrar(proc, pasta)
        return _recusa(pasta, 'tela_nao_respondeu')
    try:
        proc.stdout.close()
    except OSError:
        pass
    if aviso == 'pronto':
        return Resultado(comando='tela abrir', situacao='ok', fase='tela', pasta_job=pasta,
                         o_que_fazer=O_QUE_FAZER_ABERTA, contagens={'tela_aberta': 1},
                         linhas_humanas=['Tela de briefing aberta.'])
    prefixo, _, motivo = aviso.partition(' ')
    if prefixo != 'recusado' or motivo not in O_QUE_FAZER_RECUSA:
        motivo = 'erro_interno'
    return _recusa(pasta, motivo)
