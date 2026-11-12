# -*- coding: utf-8 -*-
"""A marca do job, escolhida pelo DA no passo 1 da tela (M7c, passo M3; decisoes-v1.md, 190, Q5).

Arquivo: briefing/marca.json, contrato marca-job/1, gravado so pelo servidor da tela com o Disparo do clique do DA
confirmado na janela (COMANDO, humano.ATOS_DA_TELA). Guarda o id da marca na biblioteca da agencia, ou a escolha
"Sem marca", com a origem e o meio do Disparo (da e tela; no modo de teste da tela, fixture_de_teste e medicao). O
nome da marca fica so no perfil da biblioteca (desdobra.marca.perfil), nunca no job.

As tres escolhas da tela, nenhuma marcada antes do DA:
  - uma marca da biblioteca: {'escolha': 'marca', 'id': <id do perfil>}, so entre os perfis que a biblioteca tem agora;
  - "Marca nova": {'escolha': 'nova', 'nome': <o nome que o DA digitou>}; o motor cria o perfil da marca na
    biblioteca (perfil.criar, versao 0, sem registro) e grava o id dele no job. Nome vazio, fora do contrato do perfil
    ou igual ao de uma marca que ja existe (chave: sem diferenca de Unicode NFC e NFD, de espacos nem de maiusculas)
    e recusado; o nome entra na forma NFC, com um espaco so entre as palavras;
  - "Sem marca": {'escolha': 'sem_marca'}, que vale sem biblioteca.
A escolha e opcional e nunca trava o "Salvar e seguir": sem o arquivo, o job segue sem padrao de marca citado. A
biblioteca ausente, vazia ou com problema nunca trava a tela: so "Sem marca" fica, com a nota de onde configurar.

O que vai ao Claude e so se ha marca escolhida (para_o_claude), nunca o nome nem o id. A pagina recebe o nome das
marcas (dado do DA, posto so por textContent) e nunca o caminho da biblioteca (na_tela).
"""
import unicodedata
from pathlib import Path

from desdobra import contratos

ARQUIVO = Path('briefing') / 'marca.json'
ESQUEMA = 'marca-job/1'
COMANDO = 'marca escolher'
ESCOLHAS = ('marca', 'nova', 'sem_marca')


class ErroMarca(Exception):
    """A escolha nao pode ser gravada como pedida. A mensagem nao leva o caminho da biblioteca."""


def ler(pasta):
    """O registro da escolha, ou None (sem arquivo ou arquivo fora do contrato)."""
    arq = Path(pasta) / ARQUIVO
    if not arq.is_file():
        return None
    try:
        return contratos.ler(arq, ESQUEMA)
    except (contratos.ErroContrato, OSError, ValueError):
        return None


def marcas(biblioteca):
    """[{'id', 'nome'}] das marcas da biblioteca, pelo nome; [] sem biblioteca ou com a pasta de marcas recusada."""
    from desdobra.marca import perfil
    if biblioteca is None:
        return []
    try:
        return [{'id': m['id'], 'nome': m['marca']} for m in perfil.listar(biblioteca)]
    except (perfil.ErroPerfil, OSError):
        return []


def forma(nome):
    """O nome como entra na biblioteca: Unicode NFC, sem os espacos das pontas e com um espaco so entre as palavras
    (qualquer espaco Unicode vira o espaco comum)."""
    return unicodedata.normalize('NFC', ' '.join(nome.split()))


def chave(nome):
    """O que diz se dois nomes sao a mesma marca (revisao do M3): a forma do nome sem diferenca de maiusculas
    (casefold, que junta tambem 'Straße' e 'STRASSE'), de novo em NFC."""
    return unicodedata.normalize('NFC', forma(nome).casefold())


def _serve_ao_perfil(nome):
    from desdobra.marca import perfil
    prova = {'esquema': perfil.ESQUEMA, 'id': perfil.novo_id(), 'marca': nome, 'criado_em': perfil.agora(), 'versao': 0,
             'atual': None, 'historico': []}
    try:
        perfil.validar(prova)
    except (contratos.ErroContrato, perfil.ErroPerfil):
        return False
    return True


def nome_novo(nome, biblioteca):
    """O nome da marca nova na forma da biblioteca (forma), ou None quando ele nao serve: vazio, fora do contrato do
    perfil (barra, controle, extensao de fonte, longo demais) ou igual ao de uma marca da biblioteca pela chave
    (Unicode, espacos e maiusculas nao fazem outra marca)."""
    if not isinstance(nome, str) or biblioteca is None:
        return None
    # o nome como veio passa antes pelo contrato: o controle entre as palavras e recusado, nunca trocado por espaco
    bruto = nome.strip()
    if not bruto or not _serve_ao_perfil(bruto):
        return None
    nome = forma(bruto)
    if not nome or not _serve_ao_perfil(nome):
        return None
    if any(chave(m['nome']) == chave(nome) for m in marcas(biblioteca)):
        return None
    return nome


