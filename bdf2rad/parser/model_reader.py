from __future__ import annotations

from ..model import (
    BCTSet,
    BCRPara,
    BsurfS,
    BGSet,
    Element,
    Gravity,
    Material,
    Mass,
    Model,
    Node,
    Plastic,
    Property,
    RBE2,
    RBE3,
    SPC,
    TStep,
    TIC,
)

from .cards import (
    iter_cards,
    nastran_float,
    read_case_control,
)


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


def _text(value):
    if value is None:
        return ""
    return str(value).strip()


def _i(value, default=None):
    text = _text(value)

    if not text:
        return default

    try:
        return int(float(text))
    except (TypeError, ValueError):
        return default


def _f(value, default=None):
    text = _text(value)

    if not text:
        return default

    try:
        return nastran_float(text)
    except (TypeError, ValueError):
        return default


def F(fields, index, default=""):
    if index < 0 or index >= len(fields):
        return default
    return fields[index]


def _required_int(value, name, line):
    result = _i(value, None)

    if result is None:
        raise ValueError(
            f"{name} is missing or invalid at BDF line "
            f"{line}: {value!r}"
        )

    return result


def _required_float(value, name, line):
    result = _f(value, None)

    if result is None:
        raise ValueError(
            f"{name} is missing or invalid at BDF line "
            f"{line}: {value!r}"
        )

    return result


def _valid_positive_integer(value):
    result = _i(value, None)
    return result is not None and result > 0


def _valid_rbe_component(value, max_digits=6):
    """Return True when *value* is a Nastran RBE component mask.

    RBE3 REFC/CM fields contain one or more digits from 1..6 with no
    embedded blanks.  Treating this pattern semantically is important when
    recovering decks that omit the otherwise-blank third field of RBE3.
    """
    text = _text(value)
    if not text or len(text) > max_digits:
        return False
    return text.isdigit() and all(ch in "123456" for ch in text)


def _parse_rbe3(card, model):
    """Parse one Nastran RBE3 weighting set without node-existence guessing.

    Canonical Card.fields must preserve blank fields. Therefore the presence of
    the published blank field after EID is the authoritative discriminator:

        official: RBE3,EID,,REFGRID,REFC,WT,C,G1,...
        compact:  RBE3,EID,REFGRID,REFC,WT,C,G1,...

    The old implementation used ``REFGRID in model.nodes`` to choose between
    the two layouts. That made the interpretation depend on the model contents
    rather than the source syntax and caused T07-style RBE3 records to flip
    interpretations after unrelated GRID changes.
    """
    f = list(card.fields or [])
    if len(f) < 6:
        raise ValueError(f"RBE3 at line {card.line}: too few fields: {f!r}")

    rid = _required_int(F(f, 1), "RBE3 ID", card.line)

    if _text(F(f, 2)) == "":
        # Official Nastran layout.
        ref = _required_int(F(f, 3), "RBE3 REFGRID", card.line)
        ref_comp = _text(F(f, 4))
        weight = _f(F(f, 5), None)
        ind_comp = _text(F(f, 6))
        node_start = 7
        layout = "official"
    else:
        # Compatibility compact layout with the published blank omitted.
        ref = _required_int(F(f, 2), "RBE3 REFGRID", card.line)
        ref_comp = _text(F(f, 3))
        weight = _f(F(f, 4), None)
        ind_comp = _text(F(f, 5))
        node_start = 6
        layout = "compact_omitted_blank"

    if ref <= 0:
        raise ValueError(f"RBE3 {rid} at line {card.line}: reference node must be > 0, got {ref}")
    if not _valid_rbe_component(ref_comp, 6):
        raise ValueError(f"RBE3 {rid} at line {card.line}: invalid REFC {ref_comp!r}")
    if weight is None:
        raise ValueError(f"RBE3 {rid} at line {card.line}: missing weighting factor")
    if not _valid_rbe_component(ind_comp, 3):
        raise ValueError(f"RBE3 {rid} at line {card.line}: invalid weighting component {ind_comp!r}")

    independent: list[int] = []
    for value in f[node_start:]:
        text = _text(value)
        if not text:
            continue
        node_id = _i(text, None)
        if node_id is None:
            # A second weighting-set sequence is not represented by the current
            # legacy RBE3 model. Refuse to reinterpret arbitrary numbers as GRID IDs.
            raise ValueError(
                f"RBE3 {rid} at line {card.line}: unsupported additional weighting-set data "
                f"or invalid independent node field {value!r}"
            )
        if node_id <= 0:
            raise ValueError(f"RBE3 {rid} at line {card.line}: invalid node ID {node_id}")
        independent.append(node_id)

    independent = list(dict.fromkeys(independent))
    if not independent:
        raise ValueError(f"RBE3 {rid} at line {card.line}: no independent grid nodes found")

    missing = [node_id for node_id in independent if node_id not in model.nodes]
    if missing:
        preview = ", ".join(str(node_id) for node_id in missing[:20])
        raise ValueError(f"RBE3 {rid}: undefined independent node(s): {preview}")

    if ref not in model.nodes:
        raise ValueError(f"RBE3 {rid}: undefined reference node {ref}")

    if ref in independent:
        raise ValueError(
            f"RBE3 {rid}: reference node {ref} is also listed as an independent node"
        )

    if layout == "compact_omitted_blank":
        model.diagnostics.append({
            "card": "RBE3",
            "id": rid,
            "line": card.line,
            "warning": "Recovered RBE3 compact layout because the published blank field after EID was omitted",
            "reference_node": ref,
        })

    return RBE3(
        rid=rid,
        ref=ref,
        ref_comp=ref_comp,
        weight=float(weight),
        ind_comp=ind_comp,
        independent=independent,
    )


