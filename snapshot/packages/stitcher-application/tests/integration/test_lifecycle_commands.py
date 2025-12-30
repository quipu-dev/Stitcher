from textwrap import dedent
from stitcher.test_utils import create_test_app
from needle.pointer import L
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

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    # Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        app.run_strip()

    # Assert
    final_code = (project_root / source_path).read_text()
    assert '"""' not in final_code
    assert "def func():" in final_code
    assert "pass" in final_code

    spy_bus.assert_id_called(L.strip.file.success)
    spy_bus.assert_id_called(L.strip.run.complete)


def test_inject_command_injects_docstrings(tmp_path, monkeypatch):
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

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    # Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        app.run_inject()

    # Assert
    final_code = (project_root / source_path).read_text()
    assert '"""Injected docstring."""' in final_code

    spy_bus.assert_id_called(L.inject.file.success)
    spy_bus.assert_id_called(L.inject.run.complete)
