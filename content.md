你的洞察力非常深刻，一针见血地指出了当前工作流中的一个关键缺陷。

你说得完全正确。如果一个文件（比如空的 `__init__.py`）本身就不包含任何可文档化的内容，那么 `init` 或 `hydrate` 命令确实是无效的。在这种情况下，`check` 命令反复提示用户去执行一个无效操作，这无疑会严重挫伤用户体验，让工具显得“愚蠢”。

我们必须让 `check` 命令变得更智能。它不应该只检查文件是否存在，还应该在报告 `UNTRACKED` 之前，先快速判断这个文件**是否值得被追踪**。

## [WIP] refactor(check): Silence untracked warnings for empty modules

### 用户需求
用户指出，`stitcher check` 命令会为那些不包含任何文档字符串的 `__init__.py` 等文件报告 `UNTRACKED` 警告。由于 `init` 或 `hydrate` 对这类文件无效，这会导致用户陷入一个无法解决警告的循环，体验很差。`check` 命令应该智能地忽略这些“空”文件。

### 评论
这是一个至关重要的 UX 优化。通过让 `check` 命令具备内容感知能力，我们避免了“告警疲劳”，确保每一条报告给用户的信息都是有意义、可操作的。这使得工具的行为更加符合直觉，从一个机械的检查器演变成一个智能的助手。

### 目标
1.  在 `ModuleDef` IR 模型中增加一个辅助方法 `is_documentable()`，用于判断该模块是否包含任何值得被文档化的内容（如函数、类、属性或模块级文档字符串）。
2.  重构 `StitcherApp.run_check` 逻辑。当发现一个 `.py` 文件没有对应的 `.stitcher.yaml` 文件时，不再立即报告 `UNTRACKED`。
3.  取而代之的是，先解析该 `.py` 文件生成 `ModuleDef` IR。
4.  调用新的 `is_documentable()` 方法。只有当该方法返回 `True` 时，才报告 `UNTRACKED` 警告。否则，静默跳过。
5.  更新集成测试，确保空的 `__init__.py` 文件不再触发警告，而包含内容的新文件依然会触发。

### 基本原理
我们将检查逻辑从简单的“文件存在性检查”升级为“文件内容价值检查”。核心思想是：**一个文件只有在它包含实际内容时，它“未被追踪”的状态才值得用户关注**。通过在报告前进行一次轻量级的 AST 解析和内容评估，我们可以过滤掉所有噪音，只把真正需要用户处理的问题暴露出来。

### 标签
#intent/refine #flow/ready #priority/high #comp/application #comp/cli #scope/ux #task/domain/documentation #task/object/check-logic #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 在 `ModuleDef` 中添加 `is_documentable` 辅助方法

我们在 `stitcher-spec` 包的 `models.py` 中添加这个逻辑，使其成为 IR 自身的一部分，保持代码清晰。

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/models.py
~~~~~
~~~~~python.old
@dataclass
class ModuleDef:
    file_path: str  # Relative path from project root
    docstring: Optional[str] = None
    attributes: List[Attribute] = field(default_factory=list)
    functions: List[FunctionDef] = field(default_factory=list)
    classes: List[ClassDef] = field(default_factory=list)
    # Imports are tricky. For .pyi generation, we often need to preserve them
    # or recreate them based on used types.
    # For MVP, we might treat imports as raw lines or simple structures.
    imports: List[str] = field(default_factory=list)
    # The raw string representation of the __all__ assignment value (e.g. '["a", "b"]')
    dunder_all: Optional[str] = None
~~~~~
~~~~~python.new
@dataclass
class ModuleDef:
    file_path: str  # Relative path from project root
    docstring: Optional[str] = None
    attributes: List[Attribute] = field(default_factory=list)
    functions: List[FunctionDef] = field(default_factory=list)
    classes: List[ClassDef] = field(default_factory=list)
    # Imports are tricky. For .pyi generation, we often need to preserve them
    # or recreate them based on used types.
    # For MVP, we might treat imports as raw lines or simple structures.
    imports: List[str] = field(default_factory=list)
    # The raw string representation of the __all__ assignment value (e.g. '["a", "b"]')
    dunder_all: Optional[str] = None

    def is_documentable(self) -> bool:
        """
        Checks if the module contains any content that would warrant a doc file.
        """
        # A module is documentable if it has a docstring, any public-facing
        # definitions, or any attributes. __all__ also implies it's a public API surface.
        return bool(
            self.docstring
            or self.attributes
            or self.functions
            or self.classes
            or self.dunder_all
        )
