from typing import List, Dict
from pathlib import Path

from stitcher.common import bus
from needle.pointer import L
from stitcher.spec import Fingerprint, ModuleDef
from stitcher.app.services import DocumentManager, SignatureManager


class InitRunner:
    def __init__(
        self,
        root_path: Path,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
    ):
        self.root_path = root_path
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager

    def run_batch(self, modules: List[ModuleDef]) -> List[Path]:
        created_files: List[Path] = []
        for module in modules:
            output_path = self.doc_manager.save_docs_for_module(module)

            # Use the new unified compute method
            computed_fingerprints = self.sig_manager.compute_fingerprints(module)
            yaml_hashes = self.doc_manager.compute_yaml_content_hashes(module)

            combined: Dict[str, Fingerprint] = {}
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

                combined[fqn] = fp

            self.sig_manager.save_composite_hashes(module, combined)
            if output_path and output_path.name:
                relative_path = output_path.relative_to(self.root_path)
                bus.success(L.init.file.created, path=relative_path)
                created_files.append(output_path)
        return created_files
