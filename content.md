好的，我将实现 `MoveFileOperation`。

这个操作的核心思想是**组合**：它将物理上的文件移动 (`MoveFileOp`) 和逻辑上的符号重命名 (`RenameSymbolOperation`) 结合成一个原子操作。它首先计算出因文件移动导致的所有 FQN (完全限定名) 的变化，然后委托 `RenameSymbolOperation` 去更新整个代码库中对这些 FQN 的引用，最后再添加移动物理文件的指令。

我将创建 `packages/stitcher-refactor/src/stitcher/refactor/operations/move_file.py` 文件并实现其逻辑。

## [WIP] feat(refactor): 实现 MoveFileOperation 以支持文件和符号的原子化移动

### 用户需求

实现 `MoveFileOperation`，使其能够：
1.  接收一个源路径和目标路径。
2.  自动计算因文件移动导致的模块 FQN 变更。
3.  组合 `TransactionManager` 的文件移动指令和 `RenameSymbolOperation` 的符号重命名逻辑，以原子方式更新代码库。

### 评论

这是重构引擎的关键一步，它将简单的文件操作（如 `mv`）提升到了语义层面。通过将文件移动与符号重命名绑定，我们可以确保在调整项目结构时，代码的引用完整性不会被破坏，这是传统重构工具难以做到的。

### 目标

1.  创建 `packages/stitcher-refactor/src/stitcher/refactor/operations/move_file.py` 文件。
2.  实现 `MoveFileOperation` 类，继承自 `AbstractOperation`。
3.  在 `analyze` 方法中，实现 FQN 变更计算逻辑。
4.  在 `analyze` 方法中，调用 `RenameSymbolOperation` 来处理所有受影响符号的引用更新。
5.  在 `analyze` 方法中，为源文件、文档文件和签名文件生成 `MoveFileOp`。

### 基本原理

`MoveFileOperation` 的 `analyze` 方法将遵循以下步骤：
1.  **路径转 FQN**: 实现一个内部辅助函数，将文件路径（例如 `src/mypkg/utils.py`）转换为 Python 模块的 FQN（例如 `mypkg.utils`）。
2.  **计算 FQN 变更**: 使用上述函数计算源路径和目标路径对应的旧、新模块 FQN。
3.  **识别内部符号**: 遍历 `SemanticGraph`，找出所有定义在源文件中的顶层符号（类、函数等）。
4.  **委托重命名**: 对每一个找到的符号，根据旧、新模块 FQN 计算出其 FQN 的变化（例如 `mypkg.utils.MyClass` -> `mypkg.new_utils.MyClass`），然后创建一个 `RenameSymbolOperation` 实例，并调用其 `analyze` 方法。这将生成所有必要的代码文件 (`.py`) 和边车文件 (`.yaml`, `.json`) 的内容更新指令 (`WriteFileOp`)。
5.  **生成移动指令**: 创建 `MoveFileOp` 指令来移动 `.py` 源文件、`.stitcher.yaml` 文档文件和 `.stitcher/signatures/*.json` 签名文件。
6.  **合并结果**: 将所有生成的 `WriteFileOp` 和 `MoveFileOp` 汇总成一个列表并返回，形成一个完整的、事务性的重构计划。

### 标签

#intent/build #flow/ready #priority/high #comp/engine #concept/executor #scope/core #ai/instruct #task/domain/refactor #task/object/move-operation #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建 `move_file.py` 并实现 `MoveFileOperation`

我将创建 `move_file.py` 文件，并实现 `MoveFileOperation` 的完整逻辑。这包括 FQN 计算、组合 `RenameSymbolOperation` 以及处理边车文件的移动。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/operations/move_file.py
~~~~~
~~~~~python
from pathlib import Path
from typing import List

from .base import AbstractOperation
from .rename_symbol import RenameSymbolOperation
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import FileOp, MoveFileOp


