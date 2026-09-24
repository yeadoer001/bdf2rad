from __future__ import annotations

from collections import defaultdict

from bdf2rad.core.plugin_helpers import (
    emit,
    rb,
)


def _fmt10(value: int) -> str:
    return f"{int(value):>10d}"


def _tetra4_row(
    eid: int,
    nodes: list[int],
) -> str:
    """
    Official conversion path:

        Nastran CTETRA10
              ->
        first-order tetrahedron
              ->
        Radioss /TETRA4

    /TETRA4 requires:
        tetra_ID + 4 node IDs
    """

    if len(nodes) != 10:
        raise ValueError(
            f"CTETRA10 element {eid} requires exactly "
            f"10 source nodes, got {len(nodes)}"
        )

    # ------------------------------------------------------------
    # Official first-order conversion:
    #
    # CTETRA10:
    #   node 1..4 = corner nodes
    #   node 5..10 = midside nodes
    #
    # TETRA4:
    #   only the four corner nodes remain.
    # ------------------------------------------------------------
    corner_nodes = nodes[:4]

    return (
        _fmt10(eid)
        + "".join(
            _fmt10(node_id)
            for node_id in corner_nodes
        )
    )


def translate(
    model,
    ctx,
    plugin,
):
    """
    Translate Nastran CTETRA10 -> OpenRadioss /TETRA4.

    The mapping follows the official Nastran-to-Radioss
    conversion table:

        CTETRA10
            ->
        first-order downgrade
            ->
        /TETRA4
    """

    groups = defaultdict(list)

    # ------------------------------------------------------------
    # Only CTETRA elements with exactly 10 nodes belong here.
    # CTETRA4 is handled by the first-order tetra translator.
    # ------------------------------------------------------------
    for element in model.elements.values():

        if (
            element.typ == "CTETRA"
            and len(element.nodes) == 10
        ):
            groups[
                element.pid
            ].append(
                element
            )

    blocks = []
    audit = []

    for pid, elements in sorted(
        groups.items()
    ):

        # --------------------------------------------------------
        # IMPORTANT:
        # PART uses the SAME family name: TETRA4.
        # This prevents the element from referencing a Part
        # generated under the TETRA10 family.
        # --------------------------------------------------------
        part = (
            ctx.metadata
            .get(
                "part_map",
                {},
            )
            .get(
                (
                    pid,
                    "TETRA4",
                ),
                pid,
            )
        )

        rows = []

        for element in sorted(
            elements,
            key=lambda item: item.eid,
        ):

            # ----------------------------------------------------
            # Validate all 10 source node IDs.
            # ----------------------------------------------------
            missing = [
                node_id
                for node_id in element.nodes
                if node_id not in model.nodes
            ]

            if missing:
                preview = ", ".join(
                    str(node_id)
                    for node_id in missing[:20]
                )

                raise ValueError(
                    f"CTETRA10 element {element.eid} "
                    f"references undefined node(s): "
                    f"{preview}"
                )

            rows.append(
                _tetra4_row(
                    element.eid,
                    element.nodes,
                )
            )

        rendered = emit(
            plugin,
            {
                "PART": part,
                "ROWS": "\n".join(rows),
            },
        )

        blocks.append(
            rb(
                plugin,
                f"/TETRA4/{part}",
                rendered,
            )
        )

        audit.append(
            {
                "card": "CTETRA",
                "source_order": 10,
                "status": "translated_first_order",
                "target": (
                    f"/TETRA4/{part}"
                ),
                "count": len(
                    elements
                ),
                "source_pid": pid,
                "source_nodes_per_element": 10,
                "target_nodes_per_element": 4,
                "source_midside_nodes": 6,
                "source_midside_nodes_used": False,
                "mapping_basis": (
                    "CTETRA10 -> "
                    "first-order -> /TETRA4"
                ),
            }
        )

    return (
        blocks,
        audit,
    )