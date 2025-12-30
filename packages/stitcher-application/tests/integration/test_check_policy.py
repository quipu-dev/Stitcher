from stitcher.test_utils import create_test_app
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def test_private_members_allowed_in_yaml(tmp_path, monkeypatch):
    """
    Policy Test: Private members present in YAML should NOT trigger EXTRA error
    if they exist in the code. They are 'allowed extras'.
    """
    # 1. Arrange: Code with private members and corresponding docs
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(
            "src/core.py",
            """
            class Internal:
                def _hidden(self): pass
            def _helper(): pass
            """,
        )
        .with_docs(
            "src/core.stitcher.yaml",
            {
                "Internal": "Public class doc",  # Public, checked normally
                "Internal._hidden": "Private method doc",  # Private, allowed
                "_helper": "Private func doc",  # Private, allowed
            },
        )
        .build()
    )

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        success = app.run_check()

    # 3. Assert
    # Should be perfectly clean (True) because private docs are allowed
    assert success is True

    # Ensure NO errors or warnings about extras/missing
    messages = spy_bus.get_messages()
    errors = [m for m in messages if m["level"] == "error"]
    warnings = [m for m in messages if m["level"] == "warning"]

    assert not errors, f"Found unexpected errors: {errors}"
    assert not warnings, f"Found unexpected warnings: {warnings}"

    spy_bus.assert_id_called(L.check.run.success, level="success")


def test_ghost_keys_trigger_extra_error(tmp_path, monkeypatch):
    """
    Policy Test: Keys in YAML that do not exist in code (even privately)
    MUST trigger EXTRA error.
    """
    # 1. Arrange: Docs pointing to non-existent code
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/ghost.py", "def real(): pass")
        .with_docs(
            "src/ghost.stitcher.yaml",
            {
                "real": "Exists",
                "ghost_func": "Does not exist",
                "_ghost_private": "Does not exist either",
            },
        )
        .build()
    )

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        success = app.run_check()

    # 3. Assert
    assert success is False

    # We expect EXTRA errors for both ghost keys
    spy_bus.assert_id_called(L.check.issue.extra, level="error")

    # Verify specific keys
    extra_msgs = [
        m for m in spy_bus.get_messages() if m["id"] == str(L.check.issue.extra)
    ]
    keys = sorted([m["params"]["key"] for m in extra_msgs])
    assert keys == ["_ghost_private", "ghost_func"]


def test_public_missing_triggers_warning_only(tmp_path, monkeypatch):
    """
    Policy Test: Missing docs for public API should be WARNING, not ERROR.
    Exit code should be success (True).
    """
    # 1. Arrange: Public code without docs
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/lib.py", "def public_api(): pass")
        # Create an empty doc file to ensure the file is tracked
        .with_docs("src/lib.stitcher.yaml", {"__doc__": "Module doc"})
        .build()
    )

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        success = app.run_check()

    # 3. Assert
    assert success is True  # Not blocking

    spy_bus.assert_id_called(L.check.issue.missing, level="warning")
    spy_bus.assert_id_called(L.check.run.success_with_warnings, level="success")
