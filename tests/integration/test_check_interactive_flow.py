from typing import List
from stitcher.app import StitcherApp
from stitcher.app.protocols import InteractionHandler, InteractionContext
from stitcher.spec import ResolutionAction
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

    app_for_init = StitcherApp(root_path=project_root)
    with SpyBus().patch(monkeypatch, "stitcher.app.core.bus"):
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
    app = StitcherApp(root_path=project_root, interaction_handler=handler)

    # 4. Run Check
    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
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
