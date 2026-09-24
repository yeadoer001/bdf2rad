from __future__ import annotations

from collections import defaultdict

from bdf2rad.core.plugin_helpers import (
    rb,
    fs,
    fi,
    bdf_velocity_to_rad_mm_ms,
)


def _case_int(
    model,
    key,
):
    value = model.case.get(
        key
    )

    if value is None:
        return None

    text = str(
        value
    ).strip()

    if not text:
        return None

    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(
            f"Case Control {key}={value!r} "
            "is not an integer"
        ) from exc


def translate(
    model,
    ctx,
    plugin,
):
    """
    Nastran TIC -> Radioss initial velocity.

    Output consists of two independent Starter blocks:

        /GRNOD/NODE/<group_id>/0

        /INIVEL/TRA/<inivel_id>

    No /RUN or Engine content is emitted here.
    TSTEP1 is responsible for Engine time control.
    """

    ic_sid = _case_int(
        model,
        "IC",
    )

    if ic_sid is None:

        return (
            [],
            [
                {
                    "card":
                        "TIC",
                    "status":
                        "not_selected",
                    "reason":
                        "No IC=<SID> Case Control "
                        "reference was found.",
                }
            ],
        )

    grouped = defaultdict(list)

    for record in model.tics:

        if int(record.sid) != ic_sid:
            continue

        if record.nid not in model.nodes:

            raise ValueError(
                f"TIC references undefined "
                f"GRID {record.nid}"
            )

        if record.dof not in {
            1,
            2,
            3,
        }:

            raise ValueError(
                f"TIC {record.sid}: "
                f"unsupported translational DOF "
                f"{record.dof}"
            )

        if record.velocity is None:

            # Current translator only maps
            # initial velocity TIC records.
            continue

        grouped[
            (
                int(record.dof),
                float(record.velocity),
            )
        ].append(
            int(record.nid)
        )

    if not grouped:

        return (
            [],
            [
                {
                    "card":
                        "TIC",
                    "status":
                        "not_translated",
                    "reason":
                        f"No velocity TIC records "
                        f"referenced by IC={ic_sid}",
                }
            ],
        )

    blocks = []
    audit = []

    # ------------------------------------------------------------
    # Avoid reusing IDs already allocated by other translators.
    # ------------------------------------------------------------

    next_group_id = ctx.ids.get(
        "next:TIC_GRNOD",
        410000,
    )

    for (
        dof,
        velocity,
    ), source_nodes in sorted(
        grouped.items()
    ):

        node_ids = sorted(
            set(source_nodes)
        )

        if not node_ids:
            continue

        # --------------------------------------------------------
        # Convert source velocity to current RAD unit system.
        # --------------------------------------------------------

        value = (
            bdf_velocity_to_rad_mm_ms(
                velocity
            )
        )

        vx = (
            value
            if dof == 1
            else 0.0
        )

        vy = (
            value
            if dof == 2
            else 0.0
        )

        vz = (
            value
            if dof == 3
            else 0.0
        )

        group_id = int(
            next_group_id
        )

        inivel_id = int(
            next_group_id
        )

        next_group_id += 1

        ctx.ids[
            "next:TIC_GRNOD"
        ] = next_group_id

        # ========================================================
        # /GRNOD/NODE
        # ========================================================

        grnod_lines = [
            f"IC_VELOCITY_{dof}",
        ]

        # Official group node data:
        # node IDs, 10 per line.
        for start in range(
            0,
            len(node_ids),
            10,
        ):

            chunk = node_ids[
                start:start + 10
            ]

            grnod_lines.append(
                "".join(
                    f"{node_id:>10d}"
                    for node_id in chunk
                )
            )

        blocks.append(
            rb(
                plugin,
                f"/GRNOD/NODE/{group_id}/0",
                grnod_lines,
                order=51,
                source_cards=(
                    "TIC",
                ),
            )
        )

        # ========================================================
        # /INIVEL/TRA
        # ========================================================

        inivel_lines = [
            f"Initial velocity DOF {dof}",
            (
                f"{fs(vx)}"
                f"{fs(vy)}"
                f"{fs(vz)}"
                f"{fi(group_id)}"
                f"{fi(0)}"
            ),
            (
                f"{fs(0.0)}"
                f"{fi(0)}"
            ),
        ]

        blocks.append(
            rb(
                plugin,
                f"/INIVEL/TRA/{inivel_id}",
                inivel_lines,
                order=52,
                source_cards=(
                    "TIC",
                ),
            )
        )

        audit.append(
            {
                "card":
                    "TIC",
                "status":
                    "translated",
                "target": [
                    f"/GRNOD/NODE/{group_id}/0",
                    f"/INIVEL/TRA/{inivel_id}",
                ],
                "IC":
                    ic_sid,
                "DOF":
                    dof,
                "node_group_id":
                    group_id,
                "inivel_id":
                    inivel_id,
                "nodes":
                    node_ids,
                "velocity_source":
                    velocity,
                "velocity_target_mm_ms":
                    value,
            }
        )

    return (
        blocks,
        audit,
    )