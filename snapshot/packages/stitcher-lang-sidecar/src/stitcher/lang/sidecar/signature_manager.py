import json
import logging
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Dict, Set

from stitcher.spec import Fingerprint, InvalidFingerprintKeyError
from stitcher.workspace import Workspace, find_package_root
from stitcher.lang.python.uri import SURIGenerator

log = logging.getLogger(__name__)

LOCK_FILE_VERSION = "1.0"
LOCK_FILE_NAME = "stitcher.lock"
LEGACY_SIG_DIR = ".stitcher/signatures"


class SignatureManager:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        # Cache: lock_file_path -> {suri: Fingerprint}
        self._fingerprints_cache: Dict[Path, Dict[str, Fingerprint]] = {}
        self._dirty_locks: Set[Path] = set()
        self._migration_done = False
        self._legacy_dir_to_delete: Path | None = None

    def _get_lock_path(self, package_root: Path) -> Path:
        return package_root / LOCK_FILE_NAME

    def _ensure_loaded(self, abs_file_path: Path) -> Path:
        package_root = find_package_root(abs_file_path)
        if not package_root:
            raise FileNotFoundError(f"Could not find package root for: {abs_file_path}")

        lock_path = self._get_lock_path(package_root)
        if lock_path in self._fingerprints_cache:
            return lock_path

        if not self._migration_done:
            self._run_migration_if_needed()

        if lock_path in self._fingerprints_cache:
            return lock_path

        if lock_path.exists():
            log.debug(f"Loading lock file: {lock_path}")
            try:
                with lock_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("version") == LOCK_FILE_VERSION and "fingerprints" in data:
                    self._fingerprints_cache[lock_path] = {
                        suri: Fingerprint.from_dict(fp_data)
                        for suri, fp_data in data["fingerprints"].items()
                    }
                else:
                    self._fingerprints_cache[lock_path] = {}
            except (json.JSONDecodeError, OSError):
                self._fingerprints_cache[lock_path] = {}
        else:
            self._fingerprints_cache[lock_path] = {}

        return lock_path

    def _run_migration_if_needed(self):
        legacy_dir = self.workspace.root_path / LEGACY_SIG_DIR
        if not legacy_dir.is_dir():
            self._migration_done = True
            return

        log.info("Legacy '.stitcher/signatures' directory found. Starting migration...")
        fingerprints_by_pkg: Dict[Path, Dict[str, Fingerprint]] = defaultdict(dict)

        for sig_file in legacy_dir.rglob("*.json"):
            try:
                rel_source_path = str(sig_file.relative_to(legacy_dir))[:-5]
                abs_source_path = self.workspace.root_path / rel_source_path
                package_root = find_package_root(abs_source_path)
                if not package_root:
                    continue

                with sig_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)

                for key, fp_data in data.items():
                    suri = (
                        key
                        if key.startswith("py://")
                        else SURIGenerator.for_symbol(rel_source_path, key)
                    )
                    fingerprints_by_pkg[package_root][suri] = Fingerprint.from_dict(
                        fp_data
                    )
            except (json.JSONDecodeError, InvalidFingerprintKeyError, ValueError):
                continue

        for pkg_root, fingerprints in fingerprints_by_pkg.items():
            lock_path = self._get_lock_path(pkg_root)
            self._fingerprints_cache[lock_path] = fingerprints
            self._dirty_locks.add(lock_path)

        self._migration_done = True
        self._legacy_dir_to_delete = legacy_dir

    def load_composite_hashes(self, file_path_str: str) -> Dict[str, Fingerprint]:
        abs_file_path = (self.workspace.root_path / file_path_str).resolve()
        lock_path = self._ensure_loaded(abs_file_path)

        workspace_rel_path = self.workspace.get_suri_path(abs_file_path)
        prefix = f"py://{workspace_rel_path}"
        all_lock_fps = self._fingerprints_cache.get(lock_path, {})
        file_fingerprints: Dict[str, Fingerprint] = {}

        for suri, fp in all_lock_fps.items():
            if suri.startswith(prefix):
                _, fragment = SURIGenerator.parse(suri)
                if fragment:
                    file_fingerprints[fragment] = fp
        return file_fingerprints

    def save_composite_hashes(
        self, file_path_str: str, hashes: Dict[str, Fingerprint]
    ) -> None:
        abs_file_path = (self.workspace.root_path / file_path_str).resolve()
        lock_path = self._ensure_loaded(abs_file_path)
        self._dirty_locks.add(lock_path)
        lock_cache = self._fingerprints_cache.setdefault(lock_path, {})

        workspace_rel_path = self.workspace.get_suri_path(abs_file_path)
        updated_suris = {
            SURIGenerator.for_symbol(workspace_rel_path, fragment)
            for fragment in hashes
        }

        prefix = f"py://{workspace_rel_path}"
        stale_suris = [
            suri
            for suri in lock_cache
            if suri.startswith(prefix) and suri not in updated_suris
        ]
        for suri in stale_suris:
            del lock_cache[suri]

        for fragment, fp in hashes.items():
            suri = SURIGenerator.for_symbol(workspace_rel_path, fragment)
            lock_cache[suri] = fp

    def flush(self) -> None:
        if not self._dirty_locks:
            return

        log.debug(f"Flushing {len(self._dirty_locks)} dirty lock files.")
        for lock_path in self._dirty_locks:
            fingerprints = self._fingerprints_cache.get(lock_path, {})
            if not fingerprints:
                if lock_path.exists():
                    lock_path.unlink()
                continue

            lock_data = {
                "version": LOCK_FILE_VERSION,
                "fingerprints": {
                    suri: fp.to_dict() for suri, fp in sorted(fingerprints.items())
                },
            }
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            with lock_path.open("w", encoding="utf-8") as f:
                json.dump(lock_data, f, indent=2)
                f.write("\n")

        self._dirty_locks.clear()

        if self._legacy_dir_to_delete:
            log.info(
                "Migration successful. "
                f"Deleting legacy signature directory: {self._legacy_dir_to_delete}"
            )
            shutil.rmtree(self._legacy_dir_to_delete)
            self._legacy_dir_to_delete = None

    def get_signature_path(self, file_path: str) -> Path:
        abs_file_path = (self.workspace.root_path / file_path).resolve()
        package_root = find_package_root(abs_file_path)
        if not package_root:
            raise FileNotFoundError(f"Cannot find package root for {file_path}")
        return self._get_lock_path(package_root)
