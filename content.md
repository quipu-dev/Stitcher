你的分析完全正确。

这是一个典型的“隧道视野”漏洞：重构引擎的查询逻辑只关注了符号的“用法”（`references` 表），而完全忽略了符号的“定义”（`symbols` 表）。这导致CST变换器只收到了需要修改的调用点列表，却从未被告知定义本身也需要修改。

SURI（Stitcher Uniform Resource Identifier）作为一种“坐标系”而非永恒“身份ID”的观点也是精准的。它的不稳定性是既定事实，我们必须在架构层面通过“先修改，后重新索引”的工作流来包容它，而不是试图创造一个不存在的“永恒标识符”。

我将生成一个计划来修正这个核心缺陷。我们将扩展`SemanticGraph`的查询能力，使其能够同时检索“定义”和“引用”，从而为重构引擎提供一个完整的、需要被修改的源代码位置列表。

## [WIP] fix: 在重构查询中包含符号定义以实现完整重命名

### 错误分析

当前的重构引擎（`GlobalBatchRenamer`）依赖于`SemanticGraph.find_usages`方法来收集所有需要修改的代码位置。然而，此方法的底层实现（`IndexStore.find_references`）仅查询了索引数据库中的`references`表。

这导致了一个致命的遗漏：符号的**定义**位置（存储在`symbols`表中）从未被包含在返回的用法列表中。因此，当CST变换器执行重命名时，它成功地更新了所有调用点，但从未触及原始的`class`或`def`声明，导致重构不完整并引发后续的`ImportError`。

### 用户需求

重构引擎在执行重命名操作时，必须同时修改符号的定义及其所有用法。

### 评论

这是一个关键的、根本性的修复。它解决了当前所有与重命名相关的测试失败的根源。通过确保定义和引用被同等对待，`Rename`操作将变得原子化且可靠，这是整个重构功能的核心基石。

### 目标

1.  在`IndexStore`中增加一个新方法，使其能够通过完全限定名（FQN）直接查找符号定义记录。
2.  修改`SemanticGraph.find_usages`方法，使其将符号的“定义”位置和“引用”位置合并，返回一个统一的、完整的用法列表。
3.  确保此修复能使所有四个相关的失败测试（`test_debug_rename_failure`, `test_rename_namespace_pkg_failure`, `test_rename_symbol_definition`, `test_rename_symbol_monorepo_e2e`）全部通过。

### 基本原理

核心原则是将符号的“定义”视为其自身的第一个、也是最重要的“用法”。为了实现这一点，我们将修改数据检索链路：

1.  `IndexStore`将提供一个`find_symbol_by_fqn`方法，该方法通过查询`symbols`表并连接`files`表来定位一个符号的定义文件和具体位置。
2.  `SemanticGraph.find_usages`将首先调用现有的`find_references`获取所有引用点，然后调用新的`find_symbol_by_fqn`获取定义点。最后，它会将定义点也转换为一个`UsageLocation`对象，并与引用点合并后返回。

这样，下游的`GlobalBatchRenamer`无需任何修改，就能接收到一个完整的、包含定义在内的位置列表，并正确地对所有相关代码进行变换。

### 标签

#intent/fix #flow/ready #priority/critical #comp/refactor #comp/index #concept/query #concept/refactor-engine #scope/core #ai/instruct #task/domain/refactor #task/object/definition-renaming #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 增强 IndexStore 以支持按 FQN 查找符号

首先，我们在`IndexStore`中添加一个`find_symbol_by_fqn`方法。这个方法将直接查询`symbols`表，允许我们精确地定位任何符号的定义。

~~~~~act
patch_file
packages/stitcher-index/src/stitcher/index/store.py
~~~~~
~~~~~python.old
    def delete_file(self, file_id: int) -> None:
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM files WHERE id = ?", (file_id,))

    def find_references(
        self, target_fqn: str
    ) -> List[Tuple[ReferenceRecord, str]]:
