"""Concrete BDF -> OpenRadioss translators for Solution 3-1.

Put this file at:
    D:\\BDF2RAD-X\\src\\bdf2rad\\remaining_bdf_to_rad_translators.py

The module is intentionally adapter-light: it consumes the existing NastranIR
objects from bdf-rad (Entity.data dictionaries) and returns text blocks plus
mapping metadata. It does not own BDF parsing or the master writer.

Supported concrete source subset (verified from Solution 3-1(4).bdf):
- MAT1 -> /MAT/LAW1
- MATS1 (TYPE=PLASTIC, YF=1, HR=1, TID blank, constant H) -> /MAT/LAW2
- PSOLID -> /PROP/SOLID
- CONM2 with zero offset/inertia -> /ADMAS/5
- SPC -> /GRNOD/NODE + /BCS
- TIC -> /GRNOD/NODE + /INIVEL/TRA
- GRAV -> /GRAV
- RBE2 -> /GRNOD/NODE + /RBE2
- RBE3 with one weighting set -> /GRNOD/NODE + /RBE3
- BSURFS -> /SURF/SEG
- BCTSET/BCTADD -> /INTER/TYPE7
- BGSET/BGADD -> /INTER/TYPE2

This is a model-specific translator, not a claim of general Nastran coverage.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import isfinite
from typing import Any, Iterable, Mapping, Sequence


def _data(entity: Any) -> Any:
    return getattr(entity, "data", entity)


def _get(entity: Any, key: str, default: Any = None) -> Any:
    d = _data(entity)
    if isinstance(d, Mapping):
        return d.get(key, default)
    return getattr(d, key, default)


def _raw(entity: Any) -> list[str]:
    raw = _get(entity, "raw", [])
    return list(raw or [])


def _float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"non-finite value: {value!r}")
    return value


def _fmt(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError(f"non-finite value: {value!r}")
        return f"{value:.12g}"
    return str(value)


def _line(*values: Any) -> str:
    return " ".join(_fmt(v) for v in values) + "\n"


def _chunks(values: Sequence[int], n: int = 10) -> Iterable[Sequence[int]]:
    for i in range(0, len(values), n):
        yield values[i:i + n]


def dof_to_trarot(dof: str | int) -> str:
    """Nastran DOF digits -> Radioss six Boolean Trarot field."""
    s = str(dof).strip()
    if not s or any(c not in "123456" for c in s):
        raise ValueError(f"unsupported Nastran DOF: {dof!r}")
    active = set(s)
    return "".join("1" if str(i) in active else "0" for i in range(1, 7))


@dataclass(frozen=True)
class NodeGroup:
    group_id: int
    title: str
    node_ids: tuple[int, ...]
    unit_id: int = 1

    def render(self) -> str:
        if self.group_id <= 0:
            raise ValueError("group_id must be > 0")
        ids = tuple(dict.fromkeys(int(x) for x in self.node_ids))
        if not ids:
            raise ValueError(f"empty node group {self.group_id}")
        return (
            f"/GRNOD/NODE/{self.group_id}/{self.unit_id}\n"
            f"{self.title[:100]}\n"
            + "".join(_line(*chunk) for chunk in _chunks(ids))
        )


# ---------------------------------------------------------------------------
# Direct target blocks
# ---------------------------------------------------------------------------


def render_mat1_law1(mid: int, rho: float, E: float, nu: float, title: str | None = None) -> str:
    return (
        f"/MAT/LAW1/{mid}/1\n"
        f"{title or f'MAT1_{mid}'}\n"
        f"{_line(rho)}"
        f"{_line(E, nu)}"
    )


def render_mats1_law2(
    mid: int,
    rho: float,
    E: float,
    nu: float,
    yield_stress: float,
    hardening_modulus: float,
    title: str | None = None,
) -> str:
    """Map the actual deck's simple MATS1 subset to LAW2.

    Source subset:
      TYPE=PLASTIC, YF=1 (von Mises), HR=1 (isotropic hardening),
      TID blank, H constant, LIMIT1 = initial yield stress.

    The Johnson-Cook expression becomes sigma_y = A + B*eps_p when
    n=1, C=0 and thermal/rate effects are disabled.
    This is an exact constitutive representation of the *linear-hardening
    subset*, not a statement that arbitrary MATS1 cards map to LAW2.
    """
    if yield_stress <= 0.0:
        raise ValueError(f"MATS1 {mid}: LIMIT1 must be > 0")
    if hardening_modulus < 0.0:
        raise ValueError(f"MATS1 {mid}: H must be >= 0")

    # /MAT/LAW2 classic input, Iflag=0:
    # rho
    # E nu Iflag VP Pmin
    # A B n eps_p_max sigma_max0
    # C eps_dot0 ICC Fsmooth Fcut Chard
    # m Tmelt rhoCp Tr Tmax
    return (
        f"/MAT/LAW2/{mid}/1\n"
        f"{title or f'MATS1_{mid}'}\n"
        f"{_line(rho)}"
        f"{_line(E, nu, 0, 0, -1.0e30)}"
        f"{_line(yield_stress, hardening_modulus, 1.0, 1.0e30, 1.0e30)}"
        f"{_line(0.0, 1.0, 0, 0.0, 1.0e30, 0.0)}"
        f"{_line(0.0, 1.0e30, 0.0, 0.0, 1.0e30)}"
    )


def render_psolid(
    pid: int,
    material_id: int,
    *,
    element_types: set[str],
    material_is_plastic: bool,
    title: str | None = None,
) -> str:
    """Render a non-placeholder /PROP/SOLID block.

    Selection is deliberately deterministic:
    - quadratic brick usage => Isolid=16
    - otherwise brick usage => Isolid=24
    - tetra-only properties still receive a legal solid property with
      TETRA10/TETRA4 selectors.

    If one source PID mixes linear and quadratic brick formulations, the
    caller should split the property before calling this function; a single
    /PROP/SOLID formulation cannot safely encode two incompatible brick
    interpolation orders.
    """
    has_quad_brick = "CHEXA20" in element_types
    has_linear_brick = bool(element_types & {"CHEXA8", "CPENTA15"})
    if has_quad_brick and has_linear_brick:
        raise ValueError(
            f"PSOLID {pid}: same property is used by both quadratic and linear brick elements; split property or choose a deliberate approximation"
        )

    isolid = 16 if has_quad_brick else 24
    ismstr = 2                 # full geometric nonlinearity; compatible with general explicit use
    # I_cpre=2 is only valid for I_solid=14/17/18/24.
    # For quadratic 20-node solids (I_solid=16), keep the default formulation.
    icpre = 2 if material_is_plastic and isolid in (14, 17, 18, 24) else (3 if not material_is_plastic else 0)
    itetra10 = 2 if "CTETRA10" in element_types else 1000
    inpts = 222 if isolid == 16 else 0
    itetra4 = 1000
    iframe = -1
    dn = 0.0

    return (
        f"/PROP/SOLID/{pid}/1\n"
        f"{title or f'PSOLID_{pid}'}\n"
        f"{_line(isolid, ismstr, 0, icpre, itetra10, inpts, itetra4, iframe, dn)}"
        f"{_line(1.10, 0.05, 0.10 if isolid in (1, 2) else 0.0, 0.0, 0.0)}"
        f"{_line(0.0)}"
    )


def render_admas5(admas_id: int, node_id: int, mass: float, title: str | None = None) -> str:
    if mass < 0.0:
        raise ValueError(f"negative mass for CONM2 {admas_id}")
    return (
        f"/ADMAS/5/{admas_id}/1\n"
        f"{title or f'CONM2_{admas_id}'}\n"
        f"{_line(mass, node_id)}"
    )


def render_bcs(bcs_id: int, group_id: int, dof: str | int, title: str) -> str:
    return (
        f"/BCS/{bcs_id}\n"
        f"{title[:100]}\n"
        f"{_line(dof_to_trarot(dof), 0, group_id)}"
    )


def render_inivel(group_id: int, velocity: Sequence[float], title: str = "Initial_velocity") -> str:
    if len(velocity) != 3:
        raise ValueError("velocity must contain 3 components")
    return (
        "/INIVEL/TRA/1/1\n"
        f"{title[:100]}\n"
        f"{_line(float(velocity[0]), float(velocity[1]), float(velocity[2]), group_id, 0)}"
    )


def render_grav(grav_id: int, vector: Sequence[float], title: str = "Gravity") -> str:
    if len(vector) != 3:
        raise ValueError("gravity vector must contain 3 components")
    gx, gy, gz = (float(v) for v in vector)
    if abs(gx) > 1e-12 or abs(gy) > 1e-12:
        raise ValueError("current translator only supports a pure Z gravity vector")
    return (
        f"/GRAV/{grav_id}/1\n"
        f"{title[:100]}\n"
        f"{_line(0, 'Z', 0, 0, 0, 1.0, gz)}"
    )


def render_rbe2(rbe2_id: int, independent: int, dof: str | int, dependent_group: int, title: str) -> str:
    return (
        f"/RBE2/{rbe2_id}\n"
        f"{title[:100]}\n"
        f"{_line(independent, dof_to_trarot(dof), 0, dependent_group, 0)}"
    )


def render_rbe3(
    rbe3_id: int,
    reference_node: int,
    reference_dof: str | int,
    weight: float,
    independent_dof: str | int,
    independent_group: int,
    title: str,
) -> str:
    return (
        f"/RBE3/{rbe3_id}\n"
        f"{title[:100]}\n"
        f"{_line(reference_node, dof_to_trarot(reference_dof), 1, 1, 1)}"
        f"{_line(weight, dof_to_trarot(independent_dof), 0, independent_group)}"
    )


def render_surf_seg(surface_id: int, segments: Sequence[Sequence[int]], title: str) -> str:
    if surface_id <= 0:
        raise ValueError("surface_id must be > 0")
    if not segments:
        raise ValueError(f"surface {surface_id} has no segments")
    out = [f"/SURF/SEG/{surface_id}/1\n", f"{title[:100]}\n"]
    for seg_id, nodes in enumerate(segments, 1):
        if len(nodes) not in (3, 4):
            raise ValueError(f"surface {surface_id}: segment {seg_id} has {len(nodes)} nodes")
        if len(set(nodes)) != len(nodes):
            raise ValueError(f"surface {surface_id}: segment {seg_id} has duplicate nodes")
        out.append(_line(seg_id, *nodes))
    return "".join(out)


def render_type7(
    interface_id: int,
    secondary_group: int,
    main_surface: int,
    *,
    friction: float,
    gap_min: float = 0.0,
    title: str = "BCTSET",
) -> str:
    if secondary_group <= 0 or main_surface <= 0:
        raise ValueError("TYPE7 requires non-zero secondary group and main surface")
    return (
        f"/INTER/TYPE7/{interface_id}/1\n"
        f"{title[:100]}\n"
        # grnd_IDs surf_IDm Istf Ithe Igap ...
        f"{_line(secondary_group, main_surface, 1000, 0, 1000, 0, 2, 1000, 0, 0)}"
        # Stfac Fric Gapmin Tstart Tstop IBC Inacti VISs VISF Bumult
        f"{_line(1.0, friction, gap_min, 0.0, 1.0e30, 0, 1000, 0.05, 1.0, 0.20)}"
        # If = 0, no extra friction function line is needed.
    )


def render_type2(
    interface_id: int,
    secondary_group: int,
    main_surface: int,
    *,
    search_distance: float,
    title: str = "BGSET",
) -> str:
    if secondary_group <= 0 or main_surface <= 0:
        raise ValueError("TYPE2 requires non-zero secondary group and main surface")
    # Ignore=0, Spot=0, Level=0, Isearch=0, Idel2=0, secondary surface=0,
    # d_search=source SDIST.
    return (
        f"/INTER/TYPE2/{interface_id}/1\n"
        f"{title[:100]}\n"
        f"{_line(secondary_group, main_surface, 0, 0, 0, 0, 0, 0, search_distance)}"
    )


# ---------------------------------------------------------------------------
# Source extraction and translations
# ---------------------------------------------------------------------------


def translate_materials(ir: Any) -> tuple[list[str], list[dict[str, Any]]]:
    mats = getattr(ir, "materials", {})
    plastics = getattr(ir, "plasticity", {})
    plastic_by_mid: dict[int, Any] = {}
    for _, e in plastics.items():
        d = _data(e)
        mid = int(_get(d, "mid", 0))
        plastic_by_mid[mid] = e

    blocks: list[str] = []
    report: list[dict[str, Any]] = []
    for mid, mat in sorted(mats.items(), key=lambda x: int(x[0])):
        mid = int(mid)
        d = _data(mat)
        rho = _float(_get(d, "rho", 0.0))
        E = _float(_get(d, "E", 0.0))
        nu = _float(_get(d, "nu", 0.0))
        pe = plastic_by_mid.get(mid)
        if pe is None:
            blocks.append(render_mat1_law1(mid, rho, E, nu))
            report.append({"source": "MAT1", "id": mid, "target": f"/MAT/LAW1/{mid}/1", "status": "PASS"})
            continue

        pd = _data(pe)
        tid = str(_get(pd, "tid", "") or "").strip()
        typ = str(_get(pd, "type", "") or "").strip().upper()
        yf = int(_get(pd, "yf", 1))
        hr = int(_get(pd, "hr", 1))
        H = _float(_get(pd, "h", 0.0))
        limit1 = _float(_get(pd, "limit1", 0.0))
        if tid or typ != "PLASTIC" or yf != 1 or hr != 1:
            report.append({
                "source": "MATS1", "id": mid, "status": "FAILED_MAPPING",
                "reason": "Only TID-blank, TYPE=PLASTIC, YF=1, HR=1 simple subset is implemented"
            })
            continue
        blocks.append(render_mats1_law2(mid, rho, E, nu, limit1, H))
        report.append({
            "source": "MATS1", "id": mid, "target": f"/MAT/LAW2/{mid}/1",
            "A": limit1, "B": H, "n": 1.0, "C": 0.0, "status": "PASS_WITH_EXPLICIT_SUBSET"
        })
    return blocks, report


def translate_psolids(ir: Any) -> tuple[list[str], list[dict[str, Any]]]:
    elements = getattr(ir, "solid_elements", {})
    pid_types: dict[int, set[str]] = defaultdict(set)
    for e in elements.values():
        d = _data(e)
        pid = int(_get(d, "pid"))
        pid_types[pid].add(str(_get(d, "type", "")))

    plastics = getattr(ir, "plasticity", {})
    plastic_mids = {int(_get(_data(e), "mid", 0)) for e in plastics.values()}
    blocks: list[str] = []
    report: list[dict[str, Any]] = []
    for pid, e in sorted(getattr(ir, "properties", {}).items(), key=lambda x: int(x[0])):
        pid = int(pid)
        d = _data(e)
        mid = int(_get(d, "mid"))
        types = pid_types.get(pid, set())
        blocks.append(render_psolid(pid, mid, element_types=types, material_is_plastic=mid in plastic_mids))
        report.append({
            "source": "PSOLID", "id": pid, "mid": mid,
            "target": f"/PROP/SOLID/{pid}/1", "element_types": sorted(types),
            "status": "PASS_WITH_EXPLICIT_FORMULATION"
        })
    return blocks, report


def translate_conm2(ir: Any, start_id: int = 100000) -> tuple[list[str], list[dict[str, Any]]]:
    blocks: list[str] = []
    report: list[dict[str, Any]] = []
    target_id = start_id
    for cid, e in sorted(getattr(ir, "masses", {}).items(), key=lambda x: int(x[0])):
        cid = int(cid)
        d = _data(e)
        node = int(_get(d, "node"))
        mass = _float(_get(d, "mass", 0.0))
        offset = list(_get(d, "offset", [0.0, 0.0, 0.0]) or [0.0, 0.0, 0.0])
        if any(abs(_float(x)) > 0.0 for x in offset):
            report.append({"source": "CONM2", "id": cid, "status": "FAILED_MAPPING", "reason": "non-zero offset needs a different target representation"})
            continue
        blocks.append(render_admas5(target_id, node, mass))
        report.append({"source": "CONM2", "id": cid, "target": f"/ADMAS/5/{target_id}/1", "node": node, "mass": mass, "status": "PASS"})
        target_id += 1
    return blocks, report


def translate_spc(ir: Any, spc_sid: int, group_id: int) -> tuple[list[str], NodeGroup | None, list[dict[str, Any]]]:
    rows: list[tuple[int, str, float]] = []
    for e in getattr(ir, "boundary_conditions", {}).values():
        sid = getattr(getattr(e, "provenance", None), "source_id", None)
        if sid != spc_sid:
            continue
        raw = _raw(e)
        if len(raw) < 4 or raw[0].strip().upper() not in {"SPC", "SPC1"}:
            continue
        node = int(raw[1])
        dof = str(raw[2]).strip()
        val = _float(raw[3])
        rows.append((node, dof, val))

    if not rows:
        return [], None, []
    if any(abs(v) > 0.0 for _, _, v in rows):
        raise ValueError("active SPC contains non-zero prescribed values; current /BCS translator supports only zero SPC values")
    patterns = sorted({d for _, d, _ in rows})
    if len(patterns) != 1:
        raise ValueError(f"active SPC contains multiple DOF patterns: {patterns}")
    group = NodeGroup(group_id, f"SPC_{spc_sid}", tuple(sorted({n for n, _, _ in rows})))
    block = render_bcs(spc_sid, group_id, patterns[0], f"SPC_{spc_sid}")
    return [block], group, [{
        "source": "SPC", "sid": spc_sid, "records": len(rows),
        "group_id": group_id, "dof": patterns[0], "status": "PASS"
    }]


def translate_tic(ir: Any, ic_sid: int, group_id: int) -> tuple[list[str], NodeGroup | None, list[dict[str, Any]]]:
    vectors: dict[int, list[float]] = {}
    for e in getattr(ir, "initial_conditions", {}).values():
        sid = getattr(getattr(e, "provenance", None), "source_id", None)
        if sid != ic_sid:
            continue
        d = _data(e)
        node = int(_get(d, "node"))
        dof = str(_get(d, "dof", "")).strip()
        vel = _float(_get(d, "velocity", 0.0))
        disp = _float(_get(d, "displacement", 0.0))
        if disp != 0.0:
            raise ValueError(f"TIC node {node}: non-zero initial displacement unsupported")
        if dof not in {"1", "2", "3"}:
            raise ValueError(f"TIC node {node}: only DOF 1/2/3 supported")
        v = vectors.setdefault(node, [0.0, 0.0, 0.0])
        v[int(dof) - 1] = vel

    if not vectors:
        return [], None, []
    unique = {tuple(v) for v in vectors.values()}
    if len(unique) != 1:
        raise ValueError(f"active TIC contains multiple velocity vectors: {sorted(unique)}")
    velocity = next(iter(unique))
    group = NodeGroup(group_id, f"TIC_{ic_sid}", tuple(sorted(vectors)))
    return [render_inivel(group_id, velocity)], group, [{
        "source": "TIC", "sid": ic_sid, "records": sum(1 for _ in getattr(ir, "initial_conditions", {}).values() if getattr(getattr(_, "provenance", None), "source_id", None) == ic_sid),
        "group_id": group_id, "velocity": list(velocity), "status": "PASS"
    }]


def translate_gravity(ir: Any, load_id: int) -> tuple[list[str], list[dict[str, Any]]]:
    e = getattr(ir, "gravity", {}).get(load_id)
    if e is None:
        return [], []
    d = _data(e)
    scale = _float(_get(d, "scale", 1.0))
    vector = [_float(x) * scale for x in _get(d, "vector", [0.0, 0.0, 0.0])]
    return [render_grav(load_id, vector)], [{"source": "GRAV", "id": load_id, "vector": vector, "target": f"/GRAV/{load_id}/1", "status": "PASS"}]


def _parse_bsurfs_raw(raw: Sequence[str]) -> tuple[int, int, list[int]]:
    if not raw:
        raise ValueError("empty BSURFS raw")
    region = int(raw[0])
    tail = [str(x).strip() for x in raw[1:] if str(x).strip()]
    nums = [int(x) for x in tail]
    if len(nums) not in (4, 5):
        raise ValueError(f"BSURFS {region}: expected EID + 3/4 corner nodes, got {len(nums)} numeric fields")
    eid = nums[0]
    nodes = nums[1:]
    return region, eid, nodes


def translate_surfaces(ir: Any) -> tuple[list[str], dict[int, list[int]], list[dict[str, Any]]]:
    by_region: dict[int, list[list[int]]] = defaultdict(list)
    report: list[dict[str, Any]] = []
    for e in getattr(ir, "contact_surfaces", {}).values():
        raw = _raw(e)
        region, eid, nodes = _parse_bsurfs_raw(raw)
        if len(nodes) not in (3, 4):
            raise ValueError(f"BSURFS {region}: only triangular/quadrilateral faces are supported")
        by_region[region].append(nodes)

    blocks: list[str] = []
    surface_nodes: dict[int, list[int]] = {}
    for region, segments in sorted(by_region.items()):
        blocks.append(render_surf_seg(region, segments, f"BSURFS_{region}"))
        surface_nodes[region] = sorted({n for seg in segments for n in seg})
        report.append({
            "source": "BSURFS", "region": region,
            "target": f"/SURF/SEG/{region}/1",
            "segments": len(segments),
            "nodes": len(surface_nodes[region]), "status": "PASS"
        })
    return blocks, surface_nodes, report


def _active_members(table: Mapping[int, Any], selected_id: int, add_card: str) -> list[int]:
    e = table.get(selected_id)
    if e is None:
        raise ValueError(f"missing active set {selected_id}")
    typ = str(_get(_data(e), "type", ""))
    if typ != add_card:
        return [selected_id]
    out: list[int] = []
    for x in _raw(e)[1:]:
        x = str(x).strip()
        if x:
            out.append(int(x))
    return out


def translate_bctset_type7(
    ir: Any,
    selected_bcset: int,
    surface_nodes: Mapping[int, Sequence[int]],
    group_base: int = 210000,
) -> tuple[list[str], list[NodeGroup], list[dict[str, Any]]]:
    table = getattr(ir, "contacts", {})
    ids = _active_members(table, selected_bcset, "BCTADD")
    blocks: list[str] = []
    groups: list[NodeGroup] = []
    report: list[dict[str, Any]] = []
    for i, cid in enumerate(ids):
        e = table.get(cid)
        raw = _raw(e)
        if len(raw) < 4:
            raise ValueError(f"BCTSET {cid}: malformed")
        sid1, tid1 = int(raw[1]), int(raw[2])
        friction = _float(raw[3], 0.0)
        if sid1 not in surface_nodes or tid1 not in surface_nodes:
            raise ValueError(f"BCTSET {cid}: surface {sid1} or {tid1} was not translated")
        group_id = group_base + i
        groups.append(NodeGroup(group_id, f"BCTSET_{cid}_secondary", tuple(surface_nodes[sid1])))
        blocks.append(render_type7(cid, group_id, tid1, friction=friction, gap_min=0.0, title=f"BCTSET_{cid}"))
        report.append({
            "source": "BCTSET", "id": cid, "secondary_surface": sid1,
            "main_surface": tid1, "secondary_group": group_id,
            "friction": friction, "target": f"/INTER/TYPE7/{cid}/1", "status": "PASS_WITH_PARAMETER_MAPPING"
        })
    return blocks, groups, report


def translate_bgset_type2(
    ir: Any,
    selected_bgset: int,
    surface_nodes: Mapping[int, Sequence[int]],
    group_base: int = 220000,
) -> tuple[list[str], list[NodeGroup], list[dict[str, Any]]]:
    table = getattr(ir, "glue_interfaces", {})
    ids = _active_members(table, selected_bgset, "BGADD")
    blocks: list[str] = []
    groups: list[NodeGroup] = []
    report: list[dict[str, Any]] = []
    for i, gid in enumerate(ids):
        e = table.get(gid)
        raw = _raw(e)
        if len(raw) < 4:
            raise ValueError(f"BGSET {gid}: malformed")
        sid1, tid1 = int(raw[1]), int(raw[2])
        search_distance = _float(raw[3], 0.0)
        if sid1 not in surface_nodes or tid1 not in surface_nodes:
            raise ValueError(f"BGSET {gid}: surface {sid1} or {tid1} was not translated")
        group_id = group_base + i
        groups.append(NodeGroup(group_id, f"BGSET_{gid}_secondary", tuple(surface_nodes[sid1])))
        blocks.append(render_type2(gid, group_id, tid1, search_distance=search_distance, title=f"BGSET_{gid}"))
        report.append({
            "source": "BGSET", "id": gid, "secondary_surface": sid1,
            "main_surface": tid1, "secondary_group": group_id,
            "search_distance": search_distance, "target": f"/INTER/TYPE2/{gid}/1", "status": "PASS_WITH_PARAMETER_MAPPING"
        })
    return blocks, groups, report


def translate_rbe2(ir: Any, group_base: int = 230000) -> tuple[list[str], list[NodeGroup], list[dict[str, Any]]]:
    blocks: list[str] = []
    groups: list[NodeGroup] = []
    report: list[dict[str, Any]] = []
    for i, (rid, e) in enumerate(sorted(getattr(ir, "rbe2", {}).items(), key=lambda x: int(x[0]))):
        d = _data(e)
        independent = int(_get(d, "independent"))
        dof = str(_get(d, "cm", "123456")).strip() or "123456"
        deps = tuple(int(x) for x in _get(d, "dependent", []) or [])
        group_id = group_base + i
        groups.append(NodeGroup(group_id, f"RBE2_{rid}", deps))
        blocks.append(render_rbe2(int(rid), independent, dof, group_id, f"RBE2_{rid}"))
        report.append({"source": "RBE2", "id": int(rid), "target": f"/RBE2/{rid}", "group_id": group_id, "status": "PASS"})
    return blocks, groups, report


def parse_rbe3_one_set(entity: Any) -> tuple[int, str, float, str, list[int]]:
    """Parse the actual deck's one-weighting-set RBE3 layout."""
    raw = _raw(entity)
    if len(raw) < 7:
        raise ValueError("RBE3 is too short")
    # [EID, blank, ref_node, ref_dof, weight, indep_dof, nodes...]
    ref_node = int(raw[2]) if str(raw[1]).strip() == "" else int(raw[1])
    if str(raw[1]).strip() == "":
        offset = 2
    else:
        offset = 1
    ref_dof = str(raw[offset + 1]).strip()
    weight = _float(raw[offset + 2])
    indep_dof = str(raw[offset + 3]).strip()
    nodes = [int(x) for x in raw[offset + 4:] if str(x).strip()]
    if not nodes:
        raise ValueError("RBE3 has no independent nodes")
    return ref_node, ref_dof, weight, indep_dof, nodes


