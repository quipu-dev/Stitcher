import pytest
import yaml
from typing import List
from stitcher.test_utils import create_test_app
from stitcher.app.protocols import InteractionHandler, InteractionContext
from stitcher.spec import ResolutionAction, ConflictType
from stitcher.test_utils import WorkspaceFactory, SpyBus, get_stored_hashes
from needle.pointer import L


class MockResolutionHandler(InteractionHandler):
    """A handler that returns a pre-defined sequence of actions."""

    def __init__(self, actions: List[ResolutionAction]):
        self.actions = actions
        self.called_with: List[InteractionContext] = []

    def process_interactive_session(
        self, contexts: List[InteractionContext]
    ) -> List[ResolutionAction]:
        self.called_with = contexts
        # Return the pre-programmed sequence of actions
        return self.actions * len(contexts) if len(self.actions) == 1 else self.actions


def test_check_workflow_mixed_auto_and_interactive(tmp_path, monkeypatch):
    """
    Ensures that auto-reconciliation and interactive decisions can co-exist
    and are executed correctly in their respective phases.
    """
    factory = WorkspaceFactory(tmp_path)
    # 1. Setup: A module with two functions
    # func_a: will have doc improvement (auto)
    # func_b: will have signature drift (interactive)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(
            "src/app.py",
            '''
def func_a():
    """Old Doc A."""
    pass
def func_b(x: int):
    """Doc B."""
    pass
''',
        )
        .build()
    )

    app_for_init = create_test_app(root_path=project_root)
    with SpyBus().patch(monkeypatch, "stitcher.common.bus"):
        app_for_init.run_init()

    # 2. Trigger Changes
    # Change A: Modify YAML directly (Doc Improvement)
    doc_file = project_root / "src/app.stitcher.yaml"
    doc_file.write_text('func_a: "New Doc A."\nfunc_b: "Doc B."\n', encoding="utf-8")

    # Change B: Modify Source Code (Signature Drift)
    (project_root / "src/app.py").write_text("""
def func_a():
    pass
def func_b(x: str): # int -> str
    pass
""")

    # 3. Define Interactive Decision and inject Handler
    handler = MockResolutionHandler([ResolutionAction.RELINK])
    app = create_test_app(root_path=project_root, interaction_handler=handler)

    # 4. Run Check
    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        success = app.run_check()

    # 5. Assertions
    assert success is True
    # Verify Auto-reconcile report for func_a
    doc_updated_msg = next(
        (
            m
            for m in spy_bus.get_messages()
            if m["id"] == str(L.check.state.doc_updated)
        ),
        None,
    )
    assert doc_updated_msg is not None
    assert doc_updated_msg["params"]["key"] == "func_a"

    # Verify Interactive resolution report for func_b
    spy_bus.assert_id_called(L.check.state.relinked, level="success")

    # Verify Hashes are actually updated in storage
    final_hashes = get_stored_hashes(project_root, "src/app.py")

    # func_a should have updated yaml hash
    expected_doc_a_hash = app.doc_manager.compute_yaml_content_hash("New Doc A.")
    assert final_hashes["func_a"]["baseline_yaml_content_hash"] == expected_doc_a_hash

    # func_b should have updated code hash due to RELINK
    assert "baseline_code_structure_hash" in final_hashes["func_b"]
    assert final_hashes["func_b"]["baseline_code_structure_hash"] is not None


@pytest.fixture
def dangling_doc_workspace(tmp_path):
    """Creates a workspace with a doc file containing an extra key."""
    factory = WorkspaceFactory(tmp_path)
    return (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/app.py", "def func_a(): pass")
        .with_docs(
            "src/app.stitcher.yaml",
            {"func_a": "Doc A.", "dangling_func": "This one is extra."},
        )
        .build()
    )


def test_check_interactive_purge_removes_dangling_doc(
    dangling_doc_workspace, monkeypatch
):
    """
    Verify that choosing [P]urge correctly removes the dangling entry from the YAML file.
    """
    # 1. Arrange: Inject a handler that simulates choosing 'Purge'
    handler = MockResolutionHandler([ResolutionAction.PURGE_DOC])
    app = create_test_app(root_path=dangling_doc_workspace, interaction_handler=handler)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        success = app.run_check()

    # 3. Assert
    assert success is True, "Check should succeed after interactive purge."

    # Assert correct context was passed to handler
    assert len(handler.called_with) == 1
    assert handler.called_with[0].fqn == "dangling_func"
    assert handler.called_with[0].conflict_type == ConflictType.DANGLING_DOC

    # Assert correct bus message was sent
    spy_bus.assert_id_called(L.check.state.purged, level="success")

    # Assert YAML file was modified
    doc_file = dangling_doc_workspace / "src/app.stitcher.yaml"
    with doc_file.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "dangling_func" not in data
    assert "func_a" in data

    # A subsequent check should be clean
    app_verify = create_test_app(root_path=dangling_doc_workspace)
    spy_verify = SpyBus()
    with spy_verify.patch(monkeypatch, "stitcher.common.bus"):
        assert app_verify.run_check() is True
    spy_verify.assert_id_called(L.check.run.success)


