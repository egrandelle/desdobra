# -*- coding: utf-8 -*-
"""Revisao adversarial do M5: um ou mais testes por achado, escritos antes da correcao (falham no codigo de antes).

B1 rascunho que forja briefing do DA; A1 portao de entrega que so olha a origem; gancho (derivacao/, escritas por
rename e --saida, python -m desdobra.cli); A2 render que confia em derivacao/<id>.json; A3 texto e marca que
encostam na borda fugiam da folha; A4 base arquivo sem giro; M1 mestre sem elemento; M2 hierarquia estrita; M3 ids
reservados; M4 formato sem folha ou com outra dimensao; M5 derivar --formato apagava as outras devolucoes; baixos.
"""
import argparse
import json
import subprocess
import sys

import pytest

import test_derivacao_apoio as ap
from desdobra import arquivos, contratos
from desdobra.briefing import modelo as mb
from desdobra.derivacao import nucleo as nd
from desdobra.derivacao import solver as msol
from desdobra.derivacao import validacao as mval
from desdobra.resultado import Codigo
from test_derivacao_job import _cli, _importar, job_der  # noqa: F401  (fixture do job sintetico)

RAIZ_PLUGIN = __import__('pathlib').Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')


def _derivar(laudo=None, briefing=None, specs=None, so=None):
    ctx = nd.contexto(laudo or ap.laudo(), briefing or ap.briefing())
    return nd.derivar_em_memoria(ctx, specs=specs or {}, arquivo_specs='specs/rascunho.json', so=so)


def _el(d, ident):
    return next(e for e in d['elementos'] if e['id'] == ident)


def _copia(job_der, tmp_path, nome='copia'):
    import shutil
    job = tmp_path / nome
    shutil.copytree(job_der['job'], job)
    return job


# ------------------------------------------------------------------ B1
def test_b1_rascunho_nunca_tem_origem_da_e_o_portao_e_o_derivar_recusam(job_der, tmp_path):
    job = _copia(job_der, tmp_path)
    dados, _c = mb.rascunho(job)
    assert dados['cabecalho']['origem'] == 'rascunho'
    contratos.gravar(job / mb.ARQUIVO, dados, 'briefing/1')
    assert mb.conferir_para_entrega(job) == (False, 'briefing_rascunho')
    with pytest.raises(nd.ErroDerivacao) as e:
        nd.derivar(job)
    assert e.value.motivo == 'briefing_rascunho'


def test_b1_rascunho_saida_recusa_os_arquivos_do_job_e_grava_fora_deles(job_der, tmp_path):
    import _winapi
    from desdobra import briefing as cli_b
    job = _copia(job_der, tmp_path)
    for rel in ('specs/confirmacoes.json', 'render/origem/render.json', 'derivacao/perto.json', 'briefing/x.json'):
        (job / rel).parent.mkdir(parents=True, exist_ok=True)
        (job / rel).write_text('{"do_da": true}', encoding='utf-8')
    juncao = tmp_path / 'juncao'
    _winapi.CreateJunction(str(job / 'briefing'), str(juncao))
    alvos = [job / 'briefing' / 'briefing-confirmado.json', job / 'specs' / 'confirmacoes.json',
             job / 'render' / 'origem' / 'render.json', job / 'derivacao' / 'perto.json',
             job / 'laudo' / '..' / 'briefing' / 'x.json', juncao / 'briefing-confirmado.json', job / 'estado.json']
    for alvo in alvos:
        antes = alvo.read_bytes() if alvo.exists() else None
        r = cli_b._rascunho(argparse.Namespace(job=str(job), saida=str(alvo)))
        assert r.codigo == int(Codigo.RECUSADO), alvo
        assert (alvo.read_bytes() if alvo.exists() else None) == antes, alvo
    r = cli_b._rascunho(argparse.Namespace(job=str(job), saida=None))
    assert r.codigo == 0
    padrao = job / 'rotulagem' / 'briefing-rascunho.json'
    assert json.loads(padrao.read_text(encoding='utf-8'))['cabecalho']['origem'] == 'rascunho'
    fora = tmp_path / 'fora' / 'r.json'
    assert cli_b._rascunho(argparse.Namespace(job=str(job), saida=str(fora))).codigo == 0 and fora.is_file()


