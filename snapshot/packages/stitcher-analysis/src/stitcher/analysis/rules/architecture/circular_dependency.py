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
    def _format_cycle_path(self, graph: nx.DiGraph, cycle: List[str]) -> str:
        """Helper to format one cycle path with code snippets."""
        details = []
        cycle_len = len(cycle)
        for i in range(cycle_len):
            u = cycle[i]
            # For the last node in the list, the path is back to the first node.
            v = cycle[(i + 1) % cycle_len]

            reasons = graph[u][v].get("reasons", [])
            if not reasons:
                details.append(f"\n  - `{u}` -> `{v}` (reason unavailable)")
                continue

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
                        snippet_lines = [
                            f"    {idx:4d} | {' >'[idx != line_number]} {line_content}"
                            for idx, line_content in enumerate(
                                lines[start:end], start=start + 1
                            )
                        ]
                        snippet = "\n".join(snippet_lines)
                except Exception:
                    snippet = "    <Could not read source file>"

            details.append(f"\n  - In `{u}`:")
            details.append(
                f"    - Causes dependency on `{v}` via import of `{first_reason}`"
            )
            if snippet:
                details.append(f"\n{snippet}\n")
        return "".join(details)

    def check(self, graph: nx.DiGraph) -> List[Violation]:
        violations: List[Violation] = []
        problematic_components = detect_circular_dependencies(graph)

        for scc, shortest_cycle in problematic_components:
            # 1. Format the list of all files in the tightly coupled component.
            component_files_str = "\n".join(f"    - {file}" for file in sorted(scc))

            # 2. Format the shortest cycle path as evidence.
            cycle_path_str = self._format_cycle_path(graph, shortest_cycle)

            # 3. Combine them into a comprehensive context message.
            full_context = (
                f"\n  Tightly coupled component of {len(scc)} files detected:\n"
                f"{component_files_str}\n\n"
                f"  Shortest cycle found as evidence:\n"
                f"{cycle_path_str}"
            )

            # Report the violation, anchoring it to the first file in the component.
            report_anchor_file = sorted(scc)[0]
            violations.append(
                Violation(
                    kind=L.check.architecture.circular_dependency,
                    fqn=report_anchor_file,
                    context={"details": full_context},
                )
            )
        return violations
