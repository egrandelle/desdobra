# -*- coding: utf-8 -*-
"""Relatorio da entrega e manifesto de licenca (M6, fatia 5 da proposta; arquitetura-v1.md, 5.8, 5.9 e 9.7;
decisoes-v1.md, arquitetura nº 19 e 136 a 143).

O relatorio-entrega.json e montado em desdobra.entrega.validar (relatorio()); daqui saem as partes que fecham o job:
  - ambiente: as versoes do encoder desta build (Pillow, libjpeg-turbo, zlib) contra a build de referencia
    (entrega.encoder_build_referencia) e, do render.json de cada formato, as versoes do render e o sha256 de cada
    arquivo de fonte usado, que liga a entrega ao arquivo congelado;
  - limites: a citacao (limites.obter(id).citacao()) de cada limite da entrega;
  - fontes_dos_campos: de onde vem cada numero do registro de arquivo que nao esta dentro de uma verificacao com fonte
    ou de uma citacao (bytes e dimensao medidos no arquivo, parametros do encoder, medidas da busca de qualidade).
    numeros_sem_fonte() anda o relatorio inteiro e devolve todo numero sem fonte: o relatorio nao e gravado com um;
  - por arquivo: os hashes medidos agora (origem), a aprovacao do formato (registro e campos que mudaram desde ela) e
    o que mudou desde a entrega anterior;
  - resumo: contagens do que passou, do que avisou e do que ficou so como registro; linhas_do_resumo() e o resumo em
    portugues que a skill mostra ao DA.
Sem texto de peca: so ids, hashes, contagens, codigos de regra e valores medidos.

manifesto(): o manifesto-licenca.json da raiz do job (nunca dentro de entrega/aprovados), so registro e sem portao
(nº 19): uma entrada por arquivo de entrada/fontes/ (nome, sha256, formato e, da conferencia, o nome PostScript e a
versao da tabela name de cada face), o sha256 de fontes/conferencia.json e a frase da responsabilidade. Nao tem campo de
canal, EULA, kit web, fsType, restricao de uso desktop, titular, numero de usuarios nem comprovante.
"""
import hashlib
import json
from pathlib import Path

from desdobra import contratos, limites

ESQUEMA_MANIFESTO = 'manifesto-licenca/1'
ARQUIVO_MANIFESTO = Path('manifesto-licenca.json')
PASTA_FONTES = 'entrada/fontes/'
FRASE_RESPONSABILIDADE = ('Toda fonte enviada pela agência é tratada como fonte com direito de uso, e a responsabilidade '
                          'pela licença é da agência ou do usuário (decisoes-v1.md, arquitetura nº 19). Este manifesto '
                          'é só registro: não bloqueia, não avisa e não libera o job, e não é parecer jurídico.')
# os limites que a entrega cita alem dos entrega.* (o perfil embutido, nº 140)
LIMITES_EXTRA = ('cor.saida_perfil_embutido',)
HASHES = ('briefing_sha256', 'master_sha256', 'render_json_sha256', 'contrato_sha256')


def citacoes_da_entrega():
    """A citacao de cada limite da entrega (todos os entrega.* do registro e LIMITES_EXTRA)."""
    ids = sorted(i for i in limites.carregar() if i.startswith('entrega.')) + list(LIMITES_EXTRA)
    return [limites.obter(i).citacao() for i in ids]


def fontes_dos_campos():
    """{caminho no relatorio: fonte} dos numeros fora de verificacao com fonte e de citacao. O caminho usa [] no lugar
    do indice de lista; vale para o campo e tudo dentro dele."""
    medida = {'tipo': 'medida', 'de': 'arquivo entregue (o sha256 do registro)'}
    return {
        'contagens': {'tipo': 'contagem', 'de': 'arquivos deste relatorio'},
        'resumo': {'tipo': 'contagem', 'de': 'verificacoes deste relatorio'},
        'arquivos[].bytes': medida, 'arquivos[].largura': medida, 'arquivos[].altura': medida,
        'arquivos[].parametros_encoder.qualidade': {
            'tipo': 'medida', 'de': 'busca de qualidade pelos bytes finais (medidas_encoder.tentativas)',
            'limites': [limites.obter('entrega.jpeg_qualidade_min').citacao(),
                        limites.obter('entrega.jpeg_qualidade_max').citacao()]},
        'arquivos[].parametros_encoder.nivel_png': limites.obter('entrega.png_nivel_compressao').citacao(),
        'arquivos[].parametros_encoder.buffer_bytes': limites.obter('entrega.jpeg_buffer_bytes').citacao(),
        'arquivos[].parametros_encoder.teto': {
            'tipo': 'folha', 'arquivo': 'specs/formatos-do-job.json',
            'limite': limites.obter('entrega.peso_reprova_acima_da_leitura_decimal').citacao()},
        'arquivos[].parametros_encoder.rotacao': {'tipo': 'briefing', 'campo': 'formatos[].rotacao',
                                                  'sentido': 'parametros/entrega.json (decisão 139)'},
        'arquivos[].parametros_encoder.borda': {'tipo': 'folha', 'arquivo': 'specs/formatos-do-job.json',
                                                'campo': 'borda_1px'},
        'arquivos[].medidas_encoder': {'tipo': 'medida', 'de': 'desdobra.entrega.codificar (bytes de cada tentativa)'},
        'ambiente.render.versoes': {'tipo': 'render.json', 'campo': 'versoes'},
    }


