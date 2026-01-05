好的，你的观察非常敏锐。一个只重构业务代码却忽略了测试代码的工具是不完整的，这会给开发者带来额外的手动修复工作。我们必须确保重构操作是原子化的，能够同步更新代码库中所有相关的引用，包括测试文件。

我将立即执行一个计划来扩展重构引擎的能力，使其能够发现并更新测试文件中的代码引用。

## [WIP] feat(refactor): 在重构过程中同步更新测试文件

### 用户需求

在执行如“移动文件”之类的重构操作时，引擎必须能够自动发现并更新测试文件中对被移动代码的引用。

### 评论

这是一个对开发者体验（DX）至关重要的增强。自动化重构的核心价值在于其可靠性和完整性。如果一个工具只更新了实现，却破坏了测试，那么它就不是一个值得信赖的伙伴。通过将测试文件纳入重构范围，我们极大地提升了 `stitcher-refactor` 的健壮性和实用性，使其成为一个真正能为开发者减负的工具。

### 目标

1.  **扩展 `SemanticGraph` 的发现能力**：修改 `SemanticGraph` 的初始化逻辑，使其除了扫描 `src` 目录外，还能自动发现并扫描项目中的测试目录（如顶层的 `tests/` 和各子包内的 `packages/*/tests/`）。
2.  **创建全面的端到端测试**：编写一个新的集成测试，该测试将构建一个包含业务代码、包内测试和顶层集成测试的 monorepo 结构。然后，通过移动一个核心模块，验证所有三种类型的引用（跨包业务代码、包内测试、顶层测试）都被正确地更新了。

### 基本原理

实现这一功能的关键在于为 `griffe` 提供一个完整的代码库视图。当前的 `SemanticGraph` 仅将源码目录（`src` 或 `packages/*/src`）作为搜索路径，导致测试文件被完全忽略。

我的计划是扩展 `SemanticGraph` 的路径发现逻辑。它将在初始化时，主动查找并添加所有标准的测试目录到 `griffe` 的搜索路径列表中。一旦 `griffe` 能够“看到”测试代码，它就能解析其中的导入语句和符号引用。这样，我们的 `_UsageVisitor` 就能在扫描时捕获到这些引用，并将它们添加到 `UsageRegistry` 中。

由于后续的 `RenameSymbolOperation` 和 `MoveFileOperation` 都依赖于 `UsageRegistry` 来找到所有需要修改的位置，这个改动将无缝地使整个重构流程“感知”到测试文件，从而实现对它们的自动更新，无需修改操作层本身的代码。新的端到端测试将为这一增强功能的正确性提供最终的、无可辩驳的证明。

### 标签

#intent/build #flow/ready #priority/high #comp/engine #comp/tests #concept/state #scope/core #scope/dx #ai/instruct #task/state/continue

---

### Script

#### Acts 1: 增强 SemanticGraph 以包含测试目录

我将更新 `SemanticGraph` 的构造函数，添加逻辑来扫描并包含顶层 `tests` 目录和 monorepo 包内的 `tests` 目录。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
~~~~~
~~~~~python.old
class SemanticGraph:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        search_paths = []

        # 1. Add top-level src if it exists
        top_level_src = self.root_path / "src"
        if top_level_src.is_dir():
            search_paths.append(top_level_src)

        # 2. Add packages from monorepo structure
        packages_dir = self.root_path / "packages"
        if packages_dir.is_dir():
            for package_path in packages_dir.iterdir():
                if package_path.is_dir():
                    package_src_path = package_path / "src"
                    if package_src_path.is_dir():
                        search_paths.append(package_src_path)

        # 3. Fallback to root if no specific source directories were found
        if not search_paths:
            search_paths.append(self.root_path)

        # Store unique, sorted paths for deterministic behavior
        self.search_paths = sorted(list(set(search_paths)))

        self._griffe_loader = griffe.GriffeLoader(search_paths=self.search_paths)
        self._modules: Dict[str, griffe.Module] = {}
        self.registry = UsageRegistry()
~~~~~
~~~~~python.new
class SemanticGraph:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        search_paths = []

        # 1. Add top-level src and tests directories
        for top_level_dir in ["src", "tests"]:
            path = self.root_path / top_level_dir
            if path.is_dir():
                search_paths.append(path)

        # 2. Add packages from monorepo structure (both src and tests)
        packages_dir = self.root_path / "packages"
        if packages_dir.is_dir():
            for package_path in packages_dir.iterdir():
                if package_path.is_dir():
                    for sub_dir in ["src", "tests"]:
                        package_sub_dir = package_path / sub_dir
                        if package_sub_dir.is_dir():
                            search_paths.append(package_sub_dir)

        # 3. Fallback to root if no specific source directories were found
        if not search_paths:
            search_paths.append(self.root_path)

        # Store unique, sorted paths for deterministic behavior
        self.search_paths = sorted(list(set(search_paths)))

        self._griffe_loader = griffe.GriffeLoader(search_paths=self.search_paths)
        self._modules: Dict[str, griffe.Module] = {}
        self.registry = UsageRegistry()
