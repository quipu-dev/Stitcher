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