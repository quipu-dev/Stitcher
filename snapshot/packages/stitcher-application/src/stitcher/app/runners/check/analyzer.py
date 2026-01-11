from pathlib import Path
from typing import List, Tuple, Dict

from stitcher.spec import (
    ModuleDef,
    ConflictType,
    Fingerprint,
    FingerprintStrategyProtocol,
)
from stitcher.app.services import DocumentManager, SignatureManager, Differ
from stitcher.app.protocols import InteractionContext
from stitcher.app.types import FileCheckResult


class CheckAnalyzer:
    def __init__(
        self,
        root_path: Path,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
        differ: Differ,
        fingerprint_strategy: FingerprintStrategyProtocol,
    ):
        self.root_path = root_path
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.differ = differ
        self.fingerprint_strategy = fingerprint_strategy

    def analyze_batch(
        self, modules: List[ModuleDef]
    ) -> Tuple[List[FileCheckResult], List[InteractionContext]]:
        results = []
        conflicts = []
        for module in modules:
            res, conf = self._analyze_file(module)
            results.append(res)
            conflicts.extend(conf)
        return results, conflicts

    def _compute_fingerprints(self, module: ModuleDef) -> Dict[str, Fingerprint]:
        fingerprints: Dict[str, Fingerprint] = {}
        for func in module.functions:
            fingerprints[func.name] = self.fingerprint_strategy.compute(func)
        for cls in module.classes:
            for method in cls.methods:
                fqn = f"{cls.name}.{method.name}"
                fingerprints[fqn] = self.fingerprint_strategy.compute(method)
        return fingerprints

    def _analyze_file(
        self, module: ModuleDef
    ) -> Tuple[FileCheckResult, List[InteractionContext]]:
        result = FileCheckResult(path=module.file_path)
        unresolved_conflicts: List[InteractionContext] = []

        # Content checks
        if (self.root_path / module.file_path).with_suffix(".stitcher.yaml").exists():
            doc_issues = self.doc_manager.check_module(module)
            result.warnings["missing"].extend(doc_issues["missing"])
            result.warnings["redundant"].extend(doc_issues["redundant"])
            result.errors["pending"].extend(doc_issues["pending"])
            result.errors["conflict"].extend(doc_issues["conflict"])
            for fqn in doc_issues["extra"]:
                unresolved_conflicts.append(
                    InteractionContext(module.file_path, fqn, ConflictType.DANGLING_DOC)
                )

        # State machine analysis
        is_tracked = (
            (self.root_path / module.file_path).with_suffix(".stitcher.yaml").exists()
        )

        computed_fingerprints = self._compute_fingerprints(module)
        current_yaml_map = self.doc_manager.compute_yaml_content_hashes(module)
        stored_hashes_map = self.sig_manager.load_composite_hashes(module.file_path)

        all_fqns = set(computed_fingerprints.keys()) | set(stored_hashes_map.keys())

        for fqn in sorted(list(all_fqns)):
            computed_fp = computed_fingerprints.get(fqn, Fingerprint())

            code_hash = computed_fp.get("current_code_structure_hash")
            current_sig_text = computed_fp.get("current_code_signature_text")
            yaml_hash = current_yaml_map.get(fqn)

            stored_fp = stored_hashes_map.get(fqn)
            baseline_code_hash = (
                stored_fp.get("baseline_code_structure_hash") if stored_fp else None
            )
            baseline_yaml_hash = (
                stored_fp.get("baseline_yaml_content_hash") if stored_fp else None
            )
            baseline_sig_text = (
                stored_fp.get("baseline_code_signature_text") if stored_fp else None
            )

            if not code_hash and baseline_code_hash:  # Extra
                continue
            if code_hash and not baseline_code_hash:  # New
                continue

            code_matches = code_hash == baseline_code_hash
            yaml_matches = yaml_hash == baseline_yaml_hash

            if code_matches and not yaml_matches:  # Doc improvement
                result.infos["doc_improvement"].append(fqn)
            elif not code_matches:
                sig_diff = None
                if baseline_sig_text and current_sig_text:
                    sig_diff = self.differ.generate_text_diff(
                        baseline_sig_text,
                        current_sig_text,
                        "baseline",
                        "current",
                    )
                elif current_sig_text:
                    sig_diff = f"(No baseline signature stored)\n+++ current\n{current_sig_text}"

                conflict_type = (
                    ConflictType.SIGNATURE_DRIFT
                    if yaml_matches
                    else ConflictType.CO_EVOLUTION
                )

                unresolved_conflicts.append(
                    InteractionContext(
                        module.file_path, fqn, conflict_type, signature_diff=sig_diff
                    )
                )

        if not is_tracked and module.is_documentable():
            undocumented = module.get_undocumented_public_keys()
            if undocumented:
                result.warnings["untracked_detailed"].extend(undocumented)
            else:
                result.warnings["untracked"].append("all")

        return result, unresolved_conflicts