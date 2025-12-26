from pathlib import Path
from stitcher.spec import ModuleDef, FunctionDef
from stitcher.app.services import DocumentManager
from stitcher.io import YamlAdapter

def test_apply_docs_overlay(tmp_path: Path):
    """Verifies that external docs overwrite source docs in the IR."""
    ...

def test_apply_docs_partial_overlay(tmp_path: Path):
    """Verifies that if a key is missing in YAML, source doc is preserved."""
    ...