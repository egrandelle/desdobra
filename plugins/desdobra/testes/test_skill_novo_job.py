# -*- coding: utf-8 -*-
"""M7c, K1: o texto da skill novo-job e das referencias dela (revisao do K1).

1. O o_que_fazer do motor fala com quem roda o motor e cita comandos (job proxima, spec confirmar, render, aprovar,
   entregar, parametros-entrega). A skill nunca manda repetir esse texto ao DA ao pe da letra: o Claude traduz para o
   clique na tela e nunca passa comando ao DA (no 159).
2. O Claude Code troca ${user_config.biblioteca_agencia} pelo valor configurado em todo o texto da SKILL.md. Uma
   guarda que cita o marcador vira, com a pasta configurada, uma condicao sempre verdadeira. A skill passa sempre
   --biblioteca, e o motor trata o valor vazio ou sem troca como biblioteca nao configurada.
3. A sinopse de job criar no README e na doc do M2 mostra --modo-dados como opcional.
"""
import re
from pathlib import Path

from desdobra import biblioteca

RAIZ_PLUGIN = Path(__file__).resolve().parents[1]
RAIZ_REPO = RAIZ_PLUGIN.parents[1]
SKILL = RAIZ_PLUGIN / 'skills' / 'novo-job'
MARCADOR = '${user_config.biblioteca_agencia}'


def _textos():
    arquivos = [SKILL / 'SKILL.md'] + sorted((SKILL / 'references').glob('*.md'))
    return {a.name: a.read_text(encoding='utf-8') for a in arquivos}


def test_skill_nunca_manda_repetir_o_o_que_fazer_ao_da():
    proibidos = [re.compile(r'repit\w*[^.\n]{0,40}o_que_fazer', re.I),
                 re.compile(r'repita-o', re.I),
                 re.compile(r'diga ao DA o `o_que_fazer`', re.I)]
    achados = [(nome, m.group(0)) for nome, texto in _textos().items() for p in proibidos for m in p.finditer(texto)]
    assert achados == []


def test_skill_diz_que_o_comando_do_o_que_fazer_nunca_vai_ao_da():
    textos = _textos()
    regras = textos['regras-do-modelo.md']
    # a regra: o o_que_fazer fala com quem roda o motor; comando dele nunca chega ao DA; ato do DA vira clique na tela
    assert re.search(r'o_que_fazer[^\n]*nunca[^\n]*comando|comando[^\n]*o_que_fazer[^\n]*nunca', regras)
    assert 'clique' in regras
    # no concluido, o texto final do motor cita render, aprovacao e entrega: a skill manda abrir a tela, sem repetir
    fluxo = textos['fluxo.md']
    assert re.search(r'concluido[^\n]*', fluxo)
    assert 'entrega' in fluxo and 'próximo marco' in fluxo


def test_biblioteca_sem_guarda_que_cite_o_marcador():
    texto = (SKILL / 'SKILL.md').read_text(encoding='utf-8')
    # o marcador aparece uma vez so, na definicao; nada no texto manda tirar --biblioteca
    assert texto.count(MARCADOR) == 1
    for valor in ('D:/Agencia/biblioteca', ''):
        trocado = texto.replace(MARCADOR, valor)  # a troca que o Claude Code faz no texto da skill
        assert not re.search(r'tir\w*\s+`?--biblioteca', trocado)
        assert 'sem troca' not in trocado
    # o comando da tela leva sempre a biblioteca
    linhas_tela = [l for l in texto.splitlines() if 'tela abrir' in l and '-m desdobra' in l]
    assert linhas_tela and all('--biblioteca "BIBLIOTECA"' in l for l in linhas_tela)
    # o caso vazio continua tratado no texto
    assert 'vazia' in texto


def test_motor_trata_biblioteca_vazia_ou_sem_troca_como_nao_configurada():
    assert biblioteca.normalizar('') is None
    assert biblioteca.normalizar('   ') is None
    assert biblioteca.normalizar(MARCADOR) is None


def test_sinopse_de_job_criar_mostra_modo_dados_opcional():
    obrigatorio = re.compile(r'job criar[^\n]*(?<!\[)--modo-dados \{a,b,c\}')
    readme = (RAIZ_REPO / 'README.md').read_text(encoding='utf-8')
    assert not obrigatorio.search(readme)
    # a sinopse da entrada de fontes (M2) na doc de interfaces; a das linhas 200 a 208 e do K5
    doc = (RAIZ_REPO / 'docs' / 'm1-interfaces.md').read_text(encoding='utf-8')
    linhas = [l for l in doc.splitlines() if 'job criar' in l and '--fontes <arquivo ou pasta>' in l]
    assert linhas and not any(obrigatorio.search(l) for l in linhas)
