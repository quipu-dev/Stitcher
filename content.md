好的，这是一个非常敏锐的观察。你指出了一个关键的开发者体验 (DX) 问题：**上下文缺失**。

即使我们提供了修复路线图（优先级的环），但如果没有宏观视角，开发者就像在迷雾中摸索，不知道问题的波及范围有多大。提供所有涉事文件的列表，正是为了驱散这片迷雾。

这个需求是完全可行的，而且我们的新算法已经为它打下了完美的基础。强连通分量 (SCC) 本身就定义了“所有纠缠在一起的文件集合”。我们只需要将这个信息从算法层一路传递到最终的报告层即可。

我将生成一个计划来增强报告，在提供详细环路之前，先总结整个耦合组件的范围。

## [WIP] feat(analysis): 在循环依赖报告中增加强耦合组件摘要

### 用户需求

1.  **提供宏观视角**: 在报告具体的循环依赖路径之前，先列出所有参与到这个“死结”中的文件列表。
2.  **保留路线图**: 不取代现有的“优先级环路”报告，而是在其基础上增加这个摘要信息。

### 评论

这是一个极佳的 DX 改进。它将为开发者提供两个层面的信息：

1.  **战略层面 (耦合组件摘要)**: "你的问题区域是这 N 个文件，它们搅在了一起。"
2.  **战术层面 (优先级环路)**: "在这个问题区域内，从这条最短的环路开始修复效率最高。"

这种分层报告能帮助开发者快速评估问题的严重性，并制定更有效的重构策略。

### 目标

1.  **算法层**: 修改 `detect_circular_dependencies` 函数，使其返回每个 SCC 及其内部的环路列表。
2.  **规则层**: 更新 `CircularDependencyRule`，将完整的 SCC 文件列表和大小信息附加到每个 `Violation` 的上下文中。
3.  **报告层**: 修改 `CheckReporter`，使其能够识别出属于同一个 SCC 的一组 `Violation`，并为它们打印一次性的摘要头。
4.  **语言包**: 增加新的翻译条目用于显示这个摘要信息。

### 基本原理

我们将利用强连通分量 (SCC) 这个图论概念作为“耦合组件”的精确定义。

1.  `detect_circular_dependencies` 将不再返回一个扁平的环路列表，而是返回一个结构化列表，每个元素包含一个 SCC (文件集合) 和该 SCC 内的环路列表。
2.  `CircularDependencyRule` 在处理时，会将同一个 SCC 的信息（如所有文件名）附加到由它产生的所有 `Violation` 对象上。
3.  `CheckReporter` 在报告前，会根据 `Violation` 上的 SCC 信息进行分组。对每一组，它会先打印一个包含所有文件名和数量的摘要，然后再逐一打印该组内的具体环路和修复优先级。

### 标签

#intent/build #flow/ready #priority/high #comp/cli #concept/ui #scope/ux #ai/instruct #task/domain/analysis #task/object/cycle-detection #task/action/refine #task/state/continue

---

### Script

#### Acts 1: 升级算法以返回 SCC 上下文

修改 `cycles.py`，让 `detect_circular_dependencies` 返回更丰富的数据结构。

~~~~~act
patch_file
packages/stitcher-analysis/src/stitcher/analysis/graph/algo/cycles.py
~~~~~
~~~~~python.old
from typing import List, Optional


