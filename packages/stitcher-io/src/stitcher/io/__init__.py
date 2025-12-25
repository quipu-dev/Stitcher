__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .stub_generator import StubGenerator

__all__ = ["StubGenerator"]