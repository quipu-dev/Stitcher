from dataclasses import dataclass
from typing import List

from needle.pointer import L
from stitcher.spec import DifferProtocol
from stitcher.analysis.protocols import AnalysisSubject
from stitcher.analysis.schema import Violation
from stitcher.analysis.rules.protocols import AnalysisRule


@dataclass
class ContentRule(AnalysisRule):
    differ: DifferProtocol

    def check(self, subject: AnalysisSubject) -> List[Violation]:
        violations: List[Violation] = []
        states = subject.get_all_symbol_states()

        for fqn, state in states.items():
            # We only care if doc exists in BOTH places
            if not (state.exists_in_code and state.exists_in_yaml):
                continue

            # Need content to compare
            if not (state.source_doc_content and state.yaml_doc_ir):
                continue

            src_summary = state.source_doc_content
            yaml_summary = state.yaml_doc_ir.summary

            if src_summary == yaml_summary:
                # Redundant: Info/Warning depending on policy, usually a warning to strip
                violations.append(
                    Violation(
                        kind=L.check.issue.redundant,
                        fqn=fqn,
                    )
                )
            else:
                # Conflict: Content differs
                doc_diff = self.differ.generate_text_diff(
                    yaml_summary or "",
                    src_summary or "",
                    "yaml",
                    "code",
                )
                violations.append(
                    Violation(
                        kind=L.check.issue.conflict,
                        fqn=fqn,
                        context={"doc_diff": doc_diff},
                    )
                )

        return violations