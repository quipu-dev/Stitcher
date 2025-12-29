from typing import List, Union, Any
from needle.spec import OperatorProtocol, SemanticPointerProtocol


class OverlayOperator(OperatorProtocol):
    """
    A pure composition operator that delegates to a list of child operators.
    It returns the first non-None result found.
    """

    def __init__(self, operators: List[OperatorProtocol]):
        self.operators = operators

    def __call__(self, key: Union[str, SemanticPointerProtocol]) -> Any:
        # Stringify once for efficiency if children expect string
        # But OperatorProtocol allows Any, so we pass raw key mostly?
        # Standard convention for Executor Operators is to expect SemanticPointer/str.
        # Let's pass the key as-is to children to allow flexibility.
        
        for op in self.operators:
            result = op(key)
            if result is not None:
                return result
        return None