Excellent question. You've correctly identified that my previous fix, while effective, introduced technical debt by duplicating logic. The path transformation logic is **not yet centralized**.

I will now generate a plan to perform this crucial refactoring. This is a perfect example of the "Refactor" step in the "Red-Green-Refactor" cycle. The goal is to improve the internal code quality without changing the external behavior, meaning all tests should continue to pass after this change.

## [WIP] refactor(app): Centralize PEP 561 path transformation logic

### 用户需求
在确认 `test_pep561_structure_compliance` 测试通过后，需要对代码进行重构，将分散在 `StubPackageManager` 和 `StitcherApp` 中用于计算 PEP 561 兼容目录名的逻辑集中到一处，以遵循 DRY (Don't Repeat Yourself) 原则。

### 评论
这是一个非常重要的代码健康度改进。将这个核心的路径转换逻辑集中管理，不仅能消除冗余代码，还能确保未来对 PEP 561 相关规则的任何修改都只需要在一个地方进行，极大地提高了代码的可维护性和健壮性，降低了引入不一致性 bug 的风险。

### 目标
1.  在 `StubPackageManager` 类中创建一个新的、可复用的 **静态方法**，该方法封装将逻辑路径（如 `my_project/main.py`）转换为 PEP 561 兼容路径（`my_project-stubs/main.py`）的逻辑。
2.  重构 `StubPackageManager.scaffold` 方法，使其调用这个新的静态方法来确定要创建的目录名和要写入 `pyproject.toml` 的路径。
3.  重构 `StitcherApp._generate_stubs` 方法，使其也调用 `StubPackageManager` 的这个新静态方法来计算 `.pyi` 文件的正确输出路径。

### 基本原理
我们将 `StubPackageManager` 确立为管理存根包结构约定的“唯一事实来源”。通过在其上创建一个静态方法 `_get_pep561_logical_path`，我们为整个应用程序提供了一个单一、权威的函数来执行此路径转换。`StitcherApp` 作为该服务的消费者，将通过其实例化的 `doc_manager` 调用这个方法，从而确保无论是在创建骨架（scaffold）还是在生成文件（generate）时，所遵循的路径逻辑都是完全一致的。

### 标签
#intent/refine #flow/ready #priority/medium #comp/app #scope/core #ai/instruct #task/domain/testing #task/object/refactoring #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 在 StubPackageManager 中集中化逻辑并重构 `scaffold`

我们将首先修改 `stub_package_manager.py`，添加新的静态方法并更新 `scaffold` 方法以使用它。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/stub_package_manager.py
~~~~~
~~~~~python.old
from pathlib import Path
import tomli_w


class StubPackageManager:
    def scaffold(
        self, package_path: Path, source_project_name: str, package_namespace: str
    ) -> bool:
        config_path = package_path / "pyproject.toml"
        if config_path.exists():
            return False

        # Ensure root directory exists
        package_path.mkdir(parents=True, exist_ok=True)
        # PEP 561: The distribution name should end in '-stubs', and the package
        # directory within should also end in '-stubs'.
        stub_src_dirname = f"{package_namespace}-stubs"
        (package_path / "src" / stub_src_dirname).mkdir(parents=True, exist_ok=True)

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
                                "packages": [f"src/{stub_src_dirname}"]
                            }
                        }
                    }
                }
            },
        }
        with config_path.open("wb") as f:
            tomli_w.dump(pyproject_content, f)

        return True
~~~~~
~~~~~python.new
from pathlib import Path
import tomli_w


class StubPackageManager:
    @staticmethod
    def _get_pep561_logical_path(logical_path: Path) -> Path:
        """Converts a standard logical path to a PEP 561-compliant one for stubs."""
        if not logical_path.parts:
            return logical_path

        namespace = logical_path.parts[0]
        rest_of_path = logical_path.parts[1:]
        # e.g. my_app/main.py -> my_app-stubs/main.py
        return Path(f"{namespace}-stubs", *rest_of_path)

    def scaffold(
        self, package_path: Path, source_project_name: str, package_namespace: str
    ) -> bool:
        config_path = package_path / "pyproject.toml"
        if config_path.exists():
            return False

        # Ensure root directory exists
        package_path.mkdir(parents=True, exist_ok=True)

        # Use the centralized logic to determine the stub source directory name
        stub_src_dirname = self._get_pep561_logical_path(
            Path(package_namespace)
        ).as_posix()
        (package_path / "src" / stub_src_dirname).mkdir(parents=True, exist_ok=True)

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
                                "packages": [f"src/{stub_src_dirname}"]
                            }
                        }
                    }
                }
            },
        }
        with config_path.open("wb") as f:
            tomli_w.dump(pyproject_content, f)

        return True
~~~~~

#### Acts 2: 重构 `StitcherApp` 以使用集中化逻辑

现在，我们更新 `StitcherApp`，移除重复的逻辑，并调用新的静态方法。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
            if config.stub_package:
                # Stub Package mode
                logical_path = self._derive_logical_path(module.file_path)

                # PEP 561 adjustment: output to `<namespace>-stubs` dir
                stub_logical_path = logical_path
                if logical_path.parts:
                    namespace = logical_path.parts[0]
                    rest_of_path = logical_path.parts[1:]
                    stub_logical_path = Path(f"{namespace}-stubs", *rest_of_path)

                output_path = (
                    self.root_path
                    / config.stub_package
                    / "src"
                    / stub_logical_path.with_suffix(".pyi")
                )

                # Create py.typed marker file in top-level package dir
                if stub_logical_path.parts:
                    top_level_pkg_dir = (
                        self.root_path
                        / config.stub_package
                        / "src"
                        / stub_logical_path.parts[0]
                    )
~~~~~
~~~~~python.new
            if config.stub_package:
                # Stub Package mode
                logical_path = self._derive_logical_path(module.file_path)

                # Use the centralized logic from StubPackageManager
                stub_logical_path = self.stub_pkg_manager._get_pep561_logical_path(
                    logical_path
                )

                output_path = (
                    self.root_path
                    / config.stub_package
                    / "src"
                    / stub_logical_path.with_suffix(".pyi")
                )

                # Create py.typed marker file in top-level package dir
                if stub_logical_path.parts:
                    top_level_pkg_dir = (
                        self.root_path
                        / config.stub_package
                        / "src"
                        / stub_logical_path.parts[0]
                    )
~~~~~

### 下一步建议

我们已经成功地将路径转换逻辑集中到了 `StubPackageManager` 中。由于这只是一个内部重构，它不应该改变任何外部行为。

请您再次运行 `pytest`。所有测试，特别是 `test_pep561_structure_compliance`，应该依然会**通过**。

在您确认测试通过后，我们将正式开始编写下一个全新的测试：**安装与类型解析测试**。
