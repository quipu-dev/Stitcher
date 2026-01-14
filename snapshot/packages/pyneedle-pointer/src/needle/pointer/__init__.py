__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .core import SemanticPointer

# The Global Root Pointer
L = SemanticPointer()

__all__ = ["L", "SemanticPointer", "PointerSet"]


# Use PEP 562 to lazily load PointerSet and break the core <-> set cycle.
def __getattr__(name: str):
    if name == "PointerSet":
        from .set import PointerSet

        return PointerSet

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
