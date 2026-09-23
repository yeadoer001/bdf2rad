from __future__ import annotations

from collections import defaultdict

from bdf2rad.core.plugin_helpers import emit, rb, dof6


def _group_spc_records(model):
    """
    Group SPC records by the resulting Radioss Trarot code.

    Nastran:
        SPC SID
        node
        component

    Radioss:
        /GRNOD/NODE/<grnd_ID>/<unit_ID>
        +
        /BCS/<bcs_ID>
    """

    # ------------------------------------------------------------
    # Get the SPC set referenced by Case Control.
    # ------------------------------------------------------------
    raw_sid = (
        model.case.get("SPC", "0")
        or "0"
    )

    try:
        sid = int(raw_sid)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid SPC Case Control ID: {raw_sid!r}"
        ) from exc

    groups = defaultdict(list)

    for record in model.spcs:
        if record.sid != sid:
            continue

        code = dof6(record.comp)

        if not code:
            raise ValueError(
                f"SPC record for node {record.nid} "
                f"produced an empty Trarot code."
            )

        groups[code].append(
            int(record.nid)
        )

    return sid, groups


def _format_trarot(code: str) -> str:
    """
    Radioss 2023 /BCS:
        Trarot is a 6-Boolean code and is right justified
        in a 10-character field.

    Example:
        111111 -> '    111111'
    """
    code = str(code).strip()

    if len(code) != 6:
        raise ValueError(
            f"Invalid Radioss Trarot code: {code!r}"
        )

    if any(ch not in "01" for ch in code):
        raise ValueError(
            f"Trarot must contain only 0/1: {code!r}"
        )

    return f"{code:>10s}"


def _format_int(value: int) -> str:
    """
    Radioss integer field width used by the provided
    fixed-format examples.
    """
    return f"{int(value):>10d}"


def translate(model, ctx, plugin):
    """
    Translate Nastran SPC -> Radioss:

        SPC
          ↓
        /GRNOD/NODE
          +
        /BCS

    One Radioss node group and one BCS block are created
    for each unique Trarot pattern.
    """

    spc_sid, groups = _group_spc_records(
        model
    )

    blocks = []
    audit = []

    # Keep generated IDs in a dedicated range so they do not
    # collide with ordinary BDF/Radioss IDs.
    next_group_id = 400000

    for trarot, node_ids in sorted(
        groups.items(),
        key=lambda item: item[0],
    ):
        unique_nodes = sorted(
            set(node_ids)
        )

        if not unique_nodes:
            continue

        group_id = next_group_id
        bcs_id = group_id

        # --------------------------------------------------------
        # Validate node IDs against the BDF node table.
        # Do not ever emit an undefined node.
        # --------------------------------------------------------
        missing = [
            nid
            for nid in unique_nodes
            if nid not in model.nodes
        ]

        if missing:
            preview = ", ".join(
                str(x)
                for x in missing[:20]
            )

            raise ValueError(
                f"SPC SID={spc_sid}, Trarot={trarot}: "
                f"{len(missing)} undefined node(s): "
                f"{preview}"
            )

        # --------------------------------------------------------
        # /GRNOD/NODE/<grnd_ID>/<unit_ID>
        #
        # Official OpenRadioss 2023 format:
        #   /GRNOD/NODE/grnd_ID/unit_ID
        #   title
        #   node list, up to 10 per line
        # --------------------------------------------------------
        node_rows = "\n".join(
            "".join(
                f"{nid:>10d}"
                for nid in unique_nodes[i:i + 10]
            )
            for i in range(
                0,
                len(unique_nodes),
                10,
            )
        )

        # --------------------------------------------------------
        # Fixed-width BCS data line:
        #
        # Trarot      Skew_ID      grnd_ID
        #
        # Each field is 10 characters.
        # --------------------------------------------------------
        bcs_data_line = (
            _format_trarot(trarot)
            + _format_int(0)
            + _format_int(group_id)
        )

        block_lines = emit(
            plugin,
            {
                "GRID": group_id,
                "CODE": trarot,
                "GROUP_TITLE": f"SPC_{trarot}",
                "NODE_ROWS": node_rows,
                "NODE": "",
                "ID": bcs_id,
                "TITLE": f"SPC_{trarot}",
                "TRAROT": _format_trarot(trarot),
                "SKEW": _format_int(0),
                "GRND": _format_int(group_id),
                "BCS_DATA": bcs_data_line,
            }
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
                "sid": spc_sid,
                "status": "translated",
                "target": [
                    f"/GRNOD/NODE/{group_id}/0",
                    f"/BCS/{bcs_id}",
                ],
                "node_group": group_id,
                "bcs_id": bcs_id,
                "Trarot": trarot,
                "Skew_ID": 0,
                "count": len(unique_nodes),
            }
        )

        next_group_id += 1

    return blocks, audit