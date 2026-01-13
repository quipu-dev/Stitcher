import json
from pathlib import Path

from stitcher.spec import Fingerprint
from stitcher.workspace import Workspace
from stitcher.lang.sidecar import SignatureManager
from stitcher.test_utils import WorkspaceFactory


def test_save_and_load_single_lock_file(tmp_path: Path):
    # Arrange
    ws_factory = WorkspaceFactory(tmp_path).with_pyproject("packages/pkg-a")
    pkg_a_root = ws_factory.root_path / "packages/pkg-a"
    ws_factory.with_source("packages/pkg-a/src/main.py", "def func_a(): ...").build()
    workspace = Workspace(tmp_path)
    manager = SignatureManager(workspace)

    # Act
    hashes = {
        "func_a": Fingerprint.from_dict({"baseline_code_structure_hash": "hash_a"})
    }
    manager.save_composite_hashes("packages/pkg-a/src/main.py", hashes)
    manager.flush()

    # Assert: Lock file is created correctly
    lock_path = pkg_a_root / "stitcher.lock"
    assert lock_path.exists()
    with lock_path.open("r") as f:
        data = json.load(f)
    assert data["version"] == "1.0"
    assert "py://packages/pkg-a/src/main.py#func_a" in data["fingerprints"]
    assert (
        data["fingerprints"]["py://packages/pkg-a/src/main.py#func_a"][
            "baseline_code_structure_hash"
        ]
        == "hash_a"
    )

    # Assert: Loading works
    new_manager = SignatureManager(workspace)
    loaded_hashes = new_manager.load_composite_hashes("packages/pkg-a/src/main.py")
    assert loaded_hashes == hashes


def test_legacy_migration_and_cleanup(tmp_path: Path):
    # Arrange: Create a legacy .stitcher/signatures layout
    ws_factory = WorkspaceFactory(tmp_path).with_pyproject("packages/pkg-a")
    pkg_a_root = ws_factory.root_path / "packages/pkg-a"
    ws_factory.with_source("packages/pkg-a/src/main.py", "def func_a(): ...").build()

    legacy_sig_dir = tmp_path / ".stitcher/signatures/packages/pkg-a/src"
    legacy_sig_dir.mkdir(parents=True, exist_ok=True)
    legacy_sig_file = legacy_sig_dir / "main.json"
    legacy_suri = "py://packages/pkg-a/src/main.py#func_a"
    legacy_data = {legacy_suri: {"baseline_code_structure_hash": "legacy_hash"}}
    with legacy_sig_file.open("w") as f:
        json.dump(legacy_data, f)

    workspace = Workspace(tmp_path)
    manager = SignatureManager(workspace)

    # Act: Loading should trigger migration into cache
    loaded_hashes = manager.load_composite_hashes("packages/pkg-a/src/main.py")

    # Assert: Data is loaded correctly from legacy source
    assert loaded_hashes["func_a"].to_dict() == {
        "baseline_code_structure_hash": "legacy_hash"
    }

    # Act: Flush should write new lock file and delete old directory
    manager.flush()

    # Assert: New lock file exists and is correct
    lock_path = pkg_a_root / "stitcher.lock"
    assert lock_path.exists()
    with lock_path.open("r") as f:
        data = json.load(f)
    assert (
        data["fingerprints"][legacy_suri]["baseline_code_structure_hash"]
        == "legacy_hash"
    )

    # Assert: Legacy directory is deleted
    assert not (tmp_path / ".stitcher/signatures").exists()


def test_empty_hashes_removes_lock_file(tmp_path: Path):
    # Arrange
    ws_factory = WorkspaceFactory(tmp_path).with_pyproject("packages/pkg-a")
    pkg_a_root = ws_factory.root_path / "packages/pkg-a"
    ws_factory.with_source("packages/pkg-a/src/main.py", "def func_a(): ...").build()
    workspace = Workspace(tmp_path)
    manager = SignatureManager(workspace)
    lock_path = pkg_a_root / "stitcher.lock"
    lock_path.touch()

    # Act
    manager.save_composite_hashes("packages/pkg-a/src/main.py", {})
    manager.flush()

    # Assert
    assert not lock_path.exists()
