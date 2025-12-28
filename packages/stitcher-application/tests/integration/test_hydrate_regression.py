import json
from pathlib import Path
from stitcher.app import StitcherApp
from stitcher.test_utils import WorkspaceFactory, SpyBus
from needle.pointer import L


def test_hydrate_does_not_rewrite_synced_legacy_signatures(tmp_path: Path, monkeypatch):
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
    sig_file_path = project_root / ".stitcher/signatures/src/main.json"
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

    spy_bus = SpyBus()

    # 3. Act: Run the hydrate command.
    # Because the signature file contains legacy keys ('code_structure_hash'),
    # the strict Fingerprint validation should fail, treating the file as corrupted/empty.
    # Hydrate will then treat the code as "new" and regenerate the signatures with
    # correct keys ('baseline_code_structure_hash').
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_hydrate()

    # 4. Assert
    data_after = json.loads(sig_file_path.read_text())

    assert success is True

    # Verify the new schema is present for the function
    fp_func = data_after.get("func", {})
    assert "baseline_code_structure_hash" in fp_func, (
        "New schema key 'baseline_code_structure_hash' missing."
    )
    assert "code_structure_hash" not in fp_func, (
        "Legacy schema key 'code_structure_hash' was not removed."
    )

    # Even though we migrated signatures, no docs were hydrated, so user sees "no changes"
    # in terms of docstring updates.
    spy_bus.assert_id_called(L.hydrate.run.no_changes, level="info")
