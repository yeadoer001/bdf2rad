from __future__ import annotations

from collections import defaultdict

from bdf2rad.core.plugin_helpers import (
    rb,
    dof6,
)


def _fmt10_int(value: int) -> str:
    return f"{int(value):>10d}"


def _fmt_trarot(component: str) -> str:
    """
    OpenRadioss /BCS Trarot field.

    The Trarot variable occupies one 10-character field.
    The six Boolean codes are located at the official positions:

        1 2 3 [TX TY TZ] 7 [RX RY RZ]

    Therefore:

        123456 -> "   111 111"

    NOT:

        "    111111"
    """

    code = dof6(component)

    if len(code) != 6:
        raise ValueError(
            f"Invalid Trarot code generated from "
            f"SPC component {component!r}: {code!r}"
        )

    # Official ten-character Trarot field:
    #
    # 1-3 : blank
    # 4-6 : TX TY TZ
    # 7   : blank
    # 8-10: RX RY RZ
    return (
        f"   {code[:3]} "
        f"{code[3:]}"
    )


def _bcs_data_line(
    component: str,
    skew_id: int,
    grnd_id: int,
) -> str:
    """
    Official /BCS top-level fields:

        Trarot | Skew_ID | grnd_ID
    """

    trarot = _fmt_trarot(
        component
    )

    result = (
        trarot
        + _fmt10_int(skew_id)
        + _fmt10_int(grnd_id)
    )

    if len(result) != 30:
        raise RuntimeError(
            "Invalid /BCS data line length: "
            f"expected 30 characters, got {len(result)}"
        )

    return result


def _node_rows(
    node_ids: list[int],
) -> list[str]:
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
                _fmt10_int(
                    node_id
                )
                for node_id in chunk
            )
        )

    return rows


def _resolve_spc_sid(
    model,
) -> int:
    raw_sid = (
        model.case.get(
            "SPC",
            "0",
        )
        or "0"
    )

    try:
        return int(
            raw_sid
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            f"Invalid SPC Case Control ID: "
            f"{raw_sid!r}"
        ) from exc


def translate(
    model,
    ctx,
    plugin,
):
    """
    Nastran SPC ->

        /GRNOD/NODE/<grnd_ID>/0
        /BCS/<bcs_ID>
    """

    sid = _resolve_spc_sid(
        model
    )

    grouped = defaultdict(list)

    for record in model.spcs:

        if int(
            record.sid
        ) != sid:
            continue

        component = str(
            record.comp
        ).strip()

        grouped[
            component
        ].append(
            int(
                record.nid
            )
        )

    blocks = []
    audit = []

    next_group_id = ctx.ids.get(
        "next:SPC_GRNOD",
        400000,
    )

    for (
        component,
        node_ids,
    ) in sorted(
        grouped.items()
    ):

        node_ids = sorted(
            set(node_ids)
        )

        if not node_ids:
            continue

        missing = [
            node_id
            for node_id in node_ids
            if node_id not in model.nodes
        ]

        if missing:
            preview = ", ".join(
                str(node_id)
                for node_id in missing[:20]
            )

            raise ValueError(
                f"SPC SID={sid}, "
                f"component={component}: "
                f"undefined node ID(s): "
                f"{preview}"
            )

        grnd_id = int(
            next_group_id
        )

        next_group_id += 1

        ctx.ids[
            "next:SPC_GRNOD"
        ] = next_group_id

        skew_id = 0

        # --------------------------------------------------------
        # /GRNOD/NODE
        # --------------------------------------------------------

        grnod_keyword = (
            f"/GRNOD/NODE/"
            f"{grnd_id}/0"
        )

        grnod_lines = [
            f"SPC_{component}"
        ]

        grnod_lines.extend(
            _node_rows(
                node_ids
            )
        )

        blocks.append(
            rb(
                plugin,
                grnod_keyword,
                grnod_lines,
                order=50,
                source_cards=("SPC",),
            )
        )

        # --------------------------------------------------------
        # /BCS
        # --------------------------------------------------------

        bcs_keyword = (
            f"/BCS/{grnd_id}"
        )

        bcs_lines = [
            f"SPC_{component}",
            _bcs_data_line(
                component=component,
                skew_id=skew_id,
                grnd_id=grnd_id,
            ),
        ]

        blocks.append(
            rb(
                plugin,
                bcs_keyword,
                bcs_lines,
                order=51,
                source_cards=("SPC",),
            )
        )

        trarot = dof6(
            component
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
                "component": component,
                "Trarot": trarot,
                "Trarot_field": (
                    _fmt_trarot(
                        component
                    )
                ),
                "Skew_ID": skew_id,
                "grnd_ID": grnd_id,
                "node_count": len(
                    node_ids
                ),
            }
        )

    return (
        blocks,
        audit,
    )