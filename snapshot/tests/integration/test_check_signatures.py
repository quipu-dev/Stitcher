from stitcher.app import StitcherApp
from stitcher.needle import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def test_check_detects_signature_change(tmp_path, monkeypatch):
    """
    End-to-End test verifying that modifying a function signature
    triggers a check failure/warning.
    """
    # 1. Setup Initial Workspace
    factory = WorkspaceFactory(tmp_path)
    # Define a simple function with one argument
    initial_code = """
    def process(value: int) -> int:
        \"\"\"Process an integer.\"\"\"
        return value * 2
    """
    
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/processor.py", initial_code)
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Run Init (This should establish the baseline signatures)
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        app.run_init()
        
    # Verify init was successful
    spy_bus.assert_id_called(L.init.run.complete, level="success")
    
    # 3. Modify Code (Change argument type int -> str)
    modified_code = """
    def process(value: str) -> int:
        \"\"\"Process a string (Changed).\"\"\"
        return len(value) * 2
    """
    (project_root / "src/processor.py").write_text(modified_code, encoding="utf-8")
    
    # Clear previous messages
    spy_bus = SpyBus()
    
    # 4. Run Check
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_check()
        
    # 5. Assertions
    # Check should report failure (or at least issues found)
    assert success is False
    
    # Verify the specific mismatch message was fired
    spy_bus.assert_id_called(L.check.issue.mismatch, level="error")
    
    # Verify we specifically complained about 'process'
    mismatch_msgs = [
        m for m in spy_bus.get_messages() 
        if str(L.check.issue.mismatch) == m["id"]
    ]
    assert len(mismatch_msgs) == 1
    assert mismatch_msgs[0]["params"]["key"] == "process"


def test_generate_updates_signatures(tmp_path, monkeypatch):
    """
    Verify that running 'generate' updates the signature baseline,
    so subsequent checks pass.
    """
    # 1. Setup Workspace
    factory = WorkspaceFactory(tmp_path)
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
    with SpyBus().patch(monkeypatch, "stitcher.app.core.bus"):
        app.run_from_config()
        
    # 5. Run Check (Should now pass because baseline was updated)
    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_check()
        
    assert success is True
    spy_bus.assert_id_called(L.check.run.success, level="success")