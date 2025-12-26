好的，我们已经完成了 `hydrate` 命令的逻辑实现。现在，我将创建相应的集成测试来验证其行为的正确性，并为 `check` 命令的新冲突检测功能添加一个专门的测试。

## 简要回答
我将创建一个新的测试文件 `test_hydrate_command.py` 来覆盖正常补水、冲突检测、强制覆盖和 `strip` 联动这四个核心场景。同时，我也会创建一个 `test_check_conflict.py` 文件，专门验证 `check` 命令现在能够正确地报告代码与 YAML 文档之间的内容冲突。

## [WIP] test: 为 hydrate 命令和 check 冲突检测添加集成测试

### 用户需求
1.  为 `hydrate` 命令编写全面的集成测试。
2.  验证 `check` 命令的新冲突检测功能。

### 评论
编写这些测试至关重要，它不仅能确保 `hydrate` 功能的正确性，还能锁定 `check` 命令的行为，确保 CI 流程能够捕获所有预期的文档不同步状态，符合我们“验证意图而非实现”的测试原则。

### 目标
1.  创建 `tests/integration/test_hydrate_command.py` 文件。
2.  在该文件中实现四个独立的测试用例，每个用例都使用 `WorkspaceFactory` 和 `SpyBus`。
3.  创建 `tests/integration/test_check_conflict.py` 文件，验证 `check` 命令的冲突报告。

### 基本原理
通过 `WorkspaceFactory`，每个测试都在一个隔离的、声明式定义的虚拟项目中运行，保证了测试的纯粹性和可复现性。通过 `SpyBus`，我们断言的是业务逻辑发出的语义消息，而不是脆弱的 UI 文本，这使得测试更加健壮。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #concept/sync #scope/dx #ai/instruct #task/domain/cli #task/object/command-hydrate #task/action/testing #task/state/continue

---

### Script

#### Acts 1: 创建 `hydrate` 命令的集成测试

我们将创建一个新文件，并在其中填充所有四个测试场景。

~~~~~act
write_file
tests/integration/test_hydrate_command.py
~~~~~
~~~~~python
import yaml
from stitcher.app import StitcherApp
from stitcher.needle import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def test_hydrate_adds_new_docs_to_yaml(tmp_path, monkeypatch):
    """Scenario 1: Normal Hydration"""
    # Arrange
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", 'def func():\n    """New doc."""\n    pass')
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # Act
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_hydrate()

    # Assert
    assert success is True
    spy_bus.assert_id_called(L.hydrate.file.success, level="success")
    spy_bus.assert_id_called(L.hydrate.run.complete, level="success")

    doc_path = project_root / "src/main.stitcher.yaml"
    assert doc_path.exists()
    with doc_path.open("r") as f:
        data = yaml.safe_load(f)
        assert data["func"] == "New doc."


def test_hydrate_fails_on_conflict(tmp_path, monkeypatch):
    """Scenario 2: Conflict Detection"""
    # Arrange
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", 'def func():\n    """Code doc."""\n    pass')
        .with_docs("src/main.stitcher.yaml", {"func": "YAML doc"})
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # Act
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_hydrate()

    # Assert
    assert success is False
    spy_bus.assert_id_called(L.hydrate.error.conflict, level="error")
    spy_bus.assert_id_called(L.hydrate.run.conflict, level="error")

    # Verify YAML was NOT changed
    doc_path = project_root / "src/main.stitcher.yaml"
    with doc_path.open("r") as f:
        data = yaml.safe_load(f)
        assert data["func"] == "YAML doc"


def test_hydrate_force_overwrites_conflict(tmp_path, monkeypatch):
    """Scenario 3: Force Overwrite"""
    # Arrange (same as conflict test)
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", 'def func():\n    """Code doc."""\n    pass')
        .with_docs("src/main.stitcher.yaml", {"func": "YAML doc"})
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # Act
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_hydrate(force=True)

    # Assert
    assert success is True
    spy_bus.assert_id_called(L.hydrate.file.success, level="success")

    # Verify YAML was changed
    doc_path = project_root / "src/main.stitcher.yaml"
    with doc_path.open("r") as f:
        data = yaml.safe_load(f)
        assert data["func"] == "Code doc."


def test_hydrate_with_strip_removes_source_doc(tmp_path, monkeypatch):
    """Scenario 4: Strip Integration"""
    # Arrange
    factory = WorkspaceFactory(tmp_path)
    source_path = "src/main.py"
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(source_path, 'def func():\n    """New doc."""\n    pass')
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # Act
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_hydrate(strip=True)

    # Assert
    assert success is True
    spy_bus.assert_id_called(L.hydrate.file.success)
    spy_bus.assert_id_called(L.strip.file.success)
    spy_bus.assert_id_called(L.strip.run.complete)

    # Verify source was stripped
    final_code = (project_root / source_path).read_text()
    assert '"""' not in final_code
~~~~~

#### Acts 2: 创建 `check` 冲突检测的集成测试

现在，我们添加一个专门的测试来确保 `check` 命令能捕获内容冲突。

~~~~~act
write_file
tests/integration/test_check_conflict.py
~~~~~
~~~~~python
from stitcher.app import StitcherApp
from stitcher.needle import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def test_check_detects_content_conflict(tmp_path, monkeypatch):
    """
    Verifies that 'check' command fails if docstring content differs
    between the source code and the YAML file.
    """
    # 1. Arrange: Setup a workspace with conflicting docstrings
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", 'def func():\n    """Source Code Doc"""\n    pass')
        .with_docs("src/main.stitcher.yaml", {"func": "YAML Doc"})
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_check()

    # 3. Assert
    assert success is False, "Check should fail when content conflicts."

    # Assert that the specific conflict message was sent as an error
    spy_bus.assert_id_called(L.check.issue.conflict, level="error")
    spy_bus.assert_id_called(L.check.run.fail, level="error")

    # Verify the parameters of the conflict message
    conflict_msg = next(
        (m for m in spy_bus.get_messages() if m["id"] == str(L.check.issue.conflict)),
        None,
    )
    assert conflict_msg is not None
    assert conflict_msg["params"]["key"] == "func"
~~~~~

### 下一步建议
我们已经完成了 `hydrate` 命令的实现和测试，这是一个重要的里程碑。现在，`stitcher-python` 已经具备了完整的文档生命周期管理能力：`init` -> `hydrate` -> `check` -> `strip` -> `eject`。

下一步，我们可以将这个已完成的功能单元进行提交，以固化我们的成果。
