# -*- coding: utf-8 -*-
"""M7c, M2: esquema e modulo do perfil de marca (desdobra.marca.perfil, schemas/perfil-marca-1.json) e a parte do
gancho que nega ao Claude a escrita na biblioteca de marcas.

Conteudo pela decisoes-v1.md, 190: Q1, o perfil guarda so as regras de escala e as ancoras por funcao confirmadas
pelo DA, cada uma com o job de origem, e o nome PostScript das faces; a versao da galeria, as edicoes de palco e o
lockup de governo ficam no job; as cores ficam como campo opcional sem produtor. Q3, cada registro vira uma versao
nova; vale a mais recente, citando o job de origem; as anteriores ficam inteiras no historico e nunca sao apagadas.

Tudo sintetico: a biblioteca e uma pasta temporaria; nenhum arquivo de fonte e lido. Os bytes com assinatura de fonte
do teste da recusa sao so a assinatura, escritos na hora.
"""
import copy
import hashlib
import importlib.util
import json

import pytest

from conftest import RAIZ_PLUGIN
from desdobra import contratos
from desdobra.arquivos import para_json
from desdobra.contratos import ErroContrato

SCRIPT_GANCHO = RAIZ_PLUGIN / 'scripts' / 'gancho_confirmacoes.py'
JOB_1 = 'a1' * 8
JOB_2 = 'b2' * 8
JOB_3 = 'c3' * 8
SHA = 'd4' * 32
SHA_2 = 'e5' * 32


def _perfil():
    from desdobra.marca import perfil as p
    return p


def _campanha(job, formatos=('f1080x1080', 'f300x250'), sha=SHA):
    return {'job': job, 'data': '2026-11-12', 'formatos': [{'formato': f, 'aprovacao_sha256': sha} for f in formatos],
            'confirmado_por': {'usuario': 'da', 'maquina': 'estacao'}, 'origem': 'da', 'meio': 'tela'}


def _conteudo(job, regra_titulo='lado_curto', x_logo='direita'):
    return {
        'regras_escala': [{'funcao': 'titulo', 'regra': regra_titulo, 'job_origem': job},
                          {'funcao': 'logo_principal', 'regra': 'raiz_area', 'job_origem': job}],
        'ancoras': [{'funcao': 'logo_principal', 'x': x_logo, 'y': 'base', 'job_origem': job}],
        'faces': [{'postscript': 'Sintetica-Bold'}, {'postscript': 'Sintetica-Regular'}],
    }


def _registrar(p, bib, id_, job, **kw):
    conteudo = _conteudo(job, **{k: v for k, v in kw.items() if k in ('regra_titulo', 'x_logo')})
    return p.nova_versao(bib, id_, campanha=_campanha(job), quando='2026-11-12T10:00:00-03:00', **conteudo)


@pytest.fixture
def bib(tmp_path):
    pasta = tmp_path / 'biblioteca'
    pasta.mkdir()
    return pasta


# ------------------------------------------------------------------ esquema

def test_esquema_existe_e_segue_a_convencao():
    assert 'perfil-marca/1' in contratos.listar_esquemas()
    esquema = contratos.carregar_esquema('perfil-marca/1')
    assert esquema['properties']['esquema'] == {'const': 'perfil-marca/1'}


def test_funcoes_e_regras_do_perfil_sao_as_do_briefing_sem_indeterminado():
    briefing = contratos.carregar_esquema('briefing/1')['$defs']
    esquema = contratos.carregar_esquema('perfil-marca/1')['$defs']
    assert set(esquema['funcao']['enum']) == set(briefing['funcao']['enum']) - {'indeterminado'}
    assert esquema['regra']['enum'] == briefing['regra']['enum']


def _perfil_valido():
    v1 = dict(versao=1, job_origem=JOB_1, quando='2026-11-12T10:00:00-03:00', campanha=_campanha(JOB_1),
              **_conteudo(JOB_1))
    return {'esquema': 'perfil-marca/1', 'id': '0f' * 16, 'marca': 'Marca Sintetica', 'criado_em': '2026-11-12',
            'versao': 1, 'atual': v1, 'historico': []}


def test_perfil_valido_passa_e_cores_sao_opcionais():
    dados = _perfil_valido()
    contratos.validar(dados, 'perfil-marca/1')
    dados['atual']['cores'] = [{'srgb': '#12ab34', 'job_origem': JOB_1}]
    contratos.validar(dados, 'perfil-marca/1')
    dados['atual']['cores'] = [{'srgb': 'vermelho', 'job_origem': JOB_1}]
    with pytest.raises(ErroContrato):
        contratos.validar(dados, 'perfil-marca/1')


def _mexer(caminho, valor):
    def f(d):
        alvo = d
        for k in caminho[:-1]:
            alvo = alvo[k]
        alvo[caminho[-1]] = valor
    return f


