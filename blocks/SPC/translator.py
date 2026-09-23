from __future__ import annotations

from collections import defaultdict

from bdf2rad.core.plugin_helpers import emit, rb


def _nastran_component_to_trarot(component):
    """
    Convert Nastran SPC component string to Radioss Trarot.

    Nastran:
        1=X
        2=Y
        3=Z
        4=RX
        5=RY
        6=RZ

    Radioss:
        TX TY TZ RX RY RZ
        represented by six Boolean values.
    """

    text = str(component).strip()

    if not text:
        raise ValueError(
            "SPC component is empty."
        )

    if not text.isdigit():
        raise ValueError(
            f"Invalid Nastran SPC component: "
            f"{component!r}"
        )

    allowed = set("123456")

    if any(ch not in allowed for ch in text):
        raise ValueError(
            f"Invalid Nastran SPC component: "
            f"{component!r}"
        )

    flags = ["0"] * 6

    for ch in text:
        flags[int(ch) - 1] = "1"

    return "".join(flags)


def _format_trarot(trarot):
    """
    Official Radioss /BCS format:
    the six Trarot Boolean values occupy the first
    10-character field and are right-justified.
    """
    value = str(trarot).strip()

    if len(value) != 6:
        raise ValueError(
            f"Invalid Trarot value: {value!r}"
        )

    if any(ch not in "01" for ch in value):
        raise ValueError(
            f"Invalid Trarot value: {value!r}"
        )

    return f"{value:>10}"


def _format_int(value):
    """
    Radioss integer field.
    """
    return f"{int(value):>10d}"


def _format_bcs_data(
    trarot,
    skew_id,
    grnd_id,
):
    """
    Build the complete /BCS data row.

    /BCS:
        Trarot    Skew_ID    grnd_ID

    Each is represented as a 10-character field.
    """
    return (
        _format_trarot(trarot)
        + _format_int(skew_id)
        + _format_int(grnd_id)
    )


def _resolve_spc_sid(model):
    raw_sid = (
        model.case.get(
            "SPC",
            "0",
        )
        or "0"
    )

    try:
        return int(raw_sid)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid SPC Case Control ID: "
            f"{raw_sid!r}"
        ) from exc


def translate(model, ctx, plugin):
    """
    Translate Nastran SPC into:

        /GRNOD/NODE/<grnd_ID>/<unit_ID>
        /BCS/<bcs_ID>
    """

    sid = _resolve_spc_sid(model)

    grouped = defaultdict(list)

    for record in model.spcs:
        if int(record.sid) != sid:
            continue

        trarot = _nastran_component_to_trarot(
            record.comp
        )

        grouped[trarot].append(
            int(record.nid)
        )

    blocks = []
    audit = []

    next_group_id = 400000

    for trarot, node_ids in sorted(
        grouped.items()
    ):
        node_ids = sorted(
            set(node_ids)
        )

        if not node_ids:
            continue

        # --------------------------------------------------------
        # Verify every node exists.
        # --------------------------------------------------------
        missing = [
            nid
            for nid in node_ids
            if nid not in model.nodes
        ]

        if missing:
            sample = ", ".join(
                str(nid)
                for nid in missing[:20]
            )

            raise ValueError(
                f"SPC SID={sid}, Trarot={trarot}: "
                f"{len(missing)} undefined node(s): "
                f"{sample}"
            )

        group_id = next_group_id
        bcs_id = group_id

        # --------------------------------------------------------
        # /GRNOD/NODE
        #
        # Ten node IDs per line.
        # --------------------------------------------------------
        node_rows = "\n".join(
            "".join(
                f"{nid:>10d}"
                for nid in node_ids[
                    start:start + 10
                ]
            )
            for start in range(
                0,
                len(node_ids),
                10,
            )
        )

        # --------------------------------------------------------
        # /BCS data row
        # --------------------------------------------------------
        bcs_data = _format_bcs_data(
            trarot=trarot,
            skew_id=0,
            grnd_id=group_id,
        )

        substitutions = {
            "GRID": group_id,
            "CODE": trarot,
            "NODE_ROWS": node_rows,
            "ID": bcs_id,
            "BCS_DATA": bcs_data,
        }

        block_lines = emit(
            plugin,
            substitutions,
        )

        blocks.append(
            rb(
                plugin,
                f"/BCS/{bcs_id}",
                block_lines,
                source_cards=("SPC",),
            )
        )

        audit.append(
            {
                "card": "SPC",
                "sid": sid,
                "status": "translated",
                "target": [
                    f"/GRNOD/NODE/{group_id}/0",
                    f"/BCS/{bcs_id}",
                ],
                "Trarot": trarot,
                "Skew_ID": 0,
                "grnd_ID": group_id,
                "count": len(node_ids),
            }
        )

        next_group_id += 1

    return blocks, audit