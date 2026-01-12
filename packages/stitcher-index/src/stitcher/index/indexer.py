import hashlib
import logging
from pathlib import Path
from typing import Dict, Set, Any

from stitcher.spec import IndexStoreProtocol
from stitcher.spec.index import FileRecord
from stitcher.spec.registry import LanguageAdapter

log = logging.getLogger(__name__)


class FileIndexer:
    def __init__(self, root_path: Path, store: IndexStoreProtocol):
        self.root_path = root_path
        self.store = store
        self.adapters: Dict[str, LanguageAdapter] = {}

    def register_adapter(self, extension: str, adapter: LanguageAdapter):
        self.adapters[extension] = adapter

    def index_files(self, discovered_paths: Set[str]) -> Dict[str, Any]:
        stats: Dict[str, Any] = {
            "added": 0,
            "updated": 0,
            "deleted": 0,
            "skipped": 0,
            "errors": 0,
            "error_details": [],
            "modified_paths": set(),
        }

        # Load DB state
        known_files: Dict[str, FileRecord] = {
            r.path: r for r in self.store.get_all_files_metadata()
        }

        # --- Handle Deletions ---
        for known_path, record in known_files.items():
            if known_path not in discovered_paths:
                self.store.delete_file(record.id)
                stats["deleted"] += 1

        # --- Check and Update ---
        for rel_path_str in discovered_paths:
            abs_path = self.root_path / rel_path_str
            try:
                file_stat = abs_path.stat()
            except FileNotFoundError:
                continue

            current_mtime = file_stat.st_mtime
            current_size = file_stat.st_size
            record = known_files.get(rel_path_str)

            if (
                record
                and record.indexing_status == 1
                and record.last_mtime == current_mtime
                and record.last_size == current_size
            ):
                stats["skipped"] += 1
                continue

            try:
                content_bytes = abs_path.read_bytes()
            except (OSError, PermissionError) as e:
                log.warning(f"Could not read file {rel_path_str}: {e}")
                continue

            current_hash = hashlib.sha256(content_bytes).hexdigest()

            if record and record.content_hash == current_hash:
                self.store.sync_file(
                    rel_path_str, current_hash, current_mtime, current_size
                )
                if record.indexing_status == 1:
                    stats["skipped"] += 1
                    continue

            file_id, is_new_content = self.store.sync_file(
                rel_path_str, current_hash, current_mtime, current_size
            )
            if is_new_content:
                stats["updated" if record else "added"] += 1
                stats["modified_paths"].add(rel_path_str)

            try:
                self._process_file_content(file_id, abs_path, content_bytes)
            except Exception as e:
                stats["errors"] += 1
                stats["error_details"].append((str(abs_path), str(e)))

        # --- Linking ---
        self.store.resolve_missing_links()
        return stats

    def _process_file_content(
        self, file_id: int, abs_path: Path, content_bytes: bytes
    ) -> None:
        try:
            text_content = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            self.store.update_analysis(file_id, [], [])
            return  # Not a parser error, just binary file

        ext = abs_path.suffix
        adapter = self.adapters.get(ext)
        if not adapter:
            self.store.update_analysis(file_id, [], [])
            return

        # Let exceptions bubble up to be caught by the caller
        symbols, references = adapter.parse(abs_path, text_content)
        self.store.update_analysis(file_id, symbols, references)
