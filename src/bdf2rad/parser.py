"""Streaming lexical BDF reader. Unknown cards remain first-class AST records."""
from dataclasses import dataclass, field
from pathlib import Path
import math
import re

from .diagnostics import BDFError, Diagnostic, SourceLocation


@dataclass(frozen=True, slots=True)
class Card:
    name: str
    fields: tuple[str, ...]
    source: SourceLocation
    raw: tuple[str, ...]
    line_numbers: tuple[int, ...]
    format: str
    continuation: tuple[str, ...] = ()
    original_name: str = ""


@dataclass(slots=True)
class IncludeEdge:
    source: SourceLocation
    target: str


def nastran_float(value: str) -> float:
    text = value.strip().upper().replace("D", "E")
    if "E" not in text:
        text = re.sub(r"(?<=[\d.])([+-]\d+)$", r"E\1", text)
    result = float(text)
    if not math.isfinite(result):
        raise ValueError(f"Non-finite BDF number: {value}")
    return result


def _commentless(raw):
    quote = None
    for i, ch in enumerate(raw):
        if ch in "\"'":
            if quote == ch:
                quote = None
            elif quote is None:
                quote = ch
        elif ch == "$" and quote is None:
            return raw[:i]
    return raw


def _split(line, large=False):
    if "," in line:
        parts = line.split(",")
        head = parts[0].strip()
        values = [p.strip() for p in parts[1:]]
        label = ""
        if len(values) >= 9:
            if len(values) > 9:
                raise ValueError("Free field has more than eight data fields and a continuation field")
            label = values.pop()
            if label and not label.startswith(("+", "*")):
                raise ValueError("Ninth free field must be a continuation identifier")
        return head, values, label, "free"
    head = line[:8].strip()
    large = large or head.endswith("*") or head.startswith("*")
    width = 16 if large else 8
    padded = line[:72].ljust(72)
    return head, [padded[i:i+width].strip() for i in range(8, 72, width)], line[72:80].strip(), "large" if large else "small"


class BDFParser:
    def __init__(self, *, encoding="utf-8-sig", max_include_depth=100):
        self.encoding = encoding
        self.max_include_depth = max_include_depth
        self.include_tree: list[IncludeEdge] = []
        self.control_lines: list[tuple[SourceLocation, str]] = []

    def parse(self, filename):
        self.include_tree.clear()
        self.control_lines.clear()
        yield from self._read(Path(filename).resolve(), ())

    def _read(self, path, ancestors):
        if path in ancestors:
            raise BDFError(Diagnostic("INCLUDE_CYCLE", " -> ".join(map(str, (*ancestors, path))), SourceLocation(str(path), 1)))
        if len(ancestors) >= self.max_include_depth:
            raise BDFError(Diagnostic("INCLUDE_DEPTH", "INCLUDE depth limit exceeded", SourceLocation(str(path), 1)))
        pending = None
        expected = ""
        include_lines = []
        include_start = 0
        in_control = False

        def finish():
            return Card(pending[0].upper().rstrip("*"), tuple(pending[1]),
                        SourceLocation(str(path), pending[3][0]), tuple(pending[2]),
                        tuple(pending[3]), pending[4], tuple(pending[5]), pending[0])

        try:
            stream = path.open(encoding=self.encoding, errors="strict")
        except OSError as exc:
            raise BDFError(Diagnostic("INCLUDE_IO", str(exc), SourceLocation(str(path), 1))) from exc
        with stream:
            for number, raw in enumerate(stream, 1):
                raw = raw.rstrip("\r\n")
                line = _commentless(raw).rstrip()
                if not line.strip():
                    continue
                loc = SourceLocation(str(path), number)
                upper = line.strip().upper()
                if include_lines or re.match(r"^INCLUDE\s", upper):
                    if not include_lines:
                        if expected:
                            raise BDFError(Diagnostic("MISSING_CONTINUATION", expected, loc))
                        if pending:
                            yield finish()
                            pending = None
                        include_start = number
                    include_lines.append(line.strip())
                    joined = "".join(include_lines)
                    match = re.fullmatch(r"INCLUDE\s+(['\"])(.*?)\1\s*", joined, re.IGNORECASE)
                    if not match:
                        if len(include_lines) > 32:
                            raise BDFError(Diagnostic("INCLUDE_SYNTAX", joined, loc))
                        continue
                    target = (path.parent / match[2]).resolve()
                    self.include_tree.append(IncludeEdge(SourceLocation(str(path), include_start), str(target)))
                    include_lines = []
                    yield from self._read(target, (*ancestors, path))
                    continue
                if upper.startswith(("NASTRAN ", "ID,", "SOL ", "SOL\t", "CEND", "BEGIN BULK", "BEGIN,BULK")) or upper[:8].strip() == "ENDDATA":
                    if expected:
                        raise BDFError(Diagnostic("MISSING_CONTINUATION", expected, loc))
                    if pending:
                        yield finish()
                        pending = None
                    self.control_lines.append((loc, raw))
                    if upper.startswith(("NASTRAN ", "ID,", "SOL ", "SOL\t", "CEND")):
                        in_control = True
                    elif upper.startswith("BEGIN"):
                        in_control = False
                    else:
                        # Do not hide non-comment data after ENDDATA.
                        for tail_no, tail in enumerate(stream, number + 1):
                            if _commentless(tail).strip():
                                raise BDFError(Diagnostic("DATA_AFTER_ENDDATA", tail.rstrip(), SourceLocation(str(path), tail_no)))
                        return
                    continue
                if in_control:
                    self.control_lines.append((loc, raw))
                    continue
                try:
                    head, values, label, fmt = _split(line, bool(pending and pending[4] == "large"))
                except ValueError as exc:
                    raise BDFError(Diagnostic("FIELD_SYNTAX", str(exc), loc, raw=(raw,))) from exc
                continuation = not head or head.startswith(("+", "*"))
                if continuation:
                    if pending is None:
                        raise BDFError(Diagnostic("ORPHAN_CONTINUATION", head, loc, raw=(raw,)))
                    # Simcenter/Nastran exporters use both '+' and '*' for a
                    # continuation marker. They are equivalent when the
                    # previous field explicitly requested a continuation.
                    marker_equivalent = {expected, head} <= {"+", "*"}
                    if expected and head != expected and not marker_equivalent:
                        raise BDFError(Diagnostic("CONTINUATION_MISMATCH", f"Expected {expected!r}, got {head!r}", loc))
                    if fmt != pending[4]:
                        raise BDFError(Diagnostic("MIXED_FIELD_FORMAT", "Mixed continuation formats require explicit handling", loc))
                    # Free-field continuation starts at the next 8-field boundary.
                    if fmt == "free":
                        pending[1].extend([""] * ((-len(pending[1])) % 8))
                    pending[1].extend(values)
                    pending[2].append(raw)
                    pending[3].append(number)
                    pending[5].append(head)
                else:
                    if expected:
                        raise BDFError(Diagnostic("MISSING_CONTINUATION", expected, loc))
                    if pending:
                        yield finish()
                    # Re-split a new card without the preceding card's large-field mode.
                    head, values, label, fmt = _split(line)
                    pending = [head, values, [raw], [number], fmt, []]
                expected = label
        if include_lines:
            raise BDFError(Diagnostic("INCLUDE_SYNTAX", "Unclosed or malformed INCLUDE", SourceLocation(str(path), include_start), raw=tuple(include_lines)))
        if expected:
            raise BDFError(Diagnostic("MISSING_CONTINUATION", expected, SourceLocation(str(path), pending[3][-1])))
        if pending:
            yield finish()
