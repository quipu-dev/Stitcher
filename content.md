生成 Quipu 计划以修复 `stitcher-refactor` 中的重构引擎缺陷。

简要回答：
Plan 包含修复 `MoveDirectoryOperation` 中 Sidecar 文件被重复移动导致的 FileNotFoundError，以及重构 `RenameNamespaceOperation` 以消除对不可靠的 Metadata Provider 的依赖。

## [WIP] fix: 修复目录移动时的重复操作与命名空间重命名逻辑

### 错误分析

1.  **`MoveDirectoryOperation` 重复移动 Sidecar**:
    *   **现象**: `FileNotFoundError`。
    *   **原因**: `MoveDirectoryOperation` 遍历源目录时，会分别遇到 `module.py` 和 `module.stitcher.yaml`。
        *   处理 `module.py` 时，逻辑会自动寻找并移动关联的 `module.stitcher.yaml`（作为附属品）。
        *   处理 `module.stitcher.yaml` 时，逻辑将其视为普通文件再次尝试移动。
        *   第二次移动时文件已不存在，导致崩溃。
    *   **修复**: 引入两遍扫描机制。第一遍优先处理 `.py` 文件及其附属 Sidecar，并记录已处理文件；第二遍仅处理剩余的未处理文件。

2.  **`RenameNamespaceOperation` 属性错误**:
    *   **现象**: `AttributeError: 'QualifiedNameSource' object has no attribute 'ref_type'`。
    *   **原因**: 试图通过 `MetadataWrapper` 注入自定义的 `QualifiedNameProvider` 结果，但在运行时 LibCST 似乎使用了原生的 `QualifiedNameSource` 枚举，导致类型不匹配。这种基于 Provider 注入的 Mock 机制过于脆弱。
    *   **修复**: 放弃注入 Provider。改为显式地将 `usage_locations` 字典传递给 `NamespaceRenamerTransformer`，并在 Transformer 内部通过 `PositionProvider` 匹配节点位置。这与 `SymbolRenamerTransformer` 的模式保持一致，更加健壮。

### 用户需求
修复重构引擎在处理目录移动和命名空间重命名时的崩溃问题，确保测试套件通过。

### 评论
这些修复消除了重构引擎中的竞态条件和类型假设错误，是保证 `stitcher refactor` 命令可靠性的关键步骤。

### 目标
1.  重构 `MoveDirectoryOperation.analyze`，防止对 Sidecar 文件进行重复操作。
2.  重构 `RenameNamespaceOperation` 和 `NamespaceRenamerTransformer`，移除对 `QualifiedNameProvider` 的依赖。

### 基本原理
*   **去重**: 通过 `processed_files` 集合跟踪文件处理状态，确保每个文件在一次事务中只被操作一次。
*   **显式依赖**: 显式传递数据（Location Map）优于隐式依赖注入（Metadata Provider），前者更易于调试和维护。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/refactor #scope/core #ai/instruct #task/domain/refactoring #task/object/engine #task/action/fix-bugs #task/state/continue

---

### Script

#### Acts 1: 重构 `MoveDirectoryOperation` 以避免重复移动

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/move_directory.py
~~~~~
~~~~~python.old
        # 2. Plan physical file moves and sidecar updates
        doc_updater = DocUpdater()
        sig_updater = SigUpdater()

        for src_item in self.src_dir.rglob("*"):
            if not src_item.is_file():
                continue

            relative_path = src_item.relative_to(self.src_dir)
            dest_item = self.dest_dir / relative_path

            # Plan the move for the item itself
            all_ops.append(
                MoveFileOp(src_item.relative_to(root), dest_item.relative_to(root))
            )

            # If it's a Python file, update its associated sidecars
            if src_item.suffix == ".py":
                # Doc sidecar
                doc_path = ctx.sidecar_manager.get_doc_path(src_item)
                if doc_path.exists():
                    # 1. Update Content if needed
                    doc_data = doc_updater.load(doc_path)
                    updated_data = {
                        key.replace(old_prefix, new_prefix, 1): value
                        for key, value in doc_data.items()
                    }
                    if updated_data != doc_data:
                        # Write updated content before moving
                        all_ops.append(
                            WriteFileOp(
                                path=doc_path.relative_to(root),
                                content=doc_updater.dump(updated_data),
                            )
                        )
                    # 2. Move File
                    dest_doc_path = ctx.sidecar_manager.get_doc_path(dest_item)
                    all_ops.append(
                        MoveFileOp(
                            doc_path.relative_to(root), dest_doc_path.relative_to(root)
                        )
                    )

                # Signature sidecar
                sig_path = ctx.sidecar_manager.get_signature_path(src_item)
                if sig_path.exists():
                    # 1. Update Content if needed
                    sig_data = sig_updater.load(sig_path)
                    updated_data = {
                        key.replace(old_prefix, new_prefix, 1): value
                        for key, value in sig_data.items()
                    }
                    if updated_data != sig_data:
                        all_ops.append(
                            WriteFileOp(
                                path=sig_path.relative_to(root),
                                content=sig_updater.dump(updated_data),
                            )
                        )
                    # 2. Move File
                    dest_sig_path = ctx.sidecar_manager.get_signature_path(dest_item)
                    all_ops.append(
                        MoveFileOp(
                            sig_path.relative_to(root), dest_sig_path.relative_to(root)
                        )
                    )
