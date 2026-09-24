from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Node:
    nid: int
    xyz: tuple[float, float, float]
    cp: int = 0
    cd: int = 0


@dataclass(slots=True)
class Element:
    eid: int
    typ: str
    pid: int
    nodes: list[int]
    order: int = 0

    def __post_init__(self):
        """
        Determine the source element order from connectivity
        when it was not explicitly supplied.

        Nastran solid topologies:
            CTETRA: 4 or 10 nodes
            CPENTA: 6 or 15 nodes
            CHEXA:  8 or 20 nodes
        """
        if self.order:
            return

        count = len(self.nodes)

        if self.typ == "CTETRA":
            if count in (4, 10):
                self.order = count

        elif self.typ == "CPENTA":
            if count in (6, 15):
                self.order = count

        elif self.typ == "CHEXA":
            if count in (8, 20):
                self.order = count


@dataclass(slots=True)
class Property:
    pid: int
    mid: int
    raw: list[str]


@dataclass(slots=True)
class Material:
    mid: int
    E: float
    nu: float
    rho: float
    G: float = 0.0
    alpha: float = 0.0


@dataclass(slots=True)
class Plastic:
    mid: int
    table_id: int = 0
    form: str = "PLASTIC"
    H: float = 0.0
    YF: int = 1
    HR: int = 1
    limit1: float = 0.0


@dataclass(slots=True)
class Mass:
    eid: int
    nid: int
    mass: float
    xyz: tuple[float, float, float]
    cid: int = 0


@dataclass(slots=True)
class RBE2:
    rid: int
    independent: int
    cm: str
    dependent: list[int]


@dataclass(slots=True)
class RBE3:
    rid: int
    ref: int
    ref_comp: str
    weight: float
    ind_comp: str
    independent: list[int]


@dataclass(slots=True)
class SPC:
    sid: int
    nid: int
    comp: str
    value: float


@dataclass(slots=True)
class TIC:
    sid: int
    nid: int
    dof: int
    displacement: float | None
    velocity: float | None


@dataclass(slots=True)
class Gravity:
    sid: int
    cid: int
    scale: float
    vector: tuple[float, float, float]


@dataclass(slots=True)
class BsurfS:
    sid: int
    faces: list[tuple[int, int, int, int]]


@dataclass(slots=True)
class BCTSet:
    sid: int
    source: int
    target: int
    friction: float = 0.0
    mind: int = 0
    maxd: float = 0.0
    form: int = 1


@dataclass(slots=True)
class BCRPara:
    sid: int
    offset: float = 0.0
    surf: str = "FLEX"


@dataclass(slots=True)
class BGSet:
    sid: int
    source: int
    target: int
    scale: float = 1.0
    clearance: float = 0.0


@dataclass(slots=True)
class TStep:
    sid: int
    dt: float
    n: int
    method: str = ""


@dataclass(slots=True)
class Model:
    nodes: dict[int, Node] = field(
        default_factory=dict
    )

    elements: dict[int, Element] = field(
        default_factory=dict
    )

    props: dict[int, Property] = field(
        default_factory=dict
    )

    mats: dict[int, Material] = field(
        default_factory=dict
    )

    plastics: dict[int, Plastic] = field(
        default_factory=dict
    )

    masses: dict[int, Mass] = field(
        default_factory=dict
    )

    rbe2: dict[int, RBE2] = field(
        default_factory=dict
    )

    rbe3: dict[int, RBE3] = field(
        default_factory=dict
    )

    spcs: list[SPC] = field(
        default_factory=list
    )

    tics: list[TIC] = field(
        default_factory=list
    )

    gravs: dict[int, Gravity] = field(
        default_factory=dict
    )

    bsurfs: dict[int, BsurfS] = field(
        default_factory=dict
    )

    bctsets: dict[int, BCTSet] = field(
        default_factory=dict
    )

    bcrpara: dict[int, BCRPara] = field(
        default_factory=dict
    )

    bgsets: dict[int, BGSet] = field(
        default_factory=dict
    )

    bctadds: dict[int, list[int]] = field(
        default_factory=dict
    )

    bgadds: dict[int, list[int]] = field(
        default_factory=dict
    )

    tsteps: dict[int, TStep] = field(
        default_factory=dict
    )

    card_counts: dict[str, int] = field(
        default_factory=dict
    )

    case: dict[str, str] = field(
        default_factory=dict
    )

    control_lines: list[str] = field(
        default_factory=list
    )

    executive: list[str] = field(
        default_factory=list
    )

    diagnostics: list[dict] = field(
        default_factory=list
    )