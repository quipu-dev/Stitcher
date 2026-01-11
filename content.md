好的，我完全理解了。

这些测试失败的根本原因高度一致且非常清晰：重构引擎在执行重命名操作时，成功地找到了所有符号的**使用点（usages）**并进行了修改，但唯独遗漏了对符号**定义点（definition）**本身的修改。这是一个核心的逻辑缺陷。

用户的指令“增强 index 的能力”一针见血。当前，我们的索引和图谱查询 (`find_usages`) 只关注“引用”，而没有提供一个直接、可靠的方式来定位符号的“定义”。为了从根本上解决这个问题，我们必须把“定义”也作为索引的一等公民来对待。

我将执行一个计划，通过增强索引、图谱和重构规划器的能力，确保符号定义在重命名过程中被正确处理。

## [WIP] fix: 增强索引以追踪定义，实现可靠的符号重命名

### 错误分析

所有四个失败的测试都暴露了同一个根本问题：`GlobalBatchRenamer` 在收集需要修改的代码位置时，其数据源 (`SemanticGraph.find_usages`) 只返回了符号被引用的位置，而没有包含符号被定义的那一行代码的位置。

因此，当重构事务执行时：
1.  所有 `import` 语句和函数调用都被正确地重命名了。
2.  但 `class OldName: ...` 或 `def old_func(): ...` 这一行定义代码本身，由于从未被加入到待办事项列表中，所以被原封不动地保留了下来。
3.  这导致了代码状态不一致：外部调用一个不再存在的旧名称，或者调用一个新名称但其定义仍然是旧的，从而引发 `AssertionError` 或潜在的 `ImportError`。

这个问题的根源在于索引层 (`IndexStore`) 和图谱层 (`SemanticGraph`) 缺乏一个专门用于查询符号“定义”位置的接口。

### 用户需求

修复所有因“定义未被重命名”而失败的测试。核心需求是让 `Rename` 操作能够原子化地修改一个符号的所有引用以及其定义本身。

### 评论

这是一个典型的“本体论不完备”架构缺陷。系统正确地建模了“是什么”（符号）和“在哪里被使用”（引用），却忽略了“它在哪里被定义”这一关键信息的可查询性。根据 HFEA 协议，我们必须修复这个基础缺陷，而不是在规划器（Planner）层面打补丁。

通过为索引增加直接查询符号定义的能力，我们让索引成为了更完整的“真理单一来源 (SSoT)”，这使得上层逻辑（如重构）可以建立在更确定性的基础之上。

### 目标

1.  **增强 `IndexStore`**: 添加一个 `find_symbol_by_fqn` 方法，使其能够根据完全限定名（FQN）直接查询并返回一个符号的定义记录 (`SymbolRecord`) 及其所在的文件路径。
2.  **增强 `SemanticGraph`**: 添加一个 `find_definition_location` 方法，该方法利用 `IndexStore` 的新能力，将符号的定义位置封装成一个 `UsageLocation` 对象返回。
3.  **修复 `GlobalBatchRenamer`**: 修改其 `analyze` 方法，使其在为每个符号收集使用点（usages）的同时，也主动查询其定义点（definition），并将两者合并，形成一个完整的待修改位置列表。

### 基本原理

我们将通过一条清晰的调用链来解决这个问题：

1.  `GlobalBatchRenamer` 在规划重命名时，除了调用 `graph.find_usages(fqn)`，还将调用新的 `graph.find_definition_location(fqn)`。
2.  `SemanticGraph.find_definition_location` 会委托给 `IndexStore.find_symbol_by_fqn`。
3.  `IndexStore.find_symbol_by_fqn` 执行一个 SQL 查询，直接从 `symbols` 表中通过 `canonical_fqn` 字段定位到唯一的符号定义，并返回其位置信息。
4.  `GlobalBatchRenamer` 将这个“定义位置”与所有“使用位置”一视同仁地添加到按文件分组的待办列表中。
5.  最终，`SymbolRenamerTransformer` 在访问代码时，会发现定义处的代码也匹配上了位置和 FQN，从而正确地将其重命名。

这个方案从数据源头解决了问题，确保了重命名操作的原子性和完整性。

### 标签

#intent/fix #flow/ready #priority/critical #comp/refactor #comp/index #concept/state #scope/core #ai/instruct #task/domain/refactor #task/object/rename-engine #task/action/bug-fix #task-state/continue

