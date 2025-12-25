__path__ = __import__("pkgutil").extend_path(__path__, __name__)

# Make bus easily accessible
from .messaging import bus