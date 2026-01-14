# This is the crucial line. It makes this regular package
# "porous" and allows the namespace to be extended.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)


__all__ = [
    "L",
    "SemanticPointer",
    "PointerSet",
    "nexus",
    "OperatorProtocol",
    "SemanticPointerProtocol",
    "PointerSetProtocol",
    "OverlayOperator",
]


# Use PEP 562 to lazily load modules and break circular dependencies.
def __getattr__(name: str):
    if name in ("L", "SemanticPointer", "PointerSet"):
        # We must import all, as the module only executes once.
        from needle.pointer import L, SemanticPointer, PointerSet

        if name == "L":
            return L
        if name == "SemanticPointer":
            return SemanticPointer
        return PointerSet  # PointerSet
    elif name == "nexus":
        from needle.runtime import nexus

        return nexus
    elif name in ("OperatorProtocol", "SemanticPointerProtocol", "PointerSetProtocol"):
        from needle.spec import (
            OperatorProtocol,
            SemanticPointerProtocol,
            PointerSetProtocol,
        )

        if name == "OperatorProtocol":
            return OperatorProtocol
        if name == "SemanticPointerProtocol":
            return SemanticPointerProtocol
        return PointerSetProtocol  # PointerSetProtocol
    elif name == "OverlayOperator":
        from needle.operators import OverlayOperator

        return OverlayOperator

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
