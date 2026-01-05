好的，我们现在开始执行路线图的**任务 1.2**。

这个计划将创建 `SidecarManager` 类，它将作为所有 Sidecar 文件路径解析的唯一事实来源，并为其配备单元测试以确保其正确性。

## [WIP] feat: 实现 SidecarManager 以解耦路径逻辑

### 用户需求

根据重构路线图，实施第一阶段的任务 1.2：
1.  在 `stitcher.refactor.sidecar` 模块中创建一个新的 `SidecarManager` 类。
2.  该类需要封装所有关于 `.stitcher.yaml` 和 `.stitcher/signatures/*.json` 文件位置和命名规则的知识。
3.  为 `SidecarManager` 编写单元测试，验证其路径解析逻辑的准确性。

### 评论

这是向“不要重复自己”（DRY）原则迈出的关键一步。通过将所有 Sidecar 文件的定位逻辑集中到一个服务类中，我们极大地简化了各个重构操作（`*Operation`）类的实现。它们不再需要关心文件系统的具体布局。这使得整个重构引擎的架构更加清晰、更易于维护。未来任何对 Sidecar 存储策略的调整，都只需要修改 `SidecarManager` 这一个地方。

### 目标

1.  **创建 `SidecarManager` 类**: 在 `packages/stitcher-refactor/src/stitcher/refactor/sidecar/manager.py` 文件中实现 `SidecarManager`。它将包含 `__init__`、`get_doc_path` 和 `get_signature_path` 三个核心方法。
2.  **编写单元测试**: 在 `packages/stitcher-refactor/tests/unit/sidecar/test_manager.py` 文件中为 `SidecarManager` 编写测试用例，确保对于给定的源文件路径，它能准确返回对应的文档和签名文件的绝对路径。

### 基本原理

`SidecarManager` 的实现将直接遵循我们在重构方案中定义的设计。它在初始化时接收项目根目录的路径。
*   `get_doc_path` 方法将简单地使用 `.with_suffix(".stitcher.yaml")` 来定位文档文件。
*   `get_signature_path` 方法将封装更复杂的逻辑：首先计算源文件相对于项目根目录的路径，然后将其与 `.stitcher/signatures` 基础路径结合，最后附加 `.json` 后缀。

测试将使用 `pytest` 的 `tmp_path` 来创建一个虚拟的项目根目录，然后在其中定义一个源文件。我们将断言 `SidecarManager` 实例返回的路径与我们手动计算出的预期路径完全一致。

### 标签

#intent/build #flow/ready #priority/high #comp/refactor #concept/state #scope/core #ai/instruct #task/domain/refactor-engine #task/object/sidecar-manager #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 实现 `SidecarManager` 类

我们首先创建 `SidecarManager` 的实现文件，它将包含所有 Sidecar 路径的解析逻辑。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/sidecar/manager.py
~~~~~
~~~~~python
from pathlib import Path


class SidecarManager:
    def __init__(self, root_path: Path):
        self.root_path = root_path.resolve()
        self.sig_root = self.root_path / ".stitcher" / "signatures"

    def get_doc_path(self, source_file_path: Path) -> Path:
        """Returns the absolute path to the doc sidecar for a source file."""
        return source_file_path.resolve().with_suffix(".stitcher.yaml")

    def get_signature_path(self, source_file_path: Path) -> Path:
        """Returns the absolute path to the signature sidecar for a source file."""
        resolved_source = source_file_path.resolve()
        # This encapsulates the complex relative path logic
        try:
            relative_source_path = resolved_source.relative_to(self.root_path)
            return self.sig_root / relative_source_path.with_suffix(".json")
        except ValueError:
            # This can happen if source_file_path is not within root_path.
            # While unlikely in normal operation, it's safer to handle.
            # We'll re-raise a more informative error.
            raise ValueError(
                f"Source file {resolved_source} is not within the project root {self.root_path}"
            )
~~~~~

#### Acts 2: 为 `SidecarManager` 添加单元测试

现在，我们为 `SidecarManager` 创建单元测试，以验证其路径计算的准确性。

~~~~~act
write_file
packages/stitcher-refactor/tests/unit/sidecar/test_manager.py
~~~~~
~~~~~python
from pathlib import Path
import pytest
from stitcher.refactor.sidecar.manager import SidecarManager


@pytest.fixture
def project_structure(tmp_path: Path):
    """Creates a dummy project structure."""
    root = tmp_path
    src_file = root / "src" / "mypkg" / "module.py"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.touch()
    return root, src_file


def test_sidecar_manager_get_doc_path(project_structure):
    # ARRANGE
    root, src_file = project_structure
    manager = SidecarManager(root)
    expected_doc_path = root / "src" / "mypkg" / "module.stitcher.yaml"

    # ACT
    actual_doc_path = manager.get_doc_path(src_file)

    # ASSERT
    assert actual_doc_path == expected_doc_path


def test_sidecar_manager_get_signature_path(project_structure):
    # ARRANGE
    root, src_file = project_structure
    manager = SidecarManager(root)
    expected_sig_path = (
        root / ".stitcher" / "signatures" / "src" / "mypkg" / "module.json"
    )

    # ACT
    actual_sig_path = manager.get_signature_path(src_file)

    # ASSERT
    assert actual_sig_path == expected_sig_path


def test_sidecar_manager_handles_files_outside_root_gracefully(tmp_path):
    # ARRANGE
    project_root = tmp_path / "project"
    project_root.mkdir()
    outside_file = tmp_path / "outside.py"
    outside_file.touch()

    manager = SidecarManager(project_root)

    # ACT & ASSERT
    with pytest.raises(ValueError, match="is not within the project root"):
        manager.get_signature_path(outside_file)
~~~~~

### 下一步建议

我们已经成功完成了**任务 1.2**，并为重构引擎奠定了坚实的基础。`Workspace` 和 `SidecarManager` 这两个核心抽象现在已经准备就绪。

下一步，我们将进入路线图的**阶段二：集成与重构**。我们将首先从 **任务 2.1** 开始，演进 `RefactorContext`，使其成为持有这些新服务的中央枢纽。如果您同意，我将开始准备该计划。
