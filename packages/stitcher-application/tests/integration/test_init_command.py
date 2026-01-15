from stitcher.test_utils import create_test_app
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

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        app.run_init()

    # 3. Assert
    expected_yaml = project_root / "src/main.stitcher.yaml"
    assert expected_yaml.exists()

    content = expected_yaml.read_text()
    # Check for block style. ruamel.yaml is smart and won't quote simple keys.
    assert "my_func: |-" in content
    assert "  This is a docstring." in content

    # Updated assertions for Pump behavior
    # L.init.file.created -> L.pump.file.success (since keys were updated)
    spy_bus.assert_id_called(L.pump.file.success, level="success")
    spy_bus.assert_id_called(L.pump.run.complete, level="success")


def test_init_skips_files_without_docs(tmp_path, monkeypatch):
    # 1. Arrange
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", "def no_doc(): pass")
        .build()
    )

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        app.run_init()

    # 3. Assert - Pump returns No Changes info
    spy_bus.assert_id_called(L.pump.run.no_changes, level="info")
