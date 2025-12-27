from textwrap import dedent
from stitcher.app import StitcherApp
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def _assert_no_errors(spy_bus):
    errors = [m for m in spy_bus.get_messages() if m["level"] == "error"]
    assert not errors, f"Unexpected errors: {errors}"


def test_check_detects_signature_change(tmp_path, monkeypatch):
    """
    End-to-End test verifying that modifying a function signature
    triggers a check failure/warning.
    """
    # 1. Setup Initial Workspace
    factory = WorkspaceFactory(tmp_path)
    # Use dedent to ensure clean indentation
    initial_code = dedent("""
    def process(value: int) -> int:
        \"\"\"Process an integer.\"\"\"
        return value * 2
    """).strip()

    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/processor.py", initial_code)
        .build()
    )

    app = StitcherApp(root_path=project_root)

    # 2. Run Init (Baseline)
    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        app.run_init()

    _assert_no_errors(spy_bus)
    spy_bus.assert_id_called(L.init.run.complete, level="success")

    # Verify fingerprint file exists
    sig_file = project_root / ".stitcher/signatures/src/processor.json"
    assert sig_file.exists(), "Fingerprint file was not created during Init"

    # 3. Modify Code
    modified_code = dedent("""
    def process(value: str) -> int:
        \"\"\"Process a string (Changed).\"\"\"
        return len(value) * 2
    """).strip()
    (project_root / "src/processor.py").write_text(modified_code, encoding="utf-8")

    # 4. Run Check
    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_check()

    # 5. Assertions
    assert success is False, (
        "Check passed but should have failed due to signature mismatch"
    )
    spy_bus.assert_id_called(L.check.issue.mismatch, level="error")


def test_generate_does_not_update_signatures(tmp_path, monkeypatch):
    """
    Verify that running 'generate' is now pure and DOES NOT update the signature baseline.
    """
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", "def func(a: int): ...")
        .with_docs("src/main.stitcher.yaml", {"func": "doc"})
        .build()
    )
    app = StitcherApp(root_path=project_root)

    # 1. Run Init to set baseline
    with SpyBus().patch(monkeypatch, "stitcher.app.core.bus"):
        app.run_init()

    # 2. Modify Code
    (project_root / "src/main.py").write_text("def func(a: str): ...")

    # 3. Run Generate
    with SpyBus().patch(monkeypatch, "stitcher.app.core.bus"):
        app.run_from_config()

    # 4. Run Check - it should now FAIL because generate did not update anything.
    spy_bus_check = SpyBus()
    with spy_bus_check.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_check()

    assert not success, "Check passed, but it should have failed."
    spy_bus_check.assert_id_called(L.check.issue.mismatch, level="error")


def test_check_with_update_signatures_flag_reconciles_changes(tmp_path, monkeypatch):
    """
    Verify the complete workflow of reconciling signature changes with `check --update-signatures`.
    """
    # 1. Arrange: Setup and Init to establish a baseline.
    # CRITICAL: The source MUST have a docstring so 'init' creates the tracking file (.stitcher.yaml).
    # If the file is untracked, 'check' skips signature verification!
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", 'def func(a: int):\n    """Doc."""\n    ...')
        .build()
    )
    app = StitcherApp(root_path=project_root)
    with SpyBus().patch(monkeypatch, "stitcher.app.core.bus"):
        app.run_init()

    # 2. Modify the code to create a signature mismatch.
    # CRITICAL: Do NOT include the docstring here. If we do, 'check' will report a
    # REDUNDANT warning (because docs exist in both code and YAML), causing the
    # final result to be 'success_with_warnings' instead of 'success'.
    # We want a clean state where docs are only in YAML.
    (project_root / "src/main.py").write_text("def func(a: str):\n    ...")

    # 3. Act I: Run check with the --update-signatures flag
    spy_bus_reconcile = SpyBus()
    with spy_bus_reconcile.patch(monkeypatch, "stitcher.app.core.bus"):
        success_reconcile = app.run_check(update_signatures=True)

    # 4. Assert I: The reconciliation check should succeed and report the update
    assert success_reconcile is True, "Check with --update-signatures failed"
    spy_bus_reconcile.assert_id_called(L.check.run.signatures_updated, level="success")
    # Crucially, it should NOT have reported a mismatch error
    mismatch_errors = [
        m for m in spy_bus_reconcile.get_messages() if m["id"] == str(L.check.issue.mismatch)
    ]
    assert not mismatch_errors, "Mismatch error was reported during reconciliation"

    # 5. Act II: Run a normal check again to verify the baseline was updated
    spy_bus_verify = SpyBus()
    with spy_bus_verify.patch(monkeypatch, "stitcher.app.core.bus"):
        success_verify = app.run_check()

    # 6. Assert II: The verification check should now pass cleanly
    assert success_verify is True, "Verification check failed after reconciliation"
    spy_bus_verify.assert_id_called(L.check.run.success, level="success")
