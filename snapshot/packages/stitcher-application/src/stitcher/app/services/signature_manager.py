import json
from pathlib import Path
from typing import Dict


from stitcher.spec import (
    Fingerprint,
    InvalidFingerprintKeyError,
)
from stitcher.common.services import AssetPathResolver
from stitcher.adapter.python.uri import SURIGenerator


class SignatureManager:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.resolver = AssetPathResolver(root_path)

    def _get_sig_path(self, file_path: str) -> Path:
        return self.resolver.get_signature_path(file_path)

    def save_composite_hashes(
        self, file_path: str, hashes: Dict[str, Fingerprint]
    ) -> None:
        if not hashes:
            sig_path = self._get_sig_path(file_path)
            if sig_path.exists():
                sig_path.unlink()
            return

        sig_path = self._get_sig_path(file_path)
        sig_path.parent.mkdir(parents=True, exist_ok=True)

        serialized_data = {
            SURIGenerator.for_symbol(file_path, fqn): fp.to_dict()
            for fqn, fp in hashes.items()
        }

        with sig_path.open("w", encoding="utf-8") as f:
            json.dump(serialized_data, f, indent=2, sort_keys=True)

    def load_composite_hashes(self, file_path: str) -> Dict[str, Fingerprint]:
        sig_path = self._get_sig_path(file_path)
        if not sig_path.exists():
            return {}
        try:
            with sig_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    return {}
                result = {}
                for suri, fp_data in data.items():
                    try:
                        _path, fragment = SURIGenerator.parse(suri)
                        if fragment:
                            result[fragment] = Fingerprint.from_dict(fp_data)
                    except (ValueError, InvalidFingerprintKeyError):
                        # Gracefully skip malformed SURIs or invalid fingerprint data
                        continue
                return result
        except (json.JSONDecodeError, OSError):
            return {}

    def reformat_hashes_for_file(self, file_path: str) -> bool:
        sig_path = self._get_sig_path(file_path)
        if not sig_path.exists():
            return False

        hashes = self.load_composite_hashes(file_path)
        if not hashes:
            return False

        self.save_composite_hashes(file_path, hashes)
        return True