def test_b1_importar_teste_grava_por_cima_do_rascunho(job_der, python, tmp_path):
    job = _copia(job_der, tmp_path)
    dados, _c = mb.rascunho(job)
    contratos.gravar(job / mb.ARQUIVO, dados, 'briefing/1')
    cod, env = _importar(job_der, python, job)
    assert cod == 0, env


# ------------------------------------------------------------------ A1
def test_a1_portao_de_entrega_confere_o_conteudo_do_briefing(job_der, python, tmp_path):
    job = _copia(job_der, tmp_path)
    _importar(job_der, python, job)
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    b['cabecalho']['origem'], b['cabecalho']['meio'] = 'da', 'terminal'
    b['modo_dados'] = ap.pendente()
    contratos.gravar(job / mb.ARQUIVO, b, 'briefing/1')
    assert mb.conferir_para_entrega(job) == (False, 'briefing_com_problema')


# ------------------------------------------------------------------ gancho
def _gancho(ferramenta, entrada):
    script = RAIZ_PLUGIN / 'scripts' / 'gancho_confirmacoes.py'
    r = subprocess.run([sys.executable, '-I', '-B', str(script)], input=json.dumps(
        {'hook_event_name': 'PreToolUse', 'tool_name': ferramenta, 'tool_input': entrada}).encode(),
        capture_output=True, timeout=60)
    txt = r.stdout.decode('utf-8').strip()
    return json.loads(txt)['hookSpecificOutput']['permissionDecision'] if txt else 'segue'


def test_gancho_cobre_derivacao_renomear_saida_e_desdobra_cli():
    J = 'C:\\jobs\\j1'
    negar = [('Bash', 'desdobra briefing rascunho --job %s --saida %s/briefing/briefing-confirmado.json' % (J, J)),
             ('Bash', 'desdobra briefing rascunho --job %s --saida %s\\specs\\confirmacoes.json' % (J, J)),
             ('Bash', 'python -c "import os;os.replace(\'x.json\', r\'%s\\briefing\\briefing-confirmado.json\')"' % J),
             ('Bash', 'python -c "import os;os.rename(\'x.json\', r\'%s\\derivacao\\perto.json\')"' % J),
             ('Bash', 'python -c "import shutil;shutil.copy(\'x\', r\'%s\\derivacao\\perto.json\')"' % J),
             ('PowerShell', 'Rename-Item x.json %s\\briefing\\briefing-confirmado.json' % J),
             ('PowerShell', 'Move-Item x.json %s\\derivacao\\vertical.json' % J),
             ('PowerShell', 'Copy-Item x.json %s\\specs\\confirmacoes.json' % J),
             ('Bash', 'cmd /c ren x.json %s\\derivacao\\perto.json' % J),
             ('Bash', 'python -m desdobra.cli render --job %s --formato perto' % J),
             ('Bash', 'python -m desdobra.cli briefing confirmar --job %s' % J)]
    for ferramenta, c in negar:
        assert _gancho(ferramenta, {'command': c}) == 'deny', c
    for caminho in (J + '/derivacao/perto.json', J + '\\derivacao\\devolucoes.json'):
        assert _gancho('Write', {'file_path': caminho}) == 'deny'
        assert _gancho('Edit', {'file_path': caminho}) == 'deny'
    seguir = [('Bash', 'python -m desdobra derivar --job %s' % J),
              ('Bash', 'python -m desdobra briefing importar f.json --teste --job %s' % J),
              ('Bash', 'type %s\\derivacao\\perto.json' % J)]
    for ferramenta, c in seguir:
        assert _gancho(ferramenta, {'command': c}) == 'segue', c
    for caminho in ('C:/repo/plugins/desdobra/motor/desdobra/derivacao/nucleo.py',
                    'C:/repo/plugins/desdobra/motor/desdobra/briefing/modelo.py',
                    'C:/repo/plugins/desdobra/motor/schemas/derivacao-1.json',
                    'C:/repo/plugins/desdobra/testes/test_derivacao.py'):
        assert _gancho('Edit', {'file_path': caminho}) == 'segue', caminho


