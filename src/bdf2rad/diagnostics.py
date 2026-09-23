from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class SourceLocation:
    file: str
    line: int


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    message: str
    source: SourceLocation | None = None
    severity: str = "ERROR"
    card: str = ""
    raw: tuple[str, ...] = ()

    def to_dict(self):
        return asdict(self)


class BDFError(ValueError):
    def __init__(self, diagnostic: Diagnostic):
        self.diagnostic = diagnostic
        source = diagnostic.source
        prefix = f"{source.file}:{source.line}: " if source else ""
        super().__init__(f"{prefix}{diagnostic.code}: {diagnostic.message}")
