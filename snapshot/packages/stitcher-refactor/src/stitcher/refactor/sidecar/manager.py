from pathlib import Path


class SidecarManager:
    def __init__(self, root_path: Path):
        self.root_path = root_path.resolve()
        self.sig_root = self.root_path / ".stitcher" / "signatures"

    def get_doc_path(self, source_file_path: Path) -> Path:
        return source_file_path.resolve().with_suffix(".stitcher.yaml")

    def get_signature_path(self, source_file_path: Path) -> Path:
        resolved_source = source_file_path.resolve()
        # This encapsulates the complex relative path logic
        try:
            relative_source_path = resolved_source.relative_to(self.root_path)
            return self.sig_root / relative_source_path.with_suffix(".json")
        except ValueError:
            # This can happen if source_file_path is not within root_path.
            # While unlikely in normal operation, it's safer to handle.
            # We'll re-raise a more informative error.
            raise ValueError(
                f"Source file {resolved_source} is not within the project root {self.root_path}"
            )
