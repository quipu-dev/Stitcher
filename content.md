Excellent. We are now ready to implement the final piece of this feature. By enriching the `local_symbols` map, we will empower the `UsageScanVisitor` to correctly resolve references to imported aliases, thus completing the semantic chain from usage to definition.

Here is the plan for **Atomic Task 4**.

## [WIP] feat(index): Enrich local symbol map to enable alias-aware reference scanning

### 用户需求

根据任务计划，需要实施 **Atomic Task 4**。具体目标是更新 `PythonAdapter._extract_references` 方法，使其在构建 `local_symbols` 映射表时，不仅包含本地定义的符号，还包含所有通过 `import` 语句引入的别名。

### 评论

这是整个别名解析功能中“画龙点睛”的一笔。前续任务让我们能够在数据库中*存储*别名信息，而此任务则让我们能够*利用*这些信息进行真正的语义分析。完成这一步后，系统的引用分析能力将从简单的文本匹配跃升到具备初步上下文感知的水平，为实现高保真的代码导航和重构奠定了坚实的基础。

### 目标

1.  修改 `packages/stitcher-python-adapter/src/stitcher/adapter/python/index_adapter.py` 文件中的 `_extract_references` 方法。
2.  在方法内部，扩展 `local_symbols` 字典的填充逻辑。
3.  遍历 `module.attributes` 和每个 `class.attributes`，检查 `attr.alias_target` 字段。
4.  如果 `attr.alias_target` 存在，则将该别名（`attr.name`）及其指向的完全限定名（`attr.alias_target`）添加到 `local_symbols` 字典中。
5.  确保此增强后的 `local_symbols` 字典被传递给 `UsageScanVisitor`。

### 基本原理

`UsageScanVisitor` 在遍历代码的 AST 时，会遇到各种标识符（`Name` 节点）。它通过查询 `local_symbols` 映射来判断这个标识符究竟指向哪个“真实”的实体。

目前的实现只将文件中*定义*的函数和类放入了 `local_symbols`。这导致当 Visitor 遇到一个*导入*的符号（如 `helper`）时，它在映射表中找不到对应的条目，因而无法解析该引用。

本次修改的核心就是将 `ModuleDef` 中携带的别名信息（`Attribute` with `alias_target`）注入到 `local_symbols` 映射中。例如，对于 `from .utils import helper`，我们将添加一条 `{ "helper": "your_package.utils.helper" }` 的映射。这样，当 Visitor 遇到 `helper()` 的调用时，它就能立即知道这个 `helper` 实际上是 `your_package.utils.helper`，从而创建出一条正确的引用记录。

### 标签

#intent/build #flow/ready #priority/high #comp/core #concept/state #scope/core #ai/instruct #task/domain/testing #task/object/alias-resolution #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 增强 `_extract_references` 以识别别名

我们将精确地 `patch` `_extract_references` 方法，以扩展 `local_symbols` 的填充逻辑。

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/index_adapter.py
~~~~~
~~~~~python.old
    def _extract_references(
        self,
        rel_path: str,
        module: ModuleDef,
        content: str,
        file_path: Path,
        logical_module_fqn: str,
    ) -> List[ReferenceRecord]:
        refs: List[ReferenceRecord] = []

        # 1. Build local_symbols map (Name -> FQN)
        # This helps the visitor distinguish between local usages and globals/builtins
        # The FQN here is logical (e.g. "pkg.mod.Class")
        local_symbols = {}

        # Helper to construct logical FQN for local symbols
        def register_local(name: str, parent_fqn: str = ""):
            fqn = (
                f"{parent_fqn}.{name}" if parent_fqn else f"{logical_module_fqn}.{name}"
            )
            local_symbols[name] = fqn
            return fqn

        for func in module.functions:
            register_local(func.name)

        for cls in module.classes:
            for method in cls.methods:
                # Assuming UsageScanVisitor handles attribute lookups,
                # strictly speaking we might not need to pass method names as locals
                # unless they are used unqualified (which they aren't, they are self.x),
                # but registering top-level classes/funcs is key.
                pass

        # 2. Parse CST and Run Visitor
        try:
~~~~~
~~~~~python.new
    def _extract_references(
        self,
        rel_path: str,
        module: ModuleDef,
        content: str,
        file_path: Path,
        logical_module_fqn: str,
    ) -> List[ReferenceRecord]:
        refs: List[ReferenceRecord] = []

        # 1. Build local_symbols map (Name -> FQN)
        # This helps the visitor distinguish between local usages and globals/builtins.
        # It maps a name visible in the current scope to its fully-qualified name.
        local_symbols = {}

        # 1a. Register all imported aliases (e.g., 'helper' -> 'pkg.utils.helper')
        for attr in module.attributes:
            if attr.alias_target:
                local_symbols[attr.name] = attr.alias_target

        # 1b. Register all local definitions
        def register_local(name: str, parent_fqn: str = "") -> str:
            fqn = (
                f"{parent_fqn}.{name}" if parent_fqn else f"{logical_module_fqn}.{name}"
            )
            local_symbols[name] = fqn
            return fqn

        for func in module.functions:
            register_local(func.name)

        for cls in module.classes:
            cls_fqn = register_local(cls.name)
            # Register class-level aliases
            for attr in cls.attributes:
                if attr.alias_target:
                    local_symbols[attr.name] = attr.alias_target
            # Methods are handled by the visitor's scope analysis (e.g., self.method)
            # so we don't need to register them as top-level local symbols.

        # 2. Parse CST and Run Visitor
        try:
~~~~~

### 下一步建议

我们已经完成了别名解析和引用分析的核心逻辑实现。整个功能链条（`Parser -> IR -> Adapter -> Index`）现在已经贯通。

**现在，最关键的下一步是验证。**

我强烈建议编写一个或多个集成测试来端到端地验证这个新功能。一个好的测试用例应该包含：

1.  一个定义了函数/类的 `utils.py` 文件。
2.  一个 `main.py` 文件，其中包含：
    *   `import utils`
    *   `from utils import specific_function`
    *   `from . import sibling` (如果适用)
    *   对上述导入符号的调用。
3.  测试逻辑应该：
    *   创建一个包含这些文件的测试工作区。
    *   运行 `WorkspaceScanner`。
    *   查询 `IndexStore` 并断言：
        *   `main.py` 的符号表中包含了 `kind='alias'` 的 `SymbolRecord`。
        *   这些别名记录的 `alias_target_id` 正确指向了 `utils.py` 中对应符号的 SURI。
        *   `main.py` 的引用表中包含了从*调用点*到*别名符号*的 `ReferenceRecord`。

这将确保我们所做的所有修改都能协同工作，并真正解决了最初的技术债务。如果你同意，我将开始设计并实施这个集成测试。
