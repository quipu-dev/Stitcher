import json
from pathlib import Path
from stitcher.spec import ModuleDef, FunctionDef, Argument, ArgumentKind
from stitcher.app.services import SignatureManager

def create_func(name = "func", args = None, ret = None):
    """Helper to create a FunctionDef."""
    ...

def test_fingerprint_stability():
    """Test that compute_fingerprint is deterministic and sensitive to changes."""
    ...

def test_manager_save_and_load(tmp_path: Path):
    """Test that SignatureManager correctly persists fingerprints to JSON."""
    ...

def test_manager_check_detects_mismatch(tmp_path: Path):
    """Test that check_signatures logic correctly identifies differences."""
    ...