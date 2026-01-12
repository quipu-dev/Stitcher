from dataclasses import dataclass
from typing import List

from needle.pointer import L
from stitcher.analysis.protocols import AnalysisSubject
from stitcher.analysis.schema import Violation
from stitcher.analysis.rules.protocols import AnalysisRule


@dataclass
class ExistenceRule(AnalysisRule):
    def check(self, subject: AnalysisSubject) -> List[Violation]:
        violations: List[Violation] = []
        states = subject.get_all_symbol_states()

        for fqn, state in states.items():
            # 1. Pending & Missing (Code exists, YAML missing)
            if state.exists_in_code and not state.exists_in_yaml:
                if state.is_public:
                    if state.source_doc_content:
                        # Has doc in code -> Pending import
                        violations.append(Violation(kind=L.check.issue.pending, fqn=fqn))
                    else:
                        # No doc in code -> Missing
                        # Legacy behavior: __doc__ is optional
                        if fqn != "__doc__":
                            violations.append(Violation(kind=L.check.issue.missing, fqn=fqn))

            # 2. Extra / Dangling (YAML exists, Code missing)
            elif not state.exists_in_code and state.exists_in_yaml:
                violations.append(Violation(kind=L.check.issue.extra, fqn=fqn))

        return violations