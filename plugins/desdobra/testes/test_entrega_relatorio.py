# -*- coding: utf-8 -*-
"""Relatorio da entrega, manifesto de licenca e encoder no doctor (M6, fatias 5 e 9 da proposta; arquitetura-v1.md, 5.8,
5.9 e 9.7; decisoes-v1.md, arquitetura nº 19 e 136 a 143), com imagens e contextos sinteticos (rotulos KV A, sem
conteudo de cliente).

Criterios de pronto cobertos aqui (arquitetura-v1.md, 9.7):
  - relatorio sem numero sem fonte: todo numero esta numa verificacao com fonte, numa citacao de limite
    (limites.obter(id).citacao()) ou num campo de fontes_dos_campos; numero sem fonte enfiado no relatorio e pego em
    100% das mutacoes, e o relatorio() recusa gravar com um;
  - o relatorio grava as versoes do encoder (Pillow, libjpeg-turbo, zlib) contra a build de referencia, a escolha entre
    PNG e JPEG, a qualidade escolhida e o aviso de piso de qualidade (a calibrar: so registra sem valor, so avisa com
    valor, nunca manda para reprovados);
  - a aprovacao de cada formato (registro e campos que mudaram desde ela) e o que mudou por formato desde a entrega
    anterior;
  - resumo em portugues para a skill: o que passou, o que avisou e o que ficou so como registro;
  - manifesto-licenca.json na raiz do job, nunca em entrega/aprovados, sem campo de licenca (nº 19); o conferir-entrega
    pega o manifesto apagado ou mexido;
  - doctor: falha so com o libimagequant ou sem JPEG; outra build so avisa.

A gravacao da entrega so parte de uma pessoa: o console e simulado pelo fixture pessoa (o caminho do Disparo e o de
verdade).
"""
import copy
import dataclasses
import json

import pytest

import test_entrega_validar as tv
from desdobra import arquivos, contratos, humano, limites
from desdobra.doctor import verificacoes as dv
from desdobra.entrega import aprovacao, codificar, validar
from desdobra.entrega import relatorio as mr

JOB = 'j' * 32
H = {'briefing_sha256': 'b' * 64, 'master_sha256': 'c' * 64, 'render_json_sha256': 'd' * 64, 'contrato_sha256': 'e' * 64}
CAMPOS_DE_LICENCA = ('canal', 'eula', 'kit_web', 'fstype', 'restricao', 'desktop', 'titular', 'usuarios', 'comprovante',
                     'licenca_')


def _itens(casos, origem=None):
    itens = tv._itens_de(casos)
    for it in itens:
        it['origem'] = dict(origem or H)
        it['render'] = {'versoes': {'chromium': 'x', 'playwright': 'y', 'pypdfium2': 'z', 'pdfium': 'w'},
                        'fontes_sha256': ['f' * 64]}
    return itens


def _rel(itens, **k):
    return validar.relatorio(itens, JOB, _disparo(), **k)


class _Quem:
    """So o registro de quem entregou (o relatorio nao confere o disparo; o gravar confere)."""

    def registro(self):
        return dict(tv.QUEM)


def _disparo():
    return _Quem()


def _limpos():
    return [tv._limpo(1), tv._limpo(2, jpeg=True), tv._byte_acima()]


# ------------------------------------------------------------------ nenhum numero sem fonte
def test_relatorio_nao_tem_numero_sem_fonte():
    rel = _rel(_itens(_limpos()))
    assert mr.numeros_sem_fonte(rel) == []
    contratos.validar(rel, validar.ESQUEMA)
    # todo limite da entrega e citado pelo id, com fonte
    citados = {c['limite_id'] for c in rel['limites']}
    assert {i for i in limites.carregar() if i.startswith('entrega.')} <= citados
    assert all(c['fonte'] for c in rel['limites'])


def _num_no_encoder(rel):
    rel['arquivos'][0]['parametros_encoder']['novo_numero'] = 7


def _num_no_ambiente(rel):
    rel['ambiente']['encoder']['numero'] = 2


def _verificacao_sem_fonte(rel):
    v = next(v for v in rel['arquivos'][0]['verificacoes'] if v['nome'] == 'peso')
    v['fonte'] = None


def _citacao_sem_id(rel):
    """Um numero de limite sem o id e sem a fonte: deixa de ser citacao."""
    c = next(c for c in rel['limites'] if c['limite_id'] == 'entrega.jpeg_buffer_bytes')
    del c['limite_id'], c['fonte']


def _num_na_aprovacao(rel):
    rel['arquivos'][0]['origem']['n'] = 3


