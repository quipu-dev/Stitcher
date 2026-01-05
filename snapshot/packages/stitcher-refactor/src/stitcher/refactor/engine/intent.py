from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class RefactorIntent:
    """Base class for all refactoring intents."""

    pass


# --- Symbol-level Intents ---


@dataclass(frozen=True)
class RenameIntent(RefactorIntent):
    """Intent to rename a symbol and all its usages."""

    old_fqn: str
    new_fqn: str


# --- Filesystem-level Intents ---


@dataclass(frozen=True)
class FileSystemIntent(RefactorIntent):
    """Base class for intents that directly manipulate the filesystem."""

    pass


@dataclass(frozen=True)
class MoveFileIntent(FileSystemIntent):
    """Intent to move a file from a source to a destination."""

    src_path: Path
    dest_path: Path


@dataclass(frozen=True)
class DeleteFileIntent(FileSystemIntent):
    """Intent to delete a file."""

    path: Path


@dataclass(frozen=True)
class DeleteDirectoryIntent(FileSystemIntent):
    """Intent to delete an empty directory."""

    path: Path


@dataclass(frozen=True)
class ScaffoldIntent(FileSystemIntent):
    """Intent to create a file, typically an empty __init__.py."""

    path: Path
    content: str = ""


# --- Sidecar-level Intents ---


@dataclass(frozen=True)
class SidecarUpdateIntent(RefactorIntent):
    """

    Intent to update keys within a sidecar file due to a symbol rename.
    This is a high-level intent that will be processed by a dedicated aggregator.
    """

    sidecar_path: Path
    module_fqn: Optional[str]
    old_fqn: str
    new_fqn: str
