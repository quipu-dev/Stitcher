__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from pathlib import Path
from needle.runtime import _default_loader
from pathlib import Path

# --- Auto-register CLI assets ---
try:
    _assets_path = Path(__file__).parent / "assets"
    if _assets_path.is_dir():
        _default_loader.add_root(_assets_path)
except NameError:
    pass
# --------------------------------
