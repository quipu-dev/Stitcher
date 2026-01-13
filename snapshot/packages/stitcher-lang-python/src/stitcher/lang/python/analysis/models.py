from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Tuple, Optional


class ReferenceType(Enum):
    SYMBOL = "symbol"
    IMPORT_PATH = "import_path"
    SIDECAR_ID = "json_suri"      # Reference in Signature (.json) via SURI
    SIDECAR_NAME = "yaml_fqn"     # Reference in Doc (.yaml) via FQN


@dataclass
class UsageLocation:
    file_path: Path
    lineno: int
    col_offset: int
    end_lineno: int
    end_col_offset: int
    ref_type: ReferenceType
    target_node_fqn: Optional[str]
    target_node_id: Optional[str] = None

    @property
    def range_tuple(self) -> Tuple[int, int]:
        return (self.lineno, self.col_offset)
