from pathlib import Path
from typing import Optional
from needle.pointer import L, SemanticPointer, PointerSet
from needle.nexus import OverlayNexus


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
# This is a generic, side-effect-free instance.
# Applications should compose their own nexus with specific loaders.
nexus = OverlayNexus(loaders=[])
# ---------------------------------


__all__ = ["L", "nexus", "SemanticPointer", "PointerSet", "_find_project_root"]
