好的，分析完全正确。`RenameSymbolOperation` 在执行符号重命名时，只修改了 Python 源代码，却忽略了与之关联的 sidecar 文件（文档 `.stitcher.yaml` 和签名 `.json`）。这导致了元数据与代码状态的不一致。

为了捕获这个 bug，我将更新 `test_debug_rename_failure.py` 测试。在测试初始化阶段，我会一并创建 mock 的 sidecar 文件；在断言阶段，我会检查这些 sidecar 文件中的键是否也已从 `MessageBus` 被正确地重命名为 `FeedbackBus`。

## [WIP] fix(refactor): 为重命名失败测试添加 sidecar 文件检查

### 错误分析

`RenameSymbolOperation` 的 `analyze` 方法在规划文件操作时，其逻辑只涵盖了对 Python 源代码（`.py`）的修改。它成功地通过语义图谱找到了符号的所有用法并进行了重命名，但完全没有查询或处理与这些符号关联的 sidecar 文件，如 `.stitcher.yaml`（文档）和 `.stitcher/signatures/... .json`（签名）。

这导致重构操作是不完整的。虽然代码层面看起来是正确的（测试也因此通过），但元数据层（文档和签名）却被遗留在了旧的状态，从而在下一次运行 `stitcher check` 时报告“悬空文档”错误。根本原因在于测试覆盖率不足，没有将 sidecar 文件视为符号身份的一部分进行验证。

### 用户需求

用户要求我修改集成测试 `packages/stitcher-refactor/tests/integration/test_debug_rename_failure.py`，使其能够捕获 `RenameSymbolOperation` 未能更新 sidecar 文件的 bug。

### 评论

这是一个非常重要的修复。一个声称能进行符号重构的工具，必须保证操作的原子性和完整性，即同步更新与该符号相关的所有资产，包括代码、文档和签名。将 sidecar 文件纳入测试范围，是确保重构引擎健壮性的关键一步。

### 目标

1.  修改 `test_debug_rename_failure_analysis` 测试用例。
2.  在 `WorkspaceFactory` 的构建阶段，添加一个 `bus.stitcher.yaml` 文档文件和一个对应的 `bus.json` 签名文件。
3.  在测试的断言阶段，增加对这两个 sidecar 文件内容的检查，验证其中的键是否已从 `stitcher.common.messaging.bus.MessageBus` 被正确重命名为 `stitcher.common.messaging.bus.FeedbackBus`。

### 基本原理

我将使用 `patch_file` 来替换整个 `test_debug_rename_failure_analysis` 函数。新的实现将在 `WorkspaceFactory` 中使用 `.with_docs()` 和 `.with_raw_file()` 方法来创建所需的 sidecar 文件。在测试执行并提交事务后，我将使用 `yaml.safe_load` 和 `json.loads` 读取并解析被修改后的 sidecar 文件，然后断言新的 FQN 键存在且旧的 FQN 键已被移除。

### 标签

#intent/fix #flow/ready #priority/high #comp/tests #concept/state #scope/core #ai/instruct #task/domain/testing #task/object/refactor-engine #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 更新集成测试以包含 Sidecar 文件验证

此操作将修改测试文件，为 `bus.py` 添加文档和签名 sidecar 文件，并在重构后验证它们的内容是否被正确更新。

~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_debug_rename_failure.py
~~~~~
~~~~~python.old
def test_debug_rename_failure_analysis(tmp_path):
    """
    A diagnostic test to inspect why the class definition in bus.py is not being renamed.
    """
    # 1. ARRANGE
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_pyproject(".")
        .with_pyproject("packages/stitcher-common")
        # Simulate the __init__.py that imports it
        .with_source(
            "packages/stitcher-common/src/stitcher/common/__init__.py",
            "from .messaging.bus import MessageBus\n"
        )
        # Simulate the protocols.py needed for import resolution
        .with_source(
            "packages/stitcher-common/src/stitcher/common/messaging/protocols.py",
            "class Renderer: pass"
        )
        # Add the missing __init__.py to make 'messaging' a valid package
        .with_source(
            "packages/stitcher-common/src/stitcher/common/messaging/__init__.py",
            ""
        )
        # Use REAL content for bus.py
        .with_source(
            "packages/stitcher-common/src/stitcher/common/messaging/bus.py", 
            BUS_PY_CONTENT
        )
        .build()
    )

    bus_path = project_root / "packages/stitcher-common/src/stitcher/common/messaging/bus.py"
    target_fqn = "stitcher.common.messaging.bus.MessageBus"
    new_fqn = "stitcher.common.messaging.bus.FeedbackBus"

    # 2. LOAD GRAPH
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace)
    
    print(f"\n[DEBUG] Loading 'stitcher' package...")
    graph.load("stitcher")
    
    # --- DIAGNOSTIC 1: Check if module loaded ---
    module = graph.get_module("stitcher.common.messaging.bus")
    if module:
        print(f"[DEBUG] Module 'stitcher.common.messaging.bus' loaded successfully.")
        print(f"[DEBUG] Module path: {module.path}")
        print(f"[DEBUG] Module filepath: {module.filepath}")
    else:
        # Try finding it via parent
        parent = graph.get_module("stitcher.common")
        print(f"[DEBUG] Could not find 'stitcher.common.messaging.bus' directly.")
        if parent:
            print(f"[DEBUG] Found parent 'stitcher.common'. Members: {list(parent.members.keys())}")
    
    # --- DIAGNOSTIC 2: Check UsageRegistry ---
    usages = graph.registry.get_usages(target_fqn)
    print(f"[DEBUG] Found {len(usages)} usages for {target_fqn}")
    
    bus_file_usages = []
    for u in usages:
        print(f"  - [{u.ref_type.name}] {u.file_path}: {u.lineno}:{u.col_offset}")
        # Check if this usage points to our bus.py file
        # Note: u.file_path is absolute, bus_path is absolute
        if u.file_path.resolve() == bus_path.resolve():
            bus_file_usages.append(u)

    print(f"[DEBUG] Usages inside bus.py: {len(bus_file_usages)}")

    # 3. EXECUTE REFACTOR
    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace, graph=graph, sidecar_manager=sidecar_manager
    )

    op = RenameSymbolOperation(target_fqn, new_fqn)
    file_ops = op.analyze(ctx)

    print(f"[DEBUG] Planner generated {len(file_ops)} operations.")
    for fop in file_ops:
        print(f"  - OP: {fop.describe()} on {fop.path}")

    tm = TransactionManager(project_root)
    for fop in file_ops:
        tm.add_write(fop.path, fop.content)
    tm.commit()

    # 4. FINAL ASSERTION
    updated_content = bus_path.read_text()
    if "class FeedbackBus:" not in updated_content:
        pytest.fail(
            "BUG REPRODUCED: 'class MessageBus' was NOT renamed to 'class FeedbackBus' inside bus.py.\n"
            f"See stdout for debug info."
        )
    else:
        print("[SUCCESS] Rename worked in test environment.")
