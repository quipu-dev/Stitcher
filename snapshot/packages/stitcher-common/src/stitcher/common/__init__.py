__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from pathlib import Path
from needle.nexus import OverlayNexus
from needle.loaders import FileSystemLoader
from needle.runtime import _find_project_root
from .formatting import format_docstring, parse_docstring
from .messaging.bus import MessageBus

# --- Composition Root for Stitcher's Core Services ---

# 1. Discover necessary roots
#    - The current project's root (for user overrides)
#    - The `stitcher-common` package's own assets root (for defaults)
_project_root = _find_project_root()
_common_assets_root = Path(__file__).parent / "assets"

# 2. Create a loader for each root.
#    The project loader will be writable and has higher priority.
project_loader = FileSystemLoader(root=_project_root)
common_assets_loader = FileSystemLoader(root=_common_assets_root)

# 3. Create the nexus instance, composing loaders in the correct priority order.
#    `project_loader` comes first, so it overrides `common_assets_loader`.
stitcher_nexus = OverlayNexus(loaders=[project_loader, common_assets_loader])

# 4. Create the bus instance, injecting the application-specific nexus.
bus = MessageBus(nexus_instance=stitcher_nexus)

# Public API for stitcher packages.
# `stitcher_loader` is aliased to `project_loader` to maintain the contract
# for write operations, ensuring they go to the user's project directory.
stitcher_loader = project_loader

__all__ = [
    "bus",
    "stitcher_nexus",
    "stitcher_loader",
    "format_docstring",
    "parse_docstring",
]