RECUSAS = {
    'arquivo de fonte no topo': _mexer(['arquivo_fonte'], 'Sintetica-Bold.otf'),
    'caminho de fonte no topo': _mexer(['caminho_fonte'], 'C:/fontes/Sintetica-Bold.otf'),
    'arquivo de fonte na versao': _mexer(['atual', 'fontes'], [{'arquivo': 'x.ttf'}]),
    'face com arquivo': _mexer(['atual', 'faces'], [{'postscript': 'Sintetica-Bold', 'arquivo': 'x.otf'}]),
    'face com nome de arquivo de fonte': _mexer(['atual', 'faces'], [{'postscript': 'Sintetica-Bold.otf'}]),
    'face com caminho': _mexer(['atual', 'faces'], [{'postscript': 'fontes/Sintetica-Bold'}]),
    'face com caminho do windows': _mexer(['atual', 'faces'], [{'postscript': 'C:\\fontes\\Sintetica'}]),
    'face com bytes': _mexer(['atual', 'faces'], [{'postscript': 'Sintetica-Bold', 'bytes': 'AAEAAA=='}]),
    'lockup de governo': _mexer(['atual', 'lockup_governo'], {'valor': 'sim'}),
    'limite sem fonte': _mexer(['atual', 'limites'], [{'id': 'x', 'valor': 3}]),
    'versao da galeria': _mexer(['atual', 'galeria'], {'versao': 2}),
    'edicao de palco': _mexer(['atual', 'edicoes_palco'], [{'layer_id': 3, 'dx': 4}]),
    'mestres do job': _mexer(['atual', 'mestres'], []),
    'regra de camada indeterminado': _mexer(['atual', 'regras_escala'],
                                           [{'funcao': 'indeterminado', 'regra': 'largura', 'job_origem': JOB_1}]),
    'regra sem job de origem': _mexer(['atual', 'regras_escala'], [{'funcao': 'titulo', 'regra': 'largura'}]),
    'regra fora do enum': _mexer(['atual', 'regras_escala'],
                                 [{'funcao': 'titulo', 'regra': 'esticar', 'job_origem': JOB_1}]),
    'ancora por camada': _mexer(['atual', 'ancoras'],
                                [{'layer_id': 7, 'x': 'centro', 'y': 'meio', 'job_origem': JOB_1}]),
    'ancora sem job de origem': _mexer(['atual', 'ancoras'], [{'funcao': 'cta', 'x': 'centro', 'y': 'meio'}]),
    'campanha de teste': _mexer(['atual', 'campanha', 'origem'], 'fixture_de_teste'),
    'campanha fora da tela': _mexer(['atual', 'campanha', 'meio'], 'terminal'),
    'campanha sem formato': _mexer(['atual', 'campanha', 'formatos'], []),
    'aprovacao sem sha256': _mexer(['atual', 'campanha', 'formatos'], [{'formato': 'f1', 'aprovacao_sha256': 'x'}]),
    'id derivado do nome': _mexer(['id'], 'marca-sintetica'),
    'nome com caminho': _mexer(['marca'], 'marcas/../x'),
    'nome de arquivo de fonte': _mexer(['marca'], 'Sintetica.ttf'),
    'nome vazio': _mexer(['marca'], ''),
    'cor com produtor de outro tipo': _mexer(['atual', 'cores'], [{'srgb': '#000000'}]),
    # revisao do M2: caminho ou arquivo de fonte nos campos de texto
    'formato com caminho de fonte': _mexer(['atual', 'campanha', 'formatos'],
                                           [{'formato': 'C:/Windows/Fonts/sintetica.ttf', 'aprovacao_sha256': SHA}]),
    'formato com arquivo de fonte': _mexer(['atual', 'campanha', 'formatos'],
                                           [{'formato': 'sintetica.otf', 'aprovacao_sha256': SHA}]),
    'data com caminho de fonte': _mexer(['atual', 'campanha', 'data'], 'D:/fontes/Sintetica-Bold.otf'),
    'usuario com caminho de fonte': _mexer(['atual', 'campanha', 'confirmado_por', 'usuario'], '/fontes/x.woff2'),
    'usuario com arquivo de fonte': _mexer(['atual', 'campanha', 'confirmado_por', 'usuario'], 'Sintetica.ttf'),
    'maquina com caminho': _mexer(['atual', 'campanha', 'confirmado_por', 'maquina'], 'C:\\fontes\\x'),
    'quando com caminho de fonte': _mexer(['atual', 'quando'], 'C:/fontes/Sintetica.ttf'),
    'quando fora de data': _mexer(['atual', 'quando'], 'x'),
    'criado_em com caminho de fonte': _mexer(['criado_em'], 'C:/fontes/Sintetica.ttf'),
    'criado_em em base64': _mexer(['criado_em'], 'T1RUTwAAAAAAAAAAAAAAAAAA'),
    'nome com fonte no meio': _mexer(['marca'], 'Sintetica.otf v2'),
}


@pytest.mark.parametrize('caso', sorted(RECUSAS))
def test_esquema_recusa(caso):
    dados = _perfil_valido()
    contratos.validar(copy.deepcopy(dados), 'perfil-marca/1')  # o valido passa: a recusa e do campo mexido
    RECUSAS[caso](dados)
    with pytest.raises(ErroContrato):
        contratos.validar(dados, 'perfil-marca/1')


