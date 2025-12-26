## [WIP] feat: 实现 `stitcher init` 命令

### 用户需求
实现 **任务 2.2: `stitcher init` 命令**。该命令用于将项目源代码中的文档字符串（docstrings）提取并迁移到外部的 YAML 文件中，从而完成文档解耦的初始化工作。

### 评论
这是用户接触文档解耦特性的第一步。体验必须流畅且直观。通过复用现有的扫描逻辑和服务层的 `DocumentManager`，我们可以快速组装出这个功能。同时，我们需要在 Needle 中添加相应的反馈消息，确保用户知道哪些文件被创建了。

### 目标
1.  在 `stitcher-needle` 中定义 `init` 命令相关的用户反馈消息。
2.  在 `StitcherApp` 中集成 `DocumentManager` 并实现 `run_init` 核心逻辑。
3.  在 `stitcher-cli` 中挂载 `init` 命令。
4.  通过集成测试验证全流程：从 `.py` 源码 -> 运行 init -> 生成 `.stitcher.yaml`。

### 基本原理
`init` 命令的工作流如下：
1.  读取配置，确定扫描路径（`scan_paths`）。
2.  复用 `_scan_files` 逻辑，将所有 `.py` 文件解析为 `ModuleDef`。
3.  遍历解析结果，调用 `DocumentManager.save_docs_for_module`。
4.  对于每一个生成的 `.stitcher.yaml`，通过消息总线通知用户。

### 标签
#intent/build #flow/ready #priority/high #comp/cli #comp/runtime #scope/core #ai/instruct #task/domain/cli #task/object/command-init #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 添加 Needle 消息资源

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p .stitcher/needle/en/init
~~~~~

~~~~~act
write_file
.stitcher/needle/en/init/main.json
~~~~~
~~~~~json
{
    "init.file.created": "📝 Created doc file: {path}",
    "init.run.complete": "🎉 Initialization complete. {count} document files created.",
    "init.no_docs_found": "🤔 No docstrings found in source files. No .stitcher.yaml files created."
}
~~~~~

#### Acts 2: 更新 StitcherApp 核心逻辑

我们需要在 `StitcherApp` 中实例化 `DocumentManager`，并添加 `run_init` 方法。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
from stitcher.scanner import parse_source_code, parse_plugin_entry, InspectionError
from stitcher.io import StubGenerator
from stitcher.spec import ModuleDef
from stitcher.common import bus
from stitcher.needle import L
from stitcher.config import load_config_from_path


class StitcherApp:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.generator = StubGenerator()

    def _scan_files(self, files_to_scan: List[Path]) -> List[ModuleDef]:
~~~~~
~~~~~python.new
from stitcher.scanner import parse_source_code, parse_plugin_entry, InspectionError
from stitcher.io import StubGenerator
from stitcher.spec import ModuleDef
from stitcher.common import bus
from stitcher.needle import L
from stitcher.config import load_config_from_path
from stitcher.app.services import DocumentManager


class StitcherApp:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.generator = StubGenerator()
        self.doc_manager = DocumentManager(root_path)

    def _scan_files(self, files_to_scan: List[Path]) -> List[ModuleDef]:
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        if generated_files:
            bus.success(L.generate.run.complete, count=len(generated_files))

        return generated_files
~~~~~
~~~~~python.new
        if generated_files:
            bus.success(L.generate.run.complete, count=len(generated_files))

        return generated_files

    def run_init(self) -> List[Path]:
        """
        Scans source files and extracts docstrings into external .stitcher.yaml files.
        """
        config = load_config_from_path(self.root_path)
        
        # 1. Discover and scan source files
        files_to_scan = []
        for scan_path_str in config.scan_paths:
            scan_path = self.root_path / scan_path_str
            if scan_path.is_dir():
                files_to_scan.extend(scan_path.rglob("*.py"))
            elif scan_path.is_file():
                files_to_scan.append(scan_path)
                
        unique_files = sorted(list(set(files_to_scan)))
        modules = self._scan_files(unique_files)
        
        if not modules:
            bus.warning(L.warning.no_files_or_plugins_found)
            return []
            
        # 2. Extract and save docs
        created_files: List[Path] = []
        for module in modules:
            # save_docs_for_module returns an empty path if no docs found/saved
            output_path = self.doc_manager.save_docs_for_module(module)
            if output_path and output_path.name:
                relative_path = output_path.relative_to(self.root_path)
                bus.success(L.init.file.created, path=relative_path)
                created_files.append(output_path)
                
        # 3. Report results
        if created_files:
            bus.success(L.init.run.complete, count=len(created_files))
        else:
            bus.info(L.init.no_docs_found)
            
        return created_files
