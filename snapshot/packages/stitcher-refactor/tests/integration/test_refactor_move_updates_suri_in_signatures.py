import json
from pathlib import Path
from stitcher.test_utils import WorkspaceFactory, create_test_app


def test_move_file_operation_updates_suri_in_lockfile(tmp_path: Path):
    """
    Verify that moving a file updates the SURI keys in the corresponding stitcher.lock file.
    """
    # --- Arrange ---
    # Note: We now have a package structure.
    pkg_a_root = tmp_path / "packages" / "pkg-a"
    workspace_factory = WorkspaceFactory(root_path=tmp_path)
    workspace_root = (
        workspace_factory
        .with_config({
            "scan_paths": ["packages/pkg-a/src"]
        })
        .with_pyproject("packages/pkg-a")  # Creates pyproject.toml for pkg-a
        .with_source(
            "packages/pkg-a/src/my_app/logic.py",
            """
        def do_something():
            \"\"\"This is a docstring.\"\"\"
            pass
        """,
        )
        .build()
    )

    app = create_test_app(workspace_root)

    # --- Act 1: Initialize the project to create the lock file ---
    app.run_init()

    # --- Assert 1: Verify initial lock file and SURI key ---
    lock_path = pkg_a_root / "stitcher.lock"
    assert lock_path.exists(), "stitcher.lock should be created in the package root"

    old_suri = "py://packages/pkg-a/src/my_app/logic.py#do_something"
    new_suri = "py://packages/pkg-a/src/my_app/core/logic.py#do_something"

    initial_data = json.loads(lock_path.read_text())
    assert old_suri in initial_data["fingerprints"]
    assert "baseline_code_structure_hash" in initial_data["fingerprints"][old_suri]

    # --- Arrange 2: Create the migration script ---
    migration_script_content = """
from pathlib import Path
from stitcher.refactor.migration import MigrationSpec, Move

def upgrade(spec: MigrationSpec):
    spec.add(Move(
        Path("packages/pkg-a/src/my_app/logic.py"),
        Path("packages/pkg-a/src/my_app/core/logic.py")
    ))
"""
    migration_script_path = workspace_root / "migration.py"
    migration_script_path.write_text(migration_script_content)

    # --- Act 2: Run the refactor operation ---
    # We are asserting False because the refactor logic is not yet updated.
    # This is a placeholder to show what the new test *should* do.
    # The next step (Phase 4) will make this test pass.
    # For now, we expect it to fail, but for the right reasons.
    try:
        app.run_refactor_apply(migration_script_path, confirm_callback=lambda _: True)
    except Exception as e:
        # The refactor might fail because its internal logic is still old.
        # We accept this for now, the goal is to have the test structure ready.
        print(f"Refactor apply failed as expected (will be fixed in Phase 4): {e}")


    # --- Assert 2: Verify the lock file content was updated ---
    # The test will fail here until Phase 4 is complete. This is intentional.
    # The assertion is our goal.
    assert lock_path.exists(), "Lock file should still exist"
    
    # This part of the test will fail until the refactor logic is updated.
    if lock_path.exists():
        final_data = json.loads(lock_path.read_text())
        assert old_suri not in final_data["fingerprints"], "The old SURI key should be removed from the lock file"
        assert new_suri in final_data["fingerprints"], "The new SURI key should be present in the lock file"

        # Also verify the fingerprint data was preserved
        assert "baseline_code_structure_hash" in final_data["fingerprints"][new_suri]
    else:
        # This branch is for the current failing state, where the lock file might be deleted or not updated.
        assert False, "Lock file was not correctly updated or was deleted during refactor."