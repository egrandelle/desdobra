# -*- coding: utf-8 -*-
"""Aprovacao do DA por formato (aprovacao/2, arquitetura-v1.md, 5.4; decisoes-v1.md, 138).

A aprovacao vale para o arquivo que vai para o veiculo: cada registro guarda a impressao do formato
(desdobra.derivacao.impressao; M7b, A2: mudar o briefing fora do formato nao derruba a aprovacao dele), os hashes do
master, do render.json e do contrato, o sha256 do arquivo final (desdobra.entrega.codificar) e os parametros do encoder. Mudar
qualquer um derruba a aprovacao daquele formato, e diferencas() diz qual campo mudou. O registro leva o proprio
sha256 (registro_sha256): registro mexido a mao cai. O selo e um sha256 sem segredo: pega mexida acidental, nao
falsificacao (quem refaz o registro refaz o selo); contra o Claude, quem segura e o gancho PreToolUse e o Disparo, que o
registro() e o gravar() conferem.

So grava com o Disparo que desdobra.humano.exigir('aprovar') emite depois de conferir o console, e com a trava do
job (quem chama e o "desdobra aprovar"). Um "aprovar" com varios formatos pede uma confirmacao so e grava um registro
por formato; os registros dos outros formatos ficam.

O arquivo fica em briefing/, mas o briefing nao muda com ele: o cabecalho do briefing guarda so os hashes do laudo,
das specs, do design system e da conferencia (desdobra.briefing.modelo.hashes_atuais), e nenhuma fase do job tem
padrao em briefing/ (teste).
"""
import hashlib
import json
from pathlib import Path

from desdobra import arquivos, contratos, humano

ESQUEMA = 'aprovacao/2'
# a de antes do M7b (com o sha do briefing inteiro): ler() a aceita, e o portao a conta como aprovacao caida
# (aprovacao_antiga); gravar() nao a carrega para o arquivo novo
ESQUEMA_ANTIGO = 'aprovacao/1'
ARQUIVO = Path('briefing') / 'aprovacao.json'
PASTA_ENTREGA = Path('entrega')
PASTA_ANTERIORES = 'anteriores'
PASTA_PREVIA = PASTA_ENTREGA / 'previa'
# os hashes que o registro guarda e o portao mede de novo (desdobra.entrega.portao, atual de cada formato)
HASHES = ('impressao_formato', 'master_sha256', 'render_json_sha256', 'contrato_sha256')


def selo(registro):
    """sha256 do registro sem o campo registro_sha256 (JSON com chaves ordenadas)."""
    sem = {k: v for k, v in registro.items() if k != 'registro_sha256'}
    return hashlib.sha256(json.dumps(sem, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def registro(formato, job_id, atual, final, disparo):
    """Registro de aprovacao de um formato: atual = os HASHES medidos agora; final = o ArquivoFinal mostrado ao DA.
    humano.ErroHumano sem o disparo do "aprovar" (confere sem consumir: o gravar consome)."""
    humano.conferir(disparo, 'aprovar')
    reg = {'formato': formato, 'job_id': job_id}
    reg.update({k: atual[k] for k in HASHES})
    reg['arquivo_entregue'] = {'sha256': final.sha256, 'bytes': len(final.dados), 'extensao': final.extensao}
    reg['parametros_encoder'] = json.loads(json.dumps(final.parametros, sort_keys=True))
    reg['aprovado_por'] = disparo.registro()
    reg['registro_sha256'] = selo(reg)
    return reg


def ler(pasta):
    """A aprovacao gravada (aprovacao/2, ou a antiga aprovacao/1, com o esquema dela no campo 'esquema'), ou None.
    ErroContrato quando o arquivo nao segue nenhum dos dois."""
    arq = Path(pasta) / ARQUIVO
    if not arq.is_file():
        return None
    try:
        return contratos.ler(arq, ESQUEMA)
    except contratos.ErroContrato as e:
        try:
            return contratos.ler(arq, ESQUEMA_ANTIGO)
        except contratos.ErroContrato:
            raise e from None


def diferencas(reg, job_id, atual, final=None):
    """Campos que mudaram desde a aprovacao do formato (lista vazia: a aprovacao vale). final None (o arquivo final
    nao saiu agora) nao compara o arquivo nem os parametros."""
    campos = []
    if reg.get('registro_sha256') != selo(reg):
        campos.append('registro_sha256')
    if reg.get('job_id') != job_id:
        campos.append('job_id')
    campos += [k for k in HASHES if reg.get(k) != atual.get(k)]
    if final is not None:
        if (reg.get('arquivo_entregue') or {}).get('sha256') != final.sha256:
            campos.append('arquivo_entregue_sha256')
        antes = reg.get('parametros_encoder') or {}
        agora = json.loads(json.dumps(final.parametros, sort_keys=True))
        campos += ['parametros_encoder.%s' % k for k in sorted(set(antes) | set(agora)) if antes.get(k) != agora.get(k)]
    return campos


def gravar(pasta, registros, job_id, *, disparo):
    """Grava os registros (um por formato) em briefing/aprovacao.json, por cima dos registros dos mesmos formatos.
    Os registros de outro job e os da aprovacao/1 (ja caidos) saem. humano.ErroHumano sem o disparo do "aprovar"."""
    humano.conferir(disparo, 'aprovar', consumir=True)
    pasta = Path(pasta).resolve()
    formatos = {}
    try:
        velha = ler(pasta)
    except contratos.ErroContrato:
        velha = None
    if velha is not None and velha['job_id'] == job_id and velha['esquema'] == ESQUEMA:
        formatos = dict(velha['formatos'])
    for reg in registros:
        formatos[reg['formato']] = reg
    dados = {'esquema': ESQUEMA, 'job_id': job_id, 'formatos': dict(sorted(formatos.items()))}
    contratos.gravar(pasta / ARQUIVO, dados, ESQUEMA)
    return dados


def gravar_previa(pasta, formato, final):
    """O arquivo final do formato em entrega/previa/, para o DA abrir antes de aprovar. Devolve o caminho relativo."""
    rel = PASTA_PREVIA / ('%s.%s' % (formato, final.extensao))
    arquivos.gravar_bytes_atomico(Path(pasta) / rel, final.dados)
    return rel.as_posix()