def _num_solto_no_topo(rel):
    rel['extra'] = 1.5


def _campo_tirado_das_fontes(rel):
    rel['fontes_dos_campos'].pop('arquivos[].bytes')


MUTACOES_NUMERO = [_num_no_encoder, _num_no_ambiente, _verificacao_sem_fonte, _citacao_sem_id, _num_na_aprovacao,
                   _num_solto_no_topo, _campo_tirado_das_fontes]


@pytest.mark.parametrize('mexer', MUTACOES_NUMERO, ids=[m.__name__ for m in MUTACOES_NUMERO])
def test_numero_sem_fonte_e_pego(mexer):
    rel = _rel(_itens(_limpos()))
    mexer(rel)
    assert mr.numeros_sem_fonte(rel)


def test_mutacoes_de_numero_sem_fonte_detectadas_em_100_por_cento():
    base = _rel(_itens(_limpos()))
    detectadas = 0
    for mexer in MUTACOES_NUMERO:
        rel = copy.deepcopy(base)
        mexer(rel)
        detectadas += bool(mr.numeros_sem_fonte(rel))
    assert detectadas == len(MUTACOES_NUMERO)


def test_relatorio_recusa_numero_sem_fonte(monkeypatch):
    itens = _itens(_limpos())
    itens[0]['verificacoes'].append({'nome': 'sem_fonte', 'situacao': 'ok', 'regra': None, 'fonte': None,
                                     'medidas': {'medida': 3}})
    with pytest.raises(validar.ErroEntrega) as e:
        _rel(itens)
    assert e.value.codigo == 'relatorio_com_numero_sem_fonte'
    assert e.value.medidas['caminhos'] == ['arquivos[].verificacoes[].medidas.medida']


# ------------------------------------------------------------------ encoder, escolha e qualidade
def test_relatorio_grava_a_build_do_encoder_a_escolha_e_a_qualidade():
    rel = _rel(_itens(_limpos()))
    enc = rel['ambiente']['encoder']
    assert set(enc['versoes']) == {'pillow', 'libjpeg_turbo', 'zlib'} and enc['versoes']['libjpeg_turbo']
    assert enc['referencia']['limite_id'] == 'entrega.encoder_build_referencia'
    assert enc['difere'] == codificar.build_difere()
    assert rel['ambiente']['render'] == {'versoes': [{'chromium': 'x', 'playwright': 'y', 'pypdfium2': 'z',
                                                       'pdfium': 'w'}], 'fontes_sha256': ['f' * 64]}
    png, jpg = rel['arquivos'][0], rel['arquivos'][1]
    v_png = {v['nome']: v for v in png['verificacoes']}
    v_jpg = {v['nome']: v for v in jpg['verificacoes']}
    assert v_png['escolha_do_tipo']['regra'] == 'png_sem_perda' and v_png['escolha_do_tipo']['situacao'] == 'registra'
    assert 'qualidade_jpeg' not in v_png
    assert v_jpg['escolha_do_tipo']['regra'] == 'jpeg'
    q = v_jpg['qualidade_jpeg']
    # sem valor no piso (a calibrar): a qualidade escolhida fica so como registro
    assert q['regra'] == 'piso_de_qualidade_a_calibrar' and q['situacao'] == 'registra'
    assert q['medidas']['qualidade'] == jpg['parametros_encoder']['qualidade']
    assert q['fonte']['limite']['limite_id'] == 'entrega.jpeg_qualidade_piso_aviso'


def _piso(monkeypatch, valor):
    original = limites.obter

    def obter(lid):
        lim = original(lid)
        return dataclasses.replace(lim, valor=valor) if lid == 'entrega.jpeg_qualidade_piso_aviso' else lim
    monkeypatch.setattr(limites, 'obter', obter)


def test_qualidade_abaixo_do_piso_so_avisa_e_nao_reprova(monkeypatch, tmp_path, pessoa):
    _piso(monkeypatch, 101)  # acima da qualidade maxima: todo JPEG fica abaixo do piso
    f, ctx = tv._limpo(2, jpeg=True)
    itens = _itens([(f, ctx)])
    q = next(v for v in itens[0]['verificacoes'] if v['nome'] == 'qualidade_jpeg')
    assert q['regra'] == 'qualidade_abaixo_do_piso' and q['situacao'] == 'avisa' and q['medidas']['piso'] == 101
    rel, _a = validar.gravar(tmp_path, itens, JOB, disparo=humano.exigir('entregar'))
    assert rel['arquivos'][0]['pasta'] == validar.APROVADOS
    assert rel['resumo']['avisos'] == {'qualidade_abaixo_do_piso': 1} and rel['resumo']['aprovados_sem_aviso'] == 0
    _piso(monkeypatch, 1)
    q = next(v for v in tv._itens_de([tv._limpo(2, jpeg=True)])[0]['verificacoes'] if v['nome'] == 'qualidade_jpeg')
    assert q['situacao'] == 'ok' and q['regra'] is None


