# -*- coding: utf-8 -*-
"""M7c, K5: os textos que chegam ao DA nao mandam ninguem ao terminal (decisoes-v1.md, 159).

O DA nunca roda comando. Todo o_que_fazer e todo FIM que o DA pode ver (pela tela ou pelo Claude, que repassa o
envelope) diz que o ato e um clique dele na tela ou pede ao Claude para abrir a tela ou seguir o job. Os comandos
continuam no motor so para os testes e para a Trezion.

Textos alcancaveis pelo DA, nos modulos deste passo:
  - humano.O_QUE_FAZER (recusa de um ato so do DA que partiu de fora da tela);
  - tela.O_QUE_FAZER_ABERTA e cada tela.O_QUE_FAZER_RECUSA;
  - o FIM da esteira, o o_que_fazer de cada fase da ESTEIRA e os textos de calcular_proxima (fase que falhou, fase que
    ainda nao rodou, job concluido);
  - os o_que_fazer de job/nucleo.py e job/fases.py, lidos do proprio codigo (ast), menos os erros de uso dos
    comandos que so o Claude e os testes rodam (job criar, trocar-entrada, remover-entrada: opcao --kv, --fontes,
    caminho da entrada). Esses ficam listados em SO_DO_CLAUDE, com o motivo.

Fora deste passo (outros modulos do motor que ainda citam comando de terminal num o_que_fazer: specs, entrega, ds,
leitor, briefing, derivacao) ficam como risco declarado em docs/m1-interfaces.md, secao "M7c, K5".
"""
import ast
import inspect
import re
from pathlib import Path

import pytest

from conftest import RAIZ_PLUGIN
from desdobra import humano, tela
from desdobra.job import fases as mod_fases
from desdobra.job import nucleo
from desdobra.job.nucleo import ErroJob

# o que conta como mandar alguem ao terminal num texto para o DA
PROIBIDOS = (
    ('comando entre aspas', re.compile(r'"\s*desdobra\s', re.I)),
    ('subcomando do motor', re.compile(r'\bdesdobra\s+(?:job|spec|render|aprovar|entregar|parametros-entrega|briefing|'
                                       r'ds|fontes|derivar|doctor|conferir-entrega|tela|ler|sugestao|linkado|marca)\b',
                                       re.I)),
    ('opcao de linha de comando', re.compile(r'(?<![\w-])--[a-z]', re.I)),
    ('terminal', re.compile(r'\bterminal\b', re.I)),
    ('prompt de comando', re.compile(r'prompt de comando', re.I)),
    ('powershell', re.compile(r'powershell', re.I)),
    ('rode', re.compile(r'\brode\b', re.I)),
    ('digite', re.compile(r'\bdigite\b', re.I)),
    ('marcador de pasta', re.compile(r'<pasta>', re.I)),
)
TRAVESSAO = ('—', '–')
NAO_E_X_E_Y = re.compile(r'\bnão é [^.;:]{1,60}, é\b', re.I)
# funcoes de job/nucleo.py cujos o_que_fazer sao erro de uso de comando que so o Claude e os testes rodam (a skill
# novo-job cria o job; a continuar troca e remove entrada). O DA nunca ve o argumento; o Claude corrige a chamada
SO_DO_CLAUDE = {
    'criar': 'erro de uso do job criar (opcao --kv, --fontes, --campanha, --specs, modo)',
    'trocar_entrada': 'erro de uso do job trocar-entrada (caminho relativo, caixa, arquivo novo)',
    'remover_entrada': 'erro de uso do job remover-entrada (caminho da fonte)',
    '_arquivos_de_fonte_oferecidos': 'erro de uso de --fontes do job criar',
    '_recusar_fontes': 'erro de uso do job criar (fonte na pasta de campanha ou de specs)',
}
CONSTANTES_SO_DO_CLAUDE = {'O_QUE_FAZER_FONTE_FORA': 'erro de uso do job criar (fonte em --campanha ou --specs)'}


def _problemas(texto):
    achados = [nome for nome, rx in PROIBIDOS if rx.search(texto)]
    if any(t in texto for t in TRAVESSAO):
        achados.append('travessao')
    if NAO_E_X_E_Y.search(texto):
        achados.append('nao e X, e Y')
    return achados


class _Fase:
    def __init__(self, id_, o_que_fazer='', tipo='fase', descricao='uma fase'):
        self.id, self.o_que_fazer, self.tipo, self.descricao = id_, o_que_fazer, tipo, descricao


