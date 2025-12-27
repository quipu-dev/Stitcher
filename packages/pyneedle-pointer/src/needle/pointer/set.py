from typing import Set, Iterable, Union, TYPE_CHECKING
from needle.spec import PointerSetProtocol, SemanticPointerProtocol

if TYPE_CHECKING:
    from .core import SemanticPointer


class PointerSet(Set["SemanticPointer"], PointerSetProtocol):
    def __truediv__(self, other: Union[str, "SemanticPointerProtocol"]) -> "PointerSet":
        # We assume elements are SemanticPointers which support __truediv__
        return PointerSet(p / other for p in self)

    def __add__(self, other: Union[str, "SemanticPointerProtocol"]) -> "PointerSet":
        return PointerSet(p + other for p in self)

    def __mul__(self, other: Iterable[str]) -> "PointerSet":
        new_set = PointerSet()
        for p in self:
            # p * other returns a PointerSet (from SemanticPointer.__mul__)
            # We union these sets together
            new_set.update(p * other)
        return new_set
