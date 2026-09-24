from __future__ import annotations


def translate(
    model,
    ctx,
    plugin,
):
    """
    BGSET is currently audit-only.

    Until a formally verified Nastran BGSET ->
    Radioss interface mapping is implemented, this
    plugin must NOT emit /INTER/TYPE2.
    """

    audit = []

    for sid, record in sorted(
        model.bgsets.items()
    ):

        audit.append(
            {
                "card":
                    "BGSET",
                "id":
                    sid,
                "status":
                    "audit-only",
                "source":
                    {
                        "source_group":
                            record.source,
                        "target_group":
                            record.target,
                        "scale":
                            record.scale,
                        "clearance":
                            record.clearance,
                    },
                "target":
                    None,
                "reason":
                    (
                        "BGSET -> /INTER/TYPE2 "
                        "mapping is not yet formally "
                        "verified; no target interface "
                        "is emitted."
                    ),
            }
        )

    return (
        [],
        audit,
    )