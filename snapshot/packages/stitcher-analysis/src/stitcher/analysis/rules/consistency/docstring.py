from typing import List
from stitcher.analysis.schema import SymbolState, Violation, ViolationLevel
from stitcher.analysis.rules.base import SymbolRule


class DocstringContentRule(SymbolRule):
    """
    Checks for consistency between docstrings in source code and YAML.
    - `conflict`: Docstring summaries differ.
    - `redundant`: Docstring summaries are identical.
    """

    id = "CONSISTENCY_DOCSTRING_CONTENT"

    def check(self, state: SymbolState) -> List[Violation]:
        violations: List[Violation] = []
        if not (state.exists_in_code and state.exists_in_yaml):
            return violations
        
        if state.source_doc_content and state.yaml_doc_ir:
            if state.source_doc_content == state.yaml_doc_ir.summary:
                violations.append(
                    Violation(
                        fqn=state.fqn,
                        rule_id=self.id,
                        level=ViolationLevel.WARNING,
                        category="redundant",
                        message=(
                            "Docstring exists in both code and YAML. "
                            "Consider running `stitcher strip`."
                        ),
                    )
                )
            else:
                violations.append(
                    Violation(
                        fqn=state.fqn,
                        rule_id=self.id,
                        level=ViolationLevel.ERROR,
                        category="conflict",
                        message="Content differs between source code docstring and YAML.",
                    )
                )

        return violations