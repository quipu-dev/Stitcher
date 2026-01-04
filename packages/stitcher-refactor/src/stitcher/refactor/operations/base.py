from abc import ABC, abstractmethod
from typing import List
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import FileOp


class AbstractOperation(ABC):
    @abstractmethod
    def analyze(self, ctx: RefactorContext) -> List[FileOp]:
        pass
