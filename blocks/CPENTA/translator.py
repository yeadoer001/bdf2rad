from __future__ import annotations

from collections import defaultdict

from bdf2rad.core.plugin_helpers import (
    emit,
    rb,
)


def _fmt10(value: int) -> str:
    return f"{int(value):>10d}"


def _validate_corner_nodes(
    element,
) -> None:
    """
    Validate that the six first-order corner nodes exist
    and are distinct.

    CPENTA15:
        nodes 1-6   = corner nodes
        nodes 7-15  = midside nodes
    """

    if len(element.nodes) != 15:
        raise ValueError(
            f"CPENTA15 element {element.eid} must contain "
            f"exactly 15 nodes, got {len(element.nodes)}"
        )

    corners = [
        int(node_id)
        for node_id in element.nodes[:6]
    ]

    if len(set(corners)) != 6:
        raise ValueError(
            f"CPENTA15 element {element.eid} has duplicate "
            f"corner node IDs: {corners}"
        )


def _degenerate_brick_nodes(
    nodes: list[int],
) -> list[int]:
    """
    Convert first-order pentahedron corner ordering

        P1 P2 P3 P4 P5 P6

    into the 8-node degenerated /BRICK ordering

        P1 P2 P2 P3 P4 P5 P5 P6

    This represents the triangular prism by collapsing
    brick edges (2,3) and (6,7).

    Altair's element-definition documentation describes
    degenerated BRICK elements by repeating node numbers
    to collapse brick corners and form a pentahedron.
    """

    if len(nodes) != 6:
        raise ValueError(
            "A first-order pentahedron must have "
            "exactly 6 corner nodes."
        )

    n1, n2, n3, n4, n5, n6 = (
        int(node_id)
        for node_id in nodes
    )

    return [
        n1,
        n2,
        n2,
        n3,
        n4,
        n5,
        n5,
        n6,
    ]


def _brick_row(
    eid: int,
    nodes: list[int],
) -> str:
    """
    Produce one official /BRICK data row:

        brick_ID
        node_ID1 ... node_ID8
    """

    if len(nodes) != 8:
        raise ValueError(
            f"Degenerated BRICK requires 8 node positions, "
            f"got {len(nodes)}"
        )

    return (
        _fmt10(eid)
        + "".join(
            _fmt10(node_id)
            for node_id in nodes
        )
    )


def translate(
    model,
    ctx,
    plugin,
):
    """
    Translate Nastran CPENTA6 / CPENTA15 into
    OpenRadioss degenerated /BRICK.

    Official conversion route:

        CPENTA6
            -> /BRICK

        CPENTA15
            -> first-order
            -> /BRICK

    Therefore this translator never emits /BRIC20.
    """

    groups = defaultdict(list)

    # ------------------------------------------------------------
    # Select both 6-node and 15-node pentahedra.
    #
    # CPENTA15 is explicitly reduced to first order.
    # CPENTA6 is already first order.
    # ------------------------------------------------------------
    for element in model.elements.values():

        if element.typ != "CPENTA":
            continue

        if len(element.nodes) not in {
            6,
            15,
        }:
            raise ValueError(
                f"Unsupported CPENTA node count for element "
                f"{element.eid}: {len(element.nodes)}"
            )

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
        # PART translator must use exactly the same target family.
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
                    "BRICK",
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
            # Determine source order.
            # ----------------------------------------------------
            source_nodes = [
                int(node_id)
                for node_id in element.nodes
            ]

            if len(source_nodes) == 15:

                # ------------------------------------------------
                # CPENTA15 -> first-order CPENTA6
                # ------------------------------------------------
                _validate_corner_nodes(
                    element
                )

                corner_nodes = (
                    source_nodes[:6]
                )

                source_order = 15

            else:

                # ------------------------------------------------
                # CPENTA6 already first order.
                # ------------------------------------------------
                corner_nodes = (
                    source_nodes[:6]
                )

                if len(
                    set(corner_nodes)
                ) != 6:
                    raise ValueError(
                        f"CPENTA6 element {element.eid} "
                        f"contains duplicate corner nodes: "
                        f"{corner_nodes}"
                    )

                source_order = 6

            # ----------------------------------------------------
            # Verify the six source corner nodes exist.
            # ----------------------------------------------------
            missing = [
                node_id
                for node_id in corner_nodes
                if node_id not in model.nodes
            ]

            if missing:
                preview = ", ".join(
                    str(node_id)
                    for node_id in missing[:20]
                )

                raise ValueError(
                    f"CPENTA element {element.eid} "
                    f"references undefined node(s): "
                    f"{preview}"
                )

            # ----------------------------------------------------
            # First-order penta -> degenerated BRICK.
            # ----------------------------------------------------
            brick_nodes = (
                _degenerate_brick_nodes(
                    corner_nodes
                )
            )

            rows.append(
                _brick_row(
                    element.eid,
                    brick_nodes,
                )
            )

            audit.append(
                {
                    "card": "CPENTA",
                    "id": element.eid,
                    "source_pid": pid,
                    "source_order": source_order,
                    "status": (
                        "translated_first_order_degenerate_brick"
                    ),
                    "target": f"/BRICK/{part}",
                    "source_nodes": len(
                        source_nodes
                    ),
                    "corner_nodes_used": 6,
                    "target_node_positions": 8,
                    "target_nodes": brick_nodes,
                    "midside_nodes_used": (
                        source_order == 15
                    ),
                    "midside_nodes_discarded": (
                        9
                        if source_order == 15
                        else 0
                    ),
                    "mapping_basis": (
                        "Nastran CPENTA15 -> "
                        "first-order -> "
                        "degenerated /BRICK"
                    ),
                }
            )

        rendered = emit(
            plugin,
            {
                "PART": part,
                "ROWS": "\n".join(
                    rows
                ),
            },
        )

        blocks.append(
            rb(
                plugin,
                f"/BRICK/{part}",
                rendered,
            )
        )

    return (
        blocks,
        audit,
    )