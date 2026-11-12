# -*- coding: utf-8 -*-
"""Miniaturas permitidas do modo (a) (decisoes-v1.md, 190, Q7; arquitetura-v1.md, 4.9 e 7.4).

So entram imagens de camadas sem texto. Ficam de fora o grupo, o smart object com texto dentro, linkado ou nao
aberto, a camada escondida, a camada recortada sobre texto (e a base dela) e o arquivo de layer_id repetido. Na
duvida, a camada fica de fora. Tudo em laudos e PSD sinteticos."""
import hashlib
import json

import pytest

import sinteticos
from desdobra import leitor, plataforma
from desdobra.sugestao import miniaturas as mm
from test_sugestao_apoio import valor_rotulado


# ------------------------------------------------------------------ laudo/1 sintetico, so com o que a regra le
def cam(lid, tipo='pixel', pai_id=None, visivel=True, clipping=False, texto=None, ajuste=None, smart=None, nome=None):
    return {'identidade': {'arquivo_sha256': '0' * 64, 'layer_id': lid}, 'nome': nome or 'camada-%s' % lid,
            'tipo': tipo, 'pai_id': pai_id, 'caminho_ids': [] if pai_id is None else [pai_id],
            'aparencia': {'visivel_efetiva': visivel, 'clipping': clipping, 'ajuste': ajuste},
            'texto': None if texto is None else {'conteudo': texto, 'runs': [{'texto': texto}]},
            'smart_object': smart, 'situacao': 'lida', 'motivos': []}


def smart_aberto(n_textos=0, smart_objects=0):
    return {'embutido': True, 'abertura': {'situacao': 'aberto', 'profundidade': 1, 'pasta': None,
                                           'resumo': {'n_camadas': 2, 'n_textos': n_textos, 'fontes_ps': [],
                                                      'dims': [10, 10], 'previa_uniforme': False,
                                                      'smart_objects': smart_objects}}}


def laudo_de(*camadas):
    return {'esquema': 'laudo/1', 'camadas': list(camadas)}


def permitida(laudo, lid):
    alvo = [c for c in laudo['camadas'] if c['identidade']['layer_id'] == lid]
    assert alvo
    return all(mm.miniatura_permitida(c, laudo) for c in alvo)


@pytest.mark.parametrize('tipo', ['pixel', 'forma'])
def test_camada_folha_visivel_sem_texto_entra(tipo):
    laudo = laudo_de(cam(1, tipo))
    assert permitida(laudo, 1)
    assert mm.camadas_permitidas(laudo) == [1]


@pytest.mark.parametrize('tipo', ['texto', 'grupo', 'prancheta', 'ajuste', 'preenchimento', 'cor_solida', 'outro',
                                  'smart_linkado', None, 'tipo-que-ainda-nao-existe'])
def test_tipos_fora_da_lista_ficam_de_fora(tipo):
    assert not permitida(laudo_de(cam(1, tipo)), 1)


def test_pixel_com_textos_ou_ajuste_fica_de_fora():
    laudo = laudo_de(cam(1, texto='qualquer'), cam(2, ajuste={'tipo': 'curvas'}))
    assert not permitida(laudo, 1) and not permitida(laudo, 2)


def test_camada_invisivel_no_kv_fica_de_fora():
    assert not permitida(laudo_de(cam(1, visivel=False)), 1)


def test_grupo_fica_de_fora_e_a_folha_dentro_entra():
    laudo = laudo_de(cam(1, 'grupo'), cam(2, pai_id=1))
    assert not permitida(laudo, 1) and permitida(laudo, 2)


def test_camada_com_filhos_nao_e_folha():
    # um pixel que, pelo laudo, tem filhos (estrutura inesperada): na duvida, fora
    laudo = laudo_de(cam(1, 'pixel'), cam(2, pai_id=1))
    assert not permitida(laudo, 1)


@pytest.mark.parametrize('smart,entra', [
    # so pelo laudo, sem a estrutura interna gravada pelo leitor, o smart object fica de fora (na duvida)
    (smart_aberto(), False),
    (smart_aberto(n_textos=1), False),
    (smart_aberto(smart_objects=1), False),
    ({'embutido': True, 'abertura': {'situacao': 'nao_aberto', 'motivo': 'x'}}, False),
    ({'embutido': True, 'abertura': {'situacao': 'recusado', 'recusa': 'x', 'motivo': 'x'}}, False),
    ({'embutido': True, 'abertura': None}, False),
    ({'embutido': True, 'abertura': {'situacao': 'aberto'}}, False),
    ({'embutido': True, 'abertura': {'situacao': 'aberto', 'resumo': {'n_textos': None, 'smart_objects': 0}}}, False),
    (None, False),
])
def test_smart_object_embutido_so_aberto_e_sem_texto(smart, entra):
    assert permitida(laudo_de(cam(1, 'smart_embutido', smart=smart)), 1) is entra


