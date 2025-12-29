import pytest
from pathlib import Path
from stitcher.test_utils import WorkspaceFactory
from stitcher.adapter.python import GriffePythonParser

def test_griffe_resolves_imports(tmp_path):
    """
    Integration test to reproduce 'Could not resolve alias' error.
    Simulates a project with local imports and standard library imports.
    """
    # 1. Setup specific project structure
    # src/
    #   pkg/
    #     __init__.py
    #     models.py  (Defines User)
    #     main.py    (Imports User and List)
    
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/pkg/__init__.py", "")
        .with_source(
            "src/pkg/models.py", 
            """
class User:
    name: str = "Alice"
            """
        )
        .with_source(
            "src/pkg/main.py",
            """
from typing import List
from .models import User

def get_users() -> List[User]:
    return [User()]
            """
        )
        .build()
    )

    parser = GriffePythonParser()
    
    # We simulate what StitcherApp does: iterate files and parse them.
    # The critical part is what we pass as 'file_path'.
    # In the app, it is relative to root, e.g., "src/pkg/main.py"
    
    main_py_path = "src/pkg/main.py"
    source_code = (project_root / main_py_path).read_text(encoding="utf-8")
    
    # 2. Act
    # This might fail or return a ModuleDef with broken annotations depending on 
    # how Griffe handles the missing context if we don't config search paths.
    try:
        module = parser.parse(source_code, file_path=main_py_path)
    except Exception as e:
        pytest.fail(f"Griffe parsing crashed: {e}")

    # 3. Assert
    assert len(module.functions) == 1
    func = module.functions[0]
    
    # If alias resolution fails, Griffe might return the Alias object string rep 
    # or crash when we try to str() it in our parser implementation.
    # We want to see if the return annotation is correctly resolved to a string "List[User]"
    # or at least a string representation that doesn't crash.
    
    # Note: Griffe 1.0+ might resolve this to "typing.List[src.pkg.models.User]" or similar
    # if paths are correct. If not, it might explain the crash.
    print(f"Return annotation: {func.return_annotation}")
    assert func.return_annotation is not None
    assert "List" in func.return_annotation