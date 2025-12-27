from typing import Protocol, Dict, Any, Union, Iterable, TypeVar

# T_co is covariant, meaning SemanticPointerProtocol can return subtypes of itself
T_Pointer = TypeVar("T_Pointer", bound="SemanticPointerProtocol", covariant=True)


class SemanticPointerProtocol(Protocol[T_Pointer]):
    """
    Defines the contract for a Semantic Pointer (L).

    A Semantic Pointer is a recursive, immutable reference to a semantic location.
    It serves as the primary key for addressing resources in the Nexus.
    """

    def __getattr__(self, name: str) -> T_Pointer:
        """
        Creates a new pointer extended by the attribute name.
        Example: L.auth -> "auth"
        """
        ...

    def __str__(self) -> str:
        """
        Returns the fully qualified string representation of the pointer.
        Example: "auth.login.success"
        """
        ...

    def __hash__(self) -> int:
        """
        Pointers must be hashable to be used as dictionary keys.
        """
        ...

    def __eq__(self, other: Any) -> bool:
        """
        Pointers must be comparable with strings and other pointers.
        """
        ...

    def __add__(self, other: Union[str, "SemanticPointerProtocol"]) -> T_Pointer:
        """
        Operator '+': Joins the pointer with a string or another pointer.
        Example: L.auth + "login" -> L.auth.login
        """
        ...

    def __truediv__(self, other: Union[str, "SemanticPointerProtocol"]) -> T_Pointer:
        """
        Operator '/': Joins the pointer with a string or another pointer (path-like syntax).
        Example: L.auth / "login" -> L.auth.login
        """
        ...

    def __mul__(self, other: Iterable[str]) -> "PointerSetProtocol":
        """
        Operator '*': Distributes the pointer over a set of suffixes, creating a PointerSet.
        Example: L.auth * {"read", "write"} -> {L.auth.read, L.auth.write}
        """
        ...


class PointerSetProtocol(Protocol):
    """
    Defines the contract for a set of Semantic Pointers (Ls).

    It represents a 'Semantic Domain' or 'Surface' rather than a single point.
    """

    def __iter__(self) -> Iterable[SemanticPointerProtocol]:
        """
        Iterating over the set yields individual SemanticPointers.
        """
        ...

    def __truediv__(self, other: Union[str, SemanticPointerProtocol]) -> "PointerSetProtocol":
        """
        Operator '/': Broadcasts the join operation to all members of the set.
        Example: {L.a, L.b} / "end" -> {L.a.end, L.b.end}
        """
        ...

    def __or__(self, other: "PointerSetProtocol") -> "PointerSetProtocol":
        """
        Operator '|': Unions two PointerSets.
        """
        ...

    def __add__(self, other: Union[str, SemanticPointerProtocol]) -> "PointerSetProtocol":
        """
        Operator '+': Broadcasts the add operation to all members.
        """
        ...

    def __mul__(self, other: Iterable[str]) -> "PointerSetProtocol":
        """
        Operator '*': Broadcasts a cartesian product operation.
        """
        ...
        
    def __add__(self, other: Union[str, SemanticPointerProtocol]) -> "PointerSetProtocol":
        """
        Operator '+': Broadcasts the add operation to all members.
        """
        ...

    def __mul__(self, other: Iterable[str]) -> "PointerSetProtocol":
        """
        Operator '*': Broadcasts a cartesian product operation.
        """
        ...


class ResourceLoaderProtocol(Protocol):
    """
    Defines the contract for loading raw resource data.
    """

    def load(self, lang: str) -> Dict[str, Any]:
        """
        Loads resources for a specific language.

        Args:
            lang: The target language code (e.g., 'en', 'zh').

        Returns:
            A dictionary mapping Fully Qualified Names (FQNs) to values.
            e.g., {"auth.login.success": "Welcome!"}
        """
        ...


class NexusProtocol(Protocol):
    """
    Defines the contract for the runtime central hub (Nexus).
    """

    def get(self, pointer: Union[str, SemanticPointerProtocol], lang: str | None = None) -> str:
        """
        Resolves a pointer or string key to its localized value.

        Args:
            pointer: The semantic key to look up.
            lang: Optional explicit language override.

        Returns:
            The resolved string value, or the key itself if not found (Identity Fallback).
        """
        ...

    def reload(self, lang: str | None = None) -> None:
        """
        Clears internal caches and forces a reload of resources.

        Args:
            lang: If provided, only reload that specific language.
                  If None, reload all.
        """
        ...