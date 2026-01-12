from typing import Protocol, List, Optional
from dataclasses import dataclass

from needle.pointer import SemanticPointer

from stitcher.spec import ResolutionAction, ConflictType


@dataclass
class InteractionContext:
    file_path: str
    fqn: str
    
    # Replaced ConflictType Enum with SemanticPointer for extensibility
    violation_type: SemanticPointer
    
    signature_diff: Optional[str] = None
    doc_diff: Optional[str] = None
    
    # Deprecated: kept temporarily if strictly needed, but design goal is to remove it.
    # conflict_type: ConflictType 


class InteractionHandler(Protocol):
    def process_interactive_session(
        self, contexts: List[InteractionContext]
    ) -> List[ResolutionAction]: ...