简要回答
好的，我们将启动 Phase 2。本计划将实现核心的 `Linker` 组件，将其集成到扫描流程中，并启用此前跳过的集成测试以验证“引用-定义”闭环。

## [WIP] feat: 实现 Linker 组件并闭合引用解析环路

### 用户需求
1.  在 `stitcher-index` 中创建一个 `Linker` 类，负责通过 SQL 批量更新将引用 (`references`) 和别名 (`symbols`) 链接到它们的定义 (`symbols`)。
2.  在 `WorkspaceScanner.scan()` 流程的最后阶段集成 `Linker.link()` 调用。
3.  启用并验证 `tests/integration/test_scanner_aliases.py`，确保跨文件引用解析正确工作。

### 评论
这是将 Stitcher 从简单的“符号提取器”转变为真正的“语义索引”的关键一步。通过在数据库层面进行批量链接，我们避免了在内存中构建庞大图谱的开销，这符合“组件瘦身”的战略方向。

### 目标
1.  创建 `packages/stitcher-index/src/stitcher/index/linker.py`。
2.  修改 `packages/stitcher-index/src/stitcher/index/scanner.py` 以使用 Linker。
3.  移除 `packages/stitcher-index/tests/integration/test_scanner_aliases.py` 中的 `pytest.mark.skip`。

### 基本原理
Linker 的核心逻辑是基于 `canonical_fqn` (Phase 1 的成果) 进行精确匹配。虽然 Python 的动态性可能导致某些 FQN 无法静态解析（导致 `target_id` 为 NULL），但对于大多数静态可分析的代码，这种基于 SQL 的确定性链接提供了极高的性能和准确性基线。

### 标签
#intent/build #flow/ready #priority/high #comp/index #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/linker #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 创建 Linker 组件

实现 `Linker` 类，包含针对 `references` 表和 `symbols` 表（针对别名）的 UPDATE 逻辑。

~~~~~act
write_file
packages/stitcher-index/src/stitcher/index/linker.py
~~~~~
~~~~~python
import logging
from .db import DatabaseManager

log = logging.getLogger(__name__)


class Linker:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def link(self) -> None:
        """
        Resolves symbolic references and aliases by linking them to their definitions
        using Canonical FQNs (Fully Qualified Names).
        """
        with self.db.get_connection() as conn:
            # 1. Link References
            # Strategy: Match references.target_fqn -> symbols.canonical_fqn
            # We only attempt to link references that remain unresolved (target_id IS NULL).
            log.debug("Linking references...")
            cursor = conn.execute(
                """
                UPDATE "references"
                SET target_id = (
                    SELECT id 
                    FROM symbols 
                    WHERE symbols.canonical_fqn = "references".target_fqn 
                    LIMIT 1
                )
                WHERE target_id IS NULL
                """
            )
            if cursor.rowcount > 0:
                log.debug(f"Linked {cursor.rowcount} references.")

            # 2. Link Aliases
            # Strategy: Match symbols.alias_target_fqn -> symbols.canonical_fqn
            # Only for symbols that are aliases (kind='alias') and unresolved.
            log.debug("Linking aliases...")
            cursor = conn.execute(
                """
                UPDATE symbols
                SET alias_target_id = (
                    SELECT id 
                    FROM symbols AS s2 
                    WHERE s2.canonical_fqn = symbols.alias_target_fqn 
                    LIMIT 1
                )
                WHERE kind = 'alias' 
                  AND alias_target_id IS NULL 
                  AND alias_target_fqn IS NOT NULL
                """
            )
            if cursor.rowcount > 0:
                log.debug(f"Linked {cursor.rowcount} aliases.")
~~~~~

#### Acts 2: 将 Linker 集成到 Scanner

修改 `WorkspaceScanner`，在扫描循环结束后初始化并运行 `Linker`。

~~~~~act
patch_file
packages/stitcher-index/src/stitcher/index/scanner.py
~~~~~
~~~~~python.old
from .store import IndexStore
from .types import FileRecord
from .protocols import LanguageAdapter

log = logging.getLogger(__name__)


class WorkspaceScanner:
    def __init__(self, root_path: Path, store: IndexStore):
        self.root_path = root_path
        self.store = store
        self.adapters: Dict[str, LanguageAdapter] = {}

    def register_adapter(self, extension: str, adapter: LanguageAdapter):
~~~~~
~~~~~python.new
from .store import IndexStore
from .types import FileRecord
from .protocols import LanguageAdapter
from .linker import Linker

log = logging.getLogger(__name__)


class WorkspaceScanner:
    def __init__(self, root_path: Path, store: IndexStore):
        self.root_path = root_path
        self.store = store
        self.adapters: Dict[str, LanguageAdapter] = {}
        self.linker = Linker(store.db)

    def register_adapter(self, extension: str, adapter: LanguageAdapter):
~~~~~

~~~~~act
patch_file
packages/stitcher-index/src/stitcher/index/scanner.py
~~~~~
~~~~~python.old
            # --- Phase 4: Parsing (Semantic Extraction) ---
            self._process_file_content(file_id, abs_path, content_bytes)

        return stats

    def _discover_files(self) -> Set[str]:
~~~~~
~~~~~python.new
            # --- Phase 4: Parsing (Semantic Extraction) ---
            self._process_file_content(file_id, abs_path, content_bytes)

        # --- Phase 5: Linking ---
        # Now that all files are parsed and symbols/references are in DB,
        # we can resolve the links.
        self.linker.link()

        return stats

    def _discover_files(self) -> Set[str]:
~~~~~

#### Acts 3: 启用集成测试

移除 `pytest.mark.skip` 标记，使测试生效。

~~~~~act
patch_file
packages/stitcher-index/tests/integration/test_scanner_aliases.py
~~~~~
~~~~~python.old
import pytest

# 这会跳过整个文件中的所有测试用例
pytestmark = pytest.mark.skip(reason="该文件暂未完成")


def test_scanner_resolves_aliases_and_references(tmp_path, store):
~~~~~
~~~~~python.new
import pytest


def test_scanner_resolves_aliases_and_references(tmp_path, store):
~~~~~

### 下一步建议

执行完此计划后，我们将运行 `test_scanner_aliases.py` 以验证 Linker 是否按预期工作。如果测试通过，我们将处于一个极佳的位置来继续 Phase 3（让 Refactor 使用这个强大的索引）。如果测试失败，我们需要检查 `canonical_fqn` 的生成逻辑是否在所有情况下（如 `__init__.py` 或相对导入）都完全对齐。