def _parse_solid_connectivity(card):
    """Parse solid connectivity without compacting positional fields.

    Normal source elements are strict about their corner connectivity:
      CTETRA  G1-G4
      CPENTA  G1-G6
      CHEXA   G1-G8

    Optional midside/edge positions may be blank or zero. Full higher-order
    connectivity is preserved for the corresponding translator.

    The repository also contains an intentional BSURFS validation fixture that
    uses an incomplete seven-node CHEXA. The BSURFS translator explicitly
    documents a compatibility path for that case: it resolves a face from the
    nodes that actually exist on the incomplete CHEXA. Therefore a CHEXA with
    exactly 4..7 contiguous populated corner positions (G1..Gn), no populated
    position after the first missing corner, and no populated optional nodes is
    allowed through as a compatibility topology. It is not treated as a
    normal CHEXA8 and cannot be emitted by the CHEXA8 translator because its
    node count is not 8.
    """
    name = card.name
    fields = list(getattr(card, "fields", ()) or ())
    data = fields[3:]

    corner_count = {"CTETRA": 4, "CPENTA": 6, "CHEXA": 8}[name]
    optional_count = {"CTETRA": 6, "CPENTA": 9, "CHEXA": 12}[name]
    max_count = corner_count + optional_count

    slots: list[int | None] = []
    first_missing_corner: int | None = None

    for pos in range(max_count):
        value = data[pos] if pos < len(data) else ""
        text = _text(value)
        if not text:
            slots.append(None)
            if pos < corner_count and first_missing_corner is None:
                first_missing_corner = pos
            continue

        node_id = _i(text, None)
        if node_id is None:
            raise ValueError(
                f"{name} at line {card.line}: invalid node field {value!r} at G{pos + 1}"
            )
        if node_id < 0:
            raise ValueError(
                f"{name} at line {card.line}: negative node ID {node_id} at G{pos + 1}"
            )
        if node_id == 0:
            slots.append(None)
            if pos < corner_count and first_missing_corner is None:
                first_missing_corner = pos
        else:
            slots.append(node_id)

    if len(data) > max_count and any(_text(v) for v in data[max_count:]):
        raise ValueError(
            f"{name} at line {card.line}: too many connectivity fields; maximum G1-G{max_count}"
        )

    corners = slots[:corner_count]
    missing = [f"G{i}" for i, nid in enumerate(corners, 1) if nid is None]

    if missing:
        if name == "CHEXA":
            present_corner = [nid for nid in corners if nid is not None]
            later_corner_present = (
                first_missing_corner is not None
                and any(nid is not None for nid in corners[first_missing_corner + 1:])
            )
            optional_present = any(nid is not None for nid in slots[corner_count:])

            # Explicit repository compatibility: incomplete seven-node CHEXA
            # with the final corner (G8) omitted, or the more general prefix
            # form G1..Gn with n in [4,7].
            if (
                first_missing_corner is not None
                and not later_corner_present
                and not optional_present
                and 4 <= len(present_corner) <= 7
            ):
                ids = [int(nid) for nid in present_corner]
                if len(set(ids)) != len(ids):
                    raise ValueError(
                        f"{name} at line {card.line}: duplicate node IDs in incomplete compatibility topology"
                    )
                return ids

        raise ValueError(
            f"{name} at line {card.line}: mandatory corner node(s) {missing} are blank/zero"
        )

    corner_ids = [int(nid) for nid in corners]
    if len(set(corner_ids)) != len(corner_ids):
        raise ValueError(
            f"{name} at line {card.line}: duplicate mandatory corner node IDs {corner_ids}"
        )

    optional = slots[corner_count:]
    present_optional = [int(nid) for nid in optional if nid is not None]

    if present_optional and len(present_optional) == optional_count:
        return corner_ids + present_optional

    return corner_ids