---

### Script

#### Acts 1: 增强 `IndexStore`，使其可以直接查询符号定义

首先，我们在 `stitcher-index` 包的 `store.py` 中添加 `find_symbol_by_fqn` 方法。这将为上层提供通过 FQN 直接查找符号定义的能力。

~~~~~act
patch_file
packages/stitcher-index/src/stitcher/index/store.py
~~~~~
~~~~~python.old
    def delete_file(self, file_id: int) -> None:
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
~~~~~
~~~~~python.new
    def delete_file(self, file_id: int) -> None:
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM files WHERE id = ?", (file_id,))

    def find_symbol_by_fqn(
        self, canonical_fqn: str
    ) -> Optional[Tuple[SymbolRecord, str]]:
        """
        Finds a symbol definition by its canonical FQN.
        Returns a tuple of (SymbolRecord, file_path_str).
        """
        with self.db.get_connection() as conn:
            row = conn.execute(
                """
                SELECT s.*, f.path as file_path
                FROM symbols s
                JOIN files f ON s.file_id = f.id
                WHERE s.canonical_fqn = ?
                """,
                (canonical_fqn,),
            ).fetchone()
            if row:
                return (
                    SymbolRecord(
                        **{k: v for k, v in dict(row).items() if k != "file_path"}
                    ),
                    row["file_path"],
                )
        return None
~~~~~

#### Acts 2: 增强 `SemanticGraph`，提供查找定义位置的接口

接下来，我们在 `stitcher-refactor` 包的 `graph.py` 中添加 `find_definition_location` 方法。它将作为 `IndexStore` 和 `GlobalBatchRenamer` 之间的桥梁。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
~~~~~
~~~~~python.old
        return usages

    def get_module(self, package_name: str) -> Optional[griffe.Module]:
        if package_name in self._modules:
~~~~~
~~~~~python.new
        return usages

    def find_definition_location(self, target_fqn: str) -> Optional[UsageLocation]:
        """
        Query the Index DB for the definition location of a given FQN.
        """
        result = self.index_store.find_symbol_by_fqn(target_fqn)
        if not result:
            return None

        symbol, file_path_str = result
        abs_path = self.root_path / file_path_str

        # Adapt SymbolRecord to UsageLocation for the renamer
        return UsageLocation(
            file_path=abs_path,
            lineno=symbol.lineno,
            col_offset=symbol.col_offset,
            end_lineno=symbol.end_lineno,
            end_col_offset=symbol.end_col_offset,
            ref_type=ReferenceType.SYMBOL,  # Treat definition as a symbol reference to itself
            target_node_fqn=target_fqn,
        )

    def get_module(self, package_name: str) -> Optional[griffe.Module]:
        if package_name in self._modules:
~~~~~

#### Acts 3: 修复 `GlobalBatchRenamer`，将定义位置纳入重命名计划

最后，我们修改 `stitcher-refactor` 包中的 `renamer.py`，让它在收集用法的循环中，同时获取并注册符号的定义位置。这是完成修复的关键一步。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/renamer.py
~~~~~
~~~~~python.old
        # 1. Collect all usages for all renames and group by file
        for old_fqn in self.rename_map.keys():
            usages = self.ctx.graph.find_usages(old_fqn)
            for usage in usages:
                usages_by_file[usage.file_path].append(usage)
~~~~~
~~~~~python.new
        # 1. Collect all usages AND the definition for all renames, then group by file
        for old_fqn in self.rename_map.keys():
            # Find all usages (imports, calls, etc.)
            usages = self.ctx.graph.find_usages(old_fqn)
            for usage in usages:
                usages_by_file[usage.file_path].append(usage)

            # CRITICAL FIX: Find the definition location and add it to the list of
            # locations to be transformed.
            definition_location = self.ctx.graph.find_definition_location(old_fqn)
            if definition_location:
                usages_by_file[definition_location.file_path].append(definition_location)
~~~~~

### 下一步建议

我们已经从根本上解决了重构引擎的缺陷。现在，最重要的一步是重新运行测试套件，以验证我们的修复是否覆盖了所有失败的场景，并且没有引入新的回归问题。

我建议你立即执行 `pytest`。如果所有测试通过，我们可以将这个工作单元标记为 `[COMMIT]` 并进行提交。
