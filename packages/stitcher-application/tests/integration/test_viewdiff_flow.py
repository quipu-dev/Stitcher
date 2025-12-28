from typing import List
from stitcher.app import StitcherApp
from stitcher.app.protocols import InteractionHandler, InteractionContext
from stitcher.spec import ResolutionAction, ConflictType
from stitcher.test_utils import WorkspaceFactory, SpyBus


class CapturingHandler(InteractionHandler):
    """A handler that captures the contexts passed to it and returns SKIP."""

    def __init__(self):
        self.captured_contexts: List[InteractionContext] = []

    def process_interactive_session(
        self, contexts: List[InteractionContext]
    ) -> List[ResolutionAction]:
        self.captured_contexts.extend(contexts)
        return [ResolutionAction.SKIP] * len(contexts)


def test_check_generates_signature_diff(tmp_path, monkeypatch):
    """
    Verifies that when a signature changes, 'check' generates a unified diff
    and passes it in the InteractionContext.
    """
    # 1. Arrange: Init project with baseline
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", "def func(a: int): ...")
        .build()
    )

    # Run init to save baseline signature and TEXT
    app_init = StitcherApp(root_path=project_root)
    with SpyBus().patch(monkeypatch, "stitcher.app.core.bus"):
        app_init.run_init()

    # 2. Modify code to cause signature drift
    (project_root / "src/main.py").write_text("def func(a: str): ...", encoding="utf-8")

    # 3. Run check with capturing handler
    handler = CapturingHandler()
    app_check = StitcherApp(root_path=project_root, interaction_handler=handler)

    with SpyBus().patch(monkeypatch, "stitcher.app.core.bus"):
        app_check.run_check()

    # 4. Assert
    assert len(handler.captured_contexts) == 1
    ctx = handler.captured_contexts[0]

    assert ctx.conflict_type == ConflictType.SIGNATURE_DRIFT
    assert ctx.signature_diff is not None

    # Check for unified diff markers
    assert "--- baseline" in ctx.signature_diff
    assert "+++ current" in ctx.signature_diff
    assert "-def func(a: int):" in ctx.signature_diff
    assert "+def func(a: str):" in ctx.signature_diff


def test_pump_generates_doc_diff(tmp_path, monkeypatch):
    """
    Verifies that when doc content conflicts, 'pump' generates a unified diff
    and passes it in the InteractionContext.
    """
    # 1. Arrange: Project with conflicting docs
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", 'def func():\n    """Code Doc"""\n    pass')
        .with_docs("src/main.stitcher.yaml", {"func": "YAML Doc"})
        .build()
    )

    # 2. Run pump with capturing handler
    handler = CapturingHandler()
    app_pump = StitcherApp(root_path=project_root, interaction_handler=handler)

    with SpyBus().patch(monkeypatch, "stitcher.app.core.bus"):
        app_pump.run_pump()

    # 3. Assert
    assert len(handler.captured_contexts) == 1
    ctx = handler.captured_contexts[0]

    assert ctx.conflict_type == ConflictType.DOC_CONTENT_CONFLICT
    assert ctx.doc_diff is not None

    # Check for unified diff markers
    assert "--- yaml" in ctx.doc_diff
    assert "+++ code" in ctx.doc_diff
    assert "-YAML Doc" in ctx.doc_diff
    assert "+Code Doc" in ctx.doc_diff
