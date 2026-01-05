你提出的方向非常敏锐。`WorkspaceFactory` 的核心价值就在于将测试环境中那些命令式的、繁琐的文件创建过程，转化为声明式的、可读性更高的代码。

我立刻检查了 `packages/stitcher-refactor/tests/integration/` 目录下的测试文件，结果非常明确：

**所有集成测试** (`test_move_directory_e2e.py`, `test_move_file_e2e.py`, `test_rename_e2e.py`, `test_rename_transformer_advanced.py` 等) 目前都在使用手动的 `tmp_path.mkdir()` 和 `path.write_text()` 来搭建测试环境。这正是 `WorkspaceFactory` 要解决的痛点。

然而，在准备重构时，我发现了一个问题：当前的 `WorkspaceFactory` 只提供了 `.with_source()` 和 `.with_docs()` 方法，缺少一个通用的方法来创建像签名文件（`.json`）或其他任意配置文件。

因此，一个更健壮的计划是：
1.  **增强 `WorkspaceFactory`**: 为其增加一个通用的 `.with_raw_file()` 方法。
2.  **应用此增强**: 使用增强后的 `WorkspaceFactory` 来重构其中一个代表性的测试，作为后续所有重构的范本。

我将选择 `test_rename_e2e.py` 作为第一个重构目标，因为它同时涉及了 `.py` 源文件、`.stitcher.yaml` 文档文件和 `.json` 签名文件，是展示新能力的完美案例。

这是我的计划：

## [WIP] refactor: 使用 WorkspaceFactory 重构重构引擎的集成测试

### 用户需求

检查 `stitcher-refactor` 包下的测试，并使用 `WorkspaceFactory` 对其进行重构，以简化测试环境的搭建过程。

### 评论

这是一个极好的开发者体验 (DX) 改进。通过将命令式的文件系统操作（`mkdir`, `write_text`）替换为声明式的 `WorkspaceFactory` 调用，我们不仅能大幅减少测试设置的样板代码，还能让每个测试的“输入”——即项目结构——变得一目了然。

本次重构首先会增强 `WorkspaceFactory` 自身的能力，增加一个 `.with_raw_file()` 方法来处理签名文件等非标准文件，使其成为一个更通用的测试工具。

### 目标

1.  **增强 `WorkspaceFactory`**: 在 `packages/stitcher-test-utils/src/stitcher/test_utils/workspace.py` 中为 `WorkspaceFactory` 类添加一个新的 `.with_raw_file()` 方法，使其能够写入任意格式和内容的文本文件。
2.  **重构测试用例**: 使用增强后的 `WorkspaceFactory` 全面重构 `packages/stitcher-refactor/tests/integration/test_rename_e2e.py` 文件，用声明式 API 替代所有手动的文件和目录创建逻辑。

### 基本原理

重构的核心是遵循“声明式测试环境”原则。我们将不再手动操作 `tmp_path` 对象，而是实例化一个 `WorkspaceFactory`，并通过链式调用来描述我们需要的整个项目结构。

1.  `.with_source()` 用于创建 `.py` 文件。
2.  `.with_docs()` 用于创建 `.stitcher.yaml` 文件。
3.  新增的 `.with_raw_file()` 将用于创建 `.stitcher/signatures/**/*.json` 签名文件，它会直接写入我们提供的字符串内容。

最后调用 `.build()` 方法，`WorkspaceFactory` 会在原子性的操作中为我们生成整个测试环境。这使得测试的“Arrange”阶段变得极为清晰和紧凑。

### 标签

#intent/refine #intent/build #flow/ready #priority/medium #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/workspace-factory #task/action/enhancement #task/state/continue

---

### Script

#### Acts 1: 增强 `WorkspaceFactory`

首先，我们为 `WorkspaceFactory` 添加 `.with_raw_file()` 方法，使其能够处理任意文本文件，这对创建签名文件至关重要。

~~~~~act
patch_file
packages/stitcher-test-utils/src/stitcher/test_utils/workspace.py
~~~~~
~~~~~python.old
    def with_docs(self, path: str, data: Dict[str, Any]) -> "WorkspaceFactory":
        self._files_to_create.append({"path": path, "content": data, "format": "yaml"})
        return self

    def build(self) -> Path:
        # 1. Finalize pyproject.toml if data was added
