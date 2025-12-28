此计划执行两个核心任务：
1.  **重构测试架构**: 将所有包的测试套件严格划分为 `unit` 和 `integration` 两个层级，解决当前测试文件存放混乱的问题。
2.  **创建 ViewDiff 测试**: 新增针对 `viewdiff` 功能的单元测试（签名文本提取）和集成测试（Diff 生成流），以验证上一阶段的应用层变更。

## [WIP] test: 重构测试目录结构并添加 ViewDiff 测试套件

### 摘要头
## [WIP] test: 重构测试目录结构并添加 ViewDiff 测试套件

### 用户需求
1.  将现有的测试文件按照 `unit` 和 `integration` 进行分类移动，规范化测试目录结构。
2.  为新实现的 `viewdiff` 功能（签名文本提取、Diff 生成与传递）编写测试用例。

### 评论
测试结构的规范化是项目长期维护的基础。将单元测试与集成测试分离可以提高 CI 反馈速度（先跑单元测试），并使测试意图更清晰。针对 `viewdiff` 的测试是验证本次核心功能变更的关键，确保了用户在交互式界面中能看到预期的差异信息。

### 目标
1.  在所有 `packages/*/tests` 目录下建立 `unit` 子目录（`integration` 目录部分包已有）。
2.  将纯函数/类测试移动到 `unit` 目录。
3.  保持涉及 `StitcherApp` 完整流程的测试在 `integration` 目录。
4.  创建 `test_signature_extraction.py` 验证 `SignatureManager` 的新能力。
5.  创建 `test_viewdiff_flow.py` 验证 `check` 和 `pump` 命令中 Diff 数据的生成与传递。

### 基本原理
*   **重构**: 使用 `move_file` 指令重新组织文件结构。
*   **测试策略**:
    *   **Unit**: 验证 `SignatureManager` 能正确通过 `extract_signature_texts` 还原函数签名字符串。
    *   **Integration**: 使用 `WorkspaceFactory` 构建真实项目环境，触发 `SIGNATURE_DRIFT` 和 `DOC_CONTENT_CONFLICT` 场景，通过自定义 `InteractionHandler` 捕获并断言 `InteractionContext` 对象中是否携带了正确的 `diff` 数据。

### 标签
#intent/tooling #intent/test #flow/ready #priority/medium #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/test-suite #task/action/refactor

---

### Script

#### Acts 1: 重构 stitcher-application 测试结构

将 `stitcher-application` 中属于单元测试的文件从 `integration` 移至 `unit`。

~~~~~act
move_file
packages/stitcher-application/tests/test_doc_manager.py
packages/stitcher-application/tests/unit/test_doc_manager.py
~~~~~
~~~~~act
move_file
packages/stitcher-application/tests/test_doc_manager.stitcher.yaml
packages/stitcher-application/tests/unit/test_doc_manager.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/stitcher-application/tests/test_doc_overlay.py
packages/stitcher-application/tests/unit/test_doc_overlay.py
~~~~~
~~~~~act
move_file
packages/stitcher-application/tests/test_doc_overlay.stitcher.yaml
packages/stitcher-application/tests/unit/test_doc_overlay.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/stitcher-application/tests/test_signature_manager.py
packages/stitcher-application/tests/unit/test_signature_manager.py
~~~~~
~~~~~act
move_file
packages/stitcher-application/tests/test_signature_manager.stitcher.yaml
packages/stitcher-application/tests/unit/test_signature_manager.stitcher.yaml
~~~~~

#### Acts 2: 重构 stitcher-scanner 测试结构

`stitcher-scanner` 的测试目前都在根目录，全部视为单元测试移入 `unit`。

