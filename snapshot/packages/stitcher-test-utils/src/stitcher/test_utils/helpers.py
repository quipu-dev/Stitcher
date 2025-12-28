import json
from pathlib import Path

def get_stored_hashes(project_root: Path, file_path: str) -> dict:
    """
    Test helper to load the composite hashes for a given source file from the
    .stitcher/signatures directory.
    """
    sig_file = (
        project_root / ".stitcher/signatures" / Path(file_path).with_suffix(".json")
    )
    if not sig_file.exists():
        return {}
    with sig_file.open("r") as f:
        return json.load(f)