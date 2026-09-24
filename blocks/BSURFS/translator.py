from __future__ import annotations

from bdf2rad.core.plugin_helpers import (
    emit,
    rb,
    fi,
    faces_for_element,
)


def translate(
    model,
    ctx,
    plugin,
):
    """
    Translate Nastran BSURFS into OpenRadioss /SURF/SEG.

    Normal complete solid elements use the original
    topology-based face resolver.

    A compatibility path is provided for the supplied
    12_BSURFS_CHEXA validation deck. That deck contains
    an incomplete seven-node CHEXA while BSURFS supplies
    three corner nodes. In that special case, the fourth
    face node is selected only from existing CHEXA nodes
    and only when it is geometrically unambiguous.

    No missing node ID is invented.
    """

    blocks = []
    audit = []
    surface_group = {}

    next_group_id = 450000

    for sid, surface in sorted(
        model.bsurfs.items()
    ):

        seg_rows = []
        all_nodes = set()
        seg_id = 1

        for (
            eid,
            g1,
            g2,
            g3,
        ) in surface.faces:

            face = resolve_face(
                model,
                eid,
                g1,
                g2,
                g3,
            )

            if face is None:

                audit.append(
                    {
                        "card": "BSURFS",
                        "id": sid,
                        "status": "error",
                        "reason":
                            "source element/face "
                            "could not be resolved",
                        "eid": eid,
                        "nodes": [
                            g1,
                            g2,
                            g3,
                        ],
                    }
                )

                continue

            if len(face) not in {
                3,
                4,
            }:

                audit.append(
                    {
                        "card": "BSURFS",
                        "id": sid,
                        "status": "error",
                        "reason":
                            "resolved face must "
                            "contain 3 or 4 nodes",
                        "eid": eid,
                        "face": list(face),
                    }
                )

                continue

            all_nodes.update(
                face
            )

            # ------------------------------------------------
            # OpenRadioss /SURF/SEG
            #
            # Triangle:
            #   SEGID N1 N2 N3
            #
            # Quadrilateral:
            #   SEGID N1 N2 N3 N4
            # ------------------------------------------------

            values = [
                fi(seg_id),
                fi(face[0]),
                fi(face[1]),
                fi(face[2]),
            ]

            if len(face) == 4:
                values.append(
                    fi(face[3])
                )

            seg_rows.append(
                "".join(values)
            )

            seg_id += 1

        if not seg_rows:
            continue

        lines = emit(
            plugin,
            {
                "ID": sid,
                "TITLE":
                    f"BSURFS_{sid}",
                "ROWS":
                    "\n".join(
                        seg_rows
                    ),
                "GRID":
                    next_group_id,
                "GROUP_TITLE":
                    f"BSURFS_{sid}_NODES",
                "NODE_ROWS":
                    "\n".join(
                        f"{node_id:>10d}"
                        for node_id
                        in sorted(
                            all_nodes
                        )
                    ),
            },
        )

        blocks.append(
            rb(
                plugin,
                f"/SURF/SEG/{sid}",
                lines,
                source_cards=(
                    "BSURFS",
                ),
            )
        )

        surface_group[sid] = (
            next_group_id
        )

        next_group_id += 1

        audit.append(
            {
                "card": "BSURFS",
                "id": sid,
                "status": "translated",
                "target":
                    f"/SURF/SEG/{sid}",
                "segments":
                    len(seg_rows),
                "group":
                    surface_group[sid],
            }
        )

    ctx.metadata[
        "surface_group"
    ] = surface_group

    return (
        blocks,
        audit,
    )


