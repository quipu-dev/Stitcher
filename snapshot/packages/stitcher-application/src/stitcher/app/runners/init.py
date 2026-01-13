from typing import List, Dict
from pathlib import Path
from collections import defaultdict

from stitcher.common import bus
from needle.pointer import L
from stitcher.spec import (
    Fingerprint,
    ModuleDef,
    FingerprintStrategyProtocol,
    LockManagerProtocol,
    URIGeneratorProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol
from stitcher.workspace import Workspace


class InitRunner:
    def __init__(
        self,
        root_path: Path,
        workspace: Workspace,
        doc_manager: DocumentManagerProtocol,
        lock_manager: LockManagerProtocol,
        uri_generator: URIGeneratorProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
    ):
        self.root_path = root_path
        self.workspace = workspace
        self.doc_manager = doc_manager
        self.lock_manager = lock_manager
        self.uri_generator = uri_generator
        self.fingerprint_strategy = fingerprint_strategy

    def _compute_fingerprints(self, module: ModuleDef) -> Dict[str, Fingerprint]:
        fingerprints: Dict[str, Fingerprint] = {}
        for func in module.functions:
            fingerprints[func.name] = self.fingerprint_strategy.compute(func)
        for cls in module.classes:
            # Include the class itself
            fingerprints[cls.name] = self.fingerprint_strategy.compute(cls)
            for method in cls.methods:
                fqn = f"{cls.name}.{method.name}"
                fingerprints[fqn] = self.fingerprint_strategy.compute(method)
        return fingerprints

    def run_batch(self, modules: List[ModuleDef]) -> List[Path]:
        created_files: List[Path] = []

        # 1. Group modules by their owning package (lock file boundary)
        # This reduces I/O by loading each lock file only once per batch.
        grouped_modules: Dict[Path, List[ModuleDef]] = defaultdict(list)
        for module in modules:
            if not module.file_path:
                continue
            abs_path = self.root_path / module.file_path
            pkg_root = self.workspace.find_owning_package(abs_path)
            grouped_modules[pkg_root].append(module)

        # 2. Process each group
        for pkg_root, pkg_modules in grouped_modules.items():
            # Load existing lock or create empty
            lock_data = self.lock_manager.load(pkg_root)
            lock_updated = False

            for module in pkg_modules:
                output_path = self.doc_manager.save_docs_for_module(module)

                # Compute logical/relative paths for SURI generation
                module_abs_path = self.root_path / module.file_path
                module_ws_rel = self.workspace.to_workspace_relative(module_abs_path)

                computed_fingerprints = self._compute_fingerprints(module)
                yaml_hashes = self.doc_manager.compute_yaml_content_hashes(module)

                all_fqns = set(computed_fingerprints.keys()) | set(yaml_hashes.keys())

                for fqn in all_fqns:
                    # Get the base computed fingerprint (code structure, sig text, etc.)
                    fp = computed_fingerprints.get(fqn, Fingerprint())

                    # Convert 'current' keys to 'baseline' keys for storage
                    if "current_code_structure_hash" in fp:
                        fp["baseline_code_structure_hash"] = fp[
                            "current_code_structure_hash"
                        ]
                        del fp["current_code_structure_hash"]

                    if "current_code_signature_text" in fp:
                        fp["baseline_code_signature_text"] = fp[
                            "current_code_signature_text"
                        ]
                        del fp["current_code_signature_text"]

                    if fqn in yaml_hashes:
                        fp["baseline_yaml_content_hash"] = yaml_hashes[fqn]

                    # Generate global SURI
                    suri = self.uri_generator.generate_symbol_uri(module_ws_rel, fqn)
                    lock_data[suri] = fp
                    lock_updated = True

                if output_path and output_path.name:
                    relative_path = output_path.relative_to(self.root_path)
                    bus.success(L.init.file.created, path=relative_path)
                    created_files.append(output_path)

            # Save lock file for the package
            if lock_updated:
                self.lock_manager.save(pkg_root, lock_data)

        return created_files
