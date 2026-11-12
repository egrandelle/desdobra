# -*- coding: utf-8 -*-
"""Miniaturas que o Claude pode ver no modo (a): sugestoes/miniaturas/ (arquitetura-v1.md, 4.9 e 7.4).

decisoes-v1.md, 190, Q7: no modo (a), vao ao Claude so imagens de camadas sem texto; ficam de fora o grupo, o
objeto inteligente com texto dentro ou linkado, a camada escondida e a camada recortada sobre um texto, e na duvida
a camada fica de fora. A regra mora numa funcao so, miniatura_permitida, e cada condicao e uma lista do que entra:
o que a lista nao conhece fica de fora.

  - entra camada folha visivel do tipo pixel ou forma, sem texto e sem ajuste;
  - entra smart object embutido so aberto pelo leitor, sem texto e sem outro smart object dentro: alem do resumo do
    laudo, a regra le a estrutura interna que o leitor gravou (laudo/bruto/<sha256>/estrutura.json) e so aceita
    camada interna de pixel, forma ou grupo; sem a pasta do laudo ou sem essa estrutura, o smart object fica de fora
    (o resumo conta so o indice de registros, e uma camada smart sem registro passaria);
  - fica de fora smart object linkado, nao aberto ou recusado, grupo, prancheta, ajuste e preenchimento;
  - fica de fora camada invisivel no KV;
  - fica de fora toda a pilha de recorte (a base e as recortadas) em que alguma camada pode ter texto, com tudo o que
    estiver dentro de um grupo da pilha (o grupo base de recorte leva as camadas de dentro);
  - fica de fora layer_id repetido (o leitor grava idx<n>.png, que nunca e copiado);
  - fica de fora camada cujo nome o detector de segredos acha, e as que o chamador marcar como bloqueadas.

gravar_miniaturas(pasta_job, modo) copia laudo/miniaturas/<layer_id>.png para sugestoes/miniaturas/<layer_id>.png
so no modo (a) efetivo, confere o sha256 de cada copia contra a origem e grava sugestoes/miniaturas/indice.json
(so layer_id e sha256). Em qualquer outro modo a pasta e apagada inteira. Quem decide o modo efetivo e o chamador
(desdobra.sugestao.pacote.modo_do_job); este modulo nao le estado.json nem a escolha do DA.

Texto desenhado em pixel ou forma vetorial nao aparece no laudo como texto e passa por esta regra: o risco fica
declarado ao DA no texto do modo (a) na tela.
"""
import collections
import json
import os
import re
import shutil
from pathlib import Path

from desdobra import arquivos, contratos
from desdobra.sugestao import segredos

PASTA = Path('sugestoes') / 'miniaturas'
ARQUIVO_INDICE = PASTA / 'indice.json'
ORIGEM = Path('laudo') / 'miniaturas'

TIPOS_FOLHA = ('pixel', 'forma')
TIPO_SMART_EMBUTIDO = 'smart_embutido'
TIPOS_COM_FILHOS = ('grupo', 'prancheta')
# kinds do psd-tools que podem estar dentro do PSB ou PSD de um smart object para a miniatura dele entrar
KINDS_INTERNOS = ('pixel', 'shape', 'group')
_SHA256 = re.compile(r'[0-9a-f]{64}\Z')


class ErroMiniatura(Exception):
    """A copia nao bateu com a origem. Nada fica em sugestoes/miniaturas/."""


# ------------------------------------------------------------------ regra
def _layer_id(camada):
    lid = (camada.get('identidade') or {}).get('layer_id')
    if isinstance(lid, bool) or not isinstance(lid, int) or lid < 1:
        return None
    return lid


def _smart_limpo(camada):
    so = camada.get('smart_object')
    if not isinstance(so, dict) or so.get('embutido') is not True:
        return False
    ab = so.get('abertura')
    if not isinstance(ab, dict) or ab.get('situacao') != 'aberto':
        return False
    resumo = ab.get('resumo')
    if not isinstance(resumo, dict):
        return False
    return resumo.get('n_textos') == 0 and resumo.get('smart_objects') == 0


def _sem_texto_proprio(camada):
    # qualquer bloco de texto no laudo conta, mesmo vazio (sem importar desdobra.sugestao.pacote, que importa este
    # modulo a partir do M7c)
    return camada.get('texto') is None and camada.get('tipo') != 'texto'


