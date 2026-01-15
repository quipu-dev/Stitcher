from pathlib import Path
from typing import Dict, Optional

from stitcher.spec import (
    LockManagerProtocol,
    DocstringIR,
    ModuleDef,
    Fingerprint,
    URIGeneratorProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol
from stitcher.workspace import Workspace
from stitcher.common.transaction import TransactionManager


class LockSession:
    """
    Manages the state of stitcher.lock files during a transaction.
    Acts as a Single Source of Truth for lock updates, buffering changes in memory
    and committing them to the TransactionManager at the end of a run.
    """

    def __init__(
        self,
        lock_manager: LockManagerProtocol,
        doc_manager: DocumentManagerProtocol,
        workspace: Workspace,
        root_path: Path,
        uri_generator: URIGeneratorProtocol,
    ):
        self.lock_manager = lock_manager
        self.doc_manager = doc_manager
        self.workspace = workspace
        self.root_path = root_path
        self.uri_generator = uri_generator

        # Buffer: Package Root -> {SURI -> Fingerprint}
        # We load locks lazily (on first access to a package).
        self._locks: Dict[Path, Dict[str, Fingerprint]] = {}

    def _get_lock_data(self, abs_file_path: Path) -> Dict[str, Fingerprint]:
        """
        Retrieves the lock data for the package owning the given file.
        Loads from disk if not already in memory buffer.
        """
        pkg_root = self.workspace.find_owning_package(abs_file_path)
        if pkg_root not in self._locks:
            self._locks[pkg_root] = self.lock_manager.load(pkg_root)
        return self._locks[pkg_root]

    def _get_suri(self, module: ModuleDef, fqn: str) -> str:
        abs_path = self.root_path / module.file_path
        ws_rel = self.workspace.to_workspace_relative(abs_path)
        return self.uri_generator.generate_symbol_uri(ws_rel, fqn)

    def record_fresh_state(
        self,
        module: ModuleDef,
        fqn: str,
        doc_ir: Optional[DocstringIR] = None,
        code_fingerprint: Optional[Fingerprint] = None,
    ):
        """
        Record that the current Code (represented by code_fingerprint) and/or
        current YAML (represented by doc_ir) are the new baseline.

        Used by:
        - Pump (Overwrite/Hydrate): Updates both code and doc baselines.
        - Check (Reconcile): Updates both code and doc baselines.
        """
        if not module.file_path:
            return

        abs_path = self.root_path / module.file_path
        lock_data = self._get_lock_data(abs_path)
        suri = self._get_suri(module, fqn)

        # Get existing fingerprint or create new
        fp = lock_data.get(suri) or Fingerprint()

        # 1. Update Code Baseline
        if code_fingerprint:
            if "current_code_structure_hash" in code_fingerprint:
                fp["baseline_code_structure_hash"] = code_fingerprint[
                    "current_code_structure_hash"
                ]
            if "current_code_signature_text" in code_fingerprint:
                fp["baseline_code_signature_text"] = code_fingerprint[
                    "current_code_signature_text"
                ]

        # 2. Update Doc Baseline
        if doc_ir:
            yaml_hash = self.doc_manager.compute_ir_hash(doc_ir)
            fp["baseline_yaml_content_hash"] = yaml_hash

        lock_data[suri] = fp

    def record_relink(self, module: ModuleDef, fqn: str, code_fingerprint: Fingerprint):
        """
        Update ONLY the code hash baseline to match current code, keeping doc hash as is.
        Used by Check (Relink) to acknowledge a code change without updating docs.
        """
        self.record_fresh_state(
            module, fqn, doc_ir=None, code_fingerprint=code_fingerprint
        )

    def record_purge(self, module: ModuleDef, fqn: str):
        """
        Remove the entry from lock file.
        """
        if not module.file_path:
            return

        abs_path = self.root_path / module.file_path
        lock_data = self._get_lock_data(abs_path)
        suri = self._get_suri(module, fqn)

        if suri in lock_data:
            del lock_data[suri]

    def commit_to_transaction(self, tm: TransactionManager):
        """
        Serialize all modified lock files and register write operations with the TransactionManager.
        This ensures that lock updates respect the global dry-run setting.
        """
        for pkg_root, lock_data in self._locks.items():
            content = self.lock_manager.serialize(lock_data)
            lock_path = pkg_root / "stitcher.lock"
            try:
                # Ensure we write relative to root_path for TransactionManager
                rel_path = lock_path.relative_to(self.root_path)
                tm.add_write(str(rel_path), content)
            except ValueError:
                # Fallback/Safety: Should not happen if pkg_root is inside root_path
                pass

    def clear(self):
        """
        Clears the internal buffer. Should be called at the end of a command execution
        to prevent stale state from polluting subsequent runs.
        """
        self._locks.clear()