# ------------------------------------------------------------------ A2
def test_a2_render_refaz_a_derivacao_e_recusa_arquivo_mexido(job_der, python, tmp_path):
    from desdobra.render import derivado as mder
    job = _copia(job_der, tmp_path)
    _importar(job_der, python, job)
    assert _cli(python, 'derivar', '--job', str(job))[0] == 0
    _c, bloqueios, _p = mder.montar(job, 'perto')
    assert not bloqueios
    # o formato devolvido vira "derivado" a mao
    perto = json.loads((job / 'derivacao' / 'perto.json').read_text(encoding='utf-8'))
    vert = json.loads((job / 'derivacao' / 'vertical.json').read_text(encoding='utf-8'))
    vert.update(situacao='derivado', devolucao=None, caminho='solver', elementos=perto['elementos'])
    arquivos.gravar_json_atomico(job / 'derivacao' / 'vertical.json', vert)
    _c, bloqueios, _p = mder.montar(job, 'vertical')
    assert [b['codigo'] for b in bloqueios] == ['derivacao_desatualizada']
    # parametro do job mudado depois do derivar
    (job / 'parametros').mkdir(exist_ok=True)
    arquivos.gravar_json_atomico(job / 'parametros' / 'derivacao.json', {'faixa': 9.0})
    _c, bloqueios, _p = mder.montar(job, 'perto')
    assert [b['codigo'] for b in bloqueios] == ['derivacao_desatualizada']


# ------------------------------------------------------------------ A3
def test_a3_texto_e_marca_na_borda_do_kv_ficam_dentro_da_faixa_e_da_area_segura():
    camadas = [ap.camada(1, 'pixel', [0, 0, 400, 200]), ap.camada(30, 'smart_embutido', [320, 150, 400, 200]),
               ap.camada(40, 'texto', [20, 185, 300, 200], corpo=8)]
    laudo = ap.laudo(400, 200, camadas)
    chave = 'teste|faixa|480x300'
    specs = {chave: ap.spec(chave, {'faixas': [{'lado': 'inferior', 'px': 60}],
                                    'area_segura': {'px': 20, 'pct': None, 'lados': ['inferior', 'direita']}})}
    b = ap.briefing(funcoes={1: 'fundo', 30: 'logo_principal', 40: 'texto_legal'},
                    formatos=[ap.formato('faixa', 480, 300, chave=chave)], familias={'base': ap.decisao('composicao')})
    d = _derivar(laudo, b, specs)['formatos']['faixa']
    if d['situacao'] == 'devolvido':
        assert d['devolucao']['restricao']['fonte']['tipo'] == 'folha'
        return
    for ident in ('el30', 'el40'):
        c = _el(d, ident)['caixa']
        assert c[3] <= 240 + 1 and c[2] <= 460 + 1, (ident, c)
    assert not mval.reprovadas(d['validacoes'])


def test_a3_fundo_continua_sangrando_por_baixo_da_faixa():
    chave = 'teste|faixa|480x300'
    specs = {chave: ap.spec(chave, {'faixas': [{'lado': 'inferior', 'px': 48}]})}
    d = _derivar(briefing=ap.briefing(formatos=[ap.formato('f', 480, 300, chave=chave)],
                                      familias={'base': ap.decisao('composicao')}), specs=specs)['formatos']['f']
    assert d['situacao'] == 'derivado' and _el(d, 'el1')['caixa'][3] >= 300


# ------------------------------------------------------------------ A4
def test_a4_base_arquivo_gira_com_a_rotacao():
    f = ap.formato('girado', 800, 400, rotacao={'graus': 90, 'sentido': 'horario'})
    for base in ('arquivo', 'composicao', 'area_util'):
        d = _derivar(briefing=ap.briefing(formatos=[f], familias={'base': ap.decisao(base)}))['formatos']['girado']
        assert d['situacao'] == 'devolvido' and d['devolucao']['motivo'] == 'troca_forte_de_orientacao', base


# ------------------------------------------------------------------ M1
def test_m1_mestre_sem_elemento_e_recusada_e_o_solver_vazio_nao_levanta():
    camadas = [ap.camada(1, 'pixel', [0, 0, 400, 200])]
    b = ap.briefing(funcoes={1: 'fora_da_peca'}, formatos=[ap.formato('perto', 480, 300)], ancoras={})
    assert any(e['codigo'] == 'mestre_sem_elemento' for e in mb.conferir(ap.laudo(400, 200, camadas), b, ap.JOB))
    assert msol.resolver([], (400, 200), (480, 300), {}, []) == ([], [], [])


