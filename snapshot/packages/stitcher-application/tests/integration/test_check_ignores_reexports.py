import pytest
from needle.pointer import L
from pathlib import Path

from stitcher.test_utils import WorkspaceFactory, SpyBus, create_test_app


def test_check_ignores_reexports_and_imports(tmp_path: Path, monkeypatch):
    """
    Verifies that 'stitcher check' correctly ignores:
    1. Symbols re-exported from another module in the same package.
    2. Standard library imports.
    It should only flag symbols physically defined in the file being checked.
    """
    # 1. Setup: Create a project with a re-export structure
    workspace_factory = WorkspaceFactory(tmp_path)
    spy_bus = SpyBus()
    ws = (
        workspace_factory.with_config({"scan_paths": ["src"]})
        .with_source(
            "src/my_lib/defs.py",
            """
class MyDefinedClass:
    '''This class has a docstring.'''
    pass
            """,
        )
        .with_source(
            "src/my_lib/__init__.py",
            """
from typing import Dict
from .defs import MyDefinedClass  # This is a re-export

# This function is locally defined and should be reported
def my_local_function():
    pass
            """,
        )
        .build()
    )

    # 2. Execution: Run the check command
    app = create_test_app(ws)
    with spy_bus.patch(monkeypatch):
        app.run_check()

    # 3. Assertion: Verify the output from the bus
    messages = spy_bus.get_messages()
    
    print("\n=== Captured Bus Messages ===")
    for msg in messages:
        print(f"[{msg['level'].upper()}] {msg['id']}: {msg.get('params', {})}")
    print("=============================")


    missing_doc_warnings = [
        msg for msg in messages if msg["id"] == str(L.check.issue.missing)
    ]

    # The `missing` message only contains the key, not the path. The file-level
    # summary message contains the path. We only need to check the key here.
    reported_keys = {msg["params"]["key"] for msg in missing_doc_warnings}

    # We also check untracked messages, as new symbols will appear here.
    untracked_missing_warnings = [
        msg for msg in messages if msg["id"] == str(L.check.issue.untracked_missing_key)
    ]
    reported_untracked_keys = {msg["params"]["key"] for msg in untracked_missing_warnings}

    all_reported_keys = reported_keys.union(reported_untracked_keys)

    # Assert that the locally defined function IS reported as missing
    assert (
        "my_local_function" in all_reported_keys
    ), "Local function was not reported as missing."

    # Assert that standard imports and re-exports are NOT reported
    assert (
        "Dict" not in all_reported_keys
    ), "Standard import 'Dict' was incorrectly reported."
    
    assert (
        "MyDefinedClass" not in all_reported_keys
    ), "Re-exported class 'MyDefinedClass' was incorrectly reported."

    # Assert that the total number of missing doc warnings is exactly 1
    assert (
        len(all_reported_keys) == 1
    ), f"Expected 1 missing doc warning, but found {len(all_reported_keys)}: {all_reported_keys}"
