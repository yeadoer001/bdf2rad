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
    s = s.replace('D','E').replace('d','e')
    if 'E' not in s.upper():
        for i in range(1, len(s)):
            if s[i] in '+-' and s[i-1].isdigit():
                s = s[:i] + 'E' + s[i:]
                break
    return float(s)

def _comment(line: str) -> bool:
    s = line.strip()
    return not s or s.startswith('$') or s.startswith('#')

def _name(line: str) -> str:
    if ',' in line[:80]:
        return line.split(',',1)[0].strip().upper().rstrip('*')
    return line[:8].strip().upper().rstrip('*')

def _fixed(line: str, large: bool) -> list[str]:
    if large:
        body = line[8:]
        return [body[i:i+16].strip().rstrip('+') for i in range(0, len(body), 16)]
    return [line[i:i+8].strip().rstrip('+') for i in range(0, len(line), 8)]

def _free(line: str) -> list[str]:
    return [x.strip() for x in line.split(',')]

def _card(first: str, cont: list[str], start: int) -> Card:
    large = first[8:9] == '*' or first[:8].rstrip().endswith('*')
    if ',' in first[:80]:
        fields = _free(first)
        for ln in cont:
            fields.extend(_free(ln))
    else:
        base = _fixed(first, large)
        fields = [base[0]] + (base[1:] if not large else base)
        for ln in cont:
            b = _fixed(ln, large)
            fields.extend(b[1:] if not large else b)
    fields[0] = _name(first)
    return Card(fields[0], fields, start, tuple([first] + cont))

def iter_cards(path: str|Path, encoding: str='gb18030'):
    pending = None
    raw: list[str] = []
    line0 = 0
    mode = 'pre'
    with Path(path).open('r', encoding=encoding, errors='strict', newline=None) as fh:
        for n, ln in enumerate(fh, 1):
            ln = ln.rstrip('\r\n')
            u = ln.strip().upper()
            if u == 'BEGIN BULK':
                mode = 'bulk'; continue
            if u == 'CEND':
                mode = 'case'; continue
            if u.startswith('ENDDATA'):
                if pending is not None:
                    yield _card(raw[0], raw[1:], line0)
                pending = None; raw=[]; mode='after'; continue
            if mode != 'bulk' or _comment(ln):
                continue
            cont = ln.startswith('+') or ln.startswith('*')
            if cont and pending is not None:
                raw.append(ln); continue
            if pending is not None:
                yield _card(raw[0], raw[1:], line0)
            pending = ln; raw=[ln]; line0=n
    if pending is not None:
        yield _card(raw[0], raw[1:], line0)

def read_case_control(path: str|Path, encoding: str='gb18030'):
    control=[]; executive=[]; mode='pre'
    with Path(path).open('r', encoding=encoding, errors='strict') as fh:
        for raw in fh:
            ln=raw.rstrip('\r\n'); u=ln.strip().upper()
            if u == 'CEND': mode='case'; continue
            if u == 'BEGIN BULK': mode='bulk'; continue
            if mode=='case' and ln.strip(): control.append(ln)
            elif mode=='pre' and ln.strip(): executive.append(ln)
    return control, executive
