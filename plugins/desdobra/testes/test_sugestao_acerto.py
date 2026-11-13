# -*- coding: utf-8 -*-
"""M7c, S5: a metrica de acerto da sugestao de funcao (desdobra.sugestao.acerto e "desdobra sugestao acerto").

  - a sugestao passa pela heranca do motor (desdobra.briefing.modelo.resolver) antes da contagem por camada, igual a
    funcao confirmada pelo DA;
  - duas contagens por modo: funcao resolvida por camada e decisao por grupo (desdobra.tela.funcoes.decisoes_minimas),
    mais o acerto da alternativa e a cobertura (camadas com sugestao sobre o total);
  - com --gabarito, a comparacao e contra um gabarito fora do repositorio, pela tabela inteira de equivalencia das
    funcoes da ficha para os ids do esquema; funcao sem par fica de fora, sem acerto nem erro; do gabarito so valem
    layer_id e funcao, e o KV e escolhido pelo sha256 do PSD do job;
  - ao salvar o briefing, a metrica vai para medicoes/sugestao.json (fora do briefing), e a falha ao gravar nunca
    interrompe o salvar;
  - nenhuma meta reprova; no modo c a metrica registra "sem sugestao".

Tudo sintetico: laudo, estado, sugestoes e gabarito inventados na hora; nenhum PSD ou fonte e aberto. O gabarito real
nao e lido nem citado aqui.
"""
import io
import json
from contextlib import redirect_stdout

import pytest

import test_sugestao_importar as tsi
from conftest import RAIZ_PLUGIN, escolher_modo_do_da
from desdobra import cli, contratos, humano
from desdobra.sugestao import acerto
from desdobra.sugestao import importar as si
from test_sugestao_apoio import camada, laudo

NOME_GRUPO = 'Grupo Ficticio Turquesa'
TEXTO = 'Texto Ficticio Ambar'
# marcadores das chaves pessoais do gabarito: nenhum pode sair do comparador
MARCAS = {'respondente': 'Respondente Ficticio Ocre', 'arquivo': 'pasta-ficticia/Arquivo Ficticio Ocre.psd',
          'chave': 'chave-ficticia-ocre', 'nome': 'Nome Ficticio Ocre', 'obs': 'Observacao Ficticia Ocre',
          'ficha': 'ficha-ficticia-ocre', 'revisao': 'revisao-ficticia-ocre', 'salvo_em': 'quando-ficticio-ocre'}


# ------------------------------------------------------------------ laudo e referencia sinteticos
def _laudo_grupo():
    """Grupo 10 com as camadas 11, 12 e 15; 13 e 14 soltas."""
    return laudo([camada(10, NOME_GRUPO, tipo='grupo'),
                  camada(11, 'Fundo Ficticio', pai_id=10),
                  camada(12, 'Titulo Ficticio', tipo='texto', texto=TEXTO, pai_id=10),
                  camada(15, 'Textura Ficticia', pai_id=10),
                  camada(13, 'Logo Ficticio'),
                  camada(14, 'Botao Ficticio')])


REF = {11: 'fundo', 12: 'titulo', 15: 'fundo', 13: 'logo_principal', 14: 'cta'}
# o grupo leva fundo (11 e 15 herdam), 12 tem a propria, 13 certa, 14 errada com a alternativa certa
SUGESTOES = [{'layer_id': 10, 'funcao': 'fundo', 'alternativa': 'grafismo'},
             {'layer_id': 12, 'funcao': 'titulo', 'alternativa': 'texto_de_apoio'},
             {'layer_id': 13, 'funcao': 'logo_principal', 'alternativa': 'selo'},
             {'layer_id': 14, 'funcao': 'selo', 'alternativa': 'cta'}]