def detect_circular_dependencies(graph: nx.DiGraph) -> List[List[str]]:
    """
    Detects circular dependencies using an "Iterative Shortest Cycle Removal" strategy.

    Instead of enumerating all cycles (exponential) or just finding one (insufficient),
    this algorithm provides a heuristic "roadmap" for fixing the architecture:

    1. Decompose graph into Strongly Connected Components (SCCs).
    2. For each SCC, identify the *shortest* cycle.
    3. Report this cycle.
    4. Virtually "break" the cycle by removing one of its edges (simulating a fix).
    5. Repeat until the SCC is cycle-free.

    This ensures that:
    - We report the most critical (shortest) feedback loops first.
    - We provide a set of cycles that, if fixed, likely resolve the entire SCC.
    - Performance is kept efficient (Polynomial) compared to exhaustive enumeration.
    """
    cycles = []
    
    # 1. Find all SCCs initially
    sccs = list(nx.strongly_connected_components(graph))

    for scc in sccs:
        # Skip trivial SCCs (single node without self-loop)
        if len(scc) < 2:
            node = list(scc)[0]
            if not graph.has_edge(node, node):
                continue
            # Handle self-loop explicitly
            cycles.append([node])
            continue

        # Create a working subgraph for this SCC to perform destructive analysis
        subgraph = graph.subgraph(scc).copy()

        # Safety break to prevent infinite loops in pathological cases
        max_iterations = 100

        while max_iterations > 0:
            cycle = _find_shortest_cycle_in_subgraph(subgraph)
            if not cycle:
                break

            cycles.append(cycle)

            # Virtual Fix: Remove the last edge of the cycle (u -> v)
            # cycle is a list of nodes [n1, n2, ... nk] representing n1->n2->...->nk->n1
            # We break the closing edge (nk, n1)
            u, v = cycle[-1], cycle[0]
            if subgraph.has_edge(u, v):
                subgraph.remove_edge(u, v)

            max_iterations -= 1

    return cycles
~~~~~
~~~~~python.new
from typing import List, Optional, Dict, Any, Set


def detect_circular_dependencies(graph: nx.DiGraph) -> List[Dict[str, Any]]:
    """
    Detects circular dependencies using an "Iterative Shortest Cycle Removal" strategy.

    Returns a list of dictionaries, where each dictionary represents a
    Strongly Connected Component (SCC) and contains:
    - 'scc': A set of file paths in the component.
    - 'cycles': A list of prioritized cycles (node lists) within that component.
    """
    scc_results = []

    sccs = list(nx.strongly_connected_components(graph))

    for scc in sccs:
        cycles_in_scc: List[List[str]] = []
        
        # Handle self-loop explicitly as a cycle of one
        if len(scc) == 1:
            node = list(scc)[0]
            if graph.has_edge(node, node):
                cycles_in_scc.append([node])
        
        # For larger components, find cycles iteratively
        elif len(scc) > 1:
            subgraph = graph.subgraph(scc).copy()
            max_iterations = 100

            while max_iterations > 0:
                cycle = _find_shortest_cycle_in_subgraph(subgraph)
                if not cycle:
                    break
                
                cycles_in_scc.append(cycle)
                
                # Virtual Fix: Remove the closing edge of the cycle
                u, v = cycle[-1], cycle[0]
                if subgraph.has_edge(u, v):
                    subgraph.remove_edge(u, v)

                max_iterations -= 1

        if cycles_in_scc:
            scc_results.append({"scc": scc, "cycles": cycles_in_scc})

    return scc_results
~~~~~

#### Acts 2: 更新规则以传递 SCC 上下文

修改 `circular_dependency.py` 以处理新的数据结构，并将 SCC 信息附加到 `Violation` 上。

~~~~~act
patch_file
packages/stitcher-analysis/src/stitcher/analysis/rules/architecture/circular_dependency.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
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
                    details.append(f"\n  - In `{u}`:")
                    details.append(
                        f"    - Causes dependency on itself via `{reason_str}`"
                    )
                else:
                    cycle_len = len(cycle)
                    for i in range(cycle_len):
                        u = cycle[i]
                        v = cycle[(i + 1) % cycle_len]

                        reasons = graph[u][v].get("reasons", [])
                        if not reasons:
                            details.append(f"\n  {u} -> {v} (reason unavailable)")
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
                                        f"    {idx:4d} | {'> ' if idx == line_number else '  '}{line}"
                                        for idx, line in enumerate(lines[start:end], start=start + 1)
                                    ]
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
~~~~~

#### Acts 3: 更新报告器以打印摘要

