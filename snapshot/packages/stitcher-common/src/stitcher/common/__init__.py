__path__ = __import__("pkgutil").extend_path(__path__, __name__)

# Make core singletons easily accessible
from .messaging import bus
from stitcher.needle import L

__all__ = ["bus", "L"]