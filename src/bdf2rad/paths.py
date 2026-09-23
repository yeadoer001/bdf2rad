"""Explicit directory-scoped output authorization; workspace remains the default."""
from dataclasses import dataclass
from pathlib import Path
WORKSPACE = Path(__file__).resolve().parents[2]

@dataclass(frozen=True)
class OutputPolicy:
    external_roots: tuple[Path, ...] = ()

    def check(self, value):
        path = Path(value).resolve()
        roots = (WORKSPACE, *(Path(root).resolve() for root in self.external_roots))
        if not any(path.is_relative_to(root) for root in roots):
            raise ValueError(f'Output must be inside {WORKSPACE} or an explicitly authorized output directory: {path}')
        return path

def writable_path(value, policy=None):
    return (policy or OutputPolicy()).check(value)