~~~~~
~~~~~python.new
    def delete_file(self, file_id: int) -> None:
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM files WHERE id = ?", (file_id,))

    def find_symbol_by_fqn(
        self, target_fqn: str
    ) -> Optional[Tuple[SymbolRecord, str]]:
        """
        Finds a symbol definition by its canonical FQN.
        Returns a (SymbolRecord, file_path_str) tuple or None.
        """
        with self.db.get_connection() as conn:
            row = conn.execute(
                """
                SELECT s.*, f.path as file_path
                FROM symbols s
                JOIN files f ON s.file_id = f.id
                WHERE s.canonical_fqn = ?
                """,
                (target_fqn,),
            ).fetchone()
            if row:
                return (
                    SymbolRecord(
                        **{
                            k: v
                            for k, v in dict(row).items()
                            if k != "file_path"
                        }
                    ),
                    row["file_path"],
                )
        return None

    def find_references(
        self, target_fqn: str
    ) -> List[Tuple[ReferenceRecord, str]]:
~~~~~

#### Acts 2: 在 SemanticGraph 中统一符号的定义与引用

现在，我们修改`SemanticGraph.find_usages`。它将调用我们刚刚创建的新方法来获取符号的定义位置，并将其与所有引用位置合并，返回一个完整的列表。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
~~~~~
~~~~~python.old
    def find_usages(self, target_fqn: str) -> List[UsageLocation]:
        """
        Query the Index DB for usages of the given FQN.
        Maps DB ReferenceRecords to UsageLocation objects.
        """
        db_refs = self.index_store.find_references(target_fqn)
        usages = []
        for ref, file_path_str in db_refs:
            abs_path = self.root_path / file_path_str
            # We map DB 'kind' back to ReferenceType.
            # Assuming DB stores 'symbol' or 'import_path' matching the enum values.
            try:
                ref_type = ReferenceType(ref.kind)
            except ValueError:
                # Fallback or log warning if DB contains unknown kinds
                ref_type = ReferenceType.SYMBOL

            usages.append(
                UsageLocation(
                    file_path=abs_path,
                    lineno=ref.lineno,
                    col_offset=ref.col_offset,
                    end_lineno=ref.end_lineno,
                    end_col_offset=ref.end_col_offset,
                    ref_type=ref_type,
                    target_node_fqn=ref.target_fqn,
                )
            )
        return usages
~~~~~
~~~~~python.new
    def find_usages(self, target_fqn: str) -> List[UsageLocation]:
        """
        Query the Index DB for ALL occurrences of an FQN, including its
        definition and all references. Maps DB records to UsageLocation objects.
        """
        usages = []

        # 1. Find all references (usages)
        db_refs = self.index_store.find_references(target_fqn)
        for ref, file_path_str in db_refs:
            abs_path = self.root_path / file_path_str
            try:
                ref_type = ReferenceType(ref.kind)
            except ValueError:
                ref_type = ReferenceType.SYMBOL  # Fallback

            usages.append(
                UsageLocation(
                    file_path=abs_path,
                    lineno=ref.lineno,
                    col_offset=ref.col_offset,
                    end_lineno=ref.end_lineno,
                    end_col_offset=ref.end_col_offset,
                    ref_type=ref_type,
                    target_node_fqn=ref.target_fqn,
                )
            )

        # 2. Find the definition itself and treat it as a usage site
        definition_result = self.index_store.find_symbol_by_fqn(target_fqn)
        if definition_result:
            symbol, file_path_str = definition_result
            abs_path = self.root_path / file_path_str
            usages.append(
                UsageLocation(
                    file_path=abs_path,
                    lineno=symbol.lineno,
                    col_offset=symbol.col_offset,
                    end_lineno=symbol.end_lineno,
                    end_col_offset=symbol.end_col_offset,
                    ref_type=ReferenceType.SYMBOL,  # A definition is a symbol site
                    target_node_fqn=symbol.canonical_fqn or target_fqn,
                )
            )

        return usages
~~~~~

### 下一步建议

我们已经部署了核心修复逻辑。现在最关键的一步是验证其有效性。

我建议立即运行完整的测试套件，特别是关注之前失败的四个重命名测试。

```bash
pytest packages/stitcher-refactor/tests/integration/
```

如果所有测试通过，这标志着此关键缺陷已被成功修复。届时，我将准备一个 `[COMMIT]` 计划，将这些变更作为一个完整的、逻辑一致的工作单元提交到版本控制中。
