from typing import Protocol, List, Optional
from dataclasses import dataclass

from needle.pointer import SemanticPointer

from stitcher.spec import ResolutionAction


@dataclass
class InteractionContext:
    file_path: str
    fqn: str
    violation_type: SemanticPointer
    signature_diff: Optional[str] = None
    doc_diff: Optional[str] = None


class InteractionHandler(Protocol):
    def process_interactive_session(
        self, contexts: List[InteractionContext]
    ) -> List[ResolutionAction]: ...