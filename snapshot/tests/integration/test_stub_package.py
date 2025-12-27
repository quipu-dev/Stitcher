import sys
from pathlib import Path

if sys.version_info < (3, 11):
    import tomli as tomllib
else:
    import tomllib

from stitcher.app import StitcherApp
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def test_generate_with_stub_package_creates_correct_structure(tmp_path, monkeypatch):
    """
    End-to-end test for the PEP 561 stub package generation mode.
    """
    # 1. Arrange
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config(
            {
                "scan_paths": ["src/my_app"],
                "stub_package": "stubs",  # <-- Enable stub package mode
            }
        )
        # Define the main project's name, which is used for the stub package name
        .with_project_name("my-test-project")
        .with_source(
            "src/my_app/main.py",
            """
            def run():
                \"\"\"Main entry point.\"\"\"
                pass
            """,
        )
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        app.run_from_config()

    # 3. Assert
    # --- Assert File System Structure ---
    stub_pkg_path = project_root / "stubs"
    assert stub_pkg_path.is_dir()

    stub_pyproject = stub_pkg_path / "pyproject.toml"
    assert stub_pyproject.is_file()

    src_path = stub_pkg_path / "src"
    assert src_path.is_dir()

    pyi_file = src_path / "my_app" / "main.pyi"
    assert pyi_file.is_file()
    assert "def run() -> None:" in pyi_file.read_text()

    py_typed_marker = src_path / "my_app" / "py.typed"
    assert py_typed_marker.is_file()

    # --- Assert pyproject.toml Content ---
    with stub_pyproject.open("rb") as f:
        stub_config = tomllib.load(f)
    assert stub_config["project"]["name"] == "my-test-project-stubs"

    # --- Assert Bus Messages ---
    spy_bus.assert_id_called(L.generate.stub_pkg.scaffold)
    spy_bus.assert_id_called(L.generate.stub_pkg.success)
    spy_bus.assert_id_called(L.generate.file.success)
    spy_bus.assert_id_called(L.generate.run.complete)