class _Contexto:
    """O que a regra precisa olhar no laudo inteiro: ids repetidos, filhos, pilhas de recorte e, para o smart object,
    a estrutura interna gravada pelo leitor em pasta_laudo/bruto/."""

    def __init__(self, laudo, pasta_laudo=None):
        self.pasta_laudo = None if pasta_laudo is None else Path(pasta_laudo)
        self._estruturas = {}
        camadas = [c for c in laudo.get('camadas') or [] if isinstance(c, dict)]
        self.camadas = camadas
        self.contagem = collections.Counter(_layer_id(c) for c in camadas)
        self.filhos = collections.defaultdict(list)
        for c in camadas:
            self.filhos[c.get('pai_id')].append(c)
        self.fora_por_recorte = set()
        # o laudo lista as camadas de baixo para cima; a recortada vale sobre a irma sem recorte logo abaixo
        for irmas in list(self.filhos.values()):
            pilha = []
            for c in irmas + [None]:
                if c is None or not (c.get('aparencia') or {}).get('clipping'):
                    if len(pilha) > 1 and any(self._pode_ter_texto(x) for x in pilha):
                        for x in pilha:
                            self.fora_por_recorte.add(id(x))
                            # um grupo na pilha leva junto tudo o que esta dentro dele
                            self.fora_por_recorte.update(id(d) for d in self._descendentes(x))
                    pilha = [c]
                else:
                    pilha.append(c)

    def _descendentes(self, camada):
        """Todas as camadas dentro de `camada`, pelo pai_id e pelo caminho_ids do laudo."""
        raiz = (camada.get('identidade') or {}).get('layer_id')
        if raiz is None:
            return []
        ids, fila = {raiz}, [raiz]
        while fila:
            lid = fila.pop()
            for f in self.filhos.get(lid, []):
                fid = (f.get('identidade') or {}).get('layer_id')
                if fid is not None and fid not in ids:
                    ids.add(fid)
                    fila.append(fid)
        out = []
        for c in self.camadas:
            if c is camada:
                continue
            caminho = c.get('caminho_ids')
            caminho = caminho if isinstance(caminho, list) else []
            if c.get('pai_id') in ids or any(i in ids for i in caminho if isinstance(i, int)):
                out.append(c)
        return out

    def _estrutura_limpa(self, camada):
        """A estrutura interna que o leitor gravou para este smart object so tem camadas de pixel, forma ou grupo e
        nenhum registro de smart object. Sem a pasta do laudo, sem o arquivo ou com qualquer coisa estranha: nao."""
        if self.pasta_laudo is None:
            return False
        so = camada.get('smart_object') or {}
        pasta = (so.get('abertura') or {}).get('pasta')
        if not isinstance(pasta, str):
            return False
        partes = pasta.split('/')
        if len(partes) != 2 or partes[0] != 'bruto' or not _SHA256.match(partes[1]):  # numero-neutro: pasta bruto e sha do smart object
            return False
        sha = partes[1]
        if so.get('sha256') != sha:
            return False
        if sha not in self._estruturas:
            self._estruturas[sha] = self._ler_estrutura_limpa(sha)
        return self._estruturas[sha]

    def _ler_estrutura_limpa(self, sha):
        base = self.pasta_laudo / 'bruto'
        pasta = base / sha
        arq = pasta / 'estrutura.json'
        try:
            if base.is_symlink() or pasta.is_symlink() or arq.is_symlink() or not arq.is_file():
                return False
            arq.resolve().relative_to(base.resolve())
            est = json.loads(arq.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return False
        if not isinstance(est, dict) or (est.get('origem') or {}).get('sha256') != sha:
            return False
        if est.get('indice_smart') != []:
            return False
        internas = est.get('camadas')
        if not isinstance(internas, list):
            return False
        return all(isinstance(c, dict) and c.get('kind') in KINDS_INTERNOS for c in internas)

    def smart_limpo(self, camada):
        return _smart_limpo(camada) and self._estrutura_limpa(camada)

    def _pode_ter_texto(self, camada, _vistos=None):
        """Verdadeiro se a camada tem ou pode ter texto (na duvida, pode)."""
        if camada is None:
            return False
        if not _sem_texto_proprio(camada):
            return True
        tipo = camada.get('tipo')
        if tipo in TIPOS_FOLHA:
            return False
        if tipo == TIPO_SMART_EMBUTIDO:
            return not self.smart_limpo(camada)
        if tipo in TIPOS_COM_FILHOS:
            lid = _layer_id(camada)
            if lid is None or self.contagem[lid] != 1:
                return True
            vistos = _vistos or set()
            if lid in vistos:
                return True
            vistos.add(lid)
            return any(self._pode_ter_texto(f, vistos) for f in self.filhos.get(lid, []))
        return True

    def tem_filhos(self, camada):
        return bool(self.filhos.get((camada.get('identidade') or {}).get('layer_id')))


def miniatura_permitida(camada, laudo, contexto=None, *, pasta_laudo=None):
    """A miniatura desta camada do laudo/1 pode ir ao Claude no modo (a)? Na duvida, nao.

    pasta_laudo: a pasta laudo/ do job, onde o leitor gravou bruto/<sha256>/estrutura.json; sem ela, nenhum smart
    object entra. Com `contexto`, vale a pasta dada ao contexto."""
    if not isinstance(camada, dict):
        return False
    ctx = contexto or _Contexto(laudo, pasta_laudo)
    lid = _layer_id(camada)
    if lid is None or ctx.contagem[lid] != 1:
        return False
    aparencia = camada.get('aparencia') or {}
    if aparencia.get('visivel_efetiva') is not True or aparencia.get('ajuste'):
        return False
    if ctx.tem_filhos(camada) or not _sem_texto_proprio(camada):
        return False
    tipo = camada.get('tipo')
    if tipo == TIPO_SMART_EMBUTIDO:
        if not ctx.smart_limpo(camada):
            return False
    elif tipo not in TIPOS_FOLHA:
        return False
    return id(camada) not in ctx.fora_por_recorte


def camadas_permitidas(laudo, *, bloqueados=(), detector=None, pasta_laudo=None):
    """layer_ids, em ordem crescente, das camadas cuja miniatura pode ir ao Claude no modo (a)."""
    detector = detector or segredos.detector_padrao()
    bloqueados = set(bloqueados or ())
    ctx = _Contexto(laudo, pasta_laudo)
    out = []
    for c in laudo.get('camadas') or []:
        if not miniatura_permitida(c, laudo, ctx):
            continue
        lid = _layer_id(c)
        if lid in bloqueados:
            continue
        if detector.achado_em('miniatura', lid, {'nome': c.get('nome', '')}) is not None:
            continue
        out.append(lid)
    return sorted(out)


# ------------------------------------------------------------------ copia
def _apagar(pasta):
    """Apaga sugestoes/miniaturas/ inteira; se for um atalho, apaga so o atalho, nunca o destino."""
    pasta = Path(pasta)
    if pasta.is_symlink() or (hasattr(pasta, 'is_junction') and pasta.is_junction()):
        try:
            pasta.unlink()
        except (IsADirectoryError, PermissionError):
            os.rmdir(pasta)
        return
    if pasta.exists():
        shutil.rmtree(pasta)


def _gravar_copia(destino, dados):
    arquivos.gravar_bytes_atomico(destino, dados)


def _origem_valida(pasta_origem, lid):
    origem = pasta_origem / ('%d.png' % lid)
    if origem.is_symlink() or not origem.is_file():
        return None
    try:
        origem.resolve().relative_to(pasta_origem.resolve())
    except ValueError:
        return None
    return origem


def gravar_miniaturas(pasta_job, modo, *, laudo=None, bloqueados=(), detector=None):
    """Refaz sugestoes/miniaturas/ do job conforme o modo efetivo.

    modo 'a': copia so as miniaturas permitidas, confere o sha256 e grava indice.json; devolve o indice.
    qualquer outro modo: apaga a pasta inteira e devolve None.
    laudo: o laudo/1 do job (sem ele, le laudo/laudo.json); bloqueados: layer_ids que nao podem ir (por exemplo,
    os achados do detector de segredos que o pacote ja registrou)."""
    pasta_job = Path(pasta_job)
    destino = pasta_job / PASTA
    _apagar(destino)
    if modo != 'a':
        return None
    if laudo is None:
        laudo = contratos.ler(pasta_job / 'laudo' / 'laudo.json', 'laudo/1')
    pasta_origem = pasta_job / ORIGEM
    indice = {'miniaturas': []}
    try:
        for lid in camadas_permitidas(laudo, bloqueados=bloqueados, detector=detector,
                                      pasta_laudo=pasta_job / 'laudo'):
            origem = _origem_valida(pasta_origem, lid)
            if origem is None:
                continue
            dados = origem.read_bytes()
            sha = arquivos.sha256_bytes(dados)
            copia = destino / ('%d.png' % lid)
            _gravar_copia(copia, dados)
            if arquivos.sha256_arquivo(copia) != sha:
                raise ErroMiniatura('a cópia da miniatura não bate com a origem')
            indice['miniaturas'].append({'layer_id': lid, 'sha256': sha})
        destino.mkdir(parents=True, exist_ok=True)
        arquivos.gravar_json_atomico(pasta_job / ARQUIVO_INDICE, indice)
    except BaseException:
        _apagar(destino)
        raise
    return indice
