import re
from pathlib import Path
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

        if not cycles:
            return []

        # To avoid overwhelming output and memory usage, report a summary.
        total_cycles = len(cycles)
        # Sort by length and then alphabetically to get a deterministic sample
        sorted_cycles = sorted(cycles, key=lambda c: (len(c), sorted(c)))
        sample_cycles = sorted_cycles[:3]  # Take up to 3 samples

        sample_details = []
        for i, sample in enumerate(sample_cycles):
            path_str = " -> ".join(sample) + f" -> {sample[0]}"
            sample_details.append(f"  - Example {i+1}: {path_str}")

        summary_report = (
            f"\n  Found {total_cycles} circular dependencies. "
            "This can severely impact maintainability and cause import errors."
            "\n\n  Please break the cycles. Here are a few examples:"
            f"\n" + "\n".join(sample_details)
        )

        # An architecture violation applies to the whole project. We report it once.
        # We use the first file of the first detected cycle as the primary "location" for reporting.
        report_location = sorted_cycles[0][0]

        violations.append(
            Violation(
                kind=L.check.architecture.circular_dependency,
                fqn=report_location,
                context={"cycle": summary_report},
            )
        )

        return violations
