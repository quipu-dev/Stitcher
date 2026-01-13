## [WIP] refactor(refactor): Rewrite SidecarUpdateMixin for SURI/Fragment logic

### 用户需求

清理 `stitcher-refactor` 包，使其不再依赖旧的 FQN 字符串匹配逻辑来更新 sidecar 文件。
具体要求：
1.  **区分策略**: 根据 sidecar 文件类型（`.json` vs `.yaml`）采用不同的更新策略。
2.  **JSON (SURI)**: 对于签名文件，必须基于 SURI (`py://path#fragment`) 进行更新。支持“路径变更”（文件移动）和“Fragment 变更”（符号重命名）的组合更新。
3.  **YAML (Fragment)**: 对于文档文件，必须基于 Fragment（短名）进行更新。注意：单纯的文件移动**不应**改变 YAML 中的键（因为它们是相对的），只有符号重命名才应更新键。

### 评论

这是“大清洗”计划的第三阶段，也是逻辑最复杂的部分。之前的 Mixin 试图用一种通用的 FQN 替换逻辑来处理所有情况，导致了逻辑混淆和脆弱性。现在的目标是**分离关注点**：物理移动只影响物理 ID (SURI)，逻辑重命名影响逻辑 ID (Fragment)。通过明确区分这两者，我们的重构引擎将变得极其健壮。

**特别注意**: 我们不需要引入 `stitcher-lang-sidecar` 作为依赖。`Planner` 已经完成了文件的 I/O 操作（加载为 dict），Mixin 只需要负责纯粹的数据转换逻辑。所有的 SURI 解析和生成逻辑都可以利用 `stitcher-lang-python` 中的 `SURIGenerator`。

### 目标

1.  重写 `stitcher.refactor.operations.base.SidecarUpdateMixin`。
2.  更新 `stitcher.refactor.engine.planner.Planner` 以配合新的 Mixin 签名（传入 `sidecar_path`）。

### 基本原理

1.  **Fragment 计算**: 在 Mixin 中增加逻辑，通过比较 `module_fqn` 和 `target_fqn` 来提取 `fragment`。
2.  **SURI 更新逻辑**:
    *   解析现有的 key (SURI)。
    *   检查其 `path` 部分是否匹配 `intent.old_file_path`。如果匹配，更新为 `intent.new_file_path`。
    *   检查其 `fragment` 部分是否匹配 `old_fragment`。如果匹配，更新为 `new_fragment`。
    *   如果任一部分发生变化，重新生成 SURI 并更新字典。
3.  **Fragment 更新逻辑**:
    *   遍历现有的 keys (Fragments)。
    *   如果 key 匹配 `old_fragment`，替换为 `new_fragment`。
    *   (关键) 如果只是文件移动但符号没改名，`old_fragment` 和 `new_fragment` 是一样的（或者为空），YAML 内容保持不变。这是正确的行为。

### 标签

#intent/refine #flow/ready #priority/critical #comp/engine #concept/state #scope/core #ai/instruct #task/domain/testing #task/object/identifier-ontology #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重写 `SidecarUpdateMixin`

我们在 `base.py` 中彻底重写更新逻辑。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/operations/base.py
~~~~~
~~~~~python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from stitcher.lang.python.analysis.utils import path_to_logical_fqn
from stitcher.lang.python.uri import SURIGenerator
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.intent import RefactorIntent


