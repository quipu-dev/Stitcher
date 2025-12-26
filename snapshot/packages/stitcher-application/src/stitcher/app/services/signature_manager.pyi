import json
from pathlib import Path
from typing import Dict
from stitcher.spec import ModuleDef

class SignatureManager:
    """
    Manages the persistence and verification of code structure fingerprints.
Stores fingerprints in .stitcher/signatures/ mirroring the source tree.
    """

    def __init__(self, root_path: Path): ...

    def _get_sig_path(self, module: ModuleDef) -> Path:
        """
        Determines the storage path for a module's signatures.
e.g. src/app.py -> .stitcher/signatures/src/app.json
        """
        ...

    def compute_module_fingerprints(self, module: ModuleDef) -> Dict[str, str]:
        """
        Computes fingerprints for all addressable functions/methods in the module.
Returns: { "FQN": "hash" }
        """
        ...

    def save_signatures(self, module: ModuleDef) -> None:
        """Computes and saves the current signatures of the module to disk."""
        ...

    def load_signatures(self, module: ModuleDef) -> Dict[str, str]:
        """
        Loads the stored signatures for a module.
Returns empty dict if no signature file exists.
        """
        ...

    def check_signatures(self, module: ModuleDef) -> Dict[str, str]:
        """
        Compares current module structure against stored signatures.
Returns a dict of changed items: { "FQN": "signature_mismatch" }
        """
        ...