~~~~~act
move_file
packages/stitcher-scanner/tests/test_inspector.py
packages/stitcher-scanner/tests/unit/test_inspector.py
~~~~~
~~~~~act
move_file
packages/stitcher-scanner/tests/test_inspector.stitcher.yaml
packages/stitcher-scanner/tests/unit/test_inspector.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/stitcher-scanner/tests/test_parser_advanced.py
packages/stitcher-scanner/tests/unit/test_parser_advanced.py
~~~~~
~~~~~act
move_file
packages/stitcher-scanner/tests/test_parser_advanced.stitcher.yaml
packages/stitcher-scanner/tests/unit/test_parser_advanced.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/stitcher-scanner/tests/test_parser_basic.py
packages/stitcher-scanner/tests/unit/test_parser_basic.py
~~~~~
~~~~~act
move_file
packages/stitcher-scanner/tests/test_parser_basic.stitcher.yaml
packages/stitcher-scanner/tests/unit/test_parser_basic.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/stitcher-scanner/tests/test_parser_dunder_all.py
packages/stitcher-scanner/tests/unit/test_parser_dunder_all.py
~~~~~
~~~~~act
move_file
packages/stitcher-scanner/tests/test_parser_dunder_all.stitcher.yaml
packages/stitcher-scanner/tests/unit/test_parser_dunder_all.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/stitcher-scanner/tests/test_parser_imports.py
packages/stitcher-scanner/tests/unit/test_parser_imports.py
~~~~~
~~~~~act
move_file
packages/stitcher-scanner/tests/test_parser_imports.stitcher.yaml
packages/stitcher-scanner/tests/unit/test_parser_imports.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/stitcher-scanner/tests/test_transformer.py
packages/stitcher-scanner/tests/unit/test_transformer.py
~~~~~
~~~~~act
move_file
packages/stitcher-scanner/tests/test_transformer.stitcher.yaml
packages/stitcher-scanner/tests/unit/test_transformer.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/stitcher-scanner/tests/test_transformer_multiline.py
packages/stitcher-scanner/tests/unit/test_transformer_multiline.py
~~~~~
~~~~~act
move_file
packages/stitcher-scanner/tests/test_transformer_multiline.stitcher.yaml
packages/stitcher-scanner/tests/unit/test_transformer_multiline.stitcher.yaml
~~~~~

#### Acts 3: 重构 stitcher-io 测试结构

`stitcher-io` 的测试也全部移入 `unit`。

~~~~~act
move_file
packages/stitcher-io/tests/test_document_io.py
packages/stitcher-io/tests/unit/test_document_io.py
~~~~~
~~~~~act
move_file
packages/stitcher-io/tests/test_document_io.stitcher.yaml
packages/stitcher-io/tests/unit/test_document_io.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/stitcher-io/tests/test_generator_dunder_all.py
packages/stitcher-io/tests/unit/test_generator_dunder_all.py
~~~~~
~~~~~act
move_file
packages/stitcher-io/tests/test_generator_dunder_all.stitcher.yaml
packages/stitcher-io/tests/unit/test_generator_dunder_all.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/stitcher-io/tests/test_stub_generator.py
packages/stitcher-io/tests/unit/test_stub_generator.py
~~~~~
~~~~~act
move_file
packages/stitcher-io/tests/test_stub_generator.stitcher.yaml
packages/stitcher-io/tests/unit/test_stub_generator.stitcher.yaml
~~~~~

#### Acts 4: 重构其他包测试结构

整理 `stitcher-common` 和 `stitcher-config`。

~~~~~act
move_file
packages/stitcher-common/tests/test_message_bus.py
packages/stitcher-common/tests/unit/test_message_bus.py
~~~~~
~~~~~act
move_file
packages/stitcher-common/tests/test_message_bus.stitcher.yaml
packages/stitcher-common/tests/unit/test_message_bus.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/stitcher-config/tests/test_loader.py
packages/stitcher-config/tests/unit/test_loader.py
~~~~~
~~~~~act
move_file
packages/stitcher-config/tests/test_loader.stitcher.yaml
packages/stitcher-config/tests/unit/test_loader.stitcher.yaml
~~~~~

#### Acts 5: 创建 ViewDiff 单元测试

测试 `SignatureManager.extract_signature_texts` 的能力。

~~~~~act
write_file
packages/stitcher-application/tests/unit/test_signature_extraction.py
~~~~~
~~~~~python
from textwrap import dedent
from stitcher.spec import Argument, ArgumentKind, FunctionDef, ModuleDef
from stitcher.app.services import SignatureManager


def test_extract_signature_text_simple():
    # Arrange
    func = FunctionDef(
        name="my_func",
        args=[
            Argument(
                name="a",
                kind=ArgumentKind.POSITIONAL_OR_KEYWORD,
                annotation="int",
            ),
            Argument(
                name="b",
                kind=ArgumentKind.POSITIONAL_OR_KEYWORD,
                annotation="str",
                default="'default'",
            ),
        ],
        return_annotation="bool",
    )
    module = ModuleDef(file_path="src/main.py", functions=[func])
    
    manager = SignatureManager(root_path=None) # type: ignore

    # Act
    texts = manager.extract_signature_texts(module)

    # Assert
    expected = "def my_func(a: int, b: str = 'default') -> bool:"
    assert texts["my_func"] == expected


