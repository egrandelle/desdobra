# -*- coding: utf-8 -*-
"""M7c, E1: roteiro da sugestao de funcao nos tres modos de dados (plano do M7c, E1 e secao 4; arquitetura-v1.md,
7.3 a 7.6 e 9.8; decisoes-v1.md, 153, 155, 162, 170 e 190).

Um PSD sintetico com cada caso das miniaturas do modo (a) (testes/sinteticos, miniaturas) e mais uma camada de pixel
com um segredo sintetico no nome, gerado na hora. O roteiro:
  - o job nasce sem modo, e o pacote do modelo sai no modo (c);
  - a escolha do modo (a) feita no modo de teste da tela (origem fixture_de_teste) deixa o job em (c), sem a pasta
    sugestoes/miniaturas/;
  - a escolha do modo (a) com origem da (conftest.escolher_modo_do_da) e o "sugestao pacote" do Claude: os dois
    pacotes no modo (a), as miniaturas so das camadas permitidas, 0 de texto, e o segredo bloqueado;
  - um sugestoes.json sintetico (no lugar do Claude), com o pacote_sha256 que o "sugestao pacote" devolveu, importado
    pelo "sugestao importar";
  - a tela mostra as sugestoes sem gravar nada: nenhum campo ganha valor antes do clique do DA;
  - o DA confirma as funcoes e salva (modo de teste da tela, como os testes do salvar), e a metrica vai para
    medicoes/sugestao.json com a conta exata;
  - a troca para (b) e para (c), com os pacotes, a pasta das miniaturas e os arquivos de sugestao conferidos a cada
    troca;
  - a queda de teto para (c) com a escolha (a) do DA gravada.
As medicoes da secao 4 do plano que sao deste passo (pacote por modo nos 7 jobs, escolha de teste, segredo e fonte,
tempo do "sugestao pacote" e do "sugestao importar") saem na saida do pytest e, quando a variavel de ambiente
DESDOBRA_MEDICAO_SUGESTAO_MODOS existe, num arquivo JSON fora do repositorio.

Tudo sintetico: o PSD e as fontes sao gerados na hora; nenhum arquivo de cliente e lido."""
import hashlib
import io
import json
import os
import shutil
import time
from contextlib import redirect_stdout
from pathlib import Path

import pytest

import sinteticos
import test_derivacao_apoio as ap
import test_fontes_apoio as fap
import test_tela_salvar as tsv
import test_tela_servidor as tts
from conftest import escolher_modo_do_da
from desdobra import cli, contratos, humano, plataforma
from desdobra.briefing import modelo as mb
from desdobra.job import modo_dados
from desdobra.sugestao import acerto
from desdobra.sugestao import miniaturas as mm
from desdobra.sugestao import pacote as sp
from desdobra.tela import atos as ta
from desdobra.tela import estado as te
from desdobra.tela import funcoes as tf
from desdobra.tela import rascunho as tr
from test_sugestao_apoio import segredos_falsos

PLAT = plataforma.obter()
VARIAVEL_MEDICAO = 'DESDOBRA_MEDICAO_SUGESTAO_MODOS'
NOME_SEGREDO = 'logo-mini %s'
# o que o gancho deixa o Claude ler dentro do job (plano do M7c, P1)
LEGIVEIS = ('sugestoes/pacote-modelo.json', 'sugestoes/pacote-specs.json', 'sugestoes/sugestoes.json',
            'sugestoes/mapeamento-specs.json')
ESCRITOS_DO_CLAUDE = ('sugestoes/sugestoes.json', 'sugestoes/sugestoes-validadas.json')
EXPOSTO = {'a': {'metadados': True, 'textos': True, 'miniaturas': True},
           'b': {'metadados': True, 'textos': True, 'miniaturas': False},
           'c': {'metadados': False, 'textos': False, 'miniaturas': False}}
# as funcoes do DA no passo 2, por nome de camada (so folhas: os grupos nao levam funcao propria). A pilha de recorte
# sobre um texto leva a funcao do texto: o motor recusa bloco com regras diferentes
FUNCOES_DO_DA = {
    'fundo-mini': 'fundo', 'quadrado-mini': 'logo_principal', 'oculta-mini': 'fora_da_peca', 'texto-mini': 'titulo',
    'recorte-sobre-texto-mini': 'titulo', 'base-pixel-mini': 'grafismo', 'recorte-sobre-pixel-mini': 'grafismo',
    'dentro-do-grupo-mini': 'grafismo', 'dentro-da-base-mini': 'texto_de_apoio', 'texto-sobre-grupo-mini': 'texto_de_apoio',
    'smart-limpo-mini': 'selo', 'smart-com-texto-mini': 'selo', 'smart-png-mini': 'selo', 'smart-com-smart-mini': 'selo',
    'repetido-a-mini': 'fora_da_peca', 'segredo': 'fora_da_peca'}
USADAS = {'fundo': ('cover', 'centro', 'meio'), 'logo_principal': ('raiz_area', 'direita', 'base'),
          'titulo': ('raiz_area', 'esquerda', 'topo'), 'grafismo': ('contain', 'centro', 'meio'),
          'texto_de_apoio': ('raiz_area', 'esquerda', 'meio'), 'selo': ('raiz_area', 'direita', 'topo')}