def test_esquema_recusa_toda_extensao_de_fonte_no_nome_da_face_e_da_marca():
    from desdobra.arquivos import EXTENSOES_FONTE
    for ext in EXTENSOES_FONTE:
        for nome in ('Sintetica' + ext, 'Sintetica' + ext.upper()):
            dados = _perfil_valido()
            dados['atual']['faces'] = [{'postscript': nome}]
            with pytest.raises(ErroContrato):
                contratos.validar(dados, 'perfil-marca/1')
            dados = _perfil_valido()
            dados['marca'] = nome
            with pytest.raises(ErroContrato):
                contratos.validar(dados, 'perfil-marca/1')


def _codificados(bruto):
    import base64
    return {'base64': base64.b64encode(bruto).decode(), 'base64 url': base64.urlsafe_b64encode(bruto).decode(),
            'base64 sem preenchimento': base64.b64encode(bruto).decode().rstrip('='), 'hex': bruto.hex()}


@pytest.mark.parametrize('assinatura', [b'OTTO', b'\x00\x01\x00\x00', b'wOF2', b'ttcf', b'true'])
@pytest.mark.parametrize('onde', ['usuario', 'maquina', 'formato', 'marca', 'postscript'])
def test_validar_recusa_bytes_de_fonte_codificados_em_qualquer_texto(assinatura, onde):
    """Revisao do M2: bytes de fonte em base64 ou em hex, em qualquer campo de texto, sao recusados pelo modulo."""
    p = _perfil()
    for rotulo, texto in _codificados(assinatura + bytes(range(1, 24))).items():
        dados = _perfil_valido()
        p.validar(copy.deepcopy(dados))
        if onde in ('usuario', 'maquina'):
            dados['atual']['campanha']['confirmado_por'][onde] = texto
        elif onde == 'formato':
            dados['atual']['campanha']['formatos'][0]['formato'] = texto
        elif onde == 'marca':
            dados['marca'] = texto
        else:
            dados['atual']['faces'] = [{'postscript': texto}]
        with pytest.raises((ErroContrato, p.ErroPerfil)):
            p.validar(dados)
        assert rotulo


def test_validar_aceita_texto_comum_e_hash():
    p = _perfil()
    dados = _perfil_valido()
    dados['atual']['campanha']['confirmado_por'] = {'usuario': 'DA-Agencia', 'maquina': 'ESTACAO-07'}
    dados['marca'] = 'Marca Sintetica 2027'
    p.validar(dados)
    # quem confirmou pode vir sem usuario e sem maquina (desdobra.humano.Disparo)
    dados['atual']['campanha']['confirmado_por'] = {'usuario': None, 'maquina': None}
    p.validar(dados)
    dados['atual']['quando'] = '2026-11-12T10:00:00.123456+00:00'
    dados['criado_em'] = '2026-11-12T09:00:00Z'
    p.validar(dados)


# ------------------------------------------------------------------ modulo

def test_criar_gera_id_ao_acaso_sem_relacao_com_o_nome(bib):
    p = _perfil()
    a = p.criar(bib, 'Marca Sintetica', quando='2026-11-12T09:00:00-03:00')
    b = p.criar(bib, 'Marca Sintetica', quando='2026-11-12T09:00:00-03:00')
    assert a['id'] != b['id']
    for dados in (a, b):
        assert len(dados['id']) == 32 and set(dados['id']) <= set('0123456789abcdef')
        nome = dados['marca'].encode('utf-8')
        for derivado in (hashlib.sha256(nome).hexdigest(), hashlib.md5(nome).hexdigest(),
                         hashlib.sha1(nome).hexdigest(), nome.hex()):
            assert dados['id'] not in derivado and derivado[:32] != dados['id']
        assert dados['versao'] == 0 and dados['atual'] is None and dados['historico'] == []
        arquivo = bib / 'marcas' / dados['id'] / 'perfil-marca.json'
        assert arquivo.is_file()
        assert contratos.ler(arquivo, 'perfil-marca/1') == dados


def test_ler_e_listar(bib):
    p = _perfil()
    a = p.criar(bib, 'Marca B')
    b = p.criar(bib, 'Marca A')
    assert p.ler(bib, a['id']) == a
    assert p.listar(bib) == [{'id': b['id'], 'marca': 'Marca A'}, {'id': a['id'], 'marca': 'Marca B'}]
    # o que nao e perfil gravado pelo desdobra fica de fora da lista, sem erro
    (bib / 'marcas' / 'solto.txt').write_text('x', encoding='utf-8')
    (bib / 'marcas' / ('9a' * 16)).mkdir()
    (bib / 'marcas' / ('8b' * 16)).mkdir()
    (bib / 'marcas' / ('8b' * 16) / 'perfil-marca.json').write_text('{quebrado', encoding='utf-8')
    assert [m['id'] for m in p.listar(bib)] == [b['id'], a['id']]


def test_listar_sem_pasta_de_marcas_e_vazio(bib):
    assert _perfil().listar(bib) == []


@pytest.mark.parametrize('id_', ['../fora', 'marca-sintetica', 'AB' * 16, '', 'a' * 31])
def test_id_fora_do_formato_e_recusado(bib, id_):
    p = _perfil()
    with pytest.raises(p.ErroPerfil):
        p.ler(bib, id_)


