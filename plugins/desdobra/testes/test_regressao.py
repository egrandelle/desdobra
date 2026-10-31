# -*- coding: utf-8 -*-
"""Regressao: mapeamento sonda -> laudo/1, comparador, causas, agenda por tamanho e relatorio.

Tudo com laudos sinteticos. A comparacao da linha de base real com ela mesma roda so quando a variavel de
ambiente DESDOBRA_LINHA_DE_BASE aponta para a pasta dela (nenhum caminho do corpus fica no repositorio).
"""
import copy
import json
import os
import threading
import time
from pathlib import Path

import pytest

from conftest import psd_minimo
from desdobra import contratos, regressao
from desdobra.arquivos import gravar_json_atomico, ler_json
from desdobra.regressao import comparar, executar, mapeamento
from desdobra.resultado import Codigo
from test_sugestao_apoio import camada_sonda, laudo1_equivalente, laudo_sonda


def _sonda_basica(**kw):
    return laudo_sonda([
        camada_sonda(1, 'group'),
        camada_sonda(2, 'type', texto='Texto sintético', bbox=(5, 5, 50, 20)),
        camada_sonda(3, 'smartobject', smart={'tipo': 'embedded', 'tipo_bruto': 'liFD'}),
        camada_sonda(4, 'curves'),
        camada_sonda(5, 'pixel', status='degradado', motivos=['D8: camada visivel dentro de grupo oculto']),
        camada_sonda(6, 'solidcolorfill', visivel=False),
    ], **kw)


# ------------------------------------------------------------------ mapeamento
@pytest.mark.parametrize('kind, smart, esperado', [
    ('type', None, 'texto'), ('shape', None, 'forma'), ('pixel', None, 'pixel'), ('group', None, 'grupo'),
    ('artboard', None, 'prancheta'), ('solidcolorfill', None, 'cor_solida'), ('gradientfill', None, 'preenchimento'),
    ('huesaturation', None, 'ajuste'), ('levels', None, 'ajuste'), ('qualquercoisa', None, 'outro'),
    ('smartobject', {'tipo': 'embedded'}, 'smart_embutido'), ('smartobject', {'tipo': 'external'}, 'smart_linkado'),
])
def test_tipo_da_sonda(kind, smart, esperado):
    assert mapeamento.tipo_da_sonda(camada_sonda(1, kind, smart=smart)) == esperado


def test_situacao_e_regras_da_sonda():
    c = camada_sonda(1, status='degradado', motivos=['D9: outro recurso', 'D7: faux bold', 'nota sem regra'])
    assert mapeamento.situacao_da_sonda(c) == 'degradada'
    assert mapeamento.regras_da_sonda(c) == ['D7', 'D9']
    assert mapeamento.situacao_da_sonda(camada_sonda(1, status='lido')) == 'lida'


def test_normalizar_reconhece_o_formato():
    s = _sonda_basica()
    assert mapeamento.normalizar(s)['formato'] == 'sonda'
    assert mapeamento.normalizar(laudo1_equivalente(s))['formato'] == 'laudo/1'


# ------------------------------------------------------------------ comparador
def test_base_contra_ela_mesma_da_zero_diferenca():
    s = _sonda_basica()
    r = comparar.comparar_arquivo(mapeamento.normalizar(s), mapeamento.normalizar(copy.deepcopy(s)))
    assert r['diferencas'] == [] and not r['piorou']
    assert r['execucao']['resultado'] == 'igual' and r['prova_pixel']['resultado'] == 'igual'


def test_sonda_contra_laudo1_equivalente_da_zero_diferenca():
    s = _sonda_basica()
    r = comparar.comparar_arquivo(mapeamento.normalizar(s), mapeamento.normalizar(laudo1_equivalente(s)))
    assert r['diferencas'] == [] and not r['piorou']


def _agora(s, mudar):
    la = laudo1_equivalente(s)
    mudar(la)
    return mapeamento.normalizar(la, {'situacao': 'ok', 'tempo_s': 2.0})


def _camada(la, lid):
    return next(c for c in la['camadas'] if c['identidade']['layer_id'] == lid)


def test_d9_aposentada_e_causa_registrada():
    s = _sonda_basica()
    c = s['camadas'][3]
    c['laudo'] = {'status': 'degradado', 'motivos': ['D9: outro recurso que o psd-tools nao desenha']}
    r = comparar.comparar_arquivo(mapeamento.normalizar(s),
                                  _agora(s, lambda la: _camada(la, 4).update(situacao='lida', motivos=[])))
    assert [(d['layer_id'], d['campo'], d['causa']) for d in r['diferencas']] == [(4, 'situacao', 'd9_aposentada')]
    assert r['diferencas'][0]['base'] == 'degradada' and r['diferencas'][0]['agora'] == 'lida'


