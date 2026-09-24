from __future__ import annotations

from bdf2rad.core.plugin_helpers import (
    rb,
    dof6,
)


def _fmt10_int(
    value: int,
) -> str:
    """
    OpenRadioss integer field.
    """
    return f"{int(value):>10d}"


def _fmt10_text(
    value: str,
) -> str:
    """
    OpenRadioss ten-character text field.
    """
    return f"{str(value):>10s}"


def _node_rows(
    node_ids: list[int],
) -> list[str]:
    """
    /GRNOD/NODE:
    up to ten node IDs per line.
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
                _fmt10_int(
                    node_id
                )
                for node_id in chunk
            )
        )

    return rows


def _rbe2_data(
    independent_node: int,
    component: str,
    skew_id: int,
    grnd_id: int,
    iflag: int,
) -> str:
    """
    Official OpenRadioss /RBE2 data layout:

        node_ID
        Trarot
        Skew_ID
        grnd_ID
        Iflag
    """

    trarot = dof6(
        component
    )

    return (
        _fmt10_int(
            independent_node
        )
        + _fmt10_text(
            trarot
        )
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


def translate(
    model,
    ctx,
    plugin,
):
    """
    Nastran RBE2 -> OpenRadioss.

    Source repository model:

        RBE2.rid
        RBE2.independent
        RBE2.cm
        RBE2.dependent

    Target:

        /GRNOD/NODE/<grnd_ID>/<unit_ID>

        /RBE2/<rbe2_ID>

    Official /RBE2 format:

        node_ID
        Trarot
        Skew_ID
        grnd_ID
        Iflag

    The dependent nodes must be written into an independent
    /GRNOD/NODE Block, and /RBE2 references that group through
    grnd_ID.
    """

    blocks = []
    audit = []

    # ------------------------------------------------------------
    # Allocate from a dedicated namespace.
    # ------------------------------------------------------------
    next_group_id = ctx.ids.get(
        "next:RBE2_GRNOD",
        420000,
    )

    # ------------------------------------------------------------
    # Process RBE2 records using the ACTUAL repository data model.
    # ------------------------------------------------------------
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

        # --------------------------------------------------------
        # Validate RBE2 identity.
        # --------------------------------------------------------
        if rbe2_id <= 0:
            raise ValueError(
                f"RBE2 ID must be positive, "
                f"got {rbe2_id}"
            )

        # --------------------------------------------------------
        # Validate independent node.
        # --------------------------------------------------------
        if independent_node <= 0:
            raise ValueError(
                f"RBE2 {rbe2_id}: "
                f"invalid independent node "
                f"{independent_node}"
            )

        if independent_node not in (
            model.nodes
        ):
            raise ValueError(
                f"RBE2 {rbe2_id}: "
                f"undefined independent node "
                f"{independent_node}"
            )

        # --------------------------------------------------------
        # Validate dependent node list.
        # --------------------------------------------------------
        if not dependent_nodes:
            raise ValueError(
                f"RBE2 {rbe2_id}: "
                f"dependent node list is empty"
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

        # --------------------------------------------------------
        # Remove duplicate dependent nodes while preserving order.
        # --------------------------------------------------------
        dependent_nodes = list(
            dict.fromkeys(
                dependent_nodes
            )
        )

        # --------------------------------------------------------
        # Independent node cannot simultaneously be dependent.
        # --------------------------------------------------------
        if independent_node in (
            dependent_nodes
        ):
            raise ValueError(
                f"RBE2 {rbe2_id}: "
                f"independent node "
                f"{independent_node} is also a dependent node"
            )

        # --------------------------------------------------------
        # Nastran CM -> six-character Radioss Trarot.
        # --------------------------------------------------------
        trarot = dof6(
            component
        )

        if len(trarot) != 6:
            raise ValueError(
                f"RBE2 {rbe2_id}: "
                f"invalid Trarot generated from "
                f"component {component!r}: "
                f"{trarot!r}"
            )

        # --------------------------------------------------------
        # Allocate /GRNOD/NODE group.
        # --------------------------------------------------------
        grnd_id = int(
            next_group_id
        )

        next_group_id += 1

        # Persist allocator.
        ctx.ids[
            "next:RBE2_GRNOD"
        ] = next_group_id

        # --------------------------------------------------------
        # Nastran RBE2 in the current verified translator only
        # supports the global coordinate system.
        # Therefore:
        #
        #     Skew_ID = 0
        #
        # --------------------------------------------------------
        skew_id = 0

        # --------------------------------------------------------
        # Official default rigid-body formulation:
        #
        #     Iflag = 0
        # --------------------------------------------------------
        iflag = 0

        # ========================================================
        # BLOCK 1:
        #
        # /GRNOD/NODE/<grnd_ID>/<unit_ID>
        #
        # Unit ID 0 = repository/global system.
        # ========================================================

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

        # ========================================================
        # BLOCK 2:
        #
        # /RBE2/<rbe2_ID>
        # ========================================================

        rbe2_keyword = (
            f"/RBE2/{rbe2_id}"
        )

        rbe2_lines = [
            f"RBE2_{rbe2_id}",
            _rbe2_data(
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
                "Trarot": trarot,
                "Skew_ID": skew_id,
                "grnd_ID": grnd_id,
                "Iflag": iflag,
            }
        )

    return (
        blocks,
        audit,
    )