def test_smart_object_linkado_fica_de_fora_mesmo_com_abertura():
    smart = dict(smart_aberto(), embutido=False)
    assert not permitida(laudo_de(cam(1, 'smart_linkado', smart=smart)), 1)
    assert not permitida(laudo_de(cam(2, 'smart_embutido', smart=smart)), 2)


def test_recorte_sobre_texto_fica_de_fora_com_a_base():
    # ordem do laudo: de baixo para cima; o recorte vale sobre a camada sem recorte logo abaixo, entre irmas
    laudo = laudo_de(cam(1), cam(2, 'texto', texto='abc'), cam(3, clipping=True), cam(4, clipping=True), cam(5))
    assert permitida(laudo, 1) and permitida(laudo, 5)
    assert not permitida(laudo, 3) and not permitida(laudo, 4)


def test_base_de_recorte_de_um_texto_fica_de_fora():
    laudo = laudo_de(cam(1), cam(2, clipping=True), cam(3, 'texto', texto='abc', clipping=True), cam(4))
    assert not permitida(laudo, 1) and not permitida(laudo, 2) and not permitida(laudo, 3)
    assert permitida(laudo, 4)


def test_recorte_sobre_pixel_entra():
    laudo = laudo_de(cam(1), cam(2, clipping=True))
    assert permitida(laudo, 1) and permitida(laudo, 2)


def test_recorte_sobre_grupo_com_texto_dentro_fica_de_fora():
    laudo = laudo_de(cam(1, 'grupo'), cam(2, 'texto', pai_id=1, texto='abc'), cam(3, clipping=True))
    assert not permitida(laudo, 3)


def test_recorte_sobre_smart_object_com_texto_fica_de_fora():
    laudo = laudo_de(cam(1, 'smart_embutido', smart=smart_aberto(n_textos=1)), cam(2, clipping=True))
    assert not permitida(laudo, 2)


def test_recorte_so_vale_entre_irmas():
    # o texto dentro do grupo nao e base do recorte que esta fora dele
    # dentro do grupo 5: texto 6, pixel 7 e o 8 recortado sobre o 7. O texto fica abaixo da pilha 7-8
    laudo = laudo_de(cam(1), cam(5, 'grupo'), cam(6, 'texto', pai_id=5, texto='abc'), cam(7, pai_id=5),
                     cam(8, clipping=True, pai_id=5))
    assert permitida(laudo, 1) and permitida(laudo, 7) and permitida(laudo, 8)
    # fora do grupo, o recorte logo acima do grupo 5 tem o grupo (com texto dentro) como base
    laudo['camadas'].append(cam(9, clipping=True))
    assert not permitida(laudo, 9)
    # e a pilha 5-9 tem texto: o grupo base leva junto tudo o que esta dentro dele (na duvida, fora)
    assert not permitida(laudo, 7) and not permitida(laudo, 8)
    assert permitida(laudo, 1)


def test_layer_id_repetido_fica_de_fora():
    laudo = laudo_de(cam(1), cam(9), cam(9))
    assert permitida(laudo, 1) and not permitida(laudo, 9)
    assert mm.camadas_permitidas(laudo) == [1]


@pytest.mark.parametrize('lid', [0, -1, None, True, '3', 2.0])
def test_layer_id_invalido_fica_de_fora(lid):
    assert not permitida(laudo_de(cam(lid)), lid)


# ------------------------------------------------------------------ smart object: a estrutura interna do leitor
SHA_INTERNO = 'a' * 64


def smart_com_pasta(sha=SHA_INTERNO, **kw):
    s = smart_aberto(**kw)
    s['sha256'] = sha
    s['abertura']['pasta'] = 'bruto/%s' % sha
    return s


def _estrutura(pasta_laudo, kinds, sha=SHA_INTERNO, indice_smart=(), origem_sha=None):
    pasta = pasta_laudo / 'bruto' / sha
    pasta.mkdir(parents=True, exist_ok=True)
    est = {'esquema': 'estrutura/1', 'origem': {'sha256': origem_sha or sha, 'profundidade': 1},
           'indice_smart': list(indice_smart),
           'camadas': [{'layer_id': i + 1, 'nome': 'interna-%d' % i, 'kind': k} for i, k in enumerate(kinds)]}
    (pasta / 'estrutura.json').write_text(json.dumps(est), encoding='utf-8')
    return pasta_laudo


