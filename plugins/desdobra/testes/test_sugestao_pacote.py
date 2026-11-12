# -*- coding: utf-8 -*-
"""Pacote para o modelo (pacote-modelo/2) por modo de dados, refeito quando o modo ou o PSD muda (M7c, S2)."""
import json

import pytest

from conftest import escolher_modo_do_da
from desdobra import contratos
from desdobra.job import modo_dados
from desdobra.sugestao import pacote
from test_sugestao_apoio import (ARQUIVO_CLIENTE, CAMINHO_CLIENTE, FONTE_PS, camada, laudo, laudo_cheio_de_conteudo,
                                 segredos_falsos)


def _estado(modo, teto=None):
    return {'esquema': 'estado/1', 'job_id': '0' * 32, 'criado_em': '2026-10-29T10:00:00-03:00',
            'atualizado_em': '2026-10-29T10:00:00-03:00', 'motor_versao': '0.1.0', 'modo_dados': modo,
            'teto_modo_dados': teto, 'entradas': {}, 'fases': {},
            'proxima': {'tipo': 'concluido', 'fase': None, 'o_que_fazer': 'nada'}}


@pytest.mark.parametrize('modo', ['a', 'b', 'c'])
def test_pacote_valida_e_nunca_leva_segredo(modo):
    la, _, falsos = laudo_cheio_de_conteudo()
    p, achados = pacote.montar_pacote(la, modo, job_id='0' * 32)
    contratos.validar(p, 'pacote-modelo/2')
    bruto = json.dumps(p, ensure_ascii=False)
    for s in falsos:
        assert s not in bruto
    assert len(achados) == 2 * len(falsos) == p['contagens']['segredos_bloqueados']
    bloqueadas = [c for c in p['camadas'] if c.get('segredo_bloqueado')]
    assert len(bloqueadas) == 2 * len(falsos)
    assert all('nome' not in c and 'textos' not in c for c in bloqueadas)
    assert p['miniaturas'] == [] and p['exposto']['miniaturas'] is False
    assert ARQUIVO_CLIENTE not in bruto and CAMINHO_CLIENTE not in bruto


def test_modo_c_so_contagens_estados_e_ids():
    la, textos, _ = laudo_cheio_de_conteudo()
    p, _ = pacote.montar_pacote(la, 'c')
    bruto = json.dumps(p, ensure_ascii=False)
    for t in textos:
        assert t not in bruto
    assert 'fontes_usadas' not in p and p['exposto'] == {'metadados': False, 'textos': False, 'miniaturas': False}
    assert set(p['camadas'][0]) <= {'layer_id', 'pai_id', 'tipo', 'situacao', 'regras', 'segredo_bloqueado'}


def test_modo_b_leva_metadados_e_textos():
    la, _, _ = laudo_cheio_de_conteudo()
    p, _ = pacote.montar_pacote(la, 'b')
    por_id = {c['layer_id']: c for c in p['camadas']}
    assert por_id[2]['textos'] == ['Promoção Fictícia Lilás'] and por_id[2]['nome']
    assert por_id[4]['regras'] == ['D8'] and por_id[6]['pai_id'] == 5
    assert p['fontes_usadas'][0]['fonte_ps']


def test_esquema_recusa_nome_no_modo_c():
    la = laudo([camada(1, 'Fundo Ficticio')])
    p, _ = pacote.montar_pacote(la, 'c')
    p['camadas'][0]['nome'] = 'Fundo Ficticio'
    with pytest.raises(contratos.ErroContrato):
        contratos.validar(p, 'pacote-modelo/2')


def test_coberta_no_kv_leva_so_a_sugestao_citada():
    cob = {'coberta': True, 'fracao_coberta': 1.0, 'ocupa_canvas': True, 'fracao_canvas': 1.0, 'limites': [],
           'sugestao_da_regra': {'funcao': 'estrutura', 'regra': 'decisao-10',
                                 'fonte': {'arquivo': 'decisoes-v1.md', 'secao': '29/10, 10'}}}
    p, _ = pacote.montar_pacote(laudo([camada(1, 'Fundo', tipo='cor_solida', coberta=cob)]), 'b')
    assert p['camadas'][0]['coberta_no_kv'] == {'coberta': True, 'ocupa_canvas': True,
                                                 'sugestao_da_regra': {'funcao': 'estrutura', 'regra': 'decisao-10'}}


