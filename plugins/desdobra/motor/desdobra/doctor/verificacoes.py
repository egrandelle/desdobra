# -*- coding: utf-8 -*-
"""Verificacoes do doctor minimo do M1 (arquitetura-v1.md, 4.15 e 9.2).

Cada verificacao devolve uma Verificacao com situacao ok, falha, aviso ou pulado, um detalhe (fatos do ambiente:
versoes, caminhos da instalacao, nunca conteudo de job) e o O QUE FAZER, que e texto fixo e nunca leva caminho.

Nenhuma verificacao instala nada nem abre PSD. O teste do isolador roda dois filhos pequenos de Python puro,
sem arquivo de cliente.
"""
import importlib
import importlib.metadata
import json
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from desdobra import PASTA_MOTOR, PASTA_PLUGIN, limites, plataforma

ARQUIVO_LOCK = PASTA_MOTOR / 'requirements.lock'
NOME_INTERPRETADOR = 'interpretador.json'
NOME_PREPARO = 'preparo.json'
SEMPRE_PRESENTES = ('pip', 'desdobra')  # o venv traz o pip; o motor se instala em modo editavel

# Modulos que psd_tools.composite importa do extra composite (conferido no codigo instalado do psd-tools 1.26.0:
# composite/vector.py, effects.py, adjustments.py e paint.py), mais o proprio compositor.
MODULOS_COMPOSITE = ('aggdraw', 'scipy.interpolate', 'scipy.ndimage', 'scipy.spatial', 'psd_tools.composite')

# Filhos do teste do isolador. So Python puro: nada de PSD, nada de arquivo.
FILHO_DENTRO = (
    'import sys\n'
    'linha = sys.stdin.buffer.readline()\n'
    "sys.exit(0 if linha == b'iniciar\\n' else 3)\n"
)
FILHO_ESTOURO = (
    'import sys\n'
    'sys.stdin.buffer.readline()\n'
    'maximo = int(sys.argv[1])\n'
    'blocos = []\n'
    'total = 0\n'
    'try:\n'
    '    while total < maximo:\n'
    '        blocos.append(bytearray(1 << 20))\n'
    '        total += 1 << 20\n'
    'except MemoryError:\n'
    '    blocos.clear()\n'
    '    sys.exit(4)\n'
    'sys.exit(0)\n'
)


TOLERANCIA_HIGHS = 1e-6  # numero-neutro: folga numerica do programa de teste (otimo exato 1)


@dataclass
class Verificacao:
    id: str
    titulo: str
    situacao: str = 'ok'
    detalhe: str = ''
    o_que_fazer: str | None = None
    numeros: dict = field(default_factory=dict)
    limite: dict | None = None

    def como_dict(self):
        dados = {'id': self.id, 'titulo': self.titulo, 'situacao': self.situacao, 'detalhe': self.detalhe,
                 'o_que_fazer': self.o_que_fazer, 'numeros': dict(self.numeros)}
        if self.limite is not None:
            dados['limite'] = self.limite
        return dados


# ------------------------------------------------------------------ utilidades
def normalizar(nome):
    """Nome de distribuicao normalizado (PEP 503)."""
    return re.sub(r'[-_.]+', '-', nome).lower()


def versoes_do_lock(caminho=None):
    """{nome normalizado: versao} das linhas "nome==versao" do lock."""
    versoes = {}
    with open(caminho or ARQUIVO_LOCK, encoding='utf-8') as f:
        for linha in f:
            m = re.match(r'^([A-Za-z0-9][A-Za-z0-9_.-]*)==([^\s\\;]+)', linha)
            if m:
                versoes[normalizar(m.group(1))] = m.group(2)
    return versoes


def versao_instalada(nome):
    try:
        return importlib.metadata.version(nome)
    except importlib.metadata.PackageNotFoundError:
        return None


def mesmo_caminho(a, b):
    try:
        return Path(a).resolve() == Path(b).resolve()
    except (OSError, TypeError, ValueError):
        return False


def em_venv():
    return sys.prefix != sys.base_prefix


def pasta_dados():
    """A pasta de dados do plugin, quando o motor roda no venv que o gancho criou (DATA/venv)."""
    if not em_venv():
        return None
    candidata = Path(sys.prefix).parent
    if (candidata / NOME_INTERPRETADOR).is_file():
        return candidata
    return None


