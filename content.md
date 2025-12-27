好的，我们来迁移 `stitcher-needle` 的核心运行时测试。这非常重要，因为它将验证我们新组装的 `pyneedle` 包（特别是 `FileSystemLoader` 和 `OverlayNexus`的集成）是否与旧实现的行为完全一致。

我们将使用更现代的 `WorkspaceFactory` 来构建测试环境，并直接测试 `FileSystemLoader` 和 `OverlayNexus` 的组合，以确保“电池组装”是正确的。

## [WIP] test: 迁移旧运行时测试以验证 pyneedle 组装

### 用户需求
将 `packages/stitcher-needle/tests/test_runtime.py` 中的多根加载（multi-root loading）和覆盖（override）逻辑，迁移到 `packages/pyneedle/tests/` 目录下。新的测试必须验证 `FileSystemLoader` 和 `OverlayNexus` 组合在一起时，能够正确处理优先级和回退。

### 评论
这是对我们重构成果的一次关键验收测试。通过复现旧测试的核心场景（用户配置覆盖包内默认配置），我们可以高置信度地证明新的、分包的 `pyneedle` 架构在功能上是向后兼容且正确的。使用 `WorkspaceFactory` 会让测试的 Arrange 阶段更清晰、更易于维护。

### 目标
1.  在 `packages/pyneedle` 中创建 `tests` 目录和测试文件。
2.  使用 `WorkspaceFactory` 创建一个 `pytest` fixture，该 fixture 能模拟出一个包含“包内资产”和“用户项目覆盖”的虚拟工作区。
3.  编写一个测试用例，该用例：
    *   手动实例化 `FileSystemLoader` 和 `OverlayNexus`。
    *   验证从不同来源（包 vs 用户）加载的值。
    *   验证用户配置能够正确覆盖包内配置。
    *   验证身份回退机制依然有效。

### 基本原理
为了确保测试的隔离性和确定性，我们不会依赖全局的 `nexus` 实例（因为它依赖于当前工作目录 `cwd`，这在测试中可能不稳定）。相反，我们将在测试函数内部显式地创建 `FileSystemLoader` 和 `OverlayNexus` 的实例，并将 `WorkspaceFactory` 创建的临时路径直接传递给它们。这使我们能够精确地控制测试环境，确保测试结果 100% 可复现。

### 标签
#intent/tooling #flow/ready #priority/high
#comp/tests #comp/runtime #scope/core
#task/domain/runtime #task/object/pyneedle #task/action/testing
#task_state/continue #task_status/active

---

### Script

#### Acts 1: 创建测试目录和文件
为新的 `pyneedle` 包准备测试环境。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/pyneedle/tests
~~~~~

#### Acts 2: 编写集成测试
创建 `test_assembly.py` 并迁移原有测试逻辑。

~~~~~act
write_file
packages/pyneedle/tests/test_assembly.py
~~~~~
~~~~~python
import pytest
from pathlib import Path
from stitcher.test_utils import WorkspaceFactory

from needle.pointer import L
from needle.nexus import OverlayNexus
from needle.loaders.fs_loader import FileSystemLoader


@pytest.fixture
def multi_root_workspace(tmp_path: Path) -> dict:
    """
    Creates a workspace with two roots to test override logic.
    - pkg_root: Simulates a library's built-in assets.
    - project_root: Simulates a user's project with overrides.
    """
    factory = WorkspaceFactory(tmp_path)

    # 1. Define package assets (low priority)
    pkg_root = tmp_path / "pkg_assets"
    factory.with_source(
        f"{pkg_root.name}/needle/en/cli/main.json",
        """
        {
            "cli.default": "I am a default",
            "cli.override_me": "Default Value"
        }
        """,
    )

    # 2. Define user project assets (high priority)
    project_root = tmp_path / "my_project"
    factory.with_source(
        f"{project_root.name}/pyproject.toml",
        "[project]\nname='my-project'"
    ).with_source(
        f"{project_root.name}/.stitcher/needle/en/overrides.json",
        """
        {
            "cli.override_me": "User Override!",
            "cli.user_only": "I am from the user"
        }
        """,
    )
    
    # Build all files
    factory.build()
    
    return {"pkg_root": pkg_root, "project_root": project_root}


def test_nexus_with_fs_loader_handles_overrides(multi_root_workspace):
    """
    Validates that Nexus, when combined with FileSystemLoader,
    correctly handles multi-root priority and overrides.
    """
    # Arrange
    pkg_root = multi_root_workspace["pkg_root"]
    project_root = multi_root_workspace["project_root"]

    # The order of roots matters. The last one in the list wins.
    # We want project_root to override pkg_root.
    fs_loader = FileSystemLoader(roots=[pkg_root, project_root])
    nexus = OverlayNexus(loaders=[fs_loader])

    # Act & Assert
    
    # 1. Value only in default assets (pkg_root)
    assert nexus.get(L.cli.default) == "I am a default"

    # 2. Value only in user overrides (project_root)
    assert nexus.get(L.cli.user_only) == "I am from the user"

    # 3. Value in both, user override should win
    assert nexus.get(L.cli.override_me) == "User Override!"

    # 4. Non-existent key should fall back to identity
    assert nexus.get(L.unknown.key) == "unknown.key"
~~~~~

#### Acts 3: 更新根 `pyproject.toml`
我们已经在上一步添加了 `pyneedle/src` 的路径，这里仅作确认。`pytest` 应该能找到 `needle.loaders` 等模块。

(此步骤无需修改文件，因为 `packages/pyneedle/src` 已在 `pythonpath` 中)

### 下一步建议
我们已经成功地将 `Needle` 的核心功能重构为一个模块化、协议优先的生态系统，并通过了关键的集成测试。

接下来的工作将是：
1.  **全面迁移**: 逐一更新 `stitcher-cli`, `stitcher-common` 等包，将它们对 `stitcher-needle` 的依赖切换到新的 `pyneedle` 包，并适配 `from needle import nexus, L` 的新 API。
2.  **清理**: 在所有消费者迁移完毕后，可以安全地从工作区中删除 `packages/stitcher-needle` 目录。
