__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from pathlib import Path
from needle.nexus import OverlayNexus
from needle.loaders.fs_loader import FileSystemLoader
from .messaging.bus import MessageBus

# --- Composition Root for Stitcher's Core Services ---

# 1. Create the loader instance.
stitcher_loader = FileSystemLoader()

# 2. Create the nexus instance, injecting the loader.
stitcher_nexus = OverlayNexus(loaders=[stitcher_loader])

# 3. Create the bus instance, injecting the nexus.
bus = MessageBus(nexus_instance=stitcher_nexus)

# 4. Auto-register built-in assets for the 'common' package.
try:
    _assets_path = Path(__file__).parent / "assets"
    if _assets_path.is_dir():
        stitcher_loader.add_root(_assets_path)
except NameError:
    pass
# ---------------------------------------------


# Public API for stitcher packages
__all__ = ["bus", "stitcher_nexus", "stitcher_loader"]
