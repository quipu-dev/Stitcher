import pytest
from typer.testing import CliRunner

from stitcher.cli.main import app
from stitcher.test_utils import WorkspaceFactory, SpyBus
from needle.pointer import L, SemanticPointer

runner = CliRunner()


@pytest.fixture
def workspace_factory(tmp_path, monkeypatch):
    # Use a fixture to ensure a clean workspace and chdir for each test
    factory = WorkspaceFactory(tmp_path).init_git()
    monkeypatch.chdir(tmp_path)
    return factory


def assert_id_not_called(spy_bus: SpyBus, msg_id: SemanticPointer):
    """Helper to assert that a specific message ID was NOT called."""
    key = str(msg_id)
    for msg in spy_bus.get_messages():
        if msg["id"] == key:
            raise AssertionError(f"Message with ID '{key}' was unexpectedly sent.")


def test_loglevel_default_is_info(workspace_factory, monkeypatch):
    """Verifies the default loglevel (info) shows INFO and above, but not DEBUG."""
    workspace_factory.with_config({"scan_paths": ["src"]}).build()
    spy_bus = SpyBus()

    with spy_bus.patch(monkeypatch):
        result = runner.invoke(app, ["check"], catch_exceptions=False)

    assert result.exit_code == 0
    spy_bus.assert_id_called(L.index.run.start, level="info")
    spy_bus.assert_id_called(L.check.run.success, level="success")
    assert_id_not_called(spy_bus, L.debug.log.scan_path)


def test_loglevel_warning_hides_info_and_success(workspace_factory, monkeypatch):
    """Verifies --loglevel warning hides lower level messages."""
    # Setup a project with an untracked file, which triggers a WARNING
    workspace_factory.with_config({"scan_paths": ["src"]}).with_source(
        "src/main.py", "def func(): pass"
    ).build()
    spy_bus = SpyBus()

    with spy_bus.patch(monkeypatch):
        result = runner.invoke(
            app, ["--loglevel", "warning", "check"], catch_exceptions=False
        )

    # A warning does not cause a failure exit code
    assert result.exit_code == 0
    # INFO and the final SUCCESS summary should be hidden
    assert_id_not_called(spy_bus, L.index.run.start)
    assert_id_not_called(spy_bus, L.check.run.success)
    assert_id_not_called(spy_bus, L.check.run.success_with_warnings)

    # However, the specific WARNING messages should be visible.
    spy_bus.assert_id_called(L.check.file.warn, level="warning")
    spy_bus.assert_id_called(L.check.file.untracked_with_details, level="warning")


def test_loglevel_debug_shows_debug_messages(workspace_factory, monkeypatch):
    """Verifies --loglevel debug shows verbose debug messages."""
    workspace_factory.with_config({"scan_paths": ["src"]}).build()
    spy_bus = SpyBus()

    with spy_bus.patch(monkeypatch):
        result = runner.invoke(
            app, ["--loglevel", "debug", "check"], catch_exceptions=False
        )

    assert result.exit_code == 0
    spy_bus.assert_id_called(L.debug.log.scan_path, level="debug")
    spy_bus.assert_id_called(L.index.run.start, level="info")


def test_loglevel_error_shows_only_errors(workspace_factory, monkeypatch):
    """Verifies --loglevel error hides everything except errors."""
    # Setup a project with signature drift (ERROR) and an untracked file (WARNING)
    ws = workspace_factory.with_config({"scan_paths": ["src"]})
    ws.with_source("src/main.py", 'def func(a: int): """doc"""')
    ws.build()
    runner.invoke(app, ["init"], catch_exceptions=False)
    # Introduce signature drift
    (ws.root_path / "src/main.py").write_text('def func(a: str): """doc"""')
    # Add an untracked file to ensure its warning is suppressed
    (ws.root_path / "src/untracked.py").write_text("pass")
    spy_bus = SpyBus()

    with spy_bus.patch(monkeypatch):
        result = runner.invoke(
            app, ["--loglevel", "error", "check"], catch_exceptions=False
        )

    assert result.exit_code == 1
    # INFO, SUCCESS, WARNING messages should be hidden
    assert_id_not_called(spy_bus, L.index.run.start)
    assert_id_not_called(spy_bus, L.check.run.success)
    assert_id_not_called(spy_bus, L.check.file.untracked)

    # ERROR messages should be visible
    spy_bus.assert_id_called(L.check.run.fail, level="error")
    spy_bus.assert_id_called(L.check.state.signature_drift, level="error")
