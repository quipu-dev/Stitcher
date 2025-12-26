from typing import Any

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

    def __init__(self, path: str = ""):
        # We use a dunder name to avoid conflict with potential user-defined keys
        # starting with a single underscore.
        self.__path = path

    def __getattr__(self, name: str) -> "SemanticPointer":
        """
        Returns a new SemanticPointer with the appended path component.
        """
        # If path is empty, it's the root. New path is just the name.
        # Otherwise, join with a dot.
        new_path = f"{self.__path}.{name}" if self.__path else name
        return SemanticPointer(new_path)

    def __str__(self) -> str:
        """
        Returns the full dot-separated path string.
        """
        return self.__path

    def __repr__(self) -> str:
        return f"<SemanticPointer: '{self.__path}'>"

    def __eq__(self, other: Any) -> bool:
        """
        Allows comparison with strings or other pointers.
        L.a.b == "a.b" is True.
        """
        if isinstance(other, SemanticPointer):
            return self.__path == other.__path
        return str(other) == self.__path

    def __hash__(self) -> int:
        return hash(self.__path)


# Global singleton instance acting as the root anchor.
L = SemanticPointer()