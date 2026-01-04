简要回答
问题确实在于 `_UsageVisitor` 过于简单，只扫描了 `visit_Name`，因此无法处理 `Attribute` 链（如 `mypkg.core.OldHelper`）和 `ImportFrom` 语句中的原始名称（如 `OldHelper`）。

我们将增强 `_UsageVisitor`，使其能够：
1.  **解析 `ImportFrom`**: 结合模块路径和导入名称，合成完整的 FQN 并注册引用。
2.  **解析 `Attribute`**: 利用 LibCST 的辅助函数提取属性全名，并根据本地符号表（`local_symbols`）解析其基底（Base），从而推导出完整的 FQN。

## [WIP] fix: 增强 UsageVisitor 以支持 Attribute 和 ImportFrom

### 用户需求
修复集成测试失败，确保 `UsageRegistry` 能够正确识别属性访问 (`a.b.c`) 和 `from ... import` 语句中的符号引用。

### 评论
这是重构引擎达到“可用”状态的关键一步。通过支持这些常见的 Python 模式，我们将不仅能重命名本地变量，还能重命名跨模块的 API 调用，这才是自动化重构的真正价值所在。

### 目标
1.  修改 `packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py`。
2.  在 `_UsageVisitor` 中增加 `visit_ImportFrom` 方法。
3.  在 `_UsageVisitor` 中增加 `visit_Attribute` 方法。
4.  引入 `libcst.helpers.get_full_name_for_node` 辅助函数。

### 基本原理
-   **ImportFrom**: `from pkg import A`。这里 `A` 的 FQN 是 `pkg.A`。我们需要注册 `A` 这个节点的引用。
-   **Attribute**: `pkg.A`。这里 `pkg` 是本地符号，解析为 FQN `pkg`。组合后得到 `pkg.A`。我们需要注册 `A` 这个节点的引用（注意：对于重命名来说，我们通常只重命名链条末端的 `Name` 节点，或者整条链。LibCST Transformer 的设计是针对特定位置的 `Name` 节点，所以我们必须精确定位到 `A`）。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #task/domain/refactor #task/object/usage-visitor #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 增强 graph.py 中的 _UsageVisitor
我们引入 `libcst.helpers` 并扩展 Visitor。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
~~~~~
~~~~~python.old
import libcst as cst
from libcst.metadata import PositionProvider
from dataclasses import dataclass, field
~~~~~
~~~~~python.new
import libcst as cst
from libcst import helpers
from libcst.metadata import PositionProvider
from dataclasses import dataclass, field
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
~~~~~
~~~~~python.old
    def visit_Name(self, node: cst.Name):
        # In LibCST, Name nodes appear in definitions (ClassDef.name), 
        # references (a = 1), and aliases (import x as y).
        target_fqn = self.local_symbols.get(node.value)
        if target_fqn:
            pos = self.get_metadata(PositionProvider, node)
            # CodeRange is 1-based line, 0-based column.
            loc = UsageLocation(
                file_path=self.file_path,
                lineno=pos.start.line,
                col_offset=pos.start.column,
                end_lineno=pos.end.line,
                end_col_offset=pos.end.column
            )
            self.registry.register(target_fqn, loc)
