import pytest
from typing import List
from stitcher.test_utils import create_test_app
from stitcher.app.protocols import InteractionHandler, InteractionContext
from stitcher.spec import ResolutionAction
from stitcher.test_utils import WorkspaceFactory, SpyBus
from needle.pointer import L


class MockResolutionHandler(InteractionHandler):
    """A handler that returns a pre-defined sequence of actions for testing."""

    def __init__(self, actions: List[ResolutionAction]):
        self.actions = actions
        self.called_with: List[InteractionContext] = []

    def process_interactive_session(
        self, contexts: List[InteractionContext]
    ) -> List[ResolutionAction]:
        self.called_with = contexts
        # Return the same action for all conflicts if only one is provided
        if len(self.actions) == 1:
            return self.actions * len(contexts)
        return self.actions


@pytest.fixture
def conflicting_workspace(tmp_path):
    """Creates a workspace with a doc content conflict."""
    factory = WorkspaceFactory(tmp_path)
    return (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/app.py", 'def func():\n    """Code Doc"""')
        .with_docs("src/app.stitcher.yaml", {"func": "YAML Doc"})
        .build()
    )


def test_pump_interactive_overwrite(conflicting_workspace, monkeypatch):
    """
    Verify that choosing [F]orce-hydrate (HYDRATE_OVERWRITE) correctly
    updates the YAML file with the content from the source code.
    """
    # 1. Arrange: Inject a handler that simulates choosing 'Force-hydrate'
    handler = MockResolutionHandler([ResolutionAction.HYDRATE_OVERWRITE])
    app = create_test_app(root_path=conflicting_workspace, interaction_handler=handler)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        result = app.run_pump()

    # 3. Assert
    assert result.success is True, (
        "Pumping should succeed after interactive resolution."
    )
    spy_bus.assert_id_called(L.pump.file.success, level="success")

    # Verify file content was updated
    doc_file = conflicting_workspace / "src/app.stitcher.yaml"
    content = doc_file.read_text(encoding="utf-8")
    assert "Code Doc" in content
    assert "YAML Doc" not in content


def test_pump_interactive_reconcile(conflicting_workspace, monkeypatch):
    """
    Verify that choosing [R]econcile (HYDRATE_KEEP_EXISTING) preserves
    the existing content in the YAML file.
    """
    # 1. Arrange: Inject a handler that simulates choosing 'Reconcile'
    handler = MockResolutionHandler([ResolutionAction.HYDRATE_KEEP_EXISTING])
    app = create_test_app(root_path=conflicting_workspace, interaction_handler=handler)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        result = app.run_pump()

    # 3. Assert
    assert result.success is True
    spy_bus.assert_id_called(L.pump.info.reconciled, level="info")
    spy_bus.assert_id_called(L.pump.run.no_changes, level="info")

    # Verify file content was NOT changed
    doc_file = conflicting_workspace / "src/app.stitcher.yaml"
    content = doc_file.read_text(encoding="utf-8")
    assert "YAML Doc" in content
    assert "Code Doc" not in content


def test_pump_interactive_skip_leads_to_failure(conflicting_workspace, monkeypatch):
    """
    Verify that choosing [S]kip leaves the conflict unresolved and causes
    the command to fail.
    """
    # 1. Arrange: Inject a handler that simulates choosing 'Skip'
    handler = MockResolutionHandler([ResolutionAction.SKIP])
    app = create_test_app(root_path=conflicting_workspace, interaction_handler=handler)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        result = app.run_pump()

    # 3. Assert
    assert result.success is False, "Pumping should fail if conflicts are skipped."
    spy_bus.assert_id_called(L.pump.error.conflict, level="error")
    spy_bus.assert_id_called(L.pump.run.conflict, level="error")

    # Verify file content was NOT changed
    doc_file = conflicting_workspace / "src/app.stitcher.yaml"
    content = doc_file.read_text(encoding="utf-8")
    assert "YAML Doc" in content


def test_pump_interactive_abort_stops_process(conflicting_workspace, monkeypatch):
    """
    Verify that choosing [A]bort stops the pumping and fails the command.
    """
    # 1. Arrange: Inject a handler that simulates choosing 'Abort'
    handler = MockResolutionHandler([ResolutionAction.ABORT])
    app = create_test_app(root_path=conflicting_workspace, interaction_handler=handler)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        result = app.run_pump()

    # 3. Assert
    assert result.success is False
    # Assert that the correct semantic 'aborted' message was sent.
    spy_bus.assert_id_called(L.pump.run.aborted, level="error")

    # Verify file content was NOT changed
    doc_file = conflicting_workspace / "src/app.stitcher.yaml"
    content = doc_file.read_text(encoding="utf-8")
    assert "YAML Doc" in content
