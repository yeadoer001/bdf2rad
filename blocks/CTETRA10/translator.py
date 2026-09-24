from __future__ import annotations

from collections import defaultdict

from bdf2rad.core.plugin_helpers import (
    emit,
    rb,
)


def _fmt10(
    value: int,
) -> str:
    return f"{int(value):>10d}"


def _tetra4_row(
    eid: int,
    nodes: list[int],
) -> str:

    if len(nodes) == 4:

        corners = nodes

    elif len(nodes) == 10:

        # Nastran CTETRA10:
        #
        # 1-4  = corner nodes
        # 5-10 = midside nodes
        #
        # Current target mapping is first-order /TETRA4,
        # therefore retain only the four corner nodes.
        corners = nodes[:4]

    else:

        raise ValueError(
            f"CTETRA element {eid}: "
            f"expected 4 or 10 nodes, "
            f"got {len(nodes)}"
        )

    return (
        _fmt10(eid)
        + "".join(
            _fmt10(node)
            for node in corners
        )
    )


def translate(
    model,
    ctx,
    plugin,
):
    """
    Translate Nastran CTETRA4 and CTETRA10
    to OpenRadioss /TETRA4.

    CTETRA4:
        direct topology mapping.

    CTETRA10:
        first-order downgrade using the four corner nodes.

    This translator does NOT accept:
        node ID 0
        incomplete connectivity
        arbitrary connectivity lengths
    """

    groups = defaultdict(list)

    for element in model.elements.values():

        if element.typ != "CTETRA":
            continue

        if element.order not in {
            4,
            10,
        }:

            raise ValueError(
                f"CTETRA element {element.eid}: "
                f"unsupported source order "
                f"{element.order}; expected 4 or 10"
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

        count4 = 0
        count10 = 0

        for element in sorted(
            elements,
            key=lambda item: item.eid,
        ):

            # ----------------------------------------------------
            # Strict source connectivity validation.
            # ----------------------------------------------------

            if element.order == 4:

                expected = 4

            else:

                expected = 10

            if len(element.nodes) != expected:

                raise ValueError(
                    f"CTETRA element {element.eid}: "
                    f"source order={element.order}, "
                    f"but connectivity contains "
                    f"{len(element.nodes)} nodes"
                )

            invalid = [
                node_id
                for node_id in element.nodes
                if node_id <= 0
                or node_id not in model.nodes
            ]

            if invalid:

                preview = ", ".join(
                    str(x)
                    for x in invalid[:20]
                )

                raise ValueError(
                    f"CTETRA element {element.eid} "
                    f"references invalid/undefined "
                    f"node(s): {preview}"
                )

            rows.append(
                _tetra4_row(
                    element.eid,
                    element.nodes,
                )
            )

            if element.order == 4:
                count4 += 1
            else:
                count10 += 1

        if not rows:
            continue

        rendered = emit(
            plugin,
            {
                "PART": part,
                "ROWS":
                    "\n".join(
                        rows
                    ),
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
                "card":
                    "CTETRA",
                "status":
                    "translated_first_order",
                "target":
                    f"/TETRA4/{part}",
                "source_pid":
                    pid,
                "count":
                    len(elements),
                "ctetra4_count":
                    count4,
                "ctetra10_count":
                    count10,
                "source_orders":
                    sorted(
                        {
                            e.order
                            for e
                            in elements
                        }
                    ),
                "target_nodes_per_element":
                    4,
                "mapping_basis":
                    (
                        "CTETRA4 -> direct /TETRA4; "
                        "CTETRA10 -> first-order "
                        "downgrade -> /TETRA4"
                    ),
            }
        )

    return (
        blocks,
        audit,
    )