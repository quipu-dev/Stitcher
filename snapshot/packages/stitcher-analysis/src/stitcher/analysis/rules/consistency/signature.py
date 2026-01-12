from dataclasses import dataclass
from typing import List

from needle.pointer import L
from stitcher.spec import DifferProtocol
from stitcher.analysis.protocols import AnalysisSubject
from stitcher.analysis.schema import Violation
from stitcher.analysis.rules.protocols import AnalysisRule


@dataclass
class SignatureRule(AnalysisRule):
    differ: DifferProtocol

    def check(self, subject: AnalysisSubject) -> List[Violation]:
        violations: List[Violation] = []
        states = subject.get_all_symbol_states()

        for fqn, state in states.items():
            # Skip if not tracked in YAML (not our responsibility)
            if not state.exists_in_yaml:
                continue
            
            # Skip if not in code (handled by ExistenceRule/Dangling)
            if not state.exists_in_code:
                continue

            # Skip new symbols (no baseline)
            code_hash = state.signature_hash
            baseline_code_hash = state.baseline_signature_hash
            if code_hash and not baseline_code_hash:
                continue

            code_matches = code_hash == baseline_code_hash
            yaml_matches = state.yaml_content_hash == state.baseline_yaml_content_hash

            # Case 1: Doc Updated (Info)
            # Code matches baseline, but YAML changed. This is a valid update.
            if code_matches and not yaml_matches:
                violations.append(
                    Violation(
                        kind=L.check.state.doc_updated,
                        fqn=fqn,
                    )
                )

            # Case 2: Signature Changed
            elif not code_matches:
                sig_diff = self.differ.generate_text_diff(
                    state.baseline_signature_text or "",
                    state.signature_text or "",
                    "baseline",
                    "current",
                )
                
                # If YAML hasn't changed, it's just drift.
                # If YAML ALSO changed, it's co-evolution (ambiguous intent).
                kind = (
                    L.check.state.signature_drift
                    if yaml_matches
                    else L.check.state.co_evolution
                )

                violations.append(
                    Violation(
                        kind=kind,
                        fqn=fqn,
                        context={"signature_diff": sig_diff},
                    )
                )

        return violations