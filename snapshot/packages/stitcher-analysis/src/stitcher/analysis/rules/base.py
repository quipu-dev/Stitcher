from typing import Protocol, List
from stitcher.analysis.protocols import AnalysisSubject
from stitcher.analysis.schema import SymbolState, Violation


class SymbolRule(Protocol):
    """A rule that checks a single symbol's state."""
    
    id: str

    def check(self, state: SymbolState) -> List[Violation]:
        ...


class SubjectRule(Protocol):
    """A rule that checks the entire subject (file)."""
    
    id: str

    def check(self, subject: AnalysisSubject) -> List[Violation]:
        ...