def conferir(dados, biblioteca):
    """A escolha pedida pela pagina, conferida: {'escolha', 'id', 'nome'} ou None quando nao serve. biblioteca: a
    pasta da biblioteca que serve (None quando nao configurada ou com problema)."""
    if not isinstance(dados, dict) or dados.get('escolha') not in ESCOLHAS:
        return None
    escolha = dados['escolha']
    if escolha == 'sem_marca':
        return {'escolha': 'sem_marca', 'id': None, 'nome': None} if set(dados) == {'escolha'} else None
    if escolha == 'marca':
        if set(dados) != {'escolha', 'id'} or not isinstance(dados['id'], str):
            return None
        achada = next((m for m in marcas(biblioteca) if m['id'] == dados['id']), None)
        return None if achada is None else {'escolha': 'marca', 'id': achada['id'], 'nome': achada['nome']}
    if set(dados) != {'escolha', 'nome'}:
        return None
    nome = nome_novo(dados['nome'], biblioteca)
    return None if nome is None else {'escolha': 'nova', 'id': None, 'nome': nome}


def gravar(pasta, dados, *, disparo, biblioteca=None):
    """Grava a escolha do DA em briefing/marca.json. disparo: o da tela (humano.exigir_tela(COMANDO, ...)), gasto aqui
    mesmo quando a escolha e recusada. Na "Marca nova", cria antes o perfil da marca na biblioteca. ErroMarca para a
    escolha que nao serve."""
    from desdobra import humano
    from desdobra.job import nucleo
    from desdobra.marca import perfil
    humano.conferir(disparo, COMANDO, consumir=True)
    pasta = Path(pasta).resolve()
    escolha = conferir(dados, biblioteca)
    if escolha is None:
        raise ErroMarca('A escolha da marca não serve para este job.')
    with nucleo.Trava(pasta):
        estado = contratos.ler(pasta / 'estado.json', 'estado/1')
        nova = escolha['escolha'] == 'nova'
        if nova:
            try:
                marca_id = perfil.criar(biblioteca, escolha['nome'])['id']
            except perfil.ErroPerfil as e:
                raise ErroMarca(str(e)) from None
        else:
            marca_id = escolha['id']
        reg = disparo.registro()
        dados_ = {'esquema': ESQUEMA, 'job_id': estado['job_id'],
                  'escolha': 'sem_marca' if marca_id is None else 'marca', 'marca_id': marca_id,
                  'origem': disparo.origem,
                  'escolhido_por': {'usuario': reg['usuario'], 'maquina': reg['maquina'], 'meio': reg['meio'],
                                    'quando': reg['quando']}}
        contratos.gravar(pasta / ARQUIVO, dados_, ESQUEMA)
        # no log, so a escolha: nem o nome nem o id da marca
        nucleo.registrar_evento(pasta, 'marca_escolhida', escolha=dados_['escolha'], nova=nova,
                                origem=disparo.origem)
    return dados_


def escolhida(pasta, biblioteca=None):
    """A escolha gravada, como a tela mostra: {'escolha', 'id', 'nome'} ou None. O nome sai da biblioteca (None sem
    ela ou quando a marca saiu dela)."""
    reg = ler(pasta)
    if reg is None:
        return None
    if reg['escolha'] == 'sem_marca':
        return {'escolha': 'sem_marca', 'id': None, 'nome': None}
    nome = next((m['nome'] for m in marcas(biblioteca) if m['id'] == reg['marca_id']), None)
    return {'escolha': 'marca', 'id': reg['marca_id'], 'nome': nome}


def na_tela(pasta, conferencia):
    """O bloco da marca no passo 1: {'biblioteca' (desdobra.biblioteca.para_tela, sem caminho), 'marcas',
    'pode_criar', 'escolhida'}. conferencia: a da biblioteca (desdobra.biblioteca.conferir)."""
    from desdobra import biblioteca as mb
    from desdobra.arquivos import EXTENSOES_FONTE
    bib = conferencia.pasta if conferencia.usavel else None
    # revisao do M3: as extensoes de arquivo de fonte que o contrato do perfil recusa no nome, sem o ponto, para a
    # pagina avisar na linha do campo antes do pedido (a mesma lista do motor, nunca uma copia na pagina)
    return {'biblioteca': mb.para_tela(conferencia), 'marcas': marcas(bib), 'pode_criar': bib is not None,
            'escolhida': escolhida(pasta, bib), 'extensoes_fonte': [e[1:] for e in EXTENSOES_FONTE]}


def para_o_claude(pasta):
    """O que o envelope leva ao Claude: 1 quando o job tem uma marca escolhida, 0 sem escolha ou com "Sem marca"."""
    reg = ler(pasta)
    return int(reg is not None and reg['escolha'] == 'marca')
