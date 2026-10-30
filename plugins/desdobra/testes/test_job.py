# -*- coding: utf-8 -*-
"""Pasta do job, entradas congeladas, invalidacao por hash, codigo de retorno e portao."""
import json
import sys

import pytest

from desdobra import contratos
from desdobra.arquivos import eh_somente_leitura, sha256_arquivo
from desdobra.job import nucleo
from desdobra.job.fases import FASES_M1, Fase
from desdobra.job.nucleo import ErroJob
from desdobra.resultado import Codigo

# Um "programa de fase" sintetico: copia (com prefixo) o conteudo de uma entrada para uma saida.
COPIAR = ('import sys, pathlib; p = pathlib.Path(sys.argv[1]); '
          'o = p / sys.argv[3]; o.parent.mkdir(parents=True, exist_ok=True); '
          'o.write_bytes(b"saida:" + (p / sys.argv[2]).read_bytes())')


def fase_copia(fid, entrada, saida, depende_de=()):
    return Fase(id=fid, tipo='fase', descricao='teste %s' % fid, entradas=(entrada,), depende_de=depende_de,
                saidas=(saida,), comando=lambda pasta, e=entrada, s=saida: [sys.executable, '-I', '-c', COPIAR, str(pasta), e, s])


def fase_codigo(fid, codigo):
    return Fase(id=fid, tipo='fase', descricao='sai com %d' % codigo, entradas=('entrada/kv.psd',),
                comando=lambda pasta: [sys.executable, '-I', '-c', 'import sys; sys.exit(%d)' % codigo])


@pytest.fixture
def pastas_extra(tmp_path):
    campanha = tmp_path / 'campanha'
    campanha.mkdir()
    (campanha / 'x.txt').write_bytes(b'x1')
    (campanha / 'y.txt').write_bytes(b'y1')
    return campanha


def esteira_abc():
    return (fase_copia('a', 'entrada/campanha/x.txt', 'saidas/a.txt'),
            fase_copia('b', 'entrada/campanha/y.txt', 'saidas/b.txt'),
            fase_copia('c', 'saidas/a.txt', 'saidas/c.txt', depende_de=('a',)))


# ------------------------------------------------------------------ criar
def test_criar_monta_a_pasta_e_congela_as_entradas(tmp_path, kv_psd, pastas_extra):
    job = tmp_path / 'job'
    estado = nucleo.criar(job, kv_psd, 'b', teto_modo_dados='b', campanha=pastas_extra)
    for sub in ('entrada', 'laudo', 'log'):
        assert (job / sub).is_dir()
    contratos.ler(job / 'estado.json', 'estado/1')
    assert set(estado['entradas']) == {'entrada/kv.psd', 'entrada/campanha/x.txt', 'entrada/campanha/y.txt'}
    for rel, reg in estado['entradas'].items():
        assert reg['sha256'] == sha256_arquivo(job / rel)
        assert eh_somente_leitura(job / rel)
    assert estado['entradas']['entrada/kv.psd']['sha256'] == sha256_arquivo(kv_psd)
    assert estado['fases'] == {'ler': nucleo._registro_vazio()}
    assert estado['proxima']['tipo'] == 'fase' and estado['proxima']['fase'] == 'ler'
    eventos = [json.loads(l) for l in (job / 'log' / 'eventos.jsonl').read_text(encoding='utf-8').splitlines()]
    assert eventos[0]['evento'] == 'job_criado'
    assert not list(job.rglob('.tmp-*'))


def test_criar_recusa_entradas_erradas(tmp_path, kv_psd):
    nao_psd = tmp_path / 'falso.psd'
    nao_psd.write_bytes(b'nao e psd')
    with pytest.raises(ErroJob):
        nucleo.criar(tmp_path / 'j1', nao_psd, 'c')
    with pytest.raises(ErroJob) as e:
        nucleo.criar(tmp_path / 'j2', kv_psd, 'z')
    assert e.value.codigo == Codigo.USO
    with pytest.raises(ErroJob, match='teto'):
        nucleo.criar(tmp_path / 'j3', kv_psd, 'a', teto_modo_dados='b')
    cheia = tmp_path / 'cheia'
    cheia.mkdir()
    (cheia / 'algo').write_text('x')
    with pytest.raises(ErroJob, match='não está vazia'):
        nucleo.criar(cheia, kv_psd, 'c')