class MoveFileOperation(AbstractOperation):
    def __init__(self, src_path: Path, dest_path: Path):
        self.src_path = src_path
        self.dest_path = dest_path

    def _path_to_fqn(self, path: Path, root: Path) -> str:
        """Converts a file path to a Python module FQN."""
        # mypkg/utils.py -> mypkg.utils
        relative_path = path.relative_to(root)
        parts = list(relative_path.parts)
        if parts[-1] == "__init__.py":
            parts.pop()
        else:
            parts[-1] = parts[-1].removesuffix(".py")
        return ".".join(parts)

    def analyze(self, ctx: RefactorContext) -> List[FileOp]:
        ops: List[FileOp] = []
        root = ctx.graph.root_path

        # Ensure paths are relative to the project root for consistency
        src_relative = self.src_path.relative_to(root)
        dest_relative = self.dest_path.relative_to(root)

        # 1. Calculate FQN changes for the module itself
        old_module_fqn = self._path_to_fqn(self.src_path, root)
        new_module_fqn = self._path_to_fqn(self.dest_path, root)

        # 2. Find all symbols defined in the source file and generate rename ops
        # This is the "composition" part of the logic.
        symbols_in_file = [
            s
            for s in ctx.graph.iter_members(old_module_fqn)
            if s.path == self.src_path and s.fqn.startswith(old_module_fqn)
        ]

        for symbol in symbols_in_file:
            # We skip the module itself, as we handle its "renaming" by moving files.
            if symbol.fqn == old_module_fqn:
                continue

            old_symbol_fqn = symbol.fqn
            new_symbol_fqn = old_symbol_fqn.replace(
                old_module_fqn, new_module_fqn, 1
            )

            # Delegate to RenameSymbolOperation to handle all reference updates
            rename_op = RenameSymbolOperation(old_symbol_fqn, new_symbol_fqn)
            ops.extend(rename_op.analyze(ctx))

        # 3. Add file move operations for the source and sidecar files
        ops.append(MoveFileOp(path=src_relative, dest=dest_relative))

        # Handle sidecar files
        doc_src = src_relative.with_suffix(".stitcher.yaml")
        doc_dest = dest_relative.with_suffix(".stitcher.yaml")
        if (root / doc_src).exists():
            ops.append(MoveFileOp(path=doc_src, dest=doc_dest))

        sig_src = Path(".stitcher/signatures") / src_relative.with_suffix(".json")
        sig_dest = Path(".stitcher/signatures") / dest_relative.with_suffix(".json")
        if (root / sig_src).exists():
            ops.append(MoveFileOp(path=sig_src, dest=sig_dest))

        return ops
~~~~~

#### Acts 2: 更新 `operations/__init__.py`

为了方便外部调用，我将 `MoveFileOperation` 导出。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/__init__.py
~~~~~
~~~~~python.old
~~~~~
~~~~~python.new
from .base import AbstractOperation
from .rename_symbol import RenameSymbolOperation
from .move_file import MoveFileOperation

__all__ = ["AbstractOperation", "RenameSymbolOperation", "MoveFileOperation"]
~~~~~

### 下一步建议

我们已经完成了核心重构算子 `RenameSymbolOperation` 和 `MoveFileOperation` 的开发。现在是时候将它们整合到一个面向用户的 API 中了。

我建议进入路线图的**阶段四**：
1.  **设计 `MigrationSpec` API**: 创建一个简单的 Python API，让用户可以声明式地定义重构计划（例如 `spec.add(Move(...))`）。
2.  **实现 CLI 命令**: 创建 `stitcher refactor apply <migration_file.py>` 命令，负责加载这个规范文件，并驱动 `SemanticGraph`, `RefactorContext` 和 `TransactionManager` 完成整个重构流程。
3.  **增加交互式确认**: 在 `TransactionManager.commit()` 执行前，向用户清晰地展示所有待执行的文件操作，并请求确认。

如果你同意，我将开始制定实现 `MigrationSpec` 和 CLI 入口的计划。