def test_extract_signature_text_async():
    # Arrange
    func = FunctionDef(
        name="run",
        is_async=True,
        args=[],
        return_annotation="None",
    )
    module = ModuleDef(file_path="src/main.py", functions=[func])
    
    manager = SignatureManager(root_path=None) # type: ignore

    # Act
    texts = manager.extract_signature_texts(module)

    # Assert
    expected = "async def run() -> None:"
    assert texts["run"] == expected
~~~~~

#### Acts 6: 创建 ViewDiff 集成测试

验证完整的 diff 生成和传递流程。

~~~~~act
write_file
packages/stitcher-application/tests/integration/test_viewdiff_flow.py
~~~~~
~~~~~python
from typing import List
from stitcher.app import StitcherApp
from stitcher.app.protocols import InteractionHandler, InteractionContext
from stitcher.spec import ResolutionAction, ConflictType
from stitcher.test_utils import WorkspaceFactory, SpyBus


class CapturingHandler(InteractionHandler):
    """A handler that captures the contexts passed to it and returns SKIP."""
    def __init__(self):
        self.captured_contexts: List[InteractionContext] = []

    def process_interactive_session(
        self, contexts: List[InteractionContext]
    ) -> List[ResolutionAction]:
        self.captured_contexts.extend(contexts)
        return [ResolutionAction.SKIP] * len(contexts)


def test_check_generates_signature_diff(tmp_path, monkeypatch):
    """
    Verifies that when a signature changes, 'check' generates a unified diff
    and passes it in the InteractionContext.
    """
    # 1. Arrange: Init project with baseline
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", "def func(a: int): ...")
        .build()
    )
    
    # Run init to save baseline signature and TEXT
    app_init = StitcherApp(root_path=project_root)
    with SpyBus().patch(monkeypatch, "stitcher.app.core.bus"):
        app_init.run_init()

    # 2. Modify code to cause signature drift
    (project_root / "src/main.py").write_text("def func(a: str): ...", encoding="utf-8")

    # 3. Run check with capturing handler
    handler = CapturingHandler()
    app_check = StitcherApp(root_path=project_root, interaction_handler=handler)
    
    with SpyBus().patch(monkeypatch, "stitcher.app.core.bus"):
        app_check.run_check()

    # 4. Assert
    assert len(handler.captured_contexts) == 1
    ctx = handler.captured_contexts[0]
    
    assert ctx.conflict_type == ConflictType.SIGNATURE_DRIFT
    assert ctx.signature_diff is not None
    
    # Check for unified diff markers
    assert "--- baseline" in ctx.signature_diff
    assert "+++ current" in ctx.signature_diff
    assert "-def func(a: int):" in ctx.signature_diff
    assert "+def func(a: str):" in ctx.signature_diff


def test_pump_generates_doc_diff(tmp_path, monkeypatch):
    """
    Verifies that when doc content conflicts, 'pump' generates a unified diff
    and passes it in the InteractionContext.
    """
    # 1. Arrange: Project with conflicting docs
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", 'def func():\n    """Code Doc"""\n    pass')
        .with_docs("src/main.stitcher.yaml", {"func": "YAML Doc"})
        .build()
    )

    # 2. Run pump with capturing handler
    handler = CapturingHandler()
    app_pump = StitcherApp(root_path=project_root, interaction_handler=handler)
    
    with SpyBus().patch(monkeypatch, "stitcher.app.core.bus"):
        app_pump.run_pump()

    # 3. Assert
    assert len(handler.captured_contexts) == 1
    ctx = handler.captured_contexts[0]
    
    assert ctx.conflict_type == ConflictType.DOC_CONTENT_CONFLICT
    assert ctx.doc_diff is not None
    
    # Check for unified diff markers
    assert "--- yaml" in ctx.doc_diff
    assert "+++ code" in ctx.doc_diff
    assert "-YAML Doc" in ctx.doc_diff
    assert "+Code Doc" in ctx.doc_diff
~~~~~