def test_regra_nova_do_laudo_e_causa_registrada():
    s = _sonda_basica()

    def mudar(la):
        c = _camada(la, 3)
        c['situacao'] = 'degradada'
        c['motivos'] = [{'regra': 'D6', 'descricao': 'warp', 'medida': None, 'limite': None,
                         'fonte': {'arquivo': 'arquitetura-v1.md'}}]

    r = comparar.comparar_arquivo(mapeamento.normalizar(s), _agora(s, mudar))
    (d,) = r['diferencas']
    assert d['causa'] == 'regra_do_laudo' and d['detalhe'] == {'regras_so_na_base': [], 'regras_so_agora': ['D6']}


def test_caixa_tipo_visibilidade_e_texto_sem_causa():
    s = _sonda_basica()

    def mudar(la):
        _camada(la, 1)['geometria']['caixa'] = [0, 0, 11, 10]
        _camada(la, 4)['tipo'] = 'outro'
        _camada(la, 6)['aparencia']['visivel_efetiva'] = True
        _camada(la, 2)['texto']['conteudo'] = 'Texto sintético mudado'

    r = comparar.comparar_arquivo(mapeamento.normalizar(s), _agora(s, mudar))
    campos = {(d['layer_id'], d['campo']): d for d in r['diferencas']}
    assert set(campos) == {(1, 'caixa'), (4, 'tipo'), (6, 'visivel'), (2, 'texto')}
    assert all(d['causa'] == 'sem_causa' for d in campos.values())
    assert r['por_causa'] == {'sem_causa': 4}
    texto = campos[(2, 'texto')]
    assert set(texto['base']) == {'sha256', 'tamanho'} and 'sintético' not in json.dumps(texto, ensure_ascii=False)
    assert not r['piorou']


def test_mudanca_de_versao_explica_o_que_nao_tem_outra_causa():
    s = _sonda_basica()

    def mudar(la):
        la['origem']['psd_tools'] = '1.27.0'
        _camada(la, 1)['geometria']['caixa'] = [0, 0, 11, 10]

    r = comparar.comparar_arquivo(mapeamento.normalizar(s), _agora(s, mudar))
    assert [d['causa'] for d in r['diferencas']] == ['mudanca_de_versao']


def test_camada_que_sumiu_ou_apareceu():
    s = _sonda_basica()

    def mudar(la):
        la['camadas'] = [c for c in la['camadas'] if c['identidade']['layer_id'] != 5]
        extra = copy.deepcopy(la['camadas'][0])
        extra['identidade']['layer_id'] = 99
        la['camadas'].append(extra)

    r = comparar.comparar_arquivo(mapeamento.normalizar(s), _agora(s, mudar))
    assert {(d['layer_id'], d['campo'], d['base'], d['agora']) for d in r['diferencas']} == {
        (5, 'existencia', True, False), (99, 'existencia', False, True)}


@pytest.mark.parametrize('base_pct, base_feita, agora_pct, agora_feita, esperado, piorou', [
    (0.5, True, 0.5, True, 'igual', False),
    (0.5, True, 0.4, True, 'melhorou', False),
    (0.5, True, 0.6, True, 'piorou', True),
    (0.5, True, None, False, 'piorou', True),
    (None, False, 0.2, True, 'melhorou', False),
    (None, False, None, False, 'sem_medida', False),
])
def test_prova_de_pixel_nao_pode_piorar(base_pct, base_feita, agora_pct, agora_feita, esperado, piorou):
    s = _sonda_basica(pct=base_pct, feita=base_feita)

    def mudar(la):
        la['prova_pixel']['feita'] = agora_feita
        la['prova_pixel']['pct_px_acima_qualquer_canal'] = agora_pct

    r = comparar.comparar_arquivo(mapeamento.normalizar(s), _agora(s, mudar))
    assert r['prova_pixel']['resultado'] == esperado and r['piorou'] is piorou


