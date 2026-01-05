好的，我们立即开始。

为了确保 `RenameSymbolOperation` 在 monorepo 环境下的健壮性，我将编写一个新的端到端测试。这个测试将模拟一个真实世界的场景：在一个包中重命名一个类，并验证所有依赖它的地方——包括另一个包中的业务代码、包自己的测试代码，以及项目顶层的集成测试——都被正确地自动更新。

## [WIP] test(refactor): 为 RenameSymbolOperation 添加 Monorepo E2E 测试

### 用户需求

为 `RenameSymbolOperation` 编写一个全面的端到端测试，以确保当它在一个 monorepo 项目中执行时，能够正确地更新所有跨包的符号引用，包括源码和测试文件。

### 评论

这是完成 monorepo 支持故事的关键一步。通过为 `RenameSymbolOperation` 添加专门的测试，我们验证了之前对 `SemanticGraph` 的增强是通用的，能够使所有依赖于它的重构算子都具备 monorepo 感知能力。这确保了整个重构套件在复杂项目结构中的行为一致性和可靠性。

### 目标

1.  创建一个新的集成测试文件 `test_rename_symbol_monorepo_e2e.py`。
2.  在该文件中，使用 `WorkspaceFactory` 构建一个包含两个包（`pkg_a`, `pkg_b`）和顶层 `tests` 目录的 monorepo。
3.  `pkg_a` 中定义一个名为 `OldNameClass` 的类，并为其创建相应的包内测试、sidecar 文档和签名文件。
4.  `pkg_b` 和顶层 `tests` 中都导入并使用 `OldNameClass`。
5.  执行 `RenameSymbolOperation` 将 `OldNameClass` 重命名为 `NewNameClass`。
6.  断言所有引用点（`pkg_a` 的定义、`pkg_a` 的测试、`pkg_b` 的代码、顶层测试）以及 sidecar 文件中的键都已正确更新。

### 基本原理

这个端到端测试是对我们增强后的 `SemanticGraph` 的终极考验。`SemanticGraph` 现在能够扫描并加载整个 monorepo 的代码图谱（包括所有 `src` 和 `tests` 目录）。因此，当 `RenameSymbolOperation` 请求 `UsageRegistry` 提供 `OldNameClass` 的所有使用位置时，它应该能收到一个包含所有业务代码和测试代码中引用点的完整列表。

`RenameSymbolOperation` 会为每个受影响的文件生成一个 `WriteFileOp`，其内容由 `SymbolRenamerTransformer` 修改。只要 `UsageRegistry` 的数据是完整和准确的，整个重构链条就能无缝工作。此测试将直接验证这个从图谱构建到代码转换的完整流程。

### 标签

#intent/tooling #flow/ready #priority/high #comp/tests #concept/state #scope/dx #ai/instruct #task/state/continue

---

### Script

#### Acts 1: 创建 `RenameSymbolOperation` 的 Monorepo 测试用例

我将创建新的测试文件，并填充完整的测试逻辑。

~~~~~act
write_file
packages/stitcher-refactor/tests/integration/test_rename_symbol_monorepo_e2e.py
~~~~~
~~~~~python
import json
import yaml
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.transaction import TransactionManager
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.test_utils import WorkspaceFactory


def test_rename_symbol_in_monorepo_updates_all_references_and_sidecars(tmp_path):
    # 1. ARRANGE: Build a monorepo with cross-package and test references
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory
        # --- Package A: Defines the symbol ---
        .with_source("packages/pkg_a/src/pkga_lib/__init__.py", "")
        .with_source(
            "packages/pkg_a/src/pkga_lib/core.py", "class OldNameClass: pass"
        )
        .with_docs(
            "packages/pkg_a/src/pkga_lib/core.stitcher.yaml",
            {"pkga_lib.core.OldNameClass": "Docs for the old class."},
        )
        .with_raw_file(
            ".stitcher/signatures/packages/pkg_a/src/pkga_lib/core.json",
            json.dumps({"pkga_lib.core.OldNameClass": {"hash": "abc"}}),
        )
        .with_source(
            "packages/pkg_a/tests/test_core.py",
            "from pkga_lib.core import OldNameClass\n\ndef test_local():\n    assert OldNameClass is not None",
        )
        # --- Package B: Consumes the symbol ---
        .with_source("packages/pkg_b/src/pkgb_app/__init__.py", "")
        .with_source(
            "packages/pkg_b/src/pkgb_app/main.py",
            "from pkga_lib.core import OldNameClass\n\ninstance = OldNameClass()",
        )
        # --- Top-level integration test: Also consumes the symbol ---
        .with_source(
            "tests/integration/test_system.py",
            "from pkga_lib.core import OldNameClass\n\ndef test_system_integration():\n    assert OldNameClass",
        )
        .build()
    )

    # Define paths for verification
    definition_path = project_root / "packages/pkg_a/src/pkga_lib/core.py"
    pkg_a_test_path = project_root / "packages/pkg_a/tests/test_core.py"
    pkg_b_main_path = project_root / "packages/pkg_b/src/pkgb_app/main.py"
    top_level_test_path = project_root / "tests/integration/test_system.py"
    doc_path = definition_path.with_suffix(".stitcher.yaml")
    sig_path = (
        project_root
        / ".stitcher/signatures/packages/pkg_a/src/pkga_lib/core.json"
    )

    # 2. ACT
    graph = SemanticGraph(root_path=project_root)
    graph.load("pkga_lib")
    graph.load("pkgb_app")
    graph.load("test_core")
    graph.load("integration")
    ctx = RefactorContext(graph=graph)

    op = RenameSymbolOperation("pkga_lib.core.OldNameClass", "pkga_lib.core.NewNameClass")
    file_ops = op.analyze(ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        tm.add_write(fop.path, fop.content)
    tm.commit()

    # 3. ASSERT
    # --- Code Files ---
    expected_import = "from pkga_lib.core import NewNameClass"
    assert "class NewNameClass: pass" in definition_path.read_text()
    assert expected_import in pkg_a_test_path.read_text()
    assert expected_import in pkg_b_main_path.read_text()
    assert expected_import in top_level_test_path.read_text()

    # --- Sidecar Files ---
    new_fqn = "pkga_lib.core.NewNameClass"
    old_fqn = "pkga_lib.core.OldNameClass"

    # YAML Doc file
    doc_data = yaml.safe_load(doc_path.read_text())
    assert new_fqn in doc_data
    assert old_fqn not in doc_data
    assert doc_data[new_fqn] == "Docs for the old class."

    # JSON Signature file
    sig_data = json.loads(sig_path.read_text())
    assert new_fqn in sig_data
    assert old_fqn not in sig_data
    assert sig_data[new_fqn] == {"hash": "abc"}
~~~~~

### 下一步建议

我们已经为 `stitcher-refactor` 的核心算子（移动和重命名）建立了坚实的 monorepo 支持和测试保障。下一步可以专注于提升其健壮性和用户体验：

-   **冲突检测**：在 `analyze` 阶段增加冲突检测逻辑。例如，如果重命名或移动的目标已经存在，应向用户报告错误，而不是静默覆盖。
-   **交互式预览与确认**：在 `TransactionManager.commit()` 之前，实现一个交互式流程，向用户清晰地展示所有待执行的文件变更（diff 格式），并请求最终确认。
-   **性能基准测试**：针对一个包含大量包和文件的真实大型 monorepo（或模拟的）运行重构操作，建立性能基准，以识别潜在的瓶颈。
