"""
Remaining BDF -> OpenRadioss translation primitives for Solution 3-1.

Intended location in the project:
    D:\\BDF2RAD-X\\src\\bdf2rad\\remaining_translators.py

This module is deliberately small and rule-driven. It expects the existing
NastranIR-like objects used by bdf-rad (Entity.data dictionaries) and returns
RAD text blocks plus mapping metadata. The existing writer/converter should
call these functions; do not duplicate the field mappings elsewhere.

The mappings are tailored to the uploaded Solution 3-1(4).bdf:
- MAT1 -> /MAT/LAW1
- MATS1 (simple PLASTIC, YF=1, HR=1, TID blank) -> /MAT/LAW2
  with A=yield stress, B=hardening modulus, n=1, and rate/thermal effects off.
- PSOLID -> /PROP/SOLID with an explicit legal formulation selection.
- CONM2 (node mass; zero offset/inertia in this deck) -> /ADMAS/5
- SPC -> /GRNOD/NODE + /BCS
- TIC -> /GRNOD/NODE + /INIVEL/TRA
- GRAV -> /GRAV
- BSURFS -> /SURF/SEG
- BCTSET -> /INTER/TYPE7
- BGSET -> /INTER/TYPE2
- RBE2/RBE3 -> their native Radioss blocks + /GRNOD/NODE

Do NOT call the MATS1 -> LAW2 branch for a different MATS1 semantics without
first updating the mapper. The exactness of this branch relies on the actual
source subset in Solution 3-1(4).bdf.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import isfinite
from typing import Any, Iterable, Mapping, Sequence


# ----------------------------- generic helpers -----------------------------


def _v(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    if hasattr(obj, "data") and isinstance(obj.data, Mapping):
        return obj.data.get(key, default)
    return getattr(obj, key, default)


def _fmt(x: Any) -> str:
    if isinstance(x, int) and not isinstance(x, bool):
        return str(x)
    if isinstance(x, float):
        if not isfinite(x):
            raise ValueError(f"non-finite value: {x!r}")
        return f"{x:.12g}"
    return str(x)


def _line(*values: Any) -> str:
    return " ".join(_fmt(v) for v in values) + "\n"


def _chunks(values: Sequence[int], n: int = 10) -> Iterable[Sequence[int]]:
    for i in range(0, len(values), n):
        yield values[i : i + n]


def _num(x: Any, default: float = 0.0) -> float:
    if x in (None, ""):
        return default
    return float(x)


def dof_to_trarot(dof: str | int) -> str:
    s = str(dof).strip()
    if not s or any(c not in "123456" for c in s):
        raise ValueError(f"unsupported Nastran DOF: {dof!r}")
    active = set(s)
    return "".join("1" if str(i) in active else "0" for i in range(1, 7))


@dataclass(frozen=True)
class NodeGroupBlock:
    group_id: int
    title: str
    node_ids: tuple[int, ...]
    unit_id: int = 1

    def render(self) -> str:
        if not self.node_ids:
            raise ValueError("empty node group")
        if len(set(self.node_ids)) != len(self.node_ids):
            raise ValueError(f"duplicate nodes in group {self.group_id}")
        out = [f"/GRNOD/NODE/{self.group_id}/{self.unit_id}\n", f"{self.title[:100]}\n"]
        for c in _chunks(self.node_ids):
            out.append(_line(*c))
        return "".join(out)


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
    """Exact for the deck's simple MATS1 subset: von Mises + isotropic linear hardening.

    LAW2 classic form has sigma_y = A + B*ep^n when rate/temp effects are disabled.
    For MATS1 with YF=1, HR=1, H=constant and LIMIT1=sigma_y:
        A = LIMIT1, B = H, n = 1.
    """
    if yield_stress <= 0:
        raise ValueError(f"MATS1 {mid}: LIMIT1 must be > 0")
    if hardening_modulus < 0:
        raise ValueError(f"MATS1 {mid}: H must be >= 0")
    out = [
        f"/MAT/LAW2/{mid}/1\n",
        f"{title or f'MATS1_{mid}'}\n",
        _line(rho),
        _line(E, nu, 0, 0, -1.0e30),
        _line(yield_stress, hardening_modulus, 1.0, 1.0e30, 1.0e30),
        _line(0.0, 1.0e30, 1, 1, 1.0e30, 0.0),
        _line(1.0, 1.0e30, 0.0, 0.0, 1.0e30),
    ]
    return "".join(out)


def render_psolid(
    pid: int,
    title: str,
    *,
    material_id: int,
    preserve_quadratic: bool = True,
    has_tetra10: bool = True,
) -> str:
    """Render a legal /PROP/SOLID block.

    If a property is used by quadratic brick elements, Isolid=16 is selected.
    Otherwise Isolid=24 is used as a robust solid formulation. Tetra10 is
    enabled independently through Itetra10=2.
    """
    isolid = 16 if preserve_quadratic else 24
    is_mstr = 4
    iale = 0
    icpre = -1 if isolid in (14, 17, 18, 24) else 0
    itetra10 = 2 if has_tetra10 else 1000
    inpts = 0
    itetra4 = 1000
    iframe = -1
    dn = 0.0
    return (
        f"/PROP/SOLID/{pid}/1\n"
        f"{title[:100]}\n"
        f"{_line(isolid, is_mstr, iale, icpre, itetra10, inpts, itetra4, iframe, dn)}"
        f"{_line(0.0, 0.0, 0.0, 0.0, 0.0)}"
        f"{_line(0.0, 0.0, 0.0, 0.0, 0.0)}"
        f"{_line(0, 0, 2)}\n"
    )


def render_admas5(admas_id: int, node_id: int, mass: float, title: str | None = None) -> str:
    if mass < 0:
        raise ValueError("negative CONM2 mass")
    return (
        f"/ADMAS/5/{admas_id}/1\n"
        f"{title or f'CONM2_{admas_id}'}\n"
        f"{_line(mass, node_id)}"
    )


def render_bcs(bcs_id: int, node_group_id: int, dof: str | int, title: str = "BCS") -> str:
    return f"/BCS/{bcs_id}\n{title[:100]}\n{_line(dof_to_trarot(dof), 0, node_group_id)}"


def render_inivel(inivel_id: int, node_group_id: int, velocity: Sequence[float], title: str = "Initial_velocity") -> str:
    if len(velocity) != 3:
        raise ValueError("velocity must have three components")
    return (
        f"/INIVEL/TRA/{inivel_id}/1\n"
        f"{title[:100]}\n"
        f"{_line(*velocity, node_group_id, 0)}"
    )


def render_grav(grav_id: int, vector: Sequence[float], title: str = "Gravity") -> str:
    if len(vector) != 3:
        raise ValueError("gravity vector must have three components")
    vx, vy, vz = map(float, vector)
    if abs(vx) > 0 or abs(vy) > 0:
        raise ValueError("this translator's constant gravity mapper expects a pure Z vector")
    return (
        f"/GRAV/{grav_id}/1\n"
        f"{title[:100]}\n"
        f"{_line(0, 'Z', 0, 0, 0, 1.0, vz)}"
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
        f"{_line(reference_node, dof_to_trarot(reference_dof), 1, 0, 0)}"
        f"{_line(weight, dof_to_trarot(independent_dof), 0, independent_group)}"
    )


def render_surf_seg(surface_id: int, segments: Sequence[Sequence[int]], title: str) -> str:
    if not segments:
        raise ValueError(f"surface {surface_id} has no segments")
    out = [f"/SURF/SEG/{surface_id}/1\n", f"{title[:100]}\n"]
    for seg_id, nodes in enumerate(segments, 1):
        if len(nodes) not in (3, 4):
            raise ValueError(f"surface {surface_id}: segment {seg_id} has {len(nodes)} nodes")
        if len(set(nodes)) != len(nodes):
            raise ValueError(f"surface {surface_id}: duplicate segment node")
        out.append(_line(seg_id, *nodes))
    return "".join(out)


def render_type7(
    interface_id: int,
    secondary_group: int,
    main_surface: int,
    friction: float,
    gap_min: float = 0.0,
    title: str = "BCTSET",
) -> str:
    if secondary_group <= 0 or main_surface <= 0:
        raise ValueError("TYPE7 requires real secondary group and main surface IDs")
    # Use explicit stiffness and required fields, no zero placeholder IDs.
    # Gap is constant here because the source BCTSET has MIND=0.
    return (
        f"/INTER/TYPE7/{interface_id}/1\n"
        f"{title[:100]}\n"
        f"{_line(secondary_group, main_surface, 1, 0, 1000, 0, 2, 1000, 0, 0)}"
        f"{_line(1.0, friction, gap_min, 0.0, 1.0e30)}"
        f"{_line(0)}"
    )


def render_type2(
    interface_id: int,
    secondary_group: int,
    main_surface: int,
    search_distance: float,
    title: str = "BGSET",
) -> str:
    if secondary_group <= 0 or main_surface <= 0:
        raise ValueError("TYPE2 requires real secondary group and main surface IDs")
    return (
        f"/INTER/TYPE2/{interface_id}/1\n"
        f"{title[:100]}\n"
        f"{_line(secondary_group, main_surface, 0, 0, 0, 0, 0, 0, search_distance)}"
    )


# ------------------------------ BDF extraction -----------------------------


def _analysis_entities(ir: Any, name: str) -> list[Any]:
    table = getattr(ir, "analysis_controls", {})
    return list(table.get(name, [])) if isinstance(table, Mapping) else []


def _raw(e: Any) -> list[str]:
    raw = _v(e, "raw", [])
    return list(raw or [])


def _source_material_rows(ir: Any) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for mid, e in getattr(ir, "materials", {}).items():
        d = getattr(e, "data", e)
        out[int(mid)] = {
            "rho": float(_v(d, "rho", 0.0)),
            "E": float(_v(d, "E", 0.0)),
            "nu": float(_v(d, "nu", 0.0)),
        }
    for _, e in getattr(ir, "plasticity", {}).items():
        d = getattr(e, "data", e)
        mid = int(_v(d, "mid", e.provenance.source_id if hasattr(e, "provenance") else 0))
        row = out.setdefault(mid, {})
        row.update({
            "mats1": True,
            "tid": str(_v(d, "tid", "") or ""),
            "type": str(_v(d, "type", "") or "").upper(),
            "h": float(_v(d, "h", 0.0)),
            "yf": int(_v(d, "yf", 1)),
            "hr": int(_v(d, "hr", 1)),
            "limit1": float(_v(d, "limit1", 0.0)),
        })
    return out


def translate_materials(ir: Any) -> tuple[list[str], list[dict[str, Any]]]:
    blocks: list[str] = []
    report: list[dict[str, Any]] = []
    rows = _source_material_rows(ir)
    for mid in sorted(rows):
        r = rows[mid]
        rho = float(r.get("rho", 0.0))
        E = float(r.get("E", 0.0))
        nu = float(r.get("nu", 0.0))
        if r.get("mats1"):
            # Only this concrete MATS1 subset is implemented.
            if r.get("tid") or r.get("type") != "PLASTIC" or r.get("yf") != 1 or r.get("hr") != 1:
                report.append({"mid": mid, "status": "FAILED_MAPPING", "reason": "MATS1 semantics outside supported simple von-Mises isotropic-hardening subset"})
                continue
            blocks.append(render_mats1_law2(mid, rho, E, nu, r["limit1"], r["h"]))
            report.append({"mid": mid, "target": f"/MAT/LAW2/{mid}/1", "status": "PASS", "mapping": "MATS1 simple plastic -> J-C with c=0, n=1"})
        else:
            blocks.append(render_mat1_law1(mid, rho, E, nu))
            report.append({"mid": mid, "target": f"/MAT/LAW1/{mid}/1", "status": "PASS"})
    return blocks, report


def translate_conm2(ir: Any, next_id_start: int = 1) -> tuple[list[str], list[dict[str, Any]]]:
    blocks: list[str] = []
    report: list[dict[str, Any]] = []
    next_id = next_id_start
    for cid, e in sorted(getattr(ir, "masses", {}).items()):
        d = getattr(e, "data", e)
        node = int(_v(d, "node"))
        mass = float(_v(d, "mass", 0.0))
        offset = list(_v(d, "offset", [0.0, 0.0, 0.0]) or [0.0, 0.0, 0.0])
        # This uploaded deck has zero offset/inertia. Fail closed otherwise.
        if any(abs(float(x)) > 0.0 for x in offset):
            report.append({"source_id": int(cid), "status": "FAILED_MAPPING", "reason": "non-zero CONM2 offset requires rotational/mass-property mapping"})
            continue
        blocks.append(render_admas5(next_id, node, mass))
        report.append({"source_id": int(cid), "target_id": next_id, "target": f"/ADMAS/5/{next_id}/1", "status": "PASS"})
        next_id += 1
    return blocks, report


def translate_spc(ir: Any, spc_set_id: int, group_id: int) -> tuple[list[str], NodeGroupBlock | None, list[dict[str, Any]]]:
    rows = []
    for key, e in sorted(getattr(ir, "boundary_conditions", {}).items(), key=lambda x: str(x[0])):
        src_sid = getattr(getattr(e, "provenance", None), "source_id", None)
        if src_sid != spc_set_id:
            continue
        d = getattr(e, "data", e)
        raw = _raw(e)
        if str(_v(d, "type", raw[0] if raw else "SPC")).upper() not in {"SPC", "SPC1"}:
            continue
        if raw:
            node = int(raw[1]); dof = str(raw[2]); value = float(raw[3] or 0.0)
        else:
            continue
        if abs(value) > 0.0:
            raise ValueError(f"active SPC {node} has nonzero enforced value")
        rows.append((node, dof))
    if not rows:
        return [], None, []
    patterns = sorted(set(d for _, d in rows))
    if len(patterns) != 1:
        raise ValueError(f"active SPC contains multiple DOF patterns: {patterns}")
    group = NodeGroupBlock(group_id, f"SPC_{spc_set_id}", tuple(sorted({n for n, _ in rows})))
    block = render_bcs(spc_set_id, group_id, patterns[0], f"SPC_{spc_set_id}")
    report = [{"source_spc_set": spc_set_id, "source_records": len(rows), "target_group": group_id, "dof": patterns[0], "status": "PASS"}]
    return [block], group, report


def translate_tic(ir: Any, ic_set_id: int, group_id: int) -> tuple[list[str], NodeGroupBlock | None, list[dict[str, Any]]]:
    rows = []
    for key, e in sorted(getattr(ir, "initial_conditions", {}).items(), key=lambda x: str(x[0])):
        src_sid = getattr(getattr(e, "provenance", None), "source_id", None)
        if src_sid != ic_set_id:
            continue
        d = getattr(e, "data", e)
        node = int(_v(d, "node"))
        dof = str(_v(d, "dof"))
        vel = float(_v(d, "velocity", 0.0))
        disp = float(_v(d, "displacement", 0.0))
        if disp != 0.0:
            raise ValueError(f"TIC node {node}: nonzero initial displacement is unsupported")
        if dof not in {"1", "2", "3"}:
            raise ValueError(f"TIC node {node}: unsupported DOF {dof}")
        rows.append((node, int(dof), vel))
    if not rows:
        return [], None, []
    vectors: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
    for node, comp, vel in rows:
        vectors[node][comp - 1] = vel
    unique = {tuple(v) for v in vectors.values()}
    if len(unique) != 1:
        raise ValueError(f"active TIC contains multiple velocity vectors: {sorted(unique)[:5]}")
    vector = next(iter(unique))
    group = NodeGroupBlock(group_id, f"TIC_{ic_set_id}", tuple(sorted(vectors)))
    block = render_inivel(1, group_id, vector)
    report = [{"source_ic_set": ic_set_id, "source_records": len(rows), "target_group": group_id, "velocity": list(vector), "status": "PASS"}]
    return [block], group, report


def translate_gravity(ir: Any, load_id: int) -> tuple[list[str], list[dict[str, Any]]]:
    e = getattr(ir, "gravity", {}).get(load_id)
    if e is None:
        return [], []
    d = getattr(e, "data", e)
    scale = float(_v(d, "scale", 1.0))
    vector = [scale * float(x) for x in _v(d, "vector", [0.0, 0.0, 0.0])]
    return [render_grav(load_id, vector)], [{"source_grav": load_id, "vector": vector, "target": f"/GRAV/{load_id}/1", "status": "PASS"}]


def _bsurfs_by_region(ir: Any) -> dict[int, list[list[int]]]:
    out: dict[int, list[list[int]]] = defaultdict(list)
    for sid, e in getattr(ir, "contact_surfaces", {}).items():
        raw = _raw(e)
        if len(raw) < 5:
            continue
        try:
            region = int(raw[0]); nodes = [int(x) for x in raw[2:] if str(x).strip()]
        except ValueError:
            continue
        if len(nodes) in (3, 4):
            out[region].append(nodes)
    return out


def translate_surfaces(ir: Any) -> tuple[list[str], dict[int, int], list[dict[str, Any]]]:
    by_region = _bsurfs_by_region(ir)
    blocks = []
    mapping = {}
    report = []
    for region in sorted(by_region):
        blocks.append(render_surf_seg(region, by_region[region], f"BSURFS_{region}"))
        mapping[region] = region
        report.append({"source_region": region, "target_surface": region, "segment_count": len(by_region[region]), "status": "PASS"})
    return blocks, mapping, report


def _active_set_members(ir: Any, table_name: str, add_card: str, selected_id: int) -> list[int]:
    table = getattr(ir, "contacts" if table_name == "BCTSET" else "glue_interfaces", {})
    e = table.get(selected_id)
    if e is None:
        return []
    typ = str(_v(getattr(e, "data", e), "type", ""))
    raw = _raw(e)
    if typ != add_card:
        return [selected_id]
    out: list[int] = []
    for x in raw[1:]:
        if x:
            out.append(int(x))
    return out


def translate_bctset_type7(ir: Any, selected_bcset: int) -> tuple[list[str], list[dict[str, Any]]]:
    table = getattr(ir, "contacts", {})
    ids = _active_set_members(ir, "BCTSET", "BCTADD", selected_bcset)
    blocks = []; report = []
    for cid in ids:
        e = table.get(cid)
        if e is None:
            continue
        raw = _raw(e)
        if len(raw) < 3:
            raise ValueError(f"BCTSET {cid}: malformed")
        sid1, tid1 = int(raw[1]), int(raw[2])
        friction = float(raw[3] or 0.0) if len(raw) > 3 else 0.0
        blocks.append(render_type7(cid, sid1, tid1, friction, 0.0, f"BCTSET_{cid}"))
        report.append({"source_bctset": cid, "secondary_surface": sid1, "main_surface": tid1, "friction": friction, "target": f"/INTER/TYPE7/{cid}/1", "status": "PASS_WITH_PARAMETER_APPROXIMATION"})
    return blocks, report


def translate_bgset_type2(ir: Any, selected_bgset: int) -> tuple[list[str], list[dict[str, Any]]]:
    table = getattr(ir, "glue_interfaces", {})
    ids = _active_set_members(ir, "BGSET", "BGADD", selected_bgset)
    blocks = []; report = []
    for gid in ids:
        e = table.get(gid)
        if e is None:
            continue
        raw = _raw(e)
        if len(raw) < 4:
            continue
        sid1, tid1 = int(raw[1]), int(raw[2])
        search_distance = float(raw[3] or 0.0)
        blocks.append(render_type2(gid, sid1, tid1, search_distance, f"BGSET_{gid}"))
        report.append({"source_bgset": gid, "secondary_surface": sid1, "main_surface": tid1, "search_distance": search_distance, "target": f"/INTER/TYPE2/{gid}/1", "status": "PASS_WITH_PARAMETER_APPROXIMATION"})
    return blocks, report


# ----------------------------- master integration --------------------------


def build_remaining_translation(ir: Any, active: Mapping[str, Any]) -> dict[str, Any]:
    """Generate all currently missing translation blocks in one deterministic call.

    The caller should concatenate the returned blocks into the existing writer's
    Starter deck in dependency order: materials/properties first, groups/surfaces,
    constraints/RBEs/loads/interfaces, then elements.
    """
    result: dict[str, Any] = {
        "material_blocks": [], "property_blocks": [], "mass_blocks": [],
        "group_blocks": [], "surface_blocks": [], "constraint_blocks": [],
        "initial_condition_blocks": [], "gravity_blocks": [], "rbe_blocks": [],
        "interface_blocks": [], "mapping": [],
    }

    mats, mat_report = translate_materials(ir)
    result["material_blocks"] = mats
    result["mapping"].extend(mat_report)

    # Infer whether each property is likely used by quadratic elements from the source mesh.
    pid_to_types: dict[int, set[str]] = defaultdict(set)
    for e in getattr(ir, "solid_elements", {}).values():
        d = getattr(e, "data", e)
        pid = int(_v(d, "pid"))
        pid_to_types[pid].add(str(_v(d, "type", "")))
    for pid, e in sorted(getattr(ir, "properties", {}).items()):
        d = getattr(e, "data", e)
        mid = int(_v(d, "mid"))
        types = pid_to_types.get(int(pid), set())
        result["property_blocks"].append(render_psolid(int(pid), f"PSOLID_{pid}", material_id=mid, preserve_quadratic=True, has_tetra10=("CTETRA" in types)))
        result["mapping"].append({"source_psolid": int(pid), "target": f"/PROP/SOLID/{pid}/1", "material": mid, "status": "PASS_WITH_EXPLICIT_TARGET_FORMULATION"})

    masses, mass_report = translate_conm2(ir, 100000)
    result["mass_blocks"] = masses
    result["mapping"].extend(mass_report)

    selected_spc = int(active.get("selected", {}).get("SPC", 0)) if active.get("selected") else 0
    if selected_spc:
        b, g, rep = translate_spc(ir, selected_spc, 200001)
        result["constraint_blocks"].extend(b)
        if g:
            result["group_blocks"].append(g.render())
        result["mapping"].extend(rep)

    selected_ic = int(active.get("selected", {}).get("IC", 0)) if active.get("selected") else 0
    if selected_ic:
        b, g, rep = translate_tic(ir, selected_ic, 200000)
        result["initial_condition_blocks"].extend(b)
        if g:
            result["group_blocks"].append(g.render())
        result["mapping"].extend(rep)

    selected_load = int(active.get("selected", {}).get("LOAD", 0)) if active.get("selected") else 0
    if selected_load:
        b, rep = translate_gravity(ir, selected_load)
        result["gravity_blocks"].extend(b)
        result["mapping"].extend(rep)

    surf_blocks, surf_map, surf_report = translate_surfaces(ir)
    result["surface_blocks"] = surf_blocks
    result["mapping"].extend(surf_report)

    selected_bcset = int(active.get("selected", {}).get("BCSET", 0)) if active.get("selected") else 0
    if selected_bcset:
        b, rep = translate_bctset_type7(ir, selected_bcset)
        result["interface_blocks"].extend(b)
        result["mapping"].extend(rep)

    selected_bgset = int(active.get("selected", {}).get("BGSET", 0)) if active.get("selected") else 0
    if selected_bgset:
        b, rep = translate_bgset_type2(ir, selected_bgset)
        result["interface_blocks"].extend(b)
        result["mapping"].extend(rep)

    return result