# ------------------------------------------------------------------ aprovacao e entrega anterior
def _registro_aprovado(item, disparo):
    return aprovacao.registro(item['formato'], JOB, item['origem'], item['final'], disparo)


def test_relatorio_diz_a_aprovacao_e_o_que_mudou_por_formato(pessoa):
    # o registro de aprovacao so sai com o Disparo do "aprovar" (console simulado pelo fixture pessoa)
    disparo = pessoa.exigir('aprovar')
    itens = _itens(_limpos())
    for it in itens:
        it['aprovacao'] = _registro_aprovado(it, disparo)
    primeiro = _rel(itens)
    for a, it in zip(primeiro['arquivos'], itens):
        assert a['aprovacao'] == {'registro_sha256': it['aprovacao']['registro_sha256'], 'aprovado_em': disparo.quando,
                                  'diferencas': []}
        assert a['mudou_desde_a_entrega_anterior'] is None
    assert primeiro['entrega_anterior'] is None
    # segunda entrega: o master do primeiro formato mudou, o segundo saiu com outro arquivo, o terceiro e novo
    novos = _itens(_limpos())
    novos[0]['origem']['master_sha256'] = 'a' * 64
    novos[1]['final'] = tv._limpo(5, jpeg=True)[0]
    novos[2]['formato'] = 'kv-a-novo'
    segundo = _rel(novos, anterior=primeiro)
    mudou = [a['mudou_desde_a_entrega_anterior'] for a in segundo['arquivos']]
    assert mudou[0] == ['master_sha256']
    assert 'arquivo_entregue_sha256' in mudou[1] and 'master_sha256' not in mudou[1]
    assert mudou[2] == ['formato_novo']
    assert segundo['entrega_anterior'] == primeiro['carimbo']
    # a aprovacao velha contra o master novo: o campo aparece
    novos[0]['aprovacao'] = itens[0]['aprovacao']
    assert mr.aprovacao_do_arquivo(novos[0], JOB)['diferencas'] == ['master_sha256']


# ------------------------------------------------------------------ resumo em portugues
def test_resumo_em_portugues_diz_o_que_passou_avisou_e_ficou_so_como_registro():
    rel = _rel(_itens(_limpos()))
    r = rel['resumo']
    assert r['verificacoes']['reprovou'] >= 1 and r['verificacoes']['passou'] >= 1
    assert r['registros']['comparacao_com_aprovada_pendente'] == 3
    assert sum(r['verificacoes'].values()) == sum(len(a['verificacoes']) for a in rel['arquivos'])
    linhas = mr.linhas_do_resumo(rel)
    assert linhas[0].startswith('Passou: 2 de 3 arquivo(s) em entrega/aprovados')
    assert linhas[1] == 'Avisou: nada.'
    assert linhas[2].startswith('Só registro: ') and 'png_sem_perda (' in linhas[2]


# ------------------------------------------------------------------ manifesto de licenca
def _entradas_com_fontes():
    return {'entrada/kv.psd': {'sha256': '1' * 64, 'bytes': 1, 'congelada_em': tv.QUEM['quando']},
                'entrada/fontes/inventada-a.ttf': {'sha256': '2' * 64, 'bytes': 1, 'congelada_em': tv.QUEM['quando']},
                'entrada/fontes/inventada-b.otf': {'sha256': '3' * 64, 'bytes': 1, 'congelada_em': tv.QUEM['quando']}}


def test_manifesto_na_raiz_do_job_sem_campo_de_licenca(tmp_path, pessoa, monkeypatch):
    entradas = _entradas_com_fontes()
    original = contratos.ler
    monkeypatch.setattr(contratos, 'ler', lambda arq, esq: {'entradas': entradas} if esq == 'estado/1'
                        else original(arq, esq))
    rel, _a = validar.gravar(tmp_path, _itens(_limpos()), JOB, disparo=humano.exigir('entregar'))
    arq = tmp_path / mr.ARQUIVO_MANIFESTO
    man = original(arq, mr.ESQUEMA_MANIFESTO)
    assert [a['nome'] for a in man['arquivos']] == ['inventada-a.ttf', 'inventada-b.otf']
    assert [a['formato'] for a in man['arquivos']] == ['ttf', 'otf']
    assert man['arquivos'][0]['sha256'] == '2' * 64 and man['responsabilidade'] == mr.FRASE_RESPONSABILIDADE
    assert rel['manifesto_sha256'] == mr.selo_manifesto(man)
    # nunca dentro de entrega/ (nem de aprovados/)
    assert not list((tmp_path / 'entrega').rglob(mr.ARQUIVO_MANIFESTO.name))
    assert validar.conferir_entrega(tmp_path)['ok']


