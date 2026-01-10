from dataclasses import dataclass
from typing import Optional


@dataclass
class FileRecord:
    id: int
    path: str
    content_hash: str
    last_mtime: float
    last_size: int
    indexing_status: int


@dataclass
class SymbolRecord:
    id: str
    name: str
    kind: str
    location_start: int
    location_end: int
    file_id: Optional[int] = None  # Optional when inserting if handled by store context
    logical_path: Optional[str] = None
    alias_target_id: Optional[str] = None
    signature_hash: Optional[str] = None


@dataclass
class ReferenceRecord:
    target_id: str
    kind: str
    location_start: int
    location_end: int
    source_file_id: Optional[int] = None  # Optional when inserting
    id: Optional[int] = None  # Database Row ID
