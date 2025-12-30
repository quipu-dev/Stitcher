from textwrap import dedent
from stitcher.test_utils import create_test_app
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
    factory = WorkspaceFactory(tmp_path)
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

    app = create_test_app(root_path=project_root)

    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        app.run_init()

    _assert_no_errors(spy_bus)
    spy_bus.assert_id_called(L.init.run.complete, level="success")

    # Modify Code: Change signature AND remove docstring
    modified_code = dedent("""
    def process(value: str) -> int:
        return len(value) * 2
    """).strip()
    (project_root / "src/processor.py").write_text(modified_code, encoding="utf-8")

    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        success = app.run_check()

    assert success is False
    spy_bus.assert_id_called(L.check.state.signature_drift, level="error")


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
    app = create_test_app(root_path=project_root)

    with SpyBus().patch(monkeypatch, "stitcher.common.bus"):
        app.run_init()

    (project_root / "src/main.py").write_text("def func(a: str): ...")

    with SpyBus().patch(monkeypatch, "stitcher.common.bus"):
        app.run_from_config()

    spy_bus_check = SpyBus()
    with spy_bus_check.patch(monkeypatch, "stitcher.common.bus"):
        success = app.run_check()

    assert not success, "Check passed, but it should have failed."
    spy_bus_check.assert_id_called(L.check.state.signature_drift, level="error")


def test_check_with_force_relink_reconciles_changes(tmp_path, monkeypatch):
    """
    Verify the complete workflow of reconciling signature changes with `check --force-relink`.
    """
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", 'def func(a: int):\n    """Doc."""\n    ...')
        .build()
    )
    app = create_test_app(root_path=project_root)
    with SpyBus().patch(monkeypatch, "stitcher.common.bus"):
        app.run_init()

    # Modify: Change signature, remove doc to be clean
    (project_root / "src/main.py").write_text("def func(a: str):\n    ...")

    spy_bus_reconcile = SpyBus()
    with spy_bus_reconcile.patch(monkeypatch, "stitcher.common.bus"):
        success_reconcile = app.run_check(force_relink=True)

    assert success_reconcile is True, "Check with --force-relink failed"
    spy_bus_reconcile.assert_id_called(L.check.state.relinked, level="success")

    spy_bus_verify = SpyBus()
    with spy_bus_verify.patch(monkeypatch, "stitcher.common.bus"):
        success_verify = app.run_check()

    assert success_verify is True, "Verification check failed after reconciliation"
    spy_bus_verify.assert_id_called(L.check.run.success, level="success")
