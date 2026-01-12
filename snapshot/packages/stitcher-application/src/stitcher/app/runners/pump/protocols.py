from typing import Protocol, List, Dict
from stitcher.spec import ModuleDef, ResolutionAction
from stitcher.common.transaction import TransactionManager
from stitcher.app.types import PumpResult


class PumpExecutorProtocol(Protocol):
    def execute(
        self,
        modules: List[ModuleDef],
        decisions: Dict[str, ResolutionAction],
        tm: TransactionManager,
        strip: bool,
    ) -> PumpResult: ...