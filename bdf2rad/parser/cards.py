from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Card:
    name: str
    fields: list[str]
    line: int
    raw: tuple[str, ...]


def nastran_float(v: str) -> float:
    s = v.strip()

    if not s:
        return 0.0

    s = (
        s.replace("D", "E")
         .replace("d", "e")
    )

    if "E" not in s.upper():
        for i in range(1, len(s)):
            if (
                s[i] in "+-"
                and s[i - 1].isdigit()
            ):
                s = (
                    s[:i]
                    + "E"
                    + s[i:]
                )
                break

    return float(s)


def _comment(line: str) -> bool:
    s = line.strip()

    return (
        not s
        or s.startswith("$")
        or s.startswith("#")
    )


def _name(line: str) -> str:
    if "," in line[:80]:
        return (
            line
            .split(",", 1)[0]
            .strip()
            .upper()
            .rstrip("*")
        )

    return (
        line[:8]
        .strip()
        .upper()
        .rstrip("*")
    )


def _fixed(
    line: str,
    large: bool,
) -> list[str]:
    """
    Parse Nastran fixed-width fields.

    Small field:
        8 characters / field

    Large field:
        16 characters / field after
        the first 8-character marker field.
    """

    if large:
        body = line[8:]

        return [
            body[i:i + 16]
                .strip()
                .rstrip("+")
            for i in range(
                0,
                len(body),
                16,
            )
        ]

    return [
        line[i:i + 8]
            .strip()
            .rstrip("+")
        for i in range(
            0,
            len(line),
            8,
        )
    ]


def _free(line: str) -> list[str]:
    return [
        x.strip()
        for x in line.split(",")
    ]


def _is_continuation(
    line: str,
) -> bool:
    """
    Detect a Nastran continuation marker.

    The marker lives in the first 8-character field,
    not necessarily at column 1.

    Examples:

        +       9      10 ...
              + 9      10 ...
        *       9      10 ...

    Both '+' and '*' are continuation markers when
    they are the content of field 1.
    """

    if not line:
        return False

    first_field = (
        line[:8]
        .strip()
    )

    return first_field in {
        "+",
        "*",
    }


def _card(
    first: str,
    cont: list[str],
    start: int,
) -> Card:

    large = (
        first[8:9] == "*"
        or first[:8]
            .rstrip()
            .endswith("*")
    )

    # ------------------------------------------------------------
    # Free-field / comma separated card
    # ------------------------------------------------------------
    if "," in first[:80]:

        fields = _free(
            first
        )

        for ln in cont:

            cf = _free(
                ln
            )

            if cf and cf[0] in {
                "+",
                "*",
            }:
                cf = cf[1:]

            fields.extend(
                cf
            )

    # ------------------------------------------------------------
    # Fixed-width card
    # ------------------------------------------------------------
    else:

        base = _fixed(
            first,
            large,
        )

        if not base:
            raise ValueError(
                f"Empty BDF card at line {start}"
            )

        fields = [
            base[0]
        ]

        if large:
            fields.extend(
                base
            )
        else:
            fields.extend(
                base[1:]
            )

        # --------------------------------------------------------
        # Add continuation fields.
        # --------------------------------------------------------
        for ln in cont:

            b = _fixed(
                ln,
                large,
            )

            if not b:
                continue

            # First 8-character field of a fixed-width
            # continuation line is the continuation marker.
            fields.extend(
                b[1:]
            )

    fields[0] = _name(
        first
    )

    return Card(
        fields[0],
        fields,
        start,
        tuple(
            [first] + cont
        ),
    )


def iter_cards(
    path: str | Path,
    encoding: str = "gb18030",
):
    """
    Iterate over Bulk Data cards.

    Important:
    continuation detection uses the first 8-character
    field rather than requiring '+'/'*' at column 1.
    """

    pending = None

    raw: list[str] = []

    line0 = 0

    mode = "pre"

    with Path(path).open(
        "r",
        encoding=encoding,
        errors="strict",
        newline=None,
    ) as fh:

        for n, ln in enumerate(
            fh,
            1,
        ):

            ln = ln.rstrip(
                "\r\n"
            )

            u = ln.strip().upper()

            # ----------------------------------------------------
            # Case / Bulk section transitions
            # ----------------------------------------------------
            if u == "BEGIN BULK":
                mode = "bulk"
                continue

            if u == "CEND":
                mode = "case"
                continue

            # ----------------------------------------------------
            # End of bulk data
            # ----------------------------------------------------
            if u.startswith(
                "ENDDATA"
            ):

                if pending is not None:

                    yield _card(
                        raw[0],
                        raw[1:],
                        line0,
                    )

                pending = None
                raw = []
                mode = "after"

                continue

            # ----------------------------------------------------
            # Outside Bulk Data or comment
            # ----------------------------------------------------
            if (
                mode != "bulk"
                or _comment(ln)
            ):
                continue

            # ----------------------------------------------------
            # Continuation
            # ----------------------------------------------------
            continuation = _is_continuation(
                ln
            )

            if (
                continuation
                and pending is not None
            ):

                raw.append(
                    ln
                )

                continue

            # ----------------------------------------------------
            # New card
            # ----------------------------------------------------
            if pending is not None:

                yield _card(
                    raw[0],
                    raw[1:],
                    line0,
                )

            pending = ln

            raw = [
                ln
            ]

            line0 = n

    # ------------------------------------------------------------
    # Last card if ENDDATA was omitted.
    # ------------------------------------------------------------
    if pending is not None:

        yield _card(
            raw[0],
            raw[1:],
            line0,
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
    ) as fh:

        for raw in fh:

            ln = raw.rstrip(
                "\r\n"
            )

            u = ln.strip().upper()

            if u == "CEND":
                mode = "case"
                continue

            if u == "BEGIN BULK":
                mode = "bulk"
                continue

            if (
                mode == "case"
                and ln.strip()
            ):
                control.append(
                    ln
                )

            elif (
                mode == "pre"
                and ln.strip()
            ):
                executive.append(
                    ln
                )

    return (
        control,
        executive,
    )