def _permitida_com_pasta(laudo, lid, pasta_laudo):
    alvo = [c for c in laudo['camadas'] if c['identidade']['layer_id'] == lid]
    assert alvo
    return all(mm.miniatura_permitida(c, laudo, pasta_laudo=pasta_laudo) for c in alvo)


@pytest.mark.parametrize('kinds,entra', [
    (['pixel'], True),
    (['pixel', 'shape', 'group'], True),
    (['pixel', 'smartobject'], False),
    (['pixel', 'type'], False),
    (['pixel', 'tipo-que-ainda-nao-existe'], False),
    (['pixel', None], False),
])
def test_smart_embutido_confere_a_estrutura_interna(tmp_path, kinds, entra):
    laudo = laudo_de(cam(1, 'smart_embutido', smart=smart_com_pasta()))
    _estrutura(tmp_path, kinds)
    assert _permitida_com_pasta(laudo, 1, tmp_path) is entra
    assert (mm.camadas_permitidas(laudo, pasta_laudo=tmp_path) == [1]) is entra


def test_smart_com_smart_interno_sem_registro_fica_de_fora(tmp_path):
    # o resumo do laudo conta so o indice de registros do PSB interno: uma camada smart sem registro da 0
    laudo = laudo_de(cam(1, 'smart_embutido', smart=smart_com_pasta(smart_objects=0)))
    _estrutura(tmp_path, ['pixel', 'smartobject'], indice_smart=[])
    assert not _permitida_com_pasta(laudo, 1, tmp_path)


def test_smart_com_indice_smart_na_estrutura_fica_de_fora(tmp_path):
    laudo = laudo_de(cam(1, 'smart_embutido', smart=smart_com_pasta()))
    _estrutura(tmp_path, ['pixel'], indice_smart=[{'unique_id': 'x'}])
    assert not _permitida_com_pasta(laudo, 1, tmp_path)


@pytest.mark.parametrize('pasta', [None, '', 'bruto/../fora', '../bruto/' + SHA_INTERNO, 'bruto/xyz', 'bruto/' + 'b' * 64])
def test_smart_com_pasta_estranha_ou_sem_estrutura_fica_de_fora(tmp_path, pasta):
    smart = smart_com_pasta()
    smart['abertura']['pasta'] = pasta
    _estrutura(tmp_path, ['pixel'])
    assert not _permitida_com_pasta(laudo_de(cam(1, 'smart_embutido', smart=smart)), 1, tmp_path)


def test_smart_com_estrutura_de_outro_arquivo_fica_de_fora(tmp_path):
    _estrutura(tmp_path, ['pixel'], origem_sha='c' * 64)
    assert not _permitida_com_pasta(laudo_de(cam(1, 'smart_embutido', smart=smart_com_pasta())), 1, tmp_path)


def test_smart_com_estrutura_ilegivel_fica_de_fora(tmp_path):
    _estrutura(tmp_path, ['pixel'])
    (tmp_path / 'bruto' / SHA_INTERNO / 'estrutura.json').write_text('{nao e json', encoding='utf-8')
    assert not _permitida_com_pasta(laudo_de(cam(1, 'smart_embutido', smart=smart_com_pasta())), 1, tmp_path)


def test_recorte_sobre_smart_com_smart_interno_fica_de_fora(tmp_path):
    laudo = laudo_de(cam(1, 'smart_embutido', smart=smart_com_pasta()), cam(2, clipping=True))
    _estrutura(tmp_path, ['pixel', 'smartobject'])
    assert not _permitida_com_pasta(laudo, 2, tmp_path)
    _estrutura(tmp_path, ['pixel'])
    assert _permitida_com_pasta(laudo, 1, tmp_path) and _permitida_com_pasta(laudo, 2, tmp_path)


# ------------------------------------------------------------------ base de recorte que e grupo
def test_texto_recortado_sobre_grupo_tira_as_folhas_do_grupo():
    # o grupo 2 e a base de recorte do texto 4: o pixel 3 dentro do grupo e o conteudo da base e fica de fora
    laudo = laudo_de(cam(1), cam(2, 'grupo'), cam(3, pai_id=2), cam(4, 'texto', texto='abc', clipping=True))
    assert permitida(laudo, 1)
    assert not permitida(laudo, 2) and not permitida(laudo, 3) and not permitida(laudo, 4)
    assert mm.camadas_permitidas(laudo) == [1]


