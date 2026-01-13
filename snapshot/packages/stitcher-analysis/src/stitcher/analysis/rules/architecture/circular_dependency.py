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
            # cycle is a list of nodes [n1, n2, n3] representing n1->n2->n3->n1

            details = []
            cycle_len = len(cycle)
            for i in range(cycle_len):
                u = cycle[i]
                v = cycle[(i + 1) % cycle_len]

                # Extract reasons from the graph edge
                reasons = graph[u][v].get("reasons", [])
                # Take top 3 reasons to avoid clutter
                reason_str = ", ".join(reasons[:3])
                if len(reasons) > 3:
                    reason_str += ", ..."

                # Format: "a.py --[import x (L1)]--> b.py"
                details.append(f"\n      {u} --[{reason_str}]--> {v}")

            cycle_path = "".join(details)

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