def test_check_interactive_skip_dangling_doc_fails(dangling_doc_workspace, monkeypatch):
    """
    Verify that skipping a dangling doc conflict results in a check failure.
    """
    # 1. Arrange: Handler simulates choosing 'Skip'
    handler = MockResolutionHandler([ResolutionAction.SKIP])
    app = create_test_app(root_path=dangling_doc_workspace, interaction_handler=handler)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        success = app.run_check()

    # 3. Assert
    assert success is False
    spy_bus.assert_id_called(L.check.issue.extra, level="error")
    spy_bus.assert_id_called(L.check.run.fail, level="error")

    # Assert YAML was not changed
    doc_file = dangling_doc_workspace / "src/app.stitcher.yaml"
    with doc_file.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert "dangling_func" in data


def test_check_interactive_purge_deletes_empty_yaml(tmp_path, monkeypatch):
    """
    Verify that if purging the last entry makes the YAML file empty, the file is deleted.
    """
    # 1. Arrange: Workspace with only a dangling doc
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/app.py", "")
        .with_docs("src/app.stitcher.yaml", {"dangling": "doc"})
        .build()
    )
    doc_file = project_root / "src/app.stitcher.yaml"
    assert doc_file.exists()

    handler = MockResolutionHandler([ResolutionAction.PURGE_DOC])
    app = create_test_app(root_path=project_root, interaction_handler=handler)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        success = app.run_check()

    # 3. Assert
    assert success is True
    spy_bus.assert_id_called(L.check.state.purged, level="success")
    assert not doc_file.exists(), (
        "YAML file should have been deleted after last entry was purged."
    )


# --- Test Suite for Signature Drift ---


@pytest.fixture
def drift_workspace(tmp_path):
    """Creates a workspace with a signature drift conflict."""
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/app.py", "def func(a: int): ...")
        .with_docs("src/app.stitcher.yaml", {"func": "Doc"})
        .build()
    )
    # Run init to create baseline
    app = create_test_app(root_path=project_root)
    app.run_init()
    # Introduce drift
    (project_root / "src/app.py").write_text("def func(a: str): ...")
    return project_root


def test_check_interactive_relink_fixes_drift(drift_workspace, monkeypatch):
    handler = MockResolutionHandler([ResolutionAction.RELINK])
    app = create_test_app(root_path=drift_workspace, interaction_handler=handler)
    spy_bus = SpyBus()

    initial_hashes = get_stored_hashes(drift_workspace, "src/app.py")

    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        assert app.run_check() is True

    spy_bus.assert_id_called(L.check.state.relinked, level="success")

    final_hashes = get_stored_hashes(drift_workspace, "src/app.py")
    assert (
        final_hashes["func"]["baseline_code_structure_hash"]
        != initial_hashes["func"]["baseline_code_structure_hash"]
    )

    # Verify that a subsequent check is clean
    app_verify = create_test_app(root_path=drift_workspace)
    spy_verify = SpyBus()
    with spy_verify.patch(monkeypatch, "stitcher.common.bus"):
        assert app_verify.run_check() is True
    spy_verify.assert_id_called(L.check.run.success)


def test_check_interactive_skip_drift_fails_check(drift_workspace, monkeypatch):
    handler = MockResolutionHandler([ResolutionAction.SKIP])
    app = create_test_app(root_path=drift_workspace, interaction_handler=handler)
    spy_bus = SpyBus()

    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        assert app.run_check() is False

    spy_bus.assert_id_called(L.check.state.signature_drift, level="error")
    spy_bus.assert_id_called(L.check.run.fail, level="error")


# --- Test Suite for Co-Evolution ---


@pytest.fixture
def co_evolution_workspace(tmp_path):
    """Creates a workspace with a co-evolution conflict."""
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/app.py", "def func(a: int): ...")
        .with_docs("src/app.stitcher.yaml", {"func": "Old Doc"})
        .build()
    )
    app = create_test_app(root_path=project_root)
    app.run_init()
    # Introduce co-evolution
    (project_root / "src/app.py").write_text("def func(a: str): ...")
    (project_root / "src/app.stitcher.yaml").write_text('func: "New Doc"')
    return project_root


def test_check_interactive_reconcile_fixes_co_evolution(
    co_evolution_workspace, monkeypatch
):
    handler = MockResolutionHandler([ResolutionAction.RECONCILE])
    app = create_test_app(root_path=co_evolution_workspace, interaction_handler=handler)
    spy_bus = SpyBus()

    initial_hashes = get_stored_hashes(co_evolution_workspace, "src/app.py")

    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        assert app.run_check() is True

    spy_bus.assert_id_called(L.check.state.reconciled, level="success")

    final_hashes = get_stored_hashes(co_evolution_workspace, "src/app.py")
    assert (
        final_hashes["func"]["baseline_code_structure_hash"]
        != initial_hashes["func"]["baseline_code_structure_hash"]
    )
    assert (
        final_hashes["func"]["baseline_yaml_content_hash"]
        != initial_hashes["func"]["baseline_yaml_content_hash"]
    )

    # Verify that a subsequent check is clean
    app_verify = create_test_app(root_path=co_evolution_workspace)
    spy_verify = SpyBus()
    with spy_verify.patch(monkeypatch, "stitcher.common.bus"):
        assert app_verify.run_check() is True
    spy_verify.assert_id_called(L.check.run.success)


def test_check_interactive_skip_co_evolution_fails_check(
    co_evolution_workspace, monkeypatch
):
    handler = MockResolutionHandler([ResolutionAction.SKIP])
    app = create_test_app(root_path=co_evolution_workspace, interaction_handler=handler)
    spy_bus = SpyBus()

    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        assert app.run_check() is False

    spy_bus.assert_id_called(L.check.state.co_evolution, level="error")
    spy_bus.assert_id_called(L.check.run.fail, level="error")