def test_texto_recortado_sobre_grupo_tira_os_netos_tambem():
    laudo = laudo_de(cam(2, 'grupo'), cam(5, 'grupo', pai_id=2), cam(6, pai_id=5), cam(7, pai_id=2),
                     cam(4, 'texto', texto='abc', clipping=True), cam(8))
    assert mm.camadas_permitidas(laudo) == [8]


def test_grupo_recortado_sobre_texto_tira_as_folhas_do_grupo():
    # o psd-tools nao grava recorte em grupo, mas o laudo pode trazer: o conteudo do grupo recortado fica de fora
    laudo = laudo_de(cam(1, 'texto', texto='abc'), cam(2, 'grupo', clipping=True), cam(3, pai_id=2))
    assert not permitida(laudo, 3)


def test_pixel_recortado_sobre_grupo_sem_texto_entra():
    laudo = laudo_de(cam(2, 'grupo'), cam(3, pai_id=2), cam(4, clipping=True))
    assert permitida(laudo, 3) and permitida(laudo, 4)


# ------------------------------------------------------------------ copia para sugestoes/miniaturas
def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _job_falso(tmp_path, laudo, ids_com_arquivo, extras=()):
    job = tmp_path / 'job'
    pasta = job / 'laudo' / 'miniaturas'
    pasta.mkdir(parents=True)
    for lid in ids_com_arquivo:
        (pasta / ('%s.png' % lid)).write_bytes(b'png-sintetico-%s' % str(lid).encode())
    for nome in extras:
        (pasta / nome).write_bytes(b'extra')
    (job / 'laudo' / 'laudo.json').write_text(json.dumps(laudo), encoding='utf-8')
    return job


def test_modo_a_copia_so_as_permitidas_com_indice(tmp_path):
    laudo = laudo_de(cam(1), cam(2, 'texto', texto='abc'), cam(3, visivel=False), cam(4))
    job = _job_falso(tmp_path, laudo, [1, 2, 3, 4], extras=['idx7.png', 'nao-e-id.png'])
    indice = mm.gravar_miniaturas(job, 'a', laudo=laudo)
    pasta = job / 'sugestoes' / 'miniaturas'
    assert sorted(p.name for p in pasta.iterdir()) == ['1.png', '4.png', 'indice.json']
    dados = json.loads((pasta / 'indice.json').read_text(encoding='utf-8'))
    assert dados == indice
    assert [set(i) for i in dados['miniaturas']] == [{'layer_id', 'sha256'}] * 2
    assert {i['layer_id']: i['sha256'] for i in dados['miniaturas']} == {
        1: _sha(job / 'laudo' / 'miniaturas' / '1.png'), 4: _sha(job / 'laudo' / 'miniaturas' / '4.png')}
    for i in dados['miniaturas']:
        assert _sha(pasta / ('%d.png' % i['layer_id'])) == i['sha256']
    assert set(dados) == {'miniaturas'}


def test_permitida_sem_arquivo_de_origem_nao_entra(tmp_path):
    laudo = laudo_de(cam(1), cam(2))
    job = _job_falso(tmp_path, laudo, [2])
    indice = mm.gravar_miniaturas(job, 'a', laudo=laudo)
    assert [i['layer_id'] for i in indice['miniaturas']] == [2]


def test_camada_com_segredo_no_nome_fica_de_fora(tmp_path):
    laudo = laudo_de(cam(1, nome=valor_rotulado()), cam(2))
    job = _job_falso(tmp_path, laudo, [1, 2])
    indice = mm.gravar_miniaturas(job, 'a', laudo=laudo)
    assert [i['layer_id'] for i in indice['miniaturas']] == [2]
    assert not (job / 'sugestoes' / 'miniaturas' / '1.png').exists()


def test_bloqueados_ficam_de_fora(tmp_path):
    laudo = laudo_de(cam(1), cam(2))
    job = _job_falso(tmp_path, laudo, [1, 2])
    indice = mm.gravar_miniaturas(job, 'a', laudo=laudo, bloqueados={2})
    assert [i['layer_id'] for i in indice['miniaturas']] == [1]


def test_refazer_no_modo_a_apaga_o_que_sobrou(tmp_path):
    laudo = laudo_de(cam(1), cam(2))
    job = _job_falso(tmp_path, laudo, [1, 2])
    velha = job / 'sugestoes' / 'miniaturas' / '55.png'
    velha.parent.mkdir(parents=True)
    velha.write_bytes(b'de outro PSD')
    mm.gravar_miniaturas(job, 'a', laudo=laudo_de(cam(1)))
    assert sorted(p.name for p in velha.parent.iterdir()) == ['1.png', 'indice.json']


