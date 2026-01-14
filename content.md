## [WIP] feat(analysis): 引入迭代式最短环检测算法 (Iterative Shortest Cycle Removal)

### 用户需求

1.  **解决单一环反馈不足的问题**: 用户指出目前的检测虽然快，但一次只报一个环，无法提供完整的修复路线图。
2.  **提供最短实施路线图**: 希望 Stitcher 能通过算法提供一组“最小切割集”，即修完这些就能消除所有环。
3.  **算法模块化**: 建议将算法逻辑抽取到独立的包中，为未来的 SDK 做准备。
4.  **更新语言包**: 确保输出信息能反映新的“路线图”或优先级特性。

### 评论

这是一个极具价值的反馈，将静态分析工具从单纯的“报错”提升到了“辅助修复”的层次。

为了实现“最短实施路线图”，我将实施 **Iterative Shortest Cycle Removal (ISCR)** 启发式算法：
1.  在 SCC 中寻找**最短**的环（通常是最根本的耦合）。
2.  报告该环。
3.  虚拟切断该环的一条边（模拟修复）。
4.  重复此过程直到 SCC 被解开。

这将生成一个有序的修复列表，用户按顺序处理往往能获得最高的修复效率（多米诺效应）。同时，我将创建一个新的子包 `algo` 来容纳这些核心图算法。

### 目标

1.  创建 `stitcher.analysis.graph.algo` 子包。
2.  实现 `detect_circular_dependencies` 的 ISCR 算法版本。
3.  更新 `CircularDependencyRule` 以向 Violation 上下文注入 `index` (优先级)。
4.  更新中英文语言包，在报错信息中体现 `Priority #{index}`，强化“路线图”的心智模型。

### 基本原理

*   **最短环优先**: 长环往往是由短环（如 A<->B）引起的。优先修复短环能最大程度简化图结构。
*   **虚拟修复模拟**: 通过在图副本上移除边来模拟用户的修复行为，从而能够发现被当前环“掩盖”的其他独立环，提供完整的视野。
*   **算法隔离**: 将纯粹的图算法与业务规则 (`rules/`) 和基础设施 (`builder.py`) 分离，符合关注点分离原则，也方便未来复用。

### 标签

#intent/build #flow/ready #priority/high #comp/runtime #concept/history #scope/core #ai/instruct #task/domain/analysis #task/object/cycle-detection #task/action/optimize #task/state/continue

---

### Script

#### Acts 1: 创建算法子包及核心算法

首先创建新的包结构，并实现 `Iterative Shortest Cycle Removal` 算法。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/stitcher-analysis/src/stitcher/analysis/graph/algo
~~~~~

~~~~~act
write_file
packages/stitcher-analysis/src/stitcher/analysis/graph/algo/__init__.py
~~~~~
~~~~~python
from .cycles import detect_circular_dependencies

__all__ = ["detect_circular_dependencies"]
~~~~~

~~~~~act
write_file
packages/stitcher-analysis/src/stitcher/analysis/graph/algo/cycles.py
~~~~~
~~~~~python
import networkx as nx
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


def _find_shortest_cycle_in_subgraph(graph: nx.DiGraph) -> List[str]:
    """
    Finds the shortest cycle in the graph by iterating over all edges (u, v)
    and finding the shortest path from v to u.
    Returns the list of nodes in the cycle: [n1, n2, ... nk].
    """
    best_cycle: Optional[List[str]] = None

    # We iterate over edges. If an edge (u, v) is part of a cycle,
    # there must be a path v -> ... -> u.
    # The cycle length would be len(path) + 1.
    for u, v in graph.edges():
        # Optimization: If we already found a cycle of length 2 (A <-> B),
        # it is impossible to find shorter. Stop immediately.
        if best_cycle and len(best_cycle) == 2:
            return best_cycle

        try:
            # BFS for shortest path from target(v) back to source(u)
            path = nx.shortest_path(graph, source=v, target=u)
            
            # If path is [v, x, u], and we have edge (u, v).
            # The full cycle sequence is v -> x -> u -> v.
            # The node list representation is [v, x, u].
            
            if best_cycle is None or len(path) < len(best_cycle):
                best_cycle = path

        except nx.NetworkXNoPath:
            continue

    return best_cycle if best_cycle else []
~~~~~

#### Acts 2: 集成算法到 Facade

修改原有的 `algorithms.py`，使其委托给新的算法包。

~~~~~act
write_file
packages/stitcher-analysis/src/stitcher/analysis/graph/algorithms.py
~~~~~
~~~~~python
from typing import List
import networkx as nx
from .algo.cycles import detect_circular_dependencies


def has_path(graph: nx.DiGraph, source: str, target: str) -> bool:
    return nx.has_path(graph, source, target)


# Re-export for compatibility
__all__ = ["detect_circular_dependencies", "has_path"]
~~~~~

#### Acts 3: 更新规则逻辑注入优先级

修改 `circular_dependency.py`，在生成 Violation 时注入 `index`。

~~~~~act
patch_file
packages/stitcher-analysis/src/stitcher/analysis/rules/architecture/circular_dependency.py
~~~~~
~~~~~python.old
        for cycle in cycles:
            # Create a human-readable representation of the cycle
            # cycle is a list of nodes [n1, n2, n3] representing n1->n2->n3->n1

            details = []
~~~~~
~~~~~python.new
        for index, cycle in enumerate(cycles, start=1):
            # Create a human-readable representation of the cycle
            # cycle is a list of nodes [n1, n2, n3] representing n1->n2->n3->n1

            details = []
~~~~~

~~~~~act
patch_file
packages/stitcher-analysis/src/stitcher/analysis/rules/architecture/circular_dependency.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
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

#### Acts 4: 更新语言包

更新语言包以显示优先级信息。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/check/architecture.json
~~~~~
~~~~~json.old
{
  "circular_dependency": "   - [ARCH]      {key}: Circular dependency detected:{cycle}"
}
~~~~~
~~~~~json.new
{
  "circular_dependency": "   - [ARCH]      {key}: Circular dependency detected (Priority #{index}):{cycle}"
}
~~~~~

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/check/architecture.json
~~~~~
~~~~~json.old
{
  "circular_dependency": "   - [架构问题]  {key}: 检测到循环依赖:{cycle}"
}
~~~~~
~~~~~json.new
{
  "circular_dependency": "   - [架构问题]  {key}: 检测到循环依赖 (优先级 #{index}):{cycle}"
}
~~~~~

### 下一步建议

现在 `stitcher check` 应该能够：
1.  极其快速地运行（得益于 SCC 预筛选）。
2.  为每个复杂的依赖团块提供一份有序的“拆弹指南”，优先列出最短的环。

建议再次运行 `stitcher --loglevel debug check` 来验证输出的格式和速度。
