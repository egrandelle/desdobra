# -*- coding: utf-8 -*-
"""Registro de limites e a regra "nenhum numero de regra sem fonte".

Convencao (tambem em desdobra/limites.py e docs/m1-interfaces.md): fora de desdobra/limites.py, no pacote
desdobra, sao proibidos
  1. constante numerica como operando direto de comparacao, inclusive dentro de tupla, lista ou conjunto
     comparado (x > 24, n in (2, 3));
  2. atribuicao a nome em MAIUSCULAS no nivel do modulo ou de classe com constante numerica no valor
     (LIMIAR = 24, ORCAMENTO = 512 * MB);
exceto os numeros neutros 0, 1, -1, os membros de classes Enum (codigos de protocolo) e as linhas com o
comentario "# numero-neutro: <motivo>". Todo outro numero de regra vem de limites.valor('<id>').
"""
import ast
import json
import re

import pytest

from conftest import PASTA_PACOTE
from desdobra import limites
from desdobra.limites import ErroLimite, Limite

NEUTROS = {0, 1, -1}
MARCA = re.compile(r'#\s*numero-neutro:\s*\S')
NOME_MAIUSCULO = re.compile(r'^_?[A-Z][A-Z0-9_]*$')
ISENTOS = {'limites.py'}


def _numero(no):
    """Valor numerico de uma constante (aceita o sinal de menos), ou None."""
    if isinstance(no, ast.UnaryOp) and isinstance(no.op, (ast.USub, ast.UAdd)):
        v = _numero(no.operand)
        return None if v is None else (-v if isinstance(no.op, ast.USub) else v)
    if isinstance(no, ast.Constant) and isinstance(no.value, (int, float, complex)) and not isinstance(no.value, bool):
        return no.value
    return None


def _numeros_diretos(no):
    """Constantes numericas do no ou de uma tupla/lista/conjunto literal."""
    if isinstance(no, (ast.Tuple, ast.List, ast.Set)):
        for e in no.elts:
            yield from _numeros_diretos(e)
        return
    v = _numero(no)
    if v is not None:
        yield no, v


def _numeros_em(no):
    for filho in ast.walk(no):
        v = _numero(filho)
        if v is not None and not (isinstance(filho, ast.Constant) and _eh_operando_de_sinal(filho, no)):
            yield filho, v


def _eh_operando_de_sinal(constante, raiz):
    for n in ast.walk(raiz):
        if isinstance(n, ast.UnaryOp) and n.operand is constante:
            return True
    return False


def _eh_enum(classe):
    for base in classe.bases:
        nome = base.id if isinstance(base, ast.Name) else base.attr if isinstance(base, ast.Attribute) else ''
        if nome.endswith('Enum') or nome in ('IntFlag', 'Flag'):
            return True
    return False


def violacoes(fonte, nome_arquivo='<codigo>'):
    """Lista de (arquivo, linha, numero, motivo) que fere a convencao."""
    arvore = ast.parse(fonte)
    linhas = fonte.splitlines()
    achados = []

    def marcada(no):
        fim = getattr(no, 'end_lineno', no.lineno)
        return any(MARCA.search(linhas[i - 1]) for i in range(no.lineno, fim + 1) if i - 1 < len(linhas))

    def registrar(no, v, motivo, alvo=None):
        if v in NEUTROS or marcada(alvo or no):
            return
        achados.append((nome_arquivo, no.lineno, v, motivo))

    for no in ast.walk(arvore):
        if isinstance(no, ast.Compare):
            for operando in [no.left, *no.comparators]:
                for c, v in _numeros_diretos(operando):
                    registrar(c, v, 'numero em comparacao', alvo=no)

    def atribuicoes(corpo, em_enum=False):
        for no in corpo:
            if isinstance(no, ast.ClassDef):
                atribuicoes(no.body, em_enum=_eh_enum(no))
                continue
            if em_enum:
                continue
            alvos, valor = [], None
            if isinstance(no, ast.Assign):
                alvos, valor = no.targets, no.value
            elif isinstance(no, ast.AnnAssign) and no.value is not None:
                alvos, valor = [no.target], no.value
            nomes = [a.id for a in alvos if isinstance(a, ast.Name)]
            if valor is not None and any(NOME_MAIUSCULO.match(n) for n in nomes):
                for c, v in _numeros_em(valor):
                    registrar(c, v, 'numero em constante maiuscula', alvo=no)
            if isinstance(no, (ast.If, ast.Try, ast.With)):
                for bloco in ('body', 'orelse', 'finalbody'):
                    atribuicoes(getattr(no, bloco, []) or [], em_enum)
                for h in getattr(no, 'handlers', []) or []:
                    atribuicoes(h.body, em_enum)

    atribuicoes(arvore.body)
    return achados


