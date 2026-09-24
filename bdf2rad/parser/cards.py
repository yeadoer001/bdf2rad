from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Card:
    name: str
    fields: list[str]
    line: int
    raw: tuple[str, ...]


def nastran_float(value: str) -> float:
    """
    Parse a Nastran numeric field.

    Supports:
        normal decimal
        E/e scientific notation
        D/d scientific notation
        Nastran abbreviated exponent notation

    Examples:
        1.0
        1.0E-3
        1.0D-3
        1.0-3
        1.0+3
    """

    text = (
        str(value)
        .strip()
    )

    if not text:
        raise ValueError(
            "Empty Nastran numeric field"
        )

    text = (
        text
        .replace("D", "E")
        .replace("d", "e")
    )

    upper = text.upper()

    # ------------------------------------------------------------
    # Nastran abbreviated exponent:
    #
    #     1.0-3  -> 1.0E-3
    #     1.0+3  -> 1.0E+3
    #
    # Do not reinterpret a leading sign.
    # ------------------------------------------------------------

    if "E" not in upper:

        for index in range(
            1,
            len(text),
        ):

            if text[index] not in {
                "+",
                "-",
            }:
                continue

            previous = text[
                index - 1
            ]

            if (
                previous.isdigit()
                or previous == "."
            ):

                text = (
                    text[:index]
                    + "E"
                    + text[index:]
                )

                break

    result = float(text)

    if result != result:
        raise ValueError(
            f"NaN is not a valid Nastran number: {value!r}"
        )

    if result in (
        float("inf"),
        float("-inf"),
    ):
        raise ValueError(
            f"Infinity is not a valid Nastran number: {value!r}"
        )

    return result


def _is_comment(
    line: str,
) -> bool:

    stripped = line.strip()

    return (
        not stripped
        or stripped.startswith("$")
        or stripped.startswith("#")
    )


def _card_name(
    line: str,
) -> str:

    if not line:
        return ""

    # ------------------------------------------------------------
    # Free-field:
    #
    #     MAT1,1,....
    # ------------------------------------------------------------

    if "," in line[:80]:

        return (
            line
            .split(
                ",",
                1,
            )[0]
            .strip()
            .upper()
            .rstrip("*")
        )

    # ------------------------------------------------------------
    # Fixed-field / large-field:
    #
    # Card name occupies first 8 columns.
    # ------------------------------------------------------------

    return (
        line[:8]
        .strip()
        .upper()
        .rstrip("*")
    )


def _is_large_field(
    line: str,
) -> bool:

    if not line:
        return False

    first8 = line[:8]

    # Standard large-field form:
    #
    #     GRID*
    #     CHEXA*
    #     ...
    #
    return (
        first8.rstrip().endswith("*")
        or line[8:9] == "*"
        or line.startswith("*")
    )


def _parse_free_line(
    line: str,
) -> list[str]:
    """
    Parse one comma-separated free-field line.

    Empty fields are PRESERVED.

    This is critical for cards such as:

        MAT1,1,3.0E7,,0.30,1.0E-4

    which means:

        MID = 1
        E   = 3.0E7
        G   = blank
        NU  = 0.30
        RHO = 1.0E-4
    """

    values = [
        token.strip()
        for token in line.split(",")
    ]

    return values


def _parse_fixed_small(
    line: str,
) -> list[str]:
    """
    Parse standard Nastran 8-character fields.

    The returned list includes the first 8-character card-name
    field so the caller can normalize it consistently.
    """

    values = []

    for start in range(
        0,
        len(line),
        8,
    ):

        values.append(
            line[
                start:start + 8
            ].strip()
        )

    return values


def _parse_fixed_large(
    line: str,
) -> list[str]:
    """
    Parse one large-field physical line.

    Nastran large-field cards use:
        first 8 characters = card/continuation marker
        next fields        = 16 characters each
    """

    values = [
        line[:8].strip()
    ]

    body = line[8:]

    for start in range(
        0,
        len(body),
        16,
    ):

        field = body[
            start:start + 16
        ]

        values.append(
            field
            .strip()
            .rstrip("+")
        )

    return values


def _parse_physical_line(
    line: str,
):
    """
    Return:
        mode, fields

    mode:
        free
        small
        large
    """

    if "," in line[:80]:

        return (
            "free",
            _parse_free_line(
                line
            ),
        )

    if _is_large_field(line):

        return (
            "large",
            _parse_fixed_large(
                line
            ),
        )

    return (
        "small",
        _parse_fixed_small(
            line
        ),
    )