@pytest.mark.parametrize('nome, conteudo', [('fonte.otf', b'qualquer'), ('sem-extensao', b'OTTO\x00\x00'),
                                            ('outra.bin', b'wOF2abcd')])
def test_criar_recusa_arquivo_de_fonte(tmp_path, kv_psd, nome, conteudo):
    campanha = tmp_path / 'camp'
    campanha.mkdir()
    (campanha / nome).write_bytes(conteudo)
    with pytest.raises(ErroJob, match='fonte'):
        nucleo.criar(tmp_path / 'job', kv_psd, 'c', campanha=campanha)
    assert not (tmp_path / 'job').exists()


# ------------------------------------------------------------------ proxima, hash e invalidacao
def test_proxima_roda_uma_fase_por_vez_e_depois_conclui(tmp_path, kv_psd, pastas_extra):
    job = tmp_path / 'job'
    fases = esteira_abc()
    nucleo.criar(job, kv_psd, 'c', campanha=pastas_extra, fases=fases)
    r = nucleo.proxima(job, fases=fases)
    assert (r.situacao, r.fase, r.codigo) == ('ok', 'a', 0)
    assert nucleo.fases_invalidas(job, fases) == {'b', 'c'}
    r = nucleo.proxima(job, fases=fases, todas=True)
    assert r.situacao == 'concluido' and r.codigo == 0
    assert nucleo.fases_invalidas(job, fases) == set()
    estado = contratos.ler(job / 'estado.json', 'estado/1')
    assert estado['proxima']['tipo'] == 'concluido'
    assert {f: estado['fases'][f]['situacao'] for f in 'abc'} == {'a': 'concluida', 'b': 'concluida', 'c': 'concluida'}
    assert set(estado['fases']['c']['hash_entradas']) == {'saidas/a.txt'}


def test_mudar_uma_entrada_invalida_so_as_fases_que_dependem_dela(tmp_path, kv_psd, pastas_extra):
    job = tmp_path / 'job'
    fases = esteira_abc()
    nucleo.criar(job, kv_psd, 'c', campanha=pastas_extra, fases=fases)
    nucleo.proxima(job, fases=fases, todas=True)
    novo = tmp_path / 'x2.txt'
    novo.write_bytes(b'x2')
    estado, _ = nucleo.trocar_entrada(job, 'entrada/campanha/x.txt', novo, fases=fases)
    assert nucleo.fases_invalidas(job, fases) == {'a', 'c'}
    assert estado['fases']['a']['situacao'] == 'invalidada'
    assert estado['fases']['b']['situacao'] == 'concluida'
    assert eh_somente_leitura(job / 'entrada/campanha/x.txt')
    r = nucleo.proxima(job, fases=fases, todas=True)
    assert r.situacao == 'concluido'
    assert (job / 'saidas/c.txt').read_bytes() == b'saida:saida:x2'

    novo_y = tmp_path / 'y2.txt'
    novo_y.write_bytes(b'y2')
    nucleo.trocar_entrada(job, 'entrada/campanha/y.txt', novo_y, fases=fases)
    assert nucleo.fases_invalidas(job, fases) == {'b'}


def test_mesma_entrada_regravada_nao_invalida(tmp_path, kv_psd, pastas_extra):
    job = tmp_path / 'job'
    fases = esteira_abc()
    nucleo.criar(job, kv_psd, 'c', campanha=pastas_extra, fases=fases)
    nucleo.proxima(job, fases=fases, todas=True)
    igual = tmp_path / 'igual.txt'
    igual.write_bytes(b'x1')
    nucleo.trocar_entrada(job, 'entrada/campanha/x.txt', igual, fases=fases)
    assert nucleo.fases_invalidas(job, fases) == set()


