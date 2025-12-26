from typing import Any


class SemanticPointer:
    def __init__(self, path: str = ""):
        # We use a dunder name to avoid conflict with potential user-defined keys
        # starting with a single underscore.
        self.__path = path

    def __getattr__(self, name: str) -> "SemanticPointer":
        # If path is empty, it's the root. New path is just the name.
        # Otherwise, join with a dot.
        new_path = f"{self.__path}.{name}" if self.__path else name
        return SemanticPointer(new_path)

    def __str__(self) -> str:
        return self.__path

    def __repr__(self) -> str:
        return f"<SemanticPointer: '{self.__path}'>"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, SemanticPointer):
            return self.__path == other.__path
        return str(other) == self.__path

    def __hash__(self) -> int:
        return hash(self.__path)


# Global singleton instance acting as the root anchor.
L = SemanticPointer()