~~~~~
~~~~~python.new
    def _register_node(self, node: cst.CSTNode, fqn: str):
        pos = self.get_metadata(PositionProvider, node)
        loc = UsageLocation(
            file_path=self.file_path,
            lineno=pos.start.line,
            col_offset=pos.start.column,
            end_lineno=pos.end.line,
            end_col_offset=pos.end.column
        )
        self.registry.register(fqn, loc)

    def visit_Name(self, node: cst.Name):
        # In LibCST, Name nodes appear in definitions (ClassDef.name), 
        # references (a = 1), and aliases (import x as y).
        target_fqn = self.local_symbols.get(node.value)
        if target_fqn:
            self._register_node(node, target_fqn)

    def visit_ImportFrom(self, node: cst.ImportFrom) -> Optional[bool]:
        # Handle: from mypkg.core import OldHelper [as OH]
        # We want to register the usage of 'OldHelper' (the name in the import list)
        
        # 1. Resolve the module part
        if not node.module:
            # Relative import without base? e.g. "from . import x"
            # Griffe might resolve this via local context, but CST is purely syntactic.
            # However, for simple absolute imports, we can extract the name.
            # Handling relative imports properly requires knowing the current module's FQN.
            # For MVP, we'll try to rely on simple resolution or skip relative if complex.
            # But wait, local_symbols might have the module? No.
            # Let's try to reconstruct absolute import if possible, or skip.
            # For `from mypkg.core ...`
            pass
        
        module_name = helpers.get_full_name_for_node(node.module) if node.module else None
        
        if module_name:
            # If relative import (starts with .), we need context. 
            # Assuming absolute for now or basic relative handling if we knew package structure.
            # BUT, we can iterate imported names.
            pass

        # Strategy: We look at the names being imported.
        for alias in node.names:
            if isinstance(alias, cst.ImportAlias):
                name_node = alias.name
                imported_name = helpers.get_full_name_for_node(name_node)
                
                # Construct candidate FQN
                # If module_name is "mypkg.core" and imported_name is "OldHelper" -> "mypkg.core.OldHelper"
                # Note: This misses relative imports resolution (from . import X).
                # To support relative imports properly, we'd need to know the current file's module FQN.
                # Let's assume absolute imports for this test case first.
                if module_name and imported_name:
                    full_fqn = f"{module_name}.{imported_name}"
                    self._register_node(name_node, full_fqn)

        # We allow visiting children to handle AsName if it's a Name? 
        # Actually visit_Name handles the alias target (as OH) if it's used later?
        # No, visit_Name handles usages of OH.
        # We just registered the Definition/Reference of OldHelper in the import statement.
        return True

    def visit_Attribute(self, node: cst.Attribute) -> Optional[bool]:
        # Handle: mypkg.core.OldHelper
        # This comes in as Attribute(value=..., attr=Name(OldHelper))
        
        # We try to resolve the full name of the expression
        full_name = helpers.get_full_name_for_node(node)
        if not full_name:
            return True
            
        # full_name is e.g. "mypkg.core.OldHelper"
        # We check if the 'base' of this chain matches a local symbol.
        # e.g. split by dots. "mypkg" -> checks local_symbols.
        
        parts = full_name.split(".")
        if not parts:
            return True
            
        root_name = parts[0]
        root_fqn = self.local_symbols.get(root_name)
        
        if root_fqn:
            # Reconstruct the absolute FQN
            # if root_name="mypkg" maps to "mypkg", then "mypkg.core.OldHelper" -> "mypkg.core.OldHelper"
            # if root_name="m" maps to "mypkg", then "m.core.OldHelper" -> "mypkg.core.OldHelper"
            
            suffix = ".".join(parts[1:])
            absolute_fqn = f"{root_fqn}.{suffix}" if suffix else root_fqn
            
            # We want to register the `attr` node (the last part) as a usage of this absolute FQN.
            # because RenameTransformer targets the specific Name node.
            # node.attr is the Name node for the last part.
            self._register_node(node.attr, absolute_fqn)
            
        return True
~~~~~

### 下一步建议
如果这个补丁能通过测试，我们的重构引擎就正式完成了对 Attribute 和 Import 的支持。这将是一个巨大的进步。

接下来，我们将进入 **`MoveFileOperation`** 的开发。由于我们已经解决了最难的“如何找到并重命名所有引用”的问题，文件移动操作将主要集中在：
1.  **路径计算**: 确定新旧路径。
2.  **FQN 推导**: 计算移动前后的模块 FQN。
3.  **组合拳**: 调用 `TransactionManager` 移动文件，同时调用 `RenameSymbolOperation`（内部逻辑）更新所有对该模块及其内容的引用。