def test_gravar_pacote_respeita_o_teto_do_job(tmp_path):
    la, textos, falsos = laudo_cheio_de_conteudo()
    try:
        contratos.validar(la, 'laudo/1')
    except contratos.ErroContrato as e:
        pytest.fail('o laudo sintetico deixou de valer contra laudo/1: %s' % e)
    contratos.gravar(tmp_path / 'estado.json', _estado('a', teto='c'), 'estado/1')
    contratos.gravar(tmp_path / 'laudo' / 'laudo.json', la, 'laudo/1')
    destino, n = pacote.gravar_pacote(tmp_path)
    p = contratos.ler(destino, 'pacote-modelo/2')
    assert p['modo_dados'] == 'c' and n == 2 * len(falsos)
    bruto = destino.read_text(encoding='utf-8')
    for t in textos + falsos:
        assert t not in bruto
    assert (tmp_path / 'sugestoes' / 'segredos-bloqueados.json').is_file()


def test_conteudo_para_resultado():
    la = laudo([camada(1, 'A'), camada(2, 'B', tipo='texto', texto='Olá')])
    assert pacote.conteudo_para_resultado(la) == {'camadas': [
        {'layer_id': 1, 'nome': 'A', 'tipo': 'pixel', 'situacao': 'lida', 'textos': []},
        {'layer_id': 2, 'nome': 'B', 'tipo': 'texto', 'situacao': 'lida', 'textos': ['Olá']}]}


# ------------------------------------------------------------------ pacote-modelo/2 (M7c, S2)
MINI = [{'layer_id': 1, 'sha256': 'c' * 64}]


def test_esquema_2_so_aceita_miniatura_no_modo_a():
    la = laudo([camada(1, 'Fundo Ficticio')])
    p, _ = pacote.montar_pacote(la, 'a', miniaturas=MINI)
    assert p['miniaturas'] == ['sugestoes/miniaturas/1.png'] and p['exposto']['miniaturas'] is True
    contratos.validar(p, 'pacote-modelo/2')
    for ruim in (['laudo/miniaturas/1.png'], ['sugestoes/miniaturas/../kv.png'], ['sugestoes/miniaturas/idx3.png']):
        with pytest.raises(contratos.ErroContrato):
            contratos.validar(dict(p, miniaturas=ruim), 'pacote-modelo/2')
    for modo in ('b', 'c'):
        q, _ = pacote.montar_pacote(la, modo, miniaturas=MINI)
        assert q['miniaturas'] == [] and q['exposto']['miniaturas'] is False
        with pytest.raises(contratos.ErroContrato):
            contratos.validar(dict(q, miniaturas=['sugestoes/miniaturas/1.png']), 'pacote-modelo/2')
        with pytest.raises(contratos.ErroContrato):
            contratos.validar(dict(q, exposto=dict(q['exposto'], miniaturas=True)), 'pacote-modelo/2')


@pytest.mark.parametrize('modo', ['a', 'b', 'c'])
def test_sem_a_nota_do_m1(modo):
    p, _ = pacote.montar_pacote(laudo([camada(1, 'Fundo')]), modo)
    assert 'nota' not in p and 'Rascunho' not in json.dumps(p, ensure_ascii=False)


def test_pacote_1_de_job_antigo_continua_legivel(tmp_path):
    p, _ = pacote.montar_pacote(laudo([camada(1, 'Fundo')]), 'b')
    antigo = dict(p, esquema='pacote-modelo/1', nota='Rascunho antigo.')
    contratos.gravar(tmp_path / 'pacote-modelo.json', antigo, 'pacote-modelo/1')
    assert pacote.ler_pacote(tmp_path / 'pacote-modelo.json')['esquema'] == 'pacote-modelo/1'


# ------------------------------------------------------------------ job falso com laudo e miniaturas do leitor
OFERTA = 'Oferta Ficticia Ametista'


def _job_falso(tmp_path, la, modo=None, teto=None, pngs=()):
    job = tmp_path / 'job'
    estado = _estado(None, teto)
    estado['entradas'] = {'entrada/kv.psd': {'sha256': la['origem']['sha256'], 'bytes': 1234,
                                             'congelada_em': '2026-10-29T10:00:00-03:00'}}
    contratos.gravar(job / 'estado.json', estado, 'estado/1')
    contratos.gravar(job / 'laudo' / 'laudo.json', la, 'laudo/1')
    for lid in pngs:
        arq = job / 'laudo' / 'miniaturas' / ('%d.png' % lid)
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_bytes(b'png-sintetico-%d' % lid)
    if modo is not None:
        escolher_modo_do_da(job, modo)
    return job


