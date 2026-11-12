# -*- coding: utf-8 -*-
"""Conferencia de fontes do M2 (arquitetura-v1.md, 4.5 e 9.3), com fontes e PSD sinteticos gerados na hora.

Um job so (fixture de modulo) cobre os casos da conferencia: par certo com erro de largura 0, nome sem par com
face da mesma familia em outro peso, arquivo faltando, glifo faltando com fallback, divergencia de largura,
par pelo id unico e por um segundo registro do name ID 6, face de dentro de uma TTC, WOFF2 e fontes com marcas de
licenca no arquivo (kit web, uso desktop proibido, fsType restrito, nenhuma licenca declarada), que passam sem
bloqueio nem aviso (decisoes-v1.md, n. 19). Os outros testes cobrem a entrada (job criar e trocar-entrada), o
servidor local, o teste de cache e a face instalada com o mesmo nome.
"""
import hashlib
import json
import os
import socket
import stat
import subprocess
import sys
from pathlib import Path

import pytest

import test_fontes_apoio as ap
from conftest import escolher_modo_do_da, psd_minimo
from desdobra import arquivos, cli, contratos
from desdobra.chromium import navegador, servidor
from desdobra.fontes import casamento, conferencia, medicao
from desdobra.job import nucleo
from desdobra.job.fases import FASES_M1
from desdobra.job.nucleo import ErroJob
from desdobra.resultado import Codigo

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='o isolador do filho roda no Windows')

C = 24.0


def _camadas():
    """(chave, trechos, largura da caixa TySh)."""
    return [
        ('certa', [('ABC', 'Inventada-Bold', C, 0)], ap.largura('ABC', C)),
        ('sem_par', [('Abc', 'Inventada-ExtraLight', C, 0)], ap.largura('Abc', C)),
        ('faltando', [('XYZ', 'Sumida-Bold', C, 0)], ap.largura('XYZ', C)),
        ('glifo', [('ABç', 'Inventada-Bold', C, 0)], ap.largura('ABB', C)),
        ('larga', [('ABC', 'Inventada-Bold', C, 0)], ap.largura('ABC', C) * 1.05),
        ('id_unico', [('Abc', 'Abreviada-ExtraBold', C, 0)], ap.largura('Abc', C, 520)),
        ('segundo_ps', [('Abc', 'Dupla-SemiBold', C, 0)], ap.largura('Abc', C, 480)),
        ('colecao', [('Abc', 'Colecao-Bold', C, 0)], ap.largura('Abc', C, 530)),
        ('woff2', [('Abc', 'Comprimida-Regular', C, 100)], ap.largura('Abc', C, 450, tracking=100)),
        ('kit', [('Abc', 'Kit-Regular', C, 0)], ap.largura('Abc', C)),
        ('desconhecido', [('Abc', 'Paga-Regular', C, 0)], ap.largura('Abc', C)),
    ]


FONTES = {
    'inventada-bold.ttf': dict(ps='Inventada-Bold', peso=400),  # usWeightClass errado para o estilo, como na pesquisa
    'inventada-thin.otf.ttf': dict(ps='Inventada-Thin', estilo='Thin', peso=100, avanco=400),
    'abreviada.ttf': dict(ps='Abreviada-XBd', familia='Abreviada', estilo='ExtraBold', peso=800, avanco=520,
                          id_unico='1.000;TESTE;Abreviada-ExtraBold'),
    'dupla.ttf': dict(ps='DuplaSemiBold-Regular', ps_mac='Dupla-SemiBold', familia='Dupla', estilo='SemiBold', peso=600,
                      avanco=480),
    'comprimida.woff2': dict(ps='Comprimida-Regular', familia='Comprimida', estilo='Regular', peso=400, avanco=450,
                             formato='woff2'),
    # build de kit web, com uso desktop proibido no texto de licenca e o bit de licenca restrita no fsType
    'kit.ttf': dict(ps='Kit-Regular', familia='Kit', estilo='Regular', peso=400, versao='Version 1.0;wfkit2',
                    licenca='Web font kit. Web use only. Desktop use is strictly prohibited.', fs_type=2),
    'paga.ttf': dict(ps='Paga-Regular', familia='Paga', estilo='Regular', peso=400, licenca=None),
}


def _limpar(pasta):
    import shutil
    if Path(pasta).exists():
        shutil.rmtree(pasta, onexc=lambda f, p, e: (os.chmod(p, stat.S_IWRITE), os.unlink(p)))


@pytest.fixture(scope='module')
def job_fontes(tmp_path_factory):
    base = tmp_path_factory.mktemp('fontes')
    camadas = _camadas()
    psd = ap.psd_textos(base / 'origem' / 'kv.psd', [(t, w) for _k, t, w in camadas])
    pasta_fontes = base / 'origem' / 'fontes'
    shas = {}
    for nome, kw in FONTES.items():
        dados = ap.fonte(**kw)
        ap.gravar(pasta_fontes, nome, dados)
        shas[nome] = hashlib.sha256(dados).hexdigest()
    ttc = ap.colecao(ap.fonte(ps='Colecao-Light', familia='Colecao', estilo='Light', peso=300, avanco=400),
                     ap.fonte(ps='Colecao-Bold', familia='Colecao', estilo='Bold', peso=700, avanco=530))
    ap.gravar(pasta_fontes, 'colecao.ttc', ttc)
    job = base / 'job'
    nucleo.criar(job, psd, 'a', fontes=[pasta_fontes])
    r = nucleo.proxima(job, todas=True)
    assert r.codigo == 0, (r.situacao, r.linhas_humanas)
    conf = contratos.ler(job / 'fontes' / 'conferencia.json', 'conferencia-fontes/1')
    ids = {k: i + 2 for i, (k, _t, _w) in enumerate(camadas)}  # layer_id 1 e o fundo
    return {'job': job, 'conf': conf, 'ids': ids, 'shas': shas, 'resultado': r}


