from pathlib import Path
from typing import Union


class AssetPathResolver:
    def __init__(self, root_path: Path):
        self.root_path = root_path.resolve()
        self.sig_root = self.root_path / ".stitcher" / "signatures"

    def get_doc_path(self, source_path: Union[str, Path]) -> Path:
        path = Path(source_path)
        return path.with_suffix(".stitcher.yaml")

    def get_signature_path(self, source_path: Union[str, Path]) -> Path:
        path = Path(source_path)

        # If path is absolute, make it relative to root
        if path.is_absolute():
            try:
                # Resolve strictly to handle symlinks or .. components if necessary
                # though usually source_path comes from trusted traversal
                rel_path = path.resolve().relative_to(self.root_path)
            except ValueError:
                # If the path is absolute but not inside root_path,
                # we can't map it to the internal signature store structure.
                raise ValueError(
                    f"Source path {path} is not within the project root {self.root_path}"
                )
        else:
            rel_path = path

        return self.sig_root / rel_path.with_suffix(".json")