def test_codigo_diferente_de_zero_interrompe(tmp_path, kv_psd):
    job = tmp_path / 'job'
    fases = (fase_codigo('um', 0), fase_codigo('dois', 7), fase_codigo('tres', 0))
    nucleo.criar(job, kv_psd, 'c', fases=fases)
    r = nucleo.proxima(job, fases=fases, todas=True)
    assert r.codigo == Codigo.FASE_FALHOU and r.situacao == 'erro' and r.fase == 'dois'
    estado = contratos.ler(job / 'estado.json', 'estado/1')
    assert estado['fases']['um']['situacao'] == 'concluida'
    assert estado['fases']['dois']['situacao'] == 'falhou' and estado['fases']['dois']['codigo'] == 7
    assert estado['fases']['tres']['situacao'] == 'pendente' and estado['fases']['tres']['tentativas'] == 0
    assert estado['proxima']['tipo'] == 'falha'
    r = nucleo.proxima(job, fases=fases)
    assert r.fase == 'dois' and r.codigo == Codigo.FASE_FALHOU
    assert contratos.ler(job / 'estado.json', 'estado/1')['fases']['dois']['tentativas'] == 2


def test_fase_sem_a_saida_prometida_falha(tmp_path, kv_psd):
    job = tmp_path / 'job'
    fase = Fase(id='promete', tipo='fase', descricao='nao grava', entradas=('entrada/kv.psd',), saidas=('laudo/x.json',),
                comando=lambda pasta: [sys.executable, '-I', '-c', 'pass'])
    nucleo.criar(job, kv_psd, 'c', fases=(fase,))
    r = nucleo.proxima(job, fases=(fase,))
    assert r.codigo == Codigo.FASE_FALHOU
    assert 'saída ausente' in contratos.ler(job / 'estado.json', 'estado/1')['fases']['promete']['motivo']


def test_portao_para_com_o_que_fazer_e_libera_depois(tmp_path, kv_psd):
    job = tmp_path / 'job'
    portao = Fase(id='briefing', tipo='portao', descricao='DA confirma', entradas=('entrada/kv.psd',),
                  o_que_fazer='Abra a tela e confirme o briefing.',
                  cumprido=lambda pasta: (pasta / 'briefing' / 'ok.json').is_file())
    fases = (fase_codigo('antes', 0), portao, fase_codigo('depois', 0))
    nucleo.criar(job, kv_psd, 'c', fases=fases)
    r = nucleo.proxima(job, fases=fases, todas=True)
    assert (r.situacao, r.codigo, r.fase) == ('portao', Codigo.PORTAO, 'briefing')
    assert r.o_que_fazer == 'Abra a tela e confirme o briefing.'
    estado = contratos.ler(job / 'estado.json', 'estado/1')
    assert estado['fases']['briefing']['situacao'] == 'aguardando_portao'
    assert estado['fases']['depois']['tentativas'] == 0
    (job / 'briefing').mkdir()
    (job / 'briefing' / 'ok.json').write_text('{}')
    r = nucleo.proxima(job, fases=fases, todas=True)
    assert r.situacao == 'concluido'


def test_entrada_alterada_fora_do_motor_e_recusada(tmp_path, kv_psd, pastas_extra):
    job = tmp_path / 'job'
    fases = esteira_abc()
    nucleo.criar(job, kv_psd, 'c', campanha=pastas_extra, fases=fases)
    (job / 'entrada' / 'campanha' / 'intruso.txt').write_bytes(b'novo')
    with pytest.raises(ErroJob) as e:
        nucleo.proxima(job, fases=fases)
    assert e.value.codigo == Codigo.RECUSADO and 'trocar-entrada' in e.value.o_que_fazer
    (job / 'entrada' / 'campanha' / 'intruso.txt').unlink()
    nucleo.proxima(job, fases=fases)


def test_trava_impede_dois_processos(tmp_path, kv_psd):
    job = tmp_path / 'job'
    nucleo.criar(job, kv_psd, 'c')
    with nucleo.Trava(job):
        with pytest.raises(ErroJob) as e:
            nucleo.proxima(job, fases=(fase_codigo('x', 0),))
    assert e.value.codigo == Codigo.OCUPADO
    assert not (job / nucleo.ARQUIVO_TRAVA).exists()


def test_esteira_do_m1_tem_a_fase_ler():
    assert [f.id for f in FASES_M1] == ['ler']
    argv = FASES_M1[0].comando('PASTA')
    assert argv[1:7] == ['-I', '-B', '-m', 'desdobra', '--envelope', 'ler'] and argv[-2:] == ['--job', 'PASTA']


