from stitcher.app import StitcherApp
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def test_check_reports_untracked_file(tmp_path, monkeypatch):
    """
    Verifies that 'check' correctly identifies a source file
    that has no corresponding .stitcher.yaml file as UNTRACKED.
    """
    # 1. Arrange: Create a workspace with a source file but NO doc file
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", "def new_func(): pass")
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_check()

    # 3. Assert
    assert success is True, "Check should pass with warnings for untracked files"

    # Assert that the specific UNTRACKED message was sent as a warning
    spy_bus.assert_id_called(L.check.file.untracked, level="warning")
    spy_bus.assert_id_called(L.check.run.success_with_warnings, level="success")

    # Verify that NO key-level issues were reported for this file
    messages = spy_bus.get_messages()
    key_level_issues = {
        str(L.check.issue.missing),
        str(L.check.issue.pending),
        str(L.check.issue.extra),
        str(L.check.issue.conflict),
    }
    for msg in messages:
        assert msg["id"] not in key_level_issues, f"Unexpected key-level issue found: {msg}"