~~~~~
~~~~~python.new
        # 2. Plan physical file moves and sidecar updates
        doc_updater = DocUpdater()
        sig_updater = SigUpdater()
        processed_files = set()

        # Collect all files first
        all_files = [p for p in self.src_dir.rglob("*") if p.is_file()]

        # Pass 1: Process Python files and their attached sidecars
        for src_item in all_files:
            if src_item.suffix != ".py":
                continue

            processed_files.add(src_item)
            relative_path = src_item.relative_to(self.src_dir)
            dest_item = self.dest_dir / relative_path

            # Move the .py file
            all_ops.append(
                MoveFileOp(src_item.relative_to(root), dest_item.relative_to(root))
            )

            # Handle Doc sidecar
            doc_path = ctx.sidecar_manager.get_doc_path(src_item)
            if doc_path.exists():
                processed_files.add(doc_path)
                # 1. Update Content
                doc_data = doc_updater.load(doc_path)
                updated_data = {
                    key.replace(old_prefix, new_prefix, 1): value
                    for key, value in doc_data.items()
                }
                if updated_data != doc_data:
                    all_ops.append(
                        WriteFileOp(
                            path=doc_path.relative_to(root),
                            content=doc_updater.dump(updated_data),
                        )
                    )
                # 2. Move File
                dest_doc_path = ctx.sidecar_manager.get_doc_path(dest_item)
                all_ops.append(
                    MoveFileOp(
                        doc_path.relative_to(root), dest_doc_path.relative_to(root)
                    )
                )

            # Handle Signature sidecar
            sig_path = ctx.sidecar_manager.get_signature_path(src_item)
            if sig_path.exists():
                # Note: Signature files are usually outside src_dir, so they won't be in all_files
                # But if they WERE inside, we'd want to mark them processed.
                # Adding to set is safe regardless.
                processed_files.add(sig_path)

                # 1. Update Content
                sig_data = sig_updater.load(sig_path)
                updated_data = {
                    key.replace(old_prefix, new_prefix, 1): value
                    for key, value in sig_data.items()
                }
                if updated_data != sig_data:
                    all_ops.append(
                        WriteFileOp(
                            path=sig_path.relative_to(root),
                            content=sig_updater.dump(updated_data),
                        )
                    )
                # 2. Move File
                dest_sig_path = ctx.sidecar_manager.get_signature_path(dest_item)
                all_ops.append(
                    MoveFileOp(
                        sig_path.relative_to(root), dest_sig_path.relative_to(root)
                    )
                )

        # Pass 2: Process remaining files (orphans, non-py files, unattached sidecars)
        for src_item in all_files:
            if src_item in processed_files:
                continue

            relative_path = src_item.relative_to(self.src_dir)
            dest_item = self.dest_dir / relative_path

            all_ops.append(
                MoveFileOp(src_item.relative_to(root), dest_item.relative_to(root))
            )
~~~~~

#### Acts 2: 更新 `NamespaceRenamerTransformer` 以接收位置映射

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/operations/transforms/rename_namespace_transformer.py
~~~~~
~~~~~python
import libcst as cst
from libcst.metadata import PositionProvider
from typing import Optional, Dict, Tuple

