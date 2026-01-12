from typing import Protocol, List, Optional
from dataclasses import dataclass

from stitcher.spec import ResolutionAction, ConflictType


@dataclass
class InteractionContext:
    file_path: str
    fqn: str
    conflict_type: ConflictType
    signature_diff: Optional[str] = None
    doc_diff: Optional[str] = None


class InteractionHandler(Protocol):
    def process_interactive_session(
        self, contexts: List[InteractionContext]
    ) -> List[ResolutionAction]: ...