def _par(dados, chave, ps=None):
    lid = dados['ids'][chave]
    itens = [c for c in dados['conf']['camadas'] if c['layer_id'] == lid and (ps is None or c['nome_ps'] == ps)]
    assert len(itens) == 1
    return itens[0]


def _codigos(item):
    return {m['codigo'] for m in item['motivos']}


def _face(dados, ps):
    return next(f for f in dados['conf']['faces'] if f['nome_ps'] == ps)


def test_par_certo_tem_erro_de_largura_zero_e_cdp_confere(job_fontes):
    c = _par(job_fontes, 'certa')
    assert c['face_id'] and c['metodo_casamento'] == 'nome_ps' and c['glifos_faltando'] == 0
    assert c['face_cdp_confere'] is True
    assert c['largura_erro_max_pct'] is not None and c['largura_erro_max_pct'] <= 0.01
    assert job_fontes['conf']['chromium']['feito'] is True


def test_nome_sem_par_e_face_divergente_nunca_caem_em_outro_peso(job_fontes):
    c = _par(job_fontes, 'sem_par')
    assert c['face_id'] is None and c['situacao'] == 'bloqueante'
    assert {'nome_ps_sem_par', 'face_divergente'} <= _codigos(c)


def test_arquivo_faltando(job_fontes):
    c = _par(job_fontes, 'faltando')
    assert c['face_id'] is None and _codigos(c) == {'arquivo_faltando'} and c['situacao'] == 'bloqueante'


def test_glifo_faltando_e_fallback(job_fontes):
    c = _par(job_fontes, 'glifo')
    assert c['glifos_faltando'] == 1 and c['face_cdp_confere'] is False
    assert {'glifo_faltando', 'fallback'} <= _codigos(c)


def test_largura_divergente_vira_decisao_do_da_sem_reprovar(job_fontes):
    c = _par(job_fontes, 'larga')
    assert c['decisao'] == 'pede_decisao_do_da' and 'largura_divergente' in _codigos(c)
    m = next(m for m in c['motivos'] if m['codigo'] == 'largura_divergente')
    assert m['limite']['situacao'] == 'a_calibrar' and m['limite']['efeito'] != 'reprova'
    assert 4.5 < c['largura_erro_max_pct'] < 5.0 and c['largura_erro_pct'] < 0


def test_par_pelo_id_unico_e_pelo_segundo_registro_do_name_id_6(job_fontes):
    a = _par(job_fontes, 'id_unico')
    assert a['face_id'] and a['metodo_casamento'] == 'id_unico' and a['situacao'] == 'aviso'
    assert a['face_cdp_confere'] is True and a['largura_erro_max_pct'] <= 0.01
    b = _par(job_fontes, 'segundo_ps')
    assert b['face_id'] and b['metodo_casamento'] == 'nome_ps' and b['face_cdp_confere'] is True
    assert b['largura_erro_max_pct'] <= 0.01


def test_ttc_e_woff2_aceitos_e_conferidos(job_fontes):
    col = _par(job_fontes, 'colecao')
    assert col['face_cdp_confere'] is True and col['largura_erro_max_pct'] <= 0.01
    assert _face(job_fontes, 'Colecao-Bold')['formato'] == 'ttc' and _face(job_fontes, 'Colecao-Bold')['indice'] == 1
    w = _par(job_fontes, 'woff2')
    assert w['face_cdp_confere'] is True and w['largura_erro_max_pct'] <= 0.01
    assert _face(job_fontes, 'Comprimida-Regular')['formato'] == 'woff2'


CODIGOS_DE_LICENCA = {'canal_desconhecido', 'kit_web', 'adobe_fonts', 'build_proibe_desktop', 'eula_proibe_font_face',
                      'fs_type_restrito', 'liberado_pelo_da'}


def test_fonte_com_fs_type_restrito_e_marcas_de_kit_web_passa_sem_bloqueio_nem_aviso(job_fontes):
    """decisoes-v1.md, n. 19: toda fonte enviada tem direito de uso; a licenca e da agencia ou do usuario."""
    leitura = contratos.ler(job_fontes['job'] / 'fontes' / 'bruto' / job_fontes['shas']['kit.ttf'] / 'leitura.json',
                            'leitura-fonte/1')
    assert leitura['faces'][0]['os2']['fs_type'] == 2 and 'marcas' not in leitura['faces'][0]
    for ps, chave in (('Kit-Regular', 'kit'), ('Paga-Regular', 'desconhecido')):
        f = _face(job_fontes, ps)
        assert f['situacao'] == 'ok' and all(m['situacao'] == 'ok' for m in f['motivos']), (ps, f['motivos'])
        assert 'canal' not in f and not _codigos(f) & CODIGOS_DE_LICENCA
        c = _par(job_fontes, chave)
        assert c['situacao'] == 'ok' and c['face_cdp_confere'] is True and c['largura_erro_max_pct'] <= 0.01
    todos = {m['codigo'] for x in job_fontes['conf']['faces'] + job_fontes['conf']['camadas'] for m in x['motivos']}
    assert not todos & CODIGOS_DE_LICENCA
    assert _face(job_fontes, 'Comprimida-Regular')['situacao'] == 'ok'
    assert 'licencas_sha256' not in job_fontes['conf']
    assert not (job_fontes['job'] / 'manifesto-licenca.json').exists()
    assert not (job_fontes['job'] / 'entrada' / 'licencas.json').exists()
    assert job_fontes['resultado'].codigo == 0


