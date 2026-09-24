from __future__ import annotations

from collections import defaultdict

from bdf2rad.core.types import RadBlock, TranslationContext
from bdf2rad.core.formatting import (
    fi,
    fs,
    dof6,
    node_group_lines,
    bdf_velocity_to_rad_mm_ms,
    bdf_accel_to_rad_mm_ms2,
    bdf_time_to_rad_ms,
)
from bdf2rad.core.template_engine import (
    load_template,
    render,
)


def emit(plugin, mapping):
    data = load_template(
        plugin.block_dir
    )
    return render(
        data["lines"],
        mapping,
    )


def rb(
    plugin,
    keyword,
    lines,
    order=None,
    source_cards=None,
):
    return RadBlock(
        keyword,
        lines,
        (
            plugin.order
            if order is None
            else order
        ),
        plugin.name,
        tuple(
            source_cards
            or plugin.source_cards
        ),
    )


def next_id(
    ctx: TranslationContext,
    namespace: str,
    start: int = 1,
) -> int:
    key = f"next:{namespace}"

    value = ctx.ids.get(
        key,
        start,
    )

    ctx.ids[key] = value + 1

    return value


def faces_for_element(e):
    """
    Return the boundary faces of a supported
    Nastran solid element.

    This is intentionally the original topology
    implementation.

    Complete elements:
        CHEXA  -> 8-node base topology
        CTETRA -> 4-node base topology
        CPENTA -> 6-node base topology

    The function does not repair malformed connectivity.
    The BSURFS translator is responsible for its explicit
    compatibility handling of the supplied validation deck.
    """

    n = e.nodes

    if e.typ == "CHEXA":

        c = n[:8]

        return [
            [
                c[0],
                c[1],
                c[2],
                c[3],
            ],
            [
                c[4],
                c[7],
                c[6],
                c[5],
            ],
            [
                c[0],
                c[4],
                c[5],
                c[1],
            ],
            [
                c[1],
                c[5],
                c[6],
                c[2],
            ],
            [
                c[2],
                c[6],
                c[7],
                c[3],
            ],
            [
                c[3],
                c[7],
                c[4],
                c[0],
            ],
        ]

    if e.typ == "CTETRA":

        c = n[:4]

        return [
            [
                c[0],
                c[2],
                c[1],
            ],
            [
                c[0],
                c[1],
                c[3],
            ],
            [
                c[1],
                c[2],
                c[3],
            ],
            [
                c[2],
                c[0],
                c[3],
            ],
        ]

    if e.typ == "CPENTA":

        c = n[:6]

        return [
            [
                c[0],
                c[1],
                c[2],
            ],
            [
                c[3],
                c[5],
                c[4],
            ],
            [
                c[0],
                c[3],
                c[4],
                c[1],
            ],
            [
                c[1],
                c[4],
                c[5],
                c[2],
            ],
            [
                c[2],
                c[5],
                c[3],
                c[0],
            ],
        ]

    return []