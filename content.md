好的，我们开始 TDD 流程。第一步是创建一个精确复现问题的、会失败的测试。

我将生成一个计划，在 `tests/integration/` 目录下创建一个新的测试文件，这个测试会模拟一个与基线同步但使用了“旧版”指纹格式的项目，然后断言 `hydrate` 命令在这种情况下不应修改任何文件。

---
## [WIP] test: 复现 hydrate 命令重写未更改的指纹文件

### 错误分析
根据我们之前的分析，`stitcher hydrate` 在没有发现新文档时仍然重写所有指纹文件的根本原因，在于**数据模型的不一致性**。

1.  **Schema 冲突**: `hydrate` 命令似乎正在使用一个包含 `"baseline_"` 前缀的新 Schema 来写入数据，而读取逻辑（或初始状态）可能使用了不含该前缀的旧 Schema (`code_structure_hash`)。
2.  **职责不清**: `hydrate` 命令错误地承担了“将当前状态同步为新基线”的副作用，即使其核心职责（文档补水）没有执行任何操作。
3.  **状态验证不足**: `check` 命令对缺失的指纹或不一致的 Schema 过于宽容，未能提前暴露问题。

这个 bug 暴露了我们对核心状态（指纹）的管理缺乏一个严格、统一的数据模型。

### 用户需求
启动 TDD 流程，创建一个新的集成测试，该测试应在当前代码库下失败。这个测试需要精确地模拟一个场景：当项目代码、文档和指纹文件完全同步，但指纹文件使用的是旧版 Schema 时，`hydrate` 命令不应该对文件系统进行任何修改。

### 评论
这是一个至关重要的测试。它将一个模糊的 bug 描述转化为一个具体的、可自动验证的工程目标。一旦我们有了这个失败的测试，我们就可以安全地重构 `hydrate` 和 `SignatureManager` 的逻辑，并确保修复是有效且不会被回归的。

### 目标
1.  在 `packages/stitcher-application/tests/integration/` 目录下创建一个新的测试文件 `test_hydrate_regression.py`。
2.  在该文件中定义一个新的测试用例 `test_hydrate_does_not_rewrite_synced_legacy_signatures`。
3.  测试用例将执行以下操作：
    *   **准备 (Arrange)**: 创建一个项目，运行 `init` 生成基线。然后，手动修改生成的指纹 `.json` 文件，将 `baseline_code_structure_hash` 重命名为 `code_structure_hash`，以模拟遗留状态。
    *   **执行 (Act)**: 在这个“同步但遗留”的项目上运行 `app.run_hydrate()`。
    *   **断言 (Assert)**: 断言指纹文件的内容在执行 `hydrate` 前后**完全没有变化**。

### 基本原理
我们将利用 `WorkspaceFactory` 来构建一个干净的测试环境。关键步骤是手动篡改 `init` 命令生成的指纹文件，以精确复现 bug 触发的条件。通过比较执行 `hydrate` 命令前后文件的内容，我们可以确定性地验证该命令是否产生了非预期的副作用。这个测试最初会因为文件内容被修改而失败，一旦我们修复了 `hydrate` 的逻辑，这个测试就应该通过。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #concept/state #ai/instruct #task/domain/testing #task/object/hydrate-command #task/action/bug-fix #task/state/begin

---
### Script

#### Acts 1: 创建回归测试文件

我们将创建新的测试文件 `test_hydrate_regression.py`，并添加一个专门用于复现此问题的测试用例。

~~~~~act
write_file
packages/stitcher-application/tests/integration/test_hydrate_regression.py
~~~~~
~~~~~python
import json
from pathlib import Path
from stitcher.app import StitcherApp
from stitcher.test_utils import WorkspaceFactory, SpyBus
from needle.pointer import L


def test_hydrate_does_not_rewrite_synced_legacy_signatures(
    tmp_path: Path, monkeypatch
):
    """
    Regression Test: Verifies that `hydrate` does not rewrite signature files
    when they are in sync but use a legacy key schema.

    Problem: `hydrate` was rewriting files because it didn't recognize the old
    `code_structure_hash` key, causing unnecessary git changes even when
    no docstrings were hydrated.
    """
    # 1. Arrange: Create a project and initialize it to get a baseline.
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", 'def func(a: int):\n    """Doc."""')
        .build()
    )

    app = StitcherApp(root_path=project_root)
    with SpyBus().patch(monkeypatch, "stitcher.app.core.bus"):
        app.run_init()

    # 2. Arrange: Manually convert the signature file to the legacy format.
    # This simulates the state of the project before the key name change.
    sig_file_path = (
        project_root / ".stitcher/signatures/src/main.json"
    )
    with sig_file_path.open("r") as f:
        data = json.load(f)

    # Convert to legacy format: baseline_code_structure_hash -> code_structure_hash
    legacy_data = {}
    for fqn, hashes in data.items():
        legacy_data[fqn] = {
            "code_structure_hash": hashes.get("baseline_code_structure_hash"),
            "yaml_content_hash": hashes.get("baseline_yaml_content_hash"),
        }
    with sig_file_path.open("w") as f:
        json.dump(legacy_data, f)

    # The project is now in a "synchronized" state, but with a legacy signature file.
    # We also strip the source docstring to ensure hydrate has nothing to do.
    (project_root / "src/main.py").write_text("def func(a: int): ...")

    content_before = sig_file_path.read_text()
    spy_bus = SpyBus()

    # 3. Act: Run the hydrate command, which should ideally do nothing.
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_hydrate()

    # 4. Assert
    content_after = sig_file_path.read_text()

    assert success is True
    # The core assertion: the file content should NOT have changed.
    assert content_after == content_before, (
        "Hydrate command unnecessarily rewrote the signature file."
    )

    # Assert that the bus reported no changes.
    spy_bus.assert_id_called(L.hydrate.run.no_changes, level="info")
~~~~~