def ids_referenciados(fonte):
    """ids passados como texto literal para limites.valor / obter / efeito."""
    ids = set()
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, ast.Call) and no.args and isinstance(no.args[0], ast.Constant) and isinstance(no.args[0].value, str):
            f = no.func
            nome = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ''
            dono = f.value.id if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) else ''
            if nome in ('valor', 'obter', 'efeito') and dono in ('limites', ''):
                ids.add(no.args[0].value)
    return ids


def _arquivos_do_pacote():
    return sorted(p for p in PASTA_PACOTE.rglob('*.py') if p.name not in ISENTOS)


# ------------------------------------------------------------------ o detector funciona
@pytest.mark.parametrize('codigo, esperado', [
    ('if x > 24:\n    pass\n', [24]),
    ('ok = n in (2, 3)\n', [2, 3]),
    ('LIMIAR = 24\n', [24]),
    ('ORCAMENTO = 512 * MB\n', [512]),
    ('class C:\n    TETO = 0.95\n', [0.95]),
    ('y = -5 < x\n', [-5]),
    ('if x == 0 or x != -1 or x >= 1:\n    pass\n', []),
    ('class Codigo(IntEnum):\n    PORTAO = 10\n', []),
    ('TAMANHO = 26  # numero-neutro: cabecalho do PSD tem 26 bytes\n', []),
    ('TAMANHO = 26  # numero-neutro:\n', [26]),
    ('def f(a):\n    return a[:8]\n', []),
    ('nome = "LIMIAR"\nlimiar = 24\n', []),
    ('if x > limites.valor("prova_pixel.limiar_diferenca"):\n    pass\n', []),
])
def test_detector_de_numeros(codigo, esperado):
    assert [v for _a, _l, v, _m in violacoes(codigo)] == esperado


# ------------------------------------------------------------------ o pacote segue a convencao
def test_nenhum_numero_de_regra_sem_fonte_no_pacote():
    achados = []
    for arq in _arquivos_do_pacote():
        achados += violacoes(arq.read_text(encoding='utf-8'), arq.relative_to(PASTA_PACOTE).as_posix())
    assert not achados, 'numeros de regra fora de fontes-de-limites.json:\n' + '\n'.join(
        '%s:%d  %r  (%s)' % a for a in achados)


def test_todo_id_usado_no_codigo_existe_no_registro():
    registro = limites.carregar()
    faltando = []
    for arq in _arquivos_do_pacote():
        for lid in ids_referenciados(arq.read_text(encoding='utf-8')):
            if lid not in registro:
                faltando.append('%s: %s' % (arq.name, lid))
    assert not faltando, 'ids usados no codigo sem entrada no registro: %s' % faltando


# ------------------------------------------------------------------ o registro
def test_registro_carrega_e_respeita_as_regras():
    registro = limites.carregar()
    assert registro
    for lim in registro.values():
        assert lim.efeito_efetivo in ('reprova', 'avisa', 'registra')
        if lim.situacao == 'a_calibrar':
            assert lim.efeito_efetivo != 'reprova'
        else:
            assert lim.fonte and lim.valor is not None
        if lim.situacao == 'decidido':
            assert lim.fonte['arquivo'] == 'decisoes-v1.md'
        if lim.situacao == 'medido':
            assert lim.fonte['arquivo'].startswith('pesquisa/')


