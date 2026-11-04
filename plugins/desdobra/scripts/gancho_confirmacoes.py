# -*- coding: utf-8 -*-
"""Gancho PreToolUse do plugin: o Claude nunca dispara o que so o DA dispara.

Roda com o Python do PATH, so com a biblioteca padrao, na forma exec (hooks/hooks.json):

    python -I -B ${CLAUDE_PLUGIN_ROOT}/scripts/gancho_confirmacoes.py

Le da entrada padrao o JSON do evento (tool_name e tool_input) e nega (permissionDecision "deny"):
  - nas ferramentas Bash e PowerShell, comando que chama o render, a confirmacao de linkado, a confirmacao de spec,
    a do briefing, o aprovar, o entregar ou o parametros-entrega do desdobra (pela linha de comando ou pelo codigo
    Python do motor), que
    mexe na conferencia do disparo humano, ou que escreve num arquivo que so o DA grava;
  - nas ferramentas que gravam arquivo (Write, Edit, MultiEdit, NotebookEdit), arquivo que so o DA grava ou que so o
    motor grava: os .json de briefing/ (a aprovacao inclusive) e de derivacao/, specs/confirmacoes.json, master,
    render.json e contrato de render/, o que esta em entrega/, o manifesto e o relatorio da entrega e
    parametros/entrega.json.
Escrita pelo terminal inclui redirecao, copia, movimento e troca de nome (os.replace, os.rename, shutil,
Rename-Item, ren, Move-Item, Copy-Item) e a opcao --saida do motor. O motor chamado como desdobra, desdobra.exe,
desdobra.cli ou desdobra.__main__ conta igual. O comando e conferido como chegou e normalizado (sem aspas, sem o
escape ^ do cmd e ` do PowerShell, caminhos sem ./, // e segmento/..), e subcomando numa variavel ($c, %c%) e negado; o
caminho das ferramentas de arquivo tambem e normalizado.
Com a negacao, o Claude recebe o motivo: quem roda isso e o DA, num terminal proprio, fora do Claude. Sem negacao, o
gancho nao imprime nada e o Claude Code segue o fluxo normal de permissao. O codigo de saida e sempre 0.

Este gancho cobre o caminho direto do Claude, pelo texto do comando e pelo caminho do arquivo: nao le o conteudo de um
script gravado antes nem resolve caminho montado por partes ou nome de modulo partido, entao barra o engano e nao o
desvio feito de proposito (docs/m1-interfaces.md, M6). O motor confere o console de novo (desdobra.humano) so no
comando; um arquivo do DA escrito a mao nao tem prova de quem gravou (confirmado_por e dado sem segredo). Os riscos
residuais (esse e o de um processo do mesmo usuario, fora do Claude, que escreve teclas num console) ficam declarados.
"""
import json
import re
import sys

MOTIVO = ('O desdobra recusa este comando pelo Claude: render, confirmação de linkado, confirmação de spec, '
          'confirmação de briefing, aprovação, entrega e parâmetros de entrega só partem do DA. Peça ao DA para abrir um terminal próprio, fora do Claude, e rodar '
          'o comando lá; o desdobra pergunta e grava. Não tente outro caminho para o mesmo efeito.')
FERRAMENTAS_DE_COMANDO = ('Bash', 'PowerShell')
FERRAMENTAS_DE_ARQUIVO = ('Write', 'Edit', 'MultiEdit', 'NotebookEdit')
# subcomandos humanos do desdobra, depois de "desdobra" e de opcoes globais quaisquer. Os mesmos de
# desdobra.humano.COMANDOS, com teste (aprovar e entregar: decisoes-v1.md, 138 e 142)
SUBCOMANDOS_HUMANOS = ('render', 'linkado confirmar', 'spec confirmar', 'briefing confirmar', 'aprovar', 'entregar',
                       'parametros-entrega')
_PRIMEIRAS = sorted({c.split()[0] for c in SUBCOMANDOS_HUMANOS})
SUBCOMANDO = re.compile(r'desdobra(?:\.exe|\.cli|\.__main__)?["\']?(?:\s+--?[\w-]+(?:[ =](?!%s)[^\s|;&]+)?)*'
                        r'\s+(%s)(?![\w./\\-])' % ('|'.join(r'%s\b' % c for c in _PRIMEIRAS),
                                                 '|'.join(r'\s+'.join(c.split()) for c in SUBCOMANDOS_HUMANOS)),
                        re.IGNORECASE)
# subcomando passado numa variavel (PowerShell $c, cmd %c%): o gancho nao sabe qual e, entao nega
SUBCOMANDO_EM_VARIAVEL = re.compile(r'desdobra(?:\.exe|\.cli|\.__main__)?(?:\s+--?[\w-]+(?:[ =][^\s|;&]+)?)*\s+[$%]',
                                    re.IGNORECASE)
