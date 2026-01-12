from pathlib import Path
from typing import List, Tuple

from needle.pointer import L
from stitcher.spec import DifferProtocol
from stitcher.spec.interaction import InteractionContext
from stitcher.app.types import FileCheckResult
from .protocols import CheckSubject


class CheckAnalyzer:
    def __init__(self, root_path: Path, differ: DifferProtocol):
        self.root_path = root_path
        self.differ = differ

    def analyze_subject(
        self, subject: CheckSubject
    ) -> Tuple[FileCheckResult, List[InteractionContext]]:
        result = FileCheckResult(path=subject.file_path)
        unresolved_conflicts: List[InteractionContext] = []

        is_tracked = (
            (self.root_path / subject.file_path).with_suffix(".stitcher.yaml").exists()
        )

        for fqn, state in subject.get_all_symbol_states().items():
            # --- State Machine Logic ---

            # 1. Content Checks
            if state.exists_in_code and state.exists_in_yaml:
                if state.source_doc_content and state.yaml_doc_ir:
                    if state.source_doc_content == state.yaml_doc_ir.summary:
                        result.warnings["redundant"].append(fqn)
                    else:
                        result.errors["conflict"].append(fqn)

            elif state.is_public and state.exists_in_code and not state.exists_in_yaml:
                if state.source_doc_content:
                    result.errors["pending"].append(fqn)
                else:
                    # Legacy Behavior: __doc__ is optional.
                    # If it's missing in both source and YAML, don't report it as missing.
                    if fqn != "__doc__":
                        result.warnings["missing"].append(fqn)

            elif not state.exists_in_code and state.exists_in_yaml:
                unresolved_conflicts.append(
                    InteractionContext(
                        subject.file_path, fqn, violation_type=L.check.issue.extra
                    )
                )

            # 2. Signature Checks
            code_hash = state.signature_hash
            baseline_code_hash = state.baseline_signature_hash

            if code_hash and not baseline_code_hash:  # New symbol, skip
                continue
            if (
                not code_hash and baseline_code_hash
            ):  # Deleted symbol, handled by DANGLING_DOC
                continue

            code_matches = code_hash == baseline_code_hash
            yaml_matches = state.yaml_content_hash == state.baseline_yaml_content_hash

            if code_matches and not yaml_matches:
                result.infos["doc_improvement"].append(fqn)
            elif not code_matches:
                sig_diff = self.differ.generate_text_diff(
                    state.baseline_signature_text or "",
                    state.signature_text or "",
                    "baseline",
                    "current",
                )

                violation_type = (
                    L.check.state.signature_drift
                    if yaml_matches
                    else L.check.state.co_evolution
                )
                unresolved_conflicts.append(
                    InteractionContext(
                        subject.file_path,
                        fqn,
                        violation_type=violation_type,
                        signature_diff=sig_diff,
                    )
                )

        # 3. Untracked File Check
        if not is_tracked and subject.is_documentable():
            # Check for any public symbols that would be documented
            undocumented = [
                s.fqn
                for s in subject.get_all_symbol_states().values()
                if s.is_public
                and s.fqn != "__doc__"
                and not s.source_doc_content
                and not s.exists_in_yaml
            ]
            if undocumented:
                result.warnings["untracked_detailed"].extend(undocumented)
            else:
                result.warnings["untracked"].append("all")

        return result, unresolved_conflicts