~~~~~
~~~~~python.new
import yaml
import json


def test_debug_rename_failure_analysis(tmp_path):
    """
    A diagnostic test to inspect why the class definition in bus.py is not being renamed,
    AND to verify that sidecar files are also not being updated.
    """
    # 1. ARRANGE
    factory = WorkspaceFactory(tmp_path)
    old_fqn = "stitcher.common.messaging.bus.MessageBus"
    new_fqn = "stitcher.common.messaging.bus.FeedbackBus"

    project_root = (
        factory.with_pyproject(".")
        .with_pyproject("packages/stitcher-common")
        .with_source(
            "packages/stitcher-common/src/stitcher/common/__init__.py",
            "from .messaging.bus import MessageBus\n",
        )
        .with_source(
            "packages/stitcher-common/src/stitcher/common/messaging/protocols.py",
            "class Renderer: pass",
        )
        .with_source(
            "packages/stitcher-common/src/stitcher/common/messaging/__init__.py", ""
        )
        .with_source(
            "packages/stitcher-common/src/stitcher/common/messaging/bus.py",
            BUS_PY_CONTENT,
        )
        # ADD SIDECAR FILES
        .with_docs(
            "packages/stitcher-common/src/stitcher/common/messaging/bus.stitcher.yaml",
            {
                "MessageBus": "Docs for MessageBus.",
                "MessageBus.info": "Docs for info method.",
            },
        )
        .with_raw_file(
            ".stitcher/signatures/packages/stitcher-common/src/stitcher/common/messaging/bus.json",
            json.dumps({old_fqn: {"hash": "abc"}}),
        )
        .build()
    )

    bus_path = (
        project_root
        / "packages/stitcher-common/src/stitcher/common/messaging/bus.py"
    )
    bus_yaml_path = bus_path.with_suffix(".stitcher.yaml")
    bus_sig_path = (
        project_root
        / ".stitcher/signatures/packages/stitcher-common/src/stitcher/common/messaging/bus.json"
    )

    # 2. LOAD GRAPH
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace)
    graph.load("stitcher")

    # 3. EXECUTE REFACTOR
    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace, graph=graph, sidecar_manager=sidecar_manager
    )
    op = RenameSymbolOperation(old_fqn, new_fqn)
    file_ops = op.analyze(ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        tm.add_write(fop.path, fop.content)
    tm.commit()

    # 4. FINAL ASSERTION
    # Assert Python file content
    updated_content = bus_path.read_text()
    assert (
        "class FeedbackBus:" in updated_content
    ), "BUG: Python code definition was not renamed."

    # Assert YAML sidecar content
    updated_yaml_data = yaml.safe_load(bus_yaml_path.read_text())
    assert (
        "FeedbackBus" in updated_yaml_data
    ), "BUG: YAML doc key was not renamed."
    assert "MessageBus" not in updated_yaml_data
    assert (
        "FeedbackBus.info" in updated_yaml_data
    ), "BUG: YAML doc method key was not renamed."

    # Assert Signature sidecar content
    updated_sig_data = json.loads(bus_sig_path.read_text())
    assert (
        new_fqn in updated_sig_data
    ), "BUG: Signature JSON FQN key was not renamed."
    assert old_fqn not in updated_sig_data
    assert updated_sig_data[new_fqn] == {"hash": "abc"}
~~~~~

### 下一步建议

现在这个测试用例应该会因为 sidecar 文件断言失败而挂起（如果代码修改断言通过的话）。下一步是修复 `RenameSymbolOperation` 的 `analyze` 方法，使其在规划重构操作时，能够一并处理和更新与被重命名符号相关的所有 sidecar 文件。
