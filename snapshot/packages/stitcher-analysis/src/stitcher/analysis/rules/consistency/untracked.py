from dataclasses import dataclass
from typing import List

from needle.pointer import L
from stitcher.analysis.protocols import AnalysisSubject
from stitcher.analysis.schema import Violation
from stitcher.analysis.rules.protocols import AnalysisRule


@dataclass
class UntrackedRule(AnalysisRule):
    def check(self, subject: AnalysisSubject) -> List[Violation]:
        # Simple heuristic: tracked if any symbol has baseline state or is in yaml
        # But per original logic: check if .stitcher.yaml exists. 
        # Since Subject abstracts IO, we check if ANY symbol claims to be in YAML.
        # Wait, get_all_symbol_states might return empty if untracked?
        # A better heuristic for Subject abstraction: 
        # If get_all_symbol_states is populated BUT 'exists_in_yaml' is False for ALL symbols,
        # AND baseline is empty for all.
        
        # Actually, original logic checked file existence: (root / path).with_suffix(".stitcher.yaml").exists()
        # The Subject protocol should probably carry this "is_tracked" bit or we infer it.
        # Let's infer: If NO symbol has 'exists_in_yaml', the file is likely untracked.
        
        states = subject.get_all_symbol_states()
        is_tracked = any(s.exists_in_yaml for s in states.values())
        
        if is_tracked:
            return []

        if not subject.is_documentable():
            return []

        # It's untracked and documentable.
        # Check for undocumented public symbols
        undocumented_keys = [
            s.fqn
            for s in states.values()
            if s.is_public
            and s.fqn != "__doc__"
            and not s.source_doc_content
        ]

        if undocumented_keys:
            # Report file-level issue with context about missing keys
            return [
                Violation(
                    kind=L.check.file.untracked_with_details,
                    fqn=subject.file_path, # File level violation
                    context={"count": len(undocumented_keys), "keys": undocumented_keys}
                )
            ]
            # Note: Individual missing keys logic is handled by ExistenceRule? 
            # No, original logic outputted a specific warning for untracked files.
            # We stick to reproducing original logic's output structure via Violation context.
        else:
            return [
                Violation(
                    kind=L.check.file.untracked,
                    fqn=subject.file_path
                )
            ]