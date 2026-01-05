# [WIP] fix(refactor): 修复 RenameSymbol 操作未能正确更新 Sidecar 文件的问题

### 错误分析

测试失败 confirmed：`AssertionError: BUG: YAML doc key was not renamed.`。
这证明 `RenameSymbolOperation` 目前的实现仅处理了 Python 源代码的 AST 转换，而只是简单地尝试在 sidecar 中进行完全匹配的键替换 (`rename_key`)。它未能处理以下两种关键情况：
1.  **Short Name 解析**：在 definition file 的 `.stitcher.yaml` 中，键通常是相对于模块的短名（如 `MessageBus`），而不是 FQN（如 `stitcher.common.messaging.bus.MessageBus`）。简单的字符串匹配无法将 FQN `old_fqn` 映射到这些短名。
2.  **子成员联动**：当重命名一个类时，其下的所有方法和属性的文档键（如 `MessageBus.info`）也应当随之重命名（变为 `FeedbackBus.info`）。目前的逻辑不支持这种层级更新。

### 用户需求

修复 `RenameSymbolOperation`，使其能够智能地识别并更新与被重命名符号相关的 Sidecar 文件（Doc 和 Signature），支持短名解析和子成员的级联重命名。

### 评论

这是重构引擎正确性的核心保障。如果重构只做了一半（改了代码没改文档），会导致代码库处于不一致状态。修复此问题需要引入上下文感知的键解析逻辑。

### 目标

1.  在 `RenameSymbolOperation` 中引入 `_path_to_fqn` 辅助方法，用于确定当前处理文件的模块 FQN。
2.  重写 `analyze` 方法中的 Sidecar 处理逻辑：
    *   遍历 Sidecar 中的每个键。
    *   结合当前文件的模块 FQN，将键解析为绝对 FQN。
    *   检查解析后的 FQN 是否匹配 `old_fqn` 或其子成员。
    *   如果匹配，计算新的 FQN 并还原为适当的键格式（Short 或 Full）。
3.  确保 `test_debug_rename_failure.py` 测试通过。

### 基本原理

我们将借用 `MoveFileOperation` 中的路径解析逻辑，通过 `ctx.graph.search_paths` 将文件路径转换为模块 FQN。利用这个基准 FQN，我们可以将 Sidecar 中的短键（如 `MyClass`）还原为完整 FQN（`pkg.mod.MyClass`），从而与 `old_fqn` 进行可靠的比对。更新时，我们会根据原键的格式（是否包含模块前缀）来决定新键的格式，以保持风格一致性。

### 标签

#intent/fix #flow/ready #priority/high #comp/runtime #concept/state #scope/core #ai/instruct #task/domain/refactoring #task/object/rename-operation #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 RenameSymbolOperation 的 Sidecar 更新逻辑

我们将重写 `packages/stitcher-refactor/src/stitcher/refactor/operations/rename_symbol.py`。主要改动是添加 `_path_to_fqn` 方法，并替换原有的简单 `rename_key` 调用为一套完整的遍历-解析-替换逻辑。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/operations/rename_symbol.py
~~~~~
~~~~~python
import libcst as cst
from collections import defaultdict
from typing import List, Dict, Any, Optional
from pathlib import Path

from .base import AbstractOperation
from .transforms.rename_transformer import SymbolRenamerTransformer
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import FileOp, WriteFileOp
from stitcher.refactor.engine.graph import UsageLocation
from stitcher.refactor.sidecar.updater import DocUpdater, SigUpdater