~~~~~

#### Acts 2: 创建包含测试文件的 Monorepo 端到端测试

现在，我将创建一个新的、更全面的集成测试。这个测试将验证当一个模块被移动时，依赖它的业务代码、包内测试代码和项目顶层测试代码都会被正确地更新。

~~~~~act
write_file
packages/stitcher-refactor/tests/integration/test_monorepo_refactor_with_tests_e2e.py
~~~~~
~~~~~python
import json
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.transaction import TransactionManager, MoveFileOp
from stitcher.refactor.operations.move_file import MoveFileOperation
from stitcher.test_utils import WorkspaceFactory


def test_move_file_in_monorepo_updates_tests_and_cross_package_imports(tmp_path):
    # 1. ARRANGE: Build a comprehensive monorepo workspace with tests
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory
        # --- Package A: The provider ---
        .with_source("packages/pkg_a/src/pkga_lib/__init__.py", "")
        .with_source(
            "packages/pkg_a/src/pkga_lib/core.py", "class SharedClass: pass"
        )
        .with_source(
            "packages/pkg_a/tests/test_core.py",
            "from pkga_lib.core import SharedClass\n\ndef test_shared():\n    assert SharedClass is not None",
        )
        # --- Package B: A consumer ---
        .with_source("packages/pkg_b/src/pkgb_app/__init__.py", "")
        .with_source(
            "packages/pkg_b/src/pkgb_app/main.py",
            "from pkga_lib.core import SharedClass\n\ninstance = SharedClass()",
        )
        # --- Top-level integration tests ---
        .with_source("tests/integration/__init__.py", "")
        .with_source(
            "tests/integration/test_full_system.py",
            "from pkga_lib.core import SharedClass\n\ndef test_integration():\n    s = SharedClass()\n    assert s is not None",
        )
        .build()
    )

    # Define paths for the operation and verification
    src_path = project_root / "packages/pkg_a/src/pkga_lib/core.py"
    dest_path = project_root / "packages/pkg_a/src/pkga_lib/utils.py"
    pkg_a_test_path = project_root / "packages/pkg_a/tests/test_core.py"
    pkg_b_main_path = project_root / "packages/pkg_b/src/pkgb_app/main.py"
    top_level_test_path = project_root / "tests/integration/test_full_system.py"

    # 2. ACT
    graph = SemanticGraph(root_path=project_root)
    # Verify that all source and test roots were discovered
    assert project_root / "packages/pkg_a/src" in graph.search_paths
    assert project_root / "packages/pkg_a/tests" in graph.search_paths
    assert project_root / "packages/pkg_b/src" in graph.search_paths
    assert project_root / "tests" in graph.search_paths

    # Load all relevant modules
    graph.load("pkga_lib")
    graph.load("pkgb_app")
    graph.load("integration")
    # Also load the test module from pkg_a
    graph.load("test_core")

    ctx = RefactorContext(graph=graph)
    op = MoveFileOperation(src_path, dest_path)
    file_ops = op.analyze(ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        else:
            tm.add_write(fop.path, fop.content)
    tm.commit()

    # 3. ASSERT
    assert not src_path.exists()
    assert dest_path.exists()

    expected_import = "from pkga_lib.utils import SharedClass"

    # Verify package-local test file
    updated_pkg_a_test = pkg_a_test_path.read_text()
    assert expected_import in updated_pkg_a_test

    # Verify cross-package source file
    updated_pkg_b_main = pkg_b_main_path.read_text()
    assert expected_import in updated_pkg_b_main

    # Verify top-level integration test file
    updated_top_level_test = top_level_test_path.read_text()
    assert expected_import in updated_top_level_test
~~~~~

### 下一步建议

我们已经成功地将测试文件纳入了重构范围。下一步，我们可以继续增强 `stitcher-refactor` 的可靠性和易用性：

-   **实现 `RenameSymbolOperation` 的 Monorepo 测试**：创建一个与刚才类似的测试用例，但侧重于验证跨包的*符号重命名*，确保所有引用，无论在源码还是测试中，都被正确更新。
-   **引入交互式预览**：在执行重构前，向用户展示一个详细的变更计划（哪些文件将被修改，具体修改内容是什么），并请求确认。这将赋予用户最终的控制权，避免意外的更改。
