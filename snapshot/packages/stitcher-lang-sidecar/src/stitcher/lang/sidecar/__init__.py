# This allows this package to coexist with other distribution packages
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .adapter import SidecarAdapter

__all__ = ["SidecarAdapter"]
