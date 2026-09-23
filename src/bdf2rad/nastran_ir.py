"""Auditable Nastran intermediate representation."""
from dataclasses import dataclass, field, asdict

@dataclass(slots=True)
class Provenance:
    source_card: str
    source_file: str
    source_line: int
    source_id: int | None = None
    mapping_confidence: str = "REQUIRES_VALIDATION"
    warnings: list[str] = field(default_factory=list)

@dataclass(slots=True)
class Entity:
    data: dict
    provenance: Provenance

@dataclass(slots=True)
class NastranIR:
    nodes: dict[int, Entity] = field(default_factory=dict)
    solid_elements: dict[int, Entity] = field(default_factory=dict)
    properties: dict[int, Entity] = field(default_factory=dict)
    materials: dict[int, Entity] = field(default_factory=dict)
    plasticity: dict[int, Entity] = field(default_factory=dict)
    masses: dict[int, Entity] = field(default_factory=dict)
    rbe2: dict[int, Entity] = field(default_factory=dict)
    rbe3: dict[int, Entity] = field(default_factory=dict)
    boundary_conditions: dict[int, Entity] = field(default_factory=dict)
    initial_conditions: dict[int, Entity] = field(default_factory=dict)
    gravity: dict[int, Entity] = field(default_factory=dict)
    contact_surfaces: dict[int, Entity] = field(default_factory=dict)
    contacts: dict[int, Entity] = field(default_factory=dict)
    glue_interfaces: dict[int, Entity] = field(default_factory=dict)
    analysis_controls: dict[str, list[Entity]] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    card_counts: dict[str, int] = field(default_factory=dict)
    unsupported: list[dict] = field(default_factory=list)

    def entity_dict(self):
        def conv(x): return {'data': x.data, 'provenance': asdict(x.provenance)}
        return {k: {str(i): conv(v) for i,v in getattr(self,k).items()} for k in
                ('nodes','solid_elements','properties','materials','plasticity','masses','rbe2','rbe3',
                 'boundary_conditions','initial_conditions','gravity','contact_surfaces','contacts','glue_interfaces')}