def test_nova_versao_guarda_a_anterior_inteira_no_historico(bib):
    p = _perfil()
    id_ = p.criar(bib, 'Marca Sintetica')['id']
    d1, criou1 = _registrar(p, bib, id_, JOB_1)
    assert criou1 and d1['versao'] == 1 and d1['atual']['job_origem'] == JOB_1 and d1['historico'] == []
    v1_bytes = para_json(d1['atual'])

    d2, criou2 = _registrar(p, bib, id_, JOB_2, regra_titulo='largura')
    assert criou2 and d2['versao'] == 2 and d2['atual']['versao'] == 2 and d2['atual']['job_origem'] == JOB_2
    assert [h['versao'] for h in d2['historico']] == [1]
    assert para_json(d2['historico'][0]) == v1_bytes  # versao 1 igual byte a byte

    d3, criou3 = _registrar(p, bib, id_, JOB_3, x_logo='centro')
    assert criou3 and d3['versao'] == 3
    assert [h['versao'] for h in d3['historico']] == [1, 2]
    assert para_json(d3['historico'][0]) == v1_bytes
    assert para_json(d3['historico'][1]) == para_json(d2['atual'])
    # a que vale e a mais recente, citando o job de origem
    assert p.atual(d3)['job_origem'] == JOB_3
    assert p.ler(bib, id_) == d3


def test_mesmo_job_sem_mudanca_nao_cria_versao(bib):
    p = _perfil()
    id_ = p.criar(bib, 'Marca Sintetica')['id']
    _registrar(p, bib, id_, JOB_1)
    arquivo = bib / 'marcas' / id_ / 'perfil-marca.json'
    antes = arquivo.read_bytes()
    dados, criou = _registrar(p, bib, id_, JOB_1)
    assert not criou and dados['versao'] == 1
    assert arquivo.read_bytes() == antes
    # o mesmo job com mudanca cria versao
    dados, criou = _registrar(p, bib, id_, JOB_1, regra_titulo='altura')
    assert criou and dados['versao'] == 2 and dados['historico'][0]['job_origem'] == JOB_1


def test_nova_versao_recusa_versao_de_partida_diferente_da_esperada(bib):
    """Quem conferiu o perfil na versao N grava com versao_esperada=N: se outro registro gravou antes, recusa sem
    gravar; sem versao_esperada, segue como antes."""
    p = _perfil()
    id_ = p.criar(bib, 'Marca Sintetica')['id']
    _registrar(p, bib, id_, JOB_1)
    arquivo = bib / 'marcas' / id_ / 'perfil-marca.json'
    antes = arquivo.read_bytes()
    with pytest.raises(p.ErroPerfil, match='mudou'):
        p.nova_versao(bib, id_, campanha=_campanha(JOB_2), versao_esperada=0, **_conteudo(JOB_2))
    assert arquivo.read_bytes() == antes
    # o mesmo job sem mudanca tambem e recusado quando a versao de partida nao e a esperada
    with pytest.raises(p.ErroPerfil, match='mudou'):
        p.nova_versao(bib, id_, campanha=_campanha(JOB_1), quando='2026-11-12T10:00:00-03:00', versao_esperada=0,
                      **_conteudo(JOB_1))
    dados, criou = p.nova_versao(bib, id_, campanha=_campanha(JOB_2), versao_esperada=1, **_conteudo(JOB_2))
    assert criou and dados['versao'] == 2


ESPERA_DO_OUTRO_S = 1.0  # numero-neutro: sem a trava, o outro registro grava em milissegundos; com ela, fica esperando


def test_nova_versao_concorrente_entre_a_releitura_e_a_gravacao_espera_a_trava_da_marca(bib, monkeypatch):
    """Revisao da correcao B: outro registro que chega entre a releitura final e a gravacao deste espera a trava da
    marca; quando entra, le a versao nova, ve que nao e a que conferiu e e recusado. Nenhuma versao some sem erro."""
    import threading
    p = _perfil()
    id_ = p.criar(bib, 'Marca Sintetica')['id']
    original = p._gravar
    resultado = {}

    def outro():
        try:
            resultado['outro'] = p.nova_versao(bib, id_, campanha=_campanha(JOB_2), versao_esperada=0,
                                               **_conteudo(JOB_2))
        except p.ErroPerfil as e:
            resultado['erro_do_outro'] = str(e)
    linha = threading.Thread(target=outro)

    def gravar_intercalado(biblioteca, dados):
        if 'iniciado' not in resultado:
            resultado['iniciado'] = True
            linha.start()
            linha.join(ESPERA_DO_OUTRO_S)
        return original(biblioteca, dados)
    monkeypatch.setattr(p, '_gravar', gravar_intercalado)
    dados, criou = p.nova_versao(bib, id_, campanha=_campanha(JOB_1), versao_esperada=0, **_conteudo(JOB_1))
    linha.join()
    assert criou and dados['versao'] == 1
    final = p.ler(bib, id_)
    jobs = [v['campanha']['job'] for v in [final['atual']] + final['historico']]
    assert 'outro' not in resultado or JOB_2 in jobs, 'a versao do outro registro sumiu sem erro'
    assert 'mudou' in resultado.get('erro_do_outro', '')
    assert jobs == [JOB_1]