# ------------------------------------------------------------------ esquema e tabela
def test_tabela_de_equivalencia_inteira_e_so_com_ids_do_esquema():
    enum = contratos.carregar_esquema('briefing/1')['$defs']['funcao']['enum']
    # a ficha de rotulagem: as funcoes, escritas uma a uma, e o "nao sei"
    esperado = {'fundo': 'fundo', 'imagem': 'imagem', 'sujeito': 'sujeito', 'veu-legibilidade': 'veu_de_legibilidade',
                'grafismo': 'grafismo', 'titulo': 'titulo', 'texto-apoio': 'texto_de_apoio', 'cta': 'cta',
                'icone-cta': 'icone_de_cta', 'url-contato': 'url_ou_contato', 'texto-legal': 'texto_legal',
                'info-evento': 'informacao_de_evento', 'destaque-numerico': 'destaque_numerico',
                'logo-principal': 'logo_principal', 'assinatura-institucional': 'assinatura_institucional',
                'selo': 'selo', 'logo-parceiro': 'logo_de_parceiro', 'estrutura': 'estrutura',
                'fora-da-peca': 'fora_da_peca', 'indeterminado': 'indeterminado', 'nao-sei': None}
    assert acerto.FUNCOES_DO_GABARITO == esperado
    assert all(v in enum for v in esperado.values() if v is not None)
    assert acerto.traduzir('info-evento') == 'informacao_de_evento'
    assert acerto.traduzir('logo-parceiro') == 'logo_de_parceiro'
    for sem_par in ('nao-sei', '', None, 'funcao-inventada', 7):
        assert acerto.traduzir(sem_par) is None


def test_esquema_da_medicao():
    esq = contratos.carregar_esquema(acerto.ESQUEMA)
    assert esq['additionalProperties'] is False
    camada_med = esq['$defs']['camada']
    assert set(camada_med['properties']) == {'layer_id', 'funcao', 'sugestao', 'alternativa'}
    assert camada_med['additionalProperties'] is False
    assert esq['$defs']['funcao']['enum'] == contratos.carregar_esquema('briefing/1')['$defs']['funcao']['enum']


# ------------------------------------------------------------------ a conta
def test_conta_exata_por_camada_por_decisao_alternativa_e_cobertura():
    m = acerto.comparar_gabarito(_laudo_grupo(), REF, SUGESTOES)
    # por camada, pela heranca do motor: 11 e 15 herdam fundo do grupo; 14 erra
    assert m['por_camada'] == {'certas': 4, 'total': 5, 'acerto': 0.8}
    # decisoes minimas da referencia: grupo 10 fundo, 12 titulo, 13 logo, 14 cta; 3 de 4 certas
    assert m['por_decisao'] == {'certas': 3, 'total': 4, 'acerto': 0.75}
    assert m['alternativa'] == {'certas': 1, 'total': 5, 'acerto': 0.2}
    assert m['cobertura'] == {'com_sugestao': 5, 'total': 5, 'cobertura': 1.0}
    assert m['camadas'] == [
        {'layer_id': 11, 'funcao': 'fundo', 'sugestao': 'fundo', 'alternativa': 'grafismo'},
        {'layer_id': 12, 'funcao': 'titulo', 'sugestao': 'titulo', 'alternativa': 'texto_de_apoio'},
        {'layer_id': 13, 'funcao': 'logo_principal', 'sugestao': 'logo_principal', 'alternativa': 'selo'},
        {'layer_id': 14, 'funcao': 'cta', 'sugestao': 'selo', 'alternativa': 'cta'},
        {'layer_id': 15, 'funcao': 'fundo', 'sugestao': 'fundo', 'alternativa': 'grafismo'}]


def test_tres_de_quatro_por_camada_sem_sugestao_numa():
    la = laudo([camada(21, 'A'), camada(22, 'B'), camada(23, 'C'), camada(24, 'D')])
    ref = {21: 'fundo', 22: 'titulo', 23: 'cta', 24: 'selo'}
    sug = [{'layer_id': 21, 'funcao': 'fundo', 'alternativa': 'imagem'},
           {'layer_id': 22, 'funcao': 'titulo', 'alternativa': 'cta'},
           {'layer_id': 23, 'funcao': 'cta', 'alternativa': 'selo'}]
    m = acerto.comparar_gabarito(la, ref, sug)
    assert m['por_camada'] == {'certas': 3, 'total': 4, 'acerto': 0.75}
    assert m['cobertura'] == {'com_sugestao': 3, 'total': 4, 'cobertura': 0.75}
    assert m['alternativa']['certas'] == 0
    assert m['camadas'][-1] == {'layer_id': 24, 'funcao': 'selo', 'sugestao': None, 'alternativa': None}


