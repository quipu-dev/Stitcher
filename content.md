好的，我们来实施这个更完善的解决方案。

这个计划将彻底改变循环依赖检测的用户体验，从报告单一、任意的错误，升级为对整个耦合组件的精确诊断，并提供最优的修复切入点。

我将生成一个计划来修改算法和报告逻辑。

## [WIP] refactor(analysis): 改进循环依赖报告以诊断整个耦合组件

### 用户需求

当前的循环依赖检测算法虽然性能高，但用户体验不佳。它为每个紧密耦合的组件（SCC）只报告一个任意的环，这掩盖了问题的全部范围，并且提供的修复路径可能是次优的。

需要改进算法，使其能够：
1.  明确报告构成一个耦合组件的**所有文件**。
2.  提供该组件内**最短的循环路径**作为最清晰、最易于修复的证据。

### 评论

这是一个从“能用”到“好用”的关键迭代。简单地报告错误是不够的，我们的工具必须提供**可操作的、富有洞察力的诊断信息**。将报告的焦点从“一个环”转移到“一个耦合组件”，并提供最短环作为“证据”，这能极大地提升开发者定位和解决架构问题的效率，彻底根除“打地鼠”式的修复体验。

### 目标

1.  **重构算法层**:
    *   在 `stitcher.analysis.graph.algorithms` 中，创建一个新的辅助函数 `find_shortest_cycle`，它使用广度优先搜索 (BFS) 来寻找一个 SCC 内的最短环。
    *   修改主检测函数，使其返回每个耦合组件（SCC）的完整节点集合以及对应的最短环路径。
2.  **更新规则层**:
    *   修改 `stitcher.analysis.rules.architecture.circular_dependency` 中的 `check` 方法。
    *   让它能处理新的返回结构（组件+环）。
    *   生成全新的、信息更丰富的诊断消息，明确列出耦合组件中的所有文件，并展示最短环作为修复示例。

### 基本原理

我们继续沿用高效的强连通分量 (SCC) 检测作为第一步。对于识别出的每一个非平凡 SCC，我们不再满足于 `nx.find_cycle` 找到的任意环。取而代之，我们实现一个基于广度优先搜索 (BFS) 的最短环查找算法。通过遍历 SCC 中的每个节点作为起点进行 BFS，我们可以保证找到该组件中的一个全局最短环。

最终，我们将这个最短环和构成该 SCC 的所有文件列表一起呈现给用户。这提供了完整的上下文（“哪些文件有问题？”）和最佳的切入点（“从哪里开始修复最简单？”），从而将一个简单的错误报告升级为一个强大的架构诊断工具。

### 标签

#intent/refine #flow/ready #priority/high #scope/core #scope/dx #ai/instruct #task/domain/analysis #task/object/cycle-detection #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 实现最短环检测算法

我们将完全替换 `algorithms.py` 中的检测逻辑，引入 `find_shortest_cycle` 辅助函数，并让主函数返回更丰富的数据结构。由于改动幅度较大，我们使用 `write_file`。

~~~~~act
write_file
packages/stitcher-analysis/src/stitcher/analysis/graph/algorithms.py
~~~~~
~~~~~python
from typing import List, Set, Tuple
import networkx as nx


def find_shortest_cycle(graph: nx.DiGraph) -> List[str]:
    """
    Finds one of the shortest cycles in a given directed graph component.
    This implementation iterates through each node and performs a BFS to find
    the shortest cycle starting and ending at that node.
    """
    shortest_cycle = None
    nodes = list(graph.nodes)

    for start_node in nodes:
        # BFS implementation to find the shortest path back to start_node
        # queue stores tuples of (node, path_list)
        queue: List[Tuple[str, List[str]]] = [(start_node, [start_node])]
        visited = {start_node}

        head = 0
        while head < len(queue):
            current_node, path = queue[head]
            head += 1

            # If we've already found a cycle and the current path is longer,
            # we can prune this search branch.
            if shortest_cycle is not None and len(path) >= len(shortest_cycle):
                continue

            for neighbor in graph.successors(current_node):
                if neighbor == start_node:
                    # Found a cycle. Since we are using BFS, this is the shortest
                    # cycle starting and ending at `start_node`.
                    found_cycle = path
                    if shortest_cycle is None or len(found_cycle) < len(shortest_cycle):
                        shortest_cycle = found_cycle
                    # Break from the inner loop to not explore further from this node
                    # as we already found the shortest cycle from it.
                    break
                
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
            else:
                # This `else` belongs to the `for` loop. It continues if `break` was not hit.
                continue
            # This `break` belongs to the `while` loop.
            break
            
    return shortest_cycle if shortest_cycle else []


def detect_circular_dependencies(graph: nx.DiGraph) -> List[Tuple[Set[str], List[str]]]:
    """
    Detects circular dependencies by finding strongly connected components (SCCs)
    and then finding the shortest cycle within each non-trivial SCC.
    
    Returns:
        A list of tuples, where each tuple contains:
        - A set of strings representing all nodes in the coupled component (SCC).
        - A list of strings representing the nodes in the shortest found cycle.
    """
    problematic_components = []
    sccs = nx.strongly_connected_components(graph)

    for scc in sccs:
        is_trivial_scc = len(scc) < 2
        if is_trivial_scc:
            node = list(scc)[0]
            if not graph.has_edge(node, node):
                continue

        scc_subgraph = graph.subgraph(scc)
        shortest_cycle_nodes = find_shortest_cycle(scc_subgraph)

        if shortest_cycle_nodes:
            problematic_components.append((scc, shortest_cycle_nodes))

    return problematic_components
~~~~~

#### Acts 2: 更新规则以报告耦合组件和最短环

现在，我们将更新 `CircularDependencyRule` 来使用新的算法并生成更详细的报告。

~~~~~act
patch_file
packages/stitcher-analysis/src/stitcher/analysis/rules/architecture/circular_dependency.py
~~~~~
~~~~~python.old
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
                    context={"cycle": cycle_path},
                )
            )
        return violations
~~~~~
~~~~~python.new
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
~~~~~

#### Acts 3: 更新语言包以反映新的报告格式

旧的 `circular_dependency` 消息格式 (`{key}: Circular dependency detected:{cycle}`) 不再适用。我们需要一个新的格式，它只接受一个 `details` 参数。

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
  "circular_dependency": "   - [ARCH]      {key}:{details}"
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
  "circular_dependency": "   - [架构问题]  {key}:{details}"
}
~~~~~

### 下一步建议

请执行此计划。计划执行后，再次运行 `stitcher check`。你现在应该能看到全新的、信息更丰富的循环依赖报告，它会明确指出所有耦合的文件，并提供最短的环路作为证据。

确认输出符合预期后，我们就可以为这次重构创建一个最终的 `[COMMIT]` 计划了。
