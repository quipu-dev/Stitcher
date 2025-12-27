好的，我们继续。

现在我们有了 `VenvHarness` 这个强大的工具，是时候开始编写第一个、也是最关键的集成测试了：**结构合规性测试 (Structure Compliance Test)**。

这个测试的目标是验证我们生成的存根包（stub package）是否严格遵守 PEP 561 的命名规范。在实现过程中，我发现现有的 `StubPackageManager` 逻辑与 PEP 561 的目录命名要求存在偏差。因此，本计划将首先修正这个逻辑，然后立刻编写测试来锁定正确的行为，防止未来再次出现回归。

## [WIP] test: 实现 PEP 561 结构合规性测试并修复生成逻辑

### 用户需求
使用新创建的测试基础设施，编写“结构合规性测试”。该测试需要验证 `stitcher` 生成的存根包在 `pyproject.toml` 的包名和物理源码目录结构上，都严格遵循 PEP 561 规范（即使用 `-stubs` 后缀）。

### 评论
这是“吃自己的狗粮”（dogfooding）的完美范例。我们利用自己的测试工具来验证我们核心功能的正确性。修复 `StubPackageManager` 中的这个偏差至关重要，因为错误的目录结构会导致所有下游的类型检查器（Mypy, Pyright）完全无法识别我们生成的存根，使得整个工具链失效。

### 目标
1.  **修复 `StubPackageManager`**: 修改 `scaffold` 方法，使其生成的源码目录和 `pyproject.toml` 中的 `packages` 路径都遵循 `<namespace>-stubs` 的命名约定。
2.  **创建测试文件**: 在 `tests/integration/` 目录下创建新的测试文件 `test_stub_package_pep561.py`。
3.  **实现合规性测试**: 在新文件中，编写一个测试用例，该用例：
    *   使用 `WorkspaceFactory` 构建一个最小化的项目配置。
    *   运行 `StitcherApp` 来生成存根包。
    *   断言生成的 `pyproject.toml` 中的包名是 `my-project-stubs`。
    *   **关键断言**: 断言生成的源码目录是 `src/my_project-stubs`，而不是 `src/my-project`。

### 基本原理
我们将遵循“测试驱动开发”（TDD）的原则。首先，我们识别出当前生成逻辑中的一个关键缺陷：它没有为存根包内的源码目录添加 `-stubs` 后缀，这违反了 PEP 561 的规定，会导致类型检查器无法将存根与原始包关联起来。

因此，第一步是原子化地修复 `stub_package_manager.py` 中的这个逻辑。

第二步，我们立即编写一个端到端的集成测试。这个测试不关心 `StubPackageManager` 的内部实现，它只关心最终的产物——文件系统上的目录和文件——是否符合预期。这确保了我们的修复是有效的，并建立了一个安全网，防止未来的代码变更无意中破坏这一核心规范。

### 标签
#intent/build #flow/ready #priority/high #comp/tests #comp/application #scope/core #ai/instruct #task/domain/testing #task/object/pep561-test #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 修复 StubPackageManager 的目录生成逻辑

我们首先修正 `StubPackageManager`，使其为源码目录和 `tool.hatch.build.targets.wheel.packages` 配置都添加 `-stubs` 后缀。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/stub_package_manager.py
~~~~~
~~~~~python.old
        # Create src/namespace directory, e.g., src/needle or src/stitcher
        (package_path / "src" / package_namespace).mkdir(parents=True, exist_ok=True)

        # Create pyproject.toml
        pyproject_content = {
            "build-system": {
                "requires": ["hatchling"],
                "build-backend": "hatchling.build",
            },
            "project": {
                "name": f"{source_project_name}-stubs",
                "version": "0.1.0",  # Placeholder version
                "description": f"PEP 561 type stubs for {source_project_name}",
            },
            "tool": {
                "hatch": {
                    "build": {
                        "targets": {
                            "wheel": {
                                # Essential for packaging .pyi files correctly under the namespace
                                "packages": [f"src/{package_namespace}"]
                            }
                        }
                    }
                }
            },
        }
~~~~~
~~~~~python.new
        stub_namespace = f"{package_namespace}-stubs"
        # Create src/namespace-stubs directory, e.g., src/needle-stubs
        (package_path / "src" / stub_namespace).mkdir(parents=True, exist_ok=True)

        # Create pyproject.toml
        pyproject_content = {
            "build-system": {
                "requires": ["hatchling"],
                "build-backend": "hatchling.build",
            },
            "project": {
                "name": f"{source_project_name}-stubs",
                "version": "0.1.0",  # Placeholder version
                "description": f"PEP 561 type stubs for {source_project_name}",
            },
            "tool": {
                "hatch": {
                    "build": {
                        "targets": {
                            "wheel": {
                                # Essential for packaging .pyi files correctly under the namespace
                                "packages": [f"src/{stub_namespace}"]
                            }
                        }
                    }
                }
            },
        }
~~~~~

#### Acts 2: 编写 PEP 561 结构合规性测试

现在，我们创建测试文件来验证修复后的逻辑是否正确。

~~~~~act
write_file
tests/integration/test_stub_package_pep561.py
~~~~~
~~~~~python
import sys
from pathlib import Path

if sys.version_info < (3, 11):
    import tomli as tomllib
else:
    import tomllib

from stitcher.app import StitcherApp
from stitcher.test_utils import WorkspaceFactory


def test_pep561_structure_compliance(tmp_path: Path):
    """
    Verifies that generated stub packages comply with PEP 561 naming conventions
    for both package name and the source directory inside the package.
    """
    # 1. Arrange
    project_name = "my-project"
    namespace = "my_project"
    stub_dir_name = "stubs"

    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_project_name(project_name)
        .with_config({"scan_paths": [f"src/{namespace}"], "stub_package": stub_dir_name})
        .with_source(f"src/{namespace}/main.py", "def func(): ...")
        .build()
    )

    app = StitcherApp(root_path=project_root)

    # 2. Act
    app.run_from_config()

    # 3. Assert
    stub_pkg_path = project_root / stub_dir_name
    stub_toml_path = stub_pkg_path / "pyproject.toml"

    # 3.1. Assert pyproject.toml name is correct
    assert stub_toml_path.is_file()
    with stub_toml_path.open("rb") as f:
        config = tomllib.load(f)
    assert config["project"]["name"] == f"{project_name}-stubs"

    # 3.2. Assert src directory is named correctly (<namespace>-stubs)
    expected_src_dir = stub_pkg_path / "src" / f"{namespace}-stubs"
    incorrect_src_dir = stub_pkg_path / "src" / namespace

    assert expected_src_dir.is_dir()
    assert not incorrect_src_dir.exists(), "Incorrectly named src dir found."

    # 3.3. Assert Hatch config points to the correct directory
    hatch_packages = config["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    assert hatch_packages == [f"src/{namespace}-stubs"]
~~~~~

### 下一步建议

我们已经验证了生成的存根包在物理结构上是合规的。

下一步是验证它在功能上是否有效。我建议实施 **“安装与类型解析测试” (The "Can I Import It" Test)**。这个测试将是我们第一次真正使用 `isolated_env` fixture 的全部功能：
1.  生成存根包。
2.  在隔离的虚拟环境中 `pip install` 这个存根包。
3.  创建一个消费该包的客户端脚本 (`client.py`)。
4.  在虚拟环境中运行 `mypy`，并断言类型检查器能够正确解析导入的类型，而不是返回 `Any` 或 `ImportError`。

这将闭合整个验证循环，证明我们生成的包不仅结构正确，而且能被工具链正确消费。如果你同意，我将生成执行此测试的计划。
