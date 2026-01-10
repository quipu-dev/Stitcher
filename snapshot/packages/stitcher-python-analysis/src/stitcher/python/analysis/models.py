from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Tuple


class ReferenceType(Enum):
    SYMBOL = "symbol"
    IMPORT_PATH = "import_path"


@dataclass
class UsageLocation:
    file_path: Path
    lineno: int
    col_offset: int
    end_lineno: int
    end_col_offset: int
    ref_type: ReferenceType
    target_node_fqn: str

    @property
    def range_tuple(self) -> Tuple[int, int]:
        return (self.lineno, self.col_offset)
