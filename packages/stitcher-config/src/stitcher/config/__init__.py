__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .loader import StitcherConfig, load_config_from_path

__all__ = ["StitcherConfig", "load_config_from_path"]