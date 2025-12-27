from stitcher.app import StitcherApp
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def test_check_reports_untracked_for_non_empty_file(tmp_path, monkeypatch):
    """
    Verifies that 'check' correctly reports UNTRACKED for a new file
    that actually contains content.
    """
    # 1. Arrange: A source file with content, but no doc file
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
    assert success is True
    spy_bus.assert_id_called(L.check.file.untracked, level="warning")
    spy_bus.assert_id_called(L.check.run.success_with_warnings, level="success")


def test_check_is_silent_for_empty_untracked_file(tmp_path, monkeypatch):
    """
    Verifies that 'check' does NOT report UNTRACKED for an untracked file
    that contains no documentable content (e.g., an empty __init__.py).
    """
    # 1. Arrange: An empty source file with no doc file
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/__init__.py", "# This file is intentionally empty")
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_check()

    # 3. Assert
    assert success is True
    # Crucially, assert that the overall success message (without warnings) was called
    spy_bus.assert_id_called(L.check.run.success, level="success")

    # And verify NO untracked message was sent
    messages = spy_bus.get_messages()
    assert not any(msg["id"] == str(L.check.file.untracked) for msg in messages)