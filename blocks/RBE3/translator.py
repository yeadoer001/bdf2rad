from __future__ import annotations

from bdf2rad.core.plugin_helpers import (
    emit,
    rb,
    fi,
    fs,
    dof6,
)


def _fmt10_int(value: int) -> str:
    return f"{int(value):>10d}"


def _fmt_trarot(component: str) -> str:
    """
    Build one official OpenRadioss Trarot field.

    The six Boolean values are contained in ONE logical Trarot
    field. Their positions are:

        [1] [2] [3] [4] [5] [6]
         TX  TY  TZ  RX  RY  RZ

    The Radioss fixed-format representation reserves ten
    character positions for this field:

        positions 1-3 : blank
        positions 4-6 : TX TY TZ
        position 7     : blank
        positions 8-10: RX RY RZ

    Example:

        123456
        -> "   111 111"
    """

    code = dof6(
        component
    )

    if len(code) != 6:
        raise ValueError(
            f"Invalid Trarot source component "
            f"{component!r}: {code!r}"
        )

    return (
        "   "
        + code[:3]
        + " "
        + code[3:]
    )


def _rbe3_header_line(
    reference_node: int,
    reference_component: str,
    n_set: int,
    i_modif: int,
) -> str:
    """Build the 2023-format /RBE3 first data line.

    The repository currently emits a /BEGIN 2023 deck, so the
    /RBE3 header must contain only:

        Node_IDr | Trarot_ref | N_set | I_modif

    Iform is intentionally omitted.
    """

    result = (
        _fmt10_int(reference_node)
        + _fmt_trarot(reference_component)
        + _fmt10_int(n_set)
        + _fmt10_int(i_modif)
    )

    if len(result) != 40:
        raise RuntimeError(
            "Invalid /RBE3 header line length: "
            f"expected 40 characters, got {len(result)}"
        )

    return result

def _rbe3_set_line(
    weight: float,
    independent_component: str,
    skew_id: int,
    group_id: int,
) -> str:
    """
    Official /RBE3 weighting-set line:

        WT_i | Trarot_M_i | skew_ID_i | grnd_ID_i

    WT_i is a real field.
    Trarot_M_i is one fixed-width Trarot field.
    """

    result = (
        fs(
            weight
        )
        + _fmt_trarot(
            independent_component
        )
        + _fmt10_int(
            skew_id
        )
        + _fmt10_int(
            group_id
        )
    )

    if len(result) != 50:
        raise RuntimeError(
            "Invalid /RBE3 set line length: "
            f"expected 50 characters, got {len(result)}"
        )

    return result