~~~~~

#### Acts 3: 更新 CLI 命令

更新 `stitcher-cli` 中的 `init` 命令。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
@app.command()
def init():
    """Initialize Stitcher in the current project."""
    bus.info(L.cli.command.not_implemented, command="init")
~~~~~
~~~~~python.new
@app.command()
def init():
    """Initialize Stitcher in the current project."""
    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    app_instance.run_init()
~~~~~

#### Acts 4: 添加集成测试

~~~~~act
write_file
tests/integration/test_init_command.py
~~~~~
~~~~~python
import pytest
from pathlib import Path
from textwrap import dedent
from unittest.mock import MagicMock
from stitcher.app import StitcherApp


@pytest.fixture
def mock_bus(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("stitcher.app.core.bus", mock)
    # Also need to mock the service layer bus usage if we want to capture those messages, 
    # but here we test App -> Bus mainly. 
    # Actually, doc_manager uses bus? Check doc_manager impl.
    # Checked: doc_manager currently imports bus but doesn't seem to emit messages directly 
    # in save_docs_for_module. StitcherApp emits the messages. Good.
    return mock


def test_init_extracts_docs_to_yaml(tmp_path, mock_bus):
    # 1. Setup a project with source code containing docstrings
    project_root = tmp_path / "my_project"
    src_dir = project_root / "src"
    src_dir.mkdir(parents=True)
    
    # pyproject.toml
    (project_root / "pyproject.toml").write_text(dedent("""
        [tool.stitcher]
        scan_paths = ["src"]
    """))
    
    # Source file
    source_code = dedent("""
        def my_func():
            \"\"\"This is a docstring.\"\"\"
            pass
            
        class MyClass:
            \"\"\"Class doc.\"\"\"
            def method(self):
                \"\"\"Method doc.\"\"\"
                pass
    """)
    (src_dir / "main.py").write_text(source_code)
    
    # 2. Run init
    app = StitcherApp(root_path=project_root)
    created_files = app.run_init()
    
    # 3. Verify
    expected_yaml = src_dir / "main.stitcher.yaml"
    assert expected_yaml in created_files
    assert expected_yaml.exists()
    
    content = expected_yaml.read_text()
    assert "my_func: This is a docstring." in content
    assert "MyClass: Class doc." in content
    assert "MyClass.method: Method doc." in content
    
    # Verify bus messages
    mock_bus.success.assert_any_call(
        "init.file.created", path=expected_yaml.relative_to(project_root)
    )
    mock_bus.success.assert_any_call("init.run.complete", count=1)


def test_init_skips_files_without_docs(tmp_path, mock_bus):
    project_root = tmp_path / "no_docs_project"
    src_dir = project_root / "src"
    src_dir.mkdir(parents=True)
    
    (project_root / "pyproject.toml").write_text(dedent("""
        [tool.stitcher]
        scan_paths = ["src"]
    """))
    
    (src_dir / "main.py").write_text("def no_doc(): pass")
    
    app = StitcherApp(root_path=project_root)
    created_files = app.run_init()
    
    assert len(created_files) == 0
    mock_bus.info.assert_called_with("init.no_docs_found")
~~~~~

### 下一步建议
我们已经完成了文档的提取（init）。接下来的逻辑闭环是：在生成 `.pyi` 文件时（generate），能够优先读取这些外部 YAML 文件中的文档，而不是源代码中的文档（如果存在的话）。这将完成 **任务 2.3: 升级 `stitcher generate`**。