class RenameSymbolOperation(AbstractOperation):
    def __init__(self, old_fqn: str, new_fqn: str):
        self.old_fqn = old_fqn
        self.new_fqn = new_fqn

    def _path_to_fqn(self, path: Path, search_paths: List[Path]) -> Optional[str]:
        # Copied/Adapted from MoveFileOperation logic
        base_path = None
        for sp in sorted(search_paths, key=lambda p: len(p.parts), reverse=True):
            try:
                path.relative_to(sp)
                base_path = sp
                break
            except ValueError:
                continue

        if base_path is None:
            return None

        rel_path = path.relative_to(base_path)
        parts = list(rel_path.parts)

        if parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]
        elif parts[-1].endswith(".pyi"):
            parts[-1] = parts[-1][:-4]

        if parts[-1] == "__init__":
            parts = parts[:-1]

        if not parts:
            return ""

        return ".".join(parts)

    def _update_sidecar_data(
        self,
        data: Dict[str, Any],
        module_fqn: Optional[str],
    ) -> Dict[str, Any]:
        """
        Intelligently updates keys in sidecar data.
        Handles both FQN keys and short-name keys (relative to module_fqn).
        Handles cascading renames (e.g. Class.method).
        """
        new_data = {}
        modified = False

        for key, value in data.items():
            # 1. Resolve key to FQN
            key_fqn = key
            is_short_name = False

            # Heuristic: If we have a module context, and the key doesn't start with it,
            # assume it's a short name relative to that module.
            if module_fqn:
                if not key.startswith(module_fqn + "."):
                    # It's likely a short name (e.g. "MyClass" or "MyClass.method")
                    key_fqn = f"{module_fqn}.{key}"
                    is_short_name = True
                else:
                    # It's already fully qualified in the file
                    is_short_name = False

            # 2. Check for match
            new_key = key  # Default to no change

            if key_fqn == self.old_fqn:
                # Exact match (e.g. the class itself)
                target_fqn = self.new_fqn
                if is_short_name and module_fqn:
                    # Try to convert back to short name if possible
                    # We assume new_fqn is in the same module (rename symbol),
                    # so we just strip the module prefix.
                    if target_fqn.startswith(module_fqn + "."):
                        new_key = target_fqn[len(module_fqn) + 1 :]
                    else:
                        # If it moved modules, we must use FQN
                        new_key = target_fqn
                else:
                    new_key = target_fqn
                modified = True

            elif key_fqn.startswith(self.old_fqn + "."):
                # Prefix match (e.g. a method of the class)
                # old_fqn = pkg.Old
                # key_fqn = pkg.Old.method
                # suffix  = .method
                suffix = key_fqn[len(self.old_fqn) :]
                target_fqn = self.new_fqn + suffix

                if is_short_name and module_fqn:
                    if target_fqn.startswith(module_fqn + "."):
                        new_key = target_fqn[len(module_fqn) + 1 :]
                    else:
                        new_key = target_fqn
                else:
                    new_key = target_fqn
                modified = True

            new_data[new_key] = value

        return new_data if modified else data

    def analyze(self, ctx: RefactorContext) -> List[FileOp]:
        ops: List[FileOp] = []

        # We pass the full FQN map to the transformer.
        # The transformer will decide whether to replace with Short Name or Full Attribute Path
        # based on the node type it is visiting.
        rename_map = {self.old_fqn: self.new_fqn}

        # 1. Find all usages
        usages = ctx.graph.registry.get_usages(self.old_fqn)

        # 2. Group usages by file
        usages_by_file: Dict[Path, List[UsageLocation]] = defaultdict(list)
        for usage in usages:
            usages_by_file[usage.file_path].append(usage)

        # 3. For each affected file, apply transformation
        for file_path, file_usages in usages_by_file.items():
            try:
                # Determine current module FQN for Sidecar resolution
                # We do this per file.
                module_fqn = self._path_to_fqn(file_path, ctx.graph.search_paths)

                # --- 1. Handle Code Renaming ---
                original_source = file_path.read_text(encoding="utf-8")

                module = cst.parse_module(original_source)
                wrapper = cst.MetadataWrapper(module)

                transformer = SymbolRenamerTransformer(rename_map, file_usages)
                modified_module = wrapper.visit(transformer)

                relative_path = file_path.relative_to(ctx.graph.root_path)
                if modified_module.code != original_source:
                    ops.append(
                        WriteFileOp(path=relative_path, content=modified_module.code)
                    )

                # --- 2. Handle Sidecar Renaming ---
                # Note: We only update sidecars for files that actually contain the definition
                # or have docs attached. The heuristic here is: if a .stitcher.yaml exists, check it.
                # The usage loop might visit consumer files (e.g. main.py) which don't have
                # relevant sidecars for the *renamed symbol*.
                # However, updating the sidecar logic is safe because if the key isn't found,
                # _update_sidecar_data returns original data.

                doc_updater = DocUpdater()
                sig_updater = SigUpdater()

                # Doc file
                doc_path = ctx.sidecar_manager.get_doc_path(file_path)
                if doc_path.exists():
                    doc_data = doc_updater.load(doc_path)
                    new_doc_data = self._update_sidecar_data(doc_data, module_fqn)
                    if new_doc_data != doc_data:
                        ops.append(
                            WriteFileOp(
                                path=doc_path.relative_to(ctx.graph.root_path),
                                content=doc_updater.dump(new_doc_data),
                            )
                        )

                # Signature file
                sig_path = ctx.sidecar_manager.get_signature_path(file_path)
                if sig_path.exists():
                    sig_data = sig_updater.load(sig_path)
                    # Signatures usually use FQN keys always, but our logic handles that.
                    # Signatures are less likely to use short names, but passing module_fqn is safe.
                    new_sig_data = self._update_sidecar_data(sig_data, module_fqn)
                    if new_sig_data != sig_data:
                        ops.append(
                            WriteFileOp(
                                path=sig_path.relative_to(ctx.graph.root_path),
                                content=sig_updater.dump(new_sig_data),
                            )
                        )

            except Exception:
                raise

        return ops
~~~~~

### 下一步建议

执行此补丁后，应立即重新运行 `test_debug_rename_failure.py` 测试。这一次，不仅 `bus.py` 中的类定义应该被重命名，`bus.stitcher.yaml` 中的 `MessageBus` 和 `MessageBus.info` 键，以及 signature JSON 中的 FQN 键也应该全部更新，从而通过所有断言。