def test_log_so_tem_eventos_e_codigos(tmp_path, kv_psd):
    job = tmp_path / 'job'
    segredo_no_erro = 'TEXTO-DA-PECA-QUE-NAO-PODE-IR-PARA-O-LOG'
    fase = Fase(id='quebra', tipo='fase', descricao='imprime e falha', entradas=('entrada/kv.psd',),
                comando=lambda pasta: [sys.executable, '-I', '-c',
                                       'import sys; print("%s"); sys.stderr.write("%s"); sys.exit(3)' % (segredo_no_erro, segredo_no_erro)])
    nucleo.criar(job, kv_psd, 'c', fases=(fase,))
    r = nucleo.proxima(job, fases=(fase,))
    assert segredo_no_erro in '\n'.join(r.linhas_humanas)
    assert segredo_no_erro not in (job / 'log' / 'eventos.jsonl').read_text(encoding='utf-8')
    assert segredo_no_erro not in (job / 'estado.json').read_text(encoding='utf-8')


# ------------------------------------------------------------------ correcoes da verificacao do M1
@pytest.mark.parametrize('nome, conteudo', [
    ('tipo1.pfa', b'%!PS-AdobeFont-1.0: FonteInventada'), ('bitmap.fon', b'MZ resto'), ('Bitmap.FON', b'MZ'),
    ('sem-extensao', b'%!FontType1-1.0: FonteInventada'), ('bdf.txt', b'STARTFONT 2.1'),
])
def test_criar_recusa_fonte_type1_bitmap_e_bdf(tmp_path, kv_psd, nome, conteudo):
    camp = tmp_path / 'camp'
    camp.mkdir()
    (camp / nome).write_bytes(conteudo)
    with pytest.raises(ErroJob, match='fonte'):
        nucleo.criar(tmp_path / 'job', kv_psd, 'c', campanha=camp)
    assert not (tmp_path / 'job' / 'entrada' / 'campanha').exists()


def test_criar_recusa_zip_com_fonte_e_aceita_zip_sem_fonte(tmp_path, kv_psd):
    import zipfile
    for nome, membros in (('com-ttf', {'fontes/FonteInventada-Bold.ttf': b'x'}),
                          ('disfarcada', {'leia.bin': b'OTTOresto'}),
                          ('zip-dentro', {'mais.zip': b'PK'})):
        camp = tmp_path / nome
        camp.mkdir()
        with zipfile.ZipFile(camp / 'pacote.zip', 'w') as z:
            for m, dados in membros.items():
                z.writestr(m, dados)
        with pytest.raises(ErroJob, match='fonte'):
            nucleo.criar(tmp_path / ('job-' + nome), kv_psd, 'c', campanha=camp)
    camp = tmp_path / 'limpa'
    camp.mkdir()
    with zipfile.ZipFile(camp / 'pacote.zip', 'w') as z:
        z.writestr('leia.txt', b'texto qualquer')
    estado = nucleo.criar(tmp_path / 'job-limpa', kv_psd, 'c', campanha=camp)
    assert 'entrada/campanha/pacote.zip' in estado['entradas']


def test_saida_apagada_ou_mudada_depois_de_concluir_invalida_a_fase(tmp_path, kv_psd, pastas_extra):
    job = tmp_path / 'job'
    fases = esteira_abc()
    nucleo.criar(job, kv_psd, 'c', campanha=pastas_extra, fases=fases)
    assert nucleo.proxima(job, fases=fases, todas=True).situacao == 'concluido'
    assert nucleo.fases_invalidas(job, fases) == set()
    (job / 'saidas' / 'b.txt').unlink()
    assert nucleo.fases_invalidas(job, fases) == {'b'}
    r = nucleo.proxima(job, fases=fases)
    assert (r.situacao, r.fase) == ('ok', 'b') and (job / 'saidas' / 'b.txt').is_file()
    (job / 'saidas' / 'c.txt').write_bytes(b'adulterado')
    assert nucleo.fases_invalidas(job, fases) == {'c'}
    assert nucleo.proxima(job, fases=fases).fase == 'c'
    assert nucleo.fases_invalidas(job, fases) == set()


def test_trocar_entrada_recusa_caminho_que_sobe_pasta(tmp_path, kv_psd, pastas_extra):
    job = tmp_path / 'job'
    nucleo.criar(job, kv_psd, 'c', campanha=pastas_extra)
    novo = tmp_path / 'novo.txt'
    novo.write_bytes(b'n')
    for rel in ('entrada/campanha/../../estado.json', 'entrada/../estado.json'):
        with pytest.raises(ErroJob) as e:
            nucleo.trocar_entrada(job, rel, novo)
        assert e.value.codigo == Codigo.USO
    contratos.ler(job / 'estado.json', 'estado/1')


