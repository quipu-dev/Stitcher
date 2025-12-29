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


class OperatorProtocol(Protocol):
    """
    The unified interface for all operators (Config, Factory, Executor).
    An operator is an object that is configured at initialization and
    generates a result when called.
    """

    def __call__(self, key: Any) -> Any: ...