def _folhas(no, caminho, coberto):
    if isinstance(no, dict):
        coberto = coberto or bool(no.get('fonte')) or 'limite_id' in no
        for k, v in no.items():
            yield from _folhas(v, '%s.%s' % (caminho, k) if caminho else k, coberto)
    elif isinstance(no, list):
        for v in no:
            yield from _folhas(v, caminho + '[]', coberto)
    elif isinstance(no, (int, float)) and not isinstance(no, bool):
        yield caminho, coberto


def numeros_sem_fonte(rel):
    """Caminhos (com []) dos numeros do relatorio sem fonte: fora de um objeto com 'fonte' ou de uma citacao de limite
    ('limite_id') e fora de fontes_dos_campos()."""
    campos = rel.get('fontes_dos_campos') or {}

    def declarado(c):
        return any(c == p or c.startswith(p + '.') or c.startswith(p + '[') for p in campos)
    return sorted({c for c, coberto in _folhas({k: v for k, v in rel.items() if k != 'fontes_dos_campos'}, '', False)
                   if not coberto and not declarado(c)})


def _normal(dados):
    return json.loads(json.dumps(dados, sort_keys=True))


def aprovacao_do_arquivo(item, job_id):
    """{'registro_sha256', 'aprovado_em', 'diferencas'} da aprovacao do formato (None sem ela). diferencas: os campos
    que mudaram desde a aprovacao (desdobra.entrega.aprovacao.diferencas; vazia quando o portao abriu)."""
    from desdobra.entrega import aprovacao
    reg = item.get('aprovacao')
    if reg is None:
        return None
    return {'registro_sha256': reg.get('registro_sha256'), 'aprovado_em': (reg.get('aprovado_por') or {}).get('quando'),
            'diferencas': aprovacao.diferencas(reg, job_id, item.get('origem') or {}, item['final'])}


def mudou(item, anterior):
    """Campos do formato que mudaram desde a entrega anterior (None sem entrega anterior; ['formato_novo'] quando ela
    nao tinha o formato): os hashes de origem, o sha256 do arquivo entregue e cada parametro do encoder."""
    if anterior is None:
        return None
    velho = next((a for a in anterior.get('arquivos') or [] if a.get('formato') == item['formato']), None)
    if velho is None:
        return ['formato_novo']
    antes, agora = velho.get('origem') or {}, item.get('origem') or {}
    campos = [k for k in HASHES if antes.get(k) != agora.get(k)]
    final = item['final']  # None: o encoder recusou o formato (sem arquivo)
    if velho.get('sha256') != (final.sha256 if final is not None else None):
        campos.append('arquivo_entregue_sha256')
    p_antes, p_agora = velho.get('parametros_encoder') or {}, (_normal(final.parametros) if final is not None else {})
    campos += ['parametros_encoder.%s' % k for k in sorted(set(p_antes) | set(p_agora)) if p_antes.get(k) != p_agora.get(k)]
    return campos


def ambiente(itens):
    """As versoes do encoder desta build contra a referencia e, dos render.json, as versoes do render e os sha256 das
    fontes usadas."""
    from desdobra.entrega import codificar
    vistas, versoes_render, fontes = set(), [], set()
    for it in itens:
        r = it.get('render') or {}
        if r.get('versoes') is not None:
            chave = json.dumps(r['versoes'], sort_keys=True)
            if chave not in vistas:
                vistas.add(chave)
                versoes_render.append(r['versoes'])
        fontes.update(r.get('fontes_sha256') or [])
    vers = codificar.versoes()
    return {'encoder': {'versoes': vers, 'referencia': limites.obter('entrega.encoder_build_referencia').citacao(),
                        'difere': codificar.build_difere(vers)},
            'render': {'versoes': versoes_render, 'fontes_sha256': sorted(fontes)}}