def _laudo_misto():
    falso = segredos_falsos()['chave de acesso da AWS']
    la = laudo([camada(1, 'Fundo Ficticio Turquesa'), camada(2, 'Titulo Ficticio', tipo='texto', texto=OFERTA),
                camada(3, 'Logo %s' % falso), camada(4, 'Oculta Ficticia', visivel=False)])
    return la, falso


def _textos_do_claude(job):
    """Tudo o que o Claude pode ler em sugestoes/ (o gancho deixa), como texto."""
    pasta = job / 'sugestoes'
    if not pasta.exists():
        return ''
    return '\n'.join(p.read_bytes().decode('utf-8', 'replace') for p in sorted(pasta.rglob('*'))
                     if p.is_file() and p.name != 'segredos-bloqueados.json')


def _eventos(job):
    arq = job / 'log' / 'eventos.jsonl'
    return [json.loads(x) for x in arq.read_text(encoding='utf-8').splitlines()] if arq.is_file() else []


def test_gravar_pacote_no_modo_a_lista_so_as_miniaturas_do_indice(tmp_path):
    la, falso = _laudo_misto()
    job = _job_falso(tmp_path, la, 'a', pngs=(1, 2, 3, 4))
    destino, n = pacote.gravar_pacote(job)
    p = contratos.ler(destino, 'pacote-modelo/2')
    assert p['modo_dados'] == 'a' and n == 1
    assert p['miniaturas'] == ['sugestoes/miniaturas/1.png'] and p['exposto']['miniaturas'] is True
    indice = json.loads((job / 'sugestoes' / 'miniaturas' / 'indice.json').read_text(encoding='utf-8'))
    assert [i['layer_id'] for i in indice['miniaturas']] == [1]
    assert sorted(x.name for x in (job / 'sugestoes' / 'miniaturas').iterdir()) == ['1.png', 'indice.json']
    # o registro do que foi exposto: so layer_id, sha256 e modo
    ev = [e for e in _eventos(job) if e['evento'] == 'pacote_modelo_exposto'][-1]
    assert ev['modo'] == 'a' and ev['miniaturas'] == indice['miniaturas']
    assert set(ev) <= {'quando', 'evento', 'modo', 'miniaturas', 'camadas', 'textos', 'segredos_bloqueados'}
    log = (job / 'log' / 'eventos.jsonl').read_text(encoding='utf-8')
    for termo in ('Fundo Ficticio', OFERTA, falso, 'Titulo Ficticio'):
        assert termo not in log
    assert falso not in _textos_do_claude(job)


@pytest.mark.parametrize('modo', ['b', 'c', None])
def test_gravar_pacote_fora_do_modo_a_nao_tem_a_pasta(tmp_path, modo):
    la, _ = _laudo_misto()
    job = _job_falso(tmp_path, la, modo, pngs=(1, 2))
    velha = job / 'sugestoes' / 'miniaturas' / '1.png'
    velha.parent.mkdir(parents=True)
    velha.write_bytes(b'de antes')
    destino, _ = pacote.gravar_pacote(job)
    p = contratos.ler(destino, 'pacote-modelo/2')
    assert p['modo_dados'] == (modo or 'c') and p['miniaturas'] == [] and p['exposto']['miniaturas'] is False
    assert not (job / 'sugestoes' / 'miniaturas').exists()
    ev = [e for e in _eventos(job) if e['evento'] == 'pacote_modelo_exposto'][-1]
    assert ev['modo'] == (modo or 'c') and ev['miniaturas'] == []


def test_teto_da_linha_de_comando_fecha_o_pacote(tmp_path):
    la, _ = _laudo_misto()
    job = _job_falso(tmp_path, la, 'a', pngs=(1,))
    pacote.gravar_pacote(job)
    destino, _ = pacote.gravar_pacote(job, teto='b')
    assert contratos.ler(destino, 'pacote-modelo/2')['modo_dados'] == 'b'
    assert not (job / 'sugestoes' / 'miniaturas').exists()


