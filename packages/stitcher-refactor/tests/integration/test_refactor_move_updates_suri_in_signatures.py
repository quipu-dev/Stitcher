import json
from pathlib import Path
from stitcher.test_utils import WorkspaceFactory, create_test_app
from stitcher.refactor.migration import MigrationSpec, Move


def test_move_file_operation_updates_suri_in_signatures(tmp_path: Path):
    """
    Verify that moving a file also updates the SURI keys in the signature file.
    """
    # --- Arrange ---
    workspace_factory = WorkspaceFactory(root_path=tmp_path)
    workspace_root = workspace_factory.with_config({
        "scan_paths": ["src"]
    }).with_source(
        "src/my_app/logic.py",
        """
        def do_something():
            \"\"\"This is a docstring.\"\"\"
            pass
        """
    ).build()

    app = create_test_app(workspace_root)

    # --- Act 1: Initialize the project to create signatures ---
    app.run_init()

    # --- Assert 1: Verify initial signature file and SURI key ---
    old_sig_path = workspace_root / ".stitcher/signatures/src/my_app/logic.json"
    new_sig_path = workspace_root / ".stitcher/signatures/src/my_app/core/logic.json"
    old_suri = "py://src/my_app/logic.py#do_something"
    new_suri = "py://src/my_app/core/logic.py#do_something"

    assert old_sig_path.exists()
    assert not new_sig_path.exists()
    initial_data = json.loads(old_sig_path.read_text())
    assert old_suri in initial_data
    assert "baseline_code_structure_hash" in initial_data[old_suri]

    # --- Arrange 2: Create the migration script ---
    migration_script_content = """
from pathlib import Path
from stitcher.refactor.migration import MigrationSpec, Move

def upgrade(spec: MigrationSpec):
    spec.add(Move(
        Path("src/my_app/logic.py"),
        Path("src/my_app/core/logic.py")
    ))
"""
    migration_script_path = workspace_root / "migration.py"
    migration_script_path.write_text(migration_script_content)

    # --- Act 2: Run the refactor operation ---
    app.run_refactor_apply(migration_script_path, confirm_callback=lambda _: True)

    # --- Assert 2: Verify the signature file was moved AND its content updated ---
    assert not old_sig_path.exists(), "Old signature file should have been moved"
    assert new_sig_path.exists(), "New signature file should exist at the new location"

    final_data = json.loads(new_sig_path.read_text())

    # This is the failing assertion. The key should now be the NEW suri.
    assert old_suri not in final_data, "The old SURI key should not be present"
    assert new_suri in final_data, "The SURI key should have been updated to the new path"

    # Also verify the fingerprint data was preserved
    assert "baseline_code_structure_hash" in final_data[new_suri]