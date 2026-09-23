"""Solver-independent IR and deterministic namespace management."""
from dataclasses import dataclass, field
from enum import Enum

from .parser import Card


class Confidence(str, Enum):
    EXACT = "EXACT"
    VERIFIED = "VERIFIED"
    APPROXIMATE = "APPROXIMATE"
    REQUIRES_VALIDATION = "REQUIRES_VALIDATION"
    UNSUPPORTED = "UNSUPPORTED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class MappingResult:
    source: str
    target: str | None
    confidence: Confidence
    warnings: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()


@dataclass(slots=True)
class Model:
    nodes: dict = field(default_factory=dict)
    elements: dict = field(default_factory=dict)
    node_sets: dict = field(default_factory=dict)
    element_sets: dict = field(default_factory=dict)
    materials: dict = field(default_factory=dict)
    properties: dict = field(default_factory=dict)
    coordinate_systems: dict = field(default_factory=dict)
    rigid_bodies: dict = field(default_factory=dict)
    constraints: dict = field(default_factory=dict)
    contacts: dict = field(default_factory=dict)
    loads: dict = field(default_factory=dict)
    load_curves: dict = field(default_factory=dict)
    initial_conditions: dict = field(default_factory=dict)
    control_parameters: dict = field(default_factory=dict)
    output_requests: dict = field(default_factory=dict)
    connections: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


class IdManager:
    def __init__(self, maximum=999999999):
        if maximum < 1:
            raise ValueError("ID maximum must be positive")
        self.maximum = maximum
        self.mapping = {}

    def allocate(self, namespace, source_ids):
        """Reserve valid source IDs first, then remap out-of-range IDs in sorted order.

        Allocate a complete namespace once; order and Python hash seed cannot affect it.
        Duplicate input IDs are errors, never an excuse to overwrite an entity.
        """
        if namespace in self.mapping:
            raise ValueError(f"Namespace already allocated: {namespace}")
        ids = list(source_ids)
        if any(type(i) is not int or i < 1 for i in ids):
            raise ValueError("Source IDs must be positive integers")
        if len(set(ids)) != len(ids):
            raise ValueError(f"Duplicate ID in {namespace}")
        if len(ids) > self.maximum:
            raise ValueError("Target ID namespace exhausted")
        result = {i: i for i in sorted(ids) if i <= self.maximum}
        used = set(result.values())
        next_id = 1
        for i in sorted(ids):
            if i in result:
                continue
            while next_id in used:
                next_id += 1
            result[i] = next_id
            used.add(next_id)
        self.mapping[namespace] = result
        return dict(result)

    def reference(self, namespace, source_id):
        try:
            return self.mapping[namespace][source_id]
        except KeyError as exc:
            raise ValueError(f"Dangling reference {namespace}:{source_id}") from exc


class MappingRegistry:
    def __init__(self):
        self._mappers = {}

    def register(self, card_name, mapper):
        name = card_name.upper()
        if name in self._mappers:
            raise ValueError(f"Mapper already registered: {name}")
        self._mappers[name] = mapper

    def map(self, card: Card, model: Model):
        mapper = self._mappers.get(card.name)
        if mapper is None:
            return MappingResult(card.name, None, Confidence.UNSUPPORTED,
                                 ("UNKNOWN_CARD or semantic mapper not implemented; original AST retained",))
        result = mapper(card, model)
        if not isinstance(result, MappingResult):
            raise TypeError("Mappers must return auditable MappingResult metadata")
        return result
