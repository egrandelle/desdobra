# -*- coding: utf-8 -*-
"""Gancho PreToolUse do plugin: o Claude nunca dispara o que so o DA dispara.

Roda com o Python do PATH, so com a biblioteca padrao, na forma exec (hooks/hooks.json):

    python -I -B ${CLAUDE_PLUGIN_ROOT}/scripts/gancho_confirmacoes.py

Le da entrada padrao o JSON do evento (tool_name e tool_input) e nega (permissionDecision "deny"):
  - nas ferramentas Bash e PowerShell, comando que chama o render, a confirmacao de linkado, a confirmacao de spec
    ou a do briefing do desdobra (pela linha de comando ou pelo codigo Python do motor), que mexe na conferencia do
    disparo humano, ou que escreve num arquivo que so o DA grava;
  - nas ferramentas que gravam arquivo (Write, Edit, MultiEdit, NotebookEdit), arquivo que so o DA grava ou que so o
    render grava: os .json de briefing/, specs/confirmacoes.json e master, render.json e contrato de render/.
Com a negacao, o Claude recebe o motivo: quem roda isso e o DA, num terminal proprio, fora do Claude. Sem negacao, o
gancho nao imprime nada e o Claude Code segue o fluxo normal de permissao. O codigo de saida e sempre 0.

Este gancho cobre o caminho do Claude. O motor confere o console de novo (desdobra.humano), e o risco residual (um
processo do mesmo usuario, fora do Claude, que escreve teclas num console) fica declarado no relatorio do M4.
"""
import json
import re
import sys

MOTIVO = ('O desdobra recusa este comando pelo Claude: render, confirmação de linkado, confirmação de spec e '
          'confirmação de briefing só partem do DA. Peça ao DA para abrir um terminal próprio, fora do Claude, e rodar '
          'o comando lá; o desdobra pergunta e grava. Não tente outro caminho para o mesmo efeito.')
FERRAMENTAS_DE_COMANDO = ('Bash', 'PowerShell')
FERRAMENTAS_DE_ARQUIVO = ('Write', 'Edit', 'MultiEdit', 'NotebookEdit')
# subcomandos humanos do desdobra, depois de "desdobra" e de opcoes globais quaisquer
SUBCOMANDO = re.compile(r'desdobra(?:\.exe)?["\']?(?:\s+--?[\w-]+(?:[ =](?!render\b|linkado\b|spec\b|briefing\b)[^\s|;&]+)?)*'
                        r'\s+(render|linkado\s+confirmar|spec\s+confirmar|briefing\s+confirmar)(?![\w./\\-])',
                        re.IGNORECASE)
# codigo do motor que grava o que so o DA grava, ou que mexe na conferencia
CODIGO = re.compile(r'renderizar\s*\(|linkados\s*\.\s*(confirmar|sessao)|confirmar\s*\.\s*sessao|'
                    r'desdobra\s*\.\s*humano|from\s+desdobra\s+import\s+[^\n;]*\bhumano\b|\bhumano\s*\.\s*\w+\s*=|'
                    r'_SELOS|console_interativo', re.IGNORECASE)
ARQUIVOS_DO_DA = re.compile(r'(^|[\\/])(briefing[\\/][\w.-]+\.json\b|specs[\\/]confirmacoes\.json|render[\\/][^\\/]+[\\/]'
                            r'(master\.png|render\.json|contrato\.json)|linkados-confirmados\.json)', re.IGNORECASE)
ESCRITA = re.compile(r'(>|\btee\b|Set-Content|Out-File|Add-Content|\bcp\b|\bmv\b|copy|move|New-Item|\bsed\s+-i|'
                     r'write_text|write_bytes|open\s*\()', re.IGNORECASE)


def decidir(evento):
    """'deny' ou None."""
    ferramenta = evento.get('tool_name') or ''
    entrada = evento.get('tool_input') or {}
    if ferramenta in FERRAMENTAS_DE_COMANDO:
        comando = str(entrada.get('command') or '')
        if SUBCOMANDO.search(comando):
            return 'deny'
        if 'desdobra' in comando and CODIGO.search(comando):
            return 'deny'
        if ARQUIVOS_DO_DA.search(comando) and ESCRITA.search(comando):
            return 'deny'
        return None
    if ferramenta in FERRAMENTAS_DE_ARQUIVO:
        caminho = str(entrada.get('file_path') or entrada.get('notebook_path') or '')
        if ARQUIVOS_DO_DA.search(caminho.replace('\\', '/')):
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
