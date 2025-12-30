from textwrap import dedent
from pathlib import Path
from stitcher.test_utils import create_test_app
from stitcher.test_utils import WorkspaceFactory, SpyBus, get_stored_hashes
from needle.pointer import L


def test_check_persists_updates_in_multi_target_scan(tmp_path: Path, monkeypatch):
    """
    Regression Test: Ensures that 'doc_improvement' updates are persisted for ALL files,
    not just those in the last scanned batch.

    This simulates a bug where 'modules' variable scope in the loop caused early batches
    to be ignored during the execution phase.
    """
    # 1. Setup a workspace with two targets (pkg1 and pkg2)
    # pkg1 will be scanned FIRST. pkg2 SECOND.
    # We will trigger a doc improvement in pkg1.

    factory = WorkspaceFactory(tmp_path)

    # pkg1: Has a function with matching code/doc initially
    factory.with_source(
        "src/pkg1/mod.py",
        """
def func():
    \"\"\"Doc.\"\"\"
    pass
""",
    )
    factory.with_docs(
        "src/pkg1/mod.stitcher.yaml", {"func": "Doc."}
    )  # Initial state matches

    # pkg2: Just a dummy file
    factory.with_source("src/pkg2/mod.py", "def other(): pass")

    # Config: Define two targets
    factory.build()
    (tmp_path / "pyproject.toml").write_text(
        dedent("""
    [project]
    name = "test-proj"
    
    [tool.stitcher.targets.t1]
    scan_paths = ["src/pkg1"]
    
    [tool.stitcher.targets.t2]
    scan_paths = ["src/pkg2"]
    """),
        encoding="utf-8",
    )

    # 2. Initialize signatures (Run init)
    app = create_test_app(tmp_path)
    app.run_init()

    # Verify init happened
    hashes_initial = get_stored_hashes(tmp_path, "src/pkg1/mod.py")
    assert hashes_initial["func"]["baseline_yaml_content_hash"] is not None

    # 3. Modify Docs in YAML (Simulate Doc Improvement)
    # This creates a state: Code Hash matches, YAML Hash differs -> Doc Improvement
    (tmp_path / "src/pkg1/mod.stitcher.yaml").write_text(
        '"func": |-\n  Better Doc.', encoding="utf-8"
    )

    # 4. Run Check
    # This should detect the improvement and update the signature file
    spy = SpyBus()
    with spy.patch(monkeypatch, "stitcher.common.bus"):
        app.run_check()

    # 5. Assertions

    # A. Check that the bus reported the update (Phase 4 reporting works even with the bug)
    spy.assert_id_called(L.check.state.doc_updated)

    # B. Check PERMANENCE (The critical part)
    # If the bug exists, this file was NOT updated because pkg1 was not in the 'modules'
    # list when the loop finished (pkg2 was).
    hashes_after = get_stored_hashes(tmp_path, "src/pkg1/mod.py")

    # The stored hash should now reflect "Better Doc."
    # We don't check the hash value specifically, but it must differ from initial.
    assert (
        hashes_after["func"]["baseline_yaml_content_hash"]
        != hashes_initial["func"]["baseline_yaml_content_hash"]
    )
