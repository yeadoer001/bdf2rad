from dataclasses import dataclass, field
@dataclass
class SemanticEntity:
    source_id: int
    source_card: str
    provenance: object = None
    semantic: dict = field(default_factory=dict)
    target: dict = field(default_factory=dict)
    verification: str = 'NOT_VERIFIED'
NodeIR=ElementIR=MaterialIR=PropertyIR=MassIR=ConstraintIR=RigidRelationIR=RBE2IR=RBE3IR=SurfaceIR=ContactIR=GlueIR=InitialVelocityIR=GravityIR=SemanticEntity