def test_camada_coberta_nao_herda_a_sugestao_do_grupo():
    cob = {'coberta': True, 'sugestao_da_regra': {'funcao': 'fundo'}}
    la = laudo([camada(30, NOME_GRUPO, tipo='grupo'), camada(31, 'A', pai_id=30),
                camada(32, 'B', pai_id=30, coberta=cob)])
    m = acerto.comparar_gabarito(la, {31: 'grafismo', 32: 'grafismo'},
                                 [{'layer_id': 30, 'funcao': 'grafismo', 'alternativa': 'fundo'}])
    # como no motor, a coberta so recebe funcao propria
    assert m['por_camada'] == {'certas': 1, 'total': 2, 'acerto': 0.5}
    assert m['cobertura']['com_sugestao'] == 1


def test_nenhuma_meta_reprova_e_sem_referencia_o_acerto_fica_nulo():
    m = acerto.comparar_gabarito(_laudo_grupo(), REF, [{'layer_id': 10, 'funcao': 'cta', 'alternativa': 'selo'}])
    assert m['por_camada']['certas'] == 0 and m['por_camada']['acerto'] == 0.0
    vazio = acerto.comparar_gabarito(_laudo_grupo(), {}, SUGESTOES)
    assert vazio['por_camada'] == {'certas': 0, 'total': 0, 'acerto': None}
    assert vazio['por_decisao']['acerto'] is None and vazio['cobertura']['cobertura'] is None


# ------------------------------------------------------------------ job sintetico (modo, sugestoes validadas)
def _job_com_sugestoes(tmp_path, modo='a', itens=None):
    job = tsi._job(tmp_path, modo=modo)
    tsi._escrever(job, tsi._sugestoes(job, itens or tsi.VALIDAS))
    assert si.importar(job)['gravou']
    return job


def _laudo_do_job(job):
    return contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')


# referencia do job de tsi: grupo 10 (11 e 12 dentro) e 13 solta
REF_JOB = {11: 'grafismo', 12: 'titulo', 13: 'selo'}


def test_medir_no_modo_a_conta_e_registra_so_ids_e_funcoes(tmp_path):
    job = _job_com_sugestoes(tmp_path, 'a')
    m = acerto.medir(job, _laudo_do_job(job), REF_JOB, referencia='briefing', quando='2026-11-13T10:00:00-03:00')
    assert m['situacao'] == 'medido' and m['modo'] == 'a' and m['referencia'] == 'briefing'
    # 11 herda grafismo do grupo (certa), 12 titulo (certa), 13 logo_principal (errada, alternativa selo certa)
    assert m['por_camada'] == {'certas': 2, 'total': 3, 'acerto': round(2 / 3, 3)}
    assert m['alternativa']['certas'] == 1
    assert m['sugestoes_ref'] is not None
    acerto.gravar(job, m)
    dados = contratos.ler(job / acerto.ARQUIVO, acerto.ESQUEMA)
    assert dados['briefing']['a']['por_camada']['certas'] == 2
    texto = (job / acerto.ARQUIVO).read_text(encoding='utf-8')
    assert tsi.OFERTA not in texto and tsi.NOME_GRUPO not in texto and 'Logo Ficticio' not in texto
    for c in dados['briefing']['a']['camadas']:
        assert set(c) == {'layer_id', 'funcao', 'sugestao', 'alternativa'}


def test_modo_c_registra_sem_sugestao(tmp_path):
    job = _job_com_sugestoes(tmp_path, 'a')
    escolher_modo_do_da(job, 'c')
    m = acerto.medir(job, _laudo_do_job(job), REF_JOB, referencia='briefing')
    assert m['situacao'] == 'sem_sugestao' and m['modo'] == 'c'
    assert m['por_camada'] is None and m['camadas'] == [] and m['sugestoes_ref'] is None
    acerto.gravar(job, m)
    assert contratos.ler(job / acerto.ARQUIVO, acerto.ESQUEMA)['briefing']['c']['situacao'] == 'sem_sugestao'
    # a agencia fechou o teto: tambem sem sugestao
    job2 = _job_com_sugestoes(tmp_path / 'outro', 'a')
    assert acerto.medir(job2, _laudo_do_job(job2), REF_JOB, referencia='briefing', teto='c')['situacao'] == \
        'sem_sugestao'