def _ler_json(caminho):
    try:
        with open(caminho, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# ------------------------------------------------------------------ verificacoes
def verificar_python():
    v = Verificacao('python', 'Versão do Python')
    lim = limites.obter('ambiente.python_versoes_aceitas')
    v.limite = lim.citacao()
    versao = '%d.%d' % sys.version_info[:2]
    v.detalhe = 'Python %s em %s.' % (sys.version.split()[0], sys.executable)
    if versao not in lim.valor:
        v.situacao = 'falha'
        v.o_que_fazer = ('Instale uma versão do Python aceita pelo desdobra (%s), ponha no PATH do usuário e abra o '
                         'Claude Code de novo.' % ', '.join(lim.valor))
    return v


def verificar_ambiente(dados):
    """O motor roda no ambiente que o gancho criou, e o interpretador.json bate com este processo."""
    v = Verificacao('ambiente_do_plugin', 'Ambiente Python do plugin')
    if dados is None:
        v.situacao = 'aviso'
        v.detalhe = ('O motor não está rodando no ambiente criado pelo gancho do plugin (prefixo %s). Em '
                     'desenvolvimento isso é esperado.' % sys.prefix)
        v.o_que_fazer = 'Se isto for uma instalação do plugin, abra uma sessão nova do Claude Code para o gancho preparar o ambiente.'
        return v
    interp = _ler_json(dados / NOME_INTERPRETADOR) or {}
    preparo = _ler_json(dados / NOME_PREPARO) or {}
    problemas = []
    if not mesmo_caminho(interp.get('python', ''), sys.executable):
        problemas.append('o interpretador.json aponta para outro Python')
    if not mesmo_caminho(interp.get('plugin_root', ''), PASTA_PLUGIN):
        problemas.append('o motor instalado é de outra versão do plugin')
    if preparo and preparo.get('situacao') != 'ok':
        problemas.append('o último preparo terminou com a situação %s na etapa %s'
                         % (preparo.get('situacao'), preparo.get('etapa_que_falhou')))
    tempo = preparo.get('tempo_s')
    v.numeros = {'preparo_tempo_s': tempo if isinstance(tempo, (int, float)) else None}
    v.detalhe = 'Pasta de dados %s; último preparo: %s (%s).' % (dados, preparo.get('acao'), preparo.get('situacao'))
    if problemas:
        v.situacao = 'falha'
        v.detalhe += ' Problemas: %s.' % '; '.join(problemas)
        v.o_que_fazer = ('Abra uma sessão nova do Claude Code para o gancho refazer o ambiente. Se o problema voltar, '
                         'veja o preparo.log na pasta de dados do plugin.')
    return v


def verificar_lock(dados, caminho_lock=None):
    """Cada pacote do lock instalado na versao fixada; pacote a mais e aviso no ambiente do plugin."""
    v = Verificacao('versoes_do_lock', 'Versões fixadas do lock')
    try:
        fixadas = versoes_do_lock(caminho_lock)
    except OSError:
        v.situacao = 'falha'
        v.detalhe = 'O arquivo requirements.lock do motor não foi encontrado.'
        v.o_que_fazer = 'Reinstale o plugin.'
        return v
    erradas = []
    for nome, versao in sorted(fixadas.items()):
        instalada = versao_instalada(nome)
        if instalada != versao:
            erradas.append('%s %s (fixada %s)' % (nome, instalada or 'ausente', versao))
    a_mais = sorted({normalizar(d.metadata['Name']) for d in importlib.metadata.distributions()
                     if d.metadata['Name']} - set(fixadas) - set(SEMPRE_PRESENTES))
    v.numeros = {'pacotes_fixados': len(fixadas), 'pacotes_errados': len(erradas), 'pacotes_a_mais': len(a_mais)}
    v.detalhe = '%d pacotes fixados no lock.' % len(fixadas)
    if erradas:
        v.situacao = 'falha'
        v.detalhe += ' Diferentes do lock: %s.' % ', '.join(erradas)
        v.o_que_fazer = ('O ambiente não bate com o lock. Apague a cópia requirements.lock da pasta de dados do plugin '
                         'e abra uma sessão nova, para o gancho recriar o ambiente.')
    elif a_mais:
        v.detalhe += ' Pacotes fora do lock: %s.' % ', '.join(a_mais)
        if dados is not None:
            v.situacao = 'aviso'
            v.o_que_fazer = ('O ambiente do plugin tem pacotes fora do lock. Apague a cópia requirements.lock da pasta '
                             'de dados do plugin e abra uma sessão nova, para o gancho recriar o ambiente.')
    return v


def verificar_psd_tools(caminho_lock=None):
    """psd-tools na versao do lock, com cada pacote do extra composite instalado e importavel."""
    v = Verificacao('psd_tools_composite', 'psd-tools com o extra composite')
    try:
        fixadas = versoes_do_lock(caminho_lock)
    except OSError:
        fixadas = {}
    versao = versao_instalada('psd-tools')
    if versao is None:
        v.situacao = 'falha'
        v.detalhe = 'O psd-tools não está instalado.'
        v.o_que_fazer = 'Abra uma sessão nova do Claude Code para o gancho recriar o ambiente.'
        return v
    extras = set()
    for req in importlib.metadata.requires('psd-tools') or []:
        if re.search(r'extra\s*==\s*["\']composite["\']', req):
            extras.add(normalizar(re.match(r'[A-Za-z0-9][A-Za-z0-9_.-]*', req).group(0)))
    problemas = []
    if fixadas.get('psd-tools') not in (None, versao):
        problemas.append('psd-tools %s, e o lock fixa %s' % (versao, fixadas['psd-tools']))
    if not extras:
        problemas.append('os metadados do psd-tools não declaram o extra composite')
    partes = []
    for nome in sorted(extras):
        instalada = versao_instalada(nome)
        partes.append('%s %s' % (nome, instalada or 'ausente'))
        if instalada is None:
            problemas.append('%s ausente' % nome)
        elif fixadas.get(nome) not in (None, instalada):
            problemas.append('%s %s, e o lock fixa %s' % (nome, instalada, fixadas[nome]))
    for modulo in MODULOS_COMPOSITE:
        try:
            importlib.import_module(modulo)
        except Exception as e:  # noqa: BLE001 - qualquer falha de importacao do compositor e falha do ambiente
            problemas.append('o módulo %s não carrega (%s)' % (modulo, type(e).__name__))
    v.detalhe = 'psd-tools %s; extra composite: %s.' % (versao, ', '.join(partes) or 'nenhum')
    if problemas:
        v.situacao = 'falha'
        v.detalhe += ' Problemas: %s.' % '; '.join(problemas)
        v.o_que_fazer = ('O compositor do psd-tools está incompleto. Apague a cópia requirements.lock da pasta de dados '
                         'do plugin e abra uma sessão nova, para o gancho recriar o ambiente.')
    return v


def verificar_highs():
    """O HiGHS do scipy, que resolve o layout da derivacao (M5): importa e resolve um programa linear pequeno."""
    v = Verificacao('scipy_highs', 'Solver da derivação (HiGHS do scipy)')
    try:
        from scipy.optimize import linprog
        r = linprog([1.0, 1.0], A_ub=[[-1.0, -2.0]], b_ub=[-2.0], bounds=[(0, None), (0, None)], method='highs')
        ok = r.status == 0 and abs(float(r.fun) - 1.0) < TOLERANCIA_HIGHS
    except Exception as e:  # noqa: BLE001
        ok, r = False, None
        v.detalhe = 'O scipy.optimize não carregou (%s).' % type(e).__name__
    if ok:
        v.detalhe = 'HiGHS resolveu o programa de teste.'
    else:
        v.situacao = 'falha'
        v.detalhe = v.detalhe or 'O HiGHS não resolveu o programa de teste.'
        v.o_que_fazer = ('Sem o HiGHS, o "desdobra derivar" não resolve o layout. Apague a cópia requirements.lock da '
                         'pasta de dados do plugin e abra uma sessão nova, para o gancho recriar o ambiente.')
    return v


def recursos_do_pillow():
    """{'jpeg', 'libimagequant', 'versoes'} da build do Pillow instalada."""
    from PIL import features
    from desdobra.entrega import codificar
    return {'jpeg': bool(features.check('jpg')), 'libimagequant': bool(features.check_feature('libimagequant')),
            'versoes': codificar.versoes()}


def verificar_encoder(recursos=None):
    """O encoder da entrega (M6, arquitetura-v1.md, 9.7): falha so sem JPEG ou com o libimagequant (GPLv3, PNG
    quantizado fora da v1); outra build (versao do Pillow, do libjpeg-turbo ou do zlib) so avisa, porque os bytes da
    entrega podem mudar."""
    from desdobra.entrega import codificar
    v = Verificacao('encoder_entrega', 'Encoder da entrega (Pillow)')
    v.limite = limites.obter('entrega.encoder_build_referencia').citacao()
    r = recursos if recursos is not None else recursos_do_pillow()
    vers = r['versoes']
    v.detalhe = 'Pillow %s; libjpeg-turbo %s; zlib %s; JPEG %s; libimagequant %s.' % (
        vers.get('pillow'), vers.get('libjpeg_turbo') or 'ausente', vers.get('zlib') or 'ausente',
        'sim' if r['jpeg'] else 'não', 'presente' if r['libimagequant'] else 'ausente')
    if not r['jpeg']:
        v.situacao = 'falha'
        v.o_que_fazer = ('O Pillow deste ambiente não grava JPEG, e a entrega não sai sem ele. Apague a cópia '
                         'requirements.lock da pasta de dados do plugin e abra uma sessão nova, para o gancho recriar o '
                         'ambiente.')
    elif r['libimagequant']:
        v.situacao = 'falha'
        v.o_que_fazer = ('O Pillow deste ambiente traz o libimagequant (GPLv3), que a v1 não usa. Apague a cópia '
                         'requirements.lock da pasta de dados do plugin e abra uma sessão nova, para o gancho recriar o '
                         'ambiente com o Pillow do lock.')
    else:
        difere = codificar.build_difere(vers)
        if difere:
            v.situacao = 'aviso'
            v.detalhe += ' Diferente da build de referência: %s.' % ', '.join(difere)
            v.o_que_fazer = ('A build do encoder não é a de referência: os mesmos parâmetros podem dar outros bytes, e a '
                             'aprovação feita em outra máquina pode cair. As versões vão para o relatório da entrega.')
    return v


def _rodar_filho(plat, codigo, teto, tempo_s, *extra):
    with tempfile.TemporaryDirectory(prefix='desdobra-doctor-') as pasta:
        comando = [str(plat.interpretador()), '-I', '-B', '-c', codigo, *[str(x) for x in extra]]
        return plat.executar_isolado(comando, teto, tempo_s, Path(pasta))


def verificar_isolador(plat=None):
    """Dois filhos sob o isolador: um que cabe no teto e termina com 0, e outro que estoura o teto.

    O teto do teste e isolador.base_python_bytes (o custo medido de um Python com numpy e psd-tools): um Python
    puro cabe nele com folga. O filho que estoura pede memoria aos poucos ate o dobro do teto e para sozinho se o
    teto nao segurar, para o teste nunca tomar a memoria da maquina."""
    plat = plat or plataforma.obter()
    teto = int(limites.valor('isolador.base_python_bytes'))
    tempo_s = float(limites.valor('isolador.tempo_max_s'))
    citacao = limites.obter('isolador.base_python_bytes').citacao()
    sem_suporte = 'O isolador deste sistema ainda não roda. O desdobra só lê PSD no Windows por enquanto.'

    dentro = Verificacao('isolador_dentro_do_teto', 'Isolador: filho dentro do teto', limite=citacao)
    r = _rodar_filho(plat, FILHO_DENTRO, teto, tempo_s)
    dentro.numeros = {'teto_bytes': teto, 'pico_bytes': r.pico_bytes, 'tempo_s': round(r.tempo_s, 3)}
    dentro.detalhe = 'Plataforma %s: situação %s, código %s.' % (plat.nome, r.situacao, r.codigo)
    if r.situacao == 'recusado':
        dentro.situacao = 'falha'
        dentro.detalhe += ' Motivo: %s' % (r.motivo or 'sem motivo')
        dentro.o_que_fazer = sem_suporte
    elif r.situacao != 'ok' or r.codigo != 0:
        dentro.situacao = 'falha'
        dentro.detalhe += ' Motivo: %s' % (r.motivo or 'o filho de teste não terminou como esperado')
        dentro.o_que_fazer = ('O isolador não rodou um processo simples. Rode o doctor de novo; se repetir, mande o '
                              'doctor.json para a Trezion.')

    estouro = Verificacao('isolador_estouro_do_teto', 'Isolador: filho que estoura o teto', limite=citacao)
    if r.situacao == 'recusado':
        estouro.situacao = 'pulado'
        estouro.detalhe = 'Pulado: o isolador recusou o primeiro filho.'
        return [dentro, estouro], True
    limite_do_filho = teto + teto  # o filho para sozinho no dobro do teto se o teto nao segurar
    r2 = _rodar_filho(plat, FILHO_ESTOURO, teto, tempo_s, limite_do_filho)
    estouro.numeros = {'teto_bytes': teto, 'pico_bytes': r2.pico_bytes, 'tempo_s': round(r2.tempo_s, 3)}
    estouro.detalhe = 'Plataforma %s: situação %s, código %s.' % (plat.nome, r2.situacao, r2.codigo)
    if r2.situacao != 'memoria':
        estouro.situacao = 'falha'
        estouro.detalhe += ' O teto de memória não segurou o filho.'
        estouro.o_que_fazer = ('O teto de memória do isolador não funcionou nesta máquina. Não leia PSD de cliente até '
                               'isso ser resolvido. Mande o doctor.json para a Trezion.')
    return [dentro, estouro], False


def verificar_teto(teto, dados):
    v = Verificacao('teto_modo_dados', 'Teto do modo de dados')
    if teto is None:
        v.situacao = 'falha' if dados is not None else 'aviso'
        v.detalhe = 'O teto do modo de dados não chegou ao motor.'
        v.o_que_fazer = ('Configure o teto do modo de dados do plugin em /plugin, na opção Configure do desdobra, e '
                         'rode o doctor de novo.')
        return v
    descricao = {'a': 'metadados, textos e miniaturas de camadas sem texto',
                 'b': 'metadados e textos, sem imagens', 'c': 'só contagens, estados e números do motor'}
    v.detalhe = 'Teto %s: o Claude pode ver no máximo %s.' % (teto, descricao[teto])
    return v
