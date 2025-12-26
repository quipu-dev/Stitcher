__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .parser import parse_source_code
from .inspector import parse_plugin_entry, InspectionError
from .transformer import strip_docstrings, inject_docstrings

__all__ = [
    "parse_source_code",
    "parse_plugin_entry",
    "InspectionError",
    "strip_docstrings",
    "inject_docstrings",
]