def translate_rbe3(ir: Any, group_base: int = 240000) -> tuple[list[str], list[NodeGroup], list[dict[str, Any]]]:
    blocks: list[str] = []
    groups: list[NodeGroup] = []
    report: list[dict[str, Any]] = []
    for i, (rid, e) in enumerate(sorted(getattr(ir, "rbe3", {}).items(), key=lambda x: int(x[0]))):
        ref_node, ref_dof, weight, indep_dof, nodes = parse_rbe3_one_set(e)
        group_id = group_base + i
        groups.append(NodeGroup(group_id, f"RBE3_{rid}_independent", tuple(nodes)))
        blocks.append(render_rbe3(int(rid), ref_node, ref_dof, weight, indep_dof, group_id, f"RBE3_{rid}"))
        report.append({"source": "RBE3", "id": int(rid), "target": f"/RBE3/{rid}", "group_id": group_id, "status": "PASS_ONE_SET"})
    return blocks, groups, report


def build_translation(ir: Any, active: Mapping[str, Any]) -> dict[str, Any]:
    """Master function used by the formal writer.

    It returns blocks in dependency order and a mapping report. The caller
    should still write the model's existing node/element blocks before/after
    these groups according to the project's final Starter deck ordering.
    """
    out: dict[str, Any] = {
        "materials": [], "properties": [], "masses": [], "groups": [],
        "surfaces": [], "constraints": [], "rbes": [], "loads": [],
        "interfaces": [], "mapping": []
    }

    b, rep = translate_materials(ir); out["materials"] = b; out["mapping"].extend(rep)
    b, rep = translate_psolids(ir); out["properties"] = b; out["mapping"].extend(rep)
    b, rep = translate_conm2(ir); out["masses"] = b; out["mapping"].extend(rep)

    # Surfaces first because TYPE7/TYPE2 depend on them.
    b, surface_nodes, rep = translate_surfaces(ir); out["surfaces"] = b; out["mapping"].extend(rep)

    selected = active.get("selected", {}) if isinstance(active, Mapping) else {}
    if selected.get("SPC"):
        b, g, rep = translate_spc(ir, int(selected["SPC"]), 200001)
        out["constraints"].extend(b); out["mapping"].extend(rep)
        if g: out["groups"].append(g.render())

    if selected.get("IC"):
        b, g, rep = translate_tic(ir, int(selected["IC"]), 200000)
        out["loads"].extend(b); out["mapping"].extend(rep)
        if g: out["groups"].append(g.render())

    if selected.get("LOAD"):
        b, rep = translate_gravity(ir, int(selected["LOAD"]))
        out["loads"].extend(b); out["mapping"].extend(rep)

    b, gs, rep = translate_rbe2(ir); out["rbes"].extend(b); out["mapping"].extend(rep); out["groups"].extend(g.render() for g in gs)
    b, gs, rep = translate_rbe3(ir); out["rbes"].extend(b); out["mapping"].extend(rep); out["groups"].extend(g.render() for g in gs)

    if selected.get("BCSET"):
        b, gs, rep = translate_bctset_type7(ir, int(selected["BCSET"]), surface_nodes)
        out["interfaces"].extend(b); out["mapping"].extend(rep); out["groups"].extend(g.render() for g in gs)

    if selected.get("BGSET"):
        b, gs, rep = translate_bgset_type2(ir, int(selected["BGSET"]), surface_nodes)
        out["interfaces"].extend(b); out["mapping"].extend(rep); out["groups"].extend(g.render() for g in gs)

    return out
