from __future__ import annotations

from ..model import *
from .cards import iter_cards, read_case_control, nastran_float


SUPPORTED = {
    "GRID",
    "CTETRA",
    "CHEXA",
    "CPENTA",
    "PSOLID",
    "MAT1",
    "MATS1",
    "CONM2",
    "RBE2",
    "RBE3",
    "SPC",
    "SPC1",
    "SPCADD",
    "TIC",
    "GRAV",
    "BSURFS",
    "BCRPARA",
    "BCTSET",
    "BCTADD",
    "BGSET",
    "BGADD",
    "NLCNTLG",
    "NLCNTL2",
    "TSTEP1",
    "TEMPD",
    "TEMP",
    "PARAM",
    "BCSET",
    "IC",
    "LOAD",
    "TSTEP",
    "SUBCASE",
}


def _i(x, d=0):
    try:
        text = str(x).strip()

        if not text:
            return d

        return int(float(text))

    except Exception:
        return d


def _f(x, d=None):
    try:
        text = str(x).strip()

        if not text:
            return d

        return nastran_float(text)

    except Exception:
        return d


def F(f, i, d=""):
    return f[i] if i < len(f) else d


def _clean_component(value: str) -> str:
    """
    Normalize an SPC component field.

    A valid Nastran SPC component for a grid is:
        1
        12
        123
        123456
        etc.

    No embedded blanks are legal.

    This function intentionally does NOT silently truncate a malformed
    value. It only strips surrounding whitespace.
    """
    return str(value).strip()


def _parse_spc_fields(card):
    """
    Parse SPC robustly.

    Preferred path:
        use the standard fixed-field parser output.

    Fallback path:
        if the fixed-field result produces an invalid C field, use
        whitespace-separated interpretation of the original SPC line.

    The fallback is deliberately limited to SPC and is only activated
    when the strict parsed component field is invalid.

    Expected semantic fields:
        SID
        GID
        C
        D
    """

    f = card.fields

    sid = _i(F(f, 1))
    gid = _i(F(f, 2))
    comp = _clean_component(F(f, 3))
    disp = F(f, 4)

    # ------------------------------------------------------------
    # Standard fixed-field result is valid.
    # ------------------------------------------------------------
    if (
        comp
        and comp.isdigit()
        and all(ch in "0123456" for ch in comp)
        and len(comp) <= 6
    ):
        return sid, gid, comp, _f(disp, 0.0) or 0.0

    # ------------------------------------------------------------
    # Fallback for malformed / loosely aligned SPC lines.
    #
    # Example:
    #   SPC     901     1      123456  0.0
    #
    # The test fixture visually follows the Nastran layout but does
    # not actually align every field to 8-character boundaries.
    # ------------------------------------------------------------
    raw = card.raw[0] if card.raw else ""

    tokens = raw.strip().split()

    if len(tokens) >= 5:
        raw_name = tokens[0].upper().rstrip("*")

        if raw_name == "SPC":
            try:
                sid2 = int(tokens[1])
                gid2 = int(tokens[2])
                comp2 = tokens[3].strip()

                # Validate component according to Nastran SPC rules.
                if not (
                    comp2
                    and comp2.isdigit()
                    and 1 <= len(comp2) <= 6
                    and all(ch in "0123456" for ch in comp2)
                ):
                    raise ValueError(
                        f"Invalid SPC component after fallback: "
                        f"{comp2!r}"
                    )

                d2 = (
                    _f(tokens[4], 0.0)
                    if len(tokens) >= 5
                    else 0.0
                )

                return (
                    sid2,
                    gid2,
                    comp2,
                    d2 if d2 is not None else 0.0,
                )

            except Exception:
                pass

    raise ValueError(
        f"Invalid SPC fields at line {card.line}: "
        f"fields={f[:8]!r}, raw={raw!r}"
    )


