# -*- coding: utf-8 -*-
"""CLI do motor: "desdobra <comando> ...".

Cada componente registra os proprios subcomandos com uma funcao registrar(subparsers) no proprio modulo.
O handler recebe os argumentos e devolve um desdobra.resultado.Resultado (nunca imprime direto quando o
comando pode ser chamado por skill). A CLI mostra o Resultado:
  - modo humano (padrao): linhas_humanas e "O QUE FAZER";
  - --envelope: so o envelope de saida (docs/m1-interfaces.md), filtrado pelo modo de dados do job e pelo
    detector de segredos. Nesse modo a CLI segura stdout e stderr do handler, e erro de argumento ou excecao
    viram envelope, sem eco dos argumentos nem traceback.

Componente que ainda nao existe neste build aparece com um subcomando que responde "nao disponivel".
"""
import argparse
import contextlib
import importlib
import io
import json
import sys

from desdobra import __version__
from desdobra.resultado import MODOS_DADOS, Codigo, Resultado

# modulo -> subcomandos que ele registra (usados so para o aviso de "nao disponivel" se o modulo faltar)
COMPONENTES = (
    ('desdobra.job', ('job',)),
    ('desdobra.leitor', ('ler',)),
    ('desdobra.regressao', ('regressao',)),
    ('desdobra.doctor', ('doctor',)),
    ('desdobra.limites', ('limites',)),
    ('desdobra.fontes', ('fontes',)),
    ('desdobra.ds', ('ds',)),
    ('desdobra.specs', ('spec', 'validar')),
    ('desdobra.render', ('render', 'linkado')),
    ('desdobra.briefing', ('briefing',)),
    ('desdobra.derivacao', ('derivar',)),
    ('desdobra.entrega', ('aprovar', 'entregar', 'conferir-entrega', 'parametros-entrega')),
    ('desdobra.tela', ('tela',)),
    ('desdobra.sugestao', ('sugestao',)),
)
MODULO_ENVELOPE = 'desdobra.sugestao.envelope'
# M7c, S2: comandos que recalculam o modo efetivo com o teto da linha de comando antes e depois de rodar, e refazem os
# pacotes do Claude quando o modo caiu (a agencia baixou o teto sem clique do DA) ou o KV mudou. Nome do comando ->
# atributos de args com a pasta do job, em ordem. O ler e o spec importar gravam os pacotes; o job trocar-entrada
# troca o KV e deixa o pacote do KV antigo para tras
CONFEREM_O_MODO = {'tela abrir': ('job',), 'job proxima': ('pasta_job', 'pasta'), 'ler': ('job',),
                   'spec importar': ('job',), 'job trocar-entrada': ('pasta',)}


class _ErroArgumento(Exception):
    pass


class _Analisador(argparse.ArgumentParser):
    """No modo envelope, erro de argumento vira excecao (sem imprimir os argumentos no terminal)."""
    modo_envelope = False

    def error(self, message):
        if _Analisador.modo_envelope:
            raise _ErroArgumento(message)
        super().error(message)


def _registrar_indisponivel(subparsers, nome):
    # prefix_chars que nunca aparece: todo argumento (inclusive --job) cai no resto, sem erro de uso
    p = subparsers.add_parser(nome, help='(ainda não disponível neste build)', add_help=False, prefix_chars='\x01')
    p.add_argument('resto', nargs=argparse.REMAINDER)
    p.set_defaults(executar=_indisponivel, nome_comando=nome)


def _indisponivel(args):
    return Resultado(comando=args.nome_comando, codigo=int(Codigo.NAO_DISPONIVEL), situacao='nao_disponivel',
                     o_que_fazer='Este comando ainda não existe nesta versão do motor.',
                     linhas_humanas=['O comando %s ainda não está disponível.' % args.nome_comando])


def montar_analisador():
    p = _Analisador(prog='desdobra', description='Motor do desdobramento de peças de mídia estática.')
    p.add_argument('--version', action='version', version='desdobra %s' % __version__)
    p.add_argument('--envelope', action='store_true',
                   help='Imprime só o envelope de saída filtrado pelo modo de dados (uso pelas skills)')
    p.add_argument('--teto-modo-dados', choices=MODOS_DADOS, default=None,
                   help='Teto do modo de dados autorizado pela agência; o envelope nunca passa dele')
    # M7c, M1: a pasta da biblioteca da agencia (userConfig.biblioteca_agencia), opcional; o envelope nunca a traz
    p.add_argument('--biblioteca', default=None,
                   help='Pasta da biblioteca da agência (perfis de marca); opcional')
    sub = p.add_subparsers(dest='comando', metavar='COMANDO', required=True, parser_class=_Analisador)
    for nome_modulo, nomes in COMPONENTES:
        try:
            modulo = importlib.import_module(nome_modulo)
        except ModuleNotFoundError as e:
            if e.name != nome_modulo:
                raise
            for nome in nomes:
                _registrar_indisponivel(sub, nome)
            continue
        modulo.registrar(sub)
    return p


def _modo_do_resultado(resultado, teto):
    """Modo de dados do envelope: o escolhido pelo DA na tela (desdobra.job.modo_dados, fonte unica; decisoes-v1.md,
    170), limitado pelo teto da linha de comando e pelo do estado.json; sem job ou sem escolha, 'c'. O modo_dados do
    estado.json nao vale mais como fonte."""
    if resultado.pasta_job is None:
        return 'c'
    try:
        from desdobra.job import modo_dados
        return modo_dados.efetivo(resultado.pasta_job, modo_dados.teto_do_job(resultado.pasta_job, teto))
    except (OSError, ValueError):
        return 'c'


