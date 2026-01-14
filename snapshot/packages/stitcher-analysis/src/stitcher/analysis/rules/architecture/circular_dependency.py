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

        for index, cycle in enumerate(cycles, start=1):
            # Create a human-readable representation of the cycle
            # cycle is a list of nodes [n1, n2, n3] representing n1->n2->n3->n1

            details = []
            cycle_len = len(cycle)
            for i in range(cycle_len):
                u = cycle[i]
                v = cycle[(i + 1) % cycle_len]

                # Extract reasons from the graph edge
                reasons = graph[u][v].get("reasons", [])
                if not reasons:
                    details.append(f"\n  {u} -> {v} (reason unavailable)")
                    continue

                # For simplicity, focus on the first reason to extract code context
                first_reason = reasons[0]
                line_match = re.search(r"\(L(\d+)\)", first_reason)
                line_number = int(line_match.group(1)) if line_match else -1

                snippet = ""
                if line_number > 0:
                    try:
                        source_path = Path(u)
                        if source_path.exists():
                            lines = source_path.read_text(encoding="utf-8").splitlines()
                            start = max(0, line_number - 3)
                            end = min(len(lines), line_number + 2)

                            snippet_lines = []
                            for idx, line_content in enumerate(
                                lines[start:end], start=start + 1
                            ):
                                prefix = "> " if idx == line_number else "  "
                                snippet_lines.append(
                                    f"    {idx:4d} | {prefix}{line_content}"
                                )
                            snippet = "\n".join(snippet_lines)
                    except Exception:
                        snippet = "    <Could not read source file>"

                details.append(f"\n  - In `{u}`:")
                details.append(
                    f"    - Causes dependency on `{v}` via import of `{first_reason}`"
                )
                if snippet:
                    details.append(f"\n{snippet}")

            cycle_path = "".join(details)

            # An architecture violation applies to the whole project, but we use
            # the first file in the cycle as the primary "location" for reporting.
            violations.append(
                Violation(
                    kind=L.check.architecture.circular_dependency,
                    fqn=cycle[0],
                    context={"cycle": cycle_path, "index": index},
                )
            )
        return violations
