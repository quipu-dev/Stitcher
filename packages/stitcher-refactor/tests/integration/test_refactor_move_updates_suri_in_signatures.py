import json
from pathlib import Path
from stitcher.test_utils import WorkspaceFactory, create_test_app


def test_move_file_operation_updates_suri_in_lockfile(workspace_factory: WorkspaceFactory):
    workspace_root = (
        workspace_factory.with_config({"scan_paths": ["packages/pkg-a/src"]})
        .with_pyproject("packages/pkg-a")
        .with_source(
            "packages/pkg-a/src/my_app/logic.py",
            'def do_something():\n    """Doc"""\n    pass',
        )
        .build()
    )
    pkg_a_root = workspace_root / "packages" / "pkg-a"

    app = create_test_app(workspace_root)
    app.run_init()

    lock_path = pkg_a_root / "stitcher.lock"
    assert lock_path.exists()

    old_suri = "py://packages/pkg-a/src/my_app/logic.py#do_something"
    new_suri = "py://packages/pkg-a/src/my_app/core/logic.py#do_something"

    initial_data = json.loads(lock_path.read_text())
    assert old_suri in initial_data["fingerprints"]

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

    app.run_refactor_apply(migration_script_path, confirm_callback=lambda _: True)

    assert lock_path.exists()
    final_data = json.loads(lock_path.read_text())["fingerprints"]
    assert old_suri not in final_data
    assert new_suri in final_data
    assert "baseline_code_structure_hash" in final_data[new_suri]
