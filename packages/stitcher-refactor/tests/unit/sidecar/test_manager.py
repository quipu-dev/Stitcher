from pathlib import Path
import pytest
from stitcher.refactor.sidecar.manager import SidecarManager


@pytest.fixture
def project_structure(tmp_path: Path):
    """Creates a dummy project structure."""
    root = tmp_path
    src_file = root / "src" / "mypkg" / "module.py"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.touch()
    return root, src_file


def test_sidecar_manager_get_doc_path(project_structure):
    # ARRANGE
    root, src_file = project_structure
    manager = SidecarManager(root)
    expected_doc_path = root / "src" / "mypkg" / "module.stitcher.yaml"

    # ACT
    actual_doc_path = manager.get_doc_path(src_file)

    # ASSERT
    assert actual_doc_path == expected_doc_path


def test_sidecar_manager_get_signature_path(project_structure):
    # ARRANGE
    root, src_file = project_structure
    manager = SidecarManager(root)
    expected_sig_path = (
        root / ".stitcher" / "signatures" / "src" / "mypkg" / "module.json"
    )

    # ACT
    actual_sig_path = manager.get_signature_path(src_file)

    # ASSERT
    assert actual_sig_path == expected_sig_path


def test_sidecar_manager_handles_files_outside_root_gracefully(tmp_path):
    # ARRANGE
    project_root = tmp_path / "project"
    project_root.mkdir()
    outside_file = tmp_path / "outside.py"
    outside_file.touch()

    manager = SidecarManager(project_root)

    # ACT & ASSERT
    with pytest.raises(ValueError, match="is not within the project root"):
        manager.get_signature_path(outside_file)
