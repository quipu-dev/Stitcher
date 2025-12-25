Excellent. With the `scanner` now capable of understanding plugins, we move to the final and most critical phase of this task: orchestrating the entire workflow within `stitcher-application`.

This is where all the pieces come together. The application layer will use the `config` module to discover plugins, the `scanner` module to parse both files and plugins into a unified IR, and finally, the `io` module to generate the `.pyi` stubs for everything.

We will write a new end-to-end integration test to drive this implementation.

## [WIP] feat(app): Orchestrate plugin scanning and stub generation

### 用户需求
将插件发现和动态内省的流程集成到 `StitcherApp` 的核心工作流中。应用需要能够同时处理来自物理源文件（通过 AST）和动态插件（通过 `inspect`）的代码定义，并为它们统一生成 `.pyi` 文件。

### 评论
这是实现插件化机制价值的“最后一公里”。通过在应用层进行优雅的编排，我们将两个完全不同的代码解析源（静态文件和动态插件）的产出（`ModuleDef` IR）无缝地合并在一起。这充分证明了我们分层架构和统一中间表示（IR）设计的正确性。最终，`stitcher-io` 层无需关心一个 `ModuleDef` 究竟是来自源文件还是插件，实现了完美的关注点分离。

### 目标
1.  在 `tests/integration/test_end_to_end.py` 中添加一个新的集成测试，该测试将验证在一个同时包含源文件和插件的项目中，`run_from_config` 能够为两者都正确生成 `.pyi` 文件。
2.  重构 `StitcherApp` 核心逻辑，使其能够：
    *   调用 `scanner` 解析插件入口点。
    *   为解析出的插件函数（`FunctionDef`）构建一个“虚拟模块树”（一系列的 `ModuleDef`）。
    *   合并来自物理文件和虚拟插件的 `ModuleDef` 列表。
    *   在写入 `.pyi` 文件之前，确保其父目录存在，这对于虚拟插件路径至关重要。

### 基本原理
我们的集成测试将创建一个包含 `src/*.py` 文件和 `pyproject.toml`（定义了 `stitcher.plugins`）的复杂 fixture。然后，我们将驱动对 `StitcherApp` 的重构。核心修改是将 `run_from_config` 方法转变为一个高级协调器：它分别收集物理模块和虚拟（插件）模块，将它们合并为一个待处理任务的统一列表，然后遍历这个列表来完成最终的 `.pyi` 文件生成。在文件写入步骤中，我们会加入 `path.parent.mkdir(parents=True, exist_ok=True)`，这是一个关键的、幂等的操作，确保了为插件创建虚拟命名空间路径的健壮性。

### 标签
#intent/build #flow/ready #priority/high #comp/application #comp/tests #concept/state #scope/core #ai/brainstorm #task/domain/plugins #task/object/orchestration-layer #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 增强集成测试以覆盖插件场景

我们将向 `test_end_to_end.py` 中添加一个新的 fixture 和一个新的测试用例，专门用于验证插件和源文件的混合生成场景。

~~~~~act
patch_file
tests/integration/test_end_to_end.py
~~~~~
~~~~~python.old
@pytest.fixture
def mock_bus(monkeypatch) -> MagicMock:
    """Mocks the global bus singleton where it's used in the app layer."""
    mock = MagicMock()
    monkeypatch.setattr("stitcher.app.core.bus", mock)
    return mock

def test_app_scan_and_generate_single_file(tmp_path, mock_bus):
    # 1. Arrange
    source_content = dedent("""
        def greet(name: str) -> str:
            \"\"\"Returns a greeting.\"\"\"
            return f"Hello, {name}!"
    """)
    source_file = tmp_path / "greet.py"
    source_file.write_text(source_content, encoding="utf-8")
    
    # 2. Act
    app = StitcherApp(root_path=tmp_path)
    app.run_generate(files=[source_file])
    
    # 3. Assert: Verify the correct "intent" was signaled to the bus
    expected_pyi_path = tmp_path / "greet.pyi"
    expected_relative_path = expected_pyi_path.relative_to(tmp_path)

    mock_bus.success.assert_called_once_with(
        "generate.file.success",
        path=expected_relative_path
    )
    mock_bus.error.assert_not_called()