def test_execucao_que_falha_agora_piora():
    s = _sonda_basica()
    agora = mapeamento.normalizado_sem_laudo({'situacao': 'sem_laudo', 'motivo': 'x'})
    r = comparar.comparar_arquivo(mapeamento.normalizar(s), agora)
    assert r['execucao']['resultado'] == 'piorou' and r['piorou'] and r['diferencas'] == []
    r = comparar.comparar_arquivo(mapeamento.normalizar(_sonda_basica(status='timeout')),
                                  mapeamento.normalizar(laudo1_equivalente(s), {'situacao': 'ok'}))
    assert r['execucao']['resultado'] == 'melhorou' and not r['piorou']


# ------------------------------------------------------------------ corpus, agenda e relatorio
def _corpus(tmp_path, nomes):
    raiz = tmp_path / 'corpus'
    for rel in nomes:
        p = raiz / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(psd_minimo())
    (raiz / 'Marca X').mkdir(parents=True, exist_ok=True)
    (raiz / 'Marca X' / 'nao-e-psd.psd').write_bytes(b'PK\x03\x04nada')
    (raiz / 'Marca X' / 'leia.txt').write_text('x', encoding='utf-8')
    return raiz


def test_slug_igual_ao_do_agendador_da_sonda(tmp_path):
    raiz = _corpus(tmp_path, ['Marca Ção/Sub/Peça 1920x1080.psd', 'Marca Ção/Outra/Peça 1920x1080.psd',
                              'solto.psb'])
    itens = executar.listar_corpus(raiz)
    por_rel = {i.relativo.replace(os.sep, '/'): i.slug for i in itens}
    assert len(itens) == 3
    assert por_rel['solto.psb'] == 'raiz--solto'
    # o primeiro na ordem do os.walk fica com o slug simples; o repetido ganha o sufixo do sha1 do caminho
    assert por_rel['Marca Ção/Outra/Peça 1920x1080.psd'] == 'marca-cao--peca-1920x1080'
    repetido = por_rel['Marca Ção/Sub/Peça 1920x1080.psd']
    assert repetido.startswith('marca-cao--peca-1920x1080-') and len(repetido) == len('marca-cao--peca-1920x1080') + 7


def _fake_rodar(base_dir, mudar=None, registro=None):
    """Executor falso: grava em <pasta>/laudo.json o laudo/1 equivalente a linha de base do slug."""

    def rodar(item, pasta):
        if registro is not None:
            registro.append(('inicio', item.slug, time.monotonic(), threading.get_ident()))
        pasta.mkdir(parents=True, exist_ok=True)
        la = laudo1_equivalente(ler_json(base_dir / item.slug / 'laudo.json'))
        if mudar:
            mudar(item, la)
        contratos.validar(la, 'laudo/1')
        gravar_json_atomico(pasta / 'laudo.json', la)
        time.sleep(0.05)
        if registro is not None:
            registro.append(('fim', item.slug, time.monotonic(), threading.get_ident()))
        return {'execucao': {'situacao': 'ok', 'motivo': None, 'tempo_s': 0.1, 'codigo': 0}, 'laudo': la}

    return rodar


def _base(tmp_path, itens):
    base = tmp_path / 'base'
    for i in itens:
        gravar_json_atomico(base / i.slug / 'laudo.json', _sonda_basica())
    gravar_json_atomico(base / 'so-na-base' / 'laudo.json', _sonda_basica())
    return base


def test_regressao_completa_com_executor_falso(tmp_path):
    raiz = _corpus(tmp_path, ['Marca A/kv.psd', 'Marca A/banner.psd', 'Marca B/painel.psb'])
    itens = executar.listar_corpus(raiz)
    base = _base(tmp_path, itens)

    def mudar(item, la):
        if item.slug == itens[0].slug:
            la['prova_pixel']['pct_px_acima_qualquer_canal'] = 0.9

    rel, cj, cm = regressao.executar_regressao(raiz, base, tmp_path / 'saida', paralelo=2,
                                                rodar=_fake_rodar(base, mudar))
    contratos.ler(cj, 'regressao/1')
    assert rel['resultado'] == 'piorou' and rel['totais']['pioras_prova_pixel'] == 1
    assert rel['totais']['comparados'] == 3 and rel['totais']['so_na_base'] == 1
    assert rel['arquivos']['so-na-base'] == {'situacao': 'so_na_base'}
    resumo = cm.read_text(encoding='utf-8')
    assert 'PIOROU' in resumo and chr(0x2014) not in resumo and chr(0x2013) not in resumo
    assert 'sintético' not in resumo and 'sintético' not in cj.read_text(encoding='utf-8')


