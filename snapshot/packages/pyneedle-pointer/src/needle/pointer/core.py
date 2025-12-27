from typing import Any, Union, Iterable, TYPE_CHECKING
from needle.spec import SemanticPointerProtocol, PointerSetProtocol

if TYPE_CHECKING:
    from .set import PointerSet


class SemanticPointer(SemanticPointerProtocol):
    """
    Standard implementation of the Semantic Pointer (L).

    It represents a path in the semantic universe.
    Instances are immutable; operations return new instances.
    """

    __slots__ = ("_path",)

    def __init__(self, path: str = ""):
        # Internal storage of the dot-separated path
        self._path = path

    def __getattr__(self, name: str) -> "SemanticPointer":
        """
        Syntactic sugar for path extension via dot notation.
        L.auth.login -> SemanticPointer("auth.login")
        """
        new_path = f"{self._path}.{name}" if self._path else name
        return SemanticPointer(new_path)

    def __str__(self) -> str:
        return self._path

    def __repr__(self) -> str:
        return f"<L: '{self._path}'>" if self._path else "<L: (root)>"

    def __eq__(self, other: Any) -> bool:
        """
        Equality check. Supports string comparison for convenience.
        L.a == "a" is True.
        """
        if isinstance(other, SemanticPointer):
            return self._path == other._path
        return str(other) == self._path

    def __hash__(self) -> int:
        return hash(self._path)

    def _join(self, other: Union[str, "SemanticPointerProtocol"]) -> "SemanticPointer":
        """
        Internal helper to join current path with a suffix.
        Handles dot trimming to avoid double dots.
        """
        suffix = str(other).strip(".")
        if not suffix:
            return self
        
        new_path = f"{self._path}.{suffix}" if self._path else suffix
        return SemanticPointer(new_path)

    def __add__(self, other: Union[str, "SemanticPointerProtocol"]) -> "SemanticPointer":
        """
        Operator '+': Concatenate semantics.
        L.error + 404 -> L.error.404
        """
        return self._join(other)

    def __truediv__(self, other: Union[str, "SemanticPointerProtocol"]) -> "SemanticPointer":
        """
        Operator '/': Path-like composition.
        L.auth / "login" -> L.auth.login
        """
        return self._join(other)

    def __getitem__(self, key: Union[str, int]) -> "SemanticPointer":
        """
        Operator '[]': Index-based composition for non-identifier keys.
        L.errors[404] -> L.errors.404
        """
        return self._join(str(key))

    def __mul__(self, other: Iterable[str]) -> "PointerSetProtocol":
        """
        Operator '*': Dimensions expansion / Distribution.
        Creates a PointerSet by applying suffixes to the current pointer.
        
        L.user * {"name", "age"} -> {L.user.name, L.user.age}
        """
        # Lazy import to avoid circular dependency at module level
        from .set import PointerSet
        
        return PointerSet(self / item for item in other)