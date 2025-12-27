__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from needle.pointer import L, SemanticPointer, PointerSet
from needle.nexus import OverlayNexus
from .loaders.fs_loader import FileSystemLoader

# --- Global Singleton Instance ---
# This is the "batteries-included" setup.
# It automatically discovers the project root and sets up a file system loader.
_default_loader = FileSystemLoader()
nexus = OverlayNexus(loaders=[_default_loader])
# ---------------------------------

# Make the loader accessible for advanced use cases (e.g., adding asset paths)
# Example: from needle import _default_loader
#          _default_loader.add_root(my_assets_path)
#          nexus.reload()

__all__ = ["L", "nexus", "SemanticPointer", "PointerSet", "_default_loader"]