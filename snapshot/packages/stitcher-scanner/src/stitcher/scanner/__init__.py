__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .parser import parse_source_code
from .inspector import parse_plugin_entry, InspectionError

__all__ = ["parse_source_code", "parse_plugin_entry", "InspectionError"]