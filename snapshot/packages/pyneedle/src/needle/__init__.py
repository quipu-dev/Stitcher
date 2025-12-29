# This is the crucial line. It makes this regular package
# "porous" and allows the namespace to be extended.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

# Now that the full 'needle' namespace is assembled, we can safely import from it.
from needle.pointer import L, SemanticPointer, PointerSet
from needle.runtime import nexus
from needle.spec import (
    OperatorProtocol,
    SemanticPointerProtocol,
    PointerSetProtocol,
)

__all__ = [
    "L",
    "SemanticPointer",
    "PointerSet",
    "nexus",
    "OperatorProtocol",
    "SemanticPointerProtocol",
    "PointerSetProtocol",
]