def test_cada_modo_guarda_a_propria_medicao(tmp_path):
    job = _job_com_sugestoes(tmp_path, 'a')
    acerto.gravar(job, acerto.medir(job, _laudo_do_job(job), REF_JOB, referencia='briefing'))
    escolher_modo_do_da(job, 'c')
    acerto.gravar(job, acerto.medir(job, _laudo_do_job(job), REF_JOB, referencia='briefing'))
    dados = contratos.ler(job / acerto.ARQUIVO, acerto.ESQUEMA)
    assert set(dados['briefing']) == {'a', 'c'} and dados['briefing']['a']['situacao'] == 'medido'


# ------------------------------------------------------------------ gabarito fora do repositorio
def _gabarito(tmp_path, kv_sha, respostas, outro_sha='cd' * 32, com_sha=True, nome='gabarito.json'):
    """Um gabarito sintetico na forma da ficha, com as chaves pessoais preenchidas por marcadores."""
    def resp(lid, funcao):
        return {'layer_id': lid, 'funcao': funcao, 'nome': MARCAS['nome'], 'obs': MARCAS['obs']}
    kvs = [{'chave': MARCAS['chave'], 'arquivo': MARCAS['arquivo'],
            'respostas': [resp(1, 'titulo'), resp(11, 'fundo'), resp(12, 'fundo'), resp(13, 'fundo')]},
           {'chave': MARCAS['chave'] + '-2', 'arquivo': MARCAS['arquivo'],
            'respostas': [resp(lid, f) for lid, f in respostas]}]
    if com_sha:
        kvs[0]['sha256'], kvs[1]['sha256'] = outro_sha, kv_sha
    dados = {'respondente': MARCAS['respondente'], 'ficha': MARCAS['ficha'], 'revisao': MARCAS['revisao'],
             'salvo_em': MARCAS['salvo_em'], 'kvs': kvs}
    pasta = tmp_path / 'fora-do-repo-marcador-de-caminho'
    pasta.mkdir(parents=True, exist_ok=True)
    arq = pasta / nome
    arq.write_text(json.dumps(dados, ensure_ascii=False), encoding='utf-8')
    return arq


RESPOSTAS = [(10, 'grafismo'), (11, 'grafismo'), (12, 'titulo'), (13, 'cta'), (99, 'cta'), (14, 'nao-sei')]


def test_referencia_do_gabarito_pelo_sha256_do_kv_e_so_layer_id_e_funcao(tmp_path):
    job = _job_com_sugestoes(tmp_path)
    la = _laudo_do_job(job)
    arq = _gabarito(tmp_path, la['origem']['sha256'], RESPOSTAS)
    dados = json.loads(arq.read_text(encoding='utf-8'))
    ref, info = acerto.referencia_do_gabarito(dados, la)
    # o KV do sha256 do job, nunca o outro; 99 nao esta no laudo; nao-sei fica sem par
    assert ref == {10: 'grafismo', 11: 'grafismo', 12: 'titulo', 13: 'cta'}
    assert info == {'sem_par': 1, 'fora_do_laudo': 1}
    texto = json.dumps([ref, info], ensure_ascii=False)
    assert not any(v in texto for v in MARCAS.values())


def test_resposta_repetida_da_camada_vale_a_ultima_mesmo_sem_par(tmp_path):
    job = _job_com_sugestoes(tmp_path)
    la = _laudo_do_job(job)
    sha = la['origem']['sha256']

    def ref_de(respostas):
        dados = {'kvs': [{'sha256': sha, 'respostas': [{'layer_id': i, 'funcao': f} for i, f in respostas]}]}
        return acerto.referencia_do_gabarito(dados, la)

    # cta trocado depois para nao-sei: a camada sai da referencia e conta uma vez so em sem_par
    assert ref_de([(13, 'cta'), (13, 'nao-sei'), (12, 'titulo')]) == ({12: 'titulo'},
                                                                     {'sem_par': 1, 'fora_do_laudo': 0})
    # o contrario: nao-sei trocado depois para cta vale cta e nao soma sem_par
    assert ref_de([(13, 'nao-sei'), (13, 'cta')]) == ({13: 'cta'}, {'sem_par': 0, 'fora_do_laudo': 0})
    # camada fora do laudo repetida conta uma vez
    assert ref_de([(99, 'cta'), (99, 'titulo')]) == ({}, {'sem_par': 0, 'fora_do_laudo': 1})
    # pela CLI: a camada 13 nao entra como erro
    g = tmp_path / 'g-repetido.json'
    g.write_text(json.dumps({'kvs': [{'sha256': sha, 'respostas': [
        {'layer_id': 13, 'funcao': 'cta'}, {'layer_id': 13, 'funcao': 'nao-sei'},
        {'layer_id': 12, 'funcao': 'titulo'}]}]}), encoding='utf-8')
    _codigo, env, _texto = _cli('--envelope', 'sugestao', 'acerto', '--job', str(job), '--gabarito', str(g))
    assert env['contagens']['total_camada'] == 1
    assert env['contagens']['sem_par'] == 1


