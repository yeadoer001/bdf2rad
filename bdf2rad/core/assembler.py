from __future__ import annotations

from pathlib import Path
import json
import re


_PLACEHOLDER_RE = re.compile(
    r"\{\{[^{}]+\}\}"
)


def _load_header(
    root: Path,
    kind: str,
) -> list[str]:
    """
    Load fixed Starter / Engine seed from the existing
    knowledge_base.

    The seed controls the file structure. This function only
    loads
    it; it does not invent Radioss syntax.
    """

    path = (
        root
        / "knowledge_base"
        / "header_seed.json"
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Header seed not found: {path}"
        )

    data = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if kind not in data:
        raise KeyError(
            f"Header section {kind!r} "
            f"not found in {path}"
        )

    return list(
        data[kind]
    )


def _apply_seed_identity(
    lines: list[str],
    job: str,
    tstop: str | None = None,
) -> list[str]:
    """
    Replace only explicitly supported template variables.

    No other formatting or line layout is modified.
    """

    result = []

    for line in lines:

        rendered = str(line)

        rendered = rendered.replace(
            "{{RUNNAME}}",
            job,
        )

        rendered = rendered.replace(
            "{{TITLE}}",
            f"{job} Converted from Nastran BDF",
        )

        if tstop is not None:
            rendered = rendered.replace(
                "{{TSTOP}}",
                str(tstop),
            )

        result.append(
            rendered
        )

    return result


def _assert_no_placeholders(
    lines: list[str],
    deck_kind: str,
) -> None:
    """
    Never allow an unresolved {{...}} placeholder into
    an OpenRadioss input deck.
    """

    unresolved = []

    for line_no, line in enumerate(
        lines,
        start=1,
    ):

        for token in _PLACEHOLDER_RE.findall(
            line
        ):
            unresolved.append(
                (
                    line_no,
                    token,
                )
            )

    if not unresolved:
        return

    preview = ", ".join(
        f"line {line_no}: {token}"
        for line_no, token in unresolved[:20]
    )

    if len(unresolved) > 20:
        preview += (
            f", ... and "
            f"{len(unresolved) - 20} more"
        )

    raise RuntimeError(
        f"Unresolved template placeholders "
        f"in {deck_kind}: {preview}"
    )


def _clean_line(
    value,
) -> str:
    """
    Normalize one RAD output line.

    Newline characters are removed here because the writer
    adds CRLF consistently at the end.
    """

    if value is None:
        return ""

    return str(value).rstrip(
        "\r\n"
    )


def _append_rad_block(
    output: list[str],
    block,
) -> None:
    """
    Append exactly one Radioss Block.

    IMPORTANT DESIGN RULE
    ---------------------
    block.keyword is the Block header.
    block.lines contains the data lines AFTER the keyword.

    For backward compatibility with older plugins that still
    put the keyword in block.lines[0], detect and avoid
    duplicate emission.

    This allows old and new plugins to coexist while the
    plugin layer is gradually normalized.
    """

    keyword = _clean_line(
        getattr(
            block,
            "keyword",
            "",
        )
    )

    lines = [
        _clean_line(line)
        for line in getattr(
            block,
            "lines",
            [],
        )
    ]

    # ------------------------------------------------------------
    # No keyword at all.
    # This should normally never happen.
    # ------------------------------------------------------------
    if not keyword:
        output.extend(
            lines
        )
        return

    # ------------------------------------------------------------
    # Normal new-style plugin:
    #
    # keyword = "/BRIC20/1"
    # lines   = ["1 ... 20", "..."]
    # ------------------------------------------------------------
    if not lines:

        output.append(
            keyword
        )

        return

    # ------------------------------------------------------------
    # Backward compatibility:
    #
    # Some old plugins may have stored the keyword as their
    # first line as well:
    #
    # keyword = "/BRIC20/1"
    # lines   = [
    #     "/BRIC20/1",
    #     "1 ... 20"
    # ]
    #
    # Do not duplicate it.
    # ------------------------------------------------------------
    first = lines[0].strip()

    if first == keyword.strip():

        output.extend(
            lines
        )

        return

    # ------------------------------------------------------------
    # Correct modern behavior:
    #
    # append keyword first, then data lines.
    # ------------------------------------------------------------
    output.append(
        keyword
    )

    output.extend(
        lines
    )


