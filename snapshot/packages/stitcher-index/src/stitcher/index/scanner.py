import os
import hashlib
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple

from .store import IndexStore
from .types import FileRecord, SymbolRecord, ReferenceRecord
from .protocols import LanguageAdapter

log = logging.getLogger(__name__)


class WorkspaceScanner:
    def __init__(self, root_path: Path, store: IndexStore):
        self.root_path = root_path
        self.store = store
        self.adapters: Dict[str, LanguageAdapter] = {}

    def register_adapter(self, extension: str, adapter: LanguageAdapter):
        """Register a language adapter for a specific file extension (e.g., '.py')."""
        self.adapters[extension] = adapter

    def scan(self) -> Dict[str, int]:
        """
        Execute the 4-phase incremental scan pipeline.

        Returns:
            Dict with stats: {'added': int, 'updated': int, 'deleted': int, 'skipped': int}
        """
        stats = {"added": 0, "updated": 0, "deleted": 0, "skipped": 0}

        # --- Phase 1: Discovery ---
        discovered_paths = self._discover_files()
        
        # Load DB state
        # Map: relative_path_str -> FileRecord
        known_files: Dict[str, FileRecord] = {
            r.path: r for r in self.store.get_all_files_metadata()
        }

        # --- Handle Deletions ---
        # If in DB but not on disk (and discovery list), delete it.
        # Note: discovered_paths contains relative strings
        for known_path, record in known_files.items():
            if known_path not in discovered_paths:
                self.store.delete_file(record.id)
                stats["deleted"] += 1

        # --- Phase 2 & 3 & 4: Check and Update ---
        for rel_path_str in discovered_paths:
            abs_path = self.root_path / rel_path_str
            
            try:
                file_stat = abs_path.stat()
            except FileNotFoundError:
                # Race condition: file deleted during scan
                continue

            current_mtime = file_stat.st_mtime
            current_size = file_stat.st_size
            
            record = known_files.get(rel_path_str)

            # --- Phase 2: Stat Check ---
            # If metadata matches and it was successfully indexed, skip.
            if (
                record
                and record.indexing_status == 1
                and record.last_mtime == current_mtime
                and record.last_size == current_size
            ):
                stats["skipped"] += 1
                continue

            # --- Phase 3: Hash Check ---
            try:
                # Always read as bytes first to handle binary files and SHA256
                content_bytes = abs_path.read_bytes()
            except (OSError, PermissionError) as e:
                log.warning(f"Could not read file {rel_path_str}: {e}")
                continue

            current_hash = hashlib.sha256(content_bytes).hexdigest()

            if record and record.content_hash == current_hash:
                # Content hasn't changed, but mtime/size did (or status was 0).
                # Just update metadata, no need to re-parse.
                self.store.sync_file(
                    rel_path_str, current_hash, current_mtime, current_size
                )
                # If it was dirty (status=0) but hash matches, it means we failed to parse last time
                # or it was interrupted. If hash matches old hash, we technically don't need to re-parse
                # IF the old parse was successful. But if status=0, we should retry parse.
                if record.indexing_status == 1:
                    stats["skipped"] += 1
                    continue
                # If status=0, fall through to Phase 4 to retry parsing.

            # Sync file (Insert or Update)
            # This updates content_hash, mtime, size and sets status=0 (Dirty)
            file_id, is_new_content = self.store.sync_file(
                rel_path_str, current_hash, current_mtime, current_size
            )
            
            if is_new_content:
                if record:
                    stats["updated"] += 1
                else:
                    stats["added"] += 1

            # --- Phase 4: Parsing (Semantic Extraction) ---
            self._process_file_content(file_id, abs_path, content_bytes)

        return stats

    def _discover_files(self) -> Set[str]:
        """
        Phase 1: Discovery.
        Returns a set of file paths relative to root_path.
        """
        # Strategy 1: Git
        if (self.root_path / ".git").exists():
            try:
                # ls-files --cached (tracked) --others (untracked) --exclude-standard (respect .gitignore)
                result = subprocess.run(
                    ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                    cwd=self.root_path,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                paths = set(
                    line.strip() for line in result.stdout.splitlines() if line.strip()
                )
                # Filter out directories (git ls-files shouldn't list dirs usually, but check)
                return paths
            except subprocess.CalledProcessError:
                log.warning("Git discovery failed, falling back to OS walk.")
        
        # Strategy 2: Fallback OS Walk
        paths = set()
        for root, dirs, files in os.walk(self.root_path):
            # Skip hidden dirs
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            
            for file in files:
                if file.startswith("."):
                    continue
                abs_path = Path(root) / file
                rel_path = abs_path.relative_to(self.root_path).as_posix()
                paths.add(rel_path)
        return paths

    def _process_file_content(self, file_id: int, abs_path: Path, content_bytes: bytes):
        """Phase 4: Parse content using adapters."""
        # 1. Decode
        try:
            # We assume source code is UTF-8.
            text_content = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            # Binary file or non-utf8. We track the file (Phase 3) but don't index symbols.
            # We clear existing symbols for this file to be safe (it might have become binary).
            self.store.update_analysis(file_id, [], [])
            return

        # 2. Find Adapter
        ext = abs_path.suffix
        adapter = self.adapters.get(ext)
        
        if not adapter:
            # No adapter for this type (e.g. .txt, .md if not configured).
            # Mark as indexed (empty symbols) to avoid re-scanning.
            self.store.update_analysis(file_id, [], [])
            return

        # 3. Parse
        try:
            symbols, references = adapter.parse(abs_path, text_content)
            self.store.update_analysis(file_id, symbols, references)
        except Exception as e:
            log.error(f"Failed to parse {abs_path}: {e}")
            # We leave it as dirty (status=0 from sync_file) or we record error?
            # Ideally we record error in 'indexing_errors' table and mark as indexed (or partial?)
            # For now, let's leave it dirty so it retries next time? 
            # Or mark as indexed with 0 symbols to prevent infinite retry loops on syntax errors?
            # Better: Mark as indexed (processed) but log error. A syntax error shouldn't block the pipeline forever.
            # But the requirement is "Robustness".
            # Let's clear symbols and mark indexed to stop loop.
            self.store.update_analysis(file_id, [], [])