def test_entrada_que_muda_durante_a_fase_faz_a_fase_falhar(tmp_path, kv_psd, pastas_extra):
    from desdobra.arquivos import tornar_gravavel
    job = tmp_path / 'job'
    fases = (fase_copia('a', 'entrada/campanha/x.txt', 'saidas/a.txt'),)
    nucleo.criar(job, kv_psd, 'c', campanha=pastas_extra, fases=fases)

    def executor(argv, pasta):
        alvo = pasta / 'entrada' / 'campanha' / 'x.txt'
        tornar_gravavel(alvo)
        alvo.write_bytes(b'mudou durante a fase')
        (pasta / 'saidas').mkdir(exist_ok=True)
        (pasta / 'saidas' / 'a.txt').write_bytes(b'ok')
        return 0, b'', b''
    r = nucleo.proxima(job, fases=fases, executor=executor)
    assert r.codigo == Codigo.FASE_FALHOU
    assert nucleo.ler_estado(job)['fases']['a']['motivo'] == 'uma entrada mudou durante a fase'


def test_pasta_que_nao_e_job_da_erro_claro_antes_da_trava(tmp_path):
    for chamar in (lambda: nucleo.proxima(tmp_path / 'nao-existe'),
                   lambda: nucleo.trocar_entrada(tmp_path / 'nao-existe', 'entrada/kv.psd', tmp_path / 'x')):
        with pytest.raises(ErroJob, match='estado.json') as e:
            chamar()
        assert e.value.codigo == Codigo.RECUSADO
    assert not (tmp_path / 'nao-existe').exists()


def test_kv_que_nao_existe_cita_a_opcao_kv(tmp_path):
    with pytest.raises(ErroJob) as e:
        nucleo.criar(tmp_path / 'job', tmp_path / 'nao-existe.psd', 'c')
    assert '--kv' in e.value.o_que_fazer and '--psd' not in e.value.o_que_fazer


def test_opcoes_confirmadas_pelo_da_vao_para_o_comando_da_fase(tmp_path, kv_psd):
    job = tmp_path / 'job'
    fases = (fase_copia('a', 'entrada/kv.psd', 'saidas/a.txt'),)
    nucleo.criar(job, kv_psd, 'c', fases=fases)
    vistos = []

    def executor(argv, pasta):
        vistos.append(argv)
        return nucleo._executar_comando(argv[:-2], pasta)
    nucleo.proxima(job, fases=fases, executor=executor, opcoes_da_fase=['--teto-memoria-bytes', '123'])
    assert vistos[0][-2:] == ['--teto-memoria-bytes', '123']


# ------------------------------------------------------------------ correcoes da reverificacao do M1
def executor_de_envelope(situacao, codigo=0, o_que_fazer='o que fazer da fase', contagens=None, chamadas=None):
    """Executor falso da fase ler da FASES_M1: grava as saidas e imprime o envelope dado."""
    def executor(argv, pasta):
        if chamadas is not None:
            chamadas.append(list(argv))
        for rel in FASES_M1[0].saidas:
            (pasta / rel).parent.mkdir(parents=True, exist_ok=True)
            (pasta / rel).write_text('{}', encoding='utf-8')
        env = {'esquema': 'envelope/1', 'situacao': situacao, 'codigo': codigo, 'o_que_fazer': o_que_fazer,
               'contagens': dict(contagens or {})}
        return codigo, (json.dumps(env) + '\n').encode('utf-8'), b''
    return executor


@pytest.mark.parametrize('todas', [False, True])
def test_bloqueio_da_fase_chega_ao_envelope_do_job_proxima(tmp_path, kv_psd, todas):
    contagens = {'recusas': 2, 'bloqueios_documento': 1, 'recusas_pedem_confirmacao': 1}
    job = tmp_path / 'job-ok'
    nucleo.criar(job, kv_psd, 'c')
    r = nucleo.proxima(job, todas=todas, executor=executor_de_envelope('ok_com_bloqueio', 0, 'decida com o DA',
                                                                       contagens))
    assert r.codigo == int(Codigo.OK) and r.situacao == 'ok_com_bloqueio' and r.o_que_fazer == 'decida com o DA'
    assert r.fase == 'ler'
    assert {k: r.contagens[k] for k in contagens} == contagens and r.contagens['codigo_da_fase'] == 0
    job = tmp_path / 'job-bloqueado'
    nucleo.criar(job, kv_psd, 'c')
    r = nucleo.proxima(job, todas=todas, executor=executor_de_envelope('bloqueado', int(Codigo.ORCAMENTO),
                                                                       'confirme o teto', contagens))
    assert r.codigo == int(Codigo.FASE_FALHOU) and r.situacao == 'bloqueado' and r.o_que_fazer == 'confirme o teto'
    assert r.contagens['codigo_da_fase'] == int(Codigo.ORCAMENTO) and r.contagens['recusas'] == 2