def _escrito_pelo_claude(job):
    for nome in ('sugestoes.json', 'sugestoes-validadas.json', 'mapeamento-specs.json'):
        (job / 'sugestoes' / nome).write_text(json.dumps({'texto': OFERTA}), encoding='utf-8')


def test_cair_para_c_apaga_o_que_o_claude_escreveu(tmp_path):
    la, _ = _laudo_misto()
    job = _job_falso(tmp_path, la, 'a', pngs=(1,))
    pacote.gravar_pacote(job)
    _escrito_pelo_claude(job)
    # em (b) as sugestoes ficam (o S3 recusa as de pacote velho)
    r = pacote.refazer_pacotes(job, teto='b')
    assert r['modo'] == 'b' and (job / 'sugestoes' / 'sugestoes.json').is_file()
    r = pacote.refazer_pacotes(job, teto='c')
    assert r['modo'] == 'c' and r['sugestoes_apagadas'] == 3
    for nome in ('sugestoes.json', 'sugestoes-validadas.json', 'mapeamento-specs.json'):
        assert not (job / 'sugestoes' / nome).exists()
    texto = _textos_do_claude(job)
    for termo in ('Fundo Ficticio', OFERTA, 'Titulo Ficticio', 'Oculta Ficticia', FONTE_PS):
        assert termo not in texto
    assert contratos.ler(job / 'sugestoes' / 'pacote-modelo.json', 'pacote-modelo/2')['modo_dados'] == 'c'


def test_conferir_modo_refaz_so_quando_o_modo_muda(tmp_path):
    la, _ = _laudo_misto()
    job = _job_falso(tmp_path, la, 'a', pngs=(1,))
    pacote.gravar_pacote(job)
    assert pacote.conferir_modo(job, 'a') is False
    assert (job / 'sugestoes' / 'miniaturas' / '1.png').is_file()
    # a agencia baixa o teto sem clique do DA: o pacote cai junto
    assert pacote.conferir_modo(job, 'b') is True
    assert contratos.ler(job / 'sugestoes' / 'pacote-modelo.json', 'pacote-modelo/2')['modo_dados'] == 'b'
    assert not (job / 'sugestoes' / 'miniaturas').exists()
    assert pacote.conferir_modo(job, 'b') is False


def test_conferir_modo_refaz_o_pacote_1_de_job_antigo(tmp_path):
    la, _ = _laudo_misto()
    job = _job_falso(tmp_path, la, 'b', pngs=(1,))
    p, _ = pacote.montar_pacote(la, 'b')
    contratos.gravar(job / 'sugestoes' / 'pacote-modelo.json', dict(p, esquema='pacote-modelo/1'), 'pacote-modelo/1')
    assert pacote.conferir_modo(job) is True
    assert contratos.ler(job / 'sugestoes' / 'pacote-modelo.json', 'pacote-modelo/2')['modo_dados'] == 'b'


def test_kv_trocado_antes_da_releitura_fecha_o_que_o_claude_le(tmp_path):
    la, _ = _laudo_misto()
    job = _job_falso(tmp_path, la, 'a', pngs=(1,))
    pacote.gravar_pacote(job)
    _escrito_pelo_claude(job)
    estado = contratos.ler(job / 'estado.json', 'estado/1')
    estado['entradas']['entrada/kv.psd']['sha256'] = 'cd' * 32
    contratos.gravar(job / 'estado.json', estado, 'estado/1')
    # o laudo e do KV antigo: nada do pacote velho fica legivel ate a fase ler rodar de novo, nem as sugestoes de
    # funcao feitas sobre ele; a proposta das specs nao depende do KV e fica
    assert pacote.conferir_modo(job, 'a') is True
    assert not (job / 'sugestoes' / 'pacote-modelo.json').exists()
    assert not (job / 'sugestoes' / 'miniaturas').exists()
    assert not (job / 'sugestoes' / 'sugestoes.json').exists()
    assert not (job / 'sugestoes' / 'sugestoes-validadas.json').exists()
    assert (job / 'sugestoes' / 'mapeamento-specs.json').is_file()
    assert pacote.conferir_modo(job, 'a') is False


def test_conferir_modo_que_falha_fecha_tudo(tmp_path, monkeypatch):
    la, _ = _laudo_misto()
    job = _job_falso(tmp_path, la, 'a', pngs=(1,))
    pacote.gravar_pacote(job)

    def quebra(*_a, **_k):
        raise OSError('disco')
    monkeypatch.setattr(pacote, 'gravar_pacote', quebra)
    assert pacote.conferir_modo(job, 'b') is True
    assert _textos_do_claude(job) == ''


