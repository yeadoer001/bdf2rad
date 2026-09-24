from __future__ import annotations

from bdf2rad.core.plugin_helpers import (
    emit,
    rb,
    fi,
    fs,
    bdf_accel_to_rad_mm_ms2,
)


def _get_direction_and_component(
    vector,
):
    """
    Determine the dominant axis and return:

        direction
        signed acceleration component
        converted vector

    Nastran GRAV:
        A, GX, GY, GZ

    Radioss /GRAV:
        DIR + Fscale_Y
    """

    if vector is None:
        raise ValueError(
            "GRAV vector is missing."
        )

    if len(vector) != 3:
        raise ValueError(
            "GRAV vector must contain exactly "
            "three components."
        )

    converted = tuple(
        bdf_accel_to_rad_mm_ms2(
            float(value)
        )
        for value in vector
    )

    if all(
        abs(value) == 0.0
        for value in converted
    ):
        raise ValueError(
            "GRAV vector is zero."
        )

    axis = max(
        range(3),
        key=lambda i: abs(
            converted[i]
        ),
    )

    direction = (
        "X",
        "Y",
        "Z",
    )[axis]

    return (
        direction,
        converted[axis],
        converted,
    )


def _fmt_dir(
    direction: str,
) -> str:
    """
    Radioss DIR field is a 10-character field.
    """
    value = (
        str(direction)
        .strip()
        .upper()
    )

    if value not in (
        "X",
        "Y",
        "Z",
    ):
        raise ValueError(
            f"Invalid GRAV DIR: {direction!r}"
        )

    return f"{value:>10s}"


def translate(
    model,
    ctx,
    plugin,
):
    """
    Nastran GRAV -> OpenRadioss /GRAV.

    Source:
        GRAV SID CID A GX GY GZ

    Repository Gravity:
        sid
        cid
        scale
        vector

    Official OpenRadioss target:

        /GRAV/<ID>
        title
        fct_IDT DIR skew_ID sens_ID grnd_ID
        [blank] Ascale_x Fscale_Y

    Current verified support:
        CID = 0

    A non-zero Nastran coordinate system is rejected instead
    of being silently interpreted as the global frame.
    """

    blocks = []
    audit = []

    for sid, gravity in sorted(
        model.gravs.items()
    ):
        # --------------------------------------------------------
        # IMPORTANT:
        # Gravity uses "sid", not "gid".
        # --------------------------------------------------------
        grav_id = int(
            gravity.sid
        )

        cid = int(
            gravity.cid
        )

        scale = float(
            gravity.scale
        )

        vector = tuple(
            float(value)
            for value in gravity.vector
        )

        # --------------------------------------------------------
        # Coordinate-system mapping is only verified for CID=0.
        # --------------------------------------------------------
        if cid != 0:
            raise ValueError(
                f"GRAV SID={grav_id} uses "
                f"CID={cid}. "
                "Only CID=0 is supported because this repository "
                "does not yet contain a verified Nastran coordinate "
                "system -> Radioss skew transformation."
            )

        (
            direction,
            component,
            converted_vector,
        ) = _get_direction_and_component(
            vector
        )

        # --------------------------------------------------------
        # Constant gravity:
        #
        # fct_IDT = 0
        #
        # Official /GRAV uses Fscale_Y directly for the constant
        # gravity magnitude.
        # --------------------------------------------------------
        fct_id = 0

        # Global frame
        skew_id = 0

        # No sensor
        sens_id = 0

        # Apply to all nodes
        grnd_id = 0

        # Constant case
        ascale = 1.0

        fscale = (
            component
            * scale
        )

        # --------------------------------------------------------
        # Every field is formatted independently.
        #
        # The sixth field is intentionally a 10-character blank
        # field because the official /GRAV table contains an empty
        # field between grnd_ID and Ascale_x.
        # --------------------------------------------------------
        values = {
            "ID": grav_id,
            "TITLE": (
                f"GRAV_{grav_id}"
            ),
            "FCT": fi(
                fct_id
            ),
            "DIR": _fmt_dir(
                direction
            ),
            "SKEW": fi(
                skew_id
            ),
            "SENS": fi(
                sens_id
            ),
            "GRND": fi(
                grnd_id
            ),
            "BLANK": (
                " " * 10
            ),
            "ASCALE": fs(
                ascale
            ),
            "FSCALE": fs(
                fscale
            ),
        }

        rendered = emit(
            plugin,
            values
        )

        blocks.append(
            rb(
                plugin,
                f"/GRAV/{grav_id}",
                rendered
            )
        )

        audit.append(
            {
                "card": "GRAV",
                "id": grav_id,
                "status": "translated",
                "target": (
                    f"/GRAV/{grav_id}"
                ),
                "source_sid": grav_id,
                "source_cid": cid,
                "source_scale": scale,
                "source_vector": list(
                    vector
                ),
                "target_vector_mm_ms2": list(
                    converted_vector
                ),
                "direction": direction,
                "fct_IDT": fct_id,
                "skew_ID": skew_id,
                "sens_ID": sens_id,
                "grnd_ID": grnd_id,
                "Ascale_x": ascale,
                "Fscale_Y": fscale,
                "blank_field_present": True,
            }
        )

    return (
        blocks,
        audit
    )