# as sugestoes do "Claude": tres certas pela funcao (uma num grupo, que a heranca passa para a folha) e duas erradas
# com a alternativa certa
SUGESTOES = [('fundo-mini', 'fundo', 'imagem'), ('texto-mini', 'titulo', 'texto_de_apoio'),
             ('quadrado-mini', 'selo', 'logo_principal'), ('grupo-mini', 'grafismo', 'estrutura'),
             ('smart-limpo-mini', 'imagem', 'selo')]
FORMATOS = [('mesma', 200, 120), ('vertical', 120, 200)]  # numero-neutro: medidas sinteticas


# ------------------------------------------------------------------ PSD, fontes e job sinteticos
def _psd(pasta, segredo=None):
    """O PSD das miniaturas (S1); com segredo, mais uma camada de pixel visivel, sem texto, com o segredo no nome:
    sem o segredo ela entraria nas miniaturas do modo (a)."""
    if segredo is None:
        return sinteticos.miniaturas(pasta)
    from PIL import Image
    original = sinteticos._salvar  # noqa: SLF001 - o mesmo gerador, com uma camada a mais antes de gravar

    def com_segredo(psd, destino):
        psd.create_pixel_layer(Image.new('RGBA', (16, 10), (10, 120, 60, 255)), name=NOME_SEGREDO % segredo,
                               top=105, left=175)  # numero-neutro: medidas sinteticas
        return original(psd, destino)
    sinteticos._salvar = com_segredo  # noqa: SLF001
    try:
        return sinteticos.miniaturas(pasta)
    finally:
        sinteticos._salvar = original  # noqa: SLF001


def _fontes(pasta):
    fap.gravar(pasta, 'inventada-bold.ttf', fap.fonte(ps=sinteticos.FONTE_SINTETICA, familia='FonteInventada'))
    fap.gravar(pasta, 'inventada-regular.ttf', fap.fonte(ps=sinteticos.FONTE_SINTETICA_2, familia='FonteInventada',
                                                         estilo='Regular', peso=400))
    return pasta


def _ids(laudo):
    out = {}
    for c in laudo['camadas']:
        nome = 'segredo' if c['nome'].startswith('logo-mini ') else c['nome']
        out.setdefault(nome, c['identidade']['layer_id'])
    return out


def _laudo(job):
    return contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')


def _criar_job(base, segredo):
    from desdobra.job import nucleo
    psd = _psd(base / 'psd', segredo)
    fontes = _fontes(base / 'origem-fontes')
    job = base / 'job'
    t0 = time.monotonic()
    nucleo.criar(job, psd, fontes=[fontes])  # sem modo: o DA escolhe na tela (decisoes-v1.md, 170)
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    ids = _ids(_laudo(job))
    funcoes = {ids[n]: f for n, f in FUNCOES_DO_DA.items() if n in ids}
    b = ap.briefing(funcoes=funcoes, formatos=[ap.formato(i, w, h, rotacao={'graus': 0, 'sentido': None})
                                               for i, w, h in FORMATOS])
    b.pop('cabecalho')
    b.pop('job_id')
    arq = base / 'fixture.json'
    arq.write_text(json.dumps(b), encoding='utf-8')
    try:
        mb.importar_teste(job, arq)  # os formatos e o giro de cada um: as funcoes do salvar vem do rascunho do DA
    except mb.ErroBriefing as e:
        pytest.fail('briefing de teste recusado: %s' % [(x.get('codigo'), x.get('onde')) for x in e.erros])
    return {'job': job, 'psd': psd, 'fontes': fontes, 'segredo': segredo, 'ids': ids, 'funcoes': funcoes,
            'tempo_criar_s': round(time.monotonic() - t0, 3)}  # numero-neutro: milissegundos


def _sem_isolador():
    return PLAT.nome in ('sem-suporte', 'mac')


@pytest.fixture(scope='module')
def kv_e1(tmp_path_factory):
    if _sem_isolador():
        pytest.skip('sem isolador neste sistema')
    segredo = segredos_falsos()['token do GitHub']
    return _criar_job(tmp_path_factory.mktemp('e1'), segredo)


@pytest.fixture(scope='module')
def kv_s1(tmp_path_factory):
    if _sem_isolador():
        pytest.skip('sem isolador neste sistema')
    return _criar_job(tmp_path_factory.mktemp('s1'), None)


def _copia(base, destino):
    job = destino / 'job'
    shutil.copytree(base['job'], job)
    return dict(base, job=job)


# ------------------------------------------------------------------ o que o Claude le, o envelope e o log
def _ler(job, rel):
    arq = job / rel
    return arq.read_bytes().decode('utf-8', 'replace') if arq.is_file() else ''


def _legivel_pelo_claude(job):
    """Tudo o que o gancho deixa o Claude ler no job, como texto (as miniaturas pelo indice e pelos bytes)."""
    partes = [_ler(job, rel) for rel in LEGIVEIS]
    pasta = job / 'sugestoes' / 'miniaturas'
    if pasta.exists():
        partes += [p.read_bytes().decode('latin-1') for p in sorted(pasta.rglob('*')) if p.is_file()]
    return '\n'.join(partes)


