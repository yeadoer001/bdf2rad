from __future__ import annotations

from bdf2rad.core.plugin_helpers import (
    rb,
    dof6,
)


def _fmt10_int(value: int) -> str:
    return f"{int(value):>10d}"


def _fmt_trarot(
    component: str,
) -> str:
    """
    OpenRadioss /RBE2 Trarot_ref field.

    The Trarot_ref value occupies one 10-character field.

    Official internal positions:

        1-3 : blank
        4-6 : TX TY TZ
        7   : blank
        8-10: RX RY RZ

    Example:

        123456 -> "   111 111"
    """

    code = dof6(
        component
    )

    if len(code) != 6:
        raise ValueError(
            f"Invalid Trarot_ref code generated from "
            f"RBE2 component {component!r}: "
            f"{code!r}"
        )

    return (
        f"   {code[:3]} "
        f"{code[3:]}"
    )


def _rbe2_data_line(
    independent_node: int,
    component: str,
    skew_id: int,
    grnd_id: int,
    iflag: int,
) -> str:
    """
    Official /RBE2 top-level field order:

        node_ID
        Trarot_ref
        Skew_ID
        grnd_ID
        Iflag
    """

    trarot = _fmt_trarot(
        component
    )

    result = (
        _fmt10_int(
            independent_node
        )
        + trarot
        + _fmt10_int(
            skew_id
        )
        + _fmt10_int(
            grnd_id
        )
        + _fmt10_int(
            iflag
        )
    )

    if len(result) != 50:
        raise RuntimeError(
            "Invalid /RBE2 data line length: "
            f"expected 50 characters, got {len(result)}"
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


def translate(
    model,
    ctx,
    plugin,
):
    """
    Nastran RBE2 ->

        /GRNOD/NODE/<grnd_ID>/0
        /RBE2/<rbe2_ID>
    """

    blocks = []
    audit = []

    next_group_id = ctx.ids.get(
        "next:RBE2_GRNOD",
        420000,
    )

    for rid, record in sorted(
        model.rbe2.items()
    ):

        rbe2_id = int(
            record.rid
        )

        independent_node = int(
            record.independent
        )

        component = str(
            record.cm
        ).strip()

        dependent_nodes = [
            int(node_id)
            for node_id in record.dependent
        ]

        if independent_node not in (
            model.nodes
        ):
            raise ValueError(
                f"RBE2 {rbe2_id}: "
                f"undefined independent node "
                f"{independent_node}"
            )

        if not dependent_nodes:
            raise ValueError(
                f"RBE2 {rbe2_id}: "
                "dependent node list is empty"
            )

        missing = [
            node_id
            for node_id in dependent_nodes
            if node_id not in model.nodes
        ]

        if missing:
            preview = ", ".join(
                str(node_id)
                for node_id in missing[:20]
            )

            raise ValueError(
                f"RBE2 {rbe2_id}: "
                f"undefined dependent node(s): "
                f"{preview}"
            )

        dependent_nodes = list(
            dict.fromkeys(
                dependent_nodes
            )
        )

        if independent_node in (
            dependent_nodes
        ):
            raise ValueError(
                f"RBE2 {rbe2_id}: "
                f"independent node "
                f"{independent_node} is also listed "
                "as a dependent node"
            )

        grnd_id = int(
            next_group_id
        )

        next_group_id += 1

        ctx.ids[
            "next:RBE2_GRNOD"
        ] = next_group_id

        skew_id = 0
        iflag = 0

        # --------------------------------------------------------
        # /GRNOD/NODE
        # --------------------------------------------------------

        grnod_keyword = (
            f"/GRNOD/NODE/"
            f"{grnd_id}/0"
        )

        grnod_lines = [
            f"RBE2_{rbe2_id}_DEPENDENT"
        ]

        grnod_lines.extend(
            _node_rows(
                dependent_nodes
            )
        )

        blocks.append(
            rb(
                plugin,
                grnod_keyword,
                grnod_lines,
                order=59,
                source_cards=("RBE2",),
            )
        )

        # --------------------------------------------------------
        # /RBE2
        # --------------------------------------------------------

        rbe2_keyword = (
            f"/RBE2/{rbe2_id}"
        )

        rbe2_lines = [
            f"RBE2_{rbe2_id}",
            _rbe2_data_line(
                independent_node=(
                    independent_node
                ),
                component=component,
                skew_id=skew_id,
                grnd_id=grnd_id,
                iflag=iflag,
            ),
        ]

        blocks.append(
            rb(
                plugin,
                rbe2_keyword,
                rbe2_lines,
                order=60,
                source_cards=("RBE2",),
            )
        )

        trarot = dof6(
            component
        )

        audit.append(
            {
                "card": "RBE2",
                "id": rbe2_id,
                "status": "translated",
                "target": [
                    grnod_keyword,
                    rbe2_keyword,
                ],
                "independent_node": (
                    independent_node
                ),
                "dependent_nodes": (
                    dependent_nodes
                ),
                "source_component": (
                    component
                ),
                "Trarot_ref": trarot,
                "Trarot_ref_field": (
                    _fmt_trarot(
                        component
                    )
                ),
                "Skew_ID": skew_id,
                "grnd_ID": grnd_id,
                "Iflag": iflag,
            }
        )

    return (
        blocks,
        audit,
    )