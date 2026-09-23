from __future__ import annotations

import json
import re
from pathlib import Path

from .discovery import discover_blocks, describe
from .registry import build_registry
from .types import TranslationContext
from .assembler import assemble_starter, assemble_engine
from ..parser import read_model


class ConversionError(RuntimeError):
    pass


def jobname(src: str | Path) -> str:
    """
    Convert source filename into a Radioss-safe run name.
    """
    stem = Path(src).stem

    safe = re.sub(
        r"[^A-Za-z0-9_]+",
        "_",
        stem,
    )

    safe = safe.strip("_")

    return safe[:60] or "Solution"


def _write_ascii(
    path: Path,
    lines: list[str],
) -> None:
    """
    Radioss text deck writer.

    Keep ASCII-only output and CRLF line endings.
    """
    text = "\r\n".join(lines) + "\r\n"

    try:
        encoded = text.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ConversionError(
            f"RAD output contains non-ASCII characters: {exc}"
        ) from exc

    path.write_bytes(encoded)


def convert(
    src,
    outdir,
    project_root: Path,
    encoding="gb18030",
    blocks_root: Path | None = None,
):
    """
    Main BDF -> RAD conversion pipeline.

    Important design:
        1. discover block plugins from blocks/
        2. run only plugins relevant to source BDF
        3. assemble Starter from Starter blocks
        4. assemble Engine only when Engine blocks really exist
        5. never emit unresolved template placeholders
    """
    model = read_model(
        src,
        encoding,
    )

    plugin_root = (
        blocks_root
        if blocks_root is not None
        else project_root / "blocks"
    )

    specs = discover_blocks(
        plugin_root
    )

    # Keep registry construction for compatibility and
    # validation of plugin metadata.
    build_registry(specs)

    ctx = TranslationContext(
        model
    )

    ctx.metadata["jobname"] = jobname(src)
    ctx.metadata["project_root"] = str(
        project_root
    )
    ctx.metadata["registry"] = describe(
        specs
    )

    # ------------------------------------------------------------
    # Execute block translators
    # ------------------------------------------------------------
    for spec in specs:
        cards_present = any(
            model.card_counts.get(card, 0) > 0
            for card in spec.source_cards
        )

        emit_when_empty = spec.manifest.get(
            "emit_when_empty",
            False,
        )

        if not cards_present and not emit_when_empty:
            continue

        try:
            result = spec.module.translate(
                model,
                ctx,
                spec,
            )
        except Exception as exc:
            raise ConversionError(
                f"Block translator failed: "
                f"{spec.name}: {exc}"
            ) from exc

        if result is None:
            continue

        blocks, audit = result

        if blocks:
            ctx.blocks.extend(
                blocks
            )

        if audit:
            ctx.audit.extend(
                audit
            )

    # ------------------------------------------------------------
    # Output directory
    # ------------------------------------------------------------
    output_dir = Path(
        outdir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    job = ctx.metadata[
        "jobname"
    ]

    # ------------------------------------------------------------
    # Starter
    # ------------------------------------------------------------
    starter_lines = assemble_starter(
        project_root,
        job,
        ctx.blocks,
    )

    starter_path = (
        output_dir
        / f"{job}_0000.rad"
    )

    _write_ascii(
        starter_path,
        starter_lines,
    )

    # ------------------------------------------------------------
    # Engine
    # ------------------------------------------------------------
    engine_blocks = [
        block
        for block in ctx.blocks
        if block.order >= 900
    ]

    engine_lines = assemble_engine(
        project_root,
        job,
        engine_blocks,
    )

    engine_path: Path | None = None

    if engine_lines:
        engine_path = (
            output_dir
            / f"{job}_0001.rad"
        )

        _write_ascii(
            engine_path,
            engine_lines,
        )

    # ------------------------------------------------------------
    # Translation audit
    # ------------------------------------------------------------
    report = {
        "status": "GENERATED",
        "jobname": job,
        "source": str(
            Path(src).resolve()
        ),
        "blocks": describe(specs),
        "cards": model.card_counts,
        "diagnostics": model.diagnostics,
        "audit": ctx.audit,
        "starter": str(
            starter_path
        ),
        "engine": (
            str(engine_path)
            if engine_path is not None
            else None
        ),
    }

    audit_path = (
        output_dir
        / f"{job}_translation_audit.json"
    )

    audit_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    active_plugins = sum(
        any(
            model.card_counts.get(card, 0) > 0
            for card in spec.source_cards
        )
        for spec in specs
    )

    result = {
        "status": "GENERATED",
        "starter": str(
            starter_path
        ),
        "audit": str(
            audit_path
        ),
        "plugins": len(specs),
        "active_plugins": active_plugins,
        "engine": (
            str(engine_path)
            if engine_path is not None
            else None
        ),
    }

    return result