def _log(job):
    return _ler(job, 'log/eventos.jsonl')


def _ocorrencias_do_segredo(kv, *envelopes):
    """Quantas vezes o segredo do PSD aparece no que o Claude le no job, no log e nos envelopes que o motor devolveu
    (cada "sugestao pacote" e "sugestao importar" que o roteiro rodou). 0 no PSD sem segredo."""
    if not kv['segredo']:
        return 0
    texto = (_legivel_pelo_claude(kv['job']) + _log(kv['job'])
             + ''.join(json.dumps(e, ensure_ascii=False) for e in envelopes))
    return texto.count(kv['segredo'])


def _cli(*argv):
    saida = io.StringIO()
    t0 = time.monotonic()
    with redirect_stdout(saida):
        codigo = cli.principal([str(a) for a in argv])
    parede = time.monotonic() - t0
    linhas = saida.getvalue().strip().splitlines()
    assert len(linhas) == 1, saida.getvalue()
    return codigo, json.loads(linhas[0]), parede


def _pacote_pela_cli(job, teto):
    """O "sugestao pacote" como a skill o roda, com o teto da agencia."""
    codigo, env, parede = _cli('--envelope', '--teto-modo-dados', teto, 'sugestao', 'pacote', '--job', job)
    assert codigo == 0, env
    return env, parede


def _importar_pela_cli(job, teto='a'):
    return _cli('--envelope', '--teto-modo-dados', teto, 'sugestao', 'importar', '--job', job)


def _pacote(job):
    return contratos.ler(job / 'sugestoes' / 'pacote-modelo.json', 'pacote-modelo/2')


def _sha_pacote(job):
    return hashlib.sha256((job / 'sugestoes' / 'pacote-modelo.json').read_bytes()).hexdigest()


def _sugestoes_do_claude(job, ids, sha=None, itens=SUGESTOES):
    """O sugestoes.json que o Claude escreveria depois de ler o pacote: so ids e funcoes do enum."""
    dados = {'esquema': 'sugestoes/1', 'pacote_sha256': sha or _sha_pacote(job),
             'sugestoes': [{'layer_id': ids[n], 'funcao': f, 'alternativa': a} for n, f, a in itens]}
    arq = job / 'sugestoes' / 'sugestoes.json'
    arq.write_text(json.dumps(dados), encoding='utf-8')
    return dados


def _permitidas(kv):
    """Os layer_ids que podem ir como miniatura no modo (a): os casos que entram (sinteticos.CASOS_MINIATURAS)."""
    return sorted(kv['ids'][n] for n, entra in sinteticos.CASOS_MINIATURAS.items() if entra)


def _ids_de_texto(laudo):
    """As camadas com texto que o laudo ve: de texto e smart object com texto dentro."""
    out = set()
    for c in laudo['camadas']:
        resumo = ((c.get('smart_object') or {}).get('abertura') or {}).get('resumo') or {}
        if c['tipo'] == 'texto' or c.get('texto') or resumo.get('n_textos'):
            out.add(c['identidade']['layer_id'])
    return out


def _nomes_e_textos(kv):
    laudo = _laudo(kv['job'])
    termos = {c['nome'] for c in laudo['camadas']} | {sinteticos.TEXTO_SINTETICO}
    return sorted(termos)


def _assinaturas_de_fonte(kv):
    """Bytes e caminhos das fontes do job: nenhum pode estar no que o Claude le."""
    arquivos_fonte = sorted(Path(kv['fontes']).iterdir())
    bytes_fonte = [p.read_bytes()[12:76] for p in arquivos_fonte]  # numero-neutro: um trecho da tabela de diretorio
    caminhos = [p.name for p in arquivos_fonte] + [str(kv['fontes']), 'entrada/fontes', 'entrada\\fontes']
    return bytes_fonte, caminhos


def _conferir_fonte(kv):
    """0 byte, 0 caminho e 0 miniatura de glifo de fonte no que o Claude le. Devolve o numero de achados."""
    job = kv['job']
    bytes_fonte, caminhos = _assinaturas_de_fonte(kv)
    achados = 0
    for p in sorted((job / 'sugestoes').rglob('*')):
        if not p.is_file() or p.name == 'segredos-bloqueados.json':
            continue
        dados = p.read_bytes()
        achados += sum(b in dados for b in bytes_fonte)
        achados += dados[:4] in (b'\x00\x01\x00\x00', b'OTTO', b'wOFF', b'wOF2', b'ttcf', b'true')
        texto = dados.decode('utf-8', 'replace')
        achados += sum(c in texto for c in caminhos)
    pasta = job / 'sugestoes' / 'miniaturas'
    if pasta.exists():
        com_texto = _ids_de_texto(_laudo(job))
        achados += sum(int(p.stem) in com_texto for p in pasta.glob('*.png') if p.stem.isdigit())
    return achados


