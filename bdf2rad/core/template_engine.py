from __future__ import annotations
import json
from pathlib import Path

def load_template(block_dir: Path) -> dict:
    return json.loads((block_dir/'template.json').read_text(encoding='utf-8'))

def render(lines:list[str], mapping:dict[str,object]) -> list[str]:
    out=[]
    for line in lines:
        for k,v in mapping.items():
            line=line.replace('{{'+k+'}}',str(v))
        out.append(line)
    unresolved=[x for x in out if '{{' in x or '}}' in x]
    if unresolved:
        raise RuntimeError('Unresolved template placeholders: '+repr(unresolved[:3]))
    return out