def test_m1_um_formato_que_quebra_nao_derruba_os_outros(monkeypatch):
    original = nd.derivar_formato

    def quebra(ctx, kv, mestres, formato, *a, **k):
        if formato['id'] == 'perto':
            raise ValueError('quebra de teste')
        return original(ctx, kv, mestres, formato, *a, **k)
    monkeypatch.setattr(nd, 'derivar_formato', quebra)
    r = _derivar()
    assert r['formatos']['mesmo']['situacao'] == 'derivado'
    d = r['formatos']['perto']
    assert d['situacao'] == 'devolvido' and d['devolucao']['motivo'] == 'erro_no_formato'
    assert d['devolucao']['medidas']['erro'] == 'ValueError'
    contratos.validar(d, 'derivacao/1')


# ------------------------------------------------------------------ M2
def test_m2_hierarquia_estrita_media_vence_fraca_em_elemento_fino():
    sg = {'esq': False, 'topo': False, 'dir': False, 'base': False}
    for w0 in (40.0, 2.0):
        els = [{'id': 'a', 'caixa': [100.0, 100.0, 300.0, 140.0], 'sangra': sg, 'classe': 'texto', 'funcao': 'titulo',
                'regra': 'constante', 'ancora': ('esquerda', 'topo')},
               # b comeca 10 px a direita de a: sem alinhamento entre os dois (com alinhamento, a e b formam um grupo
               # que anda pela ancora do maior; rodada 3), o teste fica so na hierarquia de forcas
               {'id': 'b', 'caixa': [110.0, 300.0, 110.0 + w0, 340.0], 'sangra': sg, 'classe': 'base',
                'funcao': 'grafismo', 'regra': 'constante', 'ancora': ('direita', 'topo')}]
        for U in (1920.0, 3840.0):
            W, H = U, U * 0.5625
            caixas, escalas, _r = msol.resolver(els, (1920.0, 1080.0), (W, H), {}, [W / 1920.0, 1.0])
            alvo_a = 100.0 / 1920.0 * W
            alvo_b = W - (1920.0 - els[1]['caixa'][2]) / 1920.0 * W
            assert abs(caixas[0][0] - alvo_a) < 1e-4, (w0, U, caixas[0])
            assert abs(caixas[1][2] - alvo_b) < 1e-4, (w0, U, caixas[1])


def test_m2_forca_seguinte_que_nao_anda_fica_com_a_solucao_da_anterior(monkeypatch):
    """No corpus (KV B 960x576), o otimo preso de uma forca deixou a seguinte sem solucao numerica; isso nunca e
    uma obrigatoria que nao fecha."""
    original = msol._linprog
    chamadas = []

    def falha_na_terceira(c, *a, **k):
        chamadas.append(1)
        r = original(c, *a, **k)
        if len(chamadas) == 3:  # 1: cabe; 2: forte; 3: media
            r.status = 2
        return r
    monkeypatch.setattr(msol, '_linprog', falha_na_terceira)
    kv = nd.mestre_do_kv(nd.contexto(ap.laudo(), ap.briefing()))
    caixas, escalas, _r = msol.resolver(kv['elementos'], (400, 200), (480, 300), {}, [1.0] * len(kv['elementos']))
    assert len(caixas) == len(kv['elementos'])


# ------------------------------------------------------------------ M3
def test_m3_ids_reservados_sao_recusados():
    from desdobra import render as cli_r
    for ident in ('devolucoes', 'origem', 'nul', 'con', 'aux', 'prn', 'com1', 'com9', 'lpt1', 'lpt9'):
        b = ap.briefing(formatos=[ap.formato(ident, 480, 300)])
        with pytest.raises(contratos.ErroContrato):
            contratos.validar(b, 'briefing/1')
        assert any(e['codigo'] == 'formato_id_reservado' for e in mb.conferir(ap.laudo(), b, ap.JOB)), ident
    for ident in ('devolucoes', 'nul', 'con', 'com1', 'lpt1'):
        with pytest.raises(argparse.ArgumentTypeError):
            cli_r._id_formato(ident)
    assert cli_r._id_formato('origem') == 'origem' and cli_r._id_formato('com10') == 'com10'