def _pacote_bate_com_o_modo(kv, modo):
    """O criterio da 9.8 (pacote por modo, secao 4 do plano): os dois pacotes no modo; (a) com as miniaturas so das
    permitidas; (b) e (c) sem a pasta; (c) sem nome nem texto no que o Claude le. Devolve a lista do que nao bate."""
    job = kv['job']
    falhas = []
    p = _pacote(job)
    specs = contratos.ler(job / 'sugestoes' / 'pacote-specs.json', 'pacote-specs/1')
    if p['modo_dados'] != modo or specs['modo_dados'] != modo:
        falhas.append('modo')
    if p['exposto'] != EXPOSTO[modo]:
        falhas.append('exposto')
    pasta = job / 'sugestoes' / 'miniaturas'
    if modo == 'a':
        esperado = [i for i in _permitidas(kv)]
        indice = json.loads((pasta / 'indice.json').read_text(encoding='utf-8')) if pasta.exists() else {}
        if sorted(i['layer_id'] for i in indice.get('miniaturas', [])) != esperado:
            falhas.append('indice')
        if sorted(x.name for x in pasta.iterdir()) != sorted(['%d.png' % i for i in esperado] + ['indice.json']):
            falhas.append('pasta')
        if p['miniaturas'] != ['sugestoes/miniaturas/%d.png' % i for i in esperado]:
            falhas.append('lista')
    elif pasta.exists() or p['miniaturas']:
        falhas.append('miniaturas_fora_do_a')
    if modo == 'c':
        texto = _legivel_pelo_claude(job)
        if any(t in texto for t in _nomes_e_textos(kv)):
            falhas.append('nome_ou_texto_no_c')
    if kv['segredo'] and kv['segredo'] in _legivel_pelo_claude(job) + _log(job):
        falhas.append('segredo')
    return falhas


def _escolha_de_teste(job, modo):
    """A escolha do modo pelo ato da tela no modo de teste (origem fixture_de_teste), como test_sugestao_pacote.py."""
    ato = ta.atos_do_job(job)['modo_dados']
    disparo = humano.exigir_tela(modo_dados.ESCOLHER, humano.abrir_sessao_tela(teste=True), confirmado=True)
    return ato.executar(disparo, {'modo': modo})


def _gravar_medicao(chave, valor):
    destino = os.environ.get(VARIAVEL_MEDICAO)
    if not destino:
        return
    arq = Path(destino)
    try:
        dados = json.loads(arq.read_text(encoding='utf-8')) if arq.is_file() else {}
    except ValueError:
        dados = {}
    dados[chave] = valor
    arq.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding='utf-8')


# ------------------------------------------------------------------ o DA confirma as funcoes e salva (modo de teste)
def _passo_2(kv):
    return {'funcoes': {str(k): {'funcao': v, 'observacao': None} for k, v in kv['funcoes'].items()},
            'design': {f: {'regra': r, 'x': x, 'y': y} for f, (r, x, y) in USADAS.items()}}


def _confirmar_e_salvar(job, kv, antes_do_rascunho=None):
    """O DA, no modo de teste da tela (como test_tela_salvar.py): as funcoes do passo 2 e o Design system no rascunho,
    cada familia confirmada na janela e "Salvar e seguir". O modo de dados fica o que o DA ja escolheu."""
    conteudo = te.montar(job)
    s = tsv._servidor(job, conteudo)  # noqa: SLF001
    try:
        biscoito = tts._entrar(s)  # noqa: SLF001
        if antes_do_rascunho:
            antes_do_rascunho(s, biscoito, conteudo)
        escolhas = {gid: {'versao': f['versoes'][0] if f['versoes'] else None, 'confirmada': False, 'edicoes': []}
                    for gid, f in conteudo['familias'].items()}
        assert tsv._gravar_rascunho(s, biscoito, escolhas, _passo_2(kv)) == 200  # noqa: SLF001
        for gid, f in escolhas.items():
            assert tsv._ato(s, biscoito, 'familia', {'familia': gid, 'versao': f['versao'],  # noqa: SLF001
                                                     'edicoes': f['edicoes']})[1] == 200, gid
        codigo, c2, _p = tsv._salvar(s, biscoito, job)  # noqa: SLF001
    finally:
        s.parar()
    assert (codigo, c2) == (200, 200)


def _fases_invalidas(job):
    from desdobra.job import nucleo
    return sorted(nucleo.fases_invalidas(job))


# ------------------------------------------------------------------ defeito achado pelo roteiro (corrigido)
# refazer_pacotes regravava os pacotes do Claude, entao saidas das fases ler e specs, e a troca de modo deixava a
# derivacao, a tela e o render em fases_desatualizadas. Os pacotes passaram a ser Fase.refeitas (fora da validade;
# testes/test_job_pacotes_por_modo.py)
@pytest.mark.parametrize('modo', ['a', 'b'])
def test_trocar_o_modo_nao_desatualiza_as_fases_do_job(kv_e1, tmp_path, modo):
    from desdobra.job import nucleo
    kv = _copia(kv_e1, tmp_path)
    job = kv['job']
    assert nucleo.fases_invalidas(job) == set()
    te.montar(job)
    escolher_modo_do_da(job, modo)
    sp.refazer_pacotes(job)  # o que o ato do modo na tela e o "sugestao pacote" fazem
    assert _pacote(job)['modo_dados'] == modo
    assert nucleo.fases_invalidas(job) == set()
    te.montar(job)  # a tela reaberta depois da escolha do DA


