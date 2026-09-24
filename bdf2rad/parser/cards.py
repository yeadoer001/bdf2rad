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
    text = str(value).strip()
    if not text:
        raise ValueError("Empty Nastran numeric field")

    text = text.replace("D", "E").replace("d", "e")

    if "E" not in text.upper():
        for index in range(1, len(text)):
            if text[index] not in "+-":
                continue
            previous = text[index - 1]
            if previous.isdigit() or previous == ".":
                text = text[:index] + "E" + text[index:]
                break

    result = float(text)
    if result != result or result in (float("inf"), float("-inf")):
        raise ValueError(f"NaN/Infinity is not valid in a Nastran numeric field: {value!r}")
    return result


def _strip_inline_comment(line: str) -> str:
    """Strip an inline $ comment while preserving quoted INCLUDE paths."""
    quote: str | None = None
    for index, char in enumerate(line):
        if char in "'\"":
            if quote == char:
                quote = None
            elif quote is None:
                quote = char
        elif char == "$" and quote is None:
            return line[:index]
    return line


def _is_comment(line: str) -> bool:
    stripped = line.strip()
    return not stripped or stripped.startswith("$") or stripped.startswith("#")


def _card_name(line: str) -> str:
    if not line:
        return ""
    if "," in line[:10]:
        return line.split(",", 1)[0].strip().upper().rstrip("*")
    return line[:8].strip().upper().rstrip("*")


def _parse_free_line(line: str) -> list[str]:
    return [token.strip() for token in line.split(",")]


def _parse_small_line(line: str) -> list[str]:
    padded = line[:80].ljust(80)
    return [padded[index:index + 8].strip() for index in range(0, 80, 8)]


def _parse_large_first_line(line: str) -> tuple[list[str], str]:
    padded = line[:80].ljust(80)
    name = padded[:8].strip().upper().rstrip("*")
    data = [padded[8 + i * 16:8 + (i + 1) * 16].strip() for i in range(4)]
    continuation_id = padded[72:80].strip()
    return [name, *data], continuation_id


def _parse_large_continuation(line: str) -> tuple[list[str], str, bool]:
    """Return semantic data fields, next continuation id, compact flag."""
    stripped = line.lstrip()

    # Simcenter compatibility form seen in the supplied T02-style material:
    #     * 0.0 0
    # The star is the continuation marker, not a fixed-width field.
    if stripped.startswith("*") and len(stripped) > 1 and stripped[1].isspace():
        payload = stripped[1:].strip()
        return (payload.split() if payload else []), "", True

    padded = line[:80].ljust(80)
    first8 = padded[:8].strip()
    data = [padded[8 + i * 16:8 + (i + 1) * 16].strip() for i in range(4)]
    next_id = padded[72:80].strip()
    return data, next_id, False


def _detect_first_line(line: str) -> tuple[str, list[str], str]:
    if "," in line[:10]:
        values = _parse_free_line(line)
        return "free", values, ""

    first8 = line[:8]
    if first8.rstrip().endswith("*") or line[8:9] == "*":
        values, continuation_id = _parse_large_first_line(line)
        return "large", values, continuation_id

    return "small", _parse_small_line(line), ""


def _free_card(first: str, continuations: list[str], start: int) -> Card:
    values = _parse_free_line(first)
    if not values:
        raise ValueError(f"Empty free-field card at BDF line {start}")

    name = values[0].strip().upper().rstrip("*")
    fields = [name]

    # In free-field format, a continuation identifier occupies the final
    # position of the physical line when it starts with + or *. It is not
    # semantic card data and must be removed before exposing Card.fields.
    data = list(values[1:])
    if data and data[-1].startswith(("+", "*")):
        continuation_id = data.pop()
    else:
        continuation_id = ""

    fields.extend(data)

    expected_id = continuation_id.lstrip("+*").strip()

    for line in continuations:
        vals = _parse_free_line(line)
        if not vals:
            continue

        marker = vals[0].strip()
        if marker == "" or marker == "+" or marker == "*" or marker.startswith(("+", "*")):
            vals = vals[1:]

        fields.extend(vals)

    return Card(name, fields, start, tuple([first] + continuations))