def resumo(rel):
    """Contagens do que passou, avisou, ficou so como registro e reprovou, por verificacao, e as regras de aviso e de
    registro."""
    cont = {'passou': 0, 'avisou': 0, 'so_registro': 0, 'reprovou': 0}
    nome = {'ok': 'passou', 'avisa': 'avisou', 'registra': 'so_registro', 'reprova': 'reprovou'}
    avisos, registros = {}, {}
    for a in rel['arquivos']:
        for v in a['verificacoes']:
            cont[nome[v['situacao']]] += 1
            alvo = avisos if v['situacao'] == 'avisa' else registros if v['situacao'] == 'registra' else None
            if alvo is not None:
                alvo[v['regra']] = alvo.get(v['regra'], 0) + 1
    aprovados_sem_aviso = sum(1 for a in rel['arquivos'] if a['pasta'] == 'aprovados'
                              and not any(v['situacao'] == 'avisa' for v in a['verificacoes']))
    return {'verificacoes': cont, 'aprovados_sem_aviso': aprovados_sem_aviso,
            'avisos': dict(sorted(avisos.items())), 'registros': dict(sorted(registros.items()))}


def linhas_do_resumo(rel):
    """O resumo em portugues para a saida da skill: o que passou, o que avisou e o que ficou so como registro."""
    r = rel['resumo']
    c, n = rel['contagens'], len(rel['arquivos'])

    def regras(d):
        return ', '.join('%s (%d)' % kv for kv in d.items()) or 'nada'
    return ['Passou: %d de %d arquivo(s) em entrega/aprovados, %d sem aviso; %d verificação(ões) sem ressalva.' % (
                c['aprovados'], n, r['aprovados_sem_aviso'], r['verificacoes']['passou']),
            'Avisou: %s.' % regras(r['avisos']),
            'Só registro: %s.' % regras(r['registros'])]


# ------------------------------------------------------------------ manifesto de licenca (so registro)
def manifesto(pasta, job_id, quando):
    """manifesto-licenca/1 do job: uma entrada por arquivo de entrada/fontes/ (de estado.json), com o nome PostScript e
    a versao da tabela name das faces lidas na conferencia."""
    from desdobra import __version__
    from desdobra.fontes import conferencia
    pasta = Path(pasta)
    try:
        entradas = contratos.ler(pasta / 'estado.json', 'estado/1')['entradas']
    except (OSError, contratos.ErroContrato):
        entradas = {}
    arq_conf = pasta / conferencia.ARQUIVO
    try:
        conf = contratos.ler(arq_conf, conferencia.ESQUEMA) if arq_conf.is_file() else {}
    except contratos.ErroContrato:
        conf = {}
    formato_por_sha = {a['sha256']: a.get('formato') for a in conf.get('arquivos') or []}
    faces_por_sha = {}
    for f in conf.get('faces') or []:
        faces_por_sha.setdefault(f['sha256'], []).append({'nome_ps': f.get('nome_ps'), 'versao_name': f.get('versao_name')})
    lista = []
    for rel_arq in sorted(entradas):
        if not rel_arq.startswith(PASTA_FONTES):
            continue
        sha = entradas[rel_arq]['sha256']
        lista.append({'nome': rel_arq[len(PASTA_FONTES):], 'sha256': sha,
                      'formato': formato_por_sha.get(sha) or Path(rel_arq).suffix.lower().lstrip('.') or None,
                      'faces': faces_por_sha.get(sha, [])})
    man = {'esquema': ESQUEMA_MANIFESTO, 'job_id': job_id, 'gerado_em': quando.isoformat(timespec='seconds'),
           'motor_versao': __version__, 'conferencia_fontes_sha256': conferencia.sha256(pasta),
           'responsabilidade': FRASE_RESPONSABILIDADE, 'arquivos': lista}
    contratos.validar(man, ESQUEMA_MANIFESTO)
    return man


def selo_manifesto(man):
    """sha256 do manifesto (JSON com chaves ordenadas), que o relatorio da entrega guarda."""
    return hashlib.sha256(json.dumps(man, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def conferir_manifesto(pasta, esperado):
    """None quando o manifesto da raiz do job e o desta entrega; senao o motivo. So le."""
    arq = Path(pasta) / ARQUIVO_MANIFESTO
    if not arq.is_file():
        return 'sem_manifesto'
    try:
        man = contratos.ler(arq, ESQUEMA_MANIFESTO)
    except contratos.ErroContrato:
        return 'manifesto_invalido'
    return None if esperado is not None and selo_manifesto(man) == esperado else 'manifesto_diferente'