def _textos_em_tempo_de_execucao():
    textos = {'humano.O_QUE_FAZER': humano.O_QUE_FAZER, 'tela.O_QUE_FAZER_ABERTA': tela.O_QUE_FAZER_ABERTA,
              'fases.FIM': mod_fases.FIM, 'nucleo.FIM': nucleo.FIM}
    textos.update({'tela.O_QUE_FAZER_RECUSA[%s]' % k: v for k, v in tela.O_QUE_FAZER_RECUSA.items()})
    textos.update({'fase %s' % f.id: f.o_que_fazer for f in nucleo.ESTEIRA})
    # calcular_proxima: fase que falhou sem texto proprio, fase que ainda nao rodou, job concluido
    sem_texto = _Fase('x')
    for situacao, rotulo in (('falhou', 'proxima falha'), ('pendente', 'proxima fase')):
        estado = {'fases': {'x': {'situacao': situacao}}}
        textos[rotulo] = nucleo.calcular_proxima(estado, {'x': (False, None)}, [sem_texto])['o_que_fazer']
    textos['proxima concluido'] = nucleo.calcular_proxima({'fases': {}}, {}, [])['o_que_fazer']
    return textos


TEXTOS = _textos_em_tempo_de_execucao()


@pytest.mark.parametrize('rotulo', sorted(TEXTOS))
def test_texto_do_da_sem_comando_de_terminal(rotulo):
    texto = TEXTOS[rotulo]
    assert isinstance(texto, str) and texto.strip(), rotulo
    assert _problemas(texto) == [], (rotulo, texto)


def test_job_sem_pasta_de_job_manda_ao_claude(tmp_path):
    with pytest.raises(ErroJob) as e:
        nucleo.conferir_job(tmp_path)
    assert _problemas(e.value.o_que_fazer) == [] and 'Claude' in e.value.o_que_fazer


def test_o_que_fazer_do_ato_do_da_e_um_clique_na_tela():
    t = humano.O_QUE_FAZER
    assert 'clique seu na tela' in t and 'Peça ao Claude para abrir a tela' in t


def test_fim_manda_o_da_a_tela():
    assert 'Peça ao Claude para abrir a tela' in nucleo.FIM and 'clique' in nucleo.FIM
    # os FIM antigos dos marcos M1 a M6, com comando de terminal, sairam do motor
    assert not [n for n in vars(mod_fases) if re.fullmatch(r'FIM_M\d+', n)]


def test_falha_de_fase_manda_ao_claude_e_ao_doctor():
    for f in nucleo.ESTEIRA:
        assert 'Peça ao Claude' in f.o_que_fazer and 'doctor' in f.o_que_fazer, f.id