def _parse_solid_connectivity(card, card_name, expected_nodes):
    """
    Parse solid-element connectivity while preserving compatibility
    with both:

      1) normal Nastran fixed-width fields
      2) loosely aligned whitespace-separated BDF lines

    The existing fixed-width parser remains the first choice.

    Only when the fixed-width result contains fewer than the expected
    number of node IDs do we fall back to the original raw BDF line(s).

    No node ID is invented or guessed.
    """

    # ============================================================
    # FIRST: existing fixed-width parser result
    # ============================================================
    fixed_nodes = [
        _i(x)
        for x in card.fields[3:]
        if str(x).strip()
    ]

    if len(fixed_nodes) >= expected_nodes:
        return fixed_nodes

    # ============================================================
    # SECOND: raw-line whitespace fallback
    # ============================================================
    #
    # Some BDF test decks are visually written in a fixed-style
    # layout, but the columns are not actually aligned on 8-character
    # boundaries.
    #
    # Example:
    #
    # CHEXA   10      1       1       2       3       4       5       6       7       8
    #
    # The semantic content is:
    #
    # CHEXA 10 1 1 2 3 4 5 6 7 8
    #
    # The 8-character parser can split "9002" into "9" + "002".
    # Whitespace parsing of the original raw line avoids that.
    # ============================================================

    raw_tokens = []

    for raw_line in card.raw:
        raw_tokens.extend(
            raw_line.strip().split()
        )

    if raw_tokens:

        raw_name = (
            raw_tokens[0]
            .upper()
            .rstrip("*")
        )

        if raw_name == card_name:

            # token 0 = card name
            # token 1 = element ID
            # token 2 = property ID
            # token 3... = node IDs
            candidate = [
                _i(x)
                for x in raw_tokens[3:]
                if str(x).strip()
            ]

            if len(candidate) >= expected_nodes:
                return candidate

    # ============================================================
    # LAST: return original fixed-field result
    #
    # Do not silently repair a malformed card.
    # plugin_helpers.faces_for_element() will then issue a clear
    # validation error for insufficient connectivity.
    # ============================================================

    return fixed_nodes


