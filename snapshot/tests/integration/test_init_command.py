from stitcher.app import StitcherApp
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def test_init_extracts_docs_to_yaml(tmp_path, monkeypatch):
    # 1. Arrange: Use the factory to build the project
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(
            "src/main.py",
            """
            def my_func():
                \"\"\"This is a docstring.\"\"\"
                pass
            """,
        )
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        created_files = app.run_init()

    # 3. Assert
    expected_yaml = project_root / "src/main.stitcher.yaml"
    assert expected_yaml in created_files

    content = expected_yaml.read_text()
    # Check for block style with quoted key
    assert '"my_func": |-' in content
    assert "  This is a docstring." in content

    spy_bus.assert_id_called(L.init.file.created, level="success")
    spy_bus.assert_id_called(L.init.run.complete, level="success")


def test_init_skips_files_without_docs(tmp_path, monkeypatch):
    # 1. Arrange
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", "def no_doc(): pass")
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        created_files = app.run_init()

    # 3. Assert
    assert len(created_files) == 0
    spy_bus.assert_id_called(L.init.no_docs_found, level="info")