# codigo do motor que grava o que so o DA grava, ou que mexe na conferencia. Da aprovacao e da entrega: os modulos
# desdobra.entrega.aprovacao e desdobra.entrega.validar, o registro, o selo e a gravacao deles e os handlers do aprovar
# e do entregar (o selo dos registros, registro_sha256 e relatorio_sha256, so pega mexida acidental: e um sha256 sem
# segredo e nao prova quem gravou)
CODIGO = re.compile(r'renderizar\s*\(|linkados\s*\.\s*(confirmar|sessao)|confirmar\s*\.\s*sessao|'
                    r'desdobra\s*\.\s*humano|from\s+desdobra\s+import\s+[^\n;]*\bhumano\b|\bhumano\s*\.\s*\w+\s*=|'
                    r'_SELOS|console_interativo|'
                    r'desdobra\s*\.\s*entrega\s*\.\s*(aprovacao|validar|parametros|_\w)|'
                    r'from\s+desdobra\s*\.\s*entrega\s+import\s+[^\n;]*\b(aprovacao|validar|parametros)\b|'
                    r'from\s+desdobra\s+import\s+[^\n;]*\bentrega\b|'
                    r'aprovacao\s*\.\s*(registro|gravar|selo|ARQUIVO)\b|validar\s*\.\s*(gravar|_trocar|selo|relatorio)\s*\(|'
                    r'\b_(aprovar|entregar|parametros_entrega)\s*\(', re.IGNORECASE)
# entrega/** (menos o codigo-fonte do pacote: desdobra/entrega/<modulo>.py e o __pycache__ dele), o manifesto e o
# relatorio da entrega e os parametros de entrega do job (sentido da rotacao, decisoes-v1.md, 139) tambem sao do DA ou
# do motor. A excecao do codigo-fonte vale so logo depois de desdobra/ e para um nome de modulo inteiro, que termina o
# caminho (nada de aprovados/x.py, {a.jpg,x.py}, a.jpg,x.py, kv.py.jpg nem x.md)
FONTE_DO_PACOTE = r'(?:__pycache__/)?\w+(?:\.[\w-]+)?\.pyc?(?![\w.\\/{},-])'
ARQUIVOS_DO_DA = re.compile(r'(^|[\\/])(briefing[\\/][\w.-]+\.json\b|derivacao[\\/][\w.-]+\.json\b|specs[\\/]confirmacoes\.json|render[\\/][^\\/]+[\\/]'
                            r'(master\.png|render\.json|contrato\.json)|linkados-confirmados\.json|'
                            r'(?<!desdobra[\\/])entrega[\\/]|entrega[\\/](?!%s)|manifesto-licenca\.json|relatorio-entrega\.json|'
                            r'parametros[\\/]entrega\.json)' % FONTE_DO_PACOTE, re.IGNORECASE)
ESCRITA = re.compile(r'(>|\btee\b|Set-Content|Out-File|Add-Content|\bcp\b|\bmv\b|copy|move|New-Item|\bsed\s+-i|'
                     r'write_text|write_bytes|open\s*\(|os\s*\.\s*(replace|rename|link|symlink)|shutil\s*\.|'
                     r'Rename-Item|\bren\b|\brename\b|Move-Item|Copy-Item|--saida)', re.IGNORECASE)


def _caminhos(texto):
    """Barras para /, sem /./, sem // e sem segmento/.. (o Windows resolve o .. pelo texto do caminho)."""
    s = texto.replace('\\', '/')
    while True:
        novo = re.sub(r'(?<=[^/:])/{2,}', '/', re.sub(r'/\.(?=/)', '', s))
        novo = re.sub(r'(^|/)(?!\.\.(?:/|$))[^/\s|;&<>,{}]+/\.\.(?:/|$)', r'\1', novo)
        if novo == s:
            return s
        s = novo


def normalizar(comando):
    """O comando como o shell o le, para o casamento: sem aspas, sem o escape do cmd (^) e do PowerShell (`), e com os
    caminhos normalizados (_caminhos)."""
    return _caminhos(re.sub('[\'"^`]', '', comando))


def decidir(evento):
    """'deny' ou None."""
    ferramenta = evento.get('tool_name') or ''
    entrada = evento.get('tool_input') or {}
    if ferramenta in FERRAMENTAS_DE_COMANDO:
        bruto = str(entrada.get('command') or '')
        for comando in (bruto, normalizar(bruto)):
            if SUBCOMANDO.search(comando) or SUBCOMANDO_EM_VARIAVEL.search(comando):
                return 'deny'
            if 'desdobra' in comando and CODIGO.search(comando):
                return 'deny'
            if ARQUIVOS_DO_DA.search(comando) and ESCRITA.search(comando):
                return 'deny'
        return None
    if ferramenta in FERRAMENTAS_DE_ARQUIVO:
        caminho = str(entrada.get('file_path') or entrada.get('notebook_path') or '')
        if ARQUIVOS_DO_DA.search(_caminhos(caminho)):
            return 'deny'
    return None


def main():
    try:
        evento = json.loads(sys.stdin.buffer.read().decode('utf-8') or '{}')
    except (ValueError, UnicodeDecodeError):
        return 0
    if decidir(evento) == 'deny':
        saida = json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                                   'permissionDecisionReason': MOTIVO}}, ensure_ascii=False)
        sys.stdout.buffer.write(saida.encode('utf-8') + bytes([10]))
        sys.stdout.buffer.flush()
    return 0


if __name__ == '__main__':
    sys.exit(main())
