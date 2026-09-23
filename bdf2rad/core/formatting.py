from __future__ import annotations
from typing import Iterable

def fi(x: int | float | str, width: int = 10) -> str:
    return f'{int(float(x)):>{width}d}'

def fs(x: int | float | str, width: int = 20, prec: int = 12) -> str:
    return f'{float(x):>{width}.{prec}E}'

def chunked(seq: Iterable[int], n: int):
    seq = list(seq)
    for i in range(0, len(seq), n):
        yield seq[i:i+n]

def node_group_lines(ids: Iterable[int], width: int = 10) -> list[str]:
    out = []
    for chunk in chunked(sorted(dict.fromkeys(int(x) for x in ids)), 10):
        out.append(''.join(fi(x, width) for x in chunk))
    return out

def dof6(comp: str | int) -> str:
    digits = {int(c) for c in str(comp) if c.isdigit() and '1' <= c <= '6'}
    return ''.join('1' if i in digits else '0' for i in range(1, 7))

def bdf_velocity_to_rad_mm_ms(v: float) -> float:
    # Source file uses mm/s; user-provided working unit in the runnable seed is kg-mm-ms.
    return float(v) / 1000.0

def bdf_accel_to_rad_mm_ms2(a: float) -> float:
    return float(a) / 1_000_000.0

def bdf_time_to_rad_ms(t: float) -> float:
    return float(t) * 1000.0
