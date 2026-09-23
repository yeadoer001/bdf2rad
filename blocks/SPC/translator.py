from __future__ import annotations

from collections import defaultdict

from bdf2rad.core.types import RadBlock


def _component_to_trarot(component: str) -> str:
    """
    Nastran SPC component digits:

        1 = TX
        2 = TY
        3 = TZ
        4 = RX
        5 = RY
        6 = RZ

    Convert to Radioss Trarot:
        TX TY TZ RX RY RZ
        as six 0/1 flags.
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
        char not in "123456"
        for char in text
    ):
        raise ValueError(
            f"Invalid Nastran SPC component: {component!r}"
        )

    flags = ["0"] * 6

    for char in text:
        flags[int(char) - 1] = "1"

    return "".join(flags)


def _format_node_rows(
    node_ids: list[int],
) -> list[str]:
    """
    OpenRadioss /GRNOD/NODE:
    maximum 10 node IDs per line.
    """

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
                f"{int(node_id):>10d}"
                for node_id in chunk
            )
        )

    return rows


def _format_bcs_data(
    trarot: str,
    skew_id: int,
    grnd_id: int,
) -> str:
    """
    /BCS data:

        Trarot  Skew_ID  grnd_ID

    Each value is written in a 10-character field.
    """

    return (
        f"{trarot:>10s}"
        f"{int(skew_id):>10d}"
        f"{int(grnd_id):>10d}"
    )


def _resolve_spc_sid(model) -> int:
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
            f"Invalid SPC Case Control ID: {raw_sid!r}"
        ) from exc


def translate(model, ctx, plugin):
    """
    Translate one Nastran SPC set into two independent
    OpenRadioss Blocks:

        /GRNOD/NODE/grnd_ID/unit_ID
        /BCS/bcs_ID

    IMPORTANT:
    RadBlock.keyword contains the keyword itself.
    RadBlock.lines contains ONLY the lines AFTER that keyword.
    """

    sid = _resolve_spc_sid(
        model
    )

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
        key=lambda item: item[0],
    ):

        node_ids = sorted(
            set(node_ids)
        )

        if not node_ids:
            continue

        # --------------------------------------------------------
        # Validate source node IDs.
        # --------------------------------------------------------
        missing_nodes = [
            nid
            for nid in node_ids
            if nid not in model.nodes
        ]

        if missing_nodes:
            preview = ", ".join(
                str(nid)
                for nid in missing_nodes[:20]
            )

            raise ValueError(
                f"SPC SID={sid}, "
                f"Trarot={trarot}: "
                f"undefined node IDs: {preview}"
            )

        grnd_id = next_group_id
        bcs_id = grnd_id

        # ========================================================
        # /GRNOD/NODE/<grnd_ID>/<unit_ID>
        #
        # IMPORTANT:
        # The keyword itself is NOT duplicated inside lines.
        # ========================================================

        grnod_keyword = (
            f"/GRNOD/NODE/"
            f"{grnd_id}/0"
        )

        grnod_lines = [
            f"SPC_{trarot}"
        ]

        grnod_lines.extend(
            _format_node_rows(
                node_ids
            )
        )

        blocks.append(
            RadBlock(
                keyword=grnod_keyword,
                lines=grnod_lines,
                order=50,
                plugin=plugin.name,
                source_cards=("SPC",),
            )
        )

        # ========================================================
        # /BCS/<bcs_ID>
        #
        # Again: keyword is stored separately.
        # ========================================================

        bcs_keyword = (
            f"/BCS/{bcs_id}"
        )

        bcs_lines = [
            f"SPC_{trarot}",
            _format_bcs_data(
                trarot,
                0,
                grnd_id,
            ),
        ]

        blocks.append(
            RadBlock(
                keyword=bcs_keyword,
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
                    grnod_keyword,
                    bcs_keyword,
                ],
                "Trarot": trarot,
                "Skew_ID": 0,
                "grnd_ID": grnd_id,
                "node_count": len(node_ids),
            }
        )

        next_group_id += 1

    return blocks, audit