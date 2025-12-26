from textwrap import dedent
from stitcher.app import StitcherApp
from stitcher.needle import L
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
    assert success is False, "Check passed but should have failed due to signature mismatch"
    spy_bus.assert_id_called(L.check.issue.mismatch, level="error")


def test_generate_updates_signatures(tmp_path, monkeypatch):
    """
    Verify that running 'generate' updates the signature baseline.
    """
    # 1. Setup Workspace
    factory = WorkspaceFactory(tmp_path)
    # Simple one-liner to avoid any parsing ambiguity
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", "def func(a: int): ...")
        .with_docs("src/main.stitcher.yaml", {"func": "doc"})
        .build()
    )
    
    app = StitcherApp(root_path=project_root)
    
    # 2. Run Init
    with SpyBus().patch(monkeypatch, "stitcher.app.core.bus"):
        app.run_init()
        
    # 3. Modify Code
    (project_root / "src/main.py").write_text("def func(a: str): ...", encoding="utf-8")
    
    # 4. Run Generate (Should update signatures)
    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        app.run_from_config()
        
    _assert_no_errors(spy_bus)
    spy_bus.assert_id_called(L.generate.run.complete, level="success")
    
    # Verify fingerprint file timestamp or content? 
    # Better to verify via Check.
    
    # 5. Run Check (Should now pass)
    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_check()
        
    assert success is True, "Check failed but should have passed after Generate"
    spy_bus.assert_id_called(L.check.run.success, level="success")