# ------------------------------------------------------------------ varredura do codigo
def _strings(no):
    return [n.value for n in ast.walk(no) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def _o_que_fazer_do_codigo(modulo):
    """(rotulo, texto) de cada string que vira o_que_fazer ou FIM no codigo do modulo: argumento o_que_fazer=, chave
    'o_que_fazer' de dict, constante O_QUE_FAZER* ou FIM* e o_que_fazer de Fase(...). Pula o que esta em SO_DO_CLAUDE."""
    arvore = ast.parse(Path(inspect.getsourcefile(modulo)).read_text(encoding='utf-8'))
    pais = {}
    for no in ast.walk(arvore):
        for filho in ast.iter_child_nodes(no):
            pais[filho] = no

    def funcao_de(no):
        while no in pais:
            no = pais[no]
            if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return no.name
        return None

    saida = []
    for no in ast.walk(arvore):
        alvos = []
        if isinstance(no, ast.keyword) and no.arg == 'o_que_fazer':
            alvos.append(no.value)
        elif isinstance(no, ast.Dict):
            alvos += [v for k, v in zip(no.keys, no.values)
                      if isinstance(k, ast.Constant) and k.value == 'o_que_fazer']
        elif isinstance(no, ast.Assign):
            nomes = [t.id for t in no.targets if isinstance(t, ast.Name)]
            if any(re.match(r'(O_QUE_FAZER|FIM)', n) for n in nomes):
                if any(n in CONSTANTES_SO_DO_CLAUDE for n in nomes):
                    continue
                alvos.append(no.value)
        for alvo in alvos:
            if funcao_de(alvo) in SO_DO_CLAUDE:
                continue
            for s in _strings(alvo):
                saida.append(('%s:%d' % (modulo.__name__, getattr(alvo, 'lineno', 0)), s))
    return saida


@pytest.mark.parametrize('modulo', [humano, tela, mod_fases, nucleo], ids=lambda m: m.__name__)
def test_codigo_sem_o_que_fazer_com_comando_de_terminal(modulo):
    achados = [(r, s, _problemas(s)) for r, s in _o_que_fazer_do_codigo(modulo) if _problemas(s)]
    assert achados == []


def test_a_varredura_acha_um_comando_de_terminal():
    """A varredura pega o caso que ela existe para pegar (e nao passa em branco por um texto que mudou de forma)."""
    assert 'comando entre aspas' in _problemas('Rode "desdobra job proxima".')
    assert 'terminal' in _problemas('Abra um terminal próprio.')
    assert 'opcao de linha de comando' in _problemas('Passe --job <pasta>.')
    assert _problemas('Peça ao Claude para abrir a tela do job.') == []
    # a varredura do nucleo ve os textos de fase e o FIM
    vistos = [s for _r, s in _o_que_fazer_do_codigo(nucleo)]
    assert any('falhou' in s for s in vistos)


# ------------------------------------------------------------------ docs
DOC = RAIZ_PLUGIN.parents[1] / 'docs' / 'm1-interfaces.md'


def test_doc_nao_diz_mais_que_o_modo_vem_do_estado_nem_que_modo_dados_e_obrigatorio():
    texto = DOC.read_text(encoding='utf-8')
    assert '`--modo-dados` é obrigatório' not in texto
    assert 'O modo do envelope é o `modo_dados` do `estado.json`' not in texto
    assert '## M7c, K5' in texto


# ------------------------------------------------------------------ revisao do K5: a recusa inteira, o doctor e as skills
# A recusa de um ato so do DA (o envelope que o Claude recebe quando tenta um deles) leva o o_que_fazer e as linhas
# humanas. As duas partes chegam ao DA juntas e nenhuma manda ao terminal nem contradiz a outra.
class _Args:
    """Argumentos do comando: so a pasta do job; o resto e None (a recusa vem antes de qualquer outro argumento)."""

    def __init__(self, job):
        self.job = str(job)

    def __getattr__(self, nome):
        return None


def _comandos_de_recusa():
    from desdobra import briefing, entrega, render, specs
    return {'render': render._render, 'linkado confirmar': render._linkado_confirmar,
            'spec confirmar': specs._confirmar, 'briefing confirmar': briefing._confirmar,
            'aprovar': entrega._aprovar, 'entregar': entrega._entregar,
            'parametros-entrega': entrega._parametros_entrega}


def test_todo_comando_humano_tem_recusa_conferida():
    assert set(_comandos_de_recusa()) == set(humano.COMANDOS)


@pytest.mark.parametrize('comando', sorted(humano.COMANDOS))
def test_recusa_do_ato_do_da_sem_terminal_e_sem_contradicao(comando, tmp_path, monkeypatch):
    from desdobra.resultado import Codigo
    monkeypatch.setattr(humano, 'console_interativo', lambda: (False, 'sem_terminal'))
    r = _comandos_de_recusa()[comando](_Args(tmp_path))
    assert r.codigo == int(Codigo.RECUSADO) and r.situacao == 'recusado', (comando, r.o_que_fazer)
    for texto in [r.o_que_fazer] + list(r.linhas_humanas):
        assert _problemas(texto) == [], (comando, texto)
    if comando in humano.ATOS_SEM_BOTAO:
        # a tela ainda nao tem este ato (M8): o texto nao promete um clique que o DA nao acha
        assert 'clique seu na tela' not in r.o_que_fazer and 'próximo marco' in r.o_que_fazer, r.o_que_fazer
    else:
        assert r.o_que_fazer == humano.O_QUE_FAZER


def test_atos_sem_botao_sao_os_que_a_tela_nao_tem():
    from desdobra.tela import atos
    fonte = inspect.getsource(atos)
    assert set(humano.ATOS_SEM_BOTAO) <= set(humano.COMANDOS)
    for comando in humano.ATOS_SEM_BOTAO:
        assert "'%s'" % comando not in fonte, comando
    assert humano.o_que_fazer('render') == humano.O_QUE_FAZER
    assert humano.o_que_fazer('entregar') == humano.O_QUE_FAZER_SEM_BOTAO


def test_verificacao_quebrada_do_doctor_nao_manda_ao_terminal():
    from desdobra.doctor import _quebrou
    t = _quebrou('x', RuntimeError()).o_que_fazer
    assert _problemas(t) == [] and 'Claude' in t, t


SKILLS = RAIZ_PLUGIN / 'skills'


def test_skills_nao_dizem_que_o_texto_final_do_motor_cita_terminal():
    for rel in ('continuar/SKILL.md', 'novo-job/SKILL.md', 'novo-job/references/fluxo.md'):
        texto = (SKILLS / rel).read_text(encoding='utf-8')
        assert 'cita atos do DA pelo terminal' not in texto, rel
        assert 'com comandos de terminal' not in texto, rel


def test_skill_doctor_nao_manda_o_da_ao_terminal():
    texto = (SKILLS / 'doctor' / 'SKILL.md').read_text(encoding='utf-8')
    assert 'Peça ao DA para rodar' not in texto
    assert not re.search(r'\bno terminal\b', texto)
