这是针对 `SidecarUpdateMixin` 逻辑增强的执行计划。此修改将赋予 Refactor 引擎正确处理 Signature 文件 (`.json`) 中 SURI 键更新的能力，特别是针对符号重命名场景。

## [WIP] fix(refactor): 增强 SidecarUpdateMixin 以支持 SURI Fragment 重命名

### 用户需求
当前 `stitcher-refactor` 在处理符号重命名 (`RenameSymbol`) 时，无法更新 Signature 文件 (`.json`) 中 SURI 键的 Fragment 部分（例如 `py://...#OldName` -> `py://...#NewName`）。这导致重构后 Signature 文件中的键失效。用户需要一个能够同时处理文件路径更新和符号 Fragment 更新的健壮逻辑。

### 评论
这是一个关键的逻辑修复。虽然我们暂停了架构层面的 Sidecar 包拆分，但“原地加固”此逻辑是解决问题的最短路径。通过引入 `SURIGenerator` 并解析 SURI，我们可以精确地定位和修改 Fragment，避免脆弱的字符串匹配。

### 目标
1.  修改 `stitcher/refactor/operations/base.py` 中的 `_update_sidecar_data` 方法。
2.  引入 `stitcher.lang.python.uri.SURIGenerator` 用于解析和构建 SURI。
3.  实现 SURI Fragment 的智能更新逻辑：仅当被重命名的符号位于当前模块内部时，才更新 Fragment。
4.  保留现有的 SURI Path 更新（文件移动）和 YAML FQN 更新逻辑。

### 基本原理
SURI (`py://path#fragment`) 由两部分组成：物理路径和逻辑片段。
*   **物理路径** 受文件移动 (`MoveFile`) 影响。
*   **逻辑片段** 受符号重命名 (`RenameSymbol`) 影响，但仅当重命名发生在该文件内部时。
通过比较 `old_fqn` 和当前文件的 `module_fqn`，我们可以提取出 `old_fragment`，并在 SURI 中将其替换为 `new_fragment`。这比单纯的前缀匹配更准确，也支持嵌套类/方法的重命名。

### 标签
#intent/fix #flow/ready #priority/high #comp/refactor #concept/state #scope/core #ai/instruct #task/domain/refactoring #task/object/sidecar-mixin #task/action/enhance-logic #task/state/begin

---

### Script

#### Acts 1: 增强 SidecarUpdateMixin

我们将修改 `stitcher-refactor` 中的基类文件，导入必要的 SURI 工具，并重写 `_update_sidecar_data` 方法。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/base.py
~~~~~
~~~~~python.old
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pathlib import Path

from stitcher.lang.python.analysis.utils import path_to_logical_fqn
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.intent import RefactorIntent


class SidecarUpdateMixin:
    def _path_to_fqn(self, path: Path, search_paths: List[Path]) -> Optional[str]:
~~~~~
~~~~~python.new
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pathlib import Path

from stitcher.lang.python.analysis.utils import path_to_logical_fqn
from stitcher.lang.python.uri import SURIGenerator
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.intent import RefactorIntent


class SidecarUpdateMixin:
    def _path_to_fqn(self, path: Path, search_paths: List[Path]) -> Optional[str]:
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/base.py
~~~~~
~~~~~python.old
    def _update_sidecar_data(
        self,
        data: Dict[str, Any],
        module_fqn: Optional[str],
        old_fqn: str,
        new_fqn: str,
        old_file_path: Optional[str] = None,
        new_file_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        new_data = {}
        modified = False

        for key, value in data.items():
            # --- Case 1: SURI Update (py://path/to/file.py#symbol) ---
            if key.startswith("py://") and old_file_path and new_file_path:
                # Format: py://<path>#<fragment>
                # We check if the path component matches our old file path.
                prefix = f"py://{old_file_path}#"
                if key.startswith(prefix):
                    fragment = key[len(prefix) :]
                    # Reconstruct with new path
                    new_key = f"py://{new_file_path}#{fragment}"
                    new_data[new_key] = value
                    modified = True
                    continue
                # If path matches exactly (unlikely for symbol key but possible for file key)
                if key == f"py://{old_file_path}":
                    new_key = f"py://{new_file_path}"
                    new_data[new_key] = value
                    modified = True
                    continue

            # --- Case 2: Standard FQN Update ---
            key_fqn = key
~~~~~
~~~~~python.new
    def _update_sidecar_data(
        self,
        data: Dict[str, Any],
        module_fqn: Optional[str],
        old_fqn: str,
        new_fqn: str,
        old_file_path: Optional[str] = None,
        new_file_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        new_data = {}
        modified = False

        # Calculate logical fragments if applicable (for In-File Rename)
        old_fragment = None
        new_fragment = None

        if module_fqn and old_fqn.startswith(module_fqn + "."):
            old_fragment = old_fqn[len(module_fqn) + 1 :]
            # We assume the module part is the same for simple symbol renames.
            if new_fqn.startswith(module_fqn + "."):
                new_fragment = new_fqn[len(module_fqn) + 1 :]

        for key, value in data.items():
            # --- Case 1: SURI Update (py://path/to/file.py#symbol) ---
            if key.startswith("py://"):
                try:
                    path, fragment = SURIGenerator.parse(key)
                except ValueError:
                    new_data[key] = value
                    continue

                suri_changed = False

                # 1. Update Path (File Move)
                if (
                    old_file_path
                    and new_file_path
                    and path == old_file_path
                ):
                    path = new_file_path
                    suri_changed = True

                # 2. Update Fragment (Symbol Rename)
                if fragment and old_fragment and new_fragment:
                    if fragment == old_fragment:
                        fragment = new_fragment
                        suri_changed = True
                    elif fragment.startswith(old_fragment + "."):
                        # Nested symbol rename (e.g. Class.method -> NewClass.method)
                        suffix = fragment[len(old_fragment) :]
                        fragment = new_fragment + suffix
                        suri_changed = True

                if suri_changed:
                    # Reconstruct SURI
                    new_key = (
                        f"py://{path}#{fragment}" if fragment else f"py://{path}"
                    )
                    new_data[new_key] = value
                    modified = True
                    continue
                else:
                    new_data[key] = value
                    continue

            # --- Case 2: Standard FQN Update ---
            key_fqn = key
~~~~~

### 下一步建议

逻辑已修补。下一步应该运行测试，验证符号重命名是否正确触发了 Signature 文件的更新。如果测试通过，我们可以继续进行 `RenameSymbolOperation` 的意图收集逻辑的确认，确保它传递了正确的 `module_fqn`。
