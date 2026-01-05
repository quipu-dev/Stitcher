# [WIP] fix: 修复文件移动时的相对导入更新与包结构脚手架问题

### 错误分析
在执行文件移动重构（特别是将文件移入新的深层目录）时，当前的实现存在两个严重缺陷：
1.  **相对导入失效**: `SymbolRenamerTransformer` 仅对符号进行简单的名称替换。对于 `from .core import X` 这样的相对导入，当 `core.py` 移动到深层目录时，它无法将其更新为正确的路径（如 `from .services.core import X` 或绝对路径），导致导入断裂。
2.  **缺失 `__init__.py`**: `MoveFileOperation` 不会自动为新创建的目标目录层级生成 `__init__.py` 文件。这使得 Python 无法将新目录识别为包，引发 `ModuleNotFoundError`。

### 用户需求
1.  确保在文件移动后，所有引用该文件的相对导入语句都能被正确更新（建议转换为绝对导入以保证稳健性）。
2.  确保文件移动操作会自动为所有新创建的父目录生成 `__init__.py` 文件，保证包结构的完整性。

### 评论
这是一个对重构功能的关键修复，直接影响到大规模架构调整（如用户正在进行的 `cascade-runtime` 重组）的成功率。

### 目标
1.  修改 `SymbolRenamerTransformer`，增加对 `ImportFrom` 节点的专门处理，将受影响的相对导入转换为绝对导入。
2.  修改 `MoveFileOperation` 和 `MoveDirectoryOperation`，引入自动检测并创建缺失 `__init__.py` 的逻辑。

### 基本原理
1.  **相对导入转绝对**: 在 Transformer 的 `leave_ImportFrom` 阶段拦截。如果发现 `module` 部分指向了被重命名的符号（即被移动的文件），则忽略原有的相对路径层级 (`level`)，直接使用新的完全限定名 (FQN) 生成绝对导入路径。这比计算新的相对路径更简单且不易出错。
2.  **自动脚手架**: 在 `MoveFileOperation.analyze` 的最后阶段，分析目标路径。向上遍历父目录，收集所有不存在 `__init__.py` 的目录，并为它们生成 `WriteFileOp`。为了避免重复，可以使用一个集合来跟踪已计划创建的文件。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/refactor #scope/core #ai/instruct #task/domain/refactoring #task/object/import-fix #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 修复相对导入问题 (Transformer)

我们需要修改 `SymbolRenamerTransformer`，使其能够处理 `ImportFrom` 节点，并将相对导入“升级”为绝对导入。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/transforms/rename_transformer.py
~~~~~
~~~~~python.old
            # Name Match Guard: Only rename if the node's full text matches the old FQN.
            if node_textual_fqn == old_fqn:
                return self._create_node_from_fqn(new_fqn)

        return updated_node
~~~~~
~~~~~python.new
            # Name Match Guard: Only rename if the node's full text matches the old FQN.
            if node_textual_fqn == old_fqn:
                return self._create_node_from_fqn(new_fqn)

        return updated_node

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom:
        # If the module part of the import matches a target, we rewrite the whole
        # import to use the absolute FQN. This handles relative imports gracefully
        # by converting them to absolute ones.
        if original_node.module:
            new_fqn = self._is_target(original_node.module)
            if new_fqn:
                return updated_node.with_changes(
                    module=self._create_node_from_fqn(new_fqn),
                    level=0  # Force absolute import
                )
        return updated_node
~~~~~

#### Acts 2: 实现自动脚手架逻辑 (MoveFile)

我们将修改 `MoveFileOperation`，使其在 `analyze` 返回前检查并补充 `__init__.py` 的创建操作。由于 `MoveDirectoryOperation` 逻辑较为独立，我们先在 `MoveFileOperation` 中直接修复，这是最常用的原子操作。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/move_file.py
~~~~~
~~~~~python.old
        sig_src = ctx.sidecar_manager.get_signature_path(self.src_path)
        if sig_src.exists():
            sig_dest = ctx.sidecar_manager.get_signature_path(self.dest_path)
            move_ops.append(
                MoveFileOp(sig_src.relative_to(root), sig_dest.relative_to(root))
            )

        return content_update_ops + rename_ops + move_ops
~~~~~
~~~~~python.new
        sig_src = ctx.sidecar_manager.get_signature_path(self.src_path)
        if sig_src.exists():
            sig_dest = ctx.sidecar_manager.get_signature_path(self.dest_path)
            move_ops.append(
                MoveFileOp(sig_src.relative_to(root), sig_dest.relative_to(root))
            )

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

#### Acts 3: 实现自动脚手架逻辑 (MoveDirectory)

同样的逻辑也需要应用到 `MoveDirectoryOperation`。虽然 `MoveDirectoryOperation` 主要是移动现有目录，但如果目标是新的（例如重命名目录），目标路径的父级也可能需要 `__init__.py`。更重要的是，如果它在内部重构了结构，确保包完整性是必要的。

不过，仔细看用户的 Case，使用的是 `MoveDir`。所以这里也必须加。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/move_directory.py
~~~~~
~~~~~python.old
        # 3. Schedule the now-empty source directory for deletion
        all_ops.append(DeleteDirectoryOp(self.src_dir.relative_to(root)))

        return all_ops
~~~~~
~~~~~python.new
        # 3. Schedule the now-empty source directory for deletion
        all_ops.append(DeleteDirectoryOp(self.src_dir.relative_to(root)))

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

### 下一步建议

现在修复已经应用，应该重新运行之前失败的集成测试 `packages/stitcher-refactor/tests/integration/test_bug_relative_import_refactor.py` 来验证修复效果。