def _clean_continuation_fields(
    fields: list[str],
) -> list[str]:

    if not fields:
        return []

    cleaned = []

    for value in fields:

        text = str(
            value
        ).strip()

        if text in {
            "+",
            "*",
        }:
            cleaned.append("")
            continue

        cleaned.append(
            text
        )

    return cleaned


def _build_free_card(
    first: str,
    continuations: list[str],
    start: int,
) -> Card:

    first_fields = _parse_free_line(
        first
    )

    # First field is the card name.
    if not first_fields:
        raise ValueError(
            f"Empty free-field card at line {start}"
        )

    name = (
        first_fields[0]
        .strip()
        .upper()
        .rstrip("*")
    )

    fields = list(
        first_fields
    )

    for line in continuations:

        continuation_fields = (
            _parse_free_line(
                line
            )
        )

        if not continuation_fields:
            continue

        # --------------------------------------------------------
        # Free-field continuation:
        #
        #     +,a,b,c
        #
        # or
        #
        #     *,a,b,c
        #
        # The leading continuation marker is not a data field.
        # --------------------------------------------------------

        first_token = (
            continuation_fields[0]
            .strip()
        )

        if first_token in {
            "+",
            "*",
        }:

            continuation_fields = (
                continuation_fields[1:]
            )

        fields.extend(
            continuation_fields
        )

    fields[0] = name

    return Card(
        name=name,
        fields=fields,
        line=start,
        raw=tuple(
            [first] + continuations
        ),
    )


def _build_fixed_card(
    first: str,
    continuations: list[str],
    start: int,
) -> Card:

    mode, first_fields = (
        _parse_physical_line(
            first
        )
    )

    if not first_fields:
        raise ValueError(
            f"Empty fixed-field card at line {start}"
        )

    name = _card_name(
        first
    )

    # ------------------------------------------------------------
    # Small-field first line.
    #
    # first_fields:
    #
    #     [CARD, ID, ...]
    # ------------------------------------------------------------

    if mode == "small":

        fields = list(
            first_fields
        )

        fields[0] = name

        for line in continuations:

            continuation_mode, continuation_fields = (
                _parse_physical_line(
                    line
                )
            )

            if continuation_mode != "small":

                raise ValueError(
                    f"Mixed fixed-field format in card "
                    f"{name} at line {start}: "
                    f"continuation is not small-field."
                )

            if not continuation_fields:
                continue

            # First 8-character field contains the
            # continuation marker and is not data.
            fields.extend(
                continuation_fields[1:]
            )

        return Card(
            name=name,
            fields=fields,
            line=start,
            raw=tuple(
                [first] + continuations
            ),
        )

    # ------------------------------------------------------------
    # Large-field.
    #
    # first_fields:
    #
    #     [CARD*, ID, CP, X, Y, ...]
    #
    # ------------------------------------------------------------

    # Large-field first line contains a trailing 8-character continuation
    # identifier in field 10 (columns 73-80).  That identifier is NOT a
    # semantic data field and must not be exposed to model_reader.  The old
    # implementation kept it in `fields`, which shifted Z/CD and every
    # later field by one position.
    if len(first_fields) >= 2:
        fields = list(first_fields[:-1])
    else:
        fields = list(first_fields)

    # first field is always normalized card name.
    fields[0] = name

    for line in continuations:

        continuation_mode, continuation_fields = (
            _parse_physical_line(
                line
            )
        )

        if continuation_mode != "large":

            raise ValueError(
                f"Mixed fixed-field format in card "
                f"{name} at line {start}: "
                f"continuation is not large-field."
            )

        if not continuation_fields:
            continue

        # --------------------------------------------------------
        # Standard large-field continuation:
        #   *CONTID <16-char field> <16-char field> ...
        #
        # Some Simcenter/Nastran exporters encountered in practice emit
        # a compact continuation such as:
        #   * 0.000000000E+00 0
        # Here the Z/CD data starts immediately after the '*', rather than
        # being aligned to the second 16-character field boundary.  The
        # generic 16-character splitter would otherwise chop the number
        # itself (e.g. '* 0.0000' / '00000E+0' / '0').
        # --------------------------------------------------------
        stripped = line.lstrip()
        compact_after_marker = stripped[1:] if stripped.startswith("*") else ""
        compact_tokens = compact_after_marker.split()

        is_compact_star_data = (
            stripped.startswith("*")
            and bool(compact_tokens)
            and (
                compact_after_marker.startswith(" ")
                or compact_after_marker.startswith("\t")
            )
            and len(compact_tokens) <= 4
        )

        if is_compact_star_data:
            # The continuation marker is the first token/character; all
            # remaining whitespace-separated tokens are real data fields.
            fields.extend(compact_tokens)
            continue

        # Standard large-field: first 8-character field is the continuation
        # identifier and is not data.
        fields.extend(
            continuation_fields[1:]
        )

    return Card(
        name=name,
        fields=fields,
        line=start,
        raw=tuple(
            [first] + continuations
        ),
    )