def _sorted_blocks(
    blocks,
    min_order=None,
    max_order=None,
):
    """
    Return blocks sorted by their explicit plugin order.

    Optional order bounds distinguish Starter and Engine
    content without changing the individual plugin.
    """

    selected = []

    for block in blocks:

        order = int(
            getattr(
                block,
                "order",
                0,
            )
        )

        if (
            min_order is not None
            and order < min_order
        ):
            continue

        if (
            max_order is not None
            and order >= max_order
        ):
            continue

        selected.append(
            block
        )

    selected.sort(
        key=lambda block: (
            int(
                getattr(
                    block,
                    "order",
                    0,
                )
            ),
            str(
                getattr(
                    block,
                    "plugin",
                    "",
                )
            ),
            str(
                getattr(
                    block,
                    "keyword",
                    "",
                )
            ),
        )
    )

    return selected


def assemble_starter(
    root: Path,
    job: str,
    blocks,
) -> list[str]:
    """
    Assemble the Starter deck.

    Starter blocks:
        order < 900

    Every RadBlock is emitted as:

        block.keyword
        block.lines...

    /END is appended as the final keyword.
    """

    header = _apply_seed_identity(
        _load_header(
            root,
            "starter",
        ),
        job,
    )

    output = list(
        header
    )

    starter_blocks = _sorted_blocks(
        blocks,
        min_order=0,
        max_order=900,
    )

    for block in starter_blocks:
        _append_rad_block(
            output,
            block,
        )

    # ------------------------------------------------------------
    # /END is itself a keyword.
    # ------------------------------------------------------------
    output.append(
        "/END"
    )

    _assert_no_placeholders(
        output,
        "Starter deck",
    )

    return output


def assemble_engine(
    root: Path,
    job: str,
    blocks,
) -> list[str]:
    """
    Assemble Engine deck only when actual Engine blocks exist.

    Engine blocks:
        order >= 900

    TSTOP must be supplied by an actual Engine metadata
    block, normally produced by TSTEP1.
    """

    engine_blocks = _sorted_blocks(
        blocks,
        min_order=900,
        max_order=None,
    )

    # ------------------------------------------------------------
    # No Engine source information.
    # Do not create an Engine deck.
    # ------------------------------------------------------------
    if not engine_blocks:
        return []

    # ------------------------------------------------------------
    # Resolve TSTOP.
    # ------------------------------------------------------------
    tstop = None

    for block in engine_blocks:

        keyword = str(
            getattr(
                block,
                "keyword",
                "",
            )
        )

        plugin = str(
            getattr(
                block,
                "plugin",
                "",
            )
        ).lower()

        if (
            keyword
            == "__ENGINE_METADATA__"
            and getattr(
                block,
                "lines",
                None,
            )
        ):
            tstop = str(
                block.lines[0]
            ).strip()

            break

        if (
            plugin == "tstep1"
            and getattr(
                block,
                "lines",
                None,
            )
        ):
            tstop = str(
                block.lines[0]
            ).strip()

            break

    if not tstop:
        raise RuntimeError(
            "Engine blocks exist, but TSTOP was not "
            "resolved from an Engine metadata/TSTEP1 block."
        )

    header = _apply_seed_identity(
        _load_header(
            root,
            "engine",
        ),
        job,
        tstop,
    )

    output = list(
        header
    )

    for block in engine_blocks:

        # --------------------------------------------------------
        # Internal metadata is consumed by the Engine seed.
        # It must NEVER appear in the final RAD file.
        # --------------------------------------------------------
        if (
            getattr(
                block,
                "keyword",
                "",
            )
            == "__ENGINE_METADATA__"
        ):
            continue

        _append_rad_block(
            output,
            block,
        )

    _assert_no_placeholders(
        output,
        "Engine deck",
    )

    return output