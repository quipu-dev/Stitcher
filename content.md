是的，我在 `SignatureManager` 的实现中正是使用了标准的 `json.dump` 和 `json.load`，并将文件后缀定为 `.json`。这不仅对机器友好，也方便在必要时进行人工调试，完全符合你的建议。

现在，我们开始编写配套的测试用例。

简要回答
我们将创建单元测试和集成测试，以验证签名指纹的计算稳定性、持久化逻辑以及在 `check` 命令中的集成效果。

## [WIP] test: 添加签名指纹机制的单元测试与集成测试

### 用户需求
验证新引入的“签名指纹”机制能够正确工作。具体包括：
1.  确保相同的函数签名生成相同的指纹，不同的签名生成不同的指纹。
2.  确保 `SignatureManager` 能正确地将指纹保存为 JSON 并读取。
3.  确保当用户修改代码导致签名变更时，`stitcher check` 能通过集成流程检测到并报告错误。

### 评论
测试策略分为两层：
*   **单元测试 (`stitcher-application`)**: 聚焦于 `FunctionDef.compute_fingerprint` 的纯逻辑验证，以及 `SignatureManager` 的 I/O 契约。
*   **集成测试 (`tests/integration`)**: 模拟真实的用户工作流（Init -> Modify Code -> Check），验证整个系统组件（Scanner -> Manager -> App -> Bus）的协同工作。

### 目标
1.  创建 `packages/stitcher-application/tests/test_signature_manager.py`。
2.  创建 `tests/integration/test_check_signatures.py`。

### 基本原理
通过 `stitcher-test-utils` 提供的 `WorkspaceFactory`，我们可以轻松构建包含源代码的临时工作区，并模拟文件修改。配合 `SpyBus`，我们可以断言特定的语义消息 (`L.check.issue.mismatch`) 是否被触发，从而验证业务价值。

### 标签
#intent/tooling #flow/ready #priority/high
#comp/tests #comp/application #comp/cli
#task/domain/quality #task/object/signature-verification #task/action/test #task/state/continue

---

### Script

#### Acts 1: 创建单元测试

测试指纹计算的稳定性和 `SignatureManager` 的基本功能。

~~~~~act
write_file
packages/stitcher-application/tests/test_signature_manager.py
~~~~~
~~~~~python
import json
from pathlib import Path
from stitcher.spec import ModuleDef, FunctionDef, Argument, ArgumentKind
from stitcher.app.services import SignatureManager


def create_func(name="func", args=None, ret=None):
    """Helper to create a FunctionDef."""
    return FunctionDef(
        name=name,
        args=args or [],
        return_annotation=ret,
    )


def test_fingerprint_stability():
    """
    Test that compute_fingerprint is deterministic and sensitive to changes.
    """
    # 1. Base case
    arg_a = Argument(name="a", kind=ArgumentKind.POSITIONAL_OR_KEYWORD, annotation="int")
    func1 = create_func(name="my_func", args=[arg_a], ret="str")
    fp1 = func1.compute_fingerprint()

    # 2. Identical function should have identical fingerprint
    func2 = create_func(name="my_func", args=[arg_a], ret="str")
    fp2 = func2.compute_fingerprint()
    assert fp1 == fp2

    # 3. Change in parameter name -> Different
    arg_b = Argument(name="b", kind=ArgumentKind.POSITIONAL_OR_KEYWORD, annotation="int")
    func3 = create_func(name="my_func", args=[arg_b], ret="str")
    assert fp1 != func3.compute_fingerprint()

    # 4. Change in annotation -> Different
    arg_a_str = Argument(name="a", kind=ArgumentKind.POSITIONAL_OR_KEYWORD, annotation="str")
    func4 = create_func(name="my_func", args=[arg_a_str], ret="str")
    assert fp1 != func4.compute_fingerprint()

    # 5. Change in return type -> Different
    func5 = create_func(name="my_func", args=[arg_a], ret="int")
    assert fp1 != func5.compute_fingerprint()


