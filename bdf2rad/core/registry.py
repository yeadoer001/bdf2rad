from __future__ import annotations
from dataclasses import dataclass
from .discovery import PluginSpec
@dataclass(slots=True)
class Registry:
    plugins:list[PluginSpec]
    by_card:dict[str,list[PluginSpec]]
def build_registry(specs):
    by={}
    for s in specs:
        for c in s.source_cards: by.setdefault(c,[]).append(s)
    return Registry(specs,by)
