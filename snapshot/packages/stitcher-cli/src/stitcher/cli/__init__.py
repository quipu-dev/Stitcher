__path__ = __import__("pkgutil").extend_path(__path__, __name__)

# All assets are now loaded by stitcher-common, so no special
# loader setup is needed here anymore. We can directly import the app.
from .main import app

__all__ = ["app"]