def test_job_nao_aceita_arquivo_de_licencas(tmp_path, capsys):
    kv = _kv(tmp_path)
    lic = tmp_path / 'licencas.json'
    lic.write_text('{}', encoding='utf-8')
    env = _envelope(['job', 'criar', tmp_path / 'job0', '--kv', kv, '--licencas', lic], capsys)
    assert env['codigo'] == Codigo.USO and not (tmp_path / 'job0').exists()
    with pytest.raises(TypeError):
        nucleo.criar(tmp_path / 'job1', kv, 'c', licencas=lic)
    job = tmp_path / 'job2'
    nucleo.criar(job, kv, 'c')
    with pytest.raises(ErroJob) as e:
        nucleo.trocar_entrada(job, 'entrada/licencas.json', lic)
    assert e.value.codigo == Codigo.USO
    with pytest.raises(ErroJob):
        nucleo.remover_entrada(job, 'entrada/licencas.json')
    assert not (job / 'entrada' / 'licencas.json').exists()
    for f in nucleo.ESTEIRA:
        assert not any('licenca' in x for x in tuple(f.entradas) + tuple(f.saidas)), f.id


def test_peso_declarado_vem_do_estilo_quando_o_os2_diverge(job_fontes):
    f = _face(job_fontes, 'Inventada-Bold')
    assert f['peso_declarado'] == 700 and f['us_weight_class'] == 400
    assert 'peso_os2_diverge_do_estilo' in _codigos(f)
    assert set(f['metricas']) == {'unidades_por_em', 'ascender', 'descender', 'cap_height', 'x_height', 'entrelinha_tipo'}
    assert f['metricas']['unidades_por_em'] == 1000 and f['metricas']['cap_height'] == 700


def test_cache_sem_copia_e_perfil_apagado(job_fontes):
    cache = job_fontes['conf']['cache']
    assert cache['copias_encontradas'] == 0 and cache['perfil_apagado'] is True and cache['arquivos_varridos'] > 0
    assert not (job_fontes['job'] / 'fontes' / '.chromium-perfil').exists()


def test_nenhuma_fonte_fora_de_entrada_fontes(job_fontes):
    assert job_fontes['conf']['varredura']['arquivos_de_fonte_fora_da_entrada'] == 0
    n, _ = conferencia.varrer_fontes_fora_da_entrada(job_fontes['job'])
    assert n == 0


def test_segunda_passada_do_laudo_aplica_b3_e_guarda_o_hash(job_fontes):
    job = job_fontes['job']
    l1 = contratos.ler(job / 'laudo' / 'laudo.json', 'laudo/1')
    l2 = contratos.ler(job / 'laudo' / 'laudo-fontes.json', 'laudo/1')
    assert l2['passada'] == 2
    assert l2['conferencia_fontes']['sha256'] == arquivos.sha256_arquivo(job / 'fontes' / 'conferencia.json')
    assert l2['conferencia_fontes']['laudo_primeira_passada_sha256'] == arquivos.sha256_arquivo(job / 'laudo' / 'laudo.json')
    antes = {c['identidade']['layer_id'] for c in l1['camadas'] if any(a['codigo'] == 'fonte_nao_conferida' for a in c['alertas'])}
    assert antes == set(job_fontes['ids'].values())
    por_id = {c['identidade']['layer_id']: c for c in l2['camadas']}
    assert not any(a['codigo'] == 'fonte_nao_conferida' for c in l2['camadas'] for a in c['alertas'])
    ids = job_fontes['ids']
    for chave in ('sem_par', 'faltando', 'glifo', 'larga'):
        assert any(m['regra'] == 'B3' for m in por_id[ids[chave]]['motivos']), chave
    for chave in ('certa', 'id_unico', 'colecao', 'woff2', 'kit'):
        assert not any(m['regra'] == 'B3' for m in por_id[ids[chave]]['motivos']), chave
    sit = {f['fonte_ps']: f['situacao'] for f in l2['fontes_usadas']}
    assert sit['Sumida-Bold'] == 'ausente' and sit['Abreviada-ExtraBold'] == 'presente'


def _bytes_das_fontes(job):
    return [p.read_bytes() for p in (job / 'entrada' / 'fontes').iterdir()]


def _sem_fonte(texto_bytes, fontes, nomes):
    for d in fontes:
        for t in navegador.trechos(d):
            assert t not in texto_bytes
    for n in nomes:
        assert n.encode('utf-8') not in texto_bytes


def test_zero_byte_ou_caminho_de_fonte_no_envelope_log_e_pacote(job_fontes, python):
    job = job_fontes['job']
    fontes = _bytes_das_fontes(job)
    nomes = list(FONTES) + ['colecao.ttc', str(job / 'entrada' / 'fontes')]
    for modo in ('a', 'b', 'c'):
        escolher_modo_do_da(job, modo)  # a escolha do DA na tela e a fonte do modo (decisoes-v1.md, 170)
        for cmd in (['fontes', 'conferir'], ['fontes', 'laudo']):
            p = subprocess.run([python, '-I', '-B', '-m', 'desdobra', '--envelope', *cmd, '--job', str(job)],
                               capture_output=True)
            assert p.returncode == 0
            env = json.loads(p.stdout.decode('utf-8').strip().splitlines()[-1])
            assert env['modo_dados'] == modo and ('conteudo' in env) == (modo != 'c')
            _sem_fonte(p.stdout, fontes, nomes)
    for rel in ('log/eventos.jsonl', 'sugestoes/pacote-modelo.json', 'fontes/conferencia.json',
                'laudo/laudo-fontes.json'):
        _sem_fonte((job / rel).read_bytes(), fontes, nomes)


