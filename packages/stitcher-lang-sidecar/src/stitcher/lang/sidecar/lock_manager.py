import json
from pathlib import Path
from typing import Dict

from stitcher.spec import LockManagerProtocol, Fingerprint


class LockFileManager(LockManagerProtocol):
    """
    Manages the reading and writing of stitcher.lock files.
    This implementation is non-migratory and will not read from the legacy
    .stitcher/signatures directory.
    """

    LOCK_FILE_NAME = "stitcher.lock"

    def load(self, package_root: Path) -> Dict[str, Fingerprint]:
        lock_path = package_root / self.LOCK_FILE_NAME
        if not lock_path.exists():
            return {}

        try:
            with lock_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            raw_fingerprints = data.get("fingerprints", {})
            if not isinstance(raw_fingerprints, dict):
                return {}  # Invalid format

            return {
                suri: Fingerprint.from_dict(fp_data)
                for suri, fp_data in raw_fingerprints.items()
            }
        except (json.JSONDecodeError, OSError):
            # Log a warning in a real scenario
            return {}

    def save(self, package_root: Path, data: Dict[str, Fingerprint]) -> None:
        lock_path = package_root / self.LOCK_FILE_NAME
        lock_path.parent.mkdir(parents=True, exist_ok=True)

        serializable_data = {
            suri: fp.to_dict() for suri, fp in data.items()
        }

        lock_content = {
            "version": "1.0",
            "fingerprints": serializable_data,
        }

        with lock_path.open("w", encoding="utf-8") as f:
            json.dump(lock_content, f, indent=2, sort_keys=True)
            f.write("\n")  # Ensure trailing newline