def test_grandes_rodam_um_de_cada_vez(tmp_path, monkeypatch):
    raiz = _corpus(tmp_path, ['M/a.psd', 'M/b.psd', 'M/c.psd', 'M/d.psd'])
    # o arquivo "d" fica grande para a agenda: limiar abaixo do tamanho dele
    grande = raiz / 'M' / 'd.psd'
    grande.write_bytes(psd_minimo(4, 4))
    itens = executar.listar_corpus(raiz)
    base = _base(tmp_path, itens)
    real = executar.limites.valor
    limiar = (raiz / 'M' / 'a.psd').stat().st_size
    monkeypatch.setattr(executar.limites, 'valor',
                        lambda i: limiar if i == 'regressao.arquivo_grande_bytes' else real(i))
    registro = []
    executar.rodar_todos(itens, tmp_path / 'saida', paralelo=3, rodar=_fake_rodar(base, registro=registro))
    eventos = {(e[0], e[1]): e[2] for e in registro}
    slug_grande = next(i.slug for i in itens if i.caminho == grande)
    pequenos = [i.slug for i in itens if i.caminho != grande]
    assert all(eventos[('fim', s)] <= eventos[('inicio', slug_grande)] for s in pequenos)


def test_sem_rodar_compara_o_que_esta_na_saida(tmp_path):
    raiz = _corpus(tmp_path, ['Marca A/kv.psd'])
    itens = executar.listar_corpus(raiz)
    base = _base(tmp_path, itens)
    saida = tmp_path / 'saida'
    gravar_json_atomico(saida / itens[0].slug / 'laudo.json', laudo1_equivalente(_sonda_basica()))
    rel, _, _ = regressao.executar_regressao(raiz, base, saida, sem_rodar=True)
    # o unico problema e o arquivo que so existe na linha de base, e ele conta como piora
    tot = rel['totais']
    assert tot['diferencas_camadas'] == 0 and tot['arquivos_que_pioraram'] == 0 and tot['so_na_base'] == 1
    assert rel['resultado'] == 'piorou'


def test_cli_regressao_gera_relatorio_e_envelope(tmp_path, capsys, monkeypatch):
    from desdobra import cli
    raiz = _corpus(tmp_path, ['Marca A/kv.psd'])
    base = _base(tmp_path, executar.listar_corpus(raiz))
    saida = tmp_path / 'saida'
    monkeypatch.setattr(cli, 'COMPONENTES', (('desdobra.regressao', ('regressao',)),))
    codigo = cli.principal(['--envelope', 'regressao', '--corpus', str(raiz), '--linha-de-base', str(base),
                            '--saida', str(saida)])
    env = json.loads(capsys.readouterr().out)
    contratos.validar(env, 'envelope/1')
    assert env['comando'] == 'regressao' and env['modo_dados'] == 'c'
    assert codigo in (int(Codigo.OK), int(regressao.CODIGO_PIOROU))
    assert str(raiz) not in json.dumps(env) and 'Marca' not in json.dumps(env)
    relatorios = list(saida.glob('regressao-*.json'))
    assert len(relatorios) == 1
    contratos.ler(relatorios[0], 'regressao/1')


def test_cli_regressao_recusa_pasta_que_nao_existe(tmp_path):
    from desdobra.regressao import _executar

    class A:
        corpus = str(tmp_path / 'nao-existe')
        linha_de_base = str(tmp_path)
        saida = str(tmp_path / 's')
        paralelo = 1
        filtro = []
        sem_rodar = False

    r = _executar(A())
    assert r.codigo == Codigo.USO and r.situacao == 'erro'


@pytest.mark.skipif(not os.environ.get('DESDOBRA_LINHA_DE_BASE'),
                    reason='defina DESDOBRA_LINHA_DE_BASE com a pasta da linha de base para rodar')
def test_linha_de_base_real_contra_ela_mesma_da_zero_diferenca():
    pasta = Path(os.environ['DESDOBRA_LINHA_DE_BASE'])
    slugs = regressao.slugs_da_base(pasta)
    assert slugs
    for slug in slugs:
        b1 = regressao.ler_base(pasta, slug)
        b2 = regressao.ler_base(pasta, slug)
        r = comparar.comparar_arquivo(b1, b2)
        assert r['diferencas'] == [] and not r['piorou'], slug


