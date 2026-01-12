from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class RefactorIntent:
    pass


# --- Symbol-level Intents ---


@dataclass(frozen=True)
class RenameIntent(RefactorIntent):
    old_fqn: str
    new_fqn: str


# --- Filesystem-level Intents ---


@dataclass(frozen=True)
class FileSystemIntent(RefactorIntent):
    pass


@dataclass(frozen=True)
class MoveFileIntent(FileSystemIntent):
    src_path: Path
    dest_path: Path


@dataclass(frozen=True)
class DeleteFileIntent(FileSystemIntent):
    path: Path


@dataclass(frozen=True)
class DeleteDirectoryIntent(FileSystemIntent):
    path: Path


@dataclass(frozen=True)
class ScaffoldIntent(FileSystemIntent):
    path: Path
    content: str = ""


# --- Sidecar-level Intents ---


@dataclass(frozen=True)
class SidecarUpdateIntent(RefactorIntent):
    sidecar_path: Path
    module_fqn: Optional[str]
    old_fqn: str
    new_fqn: str
    # New fields for SURI updates
    old_file_path: Optional[str] = None
    new_file_path: Optional[str] = None
