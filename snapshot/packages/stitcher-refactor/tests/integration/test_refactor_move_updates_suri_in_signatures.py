import json
from pathlib import Path
from stitcher.test_utils import WorkspaceFactory, create_test_app


import json
from pathlib import Path
from stitcher.test_utils import WorkspaceFactory, create_test_app, get_stored_hashes


def test_move_file_operation_updates_suri_in_signatures(tmp_path: Path):
    """
    Verify that moving a file also updates the SURI keys in the signature file.
    """
    # --- Arrange ---
    workspace_factory = WorkspaceFactory(root_path=tmp_path)
    # The package root needs a pyproject.toml to be identified.
    # The structure will be src/my_app, so 'src' is the code root.
    workspace_root = (
        workspace_factory.with_config({"scan_paths": ["src"]})
        .with_pyproject(".")
        .with_source(
            "src/my_app/logic.py",
            """
        def do_something():
            \"\"\"This is a docstring.\"\"\"
            pass
        """,
        )
        .build()
    )

    app = create_test_app(workspace_root)

    # --- Act 1: Initialize the project to create signatures ---
    app.run_init()

    # --- Assert 1: Verify initial signature file and SURI key ---
    old_suri = "py://src/my_app/logic.py#do_something"
    new_suri = "py://src/my_app/core/logic.py#do_something"

    initial_hashes = get_stored_hashes(workspace_root, "src/my_app/logic.py")
    assert old_suri in initial_hashes
    assert "baseline_code_structure_hash" in initial_hashes[old_suri]

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

    # --- Assert 2: Verify the signature file content was updated ---
    # The lock file itself does not move if the package root is the same.
    lock_path = workspace_root / "stitcher.lock"
    assert lock_path.exists()

    final_data = get_stored_hashes(workspace_root, "src/my_app/core/logic.py")

    assert old_suri not in final_data, "The old SURI key should not be present"
    assert new_suri in final_data, (
        "The SURI key should have been updated to the new path"
    )
    assert "baseline_code_structure_hash" in final_data[new_suri]