# ------------------------------------------------------------------ verificacoes de seguranca
def test_varredura_da_saida_padrao_acha_nome_e_caminho(tmp_path):
    item = executar.Item(caminho=tmp_path / 'pasta-sintetica' / 'peca-sintetica.psd',
                         relativo='pasta-sintetica/peca-sintetica.psd', bytes=10, slug='s')
    laudo = {'camadas': [{'nome': 'Camada Sintética Longa', 'texto': {'conteudo': 'Linha um\nLinha dois', 'runs': []}},
                         {'nome': 'ok', 'texto': None}]}
    termos = executar.termos_do_laudo(laudo, item)
    assert 'Linha dois' in termos and 'peca-sintetica.psd' in termos
    limpo = executar.varrer_saida('{"esquema":"envelope/1","situacao":"ok"}', termos)
    # "ok" e termo curto: fora do texto livre (o valor de situacao) nao e procurado
    assert limpo['achados'] == 0 and not limpo['tem_conteudo'] and limpo['termos_curtos_presentes'] == 0
    sujo = executar.varrer_saida(json.dumps({'o_que_fazer': 'Camada Sintética Longa em %s' % item.caminho}), termos)
    assert sujo['achados'] >= 2
    # chave do envelope igual a nome de camada nao e vazamento; o mesmo texto num valor e
    termos_chave = executar.termos_do_laudo({'camadas': [{'nome': 'codigo'}]}, item)
    assert executar.varrer_saida('{"codigo": 0}', termos_chave)['achados'] == 0
    assert executar.varrer_saida('{"fase": "codigo"}', termos_chave)['achados'] == 1
    assert executar.varrer_saida('{"conteudo": {}}', termos_chave)['tem_conteudo']


def test_auditoria_e_linkado_usado_contam_como_falha(tmp_path):
    (tmp_path / 'bruto' / 'aa').mkdir(parents=True)
    (tmp_path / 'bruto' / 'aa' / 'estrutura.json').write_text(
        json.dumps({'auditoria': {'instalado': True, 'bloqueios': [{'evento': 'open'}]}}), encoding='utf-8')
    laudo = {'recusas': [], 'camadas': [{'tipo': 'smart_linkado', 'smart_object': {'casamento': {'usado': True}}}]}
    aud = executar.auditoria_dos_filhos(tmp_path, laudo)
    assert aud == {'filhos_com_estrutura': 1, 'gancho_instalado': 1, 'bloqueios': 1, 'recusas_auditoria': 0,
                   'linkados': 1, 'linkados_usados': 1}
    verif = comparar.totais_verificacoes({'s': {'verificacoes': {'saida_padrao': {'achados': 0}, 'auditoria': aud}}})
    assert comparar.falhas_de_seguranca(verif) == 2


def test_causas_especificas_pedem_o_fato_medido():
    base = {'regras': ['B3', 'D6']}
    assert comparar.causa_da_situacao(base, {'regras': [], 'evidencias': ['fonte_nao_conferida_com_tinta',
                                                                           'malha_identidade']})[0] \
        == 'b3_fontes_conferidas_no_m2'
    assert comparar.causa_da_situacao({'regras': ['B3']}, {'regras': [], 'evidencias': []})[0] == 'regra_do_laudo'
    assert comparar.causa_da_situacao({'regras': ['D6']}, {'regras': [], 'evidencias': ['malha_identidade']})[0] \
        == 'd6_falso_positivo_medido'
    # sem o fato medido, a causa fica generica
    assert comparar.causa_da_situacao({'regras': ['D6']}, {'regras': [], 'evidencias': []})[0] == 'regra_do_laudo'
    assert comparar.causa_da_situacao({'regras': ['D9', 'D6']}, {'regras': [], 'evidencias': ['malha_identidade']})[0] \
        == 'd9_aposentada'
    camada = {'texto': {'conteudo': 'x', 'runs': []},
              'smart_object': {'medidas': {'malha_custom': True, 'malha_desvio_max_px': 1e-12}}}
    # sem o alerta fonte_nao_conferida na propria camada, a perda da B3 nao fica explicada
    assert mapeamento.evidencias_do_laudo(camada, False) == ['malha_identidade']
    camada['alertas'] = [{'codigo': 'fonte_nao_conferida', 'descricao': 'x'}]
    assert mapeamento.evidencias_do_laudo(camada, False) == ['fonte_nao_conferida_com_tinta', 'malha_identidade']
    assert mapeamento.evidencias_do_laudo(camada, True) == ['malha_identidade']


