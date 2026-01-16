import re
from pathlib import Path
from typing import List
import networkx as nx
from dataclasses import dataclass

from needle.pointer import L
from stitcher.analysis.schema import Violation
from stitcher.analysis.graph.algo import detect_circular_dependencies
from .protocols import ArchitectureRule


@dataclass
class CircularDependencyRule(ArchitectureRule):
    def check(self, graph: nx.DiGraph) -> List[Violation]:
        violations: List[Violation] = []
        scc_results = detect_circular_dependencies(graph)

        for scc_result in scc_results:
            scc_nodes = sorted(list(scc_result["scc"]))
            scc_size = len(scc_nodes)
            cycles_in_scc = scc_result["cycles"]

            for index, cycle in enumerate(cycles_in_scc, start=1):
                # Create a human-readable representation of the cycle
                details = []
                # Handle self-loop case
                if len(cycle) == 1:
                    u = cycle[0]
                    reasons = graph[u][u].get("reasons", [])
                    reason_str = reasons[0] if reasons else "self-reference"
                    details.append(f"\n  1. In {u}:")
                    details.append(
                        f"\n   - ( {reason_str} )"
                    )
                else:
                    cycle_len = len(cycle)
                    for i in range(cycle_len):
                        u = cycle[i]
                        v = cycle[(i + 1) % cycle_len]

                        reasons = graph[u][v].get("reasons", [])
                        if not reasons:
                            details.append(f"\n   - ({u} -> {v} <reason unavailable>)")
                            continue

                        first_reason = reasons[0]
                        line_match = re.search(r"\(L(\d+)\)", first_reason)
                        line_number = int(line_match.group(1)) if line_match else -1

                        snippet = ""
                        if line_number > 0:
                            try:
                                source_path = Path(u)
                                if source_path.exists():
                                    lines = source_path.read_text(
                                        encoding="utf-8"
                                    ).splitlines()
                                    start = max(0, line_number - 3)
                                    end = min(len(lines), line_number + 2)

                                    snippet_lines = [
                                        f"    {idx:4d} | {'> ' if idx == line_number else '  '}{line}"
                                        for idx, line in enumerate(
                                            lines[start:end], start=start + 1
                                        )
                                    ]
                                    snippet = "\n".join(snippet_lines)
                            except Exception:
                                snippet = "    <Could not read source file>"

                        details.append(f"\n   - In {u}:")
                        details.append(
                            f"\n   - ({u} -> {first_reason} == {v})"
                        )
                        if snippet:
                            details.append(f"\n{snippet}")

                cycle_path = "".join(details)

                violations.append(
                    Violation(
                        kind=L.check.architecture.circular_dependency,
                        fqn=cycle[0],
                        context={
                            "cycle": cycle_path,
                            "index": index,
                            "scc_nodes": scc_nodes,
                            "scc_size": scc_size,
                        },
                    )
                )
        return violations