def test_refazer_pacotes_refaz_tambem_o_pacote_das_specs(tmp_path):
    import test_specs_apoio as apoio
    from conftest import psd_minimo
    from desdobra.job import nucleo
    from desdobra.specs import importar
    origem = tmp_path / 'origem-specs' / 'globo'
    origem.mkdir(parents=True)
    (origem / 'vertical.html').write_text(apoio.html_vertical(), encoding='utf-8')
    (tmp_path / 'kv.psd').write_bytes(psd_minimo())
    job = tmp_path / 'job'
    nucleo.criar(job, tmp_path / 'kv.psd', specs=tmp_path / 'origem-specs')
    escolher_modo_do_da(job, 'a')
    importar.importar(job)
    antes = contratos.ler(job / 'sugestoes' / 'pacote-specs.json', 'pacote-specs/1')
    assert antes['exposto']['textos'] and antes['trechos']
    r = pacote.refazer_pacotes(job, teto='c')
    depois = contratos.ler(job / 'sugestoes' / 'pacote-specs.json', 'pacote-specs/1')
    assert r['pacote_specs'] == 1 and depois['modo_dados'] == 'c'
    assert depois['trechos'] == [] and depois['folhas'] == [] and depois['alvos'] == []
    assert not depois['exposto']['textos']
    for t in antes['trechos']:
        assert t['texto'] not in _textos_do_claude(job)
    # sem laudo (a fase ler ainda nao rodou), nao ha pacote-modelo
    assert not (job / 'sugestoes' / 'pacote-modelo.json').exists()


# ------------------------------------------------------------------ o ato do modo na tela refaz os pacotes
@pytest.fixture
def _ato_modo(monkeypatch):
    """O ato do modo como o servidor da tela o roda depois do "Confirmar" do DA, num job sintetico. O processo do
    teste roda sob o Claude: como em test_tela_salvar.py, o ambiente da tela e simulado."""
    from desdobra import humano
    from desdobra.tela import atos
    monkeypatch.setattr(humano, 'ambiente_da_tela', lambda: (True, None))

    def rodar(job, modo, teste=False, teto=None):
        ato = atos.atos_do_job(job, teto=teto)['modo_dados']
        disparo = humano.exigir_tela(modo_dados.ESCOLHER, humano.abrir_sessao_tela(teste=teste), confirmado=True)
        return ato.executar(disparo, {'modo': modo})
    return rodar


def test_ato_do_modo_refaz_os_pacotes(tmp_path, _ato_modo):
    la, _ = _laudo_misto()
    job = _job_falso(tmp_path, la, None, pngs=(1, 2))
    pacote.gravar_pacote(job)
    assert not (job / 'sugestoes' / 'miniaturas').exists()
    assert _ato_modo(job, 'a') == {'modo': 'a'}
    assert contratos.ler(job / 'sugestoes' / 'pacote-modelo.json', 'pacote-modelo/2')['modo_dados'] == 'a'
    assert (job / 'sugestoes' / 'miniaturas' / '1.png').is_file()
    _escrito_pelo_claude(job)
    assert _ato_modo(job, 'c') == {'modo': 'c'}
    assert not (job / 'sugestoes' / 'miniaturas').exists()
    assert not (job / 'sugestoes' / 'sugestoes.json').exists()
    assert OFERTA not in _textos_do_claude(job)


def test_ato_do_modo_de_teste_nunca_abre_as_miniaturas(tmp_path, _ato_modo):
    la, _ = _laudo_misto()
    job = _job_falso(tmp_path, la, None, pngs=(1,))
    _ato_modo(job, 'a', teste=True)
    assert contratos.ler(job / 'sugestoes' / 'pacote-modelo.json', 'pacote-modelo/2')['modo_dados'] == 'c'
    assert not (job / 'sugestoes' / 'miniaturas').exists()


def test_ato_do_modo_respeita_o_teto_da_tela(tmp_path, _ato_modo):
    la, _ = _laudo_misto()
    job = _job_falso(tmp_path, la, 'a', pngs=(1,))
    pacote.gravar_pacote(job)
    _ato_modo(job, 'b', teto='b')
    assert not (job / 'sugestoes' / 'miniaturas').exists()
