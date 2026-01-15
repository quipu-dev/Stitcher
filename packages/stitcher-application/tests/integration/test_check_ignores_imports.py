from needle.pointer import L

from stitcher.test_utils import WorkspaceFactory, SpyBus, create_test_app


def test_check_does_not_report_imports_as_missing_docs(
    workspace_factory: WorkspaceFactory, monkeypatch
):
    """
    Verifies that 'stitcher check' does not incorrectly flag imported symbols
    as missing documentation. It should only flag symbols defined within the
    scanned module.
    """
    # 1. Setup: Create a project with a file that has imports and defined symbols
    spy_bus = SpyBus()
    ws = (
        workspace_factory.with_config({"scan_paths": ["src"]})
        .with_source(
            "src/my_pkg/core.py",
            """
import os
import logging
from pathlib import Path
from typing import Optional, List

# This function is defined locally and should be reported as missing docs.
def my_public_function():
    pass

# This class is defined locally and should also be reported.
class MyPublicClass:
    pass
            """,
        )
        .build()
    )

    # 2. Execution: Run the check command
    app = create_test_app(ws)
    with spy_bus.patch(monkeypatch):
        # run_check returns True (success) if there are only warnings.
        success = app.run_check()

    assert success
    # 3. Assertion & Visibility
    messages = spy_bus.get_messages()

    print("\n=== Captured Bus Messages ===")
    for msg in messages:
        print(f"[{msg['level'].upper()}] {msg['id']}: {msg.get('params', {})}")
    print("=============================")

    # Filter for only the 'missing documentation' warnings
    missing_doc_warnings = [
        msg for msg in messages if msg["id"] == str(L.check.issue.missing)
    ]

    # Extract the 'key' (the FQN) from the warning parameters
    reported_keys = {msg["params"]["key"] for msg in missing_doc_warnings}
    print(f"Reported Keys for Missing Docs: {reported_keys}")

    # Assert that our defined symbols ARE reported
    assert "my_public_function" in reported_keys, (
        "Locally defined function missing from report"
    )
    assert "MyPublicClass" in reported_keys, "Locally defined class missing from report"

    # Assert that imported symbols are NOT reported
    imported_symbols = {"os", "logging", "Path", "Optional", "List"}
    for symbol in imported_symbols:
        assert symbol not in reported_keys, (
            f"Imported symbol '{symbol}' was incorrectly reported as missing docs"
        )

    # Verify we found exactly what we expected (local definitions only)
    # Note: If there are other symbols (like __doc__ module level), adjust expectation.
    # The current setup creates a file with a module docstring (implied empty?),
    # but 'missing' check usually skips __doc__.
    # Let's stick to checking our specific targets.
