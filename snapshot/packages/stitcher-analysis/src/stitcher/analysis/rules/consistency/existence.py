from typing import List
from stitcher.analysis.schema import SymbolState, Violation, ViolationLevel
from stitcher.analysis.rules.base import SymbolRule


class ExistenceRule(SymbolRule):
    """
    Checks for the existence of symbols across code and YAML.
    - `pending`: Docstring exists in code, but not yet in YAML.
    - `missing`: Public symbol exists, but has no docstring anywhere.
    - `extra`: Docstring exists in YAML, but not in code (dangling).
    """

    id = "CONSISTENCY_EXISTENCE"

    def check(self, state: SymbolState) -> List[Violation]:
        violations: List[Violation] = []

        if state.exists_in_code and not state.exists_in_yaml:
            if state.is_public:
                if state.source_doc_content:
                    violations.append(
                        Violation(
                            fqn=state.fqn,
                            rule_id=self.id,
                            level=ViolationLevel.ERROR,
                            category="pending",
                            message="New docstring in code needs to be pumped to YAML.",
                        )
                    )
                else:
                    # Legacy: __doc__ is optional and doesn't trigger 'missing'
                    if state.fqn != "__doc__":
                        violations.append(
                            Violation(
                                fqn=state.fqn,
                                rule_id=self.id,
                                level=ViolationLevel.WARNING,
                                category="missing",
                                message="Public symbol is missing a docstring.",
                            )
                        )
        elif not state.exists_in_code and state.exists_in_yaml:
            violations.append(
                Violation(
                    fqn=state.fqn,
                    rule_id=self.id,
                    level=ViolationLevel.ERROR,
                    category="extra",
                    message="Documentation exists for a non-existent symbol in code.",
                )
            )

        return violations