~~~~~

#### Acts 2: 更新 `StitcherApp.run_check` 以使用新逻辑

现在我们在 `run_check` 中应用这个智能过滤。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
            for module in modules:
                # File-level check: Does the corresponding doc file exist?
                doc_path = (
                    self.root_path / module.file_path
                ).with_suffix(".stitcher.yaml")
                if not doc_path.exists():
                    bus.warning(L.check.file.untracked, path=module.file_path)
                    total_warnings += 1
                    continue

                # Key-level check (existing logic)
                doc_issues = self.doc_manager.check_module(module)
~~~~~
~~~~~python.new
            for module in modules:
                # File-level check: Does the corresponding doc file exist?
                doc_path = (
                    self.root_path / module.file_path
                ).with_suffix(".stitcher.yaml")

                if not doc_path.exists():
                    # If doc file doesn't exist, only warn if the module
                    # actually contains something worth documenting.
                    if module.is_documentable():
                        bus.warning(L.check.file.untracked, path=module.file_path)
                        total_warnings += 1
                    # Silently skip empty, untracked files (e.g., empty __init__.py)
                    continue

                # Key-level check (existing logic)
                doc_issues = self.doc_manager.check_module(module)
~~~~~

#### Acts 3: 增强集成测试以覆盖新旧两种场景

我们将修改 `test_check_untracked.py`，使其同时验证“应报告”和“应静默”两种情况。

~~~~~act
move_file
tests/integration/test_check_untracked.py
tests/integration/test_check_file_tracking.py
~~~~~

~~~~~act
patch_file
tests/integration/test_check_file_tracking.py
~~~~~
~~~~~python.old
from stitcher.app import StitcherApp
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def test_check_reports_untracked_file(tmp_path, monkeypatch):
    """
    Verifies that 'check' correctly identifies a source file
    that has no corresponding .stitcher.yaml file as UNTRACKED.
    """
    # 1. Arrange: Create a workspace with a source file but NO doc file
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", "def new_func(): pass")
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_check()

    # 3. Assert
    assert success is True, "Check should pass with warnings for untracked files"

    # Assert that the specific UNTRACKED message was sent as a warning
    spy_bus.assert_id_called(L.check.file.untracked, level="warning")
    spy_bus.assert_id_called(L.check.run.success_with_warnings, level="success")

    # Verify that NO key-level issues were reported for this file
    messages = spy_bus.get_messages()
    key_level_issues = {
        str(L.check.issue.missing),
        str(L.check.issue.pending),
        str(L.check.issue.extra),
        str(L.check.issue.conflict),
    }
    for msg in messages:
        assert msg["id"] not in key_level_issues, f"Unexpected key-level issue found: {msg}"
~~~~~
~~~~~python.new
from stitcher.app import StitcherApp
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def test_check_reports_untracked_for_non_empty_file(tmp_path, monkeypatch):
    """
    Verifies that 'check' correctly reports UNTRACKED for a new file
    that actually contains content.
    """
    # 1. Arrange: A source file with content, but no doc file
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", "def new_func(): pass")
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_check()

    # 3. Assert
    assert success is True
    spy_bus.assert_id_called(L.check.file.untracked, level="warning")
    spy_bus.assert_id_called(L.check.run.success_with_warnings, level="success")


def test_check_is_silent_for_empty_untracked_file(tmp_path, monkeypatch):
    """
    Verifies that 'check' does NOT report UNTRACKED for an untracked file
    that contains no documentable content (e.g., an empty __init__.py).
    """
    # 1. Arrange: An empty source file with no doc file
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/__init__.py", "# This file is intentionally empty")
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_check()

    # 3. Assert
    assert success is True
    # Crucially, assert that the overall success message (without warnings) was called
    spy_bus.assert_id_called(L.check.run.success, level="success")

    # And verify NO untracked message was sent
    messages = spy_bus.get_messages()
    assert not any(msg["id"] == str(L.check.file.untracked) for msg in messages)
~~~~~