def read_model(path, encoding="gb18030") -> Model:
    m = Model()

    # ------------------------------------------------------------
    # Case Control / Executive
    # ------------------------------------------------------------
    c, e = read_case_control(
        path,
        encoding,
    )

    m.control_lines = c
    m.executive = e

    # ------------------------------------------------------------
    # Bulk Data
    # ------------------------------------------------------------
    for card in iter_cards(
        path,
        encoding,
    ):
        f = card.fields
        n = card.name

        m.card_counts[n] = (
            m.card_counts.get(n, 0) + 1
        )

        try:

            # ====================================================
            # GRID
            # ====================================================
            if n == "GRID":

                nid = _i(
                    F(f, 1)
                )

                # Some decks omit the optional CP field and use the
                # compact form GRID,ID,X,Y,Z.  The fixed-field parser
                # then returns only five fields including the name.
                # Detect that form before applying the standard
                # GRID,ID,CP,X,Y,Z offsets; otherwise coordinates are
                # shifted and all Z values can collapse to zero.
                compact_grid = len(f) <= 5

                if compact_grid:

                    cp = 0

                    x = (
                        _f(F(f, 2), 0.0)
                        or 0.0
                    )

                    y = (
                        _f(F(f, 3), 0.0)
                        or 0.0
                    )

                    z = (
                        _f(F(f, 4), 0.0)
                        or 0.0
                    )

                else:

                    cp = _i(
                        F(f, 2)
                    )

                    x = (
                        _f(F(f, 3), 0.0)
                        or 0.0
                    )

                    y = (
                        _f(F(f, 4), 0.0)
                        or 0.0
                    )

                    z = (
                        _f(F(f, 5), 0.0)
                        or 0.0
                    )

                cd = _i(
                    F(f, 6)
                )

                m.nodes[nid] = Node(
                    nid,
                    (x, y, z),
                    cp,
                    cd,
                )

            # ====================================================
            # SOLID ELEMENTS
            # ====================================================
            elif n in (
                "CTETRA",
                "CHEXA",
                "CPENTA",
            ):

                eid = _i(
                    F(f, 1)
                )

                pid = _i(
                    F(f, 2)
                )

                expected_nodes = {
                    "CTETRA": 4,
                    "CHEXA": 8,
                    "CPENTA": 6,
                }[n]

                nodes = _parse_solid_connectivity(
                    card,
                    n,
                    expected_nodes,
                )

                m.elements[eid] = Element(
                    eid,
                    n,
                    pid,
                    nodes,
                )

            # ====================================================
            # PSOLID
            # ====================================================
            elif n == "PSOLID":

                pid = _i(
                    F(f, 1)
                )

                mid = _i(
                    F(f, 2)
                )

                m.props[pid] = Property(
                    pid,
                    mid,
                    f,
                )

            # ====================================================
            # MAT1
            # ====================================================
            elif n == "MAT1":

                mid = _i(
                    F(f, 1)
                )

                E = (
                    _f(F(f, 2), 0.0)
                    or 0.0
                )

                G = (
                    _f(F(f, 3), 0.0)
                    or 0.0
                )

                nu = (
                    _f(F(f, 4), 0.0)
                    or 0.0
                )

                rho = (
                    _f(F(f, 5), 0.0)
                    or 0.0
                )

                alpha = (
                    _f(F(f, 6), 0.0)
                    or 0.0
                )

                if (
                    G == 0
                    and E
                    and nu
                ):
                    G = E / (
                        2.0 * (1.0 + nu)
                    )

                if (
                    nu == 0
                    and E
                    and G
                ):
                    nu = (
                        E / (2.0 * G)
                    ) - 1.0

                m.mats[mid] = Material(
                    mid,
                    E,
                    nu,
                    rho,
                    G,
                    alpha,
                )

            # ====================================================
            # MATS1
            # ====================================================
            elif n == "MATS1":

                mid = _i(
                    F(f, 1)
                )

                m.plastics[mid] = Plastic(
                    mid,
                    _i(F(f, 2)),
                    F(f, 3).upper(),
                    _f(F(f, 4), 0.0) or 0.0,
                    _i(F(f, 5), 1),
                    _i(F(f, 6), 1),
                    _f(F(f, 7), 0.0) or 0.0,
                )

            # ====================================================
            # CONM2
            # ====================================================
            elif n == "CONM2":

                eid = _i(
                    F(f, 1)
                )

                gid = _i(
                    F(f, 2)
                )

                cid = _i(
                    F(f, 3)
                )

                mass = (
                    _f(F(f, 4), 0.0)
                    or 0.0
                )

                offset = (
                    _f(F(f, 5), 0.0) or 0.0,
                    _f(F(f, 6), 0.0) or 0.0,
                    _f(F(f, 7), 0.0) or 0.0,
                )

                m.masses[eid] = Mass(
                    eid,
                    gid,
                    mass,
                    offset,
                    cid,
                )

            # ====================================================
            # RBE2
            # ====================================================
            elif n == "RBE2":

                rid = _i(
                    F(f, 1)
                )

                ref_node = _i(
                    F(f, 2)
                )

                comp = (
                    F(f, 3)
                    or "123456"
                )

                dep = [
                    _i(x)
                    for x in f[4:]
                    if str(x).strip()
                ]

                m.rbe2[rid] = RBE2(
                    rid,
                    ref_node,
                    comp,
                    dep,
                )

            # ====================================================
            # RBE3
            # ====================================================
            elif n == "RBE3":

                rid = _i(
                    F(f, 1)
                )

                ref_node = _i(
                    F(f, 3)
                )

                ref_comp = (
                    F(f, 4)
                    or "123456"
                )

                weight = (
                    _f(F(f, 5), 1.0)
                    or 1.0
                )

                indep_comp = (
                    F(f, 6)
                    or "123"
                )

                indep_nodes = [
                    _i(x)
                    for x in f[7:]
                    if str(x).strip()
                ]

                m.rbe3[rid] = RBE3(
                    rid,
                    ref_node,
                    ref_comp,
                    weight,
                    indep_comp,
                    indep_nodes,
                )

            # ====================================================
            # SPC
            # ====================================================
            elif n == "SPC":

                sid, gid, comp, disp = (
                    _parse_spc_fields(
                        card
                    )
                )

                m.spcs.append(
                    SPC(
                        sid,
                        gid,
                        comp,
                        disp,
                    )
                )

            # ====================================================
            # SPC1
            # ====================================================
            elif n == "SPC1":

                sid = _i(
                    F(f, 1)
                )

                comp = F(
                    f,
                    2,
                )

                m.spcs.extend(
                    SPC(
                        sid,
                        _i(x),
                        comp,
                        0.0,
                    )
                    for x in f[3:]
                    if str(x).strip()
                )

            # ====================================================
            # TIC
            # ====================================================
            elif n == "TIC":

                m.tics.append(
                    TIC(
                        _i(F(f, 1)),
                        _i(F(f, 2)),
                        _i(F(f, 3)),
                        _f(F(f, 4), None),
                        _f(F(f, 5), None),
                    )
                )

            # ====================================================
            # GRAV
            # ====================================================
            elif n == "GRAV":

                gid = _i(
                    F(f, 1)
                )

                cid = _i(
                    F(f, 2)
                )

                scale = (
                    _f(F(f, 3), 1.0)
                    or 1.0
                )

                vector = (
                    _f(F(f, 4), 0.0) or 0.0,
                    _f(F(f, 5), 0.0) or 0.0,
                    _f(F(f, 6), 0.0) or 0.0,
                )

                m.gravs[gid] = Gravity(
                    gid,
                    cid,
                    scale,
                    vector,
                )

            # ====================================================
            # TSTEP1
            # ====================================================
            elif n == "TSTEP1":

                tid = _i(
                    F(f, 1)
                )

                dt = (
                    _f(F(f, 2), 0.0)
                    or 0.0
                )

                nsteps = _i(
                    F(f, 3)
                )

                method = F(
                    f,
                    4,
                )

                m.tsteps[tid] = TStep(
                    tid,
                    dt,
                    nsteps,
                    method,
                )

            # ====================================================
            # BCRPARA
            # ====================================================
            elif n == "BCRPARA":

                bid = _i(
                    F(f, 1)
                )

                mu = (
                    _f(F(f, 3), 0.0)
                    or 0.0
                )

                formulation = (
                    F(f, 4)
                    or "FLEX"
                )

                m.bcrpara[bid] = BCRPara(
                    bid,
                    mu,
                    formulation,
                )

            # ====================================================
            # BCTSET
            # ====================================================
            elif n == "BCTSET":

                bid = _i(
                    F(f, 1)
                )

                m.bctsets[bid] = BCTSet(
                    bid,
                    _i(F(f, 2)),
                    _i(F(f, 3)),
                    _f(F(f, 4), 0.0) or 0.0,
                    _i(F(f, 5)),
                    _f(F(f, 6), 0.0) or 0.0,
                    _i(F(f, 7), 1),
                )

            # ====================================================
            # BGSET
            # ====================================================
            elif n == "BGSET":

                bid = _i(
                    F(f, 1)
                )

                m.bgsets[bid] = BGSet(
                    bid,
                    _i(F(f, 2)),
                    _i(F(f, 3)),
                    _f(F(f, 4), 1.0) or 1.0,
                    _f(F(f, 5), 0.0) or 0.0,
                )

            # ====================================================
            # BCTADD
            # ====================================================
            elif n == "BCTADD":

                m.bctadds[
                    _i(F(f, 1))
                ] = [
                    _i(x)
                    for x in f[2:]
                    if str(x).strip()
                ]

            # ====================================================
            # BGADD
            # ====================================================
            elif n == "BGADD":

                m.bgadds[
                    _i(F(f, 1))
                ] = [
                    _i(x)
                    for x in f[2:]
                    if str(x).strip()
                ]

            # ====================================================
            # BSURFS
            # ====================================================
            elif n == "BSURFS":

                vals = [
                    _i(x)
                    for x in f[5:]
                    if str(x).strip()
                ]

                faces = []

                for k in range(
                    0,
                    len(vals),
                    4,
                ):

                    chunk = vals[
                        k:k + 4
                    ]

                    if len(chunk) == 4:

                        faces.append(
                            tuple(chunk)
                        )

                sid = _i(
                    F(f, 1)
                )

                m.bsurfs[sid] = BsurfS(
                    sid,
                    faces,
                )

            # ====================================================
            # Unsupported
            # ====================================================
            elif n not in SUPPORTED:

                m.diagnostics.append(
                    {
                        "severity":
                            "UNSUPPORTED_CARD",
                        "card": n,
                        "line": card.line,
                        "fields": f[:12],
                    }
                )

        except Exception as ex:

            m.diagnostics.append(
                {
                    "severity":
                        "PARSE_ERROR",
                    "card": n,
                    "line": card.line,
                    "error": str(ex),
                    "fields": f[:12],
                }
            )

    # ------------------------------------------------------------
    # Case Control parsing
    # ------------------------------------------------------------
    for ln in c:

        s = ln.strip()

        if "=" in s:

            key, value = s.split(
                "=",
                1,
            )

            m.case[
                key.strip().upper()
            ] = value.strip()

        elif s.upper().startswith(
            "SUBCASE"
        ):

            parts = s.split()

            m.case["_SUBCASE"] = (
                parts[1]
                if len(parts) > 1
                else "1"
            )

    return m