def test_versao_recusa_job_de_origem_diferente_da_campanha_e_funcao_repetida(bib):
    p = _perfil()
    id_ = p.criar(bib, 'Marca Sintetica')['id']
    conteudo = _conteudo(JOB_1)
    with pytest.raises(p.ErroPerfil):
        p.nova_versao(bib, id_, campanha=_campanha(JOB_2), **conteudo)
    repetida = copy.deepcopy(conteudo)
    repetida['regras_escala'].append({'funcao': 'titulo', 'regra': 'altura', 'job_origem': JOB_1})
    with pytest.raises(p.ErroPerfil):
        p.nova_versao(bib, id_, campanha=_campanha(JOB_1), **repetida)
    repetida = copy.deepcopy(conteudo)
    repetida['ancoras'].append({'funcao': 'logo_principal', 'x': 'centro', 'y': 'topo', 'job_origem': JOB_1})
    with pytest.raises(p.ErroPerfil):
        p.nova_versao(bib, id_, campanha=_campanha(JOB_1), **repetida)
    assert p.ler(bib, id_)['versao'] == 0


def test_regra_que_nao_mudou_pode_manter_o_job_de_origem_registrado_antes(bib):
    p = _perfil()
    id_ = p.criar(bib, 'Marca Sintetica')['id']
    _registrar(p, bib, id_, JOB_1)
    conteudo = _conteudo(JOB_2, regra_titulo='altura')
    conteudo['regras_escala'][1]['job_origem'] = JOB_1  # logo_principal veio do job 1 e nao mudou
    dados, criou = p.nova_versao(bib, id_, campanha=_campanha(JOB_2), **conteudo)
    assert criou and dados['atual']['regras_escala'][1]['job_origem'] == JOB_1
    conteudo['regras_escala'][1]['job_origem'] = JOB_3  # job sem campanha registrada
    with pytest.raises(p.ErroPerfil):
        p.nova_versao(bib, id_, campanha=_campanha(JOB_2), **conteudo)


@pytest.mark.parametrize('extra', [{'lockup_governo': 'sim'}, {'galeria': {'versao': 2}},
                                   {'edicoes_palco': []}, {'limites': []}])
def test_versao_recusa_o_que_fica_no_job(bib, extra):
    p = _perfil()
    id_ = p.criar(bib, 'Marca Sintetica')['id']
    with pytest.raises(TypeError):
        p.nova_versao(bib, id_, campanha=_campanha(JOB_1), **_conteudo(JOB_1), **extra)


def test_campanha_de_teste_nunca_entra(bib):
    p = _perfil()
    id_ = p.criar(bib, 'Marca Sintetica')['id']
    campanha = _campanha(JOB_1)
    campanha['origem'] = 'fixture_de_teste'
    with pytest.raises((p.ErroPerfil, ErroContrato)):
        p.nova_versao(bib, id_, campanha=campanha, **_conteudo(JOB_1))
    assert p.ler(bib, id_)['versao'] == 0


def test_cores_opcionais_sem_produtor(bib):
    p = _perfil()
    id_ = p.criar(bib, 'Marca Sintetica')['id']
    dados, _ = p.nova_versao(bib, id_, campanha=_campanha(JOB_1), cores=[{'srgb': '#00ff00', 'job_origem': JOB_1}],
                             **_conteudo(JOB_1))
    assert dados['atual']['cores'] == [{'srgb': '#00ff00', 'job_origem': JOB_1}]
    dados, _ = _registrar(p, bib, id_, JOB_2)
    assert 'cores' not in dados['atual']


def test_historico_adulterado_e_recusado_na_leitura(bib):
    p = _perfil()
    id_ = p.criar(bib, 'Marca Sintetica')['id']
    _registrar(p, bib, id_, JOB_1)
    _registrar(p, bib, id_, JOB_2, regra_titulo='largura')
    arquivo = bib / 'marcas' / id_ / 'perfil-marca.json'
    original = json.loads(arquivo.read_text(encoding='utf-8'))
    for mexer in (lambda d: d['historico'].clear(),                   # versao anterior apagada
                  lambda d: d.__setitem__('versao', 3),                # versao que nao bate com a atual
                  lambda d: d['historico'][0].__setitem__('versao', 2)):  # historico fora de ordem
        d = copy.deepcopy(original)
        mexer(d)
        arquivo.write_text(json.dumps(d), encoding='utf-8')
        with pytest.raises(p.ErroPerfil):
            p.ler(bib, id_)
        with pytest.raises(p.ErroPerfil):
            _registrar(p, bib, id_, JOB_3)


def test_gravacao_atomica_sem_temporario(bib):
    p = _perfil()
    id_ = p.criar(bib, 'Marca Sintetica')['id']
    _registrar(p, bib, id_, JOB_1)
    # a trava da marca (revisao da correcao B) fica na pasta, vazia; nenhum temporario sobra
    assert sorted(x.name for x in (bib / 'marcas' / id_).iterdir()) == [p.ARQUIVO_TRAVA, 'perfil-marca.json']
    assert (bib / 'marcas' / id_ / p.ARQUIVO_TRAVA).read_bytes() == b''