# ------------------------------------------------------------------ o que conta como piora
def _rodada_limpa(tmp_path, nomes=('Marca A/kv.psd',)):
    import shutil
    raiz = _corpus(tmp_path, list(nomes))
    itens = executar.listar_corpus(raiz)
    base = _base(tmp_path, itens)
    shutil.rmtree(base / 'so-na-base')
    return raiz, itens, base


def _sem_job(item, pasta):
    return {'achados': 0, 'tem_conteudo': False, 'termos': 1, 'falhou': False}


def test_rodada_limpa_nada_piora(tmp_path):
    raiz, _itens, base = _rodada_limpa(tmp_path)
    rel, _, _ = regressao.executar_regressao(raiz, base, tmp_path / 's', rodar=_fake_rodar(base),
                                             verificar_job=_sem_job)
    assert rel['resultado'] == 'nada_piorou'
    assert rel['totais']['verificacoes']['job_modo_c_verificados'] == 1


@pytest.mark.parametrize('verificacoes, job', [
    ({'saida_padrao': {'achados': 1}, 'auditoria': {}}, None),
    ({'saida_padrao': {'achados': 0}, 'auditoria': {'bloqueios': 1}}, None),
    ({'saida_padrao': {'achados': 0}, 'auditoria': {'linkados_usados': 1}}, None),
    (None, {'achados': 1, 'tem_conteudo': False, 'falhou': False}),
])
def test_falha_de_seguranca_faz_a_regressao_piorar(tmp_path, monkeypatch, verificacoes, job):
    from desdobra import cli
    raiz, _itens, base = _rodada_limpa(tmp_path)
    fake = _fake_rodar(base)

    def rodar(item, pasta):
        r = fake(item, pasta)
        if verificacoes is not None:
            r['verificacoes'] = verificacoes
        return r
    monkeypatch.setattr(executar, 'rodar_ler', rodar)
    monkeypatch.setattr(executar, 'verificar_job_modo_c', lambda item, pasta: job or _sem_job(item, pasta))
    codigo = cli.principal(['regressao', '--corpus', str(raiz), '--linha-de-base', str(base),
                            '--saida', str(tmp_path / 's')])
    assert codigo == int(regressao.CODIGO_PIOROU) == int(Codigo.REGRESSAO_PIOROU)
    rel = ler_json(next((tmp_path / 's').glob('regressao-*.json')))
    assert rel['resultado'] == 'piorou' and rel['totais']['arquivos_que_pioraram'] == 0
    assert rel['totais']['falhas_de_seguranca'] >= 1


def test_arquivo_sem_linha_de_base_piora(tmp_path):
    raiz, itens, base = _rodada_limpa(tmp_path, ('Marca A/kv.psd', 'Marca A/novo.psd'))
    import shutil
    shutil.rmtree(base / itens[1].slug)
    rel, _, _ = regressao.executar_regressao(raiz, base, tmp_path / 's', rodar=_fake_rodar(base_dir_de(base, itens)),
                                             verificar_job=_sem_job)
    assert rel['totais']['sem_base'] == 1 and rel['resultado'] == 'piorou'


def base_dir_de(base, itens):
    # o executor falso le a sonda do slug; para o arquivo sem base, usa a do primeiro
    import shutil
    copia = base.parent / 'base-do-executor'
    if not copia.exists():
        shutil.copytree(base, copia)
        for i in itens:
            if not (copia / i.slug).exists():
                shutil.copytree(copia / itens[0].slug, copia / i.slug)
    return copia


def test_camada_que_fica_mais_grave_sem_causa_especifica_piora():
    s = _sonda_basica()

    def mudar(la):
        c = _camada(la, 6)
        c['situacao'] = 'bloqueante'
        c['motivos'] = [{'regra': 'B2', 'descricao': 'erro', 'medida': None, 'limite': None,
                         'fonte': {'arquivo': 'pesquisa/v1-estatico-sintese.md'}}]
    r = comparar.comparar_arquivo(mapeamento.normalizar(s), _agora(s, mudar))
    assert r['camadas_mais_graves'] == 1 and r['piorou']
    # ficar menos grave por causa registrada nao piora
    s2 = _sonda_basica()
    r = comparar.comparar_arquivo(mapeamento.normalizar(s2), _agora(s2, lambda la: None))
    assert r['camadas_mais_graves'] == 0 and not r['piorou']