class SidecarUpdateMixin:
    def _path_to_fqn(self, path: Path, search_paths: List[Path]) -> Optional[str]:
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
        return path_to_logical_fqn(rel_path.as_posix())

    def _calculate_fragments(
        self, module_fqn: Optional[str], old_fqn: str, new_fqn: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Derives the symbol fragments (short names) from FQNs relative to a module.
        If the FQN implies the module itself, the fragment is None.
        """
        if not module_fqn:
            # Fallback: if we don't know the module, we assume top-level or can't determine fragment safely.
            # However, for simple renames, old_fqn might be the full key.
            return None, None

        old_fragment = None
        new_fragment = None

        # Check if old_fqn is inside module_fqn
        if old_fqn == module_fqn:
            # The operation is on the module itself (e.g. file move/rename).
            # Fragment is empty/None.
            pass
        elif old_fqn.startswith(module_fqn + "."):
            old_fragment = old_fqn[len(module_fqn) + 1 :]

        # Check if new_fqn is inside the *logical* new module location.
        # Note: We rely on the caller to provide consistent FQNs.
        # If it's a rename: module_fqn matches parent.
        # If it's a move: new_fqn matches new path.
        # We assume symmetry for the fragment calculation.
        if old_fragment:
            # Heuristic: If we extracted an old fragment, we try to extract a new one
            # assuming the structure is preserved or it's a direct rename.
            # If new_fqn is just a different name in same scope:
            #   module.Old -> module.New
            # If new_fqn is moved:
            #   old_mod.Class -> new_mod.Class
            # We need to act carefully.

            # Simple Strategy:
            # If it's a RenameSymbol, old_fqn and new_fqn share the parent module prefix usually.
            # If it's a MoveFile, the fragment usually stays the same.

            # Let's try to deduce the new fragment by stripping the known prefix if possible,
            # or by taking the last part if it looks like a symbol.
            if "." in new_fqn:
                new_fragment = new_fqn.split(".")[-1]
                # Consistency check: if it's a move, fragments often match
                if "." in old_fqn and old_fqn.split(".")[-1] == new_fragment:
                    pass
                else:
                    # It's a rename
                    pass
            else:
                new_fragment = new_fqn

        return old_fragment, new_fragment

    def _update_sidecar_data(
        self,
        data: Dict[str, Any],
        sidecar_path: Path,
        module_fqn: Optional[str],
        old_fqn: str,
        new_fqn: str,
        old_file_path: Optional[str] = None,
        new_file_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Dispatcher for sidecar updates based on file type.
        """
        # Calculate fragments once
        old_fragment, new_fragment = self._calculate_fragments(
            module_fqn, old_fqn, new_fqn
        )

        if sidecar_path.suffix == ".json":
            return self._update_json_data(
                data, old_file_path, new_file_path, old_fragment, new_fragment
            )
        elif sidecar_path.suffix in (".yaml", ".yml"):
            return self._update_yaml_data(data, old_fragment, new_fragment)

        return data

    def _update_json_data(
        self,
        data: Dict[str, Any],
        old_file_path: Optional[str],
        new_file_path: Optional[str],
        old_fragment: Optional[str],
        new_fragment: Optional[str],
    ) -> Dict[str, Any]:
        """
        Updates Signature JSON data where keys are SURIs (py://path#fragment).
        """
        new_data = {}
        modified = False

        for key, value in data.items():
            if not key.startswith("py://"):
                new_data[key] = value
                continue

            try:
                path, fragment = SURIGenerator.parse(key)
            except ValueError:
                new_data[key] = value
                continue

            path_changed = False
            fragment_changed = False

            # 1. Path Update (File Move)
            # We match strictly on the path part of the SURI.
            if old_file_path and new_file_path and path == old_file_path:
                path = new_file_path
                path_changed = True

            # 2. Fragment Update (Symbol Rename)
            # We match strictly on the fragment part.
            if old_fragment and new_fragment and fragment:
                if fragment == old_fragment:
                    fragment = new_fragment
                    fragment_changed = True
                elif fragment.startswith(old_fragment + "."):
                    # Handle nested symbols: Class.method -> NewClass.method
                    suffix = fragment[len(old_fragment) :]
                    fragment = new_fragment + suffix
                    fragment_changed = True

            if path_changed or fragment_changed:
                new_key = SURIGenerator.for_symbol(path, fragment) if fragment else SURIGenerator.for_file(path)
                new_data[new_key] = value
                modified = True
            else:
                new_data[key] = value

        return new_data if modified else data

    def _update_yaml_data(
        self,
        data: Dict[str, Any],
        old_fragment: Optional[str],
        new_fragment: Optional[str],
    ) -> Dict[str, Any]:
        """
        Updates Doc YAML data where keys are Fragments (Short Names).
        File moves do NOT affect these keys (as they are relative), unless the symbol itself is renamed.
        """
        if not old_fragment or not new_fragment or old_fragment == new_fragment:
            # No symbol rename occurred, or we couldn't determine fragments.
            # For pure file moves, YAML content usually stays static.
            return data

        new_data = {}
        modified = False

        for key, value in data.items():
            # Check for exact match (Top-level symbol rename)
            if key == old_fragment:
                new_data[new_fragment] = value
                modified = True
                continue

            # Check for nested match (Method rename via Class rename)
            # e.g. Key="OldClass.method", Rename="OldClass"->"NewClass"
            if key.startswith(old_fragment + "."):
                suffix = key[len(old_fragment) :]
                new_key = new_fragment + suffix
                new_data[new_key] = value
                modified = True
                continue

            new_data[key] = value

        return new_data if modified else data


class AbstractOperation(ABC):
    @abstractmethod
    def collect_intents(self, ctx: RefactorContext) -> List[RefactorIntent]:
        pass
~~~~~

#### Acts 2: 更新 `Planner` 以传递路径

我们需要更新 `Planner`，使其在调用 `_update_sidecar_data` 时传递 `intent.sidecar_path`，以便 Mixin 可以进行类型分发。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/planner.py
~~~~~
~~~~~python.old
            # Apply all intents for this file
            for intent in intents:
                data = self._update_sidecar_data(
                    data,
                    intent.module_fqn,
                    intent.old_fqn,
                    intent.new_fqn,
                    old_file_path=intent.old_file_path,
                    new_file_path=intent.new_file_path,
                )
~~~~~
~~~~~python.new
            # Apply all intents for this file
            for intent in intents:
                data = self._update_sidecar_data(
                    data,
                    intent.sidecar_path,
                    intent.module_fqn,
                    intent.old_fqn,
                    intent.new_fqn,
                    old_file_path=intent.old_file_path,
                    new_file_path=intent.new_file_path,
                )
~~~~~

### 下一步建议

我们已经完成了“大清洗”的全部实施步骤：
1.  测试数据已更新为 SURI/Fragment 格式。
2.  `SidecarAdapter` 已重写，支持物理 SURI 计算。
3.  `Planner` (通过 `SidecarUpdateMixin`) 已重写，拥有了清晰的、基于文件类型的更新逻辑。

现在，我们可以再次运行测试来验证整个系统的整合情况。如果所有测试通过，这意味着我们成功地将系统架构迁移到了更稳固的“物理事实”基础上。

我建议立即运行测试：
`pytest packages/stitcher-refactor/tests/integration/`