def _fixed_card(first: str, continuations: list[str], start: int) -> Card:
    mode, first_fields, continuation_id = _detect_first_line(first)
    name = _card_name(first)

    if mode == "small":
        # Small-field has 10 physical 8-character fields. Field 10 is the
        # continuation identifier and is never semantic data.
        fields = list(first_fields[:9])
        fields[0] = name

        for line in continuations:
            # Continuation field 1 is the continuation marker/identifier and
            # field 10 is the next continuation identifier; fields 2-9 are
            # semantic data.
            continuation_fields = _parse_small_line(line)
            fields.extend(continuation_fields[1:9])

        return Card(name, fields, start, tuple([first] + continuations))

    # Large-field first half-line: CARD* + four 16-character semantic fields.
    # The final 8-character continuation identifier is not semantic data.
    fields = list(first_fields)
    fields[0] = name
    expected_id = continuation_id.strip()

    for line in continuations:
        data_fields, next_id, compact = _parse_large_continuation(line)
        fields.extend(data_fields)
        if next_id:
            expected_id = next_id

    return Card(name, fields, start, tuple([first] + continuations))


def _card(first: str, continuations: list[str], start: int) -> Card:
    mode, _, _ = _detect_first_line(first)
    if mode == "free":
        return _free_card(first, continuations, start)
    return _fixed_card(first, continuations, start)


def _first_line_continuation_id(line: str) -> str:
    mode, _, continuation_id = _detect_first_line(line)
    return continuation_id if mode == "large" else ""


def _is_continuation(line: str, pending_first: str, previous_line: str | None = None) -> bool:
    """Recognize continuations using the parent's physical field format."""
    if not line:
        return False

    stripped = line.lstrip()
    if stripped.startswith(("$", "#")):
        return False

    parent_mode, _, parent_id = _detect_first_line(pending_first)

    # Free-field continuation: leading marker/blank field followed by commas.
    if parent_mode == "free":
        if "," not in line[:80]:
            return False
        first_token = line.split(",", 1)[0].strip()
        return first_token == "" or first_token == "+" or first_token == "*" or first_token.startswith(("+", "*"))

    # Small-field continuation: blank first field or explicit +/-/* marker.
    if parent_mode == "small":
        first8 = line[:8].strip()
        # Small-field continuation field 1 may be blank, or may contain a
        # continuation identifier beginning with + or *.
        return first8 == "" or first8.startswith(("+", "*"))

    # Large-field continuation:
    #   *......
    # or a blank/matching continuation identifier in the first 8 columns.
    if stripped.startswith("*"):
        return True

    first8 = line[:8].strip()
    if first8 == "":
        return True

    # For a multi-line Large Field card, the continuation identifier on the
    # immediately preceding physical line controls the next continuation.
    # This matters when a card uses a different label on each continuation.
    expected_id = parent_id
    if previous_line is not None and parent_mode == "large":
        # Once we know the pending card is Large Field, the previous physical
        # line is part of that same long record. Its final 8-character field
        # is the continuation identifier for the next physical line.
        padded = previous_line[:80].ljust(80)
        previous_id = padded[72:80].strip()
        expected_id = previous_id or expected_id

    if expected_id:
        return first8 in {expected_id, "*" + expected_id}

    return False


def iter_cards(path: str | Path, encoding: str = "gb18030"):
    pending: str | None = None
    continuations: list[str] = []
    start_line = 0
    mode = "pre"
    previous_line: str | None = None

    with Path(path).open("r", encoding=encoding, errors="strict", newline=None) as stream:
        for number, raw in enumerate(stream, 1):
            line = _strip_inline_comment(raw.rstrip("\r\n"))
            stripped = line.strip()
            upper = stripped.upper()

            if upper == "CEND":
                if pending is not None:
                    yield _card(pending, continuations, start_line)
                pending, continuations = None, []
                previous_line = None
                mode = "case"
                continue

            if upper == "BEGIN BULK":
                if pending is not None:
                    yield _card(pending, continuations, start_line)
                pending, continuations = None, []
                previous_line = None
                mode = "bulk"
                continue

            if upper.startswith("ENDDATA"):
                if pending is not None:
                    yield _card(pending, continuations, start_line)
                pending, continuations = None, []
                previous_line = None
                mode = "after"
                continue

            if mode != "bulk" or _is_comment(line):
                continue

            if pending is not None and _is_continuation(line, pending, previous_line):
                continuations.append(line)
                previous_line = line
                continue

            if pending is not None:
                yield _card(pending, continuations, start_line)

            pending = line
            continuations = []
            previous_line = line
            start_line = number

    if pending is not None:
        yield _card(pending, continuations, start_line)


def read_case_control(path: str | Path, encoding: str = "gb18030"):
    control: list[str] = []
    executive: list[str] = []
    mode = "pre"

    with Path(path).open("r", encoding=encoding, errors="strict", newline=None) as stream:
        for raw in stream:
            line = raw.rstrip("\r\n")
            upper = line.strip().upper()
            if upper == "CEND":
                mode = "case"
                continue
            if upper == "BEGIN BULK":
                mode = "bulk"
                continue
            if mode == "case" and line.strip():
                control.append(line)
            elif mode == "pre" and line.strip():
                executive.append(line)

    return control, executive
