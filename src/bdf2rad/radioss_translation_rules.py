"""
Rule-driven BDF -> OpenRadioss translation primitives.

This module deliberately does NOT parse BDF files or own project-specific IR classes.
It provides deterministic serializers and small field-mapping helpers for the
cards that occur in the supplied Solution 3-1.bdf.

Integrate these functions from:
    D:\\BDF2RAD-X\\src\\bdf2rad\\radioss_writer.py

All IDs, node lists, element connectivities and numeric values must come from
the existing parser/IR in the repository.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


def _fmt(value) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.12g}"
    return str(value)


def _line(fields: Sequence[object]) -> str:
    return " ".join(_fmt(x) for x in fields if x is not None) + "\n"


def _chunks(values: Sequence[int], n: int) -> Iterable[Sequence[int]]:
    for i in range(0, len(values), n):
        yield values[i:i+n]


def dof_to_trarot(dof: str | int) -> str:
    """
    Nastran constrained DOF digits -> Radioss Trarot 6-bit string.

    Example:
        123456 -> 111111
        123    -> 111000
    """
    s = str(dof).strip()
    if not s:
        raise ValueError("empty DOF")
    if not s.isdigit() or any(ch not in "123456" for ch in s):
        raise ValueError(f"invalid Nastran DOF: {dof!r}")
    active = set(s)
    return "".join("1" if str(i) in active else "0" for i in range(1, 7))


def write_grnod_node(
    group_id: int,
    node_ids: Sequence[int],
    title: str = "NODE_GROUP",
    unit_id: int = 1,
) -> str:
    if not node_ids:
        raise ValueError("GRNOD group cannot be empty")
    if len(set(node_ids)) != len(node_ids):
        raise ValueError("GRNOD group contains duplicate node IDs")
    out = [f"/GRNOD/NODE/{group_id}/{unit_id}\n", f"{title[:100]}\n"]
    for chunk in _chunks(list(node_ids), 10):
        out.append(_line(chunk))
    return "".join(out)


def write_inivel_tra(
    inivel_id: int,
    vx: float,
    vy: float,
    vz: float,
    group_id: int,
    title: str = "Initial_velocity",
    unit_id: int = 1,
    skew_id: int = 0,
) -> str:
    if group_id <= 0:
        raise ValueError("INIVEL/TRA requires a valid node-group ID")
    return (
        f"/INIVEL/TRA/{inivel_id}/{unit_id}\n"
        f"{title[:100]}\n"
        f"{_line([vx, vy, vz, group_id, skew_id])}"
    )


def write_grav(
    grav_id: int,
    acceleration_z: float,
    title: str = "Gravity",
    unit_id: int = 1,
    function_id: int = 0,
    direction: str = "Z",
    skew_id: int = 0,
    sensor_id: int = 0,
    group_id: int = 0,
    ascale: float = 1.0,
) -> str:
    """
    Writes the scalar gravity representation:
        /GRAV/id/unit
        title
        fct_IDT DIR skew sensor group Ascale Fscale

    For the supplied model, a constant global Z acceleration can use
    direction='Z', function_id=0, group_id=0 and Fscale=acceleration_z.
    """
    direction = direction.upper()
    if direction not in {"X", "Y", "Z"}:
        raise ValueError("direction must be X, Y or Z")
    return (
        f"/GRAV/{grav_id}/{unit_id}\n"
        f"{title[:100]}\n"
        f"{_line([function_id, direction, skew_id, sensor_id, group_id, ascale, acceleration_z])}"
    )


def write_bcs(
    bcs_id: int,
    dof: str | int,
    group_id: int,
    title: str = "Boundary_conditions",
    unit_id: int | None = None,
    skew_id: int = 0,
    law: str = "/BCS",
) -> str:
    trarot = dof_to_trarot(dof)
    if group_id <= 0:
        raise ValueError("BCS requires a valid node-group ID")
    return (
        f"{law}/{bcs_id}\n"
        f"{title[:100]}\n"
        f"{_line([trarot, skew_id, group_id])}"
    )


def write_admas_single_node(
    admas_id: int,
    node_id: int,
    mass: float,
    title: str = "CONM2",
    unit_id: int = 1,
) -> str:
    if mass < 0:
        raise ValueError("negative mass is not allowed")
    return (
        f"/ADMAS/5/{admas_id}/{unit_id}\n"
        f"{title[:100]}\n"
        f"{_line([mass, node_id])}"
    )


def write_rbe2(
    rbe2_id: int,
    independent_node: int,
    dof: str | int,
    dependent_group_id: int,
    title: str = "RBE2",
    skew_id: int = 0,
    iflag: int = 0,
) -> str:
    trarot = dof_to_trarot(dof)
    if dependent_group_id <= 0:
        raise ValueError("RBE2 requires a dependent-node group")
    return (
        f"/RBE2/{rbe2_id}\n"
        f"{title[:100]}\n"
        f"{_line([independent_node, trarot, skew_id, dependent_group_id, iflag])}"
    )


def write_rbe3(
    rbe3_id: int,
    reference_node: int,
    reference_dof: str | int,
    weighting_sets: Sequence[tuple[float, str | int, int, int]],
    title: str = "RBE3",
    imodif: int = 1,
    iform: int = 1,
) -> str:
    if not weighting_sets:
        raise ValueError("RBE3 requires at least one weighting set")
    out = [
        f"/RBE3/{rbe3_id}\n",
        f"{title[:100]}\n",
        _line([reference_node, dof_to_trarot(reference_dof), len(weighting_sets), imodif, iform]),
    ]
    for weight, indep_dof, skew_id, group_id in weighting_sets:
        if group_id <= 0:
            raise ValueError("RBE3 weighting set requires a valid node-group ID")
        out.append(_line([weight, dof_to_trarot(indep_dof), skew_id, group_id]))
    return "".join(out)


def write_surf_seg(
    surface_id: int,
    segments: Sequence[Sequence[int]],
    title: str = "BDF_SURFACE",
    unit_id: int = 1,
) -> str:
    """
    segments must contain 3 or 4 node IDs per segment.

    For the supplied BSURFS solid-face data, convert each source face
    (element_id, g1, g2, g3) to a target segment using the three source corner
    nodes. If a fourth corner can be reconstructed unambiguously from the
    source element topology, it may be supplied as a 4-node segment.
    """
    if not segments:
        raise ValueError("SURF/SEG requires at least one segment")
    out = [f"/SURF/SEG/{surface_id}/{unit_id}\n", f"{title[:100]}\n"]
    seg_id = 1
    for seg in segments:
        if len(seg) not in (3, 4):
            raise ValueError(f"segment {seg_id} must have 3 or 4 nodes")
        if len(set(seg)) != len(seg):
            raise ValueError(f"segment {seg_id} contains duplicate nodes")
        out.append(_line([seg_id, *seg]))
        seg_id += 1
    return "".join(out)


def write_type7(
    interface_id: int,
    secondary_group_id: int,
    main_surface_id: int,
    title: str = "BCTSET",
    unit_id: int = 1,
    istf: int = 1,
    stfac: float | None = None,
    friction: float | None = None,
    gap: float | None = None,
) -> str:
    if secondary_group_id <= 0:
        raise ValueError("TYPE7 requires a non-zero secondary group ID")
    if main_surface_id <= 0:
        raise ValueError("TYPE7 requires a non-zero main surface ID")
    out = [
        f"/INTER/TYPE7/{interface_id}/{unit_id}\n",
        f"{title[:100]}\n",
        _line([secondary_group_id, main_surface_id, istf]),
    ]
    if stfac is not None or friction is not None or gap is not None:
        # Do not invent source contact parameters. Caller must pass values
        # only when they have been mapped from BCTSET/BCRPARA.
        out.append(_line([
            stfac if stfac is not None else 0,
            friction if friction is not None else 0,
            gap if gap is not None else 0,
        ]))
    return "".join(out)


def write_type2(
    interface_id: int,
    secondary_group_id: int,
    main_surface_id: int,
    title: str = "BGSET",
    unit_id: int = 1,
    ignore: int = 0,
    spot_flag: int = 0,
    level: int = 0,
    isearch: int = 0,
    idel2: int = 0,
    search_distance: float = 0.0,
) -> str:
    if secondary_group_id <= 0:
        raise ValueError("TYPE2 requires a non-zero secondary group ID")
    if main_surface_id <= 0:
        raise ValueError("TYPE2 requires a non-zero main surface ID")
    return (
        f"/INTER/TYPE2/{interface_id}/{unit_id}\n"
        f"{title[:100]}\n"
        f"{_line([secondary_group_id, main_surface_id, ignore, spot_flag, level, isearch, idel2, 0, search_distance])}"
    )


@dataclass(frozen=True)
class MappingRule:
    source: str
    target: str
    exact: bool
    notes: str


RULES = {
    "GRID": MappingRule("GRID", "/NODE", True, "Direct coordinate/ID transfer."),
    "MAT1": MappingRule("MAT1", "/MAT/ELAST", True, "Elastic MAT1 subset."),
    "PSOLID": MappingRule("PSOLID", "/PROP/SOLID", True, "Direct property-family mapping; fields require mapping."),
    "CONM2": MappingRule("CONM2", "/ADMAS/5", True, "Single-node mass when offset/inertia are zero."),
    "RBE2": MappingRule("RBE2", "/RBE2", True, "Independent node + dependent node group."),
    "RBE3": MappingRule("RBE3", "/RBE3", True, "Weighted independent node groups."),
    "SPC": MappingRule("SPC", "/BCS", True, "Group nodes by identical DOF pattern."),
    "TIC": MappingRule("TIC", "/INIVEL/TRA", True, "Group nodes sharing the same initial velocity."),
    "GRAV": MappingRule("GRAV", "/GRAV", True, "Constant gravity vector can be represented directly."),
    "BSURFS": MappingRule("BSURFS", "/SURF/SEG", True, "Explicit element-face segments."),
    "BCTSET": MappingRule("BCTSET", "/INTER/TYPE7", True, "Map source region pair to secondary group + main surface."),
    "BGSET": MappingRule("BGSET", "/INTER/TYPE2", True, "Map glue region pair to secondary group + main surface."),
    "CHEXA8": MappingRule("CHEXA8", "/BRICK", True, "Direct first-order solid mapping."),
    "CHEXA20": MappingRule("CHEXA20", "/BRIC20", True, "Current preserve-order path."),
    "CTETRA10": MappingRule("CTETRA10", "/TETRA10", True, "Current preserve-order path."),
    "CPENTA15": MappingRule("CPENTA15", "/BRICK", False, "Needs explicit reduction/topology strategy; never silent."),
}
