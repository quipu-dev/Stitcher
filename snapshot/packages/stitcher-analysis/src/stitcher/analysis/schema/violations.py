from dataclasses import dataclass
from enum import Enum


class ViolationLevel(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Violation:
    """
    Represents a single issue found by a rule.
    """
    fqn: str
    rule_id: str
    level: ViolationLevel
    category: str
    message: str