@pytest.mark.parametrize('base, agora, esperado', [
    ({'feita': True, 'pct': 0.0063}, {'feita': True, 'pct': 0.00634, 'px_acima': 7, 'px_total': 100000}, 'igual'),
    ({'feita': True, 'pct': 0.0063}, {'feita': True, 'pct': 0.0064, 'px_acima': 7, 'px_total': 100000}, 'piorou'),
    ({'feita': True, 'pct': 0.01, 'px_acima': 100, 'px_total': 1000000},
     {'feita': True, 'pct': 0.01, 'px_acima': 101, 'px_total': 1000000}, 'piorou'),
    ({'feita': True, 'pct': 0.01, 'px_acima': 100, 'px_total': 1000000},
     {'feita': True, 'pct': 0.01, 'px_acima': 99, 'px_total': 1000000}, 'melhorou'),
])
def test_prova_de_pixel_na_resolucao_de_cada_lado(base, agora, esperado):
    assert comparar.comparar_prova_pixel({'prova_pixel': base}, {'prova_pixel': agora})['resultado'] == esperado


def test_termo_curto_que_vaza_no_texto_livre_e_achado():
    vocab = frozenset({'de', 'confira', 'a', 'camada', 'novo'})
    saida = json.dumps({'o_que_fazer': 'Confira a camada ZQ de novo', 'ids': {'arquivo_sha256': 'ab' * 32}})
    r = executar.varrer_saida(saida, {'ZQ', 'de', 'ab'}, vocab)
    assert r['achados'] == 1 and r['termos_curtos_presentes'] == 2 and r['termos_curtos_vocabulario'] == 1
    assert executar.varrer_saida(json.dumps({'ids': {'x': 'ab' * 32}}), {'ab'}, vocab)['achados'] == 0
    assert 'de' in executar.vocabulario_do_motor()


def test_resumo_mostra_o_tempo_de_relogio_das_duas_rodadas(tmp_path):
    raiz, _itens, base = _rodada_limpa(tmp_path)
    gravar_json_atomico(base / 'execucao.json', {'duracao_s': 183.1, 'paralelo_max': 3})
    rel, cj, cm = regressao.executar_regressao(raiz, base, tmp_path / 's', paralelo=2, rodar=_fake_rodar(base),
                                               verificar_job=_sem_job)
    assert rel['base_execucao'] == {'duracao_s': 183.1, 'paralelo': 3}
    resumo = cm.read_text(encoding='utf-8')
    assert 'Tempo de relógio: agora %s s com paralelo 2; linha de base 183.1 s com paralelo 3.' % rel['duracao_s'] in resumo


# ------------------------------------------------------------------ caminhos relativos, camada sumida e job no modo c
def test_regressao_com_caminhos_relativos_passa_caminhos_absolutos_adiante(tmp_path, monkeypatch):
    raiz, _itens, base = _rodada_limpa(tmp_path)
    monkeypatch.chdir(tmp_path)
    vistos = []
    fake = _fake_rodar(base)

    def rodar(item, pasta):
        vistos.append((item.caminho, pasta))
        return fake(item, pasta)

    rel, cj, _ = regressao.executar_regressao(raiz.name, base.name, 's', rodar=rodar, verificar_job=_sem_job)
    assert vistos and all(Path(c).is_absolute() and Path(p).is_absolute() for c, p in vistos)
    assert rel['resultado'] == 'nada_piorou' and cj.is_absolute()


