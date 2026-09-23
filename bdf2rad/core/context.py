from __future__ import annotations
from .types import TranslationContext

def next_id(ctx: TranslationContext, namespace: str, start: int=1) -> int:
    key=f'next:{namespace}'
    value=ctx.ids.get(key,start)
    ctx.ids[key]=value+1
    return value
