from dataclasses import dataclass
from pathlib import Path


@dataclass
class SymbolNode:
    fqn: str
    kind: str
    path: Path