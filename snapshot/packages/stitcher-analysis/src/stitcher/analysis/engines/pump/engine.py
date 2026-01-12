from typing import List
from dataclasses import dataclass

from needle.pointer import L
from stitcher.spec import DifferProtocol
from stitcher.spec.interaction import InteractionContext
from stitcher.common.services import Differ
from stitcher.analysis.protocols import AnalysisSubject


@dataclass
class PumpEngine:
    differ: DifferProtocol

    def analyze(self, subject: AnalysisSubject) -> List[InteractionContext]:
        conflicts: List[InteractionContext] = []
        states = subject.get_all_symbol_states()

        for fqn, state in states.items():
            # A symbol is a candidate for pumping if it has a docstring in the source code.
            if not state.source_doc_content:
                continue

            # Case 1: New docstring (exists in code, not in YAML).
            # This is not a conflict, but a candidate for clean hydration.
            # The runner will handle this, the engine just needs to identify conflicts.
            if not state.exists_in_yaml:
                continue

            # Case 2: Conflict (exists in both, content differs).
            # We need to compare the summaries.
            yaml_ir = state.yaml_doc_ir
            yaml_summary = yaml_ir.summary if yaml_ir else ""
            src_summary = state.source_doc_content or ""

            if src_summary != yaml_summary:
                doc_diff = self.differ.generate_text_diff(
                    yaml_summary or "", src_summary or "", "yaml", "code"
                )
                conflicts.append(
                    InteractionContext(
                        file_path=subject.file_path,
                        fqn=fqn,
                        violation_type=L.check.issue.conflict,
                        doc_diff=doc_diff,
                    )
                )

        return conflicts


def create_pump_engine(differ: DifferProtocol | None = None) -> PumpEngine:
    effective_differ = differ or Differ()
    return PumpEngine(differ=effective_differ)
