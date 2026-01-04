from dataclasses import dataclass
from .graph import SemanticGraph


@dataclass
class RefactorContext:
    graph: SemanticGraph
