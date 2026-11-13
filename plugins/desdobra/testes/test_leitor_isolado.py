# -*- coding: utf-8 -*-
"""Leitor de ponta a ponta com o processo filho isolado de verdade (plataforma do sistema), em PSD sintetico."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

import sinteticos
from desdobra import cli, contratos, leitor, limites, plataforma
from desdobra.resultado import Codigo

PLAT = plataforma.obter()
pytestmark = pytest.mark.skipif(PLAT.nome in ('sem-suporte', 'mac'), reason='sem isolador neste sistema')


@pytest.fixture(scope='module')
def casos(tmp_path_factory):
    """Gera os sinteticos e roda o leitor uma vez em cada um."""
    pasta = tmp_path_factory.mktemp('leitor')
    isca = pasta / 'fora-da-entrada' / 'isca.txt'
    isca.parent.mkdir()
    isca.write_text('arquivo-isca sintetico\n', encoding='utf-8')
    campanha = pasta / 'campanha'
    campanha.mkdir()
    (campanha / 'isca.txt').write_bytes(b'x' * 1234)
    arquivos = {'simples': sinteticos.simples(pasta / 'psd'), 'coberta': sinteticos.coberta(pasta / 'psd'),
                'quadros': sinteticos.quadros(pasta / 'psd'), 'embutido': sinteticos.embutido(pasta / 'psd')[0],
                'linkado': sinteticos.linkado(pasta / 'psd', isca), 'bomba': sinteticos.bomba(pasta / 'psd'),
                'embutido_png': sinteticos.embutido(pasta / 'psd', 'embutido-png.psd', sinteticos.png_pequeno())[0]}
    out = {}
    for nome, psd in arquivos.items():
        destino = pasta / 'laudos' / nome
        codigo, laudo, extras = leitor.ler(psd, destino, pasta_campanha=campanha if nome == 'linkado' else None)
        out[nome] = {'codigo': codigo, 'laudo': laudo, 'extras': extras, 'pasta': destino, 'psd': psd}
    out['_isca'] = isca
    out['_pasta'] = pasta
    return out


def estruturas(pasta):
    return {p.parent.name: json.loads(p.read_text(encoding='utf-8')) for p in (pasta / 'bruto').glob('*/estrutura.json')}


def camadas_por_nome(laudo):
    return {c['nome']: c for c in laudo['camadas']}


def test_simples_lido_valido_com_texto_por_trecho(casos):
    c = casos['simples']
    assert c['codigo'] == Codigo.OK
    laudo = contratos.ler(c['pasta'] / 'laudo.json', 'laudo/1')
    assert laudo['resumo']['n_camadas'] == 6
    cam = camadas_por_nome(laudo)
    assert cam['fundo-sintetico']['situacao'] == 'lida' and cam['grupo-sintetico']['tipo'] == 'grupo'
    t = cam['texto-sintetico']
    assert t['tipo'] == 'texto' and [r['fonte_ps'] for r in t['texto']['runs']] == [
        sinteticos.FONTE_SINTETICA, sinteticos.FONTE_SINTETICA_2, sinteticos.FONTE_SO_ESPACO]
    assert t['situacao'] == 'degradada' and [m['regra'] for m in t['motivos']] == ['D7']
    assert cam['oculta']['aparencia']['visivel_efetiva'] is False
    usadas = {f['fonte_ps']: f for f in laudo['fontes_usadas']}
    assert usadas[sinteticos.FONTE_SO_ESPACO]['so_em_espaco'] is True
    assert laudo['prova_pixel']['feita'] and laudo['prova_pixel']['pct_px_acima_qualquer_canal'] == 0.0
    assert laudo['prova_pixel']['limiar']['valor'] == limites.valor('prova_pixel.limiar_diferenca')
    assert [v['layer_id'] for v in laudo['documento']['variantes_ocultas']] == [cam['oculta']['identidade']['layer_id']]
    assert laudo['origem']['sha256'] == c['laudo']['origem']['sha256'] and laudo['origem']['psd_tools'] == '1.26.0'
    # miniaturas por layer_id e assets nomeados pelo sha256
    ids = {x['identidade']['layer_id'] for x in laudo['camadas'] if x['tipo'] != 'grupo'}
    assert {int(p.stem) for p in (c['pasta'] / 'miniaturas').glob('*.png')} == ids
    assets = list((c['pasta'] / 'assets').glob('*.png'))
    import hashlib
    assert assets and all(hashlib.sha256(p.read_bytes()).hexdigest() == p.stem for p in assets)
    assert not (c['pasta'] / '.trabalho').exists()


def test_estrutura_bruta_valida_com_auditoria_sem_alarme(casos):
    for nome in ('simples', 'coberta', 'quadros', 'embutido', 'linkado'):
        for est in estruturas(casos[nome]['pasta']).values():
            contratos.validar(est, 'estrutura/1')
            assert est['auditoria']['instalado'] is True and est['auditoria']['bloqueios'] == []
            assert est['leitor']['psd_tools'] == '1.26.0'


def test_coberta_no_kv_no_arquivo(casos):
    cam = camadas_por_nome(casos['coberta']['laudo'])
    fundo = cam['fundo-coberto']['geometria']['coberta_no_kv']
    solto = cam['elemento-coberto']['geometria']['coberta_no_kv']
    tampa = cam['tampa-opaca']['geometria']['coberta_no_kv']
    assert fundo['coberta'] and fundo['ocupa_canvas'] and fundo['sugestao_da_regra']['funcao'] == 'estrutura'
    assert solto['coberta'] and not solto['ocupa_canvas'] and solto['sugestao_da_regra']['funcao'] == 'fora_da_peca'
    assert not tampa['coberta'] and tampa['fracao_coberta'] < 1
    assert cam['veu-acima']['geometria']['coberta_no_kv']['coberta'] is False
    assert casos['coberta']['laudo']['resumo']['n_cobertas_no_kv'] == 2


def test_quadros_no_arquivo(casos):
    laudo = casos['quadros']['laudo']
    q = laudo['documento']['quadros']
    assert len(q) == 3 and sum(x['visivel_ao_salvar'] for x in q) == 1
    assert all(x['caixa'] == [0, 0, 90, 60] for x in q)
    assert laudo['resumo']['n_quadros'] == 3


def test_smart_object_embutido_aberto_em_filho_proprio(casos):
    c = casos['embutido']
    so = c['laudo']['camadas'][0]['smart_object']
    assert so['embutido'] and so['tipo_detectado'] == 'psb'
    ab = so['abertura']
    assert ab['situacao'] == 'aberto' and ab['profundidade'] == 1 and ab['resumo']['n_camadas'] == 2
    est = estruturas(c['pasta'])
    interno = est[so['sha256']]
    assert interno['origem']['recorte'] is not None and interno['origem']['profundidade'] == 1
    assert interno['prova_pixel']['motivo'] in ('sem_composicao', 'sem_merged')
    assert c['extras']['recursos']['filhos'] == 2


def test_linkado_so_registrado_e_isca_nunca_aberta(casos):
    c = casos['linkado']
    cam = c['laudo']['camadas'][0]
    assert cam['tipo'] == 'smart_linkado' and cam['situacao'] == 'bloqueante'
    assert [m['regra'] for m in cam['motivos']] == ['B1']
    so = cam['smart_object']
    assert so['registro'] == {'nome': 'isca.txt', 'tamanho': 1234, 'data': '2026-10-29T12:30:00'}
    # proposta de casamento por nome e tamanho, sem uso antes da confirmacao do DA
    assert so['casamento']['situacao'] == 'aguardando_confirmacao_do_da' and so['casamento']['usado'] is False
    assert so['casamento']['candidatos'] == [{'arquivo': 'campanha/isca.txt', 'bytes': 1234, 'mesmo_tamanho': True}]
    # o caminho gravado no PSD nao aparece em nada que o leitor gravou, e o gancho nao barrou nada
    isca = str(casos['_isca'])
    for p in c['pasta'].rglob('*.json'):
        texto = p.read_text(encoding='utf-8')
        assert isca not in texto and isca.replace('\\', '/') not in texto and 'fora-da-entrada' not in texto
    for est in estruturas(c['pasta']).values():
        assert est['auditoria']['bloqueios'] == []


def test_bomba_recusada_antes_de_alocar(casos):
    c = casos['bomba']
    assert c['codigo'] == Codigo.RECUSADO
    laudo = contratos.ler(c['pasta'] / 'laudo.json', 'laudo/1')
    assert laudo['camadas'] == [] and len(laudo['recusas']) == 1
    r = laudo['recusas'][0]
    assert r['tipo'] == 'orcamento' and r['etapa'] == 'cabecalho'
    assert r['medidas']['largura'] == 29999 and r['medidas']['estimativa_bytes'] > r['medidas']['orcamento_bytes']
    # o orcamento tem parcela a calibrar: a recusa nao reprova, pede confirmacao do DA, com os limites citados
    assert r['decisao'] == 'pede_confirmacao_do_da'
    assert {x['limite_id'] for x in r['limites']} == set(leitor.LIMITES_DO_ORCAMENTO)
    # o isolador do Windows sempre mede o pico: ele tem de existir e ficar longe da estimativa
    pico = c['extras']['recursos']['pico_bytes']
    assert pico is not None and pico < r['medidas']['estimativa_bytes'] // 10
    rec = contratos.ler(next((c['pasta'] / 'bruto').glob('*/recusa.json')), 'recusa/1')
    assert rec['codigo'] == 3 and rec['origem_sha256'] == laudo['origem']['sha256']


def test_processo_principal_nunca_abre_psd(casos, tmp_path, monkeypatch):
    import psd_tools

    def proibido(*a, **k):
        raise AssertionError('o processo principal chamou PSDImage.open')
    monkeypatch.setattr(psd_tools.PSDImage, 'open', proibido)
    codigo, laudo, _ = leitor.ler(casos['simples']['psd'], tmp_path / 'laudo')
    assert codigo == Codigo.OK and laudo['resumo']['n_camadas'] == 6


def _filho(*args, pasta):
    cmd = [str(PLAT.interpretador()), '-I', '-B', '-m', 'desdobra.leitor.filho', *[str(a) for a in args]]
    return subprocess.run(cmd, input=b'iniciar\n', capture_output=True, cwd=pasta, timeout=120)


def test_filho_recusa_profundidade_e_argumentos(casos, tmp_path):
    psd = casos['simples']['psd']
    p = _filho(psd, tmp_path / 's', '--orcamento-bytes', 10 ** 9, '--profundidade', 3, '--profundidade-max', 2,
               pasta=tmp_path)
    assert p.returncode == 3
    linha = json.loads(p.stdout.decode('utf-8').strip())
    assert linha == {'esquema': 'filho/1', 'codigo': 3, 'arquivo': 'recusa.json'}
    assert contratos.ler(tmp_path / 's' / 'recusa.json', 'recusa/1')['tipo'] == 'profundidade'
    p = _filho(psd, tmp_path / 's2', '--profundidade', 0, pasta=tmp_path)
    assert p.returncode == 2 and p.stdout == b''


def test_filho_espera_a_liberacao_do_isolador(casos, tmp_path):
    cmd = [str(PLAT.interpretador()), '-I', '-B', '-m', 'desdobra.leitor.filho', str(casos['simples']['psd']),
           str(tmp_path / 's'), '--orcamento-bytes', str(10 ** 9), '--profundidade', '0', '--profundidade-max', '2']
    p = subprocess.run(cmd, input=b'', capture_output=True, cwd=tmp_path, timeout=60)
    assert p.returncode == 2 and not (tmp_path / 's').exists()


def test_cli_ler_avulso(casos, tmp_path, monkeypatch, capsys):
    codigo = cli.principal(['--envelope', 'ler', str(casos['coberta']['psd']), '--saida', str(tmp_path / 'saida')])
    env = json.loads(capsys.readouterr().out.strip())
    contratos.validar(env, 'envelope/1')
    assert codigo == 0 and env['comando'] == 'ler' and env['contagens']['camadas'] == 4
    assert env['contagens']['cobertas_no_kv'] == 2 and len(env['ids']['arquivo_sha256']) == 64
    assert 'conteudo' not in env  # sem job, modo c
    texto = json.dumps(env, ensure_ascii=False)
    for nome in ('fundo-coberto', 'elemento-coberto', 'tampa-opaca', str(tmp_path)):
        assert nome not in texto
    assert (tmp_path / 'saida' / 'laudo.json').is_file()


def test_resultado_nao_leva_conteudo_fora_de_conteudo(casos):
    r = leitor.resultado_de(Codigo.OK, casos['simples']['laudo'], casos['simples']['extras'])
    import re
    for campo in (r.contagens, r.ids, r.numeros):
        assert all(re.match(r'^[a-z][a-z0-9_]*$', k) for k in campo)
    assert r.o_que_fazer is None and r.conteudo['camadas'][0]['nome']
    assert sinteticos.TEXTO_SINTETICO not in json.dumps([r.contagens, r.ids, r.numeros, r.o_que_fazer])


def test_embutido_que_nao_e_psd_nao_e_aberto(casos):
    c = casos['embutido_png']
    so = c['laudo']['camadas'][0]['smart_object']
    assert so['embutido'] and so['tipo_detectado'] == 'png'
    assert so['abertura'] == {'situacao': 'nao_aberto', 'motivo': 'não é PSD nem PSB'}
    assert so['dims']['largura'] == 12 and so['dims']['fonte'] == 'PIL (cabeçalho)'
    assert c['extras']['recursos']['filhos'] == 1


class _Filho:
    def __init__(self, situacao, codigo, pico=None):
        self.situacao, self.codigo, self.pico_bytes, self.tempo_s, self.motivo = situacao, codigo, pico, 1.0, 'teste'


def test_composicao_que_estoura_nao_derruba_a_leitura(casos, tmp_path):
    origem = next((casos['simples']['pasta'] / 'bruto').glob('*/estrutura.json'))
    est = json.loads(origem.read_text(encoding='utf-8'))
    est['prova_pixel'] = {'feita': False, 'motivo': 'pendente'}
    contratos.gravar(tmp_path / 'estrutura.json', est, 'estrutura/1')
    r = leitor.interpretar(_Filho('memoria', 0xC0000017), tmp_path, 1)
    assert r['codigo'] == Codigo.OK and r['estrutura']['prova_pixel'] == {'feita': False, 'motivo': 'orcamento'}
    vazio = tmp_path / 'vazio'
    vazio.mkdir()
    assert leitor.interpretar(_Filho('memoria', 1), vazio, 1)['codigo'] == Codigo.ORCAMENTO
    assert leitor.interpretar(_Filho('tempo', None), vazio, 1)['recusa']['tipo'] == 'tempo'
    assert leitor.interpretar(_Filho('queda', 0xC0000005), vazio, 1)['codigo'] == Codigo.RECUSADO
    assert leitor.interpretar(_Filho('ok', 1), vazio, 1)['codigo'] == Codigo.ERRO_INTERNO
    assert leitor.interpretar(_Filho('recusado', None), vazio, 1)['codigo'] == Codigo.NAO_DISPONIVEL


def test_recusa_de_memoria_do_filho_vira_codigo_de_orcamento(tmp_path):
    contratos.gravar(tmp_path / 'recusa.json', {'esquema': 'recusa/1', 'tipo': 'memoria', 'etapa': 'abrir',
                                                'motivo': 'x', 'codigo': 4, 'medidas': {}, 'origem_sha256': None},
                     'recusa/1')
    out = leitor.interpretar(_Filho('memoria', 4), tmp_path, 1)
    assert out['codigo'] == Codigo.ORCAMENTO and out['recusa']['tipo'] == 'memoria'
    assert leitor.CODIGOS_FILHO_RECUSA == {3: Codigo.RECUSADO, 4: Codigo.ORCAMENTO, 5: Codigo.AUDITORIA}


def test_corte_por_profundidade_no_leitor(casos, tmp_path, monkeypatch):
    real = limites.valor
    monkeypatch.setattr(limites, 'valor', lambda i: 0 if i == 'leitor.profundidade_max_smart' else real(i))
    codigo, laudo, extras = leitor.ler(casos['embutido']['psd'], tmp_path / 'l')
    assert codigo == Codigo.OK and extras['recursos']['filhos'] == 1
    so = next(c for c in laudo['camadas'] if c['tipo'] == 'smart_embutido')
    assert so['smart_object']['abertura'] == {'situacao': 'nao_aberto', 'motivo': 'profundidade máxima'}
    assert 'smart_object_nao_aberto' in [a['codigo'] for a in so['alertas']]


def test_teto_confirmado_pelo_da_substitui_o_calculado(casos, tmp_path):
    teto = 2 * 1024 ** 3
    codigo, laudo, extras = leitor.ler(casos['simples']['psd'], tmp_path / 'l', teto_memoria_bytes=teto,
                                       tempo_max_s=120)
    assert codigo == Codigo.OK and extras['recursos']['orcamento_bytes'] == teto
    assert laudo['recursos']['orcamento_bytes'] == teto


def test_caminhos_relativos_de_ponta_a_ponta(casos, tmp_path):
    import os
    psd = os.path.relpath(casos['simples']['psd'], tmp_path)

    def motor(*argumentos):
        p = subprocess.run([sys.executable, '-I', '-B', '-m', 'desdobra', '--envelope', *argumentos], cwd=tmp_path,
                           capture_output=True, timeout=300)
        return json.loads(p.stdout.decode('utf-8').strip().splitlines()[-1])
    assert motor('job', 'criar', 'job-rel', '--kv', psd)['codigo'] == 0
    env = motor('job', 'proxima', 'job-rel')
    assert env['codigo'] == 0 and env['contagens']['codigo_da_fase'] == 0, env
    assert motor('ler', psd, '--saida', 'avulso-rel')['codigo'] == 0
    assert (tmp_path / 'avulso-rel' / 'laudo.json').is_file()
    assert motor('job', 'proxima', 'pasta-que-nao-existe')['codigo'] == int(Codigo.RECUSADO)


def test_ler_avulso_nao_tem_opcao_de_modo_de_dados(casos, tmp_path):
    p = subprocess.run([sys.executable, '-I', '-B', '-m', 'desdobra', '--envelope', 'ler', str(casos['simples']['psd']),
                        '--saida', str(tmp_path / 's'), '--modo-dados', 'a'], capture_output=True, timeout=120)
    env = json.loads(p.stdout.decode('utf-8').strip())
    assert env['codigo'] == int(Codigo.USO) and env['modo_dados'] == 'c' and 'conteudo' not in env


# ------------------------------------------------------------------ correcoes da reverificacao do M1
class _PlataformaQueTroca:
    """Roda o filho de verdade e troca o resultado de um deles, para simular o que o isolador nao provoca sozinho."""

    def __init__(self, trocar):
        self.trocar = trocar

    def interpretador(self):
        return PLAT.interpretador()

    def executar_isolado(self, cmd, orcamento, tempo, pasta_trabalho, **kw):
        r = PLAT.executar_isolado(cmd, orcamento, tempo, pasta_trabalho, **kw)
        return self.trocar(cmd, r)


def test_alarme_de_auditoria_no_filho_do_smart_object_sai_com_codigo_5(casos, tmp_path):
    import dataclasses
    from desdobra.sugestao import envelope

    def trocar(cmd, r):
        if '--recorte' not in cmd:
            return r
        saida = Path(cmd[6])
        (saida / 'estrutura.json').unlink(missing_ok=True)
        contratos.gravar(saida / 'recusa.json', {'esquema': 'recusa/1', 'tipo': 'auditoria', 'etapa': 'estrutura',
                                                 'motivo': 'O gancho de auditoria barrou uma ação.', 'codigo': 5,
                                                 'medidas': {'bloqueios': 1}}, 'recusa/1')
        return dataclasses.replace(r, situacao='ok', codigo=5)
    codigo, laudo, extras = leitor.ler(casos['embutido']['psd'], tmp_path / 'l', plat=_PlataformaQueTroca(trocar))
    assert codigo == Codigo.AUDITORIA
    assert [(x['tipo'], x['etapa']) for x in laudo['recusas']] == [('auditoria', 'smart_object_estrutura')]
    r = leitor.resultado_de(codigo, laudo, extras)
    assert r.codigo == int(Codigo.AUDITORIA) and r.situacao == 'recusado'
    assert r.o_que_fazer == leitor.O_QUE_FAZER[Codigo.AUDITORIA]
    # mesmo com o codigo 0 vindo de fora, a recusa de auditoria no laudo decide
    r0 = leitor.resultado_de(Codigo.OK, laudo, extras)
    assert r0.codigo == int(Codigo.AUDITORIA) and r0.o_que_fazer == leitor.O_QUE_FAZER[Codigo.AUDITORIA]
    assert envelope.montar(r0, 'c')['codigo'] == int(Codigo.AUDITORIA)


@pytest.mark.parametrize('situacao, opcao, ids', [
    ('tempo', '--tempo-max-s', leitor.LIMITES_DO_TEMPO),
    ('memoria', '--teto-memoria-bytes', leitor.LIMITES_DO_ORCAMENTO + ('leitor.max_alloc_bytes',)),
])
def test_recusa_da_composicao_recebe_limites_e_decisao(casos, tmp_path, situacao, opcao, ids):
    import dataclasses

    def trocar(cmd, r):
        # o pai parou o filho na composicao, com a estrutura ja gravada
        saida = Path(cmd[6])
        est = json.loads((saida / 'estrutura.json').read_text(encoding='utf-8'))
        est['prova_pixel'] = {'feita': False, 'motivo': 'pendente'}
        contratos.gravar(saida / 'estrutura.json', est, 'estrutura/1')
        return dataclasses.replace(r, situacao=situacao, codigo=None, motivo=situacao)
    codigo, laudo, extras = leitor.ler(casos['simples']['psd'], tmp_path / 'l', plat=_PlataformaQueTroca(trocar))
    assert codigo == Codigo.OK
    rec = next(x for x in laudo['recusas'] if x['etapa'] == 'composicao')
    assert rec['decisao'] == 'pede_confirmacao_do_da'
    assert [x['limite_id'] for x in rec['limites']] == list(ids)
    contratos.ler(tmp_path / 'l' / 'laudo.json', 'laudo/1')
    assert json.loads((tmp_path / 'l' / 'laudo.json').read_text(encoding='utf-8'))['recusas'][0]['decisao'] == \
        'pede_confirmacao_do_da'
    r = leitor.resultado_de(codigo, laudo, extras)
    assert r.situacao == 'ok_com_bloqueio' and r.contagens['recusas_pedem_confirmacao'] == 1
    # M7c, ajuste terminal: a parada no teto continua decisão do DA, sem comando nem opção de linha de comando; o
    # teto maior fica com a Trezion
    assert opcao not in r.o_que_fazer and 'job proxima' not in r.o_que_fazer
    assert 'decidir' in r.o_que_fazer and 'Trezion' in r.o_que_fazer and '/desdobra:continuar' in r.o_que_fazer


@pytest.mark.parametrize('opcoes', [('--tempo-max-s', 'nan'), ('--tempo-max-s', 'inf'), ('--tempo-max-s', '-1'),
                                    ('--teto-memoria-bytes', '99999999999999999999999'),
                                    ('--teto-memoria-bytes', '0')])
def test_teto_fora_do_aceito_e_erro_de_uso(casos, tmp_path, opcoes):
    for argv in (['ler', str(casos['simples']['psd']), '--saida', str(tmp_path / 's')],
                 ['job', 'proxima', str(tmp_path / 'job-que-nao-existe')]):
        args = cli.montar_analisador().parse_args([*argv, *opcoes])
        r = args.executar(args)
        assert r.codigo == int(Codigo.USO) and r.situacao == 'erro', (argv, r.o_que_fazer)
        assert 'teto' in r.o_que_fazer or 'tempo' in r.o_que_fazer
    assert not (tmp_path / 's').exists()