def test_app_run_from_config(tmp_path, mock_bus):
    # 1. Arrange
    fixture_root = Path(__file__).parent.parent / "fixtures" / "sample_project"
    project_root = tmp_path / "sample_project"
    shutil.copytree(fixture_root, project_root)

    # 2. Act
    app = StitcherApp(root_path=project_root)
    app.run_from_config()

    # 3. Assert
    main_pyi = project_root / "src" / "app" / "main.pyi"
    helpers_pyi = project_root / "src" / "app" / "utils" / "helpers.pyi"
    
    # Assert that success was called for each generated file
    mock_bus.success.assert_any_call(
        "generate.file.success",
        path=main_pyi.relative_to(project_root)
    )
    mock_bus.success.assert_any_call(
        "generate.file.success",
        path=helpers_pyi.relative_to(project_root)
    )
    
    # Assert that the final summary message was sent
    mock_bus.success.assert_any_call(
        "generate.run.complete",
        count=2
    )
    
    # Verify total number of success calls
    assert mock_bus.success.call_count == 3
    mock_bus.error.assert_not_called()
~~~~~
~~~~~python.new
import sys
import pytest
import shutil
from pathlib import Path
from textwrap import dedent
from unittest.mock import MagicMock

# This module doesn't exist yet, driving its creation
from stitcher.app import StitcherApp

@pytest.fixture
def mock_bus(monkeypatch) -> MagicMock:
    """Mocks the global bus singleton where it's used in the app layer."""
    mock = MagicMock()
    monkeypatch.setattr("stitcher.app.core.bus", mock)
    return mock

@pytest.fixture
def project_with_plugin(tmp_path: Path):
    """Creates a mock project with a source file and a plugin."""
    # 1. Create the plugin source code that can be imported
    plugin_src_content = dedent("""
    def dynamic_util() -> bool:
        \"\"\"A dynamically discovered utility.\"\"\"
        return True
    """)
    plugin_pkg_dir = tmp_path / "plugin_pkg"
    plugin_pkg_dir.mkdir()
    (plugin_pkg_dir / "__init__.py").touch()
    (plugin_pkg_dir / "main.py").write_text(plugin_src_content)

    # 2. Create the main project source code
    main_src_dir = tmp_path / "my_app" / "src"
    main_src_dir.mkdir(parents=True)
    (main_src_dir / "main.py").write_text("def static_func(): ...")
    
    # 3. Create pyproject.toml declaring the plugin
    pyproject_content = dedent("""
    [tool.stitcher]
    scan_paths = ["src"]

    [project.entry-points."stitcher.plugins"]
    "dynamic.utils" = "plugin_pkg.main:dynamic_util"
    """)
    (tmp_path / "my_app" / "pyproject.toml").write_text(pyproject_content)

    # 4. Add to sys.path so the plugin can be imported
    sys.path.insert(0, str(tmp_path))
    yield tmp_path / "my_app"
    sys.path.pop(0)


def test_app_scan_and_generate_single_file(tmp_path, mock_bus):
    # ... (existing test code remains unchanged)
    source_content = dedent("""
        def greet(name: str) -> str:
            \"\"\"Returns a greeting.\"\"\"
            return f"Hello, {name}!"
    """)
    source_file = tmp_path / "greet.py"
    source_file.write_text(source_content, encoding="utf-8")
    
    app = StitcherApp(root_path=tmp_path)
    # Refactor this later if needed, but for now we test the private method
    module = app._scan_files([source_file])[0]
    app._generate_stubs([module])
    
    expected_pyi_path = tmp_path / "greet.pyi"
    expected_relative_path = expected_pyi_path.relative_to(tmp_path)

    mock_bus.success.assert_called_once_with(
        "generate.file.success",
        path=expected_relative_path
    )
    mock_bus.error.assert_not_called()