def test_motor_recusa_gravar_arquivo_com_assinatura_ou_nome_de_fonte_na_marca(bib):
    p = _perfil()
    id_ = p.criar(bib, 'Marca Sintetica')['id']
    pasta = bib / 'marcas' / id_
    for inicio in (b'OTTO', b'\x00\x01\x00\x00', b'wOF2', b'ttcf'):
        with pytest.raises(p.ErroPerfil):
            p.gravar_na_marca(bib, id_, 'perfil-marca.json', inicio + b'resto')
    with pytest.raises(p.ErroPerfil):
        p.gravar_na_marca(bib, id_, 'face.otf', b'{}')
    with pytest.raises(p.ErroPerfil):
        p.gravar_na_marca(bib, id_, '../fora.json', b'{}')
    assert sorted(x.name for x in pasta.iterdir()) == ['perfil-marca.json']
    assert not (bib / 'marcas' / 'fora.json').exists()


def test_pasta_da_marca_que_aponta_para_fora_e_recusada(bib, tmp_path):
    p = _perfil()
    fora = tmp_path / 'fora'
    fora.mkdir()
    (bib / 'marcas').mkdir()
    ligacao = bib / 'marcas' / ('7c' * 16)
    try:
        ligacao.symlink_to(fora, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip('sem permissao para criar ligacao simbolica nesta maquina')
    with pytest.raises(p.ErroPerfil):
        p.gravar_na_marca(bib, '7c' * 16, 'perfil-marca.json', b'{}')
    assert list(fora.iterdir()) == []


def test_pasta_marcas_ligada_para_fora_da_biblioteca_e_recusada(bib, tmp_path):
    """Revisao do M2: <biblioteca>/marcas ligada para fora resolve igual dos dois lados da conferencia antiga."""
    p = _perfil()
    fora = tmp_path / 'fora_da_biblioteca'
    fora.mkdir()
    try:
        (bib / 'marcas').symlink_to(fora, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip('sem permissao para criar ligacao simbolica nesta maquina')
    with pytest.raises(p.ErroPerfil):
        p.criar(bib, 'Marca Sintetica')
    with pytest.raises(p.ErroPerfil):
        p.gravar_na_marca(bib, '7c' * 16, 'perfil-marca.json', b'{}')
    assert list(fora.iterdir()) == []


def test_nada_varre_o_resto_da_biblioteca(bib):
    """A conferencia de fonte olha so o que o desdobra grava: um arquivo de fonte de terceiros em outra pasta da
    biblioteca nao trava nem avisa."""
    p = _perfil()
    (bib / 'outras-coisas').mkdir()
    (bib / 'outras-coisas' / 'face.otf').write_bytes(b'OTTO')
    id_ = p.criar(bib, 'Marca Sintetica')['id']
    dados, criou = _registrar(p, bib, id_, JOB_1)
    assert criou and dados['versao'] == 1


def test_modulo_sem_valor_numerico_de_regra():
    """Nada de regra do motor no perfil: so o que o DA confirmou."""
    p = _perfil()
    assert p.ESQUEMA == 'perfil-marca/1' and p.ARQUIVO == 'perfil-marca.json'


# ------------------------------------------------------------------ gancho

def _gancho():
    spec = importlib.util.spec_from_file_location('gancho_confirmacoes_marca', SCRIPT_GANCHO)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def g():
    return _gancho()


def _decidir(g, ferramenta, entrada, cwd):
    return g.decidir_com_motivo({'tool_name': ferramenta, 'tool_input': entrada, 'cwd': str(cwd)})


@pytest.mark.parametrize('ferramenta', ['Write', 'Edit', 'MultiEdit', 'NotebookEdit'])
@pytest.mark.parametrize('rel', ['marcas/%s/perfil-marca.json' % ('ab' * 16), 'marcas/%s/outro.json' % ('ab' * 16),
                                 'marcas/novo.json', 'marcas\\%s\\perfil-marca.json' % ('ab' * 16)])
def test_gancho_nega_ao_claude_a_escrita_na_biblioteca_de_marcas(g, tmp_path, ferramenta, rel):
    caminho = str(tmp_path / 'biblioteca') + '/' + rel
    campo = 'notebook_path' if ferramenta == 'NotebookEdit' else 'file_path'
    decisao, motivo = _decidir(g, ferramenta, {campo: caminho, 'content': '{}'}, tmp_path)
    assert decisao == 'deny'
    assert motivo == g.MOTIVO_MARCA


def test_gancho_nega_caminho_relativo_dentro_de_marcas(g, tmp_path):
    cwd = tmp_path / 'biblioteca' / 'marcas' / ('ab' * 16)
    cwd.mkdir(parents=True)
    for caminho in ('perfil-marca.json', 'x.json', './y.json'):
        assert _decidir(g, 'Write', {'file_path': caminho, 'content': '{}'}, cwd)[0] == 'deny'


def test_gancho_nega_escrita_por_ligacao_para_marcas(g, tmp_path):
    marcas = tmp_path / 'biblioteca' / 'marcas'
    marcas.mkdir(parents=True)
    atalho = tmp_path / 'atalho'
    try:
        atalho.symlink_to(marcas, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip('sem permissao para criar ligacao simbolica nesta maquina')
    assert _decidir(g, 'Write', {'file_path': str(atalho / 'x.json'), 'content': '{}'}, tmp_path)[0] == 'deny'


ID = 'ab' * 16
COMANDOS_NEGADOS = [
    ('Bash', 'echo {} > biblioteca/marcas/%s/perfil-marca.json' % ID),
    ('Bash', 'echo {} > /c/agencia/biblioteca/marcas/%s/novo.json' % ID),
    ('Bash', 'cp /tmp/x.json "biblioteca/marcas/%s/perfil-marca.json"' % ID),
    ('Bash', 'mv x.json biblioteca/marcas/%s/' % ID),
    ('Bash', 'rm -rf biblioteca/marcas/%s' % ID),
    ('Bash', 'rm biblioteca/marcas/%s/perfil-marca.json' % ID),
    ('Bash', 'mkdir -p biblioteca/marcas/%s' % ID),
    ('Bash', 'touch biblioteca/marcas/novo.json'),
    ('Bash', "python -c \"open('biblioteca/marcas/%s/perfil-marca.json','w').write('{}')\"" % ID),
    ('Bash', "python -c \"import shutil; shutil.rmtree('biblioteca/marcas')\""),
    ('Bash', 'sed -i s/a/b/ biblioteca/marcas/%s/perfil-marca.json' % ID),
    ('Bash', 'echo {} > perfil-marca.json'),
    ('PowerShell', 'Set-Content -Path biblioteca\\marcas\\%s\\perfil-marca.json -Value "{}"' % ID),
    ('PowerShell', 'Remove-Item -Recurse -Force biblioteca\\marcas\\%s' % ID),
    ('PowerShell', 'New-Item -ItemType Directory biblioteca\\marcas\\%s' % ID),
    ('PowerShell', 'del biblioteca\\marcas\\%s\\perfil-marca.json' % ID),
    ('PowerShell', 'Clear-Content biblioteca\\marcas\\%s\\perfil-marca.json' % ID),
    ('Bash', 'python -c "import desdobra.marca.perfil as p; p.criar(1, 2)"'),
    ('Bash', 'python -c "from desdobra.marca import perfil; perfil.nova_versao(1, 2)"'),
    ('Bash', 'python -c "from desdobra.marca.perfil import nova_versao"'),
    ('Bash', 'python -c "from desdobra import marca; marca.perfil.criar(1, 2)"'),
    ('Bash', 'python -c "import desdobra.marca.registrar"'),
    ('PowerShell', 'python -c "from desdobra.marca import registrar"'),
    # revisao do M2: o codigo do perfil por __import__, import_module, getattr, sys.path e run_path
    ('Bash', "python -c \"m=__import__('desdobra.marca', fromlist=['perfil']); m.perfil.ler('b', '%s')\"" % ID),
    ('Bash', "python -c \"m=__import__('desdobra.marca', fromlist=['perfil']); m.perfil.nova_versao('b', 'x')\""),
    ('Bash', "python -c \"import importlib; p=importlib.import_module('desdobra.marca.perfil')\""),
    ('Bash', "python -c \"import importlib; p=importlib.import_module('.marca', 'desdobra')\""),
    ('Bash', "python -c \"d=__import__('desdobra').marca\""),
    ('Bash', "python -c \"import desdobra; getattr(__import__('desdobra'), 'marca')\""),
    ('Bash', "python -c \"import sys; sys.path.insert(0, 'motor/desdobra/marca'); import perfil\""),
    ('Bash', "python -c \"import runpy; runpy.run_path('motor/desdobra/marca/perfil.py')\""),
    ('Bash', 'python motor/desdobra/marca/perfil.py'),
    # revisao do M4: o perfil lido pelas funcoes da tela que o carregam (padrao_da_marca, marca_na_tela)
    ('Bash', "python -c \"from desdobra.tela import funcoes; print(funcoes.padrao_da_marca('j', 'b'))\""),
    ('Bash', "python -c \"from desdobra.tela import estado; print(estado.marca_na_tela('j', 'b'))\""),
    ('PowerShell', "python -c \"from desdobra.tela.funcoes import padrao_da_marca as p; print(p('j', 'b'))\""),
    # revisao do M2: a biblioteca pelo motor (desdobra.biblioteca.pasta_marcas), sem o segmento marcas/ no texto
    ('Bash', "python -c \"import shutil; from desdobra.biblioteca import pasta_marcas as p; shutil.rmtree(p('b'))\""),
    ('Bash', "python -c \"from desdobra.biblioteca import pasta_marcas as p; "
             "print([x.read_text() for x in p('b').rglob('*.json')])\""),
    ('Bash', "python -c \"from desdobra import biblioteca as b; import shutil; shutil.rmtree(b.pasta_marcas('x'))\""),
    ('Bash', "python -c \"import os, shutil; from desdobra import biblioteca as b; "
             "shutil.rmtree(os.path.join('x', b.PASTA_MARCAS))\""),
    # revisao do M2: o nome marcas sozinho, num argumento de codigo ou depois de um cd
    ('Bash', "python -c \"import os, shutil; shutil.rmtree(os.path.join('C:/agencia/bib', 'marcas'))\""),
    ('Bash', "python -c \"from pathlib import Path; (Path('C:/agencia/bib') / 'marcas' / 'x.json').write_text('1')\""),
    ('Bash', 'cd /c/agencia/bib && rm -rf marcas'),
    ('PowerShell', 'Set-Location C:\\agencia\\bib; Remove-Item -Recurse marcas'),
    # revisao do M2: marcas. (o Windows tira o ponto e o espaco do fim do segmento)
    ('Bash', 'echo x > C:/agencia/bib/marcas./%s/notas.json' % ID),
    ('PowerShell', 'Set-Content -Path C:/agencia/bib/marcas./%s/notas.json -Value x' % ID),
    ('PowerShell', 'Set-Content -Path "C:\\agencia\\bib\\marcas. .\\%s\\notas.json" -Value x' % ID),
    ('Bash', 'rm -rf C:/agencia/bib/marcas..'),
]


@pytest.mark.parametrize('ferramenta,comando', COMANDOS_NEGADOS)
def test_gancho_nega_escrita_em_marcas_pelo_terminal(g, tmp_path, ferramenta, comando):
    decisao, motivo = _decidir(g, ferramenta, {'command': comando}, tmp_path)
    assert decisao == 'deny', comando
    assert motivo == g.MOTIVO_MARCA


COMANDOS_LIVRES = [
    ('Bash', 'git diff -- plugins/desdobra/motor/desdobra/marca/perfil.py'),
    ('Bash', 'cd plugins/desdobra && python -m pytest -p no:cacheprovider testes/test_marca_perfil.py'),
    ('Bash', 'echo marcas da agencia > notas.txt'),
    ('Bash', 'echo x > docs/marcas.md'),
    ('Bash', 'ls plugins/desdobra/motor/desdobra/marca'),
    ('PowerShell', 'Get-ChildItem plugins\\desdobra\\motor\\schemas\\perfil-marca-1.json'),
    ('Bash', 'python -m pytest -p no:cacheprovider testes/test_marca_perfil.py -k marcas 2>&1 | tail -5'),
    ('Bash', 'git diff -- docs/marcas.md > /tmp/marcas.diff'),
    ('Bash', 'echo as marcas > notas.txt'),
]


@pytest.mark.parametrize('padrao', ['marc*', 'm?rcas', '*', 'marcas*'])
def test_gancho_nega_apagar_marcas_por_curinga(g, tmp_path, padrao):
    """Revisao do M2: o curinga que cai na biblioteca de marcas (rm -rf <bib>/marc*) e conferido pelo que existe."""
    bib = tmp_path / 'bib'
    (bib / 'marcas' / ID).mkdir(parents=True)
    for comando in ('rm -rf %s/%s' % (bib.as_posix(), padrao), 'rm -rf %s' % padrao):
        decisao, motivo = _decidir(g, 'Bash', {'command': comando}, bib)
        assert decisao == 'deny', comando
        assert motivo == g.MOTIVO_MARCA


def test_gancho_nega_escrita_por_ligacao_para_marcas_pelo_terminal(g, tmp_path):
    marcas = tmp_path / 'biblioteca' / 'marcas'
    marcas.mkdir(parents=True)
    atalho = tmp_path / 'atalho'
    try:
        atalho.symlink_to(marcas, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip('sem permissao para criar ligacao simbolica nesta maquina')
    assert _decidir(g, 'Bash', {'command': 'rm -rf %s' % atalho.as_posix()}, tmp_path)[0] == 'deny'
    assert _decidir(g, 'Bash', {'command': 'echo x > atalho/x.json'}, tmp_path)[0] == 'deny'


@pytest.mark.parametrize('rel', ['marcas./%s/x.json' % ID, 'marcas. /x.json', 'MARCAS../x.json'])
def test_gancho_nega_ferramenta_de_arquivo_em_marcas_com_ponto_no_fim(g, tmp_path, rel):
    """Revisao do M2: marcas. sem a pasta existir ainda (o alvo real nao ajuda)."""
    caminho = (tmp_path / 'nova-biblioteca').as_posix() + '/' + rel
    assert _decidir(g, 'Write', {'file_path': caminho, 'content': '{}'}, tmp_path)[0] == 'deny'


@pytest.mark.parametrize('ferramenta,comando', COMANDOS_LIVRES)
def test_gancho_deixa_o_codigo_e_os_testes_da_marca(g, tmp_path, ferramenta, comando):
    assert _decidir(g, ferramenta, {'command': comando}, tmp_path) == (None, None)


@pytest.mark.parametrize('rel', ['plugins/desdobra/motor/desdobra/marca/perfil.py',
                                 'plugins/desdobra/motor/desdobra/marca/__init__.py',
                                 'plugins/desdobra/motor/schemas/perfil-marca-1.json',
                                 'plugins/desdobra/testes/test_marca_perfil.py', 'docs/marcas.md'])
def test_gancho_deixa_editar_o_codigo_fonte_da_marca(g, tmp_path, rel):
    assert _decidir(g, 'Write', {'file_path': str(tmp_path / rel), 'content': 'x'}, tmp_path) == (None, None)


def test_arquivos_do_da_tem_o_perfil_de_marca(g):
    assert g.ARQUIVOS_DO_DA.search('biblioteca/marcas/%s/perfil-marca.json' % ID)
    assert not g.ARQUIVOS_DO_DA.search('motor/schemas/perfil-marca-1.json')


def test_motivo_da_marca_manda_o_da_a_tela_sem_terminal(g):
    texto = g.MOTIVO_MARCA
    assert 'tela do desdobra' in texto and 'terminal' not in texto.lower()
    assert '\u2014' not in texto and '\u2013' not in texto
