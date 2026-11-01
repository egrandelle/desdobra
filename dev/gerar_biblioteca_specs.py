# -*- coding: utf-8 -*-
"""Gera os perfis da biblioteca inicial de specs (plugins/desdobra/biblioteca-specs/) a partir das folhas publicas.

Uso (na raiz do repositorio, com o ambiente de desenvolvimento):
  .venv/Scripts/python.exe dev/gerar_biblioteca_specs.py --pme <pdf da Eletromidia Aqui> --globo <pasta das paginas
      salvas da Globo Ads> [--saida plugins/desdobra/biblioteca-specs]

As folhas ficam fora do repositorio. O perfil guarda so os valores extraidos pelo motor, com a citacao (folha,
sha256, pagina, secao e o trecho de onde cada numero saiu), nunca a folha inteira: entram so os trechos citados.

O perfil e o que o proprio motor extrai da folha (desdobra.specs.importar), mais a curadoria abaixo: qual trecho
e o ambiente, a praca, a area segura, a borda, o nome do veiculador. A curadoria segue a mesma regra das propostas
do Claude: diz so qual trecho vai para qual campo, e o numero sai do texto literal do trecho. Os valores do perfil
ficam em rascunho: dentro de um job, quem confirma e o DA.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'plugins' / 'desdobra' / 'motor'))

from desdobra import contratos  # noqa: E402
from desdobra.specs import importar, modelo  # noqa: E402

DATA = '2026-10-31'

# Curadoria da folha PME: por pagina, o trecho do ambiente (com a segunda linha, quando ha) e o da praca.
PME = {
    5: ('Edifícios', ['Comerciais'], None), 6: ('Edifícios', ['Residenciais'], None),
    8: ('Abrigo de Ônibus', [], 'São Paulo, Salvador e Fortaleza'), 9: ('Abrigo de Ônibus', [], 'Porto Alegre'),
    10: ('Abrigo de Ônibus', [], 'Campinas'), 11: ('Abrigo de Ônibus', [], 'Fortaleza'),
    13: ('TemBici', [], 'Belo Horizonte, Curitiba, Porto Alegre e Florianópolis'),
    14: ('TemBici', [], 'Rio de Janeiro, Recife e Brasília'), 15: ('Bancas', [], 'Belo Horizonte'),
    16: ('Bancas', [], 'Rio de Janeiro, Paraná e Belo Horizonte'), 17: ('Relógio', [], 'Salvador'),
    20: ('Market Place', [], 'São Paulo'), 22: ('Metrô Tucuruvi', [], 'São Paulo'),
    27: ('Pátio Cianê', [], 'São Paulo'), 30: ('SuperShopping Osasco', [], 'São Paulo'),
    32: ('Granja Vianna', [], 'São Paulo'), 34: ('Galleria Shopping', [], 'São Paulo'),
    36: ('Iguatemi Campinas', [], 'São Paulo'), 38: ('Bossa Nova Mall', [], 'Rio de Janeiro'),
    40: ('Shopping Paralela', [], 'Bahia'), 42: ('Abrigo de Ônibus', [], 'São Paulo'),
}
# (pagina, pedaco do texto do trecho, campo, recorte_texto)
PME_OUTROS = [(42, 'sob responsabilidade da Eletromidia', 'nome', 'Eletromidia')]
# Curadoria das paginas da Globo Ads: (arquivo, pedaco do texto do trecho, campo, recorte_texto)
GLOBO = [
    ('orientacoes-gerais.html', 'deverão ter uma borda na cor preta com 1 px', 'borda_1px', None),
    ('orientacoes-gerais.html', 'o recomendável seria usar 60%', 'qualidade_jpg_recomendada', 'usar 60%'),
    ('home-super-premium.html', 'Formato de anúncio padrão Globo sem expansão', 'nome', 'Globo'),
    ('publicidade-vertical-display.html', 'Considere deixar cerca de 14%', 'area_segura', None),
]
FONTES_PUBLICAS = {
    'eletromidia': ['Folha pública "Especificações Técnicas" da Eletromidia Aqui (PME), PDF de 42 páginas, baixada com a '
                    'permissão do responsável (pesquisa/v1-estatico-sintese.md, 5)'],
    'globo-ads': ['https://negocios.globo.com/half-page/', 'https://negocios.globo.com/publicidade-vertical-display/',
                  'https://negocios.globo.com/home-super-premium/', 'https://negocios.globo.com/orientacoes-gerais/',
                  'Páginas públicas salvas pelo DA, lidas sem login (pesquisa/specs-globo-ads.md)'],
}


def _achar(doc, folha_id, pedaco, pagina=None):
    achados = [t for f in doc['folhas'] if f['id'] == folha_id for t in f['trechos']
               if pedaco in t['texto'] and (pagina is None or t['pagina'] == pagina) and t.get('papel') != 'cabecalho']
    exatos = [t for t in achados if t['texto'] == pedaco]
    achados = exatos or achados
    if len(achados) != 1:
        raise SystemExit('curadoria: o pedaço %r (folha %s, página %s) achou %d trechos' % (pedaco, folha_id, pagina, len(achados)))
    return achados[0]


def _montar(pasta_job, vid, arquivos, mapeamento_de):
    destino = pasta_job / 'entrada' / 'specs' / vid
    destino.mkdir(parents=True)
    for a in arquivos:
        shutil.copyfile(a, destino / a.name)
    doc, _info = importar.montar(pasta_job, biblioteca={})
    mapeamento = mapeamento_de(doc)
    perfil = {'veiculadores': [{'id': vid}], 'perfis': [{'id': vid, 'versao': 1}], 'mapeamento': mapeamento,
              '_arquivo': 'curadoria', 'folhas': [{'id': f['id'], 'sha256': f['sha256']} for f in doc['folhas']]}
    bib = {f['sha256']: perfil for f in doc['folhas']}
    doc, info = importar.montar(pasta_job, biblioteca=bib)
    if info['propostas_ignoradas']:
        raise SystemExit('curadoria: %d proposta(s) ignorada(s) em %s' % (info['propostas_ignoradas'], vid))
    return doc, mapeamento


def _perfil(doc, mapeamento, perfil_id, vid, nota):
    citados = set()
    for _r, _c, v in modelo.todos_os_valores(doc):
        for fon in [v.get('fonte')] + [x.get('fonte') for x in v.get('leituras') or []]:
            if fon and fon.get('trecho'):
                citados.add((fon['folha'], fon['trecho']))
                if fon.get('rotulo_trecho'):
                    citados.add((fon['folha'], fon['rotulo_trecho']))
                for extra in fon.get('trechos_adicionais') or []:
                    citados.add((fon['folha'], extra))
    for c in doc['circuitos']:
        for ref in c['trechos']:
            citados.add(tuple(ref.split(':', 1)))
    for f in doc['folhas']:
        f['trechos'] = [t for t in f['trechos'] if (f['id'], t['id']) in citados]
        f['arquivo'] = f['arquivo'].rsplit('/', 1)[-1]
        f['recortes'] = []
    doc.update(tipo='perfil', gerado_em=DATA, job_id=None, mapeamento=mapeamento)
    doc['perfis'] = [{'id': perfil_id, 'versao': 1, 'folhas_sha256': sorted(f['sha256'] for f in doc['folhas']),
                      'historico': [], 'biblioteca': None, 'nota': nota, 'fontes_publicas': FONTES_PUBLICAS[vid]}]
    doc['resumo'] = modelo.resumo(doc)
    # o registro sem valor fica implicito no arquivo (importar.perfil_da_biblioteca completa ao ler)
    modelo.enxugar_documento(doc)
    contratos.validar(doc, 'spec/1')
    erros = modelo.conferir_literais(doc)
    if erros:
        raise SystemExit('número sem trecho: %s' % erros[:5])
    return doc


def mapeamento_pme(doc):
    fid = doc['folhas'][0]['id']
    out = []
    for pagina, (ambiente, extra, praca) in sorted(PME.items()):
        t = _achar(doc, fid, ambiente, pagina)
        out.append({'folha': fid, 'pagina': pagina, 'texto': t['texto'], 'campo': 'ambiente',
                    'adicionais': [{'texto': _achar(doc, fid, e, pagina)['texto']} for e in extra]})
        if praca:
            out.append({'folha': fid, 'pagina': pagina, 'texto': _achar(doc, fid, praca, pagina)['texto'], 'campo': 'praca'})
    for pagina, pedaco, campo, corte in PME_OUTROS:
        out.append({'folha': fid, 'pagina': pagina, 'texto': _achar(doc, fid, pedaco, pagina)['texto'], 'campo': campo,
                    'recorte_texto': corte})
    return out


def mapeamento_globo(doc):
    por_nome = {f['arquivo'].rsplit('/', 1)[-1]: f['id'] for f in doc['folhas']}
    out = []
    for arquivo, pedaco, campo, corte in GLOBO:
        fid = por_nome[arquivo]
        t = _achar(doc, fid, pedaco)
        out.append({'folha': fid, 'pagina': t['pagina'], 'texto': t['texto'], 'campo': campo, 'recorte_texto': corte})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--pme', required=True, type=Path)
    ap.add_argument('--globo', required=True, type=Path)
    ap.add_argument('--saida', type=Path, default=RAIZ / 'plugins' / 'desdobra' / 'biblioteca-specs')
    a = ap.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix='desdobra-biblioteca-') as tmp:
        doc, mapa = _montar(Path(tmp) / 'pme', 'eletromidia', [a.pme], mapeamento_pme)
        pme = _perfil(doc, mapa, 'eletromidia-pme', 'eletromidia',
                      'Perfil inicial da Eletromidia Aqui (PME). Valores em rascunho: no job, quem confirma e o DA.')
        globo_arqs = [a.globo / n for n in ('half-page.html', 'home-super-premium.html',
                                            'publicidade-vertical-display.html', 'orientacoes-gerais.html')]
        doc, mapa = _montar(Path(tmp) / 'globo', 'globo-ads', globo_arqs, mapeamento_globo)
        globo = _perfil(doc, mapa, 'globo-ads', 'globo-ads',
                        'Perfil inicial da Globo Ads (display estatico). O peso por tag do Half-Page diverge entre a ficha '
                        '(550 KB) e a tabela por tamanho (500 KB na carga posterior): o perfil guarda as duas leituras, '
                        'e o DA decide no job.')
    a.saida.mkdir(parents=True, exist_ok=True)
    for nome, doc in (('eletromidia-pme-1.json', pme), ('globo-ads-1.json', globo)):
        texto = json.dumps(doc, ensure_ascii=False, indent=1) + '\n'
        (a.saida / nome).write_text(texto, encoding='utf-8', newline='\n')
        print('%s: %d formato(s), %d valor(es) com valor, %d trecho(s) citado(s)' % (
            nome, len(doc['formatos']), doc['resumo']['valores'] - doc['resumo']['sem_valor'], doc['resumo']['trechos']))
    return 0


if __name__ == '__main__':
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    sys.exit(main())
