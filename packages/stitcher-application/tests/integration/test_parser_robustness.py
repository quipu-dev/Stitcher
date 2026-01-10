import pytest
from stitcher.test_utils import WorkspaceFactory, create_test_app, SpyBus
from needle.pointer import L


def test_check_fails_gracefully_on_local_import(tmp_path, monkeypatch):
    """
    Verifies that the parser failing on a local (non-module-level) import
    is handled gracefully by the application, causing `check` to fail
    without crashing.
    """
    # GIVEN a project with a source file containing a local import
    # that is known to cause issues with type alias resolution in griffe.
    ws = WorkspaceFactory(tmp_path)
    ws.with_config({"scan_paths": ["src/buggy_pkg"]})
    ws.with_source("src/buggy_pkg/__init__.py", "")
    ws.with_source(
        "src/buggy_pkg/core.py",
        """
        class MyClass:
            def __init__(self):
                pass

            def a_method(self) -> "Optional[str]":
                from typing import Optional  # <-- This import causes the parser to fail
                return "hello"
        """,
    )
    ws.build()

    # WHEN we run the check command
    app = create_test_app(tmp_path)
    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch):
        success = app.run_check()

    # THEN the command should fail, not crash, and report a generic error
    assert not success
    spy_bus.assert_id_called(L.error.generic, level="error")

    messages = spy_bus.get_messages()
    error_msg = next(
        (m for m in messages if m["id"] == str(L.error.generic)),
        None,
    )
    assert error_msg is not None
    # Check that the error reported contains information about the root cause
    assert "Could not resolve alias" in str(error_msg["params"].get("error", ""))