def test_gabarito_sem_o_kv_do_job_ou_invalido_e_recusado(tmp_path):
    job = _job_com_sugestoes(tmp_path)
    la = _laudo_do_job(job)
    dados = json.loads(_gabarito(tmp_path, 'ef' * 32, RESPOSTAS).read_text(encoding='utf-8'))
    with pytest.raises(acerto.ErroGabarito) as e:
        acerto.referencia_do_gabarito(dados, la)
    assert e.value.codigo == 'kv_fora_do_gabarito'
    for ruim in ([], {'kvs': 'x'}, {'kvs': [{'respostas': 'x'}]}, {'kvs': [{'sha256': la['origem']['sha256'],
                                                                           'respostas': [{'layer_id': 'x'}]}]}):
        with pytest.raises(acerto.ErroGabarito) as e:
            acerto.referencia_do_gabarito(ruim, la)
        assert e.value.codigo == 'gabarito_invalido'
    # o mesmo sha256 em dois KVs do gabarito nao escolhe nenhum
    kv = {'sha256': la['origem']['sha256'], 'respostas': [{'layer_id': 11, 'funcao': 'fundo'}]}
    with pytest.raises(acerto.ErroGabarito) as e:
        acerto.referencia_do_gabarito({'kvs': [kv, dict(kv)]}, la)
    assert e.value.codigo == 'kv_repetido'


def test_kv_do_gabarito_sem_sha256_e_achado_pelo_arquivo_na_pasta_do_corpus(tmp_path):
    job = _job_com_sugestoes(tmp_path)
    corpus = tmp_path / 'corpus-ficticio'
    (corpus / 'pasta-ficticia').mkdir(parents=True)
    bytes_kv = b'bytes ficticios de um kv'
    (corpus / MARCAS['arquivo']).write_bytes(bytes_kv)
    import hashlib
    sha = hashlib.sha256(bytes_kv).hexdigest()
    la = _laudo_do_job(job)
    la['origem']['sha256'] = sha
    # sem sha256 no gabarito: so a pasta do corpus acha o KV; o primeiro KV aponta para o mesmo arquivo com outra
    # resposta, entao o de outro nome entra no lugar dele
    dados = json.loads(_gabarito(tmp_path, sha, RESPOSTAS[:4], com_sha=False).read_text(encoding='utf-8'))
    dados['kvs'][0]['arquivo'] = 'pasta-ficticia/outro.psd'
    with pytest.raises(acerto.ErroGabarito):
        acerto.referencia_do_gabarito(dados, la)
    ref, _info = acerto.referencia_do_gabarito(dados, la, corpus=corpus)
    assert ref == {10: 'grafismo', 11: 'grafismo', 12: 'titulo', 13: 'cta'}
    # caminho que sai da pasta do corpus nao vale
    (tmp_path / 'fora-do-corpus.psd').write_bytes(bytes_kv)
    dados['kvs'][1]['arquivo'] = '../fora-do-corpus.psd'
    with pytest.raises(acerto.ErroGabarito):
        acerto.referencia_do_gabarito(dados, la, corpus=corpus)


# ------------------------------------------------------------------ comando nao humano
def _cli(*argv):
    saida = io.StringIO()
    with redirect_stdout(saida):
        codigo = cli.principal(list(argv))
    linhas = saida.getvalue().strip().splitlines()
    assert len(linhas) == 1, saida.getvalue()
    return codigo, json.loads(linhas[0]), saida.getvalue()


def test_acerto_nao_e_ato_do_da_nem_aparece_na_tela():
    assert acerto.COMANDO not in humano.COMANDOS
    assert cli.CONFEREM_O_MODO.get(acerto.COMANDO) == ('job',)
    for nome in ('tela.js', 'tela.html'):
        texto = (RAIZ_PLUGIN / 'tela' / nome).read_text(encoding='utf-8')
        assert 'sugestao acerto' not in texto and 'sugestão acerto' not in texto