# ------------------------------------------------------------------ o roteiro
def test_roteiro_da_sugestao_nos_tres_modos(kv_e1, tmp_path, capsys):
    kv = _copia(kv_e1, tmp_path)
    job, ids, segredo = kv['job'], kv['ids'], kv['segredo']
    laudo = _laudo(job)
    medicao = {}

    # 1. o job nasce sem modo: o estado guarda nulo, nao ha escolha gravada e o pacote sai no (c)
    assert contratos.ler(job / 'estado.json', 'estado/1')['modo_dados'] is None
    assert modo_dados.ler(job) is None and modo_dados.efetivo(job) == 'c'
    assert _pacote_bate_com_o_modo(kv, 'c') == []
    assert not (job / 'sugestoes' / 'miniaturas').exists()

    # 2. a escolha do (a) no modo de teste da tela deixa o job em (c), sem a pasta das miniaturas
    assert _escolha_de_teste(job, 'a') == {'modo': 'a'}
    reg = modo_dados.ler(job)
    assert reg['valor'] == 'a' and reg['origem'] == 'fixture_de_teste'
    assert modo_dados.efetivo(job) == 'c'
    env, _t = _pacote_pela_cli(job, 'a')
    assert env['modo_dados'] == 'c' and env['contagens']['miniaturas'] == 0
    assert _ocorrencias_do_segredo(kv, env) == 0
    assert _pacote_bate_com_o_modo(kv, 'c') == []
    assert not (job / 'sugestoes' / 'miniaturas').exists()

    # 3 a 6 com a tela do modo de teste aberta antes da escolha do DA, como os testes do salvar: a tela de teste
    # recusa abrir num job que ja tem escolha do DA
    estado_passos = {}

    def com_a_tela_aberta(s, biscoito, conteudo):
        # 3. a escolha do (a) pelo DA e o "sugestao pacote" do Claude
        escolher_modo_do_da(job, 'a')
        env, parede_pacote = _pacote_pela_cli(job, 'a')
        medicao['sugestao_pacote_s'] = {'envelope': env['numeros']['tempo_s'], 'parede': round(parede_pacote, 3)}
        assert env['modo_dados'] == 'a' and env['ids']['pacote_sha256'] == _sha_pacote(job)
        assert env['contagens']['miniaturas'] == len(_permitidas(kv))
        assert env['contagens']['segredos_bloqueados'] >= 1
        assert _pacote_bate_com_o_modo(kv, 'a') == []
        p = _pacote(job)
        bloqueada = next(c for c in p['camadas'] if c['layer_id'] == ids['segredo'])
        assert bloqueada.get('segredo_bloqueado') and 'nome' not in bloqueada
        # o segredo vira bloqueio: 0 ocorrencia no envelope, no log e nos pacotes
        assert segredo not in json.dumps(env, ensure_ascii=False) + _log(job) + _legivel_pelo_claude(job)
        # nenhuma miniatura de camada com texto, de camada oculta, de recorte sobre texto ou de id repetido
        mini = {i['layer_id'] for i in json.loads(_ler(job, 'sugestoes/miniaturas/indice.json'))['miniaturas']}
        assert not mini & _ids_de_texto(laudo)
        for nome in ('oculta-mini', 'recorte-sobre-texto-mini', 'repetido-a-mini', 'smart-com-texto-mini',
                     'smart-png-mini', 'smart-com-smart-mini', 'grupo-mini', 'segredo'):
            assert ids[nome] not in mini, nome
        assert _conferir_fonte(kv) == 0
        # o pacote refeito no modo novo nao desatualiza fase nenhuma (test_trocar_o_modo_nao_desatualiza_as_fases_do_job)
        estado_passos.update(invalidas=_fases_invalidas(job))
        assert estado_passos['invalidas'] == []

        # 4. o sugestoes.json sintetico, no lugar do Claude, importado pelo "sugestao importar"
        dados = _sugestoes_do_claude(job, ids, sha=env['ids']['pacote_sha256'])
        codigo, env_imp, parede_importar = _importar_pela_cli(job)
        medicao['sugestao_importar_s'] = {'envelope': env_imp['numeros']['tempo_s'],
                                          'parede': round(parede_importar, 3)}
        assert codigo == 0 and env_imp['situacao'] == 'ok'
        assert env_imp['contagens'] == {'aceitas': len(SUGESTOES), 'recusadas': 0}
        validadas = contratos.ler(job / 'sugestoes' / 'sugestoes-validadas.json', 'sugestoes/1')
        assert validadas['modo_dados'] == 'a' and validadas['pacote_sha256'] == dados['pacote_sha256']
        assert validadas['sugestoes'] == sorted(dados['sugestoes'], key=lambda s: s['layer_id'])
        assert segredo not in json.dumps(env_imp) + _ler(job, 'sugestoes/sugestoes-validadas.json') + _log(job)

        # 5. a tela mostra as sugestoes sem gravar: nenhum campo com valor antes do clique do DA
        briefing_antes = (job / mb.ARQUIVO).read_bytes()
        na_tela = tf.sugestoes_na_tela(job)
        assert na_tela['modo'] == 'a' and na_tela['sugestoes'] == validadas['sugestoes']
        assert set(na_tela) == {'modo', 'sha256', 'sugestoes'}
        assert conteudo['sugestoes']() == na_tela
        lido = json.loads(tts._pedir(s, '/api/sugestoes', cookie=biscoito)[2])  # noqa: SLF001
        assert lido['sugestoes'] == na_tela['sugestoes'] and lido['sha256'] == na_tela['sha256']
        # o que a tela entrega ao DA depois da importacao: o rascunho lido pela pagina (GET /api/rascunho) continua
        # sem passo 2, e as pendencias do passo 2 calculadas com ele ainda pedem a funcao de toda camada visivel,
        # inclusive das que tem sugestao (a sugestao nao vira valor nem na resposta da tela)
        codigo_r, _cab, corpo_r = tts._pedir(s, '/api/rascunho', cookie=biscoito)  # noqa: SLF001
        assert codigo_r == 200
        rascunho_da_tela = json.loads(corpo_r)['rascunho']
        assert rascunho_da_tela is None or not any(rascunho_da_tela.get(k) for k in tr.CAMPOS_DO_PASSO_2)
        pend = tf.pendencias(laudo, rascunho_da_tela or {})
        pede_funcao = {x['camada'] for x in pend if x['tipo'] == 'funcao'}
        # toda camada visivel ainda pede a funcao do DA (a oculta no KV nao entra na lista do passo 2)
        assert pede_funcao >= set(kv['funcoes']) - {ids['oculta-mini']}
        sugeridas = {x['layer_id'] for x in na_tela['sugestoes']} - {ids['grupo-mini']}  # o grupo nao e folha
        assert sugeridas and sugeridas <= pede_funcao
        assert not (job / tr.ARQUIVO).exists()
        assert (job / mb.ARQUIVO).read_bytes() == briefing_antes
        estado_passos.update(na_tela=na_tela)

    # 6. o DA confirma as funcoes e salva: a metrica vai para medicoes/sugestao.json, com a conta exata
    _confirmar_e_salvar(job, kv, com_a_tela_aberta)
    na_tela = estado_passos['na_tela']
    b = mb.ler(job)
    assert b['cabecalho']['origem'] == 'fixture_de_teste'
    assert {x['layer_id']: x['funcao']['valor'] for x in b['funcoes']} == kv['funcoes']  # nenhuma sugestao virou valor
    assert b['sugestoes_ref'] == na_tela['sha256']
    m = contratos.ler(job / acerto.ARQUIVO, acerto.ESQUEMA)['briefing']['a']
    # a referencia e a funcao do DA resolvida pelo motor: a camada oculta no KV fica de fora da conta
    contadas = set(kv['funcoes']) - {kv['ids']['oculta-mini']}
    total = len(contadas)
    assert m['situacao'] == 'medido' and m['sugestoes_ref'] == na_tela['sha256']
    # certas: fundo, titulo e a folha do grupo (pela heranca); erradas com a alternativa certa: logo e smart limpo
    assert m['por_camada'] == {'certas': 3, 'total': total, 'acerto': round(3 / total, 3)}
    assert m['alternativa'] == {'certas': 2, 'total': total, 'acerto': round(2 / total, 3)}
    assert m['cobertura'] == {'com_sugestao': 5, 'total': total, 'cobertura': round(5 / total, 3)}
    assert m['por_decisao']['certas'] == 3 and m['por_decisao']['total'] == total
    assert {c['layer_id'] for c in m['camadas']} == contadas
    bruto = _ler(job, str(acerto.ARQUIVO))
    for termo in _nomes_e_textos(kv) + [segredo]:
        assert termo not in bruto, termo
    medicao['acerto_a'] = {k: m[k] for k in ('por_camada', 'por_decisao', 'alternativa', 'cobertura')}
    # o salvar depois da troca de modo, registrado na medicao (as fases ficam em dia: teste acima)
    ev = [json.loads(x) for x in _log(job).splitlines() if '"briefing_confirmado"' in x][-1]
    medicao['salvar_depois_da_troca'] = {'fases_invalidas': estado_passos['invalidas'], 'derivado': ev['derivado'],
                                         'motivo': ev.get('motivo')}
    # com as fases em dia, o "Salvar e seguir" depois da troca de modo deriva (antes da correcao: derivado falso,
    # motivo fases_desatualizadas)
    assert ev['derivado'] is True, ev

    # 7. troca para (b): pacotes no (b), sem a pasta; as sugestoes do (a) ficam no disco, mas a tela nao as mostra e o
    # importador recusa o pacote velho
    escolher_modo_do_da(job, 'b')
    env_b, _t = _pacote_pela_cli(job, 'a')
    assert env_b['modo_dados'] == 'b' and _pacote_bate_com_o_modo(kv, 'b') == []
    assert not (job / 'sugestoes' / 'miniaturas').exists()
    assert (job / 'sugestoes' / 'sugestoes.json').is_file()
    assert tf.sugestoes_na_tela(job) == {'modo': 'b', 'sha256': None, 'sugestoes': []}
    codigo, env_velho, _t = _importar_pela_cli(job)
    assert codigo != 0 and env_velho['contagens'].get('recusa_pacote_velho') == 1
    dados_b = _sugestoes_do_claude(job, ids, sha=env_b['ids']['pacote_sha256'])
    codigo, env_imp_b, _t = _importar_pela_cli(job)
    assert codigo == 0 and env_imp_b['contagens']['aceitas'] == len(SUGESTOES)
    assert tf.sugestoes_na_tela(job)['modo'] == 'b'
    assert tf.sugestoes_na_tela(job)['sugestoes'] == sorted(dados_b['sugestoes'], key=lambda s: s['layer_id'])
    assert _ocorrencias_do_segredo(kv, env_b, env_velho, env_imp_b) == 0
    assert _conferir_fonte(kv) == 0

    # 8. troca para (c): pacotes no (c), sem a pasta, sem as sugestoes do Claude, sem nome nem texto legivel
    escolher_modo_do_da(job, 'c')
    env_c, _t = _pacote_pela_cli(job, 'a')
    assert env_c['modo_dados'] == 'c' and env_c['contagens']['sugestoes_apagadas'] == 2
    assert _pacote_bate_com_o_modo(kv, 'c') == []
    for rel in ESCRITOS_DO_CLAUDE:
        assert not (job / rel).exists(), rel
    assert tf.sugestoes_na_tela(job) == {'modo': 'c', 'sha256': None, 'sugestoes': []}
    _sugestoes_do_claude(job, ids)
    codigo, env_imp_c, _t = _importar_pela_cli(job)
    assert codigo != 0 and env_imp_c['contagens'].get('recusa_modo_c') == 1
    assert not (job / 'sugestoes' / 'sugestoes-validadas.json').exists()
    assert _ocorrencias_do_segredo(kv, env_c, env_imp_c) == 0
    assert _conferir_fonte(kv) == 0

    with capsys.disabled():
        print('\n[medicao E1] tempo do sugestao pacote: %s s; do sugestao importar: %s s; acerto no (a): %s'
              % (medicao['sugestao_pacote_s'], medicao['sugestao_importar_s'], json.dumps(medicao['acerto_a'])))
    _gravar_medicao('roteiro', medicao)


