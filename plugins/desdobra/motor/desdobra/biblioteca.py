# -*- coding: utf-8 -*-
"""Biblioteca da agencia (M7c, passo M1; arquitetura-v1.md, 3.5 e 4.14).

A pasta onde ficam os perfis de marca (<biblioteca>/marcas/<id>/perfil-marca.json, passo M2). O DA escolhe a pasta
em /plugin, aba Installed, plugin desdobra, opcao Configure (userConfig.biblioteca_agencia, do tipo directory), por
clique, sem terminal. A opcao e opcional: sem ela, o job roda normal e a tela esconde a marca e diz onde configurar.

A pasta chega ao motor pela opcao global "--biblioteca <pasta>" (como o teto, "--teto-modo-dados"), e o "tela abrir"
a passa ao processo de fundo da tela. Valor vazio, so espacos ou com a substituicao "${user_config...}" sem fazer
(a referencia do manifesto nao diz o que sobra no texto da skill quando a opcao fica vazia) vale como nao configurada.

conferir() diz so se a pasta serve: existe, e pasta, grava (uma sonda que cria e apaga um arquivo vazio, na raiz e em
<biblioteca>/marcas quando ela ja existe) e fica fora
da pasta do plugin (que muda a cada versao; no plugin instalado, toda a pasta de plugins da configuracao) e da pasta de dados do plugin (CLAUDE_PLUGIN_DATA, apagada na
desinstalacao). Nenhum texto daqui leva o caminho nem a lista de marcas: o envelope do doctor e o da tela nunca os
trazem. O caminho fica so com o processo que o recebeu.
"""
import os
import re
import socket
import tempfile
from dataclasses import dataclass
from pathlib import Path

from desdobra import PASTA_PLUGIN

PASTA_MARCAS = 'marcas'
PREFIXO_SONDA = '.desdobra-sonda-'

ONDE_CONFIGURAR = ('Para usar as marcas da agência, escolha a pasta da biblioteca da agência em /plugin, aba '
                   'Installed, plugin desdobra, opção Configure.')

# detalhe por situacao (texto fixo, sem caminho)
DETALHE = {
    'nao_configurada': 'A biblioteca da agência não está configurada: o job roda sem marca. ' + ONDE_CONFIGURAR,
    'ok': 'A biblioteca da agência existe, grava e fica fora das pastas do plugin.',
    'ausente': 'A pasta configurada para a biblioteca da agência não existe ou não é uma pasta.',
    'sem_escrita': 'O desdobra não consegue gravar na pasta configurada para a biblioteca da agência.',
    'dentro_do_plugin': 'A pasta configurada para a biblioteca da agência fica dentro da pasta do plugin, que muda a '
                        'cada versão.',
    'dentro_dos_dados': 'A pasta configurada para a biblioteca da agência fica dentro da pasta de dados do plugin, '
                        'que some quando o plugin é desinstalado.',
    'marcas_bloqueada': 'Na biblioteca da agência, o desdobra não consegue gravar os perfis de marca no item marcas.',
}

# o que fazer por situacao (texto fixo, sem caminho, sem comando de terminal)
O_QUE_FAZER = {
    'nao_configurada': ONDE_CONFIGURAR,
    'ausente': ('Crie a pasta da biblioteca da agência ou escolha outra em /plugin, aba Installed, plugin desdobra, '
                'opção Configure.'),
    'sem_escrita': ('Dê permissão de escrita na pasta da biblioteca da agência ou escolha outra em /plugin, aba '
                    'Installed, plugin desdobra, opção Configure.'),
    'dentro_do_plugin': ('Escolha para a biblioteca da agência uma pasta fora da pasta do plugin, em /plugin, aba '
                         'Installed, plugin desdobra, opção Configure.'),
    'dentro_dos_dados': ('Escolha para a biblioteca da agência uma pasta fora da pasta de dados do plugin, em '
                         '/plugin, aba Installed, plugin desdobra, opção Configure.'),
    'marcas_bloqueada': ('Na biblioteca da agência, troque o nome do arquivo chamado marcas ou dê permissão de escrita '
                         'na pasta marcas. Também dá para escolher outra pasta em /plugin, aba Installed, plugin '
                         'desdobra, opção Configure.'),
}

# a substituicao da opcao do plugin que nao aconteceu (o texto da skill ficou com a referencia crua)
_SEM_SUBSTITUICAO = re.compile(r'\$\{\s*user_config\.', re.IGNORECASE)
_VERSAO = re.compile(r'^\d+\.\d+')



@dataclass(frozen=True)
class Conferencia:
    situacao: str
    pasta: Path = None  # so para o processo que recebeu a opcao; nunca vai a envelope, log ou tela

    @property
    def configurada(self):
        return self.situacao != 'nao_configurada'

    @property
    def usavel(self):
        return self.situacao == 'ok'

    @property
    def detalhe(self):
        return DETALHE[self.situacao]

    @property
    def o_que_fazer(self):
        return O_QUE_FAZER.get(self.situacao)


def normalizar(valor):
    """A pasta como Path, ou None quando a opcao nao foi configurada."""
    if valor is None:
        return None
    texto = str(valor).strip().strip('"').strip("'").strip()
    if not texto or _SEM_SUBSTITUICAO.search(texto):
        return None
    return Path(texto).expanduser()


def _nomes_locais():
    nomes = {'localhost', '127.0.0.1', '::1', '.', '?'}
    try:
        nomes.add(socket.gethostname().lower())
    except OSError:
        pass
    nome = os.environ.get('COMPUTERNAME')
    if nome:
        nomes.add(nome.lower())
    return nomes