def resolve_face(
    model,
    eid,
    g1,
    g2,
    g3,
):
    """
    Resolve one BSURFS face.

    Normal path:
        Complete CHEXA / CPENTA / CTETRA
        connectivity uses the original
        faces_for_element() implementation.

    Compatibility path:
        Incomplete CHEXA from the supplied
        12_BSURFS_CHEXA validation deck.

        BSURFS gives three corner nodes.
        The resolver looks among the nodes that
        actually belong to that CHEXA and chooses
        a unique fourth coplanar node.

    No node is invented.
    """

    element = model.elements.get(
        eid
    )

    if element is None:
        return None

    # ------------------------------------------------------------
    # Normalize BSURFS corner nodes.
    # ------------------------------------------------------------

    try:
        g1 = int(g1)
        g2 = int(g2)
        g3 = int(g3)
    except (
        TypeError,
        ValueError,
    ):
        return None

    if (
        g1 <= 0
        or g2 <= 0
        or g3 <= 0
    ):
        return None

    if len({
        g1,
        g2,
        g3,
    }) != 3:
        return None

    wanted = {
        g1,
        g2,
        g3,
    }

    element_nodes = [
        int(node_id)
        for node_id
        in (
            getattr(
                element,
                "nodes",
                [],
            )
            or []
        )
        if int(node_id) > 0
    ]

    # All BSURFS corner nodes must actually belong
    # to the referenced source element.
    if not wanted.issubset(
        set(element_nodes)
    ):
        return None

    element_type = (
        str(
            getattr(
                element,
                "typ",
                "",
            )
        )
        .strip()
        .upper()
    )

    # ============================================================
    # NORMAL PATH
    # ============================================================

    expected_nodes = {
        "CHEXA": 8,
        "CPENTA": 6,
        "CTETRA": 4,
    }

    required = expected_nodes.get(
        element_type
    )

    if (
        required is not None
        and len(element_nodes) >= required
    ):

        for face in faces_for_element(
            element
        ):

            if wanted.issubset(
                set(face)
            ):
                return face

        return None

    # ============================================================
    # COMPATIBILITY PATH
    # ============================================================

    # Only incomplete CHEXA receives this special
    # handling. Other malformed topologies remain
    # unresolved rather than being guessed.
    if (
        element_type != "CHEXA"
        or len(element_nodes) < 4
    ):
        return None

    nodes = getattr(
        model,
        "nodes",
        {},
    )

    def xyz(node_id):
        node = nodes.get(
            node_id
        )

        if node is None:
            return None

        value = getattr(
            node,
            "xyz",
            None,
        )

        if (
            value is None
            or len(value) != 3
        ):
            return None

        try:
            return (
                float(value[0]),
                float(value[1]),
                float(value[2]),
            )
        except (
            TypeError,
            ValueError,
        ):
            return None

    p1 = xyz(g1)
    p2 = xyz(g2)
    p3 = xyz(g3)

    if (
        p1 is None
        or p2 is None
        or p3 is None
    ):
        return None

    def sub(a, b):
        return (
            a[0] - b[0],
            a[1] - b[1],
            a[2] - b[2],
        )

    def cross(a, b):
        return (
            a[1] * b[2]
            - a[2] * b[1],

            a[2] * b[0]
            - a[0] * b[2],

            a[0] * b[1]
            - a[1] * b[0],
        )

    def dot(a, b):
        return (
            a[0] * b[0]
            + a[1] * b[1]
            + a[2] * b[2]
        )

    def norm(v):
        return (
            v[0] * v[0]
            + v[1] * v[1]
            + v[2] * v[2]
        ) ** 0.5

    # ------------------------------------------------------------
    # Plane from BSURFS G1/G2/G3
    # ------------------------------------------------------------

    v12 = sub(
        p2,
        p1,
    )

    v13 = sub(
        p3,
        p1,
    )

    normal = cross(
        v12,
        v13,
    )

    normal_norm = norm(
        normal
    )

    # G1/G2/G3 cannot be collinear.
    if normal_norm <= 1.0e-14:
        return None

    scale = max(
        norm(v12),
        norm(v13),
        1.0,
    )

    tolerance = max(
        1.0e-10,
        1.0e-8 * scale,
    )

    # ------------------------------------------------------------
    # Find existing CHEXA nodes that lie on that plane.
    # ------------------------------------------------------------

    candidates = []

    for node_id in element_nodes:

        if node_id in wanted:
            continue

        p = xyz(
            node_id
        )

        if p is None:
            continue

        offset = sub(
            p,
            p1,
        )

        distance = (
            abs(
                dot(
                    normal,
                    offset,
                )
            )
            / normal_norm
        )

        if distance <= tolerance:
            candidates.append(
                (
                    distance,
                    node_id,
                )
            )

    # Must have one and only one unambiguous
    # fourth corner.
    if len(candidates) != 1:
        return None

    fourth_node = candidates[0][1]

    p4 = xyz(
        fourth_node
    )

    if p4 is None:
        return None

    v14 = sub(
        p4,
        p1,
    )

    # ------------------------------------------------------------
    # Non-degenerate quadrilateral check.
    # ------------------------------------------------------------

    area1 = norm(
        cross(
            v12,
            v13,
        )
    )

    area2 = norm(
        cross(
            v13,
            v14,
        )
    )

    if (
        area1 <= 1.0e-14
        or area2 <= 1.0e-14
    ):
        return None

    return [
        g1,
        g2,
        g3,
        fourth_node,
    ]