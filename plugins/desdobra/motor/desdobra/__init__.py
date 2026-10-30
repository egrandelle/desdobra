# -*- coding: utf-8 -*-
"""Motor do desdobra. A versao vem so de plugins/desdobra/.claude-plugin/plugin.json."""
import json
from pathlib import Path

PASTA_MOTOR = Path(__file__).resolve().parent.parent
PASTA_PLUGIN = PASTA_MOTOR.parent


def _versao():
    try:
        with open(PASTA_PLUGIN / '.claude-plugin' / 'plugin.json', encoding='utf-8') as f:
            return json.load(f)['version']
    except (OSError, ValueError, KeyError):
        return 'desconhecida'


__version__ = _versao()
