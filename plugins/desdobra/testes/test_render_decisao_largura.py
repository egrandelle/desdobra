# -*- coding: utf-8 -*-
"""A decisao de largura divergente do render lista so os textos que o formato desenha (avaliacao do KV C, 03/11:
a decisao do formato derivado listava textos de outra tela, que nao entram no formato). Escrito antes da correcao."""
import json
import shutil
import sys

import pytest

from desdobra.render import contrato as mc
from test_derivacao_job import job_der  # noqa: F401  (fixture do job sintetico)

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='o isolador dos filhos roda no Windows')


def test_largura_divergente_so_dos_textos_desenhados(job_der, tmp_path):
    job = tmp_path / 'copia'
    shutil.copytree(job_der['job'], job)
    arq = job / 'fontes' / 'conferencia.json'
    conf = json.loads(arq.read_text(encoding='utf-8'))
    alvo = job_der['ids']['texto-apoio']
    for c in conf['camadas']:
        if c['layer_id'] == alvo:
            c['motivos'] = [{'codigo': 'largura_divergente', 'situacao': 'bloqueante', 'descricao': 'sintetico'}]
            c['largura_erro_pct'] = -1.0
    arq.write_text(json.dumps(conf), encoding='utf-8')
    _c, bloqueios, confirmar = mc.montar(job)
    assert [x['codigo'] for x in confirmar] == ['largura_divergente'], (bloqueios, confirmar)
    # o mesmo texto fora da peca (o formato derivado nao o desenha) nao entra na decisao
    _c, bloqueios, confirmar = mc.montar(job, funcoes={alvo: 'fora_da_peca'})
    assert not [x for x in confirmar if x['codigo'] == 'largura_divergente'], confirmar
