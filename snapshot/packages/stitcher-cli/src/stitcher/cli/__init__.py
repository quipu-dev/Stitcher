__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from pathlib import Path
from stitcher.needle import needle

# --- Auto-register CLI assets ---
try:
    _assets_path = Path(__file__).parent / "assets"
    if _assets_path.is_dir():
        needle.add_root(_assets_path)
except NameError:
    pass
# --------------------------------