@pytest.mark.parametrize('modo', ['b', 'c', None, 'x'])
def test_fora_do_modo_a_a_pasta_some_inteira(tmp_path, modo):
    laudo = laudo_de(cam(1))
    job = _job_falso(tmp_path, laudo, [1])
    mm.gravar_miniaturas(job, 'a', laudo=laudo)
    assert (job / 'sugestoes' / 'miniaturas' / '1.png').exists()
    assert mm.gravar_miniaturas(job, modo, laudo=laudo) is None
    assert not (job / 'sugestoes' / 'miniaturas').exists()
    assert (job / 'laudo' / 'miniaturas' / '1.png').exists()


def test_sha256_diferente_na_copia_recusa_tudo(tmp_path, monkeypatch):
    laudo = laudo_de(cam(1), cam(2))
    job = _job_falso(tmp_path, laudo, [1, 2])
    original = mm._gravar_copia

    def corromper(destino, dados):
        original(destino, dados + b'!')
    monkeypatch.setattr(mm, '_gravar_copia', corromper)
    with pytest.raises(mm.ErroMiniatura):
        mm.gravar_miniaturas(job, 'a', laudo=laudo)
    assert not (job / 'sugestoes' / 'miniaturas').exists()


# ------------------------------------------------------------------ ponta a ponta no PSD sintetico
PLAT = plataforma.obter()


@pytest.fixture(scope='module')
def kv_miniaturas(tmp_path_factory):
    if PLAT.nome in ('sem-suporte', 'mac'):
        pytest.skip('sem isolador neste sistema')
    pasta = tmp_path_factory.mktemp('miniaturas')
    psd = sinteticos.miniaturas(pasta / 'psd')
    job = pasta / 'job'
    _codigo, laudo, _extras = leitor.ler(psd, job / 'laudo')
    return job, laudo


def _ids_por_nome(laudo):
    out = {}
    for c in laudo['camadas']:
        out.setdefault(c['nome'], c['identidade']['layer_id'])
    return out


def test_psd_sintetico_traz_cada_caso(kv_miniaturas):
    _job, laudo = kv_miniaturas
    assert set(_ids_por_nome(laudo)) == set(sinteticos.CASOS_MINIATURAS)
    ids = [c['identidade']['layer_id'] for c in laudo['camadas']]
    assert ids.count(sinteticos.ID_REPETIDO) == 2


def test_psd_sintetico_modo_a_so_as_permitidas(kv_miniaturas):
    job, laudo = kv_miniaturas
    ids = _ids_por_nome(laudo)
    esperado = sorted(ids[n] for n, entra in sinteticos.CASOS_MINIATURAS.items() if entra)
    assert mm.camadas_permitidas(laudo, pasta_laudo=job / 'laudo') == esperado
    indice = mm.gravar_miniaturas(job, 'a', laudo=laudo)
    pasta = job / 'sugestoes' / 'miniaturas'
    assert sorted(i['layer_id'] for i in indice['miniaturas']) == esperado
    assert sorted(p.name for p in pasta.iterdir()) == sorted(['%d.png' % i for i in esperado] + ['indice.json'])
    assert not any(p.name.startswith('idx') for p in pasta.iterdir())
    for i in indice['miniaturas']:
        assert _sha(pasta / ('%d.png' % i['layer_id'])) == _sha(job / 'laudo' / 'miniaturas' / ('%d.png' % i['layer_id']))
    # o indice nao leva nome de camada nem texto
    bruto = (pasta / 'indice.json').read_text(encoding='utf-8')
    assert '-mini' not in bruto and sinteticos.TEXTO_SINTETICO not in bruto


def test_psd_sintetico_le_o_laudo_do_job_quando_nao_vem_pronto(kv_miniaturas):
    job, laudo = kv_miniaturas
    indice = mm.gravar_miniaturas(job, 'a')
    assert sorted(i['layer_id'] for i in indice['miniaturas']) == mm.camadas_permitidas(laudo, pasta_laudo=job / 'laudo')


@pytest.mark.parametrize('modo', ['b', 'c'])
def test_psd_sintetico_modos_b_e_c_sem_a_pasta(kv_miniaturas, modo):
    job, laudo = kv_miniaturas
    mm.gravar_miniaturas(job, 'a', laudo=laudo)
    mm.gravar_miniaturas(job, modo, laudo=laudo)
    assert not (job / 'sugestoes' / 'miniaturas').exists()
