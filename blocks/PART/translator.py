from __future__ import annotations

from collections import defaultdict

from bdf2rad.core.plugin_helpers import (
    emit,
    rb,
    fi,
)


def _family(element):
    """
    Determine the target Radioss element family from the
    parsed Nastran element topology.

    Valid source solid orders:

        CHEXA 8 / 20
        CTETRA 4 / 10
        CPENTA 6 / 15

    Current target mappings in this project:

        CHEXA8
            -> /BRICK

        CHEXA20
            -> /BRICK
            (current project performs first-order target mapping)

        CTETRA4
            -> /TETRA4

        CTETRA10
            -> /TETRA4
            (first-order downgrade)

        CPENTA6 / CPENTA15
            -> BRICK family
            (actual element topology conversion is handled
             by the CPENTA translator)
    """

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

    order = int(
        getattr(
            element,
            "order",
            0,
        )
        or 0
    )

    # ============================================================
    # CHEXA
    # ============================================================

    if (
        element_type == "CHEXA"
        and order in {
            8,
            20,
        }
    ):
        return "BRICK"

    # ============================================================
    # CTETRA
    # ============================================================

    if (
        element_type == "CTETRA"
        and order in {
            4,
            10,
        }
    ):
        return "TETRA4"

    # ============================================================
    # CPENTA
    # ============================================================

    if (
        element_type == "CPENTA"
        and order in {
            6,
            15,
        }
    ):
        return "BRICK"

    return "UNSUPPORTED"


def _require_property_and_material(
    model,
    pid,
):
    """
    Validate the complete PSOLID -> MAT1 reference chain.

    Required chain:

        PSOLID PID
            |
            +--> Property exists
            |
            +--> Property.MID exists
                    |
                    +--> MAT1 exists

    Never emit a /PART whose material ID does not exist.
    """

    prop = model.props.get(
        pid
    )

    if prop is None:
        raise ValueError(
            f"PSOLID {pid} is referenced by an element, "
            f"but the PSOLID property does not exist."
        )

    prop_id = int(
        prop.pid
    )

    mat_id = int(
        prop.mid
    )

    if mat_id <= 0:
        raise ValueError(
            f"PSOLID {pid} references invalid "
            f"material ID {mat_id}."
        )

    material = model.mats.get(
        mat_id
    )

    if material is None:
        raise ValueError(
            f"PSOLID {pid} references MAT1 {mat_id}, "
            f"but MAT1 {mat_id} was not successfully "
            f"parsed from the BDF."
        )

    return (
        prop_id,
        mat_id,
    )


def translate(
    model,
    ctx,
    plugin,
):
    """
    Generate Radioss /PART definitions.

    PARTs are grouped by:

        source PSOLID PID
        +
        actual target element family

    Before a PART is emitted, this translator verifies:

        PSOLID exists
        MAT1 exists
        material ID is valid

    This prevents invalid RAD such as:

        /PART/1
        ...
        1 1 0 0

    when /MAT/LAW1/1 was never generated.
    """

    families = defaultdict(list)

    # ------------------------------------------------------------
    # Group source elements by PID and target family.
    # ------------------------------------------------------------

    for element in model.elements.values():

        family = _family(
            element
        )

        if family == "UNSUPPORTED":
            continue

        families[
            (
                int(element.pid),
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
    # Generate PART definitions.
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
        # Preserve the source PID as PART ID when this PID only
        # maps to one target family.
        # --------------------------------------------------------

        if len(pid_families) == 1:

            part_id = pid

        else:

            part_id = next_part_id

            next_part_id += 1

        part_map[
            (
                pid,
                family,
            )
        ] = part_id

        # --------------------------------------------------------
        # Validate PSOLID -> MAT1 before writing PART.
        # --------------------------------------------------------

        prop_id, mat_id = (
            _require_property_and_material(
                model,
                pid,
            )
        )

        values = {
            "ID":
                int(part_id),

            "TITLE":
                (
                    f"BDF_PART_"
                    f"{pid}_"
                    f"{family}"
                ),

            "PROP":
                fi(
                    prop_id
                ),

            "MAT":
                fi(
                    mat_id
                ),

            "SUBSET":
                fi(0),

            "THICK":
                fi(0),
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
                "card":
                    "PSOLID",

                "source_pid":
                    pid,

                "target_family":
                    family,

                "status":
                    "translated",

                "target":
                    f"/PART/{part_id}",

                "property_id":
                    prop_id,

                "material_id":
                    mat_id,

                "element_count":
                    len(elements),
            }
        )

    # ------------------------------------------------------------
    # Expose exact source-PID / target-family mapping to element
    # translators.
    # ------------------------------------------------------------

    ctx.metadata[
        "part_map"
    ] = part_map

    return (
        blocks,
        audit,
    )