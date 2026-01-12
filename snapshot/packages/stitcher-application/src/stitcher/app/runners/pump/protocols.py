from typing import Protocol, List, Dict
from stitcher.spec import ModuleDef, ResolutionAction
from stitcher.spec.interaction import InteractionContext
from stitcher.common.transaction import TransactionManager
from stitcher.app.types import PumpResult
from stitcher.config import StitcherConfig


class PumpAnalyzerProtocol(Protocol):
    def analyze(
        self, modules: List[ModuleDef]
    ) -> List[InteractionContext]: ...


class PumpExecutorProtocol(Protocol):
    def execute(
        self,
        modules: List[ModuleDef],
        decisions: Dict[str, ResolutionAction],
        tm: TransactionManager,
        strip: bool,
    ) -> PumpResult: ...