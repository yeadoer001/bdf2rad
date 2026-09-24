from __future__ import annotations

from collections import defaultdict

from bdf2rad.core.plugin_helpers import (
    emit,
    rb,
    fi,
)


def _family(element):
    """
    Resolve the target Radioss element family according to
    the official Nastran -> Radioss conversion mapping.

    Important mappings:

        CHEXA8
            -> /BRICK

        CHEXA20
            -> first order
            -> /BRICK

        CTETRA4
            -> /TETRA4

        CTETRA10
            -> first order
            -> /TETRA4

        CPENTA6 / CPENTA15
            -> first order / degenerated brick route
    """

    # ============================================================
    # HEXA
    # ============================================================

    if (
        element.typ == "CHEXA"
        and len(element.nodes) == 8
    ):
        return "BRICK"

    if (
        element.typ == "CHEXA"
        and len(element.nodes) == 20
    ):
        return "BRICK"

    # ============================================================
    # TETRA
    # ============================================================

    if (
        element.typ == "CTETRA"
        and len(element.nodes) == 4
    ):
        return "TETRA4"

    if (
        element.typ == "CTETRA"
        and len(element.nodes) == 10
    ):
        return "TETRA4"

    # ============================================================
    # PENTA
    # ============================================================

    if (
        element.typ == "CPENTA"
        and len(element.nodes) >= 6
    ):
        return "BRICK"

    return "UNSUPPORTED"


def translate(
    model,
    ctx,
    plugin,
):
    """
    Generate /PART definitions grouped by:

        source PID
        +
        actual target Radioss family

    The family name here MUST exactly match the name queried
    by each element translator.
    """

    families = defaultdict(list)

    # ------------------------------------------------------------
    # Group elements by source PID + target family.
    # ------------------------------------------------------------
    for element in model.elements.values():

        family = _family(
            element
        )

        if family == "UNSUPPORTED":
            continue

        families[
            (
                element.pid,
                family,
            )
        ].append(
            element
        )

    part_map = {}

    blocks = []
    audit = []

    next_part_id = 100000

    # ------------------------------------------------------------
    # Generate PARTs.
    # ------------------------------------------------------------
    for (
        pid,
        family,
    ), elements in sorted(
        families.items()
    ):

        pid_families = {
            key
            for key in families
            if key[0] == pid
        }

        # --------------------------------------------------------
        # If one PID maps to exactly one target family, preserve
        # the original PID as the Radioss PART ID.
        # --------------------------------------------------------
        if len(pid_families) == 1:

            part_id = pid

        else:

            # ----------------------------------------------------
            # Same source PSOLID PID used by several target
            # element families: split into independent Radioss
            # PART IDs.
            # ----------------------------------------------------
            part_id = next_part_id
            next_part_id += 1

        part_map[
            (
                pid,
                family,
            )
        ] = part_id

        prop = model.props.get(
            pid
        )

        if prop is None:
            prop_id = 0
            mat_id = 0

        else:
            prop_id = int(
                prop.pid
            )

            mat_id = int(
                prop.mid
            )

        values = {
            "ID": part_id,
            "TITLE": (
                f"BDF_PART_"
                f"{pid}_"
                f"{family}"
            ),
            "PROP": fi(
                prop_id
            ),
            "MAT": fi(
                mat_id
            ),
            "SUBSET": fi(0),
            "THICK": fi(0),
        }

        rendered = emit(
            plugin,
            values,
        )

        blocks.append(
            rb(
                plugin,
                f"/PART/{part_id}",
                rendered,
                order=35,
            )
        )

        audit.append(
            {
                "card": "PSOLID",
                "source_pid": pid,
                "target_family": family,
                "status": "translated",
                "target": (
                    f"/PART/{part_id}"
                ),
                "property_id": prop_id,
                "material_id": mat_id,
                "element_count": len(
                    elements
                ),
            }
        )

    # ------------------------------------------------------------
    # Make the exact mapping available to element translators.
    # ------------------------------------------------------------
    ctx.metadata[
        "part_map"
    ] = part_map

    return (
        blocks,
        audit,
    )