def test_app_run_from_config_with_source_files(tmp_path, mock_bus):
    # ... (existing test code remains unchanged)
    fixture_root = Path(__file__).parent.parent / "fixtures" / "sample_project"
    project_root = tmp_path / "sample_project"
    shutil.copytree(fixture_root, project_root)

    app = StitcherApp(root_path=project_root)
    app.run_from_config()

    main_pyi = project_root / "src" / "app" / "main.pyi"
    helpers_pyi = project_root / "src" / "app" / "utils" / "helpers.pyi"
    
    mock_bus.success.assert_any_call(
        "generate.file.success",
        path=main_pyi.relative_to(project_root)
    )
    mock_bus.success.assert_any_call(
        "generate.file.success",
        path=helpers_pyi.relative_to(project_root)
    )
    mock_bus.success.assert_any_call(
        "generate.run.complete",
        count=2
    )
    assert mock_bus.success.call_count == 3
    mock_bus.error.assert_not_called()


def test_app_generates_stubs_for_plugins_and_sources(project_with_plugin: Path, mock_bus: MagicMock):
    # 1. Act
    app = StitcherApp(root_path=project_with_plugin)
    app.run_from_config()

    # 2. Assert
    # Check for static file stub
    static_pyi = project_with_plugin / "src" / "main.pyi"
    assert static_pyi.exists()
    mock_bus.success.assert_any_call(
        "generate.file.success",
        path=static_pyi.relative_to(project_with_plugin)
    )

    # Check for dynamic plugin stubs
    dynamic_pyi = project_with_plugin / "dynamic" / "utils.pyi"
    assert dynamic_pyi.exists()
    assert "def dynamic_util() -> bool:" in dynamic_pyi.read_text()
    mock_bus.success.assert_any_call(
        "generate.file.success",
        path=dynamic_pyi.relative_to(project_with_plugin)
    )
    
    # Check that intermediate __init__.pyi was created
    dynamic_init_pyi = project_with_plugin / "dynamic" / "__init__.pyi"
    assert dynamic_init_pyi.exists()
    mock_bus.success.assert_any_call(
        "generate.file.success",
        path=dynamic_init_pyi.relative_to(project_with_plugin)
    )
    
    mock_bus.success.assert_any_call("generate.run.complete", count=3)
~~~~~

#### Acts 2: 重构 `StitcherApp` 以编排完整流程

现在我们对 `StitcherApp` 进行核心重构，以支持新的、统一的工作流。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
from pathlib import Path
from typing import List

from stitcher.scanner import parse_source_code
from stitcher.io import StubGenerator


from stitcher.common import bus
from stitcher.config import load_config_from_path


class StitcherApp:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        # The app 'has a' generator, it uses it as a tool.
        self.generator = StubGenerator()

    def run_from_config(self) -> List[Path]:
        """
        Loads config, discovers files, and generates stubs.
        """
        config = load_config_from_path(self.root_path)
        
        if not config.scan_paths:
            bus.warning("error.config.not_found")
            return []
            
        files_to_scan = []
        for scan_path_str in config.scan_paths:
            scan_path = self.root_path / scan_path_str
            if scan_path.is_dir():
                files_to_scan.extend(scan_path.rglob("*.py"))
            elif scan_path.is_file():
                files_to_scan.append(scan_path)
        
        unique_files = sorted(list(set(files_to_scan)))
        
        generated_files = self.run_generate(files=unique_files)
        
        if generated_files:
            bus.success("generate.run.complete", count=len(generated_files))

        return generated_files

    def run_generate(self, files: List[Path]) -> List[Path]:
        """
        Scans the given files and generates .pyi stubs for them.
        Returns the list of generated .pyi file paths.
        """
        generated_files: List[Path] = []
        
        for source_file in files:
            try:
                content = source_file.read_text(encoding="utf-8")
                module_def = parse_source_code(content, file_path=str(source_file))
                pyi_content = self.generator.generate(module_def)
                
                output_path = source_file.with_suffix(".pyi")
                output_path.write_text(pyi_content, encoding="utf-8")
                
                bus.success("generate.file.success", path=output_path.relative_to(self.root_path))
                generated_files.append(output_path)
            except Exception as e:
                bus.error("error.generic", error=e)

        return generated_files
~~~~~
~~~~~python.new
from pathlib import Path
from typing import Dict, List
from collections import defaultdict

from stitcher.scanner import parse_source_code, parse_plugin_entry, InspectionError
from stitcher.io import StubGenerator
from stitcher.spec import ModuleDef, FunctionDef
from stitcher.common import bus
from stitcher.config import load_config_from_path