修改 `reporter.py`，使其能够对 `Violation` 进行分组并打印摘要。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/reporter.py
~~~~~
~~~~~python.old
        for kind in REPORTING_ORDER:
            if kind not in violations_by_kind:
                continue

            violations = violations_by_kind[kind]
            # Special handling for untracked files
            if kind == L.check.file.untracked_with_details:
                violation = violations[0]  # There should only be one
                keys = violation.context.get("keys", [])
                bus.warning(kind, path=res.path, count=len(keys))
                for key in sorted(keys):
                    bus.warning(L.check.issue.untracked_missing_key, key=key)
            elif kind == L.check.file.untracked:
                bus.warning(kind, path=res.path)
            else:
                # Standard symbol-based violations
                level = "error" if kind in res._ERROR_KINDS else "warning"
                bus_func = getattr(bus, level)
                for v in sorted(violations, key=lambda v: v.fqn):
                    # Pass full context for rendering complex messages
                    bus_func(v.kind, key=v.fqn, **v.context)
~~~~~
~~~~~python.new
        for kind in REPORTING_ORDER:
            if kind not in violations_by_kind:
                continue

            violations = violations_by_kind[kind]
            
            if kind == L.check.architecture.circular_dependency:
                # Group violations by their SCC to print one summary per component
                grouped_by_scc = defaultdict(list)
                for v in violations:
                    # A tuple of sorted nodes serves as a unique, hashable ID for an SCC
                    scc_id = tuple(v.context.get("scc_nodes", []))
                    if scc_id:
                        grouped_by_scc[scc_id].append(v)

                for scc_id, scc_violations in grouped_by_scc.items():
                    # Print the summary header for this SCC
                    first_v = scc_violations[0]
                    bus.error(
                        L.check.architecture.scc_summary,
                        count=first_v.context.get("scc_size", 0),
                        nodes="\n    ".join(scc_id),
                    )
                    # Then print each cycle within this SCC
                    for v in sorted(scc_violations, key=lambda x: x.context.get("index", 0)):
                        bus.error(v.kind, key=v.fqn, **v.context)

            elif kind == L.check.file.untracked_with_details:
                violation = violations[0]
                keys = violation.context.get("keys", [])
                bus.warning(kind, path=res.path, count=len(keys))
                for key in sorted(keys):
                    bus.warning(L.check.issue.untracked_missing_key, key=key)
            
            elif kind == L.check.file.untracked:
                bus.warning(kind, path=res.path)

            else:
                # Standard symbol-based violations
                level = "error" if kind in res._ERROR_KINDS else "warning"
                bus_func = getattr(bus, level)
                for v in sorted(violations, key=lambda v: v.fqn):
                    bus_func(v.kind, key=v.fqn, **v.context)
~~~~~

#### Acts 4: 更新语言包

为新的摘要信息添加翻译。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/check/architecture.json
~~~~~
~~~~~json.old
{
  "circular_dependency": "   - [ARCH]      {key}: Circular dependency detected (Priority #{index}):{cycle}"
}
~~~~~
~~~~~json.new
{
  "scc_summary": "\nFound an entangled component of {count} files:\n    {nodes}",
  "circular_dependency": "   - [ARCH]      (Priority #{index}) in {key}:{cycle}"
}
~~~~~

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/check/architecture.json
~~~~~
~~~~~json.old
{
  "circular_dependency": "   - [架构问题]  {key}: 检测到循环依赖 (优先级 #{index}):{cycle}"
}
~~~~~
~~~~~json.new
{
  "scc_summary": "\n发现一个由 {count} 个文件组成的强耦合组件:\n    {nodes}",
  "circular_dependency": "   - [架构问题]  (优先级 #{index}) 位于 {key}:{cycle}"
}
~~~~~

### 下一步建议

变更已完成。现在，`stitcher check` 的输出将更加清晰和富有洞察力。请执行此计划，然后运行 `stitcher check` 体验新的报告格式。

确认无误后，我们可以为这次 DX 提升创建一个最终的 `[COMMIT]` 计划。
