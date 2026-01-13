from pathlib import Path
from typing import Union

from stitcher.lang.sidecar.signature_manager import SignatureManager
from stitcher.workspace import Workspace


class SidecarManager:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.signature_manager = SignatureManager(workspace)

    def get_doc_path(self, source_file_path: Union[str, Path]) -> Path:
        """
        Returns the path to the document sidecar (.stitcher.yaml) for a given source file.
        This logic is simple enough to live here directly.
        """
        return Path(source_file_path).with_suffix(".stitcher.yaml")

    def get_signature_path(self, source_file_path: Union[str, Path]) -> Path:
        """
        Returns the path to the signature lock file (stitcher.lock) containing the given source file.
        Delegates to SignatureManager to handle package root resolution.
        """
        # Ensure we pass an absolute path string, as expected by some internal logic flows.
        abs_path = self.workspace.root_path / Path(source_file_path)
        return self.signature_manager.get_signature_path(str(abs_path))