def _node_rows(
    node_ids: list[int],
) -> list[str]:
    """
    /GRNOD/NODE permits ten node IDs per line.
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


def translate(
    model,
    ctx,
    plugin,
):
    """
    Translate Nastran RBE3 into two separate OpenRadioss
    Starter Blocks:

        /GRNOD/NODE/<grnd_ID>/0

        /RBE3/<rbe3_ID>

    Source model structure:

        RBE3.rid
        RBE3.ref
        RBE3.ref_comp
        RBE3.weight
        RBE3.ind_comp
        RBE3.independent

    This repository currently represents one weighting set per
    RBE3 record, which matches the current validation example.

    Official OpenRadioss RBE3 structure:

        /RBE3/id
        title
        Node_IDr Trarot_ref N_set I_modif

        WT_i Trarot_M_i skew_ID_i grnd_ID_i
    """

    blocks = []
    audit = []

    # ------------------------------------------------------------
    # Allocate the dependent-node group IDs used by RBE3.
    # ------------------------------------------------------------
    next_group_id = ctx.ids.get(
        "next:RBE3_GRNOD",
        430000,
    )

    for rid, record in sorted(
        model.rbe3.items()
    ):

        rbe3_id = int(
            record.rid
        )

        reference_node = int(
            record.ref
        )

        reference_component = str(
            record.ref_comp
        ).strip()

        weight = float(
            record.weight
        )

        independent_component = str(
            record.ind_comp
        ).strip()

        independent_nodes = [
            int(node_id)
            for node_id in record.independent
        ]

        # --------------------------------------------------------
        # Validate reference node.
        # --------------------------------------------------------
        if reference_node not in (
            model.nodes
        ):
            raise ValueError(
                f"RBE3 {rbe3_id}: "
                f"undefined reference node "
                f"{reference_node}"
            )

        # --------------------------------------------------------
        # Validate independent nodes.
        # --------------------------------------------------------
        if not independent_nodes:
            raise ValueError(
                f"RBE3 {rbe3_id}: "
                "independent node group is empty"
            )

        independent_nodes = list(
            dict.fromkeys(
                independent_nodes
            )
        )

        missing = [
            node_id
            for node_id in independent_nodes
            if node_id not in model.nodes
        ]

        if missing:
            preview = ", ".join(
                str(node_id)
                for node_id in missing[:20]
            )

            raise ValueError(
                f"RBE3 {rbe3_id}: "
                f"undefined independent node(s): "
                f"{preview}"
            )

        # --------------------------------------------------------
        # Reference node must not be an independent node of
        # its own interpolation set.
        # --------------------------------------------------------
        if reference_node in (
            independent_nodes
        ):
            raise ValueError(
                f"RBE3 {rbe3_id}: "
                f"reference node {reference_node} "
                "is also listed as an independent node"
            )

        # --------------------------------------------------------
        # Allocate node group.
        # --------------------------------------------------------
        group_id = int(
            next_group_id
        )

        next_group_id += 1

        ctx.ids[
            "next:RBE3_GRNOD"
        ] = next_group_id

        # --------------------------------------------------------
        # Current verified translator uses global coordinates.
        # Therefore:
        #
        #     skew_ID = 0
        #
        # --------------------------------------------------------
        skew_id = 0

        # --------------------------------------------------------
        # Existing repository defaults for the 2023 RAD input format:
        #
        # N_set   = 1
        # I_modif = 1
        #
        # Iform is intentionally omitted because this project
        # currently emits a /BEGIN 2023 deck.
        # --------------------------------------------------------
        n_set = 1
        i_modif = 1

        # ========================================================
        # BLOCK 1:
        # /GRNOD/NODE/<group_id>/0
        # ========================================================

        grnod_keyword = (
            f"/GRNOD/NODE/"
            f"{group_id}/0"
        )

        grnod_lines = [
            f"RBE3_{rbe3_id}_INDEPENDENT"
        ]

        grnod_lines.extend(
            _node_rows(
                independent_nodes
            )
        )

        blocks.append(
            rb(
                plugin,
                grnod_keyword,
                grnod_lines,
                order=60,
                source_cards=("RBE3",),
            )
        )

        # ========================================================
        # BLOCK 2:
        # /RBE3/<rbe3_id>
        # ========================================================

        rbe3_keyword = (
            f"/RBE3/{rbe3_id}"
        )

        header_line = (
            _rbe3_header_line(
                reference_node=(
                    reference_node
                ),
                reference_component=(
                    reference_component
                ),
                n_set=n_set,
                i_modif=i_modif,
            )
        )

        set_line = (
            _rbe3_set_line(
                weight=weight,
                independent_component=(
                    independent_component
                ),
                skew_id=skew_id,
                group_id=group_id,
            )
        )

        # IMPORTANT:
        # The template supplies:
        #
        #   RBE3_<ID>
        #   DATA
        #
        # The keyword itself is supplied by rb().
        lines = emit(
            plugin,
            {
                "ID": rbe3_id,
                "TITLE": (
                    f"RBE3_{rbe3_id}"
                ),
                "DATA": (
                    header_line
                    + "\n"
                    + set_line
                ),
            },
        )

        blocks.append(
            rb(
                plugin,
                rbe3_keyword,
                lines,
                order=61,
                source_cards=("RBE3",),
            )
        )

        audit.append(
            {
                "card": "RBE3",
                "id": rbe3_id,
                "status": "translated_single_set",
                "target": [
                    grnod_keyword,
                    rbe3_keyword,
                ],
                "reference_node": (
                    reference_node
                ),
                "reference_dof": dof6(
                    reference_component
                ),
                "weighting_set_count": 1,
                "independent_dof": dof6(
                    independent_component
                ),
                "independent_group": (
                    group_id
                ),
                "skew_ID": skew_id,
                "I_modif": i_modif,
                "independent_nodes": (
                    independent_nodes
                ),
            }
        )

    return (
        blocks,
        audit,
    )