def _raw_tokens(card):
    """Return whitespace-separated tokens from the original card lines."""
    tokens = []
    for raw_line in getattr(card, "raw", ()) or ():
        tokens.extend(str(raw_line).strip().split())
    return tokens


def _is_standard_small_field_line(raw_line):
    """Check whether a non-comma line is actually aligned to 8-char fields."""
    if not raw_line or "," in raw_line[:80]:
        return False

    import re

    starts = [m.start() for m in re.finditer(r"\S+", raw_line)]
    if not starts:
        return False

    # Card name must start in column 1; data fields in columns 9,17,25,...
    expected = list(range(0, 8 * len(starts), 8))
    return starts == expected


def _is_loose_whitespace_card(card):
    """Detect a human/solver-emitted whitespace card that is not 8-column fixed format."""
    raw = getattr(card, "raw", ()) or ()
    if not raw:
        return False

    first = str(raw[0])
    if "," in first[:80]:
        return False

    stripped = first.strip()
    if not stripped:
        return False

    first_token = stripped.split()[0].upper().rstrip("*")
    if first_token != "MAT1":
        return False

    return not _is_standard_small_field_line(first)


def _compact_mat1_from_free(card):
    """Try the explicit non-standard free-field form MAT1,MID,E,NU,RHO.

    Official free-field syntax must preserve a blank G as a double comma,
    e.g. MAT1,MID,E,,NU,RHO.  When only five fields are present, however,
    some generated decks omit that empty field.  We accept that form only
    when the compact interpretation is physically valid and the official
    five-field interpretation is materially inconsistent.
    """
    fields = list(getattr(card, "fields", ()) or ())
    raw = getattr(card, "raw", ()) or ()
    if len(fields) != 5 or not raw or "," not in str(raw[0])[:80]:
        return None
    if _text(F(fields, 0)).upper().rstrip("*") != "MAT1":
        return None

    mid = _i(F(fields, 1), None)
    E = _f(F(fields, 2), None)
    official_G = _f(F(fields, 3), None)
    official_NU = _f(F(fields, 4), None)
    if mid is None or E is None or official_G is None or official_NU is None:
        return None

    compact_nu = official_G
    compact_rho = official_NU
    if E <= 0.0 or not (-1.0 < compact_nu < 0.5) or compact_rho <= 0.0:
        return None

    expected_E = 2.0 * (1.0 + official_NU) * official_G
    rel = abs(E - expected_E) / max(abs(E), 1.0e-30)
    if rel <= 0.01:
        # Do not reinterpret a syntactically valid, self-consistent MAT1.
        return None

    return mid, E, compact_nu, compact_rho


