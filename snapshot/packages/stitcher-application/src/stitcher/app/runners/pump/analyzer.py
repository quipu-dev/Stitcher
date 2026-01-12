from typing import Dict, List

from needle.pointer import L
from stitcher.spec import (
    ModuleDef,
    DocstringIR,
    DifferProtocol,
    IndexStoreProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol, SignatureManagerProtocol
from stitcher.spec.interaction import InteractionContext


class PumpAnalyzer:
    def __init__(
        self,
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
        index_store: IndexStoreProtocol,
        differ: DifferProtocol,
    ):
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.index_store = index_store
        self.differ = differ

    def _get_dirty_source_docs(self, module: ModuleDef) -> Dict[str, DocstringIR]:
        actual_symbols = self.index_store.get_symbols_by_file_path(module.file_path)
        actual_map = {
            s.logical_path: s for s in actual_symbols if s.logical_path is not None
        }

        baseline_hashes = self.sig_manager.load_composite_hashes(module.file_path)

        dirty_fqns: set[str] = set()
        all_fqns = set(actual_map.keys()) | set(baseline_hashes.keys())

        for fqn in all_fqns:
            actual = actual_map.get(fqn)
            baseline = baseline_hashes.get(fqn)

            actual_hash = actual.docstring_hash if actual else None
            baseline_hash = (
                baseline.get("baseline_code_docstring_hash") if baseline else None
            )

            if actual_hash != baseline_hash:
                dirty_fqns.add(fqn)

        if not dirty_fqns:
            return {}

        all_source_docs = self.doc_manager.flatten_module_docs(module)
        return {fqn: doc for fqn, doc in all_source_docs.items() if fqn in dirty_fqns}

    def analyze(self, modules: List[ModuleDef]) -> List[InteractionContext]:
        all_conflicts: List[InteractionContext] = []

        for module in modules:
            dirty_docs = self._get_dirty_source_docs(module)
            if not dirty_docs:
                continue

            res = self.doc_manager.hydrate_module(
                module, dry_run=True, source_docs_override=dirty_docs
            )
            if not res["success"]:
                source_docs = self.doc_manager.flatten_module_docs(module)
                yaml_docs = self.doc_manager.load_docs_for_module(module)
                for key in res["conflicts"]:
                    yaml_summary = yaml_docs[key].summary if key in yaml_docs else ""
                    src_summary = source_docs[key].summary if key in source_docs else ""
                    doc_diff = self.differ.generate_text_diff(
                        yaml_summary or "", src_summary or "", "yaml", "code"
                    )
                    all_conflicts.append(
                        InteractionContext(
                            module.file_path,
                            key,
                            violation_type=L.check.issue.conflict,
                            doc_diff=doc_diff,
                        )
                    )
        return all_conflicts