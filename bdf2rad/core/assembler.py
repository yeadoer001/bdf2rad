from __future__ import annotations

from pathlib import Path
import json
import re


_PLACEHOLDER_RE = re.compile(r"\{\{[^{}]+\}\}")


def _load_header(root: Path, kind: str) -> list[str]:
    """
    Load the fixed Starter / Engine seed from knowledge_base/header_seed.json.

    The seed owns the RAD file structure. This module must not invent new
    Radioss syntax.
    """
    path = root / "knowledge_base" / "header_seed.json"

    if not path.exists():
        raise FileNotFoundError(
            f"Header seed not found: {path}"
        )

    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    if kind not in data:
        raise KeyError(
            f"Header seed section '{kind}' not found in {path}"
        )

    return list(data[kind])


def _apply_seed_identity(
    lines: list[str],
    job: str,
    tstop: str | None = None,
) -> list[str]:
    """
    Replace only explicitly declared template variables.

    No line layout, spacing, ordering, or keyword is changed here.
    """
    result: list[str] = []

    for line in lines:
        rendered = line

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
                tstop,
            )

        result.append(rendered)

    return result


def _assert_no_placeholders(
    lines: list[str],
    file_kind: str,
) -> None:
    """
    Final safety check.

    Any unresolved {{...}} token means the template was not fully
    instantiated and must never be passed to Radioss.
    """
    unresolved: list[tuple[int, str]] = []

    for line_number, line in enumerate(lines, start=1):
        for token in _PLACEHOLDER_RE.findall(line):
            unresolved.append(
                (line_number, token)
            )

    if not unresolved:
        return

    preview = ", ".join(
        f"line {line_number}: {token}"
        for line_number, token in unresolved[:20]
    )

    if len(unresolved) > 20:
        preview += (
            f", ... and {len(unresolved) - 20} more"
        )

    raise RuntimeError(
        f"Unresolved template placeholders in "
        f"{file_kind}: {preview}"
    )


def assemble_starter(
    root: Path,
    job: str,
    blocks,
) -> list[str]:
    """
    Assemble Starter deck.

    Blocks with order < 900 belong to Starter/model definition.
    """
    header = _apply_seed_identity(
        _load_header(root, "starter"),
        job,
    )

    body: list[str] = []

    starter_blocks = [
        block
        for block in blocks
        if block.order < 900
    ]

    starter_blocks.sort(
        key=lambda block: (
            block.order,
            block.plugin,
            block.keyword,
        )
    )

    for block in starter_blocks:
        body.extend(block.lines)

    lines = header + body + ["/END"]

    _assert_no_placeholders(
        lines,
        "Starter deck",
    )

    return lines


def assemble_engine(
    root: Path,
    job: str,
    blocks,
) -> list[str]:
    """
    Assemble Engine deck only when actual Engine-level information exists.

    Important:
        - GRID-only / MAT-only / mesh-only validation cases do not need 0001.rad.
        - TSTEP1 is currently the trigger that supplies TSTOP.
        - Never emit an unresolved {{TSTOP}}.
    """
    engine_blocks = [
        block
        for block in blocks
        if block.order >= 900
    ]

    # ------------------------------------------------------------
    # No Engine-level source content:
    # do not create an Engine deck.
    # ------------------------------------------------------------
    if not engine_blocks:
        return []

    tstop: str | None = None

    for block in engine_blocks:
        if block.keyword == "__ENGINE_METADATA__":
            if block.lines:
                tstop = str(block.lines[0]).strip()
            break

    # ------------------------------------------------------------
    # Engine blocks exist but no TSTOP was resolved.
    # Do not invent a time value.
    # ------------------------------------------------------------
    if tstop is None or tstop == "":
        raise RuntimeError(
            "Engine-level blocks exist, but no TSTOP was "
            "resolved from the source model. "
            "Do not generate an Engine deck with an "
            "unresolved or invented stop time."
        )

    header = _apply_seed_identity(
        _load_header(root, "engine"),
        job,
        tstop,
    )

    body: list[str] = []

    for block in sorted(
        engine_blocks,
        key=lambda item: (
            item.order,
            item.plugin,
            item.keyword,
        )
    ):
        # Internal metadata is consumed by the Engine seed.
        if block.keyword == "__ENGINE_METADATA__":
            continue

        body.extend(block.lines)

    lines = header + body

    _assert_no_placeholders(
        lines,
        "Engine deck",
    )

    return lines