def envelope_minimo(resultado, modo):
    """Envelope sem conteudo (equivale ao modo c). Usado quando o modulo de envelope nao esta instalado."""
    return {'esquema': 'envelope/1', 'modo_dados': modo, 'comando': resultado.comando, 'fase': resultado.fase,
            'situacao': resultado.situacao, 'codigo': int(resultado.codigo), 'o_que_fazer': resultado.o_que_fazer,
            'contagens': dict(resultado.contagens), 'ids': dict(resultado.ids), 'numeros': dict(resultado.numeros),
            'segredos_bloqueados': 0}


def _modulo_envelope():
    try:
        return importlib.import_module(MODULO_ENVELOPE)
    except ModuleNotFoundError as e:
        if e.name not in (MODULO_ENVELOPE, 'desdobra.sugestao'):
            raise
        return None


def montar_envelope(resultado, modo):
    modulo = _modulo_envelope()
    if modulo is None:
        return envelope_minimo(resultado, 'c')
    return modulo.montar(resultado, modo)


def imprimir_envelope(resultado, modo):
    """A unica impressao do modo envelope: uma linha JSON, pelo modulo de envelope quando ele existe."""
    modulo = _modulo_envelope()
    if modulo is None:
        sys.stdout.write(json.dumps(envelope_minimo(resultado, 'c'), ensure_ascii=False) + '\n')
        sys.stdout.flush()
        return
    modulo.imprimir(resultado, modo, fluxo=sys.stdout)


def _imprimir_humano(resultado):
    for linha in resultado.linhas_humanas:
        print(linha)
    if resultado.contagens:
        print('Contagens: ' + ', '.join('%s=%s' % kv for kv in resultado.contagens.items()))
    modulo = _modulo_envelope()
    if modulo is not None:
        # o DA ve no terminal onde o detector achou segredo (padrao e camada, nunca o trecho)
        for linha in modulo.avisos_de_segredo(resultado):
            print(linha)
    if resultado.o_que_fazer:
        print('\nO QUE FAZER: %s' % resultado.o_que_fazer)


def _conferir_modo(args):
    """M7c, S2: para os comandos de CONFEREM_O_MODO, refaz os pacotes do Claude se o modo efetivo de agora (com o teto
    da linha de comando) nao for o deles. Nunca derruba o comando: desdobra.sugestao.pacote.conferir_modo fecha o que
    o Claude le quando nao consegue refazer."""
    from pathlib import Path
    campos = CONFEREM_O_MODO.get(getattr(args, 'nome_comando', None))
    if not campos:
        return
    pasta = next((getattr(args, c, None) for c in campos if getattr(args, c, None)), None)
    if not pasta:
        return
    try:
        pasta = Path(pasta).resolve()
        if not (pasta / 'estado.json').is_file():
            return
        from desdobra.sugestao import pacote
        pacote.conferir_modo(pasta, getattr(args, 'teto_modo_dados', None))
    except Exception:  # noqa: BLE001 - a conferencia nunca derruba o comando
        pass


def _definir_teto_do_processo(teto):
    """M7c, S2: o teto da linha de comando vale tambem para o que o comando grava para o Claude (pacotes)."""
    try:
        from desdobra.sugestao import pacote
    except ModuleNotFoundError:
        return
    pacote.definir_teto_do_processo(teto)


def _executar(args):
    _definir_teto_do_processo(getattr(args, 'teto_modo_dados', None))
    try:
        _conferir_modo(args)
        try:
            resultado = args.executar(args)
        finally:
            _conferir_modo(args)
    finally:
        # o teto vale so para este comando (os testes chamam principal varias vezes no mesmo processo)
        _definir_teto_do_processo(None)
    if not isinstance(resultado, Resultado):
        raise TypeError('o comando %s não devolveu um Resultado' % getattr(args, 'nome_comando', '?'))
    return resultado


def principal(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, 'reconfigure'):
            fluxo.reconfigure(encoding='utf-8', errors='backslashreplace')
    envelope = '--envelope' in argv
    _Analisador.modo_envelope = envelope
    if not envelope:
        args = montar_analisador().parse_args(argv)
        resultado = _executar(args)
        _imprimir_humano(resultado)
        return int(resultado.codigo)

    teto = None
    segurado = io.StringIO()
    try:
        with contextlib.redirect_stdout(segurado), contextlib.redirect_stderr(segurado):
            args = montar_analisador().parse_args(argv)
            teto = args.teto_modo_dados
            resultado = _executar(args)
    except _ErroArgumento:
        resultado = Resultado(comando='desdobra', codigo=int(Codigo.USO), situacao='erro',
                              o_que_fazer='Os argumentos do comando estão errados. Rode o comando sem --envelope '
                                          'para ver a ajuda.')
    except SystemExit as e:
        codigo = e.code if isinstance(e.code, int) else int(Codigo.USO)
        resultado = Resultado(comando='desdobra', codigo=codigo, situacao='ok' if codigo == 0 else 'erro')
    except Exception as e:  # noqa: BLE001 - qualquer excecao vira envelope de erro, sem traceback
        resultado = Resultado(comando='desdobra', codigo=int(Codigo.ERRO_INTERNO), situacao='erro',
                              o_que_fazer='Erro interno do motor (%s). Rode o mesmo comando sem --envelope para '
                                          'ver o detalhe no terminal.' % type(e).__name__)
    modo = _modo_do_resultado(resultado, teto)
    imprimir_envelope(resultado, modo)
    return int(resultado.codigo)


if __name__ == '__main__':
    sys.exit(principal())