def _compact_mat1_from_raw(card):
    """Try the explicit non-standard compact form MAT1 MID E NU RHO.

    This is only used for a card whose original line is not comma free-field
    and is not aligned to the official 8-character fixed-field format.
    It therefore cannot silently reinterpret a valid Nastran fixed-field card.
    """
    raw = getattr(card, "raw", ()) or ()
    if not raw:
        return None

    first = str(raw[0])
    tokens = first.strip().split()
    if len(tokens) < 5:
        return None

    if tokens[0].upper().rstrip("*") != "MAT1":
        return None

    if not _is_loose_whitespace_card(card):
        return None

    # Compact compatibility syntax:
    #     MAT1 MID E NU RHO
    # or the same values separated by arbitrary whitespace.
    mid = _i(tokens[1], None)
    E = _f(tokens[2], None)
    NU = _f(tokens[3], None)
    RHO = _f(tokens[4], None)

    if mid is None or E is None or NU is None or RHO is None:
        return None

    if E <= 0.0 or not (-1.0 < NU < 0.5) or RHO <= 0.0:
        return None

    return mid, E, NU, RHO


def _parse_mat1(card):
    """Parse MAT1 using the official field positions plus explicit compatibility.

    Official Nastran/OptiStruct-style MAT1 data fields are:
        MID, E, G, NU, RHO, A, TREF, GE, ST, SC, SS, ...

    The parser supports three source representations:
      1. comma/free-field, with blank fields preserved;
      2. standard 8-character small field or 16-character large field;
      3. an explicitly non-standard whitespace-compact form
         ``MAT1 MID E NU RHO`` used by some generated decks/fixtures.

    The third form is never inferred from a valid fixed-field layout.  The
    downstream Radioss /MAT/LAW1 target requires a real initial density, so
    a genuinely absent RHO remains an error instead of being silently set to 0.
    """
    fields = list(card.fields)

    if not fields:
        raise ValueError(f"MAT1 at line {card.line}: empty card")

    if _text(F(fields, 0)).upper().rstrip("*") != "MAT1":
        raise ValueError(
            f"MAT1 parser received unexpected card {F(fields, 0)!r} "
            f"at line {card.line}"
        )

    # ============================================================
    # A. Explicit non-standard whitespace-compact form.
    #    This is the only safe way to interpret the user's 5-token
    #    line as E,NU,RHO when the blank G field was omitted.
    # ============================================================
    compact = _compact_mat1_from_raw(card)
    if compact is None:
        compact = _compact_mat1_from_free(card)
    if compact is not None:
        mid, E, NU, RHO = compact
        G = E / (2.0 * (1.0 + NU))
        alpha = _f(F(fields, 5), 0.0) or 0.0
        return Material(
            mid=mid,
            E=float(E),
            nu=float(NU),
            rho=float(RHO),
            G=float(G),
            alpha=float(alpha),
        )

    # ============================================================
    # B. Official field positions.
    # ============================================================
    mid = _required_int(F(fields, 1), "MAT1 MID", card.line)

    E = _f(F(fields, 2), None)
    G = _f(F(fields, 3), None)
    NU = _f(F(fields, 4), None)
    RHO = _f(F(fields, 5), None)

    # Autodesk Nastran explicitly permits E or G to be blank and computes the
    # missing elastic constant from the other two; do not reject a legal MAT1
    # merely because E itself is blank.
    if E is None and G is None:
        raise ValueError(
            f"MAT1 {mid}: both E and G are missing at BDF line {card.line}; "
            "at least one elastic modulus is required."
        )

    if E is not None and E < 0.0:
        raise ValueError(f"MAT1 {mid}: E must be >= 0, got {E}")
    if G is not None and G < 0.0:
        raise ValueError(f"MAT1 {mid}: G must be >= 0, got {G}")

    # ============================================================
    # C. Density is source-sensitive, but the target is not.
    #    Some Nastran variants/documentation allow a blank RHO, while
    #    Radioss LAW1 explicitly needs initial density.  Therefore do
    #    not use a generic Nastran default of 0 here.
    # ============================================================
    if RHO is None:
        raise ValueError(
            f"MAT1 {mid}: RHO is missing at BDF line {card.line}. "
            f"Parsed official fields={fields!r}. "
            "Nastran documentation permits RHO to be blank in some variants, "
            "but this BDF->Radioss /MAT/LAW1 conversion requires a positive "
            "initial density. If this card intended E,NU,RHO with G omitted, "
            "write the non-ambiguous form MAT1,MID,E,,NU,RHO or provide the "
            "same values in standard fixed/large-field columns."
        )

    if RHO <= 0.0:
        raise ValueError(f"MAT1 {mid}: RHO must be > 0 for /MAT/LAW1, got {RHO}")

    # ============================================================
    # D. Complete E/G/NU according to E = 2(1+NU)G.
    # ============================================================
    if NU is None:
        if E is None or G is None or G <= 0.0:
            raise ValueError(
                f"MAT1 {mid}: NU is missing and cannot be derived from "
                f"E={E!r}, G={G!r}."
            )
        NU = E / (2.0 * G) - 1.0

    if not (-1.0 < NU < 0.5):
        raise ValueError(
            f"MAT1 {mid}: NU={NU} is outside the physically supported range (-1,0.5)"
        )

    if E is None:
        if G is None:
            raise ValueError(f"MAT1 {mid}: insufficient E/G/NU data to compute E")
        E = 2.0 * (1.0 + NU) * G

    if G is None:
        G = E / (2.0 * (1.0 + NU))

    if E < 0.0 or G < 0.0:
        raise ValueError(
            f"MAT1 {mid}: computed non-physical modulus E={E}, G={G}"
        )

    # When all three are explicitly supplied, Nastran-style processors may
    # issue a warning for inconsistency rather than recomputing them.  This
    # converter refuses to guess because changing a source modulus changes
    # the physical model.
    if all(value is not None for value in (
        _f(F(fields, 2), None),
        _f(F(fields, 3), None),
        _f(F(fields, 4), None),
    )):
        source_E = _f(F(fields, 2), None)
        source_G = _f(F(fields, 3), None)
        source_NU = _f(F(fields, 4), None)
        expected_E = 2.0 * (1.0 + source_NU) * source_G
        scale = max(abs(source_E), 1.0e-30)
        rel = abs(source_E - expected_E) / scale
        if rel > 0.01:
            raise ValueError(
                f"MAT1 {mid}: inconsistent E/G/NU at BDF line {card.line}: "
                f"E={source_E}, G={source_G}, NU={source_NU}; "
                f"E_expected={expected_E}, relative_error={rel:.6g}. "
                "Nastran documentation treats this as implausible data; "
                "the converter will not silently alter the material."
            )

    alpha = _f(F(fields, 6), 0.0) or 0.0

    return Material(
        mid=mid,
        E=float(E),
        nu=float(NU),
        rho=float(RHO),
        G=float(G),
        alpha=float(alpha),
    )

