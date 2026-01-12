from dataclasses import dataclass, field
from typing import List
from pathlib import Path


@dataclass
class PumpResult:
    success: bool
    redundant_files: List[Path] = field(default_factory=list)


@dataclass
class CoverageResult:
    path: str
    total_symbols: int
    documented_symbols: int
    missing_symbols: int
    coverage: float
