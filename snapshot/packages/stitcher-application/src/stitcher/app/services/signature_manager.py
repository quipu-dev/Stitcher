import json
from pathlib import Path
from typing import Dict, Any

from stitcher.spec import ModuleDef


class SignatureManager:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.sig_root = root_path / ".stitcher" / "signatures"

    def _get_sig_path(self, module: ModuleDef) -> Path:
        rel_path = Path(module.file_path)
        return self.sig_root / rel_path.with_suffix(".json")

    def compute_code_structure_hashes(self, module: ModuleDef) -> Dict[str, str]:
        hashes = {}
        for func in module.functions:
            hashes[func.name] = func.compute_fingerprint()
        for cls in module.classes:
            for method in cls.methods:
                fqn = f"{cls.name}.{method.name}"
                hashes[fqn] = method.compute_fingerprint()
        return hashes

    def save_composite_hashes(self, module: ModuleDef, hashes: Dict[str, Any]) -> None:
        if not hashes:
            sig_path = self._get_sig_path(module)
            if sig_path.exists():
                sig_path.unlink()
            return

        sig_path = self._get_sig_path(module)
        sig_path.parent.mkdir(parents=True, exist_ok=True)

        with sig_path.open("w", encoding="utf-8") as f:
            json.dump(hashes, f, indent=2, sort_keys=True)

    def load_composite_hashes(self, module: ModuleDef) -> Dict[str, Any]:
        sig_path = self._get_sig_path(module)
        if not sig_path.exists():
            return {}
        try:
            with sig_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}