~~~~~
~~~~~python.new
    def with_docs(self, path: str, data: Dict[str, Any]) -> "WorkspaceFactory":
        self._files_to_create.append({"path": path, "content": data, "format": "yaml"})
        return self

    def with_raw_file(self, path: str, content: str) -> "WorkspaceFactory":
        self._files_to_create.append(
            {"path": path, "content": dedent(content), "format": "raw"}
        )
        return self

    def build(self) -> Path:
        # 1. Finalize pyproject.toml if data was added
~~~~~

#### Acts 2: 重构 `test_rename_e2e.py`

现在，我们将用增强后的 `WorkspaceFactory` 来重写整个测试文件。注意观察 `test_rename_symbol_end_to_end` 函数中的项目设置部分是多么简洁。

~~~~~act
write_file
packages/stitcher-refactor/tests/integration/test_rename_e2e.py
~~~~~
~~~~~python
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import TransactionManager
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.test_utils import WorkspaceFactory


import yaml
import json


def test_rename_symbol_end_to_end(tmp_path):
    # 1. Setup: Use WorkspaceFactory to declaratively build the project
    factory = WorkspaceFactory(tmp_path)
    project_root = factory.with_source(
        "mypkg/core.py",
        """
        class OldHelper:
            pass

        def old_func():
            pass
        """,
    ).with_source(
        "mypkg/app.py",
        """
        from .core import OldHelper, old_func

        h = OldHelper()
        old_func()
        """,
    ).with_source(
        "mypkg/__init__.py", ""
    ).with_docs(
        "mypkg/core.stitcher.yaml",
        {
            "mypkg.core.OldHelper": "This is the old helper.",
            "mypkg.core.old_func": "This is an old function.",
        },
    ).with_raw_file(
        ".stitcher/signatures/mypkg/core.json",
        json.dumps(
            {
                "mypkg.core.OldHelper": {"baseline_code_structure_hash": "hash1"},
                "mypkg.core.old_func": {"baseline_code_structure_hash": "hash2"},
            }
        ),
    ).build()

    core_path = project_root / "mypkg/core.py"
    app_path = project_root / "mypkg/app.py"
    doc_path = project_root / "mypkg/core.stitcher.yaml"
    sig_path = project_root / ".stitcher/signatures/mypkg/core.json"

    # 2. Analysis Phase
    graph = SemanticGraph(root_path=project_root)
    graph.load("mypkg")
    ctx = RefactorContext(graph=graph)

    # 3. Planning Phase
    op = RenameSymbolOperation(
        old_fqn="mypkg.core.OldHelper", new_fqn="mypkg.core.NewHelper"
    )
    file_ops = op.analyze(ctx)

    # 4. Execution Phase
    tm = TransactionManager(project_root)
    for op in file_ops:
        # In a real app, we might add ops one by one. Here we add all.
        # This assumes analyze() returns WriteFileOp with correct content.
        tm.add_write(op.path, op.content)

    tm.commit()

    # 5. Verification Phase
    # Check the file where the definition was
    modified_core_code = core_path.read_text(encoding="utf-8")
    assert "class NewHelper:" in modified_core_code
    assert "class OldHelper:" not in modified_core_code

    # Check the file where it was used
    modified_app_code = app_path.read_text(encoding="utf-8")
    assert "from .core import NewHelper, old_func" in modified_app_code
    assert "h = NewHelper()" in modified_app_code

    # Check sidecar files
    modified_doc_data = yaml.safe_load(doc_path.read_text("utf-8"))
    assert "mypkg.core.NewHelper" in modified_doc_data
    assert "mypkg.core.OldHelper" not in modified_doc_data
    assert modified_doc_data["mypkg.core.NewHelper"] == "This is the old helper."

    modified_sig_data = json.loads(sig_path.read_text("utf-8"))
    assert "mypkg.core.NewHelper" in modified_sig_data
    assert "mypkg.core.OldHelper" not in modified_sig_data
    assert (
        modified_sig_data["mypkg.core.NewHelper"]["baseline_code_structure_hash"]
        == "hash1"
    )
~~~~~

### 下一步建议

我们已经成功地增强了 `WorkspaceFactory` 并用它重构了一个关键的集成测试。现在，`WorkspaceFactory` 已具备处理我们项目中所有类型文件的能力。

下一步，我们可以利用这个增强后的工具，继续将 `packages/stitcher-refactor/tests/integration/` 目录下的其他测试（如 `test_move_directory_e2e.py` 和 `test_move_file_e2e.py`）也逐一进行重构，以统一我们的测试风格，并提高代码库的整体质量。

当你批准这个计划后，我将执行它。完成后，我们可以创建一个 `[COMMIT]` 计划来提交这些改进。