def test_queda_de_teto_para_c_com_a_escolha_a_gravada(kv_e1, tmp_path):
    kv = _copia(kv_e1, tmp_path)
    job, ids = kv['job'], kv['ids']
    escolher_modo_do_da(job, 'a')
    env, _t = _pacote_pela_cli(job, 'a')
    _sugestoes_do_claude(job, ids, sha=env['ids']['pacote_sha256'])
    assert _importar_pela_cli(job)[0] == 0
    assert (job / 'sugestoes' / 'miniaturas').is_dir()
    # a agencia baixa o teto para (c), sem clique do DA: a skill chama o motor com o teto novo
    env_c, _t = _pacote_pela_cli(job, 'c')
    assert env_c['modo_dados'] == 'c' and env_c['contagens']['sugestoes_apagadas'] == 2
    assert _pacote_bate_com_o_modo(kv, 'c') == []
    for rel in ESCRITOS_DO_CLAUDE:
        assert not (job / rel).exists(), rel
    # a escolha do DA continua gravada como ele deixou; so o efetivo cai
    reg = modo_dados.ler(job)
    assert reg['valor'] == 'a' and reg['origem'] == 'da'
    assert modo_dados.efetivo(job, 'c') == 'c'
    assert tf.sugestoes_na_tela(job, teto='c') == {'modo': 'c', 'sha256': None, 'sugestoes': []}
    # e a importacao com o teto (c) e recusada, mesmo com a escolha (a)
    _sugestoes_do_claude(job, ids)
    codigo, env_imp, _t = _importar_pela_cli(job, teto='c')
    assert codigo != 0 and env_imp['contagens'].get('recusa_modo_c') == 1
    assert _ocorrencias_do_segredo(kv, env, env_c, env_imp) == 0
    assert _conferir_fonte(kv) == 0


