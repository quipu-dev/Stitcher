import json
from pathlib import Path
from typing import Dict

from stitcher.spec import ModuleDef


class SignatureManager:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.sig_root = root_path / ".stitcher" / "signatures"

    def _get_sig_path(self, module: ModuleDef) -> Path:
        # module.file_path is relative to project root
        rel_path = Path(module.file_path)
        return self.sig_root / rel_path.with_suffix(".json")

    def compute_module_fingerprints(self, module: ModuleDef) -> Dict[str, str]:
        fingerprints = {}

        # 1. Functions
        for func in module.functions:
            fingerprints[func.name] = func.compute_fingerprint()

        # 2. Classes and Methods
        for cls in module.classes:
            # We could fingerprint the class itself (bases etc.), but for now
            # let's focus on methods as they map to docstrings.
            for method in cls.methods:
                fqn = f"{cls.name}.{method.name}"
                fingerprints[fqn] = method.compute_fingerprint()

        return fingerprints

    def save_signatures(self, module: ModuleDef) -> None:
        fingerprints = self.compute_module_fingerprints(module)
        if not fingerprints:
            # If no fingerprints (e.g. empty file), we might want to clean up any old file
            # But for now, just returning is safer.
            return

        sig_path = self._get_sig_path(module)
        # Ensure the directory exists (redundant check but safe)
        if not sig_path.parent.exists():
            sig_path.parent.mkdir(parents=True, exist_ok=True)

        with sig_path.open("w", encoding="utf-8") as f:
            json.dump(fingerprints, f, indent=2, sort_keys=True)

    def load_signatures(self, module: ModuleDef) -> Dict[str, str]:
        sig_path = self._get_sig_path(module)
        if not sig_path.exists():
            return {}

        try:
            with sig_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def check_signatures(self, module: ModuleDef) -> Dict[str, str]:
        current_sigs = self.compute_module_fingerprints(module)
        stored_sigs = self.load_signatures(module)

        issues = {}

        for fqn, current_hash in current_sigs.items():
            stored_hash = stored_sigs.get(fqn)

            # If stored_hash is None, it's a new function (covered by 'missing' check in doc_manager).
            # We only care if it EXISTS in storage but differs.
            if stored_hash and stored_hash != current_hash:
                issues[fqn] = "signature_mismatch"

        return issues
