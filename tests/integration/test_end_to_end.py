import pytest
import shutil
from pathlib import Path
from textwrap import dedent

# This module doesn't exist yet, driving its creation
from stitcher.app import StitcherApp

def test_app_scan_and_generate_single_file(tmp_path):
    # 1. Arrange: Create a source python file
    source_content = dedent("""
        def greet(name: str) -> str:
            \"\"\"Returns a greeting.\"\"\"
            return f"Hello, {name}!"
    """)
    source_file = tmp_path / "greet.py"
    source_file.write_text(source_content, encoding="utf-8")
    
    # 2. Act: Initialize App and run generation
    app = StitcherApp(root_path=tmp_path)
    # We expect this method to scan the file and generate a .pyi next to it
    generated_files = app.run_generate(files=[source_file])
    
    # 3. Assert: Verify the .pyi file exists and has correct content
    expected_pyi_path = tmp_path / "greet.pyi"
    
    assert expected_pyi_path.exists()
    assert expected_pyi_path in generated_files
    
    pyi_content = expected_pyi_path.read_text(encoding="utf-8")
    
    # Verify core components are present
    assert "def greet(name: str) -> str:" in pyi_content
    assert '"""Returns a greeting."""' in pyi_content
    assert "..." in pyi_content


def test_app_run_from_config(tmp_path):
    # 1. Arrange: Copy the fixture project into a temporary directory
    fixture_root = Path(__file__).parent.parent / "fixtures" / "sample_project"
    project_root = tmp_path / "sample_project"
    shutil.copytree(fixture_root, project_root)

    # 2. Act
    app = StitcherApp(root_path=project_root)
    # This new method should discover config and run generation
    generated_files = app.run_from_config()

    # 3. Assert
    main_pyi = project_root / "src" / "app" / "main.pyi"
    helpers_pyi = project_root / "src" / "app" / "utils" / "helpers.pyi"
    test_pyi = project_root / "tests" / "test_helpers.pyi"

    assert main_pyi.exists()
    assert helpers_pyi.exists()
    assert not test_pyi.exists() # Crucially, this should NOT be generated

    assert main_pyi in generated_files
    assert helpers_pyi in generated_files

    main_content = main_pyi.read_text()
    assert "def start():" in main_content
    assert '"""Starts the application."""' in main_content