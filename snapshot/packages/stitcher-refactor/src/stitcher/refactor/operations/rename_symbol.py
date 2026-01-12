from typing import List

from .base import AbstractOperation
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.intent import (
    RefactorIntent,
    RenameIntent,
)


class RenameSymbolOperation(AbstractOperation):
    def __init__(self, old_fqn: str, new_fqn: str):
        self.old_fqn = old_fqn
        self.new_fqn = new_fqn

    def collect_intents(self, ctx: RefactorContext) -> List[RefactorIntent]:
        # The operation's only job now is to declare the high-level intent.
        # The planner and renamer will use the unified index to find all usages,
        # including code and sidecar files, and apply the correct strategy.
        return [RenameIntent(old_fqn=self.old_fqn, new_fqn=self.new_fqn)]
