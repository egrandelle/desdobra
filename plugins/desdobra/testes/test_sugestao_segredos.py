# -*- coding: utf-8 -*-
"""Detector de segredos: padroes do registro, normalizacao, achado sem trecho e arquivo do DA."""
import json

import pytest

from desdobra import contratos, limites
from desdobra.sugestao import segredos
from test_sugestao_apoio import segredos_falsos, valor_rotulado

NOME_ROTULADO = 'valor rotulado como segredo'


def _nomes_no_registro():
    return {item['nome'] for item in limites.valor('segredos.padroes')}


def test_padroes_vem_do_registro_e_compilam():
    det = segredos.Detector()
    assert {p.nome for p in det.padroes} == _nomes_no_registro()
    assert limites.efeito('segredos.padroes') == 'reprova'


@pytest.mark.parametrize('nome_padrao', sorted(segredos_falsos()))
def test_cada_padrao_acha_o_seu_segredo_em_nome_e_em_texto(nome_padrao):
    if nome_padrao not in _nomes_no_registro():
        pytest.skip('padrao %r ainda nao esta no registro' % nome_padrao)
    segredo = segredos_falsos()[nome_padrao]
    det = segredos.Detector()
    for texto in ('Camada ' + segredo, 'Linha 1\nchave=' + segredo + '\nLinha 3'):
        nomes = [n for n, _ in det.procurar(texto)]
        assert nome_padrao in nomes


def test_caractere_invisivel_no_meio_nao_esconde_o_segredo():
    segredo = segredos_falsos()['chave de acesso da AWS']
    escondido = segredo[:6] + '​' + segredo[6:]
    assert segredos.Detector().tem_segredo('Camada ' + escondido)


@pytest.mark.parametrize('texto', [
    'Promoção da semana', 'Até 50% de desconto no app', 'R$ 19,90 à vista', 'www.exemplo.com.br/promo',
    'Logo principal', 'Camada 12 cópia 3', 'a' * 64, '0123456789abcdef' * 4, 'Senha do Wi-Fi na recepção',
    'token', 'sk-curto', 'AKIA123',
])
def test_textos_comuns_nao_disparam(texto):
    assert segredos.Detector().procurar(texto) == []


def test_achado_nunca_guarda_o_trecho():
    segredo = segredos_falsos()['chave da OpenAI']
    achado = segredos.Detector().achado_em('camada', 7, {'nome': 'x ' + segredo, 'textos': ['nada']})
    assert achado is not None and achado.layer_id == 7 and achado.campos == {'nome'}
    texto = json.dumps(achado.para_json(), ensure_ascii=False)
    assert segredo not in texto and segredo[:12] not in texto
    assert achado.entropia_bits and achado.entropia_bits > 1


def test_entropia():
    assert segredos.entropia_bits('') == 0.0
    assert segredos.entropia_bits('aaaa') == 0.0
    assert segredos.entropia_bits('abcd') == pytest.approx(2.0)


def test_padrao_mal_formado_da_erro_claro():
    with pytest.raises(segredos.ErroPadrao, match='nao compila'):
        segredos.compilar([{'nome': 'ruim', 'regex': '('}])
    with pytest.raises(segredos.ErroPadrao, match='precisa de'):
        segredos.compilar([{'nome': 'sem regex'}])


def test_rotulado_com_alta_entropia_quando_estiver_no_registro():
    if NOME_ROTULADO not in _nomes_no_registro():
        pytest.skip('o padrao %r aguarda o integrador (pendencia do registro)' % NOME_ROTULADO)
    det = segredos.Detector()
    assert NOME_ROTULADO in [n for n, _ in det.procurar('Camada ' + valor_rotulado())]
    assert not det.procurar('Senha: escreva aqui')


def test_gravar_bloqueios_junta_e_valida(tmp_path):
    falsos = segredos_falsos()
    det = segredos.Detector()
    a1 = det.achado_em('camada', 3, {'nome': falsos['token do GitHub']})
    a2 = det.achado_em('camada', 3, {'textos': [falsos['token JWT']]})
    a3 = det.achado_em('camada', 9, {'nome': falsos['chave privada']})
    assert segredos.gravar_bloqueios(tmp_path, [], comando='x') is None
    caminho = segredos.gravar_bloqueios(tmp_path, [a1, a3], comando='ler')
    segredos.gravar_bloqueios(tmp_path, [a2], comando='ler')
    dados = contratos.ler(caminho, 'segredos-bloqueados/1')
    assert dados['total'] == 2
    por_id = {b['layer_id']: b for b in dados['bloqueios']}
    assert por_id[3]['campos'] == ['nome', 'textos']
    assert set(por_id[3]['padroes']) == {'token do GitHub', 'token JWT'}
    bruto = caminho.read_text(encoding='utf-8')
    for s in falsos.values():
        assert s not in bruto


def test_linhas_para_o_da_nao_mostram_o_trecho():
    segredo = segredos_falsos()['chave do Stripe']
    achado = segredos.Detector().achado_em('camada', 4, {'nome': segredo})
    linhas = segredos.linhas_para_o_da([achado])
    assert len(linhas) == 1 and 'camada 4' in linhas[0].lower() and segredo not in linhas[0]
    assert chr(0x2014) not in linhas[0] and chr(0x2013) not in linhas[0]