def _parse_spc(card):
    f = card.fields

    sid = _required_int(
        F(f, 1),
        "SPC SID",
        card.line,
    )

    gid = _required_int(
        F(f, 2),
        "SPC GRID",
        card.line,
    )

    comp = _text(
        F(f, 3)
    )

    if not comp:
        raise ValueError(
            f"SPC at line {card.line}: "
            "component field is empty"
        )

    if not comp.isdigit():
        raise ValueError(
            f"SPC at line {card.line}: "
            f"invalid component {comp!r}"
        )

    if any(
        ch not in "123456"
        for ch in comp
    ):
        raise ValueError(
            f"SPC at line {card.line}: "
            f"invalid component {comp!r}"
        )

    value = _f(
        F(f, 4),
        0.0,
    )

    return (
        sid,
        gid,
        comp,
        value or 0.0,
    )




def read_model(
    path,
    encoding="gb18030",
):
    model = Model()

    control_lines, executive = (
        read_case_control(
            path,
            encoding,
        )
    )

    model.control_lines = control_lines
    model.executive = executive

    for card in iter_cards(
        path,
        encoding,
    ):
        name = card.name
        f = card.fields

        model.card_counts[name] = (
            model.card_counts.get(
                name,
                0,
            ) + 1
        )

        # ========================================================
        # GRID
        # ========================================================

        if name == "GRID":

            nid = _required_int(
                F(f, 1),
                "GRID ID",
                card.line,
            )

            cp = _i(
                F(f, 2),
                0,
            )

            x = _f(
                F(f, 3),
                0.0,
            )

            y = _f(
                F(f, 4),
                0.0,
            )

            z = _f(
                F(f, 5),
                0.0,
            )

            cd = _i(
                F(f, 6),
                0,
            )

            model.nodes[nid] = Node(
                nid,
                (
                    float(x or 0.0),
                    float(y or 0.0),
                    float(z or 0.0),
                ),
                int(cp or 0),
                int(cd or 0),
            )

            continue

        # ========================================================
        # SOLID ELEMENTS
        # ========================================================

        if name in {
            "CTETRA",
            "CPENTA",
            "CHEXA",
        }:

            eid = _required_int(
                F(f, 1),
                f"{name} EID",
                card.line,
            )

            pid = _required_int(
                F(f, 2),
                f"{name} PID",
                card.line,
            )

            nodes = _parse_solid_connectivity(
                card
            )

            model.elements[eid] = Element(
                eid,
                name,
                pid,
                nodes,
                len(nodes),
            )

            continue

        # ========================================================
        # PSOLID
        # ========================================================

        if name == "PSOLID":

            pid = _required_int(
                F(f, 1),
                "PSOLID PID",
                card.line,
            )

            mid = _required_int(
                F(f, 2),
                "PSOLID MID",
                card.line,
            )

            model.props[pid] = Property(
                pid,
                mid,
                list(f),
            )

            continue

        # ========================================================
        # MAT1
        # ========================================================

        if name == "MAT1":

            material = _parse_mat1(
                card
            )

            model.mats[
                material.mid
            ] = material

            continue

        # ========================================================
        # MATS1
        # ========================================================

        if name == "MATS1":

            mid = _required_int(
                F(f, 1),
                "MATS1 MID",
                card.line,
            )

            model.plastics[mid] = Plastic(
                mid,
                _i(F(f, 2), 0) or 0,
                _text(F(f, 3)),
                _f(F(f, 4), 0.0) or 0.0,
                _i(F(f, 5), 1) or 1,
                _i(F(f, 6), 1) or 1,
                _f(F(f, 7), 0.0) or 0.0,
            )

            continue

        # ========================================================
        # CONM2
        # ========================================================

        if name == "CONM2":

            eid = _required_int(
                F(f, 1),
                "CONM2 EID",
                card.line,
            )

            nid = _required_int(
                F(f, 2),
                "CONM2 GRID",
                card.line,
            )

            cid = _i(
                F(f, 3),
                0,
            ) or 0

            mass = _f(
                F(f, 4),
                0.0,
            ) or 0.0

            xyz = (
                _f(F(f, 5), 0.0) or 0.0,
                _f(F(f, 6), 0.0) or 0.0,
                _f(F(f, 7), 0.0) or 0.0,
            )

            model.masses[eid] = Mass(
                eid,
                nid,
                mass,
                xyz,
                cid,
            )

            continue

        # ========================================================
        # RBE2
        # ========================================================

        if name == "RBE2":

            rid = _required_int(
                F(f, 1),
                "RBE2 ID",
                card.line,
            )

            ref = _required_int(
                F(f, 2),
                "RBE2 independent node",
                card.line,
            )

            comp = (
                _text(F(f, 3))
                or "123456"
            )

            dependents = []

            for value in f[4:]:

                node_id = _i(
                    value,
                    None,
                )

                if node_id is not None:
                    if node_id > 0:
                        dependents.append(
                            node_id
                        )

            model.rbe2[rid] = RBE2(
                rid,
                ref,
                comp,
                dependents,
            )

            continue

        # ========================================================
        # RBE3
        # ========================================================

        if name == "RBE3":

            materialized = _parse_rbe3(
                card,
                model,
            )

            model.rbe3[
                materialized.rid
            ] = materialized

            continue

        # ========================================================
        # SPC
        # ========================================================

        if name == "SPC":

            sid, gid, comp, value = (
                _parse_spc(
                    card
                )
            )

            model.spcs.append(
                SPC(
                    sid,
                    gid,
                    comp,
                    value,
                )
            )

            continue

        # ========================================================
        # SPC1
        # ========================================================

        if name == "SPC1":

            sid = _required_int(
                F(f, 1),
                "SPC1 SID",
                card.line,
            )

            comp = _text(
                F(f, 2)
            )

            for value in f[3:]:

                gid = _i(
                    value,
                    None,
                )

                if gid is None:
                    continue

                model.spcs.append(
                    SPC(
                        sid,
                        gid,
                        comp,
                        0.0,
                    )
                )

            continue

        # ========================================================
        # TIC
        # ========================================================

        if name == "TIC":

            sid = _required_int(
                F(f, 1),
                "TIC SID",
                card.line,
            )

            nid = _required_int(
                F(f, 2),
                "TIC GRID",
                card.line,
            )

            dof = _required_int(
                F(f, 3),
                "TIC DOF",
                card.line,
            )

            displacement = _f(
                F(f, 4),
                None,
            )

            velocity = _f(
                F(f, 5),
                None,
            )

            model.tics.append(
                TIC(
                    sid,
                    nid,
                    dof,
                    displacement,
                    velocity,
                )
            )

            continue

        # ========================================================
        # GRAV
        # ========================================================

        if name == "GRAV":

            sid = _required_int(
                F(f, 1),
                "GRAV SID",
                card.line,
            )

            cid = _required_int(
                F(f, 2),
                "GRAV CID",
                card.line,
            )

            scale = _f(
                F(f, 3),
                1.0,
            ) or 1.0

            vector = (
                _f(F(f, 4), 0.0) or 0.0,
                _f(F(f, 5), 0.0) or 0.0,
                _f(F(f, 6), 0.0) or 0.0,
            )

            model.gravs[sid] = Gravity(
                sid,
                cid,
                scale,
                vector,
            )

            continue

        # ========================================================
        # TSTEP1
        # ========================================================

        if name == "TSTEP1":

            sid = _required_int(
                F(f, 1),
                "TSTEP1 ID",
                card.line,
            )

            dt = _required_float(
                F(f, 2),
                "TSTEP1 time",
                card.line,
            )

            n = _required_int(
                F(f, 3),
                "TSTEP1 increments",
                card.line,
            )

            method = _text(
                F(f, 4)
            )

            model.tsteps[sid] = TStep(
                sid,
                dt,
                n,
                method,
            )

            continue

        # ========================================================
        # BCRPARA
        # ========================================================

        if name == "BCRPARA":

            sid = _required_int(
                F(f, 1),
                "BCRPARA ID",
                card.line,
            )

            offset = _f(
                F(f, 3),
                0.0,
            ) or 0.0

            formulation = (
                _text(F(f, 4))
                or "FLEX"
            )

            model.bcrpara[sid] = BCRPara(
                sid,
                offset,
                formulation,
            )

            continue

        # ========================================================
        # BCTSET
        # ========================================================

        if name == "BCTSET":

            sid = _required_int(
                F(f, 1),
                "BCTSET ID",
                card.line,
            )

            source = _required_int(
                F(f, 2),
                "BCTSET source",
                card.line,
            )

            target = _required_int(
                F(f, 3),
                "BCTSET target",
                card.line,
            )

            friction = _f(
                F(f, 4),
                0.0,
            ) or 0.0

            mind = _i(
                F(f, 5),
                0,
            ) or 0

            maxd = _f(
                F(f, 6),
                0.0,
            ) or 0.0

            form = _i(
                F(f, 7),
                1,
            ) or 1

            model.bctsets[sid] = BCTSet(
                sid,
                source,
                target,
                friction,
                mind,
                maxd,
                form,
            )

            continue

        # ========================================================
        # BGSET
        # ========================================================

        if name == "BGSET":

            sid = _required_int(
                F(f, 1),
                "BGSET ID",
                card.line,
            )

            source = _required_int(
                F(f, 2),
                "BGSET source",
                card.line,
            )

            target = _required_int(
                F(f, 3),
                "BGSET target",
                card.line,
            )

            scale = _f(
                F(f, 4),
                1.0,
            ) or 1.0

            clearance = _f(
                F(f, 5),
                0.0,
            ) or 0.0

            model.bgsets[sid] = BGSet(
                sid,
                source,
                target,
                scale,
                clearance,
            )

            continue

        # ========================================================
        # BCTADD
        # ========================================================

        if name == "BCTADD":

            sid = _required_int(
                F(f, 1),
                "BCTADD ID",
                card.line,
            )

            model.bctadds[sid] = [
                node_id
                for value in f[2:]
                for node_id in [
                    _i(value, None)
                ]
                if node_id is not None
            ]

            continue

        # ========================================================
        # BGADD
        # ========================================================

        if name == "BGADD":

            sid = _required_int(
                F(f, 1),
                "BGADD ID",
                card.line,
            )

            model.bgadds[sid] = [
                node_id
                for value in f[2:]
                for node_id in [
                    _i(value, None)
                ]
                if node_id is not None
            ]

            continue

        # ========================================================
        # BSURFS
        # ========================================================

        if name == "BSURFS":

            sid = _required_int(
                F(f, 1),
                "BSURFS ID",
                card.line,
            )

            values = []

            for value in f[5:]:

                number = _i(
                    value,
                    None,
                )

                if number is not None:
                    values.append(
                        number
                    )

            faces = []

            for start in range(
                0,
                len(values),
                4,
            ):

                group = values[
                    start:start + 4
                ]

                if len(group) == 4:
                    faces.append(
                        tuple(group)
                    )

            model.bsurfs[sid] = BsurfS(
                sid,
                faces,
            )

            continue

        # ========================================================
        # Explicitly supported audit-only cards
        # ========================================================

        if name in {
            "SPCADD",
            "PARAM",
            "BCSET",
            "IC",
            "LOAD",
            "TSTEP",
            "SUBCASE",
            "TEMPD",
            "TEMP",
            "NLCNTLG",
            "NLCNTL2",
        }:
            continue

        # ========================================================
        # Unknown card
        # ========================================================

        if name not in SUPPORTED:

            model.diagnostics.append(
                {
                    "severity":
                        "UNSUPPORTED_CARD",
                    "card":
                        name,
                    "line":
                        card.line,
                    "fields":
                        list(f[:20]),
                }
            )

    # ------------------------------------------------------------
    # Normalize Case Control.
    # ------------------------------------------------------------

    for line in model.control_lines:

        text = line.strip()

        if "=" in text:

            key, value = (
                text.split(
                    "=",
                    1,
                )
            )

            model.case[
                key.strip().upper()
            ] = value.strip()

        elif text.upper().startswith(
            "SUBCASE"
        ):

            parts = text.split()

            if len(parts) >= 2:
                model.case[
                    "_SUBCASE"
                ] = parts[1]

    return model