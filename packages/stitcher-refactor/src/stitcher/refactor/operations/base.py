from abc import ABC, abstractmethod
from typing import List

from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.intent import RefactorIntent


class AbstractOperation(ABC):
    @abstractmethod
    def collect_intents(self, ctx: RefactorContext) -> List[RefactorIntent]:
        pass
