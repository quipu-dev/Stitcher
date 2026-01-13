好的，又发现一个 `ImportError`。`stitcher-test-utils` 这个包还在引用已被删除的 `SignatureManager`。这很正常，测试辅助工具往往与它们所辅助的旧实现紧密耦合。我需要修复它。

## [WIP] fix: 修复 stitcher-test-utils 中的过时引用

### 错误分析
`pytest` 报告在 `stitcher-test-utils/src/stitcher/test_utils/helpers.py` 中无法导入 `SignatureManager`，因为我之前已经删除了这个类。辅助函数 `get_stored_hashes` 是专门为旧的签名管理器设计的，现在它已经完全失效。我需要用一个等效的、与 `LockFileManager` 交互的新辅助函数来替换它。

### 用户需求
1.  修复 `stitcher-test-utils` 中由删除 `SignatureManager` 引起的 `ImportError`。
2.  重写 `get_stored_hashes` 辅助函数，使其能够读取新的 `stitcher.lock` 文件，并返回与旧函数格式兼容的数据，以减少对现有测试用例的冲击。

### 评论
这个修复是必要的，以确保整个测试套件能够运行。重写 `get_stored_hashes` 是一个务实的选择，它创建了一个适配层，让依赖它的旧测试可以继续工作，而无需大规模重写。

### 目标
1.  修改 `stitcher-test-utils/src/stitcher/test_utils/helpers.py`，移除对 `SignatureManager` 的导入。
2.  用 `LockFileManager` 重新实现 `get_stored_hashes`，使其能够解析 `stitcher.lock` 文件。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #ai/instruct #task/domain/storage #task/object/suri-lockfile #task/action/test-utility-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `stitcher-test-utils`

我们将重写 `helpers.py`，移除旧的导入并更新 `get_stored_hashes` 的实现。

~~~~~act
write_file
packages/stitcher-test-utils/src/stitcher/test_utils/helpers.py
~~~~~
~~~~~python
from pathlib import Path
from typing import Optional, Dict

from stitcher.app import StitcherApp
from stitcher.spec.interaction import InteractionHandler
from stitcher.lang.python import (
    PythonTransformer,
    PythonFingerprintStrategy,
)
from stitcher.workspace import Workspace

from stitcher.lang.python.parser.griffe import GriffePythonParser
from stitcher.index.db import DatabaseManager
from stitcher.index.store import IndexStore
from stitcher.index.indexer import FileIndexer
from stitcher.lang.python.adapter import PythonAdapter
from stitcher.lang.sidecar import LockFileManager


def create_populated_index(root_path: Path) -> IndexStore:
    db_path = root_path / ".stitcher" / "index" / "index.db"

    db_manager = DatabaseManager(db_path)
    db_manager.initialize()
    store = IndexStore(db_manager)

    # The indexer needs a workspace-aware adapter.
    workspace = Workspace(root_path)
    search_paths = workspace.get_search_paths()

    # Discover files first, then index them.
    files_to_index = workspace.discover_files()

    indexer = FileIndexer(root_path, store)
    indexer.register_adapter(".py", PythonAdapter(root_path, search_paths))
    indexer.index_files(files_to_index)

    return store


def create_test_app(
    root_path: Path, interaction_handler: Optional[InteractionHandler] = None
) -> StitcherApp:
    parser = GriffePythonParser()
    transformer = PythonTransformer()
    strategy = PythonFingerprintStrategy()
    return StitcherApp(
        root_path=root_path,
        parser=parser,
        transformer=transformer,
        fingerprint_strategy=strategy,
        interaction_handler=interaction_handler,
    )


def get_stored_hashes(project_root: Path, file_path: str) -> Dict[str, dict]:
    """
    Test helper to read fingerprints from the appropriate stitcher.lock file.
    
    This function simulates the logic of finding the owning package and reading
    the lock file to retrieve fingerprint data, providing it in a format
    (fragment -> dict) that is easy to assert against in tests.
    """
    workspace = Workspace(project_root)
    lock_manager = LockFileManager()

    # 1. Find the package root for the given file
    abs_file_path = project_root / file_path
    pkg_root = workspace.find_owning_package(abs_file_path)

    # 2. Load the lock data for that package
    lock_data = lock_manager.load(pkg_root)

    # 3. Filter and re-key the data for the specific file
    # We want to return a dict of {fragment: fingerprint_dict} for just this file.
    ws_rel_path = workspace.to_workspace_relative(abs_file_path)
    file_prefix = f"py://{ws_rel_path}#"
    
    file_hashes = {}
    for suri, fp in lock_data.items():
        if suri.startswith(file_prefix):
            fragment = suri[len(file_prefix):]
            file_hashes[fragment] = fp.to_dict()
            
    return file_hashes
~~~~~

### 下一步建议
测试辅助工具已修复。现在所有的 `ImportError` 和主要的 `TypeError` 都应该解决了。我们可以重新尝试运行测试，如果通过，就可以继续进行 **阶段 4: 重构引擎简化 (Refactor Engine Lobotomy)**。
