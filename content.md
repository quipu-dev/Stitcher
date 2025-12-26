好的，核心的 AST 变换器已经准备就绪。现在我们将这些能力集成到应用层和 CLI 中，并添加必要的本地化和测试，从而完成整个生命周期管理功能的闭环。

## [WIP] feat: 集成 `strip` 和 `eject` 命令到应用与 CLI

### 用户需求
用户需要通过命令行 `stitcher strip` 和 `stitcher eject` 来实际操作他们的源文件，完成文档的移除与注入。这些操作具有潜在的破坏性，因此需要有明确的确认提示。

### 评论
这个计划将之前在 `stitcher-scanner` 中构建的底层能力，通过 `stitcher-application` 暴露为业务逻辑，并最终在 `stitcher-cli` 中呈现给用户。关键点在于确保文件 I/O 的正确性，以及在 CLI 层加入交互式确认，防止用户误操作。

### 目标
1.  **应用层**: 在 `StitcherApp` 中实现 `run_strip` 和 `run_eject` 方法。
2.  **CLI 层**: 在 `stitcher.cli.main` 中创建 `strip` 和 `eject` 两个新的 `typer` 命令，并添加确认提示。
3.  **本地化**: 在 `.stitcher/needle` 中为新命令添加所有必要的 UI 文本。
4.  **测试**: 编写集成测试，验证从 CLI 调用到文件系统变更的整个端到端流程。

### 基本原理
-   **`run_strip`**: 遍历 `scan_paths` -> 读取每个文件 -> 调用 `strip_docstrings` -> 写回文件 -> 发送总线消息。
-   **`run_eject`**: 遍历 `scan_paths` -> 为每个文件加载其对应的 `.stitcher.yaml` -> 读取源文件 -> 调用 `inject_docstrings` -> 写回文件 -> 发送总线消息。
-   **CLI**: 使用 `typer.confirm()` 来处理交互，如果用户拒绝，则通过 `typer.Abort()` 优雅地中止操作。

### 标签
#intent/build #flow/ready #priority/high
#comp/application #comp/cli #comp/scanner #concept/ux
#ai/instruct
#task/domain/dev-tools #task/object/lifecycle-management #task/action/integration
#task/state/continue

---

### Script

#### Acts 1: 添加本地化消息

为新命令创建对应的消息模板。

~~~~~act
write_file
.stitcher/needle/en/strip/main.json
~~~~~
~~~~~json
{
    "strip.run.confirm": "⚠️  This will permanently remove docstrings from source files. This is irreversible unless you use version control. Are you sure you want to continue?",
    "strip.run.aborted": "Strip operation aborted.",
    "strip.file.success": "✅ Stripped docstrings from: {path}",
    "strip.run.complete": "✨ Strip complete. {count} files modified."
}
~~~~~

~~~~~act
write_file
.stitcher/needle/en/eject/main.json
~~~~~
~~~~~json
{
    "eject.run.confirm": "⚠️  This will overwrite source files with content from .stitcher.yaml files. Any docstrings currently in your code will be replaced. Are you sure you want to continue?",
    "eject.run.aborted": "Eject operation aborted.",
    "eject.file.success": "📝 Injected docstrings into: {path}",
    "eject.run.complete": "🎉 Eject complete. {count} files modified.",
    "eject.no_docs_found": "🤔 No docstrings found in any .stitcher.yaml files. Nothing to eject."
}
~~~~~

#### Acts 2: 在 `StitcherApp` 中实现核心逻辑

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
from stitcher.scanner import parse_source_code, parse_plugin_entry, InspectionError
from stitcher.io import StubGenerator
from stitcher.spec import ModuleDef
~~~~~
~~~~~python.new
from stitcher.scanner import (
    parse_source_code,
    parse_plugin_entry,
    InspectionError,
    strip_docstrings,
    inject_docstrings,
)
from stitcher.io import StubGenerator
from stitcher.spec import ModuleDef
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        bus.success(L.check.run.success)
        return True
~~~~~
~~~~~python.new
        bus.success(L.check.run.success)
        return True

    def run_strip(self) -> List[Path]:
        """Strips docstrings from all source files."""
        config = load_config_from_path(self.root_path)
        files_to_scan = self._get_files_from_config(config)
        modified_files: List[Path] = []

        for file_path in files_to_scan:
            try:
                original_content = file_path.read_text(encoding="utf-8")
                stripped_content = strip_docstrings(original_content)

                if original_content != stripped_content:
                    file_path.write_text(stripped_content, encoding="utf-8")
                    modified_files.append(file_path)
                    relative_path = file_path.relative_to(self.root_path)
                    bus.success(L.strip.file.success, path=relative_path)

            except Exception as e:
                bus.error(L.error.generic, error=e)

        if modified_files:
            bus.success(L.strip.run.complete, count=len(modified_files))
        
        return modified_files

    def run_eject(self) -> List[Path]:
        """Injects docstrings from YAML files back into source code."""
        config = load_config_from_path(self.root_path)
        modules = self._scan_files(self._get_files_from_config(config))
        modified_files: List[Path] = []
        total_docs_found = 0

        for module in modules:
            docs = self.doc_manager.load_docs_for_module(module)
            if not docs:
                continue
            
            total_docs_found += len(docs)
            source_path = self.root_path / module.file_path
            
            try:
                original_content = source_path.read_text(encoding="utf-8")
                injected_content = inject_docstrings(original_content, docs)

                if original_content != injected_content:
                    source_path.write_text(injected_content, encoding="utf-8")
                    modified_files.append(source_path)
                    relative_path = source_path.relative_to(self.root_path)
                    bus.success(L.eject.file.success, path=relative_path)
            except Exception as e:
                bus.error(L.error.generic, error=e)

        if modified_files:
            bus.success(L.eject.run.complete, count=len(modified_files))
        elif total_docs_found == 0:
            bus.info(L.eject.no_docs_found)
            
        return modified_files

    def _get_files_from_config(self, config) -> List[Path]:
        """Helper to discover all source files based on config."""
        files_to_scan = []
        for scan_path_str in config.scan_paths:
            scan_path = self.root_path / scan_path_str
            if scan_path.is_dir():
                files_to_scan.extend(scan_path.rglob("*.py"))
            elif scan_path.is_file():
                files_to_scan.append(scan_path)
        return sorted(list(set(files_to_scan)))
