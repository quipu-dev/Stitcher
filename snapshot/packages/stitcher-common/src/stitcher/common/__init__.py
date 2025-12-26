__path__ = __import__("pkgutil").extend_path(__path__, __name__)

# Make core singletons easily accessible
from stitcher.needle import needle
from .messaging.bus import bus

__all__ = ["bus", "needle"]