def test_manager_save_and_load(tmp_path: Path):
    """
    Test that SignatureManager correctly persists fingerprints to JSON.
    """
    # Arrange
    manager = SignatureManager(root_path=tmp_path)
    module = ModuleDef(
        file_path="src/main.py",
        functions=[create_func(name="foo")]
    )
    
    # Act: Save
    manager.save_signatures(module)
    
    # Assert: File exists and is JSON
    sig_path = tmp_path / ".stitcher/signatures/src/main.json"
    assert sig_path.exists()
    
    with sig_path.open("r") as f:
        data = json.load(f)
        assert "foo" in data
        assert isinstance(data["foo"], str)
        
    # Act: Load
    loaded = manager.load_signatures(module)
    assert loaded["foo"] == data["foo"]


def test_manager_check_detects_mismatch(tmp_path: Path):
    """
    Test that check_signatures logic correctly identifies differences.
    """
    manager = SignatureManager(root_path=tmp_path)
    module = ModuleDef(
        file_path="src/main.py",
        functions=[create_func(name="foo", ret="int")]
    )
    
    # 1. Save baseline
    manager.save_signatures(module)
    
    # 2. Modify module (change return type)
    module_modified = ModuleDef(
        file_path="src/main.py",
        functions=[create_func(name="foo", ret="str")]
    )
    
    # 3. Check
    issues = manager.check_signatures(module_modified)
    
    # 4. Assert
    assert "foo" in issues
    assert issues["foo"] == "signature_mismatch"
~~~~~

#### Acts 2: 创建集成测试

模拟完整工作流：Init -> Modify -> Check。

~~~~~act
write_file
tests/integration/test_check_signatures.py
~~~~~
~~~~~python
from stitcher.app import StitcherApp
from stitcher.needle import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def test_check_detects_signature_change(tmp_path, monkeypatch):
    """
    End-to-End test verifying that modifying a function signature
    triggers a check failure/warning.
    """
    # 1. Setup Initial Workspace
    factory = WorkspaceFactory(tmp_path)
    # Define a simple function with one argument
    initial_code = """
    def process(value: int) -> int:
        \"\"\"Process an integer.\"\"\"
        return value * 2
    """
    
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/processor.py", initial_code)
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Run Init (This should establish the baseline signatures)
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        app.run_init()
        
    # Verify init was successful
    spy_bus.assert_id_called(L.init.run.complete, level="success")
    
    # 3. Modify Code (Change argument type int -> str)
    modified_code = """
    def process(value: str) -> int:
        \"\"\"Process a string (Changed).\"\"\"
        return len(value) * 2
    """
    (project_root / "src/processor.py").write_text(modified_code, encoding="utf-8")
    
    # Clear previous messages
    spy_bus = SpyBus()
    
    # 4. Run Check
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_check()
        
    # 5. Assertions
    # Check should report failure (or at least issues found)
    assert success is False
    
    # Verify the specific mismatch message was fired
    spy_bus.assert_id_called(L.check.issue.mismatch, level="error")
    
    # Verify we specifically complained about 'process'
    mismatch_msgs = [
        m for m in spy_bus.get_messages() 
        if str(L.check.issue.mismatch) == m["id"]
    ]
    assert len(mismatch_msgs) == 1
    assert mismatch_msgs[0]["params"]["key"] == "process"


def test_generate_updates_signatures(tmp_path, monkeypatch):
    """
    Verify that running 'generate' updates the signature baseline,
    so subsequent checks pass.
    """
    # 1. Setup Workspace
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", "def func(a: int): ...")
        .with_docs("src/main.stitcher.yaml", {"func": "doc"})
        .build()
    )
    
    app = StitcherApp(root_path=project_root)
    
    # 2. Run Init
    with SpyBus().patch(monkeypatch, "stitcher.app.core.bus"):
        app.run_init()
        
    # 3. Modify Code
    (project_root / "src/main.py").write_text("def func(a: str): ...", encoding="utf-8")
    
    # 4. Run Generate (Should update signatures)
    with SpyBus().patch(monkeypatch, "stitcher.app.core.bus"):
        app.run_from_config()
        
    # 5. Run Check (Should now pass because baseline was updated)
    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_check()
        
    assert success is True
    spy_bus.assert_id_called(L.check.run.success, level="success")
~~~~~
