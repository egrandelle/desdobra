# -*- coding: utf-8 -*-
"""Licenca das faces do job e rascunho do manifesto de licenca (arquitetura-v1.md, 4.5, 5.8 e 7.3).

Leitura tecnica, sem parecer juridico. A licenca e da agencia (decisoes-v1.md, arquitetura 1 e 16):
  - canal desconhecido, kit web (marca no arquivo ou canal informado), build que proibe uso desktop e canal
    Adobe Fonts dao situacao bloqueante, e so o DA libera, com justificativa (entrada/licencas.json);
  - EULA que proibe @font-face ou servidor web da aviso, registrado no manifesto, e o job segue;
  - face que declara a OFL na tabela name sai com canal ofl, fora do controle de canal.

Os dados de licenca vem do DA ou da agencia em entrada/licencas.json (licencas-fontes/1), por sha256 do
arquivo. Nada aqui le arquivo de fonte.
"""
from desdobra import limites

CANAIS_BLOQUEANTES = {'desconhecido': 'canal_desconhecido', 'kit_web': 'kit_web', 'adobe_fonts': 'adobe_fonts'}
DESCRICOES = {
    'canal_desconhecido': 'O canal de compra da fonte não foi informado. O DA confirma o canal em entrada/licencas.json.',
    'kit_web': 'O arquivo é um build de kit web (marca no arquivo ou canal informado). Só o DA libera, com justificativa.',
    'adobe_fonts': 'Fonte do Adobe Fonts: o desdobra nunca usa arquivo do Adobe Fonts. Traga o arquivo desktop por outro canal licenciado.',
    'build_proibe_desktop': 'O próprio arquivo diz que o uso desktop é proibido. Só o DA libera, com justificativa.',
    'eula_proibe_font_face': 'A EULA informada proíbe @font-face ou servidor web. O job segue e o aviso fica no manifesto.',
    'fs_type_restrito': 'O fsType do arquivo marca licença restrita. Confira a licença.',
    'liberado_pelo_da': 'Bloqueio de licença liberado pelo DA, com justificativa registrada.',
}


def entrada_da_face(licencas, face):
    """O registro de entrada/licencas.json para a face (por sha256 do arquivo e, na colecao, pelo indice)."""
    for item in (licencas or {}).get('faces') or []:
        if item.get('sha256') != face['sha256']:
            continue
        if item.get('indice') is not None and item['indice'] != face['indice']:
            continue
        return item
    return None


def motivo(codigo, situacao, medida=None, limite_id=None):
    return {'codigo': codigo, 'situacao': situacao, 'descricao': DESCRICOES.get(codigo, codigo),
            'medida': medida, 'limite': limites.obter(limite_id).citacao() if limite_id else None}


def avaliar(face, licencas):
    """(canal, registro, motivos) da licenca da face. Os motivos levam situacao bloqueante, aviso ou registra."""
    reg = entrada_da_face(licencas, face)
    marcas = set(face.get('marcas') or [])
    canal = (reg or {}).get('canal') or ('ofl' if 'ofl' in marcas else 'desconhecido')
    bloqueios = []
    if canal in CANAIS_BLOQUEANTES:
        bloqueios.append((CANAIS_BLOQUEANTES[canal], None))
    if 'kit_web' in marcas and canal != 'kit_web':
        bloqueios.append(('kit_web', 'fontes.marcas_kit_web'))
    if 'proibe_desktop' in marcas:
        bloqueios.append(('build_proibe_desktop', 'fontes.marcas_proibe_desktop'))
    out = []
    liberacao = (reg or {}).get('liberado_pelo_da') or None
    for codigo, lid in bloqueios:
        # adobe_fonts nunca e liberado: nao ha arquivo do Adobe Fonts que o desdobra possa usar (7.3, regra 3)
        if liberacao and codigo != 'adobe_fonts':
            out.append(motivo(codigo, 'aviso', {'liberado_pelo_da': True}, lid))
        else:
            out.append(motivo(codigo, 'bloqueante', None, lid))
    if liberacao and any(m['situacao'] == 'aviso' for m in out):
        out.append(motivo('liberado_pelo_da', 'aviso'))
    eula = (reg or {}).get('eula') or {}
    if eula.get('font_face') == 'proibe':
        out.append(motivo('eula_proibe_font_face', 'aviso'))
    if 'fs_type_restrito' in marcas:
        out.append(motivo('fs_type_restrito', 'aviso', {'fs_type': face.get('fs_type')}, 'fontes.fs_type_bits_restritos'))
    return canal, reg, out


def manifesto(job_id, faces, arquivos, por_face, gerado_em):
    """Rascunho de manifesto-licenca/1. por_face: {face_id: {'canal', 'registro', 'situacao', 'motivos',
    'conferencia', 'instalada_mesmo_nome'}}; arquivos: [{'sha256', 'formato', 'situacao', 'motivo'}]."""
    entradas = []
    for f in faces:
        d = por_face[f['id']]
        reg = d.get('registro') or {}
        eula = reg.get('eula') or {}
        entradas.append({
            'face_id': f['id'], 'familia': f['familia'], 'estilo': f['estilo'], 'nome_ps': f['nome_ps'],
            'arquivo_sha256': f['sha256'], 'formato': f['formato'], 'versao_name': f['versao_name'],
            'origem': 'arquivo_enviado', 'canal': d['canal'],
            'eula': {'nome': eula.get('nome'), 'versao': eula.get('versao'), 'font_face': eula.get('font_face') or 'nao_lido'},
            'titular': reg.get('titular'), 'usuarios': reg.get('usuarios'), 'comprovante_ref': reg.get('comprovante_ref'),
            'liberacao_da': reg.get('liberado_pelo_da'),
            'conferencia': d['conferencia'], 'diagnostico_instalada_mesmo_nome': d.get('instalada_mesmo_nome'),
            'situacao': d['situacao'], 'motivos': [m['codigo'] for m in d['motivos']],
        })
    situacoes = [e['situacao'] for e in entradas] + [a['situacao'] == 'recusado' and 'bloqueante' or 'ok' for a in arquivos]
    return {'esquema': 'manifesto-licenca/1', 'rascunho': True, 'job_id': job_id, 'gerado_em': gerado_em,
            'nota': 'Leitura técnica, sem parecer jurídico. A licença é da agência; o manifesto nunca guarda o arquivo da fonte.',
            'situacao': 'bloqueante' if 'bloqueante' in situacoes else ('aviso' if 'aviso' in situacoes else 'ok'),
            'faces': entradas, 'arquivos': arquivos,
            'rodape': {'disparado_por': None, 'por_onde': None, 'nota': 'Preenchido no render (M4 em diante).'}}
