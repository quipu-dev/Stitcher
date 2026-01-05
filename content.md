# [WIP] fix: 优化脚手架逻辑并排查 Init 更新问题

### 用户需求
1.  **修复过度脚手架化**: 禁止在非 Source Root 子目录下（如 `packages/` 或 `src/` 根目录）创建 `__init__.py`。
2.  **修复 `__init__.py` 导入未更新**: 调查并修复当移动被 `__init__.py` 相对引用的模块时，引用未更新的问题。

### 评论
过度脚手架化会破坏项目结构，必须引入 `Search Paths` (Source Roots) 作为边界条件。
关于 `__init__.py` 的问题，我们需要先通过一个精确的测试来复现它，确认是否是 `SymbolRenamer` 在处理包级相对导入时的边缘情况。

### 目标
1.  修改 `MoveFileOperation` 和 `MoveDirectoryOperation` 的 `_scaffold_init_files` 方法，使其依赖 `RefactorContext` 中的 `search_paths` 进行边界判断。
2.  添加 `test_bug_init_relative_import.py` 来复现 `__init__.py` 更新失败的场景。

### 基本原理
**脚手架逻辑优化**:
仅当目标路径位于某个已知的 Source Root 内时，才开始向上遍历创建 `__init__.py`，并且遍历必须在到达 Source Root 时停止（不包括 Source Root 本身）。

**Init 更新排查**:
构建一个包含 `__init__.py` 和相对导入的最小复现环境。如果测试失败，我们将定位到 `_UsageVisitor` 或 Transformer 的具体逻辑缺陷。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/refactor #scope/core #ai/instruct #task/domain/refactoring #task/object/scaffold-logic #task/action/refine #task/state/continue

---

### Script

#### Acts 1: 创建 Init 相对导入复现测试

~~~~~act
write_file
packages/stitcher-refactor/tests/integration/test_bug_init_relative_import.py
~~~~~
~~~~~python
import pytest
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import (
    TransactionManager,
    MoveFileOp,
    WriteFileOp,
)
from stitcher.refactor.operations.move_file import MoveFileOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.refactor.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory


def test_move_module_referenced_by_init_relative_import(tmp_path):
    """
    Reproduces the bug where 'from .module import X' in __init__.py 
    is not updated when 'module.py' is moved.
    """
    # 1. ARRANGE
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_pyproject(".")
        .with_source(
            "mypkg/__init__.py",
            "from .core import MyClass\n\n__all__ = ['MyClass']",
        )
        .with_source("mypkg/core.py", "class MyClass: pass")
        .build()
    )

    src_path = project_root / "mypkg/core.py"
    dest_path = project_root / "mypkg/services/core.py"
    init_path = project_root / "mypkg/__init__.py"

    # 2. ACT
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace)
    graph.load("mypkg")
    
    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace, graph=graph, sidecar_manager=sidecar_manager
    )

    op = MoveFileOperation(src_path, dest_path)
    file_ops = op.analyze(ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        else:
            tm.add_write(fop.path, fop.content)
    tm.commit()

    # 3. ASSERT
    updated_init = init_path.read_text()
    
    # We expect the import to be updated to absolute path or correct relative path
    # Given our recent fix, it should be absolute: 'from mypkg.services.core import MyClass'
    print(f"DEBUG: Updated __init__.py content:\n{updated_init}")
    
    assert "from mypkg.services.core import MyClass" in updated_init or \
           "from .services.core import MyClass" in updated_init, \
           "Import in __init__.py was not updated!"
~~~~~

#### Acts 2: 修正 MoveFileOperation 的脚手架逻辑

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/move_file.py
~~~~~
~~~~~python.old
        # 4. Scaffold missing __init__.py files for the destination
        # This ensures that moving a file to a new deep directory structure
        # maintains a valid Python package hierarchy.
        scaffold_ops = self._scaffold_init_files(self.dest_path, root)
        
        return content_update_ops + rename_ops + move_ops + scaffold_ops

    def _scaffold_init_files(self, file_path: Path, root: Path) -> List[FileOp]:
        ops: List[FileOp] = []
        parent = file_path.parent
        
        # Traverse up until we hit the root
        while parent != root and parent.is_relative_to(root):
            init_file = parent / "__init__.py"
            # We assume if it doesn't exist on disk, we need to create it.
            # NOTE: In a complex transaction, another op might have created it,
            # or it might be deleted. But adding a duplicate WriteFileOp for an empty
            # __init__.py is generally safe or can be deduped by TransactionManager if needed.
            # Here we just check physical existence.
            if not init_file.exists():
                ops.append(
                    WriteFileOp(
                        path=init_file.relative_to(root),
                        content=""
                    )
                )
            
            parent = parent.parent
            
        return ops
~~~~~
~~~~~python.new
        # 4. Scaffold missing __init__.py files for the destination
        # This ensures that moving a file to a new deep directory structure
        # maintains a valid Python package hierarchy.
        scaffold_ops = self._scaffold_init_files(self.dest_path, ctx)
        
        return content_update_ops + rename_ops + move_ops + scaffold_ops

    def _scaffold_init_files(self, file_path: Path, ctx: RefactorContext) -> List[FileOp]:
        ops: List[FileOp] = []
        parent = file_path.parent
        root = ctx.graph.root_path
        search_paths = ctx.graph.search_paths

        # Determine the effective source root for this file
        active_root = None
        for sp in search_paths:
            if file_path.is_relative_to(sp):
                # Pick the deepest matching search path (e.g. prefer src/pkg over src)
                if active_root is None or len(sp.parts) > len(active_root.parts):
                    active_root = sp
        
        # If the file is not inside any known source root, do NOT scaffold.
        # This prevents creating __init__.py in root dirs like 'packages/' or 'tests/'.
        if not active_root:
            return []

        # Traverse up until we hit the active_root
        # IMPORTANT: We stop BEFORE processing the active_root itself.
        # (e.g. we don't want to create src/__init__.py)
        while parent != active_root and parent.is_relative_to(active_root):
            init_file = parent / "__init__.py"
            if not init_file.exists():
                ops.append(
                    WriteFileOp(
                        path=init_file.relative_to(root),
                        content=""
                    )
                )
            
            parent = parent.parent
            
        return ops
~~~~~

#### Acts 3: 修正 MoveDirectoryOperation 的脚手架逻辑

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/move_directory.py
~~~~~
~~~~~python.old
        # 4. Scaffold missing __init__.py files for the destination root
        scaffold_ops = self._scaffold_init_files(self.dest_dir, root)

        return all_ops + scaffold_ops

    def _scaffold_init_files(self, directory_path: Path, root: Path) -> List[FileOp]:
        # Logic duplicated from MoveFileOperation for now to avoid complex inheritance refactor
        # Ideally this goes into a Mixin.
        ops: List[FileOp] = []
        
        # We start checking from the directory itself (it should be a package)
        # up to the root.
        current = directory_path
        
        while current != root and current.is_relative_to(root):
            init_file = current / "__init__.py"
            if not init_file.exists():
                 ops.append(
                    WriteFileOp(
                        path=init_file.relative_to(root),
                        content=""
                    )
                )
            current = current.parent
            
        return ops
~~~~~
~~~~~python.new
        # 4. Scaffold missing __init__.py files for the destination root
        scaffold_ops = self._scaffold_init_files(self.dest_dir, ctx)

        return all_ops + scaffold_ops

    def _scaffold_init_files(self, directory_path: Path, ctx: RefactorContext) -> List[FileOp]:
        # Logic duplicated from MoveFileOperation (with modifications for Directory)
        ops: List[FileOp] = []
        root = ctx.graph.root_path
        search_paths = ctx.graph.search_paths

        active_root = None
        for sp in search_paths:
            if directory_path.is_relative_to(sp):
                if active_root is None or len(sp.parts) > len(active_root.parts):
                    active_root = sp
        
        if not active_root:
            return []
        
        # Start from the directory itself
        current = directory_path
        
        while current != active_root and current.is_relative_to(active_root):
            init_file = current / "__init__.py"
            if not init_file.exists():
                 ops.append(
                    WriteFileOp(
                        path=init_file.relative_to(root),
                        content=""
                    )
                )
            current = current.parent
            
        return ops
~~~~~

### 下一步建议
运行新创建的测试 `packages/stitcher-refactor/tests/integration/test_bug_init_relative_import.py` 来确认 `__init__.py` 问题是否复现。如果它通过了，说明在简单场景下没问题，我们需要去排查 `MoveDirectoryOperation` 是否在生成重命名操作时遗漏了某些模块。
