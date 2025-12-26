from .parser import parse_source_code
from .inspector import parse_plugin_entry, InspectionError
from .transformer import strip_docstrings, inject_docstrings

__path__: Any
__all__: Any