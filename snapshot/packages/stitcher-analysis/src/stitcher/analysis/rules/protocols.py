from typing import Protocol, List

from stitcher.analysis.protocols import AnalysisSubject
from stitcher.analysis.schema import Violation


class AnalysisRule(Protocol):
    """
    Protocol for a single analysis rule that checks a subject for specific issues.
    """

    def check(self, subject: AnalysisSubject) -> List[Violation]:
        """
        Analyze the subject and return a list of violations found.
        """
        ...