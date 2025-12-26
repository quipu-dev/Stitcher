import pytest
from pathlib import Path
from textwrap import dedent
from unittest.mock import MagicMock
from stitcher.app import StitcherApp
from stitcher.needle import L


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
        L.init.file.created, path=expected_yaml.relative_to(project_root)
    )
    mock_bus.success.assert_any_call(L.init.run.complete, count=1)


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
    mock_bus.info.assert_called_with(L.init.no_docs_found)