def _card(
    first: str,
    continuations: list[str],
    start: int,
) -> Card:

    mode, _ = _parse_physical_line(
        first
    )

    if mode == "free":

        return _build_free_card(
            first,
            continuations,
            start,
        )

    return _build_fixed_card(
        first,
        continuations,
        start,
    )


def _is_continuation(
    line: str,
) -> bool:

    if not line:
        return False

    # Nastran large-field continuation is identified by an asterisk
    # in column 1.  In real Simcenter/Nastran exports the continuation
    # identifier may be followed by data in the first 8-column area, e.g.
    #     * 0.000000000E+00 0
    # The old parser compared line[:8].strip() with exactly "*", which
    # rejected this legal/commonly exported form and caused the Z field to
    # be read as a new card.
    if line.startswith("*"):
        return True

    # Keep support for conventional small-field/free-field '+' markers.
    first8 = line[:8].strip()
    return first8 == "+"


def iter_cards(
    path: str | Path,
    encoding: str = "gb18030",
):

    pending = None
    pending_continuations = []
    start_line = 0

    mode = "pre"

    with Path(path).open(
        "r",
        encoding=encoding,
        errors="strict",
        newline=None,
    ) as stream:

        for number, raw in enumerate(
            stream,
            1,
        ):

            line = raw.rstrip(
                "\r\n"
            )

            stripped = (
                line.strip()
            )

            upper = (
                stripped.upper()
            )

            # ----------------------------------------------------
            # Section transitions.
            # ----------------------------------------------------

            if upper == "CEND":

                if pending is not None:

                    yield _card(
                        pending,
                        pending_continuations,
                        start_line,
                    )

                    pending = None
                    pending_continuations = []

                mode = "case"
                continue

            if upper == "BEGIN BULK":

                if pending is not None:

                    yield _card(
                        pending,
                        pending_continuations,
                        start_line,
                    )

                    pending = None
                    pending_continuations = []

                mode = "bulk"
                continue

            if upper.startswith(
                "ENDDATA"
            ):

                if pending is not None:

                    yield _card(
                        pending,
                        pending_continuations,
                        start_line,
                    )

                pending = None
                pending_continuations = []

                mode = "after"
                continue

            # ----------------------------------------------------
            # Skip comments/outside bulk.
            # ----------------------------------------------------

            if (
                mode != "bulk"
                or _is_comment(line)
            ):
                continue

            # ----------------------------------------------------
            # Continuation of current card.
            # ----------------------------------------------------

            if (
                pending is not None
                and _is_continuation(line)
            ):

                pending_continuations.append(
                    line
                )

                continue

            # ----------------------------------------------------
            # New card.
            # ----------------------------------------------------

            if pending is not None:

                yield _card(
                    pending,
                    pending_continuations,
                    start_line,
                )

            pending = line

            pending_continuations = []

            start_line = number

    if pending is not None:

        yield _card(
            pending,
            pending_continuations,
            start_line,
        )


def read_case_control(
    path: str | Path,
    encoding: str = "gb18030",
):

    control = []
    executive = []

    mode = "pre"

    with Path(path).open(
        "r",
        encoding=encoding,
        errors="strict",
        newline=None,
    ) as stream:

        for raw in stream:

            line = raw.rstrip(
                "\r\n"
            )

            upper = (
                line.strip().upper()
            )

            if upper == "CEND":

                mode = "case"
                continue

            if upper == "BEGIN BULK":

                mode = "bulk"
                continue

            if (
                mode == "case"
                and line.strip()
            ):

                control.append(
                    line
                )

            elif (
                mode == "pre"
                and line.strip()
            ):

                executive.append(
                    line
                )

    return (
        control,
        executive,
    )