def _sem_prefixo(texto):
    """Tira do caminho do Windows as formas que apontam para o disco local: o prefixo estendido (barra, barra,
    interrogacao, barra), o de dispositivo (com ponto), o UNC estendido e o compartilhamento administrativo da propria
    maquina (localhost, 127.0.0.1, o nome dela, com C$). Fora do Windows, devolve igual."""
    if os.name != 'nt':
        return texto
    b = chr(92)  # barra invertida
    t = texto.replace('/', b)
    for meio in ('?', '.'):
        unc = b + b + meio + b + 'UNC' + b
        if t[:len(unc)].upper() == unc:
            t = b + b + t[len(unc):]
        prefixo = b + b + meio + b
        if t.startswith(prefixo) and t[len(prefixo) + 1:len(prefixo) + 2] == ':':
            t = t[len(prefixo):]
    if t.startswith(b + b):
        partes = t[2:].split(b, 2)
        if (len(partes) >= 2 and partes[0].lower() in _nomes_locais() and len(partes[1]) == 2  # numero-neutro: servidor e compartilhamento, e o compartilhamento administrativo tem letra e cifrao
                and partes[1][0].isalpha() and partes[1][1] == '$'):
            t = partes[1][0] + ':' + b + (partes[2] if len(partes) > 2 else '')  # numero-neutro: servidor, compartilhamento e resto do caminho
    return t


def _chave(p):
    return os.path.normcase(os.path.normpath(_sem_prefixo(str(p))))


def _identidade(p):
    try:
        st = os.stat(p)
    except (OSError, ValueError):
        return None
    if not st.st_ino:
        return None
    return st.st_dev, st.st_ino


def _dentro(filho, pai):
    """filho e pai, ou fica abaixo dele: pelo texto (sem os prefixos locais do Windows) e pela identidade no disco
    (a pasta ou um ancestral dela e a propria pasta do pai), o que pega juncao, atalho, nome curto e caminho de rede
    que volta para o mesmo disco."""
    f, p = _chave(filho), _chave(pai)
    if f == p or f.startswith(p.rstrip(os.sep) + os.sep):
        return True
    alvo = _identidade(pai)
    if alvo is None:
        return False
    atual = Path(filho)
    while True:
        if _identidade(atual) == alvo:
            return True
        acima = atual.parent
        if acima == atual:
            return False
        atual = acima


def _pastas_do_plugin():
    """A pasta do plugin desta versao e, no plugin instalado (<config>/plugins/cache/<mkt>/<plugin>/<versao>), toda a
    pasta de plugins da configuracao: o Claude Code troca ou apaga o que fica ali a cada atualizacao."""
    raiz = Path(PASTA_PLUGIN)
    pastas = [raiz]
    if _VERSAO.match(raiz.name):  # <plugin>/<versao>: as outras versoes tambem somem na atualizacao
        pastas.append(raiz.parent)
    for acima in raiz.parents:
        if acima.name.lower() == 'cache' and acima.parent.name.lower() == 'plugins':
            pastas.append(acima.parent)
            break
    return pastas


def _resolver(p):
    try:
        return Path(_sem_prefixo(str(p))).resolve()
    except (OSError, RuntimeError):
        return Path(os.path.abspath(p))


def _dados_padrao():
    from desdobra.chromium import pasta_dados_do_plugin
    return pasta_dados_do_plugin()


def _grava(pasta):
    """Cria e apaga um arquivo vazio na pasta. So diz se deu."""
    try:
        fd, caminho = tempfile.mkstemp(prefix=PREFIXO_SONDA, dir=str(pasta))
    except OSError:
        return False
    try:
        os.close(fd)
    finally:
        try:
            os.unlink(caminho)
        except OSError:
            pass
    return True


_SEM_DADOS = object()


def conferir(valor, dados=_SEM_DADOS):
    """Conferencia da pasta da biblioteca. dados: a pasta de dados do plugin (padrao: a do ambiente do plugin)."""
    pasta = normalizar(valor)
    if pasta is None:
        return Conferencia('nao_configurada')
    if not pasta.is_absolute():
        return Conferencia('ausente')
    pasta = _resolver(pasta)
    if any(_dentro(pasta, _resolver(raiz)) for raiz in _pastas_do_plugin()):
        return Conferencia('dentro_do_plugin', pasta)
    if dados is _SEM_DADOS:
        dados = _dados_padrao()
    if dados is not None and _dentro(pasta, _resolver(dados)):
        return Conferencia('dentro_dos_dados', pasta)
    if not pasta.is_dir():
        return Conferencia('ausente', pasta)
    if not _grava(pasta):
        return Conferencia('sem_escrita', pasta)
    marcas = pasta_marcas(pasta)
    if os.path.lexists(marcas) and (not marcas.is_dir() or not _grava(marcas)):
        return Conferencia('marcas_bloqueada', pasta)
    return Conferencia('ok', pasta)


def pasta_marcas(biblioteca):
    """<biblioteca>/marcas, onde o passo M2 grava os perfis de marca."""
    return Path(biblioteca) / PASTA_MARCAS


def para_tela(conferencia):
    """O que a pagina da tela recebe: so a situacao e o texto fixo de onde configurar, nunca o caminho."""
    return {'configurada': conferencia.configurada, 'usavel': conferencia.usavel, 'situacao': conferencia.situacao,
            'o_que_fazer': conferencia.o_que_fazer or ''}