def test_todas_sem_bloqueio_continua_concluido(tmp_path, kv_psd):
    job = tmp_path / 'job'
    nucleo.criar(job, kv_psd, 'c')
    r = nucleo.proxima(job, todas=True, executor=executor_de_envelope('ok'))
    assert r.situacao == 'concluido' and r.codigo == 0 and r.o_que_fazer == nucleo.FIM_M1


def test_alarme_de_auditoria_na_fase_leva_o_que_fazer_da_auditoria(tmp_path, kv_psd):
    from desdobra import leitor
    job = tmp_path / 'job'
    nucleo.criar(job, kv_psd, 'c')
    r = nucleo.proxima(job, executor=executor_de_envelope('recusado', int(Codigo.AUDITORIA),
                                                          leitor.O_QUE_FAZER[Codigo.AUDITORIA]))
    assert r.codigo == int(Codigo.FASE_FALHOU) and r.contagens['codigo_da_fase'] == int(Codigo.AUDITORIA)
    assert r.o_que_fazer == leitor.O_QUE_FAZER[Codigo.AUDITORIA]


def test_teto_novo_do_da_roda_de_novo_a_fase_ler(tmp_path, kv_psd):
    job = tmp_path / 'job'
    nucleo.criar(job, kv_psd, 'c')
    chamadas = []
    executor = executor_de_envelope('ok_com_bloqueio', 0, 'decida com o DA', {'recusas': 1}, chamadas)
    assert nucleo.proxima(job, executor=executor).situacao == 'ok_com_bloqueio'
    assert nucleo.ler_estado(job)['fases']['ler']['opcoes'] == []
    teto = ['--teto-memoria-bytes', '999999999']
    r = nucleo.proxima(job, executor=executor, opcoes_da_fase=teto)
    assert len(chamadas) == 2 and chamadas[1][-2:] == teto and r.fase == 'ler'
    estado = contratos.ler(job / 'estado.json', 'estado/1')
    assert estado['fases']['ler']['opcoes'] == teto and estado['fases']['ler']['situacao'] == 'concluida'
    # o mesmo teto nao roda de novo; outro teto (ou o tempo) roda
    assert nucleo.proxima(job, executor=executor, opcoes_da_fase=teto).situacao == 'concluido'
    assert len(chamadas) == 2
    nucleo.proxima(job, executor=executor, opcoes_da_fase=['--tempo-max-s', '900.0'])
    assert len(chamadas) == 3
    # sem opcao nenhuma, a fase concluida fica como esta
    assert nucleo.proxima(job, executor=executor).situacao == 'concluido' and len(chamadas) == 3


def test_acrescentar_na_campanha_invalida_a_fase_ler_da_esteira_do_m1(tmp_path, kv_psd):
    job = tmp_path / 'job'
    nucleo.criar(job, kv_psd, 'c')
    nucleo.proxima(job, executor=executor_de_envelope('ok'))
    assert nucleo.fases_invalidas(job) == set()
    novo = tmp_path / 'asset.txt'
    novo.write_bytes(b'x' * 1234)
    _estado, avaliacao = nucleo.trocar_entrada(job, 'entrada/campanha/asset.txt', novo)
    assert not avaliacao['ler'][0] and 'entrada/campanha' in avaliacao['ler'][1]
    assert nucleo.fases_invalidas(job) == {'ler'}
    novo.write_bytes(b'y' * 1234)
    nucleo.proxima(job, executor=executor_de_envelope('ok'))
    nucleo.trocar_entrada(job, 'entrada/campanha/asset.txt', novo)
    assert nucleo.fases_invalidas(job) == {'ler'}