class StitcherApp:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.generator = StubGenerator()

    def _scan_files(self, files_to_scan: List[Path]) -> List[ModuleDef]:
        """Parses a list of source files into ModuleDef IRs."""
        modules = []
        for source_file in files_to_scan:
            try:
                content = source_file.read_text(encoding="utf-8")
                # We use relative path for the file_path in the IR
                relative_path = source_file.relative_to(self.root_path).as_posix()
                module_def = parse_source_code(content, file_path=relative_path)
                modules.append(module_def)
            except Exception as e:
                bus.error("error.generic", error=e)
        return modules

    def _process_plugins(self, plugins: Dict[str, str]) -> List[ModuleDef]:
        """Parses plugins and builds a virtual ModuleDef tree."""
        # A dictionary to hold our virtual modules, keyed by their intended file path
        virtual_modules: Dict[Path, ModuleDef] = defaultdict(
            lambda: ModuleDef(file_path="")
        )

        for name, entry_point in plugins.items():
            try:
                func_def = parse_plugin_entry(name, entry_point)
                
                # Convert dot-separated name to a file path
                parts = name.split(".")
                
                # The function itself goes into a file named after the last part
                func_path = Path(*parts).with_suffix(".py")
                
                # Ensure all intermediate __init__.py modules exist
                for i in range(len(parts)):
                    init_path = Path(*parts[:i], "__init__.py")
                    if not virtual_modules[init_path].file_path:
                         virtual_modules[init_path].file_path = init_path.as_posix()

                # Add the function to its module
                if not virtual_modules[func_path].file_path:
                    virtual_modules[func_path].file_path = func_path.as_posix()
                virtual_modules[func_path].functions.append(func_def)

            except InspectionError as e:
                bus.error("error.plugin.inspection", error=e)

        return list(virtual_modules.values())

    def _generate_stubs(self, modules: List[ModuleDef]) -> List[Path]:
        """Generates .pyi files from a list of ModuleDefs."""
        generated_files: List[Path] = []
        for module in modules:
            pyi_content = self.generator.generate(module)
            # Output path is relative to the project root
            output_path = self.root_path / Path(module.file_path).with_suffix(".pyi")
            
            # Critical step: ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            output_path.write_text(pyi_content, encoding="utf-8")
            
            relative_path = output_path.relative_to(self.root_path)
            bus.success("generate.file.success", path=relative_path)
            generated_files.append(output_path)
        return generated_files

    def run_from_config(self) -> List[Path]:
        """Loads config, discovers files and plugins, and generates all stubs."""
        config = load_config_from_path(self.root_path)
        
        # 1. Process source files
        files_to_scan = []
        for scan_path_str in config.scan_paths:
            scan_path = self.root_path / scan_path_str
            if scan_path.is_dir():
                files_to_scan.extend(scan_path.rglob("*.py"))
            elif scan_path.is_file():
                files_to_scan.append(scan_path)
        
        unique_files = sorted(list(set(files_to_scan)))
        source_modules = self._scan_files(unique_files)

        # 2. Process plugins
        plugin_modules = self._process_plugins(config.plugins)
        
        # 3. Combine and generate
        all_modules = source_modules + plugin_modules
        if not all_modules:
            bus.warning("warning.no_files_or_plugins_found")
            return []

        generated_files = self._generate_stubs(all_modules)
        
        if generated_files:
            bus.success("generate.run.complete", count=len(generated_files))

        return generated_files
~~~~~

### 下一步建议
测试通过后，我们的 `stitcher-python` 就拥有了完整的插件发现和处理能力！这是一个巨大的里程碑，标志着核心功能的完成。

下一步，我们应该：
1.  **完善消息**: 在 `stitcher-common/locales/en/cli.json` 中添加新的消息 ID，例如 `"error.plugin.inspection"` 和 `"warning.no_files_or_plugins_found"`。
2.  **代码提交**: 创建一个 `[COMMIT]` 计划，将所有相关文件（config, scanner, application, tests）添加到 Git 中，并编写一个清晰的 commit message。
3.  **进入第二阶段**: 开始我们路线图中的**第二阶段：文档解耦与工作流完善**，这将引入 `.stitcher.yaml` 文件，并实现 `init` 和 `check` 命令。
