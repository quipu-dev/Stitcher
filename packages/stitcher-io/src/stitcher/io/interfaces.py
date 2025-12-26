from typing import Dict, Protocol
from pathlib import Path


class DocumentAdapter(Protocol):
    """
    Protocol for document storage adapters.
    
    Responsible for marshaling dictionary data (Key -> Docstring) 
    to/from a physical file format (YAML, JSON, etc.).
    """

    def load(self, path: Path) -> Dict[str, str]:
        """
        Loads documentation from the specified file.
        
        Args:
            path: The path to the document file.

        Returns:
            A dictionary mapping semantic keys (e.g. "MyClass.my_method") 
            to docstrings. Returns an empty dict if file does not exist.
        """
        ...

    def save(self, path: Path, data: Dict[str, str]) -> None:
        """
        Saves documentation to the specified file.
        
        Args:
            path: The path to the document file.
            data: A dictionary mapping semantic keys to docstrings.
        """
        ...