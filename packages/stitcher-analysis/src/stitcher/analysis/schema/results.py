from dataclasses import dataclass, field
from typing import List, Set

from needle.pointer import L, SemanticPointer
from .violation import Violation


@dataclass
class FileCheckResult:
    path: str

    # All findings (errors, warnings, infos)
    violations: List[Violation] = field(default_factory=list)

    # Records of actions taken during auto-reconciliation
    # Reconciled items are also fundamentally Violations that were resolved.
    reconciled: List[Violation] = field(default_factory=list)

    # --- Severity Mapping ---
    _ERROR_KINDS: Set[SemanticPointer] = field(
        default_factory=lambda: {
            L.check.issue.conflict,
            L.check.state.signature_drift,
            L.check.state.co_evolution,
            L.check.issue.extra,
            L.check.issue.pending,
        },
        init=False,
        repr=False,
    )

    _WARNING_KINDS: Set[SemanticPointer] = field(
        default_factory=lambda: {
            L.check.issue.missing,
            L.check.issue.redundant,
            L.check.file.untracked,
            L.check.file.untracked_with_details,
        },
        init=False,
        repr=False,
    )

    # --- Computed Properties ---
    @property
    def error_violations(self) -> List[Violation]:
        return [v for v in self.violations if v.kind in self._ERROR_KINDS]

    @property
    def warning_violations(self) -> List[Violation]:
        return [v for v in self.violations if v.kind in self._WARNING_KINDS]

    @property
    def info_violations(self) -> List[Violation]:
        error_and_warning_kinds = self._ERROR_KINDS | self._WARNING_KINDS
        return [v for v in self.violations if v.kind not in error_and_warning_kinds]

    @property
    def error_count(self) -> int:
        return len(self.error_violations)

    @property
    def warning_count(self) -> int:
        return len(self.warning_violations)

    @property
    def is_clean(self) -> bool:
        return len(self.violations) == 0
