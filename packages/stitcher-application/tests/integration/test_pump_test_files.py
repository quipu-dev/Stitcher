import yaml
from stitcher.test_utils import create_test_app
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def test_pump_can_extract_from_test_files(tmp_path, monkeypatch):
    """
    Regression Test: Verifies that stitcher does NOT ignore files starting with 'test_'
    or living in a 'tests' directory, provided they are explicitly included in scan_paths.
    """
    # 1. Arrange
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["tests"]})
        .with_source(
            "tests/test_logic.py",
            '''
def test_something():
    """This is a docstring in a test file."""
    pass
''',
        )
        .build()
    )

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        result = app.run_pump()

    # 3. Assert
    assert result.success is True

    # It should report success for the file
    spy_bus.assert_id_called(L.pump.file.success, level="success")

    # Verify the yaml file was created and content is correct
    yaml_path = project_root / "tests/test_logic.stitcher.yaml"
    assert yaml_path.exists(), "The .stitcher.yaml file for the test was not created."

    with yaml_path.open() as f:
        data = yaml.safe_load(f)
        assert data["test_something"] == "This is a docstring in a test file."
