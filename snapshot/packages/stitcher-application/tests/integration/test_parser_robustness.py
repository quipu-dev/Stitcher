from stitcher.test_utils import WorkspaceFactory, create_test_app, SpyBus
from needle.pointer import L


def test_check_fails_gracefully_on_local_import(tmp_path, monkeypatch, spy_bus: SpyBus):
    """
    Verifies that when the parser raises an exception during scanning,
    the application handles it gracefully:
    1. Catches the exception.
    2. Logs a generic error.
    3. Ensures the overall command fails (returns False).
    """
    # GIVEN a project with a source file
    ws = WorkspaceFactory(tmp_path)
    ws.with_config({"scan_paths": ["src/pkg"]})
    ws.with_source("src/pkg/__init__.py", "")
    ws.with_source(
        "src/pkg/core.py",
        """
        def foo():
            pass
        """,
    )
    ws.build()

    # Create the app
    app = create_test_app(tmp_path)

    # SETUP: Mock the parser to simulate a crash on specific file
    # In Zero-IO mode, parsing happens in the Indexer via PythonAdapter
    # We need to find the correct parser instance to mock.

    from stitcher.lang.python.adapter import PythonAdapter

    python_adapter = app.file_indexer.adapters[".py"]
    # Verify we got the adapter and it's the concrete type we expect
    assert isinstance(python_adapter, PythonAdapter)

    real_parse = python_adapter.parser.parse

    def failing_parse(source_code, file_path=""):
        if "core.py" in str(file_path):
            raise ValueError("Simulated parser crash for testing")
        return real_parse(source_code, file_path)

    monkeypatch.setattr(python_adapter.parser, "parse", failing_parse)

    # WHEN we run the check command
    with spy_bus.patch(monkeypatch):
        success = app.run_check()

    # THEN the command should fail
    assert not success, "Command should return False when parser fails"

    # AND report a generic error
    spy_bus.assert_id_called(L.error.generic, level="error")

    messages = spy_bus.get_messages()
    error_msg = next(
        (m for m in messages if m["id"] == str(L.error.generic)),
        None,
    )
    assert error_msg is not None
    assert "Simulated parser crash" in str(error_msg["params"].get("error", ""))
