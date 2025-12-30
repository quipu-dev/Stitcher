from stitcher.test_utils import create_test_app
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def test_check_reports_untracked_with_details(tmp_path, monkeypatch):
    """
    Verifies that 'check' reports a detailed UNTRACKED message when a new
    file contains public APIs that are missing docstrings.
    """
    # 1. Arrange: A new file with one documented and one undocumented function
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(
            "src/main.py",
            """
            def func_documented():
                \"\"\"I have a docstring.\"\"\"
                pass

            def func_undocumented():
                pass
            """,
        )
        .build()
    )

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        app.run_check()

    # 3. Assert
    # Assert the detailed header was called
    spy_bus.assert_id_called(L.check.file.untracked_with_details, level="warning")
    # Assert the specific key was listed
    spy_bus.assert_id_called(L.check.issue.untracked_missing_key, level="warning")

    # Verify the correct key was reported
    messages = spy_bus.get_messages()
    missing_key_msg = next(
        (m for m in messages if m["id"] == str(L.check.issue.untracked_missing_key)),
        None,
    )
    assert missing_key_msg is not None
    assert missing_key_msg["params"]["key"] == "func_undocumented"

    # Verify the simple "untracked" message was NOT called
    assert not any(msg["id"] == str(L.check.file.untracked) for msg in messages)


def test_check_reports_simple_untracked_if_all_docs_present(tmp_path, monkeypatch):
    """
    Verifies that 'check' falls back to the simple UNTRACKED message if
    a new file has content, but all its public APIs already have docstrings
    (i.e., it just needs to be hydrated).
    """
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", 'def new_func():\n    """Docstring present."""')
        .build()
    )

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        app.run_check()

    # Assert the simple message was called
    spy_bus.assert_id_called(L.check.file.untracked, level="warning")
    # Assert the detailed message was NOT called
    messages = spy_bus.get_messages()
    assert not any(
        msg["id"] == str(L.check.file.untracked_with_details) for msg in messages
    )


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

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        success = app.run_check()

    # 3. Assert
    assert success is True
    spy_bus.assert_id_called(L.check.run.success, level="success")
    messages = spy_bus.get_messages()
    assert not any(msg["id"] == str(L.check.file.untracked) for msg in messages)


def test_check_is_silent_for_boilerplate_untracked_file(tmp_path, monkeypatch):
    """
    Verifies that 'check' also ignores untracked files that only contain
    boilerplate like __all__ or __path__.
    """
    # 1. Arrange: A source file with only boilerplate, and no doc file
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(
            "src/namespace/__init__.py",
            """
            __path__ = __import__("pkgutil").extend_path(__path__, __name__)
            __all__ = ["some_module"]
            """,
        )
        .build()
    )

    app = create_test_app(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        success = app.run_check()

    # 3. Assert
    assert success is True
    spy_bus.assert_id_called(L.check.run.success, level="success")
    messages = spy_bus.get_messages()
    assert not any(msg["id"] == str(L.check.file.untracked) for msg in messages)
