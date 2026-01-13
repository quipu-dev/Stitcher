from typing import Protocol, List
import networkx as nx

from stitcher.analysis.schema import Violation


class ArchitectureRule(Protocol):
    def check(self, graph: nx.DiGraph) -> List[Violation]: ...
