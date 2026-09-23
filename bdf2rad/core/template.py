from __future__ import annotations
import json
from pathlib import Path
import re
from typing import Any

class TemplateError(RuntimeError):
    pass

def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))

def load_template(block_dir: Path) -> list[str]:
    p = block_dir / 'template.json'
    if not p.exists():
        raise TemplateError(f'missing template.json: {block_dir}')
    data = load_json(p)
    lines = data.get('lines')
    if not isinstance(lines, list) or not all(isinstance(x, str) for x in lines):
        raise TemplateError(f'invalid template lines: {p}')
    return list(lines)

def render(lines: list[str], values: dict[str, Any]) -> list[str]:
    out = []
    for line in lines:
        s = line
        for k, v in values.items():
            s = s.replace('{{' + k + '}}', str(v))
        if '{{' in s or '}}' in s:
            # A template may intentionally expose a row token that is expanded before this layer.
            raise TemplateError(f'unresolved template token: {s}')
        out.append(s)
    return out

def normalize_lines(lines: list[str]) -> list[str]:
    return [x.rstrip('\r\n') for x in lines]

# Safe replacement utility: only replace explicit placeholders, never alter whitespace around other text.
def replace_exact(lines: list[str], token: str, replacement: str) -> list[str]:
    return [x.replace(token, replacement) for x in lines]
