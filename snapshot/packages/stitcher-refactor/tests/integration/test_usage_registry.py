from pathlib import Path
from stitcher.refactor.engine.graph import SemanticGraph, UsageLocation

def test_usage_registry_resolution(tmp_path):
    # Setup:
    # mypkg/
    #   __init__.py
    #   core.py -> defines `Helper`
    #   app.py  -> imports `Helper` as `H`, uses `H()`
    
    pkg_dir = tmp_path / "mypkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    
    # core.py
    (pkg_dir / "core.py").write_text(
        "class Helper:\n    pass", 
        encoding="utf-8"
    )
    
    # app.py
    # We import Helper as H, then instantiate it.
    # The registry should map the usage of 'H' in app.py to 'mypkg.core.Helper'
    (pkg_dir / "app.py").write_text(
        "from mypkg.core import Helper as H\n\ndef main():\n    obj = H()", 
        encoding="utf-8"
    )
    
    # Execute
    graph = SemanticGraph(root_path=tmp_path)
    graph.load("mypkg")
    
    # Verify
    # We want to find usages of 'mypkg.core.Helper'
    usages = graph.registry.get_usages("mypkg.core.Helper")
    
    # Debug info
    print(f"Usages found: {usages}")
    
    # We expect usages in:
    # 1. app.py (the import statement "Helper as H" - handled by Griffe Alias scan?)
    #    Actually our _scan_module_usages scans Name nodes.
    #    The import statement creates the alias 'H'.
    #    The UsageVisitor sees 'H' in 'obj = H()' and resolves it to 'mypkg.core.Helper'.
    
    # Let's check if we caught the usage in `main`
    app_usage = next((u for u in usages if u.file_path.name == "app.py" and u.lineno == 4), None)
    
    assert app_usage is not None, "Failed to find usage of H() in app.py"
    assert app_usage.col_offset == 10  # "    obj = H()" -> H starts at index 10
    
    # Also, we implicitly registered the definition in core.py? 
    # _scan_module_usages registers local definitions too.
    # So 'class Helper' in core.py should also be a usage of 'mypkg.core.Helper' (definition is a usage)
    core_usage = next((u for u in usages if u.file_path.name == "core.py"), None)
    assert core_usage is not None