# ------------------------------------------------------------------ medicoes da secao 4 sobre os 7 jobs
def test_medicao_pacote_por_modo_nos_sete_jobs(kv_e1, kv_s1, tmp_path, capsys):
    """Os PSD sinteticos de S1 e de E1, cada um nos tres modos, mais a queda de teto: os dois pacotes batem com o modo
    escolhido em 7 de 7 (meta 100%, criterio da 9.8); o segredo, 0 ocorrencia no que o Claude le, no log e em cada
    envelope do "sugestao pacote"; a fonte, 0 byte, 0 caminho e 0 miniatura de glifo; nenhuma fase desatualizada
    pelo pacote refeito (test_trocar_o_modo_nao_desatualiza_as_fases_do_job)."""
    linhas = []

    def medir(rotulo, modo, kv, modo_esperado, envelopes):
        linhas.append({'rotulo': rotulo, 'modo': modo, 'falhas': _pacote_bate_com_o_modo(kv, modo_esperado),
                       'fonte': _conferir_fonte(kv), 'segredo': _ocorrencias_do_segredo(kv, *envelopes),
                       'invalidas': _fases_invalidas(kv['job']), 'kv': kv})
    for rotulo, base in (('S1', kv_s1), ('E1', kv_e1)):
        for modo in ('a', 'b', 'c'):
            kv = _copia(base, tmp_path / ('%s-%s' % (rotulo, modo)))
            escolher_modo_do_da(kv['job'], modo)
            env, _t = _pacote_pela_cli(kv['job'], 'a')
            medir(rotulo, modo, kv, modo, [env])
    kv = _copia(kv_e1, tmp_path / 'E1-teto')
    escolher_modo_do_da(kv['job'], 'a')
    env_a, _t = _pacote_pela_cli(kv['job'], 'a')
    env_c, _t = _pacote_pela_cli(kv['job'], 'c')
    medir('E1', 'a com teto c', kv, 'c', [env_a, env_c])
    batem = sum(not x['falhas'] for x in linhas)
    fonte = sum(x['fonte'] for x in linhas)
    segredo = sum(x['segredo'] for x in linhas)
    # o segredo vira bloqueio em 100% dos jobs com segredo: a camada sai marcada, sem nome, em todo modo
    com_segredo = [x['kv'] for x in linhas if x['kv']['segredo']]
    bloqueado = sum(next(c for c in _pacote(x['job'])['camadas'] if c['layer_id'] == x['ids']['segredo'])
                    .get('segredo_bloqueado') is True for x in com_segredo)
    fases = {'%s %s' % (x['rotulo'], x['modo']): x['invalidas'] for x in linhas}
    desatualizados = sum(bool(v) for v in fases.values())
    with capsys.disabled():
        print('\n[medicao E1] pacote por modo: %d de %d jobs batem; segredo bloqueado em %d de %d, %d ocorrencias '
              '(pacotes, log e envelopes); fonte: %d achados; jobs com fases desatualizadas depois do pacote: %d de %d'
              % (batem, len(linhas), bloqueado, len(com_segredo), segredo, fonte, desatualizados, len(linhas)))
        for x in linhas:
            print('  %s modo %s: %s; fases desatualizadas: %s' % (
                x['rotulo'], x['modo'], 'bate' if not x['falhas'] else ', '.join(x['falhas']),
                ', '.join(x['invalidas']) or 'nenhuma'))
    _gravar_medicao('pacote_por_modo', {'batem': batem, 'jobs': len(linhas), 'segredo_bloqueado': bloqueado,
                                        'com_segredo': len(com_segredo), 'segredo': segredo, 'fonte': fonte,
                                        'fases_desatualizadas': fases})
    assert [(x['rotulo'], x['modo'], x['falhas']) for x in linhas if x['falhas']] == []
    assert batem == len(linhas) == 7
    assert segredo == 0 and fonte == 0 and bloqueado == len(com_segredo) == 4
    assert desatualizados == 0, fases


