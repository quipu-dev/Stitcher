from typing import List
import networkx as nx
from dataclasses import dataclass

from needle.pointer import L
from stitcher.analysis.schema import Violation
from stitcher.analysis.graph.algorithms import detect_circular_dependencies
from .protocols import ArchitectureRule


@dataclass
class CircularDependencyRule(ArchitectureRule):
    def check(self, graph: nx.DiGraph) -> List[Violation]:
        violations: List[Violation] = []
        cycles = detect_circular_dependencies(graph)

        for cycle in cycles:
            # Create a human-readable representation of the cycle
            cycle_path = " -> ".join(cycle) + f" -> {cycle[0]}"

            # An architecture violation applies to the whole project, but we use
            # the first file in the cycle as the primary "location" for reporting.
            violations.append(
                Violation(
                    kind=L.check.architecture.circular_dependency,
                    fqn=cycle[0],
                    context={"cycle": cycle_path},
                )
            )
        return violations