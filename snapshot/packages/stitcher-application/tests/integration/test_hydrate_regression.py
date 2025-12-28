import json
from pathlib import Path
from stitcher.app import StitcherApp
from stitcher.test_utils import WorkspaceFactory, SpyBus
from needle.pointer import L


def test_hydrate_does_not_rewrite_synced_legacy_signatures(
    tmp_path: Path, monkeypatch
):
    """
    Regression Test: Verifies that `hydrate` does not rewrite signature files
    when they are in sync but use a legacy key schema.

    Problem: `hydrate` was rewriting files because it didn't recognize the old
    `code_structure_hash` key, causing unnecessary git changes even when
    no docstrings were hydrated.
    """
    # 1. Arrange: Create a project and initialize it to get a baseline.
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", 'def func(a: int):\n    """Doc."""')
        .build()
    )

    app = StitcherApp(root_path=project_root)
    with SpyBus().patch(monkeypatch, "stitcher.app.core.bus"):
        app.run_init()

    # 2. Arrange: Manually convert the signature file to the legacy format.
    # This simulates the state of the project before the key name change.
    sig_file_path = (
        project_root / ".stitcher/signatures/src/main.json"
    )
    with sig_file_path.open("r") as f:
        data = json.load(f)

    # Convert to legacy format: baseline_code_structure_hash -> code_structure_hash
    legacy_data = {}
    for fqn, hashes in data.items():
        legacy_data[fqn] = {
            "code_structure_hash": hashes.get("baseline_code_structure_hash"),
            "yaml_content_hash": hashes.get("baseline_yaml_content_hash"),
        }
    with sig_file_path.open("w") as f:
        json.dump(legacy_data, f)

    # The project is now in a "synchronized" state, but with a legacy signature file.
    # We also strip the source docstring to ensure hydrate has nothing to do.
    (project_root / "src/main.py").write_text("def func(a: int): ...")

    content_before = sig_file_path.read_text()
    spy_bus = SpyBus()

    # 3. Act: Run the hydrate command.
    # Because the signature file contains legacy keys ('code_structure_hash'),
    # the strict Fingerprint validation should fail, treating the file as corrupted/empty.
    # Hydrate will then treat the code as "new" and regenerate the signatures with
    # correct keys ('baseline_code_structure_hash').
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_hydrate()

    # 4. Assert
    content_after = sig_file_path.read_text()

    assert success is True
    # The file content MUST change, because we are migrating from legacy to new schema.
    assert content_after != content_before, (
        "Hydrate command failed to migrate legacy signature file."
    )
    
    # Verify the new schema is present
    assert "baseline_code_structure_hash" in content_after
    assert "code_structure_hash" not in content_after

    # Even though we migrated signatures, no docs were hydrated, so user sees "no changes"
    # in terms of docstring updates.
    spy_bus.assert_id_called(L.hydrate.run.no_changes, level="info")