def test_medicao_escolha_de_teste_deixa_o_job_em_c(kv_e1, kv_s1, tmp_path, capsys):
    """A escolha do modo no modo de teste da tela (origem fixture_de_teste) deixa o job em (c) em 100% das tentadas,
    para cada modo pedido e nos dois PSD, sem a pasta das miniaturas e sem sugestao importada."""
    tentadas, em_c = 0, 0
    for rotulo, base in (('S1', kv_s1), ('E1', kv_e1)):
        for modo in ('a', 'b'):
            kv = _copia(base, tmp_path / ('%s-%s' % (rotulo, modo)))
            job = kv['job']
            assert _escolha_de_teste(job, modo) == {'modo': modo}
            env, _t = _pacote_pela_cli(job, 'a')
            _sugestoes_do_claude(job, kv['ids'])
            codigo, env_imp, _t = _importar_pela_cli(job)
            ok = (modo_dados.ler(job)['origem'] == 'fixture_de_teste' and modo_dados.efetivo(job) == 'c'
                  and env['modo_dados'] == 'c' and _pacote_bate_com_o_modo(kv, 'c') == []
                  and not (job / 'sugestoes' / 'miniaturas').exists()
                  and codigo != 0 and env_imp['contagens'].get('recusa_modo_c') == 1
                  and not (job / 'sugestoes' / 'sugestoes-validadas.json').exists())
            tentadas += 1
            em_c += ok
    with capsys.disabled():
        print('\n[medicao E1] escolha de teste: %d de %d tentadas deixam o job em (c)' % (em_c, tentadas))
    _gravar_medicao('escolha_de_teste', {'em_c': em_c, 'tentadas': tentadas})
    assert em_c == tentadas == 4


def test_regra_das_miniaturas_no_psd_do_roteiro(kv_e1):
    """O PSD do roteiro traz cada caso de S1 e a camada do segredo, que sem o segredo seria permitida."""
    laudo = _laudo(kv_e1['job'])
    nomes = set(_ids(laudo))
    assert nomes == set(sinteticos.CASOS_MINIATURAS) | {'segredo'}
    camada = next(c for c in laudo['camadas'] if c['identidade']['layer_id'] == kv_e1['ids']['segredo'])
    limpa = dict(camada, nome='logo-mini')
    assert mm.miniatura_permitida(limpa, laudo, pasta_laudo=kv_e1['job'] / 'laudo')
    # pela forma, a camada do segredo entraria; e o detector de segredos que a tira da lista das miniaturas
    assert mm.miniatura_permitida(camada, laudo, pasta_laudo=kv_e1['job'] / 'laudo')
    assert mm.camadas_permitidas(laudo, pasta_laudo=kv_e1['job'] / 'laudo') == _permitidas(kv_e1)
