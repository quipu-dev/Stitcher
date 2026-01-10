import subprocess
import hashlib
import logging
from pathlib import Path
from typing import List, Protocol, Tuple, Set

from .store import IndexStore
from .types import SymbolRecord, ReferenceRecord

log = logging.getLogger(__name__)


class LanguageAdapterProtocol(Protocol):
    """Protocol for language-specific parsers."""

    def parse(
        self, file_path: Path, content: str
    ) -> Tuple[List[SymbolRecord], List[ReferenceRecord]]: ...


class WorkspaceScanner:
    """Orchestrates the four-stage incremental scan of the workspace."""

    def __init__(
        self,
        root_path: Path,
        store: IndexStore,
        language_adapter: LanguageAdapterProtocol,
    ):
        self.root_path = root_path
        self.store = store
        self.adapter = language_adapter

    def _discover_files(self) -> Set[Path]:
        """Stage 1: Discover all relevant files in the workspace."""
        # Git-based discovery (preferred)
        try:
            result = subprocess.run(
                [
                    "git",
                    "ls-files",
                    "--cached",
                    "--others",
                    "--exclude-standard",
                ],
                cwd=self.root_path,
                check=True,
                capture_output=True,
                text=True,
            )
            # git ls-files should only return files, but we check .is_file()
            # to be robust against submodules which appear as directories.
            files = {
                p
                for p in (
                    self.root_path / path_str
                    for path_str in result.stdout.strip().splitlines()
                )
                if p.is_file()
            }
            return files
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fallback to filesystem scan, respecting .gitignore is complex,
            # so we do a simple file-only scan for now.
            return {p for p in self.root_path.rglob("*") if p.is_file()}

    def scan(self) -> None:
        """Runs the complete incremental scanning pipeline."""
        # Stage 1: Discovery
        workspace_paths = self._discover_files()
        workspace_rel_paths = {
            str(p.relative_to(self.root_path))
            for p in workspace_paths
            if p.is_file()  # Safeguard
        }

        # Handle deletions
        stored_paths = self.store.get_all_file_paths()
        deleted_paths = stored_paths - workspace_rel_paths
        if deleted_paths:
            self.store.prune_files(deleted_paths)

        confirmed_dirty_files: List[Tuple[Path, str, float, int]] = []

        for file_path in workspace_paths:
            if not file_path.is_file():
                log.debug(f"Skipping non-file path from discovery: {file_path}")
                continue

            rel_path_str = str(file_path.relative_to(self.root_path))
            stat = file_path.stat()
            mtime, size = stat.st_mtime, stat.st_size

            # Stage 2: Stat Check
            file_rec = self.store.get_file_by_path(rel_path_str)
            if (
                file_rec
                and file_rec.last_mtime == mtime
                and file_rec.last_size == size
            ):
                continue

            # Stage 3: Hash Check
            content_bytes = file_path.read_bytes()
            content_hash = hashlib.sha256(content_bytes).hexdigest()

            if file_rec and file_rec.content_hash == content_hash:
                # Content is identical, just update stat to avoid re-hashing next time
                self.store.sync_file(rel_path_str, content_hash, mtime, size)
                continue

            confirmed_dirty_files.append((file_path, content_hash, mtime, size))

        # Stage 4: Parsing
        for file_path, content_hash, mtime, size in confirmed_dirty_files:
            rel_path_str = str(file_path.relative_to(self.root_path))
            file_id, _ = self.store.sync_file(rel_path_str, content_hash, mtime, size)

            content_str = file_path.read_text("utf-8")
            symbols, references = self.adapter.parse(file_path, content_str)
            self.store.update_analysis(file_id, symbols, references)