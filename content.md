You are correct. My apologies for the malformed command. That was a critical error on my part. I failed to provide the necessary `old_str` and `new_str` arguments for the `patch_file` operations, which is a direct violation of the command's contract.

I will now correct this mistake and provide the complete, valid plan.

## [WIP] feat(analysis): 增强循环依赖检测的可观测性 (Corrected)

### 错误分析

我之前生成的 `patch_file` 指令缺少了必需的 `old_str` 和 `new_str` 参数，导致执行失败。这表明我在生成指令时疏忽了，没有遵循 `d1-quipu-command-reference-D1` 中定义的指令集规范。

### 用户需求

在架构检查报告中，针对每一个循环依赖链中的每一跳，提供具体的“证据”：
1.  触发依赖的源代码行号。
2.  触发依赖的具体符号（`target_fqn`）。

### 评论

这不仅是一个 Debug 工具，更是架构治理的长效机制。它将把“这里有个环”这种模糊的报警，转化为“你在 A 文件第 10 行导入了 B 文件的 X 符号，构成了环”这种可行动的洞察。

### 目标

1.  修改 `GraphBuilder`：在构建图的边（Edge）时，附带元数据（Metadata），记录导致该边产生的所有引用详情（行号、符号）。
2.  修改 `CircularDependencyRule`：在格式化错误消息时，从图中提取并展示这些元数据。

### 基本原理

我们将利用 `networkx` 的边属性功能。当 `GraphBuilder` 添加边时，它不再只是建立连接，而是会挂载一个 `causes` 列表。
- 如果 A 引用了 B 中的 `Sym1`，边 A->B 将被创建，`causes` 为 `[{sym: Sym1, line: 10}]`。
- 如果 A 稍后又引用了 B 中的 `Sym2`，边 A->B 保持不变，但 `causes` 列表将追加新记录。

### 标签

#intent/tooling #flow/ready #priority/high #comp/engine #concept/graph #scope/core #ai/instruct #task/domain/analysis #task/object/graph-builder #task/action/enhance-observability #task/state/continue

---

### Script

#### Acts 1: 让 GraphBuilder 记录边的成因

我们将修改 `GraphBuilder`，使其在添加边时记录 `target_fqn` 和 `lineno`。

~~~~~act
patch_file
packages/stitcher-analysis/src/stitcher/analysis/graph/builder.py
~~~~~
~~~~~python.old
            # Add edge if the target is an internal, resolved file
            if target_path and source_path != target_path:
                graph.add_edge(source_path, target_path)
~~~~~
~~~~~python.new
            # Add edge if the target is an internal, resolved file
            if target_path and source_path != target_path:
                if not graph.has_edge(source_path, target_path):
                    graph.add_edge(source_path, target_path, reasons=[])

                # Attach the reason for this specific dependency edge
                reason = f"{edge.target_fqn} (L{edge.lineno})"
                graph[source_path][target_path]["reasons"].append(reason)
~~~~~

#### Acts 2: 让 CircularDependencyRule 展示成因

我们将修改规则，使其在报告环路时，打印出每一跳的具体原因。为了保持日志整洁，我们只打印每个连接的前 3 个原因。

~~~~~act
patch_file
packages/stitcher-analysis/src/stitcher/analysis/rules/architecture/circular_dependency.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
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
~~~~~

### 下一步建议

现在指令已经修正，请执行它。

执行成功后，请再次运行 `stitcher check`。这次的错误报告将为我们提供解开循环依赖谜题所需的详细线索。