def test_valores_usados_no_m1():
    assert limites.valor('prova_pixel.limiar_diferenca') == 24
    assert limites.obter('coberta_no_kv.ocupa_canvas_fracao').situacao == 'a_calibrar'
    assert limites.efeito('segredos.padroes') == 'reprova'
    citacao = limites.obter('prova_pixel.limiar_diferenca').citacao()
    assert citacao['limite_id'] == 'prova_pixel.limiar_diferenca' and citacao['fonte']['arquivo'] == 'pesquisa/corpus-testes.md'
    with pytest.raises(ErroLimite):
        limites.valor('prova_pixel.fracao_reprova')  # a calibrar, sem valor
    with pytest.raises(ErroLimite):
        limites.obter('nao.existe')


def test_a_calibrar_nunca_reprova():
    lim = Limite(id='x.y', valor=1, unidade='u', fonte=None, situacao='a_calibrar', efeito='reprova')
    assert lim.efeito_efetivo == 'avisa'


def _gravar_registro(tmp_path, itens):
    caminho = tmp_path / 'registro.json'
    caminho.write_text(json.dumps({'esquema': 'fontes-de-limites/1', 'limites': itens}), encoding='utf-8')
    return caminho


def test_carregador_recusa_registro_errado(tmp_path):
    base = {'id': 'a.b', 'valor': 3, 'unidade': 'px', 'fonte': None, 'situacao': 'medido', 'efeito': 'registra'}
    for item in (base, dict(base, situacao='a_calibrar', efeito='reprova'),
                 dict(base, situacao='decidido', fonte={'arquivo': 'pesquisa/x.md'}),
                 dict(base, situacao='medido', valor=None, fonte={'arquivo': 'pesquisa/x.md'})):
        with pytest.raises(Exception):
            limites.carregar(_gravar_registro(tmp_path, [item]))
        limites.carregar.cache_clear()
    repetido = dict(base, situacao='a_calibrar')
    with pytest.raises(ErroLimite, match='repetido'):
        limites.carregar(_gravar_registro(tmp_path, [repetido, repetido]))
    limites.carregar.cache_clear()


def test_padroes_de_segredo_compilam_e_pegam_exemplos_sinteticos():
    padroes = [re.compile(p['regex']) for p in limites.valor('segredos.padroes')]
    exemplos = ['AIza' + 'A' * 35, 'AKIA' + 'B' * 16, 'ghp_' + 'c' * 36, 'sk-ant-' + 'd' * 24,
                '-----BEGIN RSA ' + 'PRIVATE KEY-----', 'xoxb-' + '1' * 12]
    for ex in exemplos:
        assert any(p.search('texto %s fim' % ex) for p in padroes), ex
    assert not any(p.search('LIQUIDA 2026 PROMO 50% OFF') for p in padroes)


def test_limites_que_decidem_o_codigo_declaram_o_efeito_real():
    """O registro nao pode dizer "registra" para um numero que recusa o arquivo ou para o filho; e um limite a
    calibrar nunca reprova: a parada pede confirmacao do DA."""
    from desdobra import leitor
    lims = [limites.obter(i) for i in leitor.LIMITES_QUE_DECIDEM_CODIGO]
    for lim in lims:
        assert lim.efeito != 'registra', lim.id
        if lim.situacao == 'a_calibrar':
            assert lim.efeito_efetivo != 'reprova', lim.id
    rec = leitor.anotar_limites({'tipo': 'orcamento', 'etapa': 'cabecalho', 'motivo': 'x'})
    esperado = 'pede_confirmacao_do_da' if any(l.situacao == 'a_calibrar' for l in lims) else 'reprova'
    assert rec['decisao'] == esperado


def test_limite_sem_numero_na_fonte_fica_a_calibrar():
    assert limites.obter('quadros.fracao_canvas_grupo_topo').situacao == 'a_calibrar'