def test_rodar_ler_com_caminho_relativo_chama_o_ler_com_caminhos_absolutos(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    raiz = _corpus(tmp_path, ['Marca A/kv.psd'])
    item = executar.listar_corpus(raiz.name)[0]
    assert not Path(item.caminho).is_absolute()
    chamadas = []

    class Proc:
        returncode = 2
        stdout = b''
        stderr = b''

    def run(comando, **kw):
        chamadas.append((comando, kw.get('cwd')))
        return Proc()

    monkeypatch.setattr(executar.subprocess, 'run', run)
    executar.rodar_ler(item, Path('s') / item.slug)
    comando, cwd = chamadas[0]
    arquivo = comando[comando.index('ler') + 1]
    saida = comando[comando.index('--saida') + 1]
    assert Path(arquivo).is_absolute() and Path(arquivo).is_file()
    assert Path(saida).is_absolute() and Path(saida) == (tmp_path / 's' / item.slug).resolve()


@pytest.mark.parametrize('versao_agora', [None, '1.27.0'])
def test_camada_que_some_conta_como_piora_com_ou_sem_mudanca_de_versao(versao_agora):
    s = _sonda_basica()

    def mudar(la):
        la['camadas'] = [c for c in la['camadas'] if c['identidade']['layer_id'] != 5]
        if versao_agora:
            la['origem']['psd_tools'] = versao_agora

    r = comparar.comparar_arquivo(mapeamento.normalizar(s), _agora(s, mudar))
    assert [d['campo'] for d in r['diferencas']] == ['existencia']
    assert r['camadas_mais_graves'] == 1 and r['piorou']


def test_camada_que_aparece_agora_nao_e_piora():
    s = _sonda_basica()

    def mudar(la):
        extra = copy.deepcopy(la['camadas'][0])
        extra['identidade']['layer_id'] = 99
        la['camadas'].append(extra)

    r = comparar.comparar_arquivo(mapeamento.normalizar(s), _agora(s, mudar))
    assert r['camadas_mais_graves'] == 0 and not r['piorou']


@pytest.mark.parametrize('job', [
    {'achados': 0, 'tem_conteudo': False, 'falhou': True, 'codigo_criar': 1, 'codigo_proxima': None},
    {'achados': 0, 'tem_conteudo': False, 'falhou': True, 'codigo_criar': 0, 'codigo_proxima': 3},
])
def test_falha_do_job_no_modo_c_conta_como_falha_de_seguranca(tmp_path, job):
    verif = comparar.totais_verificacoes({'a': {'verificacoes': {'job_modo_c': job}}})
    assert comparar.falhas_de_seguranca(verif) >= 1
    raiz, _itens, base = _rodada_limpa(tmp_path)
    rel, _, _ = regressao.executar_regressao(raiz, base, tmp_path / 's', rodar=_fake_rodar(base),
                                             verificar_job=lambda item, pasta: dict(job))
    assert rel['totais']['falhas_de_seguranca'] >= 1 and rel['resultado'] == 'piorou'


def test_job_no_modo_c_que_nao_roda_porque_nada_leu_ok_conta_como_falha(tmp_path):
    raiz = _corpus(tmp_path, ['Marca A/kv.psd'])
    itens = executar.listar_corpus(raiz)
    base = tmp_path / 'base'
    for i in itens:
        gravar_json_atomico(base / i.slug / 'laudo.json', _sonda_basica(status='timeout', feita=False, pct=None))
    chamadas = []

    def rodar(item, pasta):
        pasta.mkdir(parents=True, exist_ok=True)
        return {'execucao': {'situacao': 'recusado', 'motivo': 'x', 'tempo_s': 0.1, 'codigo': 3}, 'laudo': None}

    rel, _, _ = regressao.executar_regressao(raiz, base, tmp_path / 's', rodar=rodar,
                                             verificar_job=lambda item, pasta: chamadas.append(item))
    assert chamadas == []
    assert rel['totais']['arquivos_que_pioraram'] == 0
    assert rel['totais']['verificacoes']['job_modo_c_nao_rodou'] == 1
    assert rel['totais']['falhas_de_seguranca'] >= 1 and rel['resultado'] == 'piorou'


def test_cli_regressao_recusa_saida_dentro_do_repositorio_do_plugin(tmp_path, monkeypatch):
    from desdobra import PASTA_PLUGIN
    from desdobra.regressao import _executar

    def nao_devia_rodar(*a, **kw):
        raise AssertionError('a regressao nao devia rodar com a saida dentro do repositorio')

    monkeypatch.setattr(regressao, 'executar_regressao', nao_devia_rodar)
    (tmp_path / 'corpus').mkdir()

    class A:
        corpus = str(tmp_path / 'corpus')
        linha_de_base = str(tmp_path)
        saida = str(PASTA_PLUGIN / 'saida-de-teste-que-nao-pode-existir')
        paralelo = 1
        filtro = []
        sem_rodar = False

    r = _executar(A())
    assert r.codigo == Codigo.USO and r.situacao == 'erro' and 'reposit' in r.o_que_fazer
    assert not Path(A.saida).exists()
    A.saida = os.path.relpath(PASTA_PLUGIN / 'motor' / 'outra-saida')
    r = _executar(A())
    assert r.codigo == Codigo.USO


# ------------------------------------------------------------------ correcoes da revisao do M2
def test_textos_da_regressao_e_da_cor_atualizados():
    from desdobra import cor
    from desdobra.regressao import comparar
    texto = comparar.CAUSAS['b3_fontes_conferidas_no_m2']['descricao']
    assert 'No M1' not in texto and 'segunda passada' in texto
    assert 'smart object' in cor.__doc__ and 'revista em 31/10' in cor.__doc__