def test_cli_com_gabarito_so_devolve_numeros_e_nada_pessoal(tmp_path):
    job = _job_com_sugestoes(tmp_path)
    la = _laudo_do_job(job)
    arq = _gabarito(tmp_path, la['origem']['sha256'], RESPOSTAS)
    codigo, env, bruto = _cli('--envelope', 'sugestao', 'acerto', '--job', str(job), '--gabarito', str(arq))
    assert codigo == 0 and env['situacao'] == 'ok' and env['modo_dados'] == 'a'
    c, n = env['contagens'], env['numeros']
    # 10 e um grupo: entra pela sugestao direta; 11 herda grafismo; 12 titulo; 13 errada (alternativa selo errada)
    assert (c['certas_camada'], c['total_camada']) == (3, 4)
    assert c['certas_alternativa'] == 0 and c['com_sugestao'] == 4
    assert c['sem_par'] == 1 and c['fora_do_laudo'] == 1
    assert n['acerto_camada'] == 0.75 and n['cobertura'] == 1.0
    assert 'certas_decisao' in c and 'acerto_decisao' in n
    # nada pessoal nem o caminho do gabarito no envelope, no log ou na medicao
    log = (job / 'log' / 'eventos.jsonl').read_text(encoding='utf-8')
    med = (job / acerto.ARQUIVO).read_text(encoding='utf-8')
    for texto in (bruto, log, med):
        assert not any(v in texto for v in MARCAS.values())
        assert 'marcador-de-caminho' not in texto and str(arq) not in texto
    dados = contratos.ler(job / acerto.ARQUIVO, acerto.ESQUEMA)
    assert dados['gabarito']['a']['referencia'] == 'gabarito'
    assert dados['gabarito']['a']['por_camada'] == {'certas': 3, 'total': 4, 'acerto': 0.75}
    assert '"evento": "%s"' % acerto.EVENTO in log


def test_cli_com_kv_fora_do_gabarito_recusa_sem_gravar(tmp_path):
    job = _job_com_sugestoes(tmp_path)
    arq = _gabarito(tmp_path, 'ef' * 32, RESPOSTAS)
    codigo, env, bruto = _cli('--envelope', 'sugestao', 'acerto', '--job', str(job), '--gabarito', str(arq))
    assert codigo != 0 and env['situacao'] == 'recusado'
    assert env['contagens'] == {'recusa_kv_fora_do_gabarito': 1}
    assert not (job / acerto.ARQUIVO).exists()
    assert 'marcador-de-caminho' not in bruto
    # gabarito que nao existe ou nao se le: o mesmo, sem citar o caminho
    falta = tmp_path / 'marcador-de-caminho-que-falta.json'
    codigo, env, bruto = _cli('--envelope', 'sugestao', 'acerto', '--job', str(job), '--gabarito', str(falta))
    assert codigo != 0 and env['contagens'] == {'recusa_gabarito_invalido': 1}
    assert 'marcador-de-caminho' not in bruto


def test_cli_no_modo_c_registra_sem_sugestao(tmp_path):
    job = _job_com_sugestoes(tmp_path)
    la = _laudo_do_job(job)
    arq = _gabarito(tmp_path, la['origem']['sha256'], RESPOSTAS)
    codigo, env, _ = _cli('--envelope', '--teto-modo-dados', 'c', 'sugestao', 'acerto', '--job', str(job),
                          '--gabarito', str(arq))
    assert codigo == 0 and env['situacao'] == 'ok' and env['contagens'].get('sem_sugestao') == 1
    assert contratos.ler(job / acerto.ARQUIVO, acerto.ESQUEMA)['gabarito']['c']['situacao'] == 'sem_sugestao'


def test_cli_sem_gabarito_e_sem_briefing_recusa(tmp_path):
    job = _job_com_sugestoes(tmp_path)
    codigo, env, _ = _cli('--envelope', 'sugestao', 'acerto', '--job', str(job))
    assert codigo != 0 and env['contagens'] == {'recusa_sem_briefing': 1}


def test_cli_fora_de_um_job(tmp_path):
    codigo, env, _ = _cli('--envelope', 'sugestao', 'acerto', '--job', str(tmp_path))
    assert codigo != 0 and env['situacao'] == 'erro'


