from __future__ import annotations

from bdf2rad.core.types import RadBlock
from bdf2rad.core.formatting import bdf_time_to_rad_ms


def translate(model, ctx, plugin):
    """
    Translate Nastran TSTEP1 into Engine metadata.

    This plugin must only run when TSTEP1 is actually present.
    It never invents a default stop time.
    """

    # ------------------------------------------------------------
    # Case Control:
    #
    # TSTEP = 401
    # ------------------------------------------------------------
    raw_tstep_id = (
        model.case.get(
            "TSTEP",
            "0",
        )
        or "0"
    )

    try:
        tstep_id = int(
            raw_tstep_id
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid TSTEP ID: "
            f"{raw_tstep_id!r}"
        ) from exc

    # ------------------------------------------------------------
    # Find actual TSTEP1 bulk card
    # ------------------------------------------------------------
    tstep = model.tsteps.get(
        tstep_id
    )

    if tstep is None:
        raise ValueError(
            f"Case Control TSTEP={tstep_id} "
            f"but no TSTEP1 record exists."
        )

    # ------------------------------------------------------------
    # Unit conversion:
    #
    # BDF source time assumed in seconds.
    # Current RAD seed uses ms.
    # ------------------------------------------------------------
    tstop_ms = bdf_time_to_rad_ms(
        tstep.dt
    )

    # ------------------------------------------------------------
    # Internal metadata block:
    #
    # It is NOT written directly into RAD.
    # assembler.py consumes it to render the fixed
    # Engine seed's /RUN TSTOP field.
    # ------------------------------------------------------------
    metadata_block = RadBlock(
        keyword="__ENGINE_METADATA__",
        lines=[
            f"{tstop_ms:.12g}"
        ],
        order=910,
        plugin=plugin.name,
        source_cards=plugin.source_cards,
    )

    audit = {
        "card": "TSTEP1",
        "status": "translated",
        "target": "/RUN/{{RUNNAME}}/1",
        "TSTEP_ID": tstep_id,
        "TSTOP_source": tstep.dt,
        "TSTOP_rad_ms": tstop_ms,
    }

    return (
        [metadata_block],
        [audit],
    )