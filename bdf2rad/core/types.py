from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass(slots=True)
class RadBlock:
    keyword: str
    lines: list[str]
    order: int = 100
    plugin: str = ''
    source_cards: tuple[str, ...] = ()

@dataclass(slots=True)
class TranslationContext:
    model: Any
    blocks: list[RadBlock] = field(default_factory=list)
    audit: list[dict[str, Any]] = field(default_factory=list)
    ids: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