# ------------------------------------------------------------------ ao salvar o briefing
from test_tela_salvar import job as job_salvar, modelo  # noqa: E402,F401 - o job sintetico do salvar
import test_tela_salvar as tts_salvar  # noqa: E402
import test_tela_servidor as tts  # noqa: E402
from desdobra.briefing import modelo as mb  # noqa: E402
from desdobra.sugestao import pacote as sp  # noqa: E402
from desdobra.tela import estado as te  # noqa: E402


def _salvar_pela_tela(job, modelo, antes_de_salvar=None):  # noqa: F811
    conteudo = te.montar(job)
    s = tts_salvar._servidor(job, conteudo)
    try:
        biscoito = tts._entrar(s)
        tts_salvar._preparar_rascunho(job, modelo, s, biscoito, conteudo)
        if antes_de_salvar:
            antes_de_salvar()
        codigo, c2, _p = tts_salvar._salvar(s, biscoito, job)
    finally:
        s.parar()
    return codigo, c2


def test_salvar_grava_a_metrica_sem_sugestao_no_modo_c(job_salvar, modelo):  # noqa: F811
    codigo, c2 = _salvar_pela_tela(job_salvar, modelo)
    assert (codigo, c2) == (200, 200)
    dados = contratos.ler(job_salvar / acerto.ARQUIVO, acerto.ESQUEMA)
    assert dados['briefing']['c']['situacao'] == 'sem_sugestao'
    # fora do briefing: o briefing nao cita a medicao
    assert 'medicoes' not in (job_salvar / mb.ARQUIVO).read_text(encoding='utf-8')


def test_salvar_no_modo_a_mede_a_sugestao_contra_o_briefing(job_salvar, modelo):  # noqa: F811
    funcoes = modelo['funcoes']
    certas = sorted(funcoes)[:2]
    itens = [{'layer_id': lid, 'funcao': funcoes[lid], 'alternativa': 'selo' if funcoes[lid] != 'selo' else 'cta'}
             for lid in certas]
    errada = sorted(funcoes)[2]
    itens.append({'layer_id': errada, 'funcao': 'selo' if funcoes[errada] != 'selo' else 'cta',
                  'alternativa': funcoes[errada]})

    def sugerir():
        escolher_modo_do_da(job_salvar, 'a')
        sp.refazer_pacotes(job_salvar)
        tsi._escrever(job_salvar, tsi._sugestoes(job_salvar, itens))
        assert si.importar(job_salvar)['gravou']
    codigo, c2 = _salvar_pela_tela(job_salvar, modelo, sugerir)
    assert (codigo, c2) == (200, 200)
    m = contratos.ler(job_salvar / acerto.ARQUIVO, acerto.ESQUEMA)['briefing']['a']
    b = mb.ler(job_salvar)
    resolvidas = mb.resolver(contratos.ler(job_salvar / 'laudo' / 'laudo.json', 'laudo/1'), b)[0]
    # a sugestao vai na mesma raiz da funcao do DA: as camadas que herdam dela contam igual
    de = {raiz: sum(r['raiz'] == raiz for r in resolvidas.values()) for raiz in certas + [errada]}
    assert all(de.values())
    assert m['situacao'] == 'medido' and m['por_camada']['total'] == len(resolvidas)
    assert m['por_camada']['certas'] == de[certas[0]] + de[certas[1]]
    assert m['alternativa']['certas'] == de[errada] and m['cobertura']['com_sugestao'] == sum(de.values())
    assert m['sugestoes_ref'] == b['sugestoes_ref']
    # nenhuma sugestao virou valor: o briefing tem as funcoes do DA
    assert {x['layer_id']: x['funcao']['valor'] for x in b['funcoes']} == funcoes


@pytest.mark.parametrize('erro', [OSError('disco'), RuntimeError('qualquer')])
def test_falha_ao_gravar_a_metrica_nao_interrompe_o_salvar(job_salvar, modelo, monkeypatch, erro):  # noqa: F811
    def quebra(*_a, **_k):
        raise erro
    monkeypatch.setattr(acerto, 'gravar', quebra)
    antes = (job_salvar / mb.ARQUIVO).read_bytes()
    codigo, c2 = _salvar_pela_tela(job_salvar, modelo)
    assert (codigo, c2) == (200, 200)
    assert (job_salvar / mb.ARQUIVO).read_bytes() != antes
    assert not (job_salvar / acerto.ARQUIVO).exists()
