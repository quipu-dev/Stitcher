from dataclasses import dataclass
from typing import Protocol, List

from .models import SourceLocation


@dataclass
class RefactorUsage:
    location: SourceLocation
    # Optional text matching for verification (e.g. ensure we are replacing the right thing)
    match_text: str = ""


class RefactoringStrategyProtocol(Protocol):
    def rename_symbol(
        self,
        source_code: str,
        usages: List[RefactorUsage],
        old_name: str,
        new_name: str,
    ) -> str: ...