def test_esquema_do_manifesto_nao_tem_campo_de_licenca():
    esquema = json.loads((contratos.PASTA_ESQUEMAS / 'manifesto-licenca-1.json').read_text(encoding='utf-8'))
    nomes = set()

    def andar(no):
        if isinstance(no, dict):
            nomes.update((no.get('properties') or {}).keys())
            for v in no.values():
                andar(v)
        elif isinstance(no, list):
            for v in no:
                andar(v)
    andar(esquema)
    assert not [n for n in nomes for proibido in CAMPOS_DE_LICENCA if proibido in n.lower()]
    assert esquema['additionalProperties'] is False


def _manifesto_apagado(pasta):
    (pasta / mr.ARQUIVO_MANIFESTO).unlink()


def _manifesto_mexido(pasta):
    arq = pasta / mr.ARQUIVO_MANIFESTO
    d = arquivos.ler_json(arq)
    d['arquivos'].append({'nome': 'outra.ttf', 'sha256': '9' * 64, 'formato': 'ttf', 'faces': []})
    arquivos.gravar_json_atomico(arq, d)


def _manifesto_invalido(pasta):
    arq = pasta / mr.ARQUIVO_MANIFESTO
    d = arquivos.ler_json(arq)
    d['canal'] = 'web'
    arquivos.gravar_json_atomico(arq, d)


MUTACOES_MANIFESTO = [(_manifesto_apagado, 'sem_manifesto'), (_manifesto_mexido, 'manifesto_diferente'),
                      (_manifesto_invalido, 'manifesto_invalido')]


def test_mutacoes_do_manifesto_detectadas_em_100_por_cento(tmp_path, pessoa):
    detectadas = 0
    for k, (mexer, motivo) in enumerate(MUTACOES_MANIFESTO):
        pasta = tmp_path / ('m%02d' % k)
        validar.gravar(pasta, _itens(_limpos()), JOB, disparo=humano.exigir('entregar'))
        assert validar.conferir_entrega(pasta)['ok']
        mexer(pasta)
        s = validar.conferir_entrega(pasta)
        assert s['manifesto'] == motivo
        detectadas += not s['ok']
    assert detectadas == len(MUTACOES_MANIFESTO)


# ------------------------------------------------------------------ doctor: o encoder da entrega
def _recursos(**troca):
    r = {'jpeg': True, 'libimagequant': False, 'versoes': codificar.build_de_referencia()}
    r.update(troca)
    return r


@pytest.mark.parametrize('troca, situacao', [
    ({}, 'ok'),
    ({'libimagequant': True}, 'falha'),
    ({'jpeg': False}, 'falha'),
    ({'versoes': dict(codificar.build_de_referencia(), libjpeg_turbo='9.9.9')}, 'aviso'),
    ({'versoes': dict(codificar.build_de_referencia(), zlib='1.0.0')}, 'aviso'),
    ({'versoes': dict(codificar.build_de_referencia(), pillow='1.0.0')}, 'aviso'),
    ({'versoes': dict(codificar.build_de_referencia(), libjpeg_turbo=None)}, 'aviso'),
])
def test_doctor_falha_so_com_libimagequant_ou_sem_jpeg(troca, situacao):
    v = dv.verificar_encoder(_recursos(**troca))
    assert v.situacao == situacao, v.detalhe
    assert (v.o_que_fazer is None) == (situacao == 'ok')
    assert v.limite['limite_id'] == 'entrega.encoder_build_referencia'


def test_doctor_desta_build_e_o_encoder_no_doctor():
    from desdobra import doctor
    r = dv.recursos_do_pillow()
    assert r['jpeg'] and set(r['versoes']) == {'pillow', 'libjpeg_turbo', 'zlib'}
    v = dv.verificar_encoder()
    assert v.situacao in ('ok', 'aviso', 'falha') and ('libimagequant' in v.detalhe)
    lista, _sem = doctor.rodar_verificacoes('c', None, com_isolador=False, com_chromium=False)
    assert 'encoder_entrega' in [x.id for x in lista]