# ------------------------------------------------------------------ M4
def test_m4_formato_sem_folha_ou_com_outra_dimensao_nao_deriva_em_silencio():
    chave = 'teste|faixa|480x300'
    specs = {chave: ap.spec(chave, {'faixas': [{'lado': 'inferior', 'px': 100}],
                                    'dimensao': {'largura': 480, 'altura': 300}})}
    fmts = [ap.formato('a', 480, 300, chave=chave), ap.formato('b', 480, 300, chave=chave + 'x'),
            ap.formato('c', 960, 540, chave=chave), ap.formato('d', 480, 300, chave='humano|medida|480x300', sem_folha=True)]
    r = _derivar(briefing=ap.briefing(formatos=fmts, familias={'base': ap.decisao('composicao')}), specs=specs)
    f = r['formatos']
    assert f['a']['situacao'] == 'derivado'
    assert f['b']['situacao'] == 'devolvido' and f['b']['devolucao']['motivo'] == 'formato_sem_folha'
    assert f['c']['situacao'] == 'devolvido' and f['c']['devolucao']['motivo'] == 'dimensao_diferente_da_folha'
    assert f['d']['situacao'] == 'derivado' and any(x['codigo'] == 'formato_sem_folha' for x in f['d']['registros'])


# ------------------------------------------------------------------ M5
def test_m5_derivar_um_formato_mantem_as_outras_devolucoes(job_der, python, tmp_path):
    job = _copia(job_der, tmp_path)
    _importar(job_der, python, job)
    assert _cli(python, 'derivar', '--job', str(job))[0] == 0
    assert _cli(python, 'derivar', '--job', str(job), '--formato', 'perto')[0] == 0
    dev = contratos.ler(job / 'derivacao' / 'devolucoes.json', 'devolucoes/1')
    assert [d['formato'] for d in dev['devolucoes']] == ['vertical']
    assert dev['inventario']['formatos'] == 2


# ------------------------------------------------------------------ baixos
def test_baixo_mesma_proporcao_vence_a_banda_do_quadrado():
    camadas = [ap.camada(1, 'pixel', [0, 0, 1051, 1000]), ap.camada(2, 'texto', [100, 100, 600, 200], corpo=40)]
    b = ap.briefing(funcoes={1: 'fundo', 2: 'titulo'}, formatos=[ap.formato('quase', 1052, 1000)],
                    familias={'base': ap.decisao('composicao')})
    d = _derivar(ap.laudo(1051, 1000, camadas), b)['formatos']['quase']
    assert d['situacao'] == 'derivado'


def test_baixo_motivo_de_orientacao_fica_com_mestres_demais():
    from test_derivacao import _propria
    b = ap.briefing(formatos=[ap.formato('v300', 300, 600), ap.formato('v320', 320, 560)],
                    mestres=[{'id': 'kv', 'tipo': 'kv'}, _propria()], familias={'mestres_max': ap.decisao(1)})
    r = _derivar(briefing=b)
    assert r['formatos']['v300']['devolucao']['motivo'] == 'acima_do_numero_de_mestres'
    d = r['formatos']['v320']['devolucao']
    assert d['motivo'] == 'troca_forte_de_orientacao' and d['medidas']['mestres_max_atingido'] is True


def test_baixo_importar_sobre_briefing_invalido_e_mensagem_tratada(job_der, tmp_path):
    job = _copia(job_der, tmp_path)
    (job / 'briefing').mkdir(exist_ok=True)
    (job / mb.ARQUIVO).write_text('{"esquema": "briefing/1"}', encoding='utf-8')
    with pytest.raises(mb.ErroBriefing):
        mb.importar_teste(job, job_der['fixture'])


def test_baixo_doctor_confere_o_highs():
    import inspect

    from desdobra import doctor
    from desdobra.doctor import verificacoes as v
    assert "('scipy_highs'" in inspect.getsource(doctor.rodar_verificacoes)
    assert v.verificar_highs().situacao == 'ok'


def test_baixo_validacao_rele_o_briefing_gravado_depois_do_layout(job_der, python, tmp_path):
    job = _copia(job_der, tmp_path)
    _importar(job_der, python, job)
    assert _cli(python, 'derivar', '--job', str(job))[0] == 0
    assert nd.conferir_layout(job, 'perto') == []
    b = contratos.ler(job / mb.ARQUIVO, 'briefing/1')
    apoio = job_der['ids']['texto-apoio']
    for f in b['funcoes']:
        if f['layer_id'] == apoio:
            f['funcao']['valor'] = 'texto_legal'
    b['regras_escala'].append({'funcao': 'texto_legal', 'regra': ap.decisao('constante')})
    contratos.gravar(job / mb.ARQUIVO, b, 'briefing/1')
    ruins = nd.conferir_layout(job, 'perto')
    assert [v['elementos'] for v in ruins] == [['el%d' % apoio]] and ruins[0]['nome'] == 'regra_por_funcao'
