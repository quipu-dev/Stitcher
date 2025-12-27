__path__ = __import__("pkgutil").extend_path(__path__, __name__)

# Make core singletons easily accessible
from .messaging.bus import bus
from needle.runtime import _default_loader
from pathlib import Path

# --- Auto-register built-in assets ---
# Find the path to our packaged assets directory and register it with Needle.
# This makes default translations and messages available out-of-the-box.
try:
    # __file__ gives the path to this __init__.py file
    _assets_path = Path(__file__).parent / "assets"
    if _assets_path.is_dir():
        _default_loader.add_root(_assets_path)
except NameError:
    # __file__ might not be defined in some environments (e.g. frozen).
    # We can add more robust discovery methods here later if needed.
    pass
# -------------------------------------


__all__ = ["bus"]
