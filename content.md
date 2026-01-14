好的，我们来实施这项性能优化。

这是一个关键的修复，它将 `stitcher check` 的架构分析部分从一个指数级复杂度的操作转变为线性复杂度，从而解决了内存和时间的瓶颈问题，同时保留了精确的错误报告能力。

我将生成一个计划来修改循环依赖检测算法。

## [WIP] perf(analysis): 使用强连通分量 (SCC) 优化循环依赖检测

### 用户需求

`stitcher check` 命令在包含 `networkx` 的大型项目中，因循环依赖检测逻辑 (`CircularDependencyRule`) 消耗过多时间和内存而无法完成。需要对该算法进行性能优化，同时不牺牲报告具体循环路径的能力。

### 评论

这是一个典型的算法复杂度问题。当前通过 `networkx.simple_cycles` 枚举所有简单环的策略，在面对大型、高度耦合的依赖图时，会导致组合爆炸。

切换到基于“强连通分量 (Strongly Connected Components, SCC)”的检测策略是解决此类问题的标准工业实践。它将问题的复杂度从指数级降低到线性级，能够从根本上解决性能瓶瓶颈。

### 目标

1.  修改 `stitcher.analysis.graph.algorithms.detect_circular_dependencies` 函数。
2.  用 `networkx.strongly_connected_components` 替代 `networkx.simple_cycles`。
3.  对于每一个找到的强连通分量，仅使用 `networkx.find_cycle` 寻找并报告**一个**代表性的循环路径，而不是所有路径。

### 基本原理

任何循环依赖都必然存在于一个强连通分量 (SCC) 内部。因此，我们可以先用高效的线性时间算法 (如 Tarjan 算法，`nx.strongly_connected_components` 的底层实现) 找出所有 SCCs。

然后，对于每个节点数大于 1 (或有自环) 的 SCC，我们知道其中必定存在环。我们只需通过 `nx.find_cycle` 快速找到其中任意一个环作为证据即可。这避免了对一个组件内可能存在的数百万个环进行无效的枚举，极大地提升了性能和降低了内存消耗，同时报告给用户的环路径样本仍然是有效且可操作的。

### 标签

#intent/refine #flow/ready #priority/high #comp/tests #concept/state #scope/core #ai/instruct #task/domain/analysis #task/object/cycle-detection #task/action/optimize #task/state/begin

---

### Script

#### Acts 1: 替换循环检测算法

我们将重写 `detect_circular_dependencies` 函数，用基于 SCC 的新算法替换旧的暴力枚举算法。

~~~~~act
patch_file
packages/stitcher-analysis/src/stitcher/analysis/graph/algorithms.py
~~~~~
~~~~~python.old
def detect_circular_dependencies(graph: nx.DiGraph) -> List[List[str]]:
    return [list(cycle) for cycle in nx.simple_cycles(graph)]
~~~~~
~~~~~python.new
def detect_circular_dependencies(graph: nx.DiGraph) -> List[List[str]]:
    """
    Detects circular dependencies by finding strongly connected components (SCCs)
    and then sampling one cycle from each non-trivial SCC. This is significantly
    more performant than enumerating all simple cycles.
    """
    cycles = []
    # 1. Find all strongly connected components (SCCs).
    # An SCC is a subgraph where every node is reachable from every other node.
    # Any cycle must exist entirely within an SCC.
    sccs = nx.strongly_connected_components(graph)

    for scc in sccs:
        # A non-trivial SCC (potential for a cycle) has more than one node,
        # or it's a single node that points to itself (a self-loop).
        is_trivial_scc = len(scc) < 2
        if is_trivial_scc:
            # The type hint for scc elements is `Node`, which is generic. In our
            # case, they are strings representing file paths.
            node = list(scc)[0]
            if not graph.has_edge(node, node):
                continue  # Skip single-node SCCs without self-loops.

        # 2. For each non-trivial SCC, find just *one* representative cycle.
        # This avoids the combinatorial explosion of `nx.simple_cycles`.
        scc_subgraph = graph.subgraph(scc)
        try:
            # `find_cycle` is highly optimized to return as soon as it finds any cycle.
            # It returns a list of edges, e.g., [(u, v), (v, w), (w, u)].
            # We respect the original graph's directionality.
            cycle_edges = nx.find_cycle(scc_subgraph, orientation="original")

            # 3. Convert the edge list to a node list to maintain compatibility
            # with the reporting rule, which expects a list of nodes [u, v, w].
            cycle_nodes = [edge[0] for edge in cycle_edges]
            cycles.append(cycle_nodes)

        except nx.NetworkXNoCycle:
            # This should theoretically not happen for a non-trivial SCC,
            # but we include it for robustness.
            pass

    return cycles
~~~~~

### 下一步建议

请执行此计划。计划执行完毕后，我建议你：
1.  重新运行 `stitcher --loglevel debug check` 命令，确认它现在可以快速完成。
2.  （可选）重新运行 `python scripts/profile_stitcher.py check`，观察 `detect_circular_dependencies` 的耗时是否已显著降低。

确认问题解决后，我们可以创建一个 `[COMMIT]` 计划来提交这次重要的性能优化。