from stitcher.refactor.engine.graph import ReferenceType, UsageLocation


class NamespaceRenamerTransformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(
        self,
        old_prefix: str,
        new_prefix: str,
        locations: Dict[Tuple[int, int], UsageLocation],
    ):
        self.old_prefix = old_prefix
        self.new_prefix = new_prefix
        self.locations = locations

    def _create_node_from_fqn(self, fqn: str) -> cst.BaseExpression:
        parts = fqn.split(".")
        node = cst.Name(value=parts[0])
        for part in parts[1:]:
            node = cst.Attribute(value=node, attr=cst.Name(value=part))
        return node

    def _get_import_path_fqn(self, node: cst.CSTNode) -> Optional[str]:
        pos = self.get_metadata(PositionProvider, node)
        start = (pos.start.line, pos.start.column)
        if start in self.locations:
            loc = self.locations[start]
            if loc.ref_type == ReferenceType.IMPORT_PATH:
                return loc.target_node_fqn
        return None

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        import_path_fqn = self._get_import_path_fqn(original_node)
        if import_path_fqn and import_path_fqn.startswith(self.old_prefix):
            suffix = import_path_fqn[len(self.old_prefix) :]
            new_fqn = self.new_prefix + suffix
            return self._create_node_from_fqn(new_fqn)
        return updated_node

    def leave_Name(
        self, original_node: cst.Name, updated_node: cst.Name
    ) -> cst.BaseExpression:
        import_path_fqn = self._get_import_path_fqn(original_node)
        if import_path_fqn and import_path_fqn.startswith(self.old_prefix):
            suffix = import_path_fqn[len(self.old_prefix) :]
            new_fqn = self.new_prefix + suffix
            return self._create_node_from_fqn(new_fqn)
        return updated_node
~~~~~

#### Acts 3: 更新 `RenameNamespaceOperation` 以使用新的 Transformer 接口

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/rename_namespace.py
~~~~~
~~~~~python.old
        for file_path, file_usages in usages_by_file.items():
            try:
                original_source = file_path.read_text(encoding="utf-8")
                module = cst.parse_module(original_source)

                # We need to provide QualifiedName metadata for the transformer
                # It relies on the UsageLocations we stored earlier.
                locations = {
                    (u.lineno, u.col_offset): u for u in file_usages
                }

                class UsageBasedQualifiedNameProvider(cst.metadata.BaseMetadataProvider):
                    def __init__(self, usages):
                        super().__init__()
                        self.usages = usages

                    def on_visit(self, node: cst.CSTNode) -> bool:
                        pos = (node.start_pos.line, node.start_pos.column)
                        if pos in self.usages:
                            usage = self.usages[pos]
                            self.set_metadata(node, [cst.metadata.QualifiedName(name=usage.target_node_fqn, source=usage)])
                        return True

                wrapper = cst.MetadataWrapper(
                    module,
                    cache={
                        QualifiedNameProvider: {
                            pos: [
                                cst.metadata.QualifiedName(name=u.target_node_fqn, source=u)
                            ] for pos, u in locations.items()
                        }
                    },
                )

                transformer = NamespaceRenamerTransformer(
                    self.old_prefix, self.new_prefix
                )
                modified_module = wrapper.visit(transformer)

                relative_path = file_path.relative_to(ctx.graph.root_path)
~~~~~
~~~~~python.new
        for file_path, file_usages in usages_by_file.items():
            try:
                original_source = file_path.read_text(encoding="utf-8")
                module = cst.parse_module(original_source)

                # Build locations map for the transformer
                locations = {
                    (u.lineno, u.col_offset): u for u in file_usages
                }

                # Use standard MetadataWrapper
                wrapper = cst.MetadataWrapper(module)

                transformer = NamespaceRenamerTransformer(
                    self.old_prefix, self.new_prefix, locations
                )
                modified_module = wrapper.visit(transformer)

                relative_path = file_path.relative_to(ctx.graph.root_path)
~~~~~

### 下一步建议
运行测试套件，确认所有重构引擎的集成测试均通过。重点关注 `test_move_directory_monorepo_e2e.py` 和 `test_move_directory_updates_all_contents_and_references`。