def test_processo_principal_nunca_importa_o_fonttools(job_fontes, python):
    codigo = ('import sys; from desdobra.fontes import conferencia; conferencia.conferir(sys.argv[1], usar_chromium=False);'
              ' print("fontTools" in sys.modules)')
    p = subprocess.run([python, '-I', '-B', '-c', codigo, str(job_fontes['job'])], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr[-500:]
    assert p.stdout.strip().splitlines()[-1] == 'False'


# ------------------------------------------------------------------ entrada de fontes no job
def _kv(tmp_path):
    kv = tmp_path / 'origem' / 'kv.psd'
    kv.parent.mkdir(parents=True, exist_ok=True)
    kv.write_bytes(psd_minimo())
    return kv


@pytest.mark.parametrize('nome, dados, trecho', [
    ('variavel.ttf', ap.fonte(variavel=True), 'Variable font'),
    ('tipo1.pfb', b'\x80\x01' + b'\x00' * 64, 'Type 1'),
    ('tipo1-texto.pfa', b'%!PS-AdobeFont-1.0: Inventada\n', 'Type 1'),
    ('malformada.ttf', b'\x00\x01\x00\x00' + b'\x07' * 300, 'não abre'),
    ('cortada.otf', ap.fonte()[:400], 'não abre'),
    ('texto.txt', b'nao e fonte', 'não é um arquivo de fonte'),
])
def test_job_criar_recusa_fonte_fora_do_aceito(tmp_path, nome, dados, trecho):
    kv = _kv(tmp_path)
    arq = ap.gravar(tmp_path / 'origem' / 'f', nome, dados)
    job = tmp_path / 'job'
    with pytest.raises(ErroJob) as e:
        nucleo.criar(job, kv, 'c', fontes=[arq])
    assert trecho in str(e.value)
    assert not job.exists()


def test_job_criar_recusa_pacote_com_fontes(tmp_path):
    import zipfile
    kv = _kv(tmp_path)
    z = tmp_path / 'origem' / 'fontes.zip'
    with zipfile.ZipFile(z, 'w') as zf:
        zf.writestr('Inventada-Bold.ttf', ap.fonte())
    with pytest.raises(ErroJob, match='pacote'):
        nucleo.criar(tmp_path / 'job', kv, 'c', fontes=[z])


def test_job_criar_aceita_os_cinco_formatos_e_congela(tmp_path):
    kv = _kv(tmp_path)
    pasta = tmp_path / 'origem' / 'fontes'
    ap.gravar(pasta, 'a.ttf', ap.fonte())
    ap.gravar(pasta, 'b.woff', ap.fonte(ps='B-Regular', formato='woff'))
    ap.gravar(pasta, 'c.woff2', ap.fonte(ps='C-Regular', formato='woff2'))
    ap.gravar(pasta, 'd.ttc', ap.colecao(ap.fonte(ps='D-Light'), ap.fonte(ps='D-Bold')))
    (pasta / '.DS_Store').write_bytes(b'\x00\x00\x00\x01Bud1')
    estado = nucleo.criar(tmp_path / 'job', kv, 'c', fontes=[pasta])
    rels = sorted(r for r in estado['entradas'] if r.startswith('entrada/fontes/'))
    assert rels == ['entrada/fontes/a.ttf', 'entrada/fontes/b.woff', 'entrada/fontes/c.woff2', 'entrada/fontes/d.ttc']
    for r in rels:
        assert arquivos.eh_somente_leitura(tmp_path / 'job' / r)
    assert not (tmp_path / 'job' / 'fontes').exists()


def test_fonte_continua_recusada_em_campanha_e_specs_sem_mandar_instalar(tmp_path):
    kv = _kv(tmp_path)
    for opcao in ('campanha', 'specs'):
        pasta = tmp_path / ('origem-' + opcao)
        ap.gravar(pasta, 'x.ttf', ap.fonte())
        with pytest.raises(ErroJob) as e:
            nucleo.criar(tmp_path / ('job-' + opcao), kv, 'c', **{opcao: pasta})
        texto = '%s %s' % (e.value, e.value.o_que_fazer)
        assert 'entrada/fontes' in texto and 'instalad' not in texto.lower() and 'nunca recebe' not in texto


def test_trocar_entrada_acrescenta_fonte_e_invalida_so_as_fases_de_fonte(tmp_path):
    kv = _kv(tmp_path)
    job = tmp_path / 'job'
    nucleo.criar(job, kv, 'c')
    por_id = {f.id: f for f in nucleo.ESTEIRA}
    antes = {fid: nucleo.hashes_da_fase(job, por_id[fid], por_id) for fid in ('ler', 'fontes')}
    nova = ap.gravar(tmp_path / 'novas', 'nova.ttf', ap.fonte())
    estado, _avaliacao = nucleo.trocar_entrada(job, 'entrada/fontes/nova.ttf', nova)
    assert 'entrada/fontes/nova.ttf' in estado['entradas']
    depois = {fid: nucleo.hashes_da_fase(job, por_id[fid], por_id) for fid in ('ler', 'fontes')}
    # a troca de fonte muda o hash so da fase fontes (e, em cadeia, das que dependem dela); a leitura fica valida
    assert antes['ler'] == depois['ler'] and antes['fontes'] != depois['fontes']
    assert 'fontes' in por_id['laudo-fontes'].depende_de
    with pytest.raises(ErroJob, match='Variable'):
        nucleo.trocar_entrada(job, 'entrada/fontes/var.ttf', ap.gravar(tmp_path / 'novas', 'var.ttf', ap.fonte(variavel=True)))
    with pytest.raises(ErroJob, match='entrada/fontes'):
        nucleo.trocar_entrada(job, 'entrada/campanha/x.ttf', nova)


# ------------------------------------------------------------------ servidor local e cache
def test_servidor_serve_so_a_rota_propria_sem_cache_e_sem_cors():
    import http.client
    dados = ap.fonte()
    with servidor.ServidorFontes('<p>x</p>', {'f01': (dados, 'font/ttf')}) as s:
        def get(caminho, cookie=None, host=None, origem=None):
            c = http.client.HTTPConnection('127.0.0.1', s.porta, timeout=10)
            cab = {'Host': host or '127.0.0.1:%d' % s.porta}
            if cookie:
                cab['Cookie'] = cookie
            if origem:
                cab['Origin'] = origem
            c.request('GET', caminho, headers=cab)
            r = c.getresponse()
            corpo = r.read()
            c.close()
            return r, corpo
        r, _ = get('/fonte/f01')
        assert r.status == 403
        r, _ = get('/entrar/' + 'x' * 32)
        assert r.status == 404
        r, _ = get('/entrar/' + s.token)
        assert r.status == 303 and 'HttpOnly' in r.getheader('Set-Cookie')
        cookie = r.getheader('Set-Cookie').split(';')[0]
        r, corpo = get('/fonte/f01', cookie)
        assert r.status == 200 and corpo == dados and r.getheader('Cache-Control') == 'no-store'
        assert r.getheader('Access-Control-Allow-Origin') is None
        for caminho in ('/fonte/f02', '/fonte/' + hashlib.sha256(dados).hexdigest(), '/', '/entrada/fontes/a.ttf',
                        '/fonte/../estado.json', '/fonte/f01/', '/pagina/../fonte/f01'):
            assert get(caminho, cookie)[0].status == 404, caminho
        assert get('/fonte/f01', cookie, host='localhost:%d' % s.porta)[0].status == 403
        assert get('/fonte/f01', cookie, origem='http://exemplo.invalid')[0].status == 403


def _pagina_uma_face(prefixo='dsd-teste'):
    return ("<!doctype html><html><head><style>@font-face{font-family:'%s-f01';src:url('/fonte/f01');font-weight:700}"
            "</style></head><body><div class='l' id='l0' style=\"font-family:'%s-f01';font-weight:700;font-size:100px;"
            "white-space:pre;width:max-content\">ABC</div><div id='s' style='font-family:sans-serif'>ABC</div>"
            "</body></html>" % (prefixo, prefixo))


@pytest.mark.parametrize('cache_control, com_copia', [('no-store', False), ('max-age=3600', True)])
def test_teste_de_cache_acha_copia_so_quando_o_cache_e_permitido(tmp_path, cache_control, com_copia):
    """Controle positivo do metodo: com cache permitido a varredura acha a copia; com no-store, 0 copia."""
    dados = ap.fonte()
    perfil = tmp_path / 'perfil'
    with servidor.ServidorFontes(_pagina_uma_face(), {'f01': (dados, 'font/ttf')}, cache_control=cache_control) as s:
        r = navegador.conferir(s.url_entrada, perfil, ['dsd-teste-f01'], ['l0'])
    assert r['status']['dsd-teste-f01'] == 'loaded'
    v = navegador.varrer_perfil(perfil, [dados])
    assert (v['copias_encontradas'] > 0) is com_copia
    assert navegador.apagar_perfil(perfil)


def test_face_instalada_com_o_mesmo_nome_nunca_entra_no_lugar(tmp_path):
    """Sem instalar fonte no teste: a face do job ganha o nome PostScript e a familia da face que o sistema usa
    para sans-serif (descoberta pelo CDP na hora), com outras metricas. O CDP mostra a face do arquivo do job."""
    dados = ap.fonte()
    with servidor.ServidorFontes(_pagina_uma_face(), {'f01': (dados, 'font/ttf')}) as s:
        r = navegador.conferir(s.url_entrada, tmp_path / 'p0', ['dsd-teste-f01'], ['s'])
    sistema = r['cdp']['s'][0]
    assert sistema['propria'] is False
    falsa = ap.fonte(ps=sistema['nome_ps'], familia=sistema['familia'], estilo='Regular', peso=400, avanco=611)
    face = casamento.montar_faces([(hashlib.sha256(falsa).hexdigest(), {
        'formato': 'ttf', 'faces': [_leitura_face(falsa)]})])[0]
    face['servivel'] = True
    camada = {'identidade': {'layer_id': 7}, 'tipo': 'texto', 'texto': {
        'tipo_caixa': 'ponto', 'caixa_tysh': {'bounds': {'Left': 0, 'Rght': ap.largura('ABC', 50, 611)}},
        'runs': [{'texto': 'ABC', 'fonte_ps': sistema['nome_ps'], 'corpo_espaco_texto': 50, 'tracking': 0,
                  'tem_tinta': True}]}}
    pagina, plano = medicao.montar([camada], {sistema['nome_ps']: face}, [face], 'dsd-teste')
    with servidor.ServidorFontes(pagina, {face['id']: (falsa, 'font/ttf')}) as s:
        r = navegador.conferir(s.url_entrada, tmp_path / 'p1', [medicao.familia_css('dsd-teste', face['id'])],
                               medicao.ids_para_cdp(plano))
    spans = [x['id'] for x in plano['camadas'][0]['spans']]
    for sid in spans:
        assert medicao.face_confere(r['cdp'][sid], face) is True
        assert all(f['propria'] for f in r['cdp'][sid])
    assert abs(medicao.erro_largura_pct(plano['camadas'][0], r['larguras'])) <= 0.01
    # o diagnostico pede a familia pelo nome, sem @font-face: ai entra a face do sistema
    diag = r['cdp'][plano['diagnostico'][face['id']]]
    assert any(not f['propria'] and f['nome_ps'] == sistema['nome_ps'] for f in diag)


def _leitura_face(dados):
    """Leitura de face equivalente a do filho, feita aqui no processo de teste (o arquivo e nosso)."""
    import io
    from fontTools.ttLib import TTFont
    f = TTFont(io.BytesIO(dados))
    n = f['name']
    os2 = f['OS/2']
    return {'indice': 0, 'nomes': {'ps': [n.getDebugName(6)], 'familia': n.getDebugName(1), 'estilo': n.getDebugName(2),
                                   'familia_tipografica': None, 'estilo_tipografico': None, 'nome_completo': None,
                                   'id_unico': [], 'versao': n.getDebugName(5)},
            'head': {'unidades_por_em': f['head'].unitsPerEm}, 'hhea': {'ascender': 800, 'descender': -200, 'line_gap': 0},
            'os2': {'us_weight_class': os2.usWeightClass, 's_typo_ascender': 800, 's_typo_descender': -200,
                    's_typo_line_gap': 0, 's_cap_height': 700, 's_x_height': 500, 'fs_type': 0},
            'cmap': [[c, c] for c in sorted(f.getBestCmap())], 'colecao': None}


def test_mensagens_do_motor_nao_mandam_instalar_fonte():
    from conftest import PASTA_PACOTE
    for p in PASTA_PACOTE.rglob('*.py'):
        texto = p.read_text(encoding='utf-8').casefold()
        for proibido in ('ficam instaladas na máquina', 'nunca recebe nem guarda arquivo de fonte',
                         'instale a fonte', 'instalar a fonte', 'não lê arquivo de fonte'):
            assert proibido not in texto, (p.name, proibido)


# ------------------------------------------------------------------ correcoes da revisao do M2


def _envelope(argv, capsys):
    codigo = cli.principal(['--envelope'] + [str(a) for a in argv])
    env = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    contratos.validar(env, 'envelope/1')
    assert env['codigo'] == codigo
    return env


def _job_com_fontes(base, camadas, fontes):
    psd = ap.psd_textos(base / 'origem' / 'kv.psd', camadas)
    pasta = base / 'origem' / 'fontes'
    for nome, dados in fontes.items():
        ap.gravar(pasta, nome, dados)
    job = base / 'job'
    nucleo.criar(job, psd, 'c', fontes=[pasta] if fontes else None)
    return job


def test_bloqueio_de_fonte_aparece_no_job_estado_e_em_todo_job_proxima(tmp_path, capsys):
    """Repro da revisao: fonte faltando. Antes, so o primeiro job proxima --todas dizia o bloqueio."""
    camadas = [([('Abc', 'Sumida-Bold', C, 0)], ap.largura('Abc', C)),
               ([('Abc', 'Paga-Regular', C, 0)], ap.largura('Abc', C))]
    paga = ap.fonte(ps='Paga-Regular', familia='Paga', estilo='Regular', peso=400, licenca=None)
    job = _job_com_fontes(tmp_path, camadas, {'paga.ttf': paga})
    r = nucleo.proxima(job, todas=True)
    assert r.situacao == 'ok_com_bloqueio' and r.fase == 'fontes'
    env = _envelope(['job', 'estado', job], capsys)
    assert env['situacao'] == 'ok_com_bloqueio' and env['fase'] == 'fontes' and env['contagens']['bloqueios_pendentes'] == 1
    assert env['contagens']['camadas_bloqueantes'] >= 1
    env = _envelope(['job', 'proxima', job], capsys)
    assert env['situacao'] == 'ok_com_bloqueio' and env['contagens']['fases_rodadas_agora'] == 0
    assert 'trocar-entrada' in env['o_que_fazer']
    # o DA traz o arquivo que faltava: o job conclui (a fonte sem licenca declarada nao bloqueia, decisoes-v1.md, n. 19)
    sumida = ap.gravar(tmp_path / 'nova', 'sumida.ttf', ap.fonte(ps='Sumida-Bold', familia='Sumida'))
    nucleo.trocar_entrada(job, 'entrada/fontes/sumida.ttf', sumida)
    r = nucleo.proxima(job, todas=True)
    assert r.situacao == 'concluido', (r.situacao, r.o_que_fazer)
    env = _envelope(['job', 'estado', job], capsys)
    assert env['situacao'] == 'ok' and env['contagens']['bloqueios_pendentes'] == 0


def test_cache_so_vale_quando_o_controle_positivo_aparece_no_perfil(tmp_path, monkeypatch):
    camadas = [([('Abc', 'Inventada-Bold', C, 0)], ap.largura('Abc', C))]
    job = _job_com_fontes(tmp_path, camadas, {'a.ttf': ap.fonte()})
    nucleo.proxima(job, todas=True)
    conf = contratos.ler(job / 'fontes' / 'conferencia.json', 'conferencia-fontes/1')
    cache = conf['cache']
    assert cache['feito'] is True and cache['controle_encontrado'] is True and cache['copias_encontradas'] == 0
    assert cache['perfil_caracteres'] < 100 and cache['perfil_apagado'] is True
    assert conf['resumo']['cache_provado'] == 1
    # perfil num caminho longo: o Chromium nao grava cache, e o teste fica sem prova (antes: feito com 0 copia)
    falta = 240 - len(str(tmp_path)) - len('perfil') - 2  # numero-neutro: caminho acima do que o Chromium grava cache
    if falta < 30:  # numero-neutro: folga minima para montar o caminho longo
        pytest.skip('a pasta temporaria dos testes ja e longa demais para montar o caso')
    longo = tmp_path / ('p' * falta) / 'perfil'
    monkeypatch.setattr(conferencia, 'perfil_do_chromium', lambda: longo)
    conf = conferencia.conferir(job)
    assert conf['chromium']['feito'] is True
    assert conf['cache']['feito'] is False and conf['cache']['controle_encontrado'] is False
    assert conf['cache']['motivo'] == 'perfil_nao_gravou_o_controle' and conf['resumo']['cache_provado'] == 0


def test_controle_positivo_e_servido_com_cache_e_so_com_o_cookie():
    with servidor.ServidorFontes('<html><head></head></html>', {'f01': (b'\x00\x01\x00\x00X', 'font/ttf')}) as s:
        status, cab, corpo = _pedir(s.porta, b'GET /controle HTTP/1.1', [b'Host: 127.0.0.1:%d' % s.porta])
        assert status.endswith(b'403 Forbidden')
        cookie = _cookie(s)
        status, cab, corpo = _pedir(s.porta, b'GET /controle HTTP/1.1', [b'Host: 127.0.0.1:%d' % s.porta, cookie])
        assert status.endswith(b'200 OK') and s.marcador_controle in corpo
        assert cab[b'cache-control'] == servidor.CACHE_CONTROLE.encode() and cab[b'content-type'].startswith(b'text/css')
        status, cab, corpo = _pedir(s.porta, b'GET /fonte/f01 HTTP/1.1', [b'Host: 127.0.0.1:%d' % s.porta, cookie])
        assert cab[b'cache-control'] == b'no-store'


def test_trocar_entrada_recusa_nome_de_fonte_em_outra_caixa(tmp_path):
    job = _job_com_fontes(tmp_path, [([('Abc', 'Inventada-Bold', C, 0)], ap.largura('Abc', C))],
                          {'inv.ttf': ap.fonte()})
    nova = ap.gravar(tmp_path / 'nova', 'INV.TTF', ap.fonte(avanco=520))
    with pytest.raises(ErroJob, match='outra caixa') as e:
        nucleo.trocar_entrada(job, 'entrada/fontes/INV.TTF', nova)
    assert e.value.codigo == Codigo.USO
    estado = nucleo.ler_estado(job)
    assert sorted(r for r in estado['entradas'] if r.startswith('entrada/fontes/')) == ['entrada/fontes/inv.ttf']
    assert nucleo.conferir_entradas(job, estado) == []


def test_fonte_sem_arquivo_usada_so_em_espaco_sai_ausente():
    from desdobra.laudo import fontes as segunda
    laudo = {'camadas': [], 'fontes_usadas': [{'fonte_ps': 'Sumida-Regular', 'camadas': [5], 'situacao': 'nao_conferida',
                                               'so_em_espaco': True}],
             'documento': {'quadros': []}, 'recusas': []}
    conf = {'camadas': [{'layer_id': 5, 'nome_ps': 'Sumida-Regular', 'face_id': None, 'glifos_faltando': 0,
                         'face_cdp_confere': None, 'situacao': 'ok', 'decisao': None,
                         'motivos': [{'codigo': 'so_em_espaco', 'situacao': 'ok'}]}]}
    novo = segunda.aplicar_conferencia(laudo, conf, 'a' * 64, 'b' * 64)
    (f,) = novo['fontes_usadas']
    assert f['situacao'] == 'ausente' and f['so_em_espaco'] is True and f['face_id'] is None


def test_mesmo_nome_postscript_em_dois_arquivos_bloqueia_e_o_da_remove_um(tmp_path, capsys):
    camadas = [([('Abc', 'Dup-Bold', C, 0)], ap.largura('Abc', C))]
    job = _job_com_fontes(tmp_path, camadas, {'dup1.ttf': ap.fonte(ps='Dup-Bold', familia='Dup'),
                                              'dup2.ttf': ap.fonte(ps='Dup-Bold', familia='Dup', avanco=520)})
    r = nucleo.proxima(job, todas=True)
    assert r.situacao == 'ok_com_bloqueio'
    conf = contratos.ler(job / 'fontes' / 'conferencia.json', 'conferencia-fontes/1')
    (item,) = conf['camadas']
    mot = {m['codigo']: m for m in item['motivos']}
    assert mot['mais_de_um_arquivo']['situacao'] == 'bloqueante' and item['situacao'] == 'bloqueante'
    laudo = contratos.ler(job / 'laudo' / 'laudo-fontes.json', 'laudo/1')
    assert any(m['regra'] == 'B3' and 'mais_de_um_arquivo' in m['medida']['motivos']
               for c in laudo['camadas'] for m in c['motivos'])
    # o DA tira o arquivo que nao vale; so as fases de fonte ficam invalidas
    env = _envelope(['job', 'remover-entrada', job, 'entrada/fontes/dup2.ttf'], capsys)
    assert env['codigo'] == 0 and env['contagens']['fases_invalidas'] == 3
    estado = nucleo.ler_estado(job)
    assert 'entrada/fontes/dup2.ttf' not in estado['entradas'] and not (job / 'entrada' / 'fontes' / 'dup2.ttf').exists()
    assert estado['fases']['ler']['situacao'] == 'concluida' and estado['fases']['fontes']['situacao'] == 'invalidada'
    assert nucleo.proxima(job, todas=True).situacao == 'concluido'


def test_casar_com_dois_arquivos_conta_os_candidatos():
    f1 = {'id': 'f01', 'nomes_ps': ['Dup-Bold'], 'id_unico': [], 'familia': 'Dup', 'estilo': 'Bold'}
    f2 = dict(f1, id='f02')
    assert casamento.casar('Dup-Bold', [f1, f2])[2] == 2
    assert conferencia.DESCRICOES['mais_de_um_arquivo'].count('remover-entrada') == 1


def _pedir(porta, linha, cabecalhos):
    s = socket.create_connection(('127.0.0.1', porta), timeout=5)
    s.sendall(linha + b'\r\n' + b''.join(h + b'\r\n' for h in cabecalhos + [b'Connection: close']) + b'\r\n')
    out = b''
    while True:
        try:
            pedaco = s.recv(65536)
        except OSError:
            break
        if not pedaco:
            break
        out += pedaco
    s.close()
    cabeca, _sep, corpo = out.partition(b'\r\n\r\n')
    linhas = cabeca.split(b'\r\n')
    cab = {x.split(b':', 1)[0].lower(): x.split(b':', 1)[1].strip() for x in linhas[1:] if b':' in x}
    return linhas[0], cab, corpo


def _cookie(s):
    _st, cab, _c = _pedir(s.porta, b'GET /entrar/' + s.token.encode() + b' HTTP/1.1', [b'Host: 127.0.0.1:%d' % s.porta])
    return b'Cookie: ' + cab[b'set-cookie'].split(b';')[0]


def test_token_e_cookie_fora_do_ascii_nao_imprimem_nada(capfd):
    with servidor.ServidorFontes('<html></html>', {'f01': (b'\x00\x01\x00\x00X', 'font/ttf')}) as s:
        host = b'Host: 127.0.0.1:%d' % s.porta
        status, _cab, _c = _pedir(s.porta, b'GET /entrar/\xe9 HTTP/1.1', [host])
        assert status.endswith(b'404 Not Found')
        status, _cab, _c = _pedir(s.porta, b'GET /fonte/f01 HTTP/1.1', [host, b'Cookie: dsd_sessao=\xe9'])
        assert status.endswith(b'403 Forbidden')
    saida = capfd.readouterr()
    assert saida.err == '' and saida.out == ''


@pytest.mark.parametrize('nome, peso', [
    ('Thinker-Bold', 700), ('Inventada-ExtraLight', 200), ('Inventada-ExtraBoldItalic', 800), ('Abreviada-XBd', 800),
    ('Inventada-Thin', 100), ('SemiBold', 600), ('Blackwood-Regular', 400), ('Bookish-Medium', 500),
    ('Inventada-Italic', None), ('Regular', 400),
])
def test_peso_pelo_nome_usa_palavras_e_o_sufixo_de_estilo(nome, peso):
    assert casamento.peso_do_estilo(nome) == peso


def test_job_criar_ignora_appledouble_e_ds_store_com_registro(tmp_path):
    kv = tmp_path / 'origem' / 'kv.psd'
    ap.psd_textos(kv, [([('Abc', 'Inventada-Bold', C, 0)], ap.largura('Abc', C))])
    fontes = tmp_path / 'origem' / 'fontes'
    ap.gravar(fontes, 'a.ttf', ap.fonte())
    appledouble = b'\x00\x05\x16\x07' + b'\x00' * 60
    ap.gravar(fontes, '._a.ttf', appledouble)
    campanha = tmp_path / 'origem' / 'campanha'
    ap.gravar(campanha, 'foto.png', b'\x89PNG\r\n\x1a\nx')
    ap.gravar(campanha, '._foto.png', appledouble)
    ap.gravar(campanha, '.DS_Store', b'\x00\x00\x00\x01Bud1')
    job = tmp_path / 'job'
    estado = nucleo.criar(job, kv, 'c', campanha=campanha, fontes=[fontes])
    assert sorted(estado['entradas']) == ['entrada/campanha/foto.png', 'entrada/fontes/a.ttf', 'entrada/kv.psd']
    eventos = [json.loads(x) for x in (job / 'log' / 'eventos.jsonl').read_text(encoding='utf-8').splitlines()]
    assert {'evento': 'arquivos_do_sistema_ignorados', 'n': 3}.items() <= next(
        e for e in eventos if e['evento'] == 'arquivos_do_sistema_ignorados').items()


def test_cdp_sem_resposta_vira_bloqueio(tmp_path, monkeypatch):
    camadas = [([('Abc', 'Inventada-Bold', C, 0)], ap.largura('Abc', C))]
    job = _job_com_fontes(tmp_path, camadas, {'a.ttf': ap.fonte()})
    nucleo.proxima(job, fases=FASES_M1)
    real = navegador.conferir

    def sem_cdp(url, perfil, familias, ids):
        r = real(url, perfil, familias, ids)
        r['cdp'] = {i: None for i in ids}
        return r
    monkeypatch.setattr(navegador, 'conferir', sem_cdp)
    conf = conferencia.conferir(job)
    (item,) = conf['camadas']
    assert item['face_cdp_confere'] is None and item['situacao'] == 'bloqueante'
    assert any(m['codigo'] == 'cdp_sem_resposta' and m['situacao'] == 'bloqueante' for m in item['motivos'])
    (face,) = conf['faces']
    assert face['situacao'] == 'bloqueante' and 'cdp_sem_resposta' in {m['codigo'] for m in face['motivos']}
