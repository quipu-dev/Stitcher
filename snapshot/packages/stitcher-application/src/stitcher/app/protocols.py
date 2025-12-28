from typing import Protocol, List
from dataclasses import dataclass

from stitcher.spec import ResolutionAction, ConflictType


@dataclass
class InteractionContext:
    file_path: str
    fqn: str
    conflict_type: ConflictType
    # Future extensions:
    # signature_diff: str = ""
    # doc_diff: str = ""


class InteractionHandler(Protocol):
    def process_interactive_session(
        self, contexts: List[InteractionContext]
    ) -> List[ResolutionAction]: ...
