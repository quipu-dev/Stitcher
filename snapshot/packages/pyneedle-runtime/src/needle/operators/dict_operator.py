from typing import Any, Dict, Union
from needle.spec import OperatorProtocol, SemanticPointerProtocol


class DictOperator(OperatorProtocol):
    """
    A Config Operator that provides values from an in-memory dictionary.
    It automatically flavors (flattens) nested dictionaries upon initialization.
    """

    def __init__(self, data: Dict[str, Any]):
        self._data = self._flatten(data)

    def _flatten(self, data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
        items: Dict[str, Any] = {}
        for k, v in data.items():
            new_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                items.update(self._flatten(v, new_key))
            else:
                items[new_key] = v
        return items

    def __call__(self, key: Union[str, SemanticPointerProtocol]) -> Any:
        # Check strict match first
        str_key = str(key)
        val = self._data.get(str_key)
        
        if val is not None:
             return val
             
        # Optional: We could implement partial matching here if needed, 
        # but for an atomic operator, exact match is preferred.
        return None