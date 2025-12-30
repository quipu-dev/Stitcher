import sys

from stitcher.test_utils import create_test_app
from stitcher.config import StitcherConfig
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def test_app_scan_and_generate_single_file(tmp_path, monkeypatch):
    factory = WorkspaceFactory(tmp_path)
    project_root = factory.with_source(
        "greet.py",
        """
            def greet(name: str) -> str:
                \"\"\"Returns a greeting.\"\"\"
                return f"Hello, {name}!"
            """,
    ).build()

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        # Accessing internal methods directly for this specific test case
        # as per original test logic
        source_file = project_root / "greet.py"
        module = app.scanner.scan_files([source_file])[0]
        app.generate_runner._generate_stubs([module], StitcherConfig())

    spy_bus.assert_id_called(L.generate.file.success, level="success")

    error_messages = [m for m in spy_bus.get_messages() if m["level"] == "error"]
    assert not error_messages, f"Found unexpected error messages: {error_messages}"


def test_app_run_from_config_with_source_files(tmp_path, monkeypatch):
    # Recreating the structure previously held in tests/fixtures/sample_project
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src/app"]})
        .with_source(
            "src/app/main.py",
            """
            def start():
                \"\"\"Starts the application.\"\"\"
                pass
            """,
        )
        .with_source(
            "src/app/utils/helpers.py",
            """
            def assist():
                \"\"\"Provides assistance.\"\"\"
                pass
            """,
        )
        # This file should remain untouched/unscanned
        .with_source("tests/test_helpers.py", "def test_assist(): pass")
        .build()
    )

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        app.run_from_config()

    spy_bus.assert_id_called(L.generate.file.success, level="success")
    spy_bus.assert_id_called(L.generate.run.complete, level="success")

    success_messages = [m for m in spy_bus.get_messages() if m["level"] == "success"]
    # 2 files generated (main.py, helpers.py), 1 run complete message
    assert len(success_messages) == 3


def test_app_run_multi_target(tmp_path, monkeypatch):
    """
    Verifies that StitcherApp correctly handles multiple targets defined in pyproject.toml.
    """
    # 1. Arrange
    factory = WorkspaceFactory(tmp_path)

    # Manually injecting multi-target config into pyproject.toml via raw content
    # because WorkspaceFactory.with_config currently assumes simple [tool.stitcher] structure.
    # We'll just overwrite pyproject.toml at the end or use with_source for it.

    project_root = (
        factory.with_source("src/pkg_a/main.py", "def func_a(): ...")
        .with_source("src/pkg_b/main.py", "def func_b(): ...")
        .build()
    )

    # Overwrite pyproject.toml with multi-target config
    (project_root / "pyproject.toml").write_text(
        """
[project]
name = "monorepo"

[tool.stitcher.targets.pkg_a]
scan_paths = ["src/pkg_a"]
stub_path = "typings/pkg_a"

[tool.stitcher.targets.pkg_b]
scan_paths = ["src/pkg_b"]
stub_path = "typings/pkg_b"
        """,
        encoding="utf-8",
    )

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        app.run_from_config()

    # 3. Assert
    # Check physical files
    # Note: Stitcher preserves the package structure relative to 'src'.
    # So 'src/pkg_a/main.py' becomes 'pkg_a/main.pyi' inside the stub output directory.
    assert (project_root / "typings/pkg_a/pkg_a/main.pyi").exists()
    assert (project_root / "typings/pkg_b/pkg_b/main.pyi").exists()

    # Check bus messages
    # We expect "Processing target: ..." messages
    messages = spy_bus.get_messages()
    processing_msgs = [
        m for m in messages if m["id"] == str(L.generate.target.processing)
    ]
    assert len(processing_msgs) == 2

    target_names = {m["params"]["name"] for m in processing_msgs}
    assert target_names == {"pkg_a", "pkg_b"}

    spy_bus.assert_id_called(L.generate.run.complete, level="success")


def test_app_generates_stubs_for_plugins_and_sources(tmp_path, monkeypatch):
    # 1. Arrange: Setup a workspace with both source code and a plugin definition
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", "def static_func(): ...")
        # Define the plugin source code in a separate package within the workspace
        .with_source(
            "plugin_pkg/main.py",
            """
            def dynamic_util() -> bool:
                \"\"\"A dynamically discovered utility.\"\"\"
                return True
            """,
        )
        .with_source("plugin_pkg/__init__.py", "")
        # Register the plugin via entry points
        .with_entry_points(
            "stitcher.plugins", {"dynamic.utils": "plugin_pkg.main:dynamic_util"}
        )
        .build()
    )

    # Add the workspace root to sys.path so the plugin can be imported
    sys.path.insert(0, str(project_root))

    try:
        app = create_test_app(root_path=project_root)
        spy_bus = SpyBus()

        # 2. Act
        with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
            app.run_from_config()

        # 3. Assert
        # Assert stubs were created
        assert (project_root / "src" / "main.pyi").exists()
        assert (project_root / "dynamic" / "utils.pyi").exists()
        # Intermediate __init__.pyi should be created for the virtual module
        assert (project_root / "dynamic" / "__init__.pyi").exists()

        # Assert bus messages
        spy_bus.assert_id_called(L.generate.file.success, level="success")
        spy_bus.assert_id_called(L.generate.run.complete, level="success")

        success_messages = [
            m for m in spy_bus.get_messages() if m["level"] == "success"
        ]
        # 3 files generated (src/main, dynamic/utils, dynamic/__init__), 1 run complete
        assert len(success_messages) == 4

    finally:
        # Cleanup sys.path
        sys.path.pop(0)
