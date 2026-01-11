好的，我来修复这些测试失败。

## [WIP] fix(tests): 更新测试套件以适配 SURI 格式的签名文件

### 错误分析
测试失败的根本原因在于上一步的重构。我将 `SignatureManager` 保存的 `.json` 签名文件中的字典键从简单的 FQN 片段（如 `func`）更改为了全局唯一的 SURI 字符串（如 `py://src/app.py#func`）。

然而，大量的集成测试依赖于一个名为 `get_stored_hashes` 的测试辅助函数来读取这些签名文件，而这个函数并未同步更新。它仍然只是简单地加载 JSON，导致测试代码在尝试用旧的、简单的键（`func`）访问字典时，因找不到键而抛出 `KeyError`。

此外，`SignatureManager` 自己的单元测试也存在一个问题：它直接检查了写入磁盘的 JSON 文件的内容，但其断言部分没有更新为使用新的 SURI 键，因此也失败了。

### 用户需求
修复所有因 `KeyError` 导致的测试失败，使测试套件能够正确理解和处理 SURI 格式的签名文件。

### 评论
这是一个典型的“实现与测试脱节”的例子。修复这个问题的关键是让测试基础设施（辅助函数）与被测试的组件（`SignatureManager`）遵循相同的协议。通过将 SURI 解析逻辑集中到 `SignatureManager` 并让测试工具调用它，我们不仅修复了当前的 Bug，还提高了代码的健壮性和可维护性。

### 目标
1.  **修复核心测试辅助函数**: 修改 `stitcher-test-utils` 包中的 `get_stored_hashes` 函数，使其通过 `SignatureManager` 加载签名，而不是直接读取 JSON。
2.  **修复单元测试**: 更新 `test_signature_manager.py` 中直接检查文件内容的断言，使其能够识别并使用 SURI 键。

### 基本原理
我们将把解析 SURI 的责任完全交给 `SignatureManager`。测试辅助函数 `get_stored_hashes` 将不再关心 JSON 的内部格式，而是委托 `SignatureManager.load_composite_hashes` 来加载和解析签名。由于 `load_composite_hashes` 的返回值（`Dict[str, Fingerprint]`）的键已经是 FQN 片段，因此所有依赖 `get_stored_hashes` 的上层测试代码无需任何改动即可恢复正常工作。对于单元测试，我们将直接在断言中使用 SURI 字符串来验证文件的写入是否正确。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #concept/state #scope/dx #ai/instruct #task/domain/storage #task/object/stitcher-index #task/action/upgrade-schema #task/state/continue

---

### Script

#### Acts 1: 修复核心测试辅助函数 `get_stored_hashes`

我们将修改 `stitcher-test-utils` 中的 `helpers.py`，让 `get_stored_hashes` 使用 `SignatureManager` 来加载数据，从而正确处理 SURI 键。

~~~~~act
patch_file
packages/stitcher-test-utils/src/stitcher/test_utils/helpers.py
~~~~~
~~~~~python.old
import json
from pathlib import Path
from typing import Optional

from stitcher.app import StitcherApp
from stitcher.app.protocols import InteractionHandler
from stitcher.adapter.python import (
    PythonTransformer,
    PythonFingerprintStrategy,
)
from stitcher.workspace import Workspace

from stitcher.adapter.python.griffe_parser import GriffePythonParser
from stitcher.index.db import DatabaseManager
from stitcher.index.store import IndexStore
from stitcher.index.indexer import FileIndexer
from stitcher.adapter.python.index_adapter import PythonAdapter


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


def get_stored_hashes(project_root: Path, file_path: str) -> dict:
    sig_file = (
        project_root / ".stitcher/signatures" / Path(file_path).with_suffix(".json")
    )
    if not sig_file.exists():
        return {}
    with sig_file.open("r") as f:
        return json.load(f)
~~~~~
~~~~~python.new
import json
from pathlib import Path
from typing import Optional

from stitcher.app import StitcherApp
from stitcher.app.protocols import InteractionHandler
from stitcher.adapter.python import (
    PythonTransformer,
    PythonFingerprintStrategy,
)
from stitcher.workspace import Workspace

from stitcher.adapter.python.griffe_parser import GriffePythonParser
from stitcher.index.db import DatabaseManager
from stitcher.index.store import IndexStore
from stitcher.index.indexer import FileIndexer
from stitcher.adapter.python.index_adapter import PythonAdapter
from stitcher.app.services import SignatureManager


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


def get_stored_hashes(project_root: Path, file_path: str) -> dict:
    manager = SignatureManager(root_path=project_root)
    fingerprints = manager.load_composite_hashes(file_path)
    return {fqn: fp.to_dict() for fqn, fp in fingerprints.items()}
~~~~~

#### Acts 2: 修复 `SignatureManager` 的单元测试

现在修复 `test_signature_manager.py`，使其在直接检查文件内容时使用正确的 SURI 键进行断言。

~~~~~act
patch_file
packages/stitcher-application/tests/unit/test_signature_manager.py
~~~~~
~~~~~python.old
    with sig_path.open("r") as f:
        data = json.load(f)
        assert data["foo"]["baseline_code_structure_hash"] == "abc"
        assert data["foo"]["baseline_yaml_content_hash"] == "def"
        assert data["bar"]["baseline_code_structure_hash"] == "123"
        # Since it was None, the key should be absent in the serialized JSON
        assert "baseline_yaml_content_hash" not in data["bar"]

    # Act: Load
    loaded = manager.load_composite_hashes(module.file_path)
~~~~~
~~~~~python.new
    with sig_path.open("r") as f:
        data = json.load(f)
        suri_foo = "py://src/main.py#foo"
        suri_bar = "py://src/main.py#bar"
        assert data[suri_foo]["baseline_code_structure_hash"] == "abc"
        assert data[suri_foo]["baseline_yaml_content_hash"] == "def"
        assert data[suri_bar]["baseline_code_structure_hash"] == "123"
        # Since it was None, the key should be absent in the serialized JSON
        assert "baseline_yaml_content_hash" not in data[suri_bar]

    # Act: Load
    loaded = manager.load_composite_hashes(module.file_path)
~~~~~

### 下一步建议

测试套件现在应该可以全部通过了。我们已经完成了阶段 2 的核心任务。

现在，我们可以满怀信心地进入**阶段 3：逻辑驱动重构**。我将准备一个计划来重构 `CheckRunner`，使其完全切换到高性能的 "Query-First" 模式，这将是新架构价值的首次兑现。