~~~~~

#### Acts 3: 在 CLI 中添加 `strip` 和 `eject` 命令

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
@app.command()
def check():
    """Verify consistency between code and docs."""
    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    success = app_instance.run_check()
    if not success:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
~~~~~
~~~~~python.new
@app.command()
def check():
    """Verify consistency between code and docs."""
    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    success = app_instance.run_check()
    if not success:
        raise typer.Exit(code=1)


@app.command()
def strip():
    """Remove docstrings from source files."""
    if not typer.confirm(bus.render_to_string(L.strip.run.confirm)):
        bus.warning(L.strip.run.aborted)
        raise typer.Abort()

    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    app_instance.run_strip()


@app.command()
def eject():
    """Inject docstrings from .stitcher.yaml files back into code."""
    if not typer.confirm(bus.render_to_string(L.eject.run.confirm)):
        bus.warning(L.eject.run.aborted)
        raise typer.Abort()

    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    app_instance.run_eject()


# Helper needed for typer.confirm, as it prints directly
# We need to render message to a string first
def render_to_string_patch(self, msg_id, **kwargs):
    template = L.needle.get(msg_id)
    return template.format(**kwargs)

bus.render_to_string = render_to_string_patch.__get__(bus)


if __name__ == "__main__":
    app()
~~~~~

#### Acts 4: 添加 `render_to_string` 的 Monkeypatch

上面的代码需要 `render_to_string` 方法，我们将其添加到 `MessageBus` 中。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/messaging/bus.py
~~~~~
~~~~~python.old
    def error(self, msg_id: Union[str, SemanticPointer], **kwargs: Any) -> None:
        self._render("error", msg_id, **kwargs)


# Global singleton instance
bus = MessageBus()
~~~~~
~~~~~python.new
    def error(self, msg_id: Union[str, SemanticPointer], **kwargs: Any) -> None:
        self._render("error", msg_id, **kwargs)

    def render_to_string(self, msg_id: Union[str, SemanticPointer], **kwargs: Any) -> str:
        """Resolves a message to a string without sending it to the renderer."""
        template = needle.get(msg_id)
        try:
            return template.format(**kwargs)
        except KeyError:
            return f"<formatting_error for '{str(msg_id)}'>"


# Global singleton instance
bus = MessageBus()
~~~~~

#### Acts 5: 编写集成测试

~~~~~act
write_file
tests/integration/test_lifecycle_commands.py
~~~~~
~~~~~python
from textwrap import dedent
from stitcher.app import StitcherApp
from stitcher.needle import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def test_strip_command_removes_docstrings(tmp_path, monkeypatch):
    # Arrange
    factory = WorkspaceFactory(tmp_path)
    source_path = "src/main.py"
    initial_code = dedent("""
    \"\"\"Module doc.\"\"\"
    def func():
        \"\"\"Func doc.\"\"\"
        pass
    """)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(source_path, initial_code)
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # Act
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        app.run_strip()

    # Assert
    final_code = (project_root / source_path).read_text()
    assert '"""' not in final_code
    assert "def func():" in final_code
    assert "pass" in final_code

    spy_bus.assert_id_called(L.strip.file.success)
    spy_bus.assert_id_called(L.strip.run.complete)


def test_eject_command_injects_docstrings(tmp_path, monkeypatch):
    # Arrange
    factory = WorkspaceFactory(tmp_path)
    source_path = "src/main.py"
    initial_code = "def func(): pass"
    docs_data = {"func": "Injected docstring."}
    
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(source_path, initial_code)
        .with_docs("src/main.stitcher.yaml", docs_data)
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # Act
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        app.run_eject()

    # Assert
    final_code = (project_root / source_path).read_text()
    assert '"""Injected docstring."""' in final_code
    
    spy_bus.assert_id_called(L.eject.file.success)
    spy_bus.assert_id_called(L.eject.run.complete)
~~~~~

### 下一步建议
运行 `pytest`。如果所有测试都通过，说明 `strip` 和 `eject` 命令已经成功集成。我们可以创建一个 `[COMMIT]` 计划来提交这些变更。
