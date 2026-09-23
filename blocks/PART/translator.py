from __future__ import annotations

from collections import defaultdict

from bdf2rad.core.plugin_helpers import (
    emit,
    rb,
    fi,
)


def _family(element):
    """
    Resolve the target Radioss element family according to the
    official Nastran-to-Radioss conversion mapping.

    Important:
        CHEXA20 is NOT mapped to /BRIC20 here.

        Official mapping:
            CHEXA20 -> first-order -> /BRICK
    """

    # ------------------------------------------------------------
    # First-order CHEXA
    # ------------------------------------------------------------
    if (
        element.typ == "CHEXA"
        and len(element.nodes) == 8
    ):
        return "BRICK"

    # ------------------------------------------------------------
    # Second-order CHEXA
    #
    # Official Nastran -> Radioss mapping:
    # CHEXA20 -> change to 1st order -> /BRICK
    # ------------------------------------------------------------
    if (
        element.typ == "CHEXA"
        and len(element.nodes) == 20
    ):
        return "BRICK"

    # ------------------------------------------------------------
    # CTETRA10:
    # official conversion also changes to first order.
    # The dedicated CTETRA10 translator is responsible for
    # performing the actual node reduction.
    # ------------------------------------------------------------
    if (
        element.typ == "CTETRA"
        and len(element.nodes) == 10
    ):
        return "TETRA4"

    if (
        element.typ == "CTETRA"
        and len(element.nodes) == 4
    ):
        return "TETRA4"

    # ------------------------------------------------------------
    # CPENTA15:
    # official conversion changes to first order and ultimately
    # follows the /BRICK family route.
    # Dedicated CPENTA translator handles topology.
    # ------------------------------------------------------------
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
    Create Radioss /PART definitions grouped by:

        source PSOLID PID
        +
        target Radioss element family

    This preserves separate parts when one source PID contains
    different target element families.
    """

    families = defaultdict(list)

    # ------------------------------------------------------------
    # Build source-PID / target-family groups.
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
    # Create target PARTs.
    # ------------------------------------------------------------
    for (
        pid,
        family,
    ), elements in sorted(
        families.items()
    ):

        same_pid_families = {
            key
            for key in families
            if key[0] == pid
        }

        # If this PID belongs to only one target family,
        # keep the source PID as the target PART ID.
        if len(same_pid_families) == 1:
            part_id = pid

        else:
            # If one Nastran PID contains elements that need
            # different target families, create distinct Radioss
            # part IDs.
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

        material_id = (
            prop.mid
            if prop is not None
            else 0
        )

        values = {
            "ID": part_id,
            "TITLE": (
                f"BDF_PART_{pid}_{family}"
            ),
            "PROP": fi(pid),
            "MAT": fi(material_id),
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
                "family": family,
                "status": "translated",
                "target": (
                    f"/PART/{part_id}"
                ),
                "element_count": len(
                    elements
                ),
            }
        )

    # ------------------------------------------------------------
    # Make target family map available to element translators.
    # ------------------------------------------------------------
    ctx.metadata[
        "part_map"
    ] = part_map

    return (
        blocks,
        audit,
    )