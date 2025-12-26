from dataclasses import dataclass, field
from typing import List, Set
from stitcher.spec import ModuleDef
from .doc_manager import DocumentManager


@dataclass
class CheckResult:
    is_consistent: bool
    missing_keys: Set[str] = field(default_factory=set)
    stale_keys: Set[str] = field(default_factory=set)


class ConsistencyChecker:
    def __init__(self, doc_manager: DocumentManager):
        self._doc_manager = doc_manager

    def check_module(self, module: ModuleDef) -> CheckResult:
        """
        Compares the IR of a module against its external documentation.
        """
        # Get keys from code structure
        code_keys = set(self._doc_manager.flatten_module_docs(module).keys())
        
        # Get keys from doc file
        doc_keys = set(self._doc_manager.load_docs_for_module(module).keys())
        
        missing_keys = code_keys - doc_keys
        stale_keys = doc_keys - code_keys
        
        is_consistent = not missing_keys and not stale_keys
        
        return CheckResult(
            is_consistent=is_consistent,
            missing_keys=missing_keys,
            stale_keys=stale_keys
        )