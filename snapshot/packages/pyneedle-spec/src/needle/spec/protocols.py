from typing import Protocol, Dict, Any, Union, Iterable, TypeVar
from pathlib import Path

# T_co is covariant, meaning SemanticPointerProtocol can return subtypes of itself
T_Pointer = TypeVar("T_Pointer", bound="SemanticPointerProtocol", covariant=True)


class SemanticPointerProtocol(Protocol[T_Pointer]):
    def __getattr__(self, name: str) -> T_Pointer: ...

    def __str__(self) -> str: ...

    def __hash__(self) -> int: ...

    def __eq__(self, other: Any) -> bool: ...

    def __add__(self, other: Union[str, "SemanticPointerProtocol"]) -> T_Pointer: ...

    def __truediv__(
        self, other: Union[str, "SemanticPointerProtocol"]
    ) -> T_Pointer: ...

    def __mul__(self, other: Iterable[str]) -> "PointerSetProtocol": ...


class PointerSetProtocol(Protocol):
    def __iter__(self) -> Iterable[SemanticPointerProtocol]: ...

    def __truediv__(
        self, other: Union[str, SemanticPointerProtocol]
    ) -> "PointerSetProtocol": ...

    def __or__(self, other: "PointerSetProtocol") -> "PointerSetProtocol": ...

    def __add__(
        self, other: Union[str, SemanticPointerProtocol]
    ) -> "PointerSetProtocol": ...

    def __mul__(self, other: Iterable[str]) -> "PointerSetProtocol": ...


class ResourceLoaderProtocol(Protocol):
    def fetch(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        domain: str,
        ignore_cache: bool = False,
    ) -> Union[str, None]:
        """
        Atomic lookup in a specific domain.
        Must NOT perform language fallback or cross-layer fallback internally.
        """
        ...

    def get(
        self, pointer: Union[str, SemanticPointerProtocol], domain: str | None = None
    ) -> str:
        """
        Policy-based lookup.
        Handles language fallback (Horizontal) and Identity fallback.
        """
        ...

    def load(self, domain: str, ignore_cache: bool = False) -> Dict[str, Any]:
        """
        Eagerly load all data for a domain.
        Mainly for debugging, exporting, or cache warming.
        """
        ...


class WritableResourceLoaderProtocol(ResourceLoaderProtocol, Protocol):
    def put(
        self, pointer: Union[str, SemanticPointerProtocol], value: Any, domain: str
    ) -> bool: ...

    def locate(
        self, pointer: Union[str, SemanticPointerProtocol], domain: str
    ) -> Path: ...
