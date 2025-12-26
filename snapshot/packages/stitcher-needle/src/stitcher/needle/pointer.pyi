from typing import Any

L: Any

class SemanticPointer:
    """
    A recursive proxy object that represents a semantic path in the Stitcher universe.

It allows developers to use dot notation (e.g., L.auth.login.success) to refer
to semantic keys, which are converted to their string representation
(e.g., "auth.login.success") at runtime.

This class is designed to be:
1. Zero-dependency: It relies only on Python standard features.
2. Lightweight: It performs no I/O or complex logic.
3. Immutable-ish: Attribute access returns a *new* instance.
    """

    def __init__(self, path: str = ""): ...

    def __getattr__(self, name: str) -> "SemanticPointer":
        """Returns a new SemanticPointer with the appended path component."""
        ...

    def __str__(self) -> str:
        """Returns the full dot-separated path string."""
        ...

    def __repr__(self) -> str: ...

    def __eq__(self, other: Any) -> bool:
        """
        Allows comparison with strings or other pointers.
L.a.b == "a.b" is True.
        """
        ...

    def __hash__(self) -> int: ...