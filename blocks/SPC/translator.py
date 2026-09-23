from __future__ import annotations

from collections import defaultdict

from bdf2rad.core.plugin_helpers import emit, rb, RadBlock


def _component_to_trarot(component: str) -> str:
    """
    Convert Nastran SPC component digits to Radioss Trarot.

    Nastran:
        1 2 3 4 5 6

    Radioss:
        TX TY TZ RX RY RZ
        represented by six 0/1 flags.
    """

    text = str(component).strip()

    if not text:
        raise ValueError(
            "SPC component is empty."
        )

    if not text.isdigit():
        raise ValueError(
            f"Invalid Nastran SPC component: {component!r}"
        )

    if any(
        ch not in "123456"
        for ch in text
    ):
        raise ValueError(
            f"Invalid Nastran SPC component: {component!r}"
        )

    flags = ["0"] * 6

    for ch in text:
        flags[int(ch) - 1] = "1"

    return "".join(flags)


def _fmt10(value) -> str:
    return f"{value:>10}"


def _fmt_node_rows(node_ids):
    rows = []

    for start in range(
        0,
        len(node_ids),
        10,
    ):
        chunk = node_ids[
            start:start + 10
        ]

        rows.append(
            "".join(
                f"{int(nid):>10d}"
                for nid in chunk
            )
        )

    return rows


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
    Nastran SPC -> two independent Radioss Blocks:

        /GRNOD/NODE/grnd_ID/unit_ID
        /BCS/bcs_ID

    IMPORTANT:
    These are two separate Blocks and must never be
    embedded into a single RadBlock.
    """

    sid = _resolve_spc_sid(model)

    grouped = defaultdict(list)

    for record in model.spcs:

        if int(record.sid) != sid:
            continue

        trarot = _component_to_trarot(
            record.comp
        )

        grouped[
            trarot
        ].append(
            int(record.nid)
        )

    blocks = []
    audit = []

    next_group_id = 400000

    for trarot, node_ids in sorted(
        grouped.items(),
        key=lambda x: x[0],
    ):

        node_ids = sorted(
            set(node_ids)
        )

        if not node_ids:
            continue

        # --------------------------------------------------------
        # Validate all source nodes.
        # --------------------------------------------------------
        missing = [
            nid
            for nid in node_ids
            if nid not in model.nodes
        ]

        if missing:
            preview = ", ".join(
                str(x)
                for x in missing[:20]
            )

            raise ValueError(
                f"SPC SID={sid}, Trarot={trarot}: "
                f"undefined node IDs: {preview}"
            )

        grnd_id = next_group_id
        bcs_id = next_group_id

        # ========================================================
        # BLOCK 1
        # /GRNOD/NODE/<grnd_ID>/<unit_ID>
        # ========================================================

        group_lines = [
            f"/GRNOD/NODE/{grnd_id}/0",
            f"SPC_{trarot}",
        ]

        group_lines.extend(
            _fmt_node_rows(
                node_ids
            )
        )

        blocks.append(
            RadBlock(
                keyword=(
                    f"/GRNOD/NODE/"
                    f"{grnd_id}/0"
                ),
                lines=group_lines,
                order=50,
                plugin=plugin.name,
                source_cards=("SPC",),
            )
        )

        # ========================================================
        # BLOCK 2
        # /BCS/<bcs_ID>
        # ========================================================

        bcs_data = (
            _fmt10(trarot)
            + _fmt10(0)
            + _fmt10(grnd_id)
        )

        bcs_lines = [
            f"/BCS/{bcs_id}",
            f"SPC_{trarot}",
            bcs_data,
        ]

        blocks.append(
            RadBlock(
                keyword=f"/BCS/{bcs_id}",
                lines=bcs_lines,
                order=51,
                plugin=plugin.name,
                source_cards=("SPC",),
            )
        )

        audit.append(
            {
                "card": "SPC",
                "sid": sid,
                "status": "translated",
                "target": [
                    (
                        f"/GRNOD/NODE/"
                        f"{grnd_id}/0"
                    ),
                    f"/BCS/{bcs_id}",
                ],
                "Trarot": trarot,
                "Skew_ID": 0,
                "grnd_ID": grnd_id,
                "node_count": len(node_ids),
            }
        )

        next_group_id += 1

    return (
        blocks,
        audit,
    )