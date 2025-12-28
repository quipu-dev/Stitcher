from pathlib import Path
from typing import Optional
from needle.pointer import L, SemanticPointer, PointerSet
from needle.nexus import OverlayNexus
from .loaders.fs_loader import FileSystemLoader

def _find_project_root(start_dir: Optional[Path] = None) -> Path:
    current_dir = (start_dir or Path.cwd()).resolve()
    # Stop at filesystem root
    while current_dir.parent != current_dir:
        if (current_dir / "pyproject.toml").is_file() or (
            current_dir / ".git"
        ).is_dir():
            return current_dir
        current_dir = current_dir.parent
    return start_dir or Path.cwd()

# --- Global Singleton Instance ---
# This is the "batteries-included" setup.
# It automatically discovers the project root and sets up a file system loader.
_project_root = _find_project_root()
_default_loader = FileSystemLoader(roots=[_project_root])
nexus = OverlayNexus(loaders=[_default_loader])
# ---------------------------------

# Make the loader accessible for advanced use cases (e.g., adding asset paths)
# Example: from needle import _default_loader
#          _default_loader.add_root(my_assets_path)
#          nexus.reload()

__all__ = ["L", "nexus", "SemanticPointer", "PointerSet", "_default_loader"]
